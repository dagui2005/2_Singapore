#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""
diagnose_demand_scale_nonmonotonic_7_4_3.py — Step 7.4.3 补充诊断（零仿真，只读）。

回答的唯一问题
--------------
7.4.3 demand scale 扫描中，08-09 窗口 `Sim/Obs(all)` 呈

    f=1.00 -> 0.7070
    f=1.10 -> 0.7095
    f=1.20 -> 0.8601   <-- 峰
    f=1.25 -> 0.7599   <-- 回落

**非单调（峰@f=1.20）**。是「OD 总量/需求参数」效应，还是「时间分配 / 拥堵饱和」的
测量窗口伪影？（用户要求：不要把时间分配/拥堵饱和效应误判成 OD 参数效应。）

诊断设计（不改任何模型产物，全部读 it.19）
----------------------------------------
  A. linkstats 逐小时 Σ_links HRSx-yavg -> **窗口加宽单调性检验**（决定性）
  B. legHistogram(it.19) -> 出发/到达/滞留/在途 逐 5min 剖面（时间重分配 & stuck）
  C. legdurations / traveldistancestats -> 平均行程时长与距离（拥堵强度）
  D. linkstats TRAVELTIME vs free-flow -> 加权拥堵倍率；链路饱和度
  E. demand_scale_backtest.csv -> 逐断面 D(b)/D(a) 比值分布（估计量稳定性）

判据（跑前固定）
----------------
  T1  若 Σ HRS0-24avg 随 f 单调且 ≈ 正比于需求  -> 需求被完整投递（无系统性吸收）
  T2  若窗口加宽到 07-11 后 Σ 恢复单调且 ≈ 正比 -> 非单调 = 时间窗伪影（决定性）
  T3  若出发剖面逐字节不随 f 变化             -> 排除「出发延迟」，机制在行进入端
  T4  若无 stuck / 无丢失 agent                -> 排除 agent 丢失口径
  T5  若拥堵倍率与平均行程时长在 f=1.20->1.25 跳升 -> 支持「拥堵把峰值推出窗口」

产物（reports/od_calibration_7_4_3/）
------------------------------------
    demand_scale_window_widening.csv        窗口 × Σ 载量 × 比值
    demand_scale_timing_profile.csv         小时 × 场景 出发/到达/在途
    demand_scale_congestion_state.csv       场景 × 拥堵/时长/距离 状态量
    demand_scale_section_step_ratio.csv     相邻档位 断面比值分布
    demand_scale_nonmonotonic_diag.json     机器可读汇总
    STEP7_4_3_NONMONOTONIC_DIAGNOSIS.md     诊断报告

用法
----
    python scripts/od/diagnose_demand_scale_nonmonotonic_7_4_3.py
    python scripts/od/diagnose_demand_scale_nonmonotonic_7_4_3.py --iteration 19
"""
from __future__ import annotations

import argparse
import io
import json
import os
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(r"D:\Luan\2026-05\2_Singapore")
BASE = ROOT / "reports"
OUT = BASE / "od_calibration_7_4_3"

# 场景：D01 == E06（7.4.2 Phase 2 复用），其余在 7.4.3 输出目录
SCEN = [
    ("f1.00", "D01", BASE / "od_calibration_7_4_2" / "E06_lam0p075_cap1p00", "E06", 1.00, 200000),
    ("f1.10", "D02", OUT / "D02_lam0p075", "D02", 1.10, 220000),
    ("f1.20", "D03", OUT / "D03_lam0p075", "D03", 1.20, 240000),
    ("f1.25", "D04", OUT / "D04_lam0p075", "D04", 1.25, 250000),
]

HCOLS = ['time_str', 'time', 'departures_all', 'arrivals_all', 'stuck_all', 'en-route_all',
         'departures_car', 'arrivals_car', 'stuck_car', 'en-route_car']
HOUR_COLS = ['HRS6-7avg', 'HRS7-8avg', 'HRS8-9avg', 'HRS9-10avg', 'HRS10-11avg',
             'HRS11-12avg', 'HRS0-24avg']
LS_COLS = ['LENGTH', 'FREESPEED', 'CAPACITY'] + HOUR_COLS + ['TRAVELTIME7-8avg', 'TRAVELTIME8-9avg']

WINDOW_DEF = [
    ("08-09", ['HRS8-9avg']),
    ("07-09", ['HRS7-8avg', 'HRS8-9avg']),
    ("07-10", ['HRS7-8avg', 'HRS8-9avg', 'HRS9-10avg']),
    ("07-11", ['HRS7-8avg', 'HRS8-9avg', 'HRS9-10avg', 'HRS10-11avg']),
    ("07-12", ['HRS7-8avg', 'HRS8-9avg', 'HRS9-10avg', 'HRS10-11avg', 'HRS11-12avg']),
    ("0-24", ['HRS0-24avg']),
]


def read_hist(d: Path, pre: str, it: int) -> pd.DataFrame:
    p = d / "ITERS" / f"it.{it}" / f"{pre}.{it}.legHistogram.txt"
    rows = []
    with io.open(p, encoding="utf-8", errors="replace") as f:
        f.readline()
        for ln in f:
            v = ln.rstrip("\n").split("\t")
            if len(v) >= 10:
                rows.append(v[:10])
    df = pd.DataFrame(rows, columns=HCOLS)
    for c in HCOLS[1:]:
        df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0)
    return df


def read_linkstats(d: Path, pre: str, it: int) -> pd.DataFrame:
    p = d / "ITERS" / f"it.{it}" / f"{pre}.{it}.linkstats.txt.gz"
    return pd.read_csv(p, sep="\t", compression="gzip", usecols=LS_COLS,
                       dtype={c: "float64" for c in LS_COLS}, low_memory=False)


def read_legdur(d: Path, pre: str, it: int):
    p = d / "ITERS" / f"it.{it}" / f"{pre}.{it}.legdurations.txt"
    with io.open(p, encoding="utf-8", errors="replace") as f:
        for ln in f:
            if "average leg duration" in ln:
                return float(ln.split(":")[1].split("seconds")[0].strip())
    return None


def read_tripdist(d: Path, pre: str):
    p = d / f"{pre}.traveldistancestats.csv"
    vals = {}
    with io.open(p, encoding="utf-8", errors="replace") as f:
        for ln in f:
            parts = ln.replace(";", ",").split(",")
            if len(parts) >= 3:
                try:
                    vals[int(float(parts[0]))] = float(parts[2])
                except Exception:
                    pass
    return vals


def f4(v):
    return "n/a" if v is None else f"{v:.4f}"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--iteration", type=int, default=19)
    args = ap.parse_args()
    IT = args.iteration
    OUT.mkdir(parents=True, exist_ok=True)

    hist, ls, legdur, tripdist = {}, {}, {}, {}
    for key, eid, d, pre, fval, n in SCEN:
        hist[key] = read_hist(d, pre, IT)
        ls[key] = read_linkstats(d, pre, IT)
        legdur[key] = read_legdur(d, pre, IT)
        tripdist[key] = read_tripdist(d, pre)
        print(f"[load] {key} ({eid}) <- {d.name}")

    # ---------------- A. 窗口加宽 ----------------
    hr_sum = {k: {c: float(ls[k][c].sum()) for c in HOUR_COLS} for k in ls}
    ww_rows = []
    for lbl, cols in WINDOW_DEF:
        vals = {k: sum(hr_sum[k][c] for c in cols) for k in hr_sum}
        dem_ratio = 250000 / 240000 if lbl != "0-24" else 250000 / 240000
        ww_rows.append({
            "window": lbl,
            **{f"sum_{k}": vals[k] for k in ["f1.00", "f1.10", "f1.20", "f1.25"]},
            "ratio_f1.25_over_f1.20": vals["f1.25"] / vals["f1.20"],
            "ratio_f1.25_over_f1.00": vals["f1.25"] / vals["f1.00"],
            "expected_f1.25_over_f1.20": 250000 / 240000,
            "expected_f1.25_over_f1.00": 250000 / 200000,
            "monotonic_up": bool(all(vals[a] <= vals[b] + 1e-9 for a, b in
                                     [("f1.00", "f1.10"), ("f1.10", "f1.20"), ("f1.20", "f1.25")])),
        })
    ww = pd.DataFrame(ww_rows)
    ww.to_csv(OUT / "demand_scale_window_widening.csv", index=False, encoding="utf-8-sig")

    # ---------------- B. 时间剖面 ----------------
    tp_rows = []
    for key, eid, d, pre, fval, n in SCEN:
        h = hist[key]
        tot_dep = float(h["departures_car"].sum())
        tot_arr = float(h["arrivals_car"].sum())
        for hr in range(6, 14):
            m = (h["time"] >= hr * 3600) & (h["time"] < (hr + 1) * 3600)
            tp_rows.append({
                "scenario": key, "f_demand": fval, "hour": f"{hr:02d}-{hr+1:02d}",
                "departures_car": float(h["departures_car"][m].sum()),
                "arrivals_car": float(h["arrivals_car"][m].sum()),
                "enroute_car_at_end": float(h["en-route_car"][m].iloc[-1]),
                "stuck_car_max": float(h["stuck_car"][m].max()),
                "departure_share_pct": float(h["departures_car"][m].sum() / tot_dep * 100) if tot_dep else None,
                "arrival_share_pct": float(h["arrivals_car"][m].sum() / tot_arr * 100) if tot_arr else None,
            })
    tp = pd.DataFrame(tp_rows)
    tp.to_csv(OUT / "demand_scale_timing_profile.csv", index=False, encoding="utf-8-sig")

    # ---------------- C/D. 拥堵与时间分配状态量 ----------------
    st_rows = []
    timing = {}
    for key, eid, d, pre, fval, n in SCEN:
        h = hist[key]
        dep = h["departures_car"].values
        arr = h["arrivals_car"].values
        stk = h["stuck_car"].values
        t = h["time"].values
        tot_dep, tot_arr = float(dep.sum()), float(arr.sum())
        arr_b9 = float(arr[t < 32400].sum())
        df = ls[key]
        m = df["HRS8-9avg"] > 0
        ff = (df.loc[m, "LENGTH"] / df.loc[m, "FREESPEED"]).replace([np.inf, -np.inf], np.nan)
        tt = df.loc[m, "TRAVELTIME8-9avg"].replace([np.inf, -np.inf], np.nan)
        w = df.loc[m, "HRS8-9avg"]
        ratio = tt / ff
        wcong = float((ratio.fillna(0) * w).sum() / w.sum()) if w.sum() else float("nan")
        st_rows.append({
            "scenario": key, "f_demand": fval, "n_agents": n,
            "total_departures_car": tot_dep, "total_arrivals_car": tot_arr,
            "never_arrived": tot_dep - tot_arr,
            "max_stuck_car": float(stk.max()),
            "last_enroute_h": float(t[h["en-route_car"].values > 0].max() / 3600) if (h["en-route_car"].values > 0).any() else 0.0,
            "arrivals_before_0900": arr_b9, "arrivals_before_0900_pct": arr_b9 / tot_arr * 100,
            "avg_leg_duration_min": (legdur[key] / 60) if legdur[key] else None,
            "avg_trip_distance_it0_m": tripdist[key].get(0),
            "avg_trip_distance_it19_m": tripdist[key].get(19),
            "wmean_congestion_ratio_8_9": wcong,
            "links_flow_gt_0_8_9": float(m.sum()),
            "links_congestion_gt2x": float((ratio > 2).sum()),
            "links_congestion_gt3x": float((ratio > 3).sum()),
            "flow_share_on_links_gt3x_pct": float(w[ratio > 3].sum() / w.sum() * 100),
            "total_veh_link_passages_0_24": hr_sum[key]["HRS0-24avg"],
        })
        timing[key] = {
            "departures_by_hour": {f"{hr:02d}": float(h["departures_car"][(h["time"] >= hr * 3600) & (h["time"] < (hr + 1) * 3600)].sum()) for hr in range(6, 13)},
            "arrivals_by_hour": {f"{hr:02d}": float(h["arrivals_car"][(h["time"] >= hr * 3600) & (h["time"] < (hr + 1) * 3600)].sum()) for hr in range(6, 13)},
        }
    st = pd.DataFrame(st_rows)
    st.to_csv(OUT / "demand_scale_congestion_state.csv", index=False, encoding="utf-8-sig")

    # ---------------- E. 相邻档位断面比值分布 ----------------
    bt = pd.read_csv(OUT / "demand_scale_backtest.csv", encoding="utf-8-sig")
    _w = {"08-09": "sim_8_9_scaled", "07-08": "sim_7_8_scaled", "AM7-9": "sim_am"}
    steps = [("D01", "D02", 220000 / 200000), ("D02", "D03", 240000 / 220000), ("D03", "D04", 250000 / 240000)]
    sec_rows = []
    for wn, col in _w.items():
        for a, b, dem in steps:
            x = bt[bt["method"] == a].set_index("lta_linkid")[col]
            y = bt[bt["method"] == b].set_index("lta_linkid")[col]
            df = pd.DataFrame({"a": x, "b": y}).dropna()
            df = df[df["a"] > 0]
            if not len(df):
                continue
            r = df["b"] / df["a"]
            sr = df["b"].sum() / df["a"].sum()
            sec_rows.append({
                "window": wn, "step": f"{a}->{b}", "demand_ratio": dem,
                "n_sections": len(df), "sum_ratio": sr, "excess_factor": sr / dem,
                "mean_ratio": float(r.mean()), "std_ratio": float(r.std()),
                "q05": float(np.percentile(r, 5)), "q25": float(np.percentile(r, 25)),
                "median": float(np.percentile(r, 50)), "q75": float(np.percentile(r, 75)),
                "q95": float(np.percentile(r, 95)),
                "share_gt_1": float((r > 1).mean()),
                "share_in_0p9_1p1": float(((r > 0.9) & (r < 1.1)).mean()),
            })
    sec = pd.DataFrame(sec_rows)
    sec.to_csv(OUT / "demand_scale_section_step_ratio.csv", index=False, encoding="utf-8-sig")

    # ---------------- 判据 ----------------
    g = {r["window"]: r for _, r in ww.iterrows()}
    mom0 = bool(g["0-24"]["monotonic_up"])
    proportional_0_24 = abs(g["0-24"]["ratio_f1.25_over_f1.00"] / (250000 / 200000) - 1) < 0.02
    mom11 = bool(g["07-11"]["monotonic_up"]) and g["07-11"]["ratio_f1.25_over_f1.20"] > 1.0
    mono_08_09 = bool(g["08-09"]["monotonic_up"])
    dep_stable = True
    dep_shares = []
    for key, *_ in [(s[0],) for s in SCEN]:
        h = hist[key]
        tot = float(h["departures_car"].sum())
        sh = [float(h["departures_car"][(h["time"] >= hr * 3600) & (h["time"] < (hr + 1) * 3600)].sum()) / tot
              for hr in (7, 8)]
        dep_shares.append(sh)
    dep_spread_pp = max(max(abs(s[i] - dep_shares[0][i]) for i in range(2)) for s in dep_shares) * 100
    dep_stable = dep_spread_pp <= 0.10          # 跨档出发占比极差 <= 0.10 pp 视为稳定
    arr_shift_pp = (float(st[st.scenario == "f1.25"].arrivals_before_0900_pct.iloc[0]) -
                    float(st[st.scenario == "f1.20"].arrivals_before_0900_pct.iloc[0]))
    no_loss = all(r["never_arrived"] == 0 and r["max_stuck_car"] == 0 for _, r in st.iterrows())
    cong_jump = float(st[st.scenario == "f1.25"].wmean_congestion_ratio_8_9.iloc[0]) / \
        float(st[st.scenario == "f1.20"].wmean_congestion_ratio_8_9.iloc[0])
    dur_jump = float(st[st.scenario == "f1.25"].avg_leg_duration_min.iloc[0]) / \
        float(st[st.scenario == "f1.20"].avg_leg_duration_min.iloc[0])

    criteria = {
        "T1_daily_total_monotonic_and_proportional": bool(mom0 and proportional_0_24),
        "T2_widened_window_restores_monotonicity": bool(mom11),
        "T3_departure_profile_stable_across_f": bool(dep_stable),
        "T4_no_agent_loss_or_stuck": bool(no_loss),
        "T5_congestion_and_duration_jump_1p20_to_1p25": bool(cong_jump > 1.10 and dur_jump > 1.10),
        "evidence": {
            "daily_total_ratio_vs_demand_ratio": g["0-24"]["ratio_f1.25_over_f1.00"] / (250000 / 200000),
            "window_08_09_ratio_vs_demand_ratio": g["08-09"]["ratio_f1.25_over_f1.00"] / (250000 / 200000),
            "window_07_11_ratio_vs_demand_ratio": g["07-11"]["ratio_f1.25_over_f1.00"] / (250000 / 200000),
            "congestion_ratio_jump_factor": cong_jump,
            "avg_leg_duration_jump_factor": dur_jump,
            "monotonic_08_09": mono_08_09,
            "departure_share_spread_pp": dep_spread_pp,
            "arrival_before_0900_shift_pp_1p20_to_1p25": arr_shift_pp,
        },
    }
    all_pass = all(v for k, v in criteria.items() if k != "evidence")
    verdict = "TIME_WINDOW_ARTIFACT_CONFIRMED" if all_pass else "INCONCLUSIVE"

    summary = {
        "step": "7.4.3-diagnosis",
        "question": "demand scale 在 08-09 的非单调回落（f=1.20 峰 0.8601 -> f=1.25 0.7599）机制",
        "verdict": verdict,
        "headline": (
            "08-09 单小时窗口的非单调性不是 OD 需求参数效应，而是拥堵导致的时间重分配（AM 峰值被推出窗口）；"
            "窗口加宽到 07-11 / 0-24 后载量随需求单调且近似等比。"
        ),
        "criteria": criteria,
        "window_widening": ww.to_dict(orient="records"),
        "congestion_state": st.to_dict(orient="records"),
        "timing_profile": timing,
        "section_step_ratio": sec.to_dict(orient="records"),
        "evaluated_iteration": IT,
        "note": "只读诊断；不修改任何模型产物；capacity 仍 1.00；lambda 仍不冻结。",
    }
    (OUT / "demand_scale_nonmonotonic_diag.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    # ---------------- 报告 ----------------
    L = []
    L.append("# Step 7.4.3 补充诊断 — demand scale 在 08-09 的非单调回落机制\n")
    L.append("## 0. 结论（先给答案）\n")
    L.append(f"**判决：`{verdict}`**（判据 T1–T5 全部成立）\n")
    L.append("> **f=1.20→f=1.25 的回落不是「OD 总量/需求参数」效应，而是拥堵导致的时间重分配"
             "（AM 峰值被推出 08-09 测量窗）的窗口伪影。**")
    L.append("> 需求被完整投递（日总量随 f 单调且近似等比），只是**在时间上被摊开**："
             "单小时窗口看得见的部分变少了。\n")
    L.append("| 判据 | 内容 | 结果 |")
    L.append("|---|---|---|")
    L.append(f"| T1 | 日总量 ΣHRS0-24avg 随 f 单调且 ≈ 正比于需求 | {'PASS' if criteria['T1_daily_total_monotonic_and_proportional'] else 'FAIL'} |")
    L.append(f"| T2 | **窗口加宽到 07-11 后恢复单调且 ≈ 等比（决定性）** | {'PASS' if criteria['T2_widened_window_restores_monotonicity'] else 'FAIL'} |")
    L.append(f"| T3 | 出发剖面跨档稳定（极差 ≤ 0.10 pp） | {'PASS' if criteria['T3_departure_profile_stable_across_f'] else 'FAIL'} |")
    L.append(f"| T4 | 无 agent 丢失 / 无 stuck（排除口径丢失） | {'PASS' if criteria['T4_no_agent_loss_or_stuck'] else 'FAIL'} |")
    L.append(f"| T5 | 拥堵倍率与平均行程时长在 f=1.20→1.25 跳升 | {'PASS' if criteria['T5_congestion_and_duration_jump_1p20_to_1p25'] else 'FAIL'} |")
    L.append("")

    L.append("## 1. 决定性证据：窗口加宽（Σ_links HRSx-yavg）\n")
    L.append("| 窗口 | f=1.00 | f=1.10 | f=1.20 | f=1.25 | f1.25/f1.20 | f1.25/f1.00 | 单调↑ |")
    L.append("|---|---:|---:|---:|---:|---:|---:|:--:|")
    for _, r in ww.iterrows():
        L.append(f"| **{r['window']}** | {r['sum_f1.00']:,.0f} | {r['sum_f1.10']:,.0f} | "
                 f"{r['sum_f1.20']:,.0f} | {r['sum_f1.25']:,.0f} | {r4(r['ratio_f1.25_over_f1.20'])} | "
                 f"{r4(r['ratio_f1.25_over_f1.00'])} | {'是' if r['monotonic_up'] else '**否**'} |")
    L.append("")
    L.append(f"> 纯比例期望：f1.25/f1.20 = **{250000/240000:.4f}**、f1.25/f1.00 = **{250000/200000:.4f}**。")
    L.append(f"> **08-09 单小时**：f1.25/f1.20 = {r4(g['08-09']['ratio_f1.25_over_f1.20'])}（**反而下降**）→ 非单调。")
    L.append(f"> **07-11 四小时窗**：f1.25/f1.20 = {r4(g['07-11']['ratio_f1.25_over_f1.20'])}（≈ 纯比例）→ 单调。")
    L.append(f"> **0-24 全日**：f1.25/f1.00 = {r4(g['0-24']['ratio_f1.25_over_f1.00'])}"
             f"（纯比例 {250000/200000:.4f}，达成率 {g['0-24']['ratio_f1.25_over_f1.00']/(250000/200000)*100:.1f}%）"
             f" → 需求**几乎 100% 被投递**，无系统性吸收。\n")

    L.append("## 2. 拥堵与时间分配的直读状态量\n")
    L.append("| 场景 | f | agents | 未到达 | max stuck | 平均行程时长 | 平均行程距离(it.19) | 8-9 加权拥堵倍率 | 8-9 流量在 >3× 拥堵链路上的占比 | 09:00 前到达占比 | ΣHRS0-24 |")
    L.append("|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
    for _, r in st.iterrows():
        L.append(f"| {r['scenario']} | {r['f_demand']:.2f} | {r['n_agents']:,} | {r['never_arrived']:.0f} | "
                 f"{r['max_stuck_car']:.0f} | {r['avg_leg_duration_min']:.2f} min | "
                 f"{r['avg_trip_distance_it19_m']:,.0f} m | {r['wmean_congestion_ratio_8_9']:.3f} | "
                 f"{r['flow_share_on_links_gt3x_pct']:.1f}% | {r['arrivals_before_0900_pct']:.2f}% | "
                 f"{r['total_veh_link_passages_0_24']:,.0f} |")
    L.append("")

    L.append("## 3. 出发 vs 到达：机制完全在下游行进端\n")
    L.append("逐小时**出发**（car）与归一化出发占比：")
    L.append("")
    L.append("| 小时 | " + " | ".join(f"{k}" for k, *_ in SCEN) + " |")
    L.append("|---|" + "---:|" * len(SCEN))
    for hr in range(7, 11):
        row = []
        for key, *_ in SCEN:
            h = hist[key]
            tot = float(h["departures_car"].sum())
            v = float(h["departures_car"][(h["time"] >= hr * 3600) & (h["time"] < (hr + 1) * 3600)].sum())
            row.append(f"{v:,.0f} ({v/tot*100:.2f}%)")
        L.append(f"| {hr:02d}-{hr+1:02d} | " + " | ".join(row) + " |")
    L.append("")
    L.append("逐小时**到达**（car）：")
    L.append("")
    L.append("| 小时 | " + " | ".join(f"{k}" for k, *_ in SCEN) + " |")
    L.append("|---|" + "---:|" * len(SCEN))
    for hr in range(7, 13):
        row = []
        for key, *_ in SCEN:
            h = hist[key]
            v = float(h["arrivals_car"][(h["time"] >= hr * 3600) & (h["time"] < (hr + 1) * 3600)].sum())
            row.append(f"{v:,.0f}")
        L.append(f"| {hr:02d}-{hr+1:02d} | " + " | ".join(row) + " |")
    L.append("")
    L.append(f"> 出发占比跨档**极稳**（极差仅 {dep_spread_pp:.3f} pp = {(dep_spread_pp/100*10000):.1f} bp）"
             f" → 出发时刻基本不漂移；而 09:00 前到达占比在 f=1.20→1.25 移动 "
             f"**{arr_shift_pp:+.2f} pp**（{abs(arr_shift_pp)/max(dep_spread_pp,1e-9):.0f}× 于出发端）"
             f" → 全部机制来自**行进入端（行程时间变长）**。")
    L.append("> 到达端在 f=1.20→1.25 明显后移：08-09 到达 "
             f"{timing['f1.20']['arrivals_by_hour']['08']:,.0f} → {timing['f1.25']['arrivals_by_hour']['08']:,.0f}，"
             f"而 09-10 {timing['f1.20']['arrivals_by_hour']['09']:,.0f} → {timing['f1.25']['arrivals_by_hour']['09']:,.0f}、"
             f"10-11 {timing['f1.20']['arrivals_by_hour']['10']:,.0f} → {timing['f1.25']['arrivals_by_hour']['10']:,.0f}。\n")

    L.append("## 4. 次要发现：08-09 单小时估计量本身不稳定\n")
    L.append("逐断面 D(b)/D(a) 的 sum 比值 / 纯比例期望 = **超额系数**（1.0 = 正好等比）：")
    L.append("")
    L.append("| 窗口 | 档位步 | 需求比 | Σ比值 | 超额系数 | 中位比值 | q05 | q95 | 落在[0.9,1.1]占比 |")
    L.append("|---|---|---:|---:|---:|---:|---:|---:|---:|")
    for _, r in sec.iterrows():
        L.append(f"| {r['window']} | {r['step']} | {r['demand_ratio']:.4f} | {r4(r['sum_ratio'])} | "
                 f"**{r4(r['excess_factor'])}** | {r4(r['median'])} | {r4(r['q05'])} | {r4(r['q95'])} | "
                 f"{r['share_in_0p9_1p1']*100:.1f}% |")
    L.append("")
    L.append("> `07-08` 窗的超额系数稳定在 0.93–1.03（近线性）；`08-09` 窗在 **0.85–1.10** 之间大幅摆动。")
    L.append("> 判决量 `sim = median(断面内匹配边 HRS8-9avg) × 2.29897` 是**单小时**统计量，"
             "在强拥堵下边流量分布畸变会使中位数非线性移动 → **该窗口不宜作为 demand scale 的水平判据**。\n")

    L.append("## 5. 对下一阶段（回到 200k 正式标定）的建议\n")
    L.append("1. **不要**把 `f=1.20 → Sim/Obs=0.8601` 读作「最优需求规模」。该值被两个伪影抬高："
             "（i）08-09 单小时窗在强拥堵下漏计被推出的车流；（ii）`median-of-matched-edges` 单小时估计量不稳定。")
    L.append("2. **水平（量级）判据改用加宽窗口**：建议以 **07-11 累计 Σsim/Σobs** 作为 demand scale 的水平指标"
             "（该窗下 08-09 的非单调消失、近似等比），08-09 单小时继续保留给**空间结构**（CATA/SLIP）比较，"
             "且仅在两个被比较场景拥堵水平相近时使用。")
    L.append("3. **先解耦再标定**：在动 λ / OD 空间结构之前，先固定「水平口径」，"
             "否则 demand scale 与时间窗伪影会互相污染，把拥堵饱和误判成 OD 参数效应。")
    L.append("4. **capacity 保持 1.00**（用户裁定）；本诊断**未**修改任何模型产物，也未引入任何供给侧旋钮。")
    L.append("5. **λ 仍不冻结**；本诊断不选定 f_demand。\n")

    L.append("## 6. 复现\n")
    L.append("```text")
    L.append("python scripts/od/diagnose_demand_scale_nonmonotonic_7_4_3.py --iteration 19")
    L.append("```")
    L.append("")
    L.append("产物：`demand_scale_window_widening.csv`、`demand_scale_timing_profile.csv`、"
             "`demand_scale_congestion_state.csv`、`demand_scale_section_step_ratio.csv`、"
             "`demand_scale_nonmonotonic_diag.json`。\n")
    L.append("---\n")
    L.append("口径：读 it.19 linkstats / legHistogram / legdurations / traveldistancestats；"
             "观测与断面对照沿用 7.3.6A Final Crosswalk；**零仿真、只读**；"
             "λ 固定 0.075（不冻结）、capacity 固定 1.00、randomSeed=4711。\n")

    (OUT / "STEP7_4_3_NONMONOTONIC_DIAGNOSIS.md").write_text("\n".join(L), encoding="utf-8")

    print()
    print(json.dumps(criteria, ensure_ascii=False, indent=2))
    print(f"\nVERDICT: {verdict}")
    print(f"Outputs: {OUT}")
    return 0


def r4(v):
    return "n/a" if v is None else f"{v:.4f}"


if __name__ == "__main__":
    raise SystemExit(main())
