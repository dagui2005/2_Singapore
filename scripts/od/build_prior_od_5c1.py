#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Step 5C.1: AM-peak (v2) impedance + Census Table 118 constrained Prior OD.

Same validated constraint framework as Step 5B, only the impedance is swapped:
    P_i + A_j^(v2.1) + C_ij^(AM,v2) + c_ii + Table118 -> IPF -> T_ij^(5C.1)

Inputs:
    reports/od_production/production.csv
    reports/od_attraction_v21/attraction_v21.csv
    reports/od_impedance_ampeak_v2/ampeak_impedance_v2.parquet   <- AM-v2 impedance
    reports/od_impedance/zone_network_snap.csv
    .../03_Workplace_Employment/outputFile (3)__T11.csv          <- Table 118

Outputs (reports/od_prior_5c1/):
    attraction_clean_5c1.csv
    intrazonal_impedance_5c1.csv
    table118_region_pa_constraints_5c1.csv
    prior_od_5c1_summary.csv
    prior_od_5c1_accounting.json
    prior_od_5c1_lambda_*.parquet / .csv
    region_pa_validation_lambda_*.csv

lambda is NOT frozen here; it stays a sensitivity scan (0.05 ... 0.15) to be
selected later by MATSim assignment + TrafficFlow calibration.
"""
from __future__ import annotations
import argparse,json,re
from pathlib import Path
import numpy as np
import pandas as pd

ROOT_DEFAULT=Path(r"D:\Luan\2026-05\2_Singapore")
PRODUCTION=Path("reports/od_production/production.csv")
ATTR_DIR=Path("reports/od_attraction_v21")
IMPEDANCE=Path("reports/od_impedance_ampeak_v2/ampeak_impedance_v2.parquet")
SNAP=Path("reports/od_impedance/zone_network_snap.csv")
T11=Path("Singapore_OD_MATSim_FinalData/03_Workplace_Employment/outputFile (3)__T11.csv")
OUT=Path("reports/od_prior_5c1")
REGIONS=["CENTRAL REGION","EAST REGION","NORTH REGION","NORTH-EAST REGION","WEST REGION"]
MODES=["Combinations of Rail (MRT/LRT) or Public Bus","Car or Taxi/Private Hire Car Only","Other Modes","No Transport Required"]
SPECIALS={"OTHER PLANNING AREAS OR OUTSIDE SINGAPORE","NO FIXED LOCATION FOR WORK","WORKS FROM HOME"}
LAMBDAS=[.05,.075,.10,.125,.15]; EPS=1e-15; TOL=1e-8; MAX_ITER=10000

def norm(x):
    if pd.isna(x): return ""
    return re.sub(r"\s+"," ",str(x).replace("\xa0"," ").strip())
def nn(x): return norm(x).upper()
def nums(s): return pd.to_numeric(s.astype(str).str.replace(",","",regex=False),errors="coerce")

def find_attr(root):
    for n in ["attraction_v21.csv","attraction_v2.1.csv","attraction_v2.csv"]:
        p=root/ATTR_DIR/n
        if p.exists(): return p
    cs=[p for p in (root/ATTR_DIR).glob("*.csv") if all(k not in p.name.lower() for k in ["validation","suspicious","control","landuse","building","poi"])]
    if len(cs)==1: return cs[0]
    raise FileNotFoundError(cs)

def load_zones(root):
    z=pd.read_csv(root/"reports/od_zone/zone_dictionary.csv",encoding="utf-8-sig")
    req={"zone_id","subzone_code","planning_area","planning_region","centroid_x_svy21_m","centroid_y_svy21_m"}
    m=req-set(z.columns)
    if m: raise ValueError(f"zone missing {sorted(m)}")
    if len(z)!=332: raise ValueError(f"expected 332 zones, got {len(z)}")
    z.zone_id=pd.to_numeric(z.zone_id).astype(int); z["planning_area_norm"]=z.planning_area.map(nn); z["planning_region_norm"]=z.planning_region.map(nn)
    return z.sort_values("zone_id").reset_index(drop=True)

def load_production(root):
    p=pd.read_csv(root/PRODUCTION,encoding="utf-8-sig")
    c=next((c for c in ["work_trip_production","P_work","working_trip_production","work_production"] if c in p.columns),None)
    if c is None: c=next((c for c in p.columns if "work" in str(c).lower() and "production" in str(c).lower()),None)
    if c is None: raise ValueError(f"no work production field: {list(p.columns)}")
    p=p[["zone_id",c]].rename(columns={c:"production_total"}); p.zone_id=pd.to_numeric(p.zone_id).astype(int); p.production_total=nums(p.production_total).fillna(0)
    if len(p)!=332: raise ValueError(f"production expected 332, got {len(p)}")
    return p

def load_attraction(root):
    path=find_attr(root); a=pd.read_csv(path,encoding="utf-8-sig")
    if not {"zone_id","workplace_attraction"}.issubset(a.columns): raise ValueError(f"attraction missing required fields: {list(a.columns)}")
    a.zone_id=pd.to_numeric(a.zone_id).astype(int); a.workplace_attraction=nums(a.workplace_attraction).fillna(0)
    if len(a)!=332: raise ValueError(f"attraction expected 332, got {len(a)}")
    return a[["zone_id","workplace_attraction"]],path

def load_impedance(root):
    c=pd.read_parquet(root/IMPEDANCE)
    req={"origin_zone","destination_zone","travel_time_min","reachable"}; m=req-set(c.columns)
    if m: raise ValueError(f"impedance missing {sorted(m)}")
    c.origin_zone=pd.to_numeric(c.origin_zone).astype(int); c.destination_zone=pd.to_numeric(c.destination_zone).astype(int); c.travel_time_min=nums(c.travel_time_min); c.reachable=c.reachable.astype(bool)
    if len(c)!=332*332 or not c.reachable.all(): raise ValueError("AM impedance must be complete 332x332 and fully reachable")
    return c

def load_snap(root):
    p=root/SNAP
    if not p.exists(): return None
    s=pd.read_csv(p,encoding="utf-8-sig"); s.zone_id=pd.to_numeric(s.zone_id).astype(int)
    if "no_road_access" in s.columns: s.no_road_access=s.no_road_access.astype(str).str.lower().isin(["true","1","yes"])
    elif "snap_warning" in s.columns: s.no_road_access=s.snap_warning.astype(str).str.lower().isin(["true","1","yes"])
    else: s["no_road_access"]=False
    return s[["zone_id","no_road_access"]].drop_duplicates()

def clean_attraction(z,a,snap):
    x=z[["zone_id","subzone_code","planning_area_norm","planning_area","planning_region_norm"]].merge(a,on="zone_id",how="left")
    if snap is not None: x=x.merge(snap,on="zone_id",how="left")
    else: x["no_road_access"]=False
    x.no_road_access=x.no_road_access.fillna(False).astype(bool); x["original_attraction"]=x.workplace_attraction
    x.loc[x.no_road_access,"workplace_attraction"]=0.0
    # Preserve each PA's original total after removing unusable destinations.
    pa_orig=x.groupby("planning_area_norm").original_attraction.transform("sum")
    pa_rem=x.groupby("planning_area_norm").workplace_attraction.transform("sum")
    x["workplace_attraction_clean"]=np.where(pa_rem>0,x.workplace_attraction*pa_orig/pa_rem,0.0)
    x["removed_original_destination_mass"]=np.where(x.no_road_access,x.original_attraction,0.0)
    return x

def intrazonal(z,c):
    ids=z.zone_id.astype(int).to_numpy(); xy=z[["centroid_x_svy21_m","centroid_y_svy21_m"]].to_numpy(float)
    d=np.sqrt(((xy[:,None,:]-xy[None,:,:])**2).sum(2)); np.fill_diagonal(d,np.inf)
    m=c.pivot(index="origin_zone",columns="destination_zone",values="travel_time_min").reindex(index=ids,columns=ids)
    rows=[]
    for i,zid in enumerate(ids):
        js=np.argsort(d[i])[:5]; vals=m.loc[zid,ids[js]].dropna().to_numpy(float)
        med=float(np.median(vals)); rows.append({"zone_id":int(zid),"intrazonal_travel_time_min":.5*med,"neighbor_median_min":med,"neighbor_n":len(vals)})
    return pd.DataFrame(rows)

def apply_cii(c,intra):
    m=c.pivot(index="origin_zone",columns="destination_zone",values="travel_time_min").copy()
    for _,r in intra.iterrows(): m.loc[int(r.zone_id),int(r.zone_id)]=float(r.intrazonal_travel_time_min)
    return m

def table118(root,physical_pas):
    df=pd.read_csv(root/T11,encoding="utf-8-sig",low_memory=False); label=df.columns[0]; rows=[]
    for _,r in df.iterrows():
        wp=nn(r[label])
        if not wp or wp=="TOTAL" or wp in SPECIALS or wp not in physical_pas: continue
        rec={"workplace_pa_norm":wp}
        for reg in REGIONS:
            total=0.0; found=False
            for mode in MODES:
                cs=[c for c in df.columns if str(c).lower().startswith((reg+"_").lower()) and mode.lower() in str(c).lower()]
                if cs:
                    v=nums(pd.Series([r[cs[0]]])).iloc[0]
                    if pd.notna(v): total+=float(v); found=True
            rec[reg]=total if found else np.nan
        rows.append(rec)
    t=pd.DataFrame(rows)
    out=[]
    for _,r in t.iterrows():
        for reg in REGIONS:
            if pd.notna(r.get(reg)): out.append({"residence_region_norm":reg,"workplace_pa_norm":r.workplace_pa_norm,"table118_total":float(r[reg])})
    q=pd.DataFrame(out); q["constraint_share"]=q.table118_total/q.groupby("residence_region_norm").table118_total.transform("sum")
    return q

def ipf(seed,rt,ct):
    x=seed.astype(float,copy=True)
    for it in range(MAX_ITER):
        rs=x.sum(1)
        nz=rs>0
        for i,t in enumerate(rt):
            if t<=0: x[i,:]=0
            elif nz[i]: x[i,:]*=t/rs[i]
        cs=x.sum(0); nz=cs>0
        for j,t in enumerate(ct):
            if t<=0: x[:,j]=0
            elif nz[j]: x[:,j]*=t/cs[j]
        err=max(float(np.max(np.abs(x.sum(1)-rt))),float(np.max(np.abs(x.sum(0)-ct))))
        if err<=TOL: return x,{"iterations":it+1,"converged":True,"max_abs_error":err}
    return x,{"iterations":MAX_ITER,"converged":False,"max_abs_error":float(err)}

def impose_structure(z,od,ctl):
    reg=z.planning_region_norm.to_numpy(); pa=z.planning_area_norm.to_numpy(); shares=ctl.pivot(index="residence_region_norm",columns="workplace_pa_norm",values="constraint_share").fillna(0); out=od.copy()
    for r in shares.index:
        ii=np.where(reg==r)[0]
        if not len(ii): continue
        total=out[ii,:].sum()
        for wp in shares.columns:
            jj=np.where(pa==wp)[0]
            if not len(jj): continue
            cur=out[np.ix_(ii,jj)].sum(); target=float(shares.loc[r,wp])*total
            if cur>0: out[np.ix_(ii,jj)]*=target/cur
    return out

def region_pa_val(z,od,ctl):
    reg=z.planning_region_norm.to_numpy(); pa=z.planning_area_norm.to_numpy(); rows=[]
    for r in ctl.residence_region_norm.unique():
        ii=np.where(reg==r)[0]; total=od[ii,:].sum(); sub=ctl[ctl.residence_region_norm==r]
        for _,x in sub.iterrows():
            jj=np.where(pa==x.workplace_pa_norm)[0]
            if not len(jj): continue
            actual=od[np.ix_(ii,jj)].sum(); target=float(x.constraint_share)*total
            rows.append({"residence_region_norm":r,"workplace_pa_norm":x.workplace_pa_norm,"actual_trips":actual,"target_trips":target,"difference":actual-target,"relative_error":abs(actual-target)/target if target>0 else 0})
    return pd.DataFrame(rows)

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--project-root",type=Path,default=ROOT_DEFAULT); ap.add_argument("--lambdas",nargs="+",type=float,default=LAMBDAS); args=ap.parse_args(); root=args.project_root; out=root/OUT; out.mkdir(parents=True,exist_ok=True)
    z=load_zones(root); p=load_production(root); a,a_path=load_attraction(root); imp=load_impedance(root); snap=load_snap(root)
    clean=clean_attraction(z,a,snap); clean.to_csv(out/"attraction_clean_5c1.csv",index=False,encoding="utf-8-sig")
    pa_check=clean.groupby("planning_area_norm",as_index=False).agg(original=("original_attraction","sum"),clean=("workplace_attraction_clean","sum")); pa_check["difference"]=pa_check.clean-pa_check.original; pa_check.to_csv(out/"attraction_pa_conservation.csv",index=False,encoding="utf-8-sig")
    if pa_check.difference.abs().max()>1e-6: raise ValueError("Attraction PA conservation failed")
    intra=intrazonal(z,imp); intra.to_csv(out/"intrazonal_impedance_5c1.csv",index=False,encoding="utf-8-sig"); cm=apply_cii(imp,intra)
    ctl=table118(root,set(clean.planning_area_norm)); ctl.to_csv(out/"table118_region_pa_constraints_5c1.csv",index=False,encoding="utf-8-sig")
    p_total=float(p.production_total.sum()); a_total=float(clean.workplace_attraction_clean.sum()); mass_share=a_total/p_total
    p_phys=p.production_total.to_numpy(float)*mass_share; p_phys=p_phys*(a_total/p_phys.sum()); ids=z.zone_id.astype(int).tolist(); a_target=clean.sort_values("zone_id").workplace_attraction_clean.to_numpy(float); c=cm.reindex(index=ids,columns=ids).to_numpy(float)
    summary=[]
    for lam in args.lambdas:
        seed=np.outer(np.maximum(p_phys,EPS),np.maximum(a_target,EPS))*np.exp(-lam*c); seed[:,a_target<=0]=0; seed[p_phys<=0,:]=0
        grav,gi=ipf(seed,p_phys,a_target); cs=impose_structure(z,grav,ctl); final,fi=ipf(cs,p_phys,a_target); rv=region_pa_val(z,final,ctl)
        tag=f"{lam:.3f}".replace(".","p"); lo=[]
        for i,oi in enumerate(ids):
            for j in np.flatnonzero(final[i]>1e-9): lo.append({"origin_zone":oi,"destination_zone":ids[j],"trips":float(final[i,j]),"travel_time_min":float(c[i,j])})
        lodf=pd.DataFrame(lo); lodf.to_parquet(out/f"prior_od_5c1_lambda_{tag}.parquet",index=False); lodf.to_csv(out/f"prior_od_5c1_lambda_{tag}.csv",index=False,encoding="utf-8-sig"); rv.to_csv(out/f"region_pa_validation_lambda_{tag}.csv",index=False,encoding="utf-8-sig")
        summary.append({"lambda_per_min":lam,"od_total":float(final.sum()),"row_max_abs_error":float(np.max(np.abs(final.sum(1)-p_phys))),"column_max_abs_error":float(np.max(np.abs(final.sum(0)-a_target))),"region_pa_max_relative_error":float(rv.relative_error.max()),"weighted_mean_travel_time_min":float((final*c).sum()/final.sum()),"nonzero_od_cells":int(np.count_nonzero(final>1e-9)),"cells_ge_1":int(np.count_nonzero(final>=1)),"cells_ge_100":int(np.count_nonzero(final>=100)),"gravity_ipf_iterations":gi["iterations"],"final_ipf_iterations":fi["iterations"],"converged":bool(fi["converged"]),"intrazonal_median_min":float(intra.intrazonal_travel_time_min.median())})
    pd.DataFrame(summary).to_csv(out/"prior_od_5c1_summary.csv",index=False,encoding="utf-8-sig")
    with open(out/"prior_od_5c1_accounting.json","w",encoding="utf-8") as f: json.dump({"production_total":p_total,"physical_attraction_total":a_total,"physical_workplace_mass_share":mass_share,"special_workplace_mass":p_total-a_total,"no_road_access_zone_count":int(clean.no_road_access.sum()),"no_road_original_attraction_removed":float(clean.removed_original_destination_mass.sum()),"table118_constraint":"ResidenceRegion x WorkplacePA, all four modes aggregated","intrazonal_definition":"0.5 x median travel time to five nearest other Subzones","am_impedance_source":str(IMPEDANCE),"lambda_not_selected":True},f,ensure_ascii=False,indent=2)
    print("STATUS: PASS"); print("Output:",out)
if __name__=="__main__": main()
