# -*- coding: utf-8 -*-
"""Step 7.9I-B(b)-P · 零流量断面的「方向一致性 / 对向孪生」后验探针（零仿真、只读）

⛔ 标签 = `EXPLORATORY_POST_HOC`。
它不是 7.9I-B(b) 预注册的一部分：预注册文件 `PREREG_7_9I_Bb.md` 与引擎
`audit_zero_flow_ledger_7_9ibb.py` 的判据/阈值**未被改动**，本脚本是在看到
7.9I-B(b) 结果之后**追加**的解释性核验，用于回答两个预注册没有直接覆盖的问题：

  Q1（方向性）  crosswalk 选出的匹配边，方向是否与 LTA 断面一致？
                 —— 若大量反向，则 7.9I-B(b) 的 `n_par_same=0` 是「映射选错方向」的伪影。
  Q2（孪生）    邻近承载流量的「反向」边，在网络里是否存在**同节点对的反向孪生**？
                 —— 存在 ⇒ 该设施被建模为双向 way；不存在 ⇒ 被建模为单向 way
                    （对向车行道以独立节点串另建）。

⛔ 坐标纪律（本脚本的存在理由之一）：断面位置取 `SEC_GEO_7_6C.mid_x/mid_y`（**SVY21**），
   ⛔ 不得取 `lta_section_geometry().mx/my`（**局部等距平面米 ≈1.15e7，与全网图不同源**）。
   首次探针即因混用二者而得到 `n_same=n_opp=0` 的全零伪影。
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
from audit_corridor_scale_7_9ia import load_frozen, OUT  # noqa: E402
from audit_m1_accessibility_7_9ib import Graph          # noqa: E402
from audit_kpe_ecp_object_7_9ia2 import lta_section_geometry  # noqa: E402

CACHE_NET = ROOT / "scripts" / "od" / "_cache_network_7_9c0.npz"
MAJOR = {"motorway", "motorway_link", "trunk", "trunk_link"}
R = 100.0
DIR_OK = 30.0
SAME_MAX = 30.0     # |Δbear| ≤ 30° ⇒ 同向
OPP_MIN = 150.0     # |Δbear| ≥ 150° ⇒ 反向


def circ_diff(a, b):
    return abs(((a - b + 180.0) % 360.0) - 180.0)


def main() -> int:
    t0 = time.time()
    rec: dict = {"step": "7.9I-B(b)-P/direction-and-twin-probe",
                 "label": "EXPLORATORY_POST_HOC",
                 "radius_m": R, "dir_ok_deg": DIR_OK, "scale": A.SCALE}
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

    # 同节点对反向索引： (t,f) -> [edge …]
    rev: dict = {}
    for i in range(G.n_edges):
        rev.setdefault((int(G.t[i]), int(G.f[i])), []).append(i)

    gl = lta_section_geometry(ev1.TRAFFIC).set_index("LinkID")          # bear/len_m 用
    geo = pd.read_csv(E.SEC_GEO_7_6C, dtype={"lta_linkid": str}).set_index("lta_linkid")  # SVY21 用
    bb = pd.read_csv(OUT / "bb_zero_flow_ledger_7_9ibb.csv", dtype={"lta_linkid": str})
    assert len(bb) == 38, len(bb)

    # ---------- 构造性断言：坐标必须同源 ----------
    cand = [x for x in bb["lta_linkid"].tolist() if x in geo.index]
    assert cand, "无任何断面命中 SEC_GEO"
    dchk = np.array([np.hypot(float(geo.loc[s, "mid_x"]) - float(geo.loc[s, "mid_y"]),
                              float(geo.loc[s, "mid_x"]) - float(geo.loc[s, "mid_y"])) for s in cand])
    assert np.isfinite(dchk).all()
    sample = cand[0]
    assert 0.0 < float(geo.loc[sample, "mid_x"]) < 1.0e6, \
        f"SEC_GEO 坐标疑似非同源: {float(geo.loc[sample,'mid_x'])}"
    gates.append(["G-P0 坐标同源（SEC_GEO 落在 SVY21 量级 <1e6）",
                  float(geo.loc[sample, "mid_x"]) < 1.0e6,
                  f"样例 {sample} mid_x={float(geo.loc[sample,'mid_x']):.1f}"])

    rows = []
    for sid in bb["lta_linkid"].tolist():
        srow = bb[bb["lta_linkid"] == sid].iloc[0]
        mx = float(geo.loc[sid, "mid_x"])
        my = float(geo.loc[sid, "mid_y"])
        sb = float(gl.loc[sid, "bear"])
        mi = [id2i[x] for x in cw.loc[cw["lta_linkid"] == sid, "matsim_link_id"].tolist()
              if x in id2i]
        ms = set(mi)
        dm = circ_diff(bear_e[np.array(mi)], sb) if mi else np.array([np.nan])

        cond = (((G.ex - mx) ** 2 + (G.ey - my) ** 2) < R * R) & is_major & (flow > 0) \
            & (~np.isin(np.arange(G.n_edges), list(ms)))
        near = np.where(cond)[0]
        same = np.array([e for e in near if circ_diff(bear_e[e], sb) < DIR_OK], np.int64)
        opp = np.array([e for e in near
                        if circ_diff(bear_e[e], (sb + 180.0) % 360.0) < DIR_OK], np.int64)
        twin_exist = int(sum(1 for e in opp if (int(G.f[e]), int(G.t[e])) in rev))
        twin_matched = int(sum(1 for e in opp
                               if any(j in ms for j in rev.get((int(G.f[e]), int(G.t[e])), []))))

        rows.append(dict(
            lta_linkid=sid, class_bb=srow["class_bb"], RoadCat=srow["RoadCat"],
            obs_8_9=float(srow["obs_8_9"]), n_matched=len(ms),
            n_match_same=int((dm <= SAME_MAX).sum()),
            n_match_opp=int((dm >= OPP_MIN).sum()),
            n_match_mid=int(((dm > SAME_MAX) & (dm < OPP_MIN)).sum()),
            d_match_max=float(np.nanmax(dm)) if mi else np.nan,
            n_par_same=len(same), n_par_opp=len(opp),
            par_opp_flow_xS=float(sum(flow[e] for e in opp)) * A.SCALE if len(opp) else 0.0,
            twin_exist=twin_exist, twin_matched=twin_matched,
        ))
    d = pd.DataFrame(rows)

    # ---------- 门 ----------
    n_m = int(d["n_matched"].sum())
    n_ms = int(d["n_match_same"].sum())
    n_mo = int(d["n_match_opp"].sum())
    gates.append(["G-P1 匹配边方向一致：反向匹配边 = 0", n_mo == 0,
                  f"匹配边 {n_m} 条，同向(≤30°) {n_ms}，反向(≥150°) {n_mo}"])
    gates.append(["G-P2 每断面同向匹配边占比 ≥ 0.8",
                  bool(((d["n_match_same"] / d["n_matched"]) >= 0.8).all()),
                  f"最小占比 {float((d['n_match_same']/d['n_matched']).min()):.2f}"])
    # 与冻结引擎逐位对账
    chk = d.set_index("lta_linkid").join(
        bb.set_index("lta_linkid")[["n_par_same_100", "n_par_opp_100"]])
    ok_same = bool((chk["n_par_same"] == chk["n_par_same_100"]).all())
    ok_opp = bool((chk["n_par_opp"] == chk["n_par_opp_100"]).all())
    gates.append(["G-P3 与冻结引擎逐位对账 n_par_same_100", ok_same,
                  f"全等={ok_same}  Σsame={int(d['n_par_same'].sum())}"])
    gates.append(["G-P4 与冻结引擎逐位对账 n_par_opp_100", ok_opp,
                  f"全等={ok_opp}  Σopp={int(d['n_par_opp'].sum())}"])
    gates.append(["G-P5 孪生核验非退化（存在与不存在都出现）",
                  bool(0 < int((d["twin_exist"] > 0).sum()) < len(d)),
                  f"有孪生 {int((d['twin_exist']>0).sum())}/{len(d)} 节"])

    # ---------- 分类汇总 ----------
    summ = {}
    for c in ["B1_SAME_DIR_PARALLEL", "B2_OPPOSITE_ONLY", "B3_NO_PARALLEL_FLOW"]:
        w = d[d["class_bb"] == c]
        if not len(w):
            continue
        summ[c] = dict(n=int(len(w)), obs=float(w["obs_8_9"].sum()),
                       n_matched=int(w["n_matched"].sum()),
                       n_match_same=int(w["n_match_same"].sum()),
                       n_match_opp=int(w["n_match_opp"].sum()),
                       n_par_same=int(w["n_par_same"].sum()),
                       n_par_opp=int(w["n_par_opp"].sum()),
                       twin_exist=int((w["twin_exist"] > 0).sum()),
                       twin_matched=int((w["twin_matched"] > 0).sum()))
    rec["by_class"] = summ
    rec["total"] = dict(n=len(d), obs=float(d["obs_8_9"].sum()),
                        n_matched=n_m, n_match_same=n_ms, n_match_opp=n_mo,
                        n_par_same=int(d["n_par_same"].sum()),
                        n_par_opp=int(d["n_par_opp"].sum()),
                        twin_exist_sections=int((d["twin_exist"] > 0).sum()))
    rec["gates"] = [{"gate": g, "pass": bool(p), "measured": m} for g, p, m in gates]
    rec["n_fail"] = int(sum(1 for _, p, _ in gates if not p))
    rec["verdict"] = ("BB_DIRECTION_PROBE_READY" if rec["n_fail"] == 0
                      else "BB_DIRECTION_PROBE_BLOCKED")
    rec["elapsed_s"] = round(time.time() - t0, 1)

    d.to_csv(OUT / "bbp_direction_probe_7_9ibbp.csv", index=False, encoding="utf-8-sig")
    (OUT / "bbp_direction_probe_summary_7_9ibbp.json").write_text(
        json.dumps(rec, ensure_ascii=False, indent=1), encoding="utf-8")

    print("\n===== GATES =====")
    for g, p, m in gates:
        print(f"  [{'PASS' if p else 'FAIL'}] {g}  |  {m}")
    print("\n===== SUMMARY =====")
    for c, v in summ.items():
        print(f"  {c:22s} n={v['n']:2d} 匹配边={v['n_matched']:3d}(同向{v['n_match_same']:3d}/反向{v['n_match_opp']:d})"
              f"  同向平行={v['n_par_same']:3d} 反向平行={v['n_par_opp']:3d}"
              f"  有对向孪生={v['twin_exist']}/{v['n']}")
    print(f"\nVERDICT={rec['verdict']}  n_fail={rec['n_fail']}  {rec['elapsed_s']}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
