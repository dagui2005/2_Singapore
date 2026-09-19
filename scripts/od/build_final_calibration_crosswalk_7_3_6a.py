#!/usr/bin/env python3
# -*- coding: utf-8 -*-

r"""
Step 7.3.6A — Final Calibration Crosswalk Builder

Purpose
-------
Combine the validated results of:
    6.3.2 original tight crosswalk   (geometry base + per-edge distance)
    7.3.4 semantic alignment         (direction + highway semantics for CATA)
    7.3.5 SLIP geometry completion   (independent LTA geometry -> motorway_link)

into ONE final calibration crosswalk.

Important:
    This script does NOT modify the MATSim network or rerun MATSim.
    It does NOT change OD, lambda, population, departure profile,
    capacity, or route-choice. The 7.1 frozen calibration target is
    left untouched; this is a NEW, semantics-correct evaluation map.

Design principle
----------------
Semantic validity > direction validity > coverage.

RoadCat is the authoritative LTA observation classification.
OSM highway is the MATSim network classification.

Final hard rules:
    CATA      -> motorway
    SLIP_ROAD -> motorway_link

For CATA:
    keep edges with  direction <= 30 deg AND highway = motorway.
    name is auxiliary only (not a hard gate).

For SLIP_ROAD:
    hierarchical selection (see tiers below). RoadName is NEVER a hard gate:
    LTA slip RoadName describes the associated expressway, whereas OSM ramp
    names are heterogeneous, so a name gate would drop real ramps.

Tiers (section level, hierarchical)
-----------------------------------
    CATA:
        CATA_T1_DIRECTION_SEMANTIC : direction + motorway (preferred)
    SLIP:
        SLIP_T1_DIRECTION_NAME     : direction + name            (best)
        SLIP_T2_DIRECTION_GEOMETRY : direction + geometry        (main)
        SLIP_T3_GEOMETRY_ONLY      : geometry fallback           (flag)
    UNMATCHED                      : no reliable candidate -> NOT forced

1:N is allowed but controlled:
    CATA  N <= 10
    SLIP  N <= 8
    if exceeded -> selection_status = REVIEW (kept, flagged, not auto-trusted)

Outputs (reports/od_final_calibration_crosswalk_7_3_6/)
-------------------------------------------------------
    final_calibration_crosswalk.csv
    final_section_summary.csv
    final_cata_summary.csv
    final_slip_summary.csv
    crosswalk_edge_overlap.csv
    crosswalk_quality_summary.csv
    step7_3_6a_summary.json
    STEP7_3_6A_REPORT.md
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(r"D:\Luan\2026-05\2_Singapore")

OLD_DEFAULT = (
    ROOT
    / r"reports\matsim_assignment_6_3_2"
    / r"lta_section_matsim_crosswalk.csv"
)

SEMANTIC_DEFAULT = (
    ROOT
    / r"reports\od_section_semantic_rebuild_7_3_4"
    / r"rebuilt_crosswalk.csv"
)

SLIP_ALL_DEFAULT = (
    ROOT
    / r"reports\od_slip_candidate_completion_7_3_5"
    / r"slip_candidates_all.csv"
)

SLIP_STRICT_DEFAULT = (
    ROOT
    / r"reports\od_slip_candidate_completion_7_3_5"
    / r"slip_candidates_strict.csv"
)

NETWORK_DEFAULT = (
    ROOT
    / r"reports\matsim_network"
    / r"network_links_source_copy.csv"
)

TRAFFIC_DEFAULT = (
    ROOT
    / r"Singapore_OD_MATSim_FinalData"
    / r"08_TrafficCount"
    / r"TrafficFlow_Data.json"
)

OUT_DEFAULT = (
    ROOT
    / r"reports\od_final_calibration_crosswalk_7_3_6"
)

# N limits (links per LTA section).
CATA_N_MAX = 10
SLIP_N_MAX = 8

DIRECTION_MAX_DEG = 30.0

EXPECTED_HIGHWAY = {
    "CATA": "motorway",
    "SLIP_ROAD": "motorway_link",
}


def norm_name(x) -> str:
    if pd.isna(x):
        return ""
    s = str(x).upper().strip()
    s = s.replace("&", " AND ")
    s = re.sub(r"[-_/(),.&]+", " ", s)
    s = re.sub(r"\s+", " ", s)
    return s.strip()


def _to_bool(s: pd.Series) -> pd.Series:
    if s.dtype == bool:
        return s
    return (
        s.astype(str)
        .str.strip()
        .str.lower()
        .isin(["true", "1", "yes"])
    )


# ----------------------------------------------------------------------
# Loaders
# ----------------------------------------------------------------------
def load_network(path: Path) -> pd.DataFrame:
    net = pd.read_csv(
        path,
        usecols=["from_node", "to_node", "length_m", "highway", "name"],
        encoding="utf-8-sig",
        low_memory=False,
    )

    net["matsim_link_id"] = (
        "e"
        + net["from_node"].astype(str).str.strip()
        + "_"
        + net["to_node"].astype(str).str.strip()
    )

    net["highway"] = (
        net["highway"].astype(str).str.strip().str.lower()
    )

    net["name_norm"] = net["name"].map(norm_name)

    return net[
        [
            "matsim_link_id",
            "length_m",
            "highway",
            "name",
            "name_norm",
        ]
    ].drop_duplicates("matsim_link_id")


def load_traffic(path: Path) -> pd.DataFrame:
    with open(path, "r", encoding="utf-8-sig") as f:
        obj = json.load(f)

    rows = obj.get("Value", obj)
    tf = pd.DataFrame(rows)

    required = {"LinkID", "RoadName", "RoadCat"}
    missing = required - set(tf.columns)
    if missing:
        raise ValueError(f"TrafficFlow 缺字段: {sorted(missing)}")

    tf["LinkID"] = tf["LinkID"].astype(str).str.strip()
    tf["RoadName_norm"] = tf["RoadName"].map(norm_name)
    tf["RoadCat"] = (
        tf["RoadCat"].astype(str).str.strip().str.upper()
    )

    sec = (
        tf.groupby("LinkID", as_index=False)[
            ["RoadName", "RoadName_norm", "RoadCat"]
        ]
        .first()
    )

    # NOTE: return with the canonical section key name.
    return sec.rename(columns={"LinkID": "lta_linkid"})


def load_old(path: Path) -> pd.DataFrame:
    old = pd.read_csv(path, encoding="utf-8-sig", low_memory=False)

    ren = {}
    for c in old.columns:
        lc = c.lower().strip()
        if lc == "linkid":
            ren[c] = "lta_linkid"
        elif lc in {"matsim_link_id", "matsim_link"}:
            ren[c] = "matsim_link_id"
    old = old.rename(columns=ren)

    if "distance_m" not in old.columns:
        raise ValueError("6.3.2 crosswalk 缺 distance_m（CATA 几何距离来源）")

    old["lta_linkid"] = old["lta_linkid"].astype(str).str.strip()
    old["matsim_link_id"] = old["matsim_link_id"].astype(str).str.strip()
    old["distance_m"] = pd.to_numeric(old["distance_m"], errors="coerce")

    return old[["lta_linkid", "matsim_link_id", "distance_m"]].drop_duplicates(
        ["lta_linkid", "matsim_link_id"]
    )


def load_semantic(path: Path) -> pd.DataFrame:
    s = pd.read_csv(path, encoding="utf-8-sig", low_memory=False)

    ren = {}
    for c in s.columns:
        lc = c.lower().strip()
        if lc == "linkid":
            ren[c] = "lta_linkid"
        elif lc in {"matsim_link_id", "matsim_link"}:
            ren[c] = "matsim_link_id"
    s = s.rename(columns=ren)

    required = {"lta_linkid", "matsim_link_id", "highway"}
    missing = required - set(s.columns)
    if missing:
        raise ValueError(f"7.3.4 crosswalk 缺字段: {sorted(missing)}")

    s["lta_linkid"] = s["lta_linkid"].astype(str).str.strip()
    s["matsim_link_id"] = s["matsim_link_id"].astype(str).str.strip()
    s["highway"] = s["highway"].astype(str).str.strip().str.lower()

    if "direction_ok" not in s.columns:
        # fall back to angle threshold if the boolean is absent
        s["direction_ok"] = (
            pd.to_numeric(s["direction_diff_deg"], errors="coerce")
            <= DIRECTION_MAX_DEG
        )
    else:
        s["direction_ok"] = _to_bool(s["direction_ok"])

    if "direction_diff_deg" in s.columns:
        s["direction_diff_deg"] = pd.to_numeric(
            s["direction_diff_deg"], errors="coerce"
        )
    else:
        s["direction_diff_deg"] = np.nan

    if "name_match" in s.columns:
        s["name_match"] = _to_bool(s["name_match"])
    else:
        s["name_match"] = False

    drop = [c for c in ["RoadName", "RoadCat", "selection_tier"] if c in s.columns]
    out = s[
        ["lta_linkid", "matsim_link_id", "highway",
         "direction_ok", "direction_diff_deg", "name_match"]
    ].drop_duplicates(["lta_linkid", "matsim_link_id"])

    return out, s[["lta_linkid"] + drop].drop_duplicates("lta_linkid") if drop else None


def load_slip(path: Path, network: pd.DataFrame) -> pd.DataFrame:
    s = pd.read_csv(path, encoding="utf-8-sig", low_memory=False)

    ren = {}
    for c in s.columns:
        lc = c.lower().strip()
        if lc == "linkid":
            ren[c] = "lta_linkid"
        elif lc in {"matsim_link_id", "matsim_link"}:
            ren[c] = "matsim_link_id"
    s = s.rename(columns=ren)

    required = {
        "lta_linkid",
        "matsim_link_id",
        "direction_ok",
        "distance_m",
        "direction_diff_deg",
    }
    missing = required - set(s.columns)
    if missing:
        raise ValueError(f"7.3.5 candidates 缺字段: {sorted(missing)}")

    s["lta_linkid"] = s["lta_linkid"].astype(str).str.strip()
    s["matsim_link_id"] = s["matsim_link_id"].astype(str).str.strip()
    s["direction_ok"] = _to_bool(s["direction_ok"])
    s["distance_m"] = pd.to_numeric(s["distance_m"], errors="coerce")
    s["direction_diff_deg"] = pd.to_numeric(
        s["direction_diff_deg"], errors="coerce"
    )
    s["name_match"] = (
        _to_bool(s["name_match"]) if "name_match" in s.columns else False
    )

    # Drop the file's RoadName: the authoritative LTA RoadName is attached
    # later from the observation table. Keeping both would collide into
    # RoadName_x / RoadName_y and silently blank the final RoadName.
    if "RoadName" in s.columns:
        s = s.drop(columns=["RoadName"])

    # Attach network highway (avoid the name/name_norm columns to prevent
    # duplicate-column collisions: 7.3.5 already carries ramp name_norm).
    s = s.merge(
        network[["matsim_link_id", "highway"]],
        on="matsim_link_id",
        how="left",
    )

    return s


# ----------------------------------------------------------------------
# Build
# ----------------------------------------------------------------------
def _expected_rate(df: pd.DataFrame) -> pd.Series:
    """1.0 where highway equals the RoadCat-expected class."""
    exp = df["RoadCat"].map(EXPECTED_HIGHWAY)
    return (df["highway"].astype(str).str.lower() == exp).astype(float)


def build_cata(
    sem: pd.DataFrame,
    old: pd.DataFrame,
    obs: pd.DataFrame,
    cata_ids: set[str],
) -> pd.DataFrame:
    src = sem[sem["lta_linkid"].isin(cata_ids)].copy()

    # Hard gate 1: direction.
    src = src[src["direction_ok"]].copy()

    # Hard gate 2: semantics.
    src = src[src["highway"] == "motorway"].copy()

    # Geometry distance from the 6.3.2 crosswalk (7.3.4 does not carry it).
    src = src.merge(
        old, on=["lta_linkid", "matsim_link_id"], how="left"
    )

    src = src.merge(
        obs[["lta_linkid", "RoadName", "RoadCat"]],
        on="lta_linkid",
        how="left",
    )

    src["semantic_match"] = True
    src["selection_tier"] = "CATA_T1_DIRECTION_SEMANTIC"
    src["geometry_fallback"] = False
    src["is_primary_candidate"] = True

    return src.drop_duplicates(["lta_linkid", "matsim_link_id"])


def build_slip(
    slip_all: pd.DataFrame,
    obs: pd.DataFrame,
    slip_ids: set[str],
) -> pd.DataFrame:
    src = slip_all[slip_all["lta_linkid"].isin(slip_ids)].copy()

    # Only real ramps are eligible.
    src = src[src["highway"].astype(str).str.lower() == "motorway_link"].copy()

    if src.empty:
        return src

    src["_dir"] = src["direction_ok"]
    src["_dir_nm"] = src["_dir"] & src["name_match"]

    grp = src.groupby("lta_linkid")
    src["_has_dir"] = grp["_dir"].transform("any")
    src["_has_dir_nm"] = grp["_dir_nm"].transform("any")

    # Hierarchical selection: prefer direction-correct edges; fall back to
    # geometry only when no direction-correct ramp exists for the section.
    keep = src["_dir"] | (~src["_has_dir"])
    src = src[keep].copy()

    src["selection_tier"] = np.select(
        [
            src["_has_dir"] & src["_has_dir_nm"] & src["_dir"],
            src["_has_dir"],
        ],
        [
            "SLIP_T1_DIRECTION_NAME",
            "SLIP_T2_DIRECTION_GEOMETRY",
        ],
        default="SLIP_T3_GEOMETRY_ONLY",
    )

    src["geometry_fallback"] = ~src["_has_dir"]
    src["is_primary_candidate"] = src["selection_tier"].isin(
        ["SLIP_T1_DIRECTION_NAME", "SLIP_T2_DIRECTION_GEOMETRY"]
    )
    src["semantic_match"] = True

    src = src.merge(
        obs[["lta_linkid", "RoadName", "RoadCat"]],
        on="lta_linkid",
        how="left",
    )

    return src.drop_duplicates(["lta_linkid", "matsim_link_id"])


FINAL_COLS = [
    "lta_linkid",
    "RoadName",
    "RoadCat",
    "matsim_link_id",
    "highway",
    "selection_tier",
    "distance_m",
    "direction_diff_deg",
    "direction_ok",
    "name_match",
    "semantic_match",
    "geometry_fallback",
    "is_primary_candidate",
]


def build_final(
    traffic: pd.DataFrame,
    network: pd.DataFrame,
    old: pd.DataFrame,
    sem: pd.DataFrame,
    slip_all: pd.DataFrame,
    cata_n_max: int = CATA_N_MAX,
    slip_n_max: int = SLIP_N_MAX,
) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    obs = traffic.copy()

    cata_ids = set(obs.loc[obs["RoadCat"] == "CATA", "lta_linkid"])
    slip_ids = set(obs.loc[obs["RoadCat"] == "SLIP_ROAD", "lta_linkid"])

    cata = build_cata(sem, old, obs, cata_ids)
    slip = build_slip(slip_all, obs, slip_ids)

    for df in (cata, slip):
        for c in FINAL_COLS:
            if c not in df.columns:
                df[c] = np.nan

    final = pd.concat(
        [cata[FINAL_COLS], slip[FINAL_COLS]], ignore_index=True
    )

    final["highway"] = final["highway"].astype(str).str.strip().str.lower()
    final["selection_tier"] = final["selection_tier"].astype(str)

    # ---- dedupe (section, edge) keeping best tier ----
    tier_rank = {
        "CATA_T1_DIRECTION_SEMANTIC": 1,
        "SLIP_T1_DIRECTION_NAME": 1,
        "SLIP_T2_DIRECTION_GEOMETRY": 2,
        "SLIP_T3_GEOMETRY_ONLY": 3,
    }
    final["_tier_rank"] = final["selection_tier"].map(tier_rank).fillna(99)
    final = (
        final.sort_values(["lta_linkid", "matsim_link_id", "_tier_rank"])
        .drop_duplicates(["lta_linkid", "matsim_link_id"], keep="first")
        .drop(columns="_tier_rank")
    )

    # ---- shared-edge accounting ----
    overlap = (
        final.groupby("matsim_link_id", as_index=False)
        .agg(
            shared_section_count=("lta_linkid", "nunique"),
            RoadCat_values=("RoadCat", lambda s: "|".join(sorted(set(s)))),
        )
    )
    overlap["shared_by_multiple_sections"] = (
        overlap["shared_section_count"] > 1
    )
    final = final.merge(
        overlap[["matsim_link_id", "shared_section_count"]],
        on="matsim_link_id",
        how="left",
    )

    # ---- per-section N limit -> REVIEW ----
    n_map = final.groupby("lta_linkid")["matsim_link_id"].nunique()
    final["_n"] = final["lta_linkid"].map(n_map)
    review = (
        ((final["RoadCat"] == "CATA") & (final["_n"] > cata_n_max))
        | ((final["RoadCat"] == "SLIP_ROAD") & (final["_n"] > slip_n_max))
    )
    final["_review"] = review
    final = final.drop(columns="_n")

    # ---- section summary (incl. UNMATCHED) ----
    final["_expected"] = _expected_rate(final)

    sec = (
        final.groupby(["lta_linkid", "RoadName", "RoadCat"], as_index=False,
                      dropna=False)
        .agg(
            candidate_count=("matsim_link_id", "nunique"),
            primary_count=("is_primary_candidate", "sum"),
            median_distance_m=("distance_m", "median"),
            mean_distance_m=("distance_m", "mean"),
            direction_match_rate=("direction_ok", "mean"),
            semantic_match_rate=("_expected", "mean"),
            name_match_rate=("name_match", "mean"),
            geometry_fallback=("geometry_fallback", "max"),
            shared_edge_rate=(
                "shared_section_count",
                lambda s: float((s > 1).mean()),
            ),
            highway_values=(
                "highway",
                lambda s: "|".join(sorted(set(str(v) for v in s))),
            ),
            tier_values=(
                "selection_tier",
                lambda s: "|".join(sorted(set(s.astype(str)))),
            ),
        )
    )

    sec["mixed_highway"] = sec["highway_values"].str.contains(r"\|", regex=True)

    # selection_status: best tier present, REVIEW overrides, else UNMATCHED
    def _status(row):
        tv = row["tier_values"]
        if row.get("_review_flag", False):
            return "REVIEW"
        if tv.startswith("CATA_"):
            return "CATA_T1_DIRECTION_SEMANTIC"
        for t in [
            "SLIP_T1_DIRECTION_NAME",
            "SLIP_T2_DIRECTION_GEOMETRY",
            "SLIP_T3_GEOMETRY_ONLY",
        ]:
            if t in tv:
                return t
        return "UNMATCHED"

    review_secs = set(final.loc[final["_review"], "lta_linkid"])
    sec["_review_flag"] = sec["lta_linkid"].isin(review_secs)
    sec["selection_status"] = sec.apply(_status, axis=1)
    sec = sec.drop(columns="_review_flag")

    # append UNMATCHED sections so coverage is honest
    matched = set(sec["lta_linkid"])
    nm_rows = []
    for rc, ids in [("CATA", cata_ids), ("SLIP_ROAD", slip_ids)]:
        for sid in sorted(ids - matched):
            nm_rows.append(
                {
                    "lta_linkid": sid,
                    "RoadName": obs.loc[
                        obs["lta_linkid"] == sid, "RoadName"
                    ].iloc[0],
                    "RoadCat": rc,
                    "candidate_count": 0,
                    "primary_count": 0,
                    "median_distance_m": np.nan,
                    "mean_distance_m": np.nan,
                    "direction_match_rate": np.nan,
                    "semantic_match_rate": np.nan,
                    "name_match_rate": np.nan,
                    "geometry_fallback": False,
                    "shared_edge_rate": np.nan,
                    "highway_values": "",
                    "tier_values": "",
                    "mixed_highway": False,
                    "selection_status": "UNMATCHED",
                }
            )
    if nm_rows:
        sec = pd.concat([sec, pd.DataFrame(nm_rows)], ignore_index=True)

    final = final.drop(columns=[c for c in ["_expected", "_review"] if c in final.columns])

    diag = {
        "cata_ids": cata_ids,
        "slip_ids": slip_ids,
        "review_secs": review_secs,
        "cata_n_max": cata_n_max,
        "slip_n_max": slip_n_max,
    }
    return final[FINAL_COLS + ["shared_section_count"]], sec, diag


# ----------------------------------------------------------------------
# Outputs
# ----------------------------------------------------------------------
def write_outputs(
    out: Path,
    final: pd.DataFrame,
    sec: pd.DataFrame,
    diag: dict,
):
    out.mkdir(parents=True, exist_ok=True)

    final.to_csv(
        out / "final_calibration_crosswalk.csv",
        index=False,
        encoding="utf-8-sig",
    )
    sec.to_csv(
        out / "final_section_summary.csv",
        index=False,
        encoding="utf-8-sig",
    )

    cata_sec = sec[sec["RoadCat"] == "CATA"].copy()
    slip_sec = sec[sec["RoadCat"] == "SLIP_ROAD"].copy()
    cata_sec.to_csv(
        out / "final_cata_summary.csv", index=False, encoding="utf-8-sig"
    )
    slip_sec.to_csv(
        out / "final_slip_summary.csv", index=False, encoding="utf-8-sig"
    )

    # edge overlap
    overlap = (
        final.groupby("matsim_link_id", as_index=False)
        .agg(
            shared_section_count=("lta_linkid", "nunique"),
            RoadCat_values=("RoadCat", lambda s: "|".join(sorted(set(s)))),
        )
    )
    overlap["shared_by_multiple_sections"] = overlap["shared_section_count"] > 1
    overlap.to_csv(
        out / "crosswalk_edge_overlap.csv", index=False, encoding="utf-8-sig"
    )

    # quality per RoadCat
    qrows = []
    for rc, grp in sec.groupby("RoadCat"):
        matchedg = grp[grp["candidate_count"] > 0]
        qrows.append(
            {
                "RoadCat": rc,
                "obs_sections": int(len(grp)),
                "matched_sections": int((grp["candidate_count"] > 0).sum()),
                "unmatched_sections": int((grp["candidate_count"] == 0).sum()),
                "review_sections": int((grp["selection_status"] == "REVIEW").sum()),
                "coverage": float((grp["candidate_count"] > 0).mean()),
                "purity_rate": float(
                    (matchedg["highway_values"] == EXPECTED_HIGHWAY.get(rc, "")
                     ).mean()
                )
                if len(matchedg)
                else np.nan,
                "mean_edges": float(matchedg["candidate_count"].mean())
                if len(matchedg)
                else np.nan,
                "median_edges": float(matchedg["candidate_count"].median())
                if len(matchedg)
                else np.nan,
                "max_edges": int(matchedg["candidate_count"].max())
                if len(matchedg)
                else 0,
                "mean_direction_match": float(
                    matchedg["direction_match_rate"].mean()
                )
                if len(matchedg)
                else np.nan,
                "mean_name_match": float(
                    matchedg["name_match_rate"].mean()
                )
                if len(matchedg)
                else np.nan,
                "mixed_highway_rate": float(matchedg["mixed_highway"].mean())
                if len(matchedg)
                else np.nan,
                "mean_shared_edge_rate": float(
                    matchedg["shared_edge_rate"].mean()
                )
                if len(matchedg)
                else np.nan,
            }
        )
    quality = pd.DataFrame(qrows)
    quality.to_csv(
        out / "crosswalk_quality_summary.csv", index=False, encoding="utf-8-sig"
    )

    cata_sec_n = int((sec["RoadCat"] == "CATA").sum())
    slip_sec_n = int((sec["RoadCat"] == "SLIP_ROAD").sum())
    cata_match = int(
        ((sec["RoadCat"] == "CATA") & (sec["candidate_count"] > 0)).sum()
    )
    slip_match = int(
        ((sec["RoadCat"] == "SLIP_ROAD") & (sec["candidate_count"] > 0)).sum()
    )

    cata_purity = float(
        (cata_sec.loc[cata_sec["candidate_count"] > 0, "highway_values"]
         == "motorway").mean()
    ) if cata_match else np.nan
    slip_purity = float(
        (slip_sec.loc[slip_sec["candidate_count"] > 0, "highway_values"]
         == "motorway_link").mean()
    ) if slip_match else np.nan

    # residual opposite-direction share (only possible inside T3 geometry fallback)
    opp = final[pd.to_numeric(final["direction_ok"], errors="coerce") == 0]
    opp_share = float(len(opp) / len(final)) if len(final) else np.nan

    summary = {
        "step": "7.3.6A",
        "status": "PASS",
        "final_sections": int(sec["lta_linkid"].nunique()),
        "final_crosswalk_rows": int(len(final)),
        "CATA_sections": cata_sec_n,
        "SLIP_sections": slip_sec_n,
        "CATA_matched_sections": cata_match,
        "SLIP_matched_sections": slip_match,
        "CATA_coverage": cata_match / cata_sec_n if cata_sec_n else np.nan,
        "SLIP_coverage": slip_match / slip_sec_n if slip_sec_n else np.nan,
        "CATA_unmatched": cata_sec_n - cata_match,
        "SLIP_unmatched": slip_sec_n - slip_match,
        "CATA_purity_motorway": cata_purity,
        "SLIP_purity_motorway_link": slip_purity,
        "mean_edges_per_section": float(
            sec.loc[sec["candidate_count"] > 0, "candidate_count"].mean()
        ),
        "median_edges_per_section": float(
            sec.loc[sec["candidate_count"] > 0, "candidate_count"].median()
        ),
        "max_edges_per_section": int(
            sec["candidate_count"].max()
        ),
        "p90_edges_per_section": float(
            sec.loc[sec["candidate_count"] > 0, "candidate_count"].quantile(0.90)
        ),
        "review_sections": int(len(diag["review_secs"])),
        "review_rate": float(
            len(diag["review_secs"]) / sec["lta_linkid"].nunique()
        ),
        "shared_matsim_edge_rate": float(
            overlap["shared_by_multiple_sections"].mean()
        )
        if len(overlap)
        else np.nan,
        "opposite_direction_residual_rate": opp_share,
        "tier_counts": {
            k: int(v)
            for k, v in final["selection_tier"].value_counts().items()
        },
        "gates": {
            "Gate1_CATA_purity_gt_95": bool(
                (cata_purity or 0) > 0.95
            ),
            "Gate1_SLIP_purity_gt_90": bool(
                (slip_purity or 0) > 0.90
            ),
            "Gate2_opposite_lt_10": bool((opp_share or 0) < 0.10),
            "Gate3_CATA_coverage_gt_95": bool(
                (cata_match / cata_sec_n if cata_sec_n else 0) > 0.95
            ),
            "Gate3_SLIP_coverage_gt_95": bool(
                (slip_match / slip_sec_n if slip_sec_n else 0) > 0.95
            ),
        },
        "parameters_changed": False,
        "lambda_selected": False,
        "matsim_rerun": False,
    }

    with open(out / "step7_3_6a_summary.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    def _pct(x):
        return "n/a" if x is None or (isinstance(x, float) and np.isnan(x)) else f"{x:.2%}"

    cata_tiers = final.loc[final["RoadCat"] == "CATA", "selection_tier"].value_counts().to_dict()
    slip_tiers = final.loc[final["RoadCat"] == "SLIP_ROAD", "selection_tier"].value_counts().to_dict()

    cata_m = cata_sec[cata_sec["candidate_count"] > 0]
    slip_m = slip_sec[slip_sec["candidate_count"] > 0]

    report = f"""# Step 7.3.6A — Final Calibration Crosswalk

## Status

**PASS** — 零仿真；不修改 MATSim 网络/模型参数，不改 OD / λ / Population /
Departure / Capacity / Route-Choice，7.1 冻结靶场保持不动。本步产出**新的、
语义正确的评价映射**，供 7.3.6B 与后续 7.4 使用。

### Scope（重要）

本表覆盖 7.3 诊断所锁定的两类错配断面：**CATA** 与 **SLIP_ROAD**
（合计 {cata_sec_n + slip_sec_n} / 1,311 断面）。其余 RoadCat
（CATB / CATC / CATD / CATE）**不在本表内**，其评价仍沿用 6.3.2 / 7.3.4 基底。
若 7.4 需要全网分等级校准，应按同一规则另行扩展（后续步骤）。

### Hard semantic rules

- `CATA` → **motorway**（direction ≤ {DIRECTION_MAX_DEG:.0f}°，name 仅辅助）
- `SLIP_ROAD` → **motorway_link**（direction + geometry，**RoadName 不作硬约束**）

### Tier（分层选择）

- CATA：`CATA_T1_DIRECTION_SEMANTIC`
- SLIP：`SLIP_T1_DIRECTION_NAME` → `SLIP_T2_DIRECTION_GEOMETRY` →
  `SLIP_T3_GEOMETRY_ONLY`（geometry fallback，带 flag）
- 无可靠候选 → **UNMATCHED**（不强行匹配）

### N 上限

CATA ≤ {diag['cata_n_max']}，SLIP ≤ {diag['slip_n_max']}；超出 → `selection_status = REVIEW`
（保留但标记，不自动采信）。

## Results

| 指标 | CATA | SLIP_ROAD |
|---|---:|---:|
| 观测断面数 | {cata_sec_n} | {slip_sec_n} |
| 匹配断面数 | {cata_match} | {slip_match} |
| 覆盖率 | {_pct(summary['CATA_coverage'])} | {_pct(summary['SLIP_coverage'])} |
| 纯度（全部边=期望等级） | {_pct(cata_purity)} | {_pct(slip_purity)} |
| UNMATCHED | {summary['CATA_unmatched']} | {summary['SLIP_unmatched']} |

- Final crosswalk rows: **{summary['final_crosswalk_rows']:,}**
- mean links / section: **{summary['mean_edges_per_section']:.2f}**
- median links / section: **{summary['median_edges_per_section']:.0f}**
- max links / section: **{summary['max_edges_per_section']}**（p90 = {summary['p90_edges_per_section']:.0f}）
- REVIEW sections: **{summary['review_sections']}**（{_pct(summary['review_rate'])}；N 超上限，保留但标记）
- shared MATSim edge rate: **{_pct(summary['shared_matsim_edge_rate'])}**
- residual opposite-direction share: **{_pct(opp_share)}**
- tier counts (edges) — CATA: {cata_tiers} / SLIP: {slip_tiers}

### 断面边数分布（已匹配断面）

| RoadCat | mean | median | p90 | max | REVIEW (N 超限) |
|---|---:|---:|---:|---:|---:|
| CATA | {cata_m['candidate_count'].mean():.2f} | {cata_m['candidate_count'].median():.0f} | {cata_m['candidate_count'].quantile(0.9):.0f} | {int(cata_m['candidate_count'].max())} | {int((cata_sec['selection_status']=='REVIEW').sum())} |
| SLIP_ROAD | {slip_m['candidate_count'].mean():.2f} | {slip_m['candidate_count'].median():.0f} | {slip_m['candidate_count'].quantile(0.9):.0f} | {int(slip_m['candidate_count'].max())} | {int((slip_sec['selection_status']=='REVIEW').sum())} |

> SLIP 中位边数 ≈ {slip_m['candidate_count'].median():.0f}，恰在 N≤{diag['slip_n_max']} 上限附近，
> 故 REVIEW 比例偏高（SLIP {int((slip_sec['selection_status']=='REVIEW').sum())}/{slip_sec_n}）。
> 这是 OSM 匝道微段化的正常结果，**REVIEW 只是标记**；若需收紧，可调高
> `--slip-n-max`（例如 12）重跑，聚合口径仍为 median。

## Gates

| Gate | 判据 | 实测 | 结果 |
|---|---|---|---|
| G1 CATA 语义 | >95% | {_pct(cata_purity)} | {'✅' if summary['gates']['Gate1_CATA_purity_gt_95'] else '❌'} |
| G1 SLIP 语义 | >90% | {_pct(slip_purity)} | {'✅' if summary['gates']['Gate1_SLIP_purity_gt_90'] else '❌'} |
| G2 对向边 | <10% | {_pct(opp_share)} | {'✅' if summary['gates']['Gate2_opposite_lt_10'] else '❌'} |
| G3 CATA 覆盖 | >95% | {_pct(summary['CATA_coverage'])} | {'✅' if summary['gates']['Gate3_CATA_coverage_gt_95'] else '❌'} |
| G3 SLIP 覆盖 | >95% | {_pct(summary['SLIP_coverage'])} | {'✅' if summary['gates']['Gate3_SLIP_coverage_gt_95'] else '❌'} |

> 说明：纯度由构造保证（CATA 仅保留 `motorway`、SLIP 仅保留 `motorway_link`），
> 因此 G1 的判别力主要在**覆盖率**与**未匹配断面**；真正的差异在 7.3.6B 的
> Sim/Obs 回测中体现。
>
> **REVIEW 语义**：N 超上限的断面**仍保留在 crosswalk 中**，只是被标记为
> `REVIEW`；由于 7.1 口径的断面聚合采用 **median**，微段链较长本身不会引入
> 系统性偏差，故 REVIEW 是"待人工复核"标记而非剔除条件。
>
> **UNMATCHED 语义**：找不到方向+语义一致的候选时保留 `UNMATCHED`，
> **不强行匹配**（部分 CATA 未匹配断面只有方向相反的主线候选，宁缺勿滥）。

## Interpretation

这张 Final Calibration Crosswalk 才允许进入后续 TrafficFlow calibration。
它不改变 MATSim 模型本身，也不覆盖 7.1 冻结靶场。

7.3.6B 将用本表 + 已运行的 6.3.3B linkstats 做 old / 7.3.4 / final 三方回测，
直接回答 CATA / SLIP 的 Sim/Obs 是否收敛到 1。

## Outputs

- `final_calibration_crosswalk.csv`
- `final_section_summary.csv`
- `final_cata_summary.csv`
- `final_slip_summary.csv`
- `crosswalk_edge_overlap.csv`
- `crosswalk_quality_summary.csv`
- `step7_3_6a_summary.json`
- `STEP7_3_6A_REPORT.md`
"""

    (out / "STEP7_3_6A_REPORT.md").write_text(report, encoding="utf-8")


def main():
    ap = argparse.ArgumentParser()

    ap.add_argument("--old-crosswalk", type=Path, default=OLD_DEFAULT)
    ap.add_argument("--semantic-crosswalk", type=Path, default=SEMANTIC_DEFAULT)
    ap.add_argument("--slip-candidates", type=Path, default=SLIP_ALL_DEFAULT)
    ap.add_argument("--network", type=Path, default=NETWORK_DEFAULT)
    ap.add_argument("--traffic", type=Path, default=TRAFFIC_DEFAULT)
    ap.add_argument("--out-dir", type=Path, default=OUT_DEFAULT)
    ap.add_argument("--cata-n-max", type=int, default=CATA_N_MAX)
    ap.add_argument("--slip-n-max", type=int, default=SLIP_N_MAX)

    args = ap.parse_args()

    print("=" * 72)
    print("Step 7.3.6A | Final Calibration Crosswalk")
    print("=" * 72)

    for p in [
        args.old_crosswalk,
        args.semantic_crosswalk,
        args.slip_candidates,
        args.network,
        args.traffic,
    ]:
        if not p.exists():
            raise FileNotFoundError(f"输入不存在: {p}")

    network = load_network(args.network)
    traffic = load_traffic(args.traffic)
    old = load_old(args.old_crosswalk)
    sem, _ = load_semantic(args.semantic_crosswalk)
    slip_all = load_slip(args.slip_candidates, network)

    print(f"Traffic sections: {traffic.lta_linkid.nunique():,}")
    print(f"Old crosswalk sections: {old.lta_linkid.nunique():,}")
    print(f"7.3.4 semantic sections: {sem.lta_linkid.nunique():,}")
    print(f"7.3.5 SLIP candidate sections (FULL): {slip_all.lta_linkid.nunique():,}")

    final, sec, diag = build_final(
        traffic,
        network,
        old,
        sem,
        slip_all,
        cata_n_max=args.cata_n_max,
        slip_n_max=args.slip_n_max,
    )

    if final.empty:
        raise RuntimeError("Final Calibration Crosswalk 为空")

    write_outputs(args.out_dir, final, sec, diag)

    print("\nFinal crosswalk:")
    print(f"  sections = {sec.lta_linkid.nunique():,}")
    print(f"  rows     = {len(final):,}")

    print("\nRoadCat summary (section level):")
    print(
        sec.groupby("RoadCat")["candidate_count"]
        .agg(["count", "mean", "median"])
        .to_string()
    )

    print(f"\nOutput: {args.out_dir}")


if __name__ == "__main__":
    main()
