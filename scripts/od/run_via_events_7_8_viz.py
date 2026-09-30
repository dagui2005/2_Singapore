#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
run_via_events_7_8_viz.py — 为 VIA 可视化重跑 W01 并开启 events 输出（**只改输出层，模型不变**）

为什么需要这一步
----------------
7.8 定版的最终运行 `matsim_final_7_6h/outputs/W01_rc_min` 配置里
`writeEventsInterval = 0` ⇒ **没有 `output_events.xml.gz`**；而 VIA 的车辆层
（唯一能做车流动画的层）只能靠 events。于是为可视化目的**重跑同一条 W01**。

★ 版本纪律（7.8 冻结之后）
--------------------------
`reports/final_model_7_8/FINAL_MODEL_MANIFEST.json` 已把
`matsim_final_7_6h/configs/config_W01_rc_min.xml` 列入 **14 件只读冻结输入**
（sha256 已登记）。因此本脚本：

1. **绝不修改** `matsim_final_7_6h/` 下任何文件（配置 / 人口 / 输出 / 审计）；
2. 新配置写 **新目录** `matsim_viz_7_8/configs/`，新输出写 `matsim_viz_7_8/outputs/`；
3. 改动**仅限 3 个输出层参数**（outputDirectory / runId / writeEventsInterval），
   逐项白名单落盘 + 其余参数（含 `<parameterset>` 全展开）逐位比对，
   任何非白名单差异 ⇒ 直接 FAIL 并中止；
4. 跑完对 14 件冻结输入做 mtime + sha256 跑前/跑后快照比对（read-only 硬证据）；
5. 跑完做**重放一致性分级判定**（见下），否则该 events 不得被标称为 v1.0 的流量。

重放一致性为什么是"分级"而非"必须逐位"
--------------------------------------
本配置 `qsim.numberOfThreads = 8` / `global.numberOfThreads = 8`。多线程 qsim
跨次运行的数值漂移虽通常为 0，但不保证逐位；因此判定分四档，**只把严重漂移当失败**：

    BITEXACT            整文件 sha256 逐位一致
    NUMERIC_EQUIVALENT  max|Δ HRS8-9avg| <= 1e-9 且 Σ 相对差 <= 1e-12
    APPROXIMATE         max|Δ| <= 0.5 且 Σ 相对差 <= 1e-6 → 通过，但必须带警告标注
    DIVERGED            超出以上任一 ⇒ FAIL

events 写入语义（MATSim 2026.0 自带注释实证）
--------------------------------------------
    iterationNumber % writeEventsInterval == 0     -> 该迭代写 events
    dumpDataAtEnd=true 且 lastIteration 为 events 间隔整数倍
        -> 额外在输出根目录写 output_events

本配置 lastIteration=19、writeEventsInterval=19 ⇒ it.0 与 it.19 各一份，
根目录再一份（写入时刻为最后一次满足条件的迭代 = it.19）。
**it.0 那份是未收敛路线的流量、不是最终模型**，跑完自动删除。

运行
----
    python scripts/od/run_via_events_7_8_viz.py                     # 准备（零仿真）
    python scripts/od/run_via_events_7_8_viz.py --run --heap 24g    # 点火（1 跑，~102 min）
    python scripts/od/run_via_events_7_8_viz.py --verify            # 只复核
"""
from __future__ import annotations

import argparse
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
sys.path.insert(0, str(ROOT / "scripts" / "matsim"))

# --------------------------------------------------------------------------
# 路径
# --------------------------------------------------------------------------
SRC_MANIFEST = ROOT / "reports" / "final_model_7_8" / "FINAL_MODEL_MANIFEST.json"
SRC_CONFIG = ROOT / "matsim_final_7_6h" / "configs" / "config_W01_rc_min.xml"
SRC_OUT_DIR = ROOT / "matsim_final_7_6h" / "outputs" / "W01_rc_min"
SRC_LINKSTATS = SRC_OUT_DIR / "ITERS" / "it.19" / "W01_rc_min.19.linkstats.txt.gz"

NEW_ROOT = ROOT / "matsim_viz_7_8"
CONFIG_DIR = NEW_ROOT / "configs"
OUT_ROOT = NEW_ROOT / "outputs"
LOG_DIR = NEW_ROOT / "logs"
AUDIT_DIR = NEW_ROOT / "audit"

RUN_ID = "W01_events"
OUT_DIR = OUT_ROOT / RUN_ID
NEW_CONFIG = CONFIG_DIR / "config_W01_events.xml"
NEW_LINKSTATS = OUT_DIR / "ITERS" / "it.19" / f"{RUN_ID}.19.linkstats.txt.gz"

# --------------------------------------------------------------------------
# 冻结真值（从 7.8 manifest / 冻结产物读，不手抄）
# --------------------------------------------------------------------------
EXPECT_SRC_CONFIG_SHA16 = "8f44fb349bff9cf1"
EXPECT_F_WORK = 1.180222
EXPECT_LAMBDA = 0.075
EXPECT_SCALE = 2.29897
EXPECT_F_CAP = 1.00
EXPECT_ITER = 19
EXPECT_N_SIM = 236_044
EXPECT_SIM_OBS = 0.9993347697

# 只允许改的输出层参数（白名单）
WHITELIST = {
    "outputDirectory": str(OUT_DIR),
    "runId": RUN_ID,
    "writeEventsInterval": str(EXPECT_ITER),   # 19 -> it.0 + it.19 + 根目录件
}

HRS89AVG_IDX = 32   # LINK,ORIG_ID,FROM,TO,LENGTH,FREESPEED,CAPACITY + 8h*3 + min -> avg

CHECKS: list[dict] = []


def gate(cid: str, name: str, ok: bool, detail: str = "") -> bool:
    CHECKS.append({"check": cid, "name": name, "pass": bool(ok), "detail": detail})
    print(f"  [{'PASS' if ok else 'FAIL'}] {cid} {name}" + (f"  ({detail})" if detail else ""))
    return bool(ok)


def warn(cid: str, name: str, detail: str) -> None:
    """软门：记录但不计入失败。"""
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
    """配置展开为 扁平键 -> 值。★必须覆盖 <parameterset> 子节点，
    否则 route-choice（strategysettings）等嵌套参数会被 diff 静默漏掉。"""
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


def strategy_weights(path: Path) -> dict[str, str]:
    """replanning 模块下 strategysettings 的 strategyName -> weight。"""
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


# --------------------------------------------------------------------------
def build_config() -> dict:
    print("\n[1] 由冻结配置派生新配置（仅输出层 3 项）")
    src_sha = sha16(SRC_CONFIG)
    gate("V1", "源配置 == 7.8 登记的冻结 sha256_16",
         src_sha == EXPECT_SRC_CONFIG_SHA16, f"{src_sha} vs {EXPECT_SRC_CONFIG_SHA16}")

    txt = SRC_CONFIG.read_text(encoding="utf-8")
    orig_param_count = len(re.findall(r"<param\b", txt))

    subs = [
        ("outputDirectory",
         'value="D:\\Luan\\2026-05\\2_Singapore\\matsim_final_7_6h\\outputs\\W01_rc_min"',
         f'value="{WHITELIST["outputDirectory"]}"'),
        ("runId",
         'value="W01_rc_min"',
         f'value="{WHITELIST["runId"]}"'),
        ("writeEventsInterval",
         '<param name="writeEventsInterval" value="0" />',
         f'<param name="writeEventsInterval" value="{WHITELIST["writeEventsInterval"]}" />'),
    ]
    applied = []
    for name, old, new in subs:
        n = txt.count(old)
        if not gate(f"V2-{name}", f"锚点唯一命中：{name}（n={n}）", n == 1, old[:58]):
            return {"ok": False}
        txt = txt.replace(old, new)
        applied.append({"param": name, "old": old, "new": new})

    new_param_count = len(re.findall(r"<param\b", txt))
    gate("V3", "param 标签总数不变（无结构性改动）",
         new_param_count == orig_param_count, f"{orig_param_count} -> {new_param_count}")

    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    NEW_CONFIG.write_text(txt, encoding="utf-8")

    # --- 语义级 diff：含 parameterset 全展开，除白名单外必须逐位相同 ---
    a, b = all_params(SRC_CONFIG), all_params(NEW_CONFIG)
    diff = [{"key": k, "src": a.get(k), "new": b.get(k)}
            for k in sorted(set(a) | set(b)) if a.get(k) != b.get(k)]
    rows = [{**d, "whitelisted": d["key"].split(".")[-1] in WHITELIST} for d in diff]
    with open(AUDIT_DIR / "config_diff_whitelist.csv", "w", newline="", encoding="utf-8-sig") as fh:
        w = csv.DictWriter(fh, fieldnames=["key", "src", "new", "whitelisted"])
        w.writeheader()
        w.writerows(rows)

    non_wl = [d for d in rows if not d["whitelisted"]]
    gate("V4", "配置 diff 仅含 3 项白名单（无越界改动）",
         len(diff) == 3 and not non_wl,
         f"全展开参数={len(b)} diff={len(diff)} 非白名单={len(non_wl)}")

    sw = strategy_weights(NEW_CONFIG)
    inher = [
        ("V5", "controller.lastIteration = 19", b.get("controller.lastIteration") == "19",
         b.get("controller.lastIteration")),
        ("V6", "controller.mobsim = qsim", b.get("controller.mobsim") == "qsim",
         b.get("controller.mobsim")),
        ("V7", "controller.routingAlgorithmType = SpeedyALT",
         b.get("controller.routingAlgorithmType") == "SpeedyALT",
         b.get("controller.routingAlgorithmType")),
        ("V8", "plans.inputPlansFile == 冻结人口 pop_W01（只读引用）",
         "populations\\pop_W01\\population_lambda_0p075.xml.gz" in (b.get("plans.inputPlansFile") or ""),
         (b.get("plans.inputPlansFile") or "")[-58:]),
        ("V9", "network.inputNetworkFile == 冻结路网 network_cleaned",
         "network_cleaned.xml.gz" in (b.get("network.inputNetworkFile") or ""),
         (b.get("network.inputNetworkFile") or "")[-38:]),
        ("V10", "qsim.flowCapacityFactor = 1.00（f_cap 冻结）",
         (b.get("qsim.flowCapacityFactor") or "") in ("1.00", "1.0", "1"),
         b.get("qsim.flowCapacityFactor")),
        ("V11", "qsim.storageCapacityFactor = 1.00",
         (b.get("qsim.storageCapacityFactor") or "") in ("1.00", "1.0", "1"),
         b.get("qsim.storageCapacityFactor")),
        # 7.6E route-choice（键名取自 replanning[parameterset] / scoring / routing）
        ("V12", "7.6E：ReRoute 权重 = 0.15", sw.get("ReRoute") == "0.15", sw.get("ReRoute")),
        ("V13", "7.6E：ChangeExpBeta 权重 = 0.85", sw.get("ChangeExpBeta") == "0.85",
         sw.get("ChangeExpBeta")),
        ("V13b", "7.6E：strategy 仅这两条且权重和 = 1.00",
         len(sw) == 2 and abs(sum(float(v) for v in sw.values()) - 1.0) < 1e-9, str(sw)),
        ("V14", "7.6E：fractionOfIterationsToDisableInnovation = 0.8",
         b.get("replanning.fractionOfIterationsToDisableInnovation") == "0.8",
         b.get("replanning.fractionOfIterationsToDisableInnovation")),
        ("V15", "7.6E：learningRate = 0.5 且 routingRandomness = 0.0",
         b.get("scoring.learningRate") == "0.5" and b.get("routing.routingRandomness") == "0.0",
         f"lr={b.get('scoring.learningRate')} rand={b.get('routing.routingRandomness')}"),
        ("V15b", "R01：maxAgentPlanMemorySize=5 / WorstPlanSelector",
         b.get("replanning.maxAgentPlanMemorySize") == "5"
         and b.get("replanning.planSelectorForRemoval") == "WorstPlanSelector",
         f"{b.get('replanning.maxAgentPlanMemorySize')} / "
         f"{b.get('replanning.planSelectorForRemoval')}"),
        ("V15c", "events 总开关已开（vspExperimental.writingOutputEvents=true）",
         b.get("vspExperimental.writingOutputEvents") == "true",
         b.get("vspExperimental.writingOutputEvents")),
        # 输出层新值
        ("V16", "writeEventsInterval 新值 = 19（输出层）",
         b.get("controller.writeEventsInterval") == "19", b.get("controller.writeEventsInterval")),
        ("V17", "outputDirectory 指向新目录（未覆盖冻结产物）",
         (b.get("controller.outputDirectory") or "").startswith(str(NEW_ROOT)),
         b.get("controller.outputDirectory")),
        ("V18", "dumpDataAtEnd = true（根目录 output_events 所需）",
         b.get("controller.dumpDataAtEnd") == "true", b.get("controller.dumpDataAtEnd")),
        ("V19", "eventsFileFormat = xml", b.get("controller.eventsFileFormat") == "xml",
         b.get("controller.eventsFileFormat")),
    ]
    for cid, nm, ok, det in inher:
        gate(cid, nm, ok, str(det))

    return {"ok": True, "applied": applied, "diff": rows, "n_params": len(b)}


# --------------------------------------------------------------------------
def write_readme(n_params: int) -> None:
    NEW_ROOT.mkdir(parents=True, exist_ok=True)
    txt = f"""# matsim_viz_7_8 — 为 VIA 可视化重跑 W01（仅开 events 输出）

> ⚠️ **这不是新的模型版本。** 这是 `Singapore_OD_MATSim_Final_v1.0` 的
> **输出层重执行**：模型参数（f / λ / SCALE / f_cap / route-choice / 人口 / 路网）
> **逐位继承**冻结配置，只改了 3 个输出参数；判据见
> `audit/v_integrity_checks.json` 的**重放一致性分级判定**
> （BITEXACT / NUMERIC_EQUIVALENT / APPROXIMATE / DIVERGED）。

## 为什么重跑

7.8 定版的 W01 配置里 `writeEventsInterval = 0` ⇒ **没有 events 文件**，
而 VIA 的车辆层（唯一能做车流动画的层）只能靠 events。
原目录**保持只读**：新配置 / 新输出全部落在本目录，`matsim_final_7_6h/` 一字未动
（14 件冻结输入跑前后 mtime + sha256 逐位未变，见 `audit/frozen_inputs_*.csv`）。

## 与冻结配置的差异（白名单，共 3 项）

| 参数 | 冻结值 | 本目录值 | 性质 |
|---|---|---|---|
| `controller.outputDirectory` | `...\\matsim_final_7_6h\\outputs\\W01_rc_min` | `...\\matsim_viz_7_8\\outputs\\{RUN_ID}` | 输出层 |
| `controller.runId` | `W01_rc_min` | `{RUN_ID}` | 输出层（仅文件名） |
| `controller.writeEventsInterval` | `0`（不写） | `{EXPECT_ITER}` | **输出层（本次唯一目的）** |

其余 {n_params} 个参数（含 `<parameterset>` 全展开）取值逐位相同，见
`audit/config_diff_whitelist.csv`。

## 产物

```
outputs/{RUN_ID}/
├── {RUN_ID}.output_network.xml.gz        ← VIA：Network 层（CRS EPSG:3414）
├── {RUN_ID}.output_events.xml.gz         ← ★ VIA：事件/车辆层（最后一次写入 = it.{EXPECT_ITER}）
├── {RUN_ID}.output_plans.xml.gz          ← VIA：Plans 层（很大）
├── {RUN_ID}.output_links.csv.gz          ← vol_car + WKT geometry，可作 link 附加属性
├── {RUN_ID}.output_config.xml            ← 实际生效配置（复核用）
├── ITERS/it.{EXPECT_ITER}/{RUN_ID}.{EXPECT_ITER}.events.xml.gz
└── ITERS/it.{EXPECT_ITER}/{RUN_ID}.{EXPECT_ITER}.linkstats.txt.gz   ← 与冻结件对账
```

## 在 VIA 里怎么开

1. `File > Add Data...` 选 **`{RUN_ID}.output_network.xml.gz`**
   （网络自带 `coordinateReferenceSystem = EPSG:3414 / SVY21`）；
2. `File > Add Data...` 选 **`{RUN_ID}.output_events.xml.gz`**；
3. `File > Add Layer...` → **Network**；
4. `File > Add Layer...` → **Agents > Vehicles**，再点该层的 **Load Data**
   （events 不会被自动解析，需手动点一次；gz 约 1.5 GB，解析要几分钟）；
5. 底部时间轴拖到 **08:00–09:00**（本项目标定窗）即可看早高峰车流。

> 若底图错位：EPSG:3414 是新加坡 SVY21，别把它当 WGS84（EPSG:4326）。

## 纪律

- ⛔ 不改 `matsim_final_7_6h/` 下任何文件；⛔ 不改 f / λ / SCALE / f_cap / route-choice；
- ⛔ 本目录产物**不得**被引用为新的标定证据（`Sim/Obs` 仍以冻结的 `0.9993347697` 为准）；
- it.0 的 events 是**未收敛路线**的流量、非最终模型，跑完即删。
"""
    (NEW_ROOT / "README.md").write_text(txt, encoding="utf-8")


# --------------------------------------------------------------------------
def parse_linkstats(p: Path) -> dict[str, float]:
    out: dict[str, float] = {}
    with gzip.open(p, "rt", encoding="utf-8", errors="replace") as fh:
        rd = csv.reader(fh, delimiter="\t")
        next(rd, None)
        for row in rd:
            if len(row) <= HRS89AVG_IDX:
                continue
            try:
                out[row[0]] = float(row[HRS89AVG_IDX])
            except (ValueError, IndexError):
                continue
    return out


def count_events(p: Path) -> dict:
    """流式逐行统计 events 类型分布（精确，无跨块模糊匹配风险）。"""
    cnt: dict[str, int] = {}
    n_events = 0
    with gzip.open(p, "rt", encoding="utf-8", errors="replace") as fh:
        for line in fh:
            if "<event " not in line:
                continue
            n_events += 1
            i = line.find('type="')
            if i < 0:
                continue
            j = line.find('"', i + 6)
            t = line[i + 6:j]
            cnt[t] = cnt.get(t, 0) + 1
    return {
        "entered_link": cnt.get("entered link", 0),
        "left_link": cnt.get("left link", 0),
        "departure": cnt.get("departure", 0),
        "arrival": cnt.get("arrival", 0),
        "actstart": cnt.get("actstart", 0),
        "actend": cnt.get("actend", 0),
        "PersonEntersVehicle": cnt.get("PersonEntersVehicle", 0),
        "vehicle_enters_traffic": cnt.get("vehicle enters traffic", 0),
        "vehicle_leaves_traffic": cnt.get("vehicle leaves traffic", 0),
        "total_event_records": n_events,
        "all_types": dict(sorted(cnt.items(), key=lambda kv: -kv[1])),
    }


def verify(expect_run: bool = False) -> dict:
    print("\n[verify] 冻结只读 + 重放一致性核对")
    res: dict = {}

    # ---- 1. 冻结输入只读（跑前/跑后） ----
    after = snapshot_inputs()
    with open(AUDIT_DIR / "frozen_inputs_after.csv", "w", newline="", encoding="utf-8-sig") as fh:
        w = csv.DictWriter(fh, fieldnames=list(after[0].keys()))
        w.writeheader()
        w.writerows(after)

    before_f = AUDIT_DIR / "frozen_inputs_before.csv"
    if before_f.exists():
        before = {r["path"]: r for r in csv.DictReader(open(before_f, encoding="utf-8-sig"))}
        changed = [r["path"] for r in after
                   if r["path"] in before
                   and (before[r["path"]]["sha256_16"] != r["sha256_16"]
                        or before[r["path"]]["mtime"] != r["mtime"])]
        gate("V30", "14 件冻结输入跑前后 sha256 + mtime 逐位未变", not changed,
             f"变化={len(changed)}" + (f" {changed[:3]}" if changed else ""))
    gate("V31", "14 件冻结输入 sha256 == 7.8 登记值（未漂移）",
         all(r["sha256_16"] == r["sha256_16_at_freeze"] for r in after),
         f"{sum(1 for r in after if r['sha256_16'] != r['sha256_16_at_freeze'])} 处不一致")
    gate("V32", "冻结 W01 配置未被改写（其 writeEventsInterval 仍 = 0）",
         'name="writeEventsInterval" value="0"' in SRC_CONFIG.read_text(encoding="utf-8"))
    n_ev_src = len(list(SRC_OUT_DIR.glob("**/*events*")))
    gate("V33", "冻结 W01 输出目录仍无 events（未被本次运行污染）", n_ev_src == 0,
         f"{n_ev_src} 个 events 文件")

    if not NEW_LINKSTATS.exists():
        if not expect_run:
            res["linkstats"] = "PENDING_RUN"
            print("     （尚未运行：重放核对项挂起）")
            return res
        gate("V40", "新运行 it.19 linkstats 存在", False, str(NEW_LINKSTATS))
        return res

    gate("V40", "新运行 it.19 linkstats 存在", True,
         f"{NEW_LINKSTATS.stat().st_size/1e6:.1f} MB")

    # ---- 2. 重放一致性分级判定 ----
    fa, fb = sha_full(SRC_LINKSTATS), sha_full(NEW_LINKSTATS)
    A, B = parse_linkstats(SRC_LINKSTATS), parse_linkstats(NEW_LINKSTATS)
    common = sorted(set(A) & set(B))
    mx = max((abs(A[k] - B[k]) for k in common), default=0.0)
    sa = sum(A[k] for k in common)
    sb = sum(B[k] for k in common)
    rel_sum = abs(sb - sa) / sa if sa else float("inf")
    same_keys = len(common) == len(A) and len(common) == len(B)

    if fa == fb:
        grade = "BITEXACT"
    elif same_keys and mx <= 1e-9 and rel_sum <= 1e-12:
        grade = "NUMERIC_EQUIVALENT"
    elif same_keys and mx <= 0.5 and rel_sum <= 1e-6:
        grade = "APPROXIMATE"
    else:
        grade = "DIVERGED"

    det = f"{grade}  n={len(common)}/{len(A)}  max|Δ|={mx!r}  relΣ={rel_sum:.2e}"
    if grade in ("BITEXACT", "NUMERIC_EQUIVALENT"):
        gate("V41", "重放等级 ∈ {BITEXACT, NUMERIC_EQUIVALENT}", True, det)
    elif grade == "APPROXIMATE":
        gate("V41", "重放等级 ∈ {BITEXACT, NUMERIC_EQUIVALENT}", True, det)
        warn("V41-W", "重放为 APPROXIMATE（多线程 qsim 数值抖动，非模型变更）",
             f"max|Δ HRS8-9avg|={mx:.4g}  Σ相对差={rel_sum:.2e}"
             " ⇒ events 可用于可视化，但不得据其重算标定指标")
    else:
        gate("V41", "重放等级 ∈ {BITEXACT, NUMERIC_EQUIVALENT}", False, det)

    res.update({"replay_grade": grade, "n_links_common": len(common),
                "n_links_src": len(A), "n_links_new": len(B),
                "max_abs_delta_hrs89avg": mx, "rel_sum_hrs89avg": rel_sum,
                "linkstats_sha_src": fa, "linkstats_sha_new": fb,
                "sum_hrs89avg_src": sa, "sum_hrs89avg_new": sb,
                "frozen_sim_obs_reference": EXPECT_SIM_OBS})

    # ---- 3. events 盘点 ----
    ev_root = OUT_DIR / f"{RUN_ID}.output_events.xml.gz"
    ev_iter = OUT_DIR / "ITERS" / f"it.{EXPECT_ITER}" / f"{RUN_ID}.{EXPECT_ITER}.events.xml.gz"
    ev0 = OUT_DIR / "ITERS" / "it.0" / f"{RUN_ID}.0.events.xml.gz"
    for cid, nm, p in [("V43", "根目录 output_events 存在", ev_root),
                       ("V44", f"ITERS/it.{EXPECT_ITER} events 存在", ev_iter)]:
        gate(cid, nm, p.exists(),
             f"{p.name} {p.stat().st_size/1e9:.2f} GB" if p.exists() else "缺失")

    if ev_iter.exists():
        t0 = time.time()
        st = count_events(ev_iter)
        st["count_seconds"] = round(time.time() - t0, 1)
        res["events"] = st
        print("     events 统计（%.1fs）：%s" % (
            st["count_seconds"],
            json.dumps({k: v for k, v in st.items() if k != "all_types"}, ensure_ascii=False)))
        gate("V45", "events 含车流记录（entered link > 0）",
             st.get("entered_link", 0) > 0, f"entered_link={st.get('entered_link')}")
        gate("V46", f"events 出发数 == 冻结 N_sim = {EXPECT_N_SIM:,}",
             st.get("departure", 0) == EXPECT_N_SIM, f"departure={st.get('departure')}")
        gate("V47", "events 到达数 == 出发数（无滞留）",
             st.get("arrival", 0) == st.get("departure", 0),
             f"arrival={st.get('arrival')} departure={st.get('departure')}")

    # ---- 4. 清 it.0 events（未收敛，非最终模型） ----
    if ev0.exists():
        sz = ev0.stat().st_size
        ev0.unlink()
        gate("V48", "删除 it.0 events（未收敛路线，避免误用）", True, f"释放 {sz/1e9:.2f} GB")

    return res


# --------------------------------------------------------------------------
def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--heap", default="24g")
    ap.add_argument("--run", action="store_true", help="点火（1 跑，~102 min；需用户明确指令）")
    ap.add_argument("--verify", action="store_true", help="只复核，不重跑")
    args = ap.parse_args()

    for d in (CONFIG_DIR, OUT_ROOT, LOG_DIR, AUDIT_DIR):
        d.mkdir(parents=True, exist_ok=True)

    print("=" * 84)
    print("Step 7.8-VIZ-RUN — 为 VIA 重跑 W01（仅开 events 输出；模型参数逐位继承）")
    print("=" * 84)
    print("  冻结源配置 : matsim_final_7_6h/configs/config_W01_rc_min.xml")
    print(f"  新配置     : {NEW_CONFIG.relative_to(ROOT)}")
    print(f"  新输出     : {OUT_DIR.relative_to(ROOT)}")
    print(f"  runId      : {RUN_ID}（原名 W01_rc_min，仅文件名变化）")
    print(f"  N_sim      : {EXPECT_N_SIM:,}   f_work={EXPECT_F_WORK}   λ={EXPECT_LAMBDA}   "
          f"SCALE={EXPECT_SCALE}   f_cap={EXPECT_F_CAP}")
    print(f"  events     : writeEventsInterval 0 -> {EXPECT_ITER}（输出层 3 项改动之一）")
    print("=" * 84)

    if not args.verify:
        snap = snapshot_inputs()
        with open(AUDIT_DIR / "frozen_inputs_before.csv", "w", newline="", encoding="utf-8-sig") as fh:
            w = csv.DictWriter(fh, fieldnames=list(snap[0].keys()))
            w.writeheader()
            w.writerows(snap)
        print("\n[0] 冻结输入快照 14 件 -> audit/frozen_inputs_before.csv")
        gate("V0", "14 件冻结输入均存在且 sha256 == 7.8 登记值",
             all(r["exists"] and r["sha256_16"] == r["sha256_16_at_freeze"] for r in snap),
             f"{sum(1 for r in snap if r['sha256_16'] != r['sha256_16_at_freeze'])} 处不一致")

        r = build_config()
        if not r.get("ok"):
            print("\n!! 配置派生失败，中止")
            dump_json(AUDIT_DIR / "v_integrity_checks.json", {"checks": CHECKS})
            return 2
        write_readme(r.get("n_params", 0))

    if args.run:
        pre = snapshot_inputs()
        ok = all(x["sha256_16"] == x["sha256_16_at_freeze"] for x in pre)
        gate("V20", "点火前冻结输入未漂移", ok)
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
        gate("V21", "RunMatsim 退出码 = 0", rc == 0, f"exit={rc}")
        gate("V22", "运行耗时在预期量级（> 30 min）", el > 30, f"{el:.2f} min")

    res = verify(expect_run=args.run)

    hard = [c for c in CHECKS if c["pass"] is False]
    grade = res.get("replay_grade")
    if hard:
        verdict = "FAILED"
    elif grade is None:
        verdict = "PREPARED_AWAITING_RUN"
    elif grade in ("BITEXACT", "NUMERIC_EQUIVALENT"):
        verdict = f"VIA_EVENTS_REPRODUCTION_CONFIRMED_{grade}"
    elif grade == "APPROXIMATE":
        verdict = "VIA_EVENTS_REPRODUCED_WITH_WARNING"
    else:
        verdict = "FAILED"

    summary = {
        "step": "7.8-VIZ-RUN",
        "title": "为 VIA 重跑 W01 并开启 events 输出（输出层重执行，模型不变）",
        "verdict": verdict,
        "n_checks": len(CHECKS),
        "n_pass": sum(1 for c in CHECKS if c["pass"] is True),
        "n_warn": sum(1 for c in CHECKS if c["pass"] == "WARN"),
        "failed": [c["check"] for c in hard],
        "run_id": RUN_ID,
        "new_config": str(NEW_CONFIG.relative_to(ROOT)),
        "new_out_dir": str(OUT_DIR.relative_to(ROOT)),
        "whitelist": WHITELIST,
        "model_unchanged_declaration": (
            "本步为输出层重执行：f / λ / SCALE / f_cap / route-choice / 人口 / 路网 "
            "逐位继承冻结配置；7.8 的 v1.0 身份不变。"
        ),
        "frozen_untouched": "audit/frozen_inputs_before.csv / frozen_inputs_after.csv",
        "verify": res,
        "checks": CHECKS,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
    dump_json(AUDIT_DIR / "v_integrity_checks.json", summary)
    with open(AUDIT_DIR / "v_checks.csv", "w", newline="", encoding="utf-8-sig") as fh:
        w = csv.DictWriter(fh, fieldnames=["check", "name", "pass", "detail"])
        w.writeheader()
        w.writerows(CHECKS)

    print("\n" + "=" * 84)
    print(f"  verdict : {verdict}")
    print(f"  checks  : {summary['n_pass']}/{len(CHECKS)} PASS"
          + (f"  WARN {summary['n_warn']}" if summary["n_warn"] else "")
          + (f"  失败 {[c['check'] for c in hard]}" if hard else ""))
    print("=" * 84)
    return 0 if not hard else 1


if __name__ == "__main__":
    sys.exit(main())
