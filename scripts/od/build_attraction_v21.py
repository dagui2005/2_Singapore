#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Step 3B.1: Census-controlled workplace attraction (Attraction v2.1).

与 v2 的三处结构性差异（不动四组件权重 0.55/0.30/0.10/0.05）：
  A. PA 内归一化由 min-max(+0.05 floor) 改为 log1p + PA 求和归一化：
         x' = log(1+x) ;  s_{z,k} = x'_{z,k} / Σ_{z∈PA} x'_{z,k}
     不再做 min-max，也不再加 0.05 floor —— 保留绝对量级信息。
  B. 建筑层数：优先 building:levels / height；缺失时按「建筑类型」的
     明确记录先验层数（先验由有实测层数的同类型建筑中位数推导，n>=20 才采信，
     否则回退全局中位数）。先验表写入 building_level_prior.csv，可人工标定。
  C. LandUse 完全改用 landuse_class_mapping.csv（33/33 真实类别全覆盖，
     WATERBODY / ROAD 等非就业承载用地 employment_factor = 0）。

输出目录 reports/od_attraction_v21/（不覆盖 v1 / v2）。
"""
from __future__ import annotations
import argparse, json, re
from pathlib import Path
import geopandas as gpd
import numpy as np
import pandas as pd

ROOT = Path(r"D:\Luan\2026-05\2_Singapore")
DATA = ROOT / "Singapore_OD_MATSim_FinalData"
ZONE = ROOT / "reports/od_zone/zone_dictionary.csv"
PROD = ROOT / "reports/od_production/production.csv"
T4 = DATA / "03_Workplace_Employment/outputFile (3)__T4.csv"
LU = DATA / "04_LandUse_Building/MasterPlan2019LandUselayer.geojson"
# 用 expanded 版（building / building:l / height 已是独立列），绕开 osm-polygon.dbf
# 中 other_tags 字段的 UTF-8 解码失败问题（GDAL 只取 ASCII 列即可）。
BLDG = DATA / "07_RoadNetwork/osm-polygon_expanded.shp"
POI = DATA / "05_POI_Enterprise/poi.csv"
ACRA = DATA / "05_POI_Enterprise/ACRA"
SUBZONE = DATA / "01_Boundary_TAZ/MasterPlan2019SubzoneBoundaryNoSeaGEOJSON.geojson"
BRIDGE = ROOT / "reports/od_audit/_postal_subzone_bridge.csv"
OUT = ROOT / "reports/od_attraction_v21"
LU_MAP = ROOT / "reports/od_attraction_v2/landuse_class_mapping.csv"
LEVEL_PRIOR = OUT / "building_level_prior.csv"

SPECIAL = {"OTHER PLANNING AREAS OR OUTSIDE SINGAPORE", "NO FIXED LOCATION FOR WORK", "WORKS FROM HOME"}
# 四组件权重（本步固定不变，新增：LANDUSE 用映射表 employment_factor）
W_ACRA, W_GFA, W_LU, W_POI = 0.55, 0.30, 0.10, 0.05
PRIOR_MIN_N = 20          # 类型实测样本 >= 20 才采信中位数先验
LEVEL_CLIP = (1.0, 80.0)  # 层数上下限

POI_W = {"office":1.0,"bank":1.1,"finance":1.1,"company":0.7,"shopping_mall":1.0,"supermarket":0.6,
         "food":0.25,"restaurant":0.25,"lodging":0.45,"hospital":1.0,"health":0.75,
         "school":0.75,"university":1.0,"transit_station":0.5}


def nt(x):
    if pd.isna(x):
        return ""
    return re.sub(r"\s+", " ", str(x).replace("\xa0", " ").strip())


def nn(x):
    return nt(x).upper()


def num(x):
    return pd.to_numeric(pd.Series([x]).astype(str).str.replace(",", "", regex=False), errors="coerce").iloc[0]


def _levels_series(s):
    return pd.to_numeric(
        s.astype(str).str.replace(r"[^0-9.]", "", regex=True).replace("", np.nan),
        errors="coerce",
    )


def load_zones():
    z = pd.read_csv(ZONE, encoding="utf-8-sig")
    need = {"zone_id","subzone_code","subzone_name","planning_area_code","planning_area",
            "planning_region_code","planning_region"}
    miss = need - set(z.columns)
    if miss:
        raise ValueError(f"zone_dictionary 缺字段: {sorted(miss)}")
    z["planning_area_norm"] = z.planning_area.map(nn)
    return z


def load_control():
    df = pd.read_csv(T4, encoding="utf-8-sig", low_memory=False)
    label = df.columns[0]
    total = None
    for c in df.columns:
        cl = str(c).lower()
        if "total" in cl and "transport" not in cl and "mode" not in cl:
            if pd.to_numeric(df[c].astype(str).str.replace(",", "", regex=False),
                             errors="coerce").notna().mean() > 0.8:
                total = c
                break
    if total is None:
        raise ValueError("T4 无法识别就业总量列")
    rows = []
    for _, r in df.iterrows():
        name = nt(r[label]); v = num(r[total])
        if not name or name.upper() == "TOTAL" or pd.isna(v):
            continue
        rows.append((nn(name), float(v), nn(name) in SPECIAL))
    c = pd.DataFrame(rows, columns=["planning_area_norm", "workplace_employment", "is_special_destination"])
    return c.groupby(["planning_area_norm", "is_special_destination"], as_index=False).workplace_employment.sum()


def load_bridge():
    if not BRIDGE.exists():
        return None
    b = pd.read_csv(BRIDGE, encoding="utf-8-sig", low_memory=False)
    pc = next((c for c in b.columns if "postal" in str(c).lower()), None)
    sc = next((c for c in b.columns if "subzone_c" in str(c).lower()), None)
    if not pc or not sc:
        return None
    b["postal6"] = pd.to_numeric(b[pc], errors="coerce").astype("Int64").astype(str).replace("<NA>", "").str.zfill(6)
    b["subzone_code"] = b[sc].map(nt)
    return b[["postal6", "subzone_code"]].drop_duplicates()


def load_acra():
    need = {"uen","entity_type_description","entity_status_description","postal_code",
            "primary_ssic_description","no_of_officers"}
    frames = []
    for p in sorted(ACRA.glob("*.csv")):
        frames.append(pd.read_csv(p, encoding="utf-8-sig", low_memory=False,
                                  usecols=lambda c: c in need))
    a = pd.concat(frames, ignore_index=True)
    for c in a.columns:
        a[c] = a[c].map(nt)
    a["postal6"] = pd.to_numeric(a.postal_code, errors="coerce").astype("Int64").astype(str).replace("<NA>", "").str.zfill(6)
    st = a.entity_status_description.map(nn)
    active = ~st.str.contains(r"STRUCK OFF|DISSOLVED|CEASED|CANCELLED|LIQUIDATED|WOUND UP|TERMINATED", regex=True)
    off = pd.to_numeric(a.no_of_officers, errors="coerce").fillna(0)
    entity = a.entity_type_description.map(nn)
    ew = np.where(entity.str.contains(r"LOCAL COMPANY|PRIVATE|PUBLIC", regex=True), 1.15,
                  np.where(entity.str.contains(r"SOLE|PARTNERSHIP", regex=True), 0.9, 0.8))
    a["w"] = (active.astype(float)) * (1 + np.clip(np.log1p(off), 0, 3) * 0.2) * ew
    desc = a.primary_ssic_description.map(nn); sf = pd.Series(1.0, index=a.index)
    for pat, f in [(r"FINANC|BANK|INSURANCE",1.15),(r"PROFESSIONAL|INFORMATION|COMMUNICATION|TECHNOLOGY",1.10),
                   (r"MANUFACTUR|CONSTRUCTION|INDUSTR",1.05),(r"WHOLESALE|RETAIL|RESTAURANT|FOOD|ACCOMMODATION",1.02),
                   (r"EDUCATION|UNIVERSITY|SCHOOL",1.10),(r"HEALTH|MEDICAL|HOSPITAL|CLINIC",1.10),
                   (r"TRANSPORT|LOGISTICS|WAREHOUSE",1.05)]:
        sf.loc[desc.str.contains(pat, regex=True)] = f
    a["w"] *= sf
    b = load_bridge()
    if b is not None:
        a = a.merge(b, on="postal6", how="left")
    a["subzone_code"] = a.get("subzone_code", "").fillna("")
    return a


def acra_zone(a, z):
    x = a.merge(z[["subzone_code"]], on="subzone_code", how="inner")
    # 只返回 subzone_code + 统计量，避免 merge 回主表时列名冲突（_x/_y）。
    return x.groupby(["subzone_code"], as_index=False).agg(
        acra_enterprise_count=("uen", "nunique"),
        acra_activity_weight=("w", "sum"),
    )


def _prior_map(df):
    """类型 -> 先验层数；CSV 里空类型用 <empty> 占位，需映射回空串。"""
    m = {}
    for r in df.itertuples():
        tag = str(r.building_tag).strip().lower()
        if tag == "__default__":
            continue
        m["" if tag == "<empty>" else tag] = float(r.levels_prior)
    return m


def derive_level_prior(b):
    """由「有实测层数的同类型建筑」中位数推导先验层数（数据驱动，非拍脑袋）。"""
    exp = b[b["levels_explicit"].notna()]
    gmed = round(float(np.median(exp["levels_explicit"])), 1) if len(exp) else 3.0
    g = b.groupby("btype")["levels_explicit"].agg(n="count", med="median")
    rows = []
    for t, r in g.iterrows():
        n = int(r["n"])
        tag = t if t else "<empty>"
        if n >= PRIOR_MIN_N:
            rows.append((tag, round(float(r["med"]), 1), n, "observed_median",
                         "有实测层数同类型建筑的中位数"))
        else:
            rows.append((tag, gmed, n, "global_median_fallback",
                         f"样本 {n}<{PRIOR_MIN_N}，回退全局中位数"))
    rows.append(("__DEFAULT__", gmed, int(len(exp)), "global_median", "未列出的类型统一使用"))
    df = pd.DataFrame(rows, columns=["building_tag", "levels_prior", "n_explicit", "source", "note"])
    return df


def buildings():
    # 只读 ASCII 列，避免 other_tags 的非法字节触发 UTF-8 解码错误。
    b = gpd.read_file(BLDG, columns=["building", "building:l", "height", "geometry"])
    if b.crs is None:
        b = b.set_crs(4326)
    b = b.to_crs(3414)

    n_raw = len(b)
    b["btype"] = b["building"].map(lambda x: "" if pd.isna(x) else str(x).strip().lower())
    # 只保留真正的建筑多边形：building 标签非空，且排除 building=no。
    # 注意 osm-polygon 图层含大量非建筑大面（行政/水域/陆地轮廓，最大 653 km²），
    # 若不过滤会把全岛建筑 footprint 从 ~94 km² 虚增到 ~6,055 km²（约 64 倍）。
    keep = (b["btype"] != "") & (b["btype"] != "no")
    excluded_non_building = int((b["btype"] == "").sum())
    excluded_building_no = int((b["btype"] == "no").sum())
    b = b[keep].copy()

    b["footprint_m2"] = b.geometry.area

    lv_direct = _levels_series(b["building:l"]).where(lambda s: s > 0)
    lv_height = (_levels_series(b["height"]) / 3.2).where(lambda s: s > 0)
    b["levels_explicit"] = lv_direct.fillna(lv_height)

    # ---- 先验层数：优先读配置，缺失则从数据推导并落盘 ----
    if LEVEL_PRIOR.exists():
        p = pd.read_csv(LEVEL_PRIOR, encoding="utf-8-sig")
        pmap = _prior_map(p)
        pdef = float(p.loc[p.building_tag == "__DEFAULT__", "levels_prior"].iloc[0])
        prior_src = "config_file"
        prior_table = p
    else:
        prior_table = derive_level_prior(b)
        OUT.mkdir(parents=True, exist_ok=True)
        prior_table.to_csv(LEVEL_PRIOR, index=False, encoding="utf-8-sig")
        pmap = _prior_map(prior_table)
        pdef = float(prior_table.loc[prior_table.building_tag == "__DEFAULT__", "levels_prior"].iloc[0])
        prior_src = "derived_from_osm"

    b["levels_prior"] = b["btype"].map(pmap).fillna(pdef)
    b["levels"] = b["levels_explicit"].fillna(b["levels_prior"]).clip(*LEVEL_CLIP)
    b["levels_basis"] = np.where(b["levels_explicit"].notna(), "explicit", "type_prior")
    b["gfa_m2"] = b["footprint_m2"] * b["levels"]

    s = gpd.read_file(SUBZONE)[["SUBZONE_C", "geometry"]]
    if s.crs is None:
        s = s.set_crs(4326)
    s = s.to_crs(3414)
    s["subzone_code"] = s.SUBZONE_C.map(nt)

    # 建筑按其「代表点」归属唯一 Subzone（避免 intersect 跨区重复计数）。
    pts = b.copy()
    pts["geometry"] = b.geometry.representative_point()
    j = gpd.sjoin(pts[["footprint_m2", "gfa_m2", "levels", "levels_basis", "geometry"]],
                  s[["subzone_code", "geometry"]], predicate="within", how="inner")
    j = j.rename(columns={"subzone_code": "sz"})
    j["is_explicit"] = (j["levels_basis"] == "explicit").astype(float)

    buildings.stats = {
        "polygons_read": int(n_raw),
        "building_polygons": int(len(b)),
        "excluded_non_building": excluded_non_building,
        "excluded_building_no": excluded_building_no,
        "unassigned_polygons": int(len(b) - len(j)),
        "levels_source": {"explicit": int((b["levels_basis"] == "explicit").sum()),
                          "type_prior": int((b["levels_basis"] == "type_prior").sum())},
        "explicit_coverage": float((b["levels_basis"] == "explicit").mean()),
        "prior_table_source": prior_src,
        "total_footprint_m2": float(b["footprint_m2"].sum()),
        "total_gfa_m2": float(b["gfa_m2"].sum()),
        "mean_levels": float(b["levels"].mean()),
    }

    return j.groupby("sz", as_index=False).agg(
        building_count=("gfa_m2", "size"),
        building_footprint_m2=("footprint_m2", "sum"),
        building_gfa_m2=("gfa_m2", "sum"),
        mean_building_levels=("levels", "mean"),
        building_levels_explicit_share=("is_explicit", "mean"),
    ).rename(columns={"sz": "subzone_code"})


def load_lu_factor():
    """读取 landuse_class_mapping.csv，使用 employment_factor（33/33 全覆盖）。"""
    m = pd.read_csv(LU_MAP, encoding="utf-8-sig")
    m["LU_DESC"] = m["LU_DESC"].map(nn)
    f = dict(zip(m["LU_DESC"], m["employment_factor"].astype(float)))
    return f


def landuse():
    f = load_lu_factor()
    lu = gpd.read_file(LU, columns=["LU_DESC", "geometry"])
    if lu.crs is None:
        lu = lu.set_crs(4326)
    lu = lu.to_crs(3414)
    lu["cls"] = lu.LU_DESC.fillna("").map(nn)
    lu["factor"] = lu["cls"].map(f)
    unmatched = sorted(set(lu.loc[lu["factor"].isna(), "cls"].unique()))
    if unmatched:
        raise ValueError(f"landuse_class_mapping 未覆盖类别: {unmatched}")
    s = gpd.read_file(SUBZONE)[["SUBZONE_C", "geometry"]]
    if s.crs is None:
        s = s.set_crs(4326)
    s = s.to_crs(3414)
    s["subzone_code"] = s.SUBZONE_C.map(nt)
    i = gpd.overlay(lu[["cls", "factor", "geometry"]], s[["subzone_code", "geometry"]],
                    how="intersection", keep_geom_type=True)
    i["area_m2"] = i.geometry.area
    i["weighted_area"] = i["area_m2"] * i["factor"]
    landuse.classes_matched = int(lu["cls"].nunique())
    return i.groupby("subzone_code", as_index=False).agg(
        landuse_area_m2=("area_m2", "sum"),
        landuse_weighted_area=("weighted_area", "sum"),
    )


def poi():
    p = pd.read_csv(POI, encoding="utf-8-sig", low_memory=False)
    p["subzone_code"] = p.SUBZONE_C.map(nt)
    p["poi_activity_weight"] = 0.0
    for tag, w in POI_W.items():
        cols = [c for c in p.columns if str(c).strip().lower() == tag]
        for c in cols:
            p.loc[p[c].astype(str).str.lower().eq("true"), "poi_activity_weight"] += w
    valid = p.subzone_code.str.len() > 0
    p.loc[valid & (p.poi_activity_weight <= 0), "poi_activity_weight"] = 0.05
    key = "place_id" if "place_id" in p.columns else "subzone_code"
    return p.groupby("subzone_code", as_index=False).agg(
        poi_count=(key, "nunique"),
        poi_activity_weight=("poi_activity_weight", "sum"),
    )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--project-root", type=Path, default=ROOT)
    args = ap.parse_args()
    root = args.project_root
    global DATA, ZONE, PROD, T4, LU, BLDG, POI, ACRA, SUBZONE, BRIDGE, OUT, LU_MAP, LEVEL_PRIOR
    DATA = root / "Singapore_OD_MATSim_FinalData"
    ZONE = root / "reports/od_zone/zone_dictionary.csv"
    PROD = root / "reports/od_production/production.csv"
    T4 = DATA / "03_Workplace_Employment/outputFile (3)__T4.csv"
    LU = DATA / "04_LandUse_Building/MasterPlan2019LandUselayer.geojson"
    BLDG = DATA / "07_RoadNetwork/osm-polygon_expanded.shp"
    POI = DATA / "05_POI_Enterprise/poi.csv"
    ACRA = DATA / "05_POI_Enterprise/ACRA"
    SUBZONE = DATA / "01_Boundary_TAZ/MasterPlan2019SubzoneBoundaryNoSeaGEOJSON.geojson"
    BRIDGE = root / "reports/od_audit/_postal_subzone_bridge.csv"
    LU_MAP = root / "reports/od_attraction_v2/landuse_class_mapping.csv"
    OUT = root / "reports/od_attraction_v21"
    LEVEL_PRIOR = OUT / "building_level_prior.csv"

    out = OUT
    out.mkdir(parents=True, exist_ok=True)

    z = load_zones(); control = load_control()
    a = acra_zone(load_acra(), z); b = buildings(); l = landuse(); p = poi()

    z = z.merge(control[~control.is_special_destination][["planning_area_norm", "workplace_employment"]],
                on="planning_area_norm", how="left")
    for df in (a, b, l, p):
        z = z.merge(df, on="subzone_code", how="left")

    numeric = ["workplace_employment","acra_enterprise_count","acra_activity_weight","building_count",
               "building_footprint_m2","building_gfa_m2","mean_building_levels","building_levels_explicit_share",
               "landuse_area_m2","landuse_weighted_area","poi_count","poi_activity_weight"]
    for c in numeric:
        z[c] = pd.to_numeric(z[c], errors="coerce").fillna(0)

    # ---- A. log1p + PA 求和归一化（无 min-max、无 0.05 floor）----
    z["acra_log"] = np.log1p(z["acra_activity_weight"].clip(lower=0))
    z["gfa_log"] = np.log1p(z["building_gfa_m2"].clip(lower=0))
    z["landuse_log"] = np.log1p(z["landuse_weighted_area"].clip(lower=0))
    z["poi_log"] = np.log1p(z["poi_activity_weight"].clip(lower=0))
    gkey = z["planning_area_norm"]
    for comp, col in [("acra", "acra_log"), ("gfa", "gfa_log"),
                      ("landuse", "landuse_log"), ("poi", "poi_log")]:
        tot = z[col].groupby(gkey).transform("sum")
        z[f"{comp}_component"] = np.where(tot > 0, z[col] / tot.replace(0, np.nan), 0.0)

    z["attraction_weight_raw"] = (W_ACRA * z.acra_component + W_GFA * z.gfa_component
                                  + W_LU * z.landuse_component + W_POI * z.poi_component)

    totW = z["attraction_weight_raw"].groupby(gkey).transform("sum")
    ctrl = z["workplace_employment"].groupby(gkey).transform("max")
    need_fb = (totW <= 0) & (ctrl > 0)
    if need_fb.any():
        fb = np.log1p(z["landuse_area_m2"].clip(lower=0))
        fbtot = fb.groupby(gkey).transform("sum")
        fb_share = np.where(fbtot > 0, fb / fbtot.replace(0, np.nan), 0.0)
        n = z["zone_id"].groupby(gkey).transform("count")
        fb_share = np.where(fb_share > 0, fb_share, 1.0 / n)
        z["attraction_share_within_pa"] = np.where(need_fb, fb_share,
                                                   np.where(totW > 0, z["attraction_weight_raw"] / totW.replace(0, np.nan), 0.0))
    else:
        z["attraction_share_within_pa"] = np.where(totW > 0, z["attraction_weight_raw"] / totW.replace(0, np.nan), 0.0)

    z["workplace_attraction"] = z["workplace_employment"] * z["attraction_share_within_pa"]
    z["weight_fallback_used"] = need_fb
    z["acra_zero_positive"] = (z["acra_activity_weight"] <= 0) & (z["workplace_attraction"] > 1e-9)
    z["gfa_zero_positive"] = (z["building_gfa_m2"] <= 0) & (z["workplace_attraction"] > 1e-9)
    # 只在「有就业控制量的 PA」内统计单区集中度（居住端 PA 无就业，份额无意义）
    z["share_over_50pct"] = (z["workplace_employment"] > 0) & (z["attraction_share_within_pa"] > 0.5)
    z["share_over_60pct"] = (z["workplace_employment"] > 0) & (z["attraction_share_within_pa"] > 0.6)
    z["sample_zone"] = z["planning_area"] if False else ""

    g = z.groupby("planning_area_norm")
    val = g.agg(census_control=("workplace_employment", "first"),
                attraction_sum=("workplace_attraction", "sum"),
                max_zone_share=("attraction_share_within_pa", "max"),
                n_zones=("zone_id", "count"),
                zero_acra_positive=("acra_zero_positive", "sum")).reset_index()
    val["difference"] = val["attraction_sum"] - val["census_control"]
    val["relative_error"] = np.where(val["census_control"] > 0, val["difference"].abs() / val["census_control"], 0)

    z.to_csv(out / "attraction_v21.csv", index=False, encoding="utf-8-sig")
    val.to_csv(out / "attraction_v21_pa_validation.csv", index=False, encoding="utf-8-sig")
    z[z.share_over_50pct | z.acra_zero_positive].sort_values(
        "workplace_attraction", ascending=False).to_csv(
        out / "attraction_v21_suspicious.csv", index=False, encoding="utf-8-sig")
    control[control.is_special_destination].to_csv(
        out / "special_workplace_destinations.csv", index=False, encoding="utf-8-sig")

    summary = {
        "status": "PASS" if float(val.relative_error.max()) <= 1e-8 else "WARN",
        "version": "v2.1",
        "normalization": "log1p + PA-sum (no min-max, no 0.05 floor)",
        "weights": {"acra": W_ACRA, "building_gfa": W_GFA, "landuse": W_LU, "poi": W_POI},
        "landuse_mapping": str(LU_MAP.name),
        "landuse_classes_matched": int(getattr(landuse, "classes_matched", 0)),
        "zones": len(z),
        "physical_workplace_pa": int((~control.is_special_destination).sum()),
        "special_workplace_nodes": int(control.is_special_destination.sum()),
        "census_physical_control_total": float(control.loc[~control.is_special_destination, "workplace_employment"].sum()),
        "attraction_total": float(z["workplace_attraction"].sum()),
        "max_pa_abs_error": float(val["difference"].abs().max()),
        "max_pa_relative_error": float(val["relative_error"].max()),
        "zero_acra_positive_zones": int(z["acra_zero_positive"].sum()),
        "zero_gfa_positive_zones": int(z["gfa_zero_positive"].sum()),
        "zero_attraction_zones": int((z["workplace_attraction"] <= 1e-12).sum()),
        "zone_share_over_50pct": int(z["share_over_50pct"].sum()),
        "zone_share_over_60pct": int(z["share_over_60pct"].sum()),
        "weight_fallback_zones": int(z["weight_fallback_used"].sum()),
        "building_levels": getattr(buildings, "stats", {}),
    }
    (out / "attraction_v21_validation.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print("=" * 72); print("Step 3B.1 | Attraction v2.1"); print(json.dumps(summary, ensure_ascii=False, indent=2))
    print("OUTPUT:", out); print("=" * 72)


if __name__ == "__main__":
    main()
