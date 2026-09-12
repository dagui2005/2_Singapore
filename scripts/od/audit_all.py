#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""
Singapore OD -> MATSim
Step 0: Data Audit (enhanced)

作用
----
只做“数据体检”，不修改任何原始数据。用于在写 Gravity / MATSim 之前，
确认数据接口与字段质量是否达到可开发标准。

覆盖四类必须验证项
------------------
1. 空间单元一致性  : Subzone(332) -> PlanningArea(55) -> Region(5) 三级映射；
                     Census 居住端 55 / 工作端 44+3 / 旅行端 30+Others 三套分区集合对比；
                     Table 118 与 Workplace T4 总量核对。
2. ACRA 落点匹配    : 用四源本地桥接表把 ACRA 企业按邮编落到 Subzone：
                     URANoofDwellingUnits(点) + hdb.csv + poi.csv + OSM(建筑/点 addr:postcode)。
                     统计匹配率、有效邮编率、失败原因。
3. LTA <-> OSM 链路 : TrafficFlow_Links(1278) 与 OSM 道路做几何+名称匹配，
                     分别报告“几何命中率”和“名称命中率”，为 OD 校准铺路。
4. 路网/流量完整性  : OSM 覆盖率、TrafficFlow 记录数/时间跨度/高峰分布、
                     MATSim network 是否存在。

运行
----
    python scripts/od/audit_all.py
    python scripts/od/audit_all.py --project-root "D:\Luan\2026-05\2_Singapore"
    python scripts/od/audit_all.py --skip-heavy      # 跳过 ACRA/链路匹配（快速体检）

输出
----
    reports/od_audit/
        audit_summary.json           总览 + 全部检查项 + 关键指标
        audit_zone.csv               Subzone 级 crosswalk（332 行，含质心/面积）
        audit_census.csv             Census 分区集合对比与总量核对
        audit_acra.csv               ACRA 各分片落点匹配率
        audit_network.csv            路网图层统计 + LTA<->OSM 匹配统计
        audit_trafficflow.csv        工作日早高峰 Link×hour 中位流量
        _lta_osm_match_detail.csv    LTA 链路匹配明细（人工复核用）
        _postal_subzone_bridge.csv   邮编→Subzone 桥接表（可复用）
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

try:
    import numpy as np
except ImportError:
    np = None

try:
    import pandas as pd
except ImportError:
    pd = None

try:
    import geopandas as gpd
except ImportError:
    gpd = None

try:
    import shapefile  # pyshp
except ImportError:
    shapefile = None

try:
    import shapely
except ImportError:
    shapely = None


# --------------------------------------------------------------------------- #
# 常量
# --------------------------------------------------------------------------- #

DEFAULT_PROJECT_ROOT = Path(r"D:\Luan\2026-05\2_Singapore")
DEFAULT_DATA_DIR_NAME = "Singapore_OD_MATSim_FinalData"

CRS_WGS84 = "EPSG:4326"
CRS_SVY21 = "EPSG:3414"      # 新加坡 SVY21，米制，用于距离/面积

CORE_FILES = {
    "subzone_boundary": "01_Boundary_TAZ/MasterPlan2019SubzoneBoundaryNoSeaGEOJSON.geojson",
    "planning_area_boundary": "01_Boundary_TAZ/MasterPlan2019PlanningAreaBoundaryNoSea.geojson",
    "residence_t1": "02_Population_Residence/outputFile (2)__T1.csv",
    "hdb_csv": "09_Auxiliary/POI_Background/hdb.csv",
    "workplace_t4": "03_Workplace_Employment/outputFile (3)__T4.csv",
    "workplace_t11": "03_Workplace_Employment/outputFile (3)__T11.csv",
    "travel_t15": "06_Census_TravelBehavior/outputFile (4)__T15.csv",
    "travel_t16": "06_Census_TravelBehavior/outputFile (4)__T16.csv",
    "traffic_mode_t7": "06_Census_TravelBehavior/outputFile (5)__T7.csv",
    "traffic_flow": "08_TrafficCount/TrafficFlow_Data.json",
    "traffic_flow_links": "08_TrafficCount/TrafficFlow_Links.shp",
    "road_section": "07_RoadNetwork/RoadSectionLine_Mar2026/RoadSectionLine.shp",
    "osm_lines": "07_RoadNetwork/osm-lines.shp",
    "osm_polygon": "07_RoadNetwork/osm-polygon.shp",
    "osm_points": "07_RoadNetwork/osm-points.shp",
    "matsim_network": "07_RoadNetwork/network.xml.gz",
    "acra_dir": "05_POI_Enterprise/ACRA",
    "landuse": "04_LandUse_Building/MasterPlan2019LandUselayer.geojson",
    "building": "04_LandUse_Building/MasterPlan2019Buildinglayer.geojson",
    "dwelling_points": "04_LandUse_Building/URANoofDwellingUnits.geojson",
    "poi": "05_POI_Enterprise/poi.csv",
}

EXPECTED_SUBZONE = 332
EXPECTED_PA = 55
EXPECTED_REGION = 5
EXPECTED_WORKPLACE_SPECIAL = 3
EXPECTED_TRAVEL_PA = 30

SPECIAL_NODES = {
    "OTHER_PA": "Other Planning Areas or Outside Singapore",
    "NO_FIXED": "No Fixed Location for Work",
    "WFH": "Works from Home",
    "OTHERS": "Others",
}

WEEKDAYS = {"Monday", "Tuesday", "Wednesday", "Thursday", "Friday"}

OSM_NON_ROAD = {
    "footway", "steps", "cycleway", "path", "pedestrian", "corridor",
    "track", "bridleway", "construction", "proposed", "bus_guideway",
    "raceway", "escape", "platform", "elevator",
}

LTA_BUFFER_M = 25.0
LTA_ACCEPT_M = 25.0

# 新加坡有效邮编：6 位，前两位 01–82
POSTAL_RE = re.compile(r"^(\d{6})$")


# --------------------------------------------------------------------------- #
# 通用工具
# --------------------------------------------------------------------------- #

def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def normalize_text(value: Any) -> str:
    if value is None:
        return ""
    s = str(value).replace("\xa0", " ")
    return re.sub(r"\s+", " ", s).strip()


def match_key(value: Any) -> str:
    return re.sub(r"[^A-Z0-9]", "", normalize_text(value).upper())


def clean_numeric(value: Any) -> float | None:
    if value is None:
        return None
    s = str(value).strip().replace(",", "")
    if s in {"", "-", "na", "NA", "null", "None", "nan"}:
        return None
    try:
        return float(s)
    except ValueError:
        return None


def norm_postal(value: Any) -> str | None:
    """归一化为 6 位邮编字符串（补前导 0）。"""
    if value is None:
        return None
    s = str(value).strip()
    if s in {"", "nan", "NaN", "na", "NA", "-", "None"}:
        return None
    s = re.sub(r"\.0$", "", s)
    s = re.sub(r"\D", "", s)
    if not s:
        return None
    return s.zfill(6)


def is_valid_sg_postal(p: Any) -> bool:
    """新加坡有效邮编：6 位且前两位 01–82。"""
    if not isinstance(p, str) or not POSTAL_RE.match(p):
        return False
    return 1 <= int(p[:2]) <= 82


def norm_postal_series(series):
    return series.map(norm_postal)


def find_file(data_root: Path, relative: str) -> Path | None:
    exact = data_root / relative
    if exact.exists():
        return exact
    cands = list(data_root.glob(f"**/{Path(relative).name}"))
    return cands[0] if len(cands) == 1 else None


def load_csv(path: Path, **kwargs):
    if pd is None:
        raise RuntimeError("缺少 pandas")
    kwargs.setdefault("encoding", "utf-8-sig")
    kwargs.setdefault("low_memory", False)
    return pd.read_csv(path, **kwargs)


def add_check(checks, area, item, status, detail):
    checks.append({"area": area, "item": item, "status": status, "detail": str(detail)})


# --------------------------------------------------------------------------- #
# 1. 文件完整性
# --------------------------------------------------------------------------- #

def audit_files(data_root: Path, checks):
    for key, rel in CORE_FILES.items():
        p = find_file(data_root, rel)
        if p is None:
            status = "WARN" if key == "matsim_network" else "FAIL"
            add_check(checks, "files", key, status, f"未找到: {rel}")
        else:
            add_check(checks, "files", key, "PASS",
                      f"{p} ({p.stat().st_size/1024/1024:.1f} MB)")


# --------------------------------------------------------------------------- #
# 2. 空间单元 crosswalk
# --------------------------------------------------------------------------- #

def build_crosswalk(data_root: Path, checks):
    sub_path = find_file(data_root, CORE_FILES["subzone_boundary"])
    if sub_path is None or gpd is None:
        add_check(checks, "zone", "crosswalk", "FAIL", "缺少 Subzone 边界或 geopandas")
        return None

    sub_ll = gpd.read_file(sub_path)
    required = {"SUBZONE_C", "SUBZONE_N", "PLN_AREA_C", "PLN_AREA_N", "REGION_C", "REGION_N"}
    missing = required - set(sub_ll.columns)
    if missing:
        add_check(checks, "zone", "subzone_required_fields", "FAIL", f"missing={sorted(missing)}")
        return None
    add_check(checks, "zone", "subzone_required_fields", "PASS", "6 字段齐全")

    try:
        sub_m = sub_ll.to_crs(CRS_SVY21)
        sub_ll = sub_ll.copy()
        sub_ll["centroid_x"] = sub_m.geometry.centroid.x.values
        sub_ll["centroid_y"] = sub_m.geometry.centroid.y.values
        sub_ll["area_m2"] = sub_m.geometry.area.values
        add_check(checks, "zone", "crosswalk_metric", "PASS", "已生成 SVY21 质心/面积")
    except Exception as exc:
        sub_ll["centroid_x"] = sub_ll["centroid_y"] = sub_ll["area_m2"] = None
        add_check(checks, "zone", "crosswalk_metric", "WARN", f"投影失败: {exc}")

    n = len(sub_ll)
    add_check(checks, "zone", "subzone_feature_count",
              "PASS" if n == EXPECTED_SUBZONE else "WARN",
              f"实际 {n}，期望 {EXPECTED_SUBZONE}")
    add_check(checks, "zone", "subzone_code_unique",
              "PASS" if sub_ll["SUBZONE_C"].astype(str).str.strip().nunique() == n else "FAIL",
              f"unique={sub_ll['SUBZONE_C'].astype(str).str.strip().nunique()}, rows={n}")
    add_check(checks, "zone", "subzone_pa_count",
              "PASS" if sub_ll["PLN_AREA_C"].astype(str).str.strip().nunique() == EXPECTED_PA else "WARN",
              str(sub_ll["PLN_AREA_C"].astype(str).str.strip().nunique()))
    add_check(checks, "zone", "subzone_region_count",
              "PASS" if sub_ll["REGION_C"].astype(str).str.strip().nunique() == EXPECTED_REGION else "WARN",
              str(sub_ll["REGION_C"].astype(str).str.strip().nunique()))
    add_check(checks, "zone", "subzone_crs",
              "PASS" if sub_ll.crs is not None else "WARN", f"CRS={sub_ll.crs}")
    return sub_ll


def audit_zones(data_root: Path, out_dir: Path, checks):
    cw = build_crosswalk(data_root, checks)
    if cw is None:
        return None

    rows = [{
        "zone_id": normalize_text(r.get("SUBZONE_C")),
        "subzone_code": normalize_text(r.get("SUBZONE_C")),
        "subzone_name": normalize_text(r.get("SUBZONE_N")),
        "planning_area_code": normalize_text(r.get("PLN_AREA_C")),
        "planning_area": normalize_text(r.get("PLN_AREA_N")),
        "planning_region_code": normalize_text(r.get("REGION_C")),
        "planning_region": normalize_text(r.get("REGION_N")),
        "centroid_x": r.get("centroid_x"),
        "centroid_y": r.get("centroid_y"),
        "area_m2": r.get("area_m2"),
    } for _, r in cw.iterrows()]

    pd.DataFrame(rows).to_csv(out_dir / "audit_zone.csv", index=False, encoding="utf-8-sig")
    add_check(checks, "zone", "audit_zone_export", "PASS", f"{len(rows)} 行")

    pa_path = find_file(data_root, CORE_FILES["planning_area_boundary"])
    if pa_path and gpd is not None:
        pas = gpd.read_file(pa_path)
        add_check(checks, "zone", "planning_area_feature_count",
                  "PASS" if len(pas) == EXPECTED_PA else "WARN", f"{len(pas)}")
        derived = set(cw["PLN_AREA_C"].astype(str).str.strip())
        official = set(pas["PLN_AREA_C"].astype(str).str.strip())
        only_d, only_o = derived - official, official - derived
        add_check(checks, "zone", "subzone_pa_vs_boundary_pa",
                  "PASS" if not only_d and not only_o else "FAIL",
                  f"derived={len(derived)}, official={len(official)}, "
                  f"only_derived={sorted(only_d)}, only_official={sorted(only_o)}")
    return cw


# --------------------------------------------------------------------------- #
# 3. Census 一致性
# --------------------------------------------------------------------------- #

PA_TOTAL_RE = re.compile(r"^(?P<pa>.+?)\s*-\s*Total$", re.IGNORECASE)


def classify_rows(values: list[str]) -> dict:
    """把首列标签拆成 Total / PA-Total / 其它(Subzone)。
    注意：能容忍 'Changi- Total'（连字符前无空格）这种导出不一致。"""
    national, pa_total, subzone = [], [], []
    for v in values:
        if not v:
            continue
        if v.strip().upper() == "TOTAL":
            national.append(v)
            continue
        m = PA_TOTAL_RE.match(v)
        if m:
            pa_total.append(m.group("pa").strip())
        else:
            subzone.append(v)
    return {"national": national, "pa_total": pa_total, "subzone": subzone}


def read_first_column(path: Path):
    df = load_csv(path)
    key = str(df.columns[0])
    values = [normalize_text(v) for v in df[key].dropna().tolist()]
    return df, values


def row_grand_total(row, label_col) -> float | None:
    """取总量：优先使用名为 Total 的列，否则对其余列求和。"""
    if row is None:
        return None
    for c in row.index:
        if c != label_col and match_key(c) == "TOTAL":
            v = clean_numeric(row[c])
            if v is not None:
                return v
    vals = pd.to_numeric(
        pd.Series(row.drop(labels=[label_col])).astype(str).str.replace(",", "", regex=False),
        errors="coerce")
    return float(vals.sum()) if len(vals) else None


def audit_census(data_root: Path, out_dir: Path, checks):
    report = []
    sets: dict[str, set] = {}
    nice: dict[str, str] = {}

    # 居住端 T1
    p = find_file(data_root, CORE_FILES["residence_t1"])
    if p:
        try:
            df, values = read_first_column(p)
            parts = classify_rows(values)
            sets["residence"] = {match_key(x) for x in parts["pa_total"]}
            nice.update({match_key(x): x for x in parts["pa_total"]})
            add_check(checks, "census", "residence_t1_read", "PASS",
                      f"rows={len(df)}, key={df.columns[0]}")
            add_check(checks, "census", "residence_t1_pa_count",
                      "PASS" if len(parts["pa_total"]) == EXPECTED_PA else "WARN",
                      f"{len(parts['pa_total'])}")
            add_check(checks, "census", "residence_t1_subzone_count",
                      "PASS" if len(parts["subzone"]) == EXPECTED_SUBZONE else "WARN",
                      f"{len(parts['subzone'])}")
            report += [
                {"check": "residence_t1", "metric": "rows", "value": len(df)},
                {"check": "residence_t1", "metric": "pa_total", "value": len(parts["pa_total"])},
                {"check": "residence_t1", "metric": "subzone", "value": len(parts["subzone"])},
            ]
        except Exception as exc:
            add_check(checks, "census", "residence_t1_read", "FAIL", str(exc))

    # 工作端 T4
    wp = find_file(data_root, CORE_FILES["workplace_t4"])
    if wp:
        try:
            df, values = read_first_column(wp)
            special = sorted({v for v in values if v in SPECIAL_NODES.values()})
            normal = [v for v in values if v and v.upper() != "TOTAL" and v not in SPECIAL_NODES.values()]
            sets["workplace"] = {match_key(x) for x in normal}
            nice.update({match_key(x): x for x in normal})
            add_check(checks, "census", "workplace_t4_read", "PASS",
                      f"rows={len(df)}, key={df.columns[0]}")
            add_check(checks, "census", "workplace_special_nodes",
                      "PASS" if len(special) == EXPECTED_WORKPLACE_SPECIAL else "WARN",
                      f"{special}")
            report += [
                {"check": "workplace_t4", "metric": "rows", "value": len(df)},
                {"check": "workplace_t4", "metric": "pa_normal", "value": len(normal)},
                {"check": "workplace_t4", "metric": "special_nodes", "value": len(special)},
            ]
        except Exception as exc:
            add_check(checks, "census", "workplace_t4_read", "FAIL", str(exc))

    # 旅行端 T15
    tp = find_file(data_root, CORE_FILES["travel_t15"])
    if tp:
        try:
            df, values = read_first_column(tp)
            normal = [v for v in values if v and v.upper() != "TOTAL" and v != SPECIAL_NODES["OTHERS"]]
            sets["travel"] = {match_key(x) for x in normal}
            nice.update({match_key(x): x for x in normal})
            add_check(checks, "census", "travel_t15_read", "PASS",
                      f"rows={len(df)}, key={df.columns[0]}")
            add_check(checks, "census", "travel_pa_count",
                      "PASS" if len(normal) == EXPECTED_TRAVEL_PA else "WARN", f"{len(normal)}")
            report += [
                {"check": "travel_t15", "metric": "rows", "value": len(df)},
                {"check": "travel_t15", "metric": "pa_normal", "value": len(normal)},
            ]
        except Exception as exc:
            add_check(checks, "census", "travel_t15_read", "FAIL", str(exc))

    # 三套集合对比（子集关系 = 正常；非嵌套 = 需人工确认）
    if len(sets) >= 2:
        names = [n for n in ["residence", "workplace", "travel"] if n in sets]
        def show(keys):
            return [nice.get(k, k) for k in sorted(keys)]
        for i in range(len(names)):
            for j in range(i + 1, len(names)):
                a, b = names[i], names[j]
                only_a, only_b = sets[a] - sets[b], sets[b] - sets[a]
                if not only_a and not only_b:
                    status, rel = "PASS", "完全相同"
                elif not only_a:
                    status, rel = "PASS", f"{a} ⊂ {b}（正常：{a} 更粗）"
                elif not only_b:
                    status, rel = "PASS", f"{b} ⊂ {a}（正常：{b} 更粗）"
                else:
                    status, rel = "WARN", "互不包含，需确认"
                add_check(
                    checks, "census", f"pa_set_{a}_vs_{b}", status,
                    f"|{a}|={len(sets[a])}, |{b}|={len(sets[b])}, 交集={len(sets[a]&sets[b])}, "
                    f"仅{a}={show(only_a)}, 仅{b}={show(only_b)} → {rel}")
                report += [
                    {"check": f"pa_set_{a}_vs_{b}", "metric": "intersection", "value": len(sets[a] & sets[b])},
                    {"check": f"pa_set_{a}_vs_{b}", "metric": f"only_{a}", "value": len(only_a)},
                    {"check": f"pa_set_{a}_vs_{b}", "metric": f"only_{b}", "value": len(only_b)},
                ]
        common = set.intersection(*[sets[n] for n in names])
        add_check(checks, "census", "pa_set_common_core", "PASS",
                  f"三套共同 PA = {len(common)} → 建模核心区")
        report.append({"check": "pa_set_common_core", "metric": "common_pa", "value": len(common)})

    # Table 118 vs Workplace T4 总量
    t11p = find_file(data_root, CORE_FILES["workplace_t11"])
    if t11p and wp:
        try:
            t11 = load_csv(t11p)
            t4 = load_csv(wp)
            k11, k4 = str(t11.columns[0]), str(t4.columns[0])
            r11 = t11[t11[k11].astype(str).str.strip().str.upper() == "TOTAL"]
            r4 = t4[t4[k4].astype(str).str.strip().str.upper() == "TOTAL"]
            if len(r11) and len(r4):
                v11 = row_grand_total(r11.iloc[0], k11)
                v4 = row_grand_total(r4.iloc[0], k4)
                delta = (v11 - v4) if (v11 is not None and v4 is not None) else None
                rel = (abs(delta) / v4 * 100) if (delta is not None and v4) else None
                status = "PASS" if (rel is not None and rel < 1.0) else "WARN"
                add_check(checks, "census", "table118_vs_workplace_t4_total", status,
                          f"Table118={v11:,.0f}, T4={v4:,.0f}, 差={delta:,.0f}, 相对差={rel:.3f}%"
                          if delta is not None else "无法计算")
                report += [
                    {"check": "table118_vs_t4", "metric": "table118_total", "value": v11},
                    {"check": "table118_vs_t4", "metric": "t4_total", "value": v4},
                    {"check": "table118_vs_t4", "metric": "delta", "value": delta},
                ]
        except Exception as exc:
            add_check(checks, "census", "table118_vs_workplace_t4_total", "FAIL", str(exc))

    for label, key in [("travel_t16", "travel_t16"), ("traffic_mode_t7", "traffic_mode_t7")]:
        pp = find_file(data_root, CORE_FILES[key])
        if pp:
            try:
                d = load_csv(pp)
                add_check(checks, "census", f"{label}_read", "PASS",
                          f"rows={len(d)}, cols={len(d.columns)}")
            except Exception as exc:
                add_check(checks, "census", f"{label}_read", "FAIL", str(exc))

    if report:
        pd.DataFrame(report).to_csv(out_dir / "audit_census.csv", index=False, encoding="utf-8-sig")
    return sets


# --------------------------------------------------------------------------- #
# 4. ACRA -> Subzone 落点匹配
# --------------------------------------------------------------------------- #

def extract_osm_postcode_points(shp_path: Path):
    """从 OSM 建筑/点图层 other_tags 抽出 addr:postcode + 代表点。"""
    if shapefile is None:
        return [], []
    r = shapefile.Reader(str(shp_path), encoding="latin-1")
    fields = [f[0] for f in r.fields[1:]]
    if "other_tags" not in fields:
        return [], []
    i_ot = fields.index("other_tags")
    pat = re.compile(r'addr:postcode"\s*=>\s*"(\d{6})"')
    postals, pts = [], []
    for sr in r.iterShapeRecords():
        ot = sr.record[i_ot]
        if not ot or "postcode" not in str(ot):
            continue
        m = pat.search(str(ot))
        if not m:
            continue
        ptsl = sr.shape.points
        if not ptsl:
            continue
        x = sum(p[0] for p in ptsl) / len(ptsl)
        y = sum(p[1] for p in ptsl) / len(ptsl)
        postals.append(m.group(1))
        pts.append((x, y))
    return postals, pts


def build_postal_bridge(data_root: Path, subzones_ll, checks):
    """构建 postal -> SUBZONE_C 桥接表（四源合并）。"""
    bridge: dict[str, str] = {}
    stats = {}

    # A. URANoof 住宅单元点
    try:
        p = find_file(data_root, CORE_FILES["dwelling_points"])
        if p and gpd is not None:
            g = gpd.read_file(p)
            g = g[g["POSTALCODE"].notna()].copy()
            g["_p"] = norm_postal_series(g["POSTALCODE"])
            g = g[g["_p"].notna()].copy()
            if g.crs is not None and str(g.crs) != CRS_WGS84:
                g = g.to_crs(CRS_WGS84)
            j = gpd.sjoin(g[["_p", "geometry"]], subzones_ll[["SUBZONE_C", "geometry"]],
                          predicate="within", how="inner")
            for pp, sc in zip(j["_p"], j["SUBZONE_C"]):
                bridge.setdefault(pp, normalize_text(sc))
            stats["uranof"] = len(j)
            add_check(checks, "acra", "bridge_uranof", "PASS",
                      f"点={len(g):,}, 落入 Subzone={len(j):,}")
    except Exception as exc:
        add_check(checks, "acra", "bridge_uranof", "WARN", str(exc))

    # B. hdb.csv
    try:
        p = find_file(data_root, CORE_FILES["hdb_csv"])
        if p:
            h = load_csv(p, usecols=lambda c: c in {"postal", "SUBZONE_C"})
            cnt = 0
            for pp, sc in zip(norm_postal_series(h["postal"]), h["SUBZONE_C"]):
                if pp and isinstance(sc, str) and sc.strip():
                    bridge.setdefault(pp, normalize_text(sc)); cnt += 1
            stats["hdb"] = cnt
            add_check(checks, "acra", "bridge_hdb", "PASS", f"记录={cnt:,}")
    except Exception as exc:
        add_check(checks, "acra", "bridge_hdb", "WARN", str(exc))

    # C. poi.csv（从地址提取邮编）
    try:
        p = find_file(data_root, CORE_FILES["poi"])
        if p:
            poi = load_csv(p, usecols=lambda c: c in {"formatted_address", "SUBZONE_C"})
            addr = poi["formatted_address"].astype(str)
            post = addr.str.extract(r"Singapore\s*(\d{6})")[0]
            post = post.fillna(addr.str.extract(r"(\d{6})\s*$")[0])
            cnt = 0
            for pp, sc in zip(post, poi["SUBZONE_C"]):
                np_ = norm_postal(pp)
                if np_ and isinstance(sc, str) and sc.strip():
                    bridge.setdefault(np_, normalize_text(sc)); cnt += 1
            stats["poi"] = cnt
            add_check(checks, "acra", "bridge_poi", "PASS", f"记录={cnt:,}")
    except Exception as exc:
        add_check(checks, "acra", "bridge_poi", "WARN", str(exc))

    # D. OSM 建筑 + 点（addr:postcode）
    try:
        from shapely.geometry import Point
        allp, allxy = [], []
        for key in ["osm_polygon", "osm_points"]:
            p = find_file(data_root, CORE_FILES[key])
            if p is None:
                continue
            pp, xy = extract_osm_postcode_points(p)
            allp += pp; allxy += xy
            stats[f"osm_{key.split('_')[1]}"] = len(pp)
        if allp:
            g = gpd.GeoDataFrame(
                {"p": allp},
                geometry=[Point(x, y) for x, y in allxy], crs=CRS_WGS84)
            j = gpd.sjoin(g, subzones_ll[["SUBZONE_C", "geometry"]],
                          predicate="within", how="inner")
            for pp, sc in zip(j["p"], j["SUBZONE_C"]):
                bridge.setdefault(pp, normalize_text(sc))
            add_check(checks, "acra", "bridge_osm", "PASS",
                      f"建筑/点带邮编={len(allp):,}, 落入 Subzone={len(j):,}")
    except Exception as exc:
        add_check(checks, "acra", "bridge_osm", "WARN", str(exc))

    add_check(checks, "acra", "bridge_postal_unique", "PASS",
              f"{len(bridge):,} 个唯一邮编（来源：{stats}）")
    return bridge


def audit_acra(data_root: Path, out_dir: Path, subzones_ll, checks, skip_heavy=False):
    acra_dir = data_root / CORE_FILES["acra_dir"]
    if not acra_dir.exists():
        add_check(checks, "acra", "acra_directory", "FAIL", str(acra_dir))
        return

    files = sorted(acra_dir.glob("*.csv"))
    add_check(checks, "acra", "acra_shard_count",
              "PASS" if len(files) == 12 else "WARN", f"{len(files)} CSV")

    bridge = {}
    if not skip_heavy and subzones_ll is not None:
        t = time.time()
        bridge = build_postal_bridge(data_root, subzones_ll, checks)
        print(f"      桥接表构建完成：{len(bridge):,} 邮编（{time.time()-t:.1f}s）")

        # 导出桥接表供后续复用
        pd.DataFrame({"postal": list(bridge.keys()),
                      "subzone_code": list(bridge.values())}).sort_values("postal").to_csv(
            out_dir / "_postal_subzone_bridge.csv", index=False, encoding="utf-8-sig")
    elif skip_heavy:
        add_check(checks, "acra", "bridge_skipped", "WARN", "--skip-heavy：跳过落点桥接")

    need = {"uen", "postal_code", "block", "street_name", "building_name",
            "primary_ssic_code", "no_of_officers"}
    rows = []
    total = valid = matched = 0
    matched_valid = 0

    for path in files:
        try:
            df = load_csv(path, usecols=lambda c: c in need)
            n = len(df)
            total += n
            if "postal_code" in df.columns:
                pser = norm_postal_series(df["postal_code"])
                vmask = pser.map(is_valid_sg_postal)
                n_valid = int(vmask.sum())
                valid += n_valid
                if bridge:
                    m = int(pser.isin(set(bridge)).sum())
                    mv = int((pser.isin(set(bridge)) & vmask).sum())
                else:
                    m = mv = 0
            else:
                n_valid = m = mv = 0
            matched += m
            matched_valid += mv
            rows.append({
                "file": path.name, "rows": n,
                "valid_postal": n_valid,
                "valid_postal_rate_%": round(n_valid / n * 100, 2) if n else 0,
                "matched": m,
                "match_rate_all_%": round(m / n * 100, 2) if n else 0,
                "match_rate_valid_%": round(mv / n_valid * 100, 2) if n_valid else 0,
            })
        except Exception as exc:
            add_check(checks, "acra", f"read_{path.name}", "FAIL", str(exc))

    add_check(checks, "acra", "acra_total_rows", "PASS" if total > 500_000 else "WARN", f"{total:,}")
    add_check(checks, "acra", "acra_valid_postal_rate", "PASS",
              f"{valid:,}/{total:,} = {valid/total*100:.1f}%" if total else "n/a")

    if bridge:
        rate_all = matched / total * 100 if total else 0
        rate_valid = matched_valid / valid * 100 if valid else 0
        status = "PASS" if rate_valid >= 90 else ("WARN" if rate_valid >= 80 else "FAIL")
        add_check(checks, "acra", "acra_spatial_match_rate", status,
                  f"全部 {matched:,}/{total:,}={rate_all:.1f}%; "
                  f"有效邮编 {matched_valid:,}/{valid:,}={rate_valid:.1f}% (桥接 {len(bridge):,})")
        rows.append({
            "file": "ALL", "rows": total, "valid_postal": valid,
            "valid_postal_rate_%": round(valid / total * 100, 2) if total else 0,
            "matched": matched,
            "match_rate_all_%": round(rate_all, 2),
            "match_rate_valid_%": round(rate_valid, 2),
        })

    add_check(checks, "acra", "no_of_officers_semantics", "PASS",
              "仅作辅助企业特征，不得直接当员工数（仅用于就业空间下分）。")

    if rows:
        pd.DataFrame(rows).to_csv(out_dir / "audit_acra.csv", index=False, encoding="utf-8-sig")


# --------------------------------------------------------------------------- #
# 5. 路网 + LTA <-> OSM 匹配
# --------------------------------------------------------------------------- #

def load_osm_roads(data_root: Path):
    p = find_file(data_root, CORE_FILES["osm_lines"])
    if p is None or gpd is None:
        return None
    g = gpd.read_file(p, columns=["name", "highway"], encoding="latin-1")
    g = g[~g["highway"].isin(OSM_NON_ROAD)].copy()
    g["name_key"] = g["name"].map(match_key)
    return g


def match_lta_to_osm(data_root: Path, out_dir: Path, checks):
    lta_path = find_file(data_root, CORE_FILES["traffic_flow_links"])
    if lta_path is None:
        return None
    try:
        lta = gpd.read_file(lta_path)
        osm = load_osm_roads(data_root)
        if osm is None or len(osm) == 0:
            add_check(checks, "network", "lta_osm_match", "FAIL", "OSM 道路为空")
            return None

        lta_m = lta.to_crs(CRS_SVY21)
        osm_m = osm.to_crs(CRS_SVY21)
        sindex = osm_m.sindex
        osm_geoms = osm_m.geometry.values
        osm_names = osm_m["name_key"].values

        n_geom = n_name = n_none = n_multi = 0
        details = []

        for _, row in lta_m.iterrows():
            geom = row.geometry
            nk = match_key(row.get("RoadName"))
            if geom is None or geom.is_empty:
                n_none += 1
                continue
            cand = list(sindex.query(geom.buffer(LTA_BUFFER_M), predicate="intersects"))
            if not cand:
                n_none += 1
                details.append({"LinkID": row.get("LinkID"), "RoadName": normalize_text(row.get("RoadName")),
                                "n_cand": 0, "min_dist_m": None, "name_match": False, "status": "unmatched"})
                continue

            dists = shapely.distance(geom, osm_geoms[cand])
            best = int(np.argmin(dists))
            best_dist = float(dists[best])
            geom_ok = best_dist <= LTA_ACCEPT_M
            name_ok = bool(nk) and (osm_names[cand] == nk).any()

            if geom_ok:
                n_geom += 1
            if name_ok:
                n_name += 1
            near = int((dists <= LTA_ACCEPT_M).sum())
            if near > 1:
                n_multi += 1
            status = "one_to_one" if near == 1 else ("one_to_many" if near > 1 else "unmatched")

            details.append({
                "LinkID": row.get("LinkID"),
                "RoadName": normalize_text(row.get("RoadName")),
                "n_cand": len(cand), "min_dist_m": round(best_dist, 2),
                "name_match": name_ok, "status": status,
            })

        n = len(lta_m)
        geom_rate = n_geom / n * 100 if n else 0
        name_rate = n_name / n * 100 if n else 0
        add_check(checks, "network", "lta_osm_geom_match",
                  "PASS" if geom_rate >= 95 else ("WARN" if geom_rate >= 85 else "FAIL"),
                  f"{n_geom}/{n} = {geom_rate:.1f}%（OSM 道路在 {LTA_ACCEPT_M:.0f}m 内）")
        add_check(checks, "network", "lta_osm_name_match",
                  "PASS" if name_rate >= 70 else "WARN",
                  f"{n_name}/{n} = {name_rate:.1f}%（候选段中存在同名道路）")
        add_check(checks, "network", "lta_osm_unmatched", "PASS" if n_none == 0 else "WARN",
                  f"{n_none}（1:N 属正常：OSM 把道路切成碎段，n_multi={n_multi}）")

        pd.DataFrame(details).to_csv(out_dir / "_lta_osm_match_detail.csv",
                                     index=False, encoding="utf-8-sig")

        return {
            "dataset": "lta_osm_match", "path": str(lta_path), "rows": n,
            "crs": CRS_WGS84, "geometry_types": "LineString",
            "note": f"几何命中 {geom_rate:.1f}% | 名称命中 {name_rate:.1f}% | 未匹配 {n_none}",
        }
    except Exception as exc:
        add_check(checks, "network", "lta_osm_match", "FAIL", str(exc))
        return None


def audit_network(data_root: Path, out_dir: Path, checks, skip_heavy=False):
    rows = []
    for key in ["road_section", "osm_lines", "traffic_flow_links"]:
        p = find_file(data_root, CORE_FILES[key])
        if not p:
            continue
        try:
            if key == "osm_lines":
                g = load_osm_roads(data_root)
                if g is not None:
                    rows.append({"dataset": key, "path": str(p), "rows": len(g),
                                 "crs": str(g.crs), "geometry_types": "LineString",
                                 "note": "已剔除 footway/steps/path 等非机动车道"})
                    add_check(checks, "network", "osm_lines_read", "PASS",
                              f"道路 {len(g):,} 条（latin-1 按列读取）")
            else:
                g = gpd.read_file(p)
                rows.append({"dataset": key, "path": str(p), "rows": len(g),
                             "crs": str(g.crs),
                             "geometry_types": ",".join(sorted(g.geom_type.dropna().unique().tolist())),
                             "note": ""})
                if key == "road_section":
                    miss = {"RD_CATG__1", "RD_CD_DESC"} - set(g.columns)
                    add_check(checks, "network", "road_section_fields",
                              "PASS" if not miss else "WARN", f"missing={sorted(miss)}")
                if key == "traffic_flow_links" and "LinkID" in g.columns:
                    u = g["LinkID"].astype(str).str.strip().nunique()
                    add_check(checks, "network", "traffic_link_unique", "PASS",
                              f"unique={u}, rows={len(g)}")
        except Exception as exc:
            add_check(checks, "network", f"{key}_read", "FAIL", str(exc))

    matsim = find_file(data_root, CORE_FILES["matsim_network"])
    add_check(checks, "network", "matsim_network", "PASS" if matsim else "WARN",
              str(matsim) if matsim else "network.xml.gz 未生成（属开发步骤，非数据缺失）")

    if not skip_heavy and gpd is not None and shapely is not None and np is not None:
        ms = match_lta_to_osm(data_root, out_dir, checks)
        if ms:
            rows.append(ms)

    if rows:
        pd.DataFrame(rows).to_csv(out_dir / "audit_network.csv", index=False, encoding="utf-8-sig")


# --------------------------------------------------------------------------- #
# 6. TrafficFlow
# --------------------------------------------------------------------------- #

def audit_trafficflow(data_root: Path, out_dir: Path, checks):
    p = find_file(data_root, CORE_FILES["traffic_flow"])
    if not p:
        return
    try:
        with open(p, "r", encoding="utf-8") as f:
            raw = json.load(f)
        records = raw.get("Value", [])
        add_check(checks, "trafficflow", "record_count",
                  "PASS" if records else "FAIL", f"{len(records):,}")
        required = {"LinkID", "Date", "HourOfDate", "Volume",
                    "StartLon", "StartLat", "EndLon", "EndLat", "RoadName", "RoadCat"}
        if records:
            miss = required - set(records[0].keys())
            add_check(checks, "trafficflow", "required_fields",
                      "PASS" if not miss else "FAIL", f"missing={sorted(miss)}")

        link_hours = defaultdict(list)
        dates = set()
        roadcat = Counter()
        invalid = am = 0
        for rec in records:
            link = normalize_text(rec.get("LinkID"))
            vol = clean_numeric(rec.get("Volume"))
            hour = int(clean_numeric(rec.get("HourOfDate")) or -1)
            roadcat[normalize_text(rec.get("RoadCat"))] += 1
            if vol is None:
                invalid += 1
            try:
                d = datetime.strptime(normalize_text(rec.get("Date")), "%d/%m/%Y")
                dates.add(d.date().isoformat()); wd = d.strftime("%A")
            except ValueError:
                wd = "INVALID"
            if link and hour >= 0 and vol is not None:
                link_hours[(link, hour)].append(vol)
                if wd in WEEKDAYS and 7 <= hour <= 9:
                    am += 1

        add_check(checks, "trafficflow", "volume_parse_rate", "PASS" if invalid == 0 else "WARN",
                  f"invalid={invalid}")
        add_check(checks, "trafficflow", "unique_link_count",
                  "PASS" if len({k[0] for k in link_hours}) > 1000 else "WARN",
                  f"{len({k[0] for k in link_hours}):,}")
        add_check(checks, "trafficflow", "unique_date_count",
                  "PASS" if len(dates) >= 5 else "WARN", f"{len(dates)}")
        add_check(checks, "trafficflow", "weekday_ampeak_rows",
                  "PASS" if am else "WARN", f"{am:,}")
        add_check(checks, "trafficflow", "road_category_distribution", "PASS", dict(roadcat))

        out = [{"LinkID": link, "hour": hour, "n": len(v),
                "median_volume": float(np.median(v))}
               for (link, hour), v in sorted(link_hours.items()) if 7 <= hour <= 9 and v]
        if out:
            pd.DataFrame(out).to_csv(out_dir / "audit_trafficflow.csv",
                                     index=False, encoding="utf-8-sig")
    except Exception as exc:
        add_check(checks, "trafficflow", "read_json", "FAIL", str(exc))


# --------------------------------------------------------------------------- #
# 汇总
# --------------------------------------------------------------------------- #

def build_summary(checks, out_dir, project_root, data_root):
    counter = Counter(c["status"] for c in checks)
    metrics = {}
    for key, label in [
        ("acra_spatial_match_rate", "acra_match"),
        ("lta_osm_geom_match", "lta_osm_geom_match"),
        ("lta_osm_name_match", "lta_osm_name_match"),
        ("table118_vs_workplace_t4_total", "table118_vs_t4"),
        ("pa_set_common_core", "common_core_pa"),
    ]:
        for c in checks:
            if c["item"] == key:
                metrics[label] = f"{c['detail']} [{c['status']}]"
    summary = {
        "generated_at": now_iso(),
        "project_root": str(project_root),
        "data_root": str(data_root),
        "status_counts": dict(counter),
        "overall": ("FAIL" if counter.get("FAIL", 0) > 0
                    else "WARN" if counter.get("WARN", 0) > 0 else "PASS"),
        "key_metrics": metrics,
        "checks": checks,
    }
    with open(out_dir / "audit_summary.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    return summary


def main():
    ap = argparse.ArgumentParser(description="Singapore OD -> MATSim Step 0 数据审计")
    ap.add_argument("--project-root", type=Path, default=DEFAULT_PROJECT_ROOT)
    ap.add_argument("--data-root", type=Path, default=None)
    ap.add_argument("--skip-heavy", action="store_true")
    args = ap.parse_args()

    project_root = args.project_root
    data_root = args.data_root or (project_root / DEFAULT_DATA_DIR_NAME)

    if pd is None or gpd is None:
        print("[ERROR] 需要 pandas 与 geopandas。")
        sys.exit(2)
    if not data_root.exists():
        print(f"[ERROR] data root 不存在: {data_root}")
        sys.exit(2)

    report_dir = project_root / "reports" / "od_audit"
    report_dir.mkdir(parents=True, exist_ok=True)

    checks = []
    print("=" * 78)
    print("Singapore OD -> MATSim | Step 0 Data Audit")
    print("=" * 78)
    print(f"Project : {project_root}")
    print(f"Data    : {data_root}")
    print("-" * 78)

    t0 = time.time()
    audit_files(data_root, checks);                          print("[1/6] 文件完整性 ...... done")
    subzones = audit_zones(data_root, report_dir, checks);   print("[2/6] 空间 crosswalk .... done")
    audit_census(data_root, report_dir, checks);             print("[3/6] Census 一致性 ..... done")
    audit_acra(data_root, report_dir, subzones, checks, args.skip_heavy); print("[4/6] ACRA 落点匹配 .... done")
    audit_network(data_root, report_dir, checks, args.skip_heavy);         print("[5/6] 路网/链路匹配 .... done")
    audit_trafficflow(data_root, report_dir, checks);        print("[6/6] 实测流量 ......... done")

    summary = build_summary(checks, report_dir, project_root, data_root)

    print("-" * 78)
    print(f"Overall : {summary['overall']}   ({time.time()-t0:.0f}s)")
    print(f"PASS {summary['status_counts'].get('PASS',0)} | "
          f"WARN {summary['status_counts'].get('WARN',0)} | "
          f"FAIL {summary['status_counts'].get('FAIL',0)}")
    print("-" * 78)
    for item in checks:
        print(f"[{item['status']:5}] {item['area']:11} {item['item']}: {item['detail']}")
    print("-" * 78)
    print(f"Reports: {report_dir}")
    for k, v in summary["key_metrics"].items():
        print(f"    - {k}: {v}")

    if summary["overall"] == "FAIL":
        sys.exit(1)


if __name__ == "__main__":
    main()
