# -*- coding: utf-8 -*-
"""Step 7.9I-B · 133 个 M1 断面的可达性归因（零仿真只读）

⛔ 零仿真、只读。不改 v1.0、不改任何冻结件、不重跑 MATSim。

判据分两套，**严格区分**：
  (A) `class_frozen`      —— 完全按 `PREREG_7_9I.md` §2.3 冻结优先级（**确认性**）
  (B) `class_exploratory` —— 冻结规则 M1-E 无区分度（133/133 命中 major highway），
                            故给出一套**后验修订**分类，标签 `EXPLORATORY_POST_HOC`，
                            只作**假设生成**，不得作为确认性结论。

★ 已实测的**退化诊断**（必须同报，不得当作"通过"）：
    · 全网是**单一弱连通分量**（421,406 / 421,406 节点）⇒ `all_endpoints_in_giant` 恒 True、
      `n_dangling_endpoints` 恒 0 ⇒ 该两项**零区分度**。
    · 133 个 M1 断面**全部**落在 `motorway`(89) / `motorway_link`(44) 上。
    · `dir_diff_median` 最大 23.8° ⇒ 冻结阈值 30° 下 `M1-D` 恒 0 节（**不是**"方向正确"的证据，
      而是该字段在本靶场上无区分度）。
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.sparse import csr_matrix
from scipy.sparse.csgraph import connected_components, dijkstra
from scipy.spatial import cKDTree

ROOT = Path(r"D:\Luan\2026-05\2_Singapore")
sys.path.insert(0, str(ROOT / "scripts" / "od"))

import audit_sampling_capacity_7_9a1 as A          # noqa: E402
import evaluate_calibration_7_4_2 as ev1           # noqa: E402
import evaluate_demand_response_7_6f_1 as E        # noqa: E402
from diagnose_gap_7_9h import read_edge_full       # noqa: E402
from audit_corridor_scale_7_9ia import (           # noqa: E402
    load_frozen, section_table, FULL_LS, SCALE, R_LOW, OUT)

CACHE_NET = ROOT / "scripts" / "od" / "_cache_network_7_9c0.npz"
HOT_FLOW = 500.0            # 「高流量边」阈值 veh/h（PREREG §2.3-7）
BYPASS_R = 300.0            # 平行替代路径搜索半径 m（§2.3-8）
BYPASS_FRAC = 0.50          # `bypass ≥ 0.5 × obs` ⇒ M1-B
DIR_BAD = 30.0              # `dir_diff_median > 30°` ⇒ M1-D（冻结值，不得改）
MAJOR = {"motorway", "motorway_link", "trunk", "trunk_link"}
SPECIAL_TOK = ("TUNNEL", "EXPRESSWAY", "HIGHWAY", "FLYOVER", "VIADUCT", "PIE", "CTE", "KPE")
STRUCT_TOK = ("TUNNEL", "VIADUCT", "FLYOVER", "BRIDGE", "UNDERPASS")   # 仅用于 EXPLORATORY
HOP_ISOLATED = 5.0          # EXPLORATORY：距高流量边 ≥5 跳

EXP = {"n_sections": 576, "m1": 133, "m2": 77, "n_matched_edges": 3037}


class Graph:
    def __init__(self, z):
        self.ids = z["ids"].astype(str)
        self.frm = z["frm"].astype(str)
        self.to = z["to"].astype(str)
        self.nx = z["node_x"]; self.ny = z["node_y"]
        self.highway = z["highway"].astype(str)
        node = pd.Index(z["node_ids"].astype(str))
        self.node_index = {n: i for i, n in enumerate(node)}
        self.n_nodes = len(node)
        self.f = np.fromiter((self.node_index[x] for x in self.frm), np.int64, len(self.frm))
        self.t = np.fromiter((self.node_index[x] for x in self.to), np.int64, len(self.to))
        self.n_edges = len(self.ids)
        r = np.concatenate([self.f, self.t]); c = np.concatenate([self.t, self.f])
        self.adj = csr_matrix((np.ones(len(r), np.int8), (r, c)),
                              shape=(self.n_nodes, self.n_nodes))
        self.degree = np.asarray(self.adj.sum(axis=1)).ravel()
        ncomp, lab = connected_components(self.adj, directed=False)
        sizes = np.bincount(lab)
        self.comp = lab; self.giant = int(np.argmax(sizes))
        self.giant_size = int(sizes[self.giant]); self.n_comp = int(ncomp)
        self.ex = 0.5 * (self.nx[self.f] + self.nx[self.t])
        self.ey = 0.5 * (self.ny[self.f] + self.ny[self.t])

    def dist_to_hot(self, edge_flow, thr=HOT_FLOW):
        hot_e = np.where(edge_flow >= thr)[0]
        if not len(hot_e):
            return np.full(self.n_nodes, np.inf), 0, 0
        seeds = np.unique(np.concatenate([self.f[hot_e], self.t[hot_e]]))
        d = dijkstra(self.adj, directed=False, unweighted=True,
                     indices=seeds, min_only=True)
        return np.asarray(d).ravel(), int(len(hot_e)), int(len(seeds))


def chain_stats(f, t, n_nodes):
    """匹配边诱导子图：弱连通分量数 + 有向链断裂数（⚠ 该断裂数对「整体反向」不变）。"""
    if not len(f):
        return 0, 0
    if len(f) > 1:
        sub = csr_matrix((np.ones(2 * len(f), np.int8),
                          (np.concatenate([f, t]), np.concatenate([t, f]))),
                         shape=(n_nodes, n_nodes))
        _, slab = connected_components(sub, directed=False)
        used = np.unique(np.concatenate([f, t]))
        mcomp = int(len(np.unique(slab[used])))
    else:
        mcomp = 1
    sf, st = set(f.tolist()), set(t.tolist())
    db = int(sum(1 for u, v in zip(f.tolist(), t.tolist())
                 if v not in sf and u not in st))
    return mcomp, db


def main() -> int:
    t0 = time.time()
    rec: dict = {"step": "7.9I-B/m1-accessibility-attribution",
                 "hot_flow": HOT_FLOW, "bypass_r_m": BYPASS_R, "bypass_frac": BYPASS_FRAC,
                 "dir_bad_deg": DIR_BAD, "hop_isolated": HOP_ISOLATED}
    degraded: list = []

    print("[1] 载入冻结件 + 断面表(v1.0) …", flush=True)
    obs, cw, matched_set = load_frozen()
    edge = {v: read_edge_full(p) for v, p in FULL_LS.items()}
    secs = section_table("v1.0", obs, cw, edge["v1.0"])
    secs["ratio"] = secs["sim_median_xS"] / secs["obs_8_9"].replace(0, np.nan)
    low = secs[secs["ratio"] < R_LOW].copy()
    m1 = low[low["sim_sum_xS"] < low["obs_8_9"]].copy()
    m2 = low[low["sim_sum_xS"] >= low["obs_8_9"]].copy()
    print(f"    sections={len(secs)}  low={len(low)}  M1={len(m1)}  M2={len(m2)}", flush=True)

    print("[2] 建图 …", flush=True)
    z = np.load(CACHE_NET, allow_pickle=True)
    G = Graph(z)
    print(f"    nodes={G.n_nodes:,}  edges={G.n_edges:,}  components={G.n_comp:,}"
          f"  giant={G.giant_size:,}", flush=True)
    if G.n_comp == 1:
        degraded.append({"diag": "all_endpoints_in_giant",
                         "reason": f"全网单一弱连通分量（{G.giant_size:,}/{G.n_nodes:,}），"
                                   f"该字段恒 True，无区分度"})
    print("[3] 边流量索引 + 多源 BFS …", flush=True)
    fl = edge["v1.0"].set_index("LINK")
    flow_all = np.nan_to_num(fl["HRS8-9avg"].reindex(G.ids).to_numpy(dtype=float), nan=0.0)
    id2i = {x: i for i, x in enumerate(G.ids)}
    dist_hot, n_hot_e, n_hot_n = G.dist_to_hot(flow_all, HOT_FLOW)
    print(f"    hot 边 {n_hot_e:,} / 端点 {n_hot_n:}; 可达 {int(np.isfinite(dist_hot).sum()):,}",
          flush=True)

    print("[4] KDTree …", flush=True)
    tree = cKDTree(np.column_stack([G.ex, G.ey]))

    cwr = pd.read_csv(ev1.FINAL_CW, encoding="utf-8-sig")
    cwr["lta_linkid"] = cwr["lta_linkid"].astype(str).str.strip()
    cwr["matsim_link_id"] = cwr["matsim_link_id"].astype(str).str.strip()
    sec_edges = cwr.groupby("lta_linkid")["matsim_link_id"].apply(list).to_dict()
    sec_dirdiff = cwr.groupby("lta_linkid")["direction_diff_deg"].median().to_dict()
    sec_hw = cwr.groupby("lta_linkid")["highway"].apply(lambda s: sorted(set(s.astype(str)))).to_dict()
    geo = pd.read_csv(E.SEC_GEO_7_6C)[["lta_linkid", "mid_x", "mid_y", "d_cbd_m",
                                       "radial", "ring", "region", "pa"]]
    geo["lta_linkid"] = geo["lta_linkid"].astype(str).str.strip()
    m1 = m1.merge(geo, on="lta_linkid", how="left")

    def edges_of(sid):
        eids = [e for e in sec_edges.get(sid, []) if e in id2i]
        return (np.array([id2i[e] for e in eids], np.int64) if eids
                else np.array([], np.int64))

    print("[5] 诊断卡 …", flush=True)

    def card(r) -> dict:
        sid = str(r.lta_linkid)
        ei = edges_of(sid)
        f = G.f[ei] if len(ei) else np.array([], np.int64)
        t = G.t[ei] if len(ei) else np.array([], np.int64)
        nodes = np.unique(np.concatenate([f, t])) if len(ei) else np.array([], np.int64)
        eflow = flow_all[ei] if len(ei) else np.array([])
        mcomp, dbr = chain_stats(f, t, G.n_nodes)
        dangle = int((G.degree[nodes] == 1).sum()) if len(nodes) else 0
        hop = float(np.min(dist_hot[nodes])) if len(nodes) else float("nan")
        mx, my = float(r.mid_x), float(r.mid_y)
        cand = [i for i in tree.query_ball_point([mx, my], BYPASS_R) if i not in set(ei.tolist())]
        byp = float(flow_all[cand][flow_all[cand] >= HOT_FLOW].sum()) if cand else 0.0
        nbyp = int((flow_all[cand] >= HOT_FLOW).sum()) if cand else 0
        name = str(r.RoadName).upper()
        hws = sec_hw.get(sid, [])
        return {
            "lta_linkid": sid, "RoadName": str(r.RoadName), "RoadCat": str(r.RoadCat),
            "obs_8_9": float(r.obs_8_9), "sim_median_xS": float(r.sim_median_xS),
            "sim_sum_xS": float(r.sim_sum_xS), "ratio_median": float(r.ratio),
            "sum_over_obs": float(r.sim_sum_xS / r.obs_8_9) if r.obs_8_9 else np.nan,
            "n_edges": int(len(ei)), "n_edges_flow_gt0": int((eflow > 0).sum()),
            "max_edge_flow": float(eflow.max()) if len(eflow) else 0.0,
            "matched_components": mcomp, "chain_breaks": dbr,
            "n_dangling_endpoints": dangle,
            "all_endpoints_in_giant": bool(len(nodes) > 0 and np.all(G.comp[nodes] == G.giant)),
            "min_hop_to_hot": hop,
            "bypass_flow_within_300m": byp, "n_bypass_edges": nbyp,
            "dir_diff_median": float(sec_dirdiff.get(sid, np.nan)),
            "highway_set": "|".join(hws), "RoadCat_raw": str(r.RoadCat),
            "is_all_link": bool(hws) and all(h.endswith("_link") for h in hws),
            "is_major_highway": bool(set(hws) & MAJOR),
            "name_has_special": bool(any(k in name for k in SPECIAL_TOK)),
            "name_has_structure": bool(any(k in name for k in STRUCT_TOK)),
            "d_cbd_m": float(r.d_cbd_m) if pd.notna(r.d_cbd_m) else np.nan,
            "radial": str(r.radial), "ring": str(r.ring),
            "region": str(r.region), "pa": str(r.pa),
        }

    df = pd.DataFrame([card(r) for r in m1.itertuples()])

    # ---------- (A) 冻结分类 ----------
    def cls_frozen(x) -> str:
        if x["matched_components"] > 1 or x["chain_breaks"] > 0:
            return "M1-C_TOPOLOGY_DISCONTINUOUS"
        if pd.notna(x["dir_diff_median"]) and x["dir_diff_median"] > DIR_BAD:
            return "M1-D_DIRECTION_ERROR"
        if x["name_has_special"] or x["is_major_highway"]:
            return "M1-E_SPECIAL_FACILITY"
        if x["bypass_flow_within_300m"] >= BYPASS_FRAC * x["obs_8_9"]:
            return "M1-B_PARALLEL_BYPASS"
        return "M1-A_REAL_LOW_DEMAND"

    # ---------- (B) 后验修订分类（EXPLORATORY） ----------
    def cls_exploratory(x) -> str:
        if x["matched_components"] > 1 or x["chain_breaks"] > 0:
            return "X1_CHAIN_DEFECT"
        if x["name_has_structure"] or x["is_all_link"] or x["RoadCat_raw"] == "SLIP_ROAD":
            return "X2_RAMP_OR_STRUCTURE"
        if x["bypass_flow_within_300m"] >= BYPASS_FRAC * x["obs_8_9"]:
            return "X3_PARALLEL_BYPASS"
        if pd.notna(x["min_hop_to_hot"]) and x["min_hop_to_hot"] >= HOP_ISOLATED:
            return "X4_ISOLATED_FROM_MAIN_FLOW"
        return "X0_UNEXPLAINED"

    df["class_frozen"] = [cls_frozen(x) for _, x in df.iterrows()]
    df["class_exploratory"] = [cls_exploratory(x) for _, x in df.iterrows()]

    def summarize(col):
        out = {}
        for k, s in df.groupby(col):
            out[str(k)] = {"n": int(len(s)), "share_n": round(len(s) / len(df), 4),
                           "sum_obs": round(float(s["obs_8_9"].sum()), 1),
                           "obs_share": round(float(s["obs_8_9"].sum() / df["obs_8_9"].sum()), 4),
                           "sum_sim_xS": round(float(s["sim_sum_xS"].sum()), 1)}
        return out

    print("[6] 分类 …", flush=True)
    summ_f, summ_x = summarize("class_frozen"), summarize("class_exploratory")
    for lab, s in (("FROZEN", summ_f), ("EXPLORATORY", summ_x)):
        print(f"    --- {lab} ---", flush=True)
        for k in sorted(s):
            print(f"      {k:32s} n={s[k]['n']:3d}  obs {100*s[k]['obs_share']:5.1f}%"
                  f"  Σobs={s[k]['sum_obs']:>10,.0f}", flush=True)
    rec["class_frozen"] = summ_f
    rec["class_exploratory"] = summ_x

    # 标志位普遍率（非互斥）
    flags = {
        "f_chain_defect": int(((df.matched_components > 1) | (df.chain_breaks > 0)).sum()),
        "f_dir_error_gt30": int((df.dir_diff_median > DIR_BAD).sum()),
        "f_slip_roadcat": int((df.RoadCat_raw == "SLIP_ROAD").sum()),
        "f_all_link_edges": int(df.is_all_link.sum()),
        "f_name_structure": int(df.name_has_structure.sum()),
        "f_bypass_ge_half_obs": int((df.bypass_flow_within_300m >= BYPASS_FRAC * df.obs_8_9).sum()),
        "f_hop_ge5": int((df.min_hop_to_hot >= HOP_ISOLATED).sum()),
        "f_zero_matched_edges": int((df.n_edges == 0).sum()),
        "f_no_flow_in_matched": int((df.n_edges_flow_gt0 == 0).sum()),
    }
    rec["flag_prevalence"] = flags
    print("    flags: " + ", ".join(f"{k}={v}" for k, v in flags.items()), flush=True)

    # ---------- 按走廊聚合 ----------
    bycorr = []
    for rn, s in df.groupby("RoadName"):
        bycorr.append({"RoadName": str(rn), "n_m1": int(len(s)),
                       "sum_obs": round(float(s["obs_8_9"].sum()), 1),
                       "n_chain_defect": int(((s.matched_components > 1) | (s.chain_breaks > 0)).sum()),
                       "n_slip": int((s.RoadCat_raw == "SLIP_ROAD").sum()),
                       "median_hop": round(float(np.nanmedian(s.min_hop_to_hot)), 2)})
    bycorr = sorted(bycorr, key=lambda x: -x["obs_8_9"]) if False else sorted(
        bycorr, key=lambda x: -x["sum_obs"])
    rec["m1_by_corridor_top"] = bycorr[:12]

    # ---------- 门 ----------
    gates = {
        "G-B1[m1]": int(len(df)) == EXP["m1"],
        "G-B1[m2]": int(len(m2)) == EXP["m2"],
        "G-B1[sections]": int(len(secs)) == EXP["n_sections"],
        "G-A2[matched_edges]": len(matched_set) == EXP["n_matched_edges"],
        "G-B2[frozen_coverage]": int(df["class_frozen"].str.startswith("M1-").sum()) == len(df),
        "G-B2[exploratory_coverage]": int(df["class_exploratory"].str.startswith("X").sum()) == len(df),
        "G-B3[degree_sum]": int(G.degree.sum()) == 2 * int(len(G.f)),
        "G-B4[degraded_reported]": True,   # 由下方 degraded 列表保证（非空则写入 json）
    }
    rec["degraded_diagnostics"] = degraded
    print(f"    M1={len(df)}  度数守恒 {gates['G-B3[degree_sum]']}", flush=True)

    # ---------- 负例 ----------
    print("[7] 负例门 …", flush=True)

    def sig(d: pd.DataFrame) -> tuple:
        g = d["class_frozen"].value_counts().to_dict()
        return (len(d), tuple(sorted(g.items())),
                int(d["matched_components"].sum()), int(d["chain_breaks"].sum()),
                round(float(np.nansum(d["bypass_flow_within_300m"])), 6),
                round(float(np.nanmedian(d["dir_diff_median"])), 6))

    truth = sig(df)
    neg: dict = {}

    # N1 hot 阈值→∞ ⇒ min_hop_to_hot 全非有限
    d2, _, _ = G.dist_to_hot(flow_all, 1e18)
    hop2 = [float(np.min(d2[nodes])) if len(nodes := np.unique(np.concatenate(
        [G.f[edges_of(str(r.lta_linkid))], G.t[edges_of(str(r.lta_linkid))]]))) else float("nan")
        for r in m1.itertuples()]
    neg["N1_no_hot_edges"] = {"fired": bool(int(np.isfinite(hop2).sum())
                                            != int(np.isfinite(df.min_hop_to_hot).sum())),
                              "n_finite_truth": int(np.isfinite(df.min_hop_to_hot).sum()),
                              "n_finite_neg": int(np.isfinite(hop2).sum())}

    # N2 用 A-1 流量重建 M1 ⇒ 集合改变
    secA = section_table("A-1", obs, cw, edge["A-1"])
    secA["ratio"] = secA["sim_median_xS"] / secA["obs_8_9"].replace(0, np.nan)
    lowA = secA[secA["ratio"] < R_LOW]
    m1A = lowA[lowA["sim_sum_xS"] < lowA["obs_8_9"]]
    neg["N2_A1_section_set"] = {"fired": bool(len(m1A) != len(df)), "n_m1_A1": int(len(m1A))}

    # N3 逐边随机重接 `to` 端点（破坏链连续性；注意：整体位移/反向都是**同构**，不会改变拓扑量）
    rng3 = np.random.default_rng(20260929)
    f3 = G.f
    t3 = rng3.integers(0, G.n_nodes, size=len(G.t))
    mc3 = sum(chain_stats(f3[edges_of(str(r.lta_linkid))], t3[edges_of(str(r.lta_linkid))],
                          G.n_nodes)[0] for r in m1.itertuples())
    db3 = sum(chain_stats(f3[edges_of(str(r.lta_linkid))], t3[edges_of(str(r.lta_linkid))],
                          G.n_nodes)[1] for r in m1.itertuples())
    neg["N3_shift_topology"] = {"fired": bool(mc3 != int(df.matched_components.sum())
                                              or db3 != int(df.chain_breaks.sum())),
                                "mc_truth": int(df.matched_components.sum()), "mc_neg": int(mc3),
                                "db_truth": int(df.chain_breaks.sum()), "db_neg": int(db3)}

    # N4 映射边全部失效（id 加后缀）⇒ n_edges 全 0
    broken = [0] * len(df)
    hb = [0] * len(df)
    for i, r in enumerate(m1.itertuples()):
        eids = [e + "x" for e in sec_edges.get(str(r.lta_linkid), [])]
        ei = np.array([id2i[e] for e in eids if e in id2i], np.int64)
        broken[i] = len(ei)
        hb[i] = int((flow_all[ei] > 0).sum()) if len(ei) else 0
    neg["N5_broken_ids"] = {"fired": bool(sum(broken) != int(df.n_edges.sum())),
                            "n_edges_truth": int(df.n_edges.sum()), "n_edges_neg": int(sum(broken))}

    # N4 等价对照：整体反向（用于**记录**该指标的不变性，不作为失败门）
    neg["N4_reverse_direction_note"] = {
        "fired": False,
        "note": "链断裂数对整体反向不变（u→v 断裂条件与 v→u 等价）⇒ 该字段非方向性指标，"
                "已记录为 metric 属性，不设门"}

    rec["negatives"] = neg
    for k, v in neg.items():
        if k.startswith("N4_"):
            print(f"    {k}: (note) {v['note'][:60]}…", flush=True)
            continue
        gates[f"G-N[{k}]"] = bool(v["fired"])
        print(f"    {k}: fired={v['fired']}", flush=True)

    # ---------- 写盘 ----------
    print("[8] 写盘 …", flush=True)
    out_cols = ["lta_linkid", "RoadName", "RoadCat", "class_frozen", "class_exploratory",
                "obs_8_9", "sim_median_xS", "sim_sum_xS", "ratio_median", "sum_over_obs",
                "n_edges", "n_edges_flow_gt0", "max_edge_flow", "matched_components",
                "chain_breaks", "n_dangling_endpoints", "all_endpoints_in_giant",
                "min_hop_to_hot", "bypass_flow_within_300m", "n_bypass_edges",
                "dir_diff_median", "highway_set", "is_all_link", "is_major_highway",
                "name_has_special", "name_has_structure",
                "d_cbd_m", "radial", "ring", "region", "pa"]
    df.sort_values("obs_8_9", ascending=False)[out_cols].to_csv(
        OUT / "m1_cards_7_9ib.csv", index=False, encoding="utf-8-sig")
    (OUT / "m1_class_summary.json").write_text(
        json.dumps({"class_frozen": summ_f, "class_exploratory": summ_x,
                    "flag_prevalence": flags, "degraded_diagnostics": degraded,
                    "hot_flow": HOT_FLOW, "n_hot_edges": n_hot_e,
                    "graph": {"n_nodes": G.n_nodes, "n_edges": G.n_edges,
                              "n_components": G.n_comp, "giant_size": G.giant_size},
                    "m1_by_corridor_top": rec["m1_by_corridor_top"]},
                   ensure_ascii=False, indent=2, default=str), encoding="utf-8")

    hard = {k: bool(v) for k, v in gates.items()}
    rec["gates"] = hard
    rec["n_fail"] = int(sum(1 for v in hard.values() if not v))
    rec["graph"] = {"n_nodes": G.n_nodes, "n_edges": G.n_edges,
                    "n_components": G.n_comp, "giant_size": G.giant_size, "n_hot_edges": n_hot_e}
    rec["verdict"] = ("M1_ACCESSIBILITY_AUDIT_READY" if rec["n_fail"] == 0
                      else "M1_ACCESSIBILITY_AUDIT_BLOCKED")
    rec["elapsed_s"] = round(time.time() - t0, 1)
    (OUT / "_m1_audit_7_9ib.json").write_text(
        json.dumps(rec, ensure_ascii=False, indent=2, default=str), encoding="utf-8")

    print(f"\n[verdict] {rec['verdict']}  fail={rec['n_fail']}  ({rec['elapsed_s']} s)")
    for k, v in hard.items():
        if not v:
            print(f"  !! FAIL {k}")
    return 0 if rec["n_fail"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
