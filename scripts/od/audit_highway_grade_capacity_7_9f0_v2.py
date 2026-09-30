#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Step 7.9F-0 v2 — formal zero-simulation structural audit."""
from __future__ import annotations
import argparse, ast, gzip, hashlib, json, math
import xml.etree.ElementTree as ET
from pathlib import Path
import numpy as np
import pandas as pd

ROOT_DEFAULT=Path(r"D:\Luan\2026-05\2_Singapore")
NETWORK_REL=Path("reports/matsim_network/network_links_source_copy.csv")
XML_REL=Path("reports/matsim_network/network.xml.gz")
E2_ALL_REL=Path("reports/arterial_expanded_residual_7_9e2/e2_section_residual_all_tiers.csv")
E2_MAIN_REL=Path("reports/arterial_expanded_residual_7_9e2/e2_section_residual_main.csv")
OUT_REL=Path("reports/highway_grade_capacity_7_9f0_v2")
PREREG_REL=OUT_REL/"PREREG_7_9F0_v2.md"
EXPECTED_PREREG_SHA256="31d61dc8a9e608ce1feb30a0ffb583f3a94ded3507e090f829bb6dc265019248"
CORE_HW=["motorway","motorway_link","trunk","primary","secondary","tertiary"]
TREND_HW=["trunk","secondary","tertiary"]
CAP={"motorway":1900.,"motorway_link":1700.,"trunk":1800.,"trunk_link":1600.,"primary":1500.,"primary_link":1300.,"secondary":1200.,"secondary_link":1100.,"tertiary":900.,"tertiary_link":800.,"residential":700.,"service":400.,"unclassified":600.}
DEF_LANES={"motorway":2.,"motorway_link":1.,"trunk":2.,"trunk_link":1.,"primary":2.,"primary_link":1.,"secondary":2.,"secondary_link":1.,"tertiary":1.,"tertiary_link":1.,"residential":1.,"service":1.,"unclassified":1.}


def sha256_file(p):
    h=hashlib.sha256();
    with p.open('rb') as f:
        for b in iter(lambda:f.read(1<<20),b''): h.update(b)
    return h.hexdigest()

def norm_id(x):
    s='' if x is None else str(x).strip()
    if not s or s.lower()=='nan': return ''
    return s[:-2] if s.endswith('.0') and s[:-2].isdigit() else s

def norm_text(x):
    s='' if x is None else str(x).replace('\xa0',' ').strip().lower()
    return '' if s=='nan' else ' '.join(s.split())

def num(s): return pd.to_numeric(s.astype(str).str.replace(',','',regex=False),errors='coerce')
def ratio(a,b): return float(a/b) if b and np.isfinite(b) else float('nan')
def wmean(y,w):
    z=pd.concat([pd.to_numeric(y,errors='coerce'),pd.to_numeric(w,errors='coerce')],axis=1).dropna()
    if z.empty or z.iloc[:,1].sum()<=0: return float('nan')
    return float((z.iloc[:,0]*z.iloc[:,1]).sum()/z.iloc[:,1].sum())
def corr(x,y,method):
    z=pd.concat([pd.to_numeric(x,errors='coerce'),pd.to_numeric(y,errors='coerce')],axis=1).dropna()
    return float(z.iloc[:,0].corr(z.iloc[:,1],method=method)) if len(z)>=3 else float('nan')

def zero_sim_audit(p):
    t=ast.parse(p.read_text(encoding='utf-8'))
    banned={'subprocess','jpype','py4j'}; calls={'system','popen','Popen','run','call','check_call','check_output'}
    for n in ast.walk(t):
        if isinstance(n,ast.Import) and any(a.name.split('.')[0] in banned for a in n.names): return False
        if isinstance(n,ast.ImportFrom) and n.module and n.module.split('.')[0] in banned: return False
        if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute) and n.func.attr in calls: return False
    return True

def load_source(p):
    x=pd.read_csv(p,encoding='utf-8-sig',low_memory=False); c={str(i).strip().lower():i for i in x.columns}
    req=['from_node','to_node','length_m','highway','lanes']; miss=[k for k in req if k not in c]
    if miss: raise ValueError(f'network source 缺字段: {miss}')
    x=x.rename(columns={c[k]:k for k in req})
    for k in ['from_node','to_node']: x[k]=pd.to_numeric(x[k],errors='coerce').astype('Int64')
    for k in ['length_m','lanes']: x[k]=num(x[k])
    x['highway']=x['highway'].map(norm_text)
    x['matsim_link_id']='e'+x['from_node'].astype(str)+'_'+x['to_node'].astype(str)
    if x.matsim_link_id.duplicated().any(): raise ValueError('source network duplicate link id')
    return x

def load_xml(p):
    rows=[]
    with gzip.open(p,'rb') as f:
        for _,e in ET.iterparse(f,events=('end',)):
            if e.tag.split('}')[-1] != 'link': continue
            a=e.attrib; i=norm_id(a.get('id'))
            if i:
                rows.append({'matsim_link_id':i,'xml_length_m':pd.to_numeric(a.get('length'),errors='coerce'),'freespeed_mps':pd.to_numeric(a.get('freespeed'),errors='coerce'),'xml_capacity':pd.to_numeric(a.get('capacity'),errors='coerce'),'xml_permlanes':pd.to_numeric(a.get('permlanes'),errors='coerce'),'xml_from':norm_id(a.get('from')),'xml_to':norm_id(a.get('to')),'xml_modes':a.get('modes','')})
            e.clear()
    x=pd.DataFrame(rows)
    if x.empty: raise ValueError('network.xml.gz 没有 link')
    if x.matsim_link_id.duplicated().any(): raise ValueError('XML duplicate link id')
    x['speed_kmh']=x.freespeed_mps*3.6
    x['actual_capacity_per_lane']=np.where(x.xml_permlanes>0,x.xml_capacity/x.xml_permlanes,np.nan)
    return x

def load_e2_all(p):
    x=pd.read_csv(p,encoding='utf-8-sig',low_memory=False); req=['LinkID','RoadCat','obs_8_9','sim_8_9_scaled','sim_8_9_median_raw','sim_8_9_mean_raw','diagnostic_ratio_8_9','diagnostic_residual_8_9','diagnostic_highway','valid_residual','tier_output','representative_matsim_link_id']; miss=[k for k in req if k not in x.columns]
    if miss: raise ValueError(f'E2 all_tiers 缺字段: {miss}')
    x['LinkID']=x.LinkID.map(norm_id); x['RoadCat']=x.RoadCat.map(norm_text); x['tier_output']=x.tier_output.map(norm_text); x['diagnostic_highway']=x.diagnostic_highway.map(norm_text); x['representative_matsim_link_id']=x.representative_matsim_link_id.map(norm_id)
    for k in ['obs_8_9','sim_8_9_scaled','sim_8_9_median_raw','sim_8_9_mean_raw','diagnostic_ratio_8_9','diagnostic_residual_8_9']: x[k]=num(x[k])
    x['valid_residual']=x.valid_residual.astype(str).str.strip().str.lower().isin(['true','1','yes'])
    return x

def load_e2_main(p):
    x=pd.read_csv(p,encoding='utf-8-sig',low_memory=False); x['LinkID']=x['LinkID'].map(norm_id)
    for k in ['diagnostic_residual_8_9','sim_8_9_scaled','obs_8_9']:
        if k in x: x[k]=num(x[k])
    return x

def select_ab(x):
    z=x[x.tier_output.eq('a+b_main')].copy()
    if z.empty: raise ValueError('E2 A+B_MAIN slice empty')
    if z.LinkID.duplicated().any(): raise ValueError('E2 A+B_MAIN duplicate LinkID')
    return z

def join(e2,src,xml):
    z=e2.merge(src[['matsim_link_id','length_m','highway','lanes']],left_on='representative_matsim_link_id',right_on='matsim_link_id',how='left',validate='many_to_one')
    z=z.merge(xml[['matsim_link_id','xml_length_m','freespeed_mps','speed_kmh','xml_capacity','xml_permlanes','actual_capacity_per_lane','xml_from','xml_to','xml_modes']],left_on='representative_matsim_link_id',right_on='matsim_link_id',how='left',validate='many_to_one',suffixes=('','_xml'))
    z['join_ok']=z.matsim_link_id.notna() & z.xml_capacity.notna() & z.xml_permlanes.notna() & z.speed_kmh.notna()
    z['canonical_cap_per_lane']=z.diagnostic_highway.map(CAP)
    z['cap_lookup_rel_diff']=(z.actual_capacity_per_lane-z.canonical_cap_per_lane).abs()/z.canonical_cap_per_lane
    z['lookup_match_1pct']=z.canonical_cap_per_lane.notna() & z.cap_lookup_rel_diff.le(.01)
    z['default_lanes']=z.diagnostic_highway.map(DEF_LANES)
    z['raw_lanes_missing']=z.lanes.isna()
    z['raw_lanes_default_equal']=z.lanes.notna() & z.default_lanes.notna() & (z.lanes-z.default_lanes).abs().le(1e-9)
    z['obs_to_capacity_proxy']=np.where(z.xml_capacity>0,z.obs_8_9/z.xml_capacity,np.nan)
    z['sim_to_capacity_proxy']=np.where(z.xml_capacity>0,z.sim_8_9_scaled/z.xml_capacity,np.nan)
    z['highway_consistent']=z.diagnostic_highway.eq(z.highway)
    return z

def grade_summary(z):
    v=z[z.valid_residual & z.join_ok].copy(); rows=[]
    for hw,g in v.groupby('diagnostic_highway',dropna=False):
        rows.append({'highway':hw,'n':len(g),'length_km':g.length_m.sum()/1000,'mean_residual':g.diagnostic_residual_8_9.mean(),'median_residual':g.diagnostic_residual_8_9.median(),'p10_residual':g.diagnostic_residual_8_9.quantile(.10),'p90_residual':g.diagnostic_residual_8_9.quantile(.90),'obs_weighted_residual':wmean(g.diagnostic_residual_8_9,g.obs_8_9),'sim_weighted_residual':wmean(g.diagnostic_residual_8_9,g.sim_8_9_scaled),'raw_lanes_median':g.lanes.median(),'xml_permlanes_median':g.xml_permlanes.median(),'xml_capacity_median':g.xml_capacity.median(),'capacity_per_lane_median':g.actual_capacity_per_lane.median(),'lookup_match_share':g.lookup_match_1pct.mean(),'raw_lanes_missing_share':g.raw_lanes_missing.mean(),'default_lanes_share':g.raw_lanes_default_equal.mean(),'speed_median_kmh':g.speed_kmh.median(),'speed_p10_kmh':g.speed_kmh.quantile(.10),'speed_p90_kmh':g.speed_kmh.quantile(.90),'obs_cap_p50':g.obs_to_capacity_proxy.median(),'obs_cap_p90':g.obs_to_capacity_proxy.quantile(.90),'sim_cap_p50':g.sim_to_capacity_proxy.median(),'sim_cap_p90':g.sim_to_capacity_proxy.quantile(.90)})
    return pd.DataFrame(rows).sort_values('highway')

def cap_audit(z):
    v=z[z.join_ok & z.diagnostic_highway.isin(CAP)].copy(); rows=[]
    for hw,g in v.groupby('diagnostic_highway'):
        rows.append({'highway':hw,'n':len(g),'canonical_cap_per_lane':CAP[hw],'actual_cap_per_lane_p50':g.actual_capacity_per_lane.median(),'p10':g.actual_capacity_per_lane.quantile(.10),'p90':g.actual_capacity_per_lane.quantile(.90),'lookup_match_share':g.lookup_match_1pct.mean(),'rel_diff_p50':g.cap_lookup_rel_diff.median(),'rel_diff_p90':g.cap_lookup_rel_diff.quantile(.90),'raw_lanes_missing_share':g.raw_lanes_missing.mean(),'default_lanes_share':g.raw_lanes_default_equal.mean(),'xml_permlanes_unique_n':g.xml_permlanes.nunique()})
    return pd.DataFrame(rows)

def rels(z):
    v=z[z.valid_residual & z.join_ok]; attrs=[('raw_lanes','lanes'),('xml_permlanes','xml_permlanes'),('speed_kmh','speed_kmh'),('capacity_per_lane','actual_capacity_per_lane'),('obs_to_capacity','obs_to_capacity_proxy'),('sim_to_capacity','sim_to_capacity_proxy'),('xml_capacity','xml_capacity')]; rows=[]
    for hw,g in v.groupby('diagnostic_highway',dropna=False):
        for lab,c in attrs:
            q=g[[c,'diagnostic_residual_8_9']].dropna(); rows.append({'highway':hw,'attribute':lab,'n':len(q),'spearman':corr(q['diagnostic_residual_8_9'],q[c],'spearman'),'pearson':corr(q['diagnostic_residual_8_9'],q[c],'pearson')})
    return pd.DataFrame(rows)

def dm_corr(z):
    v=z[z.valid_residual & z.join_ok].copy(); v['r_dm']=v.diagnostic_residual_8_9-v.groupby('diagnostic_highway').diagnostic_residual_8_9.transform('mean'); rows=[]
    for lab,c in [('raw_lanes','lanes'),('xml_permlanes','xml_permlanes'),('speed_kmh','speed_kmh'),('capacity_per_lane','actual_capacity_per_lane'),('obs_to_capacity','obs_to_capacity_proxy'),('sim_to_capacity','sim_to_capacity_proxy'),('xml_capacity','xml_capacity')]:
        x=v[c]-v.groupby('diagnostic_highway')[c].transform('mean'); q=pd.DataFrame({'r':v.r_dm,'x':x}).dropna(); rows.append({'attribute':lab,'n':len(q),'pearson_grade_demeaned':corr(q.r,q.x,'pearson'),'spearman_grade_demeaned':corr(q.r,q.x,'spearman')})
    return pd.DataFrame(rows)

def trend(z):
    v=z[z.valid_residual & z.join_ok & z.diagnostic_highway.isin(TREND_HW)]; rows=[]
    for i,hw in enumerate(TREND_HW,1):
        g=v[v.diagnostic_highway.eq(hw)]
        if len(g): rows.append({'highway':hw,'ordinal':i,'n':len(g),'mean_residual':g.diagnostic_residual_8_9.mean(),'obs_weighted_residual':wmean(g.diagnostic_residual_8_9,g.obs_8_9),'sim_weighted_residual':wmean(g.diagnostic_residual_8_9,g.sim_8_9_scaled),'raw_lanes_p50':g.lanes.median(),'xml_permlanes_p50':g.xml_permlanes.median(),'cap_per_lane_p50':g.actual_capacity_per_lane.median(),'speed_p50':g.speed_kmh.median()})
    o=pd.DataFrame(rows)
    if len(o)==3:
        o['trend_spearman_mean']=corr(o.ordinal,o.mean_residual,'spearman'); o['trend_spearman_obs']=corr(o.ordinal,o.obs_weighted_residual,'spearman'); o['trend_spearman_sim']=corr(o.ordinal,o.sim_weighted_residual,'spearman')
    return o

def zero_robust(z):
    v=z[z.valid_residual & z.join_ok].copy(); a=v[v.sim_8_9_median_raw.eq(0)]; b=v[~v.sim_8_9_median_raw.eq(0)]
    return pd.DataFrame([{'scope':'FULL','n':len(v),'zero_median_n':len(a),'zero_median_obs_share':ratio(a.obs_8_9.sum(),v.obs_8_9.sum()),'zero_with_mean_raw_positive':int(a.sim_8_9_mean_raw.gt(0).sum()),'obs_weighted_residual':wmean(v.diagnostic_residual_8_9,v.obs_8_9),'sim_weighted_residual':wmean(v.diagnostic_residual_8_9,v.sim_8_9_scaled)},{'scope':'EXCLUDING_ZERO_MEDIAN','n':len(b),'zero_median_n':0,'zero_median_obs_share':0.,'zero_with_mean_raw_positive':0,'obs_weighted_residual':wmean(b.diagnostic_residual_8_9,b.obs_8_9),'sim_weighted_residual':wmean(b.diagnostic_residual_8_9,b.sim_8_9_scaled)}])

def checks(script,prereg,src,xml,e2,e2main,z,out,manifest,written):
    valid=e2[e2.valid_residual]; joined=z[z.valid_residual]; cov=ratio(joined.join_ok.sum(),len(valid)); capcov=ratio(joined.actual_capacity_per_lane.notna().sum(),len(joined)); spcov=ratio(joined.speed_kmh.notna().sum(),len(joined)); pcov=min(ratio(joined.obs_to_capacity_proxy.notna().sum(),len(joined)),ratio(joined.sim_to_capacity_proxy.notna().sum(),len(joined))); cnt=joined.diagnostic_highway.value_counts(); miss=[h for h in CORE_HW if int(cnt.get(h,0))<20]
    outp=out.resolve(); r0=(outp.parent/'highway_grade_capacity_7_9f0').resolve()
    # F0V2.11 real isolation: every declared artifact inside out; out is not the R0 dir;
    #                 and no f0v2_* artifact may leak into the R0 dir.
    art_ok=all(Path(p).resolve().parent==outp for p in written)
    r0_clean=(not r0.exists()) or (not any(q.name.startswith('f0v2_') for q in r0.iterdir()))
    iso=bool(outp.name=='highway_grade_capacity_7_9f0_v2' and outp!=r0 and art_ok and r0_clean)
    iso_detail=f'out={outp}; artifacts={len(written)} all_in_dir={art_ok}; R0_dir_clean={r0_clean}'
    # F0V2.12 real provenance: re-hash every manifest entry against what is on disk right now.
    mism=[k for k,v in manifest.items() if (not Path(v['path']).exists()) or sha256_file(Path(v['path']))!=v['sha256'] or Path(v['path']).stat().st_size!=v['size_bytes']]
    prov=bool(manifest) and not mism
    prov_detail=f'manifest_entries={len(manifest)}; rehash_mismatch={mism}'
    formal=[
      ('F0V2.01_PREREG_HASH',sha256_file(prereg).lower()==EXPECTED_PREREG_SHA256.lower(),sha256_file(prereg)),
      ('F0V2.02_ZERO_SIMULATION',zero_sim_audit(script),'AST no Java/subprocess'),
      ('F0V2.03_NETWORK_SOURCE_FIELDS',set(['from_node','to_node','length_m','highway','lanes']).issubset(src.columns), 'source structural fields'),
      ('F0V2.04_E2_ALL_TIERS_FIELDS',set(['LinkID','obs_8_9','sim_8_9_scaled','diagnostic_ratio_8_9','diagnostic_residual_8_9','representative_matsim_link_id','valid_residual','tier_output']).issubset(e2.columns),'E2 A+B_MAIN source'),
      ('F0V2.05_REP_JOIN_GE_95PCT',cov>=.95,f'coverage={cov:.6f}'),('F0V2.06_VALID_RESIDUAL_N_GE_500',len(valid)>=500,f'n={len(valid)}'),('F0V2.07_CORE_HIGHWAY_SUPPORT',not miss,f'missing={miss}; counts={cnt.to_dict()}'),('F0V2.08_CAP_LANES_COVERAGE_GE_95PCT',capcov>=.95,f'coverage={capcov:.6f}'),('F0V2.09_SPEED_COVERAGE_GE_90PCT',spcov>=.90,f'coverage={spcov:.6f}'),('F0V2.10_CAPACITY_PROXY_COVERAGE_GE_80PCT',pcov>=.80,f'coverage={pcov:.6f}'),('F0V2.11_OUTPUT_ISOLATION',iso,iso_detail),('F0V2.12_PROVENANCE',prov,prov_detail)]
    # F0V2.15 real main-equivalence: LinkID set identity + max|delta residual| == 0.
    _m=e2[['LinkID','diagnostic_residual_8_9']].merge(e2main[['LinkID','diagnostic_residual_8_9']],on='LinkID',how='inner',suffixes=('_ab','_main'))
    _dmax=float((_m.diagnostic_residual_8_9_ab-_m.diagnostic_residual_8_9_main).abs().max()) if len(_m) else float('nan')
    _idok=set(e2.LinkID)==set(e2main.LinkID)
    equiv=bool(_idok and np.isfinite(_dmax) and _dmax==0.0)
    extra=[('F0V2.13_RUNTIME_XML_PARAMETER_SOURCE',bool(xml.xml_capacity.notna().all() and xml.xml_permlanes.notna().all() and xml.speed_kmh.notna().all()),f'XML links={len(xml)}; capacity/permlanes/freespeed all non-null'),('F0V2.14_E2_AB_MAIN_SOURCE',bool(len(e2)>0 and e2.tier_output.eq('a+b_main').all() and not e2.LinkID.duplicated().any()),f'A+B_MAIN rows={len(e2)}; tier uniform; LinkID unique'),('F0V2.15_MAIN_EQUIVALENCE',equiv,f'LinkID_set_equal={_idok} (ab={e2.LinkID.nunique()}, main={e2main.LinkID.nunique()}); max|dresidual|={_dmax}')]
    return [{'check':a,'pass':bool(b),'detail':str(c)} for a,b,c in formal+extra]

def resolution(e2,e2main,xml):
    m=e2[['LinkID','diagnostic_residual_8_9']].merge(e2main[['LinkID','diagnostic_residual_8_9']],on='LinkID',how='inner',suffixes=('_ab','_main')); d=float((m.diagnostic_residual_8_9_ab-m.diagnostic_residual_8_9_main).abs().max()) if len(m) else float('nan')
    return pd.DataFrame([{'item':'NETWORK_CAPACITY_SOURCE','status':'RESOLVED','detail':'capacity/permlanes/freespeed from frozen network.xml.gz'},{'item':'E2_REPRESENTATIVE_SOURCE','status':'RESOLVED','detail':'all_tiers tier_output=A+B_MAIN'},{'item':'MAIN_ID_EQUIVALENCE','status':'PASS' if set(e2.LinkID)==set(e2main.LinkID) else 'FAIL','detail':f'ab={e2.LinkID.nunique()}, main={e2main.LinkID.nunique()}'},{'item':'MAIN_RESIDUAL_MAX_ABS_DELTA','status':'PASS' if np.isfinite(d) and d==0 else 'FAIL','detail':str(d)},{'item':'RUNTIME_XML_LINKS','status':'CHECK','detail':str(len(xml))}])

def report(out,summary,cap,tr,dm,rob,ck,status):
    lines=['# Step 7.9F-0 v2 — Highway Grade × Capacity/Speed Structural Audit','',f'**STATUS: {status}**','','正式 v2 重跑；零仿真、只读；不修改 v1.0、不产生 v1.1。','','## Core results','', '| Highway | n | Mean | Obs-w | Sim-w | Raw lanes P50 | XML lanes P50 | Cap/lane P50 | Speed P50 | Obs/cap P50 |','|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|']
    for _,r in summary[summary.highway.isin(CORE_HW)].iterrows(): lines.append(f"| {r.highway} | {int(r.n)} | {r.mean_residual:.4f} | {r.obs_weighted_residual:.4f} | {r.sim_weighted_residual:.4f} | {r.raw_lanes_median:.2f} | {r.xml_permlanes_median:.2f} | {r.capacity_per_lane_median:.1f} | {r.speed_median_kmh:.1f} | {r.obs_cap_p50:.4f} |")
    lines += ['', '## Zero-median robustness','', '| Scope | n | Zero-median n | Obs-flow share | Zero with mean_raw>0 | Obs-w residual | Sim-w residual |','|---|---:|---:|---:|---:|---:|---:|']
    for _,r in rob.iterrows(): lines.append(f"| {r.scope} | {int(r.n)} | {int(r.zero_median_n)} | {r.zero_median_obs_share:.2%} | {int(r.zero_with_mean_raw_positive)} | {r.obs_weighted_residual:.4f} | {r.sim_weighted_residual:.4f} |")
    lines += ['', '## Trend','', '| Highway | Ordinal | n | Mean | Obs-w | Sim-w |','|---|---:|---:|---:|---:|---:|']
    for _,r in tr.iterrows(): lines.append(f"| {r.highway} | {int(r.ordinal)} | {int(r.n)} | {r.mean_residual:.4f} | {r.obs_weighted_residual:.4f} | {r.sim_weighted_residual:.4f} |")
    lines += ['', '## Grade-demeaned correlations','', '| Attribute | n | Pearson | Spearman |','|---|---:|---:|---:|']
    for _,r in dm.iterrows(): lines.append(f"| {r.attribute} | {int(r.n)} | {r.pearson_grade_demeaned:.4f} | {r.spearman_grade_demeaned:.4f} |")
    lines += ['', '## Gates','', '| Check | Result | Detail |','|---|---|---|']
    for c in ck: lines.append(f"| {c['check']} | {'PASS' if c['pass'] else 'FAIL'} | {c['detail']} |")
    lines += ['', '## Boundary','', '- lookup-match 只证明当前冻结网络参数表达符合既定 lookup，不证明 lookup 数值本身正确。','- raw grade relationship 与 within-grade relationship 必须联合解释。','- capacity proxy 不是 realized v/c。','- 不回写 calibration target 或 v1.0。','']
    (out/'STEP7_9F0_v2_REPORT.md').write_text('\n'.join(lines),encoding='utf-8')

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--project-root',type=Path,default=ROOT_DEFAULT); ap.add_argument('--network',type=Path); ap.add_argument('--runtime-xml',type=Path); ap.add_argument('--e2-all',type=Path); ap.add_argument('--e2-main',type=Path); ap.add_argument('--prereg',type=Path); ap.add_argument('--out-dir',type=Path,default=OUT_REL); a=ap.parse_args(); root=a.project_root; netp=a.network or root/NETWORK_REL; xmlp=a.runtime_xml or root/XML_REL; eallp=a.e2_all or root/E2_ALL_REL; emp=a.e2_main or root/E2_MAIN_REL; pp=a.prereg or root/PREREG_REL; out=a.out_dir if a.out_dir.is_absolute() else root/a.out_dir; out.mkdir(parents=True,exist_ok=True)
    for p in [netp,xmlp,eallp,emp,pp]:
        if not p.exists(): raise FileNotFoundError(f'输入不存在: {p}')
    src=load_source(netp); xml=load_xml(xmlp); allx=load_e2_all(eallp); mainx=load_e2_main(emp); e2=select_ab(allx); z=join(e2,src,xml); s=grade_summary(z); ca=cap_audit(z); rr=rels(z); d=dm_corr(z); tr=trend(z); rob=zero_robust(z); res=resolution(e2,mainx,xml)
    cols=['LinkID','RoadCat','obs_8_9','sim_8_9_scaled','diagnostic_ratio_8_9','diagnostic_residual_8_9','sim_8_9_median_raw','sim_8_9_mean_raw','diagnostic_highway','representative_matsim_link_id','valid_residual','join_ok','highway','length_m','lanes','raw_lanes_missing','default_lanes','raw_lanes_default_equal','xml_permlanes','xml_capacity','actual_capacity_per_lane','canonical_cap_per_lane','cap_lookup_rel_diff','lookup_match_1pct','speed_kmh','obs_to_capacity_proxy','sim_to_capacity_proxy','highway_consistent']; z[cols].to_csv(out/'f0v2_link_diagnostic.csv',index=False,encoding='utf-8-sig'); s.to_csv(out/'f0v2_grade_summary.csv',index=False,encoding='utf-8-sig'); ca.to_csv(out/'f0v2_capacity_lookup_audit.csv',index=False,encoding='utf-8-sig'); tr.to_csv(out/'f0v2_grade_trend.csv',index=False,encoding='utf-8-sig'); rr.to_csv(out/'f0v2_residual_relationships.csv',index=False,encoding='utf-8-sig'); d.to_csv(out/'f0v2_correlations.csv',index=False,encoding='utf-8-sig'); rob.to_csv(out/'f0v2_zero_median_robustness.csv',index=False,encoding='utf-8-sig'); res.to_csv(out/'f0v2_input_resolution.csv',index=False,encoding='utf-8-sig'); artifacts=[out/'f0v2_link_diagnostic.csv',out/'f0v2_grade_summary.csv',out/'f0v2_capacity_lookup_audit.csv',out/'f0v2_grade_trend.csv',out/'f0v2_residual_relationships.csv',out/'f0v2_correlations.csv',out/'f0v2_zero_median_robustness.csv',out/'f0v2_input_resolution.csv',out/'f0v2_input_manifest.json',out/'f0v2_checks.csv',out/'f0v2_summary.json',out/'STEP7_9F0_v2_REPORT.md']
    manifest={};
    for k,p in {'network_source':netp,'runtime_xml':xmlp,'e2_all_tiers':eallp,'e2_main':emp,'prereg':pp,'script':Path(__file__).resolve()}.items(): manifest[k]={'path':str(p),'sha256':sha256_file(p),'size_bytes':p.stat().st_size,'mtime_ns':p.stat().st_mtime_ns}
    (out/'f0v2_input_manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8'); ck=checks(Path(__file__).resolve(),pp,src,xml,e2,mainx,z,out,manifest,artifacts); formal_ok=all(c['pass'] for c in ck[:12]); status='GRADE_CAPACITY_AUDIT_READY' if formal_ok else 'GRADE_CAPACITY_AUDIT_BLOCKED'; pd.DataFrame(ck).to_csv(out/'f0v2_checks.csv',index=False,encoding='utf-8-sig'); (out/'f0v2_summary.json').write_text(json.dumps({'step':'7.9F-0 v2','status':status,'formal_hard_pass_count':sum(bool(c['pass']) for c in ck[:12]),'formal_hard_total':12,'supplementary_pass_count':sum(bool(c['pass']) for c in ck[12:]),'supplementary_total':3,'valid_joined_residual_n':int((z.valid_residual&z.join_ok).sum()),'runtime_xml_links':int(len(xml)),'e2_ab_main_rows':int(len(e2)),'prereg_sha256':sha256_file(pp)},ensure_ascii=False,indent=2),encoding='utf-8'); report(out,s,ca,tr,d,rob,ck,status)
    print('='*84); print('STEP 7.9F-0 v2 | HIGHWAY GRADE × CAPACITY/SPEED STRUCTURAL AUDIT'); print('FORMAL RERUN / ZERO SIMULATION / READ-ONLY'); print(f'[1/6] source network links = {len(src):,}'); print(f'[2/6] runtime XML links   = {len(xml):,}'); print(f'[3/6] E2 A+B_MAIN rows    = {len(e2):,}'); print(f'[4/6] valid + joined      = {int((z.valid_residual&z.join_ok).sum()):,}'); print(f'[5/6] formal gates       = {sum(bool(c["pass"]) for c in ck[:12])}/12; supplementary={sum(bool(c["pass"]) for c in ck[12:])}/3'); print(f'[6/6] STATUS              = {status}'); print(f'      OUTPUT              = {out}'); print('      NOTE                = no MATSim/Java call'); return 0 if formal_ok else 1
if __name__=='__main__': raise SystemExit(main())
