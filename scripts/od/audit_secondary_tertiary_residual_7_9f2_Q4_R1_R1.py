#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""F-2 Q4-R1-R1 — Nearest-single-link local capture (4 neighbor types, 25 real gates).
ZERO SIMULATION / READ-ONLY / DIAGNOSTIC-ONLY.

Execution-layer revision of F-2 Q4-R1:
  * four frozen neighbor types, grid = 109 x 3 x 4 = 1308 cells;
  * gates 16 / 20 / 22 rebuilt as real independent checks;
  * gate 23 rebuilt as a structural AST audit;
  * gate 25 rebuilt as an executable eight-file R2 comparison;
  * BLOCKED materializes a complete, auditable node.

The nearest-single-link definition itself is unchanged.
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
    "reports/secondary_tertiary_residual_7_9f2_Q4_R1_R1"
)
PREREG_REL = Path(
    "reports/secondary_tertiary_residual_7_9f2_Q4_R1_R1_PREREG"
    "/PREREG_7_9F2_Q4_R1_R1.md"
)
R2_NODE_REL = Path(
    "reports/secondary_tertiary_residual_7_9f2_v2_1_R2"
)
INHERITED_DIR = "inherited_r2"

EXPECTED_PREREG_SHA256 = "82a03eb8aac0dc5d7ba610f8f0e3ba53e1cc1e0bd92ca00f60dbc8fdcd7c5f7f"

STEP_ID = "F-2 Q4-R1-R1"

SCALE = 459794.0 / 200000.0
A = "A_STRICT_SEMANTIC_DIRECTION"
B = "B_DIRECTION_GEOMETRY"
C = "C_GEOMETRY_ONLY"
TIERS = {A, B, C}
TARGET_HW = {"secondary", "tertiary"}
RADII_M = [20.0, 50.0, 100.0]
FWD = 30.0
TWIN = 150.0

NEIGHBOR_TYPES = [
    "parallel",
    "twin",
    "same_name_parallel",
    "same_name_twin",
]

# Names that must never be read while the selection is being decided.
BANNED_IN_SELECTION = {
    "flow_map",
    "HRS8-9avg",
    "obs",
    "canonical_ratio",
    "canonical_abs_error",
    "nearest_ratio",
    "nearest_abs_error",
    "capture_change",
    "improved",
    "diagnostic_residual_8_9",
}

# Eight non-Q4 inherited artifacts, frozen at the R2 node.
NON_Q4_INHERITED = {
    "f2v21r2_target_sections.csv": (
        "e7bd590fb0b49581f148b29b904426338f3aab8f0a59360fc4441a0ef76a5776",
        18767,
    ),
    "f2v21r2_all_e1_candidates.csv": (
        "89a83b29074690397465c870a92d9e2b735d6d64f5502f8c18d87e1a31ff23b7",
        929020,
    ),
    "f2v21r2_selected_ab_candidates.csv": (
        "159581fd953ead61a8894bf977dcd75d61f61ce9e5c386ff497c1eab1e428014",
        86519,
    ),
    "f2v21r2_direction_candidate_summary.csv": (
        "cff9fcd1113895ee0d4efff69eb06a815817ecc632c896f07e8c33c840f6c56e",
        21550,
    ),
    "f2v21r2_direction_candidate_long.csv": (
        "e69df9864237522ffaddd22ccf061e4c6eb002a204a9e9a9eedaea82d0563598",
        933721,
    ),
    "f2v21r2_q2_correlations.csv": (
        "fd4a8d084daf1d91b8a2ab77ad805b4ca30ab2ee2a504bf1004c1573a22b1d6e",
        303,
    ),
    "f2v21r2_group_summary.csv": (
        "d384f1148abdc7b293f654b38e2130194c2e6a50ddb4fc895a246be0c922b1e4",
        424,
    ),
    "f2v21r2_obs_rebuild_check.csv": (
        "5db00d70a035c8b6b0c465f58d968dc680470d58297c3bc306f14139dd7e00cc",
        2659,
    ),
}

# Artifacts this node also computes natively; they must be byte-identical to
# the frozen R2 copies (the real teeth of gate 25).
NON_Q4_LOCAL_PAIRS = {
    "q4r1r1_target_sections.csv": "f2v21r2_target_sections.csv",
    "q4r1r1_selected_ab_candidates.csv": (
        "f2v21r2_selected_ab_candidates.csv"
    ),
}

OUTPUT_NAMES = [
    "q4r1r1_target_sections.csv",
    "q4r1r1_selected_ab_candidates.csv",
    "q4r1r1_self_definition.csv",
    "q4r1r1_candidate_pool.csv",
    "q4r1r1_candidate_grid.csv",
    "q4r1r1_single_link_capture.csv",
    "q4r1r1_summary.csv",
    "q4r1r1_group_summary.csv",
    "q4r1r1_selection_audit.csv",
    "q4r1r1_r2_artifact_compare.csv",
    "q4r1r1_checks.csv",
    "q4r1r1_closure_check.csv",
    "q4r1r1_input_manifest.json",
    "q4r1r1_summary.json",
    "STEP7_9F2_Q4_R1_R1_REPORT.md",
]

# Artifacts written before any terminal file; they are never rewritten, so
# their manifest / closure / disk hashes are stable and comparable.
ANALYTICAL_NAMES = [
    "q4r1r1_target_sections.csv",
    "q4r1r1_selected_ab_candidates.csv",
    "q4r1r1_self_definition.csv",
    "q4r1r1_candidate_pool.csv",
    "q4r1r1_candidate_grid.csv",
    "q4r1r1_single_link_capture.csv",
    "q4r1r1_summary.csv",
    "q4r1r1_group_summary.csv",
    "q4r1r1_selection_audit.csv",
    "q4r1r1_r2_artifact_compare.csv",
]

CHECK_NAME = "q4r1r1_checks.csv"
CLOSURE_NAME = "q4r1r1_closure_check.csv"
MANIFEST_NAME = "q4r1r1_input_manifest.json"
SUMMARY_NAME = "q4r1r1_summary.json"
REPORT_NAME = "STEP7_9F2_Q4_R1_R1_REPORT.md"

TERMINAL_NAMES = [
    CHECK_NAME,
    CLOSURE_NAME,
    MANIFEST_NAME,
    SUMMARY_NAME,
    REPORT_NAME,
]

# Files that cannot be compared byte-wise against the manifest, because they
# are rewritten after it or cannot hash themselves. They are still covered by
# the declared-set equality of gate 16.
WRITEBACK_EXCLUDED = {CHECK_NAME, MANIFEST_NAME, CLOSURE_NAME}

# Terminal set of a blocked node: preflight failed before the analytical
# layer, so only the five terminal artifacts can exist.
BLOCKED_NAMES = [
    CHECK_NAME,
    CLOSURE_NAME,
    MANIFEST_NAME,
    SUMMARY_NAME,
    REPORT_NAME,
]

TRANSIENT_SUFFIXES = (".uploading.cfg", ".tmp")
TRANSIENT_PREFIXES = ("~$", ".~lock.")

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


def type_predicate(ntype):
    """Frozen four-type eligibility predicate (see prereg section 4)."""
    if ntype == "parallel":
        return lambda m: m["direction_diff_deg"] <= FWD
    if ntype == "twin":
        return lambda m: m["direction_diff_deg"] >= TWIN
    if ntype == "same_name_parallel":
        return lambda m: (
            m["direction_diff_deg"] <= FWD and m["same_name"]
        )
    if ntype == "same_name_twin":
        return lambda m: (
            m["direction_diff_deg"] >= TWIN and m["same_name"]
        )
    raise ValueError(f"unknown neighbor_type: {ntype}")


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
    pool_rows = []

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
            idx_pool = set()
            for _, fr in focal.iterrows():
                idx_pool.update(
                    tree.query_ball_point(
                        [
                            float(fr["mid_x"]),
                            float(fr["mid_y"]),
                        ],
                        radius,
                    )
                )

            meta = {}
            for idx in idx_pool:
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

                nmn = str(nr["name_norm"])
                meta[nid_value] = {
                    "distance_m": float(dmin),
                    "direction_diff_deg": float(hmin),
                    "name": nr["name"],
                    "name_norm": nmn,
                    "highway": nr["highway"],
                    "same_name": bool(nmn) and nmn in focal_names,
                }

            # Serialize the candidate evidence for this (sid, radius) cell.
            # Independent gate 20 reads only this table.
            for nid_value, m in sorted(meta.items()):
                pool_rows.append(
                    {
                        "LinkID": sid,
                        "radius_m": radius,
                        "candidate_link_id": nid_value,
                        "distance_m": m["distance_m"],
                        "direction_diff_deg": m["direction_diff_deg"],
                        "same_name": m["same_name"],
                        "name_norm": m["name_norm"],
                        "highway": m["highway"],
                    }
                )

            for ntype in NEIGHBOR_TYPES:
                pred = type_predicate(ntype)
                eligible = sorted(
                    [
                        nid_value
                        for nid_value, m in meta.items()
                        if pred(m)
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

    grid_df = pd.DataFrame(rows)
    pool_df = pd.DataFrame(
        pool_rows,
        columns=[
            "LinkID",
            "radius_m",
            "candidate_link_id",
            "distance_m",
            "direction_diff_deg",
            "same_name",
            "name_norm",
            "highway",
        ],
    )
    return grid_df, pool_df

def _independent_type_mask(p: pd.DataFrame, ntype: str) -> pd.Series:
    """Second implementation of the four-type predicate, written against the
    serialized candidate evidence only."""
    if ntype == "parallel":
        return p["direction_diff_deg"] <= FWD
    if ntype == "twin":
        return p["direction_diff_deg"] >= TWIN
    if ntype == "same_name_parallel":
        return (p["direction_diff_deg"] <= FWD) & p["same_name"]
    if ntype == "same_name_twin":
        return (p["direction_diff_deg"] >= TWIN) & p["same_name"]
    raise ValueError(f"unknown neighbor_type: {ntype}")


def independent_selection_audit(
    pool: pd.DataFrame,
    grid: pd.DataFrame,
) -> pd.DataFrame:
    """Independent re-derivation of Q4R1.20.

    Reads only `candidate_pool` (geometry), re-applies the four frozen type
    predicates, re-sorts by (distance_m, direction_diff_deg, candidate_link_id)
    and re-selects the top row of every cell. The stored selected id, distance
    and direction are used exclusively on the comparison side.
    """
    skel = (
        grid[["LinkID", "radius_m", "neighbor_type"]]
        .drop_duplicates()
        .copy()
    )

    p = pool.copy()
    if len(p):
        p["distance_m"] = pd.to_numeric(
            p["distance_m"], errors="coerce"
        )
        p["direction_diff_deg"] = pd.to_numeric(
            p["direction_diff_deg"], errors="coerce"
        )
        p["same_name"] = (
            p["same_name"]
            .astype(str).str.lower()
            .isin(["true", "1", "yes"])
        )
        p["candidate_link_id"] = p["candidate_link_id"].map(norm_id)

    tops = []
    counts = []
    for ntype in NEIGHBOR_TYPES:
        q = (
            p[_independent_type_mask(p, ntype)].copy()
            if len(p)
            else p.copy()
        )
        if len(q):
            c = (
                q.groupby(["LinkID", "radius_m"], sort=True)
                .size()
                .rename("n_eligible_rederived")
                .reset_index()
            )
            q2 = q.sort_values(
                [
                    "LinkID",
                    "radius_m",
                    "distance_m",
                    "direction_diff_deg",
                    "candidate_link_id",
                ],
                kind="mergesort",
            )
            t = (
                q2.groupby(["LinkID", "radius_m"], sort=False)
                .head(1)
                .copy()
            )
            t = t.rename(
                columns={
                    "candidate_link_id": "selected_rederived",
                    "distance_m": "distance_rederived",
                    "direction_diff_deg": "direction_rederived",
                }
            )
            t = t[
                [
                    "LinkID",
                    "radius_m",
                    "selected_rederived",
                    "distance_rederived",
                    "direction_rederived",
                ]
            ]
            t["neighbor_type"] = ntype
            tops.append(t)
        else:
            c = pd.DataFrame(
                columns=[
                    "LinkID",
                    "radius_m",
                    "n_eligible_rederived",
                ]
            )
        c["neighbor_type"] = ntype
        counts.append(c)

    empty_tops = pd.DataFrame(
        columns=[
            "LinkID",
            "radius_m",
            "selected_rederived",
            "distance_rederived",
            "direction_rederived",
            "neighbor_type",
        ]
    )
    empty_counts = pd.DataFrame(
        columns=[
            "LinkID",
            "radius_m",
            "n_eligible_rederived",
            "neighbor_type",
        ]
    )
    tops_df = pd.concat(tops, ignore_index=True) if tops else empty_tops
    counts_df = (
        pd.concat(counts, ignore_index=True) if counts else empty_counts
    )

    rec = grid[
        [
            "LinkID",
            "radius_m",
            "neighbor_type",
            "n_candidates",
            "selected_neighbor_link_id",
            "selected_neighbor_distance_m",
            "selected_neighbor_direction_diff_deg",
            "ratio_unavailable_reason",
        ]
    ].copy()
    rec = rec.rename(
        columns={
            "n_candidates": "n_candidates_recorded",
            "selected_neighbor_link_id": "selected_recorded",
            "selected_neighbor_distance_m": "distance_recorded",
            "selected_neighbor_direction_diff_deg": "direction_recorded",
        }
    )

    out = skel.merge(
        counts_df,
        on=["LinkID", "radius_m", "neighbor_type"],
        how="left",
    )
    out = out.merge(
        tops_df,
        on=["LinkID", "radius_m", "neighbor_type"],
        how="left",
    )
    out = out.merge(
        rec,
        on=["LinkID", "radius_m", "neighbor_type"],
        how="left",
    )

    out["n_eligible_rederived"] = (
        out["n_eligible_rederived"].fillna(0).astype(int)
    )
    out["n_candidates_recorded"] = (
        out["n_candidates_recorded"].fillna(-1).astype(int)
    )
    out["selected_rederived"] = out["selected_rederived"].map(norm_id)
    out["selected_recorded_n"] = out["selected_recorded"].map(
        lambda v: "" if pd.isna(v) else norm_id(v)
    )

    out["n_same"] = (
        out["n_eligible_rederived"] == out["n_candidates_recorded"]
    )
    out["selected_same"] = (
        out["selected_rederived"].astype(str)
        == out["selected_recorded_n"].astype(str)
    )

    dr = pd.to_numeric(out["distance_recorded"], errors="coerce")
    dv = pd.to_numeric(out["distance_rederived"], errors="coerce")
    out["abs_delta_distance_m"] = (dr - dv).abs()
    out["distance_same"] = (
        (dr.isna() & dv.isna())
        | (out["abs_delta_distance_m"] <= 1e-9)
    )

    rr = pd.to_numeric(out["direction_recorded"], errors="coerce")
    rv = pd.to_numeric(out["direction_rederived"], errors="coerce")
    out["abs_delta_direction_deg"] = (rr - rv).abs()
    out["direction_same"] = (
        (rr.isna() & rv.isna())
        | (out["abs_delta_direction_deg"] <= 1e-9)
    )

    out["agree"] = (
        out["n_same"]
        & out["selected_same"]
        & out["distance_same"]
        & out["direction_same"]
    )
    return out[
        [
            "LinkID",
            "radius_m",
            "neighbor_type",
            "n_candidates_recorded",
            "n_eligible_rederived",
            "n_same",
            "selected_recorded",
            "selected_rederived",
            "selected_same",
            "distance_recorded",
            "distance_rederived",
            "abs_delta_distance_m",
            "direction_recorded",
            "direction_rederived",
            "abs_delta_direction_deg",
            "distance_same",
            "direction_same",
            "agree",
        ]
    ]

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


def flow_blind_ast(script_path) -> tuple[bool, str]:
    """Structural audit of Q4R1.23.

    Finds the neighbor-type loop of build_grid, takes the statement range from
    the first body statement through the `selected_id` assignment, and checks
    that no flow / residual / ratio / change name is loaded inside it. Also
    checks that the first load of `flow_map` happens after that assignment.

    This is a structural AST check, not a character window: moving a reference
    outside a text window does not satisfy it.
    """
    src = Path(script_path).read_text(encoding="utf-8")
    tree = ast.parse(src)

    fn = None
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "build_grid":
            fn = node
            break
    if fn is None:
        return False, "build_grid not found"

    loop = None
    for node in ast.walk(fn):
        if isinstance(node, ast.For) and "ntype" in ast.dump(node.target):
            loop = node
            break
    if loop is None or not loop.body:
        return False, "neighbor-type loop not found"

    sel_stmt = None
    sel_lineno = None
    for stmt in loop.body:
        hit = False
        for sub in ast.walk(stmt):
            if isinstance(sub, ast.Assign) and any(
                isinstance(t, ast.Name) and t.id == "selected_id"
                for t in sub.targets
            ):
                hit = True
                sel_lineno = sub.lineno
        if hit:
            sel_stmt = stmt
            break
    if sel_stmt is None:
        return False, "selected_id assignment not found"

    region_names = set()
    start_line = loop.body[0].lineno
    for stmt in loop.body:
        if stmt.lineno > sel_lineno:
            break
        for sub in ast.walk(stmt):
            if isinstance(sub, ast.Name) and isinstance(sub.ctx, ast.Load):
                region_names.add(sub.id)
            elif isinstance(sub, ast.Attribute):
                region_names.add(sub.attr)
    hits = sorted(region_names & BANNED_IN_SELECTION)

    first_flow = None
    for sub in ast.walk(fn):
        if (
            isinstance(sub, ast.Name)
            and sub.id == "flow_map"
            and isinstance(sub.ctx, ast.Load)
        ):
            if first_flow is None or sub.lineno < first_flow:
                first_flow = sub.lineno

    order_ok = first_flow is not None and sel_lineno is not None and (
        first_flow > sel_lineno
    )
    ok = bool(not hits and order_ok)
    detail = (
        f"region_lines={start_line}-{sel_lineno}; "
        f"banned_hits={hits}; "
        f"first_flow_map_load_line={first_flow}; "
        f"flow_after_selection={order_ok}"
    )
    return ok, detail


def referenced_check_keys(checks_fn) -> tuple[set[str], str]:
    """AST extraction of every `e1_detail["<key>"]` subscript inside checks().

    Replaces the regex used by F-2 Q4-R1, whose double-escaped pattern
    (`\\\\[`) raised re.PatternError at run time while AST_PARSE_PASS and
    COMPILE_PASS both stayed True. AST extraction removes the whole defect
    class: there is no pattern to escape.
    """
    try:
        import textwrap

        src = textwrap.dedent(inspect.getsource(checks_fn))
        tree = ast.parse(src)
    except Exception as exc:  # pragma: no cover - defensive
        return set(), f"{type(exc).__name__}: {exc}"

    keys = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Subscript):
            v = node.value
            if isinstance(v, ast.Name) and v.id == "e1_detail":
                s = node.slice
                if isinstance(s, ast.Constant) and isinstance(s.value, str):
                    keys.add(s.value)
    return keys, ""


def build_r2_compare(out_dir, r2_dir) -> tuple[pd.DataFrame, dict]:
    """Gate 25 evidence table: eight non-Q4 artifacts, two directions."""
    rows = []
    summary = {
        "r2_dir": str(r2_dir),
        "r2_present": bool(r2_dir.is_dir()),
        "n_compared": 0,
        "n_identical": 0,
        "n_r2_frozen_ok": 0,
        "n_local_pairs": 0,
        "n_local_pairs_identical": 0,
        "missing": [],
        "local_pairs": {},
    }
    inherited_dir = out_dir / INHERITED_DIR

    for name, (frozen_sha, frozen_size) in NON_Q4_INHERITED.items():
        src = r2_dir / name
        exists = src.is_file()
        size_disk = int(src.stat().st_size) if exists else -1
        sha_disk = sha256_file(src) if exists else ""
        r2_frozen_ok = bool(
            exists and sha_disk == frozen_sha and size_disk == frozen_size
        )

        dst = inherited_dir / name
        if exists and not dst.is_file():
            inherited_dir.mkdir(parents=True, exist_ok=True)
            dst.write_bytes(src.read_bytes())
        size_loc = int(dst.stat().st_size) if dst.is_file() else -1
        sha_loc = sha256_file(dst) if dst.is_file() else ""
        local_ok = bool(
            dst.is_file() and sha_loc != "" and sha_loc == sha_disk
        )

        rows.append(
            {
                "kind": "inherited",
                "artifact": name,
                "exists_in_r2": exists,
                "size_bytes": size_disk,
                "size_frozen": frozen_size,
                "sha256_disk": sha_disk,
                "sha256_frozen": frozen_sha,
                "r2_frozen_match": r2_frozen_ok,
                "local_size_bytes": size_loc,
                "local_sha256": sha_loc,
                "local_match": local_ok,
                "note": "" if exists else "MISSING_IN_R2",
            }
        )
        summary["n_compared"] += 1
        summary["n_identical"] += int(local_ok)
        summary["n_r2_frozen_ok"] += int(r2_frozen_ok)
        if not exists:
            summary["missing"].append(name)

    # Real teeth: the two artifacts this node also computes natively must be
    # byte-identical to the frozen R2 copies.
    for local_name, r2_name in NON_Q4_LOCAL_PAIRS.items():
        lp = out_dir / local_name
        rp = r2_dir / r2_name
        sha_l = sha256_file(lp) if lp.is_file() else ""
        sha_r = sha256_file(rp) if rp.is_file() else ""
        ok = bool(sha_l and sha_r and sha_l == sha_r)
        summary["n_local_pairs"] += 1
        summary["n_local_pairs_identical"] += int(ok)
        summary["local_pairs"][local_name] = {
            "r2": r2_name,
            "local_sha256": sha_l,
            "r2_sha256": sha_r,
            "identical": ok,
        }
        rows.append(
            {
                "kind": "local_recompute",
                "artifact": f"{local_name} <-> {r2_name}",
                "exists_in_r2": rp.is_file(),
                "size_bytes": (
                    int(lp.stat().st_size) if lp.is_file() else -1
                ),
                "size_frozen": (
                    int(rp.stat().st_size) if rp.is_file() else -1
                ),
                "sha256_disk": sha_l,
                "sha256_frozen": sha_r,
                "r2_frozen_match": ok,
                "local_size_bytes": (
                    int(lp.stat().st_size) if lp.is_file() else -1
                ),
                "local_sha256": sha_l,
                "local_match": ok,
                "note": "native recompute vs frozen R2 copy",
            }
        )

    return pd.DataFrame(rows), summary


def build_manifest(out_dir, ctx, paths, r2_summary):
    gen = {}
    for f in ctx["declared_names"]:
        if f in {MANIFEST_NAME, CLOSURE_NAME}:
            continue
        p = out_dir / f
        if p.is_file():
            gen[f] = {
                "sha256": sha256_file(p),
                "size_bytes": int(p.stat().st_size),
            }

    inputs = {}
    for name, path in paths.items():
        if path is not None and Path(path).is_file():
            inputs[name] = {
                "path": str(path),
                "sha256": sha256_file(path),
                "size_bytes": int(Path(path).stat().st_size),
            }

    return {
        "step": STEP_ID,
        "revision": "nearest-single-link-4types",
        "scale": SCALE,
        "radii_m": RADII_M,
        "neighbor_types": NEIGHBOR_TYPES,
        "parallel_max_deg": FWD,
        "twin_min_deg": TWIN,
        "blocked": bool(ctx["blocked"]),
        "prereg_sha256": sha256_file(ctx["prereg"]),
        "inputs": inputs,
        "r2_comparison": r2_summary,
        "generated_artifacts": gen,
    }


def build_closure(out_dir, names, status, manifest_obj):
    gen = (manifest_obj or {}).get("generated_artifacts", {})
    rows = []
    for f in names:
        if f == CLOSURE_NAME:
            # A file cannot record its own hash or size, and a
            # self-referential size row keeps the terminal state from
            # converging. Its existence, non-emptiness and set membership
            # are covered by gate 16 and by the declared-set row below.
            continue
        p = out_dir / f
        ex = p.is_file()
        nb = bool(ex and p.stat().st_size > 0)
        size_disk = int(p.stat().st_size) if ex else -1
        sha_disk = sha256_file(p) if ex else ""
        rec = gen.get(f) if isinstance(gen, dict) else None
        excluded = f in WRITEBACK_EXCLUDED
        size_man = rec.get("size_bytes") if isinstance(rec, dict) else None
        sha_man = rec.get("sha256") if isinstance(rec, dict) else None
        rows.append(
            {
                "kind": "artifact",
                "artifact": f,
                "exists": ex,
                "nonempty": nb,
                "size_bytes": size_disk,
                "size_manifest": (
                    size_man if size_man is not None else ""
                ),
                "size_match": (
                    "" if excluded or size_man is None
                    else bool(size_man == size_disk)
                ),
                "sha256_disk": sha_disk,
                "sha256_manifest": sha_man if sha_man is not None else "",
                "sha_match": (
                    "" if excluded or sha_man is None
                    else bool(sha_man == sha_disk)
                ),
                "note": (
                    "excluded_from_byte_compare" if excluded else ""
                ),
            }
        )

    _cp = out_dir / CLOSURE_NAME
    rows.append(
        {
            "kind": "self_exclusion",
            "artifact": CLOSURE_NAME,
            "exists": _cp.is_file(),
            "nonempty": bool(
                _cp.is_file() and _cp.stat().st_size > 0
            ),
            "size_bytes": "",
            "size_manifest": "",
            "size_match": "",
            "sha256_disk": "",
            "sha256_manifest": "",
            "sha_match": "",
            "note": "cannot hash itself; verified by declared-set equality",
        }
    )

    disk_set = {
        p.name for p in out_dir.iterdir()
        if p.is_file() and not is_transient(p.name)
    }
    declared_set = set(names)
    set_ok = disk_set == declared_set
    rows.append(
        {
            "kind": "declared_count",
            "artifact": "declared_set_vs_disk",
            "exists": True,
            "nonempty": True,
            "size_bytes": len(declared_set),
            "size_manifest": len(disk_set),
            "size_match": set_ok,
            "sha256_disk": "",
            "sha256_manifest": "",
            "sha_match": "",
            "note": (
                f"missing={sorted(declared_set - disk_set)}; "
                f"extra={sorted(disk_set - declared_set)}"
            ),
        }
    )

    report_p = out_dir / REPORT_NAME
    report_text = (
        report_p.read_text(encoding="utf-8") if report_p.is_file() else ""
    )
    report_match = f"**STATUS: {status}**" in report_text
    summary_p = out_dir / SUMMARY_NAME
    summary_match = False
    if summary_p.is_file():
        try:
            summary_match = (
                json.loads(summary_p.read_text(encoding="utf-8")).get(
                    "status"
                )
                == status
            )
        except Exception:
            summary_match = False
    checks_all_pass = bool(
        all(bool(r["pass"]) for r in STATUS["checks_rows"])
        if STATUS["checks_rows"]
        else False
    )
    verdict_match = bool(
        (status == "Q4_LOCAL_CAPTURE_READY") == checks_all_pass
    )

    rows.append(
        {
            "kind": "status_consistency",
            "artifact": "report_status_match",
            "exists": report_p.is_file(),
            "nonempty": bool(report_text),
            "size_bytes": len(report_text),
            "size_manifest": "",
            "size_match": "",
            "sha256_disk": "",
            "sha256_manifest": "",
            "sha_match": report_match,
            "note": f"status={status}",
        }
    )
    rows.append(
        {
            "kind": "status_consistency",
            "artifact": "summary_status_match",
            "exists": summary_p.is_file(),
            "nonempty": bool(summary_p.is_file()),
            "size_bytes": "",
            "size_manifest": "",
            "size_match": "",
            "sha256_disk": "",
            "sha256_manifest": "",
            "sha_match": summary_match,
            "note": f"status={status}",
        }
    )
    rows.append(
        {
            "kind": "status_consistency",
            "artifact": "checks_vs_verdict",
            "exists": True,
            "nonempty": True,
            "size_bytes": "",
            "size_manifest": "",
            "size_match": "",
            "sha256_disk": "",
            "sha256_manifest": "",
            "sha_match": verdict_match,
            "note": f"checks_all_pass={checks_all_pass}",
        }
    )

    artifact_rows = [
        r for r in rows if r["kind"] == "artifact"
    ]
    closure_ok = bool(
        set_ok
        and artifact_rows
        and all(r["exists"] for r in artifact_rows)
        and all(r["nonempty"] for r in artifact_rows)
        and report_match
        and summary_match
        and verdict_match
    )
    rows.append(
        {
            "kind": "closure_verdict",
            "artifact": "CLOSURE_OK" if closure_ok else "CLOSURE_FAILED",
            "exists": True,
            "nonempty": True,
            "size_bytes": len(artifact_rows),
            "size_manifest": "",
            "size_match": "",
            "sha256_disk": "",
            "sha256_manifest": "",
            "sha_match": closure_ok,
            "note": f"status={status}",
        }
    )
    return pd.DataFrame(rows), closure_ok


# Filled by main() so build_closure can audit checks-vs-verdict consistency
# without threading the table through every call.
STATUS = {"checks_rows": []}


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
    pool,
    selection_audit,
    r2_compare,
    r2_summary,
    output_dir,
    declared_names,
    analytical_written,
    network_pf,
    w01_pf,
    blocked,
):
    na = "NOT_EVALUATED: preflight blocked"

    if blocked:
        rows = []
        net_ok = bool(
            not network_pf["network_required_missing"]
            and network_pf["network_duplicate_link_id"] == 0
            and not network_pf["node_required_missing"]
            and network_pf["node_duplicate_id"] == 0
        )
        w01_ok = bool(
            not w01_pf["missing"] and w01_pf["duplicate_link"] == 0
        )
        refs, contract_err = referenced_check_keys(checks)
        existing = {
            p.name for p in output_dir.iterdir() if p.is_file()
        }
        unknown = sorted(
            x for x in existing
            if x not in OUTPUT_NAMES and not is_transient(x)
        )
        disk_set = {
            p.name for p in output_dir.iterdir()
            if p.is_file() and not is_transient(p.name)
        }
        set_ok = disk_set == set(declared_names)
        manifest_p = output_dir / MANIFEST_NAME
        manifest_obj = None
        if manifest_p.is_file() and manifest_p.stat().st_size > 0:
            try:
                manifest_obj = json.loads(
                    manifest_p.read_text(encoding="utf-8")
                )
            except Exception:
                manifest_obj = None
        gen = (manifest_obj or {}).get("generated_artifacts", {})
        cmp_names = [
            f for f in declared_names if f not in WRITEBACK_EXCLUDED
        ]
        mismatch = []
        for f in cmp_names:
            p = output_dir / f
            if not p.is_file() or p.stat().st_size <= 0:
                mismatch.append(f"{f}:missing")
                continue
            rec = gen.get(f) if isinstance(gen, dict) else None
            if not isinstance(rec, dict):
                mismatch.append(f"{f}:absent_in_manifest")
                continue
            if sha256_file(p) != rec.get("sha256"):
                mismatch.append(f"{f}:manifest_sha")
            if int(p.stat().st_size) != rec.get("size_bytes"):
                mismatch.append(f"{f}:manifest_size")
        manifest_set_ok = set(gen.keys()) == (
            set(declared_names) - {MANIFEST_NAME, CLOSURE_NAME}
        )
        terminal_ok = all(
            (output_dir / f).is_file()
            and (output_dir / f).stat().st_size > 0
            for f in TERMINAL_NAMES
        )
        wb_ok = bool(
            manifest_obj is not None
            and manifest_set_ok
            and set_ok
            and not mismatch
            and terminal_ok
        )

        rows.append(
            {
                "check": "Q4R1.01_PREREG_HASH",
                "pass": sha256_file(prereg).lower()
                == EXPECTED_PREREG_SHA256.lower(),
                "detail": sha256_file(prereg),
            }
        )
        rows.append(
            {
                "check": "Q4R1.02_ZERO_SIMULATION",
                "pass": zero_sim_audit(script),
                "detail": "AST no subprocess/Java",
            }
        )
        for i, name in enumerate(
            [
                "Q4R1.03_E1_RAW_QUALITY",
                "Q4R1.04_E2_TARGET_UNIQUE",
            ]
        ):
            rows.append({"check": name, "pass": False, "detail": na})
        rows.append(
            {
                "check": "Q4R1.05_NETWORK_PREFLIGHT",
                "pass": net_ok,
                "detail": json.dumps(network_pf, ensure_ascii=False),
            }
        )
        rows.append(
            {
                "check": "Q4R1.06_W01_PREFLIGHT",
                "pass": w01_ok,
                "detail": json.dumps(w01_pf, ensure_ascii=False),
            }
        )
        for name in [
            "Q4R1.07_TARGET_TOTAL_GE100",
            "Q4R1.08_SECONDARY_GE80",
            "Q4R1.09_TERTIARY_GE15",
            "Q4R1.10_AB_ANCHOR_COVERAGE_GE95",
            "Q4R1.11_ANCHOR_COORD_GE99",
            "Q4R1.12_E2_CANONICAL_COMPLETE",
            "Q4R1.13_W01_CAPTURE_COVERAGE",
        ]:
            rows.append({"check": name, "pass": False, "detail": na})
        rows.append(
            {
                "check": "Q4R1.14_OUTPUT_PROVENANCE",
                "pass": not unknown,
                "detail": (
                    f"unknown={unknown}; blocked_node_no_analytical_layer"
                ),
            }
        )
        rows.append(
            {
                "check": "Q4R1.15_ISOLATION",
                "pass": not _isolation_stray(output_dir),
                "detail": str(_isolation_stray(output_dir)),
            }
        )
        rows.append(
            {
                "check": "Q4R1.16_WRITEBACK_VERIFICATION",
                "pass": wb_ok,
                "detail": (
                    f"manifest_set_ok={manifest_set_ok}; set_ok={set_ok}; "
                    f"mismatch={mismatch}; terminal_ok={terminal_ok}"
                ),
            }
        )
        rows.append(
            {
                "check": "Q4R1.17_LOADER_CHECKS_CONTRACT",
                "pass": bool(not contract_err and refs),
                "detail": f"referenced={sorted(refs)}; err={contract_err}",
            }
        )
        for name in [
            "Q4R1.18_GRID_COMPLETE",
            "Q4R1.19_SCHEMA_AND_MISSINGNESS_ACCOUNTING",
            "Q4R1.20_SELECTION_REDERIVED",
            "Q4R1.21_RADIUS_MONOTONE_DISTANCE",
            "Q4R1.22_EXCLUSION_AND_CONTAINMENT",
            "Q4R1.23_SELECTION_FLOW_BLIND_STATIC",
            "Q4R1.24_Q4_TRACEABILITY",
            "Q4R1.25_NON_Q4_ARTIFACTS_UNCHANGED_VS_R2",
        ]:
            rows.append({"check": name, "pass": False, "detail": na})
        return rows

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
    canonical_complete = bool(np.isfinite(canonical).all())
    selected_w01_cov = (
        selected["matsim_link_id"].isin(set(stats["LINK"])).mean()
        if len(selected) else np.nan
    )

    existing = {
        p.name for p in output_dir.iterdir() if p.is_file()
    }
    unknown = sorted(
        x for x in existing
        if x not in OUTPUT_NAMES and not is_transient(x)
    )
    analytical_ok = all(
        (output_dir / x).is_file()
        and (output_dir / x).stat().st_size > 0
        for x in ANALYTICAL_NAMES
    )
    stray = _isolation_stray(output_dir)

    refs, contract_err = referenced_check_keys(checks)
    returned_keys = set(e1_detail.keys())
    contract_pass = bool(
        not contract_err and refs and refs.issubset(returned_keys)
    )

    expected_grid = len(target) * len(RADII_M) * len(NEIGHBOR_TYPES)
    actual_grid = (
        grid[["LinkID", "radius_m", "neighbor_type"]]
        .drop_duplicates()
        .shape[0]
    )

    valid_reasons = set(
        grid["ratio_unavailable_reason"].astype(str)
    ).issubset({"OK", "NO_CANDIDATE", "SELECTED_LINK_NOT_IN_W01"})

    monotone_ok = True
    mono_viol = 0
    for sid, ntype in (
        grid[["LinkID", "neighbor_type"]].drop_duplicates().itertuples(index=False)
    ):
        g = grid[
            grid["LinkID"].eq(sid)
            & grid["neighbor_type"].eq(ntype)
        ].set_index("radius_m")
        if not all(r in g.index for r in RADII_M):
            continue
        vals = [
            g.loc[r, "selected_neighbor_distance_m"]
            for r in RADII_M
            if pd.notna(g.loc[r, "selected_neighbor_distance_m"])
        ]
        if len(vals) >= 2 and not all(
            vals[i] >= vals[i + 1] for i in range(len(vals) - 1)
        ):
            monotone_ok = False
            mono_viol += 1

    # ---- gate 20: independent re-derivation -------------------------------
    rederived_rows = int(len(selection_audit))
    rederived_agree = bool(
        rederived_rows > 0 and bool(selection_audit["agree"].all())
    )
    rederived_ok = bool(rederived_rows == actual_grid and rederived_agree)
    max_dd = (
        float(
            pd.to_numeric(
                selection_audit["abs_delta_distance_m"], errors="coerce"
            ).max()
        )
        if rederived_rows else float("nan")
    )
    max_ddeg = (
        float(
            pd.to_numeric(
                selection_audit["abs_delta_direction_deg"], errors="coerce"
            ).max()
        )
        if rederived_rows else float("nan")
    )
    n_bad_cells = int((~selection_audit["agree"]).sum()) if rederived_rows else -1

    # ---- gate 22: independent exclusion + containment ---------------------
    self_rows = []
    for sid, g in e1[
        e1["lta_linkid"].isin(target_ids)
    ].groupby("lta_linkid", sort=True):
        q = g.sort_values(
            ["distance_m", "direction_diff_deg", "tier", "matsim_link_id"],
            ascending=[True, True, True, True],
            kind="mergesort",
        ).iloc[0]
        self_rows.append(
            {"LinkID": sid, "self_independent": norm_id(q["matsim_link_id"])}
        )
    self_ind = {r["LinkID"]: r["self_independent"] for r in self_rows}

    sel_norm = grid["selected_neighbor_link_id"].map(
        lambda v: "" if pd.isna(v) else norm_id(v)
    )
    sid_norm = grid["LinkID"].astype(str)
    self_per_row = sid_norm.map(lambda s: self_ind.get(s, ""))
    self_viol = int(((sel_norm.ne("")) & (sel_norm.eq(self_per_row))).sum())

    anchor_sets = (
        selected.groupby("lta_linkid")["matsim_link_id"]
        .apply(set).to_dict()
    )
    anchor_viol = int(
        sum(
            1 for sid, s in zip(sid_norm, sel_norm)
            if s != "" and s in anchor_sets.get(str(sid), set())
        )
    )

    pool_self_viol = 0
    pool_anchor_viol = 0
    contain_viol = 0
    if len(pool):
        pool_cand = pool["candidate_link_id"].map(norm_id)
        pool_sid = pool["LinkID"].astype(str)
        pool_self = pool_sid.map(lambda s: self_ind.get(s, ""))
        pool_self_viol = int(
            ((pool_self != "") & (pool_cand == pool_self)).sum()
        )
        pool_anchor_viol = int(
            sum(
                1 for sid, c in zip(pool_sid, pool_cand)
                if c != "" and c in anchor_sets.get(sid, set())
            )
        )
        for sid, g in pool.assign(_c=pool_cand).groupby(
            "LinkID", sort=False
        ):
            by_r = {
                r: set(g.loc[g["radius_m"].eq(r), "_c"]) for r in RADII_M
            }
            if not (by_r[20.0] <= by_r[50.0] <= by_r[100.0]):
                contain_viol += 1

    type_contain_viol = 0
    if rederived_rows:
        for (sid, ntype), g in selection_audit.groupby(
            ["LinkID", "neighbor_type"], sort=False
        ):
            g2 = g.set_index("radius_m")
            if all(r in g2.index for r in RADII_M):
                v = [
                    int(g2.loc[r, "n_eligible_rederived"])
                    for r in RADII_M
                ]
                if not (v[0] <= v[1] <= v[2]):
                    type_contain_viol += 1

    exclusion_ok = bool(
        self_viol == 0
        and anchor_viol == 0
        and pool_self_viol == 0
        and pool_anchor_viol == 0
        and contain_viol == 0
        and type_contain_viol == 0
    )

    trace_valid = grid[grid["ratio_unavailable_reason"].eq("OK")]
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

    flow_blind_ok, flow_blind_detail = flow_blind_ast(script)

    # ---- gate 25 ---------------------------------------------------------
    n_inh = len(NON_Q4_INHERITED)
    gate25_ok = bool(
        r2_summary["r2_present"]
        and r2_summary["n_identical"] == n_inh
        and r2_summary["n_r2_frozen_ok"] == n_inh
        and not r2_summary["missing"]
        and r2_summary["n_local_pairs"] > 0
        and r2_summary["n_local_pairs_identical"]
        == r2_summary["n_local_pairs"]
    )

    # ---- gate 16 ---------------------------------------------------------
    manifest_p = output_dir / MANIFEST_NAME
    manifest_obj = None
    m_err = ""
    if manifest_p.is_file() and manifest_p.stat().st_size > 0:
        try:
            manifest_obj = json.loads(
                manifest_p.read_text(encoding="utf-8")
            )
        except Exception as exc:
            m_err = str(exc)
    gen = (manifest_obj or {}).get("generated_artifacts", {})
    manifest_set_ok = bool(
        isinstance(gen, dict)
        and set(gen.keys())
        == (set(declared_names) - {MANIFEST_NAME, CLOSURE_NAME})
    )

    closure_p = output_dir / CLOSURE_NAME
    declared_closure = set()
    if closure_p.is_file() and closure_p.stat().st_size > 0:
        try:
            cdf = pd.read_csv(closure_p, encoding="utf-8-sig")
            if {"kind", "artifact"} <= set(cdf.columns):
                declared_closure = set(
                    cdf.loc[cdf["kind"].eq("artifact"), "artifact"]
                    .astype(str)
                )
        except Exception:
            declared_closure = set()
    closure_set_ok = bool(
        declared_closure == set(declared_names) - {CLOSURE_NAME}
    )

    disk_set = {
        p.name for p in output_dir.iterdir()
        if p.is_file() and not is_transient(p.name)
    }
    disk_set_ok = bool(disk_set == set(declared_names))

    cmp_names = [
        f for f in declared_names if f not in WRITEBACK_EXCLUDED
    ]
    mismatch = []
    for f in cmp_names:
        p = output_dir / f
        if not p.is_file() or p.stat().st_size <= 0:
            mismatch.append(f"{f}:missing")
            continue
        rec = gen.get(f) if isinstance(gen, dict) else None
        if not isinstance(rec, dict):
            mismatch.append(f"{f}:absent_in_manifest")
            continue
        if sha256_file(p) != rec.get("sha256"):
            mismatch.append(f"{f}:manifest_sha")
        if int(p.stat().st_size) != rec.get("size_bytes"):
            mismatch.append(f"{f}:manifest_size")
    terminal_ok = all(
        (output_dir / f).is_file()
        and (output_dir / f).stat().st_size > 0
        for f in TERMINAL_NAMES
    )
    writeback_ok = bool(
        manifest_obj is not None
        and not m_err
        and manifest_set_ok
        and closure_set_ok
        and disk_set_ok
        and not mismatch
        and terminal_ok
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
            "detail": json.dumps(e1_detail, ensure_ascii=False),
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
            "pass": len(stats) > 0 and not stats["LINK"].duplicated().any(),
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
                f"secondary="
                f"{int(target['diagnostic_highway'].eq('secondary').sum())}"
            ),
        },
        {
            "check": "Q4R1.09_TERTIARY_GE15",
            "pass": int(
                target["diagnostic_highway"].eq("tertiary").sum()
            ) >= 15,
            "detail": (
                f"tertiary="
                f"{int(target['diagnostic_highway'].eq('tertiary').sum())}"
            ),
        },
        {
            "check": "Q4R1.10_AB_ANCHOR_COVERAGE_GE95",
            "pass": np.isfinite(anchor_cov) and anchor_cov >= 0.95,
            "detail": f"coverage={anchor_cov:.6f}",
        },
        {
            "check": "Q4R1.11_ANCHOR_COORD_GE99",
            "pass": np.isfinite(coord_cov) and coord_cov >= 0.99,
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
            "pass": bool(analytical_ok and not unknown),
            "detail": (
                f"unknown={unknown}; analytical_ok={analytical_ok}"
            ),
        },
        {
            "check": "Q4R1.15_ISOLATION",
            "pass": not stray,
            "detail": str(stray),
        },
        {
            "check": "Q4R1.16_WRITEBACK_VERIFICATION",
            "pass": writeback_ok,
            "detail": (
                f"manifest_set_ok={manifest_set_ok}; "
                f"closure_set_ok={closure_set_ok}; "
                f"disk_set_ok={disk_set_ok}; "
                f"byte_mismatch={mismatch}; "
                f"terminal_ok={terminal_ok}; "
                f"n_byte_compared={len(cmp_names)}; "
                f"err={m_err or 'none'}"
            ),
        },
        {
            "check": "Q4R1.17_LOADER_CHECKS_CONTRACT",
            "pass": contract_pass,
            "detail": (
                f"referenced={sorted(refs)}; "
                f"returned={sorted(returned_keys)}; err={contract_err}"
            ),
        },
        {
            "check": "Q4R1.18_GRID_COMPLETE",
            "pass": actual_grid == expected_grid,
            "detail": (
                f"actual={actual_grid}; expected={expected_grid} "
                f"({len(target)}x{len(RADII_M)}x{len(NEIGHBOR_TYPES)})"
            ),
        },
        {
            "check": "Q4R1.19_SCHEMA_AND_MISSINGNESS_ACCOUNTING",
            "pass": (
                MANDATORY_TRACE.issubset(grid.columns) and valid_reasons
            ),
            "detail": (
                f"trace={MANDATORY_TRACE.issubset(grid.columns)}; "
                f"reasons={valid_reasons}"
            ),
        },
        {
            "check": "Q4R1.20_SELECTION_REDERIVED",
            "pass": rederived_ok,
            "detail": (
                f"cells_rederived={rederived_rows}; "
                f"cells_expected={actual_grid}; "
                f"mismatched_cells={n_bad_cells}; "
                f"max_abs_delta_distance_m={max_dd:.3e}; "
                f"max_abs_delta_direction_deg={max_ddeg:.3e}"
            ),
        },
        {
            "check": "Q4R1.21_RADIUS_MONOTONE_DISTANCE",
            "pass": monotone_ok,
            "detail": (
                f"d20>=d50>=d100; violating_cells={mono_viol}"
            ),
        },
        {
            "check": "Q4R1.22_EXCLUSION_AND_CONTAINMENT",
            "pass": exclusion_ok,
            "detail": (
                f"self_violations={self_viol}; "
                f"anchor_violations={anchor_viol}; "
                f"pool_self_violations={pool_self_viol}; "
                f"pool_anchor_violations={pool_anchor_viol}; "
                f"radius_containment_violations={contain_viol}; "
                f"type_containment_violations={type_contain_viol}"
            ),
        },
        {
            "check": "Q4R1.23_SELECTION_FLOW_BLIND_STATIC",
            "pass": flow_blind_ok,
            "detail": flow_blind_detail,
        },
        {
            "check": "Q4R1.24_Q4_TRACEABILITY",
            "pass": trace_ok,
            "detail": f"valid_trace_rows={len(trace_valid)}",
        },
        {
            "check": "Q4R1.25_NON_Q4_ARTIFACTS_UNCHANGED_VS_R2",
            "pass": gate25_ok,
            "detail": (
                f"identical={r2_summary['n_identical']}/"
                f"{r2_summary['n_compared']}; "
                f"r2_frozen_ok={r2_summary['n_r2_frozen_ok']}/"
                f"{r2_summary['n_compared']}; "
                f"local_recompute_identical="
                f"{r2_summary['n_local_pairs_identical']}/"
                f"{r2_summary['n_local_pairs']}; "
                f"missing={r2_summary['missing']}"
            ),
        },
    ]


def _isolation_stray(output_dir) -> list:
    """No Q4-R1-R1 artifact may appear in any earlier node directory."""
    stray = []
    parent = output_dir.parent
    node_name = output_dir.name
    prereg_node = node_name + "_PREREG"
    for folder in sorted(parent.iterdir()):
        if not folder.is_dir():
            continue
        n = folder.name
        if not n.startswith("secondary_tertiary_residual_7_9f2"):
            continue
        if n in {node_name, prereg_node}:
            continue
        for p in folder.iterdir():
            if p.is_file() and (
                p.name.startswith("q4r1r1_") or "Q4_R1_R1" in p.name
            ):
                stray.append(str(p))
    return stray

def write_summary(out_dir, payload, checks_rows):
    n_pass = sum(bool(r["pass"]) for r in checks_rows)
    doc = {
        "step": STEP_ID,
        "status": payload["status"],
        "closure": payload["closure"],
        "zero_simulation": True,
        "network_modified": False,
        "matsim_rerun": False,
        "blocked": bool(payload["blocked"]),
        "gates_passed": int(n_pass),
        "gates_total": int(len(checks_rows)),
        "prereg_sha256": payload["prereg_sha256"],
    }
    if not payload["blocked"]:
        target = payload["target"]
        grid = payload["grid"]
        rs = payload.get("r2_summary") or {}
        doc.update(
            {
                "target_n": int(len(target)),
                "secondary_n": int(
                    target["diagnostic_highway"].eq("secondary").sum()
                ),
                "tertiary_n": int(
                    target["diagnostic_highway"].eq("tertiary").sum()
                ),
                "grid_rows": int(len(grid)),
                "neighbor_types": NEIGHBOR_TYPES,
                "selection_rederived": payload.get("redev") or {},
                "r2_compare": {
                    "identical": rs.get("n_identical"),
                    "compared": rs.get("n_compared"),
                    "r2_frozen_ok": rs.get("n_r2_frozen_ok"),
                    "local_recompute_identical": rs.get(
                        "n_local_pairs_identical"
                    ),
                    "local_recompute_total": rs.get("n_local_pairs"),
                },
            }
        )
    (out_dir / SUMMARY_NAME).write_bytes(
        json.dumps(doc, ensure_ascii=False, indent=2).encode("utf-8")
    )


def write_report(output_dir, payload, checks_rows):
    lines = [
        "# F-2 Q4-R1-R1 — Nearest-Single-Link Local Capture",
        "",
        f"**STATUS: {payload['status']}**",
        f"**CLOSURE: {payload['closure']}**",
        "",
        "ZERO SIMULATION / READ-ONLY / DIAGNOSTIC ONLY.",
        "",
        f"PREREG SHA256: `{payload['prereg_sha256']}`",
        "",
        (
            "Neighbor types (4, frozen): "
            + ", ".join(f"`{t}`" for t in NEIGHBOR_TYPES)
        ),
        "",
    ]

    if payload["blocked"]:
        lines += [
            "## BLOCKED",
            "",
            "Preflight failed before the strict loaders. This is still a",
            "complete, auditable node: all 25 gate rows are present and the",
            "unevaluated gates are marked explicitly.",
            "",
        ]
    else:
        target = payload["target"]
        summary = payload["summary"]
        groups = payload["groups"]
        redev = payload.get("redev") or {}
        lines += [
            "## Domain",
            "",
            (
                f"- target={len(target):,}; "
                f"secondary="
                f"{int(target['diagnostic_highway'].eq('secondary').sum())}; "
                f"tertiary="
                f"{int(target['diagnostic_highway'].eq('tertiary').sum())}"
            ),
            f"- grid rows={len(payload['grid']):,}",
            "",
            "## Q4 summary",
            "",
            "| Highway | Radius | Type | n | Valid change | Median "
            "distance | Median ratio | Median error change | Improved valid "
            "| Missing |",
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
            "## Group summary (name-agnostic types, 100 m)",
            "",
            "| Highway | n | Median parallel candidates | Median twin "
            "candidates | Same-section E1 parallel | Same-section E1 twin | "
            "Self-selected | Exact-zero |",
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
            "## Gate evidence",
            "",
            f"- Q4R1.20 independent re-derivation: cells={redev.get('cells')}; "
            f"mismatched={redev.get('mismatched_cells')}; "
            f"max|delta distance|={redev.get('max_abs_delta_distance_m')}; "
            f"max|delta direction|="
            f"{redev.get('max_abs_delta_direction_deg')}",
            f"- Q4R1.25 R2 comparison: see `{CLOSURE_NAME}` and "
            "`q4r1r1_r2_artifact_compare.csv`",
            "",
        ]

    lines += [
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
        "nearest-single-link is a geometry-defined diagnostic. The selected "
        "link is the geometrically closest known link, not a functionally "
        "comparable link; in most cells it is the target section's own "
        "lower-tier E1 candidate. This node does not establish functional "
        "substitution, causality, or observed network flow conservation.",
        "",
        f"Write-back verification and status closure: `{CLOSURE_NAME}`.",
        "",
    ]

    (output_dir / REPORT_NAME).write_bytes(
        "\n".join(lines).encode("utf-8")
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
    ap.add_argument("--r2-node", type=Path, default=R2_NODE_REL)
    args = ap.parse_args()

    root = args.project_root
    tp = args.traffic or root / TRAFFIC_REL
    cp = args.e1_candidates or root / E1_REL
    ep = args.e2 or root / E2_REL
    npth = args.network or root / NETWORK_REL
    npath = args.nodes or root / NODES_REL
    pp = args.prereg or root / PREREG_REL
    r2d = (
        args.r2_node
        if args.r2_node.is_absolute()
        else root / args.r2_node
    )
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

    script = Path(__file__).resolve()
    print("=" * 92)
    print(
        "F-2 Q4-R1-R1 | NEAREST-SINGLE-LINK LOCAL CAPTURE "
        "(4 types, 25 real gates)"
    )
    print("ZERO SIMULATION / READ-ONLY / DIAGNOSTIC ONLY")
    print(f"PREREG SHA={sha256_file(pp)}")
    print(f"R2 NODE={r2d}")
    print(f"W01={wp}")
    print(f"OUTPUT={out}")

    # Preflight is evaluated before the strict loaders, and a failing
    # preflight still materializes a complete node.
    network_pf = preflight_network(npth, npath)
    w01_pf = preflight_w01(wp)
    blocked = bool(
        network_pf["network_required_missing"]
        or network_pf["network_duplicate_link_id"] > 0
        or network_pf["node_required_missing"]
        or network_pf["node_duplicate_id"] > 0
        or w01_pf["missing"]
        or w01_pf["duplicate_link"] > 0
    )

    declared = list(BLOCKED_NAMES) if blocked else list(OUTPUT_NAMES)
    paths = {
        "e1_candidates": cp,
        "e2": ep,
        "network": npth,
        "nodes": npath,
        "w01": wp,
    }

    payload = {
        "blocked": blocked,
        "target": None,
        "summary": None,
        "groups": None,
        "grid": None,
        "redev": {},
        "r2_summary": {},
        "prereg_sha256": sha256_file(pp),
        "status": "PENDING",
        "closure": "PENDING",
    }
    ctx = {
        "script": script,
        "prereg": pp,
        "e1": None,
        "e1_detail": {"blocked": True},
        "target": None,
        "network": None,
        "stats": None,
        "selected": None,
        "grid": None,
        "pool": None,
        "selection_audit": None,
        "r2_compare": pd.DataFrame(),
        "r2_summary": {
            "r2_dir": str(r2d),
            "r2_present": False,
            "n_compared": 0,
            "n_identical": 0,
            "n_r2_frozen_ok": 0,
            "n_local_pairs": 0,
            "n_local_pairs_identical": 0,
            "missing": [],
            "local_pairs": {},
        },
        "output_dir": out,
        "declared_names": declared,
        "analytical_written": not blocked,
        "network_pf": network_pf,
        "w01_pf": w01_pf,
        "blocked": blocked,
    }

    if not blocked:
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
        self_def = build_self_definition(candidates, target_ids)

        grid, pool = build_grid(
            candidates,
            selected,
            network,
            stats,
            target,
            self_def,
        )
        selection_audit = independent_selection_audit(pool, grid)
        summary = summarize(grid)
        groups = group_summary(grid)

        # Persist analytical outputs first; they are never rewritten.
        target.to_csv(
            out / "q4r1r1_target_sections.csv",
            index=False,
            encoding="utf-8-sig",
        )
        selected.to_csv(
            out / "q4r1r1_selected_ab_candidates.csv",
            index=False,
            encoding="utf-8-sig",
        )
        self_def.to_csv(
            out / "q4r1r1_self_definition.csv",
            index=False,
            encoding="utf-8-sig",
        )
        pool.to_csv(
            out / "q4r1r1_candidate_pool.csv",
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
            out / "q4r1r1_candidate_grid.csv",
            index=False,
            encoding="utf-8-sig",
        )
        grid.to_csv(
            out / "q4r1r1_single_link_capture.csv",
            index=False,
            encoding="utf-8-sig",
        )
        summary.to_csv(
            out / "q4r1r1_summary.csv",
            index=False,
            encoding="utf-8-sig",
        )
        groups.to_csv(
            out / "q4r1r1_group_summary.csv",
            index=False,
            encoding="utf-8-sig",
        )
        selection_audit.to_csv(
            out / "q4r1r1_selection_audit.csv",
            index=False,
            encoding="utf-8-sig",
        )

        r2_compare, r2_summary = build_r2_compare(out, r2d)
        r2_compare.to_csv(
            out / "q4r1r1_r2_artifact_compare.csv",
            index=False,
            encoding="utf-8-sig",
        )

        redev = {
            "cells": int(len(selection_audit)),
            "mismatched_cells": int((~selection_audit["agree"]).sum()),
            "max_abs_delta_distance_m": float(
                pd.to_numeric(
                    selection_audit["abs_delta_distance_m"],
                    errors="coerce",
                ).max()
            ),
            "max_abs_delta_direction_deg": float(
                pd.to_numeric(
                    selection_audit["abs_delta_direction_deg"],
                    errors="coerce",
                ).max()
            ),
        }

        ctx.update(
            {
                "e1": candidates,
                "e1_detail": e1_detail,
                "target": target,
                "network": network,
                "stats": stats,
                "selected": selected,
                "grid": grid,
                "pool": pool,
                "selection_audit": selection_audit,
                "r2_compare": r2_compare,
                "r2_summary": r2_summary,
            }
        )
        payload.update(
            {
                "target": target,
                "summary": summary,
                "groups": groups,
                "grid": grid,
                "redev": redev,
                "r2_summary": r2_summary,
            }
        )

    # Terminal state is a fixed point: checks -> report -> summary ->
    # manifest -> closure, repeated until the byte state stops moving.
    prev_state = None
    prev_closure = "PENDING"
    final_checks = []
    final_status = "PENDING"
    final_closure = "PENDING"
    converged = False
    iterations = 0

    for iterations in range(1, 7):
        STATUS["checks_rows"] = []
        rows = checks(**ctx)
        STATUS["checks_rows"] = rows
        status = (
            "Q4_LOCAL_CAPTURE_READY"
            if all(bool(r["pass"]) for r in rows)
            else "Q4_LOCAL_CAPTURE_BLOCKED"
        )
        pd.DataFrame(rows).to_csv(
            out / CHECK_NAME,
            index=False,
            encoding="utf-8-sig",
        )

        payload["status"] = status
        payload["closure"] = prev_closure
        write_report(out, payload, rows)
        write_summary(out, payload, rows)

        manifest = build_manifest(out, ctx, paths, ctx["r2_summary"])
        (out / MANIFEST_NAME).write_bytes(
            json.dumps(
                manifest, ensure_ascii=False, indent=2
            ).encode("utf-8")
        )

        closure_df, closure_ok = build_closure(
            out, declared, status, manifest
        )
        closure_df.to_csv(
            out / CLOSURE_NAME,
            index=False,
            encoding="utf-8-sig",
        )

        final_closure = "OK" if closure_ok else "CLOSURE_FAILED"
        state = (
            sha256_file(out / CHECK_NAME),
            sha256_file(out / REPORT_NAME),
            sha256_file(out / SUMMARY_NAME),
            sha256_file(out / MANIFEST_NAME),
            sha256_file(out / CLOSURE_NAME),
            status,
            closure_ok,
        )
        final_checks = rows
        final_status = status

        if state == prev_state:
            converged = True
            break
        prev_state = state
        prev_closure = final_closure

    print(f"converged={converged}; iterations={iterations}")
    if not payload["blocked"]:
        print(
            f"target={len(payload['target']):,}; "
            f"E1={len(ctx['e1']):,}; "
            f"anchors={len(ctx['selected']):,}; "
            f"network={len(ctx['network']):,}; "
            f"W01={len(ctx['stats']):,}; "
            f"grid={len(payload['grid']):,}"
        )
        print(
            "redev: cells={cells}; mismatched={mismatched_cells}; "
            "max|dd|={max_abs_delta_distance_m}; "
            "max|ddeg|={max_abs_delta_direction_deg}".format(
                **payload["redev"]
            )
        )
        rs = ctx["r2_summary"]
        print(
            f"r2_compare: identical={rs['n_identical']}/"
            f"{rs['n_compared']}; "
            f"local_recompute={rs['n_local_pairs_identical']}/"
            f"{rs['n_local_pairs']}"
        )
    print(
        f"checks={sum(bool(x['pass']) for x in final_checks)}/"
        f"{len(final_checks)}; STATUS={final_status}; "
        f"CLOSURE={final_closure}"
    )
    print(f"OUTPUT={out}")

    ok = bool(
        converged
        and final_status == "Q4_LOCAL_CAPTURE_READY"
        and final_closure == "OK"
    )
    return 0 if ok else 1

if __name__ == "__main__":
    raise SystemExit(main())
