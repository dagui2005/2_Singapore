#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Singapore OD -> MATSim Step 4: directed road network and 332x332 AM-peak impedance matrix.

冻结口径（与数据字典 / 用户约定一致）
------------------------------------------------
* 机动车网络：motorway/trunk/primary/secondary/tertiary/residential/service/unclassified 及 *_link
  排除 footway/steps/cycleway/path/pedestrian 等非机动车道路。
* 速度：优先 OSM `maxspeed`（支持 km/h 与 mph），缺失时回退 highway 等级默认速度。
* 方向：oneway=yes -> 正向；oneway=-1 -> 反向；oneway=no / 空 -> 双向。
  本矩阵**不做对称化**：有向网络下 c_ij != c_ji 属正常。
* 空间：统一 EPSG:3414 (SVY21)；节点按 0.1 m 网格合并。
* 接入：Subzone 质心吸附到**最大强连通分量 (giant SCC)** 内最近节点，保证 332 个 Subzone 可路由。
  （弱连通不保证有向可达；早期用弱分量曾命中 2 个单向死胡同节点，造成 661 个不可达 OD。）
* 最短路：scipy.sparse.csgraph.dijkstra（C 实现）。不使用 networkx（当前 conda 环境未安装，
  且纯 Python 实现在 ~63 万节点网络上不可行）。

输出 reports/od_impedance/
    network_links.csv         有向边清单
                              from_node,to_node,travel_time_s,length_m,speed_kmh,
                              highway,lanes,name
                              （name/lanes 供 Step 5C.1 同名道路速度传播使用）
    network_nodes.csv         节点 id -> SVY21(/WGS84) 坐标（Step 5C 速度转移必需）
    network_audit.csv         按 highway 等级的路网审计
    network_audit.json        路网审计汇总
    zone_network_snap.csv     332 个 Subzone 接入节点与吸附距离
    impedance_matrix.parquet  110,224 行 OD 阻抗
    impedance_matrix.csv      同上（CSV 便于肉眼核对）
    impedance_validation.json 校验汇总
"""
from __future__ import annotations

import argparse
import json
import math
import re
import time
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components, dijkstra
from scipy.spatial import cKDTree

# ----------------------------------------------------------------------------- config
DEFAULT_PROJECT_ROOT = Path(r"D:\Luan\2026-05\2_Singapore")
DATA_DIR = "Singapore_OD_MATSim_FinalData"
ZONE_FILE = Path("reports/od_zone/zone_dictionary.csv")
OSM_FILE = Path(f"{DATA_DIR}/07_RoadNetwork/osm-lines.shp")
OUT_DIR = "reports/od_impedance"

ALLOWED = {
    "motorway", "trunk", "primary", "secondary", "tertiary",
    "residential", "service", "unclassified",
    "motorway_link", "trunk_link", "primary_link", "secondary_link", "tertiary_link",
}
ORDER = ["motorway", "trunk", "primary", "secondary", "tertiary", "residential",
         "service", "unclassified", "motorway_link", "trunk_link", "primary_link",
         "secondary_link", "tertiary_link"]
DEFAULT_SPEED = {
    "motorway": 90, "trunk": 80, "primary": 60, "secondary": 50, "tertiary": 40,
    "residential": 30, "service": 20, "unclassified": 30,
    "motorway_link": 50, "trunk_link": 50, "primary_link": 40,
    "secondary_link": 40, "tertiary_link": 30,
}
MAX_SPEED, MIN_SPEED = 130.0, 5.0
SNAP_MAX_M, ROUND_M = 1000.0, 0.1
NO_ROAD_ACCESS_M = 1500.0     # 吸附距离超过此值视为「无机动车道路接入」（离岛等）
READ_COLS = ["highway", "oneway", "maxspeed", "lanes", "name", "geometry"]


# ----------------------------------------------------------------------------- helpers
def stext(x):
    if x is None or (isinstance(x, float) and math.isnan(x)):
        return ""
    return re.sub(r"\s+", " ", str(x).replace("\xa0", " ").strip())


def parse_oneway(x):
    """0 = 双向, 1 = 正向(u->v), -1 = 反向(v->u)."""
    s = stext(x).lower()
    if s in {"yes", "true", "1"}:
        return 1
    if s in {"-1", "reverse"}:
        return -1
    return 0


_SPEED_RE = re.compile(r"(\d+(?:\.\d+)?)\s*(mph|km/?h)?", re.I)


def parse_speed(x):
    s = stext(x).lower()
    if not s:
        return None
    m = _SPEED_RE.search(s)
    if not m:
        return None
    try:
        v = float(m.group(1))
    except ValueError:
        return None
    unit = (m.group(2) or "kmh").lower()
    if unit == "mph":
        v *= 1.609344
    return v if MIN_SPEED <= v <= MAX_SPEED else None


def parse_lanes(x):
    m = re.search(r"(\d+(?:\.\d+)?)", stext(x))
    if not m:
        return None
    try:
        v = float(m.group(1))
    except ValueError:
        return None
    return v if 1 <= v <= 20 else None


def _lines(geom):
    gt = geom.geom_type
    if gt == "LineString":
        yield list(geom.coords)
    elif gt == "MultiLineString":
        for p in geom.geoms:
            yield list(p.coords)


def read_osm(path):
    """优先读取 *_expanded.shp 的 ASCII 子集列（含 oneway/maxspeed/lanes 展开列），
    绕开 other_tags 字段的非法字节导致的 UTF-8 解码失败。"""
    expanded = path.with_name(path.stem + "_expanded.shp")
    target = expanded if expanded.exists() else path
    g = gpd.read_file(target, columns=READ_COLS)
    for c in ["highway", "oneway", "maxspeed", "lanes", "name"]:
        if c not in g.columns:
            g[c] = ""
    return g[READ_COLS], str(target.name)


# ----------------------------------------------------------------------------- network
def build_graph(g):
    if g.crs is None:
        g = g.set_crs("EPSG:4326")
    g = g.to_crs("EPSG:3414")
    g["highway"] = g["highway"].map(stext).str.lower()
    g = g[g.highway.isin(ALLOWED)].copy()
    g = g[g.geometry.notna() & (~g.geometry.is_empty)]

    node_lookup: dict = {}
    nodes: list = []
    best: dict = {}          # (u, v) -> (tt_s, length_m, speed, lanes, hw)
    feat = {h: {"features": 0, "segments": 0, "length_m": 0.0,
                "oneway_yes": 0, "oneway_rev": 0, "oneway_both": 0,
                "maxspeed_osm": 0, "maxspeed_default": 0, "lanes_known": 0}
            for h in ORDER}

    t0 = time.time()
    for hw, ow_raw, sp_raw, ln_raw, nm_raw, geom in zip(
            g["highway"], g["oneway"], g["maxspeed"], g["lanes"], g["name"], g.geometry):
        f = feat.setdefault(hw, {"features": 0, "segments": 0, "length_m": 0.0,
                                 "oneway_yes": 0, "oneway_rev": 0, "oneway_both": 0,
                                 "maxspeed_osm": 0, "maxspeed_default": 0, "lanes_known": 0})
        f["features"] += 1
        parsed = parse_speed(sp_raw)
        speed = parsed if parsed else DEFAULT_SPEED.get(hw, 30)
        f["maxspeed_osm" if parsed else "maxspeed_default"] += 1
        lanes = parse_lanes(ln_raw)
        if lanes:
            f["lanes_known"] += 1
        name = stext(nm_raw)
        ow = parse_oneway(ow_raw)
        f["oneway_yes" if ow == 1 else ("oneway_rev" if ow == -1 else "oneway_both")] += 1

        for coords in _lines(geom):
            ids = []
            for c in coords:
                x, y = float(c[0]), float(c[1])
                k = (round(x / ROUND_M) * ROUND_M, round(y / ROUND_M) * ROUND_M)
                i = node_lookup.get(k)
                if i is None:
                    i = len(nodes)
                    node_lookup[k] = i
                    nodes.append(k)
                ids.append(i)
            for u, v in zip(ids[:-1], ids[1:]):
                if u == v:
                    continue
                x1, y1 = nodes[u]
                x2, y2 = nodes[v]
                L = math.hypot(x2 - x1, y2 - y1)
                if L <= 0:
                    continue
                tt = L / (speed * 1000.0 / 3600.0)
                if ow == 1:
                    pairs = ((u, v),)
                elif ow == -1:
                    pairs = ((v, u),)
                else:
                    pairs = ((u, v), (v, u))
                f["segments"] += len(pairs)
                f["length_m"] += L
                for a, b in pairs:
                    key = (a, b)
                    old = best.get(key)
                    if old is None or tt < old[0]:
                        best[key] = (tt, L, speed, lanes, hw, name)

    n = len(nodes)
    xy = np.asarray(nodes, dtype=float) if nodes else np.zeros((0, 2))
    if best:
        keys = np.asarray(list(best.keys()), dtype=np.int64)
        u = keys[:, 0]
        v = keys[:, 1]
        vals = list(best.values())
        tt = np.fromiter((z[0] for z in vals), dtype=float)
        ll = np.fromiter((z[1] for z in vals), dtype=float)
        sp = np.fromiter((z[2] for z in vals), dtype=float)
        lns = np.fromiter((z[3] if z[3] is not None else np.nan for z in vals), dtype=float)
        hwn = np.fromiter((z[4] for z in vals), dtype=object)
        nms = np.fromiter((z[5] for z in vals), dtype=object)
    else:
        u = v = np.zeros(0, dtype=np.int64)
        tt = ll = sp = lns = np.zeros(0)
        hwn = np.zeros(0, dtype=object)
        nms = np.zeros(0, dtype=object)

    links = pd.DataFrame({
        "from_node": u, "to_node": v, "travel_time_s": tt, "length_m": ll,
        "speed_kmh": sp, "highway": hwn, "lanes": lns, "name": nms,
    })
    stats = {"raw_features": int(len(g)), "nodes": int(n), "directed_edges": int(len(links)),
             "total_edge_length_km": float(ll.sum() / 1000.0),
             "build_seconds": round(time.time() - t0, 1)}
    return xy, links, feat, stats


def analyze_components(a, n):
    """同时统计弱连通 / 强连通分量，返回「最大强连通分量」掩码。

    路由与吸附都限定在 giant SCC 内：弱连通并不保证有向可达，实测有 2 个 Subzone
    恰好吸附到单向死胡同节点（indeg=0 或 outdeg=0），会造成 661 个不可达 OD。
    """
    nw, lw = connected_components(a, directed=True, connection="weak")
    sw = np.bincount(lw)
    gcw = int(np.argmax(sw)) if len(sw) else 0
    ns, ls = connected_components(a, directed=True, connection="strong")
    ss = np.bincount(ls)
    gcs = int(np.argmax(ss)) if len(ss) else 0
    stats = {
        "weak_components": int(nw),
        "giant_weak_share": float(sw[gcw] / n) if n else 0.0,
        "other_weak_component_nodes": int(n - sw[gcw]) if n else 0,
        "strong_components": int(ns),
        "giant_strong_nodes": int(ss[gcs]) if len(ss) else 0,
        "giant_strong_share": float(ss[gcs] / n) if n else 0.0,
    }
    return (ls == gcs), stats


# ----------------------------------------------------------------------------- zones
def load_zones(root):
    z = pd.read_csv(root / ZONE_FILE, encoding="utf-8-sig")
    need = {"zone_id", "subzone_code", "subzone_name", "planning_area", "planning_region",
            "centroid_x_svy21_m", "centroid_y_svy21_m"}
    miss = need - set(z.columns)
    if miss:
        raise ValueError(f"zone_dictionary missing {sorted(miss)}")
    if len(z) != 332:
        raise ValueError(f"Expected 332 zones, got {len(z)}")
    return z.sort_values("zone_id").reset_index(drop=True)


def snap(zones, xy, mask, indeg, outdeg):
    gc_idx = np.where(mask)[0]
    tree_gc = cKDTree(xy[gc_idx])
    rows = []
    for _, r in zones.iterrows():
        pt = [float(r.centroid_x_svy21_m), float(r.centroid_y_svy21_m)]
        d, k = tree_gc.query(pt)
        nd = int(gc_idx[int(k)])
        rows.append({"zone_id": int(r.zone_id), "subzone_code": r.subzone_code,
                     "subzone_name": r.subzone_name, "nearest_node": nd,
                     "snap_distance_m": float(d),
                     "node_in_degree": int(indeg[nd]), "node_out_degree": int(outdeg[nd]),
                     "snap_warning": bool(d > SNAP_MAX_M),
                     "no_road_access": bool(d > NO_ROAD_ACCESS_M)})
    return pd.DataFrame(rows)


# ----------------------------------------------------------------------------- impedance
def impedance(a_tt, a_len, zone_ids, snap_nodes, batch=32):
    ids = [int(x) for x in zone_ids]
    src = [int(snap_nodes[z]) for z in ids]
    k = len(ids)
    Dt = np.full((k, k), np.nan)
    Dl = np.full((k, k), np.nan)
    t0 = time.time()
    for s0 in range(0, k, batch):
        s1 = min(s0 + batch, k)
        idx = src[s0:s1]
        dt = dijkstra(a_tt, directed=True, indices=idx)
        dl = dijkstra(a_len, directed=True, indices=idx)
        if dt.ndim == 1:
            dt = dt[None, :]
            dl = dl[None, :]
        for r in range(s1 - s0):
            Dt[s0 + r, :] = dt[r, src]
            Dl[s0 + r, :] = dl[r, src]
        print(f"  {s1}/{k} origins, {time.time() - t0:.1f}s")
    out = []
    for i, oz in enumerate(ids):
        for j, dz in enumerate(ids):
            reach = bool(np.isfinite(Dt[i, j]))
            tts = float(Dt[i, j]) if reach else np.nan
            dms = float(Dl[i, j]) if reach else np.nan
            imp = (dms / 1000.0) / (tts / 3600.0) if reach and tts > 0 else np.nan
            out.append({"origin_zone": oz, "destination_zone": dz,
                        "travel_time_s": tts, "travel_time_min": tts / 60.0 if reach else np.nan,
                        "distance_m": dms, "implied_speed_kmh": imp, "reachable": reach})
    return pd.DataFrame(out)


# ----------------------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--project-root", type=Path, default=DEFAULT_PROJECT_ROOT)
    a = ap.parse_args()
    root = a.project_root
    out = root / OUT_DIR
    out.mkdir(parents=True, exist_ok=True)

    z = load_zones(root)
    osm, src_name = read_osm(root / OSM_FILE)
    print(f"OSM source: {src_name}; raw features: {len(osm):,}")

    xy, links, feat, net = build_graph(osm)
    print(f"nodes={net['nodes']:,}; directed_edges={net['directed_edges']:,}; "
          f"length={net['total_edge_length_km']:,.1f} km")

    a_tt = coo_matrix((links["travel_time_s"].to_numpy(float),
                       (links["from_node"].to_numpy(), links["to_node"].to_numpy())),
                      shape=(net["nodes"], net["nodes"])).tocsr()
    a_len = coo_matrix((links["length_m"].to_numpy(float),
                        (links["from_node"].to_numpy(), links["to_node"].to_numpy())),
                       shape=(net["nodes"], net["nodes"])).tocsr()
    mask, comp = analyze_components(a_tt, net["nodes"])
    indeg = np.bincount(a_tt.indices, minlength=net["nodes"])   # 入度
    outdeg = np.diff(a_tt.indptr)                                # 出度
    print(f"weak comp={comp['weak_components']:,}; strong comp={comp['strong_components']:,}; "
          f"giant SCC share={comp['giant_strong_share']:.4f}")

    links.to_csv(out / "network_links.csv", index=False, encoding="utf-8-sig")

    # ---- persist exact node-id -> coordinate table (Step 5C needs it to
    #      transfer LTA speed-band times onto the same OSM directed edges).
    nodes_df = pd.DataFrame({
        "node_id": np.arange(net["nodes"], dtype=int),
        "x_svy21_m": xy[:, 0],
        "y_svy21_m": xy[:, 1],
    })
    try:
        from pyproj import Transformer
        tr = Transformer.from_crs("EPSG:3414", "EPSG:4326", always_xy=True)
        lon, lat = tr.transform(xy[:, 0], xy[:, 1])
        nodes_df["lon"] = lon
        nodes_df["lat"] = lat
    except Exception as exc:      # lon/lat are a convenience only
        print(f"[WARN] skip node lon/lat: {exc}")
    nodes_df.to_csv(out / "network_nodes.csv", index=False, encoding="utf-8-sig")
    print(f"nodes table written: {len(nodes_df):,} rows -> network_nodes.csv")

    sdf = snap(z, xy, mask, indeg, outdeg)
    sdf.to_csv(out / "zone_network_snap.csv", index=False, encoding="utf-8-sig")
    print(f"snap median={sdf.snap_distance_m.median():.1f} m; "
          f"max={sdf.snap_distance_m.max():.1f} m; warnings={int(sdf.snap_warning.sum())}; "
          f"no_road_access={int(sdf.no_road_access.sum())}")

    M = impedance(a_tt, a_len, z["zone_id"], dict(zip(sdf.zone_id, sdf.nearest_node)))
    M.to_parquet(out / "impedance_matrix.parquet", index=False)
    M.to_csv(out / "impedance_matrix.csv", index=False, encoding="utf-8-sig")

    # ---- validation
    reach = M["reachable"].to_numpy()
    valid = M.loc[M.reachable, "travel_time_min"]
    valid_d = M.loc[M.reachable, "distance_m"]
    valid_i = M.loc[M.reachable, "implied_speed_kmh"]
    piv = M.pivot(index="origin_zone", columns="destination_zone", values="travel_time_s").to_numpy(float)
    off = ~np.eye(piv.shape[0], dtype=bool)
    m = np.isfinite(piv) & np.isfinite(piv.T) & off
    asym = float(np.mean(np.abs(piv[m] - piv.T[m]) > 1e-9)) if m.any() else 0.0

    summary = {
        "status": "PASS" if (reach.mean() >= 0.999 and int(sdf.no_road_access.sum()) <= 5) else "WARN",
        "network": {
            "nodes": net["nodes"], "directed_edges": net["directed_edges"],
            "weak_components": comp["weak_components"],
            "strong_components": comp["strong_components"],
            "giant_weak_share": round(comp["giant_weak_share"], 6),
            "giant_strong_share": round(comp["giant_strong_share"], 6),
            "other_weak_component_nodes": comp["other_weak_component_nodes"],
            "total_edge_length_km": round(net["total_edge_length_km"], 1),
        },
        "zones": {
            "count": int(len(z)),
            "snap_max_m": float(sdf.snap_distance_m.max()),
            "snap_p90_m": float(sdf.snap_distance_m.quantile(0.9)),
            "snap_median_m": float(sdf.snap_distance_m.median()),
            "snap_warnings": int(sdf.snap_warning.sum()),
            "zones_without_road_access": int(sdf.no_road_access.sum()),
            "zones_without_road_access_list": sdf.loc[sdf.no_road_access, "subzone_name"].tolist(),
        },
        "impedance": {
            "rows": int(len(M)), "expected": 332 * 332,
            "reachable_rate": float(reach.mean()),
            "unreachable_pairs": int((~reach).sum()),
            "travel_time_min": float(valid.min()),
            "travel_time_median": float(valid.median()),
            "travel_time_mean": float(valid.mean()),
            "travel_time_max": float(valid.max()),
            "distance_median_km": float(valid_d.median() / 1000.0),
            "distance_max_km": float(valid_d.max() / 1000.0),
            "implied_speed_median_kmh": float(valid_i.median()),
            "directed_asymmetry_rate": asym,
            "speed_regime": "free-flow (no congestion); AM-peak feedback via TrafficFlow calibration in a later step",
        },
        "configuration": {
            "crs": "EPSG:3414",
            "speed_rule": "parsable OSM maxspeed else highway default",
            "oneway": "yes=forward, -1=reverse, missing/no=bidirectional",
            "routing": "scipy.sparse.csgraph.dijkstra, single-source, directed",
            "snap_rule": "nearest node within largest STRONGLY connected component",
            "matrix_symmetry": "NOT enforced",
        },
    }
    json.dump(summary, open(out / "impedance_validation.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)

    # ---- network audit
    rows = []
    for h in ORDER:
        f = feat[h]
        if f["features"] == 0:
            continue
        rows.append({
            "highway": h, "features": f["features"], "directed_segments": f["segments"],
            "length_km": round(f["length_m"] / 1000.0, 2),
            "oneway_yes": f["oneway_yes"], "oneway_reverse": f["oneway_rev"],
            "oneway_bidirectional": f["oneway_both"],
            "oneway_share": round(f["oneway_yes"] / f["features"], 4),
            "maxspeed_coverage": round(f["maxspeed_osm"] / f["features"], 4),
            "speed_default_share": round(f["maxspeed_default"] / f["features"], 4),
            "lanes_coverage": round(f["lanes_known"] / f["features"], 4),
        })
    audit = pd.DataFrame(rows)
    tot = {
        "highway": "__TOTAL__",
        "features": int(audit.features.sum()),
        "directed_segments": int(audit.directed_segments.sum()),
        "length_km": round(audit.length_km.sum(), 2),
        "oneway_share": round(audit.oneway_yes.sum() / audit.features.sum(), 4),
        "maxspeed_coverage": round((audit.maxspeed_coverage * audit.features).sum() / audit.features.sum(), 4),
        "speed_default_share": round(1 - (audit.maxspeed_coverage * audit.features).sum() / audit.features.sum(), 4),
        "lanes_coverage": round((audit.lanes_coverage * audit.features).sum() / audit.features.sum(), 4),
    }
    audit = pd.concat([audit, pd.DataFrame([tot])], ignore_index=True)
    audit.to_csv(out / "network_audit.csv", index=False, encoding="utf-8-sig")
    json.dump({"source": src_name, "rows": rows, "total": tot},
              open(out / "network_audit.json", "w", encoding="utf-8"), ensure_ascii=False, indent=2)

    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
