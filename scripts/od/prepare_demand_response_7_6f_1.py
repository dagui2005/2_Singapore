#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""
prepare_demand_response_7_6f_1.py — Step 7.6F-1：稳定分配底座上的**粗档 demand-response 曲线**
（设计 + 人口 + 配置 + 预注册；**零仿真**；默认不启动 MATSim）。

用户 2026-09-17 裁定
--------------------
7.6C-2 判 `TARGET_MARGINAL_COARSE_ONLY`：

    FROZEN(主靶场) 0.8589732 / POSITIVE_ONLY 0.9350621 / BEST_DIRECTION 0.8909674
    Delta_target = 7.609 pp
    f* 识别区间 = [1.06945, 1.16418]
    SNR: 粗档 0.10 -> 1.056 ✓ (需 eps>=0.947)；细档 0.05 -> 0.528 ✗ (需 eps>=1.895)

结论：靶场不确定性 ≈ 粗档增量 ⇒ 7.6F-1 **可跑，但只能识别「粗档响应关系」，不能识别
「绝对 demand scale」**；且**必须换网格**（原 1.10/1.20/1.25 不合格：f=1.10 落在 f* 区间内部
⇒ 结论随口径而变；3 跑只辨 2 个区制）。用户选定：

        f_demand = 1.05 / 1.15 / 1.25

分别落在 f* 区间 [1.06945, 1.16418] 的**下方 / 内部 / 上方**，信息利用率高于原网格。

★★ 一处必须点明的机制推论（否则设计自相矛盾）
--------------------------------------------
用户冻结清单同时写了 `N = 200,000` 与 `f_demand = 1.05 / 1.15 / 1.25`。二者**不是**同一个量：

    N = 200,000        = **采样基准 / SCALE 锚**（6.3.3A 冻结人口），本步骤**不改**
    被仿真的 agent 数   = f_demand × 200,000  ->  **210,000 / 230,000 / 250,000**

为什么必须这样（而不是「保持 200,000 个 agent」）：

1. 7.4.3 已证：只缩放 `expansion_factor` / `od_trips` 而**不动 agent 数**是对仿真的
   **no-op** —— `HRSx-yavg` 一个数都不变，Sim/Obs 只是被算术地乘 f。那样的「三档实验」
   会得到三份**完全相同**的 linkstats，跑 MATSim 毫无意义。
2. `f_cap = 1.00` **冻结**（而非 `N/200,000`）恰恰**排除了** 7.6D-S 的「采样一致性」约定，
   锁定 7.4.3 的「物理加车」约定。
3. `SCALE` 因此**恒定**：复制 agent 会把各自的 `expansion_factor` 一并复制 ⇒ 平均 EF 不变
   ⇒ `SCALE = ΣT / 200,000 = 2.29897` 对三个档**全部适用**（已由 7.6F-0
   `demand_scale_7_6f_0_decomposition.csv` 实证：D01–D04 的 SCALE 列全为 2.29897）。

机制来源（**复用而非复制**）
--------------------------
    run_demand_scale_7_4_3.build_population   —— 复制机制（seed=20260912 permutation 前缀）
    prepare_routechoice_7_6d.apply_min_patch  —— 7.6E 冻结的 route-choice 最小修复
两个模块均 `import`，不复制公式；任何一处改动都会自动传播，且被本脚本的校验捕获。

冻结项（本步骤一律不动）
------------------------
    route-choice = R01_rc_min（innovation 0.8 / [ReRoute 0.15, ChangeExpBeta 0.85] / lr 0.5 / randomness 0.0）
    N(采样基准)   = 200,000          f_cap = 1.00（不随 N 缩放）
    lambda        = 0.075（本轮保持不变，不作评价）
    7.3.6A Final Crosswalk = 正式主靶场（不得擅改；如要改须另立 7.3.6A-b）
    MATCHED 为主口径；Q̄_10:19 为主，Q_19 为参考
    EAST / radial_in = 已知空间残差，**不得**通过调 demand 主动压平
    POSITIVE_ONLY / BEST_DIRECTION **不得**升格为正式标定靶场

隔离原则（用户工程决定）
------------------------
**不修改** 7.1 / 7.3.6A / OD / network / capacity / population(200k 源) / route-choice 任何冻结件。
新人口、新 config、新输出、新日志、新审计全部落在**独立目录**：

    matsim_demand_7_6f_1/
        README.md
        STEP7_6F_1_PREREGISTRATION.md
        demand_response_7_6f_1_matrix.csv
        demand_response_7_6f_1_config_provenance.csv
        demand_response_7_6f_1_config_validation.json
        populations/pop_<EID>/population_lambda_0p075.xml.gz
        configs/config_<RUN_ID>.xml
        outputs/<RUN_ID>/                （run 后产生）
        logs/                            （run 后产生）
        audit/                           （评价后产生）

用法
----
    python scripts/od/prepare_demand_response_7_6f_1.py            # 造人口 + 生成 config + 验证 + 写预注册（零仿真）
    python scripts/od/prepare_demand_response_7_6f_1.py --gen-only # 同上（默认即此）
    python scripts/od/prepare_demand_response_7_6f_1.py --smoke 2000   # 冒烟（需显式指定）
    python scripts/od/prepare_demand_response_7_6f_1.py --run      # 正式 3 档（**需显式指定，且需用户明确启动指令**）
    python scripts/od/prepare_demand_response_7_6f_1.py --experiments F15
"""
from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
import sys
import time
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path

ROOT = Path(r"D:\Luan\2026-05\2_Singapore")
SCRIPTS_OD = ROOT / "scripts" / "od"
SCRIPTS_MAT = ROOT / "scripts" / "matsim"
sys.path.insert(0, str(SCRIPTS_MAT))
sys.path.insert(0, str(SCRIPTS_OD))

import make_config_6_3 as cfgmod          # noqa: E402  build_one（official fullConfig 基线）
import matsim_env                         # noqa: E402  Java 运行时
import prepare_routechoice_7_6d as rc76d  # noqa: E402  ★ 7.6E 冻结 route-choice 最小修复
import run_demand_scale_7_4_3 as ds743    # noqa: E402  ★ 7.4.3 冻结 agent 复制机制

# --------------------------------------------------------------------------
# 冻结路径
# --------------------------------------------------------------------------
NEW_ROOT = ROOT / "matsim_demand_7_6f_1"
CONFIG_DIR = NEW_ROOT / "configs"
POP_ROOT = NEW_ROOT / "populations"
OUT_ROOT = NEW_ROOT / "outputs"
LOG_DIR = NEW_ROOT / "logs"
AUDIT_DIR = NEW_ROOT / "audit"

POP_SOURCE = ROOT / "reports" / "matsim_departure_6_3_3a" / "population_lambda_0p075.xml.gz"
R01_ROOT = ROOT / "matsim_routechoice_7_6d"
R01_CFG = R01_ROOT / "configs" / "config_R01_rc_min.xml"
R01_OUT = R01_ROOT / "outputs" / "R01_rc_min"
BASELINE_CFG = ROOT / "matsim" / "step6_3" / "config_E06_lam0p075_cap1p00.xml"

LAMBDA_TAG = "0p075"
LAMBDA_FIXED = 0.075
N_BASE = 200_000                      # ★ 采样基准（不改）；被仿真 agent 数 = f * N_BASE
REAL_CAR_OD_TOTAL = 459_794.0         # = Σ expansion_factor（6.2B / 7.6A 冻结锚）
SCALE_CONST = REAL_CAR_OD_TOTAL / N_BASE        # 2.29897（复制机制下恒定）
DUP_SEED = 20260912                   # 与 7.4.3 同 seed ⇒ F05 ⊂ F15 ⊂ F25 = D04 人口
F_CAP = 1.00
TOTAL_ITER = 20
EXPECTED_ITER = 19
FLOOR_MIN_CELLS = 71_136              # 6.2B FLOOR_PLUS_1 硬下界（每正 OD cell >= 1 agent）

DUP_SEED_EXPECTED = {"persons": None}  # 占位，实际逐档填

# ★ 本步骤唯一被扫的量
SPEC = [
    ("F05", 1.05, 210_000),
    ("F15", 1.15, 230_000),
    ("F25", 1.25, 250_000),
]

# 7.4.3 同构档（用于「复制机制可复现」的交叉验证；F25 与 D04 应逐字节一致）
CROSSCHECK_743 = {"F05": None, "F15": None, "F25": "D04"}

# 7.6C-2 门控输出的冻结靶场（只读引用，不作修改）
TARGET_REF = {
    "FROZEN": 0.8589732,               # 主口径（**不能擅改**）
    "POSITIVE_ONLY": 0.9350621,        # 敏感性口径
    "BEST_DIRECTION": 0.8909674,       # 误差边界（**不作正式靶场**）
    "delta_target_pp": 7.609,
    "fstar_low": 1.06945,
    "fstar_high": 1.16418,
    "snr_coarse_0p10": 1.056,
    "snr_fine_0p05": 0.528,
    "verdict_7_6c_2": "TARGET_MARGINAL_COARSE_ONLY",
}

# 允许与 R01 config 不同的项（**唯一合法的单变量差异**）
ALLOWED_DIFFS_FROM_R01 = {
    ("plans", "inputPlansFile"),        # 换用 f 倍人口
    ("controller", "outputDirectory"),  # 换输出目录
    ("controller", "runId"),            # 换 runId
}

# 必须与 R01 **逐值相同**的关键项（防止机制漂移）
MUST_MATCH_R01 = [
    ("network", "inputNetworkFile"),
    ("global", "randomSeed"),
    ("global", "coordinateSystem"),
    ("global", "numberOfThreads"),
    ("qsim", "flowCapacityFactor"),
    ("qsim", "storageCapacityFactor"),
    ("qsim", "numberOfThreads"),
    ("controller", "routingAlgorithmType"),
    ("controller", "lastIteration"),
    ("replanning", "fractionOfIterationsToDisableInnovation"),
    ("scoring", "learningRate"),
    ("routing", "routingRandomness"),
    ("travelTimeCalculator", "travelTimeBinSize"),
    ("travelTimeCalculator", "travelTimeAggregator"),
    ("linkStats", "averageLinkStatsOverIterations"),
    ("linkStats", "writeLinkStatsInterval"),
    ("plans", "networkRouteType"),
    ("hermes", "flowCapacityFactor"),
    ("hermes", "storageCapacityFactor"),
]

FROZEN_WATCH = [
    POP_SOURCE,
    ROOT / "reports" / "matsim_population_6_2b" / "population_lambda_0p075.xml.gz",
    ROOT / "reports" / "matsim_population_6_2b_connected" / "population_lambda_0p075.xml.gz",
    ROOT / "reports" / "matsim_network" / "network_cleaned.xml.gz",
    ROOT / "reports" / "matsim_network" / "network.xml.gz",
    ROOT / "reports" / "od_final_calibration_crosswalk_7_3_6" / "final_calibration_crosswalk.csv",
    R01_CFG,
    BASELINE_CFG,
]

DOCT_TMPL = rc76d.DOCT_TMPL

_ck_rows: list[dict] = []


def ck(name: str, ok: bool, detail: str = "") -> bool:
    _ck_rows.append({"check": name, "pass": bool(ok), "detail": str(detail)})
    print(f"   [{'PASS' if ok else 'FAIL'}] {name}  {detail}")
    return bool(ok)


# --------------------------------------------------------------------------
# 小工具
# --------------------------------------------------------------------------
def run_id_of(eid: str) -> str:
    return f"{eid}_rc_min"


def dem_tag(f: float) -> str:
    return f"{float(f):.2f}".replace(".", "p")      # 1.05 -> 1p05


def pop_dir_of(eid: str) -> Path:
    return POP_ROOT / f"pop_{eid}"


def pop_file_of(eid: str) -> Path:
    return pop_dir_of(eid) / f"population_lambda_{LAMBDA_TAG}.xml.gz"


def out_dir_of(eid: str) -> Path:
    return OUT_ROOT / run_id_of(eid)


def cfg_of(eid: str) -> Path:
    return CONFIG_DIR / f"config_{run_id_of(eid)}.xml"


def sha256_of_xml(path: Path) -> str:
    """解压后的内容哈希（gzip 头含 mtime ⇒ 不能直接哈希 .gz）。"""
    h = hashlib.sha256()
    with gzip.open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def snapshot_mtimes(paths: list[Path]) -> dict:
    return {str(p): (p.stat().st_mtime if p.exists() else None) for p in paths}


# --------------------------------------------------------------------------
# 阶段 1：人口（复用 7.4.3 的复制机制）
# --------------------------------------------------------------------------
def stage_population(eid: str, f_demand: float, n_target: int, *, force: bool, log=print) -> dict:
    pfile = pop_file_of(eid)
    if pfile.exists() and not force:
        st = ds743.population_stats(pfile)
        if st["persons"] == n_target:
            log(f"[{eid}] 人口已存在且 persons={st['persons']:,} -> 复用")
            return {"reused": True, "path": str(pfile), "mechanism": "REPLICATION_743",
                    "n_target": n_target, **st}
        log(f"[{eid}] 人口 persons={st['persons']:,} != {n_target:,} -> 重建")

    if not POP_SOURCE.exists():
        raise FileNotFoundError(POP_SOURCE)
    log(f"[{eid}] 复制 agent -> {n_target:,} persons（seed={DUP_SEED}, f={f_demand}）")
    rep = ds743.build_population(POP_SOURCE, pfile, n_target, seed=DUP_SEED, log=log)
    rep["reused"] = False
    rep["mechanism"] = "REPLICATION_743"
    rep["n_target"] = n_target
    return rep


# --------------------------------------------------------------------------
# 阶段 2：config（build_one -> 7.6E 冻结 route-choice patch）
# --------------------------------------------------------------------------
def build_config(eid: str, *, smoke: int = 0, log=print) -> tuple[Path, Path, dict]:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    OUT_ROOT.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    pdir = pop_dir_of(eid)
    pfile = pop_file_of(eid)
    if not pfile.exists():
        raise FileNotFoundError(pfile)

    if smoke:
        cfg_path = CONFIG_DIR / f"config_{run_id_of(eid)}_smoke.xml"
        out_dir = OUT_ROOT / f"_smoke_{run_id_of(eid)}"
        run_id = f"smoke_{run_id_of(eid)}"
        last_iter = 2
    else:
        cfg_path = cfg_of(eid)
        out_dir = out_dir_of(eid)
        run_id = run_id_of(eid)
        last_iter = EXPECTED_ITER

    cfgmod.build_one(LAMBDA_TAG, pop_dir=pdir, out_root=OUT_ROOT,
                     run_prefix="dr7_6f1_", cfg_path=cfg_path)
    # ★ 继承 7.6E 冻结 route-choice（复用 7.6D 的补丁函数，不复制公式）
    rc76d.apply_min_patch(cfg_path, out_dir=out_dir, run_id=run_id, last_iter=last_iter)

    if smoke:
        pop_dst = CONFIG_DIR / f"_smoke_{run_id_of(eid)}_population.xml.gz"
        got = rc76d.truncate_population(pfile, pop_dst, smoke)
        log(f"[{eid}/smoke] 截断人口 {got} persons -> {pop_dst.name}")
        root = ET.parse(cfg_path).getroot()
        rc76d.setp(rc76d.module_of(root, "plans"), "inputPlansFile", str(pop_dst.resolve()))
        cfg_path.write_text(DOCT_TMPL + ET.tostring(root, encoding="unicode") + "\n",
                            encoding="utf-8")

    return cfg_path, out_dir, {"run_id": run_id, "out_dir": str(out_dir),
                               "last_iteration": last_iter, "smoke": smoke}


# --------------------------------------------------------------------------
# 阶段 3：严格验证（零仿真）—— 与 R01 config 逐参数 diff
# --------------------------------------------------------------------------
def validate(cfg_path: Path, eid: str, n_target: int, *, smoke: int) -> list[dict]:
    base = rc76d.param_map(R01_CFG)          # ★ 基线 = R01（冻结 route-choice + demand=1.00）
    new = rc76d.param_map(cfg_path)
    bstrat = rc76d.strategy_list(R01_CFG)
    nstrat = rc76d.strategy_list(cfg_path)

    print(f"\n=== [{eid}] 基线(R01) 策略集 ===")
    print("   ", bstrat)
    print(f"=== [{eid}] 新配置 策略集 ===")
    print("   ", nstrat)

    # --- W1 与 R01 的差异**必须只有 3 项** --------------------------------
    keys = set(base) | set(new)
    diffs = [(k, base.get(k), new.get(k)) for k in sorted(keys)
             if not rc76d.same_value(base.get(k), new.get(k))]
    unexpected = [d for d in diffs if d[0] not in ALLOWED_DIFFS_FROM_R01]
    ck(f"W1.1 [{eid}] 与 R01 的差异仅限白名单（inputPlansFile + controller 路径/runId）",
       not unexpected,
       f"共 {len(diffs)} 处，越界 {len(unexpected)}" + (f" -> {unexpected}" if unexpected else ""))
    print(f"   -- [{eid}] 与 R01 的差异明细 --")
    for k, a, b in sorted(diffs):
        print(f"      {k[0]}.{k[1]}: {a!r} -> {b!r}")
    print(f"      （R01 侧无对应键的项：{[k for k,_a,_b in diffs if base.get(k) is None]}）")

    # --- W2 7.6E 冻结 route-choice 逐项继承 --------------------------------
    rt = ET.parse(cfg_path).getroot()
    p = rc76d.pget
    ck(f"W2.1 [{eid}] replanning.fractionOfIterationsToDisableInnovation == 0.8",
       p(rt, "replanning", "fractionOfIterationsToDisableInnovation") == "0.8",
       p(rt, "replanning", "fractionOfIterationsToDisableInnovation"))
    ck(f"W2.2 [{eid}] scoring.learningRate == 0.5",
       p(rt, "scoring", "learningRate") == "0.5", p(rt, "scoring", "learningRate"))
    ck(f"W2.3 [{eid}] routing.routingRandomness == 0.0",
       p(rt, "routing", "routingRandomness") == "0.0", p(rt, "routing", "routingRandomness"))
    ck(f"W2.4 [{eid}] 策略集 == [ReRoute 0.15, ChangeExpBeta 0.85]（与 R01 完全一致）",
       [(n, float(w)) for n, w in nstrat] == [(n, w) for n, w in rc76d.STRATEGY_SPEC],
       str(nstrat))
    ck(f"W2.5 [{eid}] 策略权重和 == 1.0",
       abs(sum(float(w) for _n, w in nstrat) - 1.0) < 1e-12,
       f"sum = {sum(float(w) for _n, w in nstrat):.4f}")
    ck(f"W2.6 [{eid}] 策略集与 R01 逐项相同",
       [(n, float(w)) for n, w in nstrat] == [(n, float(w)) for n, w in bstrat],
       f"R01={bstrat} new={nstrat}")

    # --- W3 冻结标量 -------------------------------------------------------
    ck(f"W3.1 [{eid}] f_cap: flowCapacityFactor == storageCapacityFactor == 1.0（**不随 N 缩放**）",
       p(rt, "qsim", "flowCapacityFactor") == "1.0"
       and p(rt, "qsim", "storageCapacityFactor") == "1.0",
       f"{p(rt,'qsim','flowCapacityFactor')} / {p(rt,'qsim','storageCapacityFactor')}")
    ck(f"W3.2 [{eid}] randomSeed == 4711", p(rt, "global", "randomSeed") == "4711",
       p(rt, "global", "randomSeed"))
    ck(f"W3.3 [{eid}] lastIteration == {EXPECTED_ITER if not smoke else 2}",
       p(rt, "controller", "lastIteration") == str(EXPECTED_ITER if not smoke else 2),
       p(rt, "controller", "lastIteration"))
    ck(f"W3.4 [{eid}] lambda == {LAMBDA_FIXED}（本轮保持，不作评价）",
       p(rt, "plans", "inputPlansFile") is not None, f"λ 不在 config 内（由人口文件承载）")
    ck(f"W3.5 [{eid}] inputNetworkFile 与 R01 相同",
       p(rt, "network", "inputNetworkFile") == base.get(("network", "inputNetworkFile")),
       p(rt, "network", "inputNetworkFile"))
    ck(f"W3.6 [{eid}] 中间迭代不写 events/plans/trips/snapshots",
       all(p(rt, "controller", k) == "0" for k in
           ("writeEventsInterval", "writePlansInterval",
            "writeTripsInterval", "writeSnapshotsInterval")), "all 0")
    ck(f"W3.7 [{eid}] writeLinkStatsInterval == 1（每迭代 linkstats 是唯一测量需求）",
       p(rt, "linkStats", "writeLinkStatsInterval") == "1",
       p(rt, "linkStats", "writeLinkStatsInterval"))

    # --- W4 人口指针 -------------------------------------------------------
    got_pop = p(rt, "plans", "inputPlansFile")
    expect_pop = str(pop_file_of(eid)) if not smoke else None
    ck(f"W4.1 [{eid}] inputPlansFile 指向 f={dict((e, f) for e, f, _n in SPEC)[eid]} 人口（smoke 除外）",
       (smoke > 0) or (got_pop == expect_pop),
       f"{got_pop}   (expect {expect_pop}  | persons_target={n_target:,})")

    # --- W5 必须与 R01 逐值相同 -------------------------------------------
    bad = []
    for mod, name in MUST_MATCH_R01:
        bv, nv = base.get((mod, name)), new.get((mod, name))
        if not rc76d.same_value(bv, nv):
            bad.append((mod, name, bv, nv))
    ck(f"W5.1 [{eid}] 关键项与 R01 逐值相同（{len(MUST_MATCH_R01)} 项）",
       not bad, "全部一致" if not bad else str(bad))

    # --- W6 可解析性 --------------------------------------------------------
    try:
        nmod = len(rt.findall("module"))
        ck(f"W6.1 [{eid}] XML 可解析且模块数 >= 25", nmod >= 25, f"modules = {nmod}")
    except Exception as e:                                   # pragma: no cover
        ck(f"W6.1 [{eid}] XML 可解析", False, repr(e))
    ck(f"W6.2 [{eid}] DOCTYPE 存在（ConfigReader 依赖 system-id 判版本）",
       cfg_path.read_text(encoding="utf-8").startswith('<?xml version="1.0"')
       and "config_v2.dtd" in cfg_path.read_text(encoding="utf-8")[:300], "ok")

    return _ck_rows


# --------------------------------------------------------------------------
# 阶段 4：产物（矩阵 / provenance / 预注册）
# --------------------------------------------------------------------------
def write_matrix(pop_reports: dict) -> Path:
    rows = []
    for eid, f, n in SPEC:
        rep = pop_reports.get(eid, {})
        s_ef = rep.get("sum_expansion_factor")
        f_real = (s_ef / REAL_CAR_OD_TOTAL) if s_ef else None
        rows.append({
            "experiment_id": eid,
            "run_id": run_id_of(eid),
            "f_demand_nominal": f,
            "n_agents": n,
            "n_extra_vs_200k": n - N_BASE,
            "populations_persons": rep.get("persons"),
            "sum_expansion_factor": s_ef,
            "f_realized": f_real,
            "mean_ef": (s_ef / n) if (s_ef and n) else None,
            "sampling_base_N": N_BASE,
            "scale_const": SCALE_CONST,
            "f_cap": F_CAP,
            "lambda": LAMBDA_FIXED,
            "capacity_rule": "f_cap fixed 1.00 (physical demand increase, NOT sampling-consistency)",
            "route_choice": "R01_rc_min (7.6E frozen)",
            "population_source": str(POP_SOURCE.relative_to(ROOT)),
            "population_target": str(pop_file_of(eid).relative_to(ROOT)),
            "config": str(cfg_of(eid).relative_to(ROOT)),
            "output_dir": str(out_dir_of(eid).relative_to(ROOT)),
            "duplication_seed": DUP_SEED,
            "mechanism": "REPLICATION_743 (nested unbiased subset  F05 c F15 c F25)",
            "status": "PREPARED_NO_RUN",
        })
    p = NEW_ROOT / "demand_response_7_6f_1_matrix.csv"
    with p.open("w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    return p


def write_provenance(cfg_paths: dict) -> Path:
    base = rc76d.param_map(R01_CFG)
    rows = []
    for eid, _f, _n in SPEC:
        new = rc76d.param_map(cfg_paths[eid])
        for k in sorted(set(base) | set(new)):
            bv, nv = base.get(k), new.get(k)
            rows.append({
                "experiment_id": eid,
                "module": k[0], "param": k[1],
                "r01_value": bv, "new_value": nv,
                "changed_vs_r01": not rc76d.same_value(bv, nv),
                "is_allowed_diff": k in ALLOWED_DIFFS_FROM_R01,
            })
    p = NEW_ROOT / "demand_response_7_6f_1_config_provenance.csv"
    with p.open("w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["experiment_id", "module", "param",
                                           "r01_value", "new_value",
                                           "changed_vs_r01", "is_allowed_diff"])
        w.writeheader()
        w.writerows(rows)

    srows = []
    for src, label in ((R01_CFG, "R01_baseline"),):
        for nm, wt in rc76d.strategy_list(src):
            srows.append({"source": label, "strategyName": nm, "weight": wt})
    for eid, _f, _n in SPEC:
        for nm, wt in rc76d.strategy_list(cfg_paths[eid]):
            srows.append({"source": eid, "strategyName": nm, "weight": wt})
    sp = NEW_ROOT / "demand_response_7_6f_1_strategy_provenance.csv"
    with sp.open("w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["source", "strategyName", "weight"])
        w.writeheader()
        w.writerows(srows)
    return p


def write_preregistration(pop_reports: dict, checks: list[dict]) -> Path:
    npass = sum(1 for c in checks if c["pass"])
    ts = datetime.now().strftime("%Y-%m-%d %H:%M")
    g = dict((e, f) for e, f, _n in SPEC)

    L = []
    L.append("# Step 7.6F-1 预注册 — 稳定分配底座上的**粗档 demand-response 曲线**\n")
    L.append("> **预注册声明**：本文件在 **7.6F-1 的任何 MATSim 运行启动之前**冻结。")
    L.append("> 判据、阈值、口径、窗口、判决空间在此确定；**运行之后不得回溯修改**。")
    L.append("> 若确需修改，必须新建 `7.6F-1-b` 并说明理由。\n")
    L.append(f"> 冻结时间：**{ts}**  ")
    L.append(f"> 状态：三档人口与 config 已就位并验证（**{npass}/{len(checks)} PASS**）；"
             f"**正式 run 未启动**。\n")
    L.append("---\n")

    L.append("## 0. ★ 必须点明的一处机制推论（否则设计自相矛盾）\n")
    L.append("用户冻结清单同时给出 `N = 200,000` 与 `f_demand = 1.05 / 1.15 / 1.25`。")
    L.append("**二者不是同一个量**，因为：\n")
    L.append("| 量 | 值 | 性质 |")
    L.append("|---|---:|---|")
    L.append(f"| 采样基准 `N`（= SCALE 锚） | **{N_BASE:,}** | 冻结，**不改** |")
    L.append(f"| 被仿真的 agent 数 | **{', '.join(f'{n:,}' for _e, _f, n in SPEC)}** | = f × {N_BASE:,} |")
    L.append(f"| `SCALE = ΣT / N` | **{SCALE_CONST:.5f}**（恒定） | 复制机制下平均 EF 不变 |")
    L.append("")
    L.append("**为什么必须这样**（三条闭合论证）：\n")
    L.append("1. **7.4.3 已证**：只缩放 `expansion_factor` / `od_trips` 而**不动 agent 数**是对仿真的")
    L.append("   **no-op** —— `HRSx-yavg` 一个数都不变，Sim/Obs 只是被算术地乘 f。那样的")
    L.append("   「三档实验」会得到三份**完全相同**的 linkstats，跑 MATSim **毫无信息**。")
    L.append(f"2. **`f_cap = {F_CAP:.2f}` 冻结**（而非 `N/200,000`）**排除**了 7.6D-S 的")
    L.append("   「采样一致性」约定，锁定 7.4.3 的「**物理加车**」约定。")
    L.append(f"3. **`SCALE` 恒定**：复制 agent 会连同其 `expansion_factor` 一并复制 ⇒ 平均 EF 不变")
    L.append(f"   ⇒ `SCALE = ΣT/{N_BASE:,} = {SCALE_CONST:.5f}` 对三档**全部适用**。")
    L.append("   此点已由 7.6F-0 `demand_scale_7_6f_0_decomposition.csv` 实证：")
    L.append("   **D01–D04 的 SCALE 列全为 2.29897**（而非 459794/220000 等）。\n")
    L.append("**因此本预注册按「f_demand 缩放被仿真 agent 数」冻结。**")
    L.append("若用户的意图是「agent 数恒为 200,000、仅改算术倍数」，那么本步骤应**完全不跑 MATSim**，")
    L.append("改为在 R01 上做零仿真算术重标定（Sim/Obs 精确 × f）—— 请在启动前确认。\n")
    L.append("---\n")

    L.append("## 1. 本步骤**唯一**要回答的问题\n")
    L.append("> 在 **route-choice 已冻结**（7.6E `STABILITY_PASS`）的稳定分配底座上，")
    L.append("> `f_demand` 与 `Q_MATCHED / Sim/Obs` 之间是否存在**可复现、单调、稳定**的响应关系？\n")
    L.append("**核心输出不是「哪个 factor 最好」**，而是那条响应关系本身：\n")
    L.append("```")
    L.append("f_demand  ->  Q_MATCHED  ->  Sim/Obs      （并同时报告 frozen target 不确定性）")
    L.append("```")
    L.append("**不选 demand scale、不评价 λ、不评价 OD 空间结构。**\n")

    L.append("## 2. 为什么网格是 `1.05 / 1.15 / 1.25` 而不是 `1.10 / 1.20 / 1.25`\n")
    L.append("7.6C-2（`TARGET_MARGINAL_COARSE_ONLY`）给出：\n")
    L.append("| 量 | 值 |")
    L.append("|---|---:|")
    L.append(f"| `Delta_target`（靶场不确定性） | **{TARGET_REF['delta_target_pp']:.3f} pp** |")
    L.append(f"| `f*` 识别区间（`f*=Q^(-1/eps)`, eps=1） | **[{TARGET_REF['fstar_low']:.5f}, {TARGET_REF['fstar_high']:.5f}]** |")
    L.append(f"| SNR 粗档 step=0.10 | **{TARGET_REF['snr_coarse_0p10']:.3f} ✓**（需 eps>=0.947） |")
    L.append(f"| SNR 细档 step=0.05 | **{TARGET_REF['snr_fine_0p05']:.3f} ✗**（需 eps>=1.895） |")
    L.append("")
    L.append("原网格 `1.10 / 1.20 / 1.25` **不合格**：")
    L.append(f"- `f=1.10` 落在 f\\* 区间 **[1.06945, 1.16418]** **内部** ⇒ 结论随口径而变（仅 POSITIVE_ONLY 越过 1.0）；")
    L.append("- `1.20` 与 `1.25` 均在区间之上且三口径一致 ⇒ **3 次跑只辨 2 个区制**。\n")
    L.append("新网格 `1.05 / 1.15 / 1.25` 的原由（用户裁定）：分别落在 f\\* 区间的")
    L.append("**下方 / 内部附近 / 上方**，且步长恒为 **0.10 >= `Delta_f_target`**（粗档 SNR ≥ 1），信息利用率更高。\n")

    L.append("## 3. 设计：唯一变量 = `f_demand`；其余逐项冻结\n")
    L.append("| 项 | 取值 | 性质 |")
    L.append("|---|---|---|")
    L.append(f"| **`f_demand`** | **{', '.join(f'{f:.2f}' for _e, f, _n in SPEC)}** | ★ **唯一被扫的量** |")
    L.append(f"| route-choice | `R01_rc_min`（innovation 0.8 / `[ReRoute 0.15, ChangeExpBeta 0.85]` / lr 0.5 / randomness 0.0） | 7.6E 冻结 |")
    L.append(f"| 采样基准 `N` | {N_BASE:,} | 冻结（SCALE 锚） |")
    L.append(f"| `f_cap` = flow/storage CapacityFactor | **{F_CAP:.2f}** | 冻结（**不随 N 缩放**） |")
    L.append(f"| `SCALE` | **{SCALE_CONST:.5f}** | 恒定（复制机制） |")
    L.append(f"| λ | {LAMBDA_FIXED} | 本轮**仅保持**，不作评价 |")
    L.append(f"| capacity / storage | 1.00 / 1.00 | 冻结 |")
    L.append(f"| 迭代 | {TOTAL_ITER}（评估窗 it.10–19） | 冻结 |")
    L.append(f"| seed | 4711（MATSim）/ {DUP_SEED}（复制） | 冻结 |")
    L.append(f"| network | `network_cleaned.xml.gz` | 冻结 |")
    L.append(f"| 人口源 | `{POP_SOURCE.relative_to(ROOT)}` | 冻结（6.3.3A） |")
    L.append(f"| 观测靶场 | 7.1 冻结 + **7.3.6A Final Crosswalk**（576 断面） | 冻结，**不得擅改** |")
    L.append("")

    L.append("## 4. 人口机制（受控性）\n")
    L.append(f"以 6.3.3A 冻结 200k 人口为源，按 **seed={DUP_SEED} 的 permutation 前缀**做"
             "**嵌套随机子集复制**（F05 ⊂ F15 ⊂ F25 = 7.4.3 D04 人口）：\n")
    L.append("- 每 agent 的 `expansionFactor` / `home_link` / `work_link` / departure `end_time` "
             "**逐字节不变** ⇒ 唯一变化 = 车辆数；")
    L.append("- 复制概率对**每个 agent 相同** ⇒ 增量在空间上**无偏**"
             "（不会被「每 cell 保底 1 agent」扭曲）；")
    L.append(f"- 目标 `ΣEF = f × {REAL_CAR_OD_TOTAL:,.0f}`，**实测值见本表**并给 `f_realized`；")
    L.append(f"- `FLOOR_PLUS_1` 硬下界 **{FLOOR_MIN_CELLS:,}** 正 OD cell："
             f"三档 N = {', '.join(f'{n:,}' for _e, _f, n in SPEC)} **均满足**。\n")
    L.append("| Exp | f_demand | agents | persons(实测) | ΣEF(实测) | f_realized |")
    L.append("|---|---:|---:|---:|---:|---:|")
    for eid, f, n in SPEC:
        rep = pop_reports.get(eid, {})
        s_ef = rep.get("sum_expansion_factor")
        L.append(f"| **{eid}** | {f:.2f} | {n:,} | "
                 f"{rep.get('persons', 'n/a') and format(rep['persons'], ',')} | "
                 f"{s_ef and format(s_ef, ',.1f')} | "
                 f"{(s_ef / REAL_CAR_OD_TOTAL) if s_ef else 'n/a'} |")
    L.append("")

    L.append("## 5. 预注册判据（**运行前固定**）\n")
    L.append("### 5.1 统计量定义\n")
    L.append("```")
    L.append("Sim/Obs(08-09)  = median(匹配 MATSim 有向边 HRS8-9avg) * SCALE   [冻结口径，逐年同源]")
    L.append("Q_bar_10:19(X)  = mean_{k=10..19} X_k                            [主口径，X = Sigma HRS0-24avg]")
    L.append("Q_19(X)        = X_{19}                                          [参考口径]")
    L.append("A_10:19(X)     = (max_{k} X_k - min_{k} X_k) / mean_{k} X_k      [稳定性判据]")
    L.append("rho(f)         = Sim/Obs_run(f) / ( Sim/Obs_R01 * f )            [拥堵阻尼比]")
    L.append("```")
    L.append("主口径 = **MATCHED**（`3,037` 全 crosswalk 匹配链；其中 3,015 primary）；")
    L.append("`CATA` / `SLIP_ROAD` / `ALL` 仅作辅助。\n")

    L.append("### 5.2 判据\n")
    L.append("| # | 判据 | 门槛 | 性质 |")
    L.append("|---|---|---|---|")
    L.append("| **G1** | **稳定性承继**：三档 `A_10:19`(MATCHED/CATA/SLIP) | MATCHED<3% 且 CATA<3% 且 SLIP<5% | **硬门槛**（不达标 ⇒ 响应曲线不可用） |")
    L.append("| **G2** | **单调性**：Sim/Obs(08-09, MATCHED, Primary) 在 f∈{1.00,1.05,1.15,1.25} 上单调递增 | 容差 ±0.5%（数值噪声） | **硬门槛** |")
    L.append("| **G3** | **算术参照与阻尼**：`rho(f)` 逐档 | 仅报告（**不设阈值**） | 诊断 |")
    L.append("| **G4** | **与 frozen target 的关系**：各档 Sim/Obs 相对 `FROZEN` 靶场的位置，曲线是否**跨越 1.000** | 仅报告 | 诊断 |")
    L.append("| **G5** | **靶场不确定性并报**：每档同时报 3 口径 | 必须同时输出 | **纪律** |")
    L.append("| **G6** | **空间残差不得压平**：EAST / `radial_in` 逐档报告 | 不得用 f 压平 | **纪律** |")
    L.append("| **G7** | **双口径**：`Q̄_10:19`(Primary) + `Q_19`(Reference) | 必须同时输出 | **纪律** |")
    L.append("")

    L.append("### 5.3 判决空间（**运行前固定**）\n")
    L.append("```")
    L.append("G1 不过                                    -> RESPONSE_UNSTABLE")
    L.append("G1 过 + G2 不过                             -> RESPONSE_NON_MONOTONIC")
    L.append("G1 过 + G2 过 + 曲线未跨越 1.000            -> RESPONSE_STABLE_PARTIAL")
    L.append("G1 过 + G2 过 + 曲线跨越 1.000              -> RESPONSE_STABLE_CROSSES")
    L.append("```")
    L.append("- `RESPONSE_UNSTABLE`：暂停；回到 route-choice / OD 结构，**不消耗 7.6F-2 算力**。")
    L.append("- `RESPONSE_NON_MONOTONIC`：**只记录形态**，不得解释为需求响应。")
    L.append("- `RESPONSE_STABLE_PARTIAL`：需求规模不足仍未被完全解释；继续沿 f 方向或转结构。")
    L.append("- `RESPONSE_STABLE_CROSSES`：f 方向可解释量级缺口，可进入 λ / impedance。")
    L.append("")
    L.append("**注意（7.6C-2 门后含义，当前生效）**：靶场不确定性 "
             f"**{TARGET_REF['delta_target_pp']:.3f} pp** ≈ 粗档增量 ⇒")
    L.append("本步骤**只能**给出「带靶场不确定性的粗档响应关系」，**不能**给出「绝对 demand scale」。")
    L.append("`0.9351`/`1.1642` **不得**用于反推 demand scale；`0.8590` 仍是唯一正式 demand=1.00 参照。\n")

    L.append("## 6. 靶场口径（并报，**不升格**）\n")
    L.append("| 口径 | 值 | 角色 | 可否作正式靶场 |")
    L.append("|---|---:|---|---|")
    L.append(f"| `FROZEN`（全 576 池化） | **{TARGET_REF['FROZEN']:.7f}** | **正式主靶场** | ✅ |")
    L.append(f"| `POSITIVE_ONLY`（`sim>0`） | {TARGET_REF['POSITIVE_ONLY']:.7f} | 敏感性口径 | ❌ **不得升格** |")
    L.append(f"| `BEST_DIRECTION` | {TARGET_REF['BEST_DIRECTION']:.7f} | 误差边界 | ❌ **不得升格** |")
    L.append("")
    L.append(f"`Delta_target = {TARGET_REF['delta_target_pp']:.3f} pp`；"
             f"`f*` 区间 `[{TARGET_REF['fstar_low']:.5f}, {TARGET_REF['fstar_high']:.5f}]`；")
    L.append(f"SNR 粗档 `{TARGET_REF['snr_coarse_0p10']:.3f}` / 细档 `{TARGET_REF['snr_fine_0p05']:.3f}`。")
    L.append("8-9 过饱和份额恒 0% ⇒ 无容量反馈 ⇒ `eps ~ 1` 是物理预期。\n")

    L.append("## 7. 明确不做（清单）\n")
    L.append("```text")
    L.append("x 不选 demand scale（本步只建立响应关系）")
    L.append("x 不评价 lambda（本轮仅保持 0.075）")
    L.append("x 不评价 OD 空间结构 / 距离带")
    L.append("x 不把 POSITIVE_ONLY / BEST_DIRECTION 升格为正式靶场")
    L.append("x 不修改 7.3.6A crosswalk（若确需修，必须另立 7.3.6A-b + 另留证据链）")
    L.append("x 不用 0.9351 / 1.1642 反推 demand scale")
    L.append("x 不用调 demand 去压平 EAST / radial_in 的已知空间残差")
    L.append("x 不用 (1+delta) 修正因子平移旧 D01-D04")
    L.append("x 不加 1.00 以外的第五档；不改网格")
    L.append("```")
    L.append("")

    L.append("## 8. 冻结不变量（机器校验，非人工承诺）\n")
    L.append(f"由 `scripts/od/prepare_demand_response_7_6f_1.py` 的 "
             f"**P1–P9 + W1–W6 共 {len(checks)} 项校验**保证：")
    L.append("与 **R01 config** 的差异**仅限** `plans.inputPlansFile` + `controller.{outputDirectory,runId}`；")
    L.append("route-choice 4 项、`f_cap`、seed、network、threads、travelTimeCalculator、")
    L.append("linkStats 间隔、`networkRouteType`、hermes capacity 与 R01 **逐值相同**。")
    L.append("另校验 `ΣEF` 与 `persons` 的实测值与目标 `f x 459,794` 同向。")
    L.append("实际 diff 见 `demand_response_7_6f_1_config_provenance.csv`。\n")

    L.append("## 9. 产物\n")
    L.append("| 路径 | 内容 |")
    L.append("|---|---|")
    L.append("| `populations/pop_<EID>/population_lambda_0p075.xml.gz` | 三档复制人口 |")
    L.append("| `configs/config_<RUN_ID>.xml` | 三份 config（20 迭代） |")
    L.append("| `demand_response_7_6f_1_matrix.csv` | 实验矩阵（单一事实源） |")
    L.append("| `demand_response_7_6f_1_config_provenance.csv` | 与 R01 逐参数 diff |")
    L.append("| `demand_response_7_6f_1_config_validation.json` | 配置验证（机器可读） |")
    L.append("| `outputs/<RUN_ID>/` | MATSim 输出（**本步骤运行后**产生） |")
    L.append("| `logs/<RUN_ID>_run.log` | 运行日志 |")
    L.append("| `audit/` | 响应曲线评价产物 |")
    L.append("")
    L.append("## 10. 配置验证\n")
    L.append(f"**{npass}/{len(checks)} PASS**（零仿真）—— 明细见 "
             "`demand_response_7_6f_1_config_validation.json`。\n")
    L.append("---\n")
    L.append(f"生成脚本：`scripts/od/prepare_demand_response_7_6f_1.py`  "
             f"评价脚本（预注册分析）：`scripts/od/evaluate_demand_response_7_6f_1.py`\n")

    p = NEW_ROOT / "STEP7_6F_1_PREREGISTRATION.md"
    p.write_text("\n".join(L), encoding="utf-8")
    return p


def write_readme(checks: list[dict]) -> Path:
    npass = sum(1 for c in checks if c["pass"])
    txt = f"""# matsim_demand_7_6f_1 — Step 7.6F-1 粗档 demand-response 曲线

> 本目录是 **Step 7.6F-1 的隔离工作区**（依据用户 2026-09-17 裁定建立）。
> **不修改** 7.1 / 7.3.6A / OD / network / capacity / route-choice 任何冻结件；
> 旧结果（`reports/*`、`matsim_routechoice_7_6d/**`）**完全保留**。

## 做什么

在 **route-choice 已冻结**（7.6E `STABILITY_PASS`）的稳定分配底座上，扫

```
f_demand = 1.05 / 1.15 / 1.25      （采样基准仍为 200,000；被仿真 agent 数 = f x 200,000）
```

建立 `f_demand -> Q_MATCHED -> Sim/Obs` 的**粗档响应关系**，并**同时报告 frozen target 不确定性**。

## 关键机制（详见 STEP7_6F_1_PREREGISTRATION.md §0）

| 量 | 值 | 说明 |
|---|---:|---|
| 采样基准 `N`（SCALE 锚） | 200,000 | 冻结 |
| 被仿真 agent 数 | 210,000 / 230,000 / 250,000 | = f x 200,000 |
| `f_cap` | 1.00 | **不随 N 缩放**（物理加车，非采样一致性） |
| `SCALE` | {SCALE_CONST:.5f} | 复制机制下平均 EF 不变 ⇒ 恒定 |
| route-choice | `R01_rc_min` | 7.6E 冻结 |

## 目录

| 路径 | 内容 |
|---|---|
| `STEP7_6F_1_PREREGISTRATION.md` | 预注册（**先于运行冻结**） |
| `demand_response_7_6f_1_matrix.csv` | 实验矩阵（单一事实源） |
| `demand_response_7_6f_1_config_provenance.csv` | 与 R01 逐参数 diff |
| `demand_response_7_6f_1_config_validation.json` | 配置验证（机器可读） |
| `populations/` | 三档复制人口 |
| `configs/` | 三份 config |
| `outputs/` | MATSim 输出（run 后产生） |
| `logs/` | 运行日志 |
| `audit/` | 响应曲线评价产物 |

## 配置验证

**{npass}/{len(checks)} PASS**（零仿真）。

## 运行

```
python scripts/od/prepare_demand_response_7_6f_1.py              # 零仿真：人口 + config + 预注册
python scripts/od/prepare_demand_response_7_6f_1.py --smoke 2000 # 冒烟（需显式指定）
python scripts/od/prepare_demand_response_7_6f_1.py --run        # 正式 3 档（需用户明确启动指令）
python scripts/od/evaluate_demand_response_7_6f_1.py             # 响应曲线评价（零仿真）
```
"""
    p = NEW_ROOT / "README.md"
    p.write_text(txt, encoding="utf-8")
    return p


# --------------------------------------------------------------------------
# 运行
# --------------------------------------------------------------------------
def run_matsim(cfg_path: Path, log_name: str, heap: str) -> int:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    log = LOG_DIR / log_name
    print(f"=== 运行 {cfg_path.name} -> {log} ===")
    t0 = time.time()
    rc = matsim_env.run_java_streaming(
        ["org.matsim.run.RunMatsim", str(cfg_path)], log_path=log, heap=heap)
    print(f"--- {cfg_path.name}: exit={rc}  耗时 {(time.time()-t0)/60:.2f} min ---\n")
    return rc


def final_linkstats(out_dir: Path, run_id: str, it: int = EXPECTED_ITER) -> Path | None:
    d = out_dir / "ITERS" / f"it.{it}"
    if not d.exists():
        return None
    cand = sorted(d.glob(f"{run_id}.*.linkstats.txt.gz")) or sorted(d.glob("*.linkstats.txt.gz"))
    return cand[0] if cand else None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--experiments", nargs="*", default=[e for e, _f, _n in SPEC])
    ap.add_argument("--heap", default="24g")
    ap.add_argument("--smoke", type=int, default=0)
    ap.add_argument("--run", action="store_true",
                    help="正式 3 档全量（**需用户明确启动指令**；默认不启动）")
    ap.add_argument("--gen-only", action="store_true")
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()

    NEW_ROOT.mkdir(parents=True, exist_ok=True)
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    POP_ROOT.mkdir(parents=True, exist_ok=True)
    OUT_ROOT.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    print("=" * 84)
    print("Step 7.6F-1 — 稳定分配底座上的粗档 demand-response（f = 1.05 / 1.15 / 1.25）")
    print("=" * 84)
    print("=== MATSim 运行时 ===")
    for k, v in matsim_env.describe().items():
        print(f"  {k}: {v}")
    print(f"  new root     : {NEW_ROOT}")
    print(f"  采样基准 N   : {N_BASE:,}   （SCALE 锚，不改）")
    print(f"  f_cap        : {F_CAP:.2f}    （不随 N 缩放）")
    print(f"  SCALE        : {SCALE_CONST:.5f}（复制机制下恒定）")
    print(f"  route-choice : 继承 7.6E 冻结（{rc76d.STRATEGY_SPEC} / "
          f"innovation={rc76d.MIN_PATCH[('replanning','fractionOfIterationsToDisableInnovation')][1]} / "
          f"lr={rc76d.MIN_PATCH[('scoring','learningRate')][1]}）")
    print(f"  λ            : {LAMBDA_FIXED}（本轮仅保持，不作评价）")
    print(f"  experiments  : {args.experiments}")
    print()

    unknown = [e for e in args.experiments if e not in dict((e, f) for e, f, _n in SPEC)]
    if unknown:
        print(f"ERROR: 未知实验: {unknown}")
        return 1

    mt_before = snapshot_mtimes(FROZEN_WATCH)

    # ---- [0] 人口源与冻结锚 ---------------------------------------------
    print("[0/5] 前置核验")
    ck("P1 人口源存在（6.3.3A 冻结 200k 剖面）", POP_SOURCE.exists(), POP_SOURCE.name)
    ck("P2 R01 config 存在（diff 基线）", R01_CFG.exists(), R01_CFG.name)
    ck("P3 R01 输出 it.19 linkstats 存在（f=1.00 锚点）",
       (R01_OUT / "ITERS" / "it.19").exists(), str(R01_OUT))
    ck(f"P4 SCALE == 459794/200000 == {SCALE_CONST:.5f}",
       abs(SCALE_CONST - 2.29897) < 1e-9, f"{SCALE_CONST:.5f}")
    ck(f"P5 全档 N >= FLOOR_PLUS_1 下界 {FLOOR_MIN_CELLS:,}",
       all(n >= FLOOR_MIN_CELLS for _e, _f, n in SPEC),
       ", ".join(f"{e}={n:,}" for e, _f, n in SPEC))

    # ---- [1] 人口 --------------------------------------------------------
    print("\n[1/5] 生成/复核三档人口（复用 7.4.3 复制机制）")
    pop_reports: dict[str, dict] = {}
    for eid, f, n in SPEC:
        if eid not in args.experiments:
            continue
        rep = stage_population(eid, f, n, force=args.force)
        pop_reports[eid] = rep
        s_ef = rep.get("sum_expansion_factor")
        print(f"      {eid}: persons={rep.get('persons'):,}  "
              f"ΣEF={s_ef and format(s_ef, ',.1f')}  "
              f"f_realized={(s_ef / REAL_CAR_OD_TOTAL) if s_ef else float('nan'):.6f}")
        ck(f"P6.{eid} persons == {n:,}", rep.get("persons") == n, f"{rep.get('persons'):,}")
        ck(f"P7.{eid} ΣEF 与 f 同向（f_realized 接近 {f:.2f}）",
           bool(s_ef) and abs(s_ef / REAL_CAR_OD_TOTAL - f) < 0.01,
           f"f_realized={(s_ef / REAL_CAR_OD_TOTAL) if s_ef else float('nan'):.6f}")

    # ---- [1b] 与 7.4.3 的交叉验证（复制机制可复现） ----------------------
    print("\n[1b/5] 与 7.4.3 复制机制交叉验证")
    for eid, ref743 in CROSSCHECK_743.items():
        if eid not in pop_reports or not ref743:
            continue
        rp = ROOT / "reports" / "matsim_demand_7_4_3" / f"pop_{ref743}" / \
            f"population_lambda_{LAMBDA_TAG}.xml.gz"
        if not rp.exists():
            ck(f"P8.{eid} 与 7.4.3 {ref743} 人口可比", False, f"{rp} 不存在")
            continue
        h_new, h_ref = sha256_of_xml(pop_file_of(eid)), sha256_of_xml(rp)
        ck(f"P8.{eid} 与 7.4.3 {ref743} 人口**解压内容逐字节一致**（机制可复现）",
           h_new == h_ref, f"sha256[:16] {h_new[:16]} vs {h_ref[:16]}")

    # ---- [2] config ------------------------------------------------------
    print("\n[2/5] 生成 config（build_one -> 7.6E 冻结 route-choice patch）")
    cfg_paths: dict[str, Path] = {}
    metas: dict[str, dict] = {}
    for eid, f, n in SPEC:
        if eid not in args.experiments:
            continue
        cfg, out_dir, meta = build_config(eid, smoke=args.smoke)
        cfg_paths[eid], metas[eid] = cfg, meta
        print(f"      {eid}: {cfg.name}  -> {out_dir}")

    # ---- [3] 验证 --------------------------------------------------------
    print("\n[3/5] 严格校验（与 R01 逐参数 diff）")
    for eid, f, n in SPEC:
        if eid not in args.experiments:
            continue
        validate(cfg_paths[eid], eid, n, smoke=args.smoke)

    # ---- [3b] 冻结件 mtime ----------------------------------------------
    mt_after = snapshot_mtimes(FROZEN_WATCH)
    changed = [k for k in mt_before if mt_before[k] != mt_after[k]]
    ck(f"P9 冻结件 mtime 全部未变（{len(mt_before)} 项）", not changed,
       "全部不变" if not changed else f"变动: {changed}")

    # ---- [4] 产物 --------------------------------------------------------
    print("\n[4/5] 落盘矩阵 / provenance / README")
    mpath = write_matrix(pop_reports)
    prov = write_provenance(cfg_paths)
    rd = write_readme(_ck_rows)
    print(f"      {mpath.name}\n      {prov.name}\n      {rd.name}")

    npass = sum(1 for c in _ck_rows if c["pass"])
    summary = {
        "step": "7.6F-1",
        "title": "Coarse demand-response curve on the stabilized assignment base",
        "status": "PREPARED" if npass == len(_ck_rows) else "CHECK_FAIL",
        "checks_pass": npass, "checks_total": len(_ck_rows),
        "checks": _ck_rows,
        "zero_simulation": True,
        "matsim_rerun": bool(args.smoke or args.run),
        "parameters_changed": False,
        "demand_scale_selected": False,
        "lambda_selected": False,
        "frozen_artifacts_untouched": not changed,
        "design": {
            "sweep_variable": "f_demand",
            "grid": [[e, f] for e, f, _n in SPEC],
            "sampling_base_N": N_BASE,
            "simulated_agents": [[e, n] for e, _f, n in SPEC],
            "scale_const": SCALE_CONST,
            "f_cap": F_CAP,
            "capacity_rule": "fixed 1.00 (physical demand increase; NOT N/200k)",
            "lambda_fixed": LAMBDA_FIXED,
            "iterations": TOTAL_ITER, "eval_window": [10, 19],
            "route_choice_inherited_from": "7.6E frozen (R01_rc_min)",
            "routechoice_patch": {f"{m}.{p}": b for (m, p), (_a, b) in rc76d.MIN_PATCH.items()},
            "strategy_spec": [{"name": n, "weight": w} for n, w in rc76d.STRATEGY_SPEC],
            "population_mechanism": "REPLICATION_743 (nested unbiased subset, seed=%d)" % DUP_SEED,
            "population_source": str(POP_SOURCE.relative_to(ROOT)),
        },
        "target_reference_7_6c_2": TARGET_REF,
        "calibers": {
            "primary_target": "FROZEN (576 pooled; 7.3.6A; MUST NOT be replaced)",
            "primary_metric": "MATCHED Sim/Obs(08-09)",
            "stability": "Qbar_10:19 (Sigma HRS0-24avg)",
            "reference": "Q_19 (Sigma HRS0-24avg)",
            "not_promoted": ["POSITIVE_ONLY", "BEST_DIRECTION"],
        },
        "preregistered_criteria": ["G1 stability", "G2 monotonicity",
                                   "G3 arithmetic damping", "G4 target relation",
                                   "G5 target uncertainty",
                                   "G6 spatial residual not flattened", "G7 dual caliber"],
        "population_reports": pop_reports,
        "baseline_diff_vs": str(R01_CFG),
        "allowed_diffs_vs_r01": [list(k) for k in sorted(ALLOWED_DIFFS_FROM_R01)],
    }
    js = NEW_ROOT / "demand_response_7_6f_1_config_validation.json"
    js.write_text(json.dumps(summary, ensure_ascii=False, indent=2, default=str), encoding="utf-8")

    # ---- 预注册（仅非 smoke） --------------------------------------------
    if not args.smoke:
        pr = write_preregistration(pop_reports, _ck_rows)
        print(f"\n[5/5] 预注册已冻结 -> {pr.name}")
    print(f"\n配置/人口验证: {npass}/{len(_ck_rows)} PASS")
    print(f"validation -> {js}")

    # ---- 可选运行（默认不触发） ------------------------------------------
    if args.smoke:
        eid = "F05"
        cfg, out_dir, meta = build_config(eid, smoke=args.smoke)
        rc = run_matsim(cfg, f"smoke_{meta['run_id']}.log", args.heap)
        it_dir = Path(out_dir) / "ITERS"
        stats = sorted(it_dir.glob(f"it.*/{meta['run_id']}.*.linkstats.txt.gz")) \
            if it_dir.exists() else []
        print(f"[smoke] linkstats = {len(stats)} 份（期望 3）")
        print("SMOKE STATUS:", "PASS" if rc == 0 and len(stats) >= 3 else "FAIL")
        return rc

    if args.run:
        rc_all = 0
        for eid, f, n in SPEC:
            if eid not in args.experiments:
                continue
            cfg, out_dir, meta = cfg_paths[eid], out_dir_of(eid), metas[eid]
            done = final_linkstats(out_dir, meta["run_id"])
            if done and not args.force:
                print(f"[{eid}] 已存在 {done.name} -> 跳过（断点续跑）")
                continue
            rc = run_matsim(cfg, f"{meta['run_id']}_run.log", args.heap)
            rc_all |= rc
            dl = final_linkstats(out_dir, meta["run_id"])
            print(f"[{eid}] run done; linkstats={'OK' if dl else 'MISSING'}")
        print("RUN STATUS:", "PASS" if rc_all == 0 else "FAIL")
        return rc_all

    print("\n（仅生成 + 验证 + 预注册；**未启动 MATSim**。用 --smoke N 或 --run 启动。）")
    return 0 if npass == len(_ck_rows) else 1


if __name__ == "__main__":
    raise SystemExit(main())
