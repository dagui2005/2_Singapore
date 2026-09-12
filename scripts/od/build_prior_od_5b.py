#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Step 5B: Census Table 118 constrained physical Prior OD.

Inputs:
  reports/od_production/production.csv
  reports/od_attraction_v21/attraction_v21.csv (auto-detect fallback)
  reports/od_impedance/impedance_matrix.parquet
  reports/od_impedance/zone_network_snap.csv
  .../03_Workplace_Employment/outputFile (3)__T11.csv

Outputs:
  reports/od_prior_5b/
    attraction_carbon.csv
    intrazonal_impedance.csv
    table118_region_pa_constraints.csv
    prior_od_5b_lambda_*.parquet/csv
    region_pa_validation_lambda_*.csv
    prior_od_5b_summary.csv
    prior_od_5b_diagnostics.csv
    prior_od_5b_validation_lambda_*.json
    prior_od_5b_accounting.json

Step 5B rules:
  1. Keep the three special workplace destinations outside the 332 physical OD.
  2. Zero-out attraction of physical destination zones flagged as no-road-access,
     then re-normalize within their Workplace PA so PA employment is conserved.
  3. Replace c_ii=0 by a data-derived intrazonal proxy:
       0.5 * median(network travel time to the 5 nearest other zones)
     (explicitly a proxy, not an observed value).
  4. Use Table 118 aggregated across its four modes as a
     ResidenceRegion × WorkplacePA structure constraint.
  5. Restore exact Subzone production/attraction margins by IPF.
  6. Do not yet impose car-only mode shares; that belongs to the next stage.

This script never overwrites Step 5A outputs.
"""

from __future__ import annotations
import argparse
import json
import re
from pathlib import Path
import numpy as np
import pandas as pd

DEFAULT_ROOT=Path(r"D:\Luan\2026-05\2_Singapore")
OUT=Path("reports/od_prior_5b")
PRODUCTION=Path("reports/od_production/production.csv")
ATTR_DIR=Path("reports/od_attraction_v21")
IMPEDANCE=Path("reports/od_impedance/impedance_matrix.parquet")
SNAP=Path("reports/od_impedance/zone_network_snap.csv")
T11=Path("Singapore_OD_MATSim_FinalData/03_Workplace_Employment/outputFile (3)__T11.csv")
ATTRACTION_CANDIDATES=[
    "attraction_v21.csv","attraction_v2.1.csv","attraction_v2.csv"
]
REGIONS=["CENTRAL REGION","EAST REGION","NORTH REGION","NORTH-EAST REGION","WEST REGION"]
MODES=[
    "Combinations of Rail (MRT/LRT) or Public Bus",
    "Car or Taxi/Private Hire Car Only",
    "Other Modes",
    "No Transport Required",
]
SPECIALS={
    "OTHER PLANNING AREAS OR OUTSIDE SINGAPORE",
    "NO FIXED LOCATION FOR WORK",
    "WORKS FROM HOME",
}
K=5
INTRA_FACTOR=.50
TOL=1e-8
MAX_ITER=10000
EPS=1e-15

def norm(x):
    if pd.isna(x): return ""
    return re.sub(r"\s+"," ",str(x).replace("\xa0"," ").strip())
def nn(x): return norm(x).upper()
def nums(s):
    return pd.to_numeric(s.astype(str).str.replace(",","",regex=False),errors="coerce")
def find_attr(root):
    for n in ATTRACTION_CANDIDATES:
        p=root/ATTR_DIR/n
        if p.exists(): return p
    c=[p for p in (root/ATTR_DIR).glob("*.csv")
       if "validation" not in p.name.lower() and "suspicious" not in p.name.lower()
       and "control" not in p.name.lower() and "landuse" not in p.name.lower()
       and "building" not in p.name.lower() and "poi" not in p.name.lower()]
    if len(c)==1: return c[0]
    raise FileNotFoundError(f"Cannot identify attraction file: {c}")

def load_zones(root):
    z=pd.read_csv(root/"reports/od_zone/zone_dictionary.csv",encoding="utf-8-sig")
    req={"zone_id","subzone_code","planning_area","planning_region",
         "centroid_x_svy21_m","centroid_y_svy21_m","area_m2"}
    miss=req-set(z.columns)
    if miss: raise ValueError(f"zone_dictionary missing {sorted(miss)}")
    if len(z)!=332: raise ValueError(f"Expected 332 zones, got {len(z)}")
    z["zone_id"]=pd.to_numeric(z.zone_id).astype(int)
    z["planning_area_norm"]=z.planning_area.map(nn)
    z["planning_region_norm"]=z.planning_region.map(nn)
    return z.sort_values("zone_id").reset_index(drop=True)

def load_production(root):
    p=pd.read_csv(root/PRODUCTION,encoding="utf-8-sig")
    cols=["work_trip_production","P_work","working_trip_production","work_production"]
    wc=next((c for c in cols if c in p.columns),None)
    if wc is None:
        wc=next((c for c in p.columns if "work" in str(c).lower() and "production" in str(c).lower()),None)
    if wc is None: raise ValueError(f"No work production field in {list(p.columns)}")
    p=p[["zone_id",wc]].rename(columns={wc:"production_total"})
    p.zone_id=pd.to_numeric(p.zone_id).astype(int); p.production_total=nums(p.production_total).fillna(0)
    if len(p)!=332: raise ValueError(f"Expected 332 production rows, got {len(p)}")
    return p

def load_attraction(root):
    path=find_attr(root)
    a=pd.read_csv(path,encoding="utf-8-sig")
    req={"zone_id","workplace_attraction"}
    miss=req-set(a.columns)
    if miss: raise ValueError(f"Attraction missing {sorted(miss)}")
    a.zone_id=pd.to_numeric(a.zone_id).astype(int)
    a.workplace_attraction=nums(a.workplace_attraction).fillna(0)
    keep=["zone_id","workplace_attraction"]
    if "planning_area" in a.columns: keep.append("planning_area")
    if "workplace_employment" in a.columns: keep.append("workplace_employment")
    a=a[keep]
    if len(a)!=332: raise ValueError(f"Expected 332 attraction rows, got {len(a)}")
    return a,path

def load_impedance(root, rel=None):
    c=pd.read_parquet(root/(Path(rel) if rel else IMPEDANCE))
    req={"origin_zone","destination_zone","travel_time_min","reachable"}
    miss=req-set(c.columns)
    if miss: raise ValueError(f"Impedance missing {sorted(miss)}")
    c.origin_zone=pd.to_numeric(c.origin_zone).astype(int)
    c.destination_zone=pd.to_numeric(c.destination_zone).astype(int)
    c.travel_time_min=nums(c.travel_time_min)
    c.reachable=c.reachable.astype(bool)
    if len(c)!=332*332: raise ValueError(f"Expected 110224 impedance rows, got {len(c)}")
    if not c.reachable.all(): raise ValueError("Impedance contains unreachable pairs")
    return c

def load_controls(root):
    for rel in [
        "reports/od_attraction_v21/special_workplace_destinations.csv",
        "reports/od_attraction_v21/pa_workplace_control_v21.csv",
        "reports/od_attraction_v21/pa_workplace_control_v2.csv",
        "reports/od_attraction/pa_workplace_control.csv",
    ]:
        p=root/rel
        if p.exists():
            c=pd.read_csv(p,encoding="utf-8-sig")
            if {"planning_area_norm","workplace_employment","is_special_destination"}.issubset(c.columns):
                c.planning_area_norm=c.planning_area_norm.map(nn)
                c.workplace_employment=nums(c.workplace_employment).fillna(0)
                c.is_special_destination=c.is_special_destination.astype(str).str.lower().isin(["true","1","yes"])
                return c
    raise FileNotFoundError("No workplace PA control file found")

def load_t11(root):
    p=root/T11
    if not p.exists(): raise FileNotFoundError(p)
    df=pd.read_csv(p,encoding="utf-8-sig",low_memory=False)
    label=df.columns[0]
    rows=[]
    for _,r in df.iterrows():
        pa=norm(r[label])
        if not pa or pa.upper()=="TOTAL": continue
        rec={"workplace_pa_norm":nn(pa)}
        for reg in REGIONS:
            total=0.0; found=False
            for mode in MODES:
                cs=[c for c in df.columns
                    if str(c).lower().startswith(reg.lower()+"_") and mode.lower() in str(c).lower()]
                if cs:
                    v=nums(pd.Series([r[cs[0]]])).iloc[0]
                    if pd.notna(v): total+=float(v); found=True
            rec[reg]=total if found else np.nan
        rows.append(rec)
    return pd.DataFrame(rows).loc[lambda x:~x.workplace_pa_norm.isin(SPECIALS)].copy()

def clean_attraction(z,a,controls,snap):
    # E_PA = the Workplace PA's physical attraction total. attraction_v21 is already
    # PA-controlled (attraction_sum == census_control per PA), so E_PA is the PA sum of
    # the ORIGINAL A_j. Zero the no-road-access destinations, then renormalize the
    # remaining Subzones inside the same PA so the PA total stays conserved:
    #     A'_j = E_PA * A_j / sum_{k in PA, k not in R} A_k        (A'_j=0 for j in R)
    cols=["zone_id","workplace_attraction"]
    if "workplace_employment" in a.columns: cols.append("workplace_employment")
    x=z[["zone_id","subzone_code","planning_area_norm","planning_area","planning_region_norm"]].merge(
        a[cols],on="zone_id",how="left")
    if "workplace_employment" not in x.columns: x["workplace_employment"]=np.nan
    x["workplace_attraction"]=pd.to_numeric(x.workplace_attraction,errors="coerce").fillna(0)
    if snap is not None and "no_road_access" in snap.columns:
        s=snap.copy(); s.zone_id=pd.to_numeric(s.zone_id).astype(int)
        s["no_road_access"]=s.no_road_access.astype(str).str.lower().isin(["true","1","yes"])
        x=x.merge(s[["zone_id","no_road_access"]].drop_duplicates(),on="zone_id",how="left")
        x["no_road_access"]=x["no_road_access"].fillna(False).astype(bool)
    else:
        x["no_road_access"]=False
    x["original_attraction"]=x["workplace_attraction"]
    x.loc[x.no_road_access,"workplace_attraction"]=0.0
    s_keep=x.groupby("planning_area_norm").workplace_attraction.transform("sum")   # after zeroing
    e_pa=x.groupby("planning_area_norm").original_attraction.transform("sum")      # E_PA
    x["workplace_attraction_clean"]=np.where(s_keep>0, e_pa*x.workplace_attraction/s_keep, 0.0)
    x["removed_no_road_attraction"]=x.original_attraction-x.workplace_attraction
    x[[
        "zone_id","subzone_code","planning_area_norm","planning_area",
        "planning_region_norm","workplace_employment",
        "original_attraction","workplace_attraction",
        "workplace_attraction_clean","no_road_access","removed_no_road_attraction"
    ]].to_csv(root_out/"attraction_carbon.csv",index=False,encoding="utf-8-sig")
    return x

def intrazonal(z,c):
    ids=z.zone_id.astype(int).to_numpy()
    xy=z[["centroid_x_svy21_m","centroid_y_svy21_m"]].to_numpy(float)
    d=((xy[:,None,:]-xy[None,:,:])**2).sum(2)**.5
    np.fill_diagonal(d,np.inf)
    m=c.pivot(index="origin_zone",columns="destination_zone",values="travel_time_min").reindex(index=ids,columns=ids)
    rows=[]
    for i,zid in enumerate(ids):
        js=np.argsort(d[i])[:K]
        tt=m.loc[zid,ids[js]].dropna().to_numpy(float)
        if len(tt)==0: raise ValueError(f"No neighbor travel times for zone {zid}")
        med=float(np.median(tt))
        rows.append({"zone_id":int(zid),"intrazonal_travel_time_min":INTRA_FACTOR*med,
                     "neighbor_median_tt_min":med,"neighbor_n":int(len(tt)),
                     "method":f"{INTRA_FACTOR}*median({K} nearest-zone travel times)"})
    r=pd.DataFrame(rows)
    r.to_csv(root_out/"intrazonal_impedance.csv",index=False,encoding="utf-8-sig")
    return r

def apply_cii(c,intra):
    m=c.pivot(index="origin_zone",columns="destination_zone",values="travel_time_min").copy()
    for _,r in intra.iterrows(): m.loc[int(r.zone_id),int(r.zone_id)]=float(r.intrazonal_travel_time_min)
    # pandas>=2.1 new stack(): dropna is unspecified; matrix is complete so no NA rows are introduced
    return m.stack().rename("travel_time_min").reset_index()

def table118_constraints(t11,clean,z):
    physical_pa=set(clean.planning_area_norm)
    rows=[]
    for _,r in t11.iterrows():
        pa=r.workplace_pa_norm
        if pa not in physical_pa: continue
        for reg in REGIONS:
            v=r.get(reg)
            if pd.notna(v): rows.append({"residence_region_norm":reg,"workplace_pa_norm":pa,"table118_total":float(v)})
    q=pd.DataFrame(rows)
    if q.empty: raise ValueError("Empty Table 118 physical constraint")
    q["constraint_share"]=q["table118_total"]/q.groupby("residence_region_norm").table118_total.transform("sum")
    q.to_csv(root_out/"table118_region_pa_constraints.csv",index=False,encoding="utf-8-sig")
    return q

def ipf(seed,rt,ct):
    x=seed.astype(float,copy=True)
    for it in range(MAX_ITER):
        rs=x.sum(1)
        for i,t in enumerate(rt):
            if t<=0: x[i,:]=0
            elif rs[i]>0: x[i,:]*=t/rs[i]
        cs=x.sum(0)
        for j,t in enumerate(ct):
            if t<=0: x[:,j]=0
            elif cs[j]>0: x[:,j]*=t/cs[j]
        err=max(float(np.max(np.abs(x.sum(1)-rt))),float(np.max(np.abs(x.sum(0)-ct))))
        if err<=TOL: return x,{"iterations":it+1,"converged":True,"max_abs_error":err}
    return x,{"iterations":MAX_ITER,"converged":False,"max_abs_error":float(err)}

def apply_region_pa_share(z,od,control):
    ids=z.zone_id.astype(int).to_numpy()
    region=z.planning_region_norm.to_numpy()
    pa=z.planning_area_norm.to_numpy()
    ctl=control.pivot(index="residence_region_norm",columns="workplace_pa_norm",values="constraint_share").fillna(0)
    out=od.copy()
    n=len(ids)
    for reg in ctl.index:
        ii=np.where(region==reg)[0]
        if not len(ii): continue
        region_total=out[ii,:].sum()
        for dest_pa in ctl.columns:
            jj=np.where(pa==dest_pa)[0]
            if not len(jj): continue
            block=out[np.ix_(ii,jj)]
            cur=block.sum()
            target=float(ctl.loc[reg,dest_pa])*region_total
            if cur>0 and target>=0:
                out[np.ix_(ii,jj)]*=target/cur
    return out

def region_pa_validation(z,od,control):
    region=z.planning_region_norm.to_numpy(); pa=z.planning_area_norm.to_numpy()
    rows=[]
    for reg in control.residence_region_norm.unique():
        ii=np.where(region==reg)[0]
        if not len(ii): continue
        rt=od[ii,:].sum()
        sub=control[control.residence_region_norm==reg]
        for _,r in sub.iterrows():
            jj=np.where(pa==r.workplace_pa_norm)[0]
            if not len(jj): continue
            actual=od[np.ix_(ii,jj)].sum()
            target=float(r.constraint_share)*rt
            rows.append({"residence_region_norm":reg,"workplace_pa_norm":r.workplace_pa_norm,
                         "actual_trips":float(actual),"target_trips":target,
                         "difference":float(actual-target),
                         "relative_error":abs(actual-target)/target if target>0 else 0})
    return pd.DataFrame(rows)

def long_od(ids,m,c):
    rows=[]
    for i,oi in enumerate(ids):
        for j in np.flatnonzero(m[i]>1e-9):
            rows.append({"origin_zone":int(oi),"destination_zone":int(ids[j]),
                         "trips":float(m[i,j]),"travel_time_min":float(c[i,j])})
    return pd.DataFrame(rows)

def main():
    global root_out, prefix
    ap=argparse.ArgumentParser()
    ap.add_argument("--project-root",type=Path,default=DEFAULT_ROOT)
    ap.add_argument("--lambdas",nargs="+",type=float,default=[.05,.075,.10,.125,.15])
    ap.add_argument("--out",type=str,default=str(OUT),
                    help="output dir relative to project root")
    ap.add_argument("--prefix",type=str,default="prior_od_5b",
                    help="filename prefix for the OD/summary outputs")
    ap.add_argument("--impedance",type=str,default=str(IMPEDANCE),
                    help="impedance parquet relative to project root "
                         "(use the AM-peak matrix for Step 5C)")
    ap.add_argument("--label",type=str,default="Step 5B",
                    help="step label shown in the banner")
    args=ap.parse_args()
    root=args.project_root
    prefix=args.prefix
    root_out=root/args.out
    root_out.mkdir(parents=True,exist_ok=True)

    print("="*72); print(f"{args.label} | Census Table 118 constrained Prior OD"); print("="*72)
    print(f"  impedance: {args.impedance}")
    z=load_zones(root); p=load_production(root); a,a_path=load_attraction(root)
    c0=load_impedance(root,args.impedance)
    snap=pd.read_csv(root/SNAP,encoding="utf-8-sig") if (root/SNAP).exists() else None
    controls=load_controls(root)
    clean=clean_attraction(z,a,controls,snap)
    intra=intrazonal(z,c0)
    c_long=apply_cii(c0,intra)
    t11=load_t11(root)
    ctl=table118_constraints(t11,clean,z)

    p_total=float(p.production_total.sum())
    phys_a=float(a.workplace_attraction.sum())
    phys_share=phys_a/p_total
    pt=(p.production_total*phys_share).to_numpy(float)
    at=clean.sort_values("zone_id").workplace_attraction_clean.to_numpy(float)
    pt=pt*(at.sum()/pt.sum())  # pandas 3.0 to_numpy() is read-only; avoid in-place *=
    ids=z.zone_id.astype(int).tolist()

    summary=[]
    for lam in args.lambdas:
        cm=c_long.pivot(index="origin_zone",columns="destination_zone",values="travel_time_min").reindex(index=ids,columns=ids).to_numpy(float)
        seed=np.outer(np.maximum(pt,EPS),np.maximum(at,EPS))*np.exp(-lam*cm)
        seed[:,at<=0]=0; seed[pt<=0,:]=0
        g,gi=ipf(seed,pt,at)
        constrained_seed=apply_region_pa_share(z,g,ctl)
        final,fi=ipf(constrained_seed,pt,at)
        rv=region_pa_validation(z,final,ctl)
        tag=f"{lam:.3f}".replace(".","p")
        lo=long_od(ids,final,cm)
        lo.to_parquet(root_out/f"{prefix}_lambda_{tag}.parquet",index=False)
        lo.to_csv(root_out/f"{prefix}_lambda_{tag}.csv",index=False,encoding="utf-8-sig")
        rv.to_csv(root_out/f"region_pa_validation_lambda_{tag}.csv",index=False,encoding="utf-8-sig")
        mean_tt=float((final*cm).sum()/final.sum())
        summary.append({
            "lambda_per_min":lam,
            "od_total":float(final.sum()),
            "row_max_abs_error":float(np.max(np.abs(final.sum(1)-pt))),
            "col_max_abs_error":float(np.max(np.abs(final.sum(0)-at))),
            "region_pa_max_relative_error":float(rv.relative_error.max()) if len(rv) else np.nan,
            "weighted_mean_travel_time_min":mean_tt,
            "nonzero_od_cells":int(np.count_nonzero(final>1e-9)),
            "cells_ge_1":int(np.count_nonzero(final>=1)),
            "cells_ge_100":int(np.count_nonzero(final>=100)),
            "gravity_ipf_iterations":gi["iterations"],
            "final_ipf_iterations":fi["iterations"],
            "converged":bool(fi["converged"]),
            "intrazonal_median_min":float(intra.intrazonal_travel_time_min.median()),
        })
        with open(root_out/f"{prefix}_validation_lambda_{tag}.json","w",encoding="utf-8") as f:
            json.dump(summary[-1],f,ensure_ascii=False,indent=2)

    pd.DataFrame(summary).to_csv(root_out/f"{prefix}_summary.csv",index=False,encoding="utf-8-sig")
    diag=clean[["zone_id","subzone_code","planning_area_norm","workplace_employment",
                 "workplace_attraction_clean","no_road_access","removed_no_road_attraction"]].copy()
    diag.to_csv(root_out/f"{prefix}_diagnostics.csv",index=False,encoding="utf-8-sig")
    accounting={
        "production_total":p_total,
        "physical_attraction_total":phys_a,
        "physical_workplace_mass_share":phys_share,
        "physical_workplace_mass_share_definition":
            ("= 1,935,235 / 2,208,358; a MASS-ALLOCATION coefficient used only to align the "
             "332x332 physical OD with the Census Workplace-PA attraction. It is NOT the share "
             "of employed residents who physically commute to a concrete workplace."),
        "physical_workplace_mass_share_assumption":
            ("No Subzone-level Residence distribution is available for the Other / "
             "No Fixed Location / Works-from-Home categories, so their residence mass is "
             "assumed proportional to Residence Production. This assumption is retained."),
        "no_road_destination_zones":int(clean.no_road_access.sum()),
        "no_road_attraction_removed":float(clean.removed_no_road_attraction.sum()),
        "no_road_attraction_renormalized_within_pa":True,
        "intrazonal_method": "0.5 × median travel time to 5 nearest other Subzones",
        "table118_constraint": "ResidenceRegion × WorkplacePA, four modes aggregated",
        "mode_specific_constraint": False,
    }
    accounting["impedance_source"]=args.impedance
    accounting["step_label"]=args.label
    with open(root_out/f"{prefix}_accounting.json","w",encoding="utf-8") as f:
        json.dump(accounting,f,ensure_ascii=False,indent=2)
    print(f"Zones: {len(z)} | Table118 rows: {len(ctl)} | λ: {args.lambdas}")
    print(f"Physical attraction: {phys_a:,.3f} | Physical production: {pt.sum():,.3f}")
    print(f"No-road zones: {int(clean.no_road_access.sum())} | removed A: {clean.removed_no_road_attraction.sum():,.3f}")
    print(f"Output: {root_out}")
    print("="*72)

if __name__=="__main__": main()
