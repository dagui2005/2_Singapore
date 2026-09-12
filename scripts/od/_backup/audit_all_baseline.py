#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Singapore OD -> MATSim
Step 0: Data Audit

说明：
1. 只做数据体检，不修改原始数据。
2. 默认项目根目录：
   D:\Luan\2026-05\2_Singapore
3. 最终数据目录：
   D:\Luan\2026-05\2_Singapore\Singapore_OD_MATSim_FinalData

运行：
    python audit_all.py

或：
    python audit_all.py --project-root "D:\Luan\2026-05\2_Singapore"

输出：
    reports/od_audit/
        audit_summary.json
        audit_zone.csv
        audit_census.csv
        audit_acra.csv
        audit_network.csv
        audit_trafficflow.csv
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

try:
    import pandas as pd
except ImportError:
    pd = None

try:
    import geopandas as gpd
except ImportError:
    gpd = None


DEFAULT_PROJECT_ROOT = Path(r"D:\Luan\2026-05\2_Singapore")
DEFAULT_DATA_DIR_NAME = "Singapore_OD_MATSim_FinalData"

CORE_FILES = {
    "subzone_boundary": Path(
        "01_Boundary_TAZ/MasterPlan2019SubzoneBoundaryNoSeaGEOJSON.geojson"
    ),
    "planning_area_boundary": Path(
        "01_Boundary_TAZ/MasterPlan2019PlanningAreaBoundaryNoSea.geojson"
    ),
    "residence_t1": Path(
        "02_Population_Residence/outputFile (2)__T1.csv"
    ),
    "workplace_t4": Path(
        "03_Workplace_Employment/outputFile (3)__T4.csv"
    ),
    "workplace_t11": Path(
        "03_Workplace_Employment/outputFile (3)__T11.csv"
    ),
    "residence_t15": Path(
        "06_Census_TravelBehavior/outputFile (4)__T15.csv"
    ),
    "residence_t16": Path(
        "06_Census_TravelBehavior/outputFile (4)__T16.csv"
    ),
    "traffic_mode_t7": Path(
        "06_Census_TravelBehavior/outputFile (5)__T7.csv"
    ),
    "traffic_flow": Path(
        "08_TrafficCount/TrafficFlow_Data.json"
    ),
    "traffic_flow_links": Path(
        "08_TrafficCount/TrafficFlow_Links.shp"
    ),
    "road_section": Path(
        "07_RoadNetwork/RoadSectionLine_Mar2026/RoadSectionLine.shp"
    ),
    "osm_lines": Path(
        "07_RoadNetwork/osm-lines.shp"
    ),
    "osm_lines_expanded": Path(
        "07_RoadNetwork/osm-lines_expanded.shp"
    ),
    "matsim_network": Path(
        "07_RoadNetwork/network.xml.gz"
    ),
    "acra_dir": Path("05_POI_Enterprise/ACRA"),
    "landuse": Path(
        "04_LandUse_Building/MasterPlan2019LandUselayer.geojson"
    ),
    "building": Path(
        "04_LandUse_Building/MasterPlan2019Buildinglayer.geojson"
    ),
    "dwelling_points": Path(
        "04_LandUse_Building/URANoofDwellingUnits.geojson"
    ),
    "poi": Path("05_POI_Enterprise/poi.csv"),
}

EXPECTED_ZONE_COUNTS = {
    "subzone_boundary": 332,
    "planning_area_boundary": 55,
}

SPECIAL_WORKPLACE_LABELS = {
    "Other Planning Areas or Outside Singapore",
    "No Fixed Location for Work",
    "Works from Home",
}

WEEKDAYS = {"Monday", "Tuesday", "Wednesday", "Thursday", "Friday"}


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def normalize_name(value: Any) -> str:
    if value is None:
        return ""
    s = str(value).replace("\xa0", " ").strip()
    s = re.sub(r"\s+", " ", s)
    return s


def clean_numeric(value: Any) -> float | None:
    if value is None:
        return None
    s = str(value).strip().replace(",", "")
    if s in {"", "-", "na", "NA", "null", "None"}:
        return None
    try:
        return float(s)
    except ValueError:
        return None


def load_csv(path: Path, **kwargs):
    if pd is None:
        raise RuntimeError(
            "缺少 pandas。请先安装 requirements.txt 中的依赖。"
        )
    return pd.read_csv(
        path,
        encoding="utf-8-sig",
        low_memory=False,
        **kwargs,
    )


def find_file(root: Path, relative: Path) -> Path | None:
    exact = root / relative
    if exact.exists():
        return exact

    # 处理可能存在的命名差异：递归寻找 basename
    candidates = list(root.glob(f"**/{relative.name}"))
    if len(candidates) == 1:
        return candidates[0]
    return None


def add_check(checks, area, item, status, detail):
    checks.append({
        "area": area,
        "item": item,
        "status": status,
        "detail": str(detail),
    })


def audit_files(data_root: Path, checks):
    for key, rel in CORE_FILES.items():
        path = find_file(data_root, rel)

        if path is None:
            # matsim network.xml.gz 是当前已知尚未生成项，单独标 WARN
            status = "WARN" if key == "matsim_network" else "FAIL"
            add_check(
                checks,
                "files",
                key,
                status,
                f"未找到: {rel}",
            )
        else:
            add_check(
                checks,
                "files",
                key,
                "PASS",
                str(path),
            )


def read_zone_layer(path: Path, checks, expected_count: int, name: str):
    if gpd is None:
        add_check(
            checks, "zone", name, "WARN",
            "geopandas 未安装，无法检查几何数量/CRS。"
        )
        return None

    try:
        gdf = gpd.read_file(path)
    except Exception as exc:
        add_check(checks, "zone", name, "FAIL", f"读取失败: {exc}")
        return None

    if len(gdf) == expected_count:
        status = "PASS"
    else:
        status = "WARN"

    add_check(
        checks, "zone", f"{name}_feature_count", status,
        f"实际 {len(gdf)}，期望 {expected_count}"
    )

    crs = gdf.crs
    add_check(
        checks, "zone", f"{name}_crs",
        "PASS" if crs is not None else "WARN",
        f"CRS={crs}"
    )

    return gdf


def audit_zones(data_root: Path, out_dir: Path, checks):
    rows = []

    sub_path = find_file(data_root, CORE_FILES["subzone_boundary"])
    pa_path = find_file(data_root, CORE_FILES["planning_area_boundary"])

    subzones = None
    pas = None

    if sub_path:
        subzones = read_zone_layer(
            sub_path, checks,
            EXPECTED_ZONE_COUNTS["subzone_boundary"],
            "subzone_boundary",
        )
        if subzones is not None:
            required = {"SUBZONE_C", "SUBZONE_N", "PLN_AREA_C", "PLN_AREA_N", "REGION_C"}
            missing = required - set(subzones.columns)
            add_check(
                checks, "zone", "subzone_required_fields",
                "PASS" if not missing else "FAIL",
                f"missing={sorted(missing)}"
            )

            unique_subzone = (
                subzones["SUBZONE_C"].dropna().astype(str).str.strip().nunique()
                if "SUBZONE_C" in subzones.columns else 0
            )
            add_check(
                checks, "zone", "subzone_code_unique",
                "PASS" if unique_subzone == len(subzones) else "FAIL",
                f"unique={unique_subzone}, rows={len(subzones)}"
            )

            pa_from_subzone = (
                subzones["PLN_AREA_C"].dropna().astype(str).str.strip().nunique()
                if "PLN_AREA_C" in subzones.columns else 0
            )
            region_from_subzone = (
                subzones["REGION_C"].dropna().astype(str).str.strip().nunique()
                if "REGION_C" in subzones.columns else 0
            )
            add_check(
                checks, "zone", "subzone_pa_count",
                "PASS" if pa_from_subzone == 55 else "WARN",
                f"{pa_from_subzone}"
            )
            add_check(
                checks, "zone", "subzone_region_count",
                "PASS" if region_from_subzone == 5 else "WARN",
                f"{region_from_subzone}"
            )

            for _, r in subzones.iterrows():
                rows.append({
                    "subzone_code": normalize_name(r.get("SUBZONE_C")),
                    "subzone_name": normalize_name(r.get("SUBZONE_N")),
                    "planning_area_code": normalize_name(r.get("PLN_AREA_C")),
                    "planning_area": normalize_name(r.get("PLN_AREA_N")),
                    "planning_region_code": normalize_name(r.get("REGION_C")),
                    "planning_region": normalize_name(r.get("REGION_N")),
                })

    if pa_path:
        pas = read_zone_layer(
            pa_path, checks,
            EXPECTED_ZONE_COUNTS["planning_area_boundary"],
            "planning_area_boundary",
        )
        if pas is not None:
            required = {"PLN_AREA_C", "PLN_AREA_N", "REGION_C", "REGION_N"}
            missing = required - set(pas.columns)
            add_check(
                checks, "zone", "planning_area_required_fields",
                "PASS" if not missing else "FAIL",
                f"missing={sorted(missing)}"
            )

            pa_codes = pas["PLN_AREA_C"].dropna().astype(str).str.strip()
            add_check(
                checks, "zone", "planning_area_code_unique",
                "PASS" if pa_codes.nunique() == len(pas) else "FAIL",
                f"unique={pa_codes.nunique()}, rows={len(pas)}"
            )

    if rows:
        pd.DataFrame(rows).to_csv(
            out_dir / "audit_zone.csv",
            index=False,
            encoding="utf-8-sig",
        )


def parse_census_first_key(df) -> tuple[str | None, list[str]]:
    if df is None or df.empty:
        return None, []
    key = str(df.columns[0])
    values = [
        normalize_name(v)
        for v in df[key].dropna().tolist()
        if normalize_name(v)
    ]
    return key, values


def audit_census(data_root: Path, out_dir: Path, checks):
    summary_rows = []

    # Residence Subzone T1
    residence_path = find_file(data_root, CORE_FILES["residence_t1"])
    residence_df = None
    if residence_path:
        try:
            residence_df = load_csv(residence_path)
            key, values = parse_census_first_key(residence_df)
            pa_rows = [v for v in values if v.endswith(" - Total")]
            subzone_rows = [v for v in values if v and not v.endswith(" - Total") and v != "Total"]

            add_check(
                checks, "census", "residence_t1_read",
                "PASS", f"rows={len(residence_df)}, key={key}"
            )
            add_check(
                checks, "census", "residence_t1_pa_count",
                "PASS" if len(pa_rows) == 55 else "WARN",
                f"{len(pa_rows)}"
            )
            add_check(
                checks, "census", "residence_t1_subzone_count",
                "PASS" if len(subzone_rows) == 332 else "WARN",
                f"{len(subzone_rows)}"
            )

            summary_rows.append({
                "dataset": "residence_t1",
                "rows": len(residence_df),
                "key": key,
                "pa_rows": len(pa_rows),
                "subzone_rows": len(subzone_rows),
            })
        except Exception as exc:
            add_check(checks, "census", "residence_t1_read", "FAIL", str(exc))

    # Workplace T4
    workplace_t4_path = find_file(data_root, CORE_FILES["workplace_t4"])
    work_t4 = None
    if workplace_t4_path:
        try:
            work_t4 = load_csv(workplace_t4_path)
            key, values = parse_census_first_key(work_t4)
            work_labels = set(values)

            special_found = sorted(SPECIAL_WORKPLACE_LABELS & work_labels)
            add_check(
                checks, "census", "workplace_t4_read",
                "PASS", f"rows={len(work_t4)}, key={key}"
            )
            add_check(
                checks, "census", "workplace_special_nodes",
                "PASS" if special_found else "WARN",
                f"found={special_found}"
            )

            summary_rows.append({
                "dataset": "workplace_t4",
                "rows": len(work_t4),
                "key": key,
                "special_nodes": ";".join(special_found),
            })
        except Exception as exc:
            add_check(checks, "census", "workplace_t4_read", "FAIL", str(exc))

    # Workplace T11 / Table 118
    t11_path = find_file(data_root, CORE_FILES["workplace_t11"])
    if t11_path:
        try:
            t11 = load_csv(t11_path)
            key = str(t11.columns[0])
            labels = [normalize_name(x) for x in t11[key].tolist()]
            add_check(
                checks, "census", "table118_read",
                "PASS", f"rows={len(t11)}, cols={len(t11.columns)}, key={key}"
            )

            mode_cols = [
                c for c in t11.columns
                if "Car or Taxi/Private Hire Car Only" in str(c)
            ]
            add_check(
                checks, "census", "table118_car_columns",
                "PASS" if mode_cols else "WARN",
                f"count={len(mode_cols)}"
            )

            for col in [
                "Total_Mode of Transport_Car or Taxi/Private Hire Car Only",
                "Total_Mode of Transport_Combinations of Rail (MRT/LRT) or Public Bus",
                "Total_Mode of Transport_Other Modes",
                "Total_Mode of Transport_No Transport Required",
            ]:
                if col in t11.columns:
                    values_num = pd.to_numeric(
                        t11[col].astype(str).str.replace(",", "", regex=False),
                        errors="coerce"
                    )
                    total = values_num.iloc[0] if len(values_num) else None
                    summary_rows.append({
                        "dataset": "table118",
                        "metric": col,
                        "total_row_value": total,
                    })
        except Exception as exc:
            add_check(checks, "census", "table118_read", "FAIL", str(exc))

    # Residence T15/T16
    for label, key in [
        ("residence_t15", "residence_t15"),
        ("residence_t16", "residence_t16"),
    ]:
        p = find_file(data_root, CORE_FILES[key])
        if not p:
            continue
        try:
            df = load_csv(p)
            add_check(
                checks, "census", f"{label}_read",
                "PASS", f"rows={len(df)}, cols={len(df.columns)}"
            )
            summary_rows.append({
                "dataset": label,
                "rows": len(df),
                "cols": len(df.columns),
            })
        except Exception as exc:
            add_check(checks, "census", f"{label}_read", "FAIL", str(exc))

    if summary_rows:
        pd.DataFrame(summary_rows).to_csv(
            out_dir / "audit_census.csv",
            index=False,
            encoding="utf-8-sig"
        )


def audit_acra(data_root: Path, out_dir: Path, checks):
    acra_dir = data_root / CORE_FILES["acra_dir"]

    if not acra_dir.exists():
        add_check(checks, "acra", "acra_directory", "FAIL", str(acra_dir))
        return

    files = sorted(acra_dir.glob("*.csv"))
    add_check(
        checks, "acra", "acra_shard_count",
        "PASS" if len(files) >= 10 else "WARN",
        f"{len(files)} CSV files"
    )

    required = {
        "uen", "entity_name", "entity_status_description",
        "block", "street_name", "building_name", "postal_code",
        "primary_ssic_code", "primary_ssic_description",
        "secondary_ssic_code", "secondary_ssic_description",
        "no_of_officers",
    }

    total_rows = 0
    stats = []

    for path in files:
        try:
            # 只读字段/逐文件统计，避免同时把 1M+ 行全部载入内存
            df = load_csv(path, usecols=lambda c: c in required)
            total_rows += len(df)

            missing_required = required - set(df.columns)
            numeric_officer = (
                pd.to_numeric(
                    df["no_of_officers"].astype(str).str.replace(",", "", regex=False),
                    errors="coerce"
                )
                if "no_of_officers" in df.columns else pd.Series(dtype=float)
            )

            address_cols = [
                c for c in ["block", "street_name", "building_name", "postal_code"]
                if c in df.columns
            ]
            address_complete = (
                df[address_cols].notna().any(axis=1).mean()
                if address_cols else 0.0
            )

            stats.append({
                "file": path.name,
                "rows": len(df),
                "missing_required": ";".join(sorted(missing_required)),
                "address_any_fill_rate": round(float(address_complete), 4),
                "officer_numeric_rate": round(float(numeric_officer.notna().mean()), 4),
            })

        except Exception as exc:
            add_check(
                checks, "acra", f"read_{path.name}",
                "FAIL", str(exc)
            )

    add_check(
        checks, "acra", "acra_total_rows",
        "PASS" if total_rows > 500_000 else "WARN",
        f"{total_rows:,}"
    )

    # 明确提醒：no_of_officers 不能直接当员工数
    add_check(
        checks, "acra", "no_of_officers_semantics",
        "PASS",
        "仅作为辅助企业特征；不得直接解释为员工人数。"
    )

    if stats:
        pd.DataFrame(stats).to_csv(
            out_dir / "audit_acra.csv",
            index=False,
            encoding="utf-8-sig"
        )


def audit_network(data_root: Path, out_dir: Path, checks):
    rows = []

    for key in ["road_section", "osm_lines", "osm_lines_expanded", "traffic_flow_links"]:
        p = find_file(data_root, CORE_FILES[key])
        if not p:
            continue

        try:
            if gpd is not None and p.suffix.lower() in {".shp", ".geojson", ".gpkg"}:
                gdf = gpd.read_file(p)
                crs = str(gdf.crs)
                rows.append({
                    "dataset": key,
                    "path": str(p),
                    "rows": len(gdf),
                    "crs": crs,
                    "geometry_types": ",".join(sorted(map(str, gdf.geometry.geom_type.dropna().unique()))),
                })

                if key == "road_section":
                    expected_fields = {"RD_CATG__1", "RD_CD_DESC"}
                    missing = expected_fields - set(gdf.columns)
                    add_check(
                        checks, "network", "road_section_fields",
                        "PASS" if not missing else "WARN",
                        f"missing={sorted(missing)}"
                    )

                if key == "traffic_flow_links":
                    if "LinkID" in gdf.columns:
                        unique_links = gdf["LinkID"].astype(str).str.strip().nunique()
                        add_check(
                            checks, "network", "traffic_link_unique",
                            "PASS",
                            f"unique={unique_links}, rows={len(gdf)}"
                        )
            else:
                add_check(checks, "network", key, "WARN", f"无法用 geopandas 检查: {p}")

        except Exception as exc:
            add_check(checks, "network", f"{key}_read", "FAIL", str(exc))

    # MATSim network presence
    matsim = find_file(data_root, CORE_FILES["matsim_network"])
    if matsim:
        add_check(checks, "network", "matsim_network", "PASS", str(matsim))
    else:
        add_check(
            checks, "network", "matsim_network",
            "WARN",
            "network.xml.gz 尚未生成；这是开发步骤，不属于原始数据缺失。"
        )

    if rows:
        pd.DataFrame(rows).to_csv(
            out_dir / "audit_network.csv",
            index=False,
            encoding="utf-8-sig"
        )


def audit_trafficflow(data_root: Path, out_dir: Path, checks):
    p = find_file(data_root, CORE_FILES["traffic_flow"])
    if not p:
        return

    try:
        with open(p, "r", encoding="utf-8") as f:
            raw = json.load(f)

        records = raw.get("Value", [])
        add_check(
            checks, "trafficflow", "record_count",
            "PASS" if records else "FAIL",
            f"{len(records):,}"
        )

        required = {
            "LinkID", "Date", "HourOfDate", "Volume",
            "StartLon", "StartLat", "EndLon", "EndLat",
            "RoadName", "RoadCat"
        }
        if records:
            missing = required - set(records[0].keys())
            add_check(
                checks, "trafficflow", "required_fields",
                "PASS" if not missing else "FAIL",
                f"missing={sorted(missing)}"
            )

        parsed_rows = []
        link_hours = defaultdict(list)
        date_values = set()
        roadcat_counter = Counter()

        for rec in records:
            link = normalize_name(rec.get("LinkID"))
            date_s = normalize_name(rec.get("Date"))
            hour = int(clean_numeric(rec.get("HourOfDate")) or -1)
            vol = clean_numeric(rec.get("Volume"))
            try:
                date_obj = datetime.strptime(date_s, "%d/%m/%Y")
                weekday = date_obj.strftime("%A")
                date_values.add(date_obj.date().isoformat())
            except ValueError:
                weekday = "INVALID"

            roadcat = normalize_name(rec.get("RoadCat"))
            roadcat_counter[roadcat] += 1

            if link and hour >= 0 and vol is not None:
                link_hours[(link, hour)].append(vol)

            parsed_rows.append({
                "LinkID": link,
                "Date": date_s,
                "HourOfDate": hour,
                "Volume": vol,
                "Weekday": weekday,
                "RoadCat": roadcat,
            })

        invalid_volume = sum(r["Volume"] is None for r in parsed_rows)
        add_check(
            checks, "trafficflow", "volume_parse_rate",
            "PASS" if invalid_volume == 0 else "WARN",
            f"invalid={invalid_volume}, total={len(parsed_rows)}"
        )

        unique_links = len({r["LinkID"] for r in parsed_rows if r["LinkID"]})
        add_check(
            checks, "trafficflow", "unique_link_count",
            "PASS" if unique_links > 1000 else "WARN",
            f"{unique_links:,}"
        )

        unique_dates = len(date_values)
        add_check(
            checks, "trafficflow", "unique_date_count",
            "PASS" if unique_dates >= 5 else "WARN",
            f"{unique_dates}"
        )

        am_rows = [
            r for r in parsed_rows
            if r["Weekday"] in WEEKDAYS and 7 <= r["HourOfDate"] <= 9
        ]
        add_check(
            checks, "trafficflow", "weekday_ampeak_rows",
            "PASS" if am_rows else "WARN",
            f"{len(am_rows):,}"
        )

        # 中位数汇总：LinkID × hour
        summary = []
        for (link, hour), vols in sorted(link_hours.items()):
            if not vols:
                continue
            summary.append({
                "LinkID": link,
                "hour": hour,
                "n": len(vols),
                "median_volume": float(pd.Series(vols).median()) if pd is not None else sorted(vols)[len(vols)//2],
            })

        if summary and pd is not None:
            df_summary = pd.DataFrame(summary)
            df_summary["hour"] = df_summary["hour"].astype(int)
            df_summary = df_summary[df_summary["hour"].between(7, 9)]
            df_summary.to_csv(
                out_dir / "audit_trafficflow.csv",
                index=False,
                encoding="utf-8-sig"
            )

        add_check(
            checks, "trafficflow", "road_category_distribution",
            "PASS",
            dict(roadcat_counter)
        )

    except Exception as exc:
        add_check(checks, "trafficflow", "read_json", "FAIL", str(exc))


def build_summary(checks, out_dir: Path, project_root: Path, data_root: Path):
    counter = Counter(c["status"] for c in checks)
    summary = {
        "generated_at": now_iso(),
        "project_root": str(project_root),
        "data_root": str(data_root),
        "status_counts": dict(counter),
        "overall": (
            "FAIL" if counter.get("FAIL", 0) > 0
            else "WARN" if counter.get("WARN", 0) > 0
            else "PASS"
        ),
        "checks": checks,
    }

    with open(out_dir / "audit_summary.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    return summary


def main():
    parser = argparse.ArgumentParser(
        description="Singapore OD -> MATSim Step 0 数据审计"
    )
    parser.add_argument(
        "--project-root",
        type=Path,
        default=DEFAULT_PROJECT_ROOT,
        help="PyCharm 项目根目录",
    )
    parser.add_argument(
        "--data-root",
        type=Path,
        default=None,
        help="最终数据根目录；默认 project-root/Singapore_OD_MATSim_FinalData",
    )
    args = parser.parse_args()

    project_root = args.project_root
    data_root = args.data_root or (project_root / DEFAULT_DATA_DIR_NAME)

    report_dir = project_root / "reports" / "od_audit"
    report_dir.mkdir(parents=True, exist_ok=True)

    checks = []

    if not project_root.exists():
        print(f"[ERROR] project root not found: {project_root}")
        sys.exit(2)

    if not data_root.exists():
        print(f"[ERROR] data root not found: {data_root}")
        sys.exit(2)

    audit_files(data_root, checks)
    audit_zones(data_root, report_dir, checks)
    audit_census(data_root, report_dir, checks)
    audit_acra(data_root, report_dir, checks)
    audit_network(data_root, report_dir, checks)
    audit_trafficflow(data_root, report_dir, checks)

    summary = build_summary(checks, report_dir, project_root, data_root)

    print("\n" + "=" * 72)
    print("Singapore OD -> MATSim | Step 0 Data Audit")
    print("=" * 72)
    print(f"Project : {project_root}")
    print(f"Data    : {data_root}")
    print(f"Overall : {summary['overall']}")
    print(f"PASS    : {summary['status_counts'].get('PASS', 0)}")
    print(f"WARN    : {summary['status_counts'].get('WARN', 0)}")
    print(f"FAIL    : {summary['status_counts'].get('FAIL', 0)}")
    print("-" * 72)

    for item in checks:
        print(f"[{item['status']:5}] {item['area']:12} {item['item']}: {item['detail']}")

    print("-" * 72)
    print(f"Reports: {report_dir}")

    if summary["overall"] == "FAIL":
        sys.exit(1)


if __name__ == "__main__":
    main()
