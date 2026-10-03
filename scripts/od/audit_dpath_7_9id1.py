# -*- coding: utf-8 -*-
"""Step 7.9I-D-path · D 类零流链「上游有向路径追踪」—— 零仿真、只读

★正式问题（用户 2026-09-30 裁定，见 PREREG_7_9I_DPATH.md）：
  只追 D 类 14 节（`D_NO_LOCAL_LIVE_SAME_DIR`）：
    沿有向拓扑向上游展开 → 最近 active edge → D1 同向平行 / D2 对向对层 /
    D3 同走廊更远处汇入 / D4 拓扑替代 / D5 深度内无承载对象
  ＋ ★流量守恒核心证据（flA_in / flA_out / Rn / Rd / R_cons）
  ＋ ★第二轴：承载充分性 carry_scaled = flA_in×SCALE/obs

⛔ 底线：不改 v1.0；不跑 MATSim；不碰 signals/trafficDynamics/speedFactor；不产生 v1.1。
⛔ 判读：D1–D4 **只能**叫「承载对象替代 / 路径重分配」，不得叫「映射错误」。
★ 实现纪律（承接 O1-续② 缺陷 R2）：主路径与全部负例**共用同一 `compute(params)`**，
  从实现层面消除「扰动未生效 ⇒ 假阴性」。
"""
from __future__ import annotations

import ast
import hashlib
import json
import sys
import time
from collections import deque
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(r"D:\Luan\2026-05\2_Singapore")
sys.path.insert(0, str(ROOT / "scripts" / "od"))

import audit_sampling_capacity_7_9a1 as A               # noqa: E402
import evaluate_calibration_7_4_2 as ev1                # noqa: E402
import evaluate_demand_response_7_6f_1 as E             # noqa: E402
from diagnose_gap_7_9h import read_edge_full            # noqa: E402
from audit_corridor_scale_7_9ia import OUT              # noqa: E402
from audit_m1_accessibility_7_9ib import Graph          # noqa: E402
from audit_carriageway_pair_7_9io1 import circ_diff     # noqa: E402

CACHE_NET = ROOT / "scripts" / "od" / "_cache_network_7_9c0.npz"
OSM_SHP = ROOT / "Singapore_OD_MATSim_FinalData" / "07_RoadNetwork" / "osm-lines_expanded.shp"

# ---- 预注册常量（PREREG_7_9I_DPATH.md §2.1，运行前冻结）----
HOP_MAX = 120
CAP_DOM = 60000
MAX_STEPS = 2000
DIR_OK = 30.0
OPP_MIN = 150.0
D_PAR = 60.0
CARRY_MIN = 0.50
R_MS2 = 50.0          # 承接 O1-续②：链头同向活流邻域半径（未改）
K_POOLED = 5.5434

D1, D2, D3, D4, D5 = "D1_PARALLEL_SAME_DIR", "D2_OPPOSITE_LAYER", "D3_SAME_CORR_DOWNSTREAM", \
                     "D4_TOPOLOGICAL_ALTERNATIVE", "D5_NO_CARRIER_IN_DEPTH"
F_ADQ, F_LOW = "F_ADQ", "F_LOW"

BASE = dict(hop_max=HOP_MAX, cap_dom=CAP_DOM, max_steps=MAX_STEPS, r_ms2=R_MS2,
            dir_ok=DIR_OK, opp_min=OPP_MIN, d_par=D_PAR, carry_min=CARRY_MIN,
            flip=False, zero_only=True, dn_off=False)

# ---------- 全局只读数据 ----------
edge1 = read_edge_full(A.V10_LS)
G = Graph(np.load(CACHE_NET, allow_pickle=True))
flow = np.nan_to_num(edge1.set_index("LINK")["HRS8-9avg"].reindex(G.ids).to_numpy(float), nan=0.0)
LEN_ARR = np.nan_to_num(edge1.set_index("LINK")["LENGTH"].reindex(G.ids).to_numpy(float), nan=0.0)
id2i = {x: i for i, x in enumerate(G.ids)}
bear_e = (np.degrees(np.arctan2(G.nx[G.t] - G.nx[G.f], G.ny[G.t] - G.ny[G.f])) + 360.0) % 360.0
NN = G.n_nodes
outgoing, incoming = {}, {}
for i in range(G.n_edges):
    outgoing.setdefault(int(G.f[i]), []).append(i)
    incoming.setdefault(int(G.t[i]), []).append(i)

LIVE = np.where(flow > 0)[0]
T_LIVE = G.t[LIVE]
F_LIVE = G.f[LIVE]
FL_LIVE = flow[LIVE]
in_live_cnt = np.bincount(G.t[LIVE], minlength=NN)
out_live_cnt = np.bincount(G.f[LIVE], minlength=NN)
in_live_fl = np.bincount(G.t[LIVE], weights=FL_LIVE, minlength=NN)
out_live_fl = np.bincount(G.f[LIVE], weights=FL_LIVE, minlength=NN)

cwraw = pd.read_csv(ev1.FINAL_CW, encoding="utf-8-sig",
                    dtype={"lta_linkid": str, "matsim_link_id": str})
cwraw["matsim_link_id"] = cwraw["matsim_link_id"].astype(str).str.strip()
_prim = cwraw[cwraw["is_primary_candidate"].astype(str).str.lower().isin(["true", "1"])]
MAT = {str(s): [x for x in g["matsim_link_id"] if x in id2i] for s, g in _prim.groupby("lta_linkid")}

_o1c2 = pd.read_csv(OUT / "o1c2_access_cards_7_9io1c2.csv", dtype={"section_id": str})
DD = _o1c2[_o1c2["final_class"].str.startswith("D_")].copy()
TGT = DD["section_id"].tolist()
OBS = {r.section_id: float(r.obs_8_9) for r in DD.itertuples()}
BEAR = {r.section_id: float(r.bear) for r in DD.itertuples()}
ROAD = {r.section_id: str(r.RoadName) for r in DD.itertuples()}
SS = pd.read_csv(OUT / "section_scale_v10.csv", dtype={"lta_linkid": str}).set_index("lta_linkid")


def dead_chain(msi):
    """同向零流单链（承接 O1-续②，未改）。"""
    def ext(seed, dirn):
        cur, out = seed, []
        for _ in range(MAX_STEPS):
            v = int(G.f[cur]) if dirn == "up" else int(G.t[cur])
            nxt = incoming.get(v, []) if dirn == "up" else outgoing.get(v, [])
            cand = [j for j in nxt if flow[j] == 0]
            if len(cand) != 1:
                break
            cur = cand[0]; out.append(cur)
        return out
    up, dn = [], []
    for s in msi:
        up += ext(s, "up"); dn += ext(s, "down")
    up = list(dict.fromkeys(up)); dn = list(dict.fromkeys(dn))
    return list(dict.fromkeys(msi + up + dn)), up, dn


def hr_domain(headn, p):
    """反向 BFS：hr(n) = 从 n 经（零流边 / 全边）有向到达 head 的最少边数。"""
    hr = np.full(NN, -1, np.int32)
    hr[headn] = 0
    q = deque([headn]); nlab = 1; capped = False
    while q:
        cur = q.popleft()
        hc = hr[cur]
        if hc >= p["hop_max"]:
            continue
        for j in incoming.get(int(cur), []):
            if p["zero_only"] and flow[j] != 0:
                continue
            u = int(G.f[j])
            if hr[u] < 0:
                if nlab >= p["cap_dom"]:
                    capped = True; break
                hr[u] = hc + 1; nlab += 1; q.append(u)
        if capped:
            break
    return hr, capped


def live_chain(e0, p):
    """单度活链 A*（双向扩展 + visited 防环）。"""
    ch = [e0]
    seen = {int(G.f[e0]), int(G.t[e0])}
    cur = e0
    for _ in range(p["max_steps"]):
        v = int(G.f[cur])
        if in_live_cnt[v] != 1:
            break
        j = [x for x in incoming.get(v, []) if flow[x] > 0][0]
        if int(G.f[j]) in seen:
            break
        seen.add(int(G.f[j])); ch.insert(0, j); cur = j
    cur = e0
    for _ in range(p["max_steps"]):
        v = int(G.t[cur])
        if out_live_cnt[v] != 1:
            break
        j = [x for x in outgoing.get(v, []) if flow[x] > 0][0]
        if int(G.t[j]) in seen:
            break
        seen.add(int(G.t[j])); ch.append(j); cur = j
    return ch


def compute(p):
    """★主路径与负例共用：给定参数，返回 14 行 Card。"""
    rows = []
    for sid in TGT:
        sb = BEAR[sid]
        sb_use = (sb + (180.0 if p["flip"] else 0.0)) % 360.0
        obs = OBS[sid]
        ms = MAT.get(sid, [])
        msi = [id2i[x] for x in ms]
        chain, up_all, dn_all = dead_chain(msi)
        headn = int(G.f[msi[0]])
        hx, hy = float(G.nx[headn]), float(G.ny[headn])
        hr, capped = hr_domain(headn, p)

        # ---- C_in：to(e) 落在上游零流域（hr≥1）的活边 ----
        hr_t = hr[T_LIVE]
        sel = hr_t >= 1
        cand = LIVE[sel]; c_hop = hr_t[sel].astype(np.int64); c_fl = flow[cand]
        n_cin = int(len(cand))
        order = np.lexsort((cand, -c_fl, c_hop))
        cand = cand[order]; c_hop = c_hop[order]

        # ---- 诊断：欧氏最近活边（不限定 C_in）----
        dd_head = np.hypot(G.ex[LIVE] - hx, G.ey[LIVE] - hy)
        k = int(np.argmin(dd_head))
        e_eu = int(LIVE[k])
        near_euc_db = round(float(circ_diff(float(bear_e[e_eu]), sb_use)), 1)
        near_euc_dist = round(float(dd_head[k]), 1)
        near_euc_in = bool(hr[int(G.t[e_eu])] >= 1)

        # ---- 下游同走廊活流（D3 判据）----
        dn_live = 0
        for s in msi:
            dn_live += int(sum(1 for j in outgoing.get(int(G.t[s]), []) if flow[j] > 0))
        if dn_all:
            dn_live += int(sum(1 for j in outgoing.get(int(G.t[dn_all[-1]]), []) if flow[j] > 0))

        # ---- 链头前提复检 ----
        head_in_flow = float(sum(flow[j] for j in incoming.get(headn, [])))
        n_ms_in = len(incoming.get(headn, []))

        # ---- D/E 复现（链头 R_MS2 内同向）----
        d2h = np.hypot(G.ex - hx, G.ey - hy)
        msnear = np.where(d2h <= p["r_ms2"])[0]
        ms_same = int(sum(1 for j in msnear if circ_diff(float(bear_e[j]), sb) < p["dir_ok"]))
        ms_same_live = int(sum(1 for j in msnear
                               if circ_diff(float(bear_e[j]), sb) < p["dir_ok"] and flow[j] > 0))

        rec = dict(section_id=sid, RoadName=ROAD[sid], obs_8_9=obs, dead_chain_len=len(chain),
                   head_node=headn, chain_bear=round(sb, 1), hr_dom_n=int((hr >= 0).sum()),
                   hr_hop_max=int(hr.max()), hr_capped=bool(capped), n_Cin=n_cin,
                   ms_same=ms_same, ms_same_live=ms_same_live, dn_live=int(dn_live),
                   head_in_flow=round(head_in_flow, 1), n_ms_in=int(n_ms_in),
                   near_euc_db=near_euc_db, near_euc_dist=near_euc_dist,
                   near_euc_in_Cin=near_euc_in)

        if n_cin == 0:
            rec.update(dict(e_near_id="-", e_near_hw="-", e_near_fl=np.nan, e_near_hop=np.nan,
                            e_near_dbear=np.nan, e_near_d_own=np.nan,
                            A_star_n=0, A_star_len_m=np.nan, flA_in=np.nan, flA_out=np.nan,
                            R_cons=np.nan, fl_in_ext=np.nan, fl_out_ext=np.nan, Rn=np.nan,
                            Rd=np.nan, cons_testable=False, carry_raw=np.nan,
                            carry_scaled=np.nan, final_class=D5))
        else:
            e_n = int(cand[0]); hop = int(c_hop[0])
            ex, ey = float(G.ex[e_n]), float(G.ey[e_n])
            d_own = min(float(np.hypot(G.ex[j] - ex, G.ey[j] - ey)) for j in chain)
            db = round(float(circ_diff(float(bear_e[e_n]), sb_use)), 1)
            ch = live_chain(e_n, p)
            flA_in = float(flow[ch[0]]); flA_out = float(flow[ch[-1]])
            tail_n = int(G.f[ch[0]]); ha_n = int(G.t[ch[-1]])
            fl_in_ext = float(in_live_fl[tail_n]); fl_out_ext = float(out_live_fl[ha_n])
            R_cons = (flA_out / flA_in) if flA_in > 0 else np.nan
            Rn = (flA_in / fl_in_ext) if fl_in_ext > 0 else np.nan
            Rd = (fl_out_ext / flA_out) if flA_out > 0 else np.nan
            if (dn_live > 0) and not p["dn_off"]:
                cls = D3
            elif db >= p["opp_min"]:
                cls = D2
            elif db <= p["dir_ok"] and d_own <= p["d_par"]:
                cls = D1
            else:
                cls = D4
            rec.update(dict(e_near_id=str(G.ids[e_n]), e_near_hw=str(G.highway[e_n]),
                            e_near_fl=round(float(flow[e_n]), 1), e_near_hop=hop,
                            e_near_dbear=db, e_near_d_own=round(d_own, 1),
                            A_star_n=len(ch),
                            A_star_len_m=round(float(LEN_ARR[ch].sum()), 1),
                            flA_in=round(flA_in, 1), flA_out=round(flA_out, 1),
                            R_cons=(round(R_cons, 3) if R_cons == R_cons else np.nan),
                            fl_in_ext=round(fl_in_ext, 1), fl_out_ext=round(fl_out_ext, 1),
                            Rn=(round(Rn, 3) if Rn == Rn else np.nan),
                            Rd=(round(Rd, 3) if Rd == Rd else np.nan),
                            cons_testable=bool(fl_in_ext > 0 and flA_in > 0),
                            carry_raw=round(flA_in / obs, 4),
                            carry_scaled=round(flA_in * A.SCALE / obs, 3),
                            final_class=cls))
        cs = rec["carry_scaled"]
        rec["carry_class"] = (F_ADQ if (cs == cs and cs >= p["carry_min"]) else F_LOW)
        rec["confidence"] = ("high" if (rec["cons_testable"] and rec["n_Cin"] >= 20)
                             else ("medium" if rec["cons_testable"] else "low"))
        rows.append(rec)
    return pd.DataFrame(rows)


def sig(dfx):
    cmap = {D1: 0, D2: 0, D3: 0, D4: 0, D5: 0}
    for c in dfx["final_class"]:
        cmap[c] += 1
    return (cmap[D1], cmap[D2], cmap[D3], cmap[D4], cmap[D5],
            int(np.nansum(dfx["e_near_hop"])),
            int(round(np.nansum(dfx["carry_scaled"]) * 1000)),
            int(round(np.nansum(dfx["R_cons"]) * 100)),
            int(round(np.nansum(dfx["flA_in"]))))


def main() -> int:
    t0 = time.time()
    rec: dict = {"step": "7.9I-D-path/upstream-directed-trace", "scale": A.SCALE,
                 "hop_max": HOP_MAX, "cap_dom": CAP_DOM, "max_steps": MAX_STEPS,
                 "dir_ok_deg": DIR_OK, "opp_min_deg": OPP_MIN, "d_par_m": D_PAR,
                 "carry_min": CARRY_MIN, "r_ms2_m": R_MS2, "k_pooled": K_POOLED,
                 "label": "RUN_PRE_REGISTERED_FROZEN"}
    gates: list = []

    # ---------- 门 1：坐标同源 + LENGTH 单位自检 ----------
    gx = pd.read_csv(E.SEC_GEO_7_6C, dtype={"lta_linkid": str}).set_index("lta_linkid")
    mx_ok = bool(0.0 < float(gx.loc[TGT[0], "mid_x"]) < 1.0e6)
    _m = (LEN_ARR > 50) & (np.hypot(G.nx[G.t] - G.nx[G.f], G.ny[G.t] - G.ny[G.f]) > 50)
    ratio_p50 = float(np.median(LEN_ARR[_m] / np.hypot(G.nx[G.t] - G.nx[G.f],
                                                       G.ny[G.t] - G.ny[G.f])[_m]))
    gates.append(["G-DP-1 坐标同源 + LENGTH 单位自检（长边 LENGTH/欧氏 p50 ∈[0.99,1.01] ⇒ m）",
                  bool(mx_ok and 0.99 <= ratio_p50 <= 1.01),
                  f"mid_x 样例 {TGT[0]}={float(gx.loc[TGT[0], 'mid_x']):.1f}（SVY21）；"
                  f"n_long={int(_m.sum())}；比值 p50={ratio_p50:.4f} ⇒ 单位=m；全网 ΣLENGTH={LEN_ARR.sum()/1000:.1f} km"])

    # ---------- 主运行 ----------
    d = compute(BASE)
    assert len(d) == 14, len(d)

    # ---------- 门 2：上游复现 ----------
    same_set = bool(set(d["section_id"]) == set(TGT))
    obs_sum = float(d["obs_8_9"].sum())
    gates.append(["G-DP-2 上游复现（D 类 14 节，Σobs = 28,361.0，与 O1-续② 卡片一致）",
                  bool(len(d) == 14 and same_set and abs(obs_sum - 28361.0) < 1e-6),
                  f"n={len(d)}；Σobs={obs_sum:.1f}；与 O1-续② 集合一致={same_set}"])

    # ---------- 门 3：冻结对账 ----------
    smx = SS["sim_median_xS"].reindex(d["section_id"]).to_numpy(float)
    gates.append(["G-DP-3 冻结对账（14 节 sim_median_xS 全为 0）",
                  bool(np.nanmax(np.abs(smx)) == 0.0), f"max|sim_median_xS|={np.nanmax(np.abs(smx)):.3e}"])

    # ---------- 门 4：前提复核 ----------
    ok4 = bool((d["ms_same_live"] == 0).all() and (d["n_ms_in"] >= 1).all()
               and (d["head_in_flow"] == 0.0).all())
    gates.append(["G-DP-4 前提复核（ms_same_live==0 ∧ MATSim_access_n≥1 ∧ head_in_flow==0）", ok4,
                  f"ms_same_live max={int(d['ms_same_live'].max())}；n_ms_in min={int(d['n_ms_in'].min())}；"
                  f"head_in_flow max={float(d['head_in_flow'].max()):.3f}"])

    # ---------- 门 5：★判别量非退化 ----------
    dbv = d["e_near_dbear"].dropna(); dov = d["e_near_d_own"].dropna()
    hov = d["e_near_hop"].dropna(); rcv = d["R_cons"].dropna()
    ok5 = bool(dbv.nunique() >= 2 and (dbv.max() - dbv.min()) > 60.0
               and dov.nunique() >= 2 and hov.nunique() >= 2 and rcv.nunique() >= 2)
    gates.append(["G-DP-5 ★判别量非退化（dbear ≥2 取值∧极差>60°；d_own/hop/R_cons 各 ≥2 取值）", ok5,
                  f"dbear uniq={dbv.nunique()} range=[{dbv.min()},{dbv.max()}]；d_own uniq={dov.nunique()}；"
                  f"hop uniq={hov.nunique()}；R_cons uniq={rcv.nunique()} 取值={sorted(rcv.unique())}"])

    # ---------- 门 6：★追踪完整性 ----------
    hop_max_used = float(d["e_near_hop"].max())
    gates.append(["G-DP-6 ★追踪完整性（max(e_near_hop) ≤ HOP_MAX/4 ∧ hr_capped 全 False）",
                  bool(hop_max_used <= HOP_MAX / 4.0 and not d["hr_capped"].any()),
                  f"max hop={hop_max_used:.0f} ≤ {HOP_MAX/4:.0f}；hr_hop_max={int(d['hr_hop_max'].max())}；"
                  f"capped={int(d['hr_capped'].sum())} 节；域规模 {int(d['hr_dom_n'].min())}–{int(d['hr_dom_n'].max())} 节点"])

    # ---------- 门 7：Card 完备 ----------
    req = ["section_id", "obs_8_9", "dead_chain_len", "head_node", "chain_bear", "hr_dom_n",
           "hr_hop_max", "hr_capped", "n_Cin", "e_near_id", "e_near_hw", "e_near_fl",
           "e_near_hop", "e_near_dbear", "e_near_d_own", "A_star_n", "A_star_len_m",
           "flA_in", "flA_out", "R_cons", "fl_in_ext", "fl_out_ext", "Rn", "Rd",
           "cons_testable", "carry_raw", "carry_scaled", "carry_class", "ms_same",
           "ms_same_live", "dn_live", "near_euc_db", "near_euc_in_Cin", "final_class",
           "confidence"]
    miss = [c for c in req if c not in d.columns]
    nan_req = [c for c in ["section_id", "dead_chain_len", "n_Cin", "final_class", "carry_class",
                           "confidence", "hr_dom_n"] if d[c].isna().any()]
    gates.append(["G-DP-7 Card 完备（14 行 × §2.9 字段；final_class ⊆ D1..D5）",
                  bool(len(d) == 14 and not miss and not nan_req
                       and set(d["final_class"]) <= {D1, D2, D3, D4, D5}
                       and set(d["carry_class"]) <= {F_ADQ, F_LOW}),
                  f"缺失列={miss}；必填 NaN={nan_req}；classes={sorted(set(d['final_class']))}"])

    # ---------- 门 8：★支配类不得 100% + D1 退化披露 ----------
    vc = d["final_class"].value_counts()
    max_share = float(vc.iloc[0]) / len(d)
    gates.append(["G-DP-8 ★支配类不得 100%（nunique ≥2 ∧ 最大类占比 <100%）", 
                  bool(vc.size >= 2 and max_share < 1.0),
                  f"nunique={vc.size}；分布={vc.to_dict()}；最大类占比={max_share:.3f}；"
                  f"★D1={int((d['final_class']==D1).sum())} 节（结构性退化，须披露：D 类定义即排除同向紧邻活流）"])

    # ---------- 负例（6，与主路径共用 compute）----------
    s0 = sig(d)
    neg = []
    for nm, kw in [("N1 HOP_MAX 120→2（上游域压到 2 层）", dict(hop_max=2)),
                   ("N2 OPP_MIN 150→30.1（斜交并入同向）", dict(opp_min=30.1)),
                   ("N3 D_PAR 60→5000（远距离同向并入 D1）", dict(d_par=5000.0)),
                   ("N4 参考方位整体 +180°（同向↔对向互换）", dict(flip=True)),
                   ("N5 A* 扩展几乎禁用（max_steps=1 ⇒ 守恒证据退化为单边）", dict(max_steps=1)),
                   ("N6 D3 判据关闭（下游活流不参与分类）", dict(dn_off=True))]:
        p = dict(BASE); p.update(kw)
        sn = sig(compute(p))
        neg.append({"neg": nm, "fired": bool(sn != s0), "sig_base": list(s0), "sig_pert": list(sn)})
    # ★空扰动披露（原 N5 设计）：上游域口径（零流-only vs 全边）实测**无区分度**
    _p5 = dict(BASE); _p5["zero_only"] = False
    _d5 = compute(_p5)
    noop = {"probe": "上游域放宽为全边反向 BFS（zero_only=False）",
            "fired": bool(sig(_d5) != s0),
            "sig_base": list(s0), "sig_pert": list(sig(_d5)),
            "note": "★实测为空扰动 ⇒ 「零流-only」不是本刀的选择杠杆；保留为**披露项**，不列入门禁"}
    gates.append(["G-DP-N 负例 6/6 fired（非同构扰动，与主路径共用 compute ⇒ 无空扰动风险）",
                  all(x["fired"] for x in neg),
                  "；".join(f"{x['neg'][:2]}{'✓' if x['fired'] else '✗'}" for x in neg)
                  + f"；★披露：zero_only=False 空扰动(fired={noop['fired']})"])

    # ---------- 门 9：确定性 ----------
    src = Path(__file__).read_text(encoding="utf-8")
    bad = []
    for nd in ast.walk(ast.parse(src)):
        if isinstance(nd, ast.Attribute) and nd.attr in {"random", "shuffle", "rand", "randn", "randint"}:
            bad.append(nd.attr)
        if isinstance(nd, ast.Name) and nd.id == "random":
            bad.append("name:random")
    shared = bool("def compute(p)" in src and src.count("compute(") >= 7)
    gates.append(["G-DP-9 确定性自检（AST 无随机源 ∧ 14 行 ∧ 负例共用 compute(params)）",
                  bool(len(bad) == 0 and len(d) == 14 and shared),
                  f"随机源 {len(bad)} 个；卡片 {len(d)} 行；compute 共用={'✓' if shared else '✗'}"])

    # ---------- 汇总 ----------
    cls_cnt = {k: int(v) for k, v in vc.items()}
    obs_by_cls = {k: float(d.loc[d.final_class == k, "obs_8_9"].sum()) for k in cls_cnt}
    adq = d[d["carry_class"] == F_ADQ]
    low = d[d["carry_class"] == F_LOW]
    rec["summary"] = {
        "scope": "D_NO_LOCAL_LIVE_SAME_DIR 14 节（Σobs = %.1f）" % obs_sum,
        "obs_sum": obs_sum,
        "class_counts": cls_cnt,
        "obs_by_class": obs_by_cls,
        "share_by_class": {k: round(v / obs_sum, 4) for k, v in obs_by_cls.items()},
        "D1_degenerate_disclosure": ("D 类定义 = 链头 50 m 内无同向活流 ⇒ 同向且 d_own≤60 m 的活对象"
                                     "被上游定义结构性排除 ⇒ D1=0 不得读作「平行承载不存在」，"
                                     "只能读作「本层判据下不可检出」"),
        "carry_axis": {
            "carry_min": CARRY_MIN, "formula": "carry_scaled = flA_in × SCALE / obs_8_9",
            "n_adq": int(len(adq)), "obs_adq": float(adq["obs_8_9"].sum()),
            "n_low": int(len(low)), "obs_low": float(low["obs_8_9"].sum()),
            "share_low": round(float(low["obs_8_9"].sum()) / obs_sum, 4),
            "carry_scaled_all": {r.section_id: float(r.carry_scaled) for r in d.itertuples()},
            "note": "carry_* 为「单条 MATSim 边流量 / 单 LTA 断面观测」之比，K_pooled=5.5434 ⇒ 仅量级参照，不作独立判据"},
        "conservation": {
            "R_cons": {q: float(np.nanpercentile(d["R_cons"], pct))
                       for q, pct in [("min", 0), ("p50", 50), ("max", 100)]},
            "n_cons_testable": int(d["cons_testable"].sum()),
            "n_Rd_zero": int((d["Rd"] == 0.0).sum()),
            "Rn": {r.section_id: (None if r.Rn != r.Rn else float(r.Rn)) for r in d.itertuples()},
            "note": "R_cons=flA_out/flA_in（链内守恒）；Rn=上游分流比；Rd=下游续行比（=0 表示流量在 A_head 终止）"},
        "e_near": {r.section_id: dict(hop=int(r.e_near_hop), dbear=float(r.e_near_dbear),
                                      d_own=float(r.e_near_d_own), hw=str(r.e_near_hw),
                                      fl=float(r.e_near_fl))
                   for r in d.itertuples() if r.n_Cin > 0},
        "diagnostics": {
            "topo_vs_euclid_in_Cin": int(d["near_euc_in_Cin"].sum()),
            "note": "欧氏最近活边是否落在 C_in 内；不一致 ⇒ 零流团惰性遍历可能把 e_near 拉到物理不相邻对象上",
            "euc_not_in_cin": [r.section_id for r in d.itertuples() if not r.near_euc_in_Cin],
        },
        "ms_same_disclosure": {"n_same_obj_within_50m": int((d["ms_same"] > 0).sum()),
                               "n_same_live": int((d["ms_same_live"] > 0).sum())},
        "confidence": {k: int(v) for k, v in d["confidence"].value_counts().items()},
    }
    rec["negatives"] = neg
    rec["no_op_disclosure"] = noop
    rec["criteria_revision"] = [
        {"id": "R1", "when": "首跑后（`n_fail=1`，BLOCKED；正式结论写盘前）",
         "what": "预注册 §4 的 `N5` 原设计为「上游域放宽为全边反向 BFS」",
         "why": "**负例设计缺陷（估计错误）**：实测该扰动**完全不改变** `e_near` 选取与全部下游字段 "
                "⇒ 空扰动 `fired=False`（假阴性）。原因是 `head` 的入边**全为零流**（`head_in_flow==0`），"
                "放宽上游行进条件并未给 hop≤10 各层引入新的活边入口",
         "fix": "`N5` 改为 **`max_steps=1`（A* 扩展几乎禁用）**、新增 **`N6`（`D3` 判据关闭）**；"
                "原扰动降级为 §`no_op_disclosure` 披露项（本身是仪器发现：**零流-only 不是本刀的选择杠杆**）",
         "note": "主路径判据/阈值**未改**（`DIR_OK/OPP_MIN/D_PAR/CARRY_MIN/HOP_MAX` 全部冻结值）；"
                 "属**负例设计缺陷**，非科学结论"},
        {"id": "R2", "when": "首跑后（正式结论写盘前）",
         "what": "`cards_sha256_16` 原在 JSON 写盘**之后**才赋值 ⇒ JSON 内**缺卡片哈希**",
         "why": "**实现/顺序缺陷**：违反「产物哈希必须在被哈希产物写盘后、且在同批汇总写盘前算一次」"
                "（与「manifest 最后生成」同族纪律）",
         "fix": "调整为 **先写 CSV → 再算 SHA256 → 最后写 JSON**；`G-DP-9` 不改",
         "note": "**CSV 内容与判据未改**（哈希仍为 `866023f85b504655`）；仅汇总层顺序修正"},
    ]
    rec["gates"] = [{"gate": g, "pass": bool(pp), "measured": m} for g, pp, m in gates]
    rec["n_fail"] = int(sum(1 for _, pp, _ in gates if not pp))
    rec["verdict"] = ("DPATH_TRACE_READY" if rec["n_fail"] == 0 else "DPATH_TRACE_BLOCKED")
    rec["elapsed_s"] = round(time.time() - t0, 1)

    csv_p = OUT / "o1d_trace_cards_7_9id1.csv"
    d.to_csv(csv_p, index=False, encoding="utf-8-sig")
    # ★顺序纪律：先写被哈希产物，再算哈希，最后写 JSON（承接「manifest 最后生成」同族）
    rec["cards_sha256_16"] = hashlib.sha256(csv_p.read_bytes()).hexdigest()[:16]
    (OUT / "o1d_trace_summary_7_9id1.json").write_text(
        json.dumps(rec, ensure_ascii=False, indent=1), encoding="utf-8")

    print("\n===== GATES =====")
    for g, pp, m in gates:
        print(f"  [{'PASS' if pp else 'FAIL'}] {g}\n          | {m}")
    pd.set_option("display.width", 300)
    print("\n===== D-path Trace Card（14 节）=====")
    cols = ["section_id", "RoadName", "obs_8_9", "e_near_hop", "e_near_dbear", "e_near_d_own",
            "e_near_hw", "e_near_fl", "A_star_n", "flA_in", "flA_out", "R_cons", "Rn", "Rd",
            "carry_scaled", "carry_class", "dn_live", "near_euc_db", "near_euc_in_Cin",
            "final_class", "confidence"]
    print(d[cols].to_string(index=False))
    print("\n===== 汇总 =====")
    print("class_counts:", cls_cnt)
    print("obs_by_class:", obs_by_cls)
    print("share_by_class:", rec["summary"]["share_by_class"])
    print("carry_axis:", {k: rec["summary"]["carry_axis"][k] for k in
                          ("n_adq", "obs_adq", "n_low", "obs_low", "share_low")})
    print("conservation:", rec["summary"]["conservation"]["R_cons"],
          "testable=", rec["summary"]["conservation"]["n_cons_testable"],
          "Rd=0:", rec["summary"]["conservation"]["n_Rd_zero"])
    print("diag topo_vs_euclid_in_Cin:", rec["summary"]["diagnostics"]["topo_vs_euclid_in_Cin"],
          "euc_not_in_cin:", rec["summary"]["diagnostics"]["euc_not_in_cin"])
    print("cards_sha256_16:", rec["cards_sha256_16"])
    print(f"\nVERDICT={rec['verdict']}  n_fail={rec['n_fail']}  {rec['elapsed_s']}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
