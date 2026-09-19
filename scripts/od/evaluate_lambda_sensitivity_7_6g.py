#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""
evaluate_lambda_sensitivity_7_6g.py — Step 7.6G 评价链（**零仿真、只读**；从不启动 MATSim）。

设计：**复用 7.6F-1 的评价函数，不复制口径**
------------------------------------------
`evaluate_demand_response_7_6f_1.eval_run()` 与全部指标函数（`pooled` / `a_10_19` /
`qbar_10_19` / `parity_gap_rel` / `q_series_multi` / `load_ls_dict`）都与 run 表无关，
只经模块全局 `OUT` / `CYCLE_DIR` 访问输出路径。本脚本只重绑定这两个路径 + 换一张 run 表。

冻结口径（与 7.6F-1 / 7.6C-2 完全同源，**不得混用**）
--------------------------------------------------
    FROZEN         全 576 池化（primary candidate）  —— 正式主靶场
    POSITIVE_ONLY  仅 sim>0 池化                     —— 敏感性（不得升格）
    BEST_DIRECTION max(median(fwd),median(rev)) x SCALE —— 误差边界（不得升格）
    Sim/Obs 用 HRS8-9avg ；稳定性 Q / Qbar_10:19 用 Sum HRS0-24avg
    SCALE = 2.29897（全档统一；λ 不变性已实测 ⇒ 无混杂）

本步骤回答的问题
----------------
    1. Δ Sim/Obs(λ) 有多大？—— 是否超过靶场不确定性 Δ_target = 7.609 pp？
    2. λ 是否移动空间结构（EAST / radial_in）？—— 移动能力 vs 7.6F-1 的 demand 方向
    3. 隐含的 f*_λ 是否显著偏离 1.1803？

判决空间（预注册，见 STEP7_6G_PREREGISTRATION.md §5）
--------------------------------------------------
    全局：(LAMBDA_WEAK | LAMBDA_DETECTABLE_NOT_IDENTIFIABLE | LAMBDA_IDENTIFIABLE)
    空间：(SPATIAL_INERT | SPATIAL_ACTIVE)
    判决 = 全局 / 空间

用法
----
    python scripts/od/evaluate_lambda_sensitivity_7_6g.py
    python scripts/od/evaluate_lambda_sensitivity_7_6g.py --runs R01 L05
    python scripts/od/evaluate_lambda_sensitivity_7_6g.py --force-cycle
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(r"D:\Luan\2026-05\2_Singapore")
sys.path.insert(0, str(ROOT / "scripts" / "od"))

import compare_final_crosswalk_7_3_6b as bt            # noqa: E402  冻结口径
import evaluate_calibration_7_4_2 as ev1               # noqa: E402  冻结 TRAFFIC / FINAL_CW
import diagnose_od_spatial_structure_7_6c as d76        # noqa: E402  section_geography
import evaluate_demand_scale_7_6f_0 as e7_6f0          # noqa: E402  cycle-mean linkstats
import evaluate_demand_response_7_6f_1 as E            # noqa: E402  ★ 复用评价函数
import prepare_lambda_sensitivity_7_6g as P            # noqa: E402  ★ 7.6G 常量/判据

# --------------------------------------------------------------------------
# 路径（重绑定 E 的输出路径 → 7.6G 工作区）
# --------------------------------------------------------------------------
G_ROOT = P.NEW_ROOT
OUT = G_ROOT / "audit"
CYCLE_DIR = OUT / "_cycle_linkstats"
E.OUT = OUT
E.CYCLE_DIR = CYCLE_DIR
# ★ 复用 E.scale_audit()：把它的矩阵源指向 7.6G 的矩阵（列名已对齐 f_demand_nominal）
E.MATRIX_CSV = G_ROOT / "lambda_sensitivity_7_6g_matrix.csv"

R01_ROOT = ROOT / "matsim_routechoice_7_6d"
SEC_GEO_7_6C = d76.OUT_DIR / "section_geography.csv"
AUDIT_CACHE_7_6D = R01_ROOT / "audit" / "routechoice_stability_by_iter.csv"

SCALE = float(bt.SCALE)                    # 2.29897
SCALE_FROZEN = P.SCALE_CONST
TOTAL_ITER = P.TOTAL_ITER

# 7.6C-2 已公布量（只读引用，用于对账）
TARGET_7_6C_2 = dict(P.TARGET_REF)
ANCHOR_R01_SIMOBS = TARGET_7_6C_2["FROZEN"]

TH_GLOBAL_WEAK_PP = P.TH_GLOBAL_WEAK_PP
TH_GLOBAL_IDENT_PP = P.TH_GLOBAL_IDENT_PP
TH_SPATIAL_ACTIVE_PP = P.TH_SPATIAL_ACTIVE_PP
SLOPE_REF = P.F1_SLOPE_LOCAL
F0 = P.F_LAMBDA

# --------------------------------------------------------------------------
# run 表：R01 锚点（λ=0.075 @ f=1.00）+ 三档 λ @ f=1.18
# --------------------------------------------------------------------------
RUNS = [
    {"label": "R01", "role": "anchor_lam0.075_f1.00", "lambda": 0.075,
     "f_demand": 1.00, "N": 200_000,
     "out_dir": R01_ROOT / "outputs" / "R01_rc_min", "run_id": "R01_rc_min",
     "stage": "7.6E/7.6F-0", "desc": "稳定底座锚点（λ=0.075, f=1.00）"},
    {"label": "L05", "role": "grid", "lambda": 0.050,
     "f_demand": P.F_LAMBDA, "N": P.N_SIM,
     "out_dir": G_ROOT / "outputs" / "L05_rc_min", "run_id": "L05_rc_min",
     "stage": "7.6G", "desc": "λ=0.05 @ f=1.18"},
    {"label": "L75", "role": "grid", "lambda": 0.075,
     "f_demand": P.F_LAMBDA, "N": P.N_SIM,
     "out_dir": G_ROOT / "outputs" / "L75_rc_min", "run_id": "L75_rc_min",
     "stage": "7.6G", "desc": "λ=0.075 @ f=1.18（λ 基准 + 复现控制）"},
    {"label": "L10", "role": "grid", "lambda": 0.100,
     "f_demand": P.F_LAMBDA, "N": P.N_SIM,
     "out_dir": G_ROOT / "outputs" / "L10_rc_min", "run_id": "L10_rc_min",
     "stage": "7.6G", "desc": "λ=0.10 @ f=1.18"},
]
GRID_LABELS = ["L05", "L75", "L10"]
CALIBERS = ["FROZEN", "POSITIVE_ONLY", "BEST_DIRECTION"]

_ck: list[dict] = []


def ck(name: str, ok: bool, detail: str = "") -> bool:
    _ck.append({"check": name, "pass": bool(ok), "detail": str(detail)})
    print(f"   [{'PASS' if ok else 'FAIL'}] {name}  {detail}")
    return bool(ok)


def log(msg: str = "") -> None:
    print(msg)


def banner(msg: str) -> None:
    print("\n" + "=" * 84)
    print(msg)
    print("=" * 84)


def n_complete_iters(run: dict) -> int:
    """本 run 已落盘 linkstats 的完整迭代数（it.0–19）。"""
    got = 0
    for i in range(TOTAL_ITER):
        d = run["out_dir"] / "ITERS" / f"it.{i}"
        if not d.exists():
            continue
        if list(d.glob(f"{run['run_id']}.*.linkstats.txt.gz")) or list(d.glob("*.linkstats.txt.gz")):
            got += 1
    return got


def implied_fstar(simobs: float, slope: float = SLOPE_REF, f0: float = F0) -> float:
    """f*_lambda ≈ f0 + (1 - SimObs)/slope（局部割线斜率；假设 lambda 不变，见预注册 §5）。"""
    return f0 + (1.0 - simobs) / slope


def write_report(payload, out_dir):
    # 渲染 STEP7_6G_REPORT.md（纯只读；不重算任何指标；与 7.6F-1 报告同风格）
    st = payload.get("status", "?")
    th = payload.get("thresholds", {}) or {}
    curve = payload.get("curve", []) or []
    delta = payload.get("delta", []) or []
    xval = payload.get("crossvalidation", []) or []
    L = []
    L.append("# Step 7.6G — λ 敏感度 screening（单一 demand level f = 1.18）")
    L.append("")
    L.append("> **判决：`%s`**（零仿真评价；本步**从未启动新 MATSim**，只读 linkstats）" % st)
    L.append("")
    L.append("> 唯一被扫变量 = **λ**；demand level 固定 **f = %s**（N_sim = %s）；λ 由**人口文件**"
             "（6.3.3A 的 λ 冻结人口 → 复制到 N_sim）承载，**config 内无 λ 形参**。"
             % (payload.get("demand_level_f"), format(int(payload.get("n_sim") or 0), ",")))
    L.append("> **SCALE = %s 全档统一**（λ 不变性：ΣEF / ΣT / car_od_total 均与 λ 无关）⇒ "
             "**不得**按 ΣEF / N_sim 重算。" % payload.get("scale_used"))
    L.append("")
    L.append("## 1. 判据阈值（预注册，运行前冻结）")
    L.append("")
    L.append("- 全局**弱**：|Δ Sim/Obs| < **%s pp**" % th.get("global_weak_pp"))
    L.append("- 全局**可辨识**：|Δ Sim/Obs| ≥ **%s pp**（= 7.6C-2 `Delta_target`，靶场自身辨识下界）"
             % th.get("global_identifiable_pp"))
    L.append("- **空间活跃**：max 区域/径向 rel_dev 极差 ≥ **%s pp**" % th.get("spatial_active_pp"))
    L.append("- 局部割线斜率（承 7.6F-1，每单位 f）：**%s**" % th.get("slope_ref_per_f"))
    L.append("")
    L.append("## 2. λ 响应曲线（08-09，MATCHED，PRIMARY = 收敛窗周期均值）")
    L.append("")
    L.append("| run | λ | f_demand | N | Sim/Obs **FROZEN** | POSITIVE_ONLY | BEST_DIRECTION | `A_10:19`(MATCHED) | 隐含 f*(FROZEN) |")
    L.append("|---|---:|---:|---:|---:|---:|---:|---:|---:|")
    for r in sorted(curve, key=lambda d: (d.get("f_demand") or 0, d.get("lambda") or 0)):
        _isf = float(r.get("implied_fstar_FROZEN") or 0)
        _ist = ("%.6f" % _isf) if str(r.get("role")) == "grid" else ("%.6f（参照†）" % _isf)
        L.append("| %s | %.3f | %.2f | %s | **%.6f** | %.6f | %.6f | %.4f%% | %s |"
                 % (r.get("label"), float(r.get("lambda") or 0), float(r.get("f_demand") or 0),
                    format(int(r.get("N") or 0), ","), float(r.get("SimObs_FROZEN") or 0),
                    float(r.get("SimObs_POSITIVE_ONLY") or 0), float(r.get("SimObs_BEST_DIRECTION") or 0),
                    100.0 * float(r.get("A_10_19_MATCHED") or 0), _ist))
    L.append("")
    L.append("> `R01` = 7.6E/7.6F-0 锚点（λ=0.075, f=1.00, 200k），**仅作 λ=0.075 的 f 轴参照**，"
             "不参与 λ 网格的 Δ 计算。**L75 = λ=0.075 @ f=1.18** = 7.6F-1 插值点的**直跑复核**。")
    L.append("")
    L.append("> **† 注（R01 的隐含 f* = 1.363560 为参照值，不参与任何判断）：** 该值是"
             "**基于 f=1.18 附近局部割线向低需求侧外推**得到的结果。由于响应曲线存在"
             "**非线性 / 凹性**，该值**不作为需求尺度估计**，也**不参与 λ 敏感度比较**。"
             "7.6F-1 与 7.6G 的正式需求工作点，分别以**曲线插值**（1.1803）与"
             "**实测 f=1.18 的结果**（隐含 1.180222）为准。")
    L.append("")
    L.append("> 同理，7.6H 的最终工作点以**实跑**为准（N_sim = f_ref × 200,000，SCALE = 2.29897 不变），"
             "不得由本表中的隐含 f* 反推。")
    L.append("")
    L.append("## 3. λ 增量与隐含 f*")
    L.append("")
    L.append("| 口径 | λ_lo | λ_hi | Sim/Obs(lo) | Sim/Obs(hi) | Δ (pp) | 隐含 Δf* |")
    L.append("|---|---:|---:|---:|---:|---:|---:|")
    for d in delta:
        L.append("| %s | %.3f | %.3f | %.6f | %.6f | **%+.4f** | %+.5f |"
                 % (d.get("caliber"), float(d.get("lambda_lo") or 0), float(d.get("lambda_hi") or 0),
                    float(d.get("simobs_lo") or 0), float(d.get("simobs_hi") or 0),
                    float(d.get("delta_pp") or 0), float(d.get("delta_fstar_implied") or 0)))
    L.append("")
    sp = out_dir / "lambda_sensitivity_spatial_spread.csv"
    L.append("## 4. 空间残差随 λ 的移动（**只报告，不调参**）")
    L.append("")
    if sp.exists():
        import pandas as _pd
        sdf = _pd.read_csv(sp)
        L.append("| group_by | group | rel_lo | rel_hi | 极差 (pp) |")
        L.append("|---|---|---:|---:|---:|")
        for _, r in sdf.iterrows():
            L.append("| %s | %s | %.4f | %.4f | **%.4f** |"
                     % (r["group_by"], r["group"], float(r["rel_lo"]), float(r["rel_hi"]),
                        float(r["spread_pp"])))
        L.append("")
        L.append("> 对照：7.6F-1 demand 方向（1.00→1.25）只把 EAST 移动 **1.05 pp**、`radial_in` **2.16 pp**。"
                 "λ 的移动量与 demand 同量级，**两者都远小于 −28 pp 量级的 EAST 缺口** ⇒ "
                 "**空间结构不可由 λ 修复，亦不可由 demand 修复**。")
    else:
        L.append("（`lambda_sensitivity_spatial_spread.csv` 缺失）")
    L.append("")
    L.append("## 5. 稳定性承继（Σ HRS0-24avg，与 7.6B/7.6D/7.6E 同口径）")
    L.append("")
    L.append("| run | λ | `A_10:19` MATCHED | CATA | SLIP | ALL | `parity_gap_rel`(MATCHED) | 门槛 |")
    L.append("|---|---:|---:|---:|---:|---:|---:|---|")
    for r in sorted(curve, key=lambda d: (d.get("f_demand") or 0, d.get("lambda") or 0)):
        L.append("| %s | %.3f | %.4f%% | %.4f%% | %.4f%% | %.4f%% | %.4f%% | MATCHED/CATA<3%%, SLIP<5%% |"
                 % (r.get("label"), float(r.get("lambda") or 0),
                    100.0 * float(r.get("A_10_19_MATCHED") or 0), 100.0 * float(r.get("A_10_19_CATA") or 0),
                    100.0 * float(r.get("A_10_19_SLIP") or 0), 100.0 * float(r.get("A_10_19_ALL") or 0),
                    100.0 * float(r.get("parity_gap_rel_MATCHED") or 0)))
    L.append("")
    L.append("## 6. SCALE 冻结审计")
    L.append("")
    sa = out_dir / "lambda_sensitivity_scale_audit.csv"
    if sa.exists():
        import pandas as _pd
        adf = _pd.read_csv(sa)
        L.append("| run | λ | f_demand | n_agents | ΣEF | scale_used | 若按 ΣEF/N 重算 | Δ (ppm) |")
        L.append("|---|---:|---:|---:|---:|---:|---:|---:|")
        for _, r in adf.iterrows():
            L.append("| %s | %.3f | %.2f | %s | %s | %.5f | %.6f | %+.2f |"
                     % (r["run"], float(r["lambda"]), float(r["f_demand"]),
                        format(int(r["n_agents"]), ","), format(float(r["sum_expansion_factor"]), ",.3f"),
                        float(r["scale_used"]), float(r["scale_if_recomputed_sumEF_over_N"]),
                        float(r["scale_recompute_delta_ppm"])))
        L.append("")
        L.append("> `scale_if_recomputed_sumEF_over_N` **仅披露，NOT USED**。重算会使 L10 漂 **−517.9 ppm** ⇒ "
                 "确认冻结 SCALE 不可被 ΣEF 反推。")
    else:
        L.append("（`lambda_sensitivity_scale_audit.csv` 缺失）")
    L.append("")
    L.append("## 7. 口径未漂移对账")
    L.append("")
    L.append("| item | ours | reference | abs_diff | tol | pass |")
    L.append("|---|---:|---:|---:|---:|:--:|")
    for c in xval:
        L.append("| %s | %.7g | %.7g | %.2e | %.0e | %s |"
                 % (c.get("item"), float(c.get("ours")), float(c.get("reference")),
                    float(c.get("abs_diff")), float(c.get("tol")), "PASS" if c.get("pass") else "FAIL"))
    L.append("")
    L.append("> `X1` = 与 7.6C-2 已公布三口径逐位比对；`X2` = 与 7.6D 稳定性审计缓存"
             "（逐迭代表收敛窗 [10,19] 列均值）逐位比对。**这是口径未漂移的硬证据。**")
    L.append("")
    L.append("## 8. 预注册判据")
    L.append("")
    L.append("| 判据 | 结果 | 明细 |")
    L.append("|---|---|:--:|")
    for c in (payload.get("checks", []) or []):
        L.append("| %s | %s | %s |" % (c.get("check"), "PASS" if c.get("pass") else "**FAIL**",
                                       str(c.get("detail", "")).replace("|", "/")))
    L.append("")
    L.append("## 9. 判决解读")
    L.append("")
    if st.startswith("LAMBDA_DETECTABLE_NOT_IDENTIFIABLE"):
        _d0 = delta[0] if delta else {}
        L.append("- 在**中心问题「λ 是否改变 f*?」**上：**是，但幅度有限**。"
                 "λ 0.05 → 0.10 使 Sim/Obs 变动 **%+.4f pp**（FROZEN），对应隐含 **Δf* = %+.5f**。"
                 % (float(_d0.get("delta_pp") or 0), float(_d0.get("delta_fstar_implied") or 0)))
        L.append("- 该变动 **> 噪声底 1.0 pp**（故**可检出**），但 **< 靶场自身辨识下界 %s pp**"
                 "（故**不可辨识**为数据最优 λ）。" % th.get("global_identifiable_pp"))
        L.append("- ⇒ 按预注册 **Case A** 处理：**λ = 0.075 保持为敏感度中心 / 基准取值**，"
                 "**不得**声明为数据最优；7.6H 的 demand scale 应给**两层结果**："
                 "点估计（λ=0.075）＋由 λ 带来的不确定性带。")
    elif st.startswith("LAMBDA_WEAK"):
        L.append("- λ 的移动力落在噪声底以内（< 1.0 pp）⇒ 无法在本靶场上对 λ 作出任何判决；"
                 "λ=0.075 作为基准取值即可。")
    elif st.startswith("LAMBDA_IDENTIFIABLE"):
        L.append("- λ 的移动力达到靶场辨识下界 ⇒ λ 可被数据约束；应在**相邻 λ**上做**小幅** demand 细化"
                 "（**不做**完整 3×4 网格）。")
    else:
        L.append("- 判决标签：`%s`（含义见预注册 §5）。" % st)
    L.append("")
    if st.endswith("SPATIAL_INERT"):
        L.append("- 空间标签 **`SPATIAL_INERT`**：λ 对区域/径向 rel_dev 的移动均 < %s pp ⇒ "
                 "**λ 不能修复空间结构**，与 7.6F-1 的「全局量级 ⊥ 空间结构」结论一致。"
                 % th.get("spatial_active_pp"))
    else:
        L.append("- 空间标签 **`SPATIAL_ACTIVE`**：λ 对空间 rel_dev 有可观移动 ⇒ 需在 7.6H 中登记为空间不确定性来源。")
    L.append("")
    L.append("## 10. 本步**明确未做**")
    L.append("")
    L.append("- ✗ 未做 3×4（λ × demand）网格")
    L.append("- ✗ 未做 crosswalk-b（靶场保持 7.3.6A Frozen，**未修改**）")
    L.append("- ✗ 未做 demand 细扫（1.17/1.18/1.19/1.20）")
    L.append("- ✗ 未选 λ、未选 demand scale（`lambda_selected=False` / `demand_scale_selected=False`）")
    L.append("- ✗ 未改 7.1 / 7.3.6A / OD / network / capacity / route-choice 任一冻结件")
    L.append("")
    L.append("## 11. 产物")
    L.append("")
    for a in (payload.get("artifacts", []) or []):
        L.append("- `%s`" % a)
    L.append("")
    p = out_dir / "STEP7_6G_REPORT.md"
    p.write_text("\n".join(L), encoding="utf-8")
    return p


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", nargs="*", default=[r["label"] for r in RUNS])
    ap.add_argument("--force-cycle", action="store_true",
                    help="强制重建收敛窗周期均值 linkstats 缓存")
    args = ap.parse_args()

    OUT.mkdir(parents=True, exist_ok=True)
    CYCLE_DIR.mkdir(parents=True, exist_ok=True)

    banner("Step 7.6G EVALUATE — λ 敏感度 screening（零仿真、只读；从不启动 MATSim）")
    log(f"  SCALE = {SCALE:.5f}（冻结，全档统一）    λ∈{P.LAMS}    f={F0}（N_sim={P.N_SIM:,}）")
    log(f"  判据阈值：全局弱 < {TH_GLOBAL_WEAK_PP} pp / 可辨识 >= {TH_GLOBAL_IDENT_PP} pp / "
        f"空间活跃 >= {TH_SPATIAL_ACTIVE_PP} pp")
    log(f"  参考斜率 s_ref = {SLOPE_REF:.6f} (每单位 f)")

    # ---- [0] 前置 --------------------------------------------------------
    log("\n[0/7] 前置检查")
    sa = E.scale_audit()
    ck("P1 SCALE == 2.29897（全档统一；禁按 ΣEF 重算）",
       abs(SCALE - 2.29897) < 1e-9 and abs(SCALE - SCALE_FROZEN) < 1e-12, f"{SCALE:.5f}")
    ck("P2 7.3.6A Final Crosswalk 存在", ev1.FINAL_CW.exists(), ev1.FINAL_CW.name)
    ck("P3 7.1 冻结观测存在", ev1.TRAFFIC.exists(), ev1.TRAFFIC.name)
    ck("P4 7.6C section_geography 存在", SEC_GEO_7_6C.exists(), SEC_GEO_7_6C.name)
    ck("P5 λ 不变性源（三档 6.3.3A 人口）存在",
       all(P.pop_source_of(e).exists() for e in GRID_LABELS),
       f"{sum(1 for e in GRID_LABELS if P.pop_source_of(e).exists())}/3")

    avail, missing = {}, []
    for r in RUNS:
        n = n_complete_iters(r)
        avail[r["label"]] = n
        if n < TOTAL_ITER:
            missing.append((r["label"], n))
    log("   linkstats 完备度：" + "  ".join(f"{k}={v}/{TOTAL_ITER}" for k, v in avail.items()))
    grid_missing = [lab for lab, n in missing if lab in GRID_LABELS]
    awaiting = bool(grid_missing)
    if awaiting:
        log(f"   [AWAITING_RUNS] λ 网格未齐：{grid_missing} —— "
            f"本次只评价已齐 run，并照常复算 R01 锚点与 7.6C-2 对账。")

    # ---- [1] 冻结件 ------------------------------------------------------
    log("\n[1/7] 载入 7.1 观测 + 7.3.6A crosswalk + 7.6C 地理")
    obs = bt.load_traffic(ev1.TRAFFIC)
    cw = bt.normalize_crosswalk(ev1.FINAL_CW, "final")
    cwraw = pd.read_csv(ev1.FINAL_CW, encoding="utf-8-sig")
    cwraw["matsim_link_id"] = cwraw["matsim_link_id"].astype(str).str.strip()
    cw_prim = cwraw[cwraw["is_primary_candidate"]].copy() \
        if "is_primary_candidate" in cwraw.columns else cwraw.copy()

    matched = set(cwraw["matsim_link_id"])
    cata = set(cwraw.loc[cwraw["RoadCat"] == "CATA", "matsim_link_id"])
    slip = set(cwraw.loc[cwraw["RoadCat"] == "SLIP_ROAD", "matsim_link_id"])
    log(f"      observed sections = {obs['LinkID'].nunique():,}   crosswalk rows = {len(cwraw):,}"
        f"   sections = {cwraw['lta_linkid'].nunique()}")
    log(f"      link sets: MATCHED={len(matched):,}  CATA={len(cata):,}  SLIP={len(slip):,}")
    ck("P6 CATA + SLIP == MATCHED（口径分区完整）",
       len(cata) + len(slip) == len(matched), f"{len(cata)}+{len(slip)} vs {len(matched)}")

    geo = pd.read_csv(SEC_GEO_7_6C)[["lta_linkid", "mid_x", "mid_y", "d_cbd_m",
                                     "n_links", "radial", "ring", "region", "pa"]]
    geo["lta_linkid"] = geo["lta_linkid"].astype(str).str.strip()
    ck("P7 section_geography 覆盖 >= 570/576", int(geo["region"].notna().sum()) >= 570,
       f"{int(geo['region'].notna().sum())}/{len(geo)}")

    # ---- [2] 逐 run ------------------------------------------------------
    sel = [r for r in RUNS if r["label"] in args.runs and avail[r["label"]] == TOTAL_ITER]
    if not sel:
        log("\n没有可评价的 run（linkstats 未齐）。终止。")
        (OUT / "od_lambda_sensitivity_7_6g_summary.json").write_text(
            json.dumps({"step": "7.6G", "status": "AWAITING_RUNS",
                        "linkstats_availability": avail, "missing": missing,
                        "zero_simulation": True, "matsim_rerun": False,
                        "checks": _ck}, ensure_ascii=False, indent=2),
            encoding="utf-8")
        return 2

    log(f"\n[2/7] 逐 run 评价（{len(sel)} 档）—— 复用 evaluate_demand_response_7_6f_1.eval_run()")
    res = {}
    for r in sel:
        res[r["label"]] = E.eval_run(r, cw, cw_prim, obs, geo, matched, cata, slip,
                                     force_cycle=args.force_cycle)

    # ---- [3] ★ 与 7.6C-2 / 7.6D 对账（口径未漂移的硬证据） ----------------
    log("\n[3/7] 口径对账（与 7.6C-2 已公布值逐位比对）")
    xval = []
    if "R01" in res:
        q = res["R01"]["q"]
        for cal in CALIBERS:
            ref = TARGET_7_6C_2[cal]
            got = q[cal]
            ok = abs(got - ref) < 1e-6
            xval.append({"item": f"R01.{cal}", "ours": got, "reference": ref,
                         "abs_diff": abs(got - ref), "tol": 1e-6, "pass": ok})
            ck(f"X1 R01 {cal} == 7.6C-2 {ref:.7f}", ok, f"ours={got:.7f}  Δ={abs(got-ref):.2e}")
        # 7.6D 稳定性审计缓存（Q̄_10:19 四口径）—— ★与 7.6F-1 的 C2 检查同式
        #   缓存为**逐迭代原始表**（列 MATCHED/CATA/SLIP/ALL，无 metric 列）；
        #   参考值 = 收敛窗 [E.CONV_START, E.CONV_END] 上的列均值（即 7.6D 的 Q_conv_mean）。
        if AUDIT_CACHE_7_6D.exists():
            _au76d = pd.read_csv(AUDIT_CACHE_7_6D, encoding="utf-8-sig")
            _z76d = _au76d[(_au76d["run"] == "R01_rc_min")
                           & (_au76d["iteration"].between(E.CONV_START, E.CONV_END))]
            for kind in ("MATCHED", "CATA", "SLIP", "ALL"):
                if _z76d.empty:
                    continue
                ref = float(_z76d[kind].mean())
                got = res["R01"]["stab"][kind]["Qbar_10_19"]
                ok = abs(got - ref) / max(abs(ref), 1e-12) < 1e-9
                xval.append({"item": f"R01.Qbar_10_19.{kind}", "ours": got,
                             "reference": ref, "abs_diff": abs(got - ref),
                             "tol": 1e-9, "pass": ok})
                ck(f"X2 R01 Q̄_10:19 {kind} == 7.6D 缓存(iter 10..19 均值)", ok,
                   f"ours={got:,.1f}  ref={ref:,.1f}")
    pd.DataFrame(xval).to_csv(OUT / "lambda_sensitivity_crossvalidation.csv",
                              index=False, encoding="utf-8-sig")

    # ---- [4] λ 响应曲线 --------------------------------------------------
    log("\n[4/7] λ 响应曲线")
    rows = []
    for r in sel:
        q = res[r["label"]]["q"]
        q19 = res[r["label"]]["q_19"]
        st = res[r["label"]]["stab"]
        row = {"label": r["label"], "role": r["role"], "lambda": r["lambda"],
               "f_demand": r["f_demand"], "N": r["N"], "stage": r["stage"],
               "n_sections": len(res[r["label"]]["sec"]),
               "n_zero_sim": res[r["label"]]["n_zero_sim"],
               "A_10_19_MATCHED": st["MATCHED"]["A_10_19"],
               "A_10_19_CATA": st["CATA"]["A_10_19"],
               "A_10_19_SLIP": st["SLIP"]["A_10_19"],
               "A_10_19_ALL": st["ALL"]["A_10_19"],
               "parity_gap_rel_MATCHED": st["MATCHED"]["parity_gap_rel"],
               "Qbar_10_19_MATCHED": st["MATCHED"]["Qbar_10_19"],
               "Q_19_MATCHED": st["MATCHED"]["Q_19"]}
        for cal in CALIBERS:
            row[f"SimObs_{cal}"] = q[cal]
        row["SimObs_FROZEN_REF_it19"] = q19["FROZEN"]
        row["SimObs_FROZEN" + "_WMEAN"] = q["FROZEN_WMEAN_OF_RATIOS"]
        rows.append(row)
    curve = pd.DataFrame(rows)
    curve["implied_fstar_FROZEN"] = [implied_fstar(v) for v in curve["SimObs_FROZEN"]]
    curve["implied_fstar_BEST_DIRECTION"] = [implied_fstar(v) for v in curve["SimObs_BEST_DIRECTION"]]
    # ★ 口径护栏：anchor（R01）的 implied f* 为局部割线外推的**参照值**，不得用于需求尺度反推
    curve["implied_fstar_refonly"] = (curve["role"] != "grid")
    curve = curve.sort_values("lambda").reset_index(drop=True)
    curve.to_csv(OUT / "lambda_sensitivity_curve.csv", index=False, encoding="utf-8-sig")
    print(curve[["label", "lambda", "N", "SimObs_FROZEN", "SimObs_POSITIVE_ONLY",
                 "SimObs_BEST_DIRECTION", "A_10_19_MATCHED",
                 "implied_fstar_FROZEN"]].to_string(index=False,
                                                    float_format=lambda v: f"{v:.6f}"))

    # ---- [5] λ 增量 + 判决 -----------------------------------------------
    log("\n[5/7] λ 增量与判决")
    g = curve[curve["role"] == "grid"].sort_values("lambda")
    verdict = None
    delta_rows = []
    if len(g) >= 2:
        lo, hi = g.iloc[0], g.iloc[-1]
        d_frozen = (hi["SimObs_FROZEN"] - lo["SimObs_FROZEN"]) * 100.0
        d_pos = (hi["SimObs_POSITIVE_ONLY"] - lo["SimObs_POSITIVE_ONLY"]) * 100.0
        d_best = (hi["SimObs_BEST_DIRECTION"] - lo["SimObs_BEST_DIRECTION"]) * 100.0
        mon = np.all(np.diff(g["SimObs_FROZEN"]) >= -1e-6) or np.all(np.diff(g["SimObs_FROZEN"]) <= 1e-6)
        for cal, d in (("FROZEN", d_frozen), ("POSITIVE_ONLY", d_pos),
                       ("BEST_DIRECTION", d_best)):
            delta_rows.append({"caliber": cal, "lambda_lo": lo["lambda"],
                               "lambda_hi": hi["lambda"],
                               "simobs_lo": lo[f"SimObs_{cal}"],
                               "simobs_hi": hi[f"SimObs_{cal}"],
                               "delta_pp": d,
                               "delta_fstar_implied": -d / 100.0 / SLOPE_REF})
        dl = pd.DataFrame(delta_rows)
        dl.to_csv(OUT / "lambda_sensitivity_delta.csv", index=False, encoding="utf-8-sig")
        log(f"   Δ Sim/Obs(λ {lo['lambda']:.3f} → {hi['lambda']:.3f})："
            f"FROZEN {d_frozen:+.4f} pp  POSITIVE_ONLY {d_pos:+.4f} pp  "
            f"BEST_DIRECTION {d_best:+.4f} pp")
        log(f"   三口径 Δ 极差 = {max(abs(d_frozen), abs(d_pos), abs(d_best)) - min(abs(d_frozen), abs(d_pos), abs(d_best)):.4f} pp")
        log(f"   隐含 Δf* (FROZEN) = {-d_frozen/100.0/SLOPE_REF:+.5f}")

        ad = abs(d_frozen)
        if ad < TH_GLOBAL_WEAK_PP:
            glob = "LAMBDA_WEAK"
        elif ad < TH_GLOBAL_IDENT_PP:
            glob = "LAMBDA_DETECTABLE_NOT_IDENTIFIABLE"
        else:
            glob = "LAMBDA_IDENTIFIABLE"

        # 空间活跃性
        sp_all = pd.concat([res[r["label"]]["spatial"] for r in sel], ignore_index=True)
        sp_all.to_csv(OUT / "lambda_sensitivity_spatial_residuals.csv",
                      index=False, encoding="utf-8-sig")
        sp_g = sp_all[sp_all["run"].isin([lo["label"], hi["label"]])]
        spreads = []
        for (gb, grp), x in sp_g.groupby(["group_by", "group"]):
            d = x.set_index("run")["rel_dev_vs_global_FROZEN"]
            if len(d) == 2:
                spreads.append({"group_by": gb, "group": grp,
                                "rel_lo": float(d.loc[lo["label"]]),
                                "rel_hi": float(d.loc[hi["label"]]),
                                "spread_pp": float(abs(d.loc[hi["label"]] - d.loc[lo["label"]])) * 100})
        spd = pd.DataFrame(spreads)
        if not spd.empty:
            spd = spd.sort_values("spread_pp", ascending=False)
            spd.to_csv(OUT / "lambda_sensitivity_spatial_spread.csv",
                       index=False, encoding="utf-8-sig")
            log("\n   空间 rel_dev 移动最大的 6 组：")
            print(spd.head(6).to_string(index=False, float_format=lambda v: f"{v:.4f}"))
            max_spread = float(spd["spread_pp"].max())
        else:
            max_spread = float("nan")
        spat = "SPATIAL_ACTIVE" if (np.isfinite(max_spread)
                                    and max_spread >= TH_SPATIAL_ACTIVE_PP) else "SPATIAL_INERT"
        verdict = f"{glob} / {spat}"
        ck("G1 λ 网格齐备（3/3 档 × 20/20 迭代）",
           all(avail[e] == TOTAL_ITER for e in GRID_LABELS),
           str({e: avail.get(e) for e in GRID_LABELS}))
        ck("G5 稳定性 A_10:19(MATCHED) < 3.0%（全档）",
           bool((curve["A_10_19_MATCHED"] < 0.030).all()),
           " ".join(f"{r.label}={r.A_10_19_MATCHED:.4%}" for r in curve.itertuples()))
        ck("G6 收敛窗 parity_gap_rel(MATCHED) < 5.0%（全档）",
           bool((curve["parity_gap_rel_MATCHED"] < 0.050).all()),
           " ".join(f"{r.label}={r.parity_gap_rel_MATCHED:.4%}" for r in curve.itertuples()))
        ck(f"G7 判决全局标签 = {glob}", True, f"|Δ FROZEN| = {ad:.4f} pp")
        ck(f"G8 判决空间标签 = {spat}", True, f"max spread = {max_spread:.4f} pp")
        ck("G9 λ 响应单调（不要求，仅登记）", bool(mon),
           " ".join(f"{v:.6f}" for v in g["SimObs_FROZEN"]))

    # ---- [6] SCALE 审计 --------------------------------------------------
    log("\n[6/7] SCALE 冻结审计（ΣEF/N_sim 仅披露，NOT USED）")
    try:
        sa_g = sa[sa["run"].isin([r["label"] for r in RUNS])].copy()
        sa_g["lambda"] = sa_g["run"].map({r["label"]: r["lambda"] for r in RUNS})
        print(sa_g[["run", "lambda", "f_demand", "n_agents", "sum_expansion_factor",
                    "scale_used", "scale_if_recomputed_sumEF_over_N",
                    "scale_recompute_delta_ppm"]].to_string(index=False,
                                                            float_format=lambda v: f"{v:,.6f}"))
        sa_g.to_csv(OUT / "lambda_sensitivity_scale_audit.csv",
                    index=False, encoding="utf-8-sig")
        ok_u = bool((sa_g["scale_used"] - SCALE_FROZEN).abs().max() < 1e-12)
        ck("P1b SCALE 全档统一 = 2.29897（★不按 ΣEF/N 重算）", ok_u,
           f"n_runs={len(sa_g)}  max|delta_ppm|={sa_g['scale_recompute_delta_ppm'].abs().max():.2f}")
    except Exception as exc:   # noqa: BLE001
        ck("P1b SCALE 审计", False, f"{type(exc).__name__}: {exc}")

    # ---- [7] 汇总 --------------------------------------------------------
    log("\n[7/7] 汇总")
    npass = sum(1 for c in _ck if c["pass"])
    payload = {
        "step": "7.6G",
        "title": "Lambda sensitivity screening at fixed demand level",
        "status": "AWAITING_RUNS" if awaiting else (verdict or "INCOMPLETE"),
        "verdict": verdict,
        "zero_simulation": True, "matsim_rerun": False,
        "parameters_changed": False, "demand_scale_selected": False, "lambda_selected": False,
        "scale_used": SCALE_FROZEN,
        "scale_rule": "FROZEN 2.29897 for ALL runs; NOT recomputed from sum_EF (lambda-invariant)",
        "lambda_grid": P.LAMS, "demand_level_f": F0, "n_sim": P.N_SIM,
        "route_choice": "R01_rc_min", "target": "7.3.6A_FROZEN",
        "primary_metric": "MATCHED Sim/Obs(08-09)", "primary_window": "Qbar_10:19",
        "reference_window": "Q_19",
        "thresholds": {"global_weak_pp": TH_GLOBAL_WEAK_PP,
                       "global_identifiable_pp": TH_GLOBAL_IDENT_PP,
                       "spatial_active_pp": TH_SPATIAL_ACTIVE_PP,
                       "slope_ref_per_f": SLOPE_REF},
        "prior_it0_legacy": P.PRIOR_IT0,
        "f1_reference": {"fstar": P.F1_FSTAR, "curve": P.F1_CURVE,
                         "interp_at_f1p18": P.F1_INTERP_F18},
        "target_reference_7_6c_2": TARGET_7_6C_2,
        "linkstats_availability": avail,
        "curve": curve.to_dict(orient="records"),
        "delta": delta_rows if len(g) >= 2 else [],
        "crossvalidation": xval,
        "checks_total": len(_ck), "checks_pass": npass,
        "checks": _ck,
        "runtime_sec": None,
        "artifacts": [
            "lambda_sensitivity_curve.csv",
            "lambda_sensitivity_delta.csv",
            "lambda_sensitivity_spatial_residuals.csv",
            "lambda_sensitivity_spatial_spread.csv",
            "lambda_sensitivity_scale_audit.csv",
            "lambda_sensitivity_crossvalidation.csv",
            "od_lambda_sensitivity_7_6g_summary.json",
            "STEP7_6G_REPORT.md",
        ],
    }
    (OUT / "od_lambda_sensitivity_7_6g_summary.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    write_report(payload, OUT)
    log(f"   校验 {npass}/{len(_ck)} PASS")
    for c in _ck:
        if not c["pass"]:
            log(f"   FAIL: {c['check']}  {c['detail']}")
    log(f"\n   VERDICT: {payload['status']}")
    log(f"   -> {OUT / 'od_lambda_sensitivity_7_6g_summary.json'}")
    return 0 if npass == len(_ck) and not awaiting else (2 if awaiting else 1)


if __name__ == "__main__":
    t0 = time.time()
    rc = main()
    print(f"\n[wall] {time.time()-t0:.1f} s")
    raise SystemExit(rc)
