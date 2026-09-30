# -*- coding: utf-8 -*-
"""Step 7.9H · 动态真实性诊断（H1 流量缺口去向 / H2 快速路映射 / H3 拥堵位置）

⛔ 零仿真、只读。不改 v1.0、不改任何冻结件、不重跑 MATSim。

四个问题（用户裁定）
--------------------------------------------------
  H1  23.3% 的**断面池化**流量缺口到底去哪了？
      ├─ 是「车没跑」还是「车改道离开被观测断面」？→ 全网 vs 断面池化 双账
      └─ 「sim 很低、obs 很高」的道路清单（可执行清单，不是平均数）
  H2  快速路是否被 crosswalk 低估？
      ├─ 映射基数实测（是否真 1:1？）
      ├─ 聚合口径敏感性：median / mean / sum / max ×{SCALE, 1}
      └─ 覆盖度：motorway/trunk 的流量有多少落在**未被映射**的边上
  H3  真正的拥堵在哪里形成？（与 build_congestion_maps_7_9h.py 共用口径）
  H4  这些结论对「下一轮该改什么」意味着什么（只作判读，不构成判决）

口径
--------------------------------------------------
  冻结评价口径（不得改动）：`sim = median(匹配边 HRS8-9avg) × SCALE`，`SCALE = 2.29897`
  观测口径（7.1 冻结）：工作日、hour ∈ {7,8}、先按日取均值再跨日中位
  有效容量 = `CAPACITY × cap_mul`（linkstats 的 CAPACITY 是**基础容量**，不随
             `flowCapacityFactor` 缩放 —— 已由 `_precheck_capacity_semantics.json` 实测）
"""
from __future__ import annotations

import csv
import gzip
import json
import math
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(r"D:\Luan\2026-05\2_Singapore")
sys.path.insert(0, str(ROOT / "scripts" / "od"))

import audit_sampling_capacity_7_9a1 as A          # noqa: E402
import compare_final_crosswalk_7_3_6b as bt        # noqa: E402
import evaluate_calibration_7_4_2 as ev1           # noqa: E402
import evaluate_demand_response_7_6f_1 as E        # noqa: E402

OUT = ROOT / "reports" / "dynamic_realism_audit_7_9"
OUT.mkdir(parents=True, exist_ok=True)

CYCLE = {
    "v1.0": ROOT / "reports" / "sampling_capacity_7_9a1" / "_cycle_linkstats"
            / "V1_conv.linkstats.txt.gz",
    "A-1": ROOT / "reports" / "sampling_capacity_7_9a1" / "_cycle_linkstats"
           / "A1_conv.linkstats.txt.gz",
}
FULL_LS = {"v1.0": A.V10_LS, "A-1": A.A1_LS}
CAPMUL = {"v1.0": 1.0, "A-1": A.F_CAP}
SCALE = bt.SCALE                                   # 2.298970

R_LOW, R_HIGH = 0.50, 1.50                          # 分桶边界（sim/obs）


# --------------------------------------------------------------------------- 读
def read_edge_full(p: Path) -> pd.DataFrame:
    """匹配边所需的全部列（容量/长度/自由流/8-9 小时流量与行程时间）。"""
    rows = []
    with gzip.open(p, "rt", encoding="utf-8", errors="replace") as fh:
        rd = csv.reader(fh, delimiter="\t")
        hdr = next(rd)
        c = {n: i for i, n in enumerate(hdr)}
        i_link, i_len, i_fs, i_cap = c["LINK"], c["LENGTH"], c["FREESPEED"], c["CAPACITY"]
        i_h89, i_tt89 = c["HRS8-9avg"], c["TRAVELTIME8-9avg"]
        for r in rd:
            if len(r) <= max(i_h89, i_tt89):
                continue
            try:
                rows.append((r[i_link], float(r[i_len]), float(r[i_fs]),
                             float(r[i_cap]), float(r[i_h89]), float(r[i_tt89])))
            except ValueError:
                continue
    df = pd.DataFrame(rows, columns=["LINK", "LENGTH", "FREESPEED", "CAPACITY",
                                     "HRS8-9avg", "TRAVELTIME8-9avg"])
    df["LINK"] = df["LINK"].astype(str).str.strip()
    df["ff_s"] = np.where(df["FREESPEED"] > 0, df["LENGTH"] / df["FREESPEED"], np.nan)
    df["speed_ratio"] = np.where(df["TRAVELTIME8-9avg"] > 0,
                                 df["ff_s"] / df["TRAVELTIME8-9avg"], np.nan)
    return df


def main() -> int:
    t0 = time.time()
    rec: dict = {"step": "7.9H/dynamic-realism-diagnostic",
                 "scale": SCALE, "cap_mul": CAPMUL,
                 "buckets": {"low": f"<{R_LOW}", "near": f"{R_LOW}-{R_HIGH}",
                             "high": f">{R_HIGH}"}}

    print("[1] 载入冻结件（观测 / crosswalk / 地理）…", flush=True)
    obs = bt.load_traffic(ev1.TRAFFIC)
    cw = bt.normalize_crosswalk(ev1.FINAL_CW, "final")
    cwraw = pd.read_csv(ev1.FINAL_CW, encoding="utf-8-sig")
    cwraw["matsim_link_id"] = cwraw["matsim_link_id"].astype(str).str.strip()
    cwraw["lta_linkid"] = cwraw["lta_linkid"].astype(str).str.strip()
    cw = cw.copy()
    cw["lta_linkid"] = cw["lta_linkid"].astype(str).str.strip()
    cw["matsim_link_id"] = cw["matsim_link_id"].astype(str).str.strip()
    geo = pd.read_csv(E.SEC_GEO_7_6C)[["lta_linkid", "mid_x", "mid_y", "d_cbd_m",
                                       "radial", "ring", "region", "pa"]]
    geo["lta_linkid"] = geo["lta_linkid"].astype(str).str.strip()
    matched_set = set(cwraw["matsim_link_id"])
    print(f"    obs 断面 {obs['LinkID'].nunique():,}  crosswalk 行 {len(cwraw):,}"
          f"  断面 {cwraw['lta_linkid'].nunique():,}  匹配边 {len(matched_set):,}", flush=True)

    print("[2] 载入两版 linkstats（全列）…", flush=True)
    edge = {k: read_edge_full(p) for k, p in FULL_LS.items()}
    for k, v in edge.items():
        print(f"    {k}: edges={len(v):,}", flush=True)
    cycle = {k: bt.load_linkstats(p) for k, p in CYCLE.items()}

    # ================= H1-a 全网 vs 断面的双账 =================
    print("[3] H1-a 全网 / 断面 双账 …", flush=True)
    net = {}
    for k, df in edge.items():
        v = df["HRS8-9avg"]
        net[k] = {
            "sum_flow_all_links": float(v.sum()),
            "n_flow_gt0": int((v > 0).sum()),
            "sum_flow_on_matched_edges": float(v[df["LINK"].isin(matched_set)].sum()),
            "sum_flow_on_unmatched_edges": float(v[~df["LINK"].isin(matched_set)].sum()),
            "sum_cap_eff": float((df["CAPACITY"] * CAPMUL[k]).sum()),
            "sum_km": float(df["LENGTH"].sum()) / 1000.0,
        }
    rec["H1a_network_accounting"] = net
    print(f"    v1.0 全网 {net['v1.0']['sum_flow_all_links']:,.0f} veh/h"
          f"  → A-1 {net['A-1']['sum_flow_all_links']:,.0f}"
          f"  ({100 * (net['A-1']['sum_flow_all_links'] / net['v1.0']['sum_flow_all_links'] - 1):+.2f}%)")
    print(f"    匹配边 v1.0 {net['v1.0']['sum_flow_on_matched_edges']:,.0f}"
          f" → A-1 {net['A-1']['sum_flow_on_matched_edges']:,.0f}"
          f"  ({100 * (net['A-1']['sum_flow_on_matched_edges'] / net['v1.0']['sum_flow_on_matched_edges'] - 1):+.2f}%)")

    # ================= H1-b / H2-b 逐断面聚合敏感性 =================
    print("[4] H2-b 逐断面聚合口径敏感性 …", flush=True)
    secs: dict[str, pd.DataFrame] = {}
    agg_tbl = {}
    for k in ("v1.0", "A-1"):
        sim = cycle[k].copy()
        x = (cw.merge(obs, left_on="lta_linkid", right_on="LinkID", how="inner")
               .merge(sim, left_on="matsim_link_id", right_on="LINK", how="left")
               .merge(edge[k][["LINK", "LENGTH", "CAPACITY", "TRAVELTIME8-9avg",
                               "speed_ratio"]],
                      left_on="matsim_link_id", right_on="LINK", how="left",
                      suffixes=("", "_e")))
        g = x.groupby("lta_linkid", as_index=False).agg(
            RoadCat=("RoadCat", "first"), RoadName=("RoadName", "first"),
            n_edges=("matsim_link_id", "nunique"),
            sim_median=("HRS8-9avg", "median"), sim_mean=("HRS8-9avg", "mean"),
            sim_sum=("HRS8-9avg", "sum"), sim_max=("HRS8-9avg", "max"),
            sim_min=("HRS8-9avg", "min"),
            obs_8_9=("obs_8_9", "first"), obs_7_8=("obs_7_8", "first"),
            cap_eff_sum=("CAPACITY", lambda s: float(s.sum()) * CAPMUL[k]),
            len_sum=("LENGTH", "sum"),
            tt89_median=("TRAVELTIME8-9avg", "median"),
            sr_median=("speed_ratio", "median"),
        )
        g = g.merge(geo, on="lta_linkid", how="left")
        for c in ("sim_median", "sim_mean", "sim_sum", "sim_max"):
            g[c + "_xS"] = g[c] * SCALE
        secs[k] = g
        row = {"n_sections": int(len(g)), "sum_obs": float(g["obs_8_9"].sum())}
        for c in ("sim_median_xS", "sim_mean_xS", "sim_sum_xS", "sim_max_xS"):
            row["pooled_" + c] = float(g[c].sum() / g["obs_8_9"].sum())
        for c in ("sim_median", "sim_mean", "sim_sum", "sim_max"):
            row["pooled_" + c + "_raw"] = float(g[c].sum() / g["obs_8_9"].sum())
        agg_tbl[k] = row
        print(f"    [{k}] " + "  ".join(
            f"{c.replace('sim_','').replace('_xS','×S')}={row['pooled_' + c]:.4f}"
            for c in ("sim_median_xS", "sim_mean_xS", "sim_sum_xS", "sim_max_xS")))
    rec["H2b_aggregation_sensitivity"] = agg_tbl
    renorm = {k: {c: round(SCALE / (SCALE * v), 4)
                  for c, v in agg_tbl[k].items() if c.startswith("pooled_sim_") and c.endswith("_xS")}
              for k in agg_tbl}
    rec["H2b_scale_needed_for_ratio_1"] = renorm

    # ================= H1-b 分桶 =================
    print("[5] H1-b 断面分桶（sim 低 / ≈ / 高）…", flush=True)
    buck = {}
    low_lists = {}
    for k in ("v1.0", "A-1"):
        g = secs[k].copy()
        g["ratio"] = g["sim_median_xS"] / g["obs_8_9"].replace(0, np.nan)
        b = {}
        for name, mask in (("low", g["ratio"] < R_LOW),
                           ("near", (g["ratio"] >= R_LOW) & (g["ratio"] <= R_HIGH)),
                           ("high", g["ratio"] > R_HIGH)):
            s = g[mask]
            b[name] = {
                "n": int(len(s)),
                "share_n": round(float(len(s)) / max(1, len(g)), 4),
                "sum_obs": round(float(s["obs_8_9"].sum()), 1),
                "obs_weight_share": round(float(s["obs_8_9"].sum())
                                          / max(1e-9, float(g["obs_8_9"].sum())), 4),
                "sum_sim": round(float(s["sim_median_xS"].sum()), 1),
                "median_obs_in_bucket": round(float(s["obs_8_9"].median()), 1) if len(s) else None,
            }
        buck[k] = b
        lo = g[g["ratio"] < R_LOW].sort_values("obs_8_9", ascending=False)
        lo = lo.assign(sim_over_obs=lo["ratio"].round(4))
        col = ["lta_linkid", "RoadName", "RoadCat", "obs_8_9", "sim_median_xS",
               "sim_over_obs", "n_edges", "cap_eff_sum", "sr_median",
               "d_cbd_m", "radial", "ring", "region", "pa"]
        lo[col].to_csv(OUT / f"gap_low_ratio_sections_{'v10' if k == 'v1.0' else 'A1'}.csv",
                       index=False, encoding="utf-8-sig")
        low_lists[k] = lo
        print(f"    [{k}] low={b['low']['n']} (obs 占比 {100*b['low']['obs_weight_share']:.1f}%)"
              f"  near={b['near']['n']}  high={b['high']['n']}"
              f" (obs 占比 {100*b['high']['obs_weight_share']:.1f}%)")
    rec["H1b_buckets"] = buck

    # 分桶 × RoadCat（显式循环，避免 pandas3 `groupby.apply` 的口径歧义）
    bycat = {}
    for k in ("v1.0", "A-1"):
        g = secs[k].copy()
        g["ratio"] = g["sim_median_xS"] / g["obs_8_9"].replace(0, np.nan)
        rows = []
        for rc, s in g.groupby("RoadCat"):
            rows.append({
                "RoadCat": str(rc), "n": int(len(s)),
                "sum_obs": round(float(s["obs_8_9"].sum()), 1),
                "sum_sim": round(float(s["sim_median_xS"].sum()), 1),
                "ratio": round(float(s["sim_median_xS"].sum()
                                     / max(1e-9, float(s["obs_8_9"].sum()))), 4),
                "n_low": int((s["ratio"] < R_LOW).sum()),
                "n_high": int((s["ratio"] > R_HIGH).sum()),
            })
        bycat[k] = rows
        print(f"    [{k}] " + "; ".join(
            f"{r['RoadCat']}: n={r['n']} ratio={r['ratio']:.3f} low={r['n_low']}"
            f" high={r['n_high']}" for r in rows))
    rec["H1b_by_roadcat"] = bycat

    # ================= H2-a 映射基数 =================
    print("[6] H2-a 映射基数（是否真 1:1）…", flush=True)
    card = secs["v1.0"][["lta_linkid", "RoadCat", "RoadName", "n_edges",
                         "obs_8_9", "sim_median_xS", "sim_sum_xS", "cap_eff_sum"]].copy()
    card["sim_sum_over_obs"] = card["sim_sum_xS"] / card["obs_8_9"].replace(0, np.nan)
    card["sim_median_over_obs"] = card["sim_median_xS"] / card["obs_8_9"].replace(0, np.nan)
    card["spread"] = card["sim_sum_xS"] / (card["sim_median_xS"] * card["n_edges"]).replace(0, np.nan)
    card.to_csv(OUT / "h2_mapping_cardinality.csv", index=False, encoding="utf-8-sig")
    nd = card["n_edges"]
    rec["H2a_mapping_cardinality"] = {
        "n_sections": int(len(card)),
        "n_edges_min": int(nd.min()), "n_edges_max": int(nd.max()),
        "n_edges_median": float(nd.median()), "n_edges_mean": round(float(nd.mean()), 3),
        "n_one_to_one": int((nd == 1).sum()),
        "share_one_to_one": round(float((nd == 1).sum()) / max(1, len(nd)), 4),
        "hist": {str(int(k)): int(v) for k, v in nd.value_counts().sort_index().items()},
        "is_one_to_one": bool((nd == 1).all()),
    }
    print(f"    每断面匹配边：min={int(nd.min())} max={int(nd.max())} "
          f"median={nd.median():.0f} mean={nd.mean():.2f}；"
          f"严格 1:1 仅 {int((nd == 1).sum())}/{len(nd)} 断面")

    # 快速路专项
    exp = card[card["RoadName"].astype(str).str.contains("EXPRESSWAY", na=False)]
    rec["H2a_expressway"] = {
        "n": int(len(exp)),
        "n_edges_median": float(exp["n_edges"].median()),
        "sum_obs": round(float(exp["obs_8_9"].sum()), 1),
        "sum_sim_median_xS": round(float(exp["sim_median_xS"].sum()), 1),
        "sum_sim_sum_xS": round(float(exp["sim_sum_xS"].sum()), 1),
        "pooled_median": round(float(exp["sim_median_xS"].sum() / exp["obs_8_9"].sum()), 4),
        "pooled_sum": round(float(exp["sim_sum_xS"].sum() / exp["obs_8_9"].sum()), 4),
    }
    print(f"    快速路断面 {len(exp)}：median 口径 {rec['H2a_expressway']['pooled_median']:.3f}"
          f" vs sum 口径 {rec['H2a_expressway']['pooled_sum']:.3f}")

    # ================= H2-c 覆盖度（按公路类） =================
    print("[7] H2-c 覆盖度：各类流量的 matched / unmatched …", flush=True)
    cov = {}
    for k, df in edge.items():
        d = df.copy()
        d["is_matched"] = d["LINK"].isin(matched_set)
        t = d.groupby("is_matched").agg(
            n=("LINK", "size"), flow=("HRS8-9avg", "sum"), km=("LENGTH", "sum"))
        tot_flow = float(t["flow"].sum())
        cov[k] = {
            "all": {"n": int(t["n"].sum()), "flow": round(tot_flow, 1),
                    "km": round(float(t["km"].sum()) / 1000.0, 1)},
            "matched": {"n": int(t.loc[True, "n"]) if True in t.index else 0,
                        "flow": round(float(t.loc[True, "flow"]) if True in t.index else 0.0, 1),
                        "km": round(float(t.loc[True, "km"]) / 1000.0, 1) if True in t.index else 0.0},
            "unmatched": {"n": int(t.loc[False, "n"]) if False in t.index else 0,
                          "flow": round(float(t.loc[False, "flow"]) if False in t.index else 0.0, 1),
                          "km": round(float(t.loc[False, "km"]) / 1000.0, 1) if False in t.index else 0.0},
        }
        cov[k]["flow_share_matched"] = round(
            cov[k]["matched"]["flow"] / max(1e-9, tot_flow), 4)
        # 与 OSM 全精度 LENGTH 对齐（linkstats LENGTH 已是 canonical 长度）
    rec["H2c_coverage"] = cov
    for k in cov:
        print(f"    [{k}] matched 流量占比 {100*cov[k]['flow_share_matched']:.2f}%"
              f"（matched {cov[k]['matched']['km']:,.0f} km / unmatched "
              f"{cov[k]['unmatched']['km']:,.0f} km）")

    # ================= H3 拥堵位置（与地图脚本同口径） =================
    print("[8] H3 拥堵空间位置（vc≥0.85 且 sr<0.70）…", flush=True)
    h3 = {}
    for k, df in edge.items():
        d = df.copy()
        d["vc"] = np.where(d["CAPACITY"] * CAPMUL[k] > 0,
                           d["HRS8-9avg"] / (d["CAPACITY"] * CAPMUL[k]), np.nan)
        m = ((d["LENGTH"] >= 50) & (d["HRS8-9avg"] > 0) & (d["vc"] >= 0.85)
             & (d["speed_ratio"] < 0.70))
        s = d[m]
        h3[k] = {
            "n_congested_links": int(len(s)),
            "km": round(float(s["LENGTH"].sum()) / 1000.0, 3),
            "sum_flow": round(float(s["HRS8-9avg"].sum()), 1),
            "share_of_total_flow": round(float(s["HRS8-9avg"].sum())
                                         / max(1e-9, float(d["HRS8-9avg"].sum())), 6),
            "median_speed_ratio": round(float(s["speed_ratio"].median()), 4) if len(s) else None,
            "median_vc": round(float(s["vc"].median()), 4) if len(s) else None,
        }
        s.sort_values("HRS8-9avg", ascending=False).head(200).to_csv(
            OUT / f"h3_congested_links_{'v10' if k == 'v1.0' else 'A1'}.csv",
            index=False, encoding="utf-8-sig")
        print(f"    [{k}] 拥堵链 {h3[k]['n_congested_links']:,} / {h3[k]['km']:,.2f} km"
              f" / 担全网流量 {100*h3[k]['share_of_total_flow']:.3f}%")
    rec["H3_congestion_location"] = h3

    rec["elapsed_s"] = round(time.time() - t0, 1)
    (OUT / "_gap_diagnostic_7_9h.json").write_text(
        json.dumps(rec, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(f"\n[out] {OUT / '_gap_diagnostic_7_9h.json'}  （{rec['elapsed_s']} s）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
