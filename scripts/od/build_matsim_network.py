#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations
import argparse,gzip,json,math
from pathlib import Path
import numpy as np,pandas as pd
import xml.etree.ElementTree as ET
ROOT_DEFAULT=Path(r'D:\Luan\2026-05\2_Singapore')
NETWORK=Path('reports/od_impedance/network_links.csv')
NODES=Path('reports/od_impedance/network_nodes.csv')
SNAP=Path('reports/od_impedance/zone_network_snap.csv')
ZONES=Path('reports/od_zone/zone_dictionary.csv')
OUT=Path('reports/matsim_network')
CAPACITY_PER_LANE={'motorway':1900.,'motorway_link':1700.,'trunk':1800.,'trunk_link':1600.,'primary':1500.,'primary_link':1300.,'secondary':1200.,'secondary_link':1100.,'tertiary':900.,'tertiary_link':800.,'residential':700.,'service':400.,'unclassified':600.}
DEFAULT_LANES={'motorway':2.,'motorway_link':1.,'trunk':2.,'trunk_link':1.,'primary':2.,'primary_link':1.,'secondary':2.,'secondary_link':1.,'tertiary':1.,'tertiary_link':1.,'residential':1.,'service':1.,'unclassified':1.}

def fnum(x):
    try:
        v=float(x); return v if math.isfinite(v) else np.nan
    except: return np.nan

def _hw_norm(e):
    return e['highway'].astype(str).str.lower().str.strip()

def lanes_vec(e):
    # Vectorised equivalent of the old row-wise lanes(): use the OSM `lanes` value
    # when it is a sane 1..20, otherwise the highway-class default. Numerically identical.
    ln=pd.to_numeric(e['lanes'],errors='coerce') if 'lanes' in e.columns else pd.Series(np.nan,index=e.index)
    default=_hw_norm(e).map(DEFAULT_LANES).fillna(1.0).to_numpy(float)
    vals=ln.to_numpy(float)
    ok=np.isfinite(vals)&(vals>=1)&(vals<=20)
    return np.where(ok,vals,default)

def capacity_vec(e,lane_arr):
    per=_hw_norm(e).map(CAPACITY_PER_LANE).fillna(700.0).to_numpy(float)
    return lane_arr*per

def load(root):
    e=pd.read_csv(root/NETWORK,encoding='utf-8-sig',low_memory=False)
    n=pd.read_csv(root/NODES,encoding='utf-8-sig',low_memory=False)
    s=pd.read_csv(root/SNAP,encoding='utf-8-sig',low_memory=False)
    reqe={'from_node','to_node','length_m','travel_time_s','speed_kmh','highway'}
    reqn={'node_id','x_svy21_m','y_svy21_m'}
    if reqe-set(e.columns):raise ValueError(f'network_links missing {sorted(reqe-set(e.columns))}')
    if reqn-set(n.columns):raise ValueError(f'network_nodes missing {sorted(reqn-set(n.columns))}')
    if len(n)!=429032: raise ValueError(f'Expected 429032 nodes, got {len(n)}')
    for c in ['from_node','to_node']:e[c]=pd.to_numeric(e[c]).astype(int)
    for c in ['length_m','travel_time_s','speed_kmh']:e[c]=pd.to_numeric(e[c],errors='coerce')
    n['node_id']=pd.to_numeric(n.node_id).astype(int)
    n['x_svy21_m']=pd.to_numeric(n.x_svy21_m,errors='coerce');n['y_svy21_m']=pd.to_numeric(n.y_svy21_m,errors='coerce')
    node_set=set(n.node_id)
    if not e.from_node.isin(node_set).all() or not e.to_node.isin(node_set).all():raise ValueError('Orphan network endpoints')
    return e,n,s

def build_xml(e,n,path):
    fo=e.from_node.to_numpy(dtype=np.int64); to=e.to_node.to_numpy(dtype=np.int64)
    length=e.length_m.to_numpy(float); speed=e.speed_kmh.to_numpy(float)
    ln=lanes_vec(e); cap=capacity_vec(e,ln)
    ids=[f"e{int(a)}_{int(b)}" for a,b in zip(fo,to)]
    if len(ids)!=len(set(ids)):raise ValueError('Duplicate directed link IDs')
    # 注意：network_v2.dtd 只为 <network> 声明了 name 一个属性（ATTLIST network name ...）。
    # 因此**不能**再写 changeEvents 之类属性，否则 MATSim 的 DTD 校验会报
    # "Element <network> has no attribute ..."。
    root=ET.Element('network',{'name':'Singapore Step6.1 validated directed OSM network'})
    ns=ET.SubElement(root,'nodes')   # network_v2.dtd: <!ELEMENT nodes (node)*>，无 ATTLIST
    nid=n.node_id.to_numpy(dtype=np.int64); nx=n.x_svy21_m.to_numpy(float); ny=n.y_svy21_m.to_numpy(float)
    for i in np.argsort(nid,kind='stable'):
        ET.SubElement(ns,'node',{'id':str(int(nid[i])),'x':f'{nx[i]:.3f}','y':f'{ny[i]:.3f}'})
    ls=ET.SubElement(root,'links',{'capperiod':'01:00:00'})
    for i in range(len(fo)):
        ET.SubElement(ls,'link',{'id':ids[i],'from':str(int(fo[i])),'to':str(int(to[i])),'length':f'{length[i]:.3f}','freespeed':f'{speed[i]/3.6:.6f}','capacity':f'{cap[i]:.3f}','permlanes':f'{ln[i]:.3f}','oneway':'1','modes':'car'})
    ET.indent(ET.ElementTree(root),space='  ')
    path.parent.mkdir(parents=True,exist_ok=True)
    # 必须写 DOCTYPE：MATSim 的 MatsimXmlParser 靠 DTD system-id 识别文件版本，
    # 缺失会抛 "Missing DOCTYPE." / 解析器 delegate 为 null。
    body=ET.tostring(root,encoding='unicode')
    text=('<?xml version="1.0" encoding="utf-8"?>\n'
          '<!DOCTYPE network SYSTEM "http://www.matsim.org/files/dtd/network_v2.dtd">\n'
          +body+'\n')
    with gzip.open(path,'wb') as g: g.write(text.encode('utf-8'))

def zone_map(root,s,n):
    z=pd.read_csv(root/ZONES,encoding='utf-8-sig',low_memory=False)
    col='nearest_node' if 'nearest_node' in s.columns else 'nearest_network_node' if 'nearest_network_node' in s.columns else None
    if col is None:raise ValueError('zone_network_snap missing nearest_node')
    s['zone_id']=pd.to_numeric(s.zone_id).astype(int);s[col]=pd.to_numeric(s[col]).astype(int)
    node_set=set(n.node_id)
    if not s[col].isin(node_set).all():raise ValueError('Zone snap node outside network_nodes')
    m=z[['zone_id','subzone_code','subzone_name']].merge(s[['zone_id',col]+(['snap_distance_m'] if 'snap_distance_m' in s.columns else [])],on='zone_id',how='left').rename(columns={col:'matsim_node_id'})
    if len(m)!=332 or m.matsim_node_id.isna().any():raise ValueError('Zone mapping incomplete')
    m.matsim_node_id=m.matsim_node_id.astype(int)
    return m

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--project-root',type=Path,default=ROOT_DEFAULT);a=ap.parse_args();root=a.project_root;out=root/OUT;out.mkdir(parents=True,exist_ok=True)
    e,n,s=load(root); build_xml(e,n,out/'network.xml.gz'); e.to_csv(out/'network_links_source_copy.csv',index=False,encoding='utf-8-sig');n.to_csv(out/'network_nodes_source_copy.csv',index=False,encoding='utf-8-sig');zm=zone_map(root,s,n);zm.to_csv(out/'zone_matsim_node_map.csv',index=False,encoding='utf-8-sig')
    summary={'status':'PASS','nodes':len(n),'directed_edges':len(e),'zone_count':len(zm),'duplicate_directed_edges':int(e[['from_node','to_node']].duplicated().sum()),'speed_median_kmh':float(e.speed_kmh.median()),'speed_max_kmh':float(e.speed_kmh.max()),'lanes_median':float(np.median(lanes_vec(e))),'zone_snap_max_m':float(zm.snap_distance_m.max()) if 'snap_distance_m' in zm.columns else None,'capacity_assumption':'lanes × highway-class default veh/h/lane','capacity_per_lane':CAPACITY_PER_LANE,'network_semantics':{'modes':'car','direction':'Step-4 directed topology','freespeed_source':'Step-4 speed_kmh','crs':'EPSG:3414'}}
    if summary['duplicate_directed_edges']>0:summary['status']='FAIL'
    with open(out/'network_validation.json','w',encoding='utf-8') as f:json.dump(summary,f,ensure_ascii=False,indent=2)
    print('STATUS:',summary['status']);print('nodes:',len(n));print('directed_edges:',len(e));print('zones:',len(zm));print('network:',out/'network.xml.gz')
if __name__=='__main__':main()
