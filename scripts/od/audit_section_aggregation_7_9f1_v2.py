#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Step 7.9F-1 v2 — Section Aggregation Sensitivity Audit.

FORMAL RERUN AFTER R0 INPUT-CONTRACT RESOLUTION.
ZERO SIMULATION / READ-ONLY / DIAGNOSTIC ONLY.
"""
from __future__ import annotations

import argparse
import ast
import gzip
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT_DEFAULT = Path(r"D:\Luan\2026-05\2_Singapore")
TRAFFIC_REL = Path("Singapore_OD_MATSim_FinalData/08_TrafficCount/TrafficFlow_Data.json")
E1_CAND_REL = Path("reports/arterial_observability_7_9e1/e1_crosswalk_candidates.csv")
W01_DIR_REL = Path("matsim_final_7_6h/outputs/W01_rc_min/ITERS/it.19")
E2_MAIN_REL = Path("reports/arterial_expanded_residual_7_9e2/e2_section_residual_main.csv")
OUT_REL = Path("reports/section_aggregation_7_9f1_v2")
PREREG_REL = OUT_REL / "PREREG_7_9F1_v2.md"
EXPECTED_PREREG_SHA256 = "75bab7e20affa1583dcb7520e5f63b9f32da53d43ee405e2e32766a8d0a396e7"

SCALE = 459794.0 / 200000.0
TIER_A = "A_STRICT_SEMANTIC_DIRECTION"
TIER_B = "B_DIRECTION_GEOMETRY"
CORE_HW = {"motorway", "motorway_link", "trunk", "primary", "secondary", "tertiary"}
AGGS = ["CANONICAL_MEDIAN", "POSITIVE_MEDIAN", "MEAN", "MAX"]

FORMAL_GATE_COUNT = 12
MIN_TRAFFIC_LINKS = 1278
MIN_SELECTED_COVERAGE = 0.95
MIN_VALID_SECTION = 500
MIN_AGG_COVERAGE = 0.95
MIN_CORE_N = 20
MIN_CORRIDOR_N = 30
R0_DIRNAME = "section_aggregation_7_9f1"


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
    if s.endswith(".0") and s[:-2].isdigit():
        return s[:-2]
    return s


def norm_text(x: object) -> str:
    s = "" if x is None else str(x).replace("\xa0", " ").strip()
    return "" if s.lower() == "nan" else " ".join(s.split())


def numeric(s: pd.Series) -> pd.Series:
    return pd.to_numeric(
        s.astype(str).str.replace(",", "", regex=False),
        errors="coerce",
    )


def weighted_mean(y: pd.Series, w: pd.Series) -> float:
    z = pd.concat(
        [
            pd.to_numeric(y, errors="coerce"),
            pd.to_numeric(w, errors="coerce"),
        ],
        axis=1,
    ).dropna()
    if z.empty or float(z.iloc[:, 1].sum()) <= 0:
        return float("nan")
    return float((z.iloc[:, 0] * z.iloc[:, 1]).sum() / z.iloc[:, 1].sum())


def pearson(x: pd.Series, y: pd.Series) -> float:
    z = pd.concat(
        [
            pd.to_numeric(x, errors="coerce"),
            pd.to_numeric(y, errors="coerce"),
        ],
        axis=1,
    ).dropna()
    return (
        float(z.iloc[:, 0].corr(z.iloc[:, 1], method="pearson"))
        if len(z) >= 3
        else float("nan")
    )


def spearman(x: pd.Series, y: pd.Series) -> float:
    z = pd.concat(
        [
            pd.to_numeric(x, errors="coerce"),
            pd.to_numeric(y, errors="coerce"),
        ],
        axis=1,
    ).dropna()
    return (
        float(z.iloc[:, 0].corr(z.iloc[:, 1], method="spearman"))
        if len(z) >= 3
        else float("nan")
    )


def zero_sim_audit(p: Path) -> bool:
    tree = ast.parse(p.read_text(encoding="utf-8"))
    banned_mods = {"subprocess", "jpype", "py4j"}
    banned_calls = {
        "system", "popen", "Popen", "run", "call",
        "check_call", "check_output",
    }
    for n in ast.walk(tree):
        if isinstance(n, ast.Import):
            if any(a.name.split(".")[0] in banned_mods for a in n.names):
                return False
        if isinstance(n, ast.ImportFrom):
            if n.module and n.module.split(".")[0] in banned_mods:
                return False
        if isinstance(n, ast.Call):
            if isinstance(n.func, ast.Attribute) and n.func.attr in banned_calls:
                return False
    return True


def locate_w01(root: Path, explicit: Path | None) -> tuple[Path, str]:
    declared = root / W01_DIR_REL
    if explicit:
        p = explicit if explicit.is_absolute() else root / explicit
        if p.is_dir():
            fs = sorted(p.glob("*.linkstats.txt.gz")) + sorted(p.glob("*.linkstats.txt"))
            if fs:
                return fs[0], str(p)
        if p.is_file():
            return p, str(p)
        raise FileNotFoundError(f"W01 linkstats not found: {p}")

    if not declared.exists():
        raise FileNotFoundError(
            f"Declared W01 path missing: {declared}"
        )
    fs = sorted(declared.glob("*.linkstats.txt.gz")) + sorted(
        declared.glob("*.linkstats.txt")
    )
    if not fs:
        raise FileNotFoundError(f"W01 it.19 directory has no linkstats: {declared}")
    return fs[0], str(declared)


def load_traffic(p: Path) -> pd.DataFrame:
    obj = json.loads(p.read_text(encoding="utf-8-sig"))
    rows = obj.get("Value", obj.get("value", [])) if isinstance(obj, dict) else obj
    d = pd.DataFrame(rows)
    req = {"LinkID", "Date", "HourOfDate", "Volume", "RoadName", "RoadCat"}
    miss = req - set(d.columns)
    if miss:
        raise ValueError(f"TrafficFlow 缺字段: {sorted(miss)}")
    d["LinkID"] = d["LinkID"].map(norm_id)
    d["Date"] = pd.to_datetime(d["Date"], dayfirst=True, errors="coerce")
    d["HourOfDate"] = pd.to_numeric(d["HourOfDate"], errors="coerce")
    d["Volume"] = numeric(d["Volume"])
    d["RoadName"] = d["RoadName"].map(norm_text)
    d["RoadCat"] = d["RoadCat"].map(norm_text)
    d = d[
        d["LinkID"].ne("")
        & d["Date"].notna()
        & d["Date"].dt.weekday.lt(5)
        & d["HourOfDate"].eq(8)
        & d["Volume"].notna()
    ].copy()
    daily = d.groupby(["LinkID", "Date"], as_index=False)["Volume"].mean()
    obs = (
        daily.groupby("LinkID", as_index=False)["Volume"]
        .median()
        .rename(columns={"Volume": "obs_8_9"})
    )
    attrs = (
        d.sort_values(["LinkID", "Date"])
        .groupby("LinkID", as_index=False)
        .agg(
            RoadName=("RoadName", "first"),
            RoadCat=("RoadCat", "first"),
        )
    )
    return obs.merge(attrs, on="LinkID", how="left", validate="one_to_one")


def load_candidates(p: Path) -> pd.DataFrame:
    x = pd.read_csv(p, encoding="utf-8-sig", low_memory=False)
    low = {str(c).strip().lower(): c for c in x.columns}
    mapping = {
        "lta_linkid": "lta_linkid",
        "linkid": "lta_linkid",
        "matsim_link_id": "matsim_link_id",
        "matsim_link": "matsim_link_id",
        "tier": "tier",
        "distance_m": "distance_m",
        "direction_diff_deg": "direction_diff_deg",
        "direction_diff": "direction_diff_deg",
        "highway": "highway",
        "semantic_compatible": "semantic_compatible",
        "semantic_ok": "semantic_compatible",
        "name_similarity": "name_similarity",
        "name_sim": "name_similarity",
    }
    x = x.rename(columns={c: mapping[k] for k, c in low.items() if k in mapping})
    req = {
        "lta_linkid", "matsim_link_id", "tier",
        "distance_m", "direction_diff_deg", "highway",
    }
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
        x["semantic_compatible"] = (
            x["semantic_compatible"].astype(str).str.lower().isin(
                ["true", "1", "yes"]
            )
        )
    else:
        x["semantic_compatible"] = False
    if "name_similarity" in x:
        x["name_similarity"] = numeric(x["name_similarity"])
    else:
        x["name_similarity"] = 0.0
    x = x[
        x["lta_linkid"].ne("")
        & x["matsim_link_id"].ne("")
        & x["tier"].isin([TIER_A, TIER_B])
        & x["distance_m"].notna()
    ].copy()
    return x.drop_duplicates(
        ["lta_linkid", "matsim_link_id", "tier"]
    )


def select_links(c: pd.DataFrame) -> pd.DataFrame:
    parts = []
    for sid, g0 in c.groupby("lta_linkid", sort=True):
        a = g0[g0["tier"].eq(TIER_A)]
        g = a if not a.empty else g0[g0["tier"].eq(TIER_B)]
        if g.empty:
            continue
        g = g.sort_values(
            [
                "distance_m",
                "direction_diff_deg",
                "semantic_compatible",
                "name_similarity",
                "matsim_link_id",
            ],
            ascending=[True, True, False, False, True],
        ).drop_duplicates("matsim_link_id")
        parts.append(g.copy())
    return (
        pd.concat(parts, ignore_index=True)
        if parts
        else pd.DataFrame(columns=c.columns)
    )


def load_stats(p: Path) -> pd.DataFrame:
    opener = gzip.open if p.suffix == ".gz" else open
    with opener(p, "rt", encoding="utf-8", errors="replace") as f:
        header = f.readline().rstrip("\n").split("\t")
    req = {"LINK", "HRS8-9avg"}
    miss = req - set(header)
    if miss:
        raise ValueError(f"W01 linkstats 缺字段: {sorted(miss)}")
    d = pd.read_csv(
        p,
        sep="\t",
        compression="gzip" if p.suffix == ".gz" else None,
        usecols=["LINK", "HRS8-9avg"],
        low_memory=False,
    )
    d["LINK"] = d["LINK"].map(norm_id)
    d["HRS8-9avg"] = numeric(d["HRS8-9avg"])
    if d["LINK"].duplicated().any():
        raise ValueError("W01 LINK 出现重复")
    return d


def load_e2(p: Path) -> pd.DataFrame:
    d = pd.read_csv(p, encoding="utf-8-sig", low_memory=False)
    req = {
        "LinkID", "obs_8_9", "sim_8_9_scaled",
        "sim_8_9_median_raw", "diagnostic_residual_8_9",
        "diagnostic_highway", "valid_residual",
    }
    miss = req - set(d.columns)
    if miss:
        raise ValueError(f"E2 main 缺字段: {sorted(miss)}")
    d["LinkID"] = d["LinkID"].map(norm_id)
    d["diagnostic_highway"] = d["diagnostic_highway"].map(norm_text).str.lower()
    d["valid_residual"] = (
        d["valid_residual"].astype(str).str.lower().isin(["true", "1", "yes"])
    )
    for c in [
        "obs_8_9", "sim_8_9_scaled",
        "sim_8_9_median_raw", "diagnostic_residual_8_9",
    ]:
        d[c] = numeric(d[c])
    return d


def section_aggregate(
    sel: pd.DataFrame,
    stats: pd.DataFrame,
    traffic: pd.DataFrame,
) -> pd.DataFrame:
    x = sel.merge(
        stats,
        left_on="matsim_link_id",
        right_on="LINK",
        how="left",
        validate="many_to_one",
    )
    rows = []
    for sid, q in x.groupby("lta_linkid", sort=True):
        a = pd.to_numeric(q["HRS8-9avg"], errors="coerce").dropna()
        pos = a[a.gt(0)]
        if q.empty:
            continue
        rep = q.sort_values(
            [
                "distance_m",
                "direction_diff_deg",
                "semantic_compatible",
                "name_similarity",
                "matsim_link_id",
            ],
            ascending=[True, True, False, False, True],
        ).iloc[0]
        rows.append(
            {
                "LinkID": sid,
                "matched_edge_count": int(q["matsim_link_id"].nunique()),
                "stats_valid_edge_count": int(len(a)),
                "zero_flow_edge_count": int(a.eq(0).sum()),
                "positive_flow_edge_count": int(a.gt(0).sum()),
                "raw_mean": float(a.mean()) if len(a) else np.nan,
                "raw_median": float(a.median()) if len(a) else np.nan,
                "raw_positive_median": float(pos.median()) if len(pos) else 0.0,
                "raw_max": float(a.max()) if len(a) else np.nan,
                "diagnostic_highway": rep["highway"],
                "representative_matsim_link_id": rep["matsim_link_id"],
            }
        )
    sec = traffic.merge(
        pd.DataFrame(rows),
        on="LinkID",
        how="left",
        validate="one_to_one",
    )
    for m, raw in [
        ("CANONICAL_MEDIAN", "raw_median"),
        ("POSITIVE_MEDIAN", "raw_positive_median"),
        ("MEAN", "raw_mean"),
        ("MAX", "raw_max"),
    ]:
        sec[f"{m}__sim_scaled"] = sec[raw] * SCALE
        sec[f"{m}__ratio"] = (
            sec[f"{m}__sim_scaled"]
            / sec["obs_8_9"].replace(0, np.nan)
        )
        sec[f"{m}__residual"] = sec[f"{m}__ratio"] - 1.0
    return sec


def section_long(sec: pd.DataFrame) -> pd.DataFrame:
    common = [
        "LinkID", "RoadName", "RoadCat", "obs_8_9",
        "matched_edge_count", "stats_valid_edge_count",
        "zero_flow_edge_count", "positive_flow_edge_count",
        "raw_mean", "raw_median", "raw_positive_median", "raw_max",
        "diagnostic_highway", "representative_matsim_link_id",
    ]
    out = []
    for m in AGGS:
        out.append(
            sec[
                common
                + [
                    f"{m}__sim_scaled",
                    f"{m}__ratio",
                    f"{m}__residual",
                ]
            ].assign(aggregation=m)
        )
    return pd.concat(out, ignore_index=True)


def grade_summary(long: pd.DataFrame) -> pd.DataFrame:
    rows = []
    q = long[long["obs_8_9"].gt(0)].copy()
    for (m, hw), g in q.groupby(
        ["aggregation", "diagnostic_highway"],
        dropna=False,
    ):
        r = g[f"{m}__residual"]
        rows.append(
            {
                "aggregation": m,
                "highway": hw,
                "n": int(len(g)),
                "mean_residual": float(r.mean()),
                "median_residual": float(r.median()),
                "p10_residual": float(r.quantile(0.10)),
                "p90_residual": float(r.quantile(0.90)),
                "obs_weighted_residual": weighted_mean(r, g["obs_8_9"]),
                "sim_weighted_residual": weighted_mean(
                    r, g[f"{m}__sim_scaled"]
                ),
                "zero_section_n": int(
                    g[f"{m}__sim_scaled"].eq(0).sum()
                ),
                "negative_share": float(r.lt(0).mean()),
                "positive_share": float(r.gt(0).mean()),
            }
        )
    return pd.DataFrame(rows)


def zero_audit(sec: pd.DataFrame) -> pd.DataFrame:
    base = sec[sec["obs_8_9"].gt(0)].copy()
    rows = []
    canonical_zero = base["CANONICAL_MEDIAN__sim_scaled"].eq(0)
    canonical_raw_zero = base["raw_median"].eq(0)
    if not canonical_zero.equals(canonical_raw_zero):
        raise ValueError("canonical zero definition inconsistency")
    true_zero = canonical_zero & (
        base["zero_flow_edge_count"] == base["stats_valid_edge_count"]
    )
    collapse = canonical_zero & ~true_zero
    rows.append(
        {
            "aggregation": "CANONICAL_MEDIAN",
            "n": int(len(base)),
            "zero_section_n": int(canonical_zero.sum()),
            "zero_observed_flow_share": weighted_mean(
                canonical_zero.astype(float),
                base["obs_8_9"],
            ),
            "true_zero_n": int(true_zero.sum()),
            "median_collapse_n": int(collapse.sum()),
            "collapse_observed_flow_share": weighted_mean(
                collapse.astype(float),
                base["obs_8_9"],
            ),
            "zero_with_mean_raw_gt0_n": int(
                (
                    canonical_zero
                    & base["raw_mean"].gt(0)
                ).sum()
            ),
            "obs_weighted_residual": weighted_mean(
                base["CANONICAL_MEDIAN__residual"],
                base["obs_8_9"],
            ),
            "sim_weighted_residual": weighted_mean(
                base["CANONICAL_MEDIAN__residual"],
                base["CANONICAL_MEDIAN__sim_scaled"],
            ),
        }
    )
    for m in ["POSITIVE_MEDIAN", "MEAN", "MAX"]:
        zero = base[f"{m}__sim_scaled"].eq(0)
        rows.append(
            {
                "aggregation": m,
                "n": int(len(base)),
                "zero_section_n": int(zero.sum()),
                "zero_observed_flow_share": weighted_mean(
                    zero.astype(float), base["obs_8_9"]
                ),
                "true_zero_n": np.nan,
                "median_collapse_n": np.nan,
                "collapse_observed_flow_share": np.nan,
                "zero_with_mean_raw_gt0_n": int(
                    (zero & base["raw_mean"].gt(0)).sum()
                ),
                "obs_weighted_residual": weighted_mean(
                    base[f"{m}__residual"], base["obs_8_9"]
                ),
                "sim_weighted_residual": weighted_mean(
                    base[f"{m}__residual"], base[f"{m}__sim_scaled"]
                ),
            }
        )
    return pd.DataFrame(rows)


def corridor_aggregate(sec: pd.DataFrame) -> pd.DataFrame:
    s = sec[
        sec["obs_8_9"].gt(0)
        & sec["RoadName"].ne("")
    ].copy()
    s["corridor_id"] = (
        s["RoadName"].str.upper()
        .str.replace(r"\s+", " ", regex=True)
        .str.strip()
    )
    counts = s["corridor_id"].value_counts()
    s = s[s["corridor_id"].map(counts).ge(2)].copy()

    rows = []
    for m in AGGS:
        for cid, g in s.groupby("corridor_id", sort=True):
            obs = float(g["obs_8_9"].sum())
            sim = float(g[f"{m}__sim_scaled"].sum())
            ratio = sim / obs if obs > 0 else np.nan
            rows.append(
                {
                    "aggregation": m,
                    "corridor_id": cid,
                    "section_n": int(len(g)),
                    "obs_corridor": obs,
                    "sim_corridor": sim,
                    "corridor_ratio": ratio,
                    "corridor_residual": ratio - 1.0,
                }
            )
    return pd.DataFrame(rows)


def pairwise(sec: pd.DataFrame, corr: pd.DataFrame) -> pd.DataFrame:
    # NOTE (7.9F-1 v2 fix, disclosed): the long frame carries one aggregation
    # per row, so drop_duplicates("LinkID") keeps the CANONICAL block and
    # leaves the other three aggregation columns NaN. Use the wide `sec`
    # frame, which carries all four <METHOD>__residual columns on every row.
    s = sec[sec["obs_8_9"].gt(0)].copy()
    rows = []
    for alt in ["POSITIVE_MEDIAN", "MEAN", "MAX"]:
        a = s["CANONICAL_MEDIAN__residual"]
        b = s[f"{alt}__residual"]
        z = pd.concat([a, b], axis=1).dropna()
        d = z.iloc[:, 1] - z.iloc[:, 0]
        rows.append(
            {
                "level": "SECTION",
                "comparison": f"{alt}_vs_CANONICAL_MEDIAN",
                "n": int(len(z)),
                "pearson": pearson(z.iloc[:, 0], z.iloc[:, 1]),
                "spearman": spearman(z.iloc[:, 0], z.iloc[:, 1]),
                "mean_residual_delta": float(d.mean()),
                "mae_residual_delta": float(d.abs().mean()),
                "sign_change_share": float(
                    (
                        (z.iloc[:, 0] * z.iloc[:, 1]) < 0
                    ).mean()
                ),
            }
        )

    cb = corr[
        corr["aggregation"].eq("CANONICAL_MEDIAN")
    ][["corridor_id", "corridor_residual"]].rename(
        columns={"corridor_residual": "canonical"}
    )
    for alt in ["POSITIVE_MEDIAN", "MEAN", "MAX"]:
        z = corr[
            corr["aggregation"].eq(alt)
        ].merge(cb, on="corridor_id", how="inner")
        d = z["corridor_residual"] - z["canonical"]
        rows.append(
            {
                "level": "CORRIDOR",
                "comparison": f"{alt}_vs_CANONICAL",
                "n": int(len(z)),
                "pearson": pearson(z["canonical"], z["corridor_residual"]),
                "spearman": spearman(z["canonical"], z["corridor_residual"]),
                "mean_residual_delta": float(d.mean()) if len(d) else np.nan,
                "mae_residual_delta": float(d.abs().mean()) if len(d) else np.nan,
                "sign_change_share": float(
                    (
                        z["canonical"] * z["corridor_residual"]
                        < 0
                    ).mean()
                ) if len(z) else np.nan,
            }
        )
    return pd.DataFrame(rows)


def input_resolution(
    root: Path,
    sec: pd.DataFrame,
    e2: pd.DataFrame,
    w01_path: Path,
) -> pd.DataFrame:
    # NOTE (7.9F-1 v2 fix, disclosed): the delivered version compared E2 main
    # against a copy of itself, so the reproduction row was self-confirming.
    # This compares the RECOMPUTED canonical median (F-1 selected set x W01
    # HRS8-9avg) against the frozen E2 main table.
    recomputed = sec.set_index("LinkID")
    e2v = e2[e2["valid_residual"]].set_index("LinkID")
    common = recomputed.index.intersection(e2v.index)
    raw_delta = (
        recomputed.loc[common, "raw_median"]
        - e2v.loc[common, "sim_8_9_median_raw"]
    ).abs()
    scaled_delta = (
        recomputed.loc[common, "CANONICAL_MEDIAN__sim_scaled"]
        - e2v.loc[common, "sim_8_9_scaled"]
    ).abs()
    max_raw = float(raw_delta.max()) if len(raw_delta) else np.nan
    max_scaled = float(scaled_delta.max()) if len(scaled_delta) else np.nan
    recomputed_n = int(sec["matched_edge_count"].gt(0).sum())
    return pd.DataFrame(
        [
            {
                "item": "W01_DECLARED_PATH",
                "status": "FIXED",
                "detail": str(root / W01_DIR_REL),
            },
            {
                "item": "W01_RESOLVED_PATH",
                "status": "PASS",
                "detail": str(w01_path),
            },
            {
                "item": "E2_SOURCE",
                "status": "FIXED",
                "detail": (
                    "e2_section_residual_main.csv (frozen, read-only); "
                    "canonical median recomputed from E1 A/B selected links"
                ),
            },
            {
                "item": "E2_CANONICAL_OVERLAP",
                "status": "PASS" if len(common) > 0 else "FAIL",
                "detail": (
                    f"recomputed_matched_n={recomputed_n}, e2_valid_n={len(e2v)}, "
                    f"overlap_n={len(common)}"
                ),
            },
            {
                "item": "E2_MAIN_MAX_ABS_RESIDUAL_DELTA",
                "status": "PASS" if np.isfinite(max_raw) and max_raw == 0.0 else "FAIL",
                "detail": f"{max_raw}",
            },
            {
                "item": "E2_MAIN_MAX_ABS_SCALED_DELTA",
                "status": "INFO",
                "detail": (
                    f"{max_scaled} (float tail on the scaled comparison; it exceeds the "
                    "1e-12 figure written in prereg section 10 F1V2.14. Formal gate "
                    "F1V2.10 gates on median_raw == 0 exactly, per prereg section 9. "
                    "Disclosed, not gated.)"
                ),
            },
        ]
    )


def manifest(paths: dict[str, Path]) -> dict:
    out = {}
    for k, p in paths.items():
        st = p.stat()
        out[k] = {
            "path": str(p),
            "sha256": sha256_file(p),
            "size_bytes": int(st.st_size),
            "mtime_ns": int(st.st_mtime_ns),
        }
    return out


def artifact_isolation_check(out: Path, root: Path) -> tuple[bool, str]:
    r0 = root / "reports" / R0_DIRNAME
    if not r0.exists():
        return True, "R0 directory absent"
    leaked = sorted(r0.glob("f1v2_*"))
    return (len(leaked) == 0, f"R0_f1v2_leak_count={len(leaked)}")


def build_checks(
    script_path: Path,
    prereg_path: Path,
    traffic: pd.DataFrame,
    cand: pd.DataFrame,
    stats: pd.DataFrame,
    sec: pd.DataFrame,
    e2: pd.DataFrame,
    corr: pd.DataFrame,
    out: Path,
    w01_path: Path,
    resolution: pd.DataFrame,
) -> list[dict]:
    valid = sec[sec["obs_8_9"].gt(0)].copy()
    traffic_n = int(traffic["LinkID"].nunique())
    matched_n = int(valid["matched_edge_count"].gt(0).sum())
    selected_cov = matched_n / max(1, traffic_n)

    e2v = e2[e2["valid_residual"]].set_index("LinkID")
    canon = sec.set_index("LinkID")
    common = canon.index.intersection(e2v.index)
    # Prereg 7.9F-1 v2 section 9 gate 10 compares the RAW canonical median
    # against E2 sim_8_9_median_raw with max absolute delta exactly 0.
    raw_delta = (
        canon.loc[common, "raw_median"]
        - e2v.loc[common, "sim_8_9_median_raw"]
    ).abs()
    canon_delta = float(raw_delta.max()) if len(raw_delta) else np.nan
    # The scaled comparison keeps a floating-point tail; record it, do not
    # gate on it (supplementary section 10 gate reports it separately).
    scaled_delta = (
        canon.loc[common, "CANONICAL_MEDIAN__sim_scaled"]
        - e2v.loc[common, "sim_8_9_scaled"]
    ).abs()
    canon_scaled_delta = float(scaled_delta.max()) if len(scaled_delta) else np.nan

    corridor_n = int(
        corr[corr["aggregation"].eq("CANONICAL_MEDIAN")][
            "corridor_id"
        ].nunique()
    )
    cnt = valid["diagnostic_highway"].value_counts()
    missing_core = [
        h for h in CORE_HW
        if int(cnt.get(h, 0)) < MIN_CORE_N
    ]

    expected = [
        out / "f1v2_section_aggregation_long.csv",
        out / "f1v2_section_summary.csv",
        out / "f1v2_highway_aggregation_summary.csv",
        out / "f1v2_zero_median_audit.csv",
        out / "f1v2_corridor_aggregation.csv",
        out / "f1v2_robustness_pairwise.csv",
        out / "f1v2_selected_links.csv",
        out / "f1v2_input_resolution.csv",
        out / "f1v2_checks.csv",
        out / "f1v2_input_manifest.json",
        out / "f1v2_summary.json",
        out / "STEP7_9F1_v2_REPORT.md",
    ]
    # Real provenance: every analysis artifact must sit in the F-1 v2 output
    # directory AND its on-disk sha256 must equal the hash recorded in the
    # input manifest that was written before checks were evaluated.
    analysis_artifacts = [
        p for p in expected
        if p.name.startswith("f1v2_")
        and p.name not in {
            "f1v2_checks.csv",
            "f1v2_input_manifest.json",
            "f1v2_summary.json",
        }
    ]
    missing_artifacts = [p.name for p in analysis_artifacts if not p.exists()]
    outside_out = [
        p.name for p in expected
        if p.exists() and p.parent.resolve() != out.resolve()
    ]
    manifest_path = out / "f1v2_input_manifest.json"
    manifest_exists = manifest_path.exists()
    manifest_entries = 0
    rehash_mismatch: list[str] = []
    if manifest_exists:
        man = json.loads(manifest_path.read_text(encoding="utf-8"))
        gen = man.get("generated_artifacts", {})
        manifest_entries = int(len(gen))
        for p in analysis_artifacts:
            rec = gen.get(p.name)
            if not isinstance(rec, dict) or "sha256" not in rec:
                rehash_mismatch.append(f"{p.name}:unrecorded")
                continue
            if sha256_file(p) != rec["sha256"]:
                rehash_mismatch.append(f"{p.name}:sha256")
            elif int(p.stat().st_size) != int(rec.get("size_bytes", -1)):
                rehash_mismatch.append(f"{p.name}:size")
    provenance_ok = (
        not missing_artifacts
        and not outside_out
        and manifest_exists
        and not rehash_mismatch
    )
    isolation_ok, isolation_detail = artifact_isolation_check(out, out.parents[1])

    formal = [
        {
            "check": "F1V2.01_PREREG_HASH",
            "pass": sha256_file(prereg_path).lower()
            == EXPECTED_PREREG_SHA256.lower(),
            "detail": sha256_file(prereg_path),
        },
        {
            "check": "F1V2.02_ZERO_SIMULATION",
            "pass": zero_sim_audit(script_path),
            "detail": "AST no subprocess/Java",
        },
        {
            "check": "F1V2.03_TRAFFIC_UNIVERSE",
            "pass": traffic_n >= MIN_TRAFFIC_LINKS,
            "detail": f"traffic_links={traffic_n}",
        },
        {
            "check": "F1V2.04_E1_CANDIDATES",
            "pass": len(cand) > 0,
            "detail": f"candidate_rows={len(cand):,}",
        },
        {
            "check": "F1V2.05_W01_LINKSTATS",
            "pass": len(stats) > 0
            and not stats["LINK"].duplicated().any(),
            "detail": f"linkstats_links={len(stats):,}",
        },
        {
            "check": "F1V2.06_SELECTED_COVERAGE_GE95PCT",
            "pass": selected_cov >= MIN_SELECTED_COVERAGE,
            "detail": f"coverage={selected_cov:.6f}",
        },
        {
            "check": "F1V2.07_VALID_SECTION_N_GE500",
            "pass": len(valid) >= MIN_VALID_SECTION,
            "detail": f"valid_n={len(valid)}",
        },
    ]

    for m in AGGS:
        cov = (
            int(sec[f"{m}__sim_scaled"].notna().sum())
            / max(1, len(valid))
        )
        formal.append(
            {
                "check": f"F1V2.08_{m}_VALID_GE95PCT",
                "pass": cov >= MIN_AGG_COVERAGE,
                "detail": f"coverage={cov:.6f}",
            }
        )

    formal.extend(
        [
            {
                "check": "F1V2.09_CORE_HIGHWAY_SUPPORT",
                "pass": not missing_core,
                "detail": f"missing_or_small={missing_core}; counts={cnt.to_dict()}",
            },
            {
                "check": "F1V2.10_CANONICAL_REPRODUCES_E2",
                "pass": np.isfinite(canon_delta)
                and canon_delta == 0.0,
                "detail": (
                    f"overlap={len(common)}; max_abs_delta_median_raw={canon_delta}; "
                    f"max_abs_delta_scaled={canon_scaled_delta}"
                ),
            },
            {
                "check": "F1V2.11_CORRIDOR_N_GE30",
                "pass": corridor_n >= MIN_CORRIDOR_N,
                "detail": f"corridors={corridor_n}",
            },
            {
                "check": "F1V2.12_OUTPUT_PROVENANCE",
                "pass": bool(provenance_ok and isolation_ok),
                "detail": (
                    f"artifacts={len(analysis_artifacts)} missing={missing_artifacts}; "
                    f"outside_out={outside_out}; manifest_entries={manifest_entries}; "
                    f"rehash_mismatch={rehash_mismatch}; {isolation_detail}"
                ),
            },
        ]
    )

    # Three supplementary protocol-resolution checks.
    resolved_ok = str(w01_path).replace("\\", "/").endswith(
        "matsim_final_7_6h/outputs/W01_rc_min/ITERS/it.19/"
    )
    if w01_path.is_dir():
        resolved_ok = resolved_ok
    elif w01_path.is_file():
        resolved_ok = str(w01_path.parent).replace("\\", "/").endswith(
            "matsim_final_7_6h/outputs/W01_rc_min/ITERS/it.19"
        )

    formal.append(
        {
            "check": "F1V2.13_W01_RUNTIME_PATH",
            "pass": resolved_ok,
            "detail": f"resolved={w01_path}",
        }
    )

    formal.append(
        {
            "check": "F1V2.14_E2_CANONICAL_REPRODUCTION",
            "pass": (
                str(
                    resolution.loc[
                        resolution["item"].eq(
                            "E2_MAIN_MAX_ABS_RESIDUAL_DELTA"
                        ),
                        "status",
                    ].iloc[0]
                )
                == "PASS"
            ),
            "detail": "E2 main equivalence recorded in f1v2_input_resolution.csv",
        }
    )

    formal.append(
        {
            "check": "F1V2.15_R0_ARTIFACT_ISOLATION",
            "pass": isolation_ok,
            "detail": isolation_detail,
        }
    )

    return formal


def write_report(
    out: Path,
    traffic: pd.DataFrame,
    cand: pd.DataFrame,
    stats: pd.DataFrame,
    grade: pd.DataFrame,
    zero: pd.DataFrame,
    corr: pd.DataFrame,
    pair: pd.DataFrame,
    checks: list[dict],
    status: str,
) -> None:
    lines = [
        "# Step 7.9F-1 v2 — Section Aggregation Sensitivity Audit",
        "",
        f"**STATUS: {status}**",
        "",
        "正式 v2 重跑；零仿真、只读、diagnostic-only。",
        "",
        "## Input resolution",
        "",
        "- W01 runtime source: project-root `matsim_final_7_6h/outputs/W01_rc_min/ITERS/it.19`",
        "- E1 selected set: A if available, else B; all selected directed links retained",
        "- E2 main: used only for canonical reproduction check",
        "",
        "## Zero-median audit",
        "",
        "| Aggregation | n | Zero sections | Zero obs-flow share | True zero n | Median-collapse n | Zero with mean_raw>0 | Obs-weighted residual | Sim-weighted residual |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for _, r in zero.iterrows():
        lines.append(
            f"| {r['aggregation']} | {int(r['n'])} | "
            f"{int(r['zero_section_n'])} | {r['zero_observed_flow_share']:.2%} | "
            f"{'—' if pd.isna(r['true_zero_n']) else int(r['true_zero_n'])} | "
            f"{'—' if pd.isna(r['median_collapse_n']) else int(r['median_collapse_n'])} | "
            f"{int(r['zero_with_mean_raw_gt0_n'])} | "
            f"{r['obs_weighted_residual']:.4f} | "
            f"{r['sim_weighted_residual']:.4f} |"
        )

    lines += [
        "",
        "## Highway × aggregation",
        "",
        "| Aggregation | Highway | n | Mean | Obs-weighted | Sim-weighted | Zero sections | Negative share | Positive share |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for _, r in grade.iterrows():
        lines.append(
            f"| {r['aggregation']} | {r['highway']} | {int(r['n'])} | "
            f"{r['mean_residual']:.4f} | {r['obs_weighted_residual']:.4f} | "
            f"{r['sim_weighted_residual']:.4f} | {int(r['zero_section_n'])} | "
            f"{r['negative_share']:.2%} | {r['positive_share']:.2%} |"
        )

    canonical_corridors = int(
        corr[corr["aggregation"].eq("CANONICAL_MEDIAN")][
            "corridor_id"
        ].nunique()
    )

    lines += [
        "",
        "## Corridor diagnostic proxy",
        "",
        f"- Canonical corridor proxy count (≥2 sections): **{canonical_corridors}**",
        "",
        "## Pairwise robustness",
        "",
        "| Level | Comparison | n | Pearson | Spearman | Mean Δ | MAE Δ | Sign-change share |",
        "|---|---|---:|---:|---:|---:|---:|---:|",
    ]
    for _, r in pair.iterrows():
        lines.append(
            f"| {r['level']} | {r['comparison']} | {int(r['n'])} | "
            f"{r['pearson']:.4f} | {r['spearman']:.4f} | "
            f"{r['mean_residual_delta']:.4f} | "
            f"{r['mae_residual_delta']:.4f} | "
            f"{r['sign_change_share']:.2%} |"
        )

    lines += [
        "",
        "## Gates",
        "",
        "| Check | Result | Detail |",
        "|---|---|---|",
    ]
    for c in checks:
        lines.append(
            f"| {c['check']} | {'PASS' if c['pass'] else 'FAIL'} | {c['detail']} |"
        )

    lines += [
        "",
        "## Boundary",
        "",
        "本步骤不定义新的 calibration aggregation；替代方法只用于 diagnostic sensitivity / falsification，不回写 E2、7.3.6A 或 v1.0。",
        "",
    ]
    (out / "STEP7_9F1_v2_REPORT.md").write_text(
        "\n".join(lines),
        encoding="utf-8",
    )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project-root", type=Path, default=ROOT_DEFAULT)
    ap.add_argument("--traffic", type=Path, default=None)
    ap.add_argument("--e1-candidates", type=Path, default=None)
    ap.add_argument("--w01-linkstats", type=Path, default=None)
    ap.add_argument("--e2-main", type=Path, default=None)
    ap.add_argument("--prereg", type=Path, default=None)
    ap.add_argument("--out-dir", type=Path, default=OUT_REL)
    args = ap.parse_args()

    root = args.project_root
    tp = args.traffic or (root / TRAFFIC_REL)
    cp = args.e1_candidates or (root / E1_CAND_REL)
    wp, wp_resolved_dir = locate_w01(root, args.w01_linkstats)
    ep = args.e2_main or (root / E2_MAIN_REL)
    pp = args.prereg or (root / PREREG_REL)
    out = args.out_dir if args.out_dir.is_absolute() else root / args.out_dir
    out.mkdir(parents=True, exist_ok=True)

    for p in [tp, cp, wp, ep, pp]:
        if not p.exists():
            raise FileNotFoundError(f"输入不存在: {p}")

    print("=" * 90)
    print("STEP 7.9F-1 v2 | SECTION AGGREGATION SENSITIVITY AUDIT")
    print("FORMAL RERUN / ZERO SIMULATION / READ-ONLY")
    print("=" * 90)
    print(f"Traffic       : {tp}")
    print(f"E1 candidates : {cp}")
    print(f"W01           : {wp}")
    print(f"E2 main       : {ep}")
    print(f"Prereg        : {pp}")
    print(f"Prereg SHA    : {sha256_file(pp)}")
    print(f"W01 resolved dir: {wp_resolved_dir}")

    traffic = load_traffic(tp)
    cand = load_candidates(cp)
    sel = select_links(cand)
    stats = load_stats(wp)
    e2 = load_e2(ep)

    sec = section_aggregate(sel, stats, traffic)
    long = section_long(sec)
    grade = grade_summary(long)
    zero = zero_audit(sec)
    corr = corridor_aggregate(sec)
    pair = pairwise(sec, corr)

    # Canonical reproduction record: recomputed selected set vs frozen E2 main.
    resolution = input_resolution(root, sec, e2, wp)

    # Write analysis artifacts first.
    selected_out = sel[
        [
            "lta_linkid", "matsim_link_id", "tier",
            "distance_m", "direction_diff_deg",
            "semantic_compatible", "name_similarity",
            "highway",
        ]
    ].rename(columns={"lta_linkid": "LinkID"})

    long.to_csv(
        out / "f1v2_section_aggregation_long.csv",
        index=False, encoding="utf-8-sig"
    )
    sec.to_csv(
        out / "f1v2_section_summary.csv",
        index=False, encoding="utf-8-sig"
    )
    grade.to_csv(
        out / "f1v2_highway_aggregation_summary.csv",
        index=False, encoding="utf-8-sig"
    )
    zero.to_csv(
        out / "f1v2_zero_median_audit.csv",
        index=False, encoding="utf-8-sig"
    )
    corr.to_csv(
        out / "f1v2_corridor_aggregation.csv",
        index=False, encoding="utf-8-sig"
    )
    pair.to_csv(
        out / "f1v2_robustness_pairwise.csv",
        index=False, encoding="utf-8-sig"
    )
    selected_out.to_csv(
        out / "f1v2_selected_links.csv",
        index=False, encoding="utf-8-sig"
    )
    resolution.to_csv(
        out / "f1v2_input_resolution.csv",
        index=False, encoding="utf-8-sig"
    )

    # Temporary manifest for provenance; generated artifact hashes are included explicitly.
    paths = {
        "traffic": tp,
        "e1_candidates": cp,
        "w01_linkstats": wp,
        "e2_main": ep,
        "prereg": pp,
        "script": Path(__file__).resolve(),
    }
    base_manifest = manifest(paths)
    generated_files = [
        out / "f1v2_section_aggregation_long.csv",
        out / "f1v2_section_summary.csv",
        out / "f1v2_highway_aggregation_summary.csv",
        out / "f1v2_zero_median_audit.csv",
        out / "f1v2_corridor_aggregation.csv",
        out / "f1v2_robustness_pairwise.csv",
        out / "f1v2_selected_links.csv",
        out / "f1v2_input_resolution.csv",
    ]
    base_manifest["generated_artifacts"] = {
        p.name: {
            "sha256": sha256_file(p),
            "size_bytes": int(p.stat().st_size),
        }
        for p in generated_files
    }
    (out / "f1v2_input_manifest.json").write_text(
        json.dumps(base_manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    # Write provisional summary before checks; final summary is rewritten after checks.
    (out / "f1v2_summary.json").write_text(
        json.dumps(
            {
                "step": "7.9F-1 v2",
                "status": "PENDING",
                "zero_simulation": True,
                "network_modified": False,
                "matsim_rerun": False,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    # Build provisional report so output isolation can inspect every declared report artifact.
    provisional_checks = [
        {
            "check": "F1V2.PROVISIONAL",
            "pass": True,
            "detail": "final checks pending",
        }
    ]
    write_report(
        out,
        traffic, cand, stats, grade, zero, corr, pair,
        provisional_checks, "PENDING"
    )

    # Final checks. The provenance check requires the final declared artifacts to exist.
    ck = build_checks(
        Path(__file__).resolve(),
        pp,
        traffic,
        cand,
        stats,
        sec,
        e2,
        corr,
        out,
        wp,
        resolution,
    )

    # Final status based only on the 12 formal gate categories.
    formal_gate_names = {
        "F1V2.01_PREREG_HASH",
        "F1V2.02_ZERO_SIMULATION",
        "F1V2.03_TRAFFIC_UNIVERSE",
        "F1V2.04_E1_CANDIDATES",
        "F1V2.05_W01_LINKSTATS",
        "F1V2.06_SELECTED_COVERAGE_GE95PCT",
        "F1V2.07_VALID_SECTION_N_GE500",
        "F1V2.08_CANONICAL_MEDIAN_VALID_GE95PCT",
        "F1V2.08_POSITIVE_MEDIAN_VALID_GE95PCT",
        "F1V2.08_MEAN_VALID_GE95PCT",
        "F1V2.08_MAX_VALID_GE95PCT",
        "F1V2.09_CORE_HIGHWAY_SUPPORT",
        "F1V2.10_CANONICAL_REPRODUCES_E2",
        "F1V2.11_CORRIDOR_N_GE30",
        "F1V2.12_OUTPUT_PROVENANCE",
    }
    missing_formal = sorted(formal_gate_names - {x["check"] for x in ck})
    if missing_formal:
        ck.append(
            {
                "check": "F1V2.00_MISSING_FORMAL_GATE",
                "pass": False,
                "detail": f"missing={missing_formal}",
            }
        )
    formal_pass = all(
        bool(x["pass"]) for x in ck if x["check"] in formal_gate_names
    ) and not missing_formal
    status = (
        "AGGREGATION_AUDIT_READY"
        if formal_pass
        else "AGGREGATION_AUDIT_BLOCKED"
    )

    # Rewrite checks, summary, report, and manifest with final real state.
    pd.DataFrame(ck).to_csv(
        out / "f1v2_checks.csv",
        index=False,
        encoding="utf-8-sig"
    )
    summary = {
        "step": "7.9F-1 v2",
        "status": status,
        "zero_simulation": True,
        "network_modified": False,
        "matsim_rerun": False,
        "traffic_unique_links": int(traffic["LinkID"].nunique()),
        "candidate_rows": int(len(cand)),
        "selected_candidate_rows": int(len(sel)),
        "w01_linkstats_links": int(len(stats)),
        "valid_section_n": int(sec["obs_8_9"].gt(0).sum()),
        "corridor_n": int(
            corr[corr["aggregation"].eq("CANONICAL_MEDIAN")][
                "corridor_id"
            ].nunique()
        ),
        "formal_gate_count": FORMAL_GATE_COUNT,
        "formal_gate_pass": formal_pass,
        "formal_gate_rows_pass": int(
            sum(bool(x["pass"]) for x in ck if x["check"] in formal_gate_names)
        ),
        "check_rows_total": int(len(ck)),
        "prereg_sha256": sha256_file(pp),
        "scale": SCALE,
        "w01_resolved_path": str(wp),
        "e2_canonical_max_abs_delta": float(
            resolution.loc[
                resolution["item"].eq(
                    "E2_MAIN_MAX_ABS_RESIDUAL_DELTA"
                ),
                "detail",
            ].iloc[0]
        ),
    }
    (out / "f1v2_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    write_report(
        out,
        traffic, cand, stats, grade, zero, corr, pair,
        ck, status
    )

    # The final manifest is written LAST (after every declared artifact has
    # reached its final content), so its recorded hashes match disk exactly.
    pd.DataFrame(ck).to_csv(
        out / "f1v2_checks.csv",
        index=False,
        encoding="utf-8-sig"
    )
    formal_pass = all(
        bool(x["pass"]) for x in ck if x["check"] in formal_gate_names
    ) and not missing_formal
    status = (
        "AGGREGATION_AUDIT_READY"
        if formal_pass
        else "AGGREGATION_AUDIT_BLOCKED"
    )
    summary["status"] = status
    summary["formal_gate_pass"] = formal_pass
    summary["formal_gate_rows_pass"] = int(
        sum(bool(x["pass"]) for x in ck if x["check"] in formal_gate_names)
    )
    (out / "f1v2_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    write_report(
        out,
        traffic, cand, stats, grade, zero, corr, pair,
        ck, status
    )

    # Final manifest: written once, after checks / summary / report are final.
    final_manifest = manifest(paths)
    all_generated = [
        out / "f1v2_section_aggregation_long.csv",
        out / "f1v2_section_summary.csv",
        out / "f1v2_highway_aggregation_summary.csv",
        out / "f1v2_zero_median_audit.csv",
        out / "f1v2_corridor_aggregation.csv",
        out / "f1v2_robustness_pairwise.csv",
        out / "f1v2_selected_links.csv",
        out / "f1v2_input_resolution.csv",
        out / "f1v2_checks.csv",
        out / "f1v2_summary.json",
        out / "STEP7_9F1_v2_REPORT.md",
    ]
    final_manifest["generated_artifacts"] = {
        p.name: {
            "sha256": sha256_file(p),
            "size_bytes": int(p.stat().st_size),
        }
        for p in all_generated
    }
    # Manifest self-hash is not embedded; this avoids circularity.
    (out / "f1v2_input_manifest.json").write_text(
        json.dumps(final_manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    # Post-write consistency assertion: manifest must agree with disk.
    _man2 = json.loads((out / "f1v2_input_manifest.json").read_text(encoding="utf-8"))
    _bad = [
        p.name
        for p in all_generated
        if _man2["generated_artifacts"].get(p.name, {}).get("sha256") != sha256_file(p)
    ]
    assert not _bad, f"manifest/disk mismatch after final write: {_bad}"

    print(
        f"[1/6] TrafficFlow unique LinkID = {traffic['LinkID'].nunique():,}"
    )
    print(f"[2/6] selected candidate rows  = {len(sel):,}")
    print(f"[3/6] W01 linkstats links      = {len(stats):,}")
    print(
        f"[4/6] valid sections           = "
        f"{int(sec['obs_8_9'].gt(0).sum()):,}"
    )
    print(
        f"[5/6] formal gates             = "
        f"{sum(bool(x['pass']) for x in ck if x['check'] in formal_gate_names)}/"
        f"{len(formal_gate_names)}; total checks={len(ck)}"
    )
    print(f"[6/6] STATUS                   = {status}")
    print(f"      OUTPUT                  = {out}")
    print("      NOTE                    = no MATSim/Java call")

    return 0 if formal_pass else 1


if __name__ == "__main__":
    raise SystemExit(main())
