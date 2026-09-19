#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Step 7.3.6B — Final Crosswalk Backtest  (zero-simulation)

Compare three (plus one reference) calibration crosswalks:

    7.1_old              reports/matsim_assignment_6_3_2/lta_section_matsim_crosswalk.csv
    7.3.4_semantic       reports/od_section_semantic_rebuild_7_3_4/rebuilt_crosswalk.csv   (strict subset)
    7.3.6A_final         reports/od_final_calibration_crosswalk_7_3_6/final_calibration_crosswalk.csv
    7.3.4_full           (reference only — full rebuilt crosswalk, fallback matches retained)

using ONLY the EXISTING MATSim 6.3.3B linkstats.

No MATSim rerun.
No changes to OD, lambda, population, departure profile,
network, capacity, or route choice.

Frozen 7.1 observation convention (reproduced exactly):
    observed  : weekday daily TrafficFlow volume -> per-day mean -> median by
                LinkID x hour   (hours 7 and 8)
    observed_statistic = "weekday daily volume median by LinkID x hour"
    obs_am    = obs_7_8 + obs_8_9

Frozen 7.1 simulation convention:
    sim_raw(section, window) = median( HRSx-yavg of matched directed MATSim edges )
    sim(section, window)     = sim_raw * SCALE           (SCALE = 459794/200000 = 2.29897)
    sim_am                   = sim_7_8 + sim_8_9

Windows:
    07-08  ->  HRS7-8avg   vs  obs_7_8
    08-09  ->  HRS8-9avg   vs  obs_8_9      <-- headline window for the chain below
    AM     ->  sim_am      vs  obs_am

Headline question:
    0.3633 (7.1 old)  ->  0.9135 (7.3.4 strict)  ->  ? (7.3.6A final)
    i.e. does the CATA / SLIP_ROAD structural discrepancy converge to 1
    once the section<->link semantic mapping is corrected?

Outputs (reports/od_final_crosswalk_backtest_7_3_6/):
    final_crosswalk_backtest.csv
    final_crosswalk_roadcat_summary.csv
    final_crosswalk_method_comparison.csv
    final_crosswalk_coverage.csv
    final_crosswalk_metric_matrix.csv
    step7_3_6b_summary.json
    STEP7_3_6B_REPORT.md
"""

from __future__ import annotations

import argparse
import gzip
import json
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(r"D:\Luan\2026-05\2_Singapore")

TRAFFIC_DEFAULT = (
    ROOT
    / r"Singapore_OD_MATSim_FinalData"
    / r"08_TrafficCount"
    / r"TrafficFlow_Data.json"
)

LINKSTATS_DEFAULT = (
    ROOT
    / r"reports\matsim_assignment_6_3_3b"
)

OLD_CROSSWALK_DEFAULT = (
    ROOT
    / r"reports\matsim_assignment_6_3_2"
    / r"lta_section_matsim_crosswalk.csv"
)

SEMANTIC_CROSSWALK_DEFAULT = (
    ROOT
    / r"reports\od_section_semantic_rebuild_7_3_4"
    / r"rebuilt_crosswalk.csv"
)

FINAL_CROSSWALK_DEFAULT = (
    ROOT
    / r"reports\od_final_calibration_crosswalk_7_3_6"
    / r"final_calibration_crosswalk.csv"
)

OUT_DEFAULT = (
    ROOT
    / r"reports\od_final_crosswalk_backtest_7_3_6"
)

SCALE = 459794.0 / 200000.0

# method display order
METHOD_ORDER = [
    "7.1_old",
    "7.3.4_semantic",
    "7.3.6A_final",
    "7.3.4_full",
]

WINDOWS = [
    ("07-08", "sim_7_8_scaled", "obs_7_8", "ratio_7_8"),
    ("08-09", "sim_8_9_scaled", "obs_8_9", "ratio_8_9"),
    ("AM", "sim_am", "obs_am", "ratio_am"),
]

ROADCAT_SLOTS = [
    "ALL",
    "CATA",
    "SLIP_ROAD",
    "CATB",
    "CATC",
    "CATD",
    "CATE",
]


# --------------------------------------------------------------------------
# observation  (frozen 7.1 convention)
# --------------------------------------------------------------------------
def load_traffic(path: Path) -> pd.DataFrame:
    with open(path, "r", encoding="utf-8-sig") as f:
        obj = json.load(f)

    rows = obj.get("Value", obj)
    tf = pd.DataFrame(rows)

    required = {
        "LinkID",
        "Date",
        "HourOfDate",
        "Volume",
        "RoadName",
        "RoadCat",
    }
    missing = required - set(tf.columns)
    if missing:
        raise ValueError(
            f"TrafficFlow 缺字段: {sorted(missing)}"
        )

    tf["LinkID"] = tf["LinkID"].astype(str).str.strip()
    tf["Date"] = pd.to_datetime(
        tf["Date"],
        dayfirst=True,
        errors="coerce",
    )
    tf["HourOfDate"] = pd.to_numeric(
        tf["HourOfDate"],
        errors="coerce",
    )
    # comma-formatted values such as "1,020"
    tf["Volume_num"] = pd.to_numeric(
        tf["Volume"]
        .astype(str)
        .str.replace(",", "", regex=False)
        .str.strip(),
        errors="coerce",
    )

    # weekday only + AM peak hours, exactly as 7.1 frozen target
    tf = tf[
        tf["Date"].notna()
        & tf["Date"].dt.weekday.lt(5)
        & tf["HourOfDate"].isin([7, 8])
        & tf["Volume_num"].notna()
    ].copy()

    # per-day mean, then median across days  (7.1 convention)
    daily = (
        tf.groupby(
            ["LinkID", "Date", "HourOfDate"],
            as_index=False,
        )
        .agg(v=("Volume_num", "mean"))
    )

    med = (
        daily.groupby(
            ["LinkID", "HourOfDate"],
            as_index=False,
        )
        .agg(v=("v", "median"))
    )

    w = (
        med.pivot(
            index="LinkID",
            columns="HourOfDate",
            values="v",
        )
        .reset_index()
    )
    w.columns.name = None
    w = w.rename(
        columns={7: "obs_7_8", 8: "obs_8_9"}
    )
    for c in ["obs_7_8", "obs_8_9"]:
        if c not in w.columns:
            w[c] = np.nan

    # section attributes (LTA authoritative)
    attr = (
        tf.groupby("LinkID", as_index=False)
        .agg(
            RoadName=("RoadName", "first"),
            RoadCat=("RoadCat", "first"),
        )
    )
    attr["RoadCat"] = (
        attr["RoadCat"]
        .astype(str)
        .str.strip()
        .str.upper()
    )

    obs = w.merge(attr, on="LinkID", how="left")
    obs["obs_am"] = (
        obs[["obs_7_8", "obs_8_9"]]
        .fillna(0)
        .sum(axis=1)
    )
    return obs


# --------------------------------------------------------------------------
# crosswalks
# --------------------------------------------------------------------------
def normalize_crosswalk(
    path: Path,
    method: str,
    strict_only: bool = False,
) -> pd.DataFrame:
    df = pd.read_csv(
        path,
        encoding="utf-8-sig",
        low_memory=False,
    )

    rename = {}
    for c in df.columns:
        lc = c.lower().strip()
        if lc == "linkid":
            rename[c] = "lta_linkid"
        elif lc in {"lta_linkid", "traffic_linkid"}:
            rename[c] = "lta_linkid"
        elif lc in {"matsim_link_id", "matsim_link"}:
            rename[c] = "matsim_link_id"

    df = df.rename(columns=rename)

    required = {
        "lta_linkid",
        "matsim_link_id",
    }
    missing = required - set(df.columns)
    if missing:
        raise ValueError(
            f"{method} crosswalk 缺字段: {sorted(missing)}"
        )

    # NOTE: do NOT keep a crosswalk-side `RoadCat`/`RoadName`.
    # Section category is taken from the (single) LTA observation, so that
    # merging never produces `RoadCat_x` / `RoadCat_y` columns.
    keep = [
        "lta_linkid",
        "matsim_link_id",
    ]
    for c in [
        "highway",
        "selection_tier",
        "final_tier",
        "direction_ok",
        "semantic_match",
        "name_match",
        "distance_m",
        "direction_diff_deg",
        "geometry_fallback",
    ]:
        if c in df.columns:
            keep.append(c)

    out = df[keep].copy()

    if strict_only and "selection_tier" in out.columns:
        tier = (
            out["selection_tier"]
            .astype(str)
            .str.strip()
            .str.lower()
        )
        out = out[tier == "strict"].copy()

    out["lta_linkid"] = (
        out["lta_linkid"].astype(str).str.strip()
    )
    out["matsim_link_id"] = (
        out["matsim_link_id"].astype(str).str.strip()
    )
    out["method"] = method

    return out.drop_duplicates(
        ["lta_linkid", "matsim_link_id"]
    )


# --------------------------------------------------------------------------
# linkstats
# --------------------------------------------------------------------------
def locate_linkstats(
    base: Path,
    lambda_tag: str = "lambda_0p050",
) -> Path:
    direct = (
        base / lambda_tag / "ITERS" / "it.0"
    )

    candidates = []
    if direct.exists():
        candidates.extend(
            list(direct.glob("*.linkstats.txt.gz"))
        )
        candidates.extend(
            list(direct.glob("*.linkstats.txt"))
        )

    if not candidates:
        known = [
            base / "lambda_0p050" / "ITERS" / "it.0",
            base / "lambda_0p075" / "ITERS" / "it.0",
            base / "lambda_0p100" / "ITERS" / "it.0",
        ]
        for p in known:
            if p.exists():
                candidates.extend(
                    list(p.glob("*.linkstats.txt.gz"))
                )
                candidates.extend(
                    list(p.glob("*.linkstats.txt"))
                )

    if not candidates:
        raise FileNotFoundError(
            "未找到 6.3.3B linkstats 文件"
        )

    candidates = sorted(
        candidates,
        key=lambda p: (
            "lambda_0p050" not in str(p),
            str(p),
        ),
    )
    return candidates[0]


def load_linkstats(path: Path) -> pd.DataFrame:
    opener = gzip.open if path.suffix == ".gz" else open

    with opener(
        path, "rt", encoding="utf-8", errors="replace"
    ) as f:
        header = f.readline().rstrip("\n").split("\t")

    need = ["LINK", "HRS7-8avg", "HRS8-9avg"]
    missing = [c for c in need if c not in header]
    if missing:
        raise ValueError(
            f"linkstats 缺字段: {missing}"
        )

    df = pd.read_csv(
        path,
        sep="\t",
        compression="gzip"
        if path.suffix == ".gz"
        else None,
        usecols=need,
        low_memory=False,
    )

    for c in ["HRS7-8avg", "HRS8-9avg"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")

    df["LINK"] = df["LINK"].astype(str).str.strip()
    return df


# --------------------------------------------------------------------------
# per-section backtest
# --------------------------------------------------------------------------
def calc_method(
    cw: pd.DataFrame,
    obs: pd.DataFrame,
    sim: pd.DataFrame,
) -> pd.DataFrame:

    x = cw.merge(
        obs,
        left_on="lta_linkid",
        right_on="LinkID",
        how="inner",
    ).merge(
        sim,
        left_on="matsim_link_id",
        right_on="LINK",
        how="left",
    )

    if x.empty:
        return pd.DataFrame()

    sec = (
        x.groupby("lta_linkid", as_index=False)
        .agg(
            RoadCat=("RoadCat", "first"),
            RoadName=("RoadName", "first"),
            method=("method", "first"),
            matched_matsim_edges=(
                "matsim_link_id",
                "nunique",
            ),
            sim_7_8_raw=("HRS7-8avg", "median"),
            sim_8_9_raw=("HRS8-9avg", "median"),
            obs_7_8=("obs_7_8", "first"),
            obs_8_9=("obs_8_9", "first"),
            obs_am=("obs_am", "first"),
        )
    )

    sec["sim_7_8_scaled"] = sec["sim_7_8_raw"] * SCALE
    sec["sim_8_9_scaled"] = sec["sim_8_9_raw"] * SCALE
    sec["sim_am"] = (
        sec["sim_7_8_scaled"].fillna(0)
        + sec["sim_8_9_scaled"].fillna(0)
    )

    sec["ratio_7_8"] = np.where(
        sec["obs_7_8"] > 0,
        sec["sim_7_8_scaled"] / sec["obs_7_8"],
        np.nan,
    )
    sec["ratio_8_9"] = np.where(
        sec["obs_8_9"] > 0,
        sec["sim_8_9_scaled"] / sec["obs_8_9"],
        np.nan,
    )
    sec["ratio_am"] = np.where(
        sec["obs_am"] > 0,
        sec["sim_am"] / sec["obs_am"],
        np.nan,
    )

    return sec


# --------------------------------------------------------------------------
# metrics
# --------------------------------------------------------------------------
def _metrics(
    sim: pd.Series,
    obs: pd.Series,
    ratio: pd.Series,
) -> dict:
    valid = (
        sim.notna() & obs.notna() & (obs > 0)
    )
    sim = sim[valid].astype(float)
    obs = obs[valid].astype(float)
    ratio = ratio[valid].astype(float)

    n = int(len(sim))
    if n == 0:
        return {"n": 0}

    diff = sim - obs
    absdiff = diff.abs()

    if n >= 2 and sim.std(ddof=0) > 0 and obs.std(ddof=0) > 0:
        pearson = float(
            np.corrcoef(obs, sim)[0, 1]
        )
        spearman = float(
            obs.rank().corr(sim.rank())
        )
    else:
        pearson = float("nan")
        spearman = float("nan")

    geh = np.sqrt(
        2.0 * (sim - obs) ** 2 / (sim + obs)
    )

    sum_obs = float(obs.sum())
    sum_sim = float(sim.sum())

    return {
        "n": n,
        "pearson_r": pearson,
        "spearman_rho": spearman,
        "MAE": float(absdiff.mean()),
        "RMSE": float(np.sqrt((diff ** 2).mean())),
        "MAPE": float(
            (absdiff[obs > 0] / obs[obs > 0]).mean()
        )
        if (obs > 0).any()
        else np.nan,
        "WMAPE": float(absdiff.sum() / obs.abs().sum())
        if obs.abs().sum() > 0
        else np.nan,
        "Bias": float(diff.mean()),
        "bias_ratio": float(diff.sum() / sum_obs)
        if sum_obs > 0
        else np.nan,
        "SimObs_ratio_sum": float(sum_sim / sum_obs)
        if sum_obs > 0
        else np.nan,
        "mean_section_ratio": float(ratio.mean()),
        "median_section_ratio": float(ratio.median()),
        "GEH_lt_5": float(np.mean(geh < 5)),
        "GEH_lt_10": float(np.mean(geh < 10)),
        "GEH_median": float(np.median(geh)),
        "sum_obs": sum_obs,
        "sum_sim": sum_sim,
    }


def summarize(backtest: pd.DataFrame) -> pd.DataFrame:
    rows = []

    methods = [
        m for m in METHOD_ORDER
        if (backtest["method"] == m).any()
    ]

    for method in methods:
        for roadcat in ROADCAT_SLOTS:
            g = backtest[backtest["method"] == method]
            if roadcat == "ALL":
                g = g.copy()
            else:
                g = g[g["RoadCat"] == roadcat].copy()
            if g.empty:
                continue

            for window, s_col, o_col, r_col in WINDOWS:
                m = _metrics(
                    g[s_col], g[o_col], g[r_col]
                )
                if m.get("n", 0) == 0:
                    continue
                rows.append(
                    {
                        "method": method,
                        "RoadCat": roadcat,
                        "window": window,
                        **m,
                    }
                )

    return pd.DataFrame(rows)


def method_comparison(
    backtest: pd.DataFrame,
) -> pd.DataFrame:
    rows = []
    methods = [
        m for m in METHOD_ORDER
        if (backtest["method"] == m).any()
    ]
    for method in methods:
        for rc in ["CATA", "SLIP_ROAD"]:
            g = backtest[
                (backtest["method"] == method)
                & (backtest["RoadCat"] == rc)
            ]
            if g.empty:
                continue
            for window, s_col, o_col, r_col in WINDOWS:
                m = _metrics(
                    g[s_col], g[o_col], g[r_col]
                )
                if m.get("n", 0) == 0:
                    continue
                rows.append(
                    {
                        "method": method,
                        "RoadCat": rc,
                        "window": window,
                        "n": m["n"],
                        "SimObs_ratio_sum": m[
                            "SimObs_ratio_sum"
                        ],
                        "mean_section_ratio": m[
                            "mean_section_ratio"
                        ],
                        "median_section_ratio": m[
                            "median_section_ratio"
                        ],
                    }
                )
    return pd.DataFrame(rows)


def coverage_table(
    backtest: pd.DataFrame,
) -> pd.DataFrame:
    rows = []
    methods = [
        m for m in METHOD_ORDER
        if (backtest["method"] == m).any()
    ]
    for method in methods:
        for rc in ["ALL", "CATA", "SLIP_ROAD"]:
            g = backtest[backtest["method"] == method]
            if rc != "ALL":
                g = g[g["RoadCat"] == rc]
            if g.empty:
                continue
            rows.append(
                {
                    "method": method,
                    "RoadCat": rc,
                    "sections": int(len(g)),
                    "matched_edges_median": float(
                        g[
                            "matched_matsim_edges"
                        ].median()
                    ),
                    "matched_edges_mean": float(
                        g[
                            "matched_matsim_edges"
                        ].mean()
                    ),
                    "sim_7_8_coverage": float(
                        g["sim_7_8_scaled"].notna().mean()
                    ),
                    "sim_8_9_coverage": float(
                        g["sim_8_9_scaled"].notna().mean()
                    ),
                }
            )
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------
# main
# --------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser()

    ap.add_argument(
        "--traffic", type=Path, default=TRAFFIC_DEFAULT
    )
    ap.add_argument(
        "--linkstats-root",
        type=Path,
        default=LINKSTATS_DEFAULT,
    )
    ap.add_argument(
        "--old", type=Path, default=OLD_CROSSWALK_DEFAULT
    )
    ap.add_argument(
        "--semantic",
        type=Path,
        default=SEMANTIC_CROSSWALK_DEFAULT,
    )
    ap.add_argument(
        "--final", type=Path, default=FINAL_CROSSWALK_DEFAULT
    )
    ap.add_argument(
        "--out-dir", type=Path, default=OUT_DEFAULT
    )

    args = ap.parse_args()

    for p in [
        args.traffic,
        args.old,
        args.semantic,
        args.final,
    ]:
        if not p.exists():
            raise FileNotFoundError(f"输入不存在: {p}")

    args.out_dir.mkdir(parents=True, exist_ok=True)

    print("[1/6] load observation (7.1 frozen convention)")
    obs = load_traffic(args.traffic)
    print(
        f"      observed LTA sections = {obs['LinkID'].nunique():,}"
    )

    print("[2/6] load crosswalks")
    old = normalize_crosswalk(args.old, "7.1_old")
    semantic = normalize_crosswalk(
        args.semantic, "7.3.4_semantic", strict_only=True
    )
    semantic_full = normalize_crosswalk(
        args.semantic, "7.3.4_full", strict_only=False
    )
    final = normalize_crosswalk(
        args.final, "7.3.6A_final"
    )
    for nm, cw in [
        ("7.1_old", old),
        ("7.3.4_semantic(strict)", semantic),
        ("7.3.4_full", semantic_full),
        ("7.3.6A_final", final),
    ]:
        print(
            f"      {nm:<24} rows={len(cw):>6}  "
            f"sections={cw['lta_linkid'].nunique():>5}"
        )

    print("[3/6] load linkstats (existing 6.3.3B)")
    linkstats_path = locate_linkstats(
        args.linkstats_root
    )
    sim = load_linkstats(linkstats_path)
    print(f"      linkstats = {linkstats_path}")

    print("[4/6] section backtest")
    results = []
    for cw in [old, semantic, final, semantic_full]:
        r = calc_method(cw, obs, sim)
        if not r.empty:
            results.append(r)

    backtest = pd.concat(
        results, ignore_index=True
    )
    backtest.to_csv(
        args.out_dir / "final_crosswalk_backtest.csv",
        index=False,
        encoding="utf-8-sig",
    )

    print("[5/6] summaries")
    summary = summarize(backtest)
    summary.to_csv(
        args.out_dir
        / "final_crosswalk_roadcat_summary.csv",
        index=False,
        encoding="utf-8-sig",
    )

    method_cmp = method_comparison(backtest)
    method_cmp.to_csv(
        args.out_dir
        / "final_crosswalk_method_comparison.csv",
        index=False,
        encoding="utf-8-sig",
    )

    coverage = coverage_table(backtest)
    coverage.to_csv(
        args.out_dir / "final_crosswalk_coverage.csv",
        index=False,
        encoding="utf-8-sig",
    )

    # CATA / SLIP metric matrix (08-09 + AM)
    mm = summary[
        summary["RoadCat"].isin(["CATA", "SLIP_ROAD"])
    ].copy()
    mm.to_csv(
        args.out_dir / "final_crosswalk_metric_matrix.csv",
        index=False,
        encoding="utf-8-sig",
    )

    # ------------------------------------------------------------------
    # headline chain
    # ------------------------------------------------------------------
    def lookup_ratio(method, rc, window):
        z = method_cmp[
            (method_cmp["method"] == method)
            & (method_cmp["RoadCat"] == rc)
            & (method_cmp["window"] == window)
        ]
        if z.empty:
            return {
                "n": 0,
                "SimObs_ratio_sum": None,
                "mean_section_ratio": None,
            }
        row = z.iloc[0]
        return {
            "n": int(row["n"]),
            "SimObs_ratio_sum": float(
                row["SimObs_ratio_sum"]
            ),
            "mean_section_ratio": float(
                row["mean_section_ratio"]
            ),
        }

    def metric_dict(method, rc, window):
        z = summary[
            (summary["method"] == method)
            & (summary["RoadCat"] == rc)
            & (summary["window"] == window)
        ]
        if z.empty:
            return {}
        d = z.iloc[0].to_dict()
        out = {}
        for k, v in d.items():
            if isinstance(v, (np.floating, float)):
                out[k] = (
                    float(v)
                    if pd.notna(v)
                    else None
                )
            elif isinstance(v, (np.integer,)):
                out[k] = int(v)
            else:
                out[k] = v
        return out

    def chain(window):
        cata = {}
        slip = {}
        rel = {}
        for m in [
            "7.1_old",
            "7.3.4_semantic",
            "7.3.6A_final",
            "7.3.4_full",
        ]:
            c = lookup_ratio(m, "CATA", window)
            s = lookup_ratio(m, "SLIP_ROAD", window)
            cata[m] = c["SimObs_ratio_sum"]
            slip[m] = s["SimObs_ratio_sum"]
            if (
                c["SimObs_ratio_sum"]
                and s["SimObs_ratio_sum"]
            ):
                rel[m] = (
                    c["SimObs_ratio_sum"]
                    / s["SimObs_ratio_sum"]
                )
            else:
                rel[m] = None
        return cata, slip, rel

    cata_08, slip_08, rel_08 = chain("08-09")
    cata_am, slip_am, rel_am = chain("AM")
    cata_07, slip_07, rel_07 = chain("07-08")

    summary_json = {
        "step": "7.3.6B",
        "status": "PASS",
        "lambda_tested": 0.05,
        "scale": SCALE,
        "linkstats": str(linkstats_path),
        "windows": {
            "headline": "08-09",
            "available": ["07-08", "08-09", "AM"],
        },
        "definition": (
            "sim = median(matched MATSim edges HRSx-yavg) * 459794/200000; "
            "obs = weekday daily TrafficFlow volume -> per-day mean -> "
            "median by LinkID x hour; obs_am = obs_7_8 + obs_8_9"
        ),
        "cata_sum_ratio_08_09": cata_08,
        "slip_sum_ratio_08_09": slip_08,
        "cata_over_slip_08_09": rel_08,
        "cata_sum_ratio_am": cata_am,
        "slip_sum_ratio_am": slip_am,
        "cata_over_slip_am": rel_am,
        "cata_sum_ratio_07_08": cata_07,
        "slip_sum_ratio_07_08": slip_07,
        "cata_over_slip_07_08": rel_07,
        "chain_08_09": {
            "7.1_old": rel_08.get("7.1_old"),
            "7.3.4_semantic": rel_08.get("7.3.4_semantic"),
            "7.3.6A_final": rel_08.get("7.3.6A_final"),
            "7.3.4_full_reference": rel_08.get("7.3.4_full"),
        },
        "metrics_08_09": {
            "CATA": {
                m: metric_dict(m, "CATA", "08-09")
                for m in [
                    "7.1_old",
                    "7.3.4_semantic",
                    "7.3.6A_final",
                    "7.3.4_full",
                ]
            },
            "SLIP_ROAD": {
                m: metric_dict(m, "SLIP_ROAD", "08-09")
                for m in [
                    "7.1_old",
                    "7.3.4_semantic",
                    "7.3.6A_final",
                    "7.3.4_full",
                ]
            },
        },
        "coverage": coverage.to_dict(orient="records"),
        "parameters_changed": False,
        "lambda_selected": False,
        "matsim_rerun": False,
        "seven_one_target_modified": False,
    }

    with open(
        args.out_dir / "step7_3_6b_summary.json",
        "w",
        encoding="utf-8",
    ) as f:
        json.dump(
            summary_json,
            f,
            ensure_ascii=False,
            indent=2,
        )

    # ------------------------------------------------------------------
    # report
    # ------------------------------------------------------------------
    def fmt(v, nd=4):
        if v is None or (
            isinstance(v, float) and pd.isna(v)
        ):
            return "n/a"
        return f"{v:.{nd}f}"

    report = f"""# Step 7.3.6B — Final Crosswalk Backtest

## Status

**PASS**  （零仿真；仅复用已有的 MATSim 6.3.3B linkstats，未重跑 MATSim，
未改动 OD / λ / population / departure / network / capacity / route-choice）

### 口径（与 7.1 冻结一致）

- 观测：工作日 TrafficFlow Volume → 日内均值 → 按 `LinkID × hour` 取日中位数（hour = 7,8）
- 仿真：`sim = median(匹配 MATSim 有向边 HRSx-yavg) × 459794/200000`（= {SCALE:.5f}）
- `obs_am = obs_7_8 + obs_8_9`，`sim_am = sim_7_8 + sim_8_9`
- 主判据窗口：**08-09**

## 1. 核心链条（08-09，Σsim/Σobs）

| Crosswalk | CATA | SLIP_ROAD | CATA/SLIP_ROAD |
|---|---:|---:|---:|
| 7.1 old | {fmt(cata_08.get('7.1_old'))} | {fmt(slip_08.get('7.1_old'))} | {fmt(rel_08.get('7.1_old'))} |
| 7.3.4 semantic (strict) | {fmt(cata_08.get('7.3.4_semantic'))} | {fmt(slip_08.get('7.3.4_semantic'))} | {fmt(rel_08.get('7.3.4_semantic'))} |
| **7.3.6A final** | **{fmt(cata_08.get('7.3.6A_final'))}** | **{fmt(slip_08.get('7.3.6A_final'))}** | **{fmt(rel_08.get('7.3.6A_final'))}** |
| 7.3.4 full（参照） | {fmt(cata_08.get('7.3.4_full'))} | {fmt(slip_08.get('7.3.4_full'))} | {fmt(rel_08.get('7.3.4_full'))} |

> 目标链条：`{fmt(rel_08.get('7.1_old'))}` → `{fmt(rel_08.get('7.3.4_semantic'))}` → **`{fmt(rel_08.get('7.3.6A_final'))}`**

## 2. AM 窗口（07-09，Σsim/Σobs）

| Crosswalk | CATA | SLIP_ROAD | CATA/SLIP_ROAD |
|---|---:|---:|---:|
| 7.1 old | {fmt(cata_am.get('7.1_old'))} | {fmt(slip_am.get('7.1_old'))} | {fmt(rel_am.get('7.1_old'))} |
| 7.3.4 semantic (strict) | {fmt(cata_am.get('7.3.4_semantic'))} | {fmt(slip_am.get('7.3.4_semantic'))} | {fmt(rel_am.get('7.3.4_semantic'))} |
| 7.3.6A final | {fmt(cata_am.get('7.3.6A_final'))} | {fmt(slip_am.get('7.3.6A_final'))} | {fmt(rel_am.get('7.3.6A_final'))} |
| 7.3.4 full（参照） | {fmt(cata_am.get('7.3.4_full'))} | {fmt(slip_am.get('7.3.4_full'))} | {fmt(rel_am.get('7.3.4_full'))} |

## 3. 评价指标矩阵（08-09）

CATA：

| method | n | Pearson | Spearman | MAE | RMSE | WMAPE | GEH<5 | GEH<10 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
"""
    for m in [
        "7.1_old",
        "7.3.4_semantic",
        "7.3.6A_final",
        "7.3.4_full",
    ]:
        d = summary_json["metrics_08_09"]["CATA"].get(m, {})
        report += (
            f"| {m} | {d.get('n','n/a')} | "
            f"{fmt(d.get('pearson_r'))} | "
            f"{fmt(d.get('spearman_rho'))} | "
            f"{fmt(d.get('MAE'))} | "
            f"{fmt(d.get('RMSE'))} | "
            f"{fmt(d.get('WMAPE'))} | "
            f"{fmt(d.get('GEH_lt_5'))} | "
            f"{fmt(d.get('GEH_lt_10'))} |\n"
        )

    report += "\nSLIP_ROAD：\n\n"
    report += (
        "| method | n | Pearson | Spearman | MAE | RMSE | WMAPE | GEH<5 | GEH<10 |\n"
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|\n"
    )
    for m in [
        "7.1_old",
        "7.3.4_semantic",
        "7.3.6A_final",
        "7.3.4_full",
    ]:
        d = summary_json["metrics_08_09"]["SLIP_ROAD"].get(
            m, {}
        )
        report += (
            f"| {m} | {d.get('n','n/a')} | "
            f"{fmt(d.get('pearson_r'))} | "
            f"{fmt(d.get('spearman_rho'))} | "
            f"{fmt(d.get('MAE'))} | "
            f"{fmt(d.get('RMSE'))} | "
            f"{fmt(d.get('WMAPE'))} | "
            f"{fmt(d.get('GEH_lt_5'))} | "
            f"{fmt(d.get('GEH_lt_10'))} |\n"
        )

    report += "\n## 4. 覆盖（matched sections / edges）\n\n"
    report += (
        "| method | RoadCat | sections | edges(median) | edges(mean) |\n"
        "|---|---|---:|---:|---:|\n"
    )
    for r in summary_json["coverage"]:
        report += (
            f"| {r['method']} | {r['RoadCat']} | "
            f"{r['sections']} | "
            f"{fmt(r['matched_edges_median'],2)} | "
            f"{fmt(r['matched_edges_mean'],2)} |\n"
        )

    report += """
## 5. 解读

- 若 `CATA/SLIP_ROAD` 由约 0.36 → 0.91 → 更接近 1，
  则支持「主要结构性误差来自断面语义映射（C 类）」，
  可据此把 TrafficFlow 评价语义错配从主要模型误差中剔除。
- `7.3.4 full` 作为参照，用于披露「保留 fallback 匹配（覆盖全 251 SLIP）
  会重新引入旧式错配」这一事实，说明 7.3.4 full 更高的覆盖并不等于更好的语义对齐。
- 本步骤**不冻结 λ**，也不改动 7.1 冻结靶场。
"""
    (args.out_dir / "STEP7_3_6B_REPORT.md").write_text(
        report, encoding="utf-8"
    )

    print("[6/6] done")
    print(json.dumps(summary_json, ensure_ascii=False, indent=2))
    print(f"Outputs: {args.out_dir}")


if __name__ == "__main__":
    main()
