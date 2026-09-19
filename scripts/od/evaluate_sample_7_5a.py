#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""
evaluate_sample_7_5a.py — Step 7.5A（四）：固定样本量实验评价（零仿真，仅读已有 linkstats）。

回答的核心问题
--------------
    **100k 样本能否替代 200k？** 即：把 100k 的 linkstats 用"与其采样率匹配"的
    扩样系数抬回现实量级后，是否与 200k（同样抬回现实量级）基本一致？

设计
----
* 评价接口 = **7.3.6A Final Calibration Crosswalk**（不重建）。
* 观测口径 = **7.1 冻结口径**。
* 仿真口径 = `median(匹配 MATSim 有向边 HRSx-yavg) × SCALE`，其中
      **SCALE = ΣT / N_sample**  ← 7.5A 审计确证扩样必须在评价层施加
      S200 → 459794/200000 = 2.29897（= D01/E06，复用）
      S100 / S100c → 459794/100000 = 4.59794
* 主判据窗口 = 08-09；同时输出 07-08 / AM。
* ★**线性度检验**：`raw_sim_am(100k) / raw_sim_am(200k)` 应≈0.5。
  偏离 0.5 的部分 = 采样带来的**非线性**（拥堵/路由/时窗计数的相互作用）。
* ★**等价性检验**：逐断面比较 `sim_am×SCALE` 的 S100 vs S200：
  比值分布（中位/均值/在±10%与±20%内的比例）+ Pearson/Spearman + 总体 Σsim/Σobs。

复用（import）而非复制
----------------------
    compare_final_crosswalk_7_3_6b: load_traffic / normalize_crosswalk / load_linkstats /
        calc_method / _metrics / SCALE / WINDOWS / ROADCAT_SLOTS
    evaluate_calibration_7_4_2:     locate_experiment_linkstats / backtest_one /
        summarize / comparison_table
    run_demand_scale_7_4_3:         final_linkstats（linkstats 定位）

产物（reports/od_sample_7_5a/）
------------------------------
    sample_backtest.csv            逐断面（S200 / S100 / S100c）
    sample_roadcat_summary.csv     实验 × RoadCat × 窗口 × 全指标
    sample_comparison.csv          ★ 实验 × 窗口 × {Sim/Obs, WMAPE, GEH, CATA, SLIP, CATA/SLIP}
    step7_5a_summary.json
    STEP7_5A_REPORT.md

用法
----
    python scripts/od/evaluate_sample_7_5a.py
    python scripts/od/evaluate_sample_7_5a.py --iteration 19
    python scripts/od/evaluate_sample_7_5a.py --allow-partial   # 结果未齐时只出已有实验
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

import compare_final_crosswalk_7_3_6b as bt        # noqa: E402  (frozen 口径)
import evaluate_calibration_7_4_2 as ev1           # noqa: E402  (评价函数)
import run_demand_scale_7_4_3 as r43               # noqa: E402  (linkstats 定位)

OUT = ROOT / "reports" / "od_sample_7_5a"
MATRIX = OUT / "sample_matrix.csv"
TRAFFIC = ROOT / "Singapore_OD_MATSim_FinalData" / "08_TrafficCount" / "TrafficFlow_Data.json"
FINAL_CW = ROOT / "reports" / "od_final_calibration_crosswalk_7_3_6" / "final_calibration_crosswalk.csv"
E06_OUT = ROOT / "reports" / "od_calibration_7_4_2" / "E06_lam0p075_cap1p00"
REAL_CAR_OD_TOTAL = 459794.0

# --------------------------------------------------------------------------
# ★ 预注册判据（S100c；跑前固定，避免"看到结果再定标准"）
# --------------------------------------------------------------------------
# 用途：S100c（100k, f_cap=0.50）是"采样一致对照"——在**等效供需比**下检验
#       100k 样本能否复现 200k 的交通状态。f_cap=0.50 在此**仅作采样一致性
#       校正**（f_cap = N_sample/N_ref），**不是**交通供给标定参数，与 Phase 1
#       的 capacity_factor 严格区分。
PREREG = {
    "step": "7.5A-S100c",
    "registered_for": "S100c (N=100,000, f_cap=0.50) vs S200 (N=200,000, f_cap=1.00)",
    "criteria": [
        {
            "id": "C1",
            "name": "动力学等价性：raw flow ratio 中位数",
            "target": "接近 0.50（|中位 − 0.50| ≤ 0.05）",
            "threshold": {"metric": "linearity_raw_ratio_median", "center": 0.5, "tol": 0.05},
            "rationale": "S100（f_cap=1.00）实测 0.6174（+0.1174）明确越界 → 作为反例基线",
        },
        {
            "id": "C2",
            "name": "扩样后等价性：scaled S100c/S200 比值中位数",
            "target": "接近 1.00（|中位 − 1| ≤ 0.10）",
            "threshold": {"metric": "scaled_ratio_median", "center": 1.0, "tol": 0.10},
            "rationale": "与既有 decide() 容差一致",
        },
        {
            "id": "C3",
            "name": "scaled ratio 在 ±10% 内的断面占比",
            "target": "尽可能高（报告值，不作为门槛）",
            "threshold": None,
            "rationale": "用户判据表：±10% 仅要求'尽可能高'",
        },
        {
            "id": "C4",
            "name": "scaled ratio 在 ±20% 内的断面占比",
            "target": "≥ 0.80（较强证据）",
            "threshold": {"metric": "scaled_ratio_within_20pct", "min": 0.80},
            "rationale": "用户判据表明确 ≥80%",
        },
        {
            "id": "C5",
            "name": "Pearson / Spearman（scaled sim 逐断面 vs S200）",
            "target": "Pearson ≥ 0.90 且 Spearman ≥ 0.95",
            "threshold": {"pearson_min": 0.90, "spearman_min": 0.95},
            "rationale": "S100 已达 0.9006 / 0.9567（形态一致性本就很高）→ 作为保持线",
        },
        {
            "id": "C6",
            "name": "结构保持：CATA/SLIP 相对 S200 的系统性漂移",
            "target": "|Δ(CATA/SLIP) vs S200| ≤ 0.05（主窗口 08-09）",
            "threshold": {"metric": "abs_delta_CATA_over_SLIP", "max": 0.05},
            "rationale": ("Phase 2 λ 极差 0.0146（λ 不动）、Phase 1 capacity 极差 0.2371 "
                          "→ 取 0.05（≈capacity 极差 1/5）为'明显漂移'界线"),
        },
        {
            "id": "C7",
            "name": "三窗口方向一致",
            "target": "07-08 / 08-09 / AM：|Δ(CATA/SLIP)| 均 ≤ 0.05 且三窗口偏差同号",
            "threshold": {"max_per_window": 0.05, "sign_consistent": True},
            "rationale": "用户判据表：三窗口方向基本一致",
        },
    ],
    "pass_rule": ("全部硬门槛（C1/C2/C4/C5/C6/C7）PASS → 判定 100k 在等效供需比下"
                  "可替代 200k；C3 仅报告。"),
    "capacity_semantics": ("S100c 的 f_cap=0.50 = N_sample/N_ref，是**采样一致性校正**，"
                           "不构成交通供给标定参数，不作为后续模型参数使用。"),
}


def preregister(out_dir: Path) -> int:
    """把预注册判据落盘（必须在 S100c 跑完/评价之前执行）。"""
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "preregistered_criteria.json").write_text(
        json.dumps(PREREG, ensure_ascii=False, indent=2), encoding="utf-8")
    L = []
    L.append("# Step 7.5A — S100c 预注册判据（跑前固定）\n")
    L.append(f"**登记对象**：{PREREG['registered_for']}\n")
    L.append("**目的**：S100c 不是「继续调容量」，而是**验证 100k 样本在等效供需比下"
             "能否复现 200k 的交通状态** —— 决定后续计算规模的关键实验。\n")
    L.append("**定义**：`f_cap=0.50 = N_sample/N_ref`（100k/200k）仅作**采样一致性校正**，"
             "保持同一物理供需比；**不是**交通供给标定参数（与 Phase 1 的 `capacity_factor` "
             "严格区分）。\n")
    L.append("## 判据表（预注册）\n")
    L.append("| ID | 判据 | 目标 | 门槛 |")
    L.append("|---|---|---|---|")
    for c in PREREG["criteria"]:
        thr = "—（仅报告）" if c["threshold"] is None else "**硬门槛**"
        L.append(f"| {c['id']} | {c['name']} | {c['target']} | {thr} |")
    L.append("")
    L.append("**通过规则**：" + PREREG["pass_rule"] + "\n")
    L.append("## 阈值依据\n")
    for c in PREREG["criteria"]:
        L.append(f"- **{c['id']}**：{c['rationale']}")
    L.append("")
    L.append("## 跑完要回答的三个问题\n")
    L.append("1. **动力学等价性**：S100c 与 S200 的 raw flow ratio 是否稳定在 0.50 附近"
             "（而非 S100 的 0.6174）。")
    L.append("2. **扩样后等价性**：`S100c×4.59794` vs `S200×2.29897` → 逐断面比值、"
             "WMAPE、GEH、Pearson/Spearman。")
    L.append("3. **结构是否保持**：`CATA/SLIP` 与三时间窗 07–08 / 08–09 / AM 是否同时稳定。")
    L.append("")
    L.append("## 固定项（跑 S100c 时不变）\n")
    L.append("`N=100,000` / `f_cap=0.50` / `λ=0.075` / 20 iterations / `seed=4711` / "
             "`routingRandomness=0` / same network / same OD / same departure profile / "
             "same Final Crosswalk / same evaluation target。\n")
    L.append("> 本文件与 `preregistered_criteria.json` 在 **S100c 评价运行之前**生成；"
             "判据不得因结果而事后调整。\n")
    (out_dir / "STEP7_5A_S100C_PREREGISTRATION.md").write_text("\n".join(L), encoding="utf-8")
    print(f"预注册判据 -> {out_dir / 'STEP7_5A_S100C_PREREGISTRATION.md'}")
    print(f"            -> {out_dir / 'preregistered_criteria.json'}")
    return 0


def read_matrix(path: Path = MATRIX) -> dict[str, dict]:
    with open(path, encoding="utf-8-sig", newline="") as f:
        return {r["experiment_id"]: r for r in csv.DictReader(f)}


def locate(eid: str, spec: dict, it: int) -> Path | None:
    if str(spec["mode"]).startswith("REUSE"):
        return r43.final_linkstats(E06_OUT, "E06")
    out_dir = ROOT / spec["output_dir"]
    return r43.final_linkstats(out_dir, eid)


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


def f4(v):
    return "n/a" if v is None else f"{v:.4f}"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--iteration", type=int, default=19)
    ap.add_argument("--out-dir", type=Path, default=OUT)
    ap.add_argument("--allow-partial", action="store_true")
    ap.add_argument("--prereg-only", action="store_true",
                    help="只把预注册判据落盘（须在 S100c 评价前执行），不评价")
    args = ap.parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)
    if args.prereg_only:
        return preregister(args.out_dir)

    print("[1/6] load observation (7.1 frozen convention)")
    obs = bt.load_traffic(TRAFFIC)
    print(f"      observed LTA sections = {obs['LinkID'].nunique():,}")

    print("[2/6] load 7.3.6A Final Crosswalk")
    cw_final = bt.normalize_crosswalk(FINAL_CW, "final")
    print(f"      crosswalk rows={len(cw_final):,}  sections={cw_final['lta_linkid'].nunique():,}")

    print("[3/6] collect linkstats (per-sample SCALE)")
    matrix = read_matrix()
    order = ["S200", "S100", "S100c"]
    order = [e for e in order if e in matrix]
    sources = []   # (eid, scale, ls_path)
    for eid in order:
        spec = matrix[eid]
        ls = locate(eid, spec, args.iteration)
        scale = float(spec["scale"])
        if ls:
            sources.append((eid, scale, ls))
            print(f"      {eid}: SCALE={scale:.5f}  {ls.name}")
        else:
            print(f"      {eid}: linkstats MISSING -> 跳过（实验未完成？）")
    run_ids = [e for e in order if e != "S200"]
    present_runs = [e for e, _, _ in sources if e != "S200"]
    if not present_runs and not args.allow_partial:
        print("\nERROR: 尚无 100k 实验 linkstats；请先运行 run_sample_7_5a.py"
              "（或加 --allow-partial 只出参考行）")
        return 1

    print("[4/6] per-section backtest (SCALE injected per sample)")
    saved_scale = bt.SCALE
    parts = []
    for eid, scale, ls in sources:
        bt.SCALE = scale                       # ★ 每次评价用与该样本匹配的扩样系数
        cw = cw_final.copy()
        cw["method"] = eid
        parts.append(ev1.backtest_one(eid, cw, obs, ls))
    bt.SCALE = saved_scale
    backtest = pd.concat(parts, ignore_index=True)
    backtest.to_csv(args.out_dir / "sample_backtest.csv", index=False, encoding="utf-8-sig")

    summary = ev1.summarize(backtest)
    summary.to_csv(args.out_dir / "sample_roadcat_summary.csv", index=False, encoding="utf-8-sig")

    cmp_tbl = ev1.comparison_table(summary, args.iteration)
    cmp_tbl.to_csv(args.out_dir / "sample_comparison.csv", index=False, encoding="utf-8-sig")

    print("[5/6] equivalence & linearity tests")
    eq = equivalence(backtest, sources, matrix)
    print(f"      {json.dumps({k: v for k, v in eq.items() if k in ('available_pairs',)}, ensure_ascii=False)}")

    def row_of(eid, window="08-09"):
        z = cmp_tbl[(cmp_tbl["method"] == eid) & (cmp_tbl["window"] == window)]
        return z.iloc[0].to_dict() if not z.empty else {}

    headline = {}
    for eid, scale, _ in sources:
        d = row_of(eid)
        headline[eid] = {
            "scale": scale,
            "sample_agents": int(matrix[eid]["sample_agents"]),
            "f_cap": float(matrix[eid]["f_cap"]),
            "label": f"{eid} (N={int(matrix[eid]['sample_agents']):,}, f_cap={float(matrix[eid]['f_cap']):.2f})",
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

    verdict = decide(eq, headline)
    prereg_check = check_preregistered(eq, cmp_tbl, headline)
    summary_json = {
        "step": "7.5A",
        "status": "PASS",
        "question": "100k 样本能否替代 200k？",
        "lambda_fixed": 0.075,
        "iterations": 20,
        "evaluated_iteration": args.iteration,
        "crosswalk": "7.3.6A Final Calibration Crosswalk",
        "observation": "7.1 frozen convention",
        "simulation": "median(matched MATSim edges HRSx-yavg) * SCALE(=ΣT/N_sample)",
        "headline_window": "08-09",
        "headline": headline,
        "equivalence_tests": eq,
        "verdict": verdict,
        "preregistered_criteria": PREREG,
        "preregistered_check": prereg_check,
        "audit_ref": "STEP7_5A_DEMAND_CHAIN_AUDIT.md (verdict: NOT_CONSUMED)",
        "capacity_note": ("S100 固定 f_cap=1.00（用户字面设计）；S100c 用 f_cap=0.50 作为"
                          "采样一致对照（f_cap=N_sample/N_ref），用于分离采样效应与供给/需求比效应"),
        "parameters_changed": True,
        "lambda_selected": False,
    }
    (args.out_dir / "step7_5a_summary.json").write_text(
        json.dumps(summary_json, ensure_ascii=False, indent=2), encoding="utf-8")

    print("[6/6] write report")
    md = render_md(summary_json, sources, matrix, cmp_tbl, eq, run_ids, present_runs,
                   prereg=prereg_check)
    (args.out_dir / "STEP7_5A_REPORT.md").write_text(md, encoding="utf-8")

    print()
    print(json.dumps(headline, ensure_ascii=False, indent=2))
    print(f"\nVERDICT: {verdict['code']}")
    if prereg_check.get("available"):
        for eid, pc in prereg_check["per_experiment"].items():
            print(f"\n--- 预注册判据 [{eid}]  硬门槛 {pc['hard_passed']}/{pc['hard_total']} "
                  f"{'ALL PASS' if pc['all_pass'] else 'NOT ALL PASS'} ---")
            for r in pc["rows"]:
                v = "—" if r["verdict"] is None else ("PASS" if r["verdict"] else "FAIL")
                print(f"    {r['id']} [{v}] {r['name']}: {r['observed']}")
    print(f"Outputs: {args.out_dir}")
    return 0


# --------------------------------------------------------------------------
# equivalence / linearity
# --------------------------------------------------------------------------
def equivalence(backtest: pd.DataFrame, sources, matrix) -> dict:
    """逐断面比较 100k×SCALE 与 200k×SCALE；并检验 raw 的线性度。"""
    keys = [e for e, _, _ in sources]
    if "S200" not in keys:
        return {"available": False, "reason": "缺 S200 参照"}
    b = backtest.copy()
    piv = b.pivot_table(index="lta_linkid", columns="method",
                        values=["sim_am", "sim_7_8_scaled", "sim_8_9_scaled",
                                "sim_7_8_raw", "sim_8_9_raw", "obs_am"],
                        aggfunc="first")
    out = {"available": True, "pairs": {}}

    for eid in [e for e in keys if e != "S200"]:
        try:
            sim_e = piv[("sim_am", eid)]
            sim_r = piv[("sim_am", "S200")]
            raw_e = (piv[("sim_7_8_raw", eid)].fillna(0) + piv[("sim_8_9_raw", eid)].fillna(0))
            raw_r = (piv[("sim_7_8_raw", "S200")].fillna(0) + piv[("sim_8_9_raw", "S200")].fillna(0))
            obs_a = piv[("obs_am", "S200")]
        except KeyError:
            continue
        m = sim_e.notna() & sim_r.notna() & (sim_r > 0)
        ratio = (sim_e[m] / sim_r[m]).astype(float)
        # 线性度：只在与 200k 都为正的断面上比较 raw 比值
        m2 = (raw_e > 0) & (raw_r > 0)
        lin = (raw_e[m2] / raw_r[m2]).astype(float)
        # 相关性（逐断面 scaled sim）
        mm = sim_e.notna() & sim_r.notna()
        pr = float(sim_e[mm].astype(float).corr(sim_r[mm].astype(float), method="pearson")) \
            if mm.sum() > 2 else None
        sr = float(sim_e[mm].astype(float).corr(sim_r[mm].astype(float), method="spearman")) \
            if mm.sum() > 2 else None
        agg_e = float(sim_e[sim_e.notna()].sum())
        agg_r = float(sim_r[sim_r.notna()].sum())
        agg_o = float(obs_a[(sim_e.notna()) & (obs_a > 0)].sum())
        out["pairs"][eid] = {
            "n_sections": int(m.sum()),
            "scaled_ratio_median": float(ratio.median()) if len(ratio) else None,
            "scaled_ratio_mean": float(ratio.mean()) if len(ratio) else None,
            "scaled_ratio_within_10pct": float(((ratio - 1).abs() <= 0.10).mean()) if len(ratio) else None,
            "scaled_ratio_within_20pct": float(((ratio - 1).abs() <= 0.20).mean()) if len(ratio) else None,
            "pearson_scaled": pr,
            "spearman_scaled": sr,
            "linearity_raw_ratio_median": float(lin.median()) if len(lin) else None,
            "linearity_raw_ratio_mean": float(lin.mean()) if len(lin) else None,
            "linearity_expected": 0.5,
            "agg_sim_scaled_eid": agg_e,
            "agg_sim_scaled_200k": agg_r,
            "agg_obs": agg_o,
            "agg_SimObs_eid": (agg_e / agg_o) if agg_o else None,
            "agg_SimObs_200k": (agg_r / agg_o) if agg_o else None,
        }
    out["available_pairs"] = list(out["pairs"].keys())
    return out


def decide(eq: dict, headline: dict) -> dict:
    if not eq.get("available"):
        return {"code": "INCOMPLETE", "detail": "缺 S200 参照或实验未完成"}
    codes = {}
    for eid, p in eq["pairs"].items():
        med = p.get("scaled_ratio_median")
        lin = p.get("linearity_raw_ratio_median")
        w20 = p.get("scaled_ratio_within_20pct")
        if med is None:
            codes[eid] = "INCOMPLETE"
            continue
        near = abs(med - 1) <= 0.10 and (w20 or 0) >= 0.80
        lin_ok = lin is not None and abs(lin - 0.5) <= 0.05
        if near and lin_ok:
            codes[eid] = "SUBSTITUTABLE"
        elif near and not lin_ok:
            codes[eid] = "SUBSTITUTABLE_WITH_NONLINEARITY"
        else:
            codes[eid] = "NOT_SUBSTITUTABLE"
    if any(v == "NOT_SUBSTITUTABLE" for v in codes.values()):
        code = "NOT_SUBSTITUTABLE"
    elif any(v.startswith("SUBSTITUTABLE") for v in codes.values()):
        code = "SUBSTITUTABLE"
    else:
        code = "INCOMPLETE"
    return {"code": code, "per_experiment": codes,
            "rule": ("可替代：scaled 比值中位 |r-1|<=0.10 且 ±20% 内断面占比>=0.80 "
                     "且 raw 线性比 |0.5-中位|<=0.05；"
                     "线性度不达标时标 SUBSTITUTABLE_WITH_NONLINEARITY（提示采样非线性）")}


def check_preregistered(eq: dict, cmp_tbl, headline) -> dict:
    """按 PREREG 判据逐条判定（对每个 100k 实验；S100c 为重点）。"""
    out = {"available": bool(eq.get("available")), "per_experiment": {}}
    if not eq.get("available"):
        return out
    s200_ratio = headline.get("S200", {}).get("CATA_over_SLIP")

    def win_ratio(eid, window):
        z = cmp_tbl[(cmp_tbl["method"] == eid) & (cmp_tbl["window"] == window)]
        if z.empty:
            return None
        return clean(z.iloc[0].get("CATA_over_SLIP"))

    for eid, p in eq.get("pairs", {}).items():
        rows = []
        lin = p.get("linearity_raw_ratio_median")
        med = p.get("scaled_ratio_median")
        w10 = p.get("scaled_ratio_within_10pct")
        w20 = p.get("scaled_ratio_within_20pct")
        pr = p.get("pearson_scaled")
        sr = p.get("spearman_scaled")

        c1 = bool(lin is not None and abs(lin - 0.5) <= 0.05)
        rows.append(("C1", "动力学等价性（raw ratio 中位）", f"{f4(lin)} vs 0.5000", c1))
        c2 = bool(med is not None and abs(med - 1.0) <= 0.10)
        rows.append(("C2", "扩样后等价性（scaled 比值中位）", f"{f4(med)} vs 1.0000", c2))
        rows.append(("C3", "±10% 内占比（仅报告）", f4(w10), None))
        c4 = bool(w20 is not None and w20 >= 0.80)
        rows.append(("C4", "±20% 内占比 ≥ 0.80", f4(w20), c4))
        c5 = bool(pr is not None and sr is not None and pr >= 0.90 and sr >= 0.95)
        rows.append(("C5", "Pearson≥0.90 且 Spearman≥0.95", f"{f4(pr)} / {f4(sr)}", c5))

        r_e = win_ratio(eid, "08-09")
        d6 = abs(r_e - s200_ratio) if (r_e is not None and s200_ratio is not None) else None
        c6 = bool(d6 is not None and d6 <= 0.05)
        rows.append(("C6", "CATA/SLIP 漂移（08-09）≤0.05", f4(d6), c6))

        diffs = {}
        for w in ("07-08", "08-09", "AM"):
            r = win_ratio(eid, w)
            diffs[w] = (r - s200_ratio) if (r is not None and s200_ratio is not None) else None
        vals = [v for v in diffs.values() if v is not None]
        same_sign = bool(len(vals) == 3 and (all(v >= 0 for v in vals) or all(v <= 0 for v in vals)))
        within = bool(len(vals) == 3 and all(abs(v) <= 0.05 for v in vals))
        c7 = bool(same_sign and within)
        rows.append(("C7", "三窗口方向一致（|Δ|≤0.05 且同号）",
                     " / ".join(f"{w}:{f4(v)}" for w, v in diffs.items()), c7))

        hard = [r for r in rows if r[3] is not None]
        passed = sum(1 for r in hard if r[3])
        out["per_experiment"][eid] = {
            "rows": [{"id": r[0], "name": r[1], "observed": r[2],
                      "verdict": (None if r[3] is None else bool(r[3]))} for r in rows],
            "hard_total": len(hard),
            "hard_passed": passed,
            "all_pass": bool(len(hard) > 0 and passed == len(hard)),
        }
    return out


# --------------------------------------------------------------------------
def render_md(sj, sources, matrix, cmp_tbl, eq, run_ids, present_runs, prereg=None) -> str:
    L = []
    L.append("# Step 7.5A — 固定样本量 + 可变需求权重：100k vs 200k 等需求对照\n")
    L.append("**零仿真**（仅读 linkstats）。核心问题：**100k 样本能否替代 200k？**\n")
    partial = len(present_runs) < len(run_ids)
    if partial:
        L.append(f"**⚠️ 部分结果**：已完成 100k 实验 = {present_runs or '（无）'}；"
                 f"未完成 = {[e for e in run_ids if e not in present_runs]}。"
                 "**非最终结论**，跑完后重跑本脚本即覆盖。\n")
    L.append("## 0. 结论\n")
    v = sj["verdict"]
    L.append(f"- **总判定：`{v['code']}`**")
    for eid, c in v["per_experiment"].items():
        L.append(f"  - `{eid}` → **{c}**")
    L.append(f"- 判据：{v['rule']}\n")
    L.append("## 1. 正式评价表（窗口 08-09，Σsim/Σobs，it.%d）\n" % sj["evaluated_iteration"])
    L.append("| 实验 | N_sample | f_cap | SCALE | Sim/Obs(all) | WMAPE | GEH<5 | GEH<10 | Pearson | Spearman | CATA | SLIP | CATA/SLIP |")
    L.append("|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
    for eid, h in sj["headline"].items():
        L.append(f"| **{eid}** | {h['sample_agents']:,} | {h['f_cap']:.2f} | {h['scale']:.5f} "
                 f"| {f4(h['SimObs_all'])} | {f4(h['WMAPE_all'])} | {f4(h['GEH_lt_5_all'])} "
                 f"| {f4(h['GEH_lt_10_all'])} | {f4(h['Pearson_all'])} | {f4(h['Spearman_all'])} "
                 f"| {f4(h['CATA_simobs'])} | {f4(h['SLIP_simobs'])} | {f4(h['CATA_over_SLIP'])} |")
    L.append("")
    L.append("> 口径：观测 7.1 冻结；仿真 `median(edges HRSx-yavg) × SCALE`，"
             "**SCALE = 459794 / N_sample**（7.5A 审计：扩样必须在评价层施加）。"
             "S200 = D01/E06 复用，不重跑。\n")
    L.append("## 2. 线性度检验（raw 是否随样本量线性）\n")
    L.append("| 对比 | n 断面 | raw 比值中位 | raw 比值均值 | 期望 |")
    L.append("|---|---:|---:|---:|---:|")
    for eid, p in eq.get("pairs", {}).items():
        L.append(f"| {eid} raw / S200 raw | {p['n_sections']:,} | "
                 f"{f4(p['linearity_raw_ratio_median'])} | {f4(p['linearity_raw_ratio_mean'])} | 0.5000 |")
    L.append("")
    L.append("> 若 raw 比值中位≈0.5，说明 linkstats 原始口径**近似线性于 agent 数**"
             "（与审计一致：QSim 只数车）。偏离 0.5 的部分 = 采样引入的非线性"
             "（拥堵/路由/时窗计数相互作用）。\n")
    L.append("## 3. ★等价性检验（100k×SCALE vs 200k×SCALE，逐断面）\n")
    L.append("| 对比 | n 断面 | 比值中位 | 比值均值 | ±10% 内 | ±20% 内 | Pearson | Spearman |")
    L.append("|---|---:|---:|---:|---:|---:|---:|---:|")
    for eid, p in eq.get("pairs", {}).items():
        L.append(f"| {eid} / S200 | {p['n_sections']:,} | {f4(p['scaled_ratio_median'])} | "
                 f"{f4(p['scaled_ratio_mean'])} | {f4(p['scaled_ratio_within_10pct'])} | "
                 f"{f4(p['scaled_ratio_within_20pct'])} | {f4(p['pearson_scaled'])} | "
                 f"{f4(p['spearman_scaled'])} |")
    L.append("")
    L.append("| 对比 | Σsim(scaled) | Σobs | Σsim/Σobs |")
    L.append("|---|---:|---:|---:|")
    for eid, p in eq.get("pairs", {}).items():
        L.append(f"| {eid} | {p['agg_sim_scaled_eid']:,.0f} | {p['agg_obs']:,.0f} | "
                 f"{f4(p['agg_SimObs_eid'])} |")
    if "S200" in sj["headline"]:
        pass
    L.append("")
    L.append("## 4. 各窗口\n")
    L.append("| 实验 | 窗口 | Sim/Obs | CATA | SLIP_ROAD | CATA/SLIP |")
    L.append("|---|---|---:|---:|---:|---:|")
    for eid in list(sj["headline"].keys()):
        for window, _, _, _ in bt.WINDOWS:
            z = cmp_tbl[(cmp_tbl["method"] == eid) & (cmp_tbl["window"] == window)]
            if z.empty:
                continue
            d = z.iloc[0]
            L.append(f"| {eid} | {window} | {f4(clean(d.get('SimObs_all')))} "
                     f"| {f4(clean(d.get('CATA_simobs')))} | {f4(clean(d.get('SLIP_simobs')))} "
                     f"| {f4(clean(d.get('CATA_over_SLIP')))} |")
    L.append("")
    if prereg and prereg.get("available"):
        L.append("## 5. ★预注册判据逐条判定（跑前固定）\n")
        L.append("> 判据 C1–C7 在 S100c 评价运行**之前**固定于 "
                 "`preregistered_criteria.json` 与 `STEP7_5A_S100C_PREREGISTRATION.md`；"
                 "阈值依据见该两文件。\n")
        for eid, pc in prereg["per_experiment"].items():
            L.append(f"### {eid} — 硬门槛 **{pc['hard_passed']}/{pc['hard_total']}** "
                     f"{'（ALL PASS）' if pc['all_pass'] else '（NOT ALL PASS）'}\n")
            L.append("| ID | 判据 | 实测 | 判定 |")
            L.append("|---|---|---|---|")
            for r in pc["rows"]:
                v = "—（仅报告）" if r["verdict"] is None else ("**PASS**" if r["verdict"] else "**FAIL**")
                L.append(f"| {r['id']} | {r['name']} | {r['observed']} | {v} |")
            L.append("")
    L.append("## 6. 判读（三问）\n")
    L.append("**① 动力学等价性**：看 §2 `raw 比值中位` 是否回到 ≈0.50 —— "
             "S100 为 0.6174（+23.5%），S100c 若 ≈0.50 即证明**减半样本不再改变网络动力学状态**。")
    L.append("**② 扩样后等价性**：看 §3 `scaled 比值中位 / ±10% / ±20% / Pearson / Spearman` "
             "与 §1 的 WMAPE / GEH —— `S100c×4.59794` 应逼近 `S200×2.29897`。")
    L.append("**③ 结构是否保持**：看 §4 三窗口 `CATA/SLIP` 是否同时稳定（对应 C6/C7）。\n")
    L.append("- **S100（f_cap=1.00）**：同容量下减样本 → 车密度减半，**供给/需求比被改变**，"
             "因此它同时含「采样效应」与「拥堵物理改变」两种成分"
             "（→ 判 `NOT_SUBSTITUTABLE` 属预期）。")
    L.append("- **S100c（f_cap=0.50）**：`f_cap = N_sample/N_ref`，**保持同一物理场景**，"
             "是判定「100k 是否为可替代样本」的**干净对照**。"
             "注意：此处 f_cap=0.50 是**采样一致性校正**，**不是**交通供给标定参数。")
    L.append("- 若 **S100c 通过预注册判据** → (a) 100k 可作代表样本，用于后续 "
             "λ/需求/空间结构标定；(b) 200k 仅保留一次最终验证；改采样率时 capacity 须同比缩放。")
    L.append("- **λ 仍不冻结**（本轮固定 0.075 仅为控制变量）。\n")
    L.append("---\n")
    L.append("参照审计：`STEP7_5A_DEMAND_CHAIN_AUDIT.md`（verdict = NOT_CONSUMED："
             "`expansionFactor`/`odTrips` 不被 MATSim 消费）。\n")
    return "\n".join(L)


if __name__ == "__main__":
    raise SystemExit(main())
