#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""
prepare_calibration_phase2_7_4_2.py — Step 7.4.2 Phase 2：λ 灵敏度实验设计（零仿真，从不启动 MATSim）。

背景
----
Phase 1 已证明 capacity 是"总量杠杆 + 拥堵弹性的从属结构响应"，且 **f=1.00 全面占优**
（不存在更优 f<1.00）。故 Phase 2 **把 capacity 固定为 1.00**，只扫 λ。

θ 取值（本阶段）
--------------
    capacity_factor = storage_capacity_factor = 1.00   （固定）
    iterations      = 20（lastIteration=19，拥堵反馈开启）
    λ ∈ {0.025, 0.050, 0.075, 0.100}                   （唯一扫描变量）

⚠️ 编号映射（本脚本显式披露，务必对齐 7.4.1 冻结矩阵）
--------------------------------------------------
用户口述的 Phase 2 编号 E04/E05/E06/E07 与 **7.4.1 冻结矩阵** 的编号**不一致**：

| 用户 Phase 2 标签 | λ     | 本项目规范 ID | 说明 |
|---|---|---|---|
| E04 | 0.025 | **E10（新增）** | 7.4.1 矩阵无此 λ；**全链 population 缺失 -> BLOCKED** |
| E05 | 0.050 | **E03** | 7.4.1 矩阵 E03 = λ0.050/f1.00；**Phase 1 已完成，直接复用** |
| E06 | 0.075 | **E06** | 恰好一致：7.4.1 矩阵 E06 = λ0.075/f1.00 |
| E07 | 0.100 | **E09** | 7.4.1 矩阵 E09 = λ0.100/f1.00（矩阵 E07= λ0.100/**f0.50**，f<1.00 已退役） |

> 7.4.1 矩阵中所有 **f<1.00** 的行（E01/E02/E04/E05/E07/E08）在 Phase 1 后**退役**，不再运行。

λ=0.025 阻塞
-----------
`reports/matsim_departure_6_3_3a/` 仅存在 λ ∈ {0.050, 0.075, 0.100} 的 population。
要运行 λ=0.025，必须先补齐上游冻结链（**额外 λ，不改动既有 λ 产物**）：
    5A  build_prior_od.py            --lambdas 0.025
    5B  build_prior_od_5b.py         --lambdas 0.025
    5C1 build_prior_od_5c1.py        --lambdas 0.025
    6.2B build_matsim_population_6_2b.py --lambdas 0.025
    6.2B-connected prepare_connected_scenario.py（生成 connected population）
    6.3.3A build_departure_profile_6_3_3a.py --lambdas 0.025
本阶段**不自动执行**该链；是否补 λ=0.025 由用户决定。

产物
----
    reports/od_calibration_7_4_2/phase2_lambda_matrix.csv
    reports/od_calibration_7_4_2/phase2_parameter_definition.json
    reports/od_calibration_7_4_2/STEP7_4_2_PHASE2_DESIGN.md

用法
----
    python scripts/od/prepare_calibration_phase2_7_4_2.py
"""
from __future__ import annotations

import csv
import json
from pathlib import Path

ROOT = Path(r"D:\Luan\2026-05\2_Singapore")
OUT = ROOT / "reports" / "od_calibration_7_4_2"
POP_DIR = ROOT / "reports" / "matsim_departure_6_3_3a"

# 规范 ID 与 λ（Phase 2：capacity 固定 1.00）
SPEC = [
    # (canonical_id, lambda, user_label, status)
    ("E10", 0.025, "E04", "DEFERRED_BY_USER_DECISION"),
    ("E03", 0.050, "E05", "REUSE_PHASE1_E03"),
    ("E06", 0.075, "E06", "RUN"),
    ("E09", 0.100, "E07", "RUN"),
]

FIXED = {
    "capacity_factor": 1.0,
    "storage_capacity_factor": 1.0,
    "last_iteration": 19,
    "iterations": 20,
    "routing_algorithm": "SpeedyALT",
    "random_seed": 4711,
    "population_agents": 200000,
    "car_trip_expansion": 2.29897,
    "crosswalk": "7.3.6A Final Calibration Crosswalk",
    "departure_profile": "6.3.3A",
    "network": "network_cleaned.xml.gz",
}

# 用户决策（2026-09-14）：先跳过 λ=0.025，用现有三点 λ∈{0.050,0.075,0.100} 的趋势判断。
USER_DECISION = {
    "on_lambda_0p025": "skip_for_now",
    "note": "用户决定**先跳过 λ=0.025**，用现有三点 λ∈{0.050,0.075,0.100}（E03/E06/E09）的正式趋势判断 λ 的辨识力；"
            "若三点趋势显示确需拓展低端，再补齐上游冻结链新增 λ=0.025（E10）。",
    "decided_on": "2026-09-14",
}


def lam_tag(lam: float) -> str:
    return f"{lam:.3f}".replace(".", "p")


def pop_exists(lam: float) -> bool:
    return (POP_DIR / f"population_lambda_{lam_tag(lam)}.xml.gz").exists()


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)

    rows = []
    for eid, lam, user_label, status in SPEC:
        has_pop = pop_exists(lam)
        if status.startswith("DEFERRED"):
            eff_status = status
        else:
            eff_status = status if has_pop else "BLOCKED_NO_POPULATION"
        rows.append({
            "experiment_id": eid,
            "user_phase2_label": user_label,
            "lambda": lam,
            "capacity_factor": FIXED["capacity_factor"],
            "storage_capacity_factor": FIXED["storage_capacity_factor"],
            "last_iteration": FIXED["last_iteration"],
            "routing_algorithm": FIXED["routing_algorithm"],
            "random_seed": FIXED["random_seed"],
            "population_agents": FIXED["population_agents"],
            "car_trip_expansion": FIXED["car_trip_expansion"],
            "crosswalk": FIXED["crosswalk"],
            "departure_profile": FIXED["departure_profile"],
            "network": FIXED["network"],
            "population_file_exists": has_pop,
            "status": eff_status,
        })

    mpath = OUT / "phase2_lambda_matrix.csv"
    with open(mpath, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    blocked = [r for r in rows if r["status"] == "BLOCKED_NO_POPULATION"]
    deferred = [r for r in rows if r["status"] == "DEFERRED_BY_USER_DECISION"]
    runnable = [r for r in rows if r["status"] == "RUN"]

    definition = {
        "step": "7.4.2",
        "phase": 2,
        "purpose": "λ 灵敏度：capacity 固定 1.00、20 it，只扫 λ，检验 λ 是否同时改善总体量级 + CATA/SLIP 结构 + 断面误差",
        "sweep_variable": "lambda",
        "fixed": FIXED,
        "experiments": rows,
        "runnable_now": [r["experiment_id"] for r in runnable],
        "blocked": [r["experiment_id"] for r in blocked],
        "deferred": [r["experiment_id"] for r in deferred],
        "user_decision": USER_DECISION,
        "id_mapping_note": "用户口述 E04/E05/E06/E07 与 7.4.1 冻结矩阵编号不一致；本阶段采用规范 ID："
                           "λ0.025->E10（阻塞）、λ0.050->E03（复用）、λ0.075->E06、λ0.100->E09。"
                           "7.4.1 矩阵所有 f<1.00 行在 Phase 1 后退役。",
        "lambda_0p025_blocker": {
            "reason": "reports/matsim_departure_6_3_3a 仅有 λ∈{0.050,0.075,0.100} 的 population",
            "required_chain": [
                "build_prior_od.py --lambdas 0.025",
                "build_prior_od_5b.py --lambdas 0.025",
                "build_prior_od_5c1.py --lambdas 0.025",
                "build_matsim_population_6_2b.py --lambdas 0.025",
                "prepare_connected_scenario.py (connected population)",
                "build_departure_profile_6_3_3a.py --lambdas 0.025",
            ],
        },
        "parameters_changed": True,
        "lambda_selected": False,
        "matsim_runs_started": False,
    }
    (OUT / "phase2_parameter_definition.json").write_text(
        json.dumps(definition, ensure_ascii=False, indent=2), encoding="utf-8")

    md = []
    md.append("# Step 7.4.2 Phase 2 — λ 灵敏度实验设计（capacity 固定 1.00）\n")
    md.append("**本文件为 Phase 2 的单一事实源**（由 `prepare_calibration_phase2_7_4_2.py` 生成）。"
              "**从不启动 MATSim。**\n")
    md.append("## 1. 固定项\n")
    for k, v in FIXED.items():
        md.append(f"- `{k}` = {v}")
    md.append("")
    md.append("## 2. λ 扫描矩阵\n")
    md.append("| 规范 ID | 用户标签 | λ | capacity | 迭代 | population | 状态 |")
    md.append("|---|---|---:|---:|---:|---|---|")
    for r in rows:
        md.append(f"| **{r['experiment_id']}** | {r['user_phase2_label']} | {r['lambda']:.3f} "
                  f"| {r['capacity_factor']:.2f} | {r['last_iteration']+1} "
                  f"| {'✅' if r['population_file_exists'] else '❌ 缺失'} | {r['status']} |")
    md.append("")
    md.append("## 3. ⚠️ 编号映射（与 7.4.1 冻结矩阵对齐）\n")
    md.append("用户口述的 E04/E05/E06/E07 与 **7.4.1 冻结矩阵** 编号不一致，本阶段采用**规范 ID**：\n")
    md.append("- λ=0.025 → **E10（新增，用户决定先跳过）**；7.4.1 矩阵无此 λ。")
    md.append("- λ=0.050 → **E03**（7.4.1 矩阵既有；**Phase 1 已完成，直接复用**）。")
    md.append("- λ=0.075 → **E06**（7.4.1 矩阵既有，恰好一致）。")
    md.append("- λ=0.100 → **E09**（7.4.1 矩阵既有；矩阵 E07 = λ0.100/**f0.50** 属 f<1.00，已退役）。")
    md.append("- 7.4.1 矩阵所有 **f<1.00** 的行（E01/E02/E04/E05/E07/E08）在 Phase 1 后**退役**。\n")
    md.append("## 4. λ=0.025：现状 + 用户决策\n")
    md.append("`reports/matsim_departure_6_3_3a/` 仅存在 λ ∈ {0.050, 0.075, 0.100} 的 population。"
              "运行 λ=0.025 前需补齐上游冻结链（**新增 λ，不改既有产物**）：\n")
    for s in definition["lambda_0p025_blocker"]["required_chain"]:
        md.append(f"1. `{s}`")
    md.append("")
    md.append(f"**★用户决策（{USER_DECISION['decided_on']}）：先跳过 λ=0.025。** "
              f"{USER_DECISION['note']}\n")
    md.append("## 5. 预注册判据\n")
    md.append("- **不自行选 λ**：由 E03/E06/E09 的正式趋势决定候选区间。")
    md.append("- 若 λ 只改变总流量、`CATA/SLIP` 与 WMAPE/GEH 不随之改善 → λ 非结构杠杆 → 转 OD 总量/departure profile。")
    md.append("- 若 λ 同时改善量级与结构 → 进入 **Phase 3 λ 精细搜索**。\n")
    (OUT / "STEP7_4_2_PHASE2_DESIGN.md").write_text("\n".join(md), encoding="utf-8")

    print(f"[OK] {mpath}")
    print(f"[OK] {OUT / 'phase2_parameter_definition.json'}")
    print(f"[OK] {OUT / 'STEP7_4_2_PHASE2_DESIGN.md'}")
    print(f"runnable_now = {[r['experiment_id'] for r in runnable]}")
    print(f"deferred     = {[r['experiment_id'] for r in deferred]}")
    print(f"blocked      = {[r['experiment_id'] for r in blocked]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
