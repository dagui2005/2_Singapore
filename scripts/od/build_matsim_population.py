#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Step 6.2: convert car-only prior OD candidates into MATSim populations."""
from __future__ import annotations
import argparse, gzip, json, math, re
from pathlib import Path
import numpy as np
import pandas as pd
import xml.etree.ElementTree as ET

ROOT_DEFAULT = Path(r"D:\Luan\2026-05\2_Singapore")
PROD = Path("reports/od_production/production.csv")
MODE = Path("reports/od_production/zone_mode_shares.csv")
ATTR = Path("reports/od_attraction_v21/attraction_v21.csv")
ATTR_DIR = Path("reports/od_attraction_v21")
PRIOR_DIR = Path("reports/od_prior_5c1")
ZONE_MAP = Path("reports/matsim_network/zone_matsim_node_map.csv")
NETWORK = Path("reports/matsim_network/network_links_source_copy.csv")
SNAP = Path("reports/od_impedance/zone_network_snap.csv")
# Frozen v2.1 workplace attraction with no-road-access destinations zeroed
# (identical in Step 5B and Step 5C.1). Used as the car destination margin so its
# support matches the sparse 5C.1 prior OD support and IPF can converge exactly.
CLEAN_ATTR_CANDIDATES = [
    "reports/od_prior_5c1/attraction_clean_5c1.csv",
    "reports/od_prior_5b/attraction_carbon.csv",
]
T11 = Path("Singapore_OD_MATSim_FinalData/03_Workplace_Employment/outputFile (3)__T11.csv")
OUT = Path("reports/matsim_population")
REGIONS = ["Central Region", "East Region", "North Region", "North-East Region", "West Region"]
CAR_FRAGMENT = "car or taxi/private hire car only"
DEFAULT_LAMBDAS = [0.05, 0.075, 0.10]
DEFAULT_AGENTS = 200_000
SEED = 20260912

def norm(x):
    if pd.isna(x): return ""
    return re.sub(r"\s+", " ", str(x).replace("\xa0", " ").strip())

def nn(x): return norm(x).upper()

def nums(s):
    return pd.to_numeric(s.astype(str).str.replace(",", "", regex=False), errors="coerce")

def find_attr(root):
    for n in ["attraction_v21.csv", "attraction_v2.1.csv", "attraction_v2.csv"]:
        p=root/ATTR_DIR/n
        if p.exists(): return p
    raise FileNotFoundError(f"No attraction file in {root/ATTR_DIR}")

def load_clean_attraction(root, raw):
    """Frozen v2.1 workplace attraction, i.e. with no-road-access destinations zeroed
    and the remainder renormalized within each Workplace PA (Step 5B/5C.1 convention).

    The raw attraction_v21.csv keeps a nonzero workplace_attraction for 3 no-road-access
    Subzones; the frozen prior OD support excludes them. Using the raw column would add
    destination columns that no seed cell can ever fill, so the car IPF would not converge.
    """
    for rel in CLEAN_ATTR_CANDIDATES:
        p=root/rel
        if p.exists():
            c=pd.read_csv(p,encoding="utf-8-sig")
            if {"zone_id","workplace_attraction_clean"}.issubset(c.columns):
                c["zone_id"]=pd.to_numeric(c.zone_id).astype(int)
                c["workplace_attraction_clean"]=nums(c.workplace_attraction_clean).fillna(0)
                return c[["zone_id","workplace_attraction_clean"]]
    # Fallback: recompute exactly as Step 5B does (zero no-road-access, renormalize in PA).
    s=pd.read_csv(root/SNAP,encoding="utf-8-sig")
    s["zone_id"]=pd.to_numeric(s.zone_id).astype(int)
    s["no_road_access"]=s.no_road_access.astype(str).str.lower().isin(["true","1","yes"])
    m=raw.merge(s[["zone_id","no_road_access"]].drop_duplicates(),on="zone_id",how="left")
    m["no_road_access"]=m["no_road_access"].fillna(False).astype(bool)
    zz=pd.read_csv(root/"reports/od_zone/zone_dictionary.csv",encoding="utf-8-sig")
    zz["zone_id"]=pd.to_numeric(zz.zone_id).astype(int); zz["pa"]=zz.planning_area.map(nn)
    m=m.merge(zz[["zone_id","pa"]],on="zone_id",how="left")
    m["orig"]=m["workplace_attraction"]
    m.loc[m.no_road_access,"workplace_attraction"]=0.0
    keep=m.groupby("pa").workplace_attraction.transform("sum")
    epa=m.groupby("pa").orig.transform("sum")
    m["workplace_attraction_clean"]=np.where(keep>0, epa*m.workplace_attraction/keep, 0.0)
    return m[["zone_id","workplace_attraction_clean"]]

def load_common(root):
    z=pd.read_csv(root/"reports/od_zone/zone_dictionary.csv",encoding="utf-8-sig")
    p=pd.read_csv(root/PROD,encoding="utf-8-sig")
    m=pd.read_csv(root/MODE,encoding="utf-8-sig")
    a=pd.read_csv(find_attr(root),encoding="utf-8-sig")
    nm=pd.read_csv(root/ZONE_MAP,encoding="utf-8-sig")
    net=pd.read_csv(root/NETWORK,encoding="utf-8-sig")
    for df,name in [(z,"zones"),(p,"production"),(m,"mode_shares"),(a,"attraction"),(nm,"zone_map"),(net,"network")]:
        if df.empty: raise ValueError(f"{name} empty")
    z["zone_id"]=pd.to_numeric(z.zone_id).astype(int); z["planning_region_norm"]=z.planning_region.map(nn); z["planning_area_norm"]=z.planning_area.map(nn)
    p["zone_id"]=pd.to_numeric(p.zone_id).astype(int)
    wc=next((c for c in ["car_work_trip_production","car_work_production","P_car","work_trip_production_car","car_only_work_production"] if c in p.columns),None)
    if wc is None:
        raise ValueError(f"production.csv lacks car-only production field: {list(p.columns)}")
    p=p[["zone_id",wc]].rename(columns={wc:"car_production"}); p["car_production"]=nums(p.car_production).fillna(0)
    m["zone_id"]=pd.to_numeric(m.zone_id).astype(int)
    car_candidates=[c for c in m.columns if "car" in str(c).lower() and ("share" in str(c).lower() or "only" in str(c).lower())]
    if not car_candidates: raise ValueError(f"zone_mode_shares lacks car share: {list(m.columns)}")
    cc=next((c for c in car_candidates if "share" in str(c).lower()),car_candidates[0])
    m=m[["zone_id",cc]].rename(columns={cc:"car_share"}); m["car_share"]=nums(m.car_share).fillna(0).clip(0,1)
    a["zone_id"]=pd.to_numeric(a.zone_id).astype(int); a["workplace_attraction"]=nums(a.workplace_attraction).fillna(0)
    # Destination margin = FROZEN attraction v2.1 (no-road-access destinations zeroed,
    # renormalized within PA), matching the support of the 5B/5C.1 prior OD.
    ca=load_clean_attraction(root,a[["zone_id","workplace_attraction"]].copy())
    a=a.drop(columns=["workplace_attraction"]).merge(ca,on="zone_id",how="left")
    a["workplace_attraction"]=a["workplace_attraction_clean"].fillna(0)
    a=a[["zone_id","workplace_attraction"]]
    if not (a.workplace_attraction>0).any(): raise ValueError("cleaned workplace attraction is all zero")
    nm["zone_id"]=pd.to_numeric(nm.zone_id).astype(int); nm["matsim_node_id"]=pd.to_numeric(nm.matsim_node_id).astype(int)
    net["from_node"]=pd.to_numeric(net.from_node).astype(int); net["to_node"]=pd.to_numeric(net.to_node).astype(int)
    if "name" not in net.columns: net["name"]=""
    return z.sort_values("zone_id"),p,m,a,nm,net

def locate_prior(root,lam):
    tag=f"{lam:.3f}".replace(".","p")
    for n in [f"prior_od_5c1_lambda_{tag}.parquet",f"prior_od_5c1_lambda_{tag}.csv"]:
        p=root/PRIOR_DIR/n
        if p.exists(): return p
    raise FileNotFoundError(tag)

def load_t11_car(root, physical_pas):
    df=pd.read_csv(root/T11,encoding="utf-8-sig",low_memory=False)
    label=df.columns[0]
    rows=[]
    for _,r in df.iterrows():
        pa=norm(r[label])
        if not pa or pa.upper()=="TOTAL": continue
        pa_n=nn(pa)
        if pa_n not in physical_pas: continue
        rec={"workplace_pa_norm":pa_n}
        for reg in REGIONS:
            cols=[c for c in df.columns if str(c).lower().startswith((reg+"_").lower()) and CAR_FRAGMENT in str(c).lower()]
            rec[nn(reg)]=float(nums(pd.Series([r[cols[0]]])).iloc[0]) if cols else np.nan
        rows.append(rec)
    t=pd.DataFrame(rows)
    if t.empty: raise ValueError("Table118 car constraints empty")
    long=[]
    for _,r in t.iterrows():
        for reg in REGIONS:
            v=r.get(nn(reg),np.nan)
            if pd.notna(v): long.append({"residence_region_norm":nn(reg),"workplace_pa_norm":r.workplace_pa_norm,"car_table118":float(v)})
    c=pd.DataFrame(long)
    c["car_constraint_share"]=c.car_table118/c.groupby("residence_region_norm").car_table118.transform("sum")
    return c

def ipf(seed,rt,ct,tol=1e-8,max_iter=10000):
    x=seed.astype(float,copy=True)
    for it in range(max_iter):
        rs=x.sum(1)
        for i,t in enumerate(rt):
            if t<=0: x[i,:]=0
            elif rs[i]>0: x[i,:]*=t/rs[i]
        cs=x.sum(0)
        for j,t in enumerate(ct):
            if t<=0: x[:,j]=0
            elif cs[j]>0: x[:,j]*=t/cs[j]
        err=max(float(np.max(np.abs(x.sum(1)-rt))),float(np.max(np.abs(x.sum(0)-ct))))
        if err<=tol: return x,True,it+1,err
    return x,False,max_iter,err

def make_car_od(root,prior,z,p,m,a,table):
    ids=z.zone_id.astype(int).tolist(); n=len(ids)
    base=prior.pivot(index="origin_zone",columns="destination_zone",values="trips").fillna(0).reindex(index=ids,columns=ids,fill_value=0).to_numpy(float)
    pcar=p.set_index("zone_id").reindex(ids).car_production.fillna(0).to_numpy(float)
    ashape=a.set_index("zone_id").reindex(ids).workplace_attraction.fillna(0).to_numpy(float)
    if pcar.sum()<=0 or ashape.sum()<=0: raise ValueError("car production or attraction zero")
    region=z.planning_region_norm.to_numpy(); pa=z.planning_area_norm.to_numpy()
    shares=table.pivot(index="residence_region_norm",columns="workplace_pa_norm",values="car_constraint_share").fillna(0)
    seed=np.zeros_like(base)
    for reg in shares.index:
        ii=np.where(region==reg)[0]; target_reg=pcar[ii].sum()
        if target_reg<=0: continue
        for dest_pa in shares.columns:
            jj=np.where(pa==dest_pa)[0]
            if not len(jj): continue
            block=base[np.ix_(ii,jj)]; s=block.sum()
            if s>0: seed[np.ix_(ii,jj)]=block*(float(shares.loc[reg,dest_pa])*target_reg/s)
    # Destination margin: proportional to v2.1 physical workplace attraction.
    acar=ashape/ashape.sum()*pcar.sum(); acar[ashape<=0]=0
    # Final IPF. Cells with no seed remain zero, so we preserve observed model support.
    od,ok,it,err=ipf(seed,pcar,acar)
    return od,pcar,acar,{"converged":ok,"iterations":it,"max_abs_error":err}

def incident_link_map(net):
    # deterministic: smallest link id touching each node; MATSim activities use link IDs, not node IDs.
    inc={}
    for r in net.itertuples(index=False):
        lid=f"e{int(r.from_node)}_{int(r.to_node)}"
        for node in (int(r.from_node),int(r.to_node)):
            inc.setdefault(node,lid)
    return inc

def sample_agents(od,z,nm,net,target,seed):
    ids=z.zone_id.astype(int).tolist(); n=len(ids); flat=od.reshape(-1); valid=np.flatnonzero(flat>1e-9)
    probs=flat[valid]/flat[valid].sum(); rng=np.random.default_rng(seed); counts=rng.multinomial(target,probs)
    zone_node=nm.set_index("zone_id").reindex(ids).matsim_node_id.astype(int).to_dict(); link_map=incident_link_map(net)
    rows=[]; counter=0
    for pos,cnt in zip(valid,counts):
        if cnt<=0: continue
        i=int(pos//n); j=int(pos%n); trips=float(flat[pos]); exp=trips/cnt
        hn=zone_node[ids[i]]; wn=zone_node[ids[j]]
        if hn not in link_map or wn not in link_map: raise ValueError("Zone snap node has no incident link")
        for _ in range(int(cnt)):
            counter+=1; rows.append({"agent_id":f"a{counter:07d}","origin_zone":ids[i],"destination_zone":ids[j],"home_node":hn,"work_node":wn,"home_link":link_map[hn],"work_link":link_map[wn],"expansion_factor":exp})
    return pd.DataFrame(rows)

def write_xml(pop,path):
    root=ET.Element("population",{"desc":"Singapore Step 6.2 car-only sampled population"})
    for r in pop.itertuples(index=False):
        person=ET.SubElement(root,"person",{"id":str(r.agent_id)})
        at=ET.SubElement(person,"attributes")
        for name,value,cls in [("originZone",r.origin_zone,"java.lang.Integer"),("destinationZone",r.destination_zone,"java.lang.Integer"),("homeNode",r.home_node,"java.lang.Integer"),("workNode",r.work_node,"java.lang.Integer"),("expansionFactor",r.expansion_factor,"java.lang.Double")]:
            ET.SubElement(at,"attribute",{"name":name,"class":cls,"value":str(value)})
        plan=ET.SubElement(person,"plan",{"selected":"yes"})
        ET.SubElement(plan,"activity",{"type":"home","link":str(r.home_link),"end_time":"08:00:00"})
        ET.SubElement(plan,"leg",{"mode":"car"})
        ET.SubElement(plan,"activity",{"type":"work","link":str(r.work_link)})
    ET.indent(root,space="  ")
    with gzip.open(path,"wb",compresslevel=6) as f: ET.ElementTree(root).write(f,encoding="utf-8",xml_declaration=True)

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--project-root",type=Path,default=ROOT_DEFAULT); ap.add_argument("--lambdas",nargs="+",type=float,default=DEFAULT_LAMBDAS); ap.add_argument("--target-agents",type=int,default=DEFAULT_AGENTS); ap.add_argument("--seed",type=int,default=SEED); args=ap.parse_args()
    root=args.project_root; out=root/OUT; out.mkdir(parents=True,exist_ok=True)
    z,p,m,a,nm,net=load_common(root); table=load_t11_car(root,set(z.planning_area_norm))
    summaries=[]
    for lam in args.lambdas:
        prior_path=locate_prior(root,lam); prior=pd.read_parquet(prior_path) if prior_path.suffix==".parquet" else pd.read_csv(prior_path,encoding="utf-8-sig")
        od,pcar,acar,info=make_car_od(root,prior,z,p,m,a,table)
        tag=f"{lam:.3f}".replace(".","p")
        od_long=[]
        for i,oi in enumerate(z.zone_id):
            for j in np.flatnonzero(od[i]>1e-9): od_long.append({"origin_zone":int(oi),"destination_zone":int(z.zone_id.iloc[j]),"trips":float(od[i,j])})
        odf=pd.DataFrame(od_long); odf.to_parquet(out/f"car_prior_od_lambda_{tag}.parquet",index=False); odf.to_csv(out/f"car_prior_od_lambda_{tag}.csv",index=False,encoding="utf-8-sig")
        pop=sample_agents(od,z,nm,net,args.target_agents,args.seed+int(lam*1000)); pop.to_csv(out/f"agent_zone_assignment_lambda_{tag}.csv",index=False,encoding="utf-8-sig")
        xml=out/f"population_lambda_{tag}.xml.gz"; write_xml(pop,xml)
        summaries.append({"lambda_per_min":lam,"car_od_total":float(od.sum()),"car_production_total":float(pcar.sum()),"car_attraction_total":float(acar.sum()),"row_max_abs_error":float(np.max(np.abs(od.sum(1)-pcar))),"column_max_abs_error":float(np.max(np.abs(od.sum(0)-acar))),"ipf_converged":info["converged"],"ipf_iterations":info["iterations"],"target_agents":len(pop),"population_real_trip_equivalent":float(pop.expansion_factor.sum()),"expansion_factor_median":float(pop.expansion_factor.median()),"expansion_factor_max":float(pop.expansion_factor.max()),"xml":str(xml)})
    pd.DataFrame(summaries).to_csv(out/"population_summary.csv",index=False,encoding="utf-8-sig")
    with open(out/"population_validation.json","w",encoding="utf-8") as f: json.dump({"status":"PASS" if all(x["ipf_converged"] and x["row_max_abs_error"]<=1e-8 and x["column_max_abs_error"]<=1e-8 for x in summaries) else "WARN","lambdas":args.lambdas,"target_agents":args.target_agents,"notes":["MATSim population is car-only.","All-mode 5C.1 OD is converted using Step-2 car production and Table 118 car-only ResidenceRegion×WorkplacePA shares.","Destination car attraction is proportional to frozen workplace attraction v2.1.","Each sampled agent stores an expansion factor back to real trips.","Activities use incident MATSim link IDs, not node IDs."]},f,ensure_ascii=False,indent=2)
    print("STATUS:","PASS" if all(x["ipf_converged"] for x in summaries) else "WARN")
    for x in summaries: print(f"lambda={x['lambda_per_min']:.3f} carOD={x['car_od_total']:.1f} agents={x['target_agents']} medianExp={x['expansion_factor_median']:.3f}")
    print("OUT:",out)
if __name__=="__main__": main()
