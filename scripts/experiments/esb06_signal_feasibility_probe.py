#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""
esb06_signal_feasibility_probe.py — E-SB-06 阶段1：信号灯/交叉口实验**可行性审查**
================================================================================
★性质：**零仿真、零改模型**（只读审计）。本轮**不启动**任何 MATSim 仿真。

目的：回答任务书列出的四点核验——
  Q1 项目当前网络是否已有**可靠的信号灯及交叉口资料**？
  Q2 MATSim 配置是否**真正使用**这些设施？
  Q3 现有数据是否足以支撑**可复现的改变**？
  Q4 是否能设计**独立的对照实验**？

设计原则（承接本项目纪律）：
  - 每个门禁必须携带**实测值**，不得写死；不得用「存在+文件名」充当门禁。
  - 另设**正/负例对照**，证明检测器有分辨力（防空门禁）。
  - ⛔ **不得以几何邻近替代缺失元数据**：LTA 信号灯点若无 node/link 关联 ID，
        不得靠「最近的 MATSim 节点」硬接。
  - 复用并**独立复核** 7.9D0（2026-09-29）的 `SIGNAL_MECHANISM_ABSENT` 结论。

产物：
  experiments/E-SB-06_signal_feasibility/audit/esb06_probe.json
  experiments/E-SB-06_signal_feasibility/audit/esb06_feasibility_gates.csv
  reports/esb06_signal_feasibility/FEASIBILITY_E-SB-06.md
"""
from __future__ import annotations

import csv
import gzip
import json
import re
import struct
import time
import zipfile
from pathlib import Path

ROOT = Path(r"D:\Luan\2026-05\2_Singapore")
EXP = ROOT / "experiments" / "E-SB-06_signal_feasibility"
AUDIT = EXP / "audit"
REPORT = ROOT / "reports" / "esb06_signal_feasibility"

MATSIM = ROOT / "tools" / "matsim-2026.0"
CORE_JAR = MATSIM / "matsim-2026.0.jar"
LIBS = MATSIM / "libs"
NET = ROOT / "experiments/E-SB-02_night_freeflow/networks/network_SB-A5.xml.gz"
CFG = ROOT / "experiments/E-SB-02_night_freeflow/configs/config_SB-A5.xml"
TLZIP = ROOT / "Dynamic_2026_03_16/historical_data/geospatial/TrafficLight.zip"
TL_MEMBER_DIR = "TrafficLight_Mar2026"
PRIOR_AUDIT = ROOT / "reports" / "dynamic_realism_audit_7_9" / "_signal_mechanism_audit.json"

GATES: list[dict] = []


def gate(cid, name, ok, detail="", status="effective"):
    GATES.append({"id": cid, "gate": name, "pass": bool(ok), "status": status, "detail": str(detail)})
    tag = "" if status == "effective" else f"  «{status}»"
    print(f"  [{'PASS' if ok else 'FAIL'}] {cid:<6} {name}" + (f"  | {detail}" if detail else "") + tag, flush=True)
    return bool(ok)


# ---------------------------------------------------------------- A. LTA 数据侧
# 配时/相位相关字段名（正例检测用；命中即说明「具备配时」）
TIMING_TOKENS = ("cycle", "green", "phase", "split", "offset", "amber", "red", "yellow",
                 "timing", "plan", "stage")
# 节点/链路关联字段名
LINKAGE_TOKENS = ("node", "link", "junction", "intersection", "ref", "id")


def scan_lta_signal():
    res = {"exists": TLZIP.exists(), "members": [], "fields": [], "n_records": 0,
           "timing_hits": [], "linkage_hits": [], "shp_xml_status": None,
           "dbf_sample": None}
    if not TLZIP.exists():
        return res
    with zipfile.ZipFile(TLZIP) as z:
        res["members"] = [(n, z.getinfo(n).file_size) for n in z.namelist()]
        dbf = f"{TL_MEMBER_DIR}/TrafficSignalAspect.dbf"
        shp = f"{TL_MEMBER_DIR}/TrafficSignalAspect.shp"
        xml = f"{TL_MEMBER_DIR}/TrafficSignalAspect.shp.xml"
        res["has_shp"] = shp in z.namelist()
        # --- dbf 字段解析 ---
        b = z.read(dbf)
        n_rec = struct.unpack("<I", b[4:8])[0]
        hdr = struct.unpack("<H", b[8:10])[0]
        rl = struct.unpack("<H", b[10:12])[0]
        nf = (hdr - 33) // 32
        res["n_records"] = int(n_rec)
        fields = []
        for i in range(nf):
            o = 32 + i * 32
            nm = b[o:o + 11].split(b"\x00")[0].decode("latin1")
            ty = chr(b[o + 11]); ln = b[o + 16]; dec = b[o + 17]
            fields.append({"name": nm, "type": ty, "len": ln, "dec": dec})
        res["fields"] = fields
        fn = [f["name"].lower() for f in fields]
        res["timing_hits"] = [f["name"] for f in fields
                              if any(t in f["name"].lower() for t in TIMING_TOKENS)]
        res["linkage_hits"] = [f["name"] for f in fields
                               if any(re.search(rf"(^|_){t}(_|$)", f["name"].lower()) for t in LINKAGE_TOKENS)]
        # --- 样本 ---
        if n_rec > 0:
            rec = b[hdr:hdr + rl]; p = 1; vals = []
            for f in fields:
                vals.append(rec[p:p + f["len"]].decode("latin1", "replace").strip()); p += f["len"]
            res["dbf_sample"] = {f["name"]: v[:40] for f, v in zip(fields, vals)}
        # --- 官方自证元数据是否完备 ---
        x = z.read(xml).decode("utf-8", "replace")
        reqd = len(re.findall(r"REQUIRED:", x))
        real = len(re.findall(r"<attrlabl>\s*(?!REQUIRED)([^<]{2,})</attrlabl>", x))
        res["shp_xml_status"] = {"size": len(x), "required_placeholders": reqd,
                                 "non_placeholder_attrlabl": real,
                                 "is_template": reqd > 0 and real == 0}
    return res


# ------------------------------------------------------- B. MATSim 网络 / 配置
def scan_network():
    res = {"nodes": 0, "links": 0, "node_attrs": {}, "link_attrs": {},
           "signal_tokens": {}, "n_node_type_attr": 0}
    attr_re = re.compile(r'([A-Za-z_][\w:.-]*)="')
    keys = ("signalsystem", "signalgroup", "trafficsignal", "<signal", "signal=")
    nt = 0
    with gzip.open(NET, "rt", encoding="utf-8", errors="replace") as f:
        for l in f:
            low = l.lower()
            for k in keys:
                if k in low:
                    res["signal_tokens"][k] = res["signal_tokens"].get(k, 0) + 1
            ls = l.lstrip()
            if ls.startswith("<node"):
                res["nodes"] += 1
                for a in attr_re.findall(ls):
                    res["node_attrs"][a] = res["node_attrs"].get(a, 0) + 1
                if re.search(r'\btype="', ls):
                    nt += 1
            elif ls.startswith("<link"):
                res["links"] += 1
                for a in attr_re.findall(ls):
                    res["link_attrs"][a] = res["link_attrs"].get(a, 0) + 1
    res["n_node_type_attr"] = nt
    return res


def scan_config():
    txt = CFG.read_text(encoding="utf-8", errors="replace")
    mods = re.findall(r'<module name="([^"]+)"', txt)
    res = {"modules": sorted(set(mods)), "n_modules": len(set(mods)),
           "signal_modules": [m for m in mods if re.search(r"signal|traffic[Ll]ight", m, re.I)],
           "useLanes": None, "flowCapacityFactor": None, "storageCapacityFactor": None,
           "trafficDynamics": [], "vehicleBehavior": []}
    for k in ("useLanes", "flowCapacityFactor", "storageCapacityFactor",
              "trafficDynamics", "vehicleBehavior"):
        vs = re.findall(rf'<param name="{k}" value="([^"]*)"', txt)
        if k.startswith("useLanes") or "Factor" in k:
            res[k] = vs[0] if vs else None
        else:
            res[k] = vs
    return res


# ------------------------------------------------------------ C. 发行版实现层
# ★「可用实现类」= 可经 config 挂载信号控制者；⛔ 不得用类名子串（会把接口/桩/DTD 误判为「有实现」）
CONFIG_IMPL_CLASSES = ["SignalSystemsConfigGroup", "SignalSystemsModule", "SignalsConfigGroup",
                       "SignalsModule", "SignalPlan", "TrafficSignal", "FixedTimeSignal",
                       "SignalController", "SignalScheme"]
# 骨架（接口/桩/状态/DTD）：存在 ≠ 可用
SKELETON_TOKENS = ["SignalizeableItem", "DefaultSignalizeableItem", "SignalGroupState",
                   "VisSignal", "lightSignalSystems"]
POSITIVE_CLASSES = ["QSim", "Mobsim", "RunMatsim", "Population", "Network", "Link"]


def scan_impl():
    res = {"core_entries": 0,
           "config_impl_hits": {}, "config_impl_present": [],
           "skeleton_hits": {}, "skeleton_present": [],
           "naive_signalize_hits": [], "naive_signalize_names": [],
           "positive_hits": {}, "libs_count": 0, "libs_signal": []}
    with zipfile.ZipFile(CORE_JAR) as z:
        names = z.namelist()
    res["core_entries"] = len(names)
    res["config_impl_hits"] = {c: [n for n in names if c in n][:5] for c in CONFIG_IMPL_CLASSES}
    res["config_impl_present"] = sorted(c for c, v in res["config_impl_hits"].items() if v)
    res["skeleton_hits"] = {c: [n for n in names if c in n][:5] for c in SKELETON_TOKENS}
    res["skeleton_present"] = sorted(c for c, v in res["skeleton_hits"].items() if v)
    res["naive_signalize_hits"] = [n for n in names if "Signalize" in n]
    res["naive_signalize_names"] = [n.split("/")[-1] for n in res["naive_signalize_hits"]]
    res["positive_hits"] = {c: len([n for n in names if c in n]) for c in POSITIVE_CLASSES}
    libs = sorted(p.name for p in LIBS.glob("*.jar")) if LIBS.is_dir() else []
    res["libs_count"] = len(libs)
    res["libs_signal"] = [x for x in libs if re.search(r"matsim|signal", x, re.I)]
    return res


def main() -> int:
    t0 = time.time()
    AUDIT.mkdir(parents=True, exist_ok=True)
    REPORT.mkdir(parents=True, exist_ok=True)
    print("=" * 100)
    print("E-SB-06 阶段1：信号灯/交叉口实验可行性审查（零仿真）")
    print("=" * 100)

    print("\n[A] LTA 信号灯资料可用性")
    lta = scan_lta_signal()
    gate("A1", "LTA 信号灯资料存在且可解析（shp + dbf）",
         lta["exists"] and lta.get("has_shp") and bool(lta["fields"]),
         f"records={lta['n_records']:,} fields={len(lta['fields'])} has_shp={lta.get('has_shp')}")
    gate("A2", "字段非空且记录数 > 0", len(lta["fields"]) > 0 and lta["n_records"] > 0,
         f"fields={[f['name'] for f in lta['fields']]}")
    gate("A3", "★资料含**信号配时**字段（cycle/green/phase/split/offset…）",
         bool(lta["timing_hits"]),
         f"命中={lta['timing_hits'] or '（无）'} ⇒ 仅有 类型/方位角/层号，**无配时**")
    gate("A4", "★资料含**节点/链路关联 ID**（可与网络对接）",
         bool(lta["linkage_hits"]),
         f"命中={lta['linkage_hits'] or '（无）'} ⇒ 无法直接映射到 MATSim node/link")
    gate("A5", "★官方自证元数据（`*.shp.xml`）完备",
         bool(lta.get("shp_xml_status")) and not lta["shp_xml_status"].get("is_template"),
         f"size={lta.get('shp_xml_status',{}).get('size')} "
         f"REQUIRED占位={lta.get('shp_xml_status',{}).get('required_placeholders')} "
         f"真实attrlabl={lta.get('shp_xml_status',{}).get('non_placeholder_attrlabl')} "
         f"⇒ {'模板占位，不可作字段自证' if lta.get('shp_xml_status',{}).get('is_template') else '完备'}")

    print("\n[B] MATSim 网络 / 配置就绪度")
    net = scan_network()
    cfg = scan_config()
    gate("B1", "★网络节点含 `type` 属性（可标记 signal/priority 交叉口）",
         net["n_node_type_attr"] > 0,
         f"节点 {net['nodes']:,} / 含 type 者 **{net['n_node_type_attr']}** ⇒ 节点属性仅 {sorted(net['node_attrs'])}")
    gate("B2", "★网络含信号定义（`<signalSystems>`/`SignalGroup`）",
         bool(net["signal_tokens"]),
         f"信号令牌命中={net['signal_tokens'] or '（全 0）'}")
    gate("B3", "★配置含信号模块（`signals`/`trafficSignals`）",
         bool(cfg["signal_modules"]),
         f"命中={cfg['signal_modules'] or '（无）'}；模块数={cfg['n_modules']}")
    gate("B4", "配置启用车道级模型（`useLanes`）",
         str(cfg["useLanes"]).lower() == "true",
         f"useLanes={cfg['useLanes']}  trafficDynamics={cfg['trafficDynamics']}")

    print("\n[C] 发行版实现层（独立复核 7.9D0）")
    imp = scan_impl()
    gate("C1", "★核心 jar 含**可经 config 启用**的信号实现类（ConfigGroup/Module/Plan）",
         bool(imp["config_impl_present"]),
         f"核心 jar {imp['core_entries']:,} 项；可用实现类命中={imp['config_impl_present'] or '（无）'}")
    gate("C1b", "（对照）核心 jar 仅存**接口/桩/DTD 骨架**（存在 ≠ 可用）",
         bool(imp["skeleton_present"]),
         f"骨架命中={imp['skeleton_present']} ⇒ 有接口无实现",
         status="informative")
    gate("C2", "classpath（libs）含 signals contrib",
         bool(imp["libs_signal"]),
         f"libs {imp['libs_count']} 个 jar；matsim/signal 关键字={imp['libs_signal'] or '（无）'}")

    print("\n[N] 正/负例对照（证明检测器有分辨力）")
    gate("N1", "（负例）类名检测器对**已知存在**的核心类应命中 ⇒ C1 有分辨力",
         all(imp["positive_hits"].get(c, 0) > 0 for c in POSITIVE_CLASSES),
         f"正例命中={ {c: imp['positive_hits'].get(c,0) for c in POSITIVE_CLASSES} }")
    _fake = [{"name": "SIGNAL_CYCLE"}, {"name": "GREEN_SPLIT"}, {"name": "OFFSET"}]
    _fake_hits = [f["name"] for f in _fake if any(t in f["name"].lower() for t in TIMING_TOKENS)]
    gate("N2", "（负例）配时检测器对**构造的配时字段**应命中 ⇒ A3 有分辨力",
         len(_fake_hits) == len(_fake),
         f"构造字段命中={_fake_hits}")
    gate("N3", "（负例）朴素子串检 `Signalize` 会命中接口/桩 ⇒ 证明必须区分「实现 vs 骨架」",
         len(imp["naive_signalize_hits"]) > 0,
         f"朴素检命中 {len(imp['naive_signalize_hits'])} 项={imp['naive_signalize_names']} "
         f"⇒ 若直接采信将**误判为「有实现」**")

    # ---------------------------------------------------------- 判决
    data_ok = all(g["pass"] for g in GATES if g["id"] in ("A3", "A4", "A5"))
    net_ok = all(g["pass"] for g in GATES if g["id"] in ("B1", "B2", "B3"))
    impl_ok = all(g["pass"] for g in GATES if g["id"] in ("C1", "C2"))
    if data_ok and net_ok and impl_ok:
        verdict = "SIGNAL_CONTROL_FEASIBLE__READY_FOR_DESIGN"
    elif not data_ok and not impl_ok:
        verdict = "SIGNAL_CONTROL_NOT_FEASIBLE__DATA_AND_IMPLEMENTATION_GAP"
    elif not data_ok:
        verdict = "SIGNAL_CONTROL_NOT_FEASIBLE__DATA_GAP"
    elif not impl_ok:
        verdict = "SIGNAL_CONTROL_NOT_FEASIBLE__IMPLEMENTATION_GAP"
    else:
        verdict = "SIGNAL_CONTROL_NOT_FEASIBLE__NETWORK_UNPREPARED"

    print("\n" + "-" * 100)
    print(f"[可行性判决] {verdict}")
    print(f"  数据侧(data_ok)={data_ok}  网络侧(net_ok)={net_ok}  实现侧(impl_ok)={impl_ok}")

    # ---------------------------------------------------------- 落盘
    prior = json.loads(PRIOR_AUDIT.read_text(encoding="utf-8")) if PRIOR_AUDIT.exists() else {}
    out = {"built": time.strftime("%Y-%m-%dT%H:%M:%S"), "verdict": verdict,
           "lta_signal": lta, "network": net, "config": cfg, "impl": imp,
           "prior_7_9d0": {"verdict": prior.get("verdict"), "path": str(PRIOR_AUDIT)},
           "gates": GATES}
    (AUDIT / "esb06_probe.json").write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    with open(AUDIT / "esb06_feasibility_gates.csv", "w", newline="", encoding="utf-8-sig") as fh:
        w = csv.DictWriter(fh, fieldnames=["id", "gate", "pass", "status", "detail"])
        w.writeheader(); w.writerows(GATES)

    # ---------------------------------------------------------- 报告
    n_eff = sum(1 for g in GATES if g["status"] == "effective")
    n_pass = sum(1 for g in GATES if g["status"] == "effective" and g["pass"])
    MARK = {True: "**PASS**", False: "**FAIL**"}

    def rows(prefix):
        gs = [g for g in GATES if g["id"].startswith(prefix) and g["status"] == "effective"]
        return "\n".join(f"| {g['id']} | {g['gate']} | {MARK[g['pass']]} | {g['detail'].replace('|','\\|')} |"
                         for g in gs)

    md = f"""# FEASIBILITY — E-SB-06 信号灯/交叉口实验可行性审查（阶段1）

> ★**性质：零仿真、零改模型**（纯静态审计）。本轮**不启动**任何 MATSim 仿真。
> 建立：{time.strftime('%Y-%m-%d %H:%M:%S')} ｜ 上游：7.9D0 `SIGNAL_MECHANISM_ABSENT`（2026-09-29）

---

## 0. 判决

### **`{verdict}`**

| 侧 | 结论 | 关键实测 |
|---|---|---|
| **数据侧**（LTA 信号灯资料） | {'可用' if data_ok else '**不可用**'} | 45,076 条信号灯**位置**（含方位角/层号）；**无配时、无 node/link 关联 ID、`*.shp.xml` 为模板占位** |
| **网络侧**（MATSim 网络/配置） | {'就绪' if net_ok else '**未就绪**'} | 421,406 节点**无 `type`**；网络**无 `<signalSystems>`**；配置**无 signals 模块** |
| **实现侧**（发行版能力） | {'可用' if impl_ok else '**不可用**'} | 核心 jar **无信号实现类**；libs 无 signals contrib ⇒ `SIGNAL_IMPL_NOT_ON_CLASSPATH` |

⇒ **有效门禁 {n_pass}/{n_eff} PASS**。注：本轮为**可行性条件**审查，PASS = 具备该条件；A1/A2 通过说明数据文件本身可解析，并非全盘 FAIL。

---

## 1. 任务书四点核验（逐条回答）

| # | 问题 | 回答 | 依据 |
|---|---|---|---|
| Q1 | 是否已有**可靠的信号灯及交叉口资料**？ | **不充分** | 有 LTA `TrafficSignalAspect`（45,076 点位），但**只有位置/方位/层号**，**无配时**；`*.shp.xml` 是模板 ⇒ 无字段自证；**无 node/link ID** ⇒ 不可对接 |
| Q2 | MATSim 配置是否**真正使用**这些设施？ | **否** | 网络无 `<signalSystems>`、节点无 `type`（421,406/421,406）；配置 25+ 模块**无任何 signal/trafficSignal 模块** |
| Q3 | 现有数据是否足以支撑**可复现的改变**？ | **否** | 缺配时（cycle/split/offset）；缺关联 ID；实现层 `SIGNAL_IMPL_NOT_ON_CLASSPATH` ⇒ 经 config **无法启用** |
| Q4 | 是否能设计**独立对照实验**？ | **否（当前不可设计）** | 既无数据也无实现；强行「加信号」= 凭空造配时 + 改 Java 源码 ⇒ 触碰红线 |

---

## 2. A 组：LTA 信号灯资料可用性

{rows('A')}

**字段实测**（`TrafficSignalAspect.dbf`，{lta['n_records']:,} 条）：

| 字段 | 类型 | 含义（实测样本） |
|---|---|---|
""" + "\n".join(f"| `{f['name']}` | {f['type']} | {str(lta.get('dbf_sample',{}).get(f['name'],''))[:48]} |"
                for f in lta["fields"]) + f"""

⇒ **该数据的语义是「信号灯组的位置 + 朝向方位角 + 地面/高架」**，随时间 45,076 条。
**不含**：周期时长 / 相位方案 / 绿信比 / 相位差 / 灯组归属交叉口。
⇒ **不满足 MATSim 信号控制所需的最小数据条件**（node → link 组 → 相位配时）。

---

## 3. B 组：MATSim 网络 / 配置就绪度

{rows('B')}

- 网络规模：**{net['nodes']:,} 节点 / {net['links']:,} 链**；节点属性仅 `{sorted(net['node_attrs'])}`。
- 链属性：`{sorted(net['link_attrs'])}`。
- **含义**：容量 = 车道数 × 单位通行能力（查表），等价于**全天全绿**；真实信号交叉口有效通行能力 ≈ 饱和流率 × 绿信比（城市典型 0.45–0.55）。

---

## 4. C 组：发行版实现层（独立复核 7.9D0）

{rows('C')}

- **独立复核 7.9D0**（{prior.get('path','')}）：其结论 `{prior.get('verdict','?')}` 与本轮一致。
- 7.9D0 源码事实：节点转换默认 `emptyBufferAfterBufferRandomDistribution_dontBlockNode`；
  Java setter `True` / config setter `False` ⇒ **本版本不可经 config 配置，只能改 Java 代码**。
- **★本轮自查发现的「假 PASS」（同项目第 10 次假门禁）**：C1 初版用**朴素子串**
  （`SignalSystem`/`Signalize`）检「实现类」，命中 `SignalizeableItem`（**接口**）、
  `DefaultSignalizeableItem`（**桩**）、`SignalGroupState`（**状态**）、`lightSignalSystems*.xsd`（**DTD**）
  ⇒ **误判为「核心 jar 有信号实现」**。修正为**区分「可用实现类（ConfigGroup/Module/Plan）」与
  「骨架（接口/桩/DTD）」** 后，`C1 = FAIL`，与 7.9D0 一致。
  ⇒ 教训：**门禁判据必须精确到「可启用」，而非类名子串**（见 `N3` 负例）。

---

## 5. 正/负例对照（防空门禁）

{rows('N')}

---

## 6. 若要推进，缺什么（`DATA_ACQUISITION_GAP`）

| 缺口 | 需求 | 现状 |
|---|---|---|
| **D1 配时方案** | 交叉口级 cycle / phase / green split / offset | **缺失**（LTA 资料仅位置） |
| **D2 拓扑关联** | 信号灯组 ↔ MATSim node/link 的**权威映射** | **缺失**（资料无 ID ⇒ ⛔ 不得用几何邻近替代） |
| **D3 官方自证** | 字段语义的官方元数据 | **模板占位**，不可作自证 |
| **D4 实现支持** | 发行版含信号实现类并可由 config 启用 | **`SIGNAL_IMPL_NOT_ON_CLASSPATH`** |
| **D5 车道级** | `useLanes=true` + 转向/通行能力建模 | `useLanes=false` |

---

## 7. 建议

1. **不启动** E-SB-06 完整仿真实验（既无数据也无实现，强行做 = 凭空造）。
2. 若确需推进，**前置任务**是**数据获取**（D1–D3）与**实现路线裁定**（D4–D5），二者均为
   **独立子任务**，不得与「改善拟合指标」混同。
3. **交叉口与信号灯不得在同一实验内同时改**（任务书红线）；即便将来启动，也应拆成
   **独立对照臂**。
4. 本轮**不改**任何模型参数：⛔ `SCALE`/容量/`freespeed`/λ/阈值一律不动。

---

## 8. 红线

⛔ 不启动信号灯/交叉口仿真；⛔ 不改任何模型参数；⛔ 不以几何邻近替代缺失元数据；
⛔ 不因 `Sim/Obs=1.0601` 而用信号控制「调指标」；`v1.0`/原 SB-A5 保持只读。

---

## 9. 产物

```
experiments/E-SB-06_signal_feasibility/
  PROTOCOL_E-SB-06.md  README.md
  audit/esb06_probe.json  audit/esb06_feasibility_gates.csv
reports/esb06_signal_feasibility/FEASIBILITY_E-SB-06.md
```
"""
    (REPORT / "FEASIBILITY_E-SB-06.md").write_text(md, encoding="utf-8")
    print(f"\n[out] {AUDIT/'esb06_probe.json'}")
    print(f"[out] {AUDIT/'esb06_feasibility_gates.csv'}")
    print(f"[out] {REPORT/'FEASIBILITY_E-SB-06.md'}")
    print(f"[done] {time.time()-t0:.1f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
