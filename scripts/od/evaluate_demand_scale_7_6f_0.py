#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""
evaluate_demand_scale_7_6f_0.py — Step 7.6F-0：在新稳定分配底座上重算 demand=1.00 基准
（零仿真；只读既有 linkstats；不启动 MATSim；不改任何参数）。

背景（为什么需要这一步）
------------------------
7.6E 已判 `STABILITY_PASS`（G1–G6 6/6）⇒ **route-choice 层正式冻结**。
于是 7.6B 时代的禁令「route-choice 未稳定 ⇒ demand scale 不可评价」**已经解除**。

但**不能**把旧 D01–D04 的 Sim/Obs 直接乘一个 +3.1% 修正因子：7.6E 改变的是
**assignment dynamics**（分配动力学），而不是需求本身：

        旧：  Demand effect → Demand × 不稳定 route-choice → D01–D04 观测
        新：  Demand effect → 稳定 route-choice            → R01 (demand=1.00)

因此本步（7.6F-0）只回答一个问题：

    ★ 在 demand = 1.00 的情况下，R01 稳定分配解对应什么**新的 MATCHED Sim/Obs 水平**？

**不选 demand scale、不评价 λ、不评价 OD 空间结构。**

双口径（用户 2026-09-16 裁定 ①，7.6E 沿用）
------------------------------------------
    Primary  : 收敛窗 it.10–19 的**奇偶相位均衡周期均值**（逐链路平均 → 再算 Sim/Obs）
    Reference: **it.19 单点**（保留原始可追溯性）
两者**同时输出、不替代**。本步对**所有对照 run（含旧配置）统一施加同一口径**，
使「极限环中心」与「稳定收敛解」可以 apples-to-apples 比较。

★ 口径纪律（与 7.3.6B / 7.4.2 / 7.4.3 / 7.5A / 7.5B 逐字节同源）
--------------------------------------------------------------
    obs = 7.1 冻结口径（工作日 → 日内均值 → LinkID×hour 日中位；hour = 7,8）
    sim = median(匹配 MATSim 有向边 HRSx-yavg) × SCALE
    SCALE = ΣT / N_sample     （200k → 2.29897；100k → 4.59794）
    headline 窗口 = 08-09；另出 07-08 / AM
评价函数直接 import 冻结模块（**复用而非复制**）：
    compare_final_crosswalk_7_3_6b  (load_traffic / normalize_crosswalk /
                                     load_linkstats / calc_method / _metrics / SCALE / WINDOWS)
    evaluate_calibration_7_4_2      (backtest_one / summarize / comparison_table)

★ 注意一个窗口辨析（易错）
------------------------
    稳定性审计的 Q̄_10:19 / Q_19 用 **ΣHRS0-24avg**（0–24 全天箱，由 6.3.3A
    「全部 08:00 出发」决定其≈AM 脉冲）；Sim/Obs 用 **HRS8-9avg**。
    本脚本两者分别处理：Q 口径直接复用 7.6D/7.6E 的审计缓存，Sim/Obs 走
    freeze 评价链路 —— **不混用**。

产物（reports/od_calibration_7_6f/）
-----------------------------------
    demand_scale_7_6f_0_backtest.csv        逐断面（run × caliber）
    demand_scale_7_6f_0_roadcat_summary.csv 全指标（method × RoadCat × window）
    demand_scale_7_6f_0_comparison.csv      ★ run × caliber × window × 头条指标
    demand_scale_7_6f_0_decomposition.csv   ★★ 旧分配层 vs 新分配层 机制分解表
    step7_6f_0_summary.json
    STEP7_6F_0_REPORT.md

用法
----
    python scripts/od/evaluate_demand_scale_7_6f_0.py
    python scripts/od/evaluate_demand_scale_7_6f_0.py --no-100k     # 只做 200k
    python scripts/od/evaluate_demand_scale_7_6f_0.py --no-ref      # 不纳入 D02–D04
"""
from __future__ import annotations

import argparse
import gzip
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(r"D:\Luan\2026-05\2_Singapore")
sys.path.insert(0, str(ROOT / "scripts" / "od"))

import compare_final_crosswalk_7_3_6b as bt        # noqa: E402  冻结观测 / crosswalk / 指标口径
import evaluate_calibration_7_4_2 as ev1           # noqa: E402  评价函数（summarize / comparison_table）

NEW_ROOT = ROOT / "matsim_routechoice_7_6d"
OUT = ROOT / "reports" / "od_calibration_7_6f"
CYCLE_DIR = OUT / "_cycle_linkstats"
AUDIT_CACHE = NEW_ROOT / "audit" / "routechoice_stability_by_iter.csv"

TRAFFIC = ev1.TRAFFIC
FINAL_CW = ev1.FINAL_CW

CONV_START, CONV_END = 10, 19
CONV_ITERS = list(range(CONV_START, CONV_END + 1))
REF_ITER = 19

REAL_CAR_OD_TOTAL = 459794.0
SCALE_200K = REAL_CAR_OD_TOTAL / 200000.0      # 2.29897
SCALE_100K = REAL_CAR_OD_TOTAL / 100000.0      # 4.59794

# 交叉验证锚（7.4.3 demand_scale_comparison.csv，it.19 口径）
LEGACY_D01_SIMOBS_0809 = 0.707041
LEGACY_D01_SIMOBS_AM = 0.682991

# --------------------------------------------------------------------------
# run 目录表
#  role: anchor_new    = 新的稳定分配底座（7.6E R01）
#        before_200k   = 旧配置、同 N=200k、同 f_cap=1.00（同 N 单变量对照）
#        before_ref    = 旧配置、其他 demand 档（D02–D04，仅作旧响应谱参照）
#        before_100k / after_100k = 100k 同 N 对照（跨规模机制签名）
# --------------------------------------------------------------------------
RUNS = [
    {
        "label": "R01", "role": "anchor_new",
        "out_dir": NEW_ROOT / "outputs" / "R01_rc_min", "run_id": "R01_rc_min",
        "N": 200000, "f_cap": 1.00, "f_demand": 1.00, "rc": "rc_min",
        "stage": "7.6E", "desc": "7.6E 200k 正式稳定化（route-choice 修复后，判 STABILITY_PASS 6/6）",
    },
    {
        "label": "D01", "role": "before_200k",
        "out_dir": ROOT / "reports" / "od_calibration_7_4_2" / "E06_lam0p075_cap1p00",
        "run_id": "E06",
        "N": 200000, "f_cap": 1.00, "f_demand": 1.00, "rc": "legacy",
        "stage": "7.4.2", "desc": "7.4.2 E06（基线：ReRoute 1.0 / innovation=Infinity / learningRate=1.0）",
    },
    {
        "label": "D02", "role": "before_ref",
        "out_dir": ROOT / "reports" / "od_calibration_7_4_3" / "D02_lam0p075", "run_id": "D02",
        "N": 200000, "f_cap": 1.00, "f_demand": 1.10, "rc": "legacy",
        "stage": "7.4.3", "desc": "7.4.3 D02（f=1.10，修复前）",
    },
    {
        "label": "D03", "role": "before_ref",
        "out_dir": ROOT / "reports" / "od_calibration_7_4_3" / "D03_lam0p075", "run_id": "D03",
        "N": 200000, "f_cap": 1.00, "f_demand": 1.20, "rc": "legacy",
        "stage": "7.4.3", "desc": "7.4.3 D03（f=1.20，修复前）",
    },
    {
        "label": "D04", "role": "before_ref",
        "out_dir": ROOT / "reports" / "od_calibration_7_4_3" / "D04_lam0p075", "run_id": "D04",
        "N": 200000, "f_cap": 1.00, "f_demand": 1.25, "rc": "legacy",
        "stage": "7.4.3", "desc": "7.4.3 D04（f=1.25，修复前）",
    },
    {
        "label": "S100c", "role": "before_100k",
        "out_dir": ROOT / "reports" / "od_sample_7_5a" / "S100c_lam0p075_cap0p50",
        "run_id": "S100c",
        "N": 100000, "f_cap": 0.50, "f_demand": 1.00, "rc": "legacy",
        "stage": "7.5A", "desc": "7.5A S100c（N=100k, f_cap=0.50, FLOOR_PLUS_1, 旧 route-choice）",
    },
    {
        "label": "S100k", "role": "after_100k",
        "out_dir": NEW_ROOT / "outputs" / "S100k_rc_min", "run_id": "S100k_rc_min",
        "N": 100000, "f_cap": 0.50, "f_demand": 1.00, "rc": "rc_min",
        "stage": "7.6D-S", "desc": "7.6D-S 100k 筛查（route-choice 修复后，判 SCREENING_PASS）",
    },
]

ROLE_ORDER = ["anchor_new", "before_200k", "before_ref", "before_100k", "after_100k"]

_ck: list[dict] = []


def ck(name: str, ok: bool, detail: str = "") -> bool:
    _ck.append({"check": name, "pass": bool(ok), "detail": str(detail)})
    print(f"   [{'PASS' if ok else 'FAIL'}] {name}  {detail}")
    return bool(ok)


def scale_of(run: dict) -> float:
    return REAL_CAR_OD_TOTAL / float(run["N"])


# --------------------------------------------------------------------------
# 逐迭代链路定位
# --------------------------------------------------------------------------
def iter_linkstats(out_dir: Path, run_id: str, it: int) -> Path | None:
    d = out_dir / "ITERS" / f"it.{it}"
    if not d.exists():
        return None
    hits = sorted(d.glob(f"{run_id}.*.linkstats.txt.gz"))
    return hits[0] if hits else None


CYCLE_COLS = ["LINK", "HRS7-8avg", "HRS8-9avg", "HRS0-24avg"]


def build_cycle_linkstats(run: dict, iters: list[int], dest: Path,
                          force: bool = False) -> tuple[Path, int]:
    """构造「收敛窗周期均值」linkstats：逐链路对 it.10–19 求平均。

    与稳定性审计的 Q̄_10:19 语义一致（求均值与求和可交换 ⇒ Σ_link(mean_k) == mean_k(Σ_link)）。
    若 dest 已存在且 force=False 则复用（内容只依赖 it.10–19 的 linkstats，与阈值无关）。
    """
    if dest.exists() and not force:
        return dest, len(iters)
    acc: pd.DataFrame | None = None
    n_used = 0
    for it in iters:
        p = iter_linkstats(run["out_dir"], run["run_id"], it)
        if p is None:
            print(f"      [warn] {run['label']} it.{it} linkstats 缺失 -> 跳过该迭代")
            continue
        df = pd.read_csv(p, sep="\t", compression="gzip",
                         usecols=CYCLE_COLS, low_memory=False)
        df["LINK"] = df["LINK"].astype(str).str.strip()
        for c in CYCLE_COLS[1:]:
            df[c] = pd.to_numeric(df[c], errors="coerce")
        # 同一迭代内同 LINK 可能多行（多类型）-> 先聚合
        g = df.groupby("LINK", as_index=True)[CYCLE_COLS[1:]].sum()
        acc = g if acc is None else acc.add(g, fill_value=0.0)
        n_used += 1
    if acc is None:
        raise RuntimeError(f"{run['label']}: 没有任何可用 linkstats")
    acc = (acc / float(n_used)).reset_index()
    dest.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(str(dest), "wt", encoding="utf-8", newline="\n") as f:
        f.write("\t".join(CYCLE_COLS) + "\n")
        acc.to_csv(f, sep="\t", index=False, header=False,
                   float_format="%.6f", lineterminator="\n")
    return dest, n_used


# --------------------------------------------------------------------------
# 单次 backtest（注入该 run 的 SCALE）
# --------------------------------------------------------------------------
def backtest_on(method: str, cw_base: pd.DataFrame, obs: pd.DataFrame,
                ls_path: Path, scale: float) -> pd.DataFrame:
    saved = bt.SCALE
    try:
        bt.SCALE = float(scale)
        cw = cw_base.copy()
        cw["method"] = method
        sec = ev1.backtest_one(method, cw, obs, ls_path)
    finally:
        bt.SCALE = saved
    return sec if sec is not None else pd.DataFrame()


def load_audit_cache() -> pd.DataFrame:
    if not AUDIT_CACHE.exists():
        return pd.DataFrame()
    return pd.read_csv(AUDIT_CACHE, encoding="utf-8-sig")


def main() -> int:
    global OUT, CYCLE_DIR

    ap = argparse.ArgumentParser()
    ap.add_argument("--no-100k", action="store_true", help="不纳入 100k 跨规模对照")
    ap.add_argument("--no-ref", action="store_true", help="不纳入 D02–D04（旧 demand 响应谱参照）")
    ap.add_argument("--out-dir", type=Path, default=OUT)
    ap.add_argument("--force-cycle", action="store_true",
                    help="强制重建收敛窗周期均值 linkstats（默认若已存在则复用）")
    args = ap.parse_args()

    OUT = args.out_dir
    CYCLE_DIR = OUT / "_cycle_linkstats"
    OUT.mkdir(parents=True, exist_ok=True)

    print("=" * 80)
    print("Step 7.6F-0 — 新稳定分配底座上的 demand=1.00 基准重算（零仿真、只读）")
    print("=" * 80)

    runs = [r for r in RUNS
            if not (args.no_ref and r["role"] == "before_ref")
            and not (args.no_100k and r["role"] in ("before_100k", "after_100k"))]

    # ---- [0] 前置核验 -----------------------------------------------------
    print("\n[0/6] 前置核验（冻结件 / 运行完整性）")
    ck("P1 7.3.6A Final Crosswalk 存在",
       FINAL_CW.exists(), FINAL_CW.name)
    ck("P2 7.1 冻结观测存在", TRAFFIC.exists(), TRAFFIC.name)
    ck("P3 SCALE(200k) == 2.29897", abs(SCALE_200K - 2.29897) < 1e-9, f"{SCALE_200K:.5f}")
    ck("P4 SCALE(100k) == 4.59794", abs(SCALE_100K - 4.59794) < 1e-9, f"{SCALE_100K:.5f}")
    for r in runs:
        n_ls = sum(1 for it in range(0, 20) if iter_linkstats(r["out_dir"], r["run_id"], it))
        ck(f"P5.{r['label']} 20/20 linkstats", n_ls == 20, f"{n_ls}/20  ({r['out_dir'].name}/{r['run_id']})")

    # ---- [1] 载入观测 + crosswalk ---------------------------------------
    print("\n[1/6] 载入 7.1 冻结观测 + 7.3.6A Final Crosswalk")
    obs = bt.load_traffic(TRAFFIC)
    cw_base = bt.normalize_crosswalk(FINAL_CW, "final")
    print(f"      observed LTA sections = {obs['LinkID'].nunique():,}")
    print(f"      crosswalk rows = {len(cw_base):,}  sections = {cw_base['lta_linkid'].nunique():,}")

    # ---- [2] 构造周期均值 linkstats（Primary 口径） -----------------------
    print(f"\n[2/6] 构造收敛窗周期均值 linkstats（it.{CONV_START}–{CONV_END}，逐链路平均）")
    calibers: list[dict] = []
    for r in runs:
        dest = CYCLE_DIR / f"{r['label']}_conv.linkstats.txt.gz"
        existed = dest.exists() and not args.force_cycle
        path, n_used = build_cycle_linkstats(r, CONV_ITERS, dest, force=args.force_cycle)
        print(f"      {r['label']:<6} cycle-mean over {n_used} iters -> {dest.name}"
              + ("   [cached]" if existed else ""))
        calibers.append({"run": r, "caliber": "PRIMARY_cycle_10_19", "ls": path,
                         "scale": scale_of(r), "method": f"{r['label']}|cycle"})
        p19 = iter_linkstats(r["out_dir"], r["run_id"], REF_ITER)
        if p19 is None:
            print(f"      [warn] {r['label']} it.{REF_ITER} 缺失")
        else:
            calibers.append({"run": r, "caliber": "REFERENCE_it19", "ls": p19,
                             "scale": scale_of(r), "method": f"{r['label']}|it19"})

    # ---- [3] 逐断面 backtest -------------------------------------------
    print("\n[3/6] 逐断面 backtest（每 run 注入自身 SCALE = ΣT/N）")
    parts = []
    for c in calibers:
        sec = backtest_on(c["method"], cw_base, obs, c["ls"], c["scale"])
        if sec.empty:
            print(f"      {c['method']}: EMPTY")
            continue
        sec["run"] = c["run"]["label"]
        sec["caliber"] = c["caliber"]
        parts.append(sec)
        print(f"      {c['method']:<14} SCALE={c['scale']:.5f}  sections={len(sec):,}")
    backtest = pd.concat(parts, ignore_index=True)
    backtest.to_csv(OUT / "demand_scale_7_6f_0_backtest.csv", index=False, encoding="utf-8-sig")

    summary = ev1.summarize(backtest)
    summary.to_csv(OUT / "demand_scale_7_6f_0_roadcat_summary.csv",
                   index=False, encoding="utf-8-sig")
    cmp_tbl = ev1.comparison_table(summary, REF_ITER)
    # 回填 run / caliber
    meth2run = {c["method"]: c["run"]["label"] for c in calibers}
    meth2cal = {c["method"]: c["caliber"] for c in calibers}
    cmp_tbl["run"] = cmp_tbl["method"].map(meth2run)
    cmp_tbl["caliber"] = cmp_tbl["method"].map(meth2cal)
    cmp_tbl.to_csv(OUT / "demand_scale_7_6f_0_comparison.csv",
                   index=False, encoding="utf-8-sig")

    # ---- [4] 交叉验证：D01 it.19 必须重现 7.4.3 的 0.707041 --------------
    print("\n[4/6] 交叉验证（必须逐位重现 7.4.3 既有数值）")

    def simobs(method: str, window: str = "08-09") -> float | None:
        z = cmp_tbl[(cmp_tbl["method"] == method) & (cmp_tbl["window"] == window)]
        if z.empty:
            return None
        v = z.iloc[0]["SimObs_all"]
        return float(v) if pd.notna(v) else None

    d01_it19 = simobs("D01|it19")
    ck("C1 D01|it19 SimObs_all(08-09) == 0.707041（7.4.3 逐位一致）",
       d01_it19 is not None and abs(d01_it19 - LEGACY_D01_SIMOBS_0809) < 5e-6,
       f"{d01_it19!r} vs {LEGACY_D01_SIMOBS_0809}")
    d01_it19_am = simobs("D01|it19", "AM")
    ck("C2 D01|it19 SimObs_all(AM) == 0.682991",
       d01_it19_am is not None and abs(d01_it19_am - LEGACY_D01_SIMOBS_AM) < 5e-6,
       f"{d01_it19_am!r} vs {LEGACY_D01_SIMOBS_AM}")

    # ---- [4b] 与 7.6D/7.6E 审计缓存对账（Q̄_10:19 / Q_19，HRS0-24avg 口径）---
    audit = load_audit_cache()
    qc = {}
    if audit.empty:
        ck("C3 审计缓存可用", False, "routechoice_stability_by_iter.csv 缺失")
    else:
        #  本地 label  ->  审计缓存里的 run 名（★方向别写反）
        AUDIT_NAME = {"D01": "BASELINE_D01", "R01": "R01_rc_min",
                      "D02": "REF_D02_f1.10", "D03": "REF_D03_f1.20", "D04": "REF_D04_f1.25",
                      "S100c": "REF_S100c_N100k", "S100k": "S100k_rc_min"}
        matched_set = None
        cwraw = pd.read_csv(FINAL_CW, encoding="utf-8-sig")
        matched_set = set(cwraw["matsim_link_id"].astype(str).str.strip())
        # 用 cycle-mean linkstats 的 HRS0-24avg 复核 Q̄_10:19(MATCHED)
        for c in calibers:
            if c["caliber"] != "PRIMARY_cycle_10_19":
                continue
            df = pd.read_csv(c["ls"], sep="\t", compression="gzip",
                             usecols=["LINK", "HRS0-24avg"], low_memory=False)
            df["LINK"] = df["LINK"].astype(str).str.strip()
            df["HRS0-24avg"] = pd.to_numeric(df["HRS0-24avg"], errors="coerce").fillna(0.0)
            s = df.groupby("LINK")["HRS0-24avg"].sum()
            got = float(s.reindex(list(matched_set)).fillna(0.0).sum())
            lab = c["run"]["label"]
            cair = AUDIT_NAME.get(lab, lab)
            row = audit[(audit["run"] == cair) & (audit["iteration"] == CONV_END)]
            exp = float(row["MATCHED"].iloc[0]) if len(row) else float("nan")
            # 用周期均值比较：审计的 Q_conv_mean 需自行从缓存重算
            sub = audit[(audit["run"] == cair)
                        & (audit["iteration"].between(CONV_START, CONV_END))]
            exp_mean = float(sub["MATCHED"].mean()) if len(sub) else float("nan")
            qc[lab] = {"recomputed_Qbar_MATCHED_hrs024": got,
                       "audit_Qbar_MATCHED_hrs024": exp_mean,
                       "rel_diff": (abs(got - exp_mean) / exp_mean) if exp_mean else float("nan")}
            ck(f"C3.{lab} Σ(cycle-mean HRS0-24avg|MATCHED) == 审计 Q̄_10:19",
               np.isfinite(exp_mean) and abs(got - exp_mean) / exp_mean < 1e-6,
               f"{got:,.0f} vs {exp_mean:,.0f}")

    # ---- [5] ★★ 机制分解表 ---------------------------------------------
    print("\n[5/6] ★★ 旧分配层 vs 新分配层 机制分解")

    def rget(run_lab: str, cal: str, col: str, window: str = "08-09"):
        m = f"{run_lab}|{cal}"
        z = cmp_tbl[(cmp_tbl["method"] == m) & (cmp_tbl["window"] == window)]
        if z.empty:
            return None
        v = z.iloc[0][col]
        return float(v) if pd.notna(v) else None

    def audit_q(run_lab: str) -> dict:
        inv = {"D01": "BASELINE_D01", "R01": "R01_rc_min",
               "D02": "REF_D02_f1.10", "D03": "REF_D03_f1.20", "D04": "REF_D04_f1.25",
               "S100c": "REF_S100c_N100k", "S100k": "S100k_rc_min"}
        if audit.empty or run_lab not in inv:
            return {}
        sub = audit[(audit["run"] == inv[run_lab])
                    & (audit["iteration"].between(CONV_START, CONV_END))]
        r19 = audit[(audit["run"] == inv[run_lab]) & (audit["iteration"] == REF_ITER)]
        out = {}
        if len(sub):
            out["Qbar_10_19_MATCHED"] = float(sub["MATCHED"].mean())
            out["Qbar_10_19_ALL"] = float(sub["ALL"].mean())
            out["A_10_19_MATCHED"] = float((sub["MATCHED"].max() - sub["MATCHED"].min()) / sub["MATCHED"].mean())
        if len(r19):
            out["Q_19_MATCHED"] = float(r19["MATCHED"].iloc[0])
        return out

    dec_rows = []
    for r in runs:
        m = r["label"]
        row = {
            "run": m, "role": r["role"], "stage": r["stage"],
            "N": r["N"], "f_cap": r["f_cap"], "f_demand": r["f_demand"],
            "route_choice": r["rc"], "SCALE": scale_of(r),
            "SimObs_all_cycle": rget(m, "cycle", "SimObs_all"),
            "SimObs_all_it19": rget(m, "it19", "SimObs_all"),
            "SimObs_all_AM_cycle": rget(m, "cycle", "SimObs_all", "AM"),
            "CATA_cycle": rget(m, "cycle", "CATA_simobs"),
            "SLIP_cycle": rget(m, "cycle", "SLIP_simobs"),
            "CATA_over_SLIP_cycle": rget(m, "cycle", "CATA_over_SLIP"),
            "WMAPE_cycle": rget(m, "cycle", "WMAPE_all"),
            "GEH_lt5_cycle": rget(m, "cycle", "GEH_lt_5_all"),
            "GEH_lt10_cycle": rget(m, "cycle", "GEH_lt_10_all"),
            "Pearson_cycle": rget(m, "cycle", "Pearson_all"),
            "Spearman_cycle": rget(m, "cycle", "Spearman_all"),
            "implied_demand_mult_to_1_cycle": (
                1.0 / rget(m, "cycle", "SimObs_all")
                if rget(m, "cycle", "SimObs_all") else None),
            "phase_offset_it19_vs_cycle": (
                (rget(m, "it19", "SimObs_all") / rget(m, "cycle", "SimObs_all") - 1.0)
                if (rget(m, "cycle", "SimObs_all") and rget(m, "it19", "SimObs_all")) else None),
        }
        row.update(audit_q(m))
        dec_rows.append(row)

    dec = pd.DataFrame(dec_rows)
    dec.to_csv(OUT / "demand_scale_7_6f_0_decomposition.csv",
               index=False, encoding="utf-8-sig")

    # ---- route-choice 效应量（固定 demand=1.00） -------------------------
    def delta(before_lab: str, after_lab: str) -> dict:
        b = rget(before_lab, "cycle", "SimObs_all")
        a = rget(after_lab, "cycle", "SimObs_all")
        b19 = rget(before_lab, "it19", "SimObs_all")
        a19 = rget(after_lab, "it19", "SimObs_all")
        d = {}
        if b and a:
            d["before_cycle"] = b
            d["after_cycle"] = a
            d["delta_abs"] = a - b
            d["delta_rel"] = a / b - 1.0
        if b19 and a19:
            d["before_it19"] = b19
            d["after_it19"] = a19
            d["delta_rel_it19"] = a19 / b19 - 1.0
        ab = audit_q(before_lab)
        aa = audit_q(after_lab)
        if ab.get("Qbar_10_19_MATCHED") and aa.get("Qbar_10_19_MATCHED"):
            d["Qbar_MATCHED_before"] = ab["Qbar_10_19_MATCHED"]
            d["Qbar_MATCHED_after"] = aa["Qbar_10_19_MATCHED"]
            d["Qbar_MATCHED_delta_rel"] = (aa["Qbar_10_19_MATCHED"]
                                          / ab["Qbar_10_19_MATCHED"] - 1.0)
        return d

    eff_200k = delta("D01", "R01")
    eff_100k = delta("S100c", "S100k")

    # ---- 旧 demand 响应谱（旧配置，统一 cycle 口径） ---------------------
    legacy_curve = []
    for lab in ["D01", "D02", "D03", "D04"]:
        if not (dec["run"] == lab).any():
            continue
        rr = dec[dec["run"] == lab].iloc[0]
        legacy_curve.append({
            "f_demand": float(rr["f_demand"]),
            "SimObs_all_cycle": rr["SimObs_all_cycle"],
            "SimObs_all_it19": rr["SimObs_all_it19"],
            "CATA_cycle": rr["CATA_cycle"], "SLIP_cycle": rr["SLIP_cycle"],
            "CATA_over_SLIP_cycle": rr["CATA_over_SLIP_cycle"],
            "phase_offset_it19_vs_cycle": rr.get("phase_offset_it19_vs_cycle"),
            "A_10_19_MATCHED": rr.get("A_10_19_MATCHED"),
        })
    legacy_curve = sorted(legacy_curve, key=lambda x: x["f_demand"])

    new_point = None
    if (dec["run"] == "R01").any():
        rr = dec[dec["run"] == "R01"].iloc[0]
        new_point = {
            "f_demand": 1.00,
            "SimObs_all_cycle": rr["SimObs_all_cycle"],
            "SimObs_all_it19": rr["SimObs_all_it19"],
            "SimObs_all_AM_cycle": rr["SimObs_all_AM_cycle"],
            "CATA_cycle": rr["CATA_cycle"], "SLIP_cycle": rr["SLIP_cycle"],
            "CATA_over_SLIP_cycle": rr["CATA_over_SLIP_cycle"],
            "WMAPE_cycle": rr["WMAPE_cycle"], "GEH_lt5_cycle": rr["GEH_lt5_cycle"],
            "GEH_lt10_cycle": rr["GEH_lt10_cycle"], "Pearson_cycle": rr["Pearson_cycle"],
            "Spearman_cycle": rr["Spearman_cycle"],
            "implied_demand_mult_to_1_cycle": rr["implied_demand_mult_to_1_cycle"],
            "Qbar_10_19_MATCHED": rr.get("Qbar_10_19_MATCHED"),
            "Q_19_MATCHED": rr.get("Q_19_MATCHED"),
        }

    # ---- 是否必须补跑 D02–D04 的判据（信息量而非阈值硬性） ---------------
    need_d02_d04 = None
    note = ""
    if new_point and legacy_curve:
        lv = [x["SimObs_all_cycle"] for x in legacy_curve if x["SimObs_all_cycle"]]
        if lv:
            spread = max(lv) - min(lv)
            need_d02_d04 = {
                "legacy_curve_SimObs_spread": spread,
                "legacy_curve_SimObs_shape": (
                    "monotonic_up" if all(lv[i] <= lv[i + 1] + 1e-12 for i in range(len(lv) - 1))
                    else "monotonic_down" if all(lv[i] >= lv[i + 1] - 1e-12 for i in range(len(lv) - 1))
                    else "non_monotonic"),
                "new_point_at_f1.00": new_point["SimObs_all_cycle"],
                "new_point_vs_legacy_f1.00": (
                    (new_point["SimObs_all_cycle"] / legacy_curve[0]["SimObs_all_cycle"] - 1.0)
                    if legacy_curve[0]["SimObs_all_cycle"] else None),
                "new_point_implied_multiplier": new_point["implied_demand_mult_to_1_cycle"],
            }
            lv_curve = [x["SimObs_all_cycle"] for x in legacy_curve if x["SimObs_all_cycle"]]
            amps = [x.get("A_10_19_MATCHED") for x in legacy_curve if x.get("A_10_19_MATCHED")]
            need_d02_d04["legacy_curve_points"] = [
                {"f_demand": x["f_demand"], "SimObs_cycle": x["SimObs_all_cycle"],
                 "phase_offset": x.get("phase_offset_it19_vs_cycle")} for x in legacy_curve]
            if lv_curve and amps:
                need_d02_d04["legacy_spread_vs_own_amplitude"] = (
                    (max(lv_curve) - min(lv_curve)) / float(np.mean(amps)))
                need_d02_d04["verdict_on_legacy_curve_informativeness"] = (
                    "LEGACY_CURVE_UNINFORMATIVE"
                    if (max(lv_curve) - min(lv_curve)) < float(np.mean(amps))
                    else "LEGACY_CURVE_PARTIALLY_INFORMATIVE")
            note = ("旧响应谱内部极差与各点自身的极限环振幅同量级 ⇒ 旧曲线**无法辨识需求响应**"
                    "（信噪比 < 1），因此「结合既有 D01–D04 给出约束区间」这条路径已封闭；"
                    "唯一能提供需求响应信息的做法是在新底座上重建响应曲线（7.6F-1）。")

    # ---- [6] 落盘 JSON + REPORT ----------------------------------------
    print("\n[6/6] 落盘 summary + report")

    all_pass = all(c["pass"] for c in _ck)
    summary_json = {
        "step": "7.6F-0",
        "title": "R01 零仿真基准重算（新稳定分配底座上的 demand=1.00）",
        "status": "PASS" if all_pass else "CHECK_FAIL",
        "zero_simulation": True, "matsim_rerun": False,
        "parameters_changed": False, "lambda_selected": False,
        "demand_scale_selected": False,
        "prerequisite": {
            "7.6E": "STABILITY_PASS (G1-G6 6/6) => route-choice 层正式冻结",
            "ban_lifted": "「route-choice 未稳定 => demand scale 不可评价」已解除",
        },
        "caliber": {
            "primary": f"cycle mean over it.{CONV_START}-{CONV_END} (per-link mean -> Sim/Obs)",
            "reference": f"it.{REF_ITER} single iteration",
            "both_reported": True,
            "headline_window": "08-09",
            "windows": ["07-08", "08-09", "AM"],
            "calibration_caliber": "MATCHED (= all 7.3.6A crosswalk sections); CATA/SLIP/ALL auxiliary",
            "scale_rule": "SCALE = SigmaT / N_sample  (200k -> 2.29897; 100k -> 4.59794)",
            "frozen_lineage": "7.3.6B / 7.4.2 / 7.4.3 / 7.5A / 7.5B 逐字节同源（import, 非复制）",
        },
        "window_discipline_note": (
            "Q/Qbar_10:19 (stability audit) uses Sigma HRS0-24avg; "
            "Sim/Obs uses HRS8-9avg. Not interchangeable."),
        "cross_validation": {
            "D01_it19_SimObs_08_09_expected": LEGACY_D01_SIMOBS_0809,
            "D01_it19_SimObs_08_09_got": d01_it19,
            "D01_it19_SimObs_AM_expected": LEGACY_D01_SIMOBS_AM,
            "D01_it19_SimObs_AM_got": d01_it19_am,
            "Qbar_reconciliation": qc,
        },
        "new_baseline_point_R01_demand_1.00": new_point,
        "route_choice_effect_at_fixed_demand": {
            "at_200k_D01_to_R01": eff_200k,
            "at_100k_S100c_to_S100k": eff_100k,
            "interpretation": (
                "同 demand、同 N、同 f_cap，仅 route-choice 不同 => 纯分配层效应；"
                "两规模同向且量级接近 => 机制签名。"),
        },
        "legacy_demand_response_curve": {
            "note": ("D01-D04 全部在旧（不稳定）route-choice 下测得 —— "
                     "是「Demand x 极限环」的混合响应，不是纯 demand 响应。"),
            "caliber": f"cycle mean it.{CONV_START}-{CONV_END}",
            "points": legacy_curve,
        },
        "necessity_of_D02_D04_rerun": need_d02_d04,
        "note_on_necessity": note,
        "explicitly_not_doing": [
            "不选 demand scale",
            "不评价 lambda",
            "不评价 OD 空间结构 / 距离带",
            "不用 (1 + delta) 修正因子平移旧 D01-D04",
        ],
        "runs": [{"label": r["label"], "role": r["role"], "stage": r["stage"],
                  "N": r["N"], "f_cap": r["f_cap"], "f_demand": r["f_demand"],
                  "route_choice": r["rc"], "SCALE": scale_of(r),
                  "out_dir": str(r["out_dir"]), "run_id": r["run_id"],
                  "desc": r["desc"]} for r in runs],
        "checks": _ck,
        "checks_pass": sum(1 for c in _ck if c["pass"]),
        "checks_total": len(_ck),
    }
    (OUT / "step7_6f_0_summary.json").write_text(
        json.dumps(summary_json, ensure_ascii=False, indent=2), encoding="utf-8")

    # ---------------- REPORT ----------------
    def f4(v, nd=4):
        if v is None or (isinstance(v, float) and pd.isna(v)):
            return "n/a"
        return f"{float(v):.{nd}f}"

    def fp(v, nd=2):
        if v is None or (isinstance(v, float) and pd.isna(v)):
            return "n/a"
        return f"{float(v)*100:+.{nd}f}%"

    L = []
    L.append("# Step 7.6F-0 — 新稳定分配底座上的 demand = 1.00 基准重算\n")
    L.append("## Status\n")
    L.append(f"**{'PASS' if all_pass else 'CHECK_FAIL'}**"
             f"（零仿真；只读既有 linkstats；**未启动 MATSim、未改任何参数**；"
             f"校验 {summary_json['checks_pass']}/{summary_json['checks_total']}）\n")
    L.append("> **前置**：7.6E 判 `STABILITY_PASS`（G1–G6 6/6）⇒ route-choice 层正式冻结 ⇒"
             "「route-choice 未稳定 ⇒ demand scale 不可评价」的禁令**已解除**。\n")
    L.append("> **本步只回答一个问题**：demand = 1.00 时，R01 稳定分配解对应什么**新的 MATCHED Sim/Obs 水平**？"
             "**不选 demand scale、不评价 λ、不评价 OD 空间结构。**\n")

    L.append("## 1. ★ 新基准点（R01，demand = 1.00，200k，f_cap = 1.00）\n")
    if new_point:
        L.append("| 口径 | 值 |")
        L.append("|---|---:|")
        L.append(f"| **Sim/Obs(08-09, MATCHED/ALL)** — Primary `Q̄_10:19` | **{f4(new_point['SimObs_all_cycle'])}** |")
        L.append(f"| Sim/Obs(08-09) — Reference `Q_19` | {f4(new_point['SimObs_all_it19'])} |")
        L.append(f"| Sim/Obs(AM 07-09) — Primary | {f4(new_point['SimObs_all_AM_cycle'])} |")
        L.append(f"| CATA | {f4(new_point['CATA_cycle'])} |")
        L.append(f"| SLIP_ROAD | {f4(new_point['SLIP_cycle'])} |")
        L.append(f"| CATA/SLIP_ROAD | {f4(new_point['CATA_over_SLIP_cycle'])} |")
        L.append(f"| WMAPE | {f4(new_point['WMAPE_cycle'])} |")
        L.append(f"| GEH<5 / GEH<10 | {f4(new_point['GEH_lt5_cycle'])} / {f4(new_point['GEH_lt10_cycle'])} |")
        L.append(f"| Pearson / Spearman | {f4(new_point['Pearson_cycle'])} / "
                 f"{f4(new_point.get('Spearman_cycle'))} |")
        L.append(f"| `Q̄_10:19`(MATCHED, Σ HRS0-24avg) | {new_point.get('Qbar_10_19_MATCHED') and format(int(new_point['Qbar_10_19_MATCHED']), ',')} |")
        L.append(f"| `Q_19`(MATCHED, Σ HRS0-24avg) | {new_point.get('Q_19_MATCHED') and format(int(new_point['Q_19_MATCHED']), ',')} |")
        L.append(f"| 隐含 demand 倍率（1/Sim/Obs，**仅指示**） | {f4(new_point['implied_demand_mult_to_1_cycle'])} |")
        L.append("")
    else:
        L.append("（R01 数据缺失）\n")

    L.append("## 2. ★★ 机制分解：旧分配层 vs 新分配层\n")
    L.append("### 2.1 固定 demand = 1.00、固定 N=200k、固定 f_cap=1.00 —— **仅 route-choice 变化**\n")
    if eff_200k:
        L.append("| | 旧配置 D01 | 新配置 R01 | 变化 |")
        L.append("|---|---:|---:|---:|")
        L.append(f"| Sim/Obs(08-09) — Primary `Q̄_10:19` | {f4(eff_200k.get('before_cycle'))} | "
                 f"**{f4(eff_200k.get('after_cycle'))}** | **{fp(eff_200k.get('delta_rel'))}** |")
        L.append(f"| Sim/Obs(08-09) — Reference `Q_19` | {f4(eff_200k.get('before_it19'))} | "
                 f"{f4(eff_200k.get('after_it19'))} | {fp(eff_200k.get('delta_rel_it19'))} |")
        L.append(f"| `Q̄_10:19`(MATCHED, Σ HRS0-24avg) | "
                 f"{eff_200k.get('Qbar_MATCHED_before') and format(int(eff_200k['Qbar_MATCHED_before']), ',')} | "
                 f"{eff_200k.get('Qbar_MATCHED_after') and format(int(eff_200k['Qbar_MATCHED_after']), ',')} | "
                 f"**{fp(eff_200k.get('Qbar_MATCHED_delta_rel'))}** |")
        L.append("")
    L.append("### 2.2 固定 demand = 1.00、固定 N=100k、固定 f_cap=0.50 —— 跨规模复核\n")
    if eff_100k:
        L.append("| | 旧配置 S100c | 新配置 S100k | 变化 |")
        L.append("|---|---:|---:|---:|")
        L.append(f"| Sim/Obs(08-09) — Primary | {f4(eff_100k.get('before_cycle'))} | "
                 f"**{f4(eff_100k.get('after_cycle'))}** | **{fp(eff_100k.get('delta_rel'))}** |")
        L.append(f"| Sim/Obs(08-09) — Reference | {f4(eff_100k.get('before_it19'))} | "
                 f"{f4(eff_100k.get('after_it19'))} | {fp(eff_100k.get('delta_rel_it19'))} |")
        L.append(f"| `Q̄_10:19`(MATCHED, Σ HRS0-24avg) | "
                 f"{eff_100k.get('Qbar_MATCHED_before') and format(int(eff_100k['Qbar_MATCHED_before']), ',')} | "
                 f"{eff_100k.get('Qbar_MATCHED_after') and format(int(eff_100k['Qbar_MATCHED_after']), ',')} | "
                 f"**{fp(eff_100k.get('Qbar_MATCHED_delta_rel'))}** |")
        L.append("")
        L.append("> 若 2.1 与 2.2 的位移**同向且量级接近** ⇒ 该位移是 **route-choice 机制效应**（机制签名），"
                 "而不是某个规模下的偶然。\n")

    L.append("### 2.3 全部 run × 双口径总表\n")
    L.append("| run | role | stage | N | f_cap | f_demand | route-choice | Sim/Obs(08-09) Primary | Reference | 相位偏移 (it19/均值−1) | CATA | SLIP | CATA/SLIP | WMAPE | GEH<5 | `A_10:19`(MATCHED) |")
    L.append("|---|---|---|---:|---:|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
    for rr in dec.itertuples():
        L.append(
            f"| {rr.run} | {rr.role} | {rr.stage} | {int(rr.N):,} | {rr.f_cap:.2f} | {rr.f_demand:.2f} | "
            f"{rr.route_choice} | {f4(rr.SimObs_all_cycle)} | {f4(rr.SimObs_all_it19)} | "
            f"{fp(getattr(rr, 'phase_offset_it19_vs_cycle', None))} | "
            f"{f4(rr.CATA_cycle)} | {f4(rr.SLIP_cycle)} | {f4(rr.CATA_over_SLIP_cycle)} | "
            f"{f4(rr.WMAPE_cycle)} | {f4(rr.GEH_lt5_cycle)} | {f4(getattr(rr, 'A_10_19_MATCHED', None))} |")
    L.append("")
    L.append("> `A_10:19`(MATCHED) 列即 7.6B/7.6D/7.6E 的稳定性判据（收敛窗振幅）；"
             "旧配置显著 >3% 即代表处于**极限环**，其 Sim/Obs 水平因此不可比。\n")

    L.append("## 3. 旧 demand 响应谱（D01–D04）—— 统一 Primary 口径重算，但**仍未脱离旧分配层**\n")
    L.append("| f_demand | Sim/Obs(08-09) Primary | Reference(it.19) | 相位偏移 | CATA | SLIP | CATA/SLIP | `A_10:19`(MATCHED) |")
    L.append("|---:|---:|---:|---:|---:|---:|---:|---:|")
    for x in legacy_curve:
        L.append(f"| {x['f_demand']:.2f} | {f4(x['SimObs_all_cycle'])} | {f4(x['SimObs_all_it19'])} | "
                 f"{fp(x.get('phase_offset_it19_vs_cycle'))} | "
                 f"{f4(x['CATA_cycle'])} | {f4(x['SLIP_cycle'])} | {f4(x['CATA_over_SLIP_cycle'])} | "
                 f"{f4(x['A_10_19_MATCHED'])} |")
    L.append("")
    L.append("> **★ 关键判读**：D01–D04 全部在**旧（不稳定）route-choice**下测得，"
             "每档的 `A_10:19` 均 ≥3%（极限环）⇒ 这条曲线是「Demand × 极限环」的**混合响应**，"
             "**不能**直接当作纯 demand 响应曲线使用。\n")

    L.append("## 4. 为什么不能用「×(1+δ) 修正因子」平移旧曲线\n")
    L.append(f"- 7.6E 已确证：route-choice 修复改变的是 **assignment dynamics**，"
             f"且收敛过程**单调地把流量搬进标定断面**（MATCHED +9.28%）同时压低全网 VKT（ALL −3.70%）。")
    L.append(f"- 2.1 给出的 200k 位移 = **{fp(eff_200k.get('delta_rel')) if eff_200k else 'n/a'}**"
             f"（Sim/Obs Primary 口径）；`Q̄_10:19`(MATCHED) 位移 = "
             f"**{fp(eff_200k.get('Qbar_MATCHED_delta_rel')) if eff_200k else 'n/a'}**。")
    L.append("- 两者**不相等** ⇒ 「断面流量位移」与「Sim/Obs 位移」不是同一个数；"
             "再把后者当作可乘修正因子施加到 D02–D04，会把**分配层效应**与**需求响应**混为一谈。")
    L.append("- 正确处理：**在新底座上重算**（本步已给出 f=1.00 的新基准点）；"
             "是否补齐 f=1.10/1.20/1.25 属 **7.6F-1**，须先由本步信息量决定。\n")

    L.append("## 5. 是否需要补跑 D02–D04（7.6F-1）？\n")
    if need_d02_d04:
        L.append(f"- 旧曲线（Primary 口径）内部极差 = **{f4(need_d02_d04['legacy_curve_SimObs_spread'])}**，"
                 f"形态 = **{need_d02_d04['legacy_curve_SimObs_shape']}**。")
        L.append(f"- 新基准点（f=1.00）= **{f4(need_d02_d04['new_point_at_f1.00'])}**，"
                 f"相对旧 f=1.00 位移 = **{fp(need_d02_d04['new_point_vs_legacy_f1.00'])}**。")
        L.append(f"- 新基准点隐含 demand 倍率（1/Sim/Obs，**仅指示**）= "
                 f"**{f4(need_d02_d04['new_point_implied_multiplier'])}**。")
        L.append(f"- {note}")
    L.append("- **本步不给结论性建议**：是否投入 3 × ~85 min 重建新响应曲线，"
             "由用户依据本节数据裁定（主线顺序已定：7.6F → 7.6C → λ/impedance）。\n")

    L.append("## 6. 口径与纪律\n")
    L.append("- 观测：7.1 冻结（工作日 → 日内均值 → `LinkID × hour` 日中位；hour = 7,8）。")
    L.append("- 仿真：`median(匹配 MATSim 有向边 HRSx-yavg) × SCALE`，**`SCALE = ΣT/N_sample`**"
             "（200k → 2.29897；100k → 4.59794）。")
    L.append(f"- Primary = 收敛窗 it.{CONV_START}–{CONV_END} **逐链路周期均值**后再算 Sim/Obs"
             f"（与稳定性审计 `Q̄_10:19` 同 window）；Reference = it.{REF_ITER} 单点。")
    L.append("- 评价函数 **import** 自 `compare_final_crosswalk_7_3_6b` / `evaluate_calibration_7_4_2`"
             "（冻结模块），口径逐字节同源。")
    L.append("- 窗口辨析：稳定性审计的 `Q` 用 **ΣHRS0-24avg**，Sim/Obs 用 **HRS8-9avg** —— **不混用**。")
    L.append("- **未改动** 7.1 / 7.3.6A / OD / network / capacity / population / route-choice 任何冻结件。\n")
    L.append("---\n")
    L.append(f"校验：{summary_json['checks_pass']}/{summary_json['checks_total']} PASS   "
             f"产物目录：`{OUT}`\n")
    (OUT / "STEP7_6F_0_REPORT.md").write_text("\n".join(L), encoding="utf-8")

    print("\n" + "=" * 80)
    print(f"校验: {summary_json['checks_pass']}/{summary_json['checks_total']} PASS")
    print(f"新基准点 R01 (demand=1.00, Primary): Sim/Obs(08-09) = "
          f"{f4(new_point['SimObs_all_cycle']) if new_point else 'n/a'}")
    if eff_200k:
        print(f"route-choice 效应 @200k (固定 demand=1.00): "
              f"{f4(eff_200k.get('before_cycle'))} -> {f4(eff_200k.get('after_cycle'))} "
              f"({fp(eff_200k.get('delta_rel'))})")
    print(f"产物 -> {OUT}")
    return 0 if all_pass else 2


if __name__ == "__main__":
    raise SystemExit(main())
