# -*- coding: utf-8 -*-
"""Step 7.9I-B(b) · 38 个零流量断面的平行边记账（零仿真只读）

⛔ 零仿真、只读。不改 v1.0、不改任何冻结件、不重跑 MATSim。
判据 / 阈值以 `reports/corridor_scale_audit_7_9i/PREREG_7_9I_Bb.md` 为准（运行前冻结）。

问题不是「这条边为什么没车」，而是：
    LTA 所认为的这个交通对象，MATSim 实际把流量放到了哪个平行对象上？
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
from audit_m1_accessibility_7_9ib import Graph          # noqa: E402
from audit_kpe_ecp_object_7_9ia2 import lta_section_geometry   # noqa: E402

CACHE_NET = ROOT / "scripts" / "od" / "_cache_network_7_9c0.npz"
MAJOR = {"motorway", "motorway_link", "trunk", "trunk_link"}
DIR_OK = 30.0
RADII = [100.0, 200.0]
EXP_N, EXP_OBS = 38, 62050.5


def circ_diff(a, b):
    return abs(((a - b + 180.0) % 360.0) - 180.0)


def main() -> int:
    t0 = time.time()
    rec: dict = {"step": "7.9I-Bb/zero-flow-parallel-ledger", "radii_m": RADII,
                 "dir_ok_deg": DIR_OK, "scale": SCALE}
    gates: list = []

    print("[1] 载入冻结件 …", flush=True)
    obs, cw, _ = load_frozen()
    edge1 = read_edge_full(A.V10_LS)
    secs = section_table("v1.0", obs, cw, edge1)
    secs["lta_linkid"] = secs["lta_linkid"].astype(str)
    m1 = pd.read_csv(OUT / "m1_cards_7_9ib.csv", dtype={"lta_linkid": str})
    tgt = m1[m1["n_edges_flow_gt0"] == 0].copy()
    tgt["lta_linkid"] = tgt["lta_linkid"].astype(str)
    print(f"    target = {len(tgt)}  Σobs = {tgt['obs_8_9'].sum():,.1f}", flush=True)

    print("[2] 建全网图 …", flush=True)
    G = Graph(np.load(CACHE_NET, allow_pickle=True))
    flow = np.nan_to_num(edge1.set_index("LINK")["HRS8-9avg"].reindex(G.ids)
                         .to_numpy(dtype=float), nan=0.0)
    cap = np.nan_to_num(edge1.set_index("LINK")["CAPACITY"].reindex(G.ids)
                        .to_numpy(dtype=float), nan=0.0)
    id2i = {x: i for i, x in enumerate(G.ids)}
    bear_e = (np.degrees(np.arctan2(G.nx[G.t] - G.nx[G.f],
                                    G.ny[G.t] - G.ny[G.f])) + 360.0) % 360.0
    is_major = np.array([h in MAJOR for h in G.highway])
    gl = lta_section_geometry(ev1.TRAFFIC).set_index("LinkID")
    geo = pd.read_csv(E.SEC_GEO_7_6C, dtype={"lta_linkid": str}).set_index("lta_linkid")
    print(f"    nodes={G.n_nodes:,} edges={G.n_edges:,}", flush=True)

    # 构造性断言：目标断面匹配边流量全为 0
    zero_ok = True
    for sid in tgt["lta_linkid"].tolist():
        e = [id2i[x] for x in cw.loc[cw["lta_linkid"] == sid, "matsim_link_id"].tolist()
             if x in id2i]
        if len(e) and float(np.sum(flow[e])) != 0.0:
            zero_ok = False
    gates.append(["G-B3 构造性：匹配边流量全为 0", zero_ok,
                  f"复核 {len(tgt)} 断面，Σflow(matched) 全 0"])

    def ledger(sid: str, shift_m: float = 0.0, drop_dir: bool = False) -> dict:
        srow = secs[secs["lta_linkid"] == sid].iloc[0]
        obs_v = float(srow["obs_8_9"])
        mid = [float(geo.loc[sid, "mid_x"]) + shift_m, float(geo.loc[sid, "mid_y"])]
        bs = float(gl.loc[sid, "bear"]) if sid in gl.index else np.nan
        mset = {id2i[x] for x in cw.loc[cw["lta_linkid"] == sid, "matsim_link_id"].tolist()
                if x in id2i}
        out = dict(lta_linkid=sid, RoadName=srow["RoadName"], RoadCat=srow["RoadCat"],
                   obs_8_9=obs_v, n_matched=len(mset),
                   matched_flow_xS=float(sum(flow[i] for i in mset)) * SCALE)
        for R in RADII:
            near = np.where(((G.ex - mid[0]) ** 2 + (G.ey - mid[1]) ** 2 < R * R)
                            & is_major & (flow > 0) & (~np.isin(np.arange(G.n_edges),
                                                                list(mset))))[0]
            if np.isfinite(bs) and not drop_dir:
                same = np.array([i for i in near if circ_diff(bear_e[i], bs) < DIR_OK], np.int64)
                opp = np.array([i for i in near
                                if circ_diff(bear_e[i], (bs + 180.0) % 360.0) < DIR_OK], np.int64)
            else:
                same = np.array(near, np.int64); opp = np.array([], np.int64)
            ss = float(np.sum(flow[same])) * SCALE if len(same) else 0.0
            so = float(np.sum(flow[opp])) * SCALE if len(opp) else 0.0
            out[f"n_par_same_{int(R)}"] = int(len(same))
            out[f"n_par_opp_{int(R)}"] = int(len(opp))
            out[f"par_sum_same_xS_{int(R)}"] = ss
            out[f"par_sum_opp_xS_{int(R)}"] = so
            if R == RADII[0]:
                smax = float(np.max(flow[same])) * SCALE if len(same) else 0.0
                out["par_max_same_xS"] = smax
                out["r_par_sum_same"] = ss / obs_v
                out["r_par_max_same"] = smax / obs_v
                out["r_par_sum_opp"] = so / obs_v
                top = sorted(same.tolist(), key=lambda i: -flow[i])[:3]
                for k, i in enumerate(top, 1):
                    dd = float(np.hypot(G.ex[i] - mid[0], G.ey[i] - mid[1]))
                    out[f"par_top{k}"] = f"{G.ids[i]}|f={flow[i]:.0f}|d={dd:.0f}m|{G.highway[i]}"
                for k in range(len(top) + 1, 4):
                    out[f"par_top{k}"] = ""
        return out

    d = pd.DataFrame([ledger(s) for s in tgt["lta_linkid"].tolist()])
    d["class_bb"] = np.select(
        [d["par_sum_same_xS_100"] >= 0.5 * d["obs_8_9"],
         d["par_sum_opp_xS_100"] >= 0.5 * d["obs_8_9"]],
        ["B1_SAME_DIR_PARALLEL", "B2_OPPOSITE_ONLY"], "B3_NO_PARALLEL_FLOW")
    obs_sum = float(d["obs_8_9"].sum())

    gates.append(["G-B1 目标集 = 38", len(tgt) == EXP_N, f"n={len(tgt)}"])
    gates.append(["G-B2 Σobs 复现", abs(obs_sum - EXP_OBS) < 1e-6, f"{obs_sum:,.1f}"])
    gates.append(["G-B4 分类全覆盖",
                  bool(d["class_bb"].notna().all()
                       and set(d["class_bb"]) <= {"B1_SAME_DIR_PARALLEL",
                                                  "B2_OPPOSITE_ONLY",
                                                  "B3_NO_PARALLEL_FLOW"}),
                  f"{d['class_bb'].value_counts().to_dict()}"])
    mono = bool((d["n_par_same_100"] <= d["n_par_same_200"]).all()
                and (d["par_sum_same_xS_100"] <= d["par_sum_same_xS_200"]).all())
    gates.append(["G-B5 半径单调", mono,
                  f"Σsame 100m={d['par_sum_same_xS_100'].sum():,.0f} ≤ "
                  f"200m={d['par_sum_same_xS_200'].sum():,.0f}"])

    # ---------------- 负例 ----------------
    def sig(dd):
        o = float(dd["obs_8_9"].sum())
        return (round(float(dd["par_sum_same_xS_100"].sum()) / o, 6),
                int((dd["class_bb"] == "B1_SAME_DIR_PARALLEL").sum()),
                int((dd["class_bb"] == "B3_NO_PARALLEL_FLOW").sum()),
                round(float(dd["par_max_same_xS"].sum()) / o, 6))

    base = sig(d)
    neg: dict = {}
    rng = np.random.default_rng(20260929)
    x = d.copy()
    for c in ["par_sum_same_xS_100", "par_max_same_xS"]:
        x[c] = rng.permutation(x[c].to_numpy())
    x["class_bb"] = np.select(
        [x["par_sum_same_xS_100"] >= 0.5 * x["obs_8_9"],
         x["par_sum_opp_xS_100"] >= 0.5 * x["obs_8_9"]],
        ["B1_SAME_DIR_PARALLEL", "B2_OPPOSITE_ONLY"], "B3_NO_PARALLEL_FLOW")
    neg["N1_shuffle_parallel_flow"] = {"fired": sig(x) != base}
    b1 = sig(x)
    x = d.copy(); x["par_sum_same_xS_100"] = 0.0; x["par_max_same_xS"] = 0.0
    x["class_bb"] = "B3_NO_PARALLEL_FLOW"
    neg["N2_zero_parallel"] = {"fired": sig(x) != b1}
    b2 = sig(x)
    d3 = pd.DataFrame([ledger(s, shift_m=300.0) for s in tgt["lta_linkid"].tolist()])
    d3["class_bb"] = d["class_bb"].to_numpy()
    neg["N3_shift_mid"] = {"fired": sig(d3) != b2,
                           "detail": f"Σsame={d3['par_sum_same_xS_100'].sum():,.0f}"}
    b3 = sig(d3)
    d4 = pd.DataFrame([ledger(s, drop_dir=True) for s in tgt["lta_linkid"].tolist()])
    d4["class_bb"] = d["class_bb"].to_numpy()
    neg["N4_drop_dir_filter"] = {"fired": sig(d4) != b3,
                                 "detail": f"Σsame={d4['par_sum_same_xS_100'].sum():,.0f}"}
    neg["N5_reverse_all_note"] = {"fired": False,
                                  "note": "整体反向：同向/反向集合互换但阈值结构不变（同构）⇒ 仅记录"}

    fired = [k for k, v in neg.items() if not k.endswith("_note") and v["fired"]]
    gates.append(["G-N 负例 4 个有效门全 fired", len(fired) == 4, f"fired={fired}"])

    rec["summary"] = dict(
        n_target=len(d), obs_sum=obs_sum,
        class_count=d["class_bb"].value_counts().to_dict(),
        class_share_by_obs=(d.groupby("class_bb")["obs_8_9"].sum() / obs_sum).round(4).to_dict(),
        par_sum_same_100_xS=float(d["par_sum_same_xS_100"].sum()),
        par_sum_same_200_xS=float(d["par_sum_same_xS_200"].sum()),
        r_par_sum_same_100=float(d["par_sum_same_xS_100"].sum()) / obs_sum,
        r_par_sum_same_200=float(d["par_sum_same_xS_200"].sum()) / obs_sum,
        r_par_max_same_median=float(d["r_par_max_same"].median()),
        n_with_par_ge_half=int((d["r_par_sum_same"] >= 0.5).sum()),
        by_corridor=(d.groupby("RoadName").agg(
            n=("lta_linkid", "size"), obs=("obs_8_9", "sum"),
            r_par_same=("r_par_sum_same", "median"),
            n_B1=("class_bb", lambda s: int((s == "B1_SAME_DIR_PARALLEL").sum())),
            n_B3=("class_bb", lambda s: int((s == "B3_NO_PARALLEL_FLOW").sum()))).to_dict()),
    )
    rec["gates"] = [{"gate": g, "pass": bool(p), "measured": m} for g, p, m in gates]
    rec["negatives"] = neg
    rec["n_fail"] = int(sum(1 for _, p, _ in gates if not p))
    rec["verdict"] = ("ZERO_FLOW_PARALLEL_LEDGER_READY" if rec["n_fail"] == 0
                      else "ZERO_FLOW_PARALLEL_LEDGER_BLOCKED")
    rec["elapsed_s"] = round(time.time() - t0, 1)

    d.to_csv(OUT / "bb_zero_flow_ledger_7_9ibb.csv", index=False, encoding="utf-8-sig")
    for fn in ("bb_ledger_summary_7_9ibb.json", "_bb_audit_7_9ibb.json"):
        with open(OUT / fn, "w", encoding="utf-8") as f:
            json.dump(rec, f, ensure_ascii=False, indent=2, default=str)

    print("\n===== GATES =====", flush=True)
    for g, p, m in gates:
        print(f"  [{'PASS' if p else 'FAIL'}] {g:<36} {m}", flush=True)
    print("\n===== SUMMARY =====", flush=True)
    print(f"  class = {rec['summary']['class_count']}  by obs = {rec['summary']['class_share_by_obs']}", flush=True)
    print(f"  同向平行 Σ×S: R=100 m {rec['summary']['r_par_sum_same_100']:.4f}  "
          f"R=200 m {rec['summary']['r_par_sum_same_200']:.4f} (相对 Σobs)", flush=True)
    print(f"\nVERDICT={rec['verdict']}  n_fail={rec['n_fail']}  {rec['elapsed_s']}s", flush=True)
    return 0 if rec["n_fail"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
