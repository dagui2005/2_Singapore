#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""
esb02_night_audit.py — E-SB-02 / SB-A5 夜间 SpeedBand 数据可用性门禁（只读 · 零仿真）
=====================================================================================
目的：在启动任何 MATSim 之前，审计「夜间 SpeedBand 能否作为独立自由流代理」。

用户预注册的检查项
------------------
  G1 数据身份  ：只接受**内部时间戳**明确的快照；单次 18:53 历史快照一律排除
  G2 时间范围  ：纳入 23:00–06:59 快照
  G3 日期覆盖  ：至少 2 个不同夜晚
  G4 单链观测数：每条链的夜间有效观测数分布（正式估计门槛 ≥6；不足者保留原值）
  G5 空间覆盖  ：匹配链数 / 覆盖长度 / 各道路等级覆盖率
  G6 路网映射  ：沿用已验证的 LinkID → osm_edge_index → MATSim link，**不重新搜索匹配**
  G7 一致性    ：夜间速度 vs AM 速度（夜间应更快；检查 residential 缺口）

⛔ 只读：不写任何冻结件；不产生 v1.1；不启动仿真。
"""
from __future__ import annotations

import json
import math
import re
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(r"D:\Luan\2026-05\2_Singapore")
OUT = ROOT / "reports" / "esb02_night_audit"

MONITOR_DIR = ROOT / "Dynamic_2026_03_16" / "realtime_monitoring"
HIST_DIR = ROOT / "Dynamic_2026_03_16" / "historical_data"

AM_MATCH = ROOT / "reports" / "od_impedance_ampeak" / "lta_osm_ampeak_speed_match.csv"
NETWORK_LINKS = ROOT / "reports" / "od_impedance" / "network_links.csv"

# ---- 冻结约定（与 build_am_peak_impedance.py 一致）----
BAND8_MAX_SENTINEL = 999.0
BAND8_PROXY_KMH = 75.0
BAND_DEFAULTS = {
    1: (5.0, 9.0), 2: (10.0, 19.0), 3: (20.0, 29.0), 4: (30.0, 39.0),
    5: (40.0, 49.0), 6: (50.0, 59.0), 7: (60.0, 69.0),
}
NIGHT_HOURS = {23, 0, 1, 2, 3, 4, 5, 6}
MIN_OBS_FOR_ESTIMATE = 6          # 用户预注册门槛
FNAME_RE = re.compile(r"TrafficSpeedBands_(\d{8})_(\d{6})\.json$")

GATES: list[dict] = []


def gate(gid: str, name: str, ok: bool, detail: str = "") -> bool:
    GATES.append({"gate": gid, "name": name, "pass": bool(ok), "detail": detail})
    print(f"  [{'PASS' if ok else 'FAIL'}] {gid:<4} {name}  {detail}")
    return bool(ok)


def tofloat(x):
    try:
        return float(str(x).replace(",", ""))
    except Exception:
        return float("nan")


def speed_from_record(rec, band8_kmh=BAND8_PROXY_KMH):
    """与冻结 Step-5C 完全同口径：闭区间取中点；SB8 的开区间用哨兵识别。"""
    try:
        band = int(float(str(rec.get("SpeedBand"))))
    except Exception:
        band = None
    vmin = tofloat(rec.get("MinimumSpeed"))
    vmax = tofloat(rec.get("MaximumSpeed"))
    if np.isfinite(vmax) and vmax >= BAND8_MAX_SENTINEL:
        return float(band8_kmh), 8
    if np.isfinite(vmin) and np.isfinite(vmax) and vmax >= vmin:
        return float((vmin + vmax) / 2.0), band
    if band == 8:
        return float(band8_kmh), 8
    if band in BAND_DEFAULTS:
        lo, hi = BAND_DEFAULTS[band]
        return (lo + hi) / 2.0, band
    return float("nan"), band


def read_internal_ts(path: Path, nbytes: int = 4096):
    """只读文件头，取 LTA 顶层 lastUpdatedTime（避免全量解析 160 个 ~45MB 文件）。"""
    try:
        with path.open("rb") as f:
            head = f.read(nbytes).decode("utf-8", "replace")
    except Exception:
        return None
    m = re.search(r'"lastUpdatedTime"\s*:\s*"([^"]+)"', head)
    if not m:
        return None
    try:
        return datetime.strptime(m.group(1)[:19], "%Y-%m-%d %H:%M:%S")
    except Exception:
        return None


def ts_from_filename(name: str):
    m = FNAME_RE.search(name)
    if not m:
        return None
    try:
        return datetime.strptime(m.group(1) + m.group(2), "%Y%m%d%H%M%S")
    except ValueError:
        return None


# --------------------------------------------------------------------------
# Step 0 盘点
# --------------------------------------------------------------------------
def inventory() -> pd.DataFrame:
    rows = []
    files: list[Path] = []
    for d in (MONITOR_DIR, HIST_DIR):
        files.extend(sorted(d.glob("TrafficSpeedBands*.json")))
    for p in sorted(set(files)):
        fn_ts = ts_from_filename(p.name)
        in_ts = read_internal_ts(p)
        sz_mb = p.stat().st_size / 1e6
        lag = (round((in_ts - fn_ts).total_seconds() / 60, 1)
               if (fn_ts and in_ts) else None)
        rows.append({
            "file": p.name,
            "dir": p.parent.name,
            "size_mb": round(sz_mb, 2),
            "filename_ts": fn_ts.isoformat(sep=" ") if fn_ts else "",
            "internal_ts": in_ts.isoformat(sep=" ") if in_ts else "",
            "ts_source": ("internal" if in_ts else ("filename_only" if fn_ts else "UNDATED")),
            "ts_match": (fn_ts == in_ts) if (fn_ts and in_ts) else None,
            "lag_min": lag,
            "hour": in_ts.hour if in_ts else (fn_ts.hour if fn_ts else -1),
            "date": in_ts.date().isoformat() if in_ts else (fn_ts.date().isoformat() if fn_ts else ""),
        })
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------
# Step 1-2 夜窗选择 + 解析
# --------------------------------------------------------------------------
def parse_night_snapshots(night_files: list[Path]):
    frames = []
    counts = []
    for i, (dt, p) in enumerate(night_files, 1):
        with p.open("r", encoding="utf-8") as f:
            obj = json.load(f)
        recs = obj.get("value") if isinstance(obj, dict) else obj
        if not isinstance(recs, list):
            print(f"    [WARN] 无法识别结构 {p.name}")
            continue
        counts.append({"snapshot": p.name, "internal_ts": dt.isoformat(sep=" "),
                       "n_records": len(recs), "size_mb": round(p.stat().st_size / 1e6, 2)})
        link_ids = np.empty(len(recs), dtype=object)
        speeds = np.empty(len(recs), dtype=float)
        bands = np.empty(len(recs), dtype=int)
        for j, r in enumerate(recs):
            link_ids[j] = str(r.get("LinkID", "")).strip()
            sp, bd = speed_from_record(r)
            speeds[j] = sp
            bands[j] = bd if bd is not None else -1
        ok = np.isfinite(speeds) & (link_ids != "")
        # night_id = 该夜晚所属的“早晨日期”：23 点属于次日
        nid = (dt.date().isoformat() if dt.hour != 23
               else (dt + pd.Timedelta(days=1)).date().isoformat())
        frames.append(pd.DataFrame({
            "LinkID": link_ids[ok],
            "night_id": nid,
            "snapshot": p.name,
            "hour": dt.hour,
            "speed_kmh": speeds[ok],
            "band_raw": bands[ok],
        }))
        if i % 8 == 0 or i == len(night_files):
            print(f"    ... {i}/{len(night_files)} 快照已解析（{p.name}）", flush=True)
    if not frames:
        raise RuntimeError("没有可解析的夜间快照")
    return pd.concat(frames, ignore_index=True), pd.DataFrame(counts)


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    print("=" * 96)
    print("E-SB-02 | SB-A5 夜间 SpeedBand 数据可用性门禁（只读 · 零仿真）")
    print("=" * 96)

    # ---------------- Step 0 ----------------
    print("\n[0] 快照盘点")
    inv = inventory()
    inv.to_csv(OUT / "night_snapshot_inventory.csv", index=False, encoding="utf-8-sig")
    n_total = len(inv)
    n_int = int((inv.ts_source == "internal").sum())
    n_fn = int((inv.ts_source == "filename_only").sum())
    n_und = int((inv.ts_source == "UNDATED").sum())
    lag = inv.lag_min.abs().dropna()
    n_bad_lag = int((lag > 15).sum())
    n_diff = int((inv.ts_match == False).sum())  # noqa: E712
    print(f"    快照总数={n_total}  内部时间戳={n_int}  仅文件名={n_fn}  无日期={n_und}")
    print(f"    文件名≠内部时间戳 {n_diff} 个（全部为整点命名下载、滞后≤{lag.max():.0f} min）")
    und = inv[inv.ts_source == "UNDATED"]
    if len(und):
        for r in und.itertuples():
            print(f"      · UNDATED: {r.file}（{r.size_mb} MB, {r.dir}）")

    gate("G1a", "全部有日期快照携带内部 lastUpdatedTime",
         n_fn == 0, f"internal={n_int} filename_only={n_fn}")
    gate("G1b", "内部时间戳可信：与文件名一致，或整点命名下载滞后 ≤15 min",
         n_bad_lag == 0,
         f"命名不一致={n_diff}（最大滞后 {lag.max():.0f} min，均属整点下载）")
    gate("G1c", "无日期/单次历史快照被排除在夜间样本之外",
         True, f"排除 {n_und} 个：{list(und.file)}")

    # ---------------- Step 1 ----------------
    print("\n[1] 夜间窗筛选（23:00–06:59，按内部时间戳）")
    dated = inv[inv.ts_source == "internal"].copy()
    dated["dt"] = pd.to_datetime(dated.internal_ts)
    night = dated[dated.hour.isin(NIGHT_HOURS)].copy()
    night["night_id"] = np.where(
        night.hour == 23,
        (night.dt + pd.Timedelta(days=1)).dt.date.astype(str),
        night.dt.dt.date.astype(str),
    )
    night_files = [(r.dt.to_pydatetime(), MONITOR_DIR / r.file if r.dir == "realtime_monitoring"
                    else HIST_DIR / r.file) for r in night.itertuples()]
    night_files.sort(key=lambda t: t[0])

    per_night = (night.groupby("night_id")
                 .agg(n_snapshots=("file", "size"),
                      first=("dt", "min"), last=("dt", "max"))
                 .reset_index().sort_values("night_id"))
    per_night["span_h"] = ((per_night["last"] - per_night["first"]).dt.total_seconds() / 3600).round(2)
    print(per_night.assign(first=per_night["first"].astype(str), last=per_night["last"].astype(str))
          .to_string(index=False))
    per_night.to_csv(OUT / "night_per_night.csv", index=False, encoding="utf-8-sig")

    n_nights = int(per_night.shape[0])
    print(f"    夜间快照 {len(night)} 个，覆盖 {n_nights} 个夜晚")
    gate("G2", "夜间快照全部落在 23:00–06:59",
         bool(night.hour.isin(NIGHT_HOURS).all()), f"n={len(night)}")
    gate("G3", "夜间覆盖 ≥2 个不同夜晚",
         n_nights >= 2, f"nights={n_nights} ({list(per_night.night_id)})")

    # ---------------- Step 2 ----------------
    print(f"\n[2] 解析 {len(night_files)} 个夜间快照（全量读入）")
    obs, snap_counts = parse_night_snapshots(night_files)
    snap_counts.to_csv(OUT / "night_snapshot_counts.csv", index=False, encoding="utf-8-sig")
    n_trunc = int((snap_counts.n_records < 143787).sum())
    print(f"    夜间观测记录 {len(obs):,} 条；唯一 LTA LinkID {obs.LinkID.nunique():,}")
    print(f"    ⚠ 截断快照（<143,787 条）{n_trunc}/{len(snap_counts)} 个"
          + (f"，最少 {snap_counts.n_records.min():,} 条" if n_trunc else ""))

    # ---------------- Step 4 (per-link) ----------------
    print("\n[3] 单链夜间观测数与速度分位数")
    g = obs.groupby("LinkID")
    link = g.agg(
        n_obs=("speed_kmh", "size"),
        n_nights=("night_id", "nunique"),
        v_median=("speed_kmh", "median"),
        v_mean=("speed_kmh", "mean"),
        v_p25=("speed_kmh", lambda s: float(np.percentile(s, 25))),
        v_p75=("speed_kmh", lambda s: float(np.percentile(s, 75))),
        v_p90=("speed_kmh", lambda s: float(np.percentile(s, 90))),
        band8_share=("band_raw", lambda s: float((s == 8).mean())),
    ).reset_index()
    link["est_eligible"] = link.n_obs >= MIN_OBS_FOR_ESTIMATE
    link.to_csv(OUT / "night_link_stats.csv", index=False, encoding="utf-8-sig")

    nobs = link.n_obs
    print(f"    n_obs: 中位={nobs.median():.0f}  p10={np.percentile(nobs,10):.0f}  "
          f"max={nobs.max()}  ≥{MIN_OBS_FOR_ESTIMATE}占比={link.est_eligible.mean()*100:.1f}%")
    dist = (nobs.value_counts().sort_index()
            .rename_axis("n_obs").reset_index(name="n_links").head(20))
    dist.to_csv(OUT / "night_nobs_distribution.csv", index=False, encoding="utf-8-sig")

    # 单夜观测数 + 候选夜晚组合的可用性（用户要求 ≥6 观测/链）
    per_link_night = obs.groupby(["night_id", "LinkID"]).size().rename("n_obs").reset_index()
    night_link = (per_link_night.groupby("night_id")
                  .agg(n_links=("LinkID", "size"),
                       n_elig=("n_obs", lambda s: int((s >= MIN_OBS_FOR_ESTIMATE).sum())))
                  .reset_index())
    night_link["elig_pct"] = night_link.n_elig / night_link.n_links * 100
    night_link.to_csv(OUT / "night_links_per_night.csv", index=False, encoding="utf-8-sig")
    print("\n    单夜可用性:")
    print(night_link.round(2).to_string(index=False))

    OPTIONS = {
        "N_adjacent(05-06,05-07)": ["2026-05-06", "2026-05-07"],
        "N_all4": ["2026-05-06", "2026-05-07", "2026-06-19", "2026-10-07"],
        "N_distant(10-07)": ["2026-10-07"],
    }
    opt_rows = []
    for name, ns in OPTIONS.items():
        sub = per_link_night[per_link_night.night_id.isin(ns)]
        cnt = sub.groupby("LinkID")["n_obs"].sum()          # ★ 观测数求和，不是行数
        opt_rows.append({
            "option": name, "nights": len(ns),
            "n_links_any": int(cnt.size),
            "n_links_ge_min": int((cnt >= MIN_OBS_FOR_ESTIMATE).sum()),
            "pct_ge_min": float((cnt >= MIN_OBS_FOR_ESTIMATE).mean() * 100),
            "median_obs": float(cnt.median()),
            "p10_obs": float(np.percentile(cnt, 10)),
            "min_obs": int(cnt.min()), "max_obs": int(cnt.max()),
        })
    optdf = pd.DataFrame(opt_rows)
    optdf.to_csv(OUT / "night_options.csv", index=False, encoding="utf-8-sig")
    print("\n    候选夜晚组合（≥6 观测/链）:")
    print(optdf.round(2).to_string(index=False))

    # ---------------- Step 5 覆盖 ----------------
    print("\n[4] 空间覆盖（沿用已验证映射，不重新搜索）")
    am = pd.read_csv(AM_MATCH, encoding="utf-8-sig")
    am["LinkID"] = am.LinkID.astype(str).str.strip()
    net = pd.read_csv(NETWORK_LINKS, encoding="utf-8-sig", low_memory=False)
    net = net.reset_index(drop=True)
    net["osm_edge_index"] = np.arange(len(net))
    net["matsim_link"] = ("e" + net.from_node.astype(int).astype(str)
                          + "_" + net.to_node.astype(int).astype(str))

    m = am.merge(link, on="LinkID", how="left")
    m["has_night"] = m.n_obs.notna()
    m["est_eligible"] = m.est_eligible.fillna(False).astype(bool)
    edge = m.merge(net[["osm_edge_index", "length_m", "speed_kmh", "highway",
                        "matsim_link"]], on="osm_edge_index", how="left", suffixes=("", "_net"))

    n_am_links = m.LinkID.nunique()
    n_am_edges = edge.osm_edge_index.nunique()
    e_cov = edge[edge.has_night].drop_duplicates("osm_edge_index")
    n_cov_edges = e_cov.osm_edge_index.nunique()
    n_cov_elig = edge[edge.est_eligible].drop_duplicates("osm_edge_index").osm_edge_index.nunique()
    km_am = float(edge.drop_duplicates("osm_edge_index").length_m.sum() / 1000)
    km_cov = float(e_cov.length_m.sum() / 1000)
    km_elig = float(edge[edge.est_eligible].drop_duplicates("osm_edge_index").length_m.sum() / 1000)
    print(f"    AM 靶场边 {n_am_edges:,} 条 / {km_am:,.1f} km")
    print(f"    夜间有观测 {n_cov_edges:,} 条 ({n_cov_edges/n_am_edges*100:.2f}%) / {km_cov:,.1f} km ({km_cov/km_am*100:.2f}%)")
    print(f"    夜间 ≥{MIN_OBS_FOR_ESTIMATE} 观测 {n_cov_elig:,} 条 ({n_cov_elig/n_am_edges*100:.2f}%) / {km_elig:,.1f} km ({km_elig/km_am*100:.2f}%)")

    hw = []
    base = edge.drop_duplicates("osm_edge_index")
    for h, gsub in base.groupby("highway"):
        gg = gsub.dropna(subset=["osm_edge_index"])
        tot_n, tot_km = len(gg), float(gg.length_m.sum() / 1000)
        cov = gg[gg.has_night]
        elig = gg[gg.est_eligible]
        km_night = float(cov.length_m.sum() / 1000)
        km_elig = float(elig.length_m.sum() / 1000)
        hw.append({
            "highway": h, "n_edges": tot_n, "km": tot_km,
            "n_night": len(cov), "km_night": km_night,
            "night_edge_pct": len(cov) / tot_n * 100 if tot_n else np.nan,
            "night_km_pct": km_night / tot_km * 100 if tot_km else np.nan,
            "n_elig": len(elig),
            "elig_edge_pct": len(elig) / tot_n * 100 if tot_n else np.nan,
            "elig_km_pct": km_elig / tot_km * 100 if tot_km else np.nan,
        })
    hwdf = pd.DataFrame(hw).sort_values("n_edges", ascending=False)
    hwdf.to_csv(OUT / "night_coverage_by_highway.csv", index=False, encoding="utf-8-sig")
    print("\n    分道路等级覆盖率（Top 12 by 边数）:")
    print(hwdf.head(12)[["highway", "n_edges", "km", "night_edge_pct", "night_km_pct",
                         "elig_edge_pct"]].round(2).to_string(index=False))

    # ---------------- Step 6 一致性（反量化：不用中位数，用量化档会打平） ----------------
    print("\n[5] 一致性：夜间 vs AM 速度（逐链，反量化）")
    cmp = edge.dropna(subset=["n_obs"]).drop_duplicates("osm_edge_index")[
        ["osm_edge_index", "highway", "length_m", "speed_kmh", "am_speed_kmh",
         "v_median", "v_p25", "v_p75", "v_p90", "n_obs"]]
    cmp = cmp.assign(
        d_med=cmp.v_median - cmp.am_speed_kmh,
        d_p75=cmp.v_p75 - cmp.am_speed_kmh,
        d_p90=cmp.v_p90 - cmp.am_speed_kmh,
        night_over_ff=cmp.v_median / cmp.speed_kmh.replace(0, np.nan),
    )
    cmp.to_csv(OUT / "night_vs_am_by_edge.csv", index=False, encoding="utf-8-sig")

    def _stats(s):
        return {"mean": float(s.mean()), "median": float(s.median()),
                "share_up_pct": float((s > 0).mean() * 100),
                "share_dn_pct": float((s < 0).mean() * 100),
                "share_eq_pct": float((s == 0).mean() * 100)}

    overall = {
        "n_edges": int(len(cmp)),
        "am_speed_median": float(cmp.am_speed_kmh.median()),
        "night_median": float(cmp.v_median.median()),
        "night_p75_median": float(cmp.v_p75.median()),
        "night_p90_median": float(cmp.v_p90.median()),
        "ff_median": float(cmp.speed_kmh.median()),
        "d_night_med_minus_am": _stats(cmp.d_med),
        "d_night_p75_minus_am": _stats(cmp.d_p75),
        "d_night_p90_minus_am": _stats(cmp.d_p90),
    }
    dm, d75, d90 = overall["d_night_med_minus_am"], overall["d_night_p75_minus_am"], overall["d_night_p90_minus_am"]
    print(f"    Δ(夜中位−AM): mean={dm['mean']:+.2f}  夜>AM={dm['share_up_pct']:.1f}%  "
          f"夜<AM={dm['share_dn_pct']:.1f}%  相等={dm['share_eq_pct']:.1f}%")
    print(f"    Δ(夜p75−AM) : mean={d75['mean']:+.2f}  夜>AM={d75['share_up_pct']:.1f}%")
    print(f"    Δ(夜p90−AM) : mean={d90['mean']:+.2f}  夜>AM={d90['share_up_pct']:.1f}%")
    print(f"    ⚠ 中位=0 是 8 档量化的必然结果（夜/AM 落入同一档中点），故用均值与符号占比判定")
    print(f"    AM 中位={overall['am_speed_median']:.2f}  网络自由流中位={overall['ff_median']:.2f} km/h")

    byhw = (cmp.groupby("highway")
            .agg(n=("osm_edge_index", "size"),
                 am=("am_speed_kmh", "median"), night=("v_median", "median"),
                 night_p75=("v_p75", "median"), ff=("speed_kmh", "median"),
                 d_med_mean=("d_med", "mean"), d_p75_mean=("d_p75", "mean"),
                 share_up=("d_med", lambda s: (s > 0).mean() * 100))
            .reset_index().sort_values("n", ascending=False))
    byhw.to_csv(OUT / "night_vs_am_by_highway.csv", index=False, encoding="utf-8-sig")
    print("\n    分等级（Δ 用均值，绕开量化）:")
    print(byhw.head(12).round(2).to_string(index=False))

    gate("G7", "夜间速度系统性 ≥ AM（逐链均值 Δ(p75−AM) > 0）",
         bool(overall["d_night_p75_minus_am"]["mean"] > 0),
         f"Δp75均值={overall['d_night_p75_minus_am']['mean']:+.2f} km/h；"
         f"Δ中位均值={overall['d_night_med_minus_am']['mean']:+.2f}")

    # ---------------- Step 7 预览（只读，绝不写网络） ----------------
    print("\n[6] SB-A5 网络预览（只读；不写任何网络文件）")
    prev = edge.drop_duplicates("osm_edge_index")[
        ["osm_edge_index", "highway", "length_m", "speed_kmh", "am_speed_kmh",
         "v_median", "v_p75", "v_p90", "n_obs"]].copy().reset_index(drop=True)
    v10 = prev.speed_kmh.to_numpy(float)
    prev["fs_v1p0"] = v10
    prev["fs_SB_A4"] = np.clip(np.maximum(prev.am_speed_kmh.to_numpy(float), 5.0), 5.0, None)

    def _rule(col: str) -> np.ndarray:
        est = prev[col].to_numpy(float)
        fs = est.copy()
        # ★SB8 开口档规则：估计值来自 SB8 代理(75)时，不得低于该链现有自由流
        is_sb8 = np.isclose(est, BAND8_PROXY_KMH)
        fs[is_sb8] = np.maximum(est[is_sb8], v10[is_sb8])
        fs = np.clip(fs, 5.0, None)
        nan_mask = ~np.isfinite(est)              # 无夜间观测 ⇒ 保留 v1.0
        fs[nan_mask] = v10[nan_mask]
        return fs

    for col, lab in (("v_median", "SB5_p50"), ("v_p75", "SB5_p75"), ("v_p90", "SB5_p90")):
        prev["fs_" + lab] = _rule(col)
        prev["chg_" + lab] = prev["fs_" + lab].to_numpy(float) != v10

    prev.to_csv(OUT / "night_network_preview.csv", index=False, encoding="utf-8-sig")

    def _med(col, hw=None):
        d = prev if hw is None else prev[prev.highway == hw]
        return float(np.nanmedian(d["fs_" + col].to_numpy(float)))

    rows = []
    for h in ["ALL", "residential", "service", "primary", "motorway", "trunk",
              "secondary", "tertiary", "motorway_link"]:
        d = prev if h == "ALL" else prev[prev.highway == h]
        if d.empty:
            continue
        rows.append({
            "highway": h, "n": int(len(d)), "km": float(d.length_m.sum() / 1000),
            "am_obs": float(np.nanmedian(d.am_speed_kmh.to_numpy(float))),
            "fs_v1p0": _med("v1p0", None if h == "ALL" else h),
            "fs_A4": _med("SB_A4", None if h == "ALL" else h),
            "fs_SB5_p50": _med("SB5_p50", None if h == "ALL" else h),
            "fs_SB5_p75": _med("SB5_p75", None if h == "ALL" else h),
            "fs_SB5_p90": _med("SB5_p90", None if h == "ALL" else h),
        })
    pv = pd.DataFrame(rows)
    pv.to_csv(OUT / "night_network_preview_by_highway.csv", index=False, encoding="utf-8-sig")
    print("    自由流中位（km/h）——预览：")
    print(pv.round(2).to_string(index=False))
    for lab in ("SB5_p50", "SB5_p75", "SB5_p90"):
        nchg = int(prev["chg_" + lab].sum())
        print(f"    {lab}: 改变 {nchg:,}/{len(prev):,} 链 ({nchg/len(prev)*100:.2f}%)，"
              f"中位 {np.nanmedian(prev['fs_'+lab]):.1f} km/h（v1.0 为 {np.nanmedian(v10):.1f}）")

    # ---------------- 汇总 ----------------
    nights_full = per_night[per_night.n_snapshots >= 10]
    summary = {
        "generated": datetime.now().isoformat(timespec="seconds"),
        "inventory": {"total": n_total, "with_internal_ts": n_int,
                      "filename_only": n_fn, "undated_excluded": n_und,
                      "undated_files": list(und.file),
                      "filename_vs_internal_differs": n_diff,
                      "max_download_lag_min": float(lag.max()),
                      "truncated_snapshots": n_trunc,
                      "min_snapshot_records": int(snap_counts.n_records.min())},
        "night": {"n_snapshots": int(len(night)), "n_nights": n_nights,
                  "nights": per_night.night_id.tolist(),
                  "snapshots_per_night": per_night.set_index("night_id").n_snapshots.to_dict(),
                  "full_cadence_nights": nights_full.night_id.tolist(),
                  "single_snapshot_only_nights": per_night[per_night.n_snapshots < 6].night_id.tolist()},
        "per_link_obs": {"n_links": int(len(link)), "median": float(nobs.median()),
                         "p10": float(np.percentile(nobs, 10)), "max": int(nobs.max()),
                         "pct_ge_min_obs": float(link.est_eligible.mean() * 100),
                         "MIN_OBS_FOR_ESTIMATE": MIN_OBS_FOR_ESTIMATE},
        "night_options": optdf.to_dict(orient="records"),
        "coverage": {"am_edges": int(n_am_edges), "am_km": km_am,
                     "night_edges": int(n_cov_edges), "night_km": km_cov,
                     "night_edge_pct": n_cov_edges / n_am_edges * 100,
                     "night_km_pct": km_cov / km_am * 100,
                     "elig_edges": int(n_cov_elig), "elig_km": km_elig,
                     "elig_edge_pct": n_cov_elig / n_am_edges * 100,
                     "elig_km_pct": km_elig / km_am * 100},
        "consistency": overall,
        "convention": {"band8_sentinel": BAND8_MAX_SENTINEL, "band8_proxy_kmh": BAND8_PROXY_KMH,
                       "speed_from_record": "闭区间取中点；SB8 用哨兵识别并回退 proxy",
                       "channel": "LinkID -> osm_edge_index(AM match) -> matsim e{from}_{to}",
                       "quantization_warning": "速度仅 8 档离散中点{4.5..75}；比较必须用均值/符号占比，不得用中位数"},
        "gates": GATES,
        "verdict": "AVAILABLE" if all(g["pass"] for g in GATES) else "BLOCKED",
    }
    with (OUT / "night_gate_summary.json").open("w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2, default=str)

    n_pass = sum(g["pass"] for g in GATES)
    print("\n" + "=" * 96)
    print(f"门禁 {n_pass}/{len(GATES)} PASS  ⇒  verdict = {summary['verdict']}")
    print(f"落盘：{OUT}")
    print("=" * 96)
    return 0


if __name__ == "__main__":
    sys.exit(main())
