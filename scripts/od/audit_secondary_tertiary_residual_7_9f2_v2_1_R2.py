#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""7.9F-2 v2.1-R2 — Execution / Contract Closure Repair.
ZERO SIMULATION / READ-ONLY / DIAGNOSTIC ONLY.

R2-1  e1_load returns every key checks() reads + static AST contract self-check (gate 18).
R2-2  preflight is the sole authority for gates 05/06; failure closes the node under control.
R2-3  write-back verification of analytical artifacts (gate 17) + manifest generated last
      (not self-hashed) + materialised terminal closure (closure_check.csv).

Q2/Q4 definitions, thresholds, domains, SCALE and frozen inputs are unchanged from R1.
"""
from __future__ import annotations
import argparse, ast, gzip, hashlib, json, math, re
from pathlib import Path
import numpy as np
import pandas as pd

ROOT_DEFAULT=Path(r"D:\Luan\2026-05\2_Singapore")
TRAFFIC_REL=Path("Singapore_OD_MATSim_FinalData/08_TrafficCount/TrafficFlow_Data.json")
E1_REL=Path("reports/arterial_observability_7_9e1/e1_crosswalk_candidates.csv")
E2_REL=Path("reports/arterial_expanded_residual_7_9e2/e2_section_residual_main.csv")
NETWORK_REL=Path("reports/matsim_network/network_links_source_copy.csv")
NODES_REL=Path("reports/matsim_network/network_nodes_source_copy.csv")
W01_REL=Path("matsim_final_7_6h/outputs/W01_rc_min/ITERS/it.19")
OUT_REL=Path("reports/secondary_tertiary_residual_7_9f2_v2_1_R2")
PREREG_REL=Path("reports/secondary_tertiary_residual_7_9f2_v2_1_R2_PREREG/PREREG_7_9F2_v2_1_R2.md")
EXPECTED_PREREG_SHA256="0a0c61336056a66d5ea1506215b1680d3920aef2cb804a221571812e9de18a19"
SCALE=459794.0/200000.0
A="A_STRICT_SEMANTIC_DIRECTION"; B="B_DIRECTION_GEOMETRY"; C="C_GEOMETRY_ONLY"
TIERS={A,B,C}; TARGET_HW={"secondary","tertiary"}
RADII=[20.0,50.0,100.0]; FWD=30.0; REV=150.0
TRANSIENT_SUFFIXES=(".uploading.cfg",".tmp"); TRANSIENT_PREFIXES=("~$",".~lock.")

REVISION="F-2 v2.1-R2"; PREFIX="f2v21r2"
ST_READY="LOCAL_CAPTURE_DIAGNOSTIC_READY"; ST_BLOCKED="LOCAL_CAPTURE_DIAGNOSTIC_BLOCKED"
E1_LOADER_FN="e1_load"; CHECKS_FN="checks"; CHECKS_DETAIL_PARAM="cand_detail"
E1_LOADER_KEYS=("raw_rows","kept_rows","dropped_rows","raw_id_missing","raw_bad_tier","tier_counts")

ART_TARGET=f"{PREFIX}_target_sections.csv"
ART_E1=f"{PREFIX}_all_e1_candidates.csv"
ART_AB=f"{PREFIX}_selected_ab_candidates.csv"
ART_Q2SUM=f"{PREFIX}_direction_candidate_summary.csv"
ART_Q2LONG=f"{PREFIX}_direction_candidate_long.csv"
ART_Q2CORR=f"{PREFIX}_q2_correlations.csv"
ART_GROUP=f"{PREFIX}_group_summary.csv"
ART_Q4DETAIL=f"{PREFIX}_single_link_capture.csv"
ART_Q4SUM=f"{PREFIX}_q4_summary.csv"
ART_OBS=f"{PREFIX}_obs_rebuild_check.csv"
ART_CLOSURE=f"{PREFIX}_closure_check.csv"
ART_CHECKS=f"{PREFIX}_checks.csv"
ART_MANIFEST=f"{PREFIX}_input_manifest.json"
ART_SUMMARY=f"{PREFIX}_summary.json"
ART_REPORT="STEP7_9F2_v2_1_R2_REPORT.md"

ANALYTIC_ARTIFACTS=[ART_TARGET,ART_E1,ART_AB,ART_Q2SUM,ART_Q2LONG,ART_Q2CORR,ART_GROUP,ART_Q4DETAIL,ART_Q4SUM,ART_OBS]
NAMES_FULL=ANALYTIC_ARTIFACTS+[ART_CLOSURE,ART_CHECKS,ART_MANIFEST,ART_SUMMARY,ART_REPORT]
NAMES_BLOCKED=[ART_CLOSURE,ART_CHECKS,ART_MANIFEST,ART_SUMMARY,ART_REPORT]
EARLIER_NODES=["secondary_tertiary_residual_7_9f2","secondary_tertiary_residual_7_9f2_v2",
               "secondary_tertiary_residual_7_9f2_v2_1","secondary_tertiary_residual_7_9f2_v2_1_R1",
               "secondary_tertiary_residual_7_9f2_v2_1_R1_PREREG"]


def sha256_file(p):
    h=hashlib.sha256();
    with Path(p).open("rb") as f:
        for b in iter(lambda:f.read(1<<20),b""): h.update(b)
    return h.hexdigest()

def nid(x):
    s="" if x is None else str(x).strip()
    return "" if not s or s.lower()=="nan" else (s[:-2] if s.endswith(".0") and s[:-2].isdigit() else s)

def nt(x):
    s="" if x is None else str(x).replace("\xa0"," ").strip()
    return "" if s.lower()=="nan" else " ".join(s.split())

def nn(x):
    s=nt(x).upper()
    if not s:return ""
    s=s.replace("&"," AND "); s=re.sub(r"[-_/(),.&]+"," ",s)
    return re.sub(r"\s+"," ",s).strip()

def num(s): return pd.to_numeric(s.astype(str).str.replace(",","",regex=False),errors="coerce")
def ratio(a,b): return float(a/b) if np.isfinite(a) and np.isfinite(b) and b!=0 else np.nan

def spr(x,y):
    z=pd.concat([pd.to_numeric(x,errors="coerce"),pd.to_numeric(y,errors="coerce")],axis=1).dropna()
    if len(z)<4 or z.iloc[:,0].nunique()<2 or z.iloc[:,1].nunique()<2:return np.nan
    return float(z.iloc[:,0].corr(z.iloc[:,1],method="spearman"))

def adiff(a,b):
    if not np.isfinite(a) or not np.isfinite(b):return np.nan
    d=abs(a-b)%360.0; return min(d,360.0-d)

def bearing(dx,dy):
    if not np.isfinite(dx) or not np.isfinite(dy):return np.nan
    a=math.degrees(math.atan2(dx,dy)); return a if a>=0 else a+360.0

def zero_sim(p):
    t=ast.parse(Path(p).read_text(encoding="utf-8")); mods={"subprocess","jpype","py4j"}; calls={"system","popen","Popen","run","call","check_call","check_output"}
    for n in ast.walk(t):
        if isinstance(n,ast.Import) and any(a.name.split(".")[0] in mods for a in n.names):return False
        if isinstance(n,ast.ImportFrom) and n.module and n.module.split(".")[0] in mods:return False
        if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute) and n.func.attr in calls:return False
    return True

def transient(name):
    lo=name.lower(); return any(lo.endswith(x) for x in TRANSIENT_SUFFIXES) or any(lo.startswith(x.lower()) for x in TRANSIENT_PREFIXES)

def locate_w01(root, supplied):
    p=Path(supplied) if supplied is not None else root/W01_REL
    if p.is_file(): return p
    if not p.is_dir(): raise FileNotFoundError(f"W01 输入不存在: {p}")
    cand=sorted(q for q in p.iterdir() if q.is_file() and q.name.endswith(".linkstats.txt.gz") and "W01_rc_min.19" in q.name)
    if len(cand)!=1: raise RuntimeError(f"W01 directory must resolve exactly one frozen W01_rc_min.19.linkstats.txt.gz; found={cand}")
    return cand[0]

def traffic_obs(p):
    obj=json.loads(Path(p).read_text(encoding="utf-8-sig")); rows=obj.get("Value",obj.get("value",[])) if isinstance(obj,dict) else obj; d=pd.DataFrame(rows)
    req={"LinkID","Date","HourOfDate","Volume","RoadName","RoadCat"}; miss=req-set(d.columns)
    if miss: raise ValueError(f"TrafficFlow JSON 缺字段: {sorted(miss)}")
    d["LinkID"]=d["LinkID"].map(nid); d["Date"]=pd.to_datetime(d["Date"],dayfirst=True,errors="coerce"); d["HourOfDate"]=pd.to_numeric(d["HourOfDate"],errors="coerce"); d["Volume"]=num(d["Volume"])
    d=d[d.LinkID.ne("")&d.Date.notna()&d.Date.dt.weekday.lt(5)&d.HourOfDate.eq(8)&d.Volume.notna()].copy()
    daily=d.groupby(["LinkID","Date"],as_index=False).Volume.mean(); o=daily.groupby("LinkID",as_index=False).Volume.median().rename(columns={"Volume":"obs_8_9_rebuilt"})
    return o

def e1_load(p):
    """R2-1: return keys are a superset of every key checks() reads.

    Contract: {raw_rows,kept_rows,dropped_rows,raw_id_missing,raw_bad_tier,tier_counts}
    (declared in E1_LOADER_KEYS; enforced statically by contract_check / gate 18).
    """
    x=pd.read_csv(p,encoding="utf-8-sig",low_memory=False); raw=len(x); lo={str(c).strip().lower():c for c in x.columns}
    mp={"lta_linkid":"lta_linkid","linkid":"lta_linkid","matsim_link_id":"matsim_link_id","matsim_link":"matsim_link_id","tier":"tier","distance_m":"distance_m","geometry_distance_m":"distance_m","direction_diff_deg":"direction_diff_deg","direction_diff":"direction_diff_deg","highway":"highway","semantic_compatible":"semantic_compatible","semantic_ok":"semantic_compatible","name_similarity":"name_similarity","name_sim":"name_similarity"}
    x=x.rename(columns={c:mp[k] for k,c in lo.items() if k in mp}); req={"lta_linkid","matsim_link_id","tier","distance_m","direction_diff_deg","highway"}; miss=req-set(x.columns)
    if miss: raise ValueError(f"E1 candidates 缺字段: {sorted(miss)}")
    x.lta_linkid=x.lta_linkid.map(nid); x.matsim_link_id=x.matsim_link_id.map(nid); x.tier=x.tier.map(nt); x.distance_m=num(x.distance_m); x.direction_diff_deg=num(x.direction_diff_deg); x.highway=x.highway.map(nt).str.lower()
    _raw_id_missing=int((x.lta_linkid.eq("")|x.matsim_link_id.eq("")).sum()); _raw_bad_tier=int((~x.tier.isin(TIERS)).sum())
    x=x[x.lta_linkid.ne("")&x.matsim_link_id.ne("")&x.tier.isin(TIERS)&x.distance_m.notna()].copy(); x=x.drop_duplicates(["lta_linkid","matsim_link_id","tier"])
    return x,{"raw_rows":raw,"kept_rows":len(x),"dropped_rows":raw-len(x),"raw_id_missing":_raw_id_missing,"raw_bad_tier":_raw_bad_tier,"tier_counts":x.tier.value_counts().to_dict()}

def select_ab(c):
    out=[]
    for sid,g in c.groupby("lta_linkid",sort=True):
        a=g[g.tier.eq(A)]; q=a if not a.empty else g[g.tier.eq(B)]
        if q.empty:continue
        out.append(q.sort_values(["distance_m","direction_diff_deg","semantic_compatible","name_similarity","matsim_link_id"],ascending=[True,True,False,False,True]).drop_duplicates("matsim_link_id"))
    return pd.concat(out,ignore_index=True) if out else c.iloc[0:0].copy()

def e2_load(p):
    d=pd.read_csv(p,encoding="utf-8-sig",low_memory=False); req={"LinkID","obs_8_9","sim_8_9_scaled","diagnostic_residual_8_9","diagnostic_highway","valid_residual"}; miss=req-set(d.columns)
    if miss:raise ValueError(f"E2 缺字段: {sorted(miss)}")
    d.LinkID=d.LinkID.map(nid); d.obs_8_9=num(d.obs_8_9); d.sim_8_9_scaled=num(d.sim_8_9_scaled); d.diagnostic_residual_8_9=num(d.diagnostic_residual_8_9); d.diagnostic_highway=d.diagnostic_highway.map(nt).str.lower(); d.valid_residual=d.valid_residual.astype(str).str.lower().isin(["true","1","yes"]); return d

def network_load(p,npth):
    n=pd.read_csv(npth,low_memory=False); lo={str(c).strip().lower():c for c in n.columns}; ic=next((lo[k] for k in ["node_id","id","node"] if k in lo),None); xc=next((lo[k] for k in ["x","x_svy21_m","easting"] if k in lo),None); yc=next((lo[k] for k in ["y","y_svy21_m","northing"] if k in lo),None)
    if not ic or not xc or not yc:raise ValueError("network nodes 无法识别 node/x/y")
    n=n[[ic,xc,yc]].copy(); n.columns=["node_id","x","y"]; n.node_id=n.node_id.map(nid); n.x=num(n.x); n.y=num(n.y); n=n.dropna();
    if n.node_id.duplicated().any():raise ValueError("重复 node_id")
    g=pd.read_csv(p,usecols=["from_node","to_node","length_m","highway","name"],encoding="utf-8-sig",low_memory=False); g.from_node=g.from_node.map(nid); g.to_node=g.to_node.map(nid); g.length_m=num(g.length_m); g.highway=g.highway.map(nt).str.lower(); g.name=g.name.map(nt); g["name_norm"]=g["name"].map(nn); g["matsim_link_id"]="e"+g.from_node+"_"+g.to_node; g=g[g.from_node.ne("")&g.to_node.ne("")&g.length_m.gt(0)].copy();
    if g.matsim_link_id.duplicated().any():raise ValueError("重复 matsim_link_id")
    xy=n.set_index("node_id")[["x","y"]]; g=g.join(xy.rename(columns={"x":"from_x","y":"from_y"}),on="from_node"); g=g.join(xy.rename(columns={"x":"to_x","y":"to_y"}),on="to_node"); g=g[g.from_x.notna()&g.from_y.notna()&g.to_x.notna()&g.to_y.notna()].copy(); g["mid_x"]=(g.from_x+g.to_x)/2; g["mid_y"]=(g.from_y+g.to_y)/2; g["heading_deg"]=[bearing(a,b) for a,b in zip(g.to_x-g.from_x,g.to_y-g.from_y)]; return g

def w01_load(p):
    op=gzip.open if Path(p).suffix==".gz" else open
    with op(p,"rt",encoding="utf-8",errors="replace") as f:h=f.readline().rstrip("\n").split("\t")
    miss={"LINK","HRS8-9avg"}-set(h)
    if miss:raise ValueError(f"W01 缺字段: {sorted(miss)}")
    d=pd.read_csv(p,sep="\t",compression="gzip" if Path(p).suffix==".gz" else None,usecols=["LINK","HRS8-9avg"],low_memory=False); d.LINK=d.LINK.map(nid); d["HRS8-9avg"]=num(d["HRS8-9avg"])
    if d.LINK.duplicated().any():
        raise ValueError("W01 LINK 重复")
    return d

def q2(c,t):
    x=c.merge(t[["LinkID","diagnostic_highway","diagnostic_residual_8_9","obs_8_9"]],left_on="lta_linkid",right_on="LinkID",how="inner"); rows=[]
    for sid,g in x.groupby("lta_linkid",sort=True):
        d=num(g.direction_diff_deg).dropna(); f=d.le(FWD) if len(d) else pd.Series(dtype=bool); r=d.ge(REV) if len(d) else pd.Series(dtype=bool); n=d.gt(FWD)&d.lt(REV) if len(d) else pd.Series(dtype=bool)
        row={"LinkID":sid,"diagnostic_highway":g.diagnostic_highway.iloc[0],"diagnostic_residual_8_9":g.diagnostic_residual_8_9.iloc[0],"obs_8_9":g.obs_8_9.iloc[0],"e1_candidate_n":len(g),"A_candidate_n":int((g.tier==A).sum()),"B_candidate_n":int((g.tier==B).sum()),"C_candidate_n":int((g.tier==C).sum()),"direction_valid_n":len(d),"forward_n":int(f.sum()),"reverse_n":int(r.sum()),"neutral_n":int(n.sum()),"forward_share":float(f.mean()) if len(d) else np.nan,"reverse_share":float(r.mean()) if len(d) else np.nan,"neutral_share":float(n.mean()) if len(d) else np.nan,"median_direction_diff_deg":float(d.median()) if len(d) else np.nan,"p90_direction_diff_deg":float(d.quantile(.9)) if len(d) else np.nan,"reverse_any":bool(r.any()) if len(d) else False}
        for tier in [A,B,C]:
            z=num(g.loc[g.tier.eq(tier),"direction_diff_deg"]).dropna(); row[f"{tier}_reverse_share"]=float(z.ge(REV).mean()) if len(z) else np.nan; row[f"{tier}_forward_share"]=float(z.le(FWD).mean()) if len(z) else np.nan
        rows.append(row)
    s=pd.DataFrame(rows); l=x[["lta_linkid","tier","matsim_link_id","distance_m","direction_diff_deg","highway","diagnostic_highway","diagnostic_residual_8_9","obs_8_9"]].rename(columns={"lta_linkid":"LinkID"});
    valid = l.direction_diff_deg.notna()
    l["direction_class"] = np.select(
        [valid & l.direction_diff_deg.le(FWD), valid & l.direction_diff_deg.ge(REV), valid & l.direction_diff_deg.gt(FWD) & l.direction_diff_deg.lt(REV)],
        ["FORWARD", "REVERSE", "NEUTRAL"],
        default="UNKNOWN",
    )
    return s, l

def q2corr(s):
    rows=[]
    for m in ["reverse_share","forward_share","median_direction_diff_deg","reverse_any",f"{C}_reverse_share",f"{C}_forward_share"]:
        z=pd.concat([s[m],s.diagnostic_residual_8_9],axis=1).dropna(); rows.append({"metric":m,"n":len(z),"spearman_with_frozen_residual":spr(s[m],s.diagnostic_residual_8_9)})
    return pd.DataFrame(rows)

def q4(t,sel,net,stats):
    from scipy.spatial import cKDTree
    g=net.reset_index(drop=True); tree=cKDTree(g[["mid_x","mid_y"]].to_numpy(float)); fmap=stats.set_index("LINK")["HRS8-9avg"].to_dict(); out=[]
    ss=sel.groupby("lta_linkid")["matsim_link_id"].apply(set).to_dict()
    for sid,mids in ss.items():
        tt=t[t.LinkID.eq(sid)];
        if tt.empty:continue
        focal=g[g.matsim_link_id.isin(mids)].copy(); obs=float(tt.obs_8_9.iloc[0]); cr=float(tt.sim_8_9_scaled.iloc[0])/obs; ce=abs(cr-1)
        names={x for x in focal.name_norm if x}
        for rad in RADII:
            idx=set()
            for _,fr in focal.iterrows():idx.update(tree.query_ball_point([float(fr.mid_x),float(fr.mid_y)],rad))
            cats={k:set() for k in ["parallel","twin","same_name_parallel","same_name_twin"]}
            for i in idx:
                nr=g.iloc[i]; nid=nr.matsim_link_id
                if nid in mids:continue
                bd=min(math.hypot(float(nr.mid_x)-float(fr.mid_x),float(nr.mid_y)-float(fr.mid_y)) for _,fr in focal.iterrows())
                if bd>rad:continue
                hd=float(np.nanmin([adiff(float(nr.heading_deg),float(fr.heading_deg)) for _,fr in focal.iterrows()]));
                if hd<=FWD:
                    cats["parallel"].add(nid); 
                    if nr.name_norm and nr.name_norm in names:cats["same_name_parallel"].add(nid)
                if hd>=REV:
                    cats["twin"].add(nid); 
                    if nr.name_norm and nr.name_norm in names:cats["same_name_twin"].add(nid)
            for typ,ids in cats.items():
                vals=[float(fmap.get(x,np.nan)) for x in ids]; vals=[v for v in vals if np.isfinite(v)]; bf=max(vals) if vals else np.nan; br=ratio(bf*SCALE,obs); be=abs(br-1) if np.isfinite(br) else np.nan; ch=be-ce if np.isfinite(be) else np.nan
                out.append({"LinkID":sid,"diagnostic_highway":tt.diagnostic_highway.iloc[0],"diagnostic_residual_8_9":tt.diagnostic_residual_8_9.iloc[0],"obs_8_9":obs,"canonical_ratio_e2":cr,"canonical_abs_error_e2":ce,"radius_m":rad,"neighbor_type":typ,"neighbor_n":len(ids),"neighbor_positive_flow_n":sum(v>0 for v in vals),"best_single_link_flow_raw":bf,"best_single_link_ratio":br,"best_single_link_abs_error":be,"capture_error_change":ch,"capture_improved":(bool(ch<0) if np.isfinite(ch) else pd.NA)})
    return pd.DataFrame(out)

def q4sum(q):
    rows=[]
    for (hw,r,typ),g in q.groupby(["diagnostic_highway","radius_m","neighbor_type"]):
        ratio_valid=g.best_single_link_ratio.notna(); change_valid=g.capture_error_change.notna()
        rows.append({"diagnostic_highway":hw,"radius_m":r,"neighbor_type":typ,"n_all_target":int(len(g)),"n_valid_single_link_ratio":int(ratio_valid.sum()),"n_valid_capture_change":int(change_valid.sum()),"positive_flow_prevalence_all":float(g.neighbor_positive_flow_n.gt(0).mean()),"positive_flow_prevalence_valid_ratio":float(g.loc[ratio_valid,"neighbor_positive_flow_n"].gt(0).mean()) if ratio_valid.any() else np.nan,"median_neighbor_n":float(g.neighbor_n.median()),"median_best_single_link_ratio":float(g.loc[ratio_valid,"best_single_link_ratio"].median()) if ratio_valid.any() else np.nan,"median_capture_error_change":float(g.loc[change_valid,"capture_error_change"].median()) if change_valid.any() else np.nan,"capture_improved_share_valid":float(g.loc[change_valid,"capture_improved"].astype(bool).mean()) if change_valid.any() else np.nan,"capture_missing_share":float((~change_valid).mean())})
    return pd.DataFrame(rows)

def group_sum(s,q):
    rows=[]
    for hw in ["secondary","tertiary"]:
        a=s[s.diagnostic_highway.eq(hw)]; b=q[(q.diagnostic_highway.eq(hw))&(q.radius_m.eq(100.0))]; p=b[b.neighbor_type.eq("parallel")]; tw=b[b.neighbor_type.eq("twin")]
        rows.append({"diagnostic_highway":hw,"n":len(a),"median_reverse_share":a.reverse_share.median(),"median_forward_share":a.forward_share.median(),"median_direction_diff_deg":a.median_direction_diff_deg.median(),"reverse_any_prevalence":a.reverse_any.mean(),"median_C_reverse_share":a[f"{C}_reverse_share"].median(),"parallel_positive_flow_share_100m":float(p.neighbor_positive_flow_n.gt(0).mean()) if len(p) else np.nan,"twin_positive_flow_share_100m":float(tw.neighbor_positive_flow_n.gt(0).mean()) if len(tw) else np.nan})
    return pd.DataFrame(rows)

def preflight_network(path,nodes_path):
    out={"network_duplicate_link_id":0,"node_duplicate_id":0,"node_required_missing":[]}
    n=pd.read_csv(nodes_path,low_memory=False); low={str(c).strip().lower():c for c in n.columns}
    ic=next((low[k] for k in ["node_id","id","node"] if k in low),None); xc=next((low[k] for k in ["x","x_svy21_m","easting"] if k in low),None); yc=next((low[k] for k in ["y","y_svy21_m","northing"] if k in low),None)
    if not ic or not xc or not yc: out["node_required_missing"]=["node_id/x/y"]
    else: out["node_duplicate_id"]=int(n[ic].map(nid).duplicated().sum())
    g=pd.read_csv(path,usecols=["from_node","to_node","length_m","highway","name"],encoding="utf-8-sig",low_memory=False); ids="e"+g["from_node"].map(nid)+"_"+g["to_node"].map(nid); out["network_duplicate_link_id"]=int(ids.duplicated().sum())
    return out

def preflight_w01(path):
    op=gzip.open if Path(path).suffix.lower()==".gz" else open
    with op(path,"rt",encoding="utf-8",errors="replace") as f: header=f.readline().rstrip("\n").split("\t")
    miss=sorted({"LINK","HRS8-9avg"}-set(header)); dup=0
    if not miss:
        d=pd.read_csv(path,sep="\t",compression="gzip" if Path(path).suffix.lower()==".gz" else None,usecols=["LINK"],low_memory=False); dup=int(d["LINK"].map(nid).duplicated().sum())
    return {"missing":miss,"duplicate_link":dup}


# ---------------------------------------------------------------- R2 new code

def pf_guard(fn,*a,**kw):
    """R2-2: a preflight must never raise; it must report. Returns (result_or_None, err)."""
    try: return fn(*a,**kw), None
    except Exception as e: return None, f"{type(e).__name__}: {e}"

def pf_network_ok(pf):
    return bool(pf) and not pf.get("error") and pf.get("network_duplicate_link_id")==0 and pf.get("node_duplicate_id")==0 and not pf.get("node_required_missing")

def pf_w01_ok(pf):
    return bool(pf) and not pf.get("error") and not pf.get("missing") and pf.get("duplicate_link")==0

def contract_check(script_path):
    """R2-1: static two-way contract check between e1_load's returned keys and checks()'s reads.

    (a) the literal dict returned by e1_load must have exactly the declared key set;
    (b) every string subscript on the checks() detail parameter must be a subset of it.
    """
    src=Path(script_path).read_text(encoding="utf-8"); tree=ast.parse(src)
    loader_return=None; loader_found=False; checks_found=False; ref=None
    for node in tree.body:
        if isinstance(node,ast.FunctionDef) and node.name==E1_LOADER_FN:
            loader_found=True
            for sub in ast.walk(node):
                if isinstance(sub,ast.Return) and isinstance(sub.value,ast.Tuple) and len(sub.value.elts)==2 and isinstance(sub.value.elts[1],ast.Dict):
                    loader_return=[(k.value if isinstance(k,ast.Constant) and isinstance(k.value,str) else None) for k in sub.value.elts[1].keys]
        if isinstance(node,ast.FunctionDef) and node.name==CHECKS_FN:
            checks_found=True
            ks=set()
            for sub in ast.walk(node):
                if isinstance(sub,ast.Subscript) and isinstance(sub.value,ast.Name) and sub.value.id==CHECKS_DETAIL_PARAM:
                    sl=sub.slice
                    if isinstance(sl,ast.Constant) and isinstance(sl.value,str): ks.add(sl.value)
            ref=sorted(ks)
    declared=set(E1_LOADER_KEYS); ret=set(x for x in (loader_return or []) if x is not None)
    missing_from_loader=sorted(declared-ret); referenced_not_declared=sorted(set(ref or [])-declared)
    ok=(loader_found and checks_found and loader_return is not None and all(x is not None for x in loader_return)
        and ret==declared and not referenced_not_declared)
    return {"loader_fn_found":loader_found,"checks_fn_found":checks_found,"declared_keys":list(E1_LOADER_KEYS),
            "loader_return_keys":loader_return,"checks_param":CHECKS_DETAIL_PARAM,"checks_referenced_keys":ref,
            "missing_from_loader":missing_from_loader,"referenced_not_declared":referenced_not_declared,"pass":bool(ok)}

def dump_csv(df,path):
    df.to_csv(path,index=False,encoding="utf-8-sig")
    return {"sha256":sha256_file(path),"size_bytes":path.stat().st_size,"rows":int(len(df))}

def writeback_rows(out,names,wb):
    """R2-3(a): hash-verify each declared analytical artifact after writing."""
    rows=[]; all_ok=bool(names)
    for f in names:
        meta=wb.get(f); p=out/f; status="OK"
        if meta is None: status="NOT_WRITTEN"
        elif not p.is_file(): status="MISSING"
        elif p.stat().st_size<=0: status="EMPTY"
        elif p.stat().st_size!=meta["size_bytes"]: status="SIZE_MISMATCH"
        elif sha256_file(p)!=meta["sha256"]: status="SHA_MISMATCH"
        else:
            try:
                back=pd.read_csv(p,encoding="utf-8-sig")
                if len(back)!=meta["rows"]: status="ROWCOUNT_MISMATCH"
            except Exception as e: status=f"READ_ERROR:{type(e).__name__}"
        all_ok=all_ok and status=="OK"
        rows.append(f"{f}:{status}")
    return all_ok,"; ".join(rows) if rows else "SKIPPED_PREFLIGHT_BLOCKED"

def checks(script,pre,ctx,out,names,network_pf,w01_pf,contract,wb):
    c=ctx.get("c"); cand_detail=ctx.get("cand_detail"); t=ctx.get("t"); net=ctx.get("net"); stats=ctx.get("stats"); q2s=ctx.get("q2s"); sel=ctx.get("sel"); q4d=ctx.get("q4d")
    free=t is not None
    tn=len(t) if free else 0; target_ids=set(t.LinkID) if free else set()
    SK="SKIPPED_PREFLIGHT_BLOCKED"
    if free:
        cc=len(target_ids & set(c.lta_linkid))/tn if tn else np.nan
        dc=(q2s.direction_valid_n.gt(0).sum()/tn) if tn else np.nan
        ac=len(target_ids & set(sel.lta_linkid))/tn if tn else np.nan
        xy=sel.matsim_link_id.isin(set(net.matsim_link_id)).mean() if len(sel) else np.nan
        nc={r:len(target_ids & set(q4d.loc[q4d.radius_m.eq(r),"LinkID"]))/tn if tn else np.nan for r in RADII}
    else:
        cc=dc=ac=xy=np.nan; nc={r:np.nan for r in RADII}
    existing={p.name for p in out.iterdir() if p.is_file()}; unknown=[x for x in sorted(existing) if x not in names and not transient(x)]
    all_exist=all((out/x).is_file() for x in names); nonempty=all((out/x).stat().st_size>0 for x in names if (out/x).is_file())
    stray=set()
    for dn in EARLIER_NODES:
        d=out.parent/dn
        if d.exists(): stray |= {str(p) for p in d.glob("*R2*") if p.is_file()}
    stray=sorted(stray)
    raw_ok=(cand_detail is not None) and cand_detail["raw_rows"]>0 and cand_detail["raw_id_missing"]==0 and cand_detail["raw_bad_tier"]==0
    wb_ok,wb_detail=writeback_rows(out,ANALYTIC_ARTIFACTS if free else [],wb)
    return [
      {"check":"F2V21R2.01_PREREG_HASH","pass":sha256_file(pre).lower()==EXPECTED_PREREG_SHA256.lower(),"detail":sha256_file(pre)},
      {"check":"F2V21R2.02_ZERO_SIMULATION","pass":zero_sim(script),"detail":"AST no subprocess/Java"},
      {"check":"F2V21R2.03_E1_RAW_QUALITY","pass":bool(raw_ok),"detail":json.dumps(cand_detail,ensure_ascii=False) if cand_detail is not None else SK},
      {"check":"F2V21R2.04_E2_TARGET_UNIQUE","pass":bool(free and tn>0 and not t.LinkID.duplicated().any()),"detail":f"target_n={tn}" if free else SK},
      {"check":"F2V21R2.05_NETWORK_PREFLIGHT","pass":pf_network_ok(network_pf),"detail":json.dumps(network_pf,ensure_ascii=False)},
      {"check":"F2V21R2.06_W01_PREFLIGHT","pass":pf_w01_ok(w01_pf),"detail":json.dumps(w01_pf,ensure_ascii=False)},
      {"check":"F2V21R2.07_TARGET_TOTAL_GE100","pass":bool(free and tn>=100),"detail":f"target_n={tn}" if free else SK},
      {"check":"F2V21R2.08_SECONDARY_GE80","pass":bool(free and int(t.diagnostic_highway.eq("secondary").sum())>=80),"detail":f"secondary={int(t.diagnostic_highway.eq('secondary').sum())}" if free else SK},
      {"check":"F2V21R2.09_TERTIARY_GE15","pass":bool(free and int(t.diagnostic_highway.eq("tertiary").sum())>=15),"detail":f"tertiary={int(t.diagnostic_highway.eq('tertiary').sum())}" if free else SK},
      {"check":"F2V21R2.10_E1_COVERAGE_GE95","pass":bool(np.isfinite(cc) and cc>=.95),"detail":f"coverage={cc:.6f}" if np.isfinite(cc) else SK},
      {"check":"F2V21R2.11_DIRECTION_COVERAGE_GE95","pass":bool(np.isfinite(dc) and dc>=.95),"detail":f"coverage={dc:.6f}" if np.isfinite(dc) else SK},
      {"check":"F2V21R2.12_AB_ANCHOR_COVERAGE_GE95","pass":bool(np.isfinite(ac) and ac>=.95),"detail":f"coverage={ac:.6f}" if np.isfinite(ac) else SK},
      {"check":"F2V21R2.13_ANCHOR_COORD_GE99","pass":bool(np.isfinite(xy) and xy>=.99),"detail":f"coverage={xy:.6f}" if np.isfinite(xy) else SK},
      {"check":"F2V21R2.14_NEIGHBOR_GE95_EACH_RADIUS","pass":bool(free and all(np.isfinite(v) and v>=.95 for v in nc.values())),"detail":json.dumps({str(k):v for k,v in nc.items()}) if free else SK},
      {"check":"F2V21R2.15_OUTPUT_PROVENANCE","pass":bool(all_exist and nonempty and not unknown and out.name==OUT_REL.name),"detail":f"declared={len(names)}; all_exist={all_exist}; nonempty={nonempty}; unknown={unknown}"},
      {"check":"F2V21R2.16_ISOLATION","pass":not stray,"detail":str(stray)},
      {"check":"F2V21R2.17_WRITEBACK_VERIFICATION","pass":bool(free and wb_ok),"detail":wb_detail},
      {"check":"F2V21R2.18_LOADER_CHECKS_CONTRACT","pass":bool(contract["pass"]),"detail":json.dumps(contract,ensure_ascii=False)},
    ]

def report(out,t,q2s,q2c,q4s,groups,cks,status,boundary):
    L=["# Step 7.9F-2 v2.1-R2 — Execution / Contract Closure Repair","",f"**STATUS: {status}**","","ZERO SIMULATION / READ-ONLY / DIAGNOSTIC ONLY.",""]
    if t is None:
        L += ["## Domain","","Not evaluated: preflight / contract closure blocked this node before any loader ran.",""]
    else:
        L += ["## Domain",f"- target={len(t):,}; secondary={int(t.diagnostic_highway.eq('secondary').sum())}; tertiary={int(t.diagnostic_highway.eq('tertiary').sum())}","",
              "## Q2","","| Highway | n | median forward | median reverse | median neutral | median direction |","|---|---:|---:|---:|---:|---:|"]
        for _,r in groups.iterrows():
            neutral=float(q2s.loc[q2s.diagnostic_highway.eq(r.diagnostic_highway),"neutral_share"].median()); L.append(f"| {r.diagnostic_highway} | {int(r.n)} | {r.median_forward_share:.4f} | {r.median_reverse_share:.4f} | {neutral:.4f} | {r.median_direction_diff_deg:.2f} |")
        L += ["","| Metric | n | Spearman |","|---|---:|---:|"]
        for _,r in q2c.iterrows():
            rho="NaN" if pd.isna(r.spearman_with_frozen_residual) else f"{r.spearman_with_frozen_residual:.4f}"; L.append(f"| {r.metric} | {int(r.n)} | {rho} |")
        L += ["","## Q4","","| Highway | Radius | Type | n all | n valid | median best ratio | median error change | improved share valid | missing share |","|---|---:|---|---:|---:|---:|---:|---:|---:|"]
        for _,r in q4s.iterrows(): L.append(f"| {r.diagnostic_highway} | {int(r.radius_m)} | {r.neighbor_type} | {int(r.n_all_target)} | {int(r.n_valid_capture_change)} | {r.median_best_single_link_ratio:.4f} | {r.median_capture_error_change:.4f} | {r.capture_improved_share_valid:.2%} | {r.capture_missing_share:.2%} |")
    L += ["","## Gates","","| Check | Result | Detail |","|---|---|---|"]
    for c in cks: L.append(f"| {c['check']} | {'PASS' if c['pass'] else 'FAIL'} | {c['detail']} |")
    L += ["","## Boundary","",boundary,""]
    (out/ART_REPORT).write_text("\n".join(L),encoding="utf-8")

def pass_col(df):
    """Robust bool parse: never let the string 'False' become truthy."""
    return df["pass"].map(lambda v: str(v).strip().lower() in ("true","1"))

CLOSURE_COLS=["kind","artifact","exists","size_bytes","size_expected","size_match","nonempty","sha256_disk","sha256_expected","sha_match","note"]

def closure_reconcile(out,names,status,expected):
    """R2-3(c): re-hash the declared payload against the write-time record and re-read
    the status carriers. Verdict is materialised, never a bare assert."""
    subj=[n for n in names if n not in (ART_CLOSURE,ART_MANIFEST)]
    rows=[]; payload_ok=bool(subj)
    for f in subj:
        p=out/f; exp=expected.get(f); ex=p.is_file(); sz=p.stat().st_size if ex else -1
        szx=exp["size_bytes"] if exp is not None else None; sza=bool(exp is not None and ex and sz==szx)
        dh=sha256_file(p) if ex else ""; eh=(exp["sha256"] if exp is not None else "")
        sha_ok=bool(eh and dh==eh)
        ok=bool(ex and sz>0 and sza and sha_ok)
        payload_ok=payload_ok and ok
        rows.append({"kind":"artifact","artifact":f,"exists":ex,"size_bytes":sz,"size_expected":(szx if szx is not None else ""),
                     "size_match":sza,"nonempty":bool(ex and sz>0),"sha256_disk":dh,"sha256_expected":eh,"sha_match":sha_ok,
                     "note":"" if ok else "NOT_OK"})
    disk_payload={p.name for p in out.iterdir() if p.is_file()} - {ART_CLOSURE,ART_MANIFEST}
    declared_ok=(disk_payload==set(subj))
    rows.append({"kind":"declared_count","artifact":"declared_set_vs_disk","exists":declared_ok,"size_bytes":len(subj),
                 "size_expected":len(subj),"size_match":declared_ok,"nonempty":True,"sha256_disk":"","sha256_expected":"",
                 "sha_match":declared_ok,"note":f"missing={sorted(set(subj)-disk_payload)}; extra={sorted(disk_payload-set(subj))}"})
    ck=pd.read_csv(out/ART_CHECKS,encoding="utf-8-sig"); pass_all=bool(pass_col(ck).all()); n_fail=int((~pass_col(ck)).sum())
    sm=json.loads((out/ART_SUMMARY).read_text(encoding="utf-8")); status_summary=sm.get("status")
    rp=(out/ART_REPORT).read_text(encoding="utf-8"); report_match=f"**STATUS: {status}**" in rp
    checks_match_summary=(status_summary==status); checks_match_verdict=(pass_all==status.endswith("READY"))
    trio=checks_match_summary and checks_match_verdict and report_match
    for nm,val,note in [("checks_all_pass",pass_all,f"n_fail={n_fail}"),("summary_status",checks_match_summary,str(status_summary)),
                        ("report_status_match",report_match,status),("checks_vs_verdict",checks_match_verdict,"")]:
        rows.append({"kind":"status_consistency","artifact":nm,"exists":bool(val),"size_bytes":-1,"size_expected":"","size_match":True,
                     "nonempty":True,"sha256_disk":"","sha256_expected":"","sha_match":True,"note":note})
    ok=bool(payload_ok and declared_ok and trio)
    rows.append({"kind":"closure_verdict","artifact":"CLOSURE_OK","exists":ok,"size_bytes":len(subj),"size_expected":"","size_match":True,
                 "nonempty":True,"sha256_disk":"","sha256_expected":"","sha_match":True,"note":f"payload_ok={payload_ok}"})
    pd.DataFrame(rows).reindex(columns=CLOSURE_COLS).to_csv(out/ART_CLOSURE,index=False,encoding="utf-8-sig")
    return ok

def final_assertions(out,names,status):
    """R2-3(d): manifest <-> disk two-way reconciliation, materialised (never a bare assert)."""
    rows=[]; ok=True
    manifest=json.loads((out/ART_MANIFEST).read_text(encoding="utf-8")); ga=manifest.get("generated_artifacts",{})
    declared=set(n for n in names if n not in (ART_CLOSURE,ART_MANIFEST))
    same=set(ga)==declared; ok=ok and same
    rows.append({"kind":"final_assertion","artifact":"manifest_declared_set","exists":same,"size_bytes":len(ga),"size_expected":len(declared),
                 "size_match":same,"nonempty":True,"sha256_disk":"","sha256_expected":"","sha_match":same,
                 "note":f"missing={sorted(declared-set(ga))}; extra={sorted(set(ga)-declared)}"})
    for f,meta in ga.items():
        p=out/f; good=bool(p.is_file() and p.stat().st_size==meta["size_bytes"] and sha256_file(p)==meta["sha256"])
        ok=ok and good
        rows.append({"kind":"final_assertion","artifact":f"manifest_vs_disk::{f}","exists":good,"size_bytes":(p.stat().st_size if p.is_file() else -1),
                     "size_expected":meta["size_bytes"],"size_match":bool(p.is_file() and p.stat().st_size==meta["size_bytes"]),"nonempty":True,
                     "sha256_disk":(sha256_file(p) if p.is_file() else ""),"sha256_expected":meta["sha256"],
                     "sha_match":bool(p.is_file() and sha256_file(p)==meta["sha256"]),"note":"" if good else "NOT_OK"})
    ck=pd.read_csv(out/ART_CHECKS,encoding="utf-8-sig"); sm=json.loads((out/ART_SUMMARY).read_text(encoding="utf-8")); rp=(out/ART_REPORT).read_text(encoding="utf-8")
    trio=(bool(pass_col(ck).all())==status.endswith("READY")) and sm.get("status")==status and f"**STATUS: {status}**" in rp
    ok=ok and trio
    rows.append({"kind":"final_assertion","artifact":"status_three_way","exists":bool(trio),"size_bytes":-1,"size_expected":"","size_match":True,
                 "nonempty":True,"sha256_disk":"","sha256_expected":"","sha_match":True,"note":""})
    pd.DataFrame(rows).reindex(columns=CLOSURE_COLS).to_csv(out/ART_CLOSURE,mode="a",header=False,index=False,encoding="utf-8-sig")
    return bool(ok)

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--project-root",type=Path,default=ROOT_DEFAULT); ap.add_argument("--traffic",type=Path); ap.add_argument("--e1-candidates",type=Path); ap.add_argument("--e2",type=Path); ap.add_argument("--network",type=Path); ap.add_argument("--nodes",type=Path); ap.add_argument("--w01-linkstats",type=Path); ap.add_argument("--prereg",type=Path); ap.add_argument("--out-dir",type=Path,default=OUT_REL)
    a=ap.parse_args(); root=a.project_root; tp=a.traffic or root/TRAFFIC_REL; cp=a.e1_candidates or root/E1_REL; ep=a.e2 or root/E2_REL; npth=a.network or root/NETWORK_REL; npath=a.nodes or root/NODES_REL; pp=a.prereg or root/PREREG_REL; wp=locate_w01(root,a.w01_linkstats); out=a.out_dir if a.out_dir.is_absolute() else root/a.out_dir; out.mkdir(parents=True,exist_ok=True)
    for p in [tp,cp,ep,npth,npath,wp,pp]:
        if not p.exists(): raise FileNotFoundError(f"输入不存在: {p}")
    script=Path(__file__).resolve()
    print("="*92); print("STEP 7.9F-2 v2.1-R2 | EXECUTION / CONTRACT CLOSURE REPAIR"); print("ZERO SIMULATION / READ-ONLY / DIAGNOSTIC ONLY"); print(f"PREREG SHA={sha256_file(pp)}"); print(f"W01={wp}"); print(f"OUTPUT={out}")

    # ---- R2-2: preflight is the sole authority. Nothing below this line may raise before a gate. ----
    contract=contract_check(script)
    network_pf,network_err=pf_guard(preflight_network,npth,npath)
    if network_pf is None: network_pf={"network_duplicate_link_id":None,"node_duplicate_id":None,"node_required_missing":[],"error":network_err}
    else: network_pf["error"]=""
    w01_pf,w01_err=pf_guard(preflight_w01,wp)
    if w01_pf is None: w01_pf={"missing":[],"duplicate_link":None,"error":w01_err}
    else: w01_pf["error"]=""
    prereg_ok=sha256_file(pp).lower()==EXPECTED_PREREG_SHA256.lower(); zs_ok=zero_sim(script)
    early_ok=bool(contract["pass"] and pf_network_ok(network_pf) and pf_w01_ok(w01_pf) and prereg_ok and zs_ok)
    print(f"PREFLIGHT contract={contract['pass']} network={pf_network_ok(network_pf)} w01={pf_w01_ok(w01_pf)} prereg={prereg_ok} zero_sim={zs_ok} -> early_ok={early_ok}")

    ctx={k:None for k in ("c","cand_detail","t","net","stats","q2s","sel","q4d")}; wb={}; names=NAMES_BLOCKED
    if early_ok:
        names=NAMES_FULL
        traffic=traffic_obs(tp); cand,cand_detail=e1_load(cp); e2=e2_load(ep); net=network_load(npth,npath); stats=w01_load(wp)
        target=e2[e2.diagnostic_highway.isin(TARGET_HW)&e2.valid_residual&e2.obs_8_9.gt(0)].copy(); target_ids=set(target.LinkID)
        if target.LinkID.duplicated().any(): raise AssertionError("target LinkID duplicated")
        obscheck=target[["LinkID","obs_8_9"]].merge(traffic,on="LinkID",how="left",validate="one_to_one"); obscheck["abs_delta"]=(obscheck.obs_8_9-obscheck.obs_8_9_rebuilt).abs()
        selected=select_ab(cand); selected=selected[selected.lta_linkid.isin(target_ids)].copy(); q2s,q2l=q2(cand[cand.lta_linkid.isin(target_ids)],target); q2c=q2corr(q2s); q4d=q4(target,selected,net,stats); q4s=q4sum(q4d); groups=group_sum(q2s,q4d)
        ctx.update({"c":cand,"cand_detail":cand_detail,"t":target,"net":net,"stats":stats,"q2s":q2s,"sel":selected,"q4d":q4d})
        wb[ART_TARGET]=dump_csv(target,out/ART_TARGET); wb[ART_E1]=dump_csv(cand[cand.lta_linkid.isin(target_ids)],out/ART_E1); wb[ART_AB]=dump_csv(selected,out/ART_AB); wb[ART_Q2SUM]=dump_csv(q2s,out/ART_Q2SUM); wb[ART_Q2LONG]=dump_csv(q2l,out/ART_Q2LONG); wb[ART_Q2CORR]=dump_csv(q2c,out/ART_Q2CORR); wb[ART_GROUP]=dump_csv(groups,out/ART_GROUP); wb[ART_Q4DETAIL]=dump_csv(q4d,out/ART_Q4DETAIL); wb[ART_Q4SUM]=dump_csv(q4s,out/ART_Q4SUM); wb[ART_OBS]=dump_csv(obscheck,out/ART_OBS)
    else:
        target=None; groups=None; q2c=None; q4s=None

    boundary=("R2 仅修复执行/契约/闭环问题（R2-1/2/3）；Q2/Q4 定义、阈值、样本域、SCALE、E2 frozen residual 未变。P2-8/P2-10/P2-11 不在本版本中处理。Q4 仍为 diagnostic single-link capture，不是网络守恒或因果证明。" if early_ok else
              "本节点在 loader 运行前即被 preflight / 契约门禁拦下并受控收口；未产生任何分析产物。")
    # placeholders only for the declared non-analytical artifacts; never touch a written payload
    for f in names:
        if f in ANALYTIC_ARTIFACTS and early_ok: continue
        (out/f).write_text("PENDING\n",encoding="utf-8")
    cks=checks(script,pp,ctx,out,names,network_pf,w01_pf,contract,wb)
    status=ST_READY if all(bool(x["pass"]) for x in cks) else ST_BLOCKED
    pd.DataFrame(cks).to_csv(out/ART_CHECKS,index=False,encoding="utf-8-sig")
    wb[ART_CHECKS]={"sha256":sha256_file(out/ART_CHECKS),"size_bytes":(out/ART_CHECKS).stat().st_size,"rows":len(cks)}
    summary={"step":"7.9F-2 v2.1-R2","status":status,"zero_simulation":True,"network_modified":False,"matsim_rerun":False,
             "preflight_passed":early_ok,"target_n":(len(target) if target is not None else None),"secondary_n":(int(target.diagnostic_highway.eq("secondary").sum()) if target is not None else None),
             "tertiary_n":(int(target.diagnostic_highway.eq("tertiary").sum()) if target is not None else None),"e1_candidate_rows":(len(ctx["c"]) if ctx["c"] is not None else None),
             "selected_anchor_rows":(len(ctx["sel"]) if ctx["sel"] is not None else None),"network_links":(len(ctx["net"]) if ctx["net"] is not None else None),
             "w01_links":(len(ctx["stats"]) if ctx["stats"] is not None else None),"obs_rebuild_max_abs_delta":(float(obscheck.abs_delta.max()) if early_ok and len(obscheck) else None),
             "prereg_sha256":sha256_file(pp),"hard_pass_count":int(sum(bool(x["pass"]) for x in cks)),"hard_total":len(cks),"contract_pass":bool(contract["pass"])}
    (out/ART_SUMMARY).write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding="utf-8")
    wb[ART_SUMMARY]={"sha256":sha256_file(out/ART_SUMMARY),"size_bytes":(out/ART_SUMMARY).stat().st_size,"rows":None}
    report(out,target,(ctx["q2s"] if ctx["q2s"] is not None else None),q2c,q4s,groups,cks,status,boundary)
    wb[ART_REPORT]={"sha256":sha256_file(out/ART_REPORT),"size_bytes":(out/ART_REPORT).stat().st_size,"rows":None}
    closure_ok=closure_reconcile(out,names,status,wb)
    inputs={"traffic_json":tp,"e1_candidates":cp,"e2":ep,"network":npth,"nodes":npath,"w01":wp,"prereg":pp,"script":script}
    manifest={"step":"7.9F-2 v2.1-R2","revision":REVISION,"prereg_sha256":sha256_file(pp)}
    manifest.update({k:{"path":str(p),"sha256":sha256_file(p),"size_bytes":p.stat().st_size} for k,p in inputs.items()})
    manifest["protocol"]={"scale":SCALE,"radii_m":RADII,"forward_max_deg":FWD,"reverse_min_deg":REV,"q2_domain":"all E1 stored A/B/C candidates","q4_anchor_domain":"F-1/E2 A+B selected","revision":REVISION}
    manifest["generated_artifacts"]={f:{"sha256":sha256_file(out/f),"size_bytes":(out/f).stat().st_size} for f in names if f not in (ART_MANIFEST,ART_CLOSURE) and (out/f).is_file() and not transient(f)}
    manifest["terminal_closure_artifact"]={"path":ART_CLOSURE,"hashed":False,"note":"written after the manifest and therefore not self-hashed; see closure_check.csv"}
    (out/ART_MANIFEST).write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding="utf-8")
    finals_ok=final_assertions(out,names,status)
    if not (closure_ok and finals_ok):
        esc=f"{status}_CLOSURE_FAILED"
        summary["status"]=esc
        report(out,target,(ctx["q2s"] if ctx["q2s"] is not None else None),q2c,q4s,groups,cks,esc,boundary)
        (out/ART_SUMMARY).write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding="utf-8")
        pd.DataFrame([{"kind":"closure_escalation","artifact":"STATUS_ESCALATED","exists":True,"size_bytes":-1,"size_expected":"","size_match":True,
                       "nonempty":True,"sha256_disk":"","sha256_expected":"","sha_match":True,"note":esc}]).reindex(columns=CLOSURE_COLS).to_csv(out/ART_CLOSURE,mode="a",header=False,index=False,encoding="utf-8-sig")
        print(f"CLOSURE_FAILED closure_ok={closure_ok} final_assertions_ok={finals_ok}; STATUS={esc}"); return 2
    print(f"target={(len(target) if target is not None else 0):,}; E1={(len(ctx['c']) if ctx['c'] is not None else 0):,}; anchors={(len(ctx['sel']) if ctx['sel'] is not None else 0):,}; network={(len(ctx['net']) if ctx['net'] is not None else 0):,}; W01={(len(ctx['stats']) if ctx['stats'] is not None else 0):,}")
    print(f"gates={sum(bool(x['pass']) for x in cks)}/{len(cks)}; STATUS={status}; CLOSURE={'OK' if closure_ok and finals_ok else 'FAIL'}"); print(f"OUTPUT={out}"); print("NOTE=no MATSim/Java call")
    return 0 if status==ST_READY else 1

if __name__=="__main__": raise SystemExit(main())
