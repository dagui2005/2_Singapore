#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Step 7.9F-2 — Secondary/Tertiary Residual Mechanism Audit.
ZERO SIMULATION / READ-ONLY / DIAGNOSTIC ONLY.
"""
from __future__ import annotations

import argparse
import ast
import gzip
import hashlib
import json
import math
import re
from pathlib import Path

import numpy as np
import pandas as pd

ROOT_DEFAULT = Path(r"D:\Luan\2026-05\2_Singapore")
TRAFFIC_REL = Path("Singapore_OD_MATSim_FinalData/08_TrafficCount/TrafficFlow_Data.json")
TRAFFIC_GEOM_REL = Path("Singapore_OD_MATSim_FinalData/08_TrafficCount/TrafficFlow_Links.shp")
E1_REL = Path("reports/arterial_observability_7_9e1/e1_crosswalk_candidates.csv")
E2_REL = Path("reports/arterial_expanded_residual_7_9e2/e2_section_residual_main.csv")
NETWORK_REL = Path("reports/matsim_network/network_links_source_copy.csv")
NODES_REL = Path("reports/matsim_network/network_nodes_source_copy.csv")
W01_REL = Path("matsim_final_7_6h/outputs/W01_rc_min/ITERS/it.19")
OUT_REL = Path("reports/secondary_tertiary_residual_7_9f2")
PREREG_REL = OUT_REL / "PREREG_7_9F2.md"
EXPECTED_PREREG_SHA256 = "5c361b2de1731d6b4325bbcb3b739e85ce5fcc4fb02640e03a14239d5f968bec"

SCALE = 459794.0 / 200000.0
TIER_A = "A_STRICT_SEMANTIC_DIRECTION"
TIER_B = "B_DIRECTION_GEOMETRY"
TARGET_HW = {"secondary", "tertiary"}
RADII_M = [20.0, 50.0, 100.0]
PARALLEL_MAX_DEG = 30.0
TWIN_MIN_DEG = 150.0

MIN_TARGET_TOTAL = 100
MIN_SECONDARY = 80
MIN_TERTIARY = 15
MIN_CAND_COVERAGE = 0.95
MIN_COORD_COVERAGE = 0.99
MIN_DIRECTION_COVERAGE = 0.95
MIN_NEIGHBOR_COVERAGE = 0.95


def sha256_file(p: Path, chunk: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for b in iter(lambda: f.read(chunk), b""):
            h.update(b)
    return h.hexdigest()


def norm_id(x: object) -> str:
    s = "" if x is None else str(x).strip()
    if not s or s.lower() == "nan":
        return ""
    return s[:-2] if s.endswith(".0") and s[:-2].isdigit() else s


def norm_text(x: object) -> str:
    s = "" if x is None else str(x).replace("\xa0", " ").strip()
    return "" if s.lower() == "nan" else " ".join(s.split())


def norm_name(x: object) -> str:
    s = norm_text(x).upper()
    if not s:
        return ""
    s = s.replace("&", " AND ")
    s = re.sub(r"[-_/(),.&]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def numeric(s: pd.Series) -> pd.Series:
    return pd.to_numeric(s.astype(str).str.replace(",", "", regex=False), errors="coerce")


def safe_ratio(a: float, b: float) -> float:
    return float(a / b) if np.isfinite(a) and np.isfinite(b) and b != 0 else np.nan


def weighted_mean(y: pd.Series, w: pd.Series) -> float:
    z = pd.concat([pd.to_numeric(y, errors="coerce"), pd.to_numeric(w, errors="coerce")], axis=1).dropna()
    if z.empty or float(z.iloc[:, 1].sum()) <= 0:
        return np.nan
    return float((z.iloc[:, 0] * z.iloc[:, 1]).sum() / z.iloc[:, 1].sum())


def spearman(x: pd.Series, y: pd.Series) -> float:
    z = pd.concat([pd.to_numeric(x, errors="coerce"), pd.to_numeric(y, errors="coerce")], axis=1).dropna()
    if len(z) < 4:
        return np.nan
    return float(z.iloc[:, 0].corr(z.iloc[:, 1], method="spearman"))


def angle_diff(a: float, b: float) -> float:
    if not np.isfinite(a) or not np.isfinite(b):
        return np.nan
    d = abs(a - b) % 360.0
    return min(d, 360.0 - d)


def bearing_deg(dx: float, dy: float) -> float:
    if not np.isfinite(dx) or not np.isfinite(dy):
        return np.nan
    a = math.degrees(math.atan2(dx, dy))
    return a if a >= 0 else a + 360.0


def zero_sim_audit(path: Path) -> bool:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    banned_mods = {"subprocess", "jpype", "py4j"}
    banned_calls = {"system", "popen", "Popen", "run", "call", "check_call", "check_output"}
    for n in ast.walk(tree):
        if isinstance(n, ast.Import) and any(a.name.split(".")[0] in banned_mods for a in n.names):
            return False
        if isinstance(n, ast.ImportFrom) and n.module and n.module.split(".")[0] in banned_mods:
            return False
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr in banned_calls:
            return False
    return True


def locate_w01(root: Path, explicit: Path | None) -> Path:
    p = explicit if explicit else root / W01_REL
    if not p.is_absolute():
        p = root / p
    if p.is_file():
        return p
    if p.is_dir():
        fs = sorted(p.glob("*.linkstats.txt.gz")) + sorted(p.glob("*.linkstats.txt"))
        if fs:
            return fs[0]
    raise FileNotFoundError(f"W01 linkstats not found: {p}")


def load_traffic_json(path: Path) -> pd.DataFrame:
    obj = json.loads(path.read_text(encoding="utf-8-sig"))
    rows = obj.get("Value", obj.get("value", [])) if isinstance(obj, dict) else obj
    d = pd.DataFrame(rows)
    req = {"LinkID", "Date", "HourOfDate", "Volume", "RoadName", "RoadCat"}
    miss = req - set(d.columns)
    if miss:
        raise ValueError(f"TrafficFlow JSON 缺字段: {sorted(miss)}")
    d["LinkID"] = d["LinkID"].map(norm_id)
    d["Date"] = pd.to_datetime(d["Date"], dayfirst=True, errors="coerce")
    d["HourOfDate"] = pd.to_numeric(d["HourOfDate"], errors="coerce")
    d["Volume"] = numeric(d["Volume"])
    d["RoadName"] = d["RoadName"].map(norm_text)
    d["RoadCat"] = d["RoadCat"].map(norm_text)
    d = d[
        d["LinkID"].ne("") & d["Date"].notna() & d["Date"].dt.weekday.lt(5)
        & d["HourOfDate"].eq(8) & d["Volume"].notna()
    ].copy()
    daily = d.groupby(["LinkID", "Date"], as_index=False)["Volume"].mean()
    obs = daily.groupby("LinkID", as_index=False)["Volume"].median().rename(columns={"Volume": "obs_8_9"})
    attrs = d.sort_values(["LinkID", "Date"]).groupby("LinkID", as_index=False).agg(
        RoadName=("RoadName", "first"), RoadCat=("RoadCat", "first")
    )
    return obs.merge(attrs, on="LinkID", how="left", validate="one_to_one")


def load_traffic_geometry(path: Path) -> pd.DataFrame:
    try:
        import geopandas as gpd
    except ImportError as e:
        raise RuntimeError("F-2 需要 geopandas 读取 TrafficFlow_Links.shp") from e
    g = gpd.read_file(path, encoding="latin-1")
    req = {"LinkID", "geometry"}
    miss = req - set(g.columns)
    if miss:
        raise ValueError(f"TrafficFlow_Links.shp 缺字段: {sorted(miss)}")
    g["LinkID"] = g["LinkID"].map(norm_id)
    if g.crs is None:
        g = g.set_crs("EPSG:4326", allow_override=True)
    g = g.to_crs("EPSG:3414")

    def geom_heading(geom):
        try:
            if geom is None or geom.is_empty:
                return np.nan
            if geom.geom_type == "MultiLineString":
                parts = list(geom.geoms)
                if not parts:
                    return np.nan
                geom = parts[0]
            coords = list(geom.coords)
            if len(coords) < 2:
                return np.nan
            (x0, y0), (x1, y1) = coords[0], coords[-1]
            return bearing_deg(x1 - x0, y1 - y0)
        except Exception:
            return np.nan

    g["lta_heading_deg"] = g["geometry"].map(geom_heading)
    out = g[["LinkID", "lta_heading_deg"]].copy()
    if out["LinkID"].duplicated().any():
        raise ValueError("TrafficFlow_Links.shp 存在重复 LinkID")
    return out


def load_candidates(path: Path) -> pd.DataFrame:
    x = pd.read_csv(path, encoding="utf-8-sig", low_memory=False)
    low = {str(c).strip().lower(): c for c in x.columns}
    mp = {
        "lta_linkid": "lta_linkid", "linkid": "lta_linkid",
        "matsim_link_id": "matsim_link_id", "matsim_link": "matsim_link_id",
        "tier": "tier", "distance_m": "distance_m", "geometry_distance_m": "distance_m",
        "direction_diff_deg": "direction_diff_deg", "direction_diff": "direction_diff_deg",
        "highway": "highway", "semantic_compatible": "semantic_compatible",
        "semantic_ok": "semantic_compatible", "name_similarity": "name_similarity",
        "name_sim": "name_similarity",
    }
    x = x.rename(columns={c: mp[k] for k, c in low.items() if k in mp})
    req = {"lta_linkid", "matsim_link_id", "tier", "distance_m", "direction_diff_deg", "highway"}
    miss = req - set(x.columns)
    if miss:
        raise ValueError(f"E1 candidates 缺字段: {sorted(miss)}")
    x["lta_linkid"] = x["lta_linkid"].map(norm_id)
    x["matsim_link_id"] = x["matsim_link_id"].map(norm_id)
    x["tier"] = x["tier"].map(norm_text)
    x["highway"] = x["highway"].map(norm_text).str.lower()
    x["distance_m"] = numeric(x["distance_m"])
    x["direction_diff_deg"] = numeric(x["direction_diff_deg"])
    if "semantic_compatible" in x:
        x["semantic_compatible"] = x["semantic_compatible"].astype(str).str.lower().isin(["true", "1", "yes"])
    else:
        x["semantic_compatible"] = False
    if "name_similarity" in x:
        x["name_similarity"] = numeric(x["name_similarity"])
    else:
        x["name_similarity"] = 0.0
    x = x[
        x["lta_linkid"].ne("") & x["matsim_link_id"].ne("")
        & x["tier"].isin([TIER_A, TIER_B]) & x["distance_m"].notna()
    ].copy()
    return x.drop_duplicates(["lta_linkid", "matsim_link_id", "tier"])


def select_links(c: pd.DataFrame) -> pd.DataFrame:
    parts = []
    for sid, g0 in c.groupby("lta_linkid", sort=True):
        a = g0[g0["tier"].eq(TIER_A)]
        g = a if not a.empty else g0[g0["tier"].eq(TIER_B)]
        if g.empty:
            continue
        g = g.sort_values(
            ["distance_m", "direction_diff_deg", "semantic_compatible", "name_similarity", "matsim_link_id"],
            ascending=[True, True, False, False, True],
        ).drop_duplicates("matsim_link_id")
        parts.append(g.copy())
    return pd.concat(parts, ignore_index=True) if parts else pd.DataFrame(columns=c.columns)


def load_e2(path: Path) -> pd.DataFrame:
    d = pd.read_csv(path, encoding="utf-8-sig", low_memory=False)
    req = {"LinkID", "obs_8_9", "diagnostic_residual_8_9", "diagnostic_highway", "valid_residual"}
    miss = req - set(d.columns)
    if miss:
        raise ValueError(f"E2 main 缺字段: {sorted(miss)}")
    d["LinkID"] = d["LinkID"].map(norm_id)
    d["obs_8_9"] = numeric(d["obs_8_9"])
    d["diagnostic_residual_8_9"] = numeric(d["diagnostic_residual_8_9"])
    d["diagnostic_highway"] = d["diagnostic_highway"].map(norm_text).str.lower()
    d["valid_residual"] = d["valid_residual"].astype(str).str.lower().isin(["true", "1", "yes"])
    return d


def load_network(path: Path, nodes_path: Path) -> pd.DataFrame:
    net = pd.read_csv(path, usecols=["from_node", "to_node", "length_m", "highway", "name"], encoding="utf-8-sig", low_memory=False)
    nodes = pd.read_csv(nodes_path, low_memory=False)
    low = {str(c).strip().lower(): c for c in nodes.columns}
    id_col = next((low[k] for k in ["node_id", "id", "node"] if k in low), None)
    x_col = next((low[k] for k in ["x", "x_svy21_m", "easting"] if k in low), None)
    y_col = next((low[k] for k in ["y", "y_svy21_m", "northing"] if k in low), None)
    if not id_col or not x_col or not y_col:
        raise ValueError("network_nodes_source_copy.csv 无法识别 node/x/y 字段")
    nodes = nodes[[id_col, x_col, y_col]].copy()
    nodes.columns = ["node_id", "x", "y"]
    nodes["node_id"] = nodes["node_id"].map(norm_id)
    nodes["x"] = numeric(nodes["x"])
    nodes["y"] = numeric(nodes["y"])
    nodes = nodes.dropna(subset=["node_id", "x", "y"])
    if nodes["node_id"].duplicated().any():
        raise ValueError("network nodes 存在重复 node_id")
    net["from_node"] = net["from_node"].map(norm_id)
    net["to_node"] = net["to_node"].map(norm_id)
    net["matsim_link_id"] = "e" + net["from_node"] + "_" + net["to_node"]
    net["highway"] = net["highway"].map(norm_text).str.lower()
    net["name_norm"] = net["name"].map(norm_name)
    net["length_m"] = numeric(net["length_m"])
    if net["matsim_link_id"].duplicated().any():
        raise ValueError("network 出现重复 MATSim link id")
    nx = nodes.set_index("node_id")[["x", "y"]]
    net = net.join(nx.rename(columns={"x": "from_x", "y": "from_y"}), on="from_node")
    net = net.join(nx.rename(columns={"x": "to_x", "y": "to_y"}), on="to_node")
    net = net[
        net["from_x"].notna() & net["from_y"].notna()
        & net["to_x"].notna() & net["to_y"].notna()
    ].copy()
    net["mid_x"] = (net["from_x"] + net["to_x"]) / 2.0
    net["mid_y"] = (net["from_y"] + net["to_y"]) / 2.0
    net["heading_deg"] = [
        bearing_deg(dx, dy)
        for dx, dy in zip(net["to_x"] - net["from_x"], net["to_y"] - net["from_y"])
    ]
    return net[
        ["matsim_link_id", "from_node", "to_node", "length_m", "highway", "name", "name_norm",
         "from_x", "from_y", "to_x", "to_y", "mid_x", "mid_y", "heading_deg"]
    ].copy()


def load_w01(path: Path) -> pd.DataFrame:
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", encoding="utf-8", errors="replace") as f:
        header = f.readline().rstrip("\n").split("\t")
    req = {"LINK", "HRS8-9avg"}
    miss = req - set(header)
    if miss:
        raise ValueError(f"W01 linkstats 缺字段: {sorted(miss)}")
    d = pd.read_csv(path, sep="\t", compression="gzip" if path.suffix == ".gz" else None,
                    usecols=["LINK", "HRS8-9avg"], low_memory=False)
    d["LINK"] = d["LINK"].map(norm_id)
    d["HRS8-9avg"] = numeric(d["HRS8-9avg"])
    if d["LINK"].duplicated().any():
        raise ValueError("W01 LINK 出现重复")
    return d


def candidate_structure(target: pd.DataFrame, selected_flow: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for sid, g in selected_flow.groupby("lta_linkid", sort=True):
        e2 = target[target["LinkID"].eq(sid)]
        if e2.empty:
            continue
        d = numeric(g["distance_m"]).dropna()
        dd = numeric(g["direction_diff_deg"]).dropna()
        a = g[g["tier"].eq(TIER_A)]
        b = g[g["tier"].eq(TIER_B)]
        hws = sorted(set(g["highway"].dropna().astype(str)))
        rep = g.sort_values(
            ["distance_m", "direction_diff_deg", "semantic_compatible", "name_similarity", "matsim_link_id"],
            ascending=[True, True, False, False, True],
        ).iloc[0]
        flow = numeric(g["HRS8-9avg"]).dropna()
        obs = float(e2["obs_8_9"].iloc[0])
        scaled = float(flow.sum() * SCALE) if len(flow) else np.nan
        ratio = safe_ratio(scaled, obs)
        rows.append({
            "LinkID": sid,
            "diagnostic_highway": e2["diagnostic_highway"].iloc[0],
            "diagnostic_residual_8_9": float(e2["diagnostic_residual_8_9"].iloc[0]),
            "obs_8_9": obs,
            "selected_total_n": int(g["matsim_link_id"].nunique()),
            "selected_A_n": int(a["matsim_link_id"].nunique()),
            "selected_B_n": int(b["matsim_link_id"].nunique()),
            "selected_highway_n": int(len(hws)),
            "selected_distance_min_m": float(d.min()) if len(d) else np.nan,
            "selected_distance_median_m": float(d.median()) if len(d) else np.nan,
            "selected_direction_min_deg": float(dd.min()) if len(dd) else np.nan,
            "selected_direction_median_deg": float(dd.median()) if len(dd) else np.nan,
            "selected_direction_max_deg": float(dd.max()) if len(dd) else np.nan,
            "selected_direction_good_share": float((dd <= 30).mean()) if len(dd) else np.nan,
            "selected_direction_twin_share": float((dd >= 150).mean()) if len(dd) else np.nan,
            "same_highway_share": float((g["highway"] == rep["highway"]).mean()) if len(g) else np.nan,
            "matched_flow_raw_sum": float(flow.sum()) if len(flow) else np.nan,
            "matched_flow_scaled_sum": scaled,
            "matched_ratio_sum": ratio,
            "matched_sum_residual": ratio - 1.0 if np.isfinite(ratio) else np.nan,
            "representative_matsim_link_id": rep["matsim_link_id"],
            "representative_highway": rep["highway"],
        })
    return pd.DataFrame(rows)


def direction_diagnostics(target: pd.DataFrame, selected: pd.DataFrame,
                          traffic_geom: pd.DataFrame, network: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    net = network.set_index("matsim_link_id")
    tg = traffic_geom.set_index("LinkID")
    rows = []
    for sid, g in selected.groupby("lta_linkid", sort=True):
        if sid not in tg.index:
            continue
        lta_heading = float(tg.loc[sid, "lta_heading_deg"])
        for _, r in g.iterrows():
            mid = r["matsim_link_id"]
            if mid not in net.index:
                continue
            mheading = float(net.loc[mid, "heading_deg"])
            recomputed = angle_diff(lta_heading, mheading)
            e1diff = float(r["direction_diff_deg"]) if np.isfinite(r["direction_diff_deg"]) else np.nan
            rows.append({
                "LinkID": sid,
                "matsim_link_id": mid,
                "lta_heading_deg": lta_heading,
                "matsim_heading_deg": mheading,
                "direction_diff_recomputed_deg": recomputed,
                "direction_diff_e1_deg": e1diff,
                "direction_diff_abs_delta_deg": abs(recomputed - e1diff) if np.isfinite(recomputed) and np.isfinite(e1diff) else np.nan,
                "direction_good_recomputed": bool(recomputed <= 30) if np.isfinite(recomputed) else False,
                "direction_twin_recomputed": bool(recomputed >= 150) if np.isfinite(recomputed) else False,
            })
    long = pd.DataFrame(rows)
    out = []
    for sid, g in long.groupby("LinkID", sort=True):
        e2 = target[target["LinkID"].eq(sid)].iloc[0]
        dd = numeric(g["direction_diff_recomputed_deg"]).dropna()
        de = numeric(g["direction_diff_e1_deg"]).dropna()
        out.append({
            "LinkID": sid,
            "diagnostic_highway": e2["diagnostic_highway"],
            "diagnostic_residual_8_9": e2["diagnostic_residual_8_9"],
            "selected_direction_n_recomputed": int(len(dd)),
            "lta_heading_deg": float(g["lta_heading_deg"].iloc[0]),
            "direction_min_recomputed_deg": float(dd.min()) if len(dd) else np.nan,
            "direction_median_recomputed_deg": float(dd.median()) if len(dd) else np.nan,
            "direction_max_recomputed_deg": float(dd.max()) if len(dd) else np.nan,
            "direction_good_share_recomputed": float((dd <= 30).mean()) if len(dd) else np.nan,
            "direction_twin_share_recomputed": float((dd >= 150).mean()) if len(dd) else np.nan,
            "e1_direction_n": int(len(de)),
            "e1_vs_recomputed_max_abs_delta_deg": float(g["direction_diff_abs_delta_deg"].max()) if g["direction_diff_abs_delta_deg"].notna().any() else np.nan,
        })
    return long, pd.DataFrame(out)


def local_neighbors(target: pd.DataFrame, selected: pd.DataFrame,
                    structure: pd.DataFrame, network: pd.DataFrame, stats: pd.DataFrame) -> pd.DataFrame:
    try:
        from scipy.spatial import cKDTree
    except ImportError as e:
        raise RuntimeError("F-2 需要 scipy.spatial.cKDTree") from e
    net = network.reset_index(drop=True)
    tree = cKDTree(net[["mid_x", "mid_y"]].to_numpy(dtype=float))
    flow_map = stats.set_index("LINK")["HRS8-9avg"].to_dict()
    selected_sets = selected.groupby("lta_linkid")["matsim_link_id"].apply(set).to_dict()
    rows = []
    for sid, mids in selected_sets.items():
        srow = structure[structure["LinkID"].eq(sid)]
        if srow.empty:
            continue
        focal = net[net["matsim_link_id"].isin(mids)]
        if focal.empty:
            continue
        obs = float(srow["obs_8_9"].iloc[0])
        matched_scaled = float(srow["matched_flow_scaled_sum"].iloc[0])
        focal_names = {x for x in focal["name_norm"].astype(str) if x}
        focal_hws = {x for x in focal["highway"].astype(str) if x}
        for radius in RADII_M:
            idxs = set()
            for _, fr in focal.iterrows():
                idxs.update(tree.query_ball_point([float(fr["mid_x"]), float(fr["mid_y"])], radius))
            parallel_ids, twin_ids = set(), set()
            same_name_parallel_ids, same_name_twin_ids = set(), set()
            dist_map = {}
            type_map = {}
            for idx in idxs:
                nr = net.iloc[idx]
                nid = nr["matsim_link_id"]
                if nid in mids:
                    continue
                best_d = min(
                    math.hypot(float(nr["mid_x"]) - float(fr["mid_x"]), float(nr["mid_y"]) - float(fr["mid_y"]))
                    for _, fr in focal.iterrows()
                )
                if best_d > radius:
                    continue
                nd = np.nanmin([
                    angle_diff(float(nr["heading_deg"]), float(fr["heading_deg"]))
                    for _, fr in focal.iterrows()
                ])
                if not np.isfinite(nd):
                    continue
                is_parallel = nd <= PARALLEL_MAX_DEG
                is_twin = nd >= TWIN_MIN_DEG
                same_name = bool(nr["name_norm"] and nr["name_norm"] in focal_names)
                if is_parallel:
                    parallel_ids.add(nid)
                    if same_name:
                        same_name_parallel_ids.add(nid)
                if is_twin:
                    twin_ids.add(nid)
                    if same_name:
                        same_name_twin_ids.add(nid)
                dist_map[nid] = best_d
                type_map[nid] = "parallel" if is_parallel else ("twin" if is_twin else "other")
            def flow_sum(ids):
                vals = [flow_map.get(nid, np.nan) for nid in ids]
                vals = [float(v) for v in vals if np.isfinite(v)]
                return float(sum(vals)), int(sum(v > 0 for v in vals))
            sets = [
                ("parallel", parallel_ids), ("twin", twin_ids),
                ("same_name_parallel", same_name_parallel_ids),
                ("same_name_twin", same_name_twin_ids),
            ]
            all_ids = parallel_ids | twin_ids
            all_flow, all_pos = flow_sum(all_ids)
            for typ, ids in sets:
                f, pos = flow_sum(ids)
                rows.append({
                    "LinkID": sid,
                    "diagnostic_highway": srow["diagnostic_highway"].iloc[0],
                    "diagnostic_residual_8_9": srow["diagnostic_residual_8_9"].iloc[0],
                    "obs_8_9": obs,
                    "radius_m": radius,
                    "neighbor_type": typ,
                    "neighbor_n": int(len(ids)),
                    "neighbor_positive_flow_n": int(pos),
                    "neighbor_flow_raw": f,
                    "neighbor_flow_scaled": f * SCALE,
                    "neighbor_flow_share_obs": safe_ratio(f * SCALE, obs),
                })
            matched_ratio = safe_ratio(matched_scaled, obs)
            rows.append({
                "LinkID": sid,
                "diagnostic_highway": srow["diagnostic_highway"].iloc[0],
                "diagnostic_residual_8_9": srow["diagnostic_residual_8_9"].iloc[0],
                "obs_8_9": obs,
                "radius_m": radius,
                "neighbor_type": "ALL_DIRECTION_ENVELOPE",
                "neighbor_n": int(len(all_ids)),
                "neighbor_positive_flow_n": int(all_pos),
                "neighbor_flow_raw": all_flow,
                "neighbor_flow_scaled": all_flow * SCALE,
                "neighbor_flow_share_obs": safe_ratio(all_flow * SCALE, obs),
                "matched_flow_scaled": matched_scaled,
                "matched_ratio_sum": matched_ratio,
                "envelope_ratio": safe_ratio(matched_scaled + all_flow * SCALE, obs),
                "envelope_abs_residual_change": abs(safe_ratio(matched_scaled + all_flow * SCALE, obs) - 1.0) - abs(matched_ratio - 1.0) if np.isfinite(matched_ratio) else np.nan,
            })
    return pd.DataFrame(rows)


def build_summary(structure: pd.DataFrame, direction: pd.DataFrame, neighbors: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for hw in ["secondary", "tertiary"]:
        s = structure[structure["diagnostic_highway"].eq(hw)]
        d = direction[direction["diagnostic_highway"].eq(hw)]
        n = neighbors[neighbors["diagnostic_highway"].eq(hw)]
        z = n[n["neighbor_type"].eq("ALL_DIRECTION_ENVELOPE")]
        rows.append({
            "diagnostic_highway": hw,
            "n": int(len(s)),
            "mean_frozen_residual": float(s["diagnostic_residual_8_9"].mean()),
            "median_frozen_residual": float(s["diagnostic_residual_8_9"].median()),
            "median_matched_sum_ratio": float(s["matched_ratio_sum"].median()),
            "median_direction_deg": float(d["direction_median_recomputed_deg"].median()) if len(d) else np.nan,
            "median_direction_good_share": float(d["direction_good_share_recomputed"].median()) if len(d) else np.nan,
            "positive_parallel_100m_share": float((n[n["radius_m"].eq(100.0) & n["neighbor_type"].eq("parallel")]["neighbor_positive_flow_n"] > 0).mean())
            if len(n[n["radius_m"].eq(100.0) & n["neighbor_type"].eq("parallel")]) else np.nan,
            "positive_twin_100m_share": float((n[n["radius_m"].eq(100.0) & n["neighbor_type"].eq("twin")]["neighbor_positive_flow_n"] > 0).mean())
            if len(n[n["radius_m"].eq(100.0) & n["neighbor_type"].eq("twin")]) else np.nan,
            "median_all_direction_added_share_100m": float(z[z["radius_m"].eq(100.0)]["neighbor_flow_share_obs"].median()) if len(z[z["radius_m"].eq(100.0)]) else np.nan,
        })
    return pd.DataFrame(rows)


def mechanism_summary(structure: pd.DataFrame, direction: pd.DataFrame, neighbors: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for metric in [
        "selected_total_n", "selected_distance_median_m", "selected_direction_median_deg",
        "selected_direction_good_share", "selected_direction_twin_share", "same_highway_share",
    ]:
        rows.append({
            "family": "MATCHING_STRUCTURE",
            "metric": metric,
            "spearman_with_frozen_residual": spearman(structure[metric], structure["diagnostic_residual_8_9"]),
        })
    for metric in [
        "direction_median_recomputed_deg", "direction_good_share_recomputed", "direction_twin_share_recomputed",
    ]:
        rows.append({
            "family": "DIRECTIONALITY",
            "metric": metric,
            "spearman_with_frozen_residual": spearman(direction[metric], direction["diagnostic_residual_8_9"]),
        })
    for radius in RADII_M:
        z = neighbors[(neighbors["radius_m"].eq(radius)) & (~neighbors["neighbor_type"].eq("ALL_DIRECTION_ENVELOPE"))]
        if z.empty:
            continue
        # Aggregate section-level neighbor flow by type before correlating with the frozen residual.
        wide = z.pivot_table(index="LinkID", columns="neighbor_type", values="neighbor_flow_share_obs", aggfunc="first").reset_index()
        rr = structure[["LinkID", "diagnostic_residual_8_9"]].drop_duplicates().merge(wide, on="LinkID", how="left")
        for metric in ["parallel", "twin", "same_name_parallel", "same_name_twin"]:
            if metric in rr.columns:
                rows.append({
                    "family": "LOCAL_FLOW_ENVELOPE",
                    "metric": f"{metric}_added_share@{int(radius)}m",
                    "spearman_with_frozen_residual": spearman(rr[metric], rr["diagnostic_residual_8_9"]),
                })
        allz = neighbors[(neighbors["radius_m"].eq(radius)) & (neighbors["neighbor_type"].eq("ALL_DIRECTION_ENVELOPE"))]
        rows.append({
            "family": "LOCAL_FLOW_ENVELOPE",
            "metric": f"all_direction_envelope_abs_residual_change@{int(radius)}m",
            "spearman_with_frozen_residual": spearman(allz["envelope_abs_residual_change"], allz["diagnostic_residual_8_9"]),
        })
    return pd.DataFrame(rows)


def provenance(paths: dict[str, Path]) -> dict:
    out = {}
    for k, p in paths.items():
        st = p.stat()
        out[k] = {"path": str(p), "sha256": sha256_file(p), "size_bytes": int(st.st_size), "mtime_ns": int(st.st_mtime_ns)}
    return out


def build_checks(script: Path, prereg: Path, traffic: pd.DataFrame, traffic_geom: pd.DataFrame,
                 cand: pd.DataFrame, e2: pd.DataFrame, network: pd.DataFrame, selected: pd.DataFrame,
                 target: pd.DataFrame, direction: pd.DataFrame, neighbors: pd.DataFrame,
                 stats: pd.DataFrame, out: Path) -> list[dict]:
    target_n = len(target)
    cand_cov = safe_ratio(target["LinkID"].isin(set(selected["lta_linkid"])).sum(), target_n)
    coord_cov = safe_ratio(selected["matsim_link_id"].isin(set(network["matsim_link_id"])).sum(), len(selected))
    dir_ids = set(direction["LinkID"])
    direction_cov = safe_ratio(len(dir_ids), target_n)
    expected_rows = len(target) * len(RADII_M) * 5
    neighbor_n = neighbors.groupby("LinkID").size()
    neighbor_cov = safe_ratio(int((neighbor_n >= len(RADII_M) * 5).sum()), target_n)
    counts = target["diagnostic_highway"].value_counts()
    declared = [
        "f2_target_sections.csv", "f2_selected_candidates.csv", "f2_candidate_structure.csv",
        "f2_direction_diagnostics.csv", "f2_local_neighbors.csv", "f2_mechanism_summary.csv",
        "f2_group_summary.csv", "f2_checks.csv", "f2_input_manifest.json", "f2_summary.json",
        "STEP7_9F2_REPORT.md",
    ]
    base_outputs_exist = all(
        (out / f).exists() and (out / f).parent.resolve() == out.resolve()
        for f in declared
    )
    return [
        {"check": "F2.01_PREREG_HASH", "pass": sha256_file(prereg).lower() == EXPECTED_PREREG_SHA256.lower(), "detail": sha256_file(prereg)},
        {"check": "F2.02_ZERO_SIMULATION", "pass": zero_sim_audit(script), "detail": "AST no Java/subprocess execution"},
        {"check": "F2.03_TRAFFIC_INPUTS", "pass": traffic["LinkID"].nunique() >= 1278 and traffic_geom["LinkID"].nunique() >= 1278, "detail": f"traffic_json={traffic['LinkID'].nunique()}; geometry={traffic_geom['LinkID'].nunique()}"},
        {"check": "F2.04_E1_CANDIDATES", "pass": len(cand) > 0, "detail": f"candidate_rows={len(cand):,}"},
        {"check": "F2.05_E2_TARGET_FIELDS", "pass": {"LinkID","obs_8_9","diagnostic_residual_8_9","diagnostic_highway","valid_residual"}.issubset(e2.columns), "detail": f"e2_rows={len(e2):,}"},
        {"check": "F2.06_NETWORK_FIELDS_AND_COORDS", "pass": len(network) > 0, "detail": f"network_links_with_coords={len(network):,}"},
        {"check": "F2.07_W01_LINKSTATS", "pass": len(stats) > 0 and not stats["LINK"].duplicated().any(), "detail": f"w01_links={len(stats):,}"},
        {"check": "F2.08_TARGET_TOTAL_GE100", "pass": target_n >= MIN_TARGET_TOTAL, "detail": f"target_n={target_n}"},
        {"check": "F2.09_SECONDARY_GE80", "pass": int(counts.get("secondary", 0)) >= MIN_SECONDARY, "detail": f"secondary={int(counts.get('secondary',0))}"},
        {"check": "F2.10_TERTIARY_GE15", "pass": int(counts.get("tertiary", 0)) >= MIN_TERTIARY, "detail": f"tertiary={int(counts.get('tertiary',0))}"},
        {"check": "F2.11_SELECTED_COVERAGE_GE95", "pass": np.isfinite(cand_cov) and cand_cov >= MIN_CAND_COVERAGE, "detail": f"coverage={cand_cov:.6f}"},
        {"check": "F2.12_SELECTED_NETWORK_COORD_GE99", "pass": np.isfinite(coord_cov) and coord_cov >= MIN_COORD_COVERAGE, "detail": f"coverage={coord_cov:.6f}"},
        {"check": "F2.13_DIRECTION_RECOMPUTED_GE95", "pass": np.isfinite(direction_cov) and direction_cov >= MIN_DIRECTION_COVERAGE, "detail": f"coverage={direction_cov:.6f}"},
        {"check": "F2.14_NEIGHBOR_DIAGNOSTICS_GE95", "pass": np.isfinite(neighbor_cov) and neighbor_cov >= MIN_NEIGHBOR_COVERAGE and len(neighbors) >= expected_rows * 0.95, "detail": f"section_coverage={neighbor_cov:.6f}; rows={len(neighbors)}; expected={expected_rows}"},
        {"check": "F2.15_OUTPUT_PROVENANCE", "pass": base_outputs_exist and out.name == OUT_REL.name, "detail": f"output_dir={out}; declared_outputs_exist={base_outputs_exist}"},
    ]


def write_report(out: Path, target: pd.DataFrame, mechanism: pd.DataFrame,
                 groups: pd.DataFrame, neighbors: pd.DataFrame, checks_rows: list[dict], status: str) -> None:
    lines = [
        "# Step 7.9F-2 — Secondary/Tertiary Residual Mechanism Audit", "",
        f"**STATUS: {status}**", "",
        "零仿真、只读、diagnostic-only。", "",
        "## Domain", "",
        f"- target valid sections: **{len(target):,}**",
        f"- secondary: **{int((target['diagnostic_highway'] == 'secondary').sum())}**",
        f"- tertiary: **{int((target['diagnostic_highway'] == 'tertiary').sum())}**", "",
        "## Group summary", "",
        "| Highway | n | Mean frozen residual | Median frozen residual | Median matched-sum ratio | Median direction (deg) | Positive parallel flow @100m | Positive twin flow @100m |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for _, r in groups.iterrows():
        lines.append(
            f"| {r['diagnostic_highway']} | {int(r['n'])} | {r['mean_frozen_residual']:.4f} | {r['median_frozen_residual']:.4f} | {r['median_matched_sum_ratio']:.4f} | {r['median_direction_deg']:.2f} | {r['positive_parallel_100m_share']:.2%} | {r['positive_twin_100m_share']:.2%} |"
        )
    lines += ["", "## Local flow envelope", "",
              "| Radius | Mean matched ratio | Median matched ratio | Mean all-direction envelope | Median all-direction envelope |",
              "|---:|---:|---:|---:|---:|"]
    for radius in RADII_M:
        z = neighbors[neighbors["radius_m"].eq(radius)]
        z = z[z["neighbor_type"].eq("ALL_DIRECTION_ENVELOPE")]
        lines.append(f"| {int(radius)} | {z['matched_ratio_sum'].mean():.4f} | {z['matched_ratio_sum'].median():.4f} | {z['envelope_ratio'].mean():.4f} | {z['envelope_ratio'].median():.4f} |")
    lines += ["", "## Prespecified correlations", "", "| Family | Metric | Spearman with frozen residual |", "|---|---|---:|"]
    for _, r in mechanism.iterrows():
        lines.append(f"| {r['family']} | {r['metric']} | {r['spearman_with_frozen_residual']:.4f} |")
    lines += ["", "## Gates", "", "| Check | Result | Detail |", "|---|---|---|"]
    for c in checks_rows:
        lines.append(f"| {c['check']} | {'PASS' if c['pass'] else 'FAIL'} | {c['detail']} |")
    lines += ["", "## Boundary", "",
              "local flow envelope 是 diagnostic proxy，不是 observed network flow conservation 证明；任何数值改善均不得回写 E2、7.3.6A、v1.0 或 MATSim network。", ""]
    (out / "STEP7_9F2_REPORT.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project-root", type=Path, default=ROOT_DEFAULT)
    ap.add_argument("--traffic", type=Path, default=None)
    ap.add_argument("--traffic-geometry", type=Path, default=None)
    ap.add_argument("--e1-candidates", type=Path, default=None)
    ap.add_argument("--e2", type=Path, default=None)
    ap.add_argument("--network", type=Path, default=None)
    ap.add_argument("--nodes", type=Path, default=None)
    ap.add_argument("--w01-linkstats", type=Path, default=None)
    ap.add_argument("--prereg", type=Path, default=None)
    ap.add_argument("--out-dir", type=Path, default=OUT_REL)
    args = ap.parse_args()

    root = args.project_root
    tp = args.traffic or root / TRAFFIC_REL
    gp = args.traffic_geometry or root / TRAFFIC_GEOM_REL
    cp = args.e1_candidates or root / E1_REL
    ep = args.e2 or root / E2_REL
    npth = args.network or root / NETWORK_REL
    npath = args.nodes or root / NODES_REL
    wp = locate_w01(root, args.w01_linkstats)
    pp = args.prereg if args.prereg else root / PREREG_REL
    out = args.out_dir if args.out_dir.is_absolute() else root / args.out_dir
    out.mkdir(parents=True, exist_ok=True)
    for p in [tp, gp, cp, ep, npth, npath, wp, pp]:
        if not p.exists():
            raise FileNotFoundError(f"输入不存在: {p}")

    print("=" * 92)
    print("STEP 7.9F-2 | SECONDARY/TERTIARY RESIDUAL MECHANISM AUDIT")
    print("ZERO SIMULATION / READ-ONLY / DIAGNOSTIC ONLY")
    print("=" * 92)
    print(f"Traffic JSON : {tp}")
    print(f"Traffic geom : {gp}")
    print(f"E1 candidates: {cp}")
    print(f"E2 residual : {ep}")
    print(f"Network     : {npth}")
    print(f"Nodes       : {npath}")
    print(f"W01         : {wp}")
    print(f"Prereg      : {pp}")
    print(f"Prereg SHA  : {sha256_file(pp)}")
    print(f"SCALE       : {SCALE:.8f}")
    print(f"Radii       : {RADII_M} m; parallel <= {PARALLEL_MAX_DEG}°; twin >= {TWIN_MIN_DEG}°")

    traffic = load_traffic_json(tp)
    traffic_geom = load_traffic_geometry(gp)
    cand = load_candidates(cp)
    e2 = load_e2(ep)
    network = load_network(npth, npath)
    stats = load_w01(wp)

    target = e2[
        e2["diagnostic_highway"].isin(TARGET_HW)
        & e2["valid_residual"]
        & e2["obs_8_9"].gt(0)
    ].copy()
    if target["LinkID"].duplicated().any():
        raise ValueError("E2 target LinkID 重复，无法形成唯一目标域")

    selected = select_links(cand)
    selected_target = selected[selected["lta_linkid"].isin(set(target["LinkID"]))].copy()
    selected_flow = selected_target.merge(
        stats, left_on="matsim_link_id", right_on="LINK", how="left", validate="many_to_one"
    )

    structure = candidate_structure(target, selected_flow)
    direction_long, direction = direction_diagnostics(target, selected_target, traffic_geom, network)
    neighbors = local_neighbors(target, selected_target, structure, network, stats)
    mechanism = mechanism_summary(structure, direction, neighbors)
    groups = build_summary(structure, direction, neighbors)

    # Core analytical artifacts, excluding final checks/manifest/report until values are final.
    target.to_csv(out / "f2_target_sections.csv", index=False, encoding="utf-8-sig")
    selected_target.to_csv(out / "f2_selected_candidates.csv", index=False, encoding="utf-8-sig")
    structure.to_csv(out / "f2_candidate_structure.csv", index=False, encoding="utf-8-sig")
    direction.to_csv(out / "f2_direction_diagnostics.csv", index=False, encoding="utf-8-sig")
    direction_long.to_csv(out / "f2_direction_candidate_long.csv", index=False, encoding="utf-8-sig")
    neighbors.to_csv(out / "f2_local_neighbors.csv", index=False, encoding="utf-8-sig")
    mechanism.to_csv(out / "f2_mechanism_summary.csv", index=False, encoding="utf-8-sig")
    groups.to_csv(out / "f2_group_summary.csv", index=False, encoding="utf-8-sig")

    input_paths = {
        "traffic_json": tp, "traffic_geometry": gp, "e1_candidates": cp,
        "e2": ep, "network": npth, "nodes": npath, "w01": wp,
        "prereg": pp, "script": Path(__file__).resolve(),
    }
    manifest = provenance(input_paths)
    manifest["protocol"] = {
        "radii_m": RADII_M,
        "parallel_max_deg": PARALLEL_MAX_DEG,
        "twin_min_deg": TWIN_MIN_DEG,
        "scale": SCALE,
        "selection": "A if available, else B; C excluded",
        "local_distance": "midpoint-to-midpoint in EPSG:3414",
    }
    (out / "f2_input_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    # Provisional final-state artifacts exist before gates; gate 15 checks actual directory isolation.
    provisional_summary = {
        "step": "7.9F-2", "status": "PENDING", "zero_simulation": True,
        "network_modified": False, "matsim_rerun": False,
        "target_n": int(len(target)),
        "secondary_n": int((target["diagnostic_highway"] == "secondary").sum()),
        "tertiary_n": int((target["diagnostic_highway"] == "tertiary").sum()),
        "selected_candidate_rows": int(len(selected_target)),
        "network_links_with_coords": int(len(network)),
        "w01_links": int(len(stats)),
    }
    (out / "f2_summary.json").write_text(json.dumps(provisional_summary, ensure_ascii=False, indent=2), encoding="utf-8")
    write_report(out, target, mechanism, groups, neighbors, [], "PENDING")

    checks_rows = build_checks(
        Path(__file__).resolve(), pp, traffic, traffic_geom, cand, e2,
        network, selected_target, target, direction, neighbors, stats, out
    )
    status = "MECHANISM_AUDIT_READY" if all(bool(c["pass"]) for c in checks_rows) else "MECHANISM_AUDIT_BLOCKED"

    pd.DataFrame(checks_rows).to_csv(out / "f2_checks.csv", index=False, encoding="utf-8-sig")
    final_summary = {
        **provisional_summary,
        "status": status,
        "hard_pass_count": int(sum(bool(c["pass"]) for c in checks_rows)),
        "hard_total": int(len(checks_rows)),
        "prereg_sha256": sha256_file(pp),
        "radii_m": RADII_M,
        "parallel_max_deg": PARALLEL_MAX_DEG,
        "twin_min_deg": TWIN_MIN_DEG,
        "scale": SCALE,
    }
    (out / "f2_summary.json").write_text(json.dumps(final_summary, ensure_ascii=False, indent=2), encoding="utf-8")
    write_report(out, target, mechanism, groups, neighbors, checks_rows, status)

    manifest["generated_artifacts"] = {}
    for p in sorted(out.iterdir()):
        if p.is_file() and p.name != "f2_input_manifest.json":
            manifest["generated_artifacts"][p.name] = {
                "sha256": sha256_file(p), "size_bytes": int(p.stat().st_size)
            }
    (out / "f2_input_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    # Re-write checks after final report/manifest exist; no gate depends on manifest self-hash.
    checks_rows = build_checks(
        Path(__file__).resolve(), pp, traffic, traffic_geom, cand, e2,
        network, selected_target, target, direction, neighbors, stats, out
    )
    pd.DataFrame(checks_rows).to_csv(out / "f2_checks.csv", index=False, encoding="utf-8-sig")
    status = "MECHANISM_AUDIT_READY" if all(bool(c["pass"]) for c in checks_rows) else "MECHANISM_AUDIT_BLOCKED"
    final_summary["status"] = status
    final_summary["hard_pass_count"] = int(sum(bool(c["pass"]) for c in checks_rows))
    (out / "f2_summary.json").write_text(json.dumps(final_summary, ensure_ascii=False, indent=2), encoding="utf-8")
    write_report(out, target, mechanism, groups, neighbors, checks_rows, status)

    print(f"[1/6] target valid sections = {len(target):,}")
    print(f"[2/6] selected candidates  = {len(selected_target):,}")
    print(f"[3/6] network links        = {len(network):,}")
    print(f"[4/6] W01 links            = {len(stats):,}")
    print(f"[5/6] hard gates           = {sum(bool(c['pass']) for c in checks_rows)}/{len(checks_rows)}")
    print(f"[6/6] STATUS               = {status}")
    print(f"      OUTPUT              = {out}")
    print("      NOTE                = no MATSim/Java call")
    return 0 if status == "MECHANISM_AUDIT_READY" else 1


if __name__ == "__main__":
    raise SystemExit(main())
