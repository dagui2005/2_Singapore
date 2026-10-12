#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""
esb05_events_exec_route.py — E-SB-05 阶段 3/4：events 完整性、person 关联、执行路线重建与对账
==============================================================================================
任务书 §2.2/§2.3：
  ② 事件完整性：events 完整可解析，并能通过 PersonEntersVehicle 将车辆关联到 person，
     再重建实际经过的有向 link 序列。
  ③ 路线对账：实际经过的 link 序列 vs selected plan；分清「实际执行路线 / 计划路线 /
     MATSim 对起始 link 的事件记录语义」。

★ 阶段 4 的执行级升级检验（回答任务书 §3）：
  在同一 population（236,044）与同一迭代（it.19）下，
  对比 v1.0 与 SB-A5_EVT19_CHECK 的**实际执行路线**：
    - 执行路线改变率（逐人 executed sequence hash 不等）
    - 执行路线的快速路里程份额（motorway + motorway_link）
    - 执行路线的走廊使用（PIE/TPE/…）
  ⇒ 把 E-SB-04 的「66.06% 计划路线改变 / motorway 份额 44.56%→47.25%」升级到执行级。

用法：
    python scripts/experiments/esb05_events_exec_route.py --tag NEW    # 扫新 run it.19 events
    python scripts/experiments/esb05_events_exec_route.py --tag V10    # 扫 v1.0 events
    python scripts/experiments/esb05_events_exec_route.py --compare    # 汇总判决并渲染

产物 → experiments/E-SB-05_exec_level_events/audit/
        _exec_cache/exec_<TAG>.pkl        逐人执行路线聚合（大件，不入 reports）
        _exec_cache/exec_<TAG>.meta.json
        esb05_events_integrity.json
        esb05_exec_route_compare.csv
        esb05_exec_route_gates.csv
        esb05_exec_route_summary.json
"""
from __future__ import annotations

import argparse
import array
import csv
import gzip
import hashlib
import json
import re
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(r"D:\Luan\2026-05\2_Singapore")
EXP = ROOT / "experiments" / "E-SB-05_exec_level_events"
AUDIT = EXP / "audit"
CACHE = AUDIT / "_exec_cache"
CACHE.mkdir(parents=True, exist_ok=True)

E2 = ROOT / "experiments" / "E-SB-02_night_freeflow"
NET_XML = E2 / "networks" / "network_SB-A5.xml.gz"          # 权威 length（m）
NET_SRC = ROOT / "reports" / "matsim_network" / "network_links_source_copy.csv"  # 权威 highway/name

TAGS = {
    "NEW": {"events": EXP / "outputs" / "SB-A5_EVT19_CHECK" / "ITERS" / "it.19" /
                      "SB-A5_EVT19_CHECK.19.events.xml.gz",
            "plans": EXP / "outputs" / "SB-A5_EVT19_CHECK" / "SB-A5_EVT19_CHECK.output_plans.xml.gz",
            "label": "SB-A5_EVT19_CHECK（执行级）"},
    "V10": {"events": ROOT / "matsim_viz_7_8" / "outputs" / "W01_events" / "W01_events.output_events.xml.gz",
            "plans": ROOT / "matsim_viz_7_8" / "outputs" / "W01_events" / "W01_events.output_plans.xml.gz",
            "label": "v1.0（执行级基线）"},
}

CLASSES = ["motorway", "motorway_link", "trunk", "trunk_link", "primary", "primary_link",
           "secondary", "secondary_link", "tertiary", "tertiary_link",
           "service", "unclassified", "residential"]
CORRIDORS = {
    "PIE": r"pan[- ]?island expressway", "TPE": r"tampines expressway",
    "CTE": r"central expressway", "KPE": r"kallang[- ]?paya lebar expressway",
    "KJE": r"kranji expressway", "AYE": r"ayer rajah expressway",
    "SLE": r"seletar expressway", "BKE": r"bukit timah expressway",
    "MCE": r"marina co[a-z]*tal expressway", "ECP": r"east coast parkway",
}
EXPECTED_N_PERSONS = 236044

# ---------------- 正则 ----------------
LINK_RE = re.compile(rb'<link\s+id="([^"]+)"\s+from="([^"]+)"\s+to="([^"]+)"\s+length="([^"]*)"')
PERSON_RE = re.compile(rb' person="([^"]+)"')
VEH_RE = re.compile(rb' vehicle="([^"]+)"')
LINKA_RE = re.compile(rb' link="([^"]+)"')
TYPE_RE = re.compile(rb' type="([^"]+)"')

P_PERSON = re.compile(r'<person\s+id="([^"]+)"')
P_PLAN = re.compile(r'<plan\b[^>]*selected="(yes|no)"')
P_ROUTE = re.compile(r'<route\s+type="links"[^>]*>(.*?)</route>')


# --------------------------------------------------------------------------
def build_link_index():
    """link_id → idx；返回 (ids, LEN, HW_CODE, CORR_CODE, hw_codes, corr_codes)。"""
    ids: list[str] = []
    lens: list[float] = []
    with gzip.open(NET_XML, "rb") as f:
        for line in f:
            if b"<link " not in line:
                continue
            m = LINK_RE.search(line)
            if m:
                ids.append(m.group(1).decode("utf-8"))
                lens.append(float(m.group(4)))
    idx = {lid: i for i, lid in enumerate(ids)}
    LEN = np.asarray(lens, dtype=np.float64)

    e = pd.read_csv(NET_SRC, encoding="utf-8-sig", low_memory=False,
                    usecols=["from_node", "to_node", "highway", "name"])
    e["matsim_link_id"] = "e" + e["from_node"].astype(str) + "_" + e["to_node"].astype(str)
    e = e.drop_duplicates("matsim_link_id")
    # ⚠️ pandas 3.0 的 str dtype 会把缺失值保留为 NA/float ⇒ 必须先 fillna("") 再 astype(str)
    hw_s = e["highway"].fillna("").astype(str).str.lower().str.strip()
    nm_s = e["name"].fillna("").astype(str).str.lower()
    hw_map = dict(zip(e["matsim_link_id"], hw_s))
    nm_map = dict(zip(e["matsim_link_id"], nm_s))

    hw_codes = ["UNKNOWN"] + CLASSES
    corr_codes = [""] + list(CORRIDORS)
    hw_ci = {c: i for i, c in enumerate(hw_codes)}
    corr_ci = {c: i for i, c in enumerate(corr_codes)}
    HW = np.zeros(len(ids), dtype=np.int8)
    CORR = np.zeros(len(ids), dtype=np.int8)
    for lid, i in idx.items():
        HW[i] = hw_ci.get(hw_map.get(lid, "UNKNOWN"), 0)
        nm = nm_map.get(lid, "")
        if not isinstance(nm, str):
            nm = ""
        for code, pat in CORRIDORS.items():
            if re.search(pat, nm):
                CORR[i] = corr_ci[code]
                break
    return ids, idx, LEN, HW, CORR, hw_codes, corr_codes


def parse_selected_plans(path: Path, idx: dict) -> tuple[dict, dict]:
    """返回 {person: array('i')} 与统计。route 内容含 start_link 作首元素（实测 XML 语义）。"""
    routes: dict[str, array.array] = {}
    cur, sel = None, False
    cur_nodes: list[int] = []
    n_persons = n_plans = n_sel = 0
    pend = False
    with gzip.open(path, "rt", encoding="utf-8", errors="replace") as f:
        for line in f:
            if "<person " in line:
                if cur is not None and cur_nodes:
                    routes[cur] = array.array("i", cur_nodes)
                m = P_PERSON.search(line)
                cur = m.group(1) if m else None
                cur_nodes = []
                n_persons += 1
                continue
            if "<plan " in line or "<plan>" in line:
                m = P_PLAN.search(line)
                if m:
                    sel = (m.group(1) == "yes")
                    n_plans += 1
                    if sel:
                        n_sel += 1
                continue
            if sel and ("type=\"links\"" in line or pend):
                m = P_ROUTE.search(line)
                if m:
                    body = m.group(1).strip()
                    cur_nodes.extend(idx[x] for x in body.split() if x in idx)
                elif "type=\"links\"" in line:
                    pend = True
    if cur is not None and cur_nodes:
        routes[cur] = array.array("i", cur_nodes)
    return routes, {"n_persons": n_persons, "n_plan_total": n_plans, "n_selected": n_sel,
                    "n_routes": len(routes)}


def scan_events(events_path: Path, idx: dict, LEN, HW, CORR, hw_codes, corr_codes,
                plan_routes: dict | None, log_every=8, max_bytes: int = 0):
    """单遍扫描：事件类型计数 + 逐人执行路线聚合 + 与 selected plan 的对账。"""
    types = Counter()
    veh2person: dict[bytes, bytes] = {}
    seq: dict[bytes, array.array] = {}
    out: dict[str, dict] = {}

    n_persons_seen = 0
    n_legs = 0
    fid = Counter()

    t0 = time.time()
    dl = 0
    last_log = t0

    def person_rec(pid: str) -> dict:
        r = out.get(pid)
        if r is None:
            r = {"n_legs": 0, "n_links": 0, "total_len_m": 0.0,
                 **{f"len_{c}": 0.0 for c in CLASSES},
                 **{f"len_corr_{c}": 0.0 for c in CORRIDORS},
                 **{f"use_{c}": 0 for c in CORRIDORS},
                 "len_express_m": 0.0, "len_surface_m": 0.0,
                 "first_link": "", "last_link": "",
                 "_h": hashlib.md5(), "fid": ""}
            out[pid] = r
        return r

    def finalize_leg(veh: bytes, complete: bool = True):
        nonlocal n_legs
        pid_b = veh2person.get(veh)
        if pid_b is None:
            return
        a = seq.get(veh)
        if not a or len(a) == 0:
            return
        seq.pop(veh, None)
        if not complete:
            fid["unfinished_excluded"] += 1
            return
        pid = pid_b.decode("utf-8")
        r = person_rec(pid)
        arr = np.frombuffer(a, dtype=np.int32)
        L = LEN[arr]
        hwc = HW[arr]
        ccc = CORR[arr]
        r["n_legs"] += 1
        r["n_links"] += int(len(arr))
        r["total_len_m"] += float(L.sum())
        for ci, cname in enumerate(hw_codes):
            if ci == 0:
                continue
            m = (hwc == ci)
            if m.any():
                r[f"len_{cname}"] += float(L[m].sum())
        for ci, cname in enumerate(corr_codes):
            if ci == 0:
                continue
            m = (ccc == ci)
            if m.any():
                r[f"len_corr_{cname}"] += float(L[m].sum())
                r[f"use_{cname}"] = 1
        m_mw = (hwc == hw_codes.index("motorway")) | (hwc == hw_codes.index("motorway_link"))
        r["len_express_m"] += float(L[m_mw].sum())
        r["len_surface_m"] += float(L[~m_mw].sum())
        if not r["first_link"]:
            r["first_link"] = idx_inv.get(int(arr[0]), "")
        r["last_link"] = idx_inv.get(int(arr[-1]), "")
        r["_h"].update(arr.tobytes())
        n_legs += 1

        # ---- 与 selected plan 对账（逐 leg）----
        if plan_routes is not None and pid in plan_routes:
            pl = plan_routes[pid]
            npl = len(pl)
            if len(arr) == npl and np.array_equal(arr, pl):
                fid["direct"] += 1
            elif len(arr) == npl - 1 and npl >= 1 and np.array_equal(arr, pl[1:]):
                fid["drop_start_link"] += 1
            elif len(arr) == npl - 1 and np.array_equal(arr, pl[:-1]):
                fid["drop_last_link"] += 1
            else:
                fid["mismatch"] += 1
        elif plan_routes is not None:
            fid["person_not_in_plans"] += 1

    def _handle(block: bytes):
        nonlocal n_persons_seen
        for line in block.split(b"\n"):
            if b'type="' not in line:
                continue
            mt = TYPE_RE.search(line)
            if not mt:
                continue
            t = mt.group(1)
            types[t] += 1
            if t == b"entered link":
                mv = VEH_RE.search(line)
                ml = LINKA_RE.search(line)
                if mv and ml:
                    lid = ml.group(1).decode("utf-8")
                    i = idx.get(lid)
                    if i is None:
                        continue
                    v = mv.group(1)
                    a = seq.get(v)
                    if a is None:
                        a = array.array("i"); seq[v] = a
                    a.append(i)
            elif t == b"PersonEntersVehicle":
                mp = PERSON_RE.search(line); mv = VEH_RE.search(line)
                if mp and mv:
                    if mv.group(1) not in veh2person:
                        n_persons_seen += 1
                    veh2person[mv.group(1)] = mp.group(1)
                    seq[mv.group(1)] = array.array("i")
            elif t == b"PersonLeavesVehicle":
                mv = VEH_RE.search(line)
                if mv:
                    finalize_leg(mv.group(1))

    with gzip.open(events_path, "rb") as f:
        buf = b""
        while True:
            chunk = f.read(1 << 23)
            if not chunk:
                if buf:
                    _handle(buf)
                break
            dl += len(chunk)
            buf += chunk
            if max_bytes and dl >= max_bytes:
                if buf:
                    _handle(buf)
                break
            nl = buf.rfind(b"\n")
            if nl < 0:
                continue
            block, buf = buf[:nl], buf[nl + 1:]
            _handle(block)
            now = time.time()
            if now - last_log > 20:
                print(f"    … {dl/2**30:.2f} GiB 解开 / legs={n_legs:,} / persons={len(out):,}"
                      f" / {dl/2**20/max(1e-9,(now-t0)):.1f} MB/s", flush=True)
                last_log = now

    # 收尾：尾部未完成的车辆**不得**进入聚合与对账（否则系统性低估里程/份额）
    for v in list(seq.keys()):
        finalize_leg(v, complete=False)
    return types, out, fid, {"decompressed_bytes": dl, "elapsed_sec": round(time.time() - t0, 1),
                            "n_person_enter_events": n_persons_seen, "n_legs_finalized": n_legs,
                            "n_unfinished_excluded": fid.get("unfinished_excluded", 0)}


idx_inv: dict[int, str] = {}


def run_tag(tag: str, events_override: str | None = None, plans_override: str | None = None,
            max_bytes: int = 0, suffix: str = "") -> int:
    global idx_inv
    t0 = time.time()
    spec = dict(TAGS[tag])
    if events_override:
        spec["events"] = Path(events_override)
    if plans_override:
        spec["plans"] = Path(plans_override)
    print("=" * 100)
    print(f"E-SB-05 阶段 3/4：扫描 events（{spec['label']}）"
          + (f"  [max_bytes={max_bytes:,}]" if max_bytes else ""))
    print("=" * 100)
    for p in (spec["events"], spec["plans"]):
        if not Path(p).exists():
            print(f"[ABORT] 缺文件：{p}")
            return 3
    ids, idx, LEN, HW, CORR, hw_codes, corr_codes = build_link_index()
    idx_inv = {i: s for s, i in idx.items()}
    print(f"[net] links={len(ids):,}  LEN 合计={LEN.sum()/1000:,.1f} km")
    plans, pstat = parse_selected_plans(spec["plans"], idx)
    print(f"[plan] {pstat}")

    types, out, fid, info = scan_events(spec["events"], idx, LEN, HW, CORR,
                                        hw_codes, corr_codes, plans, max_bytes=max_bytes)
    print(f"[events] types={ {k.decode(): v for k, v in types.most_common(12)} }")
    print(f"[events] {info}")

    # 落盘（去除不可序列化的 md5 对象）
    rows = []
    for pid, r in out.items():
        d = {k: v for k, v in r.items() if k != "_h"}
        d["person"] = pid
        d["exec_hash"] = r["_h"].hexdigest()
        rows.append(d)
    df = pd.DataFrame(rows)
    tname = tag + suffix
    df.to_pickle(CACHE / f"exec_{tname}.pkl")
    meta = {"tag": tname, "label": spec["label"], "events": str(spec["events"]),
            "plans": str(spec["plans"]), "n_persons_in_events": len(df),
            "event_types": {k.decode(): v for k, v in types.items()},
            "plan_stats": pstat, "fidelity": dict(fid), "scan_info": info,
            "max_bytes": max_bytes, "scan_elapsed_sec": round(time.time() - t0, 1)}
    (CACHE / f"exec_{tname}.meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2),
                                                   encoding="utf-8")
    print(f"[out] {CACHE/f'exec_{tname}.pkl'}  rows={len(df):,}  用时 {time.time()-t0:.1f}s")
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", choices=list(TAGS))
    ap.add_argument("--events-path")
    ap.add_argument("--plans-path")
    ap.add_argument("--max-bytes", type=int, default=0)
    ap.add_argument("--suffix", default="")
    ap.add_argument("--compare", action="store_true")
    a = ap.parse_args()
    if a.tag:
        sys.exit(run_tag(a.tag, a.events_path, a.plans_path, a.max_bytes, a.suffix))
    print("需要 --tag NEW|V10 或 --compare")
    sys.exit(2)
