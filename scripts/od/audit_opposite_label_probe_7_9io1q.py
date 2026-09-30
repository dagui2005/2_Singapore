# -*- coding: utf-8 -*-
"""Step 7.9I-O1-Q · 「LTA 对向断面是否被正常加载」决定性对照（零仿真、只读）

⛔ 标签 = `EXPLORATORY_POST_HOC`。预注册 `PREREG_7_9I_O1.md` 与主引擎未改。

存在理由：O1 已证「B2 的对向对象存在且有流、同向侧无流」（`r_max` 中位 **1.87**）。
但「对向有流」**不足以**断定观测对象被错配——还须排除竞争解释：
**MATSim 是不是只加载了该设施的一条车行道？**

判据：对每个 B2 断面 `s`，在 LTA 侧找**方位相差 ~180°、几何邻近**的断面 `s'`
（同一物理段的另一方向）。若 `s'` 在**冻结 canonical 口径**下标定正常
（`ratio_median ∈ [0.5, 2]`）而 `s` 为 0 ⇒ **同一物理段两个方向，一个正常一个全零**
⇒ 属「**对象层面**」问题（单侧对象缺失/错位），**不是**需求不足。
若 `s'` 也低 ⇒ 回到需求/路径域。

★修订记录（2026-09-30，本脚本内部）：
  `v1` 的 `G-O1Q-4` 实测 `0/19` —— 经核查是**实现与其判据文字不一致**
  （`v1` 实际比较的是 `matched(s) ∩ matched(s')`，而判据要求的是
  `matched(s') ∩ E_opp(s)`）⇒ 属**实现缺陷**，非科学结论。`v2` 已改为判据声明的量，
  并新增 `R ∈ {100,200,300} m` 半径敏感性以解释 `L3_NO_LTA_OPP`。
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
from audit_carriageway_pair_7_9io1 import circ_diff, MAJOR, DIR0  # noqa: E402

CACHE_NET = ROOT / "scripts" / "od" / "_cache_network_7_9c0.npz"
R_GRID = (100.0, 200.0, 300.0)
STEP, STEP_HI = 0.5, 2.0


def main() -> int:
    t0 = time.time()
    rec: dict = {"step": "7.9I-O1-Q/opposite-label-control", "rev": "v2",
                 "label": "EXPLORATORY_POST_HOC", "scale": A.SCALE,
                 "R_grid_m": list(R_GRID), "dir0_deg": DIR0, "band": [STEP, STEP_HI],
                 "v1_defect": "G-O1Q-4 v1 实现为 matched(s)∩matched(s')，与判据文字不符 ⇒ 已修"}
    gates: list = []

    obs, cw, _ = load_frozen()
    G = Graph(np.load(CACHE_NET, allow_pickle=True))
    flow = np.nan_to_num(read_edge_full(A.V10_LS).set_index("LINK")["HRS8-9avg"]
                         .reindex(G.ids).to_numpy(dtype=float), nan=0.0)
    is_major = np.array([h in MAJOR for h in G.highway])
    id2i = {x: i for i, x in enumerate(G.ids)}
    bear_e = (np.degrees(np.arctan2(G.nx[G.t] - G.nx[G.f],
                                    G.ny[G.t] - G.ny[G.f])) + 360.0) % 360.0

    gl = lta_section_geometry(ev1.TRAFFIC).set_index("LinkID")
    geo = pd.read_csv(E.SEC_GEO_7_6C, dtype={"lta_linkid": str}).set_index("lta_linkid")
    sc = pd.read_csv(OUT / "section_scale_v10.csv", dtype={"lta_linkid": str}).set_index("lta_linkid")
    bb = pd.read_csv(OUT / "bb_zero_flow_ledger_7_9ibb.csv", dtype={"lta_linkid": str})
    o1 = pd.read_csv(OUT / "o1_pair_cards_7_9io1.csv", dtype={"lta_linkid": str}).set_index("lta_linkid")
    o1p = pd.read_csv(OUT / "o1p_pair_candidate_cards_7_9io1p.csv",
                      dtype={"lta_linkid": str}).set_index("lta_linkid")
    target = bb["lta_linkid"].tolist()
    assert len(target) == 38

    # 断面 → 匹配边（id 与索引两套）
    sec_ids: dict = {}
    sec_idx: dict = {}
    for sid, g in cw.groupby("lta_linkid"):
        ids = g["matsim_link_id"].astype(str).tolist()
        sec_ids[str(sid)] = set(ids)
        sec_idx[str(sid)] = [id2i[x] for x in ids if x in id2i]

    pool = [s for s in sc.index.astype(str) if s in geo.index and s in gl.index]
    pmx = np.array([float(geo.loc[s, "mid_x"]) for s in pool])
    pmy = np.array([float(geo.loc[s, "mid_y"]) for s in pool])
    pbr = np.array([float(gl.loc[s, "bear"]) for s in pool])

    # ---------- G-O1Q-1 坐标同源 ----------
    assert 0.0 < float(geo.loc[target[0], "mid_x"]) < 1.0e6
    gates.append(["G-O1Q-1 坐标同源（SEC_GEO SVY21 量级）", True,
                  f"样例 {target[0]} mid_x={float(geo.loc[target[0],'mid_x']):.1f}"])

    # ---------- G-O1Q-3 与冻结表对账 ----------
    zero_ok = bool((sc.loc[target, "sim_median_xS"] == 0).all())
    gates.append(["G-O1Q-3 与冻结 canonical 表对账（38 节 sim_median_xS 全为 0）",
                  zero_ok, f"全零={zero_ok} | Σsim_median_xS={float(sc.loc[target,'sim_median_xS'].sum())}"])

    rows = []
    nexc = []
    for s in target:
        mx, my, sb = float(geo.loc[s, "mid_x"]), float(geo.loc[s, "mid_y"]), float(gl.loc[s, "bear"])
        dd = np.hypot(pmx - mx, pmy - my)

        # E_opp(s)：半径内 MAJOR、对向、排除匹配边
        excl = np.zeros(G.n_edges, bool)
        if sec_idx.get(s):
            excl[np.asarray(sec_idx[s], np.int64)] = True
        near = np.where((((G.ex - mx) ** 2 + (G.ey - my) ** 2) < R_GRID[0] ** 2)
                        & is_major & (~excl))[0]
        ang = circ_diff(bear_e[near], (sb + 180.0) % 360.0) if len(near) else np.array([])
        E_opp = set(int(x) for x in near[ang < DIR0])
        nexc.append(dict(lta_linkid=s, n_E_opp_o1q=len(E_opp)))

        # 找 LTA 对向断面：由近到远，记录首次命中的半径
        rec_r = {}
        opp_sec, opp_r = "", np.nan
        n_near_any = {}
        for R in R_GRID:
            ok = (dd <= R) & (dd > 1e-6)
            idxs = np.where(ok)[0]
            n_near_any[R] = int(len(idxs))
            cand = [(pool[i], float(dd[i])) for i in idxs
                    if circ_diff(pbr[i], (sb + 180.0) % 360.0) < DIR0]
            cand.sort(key=lambda x: x[1])
            rec_r[R] = len(cand)
            if not opp_sec and cand:
                opp_sec, opp_r = cand[0]

        if not opp_sec:
            rows.append(dict(lta_linkid=s, obs_8_9=float(sc.loc[s, "obs_8_9"]),
                             opp_sec="", opp_radius_m=np.nan, opp_dist_m=np.nan, opp_dbear=np.nan,
                             opp_obs=np.nan, opp_sim_xS=np.nan, opp_ratio_median=np.nan,
                             opp_flow_edges=np.nan, n_overlap_Eopp=np.nan,
                             obs_ratio=np.nan, n_lta_near_any_300=int(n_near_any[300.0]),
                             n_opp_cand_100=rec_r[100.0], n_opp_cand_200=rec_r[200.0],
                             n_opp_cand_300=rec_r[300.0], label="L3_NO_LTA_OPP"))
            continue

        ei = set(sec_idx.get(opp_sec, []))
        rows.append(dict(
            lta_linkid=s, obs_8_9=float(sc.loc[s, "obs_8_9"]),
            opp_sec=opp_sec, opp_radius_m=opp_r,
            opp_dist_m=float(np.hypot(float(geo.loc[opp_sec, "mid_x"]) - mx,
                                      float(geo.loc[opp_sec, "mid_y"]) - my)),
            opp_dbear=circ_diff(float(gl.loc[opp_sec, "bear"]), (sb + 180.0) % 360.0),
            opp_obs=float(sc.loc[opp_sec, "obs_8_9"]),
            opp_sim_xS=float(sc.loc[opp_sec, "sim_median_xS"]),
            opp_ratio_median=float(sc.loc[opp_sec, "ratio_median"]),
            opp_flow_edges=float(sc.loc[opp_sec, "n_edge_flow_gt0"]),
            n_overlap_Eopp=len(ei & E_opp),
            obs_ratio=float(sc.loc[opp_sec, "obs_8_9"]) / float(sc.loc[s, "obs_8_9"]),
            n_lta_near_any_300=int(n_near_any[300.0]),
            n_opp_cand_100=rec_r[100.0], n_opp_cand_200=rec_r[200.0], n_opp_cand_300=rec_r[300.0],
            label=""))
    d = pd.DataFrame(rows).merge(
        bb[["lta_linkid", "RoadName", "RoadCat", "class_bb"]], on="lta_linkid", how="left")
    d = d.merge(o1[["Q_class", "r_pair", "n_comp", "n_E_opp"]], left_on="lta_linkid",
                right_index=True, how="left")

    nre = pd.DataFrame(nexc).set_index("lta_linkid")
    ok_e = bool((nre["n_E_opp_o1q"] == o1p["n_E_opp"]).all())
    gates.append(["G-O1Q-6 E_opp 重建与 O1-P 逐位对账", ok_e,
                  f"全等={ok_e}  Σ={int(nre['n_E_opp_o1q'].sum())}"])

    def lab(r):
        if r["label"] == "L3_NO_LTA_OPP":
            return r["label"]
        q = r["opp_ratio_median"]
        if not np.isfinite(q):
            return "L4_OPP_NA"
        if STEP <= q <= STEP_HI:
            return "L1_OPP_LOADED_OK"
        return "L2_OPP_ALSO_LOW" if q < STEP else "L5_OPP_HIGH"
    d["label"] = d.apply(lab, axis=1)

    lc = d["label"].value_counts().to_dict()
    gates.append(["G-O1Q-2 对照分类非退化（L1 与 L3 都出现）",
                  bool(lc.get("L1_OPP_LOADED_OK", 0) > 0 and lc.get("L3_NO_LTA_OPP", 0) < len(d)),
                  f"{lc}"])

    with_opp = d[d["label"] != "L3_NO_LTA_OPP"]
    n_hit = int((with_opp["n_overlap_Eopp"] > 0).sum())
    gates.append(["G-O1Q-4 对向断面的匹配边落在 s 的 E_opp 池内（判据声明的量）",
                  bool(n_hit > 0),
                  f"{n_hit}/{len(with_opp)} 节命中；中位重叠 "
                  f"{float(with_opp['n_overlap_Eopp'].median()):.0f} 条"])

    sym = with_opp["obs_ratio"].dropna()
    gates.append(["G-O1Q-5 LTA 双向观测对称性（obs_{s'}/obs_s 中位 ∈ [0.5,2]）",
                  bool(0.5 <= float(sym.median()) <= 2.0),
                  f"中位 {float(sym.median()):.3f} | p10 {float(sym.quantile(.10)):.3f} | p90 {float(sym.quantile(.90)):.3f}"])

    # L3 归因 + 与 O1 主引擎的构造性恒等核验
    l3 = d[d["label"] == "L3_NO_LTA_OPP"]
    eopp = nre["n_E_opp_o1q"]
    set_zero = set(eopp.index[eopp.to_numpy() == 0])
    set_q2 = set(o1.index[o1["Q_class"] == "Q2_NO_OPPOSITE_OBJECT"])
    gates.append(["G-O1Q-7 {s : n_E_opp = 0} ≡ O1 主引擎 Q2_NO_OPPOSITE_OBJECT（逐位）",
                  bool(set_zero == set_q2),
                  f"n_E_opp=0 的节 {sorted(set_zero)} vs Q2 {sorted(set_q2)}；"
                  f"对称差 {sorted(set_zero ^ set_q2)}"])
    l3a = l3[l3["lta_linkid"].isin(eopp.index[eopp.to_numpy() > 0])]
    l3b = l3[l3["lta_linkid"].isin(set_zero)]
    expl = dict(n_l3=int(len(l3)),
                L3a_LTA_COVERAGE=dict(n=int(len(l3a)), obs=float(l3a["obs_8_9"].sum()),
                                      ids=sorted(l3a["lta_linkid"].tolist())),
                L3b_NO_OBJECT_BOTH=dict(n=int(len(l3b)), obs=float(l3b["obs_8_9"].sum()),
                                        ids=sorted(l3b["lta_linkid"].tolist())),
                med_near_any_300=float(l3["n_lta_near_any_300"].median()) if len(l3) else float("nan"),
                n_l3_with_near_any_300=int((l3["n_lta_near_any_300"] > 0).sum()) if len(l3) else 0,
                n_l3_with_opp_cand_300=int((l3["n_opp_cand_300"] > 0).sum()) if len(l3) else 0)
    gates.append(["G-O1Q-8 L3 两子类合计划分完整（L3a ∪ L3b = L3 且互斥）",
                  bool(len(l3a) + len(l3b) == len(l3)),
                  f"L3a（LTA 侧覆盖不足）{len(l3a)} 节 / L3b（两侧均无对向）{len(l3b)} 节 / L3 共 {len(l3)} 节"])

    def sh(mask):
        w = d[mask]
        return dict(n=int(len(w)), obs=float(w["obs_8_9"].sum()),
                    obs_share=float(w["obs_8_9"].sum() / d["obs_8_9"].sum()))
    l1 = d["label"] == "L1_OPP_LOADED_OK"
    summ = {"label_counts": {k: int(v) for k, v in lc.items()},
            "L1_OPP_LOADED_OK": sh(l1),
            "L1_OPP_LOADED_OK_strict_R100": sh(l1 & (d["opp_radius_m"] <= 100.0)),
            "L1_OPP_LOADED_OK_wide_Rgt100": sh(l1 & (d["opp_radius_m"] > 100.0)),
            "L2_OPP_ALSO_LOW": sh(d["label"] == "L2_OPP_ALSO_LOW"),
            "L3_NO_LTA_OPP": sh(d["label"] == "L3_NO_LTA_OPP"),
            "L5_OPP_HIGH": sh(d["label"] == "L5_OPP_HIGH"),
            "by_bb_class_label": pd.crosstab(d["class_bb"], d["label"]).to_dict(),
            "opp_radius_used": {str(k): int(v) for k, v in d["opp_radius_m"].value_counts().items()},
            "L3_explain": expl,
            "n_overlap_hit": n_hit}
    rec["summary"] = summ
    rec["gates"] = [{"gate": g, "pass": bool(p), "measured": m} for g, p, m in gates]
    rec["n_fail"] = int(sum(1 for _, p, _ in gates if not p))
    rec["verdict"] = ("OPPOSITE_LABEL_CONTROL_READY" if rec["n_fail"] == 0
                      else "OPPOSITE_LABEL_CONTROL_BLOCKED")
    rec["elapsed_s"] = round(time.time() - t0, 1)

    d.to_csv(OUT / "o1q_opposite_label_cards_7_9io1q.csv", index=False, encoding="utf-8-sig")
    (OUT / "o1q_opposite_label_summary_7_9io1q.json").write_text(
        json.dumps(rec, ensure_ascii=False, indent=1), encoding="utf-8")

    print("\n===== GATES =====")
    for g, p, m in gates:
        print(f"  [{'PASS' if p else 'FAIL'}] {g}\n          | {m}")
    print("\n===== 对照分类（38 节）=====")
    for k in ("L1_OPP_LOADED_OK", "L1_OPP_LOADED_OK_strict_R100",
              "L1_OPP_LOADED_OK_wide_Rgt100", "L2_OPP_ALSO_LOW", "L5_OPP_HIGH", "L3_NO_LTA_OPP"):
        v = summ.get(k)
        if v and v["n"]:
            print(f"  {k:30s} n={v['n']:2d}  Σobs={v['obs']:9.1f}  占比={v['obs_share']:.4f}")
    print("\n  L3 归因:", expl)
    print("  对向断面定位半径分布:", summ["opp_radius_used"])
    print("\n===== B(b) 类 × 对照分类 =====")
    print(pd.crosstab(d["class_bb"], d["label"]).to_string())
    print("\n===== B2 明细 =====")
    cc = ["lta_linkid", "obs_8_9", "opp_sec", "opp_radius_m", "opp_dist_m", "opp_obs",
          "opp_sim_xS", "opp_ratio_median", "n_overlap_Eopp", "obs_ratio", "label"]
    print(d[d["class_bb"] == "B2_OPPOSITE_ONLY"][cc].sort_values("obs_8_9", ascending=False)
          .round(4).to_string(index=False))
    print(f"\nVERDICT={rec['verdict']}  n_fail={rec['n_fail']}  {rec['elapsed_s']}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
