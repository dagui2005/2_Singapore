#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
make_config_6_3.py — 生成 Step 6.3 的 MATSim AM assignment 配置。

为什么以 fullConfig 为基线
--------------------------
MATSim 的参数名在各版本间会变（例如 2026.0 里 controller 的分支参数是
`overwriteFiles` 而**不是**早年的 `overwriteFileSetting`）。凭记忆手写最小 config
很容易踩到"参数不存在"或"取值非法"的坑。

因此本脚本先用官方 `org.matsim.run.CreateFullConfig` dump 出**当前版本**的完整默认
配置（matsim/step6_3/fullConfig_2026_0.xml），再用 ElementTree 逐项覆盖。
这样写出的 config 里每个模块、每个参数都来自 MATSim 自己，必然合法。

Step 6.3 的定位
---------------
* **单次迭代**（firstIteration=lastIteration=0）→ 纯 QSim assignment，不做
  replanning / 打分反馈 / 拥堵迭代。这就是用户要的 "AM peak static assignment /
  QSim baseline"。
* 网络与人口使用**连通性修复后**的产物（由 `prepare_connected_scenario.py` 生成）：
    reports/matsim_network/network_cleaned.xml.gz          （= car 主连通分量）
    reports/matsim_population_6_2b_connected/population_lambda_*.xml.gz
  为什么不用冻结原件：MATSim 的 `NetworkRoutingProvider.checkNetwork()` 会对 car 网络
  调 `NetworkUtils.cleanNetwork()`，只要有任何 link/node 被移除就**直接中止**
  （"Network for mode 'car' has unreachable links and nodes ... Aborting."）。
  因此必须喂入已清洗的主连通分量网络，并把端点落在碎片里的 agent 重吸附到最近
  主分量 link（`prepare_connected_scenario.py` 已按最小位移完成）。
  冻结原件 `reports/matsim_network/network.xml.gz` 与 6_2b population 不改动。
* 输出 `linkStats`（按 24 小时的 volume / traveltime 分箱）作为 q_a^sim、t_a^sim。
"""
from __future__ import annotations

import sys
import xml.etree.ElementTree as ET
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
FULL_CONFIG = PROJECT_ROOT / "matsim" / "step6_3" / "fullConfig_2026_0.xml"
NETWORK = PROJECT_ROOT / "reports" / "matsim_network" / "network_cleaned.xml.gz"
POP_DIR = PROJECT_ROOT / "reports" / "matsim_population_6_2b_connected"
OUT_ROOT = PROJECT_ROOT / "reports" / "matsim_assignment"
CONFIG_DIR = PROJECT_ROOT / "matsim" / "step6_3"

LAMBDAS = ["0p050", "0p075", "0p100"]
THREADS = "8"


def set_param(module: ET.Element, name: str, value: str) -> None:
    """覆盖 module 下同名 <param> 的 value；不存在则新建。"""
    for p in module.findall("param"):
        if p.get("name") == name:
            p.set("value", value)
            return
    ET.SubElement(module, "param", {"name": name, "value": value})


def module(root: ET.Element, name: str) -> ET.Element:
    for m in root.findall("module"):
        if m.get("name") == name:
            return m
    m = ET.SubElement(root, "module", {"name": name})
    return m


def build_one(
    lam: str,
    *,
    pop_dir: Path | None = None,
    out_root: Path | None = None,
    run_prefix: str = "step6_3_lambda_",
    cfg_path: Path | None = None,
) -> Path:
    """生成单个 λ 的 config。

    所有关键路径都可覆盖，使同一脚本既能跑 Step 6.3（连通性修复版 population），
    也能跑 Step 6.3.3B（6.3.3A 出发时刻剖面 population），互不覆盖。
    """
    pop_dir = pop_dir or POP_DIR
    out_root = out_root or OUT_ROOT
    cfg_path = cfg_path or (CONFIG_DIR / f"config_lambda_{lam}.xml")

    tree = ET.parse(FULL_CONFIG)
    root = tree.getroot()

    pop = pop_dir / f"population_lambda_{lam}.xml.gz"
    if not pop.exists():
        raise FileNotFoundError(pop)
    out_dir = out_root / f"lambda_{lam}"

    # --- global ---------------------------------------------------------
    g = module(root, "global")
    set_param(g, "randomSeed", "4711")
    set_param(g, "coordinateSystem", "EPSG:3414")   # SVY21，与 network.xml.gz 一致
    set_param(g, "numberOfThreads", THREADS)

    # --- network / plans -------------------------------------------------
    set_param(module(root, "network"), "inputNetworkFile", str(NETWORK))
    set_param(module(root, "plans"), "inputPlansFile", str(pop))

    # --- controller ------------------------------------------------------
    c = module(root, "controller")
    set_param(c, "outputDirectory", str(out_dir))
    set_param(c, "runId", f"{run_prefix}{lam}")
    set_param(c, "firstIteration", "0")
    set_param(c, "lastIteration", "0")                # 单次 QSim assignment
    set_param(c, "overwriteFiles", "deleteDirectoryIfExists")
    set_param(c, "compressionType", "gzip")           # 便于 Python 直接读
    set_param(c, "writeEventsInterval", "1")
    set_param(c, "writePlansInterval", "1")           # 落盘已计算出的 route
    set_param(c, "writeTripsInterval", "1")
    set_param(c, "createGraphsInterval", "0")
    set_param(c, "cleanItersAtEnd", "keep")
    set_param(c, "mobsim", "qsim")
    set_param(c, "routingAlgorithmType", "SpeedyALT")

    # --- qsim ------------------------------------------------------------
    q = module(root, "qsim")
    set_param(q, "mainMode", "car")
    set_param(q, "numberOfThreads", THREADS)
    set_param(q, "flowCapacityFactor", "1.0")
    set_param(q, "storageCapacityFactor", "1.0")
    # 显式声明，消除 PrepareForSimImpl 的 deprecated 告警（默认行为一致）
    set_param(q, "usePersonIdForMissingVehicleId", "false")
    # startTime / endTime 保留默认值 "undefined"：
    #   -> simStarttimeInterpretation=maxOfStarttimeAndEarliestActivityEnd
    #   即"从最早的活动结束时刻（08:00）开始，跑到所有车辆消失为止"。这正是我们要的。

    # --- routing：关闭随机化（无 monetary distance rate 时 MATSim 本就无随机，
    #     显式写 0 以消除 RandomizingTimeDistanceTravelDisutilityFactory 告警）---
    set_param(module(root, "routing"), "routingRandomness", "0.0")

    # --- linkStats：必须把写出间隔设为 1，否则迭代 0 不写文件 -------------
    ls = module(root, "linkStats")
    set_param(ls, "writeLinkStatsInterval", "1")
    set_param(ls, "averageLinkStatsOverIterations", "1")

    # --- replanning：只保留 ReRoute 且权重 1.0，确保所有无 route 的 leg 都被算出
    r = module(root, "replanning")
    for ps in r.findall("parameterset"):
        r.remove(ps)
    ss = ET.SubElement(r, "parameterset", {"type": "strategysettings"})
    ET.SubElement(ss, "param", {"name": "strategyName", "value": "ReRoute"})
    ET.SubElement(ss, "param", {"name": "weight", "value": "1.0"})

    # --- scoring：为 home / work 两个活动类型补上打分参数 ------------------
    sc = module(root, "scoring")
    sp = sc.find("parameterset[@type='scoringParameters']")
    if sp is None:
        sp = ET.SubElement(sc, "parameterset", {"type": "scoringParameters"})
    for at, typical, mini in [("home", "12:00:00", "08:00:00"),
                              ("work", "09:00:00", "06:00:00")]:
        if any(p.find("param[@name='activityType']") is not None
               and p.find("param[@name='activityType']").get("value") == at
               for p in sp.findall("parameterset[@type='activityParams']")):
            continue
        ps = ET.Element("parameterset", {"type": "activityParams"})
        ET.SubElement(ps, "param", {"name": "activityType", "value": at})
        ET.SubElement(ps, "param", {"name": "typicalDuration", "value": typical})
        ET.SubElement(ps, "param", {"name": "minimalDuration", "value": mini})
        # 插到第一个 modeParams 之前，保持 "先 activity 后 mode" 的可读顺序
        idx = None
        for i, child in enumerate(list(sp)):
            if child.tag == "parameterset" and child.get("type") == "modeParams":
                idx = i
                break
        if idx is None:
            sp.append(ps)
        else:
            sp.insert(idx, ps)

    # 手写序列化：**必须保留 DOCTYPE**。
    # MATSim 的 ConfigReader 依赖 DOCTYPE 的 system-id 判断 config 版本，
    # 缺了它 delegate 为 null -> SAXParseException(NPE)。ElementTree 不会写 DOCTYPE。
    body = ET.tostring(root, encoding="unicode")
    content = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<!DOCTYPE config SYSTEM "http://www.matsim.org/files/dtd/config_v2.dtd">\n'
        + body + "\n"
    )
    cfg_path.write_text(content, encoding="utf-8")
    return cfg_path


def main() -> int:
    if not FULL_CONFIG.exists():
        print(f"ERROR: 缺少 {FULL_CONFIG}，请先运行 CreateFullConfig")
        return 1
    if not NETWORK.exists():
        print(f"ERROR: 缺少 {NETWORK}")
        return 1

    for lam in LAMBDAS:
        p = build_one(lam)
        print(f"[OK] {p}")

    # 小抄：打印我们改动的关键项，便于人工核对
    print("\n=== 关键覆盖项（λ=0p050）===")
    t = ET.parse(CONFIG_DIR / "config_lambda_0p050.xml")
    for mod in ["global", "network", "plans", "controller", "qsim", "linkStats"]:
        m = module(t.getroot(), mod)
        for p in m.findall("param"):
            if p.get("name") in {
                "coordinateSystem", "numberOfThreads", "randomSeed",
                "inputNetworkFile", "inputPlansFile", "outputDirectory", "runId",
                "firstIteration", "lastIteration", "overwriteFiles",
                "compressionType", "writeEventsInterval", "writePlansInterval",
                "mainMode", "flowCapacityFactor", "storageCapacityFactor",
                "writeLinkStatsInterval", "averageLinkStatsOverIterations",
            }:
                print(f"  [{mod}] {p.get('name')} = {p.get('value')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
