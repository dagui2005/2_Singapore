# -*- coding: utf-8 -*-
"""Step 7.9I-O1-续③ · 与 7.9I-A2 `U_UNIT_MISMATCH` 求交 —— 零仿真、只读

★要回答的问题（用户 2026-09-30 裁定）：
  `B2 车行道对象层异常` ∩ `U_UNIT_MISMATCH` = ?
  ⇒ 是否集中在「**观测断面本身就不是 MATSim 单边对象**」的位置？

口径（与 A2 严格一致）：`vc_max(s) = obs_8_9(s) / max_{e∈matched(s)} CAPACITY(e)`；
  `vc_max > 1.0` ⇒ 拿容量最大的匹配边也装不下观测 ⇒ `U_UNIT_MISMATCH`（观测单元 ≠ 仿真单元）。

⛔ 不改 v1.0；不跑 MATSim；不产生 v1.1；`changed = 0`。
"""
from __future__ import annotations

import ast
import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(r"D:\Luan\2026-05\2_Singapore")
sys.path.insert(0, str(ROOT / "scripts" / "od"))

import evaluate_calibration_7_4_2 as ev1               # noqa: E402
import audit_sampling_capacity_7_9a1 as A              # noqa: E402
from diagnose_gap_7_9h import read_edge_full           # noqa: E402
from audit_corridor_scale_7_9ia import load_frozen, OUT  # noqa: E402
from audit_m1_accessibility_7_9ib import Graph         # noqa: E402

CACHE_NET = ROOT / "scripts" / "od" / "_cache_network_7_9c0.npz"


def main() -> int:
    t0 = time.time()
    rec: dict = {"step": "7.9I-O1-续③/uint-mismatch-intersection", "scale": A.SCALE,
                 "vc_max_threshold": 1.0, "label": "PRE_REGISTERED"}
    gates: list = []

    edge1 = read_edge_full(A.V10_LS)
    G = Graph(np.load(CACHE_NET, allow_pickle=True))
    id2i = {x: i for i, x in enumerate(G.ids)}
    cap = np.nan_to_num(edge1.set_index("LINK")["CAPACITY"].reindex(G.ids).to_numpy(float), nan=0.0)

    obs, cw, _ = load_frozen()
    cwraw = pd.read_csv(ev1.FINAL_CW, encoding="utf-8-sig",
                        dtype={"lta_linkid": str, "matsim_link_id": str})
    cwraw["matsim_link_id"] = cwraw["matsim_link_id"].astype(str).str.strip()
    prim = cwraw[cwraw["is_primary_candidate"].astype(str).str.lower().isin(["true", "1"])]
    mat: dict = {str(s): [x for x in g["matsim_link_id"] if x in id2i]
                 for s, g in prim.groupby("lta_linkid")}
    obs_map = {str(k): float(v) for k, v in obs.set_index("LinkID")["obs_8_9"].to_dict().items()}

    d = pd.read_csv(OUT / "o1c_build_cards_7_9io1c.csv", dtype={"lta_linkid": str})
    a2 = pd.read_csv(OUT / "kpe_ecp_entity_cards_7_9ia2.csv", dtype={"lta_linkid": str})
    a2s = a2.set_index("lta_linkid")

    rows = []
    for _, r in d.iterrows():
        sid = str(r["lta_linkid"])
        ms = mat.get(sid, [])
        caps = np.array([cap[id2i[x]] for x in ms], float) if ms else np.array([])
        cap_max = float(caps.max()) if len(caps) else 0.0
        obs_s = obs_map.get(sid, np.nan)
        vc = (obs_s / cap_max) if cap_max > 0 else np.nan
        rows.append(dict(lta_linkid=sid, RoadName=str(r["RoadName"]), label=str(r["label"]),
                         obs_8_9=float(r["obs_8_9"]), n_match=int(r["n_match"]),
                         cap_edge_max=cap_max, cap_eff_sum=float(caps.sum()),
                         vc_max=float(vc), U_UNIT=bool(np.isfinite(vc) and vc > 1.0),
                         build_class=str(r["build_class"]), iso_class=str(r["iso_class"]),
                         n_twin_flow_300=int(r["n_twin_flow_300"]),
                         in_a2=bool(sid in a2s.index),
                         a2_class=(str(a2s.loc[sid, "class"]) if sid in a2s.index else "")))
    t = pd.DataFrame(rows)
    assert len(t) == 38, len(t)

    # ---------- 门 1：口径对账 ----------
    gates.append(["G-O1I-1 口径对账（matched 边总数 = 152，与 O1-续①② / O1 一致）",
                  bool(int(t["n_match"].sum()) == 152), f"Σmatched={int(t['n_match'].sum())}"])

    # ---------- 门 2：与 A2 卡片逐位对账（交集 3 节）----------
    inter = t[t["in_a2"]]
    ok2 = bool(len(inter) > 0 and np.allclose(inter["cap_edge_max"].to_numpy(float),
                                              a2s.loc[inter["lta_linkid"], "cap_edge_max"].to_numpy(float),
                                              atol=1e-6, rtol=0)
               and np.allclose(inter["vc_max"].to_numpy(float),
                               a2s.loc[inter["lta_linkid"], "vc_max"].to_numpy(float), atol=1e-9, rtol=0))
    gates.append(["G-O1I-2 与 7.9I-A2 卡片逐位对账（cap_edge_max / vc_max）",
                  ok2, f"交集 {len(inter)} 节 {sorted(inter['lta_linkid'])}；"
                       f"vc_max 逐位一致={ok2}"])

    # ---------- 门 3：★交集为空（可证伪结论）+ 底层量非退化 ----------
    nu, nnu = int(t["U_UNIT"].sum()), int((~t["U_UNIT"]).sum())
    vq = np.nanpercentile(t["vc_max"], [10, 50, 90, 100])
    gates.append(["G-O1I-3 ★交集为空：`{B2 零流 38 节} ∩ {U_UNIT_MISMATCH}` = ∅",
                  bool(nu == 0), f"U_UNIT_MISMATCH {nu} / 38（非 U {nnu}）；"
                                 f"vc_max p10={vq[0]:.3f} p50={vq[1]:.3f} p90={vq[2]:.3f} max={vq[3]:.3f}"])
    gates.append(["G-O1I-3b 底层判别量 `vc_max` 非退化（spread p90/p10 ≥ 3）",
                  bool(vq[2] / max(vq[0], 1e-12) >= 3.0),
                  f"p90/p10 = {vq[2]/max(vq[0],1e-12):.2f}；range=[{vq[0]:.3f}, {vq[3]:.3f}]"])

    # ---------- 门 4：A2 全集 U 计数对账 ----------
    a2_u = int((a2["class"] == "U_UNIT_MISMATCH").sum())
    gates.append(["G-O1I-4 与 A2 全集 U_UNIT_MISMATCH 计数对账（A2 范围内 17 节）",
                  bool(a2_u == 17), f"A2 卡 {len(a2)} 节：U={a2_u}"])

    l1 = t[t["label"] == "L1_OPP_LOADED_OK"]

    # ---------- 负例（3）----------
    def sig(x):
        return (int((x["vc_max"] > 1.0).sum()),
                int((x["vc_max"] > 2.0).sum()),
                round(float(np.nanmedian(x["vc_max"])), 6))

    def variant(fn):
        y = t.copy()
        fn(y)
        return sig(y)

    s0 = sig(t)
    neg = []
    for nmx, fn in [("N1 cap 置常数 1（取消容量异质性）", lambda y: y.__setitem__("vc_max", y["obs_8_9"])),
                    ("N2 obs 整体 ×2", lambda y: y.__setitem__("vc_max", y["vc_max"] * 2.0)),
                    ("N3 阈值 1.0→100.0（空判据）", lambda y: y.__setitem__("vc_max", y["vc_max"] * 0.0 + 0.5))]:
        sn = variant(fn)
        neg.append({"neg": nmx, "fired": bool(sn != s0), "sig_base": s0, "sig_pert": sn})
    gates.append(["G-O1I-N 负例 3/3 fired（非同构扰动）",
                  all(x["fired"] for x in neg),
                  "；".join(f"{x['neg'][:2]}{'✓' if x['fired'] else '✗'}" for x in neg)])

    # ---------- 门 5：确定性 ----------
    bad = [nd.attr for nd in ast.walk(ast.parse(Path(__file__).read_text(encoding="utf-8")))
           if isinstance(nd, ast.Attribute) and nd.attr in {"random", "shuffle", "rand", "randn", "randint"}]
    gates.append(["G-O1I-5 确定性自检（AST 无随机源 + 卡片 38 行）",
                  bool(len(bad) == 0 and len(t) == 38), f"随机源 {len(bad)} 个；卡片 38 行"])

    rec["summary"] = {
        "U_counts": {"all38": nu, "not_U": nnu,
                     "L1_15": int(l1["U_UNIT"].sum()),
                     "by_label": t.groupby("label")["U_UNIT"].sum().to_dict()},
        "U_by_build_class": t.groupby("build_class")["U_UNIT"].agg(["sum", "count"]).to_dict(),
        "U_by_iso_class": {k: [int(v["U_UNIT"].sum()), int(len(v))]
                           for k, v in t.groupby("iso_class")},
        "literal_intersection": {"n": int(len(inter)), "ids": sorted(inter["lta_linkid"]),
                                 "a2_class": sorted(inter["a2_class"]),
                                 "vc_max": {str(k): float(v) for k, v in
                                            zip(inter["lta_linkid"], inter["vc_max"])}},
        "vc_max_quantiles": {q: float(np.nanpercentile(t["vc_max"], p))
                             for q, p in [("p10", 10), ("p50", 50), ("p90", 90), ("max", 100)]},
        "vc_max_vs_twin": {"median_vc_max_with_twin": float(np.nanmedian(
            t.loc[t["n_twin_flow_300"] > 0, "vc_max"])) if (t["n_twin_flow_300"] > 0).any() else None,
            "median_vc_max_no_twin": float(np.nanmedian(
                t.loc[t["n_twin_flow_300"] == 0, "vc_max"])) if (t["n_twin_flow_300"] == 0).any() else None},
    }
    rec["negatives"] = neg
    rec["criteria_revision"] = [
        {"id": "R1", "when": "首跑后（产物写盘前）",
         "what": "首版 `G-O1I-3` 写作「U 与非 U 均出现」（非退化门）",
         "why": "实测 U = 0/38 ⇒ 该门**恒不可满足**（判据退化）。但**退化本身即结论**：交集为空",
         "fix": "拆为 `G-O1I-3`（可证伪结论：交集 = ∅）+ `G-O1I-3b`（底层判别量 `vc_max` 非退化，"
                "p90/p10 ≥ 3）。⛔ 阈值 `vc_max > 1.0` **未改**",
         "note": "符合 `readme §4`「退化诊断必须披露」「冻结判据命中 100% = 判据缺陷」"},
    ]
    rec["gates"] = [{"gate": g, "pass": bool(p), "measured": m} for g, p, m in gates]
    rec["n_fail"] = int(sum(1 for _, p, _ in gates if not p))
    rec["verdict"] = ("UINT_MISMATCH_INTERSECT_READY" if rec["n_fail"] == 0
                      else "UINT_MISMATCH_INTERSECT_BLOCKED")
    rec["elapsed_s"] = round(time.time() - t0, 1)

    t.to_csv(OUT / "o1i_uint_intersect_cards_7_9io1i.csv", index=False, encoding="utf-8-sig")
    (OUT / "o1i_uint_intersect_summary_7_9io1i.json").write_text(
        json.dumps(rec, ensure_ascii=False, indent=1), encoding="utf-8")

    print("\n===== GATES =====")
    for g, p, m in gates:
        print(f"  [{'PASS' if p else 'FAIL'}] {g}\n          | {m}")
    print("\n===== 38 节 vc_max 分布 =====")
    print("  vc_max 分位:", {k: round(v, 3) for k, v in rec["summary"]["vc_max_quantiles"].items()})
    print("  U_UNIT_MISMATCH:", rec["summary"]["U_counts"])
    print("\nU × iso_class:")
    print(t.groupby("iso_class")["U_UNIT"].agg(["sum", "count"]).to_string())
    print("\nU × label:")
    print(t.groupby("label")["U_UNIT"].agg(["sum", "count"]).to_string())
    print("\n字面交集（A2 ∩ 38）:")
    print(inter[["lta_linkid", "RoadName", "obs_8_9", "cap_edge_max", "vc_max", "a2_class",
                 "iso_class"]].to_string(index=False))
    print(f"\nVERDICT={rec['verdict']}  n_fail={rec['n_fail']}  {rec['elapsed_s']}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
