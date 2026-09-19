#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""
prepare_calibration_experiments_7_4_1.py — Step 7.4.1 联合校准实验矩阵（设计，不启动 MATSim）。

定位
----
把 7.4「联合校准」的实验设计固化成**可复现的单一事实源**：一次运行即产出

    reports/od_calibration_7_4_1/calibration_experiment_matrix.csv
    reports/od_calibration_7_4_1/calibration_parameter_definition.json
    reports/od_calibration_7_4_1/STEP7_4_1_EXPERIMENT_DESIGN.md

后续 7.4.2 只读这张冻结实验表按 experiment_id 依次运行，避免"跑完一堆实验后才决定评价标准"。

设计要点
--------
* θ = { λ, flowCapacityFactor, route-choice(迭代/拥堵反馈) }，只开放这三个。
* λ ∈ {0.050, 0.075, 0.100}；f_cap ∈ {0.50, 0.75, 1.00}（storage=flow 同值，MATSim 2026 硬约束）。
* route choice 固定 20 iterations（lastIteration=19）——7.3.1 已证明迭代次数不是主要校准变量。
* 共 9 组；但**第一阶段只跑 E01–E03（λ=0.050）**，用 capacity 三档回答"capacity 是否只是总量杠杆"。

⚠️ randomSeed 一致性修正（重要）
--------------------------------
外部草案把 randomSeed 写成 `20260912`（疑似把"设计日期 2026-09-12"误当种子）。
项目**实测冻结值 = 4711**（make_config_6_3.py 硬编码，且 6.3.3B / capf_* / cf_it20 三份 config 均为 4711）。
为保持与 6.3.3B linkstats 及整条 7.x 评价链**可比**，本脚本以 **4711** 为准，并在 JSON 中
以 `random_seed_note` 字段披露外部草案的 20260912，避免静默改种。

用法
----
    python scripts/od/prepare_calibration_experiments_7_4_1.py
    python scripts/od/prepare_calibration_experiments_7_4_1.py --gen-only   # 同义（本脚本从不跑 MATSim）
"""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

ROOT = Path(r"D:\Luan\2026-05\2_Singapore")
OUT_DIR = ROOT / "reports" / "od_calibration_7_4_1"

# ---- 冻结输入（7.4 全程不动）------------------------------------------------
FROZEN = {
    "network": "network_cleaned.xml.gz",
    "population": "6.2B connected population",
    "departure_profile": "6.3.3A",
    "crosswalk": "7.3.6A Final Calibration Crosswalk",
    "od": "6.2B frozen OD",
    "mode": "car",
}

# ---- 唯一实验变量 -----------------------------------------------------------
LAMBDAS = [0.050, 0.075, 0.100]
CAPACITY_FACTORS = [0.50, 0.75, 1.00]
LAST_ITERATION = 19          # => 20 iterations
TOTAL_ITERATIONS = 20

# ---- 项目实测冻结种子（见 docstring 的修正说明）----------------------------
RANDOM_SEED = 4711
RANDOM_SEED_DRAFT = 20260912  # 外部草案值，仅披露，不采用

POPULATION_AGENTS = 200000
CAR_TRIP_EXPANSION = 2.29897   # = 459794 / 200000
ROUTING_ALGORITHM = "SpeedyALT"

EXPERIMENT_STATUS = "PLANNED"
PHASE1 = ["E01", "E02", "E03"]     # λ=0.050 三档 capacity
PHASE2 = ["E04", "E05", "E06", "E07", "E08", "E09"]


def build_matrix() -> list[dict]:
    rows = []
    idx = 0
    for lam in LAMBDAS:
        for f in CAPACITY_FACTORS:
            idx += 1
            rows.append(
                {
                    "experiment_id": f"E{idx:02d}",
                    "lambda": lam,
                    "capacity_factor": f,
                    "storage_capacity_factor": f,
                    "last_iteration": LAST_ITERATION,
                    "routing_algorithm": ROUTING_ALGORITHM,
                    "random_seed": RANDOM_SEED,
                    "population_agents": POPULATION_AGENTS,
                    "car_trip_expansion": CAR_TRIP_EXPANSION,
                    "crosswalk": FROZEN["crosswalk"],
                    "departure_profile": FROZEN["departure_profile"],
                    "network": FROZEN["network"],
                    "status": EXPERIMENT_STATUS,
                }
            )
    return rows


def build_param_definition() -> dict:
    return {
        "step": "7.4.1",
        "status": "PLANNED",
        "purpose": "Controlled joint calibration experiment design.",
        "frozen_inputs": {
            "network": FROZEN["network"],
            "population": FROZEN["population"],
            "departure_profile": FROZEN["departure_profile"],
            "crosswalk": FROZEN["crosswalk"],
            "od": FROZEN["od"],
            "mode": FROZEN["mode"],
            "random_seed": RANDOM_SEED,
        },
        "random_seed_note": (
            "外部草案列为 20260912（疑为设计日期误写）；项目实测冻结值为 4711"
            "（make_config_6_3.py 硬编码，6.3.3B/capf/cf config 一致）。"
            "为保持与 6.3.3B linkstats 及 7.x 评价链可比，本定义采用 4711。"
        ),
        "open_parameters": {
            "lambda": LAMBDAS,
            "flowCapacityFactor": CAPACITY_FACTORS,
            "storageCapacityFactor": "equal to flowCapacityFactor",
        },
        "route_choice": {
            "lastIteration": LAST_ITERATION,
            "total_iterations": TOTAL_ITERATIONS,
            "routingAlgorithm": ROUTING_ALGORITHM,
            "routingRandomness": 0.0,
            "timeAllocationMutator": False,
            "modeChoice": False,
        },
        "evaluation": {
            "windows": ["07-08", "08-09", "AM"],
            "metrics": [
                "Pearson_r",
                "Spearman_rho",
                "MAE",
                "RMSE",
                "WMAPE",
                "Bias",
                "SimObs",
                "GEH_lt_5",
                "GEH_lt_10",
            ],
            "roadcat": ["CATA", "SLIP_ROAD", "CATB", "CATC", "CATD", "CATE"],
            "structural_ratio": "CATA_SimObs / SLIP_ROAD_SimObs",
            "headline_window": "08-09",
        },
        "decision_rules": [
            "Do not select lambda based on a small difference in one metric.",
            "Global Sim/Obs improvement alone is insufficient.",
            "A candidate should improve overall error without materially worsening CATA/SLIP structure.",
            "Lambda is identifiable only if its advantage persists across capacity levels and windows.",
            "Otherwise lambda remains unfrozen.",
        ],
        "execution_policy": {
            "phase_1": "E01-E03 only, lambda=0.050.",
            "phase_2": "Run E04-E09 only if Phase 1 leaves unresolved discrimination.",
            "launch_full_grid": False,
        },
        "parameters_changed": False,
        "lambda_selected": False,
        "matsim_runs_started": False,
    }


DESIGN_MD = """# Step 7.4.1 — Joint Calibration Experiment Design

## Status
**PLANNED / DESIGN ONLY**

本步骤只固化实验矩阵，不启动 MATSim，不修改冻结输入。

## 1. 核心矩阵

λ ∈ {0.050, 0.075, 0.100}

flowCapacityFactor ∈ {0.50, 0.75, 1.00}

storageCapacityFactor 与 flowCapacityFactor 同步。

route choice 固定为 20 iterations（lastIteration=19）。

共 **9 组**核心实验。

## 2. 冻结输入

Final Calibration Crosswalk = 7.3.6A  
Departure Profile = 6.3.3A  
Network = network_cleaned.xml.gz  
OD / population = 6.2B  
randomSeed = 4711  ← 见下方一致性说明  
mode = car

> **randomSeed 一致性说明**：外部草案把 randomSeed 写成 `20260912`（疑似设计日期误写）。
> 项目**实测冻结值 = 4711**（`make_config_6_3.py` 硬编码，6.3.3B / capf_* / cf_it20 三份
> config 实测均为 4711）。为保持与 6.3.3B linkstats 及整条 7.x 评价链**可比**，本步骤
> 以 **4711** 为准。

## 3. 评价

窗口：07-08、08-09、AM。

指标：Pearson r、Spearman rho、MAE、RMSE、WMAPE、Bias、Sim/Obs、GEH<5、GEH<10。

重点道路类别：CATA、SLIP_ROAD、CATB、CATC、CATD、CATE。

结构指标：

    CATA Sim/Obs
    ----------------
    SLIP_ROAD Sim/Obs

## 4. 执行策略

第一阶段只运行 E01-E03（λ=0.050）。

只有第一阶段无法判别容量作用时，才继续 E04-E09。

不一次性启动完整九组，以避免在缺乏信息增益的情况下消耗大量 MATSim 计算资源。

## 5. 预注册判据

不能只因为总体 Sim/Obs 更接近 1 就认定模型更好。

候选方案需要同时改善总体误差，并保持或改善 CATA/SLIP 结构。

λ 只有在不同 capacity factor 下表现持续占优、且多个时间窗一致时才可以冻结。

## 6. 当前状态

parameters_changed = false  
lambda_selected = false  
matsim_runs_started = false
"""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--gen-only", action="store_true",
                    help="同义开关；本脚本从不运行 MATSim。")
    args = ap.parse_args()

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    matrix = build_matrix()

    # --- matrix.csv ------------------------------------------------------
    fields = list(matrix[0].keys())
    with open(OUT_DIR / "calibration_experiment_matrix.csv", "w",
              encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(matrix)

    # --- parameter_definition.json --------------------------------------
    pd_def = build_param_definition()
    with open(OUT_DIR / "calibration_parameter_definition.json", "w",
              encoding="utf-8") as f:
        json.dump(pd_def, f, ensure_ascii=False, indent=2)

    # --- design md -------------------------------------------------------
    (OUT_DIR / "STEP7_4_1_EXPERIMENT_DESIGN.md").write_text(
        DESIGN_MD, encoding="utf-8")

    print("=== Step 7.4.1 experiment matrix ===")
    print(f"  experiments : {len(matrix)}  (Phase1={len(PHASE1)}, Phase2={len(PHASE2)})")
    print(f"  randomSeed  : {RANDOM_SEED}  (draft was {RANDOM_SEED_DRAFT} -> overridden)")
    print(f"  lambda      : {LAMBDAS}")
    print(f"  f_cap       : {CAPACITY_FACTORS}  (storage=flow)")
    print(f"  iterations  : {TOTAL_ITERATIONS}  (lastIteration={LAST_ITERATION})")
    print(f"  out dir     : {OUT_DIR}")
    for r in matrix:
        tag = " <- Phase1" if r["experiment_id"] in PHASE1 else ""
        print(f"    {r['experiment_id']}  lam={r['lambda']:.3f}  "
              f"f={r['capacity_factor']:.2f}{tag}")
    print("STATUS: PASS (design only; no MATSim started)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
