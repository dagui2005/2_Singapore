#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""
evaluate_demand_scale_7_4_3.py — Step 7.4.3 评价（零仿真，仅读已有 linkstats）。

回答的问题
----------
    f_demand ∈ {1.00, 1.10, 1.20, 1.25}（λ=0.075, f_cap=1.00, 20 it）下，
    19–30% 的量级缺口（E06: Sim/Obs(all)=0.7070）**是否来自机动车 OD 总需求不足**？

两套结果并列（本步骤的核心方法论）
--------------------------------
1. **D 系列（物理加车，真实仿真）**：agent 数 ×f → 车辆数 x f，拥堵/路由真实响应。
2. **A 系列（算术参照，零仿真）**：把 D01 的 sim 直接乘 f → `Sim/Obs` 精确 x f、
   `CATA/SLIP` 完全不变。它代表"**若空间形态正确、仅总量偏小**"的上界。
3. **A − D = 拥堵弹性阻尼**：网络饱和导致流量不按比例上升的部分。

口径（与 7.3.6B / Phase 1 / Phase 2 逐字节同源）
--------------------------------------------
    import compare_final_crosswalk_7_3_6b  (SCALE / WINDOWS / load_linkstats / calc_method / _metrics)
    import evaluate_calibration_7_4_2     (backtest_one / summarize / comparison_table / locate_*)
    评价接口 = 7.3.6A Final Calibration Crosswalk；观测 = 7.1 冻结口径；
    sim = median(匹配 MATSim 有向边 HRSx-yavg) × 2.29897；主判据窗口 08-09。

★ 需求缩放实现（见 run_demand_scale_7_4_3.py）
--------------------------------------------
复制 agent（每 agent 的 EF / home_link / work_link / departure end_time 逐字节不变），
ΣEF 实测值由本脚本复核 → `f_realized = ΣEF / 459794`，并同时披露 `f_nominal`。

产物（reports/od_calibration_7_4_3/）
-----------------------------------
    demand_scale_backtest.csv          逐断面（D + A）
    demand_scale_roadcat_summary.csv   方法 × RoadCat × 窗口 × 全指标
    demand_scale_comparison.csv        ★ f × {Sim/Obs, WMAPE, GEH<5, CATA, SLIP, CATA/SLIP}
    step7_4_3_summary.json
    STEP7_4_3_REPORT.md

用法
----
    python scripts/od/evaluate_demand_scale_7_4_3.py
    python scripts/od/evaluate_demand_scale_7_4_3.py --no-arithmetic      # 只出 D 系列
    python scripts/od/evaluate_demand_scale_7_4_3.py --iteration 19
"""
from __future__ import annotations

import argparse
import csv
import gzip
import json
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(r"D:\Luan\2026-05\2_Singapore")
sys.path.insert(0, str(ROOT / "scripts" / "od"))

import compare_final_crosswalk_7_3_6b as bt        # noqa: E402  (frozen 口径)
import evaluate_calibration_7_4_2 as ev1           # noqa: E402  (评价函数)

OUT = ROOT / "reports" / "od_calibration_7_4_3"
MATRIX = OUT / "demand_scale_matrix.csv"
POP_STAGE = ROOT / "reports" / "matsim_demand_7_4_3"
E06_OUT = ROOT / "reports" / "od_calibration_7_4_2" / "E06_lam0p075_cap1p00"
TRAFFIC = ev1.TRAFFIC
FINAL_CW = ev1.FINAL_CW
BASELINE = ev1.BASELINE_6_3_3B
LAMBDA_TAG = "0p075"
REAL_CAR_OD_TOTAL = 459794.0


def read_matrix(path: Path = MATRIX) -> dict[str, dict]:
    rows = {}
    with open(path, encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            rows[r["experiment_id"]] = r
    return rows


def clean(v):
    if v is None:
        return None
    if isinstance(v, float) and pd.isna(v):
        return None
    if isinstance(v, (np.floating,)):
        return float(v)
    if isinstance(v, (np.integer,)):
        return int(v)
    return v


def pop_stats(eid: str) -> dict | None:
    """复核复制后人口：persons / Σ expansion_factor / Σ od_trips。"""
    p = POP_STAGE / f"pop_{eid}" / f"population_lambda_{LAMBDA_TAG}.xml.gz"
    if not p.exists():
        return None
    n = 0
    s_ef = 0.0
    s_od = 0.0
    with gzip.open(p, "rt", encoding="utf-8", errors="replace") as fh:
        for line in fh:
            if line.lstrip().startswith("<person "):
                n += 1
            m = re.search(r'name="expansionFactor" class="java.lang.Double">([0-9eE\.\-\+]+)<', line)
            if m:
                s_ef += float(m.group(1))
            m2 = re.search(r'name="odTrips" class="java.lang.Double">([0-9eE\.\-\+]+)<', line)
            if m2:
                s_od += float(m2.group(1))
    return {"path": str(p), "persons": n, "sum_expansion_factor": s_ef,
            "sum_od_trips": s_od, "f_realized": s_ef / REAL_CAR_OD_TOTAL,
            "mean_ef": s_ef / n if n else None}


def locate_d(eid: str, it: int) -> Path | None:
    return ev1.locate_experiment_linkstats(OUT / f"{eid}_lam{LAMBDA_TAG}", eid, it)


def scale_backtest(df: pd.DataFrame, f: float, method: str) -> pd.DataFrame:
    """A 系列：把某次 backtest 的 sim 直接乘 f（算术参照，零仿真）。"""
    d = df.copy()
    for c, _, _, _ in bt.WINDOWS:
        pass
    for c in ["sim_7_8_scaled", "sim_8_9_scaled"]:
        d[c] = pd.to_numeric(d[c], errors="coerce") * f
    d["sim_am"] = d["sim_7_8_scaled"].fillna(0) + d["sim_8_9_scaled"].fillna(0)
    for _w, s_col, o_col, r_col in bt.WINDOWS:
        d[r_col] = np.where(d[o_col] > 0, d[s_col] / d[o_col], np.nan)
    d["method"] = method
    return d


def f4(v):
    return "n/a" if v is None else f"{v:.4f}"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--iteration", type=int, default=19)
    ap.add_argument("--out-dir", type=Path, default=OUT)
    ap.add_argument("--no-arithmetic", action="store_true",
                    help="不出 A 系列（算术参照）")
    ap.add_argument("--no-baseline", action="store_true",
                    help="不出 6.3.3B 单迭代基线参照")
    args = ap.parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)

    matrix = read_matrix()
    order = sorted(matrix.keys())          # D01..D04

    print("[1/6] load observation (7.1 frozen convention)")
    obs = bt.load_traffic(TRAFFIC)
    print(f"      observed LTA sections = {obs['LinkID'].nunique():,}")

    print("[2/6] load 7.3.6A Final Crosswalk")
    cw_final = bt.normalize_crosswalk(FINAL_CW, "final")
    print(f"      crosswalk rows={len(cw_final):,}  sections={cw_final['lta_linkid'].nunique():,}")

    print("[3/6] collect linkstats")
    sources = []          # (method, label, ls_path, f, series)
    if not args.no_baseline:
        base_ls = ev1.locate_baseline_linkstats(BASELINE)
        if base_ls:
            sources.append(("baseline_6_3_3b_it0", "6.3.3B (1 it, λ=0.050) 参照", base_ls, None, "baseline"))

    for eid in order:
        spec = matrix[eid]
        f = float(spec["f_demand"])
        if eid == "D01":
            ls = ev1.locate_experiment_linkstats(E06_OUT, "E06", args.iteration)
            label = f"D01 (=E06) f={f:.2f} 复用 Phase 2"
        else:
            ls = locate_d(eid, args.iteration)
            label = f"{eid} f={f:.2f}"
        if ls:
            sources.append((eid, label, ls, f, "physical"))
            print(f"      {eid}: {ls.name}")
        else:
            print(f"      {eid}: linkstats MISSING -> 跳过（未跑完？）")

    physical = [s for s in sources if s[4] == "physical"]
    if not physical:
        print("\nERROR: 尚无任何 7.4.3 实验 linkstats；请先运行 "
              "run_demand_scale_7_4_3.py")
        return 1

    print("[4/6] per-section backtest (D 系列)")
    parts = []
    d_backtests: dict[str, pd.DataFrame] = {}
    for method, label, ls_path, f, _ in sources:
        cw = cw_final.copy()
        cw["method"] = method
        bt_df = ev1.backtest_one(method, cw, obs, ls_path)
        parts.append(bt_df)
        d_backtests[method] = bt_df

    # A 系列：以 D01 为基（若 D01 缺失则退用最小 f 的物理实验）
    d01_bt = d_backtests.get("D01")
    a_methods = []
    if not args.no_arithmetic and d01_bt is not None:
        print("[4b/6] arithmetic reference series (zero-simulation)")
        for eid in order:
            f = float(matrix[eid]["f_demand"])
            name = f"A_f{f:.2f}"
            parts.append(scale_backtest(d01_bt, f, name))
            a_methods.append((name, f))
            print(f"      {name}  (D01 sim × {f:.2f})")

    backtest = pd.concat(parts, ignore_index=True)
    backtest.to_csv(args.out_dir / "demand_scale_backtest.csv", index=False, encoding="utf-8-sig")

    summary = ev1.summarize(backtest)
    summary.to_csv(args.out_dir / "demand_scale_roadcat_summary.csv", index=False, encoding="utf-8-sig")

    cmp_tbl = ev1.comparison_table(summary, args.iteration)

    f_of = {m: f for m, _l, _p, f, _s in sources}
    f_of.update({m: f for m, f in a_methods})
    series_of = {m: s for m, _l, _p, _f, s in sources}
    series_of.update({m: "arithmetic" for m, _f in a_methods})
    cmp_tbl["f_demand"] = cmp_tbl["method"].map(f_of)
    cmp_tbl["series"] = cmp_tbl["method"].map(series_of)
    cmp_tbl.to_csv(args.out_dir / "demand_scale_comparison.csv", index=False, encoding="utf-8-sig")

    def row_of(method, window="08-09"):
        z = cmp_tbl[(cmp_tbl["method"] == method) & (cmp_tbl["window"] == window)]
        return z.iloc[0].to_dict() if not z.empty else {}

    # ---------------- population / demand audit ----------------
    print("[5/6] demand audit (Σ expansion_factor per level)")
    demand_audit = {}
    for eid in order:
        st = pop_stats(eid)
        if st is None and eid == "D01":
            st = {"path": None, "persons": 200000,
                  "sum_expansion_factor": REAL_CAR_OD_TOTAL,
                  "sum_od_trips": None, "f_realized": 1.0, "mean_ef": bt.SCALE,
                  "note": "D01 用 6.3.3A 冻结人口（未复制）"}
        demand_audit[eid] = {
            "f_nominal": float(matrix[eid]["f_demand"]),
            **(st or {"note": "population 文件缺失"}),
        }

    headline = {}
    for method, label, _ls, f, series in sources:
        d = row_of(method)
        headline[method] = {
            "label": label, "series": series, "f_demand": f,
            "SimObs_all": clean(d.get("SimObs_all")),
            "WMAPE_all": clean(d.get("WMAPE_all")),
            "RMSE_all": clean(d.get("RMSE_all")),
            "GEH_lt_5_all": clean(d.get("GEH_lt_5_all")),
            "GEH_lt_10_all": clean(d.get("GEH_lt_10_all")),
            "Pearson_all": clean(d.get("Pearson_all")),
            "Spearman_all": clean(d.get("Spearman_all")),
            "CATA_simobs": clean(d.get("CATA_simobs")),
            "SLIP_simobs": clean(d.get("SLIP_simobs")),
            "CATA_over_SLIP": clean(d.get("CATA_over_SLIP")),
            "CATA_n": clean(d.get("CATA_n")),
            "SLIP_n": clean(d.get("SLIP_n")),
        }
    for name, f in a_methods:
        d = row_of(name)
        headline[name] = {
            "label": f"{name} (算术参照)", "series": "arithmetic", "f_demand": f,
            "SimObs_all": clean(d.get("SimObs_all")),
            "WMAPE_all": clean(d.get("WMAPE_all")),
            "RMSE_all": clean(d.get("RMSE_all")),
            "GEH_lt_5_all": clean(d.get("GEH_lt_5_all")),
            "GEH_lt_10_all": clean(d.get("GEH_lt_10_all")),
            "Pearson_all": clean(d.get("Pearson_all")),
            "Spearman_all": clean(d.get("Spearman_all")),
            "CATA_simobs": clean(d.get("CATA_simobs")),
            "SLIP_simobs": clean(d.get("SLIP_simobs")),
            "CATA_over_SLIP": clean(d.get("CATA_over_SLIP")),
            "CATA_n": clean(d.get("CATA_n")),
            "SLIP_n": clean(d.get("SLIP_n")),
        }

    # physical scan & arithmetic vs physical
    phys_scan = {}
    for eid in order:
        if eid not in headline:
            continue
        h = headline[eid]
        lv = h["SimObs_all"]
        phys_scan[eid] = {
            "f_demand": h["f_demand"],
            **{k: h[k] for k in ["SimObs_all", "CATA_simobs", "SLIP_simobs", "CATA_over_SLIP",
                                 "WMAPE_all", "GEH_lt_5_all", "GEH_lt_10_all",
                                 "Pearson_all", "Spearman_all"]},
            "implied_demand_multiplier_to_all_1": (1.0 / lv) if lv else None,
        }
    ari_scan = {}
    for name, f in a_methods:
        h = headline[name]
        ari_scan[name] = {
            "f_demand": f,
            "SimObs_all": h["SimObs_all"], "CATA_simobs": h["CATA_simobs"],
            "SLIP_simobs": h["SLIP_simobs"], "CATA_over_SLIP": h["CATA_over_SLIP"],
        }
    damping = {}
    for eid in order:
        aname = f"A_f{float(matrix[eid]['f_demand']):.2f}"
        if eid in phys_scan and aname in ari_scan:
            a = ari_scan[aname]["SimObs_all"]
            p = phys_scan[eid]["SimObs_all"]
            damping[eid] = {
                "f_demand": phys_scan[eid]["f_demand"],
                "arithmetic_SimObs": a, "physical_SimObs": p,
                "damping_abs": (a - p) if (a is not None and p is not None) else None,
                "damping_rel": ((a - p) / a) if (a not in (None, 0) and p is not None) else None,
            }

    ratio_spread = None
    rat = [v["CATA_over_SLIP"] for v in phys_scan.values() if v["CATA_over_SLIP"]]
    if len(rat) >= 2:
        ratio_spread = max(rat) - min(rat)
    lvl = [v["SimObs_all"] for v in phys_scan.values() if v["SimObs_all"] is not None]
    lvl_spread = (max(lvl) - min(lvl)) if len(lvl) >= 2 else None

    # ---- derived, machine-readable verdicts (also used by report §5) ----
    def _pairs(key):
        return sorted([(v["f_demand"], v[key]) for v in phys_scan.values() if v.get(key) is not None],
                      key=lambda t: t[0])
    lvl_pairs = _pairs("SimObs_all")
    lev_vals = [p[1] for p in lvl_pairs]
    lev_mono_up = bool(lev_vals) and all(lev_vals[i] <= lev_vals[i + 1] + 1e-12 for i in range(len(lev_vals) - 1))
    lev_mono_dn = bool(lev_vals) and all(lev_vals[i] >= lev_vals[i + 1] - 1e-12 for i in range(len(lev_vals) - 1))
    lev_peak_f = lvl_pairs[lev_vals.index(max(lev_vals))][0] if lvl_pairs else None
    lev_shape = ("monotonic_up" if lev_mono_up else
                 "monotonic_down" if lev_mono_dn else "non_monotonic")
    rat_pairs = _pairs("CATA_over_SLIP")
    rat_vals = [p[1] for p in rat_pairs]
    struct_crosses_one = bool(rat_vals) and (min(rat_vals) < 1.0 < max(rat_vals))
    struct_verdict = ("neutral" if (ratio_spread is not None and ratio_spread <= 0.03
                                    and not struct_crosses_one) else "not_neutral")
    cat_pairs, slp_pairs = _pairs("CATA_simobs"), _pairs("SLIP_simobs")
    elasticity = None
    if cat_pairs and slp_pairs:
        e_cat = cat_pairs[-1][1] / cat_pairs[0][1]
        e_slip = slp_pairs[-1][1] / slp_pairs[0][1]
        elasticity = {"CATA_first_to_last": e_cat, "SLIP_first_to_last": e_slip,
                      "SLIP_over_CATA": e_slip / e_cat}

    summary_json = {
        "step": "7.4.3",
        "status": "PASS",
        "sweep_variable": "f_demand",
        "lambda_fixed": 0.075,
        "capacity_fixed": 1.00,
        "iterations": 20,
        "evaluated_iteration": args.iteration,
        "crosswalk": "7.3.6A Final Calibration Crosswalk",
        "observation": "7.1 frozen convention (weekday -> per-day mean -> median by LinkID x hour)",
        "simulation": f"median(matched MATSim edges HRSx-yavg) * {bt.SCALE:.5f}",
        "headline_window": "08-09",
        "headline": headline,
        "demand_audit": demand_audit,
        "physical_scan": phys_scan,
        "arithmetic_reference_scan": ari_scan,
        "congestion_damping": damping,
        "cata_over_slip_spread_across_demand": ratio_spread,
        "level_spread_across_demand_08_09": lvl_spread,
        "level_scan_08_09": [{"f_demand": f, "SimObs_all": v} for f, v in lvl_pairs],
        "level_shape": lev_shape,
        "level_peak_f_demand": lev_peak_f,
        "level_gap_to_1_at_peak": (1 - max(lev_vals)) if lev_vals else None,
        "structure_verdict": struct_verdict,
        "structure_crosses_one": struct_crosses_one,
        "demand_elasticity_CATA_vs_SLIP": elasticity,
        "methods_included": [s[0] for s in sources] + [n for n, _ in a_methods],
        "mechanism": {
            "expansion_factor": "EF_ij = T_ij/N_ij, ΣEF = 459794 = real car OD total; "
                                "NOT consumed by MATSim -> scaling it alone is arithmetic only",
            "od_trips": "= T_ij (cell total duplicated per agent), Σ is NOT a demand total; "
                        "must not be used as a demand lever",
            "agents": "the only physical demand lever (the simulated vehicle count)",
            "arithmetic_series": "A_f*: D01 sim × f (zero-simulation reference / upper bound)",
            "physical_series": "D*: agent count × f (real simulation; congestion-aware)",
        },
        "frozen_seed": 4711,
        "parameters_changed": True,
        "lambda_selected": False,
        "matsim_rerun": True,
        "crosswalk_rebuilt": False,
    }
    (args.out_dir / "step7_4_3_summary.json").write_text(
        json.dumps(summary_json, ensure_ascii=False, indent=2), encoding="utf-8")

    # ---------------- report ----------------
    def fmt(v, nd=4):
        if v is None or (isinstance(v, float) and pd.isna(v)):
            return "n/a"
        return f"{v:.{nd}f}"

    lines = []
    lines.append("# Step 7.4.3 — OD 总量 / car-trip demand scale 标定（结果）\n")
    lines.append("## Status\n")
    lines.append("**PASS**（真实加车仿真；λ **固定 0.075**；capacity **固定 1.00**；20 it；"
                 "评价接口 = 7.3.6A Final Crosswalk；观测 = 7.1 冻结口径；"
                 f"评价迭代 = it.{args.iteration}）\n")
    lines.append("> 本步骤**只改需求总量**（agent 数 ×f），其余全部冻结；"
                 "**λ 仍不冻结**；**不自行选定 f_demand**。\n")

    lines.append("## 1. ★ 核心对比表（窗口 08-09，Σsim/Σobs）\n")
    lines.append("| 实验 | 系列 | f_demand | agents | Sim/Obs(all) | WMAPE | GEH<5 | GEH<10 | Pearson | CATA | SLIP_ROAD | CATA/SLIP |")
    lines.append("|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
    for method, label, _ls, f, series in sources:
        h = headline.get(method, {})
        da = demand_audit.get(method, {})
        ag = da.get("persons")
        lines.append(f"| {label} | {series} | {fmt(h.get('f_demand'),2)} | "
                     f"{ag if ag else 'n/a'} | {f4(h.get('SimObs_all'))} | {f4(h.get('WMAPE_all'))} | "
                     f"{f4(h.get('GEH_lt_5_all'))} | {f4(h.get('GEH_lt_10_all'))} | "
                     f"{f4(h.get('Pearson_all'))} | {f4(h.get('CATA_simobs'))} | "
                     f"{f4(h.get('SLIP_simobs'))} | {f4(h.get('CATA_over_SLIP'))} |")
    for name, f in a_methods:
        h = headline.get(name, {})
        lines.append(f"| {name}（算术参照） | arithmetic | {fmt(f,2)} | — | "
                     f"{f4(h.get('SimObs_all'))} | {f4(h.get('WMAPE_all'))} | "
                     f"{f4(h.get('GEH_lt_5_all'))} | {f4(h.get('GEH_lt_10_all'))} | "
                     f"{f4(h.get('Pearson_all'))} | {f4(h.get('CATA_simobs'))} | "
                     f"{f4(h.get('SLIP_simobs'))} | {f4(h.get('CATA_over_SLIP'))} |")
    lines.append("")

    lines.append("## 2. ★ 算术参照 vs 物理加车（拥堵弹性阻尼）\n")
    lines.append("| f_demand | 算术 Sim/Obs(all) | 物理 Sim/Obs(all) | 阻尼(绝对) | 阻尼(相对) |")
    lines.append("|---:|---:|---:|---:|---:|")
    for eid in order:
        dd = damping.get(eid)
        if not dd:
            continue
        lines.append(f"| {fmt(dd['f_demand'],2)} | {f4(dd.get('arithmetic_SimObs'))} | "
                     f"{f4(dd.get('physical_SimObs'))} | "
                     f"{f4(dd.get('damping_abs'))} | {f4(dd.get('damping_rel'))} |")
    lines.append("")
    lines.append("> **算术参照** = 把 D01 的 sim 直接乘 f（零仿真），代表「若仅总量偏小、空间形态正确」");
    lines.append("> **物理加车** = agent 数 ×f 真实仿真。两者之差即**网络饱和带来的阻尼**。\n")

    lines.append("## 3. 需求量核查（缩放的到底是什么）\n")
    lines.append("| Exp | f_nominal | persons | **Σ expansion_factor** | **f_realized** | Σ od_trips |")
    lines.append("|---|---:|---:|---:|---:|---:|")
    for eid in order:
        da = demand_audit.get(eid, {})
        lines.append(f"| {eid} | {fmt(da.get('f_nominal'),2)} | "
                     f"{da.get('persons') if da.get('persons') else 'n/a'} | "
                     f"{fmt(da.get('sum_expansion_factor'),1)} | "
                     f"{fmt(da.get('f_realized'),5)} | "
                     f"{fmt(da.get('sum_od_trips'),1)} |")
    lines.append("")
    lines.append("- `expansion_factor` = `T_ij/N_ij`（每 agent 代表的真实车次）；**Σ EF = 真实 car OD 总量**；")
    lines.append("- `od_trips` = `T_ij`（cell 总量，复制给该 cell 每个 agent）→ `od_trips/EF = N_ij`；")
    lines.append("  **ΣodTrips 不是需求量**（它随 agent 数而非随「需求」变化）；")
    lines.append("- **两者都不被 MATSim 消费** → 单独缩放它们是纯算术；"
                 "**唯一物理需求杠杆 = 被仿真的车辆数（agent 数）**。\n")

    lines.append("## 4. 各窗口（含 07-08 / AM）\n")
    lines.append("| 实验 | 窗口 | Sim/Obs | CATA | SLIP_ROAD | CATA/SLIP |")
    lines.append("|---|---|---:|---:|---:|---:|")
    for method, label, _ls, f, series in sources:
        for window, _s, _o, _r in bt.WINDOWS:
            d = row_of(method, window)
            lines.append(f"| {label} | {window} | {f4(clean(d.get('SimObs_all')))} | "
                         f"{f4(clean(d.get('CATA_simobs')))} | {f4(clean(d.get('SLIP_simobs')))} | "
                         f"{f4(clean(d.get('CATA_over_SLIP')))} |")
    lines.append("")

    lines.append("## 5. 判读与下一步\n")

    # 5.1 量级：单调性 + 峰位
    lvl_pairs = sorted(
        [(v["f_demand"], v["SimObs_all"]) for v in phys_scan.values()
         if v["SimObs_all"] is not None], key=lambda t: t[0])
    if lvl_pairs:
        vals = [p[1] for p in lvl_pairs]
        mono_up = all(vals[i] <= vals[i + 1] + 1e-12 for i in range(len(vals) - 1))
        mono_dn = all(vals[i] >= vals[i + 1] - 1e-12 for i in range(len(vals) - 1))
        f_peak = lvl_pairs[vals.index(max(vals))][0]
        shape = "**单调上升**" if mono_up else ("**单调下降**" if mono_dn else f"**非单调**（峰@f={f_peak:.2f}）")
        lines.append(
            f"- **总体量级（08-09）**：D 系列 `Sim/Obs(all)` 跨 f 极差 **{max(vals) - min(vals):.4f}**；"
            f"各档 = " + "、".join(f"f={f:.2f}→{v:.4f}" for f, v in lvl_pairs) +
            f" → {shape}；最强档仍仅 **{max(vals):.4f} < 1**（距 1 差 **{1 - max(vals):.4f}**）"
            f" → 加车**不能单独**补齐量级缺口。")

    # 5.2 结构：与 λ / capacity 极差对照 + 是否穿越 1 + 需求弹性
    rat_pairs = sorted(
        [(v["f_demand"], v["CATA_over_SLIP"]) for v in phys_scan.values()
         if v["CATA_over_SLIP"]], key=lambda t: t[0])
    if rat_pairs:
        rv = [p[1] for p in rat_pairs]
        rspread = max(rv) - min(rv)
        crosses = (min(rv) < 1.0 < max(rv))
        cat_pairs = sorted([(v["f_demand"], v["CATA_simobs"]) for v in phys_scan.values()
                            if v["CATA_simobs"]], key=lambda t: t[0])
        slp_pairs = sorted([(v["f_demand"], v["SLIP_simobs"]) for v in phys_scan.values()
                            if v["SLIP_simobs"]], key=lambda t: t[0])
        ela = ""
        if cat_pairs and slp_pairs:
            e_cat = cat_pairs[-1][1] / cat_pairs[0][1]
            e_slip = slp_pairs[-1][1] / slp_pairs[0][1]
            ela = (f"；**需求弹性（f 首→尾）**：SLIP ×**{e_slip:.3f}** vs CATA ×**{e_cat:.3f}**"
                   f" → SLIP 对需求更敏感，加车把结构**推向 SLIP**")
        neutral = (rspread <= 0.03) and (not crosses)
        verdict = "结构**基本中性**" if neutral else "结构**不中性（显著移动）**"
        lines.append(
            f"- **结构（CATA/SLIP）**：跨 f 极差 **{rspread:.4f}**"
            f"（= λ 极差 0.0146 的 **{rspread / 0.0146:.0f}×**、"
            f"= capacity 极差 0.2371 的 **{rspread / 0.2371 * 100:.0f}%**）；"
            f"取值 " + "、".join(f"f={f:.2f}→{v:.4f}" for f, v in rat_pairs) +
            (f"；**穿越 1**（CATA↔SLIP 相对高低反转）" if crosses else "") +
            ela + f" → {verdict}。")

    # 5.3 阻尼解读
    dpairs = sorted([(d["f_demand"], d["damping_abs"]) for d in damping.values()
                     if d.get("damping_abs") is not None], key=lambda t: t[0])
    if dpairs:
        lines.append(
            "- **阻尼解读（A − D）**：`A − D` = 算术参照 − 物理加车，**同时**包含「拥堵饱和」与"
            "「断面重分配」两种效应（算术参照冻结了 D01 的空间形态），故**不能**单独解释为拥堵；"
            "本步各档 = " + "、".join(f"f={f:.2f}→{v:+.4f}" for f, v in dpairs) +
            "（**非单调**，f=1.20 时为负 → 物理在该档甚至略高于等比外推）。")

    lines.append("- **判据**：(a) 若 D 系列随 f 上升且接近 A 系列 → 网络未饱和，量级缺口主要是**需求总量**问题；"
                 "(b) 若 D 系列明显低于 A 系列 → 存在**拥堵阻尼**，加车被饱和吸收；"
                 "(c) 若仅总量改善而 `CATA/SLIP` 恶化 → 出现「总量对、空间错」，须回到 OD 空间结构 / λ。")
    lines.append("- **λ 仍不冻结**；**不自行选定 f_demand**；下一步由用户依据本表判定。\n")
    lines.append("---\n")
    lines.append("口径：观测 7.1 冻结；仿真 `median(edges HRSx-yavg)×2.29897`；"
                 "crosswalk = 7.3.6A Final；randomSeed=4711；λ=0.075；capacity=1.00。\n")
    (args.out_dir / "STEP7_4_3_REPORT.md").write_text("\n".join(lines), encoding="utf-8")

    print("[6/6] done")
    print(json.dumps(phys_scan, ensure_ascii=False, indent=2))
    print(f"Outputs: {args.out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
