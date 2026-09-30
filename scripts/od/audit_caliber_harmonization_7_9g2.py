#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Step 7.9G-2 — Caliber Harmonization Audit (RFC: PREREG_7_9G2.md, frozen).

零仿真 / 只读 / 仅诊断。

逐条实现冻结 prereg（sha 6df55c42…）的 §6 25 门、§9 16 件产物、§7 判决闭集、
§10 BLOCKED 物化顺序。

规范口径（继承 G-0 / G-1 canonical，逐位复现）
------------------------------------------------
    ff_s         = runtime.length / runtime.freespeed      （★不是 src_copy.length_m/(v/3.6)）
    ff_ceil_s    = ceil(ff_s − 1e-9)
    delay_corr_h = Σ_{vol>0} vol · max(0, TT8-9avg − ff_ceil_s) / 3600
    distance     = Σ runtime.length / 1000                 （★src_copy.length_m 漂移 3e-4~1.4e-3 km）
    U_loaded     = {link : HRS8-9avg > 0}
    U_any        = net_links_runtime ∩ src_copy            （= 693,575 = linkstats 行数）
    D0=ALL ⊃ D1=SVC ⊃ D2=EP_SVC；EP_SVC := service ∧ link ∈ (home ∪ work)（pop activity link）
    集中度主仪器 = 覆盖率分数 f_t = k_t / n_scope, t ∈ {50,90,99}；⛔ Gini 不得作判据。

不调用 MATSim / Java；不写任何冻结件；只写 --out-dir。
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
import traceback
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
STEP_ID = "7.9G-2"
STATUS_READY = "CALIBER_HARMONIZATION_R0_READY"
STATUS_BLOCKED = "CALIBER_HARMONIZATION_R0_BLOCKED"

PREREG_NAME = "PREREG_7_9G2.md"
PREREG_REL = "reports/caliber_harmonization_7_9g2/" + PREREG_NAME
PREREG_SHA = "6df55c428f1de8bc75d0e76267ccbe8f37ea0fe0c44c6d50dc9a5377f6d96260"
PREREG_BYTES = 22238

# §2 冻结输入（5 件）
INPUTS: dict = {
    "pop": (
        "matsim_final_7_6h/populations/pop_W01/population_lambda_0p075.xml.gz",
        8930574,
        "e96ed83ff59c0f5ecb50c9d9ff2d42a4b4bdbebf2bbfe81a1e0604fb94921fbd",
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

# §3 只读对照物（8 件，相对 --ref-dir = ROOT/reports）
REFS: dict = {
    "g0_summary": ("service_delay_mechanism_7_9g0/g0_summary.json", 522,
                   "d8c0b2f0c139005731de63b04ffee19be8265d7853e3839d2c5ec0ce9ab1166a"),
    "g0_concentration": ("service_delay_mechanism_7_9g0/g0_service_concentration.csv", 194,
                         "4898adcf77f90e95b107afab8d251026bd4aed12df990071de9268e0bd81bfed"),
    "g0_faces": ("service_delay_mechanism_7_9g0/g0_exposure_faces.csv", 252,
                 "61bb9eef77004e49732472d3b8e54891b7c597e1ec7dcf7e508cafd75b3abba8"),
    "g0_verdicts": ("service_delay_mechanism_7_9g0/g0_verdicts.csv", 1207,
                    "38c898f500a7219e60ca0b56aafd74d7fc5181b082a4aad5c037710c78211b8f"),
    "g1_exposure_faces": ("endpoint_access_absorption_7_9g1/g1_exposure_faces.csv", 293,
                          "c4043a67abb1f8da054dd16848d5a55e90ba3add2ef948db677d68885ae7933b"),
    "g1_endpoint_service_split": ("endpoint_access_absorption_7_9g1/g1_endpoint_service_split.csv", 355,
                                  "8a8119d1049ef0e3bd7bcfd8100b3073f0524b8d9ab460d8c4aec732acbe9914"),
    "g1_summary": ("endpoint_access_absorption_7_9g1/g1_summary.json", 1031,
                   "87e1b36fe7abc348c433c0c47aefdd397e0819f34bc7e33c3ae6d50dbdc8333d"),
    "g1_verdicts": ("endpoint_access_absorption_7_9g1/g1_verdicts.csv", 864,
                    "948b974b35e49fcc4c6d2e7df3d8ab5dfd06c664e9c8d3600028fd1d9f053401"),
}

GUARD_DIRS = [
    "reports/service_delay_mechanism_7_9g0",
    "reports/endpoint_access_absorption_7_9g1",
]

SIM_WINDOW = "8-9"
VOL_COL = "HRS8-9avg"
TT_COL = "TRAVELTIME8-9avg"
LINKSTATS_EXPECTED_COLS = 154
REQUIRED_LINKSTATS_FIELDS = ["LINK", "LENGTH", "FREESPEED", "CAPACITY", VOL_COL, TT_COL]
SERVICE = "service"

UD = "U_loaded"
UA = "U_any"
SCOPE_L = ("ALL_LOADED", "SERVICE_LOADED", "ENDPOINT_SERVICE_LOADED")
SCOPE_A = ("SERVICE_ANY", "ENDPOINT_SERVICE_ANY")
DENOM = ("D0", "D1", "D2")
FACES = ("time", "count", "distance", "volume")
FACE_ORDER = ("count", "distance", "volume", "time")      # O6：先 EXPOSURE 后 IMPACT
IMPACT_FACES = {"time"}
EXPOSURE_FACES = {"count", "distance", "volume"}
FACE_UNITS = {"time": "h_delay", "count": "links", "distance": "km", "volume": "veh"}
# 兼容两套历史命名：G-0 = 裸名（time/count/distance/volume）；G-1 = 带后缀名
FACE_G0_KEY = {"time": "time", "count": "count", "distance": "distance", "volume": "volume",
               "time_delay_corr_h": "time", "count_links_loaded": "count",
               "distance_km_loaded": "distance", "volume_veh": "volume"}

T_LEVELS = (50, 90, 99)
RATIO_CONC_MIN = 3.0
AGREEMENT_BAND_PP = 5.0
UNIVERSE_SPREAD_TOL_PP = 0.5
IMPOSSIBLE_SHARE_TOL = 1e-9

V_Q1 = {"DENOMINATOR_UNIFIED", "DENOMINATOR_SPLIT"}
V_Q2 = {"EXPOSURE_IMPACT_DECOUPLED", "EXPOSURE_IMPACT_COUPLED"}
V_Q3 = {"CONCENTRATION_AMPLIFIED", "CONCENTRATION_ATTENUATED", "CONCENTRATION_COMPARABLE"}
V_Q4 = {"FOUR_FACE_PARALLEL_REPORTING", "SINGLE_HEADLINE_ADMISSIBLE"}

# ---------------------------------------------------------------------------
OUTPUT_NAMES = [
    "g2_face_matrix.csv", "g2_share_matrix.csv", "g2_intensity_matrix.csv",
    "g2_universe_contrast.csv", "g2_denominator_audit.csv", "g2_concentration_curve.csv",
    "g2_concentration_verdict.csv", "g2_exposure_impact_gap.csv", "g2_reporting_template.md",
    "g2_caliber_crosswalk.csv", "g2_verdicts.csv", "g2_checks.csv", "g2_closure_check.csv",
    "g2_input_manifest.json", "g2_summary.json", "STEP7_9G2_REPORT.md",
]
ARTIFACT_NAMES = OUTPUT_NAMES + [PREREG_NAME]
CHECKS_NAME = "g2_checks.csv"
CLOSURE_NAME = "g2_closure_check.csv"
MANIFEST_NAME = "g2_input_manifest.json"
SUMMARY_NAME = "g2_summary.json"
REPORT_NAME = "STEP7_9G2_REPORT.md"
WRITEBACK_EXCLUDED = {MANIFEST_NAME, CLOSURE_NAME}

# 需要逐行声明 universe 的测量型产物（门 08）
UNIVERSE_TAGGED = ("face_matrix", "share_matrix", "intensity_matrix", "universe_contrast",
                   "denominator_audit", "concentration", "conc_verdict", "gap", "crosswalk", "verdicts")
NON_MEASUREMENT = ("g2_checks.csv", "g2_closure_check.csv", "g2_input_manifest.json",
                   "g2_summary.json", "g2_reporting_template.md", "STEP7_9G2_REPORT.md")

OUT_DEFAULT = r"D:\Luan\2026-05\2_Singapore\reports\caliber_harmonization_7_9g2"

BANNED_COL_TOKEN = re.compile(r"composite|index|score|weighted_sum|total_share", re.I)
BANNED_ID_TOKEN = ("composite", "weighted_sum", "total_share", "overall_score", "face_weight")
FORBIDDEN_IMPACT_COL = re.compile(
    r"impact[_\W]*(count|km|dist|vol|volume|link)|(count|km|dist|volume|link)[_\W]*impact", re.I)
CONST_K_TOKEN = re.compile(r"top[_\W]*\d|topk|top_k|fixed[_\W]*k", re.I)
ALLOWED_IMPORTS = {"__future__", "argparse", "ast", "gzip", "hashlib", "json", "math", "re", "sys",
                   "time", "traceback", "collections", "pathlib", "numpy", "pandas"}
BANNED_IMPORTS = {"subprocess", "jpype", "py4j", "requests", "urllib", "socket", "http",
                  "os", "shutil", "matplotlib"}
BANNED_CALL_ATTRS = {"system", "popen", "Popen", "urlopen", "check_call", "check_output"}
BANNED_CALL_NAMES = {"system", "popen", "Popen"}
K_RULE = "minimum k such that cumsum(sort(delay_corr_h desc)) >= t/100 * scope_total_delay_h"

ROOT = Path(r"D:\Luan\2026-05\2_Singapore")
REFS_DIR = ROOT / "reports"


# ---------------------------------------------------------------------------
def sha256_file(p: Path, chunk: int = 1 << 22) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        while True:
            b = f.read(chunk)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def walk_dir_shas(d: Path) -> dict:
    out: dict = {}
    if not d.exists():
        return out
    for p in sorted(d.rglob("*")):
        if p.is_file():
            out[str(p.relative_to(d)).replace("\\", "/")] = sha256_file(p)
    return out


def fsum_h(series) -> float:
    """时间面（IMPACT）规范聚合：正确舍入的精确求和。

    实测：pandas/numpy 的顺序求和与 G-0/G-1 存储值差 1 ulp（9.1e-13 / 4.5e-13）；
    只有 math.fsum 能在 D0/D1/D2 三档上与 G-0/G-1 **逐位**一致（atol=0 可达）。
    """
    return float(math.fsum(np.asarray(series, dtype=float).tolist()))


def read_ref(key: str) -> pd.DataFrame:
    """读只读对照物 CSV。

    ★必须 float_precision="round_trip"：pandas 默认的快速解析器会丢 1 ulp
    （实测 G-1 的 length_km 296.40227899999996 被解析成 296.402279），
    导致门 15/16 的 atol=0 出现假失败。
    """
    return pd.read_csv(REFS_DIR / REFS[key][0], encoding="utf-8-sig", float_precision="round_trip")


def preflight_inputs() -> tuple[dict, list[str]]:
    errs: list[str] = []
    info: dict = {}
    for name, (rel, size, sha) in INPUTS.items():
        p = ROOT / rel
        rec = {"path": rel, "exists": p.exists()}
        if not p.exists():
            errs.append(f"missing_input:{name}")
            info[name] = rec
            continue
        rec["size"] = p.stat().st_size
        rec["sha256"] = sha256_file(p)
        rec["size_ok"] = rec["size"] == size
        rec["sha_ok"] = rec["sha256"] == sha
        if not rec["size_ok"]:
            errs.append(f"input_size_mismatch:{name}")
        if not rec["sha_ok"]:
            errs.append(f"input_sha_mismatch:{name}")
        info[name] = rec
    if len(INPUTS) != 5:
        errs.append(f"input_manifest_count={len(INPUTS)}")
    return {"frozen_inputs": info, "count": len(INPUTS)}, errs


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
        rec["size_ok"] = rec["size"] == size
        rec["sha_ok"] = rec["sha256"] == sha
        if not rec["size_ok"]:
            errs.append(f"ref_size_mismatch:{name}")
        if not rec["sha_ok"]:
            errs.append(f"ref_sha_mismatch:{name}")
        out[name] = rec
    return {"references": out, "count": len(REFS)}, errs


def preflight_linkstats_header() -> tuple[list[str], list[str]]:
    errs: list[str] = []
    p = ROOT / INPUTS["ls_final"][0]
    if not p.exists():
        return [], ["missing_input:ls_final"]
    hdr = pd.read_csv(p, sep="\t", nrows=0).columns.tolist()
    if len(hdr) != LINKSTATS_EXPECTED_COLS:
        errs.append(f"linkstats_cols={len(hdr)}!={LINKSTATS_EXPECTED_COLS}")
    missing = [c for c in REQUIRED_LINKSTATS_FIELDS if c not in hdr]
    if missing:
        errs.append(f"linkstats_missing:{missing}")
    return hdr, errs


# ---------------------------------------------------------------------------
def load_links() -> pd.DataFrame:
    rt = pd.read_csv(ROOT / INPUTS["net_links_runtime"][0], sep=";",
                     usecols=["link", "length", "freespeed", "capacity", "lanes"])
    src = pd.read_csv(ROOT / INPUTS["src_copy"][0], usecols=["from_node", "to_node", "highway"])
    src["link"] = "e" + src["from_node"].astype(str) + "_" + src["to_node"].astype(str)
    src = src.rename(columns={"highway": "road_type"})
    ls = pd.read_csv(ROOT / INPUTS["ls_final"][0], sep="\t",
                     usecols=["LINK", "LENGTH", "FREESPEED", "CAPACITY", VOL_COL, TT_COL],
                     low_memory=False)
    ls = ls.rename(columns={"LINK": "link"})
    m = rt.merge(src[["link", "road_type"]], on="link", how="left")
    m = m.merge(ls, on="link", how="left")
    m["ff_s"] = m["length"] / m["freespeed"]
    m["ff_ceil_s"] = np.ceil(m["ff_s"] - 1e-9)
    v = m[VOL_COL].fillna(0.0).to_numpy(float)
    tt = m[TT_COL].fillna(0.0).to_numpy(float)
    ffc = m["ff_ceil_s"].to_numpy(float)
    m["vol"] = v
    m["tt_s"] = tt
    m["delay_corr_h"] = np.where(v > 0, v * np.maximum(0.0, tt - ffc) / 3600.0, 0.0)
    m["road_type"] = m["road_type"].fillna("").astype(str).str.strip().str.lower()
    m["is_service"] = m["road_type"].eq(SERVICE)
    m["loaded"] = v > 0
    return m


def load_endpoint_links() -> dict:
    act = re.compile(r'<activity type="(\w+)" link="([^"]+)"')
    home: set = set()
    work: set = set()
    n = 0
    bad = 0
    cur: dict = {}
    with gzip.open(ROOT / INPUTS["pop"][0], "rt", encoding="utf-8") as fh:
        for line in fh:
            if "<person " in line:
                cur = {}
                n += 1
            elif "<activity " in line:
                mm = act.search(line)
                if mm:
                    cur[mm.group(1)] = mm.group(2)
            elif "</person>" in line:
                if not cur.get("home") or not cur.get("work"):
                    bad += 1
                if cur.get("home"):
                    home.add(cur["home"])
                if cur.get("work"):
                    work.add(cur["work"])
    return {"n_persons": n, "bad": bad, "home": home, "work": work, "union": home | work}


# ---------------------------------------------------------------------------
def face_value(g: pd.DataFrame, face: str) -> float:
    if face == "time":
        return fsum_h(g["delay_corr_h"])
    if face == "count":
        return float(len(g))
    if face == "distance":
        return float(g["length"].sum() / 1000.0)
    if face == "volume":
        return float(g["vol"].sum())
    raise KeyError(face)


def intensity(g: pd.DataFrame) -> dict:
    d = fsum_h(g["delay_corr_h"]) * 3600.0
    km = float(g["length"].sum() / 1000.0)
    vol = float(g["vol"].sum())
    return {"s_per_link": (d / len(g)) if len(g) else float("nan"),
            "s_per_km": (d / km) if km else float("nan"),
            "s_per_veh": (d / vol) if vol else float("nan")}


def coverage_fraction(g: pd.DataFrame, target_pct: float):
    d = pd.to_numeric(g["delay_corr_h"], errors="coerce").fillna(0.0).clip(lower=0)
    tot = float(d.sum())
    n_scope = int(len(g))
    if tot <= 0 or n_scope <= 0:
        return float("nan"), 0, tot, n_scope
    s = np.sort(d.to_numpy(float))[::-1]
    k = int(np.searchsorted(np.cumsum(s), tot * (target_pct / 100.0), side="left") + 1)
    return float(k) / float(n_scope), k, tot, n_scope


def gini_desc(values: pd.Series) -> float:
    x = pd.to_numeric(values, errors="coerce").fillna(0.0).clip(lower=0).to_numpy(float)
    if x.size == 0 or float(x.sum()) <= 0:
        return float("nan")
    x = np.sort(x)
    n = len(x)
    idx = np.arange(1, n + 1, dtype=float)
    return float((2.0 * np.sum(idx * x) / (n * np.sum(x))) - (n + 1.0) / n)


# ---------------------------------------------------------------------------
def build_analysis(m: pd.DataFrame, ep: dict):
    m["is_endpoint"] = m["link"].isin(ep["union"])
    S = {
        "ALL_LOADED": m[m["loaded"]],
        "SERVICE_LOADED": m[m["loaded"] & m["is_service"]],
        "ENDPOINT_SERVICE_LOADED": m[m["loaded"] & m["is_service"] & m["is_endpoint"]],
    }
    A = {
        "SERVICE_ANY": m[m["is_service"]],
        "ENDPOINT_SERVICE_ANY": m[m["is_service"] & m["is_endpoint"]],
    }
    all_any = m
    d0 = S["ALL_LOADED"]

    # 1) 值矩阵（U_loaded，12 行，无 NaN）
    fm = pd.DataFrame([{
        "face": f, "face_role": ("IMPACT" if f in IMPACT_FACES else "EXPOSURE"),
        "scope": s, "universe": UD, "value": face_value(S[s], f), "units": FACE_UNITS[f],
    } for s in SCOPE_L for f in FACE_ORDER])

    D0V = {f: face_value(d0, f) for f in FACES}

    # 2) 份额矩阵（12 loaded + 12 any）
    rows = []
    for s in SCOPE_L:
        for f in FACE_ORDER:
            nv = face_value(S[s], f)
            rows.append({"face": f, "scope": s, "universe": UD, "denom_scope": "D0",
                         "numerator_scope": s, "numerator_value_loaded": nv,
                         "denominator_value_loaded": D0V[f],
                         "share_loaded": (nv / D0V[f]) if D0V[f] else float("nan")})
    for s in SCOPE_A:
        for f in FACE_ORDER:
            nv = face_value(A[s], f)
            dv = face_value(all_any, f)
            rows.append({"face": f, "scope": s, "universe": UA, "denom_scope": "D0",
                         "numerator_scope": s, "numerator_value_any": nv,
                         "denominator_value_any": dv,
                         "share_any": (nv / dv) if dv else float("nan")})
    sm = pd.DataFrame(rows)

    # 3) 强度矩阵
    im = pd.DataFrame([{"scope": s, "universe": UD, "metric": mt, "value": intensity(S[s])[mt],
                        "units": mt.replace("s_per_", "s/"), "base_face": "time"}
                       for s in SCOPE_L for mt in ("s_per_link", "s_per_km", "s_per_veh")])

    # 4) 宇宙撕裂
    ep_l, ep_a = S["ENDPOINT_SERVICE_LOADED"], A["ENDPOINT_SERVICE_ANY"]
    uc = []
    for f in FACE_ORDER:
        sl = (face_value(ep_l, f) / D0V[f] * 100.0) if D0V[f] else float("nan")
        uc.append({"kind": "face_share", "face": f, "scope": "ENDPOINT_SERVICE_LOADED",
                   "universe": UD, "denom_scope": "D0", "share_pct_loaded": sl,
                   "impossible_loaded": bool(sl > 100.0 + IMPOSSIBLE_SHARE_TOL)})
    svc_any_km = float(A["SERVICE_ANY"]["length"].sum() / 1000.0)
    all_loaded_km = float(d0["length"].sum() / 1000.0)
    mixed_ratio = (svc_any_km / all_loaded_km) if all_loaded_km else float("nan")
    for f in FACE_ORDER:
        dv = face_value(all_any, f)
        sa = (face_value(ep_a, f) / dv * 100.0) if dv else float("nan")
        uc.append({"kind": "face_share", "face": f, "scope": "ENDPOINT_SERVICE_ANY",
                   "universe": UA, "denom_scope": "D0", "share_pct_any": sa,
                   "impossible_any": bool(sa > 100.0 + IMPOSSIBLE_SHARE_TOL)})
    uc.append({"kind": "illegal_mixed_universe", "face": "distance", "scope": "SERVICE_ANY",
               "universe": UA, "denom_scope": "", "ratio_any": mixed_ratio,
               "impossible_any": bool(mixed_ratio > 1.0 + IMPOSSIBLE_SHARE_TOL)})
    ucx = pd.DataFrame(uc)

    # 5) 集中度曲线
    cc = []
    base_a = all_any
    for t in T_LEVELS:
        f0l = coverage_fraction(d0, t)[0]
        f0a = coverage_fraction(base_a, t)[0]
        for s in SCOPE_L:
            f, k, tot, ns = coverage_fraction(S[s], t)
            cc.append({"scope": s, "universe": UD, "target_pct": t,
                       "n_scope_loaded": ns, "k_min_loaded": k, "f_t_loaded": f,
                       "f_t_D0_loaded": f0l,
                       "relative_coverage_ratio_loaded": (f / f0l) if (f0l and np.isfinite(f) and np.isfinite(f0l)) else float("nan"),
                       "scope_total_delay_h_loaded": tot, "instrument": "coverage_fraction", "k_rule": K_RULE})
        for s in SCOPE_A:
            f, k, tot, ns = coverage_fraction(A[s], t)
            cc.append({"scope": s, "universe": UA, "target_pct": t,
                       "n_scope_any": ns, "k_min_any": k, "f_t_any": f,
                       "f_t_D0_any": f0a,
                       "relative_coverage_ratio_any": (f / f0a) if (f0a and np.isfinite(f) and np.isfinite(f0a)) else float("nan"),
                       "scope_total_delay_h_any": tot, "instrument": "coverage_fraction", "k_rule": K_RULE})
    ccx = pd.DataFrame(cc)

    def q3_for(scope: str) -> str:
        col = "relative_coverage_ratio_loaded" if scope in SCOPE_L else "relative_coverage_ratio_any"
        rels = [float(x) for x in ccx[ccx["scope"] == scope][col].dropna() if np.isfinite(float(x))]
        if not rels:
            return ""
        if any(x >= RATIO_CONC_MIN for x in rels):
            return "CONCENTRATION_ATTENUATED"
        if any(x <= 1.0 / RATIO_CONC_MIN for x in rels):
            return "CONCENTRATION_AMPLIFIED"
        return "CONCENTRATION_COMPARABLE"

    q3_svc, q3_ep = q3_for("SERVICE_LOADED"), q3_for("ENDPOINT_SERVICE_LOADED")
    cv = []
    for s in ("SERVICE_LOADED", "ENDPOINT_SERVICE_LOADED"):
        rels = [float(x) for x in ccx[ccx["scope"] == s]["relative_coverage_ratio_loaded"].dropna()]
        cv.append({"scope": s, "universe": UD, "instrument": "coverage_fraction",
                   "targets_pct": "|".join(str(t) for t in T_LEVELS), "k_rule": K_RULE,
                   "relative_coverage_ratio_max": float(np.nanmax(rels)),
                   "relative_coverage_ratio_min": float(np.nanmin(rels)),
                   "verdict": q3_svc if s == "SERVICE_LOADED" else q3_ep,
                   "primary_scope": s == "ENDPOINT_SERVICE_LOADED"})
    cvx = pd.DataFrame(cv)

    # 6) 暴露 / 影响缺口
    sh_ep_l = {f: (face_value(ep_l, f) / D0V[f] * 100.0) if D0V[f] else float("nan") for f in FACES}
    sh_ep_a = {f: (face_value(ep_a, f) / face_value(all_any, f) * 100.0)
               if face_value(all_any, f) else float("nan") for f in FACES}
    range_ep = float(max(sh_ep_l.values()) - min(sh_ep_l.values()))
    i_l, i_e = intensity(d0), intensity(ep_l)
    g_rows = [{"kind": "share_ep_svc_over_d0", "key": f, "face": f, "scope": "ENDPOINT_SERVICE_LOADED",
               "universe": UD, "denom_scope": "D0", "value": sh_ep_l[f], "unit": "%",
               "ratio_vs_D0": float("nan"), "band": ""} for f in FACE_ORDER]
    g_rows.append({"kind": "share_range", "key": "RANGE_ep", "face": "|".join(FACE_ORDER),
                   "scope": "ENDPOINT_SERVICE_LOADED", "universe": UD, "denom_scope": "D0",
                   "value": range_ep, "unit": "pp", "ratio_vs_D0": float("nan"),
                   "band": "ABOVE_BAND" if range_ep > AGREEMENT_BAND_PP else "WITHIN_BAND"})
    for mt in ("s_per_link", "s_per_km", "s_per_veh"):
        g_rows.append({"kind": "intensity_ratio", "key": mt, "face": "time",
                       "scope": "ENDPOINT_SERVICE_LOADED", "universe": UD, "denom_scope": "D0",
                       "value": i_e[mt], "unit": mt.replace("s_per_", "s/"),
                       "ratio_vs_D0": (i_e[mt] / i_l[mt]) if i_l[mt] else float("nan"), "band": ""})
    gx = pd.DataFrame(g_rows)

    # 7) 口径交叉表
    xw = pd.DataFrame([
        {"field": "delay_corr_h", "face": "time", "universe": UD, "denom_scope": "D0",
         "inherited_from": "G-0/G-1 canonical",
         "canonical_expression": "sum over vol>0 of vol*max(0,TT8-9avg-ceil(length/freespeed-1e-9))/3600"},
        {"field": "link_count", "face": "count", "universe": UD, "denom_scope": "D0",
         "inherited_from": "G-0/G-1 canonical", "canonical_expression": "len(scope); U_loaded := vol>0"},
        {"field": "length", "face": "distance", "universe": UD, "denom_scope": "D0",
         "inherited_from": "runtime links 'length' (== linkstats LENGTH, 3dp)",
         "canonical_expression": "sum(runtime.length)/1000; NOT src_copy.length_m"},
        {"field": "HRS8-9avg", "face": "volume", "universe": UD, "denom_scope": "D0",
         "inherited_from": "linkstats 8-9 window", "canonical_expression": "sum(HRS8-9avg)"},
        {"field": "freespeed", "face": "time", "universe": UD, "denom_scope": "D0",
         "inherited_from": "runtime links 'freespeed'",
         "canonical_expression": "ff_s = runtime.length/runtime.freespeed"},
        {"field": "road_type", "face": "(scope selector)", "universe": UD, "denom_scope": "D1",
         "inherited_from": "src_copy.highway", "canonical_expression": "D1 := road_type == 'service'"},
        {"field": "endpoint_membership", "face": "(scope selector)", "universe": UD, "denom_scope": "D2",
         "inherited_from": "G-1 O10 (pop activity link)",
         "canonical_expression": "link in (home_links union work_links) of population_lambda_0p075"},
    ])

    # 8) 分母审计（含 Gini 描述性字段）★读对照物必须 round_trip
    g0f = read_ref("g0_faces")
    g1s = read_ref("g1_endpoint_service_split")
    g1e = g1s[g1s["group"].astype(str).str.strip().eq("endpoint_service")].iloc[0]
    au = []
    for _, r in g0f.iterrows():
        f = FACE_G0_KEY.get(str(r["face"]), "")
        au.append({"source": "g0_exposure_faces.csv", "field": str(r["face"]), "face": f,
                   "universe": UD, "denom_scope": "D0",
                   "value_pct_loaded": float(r["share_pct"]),
                   "recomputed_pct_loaded": float(sh_ep_l.get(f, float("nan"))),
                   "value_pct_any": float("nan"), "recomputed_pct_any": float("nan"),
                   "gini": float("nan"),
                   "decision_use": True, "note": "legacy G-0 service share, D0 denominator"})
    au.append({"source": "g1_endpoint_service_split.csv", "field": "vol_share_service_pct",
               "face": "volume", "universe": UA, "denom_scope": "D1",
               "value_pct_loaded": float("nan"),
               "recomputed_pct_loaded": float("nan"),
               "value_pct_any": float(g1_ep_row(g1e, "vol_share_service_pct")),
               "recomputed_pct_any": face_value(ep_a, "volume") / float(fsum_h(A["SERVICE_ANY"]["vol"])) * 100.0,
               "gini": float("nan"), "decision_use": True,
               "note": "G-1 stored against SERVICE denominator (D1), NOT D0 -> mixing risk"})
    au.append({"source": "g1_endpoint_service_split.csv", "field": "delay_share_service_pct",
               "face": "time", "universe": UA, "denom_scope": "D1",
               "value_pct_loaded": float("nan"),
               "recomputed_pct_loaded": float("nan"),
               "value_pct_any": float(g1_ep_row(g1e, "delay_share_service_pct")),
               "recomputed_pct_any": face_value(ep_a, "time") / fsum_h(A["SERVICE_ANY"]["delay_corr_h"]) * 100.0,
               "gini": float("nan"), "decision_use": True,
               "note": "G-1 stored against SERVICE denominator (D1), NOT D0 -> mixing risk"})
    gini_map = {}
    for s in SCOPE_L + SCOPE_A:
        fr_ = S[s] if s in S else A[s]
        gv = gini_desc(fr_["delay_corr_h"])
        gini_map[s] = gv
        au.append({"source": "derived", "field": "gini_over_delay_h[%s]" % s, "face": "(descriptive)",
                   "universe": UD if s in S else UA, "denom_scope": "",
                   "value_pct_loaded": float("nan"), "recomputed_pct_loaded": float("nan"),
                   "value_pct_any": float("nan"), "recomputed_pct_any": float("nan"),
                   "gini": gv, "decision_use": False,
                   "note": "Gini descriptive only; forbidden as concentration criterion (O5)"})
    aux = pd.DataFrame(au)

    # 9) 判决
    SPL_U = float(max(abs(sh_ep_a[f] - sh_ep_l[f]) for f in FACES))
    legal = ([sh_ep_l[f] for f in FACES] + [sh_ep_a[f] for f in FACES]
             + [float(x) for x in sm["share_loaded"].dropna()] + [float(x) for x in sm["share_any"].dropna()])
    legal = [x for x in legal if np.isfinite(x)]
    worst = max(legal) if legal else float("nan")
    no_impossible = bool(worst <= 100.0 + IMPOSSIBLE_SHARE_TOL)

    v_q1 = "DENOMINATOR_UNIFIED" if (no_impossible and SPL_U <= UNIVERSE_SPREAD_TOL_PP) else "DENOMINATOR_SPLIT"
    v_q2 = "EXPOSURE_IMPACT_DECOUPLED" if range_ep > AGREEMENT_BAND_PP else "EXPOSURE_IMPACT_COUPLED"
    v_q4 = "FOUR_FACE_PARALLEL_REPORTING" if range_ep > AGREEMENT_BAND_PP else "SINGLE_HEADLINE_ADMISSIBLE"
    for v, pool in ((v_q1, V_Q1), (v_q2, V_Q2), (q3_ep, V_Q3), (v_q4, V_Q4)):
        if v not in pool:
            raise AssertionError("verdict outside closed set: %r" % v)

    vd = pd.DataFrame([
        {"question": "Q1", "name": "DENOMINATOR_UNIFORMITY", "verdict": v_q1, "universe": UD,
         "rule": "no legal share > 100%+1e-9 AND max_face |share_any - share_loaded| (EP_SVC|D0) <= 0.5 pp",
         "evidence": "max_legal_share_pct=%.9f; universe_spread_pp=%.9f; tol_pp=%.2f; Q1 compares U_loaded vs U_any (see g2_universe_contrast.csv)"
                     % (worst, SPL_U, UNIVERSE_SPREAD_TOL_PP)},
        {"question": "Q2", "name": "EXPOSURE_IMPACT_SEPARATION", "verdict": v_q2, "universe": UD,
         "rule": "RANGE_ep > 5.0 pp => EXPOSURE_IMPACT_DECOUPLED else EXPOSURE_IMPACT_COUPLED",
         "evidence": "RANGE_ep=%.9f pp; band_pp=%.2f" % (range_ep, AGREEMENT_BAND_PP)},
        {"question": "Q3", "name": "CONCENTRATION_VERDICT", "verdict": q3_ep, "universe": UD,
         "rule": "exists t R_t>=3 => ATTENUATED; exists t R_t<=1/3 => AMPLIFIED; else COMPARABLE (primary scope EP_SVC)",
         "evidence": "EP_SVC=%s; SVC=%s; instrument=coverage_fraction; targets=%s"
                     % (q3_ep, q3_svc, "|".join(str(t) for t in T_LEVELS))},
        {"question": "Q4", "name": "HEADLINE_POLICY", "verdict": v_q4, "universe": UD,
         "rule": "RANGE_ep <= 5.0 pp => SINGLE_HEADLINE_ADMISSIBLE else FOUR_FACE_PARALLEL_REPORTING",
         "evidence": "RANGE_ep=%.9f pp" % range_ep},
    ])

    fr = {
        "shares_ep_loaded_pct": {k: float(v) for k, v in sh_ep_l.items()},
        "shares_ep_any_pct": {k: float(v) for k, v in sh_ep_a.items()},
        "range_ep_pp": range_ep, "spread_u_pp": SPL_U, "legal_max_share_pct": float(worst),
        "mixed_universe_ratio": float(mixed_ratio),
        "q1": v_q1, "q2": v_q2, "q3": q3_ep, "q3_svc": q3_svc, "q4": v_q4,
        "endpoint_ids": len(ep["union"]), "pop_persons": int(ep["n_persons"]),
        "d0": {"n": int(len(d0)), "km": all_loaded_km, "vol": float(d0["vol"].sum()),
               "delay_h": fsum_h(d0["delay_corr_h"])},
        "d1": {"n": int(len(S["SERVICE_LOADED"])), "km": float(S["SERVICE_LOADED"]["length"].sum() / 1000.0),
               "vol": float(S["SERVICE_LOADED"]["vol"].sum()),
               "delay_h": fsum_h(S["SERVICE_LOADED"]["delay_corr_h"])},
        "ep_loaded": {"n": int(len(ep_l)), "km": float(ep_l["length"].sum() / 1000.0),
                      "vol": float(ep_l["vol"].sum()), "delay_h": fsum_h(ep_l["delay_corr_h"])},
        "ep_any": {"n": int(len(ep_a)), "km": float(ep_a["length"].sum() / 1000.0),
                   "vol": float(ep_a["vol"].sum()), "delay_h": fsum_h(ep_a["delay_corr_h"])},
        "svc_any": {"n": int(len(A["SERVICE_ANY"])), "km": svc_any_km,
                    "delay_h": fsum_h(A["SERVICE_ANY"]["delay_corr_h"])},
        "gini": {k: float(v) for k, v in gini_map.items()},
        "intensity_d0": {k: float(v) for k, v in i_l.items()},
        "intensity_ep": {k: float(v) for k, v in i_e.items()},
    }
    dfs = {"face_matrix": fm, "share_matrix": sm, "intensity_matrix": im, "universe_contrast": ucx,
           "denominator_audit": aux, "concentration": ccx, "concentration_verdict": cvx,
           "gap": gx, "crosswalk": xw, "verdicts": vd}
    return fr, dfs


def g1_ep_row(row, col):
    return row[col]


def noop_selfcheck(fr: dict) -> tuple[bool, str]:
    """纪律⑧：no-op（写死为真值）不得触发；相矛盾改动必须触发（门 15 判据双盲）。"""
    # G-0 该文件用裸名 "time"；"time_delay_corr_h" 是 G-1 的命名，此处不得混用
    g0 = read_ref("g0_faces")
    row = g0[g0["face"].astype(str).str.strip().map(lambda v: FACE_G0_KEY.get(v) == "time")]
    exp_time = float(row.iloc[0]["service_value"])
    arm_a = bool(abs(fr["d1"]["delay_h"] - exp_time) == 0.0)
    arm_b = bool(not (abs(fr["d0"]["delay_h"] - exp_time) == 0.0))
    return (arm_a and arm_b), "noop_identity_holds=%s; contradictory_mutation_fires=%s" % (arm_a, arm_b)


# ---------------------------------------------------------------------------
def ast_compile_ok(p: Path) -> tuple[bool, str]:
    src = p.read_text(encoding="utf-8")
    try:
        ast.parse(src)
        compile(src, str(p), "exec")
        return True, "ast_parse=OK compile=OK n_lines=%d" % (src.count("\n") + 1)
    except Exception as e:  # pragma: no cover
        return False, "%s: %s" % (type(e).__name__, e)


def flow_blind_ast(p: Path) -> tuple[bool, str]:
    src = p.read_text(encoding="utf-8")
    tree = ast.parse(src)
    hits = []
    for n in ast.walk(tree):
        if isinstance(n, ast.Import):
            for a in n.names:
                root = a.name.split(".")[0]
                if root in BANNED_IMPORTS or root not in ALLOWED_IMPORTS:
                    hits.append("import:" + a.name)
        elif isinstance(n, ast.ImportFrom):
            root = (n.module or "").split(".")[0]
            if root in BANNED_IMPORTS or root not in ALLOWED_IMPORTS:
                hits.append("from:" + str(n.module))
        elif isinstance(n, ast.Call):
            if isinstance(n.func, ast.Attribute) and n.func.attr in BANNED_CALL_ATTRS:
                hits.append("call:." + n.func.attr)
            if isinstance(n.func, ast.Name) and n.func.id in BANNED_CALL_NAMES:
                hits.append("call:" + n.func.id)
    if ("." + "ja" + "r") in src:
        hits.append("token:." + "ja" + "r")
    return (not hits), "banned_hits=%s" % sorted(set(hits))


def ast_banned_identifiers(p: Path) -> tuple[bool, str]:
    """只扫标识符/属性/关键字名（不含字符串字面量），避免门 ID 里的 COMPOSITE 自命中。"""
    tree = ast.parse(p.read_text(encoding="utf-8"))
    names = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.Name):
            names.add(n.id)
        elif isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add(n.name)
        elif isinstance(n, ast.Attribute):
            names.add(n.attr)
        elif isinstance(n, ast.arg):
            names.add(n.arg)
        elif isinstance(n, ast.keyword) and n.arg:
            names.add(n.arg)
        elif isinstance(n, ast.arg):
            names.add(n.arg)
    hits = sorted(t for t in BANNED_ID_TOKEN if t in {x.lower() for x in names})
    return (not hits), "banned_identifiers=%s" % hits


def ast_gini_not_in_decision(p: Path) -> tuple[bool, str]:
    """gini 不得进入任何比较表达式（判据）。"""
    tree = ast.parse(p.read_text(encoding="utf-8"))
    hits = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Compare):
            for sub in ast.walk(node):
                if isinstance(sub, ast.Name) and "gini" in sub.id.lower():
                    hits.append("cmp:" + sub.id)
                if isinstance(sub, ast.Attribute) and "gini" in sub.attr.lower():
                    hits.append("cmp:." + sub.attr)
    return (not hits), "gini_in_comparisons=%s" % sorted(set(hits))


# ---------------------------------------------------------------------------
def read_artifacts(out: Path) -> dict:
    names = {"face_matrix": "g2_face_matrix.csv", "share_matrix": "g2_share_matrix.csv",
             "intensity_matrix": "g2_intensity_matrix.csv", "universe_contrast": "g2_universe_contrast.csv",
             "denominator_audit": "g2_denominator_audit.csv", "concentration": "g2_concentration_curve.csv",
             "conc_verdict": "g2_concentration_verdict.csv", "gap": "g2_exposure_impact_gap.csv",
             "crosswalk": "g2_caliber_crosswalk.csv", "verdicts": "g2_verdicts.csv"}
    out_d = {}
    for k, fn in names.items():
        p = out / fn
        # ★必须 round_trip：默认快速解析回读产物会丢 1 ulp（962.7150059999999 -> 962.715006）
        out_d[k] = pd.read_csv(p, encoding="utf-8-sig", float_precision="round_trip") if p.exists() else pd.DataFrame()
    return out_d


def build_checks(payload: dict, ctx: dict) -> list:
    rows: list = []

    def G(gid: str, ok: bool, detail: str) -> None:
        rows.append({"gate_id": gid, "pass_": bool(ok), "detail": str(detail)[:400]})

    def safe(gid: str, fn) -> None:
        try:
            ok, det = fn()
        except Exception as e:
            ok, det = False, "EXCEPTION %s: %s" % (type(e).__name__, e)
        G(gid, ok, det)

    out: Path = ctx["out"]
    script = Path(__file__).resolve()
    prereg = ROOT / PREREG_REL
    a = read_artifacts(out) if not ctx["blocked"] else {}
    fr = ctx.get("fr", {})

    def g01():
        b = prereg.stat().st_size if prereg.exists() else -1
        s = sha256_file(prereg) if prereg.exists() else ""
        return (b == PREREG_BYTES and s == PREREG_SHA), \
            "bytes=%d (declared %d); sha=%s match=%s" % (b, PREREG_BYTES, s[:16] + "…", s == PREREG_SHA)
    safe("7.9G2.01_PREREG_FROZEN_AND_EMBEDDED", g01)
    safe("7.9G2.02_SCRIPT_AST_COMPILE", lambda: ast_compile_ok(script))
    safe("7.9G2.03_ZERO_SIMULATION", lambda: flow_blind_ast(script))

    def g04():
        fi = ctx["inp"]["frozen_inputs"]
        bad = [k for k, r in fi.items() if not (r.get("exists") and r.get("size_ok") and r.get("sha_ok"))]
        return (len(fi) == 5 and not bad), "manifest_items=%d mismatched=%s" % (len(fi), bad)
    safe("7.9G2.04_INPUT_MANIFEST_COMPLETE", g04)

    def g05():
        hdr = ctx["hdr"]
        miss = [c for c in REQUIRED_LINKSTATS_FIELDS if c not in hdr]
        return (len(hdr) == LINKSTATS_EXPECTED_COLS and not miss), \
            "n_cols=%d (expected %d); required_missing=%s" % (len(hdr), LINKSTATS_EXPECTED_COLS, miss)
    safe("7.9G2.05_LINKSTATS_154_COLUMNS", g05)

    def g06():
        return (ctx["n_net_ls"] == ctx["n_net_links"] and ctx["n_ls_only"] == 0), \
            ("net_links=%d; ls_links=%d; net∩ls=%d; len(U_any)=src_copy∩runtime=%d; ls_not_in_net=%d; unmatched=0"
             % (ctx["n_net_links"], ctx["n_ls_rows"], ctx["n_net_ls"], ctx["n_net_links"], ctx["n_ls_only"]))
    safe("7.9G2.06_NETWORK_JOIN_COMPLETE", g06)

    def g07():
        s2 = ctx["inp"]["frozen_inputs"]["ls_final"].get("sha256", "")
        s3 = ctx["inp"]["frozen_inputs"]["ls_viz_ref"].get("sha256", "")
        return (s2 == s3 and ctx["n_ls_rows"] == ctx["n_net_ls"]), \
            "sha(I2)==sha(I3):%s; ls_rows=%d covered=%d" % (s2 == s3, ctx["n_ls_rows"], ctx["n_net_ls"])
    safe("7.9G2.07_LINKSTATS_JOIN_COMPLETE", g07)

    def g08():
        problems = []
        for k in UNIVERSE_TAGGED:
            df = a.get(k, pd.DataFrame())
            if df.empty:
                problems.append("%s:empty" % k)
                continue
            if "universe" not in df.columns:
                problems.append("%s:no_universe_column" % k)
                continue
            bad = set(df["universe"].dropna().astype(str).unique()) - {UD, UA}
            if bad:
                problems.append("%s:universe=%s" % (k, sorted(bad)))
            ar = df[df["universe"].astype(str).eq(UA)]
            if len(ar) and not [c for c in df.columns if c.endswith("_any")]:
                problems.append("%s:U_any_rows_without_any_suffix" % k)
        return (not problems), "tagged_checked=%d exempt=%s problems=%s" % (len(UNIVERSE_TAGGED), list(NON_MEASUREMENT), problems)
    safe("7.9G2.08_UNIVERSE_DECLARED_PER_ROW", g08)

    def g09():
        bad = []
        # ★「同一 (face, scope, Dk) 组合下 universe 唯一」需覆盖全部 share 行载体
        for k in ("face_matrix", "share_matrix", "universe_contrast", "concentration", "gap",
                  "denominator_audit", "crosswalk"):
            df = a.get(k, pd.DataFrame())
            if df.empty or "universe" not in df.columns:
                continue
            meas = [c for c in df.columns if re.match(r"^(share|numerator_value|value)", str(c))]
            if meas:
                df = df[df[meas].apply(lambda r: any(np.isfinite(float(x)) for x in r), axis=1)]
                if df.empty:
                    continue
            keys = [c for c in ("face", "scope", "denom_scope") if c in df.columns]
            if not keys:
                continue
            cnt = df.groupby(keys)["universe"].nunique()
            off = cnt[cnt > 1]
            if len(off):
                bad.append("%s:%d" % (k, len(off)))
                continue
            # 另断言：同一 (scope) 不得跨宇宙混用 Dk 语义
            if "scope" in keys:
                cross = df.groupby(["scope"])["universe"].nunique()
                over = cross[cross > 1]
                if len(over) and k != "denominator_audit":
                    bad.append("%s:scope_crosses_universe=%s" % (k, sorted(over.index)))
        return (not bad), "combos_with_multiple_universes=%s (scope names are universe-specific)" % bad
    safe("7.9G2.09_UNIVERSE_SINGLE_PER_COMPARISON", g09)

    def g10():
        vals = []
        sm = a.get("share_matrix", pd.DataFrame())
        for c in ("share_loaded", "share_any"):
            if c in sm.columns:
                vals += [float(x) for x in sm[c].dropna()]
        uc = a.get("universe_contrast", pd.DataFrame())
        for c in ("share_pct_loaded", "share_pct_any"):
            if c in uc.columns:
                vals += [float(x) / 100.0 for x in uc[c].dropna()]
        gx = a.get("gap", pd.DataFrame())
        if "value" in gx.columns and "denom_scope" in gx.columns:
            vals += [float(x) / 100.0 for x in gx[gx["kind"].eq("share_ep_svc_over_d0")]["value"].dropna()]
        worst = max(vals) if vals else float("nan")
        mixed = float(fr.get("mixed_universe_ratio", float("nan")))
        ok = bool(np.isfinite(worst) and worst <= 1.0 + IMPOSSIBLE_SHARE_TOL and mixed > 1.0)
        return ok, ("max_legal_share=%.9f; impossible_rows=0; illegal_mixed_universe_ratio=%.9f (>1 => "
                    "captured & labelled ILLEGAL_MIXED_UNIVERSE, excluded); n_legal=%d" % (worst, mixed, len(vals)))
    safe("7.9G2.10_NO_IMPOSSIBLE_SHARE", g10)

    def g11():
        bad = []
        for f in FACES:
            v = {}
            for dk, s in (("D0", "ALL_LOADED"), ("D1", "SERVICE_LOADED"), ("D2", "ENDPOINT_SERVICE_LOADED")):
                r = a["face_matrix"][(a["face_matrix"]["face"] == f) & (a["face_matrix"]["scope"] == s)]
                v[dk] = float(r.iloc[0]["value"]) if len(r) else float("nan")
            if not (v["D2"] <= v["D1"] <= v["D0"]):
                bad.append("%s:D2=%.4f D1=%.4f D0=%.4f" % (f, v["D2"], v["D1"], v["D0"]))
        return (not bad), "monotonic_violations=%s" % bad
    safe("7.9G2.11_NESTED_DENOMINATOR_MONOTONIC", g11)

    def g12():
        bad = []
        # ★prereg §6.12：「每个 share 行带 denom_scope ∈ {D0,D1,D2}，**非空**」
        #   空串经 to_csv/read_csv 往返会变成 NaN ⇒ 必须显式判 isna，不能只靠 dropna 后的集合差。
        for k in ("share_matrix", "universe_contrast", "gap", "denominator_audit", "crosswalk"):
            df = a.get(k, pd.DataFrame())
            if df.empty or "denom_scope" not in df.columns:
                bad.append("%s:no_denom_scope" % k)
                continue
            meas = [c for c in df.columns if re.match(r"^(share|numerator_value|value)", str(c))]
            if not meas:
                continue
            isshare = df[meas].apply(lambda r: any(np.isfinite(float(x)) for x in r), axis=1)
            sub = df[isshare]
            n_empty = int(sub["denom_scope"].isna().sum())
            vals = set(sub["denom_scope"].dropna().astype(str).unique())
            off = vals - set(DENOM)
            if off:
                bad.append("%s:off=%s" % (k, sorted(off)))
            if n_empty:
                bad.append("%s:empty_denom_rows=%d" % (k, n_empty))
        return (not bad), "problems=%s allowed=%s" % (bad, list(DENOM))
    safe("7.9G2.12_DENOMINATOR_DECLARED_PER_ROW", g12)

    def g13():
        fm = a.get("face_matrix", pd.DataFrame())
        m = dict(zip(fm["face"], fm["face_role"])) if len(fm) else {}
        exp = {f: ("IMPACT" if f in IMPACT_FACES else "EXPOSURE") for f in FACES}
        return (len(fm) == 12 and m == exp and set(fm["face_role"]) <= {"IMPACT", "EXPOSURE"}), \
            "face_role_map=%s" % m
    safe("7.9G2.13_FACE_ROLE_DECLARED", g13)

    def g14():
        fm = a.get("face_matrix", pd.DataFrame())
        combos = set(zip(fm["scope"], fm["face"])) if len(fm) else set()
        want = {(s, f) for s in SCOPE_L for f in FACES}
        nans = int(fm[["value", "units"]].isna().sum().sum()) if len(fm) else -1
        return (len(fm) == 12 and combos == want and nans == 0), \
            "rows=%d combos=%d/%d nans=%d" % (len(fm), len(combos), len(want), nans)
    safe("7.9G2.14_FOUR_FACE_MATRIX_COMPLETE", g14)

    def g15():
        g0 = read_ref("g0_faces")
        fm = a["face_matrix"]
        bad = []
        for _, r in g0.iterrows():
            f = FACE_G0_KEY.get(str(r["face"]))
            svc = float(fm[(fm["face"] == f) & (fm["scope"] == "SERVICE_LOADED")].iloc[0]["value"])
            tot = float(fm[(fm["face"] == f) & (fm["scope"] == "ALL_LOADED")].iloc[0]["value"])
            if not (svc == float(r["service_value"]) and tot == float(r["total_value"])):
                bad.append("%s: svc %r vs %r ; tot %r vs %r"
                           % (f, svc, float(r["service_value"]), tot, float(r["total_value"])))
        return (not bad), "bit_exact(atol=0,rtol=0) failures=%s; compared_rows=%d" % (bad, len(g0))
    safe("7.9G2.15_FACE_RECOMPUTE_MATCHES_G0", g15)

    def g16():
        g1 = read_ref("g1_endpoint_service_split")
        r = g1[g1["group"].astype(str).str.strip().eq("endpoint_service")].iloc[0]
        fm = a["face_matrix"]
        vol = float(fm[(fm["face"] == "volume") & (fm["scope"] == "ENDPOINT_SERVICE_LOADED")].iloc[0]["value"])
        dly = float(fm[(fm["face"] == "time") & (fm["scope"] == "ENDPOINT_SERVICE_LOADED")].iloc[0]["value"])
        vol_ok, dly_ok = (vol == float(r["vol"])), (dly == float(r["delay_corr_h"]))
        km_any, km_loaded = float(fr["ep_any"]["km"]), float(fr["ep_loaded"]["km"])
        km_ok = (km_any == float(r["length_km"]))
        explicit = (km_any != km_loaded)
        return (vol_ok and dly_ok and km_ok and explicit), \
            ("vol=%r match=%s; delay_h match=%s; length_km U_any=%r==file(%r) %s; U_loaded=%r explicitly labelled"
             % (float(r["vol"]), vol_ok, dly_ok, km_any, float(r["length_km"]), km_ok, km_loaded))
    safe("7.9G2.16_EP_SVC_RECOMPUTE_MATCHES_G1", g16)

    def g17():
        bad = []
        for k, df in a.items():
            if df.empty:
                continue
            for c in df.columns:
                if FORBIDDEN_IMPACT_COL.search(str(c)):
                    bad.append("%s.%s" % (k, c))
            if "face_role" in df.columns and "face" in df.columns:
                off = df[df["face_role"].eq("IMPACT") & df["face"].ne("time")]
                if len(off):
                    bad.append("%s:IMPACT_on_non_time=%d" % (k, len(off)))
        return (not bad), "forbidden_impact_columns=%s" % bad
    safe("7.9G2.17_IMPACT_ONLY_FROM_TIME_FACE", g17)

    def g18():
        im = a.get("intensity_matrix", pd.DataFrame())
        combos = set(zip(im["scope"], im["metric"])) if len(im) else set()
        want = {(s, m) for s in SCOPE_L for m in ("s_per_link", "s_per_km", "s_per_veh")}
        nans = int(im["value"].isna().sum()) if len(im) else -1
        return (combos == want and nans == 0), "rows=%d combos=%d/%d nans=%d" % (len(im), len(combos), len(want), nans)
    safe("7.9G2.18_INTENSITY_REPORTED", g18)

    def g19():
        bad = ["%s.%s" % (k, c) for k, df in a.items() if not df.empty
               for c in df.columns if BANNED_COL_TOKEN.search(str(c))]
        ok, det = ast_banned_identifiers(script)
        return ((not bad) and ok), "bad_columns=%s; %s" % (bad, det)
    safe("7.9G2.19_NO_COMPOSITE_INDEX", g19)

    def g20():
        cc = a.get("concentration", pd.DataFrame())
        cv = a.get("conc_verdict", pd.DataFrame())
        inst = set(cc["instrument"].astype(str).unique()) | set(cv["instrument"].astype(str).unique())
        tg = set(int(x) for x in cc["target_pct"].unique())
        badk = [str(x) for x in list(cc["k_rule"].astype(str).unique()) + list(cv["k_rule"].astype(str).unique())
                if CONST_K_TOKEN.search(str(x))]
        return (inst == {"coverage_fraction"} and tg == set(T_LEVELS) and not badk), \
            "instrument=%s; targets=%s; constant_k_hits=%s; k_rule=%s" % (sorted(inst), sorted(tg), badk, K_RULE[:52] + "…")
    safe("7.9G2.20_CONCENTRATION_INSTRUMENT_DECLARED", g20)

    def g21():
        cc = a.get("concentration", pd.DataFrame())
        bad = []
        for _, r in cc.iterrows():
            su = "loaded" if str(r["universe"]) == UD else "any"
            for c in ("f_t_%s" % su, "f_t_D0_%s" % su, "relative_coverage_ratio_%s" % su):
                if c not in cc.columns or not np.isfinite(float(r[c])):
                    bad.append("%s@%s@t%d:%s" % (r["scope"], r["universe"], int(r["target_pct"]), c))
        return (not bad), "unpaired_cells=%s (n=%d); rows=%d" % (bad[:5], len(bad), len(cc))
    safe("7.9G2.21_CONCENTRATION_BASELINE_PAIRED", g21)

    def g22():
        cv = a.get("conc_verdict", pd.DataFrame())
        vd = a.get("verdicts", pd.DataFrame())
        if cv.empty or vd.empty:
            return False, "missing concentration verdict or Q3 verdict row"
        q3 = vd[vd["question"].eq("Q3")]
        uniq = set(cv["verdict"].astype(str).unique())
        prim = cv[cv["primary_scope"].astype(str).str.lower().isin(["true", "1"])]
        pv = str(prim.iloc[0]["verdict"]) if len(prim) else ""
        qv = str(q3.iloc[0]["verdict"]) if len(q3) else ""
        cc = a["concentration"]
        rels = [float(x) for x in cc[cc["universe"].eq(UD)]["relative_coverage_ratio_loaded"].dropna()]
        want = ("CONCENTRATION_ATTENUATED" if any(x >= RATIO_CONC_MIN for x in rels)
                else "CONCENTRATION_AMPLIFIED" if any(x <= 1.0 / RATIO_CONC_MIN for x in rels)
                else "CONCENTRATION_COMPARABLE")
        return (uniq <= V_Q3 and pv == qv == want), \
            "closed_set_values=%s primary=%s Q3=%s recomputed=%s R_t=%s" % (sorted(uniq), pv, qv, want, [round(x, 4) for x in rels])
    safe("7.9G2.22_CONCENTRATION_VERDICT_SINGLE", g22)

    def g23():
        gn = [k for k, df in a.items() if not df.empty and any(str(c).lower() == "gini" for c in df.columns)]
        in_decision = []
        for k, df in a.items():
            if df.empty:
                continue
            for c in df.columns:
                if c in ("verdict", "classification", "band") or BANNED_COL_TOKEN.search(str(c)):
                    if any("gini" in str(x).lower() for x in df[c].dropna().astype(str).unique()):
                        in_decision.append("%s.%s" % (k, c))
        ast_ok, ast_det = ast_gini_not_in_decision(script)
        audit = a.get("denominator_audit", pd.DataFrame())
        desc_ok = True
        if not audit.empty and "gini" in audit.columns:
            gr = audit[audit["gini"].notna()]
            if len(gr):
                desc_ok = bool(gr["decision_use"].astype(str).str.lower().isin(["false", "0"]).all())
        return (gn == ["denominator_audit"] and not in_decision and ast_ok and desc_ok), \
            "artifacts_with_gini_column=%s; gini_in_decision_columns=%s; %s; descriptive_only=%s" % (gn, in_decision, ast_det, desc_ok)
    safe("7.9G2.23_GINI_FORBIDDEN_AS_CRITERION", g23)

    writeback_and_tail(rows, payload, ctx)
    return rows


FINAL_ORDER = [
    "7.9G2.01_PREREG_FROZEN_AND_EMBEDDED", "7.9G2.02_SCRIPT_AST_COMPILE", "7.9G2.03_ZERO_SIMULATION",
    "7.9G2.04_INPUT_MANIFEST_COMPLETE", "7.9G2.05_LINKSTATS_154_COLUMNS", "7.9G2.06_NETWORK_JOIN_COMPLETE",
    "7.9G2.07_LINKSTATS_JOIN_COMPLETE", "7.9G2.08_UNIVERSE_DECLARED_PER_ROW",
    "7.9G2.09_UNIVERSE_SINGLE_PER_COMPARISON", "7.9G2.10_NO_IMPOSSIBLE_SHARE",
    "7.9G2.11_NESTED_DENOMINATOR_MONOTONIC", "7.9G2.12_DENOMINATOR_DECLARED_PER_ROW",
    "7.9G2.13_FACE_ROLE_DECLARED", "7.9G2.14_FOUR_FACE_MATRIX_COMPLETE",
    "7.9G2.15_FACE_RECOMPUTE_MATCHES_G0", "7.9G2.16_EP_SVC_RECOMPUTE_MATCHES_G1",
    "7.9G2.17_IMPACT_ONLY_FROM_TIME_FACE", "7.9G2.18_INTENSITY_REPORTED",
    "7.9G2.19_NO_COMPOSITE_INDEX", "7.9G2.20_CONCENTRATION_INSTRUMENT_DECLARED",
    "7.9G2.21_CONCENTRATION_BASELINE_PAIRED", "7.9G2.22_CONCENTRATION_VERDICT_SINGLE",
    "7.9G2.23_GINI_FORBIDDEN_AS_CRITERION", "7.9G2.24_TERMINAL_STATE_THREE_WAY",
    "7.9G2.25_NON_7_9G_ARTIFACTS_UNCHANGED",
]


def writeback_and_tail(rows: list, payload: dict, ctx: dict) -> None:
    def G(gid: str, ok: bool, detail: str) -> None:
        rows.append({"gate_id": gid, "pass_": bool(ok), "detail": str(detail)[:400]})

    out: Path = ctx["out"]
    disk = {f.name for f in out.iterdir() if f.is_file()} if out.exists() else set()
    declared = set(ARTIFACT_NAMES)
    man = ctx.get("manifest_records", {})
    clo = ctx.get("closure_records", {})
    byte_bad = []
    for name in sorted(declared - WRITEBACK_EXCLUDED):
        p = out / name
        if not p.exists():
            byte_bad.append(name + ":missing")
            continue
        if man.get(name) and man[name].get("sha256") != sha256_file(p):
            byte_bad.append(name + ":sha")
        elif man.get(name) and man[name].get("size") != p.stat().st_size:
            byte_bad.append(name + ":size")
    set_ok = (disk == declared) and (set(man.keys()) | {MANIFEST_NAME, CLOSURE_NAME} == declared) \
        and (set(clo.keys()) | {CLOSURE_NAME} == declared)
    stray = ctx.get("stray", [])

    drift = []
    n_guard = 0
    for rel in GUARD_DIRS:
        cur = walk_dir_shas(ROOT / rel)
        pre = ctx.get("guard_pre", {}).get(rel, {})
        n_guard += len(pre)
        if set(cur.keys()) != set(pre.keys()):
            drift.append("%s:fileset_changed(%d->%d)" % (rel, len(pre), len(cur)))
        for k, v in pre.items():
            if cur.get(k) != v:
                drift.append("%s/%s" % (rel, k))
    for name, (rel, size, sha) in REFS.items():
        p = ctx["ref_dir"] / rel
        if (not p.exists()) or sha256_file(p) != sha:
            drift.append("ref:" + name)
    out_inside = any(str(out.resolve()).lower().startswith(str((ROOT / g).resolve()).lower()) for g in GUARD_DIRS)
    g25_ok = (not drift) and (not out_inside)
    G("7.9G2.25_NON_7_9G_ARTIFACTS_UNCHANGED", g25_ok,
      "guard_dirs=%d guard_files=%d drift=%s out_inside_guard=%s" % (len(GUARD_DIRS), n_guard, drift, out_inside))

    core = [r for r in rows if not r["gate_id"].startswith("7.9G2.24_")]
    st_ck = STATUS_READY if (all(r["pass_"] for r in core) and not ctx.get("blocked")) else STATUS_BLOCKED
    sm_p, rp_p = out / SUMMARY_NAME, out / REPORT_NAME
    st_sm = st_rp = ""
    if sm_p.exists():
        try:
            st_sm = json.loads(sm_p.read_text(encoding="utf-8")).get("status", "")
        except Exception:
            st_sm = ""
    if rp_p.exists():
        for ln in rp_p.read_text(encoding="utf-8", errors="replace").splitlines():
            mm = re.search(r"\*\*STATUS:\s*([A-Z0-9_]+)\*\*", ln)
            if mm:
                st_rp = mm.group(1)
                break
    num_ok, num_det = True, ""
    if sm_p.exists():
        try:
            o = json.loads(sm_p.read_text(encoding="utf-8"))
            got = float(o.get("ep_svc_time_share_pct", -1.0))
            want = float(ctx.get("fr", {}).get("shares_ep_loaded_pct", {}).get("time", -99.0))
            num_ok = abs(got - want) < 1e-12
            num_det = " summary_time_share=%r expected=%r" % (got, want)
        except Exception as e:
            num_ok, num_det = False, " summary_parse_err=%s" % e
    G("7.9G2.24_TERMINAL_STATE_THREE_WAY",
      (set_ok and not byte_bad and not stray and st_ck == st_sm == st_rp
       and st_ck in (STATUS_READY, STATUS_BLOCKED) and num_ok),
      "writeback_set_ok=%s byte_bad=%s stray=%s checks=%s summary=%s report=%s%s"
      % (set_ok, byte_bad, stray, st_ck, st_sm, st_rp, num_det))


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
        "prereg": {"path": PREREG_REL, "bytes": PREREG_BYTES, "sha256": PREREG_SHA},
        "frozen_inputs": {k: {"path": v[0], "bytes": v[1], "sha256": v[2]} for k, v in INPUTS.items()},
        "frozen_input_count": len(INPUTS),
        "read_only_references": {k: {"path": v[0], "bytes": v[1], "sha256": v[2]} for k, v in REFS.items()},
        "read_only_reference_count": len(REFS),
        "generated_artifacts": recs,
        "excludes_self": True,
        "excludes_closure": True,
    }


def build_closure(out: Path, status: str, manifest: dict):
    rows = []
    for name in sorted(ARTIFACT_NAMES):
        if name == CLOSURE_NAME:
            continue
        p = out / name
        if not p.exists():
            rows.append({"kind": "artifact", "name": name, "exists": False, "size_bytes": 0, "sha256": ""})
            continue
        rows.append({"kind": "artifact", "name": name, "exists": True,
                     "size_bytes": p.stat().st_size, "sha256": sha256_file(p)})
    n_art = sum(1 for r in rows if r["kind"] == "artifact")
    rows.append({"kind": "self_exclusion", "name": CLOSURE_NAME, "exists": True,
                 "size_bytes": n_art, "sha256": ""})
    for k in ("status_checks", "status_summary", "status_report"):
        rows.append({"kind": k, "name": "", "exists": True, "size_bytes": 0, "sha256": status})
    df = pd.DataFrame(rows)
    ok = all(r["exists"] for _, r in df.iterrows())
    df = pd.concat([df, pd.DataFrame([{"kind": "closure_verdict", "name": "", "exists": ok,
                                       "size_bytes": int(n_art), "sha256": "OK" if ok else "FAIL"}])],
                   ignore_index=True)
    return df, ok


def write_template(out: Path, fr: dict, fm: pd.DataFrame, im: pd.DataFrame, dfs: dict) -> None:
    L = ["# 7.9G-2 统一报告模板（物化）", "",
         "## 一、规则句（O9，固定句式）", "",
         "> **`service` 端点链对仿真延误具有显著的时间暴露特征，但其影响并不与交通流量占比同步增长；",
         "> 因此应分别从时间、数量、距离和交通量四个维度表征，而不能以单一 `delay share`",
         "> 作为系统性拥堵归因依据。**", "",
         "## 二、四要素强制（O6 / 门 12）", "",
         "任何「某类占 X%」的断言必须写全四元组：`face` + `scope` + `Dk` + `universe`。", "",
         "## 三、四面数值表（scope × face，universe = U_loaded；12 值）", "",
         "| Scope | Face | Role | Value | Units | Denom | Share[D0] |", "|---|---|---|---:|---|---|---:|"]
    d0v = {}
    if len(fm):
        for f in FACE_ORDER:
            r = fm[(fm["scope"] == "ALL_LOADED") & (fm["face"] == f)]
            d0v[f] = float(r.iloc[0]["value"]) if len(r) else float("nan")
    for _, r in fm.iterrows():
        dv = d0v.get(r["face"], float("nan"))
        sh = (float(r["value"]) / dv * 100.0) if dv else float("nan")
        L.append("| %s | %s | %s | %.6f | %s | D0 | %.6f%% |"
                 % (r["scope"], r["face"], r["face_role"], float(r["value"]), r["units"], sh))
    L += ["", "## 四、强度表（time 面基准，3 档 × 3 scope = 9 值）", "",
          "| Scope | s/link | s/km | s/veh |", "|---|---:|---:|---:|"]
    for s in SCOPE_L:
        sub = im[im["scope"] == s] if len(im) else im
        vals = {r["metric"]: float(r["value"]) for _, r in sub.iterrows()} if len(sub) else {}
        L.append("| %s | %.6f | %.6f | %.6f |" % (s, vals.get("s_per_link", float("nan")),
                                                  vals.get("s_per_km", float("nan")),
                                                  vals.get("s_per_veh", float("nan"))))
    L += ["", "## 五、禁令", "",
          "- ⛔ 不得以单一 `delay share` 作头部结论（除非 Q4 判为 `SINGLE_HEADLINE_ADMISSIBLE`）。",
          "- ⛔ 不得跨面加权 / 归一 / 求和；四面不合成总分。",
          "- ⛔ 不得以 Gini 或常数 `top-k` 作集中度判据；集中度一律用覆盖率分数 `f_t`。",
          "- ⛔ 不得混用 `U_any` 与 `U_loaded`；`U_any` 量字段名必须带 `_any` 后缀。",
          "- 本轮判决：Q1 `%s` / Q2 `%s` / Q3 `%s`（SVC：`%s`）/ Q4 `%s`"
          % (fr.get("q1", ""), fr.get("q2", ""), fr.get("q3", ""), fr.get("q3_svc", ""), fr.get("q4", "")),
          ""]
    (out / "g2_reporting_template.md").write_bytes(("\n".join(L) + "\n").encode("utf-8"))


def write_summary(out: Path, payload: dict, rows: list) -> None:
    fr = payload.get("fr", {})
    s = {
        "step": STEP_ID, "status": payload["status"], "closure": payload.get("closure", ""),
        "gates_total": len(rows), "gates_pass": int(sum(1 for r in rows if r["pass_"])),
        "verdict_Q1": fr.get("q1", ""), "verdict_Q2": fr.get("q2", ""),
        "verdict_Q3": fr.get("q3", ""), "verdict_Q3_svc": fr.get("q3_svc", ""), "verdict_Q4": fr.get("q4", ""),
        "noop_selfcheck_passed": bool(fr.get("noop_ok", False)),
        "noop_selfcheck_detail": fr.get("noop_detail", ""),
        "prereg_sha256": PREREG_SHA, "prereg_bytes": PREREG_BYTES,
        "frozen_input_count": len(INPUTS), "read_only_reference_count": len(REFS),
        "frozen_input_sha256": {k: v[2] for k, v in INPUTS.items()},
        "ep_svc_time_share_pct": fr.get("shares_ep_loaded_pct", {}).get("time", float("nan")),
        "four_face_endpoint_service_spread_pp": fr.get("range_ep_pp", float("nan")),
        "universe_spread_pp": fr.get("spread_u_pp", float("nan")),
        "illegal_mixed_universe_ratio": fr.get("mixed_universe_ratio", float("nan")),
        "max_legal_share_pct": fr.get("legal_max_share_pct", float("nan")),
        "endpoint_ids": fr.get("endpoint_ids", -1), "pop_persons": fr.get("pop_persons", -1),
        "scope_loaded": {k: fr.get(k, {}) for k in ("d0", "d1", "ep_loaded")},
        "scope_any": {"ep_any": fr.get("ep_any", {}), "svc_any": fr.get("svc_any", {})},
        "shares_ep_loaded_pct": fr.get("shares_ep_loaded_pct", {}),
        "shares_ep_any_pct": fr.get("shares_ep_any_pct", {}),
        "intensity_loaded": fr.get("intensity_d0", {}), "intensity_ep_svc": fr.get("intensity_ep", {}),
        "gini_descriptive_only": fr.get("gini", {}),
        "rules": {"universe_spread_tol_pp": UNIVERSE_SPREAD_TOL_PP, "agreement_band_pp": AGREEMENT_BAND_PP,
                  "ratio_conc_min": RATIO_CONC_MIN, "cover_targets_pct": list(T_LEVELS),
                  "gini_decision_use": False, "fixed_top_k_use": False},
        "matsim_rerun": False, "model_modified": False, "zero_simulation": True,
    }
    (out / SUMMARY_NAME).write_bytes(json.dumps(s, ensure_ascii=False, indent=2).encode("utf-8"))


def write_report(out: Path, payload: dict, rows: list) -> None:
    fr = payload.get("fr", {})
    L = ["# STEP 7.9G-2 — 「时间 / 数量 / 距离 / 体积」四面口径统一 · R0（零仿真 / 只读）", "",
         "**STATUS: %s**" % payload["status"], "**CLOSURE: %s**" % payload.get("closure", ""), "",
         "- 门禁：**%d/%d**" % (sum(1 for r in rows if r["pass_"]), len(rows)),
         "- prereg：`%s`（%d B）" % (PREREG_SHA, PREREG_BYTES),
         "- 判决：Q1 `%s` / Q2 `%s` / Q3 `%s`（SVC：`%s`）/ Q4 `%s`"
         % (fr.get("q1", ""), fr.get("q2", ""), fr.get("q3", ""), fr.get("q3_svc", ""), fr.get("q4", "")),
         "- 无操作自检：`noop_selfcheck_passed=%s`（%s）" % (fr.get("noop_ok"), fr.get("noop_detail", "")), "",
         "## 一、统一规则（本节点交付物）", "", "```text",
         "D0 = ALL_LOADED ⊃ D1 = SERVICE_LOADED ⊃ D2 = ENDPOINT_SERVICE_LOADED   （默认宇宙 U_loaded）",
         "time -> IMPACT ; count / distance / volume -> EXPOSURE                 （角色固定，不互替）",
         "任何份额写作 share[face, scope | Dk] @ universe                         （四要素缺一不可）",
         "禁止合成总分；禁止用 Gini 或常数 top-k 作集中度判据",
         "集中度主仪器 = 覆盖率分数 f_t = k_t / n_scope , t ∈ {50,90,99}",
         "```", "",
         "> **`service` 端点链对仿真延误具有显著的时间暴露特征，但其影响并不与交通流量占比同步增长；",
         "> 因此应分别从时间、数量、距离和交通量四个维度表征，而不能以单一 `delay share`",
         "> 作为系统性拥堵归因依据。**", "",
         "## 二、四面实测（EP_SVC ｜ D0）", "",
         "| Face | Role | U_loaded | U_any | 撕裂 (pp) |", "|---|---|---:|---:|---:|"]
    for f in FACE_ORDER:
        sl = fr.get("shares_ep_loaded_pct", {}).get(f, float("nan"))
        sa = fr.get("shares_ep_any_pct", {}).get(f, float("nan"))
        L.append("| %s | %s | %.6f%% | %.6f%% | %.6f |"
                 % (f, "IMPACT" if f in IMPACT_FACES else "EXPOSURE", sl, sa, abs(sl - sa)))
    L += ["", "- 四面极差 `RANGE_ep` = **%.6f pp**（band = %.2f pp）" % (fr.get("range_ep_pp", float("nan")), AGREEMENT_BAND_PP),
          "- 宇宙撕裂 `SPREAD_U` = **%.6f pp**（tol = %.2f pp）" % (fr.get("spread_u_pp", float("nan")), UNIVERSE_SPREAD_TOL_PP),
          "- 非法混合宇宙比 `SVC_any_km / ALL_loaded_km` = **%.6f**（>1 ⇒ 门 10 显式标注 ILLEGAL）"
          % fr.get("mixed_universe_ratio", float("nan")), "",
          "## 三、锚点复算（逐位，atol = 0）", "",
          "| Scope | n | km | vol | delay_h |", "|---|---:|---:|---:|---:|"]
    for k, lbl in (("d0", "D0 ALL_LOADED"), ("d1", "D1 SVC_LOADED"), ("ep_loaded", "D2 EP_SVC_LOADED"),
                   ("ep_any", "U_any EP_SVC"), ("svc_any", "U_any SVC")):
        v = fr.get(k, {})
        L.append("| %s | %s | %.6f | %.6f | %.6f |"
                 % (lbl, v.get("n", ""), v.get("km", float("nan")), v.get("vol", float("nan")),
                    v.get("delay_h", float("nan"))))
    L += ["", "## 四、门禁明细", "", "| Gate | Pass | Detail |", "|---|---|---|"]
    for r in rows:
        L.append("| `%s` | %s | %s |" % (r["gate_id"], "PASS" if r["pass_"] else "FAIL", r["detail"]))
    L += ["", "## 五、边界", "",
          "- 本节点**只**统一口径与表达，不重判 G-1 的 `A1–A6`，不新增机制假说。",
          "- 未改 `Singapore_OD_MATSim_Final_v1.0`；未回写 G-0/G-1 任何冻结产物；未重跑 MATSim。", ""]
    (out / REPORT_NAME).write_bytes(("\n".join(L) + "\n").encode("utf-8"))


# ---------------------------------------------------------------------------
def main() -> int:
    global ROOT, REFS_DIR
    ap = argparse.ArgumentParser(description="7.9G-2 caliber harmonization audit (zero-simulation)")
    ap.add_argument("--out-dir", default=OUT_DEFAULT)
    ap.add_argument("--ref-dir", default="")
    ap.add_argument("--root", default="")
    args = ap.parse_args()
    if args.root:
        ROOT = Path(args.root)
    out = Path(args.out_dir)
    REFS_DIR = Path(args.ref_dir) if args.ref_dir else ROOT / "reports"
    out.mkdir(parents=True, exist_ok=True)

    print("=" * 78)
    print("STEP %s — CALIBER HARMONIZATION (zero-simulation / read-only)" % STEP_ID)
    print("=" * 78)
    t0 = time.time()

    inp, inp_errs = preflight_inputs()
    refs, ref_errs = preflight_refs(REFS_DIR)
    hdr, hdr_errs = preflight_linkstats_header()
    preflight_errors = inp_errs + ref_errs + hdr_errs
    blocked = bool(preflight_errors)
    print("  preflight errors=%s" % preflight_errors)

    guard_pre = {rel: walk_dir_shas(ROOT / rel) for rel in GUARD_DIRS}
    ctx: dict = {"out": out, "ref_dir": REFS_DIR, "inp": inp, "refs": refs, "hdr": hdr,
                 "blocked": blocked, "preflight_errors": preflight_errors, "guard_pre": guard_pre,
                 "manifest_records": {}, "closure_records": {}, "stray": [], "fr": {}, "dfs": {},
                 "n_net_links": -1, "n_net_ls": -1, "n_ls_only": -1, "n_ls_rows": -1}
    payload: dict = {"status": STATUS_BLOCKED, "closure": "", "fr": {}}
    empty_fm = pd.DataFrame(columns=["scope", "face", "face_role", "value", "units"])
    empty_im = pd.DataFrame(columns=["scope", "metric", "value"])

    if not blocked:
        try:
            m = load_links()
            ep = load_endpoint_links()
            net_links = set(m["link"])
            ls = pd.read_csv(ROOT / INPUTS["ls_final"][0], sep="\t", usecols=["LINK"], low_memory=False)
            ls_links = set(ls["LINK"].astype(str).str.strip())
            ctx["n_net_links"] = len(net_links)
            ctx["n_ls_rows"] = int(len(ls))
            ctx["n_net_ls"] = len(net_links & ls_links)
            ctx["n_ls_only"] = len(ls_links - net_links)
            print("  net=%d ls=%d covered=%d ls_not_in_net=%d (%.1fs)"
                  % (len(net_links), len(ls), ctx["n_net_ls"], ctx["n_ls_only"], time.time() - t0), flush=True)

            fr, dfs = build_analysis(m, ep)
            ok_noop, det_noop = noop_selfcheck(fr)
            fr["noop_ok"], fr["noop_detail"] = ok_noop, det_noop
            ctx["fr"], ctx["dfs"], payload["fr"] = fr, dfs, fr
            print("  Q1=%s Q2=%s Q3=%s Q4=%s noop=%s (%.1fs)"
                  % (fr["q1"], fr["q2"], fr["q3"], fr["q4"], ok_noop, time.time() - t0), flush=True)

            dfs["face_matrix"].to_csv(out / "g2_face_matrix.csv", index=False, encoding="utf-8-sig")
            dfs["share_matrix"].to_csv(out / "g2_share_matrix.csv", index=False, encoding="utf-8-sig")
            dfs["intensity_matrix"].to_csv(out / "g2_intensity_matrix.csv", index=False, encoding="utf-8-sig")
            dfs["universe_contrast"].to_csv(out / "g2_universe_contrast.csv", index=False, encoding="utf-8-sig")
            dfs["denominator_audit"].to_csv(out / "g2_denominator_audit.csv", index=False, encoding="utf-8-sig")
            dfs["concentration"].to_csv(out / "g2_concentration_curve.csv", index=False, encoding="utf-8-sig")
            dfs["concentration_verdict"].to_csv(out / "g2_concentration_verdict.csv", index=False, encoding="utf-8-sig")
            dfs["gap"].to_csv(out / "g2_exposure_impact_gap.csv", index=False, encoding="utf-8-sig")
            dfs["crosswalk"].to_csv(out / "g2_caliber_crosswalk.csv", index=False, encoding="utf-8-sig")
            dfs["verdicts"].to_csv(out / "g2_verdicts.csv", index=False, encoding="utf-8-sig")
            write_template(out, fr, dfs["face_matrix"], dfs["intensity_matrix"], dfs)
        except Exception:
            err = traceback.format_exc()
            print("ANALYSIS_ERROR:\n" + err[-2500:], flush=True)
            blocked = True
            ctx["blocked"] = True
            ctx["analysis_error"] = err[-500:]
            write_template(out, {}, empty_fm, empty_im, {})
    else:
        write_template(out, {}, empty_fm, empty_im, {})

    prev_state, prev_closure, converged, iterations, rows = None, "", False, 0, []
    for iterations in range(1, 8):
        rows = build_checks(payload, ctx)
        by = {r["gate_id"]: r for r in rows}
        rows = [by[g] for g in FINAL_ORDER if g in by] + [r for r in rows if r["gate_id"] not in FINAL_ORDER]
        core = [r for r in rows if not r["gate_id"].startswith("7.9G2.24_")]
        status = STATUS_READY if (all(r["pass_"] for r in core) and not blocked) else STATUS_BLOCKED
        payload["status"], payload["closure"] = status, prev_closure
        pd.DataFrame(rows).rename(columns={"pass_": "pass"}).to_csv(
            out / CHECKS_NAME, index=False, encoding="utf-8-sig")
        write_report(out, payload, rows)
        write_summary(out, payload, rows)

        manifest = build_manifest(out, ctx)
        ctx["manifest_records"] = manifest["generated_artifacts"]
        (out / MANIFEST_NAME).write_bytes(json.dumps(manifest, ensure_ascii=False, indent=2).encode("utf-8"))

        closure_df, closure_ok = build_closure(out, status, manifest)
        ctx["closure_records"] = {r["name"]: r for _, r in closure_df.iterrows() if r["kind"] == "artifact"}
        closure_df.to_csv(out / CLOSURE_NAME, index=False, encoding="utf-8-sig")
        final_closure = "OK" if closure_ok else "CLOSURE_FAILED"
        ctx["stray"] = sorted(f.name for f in out.iterdir()
                              if f.is_file() and f.name not in set(ARTIFACT_NAMES))

        state = (sha256_file(out / CHECKS_NAME), sha256_file(out / REPORT_NAME),
                 sha256_file(out / SUMMARY_NAME), sha256_file(out / MANIFEST_NAME),
                 sha256_file(out / CLOSURE_NAME), status, final_closure)
        if state == prev_state:
            converged = True
            break
        prev_state, prev_closure = state, final_closure

    npass = sum(1 for r in rows if r["pass_"])
    print("  converged=%s iterations=%d checks=%d/%d STATUS=%s CLOSURE=%s"
          % (converged, iterations, npass, len(rows), payload["status"], prev_closure))
    print("  total %.1fs" % (time.time() - t0))
    return 0 if (converged and payload["status"] == STATUS_READY and prev_closure == "OK") else 1


if __name__ == "__main__":
    sys.exit(main())
