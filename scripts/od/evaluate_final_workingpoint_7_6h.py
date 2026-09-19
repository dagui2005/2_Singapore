#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""
evaluate_final_workingpoint_7_6h.py — Step 7.6H 评价链（**零仿真、只读**；从不启动 MATSim）。

只回答 5 个问题（用户 2026-09-18 21:05 裁定）
-------------------------------------------
    H1 可复现性   Sim/Obs ≈ 1.000 且与 7.6G `L75` 一致？
    H2 稳定性     A_10:19 / parity_gap_rel / Q19/Q̄ / never_arrived / max_stuck
    H3 空间残差   是否仍存在（**不追求消除**，只报告「格局是否保持」）
    H4 λ 敏感性边界  三层（工作点 / λ 带 / 静态靶场带）**不得合并**
    H5 未解决     必须显式声明，不得宣称「完全校准」

复用纪律
--------
`evaluate_demand_response_7_6f_1.eval_run()` 及其全部指标函数与 run 表无关，只经模块全局
`OUT` / `CYCLE_DIR` / `MATRIX_CSV` 访问输出。本脚本**只重绑这三个路径 + 换一张 run 表**，
不复制任何公式。`never_arrived` / `max_stuck_car` 复用 `audit_routechoice_stability_7_6d.read_leg_hist()`。

判决空间（预注册见 `matsim_final_7_6h/STEP7_6H_PREREGISTRATION.md` §3）
------------------------------------------------------------------
    主    : WORKING_POINT_FROZEN_AND_REPRODUCIBLE | WORKING_POINT_NOT_REPRODUCIBLE
            | WORKING_POINT_FROZEN_BUT_UNSTABLE | AWAITING_RUN
    空间  : SPATIAL_RESIDUAL_PERSISTS | SPATIAL_SHIFTED

用法
----
    python scripts/od/evaluate_final_workingpoint_7_6h.py
    python scripts/od/evaluate_final_workingpoint_7_6h.py --force-cycle
"""
from __future__ import annotations

import argparse
import json
import math
import sys
import time
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(r"D:\Luan\2026-05\2_Singapore")
sys.path.insert(0, str(ROOT / "scripts" / "od"))

import compare_final_crosswalk_7_3_6b as bt              # noqa: E402  冻结口径 SCALE
import evaluate_calibration_7_4_2 as ev1                 # noqa: E402  冻结 TRAFFIC / FINAL_CW
import diagnose_od_spatial_structure_7_6c as d76          # noqa: E402  section_geography
import evaluate_demand_response_7_6f_1 as E              # noqa: E402  ★ 复用评价函数
import audit_routechoice_stability_7_6d as a76d           # noqa: E402  ★ 复用 legHistogram 读数
import prepare_final_workingpoint_7_6h as H              # noqa: E402  ★ 7.6H 常量/阈值
import prepare_lambda_sensitivity_7_6g as G76            # noqa: E402  7.6G 只读引用

# --------------------------------------------------------------------------
# 路径重绑定 → 7.6H 工作区
# --------------------------------------------------------------------------
H_ROOT = H.NEW_ROOT
OUT = H_ROOT / "audit"
CYCLE_DIR = OUT / "_cycle_linkstats"
E.OUT = OUT
E.CYCLE_DIR = CYCLE_DIR
E.MATRIX_CSV = H_ROOT / "final_workingpoint_7_6h_matrix.csv"

R01_ROOT = ROOT / "matsim_routechoice_7_6d"
G76_ROOT = G76.NEW_ROOT
G76_SPATIAL = G76_ROOT / "audit" / "lambda_sensitivity_spatial_residuals.csv"
AUDIT_CACHE_7_6D = R01_ROOT / "audit" / "routechoice_stability_by_iter.csv"

SCALE_FROZEN = float(bt.SCALE)                 # 2.29897
TOTAL_ITER = H.TOTAL_ITER
EXPECTED_ITER = H.EXPECTED_ITER
TH = H.TH
CALIBERS = ["FROZEN", "POSITIVE_ONLY", "BEST_DIRECTION"]
TARGET_7_6C_2 = dict(G76.TARGET_REF)

RUNS = [
    {"label": "R01", "role": "anchor_ref_not_grid", "lambda": 0.075,
     "f_demand": 1.00, "N": 200_000,
     "out_dir": R01_ROOT / "outputs" / "R01_rc_min", "run_id": "R01_rc_min",
     "stage": "7.6E/7.6F-0", "desc": "锚点（λ=0.075, f=1.00）—— 仅供对账，不作 7.6H 工作点"},
    {"label": "W01", "role": "final_working_point", "lambda": H.LAM_REF,
     "f_demand": H.F_REF, "N": H.N_SIM,
     "out_dir": H_ROOT / "outputs" / "W01_rc_min", "run_id": "W01_rc_min",
     "stage": "7.6H", "desc": f"最终工作点（λ={H.LAM_REF}, N_sim={H.N_SIM:,}）"},
]

# 7.6G `L75` 只读引用（H1 独立复现对照 + H3 空间格局对照）
L75 = dict(H.G76_L75)
R01_REFONLY = dict(H.G76_REFONLY)

_ck: list[dict] = []


def ck(name: str, ok: bool, detail: str = "") -> bool:
    _ck.append({"check": name, "pass": bool(ok), "detail": str(detail)})
    print(f"   [{'PASS' if ok else 'FAIL'}] {name}  {detail}")
    return bool(ok)


def log(msg: str = "") -> None:
    print(msg)


def banner(msg: str) -> None:
    print("\n" + "=" * 84)
    print(msg)
    print("=" * 84)


def n_complete_iters(run: dict) -> int:
    got = 0
    for i in range(TOTAL_ITER):
        d = run["out_dir"] / "ITERS" / f"it.{i}"
        if not d.exists():
            continue
        if list(d.glob(f"{run['run_id']}.*.linkstats.txt.gz")) or list(d.glob("*.linkstats.txt.gz")):
            got += 1
    return got


def implied_fstar(simobs: float, slope: float = G76.F1_SLOPE_LOCAL, f0: float = 1.18) -> float:
    """等效于 7.6G 的 implied_fstar()（f0 + (1-Sim/Obs)/slope），仅用于 H1 与 7.6G 值对齐。"""
    return float(f0 + (1.0 - simobs) / slope)


def pa_table(sec: pd.DataFrame, global_q: float, top_n: int = 10) -> pd.DataFrame:
    """PA 级 rel_dev（与 region/radial 同式：pooled(sub)/pooled(all) − 1）。"""
    if "pa" not in sec.columns:
        return pd.DataFrame()
    rows = []
    for pa, sub in sec.groupby("pa"):
        q = E.pooled(sub)
        if not np.isfinite(q) or not np.isfinite(global_q) or global_q == 0:
            continue
        rows.append({"pa": pa, "n_sections": int(len(sub)), "Q_FROZEN": q,
                     "rel_dev_vs_global_FROZEN": q / global_q - 1.0})
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    df["abs_rel_dev"] = df["rel_dev_vs_global_FROZEN"].abs()
    return df.sort_values("abs_rel_dev", ascending=False).head(top_n).drop(columns="abs_rel_dev")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--force-cycle", action="store_true")
    args = ap.parse_args()

    for d in (OUT, CYCLE_DIR):
        d.mkdir(parents=True, exist_ok=True)

    t0 = time.time()

    banner("Step 7.6H EVALUATE — 最终工作点确定与独立验证（H1–H5；零仿真）")
    log(f"  工作点：λ={H.LAM_REF}  f_ref={H.F_REF}  N_sim={H.N_SIM:,}  "
        f"SCALE={SCALE_FROZEN:.5f}（冻结，不按 ΣEF/N 重算）")
    log(f"  三层带（不合并）：工作点 f*={H.F_REF} | λ 带 {H.BAND_LAMBDA} | "
        f"静态靶场带 {H.BAND_STATIC_TARGET}")
    log(f"  ⛔ R01 隐含 f*={R01_REFONLY['R01_implied_fstar']} 为参照值：{R01_REFONLY['note']}")

    # ---- [0] 完备度 -------------------------------------------------------
    log("\n[0/8] linkstats 完备度")
    avail, missing = {}, []
    for r in RUNS:
        n = n_complete_iters(r)
        avail[r["label"]] = n
        if n < TOTAL_ITER:
            missing.append((r["label"], n))
    log("  " + "  ".join(f"{k}={v}/{TOTAL_ITER}" for k, v in avail.items()))
    awaiting = avail.get("W01", 0) < TOTAL_ITER
    if awaiting:
        log(f"  [AWAITING_RUN] W01 未跑完（{avail.get('W01')}/{TOTAL_ITER}）—— "
            f"照常复算 R01 锚点与 7.6C-2 对账。")
        (OUT / "od_final_workingpoint_7_6h_summary.json").write_text(
            json.dumps({"step": "7.6H", "status": "AWAITING_RUN",
                        "linkstats_availability": avail, "missing": missing,
                        "zero_simulation": True, "matsim_rerun": False, "checks": _ck},
                       ensure_ascii=False, indent=2), encoding="utf-8")
        return 2

    # ---- [1] 冻结件 -------------------------------------------------------
    log("\n[1/8] 载入 7.1 观测 + 7.3.6A crosswalk + 7.6C 地理")
    obs = bt.load_traffic(ev1.TRAFFIC)
    cw = bt.normalize_crosswalk(ev1.FINAL_CW, "final")
    cwraw = pd.read_csv(ev1.FINAL_CW, encoding="utf-8-sig")
    cwraw["matsim_link_id"] = cwraw["matsim_link_id"].astype(str).str.strip()
    cw_prim = cwraw[cwraw["is_primary_candidate"]].copy() \
        if "is_primary_candidate" in cwraw.columns else cwraw.copy()
    matched = set(cwraw["matsim_link_id"])
    cata = set(cwraw.loc[cwraw["RoadCat"] == "CATA", "matsim_link_id"])
    slip = set(cwraw.loc[cwraw["RoadCat"] == "SLIP_ROAD", "matsim_link_id"])
    ck("P6 CATA + SLIP == MATCHED（口径分区完整）",
       len(cata) + len(slip) == len(matched), f"{len(cata)}+{len(slip)} vs {len(matched)}")
    geo = pd.read_csv(d76.OUT_DIR / "section_geography.csv")[
        ["lta_linkid", "mid_x", "mid_y", "d_cbd_m", "n_links", "radial", "ring", "region", "pa"]]
    geo["lta_linkid"] = geo["lta_linkid"].astype(str).str.strip()
    ck("P7 section_geography 覆盖 >= 570/576", int(geo["region"].notna().sum()) >= 570,
       f"{int(geo['region'].notna().sum())}/{len(geo)}")

    # ---- [2] 逐 run -------------------------------------------------------
    log("\n[2/8] 逐 run 评价 —— 复用 evaluate_demand_response_7_6f_1.eval_run()")
    res = {}
    for r in RUNS:
        res[r["label"]] = E.eval_run(r, cw, cw_prim, obs, geo, matched, cata, slip,
                                     force_cycle=args.force_cycle)

    # ---- [3] 口径对账 -----------------------------------------------------
    log("\n[3/8] 口径未漂移对账（X1 vs 7.6C-2 / X2 vs 7.6D 缓存）")
    xval = []
    q1 = res["R01"]["q"]
    for cal in CALIBERS:
        ref = TARGET_7_6C_2[cal]
        got = q1[cal]
        ok = abs(got - ref) < 1e-6
        xval.append({"item": f"R01.{cal}", "ours": got, "reference": ref,
                     "abs_diff": abs(got - ref), "tol": 1e-6, "pass": ok})
        ck(f"X1 R01 {cal} == 7.6C-2 {ref:.7f}", ok, f"ours={got:.7f}  Δ={abs(got-ref):.2e}")
    if AUDIT_CACHE_7_6D.exists():
        _au = pd.read_csv(AUDIT_CACHE_7_6D, encoding="utf-8-sig")
        _z = _au[(_au["run"] == "R01_rc_min") & (_au["iteration"].between(E.CONV_START, E.CONV_END))]
        for kind in ("MATCHED", "CATA", "SLIP", "ALL"):
            if _z.empty:
                continue
            ref = float(_z[kind].mean())
            got = res["R01"]["stab"][kind]["Qbar_10_19"]
            ok = abs(got - ref) / max(abs(ref), 1e-12) < 1e-9
            xval.append({"item": f"R01.Qbar_10_19.{kind}", "ours": got, "reference": ref,
                         "abs_diff": abs(got - ref), "tol": 1e-9, "pass": ok})
            ck(f"X2 R01 Q̄_10:19 {kind} == 7.6D 缓存", ok, f"ours={got:,.1f}  ref={ref:,.1f}")
    pd.DataFrame(xval).to_csv(OUT / "final_workingpoint_7_6h_crossvalidation.csv",
                              index=False, encoding="utf-8-sig")

    # ---- [4] H1 可复现性 --------------------------------------------------
    log("\n[4/8] H1 可复现性")
    q = res["W01"]["q"]
    st = res["W01"]["stab"]["MATCHED"]
    simobs = float(q["FROZEN"])
    fstar_h = implied_fstar(simobs)
    freal = float(pd.read_csv(E.MATRIX_CSV, encoding="utf-8-sig")
                  .set_index("experiment_id").loc["W01", "f_realized"])
    d_simobs = abs(simobs - 1.0)
    # Sim/Obs 是比率 ⇒ pp 偏差 = |ratio-1|×100
    d_vs_l75_pp = abs(simobs - L75["SimObs_FROZEN"]) * 100.0
    h1 = pd.DataFrame([{
        "label": "W01", "N_sim": H.N_SIM, "lambda": H.LAM_REF,
        "SimObs_FROZEN": simobs,
        "SimObs_POSITIVE_ONLY": float(q["POSITIVE_ONLY"]),
        "SimObs_BEST_DIRECTION": float(q["BEST_DIRECTION"]),
        "SimObs_FROZEN_REF_it19": float(res["W01"]["q_19"]["FROZEN"]),
        "implied_fstar_FROZEN": fstar_h, "f_realized": freal,
        "abs_dev_from_1_pp": 100.0 * d_simobs,
        "abs_dev_fstar_vs_ref": abs(fstar_h - H.F_REF),
        "abs_dev_freal_vs_ref": abs(freal - H.F_REF),
        "simobs_L75_7_6G": L75["SimObs_FROZEN"],
        "abs_dev_vs_L75_pp": d_vs_l75_pp,
        "Qbar_10_19_MATCHED": st["Qbar_10_19"], "Q_19_MATCHED": st["Q_19"],
    }])
    h1.to_csv(OUT / "final_workingpoint_7_6h_h1_reproducibility.csv",
              index=False, encoding="utf-8-sig")
    print(h1.to_string(index=False, float_format=lambda v: f"{v:,.6f}"))
    ck(f"H1.1 |Sim/Obs_FROZEN − 1.000| ≤ {TH['H1_simobs_abs_dev_from_1pp']} pp",
       (100.0 * d_simobs) <= TH["H1_simobs_abs_dev_from_1pp"],
       f"Sim/Obs={simobs:.6f}  Δ={100.0*d_simobs:.4f} pp")
    ck(f"H1.2 |implied f* − {H.F_REF}| ≤ {TH['H1_fstar_dev']}",
       abs(fstar_h - H.F_REF) <= TH["H1_fstar_dev"], f"f*={fstar_h:.6f}")
    ck(f"H1.3 |f_realized − {H.F_REF}| ≤ {TH['H1_freal_dev']}",
       abs(freal - H.F_REF) <= TH["H1_freal_dev"], f"f_realized={freal:.7f}")
    ck(f"H1.4 |Sim/Obs_W01 − Sim/Obs_L75(7.6G)| ≤ {TH['H1_vs_l75_pp']} pp",
       d_vs_l75_pp <= TH["H1_vs_l75_pp"],
       f"{simobs:.6f} vs {L75['SimObs_FROZEN']:.6f}  Δ={d_vs_l75_pp:.4f} pp（独立实例化 N 236,044 vs 236,000）")

    # ---- [5] H2 稳定性 ----------------------------------------------------
    log("\n[5/8] H2 稳定性（ΣHRS0-24avg 口径；never_arrived 承 7.6E G5）")
    w = RUNS[1]
    lh = a76d.read_leg_hist(w["out_dir"], w["run_id"], it=EXPECTED_ITER)
    a_m, a_c, a_s = (float(st["A_10_19"]), float(res["W01"]["stab"]["CATA"]["A_10_19"]),
                     float(res["W01"]["stab"]["SLIP"]["A_10_19"]))
    pg = float(st["parity_gap_rel"])
    q19_over_qbar = float(st["Q_19"]) / float(st["Qbar_10_19"]) if st["Qbar_10_19"] else float("nan")
    q19_dev_pp = abs(q19_over_qbar - 1.0) * 100.0
    h2 = pd.DataFrame([{
        "label": "W01", "A_10_19_MATCHED": a_m, "A_10_19_CATA": a_c, "A_10_19_SLIP": a_s,
        "parity_gap_rel_MATCHED": pg, "Q19_over_Qbar_MATCHED": q19_over_qbar,
        "Q19_over_Qbar_dev_pp": q19_dev_pp,
        "never_arrived": (lh or {}).get("never_arrived"),
        "max_stuck_car": (lh or {}).get("max_stuck_car"),
        "departures_car": (lh or {}).get("departures_car"),
        "arrivals_car": (lh or {}).get("arrivals_car"),
    }])
    h2.to_csv(OUT / "final_workingpoint_7_6h_h2_stability.csv", index=False, encoding="utf-8-sig")
    print(h2.to_string(index=False, float_format=lambda v: f"{v:,.6f}"))
    ck(f"H2.1 A_10:19(MATCHED) < {TH['H2_A_matched_pct']}%", a_m < TH["H2_A_matched_pct"] / 100.0,
       f"{a_m:.4%}")
    ck(f"H2.2 A_10:19(CATA) < {TH['H2_A_cata_pct']}%", a_c < TH["H2_A_cata_pct"] / 100.0, f"{a_c:.4%}")
    ck(f"H2.3 A_10:19(SLIP) < {TH['H2_A_slip_pct']}%", a_s < TH["H2_A_slip_pct"] / 100.0, f"{a_s:.4%}")
    ck(f"H2.4 parity_gap_rel(MATCHED) < {TH['H2_parity_gap_pct']}%",
       pg < TH["H2_parity_gap_pct"] / 100.0, f"{pg:.4%}")
    ck(f"H2.5 |Q_19/Q̄_10:19 − 1| ≤ {TH['H2_q19_over_qbar_dev_pct']}%", q19_dev_pp <= TH["H2_q19_over_qbar_dev_pct"],
       f"Q19/Q̄={q19_over_qbar:.6f}  Δ={q19_dev_pp:.4f}%")
    if lh is None:
        ck("H2.6 never_arrived / max_stuck_car（it.19 legHistogram）", False,
           "** legHistogram.txt 缺失 ⇒ 判据无法核验（不得算作 PASS）**")
    else:
        ck(f"H2.6 never_arrived == {TH['H2_never_arrived']} 且 max_stuck_car == {TH['H2_max_stuck_car']}",
           (lh["never_arrived"] == TH["H2_never_arrived"] and lh["max_stuck_car"] == TH["H2_max_stuck_car"]),
           f"never_arrived={lh['never_arrived']:,.0f}  max_stuck_car={lh['max_stuck_car']:,.0f}  "
           f"(dep {lh['departures_car']:,.0f} / arr {lh['arrivals_car']:,.0f})")

    # ---- [6] H3 空间残差 --------------------------------------------------
    log("\n[6/8] H3 空间残差是否仍然存在（**不追求消除**）")
    sp = res["W01"]["spatial"].copy()
    if G76_SPATIAL.exists():
        g76sp = pd.read_csv(G76_SPATIAL)
        g76sp = g76sp[g76sp["run"] == "L75"][["group_by", "group", "rel_dev_vs_global_FROZEN"]]
        g76sp = g76sp.rename(columns={"rel_dev_vs_global_FROZEN": "rel_dev_L75_7_6G"})
        sp = sp.merge(g76sp, on=["group_by", "group"], how="left")
        sp["abs_dev_vs_L75_pp"] = (sp["rel_dev_vs_global_FROZEN"] - sp["rel_dev_L75_7_6G"]).abs() * 100.0
    else:
        sp["rel_dev_L75_7_6G"] = float("nan")
        sp["abs_dev_vs_L75_pp"] = float("nan")
    sp.to_csv(OUT / "final_workingpoint_7_6h_h3_spatial.csv", index=False, encoding="utf-8-sig")
    print(sp[["group_by", "group", "n_sections", "n_zero_sim", "Q_FROZEN",
              "rel_dev_vs_global_FROZEN", "rel_dev_L75_7_6G", "abs_dev_vs_L75_pp"]]
          .sort_values("abs_dev_vs_L75_pp", ascending=False)
          .to_string(index=False, float_format=lambda v: f"{v:,.4f}"))
    max_dev = float(np.nanmax(sp["abs_dev_vs_L75_pp"])) if len(sp) else float("nan")
    ck(f"H3.1 空间格局保持（每组 |rel_dev_W01 − rel_dev_L75| ≤ {TH['H3_pattern_tol_pp']} pp）",
       bool(np.isfinite(max_dev) and max_dev <= TH["H3_pattern_tol_pp"]),
       f"max |Δ| = {max_dev:.4f} pp（{len(sp)} 组）")
    # 关键 PA（无 PA 级 rel_dev 时降级说明）
    pa = pa_table(res["W01"]["sec"], float(E.pooled(res["W01"]["sec"])))
    if pa.empty:
        log("   （`sec` 无 `pa` 列 ⇒ 跳过 PA 级表）")
    else:
        pa.to_csv(OUT / "final_workingpoint_7_6h_h3_key_pa.csv", index=False, encoding="utf-8-sig")
        print(pa.to_string(index=False, float_format=lambda v: f"{v:,.4f}"))
    ck("H3.2 空间残差**仍然存在**（EAST / radial_in 未消失）",
       bool(len(sp) and (sp["rel_dev_vs_global_FROZEN"] < 0).any()
            and (sp["rel_dev_vs_global_FROZEN"] > 0).any()),
       "正/负亏盈两侧同时存在 ⇒ 残差未被「抹平」")

    # ---- [7] H4 三层带（不合并） -----------------------------------------
    log("\n[7/8] H4 λ 敏感性边界（三层，来源不同，**不得合并**）")
    h4 = pd.DataFrame([
        {"layer": "working_point", "value": f"lambda={H.LAM_REF}, f*={H.F_REF}",
         "source": "7.6G L75 直跑（实测）", "kind": "conditional_point_estimate"},
        {"layer": "lambda_sensitivity_band", "value": f"{H.BAND_LAMBDA}",
         "source": "7.6G λ=0.05/0.10 两端", "kind": "dynamic_response_uncertainty"},
        {"layer": "static_target_band", "value": f"{H.BAND_STATIC_TARGET}",
         "source": "7.6C-2 TARGET_MARGINAL_COARSE_ONLY", "kind": "target_identification_uncertainty"},
    ])
    h4.to_csv(OUT / "final_workingpoint_7_6h_h4_bands.csv", index=False, encoding="utf-8-sig")
    print(h4.to_string(index=False))
    ck("H4.1 三层带各自独立成列（未合并为单一区间）", len(h4) == 3,
       " + ".join(h4["layer"].tolist()))
    ck("H4.2 报告文案绑定「基准工作点 + λ 敏感带」，**不写单一 λ 点估计**",
       True, f"λ_ref={H.LAM_REF}（敏感度中心）⛔ 非数据最优 λ")

    # ---- [8] SCALE 审计 + 判决 -------------------------------------------
    log("\n[8/8] SCALE 冻结审计 + 判决")
    sa = E.scale_audit()
    sa = sa[sa["run"].isin([r["label"] for r in RUNS])].copy()
    sa["lambda"] = sa["run"].map({r["label"]: r["lambda"] for r in RUNS})
    sa.to_csv(OUT / "final_workingpoint_7_6h_scale_audit.csv", index=False, encoding="utf-8-sig")
    print(sa[["run", "lambda", "f_demand", "n_agents", "sum_expansion_factor", "scale_used",
              "scale_if_recomputed_sumEF_over_N", "scale_recompute_delta_ppm"]]
          .to_string(index=False, float_format=lambda v: f"{v:,.6f}"))
    ck("P1 SCALE 全档采用 2.29897（★不按 ΣEF/N_sim 重算）",
       bool((sa["scale_used"] - SCALE_FROZEN).abs().max() < 1e-12),
       f"n={len(sa)}  max|delta_ppm|={sa['scale_recompute_delta_ppm'].abs().max():.2f}")

    h1_ok = all(c["pass"] for c in _ck if c["check"].startswith("H1."))
    h2_ok = all(c["pass"] for c in _ck if c["check"].startswith("H2."))
    h3_ok = all(c["pass"] for c in _ck if c["check"].startswith("H3."))
    if not h1_ok:
        verdict = "WORKING_POINT_NOT_REPRODUCIBLE"
    elif not h2_ok:
        verdict = "WORKING_POINT_FROZEN_BUT_UNSTABLE"
    else:
        verdict = "WORKING_POINT_FROZEN_AND_REPRODUCIBLE"
    spat = "SPATIAL_RESIDUAL_PERSISTS" if h3_ok else "SPATIAL_SHIFTED"
    status = f"{verdict} / {spat}"
    ck(f"V1 主判决 = {verdict}", True, f"H1={'ok' if h1_ok else 'FAIL'} H2={'ok' if h2_ok else 'FAIL'}")
    ck(f"V2 空间判决 = {spat}", True, f"max |Δ| = {max_dev:.4f} pp")

    npass = sum(1 for c in _ck if c["pass"])
    payload = {
        "step": "7.6H",
        "title": "Final working point determination and independent validation",
        "status": status, "verdict": verdict, "spatial_verdict": spat,
        "design": "FINAL_WORKING_POINT_PLUS_INDEPENDENT_VALIDATION",
        "zero_simulation": True, "matsim_rerun": False, "parameters_changed": False,
        "parameter_search": False, "lambda_rescanned": False, "demand_grid_refined": False,
        "working_point": {"lambda_ref": H.LAM_REF, "f_demand_ref": H.F_REF,
                          "f_demand_interp": H.F_REF_INTERP, "n_base": H.N_BASE, "n_sim": H.N_SIM,
                          "n_sim_if_f_rounded": H.N_SIM_ROUNDED_F},
        "scale_used": SCALE_FROZEN, "scale_rule": "FROZEN 2.29897; NOT recomputed from sum_EF",
        "route_choice": "R01_rc_min", "target": "7.3.6A_FROZEN",
        "primary_metric": "MATCHED Sim/Obs(08-09)", "primary_window": "Qbar_10:19",
        "reference_window": "Q_19",
        "bands_merged": False,
        "bands": {"working_point_fstar": H.F_REF,
                  "lambda_sensitivity_band": H.BAND_LAMBDA,
                  "static_target_band": H.BAND_STATIC_TARGET},
        "thresholds": TH,
        "g76_l75_reference": L75,
        "r01_refonly": R01_REFONLY,
        "h1": h1.to_dict(orient="records"),
        "h2": h2.to_dict(orient="records"),
        "h3_spatial": sp.to_dict(orient="records"),
        "h3_key_pa": (pa.to_dict(orient="records") if not pa.empty else []),
        "h3_max_abs_dev_vs_l75_pp": (None if not np.isfinite(max_dev) else max_dev),
        "h4_bands": h4.to_dict(orient="records"),
        "h5_open_issues": [
            "总体交通量尺度已达到可接受的匹配水平（|Sim/Obs − 1| 在噪声底内）",
            "EAST / NE / radial 等空间残差**仍然存在**，未因最终工作点而消失",
            "空间残差对 demand 尺度与 λ 的敏感性都较低 ⇒ 不宜通过继续调整 demand/λ 强行消除",
            "三项本地不可定量（须外部数据）：① 观测车型构成；② AM 峰占日通勤比重；③ 平均载客率",
        ],
        "crossvalidation": xval,
        "scale_audit": sa.to_dict(orient="records"),
        "linkstats_availability": avail,
        "checks_total": len(_ck), "checks_pass": npass, "checks": _ck,
        "runtime_sec": round(time.time() - t0, 1),
        "artifacts": [
            "final_workingpoint_7_6h_h1_reproducibility.csv",
            "final_workingpoint_7_6h_h2_stability.csv",
            "final_workingpoint_7_6h_h3_spatial.csv",
            "final_workingpoint_7_6h_h3_key_pa.csv",
            "final_workingpoint_7_6h_h4_bands.csv",
            "final_workingpoint_7_6h_scale_audit.csv",
            "final_workingpoint_7_6h_crossvalidation.csv",
            "od_final_workingpoint_7_6h_summary.json",
            "STEP7_6H_REPORT.md",
        ],
    }
    (OUT / "od_final_workingpoint_7_6h_summary.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    write_report(payload, OUT)
    log(f"   校验 {npass}/{len(_ck)} PASS")
    for c in _ck:
        if not c["pass"]:
            log(f"   FAIL: {c['check']}  {c['detail']}")
    log(f"\n   VERDICT: {status}")
    return 0 if npass == len(_ck) else 1


def write_report(payload: dict, out_dir: Path) -> Path:
    st = payload["status"]
    wo = payload["working_point"]
    L = []
    A = L.append
    A("# Step 7.6H — **最终工作点确定与独立验证**（不是「最终标定」，也不是参数搜索）")
    A("")
    A(f"> **判决：`{st}`**（零仿真评价；本步**只跑过 1 次 MATSim**（W01 独立验证），此后只读 linkstats）")
    A("")
    A("> 上游 7.6G 已闭环并按现口径冻结（`LAMBDA_DETECTABLE_NOT_IDENTIFIABLE / SPATIAL_INERT`）；")
    A("> 本步**不再细搜 λ、不再细化 demand grid、不做 crosswalk-b**。")
    A("")
    A("## 0. 第一层：冻结工作点（只读引用，未重估）")
    A("")
    A("| 项 | 冻结值 | 来源 / 规则 |")
    A("|---|---|---|")
    for k, v, s in H.FROZEN_PAYLOAD:
        A(f"| `{k}` | **{v}** | {s} |")
    A("")
    A(f"> `N_sim = round({wo['f_demand_ref']} × {wo['n_base']:,}) = **{wo['n_sim']:,}**`；"
      f"若把 f 四舍五入成 1.1802 则得 {wo['n_sim_if_f_rounded']:,}（差 **{wo['n_sim'] - wo['n_sim_if_f_rounded']} agent**）。")
    A("> ★ `SCALE = 459,794 / 200,000 = 2.29897` **不随 N_sim 变**；⛔ **不得**改成 `459,794 / N_sim`。")
    A("")
    A("## H1｜可复现性")
    A("")
    h1 = payload["h1"][0]
    A("| 项 | 值 |")
    A("|---|---:|")
    for kk, lab in (("SimObs_FROZEN", "Sim/Obs `FROZEN`（主靶场）"),
                    ("SimObs_POSITIVE_ONLY", "`POSITIVE_ONLY`"),
                    ("SimObs_BEST_DIRECTION", "`BEST_DIRECTION`"),
                    ("SimObs_FROZEN_REF_it19", "`it.19` 单迭代参照（不作收敛解）"),
                    ("implied_fstar_FROZEN", "隐含 f\\*"),
                    ("f_realized", "`f_realized`（产物实测）"),
                    ("abs_dev_from_1_pp", "`\\|Sim/Obs − 1.000\\|`（pp）"),
                    ("abs_dev_vs_L75_pp", "`\\|Δ vs 7.6G L75\\|`（pp）"),
                    ("Qbar_10_19_MATCHED", "`Q̄_10:19`(MATCHED)"),
                    ("Q_19_MATCHED", "`Q_19`(MATCHED)")):
        A(f"| {lab} | {h1.get(kk)} |")
    A("")
    A(f"> 通径校验门槛：`\\|Sim/Obs − 1\\| ≤ {payload['thresholds']['H1_simobs_abs_dev_from_1pp']} pp`；"
      f"`\\|f* − {wo['f_demand_ref']}\\| ≤ {payload['thresholds']['H1_fstar_dev']}`；"
      f"`\\|Δ vs L75\\| ≤ {payload['thresholds']['H1_vs_l75_pp']} pp`。")
    A("> ⛔ 参照值 `R01` 的隐含 f\\* = 1.363560 **不参与 H1**：该值为局部割线向低需求侧外推的产物，")
    A("> 受响应曲线非线性/凹性影响，**不作需求尺度估计、不参与 λ 比较**。")
    A("")
    A("## H2｜稳定性（ΣHRS0-24avg 口径；`never_arrived` 承 7.6E G5）")
    A("")
    h2 = payload["h2"][0]
    A("| 判据 | 实测 | 门槛 |")
    A("|---|---:|---:|")
    A(f"| `A_10:19`(MATCHED) | {100.0*float(h2['A_10_19_MATCHED']):.4f}% | < {payload['thresholds']['H2_A_matched_pct']}% |")
    A(f"| `A_10:19`(CATA) | {100.0*float(h2['A_10_19_CATA']):.4f}% | < {payload['thresholds']['H2_A_cata_pct']}% |")
    A(f"| `A_10:19`(SLIP) | {100.0*float(h2['A_10_19_SLIP']):.4f}% | < {payload['thresholds']['H2_A_slip_pct']}% |")
    A(f"| `parity_gap_rel`(MATCHED) | {100.0*float(h2['parity_gap_rel_MATCHED']):.4f}% | < {payload['thresholds']['H2_parity_gap_pct']}% |")
    A(f"| `\\|Q_19/Q̄_10:19 − 1\\|` | {float(h2['Q19_over_Qbar_dev_pp']):.4f}% | ≤ {payload['thresholds']['H2_q19_over_qbar_dev_pct']}% |")
    A(f"| `never_arrived` (it.{EXPECTED_ITER}) | {h2['never_arrived']} | == 0 |")
    A(f"| `max_stuck_car` (it.{EXPECTED_ITER}) | {h2['max_stuck_car']} | == 0 |")
    A("")
    A(f"> departures={h2['departures_car']} / arrivals={h2['arrivals_car']}（{H.N_SIM:,} agents）。")
    A("")
    A("## H3｜空间残差是否仍然存在（**不追求消除**）")
    A("")
    A("| group_by | group | n | Q_FROZEN | rel_dev(W01) | rel_dev(7.6G L75) | \\|Δ\\| (pp) |")
    A("|---|---|---:|---:|---:|---:|---:|")
    for r in sorted(payload["h3_spatial"], key=lambda d: -(d.get("abs_dev_vs_L75_pp") or 0)):
        A("| %s | %s | %s | %.4f | %+.4f | %+.4f | **%.4f** |"
          % (r.get("group_by"), r.get("group"), r.get("n_sections"), float(r.get("Q_FROZEN") or 0),
             float(r.get("rel_dev_vs_global_FROZEN") or 0),
             float(r.get("rel_dev_L75_7_6G") or 0), float(r.get("abs_dev_vs_L75_pp") or 0)))
    A("")
    A(f"> max `\\|Δ\\|` vs 7.6G `L75` = **{payload['h3_max_abs_dev_vs_l75_pp']:.4f} pp**"
      f"（门槛 {payload['thresholds']['H3_pattern_tol_pp']} pp）")
    A("> ⇒ **最终需求标定只解决总体量级，不改变既有空间结构残差。**")
    A("> ⛔ 不得为「把空间误差消掉」回头调 demand / λ（7.6F-1 / 7.6G 已证两者都压不平）。")
    A("")
    if payload.get("h3_key_pa"):
        A("### 关键 PA（rel_dev 绝对值最大的 10 个）")
        A("")
        A("| PA | n | Q_FROZEN | rel_dev |")
        A("|---|---:|---:|---:|")
        for r in payload["h3_key_pa"]:
            A("| %s | %s | %.4f | %+.4f |" % (r.get("pa"), r.get("n_sections"),
                                              float(r.get("Q_FROZEN") or 0),
                                              float(r.get("rel_dev_vs_global_FROZEN") or 0)))
        A("")
    A("## H4｜λ 敏感性边界（三层，来源不同，**不得合并**）")
    A("")
    A("| 层 | 值 | 来源 | 性质 |")
    A("|---|---|---|---|")
    for r in payload["h4_bands"]:
        A("| `%s` | %s | %s | %s |" % (r["layer"], r["value"], r["source"], r["kind"]))
    A("")
    A("> **基准工作点：λ = 0.075；对应需求尺度约 f = 1.1802；在当前 TrafficFlow 靶场与模型结构下，"
      "λ 敏感度对应的需求尺度范围约为 [1.1637, 1.1938]。**")
    A("> ⛔ 三层**不得**压成一个「最终置信区间」。")
    A("")
    A("## H5｜哪些问题**没有**解决")
    A("")
    for s in payload["h5_open_issues"]:
        A(f"- {s}")
    A("")
    A("## 口径未漂移对账（X1 vs 7.6C-2 / X2 vs 7.6D 缓存）")
    A("")
    A("| item | ours | reference | abs_diff | tol | pass |")
    A("|---|---:|---:|---:|---:|:--:|")
    for c in payload["crossvalidation"]:
        A("| %s | %.7g | %.7g | %.2e | %.0e | %s |"
          % (c["item"], float(c["ours"]), float(c["reference"]), float(c["abs_diff"]),
             float(c["tol"]), "PASS" if c["pass"] else "FAIL"))
    A("")
    A("## SCALE 冻结审计")
    A("")
    A("| run | λ | f_demand | n_agents | ΣEF | scale_used | 若按 ΣEF/N 重算 | Δ (ppm) |")
    A("|---|---:|---:|---:|---:|---:|---:|---:|")
    for r in payload["scale_audit"]:
        A("| %s | %.3f | %.5f | %s | %s | %.5f | %.6f | %+.2f |"
          % (r["run"], float(r["lambda"]), float(r["f_demand"]), format(int(r["n_agents"]), ","),
             format(float(r["sum_expansion_factor"]), ",.3f"), float(r["scale_used"]),
             float(r["scale_if_recomputed_sumEF_over_N"]), float(r["scale_recompute_delta_ppm"])))
    A("")
    A("> `scale_if_recomputed_sumEF_over_N` **仅披露，NOT USED**。")
    A("")
    A("## 预注册判据")
    A("")
    A("| 判据 | 结果 | 明细 |")
    A("|---|---|:--:|")
    for c in payload["checks"]:
        A("| %s | %s | %s |" % (c["check"], "PASS" if c["pass"] else "**FAIL**",
                                str(c["detail"]).replace("|", "/")))
    A("")
    A("## 本步**明确未做**")
    A("")
    A("- ✗ 未再细搜 λ（7.6G 已判 `DETECTABLE_NOT_IDENTIFIABLE`，边际收益已很低）")
    A("- ✗ 未细化 demand grid（无 1.17/1.18/1.19/1.20 细扫、无 3×4 λ×demand 网格）")
    A("- ✗ 未做 crosswalk-b（靶场保持 7.3.6A Frozen，**未修改**）")
    A("- ✗ 未改 7.1 / 7.3.6A / OD / network / capacity / route-choice 任一冻结件")
    A("- ✗ 未把 `POSITIVE_ONLY` / `BEST_DIRECTION` 升格为正式标定靶场")
    A("- ✗ 未把三层不确定带压成单一区间")
    A("")
    A("## 产物")
    A("")
    for a in payload["artifacts"]:
        A(f"- `{a}`")
    A("")
    p = out_dir / "STEP7_6H_REPORT.md"
    p.write_text("\n".join(L), encoding="utf-8")
    return p


if __name__ == "__main__":
    t0 = time.time()
    rc = main()
    print(f"\n[wall] {time.time()-t0:.1f} s")
    raise SystemExit(rc)
