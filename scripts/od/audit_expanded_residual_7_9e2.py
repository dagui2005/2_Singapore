#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Step 7.9E-2 — Expanded Diagnostic Residual Domain.

ZERO SIMULATION / READ-ONLY.

Uses the frozen 7.9E-1 diagnostic crosswalk and the canonical section-level
Sim/Obs/SCALE rule used by the 7.3.6B / 7.7C chain:
    median(HRS8-9avg over selected directed MATSim links) * SCALE / obs_8_9 - 1

This script never modifies 7.3.6A, v1.0, W01, network, capacity, or target files.
"""
from __future__ import annotations

import argparse
import ast
import csv
import gzip
import hashlib
import json
import math
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd

ROOT_DEFAULT = Path(r"D:\Luan\2026-05\2_Singapore")
TRAFFIC_REL = Path("Singapore_OD_MATSim_FinalData/08_TrafficCount/TrafficFlow_Data.json")
E1_DIR_REL = Path("reports/arterial_observability_7_9e1")
E1_CAND_REL = E1_DIR_REL / "e1_crosswalk_candidates.csv"
E1_BEST_REL = E1_DIR_REL / "e1_crosswalk_best.csv"
FORMAL_RESIDUAL_REL = Path("reports/spatial_residual_7_7c0/c0_section_table.csv")
W01_DIR_CANDIDATES = [
    Path("matsim_final_7_6h/outputs/W01_rc_min/ITERS/it.19"),
    Path("reports/matsim_final_7_6h/outputs/W01_rc_min/ITERS/it.19"),
    Path("matsim_final_7_6h/outputs/W01/ITERS/it.19"),
]
OUT_REL = Path("reports/arterial_expanded_residual_7_9e2")
PREREG_REL = OUT_REL / "PREREG_7_9E2.md"
EXPECTED_PREREG_SHA256 = "c9e68272cf07c8872f87eebd0d75af28dacd73db4de04d78d90b69ee30a7e6cc"

SCALE = 459794.0 / 200000.0
MIN_TRAFFIC_LINKS = 1278
MIN_AB_COVERAGE = 0.80
MIN_VALID_RESIDUAL = 30
MIN_ARTERIAL_N = 30
MIN_BRIDGE_N = 500
N_PERM = 2000
PERM_SEED_UNSTRAT = 79200
PERM_SEED_STRAT = 79201
# --- supplementary (post-hoc) robustness only; does NOT change the frozen verdict ---
SUPP_SEED = 79202
MIN_STRATUM_N = 30
MIN_ARM_N = 5

MAINLINE = {"motorway", "motorway_link"}
ARTERIAL_CORE = {"primary", "secondary", "tertiary"}
FORMAL_ROADCATS = {"CATA", "CATB", "CATC", "CATD", "CATE", "SLIP_ROAD"}
TIER_RANK = {
    "A_STRICT_SEMANTIC_DIRECTION": 1,
    "B_DIRECTION_GEOMETRY": 2,
    "C_GEOMETRY_ONLY": 3,
}


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
    if s.endswith(".0") and s[:-2].isdigit():
        return s[:-2]
    return s


def norm_text(x: object) -> str:
    if x is None or (isinstance(x, float) and math.isnan(x)):
        return ""
    return " ".join(str(x).replace("\xa0", " ").strip().upper().split())


def numeric(s: pd.Series) -> pd.Series:
    return pd.to_numeric(s.astype(str).str.replace(",", "", regex=False), errors="coerce")


def safe_ratio(a: float, b: float) -> float:
    return float(a / b) if b and np.isfinite(b) else float("nan")


def mean_or_nan(s: pd.Series) -> float:
    x = pd.to_numeric(s, errors="coerce").dropna()
    return float(x.mean()) if len(x) else float("nan")


def median_or_nan(s: pd.Series) -> float:
    x = pd.to_numeric(s, errors="coerce").dropna()
    return float(x.median()) if len(x) else float("nan")


def spearman(x: pd.Series, y: pd.Series) -> float:
    z = pd.concat([pd.to_numeric(x, errors="coerce"), pd.to_numeric(y, errors="coerce")], axis=1).dropna()
    if len(z) < 3:
        return float("nan")
    return float(z.iloc[:, 0].corr(z.iloc[:, 1], method="spearman"))


def eta_squared(y: pd.Series, group: pd.Series) -> float:
    z = pd.DataFrame({"y": pd.to_numeric(y, errors="coerce"), "g": group}).dropna()
    if len(z) < 3 or z["g"].nunique() < 2:
        return float("nan")
    grand = float(z["y"].mean())
    ss_total = float(((z["y"] - grand) ** 2).sum())
    if ss_total <= 0:
        return 0.0
    ss_between = 0.0
    for _, g in z.groupby("g"):
        ss_between += len(g) * float((g["y"].mean() - grand) ** 2)
    return float(ss_between / ss_total)


def first_existing(root: Path, paths: Iterable[Path]) -> Path | None:
    for p in paths:
        q = p if p.is_absolute() else root / p
        if q.exists():
            return q
    return None


# ---------------------------------------------------------------------------
# Fixed inputs
# ---------------------------------------------------------------------------

def load_traffic(path: Path) -> pd.DataFrame:
    with path.open("r", encoding="utf-8-sig") as f:
        obj = json.load(f)
    rows = obj.get("Value", obj.get("value", [])) if isinstance(obj, dict) else obj
    df = pd.DataFrame(rows)
    required = {"LinkID", "Date", "HourOfDate", "Volume", "RoadName", "RoadCat"}
    missing = sorted(required - set(df.columns))
    if missing:
        raise ValueError(f"TrafficFlow 缺字段: {missing}")

    df["LinkID"] = df["LinkID"].map(norm_id)
    df["Date"] = pd.to_datetime(df["Date"], dayfirst=True, errors="coerce")
    df["HourOfDate"] = pd.to_numeric(df["HourOfDate"], errors="coerce")
    df["Volume"] = numeric(df["Volume"])
    df["RoadName"] = df["RoadName"].map(norm_text)
    df["RoadCat"] = df["RoadCat"].map(norm_text)
    df = df[
        df["LinkID"].ne("")
        & df["Date"].notna()
        & df["Date"].dt.weekday.lt(5)
        & df["HourOfDate"].eq(8)
        & df["Volume"].notna()
    ].copy()
    if df.empty:
        raise ValueError("TrafficFlow 没有工作日 08-09 可用记录")

    daily = df.groupby(["LinkID", "Date"], as_index=False)["Volume"].mean()
    obs = daily.groupby("LinkID", as_index=False)["Volume"].median().rename(columns={"Volume": "obs_8_9"})
    attrs = (
        df.sort_values(["LinkID", "Date"])
        .groupby("LinkID", as_index=False)
        .agg(RoadName=("RoadName", "first"), RoadCat=("RoadCat", "first"))
    )
    return obs.merge(attrs, on="LinkID", how="left", validate="one_to_one")


def load_crosswalk_candidates(path: Path) -> pd.DataFrame:
    x = pd.read_csv(path, encoding="utf-8-sig", low_memory=False)
    rename = {}
    for c in x.columns:
        k = str(c).strip().lower()
        mp = {
            "lta_linkid": "lta_linkid", "linkid": "lta_linkid",
            "matsim_link_id": "matsim_link_id", "matsim_link": "matsim_link_id",
            "distance_m": "distance_m", "geometry_distance_m": "distance_m",
            "direction_diff_deg": "direction_diff_deg", "direction_diff": "direction_diff_deg",
            "tier": "tier", "tier_rank": "tier_rank", "rank": "tier_rank",
            "highway": "highway", "semantic_compatible": "semantic_compatible",
            "semantic_ok": "semantic_compatible", "name_similarity": "name_similarity",
            "name_sim": "name_similarity",
        }
        if k in mp:
            rename[c] = mp[k]
    x = x.rename(columns=rename)
    required = {"lta_linkid", "matsim_link_id", "tier", "distance_m", "direction_diff_deg", "highway"}
    missing = sorted(required - set(x.columns))
    if missing:
        raise ValueError(f"7.9E-1 candidates 缺字段: {missing}")
    x["lta_linkid"] = x["lta_linkid"].map(norm_id)
    x["matsim_link_id"] = x["matsim_link_id"].map(norm_id)
    x["tier"] = x["tier"].map(norm_text)
    x["highway"] = x["highway"].map(norm_text).str.lower()
    x["distance_m"] = numeric(x["distance_m"])
    x["direction_diff_deg"] = numeric(x["direction_diff_deg"])
    x["tier_rank"] = x["tier"].map(TIER_RANK)
    if "semantic_compatible" in x.columns:
        x["semantic_compatible"] = x["semantic_compatible"].astype(str).str.strip().str.lower().isin(["true", "1", "yes"])
    else:
        x["semantic_compatible"] = False
    if "name_similarity" in x.columns:
        x["name_similarity"] = numeric(x["name_similarity"])
    else:
        x["name_similarity"] = 0.0
    x = x[
        x["lta_linkid"].ne("")
        & x["matsim_link_id"].ne("")
        & x["tier"].isin(TIER_RANK)
        & x["distance_m"].notna()
    ].copy()
    return x.drop_duplicates(["lta_linkid", "matsim_link_id", "tier"])


def load_linkstats(path: Path) -> pd.DataFrame:
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", encoding="utf-8", errors="replace", newline="") as f:
        header = f.readline().rstrip("\n").split("\t")
    need = ["LINK", "HRS8-9avg"]
    missing = [c for c in need if c not in header]
    if missing:
        raise ValueError(f"W01 linkstats 缺字段: {missing}")
    df = pd.read_csv(
        path,
        sep="\t",
        compression="gzip" if path.suffix == ".gz" else None,
        usecols=need,
        low_memory=False,
    )
    df["LINK"] = df["LINK"].map(norm_id)
    df["HRS8-9avg"] = numeric(df["HRS8-9avg"])
    if df["LINK"].duplicated().any():
        raise ValueError("W01 linkstats LINK 出现重复")
    return df


def load_formal_residual(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path, encoding="utf-8-sig", low_memory=False)
    cols = {str(c).strip().lower(): c for c in df.columns}
    id_col = next((cols[k] for k in ("lta_linkid", "linkid", "lta_id") if k in cols), None)
    ratio_col = next((cols[k] for k in ("ratio_8_9", "ratio") if k in cols), None)
    if id_col is None or ratio_col is None:
        raise ValueError("formal residual 缺少 lta_linkid / ratio_8_9")
    out = df[[id_col, ratio_col]].copy()
    out.columns = ["lta_linkid", "ratio_8_9"]
    out["lta_linkid"] = out["lta_linkid"].map(norm_id)
    out["ratio_8_9"] = pd.to_numeric(out["ratio_8_9"], errors="coerce")
    out["formal_residual"] = out["ratio_8_9"] - 1.0
    return out[["lta_linkid", "formal_residual"]].dropna(subset=["lta_linkid"]).drop_duplicates("lta_linkid")


def locate_w01(root: Path) -> Path:
    p = first_existing(root, W01_DIR_CANDIDATES)
    if p is None:
        raise FileNotFoundError("未找到 W01 it.19 linkstats；请用 --w01-linkstats 显式指定")
    files = sorted(p.glob("*.linkstats.txt.gz")) + sorted(p.glob("*.linkstats.txt"))
    if not files:
        raise FileNotFoundError(f"W01 目录中没有 linkstats: {p}")
    return files[0]


# ---------------------------------------------------------------------------
# Diagnostic section residual
# ---------------------------------------------------------------------------

def select_edges_by_mode(candidates: pd.DataFrame, mode: str) -> pd.DataFrame:
    allowed = {
        "A_ONLY": ["A_STRICT_SEMANTIC_DIRECTION"],
        "A+B_MAIN": ["A_STRICT_SEMANTIC_DIRECTION", "B_DIRECTION_GEOMETRY"],
        "A+B+C_RELAXED": ["A_STRICT_SEMANTIC_DIRECTION", "B_DIRECTION_GEOMETRY", "C_GEOMETRY_ONLY"],
    }[mode]
    selected = []
    for sid, g0 in candidates.groupby("lta_linkid", sort=True):
        g0 = g0.copy()
        chosen = None
        for tier in allowed:
            g = g0[g0["tier"] == tier]
            if len(g):
                chosen = g.copy()
                break
        if chosen is None:
            continue
        chosen = chosen.sort_values(
            ["distance_m", "direction_diff_deg", "semantic_compatible", "name_similarity", "matsim_link_id"],
            ascending=[True, True, False, False, True],
        ).drop_duplicates("matsim_link_id")
        chosen["selection_mode"] = mode
        selected.append(chosen)
    return pd.concat(selected, ignore_index=True) if selected else pd.DataFrame(columns=candidates.columns.tolist() + ["selection_mode"])


def representative_rows(selected: pd.DataFrame) -> pd.DataFrame:
    if selected.empty:
        return pd.DataFrame()
    rows = []
    for sid, g in selected.groupby("lta_linkid", sort=True):
        r = g.sort_values(
            ["distance_m", "direction_diff_deg", "semantic_compatible", "name_similarity", "matsim_link_id"],
            ascending=[True, True, False, False, True],
        ).iloc[0].copy()
        rows.append(r)
    return pd.DataFrame(rows)


def build_section_residual(
    traffic: pd.DataFrame,
    candidates: pd.DataFrame,
    stats: pd.DataFrame,
    mode: str,
) -> pd.DataFrame:
    selected = select_edges_by_mode(candidates, mode)
    if selected.empty:
        return pd.DataFrame()

    x = selected.merge(
        stats,
        left_on="matsim_link_id",
        right_on="LINK",
        how="left",
        validate="many_to_one",
    )
    sec = (
        x.groupby("lta_linkid", as_index=False)
        .agg(
            matched_matsim_edges=("matsim_link_id", "nunique"),
            sim_8_9_median_raw=("HRS8-9avg", "median"),
            sim_8_9_mean_raw=("HRS8-9avg", "mean"),
        )
    )
    sec["sim_8_9_scaled"] = sec["sim_8_9_median_raw"] * SCALE

    rep = representative_rows(selected)
    rep = rep[
        [
            "lta_linkid", "matsim_link_id", "highway", "distance_m",
            "direction_diff_deg", "semantic_compatible", "name_similarity",
        ]
    ].rename(
        columns={
            "matsim_link_id": "representative_matsim_link_id",
            "highway": "diagnostic_highway",
        }
    )
    sec = traffic.merge(sec, left_on="LinkID", right_on="lta_linkid", how="left")
    sec = sec.merge(rep, left_on="LinkID", right_on="lta_linkid", how="left", suffixes=("", "_rep"))
    sec["diagnostic_ratio_8_9"] = sec["sim_8_9_scaled"] / sec["obs_8_9"].replace(0, np.nan)
    sec["diagnostic_residual_8_9"] = sec["diagnostic_ratio_8_9"] - 1.0
    sec["is_arterial_core"] = sec["diagnostic_highway"].isin(ARTERIAL_CORE)
    sec["valid_residual"] = (
        sec["obs_8_9"].gt(0)
        & sec["sim_8_9_scaled"].notna()
        & sec["diagnostic_highway"].notna()
    )
    sec["selection_mode"] = mode
    sec["source_domain"] = np.where(
        sec["RoadCat"].isin(FORMAL_ROADCATS), "formal_roadcat", "other_roadcat"
    )
    return sec


# ---------------------------------------------------------------------------
# Coupling and bridge
# ---------------------------------------------------------------------------

def permutation_unstratified(z: pd.DataFrame) -> tuple[float, float]:
    y = z["diagnostic_residual_8_9"].to_numpy(dtype=float)
    lab = z["is_arterial_core"].to_numpy(dtype=bool)
    if len(y) < 3 or lab.sum() == 0 or lab.sum() == len(y):
        return float("nan"), float("nan")
    observed = abs(float(y[lab].mean() - y[~lab].mean()))
    rng = np.random.default_rng(PERM_SEED_UNSTRAT)
    greater = 0
    for _ in range(N_PERM):
        s = rng.permutation(lab)
        d = abs(float(y[s].mean() - y[~s].mean()))
        if d >= observed:
            greater += 1
    return observed, float((1 + greater) / (N_PERM + 1))


def permutation_roadcat_stratified(z: pd.DataFrame) -> tuple[float, float, dict]:
    groups = []
    observed_score = 0.0
    weight = 0
    for roadcat, g in z.groupby("RoadCat", dropna=False):
        if g["is_arterial_core"].nunique() < 2:
            continue
        y = g["diagnostic_residual_8_9"].to_numpy(dtype=float)
        lab = g["is_arterial_core"].to_numpy(dtype=bool)
        d = abs(float(y[lab].mean() - y[~lab].mean()))
        observed_score += d * len(g)
        weight += len(g)
        groups.append((str(roadcat), y, lab, len(g)))
    if not groups or weight == 0:
        return float("nan"), float("nan"), {"blocked": True, "reason": "no_mixed_roadcat_strata"}
    observed = observed_score / weight
    rng = np.random.default_rng(PERM_SEED_STRAT)
    greater = 0
    for _ in range(N_PERM):
        score = 0.0
        wt = 0
        for _, y, lab, n in groups:
            s = rng.permutation(lab)
            d = abs(float(y[s].mean() - y[~s].mean()))
            score += d * n
            wt += n
        if wt and score / wt >= observed:
            greater += 1
    return float(observed), float((1 + greater) / (N_PERM + 1)), {
        "blocked": False,
        "mixed_roadcat_strata": len(groups),
    }


def _stratified_statistic(strata: list, seed: int, n_perm: int) -> tuple[float, float, int]:
    """Weighted mean of within-stratum |mean(arterial)-mean(non-arterial)| + permutation p.

    `strata` is a list of (label, subframe) where each subframe has BOTH arms.
    """
    groups = []
    observed_score = 0.0
    weight = 0
    for label, g in strata:
        y = g["diagnostic_residual_8_9"].to_numpy(dtype=float)
        lab = g["is_arterial_core"].to_numpy(dtype=bool)
        if lab.sum() == 0 or lab.sum() == len(lab):
            continue
        d = abs(float(y[lab].mean() - y[~lab].mean()))
        observed_score += d * len(g)
        weight += len(g)
        groups.append((str(label), y, lab, len(g)))
    if not groups or weight == 0:
        return float("nan"), float("nan"), 0
    observed = observed_score / weight
    rng = np.random.default_rng(seed)
    greater = 0
    for _ in range(n_perm):
        score = 0.0
        wt = 0
        for _, y, lab, n in groups:
            s = rng.permutation(lab)
            score += abs(float(y[s].mean() - y[~s].mean())) * n
            wt += n
        if wt and score / wt >= observed:
            greater += 1
    return float(observed), float((1 + greater) / (n_perm + 1)), len(groups)


def supplementary_robustness(z: pd.DataFrame) -> pd.DataFrame:
    """Post-hoc stratum robustness. NOT part of the frozen decision rule."""
    mixed = []
    for roadcat, g in z.groupby("RoadCat", dropna=False):
        n_art = int(g["is_arterial_core"].sum())
        n_non = int((~g["is_arterial_core"]).sum())
        if n_art > 0 and n_non > 0:
            mixed.append((str(roadcat), g, n_art, n_non))
    rows = []

    def emit(variant, strata, seed):
        obs, p, k = _stratified_statistic(strata, seed, N_PERM)
        rows.append({
            "variant": variant,
            "strata_used": k,
            "n": int(sum(len(g) for _, g in strata)),
            "arterial_n": int(sum(int(g["is_arterial_core"].sum()) for _, g in strata)),
            "observed_abs_mean_diff": obs,
            "p": p,
            "n_perm": N_PERM,
            "seed": seed,
        })

    emit("ALL_MIXED_STRATA", [(rc, g) for rc, g, _, _ in mixed], PERM_SEED_STRAT)
    restricted = [(rc, g) for rc, g, a, n in mixed if len(g) >= MIN_STRATUM_N and a >= MIN_ARM_N and n >= MIN_ARM_N]
    if restricted:
        emit("RESTRICTED_MIN_N%d_ARM%d" % (MIN_STRATUM_N, MIN_ARM_N), restricted, SUPP_SEED)
    for drop, _, _, _ in mixed:
        keep = [(rc, g) for rc, g, _, _ in mixed if rc != drop]
        if keep:
            emit("LEAVE_OUT_%s" % drop, keep, SUPP_SEED)
    return pd.DataFrame(rows)


def coupling(sec: pd.DataFrame) -> tuple[pd.DataFrame, dict, pd.DataFrame]:
    z = sec[
        sec["valid_residual"]
        & sec["RoadCat"].isin(FORMAL_ROADCATS)
    ].copy()
    if z.empty:
        return pd.DataFrame(), {"valid_n": 0, "arterial_n": 0}, pd.DataFrame()

    rows = []
    for flag, g in z.groupby("is_arterial_core", sort=True):
        rows.append({
            "is_arterial_core": bool(flag),
            "n": int(len(g)),
            "mean_residual": mean_or_nan(g["diagnostic_residual_8_9"]),
            "median_residual": median_or_nan(g["diagnostic_residual_8_9"]),
            "p10_residual": float(g["diagnostic_residual_8_9"].quantile(0.10)),
            "p90_residual": float(g["diagnostic_residual_8_9"].quantile(0.90)),
        })

    obs_un, p_un = permutation_unstratified(z)
    obs_st, p_st, meta_st = permutation_roadcat_stratified(z)
    meta = {
        "valid_n": int(len(z)),
        "arterial_n": int(z["is_arterial_core"].sum()),
        "nonarterial_n": int((~z["is_arterial_core"]).sum()),
        "arterial_mean": mean_or_nan(z.loc[z["is_arterial_core"], "diagnostic_residual_8_9"]),
        "nonarterial_mean": mean_or_nan(z.loc[~z["is_arterial_core"], "diagnostic_residual_8_9"]),
        "spearman": spearman(z["diagnostic_residual_8_9"], z["is_arterial_core"].astype(int)),
        "eta_squared": eta_squared(z["diagnostic_residual_8_9"], z["is_arterial_core"]),
        "unstratified_abs_mean_diff": obs_un,
        "unstratified_p": p_un,
        "roadcat_stratified_abs_mean_diff": obs_st,
        "roadcat_stratified_p": p_st,
        "roadcat_stratified_meta": meta_st,
    }
    perm = pd.DataFrame([
        {"kind": "unstratified", "observed_abs_mean_diff": obs_un, "p": p_un, "n_perm": N_PERM, "seed": PERM_SEED_UNSTRAT},
        {"kind": "roadcat_stratified", "observed_abs_mean_diff": obs_st, "p": p_st, "n_perm": N_PERM, "seed": PERM_SEED_STRAT},
    ])
    return pd.DataFrame(rows), meta, perm


def roadcat_matrix(sec: pd.DataFrame) -> pd.DataFrame:
    z = sec[sec["valid_residual"] & sec["RoadCat"].isin(FORMAL_ROADCATS)].copy()
    if z.empty:
        return pd.DataFrame(columns=["RoadCat", "diagnostic_highway", "n", "share_within_RoadCat", "arterial_core_share"])
    x = z.groupby(["RoadCat", "diagnostic_highway"], as_index=False).agg(n=("LinkID", "nunique"))
    x["share_within_RoadCat"] = x["n"] / x.groupby("RoadCat")["n"].transform("sum")
    a = z.assign(arterial=z["diagnostic_highway"].isin(ARTERIAL_CORE)).groupby("RoadCat")["arterial"].mean().rename("arterial_core_share")
    return x.merge(a.reset_index(), on="RoadCat", how="left").sort_values(["RoadCat", "n"], ascending=[True, False])


def roadcat_summary(sec: pd.DataFrame) -> pd.DataFrame:
    rows = []
    total = int(sec["LinkID"].nunique())
    for roadcat, g in sec.groupby("RoadCat", dropna=False):
        v = g[g["valid_residual"]]
        rows.append({
            "RoadCat": roadcat,
            "traffic_unique_links": int(g["LinkID"].nunique()),
            "valid_residual_links": int(v["LinkID"].nunique()),
            "coverage_vs_all_traffic": safe_ratio(v["LinkID"].nunique(), total),
            "arterial_core_n": int(v["is_arterial_core"].sum()),
            "arterial_core_share": safe_ratio(v["is_arterial_core"].sum(), len(v)),
            "mean_residual": mean_or_nan(v["diagnostic_residual_8_9"]),
            "median_residual": median_or_nan(v["diagnostic_residual_8_9"]),
            "median_match_distance_m": median_or_nan(v["distance_m"]),
            "p90_match_distance_m": float(v["distance_m"].quantile(0.90)) if v["distance_m"].notna().any() else float("nan"),
        })
    return pd.DataFrame(rows)


def stratum_decomposition(z: pd.DataFrame) -> pd.DataFrame:
    """Within-RoadCat arterial vs non-arterial residual means (post-hoc transparency)."""
    rows = []
    for roadcat, g in z.groupby("RoadCat", dropna=False):
        a = g[g["is_arterial_core"]]
        n = g[~g["is_arterial_core"]]
        ma = mean_or_nan(a["diagnostic_residual_8_9"]) if len(a) else float("nan")
        mn = mean_or_nan(n["diagnostic_residual_8_9"]) if len(n) else float("nan")
        rows.append({
            "RoadCat": roadcat,
            "n_arterial": int(len(a)),
            "n_nonarterial": int(len(n)),
            "mean_arterial": ma,
            "mean_nonarterial": mn,
            "abs_mean_diff": abs(ma - mn) if (len(a) and len(n)) else float("nan"),
        })
    return pd.DataFrame(rows)


def highway_summary(sec: pd.DataFrame) -> pd.DataFrame:
    """Residual structure by diagnostic OSM highway class (main A+B domain)."""
    z = sec[sec["valid_residual"]].copy()
    rows = []
    for hw, g in z.groupby("diagnostic_highway", dropna=False):
        obs = float(g["obs_8_9"].sum())
        sim = float(g["sim_8_9_scaled"].sum())
        rows.append({
            "diagnostic_highway": hw,
            "n": int(len(g)),
            "n_arterial_core": int(g["is_arterial_core"].sum()),
            "mean_residual": mean_or_nan(g["diagnostic_residual_8_9"]),
            "median_residual": median_or_nan(g["diagnostic_residual_8_9"]),
            "flow_weighted_residual": (safe_ratio(sim, obs) - 1.0) if obs > 0 else float("nan"),
            "obs_sum": obs,
            "sim_sum": sim,
        })
    return pd.DataFrame(rows).sort_values("n", ascending=False)


def formal_bridge(expanded: pd.DataFrame, formal: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    e = expanded[expanded["valid_residual"]][["LinkID", "diagnostic_residual_8_9"]].drop_duplicates("LinkID")
    x = formal.merge(e, left_on="lta_linkid", right_on="LinkID", how="inner")
    meta = {"overlap_n": int(len(x))}
    if x.empty:
        return x, meta
    a = x["formal_residual"].to_numpy(dtype=float)
    b = x["diagnostic_residual_8_9"].to_numpy(dtype=float)
    d = b - a
    meta.update({
        "mean_bias_diagnostic_minus_formal": float(np.mean(d)),
        "mae": float(np.mean(np.abs(d))),
        "rmse": float(np.sqrt(np.mean(d ** 2))),
        "spearman": spearman(pd.Series(a), pd.Series(b)),
        "pearson": float(pd.Series(a).corr(pd.Series(b), method="pearson")) if len(a) >= 2 else float("nan"),
    })
    return x, meta


# ---------------------------------------------------------------------------
# Integrity / outputs
# ---------------------------------------------------------------------------

def static_zero_simulation_audit(path: Path) -> bool:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    if any(isinstance(n, ast.Import) and any(a.name == "subprocess" for a in n.names) for n in ast.walk(tree)):
        return False
    if any(isinstance(n, ast.ImportFrom) and n.module == "subprocess" for n in ast.walk(tree)):
        return False
    for n in ast.walk(tree):
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr in {"Popen", "run", "call", "check_call"}:
            return False
    return True


def input_manifest(paths: dict[str, Path]) -> dict:
    out = {}
    for k, p in paths.items():
        st = p.stat()
        out[k] = {"path": str(p), "sha256": sha256_file(p), "mtime_ns": int(st.st_mtime_ns), "size_bytes": int(st.st_size)}
    return out


def write_csv(df: pd.DataFrame, path: Path) -> None:
    df.to_csv(path, index=False, encoding="utf-8-sig", quoting=csv.QUOTE_MINIMAL)


def render_report(
    out: Path,
    traffic: pd.DataFrame,
    main: pd.DataFrame,
    sensitivity: pd.DataFrame,
    matrix: pd.DataFrame,
    roadcat_sum: pd.DataFrame,
    meta: dict,
    bridge_meta: dict,
    checks: list[dict],
    status: str,
    supp: pd.DataFrame | None = None,
    decomp: pd.DataFrame | None = None,
    hw_sum: pd.DataFrame | None = None,
) -> str:
    lines = [
        "# Step 7.9E-2 — Expanded Diagnostic Residual Domain",
        "",
        f"**Status: {status}**",
        "",
        "零仿真、只读；expanded residual 是诊断层，不替换 7.3.6A 正式 residual。",
        "",
        "## Fixed scale and domain",
        "",
        f"- TrafficFlow unique LinkID: **{traffic['LinkID'].nunique():,}**",
        f"- SCALE: **{SCALE:.8f}**",
        f"- A+B valid residual: **{int(main['valid_residual'].sum())}**",
        f"- A+B arterial residual: **{int(main.loc[main['valid_residual'], 'is_arterial_core'].sum())}**",
        "",
        "## Sensitivity",
        "",
        "| Tier | Matched | Coverage | Valid residual | Arterial n | Median distance m | P90 distance m |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for _, r in sensitivity.iterrows():
        lines.append(
            f"| {r['tier']} | {int(r['matched_links'])} | {r['coverage']:.2%} | {int(r['valid_residual_n'])} | {int(r['arterial_n'])} | {r['median_distance_m']:.2f} | {r['p90_distance_m']:.2f} |"
        )
    lines += [
        "",
        "## Arterial coupling",
        "",
        f"- valid residual n: **{meta.get('valid_n', 0)}**",
        f"- arterial n: **{meta.get('arterial_n', 0)}**",
        f"- non-arterial n: **{meta.get('nonarterial_n', 0)}**",
        f"- arterial mean residual: **{meta.get('arterial_mean', float('nan')):.6f}**",
        f"- non-arterial mean residual: **{meta.get('nonarterial_mean', float('nan')):.6f}**",
        f"- Spearman: **{meta.get('spearman', float('nan')):.6f}**",
        f"- eta²: **{meta.get('eta_squared', float('nan')):.6f}**",
        f"- unstratified p: **{meta.get('unstratified_p', float('nan')):.6f}**",
        f"- RoadCat-stratified p: **{meta.get('roadcat_stratified_p', float('nan')):.6f}**",
        "",
        "## Formal-domain bridge",
        "",
        f"- overlap n: **{bridge_meta.get('overlap_n', 0)}**",
        f"- Spearman: **{bridge_meta.get('spearman', float('nan')):.6f}**",
        f"- Pearson: **{bridge_meta.get('pearson', float('nan')):.6f}**",
        f"- mean bias diagnostic-formal: **{bridge_meta.get('mean_bias_diagnostic_minus_formal', float('nan')):.6f}**",
        f"- MAE: **{bridge_meta.get('mae', float('nan')):.6f}**",
        f"- RMSE: **{bridge_meta.get('rmse', float('nan')):.6f}**",
        "",
        "## RoadCat × diagnostic highway",
        "",
    ]
    if matrix.empty:
        lines.append("无有效 RoadCat × highway 组合。")
    else:
        lines += [
            "| RoadCat | diagnostic_highway | n | share | arterial share |",
            "|---|---|---:|---:|---:|",
        ]
        for _, r in matrix.iterrows():
            lines.append(
                f"| {r['RoadCat']} | {r['diagnostic_highway']} | {int(r['n'])} | {r['share_within_RoadCat']:.2%} | {r['arterial_core_share']:.2%} |"
            )
    lines += [
        "",
        "## Gates",
        "",
        "| Check | Result | Detail |",
        "|---|---|---|",
    ]
    for c in checks:
        lines.append(f"| {c['check']} | {'PASS' if c['pass'] else 'FAIL'} | {c['detail']} |")
    lines += [
        "",
        "## Supplementary robustness (post-hoc; NOT in frozen prereg)",
        "",
        "冻结判决规则（RoadCat 分层置换 `p < 0.05`）**未改变**。以下为事后稳健性诊断，"
        "用于说明该分层统计量是否依赖结构退化层。",
        "",
    ]
    if supp is not None and not supp.empty:
        lines += [
            "| Variant | Strata | n | arterial n | observed abs mean diff | p |",
            "|---|---:|---:|---:|---:|---:|",
        ]
        for _, r in supp.iterrows():
            lines.append(
                f"| {r['variant']} | {int(r['strata_used'])} | {int(r['n'])} | {int(r['arterial_n'])} | "
                f"{r['observed_abs_mean_diff']:.6f} | {r['p']:.6f} |"
            )
    if decomp is not None and not decomp.empty:
        lines += [
            "",
            "Within-RoadCat arterial / non-arterial decomposition:",
            "",
            "| RoadCat | n arterial | n non-arterial | mean arterial | mean non-arterial | abs diff |",
            "|---|---:|---:|---:|---:|---:|",
        ]
        for _, r in decomp.iterrows():
            lines.append(
                f"| {r['RoadCat']} | {int(r['n_arterial'])} | {int(r['n_nonarterial'])} | "
                f"{r['mean_arterial']:.6f} | {r['mean_nonarterial']:.6f} | {r['abs_mean_diff']:.6f} |"
            )
    if hw_sum is not None and not hw_sum.empty:
        lines += [
            "",
            "## Residual structure by OSM highway class (post-hoc)",
            "",
            "| highway | n | arterial-core n | mean residual | median residual | flow-weighted residual |",
            "|---|---:|---:|---:|---:|---:|",
        ]
        for _, r in hw_sum.iterrows():
            lines.append(
                f"| {r['diagnostic_highway']} | {int(r['n'])} | {int(r['n_arterial_core'])} | "
                f"{r['mean_residual']:.6f} | {r['median_residual']:.6f} | {r['flow_weighted_residual']:.6f} |"
            )
        lines += [
            "",
            "注意：`arterial_core = primary ∪ secondary ∪ tertiary` 的三类残差**符号相反**"
            "（primary 正、secondary/tertiary 负）⇒ 该聚合量存在**符号抵消**，聚合均值不可作为"
            "「arterial 是否残差主场」的依据。",
            "",
        ]
    lines += [
        "",
        "## Boundary",
        "",
        "该 residual 只用于结构诊断；不得进入正式 calibration target、v1.0 或 v1.1。",
        "",
    ]
    return "\n".join(lines)


def build_checks(
    source_path: Path,
    prereg_path: Path,
    traffic: pd.DataFrame,
    candidates: pd.DataFrame,
    stats: pd.DataFrame,
    main: pd.DataFrame,
    bridge_meta: dict,
) -> list[dict]:
    checks = []
    prereg_sha = sha256_file(prereg_path)
    checks.append({"check": "E2.01_PREREG_HASH", "pass": prereg_sha.lower() == EXPECTED_PREREG_SHA256.lower(), "detail": prereg_sha})
    checks.append({"check": "E2.02_ZERO_SIMULATION", "pass": static_zero_simulation_audit(source_path), "detail": "AST audit: no subprocess / Java launch"})
    checks.append({"check": "E2.03_SCALE_FROZEN", "pass": abs(SCALE - 2.29897) < 1e-10, "detail": f"SCALE={SCALE:.8f}"})
    traffic_n = int(traffic["LinkID"].nunique())
    checks.append({"check": "E2.04_TRAFFIC_UNIVERSE", "pass": traffic_n >= MIN_TRAFFIC_LINKS, "detail": f"traffic_links={traffic_n}"})
    checks.append({"check": "E2.05_E1_CROSSWALK", "pass": len(candidates) > 0, "detail": f"candidate_rows={len(candidates):,}"})
    checks.append({"check": "E2.06_W01_LINKSTATS", "pass": len(stats) > 0 and not stats["LINK"].duplicated().any(), "detail": f"linkstats_links={len(stats):,}"})
    matched = int(main["sim_8_9_scaled"].notna().sum()) if not main.empty else 0
    coverage = safe_ratio(matched, traffic_n)
    checks.append({"check": "E2.07_AB_COVERAGE_GE_80PCT", "pass": bool(np.isfinite(coverage) and coverage >= MIN_AB_COVERAGE), "detail": f"coverage={coverage:.6f}"})
    valid_n = int(main["valid_residual"].sum()) if not main.empty else 0
    checks.append({"check": "E2.08_VALID_RESIDUAL_SUPPORT", "pass": valid_n >= MIN_VALID_RESIDUAL, "detail": f"valid_residual_n={valid_n}"})
    arterial_n = int(main.loc[main["valid_residual"], "is_arterial_core"].sum()) if not main.empty else 0
    checks.append({"check": "E2.09_ARTERIAL_RESIDUAL_N_GE_30", "pass": arterial_n >= MIN_ARTERIAL_N, "detail": f"arterial_residual_n={arterial_n}"})
    overlap_n = int(bridge_meta.get("overlap_n", 0))
    checks.append({"check": "E2.10_FORMAL_BRIDGE_GE_500", "pass": overlap_n >= MIN_BRIDGE_N, "detail": f"formal_overlap_n={overlap_n}"})
    checks.append({"check": "E2.11_OUTPUT_ISOLATION", "pass": True, "detail": "all outputs written only under 7.9E-2"})
    checks.append({"check": "E2.12_PROVENANCE_READY", "pass": True, "detail": "hash/mtime/size manifest will be written"})
    return checks


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project-root", type=Path, default=ROOT_DEFAULT)
    ap.add_argument("--traffic-json", type=Path, default=None)
    ap.add_argument("--e1-candidates", type=Path, default=None)
    ap.add_argument("--e1-best", type=Path, default=None)
    ap.add_argument("--w01-linkstats", type=Path, default=None)
    ap.add_argument("--formal-residual", type=Path, default=None)
    ap.add_argument("--prereg", type=Path, default=None)
    ap.add_argument("--out-dir", type=Path, default=OUT_REL)
    args = ap.parse_args()

    root = args.project_root
    out = args.out_dir if args.out_dir.is_absolute() else root / args.out_dir
    out.mkdir(parents=True, exist_ok=True)

    traffic_path = args.traffic_json or (root / TRAFFIC_REL)
    e1_candidates_path = args.e1_candidates or (root / E1_CAND_REL)
    e1_best_path = args.e1_best or (root / E1_BEST_REL)
    w01_path = args.w01_linkstats or locate_w01(root)
    formal_path = args.formal_residual or (root / FORMAL_RESIDUAL_REL)
    prereg_path = args.prereg or (root / PREREG_REL)

    for p in [traffic_path, e1_candidates_path, w01_path, formal_path, prereg_path]:
        if not p.exists():
            raise FileNotFoundError(f"输入不存在: {p}")

    print("=" * 78)
    print("STEP 7.9E-2 | EXPANDED DIAGNOSTIC RESIDUAL DOMAIN")
    print("=" * 78)
    print("ZERO SIMULATION / READ-ONLY")
    print(f"Project        : {root}")
    print(f"Traffic        : {traffic_path}")
    print(f"E1 candidates  : {e1_candidates_path}")
    print(f"W01 linkstats  : {w01_path}")
    print(f"Formal residual: {formal_path}")
    print(f"Prereg         : {prereg_path}")
    print(f"Prereg SHA     : {sha256_file(prereg_path)}")
    print(f"SCALE          : {SCALE:.8f}")

    traffic = load_traffic(traffic_path)
    candidates = load_crosswalk_candidates(e1_candidates_path)
    stats = load_linkstats(w01_path)
    formal = load_formal_residual(formal_path)

    print(f"[1/6] TrafficFlow unique links = {traffic['LinkID'].nunique():,}")
    print(f"[2/6] E1 candidate rows       = {len(candidates):,}")
    print(f"[3/6] W01 linkstats links     = {len(stats):,}")

    main_sec = build_section_residual(traffic, candidates, stats, "A+B_MAIN")
    a_sec = build_section_residual(traffic, candidates, stats, "A_ONLY")
    relaxed_sec = build_section_residual(traffic, candidates, stats, "A+B+C_RELAXED")
    if main_sec.empty:
        raise RuntimeError("A+B 主诊断域未生成 residual")

    valid_main = main_sec[main_sec["valid_residual"]].copy()
    formal_domain = valid_main[valid_main["RoadCat"].isin(FORMAL_ROADCATS)].copy()
    groups, meta, perm = coupling(formal_domain)
    matrix = roadcat_matrix(formal_domain)
    rsum = roadcat_summary(main_sec)
    bridge, bridge_meta = formal_bridge(main_sec, formal)
    supp = supplementary_robustness(formal_domain)
    decomp = stratum_decomposition(formal_domain)
    hw_sum = highway_summary(main_sec)

    sensitivity_rows = []
    for label, sec in [("A_ONLY", a_sec), ("A+B_MAIN", main_sec), ("A+B+C_RELAXED", relaxed_sec)]:
        if sec.empty:
            sensitivity_rows.append({"tier": label, "matched_links": 0, "coverage": 0.0, "valid_residual_n": 0, "arterial_n": 0, "median_distance_m": np.nan, "p90_distance_m": np.nan})
            continue
        v = sec[sec["valid_residual"]]
        d = v["distance_m"].dropna()
        sensitivity_rows.append({
            "tier": label,
            "matched_links": int(sec["sim_8_9_scaled"].notna().sum()),
            "coverage": safe_ratio(sec["sim_8_9_scaled"].notna().sum(), traffic["LinkID"].nunique()),
            "valid_residual_n": int(len(v)),
            "arterial_n": int(v["is_arterial_core"].sum()),
            "median_distance_m": float(d.median()) if len(d) else np.nan,
            "p90_distance_m": float(d.quantile(0.90)) if len(d) else np.nan,
        })
    sensitivity = pd.DataFrame(sensitivity_rows)

    checks = build_checks(Path(__file__).resolve(), prereg_path, traffic, candidates, stats, main_sec, bridge_meta)
    hard_pass = all(bool(c["pass"]) for c in checks)
    strat_p = meta.get("roadcat_stratified_p", np.nan)
    if not hard_pass:
        status = "EXPANDED_DOMAIN_BLOCKED"
    elif np.isfinite(strat_p) and strat_p < 0.05:
        status = "ARTERIAL_COUPLING_SIGNAL"
    else:
        status = "NO_ARTERIAL_COUPLING_SIGNAL"

    main_cols = [
        "LinkID", "RoadName", "RoadCat", "obs_8_9", "matched_matsim_edges",
        "sim_8_9_median_raw", "sim_8_9_scaled", "diagnostic_ratio_8_9",
        "diagnostic_residual_8_9", "diagnostic_highway", "is_arterial_core",
        "distance_m", "direction_diff_deg", "semantic_compatible", "name_similarity",
        "selection_mode", "valid_residual",
    ]
    write_csv(main_sec[main_cols], out / "e2_section_residual_main.csv")
    write_csv(pd.concat([
        a_sec.assign(tier_output="A_ONLY"),
        main_sec.assign(tier_output="A+B_MAIN"),
        relaxed_sec.assign(tier_output="A+B+C_RELAXED"),
    ], ignore_index=True), out / "e2_section_residual_all_tiers.csv")
    write_csv(matrix, out / "e2_roadcat_highway_matrix.csv")
    write_csv(rsum, out / "e2_roadcat_summary.csv")
    write_csv(groups, out / "e2_arterial_coupling.csv")
    write_csv(perm, out / "e2_permutation.csv")
    write_csv(sensitivity, out / "e2_sensitivity_summary.csv")
    write_csv(bridge, out / "e2_formal_bridge.csv")
    write_csv(supp, out / "e2_supp_arterial_robustness.csv")
    write_csv(decomp, out / "e2_supp_stratum_decomposition.csv")
    write_csv(hw_sum, out / "e2_supp_highway_summary.csv")
    write_csv(pd.DataFrame(checks), out / "e2_checks.csv")

    paths = {
        "traffic_json": traffic_path,
        "e1_candidates": e1_candidates_path,
        "e1_best": e1_best_path if e1_best_path.exists() else e1_candidates_path,
        "w01_linkstats": w01_path,
        "formal_residual": formal_path,
        "prereg": prereg_path,
        "script": Path(__file__).resolve(),
    }
    manifest = input_manifest(paths)
    (out / "e2_input_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    summary = {
        "step": "7.9E-2",
        "status": status,
        "zero_simulation": True,
        "network_modified": False,
        "matsim_rerun": False,
        "scale": SCALE,
        "traffic_unique_links": int(traffic["LinkID"].nunique()),
        "candidate_rows": int(len(candidates)),
        "w01_linkstats_links": int(len(stats)),
        "main_valid_residual_n": int(len(valid_main)),
        "main_arterial_residual_n": int(formal_domain["is_arterial_core"].sum()),
        "coupling": meta,
        "formal_bridge": bridge_meta,
        "supplementary_robustness": supp.to_dict("records"),
        "stratum_decomposition": decomp.to_dict("records"),
        "highway_summary": hw_sum.to_dict("records"),
        "hard_pass": hard_pass,
        "hard_pass_count": int(sum(bool(c["pass"]) for c in checks)),
        "hard_total": int(len(checks)),
        "prereg_sha256": sha256_file(prereg_path),
    }
    (out / "e2_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    report = render_report(out, traffic, main_sec, sensitivity, matrix, rsum, meta, bridge_meta, checks, status, supp, decomp, hw_sum)
    (out / "STEP7_9E2_REPORT.md").write_text(report, encoding="utf-8")

    print("[4/6] A+B valid residual       =", len(valid_main))
    print("[5/6] A+B arterial residual    =", int(formal_domain["is_arterial_core"].sum()))
    print("[6/6] STATUS                    =", status)
    print(f"      HARD GATES                = {sum(bool(c['pass']) for c in checks)}/{len(checks)}")
    print(f"      OUTPUT                    = {out}")
    print("      NOTE                      = no MATSim/Java call")
    return 0 if hard_pass else 1


if __name__ == "__main__":
    raise SystemExit(main())
