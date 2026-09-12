#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Step 5C.1  AM-peak speed coverage enhancement
=============================================
把 LTA TrafficSpeedBands 的 AM 速度，按「三级置信度」转移到 OSM 有向边，
扩大 AM 速度覆盖，再重算 332x332 AM-peak 阻抗矩阵。

三级传播（只有高置信度才传播，逐边记录 tier）
------------------------------------------------
  tier "geom"    几何匹配：LTA Link 质心 -> 最近 OSM 边（<= geom_max_m），
                 道路名一致时优先。最高置信度，速度取该边匹配 LTA 速度中位数。
  tier "name+hw" 同名 + 相近 highway：未被几何命中的边，若其路名属于
                 「有足够 LTA 证据的路名」，且其 highway 组与该路名已几何命中的
                 highway 组一致 -> 采用该路名的 LTA AM 速度中位数。
  tier "name"    仅同名：同上但 highway 组不一致，采用路名速度（记录为较低置信度）。
  tier "none"    未传播，保留 Step 4 free-flow 速度。

规则要点
--------
* 时间窗口：工作日 07:00-09:59（按文件名时间戳；快照 5 分钟一档）。
* SpeedBand=8 的 MaximumSpeed=999 是开放区间哨兵值，不是 999 km/h -> 用 75 km/h 代理。
* 不使用 TrafficFlow 流量反推速度。
* 速度下限 5 km/h；AM 速度不高于 free-flow 的 1.5 倍（软护栏，超限裁剪并计数）。

输入
----
  reports/od_impedance/network_links.csv        (Step 4，含 name/lanes/highway)
  reports/od_impedance/network_nodes.csv        (Step 4 节点坐标，5C.1 正式输入)
  reports/od_impedance/zone_network_snap.csv
  reports/od_zone/zone_dictionary.csv
  Dynamic_2026_03_16/historical_data/TrafficSpeedBands_Links.shp     (143,787 LTA 路段)
  Dynamic_2026_03_16/realtime_monitoring/TrafficSpeedBands_*.json    (按文件名预筛 AM)

输出 reports/od_impedance_ampeak_v2/
    lta_speedbands_ampeak.csv       LTA Link 级 AM 速度
    lta_name_speed_v2.csv           路名级 AM 速度聚合（供同名传播）
    lta_osm_match_v2.csv            tier-1 几何匹配明细
    osm_link_ampeak_speed_v2.csv    OSM 边级 AM 速度 + assignment_tier
    ampeak_v2_speed_by_tier.csv     按 tier 的边数/长度汇总
    ampeak_impedance_v2.parquet     332x332 AM 阻抗
    ampeak_impedance_v2.csv
    ampeak_v2_validation.json       校验汇总
"""
from __future__ import annotations
import argparse, json, math, re
from datetime import datetime
from pathlib import Path
import geopandas as gpd
import numpy as np
import pandas as pd
from scipy import sparse
from scipy.sparse.csgraph import dijkstra
from scipy.spatial import cKDTree

ROOT_DEFAULT = Path(r"D:\Luan\2026-05\2_Singapore")
SPEED_DIR = Path("Dynamic_2026_03_16/realtime_monitoring")
LTA_LINKS_CANDIDATES = [
    Path("Dynamic_2026_03_16/historical_data/TrafficSpeedBands_Links.shp"),
    Path("Singapore_OD_MATSim_FinalData/08_TrafficCount/TrafficSpeedBands_Links.shp"),
]
NETWORK = Path("reports/od_impedance/network_links.csv")
NODES = Path("reports/od_impedance/network_nodes.csv")
SNAP = Path("reports/od_impedance/zone_network_snap.csv")
ZONES = Path("reports/od_zone/zone_dictionary.csv")
OUT = Path("reports/od_impedance_ampeak_v2")

AM_HOURS = {7, 8, 9}
BAND8_SPEED = 75.0          # >=70 km/h 开放档的代理速度（假设，非观测）
GEOM_MAX_M = 100.0          # tier-1 几何匹配半径
K = 8                       # KDTree 候选数
NAME_MIN_LTA_LINKS = 3      # 一条路名至少要有这么多 LTA 路段才用于同名传播
SPEED_FLOOR = 5.0           # AM 速度下限
AM_OVER_FF = 1.5            # AM 不超过 free-flow 的该倍数


# ----------------------------------------------------------------- helpers
def norm(x):
    if x is None or (isinstance(x, float) and math.isnan(x)):
        return ""
    return re.sub(r"\s+", " ", str(x).strip()).upper()


def road_name(x):
    """路名归一化：大写、标点/连字符转空格、常见后缀缩写。两侧一致。"""
    s = norm(x)
    s = re.sub(r"[^A-Z0-9]+", " ", s)
    repl = {"AVENUE": "AVE", "STREET": "ST", "ROAD": "RD", "JUNCTION": "JCT",
            "EXPRESSWAY": "EXPY", "HIGHWAY": "HWY", "CRESCENT": "CRES",
            "BOULEVARD": "BLVD", "DRIVE": "DR"}
    for a, b in repl.items():
        s = re.sub(rf"\b{a}\b", b, s)
    return re.sub(r"\s+", " ", s).strip()


def hw_group(h):
    h = str(h).lower()
    if "motorway" in h or "trunk" in h:
        return "expressway"
    if "primary" in h or "secondary" in h:
        return "arterial"
    if "tertiary" in h or "residential" in h or "service" in h or "unclassified" in h:
        return "local"
    return "other"


def parse_ts(name):
    m = re.search(r"TrafficSpeedBands_(\d{8})_(\d{6})\.json$", name)
    if not m:
        return None
    try:
        return datetime.strptime(m.group(1) + m.group(2), "%Y%m%d%H%M%S")
    except ValueError:
        return None


def records_of(obj):
    if isinstance(obj, dict):
        for k in ("Value", "value", "d"):
            if k in obj:
                return obj[k]
        return []
    return obj


def speed_value(rec):
    """把一条 SpeedBand 记录换算为 km/h。SpeedBand=8 / max=999 为开放档哨兵。"""
    try:
        band = int(float(str(rec.get("SpeedBand", rec.get("speedBand", "")))))
    except Exception:
        band = None
    try:
        lo = float(str(rec.get("MinimumSpeed", rec.get("minimumSpeed", ""))).replace(",", ""))
    except Exception:
        lo = np.nan
    try:
        hi = float(str(rec.get("MaximumSpeed", rec.get("maximumSpeed", ""))).replace(",", ""))
    except Exception:
        hi = np.nan
    if band == 8 and (not np.isfinite(hi) or hi > 200 or hi == 999):
        return BAND8_SPEED
    if np.isfinite(lo) and np.isfinite(hi) and 0 < hi <= 200 and hi >= lo:
        return (lo + hi) / 2
    defaults = {1: (5, 9), 2: (10, 19), 3: (20, 29), 4: (30, 39),
                5: (40, 49), 6: (50, 59), 7: (60, 69)}
    if band in defaults:
        a, b = defaults[band]
        return (a + b) / 2
    return np.nan


# ----------------------------------------------------------------- loaders
def load_speedbands(root):
    files = []
    for p in sorted((root / SPEED_DIR).glob("TrafficSpeedBands_*.json")):
        dt = parse_ts(p.name)
        if dt and dt.weekday() < 5 and dt.hour in AM_HOURS:
            files.append((p, dt))
    if not files:
        raise FileNotFoundError("没有工作日 07:00-10:00 SpeedBands 快照")
    lid, sp, ts = [], [], []
    for p, dt in files:
        with p.open("r", encoding="utf-8") as f:
            recs = records_of(json.load(f))
        iso = dt.isoformat()
        for r in recs:
            lk = r.get("LinkID")
            if lk is None:
                lk = r.get("linkId")
            if lk is None:
                continue
            v = speed_value(r)
            if not np.isfinite(v):
                continue
            lid.append(str(lk).strip())
            sp.append(float(v))
            ts.append(iso)
    obs = pd.DataFrame({"LinkID": lid, "speed_kmh": sp, "timestamp": ts})
    agg = obs.groupby("LinkID", as_index=False).agg(
        am_speed_kmh=("speed_kmh", "median"),
        n_observations=("speed_kmh", "size"),
        speed_min=("speed_kmh", "min"),
        speed_max=("speed_kmh", "max"),
    )
    return agg, obs, files


def load_lta(root):
    path = next((root / p for p in LTA_LINKS_CANDIDATES if (root / p).exists()), None)
    if path is None:
        raise FileNotFoundError(f"没有 LTA link 几何文件: {LTA_LINKS_CANDIDATES}")
    g = gpd.read_file(path, columns=["LinkID", "RoadName", "geometry"])
    if g.crs is None:
        g = g.set_crs("EPSG:4326")
    g["LinkID"] = g["LinkID"].astype(str).str.strip()
    g = g.drop_duplicates("LinkID")
    g["name_norm"] = g["RoadName"].map(road_name)
    return g.to_crs("EPSG:3414"), str(path)


def load_network(root):
    e = pd.read_csv(root / NETWORK, encoding="utf-8-sig")
    n = pd.read_csv(root / NODES, encoding="utf-8-sig")
    if "name" not in e.columns:
        raise ValueError(
            "network_links.csv 缺少 name 列：先用改造后的 Step 4 重新生成"
            "（build_impedance.py 已导出 name/lanes）。"
        )
    e["from_node"] = pd.to_numeric(e["from_node"]).astype(int)
    e["to_node"] = pd.to_numeric(e["to_node"]).astype(int)
    n["node_id"] = pd.to_numeric(n["node_id"]).astype(int)
    e = e.merge(n.rename(columns={"node_id": "from_node",
                                  "x_svy21_m": "from_x", "y_svy21_m": "from_y"}),
                on="from_node", how="left")
    e = e.merge(n.rename(columns={"node_id": "to_node",
                                  "x_svy21_m": "to_x", "y_svy21_m": "to_y"}),
                on="to_node", how="left")
    if e[["from_x", "from_y", "to_x", "to_y"]].isna().any().any():
        raise ValueError("network_links 存在缺少节点坐标的边")
    e = e.reset_index(drop=True)
    e["mid_x"] = (e.from_x + e.to_x) / 2
    e["mid_y"] = (e.from_y + e.to_y) / 2
    e["name_norm"] = e["name"].map(road_name)
    e["hw_group"] = e["highway"].map(hw_group)
    return e


# ----------------------------------------------------------------- tier 1: geometry
def match_geometry(speed, lta, e):
    x = lta.merge(speed[["LinkID", "am_speed_kmh"]], on="LinkID", how="inner").drop_duplicates("LinkID")
    tree = cKDTree(e[["mid_x", "mid_y"]].to_numpy(float))
    xy = np.c_[x.geometry.centroid.x.to_numpy(float), x.geometry.centroid.y.to_numpy(float)]
    d, ix = tree.query(xy, k=K)
    if d.ndim == 1:
        d = d[:, None]
        ix = ix[:, None]
    e_names = e["name_norm"].to_numpy()
    lids = x["LinkID"].to_numpy()
    lnames = x["name_norm"].to_numpy()
    lspd = x["am_speed_kmh"].to_numpy(float)
    kk = d.shape[1]
    rows = []
    for i in range(len(x)):
        lname = lnames[i]
        di = d[i]
        xi = ix[i]
        best = None
        for k in range(kk):
            dm = di[k]
            if dm > GEOM_MAX_M:
                continue
            ei = int(xi[k])
            en = e_names[ei]
            nm = bool(lname and en and (lname == en or lname in en or en in lname))
            score = dm - (25.0 if nm else 0.0)
            if best is None or score < best[0]:
                best = (score, ei, dm, nm)
        if best:
            rows.append((lids[i], best[1], best[2], bool(best[3]), lspd[i],
                         "geom+name" if best[3] else "geom"))
    return pd.DataFrame(rows, columns=["LinkID", "osm_edge_index", "distance_m",
                                       "name_match", "am_speed_kmh", "match_method"])


# ----------------------------------------------------------------- tier 2/3: name
def lta_name_speed(speed, lta):
    x = lta[["LinkID", "name_norm"]].merge(speed[["LinkID", "am_speed_kmh"]],
                                           on="LinkID", how="inner")
    x = x[x.name_norm.ne("")]
    g = x.groupby("name_norm", as_index=False).agg(
        lta_name_speed_kmh=("am_speed_kmh", "median"),
        n_lta_links=("LinkID", "size"),
    )
    return g


def assign_speeds(e, geom_m):
    """返回 e（含 am_speed_kmh / assignment_tier / am_over_ff_clipped）与 tier 汇总。"""
    e = e.copy()
    e["free_flow_speed_kmh"] = e["speed_kmh"].astype(float)
    e["am_speed_kmh"] = e["free_flow_speed_kmh"]
    e["assignment_tier"] = "none"

    # --- tier 1
    if not geom_m.empty:
        s1 = geom_m.groupby("osm_edge_index").am_speed_kmh.median()
        idx1 = s1.index.astype(int).to_numpy()
        e.loc[idx1, "am_speed_kmh"] = s1.to_numpy(float)
        e.loc[idx1, "assignment_tier"] = "geom"

    # 路名 -> 已几何命中边所属 highway 组
    t1 = e[e.assignment_tier == "geom"]
    name_hwg = {n: set(s) for n, s in t1.groupby("name_norm").hw_group.agg(set).items() if n}

    # --- tier 2/3
    spd = e["name_norm"].map(dict(zip(lta_name_speed_df.name_norm, lta_name_speed_df.lta_name_speed_kmh)))
    cnt = e["name_norm"].map(dict(zip(lta_name_speed_df.name_norm, lta_name_speed_df.n_lta_links)))
    eligible = (e.assignment_tier == "none") & e.name_norm.ne("") & spd.notna() & (cnt.fillna(0) >= NAME_MIN_LTA_LINKS)
    if eligible.any():
        sub = e.loc[eligible, ["name_norm", "hw_group"]]
        hw_ok = np.array([bool(name_hwg.get(n)) and (g in name_hwg[n])
                          for n, g in zip(sub.name_norm, sub.hw_group)])
        t2_idx = sub.index[hw_ok]
        t3_idx = sub.index[~hw_ok]
        e.loc[t2_idx, "am_speed_kmh"] = spd.loc[t2_idx]
        e.loc[t2_idx, "assignment_tier"] = "name+hw"
        e.loc[t3_idx, "am_speed_kmh"] = spd.loc[t3_idx]
        e.loc[t3_idx, "assignment_tier"] = "name"

    # --- 软护栏：AM 不超过 free-flow 的 AM_OVER_FF 倍；速度下限
    clipped = e.am_speed_kmh > (e.free_flow_speed_kmh * AM_OVER_FF)
    e.loc[clipped, "am_speed_kmh"] = e.loc[clipped, "free_flow_speed_kmh"] * AM_OVER_FF
    e["am_over_ff_clipped"] = clipped
    e["am_speed_kmh"] = e["am_speed_kmh"].clip(lower=SPEED_FLOOR)
    return e


# ----------------------------------------------------------------- impedance
def recompute(root, e, zones):
    e = e.copy()
    e["am_travel_time_s"] = e["length_m"] / (e["am_speed_kmh"] * 1000.0 / 3600.0)
    n = max(int(e.from_node.max()), int(e.to_node.max())) + 1
    graph = sparse.csr_matrix(
        (e.am_travel_time_s.to_numpy(float), (e.from_node.to_numpy(int), e.to_node.to_numpy(int))),
        shape=(n, n))
    snap = pd.read_csv(root / SNAP, encoding="utf-8-sig")
    snap["zone_id"] = pd.to_numeric(snap["zone_id"]).astype(int)
    ids = zones["zone_id"].astype(int).sort_values().tolist()
    nodes = snap.set_index("zone_id").loc[ids]["nearest_node"].astype(int).to_numpy()
    dist = dijkstra(graph, directed=True, indices=nodes, return_predecessors=False)
    m = dist[:, nodes]
    rows = []
    for i, oi in enumerate(ids):
        for j, oj in enumerate(ids):
            v = float(m[i, j])
            rows.append({"origin_zone": oi, "destination_zone": oj,
                         "travel_time_s": v, "travel_time_min": v / 60,
                         "reachable": bool(np.isfinite(v))})
    return e, pd.DataFrame(rows)


lta_name_speed_df = None  # set in main


def main():
    global BAND8_SPEED, GEOM_MAX_M, lta_name_speed_df, NAME_MIN_LTA_LINKS
    ap = argparse.ArgumentParser()
    ap.add_argument("--project-root", type=Path, default=ROOT_DEFAULT)
    ap.add_argument("--band8-speed", type=float, default=BAND8_SPEED)
    ap.add_argument("--geom-max-m", type=float, default=GEOM_MAX_M)
    ap.add_argument("--name-min-links", type=int, default=NAME_MIN_LTA_LINKS)
    a = ap.parse_args()
    root = a.project_root
    out = root / OUT
    out.mkdir(parents=True, exist_ok=True)
    BAND8_SPEED = a.band8_speed
    GEOM_MAX_M = a.geom_max_m
    NAME_MIN_LTA_LINKS = a.name_min_links

    print("[1/6] Load AM SpeedBands ...")
    speed, obs, files = load_speedbands(root)
    speed.to_csv(out / "lta_speedbands_ampeak.csv", index=False, encoding="utf-8-sig")
    print(f"      snapshots={len(files)} obs={len(obs):,} lta_links={speed.LinkID.nunique():,}")

    print("[2/6] Load LTA geometry + Step-4 network ...")
    lta, lta_src = load_lta(root)
    e = load_network(root)
    print(f"      lta={len(lta):,} ({lta_src}) osm_edges={len(e):,} named={e.name_norm.ne('').mean():.1%}")

    print("[3/6] Tier-1 geometry match ...")
    geom_m = match_geometry(speed, lta, e)
    if geom_m.empty:
        raise ValueError("没有 LTA->OSM 几何匹配")
    geom_m.to_csv(out / "lta_osm_match_v2.csv", index=False, encoding="utf-8-sig")
    print(f"      matched LTA links={geom_m.LinkID.nunique():,} OSM edges={geom_m.osm_edge_index.nunique():,}")

    print("[4/6] Assign speed by 3-tier confidence ...")
    lta_name_speed_df = lta_name_speed(speed, lta)
    lta_name_speed_df.to_csv(out / "lta_name_speed_v2.csv", index=False, encoding="utf-8-sig")
    updated = assign_speeds(e, geom_m)
    updated.to_csv(out / "osm_link_ampeak_speed_v2.csv", index=False, encoding="utf-8-sig")

    print("[5/6] Recompute 332x332 AM impedance ...")
    updated, matrix = recompute(root, updated, pd.read_csv(root / ZONES, encoding="utf-8-sig"))
    matrix.to_parquet(out / "ampeak_impedance_v2.parquet", index=False)
    matrix.to_csv(out / "ampeak_impedance_v2.csv", index=False, encoding="utf-8-sig")

    print("[6/6] Validate ...")
    total_len = float(updated.length_m.sum())
    tier_rows = []
    for t in ["geom", "name+hw", "name", "none"]:
        s = updated[updated.assignment_tier == t]
        tier_rows.append({"tier": t, "edges": int(len(s)),
                          "length_km": float(s.length_m.sum() / 1000.0),
                          "length_share": float(s.length_m.sum() / total_len) if total_len else 0.0})
    tiers = pd.DataFrame(tier_rows)
    tiers.to_csv(out / "ampeak_v2_speed_by_tier.csv", index=False, encoding="utf-8-sig")
    cov = tiers[tiers.tier != "none"]
    coverage_len_share = float(cov.length_share.sum())
    coverage_edge_share = float(cov.edges.sum()) / len(updated)

    finite = matrix[matrix.reachable]
    summary = {
        "status": "PASS" if len(matrix) == 332 * 332 and matrix.reachable.all() else "WARN",
        "am_snapshot_files": len(files),
        "am_snapshot_observations": int(len(obs)),
        "am_lta_links": int(speed.LinkID.nunique()),
        "lta_geometry_source": lta_src,
        "matched_lta_links": int(geom_m.LinkID.nunique()),
        "matched_osm_edges_geom": int(geom_m.osm_edge_index.nunique()),
        "total_osm_edges": int(len(updated)),
        "total_length_km": float(total_len / 1000.0),
        "tier_breakdown": {r.tier: {"edges": int(r.edges), "length_km": round(float(r.length_km), 3),
                                    "length_share": round(float(r.length_share), 4)} for r in tiers.itertuples()},
        "am_coverage_length_share": coverage_len_share,
        "am_coverage_edge_share": coverage_edge_share,
        "name_match_rate_geom": float(geom_m.name_match.mean()),
        "name_propagation_names": int(lta_name_speed_df.name_norm.nunique()),
        "am_speed_median_kmh": float(updated.am_speed_kmh.median()),
        "am_speed_max_kmh": float(updated.am_speed_kmh.max()),
        "edges_over_130_kmh": int((updated.am_speed_kmh > 130).sum()),
        "am_over_ff_clipped_edges": int(updated.am_over_ff_clipped.sum()),
        "am_tt_median_min": float(finite.travel_time_min.median()),
        "am_tt_mean_min": float(finite.travel_time_min.mean()),
        "am_tt_max_min": float(finite.travel_time_min.max()),
        "reachable_rate": float(matrix.reachable.mean()),
        "band8_speed_proxy_kmh": BAND8_SPEED,
        "geom_max_m": GEOM_MAX_M,
        "name_min_lta_links": NAME_MIN_LTA_LINKS,
        "am_over_ff_cap": AM_OVER_FF,
        "time_window": "weekday 07:00-09:59",
    }
    with open(out / "ampeak_v2_validation.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    print("=" * 72)
    print("Step 5C.1 PASS/WARN:", summary["status"])
    print("AM coverage (length share): %.4f  (edge share %.4f)" % (coverage_len_share, coverage_edge_share))
    print(tiers.to_string(index=False))
    print("AM median speed (km/h):", summary["am_speed_median_kmh"])
    print("AM median TT (min):", summary["am_tt_median_min"],
          "| mean:", round(summary["am_tt_mean_min"], 3), "| max:", round(summary["am_tt_max_min"], 3))
    print("Reachable:", summary["reachable_rate"])
    print("Output:", out)


if __name__ == "__main__":
    main()
