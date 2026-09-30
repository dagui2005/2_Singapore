#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""7.9F-2 v2.1 — Direction-relaxed candidates + local single-link capture.
ZERO SIMULATION / READ-ONLY / DIAGNOSTIC ONLY.
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
OUT_REL=Path("reports/secondary_tertiary_residual_7_9f2_v2_1")
PREREG_REL=OUT_REL/"PREREG_7_9F2_v2_1.md"
EXPECTED_PREREG_SHA256="b495e2750b3cdae9ab5be51bd11dee8c4d7743ef0ba3e485cc1c5fe9d45ecf71"
SCALE=459794.0/200000.0
A="A_STRICT_SEMANTIC_DIRECTION"; B="B_DIRECTION_GEOMETRY"; C="C_GEOMETRY_ONLY"
TIERS={A,B,C}; TARGET_HW={"secondary","tertiary"}
RADII=[20.0,50.0,100.0]; FWD=30.0; REV=150.0
TRANSIENT_SUFFIXES=(".uploading.cfg",".tmp"); TRANSIENT_PREFIXES=("~$",".~lock.")


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

def traffic_obs(p):
    obj=json.loads(Path(p).read_text(encoding="utf-8-sig")); rows=obj.get("Value",obj.get("value",[])) if isinstance(obj,dict) else obj; d=pd.DataFrame(rows)
    req={"LinkID","Date","HourOfDate","Volume","RoadName","RoadCat"}; miss=req-set(d.columns)
    if miss: raise ValueError(f"TrafficFlow JSON 缺字段: {sorted(miss)}")
    d["LinkID"]=d["LinkID"].map(nid); d["Date"]=pd.to_datetime(d["Date"],dayfirst=True,errors="coerce"); d["HourOfDate"]=pd.to_numeric(d["HourOfDate"],errors="coerce"); d["Volume"]=num(d["Volume"])
    d=d[d.LinkID.ne("")&d.Date.notna()&d.Date.dt.weekday.lt(5)&d.HourOfDate.eq(8)&d.Volume.notna()].copy()
    daily=d.groupby(["LinkID","Date"],as_index=False).Volume.mean(); o=daily.groupby("LinkID",as_index=False).Volume.median().rename(columns={"Volume":"obs_8_9_rebuilt"})
    return o

def e1_load(p):
    x=pd.read_csv(p,encoding="utf-8-sig",low_memory=False); raw=len(x); lo={str(c).strip().lower():c for c in x.columns}
    mp={"lta_linkid":"lta_linkid","linkid":"lta_linkid","matsim_link_id":"matsim_link_id","matsim_link":"matsim_link_id","tier":"tier","distance_m":"distance_m","geometry_distance_m":"distance_m","direction_diff_deg":"direction_diff_deg","direction_diff":"direction_diff_deg","highway":"highway","semantic_compatible":"semantic_compatible","semantic_ok":"semantic_compatible","name_similarity":"name_similarity","name_sim":"name_similarity"}
    x=x.rename(columns={c:mp[k] for k,c in lo.items() if k in mp}); req={"lta_linkid","matsim_link_id","tier","distance_m","direction_diff_deg","highway"}; miss=req-set(x.columns)
    if miss: raise ValueError(f"E1 candidates 缺字段: {sorted(miss)}")
    x.lta_linkid=x.lta_linkid.map(nid); x.matsim_link_id=x.matsim_link_id.map(nid); x.tier=x.tier.map(nt); x.distance_m=num(x.distance_m); x.direction_diff_deg=num(x.direction_diff_deg); x.highway=x.highway.map(nt).str.lower()
    x=x[x.lta_linkid.ne("")&x.matsim_link_id.ne("")&x.tier.isin(TIERS)&x.distance_m.notna()].copy(); x=x.drop_duplicates(["lta_linkid","matsim_link_id","tier"])
    return x,{"raw_rows":raw,"kept_rows":len(x),"dropped_rows":raw-len(x),"tier_counts":x.tier.value_counts().to_dict()}

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
    g=pd.read_csv(p,usecols=["from_node","to_node","length_m","highway","name"],encoding="utf-8-sig",low_memory=False); g.from_node=g.from_node.map(nid); g.to_node=g.to_node.map(nid); g.length_m=num(g.length_m); g.highway=g.highway.map(nt).str.lower(); g.name=g.name.map(nt); g.name_norm=g.name.map(nn); g["matsim_link_id"]="e"+g.from_node+"_"+g.to_node; g=g[g.from_node.ne("")&g.to_node.ne("")&g.length_m.gt(0)].copy();
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
        [valid & l.direction_diff_deg.le(FWD), valid & l.direction_diff_deg.ge(REV)],
        ["FORWARD", "REVERSE"],
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
                out.append({"LinkID":sid,"diagnostic_highway":tt.diagnostic_highway.iloc[0],"diagnostic_residual_8_9":tt.diagnostic_residual_8_9.iloc[0],"obs_8_9":obs,"canonical_ratio_e2":cr,"canonical_abs_error_e2":ce,"radius_m":rad,"neighbor_type":typ,"neighbor_n":len(ids),"neighbor_positive_flow_n":sum(v>0 for v in vals),"best_single_link_flow_raw":bf,"best_single_link_ratio":br,"best_single_link_abs_error":be,"capture_error_change":ch,"capture_improved":bool(ch<0) if np.isfinite(ch) else False})
    return pd.DataFrame(out)

def q4sum(q):
    rows=[]
    for (hw,r,typ),g in q.groupby(["diagnostic_highway","radius_m","neighbor_type"]):
        z=g.best_single_link_ratio.dropna(); ch=g.capture_error_change.dropna(); rows.append({"diagnostic_highway":hw,"radius_m":r,"neighbor_type":typ,"n":len(g),"positive_flow_prevalence":float(g.neighbor_positive_flow_n.gt(0).mean()),"median_neighbor_n":float(g.neighbor_n.median()),"median_best_single_link_ratio":float(z.median()) if len(z) else np.nan,"median_capture_error_change":float(ch.median()) if len(ch) else np.nan,"capture_improved_share":float(g.capture_improved.mean())})
    return pd.DataFrame(rows)

def group_sum(s,q):
    rows=[]
    for hw in ["secondary","tertiary"]:
        a=s[s.diagnostic_highway.eq(hw)]; b=q[(q.diagnostic_highway.eq(hw))&(q.radius_m.eq(100.0))]; p=b[b.neighbor_type.eq("parallel")]; tw=b[b.neighbor_type.eq("twin")]
        rows.append({"diagnostic_highway":hw,"n":len(a),"median_reverse_share":a.reverse_share.median(),"median_forward_share":a.forward_share.median(),"median_direction_diff_deg":a.median_direction_diff_deg.median(),"reverse_any_prevalence":a.reverse_any.mean(),"median_C_reverse_share":a[f"{C}_reverse_share"].median(),"parallel_positive_flow_share_100m":float(p.neighbor_positive_flow_n.gt(0).mean()) if len(p) else np.nan,"twin_positive_flow_share_100m":float(tw.neighbor_positive_flow_n.gt(0).mean()) if len(tw) else np.nan})
    return pd.DataFrame(rows)

def checks(script,pre,c,t,net,stats,q2s,sel,q4d,out,names):
    tn=len(t); cc=safe_cov=t.LinkID.isin(set(c.lta_linkid)).mean() if tn else np.nan; dc=(q2s.direction_valid_n.gt(0).sum()/tn) if tn else np.nan; ac=(t.LinkID.isin(set(sel.lta_linkid)).mean()) if tn else np.nan; xy=sel.matsim_link_id.isin(set(net.matsim_link_id)).mean() if len(sel) else np.nan
    nc={r:((set(t.LinkID)&set(q4d.loc[q4d.radius_m.eq(r),"LinkID"])).__len__()/tn if tn else np.nan) for r in RADII}
    existing={p.name for p in out.iterdir() if p.is_file()}; unknown=[x for x in existing if x not in names and not transient(x)]; tr=[x for x in existing if transient(x)]; all_exist=all((out/x).is_file() for x in names)
    return [{"check":"F2V21.01_PREREG_HASH","pass":sha256_file(pre).lower()==EXPECTED_PREREG_SHA256.lower(),"detail":sha256_file(pre)},{"check":"F2V21.02_ZERO_SIMULATION","pass":zero_sim(script),"detail":"AST no subprocess/Java"},{"check":"F2V21.03_E1_CANDIDATES","pass":len(c)>0 and c.tier.isin(TIERS).all(),"detail":f"rows={len(c):,}"},{"check":"F2V21.04_E2_TARGET","pass":tn>0,"detail":f"target_n={tn}"},{"check":"F2V21.05_NETWORK","pass":len(net)>0 and not net.matsim_link_id.duplicated().any(),"detail":f"links_with_coords={len(net):,}"},{"check":"F2V21.06_W01","pass":len(stats)>0 and not stats.LINK.duplicated().any(),"detail":f"w01_links={len(stats):,}"},{"check":"F2V21.07_TARGET_TOTAL_GE100","pass":tn>=100,"detail":f"target_n={tn}"},{"check":"F2V21.08_SECONDARY_GE80","pass":int((t.diagnostic_highway=="secondary").sum())>=80,"detail":f"secondary={int((t.diagnostic_highway=="secondary").sum())}"},{"check":"F2V21.09_TERTIARY_GE15","pass":int((t.diagnostic_highway=="tertiary").sum())>=15,"detail":f"tertiary={int((t.diagnostic_highway=="tertiary").sum())}"},{"check":"F2V21.10_E1_CAND_COVERAGE_GE95","pass":cc>=.95,"detail":f"coverage={cc:.6f}"},{"check":"F2V21.11_DIRECTION_COVERAGE_GE95","pass":dc>=.95,"detail":f"coverage={dc:.6f}"},{"check":"F2V21.12_AB_ANCHOR_COVERAGE_GE95","pass":ac>=.95,"detail":f"coverage={ac:.6f}"},{"check":"F2V21.13_ANCHOR_COORD_GE99","pass":xy>=.99,"detail":f"coverage={xy:.6f}"},{"check":"F2V21.14_LOCAL_NEIGHBOR_GE95","pass":all(np.isfinite(x) and x>=.95 for x in nc.values()),"detail":f"coverage_by_radius={nc}"},{"check":"F2V21.15_OUTPUT_PROVENANCE","pass":all_exist and not unknown and out.name==OUT_REL.name,"detail":f"declared={len(names)}; all_declared_exist={all_exist}; unknown_stray={unknown}; ignored_transient={tr}"},{"check":"F2V21.16_V2_1_ISOLATION","pass":not list((out.parent/"secondary_tertiary_residual_7_9f2").glob("f2v21_*")),"detail":"isolated from F-2 v2 directory"}]

def report(out,t,q2s,q2c,q4s,groups,cks,status):
    L=["# Step 7.9F-2 v2.1 — Direction-Relaxed Candidate & Local Single-Link Capture Diagnostic","",f"**STATUS: {status}**","","## Domain",f"- target={len(t):,}; secondary={int((t.diagnostic_highway=='secondary').sum())}; tertiary={int((t.diagnostic_highway=='tertiary').sum())}","","## Q2 direction-relaxed candidate", "","| Highway | n | Median forward | Median reverse | Median direction | Reverse-any | Median C reverse |","|---|---:|---:|---:|---:|---:|---:|"]
    for _,r in groups.iterrows():L.append(f"| {r.diagnostic_highway} | {int(r.n)} | {r.median_forward_share:.3f} | {r.median_reverse_share:.3f} | {r.median_direction_diff_deg:.2f} | {r.reverse_any_prevalence:.2%} | {r.median_C_reverse_share:.3f} |")
    L += ["","| Metric | n | Spearman |","|---|---:|---:|"]
    for _,r in q2c.iterrows():L.append(f"| {r.metric} | {int(r.n)} | {'NaN' if pd.isna(r.spearman_with_frozen_residual) else f'{r.spearman_with_frozen_residual:.4f}'} |")
    L += ["","## Q4 single-link capture","","| Highway | Radius | Type | n | Positive flow | Median best ratio | Median error change | Improved share |","|---|---:|---|---:|---:|---:|---:|---:|"]
    for _,r in q4s.iterrows():L.append(f"| {r.diagnostic_highway} | {int(r.radius_m)} | {r.neighbor_type} | {int(r.n)} | {r.positive_flow_prevalence:.2%} | {r.median_best_single_link_ratio:.4f} | {r.median_capture_error_change:.4f} | {r.capture_improved_share:.2%} |")
    L += ["","## Gates","","| Check | Result | Detail |","|---|---|---|"]
    for c in cks:L.append(f"| {c['check']} | {'PASS' if c['pass'] else 'FAIL'} | {c['detail']} |")
    L += ["","## Boundary","","Q2 reverse-share 仅反映 E1 stored candidate evidence；Q4 single-link capture 不是 observed network flow conservation 证明，不自动支持模型参数修改。",""]
    (out/"STEP7_9F2_v2_1_REPORT.md").write_text("\n".join(L),encoding="utf-8")

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--project-root",type=Path,default=ROOT_DEFAULT); ap.add_argument("--traffic",type=Path); ap.add_argument("--e1-candidates",type=Path); ap.add_argument("--e2",type=Path); ap.add_argument("--network",type=Path); ap.add_argument("--nodes",type=Path); ap.add_argument("--w01-linkstats",type=Path); ap.add_argument("--prereg",type=Path); ap.add_argument("--out-dir",type=Path,default=OUT_REL); a=ap.parse_args(); root=a.project_root
    tp=a.traffic or root/TRAFFIC_REL; cp=a.e1_candidates or root/E1_REL; ep=a.e2 or root/E2_REL; npth=a.network or root/NETWORK_REL; npath=a.nodes or root/NODES_REL; wp=a.w01_linkstats or root/W01_REL; pp=a.prereg or root/PREREG_REL; out=a.out_dir if a.out_dir.is_absolute() else root/a.out_dir; out.mkdir(parents=True,exist_ok=True)
    for p in [tp,cp,ep,npth,npath,wp,pp]:
        if not p.exists():raise FileNotFoundError(f"输入不存在: {p}")
    print("="*92); print("STEP 7.9F-2 v2.1 | DIRECTION-RELAXED + SINGLE-LINK CAPTURE"); print("ZERO SIMULATION / READ-ONLY / DIAGNOSTIC ONLY"); print(f"Prereg SHA={sha256_file(pp)}")
    traffic=traffic_obs(tp); cand,detail=e1_load(cp); e2=e2_load(ep); net=network_load(npth,npath); stats=w01_load(wp)
    target=e2[e2.diagnostic_highway.isin(TARGET_HW)&e2.valid_residual&e2.obs_8_9.gt(0)].copy()
    selected=select_ab(cand); selected=selected[selected.lta_linkid.isin(set(target.LinkID))].copy();
    q2s,q2l=q2(cand[cand.lta_linkid.isin(set(target.LinkID))],target); q2c=q2corr(q2s); q4d=q4(target,selected,net,stats); q4s=q4sum(q4d); groups=group_sum(q2s,q4d)
    obscheck=target[["LinkID","obs_8_9"]].merge(traffic,on="LinkID",how="left",validate="one_to_one"); obscheck["abs_delta"]=(obscheck.obs_8_9-obscheck.obs_8_9_rebuilt).abs()
    names=["f2v21_target_sections.csv","f2v21_all_e1_candidates.csv","f2v21_selected_ab_candidates.csv","f2v21_direction_candidate_summary.csv","f2v21_direction_candidate_long.csv","f2v21_q2_correlations.csv","f2v21_group_summary.csv","f2v21_single_link_anchor_summary.csv","f2v21_single_link_capture.csv","f2v21_q4_summary.csv","f2v21_obs_rebuild_check.csv","f2v21_checks.csv","f2v21_input_manifest.json","f2v21_summary.json","STEP7_9F2_v2_1_REPORT.md"]
    target.to_csv(out/names[0],index=False,encoding="utf-8-sig"); cand[cand.lta_linkid.isin(set(target.LinkID))].to_csv(out/names[1],index=False,encoding="utf-8-sig"); selected.to_csv(out/names[2],index=False,encoding="utf-8-sig"); q2s.to_csv(out/names[3],index=False,encoding="utf-8-sig"); q2l.to_csv(out/names[4],index=False,encoding="utf-8-sig"); q2c.to_csv(out/names[5],index=False,encoding="utf-8-sig"); groups.to_csv(out/names[6],index=False,encoding="utf-8-sig");
    anchor=target[["LinkID","diagnostic_highway","obs_8_9","sim_8_9_scaled","diagnostic_residual_8_9"]].merge(selected.groupby("lta_linkid")["matsim_link_id"].nunique().rename("selected_anchor_n"),left_on="LinkID",right_index=True,how="left"); anchor.to_csv(out/names[7],index=False,encoding="utf-8-sig"); q4d.to_csv(out/names[8],index=False,encoding="utf-8-sig"); q4s.to_csv(out/names[9],index=False,encoding="utf-8-sig"); obscheck.to_csv(out/names[10],index=False,encoding="utf-8-sig")
    (out/names[11]).write_text("PENDING\n",encoding="utf-8"); (out/names[12]).write_text("PENDING\n",encoding="utf-8"); (out/names[13]).write_text(json.dumps({"step":"7.9F-2 v2.1","status":"PENDING"},ensure_ascii=False,indent=2),encoding="utf-8"); report(out,target,q2s,q2c,q4s,groups,[],"PENDING")
    cks=checks(Path(__file__).resolve(),pp,cand,target,net,stats,q2s,selected,q4d,out,names); status="LOCAL_CAPTURE_DIAGNOSTIC_READY" if all(x["pass"] for x in cks) else "LOCAL_CAPTURE_DIAGNOSTIC_BLOCKED"; pd.DataFrame(cks).to_csv(out/names[11],index=False,encoding="utf-8-sig"); summ={"step":"7.9F-2 v2.1","status":status,"zero_simulation":True,"network_modified":False,"matsim_rerun":False,"target_n":len(target),"secondary_n":int((target.diagnostic_highway=="secondary").sum()),"tertiary_n":int((target.diagnostic_highway=="tertiary").sum()),"candidate_raw_rows":detail["raw_rows"],"candidate_kept_rows":detail["kept_rows"],"selected_anchor_rows":len(selected),"obs_rebuild_max_abs_delta":float(obscheck.abs_delta.max()),"prereg_sha256":sha256_file(pp),"hard_pass_count":int(sum(x["pass"] for x in cks)),"hard_total":len(cks)}; (out/names[13]).write_text(json.dumps(summ,ensure_ascii=False,indent=2),encoding="utf-8"); report(out,target,q2s,q2c,q4s,groups,cks,status)
    inputs={"traffic_json":tp,"e1_candidates":cp,"e2":ep,"network":npth,"nodes":npath,"w01":wp,"prereg":pp,"script":Path(__file__).resolve()}; manifest={k:{"path":str(p),"sha256":sha256_file(p),"size_bytes":p.stat().st_size} for k,p in inputs.items()}; manifest["generated_artifacts"]={f:{"sha256":sha256_file(out/f),"size_bytes":(out/f).stat().st_size} for f in names if f!="f2v21_input_manifest.json" and (out/f).exists() and not transient(f)}; (out/names[12]).write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding="utf-8")
    print(f"target={len(target):,}; E1 candidates={len(cand):,}; anchors={len(selected):,}; network={len(net):,}; W01={len(stats):,}"); print(f"gates={sum(x['pass'] for x in cks)}/{len(cks)}; STATUS={status}"); print(f"OUTPUT={out}"); print("NOTE=no MATSim/Java call"); return 0 if status=="LOCAL_CAPTURE_DIAGNOSTIC_READY" else 1

if __name__=="__main__":raise SystemExit(main())
