#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Step 3B diagnostics: compare Attraction v1 vs v2 and emit space-reasonableness flags.

输出:
    reports/od_attraction_v2/attraction_diagnostics.csv
    reports/od_attraction_v2/attraction_v1_v2_comparison.csv
    reports/od_attraction_v2/attraction_diagnostics.json

原则: 只读 v1/v2 产物, 不修改任何上游文件。
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(r"D:\Luan\2026-05\2_Singapore")
V1 = ROOT / "reports/od_attraction/attraction.csv"
V2 = ROOT / "reports/od_attraction_v2/attraction_v2.csv"
OUT = ROOT / "reports/od_attraction_v2"


def main():
    v1 = pd.read_csv(V1, encoding="utf-8-sig")
    v2 = pd.read_csv(V2, encoding="utf-8-sig")

    d = v2[
        [
            "zone_id",
            "subzone_code",
            "subzone_name",
            "planning_area",
            "planning_region",
            "workplace_employment",
            "workplace_attraction",
            "acra_enterprise_count",
            "acra_activity_weight",
            "building_footprint_m2",
            "building_gfa_m2",
            "mean_building_levels",
            "landuse_weighted_area",
            "poi_activity_weight",
            "attraction_share_within_pa",
        ]
    ].copy()
    d = d.rename(columns={"workplace_employment": "census_control_pa"})

    # ---- flags ----
    d["flag_acra_zero_positive"] = (d["acra_activity_weight"] <= 0) & (
        d["workplace_attraction"] > 1e-9
    )
    d["flag_gfa_zero_positive"] = (d["building_gfa_m2"] <= 0) & (
        d["workplace_attraction"] > 1e-9
    )
    d["flag_single_zone_over_50pct"] = d["attraction_share_within_pa"] > 0.5
    # 低层数覆盖率提示: PA 平均层数接近 1 说明 GFA 退化为 footprint
    d["flag_low_levels_pa"] = d["mean_building_levels"] < 1.5

    # PA 级汇总
    pa = (
        d.groupby("planning_area", as_index=False)
        .agg(
            pa_control=("census_control_pa", "first"),
            pa_attraction=("workplace_attraction", "sum"),
            pa_zones=("zone_id", "count"),
            pa_max_share=("attraction_share_within_pa", "max"),
        )
    )
    d = d.merge(
        pa[["planning_area", "pa_max_share"]], on="planning_area", how="left"
    )

    OUT.mkdir(parents=True, exist_ok=True)
    d.to_csv(OUT / "attraction_diagnostics.csv", index=False, encoding="utf-8-sig")

    # ---- v1 vs v2 comparison ----
    m = v1[
        ["zone_id", "subzone_name", "planning_area", "workplace_attraction"]
    ].rename(columns={"workplace_attraction": "A_v1"})
    m = m.merge(
        v2[["zone_id", "workplace_attraction"]].rename(
            columns={"workplace_attraction": "A_v2"}
        ),
        on="zone_id",
        how="outer",
    )
    for tag, col in (("v1", "A_v1"), ("v2", "A_v2")):
        tot = m.groupby("planning_area")[col].transform("sum")
        m[f"share_{tag}"] = np.where(tot > 0, m[col] / tot, 0.0)
    m["delta"] = m["A_v2"] - m["A_v1"]
    m["delta_share"] = m["share_v2"] - m["share_v1"]
    m.to_csv(
        OUT / "attraction_v1_v2_comparison.csv", index=False, encoding="utf-8-sig"
    )

    nz = m[m["A_v1"] > 0]
    w1 = np.average(nz["share_v1"], weights=nz["A_v1"])
    summary = {
        "zones": int(len(d)),
        "zero_attraction_v2": int((d["workplace_attraction"] <= 1e-12).sum()),
        "flag_acra_zero_positive": int(d["flag_acra_zero_positive"].sum()),
        "flag_gfa_zero_positive": int(d["flag_gfa_zero_positive"].sum()),
        "flag_single_zone_over_50pct": int(d["flag_single_zone_over_50pct"].sum()),
        "v1_single_zone_over_50pct": int((m["share_v1"] > 0.5).sum()),
        "v2_single_zone_over_50pct": int((m["share_v2"] > 0.5).sum()),
        "v1_single_zone_over_60pct": int((m["share_v1"] > 0.6).sum()),
        "v2_single_zone_over_60pct": int((m["share_v2"] > 0.6).sum()),
        "total_abs_redistribution_m2_persons": float(m["delta"].abs().sum()),
        "max_abs_zone_delta": float(m["delta"].abs().max()),
        "spearman_share_v1_v2": float(
            m.loc[m["A_v1"] > 0, ["share_v1", "share_v2"]].corr(method="spearman").iloc[0, 1]
        ),
        "corr_acra_attraction_v2": float(
            d.loc[d["workplace_attraction"] > 0, ["acra_activity_weight", "workplace_attraction"]].corr().iloc[0, 1]
        ),
        "corr_gfa_attraction_v2": float(
            d.loc[d["workplace_attraction"] > 0, ["building_gfa_m2", "workplace_attraction"]].corr().iloc[0, 1]
        ),
        "corr_landuse_attraction_v2": float(
            d.loc[d["workplace_attraction"] > 0, ["landuse_weighted_area", "workplace_attraction"]].corr().iloc[0, 1]
        ),
        "corr_poi_attraction_v2": float(
            d.loc[d["workplace_attraction"] > 0, ["poi_activity_weight", "workplace_attraction"]].corr().iloc[0, 1]
        ),
    }
    (OUT / "attraction_diagnostics.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    print("=" * 72)
    print("Step 3B | Diagnostics")
    print("=" * 72)
    for k, val in summary.items():
        print(f"  {k:42s}: {val}")
    print(f"  output -> {OUT}")
    print("=" * 72)

    print("\n=== 变化最大的 10 个 Subzone (|delta|) ===")
    top = m.reindex(m["delta"].abs().sort_values(ascending=False).index).head(10)
    print(
        top[["zone_id", "subzone_name", "planning_area", "A_v1", "A_v2", "share_v1", "share_v2", "delta"]]
        .to_string(index=False)
    )


if __name__ == "__main__":
    main()
