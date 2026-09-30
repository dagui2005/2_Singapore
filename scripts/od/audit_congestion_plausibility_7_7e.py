# -*- coding: utf-8 -*-
"""
Step 7.7E  Congestion-State Plausibility Audit  (v2 —— 含量化审计)
=================================================================

起因（用户 2026-09-19/20 追问）：
    「为什么我用 VIA 看仿真结果，新加坡全市早高峰一点儿都不拥堵？」

7.8 已冻结（Singapore_OD_MATSim_Final_v1.0）。本步是**只读的事后合理性审计**：
    ⛔ 不重开 v1.0、不改任何冻结输入/参数/产物、不跑 MATSim。
    ✅ 只读 matsim_viz_7_8/outputs/W01_events/（7.8-VIZ-RUN 输出层重执行，已判 BITEXACT）
       + reports/matsim_network/network_links_source_copy.csv（源路网副本，带 OSM highway/name）
    产物全部落新目录 reports/congestion_plausibility_audit_7_7e/。

四个子问题（用户指定）：
    E1 容量到底怎么来的（capacity = lanes x capacityPerLane？是否异常偏高）
    E2 主要走廊（PIE/AYE/CTE/ECP/TPE/SLE/BKE/KPE/KJE/MCE）到底有多拥堵
    E2b ★量化审计：1 秒 qsim 时间步对 TRAVELTIME 口径的污染有多严重
    E3 拥堵是否形成连续空间结构（连通链长度 + 随机置换零假设）
    E4 07:00-09:00 峰值演化（15 分钟）：在途量 / V/C / 拥堵里程 / 延误

★ 两条必须记录的口径纠正
------------------------------------------------------------------
(1) linkstats 的 v/c = HRS8-9avg / CAPACITY **恒 <= 1**，这是 MATSim 的结构性质
    （链路流出被容量截断，需求超额时表现为上游排队，而非该链路 v/c > 1）。
    ⇒ v/c = 1.000000 的含义是「**已饱和 + 有排队**」，**不是**「容量富余」。

(2) ★★ `qsim.timeStepSize = 1 s`。全网络链路自由流时间中位数 < 1 s、均值约 3 s，
    而 1 s 步长下链路行程时间被**向上取整到整秒**：TT_recorded = ceil(FF)。
    于是「拥堵倍率 TT/FF」在无任何延误时也等于 ceil(FF)/FF >> 1。
    ⇒ 本项目沿用的「拥堵倍率 = TRAVELTIME8-9avg / (LENGTH/FREESPEED)」
      **是一个被量化污染的口径**；必须扣除 ceil(FF) 才得到真实延误。
    证据：全网 12-13 时（几乎空网）倍率仍有 1.552，而量化基准为 1.596。

运行：零仿真。首次 events 流式扫描 ~19 min；若产物已存在则自动读缓存（<2 min）。
设 AUDIT_7_7E_FORCE_EVENTS=1 可强制重扫。
"""

from __future__ import annotations

import gzip
import io
import json
import math
import os
import time
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd

import matplotlib
matplotlib.use("Agg")
import matplotlib.font_manager as fm  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402

try:
    fm.fontManager.addfont(r"C:\Windows\Fonts\msyh.ttc")
    matplotlib.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "DejaVu Sans"]
except Exception:
    pass
matplotlib.rcParams["axes.unicode_minus"] = False

ROOT = Path(r"D:\Luan\2026-05\2_Singapore")
VIZ = ROOT / "matsim_viz_7_8" / "outputs" / "W01_events"
NET_CSV = VIZ / "W01_events.output_links.csv.gz"
SRC_CSV = ROOT / "reports" / "matsim_network" / "network_links_source_copy.csv"
LS_GZ = VIZ / "ITERS" / "it.19" / "W01_events.19.linkstats.txt.gz"
LEG_TXT = VIZ / "ITERS" / "it.19" / "W01_events.19.legHistogram.txt"
EVENTS_GZ = VIZ / "W01_events.output_events.xml.gz"
CFG_XML = ROOT / "matsim_viz_7_8" / "configs" / "config_W01_events.xml"

OUT = ROOT / "reports" / "congestion_plausibility_audit_7_7e"
OUT.mkdir(parents=True, exist_ok=True)

FORCE_EVENTS = os.environ.get("AUDIT_7_7E_FORCE_EVENTS", "0") == "1"

CORRIDORS = {
    "PIE": ["Pan-Island Expressway", "Pan Island Expressway"],
    "AYE": ["Ayer Rajah Expressway"],
    "CTE": ["Central Expressway"],
    "ECP": ["East Coast Parkway"],
    "TPE": ["Tampines Expressway"],
    "SLE": ["Seletar Expressway"],
    "BKE": ["Bukit Timah Expressway"],
    "KPE": ["Kallang-Paya Lebar Expressway", "Kallang Paya Lebar Expressway"],
    "KJE": ["Kranji Expressway"],
    "MCE": ["Marina Coastal Expressway", "Marina Costal Expressway"],
}
NAME2CORR = {n: c for c, names in CORRIDORS.items() for n in names}

BENCH = {
    "motorway": (1800, 2400), "motorway_link": (1200, 2000),
    "trunk": (1500, 2200), "trunk_link": (1200, 2000),
    "primary": (700, 1200), "primary_link": (600, 1200),
    "secondary": (500, 1000), "secondary_link": (500, 1000),
    "tertiary": (400, 900), "tertiary_link": (400, 900),
    "unclassified": (300, 800), "residential": (200, 600),
    "service": (100, 500),
}
EXPRESS_CLASSES = {"motorway", "motorway_link", "trunk", "trunk_link"}
ARTERIAL_CLASSES = {"primary", "primary_link", "secondary", "secondary_link", "tertiary", "tertiary_link"}
LOCAL_CLASSES = {"residential", "unclassified", "service"}

Q_TOL = 0.02

GATES: list[tuple[str, bool, str]] = []
MDL: list[str] = []


def G(name: str, ok: bool, note: str = "") -> None:
    GATES.append((name, bool(ok), note))
    print("  [%s] %-52s %s" % ("PASS" if ok else "FAIL", name, note))


def A(*a) -> None:
    print(*a)


def MD(s: str) -> None:
    MDL.append(s)


def attr(line: str, key: str) -> str | None:
    i = line.find(' ' + key + '="')
    if i < 0:
        return None
    j = line.find('"', i + len(key) + 3)
    return None if j < 0 else line[i + len(key) + 3:j]


# ============================================================================
def load() -> dict:
    A("=" * 80)
    A("STEP 7.7E  CONGESTION-STATE PLAUSIBILITY AUDIT  (read-only, v2 with quantization audit)")
    A("=" * 80)
    t0 = time.time()
    net = pd.read_csv(NET_CSV, sep=";").rename(columns={"lanes": "net_lanes"})
    src = pd.read_csv(SRC_CSV)
    src["link"] = "e" + src.from_node.astype(str) + "_" + src.to_node.astype(str)
    src = src.rename(columns={"lanes": "src_lanes", "speed_kmh": "src_speed_kmh",
                              "highway": "road_type", "name": "road_name"})
    ls = pd.read_csv(LS_GZ, sep="\t", low_memory=False).rename(columns={"LINK": "link"})
    A("  network links=%d  source rows=%d  linkstats rows=%d  (%.1f s)"
      % (len(net), len(src), len(ls), time.time() - t0))

    m = net.merge(src[["link", "road_type", "road_name", "src_lanes", "src_speed_kmh"]],
                  on="link", how="left")
    G("E0.1 源副本覆盖全部链路", int(m.road_type.isna().sum()) == 0,
      "missing=%d" % int(m.road_type.isna().sum()))
    m = m.merge(ls[["link", "LENGTH", "FREESPEED", "CAPACITY",
                    "HRS7-8avg", "HRS8-9avg", "HRS9-10avg", "HRS10-11avg", "HRS11-12avg",
                    "HRS12-13avg",
                    "TRAVELTIME7-8avg", "TRAVELTIME8-9avg", "TRAVELTIME9-10avg",
                    "TRAVELTIME10-11avg", "TRAVELTIME11-12avg", "TRAVELTIME12-13avg"]],
                on="link", how="left")
    G("E0.2 linkstats 覆盖全部链路", int(m.LENGTH.notna().sum()) == len(m),
      "matched=%d" % int(m.LENGTH.notna().sum()))
    d = max(float(np.abs(m.length - m.LENGTH).max()), float(np.abs(m.freespeed - m.FREESPEED).max()),
            float(np.abs(m.capacity - m.CAPACITY).max()))
    G("E0.3 network vs linkstats 三字段逐位一致", d < 1e-9, "max|d|=%.3g" % d)

    m["ff_s"] = m.LENGTH / m.FREESPEED
    m["ff_ceil_s"] = np.ceil(m.ff_s - 1e-9)
    m["corridor"] = m.road_name.map(NAME2CORR)
    m["q_ratio"] = np.where(m.ff_s > 0, m.ff_ceil_s / m.ff_s, np.nan)
    return {"net": net, "src": src, "ls": ls, "m": m}


# ============================================================================
def e1(m: pd.DataFrame) -> dict:
    A("")
    A("=" * 80)
    A("E1  容量来源审计")
    A("=" * 80)
    m = m.copy()
    m["cpl"] = m.CAPACITY / m.net_lanes
    g = m.groupby("road_type")["cpl"].agg(["nunique"])
    G("E1.1 capacity/lane 是 road_type 的确定性函数", int((g["nunique"] > 1).sum()) == 0,
      "非唯一类别=%d" % int((g["nunique"] > 1).sum()))

    ok = m.src_lanes.notna()
    mm = int((~np.isclose(m.loc[ok, "net_lanes"], m.loc[ok, "src_lanes"], atol=1e-6)).sum())
    G("E1.2 车道数=源副本（仅比较非缺失 %d 条）" % int(ok.sum()), mm == 0,
      "不一致=%d；源副本 lanes 缺失=%d（不参与比较）" % (mm, int((~ok).sum())))

    fs = m.FREESPEED.to_numpy(float) * 3.6
    fm = int((~np.isclose(fs, m.src_speed_kmh.fillna(-1).to_numpy(float), atol=1e-3)).sum())
    G("E1.3 freespeed = 源副本限速（逐位）", fm == 0, "不一致=%d" % fm)

    rows = []
    for rt, sub in m.groupby("road_type"):
        cpl = float(sub.cpl.median())
        lo, hi = BENCH.get(rt, (np.nan, np.nan))
        rows.append(dict(road_type=rt, n_links=len(sub), link_pct=100 * len(sub) / len(m),
                         lanes_med=float(sub.net_lanes.median()), capacity_per_lane=cpl,
                         cap_med=float(sub.CAPACITY.median()),
                         freespeed_kmh=float(sub.FREESPEED.median() * 3.6),
                         length_med_m=float(sub.LENGTH.median()),
                         ff_med_s=float(sub.ff_s.median()),
                         total_length_km=float(sub.LENGTH.sum() / 1000),
                         supply_veh_km_h=float((sub.CAPACITY * sub.LENGTH).sum() / 1000),
                         bench_lo=lo, bench_hi=hi,
                         vs_bench=("in-band" if (not math.isnan(lo) and lo <= cpl <= hi)
                                   else ("ABOVE" if (not math.isnan(hi) and cpl > hi) else "other"))))
    tab = pd.DataFrame(rows).sort_values("n_links", ascending=False)
    tab.to_csv(OUT / "e1_capacity_provenance_by_roadtype.csv", index=False, encoding="utf-8-sig")

    A("")
    A("  %-16s %8s %8s %7s %7s %7s %7s %8s  %s" %
      ("road_type", "n", "link%", "lanes", "C_pl", "km/h", "len_m", "ff_s", "vs 参考带"))
    for _, r in tab.iterrows():
        A("  %-16s %8d %7.2f%% %7.1f %7.0f %7.1f %7.1f %8.2f  %s" %
          (r.road_type, r.n_links, r.link_pct, r.lanes_med, r.capacity_per_lane,
           r.freespeed_kmh, r.length_med_m, r.ff_med_s, r.vs_bench))

    above = tab[tab.vs_bench == "ABOVE"]
    G("E1.4 报告容量高于参考带的类别", True,
      "高出 = %s" % ", ".join("%s %.0f>%.0f" % (r.road_type, r.capacity_per_lane, r.bench_hi)
                              for _, r in above.iterrows()))

    slow = m[m.FREESPEED < 2.0]
    anom = [dict(kind="cpl_out_of_range", n=int(((m.cpl < 200) | (m.cpl > 2600)).sum())),
            dict(kind="freespeed_above_45ms", n=int((m.FREESPEED > 45).sum())),
            dict(kind="freespeed_below_2ms_legit_slow", n=len(slow),
                 note="全部为 5 km/h = 1.389 m/s 的 service/装卸道，属合法极低速"),
            dict(kind="lanes_out_of_range", n=int(((m.net_lanes < 0.5) | (m.net_lanes > 10)).sum()))]
    pd.DataFrame(anom).to_csv(OUT / "e1_capacity_anomalies.csv", index=False, encoding="utf-8-sig")
    G("E1.5 无逻辑异常（超高速/车道数越界）",
      int((m.FREESPEED > 45).sum()) == 0 and int(((m.net_lanes < 0.5) | (m.net_lanes > 10)).sum()) == 0,
      "freespeed>45 m/s = %d; <2 m/s = %d（合法低速，非异常）"
      % (int((m.FREESPEED > 45).sum()), len(slow)))

    def util(df):
        cap = float((df.CAPACITY * df.LENGTH).sum() / 1000)
        dem = float(df["HRS8-9avg"].fillna(0).mul(df.LENGTH).sum() / 1000)
        return dict(n=len(df), cap_veh_km_h=cap, dem_veh_km_h=dem,
                    util_pct=100 * dem / cap if cap else float("nan"))

    sup = {"ALL_LINKS": util(m), "LOADED_LINKS": util(m[m["HRS8-9avg"].fillna(0) > 0]),
           "EXPRESSWAY_CLASSES": util(m[m.road_type.isin(EXPRESS_CLASSES)]),
           "EXPRESSWAY_CORRIDORS": util(m[m.corridor.notna()]),
           "ARTERIAL_CLASSES": util(m[m.road_type.isin(ARTERIAL_CLASSES)]),
           "LOCAL_CLASSES": util(m[m.road_type.isin(LOCAL_CLASSES)])}
    pd.DataFrame(sup).T.to_csv(OUT / "e1_network_supply_vs_demand.csv", encoding="utf-8-sig")
    A("")
    A("  %-24s %16s %16s %9s" % ("scope", "supply veh-km/h", "demand veh-km/h", "util%"))
    for k, v in sup.items():
        A("  %-24s %16.0f %16.0f %8.2f%%" % (k, v["cap_veh_km_h"], v["dem_veh_km_h"], v["util_pct"]))
    G("E1.6 已载流链路容量利用率 < 100%", sup["LOADED_LINKS"]["util_pct"] < 100,
      "LOADED=%.1f%%  EXPRESSWAY=%.1f%%" % (sup["LOADED_LINKS"]["util_pct"],
                                            sup["EXPRESSWAY_CORRIDORS"]["util_pct"]))
    return dict(tab=tab, sup=sup, above=above, anom=anom)


# ============================================================================
def _agg(df: pd.DataFrame, key_col: str) -> pd.DataFrame:
    out = []
    for k, s in df.groupby(key_col):
        v = s["HRS8-9avg"].fillna(0).to_numpy(float)
        tt = s["TRAVELTIME8-9avg"].to_numpy(float)
        L = s.LENGTH.to_numpy(float)
        ff = s.ff_s.to_numpy(float)
        fc = s.ff_ceil_s.to_numpy(float)
        cap = s.CAPACITY.to_numpy(float)
        r = tt / ff
        has = (v > 0) & np.isfinite(r)
        vc = np.divide(v, cap, out=np.zeros_like(v), where=cap > 0)
        out.append(dict(
            key=k, n_links=len(s), length_km=float(L.sum() / 1000), vol_veh=float(v.sum()),
            ff_mean_s=float(ff[has].mean()) if has.any() else np.nan,
            ratio_vw=float((v[has] * r[has]).sum() / v[has].sum()) if has.any() else np.nan,
            qratio_vw=float((v[has] * (fc[has] / ff[has])).sum() / v[has].sum()) if has.any() else np.nan,
            excess_vw=float((v[has] * (r[has] - fc[has] / ff[has])).sum() / v[has].sum()) if has.any() else np.nan,
            speed_kmh=float((v[has] * L[has]).sum() / (v[has] * tt[has]).sum() * 3.6) if has.any() else np.nan,
            vc_agg=float(v.sum() / cap.sum()) if cap.sum() else np.nan,
            vc_vw=float((v[has] * vc[has]).sum() / v[has].sum()) if has.any() else np.nan,
            sat_links=int((v >= cap * 0.9999).sum()),
            delay_raw_h=float((v[has] * np.clip(tt[has] - ff[has], 0, None)).sum() / 3600) if has.any() else np.nan,
            delay_corr_h=float((v[has] * np.clip(tt[has] - fc[has], 0, None)).sum() / 3600) if has.any() else np.nan))
    return pd.DataFrame(out).sort_values("vol_veh", ascending=False)


def e2(m: pd.DataFrame) -> dict:
    A("")
    A("=" * 80)
    A("E2  主要走廊拥堵（原始口径）+ 饱和链路")
    A("=" * 80)
    m = m.copy()
    m["ratio"] = m["TRAVELTIME8-9avg"] / m.ff_s
    m["vc"] = m["HRS8-9avg"].fillna(0) / m.CAPACITY

    cor = _agg(m[m.corridor.notna()].rename(columns={"corridor": "k"}), "k")
    cor.to_csv(OUT / "e2_corridor_congestion_0809.csv", index=False, encoding="utf-8-sig")
    cls = _agg(m, "road_type").rename(columns={"key": "road_type"})
    cls.to_csv(OUT / "e2_roadclass_congestion_0809.csv", index=False, encoding="utf-8-sig")

    A("")
    A("  --- 快速路走廊（OSM name 聚合，08-09）---")
    A("  %-5s %6s %7s %9s %8s %8s %9s %8s %6s %10s %10s" %
      ("corr", "links", "km", "vol", "TT/FF", "q基准", "超额", "km/h", "sat", "原始延误h", "扣量化h"))
    for _, r in cor.iterrows():
        A("  %-5s %6d %7.1f %9.0f %8.3f %8.3f %+9.3f %8.1f %6d %10.0f %10.0f" %
          (r.key, r.n_links, r.length_km, r.vol_veh, r.ratio_vw, r.qratio_vw, r.excess_vw,
           r.speed_kmh, r.sat_links, r.delay_raw_h, r.delay_corr_h))

    A("")
    A("  --- 道路等级（08-09）---")
    A("  %-16s %8s %9s %12s %8s %8s %9s %7s %6s" %
      ("road_type", "links", "km", "vol", "TT/FF", "q基准", "超额", "km/h", "sat"))
    for _, r in cls.iterrows():
        A("  %-16s %8d %9.1f %12.0f %8.3f %8.3f %+9.3f %7.1f %6d" %
          (r.road_type, r.n_links, r.length_km, r.vol_veh, r.ratio_vw, r.qratio_vw,
           r.excess_vw, r.speed_kmh, r.sat_links))

    sat = m[m["HRS8-9avg"].fillna(0) >= m.CAPACITY * 0.9999].copy()
    sat = sat[["link", "from_node", "to_node", "road_name", "road_type", "LENGTH", "FREESPEED",
               "CAPACITY", "HRS8-9avg", "TRAVELTIME8-9avg", "ratio", "vc"]].rename(
        columns={"LENGTH": "length_m", "FREESPEED": "freespeed_mps", "CAPACITY": "capacity_veh_h",
                 "HRS8-9avg": "vol_0809", "TRAVELTIME8-9avg": "tt_0809_s"})
    sat.sort_values("vol_0809", ascending=False).to_csv(
        OUT / "e2_saturated_links_0809.csv", index=False, encoding="utf-8-sig")
    names = sat.road_name.fillna("(none)").value_counts()
    G("E2.1 饱和链路（v/c=1，正在排队）已识别", len(sat) > 0,
      "n=%d 总长=%.2f km 路名=%s" % (len(sat), float(sat.length_m.sum() / 1000),
                                     "; ".join("%s x%d" % (a, b) for a, b in names.head(3).items())))
    G("E2.2 走廊原始口径存在 TT/FF>1.2 的走廊", bool((cor.ratio_vw > 1.2).any()),
      "最差 = %s %.3f" % (cor.sort_values("ratio_vw", ascending=False).key.iloc[0],
                          float(cor.ratio_vw.max())))
    return dict(cor=cor, cls=cls, sat=sat, m=m)


# ============================================================================
def e2b(m: pd.DataFrame) -> dict:
    A("")
    A("=" * 80)
    A("E2b ★量化审计：1 秒 qsim 时间步对「拥堵倍率」口径的污染")
    A("=" * 80)
    ts = "?"
    try:
        for ln in open(CFG_XML, encoding="utf-8", errors="replace"):
            if "timeStepSize" in ln:
                ts = ln.split('value="')[1].split('"')[0]
                break
    except Exception:
        pass
    A("  配置 qsim.timeStepSize = %s" % ts)
    G("E2b.1 时间步 = 1 秒（量化前提成立）", ts.strip() in ("00:00:01", "1", "1.0"), "= %s" % ts)

    m = m.copy()
    rows = []
    for h in ["7-8", "8-9", "9-10", "10-11", "11-12", "12-13"]:
        v = m["HRS%savg" % h].fillna(0).to_numpy(float)
        tt = m["TRAVELTIME%savg" % h].to_numpy(float)
        ff = m.ff_s.to_numpy(float)
        q = m.ff_ceil_s.to_numpy(float) / ff
        k = (v > 0) & np.isfinite(tt) & (ff > 0)
        if not k.any():
            continue
        r = tt[k] / ff[k]
        rows.append(dict(hour=h, n_links=int(k.sum()), vol=float(v[k].sum()),
                         ratio_vw=float((v[k] * r).sum() / v[k].sum()),
                         qratio_vw=float((v[k] * q[k]).sum() / v[k].sum()),
                         excess_vw=float((v[k] * (r - q[k])).sum() / v[k].sum()),
                         delay_raw_h=float((v[k] * np.clip(tt[k] - ff[k], 0, None)).sum() / 3600),
                         delay_corr_h=float((v[k] * np.clip(tt[k] - q[k] * ff[k], 0, None)).sum() / 3600)))
    hr = pd.DataFrame(rows)
    hr.to_csv(OUT / "e2b_hour_control.csv", index=False, encoding="utf-8-sig")
    A("")
    A("  --- ★跨时段对照：若低流量时段倍率同样高，则该口径测的是量化不是拥堵 ---")
    A("  %-7s %9s %13s %9s %9s %9s %11s %11s" %
      ("hour", "links", "vol", "TT/FF", "ceil基准", "真实超额", "原始延误h", "扣量化h"))
    for _, r in hr.iterrows():
        A("  %-7s %9d %13.0f %9.3f %9.3f %+9.3f %11.0f %11.0f" %
          (r.hour, r.n_links, r.vol, r.ratio_vw, r.qratio_vw, r.excess_vw,
           r.delay_raw_h, r.delay_corr_h))

    v = m["HRS8-9avg"].fillna(0).to_numpy(float)
    tt = m["TRAVELTIME8-9avg"].to_numpy(float)
    ff = m.ff_s.to_numpy(float)
    q = m.ff_ceil_s.to_numpy(float) / ff
    k = (v > 0) & np.isfinite(tt) & (ff > 0)
    r = tt[k] / ff[k]
    dev = np.abs(r - q[k])
    pure = dev < Q_TOL
    G("E2b.2 多数载流链路与量化基准吻合", bool(pure.mean() > 0.5),
      "links=%.2f%% vol-w=%.2f%% (|Δ|<%.2f)" % (100 * pure.mean(),
                                                 100 * v[k][pure].sum() / v[k].sum(), Q_TOL))

    bk = pd.cut(m.LENGTH[k], [0, 20, 50, 100, 200, 500, 1e9],
                labels=["0-20", "20-50", "50-100", "100-200", "200-500", ">500"])
    dd = pd.DataFrame({"b": bk, "v": v[k], "r": r, "q": q[k], "ff": ff[k]})
    gb = dd.groupby("b", observed=True).apply(lambda s: pd.Series({
        "links": len(s), "vol_pct": 100 * s.v.sum() / v[k].sum(),
        "ff_mean_s": s.ff.mean(), "ratio_vw": (s.v * s.r).sum() / s.v.sum(),
        "qratio_vw": (s.v * s.q).sum() / s.v.sum(),
        "excess_vw": (s.v * (s.r - s.q)).sum() / s.v.sum()}), include_groups=False)
    gb.to_csv(OUT / "e2b_length_bucket.csv", encoding="utf-8-sig")
    A("")
    A("  --- 按链路长度分桶（08-09）---")
    A("  %-9s %9s %8s %10s %9s %9s %10s" %
      ("bin", "links", "vol%", "ff_mean_s", "TT/FF", "ceil基准", "真实超额"))
    for idx, r2 in gb.iterrows():
        A("  %-9s %9d %7.2f%% %10.3f %9.3f %9.3f %+10.3f" %
          (idx, r2.links, r2.vol_pct, r2.ff_mean_s, r2.ratio_vw, r2.qratio_vw, r2.excess_vw))

    A("")
    A("  --- 走廊级：原始倍率 vs 量化基准 vs 真实超额（08-09）---")
    A("  %-5s %7s %10s %10s %10s %12s" % ("corr", "km", "TT/FF", "ceil基准", "真实超额", "扣量化延误h"))
    cr = []
    for c, s in m[m.corridor.notna()].groupby("corridor"):
        vv = s["HRS8-9avg"].fillna(0).to_numpy(float)
        tt2 = s["TRAVELTIME8-9avg"].to_numpy(float)
        ff2 = s.ff_s.to_numpy(float)
        q2 = s.ff_ceil_s.to_numpy(float) / ff2
        kk = (vv > 0) & np.isfinite(tt2) & (ff2 > 0)
        rr = tt2[kk] / ff2[kk]
        row = dict(corridor=c, length_km=float(s.LENGTH.sum() / 1000),
                   ratio_vw=float((vv[kk] * rr).sum() / vv[kk].sum()),
                   qratio_vw=float((vv[kk] * q2[kk]).sum() / vv[kk].sum()),
                   excess_vw=float((vv[kk] * (rr - q2[kk])).sum() / vv[kk].sum()),
                   delay_corr_h=float((vv[kk] * np.clip(tt2[kk] - q2[kk] * ff2[kk], 0, None)).sum() / 3600))
        cr.append(row)
        A("  %-5s %7.1f %10.3f %10.3f %+10.3f %12.0f" %
          (c, row["length_km"], row["ratio_vw"], row["qratio_vw"], row["excess_vw"], row["delay_corr_h"]))
    crdf = pd.DataFrame(cr)
    crdf.to_csv(OUT / "e2b_corridor_quantization.csv", index=False, encoding="utf-8-sig")

    A("")
    A("  --- ★按道路类型分解「真实延误」（08-09，全网络）---")
    A("  %-16s %8s %9s %11s %11s %10s %13s %8s" %
      ("road_type", "links", "loaded", "TT/FF", "ceil基准", "真实超额", "扣量化延误h", "占比%"))
    rt = []
    for c, s_rt in m.groupby("road_type"):
        vv = s_rt["HRS8-9avg"].fillna(0).to_numpy(float)
        tt3 = s_rt["TRAVELTIME8-9avg"].to_numpy(float)
        ff3 = s_rt.ff_s.to_numpy(float)
        q3 = s_rt.ff_ceil_s.to_numpy(float) / ff3
        kk = (vv > 0) & np.isfinite(tt3) & (ff3 > 0)
        if not kk.any():
            continue
        rr = tt3[kk] / ff3[kk]
        rt.append(dict(road_type=str(c), n_links=int(s_rt.shape[0]), n_loaded=int(kk.sum()),
                       length_km=float(s_rt.LENGTH.sum() / 1000), vol=float(vv[kk].sum()),
                       ratio_vw=float((vv[kk] * rr).sum() / vv[kk].sum()),
                       qratio_vw=float((vv[kk] * q3[kk]).sum() / vv[kk].sum()),
                       excess_vw=float((vv[kk] * (rr - q3[kk])).sum() / vv[kk].sum()),
                       delay_raw_h=float((vv[kk] * np.clip(tt3[kk] - ff3[kk], 0, None)).sum() / 3600),
                       delay_corr_h=float((vv[kk] * np.clip(tt3[kk] - q3[kk] * ff3[kk], 0, None)).sum() / 3600)))
    byrt = pd.DataFrame(rt).sort_values("delay_corr_h", ascending=False).reset_index(drop=True)
    tot_corr = float(byrt.delay_corr_h.sum())
    byrt["delay_corr_pct"] = (100 * byrt.delay_corr_h / tot_corr) if tot_corr > 0 else 0.0
    byrt.to_csv(OUT / "e2b_roadtype_quantization.csv", index=False, encoding="utf-8-sig")
    for _, r3 in byrt.iterrows():
        A("  %-16s %8d %9d %11.3f %11.3f %+10.3f %13.0f %7.1f%%" %
          (r3.road_type, r3.n_links, r3.n_loaded, r3.ratio_vw, r3.qratio_vw,
           r3.excess_vw, r3.delay_corr_h, r3.delay_corr_pct))

    real = crdf[crdf.excess_vw > 0.05]
    G("E2b.3 走廊级真实超额已分离（>0.05 视为真有延误）", True,
      "有真实延误的走廊 = %s" % (", ".join("%s %+.3f" % (r.corridor, r.excess_vw)
                                            for _, r in real.iterrows()) or "无"))
    q1213 = hr[hr.hour == "12-13"].iloc[0]
    G("E2b.4 空网对照成立（12-13 倍率 ≈ 量化基准）",
      abs(float(q1213.ratio_vw) - float(q1213.qratio_vw)) < 0.15,
      "12-13 ratio=%.3f vs ceil基准=%.3f" % (float(q1213.ratio_vw), float(q1213.qratio_vw)))

    return dict(hr=hr, gb=gb, crdf=crdf, byrt=byrt, tot_corr_h=tot_corr,
                pure_link=float(pure.mean()),
                pure_vol=float(v[k][pure].sum() / v[k].sum()), tstep=ts)


# ============================================================================
def _chains(links, length_by, from_by, to_by):
    n = len(links)
    parent = list(range(n))

    def find(a):
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    by_from = defaultdict(list)
    for i, l in enumerate(links):
        by_from[from_by[l]].append(i)
    for i, l in enumerate(links):
        for j in by_from.get(to_by[l], ()):
            ra, rb = find(i), find(j)
            if ra != rb:
                parent[ra] = rb
    cl, cn, cm = defaultdict(float), defaultdict(int), defaultdict(list)
    for i, l in enumerate(links):
        r = find(i)
        cl[r] += length_by[l]
        cn[r] += 1
        cm[r].append(l)
    return cl, cn, cm


def e3(m: pd.DataFrame, seed: int = 4711, nperm: int = 200) -> dict:
    A("")
    A("=" * 80)
    A("E3  拥堵空间连续性（原始口径 与 扣量化后 两套判据）")
    A("=" * 80)
    d = m[(m["HRS8-9avg"].fillna(0) > 0) & (m.LENGTH >= 20.0)].copy()
    d["ratio"] = d["TRAVELTIME8-9avg"] / d.ff_s
    d["excess"] = d.ratio - (d.ff_ceil_s / d.ff_s)
    A("  宇宙（载流 & 长度>=20 m）: n=%d" % len(d))
    links = d.link.tolist()
    length_by = dict(zip(d.link, d.LENGTH.astype(float)))
    from_by = dict(zip(d.link, d.from_node.astype(int)))
    to_by = dict(zip(d.link, d.to_node.astype(int)))
    ratio_by = dict(zip(d.link, d.ratio.astype(float)))
    excess_by = dict(zip(d.link, d.excess.astype(float)))
    name_by = dict(zip(d.link, d.road_name.fillna("").astype(str)))
    rng = np.random.default_rng(seed)

    def run(tag, sel_fn, fname):
        obs = [l for l in links if sel_fn(l)]
        cl, cn, cm = _chains(obs, length_by, from_by, to_by)
        big = (max(cl.values()) / 1000.0) if cl else 0.0
        null = np.empty(nperm)
        for i in range(nperm):
            s = [links[j] for j in rng.choice(len(links), size=len(obs), replace=False)]
            c2, _, _ = _chains(s, length_by, from_by, to_by)
            null[i] = (max(c2.values()) / 1000.0) if c2 else 0.0
        p = float((null >= big).mean())
        A("  --- %s ---" % tag)
        A("    候选链路 n=%d  里程=%.2f km  连通分量=%d  最长连续链=%.3f km"
          % (len(obs), sum(length_by[l] for l in obs) / 1000, len(cl), big))
        A("    随机零假设 mean=%.3f p95=%.3f max=%.3f km ⇒ p=%.4f z=%.2f"
          % (null.mean(), np.percentile(null, 95), null.max(), p,
             (big - null.mean()) / (null.std() + 1e-12)))
        if cm:
            order = sorted(cm, key=lambda r: -cl[r])[:8]
            rr = []
            for r in order:
                mem = cm[r]
                nm = pd.Series([name_by[l] for l in mem]).replace("", np.nan).dropna()
                rr.append(dict(n_links=cn[r], length_km=cl[r] / 1000.0,
                               mean_ratio=float(np.mean([ratio_by[l] for l in mem])),
                               mean_excess=float(np.mean([excess_by[l] for l in mem])),
                               top_road_names="; ".join(nm.value_counts().head(3).index.astype(str))))
            pd.DataFrame(rr).to_csv(OUT / fname, index=False, encoding="utf-8-sig")
        return dict(n_cong=len(obs), congested_km=float(sum(length_by[l] for l in obs) / 1000),
                    n_components=len(cl), largest_km=float(big), null_mean=float(null.mean()),
                    null_p95=float(np.percentile(null, 95)), p_value=p,
                    z=float((big - null.mean()) / (null.std() + 1e-12)))

    res = {"raw1.2": run("原始口径 ratio>1.2", lambda l: ratio_by[l] > 1.2, "e3_components_raw1p2.csv"),
           "raw1.5": run("原始口径 ratio>1.5", lambda l: ratio_by[l] > 1.5, "e3_components_raw1p5.csv"),
           "exc0.1": run("★扣量化后 真实超额>0.1", lambda l: excess_by[l] > 0.1, "e3_components_excess0p1.csv")}
    json.dump(res, open(OUT / "e3_continuity_null_test.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=2, default=float)
    G("E3.1 置换检验完成（%d 次 × 3 判据）" % nperm, True,
      "raw1.2 p=%.3f | raw1.5 p=%.3f | 超额>0.1 n=%d longest=%.3fkm"
      % (res["raw1.2"]["p_value"], res["raw1.5"]["p_value"],
         res["exc0.1"]["n_cong"], res["exc0.1"]["largest_km"]))
    return res


# ============================================================================
def leg_hist() -> pd.DataFrame:
    d = pd.read_csv(LEG_TXT, sep="\t", encoding="utf-8-sig")
    d.columns = ["time", "t", "dep_all", "arr_all", "stuck_all", "enr_all",
                 "dep_car", "arr_car", "stuck_car", "enr_car"]
    d["hhmm"] = d.t.apply(lambda s: "%02d:%02d" % (s // 3600, (s % 3600) // 60))
    return d


NB, T_LO, BIN = 28, 6 * 3600, 900


def events_15min(link_meta: dict) -> tuple[pd.DataFrame, dict]:
    cache = OUT / "e4_events_15min_by_link.csv.gz"
    if cache.exists() and not FORCE_EVENTS:
        t0 = time.time()
        ev = pd.read_csv(cache, encoding="utf-8-sig")
        A("  [events] 命中缓存 %s rows=%d (%.1f s)" % (cache.name, len(ev), time.time() - t0))
        return ev, dict(cached=True, rows=len(ev))

    A("  [events] 单次流式扫描 %s（首次约 19 min）" % EVENTS_GZ.name)
    t0 = time.time()
    store: dict[str, np.ndarray] = {}
    pend: dict[str, tuple] = {}
    n_line = n_enter = n_left = 0
    with gzip.open(EVENTS_GZ, "rb") as fb:
        f = io.TextIOWrapper(fb, encoding="utf-8", errors="replace")
        for line in f:
            if "<event " not in line:
                continue
            n_line += 1
            if '"entered link"' in line:
                t = float(attr(line, "time"))
                lid = attr(line, "link")
                b = int((t - T_LO) // BIN)
                pend[attr(line, "vehicle")] = (lid, t, b)
                n_enter += 1
                if 0 <= b < NB:
                    a = store.get(lid)
                    if a is None:
                        a = np.zeros((NB, 2), dtype=np.float32)
                        store[lid] = a
                    a[b, 0] += 1.0
            elif '"left link"' in line:
                t = float(attr(line, "time"))
                lid = attr(line, "link")
                n_left += 1
                pv = pend.pop(attr(line, "vehicle"), None)
                if pv is not None and pv[0] == lid:
                    _, t0e, b = pv
                    if 0 <= b < NB:
                        a = store.get(lid)
                        if a is not None:
                            a[b, 1] += (t - t0e)
    A("    records=%d entered=%d left=%d links=%d parse=%.1f s"
      % (n_line, n_enter, n_left, len(store), time.time() - t0))

    rec = []
    for lid, a in store.items():
        meta = link_meta.get(lid)
        if meta is None:
            continue
        L, fs, cap, rt, nm = meta
        for b in range(NB):
            c = float(a[b, 0])
            if c <= 0:
                continue
            tm = T_LO + b * BIN
            rec.append(dict(link=lid, bin=b, t_mid_s=tm,
                            hhmm="%02d:%02d" % (tm // 3600, (tm % 3600) // 60),
                            road_type=rt, corridor=NAME2CORR.get(nm, ""),
                            length_m=L, capacity_veh_h=cap, n_veh=c, rate_veh_h=c * 3600.0 / BIN,
                            sum_tt_s=float(a[b, 1]), mean_tt_s=float(a[b, 1]) / c, ff_s=(L / fs)))
    ev = pd.DataFrame(rec)
    ev.to_csv(cache, index=False, encoding="utf-8-sig", compression="gzip")
    G("E4.1 events 15 min 聚合完成", len(ev) > 0, "rows=%d 解析=%.1f s" % (len(ev), time.time() - t0))
    return ev, dict(cached=False, records=n_line, entered=n_enter, left=n_left,
                    links_touched=len(store), parse_sec=time.time() - t0)


def e4(m: pd.DataFrame, lh: pd.DataFrame) -> dict:
    A("")
    A("=" * 80)
    A("E4  07:00-09:00 峰值演化（5 min 在途 + 15 min 网络状态）")
    A("=" * 80)
    meta = {r.link: (float(r.LENGTH), float(r.FREESPEED), float(r.CAPACITY), r.road_type,
                     ("" if pd.isna(r.road_name) else str(r.road_name))) for r in m.itertuples()}
    ev, parse = events_15min(meta)
    if parse.get("cached"):
        G("E4.1 events 15 min 聚合完成（读缓存）", len(ev) > 0, "rows=%d" % len(ev))
    lh.to_csv(OUT / "e4_leg_histogram_5min.csv", index=False, encoding="utf-8-sig")

    ev = ev.copy()
    ev["ff_ceil_s"] = np.ceil(ev.ff_s - 1e-9)
    ev["ratio"] = ev.mean_tt_s / ev.ff_s
    ev["excess"] = ev.ratio - ev.ff_ceil_s / ev.ff_s

    rows = []
    for b, s in ev.groupby("bin"):
        vv = s.n_veh.to_numpy(float)
        ll = s.length_m.to_numpy(float)
        st = s.sum_tt_s.to_numpy(float)
        cap = s.capacity_veh_h.to_numpy(float)
        rate = s.rate_veh_h.to_numpy(float)
        ff = s.ff_s.to_numpy(float)
        fc = s.ff_ceil_s.to_numpy(float)
        ok = st > 0
        rows.append(dict(bin=int(b), hhmm=str(s.hhmm.iloc[0]), entries=float(vv.sum()),
                         veh_km=float((vv * ll).sum() / 1000),
                         net_speed_kmh=float((vv[ok] * ll[ok]).sum() / st[ok].sum() * 3.6),
                         net_ratio=float(st[ok].sum() / (vv[ok] * ff[ok]).sum()),
                         net_excess=float(st[ok].sum() / (vv[ok] * ff[ok]).sum()
                                          - (vv[ok] * fc[ok]).sum() / (vv[ok] * ff[ok]).sum()),
                         agg_vc=float(rate.sum() / cap.sum()),
                         cong_km=float(ll[(s.ratio > 1.2).to_numpy()].sum() / 1000),
                         delay_raw_h=float(np.clip(st[ok] - vv[ok] * ff[ok], 0, None).sum() / 3600),
                         delay_corr_h=float(np.clip(st[ok] - vv[ok] * fc[ok], 0, None).sum() / 3600)))
    net15 = pd.DataFrame(rows).sort_values("bin")
    net15.to_csv(OUT / "e4_network_temporal_15min.csv", index=False, encoding="utf-8-sig")

    A("")
    A("  %-6s %10s %9s %8s %8s %9s %9s %10s %11s" %
      ("hhmm", "entries", "veh_km", "km/h", "实测RR", "真实超额", "aggV/C", "拥堵km", "扣量化延误h"))
    for _, r in net15.iterrows():
        if "06:45" <= r.hhmm <= "10:45":
            A("  %-6s %10.0f %9.0f %8.1f %8.3f %+9.3f %9.3f %10.1f %11.0f" %
              (r.hhmm, r.entries, r.veh_km, r.net_speed_kmh, r.net_ratio, r.net_excess,
               r.agg_vc, r.cong_km, r.delay_corr_h))

    ec = ev[ev.corridor != ""]
    cor15 = ec.groupby(["corridor", "bin", "hhmm"], observed=True).apply(lambda s: pd.Series({
        "veh": s.n_veh.sum(),
        "net_ratio": s.sum_tt_s.sum() / (s.n_veh * s.ff_s).sum(),
        "net_excess": (s.sum_tt_s.sum() / (s.n_veh * s.ff_s).sum()
                       - (s.n_veh * s.ff_ceil_s).sum() / (s.n_veh * s.ff_s).sum()),
        "cong_km": s.loc[s.ratio > 1.2, "length_m"].sum() / 1000.0}), include_groups=False).reset_index()
    cor15.to_csv(OUT / "e4_corridor_temporal_15min.csv", index=False, encoding="utf-8-sig")

    pk = lh.loc[lh.enr_car.idxmax()]
    am = lh[(lh.t >= 6 * 3600) & (lh.t < 11 * 3600)]
    flat = float(am.enr_car.max() / max(am.enr_car.median(), 1e-9))
    A("")
    A("  5 min 在途(car): 峰值=%.0f @ %s (N_sim=236044, %.1f%%) peak/median=%.2f"
      % (pk.enr_car, pk.hhmm, 100 * pk.enr_car / 236044, flat))
    G("E4.2 存在峰值时刻", flat > 1.5, "peak=%.0f @ %s peak/median=%.2f" % (pk.enr_car, pk.hhmm, flat))

    peakb = net15.loc[net15.entries.idxmax()]
    G("E4.3 峰值 15 min 网络 V/C << 1", float(peakb.agg_vc) < 0.5,
      "峰值 %s aggV/C=%.3f 真实超额=%+.3f 扣量化延误=%.0f 车时"
      % (peakb.hhmm, peakb.agg_vc, peakb.net_excess, peakb.delay_corr_h))

    chk = []
    for h in ("7-8", "8-9"):
        lo = int(h.split("-")[0]) * 3600
        s = ev[(ev.t_mid_s >= lo) & (ev.t_mid_s < lo + 3600)]
        chk.append(dict(hour=h, events_entries=float(s.n_veh.sum()),
                        linkstats_total=float(m["HRS%savg" % h].fillna(0).sum())))
    cdf = pd.DataFrame(chk)
    cdf["rel_diff_pct"] = 100 * (cdf.events_entries - cdf.linkstats_total) / cdf.linkstats_total
    cdf.to_csv(OUT / "e4_crosscheck_linkstats.csv", index=False, encoding="utf-8-sig")
    G("E4.4 events 汇总 = linkstats 小时值（<0.1%）", bool((cdf.rel_diff_pct.abs() < 0.1).all()),
      "max|rel|=%.4f%%" % float(cdf.rel_diff_pct.abs().max()))
    return dict(net15=net15, cor15=cor15, ev=ev, lh=lh, parse=parse,
                peak=float(pk.enr_car), peak_time=str(pk.hhmm), peak_flat=flat, cdf=cdf)


# ============================================================================
def figure(r1, r2b, r3, r4) -> Path:
    fig = plt.figure(figsize=(19.5, 11.8), dpi=125)
    gs = fig.add_gridspec(2, 3, hspace=0.44, wspace=0.30)

    ax = fig.add_subplot(gs[0, 0])
    t = r1["tab"].sort_values("capacity_per_lane")
    y = np.arange(len(t))
    ax.barh(y, t.capacity_per_lane, color="#4c78a8", height=0.6)
    for i, (_, r) in enumerate(t.iterrows()):
        if not math.isnan(r.bench_lo):
            ax.plot([r.bench_lo, r.bench_hi], [i, i], color="#e45756", lw=3.2, alpha=0.45)
    ax.set_yticks(y); ax.set_yticklabels(t.road_type, fontsize=8)
    ax.set_xlabel("每车道容量 (辆·车道$^{-1}$·h$^{-1}$)", fontsize=9)
    ax.set_title("(A) E1 容量按道路类型硬编码\n快速路在参考带内，干道偏高", fontsize=10, loc="left")
    ax.grid(alpha=0.25, axis="x")

    ax = fig.add_subplot(gs[0, 1])
    c = r2b["crdf"].sort_values("ratio_vw")
    y = np.arange(len(c))
    ax.barh(y, c.ratio_vw, color="#e45756", height=0.64, alpha=0.55, label="实测 TT/FF")
    ax.barh(y, c.qratio_vw, color="#4c78a8", height=0.64, label="ceil(FF)/FF 量化基准")
    ax.plot(1.0 + c.excess_vw * 10, y, "D", color="#000000", ms=6, label="真实超额 ×10 + 1.0")
    ax.axvline(1.0, color="#54a24b", lw=1.2, ls="--")
    ax.set_yticks(y); ax.set_yticklabels(c.corridor, fontsize=9)
    ax.set_xlabel("倍率", fontsize=9)
    ax.set_title("(B) ★走廊 TT/FF 1.2–1.44 几乎全由 1 秒量化基准解释\n黑点=真实超额，仅 CTE 明显偏离",
                 fontsize=10, loc="left")
    ax.legend(fontsize=7.5, loc="lower right")
    ax.grid(alpha=0.25, axis="x")

    ax = fig.add_subplot(gs[0, 2])
    s = r1["sup"]
    keys = ["ALL_LINKS", "LOADED_LINKS", "EXPRESSWAY_CORRIDORS", "ARTERIAL_CLASSES", "LOCAL_CLASSES"]
    vals = [s[k]["util_pct"] for k in keys]
    ax.bar(range(len(keys)), vals, color="#72b7b2")
    ax.axhline(100, color="#e45756", lw=1.4, ls="--")
    for i, v in enumerate(vals):
        ax.text(i, v + 1.5, "%.1f%%" % v, ha="center", fontsize=8.5)
    ax.set_xticks(range(len(keys)))
    ax.set_xticklabels(["全部", "已载流", "快速路\n走廊", "干道", "地方\n道路"], fontsize=8.5)
    ax.set_ylabel("容量利用率 = Σ流量/Σ容量 (%)", fontsize=9)
    ax.set_title("(C) E1 容量利用率：即使快速路走廊也仅 %.1f%%"
                 % s["EXPRESSWAY_CORRIDORS"]["util_pct"], fontsize=10, loc="left")
    ax.grid(alpha=0.25, axis="y")

    ax = fig.add_subplot(gs[1, 0])
    hr = r2b["hr"]
    x = np.arange(len(hr))
    ax.plot(x, hr.ratio_vw, "-o", ms=5, color="#e45756", label="实测 TT/FF")
    ax.plot(x, hr.qratio_vw, "-s", ms=5, color="#4c78a8", label="ceil(FF)/FF 量化基准")
    ax.fill_between(x, hr.qratio_vw, hr.ratio_vw, color="#e45756", alpha=0.15)
    ax.set_xticks(x); ax.set_xticklabels(hr.hour, fontsize=8.5)
    ax.set_ylim(1.0, max(5.0, float(hr.ratio_vw.max()) + 0.4))
    ax.set_ylabel("体量加权 TT/FF", fontsize=9)
    ax.set_title("(D) ★跨时段对照：几乎空网的 12–13 时倍率仍=%.2f\n（本口径测的是量化、不是拥堵）"
                 % float(hr[hr.hour == "12-13"].ratio_vw.iloc[0]), fontsize=10, loc="left")
    ax.legend(fontsize=8); ax.grid(alpha=0.25)

    ax = fig.add_subplot(gs[1, 1])
    w = r4["net15"]
    w = w[w.hhmm.between("06:45", "10:45")]
    ax.plot(w.bin, w.net_ratio, "-o", ms=3.5, color="#e45756", label="实测 TT/FF")
    ax.plot(w.bin, w.net_ratio - w.net_excess, "-s", ms=3.5, color="#4c78a8",
            label="量化基准（实测−超额）")
    ax.axhline(1.0, color="#54a24b", lw=1.2, ls="--")
    # 09:15 后需求崩塌 ⇒ 只剩 service 短段载流，倍率被动放大（伪影，不是拥堵波）
    _i9 = int(np.searchsorted(list(w.hhmm), "09:15"))
    ax.axvspan(_i9 - 0.5, len(w) - 0.5, color="#bfbfbf", alpha=0.30, lw=0)
    ax.text(_i9 + 0.1, float(w.net_ratio.max()) * 1.12,
            "09:15 后需求崩塌，仅 service 短段载流\n尾部升高是伪影放大，非拥堵波",
            fontsize=6.5, color="#555", va="top")
    ax.set_ylim(1.0, 1.18 * float(w.net_ratio.max()))
    ax.set_xticks(list(w.bin)); ax.set_xticklabels(list(w.hhmm), rotation=90, fontsize=7)
    ax.set_ylabel("网络行程时间倍率", fontsize=9)
    ax2 = ax.twinx()
    ax2.plot(w.bin, w.agg_vc, ":", color="#7f7f7f", lw=2)
    ax2.set_ylabel("网络 Σ流量/Σ容量", fontsize=9, color="#7f7f7f")
    ax2.set_ylim(0, max(0.2, float(w.agg_vc.max()) * 2))
    ax.set_title("(E) E4 15 min 演化：AM 峰内几乎无额外延误", fontsize=10, loc="left")
    ax.legend(fontsize=8); ax.grid(alpha=0.25)

    ax = fig.add_subplot(gs[1, 2])
    lh = r4["lh"]
    w = lh[(lh.t >= 6 * 3600) & (lh.t <= 11 * 3600)]
    ax.plot(w.t / 3600.0, w.enr_car, "-", color="#54a24b", lw=1.8)
    ax.fill_between(w.t / 3600.0, 0, w.enr_car, color="#54a24b", alpha=0.18)
    ax.axhline(236044, color="#b0b0b0", lw=1.0, ls=":")
    ax.text(6.05, 236044 * 1.02, "N_sim = 236,044（全天 agent 总数）", fontsize=7.5, color="#555")
    ax.axhline(r4["peak"], color="#e45756", lw=1.0, ls="--")
    ax.text(6.05, r4["peak"] * 1.05, "峰值同时在途 = %.0f @ %s" % (r4["peak"], r4["peak_time"]),
            fontsize=7.5, color="#c0392b")
    ax.set_ylim(0, 260000); ax.set_xlabel("时刻 (h)", fontsize=9)
    ax.set_ylabel("同时在途小汽车 (辆, 5 min)", fontsize=9)
    ax.set_title("(F) 峰值同时在途仅占 agent 总数 %.1f%%" % (100 * r4["peak"] / 236044),
                 fontsize=10, loc="left")
    ax.grid(alpha=0.25)

    fig.suptitle("Step 7.7E 拥堵状态合理性审计（v2 含量化审计）—— 只读派生，非 7.8 冻结产品",
                 fontsize=13, y=0.985)
    p = OUT / "congestion_plausibility_audit_7_7e.png"
    fig.savefig(p, bbox_inches="tight")
    plt.close(fig)
    return p


# ============================================================================
def main() -> None:
    data = load()
    m = data["m"]
    r1 = e1(m)
    r2 = e2(m)
    r2b = e2b(m)
    r3 = e3(m)
    lh = leg_hist()
    r4 = e4(m, lh)
    figp = figure(r1, r2b, r3, r4)

    s = r1["sup"]
    cor = r2["cor"]
    crdf = r2b["crdf"]
    byrt = r2b["byrt"]
    hr = r2b["hr"]
    q1213 = hr[hr.hour == "12-13"].iloc[0]
    n15 = r4["net15"]
    f = n15[n15.hhmm.between("07:00", "08:45")]
    cte = crdf[crdf.corridor == "CTE"].iloc[0]
    other = crdf[crdf.corridor != "CTE"]
    satc = r2["sat"]
    cte_sat = int((satc.road_name == "Central Expressway").sum())
    svc_sat = int((satc.road_type == "service").sum())
    cte_sat_km = float(satc.loc[satc.road_name == "Central Expressway", "length_m"].sum() / 1000)
    tot_corr_h = float(r2b["tot_corr_h"])
    _svc = byrt[byrt.road_type == "service"]
    svc_delay_pct = float(_svc.delay_corr_pct.iloc[0]) if len(_svc) else 0.0
    svc_delay_h = float(_svc.delay_corr_h.iloc[0]) if len(_svc) else 0.0
    _mw = byrt[byrt.road_type == "motorway"]
    mw_delay_h = float(_mw.delay_corr_h.iloc[0]) if len(_mw) else 0.0

    MD("# Step 7.7E 拥堵状态合理性审计报告（v2，含量化审计）\n")
    MD("> **性质**：只读事后审计。⛔ 未跑 MATSim、未改任何冻结输入/参数/产物；"
       "模型仍是 `Singapore_OD_MATSim_Final_v1.0`。产物全在 `reports/congestion_plausibility_audit_7_7e/`。\n")
    MD("> **数据源**：`matsim_viz_7_8/outputs/W01_events/`（7.8-VIZ-RUN 输出层重执行，已判 `BITEXACT`）"
       " + `reports/matsim_network/network_links_source_copy.csv`（源路网副本，含 OSM `highway`/`name`）。\n")

    MD("## 0. 两条必须先纠正的口径\n")
    MD("### 0.1 `v/c ≤ 1` 是结构性质，不是「容量富余」\n")
    MD("MATSim 链路流出被容量截断：需求超额时表现为**上游排队**，而非该链路 `v/c > 1`。"
       "所以 `v/c = HRS8-9avg / CAPACITY` **恒 ≤ 1**；`v/c = 1.000000` 表示「**已饱和 + 正在排队**」。\n")
    MD("### 0.2 ★★`qsim.timeStepSize = 1 s` ⇒「拥堵倍率」口径被量化污染\n")
    MD("配置第 222 行 `timeStepSize = %s`。本网络链路自由流时间**中位 %.2f s、均值 %.2f s**"
       "（>500 m 的链路只有 29 条），多数链路不足一个时间步；1 s 步长下链路行程时间被"
       "**向上取整到整秒**（`TT_recorded = ceil(FF)`），于是**即使零延误**，`TT/FF` 也等于 "
       "`ceil(FF)/FF ≫ 1`。\n" % (r2b["tstep"], float(m.ff_s.median()), float(m.ff_s.mean())))
    MD("**交叉证据**：\n")
    MD("- 全网 **12–13 时（几乎空网，仅 %.0f 车·链路）** 体量加权 `TT/FF` 仍有 **%.3f**，"
       "量化基准 **%.3f** ⇒ 该时段**不含拥堵信号**。\n"
       % (float(q1213.vol), float(q1213.ratio_vw), float(q1213.qratio_vw)))
    MD("- **%.2f%% 的载流链路（占 %.2f%% 体量）** 满足 `|TT/FF − ceil(FF)/FF| < %.2f` ⇒ **零延误**。\n"
       % (100 * r2b["pure_link"], 100 * r2b["pure_vol"], Q_TOL))
    MD("- 单车级样本：链路 `e138309_138310`（长 15.924 m，FF=0.955 s）07:00 有 23 辆车，"
       "`sum_tt` **恰为 23.0 s** ⇒ 每辆车恰好走 **1 秒 = ceil(0.955)**。\n")
    MD("⇒ 「**拥堵倍率 = TRAVELTIME8-9avg ÷ (LENGTH/FREESPEED)**」必须扣除量化基准。"
       "**7.6/7.7 的标定用的是断面*流量*（Sim/Obs），不受影响**；"
       "受影响的是任何以 `TRAVELTIME` 为依据的拥堵评价。\n")

    MD("## E1 容量到底怎么来的\n")
    MD("`capacity = lanes × capacityPerLane(road_type)`，`capacityPerLane` 是 `road_type` 的"
       "**确定性函数**（E1.1）；限速与源副本**逐位一致**（E1.3）；源副本 `lanes` 有 27 万余条缺失"
       "（不参与比较），可比区间内车道数完全一致（E1.2）。\n")
    MD("| road_type | 链路数 | 占比 | 车道 | **每车道容量** | km/h | 链路长中位 | FF中位 s | 参考带 | 判定 |")
    MD("|---|---:|---:|---:|---:|---:|---:|---:|---|---|")
    for _, r in r1["tab"].iterrows():
        band = "—" if math.isnan(r.bench_lo) else "%.0f–%.0f" % (r.bench_lo, r.bench_hi)
        MD("| `%s` | %d | %.1f%% | %.1f | **%.0f** | %.0f | %.1f | %.2f | %s | %s |" %
           (r.road_type, r.n_links, r.link_pct, r.lanes_med, r.capacity_per_lane,
            r.freespeed_kmh, r.length_med_m, r.ff_med_s, band, r.vs_bench))
    MD("")
    MD("**判定**：快速路/高速（motorway 1900、trunk 1800、motorway_link 1700）**在参考带内**，"
       "并未被抬高；**超出上沿的是干道与地方道路**（%s）。"
       "⇒ **容量不是「被设得离谱地大」，H1 不成立。**\n"
       % ", ".join("%s %.0f>%.0f" % (r.road_type, r.capacity_per_lane, r.bench_hi)
                   for _, r in r1["above"].iterrows()))
    MD("| 范围 | 供给 veh·km/h | 需求 veh·km/h | **利用率** |")
    MD("|---|---:|---:|---:|")
    for k in ["ALL_LINKS", "LOADED_LINKS", "EXPRESSWAY_CORRIDORS", "ARTERIAL_CLASSES", "LOCAL_CLASSES"]:
        v = s[k]
        MD("| %s | %.0f | %.0f | **%.2f%%** |" % (k, v["cap_veh_km_h"], v["dem_veh_km_h"], v["util_pct"]))
    MD("")
    MD("★ **即使只看已载流链路，容量利用率也只有 %.1f%%**；快速路走廊 %.1f%%。"
       "693,575 条链路里只有 %d 条（%.1f%%）在 08–09 有流量，其中 **%d 条是 `service` 短段**"
       "（中位 8.9 m）⇒ 需求在空间上被铺得极开。\n"
       % (s["LOADED_LINKS"]["util_pct"], s["EXPRESSWAY_CORRIDORS"]["util_pct"],
          int((m["HRS8-9avg"].fillna(0) > 0).sum()), 100 * (m["HRS8-9avg"].fillna(0) > 0).mean(),
          int(((m["HRS8-9avg"].fillna(0) > 0) & (m.road_type == "service")).sum())))

    MD("## E2 主要走廊：原始口径\n")
    MD("| 走廊 | 链路 | 里程 km | 流量 veh | **TT/FF** | 均速 km/h | V/C | 饱和链路 | 原始延误 车时 |")
    MD("|---|---:|---:|---:|---:|---:|---:|---:|---:|")
    for _, r in cor.sort_values("ratio_vw", ascending=False).iterrows():
        MD("| **%s** | %d | %.1f | %.0f | **%.3f** | %.1f | %.3f | %d | %.0f |" %
           (r.key, r.n_links, r.length_km, r.vol_veh, r.ratio_vw, r.speed_kmh, r.vc_agg,
            r.sat_links, r.delay_raw_h))
    MD("")
    MD("原始口径下 10 条快速路 `TT/FF` = %.3f–%.3f，看起来「每条都在堵」。**但这个口径是错的** —— 见 E2b。\n"
       % (float(cor.ratio_vw.min()), float(cor.ratio_vw.max())))

    MD("## E2b ★量化审计：上面的「拥堵」有多少是真的\n")
    MD("**跨时段对照**（同口径、不同需求水平）：\n")
    MD("| 时段 | 载流链路 | 流量 | 实测 TT/FF | **ceil(FF)/FF 基准** | **真实超额** | 原始延误 车时 | 扣量化延误 车时 |")
    MD("|---|---:|---:|---:|---:|---:|---:|---:|")
    for _, r in hr.iterrows():
        MD("| %s | %d | %.0f | %.3f | **%.3f** | **%+.3f** | %.0f | %.0f |" %
           (r.hour, r.n_links, r.vol, r.ratio_vw, r.qratio_vw, r.excess_vw,
            r.delay_raw_h, r.delay_corr_h))
    MD("")
    MD("⇒ 量化基准在所有时段恒定在 **%.3f–%.3f**（只由路网几何决定），"
       "实测倍率随需求在 %.3f–%.3f 之间变动；**几乎空网的 12–13 时倍率仍有 %.3f = 基准**。\n"
       % (float(hr.qratio_vw.min()), float(hr.qratio_vw.max()),
          float(hr.ratio_vw.min()), float(hr.ratio_vw.max()), float(q1213.ratio_vw)))
    MD("**按链路长度分桶（08–09）**：\n")
    MD("| 长度 | 链路 | 体量占比 | 平均 FF s | 实测 TT/FF | ceil 基准 | **真实超额** |")
    MD("|---|---:|---:|---:|---:|---:|---:|")
    for idx, r in r2b["gb"].iterrows():
        MD("| %s m | %d | %.2f%% | %.3f | %.3f | %.3f | **%+.3f** |" %
           (idx, r.links, r.vol_pct, r.ff_mean_s, r.ratio_vw, r.qratio_vw, r.excess_vw))
    MD("")
    MD("**走廊级扣量化（08–09）**：\n")
    MD("| 走廊 | 里程 km | 实测 TT/FF | ceil 基准 | **真实超额** | 扣量化延误 车时 |")
    MD("|---|---:|---:|---:|---:|---:|")
    for _, r in crdf.sort_values("excess_vw", ascending=False).iterrows():
        MD("| **%s** | %.1f | %.3f | %.3f | **%+.3f** | %.0f |" %
           (r.corridor, r.length_km, r.ratio_vw, r.qratio_vw, r.excess_vw, r.delay_corr_h))
    MD("")
    MD("**★按道路类型分解「扣量化后的真实延误」（08–09，全网络）**：\n")
    MD("| road_type | 载流链路 | 里程 km | TT/FF | ceil 基准 | **真实超额** | **扣量化延误 车时** | **占比** |")
    MD("|---|---:|---:|---:|---:|---:|---:|---:|")
    for _, r in byrt.iterrows():
        MD("| `%s` | %d | %.1f | %.3f | %.3f | **%+.3f** | **%.0f** | **%.1f%%** |" %
           (r.road_type, r.n_loaded, r.length_km, r.ratio_vw, r.qratio_vw,
            r.excess_vw, r.delay_corr_h, r.delay_corr_pct))
    MD("")
    MD("⇒ 全网 %.0f 车时真实延误里，**`service` 短段占 %.1f%%（%.0f 车时）**、"
       "**`motorway` 仅 %.0f 车时（且全部落在 CTE）**、"
       "trunk/primary/secondary/tertiary 合计 ≈ %.0f 车时。"
       "**「真实拥堵延误」的主体是大量 20 km/h 单车道接入短段的局部瓶颈，"
       "而不是城市快速路的排队拥堵。**\n"
       % (tot_corr_h, svc_delay_pct, svc_delay_h, mw_delay_h,
          float(byrt[byrt.road_type.isin(["trunk", "primary", "secondary", "tertiary"])].delay_corr_h.sum())))
    MD("★★ **9/10 条快速路走廊的真实超额在 %+.3f ~ %+.3f（≈0）**；"
       "**只有 CTE 有 %+.3f 的真实超额（%.0f 车时）**。"
       "这与 CTE 上 **%d 条链路 v/c 恰好 = 1.000（正在排队）** 完全互证 —— "
       "**CTE 是全网络唯一存在真实拥堵的快速路走廊**"
       "（注意：就全网络而言，`service` 接入短段的真实延误总量远大于此，"
       "属局部接入瓶颈、不构成快速路拥堵）。\n"
       % (float(other.excess_vw.min()), float(other.excess_vw.max()),
          float(cte.excess_vw), float(cte.delay_corr_h), cte_sat))
    MD("饱和链路清单（`e2_saturated_links_0809.csv`，n=%d，总长 %.2f km）："
       "%d 条是 6 m 左右的 `service` 短段（单车道容量 400 辆/h，`v/c=1` 属局部低容量瓶颈）；"
       "%d 条是 **CTE** 上的 motorway 链路（4 车道 / 90 km/h / 容量 7600，节点 "
       "`7214→7215→…→7221→20261` 首尾相接，SVY21 x≈29.4–29.7k、y≈33.0–33.3k，"
       "即 CTE 中段 Jalan Toa Payoh / Kampong Java 一带），构成一条 **≈%.2f km 的排队链**。\n"
       % (len(satc), float(satc.length_m.sum() / 1000), svc_sat, cte_sat, cte_sat_km))

    MD("## E3 拥堵是否形成连续空间结构\n")
    MD("宇宙 = 08–09 有流量且长度 ≥ 20 m 的链路；按 `link.to_node == next.from_node` 串成有向链，"
       "取最长连通分量，与 **200 次随机置换**比较：\n")
    MD("| 判据 | 候选链路 | 里程 km | 连通分量 | **最长连续链 km** | 随机均值 km | 随机 p95 | p 值 | z |")
    MD("|---|---:|---:|---:|---:|---:|---:|---:|---:|")
    for tag, lbl in [("raw1.2", "原始口径 TT/FF>1.2"), ("raw1.5", "原始口径 TT/FF>1.5"),
                     ("exc0.1", "★扣量化后 真实超额>0.1")]:
        v = r3[tag]
        MD("| %s | %d | %.2f | %d | **%.3f** | %.3f | %.3f | %.4f | %.2f |" %
           (lbl, v["n_cong"], v["congested_km"], v["n_components"], v["largest_km"],
            v["null_mean"], v["null_p95"], v["p_value"], v["z"]))
    MD("")
    MD("**两套原始口径**（TT/FF>1.2、TT/FF>1.5）结论一致：实测最长连续链都**短于**随机散布期望"
       "（p = %.2f / %.2f，z 为负）⇒ 被量化伪影标记的链路不但没成簇，反而比随机散布**更分散**"
       "—— 正符合量化伪影特征：`ceil(FF)/FF` 只取决于该链路 FF 的小数部分，与地理、上下游无关。\n"
       % (r3["raw1.2"]["p_value"], r3["raw1.5"]["p_value"]))
    MD("**★扣量化后的真实口径**（真实超额>0.1，n=%d 条、共 %.2f km）：最长连续链 **%.3f km**，"
       "随机均值 %.3f km，p **= %.3f**、z **= %+.2f** ⇒ **与随机散布不可区分（不显著）**。"
       "即扣掉量化后剩下的「真实拥堵」既不成簇、**也不比随机更分散**；"
       "**模型没有形成任何「连续几公里的拥堵走廊」。**\n"
       % (r3["exc0.1"]["n_cong"], r3["exc0.1"]["congested_km"], r3["exc0.1"]["largest_km"],
          r3["exc0.1"]["null_mean"], r3["exc0.1"]["p_value"], r3["exc0.1"]["z"]))

    MD("## E4 07:00–09:00 峰值演化\n")
    MD("**5 min 在途（car）**：峰值 **%.0f 辆 @ %s**，全天 agent 总数 `N_sim = 236,044` ⇒ "
       "**峰值只占 %.1f%%**；峰值/中位 = %.2f。\n"
       % (r4["peak"], r4["peak_time"], 100 * r4["peak"] / 236044, r4["peak_flat"]))
    MD("**15 min 网络状态**（与 linkstats 小时值交叉校验，最大相对差 %.4f%%）：\n"
       % float(r4["cdf"].rel_diff_pct.abs().max()))
    MD("| 时刻 | 进入链路数 | 车公里 | 均速 km/h | 实测 TT/FF | **真实超额** | Σ流量/Σ容量 | 拥堵里程 km（原始口径） | 扣量化延误 车时 |")
    MD("|---|---:|---:|---:|---:|---:|---:|---:|---:|")
    for _, r in f.iterrows():
        MD("| %s | %.0f | %.0f | %.1f | %.3f | **%+.3f** | %.3f | %.1f | %.0f |" %
           (r.hhmm, r.entries, r.veh_km, r.net_speed_kmh, r.net_ratio, r.net_excess,
            r.agg_vc, r.cong_km, r.delay_corr_h))
    MD("")
    MD("★ 整条 07–09 曲线**没有出现拥堵波**：真实超额全程 %+.3f ~ %+.3f，"
       "`Σ流量/Σ容量` 峰值仅 **%.3f**。**模型确实没有形成 AM 拥堵波。**"
       "（表中「拥堵里程 km」为**原始口径** TT/FF>1.2 的链路里程，含量化伪影；"
       "同理，该口径下的延误 **≈90%% 落在 `service` 接入短段**，非城市快速路拥堵。）\n"
       % (float(f.net_excess.min()), float(f.net_excess.max()), float(f.agg_vc.max())))

    MD("## 结论：裁决\n")
    MD("| 假设 | 证据 | 裁决 |")
    MD("|---|---|---|")
    MD("| H1 模型容量过大 | 快速路每车道容量 1700–1900 在参考带内；干道 1200–1500 偏高但只影响局部；"
       "已载流链路利用率仅 %.1f%% | **不成立**（容量不是主因，但真实利用率确实极低） |"
       % s["LOADED_LINKS"]["util_pct"])
    MD("| H2 OD 时空实现不足 | 峰值同时在途仅 %.0f 辆 = agent 总数 %.1f%%；快速路走廊利用率 %.1f%% | "
       "**主因** |" % (r4["peak"], 100 * r4["peak"] / 236044, s["EXPRESSWAY_CORRIDORS"]["util_pct"]))
    MD("| H3 路网表征稀释 | 693,575 条链路中 65%% 是 `service` 短段；链路 FF 中位 %.2f s | "
       "**成立（放大视觉错觉）** |" % float(m.ff_s.median()))
    MD("| **H4（新增，本步最重要）** 度量伪影 | `timeStepSize=1 s` 使 `TT/FF ≥ ceil(FF)/FF`；"
       "空网时段仍报 %.2f；%.2f%% 链路零延误 | **决定性，推翻既有「拥堵倍率」口径** |"
       % (float(q1213.ratio_vw), 100 * r2b["pure_link"]))
    MD("")
    MD("**一句话**：这个模型不是「有点堵但 VIA 没显示出来」，而是"
       "**在扣掉 1 秒量化伪影之后，全网基本不堵**：全网 %.0f 车时真实延误中，"
       "**%.1f%% 落在 `service`（20 km/h 单车道接入短段，局部瓶颈、疑 OSM 碎化伪影）**、"
       "**%.1f%% 落在 `motorway`（%.0f 车时，且全部在 CTE）**；"
       "**快速路走廊层面唯一成形的真实拥堵 = CTE 一段约 %.2f km 的排队链**。"
       "这不影响「总量级已校准」，但与「AM 拥堵状态是否成形」是**两件事**。\n"
       % (tot_corr_h, svc_delay_pct,
          100 * mw_delay_h / tot_corr_h if tot_corr_h > 0 else 0.0, mw_delay_h, cte_sat_km))
    MD("**「交通流量校准成功 ≠ 拥堵状态校准成功」得到数据支持**："
       "576 断面 `Sim/Obs = 0.9993348` 说明**总量级匹配**；"
       "而已载流链路容量利用率仅 %.0f%%、网络 `Σ流量/Σ容量` 峰值仅 %.3f、无拥堵波，"
       "快速路走廊真实超额 ≈ 0（9/10 条），说明**交通状态形成机制未被校准**。"
       "网络级仍剩 **+%.3f** 的真实超额，但其中 **%.1f%% 集中在 `service` 接入短段**"
       "（非快速路拥堵）。两者不矛盾。\n"
       % (s["LOADED_LINKS"]["util_pct"], float(f.agg_vc.max()),
          float(f.net_excess.max()), svc_delay_pct))
    MD("⛔ **不得为了「让动画堵起来」而放大 demand**：`f_work=1.180222`、`Sim/Obs=0.9993348` "
       "是已冻结的校准结果，放大它等于用已解决的问题去破坏另一个问题。"
       "正确路径是 `7.9 Structural Repair / v1.1`（容量/车道/瓶颈/出发剖面结构修复 "
       "+ **调小 `qsim.timeStepSize` 或改用逐车行程时间评价**），须另立版本 + 独立验证链。\n")

    MD("## 产物\n")
    MD("| 文件 | 内容 |")
    MD("|---|---|")
    for nm, desc in [
        ("`e1_capacity_provenance_by_roadtype.csv`", "每道路类型的每车道容量与参考带对照"),
        ("`e1_capacity_anomalies.csv`", "容量/车道/限速异常扫描"),
        ("`e1_network_supply_vs_demand.csv`", "网络供给 vs 需求与利用率（按范围）"),
        ("`e2_corridor_congestion_0809.csv`", "10 条快速路走廊（含原始倍率/量化基准/超额）"),
        ("`e2_roadclass_congestion_0809.csv`", "按道路等级的聚合指标"),
        ("`e2_saturated_links_0809.csv`", "**饱和链路清单（v/c=1，正在排队）**"),
        ("`e2b_hour_control.csv`", "**跨时段量化对照（含空网对照）**"),
        ("`e2b_length_bucket.csv`", "**按长度的量化分解**"),
        ("`e2b_corridor_quantization.csv`", "**走廊级扣量化结果**"),
        ("`e2b_roadtype_quantization.csv`", "**★按道路类型分解的真实延误（service 占 94.4%%）**"),
        ("`e3_components_*.csv` / `e3_continuity_null_test.json`", "连通分量明细与 200 次置换零假设"),
        ("`e4_events_15min_by_link.csv.gz`", "events 派生的 15 min × 链路流量/行程时间（缓存）"),
        ("`e4_network_temporal_15min.csv` / `e4_corridor_temporal_15min.csv`", "网络/走廊 15 min 时序"),
        ("`e4_leg_histogram_5min.csv` / `e4_crosscheck_linkstats.csv`", "5 min 在途与交叉校验"),
        ("`congestion_plausibility_audit_7_7e.png`", "6 面板总览图"),
        ("`audit_summary.json`", "机器可读摘要"),
    ]:
        MD("| %s | %s |" % (nm, desc))
    MD("")
    MD("脚本：`scripts/od/audit_congestion_plausibility_7_7e.py`"
       "（零仿真；首次 events 扫描 ~19 min，之后走缓存 < 2 min）。\n")

    (OUT / "CONGESTION_PLAUSIBILITY_AUDIT_7_7E.md").write_text("\n".join(MDL), encoding="utf-8")

    npass = sum(1 for _, ok, _ in GATES if ok)
    summary = dict(
        step="7.7E", verdict="CONGESTION_STATE_PLAUSIBILITY_AUDIT_COMPLETE",
        gates_total=len(GATES), gates_pass=npass,
        gates=[dict(name=n, pass_=ok, note=note) for n, ok, note in GATES],
        correction_1="linkstats v/c<=1 是结构性质；v/c=1 表示饱和+排队，不是容量富余",
        correction_2="qsim.timeStepSize=1s ⇒ TT=ceil(FF)；TT/FF 口径被量化污染，须扣 ceil(FF)/FF",
        time_step_size=r2b["tstep"],
        quantization=dict(
            pure_links_pct=100 * r2b["pure_link"], pure_volume_pct=100 * r2b["pure_vol"],
            hour_control={r.hour: dict(n_links=int(r.n_links), vol=float(r.vol),
                                       ratio=float(r.ratio_vw), q=float(r.qratio_vw),
                                       excess=float(r.excess_vw),
                                       delay_raw_h=float(r.delay_raw_h),
                                       delay_corr_h=float(r.delay_corr_h)) for _, r in hr.iterrows()},
            corridor={r.corridor: dict(length_km=float(r.length_km), ratio=float(r.ratio_vw),
                                       q=float(r.qratio_vw), excess=float(r.excess_vw),
                                       delay_corr_h=float(r.delay_corr_h)) for _, r in crdf.iterrows()},
            roadtype={r.road_type: dict(n_loaded=int(r.n_loaded), ratio=float(r.ratio_vw),
                                        q=float(r.qratio_vw), excess=float(r.excess_vw),
                                        delay_corr_h=float(r.delay_corr_h),
                                        delay_corr_pct=float(r.delay_corr_pct)) for _, r in byrt.iterrows()},
            total_real_delay_corr_h=tot_corr_h),
        e1_utilization_pct={k: v["util_pct"] for k, v in s.items()},
        e2_corridor_ratio_raw={r.key: float(r.ratio_vw) for _, r in cor.iterrows()},
        e3=r3,
        e4=dict(peak_in_network=r4["peak"], peak_time=r4["peak_time"],
                peak_share_pct=100 * r4["peak"] / 236044,
                peak_network_vc=float(f.agg_vc.max()),
                peak_network_ratio=float(f.net_ratio.max()),
                peak_network_excess=float(f.net_excess.max()),
                crosscheck_max_rel_diff_pct=float(r4["cdf"].rel_diff_pct.abs().max())),
        saturated_links=dict(n=len(satc), total_km=float(satc.length_m.sum() / 1000),
                             service=int(svc_sat), cte=int(cte_sat), cte_chain_km=cte_sat_km),
        no_demand_inflation=True, frozen_version="Singapore_OD_MATSim_Final_v1.0",
    )
    json.dump(summary, open(OUT / "audit_summary.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=2, default=str)

    A("")
    A("=" * 80)
    A("GATES: %d/%d PASS" % (npass, len(GATES)))
    for n, ok, note in GATES:
        if not ok:
            A("  !! FAILED: %s  %s" % (n, note))
    A("VERDICT: CONGESTION_STATE_PLAUSIBILITY_AUDIT_COMPLETE")
    A("图: %s" % figp)
    A("=" * 80)


if __name__ == "__main__":
    main()
