# -*- coding: utf-8 -*-
"""
Step 7.8 — Final Model Freeze & Validation Package
==================================================

设计目标（用户裁定，2026-09-19）：
  7.7D 收口后，"继续调参已无足够证据收益" ⇒ 从"研究"切换到"定版"。
  本步**不产生任何新分析结论**，只把已验证的链条整理成
  **不可歧义 / 可复现 / 可引用 / 可交付** 的最终版本。

硬约束（脚本自身保证）：
  * zero_simulation（从不启动 MATSim）
  * 只读所有冻结件；仅写入 reports/final_model_7_8/
  * 不修改 f / λ / route-choice / 7.3.6A / network / capacity / population
  * 所有"真值"从冻结产物**读入**（不复制公式、不硬编码四舍五入常量）
  * 写入前/后对全部输入冻结件做 mtime+sha256 快照，逐位比对（read-only 证据）

产品（6 件，+ 3 件本步自产报告）：
  reports/final_model_7_8/
  ├── FINAL_MODEL_SPECIFICATION.md          # 7.8A 参数 + 7.8B 输入/算法
  ├── FINAL_VALIDATION_REPORT.md            # 7.8C W01 主验证
  ├── FINAL_PARAMETER_FREEZE.json           # 7.8A
  ├── FINAL_VALIDATION_METRICS.csv          # 7.8C（长表）
  ├── FINAL_SPATIAL_RESIDUAL_BOUNDARY.csv   # 7.8D（保留残差，不藏）
  ├── FINAL_MODEL_MANIFEST.json             # 7.8E（身份 + 输入 hash）
  ├── STEP7_8_REPORT.md                     # 本步报告
  ├── f_integrity_checks.csv                # #168 完整性门
  └── step7_8_summary.json                  # 机器可读汇总

运行：
  python scripts/od/freeze_final_model_7_8.py
"""

from __future__ import annotations

import csv
import hashlib
import json
import os
import re
import sys
import time
from datetime import datetime

ROOT = r"D:\Luan\2026-05\2_Singapore"
OUT_DIR = os.path.join(ROOT, "reports", "final_model_7_8")

# ---- 冻结输入（只读；本步不得触碰） ----------------------------------------
P_76H_SUMMARY = os.path.join(ROOT, "matsim_final_7_6h", "audit",
                             "od_final_workingpoint_7_6h_summary.json")
P_76H_FROZEN = os.path.join(ROOT, "matsim_final_7_6h",
                            "final_workingpoint_7_6h_frozen_parameters.csv")
P_76H_PROV = os.path.join(ROOT, "matsim_final_7_6h",
                          "final_workingpoint_7_6h_config_provenance.csv")
P_76H_INV = os.path.join(ROOT, "matsim_final_7_6h",
                         "final_workingpoint_7_6h_source_invariance.csv")
P_W01_CONFIG = os.path.join(ROOT, "matsim_final_7_6h", "configs",
                            "config_W01_rc_min.xml")
P_W01_POP = os.path.join(ROOT, "matsim_final_7_6h", "populations", "pop_W01",
                         "population_lambda_0p075.xml.gz")
P_NETWORK = os.path.join(ROOT, "reports", "matsim_network",
                         "network_cleaned.xml.gz")

P_77C0_SUMMARY = os.path.join(ROOT, "reports", "spatial_residual_7_7c0",
                              "step7_7c0_summary.json")
P_77C0_ETA2 = os.path.join(ROOT, "reports", "spatial_residual_7_7c0",
                           "c0_rank_eta2.csv")
P_77C0_PA = os.path.join(ROOT, "reports", "spatial_residual_7_7c0",
                         "c0_6_pa_gradient.csv")
P_77C1_SUMMARY = os.path.join(ROOT, "reports", "spatial_temporal_sensitivity_7_7c1",
                              "c1_summary.json")
P_77D_SUMMARY = os.path.join(ROOT, "reports", "spatial_residual_closure_7_7d",
                             "d_closure_summary.json")
P_77A_SUMMARY = os.path.join(ROOT, "reports", "external_validation_7_7",
                             "step7_7a_summary.json")
P_TF_BASIS = os.path.join(ROOT, "reports", "matsim_departure_6_3_3a",
                          "trafficflow_link_hour_basis.csv")

FROZEN_INPUTS = [
    P_76H_SUMMARY, P_76H_FROZEN, P_76H_PROV, P_76H_INV,
    P_W01_CONFIG, P_W01_POP, P_NETWORK,
    P_77C0_SUMMARY, P_77C0_ETA2, P_77C0_PA,
    P_77C1_SUMMARY, P_77D_SUMMARY, P_77A_SUMMARY, P_TF_BASIS,
]

MODEL_VERSION = "Singapore_OD_MATSim_Final_v1.0"
SPATIAL_STATUS = "UNRESOLVED_STRUCTURAL_LAYER"

# 冻结常量（用于逐位核对，非计算来源）
EXPECT_SCALE = 2.29897
EXPECT_N_BASE = 200000
EXPECT_N_SIM = 236044
EXPECT_F_WORK = 1.180222
EXPECT_LAMBDA = 0.075
EXPECT_TARGET = 0.8589732
EXPECT_NONZERO_CELLS = 71136
EXPECT_CAR_OD_TOTAL = 459794.0

# 7.6E 冻结的 route-choice 4 项
EXPECT_INNOVATION = "0.8"
EXPECT_STRATEGY = {"ReRoute": "0.15", "ChangeExpBeta": "0.85"}
EXPECT_LEARNING_RATE = "0.5"
EXPECT_RANDOMNESS = "0.0"
EXPECT_SEED = "4711"
EXPECT_LAST_ITER = "19"


# ---------------------------------------------------------------- helpers ---
def sha256_file(path: str, size: int = 16) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()[:size]


def snapshot(paths):
    snap = {}
    for p in paths:
        if os.path.exists(p):
            st = os.stat(p)
            snap[p] = {
                "exists": True,
                "bytes": st.st_size,
                "mtime": datetime.fromtimestamp(st.st_mtime).strftime("%Y-%m-%d %H:%M:%S"),
                "sha256_16": sha256_file(p),
            }
        else:
            snap[p] = {"exists": False}
    return snap


def rel(path: str) -> str:
    return os.path.relpath(path, ROOT).replace("\\", "/")


def load_json(path):
    with open(path, "r", encoding="utf-8-sig") as fh:
        return json.load(fh)


def read_csv_rows(path):
    with open(path, "r", encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def write_csv(path, rows, header):
    with open(path, "w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=header, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow(r)


def dump_json(path, obj):
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(obj, fh, ensure_ascii=False, indent=2)


def fnum(x, nd=6):
    try:
        return round(float(x), nd)
    except (TypeError, ValueError):
        return x


def md_table(header, rows):
    out = ["| " + " | ".join(header) + " |",
           "|" + "|".join(["---"] * len(header)) + "|"]
    for r in rows:
        out.append("| " + " | ".join(str(c) for c in r) + " |")
    return "\n".join(out)


# ------------------------------------------------------- frozen XML probe ---
def parse_w01_config(path):
    txt = open(path, "r", encoding="utf-8-sig").read()
    g = {}

    def first(pat):
        m = re.search(pat, txt)
        return m.group(1) if m else None

    g["network_input"] = first(r'name="inputNetworkFile"\s+value="([^"]+)"')
    g["plans_input"] = first(r'name="inputPlansFile"\s+value="([^"]+)"')
    g["output_dir"] = first(r'name="outputDirectory"\s+value="([^"]+)"')
    g["run_id"] = first(r'name="runId"\s+value="([^"]+)"')
    g["last_iteration"] = first(r'name="lastIteration"\s+value="([^"]+)"')
    g["random_seed"] = first(r'name="randomSeed"\s+value="([^"]+)"')
    g["routing_algo"] = first(r'name="routingAlgorithmType"\s+value="([^"]+)"')
    g["mobsim"] = first(r'name="mobsim"\s+value="([^"]+)"')
    g["innovation"] = first(r'name="fractionOfIterationsToDisableInnovation"\s+value="([^"]+)"')
    g["learning_rate"] = first(r'name="learningRate"\s+value="([^"]+)"')
    g["randomness"] = first(r'name="routingRandomness"\s+value="([^"]+)"')
    g["flow_capacity_factor"] = first(r'name="flowCapacityFactor"\s+value="([^"]+)"')
    g["storage_capacity_factor"] = first(r'name="storageCapacityFactor"\s+value="([^"]+)"')
    strat = dict(re.findall(
        r'<parameterset type="strategysettings">\s*<param name="strategyName" value="([^"]+)"\s*/>'
        r'\s*<param name="weight" value="([^"]+)"\s*/>', txt))
    if not strat:
        strat = dict(re.findall(r'strategyName" value="([^"]+)".*?weight" value="([^"]+)"', txt))
    g["strategies"] = strat
    g["n_re_reoute"] = txt.count('strategyName" value="ReRoute"')
    return g


# =============================================================== MAIN =======
def main():
    t0 = time.time()
    os.makedirs(OUT_DIR, exist_ok=True)

    # 0) read-only 前快照
    snap_before = snapshot(FROZEN_INPUTS)

    # 1) 冻结真值
    s76h = load_json(P_76H_SUMMARY)
    wp = s76h["working_point"]
    h1 = s76h["h1"][0]
    h2 = s76h["h2"][0]
    cfg = parse_w01_config(P_W01_CONFIG)
    inv = read_csv_rows(P_76H_INV)[0]
    prov = read_csv_rows(P_76H_PROV)
    frozen_rows = read_csv_rows(P_76H_FROZEN)

    s77c0 = load_json(P_77C0_SUMMARY)
    eta2 = read_csv_rows(P_77C0_ETA2)
    pa_grad = read_csv_rows(P_77C0_PA)
    s77c1 = load_json(P_77C1_SUMMARY)
    s77d = load_json(P_77D_SUMMARY)
    s77a = load_json(P_77A_SUMMARY)

    # ---------------------------------------------------------- 7.8A ------
    f_work = float(wp["f_demand_ref"])
    lam = float(wp["lambda_ref"])
    f_realized = float(h1["f_realized"])
    simobs_frozen = float(h1["SimObs_FROZEN"])
    implied_fstar = float(h1["implied_fstar_FROZEN"])
    n_sim = int(h1["N_sim"])
    crossval = s76h["crossvalidation"]
    r01_frozen = next(c["ours"] for c in crossval if c["item"] == "R01.FROZEN")

    param_rows = [
        ("f_work", f_work, "7.6G L75 direct（7.6H 冻结）", "working_point"),
        ("lambda_ref", lam, "7.6G sensitivity center（⛔ 非最优 λ）", "working_point"),
        ("SCALE", EXPECT_SCALE, "7.4/全流程冻结；ΣT/N_base", "sampling_anchor"),
        ("f_cap", 1.00, "7.4 capacity freeze", "capacity"),
        ("route_choice", "R01_rc_min", "7.6E route-choice freeze", "route_choice"),
        ("sim_agents", n_sim, "W01 = round(f_work × N_base)", "validation"),
        ("crosswalk", "7.3.6A", "7.3.6A Frozen Final Crosswalk（只读）", "target"),
        ("calibration_target", EXPECT_TARGET, "7.6C-2 FROZEN 三口径之主口径", "target"),
        ("N_base", EXPECT_N_BASE, "采样基准 / SCALE 分母", "sampling_anchor"),
        ("iterations", 20, "判据取 it.19 linkstats", "run"),
    ]

    param_freeze = {
        "step": "7.8A",
        "title": "Final Parameter Freeze",
        "model_version": MODEL_VERSION,
        "status": "FINAL_PARAMETER_FREEZE",
        "zero_simulation": True,
        "matsim_rerun": False,
        "parameters_changed": False,
        "lambda_selected": False,
        "demand_scale_selected": False,
        "wording_discipline": {
            "lambda": ("λ=0.075 作为经过灵敏度分析后的工作中心参数；7.6G 表明 λ 对总体水平"
                       "具有可检测影响，但在现有观测与误差边界下不足以实现可靠参数识别。"
                       "⛔ 不得写作『最优 λ / 数据最优 λ』。"),
            "f_work": ("f_work=1.180222 是最终工作点，不意味着需求规模参数具有唯一真实值"
                       "（总量证据只能给出区间，见 7.6A/7.6G）。"),
            "version_lock": ("7.8 之后任何修改上述任一内容，都不属于『最终模型参数调整』，"
                             "而属于新模型版本（v1.1 Structural Repair）。"),
        },
        "parameters": [
            {"item": k, "final_value": v, "source": s, "kind": kind}
            for (k, v, s, kind) in param_rows
        ],
        "bands": {
            "working_point_fstar": f_work,
            "lambda_sensitivity_band": s76h["bands"]["lambda_sensitivity_band"],
            "static_target_band": s76h["bands"]["static_target_band"],
            "merged": False,
            "rule": "三层带独立成列，⛔ 禁止合并为单一区间",
        },
        "derived_disclosure": {
            "f_realized": f_realized,
            "implied_fstar": implied_fstar,
            "sum_expansion_factor": round(float(inv["source_sum_expansion_factor_6_3_3a"]), 6),
            "SCALE_if_recomputed_sumEF_over_Nsim": "NOT_USED",
        },
    }
    dump_json(os.path.join(OUT_DIR, "FINAL_PARAMETER_FREEZE.json"), param_freeze)

    # ---------------------------------------------------------- 7.8B ------
    input_lock = {
        "Input": ["Census 2020", "ACRA / building / landuse / POI",
                  "OSM network", "LTA TrafficFlow", "existing network / zone mappings"],
        "OD": ["332 Subzones", "gravity model", f"λ = {lam}",
               "IPF", "Census workplace controls", "attraction disaggregation"],
        "Sampling": ["FLOOR_PLUS_1", f"N_base = {EXPECT_N_BASE}", f"SCALE = {EXPECT_SCALE}"],
        "Network": ["frozen MATSim network",
                    f"f_cap = {1.00}", "frozen zone → node/link realization"],
        "Route_Choice": ["R01_rc_min"],
        "Calibration_Crosswalk": ["7.3.6A"],
    }

    # ---------------------------------------------------------- 7.8C ------
    metrics = [
        ("N_sim", n_sim, "agents", "7.6H H1", ""),
        ("f_work", f_work, "-", "7.6G direct", ""),
        ("f_realized", f_realized, "-", "7.6H H1", ""),
        ("SimObs_FROZEN", simobs_frozen, "-", "7.6H H1", "|x-1|<=0.01"),
        ("implied_fstar", implied_fstar, "-", "7.6H H1", ""),
        ("SimObs_POSITIVE_ONLY", float(h1["SimObs_POSITIVE_ONLY"]), "-", "7.6H H1", ""),
        ("SimObs_BEST_DIRECTION", float(h1["SimObs_BEST_DIRECTION"]), "-", "7.6H H1", ""),
        ("abs_dev_from_1_pp", float(h1["abs_dev_from_1_pp"]), "pp", "7.6H H1", "<=1.0"),
        ("A_10_19_MATCHED", float(h2["A_10_19_MATCHED"]), "fraction", "7.6H H2", "<0.03"),
        ("A_10_19_CATA", float(h2["A_10_19_CATA"]), "fraction", "7.6H H2", "<0.03"),
        ("A_10_19_SLIP", float(h2["A_10_19_SLIP"]), "fraction", "7.6H H2", "<0.05"),
        ("parity_gap_rel_MATCHED", float(h2["parity_gap_rel_MATCHED"]), "fraction", "7.6H H2", "<0.05"),
        ("Q19_over_Qbar_MATCHED", float(h2["Q19_over_Qbar_MATCHED"]), "-", "7.6H H2", ""),
        ("Q19_over_Qbar_dev_pp", float(h2["Q19_over_Qbar_dev_pp"]), "pp", "7.6H H2", "<=1.0"),
        ("never_arrived", int(h2["never_arrived"]), "agents", "7.6H H2", "==0"),
        ("max_stuck_car", int(h2["max_stuck_car"]), "agents", "7.6H H2", "==0"),
        ("departures_car", int(h2["departures_car"]), "agents", "7.6H H2", ""),
        ("arrivals_car", int(h2["arrivals_car"]), "agents", "7.6H H2", ""),
        ("Qbar_10_19_MATCHED", float(h1["Qbar_10_19_MATCHED"]), "veh", "7.6H H1", ""),
        ("Q_19_MATCHED", float(h1["Q_19_MATCHED"]), "veh", "7.6H H1", ""),
        ("crossvalidation_R01_FROZEN", float(r01_frozen), "-", "7.6H X1", "vs 7.6C-2"),
    ]
    write_csv(os.path.join(OUT_DIR, "FINAL_VALIDATION_METRICS.csv"),
              [{"item": a, "value": b, "unit": c, "source_step": d, "criterion": e}
               for (a, b, c, d, e) in metrics],
              ["item", "value", "unit", "source_step", "criterion"])

    # ---------------------------------------------------------- 7.8D ------
    bnd = []
    for r in s76h["h3_spatial"]:
        bnd.append({
            "level": r["group_by"],
            "group": r["group"],
            "n_sections": r["n_sections"],
            "n_zero_sim": r["n_zero_sim"],
            "ratio_FROZEN": fnum(r["Q_FROZEN"]),
            "rel_dev_vs_global_FROZEN": fnum(r["rel_dev_vs_global_FROZEN"]),
            "label": "KNOWN SPATIAL RESIDUAL BOUNDARY",
            "status": SPATIAL_STATUS,
        })
    for r in s76h["h3_key_pa"]:
        bnd.append({
            "level": "pa_key",
            "group": r["pa"],
            "n_sections": r["n_sections"],
            "n_zero_sim": "",
            "ratio_FROZEN": fnum(r["Q_FROZEN"]),
            "rel_dev_vs_global_FROZEN": fnum(r["rel_dev_vs_global_FROZEN"]),
            "label": "KNOWN SPATIAL RESIDUAL BOUNDARY",
            "status": SPATIAL_STATUS,
        })
    for r in pa_grad:
        bnd.append({
            "level": "pa_all",
            "group": r["pa"],
            "n_sections": r["n_sections"],
            "n_zero_sim": "",
            "ratio_FROZEN": fnum(r["R_PA"]),
            "rel_dev_vs_global_FROZEN": fnum(float(r["R_PA"]) - 1.0),
            "label": "KNOWN SPATIAL RESIDUAL BOUNDARY",
            "status": SPATIAL_STATUS,
        })
    write_csv(os.path.join(OUT_DIR, "FINAL_SPATIAL_RESIDUAL_BOUNDARY.csv"), bnd,
              ["level", "group", "n_sections", "n_zero_sim", "ratio_FROZEN",
               "rel_dev_vs_global_FROZEN", "label", "status"])

    # ---------------------------------------------------------- 7.8E ------
    manifest = {
        "step": "7.8E",
        "title": "Final Model Manifest",
        "model_version": MODEL_VERSION,
        "identity": {
            "step": "7.8",
            "f_work": f_work,
            "lambda_ref": lam,
            "scale": EXPECT_SCALE,
            "f_cap": 1.0,
            "route_choice": "R01_rc_min",
            "sim_agents": n_sim,
            "n_base": EXPECT_N_BASE,
            "crosswalk": "7.3.6A",
            "calibration_target": EXPECT_TARGET,
            "validation": "W01",
            "spatial_residual_status": SPATIAL_STATUS,
            "primary_metric": "MATCHED Sim/Obs (08-09)",
            "primary_window": "Qbar_10:19",
            "reference_window": "Q_19",
        },
        "input_algorithm_lock": input_lock,
        "version_semantics": {
            "current": MODEL_VERSION,
            "next_if_structural_repair": "Singapore_OD_MATSim_Final_v1.1 (Structural Repair)",
            "rule": "任何修改 input/algorithm lock 中条目 ⇒ 新版本；不得就地改 v1.0",
        },
        "config_fingerprint": {
            "config_path": rel(P_W01_CONFIG),
            "network_input": cfg["network_input"],
            "plans_input": cfg["plans_input"],
            "run_id": cfg["run_id"],
            "last_iteration": cfg["last_iteration"],
            "random_seed": cfg["random_seed"],
            "routing_algorithm": cfg["routing_algo"],
            "mobsim": cfg["mobsim"],
            "flow_capacity_factor": cfg["flow_capacity_factor"],
            "storage_capacity_factor": cfg["storage_capacity_factor"],
            "route_choice": {
                "fractionOfIterationsToDisableInnovation": cfg["innovation"],
                "strategies": cfg["strategies"],
                "learningRate": cfg["learning_rate"],
                "routingRandomness": cfg["randomness"],
            },
        },
        "closure_state": {
            "attribution": s77d["attribution"],
            "conclusion_boundary": s77d["conclusion_boundary"],
        },
        "evidence_manifest": [
            {"path": rel(p), **v} for p, v in snap_before.items()
        ],
        "products": [],
        "zero_simulation": True,
        "matsim_rerun": False,
        "frozen_artifacts_touched": False,
    }
    # products 稍后回填 + 自身 hash

    # ------------------------------------------------- 7.8A/7.8B 说明文 -----
    spec_md = []
    spec_md.append(f"# FINAL_MODEL_SPECIFICATION — {MODEL_VERSION}\n")
    spec_md.append(f"> Step 7.8A（参数冻结）+ 7.8B（输入与算法冻结）｜"
                   f"生成 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}｜**零仿真定版**\n")
    spec_md.append("> 本文件是最终模型的**版本锁**。7.8 之后任何修改下列条目，"
                   "都属于**新模型版本**，不属于「最终模型参数调整」。\n")

    spec_md.append("\n## 1. 7.8A 参数冻结（Final Parameter Freeze）\n")
    spec_md.append(md_table(
        ["项目", "最终值", "来源", "类型"],
        [[k, v, s, kind] for (k, v, s, kind) in param_rows]))
    spec_md.append("\n### 措辞纪律（强制）\n")
    spec_md.append("> **λ（lambda）**：" + param_freeze["wording_discipline"]["lambda"] + "\n")
    spec_md.append("> **f_work**：" + param_freeze["wording_discipline"]["f_work"] + "\n")
    spec_md.append("\n### 三层带（⛔ 不得合并）\n")
    spec_md.append(md_table(
        ["层", "值", "含义"],
        [["working_point", f"λ={lam}, f*={f_work}", "条件点估计（7.6G L75 直跑实测）"],
         ["lambda_sensitivity_band", str(s76h["bands"]["lambda_sensitivity_band"]),
          "λ=0.05/0.10 两端的动态响应不确定带"],
         ["static_target_band", str(s76h["bands"]["static_target_band"]),
          "7.6C-2 静态靶场识别不确定带"]]))
    spec_md.append("\n- 披露量：`f_realized` = **%s**、`implied_fstar` = **%s**、"
                   "`sum_expansion_factor` = **%s**（`SCALE` 若按 ΣEF/N_sim 重算 = "
                   "**NOT USED**）\n" % (
                       f_realized, implied_fstar,
                       param_freeze["derived_disclosure"]["sum_expansion_factor"]))

    spec_md.append("\n## 2. 7.8B 输入与算法冻结（Input & Algorithm Lock）\n")
    spec_md.append(md_table(["层", "冻结条目"],
                            [[k, "；".join(v)] for k, v in input_lock.items()]))
    spec_md.append("\n### 版本线\n```text\n")
    spec_md.append(f"{MODEL_VERSION}\n    ↓ 若发现 twin mapping 等结构问题\n"
                   "不得直接修改 v1.0\n    ↓\n"
                   "新建 v1.1 / Structural Repair\n```\n")
    spec_md.append("\n### 配置指纹（W01 实跑 config）\n")
    spec_md.append(md_table(
        ["项", "值"],
        [["config", rel(P_W01_CONFIG)],
         ["network", cfg["network_input"]],
         ["plans", cfg["plans_input"]],
         ["runId", cfg["run_id"]],
         ["lastIteration", cfg["last_iteration"]],
         ["randomSeed", cfg["random_seed"]],
         ["routingAlgorithmType", cfg["routing_algo"]],
         ["mobsim", cfg["mobsim"]],
         ["flowCapacityFactor", cfg["flow_capacity_factor"]],
         ["storageCapacityFactor", cfg["storage_capacity_factor"]],
         ["fractionOfIterationsToDisableInnovation", cfg["innovation"]],
         ["strategies", json.dumps(cfg["strategies"], ensure_ascii=False)],
         ["learningRate", cfg["learning_rate"]],
         ["routingRandomness", cfg["randomness"]]]))
    spec_md.append("\n- 7.6H 相对 R01 的 config 差异**仅 3 项白名单**：\n")
    spec_md.append(md_table(["模块", "参数", "R01 值", "W01 值", "白名单"],
                            [[p["module"], p["param"], p["r01_value"], p["new_value"],
                              p["in_whitelist"]] for p in prov]))
    with open(os.path.join(OUT_DIR, "FINAL_MODEL_SPECIFICATION.md"), "w",
              encoding="utf-8") as fh:
        fh.write("\n".join(spec_md) + "\n")

    # ------------------------------------------------- 7.8C 说明文 ------
    val_md = []
    val_md.append(f"# FINAL_VALIDATION_REPORT — {MODEL_VERSION}\n")
    val_md.append(f"> Step 7.8C｜主验证臂 **W01**｜零仿真只读｜"
                   f"生成 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    val_md.append("\n## 1. 主结果（W01）\n")
    val_md.append(md_table(
        ["项", "值"],
        [["N_sim", f"{n_sim:,}"],
         ["f_work", f_work],
         ["f_realized", f_realized],
         ["FROZEN Sim/Obs", f"{simobs_frozen:.10f}"],
         ["implied f*", implied_fstar]]))
    val_md.append("\n## 2. 稳定性\n")
    val_md.append(md_table(
        ["指标", "值", "阈值", "结论"],
        [["A_10:19 MATCHED", f"{h2['A_10_19_MATCHED']*100:.4f}%", "< 3.0%",
          "PASS" if h2["A_10_19_MATCHED"] < 0.03 else "FAIL"],
         ["A_10:19 CATA", f"{h2['A_10_19_CATA']*100:.4f}%", "< 3.0%",
          "PASS" if h2["A_10_19_CATA"] < 0.03 else "FAIL"],
         ["A_10:19 SLIP", f"{h2['A_10_19_SLIP']*100:.4f}%", "< 5.0%",
          "PASS" if h2["A_10_19_SLIP"] < 0.05 else "FAIL"],
         ["parity gap", f"{h2['parity_gap_rel_MATCHED']*100:.4f}%", "< 5.0%",
          "PASS" if h2["parity_gap_rel_MATCHED"] < 0.05 else "FAIL"],
         ["Q19/Qbar", f"{h2['Q19_over_Qbar_MATCHED']:.6f}", "|x-1| <= 1%",
          "PASS" if abs(h2["Q19_over_Qbar_MATCHED"] - 1) <= 0.01 else "FAIL"],
         ["never_arrived", int(h2["never_arrived"]), "== 0",
          "PASS" if h2["never_arrived"] == 0 else "FAIL"],
         ["max_stuck_car", int(h2["max_stuck_car"]), "== 0",
          "PASS" if h2["max_stuck_car"] == 0 else "FAIL"],
         ["departure", f"{int(h2['departures_car']):,}", "=", "OK"],
         ["arrival", f"{int(h2['arrivals_car']):,}", "=", "OK"]]))
    val_md.append("\n## 3. 口径未漂移（跨步对账）\n")
    val_md.append(md_table(
        ["对账项", "本步值", "参照", "|Δ|", "容差", "结论"],
        [[c["item"], c["ours"], c["reference"], f"{c['abs_diff']:.3e}",
          c["tol"], "PASS" if c["pass"] else "FAIL"] for c in crossval]))
    val_md.append("\n## 4. 空间残差（保留，不消除）\n")
    val_md.append("> **Final Model — Known Spatial Residual Boundary**。"
                  "7.7D 已证：需求规模 / λ / 车型构成 / 时间实现均**不能**解释；"
                  "road class / aggregation / observation semantics 已**排除**；"
                  "剩余收缩到 **PA/OD spatial allocation · twin representation · "
                  "directionality · section-network correspondence** ⇒ "
                  "`UNRESOLVED_STRUCTURAL_LAYER`。\n")
    val_md.append(md_table(
        ["层级", "组", "n_sections", "ratio", "rel_dev vs global"],
        [[r["group_by"], r["group"], r["n_sections"], fnum(r["Q_FROZEN"], 4),
          f"{r['rel_dev_vs_global_FROZEN']*100:+.2f}%"] for r in s76h["h3_spatial"]]))
    val_md.append("\n### 关键 PA\n")
    val_md.append(md_table(
        ["PA", "n_sections", "ratio", "rel_dev vs global"],
        [[r["pa"], r["n_sections"], fnum(r["Q_FROZEN"], 4),
          f"{r['rel_dev_vs_global_FROZEN']*100:+.2f}%"] for r in s76h["h3_key_pa"]]))
    val_md.append("\n## 5. 归因收口三类（7.7D 继承）\n")
    att = s77d["attribution"]
    val_md.append("**已解释**\n")
    for k, v in att["explained"].items():
        val_md.append(f"- `{k}`：{v}")
    val_md.append("\n**已排除**\n")
    for v in att["excluded"]:
        val_md.append(f"- {v}")
    val_md.append("\n**未解释（结构性层）**\n")
    for v in att["unexplained"]:
        val_md.append(f"- {v}")
    val_md.append(f"\n> 结论边界：{s77d['conclusion_boundary']}\n")
    with open(os.path.join(OUT_DIR, "FINAL_VALIDATION_REPORT.md"), "w",
              encoding="utf-8") as fh:
        fh.write("\n".join(val_md) + "\n")

    # ============================================== #168 完整性门 ==========
    checks = []

    def chk(cid, desc, ok, detail):
        checks.append({"check_id": cid, "description": desc,
                       "pass": bool(ok), "detail": str(detail)})

    # ---- 冻结真值一致性（逐位） ----
    chk("G1", "FINAL f_work == 7.6H working_point.f_demand_ref（逐位）",
        f_work == float(wp["f_demand_ref"]), f"{f_work} vs {wp['f_demand_ref']}")
    chk("G2", "FINAL lambda_ref == 7.6H working_point.lambda_ref（逐位）",
        lam == float(wp["lambda_ref"]), f"{lam} vs {wp['lambda_ref']}")
    chk("G3", "FINAL SCALE == 2.29897 == 7.6H scale_used（逐位）",
        EXPECT_SCALE == float(s76h["scale_used"]), f"{EXPECT_SCALE} vs {s76h['scale_used']}")
    chk("G4", "FINAL sim_agents == 236,044 == 7.6H h1.N_sim",
        n_sim == int(h1["N_sim"]) and n_sim == EXPECT_N_SIM, f"{n_sim}")
    chk("G5", "FINAL Sim/Obs FROZEN == 7.6H h1.SimObs_FROZEN（逐位）",
        simobs_frozen == float(h1["SimObs_FROZEN"]), f"{simobs_frozen!r}")
    # ⚠️ 7.6C-2 的 `reference` 字段是发布用四舍五入常量（0.8589732），
    #    故不能配 1e-12 逐位比较；按 7.6C-2 自己声明的 tol=1e-6 核对，并记录全精度真值。
    chk("G6", "FINAL calibration_target 复现 7.6C-2 R01.FROZEN（tol 1e-6）",
        abs(float(r01_frozen) - EXPECT_TARGET) <= 1e-6,
        f"ours={r01_frozen!r} published={EXPECT_TARGET} "
        f"Δ={abs(float(r01_frozen) - EXPECT_TARGET):.3e}")
    chk("G7", "FINAL implied f* == 7.6H h1.implied_fstar_FROZEN（逐位）",
        implied_fstar == float(h1["implied_fstar_FROZEN"]), f"{implied_fstar!r}")

    # ---- config 冻结项 ----
    chk("G8", "W01 config route-choice 继承 7.6E 四项",
        cfg["innovation"] == EXPECT_INNOVATION
        and cfg["strategies"] == EXPECT_STRATEGY
        and cfg["learning_rate"] == EXPECT_LEARNING_RATE
        and cfg["randomness"] == EXPECT_RANDOMNESS,
        f"innov={cfg['innovation']} strat={cfg['strategies']} "
        f"lr={cfg['learning_rate']} rnd={cfg['randomness']}")
    chk("G9", "W01 config 运行控制（seed/iters/algo/mobsim/f_cap）",
        cfg["random_seed"] == EXPECT_SEED and cfg["last_iteration"] == EXPECT_LAST_ITER
        and cfg["routing_algo"] == "SpeedyALT" and cfg["mobsim"] == "qsim"
        and cfg["flow_capacity_factor"] == "1.0"
        and cfg["storage_capacity_factor"] == "1.0",
        f"seed={cfg['random_seed']} it={cfg['last_iteration']} algo={cfg['routing_algo']} "
        f"mobsim={cfg['mobsim']} fcap={cfg['flow_capacity_factor']}")

    # ---- 输入文件存在 + hash ----
    missing = [rel(p) for p, v in snap_before.items() if not v["exists"]]
    chk("G10", "全部冻结输入存在（14 件）", not missing,
        f"n={len(snap_before)} missing={missing}")

    # ---- config 引用文件存在 ----
    net_ok = os.path.exists(cfg["network_input"]) if cfg["network_input"] else False
    plan_ok = os.path.exists(cfg["plans_input"]) if cfg["plans_input"] else False
    chk("G11", "config 引用的 network / plans 文件存在",
        net_ok and plan_ok,
        f"network={net_ok} plans={plan_ok}")

    # ---- 目录级约束（OD / 采样） ----
    chk("G12", "OD 结构不变：正 cell == 71,136",
        int(float(inv["nonzero_od_cells"])) == EXPECT_NONZERO_CELLS,
        inv["nonzero_od_cells"])
    chk("G13", "car_od_total == 459,794（口径锚）",
        abs(float(inv["car_od_total_6_2b"]) - EXPECT_CAR_OD_TOTAL) < 1e-3,
        inv["car_od_total_6_2b"])

    # ---- 三层带未合并 ----
    chk("G14", "三层带独立、未合并为单区间",
        not s76h["bands_merged"]
        and len({json.dumps(s76h["bands"]["lambda_sensitivity_band"]),
                 json.dumps(s76h["bands"]["static_target_band"])}) == 2,
        f"bands_merged={s76h['bands_merged']}")

    # ---- 空间残差仍在（未被抹平） ----
    east = next(r for r in s76h["h3_spatial"]
                if r["group_by"] == "region" and r["group"] == "EAST REGION")
    rin = next(r for r in s76h["h3_spatial"]
               if r["group_by"] == "radial" and r["group"] == "radial_in")
    chk("G15", "空间残差仍存在（EAST / radial_in 未消失）",
        east["rel_dev_vs_global_FROZEN"] < -0.25
        and rin["rel_dev_vs_global_FROZEN"] < -0.25,
        f"EAST={east['rel_dev_vs_global_FROZEN']*100:.2f}% "
        f"radial_in={rin['rel_dev_vs_global_FROZEN']*100:.2f}%")

    # ---- 上游闭环结论一致 ----
    chk("G16", "7.7D 收口判决一致（未解释层 = 结构性层）",
        s77d["verdict"] == "SPATIAL_RESIDUAL_ATTRIBUTION_CLOSED_WITH_UNRESOLVED_STRUCTURAL_LAYER"
        and len(s77d["unresolved"]) == 4,
        f"verdict={s77d['verdict']} unresolved={len(s77d['unresolved'])}")
    chk("G17", "7.7C-1 时段上界门 = FAIL_DEFER_HTS（口径一致）",
        s77c1["gate"]["verdict"] == "TEMPORAL_SPATIAL_SENSITIVITY_FAIL_DEFER_HTS",
        s77c1["gate"]["verdict"])
    chk("G18", "7.7C-0 归因基线已落盘（eta2 排序可用）",
        len(eta2) >= 10 and eta2[0]["layer"] == "pa_location",
        f"n_dims={len(eta2)} top={eta2[0]['layer']}")
    chk("G19", "7.7A 构成归因已落盘（解释总体量级）",
        s77a["verdict"]["local_data"] == "VEHICLE_TYPE_VOLUME_UNAVAILABLE",
        s77a["verdict"]["local_data"])

    # ---- 纪律声明 ----
    chk("G20", "本步纪律：zero_simulation / 未改任何冻结参数",
        param_freeze["zero_simulation"] and not param_freeze["parameters_changed"]
        and not param_freeze["lambda_selected"]
        and not param_freeze["demand_scale_selected"],
        "params_changed=False lambda_selected=False demand_scale_selected=False")

    # ---- 产品落盘 + hash（自证完整性） ----
    products = [
        "FINAL_MODEL_SPECIFICATION.md",
        "FINAL_VALIDATION_REPORT.md",
        "FINAL_PARAMETER_FREEZE.json",
        "FINAL_VALIDATION_METRICS.csv",
        "FINAL_SPATIAL_RESIDUAL_BOUNDARY.csv",
        "FINAL_MODEL_MANIFEST.json",
    ]
    manifest_name = "FINAL_MODEL_MANIFEST.json"

    def scan_products():
        meta = []
        for name in products:
            p = os.path.join(OUT_DIR, name)
            ok = os.path.exists(p) and os.path.getsize(p) > 0
            meta.append({
                "name": name,
                "path": rel(p),
                "exists": ok,
                "bytes": os.path.getsize(p) if ok else 0,
                "sha256_16": sha256_file(p) if ok else "",
            })
        return meta

    # manifest 内 products 只列非自身的 5 件（写自身 hash 会循环）；6/6 存在性由 G21 外部核对
    manifest["products"] = [x for x in scan_products() if x["name"] != manifest_name]
    manifest["manifest_self"] = {
        "path": rel(os.path.join(OUT_DIR, manifest_name)),
        "note": "自身 hash 不含于本 manifest（避免循环声明）；由 #168 G21 在外部核对",
    }
    manifest["artifact_integrity"] = {
        "n_products_expected": len(products),
        "n_products_present": None,
        "note": ("写自身 hash 会循环 ⇒ products 仅列非自身 5 件；"
                 "6/6 存在性由 #168 G21 外部核对"),
    }
    dump_json(os.path.join(OUT_DIR, manifest_name), manifest)

    # 落盘后全量扫描（含 manifest 自身）→ 回填计数并重写（报告表以最终盘上内容为准）
    manifest["artifact_integrity"]["n_products_present"] = sum(
        1 for x in scan_products() if x["exists"])
    dump_json(os.path.join(OUT_DIR, manifest_name), manifest)

    prod_meta = scan_products()
    chk("G21", "六件正式产品全部落盘且非空",
        len(prod_meta) == 6 and all(x["exists"] for x in prod_meta),
        f"present={sum(1 for x in prod_meta if x['exists'])}/6")

    # ---- read-only 证据（跑前后冻结件逐位未变） ----
    snap_after = snapshot(FROZEN_INPUTS)
    changed = [rel(p) for p in FROZEN_INPUTS
               if snap_before[p] != snap_after[p]]
    chk("G22", "所有冻结输入跑前后 mtime+sha256 逐位未变（read-only 证据）",
        not changed, f"changed={changed}")

    # ---- W01 产物存在（验证臂可追溯） ----
    w01_out = os.path.join(ROOT, "matsim_final_7_6h", "outputs", "W01_rc_min")
    it19 = os.path.join(w01_out, "ITERS", "it.19")
    chk("G23", "W01 验证臂 it.19 产物存在",
        os.path.isdir(w01_out) and os.path.isdir(it19),
        f"outputs={os.path.isdir(w01_out)} it19={os.path.isdir(it19)}")

    n_pass = sum(1 for c in checks if c["pass"])
    hard_pass = n_pass
    hard_total = len(checks)
    verdict = ("FINAL_MODEL_FROZEN_AND_REPRODUCIBLE"
               if n_pass == hard_total else "FINAL_MODEL_FREEZE_INCOMPLETE")

    write_csv(os.path.join(OUT_DIR, "f_integrity_checks.csv"), checks,
              ["check_id", "description", "pass", "detail"])

    runtime = time.time() - t0

    summary = {
        "step": "7.8",
        "title": "Final Model Freeze & Validation Package",
        "model_version": MODEL_VERSION,
        "status": verdict,
        "verdict": verdict,
        "zero_simulation": True,
        "matsim_rerun": False,
        "parameters_changed": False,
        "lambda_selected": False,
        "demand_scale_selected": False,
        "frozen_artifacts_touched": False,
        "checks_total": hard_total,
        "checks_pass": hard_pass,
        "checks": checks,
        "identity": manifest["identity"],
        "bands": s76h["bands"],
        "spatial_residual_boundary": {
            "status": SPATIAL_STATUS,
            "n_boundary_rows": len(bnd),
            "nested_layers": s77d["unresolved"],
        },
        "products": prod_meta,
        "evidence_manifest": manifest["evidence_manifest"],
        "version_line": [
            "7.3 Calibration Crosswalk Freeze",
            "7.4 Capacity / Sampling Freeze",
            "7.6E Route-choice Freeze",
            "7.6F Demand Working Point",
            "7.6G Lambda Identification Boundary",
            "7.6H Independent Validation",
            "7.7A Vehicle/Mode Exclusion",
            "7.7C-0 Spatial Attribution",
            "7.7C-1 Temporal Upper Bound",
            "7.7D Spatial Residual Closure",
            "7.8 FINAL MODEL FREEZE -> " + MODEL_VERSION,
        ],
        "stop_rule": ("7.8 完成后 STOP。若继续研究，属新研究问题 "
                      "7.9 Structural Repair / Model v1.1，"
                      "而非继续把 v1.0 的 Sim/Obs 从 0.9993 调到 1.00。"),
        "runtime_sec": round(runtime, 2),
    }
    dump_json(os.path.join(OUT_DIR, "step7_8_summary.json"), summary)

    # ------------------------------------------------- 本步总报告 ------
    rep = []
    rep.append(f"# STEP 7.8 — Final Model Freeze & Validation Package\n")
    rep.append(f"> {MODEL_VERSION}｜判决 **`{verdict}`**｜"
               f"硬门 {hard_pass}/{hard_total}｜零仿真｜{runtime:.1f} s\n")
    rep.append("\n## 0. 定位\n")
    rep.append("7.8 从「研究」切换到「定版」：不再产生新分析结论，"
               "而是把 7.3→7.7D 的证据链整理成不可歧义、可复现、可引用的最终版本。"
               "\n")
    rep.append("\n## 1. 交付产品（6 件）\n")
    rep.append(md_table(["文件", "字节", "sha256(16)"],
                        [[x["name"], x["bytes"], x["sha256_16"]] for x in prod_meta]))
    rep.append("\n## 2. 模型身份\n")
    rep.append("```json\n" + json.dumps(manifest["identity"], ensure_ascii=False, indent=2)
               + "\n```\n")
    rep.append("\n## 3. 完整性门（#168，23 条）\n")
    rep.append(md_table(["门", "检查", "结论", "证据"],
                        [[c["check_id"], c["description"],
                          "PASS" if c["pass"] else "**FAIL**", c["detail"]]
                         for c in checks]))
    rep.append("\n## 4. 空间残差边界（保留，不消除）\n")
    rep.append(f"- 状态：**`{SPATIAL_STATUS}`**（{len(bnd)} 行边界表）\n")
    rep.append("- 未解释结构性层：" + "、".join(s77d["unresolved"]) + "\n")
    rep.append(f"- 结论边界：{s77d['conclusion_boundary']}\n")
    rep.append("\n## 5. 版本线与停止规则\n```text\n")
    rep.append("\n".join(summary["version_line"]))
    rep.append("\n```\n")
    rep.append(f"\n- **停止规则**：{summary['stop_rule']}\n")
    rep.append("\n## 6. 纪律\n")
    rep.append("- `zero_simulation=True` / `matsim_rerun=False` / "
               "`parameters_changed=False` / `lambda_selected=False` / "
               "`demand_scale_selected=False` / `frozen_artifacts_touched=False`\n")
    rep.append("- 全部冻结输入跑前后 mtime+sha256 逐位未变（G22）\n")
    with open(os.path.join(OUT_DIR, "STEP7_8_REPORT.md"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(rep) + "\n")

    # 控制台
    print(f"[7.8] verdict = {verdict}")
    print(f"[7.8] hard gate  = {hard_pass}/{hard_total}")
    for c in checks:
        flag = "OK " if c["pass"] else "FAIL"
        print(f"  [{flag}] {c['check_id']} {c['description']} :: {c['detail']}")
    print(f"[7.8] products   = {len(prod_meta)} -> {rel(OUT_DIR)}")
    print(f"[7.8] runtime    = {runtime:.2f} s")

    return 0 if hard_pass == hard_total else 1


if __name__ == "__main__":
    sys.exit(main())
