#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Step 7.9G-1 — 端点/接入子系统「就地吸收」机制审计 · R0（零仿真 / 只读）

边界：不跑 MATSim、不改任何既有产物、不动 service 参数。
读 7 件冻结输入（§2）+ 4 件只读对照物（§3），回答 A1–A6（+A7 events 交叉校验），
落 16 件产物 + prereg。

运行：
    python audit_endpoint_access_absorption_7_9g1.py
    python audit_endpoint_access_absorption_7_9g1.py --out <dir> --ref-dir <dir>
"""
from __future__ import annotations

import argparse
import ast
import gzip
import hashlib
import json
import math
import re
import sys
import time
import zlib
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
ROOT = Path(r"D:\Luan\2026-05\2_Singapore")
OUT_DEFAULT = ROOT / "reports" / "endpoint_access_absorption_7_9g1"
REF_DEFAULT = ROOT / "reports" / "service_delay_mechanism_7_9g0"

STEP_ID = "7.9G-1"
STATUS_READY = "ENDPOINT_ACCESS_R0_READY"
STATUS_BLOCKED = "ENDPOINT_ACCESS_R0_BLOCKED"

PREREG_NAME = "PREREG_7_9G1.md"
PREREG_REL = "reports/endpoint_access_absorption_7_9g1/" + PREREG_NAME
PREREG_SHA = "4e7ffa3c90d47eaceff07c0f4a3af45dd039a0ccd2f49f8a9f751ceb73aad2ea"
PREREG_BYTES = 17536

# §2 冻结输入
INPUTS: dict[str, tuple[str, int, str]] = {
    "pop": (
        "matsim_final_7_6h/populations/pop_W01/population_lambda_0p075.xml.gz",
        8930574,
        "e96ed83ff59c0f5ecb50c9d9ff2d42a4b4bdbebf2bbfe81a1e0604fb94921fbd",
    ),
    "plans": (
        "matsim_final_7_6h/outputs/W01_rc_min/W01_rc_min.output_plans.xml.gz",
        215827261,
        "2aee1ba25a8416c986d09a8fb8f502de0dc6ace18e6863119c9959c45bbf1210",
    ),
    "events": (
        "matsim_viz_7_8/outputs/W01_events/W01_events.output_events.xml.gz",
        1694011331,
        "c9b61fba06d8a9b07b5ff27d6ccb92e996f0d74833e8bb0233b8ed942a5a3b98",
    ),
    "ls_final": (
        "matsim_final_7_6h/outputs/W01_rc_min/ITERS/it.19/W01_rc_min.19.linkstats.txt.gz",
        22629291,
        "b842b93a92f41c81248922078ebc68fdbe5ddc88f70086ccfd32bf955f0c1949",
    ),
    "ls_viz_ref": (
        "matsim_viz_7_8/outputs/W01_events/ITERS/it.19/W01_events.19.linkstats.txt.gz",
        22629291,
        "b842b93a92f41c81248922078ebc68fdbe5ddc88f70086ccfd32bf955f0c1949",
    ),
    "net_links_runtime": (
        "matsim_viz_7_8/outputs/W01_events/W01_events.output_links.csv.gz",
        14753288,
        "b65edfd5a59f233bb2e8d83384dbe07650dadbdae929ed6a378c0e3af0a6c5c9",
    ),
    "src_copy": (
        "reports/matsim_network/network_links_source_copy.csv",
        52670157,
        "b5265e5978608e7337712922b67f455b8c86c42c204ccc32a742da48180de9c6",
    ),
}
# §3 只读对照物（相对 REF_DEFAULT）
REFS: dict[str, tuple[str, int, str]] = {
    "g0_summary": (
        "g0_summary.json", 522,
        "d8c0b2f0c139005731de63b04ffee19be8265d7853e3839d2c5ec0ce9ab1166a",
    ),
    "g0_concentration": (
        "g0_service_concentration.csv", 194,
        "4898adcf77f90e95b107afab8d251026bd4aed12df990071de9268e0bd81bfed",
    ),
    "g0_faces": (
        "g0_exposure_faces.csv", 252,
        "61bb9eef77004e49732472d3b8e54891b7c597e1ec7dcf7e508cafd75b3abba8",
    ),
    "g0_verdicts": (
        "g0_verdicts.csv", 1207,
        "38c898f500a7219e60ca0b56aafd74d7fc5181b082a4aad5c037710c78211b8f",
    ),
}

# ---------------------------------------------------------------------------
READ_HOURS = ["7-8", "8-9", "9-10", "10-11"]
SIM_WINDOW = "8-9"
REQUIRED_LINKSTATS_FIELDS = [
    "LINK", "LENGTH", "FREESPEED", "CAPACITY",
    "HRS7-8avg", "TRAVELTIME7-8avg",
    "HRS8-9avg", "TRAVELTIME8-9avg",
    "HRS9-10avg", "TRAVELTIME9-10avg",
    "HRS10-11avg", "TRAVELTIME10-11avg",
]
LINKSTATS_EXPECTED_COLS = 154

SERVICE = "service"
SERVICE_UNIT_CAP = 400
UNIT_CAP: dict[str, float] = {
    "motorway": 1900.0, "motorway_link": 1700.0,
    "trunk": 1800.0, "trunk_link": 1600.0,
    "primary": 1500.0, "primary_link": 1300.0,
    "secondary": 1200.0, "secondary_link": 1100.0,
    "tertiary": 900.0, "tertiary_link": 900.0,
    "residential": 700.0, "unclassified": 600.0,
    "service": SERVICE_UNIT_CAP,
}
MAINLINE_SET = {
    "motorway", "motorway_link", "trunk", "trunk_link",
    "primary", "primary_link", "secondary", "secondary_link",
}
LOCAL_SET = {"service", "residential"}

REF_TOTAL_DELAY_G0 = 4778.77366611111
REF_SERVICE_SHARE_G0 = 94.35657888849315
CANON_REL_TOL = 1e-6
TRIPLE_TOL = 1e-9

STORAGE_DIVISOR = 7.5          # MATSim 队列储存约定：length * permlanes / 7.5
A1_ENRICH_MIN = 1.5
A2_FACTOR = 2.0
A4_SAT_MIN = 0.50
A4_CELL_STORAGE_MAX = 2.0
A5_LOCAL_MIN = 0.05
A6_DOMINANT_MIN = 0.50
SAT_VC = 0.9999
TOP_K = 12

V_A1 = {"ENRICHED_ON_SERVICE", "PROPORTIONAL_TO_MILEAGE"}
V_A2 = {"ENDPOINT_LOCALIZED", "POSITION_PROPORTIONAL"}
V_A3 = {"NOT_MAINLINE_QUEUE", "MAINLINE_QUEUE_SUSPECTED"}
V_A4 = {"FLOW_CAPACITY_BOUND", "STORAGE_CELL_BOUND", "NEITHER_BOUND"}
V_A5 = {"LOCAL_CIRCULATION_PRESENT", "NEGLIGIBLE"}
V_A6 = {"MAINLINE_QUEUE_DOMINANT", "MIDROUTE_THROUGH_DOMINANT",
        "SUBCELL_STORAGE_DOMINANT", "ENDPOINT_ABSORPTION_DOMINANT",
        "MIXED_NO_SINGLE_DOMINANT"}

# ---------------------------------------------------------------------------
OUTPUT_NAMES = [
    "g1_endpoint_snapping.csv",
    "g1_route_position_profile.csv",
    "g1_endpoint_service_split.csv",
    "g1_mainline_adjacency.csv",
    "g1_storage_buckets.csv",
    "g1_binding_diagnostics.csv",
    "g1_local_circulation.csv",
    "g1_concentration_detail.csv",
    "g1_events_trace.csv",
    "g1_exposure_faces.csv",
    "g1_verdicts.csv",
    "g1_checks.csv",
    "g1_closure_check.csv",
    "g1_input_manifest.json",
    "g1_summary.json",
    "STEP7_9G1_REPORT.md",
]
CHECKS_NAME = "g1_checks.csv"
MANIFEST_NAME = "g1_input_manifest.json"
CLOSURE_NAME = "g1_closure_check.csv"
SUMMARY_NAME = "g1_summary.json"
REPORT_NAME = "STEP7_9G1_REPORT.md"
WRITEBACK_EXCLUDED = {CHECKS_NAME, MANIFEST_NAME, CLOSURE_NAME}
ARTIFACT_NAMES = OUTPUT_NAMES + [PREREG_NAME]

REQUIRED_COLS: dict[str, list[str]] = {
    "g1_endpoint_snapping.csv": ["face", "road_type", "weighted_endpoints", "share_pct", "n_links"],
    "g1_route_position_profile.csv": ["road_type", "first", "last", "mid", "total", "endpoint_share_pct"],
    "g1_endpoint_service_split.csv": ["group", "n_links", "length_km", "vol", "delay_corr_h",
                                      "delay_share_service_pct", "vol_share_service_pct", "per_veh_delay_s"],
    "g1_mainline_adjacency.csv": ["group", "n_links", "vol", "delay_corr_h", "delay_share_total_pct"],
    "g1_storage_buckets.csv": ["bucket", "n_links", "vol", "delay_h", "delay_share_pct", "storage_med_veh"],
    "g1_binding_diagnostics.csv": ["metric", "value", "note"],
    "g1_local_circulation.csv": ["metric", "value"],
    "g1_concentration_detail.csv": ["rank", "link", "road_type", "length_m", "permlanes", "cap_flow",
                                    "storage_veh", "vol", "tt_s", "delay_corr_h", "delay_share_total_pct",
                                    "n_first", "n_last", "n_mid", "endpoint_weight"],
    "g1_events_trace.csv": ["link", "n_enter", "n_leave", "n_first_link", "cap_flow",
                            "cap_headway_s", "dwell_p50_s", "dwell_p90_s", "dwell_max_s",
                            "headway_p50_s", "ff_s"],
    "g1_exposure_faces.csv": ["face", "service_value", "total_value", "share_pct"],
    "g1_verdicts.csv": ["question", "verdict", "rule", "evidence"],
}

STATUS: dict = {"checks_rows": []}


# ===========================================================================
def sha256_file(p: Path, chunk: int = 1 << 22) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        while True:
            b = f.read(chunk)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


# ---------------------------------------------------------------------------
def preflight_inputs() -> tuple[dict, list[str]]:
    errs: list[str] = []
    info: dict = {"inputs": {}, "refs": {}}
    for name, (rel, size, sha) in INPUTS.items():
        p = ROOT / rel
        rec = {"path": rel, "exists": p.exists()}
        if not p.exists():
            errs.append(f"missing_input:{name}")
            info["inputs"][name] = rec
            continue
        rec["size"] = p.stat().st_size
        rec["sha256"] = sha256_file(p)
        rec["size_ok"] = rec["size"] == size
        rec["sha_ok"] = rec["sha256"] == sha
        if not rec["size_ok"]:
            errs.append(f"input_size_mismatch:{name}")
        if not rec["sha_ok"]:
            errs.append(f"input_sha_mismatch:{name}")
        info["inputs"][name] = rec
    return info, errs


def preflight_refs(ref_dir: Path) -> tuple[dict, list[str]]:
    errs: list[str] = []
    out: dict = {}
    for name, (rel, size, sha) in REFS.items():
        p = ref_dir / rel
        rec = {"path": str(p), "exists": p.exists()}
        if not p.exists():
            errs.append(f"missing_ref:{name}")
            out[name] = rec
            continue
        rec["size"] = p.stat().st_size
        rec["sha256"] = sha256_file(p)
        rec["sha_ok"] = rec["sha256"] == sha
        if not rec["sha_ok"]:
            errs.append(f"ref_sha_mismatch:{name}")
        out[name] = rec
    return out, errs


def preflight_linkstats_header() -> tuple[list[str], list[str]]:
    errs: list[str] = []
    p = ROOT / INPUTS["ls_final"][0]
    if not p.exists():
        return [], ["missing_input:ls_final"]
    hdr = pd.read_csv(p, sep="\t", nrows=0).columns.tolist()
    if len(hdr) != LINKSTATS_EXPECTED_COLS:
        errs.append(f"linkstats_cols={len(hdr)}!= {LINKSTATS_EXPECTED_COLS}")
    missing = [c for c in REQUIRED_LINKSTATS_FIELDS if c not in hdr]
    if missing:
        errs.append(f"linkstats_missing:{missing}")
    return hdr, errs


# ---------------------------------------------------------------------------
def load_net() -> pd.DataFrame:
    ls_cols = ["LINK", "LENGTH", "FREESPEED", "CAPACITY"] + \
              [f"HRS{h}avg" for h in READ_HOURS] + [f"TRAVELTIME{h}avg" for h in READ_HOURS]
    net = pd.read_csv(ROOT / INPUTS["net_links_runtime"][0], sep=";",
                      usecols=["link", "length", "freespeed", "capacity", "lanes"])
    src = pd.read_csv(ROOT / INPUTS["src_copy"][0], usecols=["from_node", "to_node", "highway"])
    src["link"] = "e" + src["from_node"].astype(str) + "_" + src["to_node"].astype(str)
    src = src.rename(columns={"highway": "road_type"})
    ls = pd.read_csv(ROOT / INPUTS["ls_final"][0], sep="\t", usecols=ls_cols, low_memory=False)
    ls = ls.rename(columns={"LINK": "link"})
    m = net.merge(src[["link", "road_type"]], on="link", how="left")
    m = m.merge(ls, on="link", how="left")
    m["ff_s"] = m["length"] / m["freespeed"]
    m["ff_ceil_s"] = np.ceil(m["ff_s"] - 1e-9)
    v = m[f"HRS{SIM_WINDOW}avg"].fillna(0.0).to_numpy(float)
    tt = m[f"TRAVELTIME{SIM_WINDOW}avg"].fillna(0.0).to_numpy(float)
    ffc = m["ff_ceil_s"].to_numpy(float)
    ffs = m["ff_s"].to_numpy(float)
    m["delay_corr_h"] = np.where(v > 0, v * np.maximum(0.0, tt - ffc) / 3600.0, 0.0)
    m["delay_raw_h"] = np.where(v > 0, v * np.maximum(0.0, tt - ffs) / 3600.0, 0.0)
    m["vol"] = v
    m["tt_s"] = tt
    m["storage_veh"] = m["length"].to_numpy(float) * m["lanes"].fillna(1.0).to_numpy(float) / STORAGE_DIVISOR
    m["vc_flow"] = np.where(m["capacity"].to_numpy(float) > 0,
                            v / np.maximum(m["capacity"].to_numpy(float), 1e-9), np.nan)
    m["vc_storage"] = np.where(m["storage_veh"].to_numpy(float) > 0,
                               v / np.maximum(m["storage_veh"].to_numpy(float), 1e-9), np.nan)
    return m, ls_cols


# ---------------------------------------------------------------------------
def load_population() -> dict:
    """返回 home/work 的加权端点强度与计数 + person→端点链 映射。"""
    act = re.compile(r'<activity type="(\w+)" link="([^"]+)"')
    efr = re.compile(r'name="expansionFactor"[^>]*>([^<]*)<')
    pidre = re.compile(r'<person id="([^"]+)"')
    home_w: dict[str, float] = defaultdict(float)
    work_w: dict[str, float] = defaultdict(float)
    home_c: Counter = Counter()
    work_c: Counter = Counter()
    home_p: dict[str, str] = {}
    work_p: dict[str, str] = {}
    n = 0
    bad = 0
    sum_ef = 0.0
    cur_ef = 0.0
    cur_pid = ""
    cur: dict[str, str] = {}
    with gzip.open(ROOT / INPUTS["pop"][0], "rt", encoding="utf-8") as fh:
        for line in fh:
            if "<person " in line:
                cur = {}
                n += 1
                pm = pidre.search(line)
                cur_pid = pm.group(1) if pm else ""
            elif "expansionFactor" in line:
                m = efr.search(line)
                cur_ef = float(m.group(1)) if m else 0.0
            elif "<activity " in line:
                m = act.search(line)
                if m:
                    cur[m.group(1)] = m.group(2)
            elif "</person>" in line:
                sum_ef += cur_ef
                h, w = cur.get("home"), cur.get("work")
                if h is None or w is None:
                    bad += 1
                else:
                    home_w[h] += cur_ef
                    work_w[w] += cur_ef
                    home_c[h] += 1
                    work_c[w] += 1
                    if cur_pid:
                        home_p[cur_pid] = h
                        work_p[cur_pid] = w
    return {"n": n, "bad": bad, "sum_ef": sum_ef,
            "home_w": dict(home_w), "work_w": dict(work_w),
            "home_c": dict(home_c), "work_c": dict(work_c),
            "home_p": home_p, "work_p": work_p}


# ---------------------------------------------------------------------------
def scan_plans(cls_b: dict, target_links: set) -> dict:
    """单遍扫描选中计划：位置剖面 + 契约匹配 + top-K 位置剖面。

    ⛔ 只取 selected="yes" 的计划。
    """
    tgt_b = {k.encode(): k for k in target_links}
    pos_first: Counter = Counter()
    pos_last: Counter = Counter()
    pos_mid: Counter = Counter()
    svc_first = svc_last = svc_mid = 0
    nroute = 0
    nlocal = 0
    len_hist: Counter = Counter()
    len_sum = 0
    tgt_pos = {k: Counter() for k in target_links}

    data = gzip.open(ROOT / INPUTS["plans"][0], "rb").read()
    parts = data.split(b"<person ")
    del data
    # ⛔ 注意：data.split(b"<person ") 已吃掉 "<person " 前缀，故 pb 以 id="..." 开头
    pidre = re.compile(rb'\A\s*id="([^"]+)"')
    attrre = re.compile(rb'(start_link|end_link)="([^"]*)"')
    OPEN, CLOSE, GT = b"<route", b"</route>", b">"
    loc_b = {k: (1 if v in LOCAL_SET else 0) for k, v in cls_b.items()}
    cnt_h = cnt_w = cnt_cmp = 0

    for pb in parts[1:]:
        sel_body = None
        for sg in pb.split(b"<plan "):
            if b'selected="yes"' in sg:
                sel_body = sg.split(b"</plan>")[0]
                break
        if sel_body is None:
            continue
        pos_p = 0
        first_r = None
        last_r = None
        while True:
            i = sel_body.find(OPEN, pos_p)
            if i < 0:
                break
            gt = sel_body.find(GT, i)
            if gt < 0:
                break
            cl = sel_body.find(CLOSE, gt + 1)
            if cl < 0:
                break
            tag = sel_body[i:gt]
            content = sel_body[gt + 1:cl]
            pos_p = cl + len(CLOSE)
            s = e = b""
            for mm in attrre.finditer(tag):
                if mm.group(1) == b"start_link":
                    s = mm.group(2)
                else:
                    e = mm.group(2)
            if first_r is None:
                first_r = s
            last_r = e
            links = content.split()
            n = len(links)
            if n == 0:
                continue
            nroute += 1
            len_hist[min(n, 600)] += 1
            len_sum += n
            c0 = cls_b.get(links[0], "?")
            pos_first[c0] += 1
            if c0 == SERVICE:
                svc_first += 1
            if n > 1:
                cl_c = cls_b.get(links[-1], "?")
                pos_last[cl_c] += 1
                if cl_c == SERVICE:
                    svc_last += 1
            if n > 2:
                pos_mid.update(map(cls_b.get, links[1:-1]))
            if all(map(loc_b.get, links)):
                nlocal += 1
            if tgt_b and any(map(tgt_b.__contains__, links)):
                for idx, x in enumerate(links):
                    dk = tgt_b.get(x)
                    if dk is None:
                        continue
                    if idx == 0:
                        tgt_pos[dk]["first"] += 1
                    elif idx == n - 1:
                        tgt_pos[dk]["last"] += 1
                    else:
                        tgt_pos[dk]["mid"] += 1
        if first_r is None:
            continue
        pm = pidre.search(pb)
        pid = pm.group(1).decode() if pm else ""
        cnt_cmp += 1
        cnt_h += (CONTRACT["home"].get(pid) == first_r.decode())
        cnt_w += (CONTRACT["work"].get(pid) == last_r.decode())
    return {"pos_first": dict(pos_first), "pos_last": dict(pos_last), "pos_mid": dict(pos_mid),
            "svc_first": svc_first, "svc_last": svc_last, "svc_mid": int(pos_mid.get(SERVICE, 0)),
            "nroute": nroute, "nlocal": nlocal, "len_hist": dict(len_hist),
            "len_sum": len_sum, "tgt_pos": {k: dict(v) for k, v in tgt_pos.items()},
            "cnt_cmp": cnt_cmp, "cnt_h": cnt_h, "cnt_w": cnt_w}


# ---------------------------------------------------------------------------
def events_trace(target_links: list[str], meta: dict) -> dict:
    """单遍流式扫描 events，仅抽取目标链的 entered/left/departure 事件。

    性能要点（实测）：
      ① 用 `zlib.decompressobj(31)` 直读原始 .gz —— 纯解压在 C 级约 348 MB/s，
         而 `gzip` 模块同文件仅约 33 MB/s（本机实测 447s vs 42s）；
      ② 预编译「仅命中目标链且类型受限」的正则，单遍 finditer —— 使 Python 级
         迭代从「全事件数(1.63e8)」降到「目标事件数(≈2.4e4)」。
    两者合计把 14.75 GB 事件扫描从 666s 压到 ~181s。
    """
    tgt_alt = b"|".join(re.escape(k.encode("utf-8")) for k in target_links)
    THIT = re.compile(
        rb'<event time="([0-9.]+)" type="(entered link|left link|departure)"'
        rb'[^>]*?link="(' + tgt_alt + rb')"[^>]*?/?>')
    vehre = re.compile(rb'(?:vehicle|person)="([^"]+)"')
    ent: dict[str, list] = {k: [] for k in target_links}
    lea: dict[str, list] = {k: [] for k in target_links}
    dpt: Counter = Counter()
    nbytes = 0
    n_gz = 0
    n_hit = 0
    buf = b""
    dec = zlib.decompressobj(31)  # 31 = zlib + gzip wrapper
    with open(ROOT / INPUTS["events"][0], "rb") as fh:
        while True:
            c = fh.read(1 << 22)
            if not c:
                break
            n_gz += len(c)
            chunk = dec.decompress(c)
            if buf:
                chunk = buf + chunk
                buf = b""
            last = chunk.rfind(b"\n")
            if last < 0:
                buf = chunk
                continue
            body = chunk[:last]
            buf = chunk[last + 1:]
            nbytes += len(body)
            if not body:
                continue
            for mm in THIT.finditer(body):
                tm = float(mm.group(1))
                et = mm.group(2)
                k = mm.group(3).decode("utf-8")
                tag = mm.group(0)
                vm = vehre.search(tag)
                v = vm.group(1).decode("utf-8") if vm else ""
                n_hit += 1
                if et == b"entered link":
                    ent[k].append((tm, v))
                elif et == b"left link":
                    lea[k].append((tm, v))
                else:
                    dpt[k] += 1
    out = []
    for k in target_links:
        E, L = ent[k], lea[k]
        dwell = []
        lmap = {v: t for t, v in L}
        for t, v in E:
            if v in lmap and lmap[v] >= t:
                dwell.append(lmap[v] - t)
        dwell.sort()
        ets = sorted(t for t, _ in E)
        hw = [ets[i + 1] - ets[i] for i in range(len(ets) - 1)]
        hw.sort()

        def q(a, f):
            return float(a[min(len(a) - 1, int(f * len(a)))]) if a else float("nan")

        out.append({
            "link": k,
            "n_enter": len(E), "n_leave": len(L), "n_first_link": int(dpt[k]),
            "cap_flow": float(meta[k]["cap_flow"]),
            "cap_headway_s": 3600.0 / max(meta[k]["cap_flow"], 1e-9),
            "dwell_p50_s": q(dwell, .50), "dwell_p90_s": q(dwell, .90),
            "dwell_max_s": (dwell[-1] if dwell else float("nan")),
            "headway_p50_s": q(hw, .50), "ff_s": float(meta[k]["ff_s"]),
        })
    return {"rows": out, "bytes": nbytes, "gz_bytes": n_gz, "n_hit": n_hit}


# ---------------------------------------------------------------------------
CONTRACT: dict = {"home": {}, "work": {}}


def build_analysis(m: pd.DataFrame, pop: dict, tr: dict) -> tuple[dict, dict]:
    """返回 (payload_fragment, ctx_fragment)。"""
    total_delay = float(m["delay_corr_h"].sum())
    total_raw = float(m["delay_raw_h"].sum())
    total_vol = float(m["vol"].sum())
    total_len = float(m["length"].sum())
    n_all = int(len(m))
    is_svc = (m["road_type"] == SERVICE).to_numpy()
    loaded = (m["vol"].to_numpy(float) > 0)

    svc_delay = float(m.loc[is_svc, "delay_corr_h"].sum())
    service_share_corr = 100.0 * svc_delay / total_delay
    service_share_raw = 100.0 * float(m.loc[is_svc, "delay_raw_h"].sum()) / total_raw

    # ---- 端点强度
    hw, ww = pop["home_w"], pop["work_w"]
    home_links = set(hw)
    work_links = set(ww)
    endp_all = home_links | work_links
    endp_strength: dict[str, float] = defaultdict(float)
    for k, v in hw.items():
        endp_strength[k] += v
    for k, v in ww.items():
        endp_strength[k] += v
    cls_map = dict(zip(m["link"], m["road_type"]))

    # ---------- A1 端点吸附
    by_cls: dict[str, float] = defaultdict(float)
    by_cls_n: Counter = Counter()
    tot_endp = 0.0
    for k, v in endp_strength.items():
        c = cls_map.get(k, "UNKNOWN")
        by_cls[c] += v
        by_cls_n[c] += 1
        tot_endp += v
    svc_endp = by_cls.get(SERVICE, 0.0)
    p_end_svc = svc_endp / tot_endp if tot_endp else float("nan")
    mileage_share_svc = float(m.loc[is_svc, "length"].sum()) / total_len if total_len else float("nan")
    count_share_svc = float(is_svc.sum()) / n_all if n_all else float("nan")
    enrich = p_end_svc / mileage_share_svc if mileage_share_svc else float("nan")
    a1 = "ENRICHED_ON_SERVICE" if enrich >= A1_ENRICH_MIN else "PROPORTIONAL_TO_MILEAGE"
    snap_rows = []
    for face, src in (("home", hw), ("work", ww), ("both", endp_strength)):
        tot = sum(src.values())
        agg: dict[str, float] = defaultdict(float)
        nl: Counter = Counter()
        for k, v in src.items():
            c = cls_map.get(k, "UNKNOWN")
            agg[c] += v
            nl[c] += 1
        for c, v in sorted(agg.items(), key=lambda x: -x[1]):
            snap_rows.append(dict(face=face, road_type=c, weighted_endpoints=v,
                                  share_pct=100.0 * v / tot if tot else float("nan"),
                                  n_links=nl[c]))
    snapping = pd.DataFrame(snap_rows)

    # ---------- A2 位置 vs 延误
    svc_tot_trav = tr["svc_first"] + tr["svc_last"] + tr["svc_mid"]
    f_pos = (tr["svc_first"] + tr["svc_last"]) / svc_tot_trav if svc_tot_trav else float("nan")
    endp_mask = m["link"].isin(endp_all).to_numpy()
    ep_svc = is_svc & endp_mask
    ep_svc_delay = float(m.loc[ep_svc, "delay_corr_h"].sum())
    ep_svc_vol = float(m.loc[ep_svc, "vol"].sum())
    svc_vol = float(m.loc[is_svc, "vol"].sum())
    w_ep = ep_svc_delay / svc_delay if svc_delay else float("nan")
    v_ep = ep_svc_vol / svc_vol if svc_vol else float("nan")
    a2 = ("ENDPOINT_LOCALIZED"
          if (w_ep >= A2_FACTOR * f_pos and w_ep >= A2_FACTOR * v_ep)
          else "POSITION_PROPORTIONAL")
    split_rows = []
    n_ep_svc = int(ep_svc.sum())
    non_ep_svc = is_svc & ~endp_mask
    for grp, mask, nn in (("endpoint_service", ep_svc, n_ep_svc),
                          ("nonendpoint_service", non_ep_svc, int(non_ep_svc.sum()))):
        d = float(m.loc[mask, "delay_corr_h"].sum())
        v = float(m.loc[mask, "vol"].sum())
        L = float(m.loc[mask, "length"].sum())
        split_rows.append(dict(group=grp, n_links=nn, length_km=L / 1000.0, vol=v,
                               delay_corr_h=d,
                               delay_share_service_pct=100.0 * d / svc_delay if svc_delay else float("nan"),
                               vol_share_service_pct=100.0 * v / svc_vol if svc_vol else float("nan"),
                               per_veh_delay_s=(d * 3600.0 / v) if v else float("nan")))
    split = pd.DataFrame(split_rows)
    pos_rows = []
    for c in sorted(set(tr["pos_first"]) | set(tr["pos_last"]) | set(tr["pos_mid"])):
        a = tr["pos_first"].get(c, 0)
        b = tr["pos_last"].get(c, 0)
        d = tr["pos_mid"].get(c, 0)
        t = a + b + d
        pos_rows.append(dict(road_type=c, first=a, last=b, mid=d, total=t,
                             endpoint_share_pct=100.0 * (a + b) / t if t else float("nan")))
    position = pd.DataFrame(pos_rows)

    # ---------- A3 干道接口
    pairs = []
    for k in m["link"]:
        a, b = k[1:].split("_")
        pairs.append((a, b))
    # 节点 -> 是否接干道
    node_hi: dict[str, bool] = defaultdict(bool)
    hi_links = m.loc[m["road_type"].isin(MAINLINE_SET), "link"]
    for k in hi_links:
        a, b = k[1:].split("_")
        node_hi[a] = True
        node_hi[b] = True
    adj_main = np.array([bool(node_hi.get(a)) or bool(node_hi.get(b)) for a, b in pairs])
    svc_adj = is_svc & adj_main
    svc_int = is_svc & ~adj_main
    s_main = float(m.loc[svc_adj, "delay_corr_h"].sum())
    s_int = float(m.loc[svc_int, "delay_corr_h"].sum())
    s_main_share = 100.0 * s_main / total_delay if total_delay else float("nan")
    s_int_share = 100.0 * s_int / total_delay if total_delay else float("nan")
    a3 = "NOT_MAINLINE_QUEUE" if s_main < s_int else "MAINLINE_QUEUE_SUSPECTED"
    adj_rows = []
    for grp, mask in (("mainline_adjacent_service", svc_adj), ("interior_service", svc_int)):
        adj_rows.append(dict(group=grp, n_links=int(mask.sum()),
                             vol=float(m.loc[mask, "vol"].sum()),
                             delay_corr_h=float(m.loc[mask, "delay_corr_h"].sum()),
                             delay_share_total_pct=100.0 * float(m.loc[mask, "delay_corr_h"].sum()) / total_delay
                             if total_delay else float("nan")))
    adjacency = pd.DataFrame(adj_rows)

    # ---------- A4 储存桶 + 绑定诊断
    st = m["storage_veh"].to_numpy(float)
    bins = [(0.0, 0.25, "<0.25"), (0.25, 0.5, "0.25-0.5"), (0.5, 1.0, "0.5-1"),
            (1.0, 2.0, "1-2"), (2.0, 5.0, "2-5"), (5.0, 20.0, "5-20"),
            (20.0, float("inf"), ">=20")]
    dl = m["delay_corr_h"].to_numpy(float)
    vv = m["vol"].to_numpy(float)
    srows = []
    for lo, hi, name in bins:
        sel = (st >= lo) & (st < hi)
        d = float(dl[sel].sum())
        srows.append(dict(bucket=name, n_links=int(sel.sum()), vol=float(vv[sel].sum()),
                          delay_h=d, delay_share_pct=100.0 * d / total_delay if total_delay else float("nan"),
                          storage_med_veh=float(np.median(st[sel])) if sel.any() else float("nan")))
    storage = pd.DataFrame(srows)

    D = ep_svc & (m["delay_corr_h"].to_numpy(float) > 0)
    D_delay = float(m.loc[D, "delay_corr_h"].sum())
    sat = D & (m["vc_flow"].to_numpy(float) >= SAT_VC)
    cell = D & (st < A4_CELL_STORAGE_MAX)
    sat_share_D = float(m.loc[sat, "delay_corr_h"].sum()) / D_delay if D_delay else float("nan")
    cell_share_D = float(m.loc[cell, "delay_corr_h"].sum()) / D_delay if D_delay else float("nan")
    if sat_share_D >= A4_SAT_MIN:
        a4 = "FLOW_CAPACITY_BOUND"
    elif cell_share_D >= A4_SAT_MIN:
        a4 = "STORAGE_CELL_BOUND"
    else:
        a4 = "NEITHER_BOUND"
    Dv = m.loc[D]
    bind = pd.DataFrame([
        dict(metric="n_delay_links_endpoint_service", value=float(len(Dv)), note="D 集大小"),
        dict(metric="delay_D_total_h", value=D_delay, note="D 集总延误"),
        dict(metric="sat_share_D", value=sat_share_D, note="v/c_flow>=0.9999 的延误份额"),
        dict(metric="cell_share_D", value=cell_share_D, note="storage_veh<2 的延误份额"),
        dict(metric="v_c_flow_p50", value=float(np.nanmedian(Dv["vc_flow"])) if len(Dv) else float("nan"), note="D 集"),
        dict(metric="v_c_flow_p90", value=float(np.nanpercentile(Dv["vc_flow"], 90)) if len(Dv) else float("nan"), note="D 集"),
        dict(metric="v_c_flow_max", value=float(np.nanmax(Dv["vc_flow"])) if len(Dv) else float("nan"), note="D 集"),
        dict(metric="v_c_storage_p50", value=float(np.nanmedian(Dv["vc_storage"])) if len(Dv) else float("nan"), note="vol/storage_veh"),
        dict(metric="v_c_storage_p90", value=float(np.nanpercentile(Dv["vc_storage"], 90)) if len(Dv) else float("nan"), note="vol/storage_veh"),
        dict(metric="storage_veh_p50", value=float(np.nanmedian(Dv["storage_veh"])) if len(Dv) else float("nan"), note="D 集"),
        dict(metric="storage_veh_p90", value=float(np.nanpercentile(Dv["storage_veh"], 90)) if len(Dv) else float("nan"), note="D 集"),
        dict(metric="dwell_delay_per_veh_p50_s", value=float(np.nanmedian(
            (Dv["delay_corr_h"] * 3600.0 / Dv["vol"]).replace([np.inf, -np.inf], np.nan))) if len(Dv) else float("nan"), note="D 集"),
        dict(metric="tt_s_p50", value=float(np.nanmedian(Dv["tt_s"])) if len(Dv) else float("nan"), note="D 集"),
        dict(metric="tt_s_max", value=float(np.nanmax(Dv["tt_s"])) if len(Dv) else float("nan"), note="D 集"),
    ])

    # ---------- A5 局部循环
    f_local = tr["nlocal"] / tr["nroute"] if tr["nroute"] else float("nan")
    a5 = "LOCAL_CIRCULATION_PRESENT" if f_local >= A5_LOCAL_MIN else "NEGLIGIBLE"
    lh = tr["len_hist"]
    tot_r = sum(lh.values())
    cum = 0
    rows_l = [dict(metric="n_routes", value=float(tr["nroute"])),
              dict(metric="n_local_routes", value=float(tr["nlocal"])),
              dict(metric="f_local", value=f_local),
              dict(metric="mean_route_links", value=(tr["len_sum"] / tr["nroute"]) if tr["nroute"] else float("nan"))]
    for b in sorted(lh):
        cum += lh[b]
        if b in (1, 2, 3, 5, 10, 20, 50, 100, 200, 600):
            rows_l.append(dict(metric=f"cum_share_le_{b}_links_pct", value=100.0 * cum / tot_r if tot_r else float("nan")))
    local = pd.DataFrame(rows_l)

    # ---------- A6 机制
    s_end = 100.0 * ep_svc_delay / total_delay if total_delay else float("nan")
    s_mid = 100.0 * float(m.loc[non_ep_svc, "delay_corr_h"].sum()) / total_delay if total_delay else float("nan")
    if s_main_share >= 100 * A6_DOMINANT_MIN:
        a6 = "MAINLINE_QUEUE_DOMINANT"
    elif s_mid >= 100 * A6_DOMINANT_MIN:
        a6 = "MIDROUTE_THROUGH_DOMINANT"
    elif s_end >= 100 * A6_DOMINANT_MIN and a4 == "STORAGE_CELL_BOUND":
        a6 = "SUBCELL_STORAGE_DOMINANT"
    elif s_end >= 100 * A6_DOMINANT_MIN:
        a6 = "ENDPOINT_ABSORPTION_DOMINANT"
    else:
        a6 = "MIXED_NO_SINGLE_DOMINANT"

    # ---------- 集中度
    d_ep_svc = m.loc[ep_svc].sort_values("delay_corr_h", ascending=False)
    tot_ep_svc = float(d_ep_svc["delay_corr_h"].sum())
    top10 = 100.0 * float(d_ep_svc["delay_corr_h"].head(10).sum()) / total_delay if total_delay else float("nan")
    top100 = 100.0 * float(d_ep_svc["delay_corr_h"].head(100).sum()) / total_delay if total_delay else float("nan")
    top10_ep = 100.0 * float(d_ep_svc["delay_corr_h"].head(10).sum()) / tot_ep_svc if tot_ep_svc else float("nan")
    top100_ep = 100.0 * float(d_ep_svc["delay_corr_h"].head(100).sum()) / tot_ep_svc if tot_ep_svc else float("nan")

    # ---------- top-30 画像
    detail_rows = []
    for rk, (_, row) in enumerate(d_ep_svc.head(30).iterrows(), 1):
        k = row["link"]
        tp = tr["tgt_pos"].get(k, {})
        detail_rows.append(dict(rank=rk, link=k, road_type=row["road_type"],
                                length_m=float(row["length"]), permlanes=float(row["lanes"]),
                                cap_flow=float(row["capacity"]), storage_veh=float(row["storage_veh"]),
                                vol=float(row["vol"]), tt_s=float(row["tt_s"]),
                                delay_corr_h=float(row["delay_corr_h"]),
                                delay_share_total_pct=100.0 * float(row["delay_corr_h"]) / total_delay if total_delay else float("nan"),
                                n_first=int(tp.get("first", 0)), n_last=int(tp.get("last", 0)),
                                n_mid=int(tp.get("mid", 0)),
                                endpoint_weight=float(endp_strength.get(k, 0.0))))
    detail = pd.DataFrame(detail_rows)
    targets = [r["link"] for r in detail_rows[:TOP_K]]

    # ---------- 暴露面（loaded 集）
    faces = []
    for face, sv, tv in (
        ("time_delay_corr_h", svc_delay, total_delay),
        ("count_links_loaded", float((is_svc & loaded).sum()), float(loaded.sum())),
        ("distance_km_loaded", float(m.loc[is_svc & loaded, "length"].sum()) / 1000.0,
         float(m.loc[loaded, "length"].sum()) / 1000.0),
        ("volume_veh", float(m.loc[is_svc & loaded, "vol"].sum()), float(m.loc[loaded, "vol"].sum())),
    ):
        faces.append(dict(face=face, service_value=sv, total_value=tv,
                          share_pct=100.0 * sv / tv if tv else float("nan")))
    exposure = pd.DataFrame(faces)

    vrows = [
        dict(question="A1_ENDPOINT_SNAPPING", verdict=a1,
             rule=f"enrich = p_end_svc/mileage_share_svc >= {A1_ENRICH_MIN}",
             evidence=f"p_end_svc={p_end_svc:.6f} mileage_share={mileage_share_svc:.6f} count_share={count_share_svc:.6f} enrich={enrich:.4f}"),
        dict(question="A2_ENDPOINT_ABSORPTION", verdict=a2,
             rule=f"w_ep >= {A2_FACTOR}*f_pos and w_ep >= {A2_FACTOR}*v_ep",
             evidence=f"f_pos={f_pos:.6f} w_ep={w_ep:.6f} v_ep={v_ep:.6f} svc_trav={svc_tot_trav}"),
        dict(question="A3_MAINLINE_INTERFACE", verdict=a3,
             rule="s_main < s_int",
             evidence=f"s_main={s_main_share:.4f}% s_int={s_int_share:.4f}% n_adj={int(svc_adj.sum())}"),
        dict(question="A4_BINDING_CONSTRAINT", verdict=a4,
             rule=f"sat_share_D>={A4_SAT_MIN} -> FLOW ; elif cell_share_D>={A4_SAT_MIN} -> STORAGE ; else NEITHER",
             evidence=f"sat_share_D={sat_share_D:.4f} cell_share_D={cell_share_D:.4f} nD={len(Dv)}"),
        dict(question="A5_LOCAL_CIRCULATION", verdict=a5,
             rule=f"f_local >= {A5_LOCAL_MIN}",
             evidence=f"f_local={f_local:.6f} n_local={tr['nlocal']}/{tr['nroute']}"),
        dict(question="A6_MECHANISM", verdict=a6,
             rule="ordered: main>=50% ; mid>=50% ; end>=50%&storage ; end>=50% ; else MIXED",
             evidence=f"s_end={s_end:.4f}% s_mid={s_mid:.4f}% s_main={s_main_share:.4f}% A4={a4}"),
    ]
    verdicts = pd.DataFrame(vrows)

    fr = dict(
        total_delay_corr_h=total_delay, total_delay_raw_h=total_raw, total_vol=total_vol,
        service_share_corr=service_share_corr, service_share_raw=service_share_raw,
        svc_delay=svc_delay, svc_vol=svc_vol, total_len=total_len, n_all=n_all,
        p_end_svc=p_end_svc, mileage_share_svc=mileage_share_svc, count_share_svc=count_share_svc,
        enrich=enrich, f_pos=f_pos, w_ep=w_ep, v_ep=v_ep, ep_svc_delay=ep_svc_delay,
        ep_svc_vol=ep_svc_vol, n_ep_svc=n_ep_svc, svc_tot_trav=svc_tot_trav,
        s_main_share=s_main_share, s_int_share=s_int_share, s_end=s_end, s_mid=s_mid,
        sat_share_D=sat_share_D, cell_share_D=cell_share_D, n_D=len(Dv),
        f_local=f_local, top10=top10, top100=top100, top10_ep=top10_ep, top100_ep=top100_ep,
        v1=a1, v2=a2, v3=a3, v4=a4, v5=a5, v6=a6,
        n_svc_loaded=int((is_svc & loaded).sum()), n_loaded=int(loaded.sum()),
    )
    dfs = dict(snapping=snapping, position=position, split=split, adjacency=adjacency,
               storage=storage, bind=bind, local=local, detail=detail, exposure=exposure,
               verdicts=verdicts)
    return fr, dfs


# ---------------------------------------------------------------------------
def flow_blind_ast(script_path: Path) -> tuple[bool, str]:
    src = script_path.read_text(encoding="utf-8", errors="replace")
    tree = ast.parse(src)
    bad_imports = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                if a.name.split(".")[0] in ("matsim", "java", "jpype"):
                    bad_imports.append(a.name)
        elif isinstance(node, ast.ImportFrom):
            if (node.module or "").split(".")[0] in ("matsim", "java", "jpype"):
                bad_imports.append(node.module or "")
    spawn = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            if node.func.attr in ("Popen", "run", "call", "check_output", "system"):
                spawn.append(node.func.attr)
    ok = (not bad_imports) and (not spawn)
    return ok, f"banned_imports={bad_imports}; subprocess_calls={spawn}"


def ast_compile_ok(script_path: Path) -> tuple[bool, str]:
    src = script_path.read_text(encoding="utf-8", errors="replace")
    try:
        ast.parse(src)
        det = "AST_PARSE_PASS"
    except SyntaxError as e:
        return False, f"AST_PARSE_FAIL: {e}"
    try:
        compile(src, str(script_path), "exec")
        det += "; COMPILE_PASS"
    except Exception as e:  # pragma: no cover
        return False, f"{det}; COMPILE_FAIL: {e}"
    return True, det


# ---------------------------------------------------------------------------
def checks(payload: dict, ctx: dict) -> list[dict]:
    rows: list[dict] = []

    def G(gate_id: str, ok: bool, detail: str) -> None:
        rows.append(dict(gate_id=gate_id, pass_=bool(ok), detail=detail[:400]))

    blocked = ctx.get("blocked", False)
    NA = "NOT_EVALUATED: preflight blocked"
    inp = ctx["inp"]

    G("7.9G1.01_PREREG_FROZEN_AND_EMBEDDED",
      ctx["prereg_disk_sha"] == PREREG_SHA and ctx["prereg_disk_bytes"] == PREREG_BYTES,
      f"disk={ctx['prereg_disk_sha'][:16]}({ctx['prereg_disk_bytes']}B) embedded={PREREG_SHA[:16]}({PREREG_BYTES}B)")
    ok_comp, det_comp = ast_compile_ok(Path(__file__))
    ok_blind, det_blind = flow_blind_ast(Path(__file__))
    G("7.9G1.02_SCRIPT_AST_COMPILE", ok_comp, det_comp)
    G("7.9G1.03_ZERO_SIMULATION", ok_blind, det_blind)
    G("7.9G1.04_INPUT_MANIFEST_COMPLETE",
      all(v.get("exists") and v.get("size_ok") and v.get("sha_ok") for v in inp["inputs"].values()),
      ";".join(f"{k}:{'ok' if v.get('sha_ok') else 'BAD'}" for k, v in inp["inputs"].items()))

    if blocked:
        for gid in ["7.9G1.05_LINKSTATS_154_COLUMNS", "7.9G1.06_NETWORK_JOIN_COMPLETE",
                    "7.9G1.07_LINKSTATS_JOIN_COMPLETE", "7.9G1.08_TRIPLE_FIELD_IDENTITY",
                    "7.9G1.09_REF_LINKSTATS_BYTE_IDENTICAL",
                    "7.9G1.10_ENDPOINT_LINK_EQ_ROUTE_ENDPOINT",
                    "7.9G1.11_CANONICAL_RECOMPUTE_MATCHES_G0",
                    "7.9G1.12_A1_ENDPOINT_SHARE_REPORTED", "7.9G1.13_A2_POSITION_VS_DELAY_DECLARED",
                    "7.9G1.14_A2_CONCENTRATION_REPORTED", "7.9G1.15_A3_MAINLINE_ADJACENCY_REPORTED",
                    "7.9G1.16_A4_STORAGE_BUCKETS_COMPLETE", "7.9G1.17_A4_VC_TENSION_DECLARED",
                    "7.9G1.18_A5_LOCAL_ROUTE_SHARE_REPORTED", "7.9G1.19_A6_MECHANISM_VERDICT_SINGLE",
                    "7.9G1.20_EXPOSURE_FACES_COMPLETE", "7.9G1.21_NO_WINDOW_MIXING",
                    "7.9G1.22_EVENTS_TRACE_COMPLETE", "7.9G1.23_TRACEABILITY_FIELDS_COMPLETE"]:
            G(gid, False, NA)
        writeback_and_tail(rows, payload, ctx, blocked=True)
        return rows

    G("7.9G1.05_LINKSTATS_154_COLUMNS", ctx["hdr_ok"], ctx["hdr_detail"])
    G("7.9G1.06_NETWORK_JOIN_COMPLETE", ctx["net_join_missing"] == 0, f"missing={ctx['net_join_missing']}")
    G("7.9G1.07_LINKSTATS_JOIN_COMPLETE", ctx["ls_join_missing"] == 0, f"missing={ctx['ls_join_missing']}")
    G("7.9G1.08_TRIPLE_FIELD_IDENTITY", ctx["triple_max_delta"] < TRIPLE_TOL,
      f"max|d|={ctx['triple_max_delta']:.3g}")
    G("7.9G1.09_REF_LINKSTATS_BYTE_IDENTICAL",
      inp["inputs"].get("ls_final", {}).get("sha256") == inp["inputs"].get("ls_viz_ref", {}).get("sha256"),
      f"final={str(inp['inputs'].get('ls_final',{}).get('sha256'))[:16]} viz={str(inp['inputs'].get('ls_viz_ref',{}).get('sha256'))[:16]}")

    fr = ctx["fr"]
    ct = ctx["contract"]
    mrate_h = ct["cnt_h"] / ct["cnt_cmp"] if ct["cnt_cmp"] else 0.0
    mrate_w = ct["cnt_w"] / ct["cnt_cmp"] if ct["cnt_cmp"] else 0.0
    G("7.9G1.10_ENDPOINT_LINK_EQ_ROUTE_ENDPOINT",
      ct["cnt_cmp"] == pop_expected() and mrate_h == 1.0 and mrate_w == 1.0,
      f"compared={ct['cnt_cmp']} home={mrate_h:.6f} work={mrate_w:.6f} expected={pop_expected()}")

    rel = abs(fr["service_share_corr"] - REF_SERVICE_SHARE_G0) / REF_SERVICE_SHARE_G0
    rel_t = abs(fr["total_delay_corr_h"] - REF_TOTAL_DELAY_G0) / REF_TOTAL_DELAY_G0
    G("7.9G1.11_CANONICAL_RECOMPUTE_MATCHES_G0",
      rel <= CANON_REL_TOL and rel_t <= CANON_REL_TOL,
      f"share={fr['service_share_corr']:.10f}(rel={rel:.3g}) total={fr['total_delay_corr_h']:.11f}(rel={rel_t:.3g})")

    G("7.9G1.12_A1_ENDPOINT_SHARE_REPORTED",
      np.isfinite(fr["p_end_svc"]) and 0 <= fr["p_end_svc"] <= 1
      and np.isfinite(fr["mileage_share_svc"]) and np.isfinite(fr["count_share_svc"])
      and fr["v1"] in V_A1,
      f"p_end_svc={fr['p_end_svc']:.6f} mileage={fr['mileage_share_svc']:.6f} count={fr['count_share_svc']:.6f} enrich={fr['enrich']:.4f} verdict={fr['v1']}")

    a2_rule = ("ENDPOINT_LOCALIZED"
               if (fr["w_ep"] >= A2_FACTOR * fr["f_pos"] and fr["w_ep"] >= A2_FACTOR * fr["v_ep"])
               else "POSITION_PROPORTIONAL")
    G("7.9G1.13_A2_POSITION_VS_DELAY_DECLARED",
      np.isfinite(fr["f_pos"]) and np.isfinite(fr["w_ep"]) and np.isfinite(fr["v_ep"])
      and fr["v2"] == a2_rule,
      f"f_pos={fr['f_pos']:.6f} w_ep={fr['w_ep']:.6f} v_ep={fr['v_ep']:.6f} rule={a2_rule} verdict={fr['v2']}")

    G("7.9G1.14_A2_CONCENTRATION_REPORTED",
      np.isfinite(fr["top10"]) and np.isfinite(fr["top100"])
      and fr["top10"] <= fr["top100"] <= 100.0 + 1e-9 and fr["top10"] < 100.0,
      f"top10={fr['top10']:.4f}% top100={fr['top100']:.4f}% (of total) top10_ep={fr['top10_ep']:.4f}%")

    a3_rule = "NOT_MAINLINE_QUEUE" if fr["s_main_share"] < fr["s_int_share"] else "MAINLINE_QUEUE_SUSPECTED"
    G("7.9G1.15_A3_MAINLINE_ADJACENCY_REPORTED",
      np.isfinite(fr["s_main_share"]) and np.isfinite(fr["s_int_share"]) and fr["v3"] == a3_rule,
      f"s_main={fr['s_main_share']:.4f}% s_int={fr['s_int_share']:.4f}% rule={a3_rule} verdict={fr['v3']}")

    sb = ctx["dfs"]["storage"]
    G("7.9G1.16_A4_STORAGE_BUCKETS_COMPLETE",
      len(sb) == 7 and int(sb.n_links.sum()) > 0 and int(sb.delay_share_pct.isna().sum()) == 0,
      f"buckets={len(sb)} n_sum={int(sb.n_links.sum())} nan={int(sb.delay_share_pct.isna().sum())}")

    a4_rule = ("FLOW_CAPACITY_BOUND" if fr["sat_share_D"] >= A4_SAT_MIN
               else "STORAGE_CELL_BOUND" if fr["cell_share_D"] >= A4_SAT_MIN else "NEITHER_BOUND")
    bd = ctx["dfs"]["bind"].set_index("metric")["value"]
    G("7.9G1.17_A4_VC_TENSION_DECLARED",
      np.isfinite(fr["sat_share_D"]) and np.isfinite(fr["cell_share_D"])
      and np.isfinite(float(bd.get("v_c_flow_p50", np.nan)))
      and np.isfinite(float(bd.get("v_c_storage_p50", np.nan)))
      and fr["v4"] == a4_rule,
      f"sat={fr['sat_share_D']:.4f} cell={fr['cell_share_D']:.4f} vc_flow_p50={bd.get('v_c_flow_p50')} "
      f"vc_storage_p50={bd.get('v_c_storage_p50')} rule={a4_rule} verdict={fr['v4']}")

    a5_rule = "LOCAL_CIRCULATION_PRESENT" if fr["f_local"] >= A5_LOCAL_MIN else "NEGLIGIBLE"
    G("7.9G1.18_A5_LOCAL_ROUTE_SHARE_REPORTED",
      np.isfinite(fr["f_local"]) and 0 <= fr["f_local"] <= 1 and fr["v5"] == a5_rule,
      f"f_local={fr['f_local']:.6f} rule={a5_rule} verdict={fr['v5']}")

    a6_rule = ctx["a6_rule"]
    G("7.9G1.19_A6_MECHANISM_VERDICT_SINGLE",
      fr["v1"] in V_A1 and fr["v2"] in V_A2 and fr["v3"] in V_A3 and fr["v4"] in V_A4
      and fr["v5"] in V_A5 and fr["v6"] in V_A6 and fr["v6"] == a6_rule,
      f"A1={fr['v1']} A2={fr['v2']} A3={fr['v3']} A4={fr['v4']} A5={fr['v5']} A6={fr['v6']} rule={a6_rule}")

    ex = ctx["dfs"]["exposure"]
    G("7.9G1.20_EXPOSURE_FACES_COMPLETE",
      len(ex) == 4 and int(ex.share_pct.isna().sum()) == 0
      and all(np.isfinite(ex.service_value)) and all(np.isfinite(ex.total_value)),
      f"faces={list(ex.face)}")

    bad_hours = [h for h in READ_HOURS if h not in ("7-8", "8-9", "9-10", "10-11")]
    agg_cols = [c for c in ctx.get("ls_cols", []) if "0-24" in c]
    G("7.9G1.21_NO_WINDOW_MIXING", (not bad_hours) and (SIM_WINDOW in READ_HOURS) and (not agg_cols),
      f"read_hours={READ_HOURS} sim_window={SIM_WINDOW} bad={bad_hours} aggregate_cols={agg_cols}")

    et = ctx["dfs"]["events"]
    G("7.9G1.22_EVENTS_TRACE_COMPLETE",
      len(et) == TOP_K and int((et.n_enter >= 1).sum()) == TOP_K
      and int(et.dwell_p90_s.isna().sum()) == 0 and int(et.headway_p50_s.isna().sum()) == 0,
      f"targets={len(et)} with_enter={int((et.n_enter>=1).sum())} nan_dwell={int(et.dwell_p90_s.isna().sum())}")

    miss_cols = {}
    for f, req in REQUIRED_COLS.items():
        p = ctx["out"] / f
        if not p.exists():
            miss_cols[f] = ["__MISSING_FILE__"]
            continue
        cols = pd.read_csv(p, nrows=0).columns.tolist()
        mm = [c for c in req if c not in cols]
        if mm:
            miss_cols[f] = mm
    G("7.9G1.23_TRACEABILITY_FIELDS_COMPLETE", not miss_cols, json.dumps(miss_cols)[:300])

    writeback_and_tail(rows, payload, ctx, blocked=False)
    return rows


# ---------------------------------------------------------------------------
def pop_expected() -> int:
    return POP_N


def writeback_and_tail(rows: list[dict], payload: dict, ctx: dict, blocked: bool) -> None:
    def G(gate_id: str, ok: bool, detail: str) -> None:
        rows.append(dict(gate_id=gate_id, pass_=bool(ok), detail=detail[:400]))

    out = ctx["out"]
    disk = {f.name for f in out.iterdir() if f.is_file()} if out.exists() else set()
    declared = set(ARTIFACT_NAMES)
    man = ctx.get("manifest_records", {})
    man_set = set(man.keys())
    clo = ctx.get("closure_records", {})
    clo_set = set(clo.keys())
    byte_bad = []
    n_cmp = 0
    for name in sorted(declared - WRITEBACK_EXCLUDED):
        p = out / name
        if not p.exists():
            byte_bad.append(f"{name}:missing")
            continue
        n_cmp += 1
        if man.get(name) and man[name].get("sha256") != sha256_file(p):
            byte_bad.append(f"{name}:sha")
        elif man.get(name) and man[name].get("size") != p.stat().st_size:
            byte_bad.append(f"{name}:size")
    set_ok = (disk == declared) and (man_set | {MANIFEST_NAME, CLOSURE_NAME} == declared) \
        and (clo_set | {CLOSURE_NAME} == declared)
    stray = ctx.get("stray", [])

    drift = []
    for name, (rel, size, sha) in INPUTS.items():
        p = ROOT / rel
        if (not p.exists()) or sha256_file(p) != sha:
            drift.append(f"input:{name}")
    for name, (rel, size, sha) in REFS.items():
        p = ctx["ref_dir"] / rel
        if (not p.exists()) or sha256_file(p) != sha:
            drift.append(f"ref:{name}")
    g25_ok = not drift

    core = [r for r in rows if not r["gate_id"].startswith("7.9G1.24_")]
    st_ck = STATUS_READY if (all(r["pass_"] for r in core) and g25_ok and not blocked) else STATUS_BLOCKED
    sm_p = out / SUMMARY_NAME
    rp_p = out / REPORT_NAME
    st_sm = ""
    if sm_p.exists():
        try:
            st_sm = json.loads(sm_p.read_text(encoding="utf-8")).get("status", "")
        except Exception:
            st_sm = ""
    st_rp = ""
    if rp_p.exists():
        for ln in rp_p.read_text(encoding="utf-8", errors="replace").splitlines():
            mm = re.search(r"\*\*STATUS:\s*([A-Z0-9_]+)\*\*", ln)
            if mm:
                st_rp = mm.group(1)
                break
    sm_num_ok, sm_num_detail = True, ""
    if sm_p.exists():
        try:
            _o = json.loads(sm_p.read_text(encoding="utf-8"))
            _got = float(_o.get("service_share_corr_pct_8_9", -1.0))
            _want = float(ctx.get("fr", {}).get("service_share_corr", -99.0))
            sm_num_ok = abs(_got - _want) < 1e-9 and _want == _want
            sm_num_detail = f" summary_share={_got} expected={_want}"
        except Exception as e:  # pragma: no cover
            sm_num_ok, sm_num_detail = False, f" summary_parse_err={e}"
    G("7.9G1.24_TERMINAL_STATE_THREE_WAY",
      set_ok and not byte_bad and not stray
      and st_ck == st_sm == st_rp and st_ck in (STATUS_READY, STATUS_BLOCKED) and sm_num_ok,
      f"writeback_set_ok={set_ok} byte_bad={byte_bad} stray={stray} "
      f"checks={st_ck} summary={st_sm} report={st_rp}{sm_num_detail}")

    G("7.9G1.25_NON_7_9G_ARTIFACTS_UNCHANGED", g25_ok,
      f"checked={len(INPUTS)+len(REFS)} drift={drift}")


# ---------------------------------------------------------------------------
def build_manifest(out: Path, ctx: dict) -> dict:
    recs = {}
    for name in ARTIFACT_NAMES:
        if name in (MANIFEST_NAME, CLOSURE_NAME):
            continue
        p = out / name
        if p.exists():
            recs[name] = {"size": p.stat().st_size, "sha256": sha256_file(p)}
    return {
        "step": STEP_ID,
        "prereg_sha256": PREREG_SHA,
        "generated_after_all_analysis_outputs": True,
        "excludes": [MANIFEST_NAME, CLOSURE_NAME],
        "artifacts": recs,
    }


def build_closure(out: Path, status: str, manifest: dict) -> tuple[pd.DataFrame, bool]:
    rows = []
    for name in sorted(ARTIFACT_NAMES):
        if name == CLOSURE_NAME:
            continue
        p = out / name
        if not p.exists():
            rows.append(dict(kind="artifact", name=name, exists=False, size_bytes=0, sha256=""))
            continue
        rows.append(dict(kind="artifact", name=name, exists=True,
                         size_bytes=p.stat().st_size, sha256=sha256_file(p)))
    n_art = sum(1 for r in rows if r["kind"] == "artifact")
    rows.append(dict(kind="self_exclusion", name=CLOSURE_NAME, exists=True,
                     size_bytes=n_art, sha256=""))
    for k in ("status_checks", "status_summary", "status_report"):
        rows.append(dict(kind=k, name="", exists=True, size_bytes=0, sha256=status))
    df = pd.DataFrame(rows)
    ok = all(r["exists"] for _, r in df.iterrows())
    df = pd.concat([df, pd.DataFrame([dict(kind="closure_verdict", name="", exists=ok,
                                           size_bytes=int(n_art), sha256="OK" if ok else "FAIL")])],
                   ignore_index=True)
    return df, ok


def write_summary(out: Path, payload: dict, rows: list[dict]) -> None:
    fr = payload.get("fr", {})
    s = {
        "step": STEP_ID,
        "status": payload["status"],
        "closure": payload.get("closure", ""),
        "gates_total": len(rows),
        "gates_pass": int(sum(1 for r in rows if r["pass_"])),
        "verdict_A1": fr.get("v1"), "verdict_A2": fr.get("v2"), "verdict_A3": fr.get("v3"),
        "verdict_A4": fr.get("v4"), "verdict_A5": fr.get("v5"), "verdict_A6": fr.get("v6"),
        "service_share_corr_pct_8_9": fr.get("service_share_corr"),
        "service_share_raw_pct_8_9": fr.get("service_share_raw"),
        "total_delay_corr_h": fr.get("total_delay_corr_h"),
        "p_end_svc": fr.get("p_end_svc"),
        "mileage_share_svc": fr.get("mileage_share_svc"),
        "f_pos": fr.get("f_pos"),
        "w_ep": fr.get("w_ep"),
        "v_ep": fr.get("v_ep"),
        "s_end_pct": fr.get("s_end"),
        "s_mid_pct": fr.get("s_mid"),
        "s_main_pct": fr.get("s_main_share"),
        "sat_share_D": fr.get("sat_share_D"),
        "cell_share_D": fr.get("cell_share_D"),
        "f_local": fr.get("f_local"),
        "top10_endpoint_service_pct_of_total": fr.get("top10"),
        "prereg_sha256": PREREG_SHA,
    }
    (out / SUMMARY_NAME).write_bytes(json.dumps(s, ensure_ascii=False, indent=2).encode("utf-8"))


def write_report(out: Path, payload: dict, rows: list[dict]) -> None:
    fr = payload.get("fr", {})
    L = []
    L.append("# STEP 7.9G-1 — 端点/接入子系统「就地吸收」机制审计 · R0（零仿真 / 只读）\n")
    L.append(f"**STATUS: {payload['status']}**")
    L.append(f"**CLOSURE: {payload.get('closure','')}**\n")
    L.append(f"- 门禁：**{sum(1 for r in rows if r['pass_'])}/{len(rows)}**")
    L.append(f"- prereg：`{PREREG_SHA}`（{PREREG_BYTES} B）")
    for q in ("A1", "A2", "A3", "A4", "A5", "A6"):
        L.append(f"- {q} 判决：`{fr.get('v'+q[-1])}`")
    L.append("")
    L.append("## 关键数字（第一手复算）\n")
    L.append(f"- 全网 `delay_corr_h`（08-09）= **{fr.get('total_delay_corr_h', float('nan')):.6f}**（G-0 = 4778.77366611111）")
    L.append(f"- `service` 份额 canonical = **{fr.get('service_share_corr', float('nan')):.6f}%** / raw = **{fr.get('service_share_raw', float('nan')):.6f}%**")
    L.append(f"- 端点吸附：`p_end_svc` = **{fr.get('p_end_svc', float('nan')):.6f}** vs 里程基线 **{fr.get('mileage_share_svc', float('nan')):.6f}**（enrich **{fr.get('enrich', float('nan')):.4f}×**）")
    L.append(f"- 位置面 vs 延误面：`f_pos` = **{fr.get('f_pos', float('nan')):.6f}** ; `w_ep` = **{fr.get('w_ep', float('nan')):.6f}** ; `v_ep` = **{fr.get('v_ep', float('nan')):.6f}**")
    L.append(f"- 干道接口：`s_main` = **{fr.get('s_main_share', float('nan')):.4f}%** vs 内部 `s_int` = **{fr.get('s_int_share', float('nan')):.4f}%**")
    L.append(f"- 绑定诊断：`sat_share_D` = **{fr.get('sat_share_D', float('nan')):.4f}** ; `cell_share_D` = **{fr.get('cell_share_D', float('nan')):.4f}** ; nD = {fr.get('n_D')}")
    L.append(f"- 集中度：端点 service 的 top-10 占**全网**延误 **{fr.get('top10', float('nan')):.4f}%**、top-100 **{fr.get('top100', float('nan')):.4f}%**")
    L.append(f"- 局部循环：`f_local` = **{fr.get('f_local', float('nan')):.6f}**\n")
    L.append("## 门禁明细\n")
    L.append("| gate | pass | detail |")
    L.append("|---|---|---|")
    for r in rows:
        L.append(f"| `{r['gate_id']}` | {'✅' if r['pass_'] else '❌'} | {r['detail']} |")
    (out / REPORT_NAME).write_bytes(("\n".join(L) + "\n").encode("utf-8"))


def _isolation_stray(out: Path) -> list[str]:
    allowed = set(ARTIFACT_NAMES)
    if not out.exists():
        return []
    return sorted(f.name for f in out.iterdir() if f.is_file() and f.name not in allowed)


POP_N = 0


# ---------------------------------------------------------------------------
def main() -> int:
    global POP_N
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(OUT_DEFAULT))
    ap.add_argument("--ref-dir", default=str(REF_DEFAULT))
    ap.add_argument("--cache", default="")
    args = ap.parse_args()
    out = Path(args.out)
    ref_dir = Path(args.ref_dir)
    out.mkdir(parents=True, exist_ok=True)
    print("=" * 78)
    print(f"STEP {STEP_ID} — endpoint/access absorption R0 (read-only, zero-simulation)")
    print("=" * 78)

    t0 = time.time()
    inp, inp_errs = preflight_inputs()
    refs, ref_errs = preflight_refs(ref_dir)
    hdr, hdr_errs = preflight_linkstats_header()
    preflight_errors = inp_errs + ref_errs + hdr_errs
    blocked = bool(preflight_errors)
    hdr_ok = (len(hdr) == LINKSTATS_EXPECTED_COLS) and not hdr_errs
    hdr_detail = f"n_cols={len(hdr)}; missing={[c for c in REQUIRED_LINKSTATS_FIELDS if c not in hdr]}"
    print(f"  preflight errors={preflight_errors}")

    prereg_p = ROOT / PREREG_REL
    prereg_disk_sha = sha256_file(prereg_p) if prereg_p.exists() else ""
    prereg_disk_bytes = prereg_p.stat().st_size if prereg_p.exists() else 0

    payload: dict = {"status": STATUS_BLOCKED, "closure": "", "fr": {}}
    ctx: dict = {
        "out": out, "ref_dir": ref_dir, "inp": inp, "refs": refs,
        "preflight_errors": preflight_errors, "blocked": blocked,
        "hdr_ok": hdr_ok, "hdr_detail": hdr_detail,
        "prereg_disk_sha": prereg_disk_sha, "prereg_disk_bytes": prereg_disk_bytes,
        "net_join_missing": -1, "ls_join_missing": -1, "triple_max_delta": float("inf"),
        "fr": {}, "dfs": {}, "contract": {"cnt_cmp": 0, "cnt_h": 0, "cnt_w": 0},
        "a6_rule": "", "manifest_records": {}, "closure_records": {}, "stray": [], "ls_cols": [],
    }

    analysis_err = ""
    if not blocked:
        try:
            m, ls_cols = load_net()
            ctx["ls_cols"] = ls_cols
            ctx["net_join_missing"] = int(m.road_type.isna().sum())
            ctx["ls_join_missing"] = int(m[f"HRS{SIM_WINDOW}avg"].isna().sum())
            common = m.dropna(subset=["LENGTH", "FREESPEED", "CAPACITY", "length", "freespeed", "capacity"])
            ctx["triple_max_delta"] = float(max(
                np.abs(common["length"] - common["LENGTH"]).max(),
                np.abs(common["freespeed"] - common["FREESPEED"]).max(),
                np.abs(common["capacity"] - common["CAPACITY"]).max(),
            )) if len(common) else float("inf")
            print(f"  net loaded ({time.time()-t0:.1f}s)", flush=True)

            pop = load_population()
            POP_N = pop["n"]
            CONTRACT["home"] = pop["home_p"]
            CONTRACT["work"] = pop["work_p"]
            print(f"  population parsed n={pop['n']} bad={pop['bad']} sumEF={pop['sum_ef']:.3f} "
                  f"({time.time()-t0:.1f}s)", flush=True)

            cls_b = {k.encode(): v for k, v in zip(m["link"], m["road_type"])}
            endp_links = set(pop["home_w"]) | set(pop["work_w"])
            ep = m[(m.road_type == SERVICE) & (m.link.isin(endp_links))]
            targets = list(ep.sort_values("delay_corr_h", ascending=False)["link"].head(TOP_K))
            print(f"  targets(top{TOP_K}) = {targets[:3]} ({time.time()-t0:.1f}s)", flush=True)

            ckey = "%s|%s|%s|%d" % (INPUTS["plans"][2], INPUTS["events"][2], INPUTS["pop"][2], TOP_K)
            cache_hit = False
            tr = None
            ev = None
            if args.cache and Path(args.cache).exists():
                try:
                    _cc = json.loads(Path(args.cache).read_text(encoding="utf-8"))
                    if _cc.get("key") == ckey:
                        tr = _cc["tr"]
                        ev = _cc["ev"]
                        tr["tgt_pos"] = {k: dict(v) for k, v in tr.get("tgt_pos", {}).items()}
                        cache_hit = True
                except Exception:
                    cache_hit = False
            if cache_hit:
                print(f"  plans/events from cache ({time.time()-t0:.1f}s)", flush=True)
            else:
                tr = scan_plans(cls_b, set(targets))
                print(f"  plans scanned routes={tr['nroute']} ({time.time()-t0:.1f}s)", flush=True)
                meta = {r["link"]: {"cap_flow": float(r["capacity"]), "ff_s": float(r["ff_s"])}
                        for _, r in m[m.link.isin(targets)].iterrows()}
                ev = events_trace(targets, meta)
                print(f"  events scanned {ev['bytes']/1e9:.2f} GB (gz {ev.get('gz_bytes',0)/1e9:.2f}) hits={ev['n_hit']} ({time.time()-t0:.1f}s)", flush=True)
                if args.cache:
                    try:
                        Path(args.cache).parent.mkdir(parents=True, exist_ok=True)
                        Path(args.cache).write_text(
                            json.dumps({"key": ckey, "tr": tr, "ev": ev}, ensure_ascii=False),
                            encoding="utf-8")
                    except Exception as _ce:
                        print(f"  cache write skipped: {_ce}", flush=True)
            ctx["contract"] = {"cnt_cmp": tr["cnt_cmp"], "cnt_h": tr["cnt_h"], "cnt_w": tr["cnt_w"]}
            print(f"  contract={tr['cnt_h']}/{tr['cnt_w']}/{tr['cnt_cmp']}", flush=True)

            fr, dfs = build_analysis(m, pop, tr)
            dfs["events"] = pd.DataFrame(ev["rows"])
            ctx["fr"] = fr
            ctx["dfs"] = dfs
            a6_rule = ("MAINLINE_QUEUE_DOMINANT" if fr["s_main_share"] >= 100 * A6_DOMINANT_MIN
                       else "MIDROUTE_THROUGH_DOMINANT" if fr["s_mid"] >= 100 * A6_DOMINANT_MIN
                       else "SUBCELL_STORAGE_DOMINANT" if (fr["s_end"] >= 100 * A6_DOMINANT_MIN and fr["v4"] == "STORAGE_CELL_BOUND")
                       else "ENDPOINT_ABSORPTION_DOMINANT" if fr["s_end"] >= 100 * A6_DOMINANT_MIN
                       else "MIXED_NO_SINGLE_DOMINANT")
            ctx["a6_rule"] = a6_rule
            payload["fr"] = fr

            dfs["snapping"].to_csv(out / "g1_endpoint_snapping.csv", index=False, encoding="utf-8-sig")
            dfs["position"].to_csv(out / "g1_route_position_profile.csv", index=False, encoding="utf-8-sig")
            dfs["split"].to_csv(out / "g1_endpoint_service_split.csv", index=False, encoding="utf-8-sig")
            dfs["adjacency"].to_csv(out / "g1_mainline_adjacency.csv", index=False, encoding="utf-8-sig")
            dfs["storage"].to_csv(out / "g1_storage_buckets.csv", index=False, encoding="utf-8-sig")
            dfs["bind"].to_csv(out / "g1_binding_diagnostics.csv", index=False, encoding="utf-8-sig")
            dfs["local"].to_csv(out / "g1_local_circulation.csv", index=False, encoding="utf-8-sig")
            dfs["detail"].to_csv(out / "g1_concentration_detail.csv", index=False, encoding="utf-8-sig")
            dfs["events"].to_csv(out / "g1_events_trace.csv", index=False, encoding="utf-8-sig")
            dfs["exposure"].to_csv(out / "g1_exposure_faces.csv", index=False, encoding="utf-8-sig")
            dfs["verdicts"].to_csv(out / "g1_verdicts.csv", index=False, encoding="utf-8-sig")
            print(f"  A1={fr['v1']} A2={fr['v2']} A3={fr['v3']} A4={fr['v4']} A5={fr['v5']} A6={fr['v6']}",
                  flush=True)
        except Exception:
            import traceback
            analysis_err = traceback.format_exc()
            print("ANALYSIS_ERROR:\n" + analysis_err[-2500:], flush=True)
    if analysis_err:
        blocked = True
        ctx["blocked"] = True
        ctx["analysis_error"] = analysis_err[-500:]
        print("  analysis failed -> BLOCKED terminal state", flush=True)

    prev_state = None
    prev_closure = ""
    converged = False
    iterations = 0
    for iterations in range(1, 8):
        STATUS["checks_rows"] = []
        rows = checks(payload, ctx)
        STATUS["checks_rows"] = rows
        core = [r for r in rows if not r["gate_id"].startswith("7.9G1.24_")]
        all_pass = all(r["pass_"] for r in core)
        status = STATUS_READY if (all_pass and not blocked) else STATUS_BLOCKED
        payload["status"] = status
        payload["closure"] = prev_closure
        pd.DataFrame(rows).rename(columns={"pass_": "pass"}).to_csv(
            out / CHECKS_NAME, index=False, encoding="utf-8-sig")

        write_report(out, payload, rows)
        write_summary(out, payload, rows)

        manifest = build_manifest(out, ctx)
        ctx["manifest_records"] = manifest["artifacts"]
        (out / MANIFEST_NAME).write_bytes(json.dumps(manifest, ensure_ascii=False, indent=2).encode("utf-8"))

        closure_df, closure_ok = build_closure(out, status, manifest)
        ctx["closure_records"] = {r["name"]: r for _, r in closure_df.iterrows() if r["kind"] == "artifact"}
        closure_df.to_csv(out / CLOSURE_NAME, index=False, encoding="utf-8-sig")
        final_closure = "OK" if closure_ok else "CLOSURE_FAILED"
        ctx["stray"] = _isolation_stray(out)

        state = (sha256_file(out / CHECKS_NAME), sha256_file(out / REPORT_NAME),
                 sha256_file(out / SUMMARY_NAME), sha256_file(out / MANIFEST_NAME),
                 sha256_file(out / CLOSURE_NAME), status, final_closure)
        if state == prev_state:
            converged = True
            break
        prev_state = state
        prev_closure = final_closure

    print(f"  converged={converged} iterations={iterations} "
          f"checks={sum(1 for r in STATUS['checks_rows'] if r['pass_'])}/{len(STATUS['checks_rows'])} "
          f"STATUS={payload['status']} CLOSURE={prev_closure}")
    print(f"  total {time.time()-t0:.1f}s")
    exit_ok = converged and payload["status"] == STATUS_READY and prev_closure == "OK"
    return 0 if exit_ok else 1


if __name__ == "__main__":
    sys.exit(main())
