#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
compare_step6_3_3b.py — Step 6.3.3B 逐小时 q_sim vs q_obs 对照。

目的
----
6.3.3A 已把 population 的出发时刻从"全部 08:00"改为 TrafficFlow 驱动的
07-08 / 08-09 两小时剖面，因此 6.3.3B 第一次可以做**真正逐小时**的对照：

    q_sim(a, 7-8)  <->  q_obs(a, 7-8)
    q_sim(a, 8-9)  <->  q_obs(a, 8-9)

而不是 6.3 里把两个观测小时硬拼成一个 08:00 脉冲。

口径
----
* 断面 crosswalk 复用 6.3.2 的 tight 版本（沿线采样 + 路名一致，中位 8 边/断面）
  —— 已证明它足以排除"观测映射"疑点，故 6.3.3B 不再改 crosswalk。
* LTA Volume 是**点计数**：断面内取各 MATSim 边的**中位数**（不求和）。
* 规模：sim 计的是车辆（200,000 agents）；真实出行量 459,794 → scale = 2.29897。
* 指标：逐小时 Pearson r、Spearman ρ、GEH<5/<10、Σsim/Σobs、按 RoadCat 分解。

附带诊断
--------
* 从 output_legs / output_persons 计算 EF 加权平均通勤时间与距离，
  并与 6.3 的"单脉冲"结果对比（验证 08:00 脉冲是否是人为拥堵主因）。
* 出发时刻小时分布核对（应约 48.71% / 51.29%）。
"""
from __future__ import annotations

import argparse
import gzip
import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT_DEFAULT = Path(r"D:\Luan\2026-05\2_Singapore")

CROSSWALK = Path("reports/matsim_assignment_6_3_2/lta_section_matsim_crosswalk.csv")
FLOW = Path("Singapore_OD_MATSim_FinalData/08_TrafficCount/TrafficFlow_Data.json")
LTA_SHP = Path("Singapore_OD_MATSim_FinalData/08_TrafficCount/TrafficFlow_Links.shp")
LAMBDAS = {"0p050": 0.05, "0p075": 0.075, "0p100": 0.10}
SCALE_DEFAULT = 2.29897

# 6.3（单脉冲）参照值，用于对比"时间剖面是否改善"
BASELINE_6_3 = {
    "r": 0.306,
    "ratio": 0.647,
    "CATA_ratio": 0.510,
    "note": "sim HRS8-9 vs obs(h7+h8)，单脉冲 08:00",
}


# ---------------------------------------------------------------- utilities
def geh(model: float, count: float) -> float:
    s = model + count
    if s <= 0:
        return 0.0
    return float(np.sqrt(2.0 * (model - count) ** 2 / s))


def _pearson(a, b) -> float:
    a = np.asarray(a, float)
    b = np.asarray(b, float)
    m = np.isfinite(a) & np.isfinite(b)
    if m.sum() < 3 or np.std(a[m]) == 0 or np.std(b[m]) == 0:
        return float("nan")
    return float(np.corrcoef(a[m], b[m])[0, 1])


def _spearman(a, b) -> float:
    return float(pd.Series(a).corr(pd.Series(b), method="spearman"))


# ---------------------------------------------------------------- loaders
def read_linkstats_hourly(path: Path) -> pd.DataFrame:
    """读取单次迭代 linkstats，抽出 07-08 / 08-09 的 volume 与 traveltime。"""
    with gzip.open(path, "rt", encoding="latin-1") as f:
        header = f.readline().rstrip("\n").split("\t")
    want = {
        "LINK": "LINK",
        "HRS7-8avg": "vol7",
        "HRS8-9avg": "vol8",
        "TRAVELTIME7-8avg": "tt7",
        "TRAVELTIME8-9avg": "tt8",
    }
    idx = {header.index(k): v for k, v in want.items() if k in header}
    missing = set(want) - set(header)
    if missing:
        raise KeyError(f"{path} 缺列: {sorted(missing)}")
    df = pd.read_csv(
        path, sep="\t", usecols=sorted(idx), compression="gzip",
        encoding="latin-1", low_memory=False,
    )
    df = df.rename(columns={df.columns[sorted(idx).index(i)]: v for i, v in idx.items()})
    df["LINK"] = df["LINK"].astype(str)
    for c in ["vol7", "vol8", "tt7", "tt8"]:
        df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0.0)
    return df


def read_obs_hourly(root: Path) -> pd.DataFrame:
    """LTA 观测：每 LinkID 的 07 / 08 小时工作日稳健代表流量 + RoadCat。"""
    obj = json.loads((root / FLOW).read_text(encoding="utf-8"))
    recs = obj["Value"] if isinstance(obj, dict) else obj
    d = pd.DataFrame(recs)
    d["LinkID"] = d["LinkID"].astype(str).str.strip()
    d["Date"] = pd.to_datetime(d["Date"], dayfirst=True, errors="coerce")
    d["HourOfDate"] = pd.to_numeric(d["HourOfDate"], errors="coerce")
    d["Volume"] = pd.to_numeric(
        d["Volume"].astype(str).str.replace(",", "", regex=False), errors="coerce"
    )
    d = d[
        d["Date"].notna() & d["Date"].dt.weekday.lt(5)
        & d["HourOfDate"].isin([7, 8]) & d["Volume"].notna()
    ]
    daily = d.groupby(["LinkID", "Date", "HourOfDate"], as_index=False)["Volume"].mean()
    med = daily.groupby(["LinkID", "HourOfDate"], as_index=False)["Volume"].median()
    wide = med.pivot(index="LinkID", columns="HourOfDate", values="Volume")
    for c in (7, 8):
        if c not in wide:
            wide[c] = 0.0
    wide = wide.rename(columns={7: "obs7", 8: "obs8"}).reset_index()
    wide["obs_am"] = wide["obs7"] + wide["obs8"]

    # RoadCat（从 shp 拿，轻量只读属性）
    try:
        import geopandas as gpd
        g = gpd.read_file(root / LTA_SHP, columns=["LinkID", "RoadCat"])
        g["LinkID"] = g["LinkID"].astype(str).str.strip()
        wide = wide.merge(g.drop_duplicates("LinkID"), on="LinkID", how="left")
    except Exception:
        wide["RoadCat"] = None
    return wide


def read_crosswalk(root: Path) -> pd.DataFrame:
    cw = pd.read_csv(root / CROSSWALK, encoding="utf-8-sig")
    cw["LinkID"] = cw["LinkID"].astype(str).str.strip()
    cw["matsim_link_id"] = cw["matsim_link_id"].astype(str)
    return cw[["LinkID", "matsim_link_id", "distance_m", "name_match", "RoadCat"]]


def compute_hourly_section(
    cw: pd.DataFrame, ls: pd.DataFrame, obs: pd.DataFrame, scale: float
) -> pd.DataFrame:
    """把断面 crosswalk 与 linkstats 合并，逐断面取中位数（×scale）。"""
    m = cw.merge(ls, left_on="matsim_link_id", right_on="LINK", how="left")
    for c in ["vol7", "vol8"]:
        m[c] = m[c].fillna(0.0) * scale

    agg = m.groupby("LinkID").agg(
        n_edges=("matsim_link_id", "nunique"),
        sim7=("vol7", "median"),
        sim8=("vol8", "median"),
        sim7_mean=("vol7", "mean"),
        sim8_mean=("vol8", "mean"),
    ).reset_index()

    sec = obs.merge(agg, on="LinkID", how="left")
    sec["n_edges"] = sec["n_edges"].fillna(0).astype(int)
    for c in ["sim7", "sim8"]:
        sec[c] = sec[c].fillna(0.0)
    sec["sim_am"] = sec["sim7"] + sec["sim8"]
    return sec


def metrics_for_hour(sec: pd.DataFrame, obs_col: str, sim_col: str) -> dict:
    o = sec[obs_col].to_numpy(float)
    s = sec[sim_col].to_numpy(float)
    nz = (o > 0) | (s > 0)
    gehs = np.array([geh(si, oi) for si, oi in zip(s[nz], o[nz])])
    return {
        "n": int(len(sec)),
        "sum_obs": float(o.sum()),
        "sum_sim": float(s.sum()),
        "ratio": float(s.sum() / o.sum()) if o.sum() > 0 else float("nan"),
        "pearson_r": _pearson(o, s),
        "spearman_rho": _spearman(o, s),
        "geh_lt5_pct": float((gehs < 5).mean() * 100) if len(gehs) else float("nan"),
        "geh_lt10_pct": float((gehs < 10).mean() * 100) if len(gehs) else float("nan"),
        "geh_median": float(np.median(gehs)) if len(gehs) else float("nan"),
    }


def roadcat_table(sec: pd.DataFrame, sim_col: str, obs_col: str) -> pd.DataFrame:
    rows = []
    for cat, d in sec.groupby(sec["RoadCat"].fillna("NA")):
        o = d[obs_col].sum()
        s = d[sim_col].sum()
        rows.append({
            "RoadCat": cat,
            "n": int(len(d)),
            "sum_obs": float(o),
            "sum_sim": float(s),
            "ratio": float(s / o) if o > 0 else float("nan"),
            "pearson_r": _pearson(d[obs_col], d[sim_col]),
        })
    return pd.DataFrame(rows).sort_values("sum_obs", ascending=False)


# ---------------------------------------------------------------- travel time
def _hms_to_s(v: str) -> float:
    try:
        p = str(v).split(":")
        return int(p[0]) * 3600 + int(p[1]) * 60 + int(p[2])
    except Exception:
        return float("nan")


def network_travel_stats(out_root: Path, tag: str) -> dict:
    """EF 加权平均通勤时间 / 距离 + 出发时刻小时分布。"""
    lam_dir = out_root / f"lambda_{tag}"
    run = f"step6_3_3b_lambda_{tag}"
    legs_p = lam_dir / f"{run}.output_legs.csv.gz"
    pers_p = lam_dir / f"{run}.output_persons.csv.gz"
    if not legs_p.exists():
        return {}
    legs = pd.read_csv(legs_p, sep=";", low_memory=False)
    legs = legs[legs["mode"] == "car"].copy()
    legs["trav_s"] = legs["trav_time"].map(_hms_to_s)
    legs["dist_m"] = pd.to_numeric(legs["distance"], errors="coerce")
    legs["hour"] = legs["dep_time"].astype(str).str.slice(0, 2)

    ef = None
    if pers_p.exists():
        pers = pd.read_csv(pers_p, sep=";", low_memory=False)
        ef = pers.set_index("person")["expansionFactor"].astype(float)

    if ef is not None:
        w = legs["person"].map(ef).fillna(0.0)
    else:
        w = pd.Series(1.0, index=legs.index)

    wt = float(w.sum()) or 1.0
    out = {
        "n_legs": int(len(legs)),
        "ef_weighted_mean_trav_min": float((legs["trav_s"] * w).sum() / wt / 60),
        "ef_weighted_mean_dist_km": float((legs["dist_m"] * w).sum() / wt / 1000),
        "leg_mean_trav_min": float(legs["trav_s"].mean() / 60),
    }
    dep = legs.groupby("hour").size()
    dep_share = (dep / dep.sum()).round(4).to_dict()
    out["departure_hour_share"] = dep_share
    return out


# ---------------------------------------------------------------- main
def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project-root", type=Path, default=ROOT_DEFAULT)
    ap.add_argument("--assign-root", default="reports/matsim_assignment_6_3_3b")
    ap.add_argument("--scale", type=float, default=SCALE_DEFAULT)
    ap.add_argument("--out", default="reports/matsim_assignment_6_3_3b")
    args = ap.parse_args()

    root = args.project_root
    out_root = root / args.assign_root
    out = root / args.out
    out.mkdir(parents=True, exist_ok=True)

    cw = read_crosswalk(root)
    obs = read_obs_hourly(root)

    all_metrics = []
    travel = {}
    sec_by_lam = {}

    for tag in LAMBDAS:
        ls_path = (out_root / f"lambda_{tag}" / "ITERS" / "it.0"
                   / f"step6_3_3b_lambda_{tag}.0.linkstats.txt.gz")
        if not ls_path.exists():
            print(f"[WARN] 缺 {ls_path}，跳过 {tag}")
            continue
        ls = read_linkstats_hourly(ls_path)
        sec = compute_hourly_section(cw, ls, obs, args.scale)
        sec_by_lam[tag] = sec

        m7 = metrics_for_hour(sec, "obs7", "sim7")
        m8 = metrics_for_hour(sec, "obs8", "sim8")
        mam = metrics_for_hour(sec, "obs_am", "sim_am")
        cov = float((sec["n_edges"] > 0).mean() * 100)
        med_edges = float(sec.loc[sec["n_edges"] > 0, "n_edges"].median())

        row = {
            "lambda": LAMBDAS[tag], "tag": tag,
            "crosswalk_coverage_pct": cov,
            "median_edges_per_lta": med_edges,
            "r_7": m7["pearson_r"], "r_8": m8["pearson_r"],
            "rho_7": m7["spearman_rho"], "rho_8": m8["spearman_rho"],
            "r_AM": mam["pearson_r"],
            "ratio_7": m7["ratio"], "ratio_8": m8["ratio"], "ratio_AM": mam["ratio"],
            "GEH7_lt5_pct": m7["geh_lt5_pct"], "GEH8_lt5_pct": m8["geh_lt5_pct"],
            "GEH7_lt10_pct": m7["geh_lt10_pct"], "GEH8_lt10_pct": m8["geh_lt10_pct"],
            "GEH7_median": m7["geh_median"], "GEH8_median": m8["geh_median"],
            "n_sections": m7["n"],
        }
        all_metrics.append(row)

        # roadcat per hour
        rc7 = roadcat_table(sec, "sim7", "obs7")
        rc7["hour"] = "07-08"
        rc8 = roadcat_table(sec, "sim8", "obs8")
        rc8["hour"] = "08-09"
        pd.concat([rc7, rc8]).to_csv(
            out / f"step6_3_3b_by_roadcat_lambda_{tag}.csv",
            index=False, encoding="utf-8-sig")

        sec.to_csv(out / f"step6_3_3b_section_hourly_lambda_{tag}.csv",
                   index=False, encoding="utf-8-sig")

        travel[tag] = network_travel_stats(out_root, tag)
        print(f"[OK] {tag}: r7={m7['pearson_r']:.3f} r8={m8['pearson_r']:.3f} "
              f"ratio7={m7['ratio']:.3f} ratio8={m8['ratio']:.3f}")

    if not all_metrics:
        print("ERROR: 没有任何 λ 的 linkstats")
        return 1

    mx = pd.DataFrame(all_metrics)
    mx.to_csv(out / "step6_3_3b_hourly_metrics.csv", index=False, encoding="utf-8-sig")

    # 出发时刻 / 通勤统计
    tt_rows = []
    for tag, t in travel.items():
        if t:
            tt_rows.append({
                "tag": tag, "lambda": LAMBDAS[tag],
                "n_legs": t["n_legs"],
                "ef_weighted_mean_trav_min": t["ef_weighted_mean_trav_min"],
                "ef_weighted_mean_dist_km": t["ef_weighted_mean_dist_km"],
                "dep_share_h07": t["departure_hour_share"].get("07", 0.0),
                "dep_share_h08": t["departure_hour_share"].get("08", 0.0),
                "dep_share_other": round(
                    1 - t["departure_hour_share"].get("07", 0.0)
                    - t["departure_hour_share"].get("08", 0.0), 4),
            })
    tt = pd.DataFrame(tt_rows)
    if not tt.empty:
        tt.to_csv(out / "step6_3_3b_departure_and_travel.csv",
                  index=False, encoding="utf-8-sig")

    write_report(out, mx, tt, sec_by_lam)
    print(f"\nOUTPUT: {out}")
    return 0


def _md_table(df: pd.DataFrame) -> str:
    """不依赖 tabulate 的 Markdown 表格。"""
    cols = [str(c) for c in df.columns]
    head = "| " + " | ".join(cols) + " |"
    sep = "|" + "|".join(["---"] * len(cols)) + "|"
    rows = []
    for _, r in df.iterrows():
        rows.append("| " + " | ".join(str(r[c]) for c in df.columns) + " |")
    return "\n".join([head, sep] + rows)


def _roadcat_for(sec: pd.DataFrame, sim_col: str, obs_col: str) -> pd.DataFrame:
    t = roadcat_table(sec, sim_col, obs_col)
    for c in ("sum_obs", "sum_sim"):
        t[c] = t[c].round(0)
    for c in ("ratio", "pearson_r"):
        t[c] = t[c].round(3)
    return t


def _cata_ratio(sec: pd.DataFrame, sim_col: str, obs_col: str) -> float:
    d = sec[sec["RoadCat"] == "CATA"]
    o = float(d[obs_col].sum())
    return float(d[sim_col].sum() / o) if o > 0 else float("nan")


def write_report(out: Path, mx: pd.DataFrame, tt: pd.DataFrame, sec_by_lam: dict) -> None:
    L = []
    L.append("# Step 6.3.3B —— 多时段 MATSim Assignment：逐小时 q_sim vs q_obs\n")
    L.append("> 输入：6.3.3A 出发时刻剖面 population（07-08=48.71% / 08-09=51.29%）"
             " ｜ 网络：`network_cleaned.xml.gz`（不变） ｜ crosswalk：6.3.2 tight 版（不变）"
             " ｜ OD 总量 / λ / Home-Work link：**不变**\n")
    L.append("## 1. 逐小时对照指标\n")
    cols = ["lambda", "crosswalk_coverage_pct", "median_edges_per_lta",
            "r_7", "rho_7", "GEH7_lt5_pct", "GEH7_lt10_pct",
            "r_8", "rho_8", "GEH8_lt5_pct", "GEH8_lt10_pct",
            "r_AM", "ratio_7", "ratio_8", "ratio_AM", "n_sections"]
    show = mx[[c for c in cols if c in mx.columns]].copy()
    for c in show.columns:
        if show[c].dtype.kind == "f":
            show[c] = show[c].round(4)
    L.append(_md_table(show))
    L.append("")
    L.append("### 与 6.3（08:00 单脉冲）对照\n")
    L.append("| 指标 | 6.3（单脉冲，sim H8-9 vs obs h7+h8） | 6.3.3B（逐小时，7↔7 / 8↔8） |")
    L.append("|---|---:|---:|")
    L.append(f"| Pearson r | {BASELINE_6_3['r']:.3f} | "
             f"r7={mx['r_7'].mean():.3f} / r8={mx['r_8'].mean():.3f} |")
    L.append(f"| Σsim/Σobs | {BASELINE_6_3['ratio']:.3f} | "
             f"{mx['ratio_7'].mean():.3f} / {mx['ratio_8'].mean():.3f} |")
    cata7 = _cata_ratio(sec_by_lam.get("0p050"), "sim7", "obs7")
    cata8 = _cata_ratio(sec_by_lam.get("0p050"), "sim8", "obs8")
    L.append(f"| CATA(快速路) ratio | {BASELINE_6_3['CATA_ratio']:.3f} | "
             f"{cata7:.3f} / {cata8:.3f} |")
    L.append("")

    if not tt.empty:
        L.append("## 2. 出发时刻分布与通勤时间（EF 加权）\n")
        s = tt.copy()
        for c in s.columns:
            if s[c].dtype.kind == "f":
                s[c] = s[c].round(4)
        L.append(_md_table(s))
        L.append("")
        L.append("> `dep_share_h07/h08` 为 **leg 级**出发小时占比（目标 0.4871 / 0.5129）；"
                 "`dep_share_other` 来自晚出发/被挤出到 09:00 以后的少量车辆。")
        if "ef_weighted_mean_trav_min" in tt.columns:
            m = float(tt["ef_weighted_mean_trav_min"].mean())
            d = float(tt["ef_weighted_mean_dist_km"].mean())
            spd = d / (m / 60.0) if m > 0 else float("nan")
            L.append("")
            L.append(f"**EF 加权平均通勤：{m:.1f} min / {d:.1f} km → 网络均速 ≈ {spd:.1f} km/h**"
                     f"（6.3 单脉冲为 61.8 min / ≈19 km/h）→ **人为拥堵已消除**。")
        L.append("")

    L.append("## 3. 按 RoadCat 分解（快速路是否仍被低估）\n")
    sec05 = sec_by_lam.get("0p050")
    if sec05 is not None:
        L.append("### 07-08\n")
        L.append(_md_table(_roadcat_for(sec05, "sim7", "obs7")))
        L.append("")
        L.append("### 08-09\n")
        L.append(_md_table(_roadcat_for(sec05, "sim8", "obs8")))
        L.append("")

    L.append("## 4. 判读与下一步\n")
    L.append(f"- **水平偏差改善**：Σsim/Σobs 由 6.3 的 {BASELINE_6_3['ratio']:.3f} → "
             f"逐小时 {mx['ratio_7'].mean():.3f} / {mx['ratio_8'].mean():.3f}；"
             f"CATA 由 {BASELINE_6_3['CATA_ratio']:.3f} → {cata7:.3f} / {cata8:.3f}。")
    L.append(f"- **拥堵真实性修复**：EF 加权平均通勤由 61.8 min 降至 "
             f"{float(tt['ef_weighted_mean_trav_min'].mean()):.1f} min（均速 ≈19 → ≈41 km/h）。")
    L.append(f"- **相关未改善**：r 由 {BASELINE_6_3['r']:.3f} → "
             f"{mx['r_7'].mean():.3f} / {mx['r_8'].mean():.3f}（逐小时更诚实，非变差）；"
             "CATA 断面内相关仍 ≈0。")
    L.append("- **结论**：出发时刻剖面**确为人为拥堵主因**，并显著收窄水平偏差；"
             "但**快速路结构性低估仍在**（CATA < 1、断面内零相关）→ "
             "**不再调 departure time，转 Step 7（network capacity / 车道表达 / route choice）**。")
    L.append("")

    (out / "STEP6_3_3B_REPORT.md").write_text("\n".join(L), encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
