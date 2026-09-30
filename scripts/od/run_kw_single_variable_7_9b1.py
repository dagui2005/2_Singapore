#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
run_kw_single_variable_7_9b1.py — Step 7.9B-1：**唯一变量** `qsim.trafficDynamics: queue -> kinematicWaves`

定位
----
7.9A-0（表示尺度）→ 7.9B-0（动力学机制，零仿真只读）→ 7.9C-0（空间结构，零仿真只读）
→ **7.9B-1（本步：真正的单变量动力学实验）**。

本步**只改一个模型参数**：
    qsim.trafficDynamics = queue  ->  kinematicWaves
其余全部逐位继承 `Singapore_OD_MATSim_Final_v1.0`：
    flowCapacityFactor=1.0 / storageCapacityFactor=1.0 / SCALE=2.29897 / lambda=0.075
    f_work=1.180222 / N_sim=236044 / route-choice=R01_rc_min / stuckTime=10
    removeStuckVehicles=false / network / OD / crosswalk / seed / departure = 冻结

★ 与 7.8-VIZ-RUN 同样的版本纪律
--------------------------------
`reports/final_model_7_8/FINAL_MODEL_MANIFEST.json` 登记了 **14 件只读冻结输入**（sha256）。
本脚本：
1. **绝不修改** `matsim_final_7_6h/` 下任何文件；
2. 新配置写 `matsim_kw_7_9b1/configs/`，新输出写 `matsim_kw_7_9b1/outputs/`；
3. diff **分两层**披露：
     · **模型层 = 1 项**（`qsim.trafficDynamics`）—— 本步唯一意图；
     · **输出层 = 3 项**（`outputDirectory` / `runId` / `writeEventsInterval`）—— 落新目录 + 开 events
       （后者是为复现 7.7E 的 07–09 时段/events 级指标，**不进入动力学**）。
   逐项白名单落盘 + `<parameterset>` 全展开比对，任何越界差异 ⇒ FAIL 并中止；
4. 跑前/跑后对 14 件冻结输入做 mtime + sha256 快照比对（read-only 硬证据）；
5. 跑后核对：新 it.19 linkstats 存在、link 数 == 693,575、events 出发 == 236,044、到达 == 出发。

运行
----
    python scripts/od/run_kw_single_variable_7_9b1.py                  # 准备（零仿真）
    python scripts/od/run_kw_single_variable_7_9b1.py --run --heap 24g # 点火（1 跑）
    python scripts/od/run_kw_single_variable_7_9b1.py --verify         # 只复核
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sys
import time
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path

ROOT = Path(r"D:\Luan\2026-05\2_Singapore")
sys.path.insert(0, str(ROOT / "scripts" / "matsim"))

SRC_MANIFEST = ROOT / "reports" / "final_model_7_8" / "FINAL_MODEL_MANIFEST.json"
SRC_CONFIG = ROOT / "matsim_final_7_6h" / "configs" / "config_W01_rc_min.xml"
SRC_OUT_DIR = ROOT / "matsim_final_7_6h" / "outputs" / "W01_rc_min"
SRC_LINKSTATS = SRC_OUT_DIR / "ITERS" / "it.19" / "W01_rc_min.19.linkstats.txt.gz"

NEW_ROOT = ROOT / "matsim_kw_7_9b1"
CONFIG_DIR = NEW_ROOT / "configs"
OUT_ROOT = NEW_ROOT / "outputs"
LOG_DIR = NEW_ROOT / "logs"
AUDIT_DIR = NEW_ROOT / "audit"

RUN_ID = "W01_kw"
OUT_DIR = OUT_ROOT / RUN_ID
NEW_CONFIG = CONFIG_DIR / "config_W01_kw.xml"
NEW_LINKSTATS = OUT_DIR / "ITERS" / "it.19" / f"{RUN_ID}.19.linkstats.txt.gz"

# 冻结真值
EXPECT_SRC_CONFIG_SHA16 = "8f44fb349bff9cf1"
EXPECT_F_WORK = 1.180222
EXPECT_LAMBDA = 0.075
EXPECT_SCALE = 2.29897
EXPECT_F_CAP = 1.00
EXPECT_ITER = 19
EXPECT_N_SIM = 236_044
EXPECT_SIM_OBS = 0.9993347697
EXPECT_N_LINKS = 693_575

# ★ 模型层白名单（唯一意图）
MODEL_WHITELIST = {"qsim.trafficDynamics": "kinematicWaves"}
# 输出层白名单（落新目录 + 开 events；不进入动力学）
OUTPUT_WHITELIST = {
    "controller.outputDirectory": str(OUT_DIR),
    "controller.runId": RUN_ID,
    "controller.writeEventsInterval": str(EXPECT_ITER),
}
ALL_WL_KEYS = set(MODEL_WHITELIST) | set(OUTPUT_WHITELIST)

SHA16_INDEX_FALLBACK = 32  # LINK,ORIG_ID,FROM,TO,LENGTH,FREESPEED,CAPACITY + 8h*3 -> avg

CHECKS: list[dict] = []


def gate(cid: str, name: str, ok: bool, detail: str = "") -> bool:
    CHECKS.append({"check": cid, "name": name, "pass": bool(ok), "detail": detail})
    print(f"  [{'PASS' if ok else 'FAIL'}] {cid} {name}" + (f"  ({detail})" if detail else ""))
    return bool(ok)


def warn(cid: str, name: str, detail: str) -> None:
    CHECKS.append({"check": cid, "name": name, "pass": "WARN", "detail": detail})
    print(f"  [WARN] {cid} {name}  ({detail})")


def sha_full(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def sha16(p: Path) -> str:
    return sha_full(p)[:16]


def stamp(p: Path) -> str:
    return datetime.fromtimestamp(p.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S")


def dump_json(p: Path, obj) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w", encoding="utf-8") as fh:
        json.dump(obj, fh, ensure_ascii=False, indent=2)


# --------------------------------------------------------------------------
def frozen_inputs() -> list[dict]:
    return json.loads(SRC_MANIFEST.read_text(encoding="utf-8"))["evidence_manifest"]


def snapshot_inputs() -> list[dict]:
    out = []
    for it in frozen_inputs():
        p = ROOT / it["path"]
        out.append({
            "path": it["path"],
            "exists": p.exists(),
            "bytes": p.stat().st_size if p.exists() else 0,
            "mtime": stamp(p) if p.exists() else "",
            "sha256_16": sha16(p) if p.exists() else "",
            "sha256_16_at_freeze": it["sha256_16"],
            "mtime_at_freeze": it["mtime"],
        })
    return out


def all_params(path: Path) -> dict[str, str]:
    """展开为 扁平键 -> 值；★必须覆盖 <parameterset>，否则嵌套参数会被 diff 静默漏掉。"""
    r = ET.parse(path).getroot()
    d: dict[str, str] = {}
    for mod in r.findall("module"):
        mn = mod.get("name") or "?"
        for pm in mod.findall("param"):
            d[f"{mn}.{pm.get('name')}"] = pm.get("value") or ""
        for i, ps in enumerate(mod.findall("parameterset")):
            t = ps.get("type") or ps.get("name") or "ps"
            for pm in ps.findall("param"):
                d[f"{mn}[{i}:{t}].{pm.get('name')}"] = pm.get("value") or ""
    return d


def module_param(path: Path, module: str, param: str) -> str | None:
    r = ET.parse(path).getroot()
    for mod in r.findall("module"):
        if mod.get("name") != module:
            continue
        for pm in mod.findall("param"):
            if pm.get("name") == param:
                return pm.get("value")
    return None


def strategy_weights(path: Path) -> dict[str, str]:
    r = ET.parse(path).getroot()
    out: dict[str, str] = {}
    for mod in r.findall("module"):
        if mod.get("name") != "replanning":
            continue
        for ps in mod.findall("parameterset"):
            nm = val = None
            for pm in ps.findall("param"):
                if pm.get("name") == "strategyName":
                    nm = pm.get("value")
                elif pm.get("name") == "weight":
                    val = pm.get("value")
            if nm:
                out[nm] = val or ""
    return out


def module_span(lines: list[str], name: str) -> tuple[int, int]:
    """返回 <module name="name"> 起止行号（0-based，含）。"""
    start = None
    for i, l in enumerate(lines):
        if l.strip() == f'<module name="{name}">':
            start = i
            break
    if start is None:
        raise SystemExit(f"module {name} not found")
    for j in range(start + 1, len(lines)):
        if lines[j].strip() == "</module>":
            return start, j
    raise SystemExit(f"module {name} not closed")


# --------------------------------------------------------------------------
def build_config() -> dict:
    print("\n[1] 由冻结配置派生 7.9B-1 配置（模型层 1 项 + 输出层 3 项）")
    src_sha = sha16(SRC_CONFIG)
    gate("B1.01", "源配置 == 7.8 登记的冻结 sha256_16",
         src_sha == EXPECT_SRC_CONFIG_SHA16, f"{src_sha} vs {EXPECT_SRC_CONFIG_SHA16}")

    txt = SRC_CONFIG.read_text(encoding="utf-8")
    lines = txt.split("\n")
    orig_param_count = len(re.findall(r"<param\b", txt))

    # ---- 定位 qsim 模块行区间，确保改的是 qsim 而非 dsim ----
    qs, qe = module_span(lines, "qsim")
    ds, de = module_span(lines, "dsim")
    td_anchor = '<param name="trafficDynamics" value="queue" />'
    hits = [i for i, l in enumerate(lines) if td_anchor in l]
    gate("B1.02", f"`trafficDynamics=queue` 全文唯一命中（n={len(hits)}）", len(hits) == 1,
         f"line {hits[0]+1}" if len(hits) == 1 else str(hits))
    ok_in_qsim = len(hits) == 1 and qs <= hits[0] <= qe and not (ds <= hits[0] <= de)
    gate("B1.03", f"该命中落在 `qsim` 模块内（qsim L{qs+1}-{qe+1}）而**非** `dsim`（L{ds+1}-{de+1}）",
         ok_in_qsim, f"hit L{hits[0]+1}" if hits else "")
    gate("B1.04", "`dsim.trafficDynamics` 已是 kineticWaves 且**不被本步触碰**（惰性诱饵）",
         module_param(SRC_CONFIG, "dsim", "trafficDynamics") == "kinematicWaves",
         module_param(SRC_CONFIG, "dsim", "trafficDynamics"))
    if not ok_in_qsim:
        return {"ok": False}

    subs = [
        ("model:qsim.trafficDynamics", td_anchor,
         '<param name="trafficDynamics" value="kinematicWaves" />'),
        ("output:outputDirectory",
         'value="D:\\Luan\\2026-05\\2_Singapore\\matsim_final_7_6h\\outputs\\W01_rc_min"',
         f'value="{OUTPUT_WHITELIST["controller.outputDirectory"]}"'),
        ("output:runId", 'value="W01_rc_min"', f'value="{OUTPUT_WHITELIST["controller.runId"]}"'),
        ("output:writeEventsInterval", '<param name="writeEventsInterval" value="0" />',
         f'<param name="writeEventsInterval" value="{OUTPUT_WHITELIST["controller.writeEventsInterval"]}" />'),
    ]
    applied = []
    for si, (name, old, new) in enumerate(subs, start=1):
        n = txt.count(old)
        if not gate(f"B1.05-{si}", f"锚点唯一命中：{name}（n={n}）", n == 1, old[:58]):
            return {"ok": False}
        txt = txt.replace(old, new)
        applied.append({"param": name, "old": old, "new": new})

    gate("B1.06", "param 标签总数不变（无结构性改动）",
         len(re.findall(r"<param\b", txt)) == orig_param_count,
         f"{orig_param_count} -> {len(re.findall(r'<param\\b', txt))}")

    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    NEW_CONFIG.write_text(txt, encoding="utf-8")

    # ---- 语义级 diff（含 parameterset 全展开） ----
    a, b = all_params(SRC_CONFIG), all_params(NEW_CONFIG)
    diff = [{"key": k, "src": a.get(k), "new": b.get(k)}
            for k in sorted(set(a) | set(b)) if a.get(k) != b.get(k)]
    rows = []
    for d in diff:
        layer = ("MODEL" if d["key"] in MODEL_WHITELIST
                 else "OUTPUT" if d["key"] in OUTPUT_WHITELIST else "VIOLATION")
        rows.append({**d, "layer": layer})
    (AUDIT_DIR).mkdir(parents=True, exist_ok=True)
    with open(AUDIT_DIR / "b1_config_diff.csv", "w", newline="", encoding="utf-8-sig") as fh:
        w = csv.DictWriter(fh, fieldnames=["key", "src", "new", "layer"])
        w.writeheader()
        w.writerows(rows)

    viol = [r for r in rows if r["layer"] == "VIOLATION"]
    mdl = [r for r in rows if r["layer"] == "MODEL"]
    out = [r for r in rows if r["layer"] == "OUTPUT"]
    print("     diff 明细：")
    for r in rows:
        print(f"       [{r['layer']:9s}] {r['key']}: {r['src']!r} -> {r['new']!r}")
    gate("B1.07", "★模型层 diff 恰好 1 项且 == qsim.trafficDynamics",
         len(mdl) == 1 and mdl[0]["key"] == "qsim.trafficDynamics"
         and mdl[0]["src"] == "queue" and mdl[0]["new"] == "kinematicWaves",
         f"model={[(r['key'], r['src'], r['new']) for r in mdl]}")
    gate("B1.08", "输出层 diff 恰好 3 项（outputDirectory / runId / writeEventsInterval）",
         len(out) == 3 and {r["key"] for r in out} == set(OUTPUT_WHITELIST),
         f"output={[r['key'] for r in out]}")
    gate("B1.09", "零越界改动（VIOLATION = 0）", not viol,
         f"全展开参数={len(b)} diff={len(diff)} violation={len(viol)}")

    # ---- 继承核对 ----
    sw = strategy_weights(NEW_CONFIG)
    inher = [
        ("B1.10", "controller.mobsim = qsim（生效分支未变）", b.get("controller.mobsim") == "qsim",
         b.get("controller.mobsim")),
        ("B1.11", "qsim.trafficDynamics = kinematicWaves（★唯一模型改动）",
         module_param(NEW_CONFIG, "qsim", "trafficDynamics") == "kinematicWaves",
         module_param(NEW_CONFIG, "qsim", "trafficDynamics")),
        ("B1.12", "dsim.trafficDynamics = kinematicWaves（未变，惰性）",
         module_param(NEW_CONFIG, "dsim", "trafficDynamics") == "kinematicWaves",
         module_param(NEW_CONFIG, "dsim", "trafficDynamics")),
        ("B1.13", "`qsim.inflowCapacitySetting` **未显式覆盖**（⇒ MATSim 默认 INFLOW_FROM_FDIAG）",
         "inflowCapacitySetting" not in txt, "absent"),
        ("B1.14", "qsim.flowCapacityFactor = 1.0 且 storageCapacityFactor = 1.0（f_cap 冻结）",
         b.get("qsim.flowCapacityFactor") in ("1.0", "1.00") and b.get("qsim.storageCapacityFactor") in ("1.0", "1.00"),
         f"{b.get('qsim.flowCapacityFactor')} / {b.get('qsim.storageCapacityFactor')}"),
        ("B1.15", "qsim.stuckTime = 10.0 且 removeStuckVehicles = false",
         b.get("qsim.stuckTime") == "10.0" and b.get("qsim.removeStuckVehicles") == "false",
         f"{b.get('qsim.stuckTime')} / {b.get('qsim.removeStuckVehicles')}"),
        ("B1.16", "qsim.timeStepSize = 00:00:01 / numberOfThreads = 8",
         b.get("qsim.timeStepSize") == "00:00:01" and b.get("qsim.numberOfThreads") == "8",
         f"{b.get('qsim.timeStepSize')} / {b.get('qsim.numberOfThreads')}"),
        ("B1.17", "controller.lastIteration = 19 且 firstIteration = 0",
         b.get("controller.lastIteration") == "19" and b.get("controller.firstIteration") == "0",
         f"{b.get('controller.firstIteration')}..{b.get('controller.lastIteration')}"),
        ("B1.18", "controller.routingAlgorithmType = SpeedyALT", b.get("controller.routingAlgorithmType") == "SpeedyALT",
         b.get("controller.routingAlgorithmType")),
        ("B1.19", "plans.inputPlansFile == 冻结人口 pop_W01（只读引用）",
         "population_lambda_0p075.xml.gz" in (b.get("plans.inputPlansFile") or ""),
         (b.get("plans.inputPlansFile") or "")[-46:]),
        ("B1.20", "network.inputNetworkFile == reports/matsim_network/network_cleaned.xml.gz",
         "network_cleaned.xml.gz" in (b.get("network.inputNetworkFile") or ""),
         (b.get("network.inputNetworkFile") or "")[-34:]),
        ("B1.21", "7.6E：ReRoute 0.15 / ChangeExpBeta 0.85（且仅这两条、权重和 = 1）",
         sw.get("ReRoute") == "0.15" and sw.get("ChangeExpBeta") == "0.85" and len(sw) == 2
         and abs(sum(float(v) for v in sw.values()) - 1.0) < 1e-9, str(sw)),
        ("B1.22", "7.6E：fractionOfIterationsToDisableInnovation = 0.8",
         b.get("replanning.fractionOfIterationsToDisableInnovation") == "0.8",
         b.get("replanning.fractionOfIterationsToDisableInnovation")),
        ("B1.23", "7.6E：learningRate 0.5 / routingRandomness 0.0",
         b.get("scoring.learningRate") == "0.5" and b.get("routing.routingRandomness") == "0.0",
         f"lr={b.get('scoring.learningRate')} rand={b.get('routing.routingRandomness')}"),
        ("B1.24", "R01：maxAgentPlanMemorySize 5 / WorstPlanSelector",
         b.get("replanning.maxAgentPlanMemorySize") == "5"
         and b.get("replanning.planSelectorForRemoval") == "WorstPlanSelector",
         f"{b.get('replanning.maxAgentPlanMemorySize')} / {b.get('replanning.planSelectorForRemoval')}"),
        ("B1.25", "events 总开关 vspExperimental.writingOutputEvents = true",
         b.get("vspExperimental.writingOutputEvents") == "true",
         b.get("vspExperimental.writingOutputEvents")),
        ("B1.26", "输出层：writeEventsInterval = 19（it.0 + it.19 + 根目录）",
         b.get("controller.writeEventsInterval") == "19", b.get("controller.writeEventsInterval")),
        ("B1.27", "输出层：outputDirectory 指向新目录（未指向任何冻结产物）",
         (b.get("controller.outputDirectory") or "").startswith(str(NEW_ROOT)),
         b.get("controller.outputDirectory")),
        ("B1.28", "输出层：dumpDataAtEnd = true / eventsFileFormat = xml",
         b.get("controller.dumpDataAtEnd") == "true" and b.get("controller.eventsFileFormat") == "xml",
         f"{b.get('controller.dumpDataAtEnd')} / {b.get('controller.eventsFileFormat')}"),
        ("B1.29", "★安全性：outputDirectory **不**是 matsim_final_7_6h / matsim_viz_7_8 下任何路径",
         not any(s in (b.get("controller.outputDirectory") or "")
                 for s in ["matsim_final_7_6h", "matsim_viz_7_8"]),
         b.get("controller.outputDirectory")),
    ]
    for cid, nm, ok, det in inher:
        gate(cid, nm, ok, str(det))

    return {"ok": True, "applied": applied, "diff": rows, "n_params": len(b)}


# --------------------------------------------------------------------------
def write_readme(n_params: int) -> None:
    NEW_ROOT.mkdir(parents=True, exist_ok=True)
    txt = f"""# matsim_kw_7_9b1 — Step 7.9B-1：唯一变量 `queue -> kinematicWaves`

> **这是 7.9 结构性修复链的第一刀实验**：在 `f_cap=1.0` 下**只切换交通动力学机制**，
> 其余全部逐位继承 `Singapore_OD_MATSim_Final_v1.0`。⛔ **不是**新标定、⛔ 不回灌 v1.0。
> ⛔ **不与 7.9A-1（sample-consistent capacity）合并**。

## 唯一模型改动（1 项）

| 参数 | v1.0 冻结值 | 本目录值 | 性质 |
|---|---|---|---|
| `qsim.trafficDynamics` | `queue` | **`kinematicWaves`** | ★**模型层（本步唯一意图）** |

`dsim.trafficDynamics` 本来就是 `kinematicWaves`，但 `controller.mobsim=qsim` ⇒ **dsim 惰性**，
本步**未触碰** dsim（它是同名不同 module 的经典诱饵）。

## 输出层改动（3 项，不进入动力学）

| 参数 | v1.0 冻结值 | 本目录值 | 性质 |
|---|---|---|---|
| `controller.outputDirectory` | `...\\matsim_final_7_6h\\outputs\\W01_rc_min` | `...\\matsim_kw_7_9b1\\outputs\\{RUN_ID}` | 输出层 |
| `controller.runId` | `W01_rc_min` | `{RUN_ID}` | 输出层（仅文件名） |
| `controller.writeEventsInterval` | `0` | `{EXPECT_ITER}` | 输出层（复现 7.7E 的 07–09 时段指标） |

其余 {n_params} 个参数（含 `<parameterset>` 全展开）取值逐位相同，见 `audit/b1_config_diff.csv`。

## 继承的 v1.0 条件（冻结）

`flowCapacityFactor=1.0` / `storageCapacityFactor=1.0` / `SCALE={EXPECT_SCALE}` /
`lambda={EXPECT_LAMBDA}` / `f_work={EXPECT_F_WORK}` / `N_sim={EXPECT_N_SIM:,}` /
route-choice `R01_rc_min` / `stuckTime=10` / `removeStuckVehicles=false` /
network / OD / crosswalk / seed / departure = 冻结。
`qsim.inflowCapacitySetting` **未显式覆盖** ⇒ MATSim 默认 **`INFLOW_FROM_FDIAG`**（KW 的入口上限由此生效）。

## 判读纪律（用户冻结口径）

本步必须**分开**判定两件事：
1. **`kinematicWaves` 改变了拥堵传播机制** —— 有仿真结果即可验证；
2. **`kinematicWaves` 让拥堵位置更接近真实结构瓶颈** —— 必须同时得到 **7.9C-0 的 C3/C4 空间证据**支持。

⇒ **成功 ≠ 「比 queue 更堵」**；成功 = 「在稳定性不过关的前提下，不仅产生动力学差异，
而且这种差异具有**可解释的空间结构**」。其余三层解释见 `reports/structural_.../` 与
`audit/` 下的分析产物。

## 纪律

- ⛔ 不改 `matsim_final_7_6h/` 下任何文件（14 件冻结输入跑前后 mtime + sha256 逐位未变）；
- ⛔ 不改 f / λ / SCALE / f_cap / route-choice / 人口 / 路网；
- it.0 的 events 是**未收敛路线**的流量、非最终模型，跑完即删；
- ⛔ 本目录产物**不得**回灌 v1.0（`Sim/Obs` 冻结值仍为 `{EXPECT_SIM_OBS}`）。
"""
    (NEW_ROOT / "README.md").write_text(txt, encoding="utf-8")


# --------------------------------------------------------------------------
def verify(expect_run: bool = False) -> dict:
    print("\n[verify] 冻结只读 + 7.9B-1 自检")
    res: dict = {}

    after = snapshot_inputs()
    with open(AUDIT_DIR / "b1_frozen_inputs_after.csv", "w", newline="", encoding="utf-8-sig") as fh:
        w = csv.DictWriter(fh, fieldnames=list(after[0].keys()))
        w.writeheader()
        w.writerows(after)

    before_f = AUDIT_DIR / "b1_frozen_inputs_before.csv"
    if before_f.exists():
        before = {r["path"]: r for r in csv.DictReader(open(before_f, encoding="utf-8-sig"))}
        changed = [r["path"] for r in after
                   if r["path"] in before
                   and (before[r["path"]]["sha256_16"] != r["sha256_16"]
                        or before[r["path"]]["mtime"] != r["mtime"])]
        gate("B1.31", "14 件冻结输入跑前后 sha256 + mtime 逐位未变", not changed,
             f"变化={len(changed)}" + (f" {changed[:3]}" if changed else ""))
    gate("B1.32", "14 件冻结输入 sha256 == 7.8 登记值（未漂移）",
         all(r["sha256_16"] == r["sha256_16_at_freeze"] for r in after),
         f"{sum(1 for r in after if r['sha256_16'] != r['sha256_16_at_freeze'])} 处不一致")
    gate("B1.33", "冻结 W01 配置未被改写（其 qsim.trafficDynamics 仍 = queue）",
         'name="trafficDynamics" value="queue"' in SRC_CONFIG.read_text(encoding="utf-8"))
    if SRC_OUT_DIR.exists():
        gate("B1.34", "冻结 W01 输出目录存在且未被本次运行新增 events",
             len(list(SRC_OUT_DIR.glob("**/*events*"))) == 0,
             f"{len(list(SRC_OUT_DIR.glob('**/*events*')))} 个 events 文件")

    if not NEW_LINKSTATS.exists():
        if not expect_run:
            res["linkstats"] = "PENDING_RUN"
            print("     （尚未运行：7.9B-1 自检项挂起）")
            return res
        gate("B1.40", "新运行 it.19 linkstats 存在", False, str(NEW_LINKSTATS))
        return res

    gate("B1.40", "新运行 it.19 linkstats 存在", True,
         f"{NEW_LINKSTATS.stat().st_size/1e6:.1f} MB")

    # link 数一致性
    import gzip
    with gzip.open(NEW_LINKSTATS, "rt", encoding="utf-8", errors="replace") as fh:
        rd = csv.reader(fh, delimiter="\t")
        hdr = next(rd, [])
        n = sum(1 for _ in rd)
    gate("B1.41", f"新 it.19 linkstats 链路数 == {EXPECT_N_LINKS:,}（同网络）",
         n == EXPECT_N_LINKS, f"{n:,}")
    res["n_links_new"] = n
    res["linkstats_header_cols"] = len(hdr)

    # events 盘点
    ev_root = OUT_DIR / f"{RUN_ID}.output_events.xml.gz"
    ev_iter = OUT_DIR / "ITERS" / f"it.{EXPECT_ITER}" / f"{RUN_ID}.{EXPECT_ITER}.events.xml.gz"
    ev0 = OUT_DIR / "ITERS" / "it.0" / f"{RUN_ID}.0.events.xml.gz"
    for cid, nm, p in [("B1.42", "根目录 output_events 存在", ev_root),
                       ("B1.43", f"ITERS/it.{EXPECT_ITER} events 存在", ev_iter)]:
        gate(cid, nm, p.exists(),
             f"{p.name} {p.stat().st_size/1e9:.2f} GB" if p.exists() else "缺失")

    if ev_iter.exists():
        cnt = {"departure": 0, "arrival": 0, "entered link": 0}
        t0 = time.time()
        with gzip.open(ev_iter, "rt", encoding="utf-8", errors="replace") as fh:
            for line in fh:
                i = line.find('type="')
                if i < 0:
                    continue
                j = line.find('"', i + 6)
                t = line[i + 6:j]
                if t in cnt:
                    cnt[t] += 1
        res["events"] = {**cnt, "count_seconds": round(time.time() - t0, 1)}
        gate("B1.44", f"events 出发数 == 冻结 N_sim = {EXPECT_N_SIM:,}",
             cnt["departure"] == EXPECT_N_SIM, f"departure={cnt['departure']:,}")
        gate("B1.45", "events 到达数 == 出发数（无滞留）",
             cnt["arrival"] == cnt["departure"], f"arrival={cnt['arrival']:,}")
        gate("B1.46", "events 含车流记录（entered link > 0）", cnt["entered link"] > 0,
             f"entered_link={cnt['entered link']:,}")

    if ev0.exists():
        sz = ev0.stat().st_size
        ev0.unlink()
        gate("B1.47", "删除 it.0 events（未收敛路线，避免误用）", True, f"释放 {sz/1e9:.2f} GB")

    return res


# --------------------------------------------------------------------------
def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--heap", default="24g")
    ap.add_argument("--run", action="store_true", help="点火（需用户明确指令）")
    ap.add_argument("--verify", action="store_true", help="只复核，不重跑")
    args = ap.parse_args()

    for d in (CONFIG_DIR, OUT_ROOT, LOG_DIR, AUDIT_DIR):
        d.mkdir(parents=True, exist_ok=True)

    print("=" * 88)
    print("Step 7.9B-1 — 唯一变量 qsim.trafficDynamics: queue -> kinematicWaves（f_cap=1.0）")
    print("=" * 88)
    print(f"  冻结源配置 : matsim_final_7_6h/configs/config_W01_rc_min.xml")
    print(f"  新配置     : {NEW_CONFIG.relative_to(ROOT)}")
    print(f"  新输出     : {OUT_DIR.relative_to(ROOT)}")
    print(f"  runId      : {RUN_ID}（原名 W01_rc_min，仅文件名变化）")
    print(f"  N_sim      : {EXPECT_N_SIM:,}   f_work={EXPECT_F_WORK}   λ={EXPECT_LAMBDA}   "
          f"SCALE={EXPECT_SCALE}   f_cap={EXPECT_F_CAP}")
    print(f"  模型改动   : qsim.trafficDynamics  queue -> kinematicWaves   （**唯一**）")
    print("=" * 88)

    if not args.verify:
        snap = snapshot_inputs()
        with open(AUDIT_DIR / "b1_frozen_inputs_before.csv", "w", newline="", encoding="utf-8-sig") as fh:
            w = csv.DictWriter(fh, fieldnames=list(snap[0].keys()))
            w.writeheader()
            w.writerows(snap)
        print("\n[0] 冻结输入快照 14 件 -> audit/b1_frozen_inputs_before.csv")
        gate("B1.00", "14 件冻结输入均存在且 sha256 == 7.8 登记值",
             all(r["exists"] and r["sha256_16"] == r["sha256_16_at_freeze"] for r in snap),
             f"{sum(1 for r in snap if r['sha256_16'] != r['sha256_16_at_freeze'])} 处不一致")

        r = build_config()
        if not r.get("ok"):
            print("\n!! 配置派生失败，中止")
            dump_json(AUDIT_DIR / "b1_integrity_checks.json", {"checks": CHECKS})
            return 2
        write_readme(r.get("n_params", 0))
        print("\n[2] 新配置已写出:", NEW_CONFIG.relative_to(ROOT))

    if args.run:
        pre = snapshot_inputs()
        ok = all(x["sha256_16"] == x["sha256_16_at_freeze"] for x in pre)
        gate("B1.48", "点火前冻结输入未漂移", ok)
        if not ok:
            print("\n!! 冻结输入已漂移，拒绝点火")
            return 2
        print(f"\n[RUN] 点火 {NEW_CONFIG.name}（heap {args.heap}）…")
        t0 = time.time()
        import matsim_env  # noqa: E402
        rc = matsim_env.run_java_streaming(
            ["org.matsim.run.RunMatsim", str(NEW_CONFIG)],
            log_path=LOG_DIR / f"{RUN_ID}_run.log", heap=args.heap)
        el = (time.time() - t0) / 60
        print(f"--- exit={rc}  耗时 {el:.2f} min ---")
        gate("B1.49", "RunMatsim 退出码 = 0", rc == 0, f"exit={rc}")
        gate("B1.50", "运行耗时在预期量级（> 30 min）", el > 30, f"{el:.2f} min")
        CHECKS.append({"check": "B1.51", "name": "运行耗时记录", "pass": True, "detail": f"{el:.2f} min"})

    res = verify(expect_run=args.run)

    hard = [c for c in CHECKS if c["pass"] is False]
    if hard:
        verdict = "FAILED"
    elif res.get("linkstats") == "PENDING_RUN":
        verdict = "PREPARED_AWAITING_RUN"
    else:
        verdict = "KW_SINGLE_VARIABLE_RUN_COMPLETE"

    summary = {
        "step": "7.9B-1",
        "title": "唯一变量 qsim.trafficDynamics: queue -> kinematicWaves（f_cap=1.0）",
        "verdict": verdict,
        "n_checks": len(CHECKS),
        "n_pass": sum(1 for c in CHECKS if c["pass"] is True),
        "n_warn": sum(1 for c in CHECKS if c["pass"] == "WARN"),
        "failed": [c["check"] for c in hard],
        "run_id": RUN_ID,
        "new_config": str(NEW_CONFIG.relative_to(ROOT)),
        "new_out_dir": str(OUT_DIR.relative_to(ROOT)),
        "model_whitelist": MODEL_WHITELIST,
        "output_whitelist": OUTPUT_WHITELIST,
        "inherited_frozen": {
            "flowCapacityFactor": EXPECT_F_CAP, "storageCapacityFactor": EXPECT_F_CAP,
            "SCALE": EXPECT_SCALE, "lambda": EXPECT_LAMBDA, "f_work": EXPECT_F_WORK,
            "N_sim": EXPECT_N_SIM, "route_choice": "R01_rc_min",
            "stuckTime": 10, "removeStuckVehicles": False,
            "inflowCapacitySetting": "INFLOW_FROM_FDIAG(default, not overridden)",
        },
        "v1_0_sim_obs_reference": EXPECT_SIM_OBS,
        "frozen_untouched": "audit/b1_frozen_inputs_before.csv / b1_frozen_inputs_after.csv",
        "verify": res,
        "checks": CHECKS,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
    dump_json(AUDIT_DIR / "b1_integrity_checks.json", summary)
    with open(AUDIT_DIR / "b1_checks.csv", "w", newline="", encoding="utf-8-sig") as fh:
        w = csv.DictWriter(fh, fieldnames=["check", "name", "pass", "detail"])
        w.writeheader()
        w.writerows(CHECKS)

    print("\n" + "=" * 88)
    print(f"  verdict : {verdict}")
    print(f"  checks  : {summary['n_pass']}/{len(CHECKS)} PASS"
          + (f"  WARN {summary['n_warn']}" if summary["n_warn"] else "")
          + (f"  失败 {[c['check'] for c in hard]}" if hard else ""))
    print("=" * 88)
    return 0 if not hard else 1


if __name__ == "__main__":
    sys.exit(main())
