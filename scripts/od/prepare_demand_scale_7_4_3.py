#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""
prepare_demand_scale_7_4_3.py — Step 7.4.3：OD 总量 / car-trip demand scale 标定（设计，零仿真）。

回答的问题
----------
    E06（λ=0.075, f_cap=1.00, 20 it）下 Sim/Obs(all)=0.7070、CATA=0.7137、SLIP=0.6706 全面 <1。
    这 19–30% 的量级缺口，**是否主要来自机动车 OD 总需求规模不足**？

只改一个东西
------------
    f_demand ∈ {1.00, 1.10, 1.20, 1.25}
其余全部冻结：λ=0.075 / capacity=1.00 / 20 it / seed=4711 / network_cleaned /
7.3.6A Final Crosswalk / 7.1 观测靶场 / departure profile。

★★ 本步骤最关键的前置结论：缩放的到底是什么？★★
------------------------------------------------
读 `build_matsim_population_6_2b.py:411` 与 config 全文后确认：

| 量 | 定义 | Σ | MATSim 是否消费 | 能否作为"需求缩放"对象 |
|---|---|---|---|---|
| `expansion_factor` | `EF_ij = T_ij / N_ij`（每 agent 代表的真实车次） | **459,794 = 真实 car OD 总量** | ❌ 否（纯 person attribute） | 仅**算术**：缩放它只改后处理倍数，**不改任何仿真动力学** |
| `od_trips` | **`T_ij`**（该 cell 的车 OD 总量，**同 cell 每个 agent 写同一个值**） | Σ_cells N_ij·T_ij ≈ 4.2–4.5M，**随 λ 变、非需求量** | ❌ 否 | ❌ **不能**（它不是需求总量，只是"每 cell agent 数"的影子） |
| **agents（车辆）** | `<person>` / `<plan>` 中的出行者，每人 1 条 car leg | 200,000 | ✅ **是**（QSim 唯一消费的人口信息） | ✅ **唯一物理杠杆** |

推论（本步骤的方法论基石）：
1. 只缩放 `expansion_factor`（或 `od_trips`）而不动 agent 数 → 仿真的 `HRSx-yavg` **一个数都不会变**，
   只是把标定倍数 2.29897 换成 f×2.29897 → Sim/Obs **精确 ×f**、CATA/SLIP **完全不变**。
   这是"算术重标定"，不是需求实验。→ 本脚本把它作为 **A 系列参照（零仿真）** 一并输出，用来量化
   "若空间形态正确、仅总量偏小，本该看到什么"。
2. 要让需求增加**物理地**发生（改变拥堵、改变车辆数），必须**增加被仿真的车辆数（agent 数）**。
   → 本步骤主实验 = **D 系列（真实加车、跑 MATSim）**。
3. A 系列与 D 系列之差 = **拥堵弹性阻尼**（加车后网络饱和，流量不按比例上升的部分）。

为什么"ΣodTrips 随 λ 变化"不是异常
-----------------------------------
`od_trips / expansion_factor = N_ij`（该 cell 的 agent 数，中位 4、最大 114）。
所以 ΣodTrips = Σ_cells N_ij·T_ij —— 它随 λ 变化反映的是 **每 cell agent 数分布**的变化，
与"真实需求量"无关。真实需求量恒为 Σ EF = 459,794（6.2B 报告已证明逐 cell 守恒误差 < 1e-12）。

实现方式（见 run_demand_scale_7_4_3.py）
--------------------------------------
以 6.3.3A 冻结人口 `population_lambda_0p075.xml.gz` 为源，**按嵌套随机子集复制 agent**
（seed=20260912 的 permutation 前缀，D02⊂D03⊂D04），得到 N = 220k / 240k / 250k：
    * 每 agent 的 EF / home_link / work_link / departure end_time **逐字节不变** → 受控；
    * 复制概率对**每个 agent 相同** → 增量在空间上**无偏**（不会被"每 cell 保底 1 agent"扭曲）；
    * ΣEF 目标 = f × 459,794（实测值由评价器复核并披露）。

产物（reports/od_calibration_7_4_3/）
-----------------------------------
    demand_scale_matrix.csv             实验矩阵（本步骤单一事实源）
    demand_parameter_definition.json    固定项 / 机制结论 / 判据
    STEP7_4_3_DESIGN.md                 设计文档

用法
----
    python scripts/od/prepare_demand_scale_7_4_3.py
"""
from __future__ import annotations

import csv
import json
from pathlib import Path

ROOT = Path(r"D:\Luan\2026-05\2_Singapore")
OUT = ROOT / "reports" / "od_calibration_7_4_3"

# 人口源（6.3.3A 冻结出发时刻剖面）；λ 固定 0.075
LAMBDA_FIXED = 0.075
LAMBDA_TAG = "0p075"
POP_SOURCE = ROOT / "reports" / "matsim_departure_6_3_3a" / f"population_lambda_{LAMBDA_TAG}.xml.gz"
POP_SOURCE_CSV = (
    ROOT / "reports" / "matsim_departure_6_3_3a"
    / f"agent_departure_assignment_lambda_{LAMBDA_TAG}.csv"
)
POP_DIR_7_4_3 = ROOT / "reports" / "matsim_demand_7_4_3"

N_AGENTS_BASE = 200_000
REAL_CAR_OD_TOTAL = 459_794.0        # = Σ expansion_factor (6.2B 冻结)
DUPLICATION_SEED = 20260912          # 仅用于"复制哪些 agent"的选择，与 MATSim randomSeed 无关

FIXED = {
    "lambda": LAMBDA_FIXED,
    "capacity_factor": 1.00,
    "storage_capacity_factor": 1.00,
    "iterations": 20,
    "last_iteration": 19,
    "random_seed_matsim": 4711,
    "routing_algorithm": "SpeedyALT",
    "routing_randomness": 0.0,
    "network": "reports/matsim_network/network_cleaned.xml.gz",
    "population_source": str(POP_SOURCE.relative_to(ROOT)),
    "crosswalk": "7.3.6A Final Calibration Crosswalk",
    "observation_target": "7.1 frozen (weekday -> per-day mean -> median by LinkID x hour)",
    "departure_profile": "6.3.3A",
    "car_trip_expansion": REAL_CAR_OD_TOTAL / N_AGENTS_BASE,
    "duplication_seed": DUPLICATION_SEED,
}

# (experiment_id, f_demand, n_agents, status)
SPEC = [
    ("D01", 1.00, 200_000, "REUSE_E06"),
    ("D02", 1.10, 220_000, "RUN"),
    ("D03", 1.20, 240_000, "RUN"),
    ("D04", 1.25, 250_000, "RUN"),
]

MECHANISM = {
    "question": "缩放的到底是什么：expansionFactor / odTrips / agents？",
    "expansion_factor": {
        "definition": "EF_ij = T_ij / N_ij  (per-agent real car trips)",
        "sum": REAL_CAR_OD_TOTAL,
        "is_demand_total": True,
        "consumed_by_matsim": False,
        "effect_of_scaling_alone": "纯算术：Sim/Obs 精确 x f，CATA/SLIP 不变，仿真无变化",
    },
    "od_trips": {
        "definition": "T_ij  (the OD cell's total real car trips, duplicated onto every agent of the cell)",
        "sum_lambda_0p075": 4_326_638.562,
        "is_demand_total": False,
        "consumed_by_matsim": False,
        "note": "od_trips / expansion_factor = N_ij (agents per cell, median 4, max 114). "
                "ΣodTrips varies with lambda because the per-cell agent-count distribution "
                "changes, NOT because demand changes. It must NOT be used as a demand lever.",
    },
    "agents": {
        "definition": "<person>/<plan> travelers, 1 car leg each",
        "sum_lambda_0p075": N_AGENTS_BASE,
        "consumed_by_matsim": True,
        "effect_of_scaling": "物理：车辆数 x f -> 拥堵/路由真实响应；唯一有效需求杠杆",
    },
    "conclusion": "Demand scale is implemented by scaling the simulated vehicle/agent count; "
                  "expansionFactor / odTrips scaling alone is a no-op for the simulation.",
}

# A 系列：算术参照（零仿真），用于给出"仅总量偏小"的上界
ARITHMETIC_REFERENCE = {
    "kind": "arithmetic_reference",
    "base_method": "D01",
    "levels": [1.00, 1.10, 1.20, 1.25],
    "note": "multiply D01 sim by f_demand analytically; Sim/Obs scales exactly x f, "
            "CATA/SLIP invariant. Upper bound vs the physical D series.",
}


def pop_dir_of(eid: str) -> Path:
    return POP_DIR_7_4_3 / f"pop_{eid}"


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)

    rows = []
    for eid, f, n, status in SPEC:
        rows.append({
            "experiment_id": eid,
            "f_demand": f,
            "n_agents": n,
            "n_extra": n - N_AGENTS_BASE,
            "lambda": LAMBDA_FIXED,
            "capacity_factor": 1.00,
            "iterations": 20,
            "population_source": FIXED["population_source"],
            "population_target": str((pop_dir_of(eid) / f"population_lambda_{LAMBDA_TAG}.xml.gz").relative_to(ROOT)),
            "output_dir": str((ROOT / "reports" / "od_calibration_7_4_3" / f"{eid}_lam{LAMBDA_TAG}").relative_to(ROOT)),
            "status": status,
            "note": "复用 E06 linkstats（λ=0.075, f=1.00, 20 it）" if status == "REUSE_E06"
                    else f"复制 {n - N_AGENTS_BASE:,} 个 agent（嵌套子集，seed={DUPLICATION_SEED}）",
        })

    mpath = OUT / "demand_scale_matrix.csv"
    with open(mpath, "w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    definition = {
        "step": "7.4.3",
        "title": "OD total / car-trip demand scale calibration",
        "purpose": "Test whether the 19-30% network-wide under-loading (Sim/Obs ~0.67-0.71) "
                   "is mainly a shortfall of total car OD demand, rather than of lambda / "
                   "capacity / crosswalk (all previously ruled out or fixed).",
        "sweep_variable": "f_demand",
        "levels": [r["f_demand"] for r in rows],
        "fixed": FIXED,
        "mechanism": MECHANISM,
        "arithmetic_reference": ARITHMETIC_REFERENCE,
        "frozen_before_this_step": [
            "7.1 observation target",
            "7.3.6A Final Calibration Crosswalk",
            "network_cleaned.xml.gz",
            "capacity factor = 1.00 (Phase 1 verdict: f=1.00 dominates)",
            "simulation iterations = 20",
            "6.3.3A departure profile",
            "OD structure (lambda fixed at 0.075 for this sweep)",
            "randomSeed = 4711 / routingRandomness = 0",
        ],
        "decision_rules": [
            "若 D 系列 Sim/Obs(all) 随 f 上升并趋近 1，且 CATA/SLIP 仍接近 1、WMAPE/GEH 不恶化 "
            "→ 量级缺口主要是 OD 总量问题，可冻结 demand scale。",
            "若 D 系列接近 A 系列（算术上界）→ 网络未饱和，需求标定是纯量级问题。",
            "若 D 系列显著低于 A 系列 → 存在拥堵弹性阻尼：加车被饱和吸收，量级缺口不能只靠需求补齐。",
            "若仅总量改善而 CATA/SLIP 恶化 → 出现'总量对、空间错'，须回到 OD 空间结构 / λ / attraction。",
            "λ 继续不冻结；本步骤不自行选定 λ 或 f_demand。",
        ],
        "parameters_changed": True,
        "lambda_selected": False,
        "matsim_runs_in_prepare": False,
    }
    (OUT / "demand_parameter_definition.json").write_text(
        json.dumps(definition, ensure_ascii=False, indent=2), encoding="utf-8")

    md = []
    md.append("# Step 7.4.3 — OD 总量 / car-trip demand scale 标定（设计）\n")
    md.append("> 本文件由 `scripts/od/prepare_demand_scale_7_4_3.py` 生成，是本步骤的**单一事实源**。"
              "本步骤只做**设计 + 人口变体生成 + 仿真 + 评价**；不修改任何已冻结产物。\n")

    md.append("## 1. 要回答的唯一问题\n")
    md.append("E06（λ=0.075, f_cap=1.00, 20 it）下 `Sim/Obs(all)=0.7070`、`CATA=0.7137`、"
              "`SLIP_ROAD=0.6706` 全面 <1。这 19–30% 的量级缺口，"
              "**是否主要来自机动车 OD 总需求规模不足？**\n")

    md.append("## 2. ★ 前置结论：缩放的到底是什么（本步骤的方法论基石）\n")
    md.append("| 量 | 定义 | Σ | MATSim 消费 | 能否作为需求缩放对象 |")
    md.append("|---|---|---:|---|---|")
    md.append(f"| `expansion_factor` | `EF_ij = T_ij / N_ij`（每 agent 代表的真实车次） | "
              f"**{REAL_CAR_OD_TOTAL:,.0f} = 真实 car OD 总量** | ❌ 否 | 仅**算术**，不改仿真 |")
    md.append(f"| `od_trips` | `T_ij`（cell 车 OD 总量，复制给该 cell 每个 agent） | "
              f"约 4.2–4.5M（**随 λ 变，非需求量**） | ❌ 否 | ❌ **不能** |")
    md.append(f"| **agents（车辆）** | `<person>`/`<plan>`（每人 1 条 car leg） | "
              f"**{N_AGENTS_BASE:,}** | ✅ **是** | ✅ **唯一物理杠杆** |")
    md.append("")
    md.append("**推论**：\n")
    md.append("1. 只缩放 `expansion_factor` / `od_trips` → 仿真的 `HRSx-yavg` 完全不变，"
              "只是把标定倍数换成 f×2.29897 → `Sim/Obs` **精确 ×f**、`CATA/SLIP` **完全不变**。"
              "这是**算术重标定**，不是需求实验 → 本步骤作为 **A 系列参照（零仿真）**输出。")
    md.append("2. 需求要**物理地**增加，必须**增加被仿真的车辆数（agent 数）** → 本步骤主实验 = "
              "**D 系列（真实加车、跑 MATSim）**。")
    md.append("3. **A 系列 − D 系列 = 拥堵弹性阻尼**（网络饱和导致流量不按比例上升的部分）。\n")
    md.append("**ΣodTrips 随 λ 变化不是异常**：`od_trips / expansion_factor = N_ij`"
              "（cell 内 agent 数，中位 4、最大 114）→ ΣodTrips 只反映"
              "**每 cell agent 数分布**，真实需求量恒为 `Σ EF = 459,794`（6.2B 逐 cell 守恒误差 < 1e-12）。\n")

    md.append("## 3. 冻结项（本步骤一律不动）\n")
    md.append("```text")
    md.append("7.1 观测靶场             不变")
    md.append("7.3.6A Final Crosswalk   不变")
    md.append("network_cleaned.xml.gz   不变")
    md.append("capacity factor          1.00")
    md.append("simulation iterations    20")
    md.append("departure profile        6.3.3A")
    md.append("randomSeed / routingRand 4711 / 0.0")
    md.append("λ                        固定 0.075（不冻结，但本轮不扫）")
    md.append("```\n")

    md.append("## 4. 实验矩阵\n")
    md.append("| Exp | f_demand | agents | 新增 | λ | f_cap | it | 状态 |")
    md.append("|---|---:|---:|---:|---:|---:|---:|---|")
    for r in rows:
        md.append(f"| **{r['experiment_id']}** | {r['f_demand']:.2f} | {r['n_agents']:,} | "
                  f"{r['n_extra']:,} | {r['lambda']:.3f} | {r['capacity_factor']:.2f} | {r['iterations']} | {r['status']} |")
    md.append("")
    md.append("> `D01` ≡ `E06`，**直接复用 Phase 2 结果，不重新仿真**。\n")

    md.append("## 5. 人口变体怎么造（受控性）\n")
    md.append(f"以 6.3.3A 冻结人口为源，按 **seed={DUPLICATION_SEED} 的 permutation 前缀**做"
              "**嵌套随机子集复制**（D02 ⊂ D03 ⊂ D04）：\n")
    md.append("- 每 agent 的 `expansionFactor` / `home_link` / `work_link` / departure `end_time` "
              "**逐字节不变** → 唯一变化 = 车辆数；")
    md.append("- 复制概率对**每个 agent 相同** → 增量在空间上**无偏**"
              "（不会被「每 cell 保底 1 agent」扭曲，这是逐 cell 按比例复制做不到的）；")
    md.append(f"- 目标 `Σ EF = f × {REAL_CAR_OD_TOTAL:,.0f}`，**实测值由评价器复核并披露**。\n")

    md.append("## 6. 预注册判据\n")
    for i, rule in enumerate(definition["decision_rules"], 1):
        md.append(f"{i}. {rule}")
    md.append("")

    md.append("## 7. 产物\n")
    md.append("```text")
    md.append("reports/od_calibration_7_4_3/")
    md.append("├── demand_scale_matrix.csv")
    md.append("├── demand_parameter_definition.json")
    md.append("├── STEP7_4_3_DESIGN.md")
    md.append("├── demand_run_manifest.json                  （运行后）")
    md.append("├── demand_scale_backtest.csv                 （评价后）")
    md.append("├── demand_scale_roadcat_summary.csv")
    md.append("├── demand_scale_comparison.csv               ★ f × 指标")
    md.append("├── step7_4_3_summary.json")
    md.append("└── STEP7_4_3_REPORT.md")
    md.append("```\n")

    (OUT / "STEP7_4_3_DESIGN.md").write_text("\n".join(md), encoding="utf-8")

    print(f"[OK] {mpath}")
    print(f"[OK] {OUT / 'demand_parameter_definition.json'}")
    print(f"[OK] {OUT / 'STEP7_4_3_DESIGN.md'}")
    print(f"levels = {[r['f_demand'] for r in rows]}")
    print(f"run    = {[r['experiment_id'] for r in rows if r['status'] == 'RUN']}")
    print(f"reuse  = {[r['experiment_id'] for r in rows if r['status'] == 'REUSE_E06']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
