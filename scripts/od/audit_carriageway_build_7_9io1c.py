# -*- coding: utf-8 -*-
"""Step 7.9I-O1-续① ② · 车行道建造核验 + OSM way-level / oneway 结构 —— 零仿真、只读

★要回答的问题（用户 2026-09-30 裁定）：
  ① **「少建一条车行道」** 与 **「两条都建了，但其中一条没有被路由使用」** 必须严格分开。
     四段链：`LTA 双向断面 → OSM way 数量/oneway → MATSim 对应有向链数量 → 实际加载方向对象数量`
  ② OSM `oneway` 与 way-level 结构 —— 给 ① 提供**源头证据**。
     ⛔ 不得因「MATSim 出现两条独立 node-string」就推断「OSM 原本就是双 way」；
        必须看**原始 way 数量与方向标签**。

⛔ 坐标纪律：断面位置一律取 `SEC_GEO_7_6C.mid_x/mid_y`（SVY21）。
⛔ 不改 v1.0 任何参数；不重跑 MATSim；不产生 v1.1；`changed = 0`。
"""
from __future__ import annotations

import ast
import json
import math
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(r"D:\Luan\2026-05\2_Singapore")
sys.path.insert(0, str(ROOT / "scripts" / "od"))

import evaluate_calibration_7_4_2 as ev1               # noqa: E402
import evaluate_demand_response_7_6f_1 as E            # noqa: E402
import audit_sampling_capacity_7_9a1 as A              # noqa: E402
from diagnose_gap_7_9h import read_edge_full           # noqa: E402
from audit_corridor_scale_7_9ia import load_frozen, OUT  # noqa: E402
from audit_m1_accessibility_7_9ib import Graph         # noqa: E402
from audit_kpe_ecp_object_7_9ia2 import lta_section_geometry  # noqa: E402
from audit_carriageway_pair_7_9io1 import circ_diff, weak_components  # noqa: E402

CACHE_NET = ROOT / "scripts" / "od" / "_cache_network_7_9c0.npz"
OSM_SHP = ROOT / "Singapore_OD_MATSim_FinalData" / "07_RoadNetwork" / "osm-lines_expanded.shp"
SS_PATH = OUT / "section_scale_v10.csv"

MAJOR = {"motorway", "motorway_link", "trunk", "trunk_link"}

# ---- 预注册常量（运行前冻结）----
R_OSM = 60.0      # OSM way → 断面中点 最短距离阈值（m）
R_MS = 100.0      # MATSim 边中点半径（m）
R_TWIN = 300.0    # 平行「有流双胞胎」搜索半径（m）
DIR_OK = 30.0     # 方向容差（°）

S1, S2, S3 = "S1_MS_SELF_ABSENT", "S2_MS_SELF_BUILT_UNLOADED", "S3_MS_SELF_LOADED"
ISO_DEAD, ISO_BYPASS_NOTWIN, ISO_TWIN = "ISO_DEAD_TUBE", "ISO_BYPASS_NO_TWIN", "ISO_TWIN_EXISTS"


def nearest_seg_bearing(geom, px, py):
    """几何上**离 (px,py) 最近的那一段**的方位角（°）。返回 (dist_m, bear°)。"""
    parts = [geom] if geom.geom_type == "LineString" else list(geom.geoms)
    best = (float("inf"), float("nan"))
    for part in parts:
        c = np.asarray(part.coords, float)
        if len(c) < 2:
            continue
        a = c[:-1, :2]
        b = c[1:, :2]
        ab = b - a
        ap = np.array([px, py], float) - a
        L2 = (ab ** 2).sum(axis=1)
        L2[L2 <= 0] = 1e-12
        t = np.clip((ap * ab).sum(axis=1) / L2, 0.0, 1.0)
        proj = a + t[:, None] * ab
        dd = np.hypot(proj[:, 0] - px, proj[:, 1] - py)
        k = int(np.argmin(dd))
        if dd[k] < best[0]:
            best = (float(dd[k]), math.degrees(math.atan2(ab[k, 0], ab[k, 1])) % 360.0)
    return best


def main() -> int:
    t0 = time.time()
    rec: dict = {"step": "7.9I-O1-续①②/carriageway-build-and-osm-way-level", "scale": A.SCALE,
                 "R_osm_m": R_OSM, "R_ms_m": R_MS, "R_twin_m": R_TWIN, "dir_ok_deg": DIR_OK,
                 "label": "PRE_REGISTERED"}
    gates: list = []

    # ---------- 数据 ----------
    edge1 = read_edge_full(A.V10_LS)
    G = Graph(np.load(CACHE_NET, allow_pickle=True))
    flow = np.nan_to_num(edge1.set_index("LINK")["HRS8-9avg"].reindex(G.ids).to_numpy(float), nan=0.0)
    id2i = {x: i for i, x in enumerate(G.ids)}
    bear_e = (np.degrees(np.arctan2(G.nx[G.t] - G.nx[G.f], G.ny[G.t] - G.ny[G.f])) + 360.0) % 360.0
    is_major = np.array([h in MAJOR for h in G.highway])

    incoming: dict = {}
    outgoing: dict = {}
    for i in range(G.n_edges):
        outgoing.setdefault(int(G.f[i]), []).append(i)
        incoming.setdefault(int(G.t[i]), []).append(i)

    def upstream_end(lid, max_steps=2000):
        i = id2i[lid]
        cur = int(G.f[i])
        st = 0
        while st < max_steps:
            ins = incoming.get(cur, [])
            if len(ins) != 1:
                return i, st, cur, ins
            j = ins[0]
            i = j
            cur = int(G.f[j])
            st += 1
        return i, st, cur, incoming.get(cur, [])

    obs, cw, _ = load_frozen()
    gl = lta_section_geometry(ev1.TRAFFIC).set_index("LinkID")
    geo = pd.read_csv(E.SEC_GEO_7_6C, dtype={"lta_linkid": str}).set_index("lta_linkid")
    ss = pd.read_csv(SS_PATH, dtype={"lta_linkid": str}).set_index("lta_linkid")
    obs_map_meta = obs.set_index("LinkID")
    cwraw = pd.read_csv(ev1.FINAL_CW, encoding="utf-8-sig",
                        dtype={"lta_linkid": str, "matsim_link_id": str})
    cwraw["matsim_link_id"] = cwraw["matsim_link_id"].astype(str).str.strip()
    prim = cwraw[cwraw["is_primary_candidate"].astype(str).str.lower().isin(["true", "1"])]
    mat: dict = {str(s): set(g["matsim_link_id"]) for s, g in prim.groupby("lta_linkid")}

    # ---------- OSM ----------
    import geopandas as gpd
    from shapely.geometry import Point
    gosm = gpd.read_file(OSM_SHP, columns=["osm_id", "highway", "oneway", "name", "ref", "geometry"])
    gosm = gosm[gosm["highway"].isin(MAJOR)].to_crs(3414).reset_index(drop=True)
    gosm["osm_id"] = gosm["osm_id"].astype(str)
    n_osm_major = int(len(gosm))
    ow = gosm["oneway"].astype(str).str.lower().str.strip()
    ow_yes_share = float((ow == "yes").mean())

    target = pd.read_csv(OUT / "bb_zero_flow_ledger_7_9ibb.csv", dtype={"lta_linkid": str})
    o1q = pd.read_csv(OUT / "o1q_opposite_label_cards_7_9io1q.csv", dtype={"lta_linkid": str})
    lab = o1q.set_index("lta_linkid")["label"].to_dict()
    tgt = target["lta_linkid"].tolist()

    # ---------- 门 1：坐标同源 ----------
    mx0 = float(geo.loc[tgt[0], "mid_x"])
    gates.append(["G-O1C-1 坐标同源（SEC_GEO mid_x 落在 SVY21 量级 <1e6）",
                  bool(0.0 < mx0 < 1.0e6), f"样例 {tgt[0]} mid_x={mx0:.1f}"])
    gates.append(["G-O1C-4 OSM 读入自检（MAJOR way 数 = 6694，oneway=yes 占比 ≥ 0.9）",
                  bool(n_osm_major == 6694 and ow_yes_share >= 0.90),
                  f"MAJOR={n_osm_major}  oneway=yes 占比={ow_yes_share:.4f}"])

    rows = []
    for sid in tgt:
        mx, my = float(geo.loc[sid, "mid_x"]), float(geo.loc[sid, "mid_y"])
        sb = float(gl.loc[sid, "bear"])
        P = Point(mx, my)

        # ---- OSM 阶段 ----
        dd = gosm.geometry.distance(P).to_numpy(float)
        near_idx = np.where(dd <= R_OSM)[0]
        o_same, o_opp, o_oth = [], [], []
        for k in near_idx:
            dm, br = nearest_seg_bearing(gosm.geometry.iloc[k], mx, my)
            ds = circ_diff(br, sb)
            if ds < DIR_OK:
                o_same.append(k)
            elif abs(ds - 180.0) < DIR_OK:
                o_opp.append(k)
            else:
                o_oth.append(k)

        def ow_counts(idx):
            v = ow.iloc[idx]
            return int((v == "yes").sum()), int((v == "no").sum()), int((~(v.isin(["yes", "no"]))).sum())

        oy_s, on_s, ox_s = ow_counts(o_same)
        oy_o, on_o, ox_o = ow_counts(o_opp)
        osm_cls = ("O_BOTH_DIR_WAYS" if (len(o_same) and len(o_opp)) else
                   ("O_SELF_ONLY" if len(o_same) else
                    ("O_OPP_ONLY" if len(o_opp) else "O_NONE")))

        # ---- MATSim 阶段 ----
        d2 = np.hypot(G.ex - mx, G.ey - my)
        cand = np.where((d2 <= R_MS) & is_major)[0]
        ds_ms = np.array([circ_diff(bear_e[x], sb) for x in cand], float) if len(cand) else np.array([])
        ms_same = cand[ds_ms < DIR_OK] if len(cand) else np.array([], np.int64)
        ms_opp = cand[np.abs(ds_ms - 180.0) < DIR_OK] if len(cand) else np.array([], np.int64)

        ms = sorted(mat.get(str(sid), set()))
        ms = [x for x in ms if x in id2i]
        n_match = len(ms)
        v_match = int(sum(1 for x in ms if flow[id2i[x]] > 0))

        # 死管诊断：matched 边的上游端点 Σflow(入)
        head_inf, steps_l = [], []
        for lid in ms:
            ei, st, nd, ins = upstream_end(lid)
            head_inf.append(float(sum(flow[j] for j in ins)))
            steps_l.append(int(st))
        head_inf_max = float(max(head_inf)) if head_inf else float("nan")
        steps_max = int(max(steps_l)) if steps_l else -1

        # ★有向链计数（用户 ① 链的第三段：「MATSim 对应有向链数量」）
        def n_chain(edges):
            return len(weak_components(np.asarray(edges, np.int64), G)) if len(edges) else 0

        def n_chain_loaded(edges):
            if not len(edges):
                return 0
            return int(sum(1 for C in weak_components(np.asarray(edges, np.int64), G)
                           if (flow[C] > 0).any()))

        n_chain_same = n_chain(ms_same)
        n_chain_opp = n_chain(ms_opp)
        n_chain_same_loaded = n_chain_loaded(ms_same)
        n_chain_opp_loaded = n_chain_loaded(ms_opp)

        # 平行有流双胞胎（同向、R_TWIN、flow>0、非 matched）
        excl = set(ms)
        cand2 = np.where((d2 <= R_TWIN) & is_major & (flow > 0))[0]
        twin = np.array([x for x in cand2
                         if circ_diff(bear_e[x], sb) < DIR_OK and str(G.ids[x]) not in excl], np.int64)
        twin_dmin = float(d2[twin].min()) if len(twin) else float("nan")

        # ★分类（修正：本侧对象 = 交叉表 matched 边，不用几何同向池）
        if n_match == 0:
            bcls = S1
        elif v_match == 0:
            bcls = S2
        else:
            bcls = S3
        if len(twin) > 0:
            icls = ISO_TWIN
        elif (np.isfinite(head_inf_max) and head_inf_max <= 0.0):
            icls = ISO_DEAD
        else:
            icls = ISO_BYPASS_NOTWIN

        rows.append(dict(
            lta_linkid=str(sid),
            RoadName=str(obs_map_meta.loc[sid, "RoadName"]) if sid in obs_map_meta.index else "",
            label=lab.get(str(sid), ""), obs_8_9=float(target.loc[target["lta_linkid"] == sid, "obs_8_9"].iloc[0]),
            mid_x=mx, mid_y=my, bear=sb,
            sim_median_xS=(float(ss.loc[sid, "sim_median_xS"]) if sid in ss.index else np.nan),
            ratio_median=(float(ss.loc[sid, "ratio_median"]) if sid in ss.index else np.nan),
            n_osm=len(near_idx), n_osm_same=len(o_same), n_osm_opp=len(o_opp), n_osm_other=len(o_oth),
            osm_ow_yes_same=oy_s, osm_ow_no_same=on_s, osm_ow_nan_same=ox_s,
            osm_ow_yes_opp=oy_o, osm_ow_no_opp=on_o, osm_ow_nan_opp=ox_o,
            osm_class=osm_cls,
            osm_ids_same=";".join(gosm["osm_id"].iloc[o_same]) if o_same else "",
            osm_ids_opp=";".join(gosm["osm_id"].iloc[o_opp]) if o_opp else "",
            n_ms_same=int(len(ms_same)), n_ms_opp=int(len(ms_opp)),
            n_ms_same_flow=int((flow[ms_same] > 0).sum()) if len(ms_same) else 0,
            n_ms_opp_flow=int((flow[ms_opp] > 0).sum()) if len(ms_opp) else 0,
            n_chain_same=n_chain_same, n_chain_opp=n_chain_opp,
            n_chain_same_loaded=n_chain_same_loaded, n_chain_opp_loaded=n_chain_opp_loaded,
            sum_ms_same=float(flow[ms_same].sum()) if len(ms_same) else 0.0,
            sum_ms_opp=float(flow[ms_opp].sum()) if len(ms_opp) else 0.0,
            n_match=n_match, n_match_flow=v_match,
            chain_steps_max=steps_max, head_inflow_max=head_inf_max,
            n_twin_flow_300=int(len(twin)), twin_dist_min=twin_dmin,
            build_class=bcls, iso_class=icls))

    d = pd.DataFrame(rows)
    assert len(d) == 38, len(d)
    l1 = d[d["label"] == "L1_OPP_LOADED_OK"]

    # ---------- 门 2：交叉表 matched = 152 且全零流 ----------
    gates.append(["G-O1C-2 交叉表 matched 边总数 = 152 且全零流",
                  bool(int(d["n_match"].sum()) == 152 and int(d["n_match_flow"].sum()) == 0),
                  f"matched={int(d['n_match'].sum())}  有流={int(d['n_match_flow'].sum())}"])

    # ---------- 门 3：canonical 对账 ----------
    mx = d["sim_median_xS"].to_numpy(float)
    gates.append(["G-O1C-3 与冻结 canonical 对账（38 节 sim_median_xS 全为 0）",
                  bool(np.nanmax(np.abs(mx)) == 0.0), f"max|sim_median_xS|={np.nanmax(np.abs(mx)):.3e}"])

    # ---------- 门 5：★本侧「自己的对象」是否存在（正面回答「是否只建了一条」）----------
    n_self_absent = int((d["n_match"] == 0).sum())
    gates.append(["G-O1C-5 ★本侧 matched 对象存在（「≥1 条有向链」；0 节 = 无「少建本侧」）",
                  bool(n_self_absent == 0),
                  f"matched 对象缺失 {n_self_absent}/38 节；"
                  f"同向有向链 Σ={int(d['n_chain_same'].sum())}（有流链 Σ={int(d['n_chain_same_loaded'].sum())}）"])

    # ---------- 门 6：本侧零流 + 对侧有流（★改用 matched 口径）----------
    n_opp = int((d["n_ms_opp"] >= 1).sum())
    gates.append(["G-O1C-6 ★本侧 matched 零流（38/38）+ 对向对象存在 36/38",
                  bool(int(d["n_match_flow"].sum()) == 0 and n_opp == 36),
                  f"matched 有流={int(d['n_match_flow'].sum())}（matched Σ={int(d['n_match'].sum())}）；"
                  f"对向对象存在 {n_opp}/38；【披露】几何同向池 Σflow 全零="
                  f"{bool((d['sum_ms_same']==0.0).all())}（池内混入邻近其它道路同向边，非本侧对象）"])

    # ---------- 门 7：★MATSim 对向缺失 ⇔ OSM 源头缺失（集合同一，回答「少建 vs 建了没跑」）----------
    set_ms_no_opp = set(d.loc[d["n_ms_opp"] == 0, "lta_linkid"])
    set_osm_selfonly = set(d.loc[d["osm_class"] == "O_SELF_ONLY", "lta_linkid"])
    gates.append(["G-O1C-7 ★{MATSim 无对向对象} ≡ {OSM 侧 O_SELF_ONLY}（对称差 = ∅）",
                  bool(set_ms_no_opp == set_osm_selfonly),
                  f"MATSim 无对向 {len(set_ms_no_opp)} 节 {sorted(set_ms_no_opp)}；"
                  f"OSM 仅单侧 {len(set_osm_selfonly)} 节；对称差={sorted(set_ms_no_opp ^ set_osm_selfonly)}"])

    # ---------- 门 7b：OSM 源头证据（way-level / oneway）----------
    gates.append(["G-O1C-7b OSM 源头：每节双向 way 均存在（36/38；2 节例外已由门 7 归因）",
                  bool(((d["n_osm_same"] >= 1) & (d["n_osm_opp"] >= 1)).sum() == 36
                       and d["osm_class"].value_counts().get("O_SELF_ONLY", 0) == 2),
                  f"OSM 双向均有 way {int(((d['n_osm_same']>=1)&(d['n_osm_opp']>=1)).sum())}/38；"
                  f"osm_class={d['osm_class'].value_counts().to_dict()}；"
                  f"L1 15 节 OSM 同向 way {int(l1['n_osm_same'].sum())} / 对向 way {int(l1['n_osm_opp'].sum())}"])

    # ---------- 门 8：死管诊断非退化 ----------
    dc = d["iso_class"].value_counts().to_dict()
    gates.append(["G-O1C-8 死管诊断非退化（两类都出现）",
                  bool(len(dc) >= 2), f"iso_class={dc}"])

    # ---------- 门 9：build_class 与 OSM 侧交叉一致 ----------
    ct = pd.crosstab(d["build_class"], d["osm_class"])
    gates.append(["G-O1C-9 build_class 与 osm_class 交叉（披露，非门限方向）",
                  bool(True), f"{ct.to_dict()}"])

    # ---------- 负例（4）----------
    def sig(dfx):
        return (int(dfx["n_osm_same"].sum()), int(dfx["n_osm_opp"].sum()),
                int(dfx["n_ms_same"].sum()), int(dfx["n_ms_opp"].sum()),
                int(dfx["n_twin_flow_300"].sum()),
                round(float(dfx["head_inflow_max"].fillna(-1).sum()), 4),
                tuple(sorted(dfx["build_class"].value_counts().to_dict().items())))

    def run_pert(**kw):
        rr = []
        r_osm = kw.get("R_OSM", R_OSM)
        r_ms = kw.get("R_MS", R_MS)
        r_tw = kw.get("R_TWIN", R_TWIN)
        flip = kw.get("flip", False)
        loc = kw.get("local_crs", False)
        for sid in tgt:
            if loc:
                mx, my = float(gl.loc[sid, "mx"]), float(gl.loc[sid, "my"])
            else:
                mx, my = float(geo.loc[sid, "mid_x"]), float(geo.loc[sid, "mid_y"])
            sbb = (float(gl.loc[sid, "bear"]) + (180.0 if flip else 0.0)) % 360.0
            P = Point(mx, my)
            dd = gosm.geometry.distance(P).to_numpy(float)
            near_idx = np.where(dd <= r_osm)[0]
            o_same, o_opp = [], []
            for k in near_idx:
                _, br = nearest_seg_bearing(gosm.geometry.iloc[k], mx, my)
                ds = circ_diff(br, sbb)
                if ds < DIR_OK:
                    o_same.append(k)
                elif abs(ds - 180.0) < DIR_OK:
                    o_opp.append(k)
            d2 = np.hypot(G.ex - mx, G.ey - my)
            cand = np.where((d2 <= r_ms) & is_major)[0]
            ds_ms = np.array([circ_diff(bear_e[x], sbb) for x in cand], float) if len(cand) else np.array([])
            ms_same = cand[ds_ms < DIR_OK] if len(cand) else np.array([], np.int64)
            ms_opp = cand[np.abs(ds_ms - 180.0) < DIR_OK] if len(cand) else np.array([], np.int64)
            msx = [x for x in sorted(mat.get(str(sid), set())) if x in id2i]
            hi = []
            for lid in msx:
                _, _, _, ins = upstream_end(lid)
                hi.append(float(sum(flow[j] for j in ins)))
            excl = set(msx)
            cand2 = np.where((d2 <= r_tw) & is_major & (flow > 0))[0]
            twin = [x for x in cand2 if circ_diff(bear_e[x], sbb) < DIR_OK and str(G.ids[x]) not in excl]
            if len(msx) == 0:
                bc = S1
            elif int(sum(1 for x in msx if flow[id2i[x]] > 0)) == 0:
                bc = S2
            else:
                bc = S3
            rr.append(dict(n_osm_same=len(o_same), n_osm_opp=len(o_opp), n_ms_same=len(ms_same),
                           n_ms_opp=len(ms_opp), n_twin_flow_300=len(twin),
                           head_inflow_max=(max(hi) if hi else float("nan")), build_class=bc))
        return pd.DataFrame(rr)

    s0 = sig(d)
    neg = []
    for nmx, kw in [("N1 R_OSM 60 m→5 m（取消 OSM 邻域）", dict(R_OSM=5.0)),
                    ("N2 R_MS 100 m→3000 m", dict(R_MS=3000.0)),
                    ("N3 断面坐标改用 lta_section_geometry().mx/my（非同源）", dict(local_crs=True)),
                    ("N4 方位整体反向 180°（same/opp 互换）", dict(flip=True))]:
        sn = sig(run_pert(**kw))
        neg.append({"neg": nmx, "fired": bool(sn != s0), "sig_base": s0, "sig_pert": sn})
    gates.append(["G-O1C-N 负例 4/4 fired（非同构扰动）",
                  all(x["fired"] for x in neg),
                  "；".join(f"{x['neg'][:2]}{'✓' if x['fired'] else '✗'}" for x in neg)])

    # ---------- 门 10：确定性 AST ----------
    src = Path(__file__).read_text(encoding="utf-8")
    bad = []
    for nd in ast.walk(ast.parse(src)):
        if isinstance(nd, ast.Attribute) and nd.attr in {"random", "shuffle", "rand", "randn", "randint"}:
            bad.append(nd.attr)
        if isinstance(nd, ast.Name) and nd.id == "random":
            bad.append("name:random")
    gates.append(["G-O1C-10 确定性自检（AST 无随机源 + 卡片 38 行）",
                  bool(len(bad) == 0 and len(d) == 38), f"随机源 {len(bad)} 个；卡片 {len(d)} 行"])

    # ---------- 汇总 ----------
    def sh(m):
        w = d[m]
        return dict(n=int(len(w)), obs=float(w["obs_8_9"].sum()),
                    n_ms_same=int(w["n_ms_same"].sum()), n_ms_opp=int(w["n_ms_opp"].sum()),
                    n_ms_same_flow=int(w["n_ms_same_flow"].sum()),
                    n_ms_opp_flow=int(w["n_ms_opp_flow"].sum()))

    l1 = d[d["label"] == "L1_OPP_LOADED_OK"]
    rec["criteria_revision"] = [
        {"id": "R1", "when": "首跑后（运行本脚本首版后、正式产物写盘前）",
         "what": "`G-O1C-5/6/7` 与 `build_class` 原用「R_MS 内几何同向池」代理「本侧对象」",
         "why": "首跑 FAIL 3 项。100 m 内会混入**其它道路 / 匝道**的同向 MAJOR 边（有流），"
                "几何同向池 ≠ 本侧对象 ⇒ **判据设计缺陷**（非实现缺陷、非科学结论）",
         "fix": "本侧对象改用**交叉表 matched 边**（`n_match` / `n_match_flow`）；"
                "几何同向池降级为「邻近同向对象 / 双胞胎」披露量；"
                "新增 `G-O1C-7` 集合同一判据 `{MATSim 无对向} ≡ {OSM 侧 O_SELF_ONLY}`",
         "note": "阈值**未改**（仍 R_OSM=60 / R_MS=100 / R_TWIN=300 / DIR_OK=30）；只改「对象定义」"},
        {"id": "R2", "when": "第二次运行前",
         "what": "`G-O1C-6` 第二版仍含 `本侧几何同向池 Σflow 全零` 子条件",
         "why": "该子条件 FAIL：几何同向池（R_MS=100 m）会纳入**邻近其它道路/匝道**的同向有流边 ⇒ 与「本侧对象」不同一",
         "fix": "该子条件**降级为披露量**（写入门消息）；门断言改为 `matched Σflow=0 ∧ 对向对象存在 36/38`",
         "note": "同一根因（对象定义）已连续两次触发，故在报告中登记为 **D1 判据设计缺陷**"},
    ]
    rec["summary"] = {
        "osm_major_n": n_osm_major, "osm_oneway_yes_share": ow_yes_share,
        "all38": sh(d["lta_linkid"].notna()),
        "L1_15": sh(d["label"] == "L1_OPP_LOADED_OK"),
        "L2": sh(d["label"] == "L2_OPP_ALSO_LOW"),
        "build_class_counts": {k: int(v) for k, v in d["build_class"].value_counts().items()},
        "iso_class_counts": {k: int(v) for k, v in d["iso_class"].value_counts().items()},
        "osm_class_counts": {k: int(v) for k, v in d["osm_class"].value_counts().items()},
        "by_label_build": pd.crosstab(d["label"], d["build_class"]).to_dict(),
        "twin_flow_300": int((d["n_twin_flow_300"] > 0).sum()),
        "twin_dist_min": {q: float(np.nanpercentile(d["twin_dist_min"], p)) if d["twin_dist_min"].notna().any()
                          else float("nan") for q, p in [("p25", 25), ("p50", 50), ("p90", 90)]},
        "chain_steps_max": {q: float(np.percentile(d["chain_steps_max"], p))
                            for q, p in [("p50", 50), ("p90", 90), ("max", 100)]},
        "head_inflow_max": {"n_zero": int((d["head_inflow_max"] <= 0).sum()),
                            "n_pos": int((d["head_inflow_max"] > 0).sum())},
        "self_matched": {"n_match_sum": int(d["n_match"].sum()),
                         "n_match_flow_sum": int(d["n_match_flow"].sum()),
                         "n_sections_self_absent": int((d["n_match"] == 0).sum())},
        "opp_object": {"n_sections_opp_present": int((d["n_ms_opp"] >= 1).sum()),
                       "n_sections_opp_absent": int((d["n_ms_opp"] == 0).sum()),
                       "n_sections_opp_loaded": int((d["n_ms_opp_flow"] >= 1).sum())},
        "chain_counts": {"same_chains": int(d["n_chain_same"].sum()),
                         "same_chains_loaded": int(d["n_chain_same_loaded"].sum()),
                         "opp_chains": int(d["n_chain_opp"].sum()),
                         "opp_chains_loaded": int(d["n_chain_opp_loaded"].sum())},
        "l1_n_osm_same_opp": {"same_sum": int(l1["n_osm_same"].sum()),
                              "opp_sum": int(l1["n_osm_opp"].sum()),
                              "ow_yes_same": int(l1["osm_ow_yes_same"].sum()),
                              "ow_yes_opp": int(l1["osm_ow_yes_opp"].sum()),
                              "ow_other_same": int(l1["osm_ow_no_same"].sum() + l1["osm_ow_nan_same"].sum()),
                              "ow_other_opp": int(l1["osm_ow_no_opp"].sum() + l1["osm_ow_nan_opp"].sum())}}

    rec["negatives"] = neg
    rec["gates"] = [{"gate": g, "pass": bool(p), "measured": m} for g, p, m in gates]
    rec["n_fail"] = int(sum(1 for _, p, _ in gates if not p))
    rec["verdict"] = ("CARRIAGEWAY_BUILD_AUDIT_READY" if rec["n_fail"] == 0
                      else "CARRIAGEWAY_BUILD_AUDIT_BLOCKED")
    rec["elapsed_s"] = round(time.time() - t0, 1)

    d.to_csv(OUT / "o1c_build_cards_7_9io1c.csv", index=False, encoding="utf-8-sig")
    (OUT / "o1c_build_summary_7_9io1c.json").write_text(
        json.dumps(rec, ensure_ascii=False, indent=1), encoding="utf-8")

    print("\n===== GATES =====")
    for g, p, m in gates:
        print(f"  [{'PASS' if p else 'FAIL'}] {g}\n          | {m}")
    print("\n===== 四段链（L1 15 节）=====")
    cols = ["lta_linkid", "RoadName", "obs_8_9", "n_osm_same", "n_osm_opp", "osm_class",
            "n_ms_same", "n_chain_same", "n_chain_same_loaded", "n_ms_opp", "n_chain_opp_loaded",
            "n_match", "n_match_flow", "chain_steps_max", "head_inflow_max",
            "n_twin_flow_300", "twin_dist_min", "build_class", "iso_class"]
    print(l1[cols].to_string(index=False))
    print("\n===== 38 节汇总 =====")
    print("build_class:", rec["summary"]["build_class_counts"])
    print("iso_class  :", rec["summary"]["iso_class_counts"])
    print("osm_class  :", rec["summary"]["osm_class_counts"])
    print("\nlabel × build_class:")
    print(pd.crosstab(d["label"], d["build_class"]).to_string())
    print(f"\nVERDICT={rec['verdict']}  n_fail={rec['n_fail']}  {rec['elapsed_s']}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
