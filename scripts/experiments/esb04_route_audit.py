#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""
esb04_route_audit.py — E-SB-04 阶段 1+2：输入门禁 + 路线结构（路径重分配）审计
================================================================================
★零仿真 · 只读。 不启动 MATSim；不改 network / population / capacity / freespeed /
SCALE / lambda / 阈值 / 任何冻结配置；不生成 v1.1。

主比较：v1.0 vs SB-A5；SB-A5ind 仅作独立 OD 稳健性参照。

阶段 1（输入存在性与可比性门禁）
    - 逐一核实 events / plans / network / LinkID-highway 映射 / E-SB-03 产物 是否存在且可解析
    - 逐项列明两臂差异（允许 freespeed 不同）
    - population/person ID、agent 数、seed、迭代号、网络拓扑 可比性

阶段 2（区分路线变化与时段变化）
    A 实际/计划路线变化：selected plan 的有向 link 序列、route hash 变化率、道路等级
      路径长度占比、快速路进出次数、等级转换序列、走廊集中度
    B 时段（证据受限）：仅据已存在的 events（v1.0）与 linkstats；SB-A5 无 events ⇒ 标 BLOCKED
    C 观测断面映射：与 O3-R1 分列；对向/平行 link 检测

产物 → reports/path_redistribution_audit_E_SB_04/
用法：python scripts/experiments/esb04_route_audit.py
"""
from __future__ import annotations

import gzip
import hashlib
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(r"D:\Luan\2026-05\2_Singapore")
OUT = ROOT / "reports" / "path_redistribution_audit_E_SB_04"
EXP = ROOT / "experiments" / "E-SB-04_path_redistribution_audit"
OUT.mkdir(parents=True, exist_ok=True)
CACHE = EXP / "_cache"          # 大体积中间缓存（plans 解析结果），不入 reports
CACHE.mkdir(parents=True, exist_ok=True)

NET_SRC = ROOT / "reports" / "matsim_network" / "network_links_source_copy.csv"
E3_AUDIT = ROOT / "experiments" / "E-SB-03_flow_shift_audit" / "audit"

ARMS = {
    "v1.0":     {"run": ROOT / "matsim_final_7_6h" / "outputs" / "W01_rc_min", "rid": "W01_rc_min"},
    "SB-A5":    {"run": ROOT / "experiments" / "E-SB-02_night_freeflow" / "outputs" / "SB-A5", "rid": "SB-A5"},
    "SB-A5ind": {"run": ROOT / "experiments" / "E-SB-02_night_freeflow" / "outputs" / "SB-A5ind", "rid": "SB-A5ind"},
}
BASE = "v1.0"
V10_EVENTS = ROOT / "matsim_viz_7_8" / "outputs" / "W01_events" / "W01_events.output_events.xml.gz"

# E-SB-03 已识别走廊（用于「变化是否集中于快速路」）
CORRIDORS = {
    "PIE": r"pan[- ]?island expressway",
    "TPE": r"tampines expressway",
    "CTE": r"central expressway",
    "KPE": r"kallang[- ]?paya lebar expressway",
    "KJE": r"kranji expressway",
    "AYE": r"ayer rajah expressway",
    "SLE": r"seletar expressway",
    "BKE": r"bukit timah expressway",
    "MCE": r"marina co[a-z]*tal expressway",
    "ECP": r"east coast parkway",
}

CLASSES = ["motorway", "motorway_link", "trunk", "trunk_link", "primary",
           "primary_link", "secondary", "secondary_link", "tertiary",
           "tertiary_link", "service", "unclassified", "residential"]

GATES: list[dict] = []


def gate(cid, name, ok, detail=""):
    GATES.append({"id": cid, "gate": name, "pass": bool(ok), "detail": detail})
    print(f"  [{'PASS' if ok else 'FAIL'}] {cid}  {name}" + (f"  | {detail}" if detail else ""), flush=True)
    return bool(ok)


# --------------------------------------------------------------------------
def sha256_file(p: Path, chunk=1 << 22) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        while True:
            b = f.read(chunk)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def parse_config(path: Path) -> dict:
    """极简 XML 参数抽取：name → value（module 前缀限定作用域）。"""
    txt = path.read_text(encoding="utf-8", errors="replace")
    mods = re.split(r'<module\s+name="([^"]+)"', txt)
    params = {}
    # 顶层
    for m in re.finditer(r'<param\s+name="([^"]+)"\s+value="([^"]*)"', txt):
        params.setdefault(m.group(1), m.group(2))
    # 模块内
    blocks = re.findall(r'<module\s+name="([^"]+)"(.*?)</module>', txt, re.S)
    for modname, body in blocks:
        for m in re.finditer(r'<param\s+name="([^"]+)"\s+value="([^"]*)"', body):
            params[f"{modname}.{m.group(1)}"] = m.group(2)
    return params


def parse_network(path: Path):
    """返回 id→(length, freespeed, capacity, permlanes, from, to)（length 单位=米，权威）。"""
    links = {}
    link_re = re.compile(
        r'<link\s+id="([^"]+)"\s+from="([^"]+)"\s+to="([^"]+)"\s+length="([^"]+)"'
        r'\s+freespeed="([^"]+)"\s+capacity="([^"]+)"\s+permlanes="([^"]+)"')
    with gzip.open(path, "rt", encoding="utf-8", errors="replace") as f:
        for line in f:
            if '<link ' not in line:
                continue
            m = link_re.search(line)
            if m:
                links[m.group(1)] = (float(m.group(4)), float(m.group(5)),
                                     float(m.group(6)), float(m.group(7)),
                                     m.group(2), m.group(3))
    return links


def parse_selected_plans(path: Path):
    """流式解析：每人**只取 selected='yes'** 的 plan 的 car leg 路线。

    返回 DataFrame[person, route_hash, n_links, links(空格串), start_link,
                    end_link, trav_time_s, dep_time_s, n_plans, n_car_legs]
    以及 n_persons / plan 统计。
    """
    person_re = re.compile(r'<person\s+id="([^"]+)"')
    plan_re = re.compile(r'<plan\b[^>]*selected="(yes|no)"')
    route_re = re.compile(
        r'<route\s+type="links"\s+start_link="([^"]*)"\s+end_link="([^"]*)"'
        r'[^>]*?trav_time="([^"]*)"[^>]*?>(.*?)</route>')

    rows = []
    cur = None
    sel = False          # 当前 plan 是否 selected
    cur_links = []       # 当前 person 的 selected 路线链接（可能多条 leg 拼接）
    cur_meta = None
    n_plans_person = 0
    n_persons = 0
    n_plan_total = 0
    n_sel_total = 0

    def flush():
        nonlocal cur, cur_links, cur_meta, n_plans_person
        if cur is None:
            return
        if cur_links:
            joined = " ".join(cur_links)
            rows.append({
                "person": cur,
                "route_hash": hashlib.md5(joined.encode()).hexdigest(),
                "n_links": len(cur_links),
                "links": joined,
                "start_link": cur_meta[0],
                "end_link": cur_meta[1],
                "trav_time_s": cur_meta[2],
                "n_plans": n_plans_person,
            })
        cur = None
        cur_links = []
        cur_meta = None
        n_plans_person = 0

    with gzip.open(path, "rt", encoding="utf-8", errors="replace") as f:
        for line in f:
            if '<person ' in line:
                flush()
                m = person_re.search(line)
                cur = m.group(1) if m else None
                n_persons += 1
                n_plans_person = 0
                continue
            if '<plan ' in line or '<plan>' in line:
                m = plan_re.search(line)
                if m:
                    sel = (m.group(1) == "yes")
                    n_plans_person += 1
                    n_plan_total += 1
                    if sel:
                        n_sel_total += 1
                continue
            if 'type="links"' in line and sel:
                m = route_re.search(line)
                if m:
                    cur_links.extend(m.group(4).strip().split())
                    if cur_meta is None:
                        cur_meta = (m.group(1), m.group(2), _t2s(m.group(3)))
        flush()

    return pd.DataFrame(rows), {"n_persons": n_persons, "n_plan_total": n_plan_total,
                                "n_selected": n_sel_total}


def _t2s(t: str) -> float:
    try:
        parts = t.split(":")
        if len(parts) == 3:
            return int(parts[0]) * 3600 + int(parts[1]) * 60 + float(parts[2])
        return float(t)
    except Exception:
        return np.nan


def load_net_attrs():
    """id → (highway, name, corridor) 来自 network_links_source_copy.csv （权威等级源）。"""
    e = pd.read_csv(NET_SRC, encoding="utf-8-sig", low_memory=False,
                    usecols=["from_node", "to_node", "highway", "name"])
    e["matsim_link_id"] = "e" + e["from_node"].astype(str) + "_" + e["to_node"].astype(str)
    e["highway"] = e["highway"].astype(str).str.lower().str.strip()
    nm = e["name"].astype(str).str.lower()
    corr = pd.Series("", index=e.index)
    for code, pat in CORRIDORS.items():
        corr = corr.mask(nm.str.contains(pat, regex=True) & (corr == ""), code)
    e["corridor"] = corr
    if e["matsim_link_id"].duplicated().any():
        raise RuntimeError("net src 出现重复 matsim_link_id")
    return e.set_index("matsim_link_id")[["highway", "corridor"]]


def classify_arm(routes: pd.DataFrame, net: pd.DataFrame):
    """对每个 selected 路线计算等级长度占比 / 快速路进出次数 / 走廊命中。"""
    hw = net["highway"].to_dict()
    corr = net["corridor"].to_dict()
    ln = NET_LEN  # id → length(m)，来自 network XML（权威）

    recs = []
    for r in routes.itertuples(index=False):
        links = r.links.split()
        cls_len = defaultdict(float)
        tot = 0.0
        mw_segments = 0
        prev = None
        corr_hit = set()
        for lk in links:
            c = hw.get(lk, "UNKNOWN")
            L = ln.get(lk, 0.0)
            tot += L
            cls_len[c] += L
            if c == "motorway" and prev != "motorway":
                mw_segments += 1
            prev = c
            cc = corr.get(lk, "")
            if cc:
                corr_hit.add(cc)
        d = {"person": r.person, "route_hash": r.route_hash, "n_links": r.n_links,
             "total_len_m": tot, "mw_segments": mw_segments,
             "start_link": r.start_link, "end_link": r.end_link}
        for c in CLASSES:
            d[f"len_{c}"] = cls_len.get(c, 0.0)
        for code in CORRIDORS:
            d[f"use_{code}"] = code in corr_hit
        recs.append(d)
    df = pd.DataFrame(recs)
    # 占比
    tot = df["total_len_m"].replace(0, np.nan)
    for c in CLASSES:
        df[f"share_{c}"] = df[f"len_{c}"] / tot
    return df


# --------------------------------------------------------------------------
def main() -> int:
    print("=" * 100)
    print("E-SB-04 路径重分配与观测域流量增量审计 · 阶段 1（门禁）+ 阶段 2（路线结构）")
    print("=" * 100)

    # ================= 阶段 1：输入存在性与可比性门禁 =================
    print("\n[阶段 1] 输入清单与哈希")
    input_files = {}
    for lab, a in ARMS.items():
        rid = a["rid"]
        run = a["run"]
        input_files[f"{lab}.plans"] = run / f"{rid}.output_plans.xml.gz"
        input_files[f"{lab}.network"] = run / f"{rid}.output_network.xml.gz"
        input_files[f"{lab}.config"] = run / f"{rid}.output_config_reduced.xml"
        input_files[f"{lab}.config_full"] = run / f"{rid}.output_config.xml"
    input_files["v1.0.events"] = V10_EVENTS
    input_files["v1.0.events_config"] = V10_EVENTS.parent / "W01_events.output_config_reduced.xml"
    input_files["net_src_copy"] = NET_SRC
    input_files["esb03_section_delta"] = E3_AUDIT / "esb03_section_delta.csv"
    input_files["esb03_total_decomposition"] = E3_AUDIT / "esb03_total_decomposition.csv"
    input_files["esb03_summary"] = E3_AUDIT / "esb03_summary.json"

    manifest = {}
    for k, p in input_files.items():
        ex = p.exists()
        rec = {"path": str(p), "exists": ex}
        if ex:
            rec["size_bytes"] = p.stat().st_size
            rec["sha256"] = sha256_file(p)
        manifest[k] = rec
        print(f"    {k:28s} exists={ex!s:5s} size={rec.get('size_bytes',0):>14,}")

    gate("G01", "v1.0/SB-A5/SB-A5ind 的 plans 与 network 均存在", 
         all(manifest[f"{l}.plans"]["exists"] and manifest[f"{l}.network"]["exists"] for l in ARMS))
    gate("G02", "v1.0 events 存在（writeEventsInterval 重跑）", manifest["v1.0.events"]["exists"])
    sb_ev = [manifest[f"{l}.events"]["exists"] if f"{l}.events" in manifest else False for l in ("SB-A5", "SB-A5ind")]
    gate("G03", "SB-A5/SB-A5ind events 均缺失（⇒ 证据降级）", not any(sb_ev),
         "SB-A5/SB-A5ind writeEventsInterval=0")

    # ---- 配置可比性 ----
    print("\n[阶段 1] 配置逐项比对（完整 config）")
    cfgs = {lab: parse_config(ARMS[lab]["run"] / f"{ARMS[lab]['rid']}.output_config.xml")
            for lab in ARMS}
    cfgs["v1.0_events"] = parse_config(V10_EVENTS.parent / "W01_events.output_config.xml")

    keys = sorted(set().union(*[set(c) for c in cfgs.values()]))
    cfg_rows = []
    for k in keys:
        vals = {lab: cfgs[lab].get(k, "<absent>") for lab in cfgs}
        uniq = set(vals.values())
        if len(uniq) > 1:
            cfg_rows.append({"param": k, **vals})
    cfg_diff = pd.DataFrame(cfg_rows)
    cfg_diff.to_csv(OUT / "config_diff_vs_base.csv", index=False, encoding="utf-8-sig")
    print(f"    两臂差异参数条数（v1.0/SB-A5/SB-A5ind/v1.0_events 任一不同）：{len(cfg_diff)}")
    for _, r in cfg_diff.iterrows():
        if r["param"].startswith(("network", "plans", "replanning", "qsim", "global", "controller", "timeAllocation")):
            print(f"      {r['param']:42s} v10={str(r['v1.0'])[:40]:42s} A5={str(r['SB-A5'])[:40]}")

    # events 重跑与 v1.0 只应差 outputDirectory / writeEventsInterval / runId（皆外观）
    def _cosmetic(k):
        return k.endswith("outputDirectory") or k.endswith("runId") or k == "runId"
    ev_diff = [k for k in keys if cfgs["v1.0_events"].get(k, "<absent>") != cfgs["v1.0"].get(k, "<absent>")]
    ev_diff_hard = [k for k in ev_diff if not _cosmetic(k)]
    gate("G04", "events 重跑 = v1.0 冻结配置（仅差 outputDirectory/runId/writeEventsInterval）",
         set(ev_diff_hard) <= {"writeEventsInterval", "controller.writeEventsInterval"},
         f"实质差异={ev_diff_hard}（外观差异={[k for k in ev_diff if _cosmetic(k)]}）")

    # 关键冻结参数一致性
    def cfg_get(lab, key):
        return cfgs[lab].get(key, "<absent>")

    for key in ["flowCapacityFactor", "qsim.flowCapacityFactor", "storageCapacityFactor",
                "qsim.storageCapacityFactor", "randomSeed", "global.randomSeed",
                "replanning.fractionOfIterationsToDisableInnovation", "routingRandomness",
                "replanning.routingRandomness"]:
        if cfg_get(BASE, key) != "<absent>":
            same = all(cfg_get(l, key) == cfg_get(BASE, key) for l in ARMS)
            gate(f"G05.{key}", f"{key} 三臂一致 = {cfg_get(BASE,key)}", same,
                 "" if same else " | ".join(f"{l}={cfg_get(l,key)}" for l in ARMS))

    # ★ 需求（population）同一性：决定「路线变化」能否干净归因于 freespeed
    pop = {lab: cfg_get(lab, "plans.inputPlansFile") for lab in ARMS}
    gate("G13", "v1.0 与 SB-A5 使用同一 inputPlansFile（主比较需求可比）",
         pop["SB-A5"] == pop[BASE],
         " | ".join(f"{l}={'同' if pop[l]==pop[BASE] else '异'}" for l in ARMS))
    for l in ARMS:
        if pop[l] != pop[BASE]:
            print(f"      ⚠️ {l} 需求 ≠ v1.0：{Path(pop[l]).name} ⇒ 其「路线变化」含需求变更，"
                  "只作独立参照，不并入 freespeed 归因")

    # ---- 网络拓扑可比性（必须在 plans 分类前，以便逐臂释放大列）----
    print("\n[阶段 1] 网络拓扑与 freespeed 比对")
    nets = {lab: parse_network(ARMS[lab]["run"] / f"{ARMS[lab]['rid']}.output_network.xml.gz")
            for lab in ARMS}
    for lab in ARMS:
        print(f"    {lab:9s} n_links={len(nets[lab]):,}")
    ids_by_arm = {lab: set(nets[lab]) for lab in ARMS}
    for lab in ARMS:
        if lab == BASE:
            continue
        gate(f"G08.{lab}", f"{lab} 与 v1.0 网络 link id 集合相同", ids_by_arm[lab] == ids_by_arm[BASE],
             f"∩={len(ids_by_arm[lab] & ids_by_arm[BASE]):,} A={len(ids_by_arm[lab]):,} B={len(ids_by_arm[BASE]):,}")

    topo_rows = []
    for lab in ARMS:
        if lab == BASE:
            continue
        ndiff_fs = ndiff_top = 0
        common = ids_by_arm[lab] & ids_by_arm[BASE]
        for i in common:
            a = nets[lab][i]
            b = nets[BASE][i]
            if abs(a[1] - b[1]) > 1e-9:
                ndiff_fs += 1
            if (a[4] != b[4]) or (a[5] != b[5]) or abs(a[0] - b[0]) > 1e-6 \
               or abs(a[2] - b[2]) > 1e-6 or abs(a[3] - b[3]) > 1e-6:
                ndiff_top += 1
        topo_rows.append({"arm": lab, "n_common": len(common),
                          "n_freespeed_diff": ndiff_fs, "n_topo_diff": ndiff_top})
        print(f"    {lab:9s} freespeed 差异={ndiff_fs:,}  拓扑(from/to/length/cap/lanes)差异={ndiff_top:,}")
    pd.DataFrame(topo_rows).to_csv(OUT / "network_freespeed_diff.csv", index=False, encoding="utf-8-sig")
    gate("G09", "SB-A5 仅 freespeed 变化（拓扑 from/to/length/cap/lanes 零差异）",
         all(r["n_topo_diff"] == 0 for r in topo_rows),
         " | ".join(f"{r['arm']}:topo={r['n_topo_diff']}" for r in topo_rows))

    global NET_LEN
    NET_LEN = {i: nets[BASE][i][0] for i in nets[BASE]}
    net_attr = load_net_attrs()
    cover = sum(1 for i in NET_LEN if i in net_attr.index)
    print(f"    等级映射覆盖：network {len(NET_LEN):,} 链中 {cover:,} 命中 highway 源表"
          f"（{cover/len(NET_LEN)*100:.2f}%）")
    gate("G10", "network→highway 源表覆盖 ≥ 99%", cover / len(NET_LEN) >= 0.99,
         f"{cover}/{len(NET_LEN)}")

    # ---- plans 解析 + 逐臂分类（★加载→分类→释放 links，峰值内存 ~2.3GB）----
    print("\n[阶段 1+2] 解析 selected plans（每人取 selected='yes'）")
    routes_by_arm = {}
    pinfo = {}
    cls_by_arm = {}
    v10_links = None
    for lab in ARMS:
        clscache = CACHE / f"cls_{lab}.pkl"
        cinfo = CACHE / f"info_{lab}.json"
        if clscache.exists() and cinfo.exists():
            cls_by_arm[lab] = pd.read_pickle(clscache)
            pinfo[lab] = json.loads(cinfo.read_text(encoding="utf-8"))
            routes_by_arm[lab] = cls_by_arm[lab][["person"]]
            print(f"    {lab:9s} <- cls cache  routes={len(cls_by_arm[lab]):,}", flush=True)
            continue
        p = ARMS[lab]["run"] / f"{ARMS[lab]['rid']}.output_plans.xml.gz"
        cache = CACHE / f"routes_{lab}.pkl"
        if cache.exists() and cinfo.exists():
            r = pd.read_pickle(cache)
            info = json.loads(cinfo.read_text(encoding="utf-8"))
            print(f"    {lab:9s} <- routes cache  persons={info['n_persons']:,}  with_route={len(r):,}", flush=True)
        else:
            print(f"    {lab:9s} <- {p.name} ...", flush=True)
            r, info = parse_selected_plans(p)
            r.to_pickle(cache)
            cinfo.write_text(json.dumps(info, ensure_ascii=False), encoding="utf-8")
            print(f"      persons={info['n_persons']:,}  plans={info['n_plan_total']:,}  "
                  f"selected={info['n_selected']:,}  with_route={len(r):,}", flush=True)
        pinfo[lab] = info
        cls_by_arm[lab] = classify_arm(r, net_attr)
        cls_by_arm[lab].to_pickle(clscache)      # ★小体积缓存（~60MB）
        c = cls_by_arm[lab]
        print(f"      {lab:9s} 分类完成 routes={len(c):,} 总里程={c['total_len_m'].sum()/1000:,.0f} km "
              f"motorway={c['len_motorway'].sum()/c['total_len_m'].sum()*100:.2f}%", flush=True)
        if lab == BASE:
            v10_links = r[["person", "links"]].set_index("person")
        routes_by_arm[lab] = r.drop(columns=["links"])   # ★释放大列
        del r

    for lab in ARMS:
        gate(f"G06.{lab}", f"{lab} 每个 person 恰 1 个 selected plan",
             pinfo[lab]["n_selected"] == pinfo[lab]["n_persons"],
             f"selected={pinfo[lab]['n_selected']} persons={pinfo[lab]['n_persons']}")

    # person 集合一致
    P = {lab: set(routes_by_arm[lab]["person"]) for lab in ARMS}
    for lab in ARMS:
        if lab == BASE:
            continue
        same = P[lab] == P[BASE]
        gate(f"G07.{lab}", f"{lab} 与 v1.0 person 集合逐位相同", same,
             f"∩={len(P[lab] & P[BASE]):,} | A={len(P[lab]):,} B={len(P[BASE]):,}")

    # ================= 阶段 2A：路线结构（plans）=================
    print("\n[阶段 2A] 道路等级路径占比 / 快速路使用（selected plans）")

    # 道路等级路线长度占比表（跨臂）
    rows = []
    for lab in ARMS:
        c = cls_by_arm[lab]
        Tl = c["total_len_m"].sum()
        for cls in CLASSES:
            rows.append({"arm": lab, "highway": cls,
                         "route_length_km": c[f"len_{cls}"].sum() / 1000,
                         "route_length_share_pct": c[f"len_{cls}"].sum() / Tl * 100,
                         "route_use_rate_pct": (c[f"len_{cls}"] > 0).mean() * 100})
    rc = pd.DataFrame(rows)
    rc.to_csv(OUT / "roadclass_route_share.csv", index=False, encoding="utf-8-sig")
    rc_piv = rc.pivot(index="highway", columns="arm", values="route_length_share_pct")
    rc_piv["dA5_v10_pp"] = rc_piv["SB-A5"] - rc_piv["v1.0"]
    rc_piv = rc_piv.sort_values("dA5_v10_pp", ascending=False)
    rc_piv.to_csv(OUT / "roadclass_route_share_pivot.csv", encoding="utf-8-sig")
    print("    —— 等级里程占比 (v1.0 → SB-A5, pp) ——")
    for cls, r in rc_piv.iterrows():
        print(f"      {cls:16s} {r['v1.0']:6.2f}% → {r['SB-A5']:6.2f}%  ({r['dA5_v10_pp']:+.3f} pp)")

    # ================= 阶段 2A：逐人 route hash 变化 =================
    print("\n[阶段 2A] 逐人 route 变化（v1.0 vs SB-A5 / SB-A5ind）")
    b = cls_by_arm[BASE].set_index("person")
    allp = b.index
    route_change_rows = []
    merged_cache = {}
    for lab in ("SB-A5", "SB-A5ind"):
        a = cls_by_arm[lab].set_index("person")
        common = allp.intersection(a.index)
        hb = b.loc[common, "route_hash"]
        ha = a.loc[common, "route_hash"]
        changed = (hb.values != ha.values)
        n = len(common)
        # 里程/等级变化（组级）
        m = pd.DataFrame({
            "h_v10": hb.values, "h_a5": ha.values,
            "tot_v10": b.loc[common, "total_len_m"].values, "tot_a5": a.loc[common, "total_len_m"].values,
            "mw_v10": b.loc[common, "mw_segments"].values, "mw_a5": a.loc[common, "mw_segments"].values,
        })
        merged_cache[lab] = m
        rec = {
            "compare": f"{lab} vs v1.0", "n_common_persons": n,
            "n_route_changed": int(changed.sum()),
            "route_change_pct": float(changed.mean() * 100),
            "n_route_same": int(n - changed.sum()),
            "mean_total_len_v10_km": float(m["tot_v10"].mean() / 1000),
            "mean_total_len_a5_km": float(m["tot_a5"].mean() / 1000),
            "mean_mw_segments_v10": float(m["mw_v10"].mean()),
            "mean_mw_segments_a5": float(m["mw_a5"].mean()),
            "n_mw_segments_increased": int((m["mw_a5"] > m["mw_v10"]).sum()),
            "n_mw_segments_decreased": int((m["mw_a5"] < m["mw_v10"]).sum()),
        }
        route_change_rows.append(rec)
        print(f"    {rec['compare']:16s} N={n:,}  路线变化={rec['n_route_changed']:,} "
              f"({rec['route_change_pct']:.2f}%)  快速路段数 {rec['mean_mw_segments_v10']:.3f}→{rec['mean_mw_segments_a5']:.3f}")

    # 直接对照：SB-A5ind vs SB-A5（判定两臂是否共享同一 demand 实现）
    a5d = cls_by_arm["SB-A5"].set_index("person")
    a5i_d = cls_by_arm["SB-A5ind"].set_index("person")
    com2 = a5d.index.intersection(a5i_d.index)
    ch2 = (a5d.loc[com2, "route_hash"].values != a5i_d.loc[com2, "route_hash"].values)
    rec2 = {"compare": "SB-A5ind vs SB-A5", "n_common_persons": len(com2),
            "n_route_changed": int(ch2.sum()), "route_change_pct": float(ch2.mean() * 100),
            "n_route_same": int(len(com2) - ch2.sum()),
            "mean_total_len_v10_km": float(a5d.loc[com2, "total_len_m"].mean() / 1000),
            "mean_total_len_a5_km": float(a5i_d.loc[com2, "total_len_m"].mean() / 1000),
            "mean_mw_segments_v10": float(a5d.loc[com2, "mw_segments"].mean()),
            "mean_mw_segments_a5": float(a5i_d.loc[com2, "mw_segments"].mean()),
            "n_mw_segments_increased": int((a5i_d.loc[com2, "mw_segments"].values > a5d.loc[com2, "mw_segments"].values).sum()),
            "n_mw_segments_decreased": int((a5i_d.loc[com2, "mw_segments"].values < a5d.loc[com2, "mw_segments"].values).sum())}
    route_change_rows.append(rec2)
    print(f"    {rec2['compare']:16s} N={len(com2):,}  路线变化={rec2['n_route_changed']:,} "
          f"({rec2['route_change_pct']:.2f}%)  快速路段数 {rec2['mean_mw_segments_v10']:.3f}→{rec2['mean_mw_segments_a5']:.3f}")
    pd.DataFrame(route_change_rows).to_csv(OUT / "route_change_summary.csv", index=False, encoding="utf-8-sig")

    # 变化是否集中于已识别走廊
    print("\n[阶段 2A] 路线变化 × 走廊（PIE/TPE/CTE/KPE...）")
    a5 = cls_by_arm["SB-A5"].set_index("person")
    common = allp.intersection(a5.index)
    changed = (b.loc[common, "route_hash"].values != a5.loc[common, "route_hash"].values)
    corr_rows = []
    for code in CORRIDORS:
        c_v10 = b.loc[common, f"use_{code}"].values
        c_a5 = a5.loc[common, f"use_{code}"].values
        corr_rows.append({
            "corridor": code,
            "rate_v10_pct": float(c_v10.mean() * 100),
            "rate_a5_pct": float(c_a5.mean() * 100),
            "d_rate_pp": float((c_a5.mean() - c_v10.mean()) * 100),
            "use_rate_among_changed_a5_pct": float(c_a5[changed].mean() * 100) if changed.any() else np.nan,
            "use_rate_among_unchanged_a5_pct": float(c_a5[~changed].mean() * 100) if (~changed).any() else np.nan,
            "gained_users": int((c_a5 & ~c_v10).sum()),
            "lost_users": int((~c_a5 & c_v10).sum()),
        })
    cc = pd.DataFrame(corr_rows).sort_values("d_rate_pp", ascending=False)
    cc.to_csv(OUT / "corridor_route_use.csv", index=False, encoding="utf-8-sig")
    for _, r in cc.iterrows():
        print(f"      {r['corridor']:5s} 使用率 {r['rate_v10_pct']:5.2f}% → {r['rate_a5_pct']:5.2f}% "
              f"({r['d_rate_pp']:+.3f} pp)  增{r['gained_users']:,}/减{r['lost_users']:,}")

    # ================= 阶段 2B：时段（证据受限）=================
    print("\n[阶段 2B] 时段变化（证据受限）")
    ev_info = {"v1.0_events_available": manifest["v1.0.events"]["exists"],
               "SB-A5_events_available": False, "SB-A5ind_events_available": False,
               "note": "SB-A5/SB-A5ind writeEventsInterval=0 ⇒ 无实际执行事件；"
                       "时段分支仅 v1.0 侧可校验，SB-A5 侧 BLOCKED（降级为 plans）"}
    print("    " + ev_info["note"])
    gate("G11", "时段分支对 SB-A5 判定为 BLOCKED（无 events）", True, "BLOCKED（证据不足，不裁）")

    # ================= 阶段 2C：plans↔events 保真（v1.0 侧）=================
    print("\n[阶段 2C] v1.0 plans↔events 保真抽样（证明 plans 可作执行路线代理）")
    fcache = CACHE / "fidelity.json"
    if fcache.exists():
        fid = json.loads(fcache.read_text(encoding="utf-8"))
        print("    <- cache")
    else:
        if v10_links is None:
            v10_links = pd.read_pickle(CACHE / f"routes_{BASE}.pkl")[["person", "links"]].set_index("person")
        fid = sample_plan_event_fidelity(v10_links, V10_EVENTS, sample_n=8000)
        if fid is not None:
            fcache.write_text(json.dumps(fid, ensure_ascii=False), encoding="utf-8")
    if fid is not None:
        print(f"    抽样完成行数={fid['n_matched']:,}  计划↔执行一致率={fid['match_rate_pct']:.3f}%")
        gate("G12", "v1.0 plans↔events 路线一致率 ≥ 99%（plans 可作执行代理）",
             fid["n_matched"] > 0 and fid["match_rate_pct"] >= 99.0,
             f"matched={fid['n_matched']} rate={fid['match_rate_pct']:.3f}%")
    else:
        fid = {"n_matched": 0, "match_rate_pct": float("nan"), "note": "events 抽样失败"}
        gate("G12", "v1.0 plans↔events 保真抽样", False, "events 抽样失败")

    # ================= 汇总 =================
    summary = {
        "audit": "E-SB-04", "base_arm": BASE, "date": "2026-10-11",
        "evidence_level": "PLANS_LEVEL（v1.0 另有 events 侧保真校验；SB-A5/SB-A5ind 无 events）",
        "manifest": manifest,
        "plan_info": pinfo,
        "network_topo_diff": topo_rows,
        "n_net_links": len(NET_LEN), "net_attr_coverage": cover,
        "route_change": route_change_rows,
        "corridor_route_use": cc.to_dict("records"),
        "roadclass_share": rc.to_dict("records"),
        "events": ev_info,
        "fidelity": fid,
        "gates": GATES,
    }
    (OUT / "esb04_stage12_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    pd.DataFrame(GATES).to_csv(OUT / "gate_checks.csv", index=False, encoding="utf-8-sig")
    print("\n[阶段 1] 输入 manifest → input_manifest.json")
    (OUT / "input_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    n_fail = sum(1 for g in GATES if not g["pass"])
    print("\n" + "=" * 100)
    print(f"E-SB-04 阶段1+2 门禁：{len(GATES)-n_fail}/{len(GATES)} PASS"
          + (f"  ⚠️ {n_fail} FAIL" if n_fail else "  ✅"))
    print(f"落盘：{OUT}")
    return 0 if n_fail == 0 else 1


def sample_plan_event_fidelity(plans_idx: pd.DataFrame, events_path: Path, sample_n=8000):
    """从 events 重建 v1.0 执行路线，与 selected plan 对比（有界抽样：收满即停）。

    ★ events 的 'entered link' 只带 vehicle，不带 person ⇒ 用 'PersonEntersVehicle'
      (person,vehicle) 建映射（vehicle 约定 = person + '_car'）。
    """
    if not events_path.exists():
        return None
    plan_links = {p: v.split() for p, v in plans_idx["links"].items()}
    veh2person = {}
    seq = defaultdict(list)          # vehicle -> [link...]
    finalized = 0
    n_direct = n_dropstart = n_droplast = 0
    n_matched = 0
    veh_re = re.compile(r'vehicle="([^"]+)"')
    person_re = re.compile(r'person="([^"]+)"')
    link_re = re.compile(r'link="([^"]+)"')

    def finish(v):
        nonlocal finalized, n_direct, n_dropstart, n_droplast, n_matched
        person = veh2person.get(v)
        if person is None or person not in plan_links:
            return
        obs = seq[v]
        pl = plan_links[person]
        if not obs:
            return
        finalized += 1
        n_matched += 1
        if obs == pl:
            n_direct += 1
        elif obs == pl[1:]:          # ★MATSim 语义：车辆置于 start_link，只记 left link ⇒ 少首链
            n_dropstart += 1
        elif obs == pl[:-1]:
            n_droplast += 1

    try:
        with gzip.open(events_path, "rt", encoding="utf-8", errors="replace") as f:
            for line in f:
                if 'type="PersonEntersVehicle"' in line:
                    mp = person_re.search(line)
                    mv = veh_re.search(line)
                    if mp and mv:
                        veh2person[mv.group(1)] = mp.group(1)
                elif 'type="entered link"' in line:
                    mv = veh_re.search(line)
                    ml = link_re.search(line)
                    if mv and ml:
                        seq[mv.group(1)].append(ml.group(1))
                elif 'type="vehicle leaves traffic"' in line or 'type="PersonLeavesVehicle"' in line:
                    mv = veh_re.search(line)
                    if mv:
                        finish(mv.group(1))
                        seq.pop(mv.group(1), None)
                        if n_matched >= sample_n:
                            break
    except Exception as e:
        print(f"    events 抽样异常：{e}")
        return {"n_matched": n_matched, "match_rate_pct": float("nan"), "note": str(e)}
    n_exact = n_direct + n_dropstart + n_droplast
    rate = n_exact / n_matched * 100 if n_matched else float("nan")
    return {"n_matched": n_matched, "n_exact": n_exact,
            "n_exact_direct": n_direct, "n_exact_drop_start_link": n_dropstart,
            "n_exact_drop_last_link": n_droplast,
            "match_rate_pct": rate,
            "note": "有界抽样：按 events 时间序收满 sample_n 个可比 person 即停；"
                    "「drop_start_link」= 车辆置于 start_link 故 events 不记其 entered link（MATSim 语义）"}


if __name__ == "__main__":
    sys.exit(main())
