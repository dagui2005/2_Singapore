#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Singapore OD -> MATSim
Step 5: Build doubly-constrained Gravity Prior OD.

Current frozen inputs:
    P_i  : reports/od_production/production.csv
    A_j  : reports/od_attraction_v21/attraction_v21.csv
           (actual attraction file name is auto-detected)
    C_ij : reports/od_impedance/impedance_matrix.parquet

Core model:
    T_ij = alpha_i * beta_j * P_i^phys * A_j * exp(-lambda * C_ij)

where:
    - P_i^phys is the estimated production directed to physical Workplace PAs.
    - A_j is Census-controlled physical Workplace attraction.
    - C_ij is static shortest travel time in minutes.
    - alpha_i / beta_j are solved by iterative proportional fitting / Fratar
      so row sums and column sums match exactly.

IMPORTANT MODEL ACCOUNTING:
    Total employed residents ~= 2,208,358
    Physical workplace control = 1,935,235
    Difference ~= 273,123, corresponding to the three non-physical
    Workplace categories:
        Other Planning Areas or Outside Singapore
        No Fixed Location for Work
        Works from Home

    These destinations do not have physical Subzone coordinates.
    Therefore Step 5 does NOT force them into the 332x332 physical OD.

    Instead:
        physical_workplace_share =
            physical_workplace_total / employed_total

    and:
        P_i^phys = P_i * physical_workplace_share

    This proportional allocation is explicitly an ASSUMPTION because the current
    Census data do not provide residence-Subzone distributions for those three
    special workplace categories.

    The special mass is written to special_destination_mass.csv rather than
    hidden.

LAMBDA:
    Default sensitivity grid:
        0.05, 0.075, 0.10, 0.125, 0.15 per minute

    No single lambda is declared "truth" yet. The candidate with the best
    subsequent traffic-flow fit will be selected during calibration.

NETWORK NOTE:
    Five remote/no-road-access Subzones were flagged in Step 4. They remain in
    the 332-zone matrix for structural completeness, but the script reports
    their production/attraction mass separately. They must be reviewed before
    using the OD for car MATSim.

Outputs:
    reports/od_prior/
        physical_production.csv
        special_destination_mass.csv
        prior_od_lambda_*.parquet
        prior_od_summary.csv
        prior_od_validation_lambda_*.json
        prior_od_diagnostics.csv

No TrafficFlow calibration is done here.
No MATSim loading is done here.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd


DEFAULT_PROJECT_ROOT = Path(r"D:\Luan\2026-05\2_Singapore")

PRODUCTION_REL = Path("reports/od_production/production.csv")
ATTRACTION_DIR_REL = Path("reports/od_attraction_v21")
IMPEDANCE_REL = Path("reports/od_impedance/impedance_matrix.parquet")

OUT_REL = Path("reports/od_prior")

DEFAULT_LAMBDAS = [0.05, 0.075, 0.10, 0.125, 0.15]
MAX_IPF_ITER = 10000
IPF_TOL = 1e-8
MIN_SEED = 1e-15


def find_attraction_file(root: Path) -> Path:
    folder = root / ATTRACTION_DIR_REL
    preferred = [
        folder / "attraction_v21.csv",
        folder / "attraction_v2.1.csv",
        folder / "attraction_v2.csv",
    ]
    for p in preferred:
        if p.exists():
            return p

    candidates = list(folder.glob("*attraction*.csv"))
    candidates = [
        p for p in candidates
        if "validation" not in p.name.lower()
        and "suspicious" not in p.name.lower()
        and "control" not in p.name.lower()
    ]
    if len(candidates) == 1:
        return candidates[0]

    raise FileNotFoundError(
        f"无法自动确定 Attraction 文件。\n目录: {folder}\n候选: {candidates}"
    )


def load_production(path: Path) -> pd.DataFrame:
    p = pd.read_csv(path, encoding="utf-8-sig", low_memory=False)

    required = {"zone_id"}
    missing = required - set(p.columns)
    if missing:
        raise ValueError(f"production.csv 缺少字段: {sorted(missing)}")

    # Find the work production field used by Step 2.
    candidates = [
        "work_trip_production",
        "P_work",
        "working_trip_production",
        "work_production",
    ]
    work_col = next((c for c in candidates if c in p.columns), None)
    if work_col is None:
        # Conservative fallback: search names containing work + production.
        for c in p.columns:
            cl = str(c).lower()
            if "work" in cl and "production" in cl:
                work_col = c
                break

    if work_col is None:
        raise ValueError(
            "无法从 production.csv 找到工作出行产生量字段。"
            f" 实际字段={list(p.columns)}"
        )

    p = p[["zone_id", work_col]].copy()
    p = p.rename(columns={work_col: "production_total"})
    p["zone_id"] = pd.to_numeric(p["zone_id"], errors="raise").astype(int)
    p["production_total"] = pd.to_numeric(
        p["production_total"], errors="coerce"
    ).fillna(0.0)

    if len(p) != 332:
        raise ValueError(
            f"production.csv 应有 332 个 Subzone，实际 {len(p)}"
        )

    return p


def load_attraction(path: Path) -> pd.DataFrame:
    a = pd.read_csv(path, encoding="utf-8-sig", low_memory=False)

    required = {"zone_id", "workplace_attraction"}
    missing = required - set(a.columns)
    if missing:
        raise ValueError(
            f"Attraction 文件缺少字段: {sorted(missing)}"
        )

    keep = ["zone_id", "subzone_code"]
    for c in [
        "subzone_name",
        "planning_area",
        "planning_area_norm",
        "workplace_employment",
        "workplace_attraction",
    ]:
        if c in a.columns:
            keep.append(c)

    a = a[keep].copy()
    a["zone_id"] = pd.to_numeric(
        a["zone_id"], errors="raise"
    ).astype(int)
    a["workplace_attraction"] = pd.to_numeric(
        a["workplace_attraction"], errors="coerce"
    ).fillna(0.0)

    if len(a) != 332:
        raise ValueError(
            f"Attraction 应有 332 个 Subzone，实际 {len(a)}"
        )

    if a["zone_id"].duplicated().any():
        raise ValueError("Attraction 中 zone_id 不唯一。")

    return a


def load_impedance(path: Path) -> pd.DataFrame:
    c = pd.read_parquet(path)

    required = {
        "origin_zone",
        "destination_zone",
        "travel_time_min",
        "reachable",
    }
    missing = required - set(c.columns)
    if missing:
        raise ValueError(
            f"impedance_matrix.parquet 缺少字段: {sorted(missing)}"
        )

    c["origin_zone"] = pd.to_numeric(
        c["origin_zone"], errors="raise"
    ).astype(int)
    c["destination_zone"] = pd.to_numeric(
        c["destination_zone"], errors="raise"
    ).astype(int)
    c["travel_time_min"] = pd.to_numeric(
        c["travel_time_min"], errors="coerce"
    )
    c["reachable"] = c["reachable"].astype(bool)

    expected = 332 * 332
    if len(c) != expected:
        raise ValueError(
            f"阻抗矩阵应为 {expected} 行，实际 {len(c)}"
        )

    if not c["reachable"].all():
        raise ValueError(
            "阻抗矩阵存在不可达 OD。"
            "Step 4 应先达到 reachable=100%。"
        )

    return c


def get_special_workplace_totals(root: Path):
    """
    Read pa_workplace_control_v2.csv if available. This contains the three
    special destination totals from Step 3B/3B.1.
    """
    candidates = [
        # Actual Step 3B.1 output (columns: planning_area_norm,
        # is_special_destination, workplace_employment).
        root / ATTRACTION_DIR_REL / "special_workplace_destinations.csv",
        root / ATTRACTION_DIR_REL / "pa_workplace_control_v21.csv",
        root / ATTRACTION_DIR_REL / "pa_workplace_control_v2.csv",
        root / ATTRACTION_DIR_REL / "pa_workplace_control.csv",
    ]

    path = next((p for p in candidates if p.exists()), None)
    if path is None:
        return None, []

    df = pd.read_csv(path, encoding="utf-8-sig", low_memory=False)

    required = {
        "planning_area_norm",
        "workplace_employment",
        "is_special_destination",
    }
    if not required.issubset(df.columns):
        return None, []

    def _as_bool(s: pd.Series) -> pd.Series:
        # Robust to True/False booleans and "True"/"False"/"true" strings.
        if s.dtype == bool:
            return s
        return (
            s.astype(str).str.strip().str.lower()
            .isin(["true", "1", "yes", "y", "t"])
        )

    special = df[_as_bool(df["is_special_destination"])].copy()
    physical = df[~_as_bool(df["is_special_destination"])].copy()

    special["workplace_employment"] = pd.to_numeric(
        special["workplace_employment"], errors="coerce"
    ).fillna(0.0)

    physical["workplace_employment"] = pd.to_numeric(
        physical["workplace_employment"], errors="coerce"
    ).fillna(0.0)

    return {
        "physical_total": float(physical["workplace_employment"].sum()),
        "special_total": float(special["workplace_employment"].sum()),
        "special_rows": special[
            ["planning_area_norm", "workplace_employment"]
        ].to_dict("records"),
    }, special


def ipf(seed: np.ndarray, row_targets: np.ndarray, col_targets: np.ndarray):
    """
    Standard bi-proportional iterative fitting.

    seed shape = (n_origin, n_destination)
    row_targets / col_targets are positive or zero.

    The implementation returns a matrix whose row / column sums agree with
    the targets to approximately IPF_TOL.
    """
    x = seed.astype(float, copy=True)

    # Ensure no row/column is completely zero when target > 0.
    if np.any((row_targets > 0) & (x.sum(axis=1) <= 0)):
        raise ValueError("存在正的 row target，但 seed 整行全为 0。")
    if np.any((col_targets > 0) & (x.sum(axis=0) <= 0)):
        raise ValueError("存在正的 column target，但 seed 整列全为 0。")

    for it in range(MAX_IPF_ITER):
        rs = x.sum(axis=1)
        for i in range(len(row_targets)):
            if row_targets[i] == 0:
                x[i, :] = 0.0
            elif rs[i] > 0:
                x[i, :] *= row_targets[i] / rs[i]

        cs = x.sum(axis=0)
        for j in range(len(col_targets)):
            if col_targets[j] == 0:
                x[:, j] = 0.0
            elif cs[j] > 0:
                x[:, j] *= col_targets[j] / cs[j]

        row_err = np.max(
            np.abs(x.sum(axis=1) - row_targets)
        )
        col_err = np.max(
            np.abs(x.sum(axis=0) - col_targets)
        )

        if max(row_err, col_err) <= IPF_TOL:
            return x, {
                "iterations": it + 1,
                "row_max_abs_error": float(row_err),
                "col_max_abs_error": float(col_err),
                "converged": True,
            }

    return x, {
        "iterations": MAX_IPF_ITER,
        "row_max_abs_error": float(
            np.max(np.abs(x.sum(axis=1) - row_targets))
        ),
        "col_max_abs_error": float(
            np.max(np.abs(x.sum(axis=0) - col_targets))
        ),
        "converged": False,
    }


def build_prior(
    production: pd.DataFrame,
    attraction: pd.DataFrame,
    impedance: pd.DataFrame,
    physical_share: float,
    lam: float,
):
    zones = production["zone_id"].sort_values().tolist()

    p = (
        production
        .set_index("zone_id")
        .reindex(zones)["production_total"]
        .to_numpy(dtype=float)
    )

    a = (
        attraction
        .set_index("zone_id")
        .reindex(zones)["workplace_attraction"]
        .to_numpy(dtype=float)
    )

    pivot = impedance.pivot(
        index="origin_zone",
        columns="destination_zone",
        values="travel_time_min",
    ).reindex(index=zones, columns=zones)

    c = pivot.to_numpy(dtype=float)

    if not np.isfinite(c).all():
        raise ValueError("阻抗矩阵存在 NaN/Inf。")

    # Physical-workplace production target.
    p_phys = p * physical_share

    # Ensure totals agree numerically.
    p_total = float(p_phys.sum())
    a_total = float(a.sum())

    if p_total <= 0 or a_total <= 0:
        raise ValueError("物理 OD 生产量或吸引量为 0。")

    # Due to source rounding, force exact common total by proportionally
    # adjusting production only. This is a bookkeeping adjustment, not an
    # estimation of spatial structure.
    p_phys *= a_total / p_total

    # Exponential impedance. c is minutes, lambda is per minute.
    seed = (
        np.outer(np.maximum(p_phys, MIN_SEED), np.maximum(a, MIN_SEED))
        * np.exp(-lam * c)
    )

    # Force exact zero attraction columns to zero.
    seed[:, a <= 0] = 0.0
    seed[p_phys <= 0, :] = 0.0

    od, info = ipf(
        seed=seed,
        row_targets=p_phys,
        col_targets=a,
    )

    return zones, p, p_phys, a, c, seed, od, info


def summarize_od(zones, p, p_phys, a, c, od, lam, info):
    n = len(zones)

    long_rows = []
    for i, oi in enumerate(zones):
        nz = np.flatnonzero(od[i, :] > 1e-9)
        for j in nz:
            long_rows.append({
                "origin_zone": oi,
                "destination_zone": zones[j],
                "trips": float(od[i, j]),
                "travel_time_min": float(c[i, j]),
            })

    long_df = pd.DataFrame(long_rows)

    row_sum = od.sum(axis=1)
    col_sum = od.sum(axis=0)

    total = float(od.sum())

    # Weighted mean travel time.
    weighted_tt = (
        float((od * c).sum() / total)
        if total > 0 else np.nan
    )

    # Mean Euclidean-like network time statistics only, no calibration here.
    positive = od > 1e-9
    mean_tt_od = (
        float((od[positive] * c[positive]).sum() / od[positive].sum())
        if positive.any()
        else np.nan
    )

    summary = {
        "lambda_per_min": lam,
        "zone_count": n,
        "od_total": total,
        "production_total_original": float(p.sum()),
        "production_physical_target": float(p_phys.sum()),
        "attraction_total": float(a.sum()),
        "production_physical_share": (
            float(p_phys.sum() / p.sum())
            if p.sum() > 0 else None
        ),
        "row_max_abs_error": float(
            np.max(np.abs(row_sum - p_phys))
        ),
        "col_max_abs_error": float(
            np.max(np.abs(col_sum - a))
        ),
        "mean_weighted_travel_time_min": weighted_tt,
        "nonzero_od_cells": int(np.count_nonzero(od > 1e-9)),
        "matrix_density": float(
            np.count_nonzero(od > 1e-9) / (n * n)
        ),
        "ipf_iterations": info["iterations"],
        "ipf_converged": bool(info["converged"]),
        "ipf_row_error": info["row_max_abs_error"],
        "ipf_col_error": info["col_max_abs_error"],
    }

    return long_df, summary


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--project-root",
        type=Path,
        default=DEFAULT_PROJECT_ROOT,
    )
    parser.add_argument(
        "--lambdas",
        type=float,
        nargs="+",
        default=DEFAULT_LAMBDAS,
        help="distance-decay lambda(s), unit 1/min",
    )
    args = parser.parse_args()

    root = args.project_root
    out_dir = root / OUT_REL
    out_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 72)
    print("Step 5 | Doubly-Constrained Gravity Prior OD")
    print("=" * 72)

    # ---- Load ----
    print("[1/5] Load production / attraction / impedance")
    production = load_production(root / PRODUCTION_REL)
    attraction_path = find_attraction_file(root)
    attraction = load_attraction(attraction_path)
    impedance = load_impedance(root / IMPEDANCE_REL)

    special_info, _ = get_special_workplace_totals(root)

    original_production_total = float(production["production_total"].sum())
    physical_attraction_total = float(
        attraction["workplace_attraction"].sum()
    )

    if special_info is not None:
        special_total = special_info["special_total"]
    else:
        special_total = original_production_total - physical_attraction_total

    physical_share = (
        physical_attraction_total / original_production_total
        if original_production_total > 0 else 0.0
    )

    # ---- Accounting check ----
    accounting = {
        "production_total": original_production_total,
        "physical_attraction_total": physical_attraction_total,
        "special_workplace_total": special_total,
        "production_minus_physical_attraction": (
            original_production_total - physical_attraction_total
        ),
        "physical_workplace_share_assumed": physical_share,
        "special_workplace_share_assumed": 1.0 - physical_share,
        "assumption": (
            "Special workplace destination mass is proportionally distributed "
            "across residence Subzones because current data do not provide "
            "Subzone-level residence distributions for those categories."
        ),
    }

    with open(
        out_dir / "prior_od_accounting.json",
        "w",
        encoding="utf-8",
    ) as f:
        json.dump(accounting, f, ensure_ascii=False, indent=2)

    # Physical production by zone.
    physical_production = production.copy()
    physical_production["physical_workplace_share"] = physical_share
    physical_production["physical_workplace_production"] = (
        physical_production["production_total"] * physical_share
    )
    physical_production.to_csv(
        out_dir / "physical_production.csv",
        index=False,
        encoding="utf-8-sig",
    )

    # Special destination mass.
    special_rows = []
    if special_info is not None and special_info["special_rows"]:
        for row in special_info["special_rows"]:
            special_rows.append({
                "special_destination": row["planning_area_norm"],
                "national_employment": row["workplace_employment"],
                "estimated_physical_origin_allocation": (
                    original_production_total > 0
                    and row["workplace_employment"]
                    * original_production_total
                    / original_production_total
                    or row["workplace_employment"]
                ),
                "note": (
                    "Residence Subzone distribution unavailable; "
                    "not included in physical 332x332 OD."
                ),
            })

    special_df = pd.DataFrame(special_rows)
    if special_df.empty:
        special_df = pd.DataFrame(
            [{
                "special_destination": "SPECIAL_TOTAL",
                "national_employment": special_total,
                "estimated_physical_origin_allocation": special_total,
                "note": (
                    "Special destinations are not physical Subzones; "
                    "mass kept outside the physical OD."
                ),
            }]
        )

    special_df.to_csv(
        out_dir / "special_destination_mass.csv",
        index=False,
        encoding="utf-8-sig",
    )

    # ---- No-road access check from Step 4 ----
    snap_path = root / "reports/od_impedance/zone_network_snap.csv"
    network_access = pd.DataFrame()
    if snap_path.exists():
        network_access = pd.read_csv(
            snap_path,
            encoding="utf-8-sig",
            low_memory=False,
        )

    diagnostic_rows = []

    # ---- Lambda sensitivity ----
    summary_rows = []

    for lam in args.lambdas:
        print(f"[2/5] Lambda={lam:.4f} / min")
        (
            zones,
            p,
            p_phys,
            a,
            c,
            seed,
            od,
            ipf_info,
        ) = build_prior(
            production,
            attraction,
            impedance,
            physical_share,
            lam,
        )

        long_df, summary = summarize_od(
            zones,
            p,
            p_phys,
            a,
            c,
            od,
            lam,
            ipf_info,
        )

        # Write long-form OD, robust for future MATSim conversion.
        lam_tag = f"{lam:.3f}".replace(".", "p")

        long_df.to_parquet(
            out_dir / f"prior_od_lambda_{lam_tag}.parquet",
            index=False,
        )
        long_df.to_csv(
            out_dir / f"prior_od_lambda_{lam_tag}.csv",
            index=False,
            encoding="utf-8-sig",
        )

        with open(
            out_dir / f"prior_od_validation_lambda_{lam_tag}.json",
            "w",
            encoding="utf-8",
        ) as f:
            json.dump(
                summary,
                f,
                ensure_ascii=False,
                indent=2,
            )

        summary_rows.append(summary)

        # OD-level diagnostics by origin / destination.
        for i, z in enumerate(zones):
            diagnostic_rows.append({
                "lambda_per_min": lam,
                "zone_id": int(z),
                "origin_prior_physical": float(p_phys[i]),
                "destination_attraction": float(a[i]),
                "origin_od_sum": float(od[i, :].sum()),
                "destination_od_sum": float(od[:, i].sum()),
                "origin_share_total": float(
                    od[i, :].sum() / od.sum()
                ) if od.sum() > 0 else 0.0,
                "destination_share_total": float(
                    od[:, i].sum() / od.sum()
                ) if od.sum() > 0 else 0.0,
            })

    pd.DataFrame(summary_rows).to_csv(
        out_dir / "prior_od_summary.csv",
        index=False,
        encoding="utf-8-sig",
    )
    pd.DataFrame(diagnostic_rows).to_csv(
        out_dir / "prior_od_diagnostics.csv",
        index=False,
        encoding="utf-8-sig",
    )

    # ---- network access mass ----
    if not network_access.empty:
        required = {"zone_id", "snap_warning"}
        if required.issubset(network_access.columns):
            network_access["zone_id"] = pd.to_numeric(
                network_access["zone_id"], errors="coerce"
            )
            problem = network_access[
                network_access["snap_warning"].astype(bool)
            ].copy()

            if len(problem):
                pp = physical_production.merge(
                    problem[["zone_id"]],
                    on="zone_id",
                    how="inner",
                )
                access_summary = {
                    "no_road_access_or_snap_warning_zones": int(len(problem)),
                    "production_total_original": float(
                        pp["production_total"].sum()
                    ),
                    "physical_production_mass": float(
                        pp["physical_workplace_production"].sum()
                    ),
                    "zone_ids": pp["zone_id"].astype(int).tolist(),
                }
            else:
                access_summary = {
                    "no_road_access_or_snap_warning_zones": 0,
                    "production_total_original": 0.0,
                    "physical_production_mass": 0.0,
                    "zone_ids": [],
                }

            with open(
                out_dir / "network_access_mass.json",
                "w",
                encoding="utf-8",
            ) as f:
                json.dump(
                    access_summary,
                    f,
                    ensure_ascii=False,
                    indent=2,
                )

    print("[5/5] Finished")
    print("-" * 72)
    print(f"Production total                     : {original_production_total:,.3f}")
    print(f"Physical attraction total            : {physical_attraction_total:,.3f}")
    print(f"Assumed physical-workplace share     : {physical_share:.6%}")
    print(f"Special workplace mass                : {special_total:,.3f}")
    print(f"Lambda sensitivity                    : {args.lambdas}")
    print(f"Output                                : {out_dir}")
    print("-" * 72)
    print(
        "IMPORTANT: This is a physical-workplace prior OD only; "
        "special workplace destinations remain outside the 332x332 matrix."
    )
    print("=" * 72)


if __name__ == "__main__":
    main()
