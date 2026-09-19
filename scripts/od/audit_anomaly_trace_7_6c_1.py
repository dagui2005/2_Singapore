#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Step 7.6C-1 -- anomaly trace: coverage/attribution gap vs genuine structure
(ZERO-SIMULATION, READ-ONLY)
=========================================================================

Position in the pipeline
------------------------
7.6E   route-choice layer FROZEN (STABILITY_PASS 6/6)
7.6F-0 new stable base, demand=1.00  ->  MATCHED Sim/Obs = 0.8590
7.6C   OD spatial-structure diagnosis -> OD_STRUCTURE_PARTIAL
       (distance PASS / sampling PASS / PA-control PASS / regional-radial FAIL)
7.6C-1 <-- this step : trace the TWO concentrated anomalies that 7.6C flagged
       * 13/13 zero-flow sections at R5 x radial_in
       * the EAST / CENTRAL vs NORTH / NORTH-EAST regional reversal
       and decide whether they are COVERAGE / ATTRIBUTION artifacts
       (measurement) or genuine OD / network structure.

User ruling (2026-09-17):  7.6C-1 -> 7.6F-1  (NOT  7.6C -> 7.6F-1).
Still zero-simulation, still no parameter change, no demand-scale selection,
no lambda selection, no MATSim run.

Two layers
----------
Layer 1   LTA section -> final crosswalk -> matched MATSim links -> R01 routes
          for every zero-simulated-flow section. Outcomes:
            DIRECTION_MISMATCH      reverse link carries flow
            WINDOW_ARTIFACT         flow exists in 7-8 or 0-24 but not 8-9
            MEDIAN_ARTIFACT         some matched links carry flow, median = 0
            CROSSWALK_TWIN_ORPHAN   matched link dead in ALL windows, yet a
                                    flowing parallel link sits within R metres
            GENUINE_UNROUTED        no flowing link anywhere near
          plus a topology test: is the matched link reachable / departable
          inside the actually-flowing sub-network?

Layer 2   EAST <-> CENTRAL OD flow decomposition.
          * OD side    : region-block demand, distance-band split, direction
                         symmetry vs the other residential -> CBD blocks
          * route side : R01 realised routes re-aggregated by origin region x
                         destination region x distance band, with region /
                         radial classification of the whole ~706k-link network
          -> is the EAST under-prediction an attraction error, an OD-direction
             error, or the network routing those trips somewhere else?

Hard discipline
---------------
* NEVER starts MATSim, NEVER writes to any frozen artefact
* does not select demand scale, does not select lambda
* evaluation calibers and helpers IMPORTED from the two frozen modules
  ``compare_final_crosswalk_7_3_6b`` (SCALE) and
  ``diagnose_od_spatial_structure_7_6c`` (calibers / bands / aggregation)
* window discipline: Sim/Obs uses HRS8-9avg; coverage tracing additionally
  inspects HRS7-8avg and HRS0-24avg to separate a time-window artifact from a
  genuine zero

Outputs -> reports/od_anomaly_trace_7_6c_1/
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
# frozen module imports (byte-identical evaluation lineage, NO formula copies)
# --------------------------------------------------------------------------
HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import compare_final_crosswalk_7_3_6b as bt          # noqa: E402  frozen SCALE
import diagnose_od_spatial_structure_7_6c as d76     # noqa: E402  frozen 7.6C

ROOT = Path(r"D:\Luan\2026-05\2_Singapore")

# ---------------- frozen inputs (read-only) -------------------------------
CROSSWALK = d76.CROSSWALK
BT_7_6F0 = d76.BACKTEST_7_6F0
NET_NODES = d76.NET_NODES
NET_LINKS = d76.NET_LINKS
CYCLE_LINKSTATS = d76.CYCLE_LINKSTATS
R01_OUT = d76.R01_OUT
SEC_GEO_7_6C = d76.OUT_DIR / "section_geography.csv"
T118_RESID_7_6C = d76.OUT_DIR / "od_table118_residual.csv"

OUT_DIR = ROOT / "reports" / "od_anomaly_trace_7_6c_1"

# ---------------- frozen constants ----------------------------------------
ANCHOR_SIM_OBS = d76.ANCHOR_SIM_OBS       # 0.8590  (7.6F-0 R01 demand=1.00)
SCALE = float(bt.SCALE)                   # 2.29897 (459794 / 200000)
N_ZONE = d76.N_ZONE
REAL_CAR_OD_TOTAL = d76.REAL_CAR_OD_TOTAL

# coverage / twin search radii (metres) -- fixed BEFORE the run
TWIN_RADII = [30.0, 60.0, 100.0, 150.0, 400.0]
TWIN_R_PRIMARY = 60.0                     # headline radius for the verdict
TWIN_R_MAX = 400.0                        # widest radius -> upper bound

# EAST <-> CENTRAL distance bands (user-specified)
EC_BANDS = [("0-5", 0.0, 5.0), ("5-10", 5.0, 10.0), ("10-15", 10.0, 15.0),
            ("15-20", 15.0, 20.0), ("20+", 20.0, float("inf"))]
EC_LABELS = [b[0] for b in EC_BANDS]

REGION_ORDER = ["CENTRAL REGION", "EAST REGION", "WEST REGION",
                "NORTH REGION", "NORTH-EAST REGION"]
RADIAL_ORDER = ["radial_in", "radial_out", "circumferential"]
R5_RI_RING = "R5_20km+"
NON_PHYSICAL_MARKERS = ("NO FIXED", "WORKS FROM HOME", "OUTSIDE")

# ---------------- PRE-REGISTERED CRITERIA (frozen BEFORE the run) ---------
PREREGISTERED = {
    "note": ("7.6C-1 只做异常归因追踪；阈值在跑之前固定，禁止事后调参。"
             "全部结论只看 coverage/attribution 与 OD/network 结构的可分离性，"
             "不选 demand scale，不选 lambda。"),
    "T1_hard_zero_topology":
        "13 个 R5/radial_in 断面的全部匹配边在 HRS7-8avg / HRS8-9avg / HRS0-24avg "
        "三个窗口的正向与反向全部为 0（整整一天无人使用）。",
    "T2_twin_proximity":
        ">= 90% 的零流断面在 60 m 内存在有流链路（平行孪生），"
        "即零流主要来自链路归属而非无车。",
    "T3_od_direction_normal":
        "EAST<->CENTRAL 的定向不对称比落在其余 residency->CBD 区域对的区间内。",
    "T4_attraction_conserved":
        "7.6C Table118 物理格残差 中位<0.02 且 P95<0.10（直接复用 7.6C 结论）。",
    "T5_radial_in_residual_robust":
        "即使按同名孪生做上限替代，radial_in 的 Sim/Obs 仍 < circumferential "
        "与 radial_out（graded 缺口对 link-attribution 校正稳健）。",
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


def _jsonable(o):
    if isinstance(o, dict):
        return {k: _jsonable(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_jsonable(v) for v in o]
    if isinstance(o, (np.bool_,)):
        return bool(o)
    if isinstance(o, (np.floating, np.integer, float)):
        v = float(o)
        return None if (v != v or v in (float("inf"), float("-inf"))) else v
    return o


def wmean(v, w):
    return d76.wmean(v, w)


def _add_ec_band(df):
    """Vectorised EAST<->CENTRAL distance band label for an OD frame."""
    edges = [b[1] for b in EC_BANDS] + [float("inf")]
    return pd.cut(df["d_ff_cii_km"], edges, labels=EC_LABELS, right=False)


# ==========================================================================
# Part 0 -- load frozen context
# ==========================================================================

def load_context():
    banner("Part 0 -- load frozen artefacts, linkstats and network geometry")

    d = d76.load_all(skip_plans=True)

    cw = d["cw"]
    cw_prim = d["cw_prim"].copy()
    cw_prim["matsim_link_id"] = cw_prim["matsim_link_id"].astype(str)

    bt_df = d["bt_df"]
    sub = bt_df[(bt_df["run"] == "R01") &
                (bt_df["caliber"] == "PRIMARY_cycle_10_19")].copy()
    sub = sub[["lta_linkid", "RoadCat", "RoadName", "obs_8_9",
               "sim_8_9_scaled", "ratio_8_9", "matched_matsim_edges"]]
    log(f"7.6F-0 sections: {len(sub)} R01 PRIMARY-cycle rows "
        f"(anchor Sim/Obs = {ANCHOR_SIM_OBS})")

    geo = pd.read_csv(SEC_GEO_7_6C)
    geo = geo[["lta_linkid", "mid_x", "mid_y", "d_cbd_m", "n_links",
               "radial", "ring", "region", "pa"]]
    sub = sub.merge(geo, on="lta_linkid", how="left")
    n_geo = int(sub["region"].notna().sum())
    assert n_geo >= 570, f"section geography missing too many rows: {n_geo}/{len(sub)}"
    log(f"section geography (7.6C, reused): {n_geo}/{len(sub)} sections attributed")

    # ---- cycle-mean linkstats: the 3 windows at once ----------------------
    t0 = time.time()
    ls = {}
    with gzip.open(CYCLE_LINKSTATS, "rt", encoding="utf-8", errors="replace") as f:
        hdr = f.readline().rstrip("\n").split("\t")
        assert hdr[:4] == ["LINK", "HRS7-8avg", "HRS8-9avg", "HRS0-24avg"], hdr[:4]
        for line in f:
            p = line.rstrip("\n").split("\t")
            if len(p) >= 4:
                try:
                    ls[p[0]] = (float(p[1]), float(p[2]), float(p[3]))
                except ValueError:
                    pass
    log(f"cycle linkstats : {len(ls):,} links in {time.time()-t0:.1f}s "
        f"(R01 convergence window, cycle-mean of it.10-19)")

    # ---- network geometry -------------------------------------------------
    nodes = pd.read_csv(NET_NODES)
    nxy = nodes.set_index("node_id")[["x_svy21_m", "y_svy21_m"]]
    links = pd.read_csv(NET_LINKS, usecols=["from_node", "to_node", "length_m",
                                           "highway", "name"])
    links["matsim_link_id"] = ("e" + links["from_node"].astype(str) + "_"
                               + links["to_node"].astype(str))
    links["fx"] = links["from_node"].map(nxy["x_svy21_m"])
    links["fy"] = links["from_node"].map(nxy["y_svy21_m"])
    links["tx"] = links["to_node"].map(nxy["x_svy21_m"])
    links["ty"] = links["to_node"].map(nxy["y_svy21_m"])
    links["mx"] = (links["fx"] + links["tx"]) / 2.0
    links["my"] = (links["fy"] + links["ty"]) / 2.0
    ok = (np.isfinite(links["mx"].to_numpy(float))
          & np.isfinite(links["my"].to_numpy(float)))
    links = links[ok].reset_index(drop=True)
    links["f78"] = [ls.get(m, (0.0, 0.0, 0.0))[0] for m in links["matsim_link_id"]]
    links["f89"] = [ls.get(m, (0.0, 0.0, 0.0))[1] for m in links["matsim_link_id"]]
    links["f24"] = [ls.get(m, (0.0, 0.0, 0.0))[2] for m in links["matsim_link_id"]]
    log(f"network links   : {len(links):,} with geometry "
        f"({int((links['f24'] > 0).sum()):,} carry all-day flow)")

    # the sub-network agents actually use (all-day positive flow)
    flow = links[links["f24"] > 0].reset_index(drop=True)

    # ---- region / radial / ring classification of EVERY network link ------
    from scipy.spatial import cKDTree

    zd = d["zd"]
    zs = zd.sort_values("zone_id")
    zc = zs[["centroid_x_svy21_m", "centroid_y_svy21_m"]].to_numpy(float)
    ztree = cKDTree(zc)
    _, zidx = ztree.query(links[["mx", "my"]].to_numpy(float), k=1)
    links["region"] = zs["planning_region"].to_numpy()[zidx]
    links["pa"] = zs["planning_area"].to_numpy()[zidx]

    cbx, cby, src_note = d76.cbd_xy(zd, d["attr"])
    log(f"CBD proxy (SVY21) = ({cbx:.0f}, {cby:.0f}) <- {src_note}")
    vx = (links["tx"] - links["fx"]).to_numpy(float)
    vy = (links["ty"] - links["fy"]).to_numpy(float)
    rx = cbx - links["mx"].to_numpy(float)
    ry = cby - links["my"].to_numpy(float)
    nv, nr = np.hypot(vx, vy), np.hypot(rx, ry)
    with np.errstate(invalid="ignore", divide="ignore"):
        cosang = (vx * rx + vy * ry) / (nv * nr)
    links["radial"] = np.where(cosang > 0.35, "radial_in",
                               np.where(cosang < -0.35, "radial_out",
                                        "circumferential"))
    links["d_cbd_m"] = nr
    links["ring"] = pd.cut(links["d_cbd_m"], d76.RING_EDGES,
                           labels=d76.RING_LABELS, right=False)
    log("link classification: region <- nearest zone centroid (cKDTree); "
        "radial/ring <- CBD-reference angle / distance")

    # ---- flowing twin index (any-link and same-road-name) -----------------
    ftree = cKDTree(flow[["mx", "my"]].to_numpy(float))
    fname = flow["name"].fillna("").astype(str).str.upper().str.strip()
    name_groups = {}
    for nm, g in flow.groupby(fname):
        if nm == "":
            continue
        name_groups[nm] = (g, cKDTree(g[["mx", "my"]].to_numpy(float)))
    log(f"twin index      : {len(flow):,} flowing links, "
        f"{len(name_groups):,} distinct road names")

    # ---- topology: which nodes are reachable / departable ----------------
    flow_links = links[links["f24"] > 0]
    reached = set(flow_links["to_node"].astype(int).tolist())
    depart = set(flow_links["from_node"].astype(int).tolist())
    log(f"topology        : {len(reached):,} arrive-nodes / "
        f"{len(depart):,} depart-nodes inside the flowing sub-network")

    return dict(d=d, sub=sub, cw=cw, cw_prim=cw_prim, geo=geo, ls=ls,
                nodes=nodes, nxy=nxy, links=links, flow=flow, ftree=ftree,
                name_groups=name_groups, reached=reached, depart=depart,
                cbd=(cbx, cby))


# ==========================================================================
# helper: per-section matched-link trace
# ==========================================================================

def section_link_trace(ctx, lta_linkid):
    """Per matched link of one LTA section: windowed flow, reverse flow, topology."""
    cw_prim = ctx["cw_prim"]
    ls = ctx["ls"]
    link_meta = ctx["links"].set_index("matsim_link_id")
    rows = []
    ms = cw_prim[cw_prim["lta_linkid"] == lta_linkid]["matsim_link_id"].tolist()
    for m in ms:
        f78, f89, f24 = ls.get(m, (0.0, 0.0, 0.0))
        a, b = m[1:].split("_")
        rev = f"e{b}_{a}"
        r89, r24 = ls.get(rev, (0.0, 0.0, 0.0))[1], ls.get(rev, (0.0, 0.0, 0.0))[2]
        inr = int(a) in ctx["reached"]
        outr = int(b) in ctx["depart"]
        rows.append({
            "lta_linkid": lta_linkid, "matsim_link_id": m,
            "f78": f78, "f89": f89, "f24": f24,
            "rev_f89": r89, "rev_f24": r24,
            "any_window_flow": (f78 > 0) or (f24 > 0),
            "reverse_flow": (r89 > 0) or (r24 > 0),
            "in_reachable": inr, "out_reachable": outr,
            "orphan": (not inr) and (not outr),
            "length_m": float(link_meta.loc[m, "length_m"]) if m in link_meta.index else np.nan,
            "highway": (link_meta.loc[m, "highway"] if m in link_meta.index else ""),
        })
    return pd.DataFrame(rows)


def classify_section(ctx, sec_row):
    """Assign one zero-sim section to exactly one mechanism."""
    tr = section_link_trace(ctx, sec_row["lta_linkid"])
    n = len(tr)
    if n == 0:
        return dict(mechanism="NO_MATCHED_LINK", n_matched=0, n_orphan=0,
                    n_any_window_flow=0, n_reverse_flow=0, n_f89_pos=0,
                    frac_orphan=np.nan, twin_d_any_m=np.nan, twin_f89_any=0.0,
                    twin_name_any="", twin_d_same_m=None, twin_f89_same=0.0)

    n_orphan = int(tr["orphan"].sum())
    n_any = int(tr["any_window_flow"].sum())
    n_rev = int(tr["reverse_flow"].sum())
    n_f89 = int((tr["f89"] > 0).sum())

    mx, my = float(sec_row["mid_x"]), float(sec_row["mid_y"])
    d_any, i_any = ctx["ftree"].query([mx, my])
    f89_any = float(ctx["flow"].iloc[i_any]["f89"])
    name_any = str(ctx["flow"].iloc[i_any]["name"])
    key = str(sec_row["RoadName"]).upper().strip()
    d_same, f89_same = np.inf, 0.0
    if key in ctx["name_groups"]:
        g, t = ctx["name_groups"][key]
        dd, ii = t.query([mx, my])
        d_same = float(dd)
        f89_same = float(g.iloc[ii]["f89"])

    if n_rev > 0:
        mech = "DIRECTION_MISMATCH"
    elif n_any > 0:
        mech = "WINDOW_ARTIFACT"
    elif n_f89 > 0:
        mech = "MEDIAN_ARTIFACT"
    elif d_any <= TWIN_R_PRIMARY:
        mech = "CROSSWALK_TWIN_ORPHAN"
    else:
        mech = "GENUINE_UNROUTED"

    return dict(mechanism=mech, n_matched=n, n_orphan=n_orphan,
                n_any_window_flow=n_any, n_reverse_flow=n_rev, n_f89_pos=n_f89,
                frac_orphan=n_orphan / n,
                twin_d_any_m=float(d_any), twin_f89_any=f89_any,
                twin_name_any=name_any,
                twin_d_same_m=(None if not np.isfinite(d_same) else float(d_same)),
                twin_f89_same=f89_same)


# ==========================================================================
# Layer 1 -- coverage / attribution trace
# ==========================================================================

def part_A_layer1(ctx, out):
    banner("Layer 1 -- LTA section -> crosswalk -> matched links -> R01 routes")
    sub = ctx["sub"].copy()
    sub["zero_sim"] = sub["sim_8_9_scaled"] <= 0
    zero = sub[sub["zero_sim"]].copy()

    global_ratio = wmean(sub["ratio_8_9"], sub["obs_8_9"])
    log(f"R01 PRIMARY cycle, 08-09 window: {len(sub)} sections, "
        f"obs-weighted global Sim/Obs = {global_ratio:.4f} (anchor {ANCHOR_SIM_OBS})")
    log(f"zero-simulated-flow sections  = {len(zero)} "
        f"carrying {zero['obs_8_9'].sum():,.0f} obs veh/h "
        f"= {zero['obs_8_9'].sum()/sub['obs_8_9'].sum():.2%} of the observed total")

    focus = zero[(zero["ring"] == R5_RI_RING) & (zero["radial"] == "radial_in")].copy()
    log("")
    log(f"* focus set (R5_20km+ x radial_in, all zero-sim): {len(focus)} sections, "
        f"obs {focus['obs_8_9'].sum():,.0f} veh/h")
    log(focus[["lta_linkid", "RoadName", "RoadCat", "pa", "obs_8_9",
               "matched_matsim_edges"]].to_string(index=False))

    # ---- per-section mechanism classification (all zero-sim) -------------
    recs = []
    for _, r in zero.iterrows():
        c = classify_section(ctx, r)
        c.update({"lta_linkid": int(r["lta_linkid"]), "region": r["region"],
                  "pa": r["pa"], "ring": str(r["ring"]), "radial": r["radial"],
                  "RoadName": r["RoadName"], "RoadCat": r["RoadCat"],
                  "obs_8_9": float(r["obs_8_9"]),
                  "sim_8_9_scaled": float(r["sim_8_9_scaled"]),
                  "matched_matsim_edges": int(r["matched_matsim_edges"]),
                  "is_focus_R5_radial_in":
                      int((r["ring"] == R5_RI_RING) and (r["radial"] == "radial_in"))})
        recs.append(c)
    mech = pd.DataFrame(recs)
    mech = mech.sort_values(["is_focus_R5_radial_in", "obs_8_9"],
                            ascending=[False, False])
    mech.to_csv(out / "coverage_trace_zero_sim_sections.csv",
                index=False, encoding="utf-8-sig")

    log("")
    log("* mechanism of every zero-flow section:")
    summ = (mech.groupby("mechanism")
            .agg(n_sections=("lta_linkid", "size"),
                 obs=("obs_8_9", "sum"),
                 mean_twin_d_m=("twin_d_any_m", "mean"),
                 mean_orphan_frac=("frac_orphan", "mean"))
            .sort_values("n_sections", ascending=False))
    log(summ.to_string())
    summ.to_csv(out / "coverage_mechanism_summary.csv",
                index=False, encoding="utf-8-sig")

    # ---- the matched links of the focus set, link by link ----------------
    tr_all = [section_link_trace(ctx, lid) for lid in focus["lta_linkid"].tolist()]
    trace = pd.concat(tr_all, ignore_index=True)
    trace.to_csv(out / "focus13_matched_link_trace.csv",
                 index=False, encoding="utf-8-sig")
    log("")
    log(f"* focus set matched links: {len(trace)} edges "
        f"({int((trace['highway'] == 'motorway').sum())} motorway / "
        f"{int((trace['highway'] == 'motorway_link').sum())} motorway_link)")
    log(f"   forward  HRS7-8avg>0 : {int((trace['f78'] > 0).sum())}")
    log(f"   forward  HRS8-9avg>0 : {int((trace['f89'] > 0).sum())}")
    log(f"   forward  HRS0-24avg>0: {int((trace['f24'] > 0).sum())}")
    log(f"   reverse  HRS8-9avg>0 : {int((trace['rev_f89'] > 0).sum())}")
    log(f"   reverse  HRS0-24avg>0: {int((trace['rev_f24'] > 0).sum())}")
    log(f"   orphan (from-node unreachable AND to-node undepartable): "
        f"{int(trace['orphan'].sum())}/{len(trace)}")
    log(f"   fully connected (both)                                 : "
        f"{int((trace['in_reachable'] & trace['out_reachable']).sum())}/{len(trace)}")

    n_never = int(((trace["f78"] == 0) & (trace["f89"] == 0) & (trace["f24"] == 0)
                   & (trace["rev_f89"] == 0) & (trace["rev_f24"] == 0)).sum())
    chk("T1.focus_links_never_used_all_windows", n_never,
        n_never == len(trace), f"== {len(trace)}",
        "HRS7-8avg/HRS8-9avg/HRS0-24avg, forward+reverse all zero")

    fl = ctx["flow"].sample(min(20000, len(ctx["flow"])), random_state=0)
    inr_ref = float(fl["from_node"].astype(int).isin(ctx["reached"]).mean())
    outr_ref = float(fl["to_node"].astype(int).isin(ctx["depart"]).mean())
    tr_in = float(trace["in_reachable"].mean())
    tr_out = float(trace["out_reachable"].mean())
    log("")
    log(f"reference (20k all-day-flowing links): in-reachable {inr_ref:.3f}, "
        f"out-departable {outr_ref:.3f}")
    log(f"focus-set matched links            : in-reachable {tr_in:.3f}, "
        f"out-departable {tr_out:.3f}")
    chk("T1b.focus_link_topology", round(min(tr_in, tr_out), 4),
        min(tr_in, tr_out) < 0.10, "< 0.10 (reference ~0.99)",
        f"focus in-reach {tr_in:.3f} / out-depart {tr_out:.3f}")

    # ---- neighbourhood: is the corridor alive? ---------------------------
    from scipy.spatial import cKDTree
    ltree = cKDTree(ctx["links"][["mx", "my"]].to_numpy(float))
    nrows = []
    for _, r in focus.iterrows():
        idx = ltree.query_ball_point([float(r["mid_x"]), float(r["mid_y"])], r=400.0)
        nb = ctx["links"].iloc[idx]
        nrows.append({"lta_linkid": int(r["lta_linkid"]),
                      "RoadName": r["RoadName"], "obs_8_9": float(r["obs_8_9"]),
                      "nb_links": len(idx),
                      "nb_flow_f89": int((nb["f89"] > 0).sum()),
                      "nb_sum_f89": float(nb["f89"].sum()),
                      "nb_sum_f24": float(nb["f24"].sum())})
    nbdf = pd.DataFrame(nrows)
    nbdf.to_csv(out / "focus13_neighbourhood_flow.csv",
                index=False, encoding="utf-8-sig")
    log("")
    log("* corridor aliveness within 400 m of each focus section ")
    log("  (obs vs neighbourhood simulated flow):")
    log(nbdf.to_string(index=False))

    # ---- the twin test on ALL zero-sim sections --------------------------
    d_any = mech["twin_d_any_m"].to_numpy(float)
    log("")
    log("* parallel flowing twin near a zero-flow section:")
    for thr in TWIN_RADII:
        n = int((d_any <= thr).sum())
        log(f"   nearest flowing link <= {thr:5.0f} m : {n:2d}/{len(mech)} "
            f"({100*n/len(mech):5.1f}%)")
    n_p60 = int((d_any <= TWIN_R_PRIMARY).sum())
    frac_p60 = n_p60 / len(mech)
    chk("T2.zero_sim_twin_within_60m", round(frac_p60, 4),
        frac_p60 >= 0.90, ">= 0.90",
        f"{n_p60}/{len(mech)} zero-flow sections have a flowing link within 60 m")
    n_same = int((mech["twin_f89_same"].fillna(0) > 0).sum())
    log(f"   same-road-name flowing link present: {n_same}/{len(mech)}")

    # ---- counterfactual bounds on the link-attribution repair ------------
    bounds = link_attribution_bounds(ctx, sub)
    bounds.to_csv(out / "link_attribution_repair_bounds.csv",
                  index=False, encoding="utf-8-sig")
    log("")
    log("* counterfactual bounds of the link-attribution repair "
        "(INDICATIVE ONLY, not a correction):")
    log(bounds.to_string(index=False))

    return dict(sub=sub, zero=zero, focus=focus, mech=mech, trace=trace,
                neighbourhood=nbdf, bounds=bounds, global_ratio=global_ratio)


def directional_repair(ctx, sub):
    """Post-hoc bound (mechanism discovered during the first run).

    Many zero-sim sections were matched to links of BOTH carriageway directions.
    The section statistic is the across-link median of HRS8-9avg, so it collapses
    to 0 as soon as half the matched links belong to the direction the router does
    not use.  Repair = max( median(forward f89), median(reverse f89) ) over the
    section's matched links, scaled by SCALE.
    """
    cw_prim = ctx["cw_prim"]
    ls = ctx["ls"]
    out = {}
    for lid, g in cw_prim.groupby("lta_linkid"):
        fwd, rev = [], []
        for m in g["matsim_link_id"]:
            fwd.append(ls.get(m, (0.0, 0.0, 0.0))[1])
            a, b = m[1:].split("_")
            rev.append(ls.get(f"e{b}_{a}", (0.0, 0.0, 0.0))[1])
        out[int(lid)] = max(float(np.median(fwd)), float(np.median(rev))) * SCALE
    return out


def link_attribution_bounds(ctx, sub):
    """Lower (nearest flowing link) and upper (same-name flowing max) bounds."""
    s = sub.dropna(subset=["mid_x", "mid_y"]).copy()
    pts = s[["mid_x", "mid_y"]].to_numpy(float)
    d_any, i_any = ctx["ftree"].query(pts)
    s["twin_any_f89"] = ctx["flow"]["f89"].to_numpy()[i_any]
    s["twin_any_d"] = d_any

    same_f89 = np.zeros(len(s))
    same_d = np.full(len(s), np.inf)
    for j, (_, r) in enumerate(s.iterrows()):
        key = str(r["RoadName"]).upper().strip()
        if key in ctx["name_groups"]:
            g, t = ctx["name_groups"][key]
            dd, ii = t.query([float(r["mid_x"]), float(r["mid_y"])])
            same_d[j] = float(dd)
            same_f89[j] = float(g.iloc[ii]["f89"])
    s["twin_same_f89"] = same_f89
    s["twin_same_d"] = same_d

    rows = []
    obs_tot = float(s["obs_8_9"].sum())
    matched = float(s["sim_8_9_scaled"].sum())
    rows.append({"variant": "matched (7.6F-0 actual)", "radius_m": np.nan,
                 "group_by": "", "group": "GLOBAL", "n": len(s),
                 "global_sim_obs": matched / obs_tot,
                 "sim_obs_matched": matched / obs_tot,
                 "sim_obs_repaired": matched / obs_tot})
    for thr in TWIN_RADII:
        m = (s["twin_any_d"] <= thr).to_numpy()
        new = matched - float(s.loc[m, "sim_8_9_scaled"].sum()) + \
            float((s.loc[m, "twin_any_f89"] * SCALE).sum())
        rows.append({"variant": "repair: nearest flowing link", "radius_m": thr,
                     "group_by": "", "group": "GLOBAL", "n": int(m.sum()),
                     "global_sim_obs": new / obs_tot,
                     "sim_obs_matched": np.nan, "sim_obs_repaired": new / obs_tot})
    for thr in TWIN_RADII:
        m = ((s["twin_same_d"] <= thr) & (s["twin_same_f89"] > 0)).to_numpy()
        new = matched - float(s.loc[m, "sim_8_9_scaled"].sum()) + \
            float((np.maximum(s.loc[m, "sim_8_9_scaled"],
                              s.loc[m, "twin_same_f89"] * SCALE)).sum())
        rows.append({"variant": "repair: same-name flowing max", "radius_m": thr,
                     "group_by": "", "group": "GLOBAL", "n": int(m.sum()),
                     "global_sim_obs": new / obs_tot,
                     "sim_obs_matched": np.nan, "sim_obs_repaired": new / obs_tot})

    # per-group under the widest name-twin repair (upper bound variant)
    m = ((s["twin_same_d"] <= TWIN_R_MAX) & (s["twin_same_f89"] > 0)).to_numpy()
    s["sim_repaired"] = np.where(m, np.maximum(s["sim_8_9_scaled"],
                                               s["twin_same_f89"] * SCALE),
                                 s["sim_8_9_scaled"])
    for key, tag in [("region", "region"), ("radial", "radial")]:
        for k, x in s.groupby(key):
            rows.append({"variant": "repair: same-name flowing max",
                         "radius_m": np.nan, "group_by": tag, "group": k,
                         "n": len(x),
                         "global_sim_obs": np.nan,
                         "sim_obs_matched": float(x["sim_8_9_scaled"].sum()
                                                  / x["obs_8_9"].sum()),
                         "sim_obs_repaired": float(x["sim_repaired"].sum()
                                                   / x["obs_8_9"].sum())})
    # ---- post-hoc DESCRIPTIVE bound: best-direction median repair ----------
    dirfix = directional_repair(ctx, sub)
    s["sim_dirfix"] = s["lta_linkid"].map(dirfix)
    new_dir = float(s["sim_dirfix"].sum())
    rows.append({"variant": "repair: best-direction median (POST-HOC)",
                 "radius_m": np.nan, "group_by": "", "group": "GLOBAL",
                 "n": len(s), "global_sim_obs": new_dir / obs_tot,
                 "sim_obs_matched": matched / obs_tot,
                 "sim_obs_repaired": new_dir / obs_tot})
    for key, tag in [("region", "region"), ("radial", "radial")]:
        for k, x in s.groupby(key):
            rows.append({"variant": "repair: best-direction median (POST-HOC)",
                         "radius_m": np.nan, "group_by": tag, "group": k,
                         "n": len(x), "global_sim_obs": np.nan,
                         "sim_obs_matched": float(x["sim_8_9_scaled"].sum()
                                                  / x["obs_8_9"].sum()),
                         "sim_obs_repaired": float(x["sim_dirfix"].sum()
                                                   / x["obs_8_9"].sum())})
    return pd.DataFrame(rows)


# ==========================================================================
# Layer 2 -- EAST <-> CENTRAL OD flow decomposition
# ==========================================================================

def _zone_region_band(ctx):
    d = ctx["d"]
    df = d["df"].copy()
    zd = d["zd"]
    zr = zd.set_index("zone_id")["planning_region"]
    df["o_r"] = df["origin_zone"].map(zr)
    df["d_r"] = df["destination_zone"].map(zr)
    df["ec_band"] = _add_ec_band(df)
    return df


def category_pairs():
    """resident -> CBD region pairs used as the direction-symmetry reference."""
    return [("EAST REGION", "CENTRAL REGION"),
            ("WEST REGION", "CENTRAL REGION"),
            ("NORTH REGION", "CENTRAL REGION"),
            ("NORTH-EAST REGION", "CENTRAL REGION")]


def part_C_layer2_od(ctx, out):
    banner("Layer 2a -- OD-side decomposition of the EAST <-> CENTRAL flow")
    df = _zone_region_band(ctx)
    regs = REGION_ORDER
    short = {r: r.replace(" REGION", "").replace("NORTH-EAST", "NE") for r in regs}

    blk = pd.DataFrame(
        [[float(df[(df["o_r"] == a) & (df["d_r"] == b)]["T_ij"].sum())
          for b in regs] for a in regs],
        index=[short[r] for r in regs], columns=[short[r] for r in regs])
    blk.to_csv(out / "od_region_block_matrix.csv", encoding="utf-8-sig")
    log("* regional OD block matrix (car trips, lambda=0.075), thousands:")
    log((blk / 1000.0).round(1).to_string())

    sym_rows = []
    for a, b in category_pairs():
        fwd = float(df[(df["o_r"] == a) & (df["d_r"] == b)]["T_ij"].sum())
        rev = float(df[(df["o_r"] == b) & (df["d_r"] == a)]["T_ij"].sum())
        sym_rows.append({"pair": f"{short[a]}->{short[b]}", "fwd": fwd, "rev": rev,
                         "rev_over_fwd": (rev / fwd) if fwd > 0 else np.nan})
    sym = pd.DataFrame(sym_rows)
    sym.to_csv(out / "od_direction_symmetry.csv", index=False, encoding="utf-8-sig")
    peer = sym[sym["pair"] != "EAST->CENTRAL"]
    ec_sym = float(sym.loc[sym["pair"] == "EAST->CENTRAL", "rev_over_fwd"].iloc[0])
    lo, hi = float(peer["rev_over_fwd"].min()), float(peer["rev_over_fwd"].max())
    log("")
    log("* direction symmetry of resident -> CBD blocks (rev / fwd):")
    log(sym.round(4).to_string(index=False))
    log(f"  EAST->CENTRAL asymmetry {ec_sym:.3f}; peers in [{lo:.3f}, {hi:.3f}] "
        f"-> {'INSIDE (normal)' if lo <= ec_sym <= hi else 'OUTSIDE (anomalous)'}")
    chk("T3.od_direction_symmetry_normal", round(ec_sym, 4),
        lo <= ec_sym <= hi, f"within [{lo:.3f}, {hi:.3f}]",
        "EAST->CENTRAL vs CENTRAL->EAST against the other residential->CBD blocks")

    bands = []
    for a, b, tag in [("EAST REGION", "CENTRAL REGION", "EAST->CENTRAL"),
                      ("CENTRAL REGION", "EAST REGION", "CENTRAL->EAST")]:
        x = df[(df["o_r"] == a) & (df["d_r"] == b)]
        tot = float(x["T_ij"].sum())
        for nm, lo2, hi2 in EC_BANDS:
            sel = x[(x["d_ff_cii_km"] >= lo2) & (x["d_ff_cii_km"] < hi2)]
            bands.append({"direction": tag, "band": nm,
                          "demand": float(sel["T_ij"].sum()),
                          "share": float(sel["T_ij"].sum() / tot),
                          "n_cells": int(len(sel))})
    bd = pd.DataFrame(bands)
    bd.to_csv(out / "od_east_central_distance_bands.csv",
              index=False, encoding="utf-8-sig")
    log("")
    log("* EAST<->CENTRAL demand by distance band (free-flow, c_ii proxy intra):")
    log(bd.pivot(index="band", columns="direction", values="demand")
        .reindex(EC_LABELS).round(0).to_string())

    t118 = pd.read_csv(T118_RESID_7_6C)
    wp = t118["workplace_pa"].astype(str).str.upper()
    phys = t118[~wp.str.contains("|".join(NON_PHYSICAL_MARKERS))].copy()
    resid = phys["abs_share_resid"].astype(float)
    med = float(resid.median())
    p95 = float(resid.quantile(0.95))
    log("")
    log(f"* attraction control (7.6C Table118, reused): {len(phys)} physical PA "
        f"cells (of {len(t118)}), median|resid| = {med:.4f}, P95 = {p95:.4f}")
    chk("T4.attraction_conserved_table118", round(med, 5),
        (med < 0.02) and (p95 < 0.10), "median<0.02 and P95<0.10",
        "reused from 7.6C -- workplace control conserved at Planning-Area level")

    return dict(block=blk, sym=sym, bands=bd, t118_med=med, t118_p95=p95)


def parse_route_trace(ctx, force=False):
    """Stream R01 realised routes -> per (o_region, d_region, band) link usage."""
    cache = OUT_DIR / "_route_trace_agg.parquet"
    if cache.exists() and not force:
        log(f"route trace    : [cached] <- {cache.name}")
        return pd.read_parquet(cache)

    src = R01_OUT / "R01_rc_min.output_plans.xml.gz"
    if not src.exists():
        log(f"route trace    : MISSING {src}")
        return pd.DataFrame()

    d = ctx["d"]
    zd = d["zd"]
    zr = zd.set_index("zone_id")["planning_region"]
    zids = zd["zone_id"].to_numpy(int)
    rmap = {int(z): REGION_ORDER.index(r) for z, r in zip(zids, zr.to_numpy())}

    bbl = d["df"][["origin_zone", "destination_zone", "d_ff_cii_km"]].copy()
    bbl["ec_band"] = _add_ec_band(bbl).astype(str)
    bidx = {nm: i for i, nm in enumerate(EC_LABELS)}
    band_map = {(int(o), int(x)): bidx.get(b, 0)
                for o, x, b in zip(bbl["origin_zone"], bbl["destination_zone"],
                                   bbl["ec_band"])}
    log(f"route trace    : OD lookup {len(band_map):,} cells / {len(rmap)} zones")

    links = ctx["links"]
    ridx = {r: i for i, r in enumerate(REGION_ORDER)}
    raidx = {r: i for i, r in enumerate(RADIAL_ORDER)}
    link_cls = {}
    for mid, rg, rd in zip(links["matsim_link_id"].to_numpy(),
                           links["region"].to_numpy(),
                           links["radial"].to_numpy()):
        link_cls[mid] = (ridx.get(rg, -1), raidx.get(rd, -1))
    cor_e_ri = {m for m, (ri, ai) in link_cls.items()
                if ri == REGION_ORDER.index("EAST REGION") and ai == 0}
    log(f"route trace    : {len(link_cls):,} links classified; "
        f"East radial_in corridor = {len(cor_e_ri):,} links")

    n_reg, n_rad, n_band = len(REGION_ORDER), len(RADIAL_ORDER), len(EC_BANDS)
    nkey = n_reg * n_reg * n_band
    FEAT = 2 + n_reg + n_rad
    acc = np.zeros((nkey, FEAT), dtype=np.float64)
    cor = np.zeros((n_reg, n_reg, n_band), dtype=np.float64)

    t0 = time.time()
    st = {"id": None, "o": None, "dd": None, "e": None, "links": None}
    n_person = 0

    def flush():
        nonlocal n_person
        if st["id"] is None or st["o"] is None or st["dd"] is None:
            return
        ri = rmap.get(st["o"], -1)
        di = rmap.get(st["dd"], -1)
        if ri < 0 or di < 0:
            return
        seq = st["links"]
        if seq is None:
            return
        bi = band_map.get((st["o"], st["dd"]), 0)
        exp = st["e"] if st["e"] is not None else 0.0
        cnt_r = np.zeros(n_reg)
        cnt_a = np.zeros(n_rad)
        n_cor = 0
        for lid in seq:
            c = link_cls.get(lid)
            if c is None:
                continue
            if c[0] >= 0:
                cnt_r[c[0]] += 1.0
            if c[1] >= 0:
                cnt_a[c[1]] += 1.0
            if lid in cor_e_ri:
                n_cor += 1
        key = (ri * n_reg + di) * n_band + bi
        acc[key, 0] += exp
        acc[key, 1] += exp * len(seq)
        acc[key, 2:2 + n_reg] += exp * cnt_r
        acc[key, 2 + n_reg:FEAT] += exp * cnt_a
        cor[ri, di, bi] += exp * n_cor
        n_person += 1
        st["id"] = st["o"] = st["dd"] = st["e"] = st["links"] = None

    with gzip.open(src, "rt", encoding="utf-8", errors="replace") as f:
        for event, elem in ET.iterparse(f, events=("start", "end")):
            tag = elem.tag
            if event == "start" and tag == "person":
                st["id"] = elem.get("id")
                st["o"] = st["dd"] = st["e"] = st["links"] = None
            elif event == "end" and tag == "attribute" and st["id"] is not None:
                nm = elem.get("name")
                if nm in ("originZone", "destinationZone", "expansionFactor"):
                    try:
                        v = (elem.text or "").strip()
                        if nm == "originZone":
                            st["o"] = int(v)
                        elif nm == "destinationZone":
                            st["dd"] = int(v)
                        else:
                            st["e"] = float(v)
                    except ValueError:
                        pass
            elif event == "end" and tag == "plan" and st["id"] is not None:
                if (elem.get("selected") or "").lower() == "yes":
                    rt = elem.find(".//route")
                    if rt is not None and rt.text:
                        st["links"] = rt.text.split()
                elem.clear()
            elif event == "end" and tag == "person":
                flush()
                elem.clear()

    log(f"route trace    : {n_person:,} realised routes streamed in "
        f"{time.time()-t0:.1f}s")

    recs = []
    for key in range(nkey):
        if acc[key, 0] <= 0:
            continue
        oi, rem = divmod(key, n_reg * n_band)
        di, bi = divmod(rem, n_band)
        rec = {"o_region": REGION_ORDER[oi], "d_region": REGION_ORDER[di],
               "band": EC_LABELS[bi], "demand": acc[key, 0],
               "total_route_links": acc[key, 1],
               "east_radial_in_hits": cor[oi, di, bi]}
        for j, rg in enumerate(REGION_ORDER):
            rec[f"links_in_{rg.split()[0].replace('-', '_')}"] = acc[key, 2 + j]
        for j, rd in enumerate(RADIAL_ORDER):
            rec[f"links_{rd}"] = acc[key, 2 + n_reg + j]
        recs.append(rec)
    rt = pd.DataFrame(recs)
    rt = rt[rt["demand"] > 0].copy()
    rt.to_parquet(cache, index=False)
    log(f"route trace    : cached -> {cache.name} ({len(rt)} non-empty cells)")
    return rt


def part_C_layer2_routes(ctx, out):
    banner("Layer 2b -- realised-route attribution of the EAST gap")
    rt = parse_route_trace(ctx)
    if not len(rt):
        log("route trace unavailable -> Layer 2b skipped")
        return None

    for rg in REGION_ORDER:
        k = f"links_in_{rg.split()[0].replace('-', '_')}"
        if k in rt.columns:
            rt[f"share_in_{rg.split()[0].replace('-', '_')}"] = (
                rt[k] / rt["total_route_links"])
    rt["share_radial_in"] = rt["links_radial_in"] / rt["total_route_links"]
    rt["share_radial_out"] = rt["links_radial_out"] / rt["total_route_links"]
    rt["share_circ"] = rt["links_circumferential"] / rt["total_route_links"]
    rt.to_csv(out / "route_attribution_by_region_pair.csv",
              index=False, encoding="utf-8-sig")

    rows = []
    for a, b, tag in [("EAST REGION", "CENTRAL REGION", "EAST->CENTRAL"),
                      ("CENTRAL REGION", "EAST REGION", "CENTRAL->EAST")]:
        x = rt[(rt["o_region"] == a) & (rt["d_region"] == b)]
        dem = float(x["demand"].sum())
        tl = float(x["total_route_links"].sum())
        rows.append({
            "direction": tag, "demand": dem,
            "mean_route_links": (tl / dem) if dem else np.nan,
            "share_radial_in": (float(x["links_radial_in"].sum()) / tl) if tl else np.nan,
            "share_radial_out": (float(x["links_radial_out"].sum()) / tl) if tl else np.nan,
            "share_circ": (float(x["links_circumferential"].sum()) / tl) if tl else np.nan,
            "east_radial_in_per_trip": (float(x["east_radial_in_hits"].sum()) / dem)
            if dem else np.nan,
        })
    head = pd.DataFrame(rows)
    head.to_csv(out / "east_central_route_profile.csv",
                index=False, encoding="utf-8-sig")
    log("* realised-route profile of the EAST<->CENTRAL flows:")
    log(head.round(4).to_string(index=False))

    per_band = []
    for a, b, tag in [("EAST REGION", "CENTRAL REGION", "EAST->CENTRAL"),
                      ("CENTRAL REGION", "EAST REGION", "CENTRAL->EAST")]:
        for nm in EC_LABELS:
            x = rt[(rt["o_region"] == a) & (rt["d_region"] == b) & (rt["band"] == nm)]
            dem = float(x["demand"].sum())
            tl = float(x["total_route_links"].sum())
            per_band.append({
                "direction": tag, "band": nm, "demand": dem,
                "share_radial_in": (float(x["links_radial_in"].sum()) / tl) if tl else np.nan,
                "share_radial_out": (float(x["links_radial_out"].sum()) / tl) if tl else np.nan,
                "mean_route_links": (tl / dem) if dem else np.nan})
    pb = pd.DataFrame(per_band)
    pb.to_csv(out / "east_central_route_profile_by_band.csv",
              index=False, encoding="utf-8-sig")
    log("")
    log("* per-band realised-route radial profile:")
    log(pb.round(4).to_string(index=False))

    prof = []
    for o_r, x in rt.groupby("o_region"):
        dem = float(x["demand"].sum())
        tl = float(x["total_route_links"].sum())
        prof.append({"origin_region": o_r, "demand": dem,
                     "east_radial_in_per_trip": (float(x["east_radial_in_hits"].sum())
                                                 / dem) if dem else np.nan,
                     "share_radial_in": (float(x["links_radial_in"].sum()) / tl)
                     if tl else np.nan,
                     "share_circ": (float(x["links_circumferential"].sum()) / tl)
                     if tl else np.nan})
    pr = pd.DataFrame(prof).sort_values("demand", ascending=False)
    pr.to_csv(out / "radial_in_usage_by_origin_region.csv",
              index=False, encoding="utf-8-sig")
    log("")
    log("* network-wide radial_in usage by origin region "
        "(route link share; East-corridor hits per trip):")
    log(pr.round(4).to_string(index=False))
    return dict(rt=rt, head=head, per_band=pb, origin_profile=pr)


def verdict():
    def ok(name):
        return next((c["ok"] for c in CHECKS if c["check"] == name), False)

    crit = {
        "T1_hard_zero_topology": ok("T1.focus_links_never_used_all_windows"),
        "T2_twin_proximity": ok("T2.zero_sim_twin_within_60m"),
        "T3_od_direction_normal": ok("T3.od_direction_symmetry_normal"),
        "T4_attraction_conserved": ok("T4.attraction_conserved_table118"),
        "T5_radial_in_residual_robust": ok("T5.radial_in_residual_after_repair"),
    }
    cov = crit["T1_hard_zero_topology"] and crit["T2_twin_proximity"]
    resid = crit["T5_radial_in_residual_robust"]
    if cov and resid:
        v = "MIXED_COVERAGE_AND_RESIDUAL_STRUCTURE"
        nxt = ("硬零流 = 覆盖/归属伪影（可正式从 demand 靶场扣除）；"
               "但 graded 区域/径向缺口对 link-attribution 校正稳健 ⇒ "
               "在这部分解释清楚前不得用 0.8590 反推 demand scale。"
               "可进入 7.6F-1，但必须双口径并报且必须用 MATCHED")
    elif cov:
        v = "ANOMALY_IS_COVERAGE_ARTIFACT"
        nxt = "0.8590 -> 0.9351 的跳升基本是测量伪影；可进入 7.6F-1"
    else:
        v = "ANOMALY_STRUCTURAL"
        nxt = "先修空间/网络结构，再谈 demand scale；7.6F-1 暂停"
    return {"verdict": v, "criteria": crit, "n_criteria_pass": sum(crit.values()),
            "n_criteria_total": len(crit), "next": nxt,
            "coverage_explains_hard_zeros": bool(cov),
            "residual_structure_after_repair": bool(resid)}


# ==========================================================================
# main
# ==========================================================================

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--force-routes", action="store_true",
                    help="re-stream the 190 MB R01 plans even if the cache exists")
    args = ap.parse_args()

    t_start = time.time()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    ctx = load_context()

    l1 = part_A_layer1(ctx, OUT_DIR)

    banner("Layer 2a -- OD-side decomposition + link-attribution bounds")
    l2o = part_C_layer2_od(ctx, OUT_DIR)

    # residual-structure comparison at the widest repair radius
    b = l1["bounds"]
    log("")
    log("* residual structure check (widest same-name twin repair):")
    rad_tbl = b[b["group_by"].astype(str) == "radial"] if "group_by" in b.columns \
        else pd.DataFrame()
    if len(rad_tbl):
        log(rad_tbl.round(4).to_string(index=False))
        m = {r["group"]: r["sim_obs_repaired"] for _, r in rad_tbl.iterrows()}
        ok_resid = (m.get("radial_in", 1.0) < m.get("circumferential", 0.0)
                    and m.get("radial_in", 1.0) < m.get("radial_out", 0.0))
        chk("T5.radial_in_residual_after_repair",
            round(m.get("radial_in", np.nan), 4), bool(ok_resid),
            "radial_in < circumferential AND radial_in < radial_out",
            f"repaired radial_in={m.get('radial_in'):.3f} vs "
            f"circ={m.get('circumferential'):.3f} / out={m.get('radial_out'):.3f}")
        reg_tbl = b[b["group_by"].astype(str) == "region"]
        if len(reg_tbl):
            log("")
            log("* residual by region after repair (widest radius):")
            log(reg_tbl.round(4).to_string(index=False))
    else:
        chk("T5.radial_in_residual_after_repair", np.nan, False,
            "radial_in < circumferential AND radial_in < radial_out",
            "repair table unavailable")

    l2r = part_C_layer2_routes(ctx, OUT_DIR)
    v = verdict()
    n_pass = sum(1 for c in CHECKS if c["ok"])

    summary = {
        "step": "7.6C-1",
        "status": v["verdict"],
        "verdict_detail": v,
        "zero_simulation": True,
        "matsim_rerun": False,
        "parameters_changed": False,
        "demand_scale_selected": False,
        "lambda_selected": False,
        "anchor_sim_obs": ANCHOR_SIM_OBS,
        "scale": SCALE,
        "checks_pass": n_pass,
        "checks_total": len(CHECKS),
        "checks": CHECKS,
        "preregistered": PREREGISTERED,
        "layer1": {
            "n_zero_sim_sections": int(len(l1["zero"])),
            "obs_share_on_zero_sim": float(l1["zero"]["obs_8_9"].sum()
                                           / l1["sub"]["obs_8_9"].sum()),
            "focus_set": {"ring": R5_RI_RING, "radial": "radial_in",
                          "n_sections": int(len(l1["focus"])),
                          "obs": float(l1["focus"]["obs_8_9"].sum())},
            "focus_matched_links": {
                "n": int(len(l1["trace"])),
                "never_used_all_windows": int(((l1["trace"]["f78"] == 0)
                                               & (l1["trace"]["f89"] == 0)
                                               & (l1["trace"]["f24"] == 0)
                                               & (l1["trace"]["rev_f89"] == 0)
                                               & (l1["trace"]["rev_f24"] == 0)).sum()),
                "orphan": int(l1["trace"]["orphan"].sum()),
                "fully_connected": int((l1["trace"]["in_reachable"]
                                        & l1["trace"]["out_reachable"]).sum()),
            },
            "mechanism_counts": {str(k): int(v2) for k, v2 in
                                 l1["mech"]["mechanism"].value_counts().items()},
            "twin_within_60m": int((l1["mech"]["twin_d_any_m"]
                                    <= TWIN_R_PRIMARY).sum()),
            "zero_sim_by_region_radial": _jsonable(
                pd.crosstab(l1["zero"]["region"], l1["zero"]["radial"])
                .to_dict(orient="index")),
        },
        "layer2": {
            "east_central_od": {
                "EAST_to_CENTRAL": float(l2o["sym"].loc[
                    l2o["sym"]["pair"] == "EAST->CENTRAL", "fwd"].iloc[0]),
                "CENTRAL_to_EAST": float(l2o["sym"].loc[
                    l2o["sym"]["pair"] == "EAST->CENTRAL", "rev"].iloc[0]),
                "symmetry": float(l2o["sym"].loc[
                    l2o["sym"]["pair"] == "EAST->CENTRAL", "rev_over_fwd"].iloc[0]),
            },
            "table118_median_abs_resid": l2o["t118_med"],
            "table118_p95_abs_resid": l2o["t118_p95"],
        },
        "outputs_dir": str(OUT_DIR),
        "runtime_s": round(time.time() - t_start, 1),
    }
    if l2r is not None:
        summary["layer2"]["east_central_route_profile"] = \
            _jsonable(l2r["head"].to_dict(orient="records"))
        summary["layer2"]["radial_in_usage_by_origin_region"] = \
            _jsonable(l2r["origin_profile"].to_dict(orient="records"))

    with open(OUT_DIR / "od_anomaly_trace_7_6c_1_summary.json", "w",
              encoding="utf-8") as f:
        json.dump(_jsonable(summary), f, ensure_ascii=False, indent=1)

    banner("VERDICT")
    log(f"status     : {v['verdict']}")
    log(f"criteria   : {v['criteria']}  ({v['n_criteria_pass']}/{v['n_criteria_total']})")
    log(f"checks     : {n_pass}/{len(CHECKS)}")
    log(f"next       : {v['next']}")
    log(f"runtime    : {summary['runtime_s']}s")
    log(f"outputs    : {OUT_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
