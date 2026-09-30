# -*- coding: utf-8 -*-
"""Step 7.9I-A · 走廊级容量加权比较（观测域尺度修正）

⛔ 零仿真、只读。不改 v1.0、不改任何冻结件、不重跑 MATSim。
判据与口径一律以 `reports/corridor_scale_audit_7_9i/PREREG_7_9I.md` 为准（运行前冻结）。

核心问题
--------------------------------------------------
  把比较从「边级流量」搬到「流量占容量多少」的尺度上，
  sim 与 obs 之间**是否仍存在系统性偏差**？

三种口径（§2.2，并报）
--------------------------------------------------
  走廊 = LTA `RoadName`；`E_c` = 该走廊所有断面的匹配边并集（去重）
  (1) 断面级累加（主）：sim_flow_c^sec = SCALE × Σ_{s∈c} Σ_{e∈E_s} HRS8-9avg(e)
  (2) 边级去重（对照）：sim_flow_c^edge= SCALE × Σ_{e∈E_c} HRS8-9avg(e)
  (3) 代表值（canonical）：sim_flow_c^med = SCALE × Σ_{s∈c} median_e HRS8-9avg(e)
      obs_flow_c = Σ_{s∈c} obs_8_9(s) ；cap_c = Σ cap_eff(e)

★ 1:K 计数机制（本阶段新识别）
--------------------------------------------------
  1 个 LTA 断面典型对应 K 条 MATSim 边（K = Σ_s n_edges(s) / n_sections）。
  若这些边**承载同一股车流**，则「断面级累加」把 sim 放大 ≈K 倍，而 obs 只计 1 次
  ⇒ `ratio_simobs ≈ K`。故定义**去尺度残差**：
      ratio_simobs_norm = ratio_simobs / K_c
  ⇒ ≈1 表示该走廊的偏差**可被 1:K 计数完全解释**；≪1 表示**真实缺载**。
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(r"D:\Luan\2026-05\2_Singapore")
sys.path.insert(0, str(ROOT / "scripts" / "od"))

import audit_sampling_capacity_7_9a1 as A          # noqa: E402
import compare_final_crosswalk_7_3_6b as bt        # noqa: E402
import evaluate_calibration_7_4_2 as ev1           # noqa: E402
from diagnose_gap_7_9h import read_edge_full       # noqa: E402

OUT = ROOT / "reports" / "corridor_scale_audit_7_9i"
OUT.mkdir(parents=True, exist_ok=True)

CYCLE = {
    "v1.0": ROOT / "reports" / "sampling_capacity_7_9a1" / "_cycle_linkstats"
            / "V1_conv.linkstats.txt.gz",
    "A-1": ROOT / "reports" / "sampling_capacity_7_9a1" / "_cycle_linkstats"
           / "A1_conv.linkstats.txt.gz",
}
FULL_LS = {"v1.0": A.V10_LS, "A-1": A.A1_LS}
CAPMUL = {"v1.0": 1.0, "A-1": A.F_CAP}
SCALE = bt.SCALE
R_LOW = 0.50
NORM_LOW = 0.50          # 去尺度残差 < 0.5 ⇒ 判为「真实缺载走廊」

EXP = {
    "n_sections": 576, "n_cw_rows": 3193, "n_matched_edges": 3037,
    "pooled_median": {"v1.0": 0.9993348, "A-1": 0.7664761},
    "pooled_sum": {"v1.0": 4.1616, "A-1": 3.1384},
    "flow_share_matched": {"v1.0": 0.0664, "A-1": 0.0529},
}


# --------------------------------------------------------------------------- 载入
def load_frozen():
    obs = bt.load_traffic(ev1.TRAFFIC)
    obs["LinkID"] = obs["LinkID"].astype(str).str.strip()
    obs["RoadName"] = obs["RoadName"].fillna("").astype(str).str.strip().str.upper()
    cw = bt.normalize_crosswalk(ev1.FINAL_CW, "final")
    cw["lta_linkid"] = cw["lta_linkid"].astype(str).str.strip()
    cw["matsim_link_id"] = cw["matsim_link_id"].astype(str).str.strip()
    cwraw = pd.read_csv(ev1.FINAL_CW, encoding="utf-8-sig")
    cwraw["matsim_link_id"] = cwraw["matsim_link_id"].astype(str).str.strip()
    return obs, cw, set(cwraw["matsim_link_id"])


def section_table(v: str, obs, cw, edge_df) -> pd.DataFrame:
    sim = bt.load_linkstats(CYCLE[v])
    sim["LINK"] = sim["LINK"].astype(str).str.strip()
    x = (cw.merge(obs, left_on="lta_linkid", right_on="LinkID", how="inner")
           .merge(sim, left_on="matsim_link_id", right_on="LINK", how="left")
           .merge(edge_df[["LINK", "LENGTH", "CAPACITY", "FREESPEED"]],
                  left_on="matsim_link_id", right_on="LINK", how="left",
                  suffixes=("", "_e")))
    g = x.groupby("lta_linkid", as_index=False).agg(
        RoadName=("RoadName", "first"), RoadCat=("RoadCat", "first"),
        obs_8_9=("obs_8_9", "first"), obs_7_8=("obs_7_8", "first"),
        n_edges=("matsim_link_id", "nunique"),
        sim_median=("HRS8-9avg", "median"),
        sim_sum=("HRS8-9avg", "sum"),
        n_edge_flow_gt0=("HRS8-9avg", lambda s: int((s > 0).sum())),
        cap_sum=("CAPACITY", "sum"),
        len_sum=("LENGTH", "sum"),
    )
    for c in ("sim_median", "sim_sum"):
        g[c + "_xS"] = g[c] * SCALE
    g["cap_eff_sum"] = g["cap_sum"] * CAPMUL[v]
    g["ratio_median"] = g["sim_median_xS"] / g["obs_8_9"].replace(0, np.nan)
    g["cap_edge_mean"] = g["cap_eff_sum"] / g["n_edges"].replace(0, np.nan)
    return g


# --------------------------------------------------------------------------- 走廊
def corridor_table(g: pd.DataFrame, cw: pd.DataFrame, edge_df: pd.DataFrame,
                   cap_mul: float) -> pd.DataFrame:
    pairs = (g[["lta_linkid", "RoadName"]].merge(cw, on="lta_linkid", how="left")
             [["RoadName", "matsim_link_id"]].drop_duplicates())
    ea = edge_df.set_index("LINK")[["HRS8-9avg", "CAPACITY", "LENGTH"]]
    ce = pairs.join(ea, on="matsim_link_id")
    ce["_flow"] = ce["HRS8-9avg"]
    corr = ce.groupby("RoadName", as_index=False).agg(
        n_links=("matsim_link_id", "nunique"),
        n_links_missing=("_flow", lambda s: int(s.isna().sum())),
        sim_edge_sum=("_flow", "sum"),
        cap_edge_sum=("CAPACITY", "sum"),
        len_edge_sum=("LENGTH", "sum"),
    )
    oc = g.groupby("RoadName", as_index=False).agg(
        n_sections=("lta_linkid", "nunique"),
        obs_flow=("obs_8_9", "sum"),
        sim_sec_raw=("sim_sum", "sum"),
        sim_med_raw=("sim_median", "sum"),
        cap_sec_raw=("cap_sum", "sum"),
        len_sec_raw=("len_sum", "sum"),
        n_edge_sec=("n_edges", "sum"),          # Σ_sections n_edges(s)  ← 计数基数
    )
    c = oc.merge(corr, on="RoadName", how="outer")
    c["sim_flow_sec"] = c["sim_sec_raw"] * SCALE
    c["sim_flow_med"] = c["sim_med_raw"] * SCALE
    c["sim_flow_edge"] = c["sim_edge_sum"] * SCALE
    c["cap_sec"] = c["cap_sec_raw"] * cap_mul
    c["cap_edge"] = c["cap_edge_sum"] * cap_mul

    with np.errstate(divide="ignore", invalid="ignore"):
        c["K_c"] = c["n_edge_sec"] / c["n_sections"].replace(0, np.nan)
        c["ratio_simobs"] = c["sim_flow_sec"] / c["obs_flow"].replace(0, np.nan)
        c["ratio_simobs_med"] = c["sim_flow_med"] / c["obs_flow"].replace(0, np.nan)
        c["ratio_simobs_norm"] = c["ratio_simobs"] / c["K_c"]
        # 容量的两种尺度：断面级累加 / 每 (断面,边) 对平均
        c["cap_per_pair"] = c["cap_sec"] / c["n_edge_sec"].replace(0, np.nan)
        c["obs_per_section"] = c["obs_flow"] / c["n_sections"].replace(0, np.nan)
        c["sim_per_section"] = c["sim_flow_sec"] / c["n_sections"].replace(0, np.nan)
        # 三口径的 Sim/Cap 与 Obs/Cap（(1) 断面级：分子分母同为 K 折 ⇒ 可比利用率）
        c["sim_cap"] = c["sim_flow_sec"] / c["cap_sec"].replace(0, np.nan)
        c["obs_cap"] = c["obs_flow"] / c["cap_sec"].replace(0, np.nan)
        # (3) 代表值口径（对 1:K 免疫）：把 obs 与 sim 都压到「每断面 1 份」
        c["sim_cap_rep"] = c["sim_flow_med"] / c["cap_sec"].replace(0, np.nan)
        c["obs_cap_rep"] = c["obs_flow"] / c["cap_sec"].replace(0, np.nan)
    c["residual_pp"] = 100.0 * (c["sim_cap"] - c["obs_cap"])
    c["residual_pp_rep"] = 100.0 * (c["sim_cap_rep"] - c["obs_cap_rep"])
    c["mapped_link_count"] = c["n_links"]
    c["mapped_length_m"] = c["len_edge_sum"]
    c["obs_share"] = c["obs_flow"] / c["obs_flow"].sum()
    return c


COLS = ["RoadName", "n_sections", "mapped_link_count", "n_edge_sec", "K_c",
        "mapped_length_m", "obs_flow", "obs_share",
        "sim_flow_med", "sim_flow_sec", "sim_flow_edge",
        "cap_sec", "cap_edge", "cap_per_pair", "obs_per_section", "sim_per_section",
        "sim_cap", "obs_cap", "residual_pp",
        "sim_cap_rep", "obs_cap_rep", "residual_pp_rep",
        "ratio_simobs", "ratio_simobs_med", "ratio_simobs_norm", "n_links_missing"]


def main() -> int:
    t0 = time.time()
    rec: dict = {"step": "7.9I-A/corridor-capacity-weighted-comparison",
                 "scale": SCALE, "cap_mul": CAPMUL, "norm_low": NORM_LOW}

    print("[1] 载入冻结件 …", flush=True)
    obs, cw, matched_set = load_frozen()
    print(f"    obs 断面 {obs['LinkID'].nunique()}  crosswalk 行 {len(cw)}"
          f"  匹配边 {len(matched_set)}", flush=True)

    print("[2] 载入两版 linkstats（全列）…", flush=True)
    edge = {v: read_edge_full(p) for v, p in FULL_LS.items()}
    for v, d in edge.items():
        print(f"    {v}: edges={len(d):,}", flush=True)

    print("[3] 断面级表 …", flush=True)
    secs = {v: section_table(v, obs, cw, edge[v]) for v in ("v1.0", "A-1")}
    for v, g in secs.items():
        print(f"    {v}: sections={len(g)}  Σobs={g['obs_8_9'].sum():,.0f}", flush=True)

    gates: dict = {}
    pooled = {}
    for v, g in secs.items():
        pooled[v] = {"median": float(g["sim_median_xS"].sum() / g["obs_8_9"].sum()),
                     "sum": float(g["sim_sum_xS"].sum() / g["obs_8_9"].sum())}
        ok_m = abs(pooled[v]["median"] - EXP["pooled_median"][v]) < 1e-6
        ok_s = abs(pooled[v]["sum"] - EXP["pooled_sum"][v]) < 5e-4
        gates[f"G-A3[{v}]_median"] = ok_m
        gates[f"G-A4[{v}]_sum"] = ok_s
        print(f"    {v}: pooled median {pooled[v]['median']:.7f} ({'OK' if ok_m else 'FAIL'})"
              f"  sum {pooled[v]['sum']:.4f} ({'OK' if ok_s else 'FAIL'})", flush=True)
    rec["pooled_reproduction"] = pooled

    print("[4] 走廊级聚合 …", flush=True)
    corr = {v: corridor_table(secs[v], cw, edge[v], CAPMUL[v]) for v in ("v1.0", "A-1")}
    for v, c in corr.items():
        print(f"    {v}: corridors={len(c)}  空 RoadName={int((c['RoadName'].astype(str).str.strip()=='').sum())}",
              flush=True)

    # ---------- 三条口径的网络级池化 ----------
    print("[5] 网络级池化（三口径）…", flush=True)
    netw = {}
    for v, c in corr.items():
        d = c[c["RoadName"].astype(str).str.strip() != ""].copy()
        sim_cap = float(d["sim_flow_sec"].sum() / d["cap_sec"].sum())
        obs_cap = float(d["obs_flow"].sum() / d["cap_sec"].sum())
        sim_cap_rep = float(d["sim_flow_med"].sum() / d["cap_sec"].sum())
        K = float(d["n_edge_sec"].sum() / d["n_sections"].sum())
        netw[v] = {
            "n_corridors": int(len(d)),
            "sum_obs": round(float(d["obs_flow"].sum()), 1),
            "sum_sim_sec": round(float(d["sim_flow_sec"].sum()), 1),
            "sum_sim_med": round(float(d["sim_flow_med"].sum()), 1),
            "sum_cap_sec": round(float(d["cap_sec"].sum()), 1),
            "K_pooled": round(K, 4),
            "sim_cap_sec": round(sim_cap, 6), "obs_cap_sec": round(obs_cap, 6),
            "residual_pp_sec": round(100 * (sim_cap - obs_cap), 4),
            "sim_cap_rep": round(sim_cap_rep, 6), "obs_cap_rep": round(obs_cap, 6),
            "residual_pp_rep": round(100 * (sim_cap_rep - obs_cap), 4),
            "median_residual_pp": round(float(d["residual_pp"].median()), 4),
            "share_corr_resid_pos": round(float((d["residual_pp"] > 0).mean()), 4),
            "median_ratio_simobs": round(float(d["ratio_simobs"].median()), 4),
            "median_ratio_simobs_norm": round(float(d["ratio_simobs_norm"].median()), 4),
        }
        print(f"    {v}: K={K:.3f}  ratio_simobs 中位 {netw[v]['median_ratio_simobs']:.3f}"
              f" → norm 中位 {netw[v]['median_ratio_simobs_norm']:.3f}", flush=True)
        print(f"        Sim/Cap(Σ) {sim_cap:.4f} vs Obs/Cap(Σ) {obs_cap:.4f}"
              f" ⇒ {netw[v]['residual_pp_sec']:+.2f} pp"
              f" ；代表值口径 {netw[v]['residual_pp_rep']:+.2f} pp", flush=True)
    rec["network_pooled"] = netw

    # ---------- ★真实缺载走廊（对 1:K 免疫） ----------
    print("[6] ★去尺度残差 → 真实缺载走廊 …", flush=True)
    short = {}
    for v, c in corr.items():
        d = c[(c["RoadName"].astype(str).str.strip() != "") & c["ratio_simobs_norm"].notna()].copy()
        s = d[d["ratio_simobs_norm"] < NORM_LOW].sort_values("obs_flow", ascending=False)
        short[v] = {
            "n_corridors": int(len(s)),
            "sum_obs": round(float(s["obs_flow"].sum()), 1),
            "obs_share": round(float(s["obs_flow"].sum() / d["obs_flow"].sum()), 4),
            "corridors": [{"RoadName": str(r.RoadName), "n_sections": int(r.n_sections),
                           "K_c": round(float(r.K_c), 3),
                           "ratio_simobs": round(float(r.ratio_simobs), 4),
                           "ratio_simobs_norm": round(float(r.ratio_simobs_norm), 4),
                           "obs_flow": round(float(r.obs_flow), 1)}
                          for r in s.itertuples()],
        }
        print(f"    [{v}] norm<{NORM_LOW}: {len(s)} 走廊，担 obs {100*short[v]['obs_share']:.1f}%", flush=True)
        for r in short[v]["corridors"][:6]:
            print(f"        {r['RoadName'][:44]:46s} sec={r['n_sections']:3d} K={r['K_c']:.2f}"
                  f" ratio={r['ratio_simobs']:.3f} norm={r['ratio_simobs_norm']:.3f}"
                  f" obs={r['obs_flow']:,.0f}", flush=True)
    rec["genuine_shortfall_corridors"] = short

    # ---------- 快速路 / 其他 ----------
    print("[7] 快速路 / 其他 …", flush=True)
    grp = {}
    for v, c in corr.items():
        d = c[c["RoadName"].astype(str).str.strip() != ""].copy()
        isexp = d["RoadName"].str.contains("EXPRESSWAY|HIGHWAY|TUNNEL|VIADUCT|FLYOVER", na=False)
        rows = []
        for lab, s in (("EXPRESSWAY", d[isexp]), ("OTHER", d[~isexp])):
            if not len(s):
                continue
            rows.append({"group": lab, "n_corridors": int(len(s)),
                         "sum_obs": round(float(s["obs_flow"].sum()), 1),
                         "K": round(float(s["n_edge_sec"].sum() / s["n_sections"].sum()), 3),
                         "ratio_simobs": round(float(s["sim_flow_sec"].sum() / s["obs_flow"].sum()), 4),
                         "ratio_simobs_norm": round(float(
                             (s["sim_flow_sec"].sum() / s["obs_flow"].sum())
                             / (s["n_edge_sec"].sum() / s["n_sections"].sum())), 4)})
        grp[v] = rows
        print(f"    [{v}] " + "; ".join(
            f"{r['group']}: n={r['n_corridors']} K={r['K']} ratio={r['ratio_simobs']:.3f}"
            f" norm={r['ratio_simobs_norm']:.3f}" for r in rows), flush=True)
    rec["expressway_vs_other"] = grp

    # ---------- 门 ----------
    gates["G-A1[scale]"] = abs(SCALE - 2.29897) < 1e-9
    gates["G-A1[f_cap]"] = abs(A.F_CAP - 0.434977) < 1e-9
    gates["G-A2[sections]"] = (int(secs["v1.0"]["lta_linkid"].nunique()) == EXP["n_sections"]
                               == int(secs["A-1"]["lta_linkid"].nunique()))
    gates["G-A2[cw_rows]"] = len(cw) == EXP["n_cw_rows"]
    gates["G-A2[matched_edges]"] = len(matched_set) == EXP["n_matched_edges"]

    tot_obs_sec = float(secs["v1.0"]["obs_8_9"].sum())
    tot_obs_cor = float(corr["v1.0"]["obs_flow"].sum())
    gates["G-A5[obs_conservation]"] = abs(tot_obs_sec - tot_obs_cor) < 1e-6
    gates["G-A5[no_empty_roadname]"] = int(
        (secs["v1.0"]["RoadName"].astype(str).str.strip() == "").sum()) == 0
    union = set(secs["v1.0"][["lta_linkid"]].merge(cw, on="lta_linkid", how="left")
                ["matsim_link_id"].dropna().astype(str))
    gates["G-A6[union_edges]"] = len(union) == EXP["n_matched_edges"]
    print(f"    obs 守恒 {tot_obs_sec:,.1f} vs {tot_obs_cor:,.1f}"
          f" ({'OK' if gates['G-A5[obs_conservation]'] else 'FAIL'})；边并集 {len(union)}", flush=True)

    fshare = {}
    for v, d in edge.items():
        fshare[v] = float(d.loc[d["LINK"].isin(matched_set), "HRS8-9avg"].sum()
                          / max(1e-9, float(d["HRS8-9avg"].sum())))
        gates[f"G-A7[{v}]"] = abs(fshare[v] - EXP["flow_share_matched"][v]) < 1e-4
        print(f"    {v}: 匹配边流量占比 {100*fshare[v]:.2f}%"
              f" ({'OK' if gates[f'G-A7[{v}]'] else 'FAIL'})", flush=True)
    rec["flow_share_matched"] = {v: round(x, 4) for v, x in fshare.items()}

    # ---------- G-N 负例（必须真改变可观测结果） ----------
    print("[8] 负例门 …", flush=True)
    neg = {}

    def sig(c: pd.DataFrame) -> tuple:
        """对「分组」敏感的可观测签名（池化比本身对重命名不变，故须含分布量）。"""
        d = c[c["RoadName"].astype(str).str.strip() != ""]
        return (round(float(d["sim_flow_sec"].sum() / d["cap_sec"].sum()), 10),
                round(float(d["obs_flow"].sum() / d["cap_sec"].sum()), 10),
                round(float(d["residual_pp"].median()), 8),
                int((d["residual_pp"] > 10.0).sum()))

    truth = sig(corr["v1.0"])

    rng = np.random.default_rng(20260929)
    g1 = secs["v1.0"].copy()
    g1["RoadName"] = rng.permutation(g1["RoadName"].values)
    neg["N1_permute_corridor"] = {"fired": sig(corridor_table(g1, cw, edge["v1.0"], CAPMUL["v1.0"])) != truth}

    g2 = secs["v1.0"].copy(); g2["cap_sum"] = 1.0
    e2 = edge["v1.0"].copy(); e2["CAPACITY"] = 1.0
    neg["N2_constant_capacity"] = {"fired": sig(corridor_table(g2, cw, e2, CAPMUL["v1.0"])) != truth}

    g3 = secs["v1.0"].copy()
    top = corr["v1.0"].sort_values("obs_flow", ascending=False).iloc[0]["RoadName"]
    m3 = g3["RoadName"] == top
    g3.loc[m3, ["sim_median", "sim_sum", "sim_median_xS", "sim_sum_xS"]] = 0.0
    c3 = corridor_table(g3, cw, edge["v1.0"], CAPMUL["v1.0"])
    r3 = float(c3.loc[c3["RoadName"] == top, "residual_pp"].iloc[0])
    r0 = float(corr["v1.0"].loc[corr["v1.0"]["RoadName"] == top, "residual_pp"].iloc[0])
    neg["N3_zero_corridor"] = {"fired": bool(abs(r3 - r0) > 1e-6), "corridor": str(top),
                               "resid_truth": round(r0, 6), "resid_neg": round(r3, 6)}

    neg["N4_swap_capmul"] = {"fired": sig(corridor_table(secs["v1.0"], cw, edge["v1.0"], CAPMUL["A-1"])) != truth}

    g5 = secs["v1.0"].copy()
    for c in ("sim_median", "sim_sum", "sim_median_xS", "sim_sum_xS"):
        g5[c] = 0.0
    neg["N5_zero_all_sim"] = {"fired": sig(corridor_table(g5, cw, edge["v1.0"], CAPMUL["v1.0"])) != truth}

    g6 = secs["v1.0"].copy(); g6["obs_8_9"] = g6["obs_7_8"]
    neg["N6_swap_obs_window"] = {"fired": sig(corridor_table(g6, cw, edge["v1.0"], CAPMUL["v1.0"])) != truth}

    rec["negatives"] = neg
    for k, v in neg.items():
        gates[f"G-N[{k}]"] = bool(v["fired"])
        print(f"    {k}: fired={v['fired']}", flush=True)

    # ---------- 写盘 ----------
    print("[9] 写盘 …", flush=True)
    for v, c in corr.items():
        c.sort_values("obs_flow", ascending=False)[COLS].to_csv(
            OUT / f"corridor_scale_{'v10' if v == 'v1.0' else 'A1'}.csv",
            index=False, encoding="utf-8-sig")
        secs[v].to_csv(OUT / f"section_scale_{'v10' if v == 'v1.0' else 'A1'}.csv",
                       index=False, encoding="utf-8-sig")

    hard = {k: bool(v) for k, v in gates.items()}
    rec["gates"] = hard
    rec["n_fail"] = int(sum(1 for v in hard.values() if not v))
    rec["verdict"] = ("CORRIDOR_SCALE_AUDIT_READY" if rec["n_fail"] == 0
                      else "CORRIDOR_SCALE_AUDIT_BLOCKED")
    rec["elapsed_s"] = round(time.time() - t0, 1)
    (OUT / "_corridor_audit_7_9ia.json").write_text(
        json.dumps(rec, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    (OUT / "corridor_scale_summary.json").write_text(
        json.dumps({"network_pooled": netw,
                    "genuine_shortfall_corridors": short,
                    "expressway_vs_other": grp,
                    "flow_share_matched": rec["flow_share_matched"],
                    "pooled_reproduction": pooled},
                   ensure_ascii=False, indent=2, default=str), encoding="utf-8")

    print(f"\n[verdict] {rec['verdict']}  fail={rec['n_fail']}  ({rec['elapsed_s']} s)")
    for k, v in hard.items():
        if not v:
            print(f"  !! FAIL {k}")
    return 0 if rec["n_fail"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
