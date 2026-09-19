#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""
prepare_sample_7_5b.py — Step 7.5B：Sampling Rule Sensitivity（采样规则敏感性，零仿真）。

上游结论（为什么下一步必须是这个，而不是 125k/150k/175k knee 扫描）
--------------------------------------------------------------------
7.5A 的 S100c（100k, f_cap=0.50，采样一致对照）给出两条同时成立的信号：

    (a) f_cap=0.50 把 CATA/SLIP 漂移从 0.0480 压到 0.0233（C6 PASS）
        → 「采样带来的供需密度变化」确实是重要机制，且可被容量同比缩放吸收；
    (b) 但 raw ratio 仍为 0.5799（≠0.50），且 Pearson 由 S100 的 0.9006 降到 0.8557
        → 还存在**第二层：样本空间分布偏差**。

6.2B 的 `allocate_cells` 规定「**每个正 OD cell 至少 1 个 agent**，余量按 trips
以 largest-remainder 分配」。该保底规则使小 cell 获得**相对过多**的代表个体，
且该畸变**随 N 减小而放大**（保底 agent 占比：200k 35.6% → 100k 71.1%）。

因此 7.5B 只做一个最干净的单变量对照：**只改采样规则，其余全部冻结**。

    S100c  现有规则（保底 +1 + largest-remainder）——已完成，直接复用
    S100r  **纯 trips-proportional**（不设保底，允许 cell 被抽到 0 个 agent）

判据（预注册，跑前固定，见 evaluate_sample_7_5b.py）
--------------------------------------------------
回答的是**机制问题**，而不是再找一个样本量：
    100k 的问题究竟是「样本数量不足」，还是「低样本下采样算法本身产生系统性空间偏差」？
    * 若 S100r 明显改善（raw→0.50 / scaled→1 / Pearson·Spearman 回升 / CATA÷SLIP 保持）
      → 保留 100k，但**修改采样算法**；
    * 若 S100r 仍明显偏离 → 才可认定该拥堵型网络存在不可忽略的 sample-size dependence，
      此时再做 125k/150k/175k 寻找最小稳定样本量才有意义。

★本脚本只做「人口侧 + 采样规则诊断」（零 MATSim）
------------------------------------------------
    阶段 1  6.2B（**monkeypatch allocate_cells 为纯比例**）
            --target-agents 100000  ->  reports/matsim_population_6_2b_s100r/
    阶段 2  连通性修复（复用冻结 network_cleaned.xml.gz）
                                    ->  reports/matsim_population_6_2b_connected_s100r/
    阶段 3  6.3.3A 出发时刻剖面       ->  reports/matsim_departure_6_3_3a_s100r/

另出**采样规则诊断**（不依赖 MATSim）：
    reports/od_sample_7_5b/sampling_rule_diagnostics.json
    reports/od_sample_7_5b/sampling_rule_summary.csv
    reports/od_sample_7_5b/od_cell_sampling_rules.csv     （逐 cell：trips / 两种规则的 agent 数 / EF）

7.5B 要求必须输出的量（用户点名的 6 项）
--------------------------------------
    positive OD cells / sampled OD cells / zero-sampled OD cells /
    OD coverage / Σ expansion_factor / 每个 OD cell 的重构误差

★守恒口径说明（必须写清，否则会误读）
------------------------------------
    EF_ij = T_ij / N_ij（沿用 6.2B 冻结定义，逐 cell 精确）→ 被抽到 0 的 cell
    **没有代表个体**，其 trips 不被任何 agent 承载：
        ΣEF = Σ_{(i,j): N_ij>0} T_ij  =  ΣT × OD coverage（trips 加权）
        f_realized = ΣEF / 459,794   （<1 表示名义需求未完全被样本承载）
    由于 7.5A 审计已证 **EF 不被 MATSim 消费**，ΣEF 只影响账面口径，不影响仿真；
    评价层的扩样系数由 `evaluate_sample_7_5b.py` 决定（主口径与 S100c 同 SCALE）。

★一律写入**新目录**，绝不覆盖冻结件（200k 三阶段产物 / 7.5A 的 _s100k 三阶段产物）。

用法
----
    python scripts/od/prepare_sample_7_5b.py --design-only   # 只出设计 + 采样规则诊断
    python scripts/od/prepare_sample_7_5b.py                 # 造 S100r 人口全链
    python scripts/od/prepare_sample_7_5b.py --force         # 强制重建
"""
from __future__ import annotations

import argparse
import csv
import gzip
import importlib.util
import json
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(r"D:\Luan\2026-05\2_Singapore")
OUT = ROOT / "reports" / "od_sample_7_5b"

SCRIPTS_OD = ROOT / "scripts" / "od"
SCRIPTS_MAT = ROOT / "scripts" / "matsim"
S75A = ROOT / "reports" / "od_sample_7_5a"

LAMBDA_TAG = "0p075"
LAMBDA_FIXED = 0.075
REAL_CAR_OD_TOTAL = 459794.0
N_REF = 200_000
N_100 = 100_000
FROZEN_SEED = 20260912
F_CAP = 0.50                      # = N_100/N_REF —— 采样一致性校正（继承 S100c，仅此对照）
OD_PARQUET = ROOT / "reports" / "matsim_population" / f"car_prior_od_lambda_{LAMBDA_TAG}.parquet"

# 复用的既有产物（只读）
S100C_OUT = S75A / "S100c_lam0p075_cap0p50"
E06_OUT = ROOT / "reports" / "od_calibration_7_4_2" / "E06_lam0p075_cap1p00"

# S100r 的三阶段新目录（绝不覆盖冻结件）
POP_R_DIR = ROOT / "reports" / "matsim_population_6_2b_s100r"
POP_R_CONN_DIR = ROOT / "reports" / "matsim_population_6_2b_connected_s100r"
DEP_R_DIR = ROOT / "reports" / "matsim_departure_6_3_3a_s100r"


def scale_for(n: int) -> float:
    return REAL_CAR_OD_TOTAL / float(n)


# --------------------------------------------------------------------------
# 采样规则：纯 trips-proportional（无保底）
# --------------------------------------------------------------------------
def proportional_alloc(od: pd.DataFrame, target: int, rng: np.random.Generator) -> pd.DataFrame:
    """纯 trips-proportional 采样（**不设**「每正 OD cell >=1 agent」保底）。

    与 6.2B `allocate_cells` 的唯一差异：
        floor 版:  raw = (target - n_cells) * w ;  cnt = 1 + floor(raw)   <- 保底 +1
        本 版:     raw =  target          * w ;  cnt =     floor(raw)   <- 无保底
    余量（largest-remainder）分配机制逐行一致（同 tie-break 抖动 1e-12）。
    后果：trips 很小的 cell 会被抽到 0 个 agent（本实验要观测的正是这一点）。
    """
    n_cells = len(od)
    T = od.trips.to_numpy(float)
    S = float(T.sum())
    raw = target * (T / S)
    cnt = np.floor(raw).astype(np.int64)
    left = int(target - cnt.sum())
    if left > 0:
        frac = raw - cnt
        order = np.argsort(-(frac + rng.random(len(frac)) * 1e-12))
        cnt[order[:left]] += 1
    elif left < 0:                                  # 理论不可达（sum(floor) <= target）
        frac = raw - cnt
        order = np.argsort(frac)                    # 从最小小数部分回收
        cnt[order[: -left]] -= 1
    if int(cnt.sum()) != target:
        raise AssertionError(f"比例分配总数 {int(cnt.sum())} != target {target}")
    if (cnt < 0).any():
        raise AssertionError("出现负 agent 数")

    out = od.copy()
    out["agent_count"] = cnt
    # EF_ij = T_ij / N_ij（沿用 6.2B 定义）；被抽到 0 的 cell 记 0（不写盘，仅账面）
    ef = np.zeros(n_cells, dtype=float)
    m = cnt > 0
    ef[m] = T[m] / cnt[m]
    out["expansion_factor"] = ef
    return out


def _alloc_floor_reference(od: pd.DataFrame, target: int, seed: int) -> np.ndarray:
    """复现 6.2B 冻结的保底规则（仅用于诊断对照，不写盘）。"""
    rng = np.random.default_rng(seed + int(round(LAMBDA_FIXED * 1000)))
    n_cells = len(od)
    T = od.trips.to_numpy(float)
    rem = target - n_cells
    if rem < 0:
        raise ValueError(f"保底规则要求 target >= 正 cell 数（{n_cells}），target={target}")
    raw = rem * (T / T.sum())
    cnt = 1 + np.floor(raw).astype(np.int64)
    left = int(target - cnt.sum())
    if left > 0:
        frac = raw - np.floor(raw)
        order = np.argsort(-(frac + rng.random(len(frac)) * 1e-12))
        cnt[order[:left]] += 1
    return cnt


def sampling_rule_diagnostics() -> dict:
    """零仿真：对比保底规则 vs 纯比例规则的分配后果（100k 为主，200k 作参照）。"""
    od = pd.read_parquet(OD_PARQUET)
    od["trips"] = pd.to_numeric(od.trips, errors="coerce").fillna(0)
    od = od[od.trips > 1e-12].reset_index(drop=True)
    T = od.trips.to_numpy(float)
    S = float(T.sum())
    n_cells = len(od)

    rows = []
    per_cell = None
    for target in (N_100, N_REF):
        c_floor = _alloc_floor_reference(od, target, FROZEN_SEED)
        rng = np.random.default_rng(FROZEN_SEED + int(round(LAMBDA_FIXED * 1000)))
        c_prop = proportional_alloc(od, target, rng)["agent_count"].to_numpy()
        for rule, c in (("FLOOR_PLUS_1", c_floor), ("PURE_TRIPS_PROP", c_prop)):
            zero = int((c == 0).sum())
            dropped = float(T[c == 0].sum())
            sampled_trips = float(S - dropped)
            rows.append({
                "target_agents": target,
                "sampling_rule": rule,
                "positive_od_cells": n_cells,
                "sampled_od_cells": int((c > 0).sum()),
                "zero_sampled_od_cells": zero,
                "od_coverage": float((c > 0).mean()),
                "dropped_trips": dropped,
                "dropped_trip_share": dropped / S,
                "sum_expansion_factor": sampled_trips,
                "f_realized": sampled_trips / S,
                "agents_min": int(c.min()), "agents_median": float(np.median(c)),
                "agents_mean": float(c.mean()), "agents_max": int(c.max()),
                "floor_agents": int(n_cells) if rule == "FLOOR_PLUS_1" else 0,
                "floor_agent_share": (n_cells / target) if rule == "FLOOR_PLUS_1" else 0.0,
                "cells_with_1_agent": int((c == 1).sum()),
                "ef_mean": float(sampled_trips / target),
                "max_od_cell_reconstruction_error": float(dropped) if zero else 0.0,
            })
        if target == N_100:
            per_cell = pd.DataFrame({
                "origin_zone": od.origin_zone.to_numpy(),
                "destination_zone": od.destination_zone.to_numpy(),
                "trips": T,
                "agents_floor": c_floor,
                "agents_prop": c_prop,
                "ef_floor": np.where(c_floor > 0, T / np.maximum(c_floor, 1), 0.0),
                "ef_prop": np.where(c_prop > 0, T / np.maximum(c_prop, 1), 0.0),
                "zero_under_prop": (c_prop == 0),
                "recon_error_floor": np.where(c_floor > 0, 0.0, T),
                "recon_error_prop": np.where(c_prop > 0, 0.0, T),
            })

    df = pd.DataFrame(rows)
    OUT.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUT / "sampling_rule_summary.csv", index=False, encoding="utf-8-sig")
    if per_cell is not None:
        per_cell.to_csv(OUT / "od_cell_sampling_rules.csv", index=False, encoding="utf-8-sig")

    d100 = df[df.target_agents == N_100].set_index("sampling_rule").to_dict("index")
    diag = {
        "step": "7.5B",
        "lambda_fixed": LAMBDA_FIXED,
        "positive_od_cells": n_cells,
        "real_car_od_total": S,
        "mode": "zero-simulation (allocation-only)",
        "question": ("100k 的问题究竟是「样本数量不足」，还是「低样本下保底采样算法本身"
                     "产生系统性空间偏差」？"),
        "floor_rule_definition": ("6.2B allocate_cells：每正 OD cell >=1 agent，"
                                  "余量 (target - n_cells) 按 trips largest-remainder 分配"),
        "prop_rule_definition": ("纯 trips-proportional：raw = target * T_ij/ΣT，"
                                 "floor 后按小数部分 largest-remainder 补余，无保底"),
        "at_100k": d100,
        "at_200k_reference": df[df.target_agents == N_REF].set_index("sampling_rule").to_dict("index"),
        "reading": ("保底规则把大量 agent 强行放在 trips 极小的 cell 上；该占位比例随 N 减小"
                    "急剧放大（floor_agent_share：200k 35.6% -> 100k 71.1%），"
                    "而纯比例规则该占比恒为 0。"),
    }
    (OUT / "sampling_rule_diagnostics.json").write_text(
        json.dumps(diag, ensure_ascii=False, indent=2), encoding="utf-8")
    return diag


# --------------------------------------------------------------------------
# module loading (monkeypatch-only reuse of frozen builders)
# --------------------------------------------------------------------------
def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def run_with_argv(mod_main, argv: list[str]) -> None:
    old = sys.argv
    try:
        sys.argv = argv
        mod_main()
    finally:
        sys.argv = old


def population_stats(xml_path: Path) -> dict:
    n = 0
    s_ef = 0.0
    s_od = 0.0
    with gzip.open(xml_path, "rt", encoding="utf-8", errors="replace") as fh:
        for line in fh:
            if line.lstrip().startswith("<person "):
                n += 1
            m = re.search(r'name="expansionFactor" class="java.lang.Double">([0-9eE\.\-\+]+)<', line)
            if m:
                s_ef += float(m.group(1))
            m2 = re.search(r'name="odTrips" class="java.lang.Double">([0-9eE\.\-\+]+)<', line)
            if m2:
                s_od += float(m2.group(1))
    return {"persons": n, "sum_expansion_factor": s_ef, "sum_od_trips": s_od,
            "mean_ef": (s_ef / n) if n else None}


# --------------------------------------------------------------------------
# stage 1 / 2 / 3
# --------------------------------------------------------------------------
def stage1_population(force: bool) -> dict:
    target = POP_R_DIR / f"population_lambda_{LAMBDA_TAG}.xml.gz"
    if target.exists() and not force:
        st = population_stats(target)
        if st["persons"] == N_100:
            print(f"[1/3] 已存在且 persons={st['persons']:,} -> 复用")
            return {"stage": "6.2B_population_pure_prop", "reused": True, "path": str(target), **st}
    mod = load_module(SCRIPTS_OD / "build_matsim_population_6_2b.py", "b6_2b_s100r")
    mod.OUT = Path("reports/matsim_population_6_2b_s100r")   # ★ 新目录，不覆盖冻结件
    mod.allocate_cells = proportional_alloc                  # ★ 唯一逻辑变更：替换采样规则
    print(f"[1/3] 6.2B(pure trips-proportional) --target-agents {N_100:,} -> {POP_R_DIR}")
    run_with_argv(mod.main, [
        "build_matsim_population_6_2b.py",
        "--project-root", str(ROOT),
        "--lambdas", f"{LAMBDA_FIXED}",
        "--target-agents", str(N_100),
        "--seed", str(FROZEN_SEED),
    ])
    st = population_stats(target)
    # 6.2B 自身的 PASS 判据含「coverage == 1.0 且 missing_cells == 0」→ 对纯比例规则
    # **必然 FAIL**（这正是实验目的）。此处读回逐 cell 守恒表以便按 7.5B 口径复核。
    cons = POP_R_DIR / f"od_cell_conservation_lambda_{LAMBDA_TAG}.csv"
    cell_stats = None
    if cons.exists():
        c = pd.read_csv(cons, encoding="utf-8-sig")
        zero = int((c.agent_count == 0).sum())
        cell_stats = {
            "positive_od_cells": int(len(c)),
            "sampled_od_cells": int((c.agent_count > 0).sum()),
            "zero_sampled_od_cells": zero,
            "od_coverage": float((c.agent_count > 0).mean()),
            "dropped_trips": float(c.loc[c.agent_count == 0, "trips"].sum()),
            "f_realized": float(c.loc[c.agent_count > 0, "trips"].sum() / c.trips.sum()),
            "max_od_cell_reconstruction_error": float(c.abs_error.max()),
            "sampled_cell_reconstruction_error_max": float(c.loc[c.agent_count > 0, "abs_error"].max()),
        }
    return {"stage": "6.2B_population_pure_prop", "reused": False, "path": str(target),
            "sampling_rule": "PURE_TRIPS_PROP", "cell_stats": cell_stats, **st}


def stage2_connected(force: bool) -> dict:
    target = POP_R_CONN_DIR / f"population_lambda_{LAMBDA_TAG}.xml.gz"
    if target.exists() and not force:
        st = population_stats(target)
        if st["persons"] == N_100:
            print(f"[2/3] 已存在且 persons={st['persons']:,} -> 复用")
            return {"stage": "connectivity_repair", "reused": True, "path": str(target), **st}
    mod = load_module(SCRIPTS_MAT / "prepare_connected_scenario.py", "pc_s100r")
    net_dir = ROOT / "reports" / "matsim_network"
    cleaned = net_dir / "network_cleaned.xml.gz"
    if not cleaned.exists():
        raise FileNotFoundError(f"缺少冻结清洗网络 {cleaned}（不得重算，保持冻结）")
    mod.POP_IN = POP_R_DIR                               # ★ 只改输入/输出目录
    mod.POP_OUT = POP_R_CONN_DIR
    print(f"[2/3] 连通性修复 -> {POP_R_CONN_DIR}（复用冻结 {cleaned.name}）")
    c_links, c_nodes = mod.read_network(cleaned)
    o_links, o_nodes = mod.read_network(net_dir / "network.xml.gz")
    stats = mod.repair_population(LAMBDA_TAG, c_links, c_nodes, o_links, o_nodes)
    st = population_stats(target)
    return {"stage": "connectivity_repair", "reused": False, "path": str(target),
            "repair": stats, **st}


def stage3_departure(force: bool) -> dict:
    target = DEP_R_DIR / f"population_lambda_{LAMBDA_TAG}.xml.gz"
    if target.exists() and not force:
        st = population_stats(target)
        if st["persons"] == N_100:
            print(f"[3/3] 已存在且 persons={st['persons']:,} -> 复用")
            return {"stage": "departure_profile", "reused": True, "path": str(target), **st}
    mod = load_module(SCRIPTS_OD / "build_departure_profile_6_3_3a.py", "dep_s100r")
    mod.POP_DIR = POP_R_CONN_DIR                         # ★ 只改输入/输出目录
    mod.FALLBACK_POP_DIR = ROOT / "__nonexistent__"
    mod.OUT = DEP_R_DIR
    print(f"[3/3] 出发时刻剖面 -> {DEP_R_DIR}")
    run_with_argv(mod.main, [
        "build_departure_profile_6_3_3a.py",
        "--project-root", str(ROOT),
        "--lambdas", f"{LAMBDA_FIXED}",
        "--seed", str(FROZEN_SEED),
    ])
    st = population_stats(target)
    summary_csv = DEP_R_DIR / "departure_assignment_summary.csv"
    dep_sum = None
    if summary_csv.exists():
        with open(summary_csv, encoding="utf-8-sig", newline="") as f:
            rows = list(csv.DictReader(f))
            dep_sum = rows[0] if rows else None
    return {"stage": "departure_profile", "reused": False, "path": str(target),
            "departure_summary": dep_sum, **st}


# --------------------------------------------------------------------------
# design artefacts
# --------------------------------------------------------------------------
def matrix_rows() -> list[dict]:
    return [
        {
            "experiment_id": "S200",
            "role": "reference_200k",
            "sampling_rule": "FLOOR_PLUS_1",
            "sample_agents": N_REF,
            "f_cap": 1.00,
            "scale": round(scale_for(N_REF), 5),
            "population_dir": "reports/matsim_departure_6_3_3a",
            "output_dir": "reports/od_calibration_7_4_2/E06_lam0p075_cap1p00",
            "mode": "REUSE_E06",
            "note": "参考场景（=D01/E06，200k@1.00）；不重跑",
        },
        {
            "experiment_id": "S100c",
            "role": "baseline_rule_100k",
            "sampling_rule": "FLOOR_PLUS_1",
            "sample_agents": N_100,
            "f_cap": F_CAP,
            "scale": round(scale_for(N_100), 5),
            "population_dir": "reports/matsim_departure_6_3_3a_s100k",
            "output_dir": "reports/od_sample_7_5a/S100c_lam0p075_cap0p50",
            "mode": "REUSE_EXISTING",
            "note": "现行保底规则 + f_cap=0.50（=N/N_ref 采样一致校正）；已完成，直接复用",
        },
        {
            "experiment_id": "S100r",
            "role": "pure_proportional_100k",
            "sampling_rule": "PURE_TRIPS_PROP",
            "sample_agents": N_100,
            "f_cap": F_CAP,
            "scale": round(scale_for(N_100), 5),
            "population_dir": "reports/matsim_departure_6_3_3a_s100r",
            "output_dir": "reports/od_sample_7_5b/S100r_lam0p075_cap0p50",
            "mode": "RUN",
            "note": "★唯一变量 = 采样规则（去保底、纯 trips 比例）；其余全部冻结",
        },
    ]


def write_matrix(path: Path) -> None:
    rows = matrix_rows()
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)


def write_design(path: Path, diag: dict | None, build: dict | None) -> None:
    L = []
    L.append("# Step 7.5B — Sampling Rule Sensitivity（采样规则敏感性）\n")
    L.append("**零仿真设计 + 100k 人口管线 + 一份 MATSim 实验**。"
             "核心问题：100k 的残余非线性，究竟来自**样本数量**，还是来自"
             "**低样本下「每正 OD cell ≥1 agent」保底采样规则**本身？\n")
    L.append("## 1. 为什么先做 7.5B，而不是 125k/150k/175k knee 扫描\n")
    L.append("7.5A 的 S100c（100k, f_cap=0.50）给出两条**同时成立**的信号：\n")
    L.append("| 信号 | 数值 | 含义 |")
    L.append("|---|---|---|")
    L.append("| (a) `CATA/SLIP` 漂移 | 0.0480（S100）→ **0.0233**（S100c），C6 PASS | "
             "「采样导致的供需密度变化」是重要机制，且**可被容量同比缩放吸收** |")
    L.append("| (b) `raw ratio` / `Pearson` | **0.5799**（≠0.50）；Pearson 0.9006 → **0.8557** | "
             "仍存在**第二层：样本空间分布偏差** |")
    L.append("")
    L.append("6.2B `allocate_cells` 规定「**每个正 OD cell 至少 1 个 agent**，余量按 trips "
             "largest-remainder 分配」。该保底规则让小 trips 的 cell 获得**相对过多**代表个体，"
             "且畸变随 N 减小而急剧放大：\n")
    L.append("| N_sample | 保底 agent 数 | 占全部 agent 比例 |")
    L.append("|---:|---:|---:|")
    L.append(f"| 200,000 | 71,136 | **35.6%** |")
    L.append(f"| 100,000 | 71,136 | **71.1%** |")
    L.append("")
    L.append("→ 因此在做任何样本量扫描之前，必须先回答：**保底采样到底是不是残余非线性的主因。**"
             "两者后续处理完全不同：若 S100r 改善 → 保留 100k 但改采样算法；"
             "若 S100r 仍偏离 → 才可认定存在 sample-size dependence。\n")
    L.append("## 2. 单变量设计（只改采样规则）\n")
    L.append("```text")
    L.append("S100c（现有规则）  每正 OD cell >= 1 agent  + largest-remainder    已完成，复用")
    L.append("S100r（纯比例）    不设保底；按 OD trips 比例直接抽 100k（允许 cell = 0 agent）  ← 本步")
    L.append("```\n")
    L.append("**完全冻结**：`N_sample=100,000` / `λ=0.075` / `flowCapacityFactor=storageCapacityFactor="
             f"{F_CAP:.2f}`（= N/N_ref，采样一致性校正）/ 20 iterations / `seed=4711` / "
             "`routingRandomness=0` / 同一 network / 同一 OD / 同一 departure profile / "
             "同一 7.3.6A Final Crosswalk / 同一 7.1 观测靶场。\n")
    L.append("> `f_cap=0.50` 在此**仅作采样一致性校正**（保持同一物理供需比），"
             "**不是**交通供给标定参数——与 Phase 1 的 `capacity_factor` 严格区分。\n")
    L.append("## 3. 采样规则诊断（零仿真，本脚本直接算）\n")
    if diag:
        L.append(f"λ=0.075 正 OD cell 数 = **{diag['positive_od_cells']:,}**，"
                 f"ΣT = **{diag['real_car_od_total']:,.0f}**。\n")
        L.append("| N_sample | 采样规则 | sampled cells | zero-sampled cells | OD coverage | "
                 "丢弃 trips | ΣEF | `f_realized` | agent 数 min/中位/max |")
        L.append("|---:|---|---:|---:|---:|---:|---:|---:|---|")
        for target in (N_100, N_REF):
            for rule in ("FLOOR_PLUS_1", "PURE_TRIPS_PROP"):
                r = diag["at_100k" if target == N_100 else "at_200k_reference"][rule]
                L.append(f"| {target:,} | `{rule}` | {r['sampled_od_cells']:,} | "
                         f"**{r['zero_sampled_od_cells']:,}** | {r['od_coverage']:.4f} | "
                         f"{r['dropped_trips']:,.0f} ({r['dropped_trip_share']*100:.2f}%) | "
                         f"{r['sum_expansion_factor']:,.0f} | {r['f_realized']:.5f} | "
                         f"{r['agents_min']:.0f}/{r['agents_median']:.0f}/{r['agents_max']:.0f} |")
        L.append("")
        L.append("> **读法**：保底规则下**零 cell 被遗漏**（coverage = 1.0），但小 cell 被系统性高估；"
                 "纯比例规则下 100k 有大量 cell 被抽到 0（其 trips 无代表个体），"
                 "agent 集中到高 trips 的 cell（max 26 → 87）。\n")
    L.append("## 4. 实验矩阵\n")
    L.append("| 实验 | 角色 | 采样规则 | N_sample | f_cap | SCALE | 模式 |")
    L.append("|---|---|---|---:|---:|---:|---|")
    for r in matrix_rows():
        L.append(f"| **{r['experiment_id']}** | {r['role']} | `{r['sampling_rule']}` | "
                 f"{r['sample_agents']:,} | {r['f_cap']:.2f} | {r['scale']:.5f} | `{r['mode']}` |")
    L.append("")
    L.append("## 5. S100r 人口管线（本脚本执行，全部写入新目录）\n")
    L.append("| 阶段 | 脚本（冻结件，仅 patch 目录常量 + 替换采样函数） | 输出 |")
    L.append("|---|---|---|")
    L.append("| 1 | `build_matsim_population_6_2b.py`（`allocate_cells` → 纯比例） "
             "`--target-agents 100000` | `reports/matsim_population_6_2b_s100r/` |")
    L.append("| 2 | `prepare_connected_scenario.py`（复用冻结 `network_cleaned.xml.gz`） | "
             "`reports/matsim_population_6_2b_connected_s100r/` |")
    L.append("| 3 | `build_departure_profile_6_3_3a.py` | `reports/matsim_departure_6_3_3a_s100r/` |")
    L.append("")
    L.append("> **不覆盖**冻结件（200k 三阶段产物、7.5A 的 `*_s100k` 三阶段产物、S100c 输出）。"
             "空间实现逻辑（URANOF/POI→link 抽样、XML 写出、守恒校验）**逐字节复用**，"
             "只替换 `allocate_cells`。\n")
    if build:
        L.append("## 6. 本次构建校验\n")
        L.append("| 阶段 | persons | ΣEF | ΣodTrips | 复用 |")
        L.append("|---|---:|---:|---:|---|")
        for st in build.get("stages", []):
            L.append(f"| {st['stage']} | {st.get('persons', 0):,} | "
                     f"{st.get('sum_expansion_factor', 0):,.1f} | "
                     f"{st.get('sum_od_trips', 0):,.1f} | {st.get('reused')} |")
        L.append("")
        cs = next((s.get("cell_stats") for s in build.get("stages", [])
                   if s.get("cell_stats")), None)
        if cs:
            L.append("**OD 覆盖与守恒（7.5B 要求输出的 6 项）**\n")
            L.append("| 量 | 值 |")
            L.append("|---|---:|")
            L.append(f"| positive OD cells | {cs['positive_od_cells']:,} |")
            L.append(f"| sampled OD cells | {cs['sampled_od_cells']:,} |")
            L.append(f"| **zero-sampled OD cells** | **{cs['zero_sampled_od_cells']:,}** |")
            L.append(f"| **OD coverage** | **{cs['od_coverage']:.4f}** |")
            L.append(f"| 未承载 trips（dropped） | {cs['dropped_trips']:,.0f} |")
            L.append(f"| `f_realized` = ΣEF/ΣT | **{cs['f_realized']:.5f}** |")
            L.append(f"| 逐 cell 重构误差 max（全体） | {cs['max_od_cell_reconstruction_error']:.6g} |")
            L.append(f"| 逐 cell 重构误差 max（被采样 cell） | "
                     f"{cs['sampled_cell_reconstruction_error_max']:.3e} |")
            L.append("")
        L.append(f"**构建状态：{build.get('status')}**"
                 f"（判据：persons == {N_100:,}；采样 cell 逐 cell 守恒误差 ≈ 0）\n")
    L.append("## 7. 已识别但本步不做的\n")
    L.append("- 不做 125k/150k/175k 样本量 knee 扫描（须待 7.5B 机制结论）；")
    L.append("- 不动 capacity（`f_cap=0.50` 仅作采样一致性校正）；")
    L.append("- 不跑纯比例 @200k（可作为后续对称对照）；")
    L.append("- **λ 仍不冻结**（固定 0.075 仅为控制变量）。\n")
    L.append("---\n")
    L.append("口径：观测 7.1 冻结；仿真 `median(edges HRSx-yavg) × SCALE`；"
             "crosswalk = 7.3.6A Final；randomSeed=4711；20 it；ReRoute 拥堵反馈启用。\n")
    path.write_text("\n".join(L), encoding="utf-8")


# --------------------------------------------------------------------------
def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--design-only", action="store_true")
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()

    OUT.mkdir(parents=True, exist_ok=True)
    write_matrix(OUT / "sample_matrix_7_5b.csv")
    print(f"matrix -> {OUT / 'sample_matrix_7_5b.csv'}")

    print("[diag] 采样规则诊断（零仿真）")
    diag = sampling_rule_diagnostics()
    r = diag["at_100k"]["PURE_TRIPS_PROP"]
    print(f"       100k 纯比例: sampled={r['sampled_od_cells']:,} "
          f"zero={r['zero_sampled_od_cells']:,} coverage={r['od_coverage']:.4f} "
          f"dropped={r['dropped_trips']:,.0f} f_realized={r['f_realized']:.5f}")
    print(f"       -> {OUT / 'sampling_rule_summary.csv'}")

    build = None
    if not args.design_only:
        stages = []
        stages.append(stage1_population(args.force))
        stages.append(stage2_connected(args.force))
        stages.append(stage3_departure(args.force))
        cs = next((s.get("cell_stats") for s in stages if s.get("cell_stats")), None)
        ok = (all(s.get("persons") == N_100 for s in stages)
              and cs is not None
              and cs["sampled_cell_reconstruction_error_max"] < 1e-8)
        build = {
            "step": "7.5B",
            "status": "PASS" if ok else "FAIL",
            "design": "sampling_rule_sensitivity (single variable = allocation rule)",
            "lambda_fixed": LAMBDA_FIXED,
            "n_sample": N_100,
            "f_cap": F_CAP,
            "sampling_rule": "PURE_TRIPS_PROP",
            "baseline_rule": "FLOOR_PLUS_1",
            "real_car_od_total": REAL_CAR_OD_TOTAL,
            "scale": round(scale_for(N_100), 5),
            "cell_stats": cs,
            "stages": stages,
            "note_6_2b_status": ("6.2B 自身 PASS 判据含 coverage==1.0 与 missing_cells==0，"
                                 "对纯比例规则必然 FAIL —— 这正是本实验要观测的现象；"
                                 "7.5B 采用自己的口径（persons==100k 且被采样 cell 逐 cell 守恒）。"),
            "frozen_artifacts_untouched": [
                "reports/matsim_population_6_2b",
                "reports/matsim_population_6_2b_connected",
                "reports/matsim_departure_6_3_3a",
                "reports/matsim_population_6_2b_s100k",
                "reports/matsim_population_6_2b_connected_s100k",
                "reports/matsim_departure_6_3_3a_s100k",
                "reports/od_sample_7_5a/S100c_lam0p075_cap0p50",
            ],
        }
        (OUT / "s100r_build_summary.json").write_text(
            json.dumps(build, ensure_ascii=False, indent=2), encoding="utf-8")

    write_design(OUT / "STEP7_5B_DESIGN.md", diag, build)
    print(f"design -> {OUT / 'STEP7_5B_DESIGN.md'}")
    if build:
        print("BUILD STATUS:", build["status"])
        for s in build["stages"]:
            print(f"  {s['stage']:26s} persons={s.get('persons', 0):>8,} "
                  f"ΣEF={s.get('sum_expansion_factor', 0):>12,.1f} reused={s.get('reused')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
