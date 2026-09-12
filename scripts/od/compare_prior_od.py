#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Compare the Census-constrained Prior OD matrices of Step 5B (free-flow impedance)
and Step 5C.1 (AM-peak v2 impedance), and verify zone-level conservation.

Outputs (reports/od_prior_5c1/):
    compare_5b_vs_5c1_summary.csv
    compare_5b_vs_5c1_region_pa.csv
    prior_od_5c1_conservation_check.csv
"""
from __future__ import annotations
import numpy as np
import pandas as pd
from pathlib import Path

ROOT = Path(r"D:\Luan\2026-05\2_Singapore")
LAMBDAS = [0.05, 0.075, 0.10, 0.125, 0.15]
ID_COLS = ["origin_zone", "destination_zone"]


def tag(lam: float) -> str:
    return f"{lam:.3f}".replace(".", "p")


def load_od(path: Path, ids: list[int]) -> np.ndarray:
    df = pd.read_parquet(path)
    m = (df.pivot_table(index="origin_zone", columns="destination_zone",
                        values="trips", aggfunc="sum")
           .reindex(index=ids, columns=ids).fillna(0.0))
    return m.to_numpy(float)


def load_c(path: Path, ids: list[int], intra_path: Path) -> np.ndarray:
    c = pd.read_parquet(path)
    m = (c.pivot(index="origin_zone", columns="destination_zone",
                 values="travel_time_min")
          .reindex(index=ids, columns=ids).to_numpy(float)).copy()
    intra = pd.read_csv(intra_path, encoding="utf-8-sig")
    pos = {int(z): i for i, z in enumerate(ids)}
    for _, r in intra.iterrows():
        m[pos[int(r.zone_id)], pos[int(r.zone_id)]] = float(r.intrazonal_travel_time_min)
    return m


def main() -> None:
    z = pd.read_csv(ROOT / "reports/od_zone/zone_dictionary.csv", encoding="utf-8-sig")
    z.zone_id = pd.to_numeric(z.zone_id).astype(int)
    z = z.sort_values("zone_id").reset_index(drop=True)
    ids = z.zone_id.tolist()
    reg = z.planning_region.map(lambda s: str(s).strip().upper()).to_numpy()
    pa = z.planning_area.map(lambda s: str(s).strip().upper()).to_numpy()

    cFF = load_c(ROOT / "reports/od_impedance/impedance_matrix.parquet",
                 ids, ROOT / "reports/od_prior_5b/intrazonal_impedance.csv")
    cAM = load_c(ROOT / "reports/od_impedance_ampeak_v2/ampeak_impedance_v2.parquet",
                 ids, ROOT / "reports/od_prior_5c1/intrazonal_impedance_5c1.csv")

    # production / attraction margins (re-derived exactly as the OD scripts do)
    prod = pd.read_csv(ROOT / "reports/od_production/production.csv", encoding="utf-8-sig")
    prod.zone_id = pd.to_numeric(prod.zone_id).astype(int)
    prod = prod.sort_values("zone_id")
    att = pd.read_csv(ROOT / "reports/od_prior_5c1/attraction_clean_5c1.csv", encoding="utf-8-sig")
    att.zone_id = pd.to_numeric(att.zone_id).astype(int)
    att = att.sort_values("zone_id")
    a_target = att.workplace_attraction_clean.to_numpy(float)
    p_raw = pd.to_numeric(prod.work_trip_production, errors="coerce").fillna(0).to_numpy(float)
    mass_share = a_target.sum() / float(p_raw.sum())
    p_phys = p_raw * mass_share
    p_phys = p_phys * (a_target.sum() / p_phys.sum())

    reg_pa_pairs = sorted({(reg[i], pa[i]) for i in range(len(ids))})
    pa_of_reg = {}
    for i in range(len(ids)):
        pa_of_reg.setdefault(reg[i], set()).add(pa[i])

    summary, cons, block_rows = [], [], []
    for lam in LAMBDAS:
        t = tag(lam)
        T5B = load_od(ROOT / f"reports/od_prior_5b/prior_od_5b_lambda_{t}.parquet", ids)
        T5C = load_od(ROOT / f"reports/od_prior_5c1/prior_od_5c1_lambda_{t}.parquet", ids)

        # ---- conservation check (5C.1) ----
        row_err = float(np.max(np.abs(T5C.sum(1) - p_phys)))
        col_err = float(np.max(np.abs(T5C.sum(0) - a_target)))
        cons.append({"lambda_per_min": lam, "od_total": float(T5C.sum()),
                     "production_margin_sum": p_phys.sum(),
                     "attraction_margin_sum": a_target.sum(),
                     "row_max_abs_error": row_err, "col_max_abs_error": col_err,
                     "row_exact_1e-6": row_err < 1e-6, "col_exact_1e-6": col_err < 1e-6})
        # also check 5B for the record
        cons[-1]["row_max_abs_error_5b"] = float(np.max(np.abs(T5B.sum(1) - p_phys)))
        cons[-1]["col_max_abs_error_5b"] = float(np.max(np.abs(T5B.sum(0) - a_target)))

        # ---- structure / travel-time metrics ----
        tot = T5C.sum()
        diagC = float(np.trace(T5C) / tot)
        diagB = float(np.trace(T5B) / tot)
        cross = np.array([[reg[i] != reg[j] for j in range(len(ids))] for i in range(len(ids))])
        crossC = float(T5C[cross].sum() / tot)
        crossB = float(T5B[cross].sum() / tot)

        def tt(T, c):
            return float((T * c).sum() / T.sum())

        long30C = float(T5C[cAM > 30].sum() / tot)
        long30B_onAM = float(T5B[cAM > 30].sum() / tot)
        long45C = float(T5C[cAM > 45].sum() / tot)
        long45B_onAM = float(T5B[cAM > 45].sum() / tot)
        tv = float(0.5 * np.abs(T5B - T5C).sum() / tot)

        summary.append({
            "lambda_per_min": lam,
            "mean_tt_5B_on_FF": tt(T5B, cFF), "mean_tt_5C1_on_FF": tt(T5C, cFF),
            "mean_tt_5B_on_AM": tt(T5B, cAM), "mean_tt_5C1_on_AM": tt(T5C, cAM),
            "intrazonal_share_5B": diagB, "intrazonal_share_5C1": diagC,
            "cross_region_share_5B": crossB, "cross_region_share_5C1": crossC,
            "share_gt30min_5B": long30B_onAM, "share_gt30min_5C1": long30C,
            "share_gt45min_5B": long45B_onAM, "share_gt45min_5C1": long45C,
            "total_variation_5B_vs_5C1": tv,
            "nonzero_od_cells": int(np.count_nonzero(T5C > 1e-9)),
            "cells_ge_100": int(np.count_nonzero(T5C >= 100)),
            "od_total": float(tot),
        })

        # ---- Region x PA block shares: 5B vs 5C.1 ----
        for r in sorted(set(reg)):
            ii = np.where(reg == r)[0]
            rtotC = T5C[ii, :].sum(); rtotB = T5B[ii, :].sum()
            for wp in sorted(pa_of_reg[r]):
                jj = np.where(pa == wp)[0]
                bC = T5C[np.ix_(ii, jj)].sum(); bB = T5B[np.ix_(ii, jj)].sum()
                block_rows.append({
                    "lambda_per_min": lam, "residence_region": r, "workplace_pa": wp,
                    "trips_5B": bB, "share_5B": bB / rtotB,
                    "trips_5C1": bC, "share_5C1": bC / rtotC,
                    "share_delta": bC / rtotC - bB / rtotB,
                    "share_delta_abs": abs(bC / rtotC - bB / rtotB),
                })

    out = ROOT / "reports/od_prior_5c1"
    pd.DataFrame(summary).to_csv(out / "compare_5b_vs_5c1_summary.csv", index=False, encoding="utf-8-sig")
    pd.DataFrame(cons).to_csv(out / "prior_od_5c1_conservation_check.csv", index=False, encoding="utf-8-sig")
    blk = pd.DataFrame(block_rows)
    blk.to_csv(out / "compare_5b_vs_5c1_region_pa.csv", index=False, encoding="utf-8-sig")

    print("== conservation (5C.1) ==")
    print(pd.DataFrame(cons)[["lambda_per_min", "od_total", "row_max_abs_error",
                              "col_max_abs_error", "row_exact_1e-6", "col_exact_1e-6"]].to_string(index=False))
    print("\n== comparison 5B vs 5C.1 ==")
    print(pd.DataFrame(summary).to_string(index=False))
    print("\n== Region x PA share delta (max |Δ| per lambda) ==")
    print(blk.groupby("lambda_per_min").share_delta_abs.max().to_string())
    print("\nOutput:", out)


if __name__ == "__main__":
    main()
