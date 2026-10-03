# -*- coding: utf-8 -*-
"""Step 7.9I-D2-review · 「供流对象检索敏感性实验」—— 零仿真、只读

★正式问题（用户 2026-09-30 裁定，见 PREREG_7_9I_D2REVIEW.md）：
  是否因为当前候选域过窄，把「同向供流对象」人为排除掉了？
  R0 = 当前冻结口径（候选域 = 零流边反向可达，MAX_ACTIVE=0）
  R1 = 仅放宽候选域（MAX_ACTIVE=1，允许跨 1 条活边），其余全部不动
  ★关键判据：原 D2 六节中有多少在放宽后能找到「同向、量级合理」的供流对象（carry_scaled ≥ 0.50）

⛔ 底线：不改 v1.0；不跑 MATSim；不碰 signals/trafficDynamics/speedFactor；不产生 v1.1。
⛔ 判读：限于「承载对象替代 / 路径重分配」；D1=0 不重解释；不得读作「对向车在承载」。
★ 实现纪律（承接 O1-续② R2 / D-path R1）：主路径、R0、R1 与全部负例**共用同一 `compute(params)`**。
★ 判据非退化（承接 readme §4「命中 100% = 判据缺陷」）：并列 A1 下界轴 / A2 对照轴 / A3 反证扰动(NF1)。
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

# ---- 预注册常量（PREREG_7_9I_D2REVIEW.md §2.2，运行前冻结）----
HOP_MAX = 120
CAP_DOM = 60000
MAX_STEPS = 2000
DIR_OK = 30.0
OPP_MIN = 150.0
D_PAR = 60.0
CARRY_MIN = 0.50
MAX_ACTIVE = 1          # ★本刀唯一新自由度（R1 的「跨 1 条活边」）
K_POOLED = 5.5434

D1, D2, D3, D4, D5 = "D1_PARALLEL_SAME_DIR", "D2_OPPOSITE_LAYER", "D3_SAME_CORR_DOWNSTREAM", \
                     "D4_TOPOLOGICAL_ALTERNATIVE", "D5_NO_CARRIER_IN_DEPTH"
F_ADQ, F_LOW, F_NONE = "F_ADQ", "F_LOW", "F_NONE"

BASE = dict(max_active=MAX_ACTIVE, hop_max=HOP_MAX, cap_dom=CAP_DOM, max_steps=MAX_STEPS,
            dir_ok=DIR_OK, opp_min=OPP_MIN, d_par=D_PAR, carry_min=CARRY_MIN, flip=False)

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
in_live_cnt = np.bincount(G.t[LIVE], minlength=NN)
out_live_cnt = np.bincount(G.f[LIVE], minlength=NN)

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
DP = pd.read_csv(OUT / "o1d_trace_cards_7_9id1.csv", dtype={"section_id": str}).set_index("section_id")


def dead_chain(msi):
    """同向零流单链（承接 O1-续② / D-path，未改）。"""
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


def bfs_zero(seeds, hop_max, cap):
    """反向零流 BFS（带域上限）。"""
    dist = np.full(NN, -1, np.int32)
    q = deque(); nlab = 0; capped = False
    for n, dd in seeds.items():
        if dist[n] < 0:
            if nlab >= cap:
                capped = True; break
            dist[n] = dd; nlab += 1; q.append(n)
    while q:
        cur = q.popleft()
        dc = int(dist[cur])
        if dc >= hop_max:
            continue
        for j in incoming.get(int(cur), []):
            if flow[j] != 0:
                continue
            u = int(G.f[j])
            if dist[u] < 0:
                if nlab >= cap:
                    capped = True; break
                dist[u] = dc + 1; nlab += 1; q.append(u)
        if capped:
            break
    return dist, capped


def domain(headn, p, max_active):
    """dom(n) = 从 head 反向游走、经过活边数 ≤ max_active 时的最少跳数。"""
    dist, capped = bfs_zero({headn: 0}, int(p["hop_max"]), int(p["cap_dom"]))
    for _ in range(int(max_active)):
        dom = np.where(dist >= 0)[0]
        seeds = {}
        for v in dom:
            base = int(dist[v]) + 1
            if base > int(p["hop_max"]):
                continue
            for j in incoming.get(int(v), []):
                if flow[j] > 0:
                    u = int(G.f[j])
                    if u not in seeds or base < seeds[u]:
                        seeds[u] = base
        d2, c2 = bfs_zero(seeds, int(p["hop_max"]), int(p["cap_dom"]))
        upd = (d2 >= 0) & ((dist < 0) | (d2 < dist))
        dist[upd] = d2[upd]
        capped = bool(capped or c2)
    return dist, capped


def cand_arrays(dist):
    """候选活跃边（to(e) ∈ dom，hop ≥ 1），按 (hop, −flow, id) 排序。"""
    href = dist[T_LIVE]
    sel = href >= 1
    cand = LIVE[sel]
    hop = href[sel].astype(np.int64)
    fl = flow[cand]
    order = np.lexsort((cand, -fl, hop))
    return cand[order], hop[order], fl[order]


def live_chain(e0, max_steps):
    """单度活链 A*（承接 D-path，未改）。"""
    ch = [e0]
    seen = {int(G.f[e0]), int(G.t[e0])}
    cur = e0
    for _ in range(max_steps):
        v = int(G.f[cur])
        if in_live_cnt[v] != 1:
            break
        j = [x for x in incoming.get(v, []) if flow[x] > 0][0]
        if int(G.f[j]) in seen:
            break
        seen.add(int(G.f[j])); ch.insert(0, j); cur = j
    cur = e0
    for _ in range(max_steps):
        v = int(G.t[cur])
        if out_live_cnt[v] != 1:
            break
        j = [x for x in outgoing.get(v, []) if flow[x] > 0][0]
        if int(G.t[j]) in seen:
            break
        seen.add(int(G.t[j])); ch.append(j); cur = j
    return ch


def compute(p):
    """★主路径 / R0 / R1 / 全部负例共用：给定参数，返回 14 行 Card。"""
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
        CHX = G.ex[chain]; CHY = G.ey[chain]

        dist0, cap0 = domain(headn, p, 0)                       # R0 域（固定，恒 max_active=0）
        distX, capX = domain(headn, p, int(p["max_active"]))    # 实验域
        c0, h0, f0 = cand_arrays(dist0)
        cX, hX, fX = cand_arrays(distX)

        # ---- 下游同走廊活流（D3 判据，未改）----
        dn_live = 0
        for s in msi:
            dn_live += int(sum(1 for j in outgoing.get(int(G.t[s]), []) if flow[j] > 0))
        if dn_all:
            dn_live += int(sum(1 for j in outgoing.get(int(G.t[dn_all[-1]]), []) if flow[j] > 0))

        # ---- R0 复现：e_near + 分类（与 D-path 完全同一套规则）----
        if len(c0) == 0:
            r0_cls = D5
            r0 = dict(r0_e_near_id="-", r0_e_near_hop=np.nan, r0_dbear=np.nan,
                      r0_carry_scaled=np.nan, r0_carry_class=F_NONE, r0_d_own=np.nan)
        else:
            e_n = int(c0[0])
            ex, ey = float(G.ex[e_n]), float(G.ey[e_n])
            d_own = float(np.min(np.hypot(CHX - ex, CHY - ey)))
            db = round(float(circ_diff(float(bear_e[e_n]), sb_use)), 1)
            ch = live_chain(e_n, int(p["max_steps"]))
            flA_in = float(flow[ch[0]])
            carry = flA_in * A.SCALE / obs
            if (dn_live > 0):
                r0_cls = D3
            elif db >= p["opp_min"]:
                r0_cls = D2
            elif db <= p["dir_ok"] and d_own <= p["d_par"]:
                r0_cls = D1
            else:
                r0_cls = D4
            r0 = dict(r0_e_near_id=str(G.ids[e_n]), r0_e_near_hop=int(h0[0]), r0_dbear=db,
                      r0_carry_scaled=round(carry, 3),
                      r0_carry_class=(F_ADQ if carry >= p["carry_min"] else F_LOW),
                      r0_d_own=round(d_own, 1))

        # ---- R1：同向候选检索（双口径）----
        sd = dict(same_dir_candidate_found=False, same_dir_first_hop=-1, same_dir_first_dist=np.nan,
                  same_dir_flow=np.nan, carry_scaled=np.nan, same_dir_class=F_NONE,
                  same_dir_n=0, same_dir_fl_max=0.0, same_dir_carry_max=0.0, same_dir_d_min=np.nan,
                  same_dir_d_own_first=np.nan, same_dir_euc_dist=np.nan, same_dir_euc_hop=np.nan,
                  same_dir_euc_flow=np.nan, same_dir_euc_carry=np.nan,
                  same_dir_first_id="-", same_dir_euc_id="-")
        if len(cX) > 0:
            db_all = np.array([circ_diff(float(bear_e[j]), sb_use) for j in cX])
            m = db_all <= p["dir_ok"]
            n_sd = int(m.sum())
            sd["same_dir_n"] = n_sd
            if n_sd > 0:
                idx = np.where(m)[0]
                fl_sd = fX[idx]
                dd_sd = np.hypot(G.ex[cX[idx]] - hx, G.ey[cX[idx]] - hy)
                d_own_sd = np.array([float(np.min(np.hypot(CHX - float(G.ex[j]), CHY - float(G.ey[j]))))
                                     for j in cX[idx]])
                carry_sd = fl_sd * A.SCALE / obs
                i_h = int(idx[0])                       # hop 序（candX 已按 hop,−fl,id 排序）
                i_e = int(idx[int(np.argmin(dd_sd))])   # 欧氏序
                sd.update(
                    same_dir_candidate_found=True,
                    same_dir_first_hop=int(hX[i_h]), same_dir_first_dist=round(float(dd_sd[0]), 1),
                    same_dir_flow=round(float(fX[i_h]), 1), carry_scaled=round(float(carry_sd[0]), 3),
                    same_dir_fl_max=round(float(fl_sd.max()), 1),
                    same_dir_carry_max=round(float(carry_sd.max()), 3),
                    same_dir_d_min=round(float(d_own_sd.min()), 1),
                    same_dir_d_own_first=round(float(d_own_sd[0]), 1),
                    same_dir_euc_dist=round(float(dd_sd.min()), 1),
                    same_dir_euc_hop=int(hX[i_e]), same_dir_euc_flow=round(float(fX[i_e]), 1),
                    same_dir_euc_carry=round(float(fX[i_e] * A.SCALE / obs), 3),
                    same_dir_first_id=str(G.ids[cX[i_h]]), same_dir_euc_id=str(G.ids[cX[i_e]]))
                sd["same_dir_class"] = (F_ADQ if sd["same_dir_carry_max"] >= p["carry_min"] else F_LOW)

        rec = dict(section_id=sid, RoadName=ROAD[sid], obs_8_9=obs, dead_chain_len=len(chain),
                   head_node=headn, chain_bear=round(sb, 1),
                   dom0_n=int((dist0 >= 0).sum()), dom1_n=int((distX >= 0).sum()),
                   n_c0=int(len(c0)), n_c1=int(len(cX)), added_c=int(len(cX) - len(c0)),
                   r0_class=r0_cls, hr_capped=bool(capX))
        rec.update(r0); rec.update(sd)
        rec["confidence"] = ("high" if (rec["same_dir_n"] >= 20 and rec["same_dir_carry_max"] > 0)
                             else ("medium" if rec["same_dir_n"] > 0 else "low"))
        rows.append(rec)
    return pd.DataFrame(rows)


def sig(dfx):
    return (int((dfx["same_dir_class"] == F_ADQ).sum()),
            int((dfx["same_dir_class"] == F_LOW).sum()),
            int((dfx["same_dir_class"] == F_NONE).sum()),
            int(dfx["same_dir_candidate_found"].sum()),
            int(np.nansum(dfx["same_dir_first_hop"])),
            int(round(np.nansum(dfx["same_dir_carry_max"]) * 1000)),
            int(np.nansum(dfx["n_c1"])),
            int(np.nansum(dfx["same_dir_fl_max"])))


def main() -> int:
    t0 = time.time()
    rec: dict = {"step": "7.9I-D2-review/supply-object-retrieval-sensitivity", "scale": A.SCALE,
                 "hop_max": HOP_MAX, "cap_dom": CAP_DOM, "max_steps": MAX_STEPS,
                 "dir_ok_deg": DIR_OK, "opp_min_deg": OPP_MIN, "d_par_m": D_PAR,
                 "carry_min": CARRY_MIN, "max_active": MAX_ACTIVE, "k_pooled": K_POOLED,
                 "label": "RUN_PRE_REGISTERED_FROZEN"}
    gates: list = []

    # ---------- 门 1：坐标同源 + LENGTH 单位自检 ----------
    gx = pd.read_csv(E.SEC_GEO_7_6C, dtype={"lta_linkid": str}).set_index("lta_linkid")
    mx_ok = bool(0.0 < float(gx.loc[TGT[0], "mid_x"]) < 1.0e6)
    _m = (LEN_ARR > 50) & (np.hypot(G.nx[G.t] - G.nx[G.f], G.ny[G.t] - G.ny[G.f]) > 50)
    ratio_p50 = float(np.median(LEN_ARR[_m] / np.hypot(G.nx[G.t] - G.nx[G.f],
                                                       G.ny[G.t] - G.ny[G.f])[_m]))
    gates.append(["G-D2R-1 坐标同源 + LENGTH 单位自检（长边 LENGTH/欧氏 p50 ∈[0.99,1.01] ⇒ m）",
                  bool(mx_ok and 0.99 <= ratio_p50 <= 1.01),
                  f"mid_x 样例 {TGT[0]}={float(gx.loc[TGT[0], 'mid_x']):.1f}（SVY21）；"
                  f"n_long={int(_m.sum())}；比值 p50={ratio_p50:.4f} ⇒ 单位=m"])

    # ---------- 主运行（R1）----------
    d = compute(BASE)
    assert len(d) == 14, len(d)

    # ---------- 门 2：上游复现 ----------
    same_set = bool(set(d["section_id"]) == set(TGT))
    obs_sum = float(d["obs_8_9"].sum())
    gates.append(["G-D2R-2 上游复现（D 类 14 节，Σobs = 28,361.0，与 O1-续② 卡片一致）",
                  bool(len(d) == 14 and same_set and abs(obs_sum - 28361.0) < 1e-6),
                  f"n={len(d)}；Σobs={obs_sum:.1f}；集合一致={same_set}"])

    # ---------- 门 3：★R0 复现（与 D-path 卡片逐节一致）----------
    dpath_cls = DP["final_class"].reindex(d["section_id"]).to_numpy()
    dpath_enear = DP["e_near_id"].astype(str).reindex(d["section_id"]).to_numpy()
    cls_same = bool((d["r0_class"].to_numpy() == dpath_cls).all())
    enear_same = bool((d["r0_e_near_id"].astype(str).to_numpy() == dpath_enear).all())
    vc0 = d["r0_class"].value_counts().to_dict()
    gates.append(["G-D2R-3 ★R0 复现（MAX_ACTIVE=0 ⇒ r0_class 与 D-path 卡片逐节一致 ∧ e_near_id 逐节一致）",
                  bool(cls_same and enear_same),
                  f"分类逐节一致={cls_same}；e_near_id 一致={enear_same}；分布={vc0}"])

    # ---------- 门 4：冻结对账 ----------
    smx = SS["sim_median_xS"].reindex(d["section_id"]).to_numpy(float)
    gates.append(["G-D2R-4 冻结对账（14 节 sim_median_xS 全为 0）",
                  bool(np.nanmax(np.abs(smx)) == 0.0), f"max|sim_median_xS|={np.nanmax(np.abs(smx)):.3e}"])

    # ---------- 门 5：★R1 杠杆非空 ----------
    subset = bool((d["dom1_n"] >= d["dom0_n"]).all())
    added = int(d["added_c"].sum())
    n_added_sec = int((d["added_c"] > 0).sum())
    gates.append(["G-D2R-5 ★R1 杠杆非空（dom₁ ⊇ dom₀ 逐节 ∧ ΣΔn_c > 0 ∧ ≥1 节新增候选）",
                  bool(subset and added > 0 and n_added_sec >= 1),
                  f"子集关系={subset}；ΣΔn_c=+{added}；新增节数={n_added_sec}/14；"
                  f"dom 增量 Σ={int((d['dom1_n'] - d['dom0_n']).sum())} 节点"])

    # ---------- 门 6：★判别量非退化（A1 下界轴）----------
    hv = d["same_dir_first_hop"].replace(-1, np.nan).dropna()
    dv = d["same_dir_first_dist"].dropna()
    fv = d["same_dir_flow"].dropna()
    cv = d["same_dir_carry_max"]
    # ★注意：本门**不**要求 same_dir_class ≥2 类 —— 预期结果即全 F_LOW（单一取值）。
    #   防「命中 100% = 判据缺陷」的职责由 A1 连续轴（本门 carry_max）与 G-D2R-8（NF1 反证）承担。
    ok6 = bool(hv.nunique() >= 2 and dv.nunique() >= 2 and fv.nunique() >= 2
               and cv.nunique() >= 2 and (cv.max() - cv.min()) > 0)
    gates.append(["G-D2R-6 ★判别量非退化（hop/dist/flow/carry_max 各 ≥2 取值 ∧ carry_max 极差>0；class 允许单一）",
                  ok6,
                  f"hop uniq={hv.nunique()}；dist uniq={dv.nunique()}；flow uniq={fv.nunique()}；"
                  f"carry_max uniq={cv.nunique()} range=[{cv.min()},{cv.max()}]；class={d['same_dir_class'].value_counts().to_dict()}"])

    # ---------- 门 7：Card 完备 ----------
    req = ["section_id", "obs_8_9", "dead_chain_len", "head_node", "chain_bear", "dom0_n", "dom1_n",
           "n_c0", "n_c1", "added_c", "r0_class", "r0_e_near_id", "r0_e_near_hop", "r0_dbear",
           "r0_carry_scaled", "r0_carry_class", "same_dir_candidate_found", "same_dir_first_hop",
           "same_dir_first_dist", "same_dir_flow", "carry_scaled", "same_dir_class", "same_dir_n",
           "same_dir_fl_max", "same_dir_carry_max", "same_dir_d_min", "same_dir_euc_dist",
           "same_dir_euc_hop", "same_dir_euc_flow", "same_dir_euc_carry", "confidence",
           "same_dir_first_id", "same_dir_euc_id"]
    miss = [c for c in req if c not in d.columns]
    nan_req = [c for c in ["section_id", "dead_chain_len", "same_dir_class", "same_dir_n",
                           "dom0_n", "dom1_n"] if d[c].isna().any()]
    gates.append(["G-D2R-7 Card 完备（14 行 × §2.4 字段；same_dir_class ⊆ {F_ADQ,F_LOW,F_NONE}）",
                  bool(len(d) == 14 and not miss and not nan_req
                       and set(d["same_dir_class"]) <= {F_ADQ, F_LOW, F_NONE}),
                  f"缺失列={miss}；必填 NaN={nan_req}；classes={sorted(set(d['same_dir_class']))}"])

    # ---------- 门 8：★判据可产出 F_ADQ（防 100% 判据缺陷；A3 反证轴）----------
    n_adq_main = int((d["same_dir_class"] == F_ADQ).sum())
    _pN = dict(BASE); _pN["flip"] = True
    dN = compute(_pN)
    n_adq_flip = int((dN["same_dir_class"] == F_ADQ).sum())
    m_sec = dN.loc[dN["same_dir_class"] == F_ADQ, "section_id"].tolist()
    gates.append(["G-D2R-8 ★判据可产出 F_ADQ（NF1 方位+180° ⇒ F_ADQ ≥4 节 ∧ 主路径 F_ADQ == 0 节）",
                  bool(n_adq_flip >= 4 and n_adq_main == 0),
                  f"主路径 F_ADQ={n_adq_main}/14；NF1 F_ADQ={n_adq_flip}/14（{m_sec}）⇒ 判据非恒假"])

    # ---------- 门 9：确定性自检 ----------
    src = Path(__file__).read_text(encoding="utf-8")
    bad = []
    for nd in ast.walk(ast.parse(src)):
        if isinstance(nd, ast.Attribute) and nd.attr in {"random", "shuffle", "rand", "randn", "randint"}:
            bad.append(nd.attr)
        if isinstance(nd, ast.Name) and nd.id == "random":
            bad.append("name:random")
    shared = bool("def compute(p)" in src and src.count("compute(") >= 7)
    gates.append(["G-D2R-9 确定性自检（AST 无随机源 ∧ 14 行 ∧ R0/R1/负例共用 compute(params)）",
                  bool(len(bad) == 0 and len(d) == 14 and shared),
                  f"随机源 {len(bad)} 个；卡片 {len(d)} 行；compute 共用={'✓' if shared else '✗'}"])

    # ---------- 门 10：★距离口径自洽（由 card 内边 id 反算；无阈值）----------
    SPAN = float(np.hypot(G.nx.max() - G.nx.min(), G.ny.max() - G.ny.min()))
    bad10 = []
    for r in d.itertuples():
        if not r.same_dir_candidate_found:
            continue
        hn = int(r.head_node)
        j1 = id2i[str(r.same_dir_first_id)]
        j2 = id2i[str(r.same_dir_euc_id)]
        d1 = float(np.hypot(G.ex[j1] - float(G.nx[hn]), G.ey[j1] - float(G.ny[hn])))
        d2 = float(np.hypot(G.ex[j2] - float(G.nx[hn]), G.ey[j2] - float(G.ny[hn])))
        if abs(d1 - float(r.same_dir_first_dist)) > 0.06 or abs(d2 - float(r.same_dir_euc_dist)) > 0.06:
            bad10.append(f"{r.section_id}(first {d1:.1f}vs{r.same_dir_first_dist}/euc {d2:.1f}vs{r.same_dir_euc_dist})")
        if float(r.same_dir_euc_dist) > SPAN or float(r.same_dir_first_dist) > SPAN:
            bad10.append(f"{r.section_id}(超出全网坐标跨度 {SPAN:.0f}m)")
    gates.append(["G-D2R-10 ★距离口径自洽（逐节由边 id 反算 head 距离 |Δ|<0.06 m ∧ ≤ 全网坐标跨度）",
                  bool(len(bad10) == 0),
                  f"全网坐标跨度={SPAN:.0f} m；违规={bad10 if bad10 else '无'}"
                  f"；max(first_dist)={float(d['same_dir_first_dist'].max()):.1f} m"])

    # ---------- 负例（6，全部与主路径共用 compute）----------
    s0 = sig(d)
    neg = []
    for nm, kw in [("N1 MAX_ACTIVE 1→0（R1 退化为 R0）", dict(max_active=0)),
                   ("N2 HOP_MAX 120→2（上游域压到 2 层）", dict(hop_max=2)),
                   ("N3 DIR_OK 30→180（同向=全方向）", dict(dir_ok=180.0)),
                   ("NF1 参考方位 +180°（同向↔对向互换）", dict(flip=True)),
                   ("N5 CARRY_MIN 0.50→0.20（阈值放松）", dict(carry_min=0.20)),
                   ("N6 CAP_DOM 60000→2000（域截断）", dict(cap_dom=2000))]:
        p = dict(BASE); p.update(kw)
        sn = sig(compute(p))
        neg.append({"neg": nm, "fired": bool(sn != s0), "sig_base": list(s0), "sig_pert": list(sn)})
    gates.append(["G-D2R-N 负例 6/6 fired（非同构扰动 ∧ 与主路径共用 compute ⇒ 无空扰动风险）",
                  all(x["fired"] for x in neg),
                  "；".join(f"{x['neg'][:2]}{'✓' if x['fired'] else '✗'}" for x in neg)])

    # ---------- 汇总 ----------
    obs_sum2 = float(d["obs_8_9"].sum())
    d2m = d["r0_class"] == D2
    d2sub = d[d2m]
    sd_cls = {k: int(v) for k, v in d["same_dir_class"].value_counts().items()}
    obs_by_sd = {k: float(d.loc[d.same_dir_class == k, "obs_8_9"].sum()) for k in sd_cls}
    rec["summary"] = {
        "scope": "D 类 14 节（Σobs=%.1f）；重点 = 原 D2 六节" % obs_sum2,
        "obs_sum": obs_sum2,
        "r0_class_counts": {k: int(v) for k, v in d["r0_class"].value_counts().items()},
        "r0_obs_by_class": {k: float(d.loc[d.r0_class == k, "obs_8_9"].sum())
                            for k in d["r0_class"].unique()},
        "★D2_six": {
            "n": int(len(d2sub)), "obs": float(d2sub["obs_8_9"].sum()),
            "share_of_D": round(float(d2sub["obs_8_9"].sum()) / obs_sum2, 4),
            "same_dir_class": {k: int(v) for k, v in d2sub["same_dir_class"].value_counts().items()},
            "carry_max_list": {r.section_id: float(r.same_dir_carry_max) for r in d2sub.itertuples()},
            "verdict": ("F_ADQ=%d/6" % int((d2sub["same_dir_class"] == F_ADQ).sum())),
        },
        "same_dir_class_counts": sd_cls,
        "same_dir_obs_by_class": obs_by_sd,
        "same_dir_share_by_class": {k: round(v / obs_sum2, 4) for k, v in obs_by_sd.items()},
        "A1_carry_bound": {
            "axis": "A1 下界轴：同向候选全子集的 carry_scaled 上界（same_dir_carry_max）",
            "carry_min": CARRY_MIN,
            "n_below_min": int((d["same_dir_carry_max"] < CARRY_MIN).sum()),
            "values": {r.section_id: float(r.same_dir_carry_max) for r in d.itertuples()},
            "range": [float(d["same_dir_carry_max"].min()), float(d["same_dir_carry_max"].max())],
        },
        "A2_r0_contrast": {
            "axis": "A2 对照轴：R0 选中（多为对向）对象的 carry_scaled —— 证明域内确有高承载对象",
            "r0_carry_scaled": {r.section_id: (None if r.r0_carry_scaled != r.r0_carry_scaled
                                               else float(r.r0_carry_scaled)) for r in d.itertuples()},
            "r0_carry_max": float(np.nanmax(d["r0_carry_scaled"].to_numpy(float))),
            "n_r0_adq": int((d["r0_carry_class"] == F_ADQ).sum()),
        },
        "A3_flip_falsification": {
            "axis": "A3 反证轴：NF1（方位 +180°）下 F_ADQ 节数与身份",
            "n_adq_flip": n_adq_flip,
            "sections_flip_adq": m_sec,
            "n_adq_main": n_adq_main,
        },
        "domain_growth": {"sum_dom0": int(d["dom0_n"].sum()), "sum_dom1": int(d["dom1_n"].sum()),
                          "sum_nc0": int(d["n_c0"].sum()), "sum_nc1": int(d["n_c1"].sum()),
                          "hr_capped_sections": int(d["hr_capped"].sum())},
        "diagnostics": {
            "topo_vs_euc_same_dir": int((d["same_dir_first_hop"].replace(-1, np.nan).notna()
                                         & (d["same_dir_euc_hop"] == d["same_dir_first_hop"])).sum()),
            "note": "hop 序与欧氏序一致节数（不一致 ⇒ 零流团惰性遍历伪影，必须同报）",
            "same_dir_d_own_min": float(np.nanmin(d["same_dir_d_own_first"].to_numpy(float))),
            "same_dir_within_60m_of_chain": int((d["same_dir_d_own_first"] <= D_PAR).sum()),
        },
        "k_pooled_disclosure": ("carry_* 为「单条 MATSim 边流量 / 单 LTA 断面观测」之比，K_pooled=5.5434 "
                                "⇒ 仅量级参照，不作独立判据"),
    }
    # ---------- ★R0 域自身是否已含同向候选（回答「域是否过窄」的第一手数据）----------
    _p0 = dict(BASE); _p0["max_active"] = 0
    d0 = compute(_p0)
    rec["summary"]["R0_domain_same_dir"] = {
        "note": "R0（冻结域，零流-only）**自身**的同向候选统计 —— 若已非空，则「域过窄把同向对象排除掉」不成立",
        "n_sections_with_same_dir": int((d0["same_dir_n"] > 0).sum()),
        "n_same_dir": {r.section_id: int(r.same_dir_n) for r in d0.itertuples()},
        "carry_max": {r.section_id: float(r.same_dir_carry_max) for r in d0.itertuples()},
        "range": [float(d0["same_dir_carry_max"].min()), float(d0["same_dir_carry_max"].max())],
        "n_carry_max_ge_min": int((d0["same_dir_carry_max"] >= CARRY_MIN).sum()),
    }
    rec["negatives"] = neg
    rec["criteria_revision"] = [
        {"id": "R1", "when": "首跑后（`D2REVIEW_READY` 已出，正式结论写盘前）",
         "what": "`same_dir_euc_dist` 误把**候选数组序号**当**全局边索引**（`G.ex[i_e]`）",
         "why": "**实现缺陷**：`i_e` 是候选数组 `cX` 内的位置，正确距离应为 `dd_sd.min()`。"
                "首跑该列出现 1.5e4–2.4e4 m 的物理不可能值（新加坡南北向 < 25 km）",
         "fix": "改为 `round(float(dd_sd.min()), 1)`；**并新增硬门 `G-D2R-10`**（由 card 内边 id 反算距离，"
                "|Δ|<0.06 m 且 ≤ 全网坐标跨度）—— 该门在缺陷版下会 FAIL，用于堵住「无门可拦」的缺口",
         "note": "主判据/阈值/`same_dir_first_*`/`same_dir_carry_max`/`sd_class` **全部未变**；"
                 "属**实现缺陷 + 门禁缺口**，非科学结论"},
    ]
    rec["gates"] = [{"gate": g, "pass": bool(pp), "measured": m} for g, pp, m in gates]
    rec["n_fail"] = int(sum(1 for _, pp, _ in gates if not pp))
    rec["verdict"] = ("D2REVIEW_READY" if rec["n_fail"] == 0 else "D2REVIEW_BLOCKED")
    rec["elapsed_s"] = round(time.time() - t0, 1)

    csv_p = OUT / "o1e_d2rev_cards_7_9id2.csv"
    d.to_csv(csv_p, index=False, encoding="utf-8-sig")
    # ★顺序纪律：先写被哈希产物 → 再算哈希 → 最后写 JSON
    rec["cards_sha256_16"] = hashlib.sha256(csv_p.read_bytes()).hexdigest()[:16]
    (OUT / "o1e_d2rev_summary_7_9id2.json").write_text(
        json.dumps(rec, ensure_ascii=False, indent=1), encoding="utf-8")

    print("\n===== GATES =====")
    for g, pp, m in gates:
        print(f"  [{'PASS' if pp else 'FAIL'}] {g}\n          | {m}")
    pd.set_option("display.width", 320)
    print("\n===== D2-review Card（14 节）=====")
    cols = ["section_id", "RoadName", "obs_8_9", "r0_class", "r0_dbear", "r0_carry_scaled",
            "dom0_n", "dom1_n", "n_c0", "n_c1", "same_dir_candidate_found", "same_dir_first_hop",
            "same_dir_first_dist", "same_dir_flow", "carry_scaled", "same_dir_carry_max",
            "same_dir_class", "same_dir_euc_dist", "same_dir_euc_flow"]
    print(d[cols].to_string(index=False))
    print("\n===== 汇总 =====")
    print("R0 class:", rec["summary"]["r0_class_counts"])
    print("★D2 六节:", rec["summary"]["★D2_six"]["verdict"],
          "carry_max:", rec["summary"]["★D2_six"]["carry_max_list"])
    print("same_dir_class:", sd_cls, "obs:", obs_by_sd)
    print("A1 下界轴 carry_max range:", rec["summary"]["A1_carry_bound"]["range"],
          "n_below_min:", rec["summary"]["A1_carry_bound"]["n_below_min"])
    print("A2 对照轴 r0_carry_max:", rec["summary"]["A2_r0_contrast"]["r0_carry_max"],
          "n_r0_adq:", rec["summary"]["A2_r0_contrast"]["n_r0_adq"])
    print("A3 反证轴 NF1 F_ADQ:", n_adq_flip, m_sec)
    print("R0 域自身同向候选：节数=", rec["summary"]["R0_domain_same_dir"]["n_sections_with_same_dir"],
          "carry_max range:", rec["summary"]["R0_domain_same_dir"]["range"],
          "≥0.5 节数:", rec["summary"]["R0_domain_same_dir"]["n_carry_max_ge_min"])
    print("domain_growth:", rec["summary"]["domain_growth"])
    print("cards_sha256_16:", rec["cards_sha256_16"])
    print(f"\nVERDICT={rec['verdict']}  n_fail={rec['n_fail']}  {rec['elapsed_s']}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
