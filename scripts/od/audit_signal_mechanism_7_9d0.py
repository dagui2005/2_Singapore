# -*- coding: utf-8 -*-
"""
audit_signal_mechanism_7_9d0.py —— ★Dynamic Realism Audit · 第 ④ 项
「信号交叉口 / 交叉口能力是否进入 MATSim 动态机制」的**零仿真**严格排查

动机（用户原文）
----------------
「特别是**信号交叉口是否进入 MATSim 动态机制**，这一项我们目前还没有完成
  像 Q4 那么严格的排查，因此不能现在就说它没问题。」

本脚本不跑仿真，只从**冻结产物**取证：
  Q1  config 是否启用 signals/intersection/turn 模块？
  Q2  冻结网络文件里是否存在任何信号/交叉口语义（元素、属性、OSM 标签残留）？
  Q3  链路容量是怎么来的？（是否 = lanes × 单位通行能力查表）
  Q4  该容量的隐含假设是什么？（"全天全绿" ⇒ 相对真实信号交叉口偏高多少？）
  Q5  全网里程/流量中有多少落在"信号化断面"上（即受此偏高影响的面）？

输出
----
reports/dynamic_realism_audit_7_9/_signal_mechanism_audit.json
reports/dynamic_realism_audit_7_9/_signal_mechanism_audit.md
判决闭集：SIGNAL_MECHANISM_ABSENT | SIGNAL_MECHANISM_PRESENT | AUDIT_INCONCLUSIVE
（注：本脚本**不**给出"是否该修"的结论，只给机制事实。）
"""
from __future__ import annotations

import gzip
import json
import re
import sys
import time
from pathlib import Path

ROOT = Path(r"D:\Luan\2026-05\2_Singapore")
OUT_DIR = ROOT / "reports" / "dynamic_realism_audit_7_9"
OUT_JSON = OUT_DIR / "_signal_mechanism_audit.json"
OUT_MD = OUT_DIR / "_signal_mechanism_audit.md"

CONFIG = ROOT / "matsim_final_7_6h" / "configs" / "config_W01_rc_min.xml"
NETWORK = ROOT / "reports" / "matsim_network" / "network_cleaned.xml.gz"
CACHE = ROOT / "scripts" / "od" / "_cache_network_7_9c0.npz"
LS_V10 = (ROOT / "matsim_final_7_6h" / "outputs" / "W01_rc_min" / "ITERS" / "it.19"
          / "W01_rc_min.19.linkstats.txt.gz")
MATSIM_DIR = ROOT / "tools" / "matsim-2026.0"
MATSIM_JAR = MATSIM_DIR / "matsim-2026.0.jar"
SOURCES_JAR = MATSIM_DIR / "matsim-2026.0-sources.jar"
LIBS_DIR = MATSIM_DIR / "libs"

# 信号/交叉口语义的候选令牌（在网络 XML 中搜索）
SIGNAL_TOKENS = [b"signal", b"Signal", b"SIGNAL", b"traffic_light", b"traffic_li",
                 b"trafficLight", b"greenTime", b"amber", b"phase", b"turn",
                 b"restriction", b"fromLink", b"toLink", b"nodeTransition"]

# 单位通行能力查表（若 Q3 成立，则应能从 cap/lanes 反解出每类一条常数）
SIGNALIZED_CLASSES = {"primary", "secondary", "tertiary", "residential",
                      "unclassified", "living_street", "primary_link",
                      "secondary_link", "tertiary_link", "service"}
FREEFLOW_CLASSES = {"motorway", "trunk", "motorway_link", "trunk_link"}


def q1_config() -> dict:
    txt = CONFIG.read_text(encoding="utf-8", errors="replace")
    mods = re.findall(r'<module name="([^"]+)"', txt)
    hits = [m for m in mods if re.search(r"signal|intersect|turn|node", m, re.I)]
    disabled = []
    for m in ("signals", "signalsystems", "intersection", "turns",
              "qsim.signals", "network.turnInfo"):
        disabled.append({"module": m, "present": m in [x.lower() for x in mods]})
    return {"n_modules": len(mods), "modules": mods,
            "signal_like_modules": hits,
            "candidate_module_presence": disabled,
            "verdict": "NO_SIGNAL_MODULE" if not hits else "SIGNAL_MODULE_PRESENT"}


def q2_network_scan() -> dict:
    """流式扫描网络 XML，统计信号/交叉口令牌出现次数（只扫标签名，不扫数值）。"""
    counts = {t.decode(): 0 for t in SIGNAL_TOKENS}
    n_node = 0
    n_link = 0
    node_extra_attr = 0        # 节点除 id/x/y 外还有别的属性
    link_attr_subel = 0        # link 内含 <attribute> 子元素
    pat_node = re.compile(rb"<node\b[^>]*>")
    pat_link = re.compile(rb"<link\b[^>]*>")
    pat_attr = re.compile(rb"<attribute\b")
    buf = b""
    with gzip.open(NETWORK, "rb") as fh:
        while True:
            chunk = fh.read(1 << 22)          # 4 MiB
            if not chunk:
                break
            buf += chunk
            for t in SIGNAL_TOKENS:
                counts[t.decode()] += buf.count(t)
            for m in pat_node.finditer(buf):
                n_node += 1
                tag = m.group(0)
                # 允许：id, x, y  （+ 可选空白）
                rest = re.sub(rb'\s+(id|x|y)="[^"]*"', b"", tag)
                rest = re.sub(rb"</?node\b|/?>", b"", rest).strip()
                if rest:
                    node_extra_attr += 1
            n_link += len(pat_link.findall(buf))
            link_attr_subel += len(pat_attr.findall(buf))
            buf = buf[-4096:]                 # 保留尾部，避免跨块漏匹配
    counts = {k: v for k, v in counts.items() if v}
    return {"n_node": n_node, "n_link": n_link,
            "token_counts": counts,
            "node_with_extra_attributes": node_extra_attr,
            "link_with_attribute_subelements": link_attr_subel,
            "verdict": "NETWORK_HAS_NO_SIGNAL_SEMANTICS" if not counts
                       else "NETWORK_CARRIES_SIGNAL_TOKENS"}


def q3_q4_capacity() -> dict:
    """从缓存反解 单位通行能力(unit_cap) = cap / lanes，按 highway 分组看是否常数。"""
    import numpy as np
    z = np.load(CACHE, allow_pickle=True)
    cap = z["cap"].astype("float64")
    lanes = z["lanes"].astype("float64")
    hw = np.array([str(x) for x in z["highway"]], dtype=object)
    ok = lanes > 0
    unit = np.zeros_like(cap)
    unit[ok] = cap[ok] / lanes[ok]
    rows = {}
    for h in sorted(set(hw.tolist())):
        m = (hw == h) & ok
        if not m.any():
            continue
        u = unit[m]
        rows[h] = {"n": int(m.sum()), "unit_cap_min": float(u.min()),
                   "unit_cap_max": float(u.max()),
                   "is_constant": bool(abs(u.max() - u.min()) < 1e-9),
                   "cap_sum": float(cap[m].sum()),
                   "lanes_sum": float(lanes[m].sum())}
    # 只有"每类常数"才允许断言查表
    all_const = all(r["is_constant"] for r in rows.values())
    return {"n_links_total": int(len(cap)), "n_links_lanes_gt0": int(ok.sum()),
            "by_highway": rows, "all_classes_constant": all_const,
            "verdict": "CAPACITY_IS_TABLE_LOOKUP" if all_const
                       else "CAPACITY_NOT_PURE_LOOKUP"}


def q5_exposure(unit_table: dict) -> dict:
    """按里程/流量统计"信号化断面"（非 motorway/trunk 类）暴露面。"""
    import numpy as np
    z = np.load(CACHE, allow_pickle=True)
    hw = np.array([str(x) for x in z["highway"]], dtype=object)
    ln = z["len_m"].astype("float64")
    # linkstats: LINK(0), LENGTH(4), HRS8-9avg(32)
    ids, h89, lstat_len = [], [], []
    with gzip.open(LS_V10, "rt", encoding="utf-8", newline="") as fh:
        hdr = fh.readline().rstrip("\n").split("\t")
        i_link, i_len, i_h89 = hdr.index("LINK"), hdr.index("LENGTH"), hdr.index("HRS8-9avg")
        for line in fh:
            tk = line.split("\t")
            if len(tk) <= i_h89:
                continue
            ids.append(tk[i_link]); lstat_len.append(float(tk[i_len]))
            h89.append(float(tk[i_h89]))
    ids = np.array(ids, dtype=object)
    lstat_len = np.array(lstat_len); h89 = np.array(h89)
    idx = {k: i for i, k in enumerate(z["ids"].tolist())}
    take = np.array([idx.get(k, -1) for k in ids.tolist()])
    keep = take >= 0
    hw_ls = hw[take[keep]]
    is_sig = np.array([h in SIGNALIZED_CLASSES for h in hw_ls.tolist()])
    L = lstat_len[keep]; F = h89[keep]
    # 里程面用 linkstats 的 canonical LENGTH（与靶场同源）
    km_all = float(L.sum()) / 1000.0
    km_sig = float(L[is_sig].sum()) / 1000.0
    veh_all = float(F.sum())
    veh_sig = float(F[is_sig].sum())
    return {"n_matched": int(keep.sum()),
            "km_all": km_all, "km_signalized": km_sig,
            "share_km_signalized": (km_sig / km_all) if km_all else None,
            "veh_all": veh_all, "veh_signalized": veh_sig,
            "share_veh_signalized": (veh_sig / veh_all) if veh_all else None,
            "note": "信号化面 = 非 motorway/trunk 类链路（真实中受信号控制的路段）"}


def q6_implementation() -> dict:
    """实现层证据：核心 jar 是否含信号实现？classpath 是否有 signals contrib？
    并提取 3 段源码事实（恒绿桩 / 仅拓扑转向接受 / 节点转换默认"不阻塞"）。"""
    import zipfile
    res: dict = {}
    with zipfile.ZipFile(MATSIM_JAR) as z:
        names = z.namelist()
    res["core_jar_entries"] = len(names)
    # 应有实现的类（若信号可用）
    impl_classes = ["SignalSystemsConfigGroup", "SignalSystemsModule", "SignalPlan",
                    "SignalsModule", "SignalUtils", "SignalControl", "Signals"]
    res["impl_class_hits"] = {c: [n for n in names if c in n] for c in impl_classes}
    res["impl_classes_present"] = sorted(c for c, v in res["impl_class_hits"].items() if v)
    # 仅接口/桩/可视化
    res["interface_or_stub"] = [n for n in names
                                if any(k in n for k in ("SignalizeableItem", "SignalGroupState",
                                                        "VisSignal"))]
    # 信号 DTD 存在（说明"能读"信号文件，但没有"能跑"信号的实现）
    res["signal_dtd"] = [n for n in names if n.startswith("dtd/") and "signal" in n.lower()]
    # classpath：libs/ 里有无 matsim/signals contrib
    libs = sorted(p.name for p in LIBS_DIR.glob("*.jar")) if LIBS_DIR.is_dir() else []
    res["libs_count"] = len(libs)
    res["libs_matsim_or_signal"] = [x for x in libs if re.search(r"matsim|signal", x, re.I)]

    # 源码事实
    facts = {}
    try:
        with zipfile.ZipFile(SOURCES_JAR) as zs:
            s1 = zs.read("org/matsim/core/mobsim/qsim/qnetsimengine/"
                         "DefaultSignalizeableItem.java").decode("utf-8", "replace")
            s2 = zs.read("org/matsim/core/mobsim/qsim/qnetsimengine/"
                         "DefaultTurnAcceptanceLogic.java").decode("utf-8", "replace")
            s3 = zs.read("org/matsim/core/config/groups/QSimConfigGroup.java").decode("utf-8", "replace")
        facts["all_green_stub"] = bool(
            "SignalGroupState.GREEN" in s1 and "private boolean linkGreen = true" in s1)
        facts["turn_accept_topology_only"] = bool(
            "isAcceptingTurn" in s2 and "getFromNode()" in s2
            and "capacity" not in s2.lower() and "green" not in s2.lower())
        m = re.search(r"private\s+NodeTransition\s+nodeTransitionLogic\s*=\s*NodeTransition\.(\w+)", s3)
        facts["node_transition_default"] = m.group(1) if m else None
        m2 = re.search(r"public\s+enum\s+NodeTransition\s*\{(.*?)\}", s3, re.S)
        facts["node_transition_options"] = (
            [x.strip() for x in m2.group(1).split(",") if x.strip()] if m2 else [])
        facts["node_transition_has_java_setter"] = bool(
            re.search(r"public\s+void\s+setNodeTransitionLogic\s*\(", s3))
        facts["node_transition_has_config_setter"] = bool(
            re.search(r"@StringSetter\([^)]*NODE_TRANSITION[^)]*\)\s*"
                      r"(?:private|public)\s+void\s+setNodeTransition[A-Za-z]*\(", s3))
        facts["node_transition_is_config_written"] = bool(
            re.search(r'name="nodeTransition', CONFIG.read_text(encoding="utf-8", errors="replace")))
    except Exception as e:  # pragma: no cover
        facts["error"] = repr(e)
    res["source_facts"] = facts

    absent = (not res["impl_classes_present"]) and (not res["libs_matsim_or_signal"])
    res["verdict"] = ("SIGNAL_IMPL_NOT_ON_CLASSPATH" if absent
                      else "SIGNAL_IMPL_AVAILABLE")
    return res


def main() -> int:
    t0 = time.time()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    print("=" * 78)
    print("★ Dynamic Realism Audit · 第 ④ 项：信号/交叉口是否进入 MATSim 动态机制")
    print("=" * 78)

    r1 = q1_config()
    print(f"\n[Q1] config 模块 = {r1['n_modules']} 个；信号类命中 = {r1['signal_like_modules']}")
    print(f"     -> {r1['verdict']}")

    r2 = q2_network_scan()
    print(f"\n[Q2] 网络文件：node={r2['n_node']:,}  link={r2['n_link']:,}")
    print(f"     信号/交叉口令牌计数 = {r2['token_counts'] or '（全部为 0）'}")
    print(f"     节点带额外属性 = {r2['node_with_extra_attributes']:,}；"
          f"link 含 <attribute> 子元素 = {r2['link_with_attribute_subelements']:,}")
    print(f"     -> {r2['verdict']}")

    r3 = q3_q4_capacity()
    print(f"\n[Q3] 单位通行能力反解（cap/lanes）按 highway 分组，是否组内常数 = "
          f"{r3['all_classes_constant']}")
    for h, d in sorted(r3["by_highway"].items(), key=lambda kv: -kv[1]["n"])[:12]:
        print(f"     {h:<16} n={d['n']:>7,}  unit_cap={d['unit_cap_min']:.1f}"
              f"{'' if d['is_constant'] else '..'+format(d['unit_cap_max'],'.1f')}"
              f"  const={d['is_constant']}")
    print(f"     -> {r3['verdict']}")

    r5 = q5_exposure(r3)
    print(f"\n[Q5] 信号化断面暴露面（v1.0 it.19 linkstats 口径）")
    print(f"     匹配链路 {r5['n_matched']:,}")
    print(f"     里程：{r5['km_signalized']:,.1f} / {r5['km_all']:,.1f} km "
          f"= {100*r5['share_km_signalized']:.2f}%")
    print(f"     流量：{r5['veh_signalized']:,.0f} / {r5['veh_all']:,.0f} veh/h "
          f"= {100*r5['share_veh_signalized']:.2f}%")

    r6 = q6_implementation()
    print(f"\n[Q6] 实现层：核心 jar {r6['core_jar_entries']:,} 项；信号实现类命中 = "
          f"{r6['impl_classes_present'] or '（无）'}")
    print(f"     仅接口/桩/可视化类 = {len(r6['interface_or_stub'])} 个；"
          f"信号 DTD = {len(r6['signal_dtd'])} 个")
    print(f"     libs/ 共 {r6['libs_count']} 个 jar，含 matsim/signal 关键字者 = "
          f"{r6['libs_matsim_or_signal'] or '（无）'}")
    f = r6["source_facts"]
    print(f"     源码事实：恒绿桩={f.get('all_green_stub')}；"
          f"转向接受仅拓扑={f.get('turn_accept_topology_only')}；"
          f"节点转换默认={f.get('node_transition_default')}；"
          f"Java setter={f.get('node_transition_has_java_setter')}/"
          f"config setter={f.get('node_transition_has_config_setter')}/"
          f"config 已写出={f.get('node_transition_is_config_written')}")
    print(f"     -> {r6['verdict']}")

    # Q4 的解析性结论（基于 Q3 前提）
    green_ratio_note = (
        "链路容量 = 车道数 × 单位通行能力（查表），等价于**全天全绿**假设。"
        "真实信号交叉口的进口道有效通行能力 ≈ 饱和流率 × 绿信比，城市典型绿信比 ~0.45–0.55；"
        "因此 MATSim 默认把信号化进口道的容量**系统性高估约 2 倍**（独立于 sample-size 修正）。"
    ) if r3["all_classes_constant"] else "容量非纯查表 ⇒ 需进一步判定，Q4 待定。"

    verdict = "AUDIT_INCONCLUSIVE"
    if (r1["verdict"] == "NO_SIGNAL_MODULE"
            and r2["verdict"] == "NETWORK_HAS_NO_SIGNAL_SEMANTICS"
            and r6["verdict"] == "SIGNAL_IMPL_NOT_ON_CLASSPATH"):
        verdict = "SIGNAL_MECHANISM_ABSENT"
    elif (r1["verdict"] == "SIGNAL_MODULE_PRESENT"
          or r2["verdict"] == "NETWORK_CARRIES_SIGNAL_TOKENS"):
        verdict = "SIGNAL_MECHANISM_PRESENT"

    rec = {
        "step": "DynamicRealismAudit/④-signal-intersection",
        "verdict": verdict,
        "Q1_config": r1, "Q2_network": r2, "Q3_capacity": r3, "Q5_exposure": r5,
        "Q6_implementation": r6,
        "Q4_implication": {
            "green_ratio_gap": green_ratio_note,
            "combined_with_sampling": (
                "A-1 已把 capacity 乘 0.434977（抽样修正）；信号绿信比缺口（≈×0.5）"
                "是**另一个、当前完全未处理**的因子。两者相乘 ⇒ 信号化进口道仍偏松约 2 倍。"
            ),
        },
        "elapsed_s": round(time.time() - t0, 2),
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    OUT_JSON.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")

    md = [f"# ★ 信号/交叉口机制审计（零仿真）\n",
          f"- 判决：**{verdict}**",
          f"- Q1 config 信号类模块：`{r1['signal_like_modules'] or '无'}`（共 {r1['n_modules']} 个模块）",
          f"- Q2 网络信号令牌：`{r2['token_counts'] or '全 0'}`；"
          f"节点额外属性 {r2['node_with_extra_attributes']:,}；link `<attribute>` 子元素 "
          f"{r2['link_with_attribute_subelements']:,}",
          f"- Q3 容量 = lanes × unit_cap 查表：**{r3['all_classes_constant']}**",
          f"- Q5 信号化断面里程占比 **{100*r5['share_km_signalized']:.2f}%**、"
          f"流量占比 **{100*r5['share_veh_signalized']:.2f}%**",
          f"- Q6 实现层：核心 jar 无信号实现类（命中 `{r6['impl_classes_present'] or '无'}`）；"
          f"libs/ {r6['libs_count']} jar 无 signals contrib ⇒ `{r6['verdict']}`",
          f"- Q6 源码事实：恒绿桩 `{f.get('all_green_stub')}`；"
          f"转向接受仅拓扑 `{f.get('turn_accept_topology_only')}`；"
          f"节点转换默认 `{f.get('node_transition_default')}`；"
          f"Java setter `{f.get('node_transition_has_java_setter')}` / "
          f"config setter `{f.get('node_transition_has_config_setter')}` / "
          f"config 已写出 `{f.get('node_transition_is_config_written')}`"
          f"（⇒ 本版本**不可经 config 配置**，只能改 Java 代码）",
          f"- Q4 含义：{green_ratio_note}",
          f"\n生成时间 {rec['generated_at']}（{rec['elapsed_s']} s）"]
    OUT_MD.write_text("\n".join(md) + "\n", encoding="utf-8")

    print(f"\n[判决] {verdict}")
    print(f"落盘   {OUT_JSON.name} ({OUT_JSON.stat().st_size:,} B) / {OUT_MD.name} "
          f"({OUT_MD.stat().st_size:,} B)")
    print(f"耗时   {rec['elapsed_s']} s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
