#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Step 7.6C -- OD spatial-structure diagnosis (ZERO-SIMULATION, READ-ONLY)
=======================================================================

Position in the pipeline
------------------------
7.6E   route-choice layer FROZEN (STABILITY_PASS 6/6)
7.6F-0 new stable base, demand = 1.00  ->  MATCHED Sim/Obs = 0.8590
7.6C   <-- this step: is the *SHAPE* of the OD trustworthy?
       (deliberately decoupled from the *absolute scale* question)

User ruling (2026-09-17): run 7.6C first, zero-simulation, no parameter change,
no demand-scale selection, no lambda selection; then decide on 7.6F-1.

Three diagnostic axes
---------------------
Part 1  OD distance structure (NORMALISED: shares / quantiles / tails /
        within-band concentration).  Never a total-amount judgement.
Part 2  Spatial concentration & dispersion + **the spatial structure of the
        0.8590 shortfall** -- "everywhere uniformly short" or
        "some spatial relations are systematically wrong"?
Part 3  Pre-routing OD structure vs post-routing section structure --
        mass-conservation chain / realised route distance vs impedance
        distance / localisation of the spatial redistribution.

Hard discipline
---------------
* NEVER starts MATSim, NEVER writes to any frozen artefact
* does not select demand scale, does not select lambda
* evaluation calibers **imported** from the frozen module
  ``compare_final_crosswalk_7_3_6b`` (byte-identical lineage)
* window discipline: Sim/Obs uses ``HRS8-9avg``; the 7.6E stability audit uses
  ``HRS0-24avg`` -- the two are NEVER conflated

Outputs -> reports/od_structure_7_6c/
"""

from __future__ import annotations

import argparse
import gzip
import json
import sys
import time
import xml.etree.ElementTree as ET
from pathlib import Path

import numpy as np
import pandas as pd

# --------------------------------------------------------------------------
# frozen module import (byte-identical evaluation lineage)
# --------------------------------------------------------------------------
HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import compare_final_crosswalk_7_3_6b as bt  # noqa: E402  (frozen lineage)

ROOT = Path(r"D:\Luan\2026-05\2_Singapore")

# ---------------- frozen inputs (read-only) -------------------------------
OD_PARQUET = ROOT / "reports" / "matsim_population" / "car_prior_od_lambda_0p075.parquet"
IMP_FREEFLOW = ROOT / "reports" / "od_impedance" / "impedance_matrix.parquet"
IMP_AMPEAK = ROOT / "reports" / "od_impedance_ampeak_v2" / "ampeak_impedance_v2.parquet"
ZONE_DICT = ROOT / "reports" / "od_zone" / "zone_dictionary.csv"
PRODUCTION = ROOT / "reports" / "od_production" / "production.csv"
ATTRACTION = ROOT / "reports" / "od_attraction_v21" / "attraction_v21.csv"
NET_NODES = ROOT / "reports" / "od_impedance" / "network_nodes.csv"
NET_LINKS = ROOT / "reports" / "od_impedance" / "network_links.csv"
CROSSWALK = ROOT / "reports" / "od_final_calibration_crosswalk_7_3_6" / "final_calibration_crosswalk.csv"
T118 = ROOT / "Singapore_OD_MATSim_FinalData" / "03_Workplace_Employment" / "outputFile (3)__T11.csv"
T10_COMMUTE = ROOT / "Singapore_OD_MATSim_FinalData" / "03_Workplace_Employment" / "outputFile (3)__T10.csv"
AGENT_ASSIGN = ROOT / "reports" / "matsim_population_6_2b_connected" / "agent_spatial_assignment_lambda_0p075.csv"
BACKTEST_7_6F0 = ROOT / "reports" / "od_calibration_7_6f" / "demand_scale_7_6f_0_backtest.csv"
CYCLE_LINKSTATS = ROOT / "reports" / "od_calibration_7_6f" / "_cycle_linkstats" / "R01_conv.linkstats.txt.gz"
R01_OUT = ROOT / "matsim_routechoice_7_6d" / "outputs" / "R01_rc_min"

OUT_DIR = ROOT / "reports" / "od_structure_7_6c"

# ---------------- frozen constants ----------------------------------------
REAL_CAR_OD_TOTAL = 459794.0
N_ZONE = 332
N_CELL = 71136
N_IMP_PAIRS = N_ZONE * N_ZONE
N_AGENT = 200000
ANCHOR_SIM_OBS = 0.8590  # 7.6F-0 R01 demand=1.00 MATCHED Primary (08-09)

DIST_BANDS = [
    ("B1_0-2", 0.0, 2.0),
    ("B2_2-5", 2.0, 5.0),
    ("B3_5-10", 5.0, 10.0),
    ("B4_10-15", 10.0, 15.0),
    ("B5_15-20", 15.0, 20.0),
    ("B6_20-30", 20.0, 30.0),
    ("B7_30-40", 30.0, 40.0),
    ("B8_40+", 40.0, float("inf")),
]
DIST_EDGES = [b[1] for b in DIST_BANDS] + [float("inf")]
DIST_LABELS = [b[0] for b in DIST_BANDS]

TIME_BANDS = [
    ("T1_0-15", 0.0, 15.0),
    ("T2_15-30", 15.0, 30.0),
    ("T3_30-45", 30.0, 45.0),
    ("T4_45-60", 45.0, 60.0),
    ("T5_60+", 60.0, float("inf")),
]
SML_BANDS = [("short_le5km", 0.0, 5.0), ("medium_5_15km", 5.0, 15.0), ("long_gt15km", 15.0, float("inf"))]

RING_EDGES = [0.0, 5000.0, 10000.0, 15000.0, 20000.0, float("inf")]
RING_LABELS = ["R1_0-5km", "R2_5-10km", "R3_10-15km", "R4_15-20km", "R5_20km+"]

# ---------------- PRE-REGISTERED CRITERIA (frozen BEFORE the run) ---------
PREREGISTERED = {
    "note": ("7.6C 只做结构诊断；判据在跑之前固定，禁止事后调阈值。"
             "所有判据只看归一化结构/一致性，不涉及 demand scale 选择。"),
    "S1_mass_conservation": "|sum(agent od_trips) - 459794| < 1e-4 且 agent 数 == 200000",
    "S2_distance_decay": "share(B6) >= share(B7) >= share(B8) 且 share(B8_40+) < 0.02",
    "S3_short_band_dominance": "share(B1..B3) > 0.55",
    "S4_shortfall_uniformity": "各 Planning Region obs-加权 ratio 相对全局的相对偏差 max < 0.25",
    "S5_table118_satisfaction": "model vs census share 残差 中位 < 0.02 且 P95 < 0.10",
    "S6_zone_absorption_anomaly": "z(|log(A_j/employment)|) > 5 的区域数 == 0",
    "S7_detour_factor": "1.00 <= weighted_mean(realised_m / planned_m) <= 1.35",
}

CHECKS: list = []


def chk(name, value, ok, expected="", note=""):
    if isinstance(value, (np.floating, np.integer)):
        value = float(value)
    elif isinstance(value, (np.bool_,)):
        value = bool(value)
    CHECKS.append({"check": name, "value": value, "ok": bool(ok),
                   "expected": expected, "note": note})


def log(msg=""):
    print(msg, flush=True)


def banner(msg):
    log("")
    log("=" * 78)
    log(msg)
    log("=" * 78)


# ==========================================================================
# helpers
# ==========================================================================


def gini(x):
    x = np.asarray(x, dtype=float)
    x = x[np.isfinite(x)]
    if x.size == 0 or x.sum() <= 0:
        return float("nan")
    x = np.sort(x)
    n = x.size
    cum = np.cumsum(x)
    return float((n + 1.0 - 2.0 * np.sum(cum) / cum[-1]) / n)


def hhi(shares):
    s = np.asarray(shares, dtype=float)
    s = s[np.isfinite(s)]
    return float(np.sum(s * s)) if s.size else float("nan")


def topk_share(values, k):
    v = np.asarray(values, dtype=float)
    v = v[np.isfinite(v)]
    if v.size == 0 or v.sum() <= 0:
        return float("nan")
    v = np.sort(v)[::-1]
    return float(v[:max(1, int(k))].sum() / v.sum())


def band_table(df, vcol, wcol, bands, unit):
    v = df[vcol].to_numpy(dtype=float)
    w = df[wcol].to_numpy(dtype=float)
    tot_w = float(np.nansum(w))
    ok = np.isfinite(v)
    tot_pairs = int(ok.sum())
    rows = []
    for name, lo, hi in bands:
        m = (v >= lo) & (v < hi) if np.isfinite(hi) else (v >= lo) & ok
        m = m & ok
        bsum = float(np.nansum(w[m]))
        rows.append({
            "band": name, "lo": lo, "hi": (None if not np.isfinite(hi) else hi), "unit": unit,
            "demand_trips": bsum,
            "demand_share": (bsum / tot_w) if tot_w > 0 else float("nan"),
            "pair_count": int(m.sum()),
            "pair_share": (float(m.sum()) / tot_pairs) if tot_pairs else float("nan"),
        })
    out = pd.DataFrame(rows)
    out["concentration_ratio"] = out["demand_share"] / out["pair_share"].replace(0, np.nan)
    out["cum_demand_share"] = out["demand_share"].cumsum()
    return out


def wquant(values, weights, qs):
    v = np.asarray(values, dtype=float)
    w = np.asarray(weights, dtype=float)
    m = np.isfinite(v) & np.isfinite(w) & (w > 0)
    v, w = v[m], w[m]
    if v.size == 0:
        return {f"p{int(round(q*100))}": float("nan") for q in qs}
    o = np.argsort(v)
    v, w = v[o], w[o]
    cw = np.cumsum(w)
    cw = cw / cw[-1]
    return {f"p{int(round(q*100))}": float(np.interp(q, cw, v)) for q in qs}


def wmean(values, weights):
    v = np.asarray(values, dtype=float)
    w = np.asarray(weights, dtype=float)
    m = np.isfinite(v) & np.isfinite(w) & (w > 0)
    if not m.any():
        return float("nan")
    return float(np.average(v[m], weights=w[m]))


def agg_ratio(df, key, obs="obs_8_9", sim="sim_8_9_scaled", ratio="ratio_8_9"):
    """Version-safe grouped aggregation of section residuals."""
    rows = []
    for k, x in df.dropna(subset=[key]).groupby(key):
        o = float(x[obs].sum())
        s = float(x[sim].sum())
        rows.append({
            key: k, "n_sections": int(len(x)),
            "obs_total": o, "sim_total": s,
            "ratio_pooled": (s / o) if o > 0 else float("nan"),
            "ratio_obs_weighted": wmean(x[ratio].to_numpy(), x[obs].to_numpy()),
            "ratio_median": float(x[ratio].median()),
        })
    g = pd.DataFrame(rows)
    if len(g):
        g = g.sort_values("ratio_obs_weighted")
    return g


# ==========================================================================
# Part 0 -- load & assert
# ==========================================================================


def load_all(skip_plans: bool):
    banner("Part 0 -- load frozen artefacts and assert calibers")

    od = pd.read_parquet(OD_PARQUET).rename(columns={"trips": "T_ij"})
    assert list(od.columns) == ["origin_zone", "destination_zone", "T_ij"], od.columns
    assert len(od) == N_CELL, f"OD cells {len(od)} != {N_CELL}"
    assert abs(od["T_ij"].sum() - REAL_CAR_OD_TOTAL) < 1.0, od["T_ij"].sum()
    log(f"OD             : {len(od):,} cells, Sum(T_ij) = {od['T_ij'].sum():,.3f}")

    imp = pd.read_parquet(IMP_FREEFLOW).rename(columns={"distance_m": "d_ff_m"})
    assert len(imp) == N_IMP_PAIRS, len(imp)
    log(f"impedance (ff) : {len(imp):,} pairs, distance_m present")

    amp = pd.read_parquet(IMP_AMPEAK).rename(columns={"travel_time_min": "tt_am_min"})
    assert len(amp) == N_IMP_PAIRS, len(amp)
    log(f"impedance (AM) : {len(amp):,} pairs, travel_time_min present")

    zd = pd.read_csv(ZONE_DICT)
    assert len(zd) == N_ZONE, len(zd)
    log(f"zone dictionary: {len(zd)} zones / {zd['planning_area'].nunique()} PAs / "
        f"{zd['planning_region'].nunique()} regions :: {sorted(zd['planning_region'].unique())}")

    prod = pd.read_csv(PRODUCTION)
    attr = pd.read_csv(ATTRACTION)
    assert len(prod) == N_ZONE and len(attr) == N_ZONE, (len(prod), len(attr))

    df = od.merge(imp[["origin_zone", "destination_zone", "d_ff_m"]],
                  on=["origin_zone", "destination_zone"], how="left")
    df = df.merge(amp[["origin_zone", "destination_zone", "tt_am_min"]],
                  on=["origin_zone", "destination_zone"], how="left")
    assert df["d_ff_m"].notna().all() and df["tt_am_min"].notna().all(), "unmatched impedance"

    zc = zd[["zone_id", "planning_area", "planning_region", "subzone_name",
             "centroid_x_svy21_m", "centroid_y_svy21_m", "centroid_lon", "centroid_lat",
             "area_m2"]].copy()
    df = df.merge(zc.add_prefix("o_").rename(columns={"o_zone_id": "origin_zone"}),
                  on="origin_zone", how="left")
    df = df.merge(zc.add_prefix("d_").rename(columns={"d_zone_id": "destination_zone"}),
                  on="destination_zone", how="left")
    assert df["o_planning_region"].notna().all() and df["d_planning_area"].notna().all()

    # c_ii proxy (project convention: 0.5 x median centroid distance to the 5 nearest OTHER zones)
    zs = zd.sort_values("zone_id")
    zids = zs["zone_id"].to_numpy(int)
    cxy = zs[["centroid_x_svy21_m", "centroid_y_svy21_m"]].to_numpy(float)
    dm = np.linalg.norm(cxy[:, None, :] - cxy[None, :, :], axis=2)
    np.fill_diagonal(dm, np.inf)
    idx = np.argsort(dm, axis=1)[:, :5]
    cii = 0.5 * np.median(np.take_along_axis(dm, idx, axis=1), axis=1)
    cii_map = dict(zip(zids.tolist(), cii.tolist()))

    df["is_intra"] = df["origin_zone"] == df["destination_zone"]
    df["d_ff_cii_m"] = df["d_ff_m"].where(~df["is_intra"], df["origin_zone"].map(cii_map))
    df["d_ff_km"] = df["d_ff_m"] / 1000.0
    df["d_ff_cii_km"] = df["d_ff_cii_m"] / 1000.0
    log(f"cells merged   : {len(df):,}; intra-zone {int(df['is_intra'].sum()):,} carrying "
        f"{df.loc[df['is_intra'],'T_ij'].sum()/REAL_CAR_OD_TOTAL:.2%} of demand")
    log(f"c_ii proxy     : median {np.median(cii)/1000:.2f} km (0.5 x 5-NN centroid distance)")

    cz = pd.read_csv(AGENT_ASSIGN, usecols=[
        "agent_id", "origin_zone", "destination_zone", "od_trips", "expansion_factor"])
    log(f"agent assign   : {len(cz):,} agents, Sum(od_trips) = {cz['od_trips'].sum():,.4f}")
    log(f"SCALE          : frozen-module bt.SCALE = {bt.SCALE:.5f}  "
        f"(459794/200000 = {REAL_CAR_OD_TOTAL/N_AGENT:.5f})")

    cw = pd.read_csv(CROSSWALK)
    cw_prim = cw[cw["is_primary_candidate"]] if "is_primary_candidate" in cw.columns else cw
    log(f"crosswalk      : {len(cw):,} rows, primary {len(cw_prim):,}, "
        f"{cw['lta_linkid'].nunique()} unique LTA sections")

    bt_df = pd.read_csv(BACKTEST_7_6F0)
    log(f"7.6F-0 backtest: {len(bt_df):,} rows, runs = {sorted(bt_df['run'].unique())}")

    plans = None if skip_plans else parse_realized_plans()

    return dict(df=df, od=od, zd=zd, prod=prod, attr=attr, cz=cz, cw=cw,
                cw_prim=cw_prim, bt_df=bt_df, plans=plans, cii=cii_map)


# ==========================================================================
# Part 1 -- OD distance structure (normalised)
# ==========================================================================


def part1(d, out):
    banner("Part 1 -- OD distance structure (normalised)")
    df = d["df"]
    qs = [0.05, 0.10, 0.25, 0.50, 0.75, 0.90, 0.95, 0.99]

    specs = [
        ("demand-weighted | free-flow network distance", "d_ff_km", "T_ij", "km"),
        ("demand-weighted | c_ii proxy for intra-zone", "d_ff_cii_km", "T_ij", "km"),
        ("demand-weighted | AM travel time", "tt_am_min", "T_ij", "min"),
        ("pair-count | all OD cells equally weighted", "d_ff_km", None, "km"),
        ("pair-count | c_ii proxy", "d_ff_cii_km", None, "km"),
    ]
    rows = []
    for label, vc, wc, unit in specs:
        v = df[vc].to_numpy(float)
        w = df[wc].to_numpy(float) if wc else np.ones(len(df))
        r = {"scope": label, "unit": unit,
             "n_cells": int(np.isfinite(v).sum()),
             "mean": wmean(v, w),
             "max": float(np.nanmax(v))}
        r.update(wquant(v, w, qs))
        rows.append(r)
    stats = pd.DataFrame(rows)
    stats.to_csv(out / "od_distance_stats.csv", index=False, encoding="utf-8-sig")
    log(stats.to_string(index=False))
    S = {r["scope"]: r for r in rows}

    bd = band_table(df, "d_ff_cii_km", "T_ij", DIST_BANDS, "km")
    bd_raw = band_table(df, "d_ff_km", "T_ij", DIST_BANDS, "km")
    bd.to_csv(out / "od_distance_bands.csv", index=False, encoding="utf-8-sig")
    bd_raw.to_csv(out / "od_distance_bands_rawcii.csv", index=False, encoding="utf-8-sig")
    log("")
    log("distance bands (c_ii proxy for intra-zone):")
    log(bd[["band", "demand_trips", "demand_share", "pair_share",
            "concentration_ratio", "cum_demand_share"]].to_string(index=False))

    sml = band_table(df, "d_ff_cii_km", "T_ij", SML_BANDS, "km")
    sml.to_csv(out / "od_short_med_long.csv", index=False, encoding="utf-8-sig")
    log("")
    log("short / medium / long split:")
    log(sml[["band", "demand_share", "pair_share", "concentration_ratio"]].to_string(index=False))

    # ---- AM travel-time bands vs Census T10 ------------------------------------
    tb = band_table(df, "tt_am_min", "T_ij", TIME_BANDS, "min")
    census = parse_t10_commute_bands()
    comp = tb[["band", "demand_share"]].rename(columns={"demand_share": "model_AM_share"})
    comp = comp.merge(census, on="band", how="outer")
    comp["ratio_model_over_census"] = comp["model_AM_share"] / comp["census_share"]
    comp.to_csv(out / "od_time_bands_vs_census_T10.csv", index=False, encoding="utf-8-sig")
    log("")
    log("AM travel-time bands vs Census T10 (ALL MODES -> caliber gap, reference only):")
    log(comp.to_string(index=False))

    # ---- tails ------------------------------------------------------------------
    tot = float(df["T_ij"].sum())
    g = bd.set_index("band")["demand_share"]
    tails = {
        "intra_zone_share": float(df.loc[df["is_intra"], "T_ij"].sum() / tot),
        "short_tail_le2km_share": float(g["B1_0-2"]),
        "long_tail_gt30km_share": float(g["B7_30-40"] + g["B8_40+"]),
        "long_tail_gt40km_share": float(g["B8_40+"]),
        "mean_km_demand_ff": S["demand-weighted | free-flow network distance"]["mean"] / 1.0,
        "mean_km_demand_cii": S["demand-weighted | c_ii proxy for intra-zone"]["mean"],
        "median_km_demand_cii": S["demand-weighted | c_ii proxy for intra-zone"]["p50"],
        "p95_km_demand_cii": S["demand-weighted | c_ii proxy for intra-zone"]["p95"],
        "mean_min_AM_demand": S["demand-weighted | AM travel time"]["mean"],
        "median_min_AM_demand": S["demand-weighted | AM travel time"]["p50"],
        "mean_km_paircount": S["pair-count | all OD cells equally weighted"]["mean"],
    }
    log("")
    log("tails/summary: " + json.dumps({k: round(float(v), 4) for k, v in tails.items()},
                                       ensure_ascii=False))

    # ---- sampling bias ----------------------------------------------------------
    cz = d["cz"].merge(df[["origin_zone", "destination_zone", "d_ff_cii_km"]],
                       on=["origin_zone", "destination_zone"], how="left")
    assert cz["d_ff_cii_km"].notna().all(), "agent cell not found in OD"
    ab = band_table(cz.rename(columns={"d_ff_cii_km": "d"}), "d", "expansion_factor",
                    DIST_BANDS, "km")
    bias = bd[["band", "demand_share"]].rename(columns={"demand_share": "od_matrix_share"})
    bias = bias.merge(ab[["band", "demand_share"]].rename(
        columns={"demand_share": "sampled_agent_share"}), on="band", how="left")
    bias["diff_pp"] = (bias["sampled_agent_share"] - bias["od_matrix_share"]) * 100.0
    bias.to_csv(out / "od_sampling_bias_by_band.csv", index=False, encoding="utf-8-sig")
    mean_od = wmean(df["d_ff_cii_km"], df["T_ij"])
    mean_ag = wmean(cz["d_ff_cii_km"], cz["expansion_factor"])
    log("")
    log("sampling bias (realised agents vs frozen OD matrix), band share diff (pp):")
    log(bias.to_string(index=False))
    log(f"  demand-weighted mean distance : OD matrix {mean_od:,.2f} km   vs   "
        f"sampled agents {mean_ag:,.2f} km   ({(mean_ag/mean_od-1)*100:+.2f}%)")

    chk("P1.od_cells", len(df), len(df) == N_CELL, "== 71136")
    chk("P1.od_total_trips", round(float(df["T_ij"].sum()), 3),
        abs(df["T_ij"].sum() - REAL_CAR_OD_TOTAL) < 1.0, "== 459794 (+-1)")
    chk("P1.all_cells_have_impedance", bool(df["d_ff_cii_km"].notna().all()), True, "no NaN")
    chk("P1.mean_km_cii_proxy_m", round(tails["mean_km_demand_cii"], 1), True,
        "informational (demand-weighted morning commute distance)")
    chk("S2.distance_decay",
        {k: round(float(g[k]), 5) for k in ["B6_20-30", "B7_30-40", "B8_40+"]},
        (g["B6_20-30"] >= g["B7_30-40"] >= g["B8_40+"]) and (g["B8_40+"] < 0.02),
        "non-increasing B6>=B7>=B8 and share(B8)<0.02")
    short3 = float(g[["B1_0-2", "B2_2-5", "B3_5-10"]].sum())
    chk("S3.short_band_dominance", round(short3, 4), short3 > 0.55, "share(B1..B3) > 0.55")

    return dict(stats=stats, bands=bd, bands_raw=bd_raw, sml=sml, time_bands=comp,
                tails=tails, bias=bias, mean_od=mean_od, mean_ag=mean_ag)


def parse_t10_commute_bands():
    raw = pd.read_csv(T10_COMMUTE, encoding="utf-8-sig")
    label = raw.columns[0]

    def find(pref):
        for c in raw.columns:
            if c.strip().lower().startswith(pref):
                return c
        return None

    mp = {"T1_0-15": find("up to 15"), "T2_15-30": find("16 - 30"),
          "T3_30-45": find("31 - 45"), "T4_45-60": find("46 - 60"),
          "T5_60+": find("more than 60")}
    missing = [k for k, v in mp.items() if v is None]
    if missing:
        raise ValueError(f"T10 bands not found {missing}; cols={list(raw.columns)[:12]}")
    body = raw[raw[label].astype(str).str.strip().str.lower() != "total"]
    s = {k: float(pd.to_numeric(body[v], errors="coerce").sum()) for k, v in mp.items()}
    den = sum(s.values())
    return pd.DataFrame({"band": list(s.keys()),
                         "census_share": [s[k] / den for k in s]})


def build_table118():
    """Census Table 118 == T11 in 03_Workplace_Employment (residence region x workplace PA)."""
    raw = pd.read_csv(T118, encoding="utf-8-sig", low_memory=False)
    label = raw.columns[0]
    region_cols = [c for c in raw.columns
                   if c.strip().endswith("_Total") and not c.strip().lower().startswith("total")]
    if not region_cols:
        raise ValueError(f"Table118 region columns not found; cols={list(raw.columns)[:12]}")
    body = raw[raw[label].astype(str).str.strip().str.lower() != "total"]
    recs = []
    for _, r in body.iterrows():
        pa = str(r[label]).strip()
        for rc in region_cols:
            v = pd.to_numeric(r[rc], errors="coerce")
            if pd.notna(v):
                recs.append({"residence_region": rc.replace("_Total", "").strip().upper(),
                             "workplace_pa": pa.upper(),
                             "census_trips": float(v)})
    q = pd.DataFrame(recs)
    q["census_share"] = q["census_trips"] / q.groupby("residence_region")["census_trips"].transform("sum")
    return q


# ==========================================================================
# Part 2 -- spatial concentration / dispersion
# ==========================================================================


def part2(d, out, p1):
    banner("Part 2 -- spatial concentration / dispersion + shortfall structure")
    df, zd, prod, attr = d["df"], d["zd"], d["prod"], d["attr"]
    tot = float(df["T_ij"].sum())

    P = prod[["zone_id", "car_work_trip_production"]].rename(
        columns={"car_work_trip_production": "P_i"})
    A = attr[["zone_id", "workplace_employment", "workplace_attraction",
              "weight_fallback_used", "share_over_50pct", "share_over_60pct",
              "acra_enterprise_count"]].rename(columns={"workplace_attraction": "A_j"})
    rowsum = df.groupby("origin_zone", as_index=False)["T_ij"].sum().rename(
        columns={"origin_zone": "zone_id", "T_ij": "OD_rowsum"})
    colsum = df.groupby("destination_zone", as_index=False)["T_ij"].sum().rename(
        columns={"destination_zone": "zone_id", "T_ij": "OD_colsum"})

    Z = (zd[["zone_id", "subzone_name", "planning_area", "planning_region"]]
         .merge(P, on="zone_id", how="left")
         .merge(A, on="zone_id", how="left")
         .merge(rowsum, on="zone_id", how="left")
         .merge(colsum, on="zone_id", how="left"))
    Z[["OD_rowsum", "OD_colsum"]] = Z[["OD_rowsum", "OD_colsum"]].fillna(0.0)
    Z["P_share"] = Z["P_i"] / Z["P_i"].sum()
    Z["A_share"] = Z["A_j"] / Z["A_j"].sum()
    Z["rowsum_share"] = Z["OD_rowsum"] / tot
    Z["colsum_share"] = Z["OD_colsum"] / tot

    rows = []
    for level, key in [("SUBZONE", "zone_id"), ("PA", "planning_area"),
                       ("REGION", "planning_region")]:
        g = Z.groupby(key, as_index=False)[["P_i", "A_j", "OD_rowsum", "OD_colsum"]].sum()
        for col, lab in [("P_i", "P_i (car production)"), ("A_j", "A_j (attraction)"),
                         ("OD_rowsum", "T_ij row-sum (origin side)"),
                         ("OD_colsum", "T_ij col-sum (destination side)")]:
            v = g[col].to_numpy(float)
            sh = v / v.sum()
            rows.append({
                "level": level, "quantity": lab, "n_units": int(len(g)),
                "gini": gini(v), "hhi": hhi(sh), "cv": float(np.std(v) / np.mean(v)),
                "top1_share": topk_share(v, 1), "top5_share": topk_share(v, 5),
                "top10_share": topk_share(v, 10),
                "top20pct_share": topk_share(v, max(1, int(0.2 * len(g)))),
            })
    conc = pd.DataFrame(rows)
    conc.to_csv(out / "od_concentration_by_level.csv", index=False, encoding="utf-8-sig")
    log(conc.to_string(index=False))

    # ---- OD-cell concentration --------------------------------------------------
    t = df["T_ij"].to_numpy(float)
    nz = t > 0
    cells = {
        "n_cells_positive": int(nz.sum()),
        "n_cells_in_full_matrix": int(N_IMP_PAIRS),
        "density": float(nz.sum()) / float(N_IMP_PAIRS),
        "gini_positive_cells": gini(t[nz]),
        "hhi_positive_cells": hhi(t[nz] / t[nz].sum()),
        "top1pct_cell_share": topk_share(t[nz], 0.01 * nz.sum()),
        "top5pct_cell_share": topk_share(t[nz], 0.05 * nz.sum()),
        "top10pct_cell_share": topk_share(t[nz], 0.10 * nz.sum()),
        "max_cell_trips": float(t.max()),
        "p50_positive_cell_trips": float(np.median(t[nz])),
        "mean_positive_cell_trips": float(t[nz].mean()),
        "intra_zone_trips": float(t[df["is_intra"].to_numpy()].sum()),
        "intra_zone_share": float(t[df["is_intra"].to_numpy()].sum() / t.sum()),
    }
    log("")
    log("OD-cell concentration: " + json.dumps(
        {k: (round(v, 5) if isinstance(v, float) else v) for k, v in cells.items()},
        ensure_ascii=False))

    # ---- anomalous absorption ---------------------------------------------------
    Z["logA_over_emp"] = np.log(Z["A_j"] / Z["workplace_employment"].replace(0, np.nan))
    mu, sd = float(Z["logA_over_emp"].mean()), float(Z["logA_over_emp"].std())
    Z["A_emp_z"] = (Z["logA_over_emp"] - mu) / sd
    n_extreme = int((Z["A_emp_z"].abs() > 5).sum())
    cols = ["zone_id", "subzone_name", "planning_area", "planning_region", "A_j",
            "workplace_employment", "A_emp_z", "A_share", "OD_colsum", "colsum_share",
            "share_over_50pct", "weight_fallback_used"]
    top = Z.reindex(Z["A_emp_z"].abs().sort_values(ascending=False).index).head(15)
    top[cols].to_csv(out / "od_zone_absorption_anomalies.csv", index=False, encoding="utf-8-sig")
    Z.to_csv(out / "od_zone_marginals.csv", index=False, encoding="utf-8-sig")
    log("")
    log("most extreme absorption zones (|z| of log(A_j / workplace_employment)):")
    log(top[cols].head(8).to_string(index=False))
    log(f"zones with |z| > 5 : {n_extreme}")

    # ---- Table 118 satisfaction -------------------------------------------------
    ref = build_table118()
    mod = (df.groupby(["o_planning_region", "d_planning_area"], as_index=False)["T_ij"].sum()
           .rename(columns={"o_planning_region": "residence_region",
                            "d_planning_area": "workplace_pa", "T_ij": "model_trips"}))
    mod["residence_region"] = mod["residence_region"].astype(str).str.upper()
    mod["workplace_pa"] = mod["workplace_pa"].astype(str).str.upper()
    mod["model_share"] = mod["model_trips"] / mod.groupby("residence_region")[
        "model_trips"].transform("sum")
    res = mod.merge(ref, on=["residence_region", "workplace_pa"], how="outer")
    res["model_share"] = res["model_share"].fillna(0.0)
    res["census_share"] = res["census_share"].fillna(0.0)
    res["share_resid"] = res["model_share"] - res["census_share"]
    res["abs_share_resid"] = res["share_resid"].abs()
    res = res.sort_values("abs_share_resid", ascending=False)
    res.to_csv(out / "od_table118_residual.csv", index=False, encoding="utf-8-sig")
    # 7.6A discipline: the three non-physical buckets are NOT part of the road OD
    # (No Fixed Location for Work / Works from Home / Other-or-Outside), so they must
    # be excluded before judging the physical residence-region x workplace-PA structure.
    NON_PHYSICAL_KEYS = ("NO FIXED", "WORKS FROM HOME", "OUTSIDE", "NOT APPLICABLE")
    res["is_nonphysical"] = res["workplace_pa"].astype(str).str.upper().apply(
        lambda s: any(k in s for k in NON_PHYSICAL_KEYS))
    res_phys = res[~res["is_nonphysical"]].copy()
    med_res_all = float(res["abs_share_resid"].median())
    med_res = float(res_phys["abs_share_resid"].median())
    p95_res = float(res_phys["abs_share_resid"].quantile(0.95))
    max_res = float(res_phys["abs_share_resid"].max())
    unmatched_census = int(((res["model_trips"].isna()) & res["census_share"].gt(0)).sum())
    unmatched_model = int(((res["census_trips"].isna()) & res["model_share"].gt(0)).sum())
    nonphys_cells = int(res["is_nonphysical"].sum())
    log("")
    log(f"Table118 (residence-region x workplace-PA): {len(res)} cells "
        f"({nonphys_cells} non-physical excluded -> {len(res_phys)} physical); "
        f"PHYSICAL median|resid| = {med_res:.4f}, P95 = {p95_res:.4f}, max = {max_res:.4f}; "
        f"ALL-CELLS median|resid| = {med_res_all:.4f}; "
        f"model-only {unmatched_model}, census-only {unmatched_census}")
    log(res_phys.head(8)[["residence_region", "workplace_pa", "model_share",
                          "census_share", "share_resid"]].to_string(index=False))

    # ---- ★ spatial structure of the shortfall -----------------------------------
    short = shortfall_spatial_structure(d, out)

    chk("P2.colsum_identity", round(float(Z["OD_colsum"].sum() / tot - 1.0), 10),
        abs(Z["OD_colsum"].sum() / tot - 1.0) < 1e-9, "col-sums == OD total")
    chk("P2.od_cell_density", round(cells["density"], 5), True,
        "positive cells / 332^2 (informational; 71136/110224 = 0.6454)")
    chk("P2.n_positive_cells", cells["n_cells_positive"], cells["n_cells_positive"] == N_CELL,
        "== 71136")
    chk("S6.zone_absorption_anomaly", n_extreme, n_extreme == 0, "== 0 zones with |z|>5")
    chk("S5.table118_satisfaction_PHYSICAL",
        {"median": round(med_res, 5), "p95": round(p95_res, 5),
         "n_phys": len(res_phys)},
        (med_res < 0.02) and (p95_res < 0.10),
        "physical cells only; median<0.02 and P95<0.10")
    for r in short["rows"]:
        chk(f"S4.region_ratio.{r['key']}", round(r["ratio"], 4),
            abs(r["ratio"] / short["global_ratio"] - 1.0) < 0.25,
            f"within +-25% of global {short['global_ratio']:.4f}")
    chk("S4.region_ratio_max_rel_dev", round(short["max_rel_dev"], 4),
        short["max_rel_dev"] < 0.25, "< 0.25")
    chk("S4b.region_ratio_max_rel_dev_EXCL_zero_sim", round(short["max_rel_dev_pos"], 4),
        short["max_rel_dev_pos"] < 0.25,
        "robustness: the regional spread is NOT explained by the zero-sim sections")
    chk("P2.regions_all_below_parity", short["all_short"], True, "informational")
    chk("P2.zero_sim_sections", short["n_zero_sim"], True,
        "informational: sections with ZERO simulated flow but non-zero observation")
    chk("P2.obs_share_on_zero_sim", round(short["obs_share_zero"], 5), True,
        "informational: share of observed volume sitting on those sections")

    return dict(conc=conc, cells=cells, zones=Z, table118=res, table118_phys=res_phys,
                n_extreme=n_extreme, med_res=med_res, p95_res=p95_res,
                med_res_all=med_res_all, nonphys_cells=nonphys_cells,
                shortfall=short)


def cbd_xy(zd, attr):
    """CBD proxy: DOWNTOWN CORE centroid if present, else the max-attraction zone."""
    m = zd[zd["planning_area"].astype(str).str.upper().str.contains("DOWNTOWN")]
    if len(m):
        return (float(m["centroid_x_svy21_m"].mean()),
                float(m["centroid_y_svy21_m"].mean()),
                f"mean centroid of {len(m)} 'DOWNTOWN*' zone(s)")
    j = zd.merge(attr[["zone_id", "workplace_attraction"]], on="zone_id", how="left")
    k = j["workplace_attraction"].idxmax()
    return (float(j.loc[k, "centroid_x_svy21_m"]), float(j.loc[k, "centroid_y_svy21_m"]),
            f"max-attraction zone {int(j.loc[k,'zone_id'])}")


def shortfall_spatial_structure(d, out):
    """Where exactly does the 0.8590 shortfall live? Geography from MATSim link MIDPOINTS."""
    from scipy.spatial import cKDTree

    bt_df, cw, zd = d["bt_df"], d["cw_prim"], d["zd"]

    sub = bt_df[(bt_df["run"] == "R01") & (bt_df["caliber"] == "PRIMARY_cycle_10_19")].copy()
    sub = sub[["lta_linkid", "RoadCat", "RoadName", "obs_8_9", "sim_8_9_scaled", "ratio_8_9"]]
    n_zero_sim = int((sub["sim_8_9_scaled"] <= 0).sum())
    n_zero_obs = int((sub["obs_8_9"] <= 0).sum())
    global_ratio = wmean(sub["ratio_8_9"], sub["obs_8_9"])
    log("")
    log(f"shortfall core : {len(sub)} R01 PRIMARY-cycle sections; obs-weighted global "
        f"Sim/Obs = {global_ratio:.4f} (7.6F-0 anchor {ANCHOR_SIM_OBS}); "
        f"zero-sim sections = {n_zero_sim}, zero-obs = {n_zero_obs}")

    cbx, cby, src_note = cbd_xy(zd, d["attr"])
    log(f"CBD proxy (SVY21) = ({cbx:.0f}, {cby:.0f})  <- {src_note}")

    # ---- geometry: every MATSim link in the frozen crosswalk, from link MIDPOINTS ----
    nodes = pd.read_csv(NET_NODES)
    nxy = nodes.set_index("node_id")[["x_svy21_m", "y_svy21_m"]]
    cwrows = cw[["lta_linkid", "matsim_link_id"]].dropna(subset=["matsim_link_id"]).copy()
    cwrows["matsim_link_id"] = cwrows["matsim_link_id"].astype(str)
    need = set(cwrows["matsim_link_id"])

    links = pd.read_csv(NET_LINKS, usecols=["from_node", "to_node", "length_m"])
    links["matsim_link_id"] = ("e" + links["from_node"].astype(str) + "_"
                               + links["to_node"].astype(str))
    links = links[links["matsim_link_id"].isin(need)].copy()

    fx = links["from_node"].map(nxy["x_svy21_m"]).to_numpy(float)
    fy = links["from_node"].map(nxy["y_svy21_m"]).to_numpy(float)
    tx = links["to_node"].map(nxy["x_svy21_m"]).to_numpy(float)
    ty = links["to_node"].map(nxy["y_svy21_m"]).to_numpy(float)
    mx, my = (fx + tx) / 2.0, (fy + ty) / 2.0
    vx, vy = tx - fx, ty - fy
    rx, ry = cbx - mx, cby - my
    nv, nr = np.hypot(vx, vy), np.hypot(rx, ry)
    with np.errstate(invalid="ignore", divide="ignore"):
        cosang = (vx * rx + vy * ry) / (nv * nr)
    lg = pd.DataFrame({
        "matsim_link_id": links["matsim_link_id"].to_numpy(),
        "mid_x": mx, "mid_y": my, "d_cbd_m": nr,
        "length_m": links["length_m"].to_numpy(float),
        "radial": np.where(cosang > 0.35, "radial_in",
                           np.where(cosang < -0.35, "radial_out", "circumferential")),
    })
    lg["ring"] = pd.cut(lg["d_cbd_m"], RING_EDGES, labels=RING_LABELS, right=False)
    lg.to_csv(out / "link_ring_direction.csv", index=False, encoding="utf-8-sig")

    # per-section: mean matched-link midpoint + majority radial orientation
    cwr = cwrows.merge(lg, on="matsim_link_id", how="left")
    sec = (cwr.dropna(subset=["mid_x"])
           .groupby("lta_linkid")
           .agg(mid_x=("mid_x", "mean"), mid_y=("mid_y", "mean"),
                d_cbd_m=("d_cbd_m", "mean"), n_links=("matsim_link_id", "nunique"),
                radial=("radial", lambda s: s.mode().iat[0] if len(s.mode())
                        else "circumferential"))
           .reset_index())
    sec["ring"] = pd.cut(sec["d_cbd_m"], RING_EDGES, labels=RING_LABELS, right=False)

    zs = zd.sort_values("zone_id")
    tree = cKDTree(zs[["centroid_x_svy21_m", "centroid_y_svy21_m"]].to_numpy(float))
    _, nzi = tree.query(sec[["mid_x", "mid_y"]].to_numpy(float), k=1)
    sec["region"] = zs["planning_region"].to_numpy()[nzi]
    sec["pa"] = zs["planning_area"].to_numpy()[nzi]
    sec.to_csv(out / "section_geography.csv", index=False, encoding="utf-8-sig")

    sub = sub.merge(sec[["lta_linkid", "region", "pa", "ring", "radial", "d_cbd_m"]],
                    on="lta_linkid", how="left")
    n_geo = int(sub["region"].notna().sum())
    log(f"section geography: {n_geo}/{len(sub)} sections attributed by matched-link midpoint "
        f"({len(sec)} sections carry crosswalk geometry)")

    # ---- CRITICAL split: "no simulated flow at all" vs "genuinely too little flow" ----
    sub["zero_sim"] = sub["sim_8_9_scaled"] <= 0
    zero = sub[sub["zero_sim"]]
    obs_share_zero = float(zero["obs_8_9"].sum() / sub["obs_8_9"].sum())
    sub_pos = sub[~sub["zero_sim"]].copy()
    g_all = float(sub["sim_8_9_scaled"].sum() / sub["obs_8_9"].sum())
    g_pos = float(sub_pos["sim_8_9_scaled"].sum() / sub_pos["obs_8_9"].sum())
    log("")
    log(f"★ coverage split : {len(zero)} of {len(sub)} sections have ZERO simulated flow but "
        f"carry {zero['obs_8_9'].sum():,.0f} obs veh/h = {obs_share_zero:.2%} of the observed total")
    log(f"★ pooled Sim/Obs : all sections {g_all:.4f}  |  excluding zero-sim sections "
        f"{g_pos:.4f}  (+{(g_pos/g_all-1)*100:.2f}%)")

    by_region = agg_ratio(sub, "region")
    by_roadcat = agg_ratio(sub, "RoadCat")
    by_pa = agg_ratio(sub, "pa")
    def _enrich(g, key):
        """add zero-sim exposure + positive-flow-only ratio to a grouping"""
        zr, pr = [], []
        for k, x in sub.dropna(subset=[key]).groupby(key):
            z = x[x["zero_sim"]]
            xp = x[~x["zero_sim"]]
            zr.append({key: k, "zero_sim_sections": int(len(z)),
                       "obs_share_on_zero_sim": float(z["obs_8_9"].sum()
                                                      / max(x["obs_8_9"].sum(), 1e-9))})
            pr.append({key: k,
                       "ratio_pos_only": float(xp["sim_8_9_scaled"].sum()
                                               / max(xp["obs_8_9"].sum(), 1e-9))})
        return (g.merge(pd.DataFrame(zr), on=key, how="left")
                 .merge(pd.DataFrame(pr), on=key, how="left"))

    by_region = _enrich(by_region, "region")
    by_roadcat = _enrich(by_roadcat, "RoadCat")
    by_pa = _enrich(by_pa, "pa")

    for g, name in [(by_region, "section_residual_by_region.csv"),
                    (by_roadcat, "section_residual_by_roadcat.csv"),
                    (by_pa, "section_residual_by_pa.csv")]:
        g["rel_dev_vs_global"] = g["ratio_obs_weighted"] / global_ratio - 1.0
        g.sort_values("rel_dev_vs_global").to_csv(out / name, index=False, encoding="utf-8-sig")
    log("")
    log("★ shortfall by Planning Region (obs-weighted Sim/Obs, PRIMARY cycle, 08-09):")
    br_cols = [c for c in ["region", "n_sections", "obs_total", "ratio_obs_weighted",
                           "ratio_pos_only", "ratio_median", "zero_sim_sections",
                           "obs_share_on_zero_sim", "rel_dev_vs_global"] if c in by_region]
    log(by_region.sort_values("rel_dev_vs_global")[br_cols].to_string(index=False))
    log("")
    log("shortfall by RoadCat:")
    log(by_roadcat.to_string(index=False))
    bp = by_pa.sort_values("rel_dev_vs_global")
    log("")
    log("shortfall by Planning Area (worst 8 / best 3):")
    log(pd.concat([bp.head(8), bp.tail(3)]).to_string(index=False))

    # ---- ring x radial ----------------------------------------------------------
    rows = []
    for (ring, rad), x in sub.dropna(subset=["ring", "radial"]).groupby(
            ["ring", "radial"], observed=True):
        xp = x[~x["zero_sim"]]
        rows.append({"ring": str(ring), "radial": rad, "n_sections": int(len(x)),
                     "obs_total": float(x["obs_8_9"].sum()),
                     "ratio_obs_weighted": wmean(x["ratio_8_9"], x["obs_8_9"]),
                     "zero_sim_sections": int(x["zero_sim"].sum()),
                     "ratio_pos_only": float(xp["sim_8_9_scaled"].sum()
                                             / max(xp["obs_8_9"].sum(), 1e-9))})
    brd = pd.DataFrame(rows)
    if len(brd):
        brd["rel_dev_vs_global"] = brd["ratio_obs_weighted"] / global_ratio - 1.0
        brd = brd.sort_values(["ring", "radial"])
    brd.to_csv(out / "section_residual_by_ring_dir.csv", index=False, encoding="utf-8-sig")
    log("")
    log("★ shortfall by CBD ring x radial direction:")
    log(brd.to_string(index=False) if len(brd) else "(no data)")

    # ---- radial orientation only (cleanest single read of the structure) ---------
    rrows = []
    for rad, x in sub.dropna(subset=["radial"]).groupby("radial"):
        xp = x[~x["zero_sim"]]
        rrows.append({"radial": rad, "n_sections": int(len(x)),
                      "obs_total": float(x["obs_8_9"].sum()),
                      "ratio_obs_weighted": wmean(x["ratio_8_9"], x["obs_8_9"]),
                      "zero_sim_sections": int(x["zero_sim"].sum()),
                      "ratio_pos_only": float(xp["sim_8_9_scaled"].sum()
                                              / max(xp["obs_8_9"].sum(), 1e-9))})
    brad = pd.DataFrame(rrows)
    brad["rel_dev_vs_global"] = brad["ratio_obs_weighted"] / global_ratio - 1.0
    brad["rel_dev_pos_only"] = brad["ratio_pos_only"] / g_pos - 1.0
    brad = brad.sort_values("rel_dev_vs_global")
    brad.to_csv(out / "section_residual_by_radial.csv", index=False, encoding="utf-8-sig")
    log("")
    log("★ shortfall by radial orientation (CBD reference):")
    log(brad.to_string(index=False))

    # ---- robustness: same test on positive-flow-only sections -------------------
    pos_rows = []
    for k, x in sub_pos.dropna(subset=["region"]).groupby("region"):
        pos_rows.append({"region": k, "n_sections": int(len(x)),
                         "obs_total": float(x["obs_8_9"].sum()),
                         "ratio_pos_only": float(x["sim_8_9_scaled"].sum()
                                                 / max(x["obs_8_9"].sum(), 1e-9))})
    bpos = pd.DataFrame(pos_rows)
    bpos["rel_dev_vs_global_pos"] = bpos["ratio_pos_only"] / g_pos - 1.0
    bpos = bpos.sort_values("rel_dev_vs_global_pos")
    bpos.to_csv(out / "section_residual_by_region_pos_only.csv", index=False,
                encoding="utf-8-sig")
    max_rel_dev_pos = float(bpos["rel_dev_vs_global_pos"].abs().max()) if len(bpos) else float("nan")
    log("")
    log("robustness -- by region, EXCLUDING zero-sim sections:")
    log(bpos.to_string(index=False))
    log(f"   max |rel dev| (pos-only, vs pooled pos-only {g_pos:.4f}) = {max_rel_dev_pos:.4f}")

    rows_v = [{"key": str(r["region"]), "ratio": float(r["ratio_obs_weighted"]),
               "rel_dev": float(r["ratio_obs_weighted"] / global_ratio - 1.0),
               "obs_total": float(r["obs_total"])} for _, r in by_region.iterrows()]
    max_rel_dev = max((abs(r["rel_dev"]) for r in rows_v), default=float("nan"))
    all_short = all(r["ratio"] < 1.0 for r in rows_v) if rows_v else False
    log("")
    log(f"regions all below parity 1.0 : {all_short};  max |rel dev vs global| = {max_rel_dev:.4f}")

    return dict(rows=rows_v, global_ratio=global_ratio, max_rel_dev=max_rel_dev,
                all_short=all_short, by_region=by_region, by_roadcat=by_roadcat,
                by_pa=by_pa, by_ring_dir=brd, by_radial=brad, n_zero_sim=n_zero_sim,
                obs_share_zero=obs_share_zero, pooled_all=g_all, pooled_pos=g_pos,
                by_region_pos=bpos, max_rel_dev_pos=max_rel_dev_pos,
                n_geo=n_geo, cbd=(cbx, cby, src_note))


# ==========================================================================
# Part 3 -- pre-routing OD vs post-routing section structure
# ==========================================================================


def _hhmmss(s):
    if not s:
        return float("nan")
    try:
        p = [float(x) for x in str(s).split(":")]
        while len(p) < 3:
            p = [0.0] + p
        return p[0] * 3600 + p[1] * 60 + p[2]
    except Exception:
        return float("nan")


def parse_realized_plans(force=False):
    """Stream the R01 experienced-plans file -> per-agent realised route distance."""
    cache = OUT_DIR / "_agent_realized.parquet"
    if cache.exists() and not force:
        df = pd.read_parquet(cache)
        log(f"realised plans : [cached] {len(df):,} agents <- {cache.name}")
        return df

    src = R01_OUT / "R01_rc_min.output_plans.xml.gz"
    if not src.exists():
        log(f"realised plans : MISSING {src}")
        return pd.DataFrame()

    log(f"realised plans : streaming {src.name} ({src.stat().st_size/1e6:.0f} MB) ...")
    t0 = time.time()
    rows = []
    st = {"id": None, "attrs": {}, "plan": None}

    def flush():
        if st["id"] is not None and st["plan"] is not None:
            rows.append({
                "agent_id": st["id"],
                "origin_zone": st["attrs"].get("originZone"),
                "destination_zone": st["attrs"].get("destinationZone"),
                "od_trips": st["attrs"].get("odTrips"),
                "expansion_factor": st["attrs"].get("expansionFactor"),
                "realised_m": st["plan"].get("distance"),
                "realised_s": st["plan"].get("trav_time"),
            })
        st["id"], st["attrs"], st["plan"] = None, {}, None

    with gzip.open(src, "rt", encoding="utf-8", errors="replace") as f:
        for event, elem in ET.iterparse(f, events=("start", "end")):
            tag = elem.tag
            if event == "start" and tag == "person":
                st["id"], st["attrs"], st["plan"] = elem.get("id"), {}, None
            elif event == "end" and tag == "attribute" and st["id"] is not None:
                nm = elem.get("name")
                txt = (elem.text or "").strip()
                if nm in ("originZone", "destinationZone"):
                    try:
                        st["attrs"][nm] = int(txt)
                    except ValueError:
                        pass
                elif nm in ("odTrips", "expansionFactor"):
                    try:
                        st["attrs"][nm] = float(txt)
                    except ValueError:
                        pass
            elif event == "end" and tag == "plan" and st["id"] is not None:
                if (elem.get("selected") or "").lower() == "yes":
                    rt = elem.find(".//route")
                    if rt is not None:
                        st["plan"] = {"distance": float(rt.get("distance") or "nan"),
                                      "trav_time": _hhmmss(rt.get("trav_time"))}
                elem.clear()
            elif event == "end" and tag == "person":
                flush()
                elem.clear()

    df = pd.DataFrame(rows)
    log(f"realised plans : {len(df):,} agents parsed in {time.time()-t0:.1f}s")
    if len(df):
        df.to_parquet(cache, index=False)
        log(f"realised plans : cached -> {cache.name}")
    return df


def part3(d, out, p1):
    banner("Part 3 -- pre-routing OD vs post-routing section structure")
    df, cw = d["df"], d["cw_prim"]

    # ---- 3.1 mass chain ---------------------------------------------------------
    cz = d["cz"]
    sum_exp = float(cz["expansion_factor"].sum())
    sum_odtrips = float(cz["od_trips"].sum())
    chain = pd.DataFrame([
        {"stage": "1 frozen OD matrix (lambda=0.075)", "value": REAL_CAR_OD_TOTAL,
         "unit": "car trips", "note": "Sum(T_ij) over 71136 positive cells"},
        {"stage": "2 MATSim population (sample)", "value": float(len(cz)),
         "unit": "agents", "note": "one home -> work car trip per agent"},
        {"stage": "3 re-expanded by expansion_factor", "value": sum_exp,
         "unit": "car trips", "note": "Sum(expansion_factor) must equal the frozen OD total"},
        {"stage": "4 scale identity", "value": float(len(cz)) * bt.SCALE,
         "unit": "car trips", "note": "N_agents x SCALE == frozen OD total"},
        {"stage": "guard: raw Sum(od_trips) [NOT a population total]", "value": sum_odtrips,
         "unit": "car trips", "note": "the agent file repeats the CELL value for every agent "
                                      "in that cell -> NEVER compare this with the OD total"},
    ])
    chain["rel_dev_vs_frozen_od"] = chain["value"] / REAL_CAR_OD_TOTAL - 1.0
    chain.to_csv(out / "mass_chain.csv", index=False, encoding="utf-8-sig")
    log(chain.to_string(index=False))

    # ---- 3.2 planned VKT / distance vs realised ---------------------------------
    planned_vkt = float((df["T_ij"] * df["d_ff_cii_m"]).sum())
    planned_vkt_raw = float((df["T_ij"] * df["d_ff_m"]).sum())
    planned_mean_m = wmean(df["d_ff_cii_m"], df["T_ij"])

    # 3.2a MATSim's own travel-distance statistics: exact, cheap, always available
    detour_stats = {}
    tds = R01_OUT / "R01_rc_min.traveldistancestats.csv"
    if tds.exists():
        td = pd.read_csv(tds, sep=";")
        c0 = td.columns[0]
        dcol = ([c for c in td.columns if "Trip distance" in c]
                or [c for c in td.columns if "Leg distance" in c])
        td[c0] = pd.to_numeric(td[c0], errors="coerce")
        td[dcol[0]] = pd.to_numeric(td[dcol[0]], errors="coerce")
        td = td.dropna().sort_values(c0)
        detour_stats = {
            "iteration_first": int(td[c0].iloc[0]),
            "iteration_last": int(td[c0].iloc[-1]),
            "mean_trip_distance_first_m": float(td[dcol[0]].iloc[0]),
            "mean_trip_distance_last_m": float(td[dcol[0]].iloc[-1]),
            "planned_mean_distance_m": float(planned_mean_m),
            "detour_factor_last_over_planned": float(td[dcol[0]].iloc[-1] / planned_mean_m),
            "distance_inflation_first_to_last_pct": float(
                (td[dcol[0]].iloc[-1] / td[dcol[0]].iloc[0] - 1.0) * 100.0),
        }
        log("")
        log("★ realised mean trip distance (MATSim traveldistancestats) vs OD-impedance mean:")
        log(json.dumps({k: (round(v, 4) if isinstance(v, float) else v)
                        for k, v in detour_stats.items()}, ensure_ascii=False))

    # 3.2b per-agent realised route vs OD impedance (needs the 190 MB plans parse)
    plans = d["plans"]
    realised, det = {}, None
    if plans is not None and len(plans):
        pl = plans.merge(df[["origin_zone", "destination_zone", "d_ff_cii_m",
                             "d_ff_cii_km", "o_planning_region"]],
                         on=["origin_zone", "destination_zone"], how="left")
        pl = pl.dropna(subset=["d_ff_cii_m", "realised_m"]).copy()
        pl["w"] = pl["expansion_factor"]
        pl["detour"] = pl["realised_m"] / pl["d_ff_cii_m"].replace(0, np.nan)
        realised_vkt = float((pl["w"] * pl["realised_m"]).sum())
        dw = wmean(pl["detour"], pl["w"])

        rows = []
        for name, lo, hi in DIST_BANDS:
            m = (pl["d_ff_cii_km"] >= lo) & (pl["d_ff_cii_km"] < hi)
            x = pl[m]
            if not len(x):
                continue
            dd = x["detour"].dropna()
            rows.append({
                "band": name, "n_agents": int(len(x)), "w_sum": float(x["w"].sum()),
                "planned_mean_m": wmean(x["d_ff_cii_m"], x["w"]),
                "realised_mean_m": wmean(x["realised_m"], x["w"]),
                "detour_wmean": wmean(x["detour"], x["w"]),
                "detour_median": float(dd.median()) if len(dd) else float("nan"),
                "planned_vkt_km": float((x["w"] * x["d_ff_cii_m"]).sum() / 1000.0),
                "realised_vkt_km": float((x["w"] * x["realised_m"]).sum() / 1000.0),
            })
        det = pd.DataFrame(rows)
        det.to_csv(out / "realized_vs_planned_by_band.csv", index=False, encoding="utf-8-sig")
        log("")
        log("★ realised route distance vs OD impedance distance, by OD distance band:")
        log(det.to_string(index=False))

        greg = []
        for k, x in pl.dropna(subset=["detour"]).groupby("o_planning_region"):
            greg.append({"o_planning_region": k, "n_agents": int(len(x)),
                         "w_sum": float(x["w"].sum()),
                         "planned_mean_m": wmean(x["d_ff_cii_m"], x["w"]),
                         "realised_mean_m": wmean(x["realised_m"], x["w"]),
                         "detour_wmean": wmean(x["detour"], x["w"])})
        greg = pd.DataFrame(greg).sort_values("detour_wmean")
        greg.to_csv(out / "realized_detour_by_origin_region.csv", index=False,
                    encoding="utf-8-sig")
        log("")
        log("realised detour by origin region:")
        log(greg.to_string(index=False))

        realised = {"vkt_realised_km": realised_vkt / 1000.0,
                    "detour_weighted_mean": dw,
                    "n_agents_parsed": int(len(pl)),
                    "realised_mean_m": wmean(pl["realised_m"], pl["w"]),
                    "by_origin_region": greg}
    else:
        log("")
        log("realised plans unavailable -> per-agent band check SKIPPED "
            "(3.2a already provides the global detour factor)")

    # ---- 3.3 independent VKT cross-check from linkstats ------------------------
    links = pd.read_csv(NET_LINKS, usecols=["from_node", "to_node", "length_m"])
    links["LINK"] = ("e" + links["from_node"].astype(str) + "_"
                     + links["to_node"].astype(str))
    lmap = links.set_index("LINK")["length_m"]
    vkt_ls = {}
    if CYCLE_LINKSTATS.exists():
        cyc = _read_linkstats(CYCLE_LINKSTATS,
                              ["LINK", "HRS7-8avg", "HRS8-9avg", "HRS0-24avg"])
        cyc["length_m"] = cyc["LINK"].map(lmap)
        cyc = cyc.dropna(subset=["length_m"])
        for col, lab in [("HRS8-9avg", "window_0809"), ("HRS0-24avg", "window_fullday_proxy")]:
            if col in cyc.columns:
                vkt_ls[f"vkt_km_{lab}"] = float(
                    (cyc[col] * cyc["length_m"]).sum() * bt.SCALE / 1000.0)
        if "HRS7-8avg" in cyc.columns and "HRS8-9avg" in cyc.columns:
            vkt_ls["vkt_km_window_0709_sum"] = float(
                ((cyc["HRS7-8avg"] + cyc["HRS8-9avg"]) * cyc["length_m"]).sum()
                * bt.SCALE / 1000.0)
        vkt_ls["vkt_km_planned_cii"] = planned_vkt / 1000.0
        if vkt_ls.get("vkt_km_window_0809"):
            vkt_ls["ratio_0809_over_planned"] = vkt_ls["vkt_km_window_0809"] / (planned_vkt / 1000.0)
        if vkt_ls.get("vkt_km_window_fullday_proxy"):
            vkt_ls["ratio_fullday_over_planned"] = (
                vkt_ls["vkt_km_window_fullday_proxy"] / (planned_vkt / 1000.0))
    log("")
    log("network VKT from linkstats (x SCALE) vs OD x impedance:")
    log(json.dumps({k: round(v, 4) for k, v in vkt_ls.items()}, ensure_ascii=False))
    log(f"planned VKT from OD x impedance   : {planned_vkt/1000.0:,.1f} km (c_ii proxy) / "
        f"{planned_vkt_raw/1000.0:,.1f} km (raw, intra-zone=0)")

    # ---- 3.4 localised spatial redistribution first -> last iteration -----------
    from scipy.spatial import cKDTree

    red = {}
    iters = sorted((R01_OUT / "ITERS").glob("it.*"),
                   key=lambda p: int(p.name.split(".")[1]))
    WCOLS = ["LINK", "HRS7-8avg", "HRS8-9avg", "HRS0-24avg"]
    if len(iters) >= 2:
        first = sorted(iters[0].glob("*.linkstats.txt.gz"))
        last = sorted(iters[-1].glob("*.linkstats.txt.gz"))
        if first and last:
            a = _read_linkstats(first[0], WCOLS)
            b = _read_linkstats(last[0], WCOLS)
            m = a.merge(b, on="LINK", suffixes=("_it0", "_it19"), how="inner").dropna()
            matched = set(cw["matsim_link_id"].astype(str))
            m["is_matched"] = m["LINK"].isin(matched)
            mm = m[m["is_matched"]]

            # link -> region via the link MIDPOINT -> nearest zone centroid
            nxy = pd.read_csv(NET_NODES).set_index("node_id")[["x_svy21_m", "y_svy21_m"]]
            lf = pd.read_csv(NET_LINKS, usecols=["from_node", "to_node"])
            lf["LINK"] = ("e" + lf["from_node"].astype(str) + "_"
                          + lf["to_node"].astype(str))
            lgeo = pd.DataFrame({
                "LINK": lf["LINK"],
                "mx": (lf["from_node"].map(nxy["x_svy21_m"])
                       + lf["to_node"].map(nxy["x_svy21_m"])) / 2.0,
                "my": (lf["from_node"].map(nxy["y_svy21_m"])
                       + lf["to_node"].map(nxy["y_svy21_m"])) / 2.0,
            }).dropna()
            zs = d["zd"].sort_values("zone_id")
            tree = cKDTree(zs[["centroid_x_svy21_m", "centroid_y_svy21_m"]].to_numpy(float))
            _, idx = tree.query(lgeo[["mx", "my"]].to_numpy(float), k=1)
            lgeo["region"] = zs["planning_region"].to_numpy()[idx]
            m = m.merge(lgeo[["LINK", "region"]], on="LINK", how="left")

            red = {"iteration_first": iters[0].name, "iteration_last": iters[-1].name,
                   "matched_n_links": int(len(mm))}
            for wcol, wlab in [("HRS8-9avg", "0809"), ("HRS0-24avg", "fullday_proxy")]:
                c0, c19 = f"{wcol}_it0", f"{wcol}_it19"
                if c0 not in m.columns or c19 not in m.columns:
                    continue
                red[f"all_flow_{wlab}_it0"] = float(m[c0].sum())
                red[f"all_flow_{wlab}_it19"] = float(m[c19].sum())
                red[f"all_rel_change_{wlab}"] = float(m[c19].sum() / max(m[c0].sum(), 1e-9) - 1.0)
                red[f"matched_flow_{wlab}_it0"] = float(mm[c0].sum())
                red[f"matched_flow_{wlab}_it19"] = float(mm[c19].sum())
                red[f"matched_rel_change_{wlab}"] = float(
                    mm[c19].sum() / max(mm[c0].sum(), 1e-9) - 1.0)

            rows = []
            for k, x in m.dropna(subset=["region"]).groupby("region"):
                xm = x[x["is_matched"]]
                row = {"region": k, "n_links": int(len(x)), "matched_links": int(len(xm))}
                for wcol, wlab in [("HRS8-9avg", "0809"), ("HRS0-24avg", "fullday_proxy")]:
                    c0, c19 = f"{wcol}_it0", f"{wcol}_it19"
                    if c0 not in x.columns:
                        continue
                    row[f"all_flow_{wlab}_it0"] = float(x[c0].sum())
                    row[f"all_flow_{wlab}_it19"] = float(x[c19].sum())
                    row[f"rel_change_all_{wlab}"] = float(
                        x[c19].sum() / max(x[c0].sum(), 1e-9) - 1.0)
                    row[f"matched_flow_{wlab}_it0"] = float(xm[c0].sum())
                    row[f"matched_flow_{wlab}_it19"] = float(xm[c19].sum())
                    row[f"rel_change_matched_{wlab}"] = float(
                        xm[c19].sum() / max(xm[c0].sum(), 1e-9) - 1.0)
                rows.append(row)
            gr = pd.DataFrame(rows).sort_values("rel_change_matched_0809")
            gr.to_csv(out / "link_redistribution_by_region.csv", index=False, encoding="utf-8-sig")
            red["by_region"] = gr
            log("")
            log(f"★ spatial redistribution {iters[0].name} -> {iters[-1].name} "
                f"(region = link midpoint -> nearest zone centroid):")
            for wlab in ["0809", "fullday_proxy"]:
                if f"all_rel_change_{wlab}" not in red:
                    continue
                log(f"   window {wlab:14s} ALL     : "
                    f"{red[f'all_flow_{wlab}_it0']:,.0f} -> {red[f'all_flow_{wlab}_it19']:,.0f} "
                    f"({red[f'all_rel_change_{wlab}']*100:+.2f}%)")
                log(f"   window {wlab:14s} MATCHED : "
                    f"{red[f'matched_flow_{wlab}_it0']:,.0f} -> "
                    f"{red[f'matched_flow_{wlab}_it19']:,.0f} "
                    f"({red[f'matched_rel_change_{wlab}']*100:+.2f}%)")
            log("")
            log("   ★ NOTE: the 7.6E audit reported MATCHED +9.28% / ALL -3.70% because it used "
                "Sigma HRS0-24avg;")
            log("            the 08-09 window gives a different (larger) pair of numbers. "
                "Both are correct -- the window must ALWAYS be stated.")
            log(gr.to_string(index=False))

    # ---- checks ----------------------------------------------------------------
    chk("S1.agent_count", len(cz), len(cz) == N_AGENT, "== 200000")
    chk("S1.expansion_conservation", round(abs(sum_exp - REAL_CAR_OD_TOTAL), 8),
        abs(sum_exp - REAL_CAR_OD_TOTAL) < 1e-4, "|Sum(expansion_factor) - 459794| < 1e-4")
    chk("S1.scale_identity", round(abs(len(cz) * bt.SCALE - REAL_CAR_OD_TOTAL), 6),
        abs(len(cz) * bt.SCALE - REAL_CAR_OD_TOTAL) < 1e-6, "N_agents x SCALE == 459794")
    chk("P3.planned_vkt_consistency", round(planned_vkt / planned_vkt_raw, 5), True,
        "informational: c_ii proxy vs raw (intra-zone = 0)")
    if realised:
        detour_val, detour_src = realised["detour_weighted_mean"], "per-agent plans (weighted)"
    elif detour_stats:
        detour_val, detour_src = (detour_stats["detour_factor_last_over_planned"],
                                  "traveldistancestats (agent mean)")
    else:
        detour_val, detour_src = None, "unavailable"
    chk("S7.detour_factor", (None if detour_val is None else round(float(detour_val), 4)),
        (detour_val is not None) and (1.00 <= detour_val <= 1.35), "in [1.00, 1.35]", detour_src)
    if realised:
        chk("P3.realised_agents_parsed", realised["n_agents_parsed"],
            realised["n_agents_parsed"] >= int(0.98 * N_AGENT), ">= 98% of population")
    if red:
        km = "matched_rel_change_0809" if "matched_rel_change_0809" in red else "matched_rel_change"
        ka = "all_rel_change_0809" if "all_rel_change_0809" in red else "all_rel_change"
        chk("P3.redistribution_signature",
            {"window": "0809" if km.endswith("0809") else "legacy",
             "matched_rel": round(red[km], 5), "all_rel": round(red[ka], 5)},
            red[km] > red[ka],
            "calibrated (MATCHED) links gain flow while the network total does not")

    return dict(chain=chain, planned_vkt=planned_vkt, planned_vkt_raw=planned_vkt_raw,
                planned_mean_m=planned_mean_m, detour_stats=detour_stats,
                realised=realised, vkt_ls=vkt_ls, redistribution=red, by_band=det)


def _read_linkstats(path, cols):
    with gzip.open(path, "rt", encoding="utf-8", errors="replace") as f:
        header = f.readline().rstrip("\n").split("\t")
    use = [c for c in cols if c in header]
    df = pd.read_csv(path, sep="\t", compression="gzip", usecols=use, low_memory=False)
    for c in use:
        if c != "LINK":
            df[c] = pd.to_numeric(df[c], errors="coerce")
    df["LINK"] = df["LINK"].astype(str).str.strip()
    return df


# ==========================================================================
# verdict + main
# ==========================================================================


def get_check(name, default=True):
    for c in CHECKS:
        if c["check"] == name:
            return bool(c["ok"])
    return default


def verdict(p2, p3):
    crit = {
        "S4_shortfall_uniformity": get_check("S4.region_ratio_max_rel_dev"),
        "S5_table118_satisfaction": get_check("S5.table118_satisfaction_PHYSICAL"),
        "S6_zone_absorption_anomaly": get_check("S6.zone_absorption_anomaly"),
        "S7_detour_factor": get_check("S7.detour_factor"),
    }
    n_ok = sum(crit.values())
    if n_ok == len(crit):
        v = "OD_STRUCTURE_CONSISTENT"
        nxt = ("可行 -> 7.6F-1：在已冻结的 R01 route-choice 底座上补跑 "
               "f = 1.10 / 1.20 / 1.25，建立稳定的 demand-response curve")
    elif n_ok >= 2:
        v = "OD_STRUCTURE_PARTIAL"
        nxt = ("先解决被标记的结构项，再决定 7.6F-1；"
               "不得盲目补跑 D02-D04（旧谱已判 LEGACY_CURVE_UNINFORMATIVE）")
    else:
        v = "OD_STRUCTURE_ANOMALY_FOUND"
        nxt = "先修 OD 空间结构，再谈 demand scale；7.6F-1 暂停"
    return {"verdict": v, "criteria": crit, "n_criteria_pass": n_ok,
            "n_criteria_total": len(crit), "next": nxt}


def main():
    global OUT_DIR

    ap = argparse.ArgumentParser(description="Step 7.6C OD spatial structure diagnosis")
    ap.add_argument("--out", default=str(OUT_DIR))
    ap.add_argument("--skip-plans", action="store_true",
                    help="skip the 190 MB experienced-plans parse (Part 3.2 partial)")
    ap.add_argument("--force-plans", action="store_true", help="re-parse the plans file")
    args = ap.parse_args()

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    OUT_DIR = out

    t0 = time.time()
    d = load_all(skip_plans=args.skip_plans)
    if args.force_plans and not args.skip_plans:
        d["plans"] = parse_realized_plans(force=True)

    p1 = part1(d, out)
    p2 = part2(d, out, p1)
    p3 = part3(d, out, p1)

    banner("verdict")
    v = verdict(p2, p3)
    log(json.dumps(v, ensure_ascii=False, indent=2))

    npass = sum(1 for c in CHECKS if c["ok"])
    summary = {
        "step": "7.6C",
        "title": "OD spatial structure / distance band / spatial concentration diagnosis",
        "status": v["verdict"],
        "zero_simulation": True,
        "matsim_rerun": False,
        "parameters_changed": False,
        "demand_scale_selected": False,
        "lambda_selected": False,
        "prerequisite": "7.6E route-choice FROZEN; 7.6F-0 new base demand=1.00 Sim/Obs=0.8590",
        "preregistered_criteria": PREREGISTERED,
        "caliber": {
            "od": "car_prior_od_lambda_0p075 (frozen: 71136 cells, Sum=459794)",
            "distance": "impedance_matrix.parquet distance_m (free-flow network shortest path)",
            "c_ii_proxy": "0.5 x median centroid distance to the 5 nearest OTHER zones",
            "am_time": "ampeak_impedance_v2.parquet travel_time_min",
            "sim_obs": "HRS8-9avg x SCALE (frozen module bt.SCALE)",
            "stability": "Sigma HRS0-24avg (7.6E audit) -- NOT conflated with Sim/Obs",
            "verdict_anchor": f"7.6F-0 R01 demand=1.00 MATCHED Primary = {ANCHOR_SIM_OBS}",
            "external_anchors": ["Census Table 118 (residence region x workplace PA)",
                                 "Census T10 (workplace PA x usual travel time, ALL MODES)"],
        },
        "part1_distance": {
            "stats": p1["stats"].to_dict(orient="records"),
            "bands": p1["bands"].to_dict(orient="records"),
            "bands_raw_intra_zero": p1["bands_raw"].to_dict(orient="records"),
            "short_med_long": p1["sml"].to_dict(orient="records"),
            "tails": p1["tails"],
            "am_vs_census_T10": p1["time_bands"].to_dict(orient="records"),
            "sampling_bias": p1["bias"].to_dict(orient="records"),
            "mean_od_m": p1["mean_od"], "mean_agent_m": p1["mean_ag"],
        },
        "part2_spatial": {
            "concentration": p2["conc"].to_dict(orient="records"),
            "od_cells": p2["cells"],
            "n_extreme_absorption_zones": p2["n_extreme"],
            "table118": {"median_abs_share_resid_PHYSICAL": p2["med_res"],
                         "p95_abs_share_resid_PHYSICAL": p2["p95_res"],
                         "median_abs_share_resid_ALLCELLS": p2["med_res_all"],
                         "nonphysical_cells_excluded": p2["nonphys_cells"]},
            "shortfall_by_region": p2["shortfall"]["by_region"].to_dict(orient="records"),
            "shortfall_by_region_pos_only": p2["shortfall"]["by_region_pos"].to_dict(orient="records"),
            "max_rel_dev_pos_only": p2["shortfall"]["max_rel_dev_pos"],
            "shortfall_by_roadcat": p2["shortfall"]["by_roadcat"].to_dict(orient="records"),
            "shortfall_by_pa": p2["shortfall"]["by_pa"].to_dict(orient="records"),
            "shortfall_by_ring_dir": p2["shortfall"]["by_ring_dir"].to_dict(orient="records"),
            "shortfall_by_radial": p2["shortfall"]["by_radial"].to_dict(orient="records"),
            "sections_with_zero_simulated_flow": p2["shortfall"]["n_zero_sim"],
            "obs_share_on_zero_sim_sections": p2["shortfall"]["obs_share_zero"],
            "pooled_ratio_all_sections": p2["shortfall"]["pooled_all"],
            "pooled_ratio_excl_zero_sim": p2["shortfall"]["pooled_pos"],
            "global_ratio": p2["shortfall"]["global_ratio"],
            "max_rel_dev": p2["shortfall"]["max_rel_dev"],
            "regions_all_below_parity": p2["shortfall"]["all_short"],
        },
        "part3_consistency": {
            "mass_chain": p3["chain"].to_dict(orient="records"),
            "planned_mean_distance_m": p3["planned_mean_m"],
            "planned_vkt_km": p3["planned_vkt"] / 1000.0,
            "planned_vkt_raw_km": p3["planned_vkt_raw"] / 1000.0,
            "detour_from_traveldistancestats": p3["detour_stats"],
            "realised_per_agent": {
                k: (v2 if not isinstance(v2, pd.DataFrame) else v2.to_dict(orient="records"))
                for k, v2 in (p3["realised"] or {}).items()},
            "network_vkt_from_linkstats": p3["vkt_ls"],
            "redistribution": {
                k: (v2 if not isinstance(v2, pd.DataFrame) else v2.to_dict(orient="records"))
                for k, v2 in (p3["redistribution"] or {}).items()},
        },
        "verdict_detail": v,
        "checks": CHECKS,
        "checks_pass": npass,
        "checks_total": len(CHECKS),
        "runtime_s": round(time.time() - t0, 1),
    }
    (out / "od_structure_7_6c_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    log("")
    log(f"checks: {npass}/{len(CHECKS)} passed")
    log(f"products -> {out}")
    log(f"runtime: {time.time()-t0:.1f}s")
    return 0 if npass == len(CHECKS) else 2


if __name__ == "__main__":
    raise SystemExit(main())
