#!/usr/bin/env python3
# -*- coding: utf-8 -*-

r"""
Singapore OD -> MATSim
Step 1: Build unified spatial zone dictionary

输入：
    D:\Luan\2026-05\2_Singapore\Singapore_OD_MATSim_FinalData\01_Boundary_TAZ\

输出：
    D:\Luan\2026-05\2_Singapore\reports\od_zone\
        zone_dictionary.csv
        planning_area_dictionary.csv
        zone_dictionary_validation.json

原则：
    1. 最终 OD 计算单元固定为 332 个 Subzone。
    2. Planning Area / Planning Region 作为统计控制层，不作为最终 OD 单元。
    3. 所有后续模型只通过 zone_id / subzone_code 连接。
    4. 面积、质心等几何指标统一在 SVY21 / EPSG:3414 下计算。
    5. 不在本步骤擅自处理 55/44/30 PA 的统计口径差异。
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import geopandas as gpd
import pandas as pd


DEFAULT_PROJECT_ROOT = Path(r"D:\Luan\2026-05\2_Singapore")
DEFAULT_DATA_ROOT_NAME = "Singapore_OD_MATSim_FinalData"

SUBZONE_FILE = Path(
    "01_Boundary_TAZ/MasterPlan2019SubzoneBoundaryNoSeaGEOJSON.geojson"
)
PA_FILE = Path(
    "01_Boundary_TAZ/MasterPlan2019PlanningAreaBoundaryNoSea.geojson"
)

EXPECTED_SUBZONES = 332
EXPECTED_PA = 55
EXPECTED_REGIONS = 5
TARGET_CRS = "EPSG:3414"
SOURCE_CRS = "EPSG:4326"


def norm_text(value) -> str:
    if value is None:
        return ""
    s = str(value).replace("\xa0", " ").strip()
    s = re.sub(r"\s+", " ", s)
    return s


def norm_name(value) -> str:
    """
    行政区名称统一：
    - 大小写统一到 upper
    - 多余空格统一
    """
    return norm_text(value).upper()


def assert_columns(gdf: gpd.GeoDataFrame, required: set[str], name: str):
    missing = required - set(gdf.columns)
    if missing:
        raise ValueError(
            f"{name} 缺少字段: {sorted(missing)}\n"
            f"实际字段: {list(gdf.columns)}"
        )


def build_subzone_dictionary(subzone_path: Path, pa_path: Path, out_dir: Path):
    print(f"[1/5] 读取 Subzone: {subzone_path}")
    sub = gpd.read_file(subzone_path)

    print(f"[2/5] 读取 Planning Area: {pa_path}")
    pa = gpd.read_file(pa_path)

    assert_columns(
        sub,
        {"SUBZONE_C", "SUBZONE_N", "PLN_AREA_C", "PLN_AREA_N",
         "REGION_C", "REGION_N", "geometry"},
        "Subzone",
    )
    assert_columns(
        pa,
        {"PLN_AREA_C", "PLN_AREA_N", "REGION_C", "REGION_N", "geometry"},
        "Planning Area",
    )

    # --- 基础数量检查 ---
    checks = {
        "subzone_rows": int(len(sub)),
        "planning_area_rows": int(len(pa)),
        "subzone_expected": EXPECTED_SUBZONES,
        "planning_area_expected": EXPECTED_PA,
    }

    if len(sub) != EXPECTED_SUBZONES:
        raise ValueError(
            f"Subzone 数量异常：{len(sub)} != {EXPECTED_SUBZONES}"
        )
    if len(pa) != EXPECTED_PA:
        raise ValueError(
            f"Planning Area 数量异常：{len(pa)} != {EXPECTED_PA}"
        )

    # --- CRS ---
    if sub.crs is None:
        sub = sub.set_crs(SOURCE_CRS)
    if pa.crs is None:
        pa = pa.set_crs(SOURCE_CRS)

    checks["subzone_source_crs"] = str(sub.crs)
    checks["planning_area_source_crs"] = str(pa.crs)

    # 强制统一到 SVY21，用于面积和质心
    sub_metric = sub.to_crs(TARGET_CRS)
    pa_metric = pa.to_crs(TARGET_CRS)

    # --- 唯一键 ---
    sub["SUBZONE_C"] = sub["SUBZONE_C"].map(norm_text)
    sub["SUBZONE_N"] = sub["SUBZONE_N"].map(norm_text)
    sub["PLN_AREA_C"] = sub["PLN_AREA_C"].map(norm_text)
    sub["PLN_AREA_N"] = sub["PLN_AREA_N"].map(norm_text)
    sub["REGION_C"] = sub["REGION_C"].map(norm_text)
    sub["REGION_N"] = sub["REGION_N"].map(norm_text)

    duplicate_codes = (
        sub.loc[sub["SUBZONE_C"].duplicated(keep=False), "SUBZONE_C"]
        .drop_duplicates()
        .tolist()
    )
    if duplicate_codes:
        raise ValueError(
            f"发现重复 SUBZONE_C：{duplicate_codes[:20]}"
        )

    # PA 编码唯一
    pa["PLN_AREA_C"] = pa["PLN_AREA_C"].map(norm_text)
    pa["PLN_AREA_N"] = pa["PLN_AREA_N"].map(norm_text)
    pa["REGION_C"] = pa["REGION_C"].map(norm_text)
    pa["REGION_N"] = pa["REGION_N"].map(norm_text)

    if pa["PLN_AREA_C"].nunique() != len(pa):
        raise ValueError("Planning Area PLN_AREA_C 非唯一。")

    # --- PA / Region consistency ---
    pa_lookup = (
        pa[["PLN_AREA_C", "PLN_AREA_N", "REGION_C", "REGION_N"]]
        .drop_duplicates()
        .copy()
    )
    pa_lookup["pln_area_name_norm"] = pa_lookup["PLN_AREA_N"].map(norm_name)
    pa_lookup["region_name_norm"] = pa_lookup["REGION_N"].map(norm_name)

    sub["pln_area_name_norm"] = sub["PLN_AREA_N"].map(norm_name)
    sub["region_name_norm"] = sub["REGION_N"].map(norm_name)

    sub_from_pa = sub[
        ["PLN_AREA_C", "PLN_AREA_N", "REGION_C", "REGION_N",
         "pln_area_name_norm", "region_name_norm"]
    ].drop_duplicates()

    # 每个 Subzone 的 PA 编码必须唯一对应
    pa_count_by_subzone = sub.groupby("SUBZONE_C")["PLN_AREA_C"].nunique()
    inconsistent = pa_count_by_subzone[pa_count_by_subzone != 1]
    if not inconsistent.empty:
        raise ValueError(
            f"Subzone → Planning Area 映射不唯一：{inconsistent.index.tolist()[:20]}"
        )

    # --- 几何指标 ---
    sub_metric["area_m2"] = sub_metric.geometry.area
    centroids = sub_metric.geometry.centroid

    # 质心转换到 WGS84，仅用于可视化/外部工具
    centroids_wgs = gpd.GeoSeries(
        centroids, crs=TARGET_CRS
    ).to_crs(SOURCE_CRS)

    # --- zone_dictionary ---
    zone = pd.DataFrame({
        "zone_id": range(1, len(sub) + 1),
        "zone_type": "SUBZONE",
        "subzone_code": sub["SUBZONE_C"].tolist(),
        "subzone_name": sub["SUBZONE_N"].tolist(),
        "planning_area_code": sub["PLN_AREA_C"].tolist(),
        "planning_area": sub["PLN_AREA_N"].tolist(),
        "planning_region_code": sub["REGION_C"].tolist(),
        "planning_region": sub["REGION_N"].tolist(),
        "centroid_x_svy21_m": centroids.x.round(3),
        "centroid_y_svy21_m": centroids.y.round(3),
        "centroid_lon": centroids_wgs.x.round(8),
        "centroid_lat": centroids_wgs.y.round(8),
        "area_m2": sub_metric["area_m2"].round(3),
    })

    # 再按 subzone_code 排序，保证稳定输出。
    # zone_id 是模型内部整数键；subzone_code 是外部空间主键。
    zone = zone.sort_values("subzone_code").reset_index(drop=True)
    zone["zone_id"] = range(1, len(zone) + 1)

    # zone_id / subzone_code 双向唯一
    if zone["zone_id"].nunique() != EXPECTED_SUBZONES:
        raise ValueError("zone_id 非唯一。")
    if zone["subzone_code"].nunique() != EXPECTED_SUBZONES:
        raise ValueError("subzone_code 非唯一。")

    # --- planning_area_dictionary ---
    pa_out = pa_metric.copy()
    pa_centroid = pa_out.geometry.centroid
    pa_centroid_wgs = gpd.GeoSeries(
        pa_centroid, crs=TARGET_CRS
    ).to_crs(SOURCE_CRS)

    pa_dict = pd.DataFrame({
        "planning_area_code": pa["PLN_AREA_C"].tolist(),
        "planning_area": pa["PLN_AREA_N"].tolist(),
        "planning_area_norm": pa["PLN_AREA_N"].map(norm_name).tolist(),
        "planning_region_code": pa["REGION_C"].tolist(),
        "planning_region": pa["REGION_N"].tolist(),
        "planning_region_norm": pa["REGION_N"].map(norm_name).tolist(),
        "centroid_x_svy21_m": pa_centroid.x.round(3),
        "centroid_y_svy21_m": pa_centroid.y.round(3),
        "centroid_lon": pa_centroid_wgs.x.round(8),
        "centroid_lat": pa_centroid_wgs.y.round(8),
        "area_m2": pa_out.geometry.area.round(3),
    }).sort_values("planning_area_code").reset_index(drop=True)

    if pa_dict["planning_area_code"].nunique() != EXPECTED_PA:
        raise ValueError("planning_area_dictionary 中 PA 编码非唯一。")

    # --- PA / Region 数量检查 ---
    checks["subzone_unique"] = int(zone["subzone_code"].nunique())
    checks["pa_unique_from_subzone"] = int(zone["planning_area_code"].nunique())
    checks["region_unique_from_subzone"] = int(zone["planning_region_code"].nunique())
    checks["pa_unique_from_boundary"] = int(pa_dict["planning_area_code"].nunique())

    checks["pa_boundary_vs_subzone_match"] = sorted(
        set(pa_dict["planning_area_code"]) -
        set(zone["planning_area_code"])
    ) == []

    checks["subzone_pa_missing_from_boundary"] = sorted(
        set(zone["planning_area_code"]) -
        set(pa_dict["planning_area_code"])
    )

    if checks["subzone_unique"] != EXPECTED_SUBZONES:
        raise ValueError("Subzone 唯一编码数量异常。")
    if checks["pa_unique_from_subzone"] != EXPECTED_PA:
        raise ValueError("Subzone 映射出的 PA 数量不是 55。")
    if checks["region_unique_from_subzone"] != EXPECTED_REGIONS:
        raise ValueError("Subzone 映射出的 Region 数量不是 5。")
    if not checks["pa_boundary_vs_subzone_match"] or checks["subzone_pa_missing_from_boundary"]:
        raise ValueError(
            "Subzone 与 Planning Area 边界的 PA 集合不一致："
            f"{checks['subzone_pa_missing_from_boundary']}"
        )

    # 稳定性元数据
    checks["target_crs"] = TARGET_CRS
    checks["area_unit"] = "m2"
    checks["centroid_metric_crs"] = TARGET_CRS
    checks["centroid_display_crs"] = SOURCE_CRS
    checks["zone_id_rule"] = "按 SUBZONE_C 排序后从 1 开始编号"
    checks["status"] = "PASS"

    out_dir.mkdir(parents=True, exist_ok=True)

    zone_path = out_dir / "zone_dictionary.csv"
    pa_path_out = out_dir / "planning_area_dictionary.csv"
    report_path = out_dir / "zone_dictionary_validation.json"

    zone.to_csv(zone_path, index=False, encoding="utf-8-sig")
    pa_dict.to_csv(pa_path_out, index=False, encoding="utf-8-sig")

    with report_path.open("w", encoding="utf-8") as f:
        json.dump(checks, f, ensure_ascii=False, indent=2)

    print("\n" + "=" * 70)
    print("Step 1 | Unified Zone Dictionary")
    print("=" * 70)
    print(f"Subzone : {len(zone)}")
    print(f"PA      : {len(pa_dict)}")
    print(f"Region  : {zone['planning_region_code'].nunique()}")
    print(f"CRS     : {TARGET_CRS}")
    print(f"Output  : {zone_path}")
    print(f"Output  : {pa_path_out}")
    print(f"Report  : {report_path}")
    print("Status  : PASS")
    print("=" * 70)

    return zone, pa_dict, checks


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--project-root",
        type=Path,
        default=DEFAULT_PROJECT_ROOT,
    )
    parser.add_argument(
        "--data-root",
        type=Path,
        default=None,
    )
    args = parser.parse_args()

    project_root = args.project_root
    data_root = args.data_root or (
        project_root / DEFAULT_DATA_ROOT_NAME
    )

    subzone_path = data_root / SUBZONE_FILE
    pa_path = data_root / PA_FILE
    out_dir = project_root / "reports" / "od_zone"

    if not project_root.exists():
        raise FileNotFoundError(f"项目根目录不存在：{project_root}")
    if not data_root.exists():
        raise FileNotFoundError(f"最终数据目录不存在：{data_root}")
    if not subzone_path.exists():
        raise FileNotFoundError(f"Subzone 文件不存在：{subzone_path}")
    if not pa_path.exists():
        raise FileNotFoundError(f"Planning Area 文件不存在：{pa_path}")

    build_subzone_dictionary(
        subzone_path=subzone_path,
        pa_path=pa_path,
        out_dir=out_dir,
    )


if __name__ == "__main__":
    main()
