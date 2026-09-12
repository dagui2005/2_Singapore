#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Step 6.3.2  (corrected)
Build a traffic-volume comparison crosswalk at LTA road-section level.

Why this file was corrected (vs. the first draft):
    The first draft matched each LTA section to every edge within a
    centroid radius (120 m) plus every same-name edge within 250 m, then
    SUMMED their simulated flow.  For Singapore that produced ~77 edges
    per LTA section (max 264) and a headline sim/obs ratio of ~16.9 --
    an artifact of (a) over-inclusion of parallel / opposite / neighbouring
    edges and (b) summing a *cross-section* flow over a set of *sequential*
    edges (flow is conserved along a corridor, so sum = flow x n_edges).

    Correct logic for a point-count (LTA Volume = vehicles/hour passing a
    location):
        1. Candidate set = edges lying along the section's OWN geometry
           (sampled along the polyline) with a CONSISTENT road name.
        2. Section flow = a REPRESENTATIVE single value over those edges
           (median, primary; mean/max/sum kept as diagnostics).
    Summing LTA sections is also invalid because a vehicle is counted once
    per station it passes -- only per-section (per-point) comparison is valid.

Outputs (reports/matsim_assignment_6_3_2/):
    lta_section_matsim_crosswalk.csv
    section_flow_comparison_lambda_*.csv
    section_flow_by_roadcat_lambda_*.csv
    section_flow_comparison_summary.csv
    step6_3_2_validation.json

It does NOT modify OD, network, population, lambda, or MATSim outputs.
"""

from __future__ import annotations
import argparse, gzip, json, math, re
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
from scipy.spatial import cKDTree

ROOT_DEFAULT=Path(r"D:\Luan\2026-05\2_Singapore")
FLOW=Path("Singapore_OD_MATSim_FinalData/08_TrafficCount/TrafficFlow_Data.json")
LTA_GEOM_CANDIDATES=[
    Path("Singapore_OD_MATSim_FinalData/08_TrafficCount/TrafficFlow_Links.shp"),
    Path("Dynamic_2026_03_16/historical_data/TrafficSpeedBands_Links.shp"),
]
NETWORK=Path("reports/matsim_network/network_links_source_copy.csv")
NODES=Path("reports/matsim_network/network_nodes_source_copy.csv")
ASSIGN_DIR=Path("reports/matsim_assignment")
OUT=Path("reports/matsim_assignment_6_3_2")

# tight (corrected) defaults
TIGHT_RADIUS_M=45.0
SAMPLE_STEP_M=25.0
# generous (first-draft) parameters, kept for the diagnostic comparison
GEN_CORRIDOR_RADIUS_M=120.0
GEN_NAME_RADIUS_M=250.0

DEFAULT_SCALE=459794.0/200000.0


def norm(x):
    if x is None or pd.isna(x):
        return ""
    s=re.sub(r"[^A-Z0-9 ]+"," ",str(x).upper().strip())
    repl={"AVENUE":"AVE","STREET":"ST","ROAD":"RD",
          "JUNCTION":"JCT","EXPRESSWAY":"EXPY","CENTRAL":"CTRL"}
    for a,b in repl.items():
        s=re.sub(rf"\b{a}\b",b,s)
    return re.sub(r"\s+"," ",s).strip()


def name_consistent(a,b):
    """True if two normalised road names are compatible (either direction)."""
    if not a or not b:
        return False
    return a==b or a in b or b in a


def find_lta(root):
    for p in LTA_GEOM_CANDIDATES:
        q=root/p
        if q.exists():
            return q
    raise FileNotFoundError("找不到 LTA traffic/speed section geometry")


def load_network(root):
    e=pd.read_csv(root/NETWORK,encoding="utf-8-sig",low_memory=False)
    n=pd.read_csv(root/NODES,encoding="utf-8-sig",low_memory=False)
    for c in ["from_node","to_node"]:
        e[c]=pd.to_numeric(e[c]).astype(int)
    n["node_id"]=pd.to_numeric(n["node_id"]).astype(int)
    e=e.merge(n.rename(columns={"node_id":"from_node","x_svy21_m":"from_x","y_svy21_m":"from_y"}),
              on="from_node",how="left")
    e=e.merge(n.rename(columns={"node_id":"to_node","x_svy21_m":"to_x","y_svy21_m":"to_y"}),
              on="to_node",how="left")
    e["mid_x"]=(e.from_x+e.to_x)/2
    e["mid_y"]=(e.from_y+e.to_y)/2
    e["matsim_link_id"]="e"+e.from_node.astype(str)+"_"+e.to_node.astype(str)
    e["name_norm"]=e["name"].map(norm) if "name" in e.columns else ""
    e["name_norm"]=e["name_norm"].fillna("")
    return e.reset_index(drop=True)


def load_lta(root):
    p=find_lta(root)
    g=gpd.read_file(p,columns=["LinkID","RoadName","RoadCat","geometry"])
    if g.crs is None:
        g=g.set_crs("EPSG:4326")
    g=g.to_crs("EPSG:3414")
    g["LinkID"]=g["LinkID"].astype(str).str.strip()
    g["name_norm"]=g["RoadName"].map(norm)
    return g


def load_obs(root):
    with (root/FLOW).open("r",encoding="utf-8") as f:
        obj=json.load(f)
    rows=obj.get("Value",obj if isinstance(obj,list) else obj.get("value",[]))
    d=pd.DataFrame(rows)
    req={"LinkID","Date","HourOfDate","Volume"}
    miss=req-set(d.columns)
    if miss:
        raise ValueError(f"TrafficFlow 缺字段: {sorted(miss)}")
    d["LinkID"]=d["LinkID"].astype(str).str.strip()
    d["Date"]=pd.to_datetime(d["Date"],dayfirst=True,errors="coerce")
    d["HourOfDate"]=pd.to_numeric(d["HourOfDate"],errors="coerce")
    d["Volume"]=pd.to_numeric(d["Volume"].astype(str).str.replace(",","",regex=False),errors="coerce")
    d=d[d["Date"].notna() & d["Date"].dt.weekday.lt(5) & d["HourOfDate"].isin([7,8])].copy()
    day=d.groupby(["LinkID","Date","HourOfDate"],as_index=False)["Volume"].mean()
    med=day.groupby(["LinkID","HourOfDate"],as_index=False)["Volume"].median()
    w=med.pivot(index="LinkID",columns="HourOfDate",values="Volume").reset_index()
    if 7 in w.columns: w=w.rename(columns={7:"obs_h7"})
    if 8 in w.columns: w=w.rename(columns={8:"obs_h8"})
    for c in ["obs_h7","obs_h8"]:
        if c not in w.columns: w[c]=0.0
    w["obs_h7"]=w["obs_h7"].fillna(0)
    w["obs_h8"]=w["obs_h8"].fillna(0)
    w["obs_am"]=w["obs_h7"]+w["obs_h8"]
    return w


def load_linkstats(root,lam):
    tag=f"{lam:.3f}".replace(".","p")
    files=list((root/ASSIGN_DIR).rglob("*.linkstats.txt.gz"))
    files=[p for p in files if f"0p{int(round(lam*1000)):03d}" in str(p).replace(".","p") or f"lambda_{tag}" in str(p)]
    if not files:
        raise FileNotFoundError(f"找不到 lambda={lam} 的 linkstats")
    path=sorted(files,key=lambda p: ("it.0" not in str(p).lower(),len(str(p))))[0]
    with gzip.open(path,"rt",encoding="latin-1",errors="replace") as f:
        header=f.readline().rstrip("\n").split("\t")
    want=["LINK","HRS7-8avg","HRS8-9avg","TRAVELTIME7-8avg","TRAVELTIME8-9avg"]
    pos={c:i for i,c in enumerate(header) if c in want}
    if "LINK" not in pos:
        raise ValueError("linkstats 缺 LINK")
    use=sorted(pos.values())
    df=pd.read_csv(path,sep="\t",usecols=use,compression="gzip",encoding="latin-1",low_memory=False)
    rename={df.columns[use.index(i)]:c for c,i in pos.items()}
    df=df.rename(columns=rename)
    for c in want[1:]:
        if c in df.columns:
            df[c]=pd.to_numeric(df[c],errors="coerce")
    df["LINK"]=df["LINK"].astype(str)
    return df,path


def _longest_line(geom):
    """Return the longest LineString of a (Multi)LineString/Polygon geometry."""
    if geom is None:
        return None
    t=geom.geom_type
    if t=="LineString":
        return geom
    if t in ("MultiLineString","GeometryCollection"):
        geoms=[g for g in geom.geoms if g.geom_type=="LineString" and g.length>0]
        return max(geoms,key=lambda g:g.length) if geoms else None
    if t=="Polygon":
        return geom.exterior
    return None


def build_crosswalk(edges,lta,obs_links,radius,sample_step):
    """Corrected crosswalk: sample points along each section's own polyline,
    keep edges whose mid-point is within `radius` AND whose road name is
    consistent with the section (geometry-only fallback for unnamed roads)."""
    lta=lta[lta.LinkID.isin(obs_links)].copy()
    tree=cKDTree(edges[["mid_x","mid_y"]].to_numpy(float))
    e_nn=edges["name_norm"].to_numpy()
    rows=[]
    for _,r in lta.iterrows():
        line=_longest_line(r.geometry)
        if line is None or line.length<=0:
            continue
        nn=r["name_norm"]
        k=max(2,int(line.length//sample_step)+1)
        cand=set()
        for t in range(k+1):
            pt=line.interpolate(t/k,normalized=True)
            for j in tree.query_ball_point([pt.x,pt.y],r=radius):
                j=int(j)
                if nn:
                    if name_consistent(nn,e_nn[j]):
                        cand.add(j)
                else:
                    cand.add(j)
        # fallback for named sections that found nothing: geometry only
        if nn and not cand:
            for t in range(k+1):
                pt=line.interpolate(t/k,normalized=True)
                for j in tree.query_ball_point([pt.x,pt.y],r=radius):
                    cand.add(int(j))
        mid=line.centroid
        for j in cand:
            e=edges.iloc[j]
            rows.append({"LinkID":r.LinkID,"osm_edge_index":int(j),
                         "matsim_link_id":e.matsim_link_id,
                         "distance_m":float(math.hypot(e.mid_x-mid.x,e.mid_y-mid.y)),
                         "name_match":bool(name_consistent(nn,e["name_norm"])),
                         "highway":e.highway,
                         "RoadCat":r.get("RoadCat")})
    m=pd.DataFrame(rows)
    if m.empty:
        raise ValueError("crosswalk为空")
    return m


def build_crosswalk_generous(edges,lta,obs_links,corridor_radius,name_radius):
    """Faithful reproduction of the FIRST-DRAFT crosswalk (for the diagnostic
    comparison only): centroid radius for ALL edges + exact same-name radius.
    This is the version that produced ~77 edges/LTA and the sum artifact."""
    lta=lta[lta.LinkID.isin(obs_links)].copy()
    tree=cKDTree(edges[["mid_x","mid_y"]].to_numpy(float))
    e_nn=edges["name_norm"].to_numpy()
    rows=[]
    for _,r in lta.iterrows():
        mid=r.geometry.centroid
        nn=r["name_norm"]
        idx=set(tree.query_ball_point([mid.x,mid.y],r=corridor_radius))
        if nn:
            for j in tree.query_ball_point([mid.x,mid.y],r=name_radius):
                if e_nn[int(j)]==nn:
                    idx.add(int(j))
        for j in idx:
            e=edges.iloc[int(j)]
            rows.append({"LinkID":r.LinkID,"osm_edge_index":int(j),
                         "matsim_link_id":e.matsim_link_id,
                         "distance_m":float(math.hypot(e.mid_x-mid.x,e.mid_y-mid.y)),
                         "name_match":bool(name_consistent(nn,e["name_norm"])),
                         "highway":e.highway,
                         "RoadCat":r.get("RoadCat")})
    m=pd.DataFrame(rows)
    if m.empty:
        raise ValueError("crosswalk为空")
    return m


def metrics(y,s):
    y=np.asarray(y,float); s=np.asarray(s,float)
    mask=np.isfinite(y)&np.isfinite(s)
    y=y[mask]; s=s[mask]
    if len(y)==0:
        return {"n":0}
    out={"n":int(len(y)),
         "sum_obs":float(y.sum()),
         "sum_sim":float(s.sum()),
         "sim_obs_ratio":float(s.sum()/y.sum()) if y.sum()>0 else float("nan"),
         "mae":float(np.mean(np.abs(s-y))),
         "rmse":float(np.sqrt(np.mean((s-y)**2)))}
    if np.std(y)>0 and np.std(s)>0:
        out["pearson_r"]=float(np.corrcoef(y,s)[0,1])
    else:
        out["pearson_r"]=float("nan")
    if len(y)>1:
        out["spearman_rho"]=float(pd.Series(y).rank().corr(pd.Series(s).rank()))
    else:
        out["spearman_rho"]=float("nan")
    return out


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--project-root",type=Path,default=ROOT_DEFAULT)
    ap.add_argument("--lambdas",nargs="+",type=float,default=[0.05,0.075,0.10])
    ap.add_argument("--scale",type=float,default=DEFAULT_SCALE)
    ap.add_argument("--mode",choices=["tight","generous"],default="tight",
                    help="tight=corrected (沿几何+路名一致); generous=first-draft (质心半径)")
    ap.add_argument("--corridor-radius",type=float,default=None)
    ap.add_argument("--sample-step-m",type=float,default=SAMPLE_STEP_M)
    ap.add_argument("--out-dir",type=Path,default=None)
    args=ap.parse_args()
    root=args.project_root
    out=args.out_dir if args.out_dir is not None else (root/OUT)
    if not out.is_absolute():
        out=root/out
    out.mkdir(parents=True,exist_ok=True)

    if args.corridor_radius is not None:
        radius=args.corridor_radius
    else:
        radius=TIGHT_RADIUS_M if args.mode=="tight" else GEN_CORRIDOR_RADIUS_M

    edges=load_network(root)
    lta=load_lta(root)
    obs=load_obs(root)
    if args.mode=="tight":
        cross=build_crosswalk(edges,lta,set(obs.LinkID),radius,args.sample_step_m)
    else:
        cross=build_crosswalk_generous(edges,lta,set(obs.LinkID),GEN_CORRIDOR_RADIUS_M,GEN_NAME_RADIUS_M)
    cross.to_csv(out/"lta_section_matsim_crosswalk.csv",index=False,encoding="utf-8-sig")

    n_obs=obs.LinkID.nunique()
    n_match=cross.LinkID.nunique()
    med_edges=cross.groupby("LinkID").osm_edge_index.nunique().median()
    print(f"[mode={args.mode} radius={radius:.0f}m] Observed LTA links: {n_obs:,}")
    print(f"Matched LTA links: {n_match:,}  Coverage: {n_match/n_obs:.2%}")
    print(f"Median MATSim edges per LTA section: {med_edges:.1f}")

    # crosswalk edge index -> LINK (for joining to linkstats)
    emap=(edges[["matsim_link_id"]].reset_index(names="osm_edge_index")
          .rename(columns={"matsim_link_id":"LINK"}))
    ncg=cross.groupby("LinkID").osm_edge_index.nunique().rename("n_edges_crosswalk")

    summary=[]
    for lam in args.lambdas:
        sim,path=load_linkstats(root,lam)
        sim2=sim.merge(emap,on="LINK",how="inner")
        m=cross.merge(sim2,on="osm_edge_index",how="left")
        # aggregate section flow across the section's own candidate edges
        g=m.groupby("LinkID")["HRS8-9avg"]
        sec=pd.DataFrame({
            "n_edges_matched":g.apply(lambda s:int(s.notna().sum())),
            "sim_median_raw":g.median(),
            "sim_mean_raw":g.mean(),
            "sim_max_raw":g.max(),
            "sim_sum_raw":g.sum(),
        }).reset_index()
        sec=sec.merge(ncg,on="LinkID",how="left")
        rc=cross.drop_duplicates("LinkID")[["LinkID","RoadCat"]]
        sec=sec.merge(rc,on="LinkID",how="left")
        sec=sec.merge(obs,on="LinkID",how="inner")
        for src,dst in [("sim_median_raw","sim_median_scaled"),
                        ("sim_mean_raw","sim_mean_scaled"),
                        ("sim_max_raw","sim_max_scaled"),
                        ("sim_sum_raw","sim_sum_scaled")]:
            sec[dst]=sec[src].fillna(0)*args.scale
        sec["rel_err_median"]=(sec.sim_median_scaled-sec.obs_am)/sec.obs_am.replace(0,np.nan)
        tag=f"{lam:.3f}".replace(".","p")
        sec.to_csv(out/f"section_flow_comparison_lambda_{tag}.csv",index=False,encoding="utf-8-sig")

        # RoadCat breakdown (median estimator)
        cat=(sec.groupby("RoadCat")
             .apply(lambda d:pd.Series({
                 "n":len(d),
                 "sum_obs":d.obs_am.sum(),
                 "sum_sim_median":d.sim_median_scaled.sum(),
                 "ratio_median":d.sim_median_scaled.sum()/d.obs_am.sum() if d.obs_am.sum()>0 else np.nan,
                 "pearson_r":d[["obs_am","sim_median_scaled"]].corr().iloc[0,1],
             }),include_groups=False)
             .reset_index())
        cat.to_csv(out/f"section_flow_by_roadcat_lambda_{tag}.csv",index=False,encoding="utf-8-sig")

        for est in ["median","max","sum","mean"]:
            mt=metrics(sec["obs_am"],sec[f"sim_{est}_scaled"])
            mt={"lambda_per_min":lam,"estimator":est,"linkstats_file":str(path),
                "population_scale":args.scale,**mt}
            summary.append(mt)

    sdf=pd.DataFrame(summary)
    sdf.to_csv(out/"section_flow_comparison_summary.csv",index=False,encoding="utf-8-sig")

    headline=sdf[(sdf.estimator=="median")&(sdf.lambda_per_min==args.lambdas[0])].iloc[0]
    with open(out/"step6_3_2_validation.json","w",encoding="utf-8") as f:
        json.dump({
            "status":"PASS" if n_match>0 else "FAIL",
            "mode":args.mode,
            "corridor_radius_m":radius,
            "sample_step_m":args.sample_step_m,
            "observed_lta_links":int(n_obs),
            "matched_lta_links":int(n_match),
            "crosswalk_coverage":float(n_match/n_obs),
            "median_edges_per_lta":float(med_edges),
            "scale":args.scale,
            "estimator":"median (per-section representative flow)",
            "headline_lambda":args.lambdas[0],
            "headline_metrics":{k:(None if pd.isna(v) else float(v))
                                for k,v in headline.items()
                                if k in ("sim_obs_ratio","pearson_r","spearman_rho","mae","rmse")},
            "note":("Section-level flow uses a per-section representative value "
                    "(median over same-corridor edges); summing sections or edges "
                    "double-counts vehicles and is not a valid point-count comparison."),
        },f,ensure_ascii=False,indent=2)

    print("\nSummary (per estimator):")
    with pd.option_context("display.width",240):
        print(sdf[["lambda_per_min","estimator","n","sum_obs","sum_sim",
                   "sim_obs_ratio","pearson_r","spearman_rho","mae","rmse"]].round(4).to_string(index=False))
    print("\nOutput:",out)


if __name__=="__main__":
    main()
