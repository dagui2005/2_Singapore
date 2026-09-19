#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""
prepare_routechoice_7_6d.py — Step 7.6D：Route-choice stabilization（最小配置修复 + 零仿真配置验证）。

背景（7.6B 判决）
-----------------
7.6B 证明 D01-D04 的 MATSim 分配**从未收敛**，而是 **周期-2 极限环（route flip-flop）**：
    标定子集 MATCHED 周期振幅 1.59% / 3.77% / 20.75% / 16.22%（f=1.00/1.10/1.20/1.25）
    全网 ALL   周期振幅 0.39% / 1.34% / 1.13% / 1.40%   ⇒ 放大 14.8×
根因是**配置组合**（4 份 config 全部相同）：
    fractionOfIterationsToDisableInnovation = Infinity   （100% 迭代都在创新，无收尾阶段）
    strategyName                            = ReRoute    （唯一策略，weight 1.0，每代全部重选路）
    planCalcScore.learningRate              = 1.0        （无指数平滑）
    routingRandomness                       = 0.0        （确定性最短路 ⇒ 上代贵、这代全切走）

本步骤做什么（用户裁定：最小修复，只针对「学习过猛 + 持续创新」）
------------------------------------------------------------------
**只改 3 个标量 + 1 个策略集**，其余一切（network / population / OD / capacity / seed /
threads / TTC / crosswalk / 观测靶场）**逐字节不变**：

    replanning.fractionOfIterationsToDisableInnovation   Infinity -> 0.8
    replanning 策略集                                    [ReRoute 1.00] -> [ReRoute 0.15, ChangeExpBeta 0.85]
    scoring.learningRate                                 1.0 -> 0.5
    routing.routingRandomness                            0.0 -> 0.0（保留，显式断言）

为什么保留一个「plan-selection」策略
----------------------------------
`fractionOfIterationsToDisableInnovation = 0.8` 的语义是：**迭代 16 之后禁用创新策略**，
届时只剩「选计划」而不「造新计划」。若策略集里没有 ChangeExpBeta/BestScore，
禁用创新后就没有任何可用的计划选择算子 ⇒ 网络无法沉降。
故加入 `ChangeExpBeta`（weight 0.85，标准 logit 选择器；brainExpBeta=1.0 已在基线）。

为什么只做这一轮、且**不追求 Sim/Obs 变好**
------------------------------------------
本轮唯一目标是**把 assignment 从周期-2 振荡变成可接受的稳定状态**。
若同时调 demand scale / λ / capacity，就无法区分「哪项修改产生了稳定性」。
（这是用户明确要求的单变量纪律。）

隔离原则（用户工程决定）
------------------------
**不修改任何现有 7.1 / 7.3.6A / OD / network / capacity 产物**。
新配置、新输出、新日志、新审计全部落在**独立目录**：
    matsim_routechoice_7_6d/
        README.md
        STEP7_6D_PREREGISTRATION.md
        configs/                新 config（本脚本产物）
        outputs/                MATSim 输出（本步骤运行后产生）
        logs/                   MATSim 运行日志
        audit/                  7.6D 稳定性评价产物
旧结果（reports/od_calibration_7_4_2、7_4_3、7_6b ...）**完全保留**。

用法
----
    python scripts/od/prepare_routechoice_7_6d.py                 # 生成 + 严格验证（零仿真）
    python scripts/od/prepare_routechoice_7_6d.py --smoke 2000    # 冒烟：截断 2000 agents × 3 迭代
    python scripts/od/prepare_routechoice_7_6d.py --run           # 正式 20 迭代全量（需显式指定）
"""
from __future__ import annotations

import argparse
import csv
import gzip
import json
import sys
import time
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(r"D:\Luan\2026-05\2_Singapore")
sys.path.insert(0, str(ROOT / "scripts" / "matsim"))
sys.path.insert(0, str(ROOT / "scripts" / "od"))

import make_config_6_3 as cfgmod      # noqa: E402  build_one（以官方 fullConfig 为基线）
import matsim_env                     # noqa: E402  Java 运行时

# --------------------------------------------------------------------------
# 冻结路径
# --------------------------------------------------------------------------
NEW_ROOT = ROOT / "matsim_routechoice_7_6d"
CONFIG_DIR = NEW_ROOT / "configs"
OUT_ROOT = NEW_ROOT / "outputs"
LOG_DIR = NEW_ROOT / "logs"
AUDIT_DIR = NEW_ROOT / "audit"

POP_DIR = ROOT / "reports" / "matsim_departure_6_3_3a"      # 6.3.3A 冻结出发时刻剖面
POP_FILE = POP_DIR / "population_lambda_0p075.xml.gz"
BASELINE_CFG = ROOT / "matsim" / "step6_3" / "config_E06_lam0p075_cap1p00.xml"   # = D01 基线

LAMBDA_TAG = "0p075"
RUN_ID = "R01_rc_min"
RUN_DIR = OUT_ROOT / RUN_ID
TOTAL_ITER = 20
EXPECTED_ITER = 19

DOCT_TMPL = ('<?xml version="1.0" encoding="UTF-8"?>\n'
             '<!DOCTYPE config SYSTEM "http://www.matsim.org/files/dtd/config_v2.dtd">\n')

# --------------------------------------------------------------------------
# 最小修复规格（唯一允许改动的量）
# --------------------------------------------------------------------------
MIN_PATCH = {
    # (module, param) -> (baseline_value, new_value)
    ("replanning", "fractionOfIterationsToDisableInnovation"): ("Infinity", "0.8"),
    ("scoring", "learningRate"): ("1.0", "0.5"),
    ("routing", "routingRandomness"): ("0.0", "0.0"),          # 保留（显式冻结）
}
STRATEGY_SPEC = [("ReRoute", 0.15), ("ChangeExpBeta", 0.85)]

# 控制器级差异（必然变化，且与「稳定性机制」无关）
CONTROLLER_ALLOWED = {
    "outputDirectory", "runId", "firstIteration", "lastIteration",
    "writeEventsInterval", "writePlansInterval", "writeTripsInterval",
    "writeSnapshotsInterval", "writeLinkStatsInterval",
}

# 必需与基线**逐值相同**的关键项（防止误改模型）
MUST_MATCH_BASELINE = [
    ("network", "inputNetworkFile"),
    ("plans", "inputPlansFile"),
    ("global", "randomSeed"),
    ("global", "coordinateSystem"),
    ("global", "numberOfThreads"),
    ("qsim", "flowCapacityFactor"),
    ("qsim", "storageCapacityFactor"),
    ("qsim", "numberOfThreads"),
    ("controller", "routingAlgorithmType"),
    ("travelTimeCalculator", "travelTimeBinSize"),
    ("travelTimeCalculator", "travelTimeAggregator"),
    ("linkStats", "averageLinkStatsOverIterations"),
    ("linkStats", "writeLinkStatsInterval"),
    ("plans", "networkRouteType"),
    ("hermes", "flowCapacityFactor"),
    ("hermes", "storageCapacityFactor"),
]

ANCHOR_CLASSES = {"RUN_MATCHED": 3037, "RUN_ALL": 693575}

_ck_rows: list[dict] = []


def ck(name: str, ok: bool, detail: str = "") -> bool:
    _ck_rows.append({"check": name, "pass": bool(ok), "detail": str(detail)})
    print(f"   [{'PASS' if ok else 'FAIL'}] {name}  {detail}")
    return bool(ok)


# --------------------------------------------------------------------------
# XML 工具
# --------------------------------------------------------------------------
def module_of(root: ET.Element, name: str) -> ET.Element:
    for m in root.findall("module"):
        if m.get("name") == name:
            return m
    raise KeyError(f"module not found: {name}")


def setp(mod_el: ET.Element, name: str, value: str) -> None:
    for p in mod_el.findall("param"):
        if p.get("name") == name:
            p.set("value", value)
            return
    ET.SubElement(mod_el, "param", {"name": name, "value": value})


def pget(root: ET.Element, mod: str, name: str):
    try:
        m = module_of(root, mod)
    except KeyError:
        return None
    return next((p.get("value") for p in m.findall("param") if p.get("name") == name), None)


def same_value(a, b) -> bool:
    """字符串相等，或**数值相等**。

    基线 E06 由 7.4.2 runner 以 ``f"{f_cap:g}"`` 写回，得到 "1"；
    而 build_one 的默认值是 "1.0"。两者语义完全一致，故 diff 必须数值感知，
    否则会把「格式差异」误报成「模型改动」。
    """
    if str(a) == str(b):
        return True
    try:
        return abs(float(a) - float(b)) < 1e-12
    except (TypeError, ValueError):
        return False


def param_map(cfg: Path) -> dict:
    """{ (module, param) : value } —— 只取 <param>（不含 parameterset 内部）。"""
    root = ET.parse(cfg).getroot()
    out = {}
    for m in root.findall("module"):
        mod = m.get("name")
        for p in m.findall("param"):
            out[(mod, p.get("name"))] = p.get("value")
    return out


def strategy_list(cfg: Path) -> list[tuple[str, str]]:
    root = ET.parse(cfg).getroot()
    r = module_of(root, "replanning")
    out = []
    for ps in r.findall("parameterset"):
        if ps.get("type") != "strategysettings":
            continue
        nm = next((p.get("value") for p in ps.findall("param")
                   if p.get("name") == "strategyName"), None)
        wt = next((p.get("value") for p in ps.findall("param")
                   if p.get("name") == "weight"), None)
        if nm:
            out.append((nm, wt))
    return out


# --------------------------------------------------------------------------
# 生成
# --------------------------------------------------------------------------
def apply_min_patch(cfg_path: Path, *, out_dir: Path, run_id: str, last_iter: int) -> None:
    """在 build_one 产出的基线上施加最小修复（只动白名单内的量）。"""
    tree = ET.parse(cfg_path)
    root = tree.getroot()

    # --- controller：路径 / 迭代数 / 磁盘控制 -----------------------------
    c = module_of(root, "controller")
    setp(c, "outputDirectory", str(out_dir))
    setp(c, "runId", run_id)
    setp(c, "firstIteration", "0")
    setp(c, "lastIteration", str(last_iter))
    for k in ("writeEventsInterval", "writePlansInterval",
              "writeTripsInterval", "writeSnapshotsInterval"):
        setp(c, k, "0")

    # --- ★ 修复 1：innovation 收尾 ----------------------------------------
    r = module_of(root, "replanning")
    setp(r, "fractionOfIterationsToDisableInnovation",
         MIN_PATCH[("replanning", "fractionOfIterationsToDisableInnovation")][1])

    # --- ★ 修复 2：策略集（ReRoute 降权 + 加入 ChangeExpBeta） -------------
    for ps in list(r.findall("parameterset")):
        if ps.get("type") == "strategysettings":
            r.remove(ps)
    for nm, wt in STRATEGY_SPEC:
        ss = ET.SubElement(r, "parameterset", {"type": "strategysettings"})
        ET.SubElement(ss, "param", {"name": "strategyName", "value": nm})
        ET.SubElement(ss, "param", {"name": "weight", "value": f"{wt:g}"})

    # --- ★ 修复 3：学习率（指数平滑） --------------------------------------
    setp(module_of(root, "scoring"), "learningRate",
         MIN_PATCH[("scoring", "learningRate")][1])

    # --- 保留：确定性最短路 ------------------------------------------------
    setp(module_of(root, "routing"), "routingRandomness",
         MIN_PATCH[("routing", "routingRandomness")][1])

    # --- qsim capacity 显式回写为基线值（防 build_one 默认漂移） -----------
    q = module_of(root, "qsim")
    setp(q, "flowCapacityFactor", "1.0")
    setp(q, "storageCapacityFactor", "1.0")

    cfg_path.write_text(DOCT_TMPL + ET.tostring(root, encoding="unicode") + "\n",
                        encoding="utf-8")


def truncate_population(src: Path, dst: Path, n: int) -> int:
    buf, cnt, done = [], 0, False
    with gzip.open(src, "rt", encoding="utf-8") as fh:
        for line in fh:
            if not done:
                buf.append(line)
                if line.strip().startswith("</person>"):
                    cnt += 1
                    if cnt >= n:
                        done = True
    buf.append("</population>\n")
    with gzip.open(dst, "wt", encoding="utf-8") as fh:
        fh.write("".join(buf))
    return cnt


def build(*, smoke: int = 0) -> tuple[Path, Path, dict]:
    """生成 config（smoke>0 时生成冒烟 config + 截断人口）。"""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    OUT_ROOT.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    if not POP_FILE.exists():
        raise FileNotFoundError(POP_FILE)

    if smoke:
        cfg_path = CONFIG_DIR / f"config_{RUN_ID}_smoke.xml"
        out_dir = OUT_ROOT / f"_smoke_{RUN_ID}"
        run_id = f"smoke_{RUN_ID}"
        last_iter = 2
    else:
        cfg_path = CONFIG_DIR / f"config_{RUN_ID}.xml"
        out_dir = RUN_DIR
        run_id = RUN_ID
        last_iter = EXPECTED_ITER

    # 以 build_one 从官方 fullConfig 生成合法基线（保证每个参数名/取值都来自 MATSim 自己）
    cfgmod.build_one(LAMBDA_TAG, pop_dir=POP_DIR, out_root=OUT_ROOT,
                     run_prefix="rc7_6d_", cfg_path=cfg_path)

    apply_min_patch(cfg_path, out_dir=out_dir, run_id=run_id, last_iter=last_iter)

    if smoke:
        pop_dst = CONFIG_DIR / f"_smoke_{RUN_ID}_population.xml.gz"
        got = truncate_population(POP_FILE, pop_dst, smoke)
        print(f"[smoke] 截断人口 {got} persons -> {pop_dst}")
        tree = ET.parse(cfg_path)
        root = tree.getroot()
        setp(module_of(root, "plans"), "inputPlansFile", str(pop_dst.resolve()))
        cfg_path.write_text(DOCT_TMPL + ET.tostring(root, encoding="unicode") + "\n",
                            encoding="utf-8")

    return cfg_path, out_dir, {"run_id": run_id, "out_dir": str(out_dir),
                               "last_iteration": last_iter, "smoke": smoke}


# --------------------------------------------------------------------------
# 严格配置验证（零仿真）
# --------------------------------------------------------------------------
def validate(cfg_path: Path, *, expect_iter: int, smoke: int) -> list[dict]:
    base = param_map(BASELINE_CFG)
    new = param_map(cfg_path)
    bstrat = strategy_list(BASELINE_CFG)
    nstrat = strategy_list(cfg_path)

    print("\n=== 基线策略集 ===")
    print("   ", bstrat)
    print("=== 新配置策略集 ===")
    print("   ", nstrat)

    # --- V1 策略集：ReRoute 降权 + 恰好加入 ChangeExpBeta，权重和 = 1 -------
    ck("V1.1 新策略集 == [ReRoute 0.15, ChangeExpBeta 0.85]",
       [(n, float(w)) for n, w in nstrat] == [(n, w) for n, w in STRATEGY_SPEC],
       str(nstrat))
    ck("V1.2 策略权重和 == 1.0",
       abs(sum(float(w) for _n, w in nstrat) - 1.0) < 1e-12,
       f"sum = {sum(float(w) for _n, w in nstrat):.4f}")
    ck("V1.3 ReRoute 权重由 1.0 降至 0.15",
       dict(nstrat).get("ReRoute") == "0.15"
       and dict(bstrat).get("ReRoute") == "1.0",
       f"{dict(bstrat).get('ReRoute')} -> {dict(nstrat).get('ReRoute')}")
    ck("V1.4 基线无任何 plan-selection 策略（复现 7.6B 根因）",
       "ChangeExpBeta" not in dict(bstrat) and "BestScore" not in dict(bstrat),
       f"baseline = {list(dict(bstrat))}")

    # --- V2 三个标量 -------------------------------------------------------
    for (mod, name), (old, newv) in MIN_PATCH.items():
        got = pget(ET.parse(cfg_path).getroot(), mod, name)
        ck(f"V2 {mod}.{name} == {newv}", got == newv,
           f"baseline={old}  new={got}")

    # --- V3 与基线逐参数 diff（白名单之外必须完全相同） ---------------------
    keys = set(base) | set(new)
    diffs = [(k, base.get(k), new.get(k)) for k in sorted(keys)
             if not same_value(base.get(k), new.get(k))]
    def _is_allowed(k):
        mod, name = k
        if mod == "controller" and name in CONTROLLER_ALLOWED:
            return True
        if (mod, name) in MIN_PATCH:
            return True
        # 冒烟模式会换用截断人口，这是实验脚手架而非模型改动
        if smoke > 0 and k == ("plans", "inputPlansFile"):
            return True
        return False
    unexpected = [d for d in diffs if not _is_allowed(d[0])]
    ck("V3.1 与基线差异仅限白名单（controller 路径/迭代 + 3 个修复标量）",
       not unexpected,
       f"共 {len(diffs)} 处差异，越界 {len(unexpected)}" +
       (f" -> {unexpected}" if unexpected else ""))

    changed_mech = [d for d in diffs
                    if (d[0][0], d[0][1]) in MIN_PATCH]
    print("   -- 白名单内差异明细 --")
    for k, a, b in sorted(diffs):
        print(f"      {k[0]}.{k[1]}: {a} -> {b}")

    # --- V4 模型必须逐值不变 ----------------------------------------------
    bad = []
    for mod, name in MUST_MATCH_BASELINE:
        if smoke > 0 and (mod, name) == ("plans", "inputPlansFile"):
            continue        # 冒烟模式刻意换用截断人口
        bv, nv = base.get((mod, name)), new.get((mod, name))
        if not same_value(bv, nv):
            bad.append((mod, name, bv, nv))
    ck(f"V4 模型关键项与基线逐值相同（{len(MUST_MATCH_BASELINE)} 项）",
       not bad, "全部一致" if not bad else str(bad))

    # --- V5 显式冻结断言 ---------------------------------------------------
    rt = ET.parse(cfg_path).getroot()
    ck("V5.1 routingRandomness == 0.0（确定性最短路保留）",
       pget(rt, "routing", "routingRandomness") == "0.0",
       pget(rt, "routing", "routingRandomness"))
    ck("V5.2 randomSeed == 4711",
       pget(rt, "global", "randomSeed") == "4711",
       pget(rt, "global", "randomSeed"))
    ck("V5.3 flowCapacityFactor == storageCapacityFactor == 1.0",
       pget(rt, "qsim", "flowCapacityFactor") == "1.0"
       and pget(rt, "qsim", "storageCapacityFactor") == "1.0",
       f"{pget(rt, 'qsim', 'flowCapacityFactor')} / {pget(rt, 'qsim', 'storageCapacityFactor')}")
    ck("V5.4 lastIteration == %d" % expect_iter,
       pget(rt, "controller", "lastIteration") == str(expect_iter),
       pget(rt, "controller", "lastIteration"))
    ck("V5.5 inputNetworkFile 与基线相同（network 未换）",
       pget(rt, "network", "inputNetworkFile") == base.get(("network", "inputNetworkFile")),
       pget(rt, "network", "inputNetworkFile"))
    ck("V5.6 population 指向 6.3.3A 冻结剖面（smoke 除外）",
       (smoke > 0) or (pget(rt, "plans", "inputPlansFile") == str(POP_FILE)),
       pget(rt, "plans", "inputPlansFile"))
    ck("V5.7 中间迭代不写 events/plans/trips/snapshots",
       all(pget(rt, "controller", k) == "0" for k in
           ("writeEventsInterval", "writePlansInterval",
            "writeTripsInterval", "writeSnapshotsInterval")),
       "all 0")
    ck("V5.8 writeLinkStatsInterval == 1（每迭代 linkstats 是唯一测量需求）",
       pget(rt, "linkStats", "writeLinkStatsInterval") == "1",
       pget(rt, "linkStats", "writeLinkStatsInterval"))
    ck("V5.9 DOCTYPE 存在（MATSim ConfigReader 依赖 system-id 判版本）",
       cfg_path.read_text(encoding="utf-8").startswith('<?xml version="1.0"')
       and "config_v2.dtd" in cfg_path.read_text(encoding="utf-8")[:300],
       "ok")

    # --- V6 可加载性（MATSim 解析器试读） ----------------------------------
    try:
        nmod = len(ET.parse(cfg_path).getroot().findall("module"))
        ck("V6.1 XML 可解析且模块数 >= 25", nmod >= 25, f"modules = {nmod}")
    except Exception as e:                                  # pragma: no cover
        ck("V6.1 XML 可解析", False, repr(e))

    return _ck_rows


# --------------------------------------------------------------------------
# 产物
# --------------------------------------------------------------------------
def write_provenance(cfg_path: Path, out_csv: Path) -> None:
    base = param_map(BASELINE_CFG)
    new = param_map(cfg_path)
    keys = sorted(set(base) | set(new))
    rows = []
    for k in keys:
        bv, nv = base.get(k), new.get(k)
        rows.append({
            "module": k[0], "param": k[1],
            "baseline_value": bv, "new_value": nv,
            "changed": not same_value(bv, nv),
            "is_target_patch": (k[0], k[1]) in MIN_PATCH,
        })
    with out_csv.open("w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["module", "param", "baseline_value",
                                           "new_value", "changed", "is_target_patch"])
        w.writeheader()
        w.writerows(rows)

    # 策略集单列
    srows = []
    for src, label in ((BASELINE_CFG, "baseline"), (cfg_path, "new")):
        for nm, wt in strategy_list(src):
            srows.append({"source": label, "strategyName": nm, "weight": wt})
    sdir = out_csv.parent / "routechoice_7_6d_strategy_provenance.csv"
    with sdir.open("w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["source", "strategyName", "weight"])
        w.writeheader()
        w.writerows(srows)


def write_readme(cfg_path: Path, meta: dict, checks: list[dict]) -> None:
    npass = sum(1 for c in checks if c["pass"])
    txt = f"""# matsim_routechoice_7_6d — Step 7.6D Route-choice Stabilization

> 本目录是 **Step 7.6D 的隔离工作区**。依据用户 2026-09-16 裁定建立：
> **不修改任何现有 7.1 / 7.3.6A / OD / network / capacity 产物**；旧结果
> （`reports/od_calibration_7_4_2`、`7_4_3`、`7_4_3r`、`7_6a`、`7_6b` 等）**完全保留**。

## 为什么需要这一步

7.6B（`reports/od_calibration_7_6b/STEP7_6B_REPORT.md`）证明 D01-D04 的分配**从未收敛**，
而是 **周期-2 极限环（route flip-flop）**：

| 口径 | D01 (f=1.00) | D02 (1.10) | D03 (1.20) | D04 (1.25) |
|---|---:|---:|---:|---:|
| MATCHED 周期振幅 | 1.59% | 3.77% | **20.75%** | **16.22%** |
| ALL 周期振幅 | 0.39% | 1.34% | 1.13% | 1.40% |
| 放大倍数 | 4.0x | 2.8x | 18.3x | 11.6x |

根因是**配置组合**（D01-D04 四份 config 完全一致）：

| 参数 | 基线值 | 后果 |
|---|---|---|
| `replanning.fractionOfIterationsToDisableInnovation` | `Infinity` | 100% 迭代都在创新，无收尾沉降阶段 |
| `replanning` 策略集 | `[ReRoute 1.00]` | 每个 agent 每一代全部重新选路 |
| `scoring.learningRate` | `1.0` | 计划得分无指数平滑 |
| `routing.routingRandomness` | `0.0` | 确定性最短路 ⇒ 上代贵、这代全切走 |

## 最小修复（唯一变量）

**只改 3 个标量 + 1 个策略集**，针对「学习过猛 + 持续创新」两个机制：

| 参数 | 基线 | 修复后 |
|---|---|---|
| `replanning.fractionOfIterationsToDisableInnovation` | `Infinity` | **`0.8`** |
| `replanning` 策略集 | `[ReRoute 1.00]` | **`[ReRoute 0.15, ChangeExpBeta 0.85]`** |
| `scoring.learningRate` | `1.0` | **`0.5`** |
| `routing.routingRandomness` | `0.0` | `0.0`（保留） |

其余一切（network / population / OD / capacity / seed / threads / travelTimeCalculator /
crosswalk / 观测靶场）**逐参数不变**，见 `routechoice_7_6d_config_provenance.csv`。

**为什么加 `ChangeExpBeta`**：`fractionOfIterationsToDisableInnovation = 0.8` 意味着
**迭代 16 之后禁用创新策略**；若策略集里没有 plan-selection 算子，禁用创新后网络无法沉降。

**本轮唯一目标**：把 assignment 从周期-2 振荡变成可接受稳定状态。
**不做**：调 demand scale / λ / capacity；**不追求** Sim/Obs 变好（单变量纪律）。

## 目录

| 路径 | 内容 |
|---|---|
| `configs/config_{RUN_ID}.xml` | 修复后的正式 config（20 迭代） |
| `configs/config_{RUN_ID}_smoke.xml` | 冒烟 config（截断人口 × 3 迭代） |
| `routechoice_7_6d_config_provenance.csv` | 与基线逐参数 diff（唯一权威差异表） |
| `routechoice_7_6d_strategy_provenance.csv` | 策略集前后对照 |
| `routechoice_7_6d_config_validation.json` | 配置验证结果（机器可读） |
| `STEP7_6D_PREREGISTRATION.md` | 预注册稳定性判据（先于运行冻结） |
| `outputs/` | MATSim 输出（正式 run 尚未启动） |
| `logs/` | MATSim 运行日志 |
| `audit/` | 7.6D 稳定性评价产物 |

## 配置验证

**{npass}/{len(checks)} PASS**（零仿真，见 `routechoice_7_6d_config_validation.json`）。

## 运行

```
python scripts/od/prepare_routechoice_7_6d.py --smoke 2000   # 冒烟（配置可运行性预检）
python scripts/od/prepare_routechoice_7_6d.py --run          # 正式 20 迭代
python scripts/od/audit_routechoice_stability_7_6d.py        # 稳定性评价（零仿真）
```

run_id = `{RUN_ID}`；population = {POP_FILE.name}；λ = 0.075；f_cap = 1.00；seed = 4711。
"""
    (NEW_ROOT / "README.md").write_text(txt, encoding="utf-8")


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


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--smoke", type=int, default=0, help="截断 n agents 跑 3 迭代")
    ap.add_argument("--run", action="store_true", help="正式 20 迭代全量")
    ap.add_argument("--heap", default="24g")
    ap.add_argument("--gen-only", action="store_true", help="只生成（默认行为）")
    args = ap.parse_args()

    NEW_ROOT.mkdir(parents=True, exist_ok=True)
    print("=== MATSim 运行时 ===")
    for k, v in matsim_env.describe().items():
        print(f"  {k}: {v}")
    print(f"  population : {POP_FILE}")
    print(f"  new root   : {NEW_ROOT}")
    print(f"  run_id     : {RUN_ID}")
    print()

    smoke = args.smoke
    cfg_path, out_dir, meta = build(smoke=smoke)
    print(f"[build] {cfg_path}")
    print(f"[build] output -> {out_dir}  lastIteration={meta['last_iteration']}")

    checks = validate(cfg_path, expect_iter=meta["last_iteration"], smoke=smoke)

    prov_csv = NEW_ROOT / "routechoice_7_6d_config_provenance.csv"
    write_provenance(cfg_path, prov_csv)
    write_readme(cfg_path, meta, checks)

    npass = sum(1 for c in checks if c["pass"])
    summary = {
        "step": "7.6D",
        "title": "Route-choice stabilization — minimal config patch",
        "status": "PASS" if npass == len(checks) else "FAIL",
        "checks_pass": npass, "checks_total": len(checks),
        "checks": checks,
        "run_id": RUN_ID,
        "config": str(cfg_path),
        "smoke": smoke,
        "last_iteration": meta["last_iteration"],
        "output_dir": str(out_dir),
        "baseline_config": str(BASELINE_CFG),
        "min_patch": {f"{m}.{p}": {"baseline": a, "new": b}
                      for (m, p), (a, b) in MIN_PATCH.items()},
        "strategy_spec": [{"name": n, "weight": w} for n, w in STRATEGY_SPEC],
        "matsim_rerun": False,
        "zero_simulation": True,
        "parameters_changed_in_model": False,
        "isolation": {"new_root": str(NEW_ROOT),
                      "existing_reports_untouched": True},
    }
    js = NEW_ROOT / "routechoice_7_6d_config_validation.json"
    js.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"\n配置验证: {npass}/{len(checks)} PASS")
    print(f"provenance -> {prov_csv}")
    print(f"validation -> {js}")

    if smoke:
        rc = run_matsim(cfg_path, f"smoke_{RUN_ID}.log", args.heap)
        it_dir = Path(out_dir) / "ITERS"
        stats = sorted(it_dir.glob(f"it.*/{meta['run_id']}.*.linkstats.txt.gz")) \
            if it_dir.exists() else []
        print(f"[smoke] 每迭代 linkstats 共 {len(stats)} 份（期望 3）")
        print("SMOKE STATUS:", "PASS" if rc == 0 and len(stats) >= 3 else "FAIL")
        return rc

    if args.run:
        rc = run_matsim(cfg_path, f"{RUN_ID}_run.log", args.heap)
        it_dir = RUN_DIR / "ITERS"
        stats = sorted(it_dir.glob(f"it.*/{RUN_ID}.*.linkstats.txt.gz")) if it_dir.exists() else []
        print(f"[run] 每迭代 linkstats 共 {len(stats)} 份（期望 {TOTAL_ITER}）")
        print("RUN STATUS:", "PASS" if rc == 0 and len(stats) >= TOTAL_ITER else "FAIL")
        return rc

    print("\n（仅生成 + 验证；未启动 MATSim。用 --smoke N 或 --run 启动。）")
    return 0 if npass == len(checks) else 1


if __name__ == "__main__":
    raise SystemExit(main())
