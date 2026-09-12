#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Singapore OD -> MATSim
Step 3: Build workplace attraction / employment by Subzone.

目标：
    Census Workplace PA employment control
        +
    ACRA enterprise spatial distribution
        +
    Master Plan land-use intensity
    ->
    Subzone-level workplace attraction A_j

核心原则：
    1. Census PA employment is the control total.
    2. ACRA is NOT treated as employee count.
    3. ACRA contributes spatial + industry activity weight.
    4. LandUse contributes employment/activity capacity weight.
    5. Within each workplace PA, final Subzone attraction is normalized
       to the Census control total.
    6. Unlocated ACRA is NOT discarded from the Census control total;
       it is represented indirectly through Census-controlled normalization.
    7. This version is intentionally transparent and auditable.
       ACRA/building/POI weights are exposed as columns.

Expected upstream:
    reports/od_zone/zone_dictionary.csv
    reports/od_production/production.csv
    Singapore_OD_MATSim_FinalData/

Expected outputs:
    reports/od_attraction/
        pa_workplace_control.csv
        acra_subzone_activity.csv
        subzone_activity_weights.csv
        attraction.csv
        attraction_validation.json

Notes:
    - The script auto-detects Census T4 numeric total column.
    - It supports the documented "Other Planning Areas or Outside Singapore"
      special workplace categories by retaining them in control output.
    - 44 workplace PAs are treated as physical destination controls.
    - Special / outside categories are not forced into the 332 physical zones.
"""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd


DEFAULT_PROJECT_ROOT = Path(r"D:\Luan\2026-05\2_Singapore")
DATA_DIR_NAME = "Singapore_OD_MATSim_FinalData"

ZONE_FILE = Path("reports/od_zone/zone_dictionary.csv")
PRODUCTION_FILE = Path("reports/od_production/production.csv")
T4_FILE = Path(
    f"{DATA_DIR_NAME}/03_Workplace_Employment/outputFile (3)__T4.csv"
)
ACRA_DIR = Path(f"{DATA_DIR_NAME}/05_POI_Enterprise/ACRA")
LANDUSE_FILE = Path(
    f"{DATA_DIR_NAME}/04_LandUse_Building/MasterPlan2019LandUselayer.geojson"
)
POI_FILE = Path(f"{DATA_DIR_NAME}/05_POI_Enterprise/poi.csv")

SPECIAL_DESTINATIONS = {
    "OTHER PLANNING AREAS OR OUTSIDE SINGAPORE",
    "NO FIXED LOCATION FOR WORK",
    "WORKS FROM HOME",
}

# Initial transparent weights.
# We deliberately avoid using officer count as a direct employee estimate.
LANDUSE_WEIGHT = {
    "BUSINESS PARK": 3.0,
    "COMMERCIAL": 2.5,
    "BUSINESS 1": 2.5,
    "BUSINESS 2": 2.5,
    "RESIDENTIAL WITH COMMERCIAL AT 1ST STOREY": 1.5,
    "WHITE": 2.0,
    "INDUSTRIAL": 2.0,
    "LIGHT INDUSTRIAL": 2.0,
    "GENERAL INDUSTRIAL": 2.0,
    "EDUCATIONAL INSTITUTION": 1.8,
    "HEALTH & MEDICAL CARE": 2.0,
    "CIVIC & COMMUNITY INSTITUTION": 1.5,
    "SPORTS & RECREATION": 1.0,
    "HOTEL": 1.5,
    "RESIDENTIAL": 0.15,
    "PARK": 0.05,
    "OPEN SPACE": 0.05,
    "ROAD": 0.0,
}

# ACRA status terms that are generally not active operating entities.
INACTIVE_STATUS_HINTS = {
    "STRUCK OFF",
    "DISSOLVED",
    "CEASED",
    "CANCELLED",
    "LIQUIDATED",
    "WOUND UP",
    "TERMINATED",
}


def norm_text(x) -> str:
    if pd.isna(x):
        return ""
    s = str(x).replace("\xa0", " ").strip()
    s = re.sub(r"\s+", " ", s)
    return s


def norm_name(x) -> str:
    return norm_text(x).upper()


def numeric_series(s: pd.Series) -> pd.Series:
    return pd.to_numeric(
        s.astype(str).str.replace(",", "", regex=False),
        errors="coerce",
    )


def detect_first_column(df: pd.DataFrame, candidates):
    lower_map = {str(c).strip().lower(): c for c in df.columns}
    for c in candidates:
        if c.lower() in lower_map:
            return lower_map[c.lower()]
    return df.columns[0]


def detect_t4_total_column(df: pd.DataFrame):
    """
    优先寻找 Total/Employment/Employed 等列。
    不能确定时，选择第一列数值占比高且位于前 5 个字段的列。
    """
    cols = list(df.columns)

    preferred = []
    for c in cols:
        cl = str(c).lower()
        if "total" in cl and (
            "transport" not in cl
            and "mode" not in cl
            and "sex" not in cl
            and "industry" not in cl
        ):
            preferred.append(c)

    for c in preferred:
        vals = numeric_series(df[c])
        if vals.notna().mean() > 0.8:
            return c

    for token in ["employed residents", "employed", "employment"]:
        for c in cols:
            if token in str(c).lower():
                vals = numeric_series(df[c])
                if vals.notna().mean() > 0.8:
                    return c

    for c in cols[:8]:
        vals = numeric_series(df[c])
        if vals.notna().mean() > 0.85:
            return c

    raise ValueError(
        "无法从 Workplace T4 自动识别就业总量列。"
        f"实际字段：{cols}"
    )


def parse_census_pa_rows(df: pd.DataFrame, label_col: str):
    """
    支持两种真实导出形态：
        (A) 裸 PA 名          -> 'Ang Mo Kio'            (Census T4 实际形态)
        (B) 带后缀            -> 'Ang Mo Kio - Total'
    以及全国合计行 'Total'。

    注意：Census 2020 Workplace T4 使用的是裸 PA 名，
    早期版本只匹配 (B)，会导致 pa_records 为空并使脚本崩溃。
    """
    pa_records = []
    total_row = None

    pattern = re.compile(r"^(.+?)\s*-\s*Total$", re.I)

    for _, row in df.iterrows():
        label = norm_text(row[label_col])
        if not label:
            continue

        if label.upper() == "TOTAL":
            total_row = row
            continue

        m = pattern.match(label)
        if m:
            pa = norm_text(m.group(1))
        else:
            # 裸 PA 名形态（T4 实际）
            pa = label

        if pa:
            pa_records.append((pa, row))

    return total_row, pa_records


def build_workplace_control(t4_path: Path, output_path: Path):
    df = pd.read_csv(t4_path, encoding="utf-8-sig", low_memory=False)

    label_col = detect_first_column(
        df,
        ["Planning Area of Workplace", "Planning Area", "Workplace"],
    )
    total_col = detect_t4_total_column(df)

    total_row, pa_records = parse_census_pa_rows(df, label_col)

    records = []
    for pa_name, row in pa_records:
        value = numeric_series(pd.Series([row[total_col]])).iloc[0]
        if pd.isna(value):
            continue

        records.append({
            "planning_area_raw": pa_name,
            "planning_area_norm": norm_name(pa_name),
            "workplace_employment": float(value),
            "is_special_destination": norm_name(pa_name) in SPECIAL_DESTINATIONS,
        })

    control = pd.DataFrame(records)

    # 合并同名重复行，防止异常导出重复。
    if not control.empty:
        control = (
            control.groupby(
                ["planning_area_norm", "is_special_destination"],
                as_index=False,
                dropna=False,
            )["workplace_employment"]
            .sum()
        )
        control["planning_area"] = control["planning_area_norm"]

    if total_row is not None:
        nation_total = numeric_series(
            pd.Series([total_row[total_col]])
        ).iloc[0]
    else:
        nation_total = np.nan

    control["national_total_reference"] = nation_total
    control["control_source_column"] = str(total_col)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    control.sort_values(
        ["is_special_destination", "planning_area_norm"]
    ).to_csv(output_path, index=False, encoding="utf-8-sig")

    return control, df, label_col, total_col


def load_zone_dictionary(path: Path):
    z = pd.read_csv(path, encoding="utf-8-sig", low_memory=False)
    required = {
        "zone_id",
        "subzone_code",
        "subzone_name",
        "planning_area",
        "planning_area_code",
        "planning_region",
        "planning_region_code",
    }
    missing = required - set(z.columns)
    if missing:
        raise ValueError(f"zone_dictionary 缺少字段: {sorted(missing)}")
    z["planning_area_norm"] = z["planning_area"].map(norm_name)
    return z


def load_postal_bridge(project_root: Path):
    bridge = project_root / "reports/od_audit/_postal_subzone_bridge.csv"
    if not bridge.exists():
        return None
    b = pd.read_csv(bridge, encoding="utf-8-sig", low_memory=False)
    rename = {}
    for c in b.columns:
        cl = str(c).lower()
        if "postal" in cl:
            rename[c] = "postal"
        elif "subzone_c" in cl:
            rename[c] = "subzone_code"
    b = b.rename(columns=rename)
    if "postal" not in b.columns or "subzone_code" not in b.columns:
        return None
    b["postal"] = (
        pd.to_numeric(b["postal"], errors="coerce")
        .astype("Int64")
        .astype(str)
        .replace("<NA>", "")
        .str.zfill(6)
    )
    b["subzone_code"] = b["subzone_code"].map(norm_text)
    return b[["postal", "subzone_code"]].drop_duplicates()


def load_acra(project_root: Path, postal_bridge: pd.DataFrame | None):
    acra_dir = project_root / ACRA_DIR
    files = sorted(acra_dir.glob("*.csv"))
    if not files:
        raise FileNotFoundError(f"ACRA 目录没有 CSV: {acra_dir}")

    required_cols = {
        "uen",
        "entity_name",
        "entity_type_description",
        "entity_status_description",
        "block",
        "street_name",
        "building_name",
        "postal_code",
        "primary_ssic_code",
        "primary_ssic_description",
        "secondary_ssic_code",
        "secondary_ssic_description",
        "no_of_officers",
    }

    frames = []
    for f in files:
        df = pd.read_csv(
            f,
            encoding="utf-8-sig",
            low_memory=False,
            usecols=lambda c: c in required_cols,
        )
        frames.append(df)

    acra = pd.concat(frames, ignore_index=True)

    for c in acra.columns:
        acra[c] = acra[c].map(norm_text)

    acra["postal6"] = (
        pd.to_numeric(acra["postal_code"], errors="coerce")
        .astype("Int64")
        .astype(str)
        .replace("<NA>", "")
        .str.zfill(6)
    )

    status_norm = acra["entity_status_description"].map(norm_name)
    acra["is_active_status"] = ~status_norm.apply(
        lambda s: any(token in s for token in INACTIVE_STATUS_HINTS)
    )

    # Activity size proxy:
    # Use officers only as a weak capped feature, never as employment count.
    officers = pd.to_numeric(
        acra["no_of_officers"].replace("", np.nan),
        errors="coerce",
    ).fillna(0.0)
    acra["officer_proxy"] = np.clip(np.log1p(officers), 0.0, 3.5) + 1.0

    # SSIC / entity type feature.
    primary_ssic = acra.get("primary_ssic_code", pd.Series("", index=acra.index))
    primary_ssic = primary_ssic.astype(str).str.extract(r"(\d{2,5})", expand=False).fillna("")
    acra["ssic2"] = primary_ssic.str[:2]

    entity_type = acra["entity_type_description"].map(norm_name)
    acra["entity_weight"] = np.where(
        entity_type.str.contains("LOCAL COMPANY|PRIVATE|PUBLIC", regex=True),
        1.2,
        np.where(
            entity_type.str.contains("SOLE|PARTNERSHIP", regex=True),
            0.9,
            0.8,
        ),
    )

    acra["base_activity_weight"] = (
        acra["officer_proxy"]
        * acra["entity_weight"]
        * acra["is_active_status"].astype(float)
    )

    if postal_bridge is not None:
        acra = acra.merge(
            postal_bridge,
            left_on="postal6",
            right_on="postal",
            how="left",
        )
        acra["subzone_code"] = acra["subzone_code"].fillna("")
    else:
        acra["subzone_code"] = ""

    return acra


def build_acra_subzone_activity(
    acra: pd.DataFrame,
    zones: pd.DataFrame,
    out_path: Path,
):
    """
    将 ACRA 的空间 + 行业活动强度聚合到 Subzone。
    """
    zlookup = zones[
        ["subzone_code", "planning_area", "planning_area_norm", "zone_id"]
    ].drop_duplicates()

    a = acra.merge(
        zlookup,
        on="subzone_code",
        how="left",
    )

    a["primary_ssic_desc_norm"] = (
        a["primary_ssic_description"].map(norm_name)
    )

    # 用 SSIC 描述做透明、可解释的行业修正。
    # 不把 SSIC 映射成真实员工数，只影响空间权重。
    desc = a["primary_ssic_desc_norm"]
    a["ssic_activity_factor"] = 1.0

    masks = [
        (desc.str.contains("MANUFACTUR|CONSTRUCTION|INDUSTR", regex=True)),
        (desc.str.contains("FINANC|BANK|INSURANCE", regex=True)),
        (desc.str.contains("PROFESSIONAL|INFORMATION|COMMUNICATION|TECHNOLOGY", regex=True)),
        (desc.str.contains("WHOLESALE|RETAIL|RESTAURANT|FOOD|ACCOMMODATION", regex=True)),
        (desc.str.contains("EDUCATION|SCHOOL|UNIVERSITY", regex=True)),
        (desc.str.contains("HEALTH|MEDICAL|HOSPITAL|CLINIC", regex=True)),
        (desc.str.contains("TRANSPORT|LOGISTICS|WAREHOUSE", regex=True)),
    ]
    factors = [1.15, 1.25, 1.20, 1.05, 1.15, 1.20, 1.10]

    for mask, factor in zip(masks, factors):
        a.loc[mask, "ssic_activity_factor"] = factor

    a["enterprise_activity_weight"] = (
        a["base_activity_weight"]
        * a["ssic_activity_factor"]
    )

    grouped = (
        a[a["subzone_code"].astype(str).str.len() > 0]
        .groupby(
            [
                "zone_id",
                "subzone_code",
                "planning_area",
                "planning_area_norm",
            ],
            as_index=False,
        )
        .agg(
            acra_enterprise_count=("uen", "nunique"),
            acra_activity_weight=("enterprise_activity_weight", "sum"),
        )
    )

    out_path.parent.mkdir(parents=True, exist_ok=True)
    grouped.to_csv(out_path, index=False, encoding="utf-8-sig")
    return grouped, a


def build_landuse_weights(
    landuse_path: Path,
    zones: pd.DataFrame,
    out_path: Path,
):
    print("[LandUse] reading...")
    gdf = gpd.read_file(landuse_path, columns=["LU_DESC", "geometry"])

    if gdf.crs is None:
        gdf = gdf.set_crs("EPSG:4326")

    gdf = gdf.to_crs("EPSG:3414")
    gdf["area_m2"] = gdf.geometry.area
    gdf["lu_desc_norm"] = gdf["LU_DESC"].fillna("").map(norm_name)

    gdf["lu_weight"] = gdf["lu_desc_norm"].map(
        lambda x: LANDUSE_WEIGHT.get(x, 0.2)
    )

    gdf["weighted_area"] = gdf["area_m2"] * gdf["lu_weight"]

    # Use zone polygons only.
    zone_geo = gpd.read_file(
        Path(zones.attrs["subzone_boundary_path"]),
    )
    if zone_geo.crs is None:
        zone_geo = zone_geo.set_crs("EPSG:4326")
    zone_geo = zone_geo.to_crs("EPSG:3414")

    zone_geo = zone_geo[
        ["SUBZONE_C", "PLN_AREA_N", "geometry"]
    ].copy()
    zone_geo["subzone_code"] = zone_geo["SUBZONE_C"].map(norm_text)
    zone_geo["planning_area_norm"] = zone_geo["PLN_AREA_N"].map(norm_name)

    # Spatial intersection; process only weighted land-use polygons.
    lu_cols = [
        "lu_desc_norm",
        "area_m2",
        "weighted_area",
        "lu_weight",
        "geometry",
    ]
    joined = gpd.sjoin(
        gdf[lu_cols],
        zone_geo[["subzone_code", "planning_area_norm", "geometry"]],
        predicate="intersects",
        how="inner",
    )

    # This is an area-weight approximation.
    # A polygon may overlap more than one zone; proportionality is based on
    # overlap geometry where possible.
    try:
        inter = gpd.overlay(
            gdf[lu_cols],
            zone_geo[["subzone_code", "planning_area_norm", "geometry"]],
            how="intersection",
        )
        inter["intersection_area"] = inter.geometry.area
        # 关键：必须把 lu_weight 带进 overlay，否则 LU_DESC 权重被丢弃，
        # weighted_intersection 会退化为裸面积。
        inter["weighted_intersection"] = (
            inter["intersection_area"] * inter["lu_weight"].fillna(0.2)
        )
    except Exception:
        inter = joined.copy()
        inter["intersection_area"] = inter.geometry.area
        inter["weighted_intersection"] = inter["weighted_area"]

    lu = (
        inter.groupby(
            ["subzone_code", "planning_area_norm"],
            as_index=False,
        )
        .agg(
            landuse_area_m2=("intersection_area", "sum"),
            landuse_activity_weight=("weighted_intersection", "sum"),
        )
    )

    out_path.parent.mkdir(parents=True, exist_ok=True)
    lu.to_csv(out_path, index=False, encoding="utf-8-sig")
    return lu


def build_attraction(
    zones,
    controls,
    acra_activity,
    landuse,
    output_dir,
):
    # physical workplace PAs
    physical_controls = controls[
        ~controls["is_special_destination"]
    ].copy()

    # normalize control names
    physical_controls["planning_area_norm"] = physical_controls[
        "planning_area_norm"
    ].map(norm_name)

    z = zones.copy()

    # Important: only physical Workplace PA controls are distributed.
    z = z.merge(
        physical_controls[
            ["planning_area_norm", "workplace_employment"]
        ],
        on="planning_area_norm",
        how="left",
    )

    z = z.merge(
        acra_activity[
            [
                "subzone_code",
                "acra_enterprise_count",
                "acra_activity_weight",
            ]
        ],
        on="subzone_code",
        how="left",
    )

    z = z.merge(
        landuse[
            [
                "subzone_code",
                "landuse_area_m2",
                "landuse_activity_weight",
            ]
        ],
        on="subzone_code",
        how="left",
    )

    for c in [
        "acra_enterprise_count",
        "acra_activity_weight",
        "landuse_area_m2",
        "landuse_activity_weight",
    ]:
        z[c] = pd.to_numeric(z[c], errors="coerce").fillna(0.0)

    # Blend two independent spatial proxies.
    #
    # ACRA captures "where active business entities are".
    # LandUse captures "where employment/activity capacity can occur".
    #
    # We standardize within PA, then multiply.
    def minmax_or_uniform(s):
        s = s.astype(float)
        if s.max() <= 0:
            return pd.Series(1.0, index=s.index)
        lo, hi = s.min(), s.max()
        if hi <= lo:
            return pd.Series(1.0, index=s.index)
        return (s - lo) / (hi - lo) + 0.05

    z["acra_norm"] = (
        z.groupby("planning_area_norm")["acra_activity_weight"]
        .transform(minmax_or_uniform)
    )
    z["landuse_norm"] = (
        z.groupby("planning_area_norm")["landuse_activity_weight"]
        .transform(minmax_or_uniform)
    )

    # ACRA is the stronger "observed activity" signal;
    # LandUse is capacity/context.
    z["activity_weight_raw"] = (
        0.65 * z["acra_norm"]
        + 0.35 * z["landuse_norm"]
    )

    # If a PA has no matched ACRA at all, landuse proxy still distributes jobs.
    no_acra = z.groupby("planning_area_norm")["acra_activity_weight"].transform(
        "sum"
    ) <= 0
    z.loc[no_acra, "activity_weight_raw"] = z.loc[no_acra, "landuse_norm"]

    z["attraction_weight_sum_pa"] = z.groupby(
        "planning_area_norm"
    )["activity_weight_raw"].transform("sum")

    z["attraction_share_within_pa"] = np.where(
        z["attraction_weight_sum_pa"] > 0,
        z["activity_weight_raw"] / z["attraction_weight_sum_pa"],
        0.0,
    )

    z["workplace_employment"] = z["workplace_employment"].fillna(0.0)

    z["workplace_attraction"] = (
        z["workplace_employment"]
        * z["attraction_share_within_pa"]
    )

    # Special/undefined destination controls are kept separately.
    special = controls[
        controls["is_special_destination"]
    ].copy()

    # validation by physical workplace PA
    val = (
        z.groupby("planning_area_norm", as_index=False)
        .agg(
            census_control=("workplace_employment", "first"),
            attraction_sum=("workplace_attraction", "sum"),
            zones=("zone_id", "count"),
        )
    )
    val["difference"] = (
        val["attraction_sum"] - val["census_control"]
    )
    val["relative_error"] = np.where(
        val["census_control"] > 0,
        val["difference"].abs() / val["census_control"],
        0,
    )

    max_abs_diff = float(val["difference"].abs().max()) if len(val) else 0.0
    max_rel_error = float(val["relative_error"].max()) if len(val) else 0.0

    result = z[
        [
            "zone_id",
            "subzone_code",
            "subzone_name",
            "planning_area_code",
            "planning_area",
            "planning_area_norm",
            "planning_region_code",
            "planning_region",
            "workplace_employment",
            "acra_enterprise_count",
            "acra_activity_weight",
            "landuse_area_m2",
            "landuse_activity_weight",
            "acra_norm",
            "landuse_norm",
            "activity_weight_raw",
            "attraction_share_within_pa",
            "workplace_attraction",
        ]
    ].copy()

    result["workplace_attraction"] = result[
        "workplace_attraction"
    ].round(6)

    return result, val, special, {
        "max_abs_pa_conservation_error": max_abs_diff,
        "max_relative_pa_conservation_error": max_rel_error,
        "physical_workplace_pa_count": int(len(physical_controls)),
        "special_destination_count": int(len(special)),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--project-root",
        type=Path,
        default=DEFAULT_PROJECT_ROOT,
    )
    args = parser.parse_args()

    project_root = args.project_root
    data_root = project_root / DATA_DIR_NAME
    output_dir = project_root / "reports" / "od_attraction"
    output_dir.mkdir(parents=True, exist_ok=True)

    zone_path = project_root / ZONE_FILE
    production_path = project_root / PRODUCTION_FILE
    t4_path = project_root / T4_FILE
    landuse_path = project_root / LANDUSE_FILE

    # 1. Upstream checks
    for p in [zone_path, production_path, t4_path, landuse_path]:
        if not p.exists():
            raise FileNotFoundError(f"必要文件不存在: {p}")

    # production is an explicit upstream dependency check
    production = pd.read_csv(
        production_path,
        encoding="utf-8-sig",
        low_memory=False,
    )
    if "zone_id" not in production.columns:
        raise ValueError("production.csv 缺少 zone_id。")

    zones = load_zone_dictionary(zone_path)

    # Preserve actual polygon path for build_landuse_weights.
    zones.attrs["subzone_boundary_path"] = str(
        data_root
        / "01_Boundary_TAZ/MasterPlan2019SubzoneBoundaryNoSeaGEOJSON.geojson"
    )

    # 2. Census workplace controls
    print("[1/5] Workplace Census T4")
    controls, t4_df, label_col, total_col = build_workplace_control(
        t4_path,
        output_dir / "pa_workplace_control.csv",
    )

    # 3. ACRA
    print("[2/5] ACRA")
    bridge = load_postal_bridge(project_root)
    acra = load_acra(project_root, bridge)

    acra_activity, acra_enriched = build_acra_subzone_activity(
        acra,
        zones,
        output_dir / "acra_subzone_activity.csv",
    )

    # 4. Land use
    print("[3/5] LandUse")
    landuse = build_landuse_weights(
        landuse_path,
        zones,
        output_dir / "subzone_landuse_weights.csv",
    )

    # 5. Attraction
    print("[4/5] Build attraction")
    attraction, validation, special, metrics = build_attraction(
        zones,
        controls,
        acra_activity,
        landuse,
        output_dir,
    )

    attraction.to_csv(
        output_dir / "attraction.csv",
        index=False,
        encoding="utf-8-sig",
    )

    # Save PA validation
    validation.to_csv(
        output_dir / "attraction_pa_validation.csv",
        index=False,
        encoding="utf-8-sig",
    )

    # Build summary
    acra_total = len(acra)
    acra_located = int(
        acra["subzone_code"].astype(str).str.len().gt(0).sum()
    )
    acra_valid_postal = int(
        acra["postal6"].astype(str).str.match(r"^\d{6}$").sum()
    )

    control_total = float(
        controls.loc[
            ~controls["is_special_destination"],
            "workplace_employment",
        ].sum()
    )
    attraction_total = float(attraction["workplace_attraction"].sum())

    summary = {
        "status": (
            "PASS"
            if metrics["max_relative_pa_conservation_error"] <= 1e-8
            else "WARN"
        ),
        "generated_at": pd.Timestamp.now().isoformat(),
        "project_root": str(project_root),
        "data_root": str(data_root),
        "upstream": {
            "zone_rows": int(len(zones)),
            "production_rows": int(len(production)),
            "t4_rows": int(len(t4_df)),
            "t4_label_column": str(label_col),
            "t4_total_column": str(total_col),
        },
        "workplace_control": {
            "physical_pa_count": int(
                (~controls["is_special_destination"]).sum()
            ),
            "special_destination_count": int(
                controls["is_special_destination"].sum()
            ),
            "physical_control_total": control_total,
            "subzone_attraction_total": attraction_total,
            "total_difference": attraction_total - control_total,
        },
        "acra": {
            "total_records": acra_total,
            "valid_postal_records": acra_valid_postal,
            "subzone_located_records": acra_located,
            "valid_postal_match_rate": (
                round(acra_located / acra_valid_postal, 6)
                if acra_valid_postal else None
            ),
        },
        "pa_conservation": metrics,
        "zero_attraction_zones": int(
            (attraction["workplace_attraction"] <= 1e-12).sum()
        ),
        "notes": [
            "Census Workplace employment is the PA-level control total.",
            "ACRA no_of_officers is not interpreted as employee count.",
            "ACRA contributes enterprise spatial/activity weight only.",
            "LandUse contributes capacity/activity context.",
            "Physical Workplace PA totals are exactly conserved after normalization.",
            "Special workplace categories are retained in pa_workplace_control.csv and are not assigned to physical Subzones.",
        ],
    }

    with open(
        output_dir / "attraction_validation.json",
        "w",
        encoding="utf-8",
    ) as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    print("\n" + "=" * 72)
    print("Step 3 | Workplace Attraction")
    print("=" * 72)
    print(f"Zones                  : {len(attraction)}")
    print(f"Physical PA controls   : {metrics['physical_workplace_pa_count']}")
    print(f"Special destinations   : {metrics['special_destination_count']}")
    print(f"ACRA records           : {acra_total:,}")
    print(f"ACRA valid postal      : {acra_valid_postal:,}")
    print(f"ACRA located Subzones  : {acra_located:,}")
    print(
        f"ACRA postal match rate : "
        f"{summary['acra']['valid_postal_match_rate']}"
    )
    print(f"Census control total   : {control_total:,.3f}")
    print(f"Attraction total       : {attraction_total:,.3f}")
    print(
        "Max PA conservation    : "
        f"{metrics['max_abs_pa_conservation_error']:.12g}"
    )
    print(
        "Max relative error     : "
        f"{metrics['max_relative_pa_conservation_error']:.12g}"
    )
    print(f"Status                 : {summary['status']}")
    print(f"Output                 : {output_dir}")
    print("=" * 72)

    if summary["status"] == "WARN":
        print(
            "WARNING: PA conservation 未达到机器精度。"
            "请检查 attraction_pa_validation.csv。"
        )


if __name__ == "__main__":
    main()
