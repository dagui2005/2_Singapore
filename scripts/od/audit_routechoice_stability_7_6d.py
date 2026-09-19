#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""
audit_routechoice_stability_7_6d.py — Step 7.6D 稳定性评价（零仿真、只读）。

预注册判据（先于任何运行冻结，见 matsim_routechoice_7_6d/STEP7_6D_PREREGISTRATION.md）
-------------------------------------------------------------------------------
对每个量 X ∈ {ALL, MATCHED, CATA, SLIP} 与窗口 W，定义**周期振幅**：

        A_W(X) = ( max_{k in W} X_k − min_{k in W} X_k ) / mean_{k in W} X_k

主判据（收敛窗 W = it.10–19，MATCHED 口径）：

        A_10:19(MATCHED) < 3.0%          -> STABLE
        3.0% <= A < 10.0%                -> PARTIAL
        A >= 10.0%                       -> UNSTABLE

为什么用振幅而不是「it.19 水平」
--------------------------------
7.6B 已证明 D01–D04 处于**周期-2 极限环**：it.19 落在奇相位，被系统性抬高 +12.47%（f=1.20）。
故单迭代水平不可用于任何参数判决。振幅是「分配是否稳定」的直接度量，与相位选择无关。

双口径并报（用户 2026-09-16 裁定 ①）
------------------------------------
    Primary  : Q̄_10:19 = (1/10) Σ_{k=10..19} Q_k     （奇偶相位均衡周期均值）
    Reference: Q_19                                   （保留可追溯性，不丢弃）
两者**同时输出**，任何后续参数敏感性分析都以 Primary 为主、Reference 并报。

本脚本只读
----------
不启动 MATSim、不改任何参数。既评价基线（D01 = 7.4.2 E06）给出「修复前」振幅，
也评价 matsim_routechoice_7_6d/outputs/ 下的修复后 run（若已存在）。

用法
----
    python scripts/od/audit_routechoice_stability_7_6d.py
    python scripts/od/audit_routechoice_stability_7_6d.py --reuse
"""
from __future__ import annotations

import argparse
import io
import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(r"D:\Luan\2026-05\2_Singapore")
sys.path.insert(0, str(ROOT / "scripts" / "od"))

import compare_final_crosswalk_7_3_6b as bt      # noqa: E402  冻结观测 / crosswalk 口径

NEW_ROOT = ROOT / "matsim_routechoice_7_6d"
AUDIT_DIR = NEW_ROOT / "audit"
OUTPUTS = NEW_ROOT / "outputs"
CACHE = AUDIT_DIR / "routechoice_stability_by_iter.csv"

CW = ROOT / "reports" / "od_final_calibration_crosswalk_7_3_6" / "final_calibration_crosswalk.csv"
SCALE = bt.SCALE

CONV_START, CONV_END = 10, 19
PRECHECK_START, PRECHECK_END = 5, 9
WINDOWS = {
    "pre_05_09": (PRECHECK_START, PRECHECK_END),
    "conv_10_19": (CONV_START, CONV_END),
    "full_00_19": (0, 19),
}

# 预注册阈值（MATCHED 口径，收敛窗）
TH_STABLE, TH_PARTIAL = 0.030, 0.100

# ★ 7.6D-S 预注册门槛（低样本 100k 稳定性筛查，**按口径分别固定**）
#   见 matsim_routechoice_7_6d/STEP7_6D_S_PREREGISTRATION.md（先于运行冻结）
#   MATCHED < 3% / CATA < 3% / SLIP < 5%；ALL 仅报告；parity_gap_rel 仅辅助诊断。
TH_SCREEN_76DS = {"MATCHED": 0.030, "CATA": 0.030, "SLIP": 0.050}
SCREEN_RUN_PREFIX = "S100k"

# ★ 7.6E 预注册（200k 正式稳定化）—— 见 matsim_routechoice_7_6d/STEP7_6E_PREREGISTRATION.md
#   G1 单调收敛 / G2 收敛窗振幅 / G3 无周期结构 / G4 单点代表性 /
#   G5 无 agent 丢失 / G6 跨规模不恶化
TH_76E = {"MATCHED": 0.030, "CATA": 0.030, "SLIP": 0.050}
E76_TARGET_PREFIX = "R01"
E76_G3_PARITY = 0.010        # parity_gap_rel < 1%
E76_G4_Q19_TOL = 0.020       # |Q19/Qbar_10:19 - 1| < 2%
E76_G6_RATIO = 5.0           # A(200k)/A(100k) < 5
E76_G1_SIGN = 0.85           # sign_consistency(it.0->13) >= 0.85
E76_G1_TOL = 0.002           # 0.2% x Qbar 容差

# 7.6E 跨规模对照：100k 修复后
E76_AFTER_100K = {
    "label": "S100k_rc_min", "role": "after_100k",
    "out_dir": OUTPUTS / "S100k_rc_min", "run_id": "S100k_rc_min",
    "desc": "7.6D-S 100k 修复后（跨规模对照）",
}

# 7.6D-S 的「修复前」同 N 对照：S100c（100k, f_cap=0.50, FLOOR_PLUS_1, 旧 route-choice, 20 迭代已在盘）
SCREEN_BEFORE = {
    "label": "REF_S100c_N100k", "role": "before_s100k",
    "out_dir": ROOT / "reports" / "od_sample_7_5a" / "S100c_lam0p075_cap0p50",
    "run_id": "S100c",
    "desc": "7.5A S100c（N=100k, f_cap=0.50, FLOOR_PLUS_1, 旧 route-choice）",
}

# 修复前基线（= 7.4.3 / 7.6B 的 D01，λ=0.075, f=1.00, cap=1.00, 20 it）
BASELINE = {
    "label": "BASELINE_D01",
    "role": "before",
    "out_dir": ROOT / "reports" / "od_calibration_7_4_2" / "E06_lam0p075_cap1p00",
    "run_id": "E06",
    "desc": "7.4.2 E06（基线：ReRoute 1.0 / fractionOfIterationsToDisableInnovation=Infinity / learningRate=1.0）",
}

LINKSTAT_GLOB = "ITERS/it.{it}/{run_id}.*.linkstats.txt.gz"

# 「修复前」参照档（7.4.3 D 系列，零仿真复用；仅用于给出跨 demand 的 before 谱）
REF_RUNS = [
    {"label": "REF_D02_f1.10", "role": "before_ref",
     "out_dir": ROOT / "reports" / "od_calibration_7_4_3" / "D02_lam0p075", "run_id": "D02",
     "desc": "7.4.3 D02（f=1.10，修复前）"},
    {"label": "REF_D03_f1.20", "role": "before_ref",
     "out_dir": ROOT / "reports" / "od_calibration_7_4_3" / "D03_lam0p075", "run_id": "D03",
     "desc": "7.4.3 D03（f=1.20，修复前）"},
    {"label": "REF_D04_f1.25", "role": "before_ref",
     "out_dir": ROOT / "reports" / "od_calibration_7_4_3" / "D04_lam0p075", "run_id": "D04",
     "desc": "7.4.3 D04（f=1.25，修复前）"},
]

_ck_rows: list[dict] = []


def ck(name: str, ok: bool, detail: str = "") -> bool:
    _ck_rows.append({"check": name, "pass": bool(ok), "detail": str(detail)})
    print(f"   [{'PASS' if ok else 'FAIL'}] {name}  {detail}")
    return bool(ok)


# --------------------------------------------------------------------------
def load_matched_sets() -> dict[str, set[str]]:
    """从 7.3.6A Final Crosswalk 取 matched / CATA / SLIP 的 MATSim 链路集合。"""
    cw = pd.read_csv(CW, encoding="utf-8-sig")
    cw["matsim_link_id"] = cw["matsim_link_id"].astype(str).str.strip()
    cw["RoadCat"] = cw["RoadCat"].astype(str).str.strip()
    matched = set(cw["matsim_link_id"])
    cata = set(cw.loc[cw["RoadCat"] == "CATA", "matsim_link_id"])
    slip = set(cw.loc[cw["RoadCat"] == "SLIP_ROAD", "matsim_link_id"])
    return {"MATCHED": matched, "CATA": cata, "SLIP": slip}


def linkstats_path(out_dir: Path, it: int, run_id: str) -> Path | None:
    d = out_dir / "ITERS" / f"it.{it}"
    if not d.exists():
        return None
    hits = sorted(d.glob(f"{run_id}.*.linkstats.txt.gz"))
    return hits[0] if hits else None


def iter_quantities(path: Path, sets: dict[str, set[str]]) -> dict:
    """单个迭代的 4 个口径 Σ(HRS0-24avg)。"""
    df = pd.read_csv(path, sep="\t", compression="gzip",
                     usecols=["LINK", "HRS0-24avg"], low_memory=False)
    df["LINK"] = df["LINK"].astype(str).str.strip()
    df["HRS0-24avg"] = pd.to_numeric(df["HRS0-24avg"], errors="coerce").fillna(0.0)
    s = df.groupby("LINK")["HRS0-24avg"].sum()
    out = {"ALL": float(s.sum()), "n_links_all": int(len(s))}
    for key, ids in sets.items():
        out[key] = float(s.reindex(list(ids)).fillna(0.0).sum())
        out[f"n_links_{key}"] = int(len(ids))
    return out


def scan_run(label: str, role: str, out_dir: Path, run_id: str, desc: str,
             sets: dict[str, set[str]]) -> list[dict]:
    rows = []
    if not out_dir.exists():
        print(f"   [skip] {label}: 目录不存在 {out_dir}")
        return rows
    for it in range(0, 20):
        p = linkstats_path(out_dir, it, run_id)
        if p is None:
            continue
        q = iter_quantities(p, sets)
        q.update({"run": label, "role": role, "run_id": run_id,
                  "iteration": it, "parity": "odd" if it % 2 else "even",
                  "out_dir": str(out_dir), "desc": desc})
        rows.append(q)
    print(f"   [scan] {label}: {len(rows)} 个迭代 linkstats")
    return rows


# --------------------------------------------------------------------------
def amplitude(x: np.ndarray) -> float:
    x = np.asarray(x, dtype=float)
    mu = float(np.nanmean(x))
    if mu == 0 or not np.isfinite(mu):
        return float("nan")
    return float((np.nanmax(x) - np.nanmin(x)) / mu)


def decompose(per_iter: pd.DataFrame, run: str, metric: str) -> dict:
    """周期振幅 + 双口径（周期均值 vs it.19）+ 奇偶分解。"""
    d = per_iter[(per_iter["run"] == run) & (per_iter["iteration"].between(0, 19))]
    out = {"run": run, "metric": metric}
    for wname, (a, b) in WINDOWS.items():
        dd = d[d["iteration"].between(a, b)]
        x = dd[metric].to_numpy(dtype=float)
        out[f"A_{wname}"] = amplitude(x) if len(x) else np.nan
        out[f"n_{wname}"] = int(len(x))
    conv = d[d["iteration"].between(CONV_START, CONV_END)]
    x = conv[metric].to_numpy(dtype=float)
    ev = conv[conv["parity"] == "even"][metric].to_numpy(dtype=float)
    od = conv[conv["parity"] == "odd"][metric].to_numpy(dtype=float)
    mean_cycle = float(np.nanmean(x)) if len(x) else np.nan
    out["Q_conv_mean"] = mean_cycle
    out["Q_conv_even_mean"] = float(np.nanmean(ev)) if len(ev) else np.nan
    out["Q_conv_odd_mean"] = float(np.nanmean(od)) if len(od) else np.nan
    out["parity_gap_rel"] = (abs(out["Q_conv_even_mean"] - out["Q_conv_odd_mean"]) / mean_cycle
                             if mean_cycle else np.nan)
    it19 = d[d["iteration"] == 19][metric].to_numpy(dtype=float)
    out["Q_19"] = float(it19[0]) if len(it19) else np.nan
    out["Q_19_vs_cycle_pct"] = ((out["Q_19"] - mean_cycle) / mean_cycle * 100.0
                                if mean_cycle else np.nan)
    if len(x) >= 4:
        k = np.arange(len(x), dtype=float)
        sl = np.polyfit(k, x, 1)[0]
        out["slope_pct_per_iter"] = float(sl / mean_cycle * 100.0) if mean_cycle else np.nan
    else:
        out["slope_pct_per_iter"] = np.nan
    return out


def sign_consistency(series, qbar: float, tol: float = E76_G1_TOL) -> float:
    """it.0->it.13 单调性：连续差分 >= -tol*Qbar 的比例。完全单调上升 = 1.0。"""
    x = np.asarray(series, dtype=float)
    x = x[np.isfinite(x)][:14]
    if len(x) < 2 or not np.isfinite(qbar) or qbar == 0:
        return float("nan")
    d = np.diff(x)
    return float((d >= -tol * qbar).mean()) if len(d) else float("nan")


def read_leg_hist(out_dir: Path, run_id: str, it: int = 19):
    """从 it.N 的 legHistogram.txt 算 never_arrived / max_stuck_car
    （与 7.4.3 diagnose_demand_scale_nonmonotonic_7_4_3.py 同源同口径）。"""
    p = out_dir / "ITERS" / ("it.%d" % it) / ("%s.%d.legHistogram.txt" % (run_id, it))
    if not p.exists():
        return None
    with io.open(str(p), encoding="utf-8", errors="replace") as f:
        cols = f.readline().rstrip("\n").split("\t")
        rows = [ln.rstrip("\n").split("\t") for ln in f if ln.strip()]
    if "departures_car" not in cols or "arrivals_car" not in cols or "stuck_car" not in cols:
        return None
    i_d, i_a, i_s = cols.index("departures_car"), cols.index("arrivals_car"), cols.index("stuck_car")

    def _s(i):
        return sum(float(r[i]) for r in rows if len(r) > i and r[i] not in ("", "nan"))
    dep, arr = _s(i_d), _s(i_a)
    stk = max([float(r[i_s]) for r in rows if len(r) > i_s and r[i_s] not in ("", "nan")] or [0.0])
    return {"departures_car": dep, "arrivals_car": arr,
            "never_arrived": dep - arr, "max_stuck_car": stk}


def verdict_of(a_matched: float) -> str:
    if not np.isfinite(a_matched):
        return "NO_DATA"
    if a_matched < TH_STABLE:
        return "STABLE"
    if a_matched < TH_PARTIAL:
        return "PARTIAL"
    return "UNSTABLE"


# --------------------------------------------------------------------------
def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--reuse", action="store_true", help="复用逐迭代缓存")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--screening", action="store_true",
                    help="以 7.6D-S 预注册门槛（MATCHED/CATA<3%%, SLIP<5%%）判定，并纳入 S100c 同 N 对照；未达标返回码 2")
    ap.add_argument("--stability-7_6e", dest="stability_7_6e", action="store_true",
                    help="7.6E 200k 正式稳定化审计（G1..G6）；未达标返回码 2")
    ap.add_argument("--include-ref", action="store_true",
                    help="同时评价 D02/D03/D04（修复前参照档，跨 demand 的 before 谱）")
    args = ap.parse_args()
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    print("=" * 78)
    print("Step 7.6D — Route-choice stability audit（零仿真、只读）")
    print("=" * 78)

    sets = load_matched_sets()
    print(f"crosswalk: {CW.name}")
    print(f"  MATCHED = {len(sets['MATCHED']):,}  CATA = {len(sets['CATA']):,}  "
          f"SLIP = {len(sets['SLIP']):,}")
    print()

    ck("S0.1 crosswalk 命中链路 == 3,037", len(sets["MATCHED"]) == 3037, f"{len(sets['MATCHED']):,}")
    ck("S0.2 CATA + SLIP == MATCHED",
       sets["CATA"] | sets["SLIP"] == sets["MATCHED"]
       and not (sets["CATA"] & sets["SLIP"]),
       f"CATA={len(sets['CATA'])} SLIP={len(sets['SLIP'])}")

    # ---- 扫描（带缓存） ---------------------------------------------------
    runs = [BASELINE] + (REF_RUNS if args.include_ref else [])
    if args.screening:
        runs.append(SCREEN_BEFORE)
    if args.stability_7_6e:
        runs.append(E76_AFTER_100K)
    for d in sorted(OUTPUTS.glob("*")) if OUTPUTS.exists() else []:
        if not d.is_dir() or d.name.startswith("_"):
            continue
        rid = d.name
        runs.append({"label": rid, "role": "after", "out_dir": d, "run_id": rid,
                     "desc": "7.6D 最小 route-choice 修复后"})

    if args.reuse and CACHE.exists() and not args.force:
        cached = pd.read_csv(CACHE, encoding="utf-8-sig")
        have = set(cached["run"])
        rows = cached.to_dict("records")
        print(f"[reuse] 载入缓存 {CACHE.name}（{len(rows)} 行，runs={sorted(have)}）")
        missing = [r for r in runs if r["label"] not in have]
    else:
        rows = []
        missing = runs

    for spec in missing:
        rows.extend(scan_run(spec["label"], spec["role"], spec["out_dir"],
                             spec["run_id"], spec["desc"], sets))

    per_iter = pd.DataFrame(rows)
    if per_iter.empty:
        print("ERROR: 没有可用 linkstats")
        return 1
    per_iter = per_iter.sort_values(["run", "iteration"]).reset_index(drop=True)
    per_iter.to_csv(CACHE, index=False, encoding="utf-8-sig")

    _have = set(per_iter["run"])
    run_order, _seen = [], set()
    for r in runs:                      # 去重：同一 label 只保留首次出现（即显式对照优先）
        if r["label"] in _have and r["label"] not in _seen:
            _seen.add(r["label"])
            run_order.append(r["label"])
    ck("S1.1 基线 run 覆盖 it.0..19（20 份）",
       int((per_iter["run"] == BASELINE["label"]).sum()) == 20,
       f"{int((per_iter['run'] == BASELINE['label']).sum())} 份")

    # ---- 振幅分解 --------------------------------------------------------
    METRICS = ["ALL", "MATCHED", "CATA", "SLIP"]
    amp_rows = []
    for r in run_order:
        for m in METRICS:
            amp_rows.append(decompose(per_iter, r, m))
    amp = pd.DataFrame(amp_rows)
    amp.to_csv(AUDIT_DIR / "routechoice_stability_amplitude.csv",
               index=False, encoding="utf-8-sig")

    # ---- 修复前 / 后 对照 ------------------------------------------------
    print("\n=== 周期振幅 A(10:19) 对照 ===")
    hdr = f"{'run':<16}{'role':<12}" + "".join(f"{m:>12}" for m in METRICS)
    print(hdr)
    print("-" * len(hdr))
    for r in run_order:
        role = next((x["role"] for x in runs if x["label"] == r), "?")
        vals = []
        for m in METRICS:
            v = amp[(amp["run"] == r) & (amp["metric"] == m)]["A_conv_10_19"]
            vals.append(f"{(float(v.iloc[0])*100 if len(v) and np.isfinite(v.iloc[0]) else float('nan')):>11.2f}%")
        print(f"{r:<16}{role:<12}" + "".join(vals))

    # ---- 双口径 ----------------------------------------------------------
    dual = amp[amp["metric"] == "MATCHED"][
        ["run", "Q_conv_mean", "Q_19", "Q_19_vs_cycle_pct",
         "Q_conv_even_mean", "Q_conv_odd_mean", "parity_gap_rel",
         "A_pre_05_09", "A_conv_10_19", "A_full_00_19", "slope_pct_per_iter"]].copy()
    dual.to_csv(AUDIT_DIR / "routechoice_stability_dual_caliber.csv",
                index=False, encoding="utf-8-sig")

    # ---- 判决 ------------------------------------------------------------
    base_a = float(amp[(amp["run"] == BASELINE["label"]) & (amp["metric"] == "MATCHED")]
                   ["A_conv_10_19"].iloc[0])
    verdicts = {}
    for r in run_order:
        a = float(amp[(amp["run"] == r) & (amp["metric"] == "MATCHED")]["A_conv_10_19"].iloc[0])
        verdicts[r] = {"A_matched_conv": a, "verdict": verdict_of(a),
                       "role": next((x["role"] for x in runs if x["label"] == r), "?")}

    print("\n=== 判决（预注册：MATCHED A(10:19) < 3% = STABLE）===")
    for r in run_order:
        v = verdicts[r]
        print(f"  {r:<16} [{v['role']:<6}] A = {v['A_matched_conv']*100:6.2f}%  -> {v['verdict']}")

    afters = [r for r in run_order if verdicts[r]["role"] == "after"]
    if afters:
        best = min(afters, key=lambda r: verdicts[r]["A_matched_conv"])
        ba = verdicts[best]["A_matched_conv"]
        ck("S2.1 修复后 A(MATCHED,10:19) < 3%（预注册门槛）",
           ba < TH_STABLE, f"{best}: {ba*100:.2f}%")
        ck("S2.2 修复后振幅低于基线",
           ba < base_a, f"baseline {base_a*100:.2f}% -> {ba*100:.2f}%")
        final_verdict = verdicts[best]["verdict"]
        target_run = best
    else:
        print("\n  （修复后 run 尚未产出 —— 基线振幅已记录，作为预注册的 before 参照）")
        final_verdict = "AWAITING_R01"
        target_run = None

    # ---- ★ 7.6D-S 低样本（100k）稳定性筛查：按口径门槛 + 同 N 对照 ----------
    def _srow(r: str, role: str, is_target: bool) -> dict:
        row = {"run": r, "role": role, "is_target": is_target}
        ok_all = True
        for m, th in TH_SCREEN_76DS.items():
            a = float(amp[(amp["run"] == r) & (amp["metric"] == m)]["A_conv_10_19"].iloc[0])
            pg = float(amp[(amp["run"] == r) & (amp["metric"] == m)]["parity_gap_rel"].iloc[0])
            ok = bool(np.isfinite(a) and a < th)
            row[f"A_{m}"] = a
            row[f"threshold_{m}"] = th
            row[f"pass_{m}"] = ok
            row[f"parity_gap_{m}"] = pg
            ok_all = ok_all and ok
        row["A_ALL"] = float(amp[(amp["run"] == r) & (amp["metric"] == "ALL")]["A_conv_10_19"].iloc[0])
        row["parity_gap_ALL"] = float(amp[(amp["run"] == r) & (amp["metric"] == "ALL")]["parity_gap_rel"].iloc[0])
        row["Q_conv_mean_MATCHED"] = float(
            amp[(amp["run"] == r) & (amp["metric"] == "MATCHED")]["Q_conv_mean"].iloc[0])
        row["Q_19_MATCHED"] = float(
            amp[(amp["run"] == r) & (amp["metric"] == "MATCHED")]["Q_19"].iloc[0])
        row["verdict"] = (("SCREENING_PASS" if ok_all else "SCREENING_FAIL")
                          if is_target else "BEFORE_REFERENCE")
        return row

    screen_rows = []
    have = set(per_iter["run"])
    if args.screening and SCREEN_BEFORE["label"] in have:
        screen_rows.append(_srow(SCREEN_BEFORE["label"], SCREEN_BEFORE["role"], False))
    for r in run_order:
        if r.startswith(SCREEN_RUN_PREFIX):
            screen_rows.append(_srow(r, next((x["role"] for x in runs if x["label"] == r), "after"), True))

    targets = [r for r in screen_rows if r["is_target"]]
    screening_summary = {
        "criteria": TH_SCREEN_76DS,
        "runs": screen_rows,
        "any_run": bool(targets),
        "all_pass": bool(targets) and all(r["verdict"] == "SCREENING_PASS" for r in targets),
    }
    if screen_rows:
        pd.DataFrame(screen_rows).to_csv(
            AUDIT_DIR / "routechoice_stability_screening_7_6d_s.csv",
            index=False, encoding="utf-8-sig")
        print("\n=== ★ 7.6D-S 低样本(100k)稳定性筛查（预注册：MATCHED/CATA < 3%，SLIP < 5%）===")
        for row in screen_rows:
            print(f"  {row['run']:<20} [{row['role']}]")
            for m, th in TH_SCREEN_76DS.items():
                print(f"      {m:<8} A_10:19 = {row[f'A_{m}']*100:6.2f}%  (<{th*100:.0f}%)"
                      f"  [{'PASS' if row[f'pass_{m}'] else 'FAIL'}]"
                      f"   parity_gap = {row[f'parity_gap_{m}']*100:5.2f}%")
            print(f"      {'ALL':<8} A_10:19 = {row['A_ALL']*100:6.2f}%  (仅报告)"
                  f"   parity_gap = {row['parity_gap_ALL']*100:5.2f}%")
            print(f"      Q̄_10:19(MATCHED) = {row['Q_conv_mean_MATCHED']:>14,.0f}"
                  f"   Q_19 = {row['Q_19_MATCHED']:>14,.0f}")
            print(f"      -> {row['verdict']}")
        # 同 N 相对变化
        bef = next((r for r in screen_rows if r["role"] == "before_s100k"), None)
        aft = next((r for r in screen_rows if r["is_target"]), None)
        if bef and aft:
            print("\n  -- 同 N (100k) 相对变化（修复前 S100c -> 修复后）--")
            for m in ("MATCHED", "CATA", "SLIP", "ALL"):
                b, a = bef.get(f"A_{m}"), aft.get(f"A_{m}")
                if b and np.isfinite(a):
                    print(f"     {m:<8} {b*100:6.2f}% -> {a*100:6.2f}%   "
                          f"(x{a/b:.2f})" if b else "")
    else:
        print(f"\n  （未发现以 '{SCREEN_RUN_PREFIX}' 开头的 run —— 7.6D-S 筛查尚未运行）")

    # ---- ★★ 7.6E：200k 正式稳定化审计（G1..G6）-------------------------
    e76_block = {}
    e76_rc = None
    if args.stability_7_6e:
        tgt = [r for r in run_order if r.startswith(E76_TARGET_PREFIX)]
        if not tgt:
            print("\n=== ★ 7.6E 200k 正式稳定化审计 ===")
            print("  （未发现 run_id 以 '%s' 开头的 run —— 7.6E 尚未运行）"
                  % E76_TARGET_PREFIX)
            e76_rc = 3
        else:
            tr = tgt[0]
            a = amp[amp["run"] == tr].set_index("metric")
            b = amp[amp["run"] == BASELINE["label"]].set_index("metric")
            h100 = (amp[amp["run"] == E76_AFTER_100K["label"]].set_index("metric")
                    if E76_AFTER_100K["label"] in set(per_iter["run"]) else None)

            def _f(df, m, col):
                try:
                    return float(df.loc[m, col])
                except Exception:
                    return float("nan")

            lh = read_leg_hist(OUTPUTS / tr, tr, 19)
            if lh is None:
                lh = read_leg_hist(OUTPUTS / tr, next(
                    (x["run_id"] for x in runs if x["label"] == tr), tr), 19)
            trace = per_iter[per_iter["run"] == tr]
            trace = trace.sort_values("iteration")

            by_iter = trace[["run", "role", "iteration", "parity",
                             "ALL", "MATCHED", "CATA", "SLIP"]].copy()
            qbar_m = _f(a, "MATCHED", "Q_conv_mean")
            sc = sign_consistency(trace["MATCHED"].to_numpy(dtype=float), qbar_m)

            # G1..G6
            A = {m: _f(a, m, "A_conv_10_19") for m in METRICS}
            PG = {m: _f(a, m, "parity_gap_rel") for m in METRICS}
            Ab = {m: _f(b, m, "A_conv_10_19") for m in METRICS}
            q19 = _f(a, "MATCHED", "Q_19")
            q19_ratio = (q19 / qbar_m) if qbar_m else float("nan")
            a100 = _f(h100, "MATCHED", "A_conv_10_19") if h100 is not None else float("nan")
            ratio_scale = (A["MATCHED"] / a100) if (a100 and np.isfinite(a100) and a100 > 0) else float("nan")

            G = {
                "G1_monotone_convergence": bool(np.isfinite(sc) and sc >= E76_G1_SIGN),
                "G2_conv_amplitude": bool(
                    np.isfinite(A["MATCHED"]) and A["MATCHED"] < TH_76E["MATCHED"]
                    and np.isfinite(A["CATA"]) and A["CATA"] < TH_76E["CATA"]
                    and np.isfinite(A["SLIP"]) and A["SLIP"] < TH_76E["SLIP"]),
                "G3_no_periodic_structure": bool(all(
                    np.isfinite(PG[m]) and PG[m] < E76_G3_PARITY for m in TH_76E)),
                "G4_Q19_representativeness": bool(
                    np.isfinite(q19_ratio) and abs(q19_ratio - 1.0) < E76_G4_Q19_TOL),
                "G5_no_agent_loss": bool(
                    lh is not None and lh["never_arrived"] == 0 and lh["max_stuck_car"] == 0),
                "G6_cross_scale_not_worse": bool(
                    not np.isfinite(ratio_scale) or (A["MATCHED"] < TH_76E["MATCHED"]
                                                     and ratio_scale < E76_G6_RATIO)),
            }
            all_pass = all(G.values())
            e76_rc = 0 if all_pass else 2

            print("\n=== ★ 7.6E 200k 正式稳定化审计（第一关 = 稳定性，非拟合）===")
            print("  target run = %s   (200k x 20 it, f_cap=1.00)" % tr)
            print("  -- 四口径 A_10:19：修复前(200k D01) -> 修复后(200k %s) --" % tr)
            for m in METRICS:
                mark = " (仅报告)" if m == "ALL" else ""
                print("     %-8s %6.2f%% -> %6.2f%%   parity_gap %5.2f%% -> %5.2f%%%s"
                      % (m, Ab[m] * 100, A[m] * 100, PG[m] * 100, PG[m] * 100, mark))
            print("  -- 双口径 --")
            print("     Qbar_10:19(MATCHED) = %14s   Q_19 = %14s   Q19/Qbar = %.4f"
                  % ("{:,}".format(int(qbar_m)), "{:,}".format(int(q19)), q19_ratio))
            print("     A_full_00_19(MATCHED) = %.2f%%  ← 仅报告（含 burn-in 瞬态）"
                  % (_f(a, "MATCHED", "A_full_00_19") * 100))
            print("  -- 单调性 --")
            print("     sign_consistency(it.0->13, MATCHED) = %.3f  (阈值 >= %.2f)" % (sc, E76_G1_SIGN))
            print("  -- 无 agent 丢失 (it.19 legHistogram) --")
            if lh is None:
                print("     legHistogram 缺失 -> G5 FAIL")
            else:
                print("     departures=%s arrivals=%s never_arrived=%s max_stuck=%s"
                      % ("{:,.0f}".format(lh["departures_car"]), "{:,.0f}".format(lh["arrivals_car"]),
                         "{:,.0f}".format(lh["never_arrived"]), "{:,.0f}".format(lh["max_stuck_car"])))
            if np.isfinite(ratio_scale):
                print("  -- 跨规模 --  A(200k)/A(100k) = %.2f  (阈值 < %.1f)" % (ratio_scale, E76_G6_RATIO))
            print("  -- 逐迭代轨迹 (MATCHED, 归一化到 Qbar_10:19) --")
            for _, r in trace.iterrows():
                print("     it.%02d  %s  %s" % (int(r["iteration"]), r["parity"][:4],
                                                " ".join("%8.4f" % (float(r[m]) / qbar_m) for m in METRICS)))
            print("  -- G1..G6 --")
            for k, v in G.items():
                print("     [%s] %s" % ("PASS" if v else "FAIL", k))
            print("  => %s" % ("STABILITY_PASS -> route-choice 层可正式冻结"
                               if all_pass else
                               "STABILITY_FAIL -> 暂停，不进入 7.6F / 7.6C"))

            pd.DataFrame([{ "run": tr, "A_MATCHED": A["MATCHED"], "A_CATA": A["CATA"],
                            "A_SLIP": A["SLIP"], "A_ALL": A["ALL"],
                            "parity_gap_MATCHED": PG["MATCHED"], "parity_gap_CATA": PG["CATA"],
                            "parity_gap_SLIP": PG["SLIP"], "parity_gap_ALL": PG["ALL"],
                            "Q_conv_mean_MATCHED": qbar_m, "Q_19_MATCHED": q19,
                            "Q19_over_Qbar_MATCHED": q19_ratio,
                            "A_full_00_19_MATCHED": _f(a, "MATCHED", "A_full_00_19"),
                            "sign_consistency_MATCHED": sc,
                            "never_arrived": (lh["never_arrived"] if lh else None),
                            "max_stuck_car": (lh["max_stuck_car"] if lh else None),
                            "A_MATCHED_before_200k": Ab["MATCHED"],
                            "A_MATCHED_after_100k": a100,
                            "ratio_200k_over_100k": ratio_scale,
                            "verdict": ("STABILITY_PASS" if all_pass else "STABILITY_FAIL")}]
                        ).to_csv(AUDIT_DIR / "routechoice_stability_7_6e.csv",
                                 index=False, encoding="utf-8-sig")
            by_iter.to_csv(AUDIT_DIR / "routechoice_stability_7_6e_by_iter.csv",
                           index=False, encoding="utf-8-sig")
            e76_block = {
                "preregistered_thresholds": TH_76E,
                "target_prefix": E76_TARGET_PREFIX,
                "criteria": {
                    "G1_sign_consistency_ge": E76_G1_SIGN,
                    "G2_A_MATCHED_CATA_lt": TH_76E["MATCHED"], "G2_A_SLIP_lt": TH_76E["SLIP"],
                    "G3_parity_gap_lt": E76_G3_PARITY,
                    "G4_abs_Q19_over_Qbar_minus_1_lt": E76_G4_Q19_TOL,
                    "G5_never_arrived_eq_0_and_max_stuck_eq_0": True,
                    "G6_A_ratio_200k_over_100k_lt": E76_G6_RATIO,
                },
                "statistic_discipline": {
                    "formal_criterion": "A_10:19 = (max-min)/mean over it.10-19",
                    "auxiliary_diagnostic": "parity_gap_rel = |even-odd|/mean",
                    "reported_only_not_criterion": "A_full_00_19 (contains burn-in transient)",
                },
                "target_run": tr,
                "A_10_19": A, "A_10_19_before_200k": Ab, "parity_gap_rel": PG,
                "Q_conv_mean_MATCHED": qbar_m, "Q_19_MATCHED": q19,
                "Q19_over_Qbar_MATCHED": q19_ratio,
                "sign_consistency_MATCHED": sc,
                "leg_hist_it19": lh,
                "A_MATCHED_after_100k": a100, "ratio_200k_over_100k": ratio_scale,
                "gates": G, "all_pass": bool(all_pass),
                "verdict": ("STABILITY_PASS" if all_pass else "STABILITY_FAIL"),
            }

    summary = {
        "step": "7.6D",
        "title": "Route-choice stabilization — stability audit",
        "zero_simulation": True,
        "matsim_rerun": False,
        "crosswalk": str(CW),
        "n_matched": len(sets["MATCHED"]),
        "n_cata": len(sets["CATA"]),
        "n_slip": len(sets["SLIP"]),
        "criteria": {
            "A_window": "it.10-19",
            "A_definition": "(max - min) / mean",
            "STABLE_lt": TH_STABLE, "PARTIAL_lt": TH_PARTIAL,
            "primary_caliber": "cycle_mean over it.10-19 (parity-balanced)",
            "reference_caliber": "it.19 single iteration",
        },
        "runs": {r: {"role": next((x["role"] for x in runs if x["label"] == r), "?"),
                     "description": next((x["desc"] for x in runs if x["label"] == r), "")}
                 for r in run_order},
        "amplitude_10_19": {
            r: {m: float(amp[(amp["run"] == r) & (amp["metric"] == m)]["A_conv_10_19"].iloc[0])
                for m in METRICS} for r in run_order},
        "verdicts": verdicts,
        "final_verdict": final_verdict,
        "target_run": target_run,
        "screening_7_6d_s": {
            "preregistered_thresholds": TH_SCREEN_76DS,
            "screen_run_prefix": SCREEN_RUN_PREFIX,
            "before_run": {k: str(v) for k, v in SCREEN_BEFORE.items()},
            "statistic_discipline": {
                "formal_criterion": "A_10:19 = (max-min)/mean over it.10-19",
                "auxiliary_diagnostic": "parity_gap_rel = |even-odd|/mean",
                "note": "两者不得统称为「周期振幅」",
            },
            "runs": screening_summary["runs"],
            "any_run": screening_summary["any_run"],
            "all_pass": screening_summary["all_pass"],
        },
        "stability_7_6e": e76_block,
        "checks": _ck_rows,
        "checks_pass": sum(1 for c in _ck_rows if c["pass"]),
        "checks_total": len(_ck_rows),
    }
    (AUDIT_DIR / "routechoice_stability_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    npass = summary["checks_pass"]
    print(f"\n校验: {npass}/{summary['checks_total']} PASS")
    print(f"产物 -> {AUDIT_DIR}")

    if args.stability_7_6e:
        print("7.6E \u5ba1\u8ba1: " + ("NO_RUN" if e76_rc == 3 else (
            "STABILITY_PASS -> route-choice \u5c42\u53ef\u6b63\u5f0f\u51bb\u7ed3" if e76_rc == 0 else
            "STABILITY_FAIL -> \u6682\u505c\uff0c\u4e0d\u8fdb\u5165 7.6F / 7.6C")))
        return e76_rc if e76_rc is not None else 3
    if args.screening:
        if not screening_summary["any_run"]:
            print("7.6D-S 筛查: NO_RUN")
            return 3
        if screening_summary["all_pass"]:
            print("7.6D-S 筛查: SCREENING_PASS -> 可进入 200k x 20 it 正式稳定化")
            return 0
        print("7.6D-S 筛查: SCREENING_FAIL -> 暂停，不消耗 200k 算力，继续修 route-choice")
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
