#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""
prepare_final_workingpoint_7_6h.py — Step 7.6H：**最终工作点确定与独立验证**（第一层冻结 + 单跑
独立验证；**本文件只做「准备」**，点火需 `--run`）。

用户 2026-09-18 21:05 裁定（要点）
----------------------------------
7.6G 已闭环，**结论按现口径冻结**，不再在 λ 网格上消耗算力。7.6H **不是**「最终标定」，
也**不是**新一轮参数搜索，而是：

    「最终工作点确定 + 独立验证」

**第一层（先冻结，全部只读引用，不重估）**

| 项 | 冻结值 | 来源 |
|---|---|---|
| `λ_ref` | **0.075** | 7.6G 判 `LAMBDA_DETECTABLE_NOT_IDENTIFIABLE` ⇒ **敏感度中心 / 基准取值**，⛔ 不是「数据最优 λ」 |
| `f_demand,ref` | **1.180222** | 7.6G `L75` 直跑实测隐含 f\*（插值对照 1.1803，差 0.007%） |
| `N_base` | **200,000** | 采样基准（只作 SCALE 锚） |
| `N_sim` | **236,044** = round(1.180222 × 200,000) | 「物理加车」：被仿真 agent 数 = f × 200,000 |
| `SCALE` | **2.29897** = 459,794 / 200,000 | ★⛔ **不得改成 459,794 / 236,044**（见 §4 披露） |
| `f_cap` | **1.00** | 冻结，非性能旋钮 |
| route-choice | **R01_rc_min** | 7.6E 冻结 4 项（innovation 0.8 / [ReRoute 0.15, ChangeExpBeta 0.85] / lr 0.5 / randomness 0.0） |
| 靶场 | **7.3.6A Frozen Final Crosswalk** | 只读；要改须另立 7.3.6A-b |
| 迭代 | **20**（判据取 `it.19` linkstats） | 承 7.6E/7.6F-1/7.6G |

**第二层：一次独立 200k 最终验证**（`W01`，λ=0.075，N_sim=236,044）。

★ 关于 `N_sim` 的算术披露（透明化，避免口径隐患）
--------------------------------------------------
用户原文写 `N_sim ≈ 1.1802 × 200,000 ≈ 236,044`。逐位核算：

    1.1802   × 200,000 = 236,040
    1.180222 × 200,000 = 236,044.4  ->  round  236,044   ← 本步采用（对应 f\* 的 6 位精度）

⇒ 取 **236,044**（与用户给的 236,044 一致，且由**实测** f\*=1.180222 推出，而非四舍五入到
1.1802 的 236,040）。两者相差 **4 个 agent（0.0017%）**，记录在案但**不构成歧义**。

★ 与 7.6G `L75`（N_sim=236,000）的独立性说明
---------------------------------------------
7.6H `W01` 与 7.6G `L75` **不是同一个网格单元**：agent 数不同（236,044 vs 236,000）⇒
复制后的 `ΣEF` 分布不同 ⇒ 是**独立实例化**的一次运行，用途是
**H1 复现性校验**（而非再次扫 λ）。两者一致即证明工作点可复现。

★ 三层不确定带**不得合并**（用户硬约束）
---------------------------------------
| 层 | 区间 | 来源 | 性质 |
|---|---|---|---|
| 工作点 | `f* = 1.180222` | 7.6G `L75` 直跑 | 条件点估计（λ=0.075、7.3.6A 冻结靶场） |
| λ 敏感带 | `[1.1637, 1.1938]` | 7.6G λ=0.05 / 0.10 两端 | **动态响应**带来的不确定 |
| 静态靶场带 | `[1.06945, 1.16418]` | 7.6C-2 `TARGET_MARGINAL_COARSE_ONLY` | 靶场自身辨识不确定 |

⇒ **来源不同，⛔ 不得压成一个「最终置信区间」。**

复用纪律（**不复制任何公式/逻辑**）
-----------------------------------
本脚本以**单点重绑定**方式复用 7.6G 的准备机器：

    prepare_lambda_sensitivity_7_6g  (g76)
        .stage_population  ← 内部调 7.4.3 build_population（FLOOR_PLUS_1 复制机制）
        .build_config      ← make_config_6_3.build_one + 7.6D apply_min_patch（7.6E 冻结 rc）
        .validate          ← 7.6F-1 validate()（W1–W6）+ g76 的 L1–L5
        .write_provenance / .write_matrix / .write_lambda_invariance
        .run_matsim / .final_linkstats

只重绑：`NEW_ROOT / CONFIG_DIR / POP_ROOT / OUT_ROOT / LOG_DIR / AUDIT_DIR / SPEC / F_LAMBDA / N_SIM`。
⇒ 配置与 7.6G/R01 的差异必须**仍恰为 3 项白名单**（outputDirectory / runId / inputPlansFile）。

隔离原则
--------
**不修改** 7.1 / 7.3.6A / OD / network / capacity / route-choice / 6.3.3A 源人口任何冻结件。
全部产物落在独立目录 `matsim_final_7_6h/`。

用法
----
    python scripts/od/prepare_final_workingpoint_7_6h.py              # 造人口 + config + 验证 + 预注册（零仿真）
    python scripts/od/prepare_final_workingpoint_7_6h.py --smoke 2000
    python scripts/od/prepare_final_workingpoint_7_6h.py --run --heap 24g   # ★ 点火（1 跑，约 85 min）
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(r"D:\Luan\2026-05\2_Singapore")
sys.path.insert(0, str(ROOT / "scripts" / "od"))
sys.path.insert(0, str(ROOT / "scripts" / "matsim"))

import prepare_lambda_sensitivity_7_6g as g76  # noqa: E402  ★ 复用机器（不复制逻辑）

# --------------------------------------------------------------------------
# 7.6H 冻结层（全部只读引用；本步骤不重估任何一项）
# --------------------------------------------------------------------------
STEP = "7.6H"
NEW_ROOT = ROOT / "matsim_final_7_6h"

LAM_REF = 0.075                       # 7.6G 敏感度中心（⛔ 非数据最优 λ）
F_REF_MEASURED = 1.180222             # 7.6G L75 直跑实测隐含 f*
F_REF_INTERP = 1.1803                 # 7.6F-1 曲线插值（对照，非主值）
F_REF = F_REF_MEASURED
N_BASE = 200_000
N_SIM = int(round(F_REF * N_BASE))    # 236,044
N_SIM_ROUNDED_F = int(round(1.1802 * N_BASE))   # 236,040（披露用：四舍五入 f 的差异）
SCALE_CONST = g76.REAL_CAR_OD_TOTAL / N_BASE    # 2.29897（★不按 ΣEF/N_sim 重算）
SCALE_IF_RECOMPUTED = g76.REAL_CAR_OD_TOTAL / N_SIM
TOTAL_ITER = 20
EXPECTED_ITER = 19

# 三层不确定带（⛔ 不得合并）
BAND_LAMBDA = [1.1637, 1.1938]        # 7.6G λ 敏感带
BAND_STATIC_TARGET = [1.06945, 1.16418]   # 7.6C-2 静态靶场带

# H1–H5 判据阈值（预注册，运行前冻结）
TH = {
    "H1_simobs_abs_dev_from_1pp": 1.0,      # |Sim/Obs − 1.000| ≤ 1.0 pp（= 噪声底）
    "H1_fstar_dev": 0.005,                  # |implied f*_H − 1.180222| ≤ 0.005
    "H1_freal_dev": 0.001,                  # |f_realized − F_REF| ≤ 0.001
    "H1_vs_l75_pp": 1.0,                    # |Sim/Obs_H − Sim/Obs_L75| ≤ 1.0 pp（独立复现）
    "H2_A_matched_pct": 3.0,                # A_10:19(MATCHED) < 3.0%
    "H2_A_cata_pct": 3.0,                   # CATA < 3.0%
    "H2_A_slip_pct": 5.0,                   # SLIP < 5.0%
    "H2_parity_gap_pct": 5.0,               # parity_gap_rel(MATCHED) < 5.0%
    "H2_q19_over_qbar_dev_pct": 1.0,        # |Q_19/Q̄_10:19 − 1| ≤ 1.0%
    "H2_never_arrived": 0,                  # 承 7.6E G5（严格 0）
    "H2_max_stuck_car": 0,                  # 承 7.6E G5（严格 0）
    "H3_pattern_tol_pp": 2.0,               # 空间格局保持：|rel_dev_H − rel_dev_L75| ≤ 2.0 pp
}

SPEC = [("W01", LAM_REF, N_SIM)]          # ★ 单臂：最终工作点

# ---- 7.6G 已公布结果（只读引用，用于 H1/H3 对照） -------------------------
G76_L75 = {"label": "L75", "lambda": 0.075, "f_demand": 1.18, "N": 236_000,
           "SimObs_FROZEN": 0.9998291, "SimObs_POSITIVE_ONLY": 1.087887,
           "SimObs_BEST_DIRECTION": 1.038749, "implied_fstar_FROZEN": 1.180222}
G76_REFONLY = {"R01_implied_fstar": 1.363560,
               "note": "局部割线向低需求侧外推的参照值，⛔ 不作需求尺度估计、不参与 λ 比较"}

FROZEN_PAYLOAD = [
    ("lambda_ref", "0.075", "7.6G 敏感度中心（⛔ 非数据最优 λ）"),
    ("f_demand_ref", f"{F_REF}", "7.6G L75 直跑实测隐含 f*"),
    ("f_demand_interp", f"{F_REF_INTERP}", "7.6F-1 曲线插值（对照，非主值）"),
    ("N_base", f"{N_BASE:,}", "采样基准（仅作 SCALE 锚）"),
    ("N_sim", f"{N_SIM:,}", "round(f_ref × 200,000) ⇒ 物理加车"),
    ("SCALE", f"{SCALE_CONST:.5f}", "★ΣT/N_base；⛔ 不得改为 459,794/N_sim"),
    ("f_cap", "1.00", "冻结（非性能旋钮）"),
    ("route_choice", "R01_rc_min", "7.6E 冻结：innovation 0.8 / [ReRoute .15, ChangeExpBeta .85] / lr .5 / randomness 0"),
    ("iterations", f"{TOTAL_ITER}", f"判据取 it.{EXPECTED_ITER} linkstats"),
    ("target", "7.3.6A Frozen Final Crosswalk", "只读；要改须另立 7.3.6A-b"),
    ("primary_metric", "MATCHED Sim/Obs 08-09", "HRS8-9avg"),
    ("primary_window", "Qbar_10:19", "ΣHRS0-24avg（与 Sim/Obs 窗口⛔不可混用）"),
    ("reference_window", "Q_19", "同上"),
    ("band_lambda", "[1.1637, 1.1938]", "7.6G λ 敏感带（动态响应）"),
    ("band_static_target", "[1.06945, 1.16418]", "7.6C-2 静态靶场带（⛔ 不与 λ 带合并）"),
]


# --------------------------------------------------------------------------
# 重绑定：把 7.6G 机器指向 7.6H（单点重绑，函数体零修改）
# --------------------------------------------------------------------------
def rebind() -> None:
    g76.NEW_ROOT = NEW_ROOT
    g76.CONFIG_DIR = NEW_ROOT / "configs"
    g76.POP_ROOT = NEW_ROOT / "populations"
    g76.OUT_ROOT = NEW_ROOT / "outputs"
    g76.LOG_DIR = NEW_ROOT / "logs"
    g76.AUDIT_DIR = NEW_ROOT / "audit"
    g76.SPEC = SPEC
    g76.F_LAMBDA = F_REF
    g76.N_SIM = N_SIM
    # 供货架：L4b 用 F_LAMBDA 判 f_realized；本步骤期望 F_REF
    g76._ck_rows.clear()


# --------------------------------------------------------------------------
# 7.6H 专属产物（命名与 7.6G 区分；数值仍由 g76 写出后改名，保持可追溯）
# --------------------------------------------------------------------------
RENAME_MAP = {
    "lambda_sensitivity_7_6g_matrix.csv": "final_workingpoint_7_6h_matrix.csv",
    "lambda_sensitivity_7_6g_config_provenance.csv": "final_workingpoint_7_6h_config_provenance.csv",
    "lambda_sensitivity_7_6g_lambda_invariance.csv": "final_workingpoint_7_6h_source_invariance.csv",
}


def write_frozen_parameters(checks: list[dict], pop_rep: dict) -> Path:
    p = NEW_ROOT / "final_workingpoint_7_6h_frozen_parameters.csv"
    with open(p, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["item", "frozen_value", "source_or_rule"])
        for k, v, s in FROZEN_PAYLOAD:
            w.writerow([k, v, s])
        w.writerow([])
        w.writerow(["# 派生量（仅披露）", "", ""])
        w.writerow(["N_sim_if_f_rounded_to_1.1802", f"{N_SIM_ROUNDED_F:,}",
                    f"与采用值差 {N_SIM - N_SIM_ROUNDED_F} agent"])
        w.writerow(["SCALE_if_recomputed_sumEF_over_Nsim", f"{SCALE_IF_RECOMPUTED:.6f}",
                    f"Δ={((SCALE_IF_RECOMPUTED - SCALE_CONST) / SCALE_CONST * 1e6):+.0f} ppm ⇒ NOT USED"])
        w.writerow(["f_realized", f"{(pop_rep.get('sum_expansion_factor') or float('nan')) / g76.REAL_CAR_OD_TOTAL:.7f}",
                    "产物实测（ground truth）"])
        w.writerow(["sum_expansion_factor", f"{pop_rep.get('sum_expansion_factor')}", "复制后人口实测 ΣEF"])
        w.writerow(["checks", f"{sum(1 for c in checks if c['pass'])}/{len(checks)}", "零仿真校验"])
    return p


def write_preregistration(checks: list[dict], pop_rep: dict, mt_before: dict, mt_after: dict) -> Path:
    L = []
    A = L.append
    A("# Step 7.6H 预注册 — **最终工作点确定与独立验证**（不是「最终标定」，也不是参数搜索）\n")
    A(f"> 冻结时间：**{datetime.now().isoformat(timespec='minutes')}**  ")
    A("> 上游：7.6G 已闭环并**按现口径冻结**（`LAMBDA_DETECTABLE_NOT_IDENTIFIABLE / SPATIAL_INERT`），")
    A("> 本步**不在 λ 网格上继续消耗算力**，仅在**一个已确定的工作点**上做一次独立验证。\n")

    A("## 0. 第一层：冻结工作点（全部只读引用，本步骤不重估）\n")
    A("| 项 | 冻结值 | 来源 / 规则 |")
    A("|---|---|---|")
    for k, v, s in FROZEN_PAYLOAD:
        A(f"| `{k}` | **{v}** | {s} |")
    A("")
    A(f"> `N_sim = round({F_REF} × {N_BASE:,}) = **{N_SIM:,}**`；"
      f"若把 f 四舍五入为 1.1802 则得 {N_SIM_ROUNDED_F:,}（差 **{N_SIM - N_SIM_ROUNDED_F} agent**，均已披露）。")
    A(f"> **★SCALE 冻结披露**：若误按 `459,794 / {N_SIM:,}` 重算得 `{SCALE_IF_RECOMPUTED:.6f}`，"
      f"相对冻结值漂 **{((SCALE_IF_RECOMPUTED - SCALE_CONST) / SCALE_CONST * 1e6):+.0f} ppm** ⇒ **NOT USED**。")
    A("")

    A("## 1. 第二层：一次独立 200k 最终验证\n")
    A("| 项 | 值 |")
    A("|---|---|")
    A(f"| 实验臂 | `W01`（λ={LAM_REF}，唯一臂，⛔ 不扫 λ、不扫 demand） |")
    A(f"| 被仿真 agent | **{N_SIM:,}** |")
    A(f"| 配置 | `config_W01_rc_min.xml`（与 R01 差异须**恰为 3 项白名单**） |")
    A(f"| 迭代 | {TOTAL_ITER}（判据取 `it.{EXPECTED_ITER}` linkstats） |")
    A("| 与 7.6G `L75` 的关系 | **独立实例化**（agent 数 236,044 vs 236,000 ⇒ `ΣEF` 分布不同） |")
    A("")

    A("## 2. 本步只回答 5 个问题（H1–H5）与预注册判据\n")
    A("### H1｜可复现性（工作点是否复现 7.6G）\n")
    A("| 判据 | 阈值 | 说明 |")
    A("|---|---:|---|")
    A(f"| `\\|Sim/Obs_FROZEN − 1.000\\|` | ≤ **{TH['H1_simobs_abs_dev_from_1pp']} pp** | 达标即「总体量级匹配」 |")
    A(f"| `\\|implied f*_H − {F_REF}\\|` | ≤ **{TH['H1_fstar_dev']}** | 与 7.6G `L75` 直跑值一致 |")
    A(f"| `\\|f_realized − {F_REF}\\|` | ≤ **{TH['H1_freal_dev']}** | 人口产物实测 |")
    A(f"| `\\|Sim/Obs_H − Sim/Obs_L75\\|`（= {G76_L75['SimObs_FROZEN']}） | ≤ **{TH['H1_vs_l75_pp']} pp** | 独立复现 |")
    A(f"> ⛔ 参照值 `R01` 的隐含 f\\* = {G76_REFONLY['R01_implied_fstar']} **不参与 H1**：{G76_REFONLY['note']}。")
    A("")
    A("### H2｜稳定性（在最终工作点上是否重新产生不稳定）\n")
    A("| 判据 | 阈值 |")
    A("|---|---:|")
    for k, lab in (("H2_A_matched_pct", "`A_10:19`(MATCHED)"), ("H2_A_cata_pct", "`A_10:19`(CATA)"),
                   ("H2_A_slip_pct", "`A_10:19`(SLIP)"), ("H2_parity_gap_pct", "`parity_gap_rel`(MATCHED)"),
                   ("H2_q19_over_qbar_dev_pct", "`\\|Q_19/Q̄_10:19 − 1\\|`")):
        A(f"| {lab} | < **{TH[k]}%** |")
    A(f"| `never_arrived`（it.{EXPECTED_ITER}） | == **{TH['H2_never_arrived']}**（承 7.6E G5，严格 0） |")
    A(f"| `max_stuck_car`（it.{EXPECTED_ITER}） | == **{TH['H2_max_stuck_car']}**（承 7.6E G5，严格 0） |")
    A("")
    A("### H3｜空间残差是否仍然存在（**不追求消除**）\n")
    A("报告 `EAST / CENTRAL / NORTH / NORTH-EAST / radial_in / radial_out` 及关键 PA 的 `rel_dev`，")
    A("并与 7.6G `L75`（同工作点）、7.6F-1 的空间格局对照：\n")
    A(f"- 判据（**格局保持**）：每个分组的 `\\|rel_dev_H − rel_dev_L75\\|` ≤ **{TH['H3_pattern_tol_pp']} pp**")
    A("- 若保持 ⇒ 结论：**最终需求标定只解决总体量级，不改变既有空间结构残差**（`SPATIAL_RESIDUAL_PERSISTS`）")
    A("- ⛔ **不得**为「把空间误差消掉」而回头调 demand / λ（7.6F-1/7.6G 已证两者都压不平，且均 < 3 pp）")
    A("")
    A("### H4｜λ 敏感性边界（表述层硬约束）\n")
    A("最终报告**不得**只写「λ=0.075」，必须写成三层、且**三层来源不同不得合并**：\n")
    A("| 层 | 区间 / 值 | 来源 |")
    A("|---|---|---|")
    A(f"| 基准工作点 | `λ = {LAM_REF}`，`f* = {F_REF}` | 7.6G `L75` 直跑 |")
    A(f"| λ 敏感带 | `{BAND_LAMBDA}` | 7.6G λ=0.05/0.10 两端（**动态响应**不确定） |")
    A(f"| 静态靶场带 | `{BAND_STATIC_TARGET}` | 7.6C-2 `TARGET_MARGINAL_COARSE_ONLY` |")
    A("")
    A("### H5｜哪些问题**没有**解决（必须保留）\n")
    A("最终报告必须显式声明（而非「所有指标都很好」）：\n")
    A("> **总体交通量尺度已达到可接受的匹配水平，但 EAST / NE / radial 等空间残差仍然存在；"
      "其对需求尺度与 λ 的敏感性都较低，因此不宜通过继续调整需求尺度或 λ 强行消除。**\n")
    A("另须保留三项**本地不可定量**（须外部数据）：① 观测车型构成；② AM 峰占日通勤比重；③ 平均载客率。\n")

    A("## 3. 判决空间（预注册）\n")
    A("| 维度 | 取值 | 条件 |")
    A("|---|---|---|")
    A("| 主 | `WORKING_POINT_FROZEN_AND_REPRODUCIBLE` | H1 全过 且 H2 全过 |")
    A("| 主 | `WORKING_POINT_NOT_REPRODUCIBLE` | H1 有不过 |")
    A("| 主 | `WORKING_POINT_FROZEN_BUT_UNSTABLE` | H1 全过 且 H2 有不过 |")
    A("| 空间 | `SPATIAL_RESIDUAL_PERSISTS` | H3 全过（格局保持） |")
    A("| 空间 | `SPATIAL_SHIFTED` | H3 有不过（空间格局被改变 ⇒ 需登记） |")
    A("")

    A("## 4. 本步**明确不做**（用户 2026-09-18 21:05 裁定）\n")
    A("- ✗ **不再细搜 λ**（7.6G 已判 `DETECTABLE_NOT_IDENTIFIABLE`，边际收益已很低）")
    A("- ✗ **不再细化 demand grid**（不做 1.17/1.18/1.19/1.20 细扫，不做 3×4 λ×demand 网格）")
    A("- ✗ **不做** crosswalk-b（靶场保持 7.3.6A Frozen，**未修改**）")
    A("- ✗ 不改 7.1 / 7.3.6A / OD / network / capacity / route-choice 任一冻结件")
    A("- ✗ 不把 `POSITIVE_ONLY` / `BEST_DIRECTION` 升格为正式标定靶场")
    A("- ✗ 不把三层不确定带压成单一「最终置信区间」")
    A("")

    A("## 5. 冻结件未变（本步骤隔离性证据）\n")
    touched = [k for k in mt_before if mt_before[k] != mt_after.get(k)]
    A(f"- 监视冻结件 **{len(mt_before)}** 个；mtime 变化 **{len(touched)}** 个")
    if touched:
        for t in touched:
            A(f"  - ⚠️ {Path(t).name}")
    else:
        A("- ✅ 全部未变（mtime 逐项一致）")
    A("")

    A("## 6. 零仿真校验（复用 7.6G 机器）\n")
    A(f"共 **{len(checks)}** 项，PASS **{sum(1 for c in checks if c['pass'])}**。")
    fails = [c for c in checks if not c["pass"]]
    A("")
    if fails:
        A("| FAIL | detail |")
        A("|---|---|")
        for c in fails:
            A(f"| {c['check']} | {c['detail']} |")
    else:
        A("（全部通过）")
    A("")

    A("## 7. 产物\n")
    for a in ("final_workingpoint_7_6h_matrix.csv",
              "final_workingpoint_7_6h_frozen_parameters.csv",
              "final_workingpoint_7_6h_config_provenance.csv",
              "final_workingpoint_7_6h_source_invariance.csv",
              "final_workingpoint_7_6h_config_validation.json",
              "STEP7_6H_PREREGISTRATION.md",
              "README.md",
              "populations/pop_W01/…", "configs/config_W01_rc_min.xml",
              "outputs/W01_rc_min/…（run 后）", "audit/…（评价后）"):
        A(f"- `{a}`")
    A("")
    p = NEW_ROOT / "STEP7_6H_PREREGISTRATION.md"
    p.write_text("\n".join(L), encoding="utf-8")
    return p


def write_readme(status: str, npass: int, ntot: int) -> Path:
    p = NEW_ROOT / "README.md"
    p.write_text(f"""# matsim_final_7_6h — Step 7.6H **最终工作点确定与独立验证**

> 建立：{datetime.now().isoformat(timespec='seconds')}   状态：**{status}**（{npass}/{ntot} 零仿真校验）
> 上游：7.6G 判 `LAMBDA_DETECTABLE_NOT_IDENTIFIABLE / SPATIAL_INERT`，**结论已按现口径冻结**。

## 冻结工作点
| 项 | 值 |
|---|---|
| `λ_ref` | **{LAM_REF}**（敏感度中心；⛔ 非数据最优 λ） |
| `f_demand,ref` | **{F_REF}**（7.6G `L75` 直跑实测隐含 f\\*；插值对照 {F_REF_INTERP}） |
| `N_base` | **{N_BASE:,}** |
| `N_sim` | **{N_SIM:,}** = round(f_ref × 200,000) |
| `SCALE` | **{SCALE_CONST:.5f}** ★⛔ 不得改为 459,794/N_sim |
| `f_cap` | **1.00** |
| route-choice | **R01_rc_min**（7.6E 冻结 4 项） |
| 靶场 | **7.3.6A Frozen Final Crosswalk**（只读） |

## 唯一实验臂
`W01`（λ={LAM_REF}，N_sim={N_SIM:,}，{TOTAL_ITER} it）→ `outputs/W01_rc_min/`

## 本步只回答 5 个问题
- **H1 可复现性**：`Sim/Obs ≈ 1.000`，且与 7.6G `L75` = {G76_L75['SimObs_FROZEN']} 一致
- **H2 稳定性**：`A_10:19` / `parity_gap_rel` / `Q19/Q̄` / `never_arrived` / `max_stuck`
- **H3 空间残差仍存在**（**不追求消除**；只报告格局是否保持）
- **H4 λ 敏感性边界**：基准工作点 + λ 敏感带 `{BAND_LAMBDA}` + 静态靶场带 `{BAND_STATIC_TARGET}`（**三层不合并**）
- **H5 未解决问题**：总体量级达标，但 EAST/NE/radial 空间残差仍在，**不宜**由 demand/λ 强行消除

## 明确不做
不再细搜 λ / 不再细化 demand grid / 不做 crosswalk-b / 不改任何冻结件 / 不把三层带压成单点。

## 运行
```
python scripts/od/prepare_final_workingpoint_7_6h.py            # 准备（零仿真）
python scripts/od/prepare_final_workingpoint_7_6h.py --run --heap 24g   # 点火（1 跑）
python scripts/od/evaluate_final_workingpoint_7_6h.py          # 评价出 H1–H5（run 后）
```
""", encoding="utf-8")
    return p


# --------------------------------------------------------------------------
def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--heap", default="24g")
    ap.add_argument("--smoke", type=int, default=0)
    ap.add_argument("--gen-only", action="store_true")
    ap.add_argument("--run", action="store_true", help="点火（1 跑；需用户明确启动指令）")
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()

    rebind()
    for d in (g76.NEW_ROOT, g76.CONFIG_DIR, g76.POP_ROOT, g76.OUT_ROOT, g76.LOG_DIR, g76.AUDIT_DIR):
        d.mkdir(parents=True, exist_ok=True)

    print("=" * 84)
    print("Step 7.6H PREPARE — 最终工作点确定与独立验证（单臂，不扫参）")
    print("=" * 84)
    print(f"  λ_ref      : {LAM_REF}   （7.6G 敏感度中心，⛔ 非数据最优）")
    print(f"  f_ref      : {F_REF}  （插值对照 {F_REF_INTERP}）")
    print(f"  N_sim      : {N_SIM:,} = round({F_REF} × {N_BASE:,})")
    print(f"  SCALE      : {SCALE_CONST:.5f}  ★不按 ΣEF/N_sim 重算（否则漂 "
          f"{((SCALE_IF_RECOMPUTED - SCALE_CONST) / SCALE_CONST * 1e6):+.0f} ppm）")
    print(f"  f_cap      : {g76.F_CAP}   route-choice: R01_rc_min   {TOTAL_ITER} it")
    print(f"  λ 源人口   : {g76.POP_SRC_DIR}")
    print()

    mt_before = g76.snapshot_mtimes(g76.FROZEN_WATCH)
    for k, v in mt_before.items():
        print(f"  [frozen] {Path(k).name}: mtime={v}")

    eid = SPEC[0][0]
    n_target = N_SIM if not args.smoke else args.smoke

    print("\n[1/4] 复制人口（源 = 6.3.3A 的 λ=0.075 冻结人口）")
    pop_rep = g76.stage_population(eid, LAM_REF, n_target, force=args.force)
    print(f"   persons={pop_rep['persons']:,}  ΣEF={pop_rep['sum_expansion_factor']:.3f}  "
          f"f_realized={pop_rep['sum_expansion_factor'] / g76.REAL_CAR_OD_TOTAL:.7f}")

    print("\n[2/4] 生成 config（build_one + 7.6E 冻结 route-choice patch）")
    cfg_path, out_dir, meta = g76.build_config(eid, smoke=args.smoke)
    print(f"   -> {cfg_path.name}   out={meta['out_dir']}  last_iter={meta['last_iteration']}")

    print("\n[3/4] 严格验证（零仿真；复用 7.6G 机器：W1–W6 + L1–L5）")
    checks = g76.validate(cfg_path, eid, n_target, smoke=args.smoke)
    npass = sum(1 for c in checks if c["pass"])

    print("\n[4/4] 产物")
    m = g76.write_matrix({eid: pop_rep})
    prov = g76.write_provenance({eid: cfg_path})
    inv = g76.write_lambda_invariance()
    ren = []
    for src, dst in RENAME_MAP.items():
        s, d = g76.NEW_ROOT / src, g76.NEW_ROOT / dst
        if s.exists():
            s.replace(d)
            ren.append(dst)
    fp = write_frozen_parameters(checks, pop_rep)
    mt_after = g76.snapshot_mtimes(g76.FROZEN_WATCH)
    pre = write_preregistration(checks, pop_rep, mt_before, mt_after)
    ok_touch = not [k for k in mt_before if mt_before[k] != mt_after.get(k)]
    status = "PREPARED" if (npass == len(checks) and ok_touch) else "FAIL"
    rd = write_readme(status, npass, len(checks))
    for p in [*ren, fp, pre, rd]:
        print(f"   -> {Path(p).name if isinstance(p, str) else Path(p).relative_to(ROOT)}")

    payload = {
        "status": status, "step": STEP,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "design": "FINAL_WORKING_POINT_PLUS_INDEPENDENT_VALIDATION",
        "swept": None, "parameter_search": False,
        "lambda_ref": LAM_REF, "f_demand_ref": F_REF, "f_demand_interp": F_REF_INTERP,
        "n_base": N_BASE, "n_sim": N_SIM, "n_sim_if_f_rounded": N_SIM_ROUNDED_F,
        "scale_used": SCALE_CONST, "scale_rule": "FROZEN_NOT_RECOMPUTED",
        "scale_if_recomputed": SCALE_IF_RECOMPUTED,
        "f_cap": g76.F_CAP, "route_choice": "R01_rc_min", "iterations": TOTAL_ITER,
        "target": "7.3.6A_FROZEN", "primary_metric": "MATCHED_SimObs_08_09",
        "primary_window": "Qbar_10:19", "reference_window": "Q_19",
        "band_lambda": BAND_LAMBDA, "band_static_target": BAND_STATIC_TARGET,
        "bands_merged": False,
        "thresholds": TH, "g76_l75_reference": G76_L75, "r01_refonly": G76_REFONLY,
        "frozen_artifacts_untouched": ok_touch,
        "checks_total": len(checks), "checks_pass": npass,
    }
    vp = g76.NEW_ROOT / "final_workingpoint_7_6h_config_validation.json"
    vp.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(f"\n   校验 {npass}/{len(checks)} PASS   冻结件未变: {ok_touch}")
    for c in checks:
        if not c["pass"]:
            print(f"   FAIL: {c['check']}  {c['detail']}")
    print(f"   -> {vp.name}")
    print(f"\nPREPARE STATUS: {status}")

    if args.run:
        print("\n[run] 点火 W01（单跑）")
        t0 = time.time()
        rc = g76.run_matsim(cfg_path, "W01_rc_min_run.log", args.heap)
        ls = g76.final_linkstats(out_dir, meta["run_id"])
        print(f"   exit={rc}  耗时 {(time.time() - t0) / 60:.2f} min   "
              f"it.{EXPECTED_ITER} linkstats: {ls.name if ls else '** MISSING **'}")
        return 0 if (rc == 0 and ls) else 1
    return 0 if status == "PREPARED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
