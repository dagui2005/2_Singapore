#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""
prepare_lambda_sensitivity_7_6g.py — Step 7.6G：**λ 敏感度 screening**（设计 + 人口 + 配置 +
预注册；**零仿真**；默认不启动 MATSim）。

用户 2026-09-18 08:42 裁定（要点）
----------------------------------
7.6F-1 判 `RESPONSE_STABLE_CROSSES` 后，把 demand scale 从「不可识别」推进到「**条件可识别**」：

    f*_FROZEN(λ=0.075) = 1.1803   ← 条件估计，**不冻结为最终 demand scale**

下一步顺序改为 `7.6F-1 → 7.6G(λ敏感度) → 7.6H(最终标定)`，**不做** crosswalk-b、
**不做**新的 demand 细扫。7.6G 只跑：

    λ ∈ {0.05, 0.075, 0.10}  @  单一 demand level  f ≈ 1.18   （3 档，串行）

动机（7.6F-1 已证）：**调 demand 能解决全局量级，完全不能解决空间结构**
（EAST −32.20%→−31.38%，`radial_in` −28.80%→−30.96%，极差 1.05 / 2.16 pp）。
因此唯一尚未问的问题是：**λ 是否会改变 f\***？

★★ 一个必须先讲清的机制事实（决定 7.6G 的成本结构）
--------------------------------------------------
**λ 不是 MATSim 的运行参数，而是 OD 构建（Gravity+IPF）阶段的参数。**

    5C1  build_prior_od_5c1.py        λ 扫描（LAMBDAS=[.05,.075,.10,.125,.15]）-> prior_od_5c1_lambda_*.parquet
    6.2B build_matsim_population_6_2b λ 扫描 -> population_lambda_*.xml.gz
    6.3.3A build_departure_profile    λ 扫描（DEFAULT_LAMBDAS=[0.05,0.075,0.10]）-> 出发时刻剖面
    7.4.3 / 7.6F-1                    复制机制（f x 200,000）

⇒ **三档 λ 的 200,000 人冻结人口已经存在**（`reports/matsim_departure_6_3_3a/`），
**无需重建任何上游**；7.6G = 复制到 N_sim + 换 config + 跑 20 迭代。

★★ λ 不变性（本步骤的结构性保障，已实测）
----------------------------------------
| 量 | λ=0.05 | λ=0.075 | λ=0.10 |
|---|---|---|---|
| ΣT（5C1 OD 总量） | 1,935,235 | 1,935,235 | 1,935,235 |
| car_od_total（6.2B） | 459,794.0 | 459,794.0 | 459,794.0 |
| ΣEF（6.3.3A 人口） | 459,794.0000 | 459,794.0000 | 459,794.0000 |

⇒ **SCALE = ΣT / N_base = 459794/200000 = 2.29897 对三档 λ 自动成立**，
用户 2026-09-17 的硬约束（「不得按 ΣEF 重算 SCALE」）在 λ 维度上**天然满足**，
不存在「λ 改总量」与「λ 改空间」的混杂。

★★ 零成本机制预探（已有 it.0 λ 分档 linkstats，**非 7.6G 口径**）
--------------------------------------------------------------
旧配置（Innovation=Infinity / lr=1.0 / lastIteration=0）+ 无出发剖面人口，仅作**期望效应量先验**：

  * 全链路 Σ(HRS8-9avg)：λ=0.05 → 0.10 变化 **−0.0786%**，且**非单调**
  * 冻结口径 pooled Sim/Obs（primary）：**+0.5291 pp**（1.063027 → 1.068318）
  * 区域/径向 rel_dev 极差：EAST **0.96 pp**、`radial_in` **0.42 pp**、NE 1.35 pp

对照 7.6F-1 的 demand 方向（f=1.00→1.25）：EAST 极差 **1.05 pp**、`radial_in` **2.16 pp**。

⇒ **先验判读：λ 的移动能力与 demand 同量级（约 1 pp），而 EAST 缺口是 −28 pp
⇒ 期望判决 `LAMBDA_WEAK`。** 但这是 it.0/旧配置的先验——**必须用冻结口径实测**，
不得据此外推（项目纪律：测量而非推断）。

★ demand level 的一个口径澄清（必须点明）
---------------------------------------
用户表格把 `λ=0.075 @ f=1.18` 标为「已有/基准」。**实际上 7.6F-1 只跑了
f = 1.00 / 1.05 / 1.15 / 1.25，从未跑过 1.18。** 因此该点必须二选一：

  (A) **实跑**（推荐）：成本 +1 run（≈85 min），且兼作
      「响应曲线可复现性 + 插值可信度」的对照；
  (B) **插值**：由 7.6F-1 已公布的 4 点插值，FROZEN 口径 = **0.99978468**（线性）
      / 0.99983318（二次）/ 0.99959237（三次），**极差仅 0.0860%**
      —— 远小于靶场不确定性 7.609 pp，但会把插值误差引入 λ 效应的分子。

本预注册按 **(A) 三档全实跑** 冻结（`SPEC` 含 L75）。

冻结项（本步骤一律不动）
------------------------
    route-choice = R01_rc_min（innovation 0.8 / [ReRoute 0.15, ChangeExpBeta 0.85] / lr 0.5 / randomness 0.0）
    N_base       = 200,000（采样基准 / SCALE 锚）  N_sim = f x 200,000 = 236,000
    SCALE        = 2.29897（全档统一，**禁按 ΣEF 重算**）
    f_cap        = 1.00（不随 N 缩放）
    7.3.6A Final Crosswalk = 正式主靶场（不得擅改；如要改须另立 7.3.6A-b）
    MATCHED 为主口径；Q̄_10:19 为主，Q_19 为参考
    EAST / radial_in = 已知空间残差，**不得**通过调 demand / λ 主动压平
    POSITIVE_ONLY / BEST_DIRECTION **不得**升格为正式标定靶场

隔离原则
--------
**不修改** 7.1 / 7.3.6A / OD / network / capacity / population(200k 源) / route-choice 任何冻结件。
新人口、新 config、新输出、新日志、新审计全部落在独立目录：

    matsim_lambda_7_6g/
        README.md
        STEP7_6G_PREREGISTRATION.md
        lambda_sensitivity_7_6g_matrix.csv
        lambda_sensitivity_7_6g_config_provenance.csv
        lambda_sensitivity_7_6g_config_validation.json
        lambda_sensitivity_7_6g_lambda_invariance.csv
        populations/pop_<EID>/population_lambda_<LAMTAG>.xml.gz
        configs/config_<RUN_ID>.xml
        outputs/<RUN_ID>/                （run 后产生）
        logs/                            （run 后产生）
        audit/                           （评价后产生）

用法
----
    python scripts/od/prepare_lambda_sensitivity_7_6g.py            # 造人口 + 生成 config + 验证 + 写预注册（零仿真）
    python scripts/od/prepare_lambda_sensitivity_7_6g.py --smoke 2000
    python scripts/od/prepare_lambda_sensitivity_7_6g.py --run      # **需用户明确启动指令**
"""
from __future__ import annotations

import argparse
import contextlib
import csv
import gzip
import hashlib
import json
import re
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

import make_config_6_3 as cfgmod                     # noqa: E402  build_one
import matsim_env                                    # noqa: E402  Java 运行时
import prepare_routechoice_7_6d as rc76d             # noqa: E402  ★ 7.6E 冻结 route-choice
import run_demand_scale_7_4_3 as ds743               # noqa: E402  ★ 7.4.3 冻结 agent 复制机制
import prepare_demand_response_7_6f_1 as p1          # noqa: E402  ★ 复用其 validate()（不复制逻辑）

# --------------------------------------------------------------------------
# 冻结路径
# --------------------------------------------------------------------------
NEW_ROOT = ROOT / "matsim_lambda_7_6g"
CONFIG_DIR = NEW_ROOT / "configs"
POP_ROOT = NEW_ROOT / "populations"
OUT_ROOT = NEW_ROOT / "outputs"
LOG_DIR = NEW_ROOT / "logs"
AUDIT_DIR = NEW_ROOT / "audit"

R01_ROOT = ROOT / "matsim_routechoice_7_6d"
R01_CFG = R01_ROOT / "configs" / "config_R01_rc_min.xml"
R01_OUT = R01_ROOT / "outputs" / "R01_rc_min"

# 6.3.3A 三档 λ 冻结人口（**本步骤的人口源；不重建上游**）
POP_SRC_DIR = ROOT / "reports" / "matsim_departure_6_3_3a"
OD_5C1_SUMMARY = ROOT / "reports" / "od_prior_5c1" / "prior_od_5c1_summary.csv"
POP62_SUMMARY = ROOT / "reports" / "matsim_population_6_2b" / "population_6_2b_summary.csv"
F1_ROOT = ROOT / "matsim_demand_7_6f_1"

# --------------------------------------------------------------------------
# 冻结标量
# --------------------------------------------------------------------------
LAM_REF = 0.075                    # 参考 λ（仅标注用）
F_LAMBDA = 1.18                    # ★ 唯一 demand level（7.6F-1 条件估计 f*_FROZEN）
N_BASE = 200_000                   # ★ 采样基准（不改）
REAL_CAR_OD_TOTAL = 459_794.0      # Σ expansion_factor（6.2B / 7.6A 冻结锚）
SCALE_CONST = REAL_CAR_OD_TOTAL / N_BASE        # 2.29897（λ 不变性已实测）
DUP_SEED = 20260912                # 与 7.4.3 同 seed
F_CAP = 1.00
TOTAL_ITER = 20
EXPECTED_ITER = 19
FLOOR_MIN_CELLS = 71_136           # 6.2B FLOOR_PLUS_1 硬下界

# ★ 本步骤唯一被扫的量
N_SIM = int(round(F_LAMBDA * N_BASE))           # 236,000
SPEC = [
    ("L05", 0.050, N_SIM),
    ("L75", 0.075, N_SIM),
    ("L10", 0.100, N_SIM),
]
LAMS = [lam for _e, lam, _n in SPEC]

# ---- 7.6F-1 已公布响应曲线（只读引用，用于 λ=0.075 基准与 slope 标定） ----
F1_CURVE = {
    "f": [1.00, 1.05, 1.15, 1.25],
    "FROZEN": [0.8589732, 0.8994456, 0.9767361, 1.0535647],
    "POSITIVE_ONLY": [0.9350621, 0.9791197, 1.0632567, 1.1463563],
    "BEST_DIRECTION": [0.8909674, 0.9333491, 1.0146563, 1.0956645],
}
F1_FSTAR = {"FROZEN": 1.1803, "BEST_DIRECTION": 1.1320, "POSITIVE_ONLY": 1.0748}
# 1.15-1.25 局部割线斜率（λ 敏感性下估计 f*_λ 用；口径见预注册 §8）
F1_SLOPE_LOCAL = (F1_CURVE["FROZEN"][3] - F1_CURVE["FROZEN"][2]) / (1.25 - 1.15)
# λ=0.075 @ f=1.18 的插值基准（仅作对照，不作主结果）
F1_INTERP_F18 = {
    "linear_1p15_1p25": 0.99978468,
    "quad_1p05_1p15_1p25": 0.99983318,
    "cubic_4pt": 0.99959237,
    "spread_pct": 0.0860,
}

# ---- 7.6C-2 已公布靶场（只读引用） --------------------------------------
TARGET_REF = {
    "FROZEN": 0.8589732,
    "POSITIVE_ONLY": 0.9350621,
    "BEST_DIRECTION": 0.8909674,
    "delta_target_pp": 7.609,
    "delta_f_target": 0.09473,
    "fstar_low": 1.06945,
    "fstar_high": 1.16418,
    "verdict_7_6c_2": "TARGET_MARGINAL_COARSE_ONLY",
}

# ---- λ 不变性期望（实测 2026-09-18，作为本步骤的门） ---------------------
LAM_INVARIANCE_EXPECT = {
    "od_total": 1_935_235.0,
    "car_od_total": 459_794.0,
    "sum_expansion_factor": 459_794.0,
    "persons": 200_000,
}

# ---- 7.6G 判决阈值（预注册，冻结） --------------------------------------
TH_GLOBAL_WEAK_PP = 1.0        # |Δ Sim/Obs(0.05->0.10)| < 1.0 pp ⇒ 全局不可辨识
TH_GLOBAL_IDENT_PP = TARGET_REF["delta_target_pp"]    # >= 7.609 pp ⇒ 可辨识（超靶场不确定性）
TH_SPATIAL_ACTIVE_PP = 3.0     # 区域/径向 rel_dev 移动 >= 3 pp ⇒ 空间维度"活跃"
# 先验（it.0 预探）登记，用于判决后的偏差说明
PRIOR_IT0 = {
    "global_delta_pp": 0.5291,
    "total_flow_rel_pct": -0.0786,
    "east_spread_pp": 0.96,
    "radial_in_spread_pp": 0.42,
    "ne_spread_pp": 1.35,
    "caliber": "LEGACY_it0_old_config_NOT_7_6G",
}

ALLOWED_DIFFS_FROM_R01 = {
    ("plans", "inputPlansFile"),        # 换 λ 人口
    ("controller", "outputDirectory"),
    ("controller", "runId"),
}
MUST_MATCH_R01 = p1.MUST_MATCH_R01      # ★ 复用 7.6F-1 的同一张清单（不复制）

FROZEN_WATCH = [
    R01_CFG,
    POP_SRC_DIR / "population_lambda_0p050.xml.gz",
    POP_SRC_DIR / "population_lambda_0p075.xml.gz",
    POP_SRC_DIR / "population_lambda_0p100.xml.gz",
    ROOT / "reports" / "matsim_network" / "network.xml.gz",
    ROOT / "reports" / "od_final_calibration_crosswalk_7_3_6" / "final_calibration_crosswalk.csv",
    OD_5C1_SUMMARY,
    POP62_SUMMARY,
]

DOCT_TMPL = rc76d.DOCT_TMPL
_ck_rows: list[dict] = []


# --------------------------------------------------------------------------
# 小工具
# --------------------------------------------------------------------------
def ck(name: str, ok: bool, detail: str = "") -> bool:
    _ck_rows.append({"check": name, "pass": bool(ok), "detail": str(detail)})
    print(f"   [{'PASS' if ok else 'FAIL'}] {name}  {detail}")
    return bool(ok)


def lam_tag(lam: float) -> str:
    return f"{float(lam):.3f}".replace(".", "p")      # 0.05 -> 0p050


def tag_of(eid: str) -> str:
    return lam_tag(dict((e, l) for e, l, _n in SPEC)[eid])


def lam_of(eid: str) -> float:
    return dict((e, l) for e, l, _n in SPEC)[eid]


def run_id_of(eid: str) -> str:
    return f"{eid}_rc_min"


def pop_dir_of(eid: str) -> Path:
    return POP_ROOT / f"pop_{eid}"


def pop_file_of(eid: str) -> Path:
    return pop_dir_of(eid) / f"population_lambda_{tag_of(eid)}.xml.gz"


def pop_source_of(eid: str) -> Path:
    return POP_SRC_DIR / f"population_lambda_{tag_of(eid)}.xml.gz"


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


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def snapshot_mtimes(paths: list[Path]) -> dict:
    return {str(p): (p.stat().st_mtime if p.exists() else None) for p in paths}


def pop_sum_ef(path: Path) -> dict:
    """流式解析 population xml.gz：persons / ΣEF / EF 极值 / leg 数。"""
    n = 0
    s_ef = 0.0
    ef_min, ef_max = None, None
    n_legs = 0
    with gzip.open(path, "rt", encoding="utf-8", errors="replace") as fh:
        for line in fh:
            s = line.strip()
            if s.startswith("<person "):
                n += 1
            elif 'name="expansionFactor"' in s:
                m = re.search(r">([0-9.eE+-]+)<", s)
                if m:
                    v = float(m.group(1))
                    s_ef += v
                    ef_min = v if ef_min is None else min(ef_min, v)
                    ef_max = v if ef_max is None else max(ef_max, v)
            elif s.startswith("<leg "):
                n_legs += 1
    return {"persons": n, "sum_expansion_factor": s_ef,
            "ef_min": ef_min, "ef_max": ef_max, "n_legs": n_legs}


@contextlib.contextmanager
def _p1_view_7_6g():
    """临时把 7.6F-1 模块的 run 表 / 人口指针指向 7.6G，以**复用其 validate()**。

    ★ 不复制任何校验逻辑；退出时逐项还原，保证 7.6F-1 模块状态不被污染。
    """
    old_spec, old_popf = p1.SPEC, p1.pop_file_of
    old_rows = p1._ck_rows
    p1.SPEC = SPEC
    p1.pop_file_of = pop_file_of
    p1._ck_rows = []
    try:
        yield
    finally:
        p1.SPEC, p1.pop_file_of = old_spec, old_popf
        p1._ck_rows = old_rows


# --------------------------------------------------------------------------
# 阶段 1：人口（复用 7.4.3 的复制机制；源 = 6.3.3A 的 λ 人口，**不重建上游**）
# --------------------------------------------------------------------------
def stage_population(eid: str, lam: float, n_target: int, *, force: bool, log=print) -> dict:
    src = pop_source_of(eid)
    if not src.exists():
        raise FileNotFoundError(f"[{eid}] λ 源人口缺失: {src}")
    pfile = pop_file_of(eid)
    pop_dir_of(eid).mkdir(parents=True, exist_ok=True)

    sst = pop_sum_ef(src)
    if pfile.exists() and not force:
        st = pop_sum_ef(pfile)
        if st["persons"] == n_target:
            log(f"[{eid}] 人口已存在且 persons={st['persons']:,} -> 复用")
            return {"reused": True, "path": str(pfile), "mechanism": "REPLICATION_743",
                    "n_target": n_target, "source": str(src),
                    "source_stats": sst, **st}
        log(f"[{eid}] 人口 persons={st['persons']:,} != {n_target:,} -> 重建")

    log(f"[{eid}] λ={lam:.3f} 复制 agent -> {n_target:,} persons（seed={DUP_SEED}）")
    ds743.build_population(src, pfile, n_target, seed=DUP_SEED, log=log)
    # ★ 以**产物文件**的实测值为准（ground truth），不依赖上游返回值
    st = pop_sum_ef(pfile)
    return {"reused": False, "path": str(pfile), "mechanism": "REPLICATION_743",
            "n_target": n_target, "source": str(src),
            "source_stats": sst, "source_sha256_content": sha256_of_xml(src),
            "product_sha256_content": sha256_of_xml(pfile), **st}


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

    cfgmod.build_one(tag_of(eid), pop_dir=pdir, out_root=OUT_ROOT,
                     run_prefix="ls7_6g_", cfg_path=cfg_path)
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
# 阶段 3：验证（零仿真）—— 复用 7.6F-1 的 validate()，另加 λ 专属门
# --------------------------------------------------------------------------
def validate(cfg_path: Path, eid: str, n_target: int, *, smoke: int) -> list[dict]:
    """复用 `prepare_demand_response_7_6f_1.validate()`（W1–W6，逐参数 diff + route-choice 继承），
    另加 L 系列 λ 专属门。W 系列结果**归并进本模块的 `_ck_rows`**。"""
    with _p1_view_7_6g():
        p1.validate(cfg_path, eid, n_target, smoke=smoke)
        w_rows = list(p1._ck_rows)
    _ck_rows.extend(w_rows)          # W1–W6 进入本步骤的累计校验表

    # --- L 系列：λ 专属门 -------------------------------------------------
    rt = ET.parse(cfg_path).getroot()

    # L1: λ 由人口文件承载（config 内无 λ 参数）
    ck(f"L1 [{eid}] λ 由 inputPlansFile 承载（config 内无 λ 形参）",
       rc76d.pget(rt, "plans", "inputPlansFile") == str(pop_file_of(eid)),
       f"λ={lam_of(eid):.3f}  tag={tag_of(eid)}")

    # L2: 源人口 = 对应 λ 的 6.3.3A 冻结人口
    src = pop_source_of(eid)
    sst = pop_sum_ef(src) if src.exists() else {"persons": None, "sum_expansion_factor": None}
    ck(f"L2 [{eid}] 源人口 = 6.3.3A 的 λ={lam_of(eid):.3f} 冻结人口且 persons=200,000",
       src.exists() and sst["persons"] == LAM_INVARIANCE_EXPECT["persons"],
       f"{src.name}  persons={sst['persons']}")

    # L3: λ 不变性 —— ΣEF 跨 λ 应逐位一致（⇒ SCALE 恒定）
    ck(f"L3 [{eid}] 源人口 ΣEF == {LAM_INVARIANCE_EXPECT['sum_expansion_factor']:.1f}（λ 不变性）",
       sst["sum_expansion_factor"] is not None
       and abs(sst["sum_expansion_factor"]
               - LAM_INVARIANCE_EXPECT["sum_expansion_factor"]) < 1e-3,
       f"ΣEF={sst['sum_expansion_factor']!r}")

    # L4: 复制人口 persons == N_sim 且 f_realized 如实记录
    pf = pop_file_of(eid)
    rp = pop_sum_ef(pf) if pf.exists() else {"persons": None, "sum_expansion_factor": None}
    f_real = (rp["sum_expansion_factor"] / REAL_CAR_OD_TOTAL
              if rp["sum_expansion_factor"] is not None else float("nan"))
    ck(f"L4 [{eid}] 复制人口 persons == {n_target:,}",
       rp["persons"] == n_target, f"persons={rp['persons']}")
    ck(f"L4b [{eid}] f_realized 与标称 {F_LAMBDA} 偏差 < 0.01",
       abs(f_real - F_LAMBDA) < 0.01, f"f_realized={f_real:.7f}")

    # L5: SCALE 冻结 —— 禁按 ΣEF/N_sim 重算（仅披露）
    scale_re = (rp["sum_expansion_factor"] / n_target
                if rp["sum_expansion_factor"] is not None else float("nan"))
    ck(f"L5 [{eid}] SCALE 采用 {SCALE_CONST:.5f}（**不按 ΣEF/N_sim 重算**）",
       abs(SCALE_CONST - 2.29897) < 1e-9,
       f"若重算={scale_re:.6f}  Δ={((scale_re - SCALE_CONST) / SCALE_CONST * 1e6):+.2f} ppm（NOT USED）")

    return _ck_rows


# --------------------------------------------------------------------------
# 阶段 4：产物
# --------------------------------------------------------------------------
def write_matrix(pop_reports: dict) -> Path:
    rows = []
    for eid, lam, n in SPEC:
        r = pop_reports.get(eid, {})
        rows.append({
            "experiment_id": eid,
            "lambda_per_min": lam,
            "lambda_tag": tag_of(eid),
            "f_demand": F_LAMBDA,
            "f_demand_nominal": F_LAMBDA,        # 供复用 evaluate_demand_response_7_6f_1.scale_audit()
            "n_agents": n,
            "scale_used": SCALE_CONST,
            "scale_rule": "FROZEN_2.29897_NOT_RECOMPUTED",
            "f_realized": (r.get("sum_expansion_factor", float("nan")) / REAL_CAR_OD_TOTAL
                           if r.get("sum_expansion_factor") else float("nan")),
            "sum_expansion_factor": r.get("sum_expansion_factor"),
            "persons": r.get("persons"),
            "pop_source": str(pop_source_of(eid)),
            "pop_source_sum_ef": (r.get("source_stats") or {}).get("sum_expansion_factor"),
            "route_choice": "R01_rc_min",
            "f_cap": F_CAP,
            "target": "7.3.6A_FROZEN",
            "primary_metric": "MATCHED_SimObs_08_09",
            "primary_window": "Qbar_10:19",
            "reference_window": "Q_19",
            "run_id": run_id_of(eid),
        })
    p = NEW_ROOT / "lambda_sensitivity_7_6g_matrix.csv"
    with open(p, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    return p


def write_lambda_invariance() -> Path:
    """逐 λ 抽出上游三张表的冻结量，机器校验 λ 不变性。"""
    rows = []
    try:
        import pandas as pd
        od = pd.read_csv(OD_5C1_SUMMARY)
        pop62 = pd.read_csv(POP62_SUMMARY) if POP62_SUMMARY.exists() else None
    except Exception:
        od, pop62 = None, None
    for eid, lam, _n in SPEC:
        r = {"experiment_id": eid, "lambda_per_min": lam}
        if od is not None:
            m = od[od["lambda_per_min"].round(3) == round(lam, 3)]
            r["od_total_5c1"] = float(m["od_total"].iloc[0]) if len(m) else None
            r["weighted_mean_travel_time_min"] = (
                float(m["weighted_mean_travel_time_min"].iloc[0]) if len(m) else None)
            r["nonzero_od_cells"] = int(m["nonzero_od_cells"].iloc[0]) if len(m) else None
        if pop62 is not None:
            m2 = pop62[pop62["lambda_per_min"].round(3) == round(lam, 3)]
            r["car_od_total_6_2b"] = float(m2["car_od_total"].iloc[0]) if len(m2) else None
        st = pop_sum_ef(pop_source_of(eid)) if pop_source_of(eid).exists() else {}
        r["source_persons"] = st.get("persons")
        r["source_sum_expansion_factor_6_3_3a"] = st.get("sum_expansion_factor")
        rows.append(r)
    p = NEW_ROOT / "lambda_sensitivity_7_6g_lambda_invariance.csv"
    try:
        import pandas as pd
        pd.DataFrame(rows).to_csv(p, index=False, encoding="utf-8-sig")
    except Exception:
        with open(p, "w", encoding="utf-8-sig", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            w.writeheader()
            w.writerows(rows)
    return p


def write_provenance(cfg_paths: dict) -> Path:
    base = rc76d.param_map(R01_CFG)
    rows = []
    for eid in cfg_paths:
        new = rc76d.param_map(cfg_paths[eid])
        keys = set(base) | set(new)
        for k in sorted(keys):
            a, b = base.get(k), new.get(k)
            if rc76d.same_value(a, b):
                continue
            rows.append({"experiment_id": eid, "module": k[0], "param": k[1],
                         "r01_value": a, "new_value": b,
                         "in_whitelist": k in ALLOWED_DIFFS_FROM_R01})
    p = NEW_ROOT / "lambda_sensitivity_7_6g_config_provenance.csv"
    with open(p, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["experiment_id", "module", "param",
                                          "r01_value", "new_value", "in_whitelist"])
        w.writeheader()
        w.writerows(rows)
    return p


def write_preregistration(pop_reports: dict, checks: list[dict], mt_before: dict) -> Path:
    L = []
    A = L.append
    A("# Step 7.6G 预注册 — λ 敏感度 screening（三档 λ × 单一 demand level）\n")
    A(f"> 冻结时间：**{datetime.now().isoformat(timespec='minutes')}**  ")
    A("> 状态：三档人口与 config 已就位并验证；**正式 run 未启动**（需用户明确启动指令）。\n")
    A("---\n")
    A("## 0. 机制事实：λ 作用在 OD 构建层，不是 MATSim 运行参数\n")
    A("| 步骤 | 脚本 | λ 处理 | 产物 |")
    A("|---|---|---|---|")
    A("| 5C1 | `build_prior_od_5c1.py` | `LAMBDAS=[.05,.075,.10,.125,.15]` | `prior_od_5c1_lambda_*.parquet` |")
    A("| 6.2B | `build_matsim_population_6_2b.py` | `DEFAULT_LAMBDAS=[0.05,0.075,0.10]` | `population_lambda_*.xml.gz` |")
    A("| 6.3.3A | `build_departure_profile_6_3_3a.py` | `DEFAULT_LAMBDAS=[0.05,0.075,0.10]` | 出发时刻剖面人口 |")
    A("| 7.4.3 / 7.6F-1 | `run_demand_scale_7_4_3.py` | 复制机制 | `f × 200,000` persons |")
    A("")
    A("**⇒ 三档 λ 的 200,000 人冻结人口已存在**（`reports/matsim_departure_6_3_3a/`），")
    A("7.6G **不重建任何上游**，只做「复制到 N_sim + 换 config + 20 迭代」。\n")
    A("## 1. λ 不变性门（本步骤的结构性保障）\n")
    A("| 量 | λ=0.05 | λ=0.075 | λ=0.10 | 判定 |")
    A("|---|---:|---:|---:|---|")
    v = LAM_INVARIANCE_EXPECT
    A(f"| ΣT（5C1 OD 总量） | {v['od_total']:,.0f} | {v['od_total']:,.0f} | {v['od_total']:,.0f} | **逐位一致** |")
    A(f"| car_od_total（6.2B） | {v['car_od_total']:,.1f} | {v['car_od_total']:,.1f} | {v['car_od_total']:,.1f} | **逐位一致** |")
    A(f"| ΣEF（6.3.3A 人口） | {v['sum_expansion_factor']:,.4f} | {v['sum_expansion_factor']:,.4f} | {v['sum_expansion_factor']:,.4f} | **逐位一致** |")
    A(f"| persons | {v['persons']:,} | {v['persons']:,} | {v['persons']:,} | **逐位一致** |")
    A("")
    A(f"⇒ **`SCALE = {SCALE_CONST:.5f}` 对三档 λ 自动成立**；不存在「λ 改总量」与「λ 改空间」的混杂。")
    A("用户 2026-09-17 硬约束（不得按 ΣEF 重算 SCALE）在 λ 维度上**天然满足**。\n")
    A("★ λ 确实改变的东西（上游 5C1 实测，机制预信号）：")
    A("")
    A("| λ | `weighted_mean_travel_time_min` | `nonzero_od_cells` |")
    A("|---|---:|---:|")
    A("| 0.05 | 18.082 | 71,136 |")
    A("| 0.075 | 17.811 | 71,136 |")
    A("| 0.10 | 17.533 | 71,136 |")
    A("")
    A("## 2. 网格与 demand level 的理由\n")
    A("**唯一被扫的量 = λ ∈ {0.05, 0.075, 0.10}；demand level 固定为 f = "
      f"{F_LAMBDA}（N_sim = {N_SIM:,}）。**\n")
    A("| run | λ | N_sim | SCALE | route-choice |")
    A("|---|---:|---:|---:|---|")
    for eid, lam, n in SPEC:
        A(f"| {eid} | {lam:.3f} | {n:,} | {SCALE_CONST:.5f} | R01_rc_min |")
    A("")
    A("理由：")
    A(f"1. **f = {F_LAMBDA} = 7.6F-1 的 FROZEN 条件估计 f\\* = {F1_FSTAR['FROZEN']}**，")
    A("   即把 demand level 钉在「当前最佳条件估计」上，使 λ 成为唯一变量；")
    A("2. 三档 λ 落在 5C1 原始扫描的中心区（0.125/0.15 使 Table118 约束残差劣化到 3.67%/5.76%，不取）；")
    A("3. **不做 3×4 demand×λ 全网格**（12 次仿真不必要）：先做 λ screening，")
    A("   仅当 λ 显著改变 demand response 时才在相邻 λ 上补小型 demand refinement。\n")
    A("### ★ 一处必须点明的口径澄清\n")
    A("用户表格把 `λ=0.075 @ f=1.18` 标为「已有/基准」。**实际上 7.6F-1 只跑了 "
      "f = 1.00 / 1.05 / 1.15 / 1.25，从未跑过 1.18。** 因此：")
    A("")
    A("| 方案 | 成本 | FROZEN 值 | 说明 |")
    A("|---|---:|---:|---|")
    A("| (A) **实跑 L75**（本预注册采用） | +1 run ≈85 min | 待测 | 兼作响应曲线可复现性与插值可信度对照 |")
    A(f"| (B) 插值 | 0 | **{F1_INTERP_F18['linear_1p15_1p25']:.8f}**（线性） | 二次 {F1_INTERP_F18['quad_1p05_1p15_1p25']:.8f} / 三次 {F1_INTERP_F18['cubic_4pt']:.8f}；**极差仅 {F1_INTERP_F18['spread_pct']:.4f}%** |")
    A("")
    A("插值极差 0.086% 远小于靶场不确定性 7.609 pp，但方案 (A) 可把插值误差从 λ 效应的")
    A("分子中彻底移除，且提供一次**独立复现控制**。本步骤按 (A) 冻结。\n")
    A("## 3. 零成本机制预探（已有 it.0 λ 分档 linkstats）\n")
    A("> ⚠️ **口径声明**：这些 it.0 来自旧配置（`Innovation=Infinity` / `lr=1.0` / "
      "`lastIteration=0`）且人口为 `6_2b_connected`（**无 6.3.3A 出发剖面**）。")
    A("> **不是 7.6G 结果**，只作**期望效应量先验**，用于给 §5 判据设定合理量级。\n")
    A("| 指标 | λ=0.05 | λ=0.075 | λ=0.10 | Δ(0.10−0.05) |")
    A("|---|---:|---:|---:|---:|")
    A("| 冻结口径 pooled Sim/Obs（primary） | 1.063027 | 1.063662 | 1.068318 | **+0.5291 pp** |")
    A("| 全链路 Σ(HRS8-9avg) | 48,087,442 | 48,002,925 | 48,049,640 | **−0.0786%**（非单调） |")
    A("")
    A("区域/径向 rel_dev(%)：EAST −29.23 → −28.60 → −28.27（极差 **0.96 pp**）；")
    A("`radial_in` −27.85 → −27.77 → −28.19（极差 **0.42 pp**）；NORTH-EAST 极差 1.35 pp。\n")
    A("**对照 7.6F-1 的 demand 方向**（f=1.00→1.25）：EAST 极差 **1.05 pp**、"
      "`radial_in` **2.16 pp**。")
    A("")
    A("⇒ **先验判读：λ 的移动能力与 demand 同量级（约 1 pp），而 EAST 缺口是 −28 pp "
      "⇒ 期望判决 `LAMBDA_WEAK`。**")
    A("⇒ 但这是 it.0/旧配置的先验 —— **必须用冻结口径实测**（项目纪律：测量而非推断）。")
    A("若实测与先验冲突，需在报告中说明收敛/route-choice 放大的机制。\n")
    A("## 4. 口径（冻结，不可混用）\n")
    A("| 口径 | 定义 | 角色 |")
    A("|---|---|---|")
    A("| `FROZEN` | 全 576 池化（primary candidate） | **正式主靶场**（不得擅改） |")
    A("| `POSITIVE_ONLY` | 仅 sim>0 池化 | 敏感性（**不得升格**） |")
    A("| `BEST_DIRECTION` | `max(median(fwd),median(rev)) × SCALE` | 误差边界（**不得升格**） |")
    A("")
    A(f"- 双口径：Primary `Q̄_10:19`（收敛窗 it.10–19 周期均值）/ Reference `Q_19`（单点）")
    A(f"- 窗口纪律：Sim/Obs 用 `HRS8-9avg`；稳定性 `Q`/`Q̄` 用 `Σ HRS0-24avg`，**永不混用**")
    A(f"- 目标不确定性（7.6C-2）：`Δ_target` = **{TARGET_REF['delta_target_pp']} pp**，"
      f"`Δ_f_target` = **{TARGET_REF['delta_f_target']}**\n")
    A("## 5. 判据 G1–G8 与判决空间（预注册，冻结）\n")
    A("**判据（全部要求 PASS 才算本步骤技术有效）**\n")
    A("| # | 判据 | 阈值 |")
    A("|---|---|---|")
    A("| G1 | 三档 linkstats 齐备（it.0–19） | 3/3 档 × 20/20 迭代 |")
    A("| G2 | 与 7.6C-2 对账（R01 三口径） | 逐位（tol 1e-6） |")
    A("| G3 | 与 7.6D 审计缓存对账（R01 Q̄_10:19 四项） | 逐位 |")
    A("| G4 | SCALE 全档统一 2.29897，ΣEF/N 仅披露 | P1b/P1c PASS |")
    A("| G5 | 稳定性 `A_10:19`(MATCHED) | < 3.0% |")
    A("| G6 | 收敛窗 `parity_gap_rel` | < 5.0% |")
    A("| G7 | 空间残差**只报告不压平**（EAST / radial_in 登记为已知偏差） | 无调参 |")
    A("| G8 | λ=0.075 @ f=1.18 与 7.6F-1 插值基准的一致性 | \u007cΔ\u007c 记录（不设硬阈，作复现控制） |")
    A("")
    A("**判决空间（两维）**\n")
    A("| 维度 | 判据 | 标签 |")
    A("|---|---|---|")
    A(f"| 全局 λ 可辨性 | `\u007cΔ Sim/Obs(0.05→0.10)\u007c < {TH_GLOBAL_WEAK_PP} pp` | `LAMBDA_WEAK`（情况 A） |")
    A(f"| | `{TH_GLOBAL_WEAK_PP} ≤ \u007cΔ\u007c < {TH_GLOBAL_IDENT_PP} pp` | `LAMBDA_DETECTABLE_NOT_IDENTIFIABLE` |")
    A(f"| | `\u007cΔ\u007c ≥ {TH_GLOBAL_IDENT_PP} pp`（= Δ_target） | `LAMBDA_IDENTIFIABLE`（情况 B） |")
    A(f"| 空间活跃性 | 区域/径向 rel_dev 极差 `≥ {TH_SPATIAL_ACTIVE_PP} pp` | `SPATIAL_ACTIVE` |")
    A(f"| | `< {TH_SPATIAL_ACTIVE_PP} pp` | `SPATIAL_INERT` |")
    A("")
    A("**判决 = (全局标签) / (空间标签)**，例如 `LAMBDA_WEAK / SPATIAL_INERT`。\n")
    A(f"阈值依据：① {TH_GLOBAL_WEAK_PP} pp ≈ 7.6F-1 中 demand 全幅（f=1.00→1.25，19.5 pp）的 1/20，")
    A("低于此即「杠杆可忽略」；② 7.609 pp = 7.6C-2 的 `Δ_target`，是**绝对**识别的下限；")
    A("③ 空间 3.0 pp 阈值基于：7.6F-1 中 demand 对 EAST / radial_in 的移动仅 1.05 / 2.16 pp，")
    A("若 λ 不能超过此量级，则面对 −28 ~ −32 pp 的结构缺口**不构成修复路径**。\n")
    A("**λ 对 f\\* 的影响（估计，不是直接观测）**\n")
    A(f"- 参考斜率（7.6F-1 的 1.15–1.25 局部割线）：`s_ref = {F1_SLOPE_LOCAL:.6f}`（每单位 f）")
    A("- `f*_λ ≈ f_0 + (1 − SimObs_λ)/s_ref`，`f_0 = 1.18`；`Δf*_λ ≈ −ΔSim/Obs_λ / s_ref`")
    A(f"- 换算：`\u007cΔSim/Obs\u007c = {TH_GLOBAL_IDENT_PP} pp ⟺ \u007cΔf*\u007c ≈ "
      f"{TH_GLOBAL_IDENT_PP/100/F1_SLOPE_LOCAL:.5f}`（与 7.6C-2 的 `Δ_f_target` = "
      f"{TARGET_REF['delta_f_target']} 自洽）")
    A("- ⚠️ **该估计假设局部斜率 λ 不变**；只有一次 demand level/λ，**不能**直接观测 `f*_λ`。\n")
    A("## 6. 明确不做\n")
    A("```text")
    A("x 不做 crosswalk-b（7.3.6A 保持冻结）")
    A("x 不做新的 demand 细扫（1.17/1.18/1.19/1.20）")
    A("x 不做 3×4 demand×λ 全网格")
    A("x 不把 0.8590 / 0.9351 或任何倒数值预先用于选 λ 或 demand scale")
    A("x 不把 POSITIVE_ONLY / BEST_DIRECTION 升格为正式靶场")
    A("x 不用调 demand 或 λ 去压平 EAST / radial_in")
    A("x 不改任何模型参数（本步骤的唯一变量是 λ，且 λ 由人口文件承载）")
    A("```\n")
    A("## 7. 冻结不变量（机器校验）\n")
    A(f"由 `scripts/od/prepare_lambda_sensitivity_7_6g.py` 的 W1–W6（复用 7.6F-1 `validate()`，")
    A(f"**不复制逻辑**）+ L1–L6 共 **{len(checks)} 项校验**保证：")
    A("- 与 **R01 config** 的差异**仅限** `plans.inputPlansFile` + `controller.{outputDirectory,runId}`；")
    A("- route-choice 4 项、`f_cap`、seed 4711、network、threads、travelTimeCalculator、")
    A("  linkStats 间隔、`networkRouteType`、hermes capacity 与 R01 **逐值相同**；")
    A("- 三档 **SCALE 统一 2.29897**，`ΣEF/N_sim` 仅披露（NOT USED）。\n")
    A("冻结件 mtime 快照（**运行前后均须不变**）：\n")
    A("| 文件 | mtime |")
    A("|---|---|")
    for k, v in mt_before.items():
        A(f"| `{Path(k).name}` | {v} |")
    A("")
    A("## 8. 产物与复现\n")
    A("- 入场准备：`scripts/od/prepare_lambda_sensitivity_7_6g.py`")
    A("- 点火器：`scripts/od/run_lambda_sensitivity_7_6g.py`")
    A("- 预注册分析：`scripts/od/evaluate_lambda_sensitivity_7_6g.py`")
    A(f"- 工作区：`matsim_lambda_7_6g/`（`configs/config_L05|L75|L10_rc_min.xml` + "
      "`populations/pop_L05|L75|L10/` + 本预注册 + matrix/provenance/validation/lambda-invariance）")
    A("- 状态：**三档人口与 config 已就位；`outputs/` 与 `logs/` 为空 —— 正式 run 未启动。**\n")
    A("```bash")
    A("python scripts/od/prepare_lambda_sensitivity_7_6g.py            # 生成 + 校验（已完成）")
    A("python scripts/od/run_lambda_sensitivity_7_6g.py --dry-run      # 前置核验")
    A("python scripts/od/run_lambda_sensitivity_7_6g.py --experiments L05 --heap 24g")
    A("python scripts/od/evaluate_lambda_sensitivity_7_6g.py           # 网格未齐时输出 AWAITING_RUNS")
    A("```\n")
    A("**冻结不动**：7.1 / 7.3.6A / OD / network / capacity / population(200k 源) / route-choice 任何冻结件；")
    A(f"**未启动任何 MATSim 仿真；未选 demand scale / 未评价最终 λ**。\n")
    p = NEW_ROOT / "STEP7_6G_PREREGISTRATION.md"
    p.write_text("\n".join(L), encoding="utf-8")
    return p


def write_readme(checks: list[dict]) -> Path:
    L = []
    A = L.append
    A("# Step 7.6G — λ 敏感度 screening（三档 λ × 单一 demand level）\n")
    A("**隔离工作区**：不修改 7.1 / 7.3.6A / OD / network / capacity / 200k 源人口 / route-choice 任何冻结件。\n")
    A("| 项 | 值 |")
    A("|---|---|")
    A(f"| 被扫变量 | λ ∈ {{0.05, 0.075, 0.10}} |")
    A(f"| demand level | f = {F_LAMBDA}（N_sim = {N_SIM:,}） |")
    A(f"| λ 参考 | {LAM_REF} |")
    A(f"| SCALE | {SCALE_CONST:.5f}（全档统一，禁按 ΣEF 重算） |")
    A(f"| f_cap | {F_CAP} |")
    A("| route-choice | R01_rc_min（7.6E 冻结） |")
    A("| 靶场 | 7.3.6A Frozen crosswalk（576 池化） |")
    A("| 主口径 | MATCHED Sim/Obs(08-09) |")
    A("| Primary / Reference | `Q̄_10:19` / `Q_19` |")
    A("")
    A("## 目录")
    A("```text")
    A("matsim_lambda_7_6g/")
    A("├─ README.md                              ← 本文件")
    A("├─ STEP7_6G_PREREGISTRATION.md            ← 预注册（判据/判决空间/阈值依据）")
    A("├─ lambda_sensitivity_7_6g_matrix.csv")
    A("├─ lambda_sensitivity_7_6g_lambda_invariance.csv")
    A("├─ lambda_sensitivity_7_6g_config_provenance.csv")
    A("├─ lambda_sensitivity_7_6g_config_validation.json")
    A("├─ populations/pop_L05|L75|L10/population_lambda_<TAG>.xml.gz")
    A("├─ configs/config_L05|L75|L10_rc_min.xml")
    A("├─ outputs/                               ← run 后产生")
    A("├─ logs/                                  ← run 后产生")
    A("└─ audit/                                 ← 评价后产生")
    A("```\n")
    A("## 状态\n")
    A(f"- 配置/人口校验：**{sum(1 for c in checks if c['pass'])}/{len(checks)} PASS**")
    A("- 正式 run：**未启动**（需用户明确启动指令）")
    A("- 串行执行：本机 63.7 GB RAM，24g/run ⇒ 并行必 OOM；预计 ≈85 min/档，合计 ≈4.3 h\n")
    p = NEW_ROOT / "README.md"
    p.write_text("\n".join(L), encoding="utf-8")
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
    ap.add_argument("--experiments", nargs="*", default=[e for e, _l, _n in SPEC])
    ap.add_argument("--heap", default="24g")
    ap.add_argument("--smoke", type=int, default=0)
    ap.add_argument("--run", action="store_true",
                    help="正式 3 档全量（**需用户明确启动指令**；默认不启动）")
    ap.add_argument("--gen-only", action="store_true")
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()

    for d in (NEW_ROOT, CONFIG_DIR, POP_ROOT, OUT_ROOT, LOG_DIR, AUDIT_DIR):
        d.mkdir(parents=True, exist_ok=True)

    print("=" * 84)
    print("Step 7.6G PREPARE — λ 敏感度 screening（三档 λ × 单一 demand level）")
    print("=" * 84)
    print(f"  被扫变量   : λ ∈ {{0.05, 0.075, 0.10}}")
    print(f"  demand lvl : f = {F_LAMBDA}  ->  N_sim = {N_SIM:,}")
    print(f"  SCALE      : {SCALE_CONST:.5f} ★全档统一（λ 不变性已实测），禁按 ΣEF 重算")
    print(f"  f_cap      : {F_CAP}   route-choice: R01_rc_min   20 it")
    print(f"  靶场       : 7.3.6A Frozen（只读）")
    print(f"  λ 源人口   : {POP_SRC_DIR}")
    print()

    mt_before = snapshot_mtimes(FROZEN_WATCH)
    for k, v in mt_before.items():
        print(f"  [frozen] {Path(k).name}: mtime={v}")

    order = [e for e, _l, _n in SPEC if e in set(args.experiments)]
    targets = {e: n for e, _l, n in SPEC}

    # ---- 阶段 1+2 ---------------------------------------------------------
    print("\n[1/4] 逐档：复制人口 + 生成 config")
    pop_reports: dict[str, dict] = {}
    cfg_paths: dict[str, Path] = {}
    for eid in order:
        lam = lam_of(eid)
        pop_reports[eid] = stage_population(eid, lam, targets[eid], force=args.force)
        c, od, meta = build_config(eid, smoke=args.smoke)
        cfg_paths[eid] = c
        print(f"   [{eid}] cfg -> {c.name}   out -> {meta['out_dir']}")

    # ---- 阶段 3 -----------------------------------------------------------
    print("\n[2/4] 严格验证（零仿真）")
    _ck_rows.clear()
    for eid in order:
        n = targets[eid] if not args.smoke else args.smoke
        validate(cfg_paths[eid], eid, n, smoke=args.smoke)
        print()

    # ---- 阶段 4 -----------------------------------------------------------
    print("[3/4] 产物")
    m = write_matrix(pop_reports)
    inv = write_lambda_invariance()
    prov = write_provenance(cfg_paths)
    pre = write_preregistration(pop_reports, _ck_rows, mt_before)
    rd = write_readme(_ck_rows)
    for p in (m, inv, prov, pre, rd):
        print(f"   -> {p.relative_to(ROOT)}")

    mt_after = snapshot_mtimes(FROZEN_WATCH)
    touched = [k for k in mt_before if mt_before[k] != mt_after.get(k)]
    ok_touch = not touched

    npass = sum(1 for c in _ck_rows if c["pass"])
    payload = {
        "status": "PREPARED" if (npass == len(_ck_rows) and ok_touch) else "FAIL",
        "step": "7.6G",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "swept": "lambda", "lambda_grid": LAMS, "demand_level": F_LAMBDA,
        "n_sim": N_SIM, "scale_used": SCALE_CONST, "scale_rule": "FROZEN_NOT_RECOMPUTED",
        "f_cap": F_CAP, "route_choice": "R01_rc_min", "iterations": TOTAL_ITER,
        "target": "7.3.6A_FROZEN", "primary_metric": "MATCHED_SimObs_08_09",
        "primary_window": "Qbar_10:19", "reference_window": "Q_19",
        "zero_simulation": True, "matsim_rerun": False,
        "parameters_changed": False, "lambda_swept_by_population": True,
        "demand_scale_selected": False, "lambda_selected": False,
        "frozen_artifacts_untouched": ok_touch, "frozen_touched": touched,
        "checks_total": len(_ck_rows), "checks_pass": npass,
        "runs": [{"experiment_id": eid, "lambda": lam_of(eid),
                  "n_agents": targets[eid], "run_id": run_id_of(eid),
                  "config": str(cfg_paths[eid]), "output_dir": str(out_dir_of(eid)),
                  "f_realized": (pop_reports[eid].get("sum_expansion_factor", float("nan"))
                                 / REAL_CAR_OD_TOTAL
                                 if pop_reports[eid].get("sum_expansion_factor")
                                 else float("nan"))}
                 for eid in order],
        "checks": _ck_rows,
    }
    vp = NEW_ROOT / "lambda_sensitivity_7_6g_config_validation.json"
    vp.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")

    print("\n[4/4] 校验汇总")
    print(f"   {npass}/{len(_ck_rows)} PASS   冻结件未变: {ok_touch}")
    for c in _ck_rows:
        if not c["pass"]:
            print(f"   FAIL: {c['check']}  {c['detail']}")
    print(f"   -> {vp.relative_to(ROOT)}")
    print(f"\nPREPARE STATUS: {payload['status']}")

    if args.run:
        print("\n[run] 三档串行点火 —— 请使用 run_lambda_sensitivity_7_6g.py（本脚本不点火）")
    return 0 if payload["status"] == "PREPARED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
