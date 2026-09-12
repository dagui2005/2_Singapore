#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
prepare_connected_scenario.py — Step 6.3 前置：把"可路由网络 + 人口"准备好。

背景（为什么需要这一步）
------------------------
MATSim 的 `NetworkRoutingProvider.checkNetwork()` 会对 car 模式网络调用
`NetworkUtils.cleanNetwork()`，**一旦有 link/node 被移除就直接抛异常中止**：
    "Network for mode 'car' has unreachable links and nodes ... Aborting."

我们冻结的 OSM 有向路网里天然存在一些小碎片（service road / 支路没有接回主干），
实测：
    706,554 有向边 -> 最大 car 强连通分量 693,575 边（移除 1.84%）
    429,032 节点   -> 保留 421,406 节点（移除 1.78%）
    332 个 Subzone 锚点节点 **全部保留**（0 个受影响）

如果直接 `networkRouteConsistencyCheck=disable`，那些端点落在碎片里的 agent
将无路可走导致路由失败。因此本脚本做两件**最小且可辩护**的事：

1. 用 MATSim 官方 `org.matsim.run.NetworkCleaner` 产出
   `reports/matsim_network/network_cleaned.xml.gz`（= car 主连通分量）。
   原 `network.xml.gz` **保持冻结不动**，仅新增一个派生的路由网络。

2. 对 3 套 λ 的 population 做**连通性修复**：把 home/work link 不在主分量里的
   agent 重吸附到最近的主分量 link（KD-tree 最近邻）。
   实测位移极小：中位 21.2 m、p90 52.8 m、p95 83.7 m、最大 518 m；
   受影响 agent 5,066 / 200,000 = 2.53%。
   被修复的 agent 在 XML 里新增 `homeRepairM` / `workRepairM` 属性（单位 m，未修复=0），
   便于事后追溯。

产物
----
    reports/matsim_network/network_cleaned.xml.gz
    reports/matsim_network/connectivity_repair.json
    reports/matsim_population_6_2b_connected/population_lambda_*.xml.gz
    reports/matsim_population_6_2b_connected/agent_spatial_assignment_lambda_*.csv
"""
from __future__ import annotations

import gzip
import json
import shutil
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import matsim_env  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
NET_DIR = ROOT / "reports" / "matsim_network"
POP_IN = ROOT / "reports" / "matsim_population_6_2b"
POP_OUT = ROOT / "reports" / "matsim_population_6_2b_connected"
LAMBDAS = ["0p050", "0p075", "0p100"]
DECL = '<?xml version="1.0" encoding="utf-8"?>\n'
DOCTYPE_POP = ('<!DOCTYPE population SYSTEM '
               '"http://www.matsim.org/files/dtd/population_v6.dtd">\n')


# ------------------------------------------------------------------ helpers --
def read_network(path: Path):
    """返回 {link_id: (from_node, to_node)} 与 {node_id: (x, y)}。"""
    with gzip.open(path, "rb") as f:
        root = ET.parse(f).getroot()
    links = {l.get("id"): (l.get("from"), l.get("to")) for l in root.find("links")}
    nodes = {n.get("id"): (float(n.get("x")), float(n.get("y")))
             for n in root.find("nodes")}
    return links, nodes


def link_mid(link_id, links, nodes):
    a, b = links[link_id]
    return ((nodes[a][0] + nodes[b][0]) / 2.0, (nodes[a][1] + nodes[b][1]) / 2.0)


def run_network_cleaner(src: Path, dst: Path) -> int:
    print(f"[clean] {src.name} -> {dst.name}")
    return matsim_env.run_java_streaming(
        ["org.matsim.run.NetworkCleaner", str(src), str(dst)],
        log_path=ROOT / "matsim" / "step6_3" / "logs" / "network_cleaner.log",
        heap="10g",
    )


# ------------------------------------------------------------------- repair --
def repair_population(lam: str, cleaned_links: dict, cleaned_nodes: dict,
                      orig_links: dict, orig_nodes: dict) -> dict:
    """流式改写 population：把不在主分量里的 home/work link 重吸附到最近的主分量 link。"""
    from scipy.spatial import cKDTree

    src = POP_IN / f"population_lambda_{lam}.xml.gz"
    dst = POP_OUT / f"population_lambda_{lam}.xml.gz"
    POP_OUT.mkdir(parents=True, exist_ok=True)

    # 主分量 link 的中点 KD-tree
    cids = [k for k, v in cleaned_links.items()
            if v[0] in cleaned_nodes and v[1] in cleaned_nodes]
    cmid = np.array([link_mid(k, cleaned_links, cleaned_nodes) for k in cids])
    tree = cKDTree(cmid)
    cset = set(cleaned_links)
    # link -> from_node
    cfrom = {k: cleaned_links[k][0] for k in cleaned_links}

    cache: dict[str, tuple[str, float]] = {}

    def snap(link_id: str):
        if link_id in cset:
            return link_id, 0.0
        if link_id in cache:
            return cache[link_id]
        if link_id not in orig_links:            # 理论上不会发生
            cache[link_id] = (link_id, 0.0)
            return cache[link_id]
        p = link_mid(link_id, orig_links, orig_nodes)
        d, i = tree.query(np.array(p))
        res = (cids[i], float(d))
        cache[link_id] = res
        return res

    n_person = n_home_fix = n_work_fix = 0
    repair_d = []
    rows = []

    with gzip.open(src, "rb") as fin, gzip.open(dst, "wt", encoding="utf-8",
                                                compresslevel=6) as fout:
        fout.write(DECL + DOCTYPE_POP)
        fout.write('<population desc="Singapore Step 6.2B spatially realized car '
                   'population (connectivity-repaired)">\n')

        ctx = ET.iterparse(fin, events=("end",))
        for _, el in ctx:
            if el.tag != "person":
                continue
            n_person += 1
            attrs = el.find("attributes")
            av = {}
            for a in attrs:
                av[a.get("name")] = (a.get("class"), (a.text or ""))

            plan = el.find("plan")
            acts = plan.findall("activity")
            home_act = next(a for a in acts if a.get("type") == "home")
            work_act = next(a for a in acts if a.get("type") == "work")

            new_home, dh = snap(home_act.get("link"))
            new_work, dw = snap(work_act.get("link"))
            if dh > 0:
                n_home_fix += 1
            if dw > 0:
                n_work_fix += 1
            if dh > 0 or dw > 0:
                repair_d.extend([dh, dw])
                home_act.set("link", new_home)
                work_act.set("link", new_work)
                if dh > 0:
                    av["homeNode"] = ("java.lang.Integer", cfrom[new_home])
                if dw > 0:
                    av["workNode"] = ("java.lang.Integer", cfrom[new_work])

            # 新增/覆盖修复距离属性
            for k, v in (("homeRepairM", dh), ("workRepairM", dw)):
                av[k] = ("java.lang.Double", repr(float(v)))

            # 重建 attributes（保持既有顺序，修复属性追加在后）
            order = ["originZone", "destinationZone", "homeNode", "workNode",
                     "expansionFactor", "odTrips", "homeSource", "workSource"]
            for a in list(attrs):
                attrs.remove(a)
            for k in order:
                if k in av:
                    cls, txt = av[k]
                    e = ET.SubElement(attrs, "attribute", {"name": k, "class": cls})
                    e.text = txt
            for k in ("homeRepairM", "workRepairM"):
                cls, txt = av[k]
                e = ET.SubElement(attrs, "attribute", {"name": k, "class": cls})
                e.text = txt

            ET.indent(el, space="  ")
            fout.write(ET.tostring(el, encoding="unicode"))
            fout.write("\n")
            el.clear()

        fout.write("</population>\n")

    # 同步 CSV
    csv_src = POP_IN / f"agent_spatial_assignment_lambda_{lam}.csv"
    df = pd.read_csv(csv_src, encoding="utf-8-sig")
    df["home_link_orig"] = df.home_link
    df["work_link_orig"] = df.work_link
    hmap = {k: snap(k)[0] for k in set(df.home_link.astype(str))}
    wmap = {k: snap(k)[0] for k in set(df.work_link.astype(str))}
    df["home_link"] = df.home_link.astype(str).map(hmap)
    df["work_link"] = df.work_link.astype(str).map(wmap)
    df["home_repair_m"] = df.home_link_orig.astype(str).map(lambda k: snap(k)[1])
    df["work_repair_m"] = df.work_link_orig.astype(str).map(lambda k: snap(k)[1])
    df["home_node"] = df.home_link.map(lambda k: int(cfrom[k]))
    df["work_node"] = df.work_link.map(lambda k: int(cfrom[k]))
    df.to_csv(POP_OUT / f"agent_spatial_assignment_lambda_{lam}.csv",
              index=False, encoding="utf-8-sig")

    d = np.array(repair_d) if repair_d else np.array([0.0])
    stats = {
        "lambda": lam,
        "persons": n_person,
        "home_link_repaired": n_home_fix,
        "work_link_repaired": n_work_fix,
        "affected_persons": int(((df.home_repair_m > 0) | (df.work_repair_m > 0)).sum()),
        "repair_distance_m": {
            "median": float(np.median(d)),
            "p90": float(np.percentile(d, 90)),
            "p95": float(np.percentile(d, 95)),
            "max": float(d.max()),
        },
        "output": str(dst),
    }
    print(f"[repair] {lam}: persons={n_person} home_fix={n_home_fix} "
          f"work_fix={n_work_fix} median_d={stats['repair_distance_m']['median']:.1f} m")
    return stats


def main() -> int:
    clean_out = NET_DIR / "network_cleaned.xml.gz"
    if not clean_out.exists() or "--force-clean" in sys.argv:
        rc = run_network_cleaner(NET_DIR / "network.xml.gz", clean_out)
        if rc != 0:
            print("NetworkCleaner FAILED")
            return 1

    orig_links, orig_nodes = read_network(NET_DIR / "network.xml.gz")
    c_links, c_nodes = read_network(clean_out)
    rem_links = set(orig_links) - set(c_links)
    rem_nodes = set(orig_nodes) - set(c_nodes)

    report = {
        "frozen_network": str(NET_DIR / "network.xml.gz"),
        "cleaned_network": str(clean_out),
        "original": {"nodes": len(orig_nodes), "directed_links": len(orig_links)},
        "car_main_component": {"nodes": len(c_nodes), "directed_links": len(c_links)},
        "removed": {"nodes": len(rem_nodes), "directed_links": len(rem_links),
                    "pct_links": round(100 * len(rem_links) / len(orig_links), 3)},
        "population_repair": [],
    }

    for lam in LAMBDAS:
        report["population_repair"].append(
            repair_population(lam, c_links, c_nodes, orig_links, orig_nodes))

    (NET_DIR / "connectivity_repair.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print("\n[report]", NET_DIR / "connectivity_repair.json")
    print(json.dumps({k: v for k, v in report.items() if k != "population_repair"},
                     indent=2, ensure_ascii=False))
    print("STATUS: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
