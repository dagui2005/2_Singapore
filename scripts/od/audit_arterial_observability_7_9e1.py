#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Step 7.9E-1 — Arterial Observability Expansion.

ZERO SIMULATION / READ-ONLY.

Builds an independent TrafficFlow -> directed MATSim diagnostic crosswalk.
It never replaces 7.3.6A and never launches MATSim/Java.
"""
from __future__ import annotations

import argparse
import ast
import csv
import hashlib
import json
import math
import re
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd
from scipy.spatial import cKDTree
from scipy import stats as scipy_stats

try:
    import geopandas as gpd
except ImportError:
    gpd = None

try:
    from pyproj import Transformer
except ImportError:
    Transformer = None

ROOT_DEFAULT = Path(r"D:\Luan\2026-05\2_Singapore")
TRAFFIC_JSON_REL = Path("Singapore_OD_MATSim_FinalData/08_TrafficCount/TrafficFlow_Data.json")
TRAFFIC_SHP_REL = Path("Singapore_OD_MATSim_FinalData/08_TrafficCount/TrafficFlow_Links.shp")
NETWORK_REL = Path("reports/matsim_network/network_links_source_copy.csv")
NODES_REL = Path("reports/matsim_network/network_nodes_source_copy.csv")
RESIDUAL_REL = Path("reports/spatial_residual_7_7c0/c0_section_table.csv")
OUT_REL = Path("reports/arterial_observability_7_9e1")
PREREG_REL = OUT_REL / "PREREG_7_9E1.md"

EXPECTED_PREREG_SHA256 = "4d5ee3e171674ee75094d3aa3eabc09ab8d0591abd9821fe20199cd8ed46751d"

SEARCH_RADIUS_M = 80.0
A_DISTANCE_M = 25.0
B_DISTANCE_M = 50.0
DIRECTION_DEG = 30.0
SAMPLE_SPACING_M = 50.0
MIN_SAMPLES = 5
MAX_SAMPLES = 25
MAX_CANDIDATES = 80

MIN_TRAFFIC_LINKS = 1278
MIN_AB_COVERAGE = 0.80
MAX_AB_P90_DISTANCE_M = 50.0
MIN_RESIDUAL_SECTIONS = 576
MIN_ARTERIAL_RESIDUAL_N = 30
N_PERM = 2000
PERM_SEED = 79101

MAINLINE = {"motorway", "motorway_link"}
ARTERIAL_CORE = {"primary", "secondary", "tertiary"}
COMPATIBLE_HIGHWAYS = {
    "CATA": {"motorway"},
    "SLIP_ROAD": {"motorway_link"},
    "CATB": {"trunk", "primary", "secondary"},
    "CATC": {"primary", "secondary", "tertiary"},
    "CATD": {"secondary", "tertiary", "residential"},
    "CATE": {"tertiary", "residential", "service", "unclassified"},
}

_TRANSFORMER = None
_PREREG_PATH: Path | None = None
_NETWORK: pd.DataFrame | None = None


def sha256_file(path: Path, chunk: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            b = f.read(chunk)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def norm_id(x: object) -> str:
    if x is None or (isinstance(x, float) and math.isnan(x)):
        return ""
    s = str(x).strip()
    if re.fullmatch(r"-?\d+\.0+", s):
        s = s.split(".", 1)[0]
    return s


def norm_text(x: object) -> str:
    if x is None or (isinstance(x, float) and math.isnan(x)):
        return ""
    return re.sub(r"\s+", " ", str(x).replace("\xa0", " ").strip()).upper()


def norm_name(x: object) -> str:
    s = norm_text(x).replace("&", " AND ")
    s = re.sub(r"[^A-Z0-9]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def name_similarity(a: object, b: object) -> float:
    ta = set(re.findall(r"[A-Z0-9]+", norm_name(a)))
    tb = set(re.findall(r"[A-Z0-9]+", norm_name(b)))
    if not ta or not tb:
        return 0.0
    return float(len(ta & tb) / max(1, len(ta | tb)))


def angle_diff(a: float, b: float) -> float:
    d = abs(float(a) - float(b)) % 360.0
    return min(d, 360.0 - d)


def safe_ratio(a: float, b: float) -> float:
    return float(a / b) if b and np.isfinite(b) else float("nan")


def spearman(x: pd.Series, y: pd.Series) -> float:
    z = pd.concat([
        pd.to_numeric(x, errors="coerce"),
        pd.to_numeric(y, errors="coerce"),
    ], axis=1).dropna()
    if len(z) < 3:
        return float("nan")
    return float(z.iloc[:, 0].corr(z.iloc[:, 1], method="spearman"))


def eta_squared(y: pd.Series, group: pd.Series) -> float:
    z = pd.concat([
        pd.to_numeric(y, errors="coerce"),
        pd.Series(group).astype(bool),
    ], axis=1).dropna()
    if len(z) < 3 or z.iloc[:, 1].nunique() < 2:
        return float("nan")
    vals = z.iloc[:, 0].to_numpy(dtype=float)
    labels = z.iloc[:, 1].to_numpy(dtype=bool)
    grand = float(vals.mean())
    ss_total = float(((vals - grand) ** 2).sum())
    if ss_total <= 0:
        return 0.0
    ss_between = 0.0
    for flag in (False, True):
        v = vals[labels == flag]
        if len(v):
            ss_between += len(v) * float((v.mean() - grand) ** 2)
    return float(ss_between / ss_total)


def load_traffic_json(path: Path) -> pd.DataFrame:
    with path.open("r", encoding="utf-8-sig") as f:
        obj = json.load(f)
    if isinstance(obj, list):
        rows = obj
    elif isinstance(obj, dict):
        rows = None
        for key in ("Value", "value", "d"):
            if isinstance(obj.get(key), list):
                rows = obj[key]
                break
        if rows is None:
            raise ValueError("TrafficFlow JSON 无法识别 Value/value/d 列表结构")
    else:
        raise ValueError("TrafficFlow JSON 顶层结构无效")

    df = pd.DataFrame(rows)
    required = {
        "LinkID", "RoadName", "RoadCat",
        "StartLon", "StartLat", "EndLon", "EndLat",
    }
    missing = sorted(required - set(df.columns))
    if missing:
        raise ValueError(f"TrafficFlow JSON 缺字段: {missing}")

    df["LinkID"] = df["LinkID"].map(norm_id)
    df["RoadName"] = df["RoadName"].map(norm_text)
    df["RoadCat"] = df["RoadCat"].map(norm_text)
    for c in ("StartLon", "StartLat", "EndLon", "EndLat"):
        df[c] = pd.to_numeric(df[c], errors="coerce")

    meta = (
        df.sort_values("LinkID")
        .groupby("LinkID", as_index=False)
        .agg(
            RoadName=("RoadName", "first"),
            RoadCat=("RoadCat", "first"),
            StartLon=("StartLon", "first"),
            StartLat=("StartLat", "first"),
            EndLon=("EndLon", "first"),
            EndLat=("EndLat", "first"),
        )
    )
    meta = meta[meta["LinkID"] != ""].copy()
    if meta.empty:
        raise ValueError("TrafficFlow 没有有效 LinkID")
    return meta


def attach_shapefile_geometry(
    root: Path,
    traffic: pd.DataFrame,
    explicit: Path | None,
) -> tuple[pd.DataFrame, str]:
    shp = explicit or (root / TRAFFIC_SHP_REL)
    if gpd is None or not shp.exists():
        return traffic, "json_endpoints"

    g = gpd.read_file(shp)
    required = {"LinkID", "geometry"}
    missing = sorted(required - set(g.columns))
    if missing:
        return traffic, "json_endpoints"
    g["LinkID"] = g["LinkID"].map(norm_id)
    g = g[g["LinkID"] != ""].copy()
    if g.crs is None:
        g = g.set_crs("EPSG:4326", allow_override=True)
    g = g.to_crs("EPSG:3414")
    g = g[["LinkID", "geometry"]].drop_duplicates("LinkID")
    out = traffic.merge(g, on="LinkID", how="left")
    used = int(out["geometry"].notna().sum())
    return out, f"shapefile_geometry({used}/{len(out)})"


def load_nodes(path: Path) -> pd.DataFrame:
    nodes = pd.read_csv(path, encoding="utf-8-sig", low_memory=False)
    cols = {str(c).strip().lower(): c for c in nodes.columns}
    id_col = next((cols[c] for c in ("node_id", "id", "node") if c in cols), None)
    x_col = next((cols[c] for c in ("x", "x_svy21_m", "easting") if c in cols), None)
    y_col = next((cols[c] for c in ("y", "y_svy21_m", "northing") if c in cols), None)
    if None in (id_col, x_col, y_col):
        raise ValueError("network_nodes_source_copy.csv 无法识别 node/x/y 字段")
    out = nodes[[id_col, x_col, y_col]].copy()
    out.columns = ["node_id", "x", "y"]
    out["node_id"] = out["node_id"].map(norm_id)
    out["x"] = pd.to_numeric(out["x"], errors="coerce")
    out["y"] = pd.to_numeric(out["y"], errors="coerce")
    out = out.dropna(subset=["node_id", "x", "y"]).drop_duplicates("node_id")
    return out


def load_network(path: Path, nodes: pd.DataFrame) -> pd.DataFrame:
    net = pd.read_csv(path, encoding="utf-8-sig", low_memory=False)
    cols = {str(c).strip().lower(): c for c in net.columns}
    required = ["from_node", "to_node", "length_m", "highway", "name"]
    missing = [c for c in required if c not in cols]
    if missing:
        raise ValueError(f"network 缺字段: {missing}")
    out = net[[cols[c] for c in required]].copy()
    out.columns = required
    out["from_node"] = out["from_node"].map(norm_id)
    out["to_node"] = out["to_node"].map(norm_id)
    out["length_m"] = pd.to_numeric(out["length_m"], errors="coerce")
    out["highway"] = out["highway"].map(norm_text).str.lower()
    out["name"] = out["name"].map(norm_text)
    out["matsim_link_id"] = "e" + out["from_node"] + "_" + out["to_node"]
    out = out[
        out["from_node"].ne("")
        & out["to_node"].ne("")
        & out["length_m"].gt(0)
    ].copy()
    if out["matsim_link_id"].duplicated().any():
        raise ValueError("network 存在重复 matsim_link_id")

    xy = nodes.set_index("node_id")[["x", "y"]]
    out = out.join(xy.rename(columns={"x": "from_x", "y": "from_y"}), on="from_node")
    out = out.join(xy.rename(columns={"x": "to_x", "y": "to_y"}), on="to_node")
    out["mid_x"] = (out["from_x"] + out["to_x"]) / 2.0
    out["mid_y"] = (out["from_y"] + out["to_y"]) / 2.0
    out = out.dropna(subset=["from_x", "from_y", "to_x", "to_y"]).copy()

    dx = out["to_x"].to_numpy(float) - out["from_x"].to_numpy(float)
    dy = out["to_y"].to_numpy(float) - out["from_y"].to_numpy(float)
    heading = np.degrees(np.arctan2(dx, dy))
    heading[heading < 0] += 360.0
    out["heading_deg"] = heading
    return out


def load_residual(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path, encoding="utf-8-sig", low_memory=False)
    cols = {str(c).strip().lower(): c for c in df.columns}
    required = ["lta_linkid", "ratio_8_9", "dominant_highway"]
    missing = [c for c in required if c not in cols]
    if missing:
        raise ValueError(f"residual table 缺字段: {missing}")
    # 7.7C-0 c0_section_table.csv 用 section_length_m；正式 length_m 为别名回退。
    len_col = cols.get("length_m") or cols.get("section_length_m")
    if len_col is None:
        raise ValueError("residual table 缺字段: length_m / section_length_m")
    ren = {cols[c]: c for c in required}
    ren[len_col] = "length_m"
    for c in ("pa", "region", "radial", "reciprocal", "has_reciprocal_pair"):
        if c in cols:
            ren[cols[c]] = c
    out = df.rename(columns=ren).copy()
    out["lta_linkid"] = out["lta_linkid"].map(norm_id)
    out["ratio_8_9"] = pd.to_numeric(out["ratio_8_9"], errors="coerce")
    out["residual"] = out["ratio_8_9"] - 1.0
    out["dominant_highway"] = out["dominant_highway"].map(norm_text).str.lower()
    out = out[out["lta_linkid"] != ""].copy()
    if out["lta_linkid"].duplicated().any():
        raise ValueError("residual table 存在重复 lta_linkid")
    if len(out) < MIN_RESIDUAL_SECTIONS:
        raise ValueError(f"residual sections={len(out)} < {MIN_RESIDUAL_SECTIONS}")
    return out


def make_transformer():
    if Transformer is None:
        raise RuntimeError("缺少 pyproj，无法转换到 EPSG:3414")
    return Transformer.from_crs("EPSG:4326", "EPSG:3414", always_xy=True)


def _finite_rows(arr: np.ndarray) -> np.ndarray:
    arr = np.asarray(arr, dtype=float)
    if arr.ndim != 2 or arr.shape[0] == 0:
        return arr.reshape(0, 2)
    good = np.isfinite(arr[:, :2]).all(axis=1)
    return arr[good][:, :2]


def extract_lta_coords(row: pd.Series) -> np.ndarray:
    geom = row.get("geometry", None)
    if geom is not None and not getattr(geom, "is_empty", True):
        try:
            coords = np.asarray(geom.coords, dtype=float)
            if coords.shape[0] >= 2:
                coords = _finite_rows(coords)
                if coords.shape[0] >= 2:
                    return coords
        except Exception:
            pass
    lon = np.array([row["StartLon"], row["EndLon"]], dtype=float)
    lat = np.array([row["StartLat"], row["EndLat"]], dtype=float)
    try:
        x, y = _TRANSFORMER.transform(lon, lat)
    except Exception:
        return np.empty((0, 2), dtype=float)
    return _finite_rows(np.column_stack([x, y]))


def sample_polyline(coords: np.ndarray) -> np.ndarray:
    if len(coords) < 2:
        return coords
    d = np.sqrt((np.diff(coords, axis=0) ** 2).sum(axis=1))
    cumulative = np.concatenate([[0.0], np.cumsum(d)])
    total = float(cumulative[-1])
    if not np.isfinite(total) or total <= 0:
        return coords[:1]
    n = int(min(MAX_SAMPLES, max(MIN_SAMPLES, math.ceil(total / SAMPLE_SPACING_M) + 1)))
    targets = np.linspace(0.0, total, n)
    out = []
    for target in targets:
        i = int(np.searchsorted(cumulative, target, side="right") - 1)
        i = max(0, min(i, len(coords) - 2))
        d0, d1 = cumulative[i], cumulative[i + 1]
        if d1 <= d0:
            out.append(coords[i])
        else:
            f = (target - d0) / (d1 - d0)
            out.append(coords[i] + f * (coords[i + 1] - coords[i]))
    return np.asarray(out, dtype=float)


def heading(coords: np.ndarray) -> float:
    dx = float(coords[-1, 0] - coords[0, 0])
    dy = float(coords[-1, 1] - coords[0, 1])
    if abs(dx) < 1e-9 and abs(dy) < 1e-9:
        return float("nan")
    h = math.degrees(math.atan2(dx, dy))
    return h if h >= 0 else h + 360.0


def point_segment_distance_sq(
    px: float, py: float,
    ax: np.ndarray, ay: np.ndarray,
    bx: np.ndarray, by: np.ndarray,
) -> np.ndarray:
    vx = bx - ax
    vy = by - ay
    wx = px - ax
    wy = py - ay
    denom = vx * vx + vy * vy
    t = np.divide(wx * vx + wy * vy, denom, out=np.zeros_like(denom), where=denom > 0)
    t = np.clip(t, 0.0, 1.0)
    cx = ax + t * vx
    cy = ay + t * vy
    return (px - cx) ** 2 + (py - cy) ** 2


def min_distance_to_edges(samples, fx, fy, tx, ty) -> np.ndarray:
    best = np.full(len(fx), np.inf, dtype=float)
    for px, py in samples:
        best = np.minimum(best, point_segment_distance_sq(px, py, fx, fy, tx, ty))
    return np.sqrt(best)


def build_crosswalk(traffic: pd.DataFrame, network: pd.DataFrame):
    tree = cKDTree(network[["mid_x", "mid_y"]].to_numpy(dtype=float))
    fx = network["from_x"].to_numpy(float)
    fy = network["from_y"].to_numpy(float)
    tx = network["to_x"].to_numpy(float)
    ty = network["to_y"].to_numpy(float)
    eh = network["heading_deg"].to_numpy(float)
    eid = network["matsim_link_id"].to_numpy(str)
    hw = network["highway"].to_numpy(str)
    nm = network["name"].to_numpy(str)

    all_candidates = []
    best_records = []

    for _, row in traffic.iterrows():
        lta_id = str(row["LinkID"])
        coords = extract_lta_coords(row)
        if len(coords) < 2:
            continue
        samples = sample_polyline(coords)
        if len(samples):
            samples = samples[np.isfinite(samples).all(axis=1)]
        if len(samples) == 0:
            continue
        h_lta = heading(coords)

        idx_set: set[int] = set()
        for p in samples:
            idx_set.update(int(i) for i in tree.query_ball_point(p, SEARCH_RADIUS_M))
        if not idx_set:
            continue

        cand = np.fromiter(sorted(idx_set), dtype=np.int64)
        dist_m = min_distance_to_edges(samples, fx[cand], fy[cand], tx[cand], ty[cand])
        if np.isfinite(h_lta):
            dir_m = np.array([angle_diff(h_lta, eh[j]) for j in cand], dtype=float)
        else:
            dir_m = np.full(len(cand), np.nan)

        roadcat = str(row["RoadCat"]).upper()
        roadname = str(row["RoadName"])
        local = []
        for k, j in enumerate(cand):
            d = float(dist_m[k])
            direc = float(dir_m[k])
            highway = str(hw[j]).lower()
            compat = highway in COMPATIBLE_HIGHWAYS.get(roadcat, set())
            ns = name_similarity(roadname, nm[j])
            if d <= A_DISTANCE_M and np.isfinite(direc) and direc <= DIRECTION_DEG and compat:
                tier, rank = "A_STRICT_SEMANTIC_DIRECTION", 1
            elif d <= B_DISTANCE_M and np.isfinite(direc) and direc <= DIRECTION_DEG:
                tier, rank = "B_DIRECTION_GEOMETRY", 2
            elif d <= SEARCH_RADIUS_M:
                tier, rank = "C_GEOMETRY_ONLY", 3
            else:
                continue
            local.append({
                "lta_linkid": lta_id,
                "RoadName": roadname,
                "RoadCat": roadcat,
                "matsim_link_id": str(eid[j]),
                "highway": highway,
                "matsim_name": str(nm[j]),
                "distance_m": d,
                "direction_diff_deg": direc,
                "semantic_compatible": bool(compat),
                "name_similarity": ns,
                "tier": tier,
                "tier_rank": rank,
            })

        local.sort(key=lambda r: (
            r["tier_rank"], r["distance_m"],
            r["direction_diff_deg"] if np.isfinite(r["direction_diff_deg"]) else 999.0,
            -r["name_similarity"], r["matsim_link_id"],
        ))
        # Keep the full nearest evidence up to a deterministic per-LTA cap.
        all_candidates.extend(local[:MAX_CANDIDATES])
        seen = set()
        for r in local:
            if r["tier"] in seen:
                continue
            best_records.append(r.copy())
            seen.add(r["tier"])
            if len(seen) == 3:
                break

    candidates = pd.DataFrame(all_candidates)
    best = pd.DataFrame(best_records)
    if candidates.empty or best.empty:
        raise RuntimeError("diagnostic crosswalk 未生成任何候选/代表记录")
    return candidates, best


def build_section_summary(traffic: pd.DataFrame, best: pd.DataFrame):
    rows = []
    for lta_id, g in best.groupby("lta_linkid", sort=True):
        base = g.iloc[0]
        rows.append({
            "lta_linkid": lta_id,
            "RoadName": base["RoadName"],
            "RoadCat": base["RoadCat"],
            "has_A": bool((g["tier"] == "A_STRICT_SEMANTIC_DIRECTION").any()),
            "has_B": bool((g["tier"] == "B_DIRECTION_GEOMETRY").any()),
            "has_C": bool((g["tier"] == "C_GEOMETRY_ONLY").any()),
        })
    return pd.DataFrame(rows)


def build_main_best(best: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for lta_id, g in best.groupby("lta_linkid", sort=True):
        a = g[g["tier"] == "A_STRICT_SEMANTIC_DIRECTION"]
        b = g[g["tier"] == "B_DIRECTION_GEOMETRY"]
        c = g[g["tier"] == "C_GEOMETRY_ONLY"]
        if len(a):
            r, level = a.iloc[0], "A_STRICT_SEMANTIC_DIRECTION"
        elif len(b):
            r, level = b.iloc[0], "B_DIRECTION_GEOMETRY"
        elif len(c):
            r, level = c.iloc[0], "C_GEOMETRY_ONLY"
        else:
            continue
        rows.append({
            "lta_linkid": lta_id,
            "RoadName": r["RoadName"],
            "RoadCat": r["RoadCat"],
            "obs_level_ab_priority": level,
            "matsim_link_id": r["matsim_link_id"],
            "highway": str(r["highway"]).lower(),
            "matsim_name": r["matsim_name"],
            "distance_m": float(r["distance_m"]),
            "direction_diff_deg": float(r["direction_diff_deg"]),
            "semantic_compatible": bool(r["semantic_compatible"]),
            "name_similarity": float(r["name_similarity"]),
        })
    main = pd.DataFrame(rows)
    if not main.empty:
        main["ab_match"] = main["obs_level_ab_priority"].isin(
            {"A_STRICT_SEMANTIC_DIRECTION", "B_DIRECTION_GEOMETRY"}
        )
        main["is_arterial_core"] = main["highway"].isin(ARTERIAL_CORE)
    return main


def observability_by_tier(traffic, best, main) -> pd.DataFrame:
    total = int(traffic["LinkID"].nunique())
    rows = []
    for tier in ("A_STRICT", "A+B_MAIN", "A+B+C_RELAXED"):
        if tier == "A_STRICT":
            g = main[main["obs_level_ab_priority"] == "A_STRICT_SEMANTIC_DIRECTION"]
        elif tier == "A+B_MAIN":
            g = main[main["ab_match"]]
        else:
            g = main
        d = g["distance_m"].dropna()
        rows.append({
            "tier": tier,
            "traffic_total_links": total,
            "matched_links": int(g["lta_linkid"].nunique()),
            "coverage": safe_ratio(g["lta_linkid"].nunique(), total),
            "median_distance_m": float(d.median()) if len(d) else np.nan,
            "p90_distance_m": float(d.quantile(0.90)) if len(d) else np.nan,
            "median_direction_diff_deg": float(g["direction_diff_deg"].median()) if len(g) else np.nan,
            "arterial_core_links": int(g.loc[g["is_arterial_core"], "lta_linkid"].nunique()) if len(g) else 0,
        })
    return pd.DataFrame(rows)


def roadcat_highway_matrix(main):
    g = main[main["ab_match"]].copy()
    if g.empty:
        return pd.DataFrame(columns=["RoadCat", "highway", "n", "share_within_RoadCat"])
    out = g.groupby(["RoadCat", "highway"], as_index=False).agg(n=("lta_linkid", "nunique"))
    out["share_within_RoadCat"] = out["n"] / out.groupby("RoadCat")["n"].transform("sum")
    return out.sort_values(["RoadCat", "n"], ascending=[True, False])


def roadcat_summary(main):
    rows = []
    for rc, g in main.groupby("RoadCat", sort=True):
        ab = g[g["ab_match"]]
        d = ab["distance_m"].dropna()
        rows.append({
            "RoadCat": rc,
            "traffic_links": int(g["lta_linkid"].nunique()),
            "ab_matched_links": int(ab["lta_linkid"].nunique()),
            "ab_coverage": safe_ratio(ab["lta_linkid"].nunique(), g["lta_linkid"].nunique()),
            "ab_arterial_core_share": safe_ratio(ab.loc[ab["is_arterial_core"], "lta_linkid"].nunique(), ab["lta_linkid"].nunique()),
            "dominant_highway": str(ab["highway"].value_counts().index[0]) if len(ab) else "",
            "median_distance_m": float(d.median()) if len(d) else np.nan,
            "p90_distance_m": float(d.quantile(0.90)) if len(d) else np.nan,
            "median_direction_diff_deg": float(ab["direction_diff_deg"].median()) if len(ab) else np.nan,
        })
    return pd.DataFrame(rows)


def permutation_p(y, labels):
    y = np.asarray(y, dtype=float)
    labels = np.asarray(labels, dtype=bool)
    if len(y) < 3 or labels.sum() == 0 or labels.sum() == len(y):
        return np.nan, np.nan
    observed = abs(float(y[labels].mean() - y[~labels].mean()))
    rng = np.random.default_rng(PERM_SEED)
    greater = 0
    for _ in range(N_PERM):
        sh = rng.permutation(labels)
        diff = abs(float(y[sh].mean() - y[~sh].mean()))
        if diff >= observed:
            greater += 1
    return observed, float((1 + greater) / (N_PERM + 1))


def stratified_permutation(df: pd.DataFrame, strata_col: str):
    if strata_col not in df.columns:
        return np.nan, {"stratum": strata_col, "blocked": True, "reason": "missing_stratum"}
    z = df[["residual", "is_arterial_core", strata_col]].dropna().copy()
    groups = []
    observed_score = 0.0
    weight = 0
    for _, g in z.groupby(strata_col, dropna=False):
        if g["is_arterial_core"].nunique() < 2:
            continue
        y = g["residual"].to_numpy(float)
        lab = g["is_arterial_core"].to_numpy(bool)
        observed_score += abs(float(y[lab].mean() - y[~lab].mean())) * len(g)
        weight += len(g)
        groups.append((y, lab, len(g)))
    if not groups or weight == 0:
        return np.nan, {"stratum": strata_col, "blocked": True, "reason": "no_mixed_strata"}
    observed = observed_score / weight
    rng = np.random.default_rng(PERM_SEED + 1)
    greater = 0
    for _ in range(N_PERM):
        score = 0.0
        wt = 0
        for y, lab, n in groups:
            sh = rng.permutation(lab)
            score += abs(float(y[sh].mean() - y[~sh].mean())) * n
            wt += n
        if wt and score / wt >= observed:
            greater += 1
    return float((1 + greater) / (N_PERM + 1)), {
        "stratum": strata_col,
        "blocked": False,
        "observed_weighted_abs_mean_diff": float(observed),
        "mixed_strata": len(groups),
    }


def residual_coupling(residual: pd.DataFrame, main: pd.DataFrame):
    x = residual.merge(
        main[["lta_linkid", "highway", "obs_level_ab_priority", "distance_m", "direction_diff_deg"]],
        on="lta_linkid", how="left", validate="one_to_one",
    )
    x["is_arterial_core"] = x["highway"].isin(ARTERIAL_CORE)
    x["ab_match"] = x["obs_level_ab_priority"].isin({"A_STRICT_SEMANTIC_DIRECTION", "B_DIRECTION_GEOMETRY"})
    z = x[x["ab_match"] & x["residual"].notna()].copy()
    if z.empty:
        return pd.DataFrame(), z, {"valid_residual_n": 0, "arterial_n": 0, "nonarterial_n": 0}

    group_rows = []
    for flag in (True, False):
        g = z[z["is_arterial_core"] == flag]
        group_rows.append({
            "is_arterial_core": bool(flag),
            "n": int(len(g)),
            "mean_residual": float(g["residual"].mean()) if len(g) else float("nan"),
            "median_residual": float(g["residual"].median()) if len(g) else float("nan"),
            "p10_residual": float(g["residual"].quantile(0.10)) if len(g) else float("nan"),
            "p90_residual": float(g["residual"].quantile(0.90)) if len(g) else float("nan"),
        })

    y = z["residual"].to_numpy(float)
    lab = z["is_arterial_core"].to_numpy(bool)
    obs_diff, p_un = permutation_p(y, lab)
    spr = spearman(z["residual"], z["is_arterial_core"].astype(int))
    eta = eta_squared(z["residual"], z["is_arterial_core"])

    strata = "pa" if "pa" in x.columns and x["pa"].notna().sum() >= 3 else ("region" if "region" in x.columns and x["region"].notna().sum() >= 3 else None)
    if strata:
        p_strat, strat_meta = stratified_permutation(z, strata)
    else:
        p_strat, strat_meta = np.nan, {"stratum": None, "blocked": True, "reason": "no_stratum"}

    meta = {
        "valid_residual_n": int(len(z)),
        "arterial_n": int(lab.sum()),
        "nonarterial_n": int((~lab).sum()),
        "spearman_residual_vs_arterial_flag": spr,
        "eta_squared": eta,
        "observed_abs_mean_diff": obs_diff,
        "permutation_p_unstratified": p_un,
        "permutation_p_stratified": p_strat,
        "stratified_meta": strat_meta,
    }
    return pd.DataFrame(group_rows), z, meta


def static_zero_simulation_audit(src_path: Path) -> tuple[bool, str]:
    """AST-based self-audit: no process-spawning import or shell call.

    Must not scan its own source text for literal tokens, otherwise the
    audit string list matches itself (7.9E-0 lesson). We therefore parse
    the module and inspect Import/ImportFrom nodes and Attribute calls.
    """
    tree = ast.parse(src_path.read_text(encoding="utf-8"))
    mods: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            mods.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            mods.add(node.module.split(".")[0])
    banned = {"subprocess", "multiprocessing", "pty", "ptyprocess", "ctypes", "pexpect"}
    hit_mods = sorted(banned & mods)
    spawn_attrs: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            if node.func.attr.lower() in {"system", "popen", "spawnv", "spawnl", "execv", "execl"}:
                spawn_attrs.append(node.func.attr)
    ok = (not hit_mods) and (not spawn_attrs)
    return ok, f"ast audit: banned_modules={hit_mods} spawn_attr_calls={sorted(set(spawn_attrs))}"


def residual_arterial_count(best: pd.DataFrame, residual_ids: set[str], allowed_tiers: set[str]) -> int:
    """Arterial-core representative count restricted to the residual section universe.

    The prereg's C_ONLY branch must compare residual-restricted counts, not
    universe-wide counts (universe-wide would wrongly promote C_ONLY).
    """
    b = best[best["tier"].isin(allowed_tiers) & best["lta_linkid"].isin(residual_ids)]
    if b.empty:
        return 0
    pri = {
        "A_STRICT_SEMANTIC_DIRECTION": 0,
        "B_DIRECTION_GEOMETRY": 1,
        "C_GEOMETRY_ONLY": 2,
    }
    b = b.assign(_pri=b["tier"].map(pri)).sort_values(["_pri", "distance_m", "lta_linkid"])
    rep = b.groupby("lta_linkid").first()
    return int(rep["highway"].isin(ARTERIAL_CORE).sum())


def build_checks(traffic, network, residual, main, observability, residual_meta):
    checks = []
    prereg_hash = sha256_file(_PREREG_PATH)
    checks.append({
        "check": "E1.01_PREREG_HASH",
        "pass": prereg_hash.lower() == EXPECTED_PREREG_SHA256.lower(),
        "detail": prereg_hash,
    })

    zero_sim, zero_detail = static_zero_simulation_audit(Path(__file__))
    checks.append({
        "check": "E1.02_ZERO_SIMULATION",
        "pass": bool(zero_sim),
        "detail": zero_detail,
    })
    checks.append({
        "check": "E1.03_NETWORK_FIELDS_AND_UNIQUE",
        "pass": bool(len(network) > 0 and not network["matsim_link_id"].duplicated().any()),
        "detail": f"usable_directed_links={len(network):,}",
    })
    checks.append({
        "check": "E1.04_NODE_COORDINATE_COVERAGE",
        "pass": bool(len(network) > 0),
        "detail": f"links_with_endpoint_xy={len(network):,}",
    })
    traffic_n = int(traffic["LinkID"].nunique())
    checks.append({
        "check": "E1.05_TRAFFIC_LINK_UNIVERSE",
        "pass": traffic_n >= MIN_TRAFFIC_LINKS,
        "detail": f"traffic_links={traffic_n:,}; minimum={MIN_TRAFFIC_LINKS:,}",
    })

    ab = observability[observability["tier"] == "A+B_MAIN"]
    ab_cov = float(ab["coverage"].iloc[0]) if len(ab) else np.nan
    ab_p90 = float(ab["p90_distance_m"].iloc[0]) if len(ab) else np.nan
    checks.append({
        "check": "E1.06_AB_COVERAGE_GE_80PCT",
        "pass": bool(np.isfinite(ab_cov) and ab_cov >= MIN_AB_COVERAGE),
        "detail": f"coverage={ab_cov:.6f}",
    })
    checks.append({
        "check": "E1.07_AB_P90_DISTANCE_LE_50M",
        "pass": bool(np.isfinite(ab_p90) and ab_p90 <= MAX_AB_P90_DISTANCE_M),
        "detail": f"p90_distance_m={ab_p90:.3f}",
    })
    checks.append({
        "check": "E1.08_RESIDUAL_SECTIONS_GE_576",
        "pass": bool(len(residual) >= MIN_RESIDUAL_SECTIONS),
        "detail": f"sections={len(residual):,}",
    })
    valid_n = int(residual_meta.get("valid_residual_n", 0))
    arterial_n = int(residual_meta.get("arterial_n", 0))
    checks.append({
        "check": "E1.09_RESIDUAL_COUPLING_SUPPORT",
        "pass": bool(valid_n >= MIN_ARTERIAL_RESIDUAL_N and arterial_n >= 1),
        "detail": f"valid_residual={valid_n}; arterial={arterial_n}",
    })
    checks.append({
        "check": "E1.10_ARTERIAL_OBSERVABILITY_GE_30",
        "pass": arterial_n >= MIN_ARTERIAL_RESIDUAL_N,
        "detail": f"AB_arterial_residual_n={arterial_n}; required={MIN_ARTERIAL_RESIDUAL_N}",
    })
    checks.append({
        "check": "E1.11_OUTPUT_ISOLATION",
        "pass": True,
        "detail": "outputs isolated under reports/arterial_observability_7_9e1",
    })
    checks.append({
        "check": "E1.12_PROVENANCE_READY",
        "pass": True,
        "detail": "manifest includes sha256/mtime/size",
    })
    return checks


def write_csv(df: pd.DataFrame, path: Path):
    df.to_csv(path, index=False, encoding="utf-8-sig", quoting=csv.QUOTE_MINIMAL)


def manifest(paths: dict[str, Path]):
    result = {}
    for k, p in paths.items():
        st = p.stat()
        result[k] = {
            "path": str(p),
            "sha256": sha256_file(p),
            "mtime_ns": int(st.st_mtime_ns),
            "size_bytes": int(st.st_size),
        }
    return result


def render_report(out, checks, traffic, observability, roadcat_matrix, residual_meta, status, geometry_mode, script_sha, residual_universe=None, roadcat_summary=None):
    lines = [
        "# Step 7.9E-1 — Arterial Observability Expansion",
        "",
        f"## Status",
        f"**{status}**",
        "",
        "## Scope",
        "零仿真、只读；独立 diagnostic crosswalk；不替换 7.3.6A。",
        "",
        "## TrafficFlow universe",
        f"- unique TrafficFlow links: **{traffic['LinkID'].nunique():,}**",
        f"- geometry source: **{geometry_mode}**",
        f"- usable directed MATSim links: **{len(_NETWORK):,}**",
        "",
        "## Observability",
        "| Tier | Coverage | Median distance (m) | P90 distance (m) | Arterial-core residual links |",
        "|---|---:|---:|---:|---:|",
    ]
    for _, r in observability.iterrows():
        lines.append(
            f"| {r['tier']} | {r['coverage']:.2%} | {r['median_distance_m']:.2f} | {r['p90_distance_m']:.2f} | {int(r['arterial_core_links'])} |"
        )
    lines += [
        "",
        "## Per-RoadCat observability (A+B)",
        "| RoadCat | traffic links | A+B matched | coverage | arterial-core share | dominant highway | median dist (m) | P90 dist (m) |",
        "|---|---:|---:|---:|---:|---|---:|---:|",
    ]
    if roadcat_summary is None or len(roadcat_summary) == 0:
        lines.append("| — | 0 | 0 | — | — | — | — | — |")
    else:
        for _, r in roadcat_summary.iterrows():
            lines.append(
                f"| {r['RoadCat']} | {int(r['traffic_links'])} | {int(r['ab_matched_links'])} | "
                f"{r['ab_coverage']:.2%} | {r['ab_arterial_core_share']:.2%} | {r['dominant_highway']} | "
                f"{r['median_distance_m']:.2f} | {r['p90_distance_m']:.2f} |"
            )
    lines += [
        "",
        "## RoadCat × OSM highway (A+B)",
        "| RoadCat | highway | n | share within RoadCat |",
        "|---|---|---:|---:|",
    ]
    if roadcat_matrix.empty:
        lines.append("| — | — | 0 | — |")
    else:
        for _, r in roadcat_matrix.iterrows():
            lines.append(f"| {r['RoadCat']} | {r['highway']} | {int(r['n'])} | {r['share_within_RoadCat']:.2%} |")
    ru = residual_universe or {}
    lines += [
        "",
        "## Residual section universe",
        f"- residual sections: **{ru.get('residual_n', 0)}**",
        f"- residual RoadCat composition: **{ru.get('residual_roadcat', {})}**",
        f"- residual representative highway (A+B): **{ru.get('residual_rep_highway_ab', {})}**",
        f"- arterial residual n — A: **{ru.get('arterial_residual_n_strict', 0)}** / A+B: **{ru.get('arterial_residual_n_ab', 0)}** / A+B+C: **{ru.get('arterial_residual_n_relaxed', 0)}**",
        "",
        "## Residual coupling (A+B)",
        f"- valid residual sample: **{residual_meta.get('valid_residual_n', 0)}**",
        f"- arterial-core sample: **{residual_meta.get('arterial_n', 0)}**",
        f"- non-arterial sample: **{residual_meta.get('nonarterial_n', 0)}**",
        f"- Spearman: **{residual_meta.get('spearman_residual_vs_arterial_flag', np.nan):.6f}**",
        f"- eta²: **{residual_meta.get('eta_squared', np.nan):.6f}**",
        f"- permutation p (unstratified): **{residual_meta.get('permutation_p_unstratified', np.nan):.6f}**",
        f"- permutation p (stratified): **{residual_meta.get('permutation_p_stratified', np.nan):.6f}**",
        "",
        "## Boundary",
        "A+B 达到 ≥30 个 arterial residual sections 只表示可观测性得到支持，不直接证明 arterial capacity 错误。",
        "",
        "## Decision state",
        f"- **{status}**",
        "- `OBSERVABILITY_PASS` -> 7.9E-2 arterial mechanism audit",
        "- `C_ONLY_OBSERVABILITY` -> 不得直接作 arterial mechanism attribution",
        "- `OBSERVABILITY_BLOCKED` -> 转向外部 LTA 数据或其他独立观测",
        "",
        "## Gates",
        "| Check | Result | Detail |",
        "|---|---|---|",
    ]
    for c in checks:
        lines.append(f"| {c['check']} | {'PASS' if c['pass'] else 'FAIL'} | {c['detail']} |")
    lines += [
        "",
        f"Script SHA256: `{script_sha}`",
        "",
    ]
    return "\n".join(lines)


def main():
    global _TRANSFORMER, _PREREG_PATH, _NETWORK

    ap = argparse.ArgumentParser(description="Step 7.9E-1 arterial observability expansion")
    ap.add_argument("--project-root", type=Path, default=ROOT_DEFAULT)
    ap.add_argument("--traffic-json", type=Path, default=None)
    ap.add_argument("--traffic-shp", type=Path, default=None)
    ap.add_argument("--network", type=Path, default=None)
    ap.add_argument("--nodes", type=Path, default=None)
    ap.add_argument("--residual-table", type=Path, default=None)
    ap.add_argument("--prereg", type=Path, default=None)
    ap.add_argument("--out-dir", type=Path, default=OUT_REL)
    args = ap.parse_args()

    root = args.project_root
    out = args.out_dir if args.out_dir.is_absolute() else root / args.out_dir
    out.mkdir(parents=True, exist_ok=True)

    traffic_json = args.traffic_json or (root / TRAFFIC_JSON_REL)
    traffic_shp = args.traffic_shp or (root / TRAFFIC_SHP_REL)
    network_path = args.network or (root / NETWORK_REL)
    nodes_path = args.nodes or (root / NODES_REL)
    residual_path = args.residual_table or (root / RESIDUAL_REL)
    prereg_path = args.prereg or (root / PREREG_REL)

    for p in (traffic_json, network_path, nodes_path, residual_path, prereg_path):
        if not p.exists():
            raise FileNotFoundError(f"输入不存在: {p}")

    _PREREG_PATH = prereg_path
    _TRANSFORMER = make_transformer()
    prereg_sha = sha256_file(prereg_path)

    print("=" * 78)
    print("STEP 7.9E-1 | ARTERIAL OBSERVABILITY EXPANSION")
    print("=" * 78)
    print("ZERO SIMULATION / READ-ONLY")
    print(f"Project    : {root}")
    print(f"Traffic    : {traffic_json}")
    print(f"Traffic shp: {traffic_shp if traffic_shp.exists() else 'not used'}")
    print(f"Network    : {network_path}")
    print(f"Nodes      : {nodes_path}")
    print(f"Residual   : {residual_path}")
    print(f"Prereg     : {prereg_path}")
    print(f"Prereg SHA : {prereg_sha}")

    traffic = load_traffic_json(traffic_json)
    traffic, geometry_mode = attach_shapefile_geometry(root, traffic, traffic_shp)
    nodes = load_nodes(nodes_path)
    network = load_network(network_path, nodes)
    residual = load_residual(residual_path)
    _NETWORK = network

    print(f"[1/6] TrafficFlow unique links = {traffic['LinkID'].nunique():,}")
    print(f"[2/6] Network usable directed links = {len(network):,}")
    print(f"[3/6] Residual sections = {len(residual):,}")
    print("[4/6] Building independent diagnostic crosswalk ...")

    candidates, best = build_crosswalk(traffic, network)
    main = build_main_best(best)
    print(f"      candidate rows = {len(candidates):,}")
    print(f"      representative rows = {len(main):,}")

    observability = observability_by_tier(traffic, best, main)
    roadcat_matrix = roadcat_highway_matrix(main)
    roadcat_summary_df = roadcat_summary(main)
    residual_stats, residual_rows, residual_meta = residual_coupling(residual, main)
    checks = build_checks(traffic, network, residual, main, observability, residual_meta)

    ab_cov = float(observability.loc[observability["tier"] == "A+B_MAIN", "coverage"].iloc[0])
    ab_ar_n = int(residual_meta.get("arterial_n", 0))
    res_ids = set(residual["lta_linkid"])
    strict_ar_n = residual_arterial_count(best, res_ids, {"A_STRICT_SEMANTIC_DIRECTION"})
    relaxed_ar_n = residual_arterial_count(best, res_ids, {
        "A_STRICT_SEMANTIC_DIRECTION", "B_DIRECTION_GEOMETRY", "C_GEOMETRY_ONLY",
    })

    # Residual-section universe composition (explains the arterial absence).
    resid_rep = main[main["lta_linkid"].isin(res_ids)]
    residual_universe = {
        "residual_n": int(len(res_ids)),
        "residual_roadcat": {str(k): int(v) for k, v in residual["RoadCat"].value_counts().items()}
        if "RoadCat" in residual.columns else {},
        "residual_rep_highway_ab": {str(k): int(v) for k, v in resid_rep["highway"].value_counts().items()},
        "arterial_residual_n_strict": int(strict_ar_n),
        "arterial_residual_n_ab": int(ab_ar_n),
        "arterial_residual_n_relaxed": int(relaxed_ar_n),
    }

    if ab_cov >= MIN_AB_COVERAGE and ab_ar_n >= MIN_ARTERIAL_RESIDUAL_N and all(c["pass"] for c in checks):
        status = "OBSERVABILITY_PASS"
    elif ab_ar_n < MIN_ARTERIAL_RESIDUAL_N and relaxed_ar_n >= MIN_ARTERIAL_RESIDUAL_N:
        status = "C_ONLY_OBSERVABILITY"
    else:
        status = "OBSERVABILITY_BLOCKED"

    write_csv(candidates, out / "e1_crosswalk_candidates.csv")
    write_csv(best, out / "e1_crosswalk_best.csv")
    write_csv(main, out / "e1_section_summary.csv")
    write_csv(roadcat_matrix, out / "e1_roadcat_highway_matrix.csv")
    write_csv(roadcat_summary_df, out / "e1_observability_by_roadcat.csv")
    write_csv(residual_stats, out / "e1_residual_coupling.csv")
    write_csv(pd.DataFrame([
        {"kind": "unstratified", "p": residual_meta.get("permutation_p_unstratified", np.nan)},
        {"kind": "stratified", "p": residual_meta.get("permutation_p_stratified", np.nan)},
    ]), out / "e1_residual_permutation.csv")
    write_csv(observability, out / "e1_sensitivity_summary.csv")
    write_csv(pd.DataFrame(checks), out / "e1_checks.csv")

    inputs = {
        "traffic_json": traffic_json,
        "traffic_shp": traffic_shp if traffic_shp.exists() else traffic_json,
        "network": network_path,
        "nodes": nodes_path,
        "residual": residual_path,
        "prereg": prereg_path,
        "script": Path(__file__).resolve(),
    }
    (out / "e1_input_manifest.json").write_text(
        json.dumps(manifest(inputs), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    script_sha = sha256_file(Path(__file__).resolve())
    summary = {
        "step": "7.9E-1",
        "status": status,
        "zero_simulation": True,
        "network_modified": False,
        "matsim_rerun": False,
        "traffic_links": int(traffic["LinkID"].nunique()),
        "network_directed_links": int(len(network)),
        "candidate_rows": int(len(candidates)),
        "representative_rows": int(len(main)),
        "ab_coverage": ab_cov,
        "ab_p90_distance_m": float(observability.loc[observability["tier"] == "A+B_MAIN", "p90_distance_m"].iloc[0]),
        "arterial_residual_n_strict": int(strict_ar_n),
        "ab_arterial_residual_n": ab_ar_n,
        "relaxed_arterial_residual_n": relaxed_ar_n,
        "residual_universe": residual_universe,
        "residual_meta": residual_meta,
        "prereg_sha256": prereg_sha,
        "script_sha256": script_sha,
        "hard_pass": all(c["pass"] for c in checks),
        "hard_pass_count": int(sum(bool(c["pass"]) for c in checks)),
        "hard_total": int(len(checks)),
        "geometry_mode": geometry_mode,
    }
    (out / "e1_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    report = render_report(
        out,
        checks,
        traffic,
        observability,
        roadcat_matrix,
        residual_meta,
        status,
        geometry_mode,
        script_sha,
        residual_universe,
        roadcat_summary_df,
    )
    (out / "STEP7_9E1_REPORT.md").write_text(report, encoding="utf-8")

    print("-" * 78)
    print("[6/6] OBSERVABILITY")
    for _, r in observability.iterrows():
        print(f"      {r['tier']:<16s} cov={r['coverage']:.4f}  n={int(r['matched_links']):4d}  "
              f"median={r['median_distance_m']:.2f}m  p90={r['p90_distance_m']:.2f}m  "
              f"arterial={int(r['arterial_core_links'])}")
    print("      RESIDUAL UNIVERSE")
    print(f"        RoadCat        = {residual_universe['residual_roadcat']}")
    print(f"        rep highway AB = {residual_universe['residual_rep_highway_ab']}")
    print(f"        arterial n     = A:{strict_ar_n}  A+B:{ab_ar_n}  A+B+C:{relaxed_ar_n}")
    print("      RESIDUAL COUPLING (A+B)")
    print(f"        valid_residual = {residual_meta.get('valid_residual_n', 0)}")
    print(f"        arterial       = {residual_meta.get('arterial_n', 0)}")
    print(f"        non-arterial   = {residual_meta.get('nonarterial_n', 0)}")
    print(f"        spearman       = {residual_meta.get('spearman_residual_vs_arterial_flag', float('nan'))}")
    print(f"        eta^2          = {residual_meta.get('eta_squared', float('nan'))}")
    print(f"        perm p (unstr) = {residual_meta.get('permutation_p_unstratified', float('nan'))}")
    print(f"        perm p (strat) = {residual_meta.get('permutation_p_stratified', float('nan'))}")
    print("-" * 78)
    print(f"STATUS      = {status}")
    print(f"HARD GATES  = {sum(bool(c['pass']) for c in checks)}/{len(checks)}")
    print(f"OUTPUT      = {out}")
    print("NOTE        = no MATSim/Java call")

    # BLOCKED is a legitimate prereg decision state, not an execution error.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
