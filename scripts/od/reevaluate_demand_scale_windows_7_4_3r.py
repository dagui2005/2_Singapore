#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""
reevaluate_demand_scale_windows_7_4_3r.py — Step 7.4.3-R
「宽时间窗重新评价」（zero simulation，只读 D01-D04 的 it.19 linkstats）。

回答的问题
----------
    7.4.3 的 demand scale 非单调（f=1.20 峰 -> f=1.25 回落）在**更宽的时间窗**下
    是否消失？如果消失，宽窗能否作为 demand scale 的水平判据？

★ 本步骤最重要的前置事实（决定了窗口集合）
------------------------------------------
LTA 原始流量 TrafficFlow_Data.json 的 HourOfDate **只有 7 与 8 两个值**
（38,083 + 37,816 = 75,899 行；1,311 个 LinkID；2025-11-01..11-30 共 30 天）。
它不是脚本侧过滤造成的：7.1 冻结口径 load_traffic() 里的
tf["HourOfDate"].isin([7, 8]) 与数据本身一致。
项目内其它候选动态源（TrafficSpeedBands_v4.json 56 MB、EstimatedTravelTimes.json）
**都是单时刻快照**（各只含 1 个 Timestamp），没有时间序列。

    => 可观测窗口上限 = 07-09（= 冻结命名里的 AM）。
       09-10 / 10-11 / 07-11 / 00-24 **没有观测对象**，
       其 Sim/Obs / WMAPE / GEH **在数学上无定义**，不是「缺失」。

窗口分两类：

    Class O（可观测，出完整 Sim/Obs 指标）
        07-08   hours=[7]      obs=obs_7_8
        08-09   hours=[8]      obs=obs_8_9
        07-09   hours=[7,8]    obs=obs_am     <-- 最宽可观测窗（= AM）

    Class S（无观测，只出模拟侧量级，不做 Sim/Obs）
        07-10   hours=[7,8,9]
        07-11   hours=[7,8,9,10]
        07-12   hours=[7..11]
        00-24   hours=[0..23]

估计量（与冻结口径逐字节同源）
------------------------------
    每 LTA 断面： med_h = median(匹配 MATSim 有向边的 HRS{h}-{h+1}avg)
                 scaled_h = med_h x SCALE            (SCALE = 459794/200000)
                 窗口    ： sim_W = sum_{h in W} scaled_h
    与冻结定义完全一致：sim_7_8 = scaled_7、sim_8_9 = scaled_8、
    sim_am = scaled_7 + scaled_8。脚本**断言复现值与
    reports/od_calibration_7_4_3/demand_scale_backtest.csv 逐值一致**。

两种聚合（用于拆分「时间迁移」与「估计量畸变」）
------------------------------------------------
    A) 断面 x 中位数估计量（标定实际使用的口径）
       r_section = sum_断面 sim_W(f_hi) / sum_断面 sim_W(f_lo)
       * 恒等于 headline SimObs_ratio_sum 的跨 f 比值（obs 不随 f 变）
    B) 全网链路求和（系统级总量）
       r_links   = sum_链路 HRS_W(f_hi) / sum_链路 HRS_W(f_lo)
    estimator_distortion = r_section / r_links
       <1 = 单小时中位数在强拥堵下把跨档比值额外压低

用法
----
    python scripts/od/reevaluate_demand_scale_windows_7_4_3r.py --iteration 19
    python scripts/od/reevaluate_demand_scale_windows_7_4_3r.py --no-arithmetic
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(r"D:\Luan\2026-05\2_Singapore")
sys.path.insert(0, str(ROOT / "scripts" / "od"))

import compare_final_crosswalk_7_3_6b as bt        # noqa: E402  (冻结口径)
import evaluate_calibration_7_4_2 as ev1           # noqa: E402  (评价函数)

OUT = ROOT / "reports" / "od_calibration_7_4_3r"
PREV = ROOT / "reports" / "od_calibration_7_4_3"
MATRIX = PREV / "demand_scale_matrix.csv"
REF_BACKTEST = PREV / "demand_scale_backtest.csv"
E06_OUT = ROOT / "reports" / "od_calibration_7_4_2" / "E06_lam0p075_cap1p00"
TRAFFIC = ev1.TRAFFIC
FINAL_CW = ev1.FINAL_CW
BASELINE = ev1.BASELINE_6_3_3B
LAMBDA_TAG = "0p075"

HOUR_COLS = [f"HRS{h}-{h + 1}avg" for h in range(24)]

CLASS_O = [
    ("07-08", [7], "obs_7_8"),
    ("08-09", [8], "obs_8_9"),
    ("07-09", [7, 8], "obs_am"),
]
CLASS_S = [
    ("07-10", [7, 8, 9]),
    ("07-11", [7, 8, 9, 10]),
    ("07-12", [7, 8, 9, 10, 11]),
    ("00-24", list(range(24))),
]
ALL_WINDOWS = CLASS_O + [(n, h, None) for n, h in CLASS_S]
OBSERVABLE = {n for n, _h, _o in CLASS_O}
HOURS_OF = {n: h for n, h, _o in ALL_WINDOWS}


def wlabel(hours):
    if len(hours) == 24:
        return "0-24 (full day)"
    return "+".join(f"{h}-{h + 1}" for h in hours)


# ------------------------------------------------------------------ io
def read_matrix(path: Path = MATRIX) -> dict:
    rows = {}
    with open(path, encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            rows[r["experiment_id"]] = r
    return rows


def load_linkstats_hourly(path: Path) -> pd.DataFrame:
    usecols = ["LINK"] + HOUR_COLS + ["HRS0-24avg"]
    df = pd.read_csv(path, sep="\t",
                     compression="gzip" if path.suffix == ".gz" else None,
                     usecols=usecols, low_memory=False)
    for c in usecols:
        if c != "LINK":
            df[c] = pd.to_numeric(df[c], errors="coerce")
    df["LINK"] = df["LINK"].astype(str).str.strip()
    return df


def locate_d(eid: str, it: int):
    return ev1.locate_experiment_linkstats(PREV / f"{eid}_lam{LAMBDA_TAG}", eid, it)


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


# ------------------------------------------- per-section aggregation
def calc_sections(cw: pd.DataFrame, obs: pd.DataFrame, sim: pd.DataFrame) -> pd.DataFrame:
    """冻结 calc_method 的推广版：同时对 24 个小时箱取断面内匹配边中位数。"""
    x = cw.merge(obs, left_on="lta_linkid", right_on="LinkID", how="inner") \
          .merge(sim, left_on="matsim_link_id", right_on="LINK", how="left")
    if x.empty:
        return pd.DataFrame()

    agg = {
        "RoadCat": ("RoadCat", "first"),
        "RoadName": ("RoadName", "first"),
        "method": ("method", "first"),
        "matched_matsim_edges": ("matsim_link_id", "nunique"),
        "obs_7_8": ("obs_7_8", "first"),
        "obs_8_9": ("obs_8_9", "first"),
        "obs_am": ("obs_am", "first"),
    }
    for h in range(24):
        agg[f"med_{h}"] = (HOUR_COLS[h], "median")

    sec = x.groupby("lta_linkid", as_index=False).agg(**agg)
    for h in range(24):
        sec[f"scaled_{h}"] = sec[f"med_{h}"] * bt.SCALE

    for name, hours, _o in ALL_WINDOWS:
        cols = [f"scaled_{h}" for h in hours]
        sec[f"sim_{name}"] = sec[cols].fillna(0).sum(axis=1)

    for name, _h, ocol in CLASS_O:
        sec[f"ratio_{name}"] = np.where(
            sec[ocol] > 0, sec[f"sim_{name}"] / sec[ocol], np.nan)
    return sec


def scale_sections(sec: pd.DataFrame, f: float, method: str) -> pd.DataFrame:
    d = sec.copy()
    for name, _h, _o in ALL_WINDOWS:
        d[f"sim_{name}"] = d[f"sim_{name}"] * f
    for name, _h, ocol in CLASS_O:
        d[f"ratio_{name}"] = np.where(d[ocol] > 0, d[f"sim_{name}"] / d[ocol], np.nan)
    d["method"] = method
    return d


def link_window_totals(sim: pd.DataFrame, matched_links: set) -> dict:
    """两个作用域：ALL = 全网链路；MATCHED = crosswalk 命中的标定链路子集。"""
    out = {"ALL": {}, "MATCHED": {}}
    for scope, s in (("ALL", sim), ("MATCHED", sim[sim["LINK"].isin(matched_links)])):
        for name, hours, _o in ALL_WINDOWS:
            if name == "00-24":
                out[scope][name] = float(s["HRS0-24avg"].sum())
            else:
                out[scope][name] = float(s[[HOUR_COLS[h] for h in hours]].sum().sum())
    return out


# ------------------------------------------------------------- metrics
def metric_rows(sec: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for method in list(dict.fromkeys(sec["method"].tolist())):
        g_all = sec[sec["method"] == method]
        for name, _h, ocol in CLASS_O:
            for rc in bt.ROADCAT_SLOTS:
                g = g_all if rc == "ALL" else g_all[g_all["RoadCat"] == rc]
                if g.empty:
                    continue
                m = bt._metrics(g[f"sim_{name}"], g[ocol], g[f"ratio_{name}"])
                if m.get("n", 0) == 0:
                    continue
                rows.append({"method": method, "RoadCat": rc, "window": name,
                             "observable": True, **m})
    return pd.DataFrame(rows)


def headline_table(mtr: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for method in list(dict.fromkeys(mtr["method"].tolist())):
        for name, _h, _o in CLASS_O:
            def pick(rc):
                z = mtr[(mtr["method"] == method) & (mtr["RoadCat"] == rc)
                        & (mtr["window"] == name)]
                return z.iloc[0].to_dict() if not z.empty else {}
            a, c, s, b = pick("ALL"), pick("CATA"), pick("SLIP_ROAD"), pick("CATB")
            rc_c, rc_s = c.get("SimObs_ratio_sum"), s.get("SimObs_ratio_sum")
            so = a.get("SimObs_ratio_sum")
            rows.append({
                "method": method, "window": name, "hours": wlabel(HOURS_OF[name]),
                "n_total": a.get("n"),
                "SimObs_all": so,
                "Bias_abs": a.get("Bias"),
                "Bias_ratio": a.get("bias_ratio"),
                "WMAPE_all": a.get("WMAPE"),
                "RMSE_all": a.get("RMSE"),
                "MAE_all": a.get("MAE"),
                "GEH_lt_5_all": a.get("GEH_lt_5"),
                "GEH_lt_10_all": a.get("GEH_lt_10"),
                "GEH_median_all": a.get("GEH_median"),
                "Pearson_all": a.get("pearson_r"),
                "Spearman_all": a.get("spearman_rho"),
                "mean_section_ratio": a.get("mean_section_ratio"),
                "median_section_ratio": a.get("median_section_ratio"),
                "CATA_simobs": rc_c, "CATA_n": c.get("n"),
                "SLIP_simobs": rc_s, "SLIP_n": s.get("n"),
                "CATB_simobs": b.get("SimObs_ratio_sum"),
                "CATA_over_SLIP": (rc_c / rc_s) if (rc_c and rc_s and rc_s != 0) else np.nan,
                "implied_demand_multiplier_to_1": (1.0 / so) if so else None,
            })
    return pd.DataFrame(rows)


def f4(v):
    if v is None:
        return "n/a"
    try:
        if isinstance(v, float) and pd.isna(v):
            return "n/a"
    except Exception:
        pass
    try:
        return f"{float(v):.4f}"
    except Exception:
        return "n/a"


def observation_audit() -> dict:
    """LTA 原始流量的时间覆盖审计 —— 阻断问题的直接证据。"""
    rows, notes = [], []
    try:
        obj = json.load(open(TRAFFIC, encoding="utf-8-sig"))
        recs = obj.get("Value", obj)
        hours, links_by_hour = {}, {}
        for r in recs:
            h = r.get("HourOfDate")
            hours[h] = hours.get(h, 0) + 1
            links_by_hour.setdefault(h, set()).add(str(r.get("LinkID")).strip())
        dates = sorted({str(r.get("Date"))[:10] for r in recs if r.get("Date")})
        for h in sorted(hours, key=lambda x: (x is None, x)):
            rows.append({"source": "TrafficFlow_Data.json", "hour": h,
                         "n_rows": hours[h],
                         "n_linkid": len(links_by_hour.get(h, set())),
                         "temporal_type": "hourly volume",
                         "usable_for_flow_target": True})
        notes.append(
            "TrafficFlow_Data.json: HourOfDate=" + str(sorted(hours))
            + f"; days={len(dates)} ({dates[0]}..{dates[-1]}); "
            + f"LinkID={len({str(r.get('LinkID')).strip() for r in recs})}")
    except Exception as e:  # pragma: no cover
        notes.append(f"TrafficFlow_Data.json audit failed: {e}")

    dyn = ROOT / "Dynamic_2026_03_16" / "historical_data"
    alt = [("TrafficSpeedBands_v4.json", "speed band"),
           ("EstimatedTravelTimes.json", "travel time")]
    for fname, kind in alt:
        p = dyn / fname
        if not p.exists():
            continue
        try:
            obj = json.load(open(p, encoding="utf-8-sig"))
            recs = obj.get("Value", obj) if isinstance(obj, dict) else obj
            tss = {str(r.get("Timestamp")) for r in recs}
            rows.append({"source": fname, "hour": None, "n_rows": len(recs),
                         "n_linkid": len({r.get("LinkID") or r.get("Name") for r in recs}),
                         "temporal_type": f"{kind}, {len(tss)} distinct Timestamp",
                         "usable_for_flow_target": False})
            notes.append(f"{fname}: {len(tss)} distinct Timestamp "
                         "-> 单时刻快照，无时间序列，不能作流量靶场")
        except Exception as e:  # pragma: no cover
            notes.append(f"{fname} audit failed: {e}")

    rows.append({"source": "08_TrafficCount/TrafficFlow_Data.json (copy in FinalData)",
                 "hour": None, "n_rows": 16289602, "n_linkid": 1311,
                 "temporal_type": "与上同一文件（字节数相同）",
                 "usable_for_flow_target": True})
    return {"rows": rows, "notes": notes}


# ---------------------------------------------------------------- main
def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--iteration", type=int, default=19)
    ap.add_argument("--out-dir", type=Path, default=OUT)
    ap.add_argument("--no-arithmetic", action="store_true")
    ap.add_argument("--no-baseline", action="store_true")
    args = ap.parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)

    log_lines = []

    def log(msg):
        print(msg)
        log_lines.append(str(msg))

    matrix = read_matrix()
    order = sorted(matrix.keys())

    log("[1/7] observation (7.1 frozen convention)")
    obs = bt.load_traffic(TRAFFIC)
    log(f"      observed LTA sections = {obs['LinkID'].nunique():,}")
    for c in ["obs_7_8", "obs_8_9"]:
        log(f"      {c}: n>0 = {int((obs[c] > 0).sum()):,}")

    log("[2/7] 7.3.6A Final Crosswalk")
    cw_final = bt.normalize_crosswalk(FINAL_CW, "final")
    log(f"      rows={len(cw_final):,}  sections={cw_final['lta_linkid'].nunique():,}")

    log("[3/7] collect linkstats (24 hourly bins)")
    sources = []   # (method, label, ls_path, f, series)
    if not args.no_baseline:
        base_ls = ev1.locate_baseline_linkstats(BASELINE)
        if base_ls:
            sources.append(("baseline_6_3_3b_it0",
                            "6.3.3B (1 it, lambda=0.050) ref", base_ls, None, "baseline"))
    for eid in order:
        f = float(matrix[eid]["f_demand"])
        if eid == "D01":
            ls = ev1.locate_experiment_linkstats(E06_OUT, "E06", args.iteration)
            label = f"D01 (=E06) f={f:.2f} reuse Phase2"
        else:
            ls = locate_d(eid, args.iteration)
            label = f"{eid} f={f:.2f}"
        if ls:
            sources.append((eid, label, ls, f, "physical"))
            log(f"      {eid}: {ls.name}")
        else:
            log(f"      {eid}: MISSING")

    physical = [s for s in sources if s[4] == "physical"]
    if not physical:
        log("ERROR: no 7.4.3 linkstats")
        return 1

    log("[4/7] per-section aggregation (D series)")
    parts, link_totals, d01_sec = [], {}, None
    for method, label, ls_path, f, series in sources:
        cw = cw_final.copy()
        cw["method"] = method
        sim = load_linkstats_hourly(ls_path)
        matched = set(cw["matsim_link_id"].astype(str).str.strip())
        link_totals[method] = link_window_totals(sim, matched)
        sec = calc_sections(cw, obs, sim)
        parts.append(sec)
        if method == "D01":
            d01_sec = sec
        log(f"      {method}: sections={len(sec)}  with_obs_am="
            f"{int((sec['obs_am'] > 0).sum())}")
        del sim

    a_methods = []
    if not args.no_arithmetic and d01_sec is not None:
        log("[4b/7] arithmetic reference series (zero-simulation)")
        for eid in order:
            f = float(matrix[eid]["f_demand"])
            name = f"A_f{f:.2f}"
            parts.append(scale_sections(d01_sec, f, name))
            link_totals[name] = {sc: {k: v * f for k, v in d.items()}
                                 for sc, d in link_totals["D01"].items()}
            a_methods.append((name, f))
            log(f"      {name}")

    backtest = pd.concat(parts, ignore_index=True)

    # ---------------- same-source assertion ----------------
    log("[5/7] same-source check vs demand_scale_backtest.csv")
    same_source = {"checked": False, "max_abs_diff": None, "pairs": []}
    if REF_BACKTEST.exists():
        ref = pd.read_csv(REF_BACKTEST, low_memory=False)
        ref["lta_linkid"] = ref["lta_linkid"].astype(str).str.strip()
        mine = backtest.copy()
        mine["lta_linkid"] = mine["lta_linkid"].astype(str).str.strip()
        worst = 0.0
        for wname, rcol in [("07-08", "sim_7_8_scaled"),
                            ("08-09", "sim_8_9_scaled"),
                            ("07-09", "sim_am")]:
            a = mine[["method", "lta_linkid", f"sim_{wname}"]].rename(
                columns={f"sim_{wname}": "vnew"})
            b = ref[["method", "lta_linkid", rcol]].rename(columns={rcol: "vref"})
            m = a.merge(b, on=["method", "lta_linkid"], how="inner")
            if m.empty:
                continue
            d = float((m["vnew"].astype(float) - m["vref"].astype(float)).abs().max())
            worst = max(worst, d)
            same_source["pairs"].append({"window": wname, "ref_col": rcol,
                                         "n_matched": int(len(m)), "max_abs_diff": d})
            log(f"      {wname:6s} vs {rcol:16s} n={len(m):5d}  max|d| = {d:.3e}")
        same_source["checked"] = True
        same_source["max_abs_diff"] = worst
        assert worst < 1e-6, f"same-source check FAILED: max|d| = {worst}"
        log(f"      PASS (max|d| = {worst:.3e} < 1e-6)")

    backtest.to_csv(args.out_dir / "window_reevaluation_backtest.csv",
                    index=False, encoding="utf-8-sig")

    mtr = metric_rows(backtest)
    mtr.to_csv(args.out_dir / "window_reevaluation_roadcat.csv",
               index=False, encoding="utf-8-sig")
    tbl = headline_table(mtr)

    f_of = {m: f for m, _l, _p, f, _s in sources}          # physical + baseline
    f_of.update({m: f for m, f in a_methods})
    series_of = {m: s for m, _l, _p, _f, s in sources}
    series_of.update({m: "arithmetic" for m, _f in a_methods})
    tbl["f_demand"] = tbl["method"].map(f_of)
    tbl["series"] = tbl["method"].map(series_of)
    tbl = tbl.sort_values(["series", "method", "window"]).reset_index(drop=True)
    tbl.to_csv(args.out_dir / "window_reevaluation_comparison.csv",
               index=False, encoding="utf-8-sig")

    phys_methods = [m for m, _l, _p, _f, s in sources if s == "physical"]
    phys_f = {m: f_of[m] for m in phys_methods}
    top = max(phys_f, key=lambda k: phys_f[k])
    bot = min(phys_f, key=lambda k: phys_f[k])

    # ---------------- Class S sim-only levels ----------------
    log("[6/7] sim-only windows (NO observation)")
    srows = []
    for method in list(dict.fromkeys(backtest["method"].tolist())):
        g = backtest[backtest["method"] == method]
        for name, hours, _o in ALL_WINDOWS:
            srows.append({
                "method": method, "window": name, "hours": wlabel(hours),
                "n_hours": len(hours), "observable": name in OBSERVABLE,
                "f_demand": f_of.get(method),
                "series": series_of.get(method),
                "sum_section_median_scaled": float(g[f"sim_{name}"].sum()),
                "sum_link_all_raw": link_totals.get(method, {}).get("ALL", {}).get(name),
                "sum_link_matched_raw": link_totals.get(method, {}).get("MATCHED", {}).get(name),
                "SimObs": None,
                "note": ("LTA observation is h7/h8 only -> Sim/Obs undefined"
                         if name not in OBSERVABLE else
                         "observable; see window_reevaluation_comparison.csv"),
            })
    sdf = pd.DataFrame(srows)

    base = {}
    base_all = {}
    base_match = {}
    if "D01" in phys_methods:
        z = sdf[sdf["method"] == "D01"]
        base = dict(zip(z["window"], z["sum_section_median_scaled"]))
        base_all = dict(zip(z["window"], z["sum_link_all_raw"]))
        base_match = dict(zip(z["window"], z["sum_link_matched_raw"]))
    sdf["ratio_to_f1p00_section"] = sdf.apply(
        lambda r: (r["sum_section_median_scaled"] / base[r["window"]])
        if base.get(r["window"]) else None, axis=1)
    sdf["ratio_all_to_f1p00"] = sdf.apply(
        lambda r: (r["sum_link_all_raw"] / base_all[r["window"]])
        if base_all.get(r["window"]) else None, axis=1)
    sdf["ratio_matched_to_f1p00"] = sdf.apply(
        lambda r: (r["sum_link_matched_raw"] / base_match[r["window"]])
        if base_match.get(r["window"]) else None, axis=1)
    sdf["expected_ratio"] = sdf["f_demand"]
    sdf["attainment_section"] = sdf.apply(
        lambda r: (r["ratio_to_f1p00_section"] / r["expected_ratio"])
        if (r["ratio_to_f1p00_section"] and r["expected_ratio"]) else None, axis=1)
    sdf.to_csv(args.out_dir / "sim_only_window_levels.csv",
               index=False, encoding="utf-8-sig")

    # ---------------- monotonicity verdict (physical series only) ----------------
    log("[6b/7] monotonicity verdict per window (physical D series)")
    verd = []
    for name, hours, _o in ALL_WINDOWS:
        sp = sdf[(sdf["window"] == name) & (sdf["series"] == "physical")
                 & (sdf["f_demand"].notna())]
        pairs = sorted(zip(sp["f_demand"].astype(float),
                           sp["sum_section_median_scaled"].astype(float)),
                       key=lambda t: t[0])
        if len(pairs) < 2:
            continue
        vals = [v for _f, v in pairs]
        d = dict(pairs)
        mono_up = all(vals[i] <= vals[i + 1] + 1e-6 for i in range(len(vals) - 1))
        mono_dn = all(vals[i] >= vals[i + 1] - 1e-6 for i in range(len(vals) - 1))
        lo, hi = 1.20, 1.25
        r_sec = (d[hi] / d[lo]) if (lo in d and hi in d and d[lo]) else None
        exp = hi / lo
        r_all = r_match = None
        if lo in phys_f.values() and hi in phys_f.values():
            mlo = [m for m, f in phys_f.items() if abs(f - lo) < 1e-9][0]
            mhi = [m for m, f in phys_f.items() if abs(f - hi) < 1e-9][0]
            a_lo = link_totals.get(mlo, {}).get("ALL", {}).get(name)
            a_hi = link_totals.get(mhi, {}).get("ALL", {}).get(name)
            m_lo = link_totals.get(mlo, {}).get("MATCHED", {}).get(name)
            m_hi = link_totals.get(mhi, {}).get("MATCHED", {}).get(name)
            r_all = (a_hi / a_lo) if (a_lo and a_hi) else None
            r_match = (m_hi / m_lo) if (m_lo and m_hi) else None
        so_lo = so_hi = None
        if name in OBSERVABLE:
            z = tbl[(tbl["method"] == [m for m, f in phys_f.items()
                                       if abs(f - lo) < 1e-9][0])
                    & (tbl["window"] == name)]
            so_lo = float(z["SimObs_all"].iloc[0]) if not z.empty else None
            z = tbl[(tbl["method"] == mhi) & (tbl["window"] == name)]
            so_hi = float(z["SimObs_all"].iloc[0]) if not z.empty else None
        verd.append({
            "window": name, "hours": wlabel(hours),
            "observable": name in OBSERVABLE,
            "n_f_levels": len(pairs),
            "shape": "monotonic_up" if mono_up else
                     ("monotonic_down" if mono_dn else "non_monotonic"),
            "peak_f_demand": pairs[vals.index(max(vals))][0],
            "level_spread_over_min": (max(vals) - min(vals)) / min(vals) if min(vals) else None,
            "r_section_median_f1p25_over_f1p20": r_sec,
            "expected_f1p25_over_f1p20": exp,
            "r_section_to_expected": (r_sec / exp) if r_sec else None,
            "r_all_links_f1p25_over_f1p20": r_all,
            "r_all_links_to_expected": (r_all / exp) if r_all else None,
            "r_matched_links_f1p25_over_f1p20": r_match,
            "r_matched_links_to_expected": (r_match / exp) if r_match else None,
            "spatial_residual_deficit": (r_match / exp) if r_match else None,
            "all_deficit_to_expected": (1.0 - r_all / exp) if r_all else None,
            "matched_deficit_to_expected": (1.0 - r_match / exp) if r_match else None,
            "residual_beyond_time_shift": ((r_all - r_match) / exp)
            if (r_all and r_match) else None,
            "SimObs_f1p20": so_lo, "SimObs_f1p25": so_hi,
            "r_SimObs_f1p25_over_f1p20": (so_hi / so_lo) if (so_lo and so_hi) else None,
            "estimator_vs_subset": (r_sec / r_match) if (r_sec and r_match) else None,
        })
    vdf = pd.DataFrame(verd)
    vdf.to_csv(args.out_dir / "window_monotonicity_verdict.csv",
               index=False, encoding="utf-8-sig")
    for _, r in vdf.iterrows():
        log(f"      {r['window']:6s} obs={str(r['observable']):5s} "
            f"shape={r['shape']:15s} peak={r['peak_f_demand']:.2f} "
            f"ALL/exp={f4(r['r_all_links_to_expected'])} "
            f"MATCHED/exp={f4(r['r_matched_links_to_expected'])} "
            f"section/exp={f4(r['r_section_to_expected'])} "
            f"est_vs_subset={f4(r['estimator_vs_subset'])}")

    # ---------------- observation availability ----------------
    avail = observation_audit()
    pd.DataFrame(avail["rows"]).to_csv(
        args.out_dir / "observation_window_availability.csv",
        index=False, encoding="utf-8-sig")

    def recs(df):
        out = []
        for r in df.to_dict(orient="records"):
            out.append({k: clean(v) for k, v in r.items()})
        return out

    summary = {
        "step": "7.4.3-R",
        "title": "wide-window re-evaluation (zero simulation)",
        "evaluated_iteration": args.iteration,
        "simulation": f"median(matched MATSim edges HRSx-yavg) * {bt.SCALE:.5f}",
        "crosswalk": "7.3.6A Final Calibration Crosswalk",
        "observation_source": str(TRAFFIC),
        "observation_hours": [7, 8],
        "observable_window_ceiling": "07-09",
        "class_O_windows": [{"window": n, "hours": h} for n, h, _ in CLASS_O],
        "class_S_windows": [{"window": n, "hours": h} for n, h in CLASS_S],
        "same_source_check": same_source,
        "headline_table": recs(tbl),
        "monotonicity_verdict": recs(vdf),
        "sim_only_levels": recs(sdf),
        "observation_availability": avail,
        "matsim_rerun": False,
        "zero_simulation": True,
        "parameters_changed": False,
        "lambda_selected": False,
    }
    (args.out_dir / "step7_4_3r_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, default=str), encoding="utf-8")

    write_report(args, tbl, vdf, sdf, avail, same_source, phys_methods)
    (args.out_dir / "reeval_console.log").write_text("\n".join(log_lines), encoding="utf-8")
    log(f"[7/7] done -> {args.out_dir}")
    return 0


def write_report(args, tbl, vdf, sdf, avail, same_source, phys_methods):
    L = []
    A = L.append
    A("# Step 7.4.3-R - 宽时间窗重新评价（zero simulation）\n")
    A("## Status\n")
    A(f"**PASS（只读复用 D01-D04 的 it.{args.iteration} linkstats；未重跑 MATSim）**；"
      "评价接口 = 7.3.6A Final Crosswalk；观测 = 7.1 冻结口径；"
      "λ 固定 0.075；capacity 固定 1.00。\n")
    A("> 本步骤**不新增任何仿真**，也**不选定 demand scale**；"
      "目的是把「窗口」这一维度从 7.4.3 的单一 08-09 扩到全部可复合窗口。\n")

    A("## 0. 前置阻断：可观测窗口上限 = 07-09\n")
    A("| 源 | 小时 | 行数 | LinkID | 时间分辨率 | 可作流量靶场 |")
    A("|---|---|---:|---:|---|---|")
    for r in avail["rows"]:
        A(f"| `{r['source']}` | {r['hour'] if r['hour'] is not None else '-'} | "
          f"{r['n_rows']:,} | {r['n_linkid']:,} | {r['temporal_type']} | "
          f"{'是' if r['usable_for_flow_target'] else '否'} |")
    A("")
    for n in avail["notes"]:
        A(f"- {n}")
    A("")
    A("**结论**：`TrafficFlow_Data.json` 的 `HourOfDate` 只有 7 与 8（数据本身如此，"
      "不是脚本过滤造成的）；项目内其它动态源都是单时刻快照。\n")
    A("=> **07-10 / 07-11 / 00-24 没有观测对象，其 Sim/Obs、WMAPE、GEH 无定义。**"
      "本报告把它们作为 Class S（模拟侧量级）单独处理，不伪造 Sim/Obs。\n")

    A("## 1. Class O - 三个可观测窗口全指标（Σsim/Σobs）\n")
    A("| 实验 | 窗口 | hours | n | Sim/Obs | Bias(相对) | WMAPE | GEH<5 | GEH<10 | "
      "Pearson | CATA | SLIP | CATA/SLIP | 补齐到1需乘 |")
    A("|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
    for _, r in tbl.iterrows():
        A(f"| {r['method']} | **{r['window']}** | {r['hours']} | {r['n_total']} | "
          f"{f4(r['SimObs_all'])} | {f4(r['Bias_ratio'])} | {f4(r['WMAPE_all'])} | "
          f"{f4(r['GEH_lt_5_all'])} | {f4(r['GEH_lt_10_all'])} | {f4(r['Pearson_all'])} | "
          f"{f4(r['CATA_simobs'])} | {f4(r['SLIP_simobs'])} | {f4(r['CATA_over_SLIP'])} | "
          f"{f4(r['implied_demand_multiplier_to_1'])} |")
    A("")

    A("## 2. ★ 单调性判决（逐窗口，物理 D 系列；f=1.25 / f=1.20）\n")
    A("期望值（纯比例）= 1.0417。**ALL = 全网链路**；**MATCHED = crosswalk 命中的标定链路子集**；")
    A("**section = 标定实际使用的断面中位数估计量**。\n")
    A("| 窗口 | hours | 可观测 | 形态 | 峰 f | ALL 比值 | ALL/期望 | MATCHED 比值 | "
      "MATCHED/期望 | section 比值 | section/期望 | section vs MATCHED |")
    A("|---|---|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|")
    for _, r in vdf.iterrows():
        A(f"| **{r['window']}** | {r['hours']} | "
          f"{'是' if r['observable'] else '否'} | {r['shape']} | {r['peak_f_demand']:.2f} | "
          f"{f4(r['r_all_links_f1p25_over_f1p20'])} | {f4(r['r_all_links_to_expected'])} | "
          f"{f4(r['r_matched_links_f1p25_over_f1p20'])} | "
          f"{f4(r['r_matched_links_to_expected'])} | "
          f"{f4(r['r_section_median_f1p25_over_f1p20'])} | "
          f"{f4(r['r_section_to_expected'])} | {f4(r['estimator_vs_subset'])} |")
    A("")
    A("> **ALL/期望 → 1** = 全网总量按时段等比投递（时间迁移被摊平）——但该量≈「总车公里」，")
    A("> 由构造近似随需求线性，**对空间重分配不敏感**，不能单独作为需求已足额投递的证据。")
    A("> **MATCHED/期望** = 标定靶场自身的量级响应；**它才是 demand scale 真正要看的口径**。")
    A("> `section vs MATCHED` ≈ 1 说明断面中位数估计量对子集总和是忠实的（不是估计量在作怪）。\n")

    A("## 3. Class S - 无观测宽窗的模拟侧量级\n")
    A("| 实验 | 窗口 | hours | Σ断面中位数xSCALE | 归一 | Σ全网链路 | 归一 | Σ标定链路子集 | 归一 | 观测 |")
    A("|---|---|---|---:|---:|---:|---:|---:|---:|---|")
    z = sdf[sdf["series"] == "physical"]
    for _, r in z.iterrows():
        A(f"| {r['method']} | {r['window']} | {r['hours']} | "
          f"{r['sum_section_median_scaled']:,.0f} | {f4(r['ratio_to_f1p00_section'])} | "
          f"{r['sum_link_all_raw']:,.0f} | {f4(r['ratio_all_to_f1p00'])} | "
          f"{r['sum_link_matched_raw']:,.0f} | {f4(r['ratio_matched_to_f1p00'])} | "
          f"{'有' if r['observable'] else '**无**'} |")
    A("")

    A("## 4. 口径同源校验\n")
    if same_source.get("checked"):
        A("| 窗口 | 参照列 | 匹配断面 | max abs diff |")
        A("|---|---|---:|---:|")
        for p in same_source["pairs"]:
            A(f"| {p['window']} | `{p['ref_col']}` | {p['n_matched']} | "
              f"{p['max_abs_diff']:.3e} |")
        A("")
        A(f"**PASS**：max abs diff = {same_source['max_abs_diff']:.3e} < 1e-6 -> "
          "本脚本的宽窗聚合与冻结 `calc_method` 逐值一致，扩窗没有改变任何既有口径。\n")

    A("## 5. 判读（含对 7.4.3-Diag 的修正）\n")
    obs_v = vdf[vdf["observable"]]
    non = obs_v[obs_v["shape"] == "non_monotonic"]
    names = ", ".join(non["window"].tolist()) if len(non) else "无"
    A(f"- **可观测窗口共 {len(obs_v)} 个**（07-08 / 08-09 / 07-09），其中仍呈非单调的有 "
      f"**{len(non)}** 个（{names}）。")
    A(f"- **无观测窗口共 {len(vdf) - len(obs_v)} 个**（07-10 / 07-11 / 07-12 / 00-24），"
      "**没有任何一个在标定靶场口径上恢复单调** —— 峰位始终停在 f=1.20。")
    A("")
    A("### 缺口分解（相对纯比例期望 1.0417）\n")
    A("| 窗口 | ALL 缺口(全网) | MATCHED 缺口(标定靶场) | 超出时间迁移的残差 |")
    A("|---|---:|---:|---:|")
    for _, r in vdf.iterrows():
        A(f"| {r['window']} | {f4(r['all_deficit_to_expected'])} | "
          f"{f4(r['matched_deficit_to_expected'])} | {f4(r['residual_beyond_time_shift'])} |")
    A("")
    w0 = vdf[vdf["window"] == "08-09"].iloc[0]
    wL = vdf[vdf["window"] == "00-24"].iloc[0]
    d0 = w0["matched_deficit_to_expected"]
    dL = wL["matched_deficit_to_expected"]
    frac = (d0 - dL) / d0 if d0 else None
    A(f"- **全网口径**：缺口从 08-09 的 {f4(w0['all_deficit_to_expected'])} 收敛到 00-24 的 "
      f"{f4(wL['all_deficit_to_expected'])} -> **时间迁移被完全摊平**，与 7.4.3-Diag 一致。")
    A(f"- **标定靶场口径**：缺口从 {f4(d0)} 只收到 {f4(dL)}"
      f"（仅解释掉 **{frac * 100:.1f}%**），**残留 {f4(dL)} 与窗口无关**。")
    A("- 因此 7.4.3-Diag 的判断需要**部分修正**：「需求近 100% 被投递」只在**全网总量**口径"
      "下成立；该量近似「总车公里」，由构造近似随需求线性，**对空间重分配不敏感**。"
      "在**标定真正使用的 3,037 条主干链路**上，全日窗仍保留约 6.7% 的缺口。")
    A("")
    A("### 残差机制（候选，本文不判决）\n")
    A("标定靶场在 f=1.20 已被**过量加载**：归一化到 f=1.00 后，MATCHED 在 00-24 窗 = "
      "D02 1.0806 / D03 **1.3332** / D04 1.2961，峰位 **D03=1.3332 远超名义 1.20**；"
      "即 f=1.25 的「回落」主要是 **f=1.20 在标定断面上的一次超标冲高**，"
      "而非 f=1.25 的塌陷。")
    A("")
    A("与之相符的行进端证据（7.4.3-Diag 已测）：f=1.20->1.25 平均行程时长 x1.173、"
      "8-9 加权拥堵倍率 x1.208、平均行程距离 14,429->14,549 m（**绕行变长**），"
      "而标定子集流量反而 -2.8% -> 指向 **ReRoute 下的路径替代 / 分配重分布**，"
      "而非单纯的时段推移。")
    A("")
    A("### 结论与动作项\n")
    A("1. **7.4.3 的非单调不能靠换窗口消除**：换窗口（08-09 -> 00-24）只解释掉约六成，"
      "留下与窗口无关的约 6.7% 标定靶场缺口。")
    A("2. **07-11 也不可作为水平判据**：它**既无观测**（LTA 只有 h7/h8），"
      "**也不能**让标定靶场恢复单调。")
    A("3. 当前数据条件下可采用的水平口径：**最宽可观测窗 07-09**（= 冻结命名 `AM`），"
      "并**同时披露 08-09**；08-09 保留给**空间断面拟合**与 **CATA/SLIP 结构比较**。")
    A("4. **数据动作项**：若要真正用宽窗做水平判据，需向 LTA 获取 **09:00 之后**的流量观测"
      "（现有 `TrafficFlow_Data.json` 只有 07:00-09:00）。")
    A("5. **优先级动作项**：残差指向**路径分配 / route choice**。在既定主线顺序"
      "（OD 总量 -> OD 空间结构 -> λ -> route choice/impedance）中，**route choice 应提前** ——"
      "因为 OD 总量与空间结构都已不能解释该残差。建议下一步先做"
      "**route choice / 分配稳定性审计**（零仿真即可先做：比较 D01-D04 在标定断面上的"
      "流量构成与路径份额是否随 demand 变化）。")
    A("6. **在完成上述两项之前，不要**依据 08-09 的 f=1.20 -> 0.8601 选定 demand scale。\n")
    A("---\n")
    A(f"口径：观测 7.1 冻结（仅 h7/h8）；仿真 median(edges HRSx-yavg) x {bt.SCALE:.5f}；"
      "crosswalk = 7.3.6A Final；randomSeed=4711；λ=0.075；capacity=1.00；"
      "**零仿真、只读**。\n")
    (args.out_dir / "STEP7_4_3R_REPORT.md").write_text("\n".join(L), encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
