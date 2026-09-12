#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Step 7.1: build a frozen TrafficFlow calibration-target table.

No OD/network/capacity/route-choice/lambda changes.
Observed: weekday daily TrafficFlow volume -> median by LinkID x hour.
Simulated: MATSim it.0 linkstats HRS7-8/HRS8-9, scaled by 459794/200000.
LTA sections are linked to MATSim through the validated 6.3.2 crosswalk;
multiple MATSim edges are represented by the median edge flow per section.

Outputs:
  reports/od_calibration_7_1/
    calibration_target_lambda_*.csv
    calibration_target_summary.csv
    calibration_target_by_roadcat.csv
    calibration_target_definition.json
"""
from __future__ import annotations
import argparse, gzip, json, math
from pathlib import Path
import numpy as np
import pandas as pd

ROOT_DEFAULT=Path(r"D:\Luan\2026-05\2_Singapore")
FLOW=Path("Singapore_OD_MATSim_FinalData/08_TrafficCount/TrafficFlow_Data.json")
CROSS=Path("reports/matsim_assignment_6_3_2/lta_section_matsim_crosswalk.csv")
ASSIGN=Path("reports/matsim_assignment_6_3_3b")
OUT=Path("reports/od_calibration_7_1")
SCALE=459794.0/200000.0

def obs_load(root):
    with (root/FLOW).open("r",encoding="utf-8") as f: obj=json.load(f)
    d=pd.DataFrame(obj.get("Value",obj if isinstance(obj,list) else obj.get("value",[])))
    req={"LinkID","Date","HourOfDate","Volume"}
    miss=req-set(d.columns)
    if miss: raise ValueError(f"TrafficFlow缺字段: {sorted(miss)}")
    d["LinkID"]=d.LinkID.astype(str).str.strip()
    d["Date"]=pd.to_datetime(d.Date,dayfirst=True,errors="coerce")
    d["HourOfDate"]=pd.to_numeric(d.HourOfDate,errors="coerce")
    d["Volume"]=pd.to_numeric(d.Volume.astype(str).str.replace(",","",regex=False),errors="coerce")
    d=d[d.Date.notna() & d.Date.dt.weekday.lt(5) & d.HourOfDate.isin([7,8]) & d.Volume.notna()].copy()
    daily=d.groupby(["LinkID","Date","HourOfDate"],as_index=False).Volume.mean()
    med=daily.groupby(["LinkID","HourOfDate"],as_index=False).Volume.median()
    w=med.pivot(index="LinkID",columns="HourOfDate",values="Volume").reset_index()
    w.columns.name=None
    w=w.rename(columns={7:"obs_7_8",8:"obs_8_9"})
    for c in ["obs_7_8","obs_8_9"]:
        if c not in w.columns: w[c]=np.nan
    w["obs_am"]=w[["obs_7_8","obs_8_9"]].fillna(0).sum(axis=1)
    return w

def cross_load(root):
    p=root/CROSS
    c=pd.read_csv(p,encoding="utf-8-sig",low_memory=False)
    # 分层必须用 LTA 断面级 RoadCat（CATA/CATB/CATC/CATD/CATE/SLIP_ROAD），
    # 而不是逐边 OSM `highway`（同一 LinkID 内会出现多值，导致分层与 LTA 口径不一致）。
    req={"LinkID","matsim_link_id","name_match","RoadCat"}
    miss=req-set(c.columns)
    if miss: raise ValueError(f"crosswalk缺字段: {sorted(miss)}")
    c["LinkID"]=c.LinkID.astype(str).str.strip()
    c["matsim_link_id"]=c.matsim_link_id.astype(str)
    # 防御：RoadCat 必须断面级一致，否则无法作为断面属性使用
    bad=(c.groupby("LinkID").RoadCat.nunique()>1).sum()
    if bad: raise ValueError(f"RoadCat 在 {int(bad)} 个 LinkID 内不一致，无法作为断面级属性")
    return c

def find_stats(root,lam):
    tag=f"{lam:.3f}".replace(".","p")
    files=[p for p in (root/ASSIGN).rglob("*.linkstats.txt.gz") if "it.0" in str(p).lower() and (f"lambda_{tag}" in str(p) or f"0p{int(round(lam*1000)):03d}" in str(p))]
    if not files: raise FileNotFoundError(f"找不到lambda={lam} linkstats")
    return sorted(files,key=lambda p:(len(str(p)),str(p)))[0]

def sim_load(root,lam):
    p=find_stats(root,lam)
    with gzip.open(p,"rt",encoding="latin-1",errors="replace") as f: header=f.readline().rstrip("\n").split("\t")
    wanted=["LINK","HRS7-8avg","HRS8-9avg"]
    pos={x:header.index(x) for x in wanted if x in header}
    if set(pos)!=set(wanted): raise ValueError(f"linkstats缺字段: {sorted(set(wanted)-set(pos))}")
    use=sorted(pos.values())
    d=pd.read_csv(p,sep="\t",usecols=use,compression="gzip",encoding="latin-1",low_memory=False)
    ren={d.columns[use.index(i)]:c for c,i in pos.items()}
    d=d.rename(columns=ren)
    d["LINK"]=d.LINK.astype(str)
    for c in wanted[1:]: d[c]=pd.to_numeric(d[c],errors="coerce").fillna(0.0)
    return d,p

def metric(o,s):
    z=pd.DataFrame({"obs":o,"sim":s}).replace([np.inf,-np.inf],np.nan).dropna()
    if z.empty: return dict(n=0)
    o=z.obs.to_numpy(float); s=z.sim.to_numpy(float); e=s-o
    geh=np.sqrt(2*(s-o)**2/np.maximum(s+o,1e-12))
    n=len(z)
    # 相关类指标：n<2 或任一序列无方差时无定义（如 CATE 仅 1 条断面），避免 numpy 警告
    if n>=2 and np.std(o)>0 and np.std(s)>0:
        pear=float(np.corrcoef(o,s)[0,1]); rho=float(pd.Series(o).rank().corr(pd.Series(s).rank()))
    else:
        pear=float("nan"); rho=float("nan")
    return {
        "n":int(n),
        "pearson_r":pear,
        "spearman_rho":rho,
        "mae":float(np.mean(np.abs(e))),
        "rmse":float(np.sqrt(np.mean(e**2))),
        "mape":float(np.mean(np.abs(e[o>0]/o[o>0]))) if np.any(o>0) else np.nan,
        "wmape":float(np.sum(np.abs(e))/np.sum(np.abs(o))) if np.sum(np.abs(o))>0 else np.nan,
        "bias":float(np.mean(e)),
        "bias_ratio":float(np.sum(e)/np.sum(o)) if np.sum(o)>0 else np.nan,
        "sim_obs_ratio":float(np.sum(s)/np.sum(o)) if np.sum(o)>0 else np.nan,
        "geh_lt_5_rate":float(np.mean(geh<5)),
        "geh_lt_10_rate":float(np.mean(geh<10)),
        "geh_median":float(np.median(geh)),
        "sum_obs":float(np.sum(o)),
        "sum_sim":float(np.sum(s)),
    }

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--project-root",type=Path,default=ROOT_DEFAULT)
    ap.add_argument("--lambdas",nargs="+",type=float,default=[0.05,0.075,0.10])
    ap.add_argument("--scale",type=float,default=SCALE)
    a=ap.parse_args()
    root=a.project_root; out=root/OUT; out.mkdir(parents=True,exist_ok=True)
    obs=obs_load(root); cross=cross_load(root)
    cross=cross[cross.LinkID.isin(set(obs.LinkID))].copy()
    if cross.empty: raise ValueError("crosswalk与观测LinkID无交集")
    allsum=[]; rc=[]
    for lam in a.lambdas:
        sim,path=sim_load(root,lam)
        x=cross[["LinkID","matsim_link_id","name_match","RoadCat"]].drop_duplicates()
        x=x.merge(sim.rename(columns={"LINK":"matsim_link_id"}),on="matsim_link_id",how="left").fillna({"HRS7-8avg":0,"HRS8-9avg":0})
        sec=x.groupby("LinkID",as_index=False).agg(matched_matsim_edges=("matsim_link_id","nunique"),
              sim_7_8_raw=("HRS7-8avg","median"),sim_8_9_raw=("HRS8-9avg","median"),
              name_match_rate=("name_match","mean"),RoadCat=("RoadCat","first"))
        sec=sec.merge(obs,on="LinkID",how="inner")
        sec["sim_7_8"]=sec.sim_7_8_raw*a.scale
        sec["sim_8_9"]=sec.sim_8_9_raw*a.scale
        sec["sim_am"]=sec.sim_7_8+sec.sim_8_9
        tag=f"{lam:.3f}".replace(".","p")
        sec.to_csv(out/f"calibration_target_lambda_{tag}.csv",index=False,encoding="utf-8-sig")
        for tw,o,s in [("07-08","obs_7_8","sim_7_8"),("08-09","obs_8_9","sim_8_9"),("AM","obs_am","sim_am")]:
            m=metric(sec[o],sec[s]); allsum.append({"lambda_per_min":lam,"time_window":tw,**m,"linkstats_file":str(path)})
        for tw,o,s in [("07-08","obs_7_8","sim_7_8"),("08-09","obs_8_9","sim_8_9"),("AM","obs_am","sim_am")]:
            for cat,g in sec.groupby("RoadCat",dropna=False):
                rc.append({"lambda_per_min":lam,"time_window":tw,"roadcat":str(cat),**metric(g[o],g[s])})
    sm=pd.DataFrame(allsum); rr=pd.DataFrame(rc)
    sm.to_csv(out/"calibration_target_summary.csv",index=False,encoding="utf-8-sig")
    rr.to_csv(out/"calibration_target_by_roadcat.csv",index=False,encoding="utf-8-sig")
    definition={"step":"7.1","status":"PASS","observed_source":str(FLOW),"crosswalk_source":str(CROSS),
      "time_windows":["07:00-08:00","08:00-09:00","AM(07-09)"],"observed_statistic":"weekday daily volume median by LinkID x hour",
      "simulation_statistic":"MATSim linkstats hourly average, scaled by real_trip/sample_agent ratio; median of matched directed edges per LTA section",
      "stratification":"LTA RoadCat (CATA/CATB/CATC/CATD/CATE/SLIP_ROAD), section-level constant",
      "scale":a.scale,"real_car_trips":REAL_CAR_TRIPS if 'REAL_CAR_TRIPS' in globals() else 459794.0,
      "sample_agents":200000,"metrics":["pearson_r","spearman_rho","mae","rmse","mape","wmape","bias","sim_obs_ratio","GEH<5","GEH<10"],
      "parameters_changed":False,"lambda_selected":False}
    (out/"calibration_target_definition.json").write_text(json.dumps(definition,ensure_ascii=False,indent=2),encoding="utf-8")
    print(sm.to_string(index=False))
    print(f"Observed LTA links: {obs.LinkID.nunique():,}")
    print(f"Crosswalk LTA links: {cross.LinkID.nunique():,}")
    print(f"Output: {out}")

if __name__=="__main__": main()
