#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""
prepare_routechoice_7_6d_s.py — Step 7.6D-S：低样本（100k）**稳定性筛查**。

用户 2026-09-16 22:16 裁定
--------------------------
不做 50k 作为「正式实验」，而做**更便宜、更有辨识力的机制筛查**：

    保持 7.6D 已通过验证的最小 route-choice 修复不变：
        fractionOfIterationsToDisableInnovation = 0.8
        learningRate                            = 0.5
        ReRoute                                 = 0.15
        ChangeExpBeta                           = 0.85
        routingRandomness                       = 0.0
    只把人口缩到低样本档，并保持 f_cap = N / 200,000（采样一致性）。

★2026-09-16 22:xx 关键修正：原定 N = 50,000 **数学上不可行**。
    6.2B 的 FLOOR_PLUS_1 保底规则要求「每个正 OD cell 至少 1 个 agent」，
    而正 OD cell 数恒为 **71,136**（= Σtrips 459,794 的全部非空格）
        ValueError: agents 50000 < positive OD cells 71136
    ⇒ 用户改选 **N = 100,000, f_cap = 0.50**，并**复用 S100c 已冻结的 100k 人口**
      （`reports/matsim_departure_6_3_3a_s100k/`），额外获得一个
      **「同 N、仅 route-choice 不同」的严格对照**（S100c 已有完整 20 迭代 linkstats）。

    **不评价 demand scale、不评价 λ、不评价 OD 空间结构。**

预注册判据（先于运行冻结）
--------------------------
    MATCHED  A_10:19 < 3%
    CATA     A_10:19 < 3%
    SLIP     A_10:19 < 5%
    + 保留 parity_gap_rel 作为**周期结构辅助诊断**（不是稳定性判据）

    PASS → 再做 200k × 20 it 正式稳定化
    FAIL → 暂停，不消耗 200k 算力，继续修 route-choice

统计量纪律（用户明确要求保持区分）
--------------------------------
    A_10:19        = (max(Q_k) − min(Q_k)) / Q̄_10:19   ← **正式稳定性判据**
    parity_gap_rel = |even_mean − odd_mean| / mean      ← **周期结构诊断**
两者**不得**再统称为「周期振幅」。

隔离原则
--------
新增人口三阶段全部落在**新目录**（`*_s50_76ds`），不覆盖任何冻结件；
新 config / outputs / logs / audit 全部落在既有 `matsim_routechoice_7_6d/` 内。

用法
----
    python scripts/od/prepare_routechoice_7_6d_s.py              # 建人口 + 生成 config + 验证 + 写预注册
    python scripts/od/prepare_routechoice_7_6d_s.py --smoke 2000 # 冒烟（2000 agents × 3 it）
    python scripts/od/prepare_routechoice_7_6d_s.py --run        # 正式筛查 50k × 20 it
"""
from __future__ import annotations

import argparse
import csv
import gzip
import importlib.util
import json
import re
import sys
import time
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path

ROOT = Path(r"D:\Luan\2026-05\2_Singapore")
SCRIPTS_OD = ROOT / "scripts" / "od"
SCRIPTS_MAT = ROOT / "scripts" / "matsim"
sys.path.insert(0, str(SCRIPTS_MAT))
sys.path.insert(0, str(SCRIPTS_OD))

import make_config_6_3 as cfgmod      # noqa: E402
import matsim_env                     # noqa: E402

# --------------------------------------------------------------------------
# 冻结常量
# --------------------------------------------------------------------------
S_ROOT = ROOT / "matsim_routechoice_7_6d"
CONFIG_DIR = S_ROOT / "configs"
OUT_ROOT = S_ROOT / "outputs"
LOG_DIR = S_ROOT / "logs"
AUDIT_DIR = S_ROOT / "audit"

N_REF = 200_000
N_SCREEN = 100_000
F_CAP = N_SCREEN / N_REF              # = 0.50（采样一致性校正，非交通供给标定参数）

# ★ FLOOR_PLUS_1 的硬下界：正 OD cell 数（= Σtrips 459,794 的非空格）
FLOOR_MIN_CELLS = 71_136
assert N_SCREEN >= FLOOR_MIN_CELLS, (
    f"N_SCREEN={N_SCREEN:,} < FLOOR_PLUS_1 下界 {FLOOR_MIN_CELLS:,}"
    "（每正 OD cell 至少 1 agent）")

# 「修复前」同 N 对照：S100c（100k, f_cap=0.50, 旧 route-choice, 20 迭代已在盘）
SCREEN_BEFORE = {
    "label": "REF_S100c_N100k",
    "role": "before_s100k",
    "out_dir": ROOT / "reports" / "od_sample_7_5a" / "S100c_lam0p075_cap0p50",
    "run_id": "S100c",
    "desc": "7.5A S100c（N=100k, f_cap=0.50, FLOOR_PLUS_1, 旧 route-choice: ReRoute 1.0 / innovation=Infinity / lr=1.0）",
}

LAMBDA_TAG = "0p075"
LAMBDA_FIXED = 0.075
FROZEN_SEED = 20260912

POP_S_DIR = ROOT / "reports" / "matsim_population_6_2b_s100k"          # S100c 冻结人口
POP_S_CONN_DIR = ROOT / "reports" / "matsim_population_6_2b_connected_s100k"
DEP_S_DIR = ROOT / "reports" / "matsim_departure_6_3_3a_s100k"
POP_FILE = DEP_S_DIR / f"population_lambda_{LAMBDA_TAG}.xml.gz"

BASELINE_CFG = ROOT / "matsim" / "step6_3" / "config_E06_lam0p075_cap1p00.xml"   # = D01 基线

RUN_ID = "S100k_rc_min"
RUN_DIR = OUT_ROOT / RUN_ID
TOTAL_ITER = 20
EXPECTED_ITER = 19

DOCT_TMPL = ('<?xml version="1.0" encoding="UTF-8"?>\n'
             '<!DOCTYPE config SYSTEM "http://www.matsim.org/files/dtd/config_v2.dtd">\n')

# --------------------------------------------------------------------------
# 最小修复（与 7.6D 完全一致 —— 本轮唯一新增变量是「人口 50k + f_cap 0.25」）
# --------------------------------------------------------------------------
MIN_PATCH = {
    ("replanning", "fractionOfIterationsToDisableInnovation"): ("Infinity", "0.8"),
    ("scoring", "learningRate"): ("1.0", "0.5"),
    ("routing", "routingRandomness"): ("0.0", "0.0"),
}
STRATEGY_SPEC = [("ReRoute", 0.15), ("ChangeExpBeta", 0.85)]

# 采样一致性校正（与 S100c 同构：只动 qsim 两项；hermes 保持 1.0 不动）
F_CAP_PATCH = {
    ("qsim", "flowCapacityFactor"): ("1", f"{F_CAP:g}"),
    ("qsim", "storageCapacityFactor"): ("1", f"{F_CAP:g}"),
}

CONTROLLER_ALLOWED = {
    "outputDirectory", "runId", "firstIteration", "lastIteration",
    "writeEventsInterval", "writePlansInterval", "writeTripsInterval",
    "writeSnapshotsInterval", "writeLinkStatsInterval",
}

# 需求文件是**合法差异**（换用 50k 人口），不列入必须一致项
PLANS_ALLOWED = {("plans", "inputPlansFile")}

# 必需与基线逐值相同的关键项（排除合法差异项）
MUST_MATCH_BASELINE = [
    ("network", "inputNetworkFile"),
    ("global", "randomSeed"),
    ("global", "coordinateSystem"),
    ("global", "numberOfThreads"),
    ("qsim", "numberOfThreads"),
    ("controller", "routingAlgorithmType"),
    ("travelTimeCalculator", "travelTimeBinSize"),
    ("travelTimeCalculator", "travelTimeAggregator"),
    ("linkStats", "averageLinkStatsOverIterations"),
    ("linkStats", "writeLinkStatsInterval"),
    ("plans", "networkRouteType"),
    ("hermes", "flowCapacityFactor"),
    ("hermes", "storageCapacityFactor"),
]

# 预注册阈值（7.6D-S，按口径分别固定）
TH_SCREEN = {"MATCHED": 0.030, "CATA": 0.030, "SLIP": 0.050}

# 冻结件（阶段前后 mtime 必须不变）
FROZEN_WATCH = [
    ROOT / "reports" / "matsim_departure_6_3_3a" / "population_lambda_0p075.xml.gz",
    ROOT / "reports" / "matsim_population_6_2b" / "population_lambda_0p075.xml.gz",
    ROOT / "reports" / "matsim_population_6_2b_connected" / "population_lambda_0p075.xml.gz",
    ROOT / "reports" / "matsim_network" / "network_cleaned.xml.gz",
    ROOT / "reports" / "matsim_network" / "network.xml.gz",
    BASELINE_CFG,
    ROOT / "matsim" / "step6_3" / "config_S100c_lam0p075_cap0p50.xml",
    ROOT / "matsim" / "step6_3" / "config_S100r_lam0p075_cap0p50.xml",
    ROOT / "reports" / "od_final_calibration_crosswalk_7_3_6" / "final_calibration_crosswalk.csv",
]

_ck_rows: list[dict] = []


def ck(name: str, ok: bool, detail: str = "") -> bool:
    _ck_rows.append({"check": name, "pass": bool(ok), "detail": str(detail)})
    print(f"   [{'PASS' if ok else 'FAIL'}] {name}  {detail}")
    return bool(ok)


# --------------------------------------------------------------------------
# XML / 通用工具
# --------------------------------------------------------------------------
def module_of(root: ET.Element, name: str) -> ET.Element:
    for m in root.findall("module"):
        if m.get("name") == name:
            return m
    raise KeyError(f"module not found: {name}")


def setp(mod_el: ET.Element, name: str, value: str) -> None:
    for p in mod_el.findall("param"):
        if p.get("name") == name:
            p.set("value", value)
            return
    ET.SubElement(mod_el, "param", {"name": name, "value": value})


def pget(root: ET.Element, mod: str, name: str):
    try:
        m = module_of(root, mod)
    except KeyError:
        return None
    return next((p.get("value") for p in m.findall("param") if p.get("name") == name), None)


def same_value(a, b) -> bool:
    """字符串相等或**数值相等**（基线写 "1"、builder 写 "1.0" 视为相同）。"""
    if str(a) == str(b):
        return True
    try:
        return abs(float(a) - float(b)) < 1e-12
    except (TypeError, ValueError):
        return False


def param_map(cfg: Path) -> dict:
    root = ET.parse(cfg).getroot()
    out = {}
    for m in root.findall("module"):
        mod = m.get("name")
        for p in m.findall("param"):
            out[(mod, p.get("name"))] = p.get("value")
    return out


def strategy_list(cfg: Path) -> list[tuple[str, str]]:
    root = ET.parse(cfg).getroot()
    r = module_of(root, "replanning")
    out = []
    for ps in r.findall("parameterset"):
        if ps.get("type") != "strategysettings":
            continue
        nm = next((p.get("value") for p in ps.findall("param")
                   if p.get("name") == "strategyName"), None)
        wt = next((p.get("value") for p in ps.findall("param")
                   if p.get("name") == "weight"), None)
        if nm:
            out.append((nm, wt))
    return out


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
    with gzip.open(xml_path, "rt", encoding="utf-8", errors="replace") as fh:
        for line in fh:
            if line.lstrip().startswith("<person "):
                n += 1
            m = re.search(r'name="expansionFactor" class="java.lang.Double">([0-9eE\.\-\+]+)<', line)
            if m:
                s_ef += float(m.group(1))
    return {"persons": n, "sum_expansion_factor": s_ef,
            "mean_ef": (s_ef / n) if n else None}


def snapshot_mtimes(paths: list[Path]) -> dict:
    return {str(p): (p.stat().st_mtime if p.exists() else None) for p in paths}


# --------------------------------------------------------------------------
# 阶段 1-3：50k 人口管线（FLOOR_PLUS_1 保底规则**保持不动**）
# --------------------------------------------------------------------------
def stage1_population(force: bool) -> dict:
    target = POP_S_DIR / f"population_lambda_{LAMBDA_TAG}.xml.gz"
    if target.exists() and not force:
        st = population_stats(target)
        if st["persons"] == N_SCREEN:
            print(f"[1/3] 已存在且 persons={st['persons']:,} -> 复用")
            return {"reused": True, "path": str(target), **st}
    mod = load_module(SCRIPTS_OD / "build_matsim_population_6_2b.py", "b6_2b_s50_76ds")
    mod.OUT = Path("reports/matsim_population_6_2b_s100k")   # ★ 复用 S100c 冻结目录
    # ★ 不替换 allocate_cells —— 保持 6.2B 原生的 FLOOR_PLUS_1 保底规则（与 200k 基准同规则）
    print(f"[1/3] 6.2B(FLOOR_PLUS_1) --target-agents {N_SCREEN:,} -> {POP_S_DIR}")
    run_with_argv(mod.main, [
        "build_matsim_population_6_2b.py",
        "--project-root", str(ROOT),
        "--lambdas", f"{LAMBDA_FIXED}",
        "--target-agents", str(N_SCREEN),
        "--seed", str(FROZEN_SEED),
    ])
    st = population_stats(target)
    cons = POP_S_DIR / f"od_cell_conservation_lambda_{LAMBDA_TAG}.csv"
    cell = None
    if cons.exists():
        import pandas as pd
        c = pd.read_csv(cons, encoding="utf-8-sig")
        cell = {"positive_od_cells": int(len(c)),
                "sampled_od_cells": int((c.agent_count > 0).sum()),
                "zero_sampled_od_cells": int((c.agent_count == 0).sum()),
                "od_coverage": float((c.agent_count > 0).mean()),
                "sum_trips": float(c.trips.sum()),
                "max_abs_error": float(c.abs_error.max()),
                "agent_min": int(c.agent_count.min()),
                "agent_median": float(c.agent_count.median()),
                "agent_max": int(c.agent_count.max())}
    return {"reused": False, "path": str(target), "sampling_rule": "FLOOR_PLUS_1",
            "cell_stats": cell, **st}


def stage2_connected(force: bool) -> dict:
    target = POP_S_CONN_DIR / f"population_lambda_{LAMBDA_TAG}.xml.gz"
    if target.exists() and not force:
        st = population_stats(target)
        if st["persons"] == N_SCREEN:
            print(f"[2/3] 已存在且 persons={st['persons']:,} -> 复用")
            return {"reused": True, "path": str(target), **st}
    mod = load_module(SCRIPTS_MAT / "prepare_connected_scenario.py", "pc_s50_76ds")
    net_dir = ROOT / "reports" / "matsim_network"
    cleaned = net_dir / "network_cleaned.xml.gz"
    if not cleaned.exists():
        raise FileNotFoundError(f"缺少冻结清洗网络 {cleaned}（不得重算）")
    mod.POP_IN = POP_S_DIR
    mod.POP_OUT = POP_S_CONN_DIR
    print(f"[2/3] 连通性修复 -> {POP_S_CONN_DIR}（复用冻结 {cleaned.name}）")
    c_links, c_nodes = mod.read_network(cleaned)
    o_links, o_nodes = mod.read_network(net_dir / "network.xml.gz")
    stats = mod.repair_population(LAMBDA_TAG, c_links, c_nodes, o_links, o_nodes)
    st = population_stats(target)
    return {"reused": False, "path": str(target), "repair": stats, **st}


def stage3_departure(force: bool) -> dict:
    target = DEP_S_DIR / f"population_lambda_{LAMBDA_TAG}.xml.gz"
    if target.exists() and not force:
        st = population_stats(target)
        if st["persons"] == N_SCREEN:
            print(f"[3/3] 已存在且 persons={st['persons']:,} -> 复用")
            return {"reused": True, "path": str(target), **st}
    mod = load_module(SCRIPTS_OD / "build_departure_profile_6_3_3a.py", "dep_s50_76ds")
    mod.POP_DIR = POP_S_CONN_DIR
    mod.FALLBACK_POP_DIR = ROOT / "__nonexistent__"
    mod.OUT = DEP_S_DIR
    print(f"[3/3] 出发时刻剖面 -> {DEP_S_DIR}")
    run_with_argv(mod.main, [
        "build_departure_profile_6_3_3a.py",
        "--project-root", str(ROOT),
        "--lambdas", f"{LAMBDA_FIXED}",
        "--seed", str(FROZEN_SEED),
    ])
    st = population_stats(target)
    summary_csv = DEP_S_DIR / "departure_assignment_summary.csv"
    dep = None
    if summary_csv.exists():
        with open(summary_csv, encoding="utf-8-sig", newline="") as f:
            rows = list(csv.DictReader(f))
            dep = rows[0] if rows else None
    return {"reused": False, "path": str(target), "departure_summary": dep, **st}


# --------------------------------------------------------------------------
# 阶段 4：config 生成（最小修复 + f_cap=0.25）
# --------------------------------------------------------------------------
def apply_patch_76ds(cfg_path: Path, *, out_dir: Path, run_id: str, last_iter: int) -> None:
    tree = ET.parse(cfg_path)
    root = tree.getroot()

    c = module_of(root, "controller")
    setp(c, "outputDirectory", str(out_dir))
    setp(c, "runId", run_id)
    setp(c, "firstIteration", "0")
    setp(c, "lastIteration", str(last_iter))
    for k in ("writeEventsInterval", "writePlansInterval",
              "writeTripsInterval", "writeSnapshotsInterval"):
        setp(c, k, "0")

    # ★ 修复 1：innovation 收尾
    r = module_of(root, "replanning")
    setp(r, "fractionOfIterationsToDisableInnovation", MIN_PATCH[
        ("replanning", "fractionOfIterationsToDisableInnovation")][1])

    # ★ 修复 2：策略集
    for ps in list(r.findall("parameterset")):
        if ps.get("type") == "strategysettings":
            r.remove(ps)
    for nm, wt in STRATEGY_SPEC:
        ss = ET.SubElement(r, "parameterset", {"type": "strategysettings"})
        ET.SubElement(ss, "param", {"name": "strategyName", "value": nm})
        ET.SubElement(ss, "param", {"name": "weight", "value": f"{wt:g}"})

    # ★ 修复 3：学习率
    setp(module_of(root, "scoring"), "learningRate", MIN_PATCH[("scoring", "learningRate")][1])

    # 保留确定性最短路
    setp(module_of(root, "routing"), "routingRandomness", "0.0")

    # ★ 采样一致性：qsim capacity = N/200k = 0.25（hermes 保持 1.0，与 S100c 同构）
    q = module_of(root, "qsim")
    setp(q, "flowCapacityFactor", f"{F_CAP:g}")
    setp(q, "storageCapacityFactor", f"{F_CAP:g}")

    cfg_path.write_text(DOCT_TMPL + ET.tostring(root, encoding="unicode") + "\n",
                        encoding="utf-8")


def truncate_population(src: Path, dst: Path, n: int) -> int:
    buf, cnt, done = [], 0, False
    with gzip.open(src, "rt", encoding="utf-8") as fh:
        for line in fh:
            if not done:
                buf.append(line)
                if line.strip().startswith("</person>"):
                    cnt += 1
                    if cnt >= n:
                        done = True
    buf.append("</population>\n")
    with gzip.open(dst, "wt", encoding="utf-8") as fh:
        fh.write("".join(buf))
    return cnt


def build(*, smoke: int = 0) -> tuple[Path, Path, dict]:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    OUT_ROOT.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    if not POP_FILE.exists():
        raise FileNotFoundError(POP_FILE)

    if smoke:
        cfg_path = CONFIG_DIR / f"config_{RUN_ID}_smoke.xml"
        out_dir = OUT_ROOT / f"_smoke_{RUN_ID}"
        run_id = f"smoke_{RUN_ID}"
        last_iter = 2
    else:
        cfg_path = CONFIG_DIR / f"config_{RUN_ID}.xml"
        out_dir = RUN_DIR
        run_id = RUN_ID
        last_iter = EXPECTED_ITER

    cfgmod.build_one(LAMBDA_TAG, pop_dir=DEP_S_DIR, out_root=OUT_ROOT,
                     run_prefix="rc7_6ds_", cfg_path=cfg_path)
    apply_patch_76ds(cfg_path, out_dir=out_dir, run_id=run_id, last_iter=last_iter)

    if smoke:
        pop_dst = CONFIG_DIR / f"_smoke_{RUN_ID}_population.xml.gz"
        got = truncate_population(POP_FILE, pop_dst, smoke)
        print(f"[smoke] 截断人口 {got} persons -> {pop_dst}")
        tree = ET.parse(cfg_path)
        root = tree.getroot()
        setp(module_of(root, "plans"), "inputPlansFile", str(pop_dst.resolve()))
        cfg_path.write_text(DOCT_TMPL + ET.tostring(root, encoding="unicode") + "\n",
                            encoding="utf-8")

    return cfg_path, out_dir, {"run_id": run_id, "out_dir": str(out_dir),
                               "last_iteration": last_iter, "smoke": smoke}


# --------------------------------------------------------------------------
# 阶段 5：配置验证（零仿真）
# --------------------------------------------------------------------------
def validate(cfg_path: Path, *, expect_iter: int, smoke: int) -> list[dict]:
    base = param_map(BASELINE_CFG)
    new = param_map(cfg_path)
    bstrat, nstrat = strategy_list(BASELINE_CFG), strategy_list(cfg_path)

    print("\n=== 基线策略集 ===")
    print("   ", bstrat)
    print("=== 7.6D-S 策略集 ===")
    print("   ", nstrat)

    # V1 策略集
    ck("V1.1 策略集 == [ReRoute 0.15, ChangeExpBeta 0.85]（与 7.6D 完全一致）",
       [(n, float(w)) for n, w in nstrat] == list(STRATEGY_SPEC), str(nstrat))
    ck("V1.2 策略权重和 == 1.0",
       abs(sum(float(w) for _n, w in nstrat) - 1.0) < 1e-12,
       f"sum = {sum(float(w) for _n, w in nstrat):.4f}")
    ck("V1.3 基线无任何 plan-selection 策略",
       "ChangeExpBeta" not in dict(bstrat) and "BestScore" not in dict(bstrat),
       f"baseline = {list(dict(bstrat))}")

    # V2 目标值
    root_new = ET.parse(cfg_path).getroot()
    for (mod, name), (_old, newv) in MIN_PATCH.items():
        got = pget(root_new, mod, name)
        ck(f"V2 {mod}.{name} == {newv}", got == newv, f"baseline={_old} new={got}")
    for (mod, name), (old, newv) in F_CAP_PATCH.items():
        got = pget(root_new, mod, name)
        ck(f"V2-S {mod}.{name} == {newv}（采样一致性 N/200k）",
           same_value(got, newv), f"baseline={old} new={got}")
    ck(f"V2-S 采样一致性关系成立：{N_SCREEN:,} / {N_REF:,} = {F_CAP:g}",
       abs(F_CAP - N_SCREEN / N_REF) < 1e-15, f"f_cap = {F_CAP:g}")
    ck("V2-S hermes capacity 未被缩放（保持 1.0，与 S100c 同构）",
       same_value(pget(root_new, "hermes", "flowCapacityFactor"), base.get(("hermes", "flowCapacityFactor")))
       and same_value(pget(root_new, "hermes", "storageCapacityFactor"), base.get(("hermes", "storageCapacityFactor"))),
       f"{pget(root_new, 'hermes', 'flowCapacityFactor')} / {pget(root_new, 'hermes', 'storageCapacityFactor')}")

    # V3 diff 白名单
    keys = set(base) | set(new)
    diffs = [(k, base.get(k), new.get(k)) for k in sorted(keys)
             if not same_value(base.get(k), new.get(k))]

    def _is_allowed(k):
        mod, name = k
        if mod == "controller" and name in CONTROLLER_ALLOWED:
            return True
        if k in MIN_PATCH or k in F_CAP_PATCH:
            return True
        if k in PLANS_ALLOWED:
            return True
        if smoke > 0 and k == ("plans", "inputPlansFile"):
            return True
        return False

    unexpected = [d for d in diffs if not _is_allowed(d[0])]
    ck("V3.1 与基线差异仅限白名单（controller 路径/迭代 + 3 修复标量 + qsim capacity + 人口文件）",
       not unexpected,
       f"共 {len(diffs)} 处差异，越界 {len(unexpected)}" +
       (f" -> {unexpected}" if unexpected else ""))
    print("   -- 白名单内差异明细 --")
    for k, a, b in sorted(diffs):
        print(f"      {k[0]}.{k[1]}: {a} -> {b}")

    # V4 模型关键项逐值不变
    bad = []
    for mod, name in MUST_MATCH_BASELINE:
        bv, nv = base.get((mod, name)), new.get((mod, name))
        if not same_value(bv, nv):
            bad.append((mod, name, bv, nv))
    ck(f"V4 模型关键项与基线逐值相同（{len(MUST_MATCH_BASELINE)} 项）",
       not bad, "全部一致" if not bad else str(bad))

    # V5 显式冻结
    ck("V5.1 routingRandomness == 0.0",
       pget(root_new, "routing", "routingRandomness") == "0.0",
       pget(root_new, "routing", "routingRandomness"))
    ck("V5.2 randomSeed == 4711", pget(root_new, "global", "randomSeed") == "4711",
       pget(root_new, "global", "randomSeed"))
    ck(f"V5.3 lastIteration == {expect_iter}",
       pget(root_new, "controller", "lastIteration") == str(expect_iter),
       pget(root_new, "controller", "lastIteration"))
    ck("V5.4 inputNetworkFile 与基线相同",
       pget(root_new, "network", "inputNetworkFile") == base.get(("network", "inputNetworkFile")),
       pget(root_new, "network", "inputNetworkFile"))
    got_pop = pget(root_new, "plans", "inputPlansFile")
    ck("V5.5 population 指向 100k 6.3.3A 剖面（smoke 除外）",
       (smoke > 0) or (got_pop == str(POP_FILE)), str(got_pop))
    ck("V5.6 中间迭代不写 events/plans/trips/snapshots",
       all(pget(root_new, "controller", k) == "0" for k in
           ("writeEventsInterval", "writePlansInterval",
            "writeTripsInterval", "writeSnapshotsInterval")), "all 0")
    ck("V5.7 writeLinkStatsInterval == 1",
       pget(root_new, "linkStats", "writeLinkStatsInterval") == "1",
       pget(root_new, "linkStats", "writeLinkStatsInterval"))
    ck("V5.8 DOCTYPE 存在",
       cfg_path.read_text(encoding="utf-8").startswith('<?xml version="1.0"')
       and "config_v2.dtd" in cfg_path.read_text(encoding="utf-8")[:300], "ok")

    # V6 可解析
    try:
        nmod = len(ET.parse(cfg_path).getroot().findall("module"))
        ck("V6.1 XML 可解析且模块数 >= 25", nmod >= 25, f"modules = {nmod}")
    except Exception as e:                                  # pragma: no cover
        ck("V6.1 XML 可解析", False, repr(e))

    return _ck_rows


# --------------------------------------------------------------------------
# 阶段 6：预注册落盘（必须先于运行）
# --------------------------------------------------------------------------
def write_preregistration(cfg_path: Path, meta: dict, checks: list[dict], pop: dict) -> Path:
    npass = sum(1 for c in checks if c["pass"])
    ts = datetime.now().strftime("%Y-%m-%d %H:%M")
    txt = f"""# Step 7.6D-S 预注册 — 低样本（100k）「稳定性筛查」

> **预注册声明**：本文件在 **7.6D-S 的任何 MATSim 运行启动之前** 冻结。
> 判据、阈值、口径、窗口在此确定；**运行之后不得回溯修改**。
> 若确需修改，必须新建 `7.6D-S-b` 并说明理由。
>
> 冻结时间：**{ts}**
> 状态：100k 人口已就位（复用 S100c 冻结件）；config 已生成并验证 **{npass}/{len(checks)} PASS**；正式 run 未启动。

---

## 0. ★与原设计的偏离（必须先读）

原定 **N = 50,000, f_cap = 0.25**。实测**不可行**：

    6.2B `allocate_cells` 的 FLOOR_PLUS_1 保底规则 = 「每个正 OD cell 至少 1 个 agent」
    而正 OD cell 数恒为 **71,136**（Σtrips 459,794 的全部非空格）
    -> ValueError: agents 50000 < positive OD cells 71136

即 50k **不是「跑得慢」，而是「建不出来」**。用户裁定改选 **N = 100,000, f_cap = 0.50**，
并**复用 S100c 已冻结的 100k 人口**（`reports/matsim_departure_6_3_3a_s100k/`）。

候选样本量实测形态（零仿真复现，与 7.5B 实测一致）：

| N | f_cap | 每 cell 最大 agent | 保底 cell 占比 | 可行性 |
|---:|---:|---:|---:|---|
| 50,000 | 0.25 | — | — | ❌ **不可行（< 71,136）** |
| 71,136 | 0.35568 | 1（完全退化） | 100.0% | 可行但退化 |
| 80,000 | 0.40 | 9 | 88.5% | 可行 |
| **100,000** | **0.50** | **26** | **70.5%** | ✅ **采用** |
| 200,000（正式档） | 1.00 | 114 | 41.5% | 正式档 |

**为什么选 100k 而不是更便宜的 80k**：① 复用 S100c 人口，**零人口重建**；
② 与 S100c 构成**同 N、同 f_cap、同采样规则、同 seed** 的严格对照（见 §5）——
把判决从「绝对门槛」升级为「绝对门槛 + 同 N 相对变化」；③ 成本仍仅为 200k 正式档的一半。

---

## 1. 本步骤**唯一**要回答的问题

> **新 route-choice 配置有没有让 assignment 从不稳定变成稳定？**

**不评价** demand scale、**不评价** λ、**不评价** OD 空间结构 / 距离带。
**不追求** Sim/Obs 变好 —— 只要稳定性达标即判成功（Sim/Obs 属 7.6E）。

## 2. 设计：只缩样本，不动机制

| 项 | 200k 正式档 | **7.6D-S** | 说明 |
|---|---:|---:|---|
| 人口 N | 200,000 | **100,000** | 低样本筛查 |
| `qsim.flowCapacityFactor` | `1.00` | **`0.50`** | = 100,000 / 200,000（采样一致性） |
| `qsim.storageCapacityFactor` | `1.00` | **`0.50`** | 同上 |
| `hermes.*CapacityFactor` | `1.00` | `1.00` | 不缩放（与 S100c 同构） |
| 采样规则 | `FLOOR_PLUS_1` | **`FLOOR_PLUS_1`** | 与 200k 基准**同规则**，不重构 |
| `λ` | 0.075 | 0.075 | 冻结 |
| seed | 4711 / 20260912 | 同 | 冻结 |

理由 `f_cap = 100,000/200,000`：保持与 S100c 相同的**采样一致性**思想 ——
样本量与容量同比缩放，使「物理供需比」不变，从而隔离出「样本量 ↓」的影响，
而不引入「拥堵水平变化」这一混杂因素。

## 3. route-choice 修复：与 7.6D **完全一致**（本轮不新增任何机制变量）

| 参数 | 基线 | 7.6D / 7.6D-S |
|---|---|---|
| `replanning.fractionOfIterationsToDisableInnovation` | `Infinity` | **`0.8`** |
| `replanning` 策略集 | `[ReRoute 1.00]` | **`[ReRoute 0.15, ChangeExpBeta 0.85]`** |
| `scoring.learningRate` | `1.0` | **`0.5`** |
| `routing.routingRandomness` | `0.0` | `0.0`（保留） |

其余一切（network / OD / 剖面 / threads / travelTimeCalculator / crosswalk / 观测靶场）
**逐参数不变**，见 `routechoice_7_6d_s_config_provenance.csv`。

## 4. 预注册判据（**稳定性筛查门槛**，不是拟合优劣门槛）

### 4.1 统计量定义

```
A_10:19(X) = ( max_{{k in 10..19}} X_k − min_{{k in 10..19}} X_k ) / mean_{{k in 10..19}} X_k
parity_gap_rel(X) = | even_mean − odd_mean | / mean        （周期结构诊断）
```

`X` 取 4 个口径：`ALL` / `MATCHED`(3,037) / `CATA`(1,020) / `SLIP`(2,017)。

### 4.2 门槛（**运行前固定**）

| 口径 | 门槛 | 性质 |
|---|---|---|
| **MATCHED** | `A_10:19 < 3%` | **正式稳定性判据** |
| **CATA** | `A_10:19 < 3%` | **正式稳定性判据** |
| **SLIP** | `A_10:19 < 5%` | **正式稳定性判据**（匝道侧放宽至 5%） |
| `ALL` | 仅报告 | 不设门槛（全网总量对空间重分配不敏感） |
| `parity_gap_rel` | 仅报告 | **辅助诊断**，不作为判据 |

### 4.3 ★统计量纪律（用户明确要求保持区分）

- **`A_10:19` = 正式稳定性判据**（含奇偶分离 + 窗内非周期漂移，更严格）。
- **`parity_gap_rel` = 周期结构诊断**（只含奇偶相位分离）。
- **两者不得再统称为「周期振幅」。** 7.6B 报的「20.75%」是 D03 的 `parity_gap_rel`，
  而同一档的 `A_10:19` 是 **23.25%**；D01 的二者为 **1.59% vs 8.48%（5.3×）**。

## 5. ★修复前 / 修复后：同 N 严格对照（本步骤最大信息增益）

| run | N | f_cap | 采样规则 | route-choice | 角色 |
|---|---:|---:|---|---|---|
| **REF_S100c_N100k** | 100,000 | 0.50 | FLOOR_PLUS_1 | 旧（ReRoute 1.0 / innovation=∞ / lr=1.0） | **修复前** |
| **S100k_rc_min** | 100,000 | 0.50 | FLOOR_PLUS_1 | 新（ReRoute 0.15 + ChangeExpBeta 0.85 / 0.8 / lr=0.5） | **修复后** |

两者除 route-choice 4 项外**完全一致**（同人口文件、同网络、同 seed、同窗口、
同 crosswalk）。S100c 已有完整 20 迭代 linkstats（it.0–it.19），故对照**边际成本为零**。

补充的跨样本量 before 参照（200k 档，零仿真复用）：

| run | N | MATCHED `A_10:19` | 判定 |
|---|---:|---:|---|
| BASELINE_D01 (E06) | 200,000 | **8.48%** | PARTIAL |
| REF_D02 (f=1.10) | 200,000 | **11.10%** | UNSTABLE |
| REF_D03 (f=1.20) | 200,000 | **23.25%** | UNSTABLE |
| REF_D04 (f=1.25) | 200,000 | **20.32%** | UNSTABLE |

## 6. 判决与后续动作（**运行前固定**）

```
若 MATCHED < 3% 且 CATA < 3% 且 SLIP < 5%
    -> SCREENING_PASS -> 再跑 200k x 20 it 正式稳定化
否则
    -> SCREENING_FAIL -> 暂停，**不消耗 200k 算力**，继续修 route-choice
```

辅助读法（不改变判决）：修复后 `A_10:19` 相对 S100c 的变化方向与幅度。
**注意**：即使绝对门槛未达标，只要相对 S100c 出现数量级下降，也说明修复方向正确。

无论 PASS / FAIL，均继续并报 `Q̄_10:19`（Primary）与 `Q_19`（Reference）双口径，
以及 `parity_gap_rel` 辅助诊断。

## 7. 冻结不变量（机器校验，非人工承诺）

由 `scripts/od/prepare_routechoice_7_6d_s.py` 的 V1–V6 共 **{len(checks)} 项校验** 保证：
network / seed / coordinateSystem / threads / routingAlgorithm / travelTimeCalculator /
linkStats 间隔 / networkRouteType / hermes capacity 与基线**逐值相同**。
实际 diff 见 `routechoice_7_6d_s_config_provenance.csv`。

## 8. 产物

| 路径 | 内容 |
|---|---|
| `configs/config_{RUN_ID}.xml` | 7.6D-S 正式 config（20 迭代） |
| `configs/config_{RUN_ID}_smoke.xml` | 冒烟 config（截断人口 × 3 迭代） |
| `routechoice_7_6d_s_config_provenance.csv` | 与基线逐参数 diff |
| `routechoice_7_6d_s_config_validation.json` | 配置验证（机器可读） |
| `outputs/{RUN_ID}/` | MATSim 输出（本步骤运行后产生） |
| `logs/{RUN_ID}_run.log` | 运行日志 |
| `audit/routechoice_stability_screening_7_6d_s.csv` | 稳定性筛查判决（含 S100c 对照） |

## 9. 人口

- persons = **{pop.get('persons'):,}**（期望 {N_SCREEN:,}）
- ΣEF = **{pop.get('sum_expansion_factor'):.1f}**（名义 459,794）
- 采样规则 = **FLOOR_PLUS_1**（6.2B 原生，**未重构**）
- 来源 = `reports/matsim_departure_6_3_3a_s100k/`（S100c 冻结件，**未重建**）

## 10. 配置验证

**{npass}/{len(checks)} PASS**（零仿真）—— 明细见 `routechoice_7_6d_s_config_validation.json`。
"""
    p = S_ROOT / "STEP7_6D_S_PREREGISTRATION.md"
    p.write_text(txt, encoding="utf-8")
    return p


def write_provenance(cfg_path: Path) -> Path:
    base = param_map(BASELINE_CFG)
    new = param_map(cfg_path)
    rows = []
    for k in sorted(set(base) | set(new)):
        bv, nv = base.get(k), new.get(k)
        rows.append({"module": k[0], "param": k[1],
                     "baseline_value": bv, "new_value": nv,
                     "changed": not same_value(bv, nv),
                     "is_routechoice_patch": k in MIN_PATCH,
                     "is_sampling_consistency": k in F_CAP_PATCH})
    p = S_ROOT / "routechoice_7_6d_s_config_provenance.csv"
    with p.open("w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["module", "param", "baseline_value",
                                           "new_value", "changed",
                                           "is_routechoice_patch", "is_sampling_consistency"])
        w.writeheader()
        w.writerows(rows)
    srows = []
    for src, label in ((BASELINE_CFG, "baseline"), (cfg_path, "new")):
        for nm, wt in strategy_list(src):
            srows.append({"source": label, "strategyName": nm, "weight": wt})
    sp = S_ROOT / "routechoice_7_6d_s_strategy_provenance.csv"
    with sp.open("w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["source", "strategyName", "weight"])
        w.writeheader()
        w.writerows(srows)
    return p


# --------------------------------------------------------------------------
# 阶段 7：运行
# --------------------------------------------------------------------------
def run_matsim(cfg_path: Path, log_name: str, heap: str) -> int:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    log = LOG_DIR / log_name
    print(f"=== 运行 {cfg_path.name} -> {log} ===")
    t0 = time.time()
    rc = matsim_env.run_java_streaming(
        ["org.matsim.run.RunMatsim", str(cfg_path)], log_path=log, heap=heap)
    print(f"--- {cfg_path.name}: exit={rc}  耗时 {(time.time() - t0)/60:.2f} min ---\n")
    return rc


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--smoke", type=int, default=0)
    ap.add_argument("--run", action="store_true")
    ap.add_argument("--heap", default="24g")
    ap.add_argument("--force", action="store_true", help="强制重建 50k 人口三阶段")
    ap.add_argument("--skip-pipeline", action="store_true", help="跳过人口三阶段（已建好时）")
    args = ap.parse_args()

    S_ROOT.mkdir(parents=True, exist_ok=True)
    print("=" * 78)
    print("Step 7.6D-S — 100k 低样本稳定性筛查")
    print("=" * 78)
    print("=== MATSim 运行时 ===")
    for k, v in matsim_env.describe().items():
        print(f"  {k}: {v}")
    print(f"  N_SCREEN     : {N_SCREEN:,}")
    print(f"  f_cap        : {F_CAP:g}  (= {N_SCREEN:,}/{N_REF:,})")
    print(f"  route-choice : {MIN_PATCH[('replanning', 'fractionOfIterationsToDisableInnovation')][1]} / "
          f"{STRATEGY_SPEC} / lr={MIN_PATCH[('scoring', 'learningRate')][1]}")
    print(f"  run_id       : {RUN_ID}")
    print()

    mt_before = snapshot_mtimes(FROZEN_WATCH)

    # ---- 阶段 1-3：50k 人口 ----
    if args.skip_pipeline:
        st1 = st2 = st3 = {"skipped": True}
        pop = population_stats(POP_FILE)
    else:
        st1 = stage1_population(args.force)
        st2 = stage2_connected(args.force)
        st3 = stage3_departure(args.force)
        pop = population_stats(POP_FILE)

    print(f"\n[人口] persons = {pop['persons']:,}  ΣEF = {pop['sum_expansion_factor']:.1f}")
    ck(f"P0 样本量不低于 FLOOR_PLUS_1 下界（{FLOOR_MIN_CELLS:,} 正 OD cell）",
       N_SCREEN >= FLOOR_MIN_CELLS, f"N = {N_SCREEN:,} >= {FLOOR_MIN_CELLS:,}")
    ck(f"P1 100k 人口 persons == {N_SCREEN:,}", pop["persons"] == N_SCREEN, f"{pop['persons']:,}")
    ck("P2 ΣEF 与 200k 基准同锚（459,794，f_cap 不改变 EF）",
       abs(pop["sum_expansion_factor"] - 459794.0) < 500.0,
       f"{pop['sum_expansion_factor']:.1f}")

    mt_after = snapshot_mtimes(FROZEN_WATCH)
    unchanged = [k for k in mt_before if mt_before[k] == mt_after[k]]
    changed = [k for k in mt_before if mt_before[k] != mt_after[k]]
    ck("P3 冻结件 mtime 全部未变", not changed,
       f"{len(unchanged)}/{len(mt_before)} 不变" + (f" | 变动: {changed}" if changed else ""))

    # ---- 阶段 4-6 ----
    smoke = args.smoke
    cfg_path, out_dir, meta = build(smoke=smoke)
    print(f"[build] {cfg_path}")
    print(f"[build] output -> {out_dir}  lastIteration={meta['last_iteration']}")

    checks = validate(cfg_path, expect_iter=meta["last_iteration"], smoke=smoke)
    prov = write_provenance(cfg_path)

    if not smoke:
        prereg = write_preregistration(cfg_path, meta, checks, pop)
        print(f"[prereg] 预注册已冻结 -> {prereg}")

    npass = sum(1 for c in checks if c["pass"])
    summary = {
        "step": "7.6D-S",
        "title": "Low-sample (50k) route-choice stability screening",
        "status": "PASS" if npass == len(checks) else "FAIL",
        "checks_pass": npass, "checks_total": len(checks),
        "checks": checks,
        "run_id": RUN_ID, "config": str(cfg_path), "smoke": smoke,
        "last_iteration": meta["last_iteration"], "output_dir": str(out_dir),
        "baseline_config": str(BASELINE_CFG),
        "design": {"n_screen": N_SCREEN, "n_ref": N_REF, "f_cap": F_CAP,
                   "sampling_rule": "FLOOR_PLUS_1",
                   "routechoice_patch": {f"{m}.{p}": {"baseline": a, "new": b}
                                         for (m, p), (a, b) in MIN_PATCH.items()},
                   "strategy_spec": [{"name": n, "weight": w} for n, w in STRATEGY_SPEC]},
        "preregistered_thresholds": TH_SCREEN,
        "floor_plus_1_min_cells": FLOOR_MIN_CELLS,
        "screening_before_run": {k: str(v) for k, v in SCREEN_BEFORE.items()},
        "statistic_discipline": {
            "formal_criterion": "A_10:19 = (max-min)/mean over it.10-19",
            "auxiliary_diagnostic": "parity_gap_rel = |even-odd|/mean",
            "note": "两者不得统称为「周期振幅」",
        },
        "population": pop,
        "stages": {"stage1": st1, "stage2": st2, "stage3": st3},
        "frozen_mtime_unchanged": not changed,
        "matsim_rerun": bool(smoke or args.run),
        "existing_reports_untouched": True,
    }
    js = S_ROOT / "routechoice_7_6d_s_config_validation.json"
    js.write_text(json.dumps(summary, ensure_ascii=False, indent=2, default=str), encoding="utf-8")

    print(f"\n配置验证: {npass}/{len(checks)} PASS")
    print(f"provenance -> {prov}")
    print(f"validation -> {js}")

    if smoke:
        rc = run_matsim(cfg_path, f"smoke_{RUN_ID}.log", args.heap)
        it_dir = Path(out_dir) / "ITERS"
        stats = sorted(it_dir.glob(f"it.*/{meta['run_id']}.*.linkstats.txt.gz")) \
            if it_dir.exists() else []
        print(f"[smoke] linkstats = {len(stats)} 份（期望 3）")
        print("SMOKE STATUS:", "PASS" if rc == 0 and len(stats) >= 3 else "FAIL")
        return rc

    if args.run:
        rc = run_matsim(cfg_path, f"{RUN_ID}_run.log", args.heap)
        it_dir = RUN_DIR / "ITERS"
        stats = sorted(it_dir.glob(f"it.*/{RUN_ID}.*.linkstats.txt.gz")) \
            if it_dir.exists() else []
        print(f"[run] linkstats = {len(stats)} 份（期望 {TOTAL_ITER}）")
        print("RUN STATUS:", "PASS" if rc == 0 and len(stats) >= TOTAL_ITER else "FAIL")
        return rc

    print("\n（仅生成 + 验证 + 预注册；未启动 MATSim。用 --smoke N 或 --run 启动。）")
    return 0 if npass == len(checks) else 1


if __name__ == "__main__":
    raise SystemExit(main())
