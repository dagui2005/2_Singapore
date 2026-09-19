#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""
prepare_sample_7_5a.py — Step 7.5A（二）：固定样本量采样架构 + 100k 人口管线（零仿真）。

背景（为什么需要这一步）
------------------------
7.4.3 证明 demand scale **不能单独补齐量级缺口**（Sim/Obs 峰 @f=1.20 仅 0.8601），
且 D02–D04 用「200k→250k agents」实现需求放大，**运行时间随 agent 数暴涨**
（D04 单次 ≈ 493 min）。若后续还要做 λ 细搜 / OD attraction / departure profile /
route choice / 最终验证，按 200k~250k/次跑十几次是不可接受的计算规模。

核心认识（由 7.5A 审计确证，见 STEP7_5A_DEMAND_CHAIN_AUDIT.md）
------------------------------------------------------------
    MATSim QSim **只消费 person/vehicle 数**；`expansionFactor` / `odTrips` 只是
    人口 XML 的自定义属性，**不被任何 MATSim 代码读取**（jar 字节级扫描零命中于
    MATSim 自身 class）→ linkstats 原始口径随 agent 数近似线性变化。
    因此「代表多少现实出行」的扩样权重必须在**评价层**施加：
        SCALE = ΣT / N_sample
    这意味着 **样本量 N_sample 与需求量可解耦**：

        真实需求 ΣT = 459,794
             |
             v  采样（6.2B allocate_cells：每正 cell >=1 agent，余量按 trips 分配）
        N_sample 个代表性 agent   <-- 只决定计算量
             |
             v  QSim
        linkstats 原始车辆数
             |
             v  评价层 × SCALE = ΣT / N_sample   <-- 有效需求权重在此形成
        与观测比对

三层需求（论文口径）
--------------------
    第一层 真实需求      ΣT          （459,794；与 N 无关）
    第二层 采样率        N_sample    （200k 基准 / **100k 标定主力** / 50k 探索）
    第三层 有效需求权重  SCALE       （ΣT / N_sample：200k→2.29897，100k→4.59794）

★硬约束（必须先说清，否则会踩坑）
--------------------------------
    `allocate_cells` 要求 `target_agents >= 正 OD cell 数`。λ=0.075 时
    **正 OD cell = 71,136** → **N_sample 下限 71,136**；因此
    **50k 不可行**（会直接 ValueError），100k 是可行且推荐的最低标定档。

容量与采样率的关系（★关键判断，不是"调参"）
------------------------------------------
    `flowCapacityFactor` 决定每车经历的供给饱和度。若把 N_sample 从 200k 降到 100k
    而把 f_cap 固定在 1.00，则车密度减半 → **拥堵物理被改变**，
    S100 与 S200 的差异就混杂了「采样效应」与「供给/需求比效应」，
    无法判定 100k 是否是可替代样本。
    要保持**同一物理交通场景**，f_cap 必须随采样率同比缩放
    （200k@1.00 ↔ 100k@0.50）。这是采样一致性的数学要求，不是性能旋钮。

    因此本步骤并列两个 100k 变体：
      * S100  （f_cap=1.00）：用户指定的字面设计——"同容量下减样本"
      * S100c （f_cap=0.50）：**采样一致对照**——"同物理场景下减样本"
    再与 S200（=D01/E06，200k@1.00）比较。**最终由用户裁定**采用哪一个作为
    后续标定的样本口径。

实验矩阵（reports/od_sample_7_5a/sample_matrix.csv）
--------------------------------------------------
    S200  200k f_cap=1.00 SCALE=2.29897  REUSE_E06（不重跑）
    S100  100k f_cap=1.00 SCALE=4.59794  RUN
    S100c 100k f_cap=0.50 SCALE=4.59794  RUN（采样一致对照，可选）

本脚本只做 **人口侧**（零 MATSim）：
    阶段 1  6.2B --target-agents 100000        -> reports/matsim_population_6_2b_s100k/
    阶段 2  连通性修复（复用冻结 network_cleaned.xml.gz）-> reports/matsim_population_6_2b_connected_s100k/
    阶段 3  6.3.3A 出发时刻剖面                -> reports/matsim_departure_6_3_3a_s100k/

★一律写入**新目录**，绝不覆盖冻结的 200k 三阶段产物
（`matsim_population_6_2b` / `..._connected` / `matsim_departure_6_3_3a`）。
实现方式：以模块方式 import 三个冻结构建脚本，**只 monkeypatch 其输出/输入目录常量**，
其余逻辑（含守恒校验）逐字节复用。

产物
----
    reports/od_sample_7_5a/sample_matrix.csv
    reports/od_sample_7_5a/STEP7_5A_DESIGN.md
    reports/od_sample_7_5a/sample_build_summary.json
    reports/matsim_population_6_2b_s100k/...
    reports/matsim_population_6_2b_connected_s100k/...
    reports/matsim_departure_6_3_3a_s100k/...

用法
----
    python scripts/od/prepare_sample_7_5a.py --design-only   # 只出设计文件（不造人口）
    python scripts/od/prepare_sample_7_5a.py                 # 造 100k 人口全链
    python scripts/od/prepare_sample_7_5a.py --force         # 强制重建
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

ROOT = Path(r"D:\Luan\2026-05\2_Singapore")
OUT = ROOT / "reports" / "od_sample_7_5a"

SCRIPTS_OD = ROOT / "scripts" / "od"
SCRIPTS_MAT = ROOT / "scripts" / "matsim"

LAMBDA_TAG = "0p075"
LAMBDA_FIXED = 0.075
REAL_CAR_OD_TOTAL = 459794.0
POSITIVE_OD_CELLS = 71136          # λ=0.075，来自 car_prior_od_lambda_0p075.parquet
N_REF = 200_000
N_100 = 100_000
FROZEN_SEED = 20260912

POP_100_DIR = ROOT / "reports" / "matsim_population_6_2b_s100k"
POP_100_CONN_DIR = ROOT / "reports" / "matsim_population_6_2b_connected_s100k"
DEP_100_DIR = ROOT / "reports" / "matsim_departure_6_3_3a_s100k"

DEP_200_DIR = ROOT / "reports" / "matsim_departure_6_3_3a"
E06_OUT = ROOT / "reports" / "od_calibration_7_4_2" / "E06_lam0p075_cap1p00"
RUN_OUT_ROOT = OUT


def scale_for(n: int) -> float:
    return REAL_CAR_OD_TOTAL / float(n)


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


# --------------------------------------------------------------------------
# population stat verification (streaming)
# --------------------------------------------------------------------------
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
    target = POP_100_DIR / f"population_lambda_{LAMBDA_TAG}.xml.gz"
    if target.exists() and not force:
        st = population_stats(target)
        if st["persons"] == N_100:
            print(f"[1/3] 已存在且 persons={st['persons']:,} -> 复用")
            return {"stage": "6.2B_population", "reused": True, "path": str(target), **st}
    mod = load_module(SCRIPTS_OD / "build_matsim_population_6_2b.py", "b6_2b_sample")
    mod.OUT = Path("reports/matsim_population_6_2b_s100k")   # ★ 新目录，不覆盖冻结件
    print(f"[1/3] 6.2B --target-agents {N_100:,} -> {POP_100_DIR}")
    run_with_argv(mod.main, [
        "build_matsim_population_6_2b.py",
        "--project-root", str(ROOT),
        "--lambdas", f"{LAMBDA_FIXED}",
        "--target-agents", str(N_100),
        "--seed", str(FROZEN_SEED),
    ])
    st = population_stats(target)
    return {"stage": "6.2B_population", "reused": False, "path": str(target), **st}


def stage2_connected(force: bool) -> dict:
    target = POP_100_CONN_DIR / f"population_lambda_{LAMBDA_TAG}.xml.gz"
    if target.exists() and not force:
        st = population_stats(target)
        if st["persons"] == N_100:
            print(f"[2/3] 已存在且 persons={st['persons']:,} -> 复用")
            return {"stage": "connectivity_repair", "reused": True, "path": str(target), **st}
    mod = load_module(SCRIPTS_MAT / "prepare_connected_scenario.py", "pc_sample")
    net_dir = ROOT / "reports" / "matsim_network"
    cleaned = net_dir / "network_cleaned.xml.gz"
    if not cleaned.exists():
        raise FileNotFoundError(f"缺少冻结清洗网络 {cleaned}（不得重算，保持冻结）")
    mod.POP_IN = POP_100_DIR                              # ★ 只改输入/输出目录
    mod.POP_OUT = POP_100_CONN_DIR
    print(f"[2/3] 连通性修复 -> {POP_100_CONN_DIR}（复用冻结 {cleaned.name}）")
    c_links, c_nodes = mod.read_network(cleaned)
    o_links, o_nodes = mod.read_network(net_dir / "network.xml.gz")
    stats = mod.repair_population(LAMBDA_TAG, c_links, c_nodes, o_links, o_nodes)
    st = population_stats(target)
    return {"stage": "connectivity_repair", "reused": False, "path": str(target),
            "repair": stats, **st}


def stage3_departure(force: bool) -> dict:
    target = DEP_100_DIR / f"population_lambda_{LAMBDA_TAG}.xml.gz"
    if target.exists() and not force:
        st = population_stats(target)
        if st["persons"] == N_100:
            print(f"[3/3] 已存在且 persons={st['persons']:,} -> 复用")
            return {"stage": "departure_profile", "reused": True, "path": str(target), **st}
    mod = load_module(SCRIPTS_OD / "build_departure_profile_6_3_3a.py", "dep_sample")
    mod.POP_DIR = POP_100_CONN_DIR                       # ★ 只改输入/输出目录
    mod.FALLBACK_POP_DIR = ROOT / "__nonexistent__"
    mod.OUT = DEP_100_DIR
    print(f"[3/3] 出发时刻剖面 -> {DEP_100_DIR}")
    run_with_argv(mod.main, [
        "build_departure_profile_6_3_3a.py",
        "--project-root", str(ROOT),
        "--lambdas", f"{LAMBDA_FIXED}",
        "--seed", str(FROZEN_SEED),
    ])
    st = population_stats(target)
    summary_csv = DEP_100_DIR / "departure_assignment_summary.csv"
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
            "sample_agents": N_REF,
            "f_demand": 1.00,
            "f_cap": 1.00,
            "scale": round(scale_for(N_REF), 5),
            "population_dir": "reports/matsim_departure_6_3_3a",
            "output_dir": "reports/od_calibration_7_4_2/E06_lam0p075_cap1p00",
            "mode": "REUSE_E06",
            "note": "= D01/E06（λ=0.075, cap=1.00, 20 it）；不重跑",
        },
        {
            "experiment_id": "S100",
            "role": "calibration_sample_100k",
            "sample_agents": N_100,
            "f_demand": 1.00,
            "f_cap": 1.00,
            "scale": round(scale_for(N_100), 5),
            "population_dir": "reports/matsim_departure_6_3_3a_s100k",
            "output_dir": "reports/od_sample_7_5a/S100_lam0p075_cap1p00",
            "mode": "RUN",
            "note": "用户指定字面设计：同容量(1.00)下减样本",
        },
        {
            "experiment_id": "S100c",
            "role": "sample_consistent_100k",
            "sample_agents": N_100,
            "f_demand": 1.00,
            "f_cap": 0.50,
            "scale": round(scale_for(N_100), 5),
            "population_dir": "reports/matsim_departure_6_3_3a_s100k",
            "output_dir": "reports/od_sample_7_5a/S100c_lam0p075_cap0p50",
            "mode": "RUN_OPTIONAL",
            "note": "采样一致对照：f_cap = N_sample/N_ref = 0.50，保持同一物理场景",
        },
    ]


def write_matrix(path: Path) -> None:
    rows = matrix_rows()
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)


def write_design(path: Path, build: dict | None) -> None:
    L = []
    L.append("# Step 7.5A（二）— 固定样本量 + 可变需求权重（采样—扩样架构）\n")
    L.append("**零仿真**。本文件是 7.5A 的设计单一事实源：确定「样本率—扩样系数」解耦方案，"
             "并给出 100k 人口的构建与校验。\n")
    L.append("## 1. 为什么不靠降低道路容量省时间\n")
    L.append("`flowCapacityFactor` 是**供给物理参数**，不是性能旋钮：\n")
    L.append("- Phase 1 已证 `capacity 0.50→0.75→1.00` 显著改变 CATA/SLIP 结构（其结构影响大于 λ）；")
    L.append("- Phase 2 / 7.4.3 又证需求变化本身也改变结构；")
    L.append("- 7.4.3 的 D 系列已出现非单调（峰 @f=1.20），此时再动 capacity 将无法归因。\n")
    L.append("→ **capacity 继续作为物理参数冻结（=1.00），不作计算性能旋钮。**\n")
    L.append("## 2. 真正可调的是「样本率」，它与需求量原则上可解耦\n")
    L.append("7.5A 审计（见 `STEP7_5A_DEMAND_CHAIN_AUDIT.md`）已确证：\n")
    L.append("```text")
    L.append("MATSim QSim 只消费 person/vehicle 数（agents）")
    L.append("expansionFactor / odTrips：仅人口 XML 自定义属性，MATSim 自身 class 零命中 -> 不消费")
    L.append("=> linkstats 原始口径 ~ 线性于 agent 数")
    L.append("=> 扩样权重必须在评价层施加：SCALE = ΣT / N_sample")
    L.append("```\n")
    L.append("## 3. 三层需求（论文口径）\n")
    L.append("| 层 | 量 | 符号 | λ=0.075 基准值 | 决定什么 |")
    L.append("|---|---|---|---:|---|")
    L.append(f"| 1 | 真实需求 | `ΣT` | {REAL_CAR_OD_TOTAL:,.0f} | 现实机动车 OD 总量（与 N 无关） |")
    L.append(f"| 2 | 采样率 | `N_sample` | 200,000 / **100,000** | **只决定计算量** |")
    L.append(f"| 3 | 有效需求权重 | `SCALE = ΣT/N_sample` | 2.29897 / **{scale_for(N_100):.5f}** | 把链接车数换算成现实车次 |")
    L.append("")
    L.append("## 4. ★硬约束：N_sample 下限 = 正 OD cell 数\n")
    L.append(f"- λ=0.075 的**正 OD cell 数 = {POSITIVE_OD_CELLS:,}**"
             "（6.2B `allocate_cells` 要求每个正 cell ≥1 agent）。")
    L.append(f"- 因此 `target_agents ≥ {POSITIVE_OD_CELLS:,}`；"
             "**50k 会直接 `ValueError`（不可行）**；100k 是可行且推荐的最低标定档。")
    L.append(f"- 均值 EF @100k = ΣT/100k = {scale_for(N_100):.5f}（@200k = {scale_for(N_REF):.5f}）。\n")
    L.append("## 5. ★容量与采样率的耦合（本步最需要你裁定的点）\n")
    L.append("若 N_sample 从 200k 降到 100k 而 **f_cap 固定 1.00**，则车密度减半 → "
             "**每车经历的供给饱和度被改变** → S100 与 S200 的差异混杂了"
             "「采样效应」与「供给/需求比效应」，无法判定 100k 是否为可替代样本。\n")
    L.append("要保持**同一物理交通场景**，`flowCapacityFactor` 必须随采样率同比缩放：\n")
    L.append("| 变体 | N_sample | f_cap | 物理含义 |")
    L.append("|---|---:|---:|---|")
    L.append("| S200（=D01/E06） | 200,000 | 1.00 | 参考场景 |")
    L.append("| S100 | 100,000 | **1.00** | 用户指定：同容量减样本（供给/需求比改变） |")
    L.append("| S100c | 100,000 | **0.50** | 采样一致：f_cap = N/200k，**保持同一物理场景** |")
    L.append("")
    L.append("> 判定逻辑：若 `S100c×SCALE ≈ S200×SCALE` 而 `S100×SCALE` 明显偏离，"
             "则可同时得到两个结论——（a）100k 是可替代样本；（b）"
             "**一旦改变采样率，capacity 就不能再独立冻结 1.00**（这是采样一致性的数学要求，"
             "不是把 capacity 当性能旋钮）。\n")
    L.append("## 6. 实验矩阵\n")
    L.append("| 实验 | 角色 | N_sample | f_cap | SCALE | 模式 |")
    L.append("|---|---|---:|---:|---:|---|")
    for r in matrix_rows():
        L.append(f"| **{r['experiment_id']}** | {r['role']} | {r['sample_agents']:,} | "
                 f"{r['f_cap']:.2f} | {r['scale']:.5f} | `{r['mode']}` |")
    L.append("")
    L.append("## 7. 100k 人口管线（本脚本执行，全部写入新目录）\n")
    L.append("| 阶段 | 脚本（冻结件，仅 patch 目录常量） | 输出 |")
    L.append("|---|---|---|")
    L.append("| 1 | `build_matsim_population_6_2b.py --target-agents 100000` | `reports/matsim_population_6_2b_s100k/` |")
    L.append("| 2 | `prepare_connected_scenario.py`（复用冻结 `network_cleaned.xml.gz`） | `reports/matsim_population_6_2b_connected_s100k/` |")
    L.append("| 3 | `build_departure_profile_6_3_3a.py` | `reports/matsim_departure_6_3_3a_s100k/` |")
    L.append("")
    L.append("> **不覆盖**冻结 200k 三阶段产物（`matsim_population_6_2b` / `..._connected` / "
             "`matsim_departure_6_3_3a`）；只 monkeypatch 目录常量，构建逻辑与守恒校验逐字节复用。\n")
    if build:
        L.append("## 8. 本次构建校验\n")
        L.append("| 阶段 | persons | ΣEF | ΣodTrips | 复用 |")
        L.append("|---|---:|---:|---:|---|")
        for st in build.get("stages", []):
            L.append(f"| {st['stage']} | {st.get('persons'):,} | "
                     f"{st.get('sum_expansion_factor'):,.1f} | "
                     f"{st.get('sum_od_trips'):,.1f} | {st.get('reused')} |")
        L.append("")
        ok = build.get("status") == "PASS"
        L.append(f"**构建状态：{'PASS' if ok else 'FAIL'}**"
                 f"（判据：persons == {N_100:,} 且 ΣEF == {REAL_CAR_OD_TOTAL:,.0f}）\n")
    L.append("## 9. 已识别但本步不做的\n")
    L.append("- 不继续 7.4.3 的 f=1.15/1.20/1.25 细扫；不动 capacity（除 S100c 的采样一致对照）。")
    L.append("- λ 仍不冻结（本轮所有实验固定 λ=0.075 仅为控制变量）。")
    L.append("- 50k 探索档当前**不可行**（< 正 OD cell 数 71,136）。\n")
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
    write_matrix(OUT / "sample_matrix.csv")
    print(f"matrix -> {OUT / 'sample_matrix.csv'}")

    build = None
    if not args.design_only:
        stages = []
        stages.append(stage1_population(args.force))
        stages.append(stage2_connected(args.force))
        stages.append(stage3_departure(args.force))
        ok = all(s.get("persons") == N_100
                 and abs(s.get("sum_expansion_factor", 0) - REAL_CAR_OD_TOTAL) < 1e-3
                 for s in stages)
        build = {
            "step": "7.5A",
            "status": "PASS" if ok else "FAIL",
            "lambda_fixed": LAMBDA_FIXED,
            "n_sample": N_100,
            "real_car_od_total": REAL_CAR_OD_TOTAL,
            "scale_200k": round(scale_for(N_REF), 5),
            "scale_100k": round(scale_for(N_100), 5),
            "positive_od_cells": POSITIVE_OD_CELLS,
            "min_feasible_sample": POSITIVE_OD_CELLS,
            "stages": stages,
            "frozen_artifacts_untouched": [
                "reports/matsim_population_6_2b",
                "reports/matsim_population_6_2b_connected",
                "reports/matsim_departure_6_3_3a",
            ],
        }
        (OUT / "sample_build_summary.json").write_text(
            json.dumps(build, ensure_ascii=False, indent=2), encoding="utf-8")

    write_design(OUT / "STEP7_5A_DESIGN.md", build)
    print(f"design -> {OUT / 'STEP7_5A_DESIGN.md'}")
    if build:
        print("BUILD STATUS:", build["status"])
        for s in build["stages"]:
            print(f"  {s['stage']:22s} persons={s.get('persons'):>8,} "
                  f"ΣEF={s.get('sum_expansion_factor'):>12,.1f} reused={s.get('reused')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
