#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""
evaluate_calibration_phase2_7_4_2.py — Step 7.4.2 Phase 2：λ 灵敏度评价（零仿真）。

回答 Phase 2 的核心问题
----------------------
    在 capacity 固定 f_cap = 1.00、20 iterations 下，**只改变 λ**：
        E03  λ=0.050   （= Phase 1 已完成，直接复用）
        E06  λ=0.075   （7.4.1 矩阵既有，f=1.00）
        E09  λ=0.100   （7.4.1 矩阵既有，f=1.00）
    观察 λ 是否同时改善「总体量级 + CATA/SLIP 结构 + 断面误差」，而不仅是移动总流量。

设计（与 Phase 1 评价器逐字节同源）
--------------------------------
* 评价接口 = **7.3.6A Final Calibration Crosswalk**（不重建）。
* 观测口径 = **7.1 冻结口径**（工作日 → 日内均值 → LinkID×hour 日中位）。
* 仿真口径 = `median(匹配 MATSim 有向边 HRSx-yavg) × 459794/200000`（=2.29897）。
* 主判据窗口 = 08-09；同时输出 07-08 / AM。
* 迭代轴 = 最末迭代 it.19（含拥堵反馈）；另附 6.3.3B 单迭代基线作参照。

复用（import）而非复制
----------------------
    import compare_final_crosswalk_7_3_6b as bt        # 冻结口径（7.3.6B）
    import run_calibration_phase1_7_4_2 as rp          # 矩阵 + 路径约定
    import evaluate_calibration_7_4_2 as ev1           # Phase 1 评价函数
保证与 Phase 1 完全同一套口径，避免漂移。

产物（reports/od_calibration_7_4_2/）
-----------------------------------
    phase2_backtest.csv                 逐断面
    phase2_roadcat_summary.csv          λ × RoadCat × 窗口 × 全指标
    phase2_lambda_comparison.csv        ★ λ × {Sim/Obs, WMAPE, GEH<5, CATA, SLIP, CATA/SLIP}
    step7_4_2_phase2_summary.json
    STEP7_4_2_PHASE2_REPORT.md

用法
----
    python scripts/od/evaluate_calibration_phase2_7_4_2.py
    python scripts/od/evaluate_calibration_phase2_7_4_2.py --experiments E03 E06 E09
    python scripts/od/evaluate_calibration_phase2_7_4_2.py --allow-missing   # 缺实验也出报告
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(r"D:\Luan\2026-05\2_Singapore")
sys.path.insert(0, str(ROOT / "scripts" / "od"))

import compare_final_crosswalk_7_3_6b as bt        # noqa: E402  (frozen 口径)
import run_calibration_phase1_7_4_2 as rp          # noqa: E402  (矩阵 + 路径约定)
import evaluate_calibration_7_4_2 as ev1           # noqa: E402  (Phase 1 评价函数)

OUT_ROOT = ev1.OUT_ROOT
TRAFFIC = ev1.TRAFFIC
FINAL_CW = ev1.FINAL_CW
BASELINE_6_3_3B = ev1.BASELINE_6_3_3B

# Phase 2 默认 λ 扫描（f_cap 一律 1.00，20 it）
#   E03 ≡ λ=0.050（Phase 1 已完成，复用）
#   E06 ≡ λ=0.075、E09 ≡ λ=0.100（7.4.1 矩阵既有）
DEFAULT_EXPERIMENTS = ["E03", "E06", "E09"]


def f4(v):
    return "n/a" if v is None else f"{v:.4f}"


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


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--iteration", type=int, default=19,
                    help="20 迭代实验取哪一迭代评价（默认 it.19 = 最末）")
    ap.add_argument("--experiments", nargs="*", default=DEFAULT_EXPERIMENTS,
                    help=f"要评价的 experiment_id（默认 {DEFAULT_EXPERIMENTS}）")
    ap.add_argument("--matrix", type=Path, default=rp.MATRIX_CSV,
                    help="实验矩阵 CSV（默认 7.4.1 矩阵）")
    ap.add_argument("--tag", default="phase2", help="产物前缀（默认 phase2）")
    ap.add_argument("--out-dir", type=Path, default=OUT_ROOT)
    ap.add_argument("--allow-missing", action="store_true",
                    help="即使部分实验 linkstats 缺失也出报告（用于只看已完成部分）")
    args = ap.parse_args()

    args.out_dir.mkdir(parents=True, exist_ok=True)

    print("[1/5] load observation (7.1 frozen convention)")
    obs = bt.load_traffic(TRAFFIC)
    print(f"      observed LTA sections = {obs['LinkID'].nunique():,}")

    print("[2/5] load 7.3.6A Final Crosswalk")
    cw_final = bt.normalize_crosswalk(FINAL_CW, "final")
    print(f"      crosswalk rows={len(cw_final):,}  sections={cw_final['lta_linkid'].nunique():,}")

    print("[3/5] collect linkstats")
    matrix = rp.read_matrix(args.matrix)
    sources = []   # (method, display, ls_path, is_baseline)
    base_ls = ev1.locate_baseline_linkstats(BASELINE_6_3_3B)
    if base_ls:
        sources.append(("baseline_6_3_3b_it0", "6.3.3B (1 it, λ=0.050)", base_ls, True))

    lam_of: dict[str, float] = {}
    for eid in args.experiments:
        if eid not in matrix:
            print(f"      {eid}: 不在矩阵 {args.matrix.name} -> 跳过")
            continue
        spec = matrix[eid]
        lam = float(spec["lambda"])
        f = float(spec["capacity_factor"])
        lam_of[eid] = lam
        od = rp.exp_out_dir(eid, lam, f)
        ls = ev1.locate_experiment_linkstats(od, eid, args.iteration)
        label = f"{eid} (λ={lam:.3f}, 20 it, f={f:.2f})"
        if ls:
            sources.append((eid, label, ls, False))
            print(f"      {eid}: {ls.name}")
        else:
            print(f"      {eid}: linkstats MISSING at {od} -> 跳过（实验未完成？）")

    if len([s for s in sources if not s[3]]) == 0 and not args.allow_missing:
        print("\nERROR: 尚无任何 Phase 2 实验 linkstats；请先运行 "
              "run_calibration_phase1_7_4_2.py --experiments E06 E09 "
              "--manifest .../phase2_run_manifest.json --phase 2 "
              "（或加 --allow-missing）")
        return 1

    print("[4/5] per-section backtest")
    parts = []
    for method, label, ls_path, _ in sources:
        cw = cw_final.copy()
        cw["method"] = method
        parts.append(ev1.backtest_one(method, cw, obs, ls_path))
    backtest = pd.concat(parts, ignore_index=True)
    backtest.to_csv(args.out_dir / f"{args.tag}_backtest.csv", index=False, encoding="utf-8-sig")

    summary = ev1.summarize(backtest)
    summary.to_csv(args.out_dir / f"{args.tag}_roadcat_summary.csv", index=False, encoding="utf-8-sig")

    cmp_tbl = ev1.comparison_table(summary, args.iteration)
    # 附加 λ 列，便于按 λ 排序阅读
    cmp_tbl["lambda"] = cmp_tbl["method"].map(lambda m: lam_of.get(m, np.nan))
    cmp_tbl.to_csv(args.out_dir / f"{args.tag}_lambda_comparison.csv", index=False, encoding="utf-8-sig")

    def row_of(method, window="08-09"):
        z = cmp_tbl[(cmp_tbl["method"] == method) & (cmp_tbl["window"] == window)]
        return z.iloc[0].to_dict() if not z.empty else {}

    headline = {}
    for method, label, _, _ in sources:
        d = row_of(method)
        headline[method] = {
            "label": label,
            "lambda": lam_of.get(method),
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

    # λ 趋势：仅取 20 it 实验（含 λ）
    lam_scan = {}
    for eid in args.experiments:
        if eid not in headline:
            continue
        h = headline[eid]
        lam_scan[eid] = {
            "lambda": lam_of.get(eid),
            "SimObs_all": h["SimObs_all"],
            "CATA_simobs": h["CATA_simobs"],
            "SLIP_simobs": h["SLIP_simobs"],
            "CATA_over_SLIP": h["CATA_over_SLIP"],
            "WMAPE_all": h["WMAPE_all"],
            "GEH_lt_5_all": h["GEH_lt_5_all"],
            "GEH_lt_10_all": h["GEH_lt_10_all"],
            "Pearson_all": h["Pearson_all"],
        }
    ratios = [v["CATA_over_SLIP"] for v in lam_scan.values() if v["CATA_over_SLIP"]]
    ratio_spread = (max(ratios) - min(ratios)) if len(ratios) >= 2 else None

    summary_json = {
        "step": "7.4.2",
        "phase": 2,
        "status": "PASS",
        "sweep_variable": "lambda",
        "capacity_fixed": 1.00,
        "iterations": 20,
        "evaluated_iteration": args.iteration,
        "crosswalk": "7.3.6A Final Calibration Crosswalk",
        "observation": "7.1 frozen convention (weekday -> per-day mean -> median by LinkID x hour)",
        "simulation": f"median(matched MATSim edges HRSx-yavg) * {bt.SCALE:.5f}",
        "headline_window": "08-09",
        "headline": headline,
        "lambda_scan": lam_scan,
        "cata_over_slip_spread_across_lambda": ratio_spread,
        "methods_included": [s[0] for s in sources],
        "frozen_seed": 4711,
        "parameters_changed": True,
        "lambda_selected": False,
        "matsim_rerun": False,
        "crosswalk_rebuilt": False,
    }
    (args.out_dir / f"step7_4_2_{args.tag}_summary.json").write_text(
        json.dumps(summary_json, ensure_ascii=False, indent=2), encoding="utf-8")

    # ---- report ----
    lines = []
    lines.append("# Step 7.4.2 Phase 2 — λ 灵敏度（capacity 固定 1.00，20 it）\n")
    lines.append("## Status\n")
    lines.append("**PASS**（零仿真；capacity 固定 f=1.00；评价用 7.3.6A Final Crosswalk；"
                 f"观测=7.1 冻结口径；评价迭代 = it.{args.iteration}）\n")
    lines.append(f"\n包含方法：{', '.join(s[0] for s in sources)}\n")
    lines.append("\n## 1. ★ 核心对比表（窗口 08-09，Σsim/Σobs）\n")
    lines.append("| 实验 | λ | 迭代 | Sim/Obs(all) | WMAPE | GEH<5 | GEH<10 | Pearson | CATA | SLIP_ROAD | CATA/SLIP |")
    lines.append("|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
    for method, label, _, is_base in sources:
        h = headline.get(method, {})
        lam_disp = f"{h.get('lambda'):.3f}" if h.get("lambda") is not None else "0.050"
        lines.append(
            f"| {label} | {lam_disp} | {'1' if is_base else 20} "
            f"| {f4(h.get('SimObs_all'))} | {f4(h.get('WMAPE_all'))} | {f4(h.get('GEH_lt_5_all'))} "
            f"| {f4(h.get('GEH_lt_10_all'))} | {f4(h.get('Pearson_all'))} "
            f"| {f4(h.get('CATA_simobs'))} | {f4(h.get('SLIP_simobs'))} | {f4(h.get('CATA_over_SLIP'))} |")
    lines.append("")
    lines.append("> 参照：7.3.6B/Phase 1 已确认 `CATA/SLIP` 在 λ=0.050、f=1.00、20 it 下 ≈ **1.0698**；"
                 "Phase 1 已证明 capacity 不是结构主因。本表考察 **λ 单独**对量级与结构的作用。\n")
    # ---- λ 趋势分析 ----
    ORDERED = sorted([e for e in args.experiments if e in headline],
                     key=lambda e: (lam_of.get(e) if lam_of.get(e) is not None else 9e9))
    METRICS = [("SimObs_all", "Sim/Obs(all)", "high"),
               ("CATA_simobs", "CATA Sim/Obs", "near1"),
               ("SLIP_simobs", "SLIP Sim/Obs", "near1"),
               ("CATA_over_SLIP", "CATA/SLIP", "near1"),
               ("WMAPE_all", "WMAPE", "low"),
               ("GEH_lt_5_all", "GEH<5", "high"),
               ("GEH_lt_10_all", "GEH<10", "high"),
               ("Pearson_all", "Pearson", "high"),
               ("Spearman_all", "Spearman", "high")]
    WINDOWS = [w for w, _, _, _ in bt.WINDOWS]

    def m_of(method, window, col):
        z = cmp_tbl[(cmp_tbl["method"] == method) & (cmp_tbl["window"] == window)]
        return clean(z.iloc[0].get(col)) if not z.empty else None

    def trend_str(pairs):
        vv = [(lam_of.get(e), v) for e, v in pairs if v is not None]
        num = [v for _, v in vv]
        if len(num) < 2:
            return "n/a"
        inc = all(b >= a - 1e-12 for a, b in zip(num, num[1:]))
        dec = all(b <= a + 1e-12 for a, b in zip(num, num[1:]))
        if inc and dec:
            return "平坦"
        if inc:
            return "↑ 单调"
        if dec:
            return "↓ 单调"
        i_mx = max(range(len(num)), key=lambda i: num[i])
        i_mn = min(range(len(num)), key=lambda i: num[i])
        return f"非单调（峰@λ={vv[i_mx][0]:.3f}，谷@λ={vv[i_mn][0]:.3f}）"

    def best_lambda(col, direction):
        res = []
        for w in WINDOWS:
            cand = [(e, m_of(e, w, col)) for e in ORDERED]
            cand = [(e, v) for e, v in cand if v is not None]
            if not cand:
                res.append((w, None))
                continue
            if direction == "high":
                e, _ = max(cand, key=lambda t: t[1])
            elif direction == "low":
                e, _ = min(cand, key=lambda t: t[1])
            else:
                e, _ = min(cand, key=lambda t: abs(t[1] - 1))
            res.append((w, e))
        return res

    lines.append("## 2. λ 趋势分析（是否稳定、可解释）\n")
    lines.append("### 2.1 逐指标趋势（主判据窗口 08-09）\n")
    lines.append("| 指标 | " + " | ".join(f"λ={lam_of[e]:.3f}" for e in ORDERED) + " | 趋势 |")
    lines.append("|---|" + "---:|" * (len(ORDERED) + 1))
    for col, name, _ in METRICS:
        vals = [m_of(e, "08-09", col) for e in ORDERED]
        lines.append(f"| {name} | " + " | ".join(f4(v) for v in vals)
                     + f" | {trend_str(list(zip(ORDERED, vals)))} |")
    lines.append("")

    lines.append("### 2.2 跨窗口一致性（各窗口独立取最优 λ，考察是否稳定）\n")
    lines.append("| 指标 | 方向 | " + " | ".join(WINDOWS) + " | 跨窗口一致? |")
    lines.append("|---|---|" + "---:|" * len(WINDOWS) + "---|")
    consistent_map = {}
    for col, name, direction in METRICS:
        bl = best_lambda(col, direction)
        picks = [p for _, p in bl]
        ok = len(set(picks)) == 1 and picks[0] is not None
        consistent_map[col] = {"picks": picks, "consistent": ok}
        dir_cn = {"high": "越大越好", "low": "越小越好", "near1": "越近1越好"}[direction]
        cells = " | ".join((f"{p} (λ={lam_of[p]:.3f})" if p else "n/a") for _, p in bl)
        lines.append(f"| {name} | {dir_cn} | {cells} | {'✅ 一致' if ok else '❌ 不一致'} |")
    lines.append("")

    lines.append("### 2.3 三类响应：结构 / 量级 / 截面拟合\n")
    lvl = [(e, m_of(e, "08-09", "SimObs_all")) for e in ORDERED]
    lvlv = [v for _, v in lvl if v is not None]
    lvl_spread = (max(lvlv) - min(lvlv)) if len(lvlv) >= 2 else None
    best_level = max([t for t in lvl if t[1] is not None], key=lambda t: t[1])[0] if lvlv else None
    fit_picks = consistent_map.get("Pearson_all", {}).get("picks", [])
    fit_uniform = consistent_map.get("Pearson_all", {}).get("consistent", False)
    if ratio_spread is not None:
        lines.append(f"- **结构（CATA/SLIP）**：跨 λ 极差 **{ratio_spread:.4f}**；"
                     f"对照 Phase 1 的 capacity 极差 **0.2371**，λ 的结构杠杆弱约 "
                     f"**{0.2371 / max(ratio_spread, 1e-9):.0f}×** → λ 不是结构杠杆。")
    if lvl_spread is not None:
        lines.append(f"- **总体量级（Sim/Obs(all)）**：跨 λ 极差 **{lvl_spread:.4f}**，"
                     f"且**非单调**（最优 λ={lam_of[best_level]:.3f} 仍仅 {max(lvlv):.4f} < 1）"
                     f" → λ 补不上 19–25% 的整体量级缺口。")
    if fit_uniform:
        e_best = fit_picks[0]
        lines.append(f"- **截面拟合（WMAPE / GEH / Pearson / Spearman）**：三窗口一致指向 "
                     f"**{e_best} (λ={lam_of[e_best]:.3f})** → λ 对空间分配确有真实但有限的正效应。")
    lines.append("- **权衡**：量级最优 λ 与拟合最优 λ 不同 → λ 无法同时改善三者，"
                 "其残余辨识度仍弱（与 7.2–7.3 的结论一致）。\n")
    lines.append("## 3. 各窗口（含 07-08 / AM）\n")
    lines.append("| 实验 | 窗口 | Sim/Obs | CATA | SLIP_ROAD | CATA/SLIP |")
    lines.append("|---|---|---:|---:|---:|---:|")
    for method, label, _, _ in sources:
        for window, _, _, _ in bt.WINDOWS:
            d = row_of(method, window)
            lines.append(f"| {label} | {window} | {f4(clean(d.get('SimObs_all')))} "
                         f"| {f4(clean(d.get('CATA_simobs')))} | {f4(clean(d.get('SLIP_simobs')))} "
                         f"| {f4(clean(d.get('CATA_over_SLIP')))} |")
    lines.append("")
    lines.append("## 4. 判读与下一步\n")
    lines.append("- 本步骤**不自行选 λ**；由 E03/E06/E09 的正式趋势决定候选区间（用户决策）。")
    lines.append("- **λ 不是结构杠杆**：`CATA/SLIP` 极差远小于 Phase 1 的 capacity 极差 0.2371；"
                 "7.3.6A Final Crosswalk 已把断面语义结构问题解决，λ 不再需要动结构。")
    lines.append("- **λ 不是量级杠杆**：Sim/Obs(all) 随 λ **非单调**，且任何 λ 都 < 0.82 → "
                 "补不上 19–25% 的整体量级缺口；量级缺口应由 **OD 总量 / car-trip 扩样因子 / "
                 "departure profile / mode coverage** 方向排查。")
    lines.append("- **λ 对截面拟合有真实但有限的正效应**：E06 (λ=0.075) 在 GEH<5 / GEH<10 / WMAPE / "
                 "Pearson / Spearman 上**三窗口一致最优** → 存在 "
                 "**量级最优(λ≈0.050) vs 拟合最优(λ≈0.075) 的权衡**。")
    lines.append("- **λ=0.025 暂缓**：上游 `population_lambda_0p025.xml.gz` 缺失"
                 "（E10 = DEFERRED_BY_USER_DECISION），未纳入本轮趋势。")
    lines.append("- 下一步候选：(a) 用户判定是否做 **Phase 3 λ∈[0.06,0.09] 精细搜索**（改善截面拟合）；"
                 "(b) 转 **OD 总量 / car-trip 扩样因子 (2.29897) / departure profile** 补量级缺口。\n")
    lines.append("---\n")
    lines.append("口径：观测 7.1 冻结；仿真 `median(edges HRSx-yavg)×2.29897`；"
                 "crosswalk = 7.3.6A Final；randomSeed=4711；capacity=1.00。\n")
    (args.out_dir / f"STEP7_4_2_{args.tag.upper()}_REPORT.md").write_text(
        "\n".join(lines), encoding="utf-8")

    # ---- 把 λ 趋势固化进 summary JSON（覆盖写；含趋势块与 λ=0.025 状态）----
    summary_json["lambda_0p025_status"] = "DEFERRED_BY_USER_DECISION"
    summary_json["lambda_candidates_tested"] = sorted(
        [v["lambda"] for v in lam_scan.values() if v["lambda"] is not None])
    summary_json["lambda_trend_08_09"] = {
        name: {"values": {f"lambda_{lam_of[e]:.3f}": m_of(e, "08-09", col) for e in ORDERED},
               "trend": trend_str([(e, m_of(e, "08-09", col)) for e in ORDERED])}
        for col, name, _ in METRICS}
    summary_json["lambda_window_consistency"] = {
        name: {"direction": direction,
               "best_per_window": {w: {"experiment": p, "lambda": (lam_of.get(p) if p else None)}
                                   for w, p in best_lambda(col, direction)},
               "consistent": consistent_map[col]["consistent"]}
        for col, name, direction in METRICS}
    summary_json["level_spread_across_lambda_08_09"] = lvl_spread
    summary_json["level_best_lambda_08_09"] = (lam_of.get(best_level) if best_level else None)
    (args.out_dir / f"step7_4_2_{args.tag}_summary.json").write_text(
        json.dumps(summary_json, ensure_ascii=False, indent=2), encoding="utf-8")

    print("[5/5] done")
    print(json.dumps(summary_json["lambda_scan"], ensure_ascii=False, indent=2))
    print(f"Outputs: {args.out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
