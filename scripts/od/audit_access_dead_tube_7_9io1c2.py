# -*- coding: utf-8 -*-
"""Step 7.9I-O1-续② · 死管链「接入（access）审计」—— 零仿真、只读

★正式问题（用户 2026-09-30 裁定）：
  把 18 个 `ISO_DEAD_TUBE` 拆成可证伪分支
    A 源头无接入 / B OSM 有接入但转换丢失 / C MATSim 无入口边
  ＋（因 A/B/C 预期为空）已预注册的细化轴 D/E（本地同向有无活流）。

★B 类判据（严格版）：OSM link way 的**顶点覆盖率** `cov_frac >= COV_MIN=0.5`
  ⇒ 已转换；`OSM_link_n>0 ∧ 已转换==0` ⇒ 转换丢失。

⛔ 坐标纪律：断面位置一律取 `SEC_GEO_7_6C.mid_x/mid_y`（SVY21）。
⛔ 不改 v1.0；不跑 MATSim；不碰 signals/trafficDynamics/speedFactor；不产生 v1.1；`changed = 0`。
⛔ `ISO_TWIN_EXISTS` 18 节**只做证据整理**，不做「同一物理车行道」裁定。
"""
from __future__ import annotations

import ast
import json
import math
import sys
import time
from collections import deque
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
from audit_carriageway_pair_7_9io1 import circ_diff    # noqa: E402

CACHE_NET = ROOT / "scripts" / "od" / "_cache_network_7_9c0.npz"
OSM_SHP = ROOT / "Singapore_OD_MATSim_FinalData" / "07_RoadNetwork" / "osm-lines_expanded.shp"

MAJOR = {"motorway", "motorway_link", "trunk", "trunk_link"}
LINK_TYPES = {"motorway_link", "trunk_link", "primary_link", "secondary_link", "tertiary_link"}
# ★可驾驶「接入对象」类型（⛔ 排除 footway/cycleway/path/steps/pedestrian/corridor/service/
#    residential/track/construction/proposed/living_street/raceway/elevator）
ACCESS_TYPES = {"motorway", "motorway_link", "trunk", "trunk_link",
                "primary", "primary_link", "secondary", "secondary_link",
                "tertiary", "tertiary_link", "unclassified"}

# ---- 预注册常量（见 PREREG_7_9I_O1CONT2.md，运行前冻结）----
R_ACC = 60.0
R_MS2 = 50.0
R_SNAP = 30.0
DIR_OK = 30.0
COV_MIN = 0.50
SAMPLE_M = 10.0
MAX_STEPS = 2000
CAP_BFS = 4000

A_C, B_C, C_C, D_C, E_C = ("A_NO_OSM_FEEDER", "B_LINK_UNCONVERTED", "C_NO_MATSIM_IN_EDGE",
                           "D_NO_LOCAL_LIVE_SAME_DIR", "E_LOCAL_LIVE_SAME_DIR_EXISTS")
CLASSES = {A_C, B_C, C_C, D_C, E_C}


def nearest_seg_bearing(geom, px, py):
    """最近那一段的方位角（°）与最近投影点。返回 (dist_m, bear°, (proj_x, proj_y))。"""
    parts = [geom] if geom.geom_type == "LineString" else list(geom.geoms)
    best = (float("inf"), float("nan"), (float("nan"), float("nan")))
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
            best = (float(dd[k]), math.degrees(math.atan2(ab[k, 0], ab[k, 1])) % 360.0,
                    (float(proj[k, 0]), float(proj[k, 1])))
    return best


def sample_points(geom, step=SAMPLE_M):
    """沿几何每 step 米重采样顶点。"""
    c = np.asarray(geom.coords, float)
    if len(c) < 2:
        return c
    seg = np.hypot(np.diff(c[:, 0]), np.diff(c[:, 1]))
    cum = np.concatenate([[0.0], np.cumsum(seg)])
    if cum[-1] <= 0:
        return c[:1]
    dots = np.arange(0.0, cum[-1] + 1e-9, step)
    idx = np.clip(np.searchsorted(cum, dots) - 1, 0, len(c) - 2)
    tt = (dots - cum[idx]) / np.maximum(seg[idx], 1e-9)
    return c[idx] * (1 - tt[:, None]) + c[idx + 1] * tt[:, None]


def main() -> int:
    t0 = time.time()
    rec: dict = {"step": "7.9I-O1-续②/dead-tube-access-audit", "scale": A.SCALE,
                 "R_acc_m": R_ACC, "R_ms2_m": R_MS2, "R_snap_m": R_SNAP, "dir_ok_deg": DIR_OK,
                 "cov_min": COV_MIN, "sample_m": SAMPLE_M, "label": "RUN_PRE_REGISTERED_FROZEN"}
    gates: list = []

    # ---------- 数据 ----------
    edge1 = read_edge_full(A.V10_LS)
    G = Graph(np.load(CACHE_NET, allow_pickle=True))
    flow = np.nan_to_num(edge1.set_index("LINK")["HRS8-9avg"].reindex(G.ids).to_numpy(float), nan=0.0)
    id2i = {x: i for i, x in enumerate(G.ids)}
    bear_e = (np.degrees(np.arctan2(G.nx[G.t] - G.nx[G.f], G.ny[G.t] - G.ny[G.f])) + 360.0) % 360.0
    n_E = G.n_edges

    incoming: dict = {}
    outgoing: dict = {}
    for i in range(n_E):
        outgoing.setdefault(int(G.f[i]), []).append(i)
        incoming.setdefault(int(G.t[i]), []).append(i)

    live_e = np.where(flow > 0)[0]
    live_nodes = np.unique(np.concatenate([G.f[live_e], G.t[live_e]]))

    def rev_reach(head_n, cap=CAP_BFS):
        """可从哪些节点**有向到达** head_n（含 head_n）。"""
        seen = {head_n}
        q = deque([head_n])
        while q and len(seen) <= cap:
            cur = q.popleft()
            for j in incoming.get(cur, []):
                u = int(G.f[j])
                if u not in seen:
                    seen.add(u)
                    q.append(u)
        return seen

    obs, cw, _ = load_frozen()
    gl = lta_section_geometry(ev1.TRAFFIC).set_index("LinkID")
    geo = pd.read_csv(E.SEC_GEO_7_6C, dtype={"lta_linkid": str}).set_index("lta_linkid")
    ss_path = OUT / "section_scale_v10.csv"
    ss = pd.read_csv(ss_path, dtype={"lta_linkid": str}).set_index("lta_linkid")
    cwraw = pd.read_csv(ev1.FINAL_CW, encoding="utf-8-sig",
                        dtype={"lta_linkid": str, "matsim_link_id": str})
    cwraw["matsim_link_id"] = cwraw["matsim_link_id"].astype(str).str.strip()
    prim = cwraw[cwraw["is_primary_candidate"].astype(str).str.lower().isin(["true", "1"])]
    mat = {str(s): [x for x in g["matsim_link_id"] if x in id2i] for s, g in prim.groupby("lta_linkid")}

    # ---------- OSM ----------
    import geopandas as gpd
    from shapely.geometry import Point
    gosm = gpd.read_file(OSM_SHP, columns=["osm_id", "highway", "oneway", "name", "ref", "geometry"])
    geom_ll = gosm.geometry.copy()          # ★原始 EPSG:4326（供 N3 非同源扰动）
    gosm = gosm.to_crs(3414).reset_index(drop=True)
    gosm["osm_id"] = gosm["osm_id"].astype(str)
    hw_o = gosm["highway"].astype(str)
    n_osm_major = int(hw_o.isin(MAJOR).sum())
    ow = gosm.loc[hw_o.isin(MAJOR), "oneway"].astype(str).str.lower().str.strip()
    ow_yes_share = float((ow == "yes").mean())
    geom_o = gosm.geometry
    is_access = hw_o.isin(ACCESS_TYPES).to_numpy()

    target = pd.read_csv(OUT / "bb_zero_flow_ledger_7_9ibb.csv", dtype={"lta_linkid": str})
    o1c = pd.read_csv(OUT / "o1c_build_cards_7_9io1c.csv", dtype={"lta_linkid": str})
    dt = o1c[o1c["iso_class"] == "ISO_DEAD_TUBE"].copy()
    tw = o1c[o1c["iso_class"] == "ISO_TWIN_EXISTS"].copy()
    tgt = dt["lta_linkid"].tolist()

    # ---------- 门 1：坐标同源 ----------
    mx0 = float(geo.loc[tgt[0], "mid_x"])
    gates.append(["G-O1C2-1 坐标同源（SEC_GEO mid_x 落在 SVY21 量级 <1e6）",
                  bool(0.0 < mx0 < 1.0e6), f"样例 {tgt[0]} mid_x={mx0:.1f}"])
    gates.append(["G-O1C2-4 OSM 读入自检（MAJOR way = 6694，oneway=yes 占比 = 0.9283）",
                  bool(n_osm_major == 6694 and abs(ow_yes_share - 0.9282939946220496) < 1e-9),
                  f"MAJOR={n_osm_major}  oneway=yes 占比={ow_yes_share:.4f}"])

    rows = []
    for sid in tgt:
        mx, my = float(geo.loc[sid, "mid_x"]), float(geo.loc[sid, "mid_y"])
        sb = float(gl.loc[sid, "bear"])
        ms = mat.get(sid, [])
        msi = [id2i[x] for x in ms]

        # ---- 死管链（同向零流单链，双向扩展）----
        def ext(seed, dirn):
            cur, out = seed, []
            for _ in range(MAX_STEPS):
                v = int(G.f[cur]) if dirn == "up" else int(G.t[cur])
                nxt = incoming.get(v, []) if dirn == "up" else outgoing.get(v, [])
                cand = [j for j in nxt if flow[j] == 0]
                if len(cand) != 1:
                    break
                cur = cand[0]
                out.append(cur)
            return out

        up_all, dn_all = [], []
        for s in msi:
            up_all += ext(s, "up")
            dn_all += ext(s, "down")
        up_all = list(dict.fromkeys(up_all))
        dn_all = list(dict.fromkeys(dn_all))
        chain = list(dict.fromkeys(msi + up_all + dn_all))

        # ---- 链头 ----
        headn = int(G.f[msi[0]])
        hx, hy = float(G.nx[headn]), float(G.ny[headn])
        ins = incoming.get(headn, [])
        n_in = len(ins)
        hw_in = [G.highway[j] for j in ins]
        n_in_link = int(sum(h in LINK_TYPES for h in hw_in))

        # ---- first_nonzero_dist ----
        fn_dist = float(np.min(np.hypot(G.nx[live_nodes] - hx, G.ny[live_nodes] - hy)))

        # ---- route_accessible（拓扑可达；预注册已披露为不区分量）----
        RR = rev_reach(headn)
        route_acc = bool(any(int(G.t[e]) in RR for e in live_e))

        # ---- OSM 接入对象 ----
        dgeo = geom_o.distance(Point(hx, hy)).to_numpy(float)
        near = np.where((dgeo <= R_ACC) & is_access)[0]
        o_same, o_other = [], []
        for k in near:
            br = nearest_seg_bearing(geom_o.iloc[k], hx, hy)[1]
            (o_same if circ_diff(br, sb) < DIR_OK else o_other).append(int(k))
        osm_access_n = len(o_same)
        osm_link = [k for k in o_same if str(hw_o.iloc[k]) in LINK_TYPES]
        types_all = sorted({str(hw_o.iloc[k]) for k in near})

        # ---- ★B 判据：link way 顶点覆盖率 ----
        conv, unconv, cov_list = 0, 0, []
        unconv_ids, conv_det = [], []
        for k in osm_link:
            pts = sample_points(geom_o.iloc[k])
            cov = 0
            for px, py in pts:
                dj = np.hypot(G.ex - px, G.ey - py)
                cj = np.where(dj <= R_MS2)[0]
                if len(cj) and any(circ_diff(bear_e[j], sb) < DIR_OK for j in cj):
                    cov += 1
            frac = cov / max(len(pts), 1)
            cov_list.append(frac)
            if frac >= COV_MIN:
                conv += 1
                conv_det.append((str(gosm["osm_id"].iloc[k]), round(float(frac), 3)))
            else:
                unconv += 1
                unconv_ids.append(str(gosm["osm_id"].iloc[k]))
        conversion_loss = bool(len(osm_link) > 0 and conv == 0)

        # ---- D/E：头部 R_MS2 内同向活流边 ----
        d2h = np.hypot(G.ex - hx, G.ey - hy)
        msnear = np.where(d2h <= R_MS2)[0]
        ms_same_live = int(sum(1 for j in msnear
                               if circ_diff(bear_e[j], sb) < DIR_OK and flow[j] > 0))
        ms_same = int(sum(1 for j in msnear if circ_diff(bear_e[j], sb) < DIR_OK))
        ms_same_link_n = int(sum(1 for j in msnear
                                 if circ_diff(bear_e[j], sb) < DIR_OK and G.highway[j] in LINK_TYPES))

        # ---- OSM 端点吸附（披露）----
        snap_term = 0
        for k in o_same:
            c = np.asarray(geom_o.iloc[k].coords, float)
            if np.hypot(c[0, 0] - hx, c[0, 1] - hy) <= R_SNAP or np.hypot(c[-1, 0] - hx, c[-1, 1] - hy) <= R_SNAP:
                snap_term += 1

        # ---- 分类（互斥，优先级 A>B>C>D>E）----
        if osm_access_n == 0:
            cls = A_C
        elif conversion_loss:
            cls = B_C
        elif n_in == 0:
            cls = C_C
        elif ms_same_live == 0:
            cls = D_C
        else:
            cls = E_C
        chain_len = len(chain)
        conf = "high" if cls in (A_C, B_C, C_C) else ("medium" if chain_len >= 3 else "low")

        rows.append(dict(
            section_id=str(sid),
            RoadName=str(dt.loc[dt["lta_linkid"] == sid, "RoadName"].iloc[0]),
            label=str(dt.loc[dt["lta_linkid"] == sid, "label"].iloc[0]),
            obs_8_9=float(dt.loc[dt["lta_linkid"] == sid, "obs_8_9"].iloc[0]),
            n_match=len(ms), head_node=int(headn), head_x=hx, head_y=hy, bear=sb,
            dead_chain_len=chain_len, upstream_zero_depth=len(up_all), downstream_zero_depth=len(dn_all),
            first_nonzero_dist=round(fn_dist, 1),
            OSM_access_n=osm_access_n, OSM_link_n=len(osm_link),
            MATSim_access_n=n_in, MATSim_access_link_n=n_in_link,
            link_evidence=(f"OSM:{','.join(sorted(set(str(hw_o.iloc[k]) for k in osm_link))) or '-'}"
                           f"(n={len(osm_link)}) | MATSim:{','.join(sorted(set(hw_in))) or '-'}(n={n_in})"),
            link_converted=conv, link_unconverted=unconv,
            cov_min_frac=(round(min(cov_list), 3) if cov_list else np.nan),
            cov_p50_frac=(round(float(np.median(cov_list)), 3) if cov_list else np.nan),
            unconverted_ids=";".join(unconv_ids),
            conversion_loss=conversion_loss,
            route_accessible=route_acc,
            ms_same=int(ms_same), ms_same_link=int(ms_same_link_n), ms_same_live=int(ms_same_live),
            osm_snap_term=snap_term, osm_types_all="|".join(types_all),
            final_class=cls, confidence=conf))

    d = pd.DataFrame(rows)
    assert len(d) == 18, len(d)

    # ---------- 门 2：上游复现（18 节 matched 边 Σ = 74，与 O1-续卡片一致）----------
    sum_match = int(d["n_match"].sum())
    gates.append(["G-O1C2-2 上游复现（18 节 matched 边总数 = 74，与 O1-续卡片一致）",
                  bool(sum_match == 74), f"Σmatched={sum_match}"])

    # ---------- 门 3：冻结 canonical 对账 ----------
    smx = ss["sim_median_xS"].reindex(d["section_id"]).to_numpy(float)
    gates.append(["G-O1C2-3 冻结对账（18 节 sim_median_xS 全为 0）",
                  bool(np.nanmax(np.abs(smx)) == 0.0), f"max|sim_median_xS|={np.nanmax(np.abs(smx)):.3e}"])

    # ---------- 门 5：★判别量非退化 ----------
    def nuniq(s):
        return int(pd.Series(s).nunique())
    ok5 = bool(nuniq(d["OSM_access_n"]) >= 2 and nuniq(d["MATSim_access_n"]) >= 2
               and nuniq(d["ms_same_live"]) >= 2)
    gates.append(["G-O1C2-5 ★判别量非退化（OSM_access_n / MATSim_access_n / ms_same_live 各 ≥2 取值）",
                  ok5, f"uniq OSM_access_n={nuniq(d['OSM_access_n'])}{sorted(d['OSM_access_n'].unique())}"
                       f"；MATSim_access_n={nuniq(d['MATSim_access_n'])}{sorted(d['MATSim_access_n'].unique())}"
                       f"；ms_same_live={nuniq(d['ms_same_live'])}{sorted(d['ms_same_live'].unique())}"])

    # ---------- 门 6：★覆盖率口径非退化 ----------
    cl = d["cov_p50_frac"].dropna()
    mincl = d["cov_min_frac"].dropna()
    gates.append(["G-O1C2-6 ★覆盖率口径非退化（存在 cov_frac ∈ (0,1)；且 min < 1）",
                  bool(len(cl) > 0 and float(mincl.min()) < 1.0 and float(cl.median()) >= 0.5),
                  f"有 link way 的节数={len(cl)}；min cov_frac={float(mincl.min()):.3f}；"
                  f"p50 cov_frac={float(cl.median()):.3f}"])

    # ---------- 门 7：死管链非退化 ----------
    gates.append(["G-O1C2-7 死管链非退化（dead_chain_len ≥3 类；upstream_zero_depth 有 0 与非 0）",
                  bool(d["dead_chain_len"].nunique() >= 3
                       and (d["upstream_zero_depth"] == 0).any() and (d["upstream_zero_depth"] > 0).any()),
                  f"dead_chain_len uniq={d['dead_chain_len'].nunique()}"
                  f"{sorted(d['dead_chain_len'].unique())}；"
                  f"up_depth=0 有 {int((d['upstream_zero_depth']==0).sum())} 节，>0 有 {int((d['upstream_zero_depth']>0).sum())} 节"])

    # ---------- 门 8：卡片完备 ----------
    req = ["section_id", "dead_chain_len", "upstream_zero_depth", "first_nonzero_dist",
           "OSM_access_n", "MATSim_access_n", "link_evidence", "conversion_loss",
           "route_accessible", "final_class", "confidence"]
    miss = [c for c in req if c not in d.columns]
    nan_req = [c for c in ["section_id", "dead_chain_len", "upstream_zero_depth", "first_nonzero_dist",
                           "OSM_access_n", "MATSim_access_n", "final_class", "confidence"]
               if d[c].isna().any()]
    gates.append(["G-O1C2-8 卡片完备（18 行 × 11 必填字段；final_class ⊆ {A,B,C,D,E}）",
                  bool(len(d) == 18 and not miss and not nan_req and set(d["final_class"]) <= CLASSES),
                  f"缺失列={miss}；必填 NaN 列={nan_req}；classes={sorted(set(d['final_class']))}"])

    # ---------- 负例（5）----------
    def cards_pert(**kw):
        r_acc = kw.get("R_ACC", R_ACC)
        r_ms2 = kw.get("R_MS2", R_MS2)
        cov_min = kw.get("COV_MIN", COV_MIN)
        flip = kw.get("flip", False)
        bad_crs = kw.get("bad_crs", False)
        gg = geom_ll if bad_crs else geom_o       # ★N3：不投影 ⇒ 非同源（单位从 m 变 degree）
        rr = []
        for sid in tgt:
            sb = (float(gl.loc[sid, "bear"]) + (180.0 if flip else 0.0)) % 360.0
            ms = mat.get(sid, [])
            headn = int(G.f[id2i[ms[0]]])
            hx, hy = float(G.nx[headn]), float(G.ny[headn])
            dgeo = gg.distance(Point(hx, hy)).to_numpy(float)
            near = np.where((dgeo <= r_acc) & is_access)[0]
            o_same = [int(k) for k in near
                      if circ_diff(nearest_seg_bearing(gg.iloc[k], hx, hy)[1], sb) < DIR_OK]
            osm_link = [k for k in o_same if str(hw_o.iloc[k]) in LINK_TYPES]
            conv = 0
            for k in osm_link:
                pts = sample_points(gg.iloc[k])
                cov = 0
                for px, py in pts:
                    dj = np.hypot(G.ex - px, G.ey - py)
                    cj = np.where(dj <= r_ms2)[0]
                    if len(cj) and any(circ_diff(bear_e[j], sb) < DIR_OK for j in cj):
                        cov += 1
                if cov / max(len(pts), 1) >= cov_min:
                    conv += 1
            d2h = np.hypot(G.ex - hx, G.ey - hy)
            ms_same_live = int(sum(1 for j in np.where(d2h <= r_ms2)[0]
                                   if circ_diff(bear_e[j], sb) < DIR_OK and flow[j] > 0))
            rr.append(dict(osm=len(o_same), nin=len(incoming.get(headn, [])),
                           msl=ms_same_live, conv=conv, un=len(osm_link) - conv))
        return pd.DataFrame(rr)

    def sig(dfx):
        return (int(dfx["osm"].sum()), int(dfx["nin"].sum()), int(dfx["msl"].sum()),
                int(dfx["conv"].sum()), int(dfx["un"].sum()))

    base = pd.DataFrame({"osm": d["OSM_access_n"], "nin": d["MATSim_access_n"],
                         "msl": d["ms_same_live"], "conv": d["link_converted"],
                         "un": d["link_unconverted"]})
    s0 = sig(base)
    neg = []
    for nm, kw in [("N1 R_ACC 60 m → 5 m（取消 OSM 邻域）", dict(R_ACC=5.0)),
                   ("N2 R_MS2 50 m → 2000 m", dict(R_MS2=2000.0)),
                   ("N3 OSM 几何不投影（保持 EPSG:4326，与 SVY21 锚点非同源）", dict(bad_crs=True)),
                   ("N4 COV_MIN 0.5 → 1.01（空判据）", dict(COV_MIN=1.01)),
                   ("N5 方位整体 +180°（same/opp 互换）", dict(flip=True))]:
        sn = sig(cards_pert(**kw))
        neg.append({"neg": nm, "fired": bool(sn != s0), "sig_base": s0, "sig_pert": sn})
    gates.append(["G-O1C2-N 负例 5/5 fired（非同构扰动，须真改变可观测结果）",
                  all(x["fired"] for x in neg),
                  "；".join(f"{x['neg'][:2]}{'✓' if x['fired'] else '✗'}" for x in neg)])

    # ---------- 门 9：确定性 ----------
    src = Path(__file__).read_text(encoding="utf-8")
    bad = []
    for nd in ast.walk(ast.parse(src)):
        if isinstance(nd, ast.Attribute) and nd.attr in {"random", "shuffle", "rand", "randn", "randint"}:
            bad.append(nd.attr)
        if isinstance(nd, ast.Name) and nd.id == "random":
            bad.append("name:random")
    gates.append(["G-O1C2-9 确定性自检（AST 无随机源 + 卡片 18 行）",
                  bool(len(bad) == 0 and len(d) == 18), f"随机源 {len(bad)} 个；卡片 {len(d)} 行"])

    # ---------- 汇总 ----------
    cls_cnt = {k: int(v) for k, v in d["final_class"].value_counts().items()}
    rec["criteria_revision"] = [
        {"id": "R1", "when": "探路后、正式跑前（写入本预注册 §2.4）",
         "what": "B 判据原为「单点」口径（只看 link way 距 head 最近的一点是否有同向 MATSim 边）",
         "why": "单点口径把**端点落在路口空档**的 way 误判为未转换：49054 的 `479127292` 单点=未转换，覆盖率=**0.893** ⇒ 实为已转换 ⇒ **判据设计缺陷**（非实现缺陷、非科学结论）",
         "fix": "改为**顶点覆盖率**（沿几何每 `SAMPLE_M=10 m` 重采样，命中同向 MATSim 边即覆盖），`COV_MIN=0.5`；并要求门 `G-O1C2-6` 披露覆盖率非退化",
         "note": "阈值未改（`R_ACC=60 / R_MS2=50 / DIR_OK=30`）；只改「是否转换」的判定口径"},
        {"id": "R2", "when": "首跑后（`n_fail=1`，BLOCKED；正式结论写盘前）",
         "what": "负例 `N3` 原设计为「断面坐标改用 `lta_section_geometry().mx/my`（非同源）」",
         "why": "**实现缺陷**：扰动函数以**链头节点**（SVY21）为 OSM 邻域锚点，`mx/my` 从未被使用 ⇒ 扰动 = 空操作 ⇒ `fired=False`（假阴性）。非同构扰动的目的是证明仪器对变化有响应，空扰动违反该目的",
         "fix": "`N3` 改为 **OSM 几何不投影（保持 EPSG:4326）** ⇒ 与 SVY21 锚点**真非同源**（单位由 m 变 degree）",
         "note": "主路径判据/阈值**未改**；只改负例的扰动构造。属**仪器缺陷**，非科学结论"},
    ]
    tw_dist = tw["twin_dist_min"].to_numpy(float)
    rec["summary"] = {
        "scope": "ISO_DEAD_TUBE 18 节（Σobs = %.1f）" % d["obs_8_9"].sum(),
        "obs_sum": float(d["obs_8_9"].sum()),
        "class_counts": cls_cnt,
        "A_no_osm_feeder": int((d["final_class"] == A_C).sum()),
        "B_link_unconverted": int((d["final_class"] == B_C).sum()),
        "C_no_matsim_in_edge": int((d["final_class"] == C_C).sum()),
        "D_no_local_live_same_dir": int((d["final_class"] == D_C).sum()),
        "E_local_live_same_dir_exists": int((d["final_class"] == E_C).sum()),
        "osm_access_n": {"n_zero": int((d["OSM_access_n"] == 0).sum()),
                         "min": int(d["OSM_access_n"].min()), "max": int(d["OSM_access_n"].max())},
        "matsim_access_n": {str(k): int(v) for k, v in d["MATSim_access_n"].value_counts().items()},
        "link_evidence": {"sections_with_osm_link": int((d["OSM_link_n"] > 0).sum()),
                          "osm_link_ways_total": int(d["OSM_link_n"].sum()),
                          "converted_total": int(d["link_converted"].sum()),
                          "unconverted_total": int(d["link_unconverted"].sum()),
                          "min_cov_frac": (float(d["cov_min_frac"].min()) if d["cov_min_frac"].notna().any() else None),
                          "p50_cov_frac": (float(d["cov_p50_frac"].median()) if d["cov_p50_frac"].notna().any() else None)},
        "ms_same_live": {"n_zero": int((d["ms_same_live"] == 0).sum()),
                         "n_pos": int((d["ms_same_live"] > 0).sum())},
        "route_accessible": {"n_true": int(d["route_accessible"].sum()),
                             "n_false": int((~d["route_accessible"]).sum()),
                             "note": "预注册已披露：18/18 为 True ⇒ 不区分量"},
        "first_nonzero_dist": {q: float(np.percentile(d["first_nonzero_dist"], p))
                               for q, p in [("p10", 10), ("p50", 50), ("p90", 90), ("max", 100)]},
        "dead_chain_len": {q: float(np.percentile(d["dead_chain_len"], p))
                           for q, p in [("p50", 50), ("p90", 90), ("max", 100)]},
        "confidence": {k: int(v) for k, v in d["confidence"].value_counts().items()},
        "TWIN_evidence_only": {
            "label": "TWIN_GEOMETRIC_SUBSTITUTE",
            "n": int(len(tw)), "obs_sum": float(tw["obs_8_9"].sum()),
            "twin_dist_min": {q: float(np.nanpercentile(tw_dist, p))
                              for q, p in [("p25", 25), ("p50", 50), ("p90", 90)]},
            "note": "⛔ 仅证据整理；不做「同一物理车行道」裁定（需 detector/设施元数据）"}}

    rec["negatives"] = neg
    rec["gates"] = [{"gate": g, "pass": bool(p), "measured": m} for g, p, m in gates]
    rec["n_fail"] = int(sum(1 for _, p, _ in gates if not p))
    rec["verdict"] = ("DEAD_TUBE_ACCESS_AUDIT_READY" if rec["n_fail"] == 0
                      else "DEAD_TUBE_ACCESS_AUDIT_BLOCKED")
    rec["elapsed_s"] = round(time.time() - t0, 1)

    d.to_csv(OUT / "o1c2_access_cards_7_9io1c2.csv", index=False, encoding="utf-8-sig")
    (OUT / "o1c2_access_summary_7_9io1c2.json").write_text(
        json.dumps(rec, ensure_ascii=False, indent=1), encoding="utf-8")

    print("\n===== GATES =====")
    for g, p, m in gates:
        print(f"  [{'PASS' if p else 'FAIL'}] {g}\n          | {m}")
    print("\n===== Access Card（18 节 ISO_DEAD_TUBE）=====")
    cols = ["section_id", "RoadName", "obs_8_9", "dead_chain_len", "upstream_zero_depth",
            "first_nonzero_dist", "OSM_access_n", "MATSim_access_n", "OSM_link_n",
            "link_unconverted", "cov_min_frac", "ms_same_live", "route_accessible",
            "final_class", "confidence"]
    pd.set_option("display.width", 260)
    print(d[cols].to_string(index=False))
    print("\n===== 汇总 =====")
    print("class_counts:", cls_cnt)
    print("link_evidence:", rec["summary"]["link_evidence"])
    print("ms_same_live:", rec["summary"]["ms_same_live"])
    print("osm_access_n:", rec["summary"]["osm_access_n"])
    print(f"\nVERDICT={rec['verdict']}  n_fail={rec['n_fail']}  {rec['elapsed_s']}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
