# -*- coding: utf-8 -*-
"""Step 7.9I-A2 · KPE / ECP 实体定义核验（零仿真只读）

⛔ 零仿真、只读。不改 v1.0、不改任何冻结件、不重跑 MATSim。
判据与阈值一律以 `reports/corridor_scale_audit_7_9i/PREREG_7_9I_A2.md` 为准（运行前冻结）。

回答两个问题
--------------------------------------------------
  Q1  LTA 的 KPE 隧道 / ECP / KPE 断面**代表什么物理对象**？其观测值与该对象的
      MATSim 表征是否为**同一测量单元**？
  Q2  三条走廊的「真实缺载」在**不除以 K** 的口径下还剩多少？即 `norm` 是真实缺载
      还是「除以 K」造成的伪缺载？

判据（PREREG §2.4，固定优先级）
--------------------------------------------------
  U_UNIT_MISMATCH : vc_max = obs / cap_edge_max > 1.0        （观测单元 ≠ 仿真单元）
  S_SLIP_GEOM     : RoadCat == SLIP_ROAD 或全部匹配边 ∈ *_link
  C_CHAIN         : 匹配边为一整条连续有向链（n_comp==1 且 chain_break==0 且 n≥2）
  P_PARALLEL      : 非链且（n_comp>1 或 chain_break>0）
  N_PLAIN         : 其余
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

import audit_sampling_capacity_7_9a1 as A              # noqa: E402
import evaluate_calibration_7_4_2 as ev1               # noqa: E402
import evaluate_demand_response_7_6f_1 as E            # noqa: E402
from diagnose_gap_7_9h import read_edge_full           # noqa: E402
from audit_corridor_scale_7_9ia import (               # noqa: E402
    load_frozen, section_table, SCALE, OUT)
from audit_m1_accessibility_7_9ib import Graph, chain_stats   # noqa: E402

CACHE_NET = ROOT / "scripts" / "od" / "_cache_network_7_9c0.npz"
RADII = [50.0, 100.0, 150.0]
MAJOR = {"motorway", "motorway_link", "trunk", "trunk_link"}
OPP_R = 60.0
OPP_DEG = 30.0
CORRIDORS = ["KALLANG PAYA LEBAR EXPRESSWAY TUNNEL",
             "EAST COAST PARKWAY",
             "KALLANG PAYA LEBAR EXPRESSWAY"]
SHORT = {CORRIDORS[0]: "KPE_TUNNEL", CORRIDORS[1]: "ECP", CORRIDORS[2]: "KPE"}
LABELS = {"U_UNIT_MISMATCH", "S_SLIP_GEOM", "C_CHAIN", "P_PARALLEL", "N_PLAIN"}

# ★ 口径记法披露（运行后修正，非阈值改动）：
#   `matched_edges` 有两个不同但都正确的计数——
#     n_edge_sec    = Σ_sections n_edges(s)（逐断面求和；走廊表 `n_edge_sec`）
#     n_edge_dedup  = |∪_sections E_s|（去重；走廊表 `mapped_link_count`）
#   PREREG §1 该行给的是 **dedup** 值，而 G-A2-1 原写 `n_edge` 未区分口径 ⇒
#   现让门**同时断言两者**并携带实测值（阈值/判据未改）。
EXP = {
    CORRIDORS[0]: dict(obs=230267.5, n_sec=19, n_edge_sec=67, n_edge_dedup=67,
                       norm=0.117223, r_med=0.096581),
    CORRIDORS[1]: dict(obs=93818.0, n_sec=47, n_edge_sec=289, n_edge_dedup=283,
                       norm=0.131760),
    CORRIDORS[2]: dict(obs=15362.0, n_sec=3, n_edge_sec=16, n_edge_dedup=16,
                       norm=0.119084),
}


def lta_section_geometry(path: Path) -> pd.DataFrame:
    """LTA 断面几何。

    ⚠️ 坐标陷阱：`mx`/`my` 是**局部等距平面米**（lon×111320·cos(lat0), lat×111320，
    原点在 (0,0) ⇒ x≈1.15e7、y≈1.4e5），**与全网图的 SVY21 坐标不同源**。
    ⇒ `mx/my` 只能用于本函数内部（`bear`/`len_m`/`opposite_pairs` 的自洽比较），
    ⛔ **绝不能**与 `Graph.ex/ey` 或 `SEC_GEO_7_6C.mid_x/mid_y`（SVY21）做半径/距离运算。
    需要与网络做空间运算时：断面位置一律取 `SEC_GEO_7_6C` 的 `mid_x/mid_y`，
    本函数的 `bear`/`len_m`（与 CRS 无关）可照用。
    """
    with open(path, "r", encoding="utf-8-sig") as f:
        obj = json.load(f)
    tf = pd.DataFrame(obj["Value"] if isinstance(obj, dict) else obj)
    for c in ["StartLon", "StartLat", "EndLon", "EndLat"]:
        tf[c] = pd.to_numeric(tf[c], errors="coerce")
    g = (tf.groupby("LinkID", as_index=False)
           .agg(RoadName=("RoadName", "first"), RoadCat=("RoadCat", "first"),
                slon=("StartLon", "first"), slat=("StartLat", "first"),
                elon=("EndLon", "first"), elat=("EndLat", "first")))
    g["LinkID"] = g["LinkID"].astype(str).str.strip()
    lat0 = float(np.nanmean(g["slat"]))
    kx = 111320.0 * np.cos(np.radians(lat0)); ky = 111320.0
    x0 = g["slon"] * kx; x1 = g["elon"] * kx
    y0 = g["slat"] * ky; y1 = g["elat"] * ky
    g["len_m"] = np.hypot(x1 - x0, y1 - y0)
    g["bear"] = (np.degrees(np.arctan2(x1 - x0, y1 - y0)) + 360.0) % 360.0
    g["mx"] = 0.5 * (x0 + x1); g["my"] = 0.5 * (y0 + y1)
    return g


def opposite_pairs(sub: pd.DataFrame) -> pd.DataFrame:
    a = sub[["mx", "my"]].to_numpy()
    ids = sub["LinkID"].to_numpy(); br = sub["bear"].to_numpy()
    out = []
    for i in range(len(a)):
        d = np.hypot(a[:, 0] - a[i, 0], a[:, 1] - a[i, 1]); d[i] = 9e18
        j = int(np.argmin(d))
        dev = abs(((br[i] - br[j] + 180.0) % 360.0) - 180.0)   # 180 ⇒ 反向
        out.append((ids[i], ids[j], float(d[j]), bool(d[j] < OPP_R and (180.0 - dev) < OPP_DEG)))
    return pd.DataFrame(out, columns=["LinkID", "nn_id", "nn_dist_m", "is_opposite_pair"])


def main() -> int:
    t0 = time.time()
    rec: dict = {"step": "7.9I-A2/kpe-ecp-object-definition",
                 "radii_m": RADII, "opp_r_m": OPP_R, "opp_deg": OPP_DEG,
                 "scale": SCALE, "corridors": {}}
    gates: list = []

    print("[1] 载入冻结件 …", flush=True)
    obs, cw, _ = load_frozen()
    secs = section_table("v1.0", obs, cw, read_edge_full(A.V10_LS))
    secs["lta_linkid"] = secs["lta_linkid"].astype(str)
    geo_lta = lta_section_geometry(ev1.TRAFFIC)
    print(f"    sections={len(secs)}  crosswalk rows={len(cw)}  LTA links={len(geo_lta)}",
          flush=True)

    print("[2] 建全网图 …", flush=True)
    G = Graph(np.load(CACHE_NET, allow_pickle=True))
    print(f"    nodes={G.n_nodes:,}  edges={G.n_edges:,}  components={G.n_comp:,}", flush=True)

    edge1 = read_edge_full(A.V10_LS)
    cap_e = edge1.set_index("LINK")["CAPACITY"]
    flow_e = edge1.set_index("LINK")["HRS8-9avg"]
    id2i = {x: i for i, x in enumerate(G.ids)}
    hw_major = np.array([h in MAJOR for h in G.highway])
    ref_cap = (pd.read_csv(OUT / "section_scale_v10.csv", dtype={"lta_linkid": str})
                 .set_index("lta_linkid")["cap_eff_sum"])

    sec_of = {nm: sorted(secs.loc[secs["RoadName"] == nm, "lta_linkid"].tolist())
              for nm in CORRIDORS}
    cw_by = {nm: cw[cw["lta_linkid"].isin(sec_of[nm])] for nm in CORRIDORS}
    geo = pd.read_csv(E.SEC_GEO_7_6C, dtype={"lta_linkid": str}).set_index("lta_linkid")

    def radius_agg(mid_xy: np.ndarray) -> dict:
        out = {}
        for R in RADII:
            s = np.zeros(G.n_edges, bool)
            for mx, my in mid_xy:
                if np.isfinite(mx) and np.isfinite(my):
                    s |= ((G.ex - mx) ** 2 + (G.ey - my) ** 2) < R * R
            s &= hw_major
            fl = np.nan_to_num(flow_e.reindex(G.ids[s]).to_numpy(dtype=float), nan=0.0)
            out[R] = (int(s.sum()), float(fl.sum() * SCALE))
        return out

    def build(nmc: str) -> pd.DataFrame:
        sub = cw_by[nmc]
        rows = []
        for sid in sec_of[nmc]:
            srow = secs[secs["lta_linkid"] == sid].iloc[0]
            mm = sub[sub["lta_linkid"] == sid]
            m = [x for x in dict.fromkeys(mm["matsim_link_id"].tolist()) if x in id2i]
            caps = np.array([float(cap_e.get(x, np.nan)) for x in m], float)
            flows = np.array([float(flow_e.get(x, 0.0)) for x in m], float)
            idx = np.array([id2i[x] for x in m], np.int64)
            ncomp, nbreak = chain_stats(G.f[idx], G.t[idx], G.n_nodes) if len(m) else (0, 0)
            hw = {G.highway[i] for i in idx}
            gl = geo_lta[geo_lta["LinkID"] == sid]
            rows.append(dict(
                lta_linkid=sid, RoadName=srow["RoadName"], RoadCat=srow["RoadCat"],
                obs_8_9=float(srow["obs_8_9"]), n_edges=int(srow["n_edges"]),
                n_flow_gt0=int(srow["n_edge_flow_gt0"]),
                cap_eff_sum=float(srow["cap_eff_sum"]),
                cap_edge_mean=float(srow["cap_eff_sum"]) / max(int(srow["n_edges"]), 1),
                cap_edge_max=float(np.nanmax(caps)) if len(caps) else np.nan,
                sim_median_xS=float(srow["sim_median_xS"]),
                sim_sum_xS=float(srow["sim_sum_xS"]),
                matched_flow_max=float(np.nanmax(flows)) if len(flows) else np.nan,
                max_dist_m=float(mm["distance_m"].max()),
                tier="|".join(sorted(mm["selection_tier"].dropna().unique())),
                name_match=bool(mm["name_match"].any()),
                all_link=bool(len(hw) and all(h.endswith("_link") for h in hw)),
                highway_set=", ".join(sorted(hw)),
                n_comp=ncomp, chain_break=nbreak,
                len_m=float(gl["len_m"].iloc[0]) if len(gl) else np.nan,
                bear=float(gl["bear"].iloc[0]) if len(gl) else np.nan,
                mid_x=float(geo.loc[sid, "mid_x"]) if sid in geo.index else np.nan,
                mid_y=float(geo.loc[sid, "mid_y"]) if sid in geo.index else np.nan,
            ))
        d = pd.DataFrame(rows)
        d["vc_mean"] = d["obs_8_9"] / d["cap_edge_mean"]
        d["vc_max"] = d["obs_8_9"] / d["cap_edge_max"]
        d["r_med"] = d["sim_median_xS"] / d["obs_8_9"]
        d["r_sum"] = d["sim_sum_xS"] / d["obs_8_9"]
        d["is_chain"] = (d["n_comp"] == 1) & (d["chain_break"] == 0) & (d["n_edges"] >= 2)
        pr = opposite_pairs(geo_lta[geo_lta["LinkID"].isin(sec_of[nmc])])
        d = d.merge(pr, left_on="lta_linkid", right_on="LinkID", how="left")
        cls = []
        for r in d.itertuples():
            if np.isfinite(r.vc_max) and r.vc_max > 1.0:
                cls.append("U_UNIT_MISMATCH")
            elif r.RoadCat == "SLIP_ROAD" or r.all_link:
                cls.append("S_SLIP_GEOM")
            elif r.is_chain:
                cls.append("C_CHAIN")
            elif r.n_comp > 1 or r.chain_break > 0:
                cls.append("P_PARALLEL")
            else:
                cls.append("N_PLAIN")
        d["class"] = cls
        return d

    def summarize(nmc: str, d: pd.DataFrame) -> dict:
        obs_sum = float(d["obs_8_9"].sum())
        # 设施级去重口径（与 corridor_table.sim_flow_edge 同源）
        eids = [x for x in dict.fromkeys(cw_by[nmc]["matsim_link_id"].tolist()) if x in id2i]
        sim_edge = float(np.nansum(flow_e.reindex(eids).to_numpy(dtype=float)) * SCALE)
        sim_sec = float(d["sim_sum_xS"].sum())
        K_c = float(d["n_edges"].sum()) / len(d)
        rad = radius_agg(d[["mid_x", "mid_y"]].to_numpy())
        return dict(
            n_sections=len(d), obs_sum=obs_sum, K_c=round(K_c, 6),
            n_match_edges=int(d["n_edges"].sum()), n_match_edges_dedup=len(eids),
            sim_edge_xS=round(sim_edge, 1), sim_sec_xS=round(sim_sec, 1),
            r_med=float(d["sim_median_xS"].sum()) / obs_sum,
            r_edge=sim_edge / obs_sum, r_sec=sim_sec / obs_sum,
            r_norm=(sim_sec / obs_sum) / K_c,
            n_vc_max_gt1=int((d["vc_max"] > 1.0).sum()),
            n_vc_mean_gt1=int((d["vc_mean"] > 1.0).sum()),
            vc_mean_median=float(d["vc_mean"].median()), vc_max_max=float(d["vc_max"].max()),
            n_chain=int(d["is_chain"].sum()),
            n_parallel_comp=int((d["n_comp"] > 1).sum()),
            n_chain_break=int((d["chain_break"] > 0).sum()),
            n_slip=int((d["class"] == "S_SLIP_GEOM").sum()),
            opposite_pairs=int(d["is_opposite_pair"].fillna(False).sum()),
            class_share_by_obs=(d.groupby("class")["obs_8_9"].sum() / obs_sum).round(4).to_dict(),
            radius={int(k): {"n_edges": v[0], "flow_xS": round(v[1], 1),
                             "ratio": round(v[1] / obs_sum, 4)} for k, v in rad.items()},
            len_m_median=float(d["len_m"].median()),
            max_dist_median=float(d["max_dist_m"].median()),
            name_match_share=float(d["name_match"].mean()),
        )

    cards_all = []
    for nmc in CORRIDORS:
        d = build(nmc)
        cards_all.append(d)
        s = summarize(nmc, d)
        rec["corridors"][nmc] = s
        e = EXP[nmc]
        tg = SHORT[nmc]
        gates.append([f"G-A2-1[{tg}] obs/n_sec/n_edge_sec/n_edge_dedup",
                      abs(s["obs_sum"] - e["obs"]) < 1e-6 and s["n_sections"] == e["n_sec"]
                      and s["n_match_edges"] == e["n_edge_sec"]
                      and s["n_match_edges_dedup"] == e["n_edge_dedup"],
                      f"obs={s['obs_sum']:,.1f} n_sec={s['n_sections']} "
                      f"n_edge_sec={s['n_match_edges']} n_edge_dedup={s['n_match_edges_dedup']}"])
        gates.append([f"G-A2-2[{tg}] norm", abs(s["r_norm"] - e["norm"]) < 1e-6,
                      f"{s['r_norm']:.6f} vs {e['norm']}"])
        if "r_med" in e:
            gates.append([f"G-A2-3[{tg}] r_med", abs(s["r_med"] - e["r_med"]) < 1e-6,
                          f"{s['r_med']:.6f} vs {e['r_med']}"])
        gates.append([f"G-A2-5[{tg}] cap_eff_sum",
                      abs(float(d["cap_eff_sum"].sum()) - float(ref_cap.loc[sec_of[nmc]].sum())) < 1e-6,
                      "Σcap_eff 逐位一致"])
        gates.append([f"G-A2-7[{tg}] radius monotone",
                      s["radius"][50]["flow_xS"] <= s["radius"][100]["flow_xS"] <= s["radius"][150]["flow_xS"],
                      f"{s['radius'][50]['ratio']} ≤ {s['radius'][100]['ratio']} ≤ {s['radius'][150]['ratio']}"])
        gates.append([f"G-A2-6[{tg}] opposite-pair non-degenerate",
                      0 <= s["opposite_pairs"] < s["n_sections"],
                      f"{s['opposite_pairs']}/{s['n_sections']}"])
        print(f"  [{nmc[:30]}] obs={s['obs_sum']:,.0f} K={s['K_c']:.3f} "
              f"r_edge={s['r_edge']:.3f} r_norm={s['r_norm']:.4f} "
              f"vc_max>1: {s['n_vc_max_gt1']}/{s['n_sections']}", flush=True)

    cards = pd.concat(cards_all, ignore_index=True)

    # ---------------- 负例（非同构扰动） ----------------
    def sig(c: dict) -> tuple:
        return (tuple(round(c[n]["r_norm"], 8) for n in CORRIDORS)
                + tuple(round(c[n]["vc_mean_median"], 8) for n in CORRIDORS)
                + tuple(int(c[n]["n_chain"]) for n in CORRIDORS)
                + tuple(round(c[n]["radius"][100]["ratio"], 8) for n in CORRIDORS))

    base = sig(rec["corridors"])
    neg: dict = {}

    def variant(apply) -> dict:
        c = {}
        for nmc in CORRIDORS:
            d = build(nmc).copy()
            apply(nmc, d)
            d["vc_mean"] = d["obs_8_9"] / (d["cap_eff_sum"] / d["n_edges"])
            obs_sum = float(d["obs_8_9"].sum())
            K_c = float(d["n_edges"].sum()) / len(d)
            rad = radius_agg(d[["mid_x", "mid_y"]].to_numpy())
            c[nmc] = {"r_norm": (float(d["sim_sum_xS"].sum()) / obs_sum) / K_c,
                      "vc_mean_median": float(d["vc_mean"].median()),
                      "n_chain": int(((d["n_comp"] == 1) & (d["chain_break"] == 0)
                                      & (d["n_edges"] >= 2)).sum()),
                      "radius": {int(k): {"ratio": v[1] / obs_sum} for k, v in rad.items()}}
        return c

    rng = np.random.default_rng(20260929)
    c = variant(lambda nm, d: d.__setitem__("obs_8_9", rng.permutation(d["obs_8_9"].to_numpy())))
    neg["N1_shuffle_obs"] = {"fired": sig(c) != base}
    b1 = sig(c)
    c = variant(lambda nm, d: d.__setitem__("cap_eff_sum", 1.0 * d["n_edges"]))
    neg["N2_cap_uniform"] = {"fired": sig(c) != b1}
    b2 = sig(c)
    c = variant(lambda nm, d: d.__setitem__("mid_x", d["mid_x"] + 500.0))
    neg["N3_shift_section_mid"] = {"fired": sig(c) != b2}
    b3 = sig(c)
    r4 = np.random.default_rng(4242)
    c = variant(lambda nm, d: (d.__setitem__("n_comp", r4.integers(1, 6, size=len(d))),
                               d.__setitem__("chain_break", r4.integers(0, 4, size=len(d)))))
    neg["N4_permute_chain_structure"] = {"fired": sig(c) != b3}
    neg["N5_reverse_all_note"] = {"fired": False,
                                  "note": "整体反向不改变无向分量数与有向链断裂数（同构）⇒ 不设门，仅记录"}

    gates.append(["G-A2-4 分类全覆盖",
                  bool(cards["class"].notna().all() and set(cards["class"]) <= LABELS),
                  f"labels={sorted(set(cards['class']))}"])
    fired = [k for k, v in neg.items() if not k.endswith("_note") and v["fired"]]
    gates.append(["G-N 负例 4 个有效门全 fired", len(fired) == 4, f"fired={fired}"])

    rec["gates"] = [{"gate": g, "pass": bool(p), "measured": m} for g, p, m in gates]
    rec["negatives"] = neg
    rec["n_fail"] = int(sum(1 for _, p, _ in gates if not p))
    rec["verdict"] = ("KPE_ECP_OBJECT_AUDIT_READY" if rec["n_fail"] == 0
                      else "KPE_ECP_OBJECT_AUDIT_BLOCKED")
    rec["elapsed_s"] = round(time.time() - t0, 1)

    cards.to_csv(OUT / "kpe_ecp_entity_cards_7_9ia2.csv", index=False, encoding="utf-8-sig")
    for fn in ("kpe_ecp_object_summary_7_9ia2.json", "_kpe_ecp_audit_7_9ia2.json"):
        with open(OUT / fn, "w", encoding="utf-8") as f:
            json.dump(rec, f, ensure_ascii=False, indent=2)

    print("\n===== GATES =====", flush=True)
    for g, p, m in gates:
        print(f"  [{'PASS' if p else 'FAIL'}] {g:<52} {m}", flush=True)
    print(f"\nVERDICT={rec['verdict']}  n_fail={rec['n_fail']}  {rec['elapsed_s']}s", flush=True)
    return 0 if rec["n_fail"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
