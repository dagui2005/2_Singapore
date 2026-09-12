#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Step 3B: Census-controlled workplace attraction for 332 Subzones."""
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
# 注意：用 expanded 版（building:l / height 已是独立列），可绕开 osm-polygon.dbf
# 中 other_tags 字段的 UTF-8 解码失败问题（GDAL 只取 ASCII 列即可）。
BLDG = DATA / "07_RoadNetwork/osm-polygon_expanded.shp"
POI = DATA / "05_POI_Enterprise/poi.csv"
ACRA = DATA / "05_POI_Enterprise/ACRA"
SUBZONE = DATA / "01_Boundary_TAZ/MasterPlan2019SubzoneBoundaryNoSeaGEOJSON.geojson"
BRIDGE = ROOT / "reports/od_audit/_postal_subzone_bridge.csv"
SPECIAL = {"OTHER PLANNING AREAS OR OUTSIDE SINGAPORE","NO FIXED LOCATION FOR WORK","WORKS FROM HOME"}
LU_FACTOR = {
    "WATERBODY":0.0,"ROAD":0.0,"PARK":0.05,"OPEN SPACE":0.05,"RESERVE SITE":0.10,
    "AGRICULTURE":0.10,"CEMETERY":0.05,"BEACH":0.05,"RESIDENTIAL":0.15,
    "RESIDENTIAL WITH COMMERCIAL AT 1ST STOREY":0.75,"RESIDENTIAL / INSTITUTION":0.55,
    "COMMERCIAL":1.0,"COMMERCIAL & RESIDENTIAL":0.9,"BUSINESS 1":1.15,"BUSINESS 2":1.15,
    "BUSINESS PARK":1.25,"BUSINESS PARK-WHITE":1.2,"B1-WHITE":1.1,"B2-WHITE":1.1,
    "WHITE":1.0,"INDUSTRIAL":1.1,"LIGHT INDUSTRIAL":1.1,"GENERAL INDUSTRIAL":1.1,
    "PORT":1.1,"AIRPORT":1.15,"PORT-AIRPORT":1.15,"TRANSPORT FACILITIES":0.8,
    "SPECIAL USE":0.5,"PLACE OF WORSHIP":0.35,"HEALTH & MEDICAL CARE":1.0,
    "EDUCATIONAL INSTITUTION":1.0,"CIVIC & COMMUNITY INSTITUTION":0.75,"SPORTS & RECREATION":0.5,
}
POI_W = {"office":1.0,"bank":1.1,"finance":1.1,"company":0.7,"shopping_mall":1.0,"supermarket":0.6,
         "food":0.25,"restaurant":0.25,"lodging":0.45,"hospital":1.0,"health":0.75,
         "school":0.75,"university":1.0,"transit_station":0.5}

def nt(x):
    if pd.isna(x): return ""
    return re.sub(r"\s+"," ",str(x).replace("\xa0"," ").strip())
def nn(x): return nt(x).upper()
def num(x):
    return pd.to_numeric(pd.Series([x]).astype(str).str.replace(",","",regex=False),errors="coerce").iloc[0]
def norm(s):
    s=s.astype(float)
    if len(s)==0:return s
    a,b=float(s.min()),float(s.max())
    if b<=a:return pd.Series(1.0,index=s.index)
    return (s-a)/(b-a)+0.05

def load_zones():
    z=pd.read_csv(ZONE,encoding="utf-8-sig")
    need={"zone_id","subzone_code","subzone_name","planning_area_code","planning_area","planning_region_code","planning_region"}
    miss=need-set(z.columns)
    if miss: raise ValueError(f"zone_dictionary 缺字段: {sorted(miss)}")
    z["planning_area_norm"]=z.planning_area.map(nn)
    return z

def load_control():
    df=pd.read_csv(T4,encoding="utf-8-sig",low_memory=False)
    label=df.columns[0]
    total=None
    for c in df.columns:
        cl=str(c).lower()
        if "total" in cl and "transport" not in cl and "mode" not in cl:
            if pd.to_numeric(df[c].astype(str).str.replace(",","",regex=False),errors="coerce").notna().mean()>0.8:
                total=c;break
    if total is None:
        raise ValueError("T4 无法识别就业总量列")
    rows=[]
    for _,r in df.iterrows():
        name=nt(r[label]); v=num(r[total])
        if not name or name.upper()=="TOTAL" or pd.isna(v): continue
        rows.append((nn(name),float(v),nn(name) in SPECIAL))
    c=pd.DataFrame(rows,columns=["planning_area_norm","workplace_employment","is_special_destination"])
    return c.groupby(["planning_area_norm","is_special_destination"],as_index=False).workplace_employment.sum()

def load_bridge():
    if not BRIDGE.exists(): return None
    b=pd.read_csv(BRIDGE,encoding="utf-8-sig",low_memory=False)
    pc=next((c for c in b.columns if "postal" in str(c).lower()),None)
    sc=next((c for c in b.columns if "subzone_c" in str(c).lower()),None)
    if not pc or not sc:return None
    b["postal6"]=pd.to_numeric(b[pc],errors="coerce").astype("Int64").astype(str).replace("<NA>","").str.zfill(6)
    b["subzone_code"]=b[sc].map(nt)
    return b[["postal6","subzone_code"]].drop_duplicates()

def load_acra():
    need={"uen","entity_type_description","entity_status_description","postal_code","primary_ssic_description","no_of_officers"}
    frames=[]
    for p in sorted(ACRA.glob("*.csv")):
        frames.append(pd.read_csv(p,encoding="utf-8-sig",low_memory=False,usecols=lambda c:c in need))
    a=pd.concat(frames,ignore_index=True)
    for c in a.columns:a[c]=a[c].map(nt)
    a["postal6"]=pd.to_numeric(a.postal_code,errors="coerce").astype("Int64").astype(str).replace("<NA>","").str.zfill(6)
    st=a.entity_status_description.map(nn)
    active=~st.str.contains(r"STRUCK OFF|DISSOLVED|CEASED|CANCELLED|LIQUIDATED|WOUND UP|TERMINATED",regex=True)
    off=pd.to_numeric(a.no_of_officers,errors="coerce").fillna(0)
    entity=a.entity_type_description.map(nn)
    ew=np.where(entity.str.contains(r"LOCAL COMPANY|PRIVATE|PUBLIC",regex=True),1.15,np.where(entity.str.contains(r"SOLE|PARTNERSHIP",regex=True),0.9,0.8))
    a["w"]=(active.astype(float))*(1+np.clip(np.log1p(off),0,3)*0.2)*ew
    desc=a.primary_ssic_description.map(nn); sf=pd.Series(1.0,index=a.index)
    for pat,f in [(r"FINANC|BANK|INSURANCE",1.15),(r"PROFESSIONAL|INFORMATION|COMMUNICATION|TECHNOLOGY",1.10),(r"MANUFACTUR|CONSTRUCTION|INDUSTR",1.05),(r"WHOLESALE|RETAIL|RESTAURANT|FOOD|ACCOMMODATION",1.02),(r"EDUCATION|UNIVERSITY|SCHOOL",1.10),(r"HEALTH|MEDICAL|HOSPITAL|CLINIC",1.10),(r"TRANSPORT|LOGISTICS|WAREHOUSE",1.05)]: sf.loc[desc.str.contains(pat,regex=True)]=f
    a["w"]*=sf
    b=load_bridge()
    if b is not None:a=a.merge(b,on="postal6",how="left")
    a["subzone_code"]=a.get("subzone_code","").fillna("")
    return a

def acra_zone(a,z):
    x=a.merge(z[["subzone_code"]],on="subzone_code",how="inner")
    # 注意：只能返回 subzone_code + 统计量。
    # 若返回 zone_id / planning_area_norm，merge 回 z 时会与已有列冲突（_x/_y）。
    return x.groupby(["subzone_code"],as_index=False).agg(acra_enterprise_count=("uen","nunique"),acra_activity_weight=("w","sum"))

def parse_levels(s):
    if not isinstance(s,str) or not s:return np.nan
    for key in ("building:levels","levels"):
        m=re.search(rf'"{re.escape(key)}"\s*=>\s*"([^"]+)"',s)
        if m:
            t=re.sub(r"[^0-9.]","",m.group(1))
            if t:
                try:return float(t)
                except ValueError:pass
    m=re.search(r'"height"\s*=>\s*"([^"]+)"',s)
    if m:
        t=re.sub(r"[^0-9.]","",m.group(1))
        if t:
            try:return max(1,float(t)/3.2)
            except ValueError:pass
    return np.nan

def _levels_series(s):
    return pd.to_numeric(
        s.astype(str).str.replace(r"[^0-9.]", "", regex=True).replace("", np.nan),
        errors="coerce",
    )


def buildings():
    # 只读 ASCII 列，避免 other_tags 的非法字节触发 UTF-8 解码错误。
    b = gpd.read_file(
        BLDG,
        columns=["building", "building:l", "height", "geometry"],
    )
    if b.crs is None:
        b = b.set_crs(4326)
    b = b.to_crs(3414)
    b["footprint_m2"] = b.geometry.area

    # building:l == OSM building:levels（SHP 字段名 10 字符截断）
    lv_direct = _levels_series(b["building:l"])
    lv_direct = lv_direct.where(lv_direct > 0)
    # 回退：height / 3.2 m 每层
    lv_height = _levels_series(b["height"]) / 3.2
    lv_height = lv_height.where(lv_height > 0)

    b["levels_source"] = np.where(
        lv_direct.notna(),
        "building:levels",
        np.where(lv_height.notna(), "height/3.2", "default_1"),
    )
    # 缺失时保守按 1 层（用户既定口径）
    b["levels"] = lv_direct.fillna(lv_height).fillna(1.0).clip(1, 80)
    b["gfa_m2"] = b["footprint_m2"] * b["levels"]

    buildings.stats = {
        "building_polygons": int(len(b)),
        "levels_from_osm": int((b["levels_source"] == "building:levels").sum()),
        "levels_from_height": int((b["levels_source"] == "height/3.2").sum()),
        "levels_default_1": int((b["levels_source"] == "default_1").sum()),
        "levels_coverage": float((b["levels_source"] != "default_1").mean()),
    }

    s = gpd.read_file(SUBZONE)[["SUBZONE_C", "geometry"]]
    if s.crs is None:
        s = s.set_crs(4326)
    s = s.to_crs(3414)
    s["subzone_code"] = s.SUBZONE_C.map(nt)
    j = gpd.sjoin(
        b[["footprint_m2", "gfa_m2", "levels", "geometry"]],
        s[["subzone_code", "geometry"]],
        predicate="intersects",
        how="inner",
    )
    return j.groupby("subzone_code", as_index=False).agg(
        building_count=("gfa_m2", "size"),
        building_footprint_m2=("footprint_m2", "sum"),
        building_gfa_m2=("gfa_m2", "sum"),
        mean_building_levels=("levels", "mean"),
    )

def landuse():
    lu=gpd.read_file(LU,columns=["LU_DESC","geometry"])
    if lu.crs is None:lu=lu.set_crs(4326)
    lu=lu.to_crs(3414); lu["cls"]=lu.LU_DESC.fillna("").map(nn); lu["factor"]=lu.cls.map(lambda x:LU_FACTOR.get(x,0.20))
    s=gpd.read_file(SUBZONE)[["SUBZONE_C","geometry"]]
    if s.crs is None:s=s.set_crs(4326)
    s=s.to_crs(3414); s["subzone_code"]=s.SUBZONE_C.map(nt)
    i=gpd.overlay(lu[["cls","factor","geometry"]],s[["subzone_code","geometry"]],how="intersection",keep_geom_type=True)
    i["area_m2"]=i.geometry.area; i["weighted_area"]=i.area_m2*i.factor
    return i.groupby("subzone_code",as_index=False).agg(landuse_area_m2=("area_m2","sum"),landuse_weighted_area=("weighted_area","sum"))

def poi():
    p=pd.read_csv(POI,encoding="utf-8-sig",low_memory=False); p["subzone_code"]=p.SUBZONE_C.map(nt); p["poi_activity_weight"]=0.0
    for tag,w in POI_W.items():
        cols=[c for c in p.columns if str(c).strip().lower()==tag]
        for c in cols:p.loc[p[c].astype(str).str.lower().eq("true"),"poi_activity_weight"]+=w
    valid=p.subzone_code.str.len()>0; p.loc[valid & (p.poi_activity_weight<=0),"poi_activity_weight"]=0.05
    key="place_id" if "place_id" in p.columns else "subzone_code"
    return p.groupby("subzone_code",as_index=False).agg(poi_count=(key,"nunique"),poi_activity_weight=("poi_activity_weight","sum"))

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--project-root",type=Path,default=ROOT); args=ap.parse_args(); root=args.project_root
    global DATA,ZONE,PROD,T4,LU,BLDG,POI,ACRA,SUBZONE,BRIDGE
    DATA=root/DATA_DIR_NAME if False else root/"Singapore_OD_MATSim_FinalData"
    ZONE=root/"reports/od_zone/zone_dictionary.csv"; PROD=root/"reports/od_production/production.csv"; T4=DATA/"03_Workplace_Employment/outputFile (3)__T4.csv"; LU=DATA/"04_LandUse_Building/MasterPlan2019LandUselayer.geojson"; BLDG=DATA/"07_RoadNetwork/osm-polygon_expanded.shp"; POI=DATA/"05_POI_Enterprise/poi.csv"; ACRA=DATA/"05_POI_Enterprise/ACRA"; SUBZONE=DATA/"01_Boundary_TAZ/MasterPlan2019SubzoneBoundaryNoSeaGEOJSON.geojson"; BRIDGE=root/"reports/od_audit/_postal_subzone_bridge.csv"
    out=root/"reports/od_attraction_v2"; out.mkdir(parents=True,exist_ok=True)
    z=load_zones(); control=load_control(); a=acra_zone(load_acra(),z); b=buildings(); l=landuse(); p=poi()
    z=z.merge(control[~control.is_special_destination][["planning_area_norm","workplace_employment"]],on="planning_area_norm",how="left")
    for df in (a,b,l,p):z=z.merge(df,on="subzone_code",how="left")
    numeric=["workplace_employment","acra_enterprise_count","acra_activity_weight","building_count","building_footprint_m2","building_gfa_m2","mean_building_levels","landuse_area_m2","landuse_weighted_area","poi_count","poi_activity_weight"]
    for c in numeric:z[c]=pd.to_numeric(z[c],errors="coerce").fillna(0)
    g=z.groupby("planning_area_norm")
    z["acra_component"]=g.acra_activity_weight.transform(norm); z["gfa_component"]=g.building_gfa_m2.transform(norm); z["landuse_component"]=g.landuse_weighted_area.transform(norm); z["poi_component"]=g.poi_activity_weight.transform(norm)
    z["attraction_weight_raw"]=0.55*z.acra_component+0.30*z.gfa_component+0.10*z.landuse_component+0.05*z.poi_component
    noacra=g.acra_activity_weight.transform("sum")<=0; z.loc[noacra,"attraction_weight_raw"]=0.75*z.loc[noacra,"gfa_component"]+0.20*z.loc[noacra,"landuse_component"]+0.05*z.loc[noacra,"poi_component"]
    nogfa=g.building_gfa_m2.transform("sum")<=0; z.loc[nogfa,"attraction_weight_raw"]=0.70*z.loc[nogfa,"acra_component"]+0.20*z.loc[nogfa,"landuse_component"]+0.10*z.loc[nogfa,"poi_component"]
    s=g.attraction_weight_raw.transform("sum"); z["attraction_share_within_pa"]=np.where(s>0,z.attraction_weight_raw/s,0); z["workplace_attraction"]=z.workplace_employment*z.attraction_share_within_pa
    z["acra_zero_positive"]= (z.acra_activity_weight<=0)&(z.workplace_attraction>1e-9); z["share_over_50pct"]=z.attraction_share_within_pa>0.5
    val=g.agg(census_control=("workplace_employment","first"),attraction_sum=("workplace_attraction","sum"),max_zone_share=("attraction_share_within_pa","max"),n_zones=("zone_id","count"),zero_acra_positive=("acra_zero_positive","sum")).reset_index(); val["difference"]=val.attraction_sum-val.census_control; val["relative_error"]=np.where(val.census_control>0,val.difference.abs()/val.census_control,0)
    z.to_csv(out/"attraction_v2.csv",index=False,encoding="utf-8-sig"); val.to_csv(out/"attraction_v2_pa_validation.csv",index=False,encoding="utf-8-sig"); z[z.share_over_50pct|z.acra_zero_positive].sort_values("workplace_attraction",ascending=False).to_csv(out/"attraction_v2_suspicious.csv",index=False,encoding="utf-8-sig"); control[control.is_special_destination].to_csv(out/"special_workplace_destinations.csv",index=False,encoding="utf-8-sig")
    summary={"status":"PASS" if float(val.relative_error.max())<=1e-8 else "WARN","zones":len(z),"physical_workplace_pa":int((~control.is_special_destination).sum()),"special_workplace_nodes":int(control.is_special_destination.sum()),"census_physical_control_total":float(control.loc[~control.is_special_destination,"workplace_employment"].sum()),"attraction_total":float(z.workplace_attraction.sum()),"max_pa_abs_error":float(val.difference.abs().max()),"max_pa_relative_error":float(val.relative_error.max()),"acra_total":int(len(load_acra())),"zero_acra_positive_zones":int(z.acra_zero_positive.sum()),"zone_share_over_50pct":int(z.share_over_50pct.sum()),"weights":{"acra":0.55,"building_gfa":0.30,"landuse":0.10,"poi":0.05}}
    summary["building_levels"]=getattr(buildings,"stats",{})
    (out/"attraction_v2_validation.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding="utf-8")
    print("="*72); print("Step 3B | Attraction v2"); print(summary); print("OUTPUT:",out); print("="*72)

if __name__=="__main__": main()
