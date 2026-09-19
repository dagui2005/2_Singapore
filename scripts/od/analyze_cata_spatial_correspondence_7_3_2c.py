#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Step 7.3.2C-2
CATA Spatial Correspondence

把 1,278 个 LTA 流量断面（6.3.2 tight crosswalk）落到其匹配的 MATSim 边上，
再叠加 7.3.2C 的 route 装载计数（edge_route_loading.csv），回答：

    LTA 的 CATA 观测点，是落在「高装载」还是「低装载」的
    MATSim motorway corridor 上？

本步骤：
    不修改 OD / lambda / population / departure / network /
    capacity / route-choice / crosswalk
    只做空间对应诊断。
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(r"D:\Luan\2026-05\2_Singapore")

CROSSWALK = ROOT / "reports" / "matsim_assignment_6_3_2" / "lta_section_matsim_crosswalk.csv"
SECTION_FLOW = ROOT / "reports" / "matsim_assignment_6_3_2" / "section_flow_comparison_lambda_0p050.csv"
EDGE_LOADING = ROOT / "reports" / "od_route_diagnosis_7_3_2c" / "edge_route_loading.csv"
OUT = ROOT / "reports" / "od_route_diagnosis_7_3_2c"


def main() -> None:
    print("[1/4] load crosswalk")
    cw = pd.read_csv(CROSSWALK, encoding="utf-8-sig", low_memory=False)
    cw = cw[["LinkID", "matsim_link_id", "highway", "RoadCat"]].copy()

    print("[2/4] load edge loading")
    ed = pd.read_csv(EDGE_LOADING, encoding="utf-8-sig", low_memory=False)
    ed = ed[["link", "highway", "motorway_route_count", "motorway_link_route_count"]].copy()
    ed = ed.rename(columns={"link": "matsim_link_id", "highway": "edge_class"})

    print("[3/4] load section flow")
    sf = pd.read_csv(SECTION_FLOW, encoding="utf-8-sig", low_memory=False)
    sf = sf[["LinkID", "RoadCat", "n_edges_matched", "obs_am",
             "sim_median_scaled", "sim_sum_scaled", "rel_err_median"]].copy()

    # ---- join: section -> matched edges -> loading ----
    m = cw.merge(ed, on="matsim_link_id", how="left")
    m["motorway_route_count"] = m["motorway_route_count"].fillna(0)
    m["motorway_link_route_count"] = m["motorway_link_route_count"].fillna(0)

    # network-wide motorway / ramp reference means (over ALL such edges)
    mw_all = ed[ed["edge_class"] == "motorway"]["motorway_route_count"]
    rp_all = ed[ed["edge_class"] == "motorway_link"]["motorway_link_route_count"]
    net_mw_mean = float(mw_all.mean())
    net_rp_mean = float(rp_all.mean())
    net_mw_used_mean = float(mw_all[mw_all > 0].mean())

    print(f"    network motorway edges={len(mw_all):,} mean={net_mw_mean:.1f} "
          f"used_mean={net_mw_used_mean:.1f}")

    # per-section aggregates over MOTORWAY matched edges only
    mw = m[m["edge_class"] == "motorway"]
    agg = mw.groupby("LinkID").agg(
        n_mw_edges=("matsim_link_id", "size"),
        mw_load_mean=("motorway_route_count", "mean"),
        mw_load_max=("motorway_route_count", "max"),
        mw_load_sum=("motorway_route_count", "sum"),
    ).reset_index()

    # also total matched edges and ramp matched edges
    tot = m.groupby("LinkID").agg(n_edges_total=("matsim_link_id", "size")).reset_index()
    rp = m[m["edge_class"] == "motorway_link"].groupby("LinkID").agg(
        n_ramp_edges=("matsim_link_id", "size"),
        ramp_load_mean=("motorway_link_route_count", "mean"),
    ).reset_index()

    sec = (sf.merge(agg, on="LinkID", how="left")
             .merge(tot, on="LinkID", how="left")
             .merge(rp, on="LinkID", how="left"))
    for c in ["n_mw_edges", "n_ramp_edges"]:
        sec[c] = sec[c].fillna(0).astype(int)
    sec["n_edges_total"] = sec["n_edges_total"].fillna(0).astype(int)

    # corridor loading index vs network mean (only where motorway matched)
    sec["mw_load_index"] = sec["mw_load_mean"] / net_mw_mean
    sec["ramp_load_index"] = sec["ramp_load_mean"] / net_rp_mean
    sec["sim_obs"] = sec["sim_median_scaled"] / sec["obs_am"].replace(0, np.nan)

    sec.to_csv(OUT / "cata_section_spatial_correspondence.csv",
               index=False, encoding="utf-8-sig")

    # ---- by RoadCat ----
    rows = []
    for rc, g in sec.groupby("RoadCat"):
        gg = g[g["n_mw_edges"] > 0]
        rows.append({
            "RoadCat": rc,
            "n_sections": int(len(g)),
            "n_sections_with_motorway_matched": int(len(gg)),
            "mw_part=": "",
            "mw_load_index_mean": float(gg["mw_load_index"].mean()) if len(gg) else np.nan,
            "mw_load_index_median": float(gg["mw_load_index"].median()) if len(gg) else np.nan,
            "sim_obs_mean": float(g["sim_obs"].mean()),
            "sim_obs_median": float(g["sim_obs"].median()),
        })
    byrc = pd.DataFrame(rows).drop(columns=["mw_part="])
    byrc.to_csv(OUT / "cata_loading_index_by_roadcat.csv",
                index=False, encoding="utf-8-sig")

    # ---- correlations ----
    def corr(sub, col):
        s = sub[[col, "sim_obs"]].dropna()
        if len(s) < 3:
            return np.nan, int(len(s))
        return float(np.corrcoef(s[col], s["sim_obs"])[0, 1]), int(len(s))

    cata = sec[(sec["RoadCat"] == "CATA") & (sec["n_mw_edges"] > 0)]
    r_cata, n_cata = corr(cata, "mw_load_index")
    r_all, n_all = corr(sec[sec["n_mw_edges"] > 0], "mw_load_index")

    # share of CATA sections below/above network mean
    below = int((cata["mw_load_index"] < 1).sum())
    above = int((cata["mw_load_index"] >= 1).sum())

    summary = {
        "step": "7.3.2C-2",
        "status": "PASS",
        "network_motorway_edges": int(len(mw_all)),
        "network_motorway_mean_loading": net_mw_mean,
        "network_motorway_used_mean_loading": net_mw_used_mean,
        "network_motorway_link_mean_loading": net_rp_mean,
        "sections_total": int(len(sec)),
        "cata_sections_with_motorway_matched": int(len(cata)),
        "cata_below_network_mean": below,
        "cata_above_network_mean": above,
        "cata_below_share": below / len(cata) if len(cata) else np.nan,
        "cata_mw_load_index_mean": float(cata["mw_load_index"].mean()),
        "cata_mw_load_index_median": float(cata["mw_load_index"].median()),
        "cata_sim_obs_mean": float(cata["sim_obs"].mean()),
        "pearson_mw_load_index_vs_sim_obs_CATA": r_cata,
        "n_CATA_for_corr": n_cata,
        "pearson_mw_load_index_vs_sim_obs_all": r_all,
        "n_all_for_corr": n_all,
        "frozen_inputs_unchanged": True,
        "lambda_selected": False,
    }
    with open(OUT / "cata_spatial_correspondence_summary.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    print("[4/4] done")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
