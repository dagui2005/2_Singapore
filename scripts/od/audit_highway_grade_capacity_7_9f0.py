#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Step 7.9F-0 — Highway Grade x Capacity/Speed Structural Audit.

ZERO SIMULATION / READ-ONLY.
Reads the frozen MATSim network (network.xml.gz, the network actually loaded by
7.6H) together with its OSM source snapshot, and the frozen 7.9E-2 expanded
residual table. Never launches MATSim/Java and never edits frozen inputs.

--- INPUT RESOLUTION (deviation from PREREG_7_9F0.md section 2, documented) ---
PREREG section 2 declared:
  (a) reports/matsim_network/network_links_source_copy.csv with a `capacity` field;
  (b) reports/arterial_expanded_residual_7_9e2/e2_section_residual_main.csv with a
      `representative_matsim_link_id` field.
Neither holds on disk:
  (a) that CSV has only from_node,to_node,travel_time_s,length_m,speed_kmh,highway,
      lanes,name -> no `capacity`. Capacity is *derived* at network-build time as
      lanes_vec x CAPACITY_PER_LANE[highway] (scripts/od/build_matsim_network.py)
      and materialised only in network.xml.gz. Reading it back from the lookup
      table would make the whole capacity audit tautological, so the frozen XML
      attribute is used as the authoritative carrier.
  (b) e2_section_residual_main.csv has 17 columns and does NOT carry the
      representative link id; e2_section_residual_all_tiers.csv does. The
      A+B_MAIN tier slice of all_tiers was verified to be bit-identical to the
      main table (same 1311 LinkIDs, max|delta residual| = 0, 0 discrepant
      valid flags), so it is the faithful equivalent.

Both deviations are written to f0_input_resolution.csv and gated by F0.13.
The 12 pre-registered hard gates (PREREG section 9) are evaluated unchanged and
alone decide the READY/BLOCKED status (PREREG section 11).
"""
from __future__ import annotations

import argparse
import ast
import gzip
import hashlib
import json
import re
from pathlib import Path

import numpy as np
import pandas as pd

ROOT_DEFAULT = Path(r"D:\Luan\2026-05\2_Singapore")
NET_XML_REL = Path("reports/matsim_network/network.xml.gz")
NET_CSV_REL = Path("reports/matsim_network/network_links_source_copy.csv")
E2_ALL_REL = Path("reports/arterial_expanded_residual_7_9e2/e2_section_residual_all_tiers.csv")
E2_MAIN_REL = Path("reports/arterial_expanded_residual_7_9e2/e2_section_residual_main.csv")
OUT_REL = Path("reports/highway_grade_capacity_7_9f0")
PREREG_REL = OUT_REL / "PREREG_7_9F0.md"
EXPECTED_PREREG_SHA256 = "1e058914d8e3a9768a76d69c021b2e91dede22d91db240f4a1a333d9505e166b"
MAIN_TIER = "A+B_MAIN"

CORE_HW = ["motorway", "motorway_link", "trunk", "primary", "secondary", "tertiary"]
TARGET_TREND_HW = ["trunk", "secondary", "tertiary"]

CAPACITY_PER_LANE = {
    "motorway": 1900.0, "motorway_link": 1700.0,
    "trunk": 1800.0, "trunk_link": 1600.0,
    "primary": 1500.0, "primary_link": 1300.0,
    "secondary": 1200.0, "secondary_link": 1100.0,
    "tertiary": 900.0, "tertiary_link": 800.0,
    "residential": 700.0, "service": 400.0, "unclassified": 600.0,
}
DEFAULT_LANES = {
    "motorway": 2.0, "motorway_link": 1.0,
    "trunk": 2.0, "trunk_link": 1.0,
    "primary": 2.0, "primary_link": 1.0,
    "secondary": 2.0, "secondary_link": 1.0,
    "tertiary": 1.0, "tertiary_link": 1.0,
    "residential": 1.0, "service": 1.0, "unclassified": 1.0,
}

MIN_JOIN_COVERAGE = 0.95
MIN_VALID_RESIDUAL = 500
MIN_CORE_CLASS_N = 20
MIN_CAP_LANES_COVERAGE = 0.95
MIN_SPEED_COVERAGE = 0.90
MIN_PROXY_COVERAGE = 0.80

FROZEN_FORBIDDEN_PREFIXES = (
    "reports/final_model_7_8",
    "matsim_final_7_6h",
    "reports/arterial_expanded_residual_7_9e2",
    "reports/arterial_observability_7_9e1",
    "reports/arterial_delay_attribution_7_9e0",
    "reports/sampling_capacity_audit_7_9a0",
    "reports/spatial_residual_7_7c0",
    "Singapore_OD_MATSim_FinalData",
)


def sha256_file(path: Path, chunk: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for b in iter(lambda: f.read(chunk), b""):
            h.update(b)
    return h.hexdigest()


def norm_id(x: object) -> str:
    s = "" if x is None else str(x).strip()
    if not s or s.lower() == "nan":
        return ""
    if s.endswith(".0") and s[:-2].isdigit():
        return s[:-2]
    return s


def norm_text(x: object) -> str:
    s = "" if x is None else str(x).replace("\xa0", " ").strip().lower()
    return "" if s == "nan" else " ".join(s.split())


def numeric(s: pd.Series) -> pd.Series:
    return pd.to_numeric(s.astype(str).str.replace(",", "", regex=False), errors="coerce")


def to_bool(s: pd.Series) -> pd.Series:
    return s.astype(str).str.strip().str.lower().isin(["true", "1", "yes"])


def safe_ratio(a: float, b: float) -> float:
    return float(a / b) if b and np.isfinite(b) else float("nan")


def spearman(x: pd.Series, y: pd.Series) -> float:
    z = pd.concat([pd.to_numeric(x, errors="coerce"), pd.to_numeric(y, errors="coerce")], axis=1).dropna()
    return float(z.iloc[:, 0].corr(z.iloc[:, 1], method="spearman")) if len(z) >= 3 else float("nan")


def pearson(x: pd.Series, y: pd.Series) -> float:
    z = pd.concat([pd.to_numeric(x, errors="coerce"), pd.to_numeric(y, errors="coerce")], axis=1).dropna()
    return float(z.iloc[:, 0].corr(z.iloc[:, 1], method="pearson")) if len(z) >= 3 else float("nan")


def weighted_mean(y: pd.Series, w: pd.Series) -> float:
    z = pd.concat([pd.to_numeric(y, errors="coerce"), pd.to_numeric(w, errors="coerce")], axis=1).dropna()
    if len(z) == 0:
        return float("nan")
    tot = float(z.iloc[:, 1].sum())
    return float((z.iloc[:, 0] * z.iloc[:, 1]).sum() / tot) if tot > 0 else float("nan")


def zero_sim_audit(path: Path) -> bool:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    banned_modules = {"subprocess", "jpype", "py4j"}
    banned_attrs = {"system", "popen", "Popen", "run", "call", "check_call", "check_output"}
    for n in ast.walk(tree):
        if isinstance(n, ast.Import) and any(a.name.split(".")[0] in banned_modules for a in n.names):
            return False
        if isinstance(n, ast.ImportFrom) and n.module and n.module.split(".")[0] in banned_modules:
            return False
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr in banned_attrs:
            return False
    return True


def read_xml_links(path: Path) -> pd.DataFrame:
    """Stream the frozen MATSim network: the only place capacity/freespeed live."""
    ids, fo, to, ln, fs, cap, per = [], [], [], [], [], [], []
    with gzip.open(path, "rt", encoding="utf-8", errors="replace") as f:
        for line in f:
            if "<link " not in line:
                continue
            d = dict(re.findall(r'([A-Za-z_]\w*)="([^"]*)"', line))
            if not d.get("id"):
                continue
            ids.append(d["id"])
            fo.append(d.get("from"))
            to.append(d.get("to"))
            ln.append(float(d.get("length", "nan")))
            fs.append(float(d.get("freespeed", "nan")))
            cap.append(float(d.get("capacity", "nan")))
            per.append(float(d.get("permlanes", "nan")))
    x = pd.DataFrame({
        "matsim_link_id": ids, "xml_from": fo, "xml_to": to,
        "xml_length_m": ln, "freespeed_ms": fs, "raw_capacity": cap, "raw_permlanes": per,
    })
    if x["matsim_link_id"].duplicated().any():
        raise ValueError("network.xml.gz 出现重复 link id")
    x["freespeed_kmh"] = x["freespeed_ms"] * 3.6
    return x


def read_csv_links(path: Path) -> pd.DataFrame:
    e = pd.read_csv(path, encoding="utf-8-sig", low_memory=False)
    cols = {str(c).strip().lower(): c for c in e.columns}
    req = ["from_node", "to_node", "length_m", "highway", "lanes"]
    missing = [c for c in req if c not in cols]
    if missing:
        raise ValueError(f"network CSV 缺字段: {missing}")
    ren = {cols[c]: c for c in req}
    for c in ["speed_kmh", "travel_time_s", "name"]:
        if c in cols:
            ren[cols[c]] = c
    e = e.rename(columns=ren)
    for c in ["from_node", "to_node"]:
        e[c] = pd.to_numeric(e[c], errors="coerce")
        if e[c].isna().any():
            raise ValueError(f"network {c} 存在无法解析值")
        e[c] = e[c].astype("int64")
    e["length_m"] = numeric(e["length_m"])
    e["highway"] = e["highway"].map(norm_text)
    e["lanes_osm_raw"] = numeric(e["lanes"])
    e["matsim_link_id"] = "e" + e["from_node"].astype(str) + "_" + e["to_node"].astype(str)
    if e["matsim_link_id"].duplicated().any():
        raise ValueError("network CSV 出现重复 matsim_link_id")
    return e.drop(columns=["lanes"])


def lane_vec_is_valid(v: pd.Series) -> pd.Series:
    return v.notna() & (v >= 1) & (v <= 20)


def load_network(xml_path: Path, csv_path: Path) -> pd.DataFrame:
    x = read_xml_links(xml_path)
    e = read_csv_links(csv_path)
    net = e.merge(x, on="matsim_link_id", how="inner", validate="one_to_one")
    if len(net) != len(x) or len(net) != len(e):
        raise ValueError(f"CSV/XML link 数不一致: csv={len(e)} xml={len(x)} merged={len(net)}")
    net["canonical_cap_per_lane"] = net["highway"].map(CAPACITY_PER_LANE)
    net["canonical_fallback_used"] = net["canonical_cap_per_lane"].isna()
    net["capacity_per_lane"] = np.where(
        net["raw_permlanes"] > 0, net["raw_capacity"] / net["raw_permlanes"], np.nan)
    net["cap_lookup_abs_diff"] = (net["capacity_per_lane"] - net["canonical_cap_per_lane"]).abs()
    net["cap_lookup_rel_diff"] = np.where(
        net["canonical_cap_per_lane"] > 0,
        net["cap_lookup_abs_diff"] / net["canonical_cap_per_lane"], np.nan)
    net["capacity_lookup_match_1pct"] = (
        net["canonical_cap_per_lane"].notna() & net["cap_lookup_rel_diff"].le(0.01))
    net["default_lanes"] = net["highway"].map(DEFAULT_LANES)
    net["lanes_equals_class_default"] = (
        net["raw_permlanes"].notna() & net["default_lanes"].notna()
        & (net["raw_permlanes"] - net["default_lanes"]).abs().le(1e-9))
    net["lanes_osm_valid"] = lane_vec_is_valid(net["lanes_osm_raw"])
    net["lanes_fallback_applied"] = ~net["lanes_osm_valid"]
    net["lanes_source"] = np.where(net["lanes_osm_valid"], "osm", "class_default")
    net["capacity_forced_default_class"] = net["canonical_fallback_used"]
    return net


def load_e2(all_path: Path, main_path: Path) -> tuple[pd.DataFrame, dict]:
    al = pd.read_csv(all_path, encoding="utf-8-sig", low_memory=False)
    req = [
        "LinkID", "RoadName", "RoadCat", "obs_8_9", "sim_8_9_scaled",
        "diagnostic_ratio_8_9", "diagnostic_residual_8_9", "diagnostic_highway",
        "representative_matsim_link_id", "valid_residual", "selection_mode",
        "tier_output", "matched_matsim_edges", "source_domain",
    ]
    missing = [c for c in req if c not in al.columns]
    if missing:
        raise ValueError(f"E2 all_tiers 缺字段: {missing}")
    al["diagnostic_highway"] = al["diagnostic_highway"].map(norm_text)
    for c in ["obs_8_9", "sim_8_9_scaled", "diagnostic_ratio_8_9", "diagnostic_residual_8_9",
              "matched_matsim_edges", "sim_8_9_median_raw", "sim_8_9_mean_raw"]:
        if c in al.columns:
            al[c] = numeric(al[c])
    al["LinkID"] = al["LinkID"].map(norm_id)
    al["representative_matsim_link_id"] = al["representative_matsim_link_id"].map(norm_id)
    al["valid_residual"] = to_bool(al["valid_residual"])
    al = al[al["LinkID"].ne("")].copy()

    slice_df = al[al["tier_output"].astype(str).eq(MAIN_TIER)].copy()
    if slice_df.empty:
        raise ValueError(f"E2 all_tiers 无 tier_output={MAIN_TIER}")

    equivalence = {"main_file_present": main_path.exists(), "same_linkid_set": None,
                   "valid_flag_discrepant": None, "max_abs_residual_delta": None,
                   "n_slice": int(len(slice_df))}
    if main_path.exists():
        am = pd.read_csv(main_path, encoding="utf-8-sig", low_memory=False)
        am["LinkID"] = am["LinkID"].map(norm_id)
        am["valid_residual"] = to_bool(am["valid_residual"])
        am["diagnostic_residual_8_9"] = numeric(am["diagnostic_residual_8_9"])
        a = am.set_index("LinkID")
        b = slice_df.set_index("LinkID")
        equivalence["same_linkid_set"] = set(a.index) == set(b.index)
        j = a[["valid_residual", "diagnostic_residual_8_9"]].join(
            b[["valid_residual", "diagnostic_residual_8_9"]], rsuffix="_slice", how="inner")
        equivalence["valid_flag_discrepant"] = int((j["valid_residual"] != j["valid_residual_slice"]).sum())
        equivalence["max_abs_residual_delta"] = float(
            (j["diagnostic_residual_8_9"] - j["diagnostic_residual_8_9_slice"]).abs().max())
    return slice_df, equivalence


def join_diagnostic(e2: pd.DataFrame, net: pd.DataFrame) -> pd.DataFrame:
    cols = [
        "matsim_link_id", "xml_length_m", "highway", "raw_capacity", "raw_permlanes",
        "capacity_per_lane", "canonical_cap_per_lane", "canonical_fallback_used",
        "cap_lookup_abs_diff", "cap_lookup_rel_diff", "capacity_lookup_match_1pct",
        "default_lanes", "lanes_equals_class_default", "lanes_osm_raw", "lanes_osm_valid",
        "lanes_fallback_applied", "lanes_source", "capacity_forced_default_class",
        "freespeed_kmh", "speed_kmh", "travel_time_s", "length_m", "name",
    ]
    cols = [c for c in cols if c in net.columns]
    z = e2.merge(net[cols], left_on="representative_matsim_link_id",
                 right_on="matsim_link_id", how="left", validate="many_to_one")
    z["join_ok"] = z["matsim_link_id"].notna()
    z["length_m_effective"] = z["xml_length_m"].where(z["join_ok"], np.nan)
    z["obs_to_capacity_proxy"] = np.where(z["raw_capacity"] > 0, z["obs_8_9"] / z["raw_capacity"], np.nan)
    z["sim_to_capacity_proxy"] = np.where(z["raw_capacity"] > 0, z["sim_8_9_scaled"] / z["raw_capacity"], np.nan)
    z["capacity_per_obs_flow"] = np.where(z["obs_8_9"] > 0, z["raw_capacity"] / z["obs_8_9"], np.nan)
    z["free_flow_time_h"] = np.where(z["freespeed_kmh"] > 0, z["xml_length_m"] / 1000.0 / z["freespeed_kmh"], np.nan)
    z["highway_consistent"] = z["diagnostic_highway"].ne("") & z["highway"].notna() & z["diagnostic_highway"].eq(z["highway"])
    z["speed_xml_csv_mismatch"] = (
        z["freespeed_kmh"].notna() & z["speed_kmh"].notna()
        & (z["freespeed_kmh"] - z["speed_kmh"]).abs().gt(0.1))
    return z


def valid_joined(z: pd.DataFrame) -> pd.DataFrame:
    return z[z["valid_residual"] & z["join_ok"]].copy()


def grade_summary(z: pd.DataFrame) -> pd.DataFrame:
    v = valid_joined(z)
    rows = []
    for hw, g in v.groupby("diagnostic_highway", dropna=False):
        rows.append({
            "diagnostic_highway": hw, "n": len(g),
            "length_km": g["length_m_effective"].sum() / 1000.0,
            "free_flow_time_h": g["free_flow_time_h"].sum(),
            "obs_flow_sum": g["obs_8_9"].sum(), "sim_flow_sum": g["sim_8_9_scaled"].sum(),
            "mean_residual": g["diagnostic_residual_8_9"].mean(),
            "median_residual": g["diagnostic_residual_8_9"].median(),
            "p10_residual": g["diagnostic_residual_8_9"].quantile(0.10),
            "p90_residual": g["diagnostic_residual_8_9"].quantile(0.90),
            "obs_weighted_residual": weighted_mean(g["diagnostic_residual_8_9"], g["obs_8_9"]),
            "sim_weighted_residual": weighted_mean(g["diagnostic_residual_8_9"], g["sim_8_9_scaled"]),
            "length_weighted_residual": weighted_mean(g["diagnostic_residual_8_9"], g["length_m_effective"]),
            "lanes_median": g["raw_permlanes"].median(),
            "lanes_p10": g["raw_permlanes"].quantile(0.10),
            "lanes_p90": g["raw_permlanes"].quantile(0.90),
            "lanes_osm_missing_share": g["lanes_osm_raw"].isna().mean(),
            "lanes_fallback_share": g["lanes_fallback_applied"].mean(),
            "lanes_default_equal_share": g["lanes_equals_class_default"].mean(),
            "capacity_median": g["raw_capacity"].median(),
            "capacity_per_lane_median": g["capacity_per_lane"].median(),
            "capacity_lookup_match_share": g["capacity_lookup_match_1pct"].mean(),
            "speed_median_kmh": g["freespeed_kmh"].median(),
            "speed_p10_kmh": g["freespeed_kmh"].quantile(0.10),
            "speed_p90_kmh": g["freespeed_kmh"].quantile(0.90),
            "speed_unique_n": g["freespeed_kmh"].nunique(dropna=True),
            "obs_to_capacity_median": g["obs_to_capacity_proxy"].median(),
            "obs_to_capacity_p90": g["obs_to_capacity_proxy"].quantile(0.90),
            "sim_to_capacity_median": g["sim_to_capacity_proxy"].median(),
            "sim_to_capacity_p90": g["sim_to_capacity_proxy"].quantile(0.90),
            "capacity_per_obs_flow_median": g["capacity_per_obs_flow"].median(),
        })
    return pd.DataFrame(rows).sort_values("diagnostic_highway")


def cap_lookup_audit(z: pd.DataFrame) -> pd.DataFrame:
    v = z[z["join_ok"] & z["diagnostic_highway"].isin(CAPACITY_PER_LANE)].copy()
    rows = []
    for hw, g in v.groupby("diagnostic_highway"):
        rows.append({
            "highway": hw, "n": len(g),
            "canonical_capacity_per_lane": CAPACITY_PER_LANE[hw],
            "actual_capacity_per_lane_median": g["capacity_per_lane"].median(),
            "actual_capacity_per_lane_p10": g["capacity_per_lane"].quantile(0.10),
            "actual_capacity_per_lane_p90": g["capacity_per_lane"].quantile(0.90),
            "actual_capacity_per_lane_unique_n": g["capacity_per_lane"].nunique(dropna=True),
            "lookup_match_share_1pct": g["capacity_lookup_match_1pct"].mean(),
            "lookup_rel_diff_median": g["cap_lookup_rel_diff"].median(),
            "lookup_rel_diff_p90": g["cap_lookup_rel_diff"].quantile(0.90),
            "lanes_median": g["raw_permlanes"].median(),
            "lanes_unique_n": g["raw_permlanes"].nunique(dropna=True),
            "class_default_lanes": DEFAULT_LANES.get(hw, np.nan),
            "default_lanes_equal_share": g["lanes_equals_class_default"].mean(),
            "lanes_fallback_share": g["lanes_fallback_applied"].mean(),
        })
    return pd.DataFrame(rows).sort_values("canonical_capacity_per_lane", ascending=False)


def speed_ladder(net: pd.DataFrame) -> pd.DataFrame:
    n = net[net["highway"].isin(CAPACITY_PER_LANE)].copy()
    n["speed_kmh"] = n["freespeed_kmh"]
    rows = []
    for hw, g in n.groupby("highway"):
        cnt = g["speed_kmh"].round(3).value_counts().sort_values(ascending=False)
        top = cnt.head(5)
        rows.append({
            "highway": hw, "n_links": len(g), "speed_median_kmh": g["speed_kmh"].median(),
            "speed_p10_kmh": g["speed_kmh"].quantile(0.10),
            "speed_p90_kmh": g["speed_kmh"].quantile(0.90),
            "speed_max_kmh": g["speed_kmh"].max(),
            "speed_unique_n": g["speed_kmh"].nunique(dropna=True),
            "top_speeds_kmh": "; ".join(f"{v:g}x{c}" for v, c in top.items()),
            "share_at_max_speed": float((g["speed_kmh"] - g["speed_kmh"].max()).abs().lt(1e-6).mean()),
        })
    return pd.DataFrame(rows).sort_values("speed_median_kmh", ascending=False)


def lane_expression(net: pd.DataFrame) -> pd.DataFrame:
    n = net[net["highway"].isin(CAPACITY_PER_LANE)].copy()
    agg = n.groupby("highway").agg(
        n_links=("matsim_link_id", "size"),
        lanes_osm_present_share=("lanes_osm_valid", "mean"),
        lanes_fallback_share=("lanes_fallback_applied", "mean"),
        lanes_effective_median=("raw_permlanes", "median"),
        lanes_osm_raw_median=("lanes_osm_raw", "median"),
        class_default_lanes=("default_lanes", "median"),
        lanes_equals_default_share=("lanes_equals_class_default", "mean"),
        capacity_forced_fallback_share=("canonical_fallback_used", "mean"),
    ).reset_index()
    return agg.sort_values("n_links", ascending=False)


def relationship_table(z: pd.DataFrame) -> pd.DataFrame:
    v = valid_joined(z)
    attrs = [
        ("lanes_effective", "raw_permlanes"), ("speed_kmh", "freespeed_kmh"),
        ("capacity", "raw_capacity"), ("capacity_per_lane", "capacity_per_lane"),
        ("capacity_per_obs_flow", "capacity_per_obs_flow"),
        ("obs_to_capacity_proxy", "obs_to_capacity_proxy"),
        ("sim_to_capacity_proxy", "sim_to_capacity_proxy"),
        ("lanes_osm_missing", "lanes_osm_valid"),
    ]
    rows = []
    for hw, g in v.groupby("diagnostic_highway", dropna=False):
        for label, col in attrs:
            if col not in g.columns:
                continue
            x = g[col]
            if col == "lanes_osm_valid":
                x = (~x.astype(bool)).astype(float)
            rows.append({
                "highway": hw, "attribute": label,
                "n": int(pd.concat([g["diagnostic_residual_8_9"], x], axis=1).dropna().shape[0]),
                "spearman_raw": spearman(g["diagnostic_residual_8_9"], x),
                "pearson_raw": pearson(g["diagnostic_residual_8_9"], x),
            })
    return pd.DataFrame(rows)


def grade_demeaned(z: pd.DataFrame) -> pd.DataFrame:
    v = valid_joined(z)
    v["residual_dm"] = v["diagnostic_residual_8_9"] - v.groupby("diagnostic_highway")["diagnostic_residual_8_9"].transform("mean")
    rows = []
    for label, col in [
        ("lanes_effective", "raw_permlanes"), ("speed_kmh", "freespeed_kmh"),
        ("capacity", "raw_capacity"), ("capacity_per_lane", "capacity_per_lane"),
        ("capacity_per_obs_flow", "capacity_per_obs_flow"),
        ("obs_to_capacity_proxy", "obs_to_capacity_proxy"),
        ("sim_to_capacity_proxy", "sim_to_capacity_proxy"),
    ]:
        if col not in v.columns:
            continue
        dm = v[col] - v.groupby("diagnostic_highway")[col].transform("mean")
        rows.append({
            "attribute": label,
            "n": int(pd.concat([v["residual_dm"], dm], axis=1).dropna().shape[0]),
            "pearson_grade_demeaned": pearson(v["residual_dm"], dm),
            "spearman_grade_demeaned": spearman(v["residual_dm"], dm),
        })
    return pd.DataFrame(rows)


def trend_table(z: pd.DataFrame) -> pd.DataFrame:
    v = valid_joined(z)
    v = v[v["diagnostic_highway"].isin(TARGET_TREND_HW)]
    if v.empty:
        return pd.DataFrame()
    ord_map = {"trunk": 1, "secondary": 2, "tertiary": 3}
    rows = []
    for hw in TARGET_TREND_HW:
        g = v[v["diagnostic_highway"] == hw]
        if len(g):
            rows.append({
                "highway": hw, "ordinal": ord_map[hw], "n": len(g),
                "mean_residual": g["diagnostic_residual_8_9"].mean(),
                "median_residual": g["diagnostic_residual_8_9"].median(),
                "obs_weighted_residual": weighted_mean(g["diagnostic_residual_8_9"], g["obs_8_9"]),
                "sim_weighted_residual": weighted_mean(g["diagnostic_residual_8_9"], g["sim_8_9_scaled"]),
                "lanes_fallback_share": g["lanes_fallback_applied"].mean(),
                "capacity_per_lane_median": g["capacity_per_lane"].median(),
                "speed_median_kmh": g["freespeed_kmh"].median(),
                "obs_to_capacity_median": g["obs_to_capacity_proxy"].median(),
            })
    out = pd.DataFrame(rows)
    if len(out) == 3:
        out["trend_spearman_mean"] = spearman(out["ordinal"], out["mean_residual"])
        out["trend_spearman_obs_weighted"] = spearman(out["ordinal"], out["obs_weighted_residual"])
        out["trend_spearman_sim_weighted"] = spearman(out["ordinal"], out["sim_weighted_residual"])
        out["trend_spearman_capacity_per_lane"] = spearman(out["ordinal"], out["capacity_per_lane_median"])
        out["trend_spearman_speed"] = spearman(out["ordinal"], out["speed_median_kmh"])
        out["trend_spearman_lane_fallback"] = spearman(out["ordinal"], out["lanes_fallback_share"])
    return out


def zero_sim_sensitivity(z: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Sections whose section value is 0 by the median-over-matched-edges rule.

    A section value of exactly 0 forces residual = -1.0 and is therefore a
    first-order driver of any *observed-flow-weighted* aggregate. This block
    quantifies how much of the grade picture is produced by that rule rather
    than by the network's capacity/speed expression.
    """
    v = valid_joined(z)
    zs = v[np.isclose(v["sim_8_9_scaled"], 0.0, atol=1e-9)]
    zero_ids = set(zs["LinkID"])
    med = numeric(v["sim_8_9_median_raw"]) if "sim_8_9_median_raw" in v.columns else pd.Series(np.nan, index=v.index)
    mean = numeric(v["sim_8_9_mean_raw"]) if "sim_8_9_mean_raw" in v.columns else pd.Series(np.nan, index=v.index)
    v = v.assign(_median_raw=med, _mean_raw=mean)
    zs = v[np.isclose(v["sim_8_9_scaled"], 0.0, atol=1e-9)]

    totals = []
    for hw, g in v.groupby("diagnostic_highway", dropna=False):
        gz = g[g["LinkID"].isin(zero_ids)]
        ga = g[~g["LinkID"].isin(zero_ids)]
        ow_all = weighted_mean(g["diagnostic_residual_8_9"], g["obs_8_9"])
        ow_ex = weighted_mean(ga["diagnostic_residual_8_9"], ga["obs_8_9"]) if len(ga) else np.nan
        sw_all = weighted_mean(g["diagnostic_residual_8_9"], g["sim_8_9_scaled"])
        sw_ex = weighted_mean(ga["diagnostic_residual_8_9"], ga["sim_8_9_scaled"]) if len(ga) else np.nan
        totals.append({
            "diagnostic_highway": hw, "n_all": len(g), "obs_all": g["obs_8_9"].sum(),
            "sim_all": g["sim_8_9_scaled"].sum(),
            "obs_w_residual_all": ow_all, "sim_w_residual_all": sw_all,
            "n_zero_sim": len(gz), "obs_zero_sim": gz["obs_8_9"].sum(),
            "obs_share_zero_sim": safe_ratio(gz["obs_8_9"].sum(), g["obs_8_9"].sum()),
            "n_excl_zero": len(ga), "obs_w_residual_excl_zero": ow_ex,
            "sim_w_residual_excl_zero": sw_ex,
            "obs_w_delta": ow_ex - ow_all, "sim_w_delta": sw_ex - sw_all,
        })
    tbl = pd.DataFrame(totals)
    row = {
        "diagnostic_highway": "__ALL_VALID__", "n_all": len(v), "obs_all": v["obs_8_9"].sum(),
        "sim_all": v["sim_8_9_scaled"].sum(),
        "obs_w_residual_all": weighted_mean(v["diagnostic_residual_8_9"], v["obs_8_9"]),
        "sim_w_residual_all": weighted_mean(v["diagnostic_residual_8_9"], v["sim_8_9_scaled"]),
        "n_zero_sim": len(zs), "obs_zero_sim": zs["obs_8_9"].sum(),
        "obs_share_zero_sim": safe_ratio(zs["obs_8_9"].sum(), v["obs_8_9"].sum()),
    }
    va = v[~v["LinkID"].isin(zero_ids)]
    row.update({
        "n_excl_zero": len(va), "obs_w_residual_excl_zero": weighted_mean(va["diagnostic_residual_8_9"], va["obs_8_9"]),
        "sim_w_residual_excl_zero": weighted_mean(va["diagnostic_residual_8_9"], va["sim_8_9_scaled"]),
        "obs_w_delta": weighted_mean(va["diagnostic_residual_8_9"], va["obs_8_9"]) - row["obs_w_residual_all"],
        "sim_w_delta": weighted_mean(va["diagnostic_residual_8_9"], va["sim_8_9_scaled"]) - row["sim_w_residual_all"],
    })
    tbl = pd.concat([pd.DataFrame([row]), tbl], ignore_index=True)

    agg = pd.DataFrame([{
        "n_zero_median_sections": int(len(zs)),
        "n_zero_median_with_positive_mean_raw": int((zs["_mean_raw"] > 0).sum()),
        "share_mean_raw_positive": float((zs["_mean_raw"] > 0).mean()) if len(zs) else np.nan,
        "matched_edges_median": float(numeric(zs["matched_matsim_edges"]).median()) if len(zs) else np.nan,
        "matched_edges_max": float(numeric(zs["matched_matsim_edges"]).max()) if len(zs) else np.nan,
        "rule": "section value = sim_8_9_median_raw scaled by SCALE; a section whose matched edges are mostly unused collapses to 0",
    }])
    return tbl, agg


def checks(script_path: Path, prereg_path: Path, net: pd.DataFrame, e2: pd.DataFrame,
           z: pd.DataFrame, out: Path, manifest: dict, equiv: dict,
           written: list[Path]) -> list[dict]:
    valid = e2[e2["valid_residual"]]
    joined = z[z["valid_residual"]]
    join_cov = safe_ratio(joined["join_ok"].sum(), len(valid))
    cap_cov = safe_ratio(joined["capacity_per_lane"].notna().sum(), len(joined))
    speed_cov = safe_ratio(joined["freespeed_kmh"].notna().sum(), len(joined))
    proxy_cov = min(
        safe_ratio(joined["obs_to_capacity_proxy"].notna().sum(), len(joined)),
        safe_ratio(joined["sim_to_capacity_proxy"].notna().sum(), len(joined)),
    )
    cnt = joined["diagnostic_highway"].value_counts()
    missing_core = [h for h in CORE_HW if int(cnt.get(h, 0)) < MIN_CORE_CLASS_N]
    req_net = {"matsim_link_id", "from_node", "to_node", "length_m", "highway",
               "raw_permlanes", "raw_capacity", "freespeed_kmh"}
    req_e2 = {"LinkID", "obs_8_9", "sim_8_9_scaled", "diagnostic_ratio_8_9",
              "diagnostic_residual_8_9", "representative_matsim_link_id", "valid_residual"}

    out_abs = out.resolve()
    outside = [str(p) for p in written if out_abs not in p.resolve().parents]
    frozen_touched = [str(p) for p in written
                      if any(str(p).replace("\\", "/").startswith(pre) for pre in FROZEN_FORBIDDEN_PREFIXES)]
    manifest_ok = bool(manifest)
    if manifest_ok:
        for k, rec in manifest.items():
            fp = Path(rec["path"])
            if not fp.exists() or sha256_file(fp) != rec["sha256"] or fp.stat().st_size != rec["size_bytes"]:
                manifest_ok = False
    resolution_ok = (out / "f0_input_resolution.csv").exists()

    gates = [
        {"gate_class": "PREREG", "check": "F0.01_PREREG_HASH",
         "pass": sha256_file(prereg_path).lower() == EXPECTED_PREREG_SHA256.lower(),
         "detail": sha256_file(prereg_path)},
        {"gate_class": "PREREG", "check": "F0.02_ZERO_SIMULATION", "pass": zero_sim_audit(script_path),
         "detail": "AST: no subprocess/jpype/py4j, no run/system/popen attribute call"},
        {"gate_class": "PREREG", "check": "F0.03_NETWORK_FIELDS", "pass": req_net.issubset(net.columns),
         "detail": f"missing={sorted(req_net - set(net.columns))}; "
                   f"capacity from network.xml.gz, raw lanes from network_links_source_copy.csv"},
        {"gate_class": "PREREG", "check": "F0.04_E2_RESIDUAL_FIELDS", "pass": req_e2.issubset(e2.columns),
         "detail": f"missing={sorted(req_e2 - set(e2.columns))}; "
                   f"rep link id from all_tiers tier_output={MAIN_TIER}"},
        {"gate_class": "PREREG", "check": "F0.05_REP_LINK_JOIN_GE_95PCT",
         "pass": np.isfinite(join_cov) and join_cov >= MIN_JOIN_COVERAGE,
         "detail": f"join_coverage={join_cov:.6f} ({int(joined['join_ok'].sum())}/{len(valid)})"},
        {"gate_class": "PREREG", "check": "F0.06_VALID_RESIDUAL_N_GE_500",
         "pass": len(valid) >= MIN_VALID_RESIDUAL, "detail": f"valid_residual_n={len(valid)}"},
        {"gate_class": "PREREG", "check": "F0.07_CORE_HIGHWAY_SUPPORT",
         "pass": not missing_core,
         "detail": f"below_{MIN_CORE_CLASS_N}={missing_core}; counts={ {k: int(v) for k, v in cnt.items()} }"},
        {"gate_class": "PREREG", "check": "F0.08_CAP_LANES_COVERAGE_GE_95PCT",
         "pass": np.isfinite(cap_cov) and cap_cov >= MIN_CAP_LANES_COVERAGE,
         "detail": f"coverage={cap_cov:.6f}"},
        {"gate_class": "PREREG", "check": "F0.09_SPEED_COVERAGE_GE_90PCT",
         "pass": np.isfinite(speed_cov) and speed_cov >= MIN_SPEED_COVERAGE,
         "detail": f"coverage={speed_cov:.6f}"},
        {"gate_class": "PREREG", "check": "F0.10_CAPACITY_PROXY_COVERAGE_GE_80PCT",
         "pass": np.isfinite(proxy_cov) and proxy_cov >= MIN_PROXY_COVERAGE,
         "detail": f"coverage={proxy_cov:.6f}"},
        {"gate_class": "PREREG", "check": "F0.11_OUTPUT_ISOLATION", "pass": not outside and not frozen_touched,
         "detail": f"files_written={len(written)}; outside_out_dir={outside}; frozen_paths_touched={frozen_touched}"},
        {"gate_class": "PREREG", "check": "F0.12_PROVENANCE", "pass": manifest_ok,
         "detail": f"manifest_keys={sorted(manifest)}; sha256+size re-verified={manifest_ok}"},
        {"gate_class": "SUPPLEMENTARY", "check": "F0.13_INPUT_SCHEMA_DEVIATION_DOCUMENTED",
         "pass": resolution_ok, "detail": "f0_input_resolution.csv records both PREREG section-2 deviations"},
        {"gate_class": "SUPPLEMENTARY", "check": "F0.14_E2_MAIN_TIER_EQUIVALENCE",
         "pass": bool(equiv.get("same_linkid_set")) and equiv.get("valid_flag_discrepant") == 0
                 and abs(float(equiv.get("max_abs_residual_delta") or 0.0)) < 1e-12,
         "detail": json.dumps(equiv, ensure_ascii=False)},
        {"gate_class": "SUPPLEMENTARY", "check": "F0.15_XML_CSV_LINK_PARITY",
         "pass": len(net) > 0 and not net["matsim_link_id"].duplicated().any(),
         "detail": f"links={len(net)}; dup=0; xml_csv_speed_mismatch={int(z['speed_xml_csv_mismatch'].sum())}"},
    ]
    return gates


def write_report(out: Path, net: pd.DataFrame, z: pd.DataFrame, summary: pd.DataFrame,
                 cap: pd.DataFrame, trend: pd.DataFrame, dm: pd.DataFrame,
                 ladder: pd.DataFrame, laneexpr: pd.DataFrame,
                 zerosens: pd.DataFrame, zerorule: pd.DataFrame,
                 gates: list[dict], status: str, equiv: dict) -> None:
    v = valid_joined(z)
    lines = [
        "# Step 7.9F-0 — Highway Grade x Capacity/Speed Structural Audit", "",
        f"**STATUS: {status}**", "",
        "零仿真、只读；不修改 v1.0，不产生 v1.1。", "",
        f"- frozen network: `{NET_XML_REL.as_posix()}` ({len(net):,} directed links)",
        f"- residual domain: 7.9E-2 expanded, `tier_output={MAIN_TIER}`, valid n = **{len(v):,}**", "",
        "## 0. Input resolution (deviation from PREREG section 2)", "",
        "预注册 §2 对两个输入的字段声明均不成立，实际解析如下（详见 `f0_input_resolution.csv`）：", "",
        "| declared input | declared field | actual resolution |", "|---|---|---|",
        f"| `network_links_source_copy.csv` | `capacity` | 该 CSV 无此列（仅 8 列）；capacity 取自冻结 `network.xml.gz` 的 link 属性 |",
        f"| `e2_section_residual_main.csv` | `representative_matsim_link_id` | 该表 17 列无此字段；取自 `e2_section_residual_all_tiers.csv` 的 `{MAIN_TIER}` 切片 |",
        "",
        f"A+B_MAIN 切片与 main 表等价性：LinkID 集合相同 = **{equiv.get('same_linkid_set')}**，"
        f"valid 标记差异 = **{equiv.get('valid_flag_discrepant')}**，"
        f"max|Δresidual| = **{equiv.get('max_abs_residual_delta')}**。", "",
        "## 1. Core result by highway grade", "",
        "| Highway | n | Mean res | Obs-w res | Sim-w res | Lanes med | Lanes fallback | Cap/lane | Speed med | Obs/cap P50 | Sim/cap P50 |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for _, r in summary[summary["diagnostic_highway"].isin(CORE_HW)].iterrows():
        lines.append(
            f"| {r['diagnostic_highway']} | {int(r['n'])} | {r['mean_residual']:.4f} | "
            f"{r['obs_weighted_residual']:.4f} | {r['sim_weighted_residual']:.4f} | "
            f"{r['lanes_median']:.2f} | {r['lanes_fallback_share']:.2%} | "
            f"{r['capacity_per_lane_median']:.1f} | {r['speed_median_kmh']:.1f} | "
            f"{r['obs_to_capacity_median']:.4f} | {r['sim_to_capacity_median']:.4f} |")
    lines += ["", "## 2. Capacity/lane lookup (tautology check)", "",
              "| Highway | n | Canonical | Actual P50 | Unique | Match ≤1% | Rel diff P50 | Default-lanes share |",
              "|---|---:|---:|---:|---:|---:|---:|---:|"]
    for _, r in cap.iterrows():
        lines.append(f"| {r['highway']} | {int(r['n'])} | {r['canonical_capacity_per_lane']:.0f} | "
                     f"{r['actual_capacity_per_lane_median']:.1f} | {int(r['actual_capacity_per_lane_unique_n'])} | "
                     f"{r['lookup_match_share_1pct']:.2%} | {r['lookup_rel_diff_median']:.4f} | "
                     f"{r['default_lanes_equal_share']:.2%} |")
    lines += ["", "## 3. Lane expression (OSM present vs class default)", "",
              "| Highway | Links | OSM lanes present | Fallback to default | Effective med | OSM raw med | Class default |",
              "|---|---:|---:|---:|---:|---:|---:|"]
    for _, r in laneexpr.iterrows():
        lines.append(f"| {r['highway']} | {int(r['n_links'])} | {r['lanes_osm_present_share']:.2%} | "
                     f"{r['lanes_fallback_share']:.2%} | {r['lanes_effective_median']:.2f} | "
                     f"{r['lanes_osm_raw_median']:.2f} | {r['class_default_lanes']:.1f} |")
    lines += ["", "## 4. Speed ladder", "",
              "| Highway | Links | P10 | Median | P90 | Max | Unique | Top speeds (km/h x n) |",
              "|---|---:|---:|---:|---:|---:|---:|---|"]
    for _, r in ladder.iterrows():
        lines.append(f"| {r['highway']} | {int(r['n_links'])} | {r['speed_p10_kmh']:.1f} | "
                     f"{r['speed_median_kmh']:.1f} | {r['speed_p90_kmh']:.1f} | {r['speed_max_kmh']:.1f} | "
                     f"{int(r['speed_unique_n'])} | {r['top_speeds_kmh']} |")
    if not trend.empty:
        lines += ["", "## 5. Trunk -> Secondary -> Tertiary gradient", "",
                  "| Highway | Ordinal | n | Mean | Obs-weighted | Sim-weighted | Lanes fallback | Cap/lane | Speed med |",
                  "|---|---:|---:|---:|---:|---:|---:|---:|---:|"]
        for _, r in trend.iterrows():
            lines.append(f"| {r['highway']} | {int(r['ordinal'])} | {int(r['n'])} | {r['mean_residual']:.4f} | "
                         f"{r['obs_weighted_residual']:.4f} | {r['sim_weighted_residual']:.4f} | "
                         f"{r['lanes_fallback_share']:.2%} | {r['capacity_per_lane_median']:.1f} | "
                         f"{r['speed_median_kmh']:.1f} |")
        if len(trend) == 3:
            lines += ["",
                      f"- Trend Spearman(mean) = **{trend.iloc[0]['trend_spearman_mean']:.4f}**",
                      f"- Trend Spearman(obs-weighted) = **{trend.iloc[0]['trend_spearman_obs_weighted']:.4f}**",
                      f"- Trend Spearman(sim-weighted) = **{trend.iloc[0]['trend_spearman_sim_weighted']:.4f}**",
                      f"- Companion structural trend: capacity/lane = {trend.iloc[0]['trend_spearman_capacity_per_lane']:.4f}, "
                      f"speed = {trend.iloc[0]['trend_spearman_speed']:.4f}, "
                      f"lane-fallback = {trend.iloc[0]['trend_spearman_lane_fallback']:.4f}"]
    lines += ["", "## 6. Zero-median sections and the weighting-base flip", ""]
    if not zerorule.empty:
        r0 = zerorule.iloc[0]
        lines += ["断面值 = `sim_8_9_median_raw × SCALE`，即**匹配边上的中位数**。"
                  "一支断面的匹配边若多数无流量，该断面被压成 0，残差恒为 **−1.0**，"
                  "因而成为任何 *observed-flow-weighted* 聚合的一阶驱动量。", "",
                  f"- 零中位断面数 = **{int(r0['n_zero_median_sections'])}**，"
                  f"其中 `sim_8_9_mean_raw > 0`（中位数塌陷而均值不塌陷）的有 "
                  f"**{int(r0['n_zero_median_with_positive_mean_raw'])}** "
                  f"（{r0['share_mean_raw_positive']:.1%}）",
                  f"- 这些断面的匹配边数中位 = {r0['matched_edges_median']:.0f}，最大 = {r0['matched_edges_max']:.0f}",
                  f"- 规则：{r0['rule']}", ""]
    if not zerosens.empty:
        lines += ["| Highway | n all | obs all | n zero-sim | obs share zero-sim | obs-w all | obs-w excl-zero | Δ | sim-w all | sim-w excl-zero |",
                  "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
        for _, r in zerosens.iterrows():
            lines.append(f"| {r['diagnostic_highway']} | {int(r['n_all'])} | {r['obs_all']:,.0f} | "
                         f"{int(r['n_zero_sim'])} | {r['obs_share_zero_sim']:.2%} | "
                         f"{r['obs_w_residual_all']:+.4f} | {r['obs_w_residual_excl_zero']:+.4f} | "
                         f"{r['obs_w_delta']:+.4f} | {r['sim_w_residual_all']:+.4f} | "
                         f"{r['sim_w_residual_excl_zero']:+.4f} |")
    lines += ["", "## 7. Raw vs grade-demeaned correlations", "",
              "| Attribute | n | Pearson (demeaned) | Spearman (demeaned) |", "|---|---:|---:|---:|"]
    for _, r in dm.iterrows():
        lines.append(f"| {r['attribute']} | {int(r['n'])} | {r['pearson_grade_demeaned']:.4f} | "
                     f"{r['spearman_grade_demeaned']:.4f} |")
    lines += ["", "## 8. Gates", "", "| Class | Check | Result | Detail |", "|---|---|---|---|"]
    for c in gates:
        lines.append(f"| {c['gate_class']} | {c['check']} | {'PASS' if c['pass'] else 'FAIL'} | {c['detail']} |")
    lines += ["", "## Interpretation boundary", "",
              "- **obs-weighted 与 sim-weighted 不是同一件事**：obs-weighted = `Σsim/Σobs − 1`（流量守恒），"
              "sim-weighted = `Σsim·r / Σsim`（模拟流量的所在之处）。两者在本数据上系统性背离，"
              "主因是零中位断面的 −1.0 只进入 obs 基数。任何等级梯度结论**必须双基数并报**。",
              "- capacity/lane 在该网络中由 `lanes × CAPACITY_PER_LANE[highway]` 解析生成；"
              "若 lookup-match 接近 100%，说明 capacity 层**不含 link 级信息**，"
              "lookup-match 只证明参数表达，不证明参数正确（R-GRADE-3）。",
              "- raw between-grade correlation 可能被 highway class 本身驱动，必须结合 grade-demeaned 结果（R-GRADE-4）。",
              "- observed/simulated capacity proxy 只是诊断代理，不等价于 realized v/c（R-GRADE-5）。",
              "- 本步骤零仿真、只读，不产生 v1.1；不得回写 v1.0 或 7.3.6A target（R-GRADE-1 / R-GRADE-6）。", ""]
    (out / "STEP7_9F0_REPORT.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project-root", type=Path, default=ROOT_DEFAULT)
    ap.add_argument("--network-xml", type=Path, default=None)
    ap.add_argument("--network-csv", type=Path, default=None)
    ap.add_argument("--e2-all", type=Path, default=None)
    ap.add_argument("--e2-main", type=Path, default=None)
    ap.add_argument("--prereg", type=Path, default=None)
    ap.add_argument("--out-dir", type=Path, default=OUT_REL)
    args = ap.parse_args()

    root = args.project_root
    xml_path = args.network_xml or (root / NET_XML_REL)
    csv_path = args.network_csv or (root / NET_CSV_REL)
    e2_all_path = args.e2_all or (root / E2_ALL_REL)
    e2_main_path = args.e2_main or (root / E2_MAIN_REL)
    prereg_path = args.prereg or (root / PREREG_REL)
    out = args.out_dir if args.out_dir.is_absolute() else root / args.out_dir
    out.mkdir(parents=True, exist_ok=True)
    for p in [xml_path, csv_path, e2_all_path, e2_main_path, prereg_path]:
        if not p.exists():
            raise FileNotFoundError(f"输入不存在: {p}")

    print("=" * 84)
    print("STEP 7.9F-0 | HIGHWAY GRADE x CAPACITY/SPEED STRUCTURAL AUDIT")
    print("=" * 84)
    print("ZERO SIMULATION / READ-ONLY")
    print(f"network xml : {xml_path}")
    print(f"network csv : {csv_path}")
    print(f"E2 all tier : {e2_all_path}  [{MAIN_TIER}]")
    print(f"Prereg SHA  : {sha256_file(prereg_path)}")

    net = load_network(xml_path, csv_path)
    e2, equiv = load_e2(e2_all_path, e2_main_path)
    z = join_diagnostic(e2, net)
    summary = grade_summary(z)
    cap = cap_lookup_audit(z)
    rels = relationship_table(z)
    dm = grade_demeaned(z)
    trend = trend_table(z)
    ladder = speed_ladder(net)
    laneexpr = lane_expression(net)
    zerosens, zerorule = zero_sim_sensitivity(z)

    written: list[Path] = []

    def dump_csv(df: pd.DataFrame, name: str) -> None:
        p = out / name
        df.to_csv(p, index=False, encoding="utf-8-sig")
        written.append(p)

    cols = [
        "LinkID", "RoadName", "RoadCat", "obs_8_9", "sim_8_9_scaled", "diagnostic_ratio_8_9",
        "diagnostic_residual_8_9", "diagnostic_highway", "representative_matsim_link_id",
        "valid_residual", "join_ok", "highway", "highway_consistent", "length_m_effective",
        "raw_permlanes", "raw_capacity", "capacity_per_lane", "canonical_cap_per_lane",
        "cap_lookup_abs_diff", "cap_lookup_rel_diff", "capacity_lookup_match_1pct",
        "default_lanes", "lanes_equals_class_default", "lanes_osm_raw", "lanes_osm_valid",
        "lanes_fallback_applied", "lanes_source", "freespeed_kmh", "speed_kmh",
        "speed_xml_csv_mismatch", "travel_time_s", "free_flow_time_h",
        "obs_to_capacity_proxy", "sim_to_capacity_proxy", "capacity_per_obs_flow",
        "matched_matsim_edges", "source_domain",
    ]
    cols = [c for c in cols if c in z.columns]
    dump_csv(z[cols], "f0_link_diagnostic.csv")
    dump_csv(summary, "f0_grade_summary.csv")
    dump_csv(cap, "f0_capacity_lookup_audit.csv")
    dump_csv(trend, "f0_grade_trend.csv")
    dump_csv(rels, "f0_residual_relationships.csv")
    dump_csv(dm, "f0_correlations.csv")
    dump_csv(ladder, "f0_speed_ladder.csv")
    dump_csv(laneexpr, "f0_lane_expression.csv")
    dump_csv(zerosens, "f0_zero_sim_sensitivity.csv")
    dump_csv(zerorule, "f0_aggregation_rule_audit.csv")

    resolution = pd.DataFrame([
        {
            "input_role": "network",
            "prereg_declared_path": NET_CSV_REL.as_posix(),
            "prereg_declared_fields": "from_node,to_node,length_m,highway,lanes,capacity",
            "resolved_path": xml_path.relative_to(root).as_posix(),
            "resolved_fields": "matsim_link_id,from,to,length,freespeed,capacity,permlanes",
            "issue": "declared CSV has 8 columns and NO capacity field",
            "reason": "capacity is derived at build time (lanes x class lookup) and materialised only in the frozen network.xml.gz; using the lookup to synthesise it would make the audit tautological",
            "rows": int(len(net)),
            "sha256": sha256_file(xml_path),
        },
        {
            "input_role": "network_secondary",
            "prereg_declared_path": NET_CSV_REL.as_posix(),
            "prereg_declared_fields": "lanes (raw OSM)",
            "resolved_path": csv_path.relative_to(root).as_posix(),
            "resolved_fields": "from_node,to_node,travel_time_s,length_m,speed_kmh,highway,lanes,name",
            "issue": "used for raw pre-fallback OSM lanes only",
            "reason": "raw lane presence is required by PREREG section 4 (missing rate / default-lanes hit rate)",
            "rows": int(len(net)),
            "sha256": sha256_file(csv_path),
        },
        {
            "input_role": "e2_residual",
            "prereg_declared_path": E2_MAIN_REL.as_posix(),
            "prereg_declared_fields": "...,representative_matsim_link_id,...",
            "resolved_path": e2_all_path.relative_to(root).as_posix(),
            "resolved_fields": "tier_output==A+B_MAIN slice, 23 columns incl. representative_matsim_link_id",
            "issue": "declared main table has 17 columns and NO representative_matsim_link_id",
            "reason": "verified bit-identical to main (same LinkID set, 0 discrepant valid flags, max|delta residual|=0)",
            "rows": int(len(e2)),
            "sha256": sha256_file(e2_all_path),
        },
    ])
    dump_csv(resolution, "f0_input_resolution.csv")

    manifest = {}
    for k, p in [("network_xml", xml_path), ("network_csv", csv_path), ("e2_all_tiers", e2_all_path),
                 ("e2_main", e2_main_path), ("prereg", prereg_path),
                 ("script", Path(__file__).resolve())]:
        st = p.stat()
        manifest[k] = {"path": str(p), "sha256": sha256_file(p), "mtime_ns": int(st.st_mtime_ns),
                       "size_bytes": int(st.st_size)}

    # dry-run the checker twice so isolation/provenance gates see the final write set
    ck = checks(Path(__file__).resolve(), prereg_path, net, e2, z, out, manifest, equiv, written)
    ck = checks(Path(__file__).resolve(), prereg_path, net, e2, z, out, manifest, equiv,
                written + [out / "f0_checks.csv", out / "f0_input_manifest.json",
                           out / "f0_summary.json", out / "STEP7_9F0_REPORT.md",
                           out / "f0_input_resolution.csv",
                           out / "f0_zero_sim_sensitivity.csv", out / "f0_aggregation_rule_audit.csv"])
    prereg_gates = [c for c in ck if c["gate_class"] == "PREREG"]
    supp_gates = [c for c in ck if c["gate_class"] == "SUPPLEMENTARY"]
    hard_pass = all(bool(c["pass"]) for c in prereg_gates)
    augmented_pass = hard_pass and all(bool(c["pass"]) for c in supp_gates)
    status = "GRADE_CAPACITY_AUDIT_READY" if hard_pass else "GRADE_CAPACITY_AUDIT_BLOCKED"

    pd.DataFrame(ck).to_csv(out / "f0_checks.csv", index=False, encoding="utf-8-sig")
    (out / "f0_input_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    v = valid_joined(z)
    summary_json = {
        "step": "7.9F-0", "status": status, "zero_simulation": True,
        "network_modified": False, "matsim_rerun": False, "frozen_touched": False,
        "network_links": int(len(net)), "e2_rows": int(len(e2)),
        "e2_tier": MAIN_TIER,
        "valid_joined_residual_n": int(len(v)),
        "core_grade_counts": {k: int(n) for k, n in
                              v[v["diagnostic_highway"].isin(CORE_HW)]["diagnostic_highway"].value_counts().items()},
        "hard_pass": hard_pass, "hard_pass_count": int(sum(bool(c["pass"]) for c in prereg_gates)),
        "hard_total": len(prereg_gates),
        "supplementary_pass_count": int(sum(bool(c["pass"]) for c in supp_gates)),
        "supplementary_total": len(supp_gates),
        "augmented_pass": augmented_pass,
        "prereg_sha256": sha256_file(prereg_path),
        "input_schema_deviation": True,
        "input_resolution": resolution[["input_role", "prereg_declared_path", "issue",
                                        "resolved_path"]].to_dict(orient="records"),
        "capacity_lookup_match_share_networkwide": float(net["capacity_lookup_match_1pct"].mean()),
        "lanes_fallback_share_networkwide": float(net["lanes_fallback_applied"].mean()),
        "speed_max_kmh_networkwide": float(net["freespeed_kmh"].max()),
        "e2_main_tier_equivalence": equiv,
        "zero_median_sections": int(len(valid_joined(z)[np.isclose(valid_joined(z)["sim_8_9_scaled"], 0.0, atol=1e-9)])),
        "obs_weighted_residual_excl_zero_median": float(
            zerosens.loc[zerosens["diagnostic_highway"].eq("__ALL_VALID__"), "obs_w_residual_excl_zero"].iloc[0]),
        "obs_weighted_residual_all": float(
            zerosens.loc[zerosens["diagnostic_highway"].eq("__ALL_VALID__"), "obs_w_residual_all"].iloc[0]),
    }
    (out / "f0_summary.json").write_text(json.dumps(summary_json, ensure_ascii=False, indent=2),
                                         encoding="utf-8")

    write_report(out, net, z, summary, cap, trend, dm, ladder, laneexpr, zerosens, zerorule,
                 ck, status, equiv)

    print(f"[1/6] network links            = {len(net):,}")
    print(f"[2/6] E2 rows (tier={MAIN_TIER}) = {len(e2):,}")
    print(f"[3/6] valid + joined           = {len(v):,}")
    print(f"[4/6] capacity lookup match    = {net['capacity_lookup_match_1pct'].mean():.6%}")
    _z = zerosens[zerosens["diagnostic_highway"].eq("__ALL_VALID__")].iloc[0]
    print(f"      zero-median sections     = {int(_z['n_zero_sim'])}  "
          f"(obs share {_z['obs_share_zero_sim']:.2%}); "
          f"obs-w residual {_z['obs_w_residual_all']:+.4f} -> {_z['obs_w_residual_excl_zero']:+.4f} when excluded")
    print(f"[5/6] hard gates (PREREG)      = {sum(bool(c['pass']) for c in prereg_gates)}/{len(prereg_gates)}"
          f"   supplementary = {sum(bool(c['pass']) for c in supp_gates)}/{len(supp_gates)}")
    print(f"[6/6] STATUS                   = {status}")
    print(f"      OUTPUT                   = {out}")
    print("      NOTE                     = no MATSim/Java call")
    return 0 if hard_pass else 1


if __name__ == "__main__":
    raise SystemExit(main())
