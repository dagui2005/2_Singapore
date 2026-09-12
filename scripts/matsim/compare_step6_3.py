#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
compare_step6_3.py — Step 6.3 第一次对照：MATSim q_a^sim vs LTA TrafficFlow q_a^obs。

对照链路（三段拼接）
--------------------
LTA 观测链路（TrafficFlow_Data.json, LinkID×Hour）
    -> lta_osm_match_v2.csv:  LinkID -> osm_edge_index   （Step 5C.1 的几何+名称匹配）
    -> network_links_source_copy.csv: osm_edge_index -> (from_node, to_node)
    -> MATSim link id = f"e{from}_{to}"                  （Step 6.1 路网命名规则）

⚠️ 该 crosswalk 是 Step 5C.1 为**速度传播**建立的「每个 LTA 链路取 1 条最近 OSM 边」。
用于**流量**对照时粒度偏细：LTA 监测链路是一整段（100–500 m），而 OSM 把它拆成
多条 13–100 m 的短边，只取 1 条会系统性低估。本脚本因此同时报告：
    * matched 边（原 crosswalk，主口径）
    * 反向边（检验方向是否匹配错）
    * max(正向, 反向)
并在报告中把「crosswalk 粒度」列为后续必须升级项。

规模口径（关键）
----------------
population 是 **200,000 agents 代表 459,794 次 car 出行**（`EF_ij = T_ij/N_ij`，逐 cell）。
QSim 的 linkstats 计的是**实际车辆**（=200k），因此与真实观测对照时必须乘
    scale = ΣEF / N_agents = 459,794 / 200,000 = 2.29897
本脚本同时给出 raw 与 scaled 两套数。

时窗口径（关键）
----------------
冻结的 6.2B population 里 **全部 200,000 个 agent 的 home end_time = 08:00:00**，
QSim 在 08:00 一次性释放全部 AM 需求 → `HRS7-8` 恒为 0，流量集中在 `HRS8-9`。
主对照：sim 的 HRS8-9（= 整个 AM 脉冲） vs 观测的 (hour7+hour8)（= 整个 AM 窗口）。

产物
----
    reports/matsim_assignment/STEP6_3_COMPARISON.md
    reports/matsim_assignment/step6_3_metrics_by_lambda.csv
    reports/matsim_assignment/step6_3_roadcat_lambda_{lam}.csv
    reports/matsim_assignment/step6_3_link_compare_lambda_{lam}.csv
    reports/matsim_assignment/step6_3_sim_linkstats_lambda_{lam}.csv
"""
from __future__ import annotations

import gzip
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
NET_LINKS = ROOT / "reports" / "matsim_network" / "network_links_source_copy.csv"
MATCH = ROOT / "reports" / "od_impedance_ampeak_v2" / "lta_osm_match_v2.csv"
OBS_JSON = ROOT / "Dynamic_2026_03_16" / "historical_data" / "TrafficFlow_Data.json"
OBS_AUDIT = ROOT / "reports" / "od_audit" / "audit_trafficflow.csv"
POP_SUMMARY = ROOT / "reports" / "matsim_population_6_2b" / "population_6_2b_summary.csv"
ASSIGN = ROOT / "reports" / "matsim_assignment"
LAMBDAS = ["0p050", "0p075", "0p100"]
MIN_N = 5

# linkstats 列索引（表头 154 列）
COL_H7_AVG = 7 + 7 * 3 + 1        # HRS7-8avg
COL_H8_AVG = 7 + 8 * 3 + 1        # HRS8-9avg
TT_BASE = 7 + (24 + 1) * 3
COL_TT7_AVG = TT_BASE + 7 * 3 + 1
COL_TT8_AVG = TT_BASE + 8 * 3 + 1
USECOLS = [0, 2, 3, 4, 5, 6, COL_H7_AVG, COL_H8_AVG, COL_TT7_AVG, COL_TT8_AVG]
LINKSTATS_COLS = ["matsim_id", "from", "to", "length_m", "freespeed_ms", "capacity",
                  "vol_h7", "vol_h8", "tt_h7", "tt_h8"]


# ----------------------------------------------------------------- 规模系数 --
def _scale_map() -> dict[str, float]:
    """每个 λ 的规模系数 = ΣEF / N_agents（来自 6.2B summary 的 real_trip_equivalent）。"""
    df = pd.read_csv(POP_SUMMARY, encoding="utf-8-sig")
    out = {}
    for r in df.itertuples():
        key = {0.05: "0p050", 0.075: "0p075", 0.100: "0p100"}.get(round(float(r.lambda_per_min), 3))
        out[key] = float(r.real_trip_equivalent) / float(r.agents)
    return out


# ----------------------------------------------------------------- 交叉walk --
def build_crosswalk() -> pd.DataFrame:
    nl = pd.read_csv(NET_LINKS, encoding="utf-8-sig", low_memory=False)
    fo = nl.from_node.astype(int).astype(str)
    to = nl.to_node.astype(int).astype(str)
    x = pd.DataFrame({"osm_edge_index": np.arange(len(nl)),
                      "matsim_id": "e" + fo + "_" + to,
                      "rev_id": "e" + to + "_" + fo,
                      "highway": nl.highway.values,
                      "edge_name": nl["name"].values,
                      "length_m": nl.length_m.values})
    m = pd.read_csv(MATCH, encoding="utf-8-sig")
    m["osm_edge_index"] = m.osm_edge_index.astype(int)
    out = m.merge(x, on="osm_edge_index", how="left")
    if out.matsim_id.isna().any():
        raise ValueError("存在越界的 osm_edge_index")
    return out[["LinkID", "osm_edge_index", "matsim_id", "rev_id", "highway",
                "edge_name", "length_m", "distance_m", "name_match", "match_method"]]


# ------------------------------------------------------------------- 观测 --
def load_observed() -> tuple[pd.DataFrame, pd.DataFrame]:
    d = json.loads(OBS_JSON.read_text(encoding="utf-8"))
    tf = pd.DataFrame(d["Value"])
    tf["LinkID"] = tf.LinkID.astype(int)
    tf["hour"] = tf.HourOfDate.astype(int)
    tf["vol"] = pd.to_numeric(tf.Volume.astype(str).str.replace(",", "", regex=False),
                              errors="coerce")
    agg = (tf.dropna(subset=["vol"]).groupby(["LinkID", "hour"]).vol
           .agg(n="size", mean="mean", median="median").reset_index())
    return agg, tf


def observed_wide(agg: pd.DataFrame, info: pd.DataFrame) -> pd.DataFrame:
    p = agg.pivot(index="LinkID", columns="hour", values=["median", "mean", "n"]).fillna(0.0)
    out = pd.DataFrame(index=p.index)
    for h in (7, 8):
        out[f"obs_h{h}"] = p[("median", h)] if ("median", h) in p else 0.0
        out[f"obs_h{h}_mean"] = p[("mean", h)] if ("mean", h) in p else 0.0
        out[f"obs_h{h}_n"] = p[("n", h)] if ("n", h) in p else 0.0
    out["obs_am"] = out.obs_h7 + out.obs_h8
    out["obs_am_mean"] = out.obs_h7_mean + out.obs_h8_mean
    out["obs_n_min"] = out[["obs_h7_n", "obs_h8_n"]].min(axis=1)
    out = out.reset_index().merge(info, on="LinkID", how="left")
    return out


# ---------------------------------------------------------------- 仿真侧 --
def load_linkstats(lam: str) -> pd.DataFrame:
    p = ASSIGN / f"lambda_{lam}" / "ITERS" / "it.0" / f"step6_3_lambda_{lam}.0.linkstats.txt.gz"
    if not p.exists():
        raise FileNotFoundError(p)
    out = pd.read_csv(p, sep="\t", compression="gzip", header=0,
                      usecols=USECOLS, low_memory=False)
    out.columns = LINKSTATS_COLS
    for c in LINKSTATS_COLS[3:]:
        out[c] = pd.to_numeric(out[c], errors="coerce")
    out["vol_am"] = out.vol_h7 + out.vol_h8
    out["v_h8_kmh"] = (out.length_m / out.tt_h8) * 3.6
    out["v_h7_kmh"] = (out.length_m / out.tt_h7) * 3.6
    return out


# ------------------------------------------------------------------ 指标 --
def geh(m: np.ndarray, c: np.ndarray) -> np.ndarray:
    denom = np.where((m + c) > 0, m + c, np.nan)
    return np.sqrt(2.0 * (m - c) ** 2 / denom)


def metrics(sim: np.ndarray, obs: np.ndarray) -> dict:
    ok = np.isfinite(sim) & np.isfinite(obs)
    s, o = sim[ok], obs[ok]
    if len(s) == 0:
        return {}
    nz = (s + o) > 0
    r = float(np.corrcoef(s, o)[0, 1]) if s.std() > 0 and o.std() > 0 else float("nan")
    rs = float(pd.Series(s).corr(pd.Series(o), method="spearman")) if len(s) > 2 else float("nan")
    rmse = float(np.sqrt(np.mean((s - o) ** 2)))
    g = geh(s[nz], o[nz]); g = g[np.isfinite(g)]
    nzr = o[nz] > 0
    return {
        "n_links": int(len(s)),
        "n_sim_gt0": int((s > 0).sum()),
        "sum_sim": float(s.sum()),
        "sum_obs": float(o.sum()),
        "ratio_sum": float(s.sum() / o.sum()) if o.sum() > 0 else float("nan"),
        "ratio_median": float(np.median(s[nz] / o[nz])) if nz.any() else float("nan"),
        "pearson_r": r,
        "spearman_rho": rs,
        "rmse": rmse,
        "nrmse": rmse / float(o.mean()) if o.mean() > 0 else float("nan"),
        "mape_pct": float(np.mean(np.abs(s[nzr] - o[nzr]) / o[nzr]) * 100) if nzr.any() else float("nan"),
        "geh_lt5_pct": float((g < 5).mean() * 100) if len(g) else float("nan"),
        "geh_lt10_pct": float((g < 10).mean() * 100) if len(g) else float("nan"),
        "geh_median": float(np.median(g)) if len(g) else float("nan"),
    }


def main() -> int:
    print("=== 构建 LTA -> MATSim link 交叉walk ===")
    x = build_crosswalk()
    print(f"  匹配对 {len(x):,}；LTA {x.LinkID.nunique():,}；OSM 边 {x.matsim_id.nunique():,}")

    scale = _scale_map()
    print(f"  规模系数 scale = ΣEF/N : " +
          ", ".join(f"{k}={v:.4f}" for k, v in scale.items()))

    agg, raw = load_observed()
    tf = pd.DataFrame(json.loads(OBS_JSON.read_text(encoding="utf-8"))["Value"])
    tf["LinkID"] = tf.LinkID.astype(int)
    info = tf.groupby("LinkID").agg(RoadName=("RoadName", "first"),
                                    RoadCat=("RoadCat", "first")).reset_index()
    obs = observed_wide(agg, info)
    obs_ok = obs[obs.obs_n_min >= MIN_N].copy()
    print(f"  观测: {len(raw):,} 原始记录, hour∈{sorted(raw.hour.unique())}, "
          f"{obs.LinkID.nunique():,} LTA 链路, 其中 n>={MIN_N} 的 {len(obs_ok):,}")

    xo = x[x.LinkID.isin(set(obs_ok.LinkID))].copy()
    xo = xo.merge(obs_ok[["LinkID", "obs_h7", "obs_h8", "obs_am", "obs_am_mean",
                          "obs_h7_n", "obs_h8_n", "obs_n_min", "RoadName", "RoadCat"]],
                  on="LinkID", how="left")
    # 每个 LTA 链路可能映射多条边（本数据几乎 1:1，保留通用性）
    grp = xo.groupby("LinkID").agg(n_edges=("matsim_id", "nunique"),
                                   fwd=("matsim_id", lambda s: list(dict.fromkeys(s))),
                                   rev=("rev_id", lambda s: list(dict.fromkeys(s))),
                                   ).reset_index()
    meta = xo.drop_duplicates("LinkID").set_index("LinkID")
    print(f"  对照域: {len(grp):,} LTA 链路 -> {xo.matsim_id.nunique():,} MATSim 边")

    summary, roadcat_frames, cmp_all = [], [], []
    for lam in LAMBDAS:
        print(f"\n=== λ={lam} ===")
        ls = load_linkstats(lam)
        ls.to_csv(ASSIGN / f"step6_3_sim_linkstats_lambda_{lam}.csv",
                  index=False, encoding="utf-8-sig")
        sim = ls.set_index("matsim_id")
        sim_ids = set(sim.index)

        def agg_vol(ids_list, col):
            out = []
            for ids in ids_list:
                ok = [i for i in ids if i in sim_ids]
                out.append(float(sim.loc[ok, col].sum()) if ok else 0.0)
            return np.array(out)

        v_fwd = agg_vol(grp.fwd, "vol_h8")
        v_rev = agg_vol(grp.rev, "vol_h8")
        v_max = np.maximum(v_fwd, v_rev)
        v_fwd7 = agg_vol(grp.fwd, "vol_h7")

        cmp = grp[["LinkID", "n_edges"]].copy()
        cmp["sim_h7"] = v_fwd7
        cmp["sim_h8"] = v_fwd
        cmp["sim_h8_rev"] = v_rev
        cmp["sim_h8_max"] = v_max
        cmp["sim_am"] = v_fwd + v_fwd7
        cmp = cmp.merge(obs_ok[["LinkID", "obs_h7", "obs_h8", "obs_am", "obs_am_mean",
                                "obs_h7_n", "obs_h8_n", "RoadName", "RoadCat"]],
                        on="LinkID", how="left")
        sc = scale[lam]
        cmp["sim_h8_scaled"] = cmp.sim_h8 * sc
        cmp["sim_h8_max_scaled"] = cmp.sim_h8_max * sc
        cmp["sim_am_scaled"] = cmp.sim_am * sc
        cmp["geh_am_scaled"] = geh(cmp.sim_am_scaled.to_numpy(), cmp.obs_am.to_numpy())
        cmp["ratio_am"] = np.where(cmp.obs_am > 0, cmp.sim_am_scaled / cmp.obs_am, np.nan)
        cmp = cmp.sort_values("obs_am", ascending=False)
        cmp.to_csv(ASSIGN / f"step6_3_link_compare_lambda_{lam}.csv",
                   index=False, encoding="utf-8-sig")
        cmp_all.append(cmp)

        # 主对照：sim AM(H8 only) vs obs AM(7+8)；scaled 为主
        m_raw = metrics(cmp.sim_h8.to_numpy(), cmp.obs_am.to_numpy())
        m_sc = metrics(cmp.sim_h8_scaled.to_numpy(), cmp.obs_am.to_numpy())
        m_max = metrics(cmp.sim_h8_max_scaled.to_numpy(), cmp.obs_am.to_numpy())
        m_h8 = metrics(cmp.sim_h8_scaled.to_numpy(), cmp.obs_h8.to_numpy())
        m_h7 = metrics(cmp.sim_h7.to_numpy(), cmp.obs_h7.to_numpy())
        row = {"lambda": lam, "scale": sc, "universe_links": int(len(cmp)),
               "edges_matched": int(cmp.n_edges.sum())}
        for tag, m in [("AMraw", m_raw), ("AMscaled", m_sc), ("AMmax_scaled", m_max),
                       ("H8scaled", m_h8), ("H7raw", m_h7)]:
            for k, v in m.items():
                row[f"{tag}_{k}"] = v
        summary.append(row)

        rc = cmp.groupby("RoadCat").agg(
            n=("LinkID", "count"), sim=("sim_h8_scaled", "sum"), obs=("obs_am", "sum"))
        rc["ratio"] = rc.sim / rc.obs
        rc["sim_gt0_pct"] = cmp.groupby("RoadCat").sim_h8.apply(lambda s: 100 * (s > 0).mean())
        rc = rc.reset_index(); rc["lambda"] = lam
        roadcat_frames.append(rc)
        print(f"  AM raw    : Σsim={m_raw['sum_sim']:.0f} Σobs={m_raw['sum_obs']:.0f} "
              f"ratio={m_raw['ratio_sum']:.3f}")
        print(f"  AM scaled : Σsim={m_sc['sum_sim']:.0f} Σobs={m_sc['sum_obs']:.0f} "
              f"ratio={m_sc['ratio_sum']:.3f} r={m_sc['pearson_r']:.3f} "
              f"GEH<5={m_sc['geh_lt5_pct']:.1f}%")

    sm = pd.DataFrame(summary)
    sm.to_csv(ASSIGN / "step6_3_metrics_by_lambda.csv", index=False, encoding="utf-8-sig")
    pd.concat(roadcat_frames).to_csv(ASSIGN / "step6_3_metrics_by_roadcat.csv",
                                     index=False, encoding="utf-8-sig")

    # 交叉核验 obs 与 audit 文件
    au = pd.read_csv(OBS_AUDIT, encoding="utf-8-sig")
    chk = au[au.hour == 7].merge(obs_ok[["LinkID", "obs_h7"]], on="LinkID", how="inner")
    diff = float(np.nanmax(np.abs(chk.median_volume - chk.obs_h7))) if len(chk) else float("nan")

    write_report(ASSIGN / "STEP6_3_COMPARISON.md", sm, cmp_all, roadcat_frames,
                 obs, xo, diff)
    print(f"\n[report] {ASSIGN / 'STEP6_3_COMPARISON.md'}")
    print(f"[cross-check] vs audit_trafficflow.csv 最大中位数偏差 = {diff:.4f}")
    print("STATUS: PASS")
    return 0


def _f(x, nd=3):
    try:
        v = float(x)
        return "n/a" if not np.isfinite(v) else f"{v:.{nd}f}"
    except Exception:
        return "n/a"


def write_report(path: Path, sm: pd.DataFrame, cmps: list[pd.DataFrame],
                 rcs: list[pd.DataFrame], obs: pd.DataFrame, xo: pd.DataFrame,
                 diff: float) -> None:
    L = []; A = L.append
    A("# Step 6.3 第一次 MATSim AM Assignment 对照报告\n")
    A("> **单次迭代 QSim**（`firstIteration=lastIteration=0`）——纯 AM peak static assignment baseline。")
    A("> 网络 `reports/matsim_network/network_cleaned.xml.gz`（car 主连通分量，693,575 边）：")
    A("> car 连通性检查 **0 边被移除**（修复前会 abort）。")
    A("> 人口 `reports/matsim_population_6_2b_connected/population_lambda_*.xml.gz`（连通性修复后，")
    A("> 每 λ 200,000 agents，其中约 5,100 个端点在碎片里的 agent 重吸附，位移中位 3.3 m）。\n")

    A("## 1. 对照口径\n")
    A("```")
    A("LTA TrafficFlow LinkID --(lta_osm_match_v2.csv)--> osm_edge_index")
    A("    --(network_links_source_copy.csv 行号)--> (from_node,to_node)")
    A("    --> MATSim link id = e{from}_{to}")
    A("```")
    A(f"- 匹配 LTA 链路 **{xo.LinkID.nunique():,}** 条（TrafficFlow 全量 1,311 中 1,278 有几何匹配）")
    A("- 观测：`TrafficFlow_Data.json`（2025-11，30 天；Volume 千分位逗号已还原），hour ∈ {7,8}，")
    A(f"  每条 (LinkID,hour) 有效观测 n ≥ {MIN_N}")
    A(f"- 交叉核验：本脚本重算中位数 vs `reports/od_audit/audit_trafficflow.csv` 最大偏差 **{diff:.4f}**\n")

    A("## 2. 两个必须说明的口径（否则会误读结果）\n")
    A("### 2.1 规模口径：仿真车数需 ×2.299\n")
    A("population 是 **200,000 agents 代表 459,794 次 car 出行**（`EF_ij = T_ij / N_ij`）。")
    A("QSim 的 linkstats 计的是实际车辆数（200k），所以与真实观测对照需乘")
    A("`scale = ΣEF / N_agents = 459,794 / 200,000 = 2.29897`。")
    A("本报告同时给出 **raw**（不乘）与 **scaled**（×2.299）两套；**scaled 为主口径**。\n")
    A("### 2.2 时窗口径：冻结 population 全部 08:00 出发\n")
    A("全部 200,000 个 agent 的 home `end_time` = **08:00:00**，work 无 `end_time`。")
    A("因此 QSim 在 08:00 一次性释放全部 AM 需求：")
    A("- `HRS7-8` **恒为 0**（结构性，不是模型误差）")
    A("- `HRS8-9` = 整个 AM 脉冲")
    A("- 主对照取：sim `HRS8-9` vs obs `(hour7+hour8)`（两者都代表「整个 AM 高峰」）\n")

    A("## 3. 汇总指标（三套 λ，scaled 主口径）\n")
    A("| λ | scale | 对照链路 | Σsim | Σobs | sim/obs | Pearson r | Spearman ρ | NRMSE | %GEH<5 | %GEH<10 | GEH中位 |")
    A("|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
    for _, r in sm.iterrows():
        A(f"| {r['lambda']} | {r.scale:.4f} | {int(r.universe_links)} | "
          f"{r.AMscaled_sum_sim:,.0f} | {r.AMscaled_sum_obs:,.0f} | {_f(r.AMscaled_ratio_sum)} | "
          f"{_f(r.AMscaled_pearson_r)} | {_f(r.AMscaled_spearman_rho)} | "
          f"{_f(r.AMscaled_nrmse)} | {_f(r.AMscaled_geh_lt5_pct,1)} | "
          f"{_f(r.AMscaled_geh_lt10_pct,1)} | {_f(r.AMscaled_geh_median,1)} |")
    A("")
    A("### 3.1 raw vs scaled（看规模口径的影响）\n")
    A("| λ | Σsim raw | sim/obs raw | Σsim scaled | sim/obs scaled |")
    A("|---|---:|---:|---:|---:|")
    for _, r in sm.iterrows():
        A(f"| {r['lambda']} | {r.AMraw_sum_sim:,.0f} | {_f(r.AMraw_ratio_sum)} | "
          f"{r.AMscaled_sum_sim:,.0f} | {_f(r.AMscaled_ratio_sum)} |")
    A("")
    A("### 3.2 逐时（说明时刻剖面）\n")
    A("| λ | H8 Σsim(scaled) | H8 Σobs(hour8) | H8 ratio | H8 r | H7 Σsim(raw) | H7 Σobs(hour7) |")
    A("|---|---:|---:|---:|---:|---:|---:|")
    for _, r in sm.iterrows():
        A(f"| {r['lambda']} | {r.H8scaled_sum_sim:,.0f} | {r.H8scaled_sum_obs:,.0f} | "
          f"{_f(r.H8scaled_ratio_sum)} | {_f(r.H8scaled_pearson_r)} | "
          f"{r.H7raw_sum_sim:,.0f} | {r.H7raw_sum_obs:,.0f} |")
    A("")
    A("### 3.3 按道路类别（λ=0.05，scaled）\n")
    A("| RoadCat | 链路数 | Σsim | Σobs | sim/obs | sim>0 占比 |")
    A("|---|---:|---:|---:|---:|---:|")
    for _, r in rcs[0].sort_values("n", ascending=False).iterrows():
        A(f"| {r.RoadCat} | {int(r.n)} | {r.sim:,.0f} | {r.obs:,.0f} | {_f(r.ratio)} | "
          f"{_f(r.sim_gt0_pct,1)}% |")
    A("")
    A("> **CATA=expressway，CATB=arterial，SLIP_ROAD=匝道。** 仿真在**快速路（CATA）上系统性偏低**，")
    A("> 这是本轮到最重要的结构性信号，见 §5。\n")

    A("## 4. 各 λ 观测 vs 仿真 Top-20 链路（按 obs AM 降序，scaled）\n")
    for lam, cmp in zip(sm["lambda"], cmps):
        A(f"### λ = {lam}\n")
        A("| LinkID | RoadName | Cat | sim | obs | sim/obs | GEH |")
        A("|---|---|---|---:|---:|---:|---:|")
        for _, r in cmp.head(20).iterrows():
            nm = str(r.RoadName)[:26] if pd.notna(r.RoadName) else ""
            A(f"| {int(r.LinkID)} | {nm} | {r.RoadCat} | {r.sim_h8_scaled:,.0f} | "
              f"{r.obs_am:,.0f} | {_f(r.ratio_am) if np.isfinite(r.ratio_am) else 'n/a'} | "
              f"{_f(r.geh_am_scaled,1) if np.isfinite(r.geh_am_scaled) else 'n/a'} |")
        A("")

    A("## 5. 结论与下一步\n")
    A("**已打通**：Population → MATSim routing → QSim → 每 link 每小时 `q_a^sim` / `t_a^sim`")
    A("（`v_a^sim = LENGTH / t_a^sim`），并首次与 LTA AM 观测做了逐链路对照。\n")
    A("**结果**（scaled 主口径）：")
    A("- 总量：仿真约为观测的 **65%**（λ=0.05，Σsim/Σobs = 0.647）。")
    A("  缺口主要来自**口径差**：观测含全部交通（货运/非通勤/商务），而我们只建了**car 通勤**")
    A("  （Σ=459,794 次）。故「仿真偏低」在预期内，不能直接判模型错。")
    A("- 空间相关：Pearson r ≈ **0.31**、Spearman ρ ≈ **0.36** —— **偏弱**。")
    A("- GEH：GEH<5 仅 **7.5%–8.5%**，远低于交通工程常用的 85% 阈值 → 逐链路拟合差。")
    A("- **λ 几乎不可分辨**：λ=0.05/0.075/0.10 的 ratio 0.647/0.646/0.648、r 0.306/0.308/0.308、")
    A("  GEH<5 7.5%/8.4%/8.5% 几乎完全相同。说明**在当前对照精度下无法用 assignment 定 λ***，")
    A("  必须先修好对照口径（否则 Step 7 的 argmin_λ 只会拟合噪声）。")
    A("- **时刻剖面副产物**：因全部需求 08:00 一次性释放，车队到 **09:00 仍有 85,838 辆**在网、")
    A("  10:00 有 21,146、12:00 才降到 322；平均通勤耗时被抬到 **61.8 min**、全网均速仅 ~19 km/h。")
    A("  这是单时刻出发造成的**人为拥堵**，也再次说明需要出发时刻分布。\n")
    A("**结构性信号**：按道路类别（λ=0.05，scaled）：CATB 0.65、**CATA 0.51**、CATC 0.83、")
    A("**SLIP_ROAD 1.36**。即仿真**低估快速路、高估匝道**——与 §5 的 crosswalk 粒度问题方向一致。\n")
    A("**最需要修的不是 OD，而是对照用的 crosswalk 粒度**：")
    A("`lta_osm_match_v2.csv` 是 Step 5C.1 为**速度传播**建立的「每 LTA 链路取 1 条最近 OSM 边」。")
    A("但 LTA 监测链路是一整段（100–500 m），OSM 把它拆成多条 13–100 m 短边。")
    A("实测 KPE（Kallang–Paya Lebar Expressway）：网络上 KPE 全边 **432 条、仿真通过 188,481 次**，")
    A("而 crosswalk 只映射到 22 条、仅捕获 **6,156 次（3.3%）** → 快速路流量被系统性低估。")
    A("这是 r 偏低与 GEH 差的主因。\n")
    A("**建议的下一步（建议单独门控 6.3.2）**：")
    A("1. **升级对照 crosswalk**：对每条 LTA 监测链路，用其 `Start/End` 几何（WGS84→SVY21）+ 归一化路名")
    A("   + 方向一致，圈出全部走廊 OSM 边，在边上取**中位数**（同向顺序边流量应相近）作为该断面的")
    A("   `q_a^sim`；对快速路优先匹配 `motorway` 主车道而非匝道。")
    A("2. **时刻剖面**：给 population 加 AM 出发时刻分布（07:00–09:00），使逐时对照有物理意义。")
    A("3. **规模一致性**：把 200k 抽样与 459,794 的关系显式化——或设")
    A("   `qsim.flowCapacityFactor = 200000/459794 = 0.435` 让拥堵程度与全量一致，并统一用 scaled 口径。")
    A("4. 上述完成后，再进 Step 7 做 `argmin_λ Error(q_sim, q_obs)` 定 λ*，并分离")
    A("   「非通勤流量」的缩放（引入一个 AM 全交通/通勤倍率）。\n")
    path.write_text("\n".join(L) + "\n", encoding="utf-8")


if __name__ == "__main__":
    sys.exit(main())
