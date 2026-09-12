#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Singapore OD -> MATSim
Step 5C: AM-peak impedance from historical LTA TrafficSpeedBands.

Purpose:
    Build an AM-peak road-speed layer from historical LTA TrafficSpeedBands,
    then transfer it to the OSM directed network used in Step 4 and recompute
    a 332x332 shortest travel-time matrix.

Why this is separate from TrafficFlow:
    TrafficSpeedBands directly contains speed ranges for LTA links, while
    TrafficFlow contains volume. Therefore no volume/capacity assumption is
    needed here.

Input:
    Dynamic_2026_03_16/realtime_monitoring/TrafficSpeedBands_YYYYMMDD_HHMMSS.json
        (weekday 07:00-09:59 snapshots; the ONLY true AM-peak observations)
    Dynamic_2026_03_16/historical_data/TrafficSpeedBands_v4.json
        (undated single snapshot, used only as a fallback)
    Dynamic_2026_03_16/historical_data/TrafficSpeedBands_Links.shp
        (LTA speed-band link geometry: 143,787 links)
    reports/od_impedance/network_links.csv
    reports/od_impedance/network_nodes.csv   (node id -> SVY21 XY; from Step 4)
    reports/od_impedance/zone_network_snap.csv
    reports/od_zone/zone_dictionary.csv

Outputs:
    reports/od_impedance_ampeak/
        lta_speedbands_ampeak.csv
        lta_speedbands_coverage.json
        lta_osm_ampeak_speed_match.csv
        osm_link_ampeak_speed.csv
        ampeak_impedance_matrix.parquet
        ampeak_impedance_matrix.csv
        ampeak_comparison.csv          free-flow (Step 4) vs AM peak
        ampeak_network_validation.json

Method:
    1. Parse all historical speed-band observations.
    2. Select weekday AM peak 07:00–10:00 observations.
    3. For each LTA LinkID, convert the speed band to midpoint speed:
         speed = (MinimumSpeed + MaximumSpeed) / 2
       and for band 8 use a configurable lower-bound + cap.
    4. Aggregate repeated observations by median.
    5. Match each LTA link geometry to the OSM directed network by spatial
       proximity. Direction is inferred from LTA start/end coordinates and
       OSM edge geometry/name where possible.
    6. For matched OSM edges use the LTA AM speed; unmatched edges retain
       Step-4 static speed.
    7. Recompute the shortest directed 332x332 travel-time matrix.
    8. Do NOT alter TrafficFlow or perform OD calibration here.

Important:
    SpeedBand 8 is "70 or more". It has no upper bound. The default proxy is
    75 km/h, configurable with --band8-speed.
"""

from __future__ import annotations

import argparse
import json
import math
import re
from datetime import datetime
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
from scipy import sparse
from scipy.sparse.csgraph import dijkstra
from scipy.spatial import cKDTree


ROOT_DEFAULT = Path(r"D:\Luan\2026-05\2_Singapore")

# Historical speed-band snapshots live in three folders; the ONLY weekday
# 07:00-09:59 observations are in realtime_monitoring/.
SPEED_DIRS = [
    Path("Dynamic_2026_03_16/realtime_monitoring"),
    Path("Dynamic_2026_03_16/historical_data"),
]
SPEED_PRIMARY = "TrafficSpeedBands_v4.json"
SPEED_GLOB = "TrafficSpeedBands_*.json"

# LTA speed-band link geometry = 143,787 links, exactly the SpeedBand link set.
# Do NOT use 08_TrafficCount/TrafficFlow_Links.shp here: that file only holds the
# ~1,278 traffic-count sites, which would cap matching coverage below 1%.
LTA_LINKS_CANDIDATES = [
    Path("Dynamic_2026_03_16/historical_data/TrafficSpeedBands_Links.shp"),
    Path("Singapore_OD_MATSim_FinalData/08_TrafficCount/TrafficFlow_Links.shp"),
]

NETWORK = Path("reports/od_impedance/network_links.csv")
NODES = Path("reports/od_impedance/network_nodes.csv")
SNAP = Path("reports/od_impedance/zone_network_snap.csv")
ZONES = Path("reports/od_zone/zone_dictionary.csv")

OUT = Path("reports/od_impedance_ampeak")

AM_START = 7
AM_END = 10
BAND8_DEFAULT = 75.0
LTA_MATCH_MAX_M = 80.0
LTA_MATCH_CANDIDATES = 8

# LTA documentation: 8 speed bands:
# 1: <10, 2: 10-19, ..., 7: 60-69, 8: >=70.
# Data often contain explicit Min/MaxSpeed.
BAND_DEFAULTS = {
    1: (5.0, 9.0),
    2: (10.0, 19.0),
    3: (20.0, 29.0),
    4: (30.0, 39.0),
    5: (40.0, 49.0),
    6: (50.0, 59.0),
    7: (60.0, 69.0),
}


def norm(x):
    if x is None or (isinstance(x, float) and math.isnan(x)):
        return ""
    return re.sub(r"\s+", " ", str(x).strip())


def tofloat(x):
    """Scalar float parse. Avoids pd.to_numeric(pd.Series([x])) per record,
    which created ~7M throwaway Series over the 12 AM snapshots."""
    try:
        return float(str(x).replace(",", ""))
    except Exception:
        return float("nan")


def parse_datetime_from_filename(name: str):
    m = re.search(r"TrafficSpeedBands_(\d{8})_(\d{6})\.json$", name)
    if not m:
        return None
    try:
        return datetime.strptime(
            m.group(1) + m.group(2), "%Y%m%d%H%M%S"
        )
    except ValueError:
        return None


def load_json_records(path: Path):
    with path.open("r", encoding="utf-8") as f:
        obj = json.load(f)

    # LTA downloaded files have appeared in both direct-list and
    # {"Value": [...]}/{"value": [...]} wrappers.
    if isinstance(obj, list):
        return obj
    if isinstance(obj, dict):
        for key in ("Value", "value", "d"):
            if key in obj and isinstance(obj[key], list):
                return obj[key]
    raise ValueError(f"无法识别 JSON 结构: {path}")


def pick(records, *names):
    if not records:
        return None
    keys = {str(k).lower(): k for k in records[0].keys()}
    for name in names:
        if name.lower() in keys:
            return keys[name.lower()]
    # tolerant prefix
    for name in names:
        for lk, actual in keys.items():
            if lk.startswith(name.lower()):
                return actual
    return None


# LTA encodes the open-ended top band (SpeedBand 8 = ">=70 km/h") as
# MinimumSpeed=70, MaximumSpeed=999. That 999 is a SENTINEL, not 999 km/h:
# taking the midpoint would give (70+999)/2 = 534.5 km/h and turn every
# expressway into a near-free link, badly understating AM-peak congestion.
BAND8_MAX_SENTINEL = 999.0


def speed_from_record(rec, band8_speed):
    band_raw = (
        rec.get("SpeedBand")
        if "SpeedBand" in rec
        else rec.get("speedBand")
    )
    try:
        band = int(float(str(band_raw)))
    except Exception:
        band = None

    vmin = tofloat(
        rec.get("MinimumSpeed")
        if "MinimumSpeed" in rec
        else rec.get("minimumSpeed")
    )
    vmax = tofloat(
        rec.get("MaximumSpeed")
        if "MaximumSpeed" in rec
        else rec.get("maximumSpeed")
    )

    # Open-ended top band: always fall back to the configured proxy.
    if np.isfinite(vmax) and vmax >= BAND8_MAX_SENTINEL:
        return float(band8_speed)

    if np.isfinite(vmin) and np.isfinite(vmax) and vmax >= vmin:
        # Explicit closed range is authoritative.
        return float((vmin + vmax) / 2)

    if band == 8:
        return float(band8_speed)

    if band is not None and band in BAND_DEFAULTS:
        lo, hi = BAND_DEFAULTS[band]
        return (lo + hi) / 2.0

    return np.nan


def extract_observation_datetime(rec, fallback):
    for key in (
        "Timestamp", "timestamp", "DateTime", "datetime",
        "Date", "date"
    ):
        if key in rec and norm(rec[key]):
            val = norm(rec[key])
            # Try common ISO / slash formats.
            for fmt in (
                "%Y-%m-%dT%H:%M:%S",
                "%Y-%m-%d %H:%M:%S",
                "%d/%m/%Y %H:%M:%S",
                "%d/%m/%Y",
                "%Y-%m-%d",
            ):
                try:
                    dt = datetime.strptime(val[:19], fmt)
                    return dt
                except Exception:
                    pass
    return fallback


def load_speedbands(root: Path, band8_speed: float):
    files = []
    for d in SPEED_DIRS:
        files.extend(sorted((root / d).glob(SPEED_GLOB)))
    files = sorted(set(files))

    # Select weekday 07:00-09:59 snapshots from the FILENAME FIRST. Reading all
    # ~144 realtime files (tens of MB each) only to discard them is prohibitive.
    dated = []
    for p in files:
        dt = parse_datetime_from_filename(p.name)
        if dt is not None:
            dated.append((dt, p))
    dated.sort(key=lambda t: t[0])

    am_dated = [
        (dt, p) for dt, p in dated
        if dt.weekday() <= 4 and AM_START <= dt.hour <= AM_END - 1
    ]

    using_filename_filter = bool(am_dated)
    if using_filename_filter:
        selected_files = [p for _, p in am_dated]
    else:
        primary = None
        for d in SPEED_DIRS:
            cand = root / d / SPEED_PRIMARY
            if cand.exists():
                primary = cand
                break
        if primary is None:
            raise FileNotFoundError(
                f"没有工作日 07:00-{AM_END - 1:02d}:59 快照，且找不到 {SPEED_PRIMARY}"
            )
        selected_files = [primary]

    rows = []
    raw_records = 0

    for path in selected_files:
        fallback_dt = parse_datetime_from_filename(path.name)

        try:
            records = load_json_records(path)
        except Exception as exc:
            print(f"[WARN] skip {path.name}: {exc}")
            continue

        raw_records += len(records)
        if not records:
            continue

        # Schema is uniform within one snapshot: resolve keys once per file
        # instead of scanning rec.keys() for every record.
        keys = list(records[0].keys())
        link_key = next(
            (k for k in keys if str(k).lower() == "linkid"), None
        )
        road_name_key = next(
            (k for k in keys if str(k).lower() == "roadname"), None
        )
        has_ts_key = any(
            str(k).lower() in ("timestamp", "datetime", "date")
            for k in keys
        )
        if link_key is None:
            continue

        for rec in records:
            link_id = norm(rec.get(link_key))
            if not link_id:
                continue

            speed = speed_from_record(rec, band8_speed)
            if not np.isfinite(speed):
                continue

            dt = (
                extract_observation_datetime(rec, fallback_dt)
                if has_ts_key
                else fallback_dt
            )
            if dt is None:
                # No timestamp: keep only as an undated baseline.
                timestamp_known = False
                weekday = None
                hour = None
            else:
                timestamp_known = True
                weekday = dt.weekday()  # Mon=0
                hour = dt.hour

            rows.append({
                "LinkID": link_id,
                "RoadName": norm(rec.get(road_name_key, ""))
                if road_name_key else "",
                "speed_kmh": speed,
                "timestamp": dt.isoformat() if dt else "",
                "timestamp_known": timestamp_known,
                "weekday": weekday,
                "hour": hour,
                "start_lon": tofloat(
                    rec.get("StartLon", rec.get("startLon", np.nan))
                ),
                "start_lat": tofloat(
                    rec.get("StartLat", rec.get("startLat", np.nan))
                ),
                "end_lon": tofloat(
                    rec.get("EndLon", rec.get("endLon", np.nan))
                ),
                "end_lat": tofloat(
                    rec.get("EndLat", rec.get("endLat", np.nan))
                ),
                "source_file": path.name,
            })

    obs = pd.DataFrame(rows)
    if obs.empty:
        raise ValueError("TrafficSpeedBands 没有可解析记录。")

    # Temporal selection already happened at file level when AM snapshots exist.
    if using_filename_filter:
        am = obs.copy()
        temporal_rule = "weekday 07:00-09:59 (selected by snapshot filename)"
    elif obs["timestamp_known"].any():
        am = obs[
            obs["weekday"].between(0, 4, inclusive="both")
            & obs["hour"].between(AM_START, AM_END - 1, inclusive="both")
        ].copy()
        if am.empty:
            am = obs.copy()
            temporal_rule = "undated single snapshot fallback"
        else:
            temporal_rule = "weekday 07:00-09:59 (from record timestamp)"
    else:
        am = obs.copy()
        temporal_rule = "undated single snapshot fallback"

    # One AM speed per LTA link: median robust to repeated retrievals.
    agg = (
        am.groupby("LinkID", as_index=False)
        .agg(
            am_speed_kmh=("speed_kmh", "median"),
            n_observations=("speed_kmh", "size"),
            am_speed_min=("speed_kmh", "min"),
            am_speed_max=("speed_kmh", "max"),
            road_name=("RoadName", "first"),
            start_lon=("start_lon", "median"),
            start_lat=("start_lat", "median"),
            end_lon=("end_lon", "median"),
            end_lat=("end_lat", "median"),
        )
    )

    coverage = {
        "selected_files": len(selected_files),
        "selected_file_names": [p.name for p in selected_files],
        "selected_observations": int(len(am)),
        "raw_records_read": int(raw_records),
        "unique_lta_links": int(agg.LinkID.nunique()),
        "temporal_rule": temporal_rule,
        "filename_filter_applied": using_filename_filter,
    }

    return agg, obs, coverage


def load_lta_link_geometry(root):
    path = next(
        (root / p for p in LTA_LINKS_CANDIDATES if (root / p).exists()),
        None,
    )
    if path is None:
        raise FileNotFoundError(
            f"没有 LTA link 几何文件: {LTA_LINKS_CANDIDATES}"
        )

    g = gpd.read_file(
        path,
        columns=[
            "LinkID", "RoadName",
            "StartLon", "StartLat",
            "EndLon", "EndLat",
            "geometry",
        ],
    )
    if g.crs is None:
        g = g.set_crs("EPSG:4326")
    else:
        g = g.to_crs("EPSG:4326")

    g["LinkID"] = g["LinkID"].astype(str).str.strip()

    # Use WGS84 source coordinates for direction / geometry matching.
    return g


def load_step4_network(root):
    p = root / NETWORK
    if not p.exists():
        raise FileNotFoundError(p)

    n = pd.read_csv(p, encoding="utf-8-sig")
    required = {
        "from_node", "to_node",
        "length_m", "travel_time_s",
        "speed_kmh", "highway",
    }
    miss = required - set(n.columns)
    if miss:
        raise ValueError(
            f"network_links.csv 缺少字段: {sorted(miss)}"
        )
    return n


def match_lta_to_osm(
    root,
    lta_speed,
    network_links,
    max_distance_m,
):
    """
    The Step-4 network_links table has nodes but not geometry.
    We therefore use the TrafficFlow_Links geometry as an independent LTA
    geometry and assign LTA speeds to OSM directed edges through the existing
    Step-0 / Step-4 LTA geometry relationship.

    A direct edge geometry is reconstructed from node coordinates only if
    node coordinate columns are available. Otherwise, fall back to road-name
    allocation at LTA-link level using nearest-node coordinates.
    """
    lta = load_lta_link_geometry(root).to_crs("EPSG:3414")

    # Only keep speed records that have matching geometry.
    x = lta.merge(
        lta_speed,
        on="LinkID",
        how="inner",
        suffixes=("_geom", "_speed"),
    )

    if x.empty:
        raise ValueError(
            "TrafficSpeedBands 与 TrafficFlow_Links 没有共同 LinkID。"
        )

    # Build OSM node coordinate table from zone snap is not sufficient.
    # network_links itself may not carry node XY, so discover them from
    # osm-lines Expanded directly through the Step-4 network construction
    # schema if available. To keep this step robust, use the Step-4 edge
    # endpoints from a generated node table when present.
    node_path = root / NODES

    if not node_path.exists():
        raise FileNotFoundError(
            "缺少 reports/od_impedance/network_nodes.csv。\n"
            "Step 4 (build_impedance.py) 需要先补充保存节点坐标，"
            "才能进行精确的 LTA speed → OSM edge 匹配。"
        )

    nodes = pd.read_csv(node_path, encoding="utf-8-sig")
    required = {"node_id", "x_svy21_m", "y_svy21_m"}
    miss = required - set(nodes.columns)
    if miss:
        raise ValueError(
            f"network_nodes.csv 缺少字段: {sorted(miss)}"
        )

    nodes["node_id"] = pd.to_numeric(nodes["node_id"]).astype(int)

    e = network_links.copy()
    e["from_node"] = pd.to_numeric(e["from_node"]).astype(int)
    e["to_node"] = pd.to_numeric(e["to_node"]).astype(int)

    e = e.merge(
        nodes.rename(
            columns={
                "node_id": "from_node",
                "x_svy21_m": "from_x",
                "y_svy21_m": "from_y",
            }
        ),
        on="from_node",
        how="left",
    ).merge(
        nodes.rename(
            columns={
                "node_id": "to_node",
                "x_svy21_m": "to_x",
                "y_svy21_m": "to_y",
            }
        ),
        on="to_node",
        how="left",
    )

    if e[["from_x", "from_y", "to_x", "to_y"]].isna().any().any():
        raise ValueError("network_links 中存在无法恢复端点坐标的节点。")

    e = e.reset_index(drop=True)

    # ---- vectorised LTA-link -> OSM-edge matching -------------------------
    # A per-row Python loop over 143,787 LTA links x 8 candidates with pandas
    # .iloc + shapely scalar access is far too slow; do it with numpy.
    e["mid_x"] = (e.from_x + e.to_x) / 2
    e["mid_y"] = (e.from_y + e.to_y) / 2
    tree = cKDTree(e[["mid_x", "mid_y"]].to_numpy(float))

    x = x.reset_index(drop=True)
    cent = x.geometry.centroid
    lta_xy = np.column_stack([cent.x.to_numpy(), cent.y.to_numpy()])

    d, idxs = tree.query(lta_xy, k=LTA_MATCH_CANDIDATES)
    if np.ndim(d) == 1:
        d = d[:, None]
        idxs = idxs[:, None]

    # LTA endpoints straight from geometry (SVY21, order preserved).
    lta_p0 = np.asarray([g.coords[0] for g in x.geometry], dtype=float)
    lta_p1 = np.asarray([g.coords[-1] for g in x.geometry], dtype=float)

    osm_from = e[["from_x", "from_y"]].to_numpy(float)[idxs]   # (N, k, 2)
    osm_to = e[["to_x", "to_y"]].to_numpy(float)[idxs]

    l0 = lta_p0[:, None, :]
    l1 = lta_p1[:, None, :]
    forward = (
        np.linalg.norm(l0 - osm_from, axis=2)
        + np.linalg.norm(l1 - osm_to, axis=2)
    )
    reverse = (
        np.linalg.norm(l0 - osm_to, axis=2)
        + np.linalg.norm(l1 - osm_from, axis=2)
    )
    is_forward = forward <= reverse
    direction_penalty = np.minimum(forward, reverse)

    # Candidate score: distance + capped direction endpoint error.
    # (network_links.csv carries no road-name column, so name_match is not
    #  available and is reported as False.)
    score = d + np.minimum(direction_penalty, 5000.0) * 0.01
    score = np.where(d > max_distance_m, np.inf, score)

    best_rank = np.argmin(score, axis=1)
    rows_i = np.arange(len(x))
    best_score = score[rows_i, best_rank]
    ok = np.isfinite(best_score)

    if not ok.any():
        raise ValueError("没有任何 LTA → OSM speed match。")

    m = pd.DataFrame({
        "LinkID": x["LinkID"].to_numpy()[ok],
        "osm_edge_index": idxs[rows_i, best_rank][ok].astype(int),
        "distance_m": d[rows_i, best_rank][ok],
        "direction": np.where(
            is_forward[rows_i, best_rank][ok], "forward", "reverse"
        ),
        "name_match": False,
        "score": best_score[ok],
        "am_speed_kmh": x["am_speed_kmh"].to_numpy(float)[ok],
    })

    return e, m


def recompute_332_impedance(
    root,
    edge_table,
    match_table,
    zones,
):
    # Start from Step-4 network edge speeds.
    e = edge_table.copy()
    e["am_speed_kmh"] = e["speed_kmh"]

    # Multiple LTA links may hit the same OSM edge: use the median speed.
    speed_by_edge = (
        match_table.groupby("osm_edge_index")
        .am_speed_kmh
        .median()
    )
    e.loc[speed_by_edge.index.to_numpy(int), "am_speed_kmh"] = (
        speed_by_edge.to_numpy(float)
    )

    e["am_travel_time_s"] = (
        e["length_m"]
        / (e["am_speed_kmh"] * 1000 / 3600)
    )

    # Need node IDs and graph size.
    max_node = int(
        max(
            e["from_node"].max(),
            e["to_node"].max(),
        )
    )
    n_nodes = max_node + 1

    row = e["from_node"].to_numpy(int)
    col = e["to_node"].to_numpy(int)
    data = e["am_travel_time_s"].to_numpy(float)

    graph = sparse.csr_matrix(
        (data, (row, col)),
        shape=(n_nodes, n_nodes),
    )

    # Step-4 snap result already points each zone to a network node.
    snap = pd.read_csv(
        root / SNAP,
        encoding="utf-8-sig",
    )
    snap["zone_id"] = pd.to_numeric(snap["zone_id"]).astype(int)

    if "nearest_node" in snap.columns:
        snap = snap.rename(columns={"nearest_node": "nearest_network_node"})
    if "nearest_network_node" not in snap.columns:
        raise ValueError(
            "zone_network_snap.csv 缺少 nearest_node / nearest_network_node"
        )

    zone_ids = zones["zone_id"].astype(int).tolist()
    zone_nodes = (
        snap.set_index("zone_id")
        .reindex(zone_ids)["nearest_network_node"]
        .astype(int)
        .to_numpy()
    )

    # one multi-source Dijkstra per origin node.
    distances = dijkstra(
        csgraph=graph,
        directed=True,
        indices=zone_nodes,
        return_predecessors=False,
    )

    matrix = distances[:, zone_nodes]
    matrix_df = pd.DataFrame(
        [
            {
                "origin_zone": int(zone_ids[i]),
                "destination_zone": int(zone_ids[j]),
                "travel_time_s": float(matrix[i, j]),
                "travel_time_min": float(matrix[i, j] / 60.0),
                "reachable": bool(np.isfinite(matrix[i, j])),
            }
            for i in range(len(zone_ids))
            for j in range(len(zone_ids))
        ]
    )

    return e, matrix_df


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--project-root",
        type=Path,
        default=ROOT_DEFAULT,
    )
    parser.add_argument(
        "--band8-speed",
        type=float,
        default=BAND8_DEFAULT,
    )
    parser.add_argument(
        "--max-match-distance",
        type=float,
        default=LTA_MATCH_MAX_M,
    )
    args = parser.parse_args()

    root = args.project_root
    out = root / OUT
    out.mkdir(parents=True, exist_ok=True)

    print("=" * 72)
    print("Step 5C | AM Peak Speed -> 332x332 Impedance")
    print("=" * 72)

    print("[1/5] Parse historical TrafficSpeedBands")
    speed, obs, coverage = load_speedbands(
        root,
        args.band8_speed,
    )
    speed.to_csv(
        out / "lta_speedbands_ampeak.csv",
        index=False,
        encoding="utf-8-sig",
    )
    with open(
        out / "lta_speedbands_coverage.json",
        "w",
        encoding="utf-8",
    ) as f:
        json.dump(
            coverage,
            f,
            ensure_ascii=False,
            indent=2,
        )

    print(
        f"  unique LTA links={len(speed):,}; "
        f"AM observations={coverage['selected_observations']:,}"
    )

    print("[2/5] Load Step-4 network")
    network = load_step4_network(root)
    zones = pd.read_csv(
        root / ZONES,
        encoding="utf-8-sig",
    )

    print("[3/5] Match LTA links -> OSM directed edges")
    edge_base, matches = match_lta_to_osm(
        root,
        speed,
        network,
        args.max_match_distance,
    )
    matches.to_csv(
        out / "lta_osm_ampeak_speed_match.csv",
        index=False,
        encoding="utf-8-sig",
    )

    print(
        f"  matched OSM directed edges={matches.osm_edge_index.nunique():,}; "
        f"LTA links={matches.LinkID.nunique():,}"
    )

    print("[4/5] Recompute directed shortest times")
    updated_edges, matrix = recompute_332_impedance(
        root,
        edge_base,
        matches,
        zones,
    )

    updated_edges.to_csv(
        out / "osm_link_ampeak_speed.csv",
        index=False,
        encoding="utf-8-sig",
    )
    matrix.to_parquet(
        out / "ampeak_impedance_matrix.parquet",
        index=False,
    )
    matrix.to_csv(
        out / "ampeak_impedance_matrix.csv",
        index=False,
        encoding="utf-8-sig",
    )

    # ---- free-flow (Step 4) vs AM peak (Step 5C) comparison
    try:
        base = pd.read_parquet(
            root / "reports/od_impedance/impedance_matrix.parquet"
        )
        cmp = (
            base[["origin_zone", "destination_zone", "travel_time_min"]]
            .rename(columns={"travel_time_min": "freeflow_min"})
            .merge(
                matrix[["origin_zone", "destination_zone",
                        "travel_time_min"]].rename(
                    columns={"travel_time_min": "ampeak_min"}),
                on=["origin_zone", "destination_zone"],
                how="inner",
            )
        )
        cmp["delta_min"] = cmp["ampeak_min"] - cmp["freeflow_min"]
        cmp["ratio"] = cmp["ampeak_min"] / cmp["freeflow_min"].replace(0, np.nan)
        cmp.to_csv(
            out / "ampeak_comparison.csv",
            index=False,
            encoding="utf-8-sig",
        )
        comp = {
            "freeflow_median_min": float(cmp.freeflow_min.median()),
            "ampeak_median_min": float(cmp.ampeak_min.median()),
            "median_delta_min": float(cmp.delta_min.median()),
            "median_slowdown_ratio": float(cmp.ratio.median()),
            "share_pairs_slower": float((cmp.delta_min > 1e-9).mean()),
        }
    except Exception as exc:
        comp = {"error": str(exc)}

    print("[5/5] Validate")
    finite = matrix[matrix["reachable"]]
    snap = pd.read_csv(
        root / SNAP,
        encoding="utf-8-sig",
    )

    summary = {
        "status": (
            "PASS"
            if (
                len(matrix) == 332 * 332
                and matrix["reachable"].all()
                and len(matches) > 0
            )
            else "WARN"
        ),
        "speedbands": coverage,
        "lta_links_speed": int(speed.LinkID.nunique()),
        "lta_osm_matches": int(matches.LinkID.nunique()),
        "osm_edges_with_am_speed": int(matches.osm_edge_index.nunique()),
        "am_speed_median_kmh": float(
            updated_edges["am_speed_kmh"].median()
        ),
        "am_speed_mean_kmh": float(
            updated_edges["am_speed_kmh"].mean()
        ),
        "am_speed_min_kmh": float(
            updated_edges["am_speed_kmh"].min()
        ),
        "am_speed_max_kmh": float(
            updated_edges["am_speed_kmh"].max()
        ),
        "am_speed_edges_above_130_kmh": int(
            (updated_edges["am_speed_kmh"] > 130).sum()
        ),
        "am_matrix_rows": int(len(matrix)),
        "reachable_rate": float(matrix["reachable"].mean()),
        "travel_time_min": float(finite["travel_time_min"].min()),
        "travel_time_median_min": float(finite["travel_time_min"].median()),
        "travel_time_mean_min": float(finite["travel_time_min"].mean()),
        "travel_time_max_min": float(finite["travel_time_min"].max()),
        "zone_snap_max_m": float(snap["snap_distance_m"].max()),
        "freeflow_vs_ampeak": comp,
        "band8_speed_proxy_kmh": args.band8_speed,
        "notes": [
            "AM speed comes from historical LTA TrafficSpeedBands, not TrafficFlow volume.",
            "SpeedBand 8 is open-ended; its upper tail is represented by the configured proxy.",
            "Unmatched OSM edges retain Step-4 static speed.",
            "This step changes network impedance only; no OD calibration is performed.",
        ],
    }

    with open(
        out / "ampeak_network_validation.json",
        "w",
        encoding="utf-8",
    ) as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    print("-" * 72)
    print(f"Status                 : {summary['status']}")
    print(f"AM LTA links           : {summary['lta_links_speed']:,}")
    print(f"Matched OSM edges      : {summary['osm_edges_with_am_speed']:,}")
    print(f"AM speed median        : {summary['am_speed_median_kmh']:.2f} km/h")
    print(
        f"AM travel time median  : "
        f"{summary['travel_time_median_min']:.2f} min"
    )
    print(
        f"AM travel time mean    : "
        f"{summary['travel_time_mean_min']:.2f} min"
    )
    if "median_slowdown_ratio" in comp:
        print(
            f"Free-flow median       : "
            f"{comp['freeflow_median_min']:.2f} min"
        )
        print(
            f"AM/free-flow ratio     : "
            f"{comp['median_slowdown_ratio']:.3f}"
        )
    print(
        f"Reachable rate         : "
        f"{summary['reachable_rate']:.4%}"
    )
    print(f"Output                 : {out}")
    print("=" * 72)


if __name__ == "__main__":
    main()
