# -*- coding: utf-8 -*-
"""Step 7.9I-O1 · B2 车行道对（carriageway pair）层 —— 零仿真、只读

★要回答的问题（用户 2026-09-30 裁定）：
  **LTA 所观测的「一个方向断面」，与 MATSim 中由独立节点串表达的另一方向车行道，
    到底是什么对应关系？**

预注册：`reports/corridor_scale_audit_7_9i/PREREG_7_9I_O1.md`（运行前冻结）。

⛔ 坐标纪律（`CLOSURE §3-R2`）：断面位置**一律**取 `SEC_GEO_7_6C.mid_x/mid_y`（**SVY21**）；
   ⛔ 不得取 `lta_section_geometry().mx/my`（局部等距平面米 ≈1.15e7，与全网图不同源）。
   `lta_section_geometry()` 只取其 `bear` / `len_m`（与 CRS 无关）。

⛔ 不改 v1.0 任何参数；不重跑 MATSim；不产生 v1.1；`changed = 0`。
"""
from __future__ import annotations

import ast
import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.sparse import csr_matrix
from scipy.sparse.csgraph import connected_components

ROOT = Path(r"D:\Luan\2026-05\2_Singapore")
sys.path.insert(0, str(ROOT / "scripts" / "od"))

import audit_sampling_capacity_7_9a1 as A              # noqa: E402
import evaluate_calibration_7_4_2 as ev1               # noqa: E402
import evaluate_demand_response_7_6f_1 as E            # noqa: E402
from diagnose_gap_7_9h import read_edge_full           # noqa: E402
from audit_corridor_scale_7_9ia import load_frozen, OUT  # noqa: E402
from audit_m1_accessibility_7_9ib import Graph         # noqa: E402
from audit_kpe_ecp_object_7_9ia2 import lta_section_geometry  # noqa: E402

CACHE_NET = ROOT / "scripts" / "od" / "_cache_network_7_9c0.npz"
MAJOR = {"motorway", "motorway_link", "trunk", "trunk_link"}

R0 = 100.0        # 基准半径（m）
DIR0 = 30.0       # 基准方向容差（°）
STEP = 0.5        # PAIR_CONSISTENT 下界
STEP_HI = 2.0     # PAIR_CONSISTENT 上界

Q0, Q1, Q2 = "Q0_TWIN_PAIR", "Q1_SEPARATE_CARRIAGEWAY", "Q2_NO_OPPOSITE_OBJECT"


def circ_diff(a, b):
    return abs(((a - b + 180.0) % 360.0) - 180.0)


# ---------------------------------------------------------------- 链分量代表值
def comp_rep(edges, G, flow, force_sum=False):
    """弱连通分量的代表值。返回 (rep, kind)。

    - `kind == 'directed_path'` ：`|E| = |V| − 1` 且 `max(outdeg) ≤ 1`、`max(indeg) ≤ 1`
      且**恰有 1 个 `indeg = 0` 起点、恰有 1 个 `outdeg = 0` 终点** ⇒ 同一股车流 ⇒ `median`
    - 否则（**无向**路径但折返 / 分支 / 多起点终点）⇒ 不同股车流 ⇒ `sum`

    ★为何不用「链内每步方位一致」当判据：`E_opp` 内每条边**已按方位筛过**，
      该条件**恒真** ⇒ 命中 100% 的退化判据（违反 `readme §4` 纪律）。
    """
    e = np.asarray(edges, np.int64)
    if not len(e):
        return 0.0, "sum"
    f = G.f[e]
    t = G.t[e]
    nodes = np.unique(np.concatenate([f, t]))
    nid = {int(x): i for i, x in enumerate(nodes)}
    fi = np.fromiter((nid[int(x)] for x in f), np.int64, len(f))
    ti = np.fromiter((nid[int(x)] for x in t), np.int64, len(t))
    m = len(nodes)
    outd = np.bincount(fi, minlength=m)
    ind = np.bincount(ti, minlength=m)
    is_dir = (len(e) == m - 1 and int(outd.max()) <= 1 and int(ind.max()) <= 1
              and int((ind == 0).sum()) == 1 and int((outd == 0).sum()) == 1)
    if is_dir and not force_sum:
        return float(np.median(flow[e])), "directed_path"
    return float(flow[e].sum()), "sum"


def weak_components(edges, G):
    """E_opp 诱导子图的弱连通分量 ⇒ list[np.ndarray(edge idx)]。"""
    e = np.asarray(edges, np.int64)
    if not len(e):
        return []
    f, t = G.f[e], G.t[e]
    nodes = np.unique(np.concatenate([f, t]))
    nid = {int(x): i for i, x in enumerate(nodes)}
    fi = np.fromiter((nid[int(x)] for x in f), np.int64, len(f))
    ti = np.fromiter((nid[int(x)] for x in t), np.int64, len(t))
    m = len(nodes)
    adj = csr_matrix((np.ones(2 * len(e), np.int8),
                      (np.concatenate([fi, ti]), np.concatenate([ti, fi]))),
                     shape=(m, m))
    nc, lab = connected_components(adj, directed=False)
    return [e[lab[fi] == c] for c in range(nc)]


# ---------------------------------------------------------------- 单断面扫描
def scan_section(G, flow, bear_e, is_major, rev, geo, gl, sec_edges,
                 sid, obs_map, R, DIR_OK, use_local_crs=False, force_sum=False):
    """返回 dict（一行卡片）。"""
    if sid in geo.index:
        mx, my = float(geo.loc[sid, "mid_x"]), float(geo.loc[sid, "mid_y"])
    else:
        return None
    if sid not in gl.index:
        return None
    sb = float(gl.loc[sid, "bear"])
    if use_local_crs:                       # ← 负例 N3：故意用非同源坐标
        mx, my = float(gl.loc[sid, "mx"]), float(gl.loc[sid, "my"])

    ms = sec_edges.get(sid, [])
    excl = np.zeros(G.n_edges, bool)
    if ms:
        excl[np.asarray(ms, np.int64)] = True

    near = np.where((((G.ex - mx) ** 2 + (G.ey - my) ** 2) < R * R)
                    & is_major & (~excl))[0]
    if len(near):
        d_opp = np.array([circ_diff(bear_e[x], (sb + 180.0) % 360.0)
                          for x in near], float)
        E_opp = near[d_opp < DIR_OK]
    else:
        E_opp = np.array([], np.int64)

    n_opp = int(len(E_opp))
    n_opp_flow = int((flow[E_opp] > 0).sum()) if n_opp else 0
    has_twin = any((int(G.f[x]), int(G.t[x])) in rev for x in E_opp)
    n_twin = int(sum(1 for x in E_opp if (int(G.f[x]), int(G.t[x])) in rev))

    comps = weak_components(E_opp, G)
    reps, kinds = [], []
    for C in comps:
        r, k = comp_rep(C, G, flow, force_sum)
        reps.append(r)
        kinds.append(k)
    n_dir = int(sum(1 for k in kinds if k == "directed_path"))
    sim_pair = A.SCALE * float(sum(reps))
    obs_s = float(obs_map.get(sid, np.nan))
    r_pair = (sim_pair / obs_s) if (obs_s and np.isfinite(obs_s) and obs_s > 0) else np.nan

    q = Q2 if n_opp == 0 else (Q0 if has_twin else Q1)
    return dict(lta_linkid=sid, obs_8_9=obs_s,
                n_E_opp=n_opp, n_E_opp_flow=n_opp_flow, n_E_opp_noflow=n_opp - n_opp_flow,
                Q_class=q, has_twin=bool(has_twin), n_twin_edges=n_twin,
                n_comp=len(comps), n_directed=n_dir, n_sum=len(comps) - n_dir,
                sim_pair_xS=sim_pair, r_pair=r_pair,
                pair_consistent=bool(np.isfinite(r_pair) and STEP <= r_pair <= STEP_HI))


def main() -> int:
    t0 = time.time()
    rec: dict = {"step": "7.9I-O1/carriageway-pair-layer", "scale": A.SCALE,
                 "R0_m": R0, "dir0_deg": DIR0,
                 "pair_consistent_band": [STEP, STEP_HI],
                 "label": "PRE_REGISTERED"}
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

    # 断面 → 匹配边索引
    sec_edges: dict = {}
    for sid, g in cw.groupby("lta_linkid"):
        idx = [id2i[x] for x in g["matsim_link_id"].tolist() if x in id2i]
        if idx:
            sec_edges[str(sid)] = idx
    obs_map = obs.set_index("LinkID")["obs_8_9"].to_dict()
    obs_map = {str(k): float(v) for k, v in obs_map.items()}

    bb = pd.read_csv(OUT / "bb_zero_flow_ledger_7_9ibb.csv", dtype={"lta_linkid": str})
    bbp = pd.read_csv(OUT / "bbp_direction_probe_7_9ibbp.csv", dtype={"lta_linkid": str})
    assert len(bb) == 38, len(bb)
    target = bb["lta_linkid"].tolist()

    # ---------- 构造性断言：坐标同源 ----------
    cand = [s for s in target if s in geo.index]
    assert cand, "无任何断面命中 SEC_GEO"
    smp = cand[0]
    mx_s = float(geo.loc[smp, "mid_x"])
    assert 0.0 < mx_s < 1.0e6, f"SEC_GEO 坐标疑似非同源: {mx_s}"
    gates.append(["G-O1-1 坐标同源（样例 SEC_GEO mid_x 落在 SVY21 量级 <1e6）",
                  bool(0.0 < mx_s < 1.0e6), f"样例 {smp} mid_x={mx_s:.1f}"])

    # ---------- 基准扫描：38 节 ----------
    rows = []
    for sid in target:
        r = scan_section(G, flow, bear_e, is_major, rev, geo, gl, sec_edges,
                         sid, obs_map, R0, DIR0)
        assert r is not None, f"断面 {sid} 缺几何/bear"
        rows.append(r)
    d = pd.DataFrame(rows).merge(
        bb[["lta_linkid", "RoadName", "RoadCat", "class_bb", "n_matched",
            "n_par_opp_100", "par_sum_opp_xS_100", "r_par_sum_opp"]],
        on="lta_linkid", how="left")

    # ---------- 靶场全集普查（576）----------
    all_sec = sorted(set(str(x) for x in cw["lta_linkid"].unique()))
    crows = []
    for sid in all_sec:
        r = scan_section(G, flow, bear_e, is_major, rev, geo, gl, sec_edges,
                         sid, obs_map, R0, DIR0)
        if r is None:
            continue
        crows.append(r)
    cen = pd.DataFrame(crows)
    nm = obs.set_index("LinkID")
    cen["RoadName"] = [str(nm.loc[s, "RoadName"]) if s in nm.index else "" for s in cen["lta_linkid"]]
    cen["RoadCat"] = [str(nm.loc[s, "RoadCat"]) if s in nm.index else "" for s in cen["lta_linkid"]]
    cen["in_bb_target"] = cen["lta_linkid"].isin(set(target))

    # ---------- G-O1-2 / G-O1-7：口径嵌套 + 逐位对账 ----------
    ok2 = bool((d["n_E_opp_flow"] == d["n_par_opp_100"]).all())
    gates.append(["G-O1-2 与冻结引擎逐位对账 n_par_opp_100（E_opp 加 flow>0 过滤）",
                  ok2, f"全等={ok2}  Σ={int(d['n_E_opp_flow'].sum())} vs {int(bb['n_par_opp_100'].sum())}"])
    nested_ok = bool((d["n_E_opp"] >= d["n_E_opp_flow"]).all()
                     and (d["n_E_opp_noflow"] == d["n_E_opp"] - d["n_E_opp_flow"]).all()
                     and (d["n_E_opp_flow"].sum() > 0))
    gates.append(["G-O1-7 口径嵌套自洽：E_opp ⊇ 有流子集，差集 = 对向 MAJOR 无流边",
                  nested_ok,
                  f"Σ|E_opp|={int(d['n_E_opp'].sum())}  Σ有流={int(d['n_E_opp_flow'].sum())}"
                  f"  Σ无流={int(d['n_E_opp_noflow'].sum())}"])

    # ---------- G-O1-3：匹配边方向一致（重算）----------
    n_mo = int(bbp["n_match_opp"].sum())
    n_matched = int(bbp["n_matched"].sum())
    gates.append(["G-O1-3 匹配边方向一致（反向 = 0）",
                  bool(n_mo == 0 and n_matched == 152),
                  f"匹配边 {n_matched} 条，反向 {n_mo} 条"])

    # ---------- G-O1-4：Q0 ⊇ B(b)-P 孪生节 ----------
    twin_sec = set(bbp.loc[bbp["twin_exist"] > 0, "lta_linkid"])
    q0_sec = set(d.loc[d["Q_class"] == Q0, "lta_linkid"])
    gates.append(["G-O1-4 Q0 覆盖 B(b)-P 的孪生节（E_opp 放宽 ⇒ 只多不少）",
                  bool(twin_sec <= q0_sec),
                  f"P 孪生 {len(twin_sec)} 节 / Q0 {len(q0_sec)} 节；"
                  f"差集 = {sorted(q0_sec - twin_sec)[:6]}"])

    # ---------- G-O1-5：拓扑方向判据非退化 ----------
    tot_c = int(d["n_comp"].sum())
    tot_dir = int(d["n_directed"].sum())
    gates.append(["G-O1-5 拓扑方向判据非退化（directed_path 与 sum 两类都出现）",
                  bool(0 < tot_dir < tot_c),
                  f"分量 {tot_c} 个：directed_path {tot_dir} / sum {tot_c - tot_dir}"])

    # ---------- G-O1-6：三类非退化 ----------
    qc = d["Q_class"].value_counts().to_dict()
    gates.append(["G-O1-6 对层三类均非空（非退化）",
                  all(qc.get(k, 0) > 0 for k in (Q0, Q1, Q2)),
                  f"Q0={qc.get(Q0,0)} Q1={qc.get(Q1,0)} Q2={qc.get(Q2,0)}"])

    # ---------- 负例（4）----------
    def sig(dfx):
        w = dfx.dropna(subset=["r_pair"])
        return (int(dfx["n_E_opp"].sum()),
                int((dfx["Q_class"] == Q0).sum()),
                int((dfx["Q_class"] == Q1).sum()),
                int((dfx["Q_class"] == Q2).sum()),
                round(float((w["r_pair"] * w["obs_8_9"]).sum() / w["obs_8_9"].sum()), 6))

    def run_pert(**kw):
        rr = []
        for sid in target:
            r = scan_section(G, flow, bear_e, is_major, rev, geo, gl, sec_edges,
                             sid, obs_map, kw.get("R", R0), kw.get("DIR_OK", DIR0),
                             kw.get("use_local_crs", False), kw.get("force_sum", False))
            rr.append(r)
        return pd.DataFrame(rr)

    s0 = sig(d)
    neg = []
    for nmx, kw in [("N1 DIR_OK 30°→180°（取消方向约束）", dict(DIR_OK=180.0)),
                    ("N2 R 100 m→3000 m", dict(R=3000.0)),
                    ("N3 断面坐标改用 lta_section_geometry().mx/my（非同源）", dict(use_local_crs=True)),
                    ("N4 代表值退化为全 sum（取消 directed_path 的 median）", dict(force_sum=True))]:
        sn = sig(run_pert(**kw))
        neg.append({"neg": nmx, "fired": bool(sn != s0), "sig_base": s0, "sig_pert": sn})
    gates.append(["G-O1-N 负例 4/4 fired（非同构扰动）",
                  all(x["fired"] for x in neg),
                  "；".join(f"{x['neg'][:2]}{'✓' if x['fired'] else '✗'}" for x in neg)])

    # ---------- G-O1-8：确定性 AST 自检 ----------
    src = Path(__file__).read_text(encoding="utf-8")
    tree = ast.parse(src)
    bad = []
    for nd in ast.walk(tree):
        if isinstance(nd, ast.Attribute) and nd.attr in {"random", "shuffle", "rand", "randn", "randint"}:
            bad.append(f"attr:{nd.attr}")
        if isinstance(nd, ast.Name) and nd.id == "random":
            bad.append("name:random")
    gates.append(["G-O1-8 确定性自检（AST 无随机源 + 卡片 38 行）",
                  bool(len(bad) == 0 and len(d) == 38),
                  f"随机源 {len(bad)} 个；卡片 {len(d)} 行"])

    # ---------- 汇总 ----------
    def share(dfx):
        w = dfx.dropna(subset=["r_pair"])
        tot = float(w["obs_8_9"].sum())
        cons = float(w.loc[w["pair_consistent"], "obs_8_9"].sum())
        return dict(n=int(len(dfx)), obs=float(dfx["obs_8_9"].sum()),
                    n_consistent=int(w["pair_consistent"].sum()),
                    obs_share_consistent=(cons / tot if tot > 0 else float("nan")))

    summ = {"target_38": share(d),
            "census_576": share(cen),
            "by_bb_class": {c: share(d[d["class_bb"] == c])
                            for c in ["B1_SAME_DIR_PARALLEL", "B2_OPPOSITE_ONLY",
                                      "B3_NO_PARALLEL_FLOW"] if (d["class_bb"] == c).any()},
            "Q_counts_target": {k: int(v) for k, v in qc.items()},
            "Q_counts_census": {k: int(v) for k, v in cen["Q_class"].value_counts().items()},
            "r_pair_quantiles": {q: float(np.nanquantile(d["r_pair"], p))
                                 for q, p in [("p10", .10), ("p25", .25), ("p50", .50),
                                              ("p75", .75), ("p90", .90)]},
            "r_pair_vs_r_par_sum_opp": {
                "median_r_pair": float(np.nanmedian(d["r_pair"])),
                "median_r_par_sum_opp": float(np.nanmedian(d["r_par_sum_opp"])),
                "n_improved_to_band": int(d["pair_consistent"].sum()),
                "n_already_band_by_par_sum": int(((d["r_par_sum_opp"] >= STEP)
                                                  & (d["r_par_sum_opp"] <= STEP_HI)).sum()),
                "changed_by_chain_agg": 0}}
    rec["summary"] = summ
    rec["negatives"] = neg
    rec["gates"] = [{"gate": g, "pass": bool(p), "measured": m} for g, p, m in gates]
    rec["n_fail"] = int(sum(1 for _, p, _ in gates if not p))
    rec["verdict"] = ("CARRIAGEWAY_PAIR_AUDIT_READY" if rec["n_fail"] == 0
                      else "CARRIAGEWAY_PAIR_AUDIT_BLOCKED")
    rec["elapsed_s"] = round(time.time() - t0, 1)

    d.to_csv(OUT / "o1_pair_cards_7_9io1.csv", index=False, encoding="utf-8-sig")
    cen.to_csv(OUT / "o1_pair_census_7_9io1.csv", index=False, encoding="utf-8-sig")
    (OUT / "o1_pair_summary_7_9io1.json").write_text(
        json.dumps(rec, ensure_ascii=False, indent=1), encoding="utf-8")

    print("\n===== GATES =====")
    for g, p, m in gates:
        print(f"  [{'PASS' if p else 'FAIL'}] {g}\n          | {m}")
    print("\n===== 对层分类（38 节目标集）=====")
    print(d.groupby("Q_class").agg(n=("lta_linkid", "size"),
                                   obs=("obs_8_9", "sum"),
                                   r_pair_med=("r_pair", "median")).to_string())
    print("\n===== B(b) 三类 × 对层分类 =====")
    print(pd.crosstab(d["class_bb"], d["Q_class"]).to_string())
    print("\n===== r_pair 分位 =====")
    print({k: round(v, 4) for k, v in summ["r_pair_quantiles"].items()})
    print(f"  PAIR_CONSISTENT：target {summ['target_38']['obs_share_consistent']:.4f} "
          f"/ census {summ['census_576']['obs_share_consistent']:.4f}")
    print(f"\nVERDICT={rec['verdict']}  n_fail={rec['n_fail']}  {rec['elapsed_s']}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
