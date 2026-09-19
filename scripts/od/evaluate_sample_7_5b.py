#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""
evaluate_sample_7_5b.py — Step 7.5B 评价（零仿真，仅读已有 linkstats）。

回答的机制问题
--------------
    100k 的残余非线性，究竟来自「样本数量不足」，还是来自
    「低样本下『每正 OD cell ≥1 agent』保底采样规则本身产生的系统性空间偏差」？

三方对照（唯一变量 = 采样规则）
------------------------------
    S200   200k  f_cap=1.00  rule=FLOOR_PLUS_1     （参考，复用 E06）
    S100c  100k  f_cap=0.50  rule=FLOOR_PLUS_1     （现行规则基线，复用 7.5A 输出）
    S100r  100k  f_cap=0.50  rule=PURE_TRIPS_PROP  （本步唯一新实验）

评价口径（与 7.5A 逐字节同源）
-----------------------------
* 评价接口 = 7.3.6A Final Calibration Crosswalk；观测 = 7.1 冻结口径；
* 仿真 = `median(匹配 MATSim 有向边 HRSx-yavg) × SCALE`；
* **主口径 SCALE = ΣT / N_sample**（S200 2.29897 / S100c·S100r 4.59794）
  → 三个实验的**名义需求相同**，差异只可能来自采样规则；
* 敏感性口径（仅 S100r，解析给出）：`SCALE_raw = ΣEF_sampled / N_sample = 4.38266`
  （= 4.59794 × f_realized，f_realized = 0.95318）→ 所有 scaled 量整体 ×0.95318。
  由于 7.5A 审计已证 `expansionFactor` 不被 MATSim 消费，该口径只影响账面、不影响仿真。

预注册判据（**跑前固定**）
------------------------
    D1–D7  绝对判据（与 7.5A 的 C1–C7 同阈值，便于直接比较 S100c）
    M1–M4  机制判据（差分：S100r 相对 S100c 是否改善）
    判据在 S100r 评价运行之前落盘（`--prereg-only`）。

产物
----
    sample_backtest_7_5b.csv / sample_roadcat_summary_7_5b.csv /
    sample_comparison_7_5b.csv / step7_5b_summary.json / STEP7_5B_REPORT.md

用法
----
    python scripts/od/evaluate_sample_7_5b.py --prereg-only   # 跑前固定判据
    python scripts/od/evaluate_sample_7_5b.py
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
import evaluate_sample_7_5a as ev75a               # noqa: E402  (等价性/判决函数复用)
import run_demand_scale_7_4_3 as r43               # noqa: E402  (linkstats 定位)

OUT = ROOT / "reports" / "od_sample_7_5b"
MATRIX = OUT / "sample_matrix_7_5b.csv"
TRAFFIC = ROOT / "Singapore_OD_MATSim_FinalData" / "08_TrafficCount" / "TrafficFlow_Data.json"
FINAL_CW = ROOT / "reports" / "od_final_calibration_crosswalk_7_3_6" / "final_calibration_crosswalk.csv"
E06_OUT = ROOT / "reports" / "od_calibration_7_4_2" / "E06_lam0p075_cap1p00"
S100C_OUT = ROOT / "reports" / "od_sample_7_5a" / "S100c_lam0p075_cap0p50"
REAL_CAR_OD_TOTAL = 459794.0

clean = ev75a.clean
f4 = ev75a.f4

# --------------------------------------------------------------------------
# ★ 7.5B 预注册判据（跑前固定）
# --------------------------------------------------------------------------
PREREG_B = {
    "step": "7.5B-SamplingRuleSensitivity",
    "registered_for": ("S100r (N=100,000, f_cap=0.50, PURE_TRIPS_PROP) vs "
                       "S100c (N=100,000, f_cap=0.50, FLOOR_PLUS_1) vs S200 (N=200,000, f_cap=1.00)"),
    "question": ("100k 的残余非线性来自「样本数量不足」还是「保底采样规则的系统性空间偏差」？"),
    "single_variable": "sampling_rule（其余：λ=0.075 / N=100k / f_cap=0.50 / 20 it / seed=4711 / 同网络·OD·出发剖面·crosswalk·靶场）",
    "criteria": [
        {"id": "D1", "group": "absolute", "name": "动力学等价性：raw flow ratio 中位 ≈0.50",
         "threshold": {"metric": "linearity_raw_ratio_median", "center": 0.5, "tol": 0.05},
         "rationale": "与 7.5A 的 C1 同阈值；S100c 实测 0.5799 未过"},
        {"id": "D2", "group": "absolute", "name": "扩样后等价性：scaled S100r/S200 中位 ≈1.00",
         "threshold": {"metric": "scaled_ratio_median", "center": 1.0, "tol": 0.10},
         "rationale": "与 7.5A 的 C2 同阈值；S100c 实测 1.1537 未过"},
        {"id": "D3", "group": "absolute", "name": "scaled ratio ±10% 内占比（仅报告）",
         "threshold": None, "rationale": "用户口径：仅要求尽可能高"},
        {"id": "D4", "group": "absolute", "name": "scaled ratio ±20% 内占比 ≥0.80",
         "threshold": {"metric": "scaled_ratio_within_20pct", "min": 0.80},
         "rationale": "与 7.5A 的 C4 同阈值；S100c 实测 0.2648"},
        {"id": "D5", "group": "absolute", "name": "Pearson≥0.90 且 Spearman≥0.95",
         "threshold": {"pearson_min": 0.90, "spearman_min": 0.95},
         "rationale": "与 7.5A 的 C5 同阈值；S100c 实测 0.8557/0.9344"},
        {"id": "D6", "group": "absolute", "name": "结构保持：|Δ(CATA÷SLIP) vs S200| ≤0.05（08-09）",
         "threshold": {"metric": "abs_delta_CATA_over_SLIP", "max": 0.05},
         "rationale": "与 7.5A 的 C6 同阈值；S100c 实测 0.0233 PASS"},
        {"id": "D7", "group": "absolute", "name": "三窗口方向一致（|Δ|≤0.05 且同号）",
         "threshold": {"max_per_window": 0.05, "sign_consistent": True},
         "rationale": "与 7.5A 的 C7 同阈值；S100c 实测符号不一致（FAIL）"},
        {"id": "M1", "group": "mechanism", "name": "raw ratio 比 S100c 更接近 0.50",
         "threshold": {"comparator": "closer_to_0.5_than", "reference": "S100c"},
         "rationale": "机制判据：去保底后采样非线性是否缩小"},
        {"id": "M2", "group": "mechanism", "name": "scaled ±20% 内占比 ≥ S100c",
         "threshold": {"comparator": "ge_than", "reference": "S100c"},
         "rationale": "机制判据：逐断面等价性是否回升"},
        {"id": "M3", "group": "mechanism", "name": "Pearson ≥ S100c",
         "threshold": {"comparator": "ge_than", "reference": "S100c"},
         "rationale": "机制判据：空间形态相关性是否回升（S100c 相对 S100 反而下降）"},
        {"id": "M4", "group": "mechanism", "name": "|Δ(CATA÷SLIP)| ≤ S100c",
         "threshold": {"comparator": "le_than", "reference": "S100c"},
         "rationale": "机制判据：结构漂移是否不再变差"},
    ],
    "verdict_rule": {
        "SAMPLING_RULE_WAS_THE_CAUSE": "D1–D7 全 PASS → 100k 可用，但必须改采样算法（去保底）",
        "PARTIAL_IMPROVEMENT": "M 组 ≥3 项改善但 D 未全过 → 保底规则是残余偏差的**贡献来源**之一，仍不足以让 100k 达标",
        "SAMPLE_SIZE_DEPENDENT": "M 组改善 <3 项 → 保底规则**不是**主因；残余非线性来自样本量本身（此时 knee 扫描才有意义）",
    },
    "capacity_semantics": ("f_cap=0.50 = N_sample/N_ref，仅作**采样一致性校正**"
                           "（保持同一物理供需比），不是交通供给标定参数。"),
    "scale_semantics": ("主口径 SCALE = ΣT/N_sample（三方名义需求相同，隔离采样规则效应）；"
                        "S100r 的 raw-EF 敏感性口径 = ΣEF_sampled/N = 4.38266（整体 ×0.95318）。"),
}


def preregister(out_dir: Path) -> int:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "preregistered_criteria_7_5b.json").write_text(
        json.dumps(PREREG_B, ensure_ascii=False, indent=2), encoding="utf-8")
    L = []
    L.append("# Step 7.5B — Sampling Rule Sensitivity 预注册判据（跑前固定）\n")
    L.append(f"**登记对象**：{PREREG_B['registered_for']}\n")
    L.append(f"**唯一变量**：{PREREG_B['single_variable']}\n")
    L.append(f"**要回答的机制问题**：{PREREG_B['question']}\n")
    L.append("## 判据表\n")
    L.append("| ID | 组 | 判据 | 门槛 |")
    L.append("|---|---|---|---|")
    for c in PREREG_B["criteria"]:
        thr = "—（仅报告）" if c["threshold"] is None else "**硬门槛**"
        L.append(f"| {c['id']} | {c['group']} | {c['name']} | {thr} |")
    L.append("")
    L.append("**D 组 = 绝对判据**（与 7.5A 的 C1–C7 同阈值，便于与 S100c 直接比较）；")
    L.append("**M 组 = 机制判据**（差分：S100r 相对 S100c 是否改善）。\n")
    L.append("## 判决规则\n")
    for k, v in PREREG_B["verdict_rule"].items():
        L.append(f"- **`{k}`**：{v}")
    L.append("")
    L.append("## 阈值依据\n")
    for c in PREREG_B["criteria"]:
        L.append(f"- **{c['id']}**：{c['rationale']}")
    L.append("")
    L.append("## 口径与语义\n")
    L.append(f"- **容量语义**：{PREREG_B['capacity_semantics']}")
    L.append(f"- **缩放语义**：{PREREG_B['scale_semantics']}\n")
    L.append("> 本文件与 `preregistered_criteria_7_5b.json` 在 **S100r 评价运行之前**生成；"
             "判据不得因结果而事后调整。\n")
    (out_dir / "STEP7_5B_PREREGISTRATION.md").write_text("\n".join(L), encoding="utf-8")
    print(f"预注册判据 -> {out_dir / 'STEP7_5B_PREREGISTRATION.md'}")
    print(f"            -> {out_dir / 'preregistered_criteria_7_5b.json'}")
    return 0


# --------------------------------------------------------------------------
def read_matrix(path: Path = MATRIX) -> dict[str, dict]:
    with open(path, encoding="utf-8-sig", newline="") as f:
        return {r["experiment_id"]: r for r in csv.DictReader(f)}


def locate(eid: str, spec: dict) -> Path | None:
    mode = str(spec["mode"])
    if mode.startswith("REUSE_E06"):
        return r43.final_linkstats(E06_OUT, "E06")
    if eid == "S100c":
        return r43.final_linkstats(S100C_OUT, "S100c")
    return r43.final_linkstats(ROOT / spec["output_dir"], eid)


def check_preregistered_b(eq: dict, cmp_tbl, headline, prereg: dict) -> dict:
    out = {"available": bool(eq.get("available")), "rows": [], "per_experiment": {}}
    if not eq.get("available"):
        return out

    s200 = headline.get("S200", {}).get("CATA_over_SLIP")

    def win_ratio(eid, window):
        z = cmp_tbl[(cmp_tbl["method"] == eid) & (cmp_tbl["window"] == window)]
        return None if z.empty else clean(z.iloc[0].get("CATA_over_SLIP"))

    pc = eq["pairs"].get("S100c", {})
    pr = eq["pairs"].get("S100r", {})
    if not pr:
        # ★早返路径必须把 available 置 False，否则下游渲染会 KeyError
        out["available"] = False
        out["reason"] = "S100r 尚未评价（linkstats 缺失）"
        return out

    lin = pr.get("linearity_raw_ratio_median")
    med = pr.get("scaled_ratio_median")
    w10 = pr.get("scaled_ratio_within_10pct")
    w20 = pr.get("scaled_ratio_within_20pct")
    pe = pr.get("pearson_scaled")
    sp = pr.get("spearman_scaled")

    r_r = win_ratio("S100r", "08-09")
    d6_r = abs(r_r - s200) if (r_r is not None and s200 is not None) else None
    r_c = win_ratio("S100c", "08-09")
    d6_c = abs(r_c - s200) if (r_c is not None and s200 is not None) else None

    diffs = {w: (win_ratio("S100r", w) - s200
                 if win_ratio("S100r", w) is not None and s200 is not None else None)
             for w in ("07-08", "08-09", "AM")}
    vals = [v for v in diffs.values() if v is not None]
    same_sign = bool(len(vals) == 3 and (all(v >= 0 for v in vals) or all(v <= 0 for v in vals)))
    within = bool(len(vals) == 3 and all(abs(v) <= 0.05 for v in vals))

    lin_c = pc.get("linearity_raw_ratio_median")
    w20_c = pc.get("scaled_ratio_within_20pct")
    pe_c = pc.get("pearson_scaled")

    rows = [
        ("D1", "absolute", "动力学等价性（raw ratio 中位）", f"{f4(lin)} vs 0.5000",
         bool(lin is not None and abs(lin - 0.5) <= 0.05)),
        ("D2", "absolute", "扩样后等价性（scaled 比值中位）", f"{f4(med)} vs 1.0000",
         bool(med is not None and abs(med - 1.0) <= 0.10)),
        ("D3", "absolute", "±10% 内占比（仅报告）", f4(w10), None),
        ("D4", "absolute", "±20% 内占比 ≥0.80", f4(w20),
         bool(w20 is not None and w20 >= 0.80)),
        ("D5", "absolute", "Pearson≥0.90 且 Spearman≥0.95", f"{f4(pe)} / {f4(sp)}",
         bool(pe is not None and sp is not None and pe >= 0.90 and sp >= 0.95)),
        ("D6", "absolute", "CATA÷SLIP 漂移（08-09）≤0.05", f4(d6_r),
         bool(d6_r is not None and d6_r <= 0.05)),
        ("D7", "absolute", "三窗口方向一致（|Δ|≤0.05 且同号）",
         " / ".join(f"{w}:{f4(v)}" for w, v in diffs.items()),
         bool(same_sign and within)),
        ("M1", "mechanism", "raw ratio 更接近 0.50（vs S100c）",
         f"|Δ0.5|: {f4(abs(lin - 0.5) if lin is not None else None)} < "
         f"{f4(abs(lin_c - 0.5) if lin_c is not None else None)}",
         bool(lin is not None and lin_c is not None and abs(lin - 0.5) < abs(lin_c - 0.5))),
        ("M2", "mechanism", "±20% 内占比 ≥ S100c", f"{f4(w20)} vs {f4(w20_c)}",
         bool(w20 is not None and w20_c is not None and w20 >= w20_c)),
        ("M3", "mechanism", "Pearson ≥ S100c", f"{f4(pe)} vs {f4(pe_c)}",
         bool(pe is not None and pe_c is not None and pe >= pe_c)),
        ("M4", "mechanism", "|Δ(CATA÷SLIP)| ≤ S100c", f"{f4(d6_r)} vs {f4(d6_c)}",
         bool(d6_r is not None and d6_c is not None and d6_r <= d6_c)),
    ]

    out["rows"] = [{"id": r[0], "group": r[1], "name": r[2], "observed": r[3],
                    "verdict": (None if r[4] is None else bool(r[4]))} for r in rows]
    d_rows = [r for r in rows if r[1] == "absolute" and r[4] is not None]
    m_rows = [r for r in rows if r[1] == "mechanism" and r[4] is not None]
    d_pass = sum(1 for r in d_rows if r[4])
    m_pass = sum(1 for r in m_rows if r[4])
    if d_pass == len(d_rows):
        code = "SAMPLING_RULE_WAS_THE_CAUSE"
    elif m_pass >= 3:
        code = "PARTIAL_IMPROVEMENT"
    else:
        code = "SAMPLE_SIZE_DEPENDENT"
    out["per_experiment"]["S100r"] = {
        "d_total": len(d_rows), "d_passed": d_pass,
        "m_total": len(m_rows), "m_passed": m_pass,
        "all_d_pass": bool(d_pass == len(d_rows)),
    }
    out["verdict"] = {"code": code, "d_passed": d_pass, "d_total": len(d_rows),
                      "m_passed": m_pass, "m_total": len(m_rows),
                      "rule": prereg["verdict_rule"]}
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--iteration", type=int, default=19)
    ap.add_argument("--out-dir", type=Path, default=OUT)
    ap.add_argument("--allow-partial", action="store_true")
    ap.add_argument("--prereg-only", action="store_true")
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
    order = [e for e in ["S200", "S100c", "S100r"] if e in matrix]
    sources = []
    for eid in order:
        spec = matrix[eid]
        ls = locate(eid, spec)
        scale = float(spec["scale"])
        if ls:
            sources.append((eid, scale, ls))
            print(f"      {eid}: rule={spec['sampling_rule']:16s} SCALE={scale:.5f}  {ls.name}")
        else:
            print(f"      {eid}: linkstats MISSING -> 跳过（实验未完成？）")
    present_runs = [e for e, _, _ in sources if e == "S100r"]
    if not present_runs and not args.allow_partial:
        print("\nERROR: S100r linkstats 缺失；请先运行 run_sample_7_5b.py --experiments S100r")
        return 1

    print("[4/6] per-section backtest")
    saved = bt.SCALE
    parts = []
    for eid, scale, ls in sources:
        bt.SCALE = scale
        cw = cw_final.copy()
        cw["method"] = eid
        parts.append(ev1.backtest_one(eid, cw, obs, ls))
    bt.SCALE = saved
    backtest = pd.concat(parts, ignore_index=True)
    backtest.to_csv(args.out_dir / "sample_backtest_7_5b.csv", index=False, encoding="utf-8-sig")

    summary = ev1.summarize(backtest)
    summary.to_csv(args.out_dir / "sample_roadcat_summary_7_5b.csv", index=False, encoding="utf-8-sig")
    cmp_tbl = ev1.comparison_table(summary, args.iteration)
    cmp_tbl.to_csv(args.out_dir / "sample_comparison_7_5b.csv", index=False, encoding="utf-8-sig")

    print("[5/6] equivalence / linearity / preregistered check")
    sources_e = [(e, s, l) for e, s, l in sources if e != "S100r"] + \
                [(e, s, l) for e, s, l in sources if e == "S100r"]
    eq = ev75a.equivalence(backtest, sources_e, matrix)

    def row_of(eid, window="08-09"):
        z = cmp_tbl[(cmp_tbl["method"] == eid) & (cmp_tbl["window"] == window)]
        return z.iloc[0].to_dict() if not z.empty else {}

    headline = {}
    for eid, scale, _ in sources:
        d = row_of(eid)
        headline[eid] = {
            "scale": scale,
            "sampling_rule": matrix[eid]["sampling_rule"],
            "sample_agents": int(matrix[eid]["sample_agents"]),
            "f_cap": float(matrix[eid]["f_cap"]),
            "SimObs_all": clean(d.get("SimObs_all")),
            "WMAPE_all": clean(d.get("WMAPE_all")),
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

    pc = check_preregistered_b(eq, cmp_tbl, headline, PREREG_B)
    legacy = ev75a.decide(eq, headline)

    diag = None
    dfp = args.out_dir / "sampling_rule_diagnostics.json"
    if dfp.exists():
        diag = json.loads(dfp.read_text(encoding="utf-8"))

    # 敏感性口径（解析）：S100r 若改用 raw-EF 口径的 SCALE
    raw_scale = None
    sensitivity = None
    if diag:
        f_real = diag["at_100k"]["PURE_TRIPS_PROP"]["f_realized"]
        raw_scale = float(matrix["S100r"]["scale"]) * f_real
        pr = eq["pairs"].get("S100r", {})
        if pr.get("scaled_ratio_median") is not None:
            sensitivity = {
                "scale_raw_ef": raw_scale,
                "factor_vs_primary": f_real,
                "scaled_ratio_median_under_raw_ef": pr["scaled_ratio_median"] * f_real,
            }

    print("[5b/6] mechanism diagnostics (zero-flow / gap decomposition / trip distance)")
    mech = mechanism_diagnostics(backtest, sources, matrix, args.iteration)

    summary_json = {
        "step": "7.5B",
        "status": "PASS",
        "question": PREREG_B["question"],
        "single_variable": PREREG_B["single_variable"],
        "lambda_fixed": 0.075,
        "iterations": 20,
        "evaluated_iteration": args.iteration,
        "crosswalk": "7.3.6A Final Calibration Crosswalk",
        "observation": "7.1 frozen convention",
        "simulation": "median(matched MATSim edges HRSx-yavg) * SCALE(=ΣT/N_sample)",
        "headline_window": "08-09",
        "headline": headline,
        "equivalence_tests": eq,
        "preregistered_criteria": PREREG_B,
        "preregistered_check": pc,
        "verdict_7_5b": pc.get("verdict"),
        "legacy_verdict_rule_7_5a": legacy,
        "sampling_rule_diagnostics": diag,
        "scale_sensitivity_raw_ef": sensitivity,
        "mechanism_diagnostics_section8": mech,
        "parameters_changed": "sampling_rule_only",
        "lambda_selected": False,
    }
    (args.out_dir / "step7_5b_summary.json").write_text(
        json.dumps(summary_json, ensure_ascii=False, indent=2), encoding="utf-8")

    print("[6/6] write report")
    md = render_md(summary_json, sources, matrix, cmp_tbl, eq, pc, diag, sensitivity, mech)
    (args.out_dir / "STEP7_5B_REPORT.md").write_text(md, encoding="utf-8")

    print()
    print(json.dumps(headline, ensure_ascii=False, indent=2))
    if pc.get("available"):
        for r in pc["rows"]:
            v = "—" if r["verdict"] is None else ("PASS" if r["verdict"] else "FAIL")
            print(f"    {r['id']} [{v}] {r['name']}: {r['observed']}")
        print(f"\nVERDICT 7.5B: {pc['verdict']['code']} "
              f"(D {pc['verdict']['d_passed']}/{pc['verdict']['d_total']}, "
              f"M {pc['verdict']['m_passed']}/{pc['verdict']['m_total']})")
    print(f"Outputs: {args.out_dir}")
    return 0


# --------------------------------------------------------------------------
def mechanism_diagnostics(backtest, sources, matrix, iteration) -> dict:
    """§8 机制补充诊断（**不参与预注册判据**，只解释残差的物理来源）。

    (a) 观测断面零流量分布 —— 排除「部分断面直接归零」这一解释；
    (b) S100c → S100r 断面流量缺口分解 —— 归零断面 vs 全断面比例性收缩；
    (c) 平均行程距离（`*.traveldistancestats.csv`）—— 检验纯比例采样是否
        系统性剔除了长距离 OD 对（重力模型下 T_ij 最小 ⇔ c_ij 最大）。
    """
    out: dict = {"zero_flow_sections": {}, "gap_decomposition": None,
                 "mean_trip_distance": {}, "sum_obs_8_9": None,
                 "agg_SimObs_8_9": {}}
    if backtest is None or len(backtest) == 0:
        return out

    def _pivot(value_col):
        return backtest.pivot_table(index="lta_linkid", columns="method",
                                    values=value_col, aggfunc="median")

    raw = _pivot("sim_8_9_raw")
    scaled = _pivot("sim_8_9_scaled")
    obs = _pivot("obs_8_9")
    n = int(len(raw))
    for m in raw.columns:
        v = raw[m].fillna(0.0)
        z = int((v <= 0).sum())
        out["zero_flow_sections"][m] = {
            "n_sections": n, "zero": z,
            "zero_share": (z / n) if n else None,
            "sum_raw": float(v.sum()),
        }

    if {"S100c", "S100r"}.issubset(set(raw.columns)):
        a = raw["S100c"].fillna(0.0)
        b = raw["S100r"].fillna(0.0)
        d = a - b
        zeroed = (a > 0) & (b <= 0)
        tot = float(d.sum())
        out["gap_decomposition"] = {
            "sum_raw_gap_S100c_minus_S100r": tot,
            "zeroed_sections": int(zeroed.sum()),
            "zeroed_share_of_sections": float(zeroed.mean()),
            "gap_from_zeroed": float(d[zeroed].sum()),
            "gap_from_zeroed_share": (float(d[zeroed].sum()) / tot) if tot else None,
            "gap_from_proportional": float(d[~zeroed].sum()),
            "gap_from_proportional_share": (float(d[~zeroed].sum()) / tot) if tot else None,
        }
        if "obs_8_9" in obs.columns:
            o = obs["obs_8_9"]
            out["sum_obs_8_9"] = float(o.sum())
            if o.sum():
                out["agg_SimObs_8_9"] = {
                    m: float(scaled[m].fillna(0.0).sum() / o.sum()) for m in scaled.columns}

    for eid, _scale, ls in sources:
        # `locate()` 返回的是 ITERS/it.N 下的 linkstats 路径，需向上一路回溯到运行根目录
        d = Path(ls)
        hits: list = []
        for _ in range(5):
            if not d.parent or str(d.parent) == str(d):
                break
            d = d.parent
            hits = sorted(d.glob("*.traveldistancestats.csv"))
            if hits:
                break
        if not hits:
            continue
        try:
            dfd = pd.read_csv(hits[0], sep=";", encoding="utf-8-sig")
        except Exception:
            continue
        cand = [c for c in dfd.columns if "Trip distance" in c]
        tcol = cand[0] if cand else dfd.columns[-1]
        rec = {"file": hits[0].name, "it0": None, f"it{iteration}": None}
        for _, r in dfd.iterrows():
            try:
                it = int(r[dfd.columns[0]])
            except Exception:
                continue
            try:
                val = float(r[tcol])
            except Exception:
                continue
            if it == 0:
                rec["it0"] = val
            if it == iteration:
                rec[f"it{iteration}"] = val
        out["mean_trip_distance"][eid] = rec
    return out


def render_md(sj, sources, matrix, cmp_tbl, eq, pc, diag, sensitivity,
              mech=None) -> str:
    L = []
    L.append("# Step 7.5B — Sampling Rule Sensitivity：保底采样 vs 纯 trips-proportional\n")
    L.append("**零仿真**（仅读 linkstats）。核心机制问题：**100k 的残余非线性来自"
             "「样本数量不足」还是「保底采样规则的系统性空间偏差」？**\n")
    L.append("## 0. 结论\n")
    v7 = sj.get("verdict_7_5b")
    if v7:
        L.append(f"- **7.5B 判决：`{v7['code']}`**"
                 f"（D 组绝对判据 **{v7['d_passed']}/{v7['d_total']}**，"
                 f"M 组机制判据 **{v7['m_passed']}/{v7['m_total']}**）")
        L.append(f"- 判决规则：{v7['rule'].get(v7['code'], '')}\n")
    L.append("## 1. 三方正式评价表（窗口 08-09，Σsim/Σobs，it.%d）\n" % sj["evaluated_iteration"])
    L.append("| 实验 | 采样规则 | N_sample | f_cap | SCALE | Sim/Obs(all) | WMAPE | GEH<5 | GEH<10 | "
             "Pearson | Spearman | CATA | SLIP | CATA/SLIP |")
    L.append("|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
    for eid, h in sj["headline"].items():
        L.append(f"| **{eid}** | `{h['sampling_rule']}` | {h['sample_agents']:,} | {h['f_cap']:.2f} "
                 f"| {h['scale']:.5f} | {f4(h['SimObs_all'])} | {f4(h['WMAPE_all'])} "
                 f"| {f4(h['GEH_lt_5_all'])} | {f4(h['GEH_lt_10_all'])} | {f4(h['Pearson_all'])} "
                 f"| {f4(h['Spearman_all'])} | {f4(h['CATA_simobs'])} | {f4(h['SLIP_simobs'])} "
                 f"| {f4(h['CATA_over_SLIP'])} |")
    L.append("")
    L.append("> 口径：观测 7.1 冻结；仿真 `median(edges HRSx-yavg) × SCALE`，"
             "**三方 SCALE 使名义需求相同**（S200 2.29897 / S100c·S100r 4.59794）"
             "→ 差异只可能来自采样规则。\n")

    if diag:
        L.append("## 2. 采样规则诊断（零仿真，人口侧）\n")
        L.append(f"λ=0.075 正 OD cell 数 = **{diag['positive_od_cells']:,}**，"
                 f"ΣT = **{diag['real_car_od_total']:,.0f}**。\n")
        L.append("| N_sample | 采样规则 | sampled cells | zero-sampled | OD coverage | "
                 "ΣEF | `f_realized` | 保底 agent 占比 | agent min/中位/max |")
        L.append("|---:|---|---:|---:|---:|---:|---:|---:|---|")
        for target, key in ((100000, "at_100k"), (200000, "at_200k_reference")):
            for rule in ("FLOOR_PLUS_1", "PURE_TRIPS_PROP"):
                r = diag[key][rule]
                L.append(f"| {target:,} | `{rule}` | {r['sampled_od_cells']:,} | "
                         f"**{r['zero_sampled_od_cells']:,}** | {r['od_coverage']:.4f} | "
                         f"{r['sum_expansion_factor']:,.0f} | {r['f_realized']:.5f} | "
                         f"{r['floor_agent_share']*100:.1f}% | "
                         f"{r['agents_min']:.0f}/{r['agents_median']:.0f}/{r['agents_max']:.0f} |")
        L.append("")

    L.append("## 3. 线性度检验（raw 是否随样本量线性）\n")
    L.append("| 对比 | n 断面 | raw 比值中位 | raw 比值均值 | 期望 |")
    L.append("|---|---:|---:|---:|---:|")
    for eid in ("S100c", "S100r"):
        p = eq.get("pairs", {}).get(eid)
        if not p:
            continue
        L.append(f"| {eid} raw / S200 raw | {p['n_sections']:,} | "
                 f"{f4(p['linearity_raw_ratio_median'])} | {f4(p['linearity_raw_ratio_mean'])} | 0.5000 |")
    L.append("")
    L.append("## 4. ★等价性检验（100k×SCALE vs 200k×SCALE，逐断面）\n")
    L.append("| 对比 | n 断面 | 比值中位 | 比值均值 | ±10% 内 | ±20% 内 | Pearson | Spearman |")
    L.append("|---|---:|---:|---:|---:|---:|---:|---:|")
    for eid in ("S100c", "S100r"):
        p = eq.get("pairs", {}).get(eid)
        if not p:
            continue
        L.append(f"| {eid} / S200 | {p['n_sections']:,} | {f4(p['scaled_ratio_median'])} | "
                 f"{f4(p['scaled_ratio_mean'])} | {f4(p['scaled_ratio_within_10pct'])} | "
                 f"{f4(p['scaled_ratio_within_20pct'])} | {f4(p['pearson_scaled'])} | "
                 f"{f4(p['spearman_scaled'])} |")
    L.append("")
    L.append("| 对比 | Σsim(scaled) | Σobs | Σsim/Σobs |")
    L.append("|---|---:|---:|---:|")
    for eid in ("S100c", "S100r"):
        p = eq.get("pairs", {}).get(eid)
        if not p:
            continue
        L.append(f"| {eid} | {p['agg_sim_scaled_eid']:,.0f} | {p['agg_obs']:,.0f} | "
                 f"{f4(p['agg_SimObs_eid'])} |")
    L.append("")
    if sensitivity:
        L.append(f"> **敏感性口径**：若 S100r 改用 raw-EF 口径 `SCALE = ΣEF_sampled/N = "
                 f"{sensitivity['scale_raw_ef']:.5f}`（= 主口径 × {sensitivity['factor_vs_primary']:.5f}），"
                 f"则其 scaled 比值中位变为 **{sensitivity['scaled_ratio_median_under_raw_ef']:.4f}**"
                 f"（其余 scaled 量整体 ×{sensitivity['factor_vs_primary']:.5f}）。\n")
    L.append("## 5. 各窗口\n")
    L.append("| 实验 | 窗口 | Sim/Obs | CATA | SLIP | CATA/SLIP |")
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
    if pc.get("available") and pc.get("per_experiment", {}).get("S100r"):
        L.append("## 6. ★预注册判据逐条判定（跑前固定）\n")
        pr = pc["per_experiment"]["S100r"]
        L.append(f"**S100r** — D 组（绝对）**{pr['d_passed']}/{pr['d_total']}**，"
                 f"M 组（机制）**{pr['m_passed']}/{pr['m_total']}**\n")
        L.append("| ID | 组 | 判据 | 实测 | 判定 |")
        L.append("|---|---|---|---|---|")
        for r in pc["rows"]:
            v = "—（仅报告）" if r["verdict"] is None else ("**PASS**" if r["verdict"] else "**FAIL**")
            L.append(f"| {r['id']} | {r['group']} | {r['name']} | {r['observed']} | {v} |")
        L.append("")
    L.append("## 7. 判读\n")
    L.append("**① 动力学等价性**：比较 §3 中 S100c 与 S100r 的 `raw 比值中位` —— "
             "若 S100r 明显更接近 0.50，说明**保底规则**是采样非线性的来源；"
             "若基本不动，说明非线性来自样本量本身。")
    L.append("**② 扩样后等价性**：比较 §4 的 `scaled 比值中位 / ±10% / ±20% / Pearson / Spearman` "
             "与 §1 的 WMAPE / GEH。")
    L.append("**③ 结构是否保持**：比较 §5 三窗口 `CATA/SLIP` 是否同时稳定。\n")
    L.append("- 若 **`SAMPLING_RULE_WAS_THE_CAUSE`** → 保留 100k，但**改用纯 trips-proportional "
             "采样算法**（或等价的无保底实现）。")
    L.append("- 若 **`PARTIAL_IMPROVEMENT`** → 保底规则是残余偏差的**贡献来源之一**，"
             "但不足以让 100k 达标；需同时考虑采样算法与样本量。")
    L.append("- 若 **`SAMPLE_SIZE_DEPENDENT`** → 保底规则**不是**主因；"
             "此时（也只有此时）125k/150k/175k 的 knee 扫描才有意义。")
    L.append("- **λ 仍不冻结**（固定 0.075 仅为控制变量）；"
             "未动 capacity（`f_cap=0.50` 仅作采样一致性校正）。\n")
    if mech and mech.get("zero_flow_sections"):
        it = sj["evaluated_iteration"]
        L.append("## 8. ★机制补充诊断（**不参与判据**，解释残差来源）\n")
        L.append("**(a) 观测断面零流量分布（窗口 08-09，raw 未扩样）**\n")
        L.append("| 实验 | 断面数 | raw 零流量断面 | 占比 | Σraw |")
        L.append("|---|---:|---:|---:|---:|")
        for m, z in mech["zero_flow_sections"].items():
            L.append(f"| {m} | {z['n_sections']:,} | {z['zero']:,} | "
                     f"{f4(z['zero_share'])} | {z['sum_raw']:,.0f} |")
        L.append("")
        g = mech.get("gap_decomposition")
        if g:
            L.append("**(b) S100c → S100r 断面流量缺口分解**\n")
            L.append(f"- Σraw 差（S100c − S100r）= **{g['sum_raw_gap_S100c_minus_S100r']:,.0f}**")
            L.append(f"- 来自「S100c>0 但 S100r 归零」的断面：**{g['zeroed_sections']:,} 个**"
                     f"（{g['zeroed_share_of_sections']*100:.2f}%），贡献 "
                     f"**{g['gap_from_zeroed']:,.0f}**（占缺口 "
                     f"{g['gap_from_zeroed_share']*100:.2f}%）")
            L.append(f"- 来自其余断面的**比例性收缩**：**{g['gap_from_proportional']:,.0f}**"
                     f"（占缺口 {g['gap_from_proportional_share']*100:.2f}%）\n")
        mtd = mech.get("mean_trip_distance")
        if mtd:
            L.append(f"**(c) 平均行程距离（`*.traveldistancestats.csv`）**\n")
            L.append(f"| 实验 | it.0 | it.{it} |")
            L.append("|---|---:|---:|")
            for eid, r in mtd.items():
                a, b = r.get("it0"), r.get(f"it{it}")
                La = f"{a:,.1f} m" if a is not None else "—"
                Lb = f"{b:,.1f} m" if b is not None else "—"
                L.append(f"| {eid} | {La} | {Lb} |")
            L.append("")
            L.append("> 判读：若 `S100r` 的平均行程距离系统性短于 `S100c`，则纯 "
                     "trips-proportional 采样**剔除了长距离 OD 对**（重力模型下 `T_ij` "
                     "最小 ⇔ `c_ij` 最大），每条留存 trip 覆盖的链路更少 ⇒ 观测断面"
                     "总流量欠冲幅度**远超**需求质量（ΣEF）损失。\n")
    L.append("---\n")
    L.append("参照：`sampling_rule_summary.csv`（规则诊断）、`od_cell_sampling_rules.csv`"
             "（逐 cell：trips / 两规则 agent 数 / EF / 重构误差）。\n")
    return "\n".join(L)


if __name__ == "__main__":
    raise SystemExit(main())
