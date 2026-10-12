#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""
esb04_section_decomp.py — E-SB-04 阶段 3：验证 E-SB-03 主要增量
================================================================
★零仿真 · 只读。固定 E-SB-03 的断面集合 / 聚合规则(median) / SCALE。
逐断面 ΔQ_g = Q_sim,SB-A5,g − Q_sim,v1.0,g；并做：
  - 全网 / 观测匹配边 / LTA 断面 三层级
  - 道路等级（highway）与走廊（RoadName）集中度
  - 对向 link / 平行近重复 link / 1:K 聚合 的替代分布
  - 路线变化指标（阶段 2）× ΔQ 的对应关系
产物 → reports/path_redistribution_audit_E_SB_04/
"""
from __future__ import annotations

import json
import re
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(r"D:\Luan\2026-05\2_Singapore")
OUT = ROOT / "reports" / "path_redistribution_audit_E_SB_04"
E3_AUDIT = ROOT / "experiments" / "E-SB-03_flow_shift_audit" / "audit"
E2_AUDIT = ROOT / "experiments" / "E-SB-02_night_freeflow" / "audit"

CW = ROOT / "reports" / "od_final_calibration_crosswalk_7_3_6" / "final_calibration_crosswalk.csv"
SEC_DELTA = E3_AUDIT / "esb03_section_delta.csv"
V10_ALL = E3_AUDIT / "v1.0_allhours_conv.linkstats.txt.gz"
A5_ALL = E3_AUDIT / "SB-A5_allhours_conv.linkstats.txt.gz"

SCALE = 459794.0 / 200000.0

CORRIDORS = {
    "PIE": r"pan[- ]?island expressway", "TPE": r"tampines expressway",
    "CTE": r"central expressway", "KPE": r"kallang[- ]?paya lebar expressway",
    "KJE": r"kranji expressway", "AYE": r"ayer rajah expressway",
    "SLE": r"seletar expressway", "BKE": r"bukit timah expressway",
    "MCE": r"marina co[a-z]*tal expressway", "ECP": r"east coast parkway",
}
GATES: list[dict] = []


def gate(cid, name, ok, detail=""):
    GATES.append({"id": cid, "gate": name, "pass": bool(ok), "detail": detail})
    print(f"  [{'PASS' if ok else 'FAIL'}] {cid}  {name}" + (f"  | {detail}" if detail else ""), flush=True)
    return bool(ok)


def corridor_code(name: str) -> str:
    n = (name or "").lower()
    for code, pat in CORRIDORS.items():
        if re.search(pat, n):
            return code
    return ""


def opposite(link_id: str) -> str | None:
    m = re.match(r"e(\d+)_(\d+)$", link_id)
    return f"e{m.group(2)}_{m.group(1)}" if m else None


def main() -> int:
    print("=" * 100)
    print("E-SB-04 阶段 3：验证 E-SB-03 主要增量（逐断面 ΔQ / 集中度 / 对向·平行 link）")
    print("=" * 100)

    cw = pd.read_csv(CW, encoding="utf-8-sig", low_memory=False)
    cw["lta_linkid"] = cw["lta_linkid"].astype(str)
    cw["matsim_link_id"] = cw["matsim_link_id"].astype(str)
    n_sec = cw["lta_linkid"].nunique()
    print(f"[in ] crosswalk: {len(cw)} 匹配边 / {n_sec} 断面")
    gate("H01", "crosswalk 匹配边数 = 3193 且断面 = 576", len(cw) == 3193 and n_sec == 576,
         f"edges={len(cw)} sections={n_sec}")

    sec = pd.read_csv(SEC_DELTA, encoding="utf-8-sig", low_memory=False)
    sec["lta_linkid"] = sec["lta_linkid"].astype(str)
    gate("H02", "E-SB-03 逐断面表 = 576 行", len(sec) == 576, f"rows={len(sec)}")

    v10 = pd.read_csv(V10_ALL, sep="\t", usecols=["LINK", "HRS8-9avg"], low_memory=False)
    a5 = pd.read_csv(A5_ALL, sep="\t", usecols=["LINK", "HRS8-9avg"], low_memory=False)
    v10["LINK"] = v10["LINK"].astype(str)
    a5["LINK"] = a5["LINK"].astype(str)
    sv = dict(zip(v10["LINK"], v10["HRS8-9avg"]))
    sa = dict(zip(a5["LINK"], a5["HRS8-9avg"]))

    # ---------------- 三层级 ----------------
    print("\n[3.0] 三层级：全网 / 观测匹配边 / LTA 断面（08-09, cycle it.10-19）")
    matched = set(cw["matsim_link_id"])
    rows = []
    for lab, svv in (("v1.0", sv), ("SB-A5", sa)):
        net_all = float(sum(x for x in svv.values() if x == x))
        net_match = float(sum(svv.get(e, 0.0) for e in matched if svv.get(e, 0.0) == svv.get(e, 0.0)))
        rows.append({"arm": lab, "level": "network_all_links_raw", "value": net_all})
        rows.append({"arm": lab, "level": "matched_edges_raw", "value": net_match})
    # 断面层（scaled）
    for lab, col in (("v1.0", "scaled_v10"), ("SB-A5", "scaled_a5")):
        rows.append({"arm": lab, "level": "lta_section_scaled", "value": float(sec[col].sum())})
    tl = pd.DataFrame(rows).pivot(index="level", columns="arm", values="value")
    tl["d_pct_A5_v10"] = (tl["SB-A5"] / tl["v1.0"] - 1) * 100
    tl = tl.reset_index()
    tl.to_csv(OUT / "three_level_summary.csv", index=False, encoding="utf-8-sig")
    for _, r in tl.iterrows():
        print(f"    {r['level']:22s} v1.0={r['v1.0']:>15,.1f}  SB-A5={r['SB-A5']:>15,.1f}  Δ={r['d_pct_A5_v10']:+.2f}%")
    gate("H03", "全网 vs 匹配边 方向相反（匹配边升、全网持平/降）",
         (tl.loc[tl.level == "matched_edges_raw", "d_pct_A5_v10"].iloc[0] > 0)
         and (tl.loc[tl.level == "network_all_links_raw", "d_pct_A5_v10"].iloc[0] < 1.0),
         " | ".join(f"{r['level']}:{r['d_pct_A5_v10']:+.2f}%" for _, r in tl.iterrows()))

    # ---------------- 逐边 ΔQ ----------------
    print("\n[3.1] 逐匹配边 ΔQ（edge-level）与对向/平行检测")
    e = cw[["lta_linkid", "matsim_link_id", "highway", "distance_m", "direction_diff_deg",
            "direction_ok", "name_match"]].copy()
    e["name"] = cw["RoadName"] if "RoadName" in cw.columns else ""
    e["corridor"] = e["name"].map(corridor_code)
    e["sim_v10"] = e["matsim_link_id"].map(sv).astype(float)
    e["sim_a5"] = e["matsim_link_id"].map(sa).astype(float)
    e["dQ_edge_raw"] = e["sim_a5"].fillna(0) - e["sim_v10"].fillna(0)
    e["dQ_edge_scaled"] = e["dQ_edge_raw"] * SCALE
    # 对向 link
    cw_ids = set(cw["matsim_link_id"])
    sec_of = dict(zip(cw["matsim_link_id"], cw["lta_linkid"]))
    e["opposite_link"] = e["matsim_link_id"].map(opposite)
    e["opposite_in_matched"] = e["opposite_link"].isin(cw_ids)
    e["opposite_same_section"] = [bool(o in sec_of and sec_of[o] == s)
                                  for o, s in zip(e["opposite_link"], e["lta_linkid"])]
    e["opposite_dQ_raw"] = e["opposite_link"].map(dict(zip(e["matsim_link_id"], e["dQ_edge_raw"])))
    # 1:K 聚合（同断面内多边）
    K = cw.groupby("lta_linkid")["matsim_link_id"].nunique()
    e["K_section"] = e["lta_linkid"].map(K)
    e.to_csv(OUT / "edge_level_delta.csv", index=False, encoding="utf-8-sig")

    n_opp = int(e["opposite_in_matched"].sum())
    n_opp_same = int(e["opposite_same_section"].sum())
    n_multi = int((e["K_section"] > 1).sum())
    print(f"    匹配边 {len(e):,}：对向边亦在匹配集者 {n_opp:,}；对向且同断面 {n_opp_same:,}；"
          f"K>1（多边聚合）的边 {n_multi:,}")
    print(f"    逐边 ΔQ：n+={int((e['dQ_edge_raw']>0).sum()):,}  n-={int((e['dQ_edge_raw']<0).sum()):,}  "
          f"Σ+= {e['dQ_edge_raw'][e['dQ_edge_raw']>0].sum():,.1f}  Σ-= {e['dQ_edge_raw'][e['dQ_edge_raw']<0].sum():,.1f}")
    gate("H04", "至少存在对向边同在同一匹配集（可检验方向性替代）", n_opp > 0, f"n_opp={n_opp}")

    # 对向抵消：断面内 正/负 抵消量
    pos = e["dQ_edge_raw"].clip(lower=0).sum()
    neg = e["dQ_edge_raw"].clip(upper=0).sum()
    print(f"    逐边 毛增={pos:,.1f} 毛减={neg:,.1f} 净={pos+neg:,.1f} 净/毛={((pos+neg)/(pos-neg) if (pos-neg) else float('nan')):.3f}")

    # ---------------- 断面级分解（走廊 / 等级）----------------
    print("\n[3.2] 断面级 ΔQ 分解（走廊 / 道路等级）")
    sec["corridor"] = sec["RoadName"].map(corridor_code)
    tot_net = float(sec["dQ_A5_v10"].sum())

    def decompose(df, by):
        outr = []
        for key, g in df.groupby(by, dropna=False):
            v = g["dQ_A5_v10"].fillna(0)
            p, ng = v[v > 0].sum(), v[v < 0].sum()
            outr.append({by: str(key), "n_sections": int(len(g)),
                         "sum_pos": float(p), "sum_neg": float(ng), "net": float(v.sum()),
                         "gross": float(p - ng),
                         "net_over_gross": float(v.sum() / (p - ng)) if (p - ng) else np.nan,
                         "share_of_net_pct": float(v.sum() / tot_net * 100) if tot_net else np.nan,
                         "sum_obs": float(g["obs_8_9"].sum())})
        return pd.DataFrame(outr).sort_values("net", ascending=False)

    corr_all = decompose(sec, "corridor")
    corr_all.to_csv(OUT / "corridor_delta_decomposition.csv", index=False, encoding="utf-8-sig")
    for _, r in corr_all[corr_all["corridor"] != ""].iterrows():
        print(f"      {r['corridor']:5s} n={r['n_sections']:3d}  净={r['net']:+11,.0f}  "
              f"毛={r['gross']:10,.0f}  净/毛={r['net_over_gross']:.2f}  占净增={r['share_of_net_pct']:6.1f}%")

    roadcat = decompose(sec, "RoadCat")
    roadcat.to_csv(OUT / "section_delta_by_roadcat.csv", index=False, encoding="utf-8-sig")

    # Top-2 / Top-10 道路集中度（RoadName）
    rn = decompose(sec, "RoadName")
    top2 = rn.head(2)["net"].sum()
    top10 = rn.head(10)["net"].sum()
    print(f"      Top-2 道路占净增 = {top2/tot_net*100:.1f}%   Top-10 = {top10/tot_net*100:.1f}%")
    rn.to_csv(OUT / "section_delta_by_roadname.csv", index=False, encoding="utf-8-sig")
    gate("H05", "净增闭合：Σ_g ΔQ_g == ΣQ_A5 − ΣQ_v1.0（断面层，±1e-6）",
         abs(tot_net - (sec["scaled_a5"].sum() - sec["scaled_v10"].sum())) < 1e-6,
         f"ΣΔQ={tot_net:,.3f}")

    # 断面级分解表（富化）
    sec_out = sec[["lta_linkid", "RoadCat", "RoadName", "corridor", "n_edges",
                   "obs_8_9", "scaled_v10", "scaled_a5", "dQ_A5_v10", "rel_dQ_A5_v10"]].copy()
    sec_out["K"] = sec_out["lta_linkid"].map(K)
    sec_out.to_csv(OUT / "section_delta_decomposition.csv", index=False, encoding="utf-8-sig")

    # ---------------- 路线变化 × ΔQ 关联 ----------------
    print("\n[3.3] 路线变化指标 × ΔQ（走廊级关联）")
    crf = OUT / "corridor_route_use.csv"
    if crf.exists():
        cru = pd.read_csv(crf, encoding="utf-8-sig")
        j = cru.merge(corr_all.rename(columns={"corridor": "code"}), left_on="corridor",
                      right_on="code", how="outer")
        j = j[["corridor", "rate_v10_pct", "rate_a5_pct", "d_rate_pp", "gained_users", "lost_users",
               "n_sections", "net", "gross", "net_over_gross", "share_of_net_pct"]]
        j.to_csv(OUT / "corridor_linkage_route_vs_flow.csv", index=False, encoding="utf-8-sig")
        print(j.to_string(index=False))
    else:
        print("    （缺 corridor_route_use.csv，跳过）")

    # 等级：路线里程占比变化 vs 路段流量变化
    rs = OUT / "roadclass_route_share.csv"
    if rs.exists():
        rr = pd.read_csv(rs, encoding="utf-8-sig")
        rp = rr.pivot(index="highway", columns="arm", values="route_length_share_pct")
        rp["d_route_share_pp"] = rp["SB-A5"] - rp["v1.0"]
        # 路段层级 dQ（匹配边）
        eh = e.groupby("highway")["dQ_edge_raw"].sum().rename("dQ_edges_raw")
        ehk = e.groupby("highway")["sim_v10"].sum().rename("sim_v10_edges_raw")
        ehq = pd.concat([eh, ehk], axis=1)
        ehq["d_pct_edges"] = ehq["dQ_edges_raw"] / ehq["sim_v10_edges_raw"].replace(0, np.nan) * 100
        rj = rp.join(ehq, how="outer").reset_index()
        rj.to_csv(OUT / "roadclass_route_vs_flow.csv", index=False, encoding="utf-8-sig")
        print("    —— 等级：路线里程占比变化(pp) vs 匹配边流量变化(%) ——")
        for _, r in rj.sort_values("d_route_share_pp", ascending=False).iterrows():
            if pd.isna(r.get("d_route_share_pp")):
                continue
            print(f"      {str(r['highway']):16s} Δ路线占比={r['d_route_share_pp']:+.3f} pp   "
                  f"Δ匹配边流量={r.get('d_pct_edges', float('nan')):+.2f}%")

    # ---------------- 汇总 ----------------
    summ = {
        "audit": "E-SB-04", "stage": 3, "scale": SCALE,
        "n_matched_edges": int(len(cw)), "n_sections": int(n_sec),
        "three_level": tl.to_dict("records"),
        "edge_dq": {"n_pos": int((e['dQ_edge_raw'] > 0).sum()), "n_neg": int((e['dQ_edge_raw'] < 0).sum()),
                    "sum_pos": float(pos), "sum_neg": float(neg), "net": float(pos + neg),
                    "gross": float(pos - neg),
                    "net_over_gross": float((pos + neg) / (pos - neg)) if (pos - neg) else None,
                    "n_opposite_in_matched": n_opp, "n_opposite_same_section": n_opp_same,
                    "n_edges_K_gt_1": n_multi},
        "section_net": float(tot_net),
        "top2_share_pct": float(top2 / tot_net * 100), "top10_share_pct": float(top10 / tot_net * 100),
        "corridor_decomp": corr_all.to_dict("records"),
        "roadcat_decomp": roadcat.to_dict("records"),
        "gates": GATES,
    }
    (OUT / "esb04_stage3_summary.json").write_text(json.dumps(summ, ensure_ascii=False, indent=2, default=str),
                                                   encoding="utf-8")
    pd.DataFrame(GATES).to_csv(OUT / "gate_checks_stage3.csv", index=False, encoding="utf-8-sig")
    n_fail = sum(1 for g in GATES if not g["pass"])
    print("\n" + "=" * 100)
    print(f"E-SB-04 阶段3 门禁：{len(GATES)-n_fail}/{len(GATES)} PASS" + (f"  ⚠️ {n_fail} FAIL" if n_fail else "  ✅"))
    return 0 if n_fail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
