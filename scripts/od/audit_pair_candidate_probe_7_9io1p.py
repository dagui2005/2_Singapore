# -*- coding: utf-8 -*-
"""Step 7.9I-O1-P · 对层「候选对象选取」后验探针（零仿真、只读）

⛔ 标签 = `EXPLORATORY_POST_HOC`。预注册 `PREREG_7_9I_O1.md` 与引擎
`audit_carriageway_pair_7_9io1.py` 的判据/阈值**未被改动**。

存在理由：O1 主引擎的 `r_pair = SCALE × Σ_C rep(C) / obs` 是「**近旁全部对向承载对象**」口径，
实测中位 **2.15**（> `PAIR_CONSISTENT` 上界 2.0）且尾部到 **72**。
按 `readme §4` 纪律「**候选对象选取 > 统计量**」与「**多边映射必报计数基数 K**」，
必须把 `Σ_C` 拆成三种候选选取规则并同报计数基数 `K_pair = n_comp`：

  R-sum ：Σ_C rep(C)          —— 预注册口径（全部对向对象）
  R-max ：max_C rep(C)        —— 单一最强对向链（「一个车行道对」口径）
  R-med ：median_C rep(C)     —— 分量中位

并同报同向侧的载流（`flow_same`）以说明「同向确无对象」。
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

import audit_sampling_capacity_7_9a1 as A                 # noqa: E402
import evaluate_calibration_7_4_2 as ev1                  # noqa: E402
import evaluate_demand_response_7_6f_1 as E               # noqa: E402
from diagnose_gap_7_9h import read_edge_full              # noqa: E402
from audit_corridor_scale_7_9ia import load_frozen, OUT   # noqa: E402
from audit_m1_accessibility_7_9ib import Graph            # noqa: E402
from audit_kpe_ecp_object_7_9ia2 import lta_section_geometry  # noqa: E402
from audit_carriageway_pair_7_9io1 import (               # noqa: E402
    circ_diff, comp_rep, weak_components, MAJOR, R0, DIR0, STEP, STEP_HI, Q0, Q1, Q2)

CACHE_NET = ROOT / "scripts" / "od" / "_cache_network_7_9c0.npz"


def main() -> int:
    t0 = time.time()
    rec: dict = {"step": "7.9I-O1-P/candidate-object-selection",
                 "label": "EXPLORATORY_POST_HOC", "scale": A.SCALE,
                 "R0_m": R0, "dir0_deg": DIR0, "band": [STEP, STEP_HI]}
    gates: list = []

    obs, cw, _ = load_frozen()
    edge1 = read_edge_full(A.V10_LS)
    G = Graph(np.load(CACHE_NET, allow_pickle=True))
    flow = np.nan_to_num(edge1.set_index("LINK")["HRS8-9avg"]
                         .reindex(G.ids).to_numpy(dtype=float), nan=0.0)
    id2i = {x: i for i, x in enumerate(G.ids)}
    bear_e = (np.degrees(np.arctan2(G.nx[G.t] - G.nx[G.f],
                                    G.ny[G.t] - G.ny[G.f])) + 360.0) % 360.0
    is_major = np.array([h in MAJOR for h in G.highway])
    rev: dict = {}
    for i in range(G.n_edges):
        rev.setdefault((int(G.t[i]), int(G.f[i])), []).append(i)

    gl = lta_section_geometry(ev1.TRAFFIC).set_index("LinkID")
    geo = pd.read_csv(E.SEC_GEO_7_6C, dtype={"lta_linkid": str}).set_index("lta_linkid")
    sec_edges: dict = {}
    for sid, g in cw.groupby("lta_linkid"):
        idx = [id2i[x] for x in g["matsim_link_id"].tolist() if x in id2i]
        if idx:
            sec_edges[str(sid)] = idx
    obs_map = {str(k): float(v) for k, v in obs.set_index("LinkID")["obs_8_9"].items()}

    bb = pd.read_csv(OUT / "bb_zero_flow_ledger_7_9ibb.csv", dtype={"lta_linkid": str})
    o1 = pd.read_csv(OUT / "o1_pair_cards_7_9io1.csv", dtype={"lta_linkid": str})
    target = bb["lta_linkid"].tolist()

    # ---------- 构造性断言：坐标同源 ----------
    assert 0.0 < float(geo.loc[target[0], "mid_x"]) < 1.0e6
    gates.append(["G-O1P-1 坐标同源（SEC_GEO SVY21 量级）", True,
                  f"样例 {target[0]} mid_x={float(geo.loc[target[0],'mid_x']):.1f}"])

    rows = []
    for sid in target:
        mx, my = float(geo.loc[sid, "mid_x"]), float(geo.loc[sid, "mid_y"])
        sb = float(gl.loc[sid, "bear"])
        excl = np.zeros(G.n_edges, bool)
        if sid in sec_edges:
            excl[np.asarray(sec_edges[sid], np.int64)] = True
        near = np.where((((G.ex - mx) ** 2 + (G.ey - my) ** 2) < R0 * R0)
                        & is_major & (~excl))[0]
        d_same = np.array([circ_diff(bear_e[x], sb) for x in near], float) if len(near) else np.array([])
        d_opp = np.array([circ_diff(bear_e[x], (sb + 180.0) % 360.0) for x in near], float) if len(near) else np.array([])
        E_same = near[d_same < DIR0]
        E_opp = near[d_opp < DIR0]

        reps = []
        for C in weak_components(E_opp, G):
            r, k = comp_rep(C, G, flow, False)
            reps.append((r, k, int(len(C)), float(flow[C].sum())))
        reps_sorted = sorted([x[0] for x in reps], reverse=True)
        K_pair = len(reps)
        rep_sum = float(sum(reps_sorted))
        rep_max = float(reps_sorted[0]) if reps_sorted else 0.0
        rep_med = float(np.median(reps_sorted)) if reps_sorted else 0.0

        obs_s = float(obs_map.get(sid, np.nan))
        div = obs_s if (obs_s and np.isfinite(obs_s) and obs_s > 0) else np.nan
        r_sum, r_max, r_med = (A.SCALE * rep_sum / div, A.SCALE * rep_max / div,
                               A.SCALE * rep_med / div)

        rows.append(dict(
            lta_linkid=sid, obs_8_9=obs_s,
            n_E_same=len(E_same), n_E_opp=len(E_opp), K_pair=K_pair,
            n_dir_comp=int(sum(1 for x in reps if x[1] == "directed_path")),
            flow_same_xS=A.SCALE * float(flow[E_same].sum()),
            flow_opp_xS=A.SCALE * float(flow[E_opp].sum()),
            rep_sum_xS=A.SCALE * rep_sum, rep_max_xS=A.SCALE * rep_max, rep_med_xS=A.SCALE * rep_med,
            r_pair_sum=r_sum, r_pair_max=r_max, r_pair_med=r_med,
            in_sum=bool(np.isfinite(r_sum) and STEP <= r_sum <= STEP_HI),
            in_max=bool(np.isfinite(r_max) and STEP <= r_max <= STEP_HI),
            in_med=bool(np.isfinite(r_med) and STEP <= r_med <= STEP_HI),
        ))
    d = pd.DataFrame(rows).merge(
        bb[["lta_linkid", "RoadName", "RoadCat", "class_bb"]], on="lta_linkid", how="left")

    # ---------- 对账：预注册口径逐位一致 ----------
    j = d.set_index("lta_linkid").join(o1.set_index("lta_linkid")[["sim_pair_xS", "r_pair", "n_comp", "n_E_opp"]], rsuffix="_o1")
    ok = bool(np.allclose(j["rep_sum_xS"], j["sim_pair_xS"]) and np.allclose(j["r_pair_sum"], j["r_pair"])
              and (j["K_pair"] == j["n_comp"]).all() and (j["n_E_opp"] == j["n_E_opp_o1"]).all())
    gates.append(["G-O1P-2 与 O1 主引擎逐位对账（rep_sum / r_pair / K_pair / n_E_opp）", ok,
                  f"全等={ok}  ΣK_pair={int(d['K_pair'].sum())}"])

    # ---------- 非退化 ----------
    n_any = int(d["in_sum"].sum()) + int(d["in_max"].sum()) + int(d["in_med"].sum())
    gates.append(["G-O1P-3 候选选取规则非退化（三种规则命中的节不全同）",
                  bool(len({frozenset(d[d[f]].index) for f in ("in_sum", "in_max", "in_med")}) > 1),
                  f"命中节数 sum={int(d['in_sum'].sum())} max={int(d['in_max'].sum())} med={int(d['in_med'].sum())}; 合计 {n_any}"])

    # ---------- 计数基数必须同报 ----------
    gates.append(["G-O1P-4 计数基数同报（K_pair 分布非退化）",
                  bool(d["K_pair"].nunique() > 1),
                  f"K_pair {d['K_pair'].value_counts().to_dict()}"])

    # ---------- 同向侧对照（说明「同向确无对象」）----------
    same_less = bool((d["flow_same_xS"] < d["flow_opp_xS"]).sum() >= int(0.8 * len(d)))
    gates.append(["G-O1P-5 同向侧对照：≥80% 断面 flow_same < flow_opp", same_less,
                  f"{(d['flow_same_xS'] < d['flow_opp_xS']).sum()}/{len(d)} 节；"
                  f"Σsame={d['flow_same_xS'].sum():.1f} Σopp={d['flow_opp_xS'].sum():.1f}"])

    def cov(col, mask_col):
        w = d.dropna(subset=[col])
        tot = float(w["obs_8_9"].sum())
        sub = float(w.loc[w[mask_col], "obs_8_9"].sum())
        return dict(n=int(w[mask_col].sum()), obs_share=sub / tot if tot > 0 else float("nan"))

    summ = {
        "rules": {"R-sum（预注册）": cov("r_pair_sum", "in_sum"),
                  "R-max（单一最强对向链）": cov("r_pair_max", "in_max"),
                  "R-med（分量中位）": cov("r_pair_med", "in_med")},
        "median_r": {k: float(np.nanmedian(d[k])) for k in ("r_pair_sum", "r_pair_max", "r_pair_med")},
        "p90_r": {k: float(np.nanquantile(d[k], .90)) for k in ("r_pair_sum", "r_pair_max", "r_pair_med")},
        "by_class_r_max_median": {c: float(np.nanmedian(d.loc[d["class_bb"] == c, "r_pair_max"]))
                                  for c in sorted(d["class_bb"].dropna().unique())},
        "K_pair_total": int(d["K_pair"].sum()),
        "flow_same_vs_opp_xS": {"same": float(d["flow_same_xS"].sum()),
                                "opp": float(d["flow_opp_xS"].sum())},
        "corr_obs_vs_r_sum": float(np.corrcoef(np.log10(d["obs_8_9"].clip(lower=1)),
                                               np.log10(d["r_pair_sum"].clip(lower=1e-6)))[0, 1]),
    }
    rec["summary"] = summ
    rec["gates"] = [{"gate": g, "pass": bool(p), "measured": m} for g, p, m in gates]
    rec["n_fail"] = int(sum(1 for _, p, _ in gates if not p))
    rec["verdict"] = ("PAIR_CANDIDATE_PROBE_READY" if rec["n_fail"] == 0
                      else "PAIR_CANDIDATE_PROBE_BLOCKED")
    rec["elapsed_s"] = round(time.time() - t0, 1)

    d.to_csv(OUT / "o1p_pair_candidate_cards_7_9io1p.csv", index=False, encoding="utf-8-sig")
    (OUT / "o1p_pair_candidate_summary_7_9io1p.json").write_text(
        json.dumps(rec, ensure_ascii=False, indent=1), encoding="utf-8")

    print("\n===== GATES =====")
    for g, p, m in gates:
        print(f"  [{'PASS' if p else 'FAIL'}] {g}\n          | {m}")
    print("\n===== 三种候选选取规则（38 节 / Σobs=62,050.5）=====")
    for k, v in summ["rules"].items():
        print(f"  {k:24s} n={v['n']:2d}  Σobs 占比={v['obs_share']:.4f}")
    print("\n  r 中位 :", {k: round(v, 4) for k, v in summ["median_r"].items()})
    print("  r p90  :", {k: round(v, 4) for k, v in summ["p90_r"].items()})
    print("  K_pair 合计:", summ["K_pair_total"], "| Σsame xS =", round(summ["flow_same_vs_opp_xS"]["same"], 1),
          "| Σopp xS =", round(summ["flow_same_vs_opp_xS"]["opp"], 1))
    print("\n===== B2 22 节（R-max 口径）=====")
    x = d[d["class_bb"] == "B2_OPPOSITE_ONLY"][
        ["lta_linkid", "RoadName", "obs_8_9", "n_E_same", "n_E_opp", "K_pair",
         "flow_same_xS", "flow_opp_xS", "r_pair_sum", "r_pair_max", "r_pair_med"]]
    print(x.sort_values("obs_8_9", ascending=False).round(4).to_string(index=False))
    print(f"\nVERDICT={rec['verdict']}  n_fail={rec['n_fail']}  {rec['elapsed_s']}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
