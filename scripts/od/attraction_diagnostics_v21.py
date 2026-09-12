#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Step 3B.1 diagnostics: Attraction v1 / v2 / v2.1 三方对比与空间合理性诊断.

输出到 reports/od_attraction_v21/:
    attraction_v1_v2_v21_comparison.csv
    attraction_v21_diagnostics.csv
    pa_employment_concentration.csv
    attraction_v21_diagnostics.json

原则: 只读 v1/v2/v2.1 产物, 不修改任何上游文件; 不做任何人工调整。
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(r"D:\Luan\2026-05\2_Singapore")
V1 = ROOT / "reports/od_attraction/attraction.csv"
V2 = ROOT / "reports/od_attraction_v2/attraction_v2.csv"
V21 = ROOT / "reports/od_attraction_v21/attraction_v21.csv"
PRE = ROOT / "reports/od_attraction_v21/_prefix_buildingfilter_off/attraction_v21_prefix.csv"
OUT = ROOT / "reports/od_attraction_v21"

KEYS = ["JURONG ISLAND AND BUKOM", "MURAI", "CHANGI AIRPORT", "UPPER THOMSON", "DHOBY GHAUT"]


def _acol(df):
    for c in ("workplace_attraction", "attraction"):
        if c in df.columns:
            return c
    raise KeyError("找不到 attraction 列")


def _share(m, col, group="planning_area"):
    tot = m.groupby(group)[col].transform("sum")
    return np.where(tot > 0, m[col] / tot, 0.0)


def _spearman(a, b):
    s = pd.DataFrame({"a": a, "b": b}).dropna()
    return float(s.corr(method="spearman").iloc[0, 1]) if len(s) > 2 else float("nan")


def main():
    v1 = pd.read_csv(V1, encoding="utf-8-sig")
    v2 = pd.read_csv(V2, encoding="utf-8-sig")
    v21 = pd.read_csv(V21, encoding="utf-8-sig")

    m = v21[["zone_id", "subzone_code", "subzone_name", "planning_area", "planning_region",
             "workplace_employment"]].copy()
    for tag, df in (("v1", v1), ("v2", v2), ("v21", v21)):
        a = _acol(df)
        m = m.merge(df[["zone_id", a]].rename(columns={a: f"A_{tag}"}), on="zone_id", how="left")

    for tag in ("v1", "v2", "v21"):
        m[f"share_{tag}"] = _share(m, f"A_{tag}")
    m["delta_v21_v2"] = m["A_v21"] - m["A_v2"]
    m["delta_v21_v1"] = m["A_v21"] - m["A_v1"]
    m["delta_v2_v1"] = m["A_v2"] - m["A_v1"]

    def azp(df, acra="acra_activity_weight"):
        a = _acol(df)
        return int(((df[acra].fillna(0) <= 0) & (df[a].fillna(0) > 1e-9)).sum()) if acra in df.columns else None

    nz = v21[v21["workplace_attraction"] > 0]

    def corr(col):
        if col not in nz.columns:
            return None
        return float(nz[[col, "workplace_attraction"]].corr().iloc[0, 1])

    summary = {
        "zones": int(len(m)),
        "zero_attraction": {t: int((m[f"A_{t}"] <= 1e-12).sum()) for t in ("v1", "v2", "v21")},
        "single_zone_share_gt_50pct": {t: int((m[f"share_{t}"] > 0.5).sum()) for t in ("v1", "v2", "v21")},
        "single_zone_share_gt_60pct": {t: int((m[f"share_{t}"] > 0.6).sum()) for t in ("v1", "v2", "v21")},
        "max_zone_share_within_pa": {t: float(m[f"share_{t}"].max()) for t in ("v1", "v2", "v21")},
        "acra_zero_but_attraction_positive": {
            "v1": azp(v1), "v2": azp(v2), "v21": azp(v21)},
        "total_abs_redistribution_persons": {
            "v2_vs_v1": float(m["delta_v2_v1"].abs().sum()),
            "v21_vs_v2": float(m["delta_v21_v2"].abs().sum()),
            "v21_vs_v1": float(m["delta_v21_v1"].abs().sum()),
        },
        "spearman_share": {
            "v1_v2": _spearman(m["share_v1"], m["share_v2"]),
            "v2_v21": _spearman(m["share_v2"], m["share_v21"]),
            "v1_v21": _spearman(m["share_v1"], m["share_v21"]),
        },
        "correlation_with_attraction_v21": {
            "acra": corr("acra_activity_weight"),
            "gfa": corr("building_gfa_m2"),
            "landuse": corr("landuse_weighted_area"),
            "poi": corr("poi_activity_weight"),
        },
        "pa_concentration_mean_top1_share": {t: float(v21.assign(s=m[f"share_{t}"]).groupby("planning_area")["s"].max().mean()) for t in ("v1", "v2", "v21")},
    }

    # ---- 建筑过滤 bug 影响（前缀 vs 终版）----
    if PRE.exists():
        pr = pd.read_csv(PRE, encoding="utf-8-sig")
        c = v21[["zone_id", "subzone_name", "planning_area", "building_footprint_m2",
                 "building_gfa_m2", "workplace_attraction", "attraction_share_within_pa"]].merge(
            pr[["zone_id", "building_footprint_m2", "building_gfa_m2", "workplace_attraction",
                "attraction_share_within_pa"]],
            on="zone_id", how="left", suffixes=("", "_prefix"))
        c["d_share"] = c["attraction_share_within_pa"] - c["attraction_share_within_pa_prefix"]
        summary["building_filter_impact"] = {
            "total_footprint_km2_prefix(no_filter)": float(pr["building_footprint_m2"].sum() / 1e6),
            "total_footprint_km2_final": float(v21["building_footprint_m2"].sum() / 1e6),
            "total_gfa_prefix": float(pr["building_gfa_m2"].sum()),
            "total_gfa_final": float(v21["building_gfa_m2"].sum()),
            "sum_abs_attraction_delta": float(c["workplace_attraction"].sub(c["workplace_attraction_prefix"]).abs().sum()) if "workplace_attraction_prefix" in c else None,
            "spearman_share_prefix_vs_final": _spearman(c["attraction_share_within_pa_prefix"], c["attraction_share_within_pa"]),
        }
        c.to_csv(OUT / "attraction_v21_buildingfilter_impact.csv", index=False, encoding="utf-8-sig")

    keys = m[m["subzone_name"].isin(KEYS)][
        ["zone_id", "subzone_name", "planning_area", "A_v1", "A_v2", "A_v21",
         "share_v1", "share_v2", "share_v21"]
    ].sort_values("share_v21", ascending=False)

    # ---- PA 集中度 ----
    rows = []
    for pa, gp in m.groupby("planning_area"):
        base = v21.loc[v21["planning_area"] == pa]
        rows.append({
            "planning_area": pa,
            "planning_region": base["planning_region"].iloc[0] if len(base) else "",
            "census_control": float(gp["workplace_employment"].iloc[0]),
            "n_zones": int(len(gp)),
            "max_share_v1": float(gp["share_v1"].max()),
            "max_share_v2": float(gp["share_v2"].max()),
            "max_share_v21": float(gp["share_v21"].max()),
            "hhi_v1": float((gp["share_v1"] ** 2).sum()),
            "hhi_v2": float((gp["share_v2"] ** 2).sum()),
            "hhi_v21": float((gp["share_v21"] ** 2).sum()),
        })
    conc = pd.DataFrame(rows).sort_values("max_share_v21", ascending=False)
    conc.to_csv(OUT / "pa_employment_concentration.csv", index=False, encoding="utf-8-sig")

    m.to_csv(OUT / "attraction_v1_v2_v21_comparison.csv", index=False, encoding="utf-8-sig")

    d = v21[[
        "zone_id", "subzone_code", "subzone_name", "planning_area", "planning_region",
        "workplace_employment", "workplace_attraction", "attraction_share_within_pa",
        "acra_enterprise_count", "acra_activity_weight", "acra_component",
        "building_footprint_m2", "building_gfa_m2", "mean_building_levels",
        "building_levels_explicit_share", "gfa_component",
        "landuse_weighted_area", "landuse_component", "poi_activity_weight", "poi_component",
    ]].rename(columns={"workplace_employment": "census_control_pa"}).copy()
    d["flag_acra_zero_positive"] = (d["acra_activity_weight"] <= 0) & (d["workplace_attraction"] > 1e-9)
    d["flag_gfa_zero_positive"] = (d["building_gfa_m2"] <= 0) & (d["workplace_attraction"] > 1e-9)
    d["flag_single_zone_over_50pct"] = d["attraction_share_within_pa"] > 0.5
    d["flag_low_levels_pa"] = d["mean_building_levels"] < 1.5
    d["attraction_share_in_total"] = d["workplace_attraction"] / max(d["workplace_attraction"].sum(), 1e-9)
    d.to_csv(OUT / "attraction_v21_diagnostics.csv", index=False, encoding="utf-8-sig")

    (OUT / "attraction_v21_diagnostics.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    print("=" * 78)
    print("Step 3B.1 | Diagnostics  v1 -> v2 -> v2.1")
    print("=" * 78)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print("\n=== 关键 Subzone ===")
    print(keys.to_string(index=False))
    print("\n=== PA 内单区占比最高 10 个 PA (v21) ===")
    print(conc.head(10)[["planning_area", "census_control", "n_zones",
                         "max_share_v1", "max_share_v2", "max_share_v21",
                         "hhi_v1", "hhi_v2", "hhi_v21"]].to_string(index=False))
    print("\n=== v21 内部占比 Top 12 ===")
    print(v21.sort_values("workplace_attraction", ascending=False).head(12)[
        ["subzone_name", "planning_area", "acra_enterprise_count", "building_gfa_m2",
         "mean_building_levels", "attraction_share_within_pa", "workplace_attraction"]
    ].to_string(index=False))
    print(f"\nOUTPUT -> {OUT}")


if __name__ == "__main__":
    main()
