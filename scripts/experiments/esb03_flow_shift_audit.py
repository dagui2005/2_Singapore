#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""
esb03_flow_shift_audit.py — E-SB-03：自由流速度变化后的观测域流量偏移审计（★零仿真·只读）
==========================================================================================
问题（校正后）：**不是**「怎样把 1.0601 调回 1.0」，**而是**「1.0601 到底反映了什么」。

数学起点（固定 SCALE 的恒等式）
    R_i = SCALE * sum_g Q^sim_{g,i} / sum_g Q^obs_g
    ⇒  R_A5 / R_v1.0 == sum_g Q^sim_{g,A5} / sum_g Q^sim_{g,v1.0}
    ⇒ 固定 SCALE 本身**不能**解释两臂之间的比例变化。

三条分支
    A 时间窗内的流量转移   —— 逐小时 HRSx-yavg（cycle it.10-19，构造**全时段**均值）
    B 路径重分配           —— 逐断面 ΔQ、正负抵消、等级/区域/环线/轴向/CBD 集中度、全网 vs 匹配子集
    C 观测域与聚合口径     —— 固定 576 断面，median/mean/max/positive_median × 匹配集敏感性

⛔ 只读：不改 v1.0 / 网络 / OD / crosswalk / TrafficFlow / SpeedBand / 评价器阈值 / SCALE。
⛔ 不启动 MATSim。产物只落 E-SB-03 与 reports/esb03_flow_shift_audit/。

用法：python scripts/experiments/esb03_flow_shift_audit.py
"""
from __future__ import annotations

import csv
import gzip
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(r"D:\Luan\2026-05\2_Singapore")
sys.path.insert(0, str(ROOT / "scripts" / "od"))

import compare_final_crosswalk_7_3_6b as bt  # noqa: E402  冻结口径（SCALE / load_traffic / calc_method）

E2 = ROOT / "experiments" / "E-SB-02_night_freeflow"
E3 = ROOT / "experiments" / "E-SB-03_flow_shift_audit"
AUDIT = E3 / "audit"
REPORT_DIR = ROOT / "reports" / "esb03_flow_shift_audit"
for d in (AUDIT, REPORT_DIR):
    d.mkdir(parents=True, exist_ok=True)

FINAL_CW = ROOT / "reports" / "od_final_calibration_crosswalk_7_3_6" / "final_calibration_crosswalk.csv"
TRAFFIC = ROOT / "Singapore_OD_MATSim_FinalData" / "08_TrafficCount" / "TrafficFlow_Data.json"
SEC_GEO = ROOT / "reports" / "od_structure_7_6c" / "section_geography.csv"

ARMS = {
    "v1.0": (ROOT / "matsim_final_7_6h" / "outputs" / "W01_rc_min", "W01_rc_min"),
    "SB-A5": (E2 / "outputs" / "SB-A5", "SB-A5"),
    "SB-A5ind": (E2 / "outputs" / "SB-A5ind", "SB-A5ind"),
}
BASE = "v1.0"
SCALE = float(bt.SCALE)
FROZEN_V10 = 0.9993347697
EXPECTED = {"v1.0": 0.9993348, "SB-A5": 1.0600691, "SB-A5ind": 1.0750786}   # 评分卡（cycle, 08-09）
CYCLE_ITERS = list(range(10, 20))
HOUR_COLS = [f"HRS{h}-{h+1}avg" for h in range(24)] + ["HRS0-24avg"]

GATES: list[dict] = []


def gate(cid: str, name: str, ok: bool, detail: str = "") -> bool:
    GATES.append({"id": cid, "gate": name, "pass": bool(ok), "detail": detail})
    print(f"  [{'PASS' if ok else 'FAIL'}] {cid}  {name}" + (f"  | {detail}" if detail else ""), flush=True)
    return bool(ok)


# --------------------------------------------------------------------------
# 载入（只读）
# --------------------------------------------------------------------------
def load_inputs():
    cw = bt.normalize_crosswalk(FINAL_CW, "final")
    obs = bt.load_traffic(TRAFFIC)
    geo = pd.read_csv(SEC_GEO)
    geo["lta_linkid"] = geo["lta_linkid"].astype(str).str.strip()
    return cw, obs, geo


def build_allhour_cycle(out_dir: Path, run_id: str, dest: Path) -> tuple[pd.DataFrame, int]:
    """it.10-19 的**全时段**逐列均值（LINK 为键）。与冻结 CYCLE_COLS 语义一致（均值可交换求和）。

    ★确定性缓存：dest 已存在则直接读回（内容由 it.10-19 唯一决定）。
    """
    if dest.exists():
        df = pd.read_csv(dest, sep="\t", dtype={c: "float64" for c in HOUR_COLS})
        return df, 10
    acc = None
    ref_index = None
    n = 0
    for it in CYCLE_ITERS:
        p = out_dir / "ITERS" / f"it.{it}" / f"{run_id}.{it}.linkstats.txt.gz"
        if not p.exists():
            continue
        df = pd.read_csv(p, sep="\t", usecols=["LINK"] + HOUR_COLS,
                         dtype={c: "float64" for c in HOUR_COLS}, low_memory=False)
        df = df.set_index("LINK")
        if ref_index is None:
            ref_index = df.index
            acc = df
        else:
            if not ref_index.equals(df.index):
                raise RuntimeError(f"{run_id} it.{it} LINK 索引与 it.{CYCLE_ITERS[0]} 不一致")
            acc = acc.add(df, fill_value=0.0)
        n += 1
    if acc is None:
        raise RuntimeError(f"{run_id}: 无 it.10-19 linkstats")
    acc = (acc / n).reset_index()
    acc.to_csv(dest, sep="\t", index=False)
    return acc, n


def section_table(cw: pd.DataFrame, obs: pd.DataFrame, sim: pd.DataFrame,
                  col: str, agg: str = "median") -> pd.DataFrame:
    """复刻 `bt.calc_method` 的断面聚合：匹配有向边 val(agg)（默认 median）→ ×SCALE。"""
    x = cw.merge(obs[["LinkID", "RoadCat", "RoadName", "obs_7_8", "obs_8_9", "obs_am"]],
                 left_on="lta_linkid", right_on="LinkID", how="inner")
    x = x.merge(sim[["LINK", col]], left_on="matsim_link_id", right_on="LINK", how="left")

    def f(s: pd.Series) -> float:
        s = s.dropna()
        if not len(s):
            return np.nan
        if agg == "median":
            return float(s.median())
        if agg == "mean":
            return float(s.mean())
        if agg == "max":
            return float(s.max())
        if agg == "min":
            return float(s.min())
        if agg == "positive_median":
            sp = s[s > 0]
            return float(sp.median()) if len(sp) else np.nan
        raise ValueError(agg)

    g = x.groupby("lta_linkid")
    out = pd.DataFrame({
        "val_raw": g[col].apply(f),
        "n_edges": g["matsim_link_id"].nunique(),
        "RoadCat": g["RoadCat"].first(),
        "RoadName": g["RoadName"].first(),
        "obs_7_8": g["obs_7_8"].first(),
        "obs_8_9": g["obs_8_9"].first(),
        "obs_am": g["obs_am"].first(),
    }).reset_index()
    out["val_scaled"] = out["val_raw"] * SCALE
    return out


def pooled(df: pd.DataFrame, sim_col: str, obs_col: str) -> float:
    o = df[obs_col].sum()
    return float(df[sim_col].sum() / o) if o else float("nan")


# --------------------------------------------------------------------------
def main() -> int:
    print("=" * 96)
    print("E-SB-03 自由流速度变化后的观测域流量偏移审计（零仿真 · 只读）")
    print("=" * 96)
    print(f"SCALE = {SCALE:.5f}（三臂同）；主窗 08-09；断面聚合 = median(匹配有向边 HRS8-9avg) × SCALE")

    cw, obs, geo = load_inputs()
    n_sec = cw["lta_linkid"].nunique()
    print(f"[in ] crosswalk 归一化：{n_sec} 个 LTA 断面 / {len(cw)} 行；obs {len(obs)} LinkID；geo {len(geo)}")

    # ---- 0. 冻结 cycle 文件（4 列）口径自校验 -----------------------------
    print("\n[0] 口径自校验（冻结 cycle 文件）")
    cyc4 = E2 / "audit" / "_cycle_linkstats"
    sec_v10_frozen = bt.calc_method(cw, obs, bt.load_linkstats(cyc4 / "v1.0_conv.linkstats.txt.gz"))
    r_frozen = pooled(sec_v10_frozen, "sim_8_9_scaled", "obs_8_9")
    gate("E01", f"冻结模块复算 v1.0 FROZEN(08-09) == {FROZEN_V10}（±1e-6）",
         abs(r_frozen - FROZEN_V10) < 1e-6, f"recomputed={r_frozen:.10f}")
    gate("E02a", "断面数 == 576", n_sec == 576, f"n_sections={n_sec}")

    # ---- 1. 构造全时段 cycle-mean（本审计目录内）--------------------------
    print("\n[1] 构造全时段 cycle-mean（it.10-19 逐列均值，只写本审计目录）")
    sim_all: dict[str, pd.DataFrame] = {}
    for lab, (out_dir, run_id) in ARMS.items():
        dest = AUDIT / f"{lab}_allhours_conv.linkstats.txt.gz"
        df, n_used = build_allhour_cycle(out_dir, run_id, dest)
        sim_all[lab] = df
        print(f"    {lab:9s} iters={n_used}  links={len(df):,}  -> {dest.name}", flush=True)

    # 用全时段文件复算 08-09 FROZEN ⇒ 必须与评分卡一致（证明同一基准）
    for lab in ARMS:
        s = section_table(cw, obs, sim_all[lab], "HRS8-9avg", "median")
        got = pooled(s, "val_scaled", "obs_8_9")
        gate(f"E07.{lab}", f"全时段文件在 08-09 复现评分卡 {lab} = {EXPECTED[lab]}（±1e-5）",
             abs(got - EXPECTED[lab]) < 1e-5, f"got={got:.7f}")

    # 三臂断面集合逐位相同
    sets = {lab: set(section_table(cw, obs, sim_all[lab], "HRS8-9avg")["lta_linkid"]) for lab in ARMS}
    same = all(sets[lab] == sets[BASE] for lab in ARMS)
    gate("E02b", "三臂断面集合逐位相同", same,
         " | ".join(f"{lab}={len(sets[lab])}" for lab in ARMS))
    gate("E04", "三臂 SCALE 相同 = 2.29897（读数自见证）", abs(SCALE - 2.29897) < 1e-9, f"SCALE={SCALE}")

    # ---- 表 1：总量分解 ---------------------------------------------------
    print("\n[2] 表 1  总量分解")
    sec_cache: dict[tuple[str, str], pd.DataFrame] = {}
    rows1 = []
    WINDOWS = [("07-08", ["HRS7-8avg"], ["obs_7_8"]),
               ("08-09", ["HRS8-9avg"], ["obs_8_9"]),
               ("07-09(双小时)", ["HRS7-8avg", "HRS8-9avg"], ["obs_7_8", "obs_8_9"]),
               ("09-10(无观测)", ["HRS9-10avg"], None)]
    for lab in ARMS:
        sim = sim_all[lab]
        for wname, cols, obcols in WINDOWS:
            s = section_table(cw, obs, sim, cols[0], "median")
            if len(cols) == 2:      # 双小时：逐断面相加
                s2 = section_table(cw, obs, sim, cols[1], "median")
                s = s.merge(s2[["lta_linkid", "val_raw", "val_scaled"]], on="lta_linkid",
                            suffixes=("", "_b"))
                s["val_raw"] = s["val_raw"].fillna(0) + s["val_raw_b"].fillna(0)
                s["val_scaled"] = s["val_scaled"].fillna(0) + s["val_scaled_b"].fillna(0)
                s["obs_sum"] = s["obs_7_8"].fillna(0) + s["obs_8_9"].fillna(0)
            else:
                s["obs_sum"] = s[obcols[0]] if obcols else np.nan
            sec_cache[(lab, wname)] = s
            net_sum = float(sim[cols].fillna(0).to_numpy().sum())      # 全网（全部链路，原始）
            matched_edges = s["val_raw"].notna()                       # 仅诊断
            rows1.append({
                "arm": lab, "window": wname,
                "n_sections": int(len(s)),
                "n_sim_gt0": int((s["val_scaled"].fillna(0) > 0).sum()),
                "sum_obs": float(s["obs_sum"].sum()) if obcols else np.nan,
                "sum_sim_raw": float(s["val_raw"].sum()),
                "sum_sim_scaled": float(s["val_scaled"].sum()),
                "SimObs": pooled(s, "val_scaled", "obs_sum") if obcols else np.nan,
                "net_sum_raw_all_links": net_sum,
            })
            print(f"    {lab:9s} {wname:14s} Σraw={rows1[-1]['sum_sim_raw']:>14,.1f}  "
                  f"Σscaled={rows1[-1]['sum_sim_scaled']:>14,.1f}  "
                  f"SimObs={rows1[-1]['SimObs'] if obcols else float('nan'):.7f}")
    t1 = pd.DataFrame(rows1)
    t1.to_csv(AUDIT / "esb03_total_decomposition.csv", index=False, encoding="utf-8-sig")

    # 恒等式 R_A5/R_v1.0 == Σraw_A5/Σraw_v1.0（08-09）
    a = t1[(t1.arm == "SB-A5") & (t1.window == "08-09")].iloc[0]
    b = t1[(t1.arm == BASE) & (t1.window == "08-09")].iloc[0]
    lhs = a["SimObs"] / b["SimObs"]
    rhs = a["sum_sim_raw"] / b["sum_sim_raw"]
    gate("E03", "恒等式 R_A5/R_v1.0 == Σraw_A5/Σraw_v1.0（±1e-9）",
         abs(lhs - rhs) < 1e-9, f"LHS={lhs:.10f}  RHS={rhs:.10f}")

    # ---- 表 2：逐断面差异 -------------------------------------------------
    print("\n[3] 表 2  逐断面差异")
    sv10 = sec_cache[(BASE, "08-09")][["lta_linkid", "val_raw", "val_scaled", "obs_8_9", "RoadCat", "RoadName", "n_edges"]]
    sa5 = sec_cache[("SB-A5", "08-09")][["lta_linkid", "val_raw", "val_scaled"]]
    saind = sec_cache[("SB-A5ind", "08-09")][["lta_linkid", "val_raw", "val_scaled"]]
    d = (sv10.rename(columns={"val_raw": "raw_v10", "val_scaled": "scaled_v10"})
         .merge(sa5.rename(columns={"val_raw": "raw_a5", "val_scaled": "scaled_a5"}), on="lta_linkid")
         .merge(saind.rename(columns={"val_raw": "raw_a5ind", "val_scaled": "scaled_a5ind"}), on="lta_linkid"))
    d["dQ_A5_v10"] = d["scaled_a5"] - d["scaled_v10"]
    d["dQ_A5ind_A5"] = d["scaled_a5ind"] - d["scaled_a5"]
    d["rel_dQ_A5_v10"] = np.where(d["scaled_v10"] > 0, d["dQ_A5_v10"] / d["scaled_v10"], np.nan)
    d = d.merge(geo, on="lta_linkid", how="left")
    d.to_csv(AUDIT / "esb03_section_delta.csv", index=False, encoding="utf-8-sig")

    def decompose(col: str) -> dict:
        v = d[col].fillna(0)
        pos, neg = v[v > 0], v[v < 0]
        return {"n_pos": int((v > 0).sum()), "n_neg": int((v < 0).sum()), "n_zero": int((v == 0).sum()),
                "sum_pos": float(pos.sum()), "sum_neg": float(neg.sum()), "net": float(v.sum()),
                "gross": float(pos.sum() - neg.sum())}

    dA = decompose("dQ_A5_v10")
    dB = decompose("dQ_A5ind_A5")
    closure = abs(dA["net"] - (a["sum_sim_scaled"] - b["sum_sim_scaled"]))
    gate("E05", "闭合：Σ_g ΔQ_g == ΣQ_A5 − ΣQ_v1.0（±1e-6）", closure < 1e-6, f"|diff|={closure:.3e}")
    # 负例：v1.0 自比
    self_d = float((d["scaled_v10"] - d["scaled_v10"]).abs().sum())
    gate("E06", "负例：v1.0 自比 ⇒ ΔQ 全 0", self_d == 0.0, f"Σ|ΔQ|={self_d}")
    print(f"    ΔQ(A5−v1.0): n+= {dA['n_pos']}  n-= {dA['n_neg']}  n0= {dA['n_zero']}  "
          f"Σ+= {dA['sum_pos']:,.0f}  Σ−= {dA['sum_neg']:,.0f}  net= {dA['net']:,.0f}  gross= {dA['gross']:,.0f}")
    print(f"    ΔQ(A5ind−A5): n+= {dB['n_pos']}  n-= {dB['n_neg']}  n0= {dB['n_zero']}  "
          f"Σ+= {dB['sum_pos']:,.0f}  Σ−= {dB['sum_neg']:,.0f}  net= {dB['net']:,.0f}  gross= {dB['gross']:,.0f}")

    # 集中度（按分组）
    def group_conc(by: str) -> pd.DataFrame:
        rows = []
        for key, g in d.groupby(by, dropna=False):
            rows.append({
                by: str(key),
                "n": int(len(g)),
                "sum_obs": float(g["obs_8_9"].sum()),
                "sum_scaled_v10": float(g["scaled_v10"].sum()),
                "sum_scaled_a5": float(g["scaled_a5"].sum()),
                "dQ_A5_v10": float(g["dQ_A5_v10"].sum()),
                "dQ_A5ind_A5": float(g["dQ_A5ind_A5"].sum()),
                "ratio_v10": float(g["scaled_v10"].sum() / g["obs_8_9"].sum()) if g["obs_8_9"].sum() else np.nan,
                "ratio_a5": float(g["scaled_a5"].sum() / g["obs_8_9"].sum()) if g["obs_8_9"].sum() else np.nan,
            })
        out = pd.DataFrame(rows)
        tot = dA["net"]
        out["share_of_net_pct"] = np.where(abs(tot) > 0, out["dQ_A5_v10"] / tot * 100, np.nan)
        return out.sort_values("dQ_A5_v10", ascending=False)

    conc = []
    for by in ["RoadCat", "region", "ring", "radial", "pa"]:
        if by in d.columns:
            g = group_conc(by)
            g["group_by"] = by
            conc.append(g)
    d["cbd_band"] = pd.cut(d["d_cbd_m"], [0, 2000, 5000, 10000, 20000, 1e9],
                           labels=["<2km", "2-5km", "5-10km", "10-20km", ">20km"])
    g = group_conc("cbd_band"); g["group_by"] = "cbd_band"; conc.append(g)
    g = group_conc("n_edges"); g["group_by"] = "n_edges(匹配边数)"; conc.append(g)
    tc = pd.concat(conc, ignore_index=True)
    tc.to_csv(AUDIT / "esb03_concentration_by_group.csv", index=False, encoding="utf-8-sig")

    # 全网 vs 匹配子集
    print("\n[3b] 全网 vs 匹配子集（覆盖率陷阱对照）")
    matched_edges = set(cw["matsim_link_id"].astype(str))
    rowsN = []
    for lab in ARMS:
        sim = sim_all[lab].copy()
        sim["LINK"] = sim["LINK"].astype(str)
        net = float(sim["HRS8-9avg"].fillna(0).sum())
        msk = sim["LINK"].isin(matched_edges)
        rowsN.append({"arm": lab,
                      "net_all_links_raw": net,
                      "net_matched_edges_raw": float(sim.loc[msk, "HRS8-9avg"].fillna(0).sum()),
                      "n_all_links": int(len(sim)),
                      "n_matched_edges": int(msk.sum())})
        print(f"    {lab:9s} 全网 Σ={rowsN[-1]['net_all_links_raw']:>14,.1f}  "
              f"匹配边 Σ={rowsN[-1]['net_matched_edges_raw']:>12,.1f}  "
              f"占全网 {rowsN[-1]['net_matched_edges_raw']/rowsN[-1]['net_all_links_raw']*100:.2f}%")
    tN = pd.DataFrame(rowsN)
    tN["d_net_vs_v10_pct"] = (tN["net_all_links_raw"] / float(tN.loc[tN.arm == BASE, "net_all_links_raw"].iloc[0]) - 1) * 100
    tN["d_matched_vs_v10_pct"] = (tN["net_matched_edges_raw"] / float(tN.loc[tN.arm == BASE, "net_matched_edges_raw"].iloc[0]) - 1) * 100
    tN.to_csv(AUDIT / "esb03_network_vs_matched.csv", index=False, encoding="utf-8-sig")
    for _, r in tN.iterrows():
        print(f"    {r['arm']:9s} Δ全网={r['d_net_vs_v10_pct']:+.2f}%  Δ匹配边={r['d_matched_vs_v10_pct']:+.2f}%")

    # ---- 表 3a：时间窗敏感性 ---------------------------------------------
    print("\n[4] 表 3a  时间窗敏感性（逐小时 Σsim，cycle it.10-19）")
    rows3 = []
    for h in range(24):
        col = f"HRS{h}-{h+1}avg"
        rec = {"hour": f"{h:02d}-{h+1:02d}", "observed": h in (7, 8)}
        for lab in ARMS:
            s = section_table(cw, obs, sim_all[lab], col, "median")
            rec[f"sec_raw_{lab}"] = float(s["val_raw"].sum())
            rec[f"net_raw_{lab}"] = float(sim_all[lab][col].fillna(0).sum())
        rec["d_sec_A5_v10_pct"] = (rec["sec_raw_SB-A5"] / rec["sec_raw_v1.0"] - 1) * 100 if rec["sec_raw_v1.0"] else np.nan
        rec["d_sec_A5ind_v10_pct"] = (rec["sec_raw_SB-A5ind"] / rec["sec_raw_v1.0"] - 1) * 100 if rec["sec_raw_v1.0"] else np.nan
        rec["d_net_A5_v10_pct"] = (rec["net_raw_SB-A5"] / rec["net_raw_v1.0"] - 1) * 100 if rec["net_raw_v1.0"] else np.nan
        rows3.append(rec)
    t3 = pd.DataFrame(rows3)
    for lab in ARMS:
        tot = t3[f"sec_raw_{lab}"].sum()
        t3[f"share24_{lab}_pct"] = t3[f"sec_raw_{lab}"] / tot * 100
    t3.to_csv(AUDIT / "esb03_window_sensitivity.csv", index=False, encoding="utf-8-sig")
    for h in [6, 7, 8, 9, 10, 11]:
        r = t3[t3.hour == f"{h:02d}-{h+1:02d}"].iloc[0]
        print(f"    {r['hour']}  obs={r['observed']!s:5s}  "
              f"Σ_v10={r['sec_raw_v1.0']:>13,.1f}  Δ(A5)={r['d_sec_A5_v10_pct']:+7.2f}%  "
              f"Δ(A5ind)={r['d_sec_A5ind_v10_pct']:+7.2f}%  Δnet(A5)={r['d_net_A5_v10_pct']:+7.2f}%")

    # ---- 表 3b：聚合与匹配集敏感性 ---------------------------------------
    print("\n[5] 表 3b  聚合 / 匹配集敏感性（固定 576 断面，08-09）")
    rows4 = []
    for agg in ["median", "mean", "max", "positive_median"]:
        rec = {"aggregation": agg}
        for lab in ARMS:
            s = section_table(cw, obs, sim_all[lab], "HRS8-9avg", agg)
            rec[f"SimObs_{lab}"] = pooled(s, "val_scaled", "obs_8_9")
            rec[f"n_sim_gt0_{lab}"] = int((s["val_scaled"].fillna(0) > 0).sum())
            rec[f"n_{lab}"] = int(len(s))
        rec["ratio_A5_over_v10"] = rec["SimObs_SB-A5"] / rec["SimObs_v1.0"]
        rec["ratio_A5ind_over_A5"] = rec["SimObs_SB-A5ind"] / rec["SimObs_SB-A5"]
        rows4.append(rec)
    # 匹配集敏感性（median 口径）
    for subset, cond in [("全 576", lambda s: np.ones(len(s), bool)),
                         ("三臂皆 sim>0", lambda s: (s["val_scaled"].fillna(0) > 0)),
                         ("n_edges==1", None), ("n_edges>1", None)]:
        rec = {"aggregation": f"median|{subset}"}
        sub = {}
        for lab in ARMS:
            s = section_table(cw, obs, sim_all[lab], "HRS8-9avg", "median")
            if subset == "n_edges==1":
                s = s[s["n_edges"] == 1]
            elif subset == "n_edges>1":
                s = s[s["n_edges"] > 1]
            elif subset == "三臂皆 sim>0":
                s = s[s["val_scaled"].fillna(0) > 0]
            sub[lab] = s
            rec[f"SimObs_{lab}"] = pooled(s, "val_scaled", "obs_8_9")
            rec[f"n_{lab}"] = int(len(s))
        rec["ratio_A5_over_v10"] = rec["SimObs_SB-A5"] / rec["SimObs_v1.0"]
        rec["ratio_A5ind_over_A5"] = rec["SimObs_SB-A5ind"] / rec["SimObs_SB-A5"]
        rows4.append(rec)
    t4 = pd.DataFrame(rows4)
    t4.to_csv(AUDIT / "esb03_aggregation_sensitivity.csv", index=False, encoding="utf-8-sig")
    for _, r in t4.iterrows():
        print(f"    {r['aggregation']:22s} SimObs v1.0={r['SimObs_v1.0']:.5f}  A5={r['SimObs_SB-A5']:.5f}  "
              f"A5ind={r['SimObs_SB-A5ind']:.5f}  R(A5/v10)={r['ratio_A5_over_v10']:.5f}  "
              f"R(A5ind/A5)={r['ratio_A5ind_over_A5']:.5f}")

    gate("E02c", "表 3b 全 576 行 == 576", int(t4.iloc[0]["n_v1.0"]) == 576 and int(t4.iloc[0]["n_SB-A5"]) == 576,
         f"n_v10={int(t4.iloc[0]['n_v1.0'])} n_A5={int(t4.iloc[0]['n_SB-A5'])}")

    # ---- 汇总 ------------------------------------------------------------
    summary = {
        "audit": "E-SB-03", "scale": SCALE, "base_arm": BASE,
        "frozen_v10_08_09": r_frozen,
        "total_decomposition": t1.to_dict("records"),
        "section_delta_decomp": {"A5_vs_v10": dA, "A5ind_vs_A5": dB},
        "network_vs_matched": tN.to_dict("records"),
        "window_sensitivity": t3.to_dict("records"),
        "aggregation_sensitivity": t4.to_dict("records"),
        "concentration_by_group": tc.to_dict("records"),
        "gates": GATES,
        "written": [str(p) for p in sorted(AUDIT.glob("*"))],
    }
    (AUDIT / "esb03_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2, default=str),
                                              encoding="utf-8")
    pd.DataFrame(GATES).to_csv(AUDIT / "esb03_gates.csv", index=False, encoding="utf-8-sig")

    n_fail = sum(1 for g in GATES if not g["pass"])
    print("\n" + "=" * 96)
    print(f"门禁：{len(GATES) - n_fail}/{len(GATES)} PASS"
          + (f"  ⚠️ {n_fail} 项 FAIL" if n_fail else "  ✅"))
    print(f"落盘：{AUDIT}")
    return 0 if n_fail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
