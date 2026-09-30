#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
analyze_kw_7_9b1.py — Step 7.9B-1 三层解释 + C3/C4 空间判据（零仿真，只读）

用户冻结的判读口径（★红线：两件事必须分开判定）
------------------------------------------------
  ①「kinematicWaves 改变了拥堵传播机制」      —— 有仿真结果即可验证
  ②「kinematicWaves 让拥堵位置更接近真实结构瓶颈」—— 必须**同时**得到 C3/C4 空间证据
  ⇒ 成功 ≠ 「比 queue 更堵」；成功 = 「稳定性不过关的前提下，不仅产生动力学差异，
     而且这种差异具有可解释的空间结构」。

三层
----
  L1 有没有产生动力学变化：Sim/Obs、v/c、excess delay、congested-component length、
                           07-09 in-network vehicles、KW 特有 inflow-capacity 使用
  L2 有没有形成真正的连续拥堵：isolated links -> short chains -> junction clusters
                           -> connected components（C-0 建立的空间尺度）
  L3 堵的位置有没有改善：C3 HitRate/Coverage/lift vs v1.0 基线；CTE/service/ramp/connector；
                           C2 式「残差 -> 结构单元」投影检验（ρ + 置换零分布）

复用（逐位同源）
---------------
  bt / ev1 / E / d76 / a76d / e7_6f0   —— 冻结 Sim/Obs 与稳定性口径
  _cache_network_7_9c0.npz / _cache_link_unit_7_9b1.npz —— 网络 + L1 单元（已自校验）
  c0_C3_hitrate_coverage.json / c0_C2_residual_projection.csv —— 7.9C-0 预登记阈值与映射

运行
----
    python scripts/od/analyze_kw_7_9b1.py              # 主体（快）
    python scripts/od/analyze_kw_7_9b1.py --events     # 追加 events 时段层（慢，~40 min）
"""
from __future__ import annotations

import argparse
import csv
import gzip
import io
import json
import math
import os
import sys
import time
from collections import defaultdict
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(r"D:\Luan\2026-05\2_Singapore")
sys.path.insert(0, str(ROOT / "scripts" / "od"))

import compare_final_crosswalk_7_3_6b as bt          # noqa: E402
import evaluate_calibration_7_4_2 as ev1             # noqa: E402
import evaluate_demand_response_7_6f_1 as E          # noqa: E402
import diagnose_od_spatial_structure_7_6c as d76     # noqa: E402
import audit_routechoice_stability_7_6d as a76d      # noqa: E402

# ---------------------------------------------------------------- paths ----
KW_ROOT = ROOT / "matsim_kw_7_9b1"
KW_OUT = KW_ROOT / "outputs" / "W01_kw"
KW_RUN = "W01_kw"
KW_LS19 = KW_OUT / "ITERS" / "it.19" / f"{KW_RUN}.19.linkstats.txt.gz"
KW_EVENTS = KW_OUT / f"{KW_RUN}.output_events.xml.gz"

V1_OUT = ROOT / "matsim_final_7_6h" / "outputs" / "W01_rc_min"
V1_RUN = "W01_rc_min"
V1_LS19 = V1_OUT / "ITERS" / "it.19" / f"{V1_RUN}.19.linkstats.txt.gz"
V1_EVENTS = ROOT / "matsim_viz_7_8" / "outputs" / "W01_events" / "W01_events.output_events.xml.gz"

C0_DIR = ROOT / "reports" / "structural_junction_cluster_audit_7_9c0"
C3_JSON = C0_DIR / "c0_C3_hitrate_coverage.json"
C2_PROJ = C0_DIR / "c0_C2_residual_projection.csv"
CACHE_NET = ROOT / "scripts" / "od" / "_cache_network_7_9c0.npz"
CACHE_UNIT = ROOT / "scripts" / "od" / "_cache_link_unit_7_9b1.npz"

OUT = ROOT / "reports" / "kw_single_variable_7_9b1"
AUDIT = OUT

FROZEN_DIRS = [ROOT / "matsim_final_7_6h", ROOT / "matsim_viz_7_8"]
V1_SIM_OBS = 0.9993347697
V1_BAND = (1.1637, 1.1938)
GUARDRAIL_SIM_OBS = 0.85
MODEL_PHASE_CHANGE = 71_136          # 正 OD cell 下界（采样硬下界，只读引用）

# 7.9C-0 冻结常量
PRIOR_CAND = 80.0
CONG_Q = 80.0
L_SHORT_M = 51.953
CELL = 7.5
TIME_STEP = 1.0
F_CAP = 1.0
EXC_THR = 0.1                        # 7.7E「真实超额」阈值
REF_ITER = 19
CONV_START, CONV_END = 10, 19

CHECKS: list[dict] = []


def gate(cid: str, name: str, ok, detail: str = "") -> bool:
    CHECKS.append({"check": cid, "name": name, "pass": ok if ok == "WARN" else bool(ok), "detail": detail})
    tag = "WARN" if ok == "WARN" else ("PASS" if ok else "FAIL")
    print(f"  [{tag}] {cid} {name}" + (f"  ({detail})" if detail else ""), flush=True)
    return bool(ok) if ok != "WARN" else True


def log(m: str = "") -> None:
    print(m, flush=True)


def banner(m: str) -> None:
    print("\n" + "=" * 92 + f"\n{m}\n" + "=" * 92, flush=True)


def spearman(a, b) -> float:
    a = np.asarray(a, dtype=float)
    b = np.asarray(b, dtype=float)
    if len(a) < 3:
        return float("nan")
    ra = np.argsort(np.argsort(a)).astype(float)
    rb = np.argsort(np.argsort(b)).astype(float)
    ra -= ra.mean(); rb -= rb.mean()
    d = math.sqrt((ra ** 2).sum() * (rb ** 2).sum())
    return float((ra * rb).sum() / d) if d > 0 else float("nan")


def snap(dirs):
    s = {}
    for d in dirs:
        for dp, _, fns in os.walk(d):
            for fn in fns:
                p = os.path.join(dp, fn)
                try:
                    s[p] = (os.path.getmtime(p), os.path.getsize(p))
                except OSError:
                    pass
    return s


# ==========================================================================
def read_linkstats_metrics(ls_path: Path, link_ids: list[str], n: int) -> dict:
    """按缓存 link 顺序对齐，产出 v/c、excess delay 等逐链路量。"""
    df = pd.read_csv(ls_path, sep="\t", compression="gzip",
                     usecols=["LINK", "LENGTH", "FREESPEED", "CAPACITY",
                              "HRS8-9avg", "TRAVELTIME8-9avg"],
                     dtype={"LINK": str}, low_memory=False)
    df["LINK"] = df["LINK"].astype(str).str.strip()
    pos = pd.Series(np.arange(n, dtype=np.int64), index=np.array(link_ids))
    jj = pos.reindex(df["LINK"].to_numpy()).to_numpy()
    good = ~pd.isna(jj)

    length = np.zeros(n); fs = np.zeros(n); cap = np.zeros(n)
    vol = np.zeros(n); tt = np.full(n, np.nan)
    idx = jj[good].astype(np.int64)
    length[idx] = pd.to_numeric(df["LENGTH"], errors="coerce").to_numpy()[good]
    fs[idx] = pd.to_numeric(df["FREESPEED"], errors="coerce").to_numpy()[good]
    cap[idx] = pd.to_numeric(df["CAPACITY"], errors="coerce").to_numpy()[good]
    vol[idx] = np.nan_to_num(pd.to_numeric(df["HRS8-9avg"], errors="coerce").to_numpy()[good], nan=0.0)
    tt[idx] = pd.to_numeric(df["TRAVELTIME8-9avg"], errors="coerce").to_numpy()[good]

    Lk = length * 0.001
    vc = np.where(cap > 0, vol / cap, 0.0)
    with np.errstate(divide="ignore", invalid="ignore"):
        ff = np.where(fs > 0, length / fs, np.nan)          # s
        quant = np.where(ff > 0, np.ceil(ff) / ff, np.nan)  # 1.0 s 时间步量化伪影
        excess = tt / ff - quant                            # 真实超额（扣量化）
    excess = np.where(np.isfinite(excess), excess, 0.0)
    delay_h = np.where(np.isfinite(tt) & np.isfinite(ff),
                       np.maximum(tt - np.ceil(ff), 0.0) * vol, 0.0) / 3600.0

    return {"vol": vol, "cap": cap, "Lk": Lk, "vc": vc, "excess": excess,
            "delay_h": delay_h, "len_m": length, "fs_mps": fs,
            "matched": int(good.sum())}


def add_highway(metrics: dict, hw: np.ndarray, nm: np.ndarray) -> None:
    hw = np.array([str(x) for x in hw])
    nm = np.array([str(x) for x in nm])
    metrics["hw"] = hw
    metrics["nm"] = nm
    metrics["cls"] = np.array([
        "ramp" if h in ("motorway_link", "trunk_link")
        else "connector" if h.endswith("_link")
        else "service" if h == "service"
        else "motorway" if h in ("motorway", "trunk")
        else "other" for h in hw])
    upstream = np.array([("CTE" in x.upper() or "CHANGI" in x.upper() or "TAMPINES EXP" in x.upper())
                         for x in nm])
    metrics["cte"] = upstream


def components(mask_Lk: np.ndarray, frm, to, sel: np.ndarray):
    """在 sel 选中的链路集合上按共享节点做有向连通分量。"""
    parent = {}
    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]; x = parent[x]
        return x
    idxs = np.where(sel)[0]
    for i in idxs:
        a, b = frm[i], to[i]
        for x in (a, b):
            if x not in parent:
                parent[x] = x
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[rb] = ra
    comp = defaultdict(list)
    for i in idxs:
        comp[find(frm[i])].append(int(i))
    sizes = sorted((len(v) for v in comp.values()), reverse=True)
    lens = sorted((sum(mask_Lk[i] for i in v) for v in comp.values()), reverse=True)
    iso = sum(1 for v in comp.values() if len(v) == 1)
    return {"n_links": int(sel.sum()), "n_components": len(sizes),
            "max_component_links": int(sizes[0]) if sizes else 0,
            "max_component_km": float(lens[0]) if lens else 0.0,
            "median_component_m": float(np.median(lens) * 1000.0) if lens else 0.0,
            "isolated_links": int(iso), "comp_link_sizes": sizes[:12]}


def unit_vc(link2unit: np.ndarray, n_units: int, vc: np.ndarray, Lk: np.ndarray) -> np.ndarray:
    U = np.zeros(n_units); W = np.zeros(n_units); S = np.zeros(n_units)
    tot = np.zeros(n_units); sat = np.zeros(n_units)
    for i in range(len(link2unit)):
        u = link2unit[i]
        if u < 0:
            continue
        w = max(Lk[i], 1e-9)
        U[u] += vc[i] * w; W[u] += w
        tot[u] += Lk[i]
        if vc[i] >= 1.0:
            sat[u] += 1.0
    out = np.where(W > 0, U / np.maximum(W, 1e-12), 0.0)
    return out, tot, sat


def unit_wmean(link2unit: np.ndarray, n_units: int, val: np.ndarray, Lk: np.ndarray) -> np.ndarray:
    """按链路长度加权，把任意 link 级量聚合到 L1 结构单元（向量化）。"""
    u = link2unit
    valid = u >= 0
    w = np.where(valid, np.maximum(Lk, 1e-9), 0.0)
    W = np.bincount(u[valid], weights=w[valid], minlength=n_units)
    U = np.bincount(u[valid], weights=(val * w)[valid], minlength=n_units)
    return np.where(W > 0, U / np.maximum(W, 1e-12), 0.0)


def hitrate_coverage(prior: np.ndarray, uvc: np.ndarray, thr_prior: float, thr_cong: float) -> dict:
    cand = prior >= thr_prior
    high = uvc >= thr_cong
    inter = int((cand & high).sum())
    nh, nc = int(high.sum()), int(cand.sum())
    hit = inter / nh if nh else float("nan")
    cov = inter / nc if nc else float("nan")
    base = nc / len(prior)
    lift = hit / base if base else float("nan")
    return {"thr_prior": thr_prior, "thr_cong": thr_cong, "n_candidate": nc,
            "n_model_high": nh, "n_intersection": inter,
            "HitRate": hit, "Coverage": cov, "base_rate": base, "lift_vs_random": lift}


# ==========================================================================
def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--events", action="store_true", help="追加 events 时段层（慢）")
    args = ap.parse_args()

    AUDIT.mkdir(parents=True, exist_ok=True)
    E.OUT = AUDIT
    E.CYCLE_DIR = AUDIT / "_cycle_linkstats"
    E.CYCLE_DIR.mkdir(parents=True, exist_ok=True)
    ev0 = snap(FROZEN_DIRS)
    t_start = time.time()

    banner("Step 7.9B-1 ANALYZE — kinematicWaves 单变量实验（零仿真只读）")
    if not KW_LS19.exists():
        log(f"!! 尚未找到 7.9B-1 输出：{KW_LS19}")
        log("   请先运行 run_kw_single_variable_7_9b1.py --run")
        return 3

    # ---- 缓存 -------------------------------------------------------------
    zu = np.load(CACHE_UNIT, allow_pickle=True)
    zn = np.load(CACHE_NET, allow_pickle=True)
    link_ids = [str(x) for x in zu["link_ids"]]
    n = int(zu["n"])
    link2unit = zu["link2unit"].astype(np.int64)
    uid_list = [str(x) for x in zu["uid_list"]]
    prior = zu["prior"].astype(float)
    n_units = int(zu["n_units"])
    u_km = zu["u_km"].astype(float)
    frm = [str(x) for x in zn["frm"]]
    to = [str(x) for x in zn["to"]]
    hw = zn["highway"]; nm = zn["name"]
    log(f"[0] 缓存：links={n:,}  units={n_units:,}  links_in_units={int((link2unit>=0).sum()):,}")

    # ======================================================================
    banner("L0 — 口径自校验（用冻结模块复算 v1.0，必须 == 0.9993347697）")
    obs = bt.load_traffic(ev1.TRAFFIC)
    cw = bt.normalize_crosswalk(ev1.FINAL_CW, "final")
    cwraw = pd.read_csv(ev1.FINAL_CW, encoding="utf-8-sig")
    cwraw["matsim_link_id"] = cwraw["matsim_link_id"].astype(str).str.strip()
    cw_prim = cwraw[cwraw["is_primary_candidate"]].copy() \
        if "is_primary_candidate" in cwraw.columns else cwraw.copy()
    matched = set(cwraw["matsim_link_id"])
    cata = set(cwraw.loc[cwraw["RoadCat"] == "CATA", "matsim_link_id"])
    slip = set(cwraw.loc[cwraw["RoadCat"] == "SLIP_ROAD", "matsim_link_id"])
    geo = pd.read_csv(d76.OUT_DIR / "section_geography.csv")[
        ["lta_linkid", "mid_x", "mid_y", "d_cbd_m", "n_links", "radial", "ring", "region", "pa"]]
    geo["lta_linkid"] = geo["lta_linkid"].astype(str).str.strip()

    RUNS = {
        "V1": {"label": "V1", "role": "frozen_v1_0_queue", "lambda": 0.075, "f_demand": 1.180222,
               "N": 236_044, "out_dir": V1_OUT, "run_id": V1_RUN, "stage": "7.6H",
               "desc": "v1.0 冻结（queue, f_cap=1.0）"},
        "KW": {"label": "KW", "role": "kinematic_waves_single_variable", "lambda": 0.075,
               "f_demand": 1.180222, "N": 236_044, "out_dir": KW_OUT, "run_id": KW_RUN,
               "stage": "7.9B-1", "desc": "7.9B-1（kinematicWaves, f_cap=1.0，其余继承）"},
    }
    res = {}
    for k in ("V1", "KW"):
        log(f"\n[eval] {RUNS[k]['label']} — {RUNS[k]['desc']}")
        res[k] = E.eval_run(RUNS[k], cw, cw_prim, obs, geo, matched, cata, slip,
                            force_cycle=(k == "KW"))

    v1_simobs = float(res["V1"]["q"]["FROZEN"])
    gate("L0.01", f"★口径自校验：复算 v1.0 Sim/Obs == {V1_SIM_OBS}（±1e-6）",
         abs(v1_simobs - V1_SIM_OBS) < 1e-6, f"recomputed={v1_simobs:.10f}")
    kw_simobs = float(res["KW"]["q"]["FROZEN"])
    kw_simobs_19 = float(res["KW"]["q_19"]["FROZEN"])
    gate("L0.02", f"7.9B-1（KW）Sim/Obs 已计算", np.isfinite(kw_simobs),
         f"Qbar_10:19={kw_simobs:.7f}  it19={kw_simobs_19:.7f}")

    # ======================================================================
    banner("L1 — 有没有产生动力学变化")
    v1m = read_linkstats_metrics(V1_LS19, link_ids, n)
    kwm = read_linkstats_metrics(KW_LS19, link_ids, n)
    for z_ in (v1m, kwm):
        add_highway(z_, hw, nm)
    gate("L1.01", "两条运行 linkstats 均对齐 693,575 链路",
         v1m["matched"] == n and kwm["matched"] == n,
         f"v1={v1m['matched']:,} kw={kwm['matched']:,}")

    sat1 = v1m["vc"] >= 1.0
    satk = kwm["vc"] >= 1.0
    exc1 = v1m["excess"] > EXC_THR
    exck = kwm["excess"] > EXC_THR
    gate("L1.02", "v1.0 自检：饱和 link = 82 / 1.151 km（与 7.9A-0 冻结投影一致）",
         int(sat1.sum()) == 82 and abs(v1m["Lk"][sat1].sum() - 1.151) < 0.02,
         f"{int(sat1.sum())} links / {v1m['Lk'][sat1].sum():.3f} km")
    log(f"  KW: 饱和(v/c>=1) = {int(satk.sum()):,} links ({100*satk.mean():.4f}%) / "
        f"{kwm['Lk'][satk].sum():.3f} km ({100*kwm['Lk'][satk].sum()/kwm['Lk'].sum():.4f}%)")
    log(f"  KW: 真实超额 > {EXC_THR} = {int(exck.sum()):,} links / {kwm['Lk'][exck].sum():.3f} km")
    log(f"  V1: 真实超额 > {EXC_THR} = {int(exc1.sum()):,} links / {v1m['Lk'][exc1].sum():.3f} km")
    log(f"  KW: 总延误车时 = {kwm['delay_h'].sum():,.0f} h   V1: {v1m['delay_h'].sum():,.0f} h")
    log(f"  ★崩解护栏：Sim/Obs(KW) = {kw_simobs:.7f}（阈值 >= {GUARDRAIL_SIM_OBS}）")
    gate("L1.03", f"★崩解护栏：Sim/Obs(KW) >= {GUARDRAIL_SIM_OBS}（总量量级未崩）",
         kw_simobs >= GUARDRAIL_SIM_OBS, f"{kw_simobs:.7f}")

    # ---- KW 特有：FD 入口容量是否真的开始约束 --------------------------
    # 逐链路 FD 入口上限：maxFlowFromFdiag = (lanes/cellSize) / (1/(15/3.6) + 1/freespeed)
    lanes = zn["lanes"].astype(float)
    fs_mps = kwm["fs_mps"]
    denom = (3.6 / 15.0) + np.where(fs_mps > 0, 1.0 / fs_mps, np.nan)
    q_fd = 3600.0 * (lanes / CELL) / denom            # veh/h
    r_fd = np.where(kwm["cap"] > 0, q_fd / kwm["cap"], np.nan)
    capped = r_fd < 1.0
    binding_kw = capped & (kwm["vol"] > 0) & (np.abs(kwm["vol"] - q_fd) <= 0.02 * np.maximum(q_fd, 1.0))
    bind_v1 = capped & (v1m["vol"] > 0) & (np.abs(v1m["vol"] - q_fd) <= 0.02 * np.maximum(q_fd, 1.0))
    log(f"  FD 入口上限 r_fdiag<1 的链路：{int(capped.sum()):,} ({100*capped.mean():.2f}%) / "
        f"{kwm['Lk'][capped].sum():.1f} km")
    log(f"  ★实际被入口上限「顶住」(realized ≈ q_fdiag)：KW = {int(binding_kw.sum()):,} links  "
        f"vs V1(queue) = {int(bind_v1.sum()):,} links")
    gate("L1.04", "KW 特有 FD 入口约束已被度量（binding link 计数）",
         np.isfinite(q_fd[capped]).all(), f"capped={int(capped.sum()):,} binding_kw={int(binding_kw.sum()):,}")

    # ---- 07-09 in-network vehicles（events；可选） ----------------------
    ev_series = None
    if args.events:
        ev_series = parse_events_windows()

    # ======================================================================
    banner("L2 — 有没有形成真正的连续拥堵（isolated -> short chain -> junction cluster -> component）")
    # 预登记阈值（7.9C-0 冻结）：「候选结构单元」判据，L2/L3 共用
    c3f = json.load(open(C3_JSON, encoding="utf-8"))
    thr_prior = float(c3f["thr_prior"])
    thr_v1 = float(c3f["thr_unit_vc"])
    _valid = link2unit >= 0
    cand_link = np.zeros(n, dtype=bool)
    cand_link[_valid] = prior[link2unit[_valid]] >= thr_prior
    l2 = {}
    for tag, m, sat, exc in (("V1", v1m, sat1, exc1), ("KW", kwm, satk, exck)):
        comp_sat = components(m["Lk"], frm, to, sat)
        comp_exc = components(m["Lk"], frm, to, exc)
        # junction-cluster 层：含饱和链路的 L1 单元
        u_of = link2unit[sat]
        u_of = u_of[u_of >= 0]
        hit_units = int(len(set(u_of.tolist())))
        u_of_exc = link2unit[exc]
        u_of_exc = u_of_exc[u_of_exc >= 0]
        hit_units_exc = int(len(set(u_of_exc.tolist())))
        n_exc = int(exc.sum())
        frac_exc_cand = (float((exc & cand_link).sum()) / n_exc) if n_exc else float("nan")
        enrich_exc = (frac_exc_cand / float(cand_link.mean())) if n_exc else float("nan")
        uvc_kw, ukm, usat = unit_vc(link2unit, n_units, m["vc"], m["Lk"])
        uex = unit_wmean(link2unit, n_units, m["excess"], m["Lk"])
        sat_km_in_units = float(sum(m["Lk"][i] for i in np.where(sat)[0] if link2unit[i] >= 0))
        # short-chain 层（L2 类）
        cls_sat = {c: int((sat & (m["cls"] == c)).sum()) for c in
                   ("ramp", "connector", "service", "motorway", "other")}
        l2[tag] = {"saturated": comp_sat, "excess_gt_0.1": comp_exc,
                   "n_units_with_saturated": hit_units,
                   "n_units_with_excess": hit_units_exc,
                   "sat_km_in_units": sat_km_in_units,
                   "sat_links_by_class": cls_sat,
                   "frac_excess_in_candidate_units": frac_exc_cand,
                   "enrichment_excess_vs_base": enrich_exc,
                   "total_delay_h": float(m["delay_h"].sum()),
                   "delay_h_by_class": {c: float(m["delay_h"][m["cls"] == c].sum())
                                        for c in ("ramp", "connector", "service", "motorway", "other")},
                   "u_vc": uvc_kw, "u_km": ukm, "u_sat": usat, "u_exc": uex}
        log(f"  [{tag}] 饱和集合：{comp_sat['n_links']:,} links / {comp_sat['n_components']:,} 分量 / "
            f"最长 {comp_sat['max_component_km']:.3f} km / 中位 {comp_sat['median_component_m']:.1f} m / "
            f"孤立 {comp_sat['isolated_links']:,}")
        log(f"       真实超额集合：{comp_exc['n_links']:,} links / {comp_exc['n_components']:,} 分量 / "
            f"最长 {comp_exc['max_component_km']:.3f} km")
        log(f"       命中 junction-cluster 单元：饱和 {hit_units:,} / 超额 {hit_units_exc:,} / {n_units:,}")
        log(f"       ★超额链路落在「候选结构单元」内的比例 = {frac_exc_cand:.4%}"
            f"（base={cand_link.mean():.4%}，富集={enrich_exc:.3f}×）")
    gate("L2.01", "四尺度聚合（isolated / short-chain / junction-cluster / component）已计算（两次运行）",
         all(l2[k]["saturated"]["n_components"] >= 0 for k in l2), "ok")
    gate("L2.02", "最长拥堵连通分量已计算（V1 vs KW）",
         np.isfinite(l2["V1"]["saturated"]["max_component_km"]) and np.isfinite(l2["KW"]["saturated"]["max_component_km"]),
         f"V1={l2['V1']['saturated']['max_component_km']:.3f} km  KW={l2['KW']['saturated']['max_component_km']:.3f} km")

    # ======================================================================
    banner("L3 — 堵的位置有没有改善（C3/C4 + C2 式残差投影）")
    c3f = json.load(open(C3_JSON, encoding="utf-8"))
    thr_prior = float(c3f["thr_prior"])
    thr_v1 = float(c3f["thr_unit_vc"])
    uvc_v1 = l2["V1"]["u_vc"]; uvc_kw = l2["KW"]["u_vc"]

    c3_tbl = []
    variants = [
        ("FROZEN_v1_p80", thr_prior, thr_v1),
        ("KW_own_p80", thr_prior, float(np.percentile(uvc_kw, CONG_Q))),
        ("ABS_unit_vc_0.5", thr_prior, 0.5),
        ("ABS_unit_vc_1.0", thr_prior, 1.0),
    ]
    for name, tp, tc in variants:
        a = hitrate_coverage(prior, uvc_v1, tp, tc)
        b = hitrate_coverage(prior, uvc_kw, tp, tc)
        c3_tbl.append({"variant": name, "thr_prior": tp, "thr_cong": tc,
                       "V1_HitRate": a["HitRate"], "V1_Coverage": a["Coverage"],
                       "V1_lift": a["lift_vs_random"], "V1_n_high": a["n_model_high"],
                       "KW_HitRate": b["HitRate"], "KW_Coverage": b["Coverage"],
                       "KW_lift": b["lift_vs_random"], "KW_n_high": b["n_model_high"],
                       "d_lift": (b["lift_vs_random"] - a["lift_vs_random"])})
        log(f"  [{name}] thr_cong={tc:.6f}  V1 lift={a['lift_vs_random']:.3f}x "
            f"(n_high={a['n_model_high']:,})  KW lift={b['lift_vs_random']:.3f}x (n_high={b['n_model_high']:,})")
    _nd = [r for r in c3_tbl if r["KW_n_high"] > 0 and r["V1_n_high"] > 0]
    gate("L3.01", "C3 HitRate/Coverage/lift 已在阈值变体下计算（V1 vs KW；退化变体 n_high=0 不计）",
         len(_nd) >= 3, f"n_variants={len(c3_tbl)} 非退化={len(_nd)}")
    gate("L3.02", "★预登记阈值（7.9C-0 冻结）下的 C3 已给出",
         any(r["variant"] == "FROZEN_v1_p80" for r in c3_tbl), "FROZEN_v1_p80")

    # ---- C2 式：残差 -> 结构单元 投影（ρ + 置换零分布） -------------------
    proj = pd.read_csv(C2_PROJ, encoding="utf-8-sig")
    proj["lta_linkid"] = proj["lta_linkid"].astype(str).str.strip()
    sec_kw = res["KW"]["sec"][["lta_linkid", "ratio_8_9", "obs_8_9", "sim_8_9_scaled"]].copy()
    sec_kw["lta_linkid"] = sec_kw["lta_linkid"].astype(str).str.strip()
    mg = proj.merge(sec_kw, on="lta_linkid", how="left", suffixes=("_v1", ""))
    mg["rel_dev_kw"] = mg["ratio_8_9"] / kw_simobs - 1.0
    mg["rel_dev_v1"] = mg["rel_dev"]

    def proj_rho(df: pd.DataFrame, col: str, min_sec: int = 1) -> float:
        g = df.dropna(subset=[col]).groupby("unit_id").agg(
            rd=(col, "mean"), n=("lta_linkid", "size"), pr=("unit_prior", "first"))
        g = g[g["n"] >= min_sec]
        return spearman(g["pr"], g["rd"]), int(len(g))

    rho_kw, nu_kw = proj_rho(mg, "rel_dev_kw")
    rho_v1, nu_v1 = proj_rho(mg, "rel_dev_v1")
    rho_kw2, nu_kw2 = proj_rho(mg, "rel_dev_kw", 2)
    rho_v12, nu_v12 = proj_rho(mg, "rel_dev_v1", 2)

    rng = np.random.default_rng(20260920)
    reg = mg["region"].astype(str).to_numpy()
    units = mg["unit_id"].to_numpy(); uprior = mg["unit_prior"].to_numpy()
    vals_kw = mg["rel_dev_kw"].to_numpy(); vals_v1 = mg["rel_dev_v1"].to_numpy()

    def perm_p(vals: np.ndarray, obs: float, nperm: int = 400):
        idx_by_reg = defaultdict(list)
        for i, r in enumerate(reg):
            idx_by_reg[r].append(i)
        null = []
        for _ in range(nperm):
            v = vals.copy()
            for r, idx in idx_by_reg.items():
                idx = np.array(idx)
                v[idx] = rng.permutation(v[idx])
            tmp = pd.DataFrame({"unit_id": units, "pr": uprior, "rd": v}).dropna()
            gg = tmp.groupby("unit_id").agg(rd=("rd", "mean"), pr=("pr", "first"))
            null.append(spearman(gg["pr"], gg["rd"]))
        null = np.array(null, dtype=float)
        return {"mean": float(np.nanmean(null)), "sd": float(np.nanstd(null)),
                "p_ge": float(np.nanmean(null >= obs)), "n_perm": nperm}

    pn_kw = perm_p(vals_kw, rho_kw)
    pn_v1 = perm_p(vals_v1, rho_v1)
    log(f"  C2 式投影：V1  ρ={rho_v1:.4f}（n_units={nu_v1}）KW  ρ={rho_kw:.4f}（n_units={nu_kw}）")
    log(f"    置换零分布 KW: mean={pn_kw['mean']:.4f} sd={pn_kw['sd']:.4f}  p={pn_kw['p_ge']:.4f}")
    log(f"    置换零分布 V1: mean={pn_v1['mean']:.4f} sd={pn_v1['sd']:.4f}  p={pn_v1['p_ge']:.4f}")
    gate("L3.03", "★C2 式残差投影已对 KW 执行（ρ + 同区域置换零分布 400 次）",
         np.isfinite(rho_kw) and np.isfinite(pn_kw["p_ge"]), f"rho_kw={rho_kw:.4f} p={pn_kw['p_ge']:.4f}")

    # ---- 辅助口径（★非预登记）：按「真实超额」定义的单位级拥堵 -----------------
    # 动机：KW 经 FD 入口上限压低 v/c（流量被削 15%），用 v/c 判「堵在哪」会系统性低估；
    # 故另按 超额 = TT/FF − ceil(FF)/FF 的长度加权单位级量，复算同一 C3 判据（对称施加于两 run）。
    aux = {}
    thr_exc_v1 = float(np.percentile(l2["V1"]["u_exc"], CONG_Q))
    for rtag in ("V1", "KW"):
        uex = l2[rtag]["u_exc"]
        own = float(np.percentile(uex, CONG_Q))
        aux[rtag] = {"thr_own_p80": own, "own": hitrate_coverage(prior, uex, thr_prior, own),
                     "frozen_v1_thr": thr_exc_v1,
                     "at_v1_thr": hitrate_coverage(prior, uex, thr_prior, thr_exc_v1)}
    log(f"  辅助口径（真实超额；★非预登记）：V1 lift={aux['V1']['own']['lift_vs_random']:.3f}x"
        f"（n_high={aux['V1']['own']['n_model_high']:,}）  "
        f"KW lift={aux['KW']['own']['lift_vs_random']:.3f}x（n_high={aux['KW']['own']['n_model_high']:,}）")
    log(f"     同一 v1.0 阈值下：V1 lift={aux['V1']['at_v1_thr']['lift_vs_random']:.3f}x  "
        f"KW lift={aux['KW']['at_v1_thr']['lift_vs_random']:.3f}x")
    gate("L3.05", "辅助口径（真实超额）位置判据已对称计算（明确标注为非预登记）",
         np.isfinite(aux["KW"]["own"]["lift_vs_random"]), f"KW lift={aux['KW']['own']['lift_vs_random']:.3f}x")

    # ---- 分类别（CTE / service / ramp / connector） ----------------------
    cls_rows = []
    for tag, m, sat, exc in (("V1", v1m, sat1, exc1), ("KW", kwm, satk, exck)):
        for c in ("motorway", "ramp", "connector", "service", "other"):
            sel = m["cls"] == c
            cls_rows.append({"run": tag, "class": c, "links": int(sel.sum()),
                             "km": float(m["Lk"][sel].sum()),
                             "sat_links": int((sel & sat).sum()),
                             "sat_km": float(m["Lk"][sel & sat].sum()),
                             "delay_h": float(m["delay_h"][sel].sum()),
                             "mean_vc_loaded": float(m["vc"][sel & (m["vol"] > 0)].mean())
                             if (sel & (m["vol"] > 0)).any() else 0.0})
    # CTE 专列
    for tag, m, sat in (("V1", v1m, sat1), ("KW", kwm, satk)):
        sel = m["cte"]
        cls_rows.append({"run": tag, "class": "CTE_corridor", "links": int(sel.sum()),
                         "km": float(m["Lk"][sel].sum()), "sat_links": int((sel & sat).sum()),
                         "sat_km": float(m["Lk"][sel & sat].sum()),
                         "delay_h": float(m["delay_h"][sel].sum()),
                         "mean_vc_loaded": float(m["vc"][sel & (m["vol"] > 0)].mean())
                         if (sel & (m["vol"] > 0)).any() else 0.0})
    gate("L3.04", "分类别（motorway/ramp/connector/service/CTE）分解已计算",
         len(cls_rows) == 12, f"{len(cls_rows)} rows")

    # ======================================================================
    banner("裁决（★机制变化 与 位置改善 分开判定）")
    stab = res["KW"]["stab"]["MATCHED"]
    a_kw = float(stab["A_10_19"]); pg_kw = float(stab["parity_gap_rel"])
    a_v1 = float(res["V1"]["stab"]["MATCHED"]["A_10_19"])
    d_sat_km = kwm["Lk"][satk].sum() - v1m["Lk"][sat1].sum()
    d_delay = kwm["delay_h"].sum() - v1m["delay_h"].sum()
    d_comp = l2["KW"]["saturated"]["max_component_km"] - l2["V1"]["saturated"]["max_component_km"]

    mech_change = (abs(d_sat_km) > 1.0) or (abs(d_delay) > 0.05 * max(v1m["delay_h"].sum(), 1.0)) \
        or (abs(d_comp) > 0.05)
    pos_row = [r for r in c3_tbl if r["variant"] == "FROZEN_v1_p80"][0]
    pos_change = pos_row["d_lift"]
    log(f"  ① 机制变化：Δ饱和里程={d_sat_km:+.3f} km  Δ延误车时={d_delay:+,.0f} h  "
        f"Δ最长分量={d_comp:+.3f} km  ⇒ {'有' if mech_change else '无'}实质变化")
    log(f"     稳定性：A_10:19(MATCHED) KW={a_kw:.4%} vs V1={a_v1:.4%}；parity_gap={pg_kw:.4%}")
    log(f"  ② 位置改善：C3 lift Δ={pos_change:+.3f}x（预登记阈值）；"
        f"C2 式 ρ(KW)={rho_kw:.4f} / p={pn_kw['p_ge']:.4f} vs V1 ρ={rho_v1:.4f} / p={pn_v1['p_ge']:.4f}")

    v_mech = "KW_CHANGES_CONGESTION_MECHANISM" if mech_change else "KW_NO_MECHANISM_CHANGE"
    v_pos = ("KW_POSITION_IMPROVED" if pos_change > 0.15 else
             "KW_POSITION_NOT_IMPROVED" if pos_change > -0.15 else "KW_POSITION_DEGRADED")
    v_stab = "STABILITY_OK" if (a_kw < 0.05 and pg_kw < 0.05) else "STABILITY_MARGINAL"
    verdict = f"{v_mech}__{v_pos}__{v_stab}"

    # ======================================================================
    # 产物
    pd.DataFrame([{**{"run": k}, **{kk: vv for kk, vv in res[k]["q"].items()},
                   "SimObs_it19": res[k]["q_19"]["FROZEN"],
                   "A_10_19_MATCHED": res[k]["stab"]["MATCHED"]["A_10_19"],
                   "parity_gap_rel": res[k]["stab"]["MATCHED"]["parity_gap_rel"],
                   "Qbar_10_19": res[k]["stab"]["MATCHED"]["Qbar_10_19"]}
                  for k in ("V1", "KW")]).to_csv(
        AUDIT / "b1_simobs_stability.csv", index=False, encoding="utf-8-sig")

    pd.DataFrame(l2["V1"]["u_vc"], columns=["v1_unit_vc"]).join(
        pd.DataFrame(l2["KW"]["u_vc"], columns=["kw_unit_vc"])).assign(
        unit_id=uid_list, prior=prior, km=u_km).to_csv(
        AUDIT / "b1_unit_vc_kw.csv", index=False, encoding="utf-8-sig")

    pd.DataFrame(c3_tbl).to_csv(AUDIT / "b1_c3_hitrate_coverage.csv", index=False, encoding="utf-8-sig")
    pd.DataFrame(cls_rows).to_csv(AUDIT / "b1_class_breakdown.csv", index=False, encoding="utf-8-sig")

    l1j = {
        "simobs_v1": v1_simobs, "simobs_kw": kw_simobs, "simobs_kw_it19": kw_simobs_19,
        "guardrail": GUARDRAIL_SIM_OBS, "guardrail_pass": bool(kw_simobs >= GUARDRAIL_SIM_OBS),
        "v1_saturated": {"links": int(sat1.sum()), "km": float(v1m["Lk"][sat1].sum())},
        "kw_saturated": {"links": int(satk.sum()), "km": float(kwm["Lk"][satk].sum())},
        "v1_excess_gt_0.1": {"links": int(exc1.sum()), "km": float(v1m["Lk"][exc1].sum())},
        "kw_excess_gt_0.1": {"links": int(exck.sum()), "km": float(kwm["Lk"][exck].sum())},
        "v1_delay_h": float(v1m["delay_h"].sum()), "kw_delay_h": float(kwm["delay_h"].sum()),
        "kw_fd_capped_links": int(capped.sum()),
        "kw_fd_binding_links": int(binding_kw.sum()),
        "v1_fd_binding_links": int(bind_v1.sum()),
        "kw_stability": {"A_10_19": a_kw, "parity_gap_rel": pg_kw, "Qbar_10_19": float(stab["Qbar_10_19"])},
        "v1_stability": {"A_10_19": a_v1,
                         "parity_gap_rel": float(res["V1"]["stab"]["MATCHED"]["parity_gap_rel"])},
    }
    json.dump(l1j, open(AUDIT / "b1_layer1_dynamics.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)
    json.dump({k: {kk: vv for kk, vv in v.items() if kk not in ("u_vc", "u_km", "u_sat", "u_exc")}
               for k, v in l2.items()},
              open(AUDIT / "b1_layer2_continuity.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)
    json.dump({"c3": c3_tbl,
               "c2_projection": {"rho_kw": rho_kw, "n_units_kw": nu_kw,
                                 "rho_v1": rho_v1, "n_units_v1": nu_v1,
                                 "rho_kw_multisec": rho_kw2, "rho_v1_multisec": rho_v12,
                                 "perm_null_kw": pn_kw, "perm_null_v1": pn_v1,
                                 "reading": ("残差是否向结构单元聚集 = 位置判据；"
                                             "ρ 的正负与显著性以置换零分布为准")},
               "aux_excess_based_not_preregistered": aux,
               "class_breakdown_rows": len(cls_rows),
               "verdict_mechanism": v_mech, "verdict_position": v_pos,
               "verdict_stability": v_stab},
              open(AUDIT / "b1_layer3_spatial.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)

    frozen_ok = snap(FROZEN_DIRS) == ev0
    gate("L9.01", "冻结件（matsim_final_7_6h + matsim_viz_7_8）本步未改动", frozen_ok,
         f"changed={'0' if frozen_ok else 'NONZERO'}")

    summary = {"step": "7.9B-1", "verdict": verdict,
               "verdict_mechanism": v_mech, "verdict_position": v_pos, "verdict_stability": v_stab,
               "n_checks": len(CHECKS),
               "n_pass": sum(1 for c in CHECKS if c["pass"] is True),
               "failed": [c["check"] for c in CHECKS if c["pass"] is False],
               "l1": l1j, "c3": c3_tbl,
               "c2_projection": {"rho_kw": rho_kw, "p_kw": pn_kw["p_ge"],
                                 "rho_v1": rho_v1, "p_v1": pn_v1["p_ge"]},
               "aux_excess_based": {k: {"lift_own": aux[k]["own"]["lift_vs_random"],
                                        "lift_at_v1_thr": aux[k]["at_v1_thr"]["lift_vs_random"],
                                        "n_high_own": aux[k]["own"]["n_model_high"]} for k in ("V1", "KW")},
               "l2_key": {k: {"n_units_with_excess": l2[k]["n_units_with_excess"],
                              "frac_excess_in_candidate_units": l2[k]["frac_excess_in_candidate_units"],
                              "enrichment_excess_vs_base": l2[k]["enrichment_excess_vs_base"],
                              "excess_components": l2[k]["excess_gt_0.1"]["n_components"],
                              "excess_max_component_km": l2[k]["excess_gt_0.1"]["max_component_km"]}
                          for k in ("V1", "KW")},
               "runtime_sec": round(time.time() - t_start, 1),
               "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
    json.dump(summary, open(AUDIT / "b1_analysis_summary.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)
    with open(AUDIT / "b1_analysis_checks.csv", "w", newline="", encoding="utf-8-sig") as fh:
        w = csv.DictWriter(fh, fieldnames=["check", "name", "pass", "detail"]); w.writeheader()
        w.writerows(CHECKS)

    banner(f"verdict = {verdict}")
    log(f"  checks: {summary['n_pass']}/{len(CHECKS)} PASS"
        + (f"  失败 {summary['failed']}" if summary["failed"] else ""))
    log(f"  runtime: {summary['runtime_sec']}s")
    return 0


def parse_events_windows() -> dict:
    """从 events 提取 07-09 的 15 min 在途车辆（queue vs KW）。"""
    out = {}
    for tag, p in (("V1", V1_EVENTS), ("KW", KW_EVENTS)):
        if not p.exists():
            out[tag] = None
            continue
        t0 = time.time()
        ent = np.zeros(97); exi = np.zeros(97)
        with gzip.open(p, "rt", encoding="utf-8", errors="replace") as fh:
            for line in fh:
                if 'type="vehicle enters traffic"' in line:
                    k = _bucket(line)
                    if k is not None:
                        ent[k] += 1
                elif 'type="vehicle leaves traffic"' in line:
                    k = _bucket(line)
                    if k is not None:
                        exi[k] += 1
        cum = np.cumsum(ent - exi)
        out[tag] = {"enters": ent.tolist(), "leaves": exi.tolist(),
                    "in_network_15min": cum.tolist(),
                    "seconds": round(time.time() - t0, 1)}
        log(f"  [events:{tag}] 07:00-09:00 峰值在途 = {int(cum[28:36].max()):,} 车  "
            f"({out[tag]['seconds']}s)")
    if out.get("V1") and out.get("KW"):
        df = pd.DataFrame({"bin_start": [f"{7 + (i // 4):02d}:{(i % 4) * 15:02d}" for i in range(32)],
                           "V1_in_network": out["V1"]["in_network_15min"][4:36],
                           "KW_in_network": out["KW"]["in_network_15min"][4:36]})
        df.to_csv(AUDIT / "b1_events_timeseries_15min.csv", index=False, encoding="utf-8-sig")
    return out


def _bucket(line: str):
    i = line.find('time="')
    if i < 0:
        return None
    j = line.find('"', i + 6)
    try:
        t = float(line[i + 6:j])
    except ValueError:
        return None
    if t < 0 or t > 86400:
        return None
    return min(96, int(t // 900))


if __name__ == "__main__":
    sys.exit(main())
