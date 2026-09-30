#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Step 7.9G-0 — `service` 延误机制 · R0 结构审计（零仿真 / 只读）

边界：不跑 MATSim、不改任何既有产物、不动 service 参数。
读 5 件冻结输入（§2）+ 3 件只读对照物（§3），回答 Q1/Q2/Q3，落 14 件产物 + prereg。

运行：
    python audit_service_delay_mechanism_7_9g0.py
    python audit_service_delay_mechanism_7_9g0.py --out <dir> --ref-dir <dir>
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import re
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
ROOT = Path(r"D:\Luan\2026-05\2_Singapore")
OUT_DEFAULT = ROOT / "reports" / "service_delay_mechanism_7_9g0"
REF_DEFAULT = ROOT / "reports" / "congestion_plausibility_audit_7_7e"

STEP_ID = "7.9G-0"
STATUS_READY = "SERVICE_DELAY_R0_READY"
STATUS_BLOCKED = "SERVICE_DELAY_R0_BLOCKED"

PREREG_NAME = "PREREG_7_9G0.md"
PREREG_REL = "reports/service_delay_mechanism_7_9g0/" + PREREG_NAME
PREREG_SHA = "2db351c89afffa93e8ccf007e28ced9b1127ad41d992e48631db98a006f49b51"
PREREG_BYTES = 14221

# §2 冻结输入
INPUTS: dict[str, tuple[str, int, str]] = {
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
    "cfg": (
        "matsim_final_7_6h/configs/config_W01_rc_min.xml",
        22098,
        "8f44fb349bff9cf1b2bfd497b914b291f9d79482936689a2f2b6a8ffcfc1206e",
    ),
}
# §3 只读对照物（相对 REF_DEFAULT）
REFS: dict[str, tuple[str, int, str]] = {
    "e7e_audit_summary": (
        "audit_summary.json", 13098,
        "e8bb8f7c02599ce9d49beaf0038b774397ad5965f159b6eafad242273573a4ee",
    ),
    "e7e_roadtype_quant": (
        "e2b_roadtype_quantization.csv", 2182,
        "5cc30ce1003a8894492884febb50d72a11185991db8b5e5c220997483d586105",
    ),
    "e7e_sat_links": (
        "e2_saturated_links_0809.csv", 7828,
        "723f11a840617de826bebbc91b29c23fcbdebb14487e34f6dd2931d62b262770",
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
SERVICE_UNIT_CAP = 400  # 单位容量（辆/h/车道）
UNIT_CAP: dict[str, float] = {
    "motorway": 1900.0, "motorway_link": 1700.0,
    "trunk": 1800.0, "trunk_link": 1600.0,
    "primary": 1500.0, "primary_link": 1300.0,
    "secondary": 1200.0, "secondary_link": 1100.0,
    "tertiary": 900.0, "tertiary_link": 900.0,
    "residential": 700.0, "unclassified": 600.0,
    "service": SERVICE_UNIT_CAP,
}

REF_SERVICE_SHARE_7E7E = 94.35657888849315
CANON_REL_TOL = 1e-6
TRIPLE_TOL = 1e-9

Q1_DOMINANT_THRESHOLD = 0.50
Q2_BAND = (0.85, 0.99)
Q2_RANGE_MAX = 0.05
Q2_GAP_MIN = 0.10
Q3_EXACT_MIN = 0.999999

VERDICT_Q1_SET = {"CAPACITY_CONSTRAINT_DOMINANT", "CAPACITY_CONSTRAINT_NOT_DOMINANT"}
VERDICT_Q2_SET = {"CALIBER_STABLE", "CALIBER_FRAGILE"}
VERDICT_Q3_SET = {"SERVICE_PARAMS_DERIVED", "SERVICE_PARAMS_FREE_KNOW"}

# ---------------------------------------------------------------------------
OUTPUT_NAMES = [
    "g0_roadtype_delay_decomposition.csv",
    "g0_caliber_matrix.csv",
    "g0_exposure_faces.csv",
    "g0_service_capacity_binding.csv",
    "g0_service_length_buckets.csv",
    "g0_service_concentration.csv",
    "g0_parameter_provenance.csv",
    "g0_qsim_override.csv",
    "g0_verdicts.csv",
    "g0_checks.csv",
    "g0_closure_check.csv",
    "g0_input_manifest.json",
    "g0_summary.json",
    "STEP7_9G0_REPORT.md",
]
CHECKS_NAME = "g0_checks.csv"
MANIFEST_NAME = "g0_input_manifest.json"
CLOSURE_NAME = "g0_closure_check.csv"
SUMMARY_NAME = "g0_summary.json"
REPORT_NAME = "STEP7_9G0_REPORT.md"
WRITEBACK_EXCLUDED = {CHECKS_NAME, MANIFEST_NAME, CLOSURE_NAME}
ARTIFACT_NAMES = OUTPUT_NAMES + [PREREG_NAME]

REQUIRED_COLS: dict[str, list[str]] = {
    "g0_roadtype_delay_decomposition.csv":
        ["road_type", "n_links", "n_loaded", "length_km", "vol", "ratio_vw",
         "qratio_vw", "delay_raw_h", "delay_corr_h", "share_corr_pct", "share_raw_pct", "sat_links"],
    "g0_caliber_matrix.csv":
        ["caliber_id", "quantization", "hour", "inclusion", "exposure",
         "service_value", "total_value", "share", "note"],
    "g0_exposure_faces.csv": ["face", "service_value", "total_value", "share_pct"],
    "g0_service_capacity_binding.csv": ["metric", "value", "note"],
    "g0_service_length_buckets.csv":
        ["bucket", "n", "vol", "delay_h", "delay_share_pct", "ff_med_s", "vc_med", "per_veh_s"],
    "g0_service_concentration.csv": ["rank_scope", "share_pct", "cum_delay_h"],
    "g0_parameter_provenance.csv":
        ["road_type", "n", "cap_eq_unit_lanes_share", "lanes_set", "capacity_set", "freespeed_set"],
    "g0_qsim_override.csv": ["param", "value"],
    "g0_verdicts.csv": ["question", "verdict", "rule", "evidence"],
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


def _src_text() -> str:
    return Path(__file__).read_text(encoding="utf-8", errors="replace")


# ---------------------------------------------------------------------------
def preflight_inputs() -> tuple[dict, list[str]]:
    """返回 (info, errors)。只读、不写盘。"""
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
def load_all() -> dict:
    t0 = time.time()
    ls_cols = ["LINK", "LENGTH", "FREESPEED", "CAPACITY"] + \
              [f"HRS{h}avg" for h in READ_HOURS] + [f"TRAVELTIME{h}avg" for h in READ_HOURS]
    net = pd.read_csv(ROOT / INPUTS["net_links_runtime"][0], sep=";",
                      usecols=["link", "length", "freespeed", "capacity", "lanes"])
    src = pd.read_csv(ROOT / INPUTS["src_copy"][0],
                      usecols=["from_node", "to_node", "highway", "lanes"])
    src["link"] = "e" + src["from_node"].astype(str) + "_" + src["to_node"].astype(str)
    src = src.rename(columns={"highway": "road_type", "lanes": "src_lanes"})
    ls = pd.read_csv(ROOT / INPUTS["ls_final"][0], sep="\t", usecols=ls_cols, low_memory=False)
    ls = ls.rename(columns={"LINK": "link"})

    m = net.merge(src[["link", "road_type"]], on="link", how="left")
    m = m.merge(ls, on="link", how="left")
    m["ff_s"] = m["length"] / m["freespeed"]
    m["ff_ceil_s"] = np.ceil(m["ff_s"] - 1e-9)
    return {"net": net, "src": src, "ls": ls, "m": m, "ls_cols": ls_cols, "secs": time.time() - t0}


# ---------------------------------------------------------------------------
def group_metrics(g: pd.DataFrame, hour: str, quant: str) -> dict:
    v = g[f"HRS{hour}avg"].fillna(0).to_numpy(float)
    tt = g[f"TRAVELTIME{hour}avg"].to_numpy(float)
    ff = g["ff_s"].to_numpy(float)
    fc = g["ff_ceil_s"].to_numpy(float)
    cap = g["capacity"].to_numpy(float)
    L = g["length"].to_numpy(float)
    k = (v > 0) & np.isfinite(tt) & (ff > 0)
    base = fc if quant == "corr" else ff
    delay = np.where(k, v * np.clip(np.where(np.isfinite(tt), tt, np.nan) - base, 0, None), 0.0) / 3600.0
    delay = np.nan_to_num(delay, nan=0.0)
    delay_raw = np.where(k, v * np.clip(np.where(np.isfinite(tt), tt, np.nan) - ff, 0, None), 0.0) / 3600.0
    delay_raw = np.nan_to_num(delay_raw, nan=0.0)
    return dict(
        n_links=int(len(g)),
        n_loaded=int(k.sum()),
        length_km=float(L.sum() / 1000.0),
        length_loaded_km=float(L[k].sum() / 1000.0),
        vol=float(v.sum()),
        ratio_vw=float((v[k] * (tt[k] / ff[k])).sum() / v[k].sum()) if k.any() else np.nan,
        qratio_vw=float((v[k] * (fc[k] / ff[k])).sum() / v[k].sum()) if k.any() else np.nan,
        delay_corr_h=float(delay.sum()),
        delay_raw_h=float(delay_raw.sum()),
        delay_h=float(delay.sum() if quant == "corr" else delay_raw.sum()),
        sat_links=int((v >= cap * 0.9999).sum()),
    )


def decompose(m: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    rows = []
    for rt, g in m.groupby("road_type", observed=True):
        d = group_metrics(g, SIM_WINDOW, "corr")
        d["road_type"] = rt
        rows.append(d)
    t = pd.DataFrame(rows).sort_values("delay_corr_h", ascending=False).reset_index(drop=True)
    tot_c, tot_r = float(t.delay_corr_h.sum()), float(t.delay_raw_h.sum())
    t["share_corr_pct"] = 100.0 * t.delay_corr_h / tot_c
    t["share_raw_pct"] = 100.0 * t.delay_raw_h / tot_r
    cols = ["road_type", "n_links", "n_loaded", "length_km", "vol", "ratio_vw",
            "qratio_vw", "delay_raw_h", "delay_corr_h", "share_corr_pct", "share_raw_pct", "sat_links"]
    t = t[cols]
    tot = dict(total_delay_corr_h=tot_c, total_delay_raw_h=tot_r)
    return t, tot


def caliber_matrix(m: pd.DataFrame) -> pd.DataFrame:
    rows = []
    n_all_links = int(len(m))
    n_all_len_km = float(m.length.sum() / 1000.0)
    for quant in ("corr", "raw"):
        for hour in READ_HOURS:
            agg = {rt: group_metrics(g, hour, quant) for rt, g in m.groupby("road_type", observed=True)}
            svc = agg.get(SERVICE, None)
            if svc is None:
                continue
            tot_time = sum(a["delay_h"] for a in agg.values())
            for incl in ("loaded", "all"):
                if incl == "loaded":
                    s_cnt, t_cnt = svc["n_loaded"], sum(a["n_loaded"] for a in agg.values())
                    s_len, t_len = svc["length_loaded_km"], sum(a["length_loaded_km"] for a in agg.values())
                else:
                    s_cnt, t_cnt = svc["n_links"], n_all_links
                    s_len, t_len = svc["length_km"], n_all_len_km
                s_vol, t_vol = svc["vol"], sum(a["vol"] for a in agg.values())
                for expo, (sv, tv) in {
                    "time": (svc["delay_h"], tot_time),
                    "count": (s_cnt, t_cnt),
                    "distance": (s_len, t_len),
                    "volume": (s_vol, t_vol),
                }.items():
                    share = (sv / tv) if tv else np.nan
                    rows.append(dict(
                        caliber_id=f"{quant}|{hour}|{incl}|{expo}",
                        quantization=quant, hour=hour, inclusion=incl, exposure=expo,
                        service_value=float(sv), total_value=float(tv), share=float(share),
                        note="canonical" if (quant == "corr" and hour == SIM_WINDOW and incl == "loaded" and expo == "time") else "",
                    ))
    return pd.DataFrame(rows)


def exposure_faces(cal: pd.DataFrame) -> pd.DataFrame:
    sub = cal[(cal.quantization == "corr") & (cal.hour == SIM_WINDOW) & (cal.inclusion == "loaded")]
    rows = []
    for _, r in sub.iterrows():
        rows.append(dict(face=r.exposure, service_value=r.service_value,
                         total_value=r.total_value, share_pct=100.0 * r.share))
    return pd.DataFrame(rows)


def q1_binding(m: pd.DataFrame, dec: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    s = m[m.road_type == SERVICE].copy()
    v = s[f"HRS{SIM_WINDOW}avg"].fillna(0).to_numpy(float)
    tt = s[f"TRAVELTIME{SIM_WINDOW}avg"].to_numpy(float)
    ff = s["ff_s"].to_numpy(float)
    fc = s["ff_ceil_s"].to_numpy(float)
    cap = s["capacity"].to_numpy(float)
    k = (v > 0) & np.isfinite(tt) & (ff > 0)
    vc = np.where(cap > 0, v / cap, np.nan)
    dly = np.nan_to_num(np.where(k, v * np.clip(tt - fc, 0, None), 0.0) / 3600.0)
    sat_mask = k & (vc >= 0.9999)
    tot = float(dly.sum())
    sat_delay = float(dly[sat_mask].sum())
    sat_delay_share = sat_delay / tot if tot else np.nan
    p50 = float(np.nanpercentile(vc[k], 50)); p90 = float(np.nanpercentile(vc[k], 90)); pmax = float(np.nanmax(vc[k]))
    n_sat = int(sat_mask.sum())
    n_loaded = int(k.sum())
    rows = [
        dict(metric="service_loaded_links", value=n_loaded, note="v>0"),
        dict(metric="vc_p50", value=p50, note="已载流 service"),
        dict(metric="vc_p90", value=p90, note="已载流 service"),
        dict(metric="vc_max", value=pmax, note="已载流 service"),
        dict(metric="sat_links_n", value=n_sat, note="v/c>=0.9999"),
        dict(metric="sat_links_share", value=n_sat / n_loaded if n_loaded else np.nan, note="饱和链路占已载流比例"),
        dict(metric="sat_delay_share", value=sat_delay_share, note="★饱和链路承载的 service 延误份额"),
        dict(metric="service_delay_corr_h", value=tot, note="canonical 8-9"),
    ]
    return pd.DataFrame(rows), dict(sat_delay_share=sat_delay_share, n_sat=n_sat, n_loaded=n_loaded,
                                    vc_p50=p50, vc_p90=p90, vc_max=pmax)


def q1_length(m: pd.DataFrame) -> pd.DataFrame:
    s = m[m.road_type == SERVICE].copy()
    v = s[f"HRS{SIM_WINDOW}avg"].fillna(0).to_numpy(float)
    tt = s[f"TRAVELTIME{SIM_WINDOW}avg"].to_numpy(float)
    ff = s["ff_s"].to_numpy(float)
    fc = s["ff_ceil_s"].to_numpy(float)
    cap = s["capacity"].to_numpy(float)
    k = (v > 0) & np.isfinite(tt) & (ff > 0)
    s = s.assign(_v=v, _tt=tt, _ff=ff, _fc=fc, _vc=np.where(cap > 0, v / cap, np.nan),
                 _dly=np.nan_to_num(np.where(k, v * np.clip(tt - fc, 0, None), 0.0) / 3600.0), _k=k)
    bins = [0, 5, 8.9, 15, 30, 60, 1e12]
    labs = ["<=5", "5-8.9", "8.9-15", "15-30", "30-60", ">60"]
    s["bucket"] = pd.cut(s["length"], bins=bins, labels=labs)
    tot = float(s["_dly"].sum())
    out = []
    for lb in labs:
        g = s[(s.bucket == lb) & s._k]
        if len(g) == 0:
            out.append(dict(bucket=lb, n=0, vol=0.0, delay_h=0.0, delay_share_pct=0.0,
                            ff_med_s=np.nan, vc_med=np.nan, per_veh_s=np.nan))
            continue
        dly = g["_dly"].sum()
        per_veh = float((np.clip(g._tt - g._fc, 0, None) * g._v).sum() / g._v.sum())
        out.append(dict(bucket=lb, n=int(len(g)), vol=float(g._v.sum()), delay_h=float(dly),
                        delay_share_pct=100.0 * float(dly) / tot if tot else np.nan,
                        ff_med_s=float(np.median(g._ff)), vc_med=float(np.nanmedian(g._vc)),
                        per_veh_s=per_veh))
    return pd.DataFrame(out)


def q1_concentration(m: pd.DataFrame) -> pd.DataFrame:
    s = m[m.road_type == SERVICE]
    v = s[f"HRS{SIM_WINDOW}avg"].fillna(0).to_numpy(float)
    tt = s[f"TRAVELTIME{SIM_WINDOW}avg"].to_numpy(float)
    ff = s["ff_s"].to_numpy(float)
    fc = s["ff_ceil_s"].to_numpy(float)
    k = (v > 0) & np.isfinite(tt) & (ff > 0)
    dly = np.nan_to_num(np.where(k, v * np.clip(tt - fc, 0, None), 0.0) / 3600.0)
    tot = float(dly.sum())
    d = np.sort(dly)[::-1]
    n = len(d)
    scopes = {"top10": 10, "top100": 100, "top1pct": max(1, int(n * 0.01)), "all": n}
    rows = []
    for name, kk in scopes.items():
        cum = float(d[:kk].sum())
        rows.append(dict(rank_scope=name, share_pct=100.0 * cum / tot if tot else np.nan, cum_delay_h=cum))
    # Gini
    x = np.sort(np.abs(dly))
    if x.sum() > 0:
        nn = len(x)
        gini = float((2 * np.arange(1, nn + 1) - nn - 1).dot(x) / (nn * x.sum()))
    else:
        gini = np.nan
    rows.append(dict(rank_scope="gini", share_pct=np.nan, cum_delay_h=np.nan))
    return pd.DataFrame(rows), dict(gini=gini, top10=rows[0]["share_pct"], top100=rows[1]["share_pct"])


def q3_provenance(m: pd.DataFrame) -> pd.DataFrame:
    rows = []
    all_ok = []
    for rt, g in m.groupby("road_type", observed=True):
        unit = UNIT_CAP.get(rt, np.nan)
        pred = g["lanes"].to_numpy(float) * (unit if np.isfinite(unit) else np.nan)
        ok = np.abs(g["capacity"].to_numpy(float) - pred) < 1e-6
        ok = np.where(np.isfinite(pred), ok, False)
        all_ok.append((rt, float(np.mean(ok)), int(len(g))))
        rows.append(dict(
            road_type=rt, n=int(len(g)), cap_eq_unit_lanes_share=float(np.mean(ok)),
            lanes_set=json.dumps(sorted({float(x) for x in np.unique(g["lanes"])})),
            capacity_set=json.dumps(sorted({float(x) for x in np.unique(g["capacity"])})[:12]),
            freespeed_set=json.dumps(sorted({float(x) for x in np.unique(g["freespeed"])})[:12]),
        ))
    df = pd.DataFrame(rows).sort_values("n", ascending=False).reset_index(drop=True)
    svc = df[df.road_type == SERVICE]
    svc_share = float(svc.cap_eq_unit_lanes_share.iloc[0]) if len(svc) else float("nan")
    return df, dict(service_cap_exact=svc_share,
                    service_lanes_set=json.loads(svc.lanes_set.iloc[0]) if len(svc) else [],
                    service_freespeed_set=json.loads(svc.freespeed_set.iloc[0]) if len(svc) else [])


def qsim_override() -> pd.DataFrame:
    t = (ROOT / INPUTS["cfg"][0]).read_text(encoding="utf-8", errors="replace")

    def getp(key: str) -> str:
        m = re.search(r'name="%s"\s+value="([^"]*)"' % re.escape(key), t)
        return m.group(1) if m else "__MISSING__"

    rows = [
        dict(param="flowCapacityFactor", value=getp("flowCapacityFactor")),
        dict(param="storageCapacityFactor", value=getp("storageCapacityFactor")),
        dict(param="linkDynamics", value=getp("linkDynamics")),
        dict(param="snapshotStyle", value=getp("snapshotStyle")),
        dict(param="timeStepSize", value=getp("timeStepSize")),
    ]
    return pd.DataFrame(rows)


def decide_verdicts(bind: dict, cal: pd.DataFrame, prov: dict, qsim: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    # Q1
    sds = bind["sat_delay_share"]
    q1 = "CAPACITY_CONSTRAINT_DOMINANT" if (sds is not None and np.isfinite(sds)
                                            and sds >= Q1_DOMINANT_THRESHOLD) else "CAPACITY_CONSTRAINT_NOT_DOMINANT"
    # Q2
    tc = cal[(cal.quantization == "corr") & (cal.inclusion == "loaded") & (cal.exposure == "time")]
    tr = cal[(cal.quantization == "raw") & (cal.inclusion == "loaded") & (cal.exposure == "time")]
    corr_by_hour = {r.hour: r.share for _, r in tc.iterrows()}
    raw_by_hour = {r.hour: r.share for _, r in tr.iterrows()}
    hours_3 = [h for h in ("7-8", "8-9", "9-10") if h in corr_by_hour]
    vals = [corr_by_hour[h] for h in hours_3]
    in_band = all(Q2_BAND[0] <= x <= Q2_BAND[1] for x in vals) if vals else False
    rng = (max(vals) - min(vals)) if vals else np.nan
    gap = (corr_by_hour.get(SIM_WINDOW, np.nan) - raw_by_hour.get(SIM_WINDOW, np.nan))
    q2 = "CALIBER_STABLE" if (in_band and np.isfinite(rng) and rng <= Q2_RANGE_MAX
                              and np.isfinite(gap) and gap >= Q2_GAP_MIN) else "CALIBER_FRAGILE"
    # Q3
    facs = {r.param: r.value for _, r in qsim.iterrows()}
    no_override = (facs.get("flowCapacityFactor") == "1.0" and facs.get("storageCapacityFactor") == "1.0")
    exact = prov["service_cap_exact"]
    q3 = "SERVICE_PARAMS_DERIVED" if (np.isfinite(exact) and exact >= Q3_EXACT_MIN and no_override) else "SERVICE_PARAMS_FREE_KNOB"
    rows = [
        dict(question="Q1_service_delay_capacity_constraint",
             verdict=q1, rule="sat_delay_share >= 0.50",
             evidence=json.dumps({"sat_delay_share": sds, "n_sat": bind["n_sat"],
                                  "n_loaded": bind["n_loaded"], "vc_p50": bind["vc_p50"]})),
        dict(question="Q2_94pct_caliber_stability",
             verdict=q2, rule="corr share in [0.85,0.99] for 7-8/8-9/9-10 and range<=0.05 and (corr-raw)>=0.10",
             evidence=json.dumps({"corr_by_hour": corr_by_hour, "raw_by_hour": raw_by_hour,
                                  "range": rng, "gap_8_9": gap})),
        dict(question="Q3_service_param_nature",
             verdict=q3, rule="cap==unit_cap*permlanes exact>=0.999999 and qsim factors==1.0",
             evidence=json.dumps({"service_cap_exact": exact,
                                  "service_lanes_set": prov["service_lanes_set"],
                                  "service_freespeed_set": prov["service_freespeed_set"],
                                  "qsim": facs})),
    ]
    return pd.DataFrame(rows), dict(Q1=q1, Q2=q2, Q3=q3,
                                    corr_by_hour=corr_by_hour, raw_by_hour=raw_by_hour,
                                    q2_range=rng, q2_gap=gap, q3_exact=exact, qsim_facs=facs)


# ---------------------------------------------------------------------------
def flow_blind_ast(script_path: Path) -> tuple[bool, str]:
    """零仿真静态检查：确认脚本未 import matsim/java、未 spawn java。"""
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
        ast_ok = True
        det = "AST_PARSE_PASS"
    except SyntaxError as e:
        return False, f"AST_PARSE_FAIL: {e}"
    try:
        compile(src, str(script_path), "exec")
        det += "; COMPILE_PASS"
    except Exception as e:  # pragma: no cover
        return False, f"{det}; COMPILE_FAIL: {e}"
    return ast_ok, det


def referenced_check_keys(script_path: Path) -> tuple[list[str], str]:
    src = script_path.read_text(encoding="utf-8", errors="replace")
    tree = ast.parse(src)
    keys: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Subscript) and isinstance(node.value, ast.Name):
            if node.value.id in ("r", "row") and isinstance(node.slice, ast.Constant) and isinstance(node.slice.value, str):
                keys.add(node.slice.value)
    return sorted(keys), ""


def checks(payload: dict, ctx: dict) -> list[dict]:
    rows: list[dict] = []

    def G(gate_id: str, ok: bool, detail: str) -> None:
        rows.append(dict(gate_id=gate_id, pass_=bool(ok), detail=detail[:400]))

    blocked = ctx.get("blocked", False)
    NA = "NOT_EVALUATED: preflight blocked"
    inp, refs = ctx["inp"], ctx["refs"]
    errs = ctx["preflight_errors"]

    G("7.9G0.01_PREREG_FROZEN_AND_EMBEDDED",
      ctx["prereg_disk_sha"] == PREREG_SHA and ctx["prereg_disk_bytes"] == PREREG_BYTES,
      f"disk={ctx['prereg_disk_sha'][:16]}({ctx['prereg_disk_bytes']}B) embedded={PREREG_SHA[:16]}({PREREG_BYTES}B)")
    ok_comp, det_comp = ast_compile_ok(Path(__file__))
    ok_blind, det_blind = flow_blind_ast(Path(__file__))
    G("7.9G0.02_SCRIPT_AST_COMPILE", ok_comp, det_comp)
    G("7.9G0.03_ZERO_SIMULATION", ok_blind, det_blind)
    G("7.9G0.04_INPUT_MANIFEST_COMPLETE",
      all(v.get("exists") and v.get("size_ok") and v.get("sha_ok") for v in inp["inputs"].values()),
      ";".join(f"{k}:{'ok' if v.get('sha_ok') else 'BAD'}" for k, v in inp["inputs"].items()))

    if blocked:
        G("7.9G0.05_LINKSTATS_154_COLUMNS", False, ctx.get("hdr_detail", NA))
        G("7.9G0.06_NETWORK_JOIN_COMPLETE", False, NA)
        G("7.9G0.07_LINKSTATS_JOIN_COMPLETE", False, NA)
        G("7.9G0.08_TRIPLE_FIELD_IDENTITY", False, NA)
        G("7.9G0.09_REF_LINKSTATS_BYTE_IDENTICAL",
          inp["inputs"].get("ls_final", {}).get("sha256") == inp["inputs"].get("ls_viz_ref", {}).get("sha256"),
          f"final={str(inp['inputs'].get('ls_final',{}).get('sha256'))[:16]} viz={str(inp['inputs'].get('ls_viz_ref',{}).get('sha256'))[:16]}")
        for gid in ["7.9G0.10_CANONICAL_RECOMPUTE_MATCHES_7E7E",
                    "7.9G0.11_Q1_CAPACITY_BINDING_REPORTED",
                    "7.9G0.12_Q1_CONCENTRATION_REPORTED",
                    "7.9G0.13_Q1_LENGTH_CONTROL_REPORTED",
                    "7.9G0.14_Q2_CALIBER_MATRIX_COMPLETE",
                    "7.9G0.15_Q2_RAW_VS_CORR_DECLARED",
                    "7.9G0.16_Q2_STABILITY_BAND_CONSISTENT",
                    "7.9G0.17_Q3_CAPACITY_PROVENANCE_EXACT",
                    "7.9G0.18_Q3_QSIM_OVERRIDE_NONE",
                    "7.9G0.19_Q3_KNOB_CLASSIFICATION_SINGLE",
                    "7.9G0.20_TRACEABILITY_FIELDS_COMPLETE",
                    "7.9G0.21_NO_WINDOW_MIXING"]:
            G(gid, False, NA)
        # 22 走 writeback，仍在下方统一处理
        writeback_and_tail(rows, payload, ctx, blocked=True)
        return rows

    G("7.9G0.05_LINKSTATS_154_COLUMNS", ctx["hdr_ok"], ctx["hdr_detail"])
    G("7.9G0.06_NETWORK_JOIN_COMPLETE", ctx["net_join_missing"] == 0,
      f"missing={ctx['net_join_missing']}")
    G("7.9G0.07_LINKSTATS_JOIN_COMPLETE", ctx["ls_join_missing"] == 0,
      f"missing={ctx['ls_join_missing']}")
    G("7.9G0.08_TRIPLE_FIELD_IDENTITY", ctx["triple_max_delta"] < TRIPLE_TOL,
      f"max|d|={ctx['triple_max_delta']:.3g}")
    G("7.9G0.09_REF_LINKSTATS_BYTE_IDENTICAL",
      inp["inputs"].get("ls_final", {}).get("sha256") == inp["inputs"].get("ls_viz_ref", {}).get("sha256"),
      f"final={str(inp['inputs'].get('ls_final',{}).get('sha256'))[:16]} viz={str(inp['inputs'].get('ls_viz_ref',{}).get('sha256'))[:16]}")

    svc_share = ctx["service_share_corr"]
    rel = abs(svc_share - REF_SERVICE_SHARE_7E7E) / REF_SERVICE_SHARE_7E7E
    G("7.9G0.10_CANONICAL_RECOMPUTE_MATCHES_7E7E", rel <= CANON_REL_TOL,
      f"recomputed={svc_share:.10f} ref={REF_SERVICE_SHARE_7E7E:.10f} rel={rel:.3g}")

    b = ctx["bind"]
    G("7.9G0.11_Q1_CAPACITY_BINDING_REPORTED",
      np.isfinite(b["vc_p50"]) and np.isfinite(b["vc_p90"]) and np.isfinite(b["vc_max"]),
      f"vc p50={b['vc_p50']:.4f} p90={b['vc_p90']:.4f} max={b['vc_max']:.4f} sat_n={b['n_sat']}")

    c = ctx["conc"]
    ord_ok = (c["top10"] <= c["top100"] <= 100.0 + 1e-9) and (c["top10"] < 100.0)
    G("7.9G0.12_Q1_CONCENTRATION_REPORTED", ord_ok,
      f"top10={c['top10']:.4f}% top100={c['top100']:.4f}% gini={c['gini']:.4f}")

    lb = ctx["length_buckets"]
    G("7.9G0.13_Q1_LENGTH_CONTROL_REPORTED",
      len(lb) == 6 and int(lb.n.sum()) > 0, f"buckets={len(lb)} merged_n={int(lb.n.sum())}")

    cal = ctx["caliber"]
    G("7.9G0.14_Q2_CALIBER_MATRIX_COMPLETE",
      len(cal) == ctx["caliber_expected"] and int(cal.share.isna().sum()) == 0,
      f"rows={len(cal)} expected={ctx['caliber_expected']} nan={int(cal.share.isna().sum())}")

    rr = ctx["raw_by_hour"]; cc = ctx["corr_by_hour"]
    c8 = cc.get(SIM_WINDOW, np.nan); r8 = rr.get(SIM_WINDOW, np.nan)
    gap = c8 - r8
    G("7.9G0.15_Q2_RAW_VS_CORR_DECLARED",
      np.isfinite(c8) and np.isfinite(r8) and abs(gap) > 0,
      f"corr={c8:.4f} raw={r8:.4f} |gap|={abs(gap):.4f} (口径敏感性存在性)")

    hours_3 = [h for h in ("7-8", "8-9", "9-10") if h in cc]
    vals = [cc[h] for h in hours_3]
    rng = (max(vals) - min(vals)) if vals else np.nan
    band_ok = (len(hours_3) == 3 and all(np.isfinite(v) for v in vals)
               and all(Q2_BAND[0] <= v <= Q2_BAND[1] for v in vals) and np.isfinite(rng) and rng <= Q2_RANGE_MAX)
    q2_consistent = (payload.get("verdict_Q2") == ("CALIBER_STABLE" if band_ok else "CALIBER_FRAGILE"))
    G("7.9G0.16_Q2_STABILITY_BAND_CONSISTENT", q2_consistent,
      f"hours={hours_3} shares={[round(v,4) for v in vals]} range={rng:.4f} "
      f"band_ok={band_ok} verdict={payload.get('verdict_Q2')}")

    G("7.9G0.17_Q3_CAPACITY_PROVENANCE_EXACT", ctx["q3_exact"] >= Q3_EXACT_MIN,
      f"service cap==unit_cap*permlanes share={ctx['q3_exact']:.8f}")
    facs = ctx["qsim_facs"]
    G("7.9G0.18_Q3_QSIM_OVERRIDE_NONE",
      facs.get("flowCapacityFactor") == "1.0" and facs.get("storageCapacityFactor") == "1.0",
      f"flowCap={facs.get('flowCapacityFactor')} storageCap={facs.get('storageCapacityFactor')}")

    q1v, q2v, q3v = payload["verdict_Q1"], payload["verdict_Q2"], payload["verdict_Q3"]
    G("7.9G0.19_Q3_KNOB_CLASSIFICATION_SINGLE",
      q1v in VERDICT_Q1_SET and q2v in VERDICT_Q2_SET and q3v in VERDICT_Q3_SET,
      f"Q1={q1v} Q2={q2v} Q3={q3v}")

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
    G("7.9G0.20_TRACEABILITY_FIELDS_COMPLETE", not miss_cols, json.dumps(miss_cols)[:300])

    bad_hours = [h for h in READ_HOURS if h not in ("7-8", "8-9", "9-10", "10-11")]
    agg_cols = [c for c in ctx.get("ls_cols", []) if "0-24" in c]
    G("7.9G0.21_NO_WINDOW_MIXING", (not bad_hours) and (SIM_WINDOW in READ_HOURS) and (not agg_cols),
      f"read_hours={READ_HOURS} sim_window={SIM_WINDOW} bad={bad_hours} aggregate_cols_in_read_set={agg_cols}")

    writeback_and_tail(rows, payload, ctx, blocked=False)
    return rows


def writeback_and_tail(rows: list[dict], payload: dict, ctx: dict, blocked: bool) -> None:
    def G(gate_id: str, ok: bool, detail: str) -> None:
        rows.append(dict(gate_id=gate_id, pass_=bool(ok), detail=detail[:400]))

    out = ctx["out"]
    # 22 WRITEBACK
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
    G("7.9G0.22_WRITEBACK_VERIFICATION", set_ok and not byte_bad,
      f"manifest_set_ok={man_set | {MANIFEST_NAME, CLOSURE_NAME} == declared} "
      f"closure_set_ok={clo_set | {CLOSURE_NAME} == declared} "
      f"disk_set_ok={disk == declared} byte_mismatch={byte_bad} n_byte_compared={n_cmp}")

    stray = ctx.get("stray", [])
    G("7.9G0.23_STRAY_ISOLATION", not stray, f"stray={stray}")

    # --- 25 先求值（不 append），使门 24 的判据可计入它 ---
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
    g25_detail = f"checked=8 drift={drift}"

    # --- 24 终局状态三方一致（判据含 01..23 与 25，不含自身）---
    st_ck = STATUS_READY if (all(r["pass_"] for r in rows) and g25_ok) else STATUS_BLOCKED
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
            _want = float(ctx.get("service_share_corr", -99.0))
            sm_num_ok = abs(_got - _want) < 1e-9 and _want == _want
            sm_num_detail = f" summary_share={_got} expected={_want}"
        except Exception as e:  # pragma: no cover
            sm_num_ok, sm_num_detail = False, f" summary_parse_err={e}"
    G("7.9G0.24_TERMINAL_STATE_THREE_WAY",
      st_ck == st_sm == st_rp and st_ck in (STATUS_READY, STATUS_BLOCKED) and sm_num_ok,
      f"checks={st_ck} summary={st_sm} report={st_rp}{sm_num_detail}")

    G("7.9G0.25_NON_7_9G_ARTIFACTS_UNCHANGED", g25_ok, g25_detail)


# ---------------------------------------------------------------------------
def build_manifest(out: Path, ctx: dict) -> dict:
    """manifest 最后生成；不自哈希，且不含 closure（否则 manifest↔closure 互引用 2-循环，永不收敛）。"""
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
    for k, v in (("status_checks", status), ("status_summary", status), ("status_report", status)):
        rows.append(dict(kind=k, name="", exists=True, size_bytes=0, sha256=v))
    df = pd.DataFrame(rows)
    ok = all(r["exists"] for _, r in df.iterrows())
    df = pd.concat([df, pd.DataFrame([dict(kind="closure_verdict", name="", exists=ok,
                                           size_bytes=int(n_art), sha256="OK" if ok else "FAIL")])],
                   ignore_index=True)
    return df, ok


def write_summary(out: Path, payload: dict, rows: list[dict]) -> None:
    s = {
        "step": STEP_ID,
        "status": payload["status"],
        "closure": payload.get("closure", ""),
        "gates_total": len(rows),
        "gates_pass": int(sum(1 for r in rows if r["pass_"])),
        "verdict_Q1": payload["verdict_Q1"],
        "verdict_Q2": payload["verdict_Q2"],
        "verdict_Q3": payload["verdict_Q3"],
        "service_share_corr_pct_8_9": payload["service_share_corr"],
        "service_share_raw_pct_8_9": payload["service_share_raw"],
        "total_delay_corr_h": payload["total_delay_corr_h"],
        "sat_delay_share": payload["sat_delay_share"],
        "prereg_sha256": PREREG_SHA,
    }
    (out / SUMMARY_NAME).write_bytes(json.dumps(s, ensure_ascii=False, indent=2).encode("utf-8"))


def write_report(out: Path, payload: dict, rows: list[dict]) -> str:
    L = []
    L.append(f"# STEP 7.9G-0 — `service` 延误机制 · R0 结构审计（零仿真 / 只读）\n")
    L.append(f"**STATUS: {payload['status']}**")
    L.append(f"**CLOSURE: {payload.get('closure','')}**\n")
    L.append(f"- 门禁：**{sum(1 for r in rows if r['pass_'])}/{len(rows)}**")
    L.append(f"- prereg：`{PREREG_SHA}`（{PREREG_BYTES} B）")
    L.append(f"- Q1 判决：`{payload['verdict_Q1']}`")
    L.append(f"- Q2 判决：`{payload['verdict_Q2']}`")
    L.append(f"- Q3 判决：`{payload['verdict_Q3']}`\n")
    L.append("## 关键数字（第一手复算）\n")
    L.append(f"- 全网 `delay_corr_h`（08-09）= **{payload['total_delay_corr_h']:.6f}**")
    L.append(f"- `service` 份额（量化校正 / canonical）= **{payload['service_share_corr']:.6f}%**")
    L.append(f"- `service` 份额（未校正 raw）= **{payload['service_share_raw']:.6f}%**")
    L.append(f"- 饱和链路承载的 service 延误份额 = **{payload['sat_delay_share']*100:.4f}%**\n")
    L.append("## 口径矩阵（time 面，8-9）\n")
    L.append("| quantization | 份额 % |\n|---|---|")
    L.append(f"| corr | {payload['corr_by_hour'].get(SIM_WINDOW, float('nan'))*100:.4f} |")
    L.append(f"| raw | {payload['raw_by_hour'].get(SIM_WINDOW, float('nan'))*100:.4f} |\n")
    L.append("## 门禁明细\n")
    L.append("| gate | pass | detail |")
    L.append("|---|---|---|")
    for r in rows:
        L.append(f"| `{r['gate_id']}` | {'✅' if r['pass_'] else '❌'} | {r['detail']} |")
    txt = "\n".join(L) + "\n"
    (out / REPORT_NAME).write_bytes(txt.encode("utf-8"))


def _isolation_stray(out: Path) -> list[str]:
    allowed = set(ARTIFACT_NAMES)
    if not out.exists():
        return []
    return sorted(f.name for f in out.iterdir() if f.is_file() and f.name not in allowed)


# ---------------------------------------------------------------------------
def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(OUT_DEFAULT))
    ap.add_argument("--ref-dir", default=str(REF_DEFAULT))
    args = ap.parse_args()
    out = Path(args.out)
    ref_dir = Path(args.ref_dir)
    out.mkdir(parents=True, exist_ok=True)
    print("=" * 78)
    print(f"STEP {STEP_ID} — service delay mechanism R0 (read-only, zero-simulation)")
    print("=" * 78)

    # --- preflight（不提前 return；BLOCKED 也须完整物化）---
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

    payload: dict = {
        "status": STATUS_BLOCKED, "closure": "", "report_status": STATUS_BLOCKED,
        "verdict_Q1": "NOT_EVALUATED", "verdict_Q2": "NOT_EVALUATED", "verdict_Q3": "NOT_EVALUATED",
        "service_share_corr": 0.0, "service_share_raw": 0.0,
        "total_delay_corr_h": 0.0, "sat_delay_share": float("nan"),
        "corr_by_hour": {}, "raw_by_hour": {},
    }
    ctx: dict = {
        "out": out, "ref_dir": ref_dir, "inp": inp, "refs": refs,
        "preflight_errors": preflight_errors, "blocked": blocked,
        "hdr_ok": hdr_ok, "hdr_detail": hdr_detail,
        "prereg_disk_sha": prereg_disk_sha, "prereg_disk_bytes": prereg_disk_bytes,
        "net_join_missing": -1, "ls_join_missing": -1, "triple_max_delta": float("inf"),
        "service_share_corr": 0.0, "service_share_raw": 0.0, "total_delay_corr_h": 0.0,
        "bind": {"sat_delay_share": float("nan"), "n_sat": 0, "n_loaded": 0,
                 "vc_p50": float("nan"), "vc_p90": float("nan"), "vc_max": float("nan")},
        "conc": {"gini": float("nan"), "top10": float("nan"), "top100": float("nan")},
        "length_buckets": pd.DataFrame(columns=["bucket", "n"]),
        "caliber": pd.DataFrame(columns=["share"]), "caliber_expected": 0,
        "raw_by_hour": {}, "corr_by_hour": {},
        "q3_exact": float("nan"), "qsim_facs": {},
        "manifest_records": {}, "closure_records": {}, "stray": [], "ls_cols": [],
    }

    if not blocked:
        d = load_all()
        m = d["m"]
        ctx["ls_cols"] = d.get("ls_cols", [])
        ctx["net_join_missing"] = int(m.road_type.isna().sum())
        ctx["ls_join_missing"] = int(m[f"HRS{SIM_WINDOW}avg"].isna().sum())
        common = m.dropna(subset=["LENGTH", "FREESPEED", "CAPACITY", "length", "freespeed", "capacity"])
        ctx["triple_max_delta"] = float(max(
            np.abs(common["length"] - common["LENGTH"]).max(),
            np.abs(common["freespeed"] - common["FREESPEED"]).max(),
            np.abs(common["capacity"] - common["CAPACITY"]).max(),
        )) if len(common) else float("inf")

        dec, tot = decompose(m)
        cal = caliber_matrix(m)
        faces = exposure_faces(cal)
        bind_df, bind = q1_binding(m, dec)
        lb = q1_length(m)
        conc_df, conc = q1_concentration(m)
        prov_df, prov = q3_provenance(m)
        qsim_df = qsim_override()

        payload.update({"total_delay_corr_h": tot["total_delay_corr_h"], "total_delay_raw_h": tot["total_delay_raw_h"]})
        svc_row = dec[dec.road_type == SERVICE]
        ctx["service_share_corr"] = float(svc_row.share_corr_pct.iloc[0])
        ctx["service_share_raw"] = float(svc_row.share_raw_pct.iloc[0])
        payload["service_share_corr"] = ctx["service_share_corr"]
        payload["service_share_raw"] = ctx["service_share_raw"]
        ctx["bind"], ctx["conc"], ctx["length_buckets"] = bind, conc, lb
        ctx["caliber"], ctx["caliber_expected"] = cal, 2 * len(READ_HOURS) * 2 * 4
        ctx["q3_exact"], ctx["qsim_facs"] = prov["service_cap_exact"], {r.param: r.value for _, r in qsim_df.iterrows()}

        vdf, vinfo = decide_verdicts(bind, cal, prov, qsim_df)
        ctx["raw_by_hour"], ctx["corr_by_hour"] = vinfo["raw_by_hour"], vinfo["corr_by_hour"]
        payload.update({"verdict_Q1": vinfo["Q1"], "verdict_Q2": vinfo["Q2"], "verdict_Q3": vinfo["Q3"],
                        "sat_delay_share": bind["sat_delay_share"],
                        "corr_by_hour": vinfo["corr_by_hour"], "raw_by_hour": vinfo["raw_by_hour"]})

        # 先写所有分析产物（checks 之后算一次）
        dec.to_csv(out / "g0_roadtype_delay_decomposition.csv", index=False, encoding="utf-8-sig")
        cal.to_csv(out / "g0_caliber_matrix.csv", index=False, encoding="utf-8-sig")
        faces.to_csv(out / "g0_exposure_faces.csv", index=False, encoding="utf-8-sig")
        bind_df.to_csv(out / "g0_service_capacity_binding.csv", index=False, encoding="utf-8-sig")
        lb.to_csv(out / "g0_service_length_buckets.csv", index=False, encoding="utf-8-sig")
        conc_df.to_csv(out / "g0_service_concentration.csv", index=False, encoding="utf-8-sig")
        prov_df.to_csv(out / "g0_parameter_provenance.csv", index=False, encoding="utf-8-sig")
        qsim_df.to_csv(out / "g0_qsim_override.csv", index=False, encoding="utf-8-sig")
        vdf.to_csv(out / "g0_verdicts.csv", index=False, encoding="utf-8-sig")
        print(f"  loaded in {d['secs']:.1f}s | service share(corr)={ctx['service_share_corr']:.6f}% "
              f"raw={ctx['service_share_raw']:.6f}% | Q1={vinfo['Q1']} Q2={vinfo['Q2']} Q3={vinfo['Q3']}")

    # --- 不动点循环 ---
    prev_state = None
    prev_closure = ""
    converged = False
    iterations = 0
    for iterations in range(1, 8):
        STATUS["checks_rows"] = []
        rows = checks(payload, ctx)
        STATUS["checks_rows"] = rows
        core = [r for r in rows if not r["gate_id"].startswith("7.9G0.24_")]
        all_pass = all(r["pass_"] for r in core)
        status = STATUS_READY if (all_pass and not blocked) else STATUS_BLOCKED
        payload["status"] = status
        payload["closure"] = prev_closure
        pd.DataFrame(rows).rename(columns={"pass_": "pass"}).to_csv(
            out / CHECKS_NAME, index=False, encoding="utf-8-sig")

        payload["report_status"] = status
        write_report(out, payload, rows)
        write_summary(out, payload, rows)

        manifest = build_manifest(out, ctx)
        ctx["manifest_records"] = manifest["artifacts"]
        (out / MANIFEST_NAME).write_bytes(json.dumps(manifest, ensure_ascii=False, indent=2).encode("utf-8"))

        closure_df, closure_ok = build_closure(out, status, manifest)
        ctx["closure_records"] = {r["name"]: r for _, r in closure_df.iterrows()
                                  if r["kind"] == "artifact"}
        closure_df.to_csv(out / CLOSURE_NAME, index=False, encoding="utf-8-sig")
        final_closure = "OK" if closure_ok else "CLOSURE_FAILED"
        ctx["stray"] = _isolation_stray(out)

        state = (
            sha256_file(out / CHECKS_NAME), sha256_file(out / REPORT_NAME),
            sha256_file(out / SUMMARY_NAME), sha256_file(out / MANIFEST_NAME),
            sha256_file(out / CLOSURE_NAME), status, final_closure,
        )
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
