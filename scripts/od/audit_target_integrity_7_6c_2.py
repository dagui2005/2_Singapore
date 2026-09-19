# -*- coding: utf-8 -*-
"""
7.6C-2 -- Calibration Target Integrity Gate   (zero simulation, read-only)

Question answered
-----------------
Is the FROZEN 7.3.6A Final Calibration Crosswalk still good enough to support
ABSOLUTE identification of the demand scale?

Why this step exists
--------------------
7.6C-1 showed that 54 of the 574 calibrated sections (8.14% of the observed
volume) are matched to links that the router never uses, or to a mixed pair of
carriageway directions whose across-link MEDIAN collapses to zero.  That is a
property of the COMPARATOR, not of the demand.  Since

        Sim/Obs = f(Demand, OD, route-choice, crosswalk, observation)

and route-choice is frozen (7.6E) and OD structure is broadly accepted (7.6C),
the remaining unknown contamination sits in the CROSSWALK term.  Running the
1.10 / 1.20 / 1.25 demand runs now would mix

        demand response  +  comparator artifact

into a single curve.  This gate decides whether that mixing is tolerable.

What this script does NOT do
----------------------------
* it does NOT modify the crosswalk (7.3.6A stays byte-frozen)
* it does NOT modify the OD, lambda, network, capacity, 7.1 or 7.3.6A
* it does NOT select a demand scale and does NOT select lambda
* it does NOT run MATSim
* it does NOT promote 0.9351 into a replacement target

It only quantifies the comparator's own uncertainty and compares it with the
demand increment that a 1.10 / 1.20 / 1.25 grid would have to resolve.

Lineage
-------
Frozen quantities are recomputed by IMPORTING the frozen modules
(compare_final_crosswalk_7_3_6b / diagnose_od_spatial_structure_7_6c /
audit_anomaly_trace_7_6c_1).  Formulas are never copied, and the recomputed
values are cross-validated against the CSV products of 7.6C and 7.6C-1.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import compare_final_crosswalk_7_3_6b as bt          # noqa: E402  frozen SCALE
import diagnose_od_spatial_structure_7_6c as d76     # noqa: E402  frozen 7.6C
import audit_anomaly_trace_7_6c_1 as a761            # noqa: E402  frozen 7.6C-1

ROOT = Path(r"D:\Luan\2026-05\2_Singapore")
OUT_DIR = ROOT / "reports" / "od_target_integrity_7_6c_2"

DIR_7C = d76.OUT_DIR                       # reports/od_structure_7_6c
DIR_7C1 = a761.OUT_DIR                     # reports/od_anomaly_trace_7_6c_1

# ---------------- frozen constants (never re-typed by hand) ---------------
ANCHOR_SIM_OBS = float(d76.ANCHOR_SIM_OBS)     # 0.8590 (7.6F-0 R01 demand=1.00)
SCALE = float(bt.SCALE)                        # 2.29897
N_AGENT = int(d76.N_AGENT)
REAL_CAR_OD_TOTAL = float(d76.REAL_CAR_OD_TOTAL)

# ---------------- gate design --------------------------------------------
# the demand grid actually proposed for 7.6F-1 (user-frozen plan)
F1_GRID = [1.10, 1.20, 1.25]
# an extended grid used only to draw the response curve
GRID_EXT = [1.00, 1.05, 1.10, 1.15, 1.20, 1.25, 1.30, 1.35]

# reference elasticity of the Sim/Obs response to the demand factor.
# eps = 1 <=> Sim/Obs scales proportionally with the demand factor (no
# congestion feedback on the calibrated sections).  Justification: the 08-09
# oversaturated share is a flat 0% (linkstats), so there is no capacity
# feedback in this window.  eps is NOT calibrated here -- it is a stated
# reference assumption, and every conclusion is re-expressed as the eps value
# that would be REQUIRED for the conclusion to flip.
EPS_REF = 1.0

# the project's own formal criterion (used for the D01-D04 legacy curve):
# signal-to-noise < 1  ==>  the curve cannot be used for inference.
SNR_MIN = 1.0

# criteria tiers: F-1 step sizes in demand-factor units
STEP_COARSE = 0.10      # 1.10 -> 1.20
STEP_FINE = 0.05        # 1.20 -> 1.25

# admissible calibers (target variants that may legitimately be read as
# "the calibration target").  BEST_DIRECTION is the conservative error
# boundary -- reported, but NOT promoted to an official target.
ADMISSIBLE = ["FROZEN", "POSITIVE_ONLY", "BEST_DIRECTION"]
OUTER = ["MATCH_NEAREST_LOWER", "MATCH_SAMENAME_UPPER"]

CALIBER_ROLE = {
    "FROZEN": "\u4e3b\u53e3\u5f84\uff0c\u4e0d\u80fd\u64c5\u6539",
    "POSITIVE_ONLY": "\u654f\u611f\u6027\u53e3\u5f84",
    "BEST_DIRECTION": "\u8bef\u5dee\u8fb9\u754c\uff0c\u4e0d\u4f5c\u6b63\u5f0f\u9776\u573a",
    "MATCH_NEAREST_LOWER": "\u5916\u5305\u7edc\u4e0b\u504f\uff08\u63a2\u7a76\uff09",
    "MATCH_SAMENAME_UPPER": "\u5916\u5305\u7edc\u4e0a\u504f\uff08\u63a2\u7a76\uff09",
}

# ---------------- PRE-REGISTERED CRITERIA (frozen BEFORE the run) ---------
PREREGISTERED = {
    "note": ("7.6C-2 \u53ea\u505a\u9776\u573a\u5b8c\u6574\u6027\u5224\u5b9a\uff1b\u9608\u503c\u5728\u8dd1\u4e4b\u524d"
             "\u56fa\u5b9a\uff0c\u7981\u6b62\u4e8b\u540e\u8c03\u53c2\u3002\u4e0d\u4fee\u6539 crosswalk\uff0c"
             "\u4e0d\u4fee\u6539 OD\uff0c\u4e0d\u4fee\u6539 lambda\uff0c\u4e0d\u9009 demand scale\uff0c"
             "\u4e0d\u542f\u52a8 MATSim\u3002"),
    "defs": {
        "FROZEN": "R01 PRIMARY_cycle_10_19\uff0c\u5168\u90e8\u65ad\u9762\uff0c\u6c60\u5316\u53e3\u5f84 "
                  "Sum(sim)/Sum(obs)\u3002\u4e0e positive-only \u540c\u51fd\u6570\u5f62\u5f0f\uff0c"
                  "\u4f7f Delta_target \u53ea\u53cd\u6620\u65ad\u9762\u6392\u9664\u6548\u5e94\u3002",
        "POSITIVE_ONLY": "\u4ec5 sim_8_9_scaled > 0 \u7684\u65ad\u9762\uff0c\u6c60\u5316 Sum(sim)/Sum(obs)\u3002",
        "BEST_DIRECTION": "7.6C-1 POST-HOC \u65b9\u5411\u4fee\u6b63\uff1a\u6bcf\u65ad\u9762\u53d6 "
                          "max(median(\u6b63\u5411 f89), median(\u53cd\u5411 f89)) x SCALE\u3002",
        "Delta_target": "Q_POSITIVE_ONLY - Q_FROZEN\uff08Sim/Obs \u5355\u4f4d\uff09\u3002",
        "Delta_f_target": "1/Q_POSITIVE_ONLY - 1/Q_FROZEN\u3002\u9776\u573a\u4e0d\u786e\u5b9a\u6027"
                          "\u6362\u7b97\u5230 demand factor \u5355\u4f4d\u3002",
        "SNR": "eps x step / Delta_f_target\u3002\u4f7f\u7528\u9879\u76ee\u81ea\u5df1\u7684\u6b63\u5f0f\u5224\u636e "
               "SNR < 1 ==> \u4e0d\u53ef\u7528\u4e8e\u63a8\u65ad\u3002",
    },
    "G1_target_uncertainty_exists": "Delta_target > 0\uff08\u9776\u573a\u5b58\u5728\u53ef\u8bc6\u522b\u6c61\u67d3\uff09\u3002",
    "G2_coarse_step_resolvable": "Delta_f_target <= %.2f\uff08\u7b49\u4ef7 SNR(step=%.2f) >= 1\uff09\u3002"
                                 % (STEP_COARSE, STEP_COARSE),
    "G3_fine_step_resolvable": "Delta_f_target <= %.2f\uff08\u7b49\u4ef7 SNR(step=%.2f) >= 1\uff09\u3002"
                               % (STEP_FINE, STEP_FINE),
    "G4_caliber_agreement_on_grid": "\u5168\u90e8 admissible \u53e3\u5f84\u5728 7.6F-1 \u7684\u4e09\u4e2a\u7f51\u683c\u70b9"
                                    "\u4e0a\u5bf9\u201cSim/Obs \u662f\u5426\u8d8a\u8fc7 1.0\u201d\u7ed9\u51fa\u4e00\u81f4\u5224\u65ad\u3002",
    "G5_grid_brackets_fstar_interval": "7.6F-1 \u7f51\u683c\u5b8c\u6574\u8de8\u8d8a f* \u53ef\u8bc6\u522b\u533a\u95f4"
                                       "\uff08\u533a\u95f4\u4e24\u7aef\u90fd\u88ab\u7f51\u683c\u70b9\u8de8\u8fc7\uff09\u3002",
    "G6_structural_separability": "Planning Region \u7ed3\u6784\u8de8\u5ea6 >= 5 x Delta_target"
                                  "\uff08\u7ed3\u6784\u7ed3\u8bba\u4e0d\u88ab\u9776\u573a\u4e0d\u786e\u5b9a\u6027\u6c61\u67d3\uff09\u3002",
}

CHECKS: list = []


def chk(name, value, ok, expected="", note=""):
    if isinstance(value, (np.floating, np.integer)):
        value = float(value)
    elif isinstance(value, (np.bool_,)):
        value = bool(value)
    CHECKS.append({"check": name, "value": value, "ok": bool(ok),
                   "expected": expected, "note": note})


def get_check(name, default=True):
    for c in CHECKS:
        if c["check"] == name:
            return c["ok"]
    return default


def log(msg=""):
    print(msg, flush=True)


def banner(msg):
    log("")
    log("=" * 78)
    log(msg)
    log("=" * 78)


def _jsonable(o):
    if isinstance(o, dict):
        return {k: _jsonable(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_jsonable(v) for v in o]
    if isinstance(o, (np.bool_,)):
        return bool(o)
    if isinstance(o, (np.floating, np.integer, float)):
        v = float(o)
        return None if (v != v or v in (float("inf"), float("-inf"))) else v
    return o


def pooled(df, sim="sim_8_9_scaled", obs="obs_8_9"):
    """Pooled (obs-weighted) Sim/Obs -- identical functional form for every caliber."""
    o = float(df[obs].sum())
    return float(df[sim].sum() / o) if o > 0 else float("nan")


# ==========================================================================
# Part 1 -- rebuild the frozen comparator and every caliber variant
# ==========================================================================

def build_calibers(ctx):
    banner("Part 1 -- frozen comparator + caliber variants (zero simulation)")

    # PRIMARY section set = the full R01 PRIMARY caliber (576 sections).  This is
    # the target as defined by 7.3.6A + 7.6F-0; geography is not a property of it.
    sub = ctx["sub"].copy()
    sub["zero_sim"] = sub["sim_8_9_scaled"] <= 0
    pos = sub[~sub["zero_sim"]].copy()

    # 7.6C's section_geography.csv covers only 574 of the 576 sections, and a few
    # downstream products (notably 7.6C-1's repair-bound CSV, whose helper does an
    # internal dropna) were therefore computed on 574 while their own "anchor" lines
    # used 576.  Both sets are tracked explicitly so the split is never implicit.
    sub_geo = sub.dropna(subset=["mid_x", "mid_y"]).copy()
    pos_geo = sub_geo[~sub_geo["zero_sim"]].copy()
    n_missing_geo = int(sub["mid_x"].isna().sum())
    if n_missing_geo:
        miss = sub[sub["mid_x"].isna()]
        log(f"NOTE: {n_missing_geo} calibrated sections have no section_geography row "
            f"(7.6C covers {len(sub_geo)}/{len(sub)}):")
        log(miss[["lta_linkid", "RoadCat", "RoadName", "obs_8_9",
                  "sim_8_9_scaled"]].to_string(index=False))
        log("      -> 7.6C products use 576 sections, 7.6C-1 repair bounds use 574")

    q, q_geo = {}, {}
    q["FROZEN"] = pooled(sub)
    q["POSITIVE_ONLY"] = pooled(pos)
    q_geo["FROZEN"] = pooled(sub_geo)
    q_geo["POSITIVE_ONLY"] = pooled(pos_geo)

    # alternative frozen definition (obs-weighted mean of per-section ratios).
    # Reported only to show the gate conclusion is invariant to the choice.
    q["FROZEN_WMEAN_OF_RATIOS"] = float(d76.wmean(sub["ratio_8_9"], sub["obs_8_9"]))
    q_geo["FROZEN_WMEAN_OF_RATIOS"] = float(
        d76.wmean(sub_geo["ratio_8_9"], sub_geo["obs_8_9"]))

    chk("P1.sections_missing_geography", n_missing_geo, True,
        "informational",
        "7.6C section_geography covers 574/576; explains 0.8589732 vs 0.8585675")

    # ---- 7.3.6A lineage: what the frozen target actually covers ------------
    cw = ctx["cw"]
    cw_prim = ctx["cw_prim"]
    n_sections_all = int(cw["lta_linkid"].nunique())
    n_sections_prim = int(cw_prim["lta_linkid"].nunique())
    n_matched_links = int(cw_prim["matsim_link_id"].nunique())

    n_links_all = int(cw["matsim_link_id"].nunique()) \
        if "matsim_link_id" in cw.columns else n_matched_links
    log(f"frozen target  : {n_sections_all} LTA sections in the 7.3.6A crosswalk "
        f"({n_sections_prim} primary candidates)")
    log(f"                 {n_matched_links:,} distinct matched MATSim links "
        f"(primary candidates); {n_links_all:,} over the whole crosswalk")
    log(f"R01 sections   : {len(sub)} rows, caliber PRIMARY_cycle_10_19")
    log("")
    log(f"Q_FROZEN          = {q['FROZEN']:.7f}  "
        f"(576-section primary set; 7.6F-0 anchor {ANCHOR_SIM_OBS:.4f})")
    log(f"Q_POSITIVE_ONLY   = {q['POSITIVE_ONLY']:.7f}")
    log(f"Q_FROZEN(wmean)   = {q['FROZEN_WMEAN_OF_RATIOS']:.7f}  "
        f"(alternative definition, robustness only)")
    log(f"[574-section subset] Q_FROZEN = {q_geo['FROZEN']:.7f}, "
        f"Q_POSITIVE_ONLY = {q_geo['POSITIVE_ONLY']:.7f}  "
        f"(the set 7.6C-1's repair bounds were silently computed on)")
    log(f"zero-flow sections= {int(sub['zero_sim'].sum())} / {len(sub)} "
        f"carrying {sub.loc[sub['zero_sim'], 'obs_8_9'].sum():,.1f} obs veh/h "
        f"= {sub.loc[sub['zero_sim'], 'obs_8_9'].sum() / sub['obs_8_9'].sum():.4%}")

    # ---- 7.6C-1 repair bounds (recomputed by importing the frozen module) --
    t0 = time.time()
    bounds = a761.link_attribution_bounds(ctx, sub)
    log(f"7.6C-1 repair bounds recomputed via frozen module in {time.time()-t0:.1f}s")

    dirfix = a761.directional_repair(ctx, sub)
    s2 = sub.copy()
    s2["sim_dirfix"] = s2["lta_linkid"].map(dirfix)
    # directional_repair iterates cw_prim (574 primary candidates), so sections
    # outside that set have no repair -- keep their observed (unrepaired) sim.
    n_nodir = int(s2["sim_dirfix"].isna().sum())
    s2["sim_dirfix"] = s2["sim_dirfix"].fillna(s2["sim_8_9_scaled"])
    q["BEST_DIRECTION"] = pooled(s2, sim="sim_dirfix")
    s2g = sub_geo.copy()
    s2g["sim_dirfix"] = s2g["lta_linkid"].map(dirfix)
    s2g["sim_dirfix"] = s2g["sim_dirfix"].fillna(s2g["sim_8_9_scaled"])
    q_geo["BEST_DIRECTION"] = pooled(s2g, sim="sim_dirfix")
    log(f"best-direction repair: {len(sub)-n_nodir} sections repaired, "
        f"{n_nodir} outside cw_prim kept unrepaired")

    def gl(variant, radius):
        r = bounds[(bounds["variant"] == variant) & (bounds["group"] == "GLOBAL")]
        if radius is None:
            r = r[r["radius_m"].isna()]
        else:
            r = r[r["radius_m"] == radius]
        return float(r["sim_obs_repaired"].iloc[0])

    q["MATCH_NEAREST_LOWER"] = gl("repair: nearest flowing link", a761.TWIN_R_MAX)
    q["MATCH_SAMENAME_UPPER"] = gl("repair: same-name flowing max", a761.TWIN_R_MAX)
    q["BEST_DIRECTION_FROM_BOUNDS"] = float(
        bounds[(bounds["variant"] == "repair: best-direction median (POST-HOC)")
               & (bounds["group"] == "GLOBAL")]["sim_obs_repaired"].iloc[0])

    log("")
    log("* every caliber (Sim/Obs, 08-09, R01 PRIMARY cycle):")
    for k in ["FROZEN", "POSITIVE_ONLY", "BEST_DIRECTION",
              "MATCH_NEAREST_LOWER", "MATCH_SAMENAME_UPPER"]:
        role = CALIBER_ROLE.get(k, "")
        log(f"   {k:22s} {q[k]:.6f}   {role}")

    # the frozen 7.6C-1 bound is inherently 574-based (its helper dropna's on
    # mid_x/mid_y); assert the 574 recomputation reproduces it bit-for-bit.
    chk("P1.directional_repair_reproduces_7_6C_1",
        round(abs(q_geo["BEST_DIRECTION"] - q["BEST_DIRECTION_FROM_BOUNDS"]), 9),
        abs(q_geo["BEST_DIRECTION"] - q["BEST_DIRECTION_FROM_BOUNDS"]) < 1e-9,
        "< 1e-9", "574-section set reproduces 7.6C-1's POST-HOC repair exactly")
    log(f"   BEST_DIRECTION : 576-set {q['BEST_DIRECTION']:.6f} / "
        f"574-set {q_geo['BEST_DIRECTION']:.6f} "
        f"(7.6C-1 published {q['BEST_DIRECTION_FROM_BOUNDS']:.6f})")
    q["ROBUSTNESS_574"] = q_geo

    # ---- cross-validation against the 7.6C / 7.6C-1 CSV products -----------
    xrows = []

    def xval(label, mine, theirs, tol):
        xrows.append({"quantity": label, "recomputed_7_6c_2": mine,
                      "frozen_product": theirs, "abs_diff": abs(mine - theirs),
                      "tol": tol, "match": abs(mine - theirs) <= tol})

    j76c = json.loads((DIR_7C / "od_structure_7_6c_summary.json").read_text(encoding="utf-8"))

    def deep(o, key):
        if isinstance(o, dict):
            for kk, vv in o.items():
                if kk == key:
                    return vv
                r = deep(vv, key)
                if r is not None:
                    return r
        return None

    xval("Q_FROZEN(pooled)", q["FROZEN"], float(deep(j76c, "pooled_ratio_all_sections")), 1e-9)
    xval("Q_POSITIVE_ONLY(pooled)", q["POSITIVE_ONLY"],
         float(deep(j76c, "pooled_ratio_excl_zero_sim")), 1e-9)
    xval("Q_FROZEN(wmean_of_ratios)", q["FROZEN_WMEAN_OF_RATIOS"],
         float(deep(j76c, "global_ratio")), 1e-9)
    xval("zero_sim_sections", float(sub["zero_sim"].sum()),
         float(deep(j76c, "sections_with_zero_simulated_flow")), 0.0)
    xval("obs_share_on_zero_sim", float(sub.loc[sub["zero_sim"], "obs_8_9"].sum()
                                       / sub["obs_8_9"].sum()),
         float(deep(j76c, "obs_share_on_zero_sim_sections")), 1e-12)

    b7c1 = pd.read_csv(DIR_7C1 / "link_attribution_repair_bounds.csv")
    r0 = b7c1[(b7c1["variant"] == "matched (7.6F-0 actual)") & (b7c1["group"] == "GLOBAL")]
    xval("Q_FROZEN(574 set, = 7.6C-1 bounds)", q_geo["FROZEN"],
         float(r0["sim_obs_matched"].iloc[0]), 1e-9)
    r1 = b7c1[(b7c1["variant"] == "repair: best-direction median (POST-HOC)")
              & (b7c1["group"] == "GLOBAL")]
    xval("Q_BEST_DIRECTION(574 set, = 7.6C-1 bounds)", q_geo["BEST_DIRECTION"],
         float(r1["sim_obs_repaired"].iloc[0]), 1e-9)

    xdf = pd.DataFrame(xrows)
    xdf.to_csv(OUT_DIR / "target_integrity_crossvalidation.csv",
               index=False, encoding="utf-8-sig")
    log("")
    log("* cross-validation against the frozen 7.6C / 7.6C-1 CSV products:")
    log(xdf[["quantity", "recomputed_7_6c_2", "frozen_product", "abs_diff", "match"]]
        .to_string(index=False))
    chk("P1.crossvalidation_all_match", int(xdf["match"].sum()),
        bool(xdf["match"].all()), f"{len(xdf)}/{len(xdf)}",
        "every recomputed quantity equals the frozen product on its own section set")

    return sub, pos, s2, q, bounds, xdf


# ==========================================================================
# Part 2 -- the gate arithmetic
# ==========================================================================

def gate_arithmetic(q):
    banner("Part 2 -- gate arithmetic: target uncertainty vs demand increment")

    q_f, q_p = q["FROZEN"], q["POSITIVE_ONLY"]
    delta_target = q_p - q_f
    chk("G1.target_uncertainty_exists", round(delta_target, 7),
        delta_target > 0, "> 0",
        "Q_POSITIVE_ONLY - Q_FROZEN (Sim/Obs units)")

    log(f"Delta_target  = Q_POSITIVE_ONLY - Q_FROZEN = {delta_target:.6f} "
        f"= {100*delta_target:.3f} pp")
    log("")

    # ---- admissible band ---------------------------------------------------
    band = {k: q[k] for k in ADMISSIBLE}
    q_lo, q_hi = min(band.values()), max(band.values())
    span = q_hi - q_lo
    log("* admissible band (target variants that may be read as the target):")
    for k in ADMISSIBLE:
        log(f"   {k:16s} Q = {q[k]:.6f}   f* = {1.0/q[k]:.5f}   ({CALIBER_ROLE[k]})")
    log(f"   band span  = {span:.6f} = {100*span:.3f} pp")

    outer_lo, outer_hi = q["MATCH_NEAREST_LOWER"], q["MATCH_SAMENAME_UPPER"]
    log("")
    log(f"* outer envelope (exploratory, NOT admissible as a target): "
        f"{outer_lo:.6f} .. {outer_hi:.6f}  "
        f"[{100*(outer_hi-outer_lo):.3f} pp wide]")

    # ---- target uncertainty translated into demand-factor units -----------
    # f* = Q^(-1/eps)  (eps = reference elasticity).  At eps = 1, f* = 1/Q.
    fstar = {k: q[k] ** (-1.0 / EPS_REF) for k in ADMISSIBLE}
    f_lo, f_hi = min(fstar.values()), max(fstar.values())
    df_target = f_hi - f_lo
    log("")
    log(f"* demand factor that exactly closes the gap, f* = Q^(-1/eps), eps = {EPS_REF:g}:")
    for k in ADMISSIBLE:
        log(f"   {k:16s} f* = {fstar[k]:.5f}")
    log(f"   ==> f* identification interval = [{f_lo:.5f}, {f_hi:.5f}], "
        f"width Delta_f_target = {df_target:.5f}")

    # ---- SNR of the 7.6F-1 steps (the project's own formal criterion) -----
    def snr(step, eps=EPS_REF):
        return eps * step / df_target

    def eps_breakeven(step):
        return df_target / step

    log("")
    log("* signal-to-noise of the 7.6F-1 demand steps (SNR < 1 ==> not usable):")
    rows = []
    for label, step in [("coarse 1.10->1.20", STEP_COARSE),
                        ("fine   1.20->1.25", STEP_FINE)]:
        s_ = snr(step)
        log(f"   {label} : step = {step:.2f}, Delta_f_target = {df_target:.5f}, "
            f"SNR = {s_:.3f}  {'OK' if s_ >= SNR_MIN else '< 1 UNINFORMATIVE'}"
            f"   (needs eps >= {eps_breakeven(step):.3f})")
        rows.append({"step_label": label, "step_f": step,
                     "delta_f_target": df_target, "snr": s_,
                     "snr_ok": s_ >= SNR_MIN,
                     "eps_required_for_snr_1": eps_breakeven(step)})

    chk("G2.coarse_step_resolvable", round(snr(STEP_COARSE), 4),
        snr(STEP_COARSE) >= SNR_MIN, f">= {SNR_MIN}",
        f"step {STEP_COARSE:.2f} vs Delta_f_target {df_target:.5f}")
    chk("G3.fine_step_resolvable", round(snr(STEP_FINE), 4),
        snr(STEP_FINE) >= SNR_MIN, f">= {SNR_MIN}",
        f"step {STEP_FINE:.2f} vs Delta_f_target {df_target:.5f}")

    snr_df = pd.DataFrame(rows)
    snr_df.to_csv(OUT_DIR / "target_step_snr.csv", index=False, encoding="utf-8-sig")

    # ---- robustness: the same gate on the 574-section subset --------------
    alt = q.get("ROBUSTNESS_574")
    rob = {}
    if alt:
        d_alt = alt["POSITIVE_ONLY"] - alt["FROZEN"]
        fa = {k: alt[k] ** (-1.0 / EPS_REF) for k in ADMISSIBLE}
        w_alt = max(fa.values()) - min(fa.values())
        rob = {"delta_target_574": d_alt, "delta_f_target_574": w_alt,
               "snr_coarse_574": EPS_REF * STEP_COARSE / w_alt,
               "snr_fine_574": EPS_REF * STEP_FINE / w_alt,
               "fstar_interval_574": [min(fa.values()), max(fa.values())]}
        log("")
        log(f"* robustness on the 574-section subset (7.6C-1's implicit set): "
            f"Delta_target = {100*d_alt:.3f} pp, Delta_f_target = {w_alt:.5f}, "
            f"SNR(coarse) = {rob['snr_coarse_574']:.3f}, "
            f"SNR(fine) = {rob['snr_fine_574']:.3f}")
        same = (abs(d_alt - delta_target) < 1e-4) and \
               ((rob["snr_coarse_574"] >= SNR_MIN) == (snr(STEP_COARSE) >= SNR_MIN)) and \
               ((rob["snr_fine_574"] >= SNR_MIN) == (snr(STEP_FINE) >= SNR_MIN))
        chk("P2.verdict_invariant_to_section_set", bool(same), bool(same), "True",
            "576 vs 574 sections does not change any gate conclusion")

    return dict(delta_target=delta_target, band=band, span=span,
                outer_lo=outer_lo, outer_hi=outer_hi, fstar=fstar,
                f_lo=f_lo, f_hi=f_hi, df_target=df_target,
                snr_coarse=snr(STEP_COARSE), snr_fine=snr(STEP_FINE),
                eps_coarse=eps_breakeven(STEP_COARSE),
                eps_fine=eps_breakeven(STEP_FINE), robustness_574=rob)


# ==========================================================================
# Part 3 -- demand-response grid and caliber agreement
# ==========================================================================

def response_grid(q, ga):
    banner("Part 3 -- demand-response grid and caliber agreement")

    cal = {k: q[k] for k in ADMISSIBLE}
    rows = []
    for f in GRID_EXT:
        r = {"f": f}
        for k, Q in cal.items():
            r[k] = Q * (f ** EPS_REF)
        vals = [r[k] for k in ADMISSIBLE]
        r["all_crossed"] = all(v > 1.0 for v in vals)
        r["none_crossed"] = all(v < 1.0 for v in vals)
        r["calibers_agree"] = bool(r["all_crossed"] or r["none_crossed"])
        r["in_f1_grid"] = f in F1_GRID
        rows.append(r)
    grid = pd.DataFrame(rows)
    grid.to_csv(OUT_DIR / "target_response_grid.csv", index=False, encoding="utf-8-sig")

    log(f"Sim/Obs(f, caliber) = Q_caliber x f^{EPS_REF:g}   "
        f"(reference proportional response; eps=1)")
    log("")
    cols = ["f"] + ADMISSIBLE + ["calibers_agree", "in_f1_grid"]
    log(grid[cols].to_string(index=False, float_format=lambda v: f"{v:.4f}"))

    f1 = grid[grid["in_f1_grid"]]
    n_agree = int(f1["calibers_agree"].sum())
    chk("G4.caliber_agreement_on_grid", n_agree, n_agree == len(f1),
        f"{len(f1)}/{len(f1)} grid points agree",
        "admissible calibers must agree on whether Sim/Obs has crossed 1.0")

    # ---- grid placement vs the f* identification interval ------------------
    log("")
    log(f"* f* identification interval = [{ga['f_lo']:.5f}, {ga['f_hi']:.5f}]")
    g_lo, g_hi = min(F1_GRID), max(F1_GRID)
    brackets = (g_lo <= ga["f_lo"]) and (g_hi >= ga["f_hi"])
    inside = [f for f in F1_GRID if ga["f_lo"] <= f <= ga["f_hi"]]
    log(f"* proposed 7.6F-1 grid        = {F1_GRID}  "
        f"(range {g_lo:.2f} .. {g_hi:.2f})")
    log(f"   bracket the interval ?     = {brackets}")
    log(f"   grid points INSIDE the interval (verdict is caliber-dependent): {inside}")

    plac = []
    for f in F1_GRID:
        r = grid[grid["f"] == f].iloc[0]
        plac.append({"f": f,
                     "in_fstar_interval": bool(ga["f_lo"] <= f <= ga["f_hi"]),
                     "calibers_agree": bool(r["calibers_agree"]),
                     "crossed_count": int(sum(1 for k in ADMISSIBLE
                                              if r[k] > 1.0)),
                     "n_admissible": len(ADMISSIBLE),
                     "interpretation":
                         "\u53e3\u5f84\u5206\u6b67\uff08\u7ed3\u8bba\u4e0d\u786e\u5b9a\uff09"
                         if not bool(r["calibers_agree"]) else
                         ("\u5168\u90e8\u8d8a\u8fc7 1.0" if bool(r["all_crossed"])
                          else "\u5168\u90e8\u672a\u8d8a\u8fc7 1.0")})
    pldf = pd.DataFrame(plac)
    pldf.to_csv(OUT_DIR / "target_grid_placement.csv", index=False, encoding="utf-8-sig")
    log("")
    log(pldf.to_string(index=False))

    chk("G5.grid_brackets_fstar_interval", brackets, brackets,
        f"grid covers [{ga['f_lo']:.4f}, {ga['f_hi']:.4f}]",
        f"grid range {g_lo:.2f}..{g_hi:.2f}")

    # ---- how many DISTINCT information points does the grid buy? -----------
    n_distinct = len(set(["in" if f in inside else
                          ("above" if f > ga["f_hi"] else "below") for f in F1_GRID]))
    log("")
    log(f"* the proposed 3-run grid resolves only {n_distinct} distinct regime(s) "
        f"({inside} inside the ambiguity window; "
        f"{[f for f in F1_GRID if f > ga['f_hi']]} above it)")

    return grid, pldf, dict(brackets=bool(brackets), inside=[float(x) for x in inside],
                            n_distinct_regimes=int(n_distinct))


# ==========================================================================
# Part 4 -- where does the target uncertainty live, and is the STRUCTURE safe?
# ==========================================================================

def localise_and_separate(sub, s2, ga):
    banner("Part 4 -- localisation of Delta_target and structural separability")

    rows = []
    for key, tag in [("region", "region"), ("radial", "radial"), ("RoadCat", "RoadCat")]:
        for k, x in sub.dropna(subset=[key]).groupby(key):
            xp = x[x["sim_8_9_scaled"] > 0]
            if len(x) == 0:
                continue
            qf = pooled(x)
            qp = pooled(xp)
            rows.append({"group_by": tag, "group": k, "n_sections": int(len(x)),
                         "n_zero_sim": int((x["sim_8_9_scaled"] <= 0).sum()),
                         "obs_total": float(x["obs_8_9"].sum()),
                         "obs_share_zero":
                             float(x.loc[x["sim_8_9_scaled"] <= 0, "obs_8_9"].sum()
                                   / max(x["obs_8_9"].sum(), 1e-9)),
                         "Q_FROZEN": qf, "Q_POSITIVE_ONLY": qp,
                         "delta_target_local": qp - qf,
                         "rel_dev_vs_global_FROZEN": qf / ga["band"]["FROZEN"] - 1.0,
                         "rel_dev_vs_global_POS": qp / ga["band"]["POSITIVE_ONLY"] - 1.0})
    loc = pd.DataFrame(rows)
    loc.to_csv(OUT_DIR / "target_uncertainty_localisation.csv",
               index=False, encoding="utf-8-sig")

    log("* where Delta_target lives (pooled Sim/Obs by group):")
    for tag in ["region", "radial"]:
        x = loc[loc["group_by"] == tag].sort_values("delta_target_local", ascending=False)
        log("")
        log(f"  -- by {tag} --")
        log(x[["group", "n_sections", "n_zero_sim", "obs_share_zero",
               "Q_FROZEN", "Q_POSITIVE_ONLY", "delta_target_local",
               "rel_dev_vs_global_FROZEN", "rel_dev_vs_global_POS"]]
            .to_string(index=False, float_format=lambda v: f"{v:.4f}"))

    # ---- structural separability ------------------------------------------
    reg = loc[loc["group_by"] == "region"]
    struct_span = float(reg["Q_POSITIVE_ONLY"].max() - reg["Q_POSITIVE_ONLY"].min())
    ratio = struct_span / ga["delta_target"]
    log("")
    log(f"* structural separability:")
    log(f"   Planning Region span (Q_POSITIVE_ONLY, most robust caliber) = "
        f"{struct_span:.4f}")
    log(f"   Delta_target                                               = "
        f"{ga['delta_target']:.4f}")
    log(f"   ratio                                                      = {ratio:.2f} x")
    chk("G6.structural_separability", round(ratio, 3), ratio >= 5.0, ">= 5.0",
        "the regional structure is far larger than the comparator uncertainty "
        "==> 7.6C/7.6C-1 structural conclusions are NOT polluted")

    # does the comparator uncertainty alone explain EAST's deficit?
    east = reg[reg["group"] == "EAST REGION"]
    if len(east):
        dev = float(east["rel_dev_vs_global_FROZEN"].iloc[0])
        log("")
        log(f"   EAST rel-deficit vs global (frozen) = {dev:+.4f}; "
            f"Delta_target alone = {ga['delta_target']:.4f} "
            f"({abs(dev)/ga['delta_target']:.2f} x the target uncertainty)")

    return loc, dict(struct_span=struct_span, ratio=float(ratio))


# ==========================================================================
# Part 4b -- grid placement recommendation
# ==========================================================================

GRID_CANDIDATES = [[1.00, 1.10, 1.20],
                   [1.05, 1.15, 1.25],
                   [1.10, 1.20, 1.30],
                   [1.00, 1.05, 1.10, 1.15, 1.20, 1.25]]


def recommend_grid(ga, pr):
    banner("Part 4b -- 7.6F-1 grid placement recommendation")
    rows = []
    for g in GRID_CANDIDATES:
        steps = [round(b - a, 10) for a, b in zip(g, g[1:])]
        step = min(steps) if steps else float("nan")
        brackets = (min(g) <= ga["f_lo"]) and (max(g) >= ga["f_hi"])
        rows.append({"grid": " / ".join(f"{x:.2f}" for x in g), "n_runs": len(g),
                     "min_step": step,
                     "step_ge_delta_f_target": bool(step >= ga["df_target"]),
                     "brackets_fstar_interval": bool(brackets),
                     "acceptable": bool(brackets and step >= ga["df_target"])})
    df = pd.DataFrame(rows)
    df.to_csv(OUT_DIR / "target_grid_recommendation.csv",
              index=False, encoding="utf-8-sig")
    log(f"criterion: min step >= Delta_f_target = {ga['df_target']:.5f} "
        f"AND the grid must bracket [{ga['f_lo']:.5f}, {ga['f_hi']:.5f}]")
    log("")
    log(df.to_string(index=False))
    ok = df[df["acceptable"]]
    rec = ok.iloc[0]["grid"] if len(ok) else "(none in the candidate list)"
    log("")
    log(f"* recommended 7.6F-1 grid: {rec}")
    return df, rec


# ==========================================================================
# Part 5 -- verdict
# ==========================================================================

def verdict(ga, pr, sep):
    banner("Part 5 -- verdict")

    g1 = get_check("G1.target_uncertainty_exists")
    g2 = get_check("G2.coarse_step_resolvable")
    g3 = get_check("G3.fine_step_resolvable")
    g4 = get_check("G4.caliber_agreement_on_grid")
    g5 = get_check("G5.grid_brackets_fstar_interval")
    g6 = get_check("G6.structural_separability")

    if not g2:
        v = "TARGET_INADEQUATE"
        nxt = ("\u9776\u573a\u4e0d\u786e\u5b9a\u6027\u5df2\u5403\u6389\u6700\u7c97\u6863\u7684 demand "
               "\u589e\u91cf \u21d2 \u4e0d\u5f97\u8fdb\u5165 7.6F-1\uff1b\u5e94\u5148\u7acb\u65b0\u7248 "
               "crosswalk \u4fee\u590d\u5b9e\u9a8c\uff087.3.6A-b\uff09\u3002")
    elif g3 and g4:
        v = "TARGET_ADEQUATE_FOR_ABSOLUTE_SCALE"
        nxt = ("\u9776\u573a\u4e0d\u786e\u5b9a\u6027\u53ef\u63a5\u53d7 \u21d2 7.6F-1 \u53ef\u6309 "
               "1.10 / 1.20 / 1.25 \u6267\u884c\uff0c\u53ef\u58f0\u79f0\u7edd\u5bf9 demand scale \u8bc6\u522b\u3002")
    else:
        v = "TARGET_MARGINAL_COARSE_ONLY"
        nxt = ("\u9776\u573a\u4e0d\u786e\u5b9a\u6027\u4e0e\u7c97\u6863 demand \u589e\u91cf\u540c\u91cf\u7ea7 "
               "\u21d2 7.6F-1 \u53ea\u80fd\u8bfb\u201c\u5e26\u9776\u573a\u4e0d\u786e\u5b9a\u6027\u7684\u7c97\u6863"
               "\u54cd\u5e94\u5173\u7cfb\u201d\uff0c\u4e0d\u80fd\u58f0\u79f0\u7edd\u5bf9 scale \u5df2\u8bc6\u522b\uff1b"
               "\u7f51\u683c\u9700\u91cd\u6392\u4ee5\u4f7f\u95f4\u8ddd >= Delta_f_target\u3002")

    log(f"G1 target uncertainty exists              : {g1}")
    log(f"G2 coarse step (0.10) resolvable          : {g2}  "
        f"SNR={ga['snr_coarse']:.3f}")
    log(f"G3 fine   step (0.05) resolvable          : {g3}  "
        f"SNR={ga['snr_fine']:.3f}")
    log(f"G4 admissible calibers agree on the grid  : {g4}")
    log(f"G5 grid brackets the f* interval          : {g5}")
    log(f"G6 structural separability (>= 5x)        : {g6}  "
        f"({sep['ratio']:.2f} x)")
    log("")
    log(f"VERDICT = {v}")
    log(nxt)

    return v, nxt


# ==========================================================================
# Part 6 -- report
# ==========================================================================

def write_report(ctx, q, ga, grid, pldf, loc, sep, pr, v, nxt, runtime,
                 gdf=None, rec=None):
    sub = ctx["sub"]
    zs = sub["sim_8_9_scaled"] <= 0
    n_zero = int(zs.sum())
    obs_zero = float(sub.loc[zs, "obs_8_9"].sum())
    obs_tot = float(sub["obs_8_9"].sum())

    L = []
    A = L.append
    A("# Step 7.6C-2 \u2014 Calibration Target Integrity Gate")
    A("")
    A(f"**Verdict: `{v}`**  \u2014 \u96f6\u4eff\u771f\u3001\u53ea\u8bfb\uff1b"
      f"\u672a\u4fee\u6539 crosswalk / OD / lambda\uff1b\u672a\u542f\u52a8 MATSim\u3002")
    A("")
    A("## 0. \u5b83\u56de\u7b54\u4ec0\u4e48\u95ee\u9898")
    A("")
    A("> \u5f53\u524d **7.3.6A frozen crosswalk**\uff0c\u662f\u5426\u4ecd\u7136\u8db3\u4ee5\u652f\u6301 "
      "demand scale \u7684**\u7edd\u5bf9\u8bc6\u522b**\uff1f")
    A("")
    A("7.6C-1 \u5df2\u8bc1\u660e\uff1a54 \u4e2a\u65ad\u9762\uff08\u5360\u89c2\u6d4b\u91cf "
      f"**{100*obs_zero/obs_tot:.3f}%**\uff09\u5339\u914d\u5230\u4e86 router \u4ece\u4e0d\u4f7f\u7528\u7684"
      "\u5b64\u513f\u8fb9 / \u53cc\u5411\u6df7\u914d\u8fb9\uff08\u4e2d\u4f4d\u5854 0\uff09\u3002"
      "\u8fd9\u662f **comparator** \u7684\u6027\u8d28\uff0c\u4e0d\u662f demand \u7684\u6027\u8d28\u3002"
      "\u56e0\u6b64\u5728\u6b64\u6b65\u4e4b\u524d\u8dd1 1.10/1.20/1.25\uff0c"
      "\u4f1a\u628a `demand response + comparator artifact` \u6df7\u5728\u540c\u4e00\u6761\u66f2\u7ebf\u91cc\u3002")
    A("")
    A("**\u672c\u6b65\u4e0d\u505a**\uff1a\u4e0d\u4fee\u6539\u51bb\u7ed3\u4ef6\uff1b\u4e0d\u628a `0.9351` "
      "\u5347\u683c\u4e3a\u65b0\u9776\u573a\uff1b\u4e0d\u9009 demand scale\uff1b\u4e0d\u9009 lambda\uff1b"
      "\u4e0d\u8dd1 MATSim\u3002")
    A("")
    A("## 1. \u4e09\u53e3\u5f84\u5b9a\u4e49\uff08\u6309\u7528\u6237\u89c4\u5b9a\uff09")
    A("")
    A("| \u53e3\u5f84 | \u542b\u4e49 | \u7528\u9014 |")
    A("|---|---|---|")
    A("| `FROZEN` | \u5168\u90e8\u65ad\u9762\u6c60\u5316 `Sum(sim)/Sum(obs)` | **\u4e3b\u53e3\u5f84\uff0c"
      "\u4e0d\u80fd\u64c5\u6539** |")
    A("| `POSITIVE_ONLY` | \u4ec5 `sim>0` \u65ad\u9762\u6c60\u5316 | **\u654f\u611f\u6027\u53e3\u5f84** |")
    A("| `BEST_DIRECTION` | `max(median(\u6b63\u5411),median(\u53cd\u5411)) x SCALE` | "
      "**\u8bef\u5dee\u8fb9\u754c\uff0c\u4e0d\u4f5c\u6b63\u5f0f\u9776\u573a** |")
    A("")
    A("\u4e3a\u4fdd\u8bc1 `Delta_target` \u53ea\u53cd\u6620**\u65ad\u9762\u6392\u9664\u6548\u5e94**\u800c"
      "\u975e\u5b9a\u4e49\u53d8\u5316\uff0c`FROZEN` \u4e0e `POSITIVE_ONLY` \u91c7\u7528**\u540c\u4e00\u51fd"
      "\u6570\u5f62\u5f0f**\uff08\u6c60\u5316\u6bd4\uff09\u3002\u82e5\u6539\u7528 `FROZEN` \u7684\u53e6\u4e00"
      "\u79cd\u5b9a\u4e49\uff08\u9010\u65ad\u9762\u6bd4\u7684 obs \u52a0\u6743\u5747\u503c\uff09\uff0c"
      f"\u7ed3\u8bba\u4e0d\u53d8\uff08\u89c1 \u00a72\uff09\u3002")
    A("")
    A("## 2. \u53e3\u5f84\u503c\u4e0e\u4ea4\u53c9\u6821\u9a8c")
    A("")
    A("| \u53e3\u5f84 | Sim/Obs | \u89d2\u8272 |")
    A("|---|---|---|")
    for k in ["FROZEN", "POSITIVE_ONLY", "BEST_DIRECTION",
              "MATCH_NEAREST_LOWER", "MATCH_SAMENAME_UPPER"]:
        A(f"| `{k}` | **{q[k]:.6f}** | {CALIBER_ROLE[k]} |")
    A("")
    A(f"- `FROZEN`\uff08\u6539\u7528\u9010\u65ad\u9762\u52a0\u6743\u5747\u503c\u5b9a\u4e49\uff09= "
      f"`{q['FROZEN_WMEAN_OF_RATIOS']:.7f}`\uff1b\u4e0e\u6c60\u5316\u53e3\u5f84\u5dee "
      f"{abs(q['FROZEN_WMEAN_OF_RATIOS']-q['FROZEN']):.6f} \u21d2 \u7ed3\u8bba\u4e0d\u654f\u611f\u3002")
    A(f"- 7.6F-0 \u5b98\u65b9\u951a `ANCHOR_SIM_OBS = {ANCHOR_SIM_OBS:.4f}`\uff08\u56db\u820d\u4e94\u5165\uff09\u3002")
    A(f"- \u96f6\u6d41\u65ad\u9762 **{n_zero}/{len(sub)}**\uff0c\u627f\u8f7d "
      f"**{obs_zero:,.1f}** obs veh/h = **{100*obs_zero/obs_tot:.3f}%**\u3002")
    n_miss = int(sub["mid_x"].isna().sum()) if "mid_x" in sub.columns else 0
    A(f"- **\u65ad\u9762\u96c6\u53e3\u5f84\u6f84\u6e05**\uff1a7.6C \u7684 `section_geography.csv` \u53ea\u8986\u76d6 "
      f"**{len(sub)-n_miss}/{len(sub)}** \u4e2a\u65ad\u9762\uff08\u7f3a "
      f"190339 YIO CHU KANG ROAD \u4e0e 195768 PAN ISLAND EXPRESSWAY\uff0c\u4e24\u8005 "
      f"obs/sim \u5747 > 0\uff09\u3002\u672c\u6b65 **\u4e3b\u53e3\u5f84\u7edf\u4e00\u53d6 576 \u5168\u96c6**\uff1b"
      f"7.6C-1 \u7684 repair-bounds CSV \u56e0\u5176\u5185\u90e8 `dropna` \u5b9e\u9645\u6309 **574** \u8ba1\u7b97"
      f"\uff0c\u4e24\u8005\u76f8\u5dee 4.06e-4\uff08\u5df2\u5728\u4ea4\u53c9\u6821\u9a8c\u4e2d\u5206\u5f00\u590d\u73b0\uff09\u3002")
    if ga.get("robustness_574"):
        r = ga["robustness_574"]
        A(f"- **\u65ad\u9762\u96c6\u7a33\u5065\u6027**\uff1a\u6539\u7528 574 \u5b50\u96c6\uff0c"
          f"`Delta_target` = **{100*r['delta_target_574']:.3f} pp**\uff08\u4e3b\u53e3\u5f84 "
          f"{100*ga['delta_target']:.3f} pp\uff09\uff0c"
          f"SNR \u7c97/{r['snr_coarse_574']:.3f}\u3001\u7ec6/{r['snr_fine_574']:.3f} "
          f"\u21d2 **\u7ed3\u8bba\u4e0d\u53d8**\u3002")
    A("")
    A("\u6240\u6709\u91cd\u7b97\u91cf\u5747\u4e0e **7.6C / 7.6C-1 \u5df2\u843d\u76d8 CSV**"
      "\u9010\u4f4d\u5bf9\u9f50\uff08\u89c1 `target_integrity_crossvalidation.csv`\uff09\u3002")
    A("")
    A("## 3. \u6838\u5fc3\u91cf\uff1a\u9776\u573a\u4e0d\u786e\u5b9a\u6027 vs demand \u589e\u91cf")
    A("")
    A("### 3.1 Sim/Obs \u5355\u4f4d")
    A("")
    A(f"    Delta_target = Q_POSITIVE_ONLY - Q_FROZEN = {ga['delta_target']:.6f} "
      f"= {100*ga['delta_target']:.3f} pp")
    A("")
    A(f"\u53ef\u63a5\u53d7\u53e3\u5f84\u5e26\u5bbd\uff08FROZEN / POSITIVE_ONLY / BEST_DIRECTION\uff09= "
      f"**{100*ga['span']:.3f} pp**\uff1b\u5916\u5305\u7edc "
      f"`{ga['outer_lo']:.4f} .. {ga['outer_hi']:.4f}`"
      f"\uff08{100*(ga['outer_hi']-ga['outer_lo']):.3f} pp\uff0c\u63a2\u7a76\u6027\uff09\u3002")
    A("")
    A("### 3.2 demand factor \u5355\u4f4d\uff08\u53e3\u5f84\u95f4\u7684\u8bc6\u522b\u533a\u95f4\uff09")
    A("")
    A(f"\u5728 f* = Q^(-1/\u03b5)\uff08\u53c2\u8003\u5f39\u6027 \u03b5 = {EPS_REF:g}\uff09\u4e0b\uff1a")
    A("")
    A("| \u53e3\u5f84 | Q | f* |")
    A("|---|---|---|")
    for k in ADMISSIBLE:
        A(f"| `{k}` | {q[k]:.6f} | {ga['fstar'][k]:.5f} |")
    A("")
    A(f"    f* identification interval = [{ga['f_lo']:.5f}, {ga['f_hi']:.5f}]")
    A(f"    Delta_f_target              = {ga['df_target']:.5f}")
    A("")
    A("### 3.3 \u4fe1\u566a\u6bd4\uff08\u9879\u76ee\u81ea\u5df1\u7684\u6b63\u5f0f\u5224\u636e\uff1aSNR < 1 "
      "\u21d2 \u4e0d\u53ef\u7528\u4e8e\u63a8\u65ad\uff09")
    A("")
    A("| 7.6F-1 \u9636\u8dc3 | \u9636\u8dc3\u5927\u5c0f \u0394f | Delta_f_target | SNR = \u0394f / "
      "Delta_f_target | \u5224\u5b9a | \u9700\u8981\u7684 \u03b5 |")
    A("|---|---|---|---|---|---|")
    A(f"| \u7c97\u6863 1.10\u21921.20 | {STEP_COARSE:.2f} | {ga['df_target']:.5f} | "
      f"**{ga['snr_coarse']:.3f}** | {'\u53ef\u7528\uff08\u52c9\u5f3a\uff09' if ga['snr_coarse']>=1 else '\u4e0d\u53ef\u7528'} | "
      f"\u2265 {ga['eps_coarse']:.3f} |")
    A(f"| \u7ec6\u6863 1.20\u21921.25 | {STEP_FINE:.2f} | {ga['df_target']:.5f} | "
      f"**{ga['snr_fine']:.3f}** | {'\u53ef\u7528' if ga['snr_fine']>=1 else '**\u4e0d\u53ef\u7528**'} | "
      f"\u2265 {ga['eps_fine']:.3f} |")
    A("")
    A(f"\u5373 **\u9776\u573a\u4e0d\u786e\u5b9a\u6027\u4e0e\u7c97\u6863 demand \u589e\u91cf\u540c\u91cf\u7ea7**"
      f"\uff08{ga['df_target']:.3f} vs {STEP_COARSE:.2f}\uff09\uff0c"
      f"\u662f\u7ec6\u6863\u589e\u91cf\u7684 **{STEP_FINE/ga['df_target']:.2f} \u500d\u5012\u6570**"
      f"\uff081/\u03b5 = {1/ga['df_target']:.2f}\uff09\u3002")
    A("")
    A("## 4. demand-\u54cd\u5e94\u7f51\u683c\u4e0e\u53e3\u5f84\u4e00\u81f4\u6027")
    A("")
    A(f"`Sim/Obs(f, caliber) = Q_caliber x f^eps`\uff0c\u53c2\u8003\u5f39\u6027 eps = {EPS_REF:g}\uff1a")
    A("")
    A("| f | FROZEN | POSITIVE_ONLY | BEST_DIRECTION | \u53e3\u5f84\u4e00\u81f4 | \u5728 F-1 \u7f51\u683c |")
    A("|---|---|---|---|---|---|")
    for _, r in grid.iterrows():
        star = " \u2190" if r["in_f1_grid"] else ""
        A(f"| {r['f']:.2f}{star} | {r['FROZEN']:.4f} | {r['POSITIVE_ONLY']:.4f} | "
          f"{r['BEST_DIRECTION']:.4f} | {'\u662f' if r['calibers_agree'] else '**\u5426**'} | "
          f"{'\u662f' if r['in_f1_grid'] else ''} |")
    A("")
    A("### 4.1 \u7f51\u683c\u4f4d\u7f6e\u8bca\u65ad")
    A("")
    A(f"- f* \u53ef\u8bc6\u522b\u533a\u95f4 = **[{ga['f_lo']:.5f}, {ga['f_hi']:.5f}]**")
    A(f"- \u63d0\u8bae\u7f51\u683c `{F1_GRID}` \u662f\u5426\u8de8\u8d8a\u8be5\u533a\u95f4\uff1a"
      f"**{'是' if pr['brackets'] else '否'}**")
    A(f"- \u843d\u5728\u533a\u95f4**\u5185\u90e8**\uff08\u7ed3\u8bba\u968f\u53e3\u5f84\u800c\u53d8\uff09\u7684\u7f51"
      f"\u683c\u70b9\uff1a**{pr['inside']}**")
    A(f"- 3 \u6b21\u8dd1\u5b9e\u9645\u53ea\u80fd\u8bfb\u51fa **{pr['n_distinct_regimes']}** \u4e2a\u4e0d\u540c"
      f"\u533a\u5236\u3002")
    A("")
    A("| f | \u5728 f* \u533a\u95f4\u5185 | \u53e3\u5f84\u4e00\u81f4 | \u8d8a\u8fc7 1.0 \u7684\u53e3\u5f84\u6570 | \u89e3\u91ca |")
    A("|---|---|---|---|---|")
    for _, r in pldf.iterrows():
        A(f"| {r['f']:.2f} | {'是' if r['in_fstar_interval'] else '否'} | "
          f"{'是' if r['calibers_agree'] else '**否**'} | "
          f"{r['crossed_count']}/{r['n_admissible']} | {r['interpretation']} |")
    A("")
    if gdf is not None and rec is not None:
        A("### 4.2 \u7f51\u683c\u91cd\u6392\u5efa\u8bae")
        A("")
        A(f"\u5224\u636e\uff1a\u6700\u5c0f\u95f4\u8ddd \u2265 `Delta_f_target` = {ga['df_target']:.5f}"
          f"\uff0c\u4e14\u7f51\u683c\u5fc5\u987b\u8de8\u8d8a "
          f"[{ga['f_lo']:.5f}, {ga['f_hi']:.5f}]\u3002")
        A("")
        A("| \u5019\u9009\u7f51\u683c | \u8dd1\u6570 | \u6700\u5c0f\u95f4\u8ddd | \u95f4\u8ddd \u2265 "
          "Delta_f_target | \u8de8\u8d8a f* \u533a\u95f4 | \u53ef\u63a5\u53d7 |")
        A("|---|---|---|---|---|---|")
        for _, r in gdf.iterrows():
            A(f"| {r['grid']} | {int(r['n_runs'])} | {r['min_step']:.2f} | "
              f"{'是' if r['step_ge_delta_f_target'] else '否'} | "
              f"{'是' if r['brackets_fstar_interval'] else '否'} | "
              f"{'**是**' if r['acceptable'] else '否'} |")
        A("")
        A(f"**\u5efa\u8bae\uff1a`{rec}`**\uff08\u4fdd\u7559 3 \u6b21\u8dd1\uff0c\u4e14\u6bcf\u4e2a\u9636\u8dc3\u90fd\u4e0d\u5c0f\u4e8e"
          f"\u9776\u573a\u4e0d\u786e\u5b9a\u6027\uff09\u3002")
        A("")
    A("## 5. Delta_target \u7684\u7a7a\u95f4\u5206\u5e03")
    A("")
    A("\u6c60\u5316 Sim/Obs\uff08\u6309 Planning Region\uff09\uff1a")
    A("")
    reg = loc[loc["group_by"] == "region"].sort_values("delta_target_local", ascending=False)
    A("| Region | N | \u96f6\u6d41 N | \u96f6\u6d41\u89c2\u6d4b\u5360\u6bd4 | Q_FROZEN | "
      "Q_POSITIVE_ONLY | Delta_local | \u76f8\u5bf9\u5168\u5c40(FROZEN) | \u76f8\u5bf9\u5168\u5c40(POS) |")
    A("|---|---|---|---|---|---|---|---|---|")
    for _, r in reg.iterrows():
        A(f"| {r['group']} | {int(r['n_sections'])} | {int(r['n_zero_sim'])} | "
          f"{r['obs_share_zero']:.2%} | {r['Q_FROZEN']:.4f} | {r['Q_POSITIVE_ONLY']:.4f} | "
          f"{r['delta_target_local']:+.4f} | {r['rel_dev_vs_global_FROZEN']:+.4f} | "
          f"{r['rel_dev_vs_global_POS']:+.4f} |")
    A("")
    rad = loc[loc["group_by"] == "radial"].sort_values("delta_target_local", ascending=False)
    A("\u6c60\u5316 Sim/Obs\uff08\u6309 CBD \u5f84\u5411\uff09\uff1a")
    A("")
    A("| Radial | N | \u96f6\u6d41 N | Q_FROZEN | Q_POSITIVE_ONLY | Delta_local | "
      "\u76f8\u5bf9\u5168\u5c40(FROZEN) | \u76f8\u5bf9\u5168\u5c40(POS) |")
    A("|---|---|---|---|---|---|---|---|")
    for _, r in rad.iterrows():
        A(f"| {r['group']} | {int(r['n_sections'])} | {int(r['n_zero_sim'])} | "
          f"{r['Q_FROZEN']:.4f} | {r['Q_POSITIVE_ONLY']:.4f} | "
          f"{r['delta_target_local']:+.4f} | {r['rel_dev_vs_global_FROZEN']:+.4f} | "
          f"{r['rel_dev_vs_global_POS']:+.4f} |")
    A("")
    A("## 6. \u7ed3\u6784\u7ed3\u8bba\u662f\u5426\u88ab\u6c61\u67d3")
    A("")
    A(f"- Planning Region \u8de8\u5ea6\uff08Q_POSITIVE_ONLY\uff09= **{sep['struct_span']:.4f}**")
    A(f"- `Delta_target` = **{ga['delta_target']:.4f}**")
    A(f"- \u500d\u6570 = **{sep['ratio']:.2f} x**"
      f"\uff08\u9608\u503c \u2265 5\uff0c\u5224\u5b9a **{'PASS' if sep['ratio']>=5 else 'FAIL'}**\uff09")
    A("")
    A("\u21d2 \u7ed3\u6784\u7ed3\u8bba\uff087.6C \u7684\u533a\u57df\u7f3a\u53e3\u3001"
      "7.6C-1 \u7684 graded \u7f3a\u53e3\u5bf9\u4fee\u6b63\u7a33\u5065\uff09**\u4e0d\u53d7**"
      "\u9776\u573a\u4e0d\u786e\u5b9a\u6027\u6c61\u67d3\uff1b\u4f46**\u7edd\u5bf9\u89c4\u6a21**\u53d7\u5230\u3002")
    A("")
    A("## 7. \u5224\u636e\u4e0e\u88c1\u5b9a")
    A("")
    A("| \u5224\u636e | \u503c | \u901a\u8fc7 |")
    A("|---|---|---|")
    for c in CHECKS:
        A(f"| `{c['check']}` | {c['value']} | {'\u2705' if c['ok'] else '\u274c'} |")
    A("")
    A(f"### VERDICT = `{v}`")
    A("")
    A(nxt)
    A("")
    A("## 8. \u5206\u6b67\u8bf4\u660e\uff08\u4e3a\u4ec0\u4e48\u4e0d\u662f ADEQUATE\uff0c"
      "\u4e5f\u4e0d\u662f INADEQUATE\uff09")
    A("")
    A(f"- **\u4e0d\u662f `TARGET_ADEQUATE_FOR_ABSOLUTE_SCALE`**\uff1a\u7ec6\u6863 SNR = "
      f"{ga['snr_fine']:.3f} < 1\uff0c\u4e14 f = 1.10 \u843d\u5728 f* \u533a\u95f4\u5185\u90e8"
      f"\uff08\u53e3\u5f84\u5206\u6b67\uff09\uff0c\u4e14\u7f51\u683c\u672a\u8de8\u8d8a\u6574\u4e2a\u533a\u95f4\u3002")
    A(f"- **\u4e0d\u662f `TARGET_INADEQUATE`**\uff1a\u7c97\u6863 SNR = {ga['snr_coarse']:.3f} \u2265 1"
      f"\uff0c\u4e14\u4e09\u53e3\u5f84\u5728 **\u65b9\u5411\u4e0a\u4e00\u81f4**\uff08f* > 1\uff0c"
      f"\u9700\u4e0a\u8c03\uff09\u3002")
    A("")
    A("\u21d2 7.6F-1 \u53ef\u4ee5\u8fdb\u5165\uff0c\u4f46**\u6027\u8d28\u5fc5\u987b\u964d\u7ea7**\uff1a"
      "\u5b83\u8bfb\u51fa\u7684\u662f\u201c**\u5e26\u9776\u573a\u4e0d\u786e\u5b9a\u6027\u7684\u7c97\u6863 "
      "demand \u54cd\u5e94\u5173\u7cfb**\u201d\uff0c\u800c\u4e0d\u662f\u201c\u7edd\u5bf9 demand scale\u201d\u3002")
    A("")
    A("## 9. \u540e\u7eed\u5206\u652f")
    A("")
    A("```text")
    A("7.3.6A Frozen Target")
    A("   \u2193")
    A("7.6C-1 comparator artifact \u53d1\u73b0")
    A("   \u2193")
    A(f"7.6C-2 Target Integrity Gate  \u2190 \u672c\u6b65\uff1a{v}")
    A("   \u251c\u2500 target uncertainty \u53ef\u63a5\u53d7      \u2192 7.6F-1\uff08\u7edd\u5bf9 scale \u53ef\u8bfb\uff09")
    A("   \u251c\u2500 \u4ec5\u7c97\u6863\u53ef\u8bfb\uff08\u672c\u6b65\uff09      \u2192 7.6F-1\uff08\u964d\u7ea7\u4e3a\u7c97\u6863\u54cd\u5e94\uff0c"
      "\u7f51\u683c\u91cd\u6392\uff09")
    A("   \u2514\u2500 target uncertainty \u4e0d\u53ef\u63a5\u53d7  \u2192 \u65b0\u5efa crosswalk \u4fee\u590d\u5b9e\u9a8c"
      "\uff087.3.6A-b\uff09")
    A("```")
    A("")
    A("**\u786c\u7ea6\u675f**\uff1a\u201c\u53d1\u73b0\u6821\u51c6\u9776\u573a\u5b58\u5728\u53ef\u4fee\u6b63\u4f2a\u5f71"
      "\u201d\u2260\u201c\u5df2\u5141\u8bb8\u4fee\u6539\u51bb\u7ed3\u9776\u573a\u201d\u3002"
      "\u540e\u8005\u5fc5\u987b\u53e6\u7acb\u7248\u672c\u3001\u53e6\u7559\u8bc1\u636e\u94fe\u3002")
    A("")
    A("## 10. \u73af\u5883\u4e0e\u4ea7\u7269")
    A("")
    A(f"- \u8fd0\u884c\u8017\u65f6\uff1a**{runtime:.1f} s**\uff1b`zero_simulation = True`\uff1b"
      f"`matsim_rerun = False`\uff1b`parameters_changed = False`")
    A("- \u4f9d\u8d56\uff1a`compare_final_crosswalk_7_3_6b` / "
      "`diagnose_od_spatial_structure_7_6c` / `audit_anomaly_trace_7_6c_1`\uff08\u5747\u4ee5 "
      "import \u65b9\u5f0f\u590d\u7528\uff0c\u672a\u590d\u5236\u516c\u5f0f\uff09")
    A("- \u4ea7\u7269\uff1a`od_target_integrity_7_6c_2_summary.json`\u3001"
      "`target_integrity_crossvalidation.csv`\u3001`target_response_grid.csv`\u3001"
      "`target_step_snr.csv`\u3001`target_grid_placement.csv`\u3001"
      "`target_uncertainty_localisation.csv`")
    A("")

    (OUT_DIR / "STEP7_6C_2_REPORT.md").write_text("\n".join(L), encoding="utf-8")
    log(f"report written: {OUT_DIR / 'STEP7_6C_2_REPORT.md'}")


# ==========================================================================
# main
# ==========================================================================

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--skip-context", action="store_true",
                    help="accepted for CLI symmetry; context is always needed")
    args = ap.parse_args()  # noqa: F841

    t0 = time.time()
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    log("=" * 78)
    log("7.6C-2  Calibration Target Integrity Gate   (zero simulation, read-only)")
    log("=" * 78)
    log(f"ROOT      = {ROOT}")
    log(f"OUT_DIR   = {OUT_DIR}")
    log(f"classifier= FROZEN / POSITIVE_ONLY / BEST_DIRECTION "
        f"(+ outer envelope MATCH_NEAREST_LOWER / MATCH_SAMENAME_UPPER)")
    log(f"F-1 grid  = {F1_GRID}   steps = {STEP_COARSE:.2f} / {STEP_FINE:.2f}")
    log(f"eps_ref   = {EPS_REF:g}   SNR_min = {SNR_MIN:g}")
    log("zero-simulation run: crosswalk / OD / lambda / network untouched")

    ctx = a761.load_context()

    sub, pos, s2, q, bounds, xdf = build_calibers(ctx)
    ga = gate_arithmetic(q)
    grid, pldf, pr = response_grid(q, ga)
    loc, sep = localise_and_separate(sub, s2, ga)
    gdf, rec = recommend_grid(ga, pr)
    v, nxt = verdict(ga, pr, sep)

    runtime = time.time() - t0
    write_report(ctx, q, ga, grid, pldf, loc, sep, pr, v, nxt, runtime, gdf, rec)

    summary = {
        "step": "7.6C-2",
        "title": "Calibration Target Integrity Gate",
        "status": v,
        "verdict_detail": {
            "verdict": v,
            "next": nxt,
            "criteria": {c["check"]: c["ok"] for c in CHECKS},
            "criteria_pass": int(sum(1 for c in CHECKS if c["ok"])),
            "criteria_total": len(CHECKS),
            "target_uncertainty_exists": get_check("G1.target_uncertainty_exists"),
            "coarse_step_resolvable": get_check("G2.coarse_step_resolvable"),
            "fine_step_resolvable": get_check("G3.fine_step_resolvable"),
            "calibers_agree_on_grid": get_check("G4.caliber_agreement_on_grid"),
            "grid_brackets_fstar": get_check("G5.grid_brackets_fstar_interval"),
            "structural_separability_ok": get_check("G6.structural_separability"),
        },
        "zero_simulation": True,
        "matsim_rerun": False,
        "parameters_changed": False,
        "crosswalk_modified": False,
        "demand_scale_selected": False,
        "lambda_selected": False,
        "anchor_sim_obs": ANCHOR_SIM_OBS,
        "scale": SCALE,
        "preregistered": PREREGISTERED,
        "calibers": {k: q[k] for k in
                     ["FROZEN", "POSITIVE_ONLY", "BEST_DIRECTION",
                      "MATCH_NEAREST_LOWER", "MATCH_SAMENAME_UPPER",
                      "FROZEN_WMEAN_OF_RATIOS"]},
        "caliber_roles": CALIBER_ROLE,
        "gate_arithmetic": {
            "delta_target_sim_obs": ga["delta_target"],
            "delta_target_pp": 100 * ga["delta_target"],
            "admissible_band_span_pp": 100 * ga["span"],
            "outer_envelope": [ga["outer_lo"], ga["outer_hi"]],
            "fstar_by_caliber": ga["fstar"],
            "fstar_interval": [ga["f_lo"], ga["f_hi"]],
            "delta_f_target": ga["df_target"],
            "snr_coarse_step": ga["snr_coarse"],
            "snr_fine_step": ga["snr_fine"],
            "eps_required_coarse": ga["eps_coarse"],
            "eps_required_fine": ga["eps_fine"],
            "eps_reference": EPS_REF,
            "robustness_574": ga["robustness_574"],
        },
        "grid_placement": {
            "f1_grid": F1_GRID,
            "f1_grid_brackets_interval": pr["brackets"],
            "grid_points_inside_interval": pr["inside"],
            "distinct_regimes_resolved": pr["n_distinct_regimes"],
        },
        "grid_recommendation": {
            "criterion": "min step >= Delta_f_target and grid brackets the f* interval",
            "recommended": rec,
            "candidates": gdf.to_dict(orient="records") if gdf is not None else [],
        },
        "structural_separability": {
            "region_span_pos_only": sep["struct_span"],
            "delta_target": ga["delta_target"],
            "ratio": sep["ratio"],
        },
        "coverage": {
            "n_sections": int(len(sub)),
            "n_zero_sim": int((sub["sim_8_9_scaled"] <= 0).sum()),
            "obs_share_on_zero_sim":
                float(sub.loc[sub["sim_8_9_scaled"] <= 0, "obs_8_9"].sum()
                      / sub["obs_8_9"].sum()),
        },
        "checks": CHECKS,
        "crossvalidation": xdf.to_dict(orient="records"),
        "localisation_by_region": loc[loc["group_by"] == "region"].to_dict(orient="records"),
        "localisation_by_radial": loc[loc["group_by"] == "radial"].to_dict(orient="records"),
        "response_grid": grid.to_dict(orient="records"),
        "outputs_dir": str(OUT_DIR),
        "runtime_s": round(runtime, 1),
    }
    (OUT_DIR / "od_target_integrity_7_6c_2_summary.json").write_text(
        json.dumps(_jsonable(summary), ensure_ascii=False, indent=2), encoding="utf-8")

    log("")
    log("=" * 78)
    log(f"7.6C-2 DONE  verdict = {v}   ({runtime:.1f}s)")
    log(f"products in {OUT_DIR}")
    log("=" * 78)


if __name__ == "__main__":
    main()
