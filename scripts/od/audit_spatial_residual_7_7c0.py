#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""
audit_spatial_residual_7_7c0.py — Step 7.7C-0 空间残差归因基线审计（**零仿真、只读**）。

目标（用户 2026-09-19 裁定）
---------------------------
三步排除链已确立：demand `f`（7.6F-1）与 λ（7.6G）与车型/方式构成（7.7A）**均不能解释**空间残差。
本步只做一件事：把「EAST / radial_in / NE 残差存在」进一步定位到下面 6 层中的哪一层——

    C0-1  OD 空间供需（P_i / A_j / T_ij）
    C0-2  方向性（inbound / outbound / radial_in / radial_out / circumferential）
    C0-3  道路等级（motorway / motorway_link / primary / secondary / slip）
    C0-4  section 几何 / twin / 拓扑（matched link 数 / reciprocal / one-to-many）
    C0-5  长度归一化（q/L 是否使残差收敛）
    C0-6  PA / Region 残差空间梯度（距 CBD / 位置 / P / A / 路密 / 高速密）

复用纪律
--------
**不复制任何公式**：逐断面 Sim/Obs 直接复用 `evaluate_demand_response_7_6f_1.eval_run()`
（与 7.6H 同一函数、同一冻结输入），只重绑 `E.OUT / E.CYCLE_DIR / E.MATRIX_CSV` 到 7.6H 工作区。
`MUST_MATCH_BASELINE` 逐位复现 7.6H `h3_spatial.csv`（1e-12）与 `SimObs_FROZEN`（1e-9）
⇒ 这是「口径未漂移」的唯一硬证据。

约束（硬）
----------
零仿真；不修改 7.1 / 7.3.6A / OD / network / capacity；不引入新的 calibration knob；
只读 7.6H / 7.6C / 7.6F-1 / 7.6G 已冻结产物。

用法
----
    python scripts/od/audit_spatial_residual_7_7c0.py
    python scripts/od/audit_spatial_residual_7_7c0.py --force-cycle
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(r"D:\Luan\2026-05\2_Singapore")
sys.path.insert(0, str(ROOT / "scripts" / "od"))

import compare_final_crosswalk_7_3_6b as bt              # noqa: E402  冻结 SCALE
import evaluate_calibration_7_4_2 as ev1                 # noqa: E402  TRAFFIC / FINAL_CW
import diagnose_od_spatial_structure_7_6c as d76         # noqa: E402  section_geography / OUT_DIR
import evaluate_demand_response_7_6f_1 as E              # noqa: E402  ★ 复用 eval_run()
import prepare_final_workingpoint_7_6h as H              # noqa: E402  7.6H 常量

# --------------------------------------------------------------------------
# 路径重绑定 → 7.6H 工作区（与 evaluate_final_workingpoint_7_6h.py 一致）
# --------------------------------------------------------------------------
H_ROOT = H.NEW_ROOT
E.OUT = H_ROOT / "audit"
E.CYCLE_DIR = E.OUT / "_cycle_linkstats"
E.MATRIX_CSV = H_ROOT / "final_workingpoint_7_6h_matrix.csv"

OUT = ROOT / "reports" / "spatial_residual_7_7c0"
GEO_CSV = d76.OUT_DIR / "section_geography.csv"
LINKRD_CSV = d76.OUT_DIR / "link_ring_direction.csv"
ZONE_CSV = d76.OUT_DIR / "od_zone_marginals.csv"
SEM_CSV = ROOT / "reports" / "od_network_semantic_audit_7_3_3" / "section_semantic_audit.csv"
OD_CSV = ROOT / "reports" / "od_prior_5c1" / "prior_od_5c1_lambda_0p075.csv"
ODBLK_CSV = ROOT / "reports" / "od_anomaly_trace_7_6c_1" / "od_region_block_matrix.csv"
ODDIR_CSV = ROOT / "reports" / "od_anomaly_trace_7_6c_1" / "od_direction_symmetry.csv"
F1_SPATIAL = ROOT / "matsim_demand_7_6f_1" / "audit" / "demand_response_spatial_residuals.csv"
G_SPATIAL = ROOT / "matsim_lambda_7_6g" / "audit" / "lambda_sensitivity_spatial_residuals.csv"
H3_SPATIAL = E.OUT / "final_workingpoint_7_6h_h3_spatial.csv"
H_SUMMARY = E.OUT / "od_final_workingpoint_7_6h_summary.json"

RUN_W01 = {
    "label": "W01", "role": "final_working_point", "lambda": H.LAM_REF,
    "f_demand": H.F_REF, "N": H.N_SIM,
    "out_dir": H_ROOT / "outputs" / "W01_rc_min", "run_id": "W01_rc_min", "stage": "7.6H",
}

WCOL, VCOL = "obs_8_9", "ratio_8_9"
_ck: list[dict] = []


def ck(name: str, ok: bool, detail: str = "") -> bool:
    _ck.append({"check": name, "pass": bool(ok), "detail": str(detail)})
    print(f"   [{'PASS' if ok else 'FAIL'}] {name}  {detail}")
    return bool(ok)


def banner(msg: str) -> None:
    print("\n" + "=" * 88 + f"\n{msg}\n" + "=" * 88)


def wmean(v: pd.Series, w: pd.Series) -> float:
    v = np.asarray(v, float)
    w = np.asarray(w, float)
    m = np.isfinite(v) & np.isfinite(w) & (w > 0)
    if not m.any() or w[m].sum() <= 0:
        return float("nan")
    return float((v[m] * w[m]).sum() / w[m].sum())


def eta2(df: pd.DataFrame, by: str, wcol: str = WCOL, vcol: str = VCOL) -> float:
    """obs 加权 η² —— 分组 `by` 解释逐断面 ratio 的方差份额（边际归因，非偏效应）。"""
    d = df[[by, wcol, vcol]].dropna()
    if d.empty:
        return float("nan")
    w = d[wcol].to_numpy(float)
    v = d[vcol].to_numpy(float)
    W = w.sum()
    if W <= 0:
        return float("nan")
    gm = (w * v).sum() / W
    sst = (w * (v - gm) ** 2).sum()
    if sst <= 0:
        return float("nan")
    ssb = 0.0
    for _, sub in d.groupby(by):
        wg = sub[wcol].sum()
        if wg <= 0:
            continue
        vg = (sub[wcol] * sub[vcol]).sum() / wg
        ssb += wg * (vg - gm) ** 2
    return float(ssb / sst)


def group_table(df: pd.DataFrame, by: str) -> pd.DataFrame:
    """分组池化 ratio + rel_dev vs 全局（与 7.6H h3 同式：pooled(sub)/pooled(all) − 1）。"""
    g_all = float(df["sim_8_9_scaled"].sum() / df["obs_8_9"].sum())
    rows = []
    for k, sub in df.dropna(subset=[by]).groupby(by):
        o = float(sub["obs_8_9"].sum())
        s = float(sub["sim_8_9_scaled"].sum())
        if o <= 0:
            continue
        pos = sub[sub["sim_8_9_scaled"] > 0]
        op = float(pos["obs_8_9"].sum())
        rows.append({
            "group": k, "n_sections": int(len(sub)),
            "n_zero_sim": int((sub["sim_8_9_scaled"] <= 0).sum()),
            "obs_total": o, "sim_total": s,
            "ratio_pooled": s / o,
            "ratio_obs_weighted": wmean(sub[VCOL], sub[WCOL]),
            "ratio_median": float(np.nanmedian(sub[VCOL])),
            "rel_dev_vs_global": s / o / g_all - 1.0,
            "ratio_pos_only": (float(pos["sim_8_9_scaled"].sum()) / op) if op > 0 else float("nan"),
        })
    out = pd.DataFrame(rows)
    if not out.empty:
        out = out.sort_values("rel_dev_vs_global")
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--force-cycle", action="store_true")
    args = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    t0 = time.time()

    banner("Step 7.7C-0 空间残差归因基线审计（零仿真、只读；复用 7.6H 冻结口径）")
    print(f"  工作点 W01: λ={H.LAM_REF}  f*={H.F_REF}  N_sim={H.N_SIM:,}  "
          f"SCALE={float(bt.SCALE):.5f}（冻结）")
    print(f"  靶场 = 7.1 观测 + 7.3.6A Crosswalk（576 断面）")

    # ---- [0] 冻结件载入（与 7.6H 逐行一致）-------------------------------
    banner("[0/7] 载入冻结件（7.1 观测 / 7.3.6A crosswalk / 7.6C 地理）")
    obs = bt.load_traffic(ev1.TRAFFIC)
    cw = bt.normalize_crosswalk(ev1.FINAL_CW, "final")
    cwraw = pd.read_csv(ev1.FINAL_CW, encoding="utf-8-sig")
    cwraw["matsim_link_id"] = cwraw["matsim_link_id"].astype(str).str.strip()
    cwraw["lta_linkid"] = cwraw["lta_linkid"].astype(str).str.strip()
    cw_prim = cwraw[cwraw["is_primary_candidate"]].copy() \
        if "is_primary_candidate" in cwraw.columns else cwraw.copy()
    matched = set(cwraw["matsim_link_id"])
    cata = set(cwraw.loc[cwraw["RoadCat"] == "CATA", "matsim_link_id"])
    slip = set(cwraw.loc[cwraw["RoadCat"] == "SLIP_ROAD", "matsim_link_id"])
    geo = pd.read_csv(GEO_CSV)[
        ["lta_linkid", "mid_x", "mid_y", "d_cbd_m", "n_links", "radial", "ring", "region", "pa"]]
    geo["lta_linkid"] = geo["lta_linkid"].astype(str).str.strip()
    ck("P1 CATA + SLIP == MATCHED", len(cata) + len(slip) == len(matched),
       f"{len(cata)}+{len(slip)} vs {len(matched)}")

    # ---- [1] 复用 eval_run 得逐断面 Sim/Obs -----------------------------
    banner("[1/7] 复用 evaluate_demand_response_7_6f_1.eval_run() → 逐断面 sec 表")
    res = E.eval_run(RUN_W01, cw, cw_prim, obs, geo, matched, cata, slip,
                     force_cycle=args.force_cycle)
    sec = res["sec"].copy()
    n_sec = len(sec)
    ck("P2 断面数 == 576", n_sec == 576, f"{n_sec}")
    ck("P3 sec 含 Sim/Obs 列",
       all(c in sec.columns for c in ("sim_8_9_scaled", "obs_8_9", "ratio_8_9")),
       "sim_8_9_scaled / obs_8_9 / ratio_8_9")

    # ---- [2] MUST_MATCH_BASELINE ---------------------------------------
    banner("[2/7] MUST_MATCH_BASELINE —— 口径未漂移（1e-12 / 1e-9）")
    h3 = pd.read_csv(H3_SPATIAL, encoding="utf-8-sig")
    h3 = h3[h3["run"] == "W01"][["group_by", "group", "rel_dev_vs_global_FROZEN"]]
    mine = res["spatial"].copy()
    mm = mine.merge(h3, on=["group_by", "group"], how="inner", suffixes=("", "_ref"))
    dmax = float((mm["rel_dev_vs_global_FROZEN"] - mm["rel_dev_vs_global_FROZEN_ref"]).abs().max())
    ck("M1 逐组 rel_dev == 7.6H h3_spatial（≤1e-12）", dmax < 1e-12,
       f"max|Δ|={dmax:.3e}（{len(mm)} 组）")
    with open(H_SUMMARY, encoding="utf-8") as fh:
        _sum = json.load(fh)
    simobs_ref = float(_sum["h1"][0]["SimObs_FROZEN"])
    simobs = float(res["q"]["FROZEN"])
    ck("M2 Sim/Obs FROZEN == 7.6H 汇总（≤1e-9）", abs(simobs - simobs_ref) < 1e-9,
       f"ours={simobs:.7f} ref={simobs_ref:.7f}")
    east = float(mine.loc[mine["group"] == "EAST REGION", "rel_dev_vs_global_FROZEN"].iloc[0])
    rin = float(mine.loc[mine["group"] == "radial_in", "rel_dev_vs_global_FROZEN"].iloc[0])
    ne = float(mine.loc[mine["group"] == "NORTH-EAST REGION", "rel_dev_vs_global_FROZEN"].iloc[0])
    ck("M3 EAST/radial_in/NE 残差复现", True,
       f"EAST={east:.4%}  radial_in={rin:.4%}  NE={ne:.4%}")
    if not (dmax < 1e-12 and abs(simobs - simobs_ref) < 1e-9):
        print("   ⛔ 口径漂移 ⇒ 中止（不得出结论）")
        return 1

    # ---- 增强：挂 7.3.3 语义 + 长度 --------------------------------------
    sem = pd.read_csv(SEM_CSV, encoding="utf-8-sig")
    sem["lta_linkid"] = sem["lta_linkid"].astype(str).str.strip()
    sem_cols = ["lta_linkid", "dominant_highway", "motorway_edges", "motorway_link_edges",
                "has_mixed_highway", "reciprocal_edge_count", "reciprocal_share",
                "has_reciprocal_pair", "self_opposite_share", "is_cata", "is_slip", "matsim_edges"]
    sem_cols = [c for c in sem_cols if c in sem.columns]
    linkrd = pd.read_csv(LINKRD_CSV, encoding="utf-8-sig")
    linkrd["matsim_link_id"] = linkrd["matsim_link_id"].astype(str).str.strip()
    len_by_sec = (cwraw.merge(linkrd[["matsim_link_id", "length_m", "radial", "ring"]],
                              on="matsim_link_id", how="left")
                  .groupby("lta_linkid")["length_m"].sum().rename("section_length_m"))
    sem["lta_linkid"] = sem["lta_linkid"].astype(str).str.strip()
    S = sec.merge(sem[sem_cols], on="lta_linkid", how="left")
    S = S.merge(cwraw.groupby("lta_linkid").agg(
        n_matsim_link=("matsim_link_id", "nunique"),
        shared_section_count=("shared_section_count", "max") if "shared_section_count" in cwraw else ("matsim_link_id", "size"),
        direction_ok=("direction_ok", "all") if "direction_ok" in cwraw else ("matsim_link_id", "size"),
    ), on="lta_linkid", how="left")
    S = S.merge(len_by_sec, on="lta_linkid", how="left")
    ck("P4 语义/长度挂接覆盖", int(S["dominant_highway"].notna().sum()) >= 570 and
       int(S["section_length_m"].notna().sum()) >= 570,
       f"highway={int(S['dominant_highway'].notna().sum())}/{len(S)}  "
       f"len={int(S['section_length_m'].notna().sum())}/{len(S)}")

    art = {}
    g_all = float(S["sim_8_9_scaled"].sum() / S["obs_8_9"].sum())
    # 逐断面归因底表（证据留档）
    SAVE_COLS = [c for c in ("lta_linkid", "sim_8_9_scaled", "obs_8_9", "ratio_8_9", "zero_sim",
                             "region", "pa", "radial", "ring", "d_cbd_m", "n_links", "mid_x", "mid_y",
                             "dominant_highway", "RoadCat", "motorway_edges", "motorway_link_edges",
                             "has_reciprocal_pair", "reciprocal_share", "self_opposite_share",
                             "has_mixed_highway", "n_matsim_link", "shared_section_count",
                             "direction_ok", "section_length_m") if c in S.columns]
    S[SAVE_COLS].to_csv(OUT / "c0_section_table.csv", index=False, encoding="utf-8-sig")

    # ======================================================================
    # C0-1 OD 空间供需
    # ======================================================================
    banner("[3/7] C0-1 OD 空间供需（P_i / A_j / T_ij）")
    zone = pd.read_csv(ZONE_CSV, encoding="utf-8-sig")
    zreg = zone["planning_region"].astype(str).str.replace(" REGION", "", regex=False).str.strip().str.upper()
    zone = zone.assign(_reg=zreg)
    zagg = zone.groupby("_reg").agg(
        P_sum=("P_i", "sum"), A_sum=("A_j", "sum"),
        od_rowsum=("OD_rowsum", "sum"), od_colsum=("OD_colsum", "sum"),
        n_zones=("zone_id", "nunique")).reset_index()
    zagg["A_over_P"] = zagg["A_sum"] / zagg["P_sum"]
    regres = mine[mine["group_by"] == "region"][["group", "rel_dev_vs_global_FROZEN", "n_sections"]].copy()
    regres["_reg"] = regres["group"].astype(str).str.replace(" REGION", "", regex=False).str.strip().str.upper()
    c01 = regres.merge(zagg, on="_reg", how="left").rename(columns={
        "group": "region", "rel_dev_vs_global_FROZEN": "residual_rel_dev"})
    c01 = c01[["region", "_reg", "n_sections", "residual_rel_dev",
               "P_sum", "A_sum", "A_over_P", "od_rowsum", "od_colsum", "n_zones"]]
    c01.to_csv(OUT / "c0_1_od_supply_demand_by_region.csv", index=False, encoding="utf-8-sig")
    print(c01.to_string(index=False, float_format=lambda v: f"{v:,.4f}"))
    r_AP = float(c01["A_over_P"].corr(c01["residual_rel_dev"], method="spearman"))
    ck("C0-1a region 残差 vs A/P 供需比（Spearman）", True, f"ρ={r_AP:+.4f}（n=5）")

    # OD region block（复用 7.6C-1 已冻结矩阵）
    blk = pd.read_csv(ODBLK_CSV, encoding="utf-8-sig", index_col=0)
    blk.to_csv(OUT / "c0_1_od_region_block_matrix.csv", encoding="utf-8-sig")
    od_dir = pd.read_csv(ODDIR_CSV, encoding="utf-8-sig")
    od_dir.to_csv(OUT / "c0_1_od_direction_symmetry.csv", index=False, encoding="utf-8-sig")
    print("\n  region→region 早高峰方向性（rev/fwd）：")
    print(od_dir.to_string(index=False, float_format=lambda v: f"{v:,.4f}"))
    asym_hold = bool((od_dir["rev_over_fwd"] < 1.0).all())
    ck("C0-1b 所有「X→CENTRAL」强方向性（rev/fwd<1）", asym_hold,
       f"min rev/fwd={od_dir['rev_over_fwd'].min():.4f}  max={od_dir['rev_over_fwd'].max():.4f}")
    art["c01_region"] = c01

    # ======================================================================
    # C0-2 方向性
    # ======================================================================
    banner("[4/7] C0-2 方向性（radial_in / radial_out / circumferential）")
    t_radial = group_table(S, "radial"); t_radial.to_csv(
        OUT / "c0_2_radial_residual.csv", index=False, encoding="utf-8-sig")
    print(t_radial.to_string(index=False, float_format=lambda v: f"{v:,.4f}"))
    rin_r = float(t_radial.loc[t_radial["group"] == "radial_in", "ratio_pooled"].iloc[0])
    rout_r = float(t_radial.loc[t_radial["group"] == "radial_out", "ratio_pooled"].iloc[0])
    ck("C0-2a radial_in ≠ radial_out", abs(rin_r - rout_r) > 0.05,
       f"in={rin_r:.4f}  out={rout_r:.4f}  Δ={rin_r-rout_r:+.4f}")

    # ring × radial（细粒度）
    t_ringdir = group_table(S, "ring").rename(columns={"group": "ring"})
    t_ringdir.to_csv(OUT / "c0_2_ring_residual.csv", index=False, encoding="utf-8-sig")

    # 方向性在 f / λ 下是否稳定（复用 7.6F-1 / 7.6G 冻结空间表）
    stab_rows = []
    for tag, p, cols in (("f", F1_SPATIAL, None), ("lambda", G_SPATIAL, None)):
        if not Path(p).exists():
            continue
        d = pd.read_csv(p, encoding="utf-8-sig")
        d = d[d["group_by"] == "radial"][["run", "group", "rel_dev_vs_global_FROZEN"]]
        pv = d.pivot(index="run", columns="group", values="rel_dev_vs_global_FROZEN")
        if {"radial_in", "radial_out", "circumferential"}.issubset(pv.columns):
            for run, row in pv.iterrows():
                stab_rows.append({"axis": tag, "run": run,
                                  "radial_in": row["radial_in"], "circumferential": row["circumferential"],
                                  "radial_out": row["radial_out"],
                                  "in_lt_out": bool(row["radial_in"] < row["radial_out"])})
    stab = pd.DataFrame(stab_rows)
    stab.to_csv(OUT / "c0_2_directionality_stability_across_f_lambda.csv", index=False, encoding="utf-8-sig")
    if not stab.empty:
        print("\n  方向性跨 f / λ 稳定性：")
        print(stab.to_string(index=False, float_format=lambda v: f"{v:,.4f}"))
    ck("C0-2b radial_in < radial_out 在 f/λ 全档成立",
       bool(not stab.empty and stab["in_lt_out"].all()),
       f"{int(stab['in_lt_out'].sum())}/{len(stab)} 档成立")
    art["c02_radial"] = t_radial

    # ======================================================================
    # C0-3 道路等级
    # ======================================================================
    banner("[5/7] C0-3 道路等级（dominant_highway / RoadCat）")
    t_hw = group_table(S, "dominant_highway").rename(columns={"group": "dominant_highway"})
    n_hw = S["dominant_highway"].value_counts().rename("n_sections_all")
    t_hw = t_hw.merge(n_hw, left_on="dominant_highway", right_index=True, how="left")
    t_hw.to_csv(OUT / "c0_3_roadclass_residual.csv", index=False, encoding="utf-8-sig")
    print(t_hw.to_string(index=False, float_format=lambda v: f"{v:,.4f}"))
    # 观测语义分层（CATA vs SLIP）—— 排查「观测口径」层
    t_rc = group_table(S, "RoadCat").rename(columns={"group": "RoadCat"})
    t_rc.to_csv(OUT / "c0_3_roadcat_residual.csv", index=False, encoding="utf-8-sig")
    print("\n  RoadCat（观测语义分层）：")
    print(t_rc.to_string(index=False, float_format=lambda v: f"{v:,.4f}"))

    # motorway mainline vs motorway_link（按 section 是否含 motorway_link 边）
    S["_has_mw_link"] = pd.to_numeric(S["motorway_link_edges"], errors="coerce").fillna(0) > 0
    mw = S[S["dominant_highway"].isin(["motorway", "motorway_link"])].copy()
    ml_rows = []
    for flag, sub in (("motorway_mainline_only", S[(S["dominant_highway"] == "motorway") &
                                                   (~S["_has_mw_link"].fillna(False))]),
                      ("with_motorway_link_edges", S[S["_has_mw_link"].fillna(False)]),
                      ("motorway_dominant", S[S["dominant_highway"] == "motorway"]),
                      ("motorway_link_dominant", S[S["dominant_highway"] == "motorway_link"])):
        o = float(sub["obs_8_9"].sum()); s = float(sub["sim_8_9_scaled"].sum())
        if o > 0:
            ml_rows.append({"bucket": flag, "n_sections": int(len(sub)),
                            "obs_total": o, "ratio_pooled": s / o,
                            "rel_dev_vs_global": s / o / g_all - 1.0})
    mwdf = pd.DataFrame(ml_rows)
    mwdf.to_csv(OUT / "c0_3_mainline_vs_link.csv", index=False, encoding="utf-8-sig")
    print("\n  motorway mainline vs motorway_link：")
    print(mwdf.to_string(index=False, float_format=lambda v: f"{v:,.4f}"))
    ck("C0-3a 道路等级分组已量化", len(t_hw) >= 3, f"{len(t_hw)} 类")
    art["c03_hw"] = t_hw

    # ======================================================================
    # C0-4 section 几何 / twin / 拓扑
    # ======================================================================
    banner("[6/7] C0-4 section 几何 / twin / 拓扑")
    S["_nlink_bucket"] = pd.cut(pd.to_numeric(S["n_matsim_link"], errors="coerce"),
                                bins=[0, 1, 2, 3, 1000],
                                labels=["1", "2", "3", "4+"], right=True).astype(object)
    S["_shared_bucket"] = pd.cut(pd.to_numeric(S["shared_section_count"], errors="coerce"),
                                 bins=[0, 1, 2, 1000], labels=["1", "2", "3+"], right=True).astype(object)
    S["_recip"] = S["has_reciprocal_pair"].astype(str) if "has_reciprocal_pair" in S else "NA"
    S["_mixed"] = S["has_mixed_highway"].astype(str) if "has_mixed_highway" in S else "NA"
    topo_rows = []
    for by, name in (("_nlink_bucket", "matched_link_count"),
                     ("_shared_bucket", "shared_section_count"),
                     ("_recip", "has_reciprocal_pair"),
                     ("_mixed", "has_mixed_highway")):
        t = group_table(S, by).rename(columns={"group": name})
        t.insert(0, "dimension", name)
        topo_rows.append(t)
    topo = pd.concat(topo_rows, ignore_index=True)
    topo.to_csv(OUT / "c0_4_topology_residual.csv", index=False, encoding="utf-8-sig")
    print(topo.to_string(index=False, float_format=lambda v: f"{v:,.4f}"))

    # 连续量相关性（Spearman）
    corr_rows = []
    for col in ("n_matsim_link", "shared_section_count", "reciprocal_share",
                "self_opposite_share", "section_length_m", "motorway_edges", "motorway_link_edges"):
        if col not in S.columns:
            continue
        x = pd.to_numeric(S[col], errors="coerce")
        m = x.notna() & S[VCOL].notna()
        if m.sum() < 30:
            continue
        corr_rows.append({"variable": col, "n": int(m.sum()),
                          "spearman_vs_ratio": float(pd.Series(x[m]).corr(pd.Series(S.loc[m, VCOL]), method="spearman"))})
    corr = pd.DataFrame(corr_rows).sort_values("spearman_vs_ratio")
    corr.to_csv(OUT / "c0_4_correlations.csv", index=False, encoding="utf-8-sig")
    print("\n  逐断面 ratio vs 网络表征量（Spearman）：")
    print(corr.to_string(index=False, float_format=lambda v: f"{v:,.4f}"))
    art["c04_topo"] = topo

    # 交叉检验：radial × reciprocal —— 两个机制是否同一批断面？
    S["_cell"] = S["radial"].astype(str) + " | recip=" + S["_recip"].astype(str)
    xrows = []
    for k, sub in S.dropna(subset=["radial"]).groupby("_cell"):
        o = float(sub["obs_8_9"].sum()); s = float(sub["sim_8_9_scaled"].sum())
        if o > 0:
            xrows.append({"cell": k, "n_sections": int(len(sub)), "obs_total": o,
                          "ratio_pooled": s / o, "rel_dev_vs_global": s / o / g_all - 1.0})
    xdf = pd.DataFrame(xrows).sort_values("rel_dev_vs_global")
    xdf.to_csv(OUT / "c0_4_radial_x_reciprocal.csv", index=False, encoding="utf-8-sig")
    print("\n  radial × reciprocal 交叉（分离两个机制）：")
    print(xdf.to_string(index=False, float_format=lambda v: f"{v:,.4f}"))
    art["c04_cross"] = xdf

    # ======================================================================
    # C0-5 长度归一化
    # ======================================================================
    banner("[7/7] C0-5 长度归一化（q/L）")
    L = pd.to_numeric(S["section_length_m"], errors="coerce")
    ok = L.notna() & (L > 0)
    per_km = S[ok].copy()
    per_km["sim_per_km"] = per_km["sim_8_9_scaled"] / L[ok]
    per_km["obs_per_km"] = per_km["obs_8_9"] / L[ok]
    per_km["ratio_per_km"] = per_km["sim_per_km"] / per_km["obs_per_km"]
    abs_ratio_global = g_all
    abs_mean = wmean(S[VCOL], S[WCOL])
    len_ratio_global = float(per_km["sim_per_km"].sum() / per_km["obs_per_km"].sum())
    len_mean = wmean(per_km["ratio_per_km"], per_km["obs_per_km"])
    # 逐 region：绝对 vs 归一化 的残差对比
    lr_rows = []
    for k, sub in per_km.groupby("region"):
        o = float(sub["obs_per_km"].sum()); s = float(sub["sim_per_km"].sum())
        ab = S[S["region"] == k]
        lr_rows.append({"region": k, "n_sections": int(len(sub)),
                        "rel_dev_absolute": float(ab["sim_8_9_scaled"].sum() / ab["obs_8_9"].sum()) / abs_ratio_global - 1.0,
                        "rel_dev_per_km": (s / o) / len_ratio_global - 1.0})
    lres = pd.DataFrame(lr_rows)
    lres["shrink_pp"] = (lres["rel_dev_absolute"].abs() - lres["rel_dev_per_km"].abs()) * 100.0
    lres.to_csv(OUT / "c0_5_length_normalized_by_region.csv", index=False, encoding="utf-8-sig")
    print(lres.to_string(index=False, float_format=lambda v: f"{v:,.4f}"))
    spread_abs = float(lres["rel_dev_absolute"].abs().max())
    spread_len = float(lres["rel_dev_per_km"].abs().max())
    ck("C0-5a 长度归一化后区域残差极差（是否收缩）", True,
       f"绝对={spread_abs:.4%} → 每km={spread_len:.4%}（Δ={100*(spread_abs-spread_len):+.2f} pp）")
    art["c05_len"] = lres

    # ======================================================================
    # C0-6 PA / Region 空间梯度
    # ======================================================================
    banner("[8/8] C0-6 PA / Region 残差空间梯度")
    pa_rows = []
    for pa, sub in S.dropna(subset=["pa"]).groupby("pa"):
        o = float(sub["obs_8_9"].sum()); s = float(sub["sim_8_9_scaled"].sum())
        if o <= 0:
            continue
        ln = pd.to_numeric(sub["section_length_m"], errors="coerce")
        mwlen = pd.to_numeric(sub.loc[sub["dominant_highway"].isin(["motorway", "motorway_link"]),
                                      "section_length_m"], errors="coerce")
        pa_rows.append({"pa": pa, "n_sections": int(len(sub)),
                        "R_PA": s / o / g_all - 1.0,
                        "mean_d_cbd_m": float(np.nanmean(sub["d_cbd_m"])),
                        "road_len_m": float(np.nansum(ln)),
                        "motorway_len_m": float(np.nansum(mwlen))})
    pa_df = pd.DataFrame(pa_rows)
    # OD inflow / outflow per PA
    zone["_pa"] = zone["planning_area"].astype(str).str.strip().str.upper()
    od = pd.read_csv(OD_CSV, encoding="utf-8-sig")
    zmap = zone.set_index("zone_id")["_pa"].to_dict()
    od["_o_pa"] = od["origin_zone"].map(zmap)
    od["_d_pa"] = od["destination_zone"].map(zmap)
    out_flow = od.groupby("_o_pa")["trips"].sum().rename("od_outflow")
    in_flow = od.groupby("_d_pa")["trips"].sum().rename("od_inflow")
    pa_df["pa_u"] = pa_df["pa"].astype(str).str.strip().str.upper()
    pa_df = pa_df.merge(out_flow, left_on="pa_u", right_index=True, how="left") \
                 .merge(in_flow, left_on="pa_u", right_index=True, how="left")
    pa_df["net_inflow_ratio"] = pa_df["od_inflow"] / pa_df["od_outflow"]
    pa_df.to_csv(OUT / "c0_6_pa_gradient.csv", index=False, encoding="utf-8-sig")
    grad_rows = []
    for col in ("mean_d_cbd_m", "road_len_m", "motorway_len_m", "od_outflow", "od_inflow", "net_inflow_ratio"):
        m = pa_df[col].notna() & pa_df["R_PA"].notna()
        if m.sum() >= 8:
            grad_rows.append({"variable": col, "n_pa": int(m.sum()),
                              "spearman_vs_R_PA": float(pd.Series(pa_df.loc[m, col]).corr(
                                  pd.Series(pa_df.loc[m, "R_PA"]), method="spearman"))})
    grad = pd.DataFrame(grad_rows).sort_values("spearman_vs_R_PA")
    grad.to_csv(OUT / "c0_6_pa_gradient_correlations.csv", index=False, encoding="utf-8-sig")
    print("  PA 级 R_PA 与空间/网络量相关性（Spearman）：")
    print(grad.to_string(index=False, float_format=lambda v: f"{v:,.4f}"))
    # 逐断面 距 CBD 梯度
    dd = S.dropna(subset=["d_cbd_m"])
    r_d = float(pd.Series(dd["d_cbd_m"]).corr(pd.Series(dd[VCOL]), method="spearman"))
    ck("C0-6a 逐断面 ratio vs 距CBD（Spearman）", True, f"ρ={r_d:+.4f}（n={len(dd)}）")
    art["c06_pa"] = pa_df

    # ======================================================================
    # 归因排序（obs 加权 η²，边际）
    # ======================================================================
    banner("[9/9] 归因排序 —— 各维度 obs 加权 η²（边际解释份额）")
    N_eff = int(S[WCOL].notna().sum())
    LAYER = {
        "region": "region_location", "pa": "pa_location",
        "ring": "distance_impedance", "distance_ring": "distance_impedance",
        "radial": "directionality",
        "_nlink_bucket": "section_crosswalk", "matched_link_count": "section_crosswalk",
        "_shared_bucket": "section_crosswalk", "shared_section_count": "section_crosswalk",
        "_recip": "network_topology_twin", "has_reciprocal_pair": "network_topology_twin",
        "_mixed": "network_representation", "has_mixed_highway": "network_representation",
        "dominant_highway": "road_class", "roadclass": "road_class", "RoadCat": "observation_semantics",
    }
    eta_rows = []
    for col, name in (("region", "region"), ("radial", "radial"),
                      ("dominant_highway", "roadclass"), ("RoadCat", "RoadCat"),
                      ("_nlink_bucket", "matched_link_count"), ("_shared_bucket", "shared_section_count"),
                      ("_recip", "has_reciprocal_pair"), ("_mixed", "has_mixed_highway"),
                      ("ring", "ring"), ("pa", "pa")):
        if col not in S.columns:
            continue
        e = eta2(S, col)
        if np.isfinite(e):
            k = int(S[col].nunique(dropna=True))
            eta_rows.append({"dimension": name, "layer": LAYER.get(name, name),
                             "eta2": e, "n_groups": k,
                             "eta2_chance": (k - 1) / max(N_eff - 1, 1),
                             "eta2_excess": e - (k - 1) / max(N_eff - 1, 1)})
    eta = pd.DataFrame(eta_rows).sort_values("eta2_excess", ascending=False)
    # 逐断面 d_cbd 梯度（连续）→ 按距离环 η²
    S["_dring"] = pd.cut(pd.to_numeric(S["d_cbd_m"], errors="coerce"),
                         bins=[0, 2000, 4000, 6000, 9000, 13000, 1e9],
                         labels=["0-2km", "2-4km", "4-6km", "6-9km", "9-13km", "13km+"])
    e_d = eta2(S, "_dring")
    if np.isfinite(e_d):
        k = int(S["_dring"].nunique())
        eta = pd.concat([eta, pd.DataFrame([{"dimension": "distance_ring", "layer": LAYER["distance_ring"],
                                             "eta2": e_d, "n_groups": k,
                                             "eta2_chance": (k - 1) / max(N_eff - 1, 1),
                                             "eta2_excess": e_d - (k - 1) / max(N_eff - 1, 1)}])],
                        ignore_index=True)
        eta = eta.sort_values("eta2_excess", ascending=False)
    eta.to_csv(OUT / "c0_rank_eta2.csv", index=False, encoding="utf-8-sig")
    print(eta.to_string(index=False, float_format=lambda v: f"{v:,.4f}"))

    top = eta.iloc[0]["dimension"] if len(eta) else "NA"
    layer_best = (eta.groupby("layer")["eta2_excess"].max()
                  .sort_values(ascending=False)) if len(eta) else pd.Series(dtype=float)
    mech_top = str(eta.iloc[0]["layer"]) if len(eta) else "NA"
    mechanisms = (eta[eta["eta2_excess"] >= 0.03]["layer"].drop_duplicates().tolist()
                  if len(eta) else [])
    excluded = (eta[eta["eta2_excess"] <= 0.005]["layer"].drop_duplicates().tolist()
                if len(eta) else [])
    print("\n  按「层」聚合最大 excess-η²：")
    print(layer_best.to_string(float_format=lambda v: f"{v:,.4f}"))
    print(f"  机制层（excess-η² ≥ 0.03）：{mechanisms}")
    print(f"  排除层（excess-η² ≤ 0.005）：{excluded}")
    if len(eta) and eta.iloc[0]["eta2_excess"] >= 0.20:
        verdict = f"RESIDUAL_LOCALIZED_TO_{mech_top.upper()}"
    elif len(eta) and eta.iloc[0]["eta2_excess"] >= 0.08:
        verdict = f"RESIDUAL_PARTIALLY_LOCALIZED_TO_{mech_top.upper()}"
    else:
        verdict = "RESIDUAL_NOT_SINGLE_FACTOR"
    print(f"\n   VERDICT: {verdict}  (top excess-η²={top} / layer={mech_top} "
          f"{float(eta.iloc[0]['eta2_excess']):.4f})" if len(eta) else "")

    # ---- 落盘汇总 --------------------------------------------------------
    npass = sum(1 for c in _ck if c["pass"])
    payload = {
        "step": "7.7C-0",
        "title": "Spatial residual attribution baseline audit",
        "verdict": verdict,
        "verdict_layer": mech_top,
        "mechanism_layers": mechanisms,
        "excluded_layers": excluded,
        "layer_ranking": layer_best.to_dict(),
        "zero_simulation": True, "matsim_rerun": False,
        "frozen_untouched": ["7.1_obs", "7.3.6A_crosswalk", "OD", "network", "capacity"],
        "working_point": {"lambda_ref": H.LAM_REF, "f_ref": H.F_REF, "n_sim": H.N_SIM,
                          "scale": float(bt.SCALE)},
        "baseline": {"SimObs_FROZEN": simobs, "ref": simobs_ref,
                     "east": east, "radial_in": rin, "north_east": ne},
        "eta2_ranking": eta.to_dict(orient="records"),
        "c0_1_region": c01.to_dict(orient="records"),
        "c0_2_radial": t_radial.to_dict(orient="records"),
        "c0_2_stability": stab.to_dict(orient="records") if not stab.empty else [],
        "c0_3_roadclass": t_hw.to_dict(orient="records"),
        "c0_3_roadcat": t_rc.to_dict(orient="records"),
        "c0_3_mainline_vs_link": mwdf.to_dict(orient="records"),
        "c0_4_topology": topo.to_dict(orient="records"),
        "c0_4_radial_x_reciprocal": xdf.to_dict(orient="records"),
        "c0_4_correlations": corr.to_dict(orient="records"),
        "c0_5_length_norm": lres.to_dict(orient="records"),
        "c0_6_pa_gradient_correlations": grad.to_dict(orient="records"),
        "c0_6_section_vs_dcbd_spearman": r_d,
        "checks_total": len(_ck), "checks_pass": npass, "checks": _ck,
        "runtime_sec": round(time.time() - t0, 1),
        "artifacts": sorted(p.name for p in OUT.glob("c0_*")),
    }
    (OUT / "step7_7c0_summary.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(f"\n   校验 {npass}/{len(_ck)} PASS   产物 {len(payload['artifacts'])} 个 -> {OUT}")
    for c in _ck:
        if not c["pass"]:
            print(f"   FAIL: {c['check']}  {c['detail']}")
    return 0 if (dmax < 1e-12 and abs(simobs - simobs_ref) < 1e-9) else 1


if __name__ == "__main__":
    sys.exit(main())
