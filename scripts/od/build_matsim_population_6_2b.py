#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Step 6.2B: full OD-cell coverage + spatial MATSim Home/Work link realization.

Model chain (nothing frozen downstream is changed):
    car Prior OD (lambda)  ->  >=1 agent per positive cell  ->  expansion factor
    Home: URANoofDwellingUnits (DU-weighted) -> Building -> zone-node link
    Work: POI -> Building -> zone-node link
    every candidate -> snapped to a real MATSim *link id*

Guarantees enforced here:
    (1) every positive OD cell gets >=1 agent            -> cell coverage = 100%
    (2) sum over agents of EF == sum of car OD trips      -> 459,794
    (3) EF_ij = T_ij / N_ij, so each cell reconstructs exactly.

Fixes applied relative to the first draft (all were fatal / silent-wrong):
    A. poi.csv uses columns `lat`/`lng` (WGS84). The draft searched for
       x|lon|longitude|wgs84_lon -> no match -> POI pool silently EMPTY, so the
       whole POI->Work down-scaling never happened. Now `lng`/`lon`/`lon`... is
       detected AND the WGS84 lon/lat is reprojected to EPSG:3414 (the network
       CRS) before snapping. Snapping degrees against metres would otherwise
       collapse every POI onto one link.
    B. MATSim population_v6.dtd declares <activity>, and
       PopulationReaderMatsimV6 switches on case ACT where ACT="activity";
       any other tag throws "[tag=... not known]". The draft emitted <act>
       -> MATSim would reject the file. Now emits <activity>.
    C. The draft wrote homeNode = zone node but home link = spatially snapped
       link (inconsistent). Now the activity node IS the snapped link's
       from_node (spatial, matching the stated "no longer on the zone-centroid
       node" intent); the zone node is kept separately as *_zone_node.
    D. Per-agent zone lookups + per-agent snapping removed: candidate links are
       snapped once per zone and sampled per cell (vectorized).

Inputs:
    reports/matsim_population/car_prior_od_lambda_*.parquet
    reports/matsim_network/{network_links_source_copy,network_nodes_source_copy}.csv
    reports/matsim_network/zone_matsim_node_map.csv
    reports/od_zone/zone_dictionary.csv
    Singapore_OD_MATSim_FinalData/04_LandUse_Building/URANoofDwellingUnits.geojson
    Singapore_OD_MATSim_FinalData/04_LandUse_Building/MasterPlan2019Buildinglayer.geojson
    Singapore_OD_MATSim_FinalData/05_POI_Enterprise/poi.csv
    Singapore_OD_MATSim_FinalData/01_Boundary_TAZ/MasterPlan2019SubzoneBoundaryNoSeaGEOJSON.geojson

Outputs (reports/matsim_population_6_2b/):
    population_lambda_*.xml.gz
    agent_spatial_assignment_lambda_*.csv
    od_cell_conservation_lambda_*.csv
    population_6_2b_summary.csv
    population_6_2b_validation.json
    spatial_source_summary.json
"""
from __future__ import annotations
import argparse, gzip, json, math, re, xml.etree.ElementTree as ET
from collections import defaultdict
from pathlib import Path
import geopandas as gpd
import numpy as np
import pandas as pd
from scipy.spatial import cKDTree

ROOT_DEFAULT = Path(r"D:\Luan\2026-05\2_Singapore")
OD_DIR = Path("reports/matsim_population")
NETWORK_DIR = Path("reports/matsim_network")
ZONE_FILE = Path("reports/od_zone/zone_dictionary.csv")
URANOF = Path("Singapore_OD_MATSim_FinalData/04_LandUse_Building/URANoofDwellingUnits.geojson")
BUILDING = Path("Singapore_OD_MATSim_FinalData/04_LandUse_Building/MasterPlan2019Buildinglayer.geojson")
POI = Path("Singapore_OD_MATSim_FinalData/05_POI_Enterprise/poi.csv")
BOUNDARY = Path("Singapore_OD_MATSim_FinalData/01_Boundary_TAZ/MasterPlan2019SubzoneBoundaryNoSeaGEOJSON.geojson")
OUT = Path("reports/matsim_population_6_2b")
DEFAULT_LAMBDAS = [0.05, 0.075, 0.10]
DEFAULT_AGENTS = 200_000
SEED = 20260912
EMPTY = pd.DataFrame(columns=["subzone_code", "x", "y"])


# ---------------------------------------------------------------- loaders ----
def load_zones(root):
    z = pd.read_csv(root / ZONE_FILE, encoding="utf-8-sig")
    for c in ["zone_id", "subzone_code", "subzone_name", "planning_area", "planning_region"]:
        if c not in z.columns:
            raise ValueError(f"zone_dictionary 缺少 {c}")
    z["zone_id"] = pd.to_numeric(z["zone_id"]).astype(int)
    z["subzone_norm"] = z["subzone_code"].astype(str).str.upper().str.strip()
    if len(z) != 332:
        raise ValueError(f"zone_dictionary 应332行，实际{len(z)}")
    return z.sort_values("zone_id").reset_index(drop=True)


def load_zone_nodes(root):
    z = pd.read_csv(root / NETWORK_DIR / "zone_matsim_node_map.csv", encoding="utf-8-sig")
    z["zone_id"] = pd.to_numeric(z["zone_id"]).astype(int)
    z["matsim_node_id"] = pd.to_numeric(z["matsim_node_id"]).astype(int)
    if len(z) != 332:
        raise ValueError("zone_matsim_node_map 不是332行")
    return z


def load_network(root):
    e = pd.read_csv(root / NETWORK_DIR / "network_links_source_copy.csv", encoding="utf-8-sig")
    n = pd.read_csv(root / NETWORK_DIR / "network_nodes_source_copy.csv", encoding="utf-8-sig")
    for c in ["from_node", "to_node"]:
        e[c] = pd.to_numeric(e[c]).astype(int)
    n["node_id"] = pd.to_numeric(n["node_id"]).astype(int)
    e = e.merge(n.rename(columns={"node_id": "from_node", "x_svy21_m": "from_x", "y_svy21_m": "from_y"}),
                on="from_node", how="left")
    e = e.merge(n.rename(columns={"node_id": "to_node", "x_svy21_m": "to_x", "y_svy21_m": "to_y"}),
                on="to_node", how="left")
    if e[["from_x", "to_x"]].isna().any().any():
        raise ValueError("有边引用了不存在的节点")
    e["mid_x"] = (e.from_x + e.to_x) / 2
    e["mid_y"] = (e.from_y + e.to_y) / 2
    e["matsim_link_id"] = "e" + e.from_node.astype(str) + "_" + e.to_node.astype(str)
    if e.matsim_link_id.duplicated().any():
        raise ValueError("存在重复的有向 link id")
    return e, cKDTree(e[["mid_x", "mid_y"]].to_numpy(float))


def load_od(root, lam):
    tag = f"{lam:.3f}".replace(".", "p")
    p = root / OD_DIR / f"car_prior_od_lambda_{tag}.parquet"
    q = root / OD_DIR / f"car_prior_od_lambda_{tag}.csv"
    path = p if p.exists() else q
    if not path.exists():
        raise FileNotFoundError(path)
    od = pd.read_parquet(path) if path.suffix == ".parquet" else pd.read_csv(path, encoding="utf-8-sig")
    od["origin_zone"] = pd.to_numeric(od.origin_zone).astype(int)
    od["destination_zone"] = pd.to_numeric(od.destination_zone).astype(int)
    od["trips"] = pd.to_numeric(od.trips, errors="coerce").fillna(0)
    od = od[od.trips > 1e-12].copy()
    if od.empty:
        raise ValueError("OD 为空")
    return od


# ------------------------------------------------------- spatial sources ----
def _read_geojson_points(root, path, zone_code, weight_col=None):
    """Join a point/polygon layer to the subzone boundary and return SVY21 points."""
    if not path.exists():
        return EMPTY.copy()
    g = gpd.read_file(path)
    if g.empty:
        return EMPTY.copy()
    if g.crs is None:
        g = g.set_crs("EPSG:4326")
    g = g.to_crs("EPSG:3414")
    b = gpd.read_file(root / BOUNDARY)
    if b.crs is None:
        b = b.set_crs("EPSG:4326")
    b = b.to_crs("EPSG:3414")
    g["geometry"] = g.geometry.representative_point()
    j = gpd.sjoin(g, b[[zone_code, "geometry"]], how="inner", predicate="within")
    if j.empty:
        return EMPTY.copy()
    out = pd.DataFrame({
        "subzone_code": j[zone_code].astype(str).str.upper().str.strip().to_numpy(),
        "x": j.geometry.x.to_numpy(),
        "y": j.geometry.y.to_numpy(),
    })
    if weight_col is not None and weight_col in j.columns:
        w = pd.to_numeric(j[weight_col], errors="coerce").to_numpy(float)
        out["w"] = np.where(np.isfinite(w) & (w > 0), w, 1.0)
    return out


def load_uranof(root):
    return _read_geojson_points(root, root / URANOF, "SUBZONE_C", weight_col="DU")


def load_building(root):
    return _read_geojson_points(root, root / BUILDING, "SUBZONE_C")


def load_poi(root):
    """poi.csv: columns SUBZONE_C + lat/lng in WGS84 -> reproject to EPSG:3414."""
    p = root / POI
    if not p.exists():
        return EMPTY.copy()
    d = pd.read_csv(p, low_memory=False)
    zc = next((c for c in d.columns if str(c).upper() in {"SUBZONE_C", "SUBZONECODE"}), None)
    xc = next((c for c in d.columns if str(c).lower() in
               {"lng", "lon", "long", "longitude", "x", "wgs84_lon"}), None)
    yc = next((c for c in d.columns if str(c).lower() in
               {"lat", "latitude", "y", "wgs84_lat"}), None)
    if not all([zc, xc, yc]):
        print("WARN: POI 无法识别列名，跳过。前若干列:", list(d.columns)[:12])
        return EMPTY.copy()
    d = d[[zc, xc, yc]].copy()
    d[xc] = pd.to_numeric(d[xc], errors="coerce")
    d[yc] = pd.to_numeric(d[yc], errors="coerce")
    d = d.dropna()
    if d.empty:
        return EMPTY.copy()
    # auto-detect geographic degrees vs projected metres
    deg = (d[xc].abs().median() < 180) and (d[yc].abs().median() < 90)
    if deg:
        pts = gpd.GeoDataFrame(geometry=gpd.points_from_xy(d[xc], d[yc]), crs="EPSG:4326").to_crs("EPSG:3414")
        xs = pts.geometry.x.to_numpy()
        ys = pts.geometry.y.to_numpy()
    else:
        xs = d[xc].to_numpy(float)
        ys = d[yc].to_numpy(float)
    return pd.DataFrame({"subzone_code": d[zc].astype(str).str.upper().str.strip().to_numpy(),
                         "x": xs, "y": ys})


def build_link_pools(points, tree, edges, source_label):
    """snap every candidate point ONCE; return {subzone_code: dict(links,nodes,w,source)}."""
    pools = {}
    if points is None or points.empty:
        return pools
    xy = points[["x", "y"]].to_numpy(float)
    _, idx = tree.query(xy, k=1)
    sub = edges.iloc[idx]
    links = sub.matsim_link_id.to_numpy()
    nodes = sub.from_node.to_numpy()
    w = points["w"].to_numpy(float) if "w" in points.columns else np.ones(len(points))
    codes = points.subzone_code.to_numpy()
    bucket = defaultdict(list)
    for c, l, nd, ww in zip(codes, links, nodes, w):
        bucket[c].append((l, int(nd), float(ww)))
    for c, rows in bucket.items():
        pools[c] = {"links": np.array([r[0] for r in rows], dtype=object),
                    "nodes": np.array([r[1] for r in rows], dtype=np.int64),
                    "w": np.array([r[2] for r in rows], dtype=float),
                    "source": source_label}
    return pools


# ------------------------------------------------------------- sampling -----
def allocate_cells(od, target, rng):
    """>=1 agent per positive cell, remainder by largest-remainder on trips."""
    if target < len(od):
        raise ValueError(f"agents {target} < positive OD cells {len(od)}")
    rem = target - len(od)
    w = od.trips.to_numpy(float)
    w = w / w.sum()
    raw = rem * w
    extra = np.floor(raw).astype(int)
    cnt = 1 + extra
    left = target - int(cnt.sum())
    if left > 0:
        frac = raw - extra
        order = np.argsort(-(frac + rng.random(len(frac)) * 1e-12))
        cnt[order[:left]] += 1
    out = od.copy()
    out["agent_count"] = cnt
    out["expansion_factor"] = out.trips / out.agent_count
    return out


def weighted_sample_idx(weights, n, rng):
    if weights is None or len(weights) == 0:
        return None
    if not np.isfinite(weights).all() or weights.sum() <= 0:
        return rng.integers(0, len(weights), size=n)
    cum = np.cumsum(weights)
    u = rng.random(n) * cum[-1]
    return np.clip(np.searchsorted(cum, u, side="right"), 0, len(weights) - 1)


# ----------------------------------------------------------------- XML ------
def write_population(pop, path):
    root = ET.Element("population", {"desc": "Singapore Step 6.2B spatially realized car population"})
    for r in pop.itertuples(index=False):
        person = ET.SubElement(root, "person", {"id": r.agent_id})
        attrs = ET.SubElement(person, "attributes")
        for name, val, cls in [
            ("originZone", r.origin_zone, "java.lang.Integer"),
            ("destinationZone", r.destination_zone, "java.lang.Integer"),
            ("homeNode", r.home_node, "java.lang.Integer"),
            ("workNode", r.work_node, "java.lang.Integer"),
            ("expansionFactor", r.expansion_factor, "java.lang.Double"),
            ("odTrips", r.od_trips, "java.lang.Double"),
            ("homeSource", r.home_source, "java.lang.String"),
            ("workSource", r.work_source, "java.lang.String"),
        ]:
            # population_v6.dtd: <!ELEMENT attribute (#PCDATA)>
            # 值必须写在元素正文里；写成 value="..." 属性会被 DTD 校验拒绝
            # （"Element <attribute> has no attribute value"）。
            el = ET.SubElement(attrs, "attribute", {"name": name, "class": cls})
            el.text = str(val)
        plan = ET.SubElement(person, "plan", {"selected": "yes"})
        # MATSim population_v6.dtd element name is <activity>
        ET.SubElement(plan, "activity", {"type": "home", "link": str(r.home_link), "end_time": "08:00:00"})
        ET.SubElement(plan, "leg", {"mode": "car"})
        ET.SubElement(plan, "activity", {"type": "work", "link": str(r.work_link)})
    ET.indent(root, space="  ")
    # 必须写 DOCTYPE：否则 MATSim 的 MatsimXmlParser 无法识别 population 版本
    body = ET.tostring(root, encoding="unicode")
    text = ('<?xml version="1.0" encoding="utf-8"?>\n'
            '<!DOCTYPE population SYSTEM "http://www.matsim.org/files/dtd/population_v6.dtd">\n'
            + body + "\n")
    with gzip.open(path, "wb", compresslevel=6) as f:
        f.write(text.encode("utf-8"))


# ---------------------------------------------------------------- main ------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--project-root", type=Path, default=ROOT_DEFAULT)
    ap.add_argument("--lambdas", nargs="+", type=float, default=DEFAULT_LAMBDAS)
    ap.add_argument("--target-agents", type=int, default=DEFAULT_AGENTS)
    ap.add_argument("--seed", type=int, default=SEED)
    args = ap.parse_args()
    root = args.project_root
    out = root / OUT
    out.mkdir(parents=True, exist_ok=True)

    zones = load_zones(root)
    zone_nodes = load_zone_nodes(root)
    edges, tree = load_network(root)
    zone_code = dict(zip(zones.zone_id, zones.subzone_norm))
    zone_node = dict(zip(zone_nodes.zone_id, zone_nodes.matsim_node_id))
    node_first_link = {}
    for fr, lid in zip(edges.from_node.to_numpy(), edges.matsim_link_id.to_numpy()):
        node_first_link.setdefault(int(fr), str(lid))

    print("Loading spatial sources...")
    ur_pts = load_uranof(root)
    bu_pts = load_building(root)
    po_pts = load_poi(root)
    ur_pool = build_link_pools(ur_pts, tree, edges, "uranof")
    bu_pool = build_link_pools(bu_pts, tree, edges, "building")
    po_pool = build_link_pools(po_pts, tree, edges, "poi")
    source_stats = {
        "uranof_points": int(len(ur_pts)), "building_points": int(len(bu_pts)), "poi_points": int(len(po_pts)),
        "uranof_subzones": int(len(ur_pool)), "building_subzones": int(len(bu_pool)), "poi_subzones": int(len(po_pool)),
        "home_uranof_zones": int(sum(1 for z in zones.zone_id if zone_code[z] in ur_pool)),
        "home_building_only_zones": int(sum(1 for z in zones.zone_id if zone_code[z] not in ur_pool and zone_code[z] in bu_pool)),
        "home_fallback_zones": int(sum(1 for z in zones.zone_id if zone_code[z] not in ur_pool and zone_code[z] not in bu_pool)),
        "work_poi_zones": int(sum(1 for z in zones.zone_id if zone_code[z] in po_pool)),
        "work_building_only_zones": int(sum(1 for z in zones.zone_id if zone_code[z] not in po_pool and zone_code[z] in bu_pool)),
        "work_fallback_zones": int(sum(1 for z in zones.zone_id if zone_code[z] not in po_pool and zone_code[z] not in bu_pool)),
        "home_sampling": "URANOF DU-weighted, else building uniform, else zone-node incident link",
        "work_sampling": "POI uniform, else building uniform, else zone-node incident link",
    }
    print("  ", source_stats)
    with open(out / "spatial_source_summary.json", "w", encoding="utf-8") as f:
        json.dump(source_stats, f, ensure_ascii=False, indent=2)

    summaries = []
    for lam in args.lambdas:
        rng = np.random.default_rng(args.seed + int(round(lam * 1000)))
        od = allocate_cells(load_od(root, lam), args.target_agents, rng)
        print(f"lambda={lam:.3f}: positive cells={len(od)}  agents={int(od.agent_count.sum())}")

        ids, oz, dz, hn, wn, hl, wl, hsrc, wsrc, otrips, efac = ([] for _ in range(11))
        counter = 0
        for r in od.itertuples(index=False):
            oi = int(r.origin_zone)
            dj = int(r.destination_zone)
            n = int(r.agent_count)
            oc = zone_code[oi]
            dc = zone_code[dj]

            # ---- home side
            hp = ur_pool.get(oc)
            if hp is not None:
                h_links, h_nodes, h_src = hp["links"], hp["nodes"], "uranof"
                h_w = hp["w"]
            else:
                hp = bu_pool.get(oc)
                if hp is not None:
                    h_links, h_nodes, h_src = hp["links"], hp["nodes"], "building"
                    h_w = None
                else:
                    fb = node_first_link.get(zone_node[oi])
                    if fb is None:
                        raise ValueError(f"zone {oi} 的 zone node 无关联 link")
                    h_links = np.array([fb] * n, dtype=object)
                    h_nodes = np.array([zone_node[oi]] * n, dtype=np.int64)
                    h_src = "zone_node_fallback"
                    h_w = None
            if h_w is not None:
                sel = weighted_sample_idx(h_w, n, rng)
                h_link = h_links[sel]
                h_node = h_nodes[sel]
            elif h_src == "zone_node_fallback":
                h_link = h_links
                h_node = h_nodes
            else:
                sel = rng.integers(0, len(h_links), size=n)
                h_link = h_links[sel]
                h_node = h_nodes[sel]

            # ---- work side
            wp = po_pool.get(dc)
            if wp is not None:
                w_links, w_nodes, w_src = wp["links"], wp["nodes"], "poi"
            else:
                wp = bu_pool.get(dc)
                if wp is not None:
                    w_links, w_nodes, w_src = wp["links"], wp["nodes"], "building"
                else:
                    fb = node_first_link.get(zone_node[dj])
                    if fb is None:
                        raise ValueError(f"zone {dj} 的 zone node 无关联 link")
                    w_links = np.array([fb] * n, dtype=object)
                    w_nodes = np.array([zone_node[dj]] * n, dtype=np.int64)
                    w_src = "zone_node_fallback"
            sel = rng.integers(0, len(w_links), size=n)
            w_link = w_links[sel]
            w_node = w_nodes[sel]

            ids.extend([f"a{i:07d}" for i in range(counter + 1, counter + n + 1)])
            counter += n
            oz.extend([oi] * n); dz.extend([dj] * n)
            hn.extend(h_node.tolist()); wn.extend(w_node.tolist())
            hl.extend(h_link.tolist()); wl.extend(w_link.tolist())
            hsrc.extend([h_src] * n); wsrc.extend([w_src] * n)
            otrips.extend([float(r.trips)] * n); efac.extend([float(r.expansion_factor)] * n)

        pop = pd.DataFrame({
            "agent_id": ids, "origin_zone": oz, "destination_zone": dz,
            "home_node": hn, "work_node": wn, "home_link": hl, "work_link": wl,
            "home_source": hsrc, "work_source": wsrc,
            "od_trips": otrips, "expansion_factor": efac,
        })
        tag = f"{lam:.3f}".replace(".", "p")
        pop.to_csv(out / f"agent_spatial_assignment_lambda_{tag}.csv", index=False, encoding="utf-8-sig")
        write_population(pop, out / f"population_lambda_{tag}.xml.gz")

        realized = pop.groupby(["origin_zone", "destination_zone"])["expansion_factor"].sum().reset_index(name="realized")
        chk = od[["origin_zone", "destination_zone", "trips", "agent_count"]].merge(
            realized, on=["origin_zone", "destination_zone"], how="left").fillna({"realized": 0})
        chk["abs_error"] = (chk.realized - chk.trips).abs()
        chk["agents_present"] = chk.agent_count
        chk.to_csv(out / f"od_cell_conservation_lambda_{tag}.csv", index=False, encoding="utf-8-sig")

        hs = pop.home_source.value_counts().to_dict()
        wsv = pop.work_source.value_counts().to_dict()
        summary = {
            "lambda_per_min": lam, "agents": int(len(pop)), "positive_od_cells": int(len(od)),
            "od_cell_coverage": float((od.agent_count > 0).mean()),
            "cells_with_agents": int(chk.loc[chk.realized > 0].shape[0]),
            "real_trip_equivalent": float(pop.expansion_factor.sum()),
            "car_od_total": float(od.trips.sum()),
            "max_od_cell_error": float(chk.abs_error.max()),
            "missing_cells": int((chk.realized <= 0).sum()),
            "home_uranof_agents": int(hs.get("uranof", 0)), "home_building_agents": int(hs.get("building", 0)),
            "home_fallback_agents": int(hs.get("zone_node_fallback", 0)),
            "work_poi_agents": int(wsv.get("poi", 0)), "work_building_agents": int(wsv.get("building", 0)),
            "work_fallback_agents": int(wsv.get("zone_node_fallback", 0)),
            "status": "PASS" if (len(pop) == args.target_agents and float(chk.abs_error.max()) < 1e-8
                                 and int((chk.realized <= 0).sum()) == 0 and float((od.agent_count > 0).mean()) == 1.0)
                      else "FAIL",
        }
        summaries.append(summary)
        print("   ", {k: summary[k] for k in ["od_cell_coverage", "real_trip_equivalent", "max_od_cell_error", "status"]})

    pd.DataFrame(summaries).to_csv(out / "population_6_2b_summary.csv", index=False, encoding="utf-8-sig")
    overall = "PASS" if all(x["status"] == "PASS" for x in summaries) else "FAIL"
    with open(out / "population_6_2b_validation.json", "w", encoding="utf-8") as f:
        json.dump({"status": overall, "target_agents": args.target_agents, "lambdas": args.lambdas,
                   "source_stats": source_stats,
                   "rule": "every positive OD cell gets >=1 agent; EF_ij = T_ij / N_ij so each cell reconstructs exactly",
                   "matsim_activity_element": "activity"},
                  f, ensure_ascii=False, indent=2)
    print("STATUS:", overall)
    print("OUTPUT:", out)


if __name__ == "__main__":
    main()
