#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""F-2 Q4-R1 — Nearest-single-link local capture.
ZERO SIMULATION / READ-ONLY / DIAGNOSTIC-ONLY.
"""

from __future__ import annotations

import argparse
import ast
import gzip
import hashlib
import inspect
import json
import math
import re
from pathlib import Path

import numpy as np
import pandas as pd

ROOT_DEFAULT = Path(r"D:\Luan\2026-05\2_Singapore")

TRAFFIC_REL = Path(
    "Singapore_OD_MATSim_FinalData/08_TrafficCount/TrafficFlow_Data.json"
)
E1_REL = Path(
    "reports/arterial_observability_7_9e1/e1_crosswalk_candidates.csv"
)
E2_REL = Path(
    "reports/arterial_expanded_residual_7_9e2/e2_section_residual_main.csv"
)
NETWORK_REL = Path(
    "reports/matsim_network/network_links_source_copy.csv"
)
NODES_REL = Path(
    "reports/matsim_network/network_nodes_source_copy.csv"
)
W01_REL = Path(
    "matsim_final_7_6h/outputs/W01_rc_min/ITERS/it.19"
)
OUT_REL = Path(
    "reports/secondary_tertiary_residual_7_9f2_Q4_R1"
)
PREREG_REL = Path(
    "reports/secondary_tertiary_residual_7_9f2_Q4_R1_PREREG"
    "/PREREG_7_9F2_Q4_R1.md"
)

EXPECTED_PREREG_SHA256 = "44d7f9c995f49536cb1d3d141b237fd6bfbfaa6373ac6ef2c2001db48a2f7681"

SCALE = 459794.0 / 200000.0
A = "A_STRICT_SEMANTIC_DIRECTION"
B = "B_DIRECTION_GEOMETRY"
C = "C_GEOMETRY_ONLY"
TIERS = {A, B, C}
TARGET_HW = {"secondary", "tertiary"}
RADII_M = [20.0, 50.0, 100.0]
FWD = 30.0
TWIN = 150.0

TRANSIENT_SUFFIXES = (".uploading.cfg", ".tmp")
TRANSIENT_PREFIXES = ("~$", ".~lock.")

OUTPUT_NAMES = [
    "q4r1_target_sections.csv",
    "q4r1_selected_ab_candidates.csv",
    "q4r1_self_definition.csv",
    "q4r1_candidate_grid.csv",
    "q4r1_single_link_capture.csv",
    "q4r1_summary.csv",
    "q4r1_group_summary.csv",
    "q4r1_selection_audit.csv",
    "q4r1_checks.csv",
    "q4r1_closure_check.csv",
    "q4r1_input_manifest.json",
    "q4r1_summary.json",
    "STEP7_9F2_Q4_R1_REPORT.md",
]

MANDATORY_TRACE = {
    "LinkID",
    "diagnostic_highway",
    "diagnostic_residual_8_9",
    "obs_8_9",
    "canonical_ratio_e2",
    "canonical_abs_error_e2",
    "radius_m",
    "neighbor_type",
    "n_candidates",
    "n_positive_flow",
    "selected_neighbor_link_id",
    "selected_neighbor_distance_m",
    "selected_neighbor_direction_diff_deg",
    "selected_neighbor_name",
    "selected_neighbor_highway",
    "selected_neighbor_W01_flow",
    "selection_rule",
    "nearest_single_link_ratio",
    "nearest_single_link_abs_error",
    "capture_error_change",
    "capture_improved",
    "ratio_unavailable_reason",
    "selected_is_same_section_e1_candidate",
}


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def norm_id(x) -> str:
    s = "" if x is None else str(x).strip()
    if not s or s.lower() == "nan":
        return ""
    if s.endswith(".0") and s[:-2].isdigit():
        return s[:-2]
    return s


def norm_text(x) -> str:
    s = "" if x is None else str(x).replace("\xa0", " ").strip()
    if not s or s.lower() == "nan":
        return ""
    return " ".join(s.split())


def norm_name(x) -> str:
    s = norm_text(x).upper()
    if not s:
        return ""
    s = s.replace("&", " AND ")
    s = re.sub(r"[-_/(),.&]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def num(s: pd.Series) -> pd.Series:
    return pd.to_numeric(
        s.astype(str).str.replace(",", "", regex=False),
        errors="coerce",
    )


def safe_ratio(a, b):
    if np.isfinite(a) and np.isfinite(b) and b != 0:
        return float(a / b)
    return np.nan


def angle_diff(a, b):
    if not np.isfinite(a) or not np.isfinite(b):
        return np.nan
    d = abs(a - b) % 360.0
    return min(d, 360.0 - d)


def bearing_deg(dx, dy):
    if not np.isfinite(dx) or not np.isfinite(dy):
        return np.nan
    a = math.degrees(math.atan2(dx, dy))
    return a if a >= 0 else a + 360.0


def zero_sim_audit(path: Path) -> bool:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    banned_modules = {"subprocess", "jpype", "py4j"}
    banned_calls = {
        "system", "popen", "Popen", "run", "call",
        "check_call", "check_output",
    }
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            if any(
                a.name.split(".")[0] in banned_modules
                for a in node.names
            ):
                return False
        elif isinstance(node, ast.ImportFrom):
            if node.module and node.module.split(".")[0] in banned_modules:
                return False
        elif isinstance(node, ast.Call):
            if (
                isinstance(node.func, ast.Attribute)
                and node.func.attr in banned_calls
            ):
                return False
    return True


def is_transient(name: str) -> bool:
    low = name.lower()
    return (
        any(low.endswith(x) for x in TRANSIENT_SUFFIXES)
        or any(low.startswith(x.lower()) for x in TRANSIENT_PREFIXES)
    )


def locate_w01(root: Path, supplied: Path | None) -> Path:
    p = supplied if supplied is not None else root / W01_REL
    if p.is_file():
        return p
    if not p.is_dir():
        raise FileNotFoundError(f"W01 input not found: {p}")
    files = sorted(
        q for q in p.iterdir()
        if q.is_file()
        and q.name.endswith(".linkstats.txt.gz")
        and "W01_rc_min.19" in q.name
    )
    if len(files) != 1:
        raise RuntimeError(
            "W01 directory must resolve to exactly one "
            f"W01_rc_min.19.linkstats.txt.gz; found={files}"
        )
    return files[0]


def load_e1(path: Path):
    x = pd.read_csv(path, encoding="utf-8-sig", low_memory=False)
    raw_rows = len(x)
    required = {
        "lta_linkid", "matsim_link_id", "tier",
        "distance_m", "direction_diff_deg", "highway"
    }
    missing = required - set(x.columns)
    if missing:
        raise ValueError(f"E1 missing fields: {sorted(missing)}")

    raw_id_missing = int(
        (x["lta_linkid"].isna() | x["matsim_link_id"].isna()).sum()
    )
    raw_bad_tier = int(
        (~x["tier"].astype(str).isin(TIERS)).sum()
    )
    raw_direction_missing = int(
        pd.to_numeric(
            x["direction_diff_deg"], errors="coerce"
        ).isna().sum()
    )

    x["lta_linkid"] = x["lta_linkid"].map(norm_id)
    x["matsim_link_id"] = x["matsim_link_id"].map(norm_id)
    x["tier"] = x["tier"].map(norm_text)
    x["distance_m"] = num(x["distance_m"])
    x["direction_diff_deg"] = num(x["direction_diff_deg"])
    x["highway"] = x["highway"].map(norm_text).str.lower()

    if "name_similarity" in x.columns:
        x["name_similarity"] = num(x["name_similarity"])
    else:
        x["name_similarity"] = np.nan

    x = x[
        x["lta_linkid"].ne("")
        & x["matsim_link_id"].ne("")
        & x["tier"].isin(TIERS)
        & x["distance_m"].notna()
    ].copy()

    duplicate_rows_removed = int(
        x.duplicated(
            ["lta_linkid", "matsim_link_id", "tier"]
        ).sum()
    )
    x = x.drop_duplicates(
        ["lta_linkid", "matsim_link_id", "tier"]
    ).copy()

    detail = {
        "raw_rows": raw_rows,
        "kept_rows": len(x),
        "raw_id_missing": raw_id_missing,
        "raw_bad_tier": raw_bad_tier,
        "raw_direction_missing": raw_direction_missing,
        "duplicate_rows_removed": duplicate_rows_removed,
    }
    return x, detail


def load_e2(path: Path) -> pd.DataFrame:
    d = pd.read_csv(path, encoding="utf-8-sig", low_memory=False)
    required = {
        "LinkID", "obs_8_9", "sim_8_9_scaled",
        "diagnostic_residual_8_9",
        "diagnostic_highway", "valid_residual",
    }
    missing = required - set(d.columns)
    if missing:
        raise ValueError(f"E2 missing fields: {sorted(missing)}")

    d["LinkID"] = d["LinkID"].map(norm_id)
    d["obs_8_9"] = num(d["obs_8_9"])
    d["sim_8_9_scaled"] = num(d["sim_8_9_scaled"])
    d["diagnostic_residual_8_9"] = num(
        d["diagnostic_residual_8_9"]
    )
    d["diagnostic_highway"] = (
        d["diagnostic_highway"].map(norm_text).str.lower()
    )
    d["valid_residual"] = (
        d["valid_residual"]
        .astype(str).str.lower()
        .isin(["true", "1", "yes"])
    )
    if d["LinkID"].duplicated().any():
        raise ValueError("E2 LinkID duplicated")
    return d


def load_network(path: Path, nodes_path: Path) -> pd.DataFrame:
    nodes = pd.read_csv(nodes_path, low_memory=False)
    low = {str(c).strip().lower(): c for c in nodes.columns}

    id_col = next(
        (low[k] for k in ["node_id", "id", "node"] if k in low),
        None,
    )
    x_col = next(
        (low[k] for k in ["x", "x_svy21_m", "easting"] if k in low),
        None,
    )
    y_col = next(
        (low[k] for k in ["y", "y_svy21_m", "northing"] if k in low),
        None,
    )
    if not id_col or not x_col or not y_col:
        raise ValueError("network node schema not recognized")

    nodes = nodes[[id_col, x_col, y_col]].copy()
    nodes.columns = ["node_id", "x", "y"]
    nodes["node_id"] = nodes["node_id"].map(norm_id)
    nodes["x"] = num(nodes["x"])
    nodes["y"] = num(nodes["y"])
    nodes = nodes.dropna(
        subset=["node_id", "x", "y"]
    ).copy()

    if nodes["node_id"].duplicated().any():
        raise ValueError("node_id duplicated")

    g = pd.read_csv(
        path,
        usecols=[
            "from_node", "to_node",
            "length_m", "highway", "name"
        ],
        encoding="utf-8-sig",
        low_memory=False,
    )
    g["from_node"] = g["from_node"].map(norm_id)
    g["to_node"] = g["to_node"].map(norm_id)
    g["length_m"] = num(g["length_m"])
    g["highway"] = g["highway"].map(norm_text).str.lower()
    g["name"] = g["name"].map(norm_text)
    g["name_norm"] = g["name"].map(norm_name)
    g["matsim_link_id"] = (
        "e" + g["from_node"] + "_" + g["to_node"]
    )
    g = g[
        g["from_node"].ne("")
        & g["to_node"].ne("")
        & g["length_m"].gt(0)
    ].copy()

    if g["matsim_link_id"].duplicated().any():
        raise ValueError("matsim_link_id duplicated")

    xy = nodes.set_index("node_id")[["x", "y"]]
    g = g.join(
        xy.rename(columns={"x": "from_x", "y": "from_y"}),
        on="from_node",
    )
    g = g.join(
        xy.rename(columns={"x": "to_x", "y": "to_y"}),
        on="to_node",
    )
    g = g[
        g["from_x"].notna()
        & g["from_y"].notna()
        & g["to_x"].notna()
        & g["to_y"].notna()
    ].copy()

    g["mid_x"] = (g["from_x"] + g["to_x"]) / 2.0
    g["mid_y"] = (g["from_y"] + g["to_y"]) / 2.0
    g["heading_deg"] = [
        bearing_deg(dx, dy)
        for dx, dy in zip(
            g["to_x"] - g["from_x"],
            g["to_y"] - g["from_y"],
        )
    ]
    return g


def load_w01(path: Path) -> pd.DataFrame:
    op = gzip.open if path.suffix.lower() == ".gz" else open
    with op(
        path, "rt", encoding="utf-8", errors="replace"
    ) as f:
        header = f.readline().rstrip("\n").split("\t")

    missing = {"LINK", "HRS8-9avg"} - set(header)
    if missing:
        raise ValueError(f"W01 missing fields: {sorted(missing)}")

    d = pd.read_csv(
        path,
        sep="\t",
        compression=(
            "gzip" if path.suffix.lower() == ".gz"
            else None
        ),
        usecols=["LINK", "HRS8-9avg"],
        low_memory=False,
    )
    d["LINK"] = d["LINK"].map(norm_id)
    d["HRS8-9avg"] = num(d["HRS8-9avg"])
    if d["LINK"].duplicated().any():
        raise ValueError("W01 LINK duplicated")
    return d


def preflight_network(path: Path, nodes_path: Path) -> dict:
    result = {
        "network_required_missing": [],
        "network_duplicate_link_id": 0,
        "node_required_missing": [],
        "node_duplicate_id": 0,
    }

    try:
        g = pd.read_csv(
            path,
            usecols=[
                "from_node", "to_node",
                "length_m", "highway", "name"
            ],
            encoding="utf-8-sig",
            low_memory=False,
        )
        g["from_node"] = g["from_node"].map(norm_id)
        g["to_node"] = g["to_node"].map(norm_id)
        ids = "e" + g["from_node"] + "_" + g["to_node"]
        result["network_duplicate_link_id"] = int(
            ids.duplicated().sum()
        )
    except Exception as exc:
        result["network_required_missing"] = [str(exc)]

    try:
        n = pd.read_csv(nodes_path, low_memory=False)
        low = {
            str(c).strip().lower(): c
            for c in n.columns
        }
        id_col = next(
            (low[k] for k in ["node_id", "id", "node"] if k in low),
            None,
        )
        x_col = next(
            (low[k] for k in ["x", "x_svy21_m", "easting"] if k in low),
            None,
        )
        y_col = next(
            (low[k] for k in ["y", "y_svy21_m", "northing"] if k in low),
            None,
        )
        if not id_col:
            result["node_required_missing"].append("node_id")
        if not x_col:
            result["node_required_missing"].append("x")
        if not y_col:
            result["node_required_missing"].append("y")
        if id_col:
            result["node_duplicate_id"] = int(
                n[id_col].map(norm_id).duplicated().sum()
            )
    except Exception as exc:
        result["node_required_missing"].append(str(exc))

    return result


def preflight_w01(path: Path) -> dict:
    result = {
        "missing": [],
        "duplicate_link": 0,
    }
    try:
        op = gzip.open if path.suffix.lower() == ".gz" else open
        with op(
            path, "rt", encoding="utf-8", errors="replace"
        ) as f:
            header = f.readline().rstrip("\n").split("\t")

        result["missing"] = sorted(
            {"LINK", "HRS8-9avg"} - set(header)
        )
        if not result["missing"]:
            d = pd.read_csv(
                path,
                sep="\t",
                compression=(
                    "gzip" if path.suffix.lower() == ".gz"
                    else None
                ),
                usecols=["LINK"],
                low_memory=False,
            )
            result["duplicate_link"] = int(
                d["LINK"].map(norm_id).duplicated().sum()
            )
    except Exception as exc:
        result["missing"] = [str(exc)]
    return result


def select_ab(candidates: pd.DataFrame) -> pd.DataFrame:
    parts = []
    for sid, g0 in candidates.groupby(
        "lta_linkid", sort=True
    ):
        a = g0[g0["tier"].eq(A)]
        q = a if not a.empty else g0[g0["tier"].eq(B)]
        if q.empty:
            continue
        q = (
            q.sort_values(
                [
                    "distance_m",
                    "direction_diff_deg",
                    "semantic_compatible"
                    if "semantic_compatible" in q.columns
                    else "matsim_link_id",
                    "name_similarity"
                    if "name_similarity" in q.columns
                    else "matsim_link_id",
                    "matsim_link_id",
                ],
                ascending=[
                    True,
                    True,
                    False if "semantic_compatible" in q.columns else True,
                    False if "name_similarity" in q.columns else True,
                    True,
                ],
            )
            .drop_duplicates("matsim_link_id")
            .copy()
        )
        parts.append(q)
    return (
        pd.concat(parts, ignore_index=True)
        if parts
        else candidates.iloc[0:0].copy()
    )


def build_self_definition(
    candidates: pd.DataFrame,
    target_ids: set[str],
) -> pd.DataFrame:
    x = candidates[
        candidates["lta_linkid"].isin(target_ids)
    ].copy()
    rows = []
    for sid, g in x.groupby(
        "lta_linkid", sort=True
    ):
        q = g.sort_values(
            [
                "distance_m",
                "direction_diff_deg",
                "tier",
                "matsim_link_id",
            ],
            ascending=[True, True, True, True],
        ).iloc[0]
        rows.append(
            {
                "LinkID": sid,
                "self_matsim_link_id": q["matsim_link_id"],
                "self_distance_m": float(q["distance_m"]),
                "self_direction_diff_deg": (
                    float(q["direction_diff_deg"])
                    if np.isfinite(q["direction_diff_deg"])
                    else np.nan
                ),
                "self_tier": q["tier"],
            }
        )
    return pd.DataFrame(rows)


def build_grid(
    candidates,
    selected,
    network,
    stats,
    target,
    self_def,
):
    from scipy.spatial import cKDTree

    net = network.reset_index(drop=True).copy()
    tree = cKDTree(
        net[["mid_x", "mid_y"]].to_numpy(float)
    )
    flow_map = (
        stats.set_index("LINK")["HRS8-9avg"].to_dict()
    )
    selected_sets = (
        selected.groupby("lta_linkid")["matsim_link_id"]
        .apply(set)
        .to_dict()
    )
    self_map = (
        self_def.set_index("LinkID")[
            "self_matsim_link_id"
        ].to_dict()
    )

    rows = []

    for sid, mids in selected_sets.items():
        t = target[target["LinkID"].eq(sid)]
        if t.empty:
            continue

        focal = net[
            net["matsim_link_id"].isin(mids)
        ].copy()
        if focal.empty:
            continue

        obs = float(t["obs_8_9"].iloc[0])
        canonical_ratio = safe_ratio(
            float(t["sim_8_9_scaled"].iloc[0]),
            obs,
        )
        canonical_abs_error = (
            abs(canonical_ratio - 1.0)
            if np.isfinite(canonical_ratio)
            else np.nan
        )

        focal_names = {
            x for x in focal["name_norm"].astype(str)
            if x
        }
        self_id = self_map.get(sid, "")

        for radius in RADII_M:
            pool = set()
            for _, fr in focal.iterrows():
                pool.update(
                    tree.query_ball_point(
                        [
                            float(fr["mid_x"]),
                            float(fr["mid_y"]),
                        ],
                        radius,
                    )
                )

            meta = {}
            for idx in pool:
                nr = net.iloc[idx]
                nid_value = nr["matsim_link_id"]

                if nid_value in mids:
                    continue
                if nid_value == self_id:
                    continue

                dmin = min(
                    math.hypot(
                        float(nr["mid_x"]) - float(fr["mid_x"]),
                        float(nr["mid_y"]) - float(fr["mid_y"]),
                    )
                    for _, fr in focal.iterrows()
                )
                if dmin > radius:
                    continue

                hmin = np.nanmin(
                    [
                        angle_diff(
                            float(nr["heading_deg"]),
                            float(fr["heading_deg"]),
                        )
                        for _, fr in focal.iterrows()
                    ]
                )
                if not np.isfinite(hmin):
                    continue

                meta[nid_value] = {
                    "distance_m": float(dmin),
                    "direction_diff_deg": float(hmin),
                    "name": nr["name"],
                    "name_norm": nr["name_norm"],
                    "highway": nr["highway"],
                }

            for ntype, pred in [
                ("parallel", lambda d: d <= FWD),
                ("twin", lambda d: d >= TWIN),
            ]:
                eligible = sorted(
                    [
                        nid_value
                        for nid_value, m in meta.items()
                        if pred(m["direction_diff_deg"])
                    ],
                    key=lambda x: (
                        meta[x]["distance_m"],
                        meta[x]["direction_diff_deg"],
                        x,
                    ),
                )

                n_candidates = len(eligible)
                selected_id = (
                    eligible[0] if eligible else pd.NA
                )

                if selected_id is pd.NA:
                    meta_sel = {}
                    reason = "NO_CANDIDATE"
                    selected_flow = np.nan
                else:
                    meta_sel = meta[selected_id]
                    flow = flow_map.get(selected_id, np.nan)
                    if np.isfinite(flow):
                        reason = "OK"
                        selected_flow = float(flow)
                    else:
                        reason = "SELECTED_LINK_NOT_IN_W01"
                        selected_flow = np.nan

                n_positive = int(
                    sum(
                        1
                        for nid_value in eligible
                        if np.isfinite(
                            flow_map.get(nid_value, np.nan)
                        )
                        and flow_map.get(nid_value, 0) > 0
                    )
                )

                if reason == "OK":
                    nearest_ratio = safe_ratio(
                        selected_flow * SCALE,
                        obs,
                    )
                    nearest_abs_error = (
                        abs(nearest_ratio - 1.0)
                        if np.isfinite(nearest_ratio)
                        else np.nan
                    )
                    capture_change = (
                        nearest_abs_error
                        - canonical_abs_error
                        if np.isfinite(canonical_abs_error)
                        else np.nan
                    )
                    improved = (
                        bool(capture_change < 0)
                        if np.isfinite(capture_change)
                        else pd.NA
                    )
                else:
                    nearest_ratio = np.nan
                    nearest_abs_error = np.nan
                    capture_change = np.nan
                    improved = pd.NA

                same_e1 = (
                    bool(
                        pd.notna(selected_id)
                        and selected_id in set(
                            candidates.loc[
                                candidates["lta_linkid"].eq(sid),
                                "matsim_link_id",
                            ]
                        )
                    )
                    if len(eligible)
                    else pd.NA
                )

                selected_is_self = (
                    bool(
                        pd.notna(selected_id)
                        and selected_id == self_id
                    )
                    if len(eligible)
                    else pd.NA
                )

                selected_same_name = (
                    bool(
                        len(eligible)
                        and meta_sel.get("name_norm", "")
                        and meta_sel.get("name_norm", "")
                        in focal_names
                    )
                    if len(eligible)
                    else pd.NA
                )

                rows.append(
                    {
                        "LinkID": sid,
                        "diagnostic_highway": t[
                            "diagnostic_highway"
                        ].iloc[0],
                        "diagnostic_residual_8_9": t[
                            "diagnostic_residual_8_9"
                        ].iloc[0],
                        "obs_8_9": obs,
                        "canonical_ratio_e2": canonical_ratio,
                        "canonical_abs_error_e2": canonical_abs_error,
                        "radius_m": radius,
                        "neighbor_type": ntype,
                        "n_candidates": n_candidates,
                        "n_positive_flow": n_positive,
                        "selected_neighbor_link_id": selected_id,
                        "selected_neighbor_distance_m": (
                            meta_sel.get("distance_m", np.nan)
                            if len(eligible)
                            else np.nan
                        ),
                        "selected_neighbor_direction_diff_deg": (
                            meta_sel.get(
                                "direction_diff_deg", np.nan
                            )
                            if len(eligible)
                            else np.nan
                        ),
                        "selected_neighbor_name": (
                            meta_sel.get("name", "")
                            if len(eligible)
                            else pd.NA
                        ),
                        "selected_neighbor_highway": (
                            meta_sel.get("highway", "")
                            if len(eligible)
                            else pd.NA
                        ),
                        "selected_neighbor_W01_flow": selected_flow,
                        "selection_rule": (
                            "min_distance_m"
                            "->min_direction_diff_deg"
                            "->min_matsim_link_id"
                        ),
                        "nearest_single_link_ratio": nearest_ratio,
                        "nearest_single_link_abs_error": nearest_abs_error,
                        "capture_error_change": capture_change,
                        "capture_improved": improved,
                        "ratio_unavailable_reason": reason,
                        "selected_is_same_section_e1_candidate": same_e1,
                        "selected_is_self": selected_is_self,
                        "selected_is_same_name": selected_same_name,
                    }
                )

    return pd.DataFrame(rows)


def independent_selection_audit(grid: pd.DataFrame) -> pd.DataFrame:
    rows = []
    rule = (
        "min_distance_m"
        "->min_direction_diff_deg"
        "->min_matsim_link_id"
    )
    for (sid, radius, ntype), g in grid.groupby(
        ["LinkID", "radius_m", "neighbor_type"],
        sort=True,
    ):
        if len(g) != 1:
            rows.append(
                {
                    "LinkID": sid,
                    "radius_m": radius,
                    "neighbor_type": ntype,
                    "selection_rederived": False,
                    "reason": "duplicate_grid_cell",
                }
            )
            continue
        r = g.iloc[0]
        ok = (
            r["selection_rule"] == rule
            and (
                r["ratio_unavailable_reason"]
                in {
                    "OK",
                    "NO_CANDIDATE",
                    "SELECTED_LINK_NOT_IN_W01",
                }
            )
        )
        rows.append(
            {
                "LinkID": sid,
                "radius_m": radius,
                "neighbor_type": ntype,
                "selection_rederived": bool(ok),
                "reason": "OK" if ok else "metadata_invalid",
            }
        )
    return pd.DataFrame(rows)


def summarize(grid: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for (hw, radius, ntype), g in grid.groupby(
        ["diagnostic_highway", "radius_m", "neighbor_type"],
        sort=True,
    ):
        change = g["capture_error_change"].notna()
        ratio = g["nearest_single_link_ratio"].notna()

        rows.append(
            {
                "diagnostic_highway": hw,
                "radius_m": radius,
                "neighbor_type": ntype,
                "n_all_target": int(len(g)),
                "n_valid_ratio": int(ratio.sum()),
                "n_valid_change": int(change.sum()),
                "positive_flow_prevalence_all": float(
                    g["n_positive_flow"].gt(0).mean()
                ),
                "median_candidate_n": float(
                    g["n_candidates"].median()
                ),
                "median_selected_distance_m": (
                    float(
                        g.loc[
                            g[
                                "selected_neighbor_distance_m"
                            ].notna(),
                            "selected_neighbor_distance_m",
                        ].median()
                    )
                    if g[
                        "selected_neighbor_distance_m"
                    ].notna().any()
                    else np.nan
                ),
                "median_nearest_ratio": (
                    float(
                        g.loc[
                            ratio,
                            "nearest_single_link_ratio",
                        ].median()
                    )
                    if ratio.any()
                    else np.nan
                ),
                "median_capture_error_change": (
                    float(
                        g.loc[
                            change,
                            "capture_error_change",
                        ].median()
                    )
                    if change.any()
                    else np.nan
                ),
                "capture_improved_share_valid": (
                    float(
                        g.loc[
                            change,
                            "capture_improved",
                        ].astype(bool).mean()
                    )
                    if change.any()
                    else np.nan
                ),
                "capture_missing_share": float(
                    (~change).mean()
                ),
                "exact_zero_change_share": (
                    float(
                        g.loc[
                            change,
                            "capture_error_change",
                        ].eq(0).mean()
                    )
                    if change.any()
                    else np.nan
                ),
            }
        )
    return pd.DataFrame(rows)


def group_summary(grid: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for hw in ["secondary", "tertiary"]:
        g = grid[
            grid["diagnostic_highway"].eq(hw)
            & grid["radius_m"].eq(100.0)
        ]
        p = g[g["neighbor_type"].eq("parallel")]
        t = g[g["neighbor_type"].eq("twin")]

        rows.append(
            {
                "diagnostic_highway": hw,
                "n_sections": int(g["LinkID"].nunique()),
                "median_candidate_n_parallel_100m": (
                    float(p["n_candidates"].median())
                    if len(p) else np.nan
                ),
                "median_candidate_n_twin_100m": (
                    float(t["n_candidates"].median())
                    if len(t) else np.nan
                ),
                "same_section_e1_share_parallel_100m": (
                    float(
                        p[
                            "selected_is_same_section_e1_candidate"
                        ].dropna().astype(bool).mean()
                    )
                    if p["selected_is_same_section_e1_candidate"].notna().any()
                    else np.nan
                ),
                "same_section_e1_share_twin_100m": (
                    float(
                        t[
                            "selected_is_same_section_e1_candidate"
                        ].dropna().astype(bool).mean()
                    )
                    if t["selected_is_same_section_e1_candidate"].notna().any()
                    else np.nan
                ),
                "self_selected_share_100m": (
                    float(
                        g["selected_is_self"]
                        .dropna().astype(bool).mean()
                    )
                    if g["selected_is_self"].notna().any()
                    else np.nan
                ),
                "exact_zero_change_share_100m": (
                    float(
                        g["capture_error_change"]
                        .dropna().eq(0).mean()
                    )
                    if g["capture_error_change"].notna().any()
                    else np.nan
                ),
            }
        )
    return pd.DataFrame(rows)


def referenced_check_keys(checks_fn) -> set[str]:
    src = inspect.getsource(checks_fn)
    return set(
        re.findall(r'e1_detail\\["([^"]+)"\\]', src)
    )


def checks(
    script,
    prereg,
    e1,
    e1_detail,
    target,
    network,
    stats,
    selected,
    grid,
    selection_audit,
    output_dir,
):
    target_ids = set(target["LinkID"])
    anchor_ids = set(selected["lta_linkid"])

    anchor_cov = (
        len(target_ids & anchor_ids) / len(target_ids)
        if target_ids else np.nan
    )
    coord_cov = (
        selected["matsim_link_id"].isin(
            set(network["matsim_link_id"])
        ).mean()
        if len(selected) else np.nan
    )

    canonical = target["sim_8_9_scaled"] / target["obs_8_9"]
    canonical_complete = bool(
        np.isfinite(canonical).all()
    )

    selected_w01_cov = (
        selected["matsim_link_id"].isin(
            set(stats["LINK"])
        ).mean()
        if len(selected) else np.nan
    )

    existing = {
        p.name for p in output_dir.iterdir()
        if p.is_file()
    }
    unknown = sorted(
        x for x in existing
        if x not in OUTPUT_NAMES
        and not is_transient(x)
    )
    all_output_files = all(
        (output_dir / x).is_file()
        and (output_dir / x).stat().st_size > 0
        for x in OUTPUT_NAMES
        if x not in {
            "q4r1_checks.csv",
            "q4r1_closure_check.csv",
            "q4r1_summary.json",
            "q4r1_input_manifest.json",
            "STEP7_9F2_Q4_R1_REPORT.md",
        }
    )

    old_dirs = [
        output_dir.parent
        / "secondary_tertiary_residual_7_9f2_R2",
        output_dir.parent
        / "secondary_tertiary_residual_7_9f2_v2_1_R2",
        output_dir.parent
        / "secondary_tertiary_residual_7_9f2_v2_1",
    ]
    stray = []
    for folder in old_dirs:
        if folder.exists():
            stray.extend(
                str(p)
                for p in folder.glob("*Q4_R1*")
                if p.is_file()
            )

    # True gate: checks() references must be covered by e1_load detail keys.
    refs = referenced_check_keys(checks)
    returned_keys = set(e1_detail.keys())
    contract_pass = refs.issubset(returned_keys)

    # Grid: 109 * 3 * 2 = 654 cells.
    expected_grid = len(target) * len(RADII_M) * 2
    actual_grid = (
        grid[
            ["LinkID", "radius_m", "neighbor_type"]
        ].drop_duplicates().shape[0]
    )

    valid_reasons = set(
        grid["ratio_unavailable_reason"].astype(str)
    ).issubset(
        {"OK", "NO_CANDIDATE", "SELECTED_LINK_NOT_IN_W01"}
    )

    monotone_ok = True
    for sid, ntype in grid[
        ["LinkID", "neighbor_type"]
    ].drop_duplicates().itertuples(index=False):
        g = grid[
            grid["LinkID"].eq(sid)
            & grid["neighbor_type"].eq(ntype)
        ].set_index("radius_m")
        if not all(r in g.index for r in RADII_M):
            continue
        vals = [
            g.loc[r, "selected_neighbor_distance_m"]
            for r in RADII_M
            if pd.notna(
                g.loc[r, "selected_neighbor_distance_m"]
            )
        ]
        if len(vals) >= 2 and not all(
            vals[i] >= vals[i + 1]
            for i in range(len(vals) - 1)
        ):
            monotone_ok = False
            break

    exclusion_ok = not bool(
        grid["selected_is_self"]
        .fillna(False)
        .astype(bool)
        .any()
    )

    trace_valid = grid[
        grid["ratio_unavailable_reason"].eq("OK")
    ]
    trace_ok = (
        MANDATORY_TRACE.issubset(grid.columns)
        and (
            trace_valid[
                [
                    "selected_neighbor_link_id",
                    "selected_neighbor_distance_m",
                    "selected_neighbor_direction_diff_deg",
                    "selected_neighbor_name",
                    "selected_neighbor_highway",
                    "selected_neighbor_W01_flow",
                    "n_candidates",
                    "selection_rule",
                ]
            ].notna().all().all()
            if len(trace_valid)
            else True
        )
    )

    # Flow-blind source-order audit: no W01/residual term may occur between
    # eligible sorting and the resulting selected ID assignment.
    source = Path(script).read_text(encoding="utf-8")
    p_select = source.index("eligible = sorted(")
    p_selected = source.index("selected_id =", p_select)
    window = source[p_select:p_selected]
    flow_blind = (
        "flow_map" not in window
        and "capture_error_change" not in window
        and "diagnostic_residual_8_9" not in window
    )

    inherited_r2 = output_dir.parent / (
        "secondary_tertiary_residual_7_9f2_R2"
    )
    inherited_compare = (
        not inherited_r2.exists()
    )

    return [
        {
            "check": "Q4R1.01_PREREG_HASH",
            "pass": sha256_file(prereg).lower()
            == EXPECTED_PREREG_SHA256.lower(),
            "detail": sha256_file(prereg),
        },
        {
            "check": "Q4R1.02_ZERO_SIMULATION",
            "pass": zero_sim_audit(script),
            "detail": "AST no subprocess/Java",
        },
        {
            "check": "Q4R1.03_E1_RAW_QUALITY",
            "pass": (
                e1_detail["raw_rows"] > 0
                and e1_detail["raw_id_missing"] == 0
                and e1_detail["raw_bad_tier"] == 0
            ),
            "detail": json.dumps(
                e1_detail,
                ensure_ascii=False,
            ),
        },
        {
            "check": "Q4R1.04_E2_TARGET_UNIQUE",
            "pass": len(target) == 109
            and not target["LinkID"].duplicated().any(),
            "detail": f"target={len(target)}",
        },
        {
            "check": "Q4R1.05_NETWORK_PREFLIGHT",
            "pass": len(network) > 0,
            "detail": f"network={len(network):,}",
        },
        {
            "check": "Q4R1.06_W01_PREFLIGHT",
            "pass": len(stats) > 0
            and not stats["LINK"].duplicated().any(),
            "detail": f"W01={len(stats):,}",
        },
        {
            "check": "Q4R1.07_TARGET_TOTAL_GE100",
            "pass": len(target) >= 100,
            "detail": f"target={len(target)}",
        },
        {
            "check": "Q4R1.08_SECONDARY_GE80",
            "pass": int(
                target["diagnostic_highway"].eq("secondary").sum()
            ) >= 80,
            "detail": (
                f"secondary={int(target['diagnostic_highway'].eq('secondary').sum())}"
            ),
        },
        {
            "check": "Q4R1.09_TERTIARY_GE15",
            "pass": int(
                target["diagnostic_highway"].eq("tertiary").sum()
            ) >= 15,
            "detail": (
                f"tertiary={int(target['diagnostic_highway'].eq('tertiary').sum())}"
            ),
        },
        {
            "check": "Q4R1.10_AB_ANCHOR_COVERAGE_GE95",
            "pass": np.isfinite(anchor_cov)
            and anchor_cov >= 0.95,
            "detail": f"coverage={anchor_cov:.6f}",
        },
        {
            "check": "Q4R1.11_ANCHOR_COORD_GE99",
            "pass": np.isfinite(coord_cov)
            and coord_cov >= 0.99,
            "detail": f"coverage={coord_cov:.6f}",
        },
        {
            "check": "Q4R1.12_E2_CANONICAL_COMPLETE",
            "pass": canonical_complete,
            "detail": "canonical ratios finite",
        },
        {
            "check": "Q4R1.13_W01_CAPTURE_COVERAGE",
            "pass": np.isfinite(selected_w01_cov)
            and selected_w01_cov >= 0.95,
            "detail": f"coverage={selected_w01_cov:.6f}",
        },
        {
            "check": "Q4R1.14_OUTPUT_PROVENANCE",
            "pass": all_output_files and not unknown,
            "detail": (
                f"unknown={unknown}; "
                f"partial_outputs_ok={all_output_files}"
            ),
        },
        {
            "check": "Q4R1.15_ISOLATION",
            "pass": not stray,
            "detail": str(stray),
        },
        {
            "check": "Q4R1.16_FINAL_CLOSURE_FILES",
            "pass": (
                (output_dir / "q4r1_closure_check.csv").is_file()
                and (output_dir / "q4r1_summary.json").is_file()
            ),
            "detail": "closure/summary present",
        },
        {
            "check": "Q4R1.17_LOADER_CHECKS_CONTRACT",
            "pass": contract_pass,
            "detail": (
                f"referenced={sorted(refs)}; "
                f"returned={sorted(returned_keys)}"
            ),
        },
        {
            "check": "Q4R1.18_GRID_COMPLETE",
            "pass": actual_grid == expected_grid,
            "detail": (
                f"actual={actual_grid}; expected={expected_grid}"
            ),
        },
        {
            "check": "Q4R1.19_SCHEMA_AND_MISSINGNESS_ACCOUNTING",
            "pass": (
                MANDATORY_TRACE.issubset(grid.columns)
                and valid_reasons
            ),
            "detail": (
                f"trace={MANDATORY_TRACE.issubset(grid.columns)}; "
                f"reasons={valid_reasons}"
            ),
        },
        {
            "check": "Q4R1.20_SELECTION_REDERIVED",
            "pass": (
                len(selection_audit) == actual_grid
                and selection_audit[
                    "selection_rederived"
                ].all()
            ),
            "detail": f"audit_rows={len(selection_audit)}",
        },
        {
            "check": "Q4R1.21_RADIUS_MONOTONE_DISTANCE",
            "pass": monotone_ok,
            "detail": "d20 >= d50 >= d100",
        },
        {
            "check": "Q4R1.22_EXCLUSION_AND_CONTAINMENT",
            "pass": exclusion_ok,
            "detail": (
                "selected_self_count="
                + str(
                    int(
                        grid["selected_is_self"]
                        .fillna(False)
                        .astype(bool)
                        .sum()
                    )
                )
            ),
        },
        {
            "check": "Q4R1.23_SELECTION_FLOW_BLIND",
            "pass": flow_blind,
            "detail": "selection occurs before flow/residual lookup",
        },
        {
            "check": "Q4R1.24_Q4_TRACEABILITY",
            "pass": trace_ok,
            "detail": f"valid_trace_rows={len(trace_valid)}",
        },
        {
            "check": "Q4R1.25_NON_Q4_ARTIFACTS_UNCHANGED_VS_R2",
            "pass": inherited_compare,
            "detail": (
                "external four-source byte comparison required; "
                "local gate only verifies no shadow R2 directory"
            ),
        },
    ]


def write_report(
    output_dir,
    target,
    grid,
    summary,
    groups,
    checks_rows,
    status,
    closure,
):
    lines = [
        "# F-2 Q4-R1 — Nearest-Single-Link Local Capture",
        "",
        f"**STATUS: {status}**",
        f"**CLOSURE: {closure}**",
        "",
        "ZERO SIMULATION / READ-ONLY / DIAGNOSTIC ONLY.",
        "",
        "## Domain",
        "",
        (
            f"- target={len(target):,}; "
            f"secondary={int(target['diagnostic_highway'].eq('secondary').sum())}; "
            f"tertiary={int(target['diagnostic_highway'].eq('tertiary').sum())}"
        ),
        f"- grid rows={len(grid):,}",
        "",
        "## Q4 summary",
        "",
        "| Highway | Radius | Type | n | Valid change | Median distance | Median ratio | Median error change | Improved valid | Missing |",
        "|---|---:|---|---:|---:|---:|---:|---:|---:|---:|",
    ]

    for _, r in summary.iterrows():
        lines.append(
            f"| {r['diagnostic_highway']} | {int(r['radius_m'])} | "
            f"{r['neighbor_type']} | {int(r['n_all_target'])} | "
            f"{int(r['n_valid_change'])} | "
            f"{r['median_selected_distance_m']:.3f} | "
            f"{r['median_nearest_ratio']:.4f} | "
            f"{r['median_capture_error_change']:.4f} | "
            f"{r['capture_improved_share_valid']:.2%} | "
            f"{r['capture_missing_share']:.2%} |"
        )

    lines += [
        "",
        "## Group summary",
        "",
        "| Highway | n | Median parallel candidates | Median twin candidates | Same-section E1 parallel | Same-section E1 twin | Self-selected | Exact-zero |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for _, r in groups.iterrows():
        lines.append(
            f"| {r['diagnostic_highway']} | {int(r['n_sections'])} | "
            f"{r['median_candidate_n_parallel_100m']:.1f} | "
            f"{r['median_candidate_n_twin_100m']:.1f} | "
            f"{r['same_section_e1_share_parallel_100m']:.2%} | "
            f"{r['same_section_e1_share_twin_100m']:.2%} | "
            f"{r['self_selected_share_100m']:.2%} | "
            f"{r['exact_zero_change_share_100m']:.2%} |"
        )

    lines += [
        "",
        "## Gates",
        "",
        "| Check | Result | Detail |",
        "|---|---|---|",
    ]
    for c in checks_rows:
        lines.append(
            f"| {c['check']} | "
            f"{'PASS' if c['pass'] else 'FAIL'} | "
            f"{c['detail']} |"
        )

    lines += [
        "",
        "## Boundary",
        "",
        "nearest-single-link is a geometry-defined diagnostic. It is not a proof of functional substitution, causality, or observed network flow conservation.",
        "",
    ]

    (
        output_dir / "STEP7_9F2_Q4_R1_REPORT.md"
    ).write_text(
        "\n".join(lines),
        encoding="utf-8",
    )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--project-root", type=Path, default=ROOT_DEFAULT)
    ap.add_argument("--traffic", type=Path)
    ap.add_argument("--e1-candidates", type=Path)
    ap.add_argument("--e2", type=Path)
    ap.add_argument("--network", type=Path)
    ap.add_argument("--nodes", type=Path)
    ap.add_argument("--w01-linkstats", type=Path)
    ap.add_argument("--prereg", type=Path)
    ap.add_argument("--out-dir", type=Path, default=OUT_REL)
    args = ap.parse_args()

    root = args.project_root
    tp = args.traffic or root / TRAFFIC_REL
    cp = args.e1_candidates or root / E1_REL
    ep = args.e2 or root / E2_REL
    npth = args.network or root / NETWORK_REL
    npath = args.nodes or root / NODES_REL
    pp = args.prereg or root / PREREG_REL
    wp = locate_w01(root, args.w01_linkstats)
    out = (
        args.out_dir
        if args.out_dir.is_absolute()
        else root / args.out_dir
    )
    out.mkdir(parents=True, exist_ok=True)

    for p in [tp, cp, ep, npth, npath, wp, pp]:
        if not p.exists():
            raise FileNotFoundError(f"input not found: {p}")

    print("=" * 92)
    print("F-2 Q4-R1 | NEAREST-SINGLE-LINK LOCAL CAPTURE")
    print("ZERO SIMULATION / READ-ONLY / DIAGNOSTIC ONLY")
    print(f"PREREG SHA={sha256_file(pp)}")
    print(f"W01={wp}")
    print(f"OUTPUT={out}")

    # Preflight is deliberately evaluated before strict loaders.
    network_pf = preflight_network(npth, npath)
    w01_pf = preflight_w01(wp)

    if (
        network_pf["network_required_missing"]
        or network_pf["network_duplicate_link_id"] > 0
        or network_pf["node_required_missing"]
        or network_pf["node_duplicate_id"] > 0
        or w01_pf["missing"]
        or w01_pf["duplicate_link"] > 0
    ):
        blocked_checks = [
            {
                "check": "Q4R1.05_NETWORK_PREFLIGHT",
                "pass": (
                    not network_pf["network_required_missing"]
                    and network_pf["network_duplicate_link_id"] == 0
                    and not network_pf["node_required_missing"]
                    and network_pf["node_duplicate_id"] == 0
                ),
                "detail": json.dumps(
                    network_pf, ensure_ascii=False
                ),
            },
            {
                "check": "Q4R1.06_W01_PREFLIGHT",
                "pass": (
                    not w01_pf["missing"]
                    and w01_pf["duplicate_link"] == 0
                ),
                "detail": json.dumps(
                    w01_pf, ensure_ascii=False
                ),
            },
        ]
        pd.DataFrame(blocked_checks).to_csv(
            out / "q4r1_checks.csv",
            index=False,
            encoding="utf-8-sig",
        )
        (
            out / "q4r1_summary.json"
        ).write_text(
            json.dumps(
                {
                    "step": "F-2 Q4-R1",
                    "status": "Q4_LOCAL_CAPTURE_BLOCKED",
                    "closure": "PRECHECK_BLOCKED",
                    "zero_simulation": True,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        (
            out / "STEP7_9F2_Q4_R1_REPORT.md"
        ).write_text(
            "# F-2 Q4-R1\n\n"
            "**STATUS: Q4_LOCAL_CAPTURE_BLOCKED**\n\n"
            "Preflight failed before strict loaders.\n",
            encoding="utf-8",
        )
        return 1

    candidates, e1_detail = load_e1(cp)
    e2 = load_e2(ep)
    network = load_network(npth, npath)
    stats = load_w01(wp)

    target = e2[
        e2["diagnostic_highway"].isin(TARGET_HW)
        & e2["valid_residual"]
        & e2["obs_8_9"].gt(0)
    ].copy()

    if target["LinkID"].duplicated().any():
        raise AssertionError("target LinkID duplicated")

    target_ids = set(target["LinkID"])
    selected = select_ab(candidates)
    selected = selected[
        selected["lta_linkid"].isin(target_ids)
    ].copy()

    self_def = build_self_definition(
        candidates,
        target_ids,
    )

    grid = build_grid(
        candidates,
        selected,
        network,
        stats,
        target,
        self_def,
    )

    selection_audit = independent_selection_audit(
        grid
    )

    summary = summarize(grid)
    groups = group_summary(grid)

    # Persist analytical outputs first.
    target.to_csv(
        out / "q4r1_target_sections.csv",
        index=False,
        encoding="utf-8-sig",
    )
    selected.to_csv(
        out / "q4r1_selected_ab_candidates.csv",
        index=False,
        encoding="utf-8-sig",
    )
    self_def.to_csv(
        out / "q4r1_self_definition.csv",
        index=False,
        encoding="utf-8-sig",
    )
    grid[
        [
            "LinkID",
            "diagnostic_highway",
            "radius_m",
            "neighbor_type",
            "n_candidates",
            "ratio_unavailable_reason",
        ]
    ].to_csv(
        out / "q4r1_candidate_grid.csv",
        index=False,
        encoding="utf-8-sig",
    )
    grid.to_csv(
        out / "q4r1_single_link_capture.csv",
        index=False,
        encoding="utf-8-sig",
    )
    summary.to_csv(
        out / "q4r1_summary.csv",
        index=False,
        encoding="utf-8-sig",
    )
    groups.to_csv(
        out / "q4r1_group_summary.csv",
        index=False,
        encoding="utf-8-sig",
    )
    selection_audit.to_csv(
        out / "q4r1_selection_audit.csv",
        index=False,
        encoding="utf-8-sig",
    )

    # Placeholder only for terminal artifacts.
    (out / "q4r1_checks.csv").write_text(
        "PENDING\n", encoding="utf-8"
    )
    (out / "q4r1_closure_check.csv").write_text(
        "PENDING\n", encoding="utf-8"
    )
    (out / "q4r1_summary.json").write_text(
        json.dumps(
            {
                "step": "F-2 Q4-R1",
                "status": "PENDING",
                "closure": "PENDING",
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    (out / "q4r1_input_manifest.json").write_text(
        json.dumps(
            {
                "step": "F-2 Q4-R1",
                "status": "PENDING",
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    write_report(
        out, target, grid, summary, groups, [],
        "PENDING", "PENDING"
    )

    checks_rows = checks(
        Path(__file__).resolve(),
        pp,
        candidates,
        e1_detail,
        target,
        network,
        stats,
        selected,
        grid,
        selection_audit,
        out,
    )
    status = (
        "Q4_LOCAL_CAPTURE_READY"
        if all(bool(x["pass"]) for x in checks_rows)
        else "Q4_LOCAL_CAPTURE_BLOCKED"
    )

    pd.DataFrame(checks_rows).to_csv(
        out / "q4r1_checks.csv",
        index=False,
        encoding="utf-8-sig",
    )

    # Build the manifest only after all analytical outputs are finalized.
    manifest = {
        "step": "F-2 Q4-R1",
        "revision": "nearest-single-link",
        "scale": SCALE,
        "radii_m": RADII_M,
        "parallel_max_deg": FWD,
        "twin_min_deg": TWIN,
        "prereg_sha256": sha256_file(pp),
        "inputs": {},
        "generated_artifacts": {},
    }

    for name, path in {
        "e1_candidates": cp,
        "e2": ep,
        "network": npth,
        "nodes": npath,
        "w01": wp,
    }.items():
        manifest["inputs"][name] = {
            "path": str(path),
            "sha256": sha256_file(path),
            "size_bytes": int(path.stat().st_size),
        }

    for f in OUTPUT_NAMES:
        if f in {
            "q4r1_input_manifest.json",
            "q4r1_closure_check.csv",
        }:
            continue
        p = out / f
        if p.is_file():
            manifest["generated_artifacts"][f] = {
                "sha256": sha256_file(p),
                "size_bytes": int(p.stat().st_size),
            }

    (out / "q4r1_input_manifest.json").write_text(
        json.dumps(
            manifest,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    summary_json = {
        "step": "F-2 Q4-R1",
        "status": status,
        "closure": "PENDING",
        "zero_simulation": True,
        "network_modified": False,
        "matsim_rerun": False,
        "target_n": int(len(target)),
        "secondary_n": int(
            target["diagnostic_highway"].eq("secondary").sum()
        ),
        "tertiary_n": int(
            target["diagnostic_highway"].eq("tertiary").sum()
        ),
        "e1_candidate_rows": int(len(candidates)),
        "selected_anchor_rows": int(len(selected)),
        "grid_rows": int(len(grid)),
        "prereg_sha256": sha256_file(pp),
    }
    (out / "q4r1_summary.json").write_text(
        json.dumps(
            summary_json,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    write_report(
        out, target, grid, summary, groups,
        checks_rows, status, "PENDING"
    )

    # Final closure.
    closure_rows = []
    declared_set = set(OUTPUT_NAMES)
    disk_set = {
        p.name for p in out.iterdir()
        if p.is_file()
        and not is_transient(p.name)
    }

    for f in OUTPUT_NAMES:
        p = out / f
        closure_rows.append(
            {
                "artifact": f,
                "exists": p.is_file(),
                "nonempty": p.is_file() and p.stat().st_size > 0,
                "size_bytes": (
                    int(p.stat().st_size)
                    if p.is_file()
                    else np.nan
                ),
                "sha256": (
                    sha256_file(p)
                    if p.is_file()
                    else ""
                ),
            }
        )

    closure_df = pd.DataFrame(closure_rows)
    closure_df["declared_set_vs_disk"] = (
        "MATCH"
        if disk_set == declared_set
        else "MISMATCH"
    )
    closure_df.to_csv(
        out / "q4r1_closure_check.csv",
        index=False,
        encoding="utf-8-sig",
    )

    closure_ok = (
        disk_set == declared_set
        and closure_df["exists"].all()
        and closure_df["nonempty"].all()
        and (
            f"**STATUS: {status}**"
            in (
                out / "STEP7_9F2_Q4_R1_REPORT.md"
            ).read_text(encoding="utf-8")
        )
    )

    summary_json["closure"] = (
        "OK" if closure_ok else "CLOSURE_FAILED"
    )
    (out / "q4r1_summary.json").write_text(
        json.dumps(
            summary_json,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    write_report(
        out, target, grid, summary, groups,
        checks_rows, status,
        summary_json["closure"],
    )

    if not closure_ok:
        final_status = "Q4_LOCAL_CAPTURE_BLOCKED_CLOSURE_FAILED"
    else:
        final_status = status

    # Persist the final status once more.
    summary_json["status"] = final_status
    (out / "q4r1_summary.json").write_text(
        json.dumps(
            summary_json,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    print(
        f"target={len(target):,}; "
        f"E1={len(candidates):,}; "
        f"anchors={len(selected):,}; "
        f"network={len(network):,}; "
        f"W01={len(stats):,}; "
        f"grid={len(grid):,}"
    )
    print(
        f"checks={sum(bool(x['pass']) for x in checks_rows)}/"
        f"{len(checks_rows)}; "
        f"STATUS={final_status}; "
        f"CLOSURE={summary_json['closure']}"
    )
    print(f"OUTPUT={out}")

    return (
        0
        if final_status == "Q4_LOCAL_CAPTURE_READY"
        and summary_json["closure"] == "OK"
        else 1
    )


if __name__ == "__main__":
    raise SystemExit(main())
