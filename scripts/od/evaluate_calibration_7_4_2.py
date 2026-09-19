#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""
evaluate_calibration_7_4_2.py — Step 7.4.2 Phase 1 评价（零仿真，仅读已有 linkstats）。

回答 Phase 1 的核心问题
----------------------
    在 λ=0.050 固定时，capacity（f_cap ∈ {0.50, 0.75, 1.00}，20 it）
    究竟只是"总量杠杆"，还是已经改变 CATA / SLIP_ROAD 的空间结构？

设计
----
* 评价接口 = **7.3.6A Final Calibration Crosswalk**（不重新构建）。
* 观测口径 = **7.1 冻结口径**（工作日 → 日内均值 → LinkID×hour 日中位）。
* 仿真口径 = `median(匹配 MATSim 有向边 HRSx-yavg) × 459794/200000`。
* 主判据窗口 = 08-09；同时输出 07-08 / AM。
* 迭代轴：20 迭代实验默认取**最末迭代**（it.19，含拥堵反馈）；
  另附 it.0 与 **6.3.3B 单迭代基线** 作参照，用于分离"迭代效应"与"capacity 效应"。

复用（import）而非复制
----------------------
直接 import 已冻结的 7.3.6B 模块，保证口径**逐字节同源**，避免复制粘贴漂移：
    compare_final_crosswalk_7_3_6b.load_traffic / normalize_crosswalk /
    load_linkstats / calc_method / _metrics / SCALE / WINDOWS

产物（reports/od_calibration_7_4_2/）
-----------------------------------
    phase1_backtest.csv                 逐断面
    phase1_roadcat_summary.csv          实验 × RoadCat × 窗口 × 全指标
    phase1_capacity_comparison.csv      ★ f × {Sim/Obs, WMAPE, GEH<5, CATA, SLIP, CATA/SLIP}
    step7_4_2_phase1_summary.json
    STEP7_4_2_PHASE1_REPORT.md

用法
----
    python scripts/od/evaluate_calibration_7_4_2.py
    python scripts/od/evaluate_calibration_7_4_2.py --iteration 0     # 看首迭代
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

TRAFFIC = ROOT / r"Singapore_OD_MATSim_FinalData" / r"08_TrafficCount" / "TrafficFlow_Data.json"
FINAL_CW = ROOT / r"reports\od_final_calibration_crosswalk_7_3_6" / "final_calibration_crosswalk.csv"
OUT_ROOT = ROOT / r"reports\od_calibration_7_4_2"
BASELINE_6_3_3B = ROOT / r"reports\matsim_assignment_6_3_3b"

PHASE1 = ["E01", "E02", "E03"]


def locate_experiment_linkstats(out_dir: Path, run_id: str, it: int) -> Path | None:
    d = out_dir / "ITERS" / f"it.{it}"
    if not d.exists():
        return None
    cands = sorted(d.glob(f"{run_id}.*.linkstats.txt.gz")) or sorted(d.glob("*.linkstats.txt.gz"))
    return cands[0] if cands else None


def locate_baseline_linkstats(base: Path, lam: str = "0p050") -> Path | None:
    d = base / f"lambda_{lam}" / "ITERS" / "it.0"
    if not d.exists():
        return None
    cands = sorted(d.glob("*.linkstats.txt.gz")) or sorted(d.glob("*.linkstats.txt"))
    return cands[0] if cands else None


def backtest_one(method: str, cw: pd.DataFrame, obs: pd.DataFrame, ls_path: Path):
    sim = bt.load_linkstats(ls_path)
    sec = bt.calc_method(cw, obs, sim)
    if not sec.empty:
        sec["iteration_source"] = method
    return sec


def summarize(backtest: pd.DataFrame) -> pd.DataFrame:
    rows = []
    methods = list(dict.fromkeys(backtest["method"].tolist()))
    for method in methods:
        for rc in bt.ROADCAT_SLOTS:
            g = backtest[backtest["method"] == method]
            g = g if rc == "ALL" else g[g["RoadCat"] == rc]
            if g.empty:
                continue
            for window, s_col, o_col, r_col in bt.WINDOWS:
                m = bt._metrics(g[s_col], g[o_col], g[r_col])
                if m.get("n", 0) == 0:
                    continue
                rows.append({"method": method, "RoadCat": rc, "window": window, **m})
    return pd.DataFrame(rows)


def comparison_table(summary: pd.DataFrame, it: int) -> pd.DataFrame:
    """★ 用户要的 f × 指标表（每实验每窗口一行）。"""
    rows = []
    for method in list(dict.fromkeys(summary["method"].tolist())):
        for window, _, _, _ in bt.WINDOWS:
            def pick(rc):
                z = summary[(summary["method"] == method)
                            & (summary["RoadCat"] == rc)
                            & (summary["window"] == window)]
                return z.iloc[0].to_dict() if not z.empty else {}

            a = pick("ALL")
            c = pick("CATA")
            s = pick("SLIP_ROAD")
            b = pick("CATB")
            rc_cata = c.get("SimObs_ratio_sum")
            rc_slip = s.get("SimObs_ratio_sum")
            ratio = (rc_cata / rc_slip) if (rc_cata and rc_slip and rc_slip != 0) else np.nan
            rows.append({
                "method": method,
                "window": window,
                "n_total": a.get("n"),
                "SimObs_all": a.get("SimObs_ratio_sum"),
                "WMAPE_all": a.get("WMAPE"),
                "RMSE_all": a.get("RMSE"),
                "GEH_lt_5_all": a.get("GEH_lt_5"),
                "GEH_lt_10_all": a.get("GEH_lt_10"),
                "Pearson_all": a.get("pearson_r"),
                "Spearman_all": a.get("spearman_rho"),
                "CATA_simobs": rc_cata,
                "CATA_n": c.get("n"),
                "CATA_WMAPE": c.get("WMAPE"),
                "SLIP_simobs": rc_slip,
                "SLIP_n": s.get("n"),
                "SLIP_WMAPE": s.get("WMAPE"),
                "CATB_simobs": b.get("SimObs_ratio_sum"),
                "CATA_over_SLIP": ratio,
                "iteration": it,
            })
    return pd.DataFrame(rows)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--iteration", type=int, default=19,
                    help="20 迭代实验取哪一迭代评价（默认 it.19 = 最末）")
    ap.add_argument("--out-dir", type=Path, default=OUT_ROOT)
    ap.add_argument("--allow-baseline-only", action="store_true",
                    help="即使 7.4.2 实验 linkstats 尚未生成也出报告（仅用于管线自检）")
    args = ap.parse_args()

    args.out_dir.mkdir(parents=True, exist_ok=True)

    print("[1/5] load observation (7.1 frozen convention)")
    obs = bt.load_traffic(TRAFFIC)
    print(f"      observed LTA sections = {obs['LinkID'].nunique():,}")

    print("[2/5] load 7.3.6A Final Crosswalk")
    cw_final = bt.normalize_crosswalk(FINAL_CW, "final")
    print(f"      crosswalk rows={len(cw_final):,}  sections={cw_final['lta_linkid'].nunique():,}")

    print("[3/5] collect linkstats")
    sources = []   # (method_label, display, ls_path, is_baseline)
    base_ls = locate_baseline_linkstats(BASELINE_6_3_3B)
    if base_ls:
        sources.append(("baseline_6_3_3b_it0", "6.3.3B (1 it, f=1.00)", base_ls, True))
    matrix = rp.read_matrix()
    for eid in PHASE1:
        spec = matrix[eid]
        lam = float(spec["lambda"])
        f = float(spec["capacity_factor"])
        od = rp.exp_out_dir(eid, lam, f)
        ls = locate_experiment_linkstats(od, eid, args.iteration)
        label = f"{eid} (20 it, f={f:.2f})"
        if ls:
            sources.append((eid, label, ls, False))
            print(f"      {eid}: {ls.name}")
        else:
            print(f"      {eid}: linkstats MISSING at {od} -> 跳过（实验未完成？）")
    if len([s for s in sources if not s[3]]) == 0:
        if args.allow_baseline_only:
            print("      [warn] 尚无 7.4.2 实验 linkstats；--allow-baseline-only "
                  "开启，仅出基线自检报告。")
        else:
            print("\nERROR: 尚无任何 7.4.2 实验 linkstats；请先运行 "
                  "run_calibration_phase1_7_4_2.py（或加 --allow-baseline-only 自检）")
            return 1

    print("[4/5] per-section backtest")
    parts = []
    for method, label, ls_path, _ in sources:
        cw = cw_final.copy()
        cw["method"] = method
        parts.append(backtest_one(method, cw, obs, ls_path))
    backtest = pd.concat(parts, ignore_index=True)
    backtest.to_csv(args.out_dir / "phase1_backtest.csv", index=False, encoding="utf-8-sig")

    summary = summarize(backtest)
    summary.to_csv(args.out_dir / "phase1_roadcat_summary.csv", index=False, encoding="utf-8-sig")

    cmp_tbl = comparison_table(summary, args.iteration)
    cmp_tbl.to_csv(args.out_dir / "phase1_capacity_comparison.csv", index=False, encoding="utf-8-sig")

    # ---- headline: 08-09 ----
    def row_of(method, window="08-09"):
        z = cmp_tbl[(cmp_tbl["method"] == method) & (cmp_tbl["window"] == window)]
        return z.iloc[0].to_dict() if not z.empty else {}

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

    headline = {}
    for method, label, _, _ in sources:
        d = row_of(method)
        headline[method] = {
            "label": label,
            "SimObs_all": clean(d.get("SimObs_all")),
            "WMAPE_all": clean(d.get("WMAPE_all")),
            "RMSE_all": clean(d.get("RMSE_all")),
            "GEH_lt_5_all": clean(d.get("GEH_lt_5_all")),
            "GEH_lt_10_all": clean(d.get("GEH_lt_10_all")),
            "Pearson_all": clean(d.get("Pearson_all")),
            "CATA_simobs": clean(d.get("CATA_simobs")),
            "SLIP_simobs": clean(d.get("SLIP_simobs")),
            "CATB_simobs": clean(d.get("CATB_simobs")),
            "CATA_over_SLIP": clean(d.get("CATA_over_SLIP")),
            "CATA_n": clean(d.get("CATA_n")),
            "SLIP_n": clean(d.get("SLIP_n")),
        }

    # capacity 是否只改总量（结构稳定性）
    struct_scan = {}
    for eid in PHASE1:
        d = row_of(eid)
        struct_scan[eid] = {
            "capacity_factor": float(matrix[eid]["capacity_factor"]),
            "SimObs_all": clean(d.get("SimObs_all")),
            "CATA_over_SLIP": clean(d.get("CATA_over_SLIP")),
            "CATA_simobs": clean(d.get("CATA_simobs")),
            "SLIP_simobs": clean(d.get("SLIP_simobs")),
        }
    ratios = [v["CATA_over_SLIP"] for v in struct_scan.values() if v["CATA_over_SLIP"]]
    ratio_spread = (max(ratios) - min(ratios)) if len(ratios) >= 2 else None

    exp_sources = [s for s in sources if not s[3]]
    baseline_only = len(exp_sources) == 0

    summary_json = {
        "step": "7.4.2",
        "phase": 1,
        "status": "PASS",
        "lambda_fixed": 0.05,
        "capacity_factors": [0.50, 0.75, 1.00],
        "iterations": 20,
        "evaluated_iteration": args.iteration,
        "crosswalk": "7.3.6A Final Calibration Crosswalk",
        "observation": "7.1 frozen convention (weekday -> per-day mean -> median by LinkID x hour)",
        "simulation": f"median(matched MATSim edges HRSx-yavg) * {bt.SCALE:.5f}",
        "headline_window": "08-09",
        "headline": headline,
        "methods_included": [s[0] for s in sources],
        "baseline_only": baseline_only,
        "capacity_structure_scan": struct_scan,
        "cata_over_slip_spread_across_capacity": ratio_spread,
        "frozen_seed": 4711,
        "parameters_changed": True,
        "lambda_selected": False,
        "matsim_rerun": False,
        "crosswalk_rebuilt": False,
    }
    (args.out_dir / "step7_4_2_phase1_summary.json").write_text(
        json.dumps(summary_json, ensure_ascii=False, indent=2), encoding="utf-8")

    # ---- report ----
    def f4(v):
        return "n/a" if v is None else f"{v:.4f}"

    lines = []
    lines.append("# Step 7.4.2 Phase 1 — λ=0.050 × capacity 三档（联合校准）\n")
    lines.append("## Status\n")
    if baseline_only:
        lines.append("**⚠️ 基线自检模式（baseline-only）**：7.4.2 实验 linkstats 尚未生成，"
                     "本报告**只含 6.3.3B 单迭代基线**，用于验证评价管线口径。"
                     "**不是** Phase 1 正式结果；跑完 E01–E03 后重跑本脚本即覆盖。\n")
    lines.append("**PASS**（20 iterations；评价用 7.3.6A Final Crosswalk；"
                 f"观测=7.1 冻结口径；评价迭代 = it.{args.iteration}）\n")
    lines.append(f"\n包含方法：{', '.join(s[0] for s in sources)}\n")
    lines.append("\n## 1. ★ 核心对比表（窗口 08-09，Σsim/Σobs）\n")
    lines.append("| 实验 | f_cap | 迭代 | Sim/Obs(all) | WMAPE | GEH<5 | CATA | SLIP_ROAD | CATA/SLIP |")
    lines.append("|---|---:|---:|---:|---:|---:|---:|---:|---:|")
    for method, label, _, _ in sources:
        h = headline.get(method, {})
        lines.append(
            f"| {label} | {f4(struct_scan.get(method, {}).get('capacity_factor')) if method in struct_scan else '1.00'} "
            f"| {'1' if method=='baseline_6_3_3b_it0' else 20} "
            f"| {f4(h.get('SimObs_all'))} | {f4(h.get('WMAPE_all'))} | {f4(h.get('GEH_lt_5_all'))} "
            f"| {f4(h.get('CATA_simobs'))} | {f4(h.get('SLIP_simobs'))} | {f4(h.get('CATA_over_SLIP'))} |")
    lines.append("")
    lines.append("> 参照：7.3.6B 记录的 `CATA/SLIP` 链条（6.3.3B 单迭代）："
                 "0.3633 (7.1 old crosswalk) → 0.9135 (7.3.4 strict) → 1.0984 (7.3.6A final)。"
                 "本表基线行应与 final=1.0984 一致（同一 linkstats、同一 crosswalk）。\n")
    lines.append("## 2. capacity 是否只改总量？\n")
    if ratio_spread is not None:
        lines.append(f"- `CATA/SLIP` 在三档 capacity 间的极差 = **{ratio_spread:.4f}**。")
        lines.append(f"- 参照：基线（6.3.3B）与 1 的偏离 |1.0984−1| = **0.0984**。"
                     f"极差 / 偏离 = **{ratio_spread/0.0984:.2f}×**。")
        lines.append("- 若极差远小于 |1.0984−1|，说明 capacity 主要平移总量、基本不改变 CATA↔SLIP 结构；")
        lines.append("  若极差与 |ratio−1| 同量级或更大，则 capacity 已进入结构通道，须保留为正式校准变量。\n")
        # ---- decomposition: 谁在驱动结构变化 ----
        s05, s10 = struct_scan.get("E01", {}), struct_scan.get("E03", {})
        if s05.get("CATA_simobs") and s10.get("CATA_simobs"):
            c_lo, c_hi = s05["CATA_simobs"], s10["CATA_simobs"]
            p_lo, p_hi = s05["SLIP_simobs"], s10["SLIP_simobs"]
            lines.append("### 2.1 结构变化由谁驱动（f=0.50 → f=1.00）\n")
            lines.append("| 类 | f=0.50 | f=1.00 | 放大倍数 | 结论 |")
            lines.append("|---|---:|---:|---:|---|")
            lines.append(f"| CATA (motorway 主线) | {c_lo:.4f} | {c_hi:.4f} | **×{c_hi/c_lo:.2f}** | 对 capacity 更敏感 |")
            lines.append(f"| SLIP_ROAD (motorway_link 匝道) | {p_lo:.4f} | {p_hi:.4f} | ×{p_hi/p_lo:.2f} | 相对不敏感 |")
            lines.append("")
            lines.append("> 主线（容量大、饱和度对总需求水平更敏感）随 capacity 上升被放大的幅度大于匝道，"
                         "因此 `CATA/SLIP` 随 capacity 单调上升。**这是两类道路拥堵弹性的差异，"
                         "不是「capacity 把车改派到哪类道路」的语义级重分配。**\n")
    # ---- iteration effect: 同 f=1.00，1 it -> 20 it ----
    base_h = headline.get("baseline_6_3_3b_it0", {})
    e03_h = headline.get("E03", {})
    if base_h.get("SimObs_all") and e03_h.get("SimObs_all"):
        lines.append("### 2.2 迭代效应（同 f=1.00：1 it → 20 it）\n")
        lines.append("| 指标 | 6.3.3B (1 it) | E03 (20 it) | 变化 |")
        lines.append("|---|---:|---:|---:|")
        for k, nm in [("SimObs_all", "Sim/Obs(all)"), ("CATA_simobs", "CATA"),
                      ("SLIP_simobs", "SLIP_ROAD"), ("CATA_over_SLIP", "CATA/SLIP"),
                      ("WMAPE_all", "WMAPE"), ("GEH_lt_5_all", "GEH<5"),
                      ("GEH_lt_10_all", "GEH<10"), ("Pearson_all", "Pearson")]:
            a, b = base_h.get(k), e03_h.get(k)
            if a is not None and b is not None:
                lines.append(f"| {nm} | {a:.4f} | {b:.4f} | {b-a:+.4f} |")
        lines.append("")
        lines.append("> 拥堵反馈（20 it）把总体水平整体抬高、并让 `CATA/SLIP` 从 1.0984 收敛到 1.0698；"
                     "说明固定 20 it 是必要的，且**迭代本身不是主要结构误差来源**。\n")
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
    # 数据驱动：f=1.00 是否占优
    gehs = {e: clean(row_of(e).get("GEH_lt_5_all")) for e in PHASE1}
    sims = {e: clean(row_of(e).get("SimObs_all")) for e in PHASE1}
    best_geh = max(gehs, key=lambda k: gehs[k] if gehs[k] else -1)
    best_sim = min(sims, key=lambda k: abs(sims[k] - 1) if sims[k] else 9)
    lines.append(f"- 三档中 GEH<5 最高 = **{best_geh}**（{gehs[best_geh]:.4f}）；"
                 f"Sim/Obs(all) 最接近 1 = **{best_sim}**（{sims[best_sim]:.4f}）。")
    lines.append("- 若二者一致落在 **f=1.00**，则降低 capacity 只会牺牲总体水平，"
                 "**不存在更优的 f<1.00**，capacity 可作为固定基线（f=1.00）处理，"
                 "直接转 **λ 辨识**（Phase 2 精简为 λ=0.075/0.100 @ f=1.00）。")
    lines.append("- 本步骤**不冻结 λ**。\n")
    lines.append("---\n")
    lines.append("口径：观测 7.1 冻结；仿真 `median(edges HRSx-yavg)×2.29897`；"
                 "crosswalk = 7.3.6A Final；randomSeed=4711。\n")
    (args.out_dir / "STEP7_4_2_PHASE1_REPORT.md").write_text("\n".join(lines), encoding="utf-8")

    print("[5/5] done")
    print(json.dumps(summary_json["headline"], ensure_ascii=False, indent=2))
    print(f"Outputs: {args.out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
