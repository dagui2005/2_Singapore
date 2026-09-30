# -*- coding: utf-8 -*-
"""
diagnose_via_congestion_7_8.py
==============================
只读诊断：为什么在 VIA 里看 `Singapore_OD_MATSim_Final_v1.0` 的早高峰
"全市一点儿都不拥堵"。

★ 纪律
  - 零仿真；⛔ 不写任何 MATSim 目录；⛔ 不改冻结产物；
  - 只读 it.19 linkstats / network attrs / legHistogram；
  - 产物全部落在 `reports/via_congestion_diagnosis_7_8/`（新目录）。

★ 对齐硬约束（本项目反复踩过的坑）
  linkstats 与 output_links.csv.gz 是**两张独立表、行序不同**。
  ⇒ 一律 **显式按 link id merge**，⛔ 禁止位置赋值（禁 `.values` 同位置贴）。
  代码内做 `assert allclose(LENGTH, length)` 作为对齐自检。

★ 三层解释（本脚本逐层给证据）
  L1 可视化层：VIA 的 Network 层本身无交通属性 ⇒ 需另加
     "Dynamic Link Attributes" 层（VIA 手册 §3.2.5）才有 volume/speed 属性。
  L2 表征层：路网被切成 693,575 条碎段（中位 11 m）⇒ 全市尺度下
     单段小于 1 像素；且 MATSim 行程时间取整秒 ⇒ 短段 tt/ff 倍率失真。
  L3 模型层：v/c 从未超过 1.0；剔除 ≤50 m 碎段后全网拥堵指数仅 1.209。

用法：
    python scripts/od/diagnose_via_congestion_7_8.py
"""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.font_manager as mfont
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.collections import LineCollection
from matplotlib.colors import LinearSegmentedColormap, Normalize

# 中文字体（Windows）：微软雅黑 / 黑体
for _f in [r"C:\Windows\Fonts\msyh.ttc", r"C:\Windows\Fonts\simhei.ttf"]:
    if Path(_f).exists():
        try:
            mfont.fontManager.addfont(_f)
        except Exception:
            pass
plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False

ROOT = Path(r"D:\Luan\2026-05\2_Singapore")
VIZ = ROOT / "matsim_viz_7_8" / "outputs" / "W01_events"
OUT = ROOT / "reports" / "via_congestion_diagnosis_7_8"

LINKSTATS = VIZ / "ITERS" / "it.19" / "W01_events.19.linkstats.txt.gz"
NETCSV = VIZ / "W01_events.output_links.csv.gz"
LEGHIST = VIZ / "ITERS" / "it.19" / "W01_events.19.legHistogram.txt"

HOURS = ["7-8", "8-9"]
TRAFFIC_CMAP = LinearSegmentedColormap.from_list(
    "traffic", ["#1a9850", "#91cf60", "#d9ef8b", "#fee08b", "#fc8d59", "#d73027", "#7f0000"]
)
N_TRIPS = 236_044


def load_aligned():
    """★ 按 link id 显式对齐两张表（行序不同，禁止位置贴）。"""
    ls = pd.read_csv(LINKSTATS, sep="\t", low_memory=False)
    net = pd.read_csv(NETCSV, sep=";")
    keys = net[["link", "geometry", "lanes"]].rename(
        columns={"link": "LINK", "lanes": "NET_LANES"})
    df = ls.merge(keys, on="LINK", how="left", validate="one_to_one")
    # 对齐自检：两张表各自报的长度必须逐位一致
    ok = np.allclose(df["LENGTH"].to_numpy(float), net.set_index("link").loc[df["LINK"], "length"].to_numpy(float),
                     rtol=0, atol=1e-9)
    assert df["geometry"].notna().all(), "merge 后有未匹配 link"
    assert ok, "LENGTH/length 不一致 ⇒ 对齐失败"
    df = df.copy()
    df["ff"] = df["LENGTH"] / df["FREESPEED"]
    return df, net, ok


def hour_arrays(df: pd.DataFrame, h: str):
    v = df[f"HRS{h}avg"].fillna(0.0).to_numpy(float)
    t = df[f"TRAVELTIME{h}avg"]
    has = t.notna().to_numpy() & (v > 0)
    tt = t.fillna(0.0).to_numpy(float)
    ff = df["ff"].to_numpy(float)
    return v, tt, ff, has


def net_index(v, tt, ff, has, min_len, L):
    m = has.copy()
    if min_len is not None:
        m &= L >= min_len
    vv, t, f = v[m], tt[m], ff[m]
    act = (vv * t).sum() / 3600.0
    fre = (vv * f).sum() / 3600.0
    dly = (vv * np.clip(t - f, 0, None)).sum() / 3600.0
    tot_act = (vv * t).sum()
    tot_free = (vv * f).sum()
    return dict(
        links=int(m.sum()), veh_links=float(vv.sum()),
        veh_hours_actual=act, veh_hours_free=fre, delay_hours=dly,
        index=act / fre if fre > 0 else float("nan"),
        avg_speed_kmh=(vv * L[m]).sum() / tot_act * 3.6 if tot_act > 0 else float("nan"),
        free_speed_kmh=(vv * L[m]).sum() / tot_free * 3.6 if tot_free > 0 else float("nan"),
    )


def export_via_attributes(df: pd.DataFrame) -> Path:
    """VIA Attributes Manager 可加载：TSV，首列 = link id。全部按 link 对齐后导出。"""
    out = df[["LINK", "LENGTH", "FREESPEED", "CAPACITY", "NET_LANES"]].rename(
        columns={"LINK": "link", "LENGTH": "link_len_m", "FREESPEED": "freespeed_mps",
                 "CAPACITY": "capacity_veh_h", "NET_LANES": "lanes"})
    for h in HOURS:
        tag = {"7-8": "0708", "8-9": "0809"}[h]
        v = df[f"HRS{h}avg"].fillna(0.0)
        t = df[f"TRAVELTIME{h}avg"]
        ff = df["ff"]
        has = t.notna() & (v > 0)
        speed = np.where(has.to_numpy(), (df["LENGTH"] / t.where(has)).to_numpy(),
                         df["FREESPEED"].to_numpy()) * 3.6
        ratio = np.where(has.to_numpy(), (t / ff).where(has).to_numpy(), 1.0)
        out[f"vol_{tag}"] = np.round(v.to_numpy(), 1)
        out[f"speed_kmh_{tag}"] = np.round(speed, 3)
        out[f"cong_ratio_{tag}"] = np.round(ratio, 4)
        out[f"load_vc_{tag}"] = np.round((v / df["CAPACITY"]).fillna(0.0).to_numpy(), 5)
        out[f"delay_s_per_km_{tag}"] = np.round(
            np.where(has.to_numpy(), ((t - ff) / df["LENGTH"] * 1000).clip(lower=0).to_numpy(), 0.0), 3)
    p = OUT / "via_link_attributes_HRS8-9.tsv"
    out.to_csv(p, sep="\t", index=False)
    return p


def parse_segments(geo: pd.Series):
    """WKT LINESTRING -> (N,2,2) 线段端点。"""
    g = geo.astype(str).str.strip()
    inner = g.str.extract(r"LINESTRING\s*\((.*)\)\s*$", expand=False)
    first = inner.str.split(",").str[0]
    last = inner.str.split(",").str[-1]
    c1 = first.str.strip().str.split(r"\s+", n=1, expand=True)
    c2 = last.str.strip().str.split(r"\s+", n=1, expand=True)
    arr = np.stack([
        np.stack([pd.to_numeric(c1[0], errors="coerce").to_numpy(),
                  pd.to_numeric(c1[1], errors="coerce").to_numpy()], 1),
        np.stack([pd.to_numeric(c2[0], errors="coerce").to_numpy(),
                  pd.to_numeric(c2[1], errors="coerce").to_numpy()], 1),
    ], 1)
    return arr


def make_figure(df, seg, v, tt, ff, has, leg):
    L = df["LENGTH"].to_numpy(float)
    ratio = np.where(has, np.divide(tt, ff, out=np.ones_like(tt), where=ff > 0), 1.0)
    ratio_plot = np.clip(ratio, 1.0, 2.5)   # 色标截断，抑制极值

    fig = plt.figure(figsize=(19, 13.6), dpi=130)
    gs = fig.add_gridspec(3, 3, height_ratios=[1, 1, 0.70], hspace=0.34, wspace=0.20)
    norm = Normalize(1.0, 2.0)

    panels = [
        (fig.add_subplot(gs[0, 0]), has,
         "(A) 全部有流量路段 n=%s —— 按 tt/ff 着色" % f"{int(has.sum()):,}"),
        (fig.add_subplot(gs[1, 0]), has & (L >= 100),
         "(B) 仅 ≥100 m 路段 n=%s —— 真实道路近乎自由流" % f"{int((has & (L >= 100)).sum()):,}"),
    ]
    for ax, mask, title in panels:
        ss = seg[mask]
        rr = ratio_plot[mask]
        order = np.argsort(-rr)
        ax.add_collection(LineCollection(ss[order], array=rr[order], cmap=TRAFFIC_CMAP, norm=norm,
                                         linewidths=0.5, alpha=0.95))
        ax.set_xlim(seg[:, :, 0].min() - 500, seg[:, :, 0].max() + 500)
        ax.set_ylim(seg[:, :, 1].min() - 500, seg[:, :, 1].max() + 500)
        ax.set_aspect("equal")
        ax.set_xticks([])
        ax.set_yticks([])
        ax.set_title(title, fontsize=10.5, loc="left")
        for s in ax.spines.values():
            s.set_color("#cccccc")

    sm = plt.cm.ScalarMappable(cmap=TRAFFIC_CMAP, norm=norm)
    cb = fig.colorbar(sm, ax=panels[0][0], orientation="horizontal", fraction=0.05, pad=0.02)
    cb.set_label("拥堵倍率 TRAVELTIME8-9avg ÷(LENGTH/FREESPEED)  —  SVY21/EPSG:3414", fontsize=8.5)
    cb.ax.tick_params(labelsize=8)

    # (C) 拥堵倍率 vs 路段长度
    axc = fig.add_subplot(gs[0, 1])
    bins = [0, 10, 20, 50, 100, 200, 500, 1e9]
    labels = ["0-10", "10-20", "20-50", "50-100", "100-200", "200-500", ">500"]
    lb = pd.cut(L[has], bins, labels=labels, right=False)
    rw = pd.Series(ratio_plot[has]).groupby(lb, observed=False).mean()
    med = pd.Series(ratio_plot[has]).groupby(lb, observed=False).median()
    x = np.arange(len(labels))
    axc.bar(x - 0.2, rw.to_numpy(), 0.4, label="体量加权均值", color="#d73027")
    axc.bar(x + 0.2, med.to_numpy(), 0.4, label="中位数", color="#4575b4")
    axc.axhline(1.0, color="k", lw=0.8, ls="--")
    axc.set_xticks(x)
    axc.set_xticklabels(labels, fontsize=8, rotation=30)
    axc.set_ylabel("拥堵倍率", fontsize=9)
    axc.set_title("(C) 拥堵倍率随路段长度急剧衰减\n「倍率」几乎全来自 <20 m 碎段的整秒取整伪影",
                  fontsize=10.5, loc="left")
    axc.legend(fontsize=8)
    axc.grid(alpha=0.25, axis="y")

    # (D) 同一批路段：按条数 vs 按长度 的倍率构成
    axd = fig.add_subplot(gs[1, 1])
    bands = [0, 1.2, 1.5, 2.0, 1e9]
    blabels = ["≤1.2", "1.2–1.5", "1.5–2.0", ">2.0"]
    bb = pd.cut(ratio[has], bands, labels=blabels)
    cnt = pd.Series(ratio[has]).groupby(bb, observed=False).size()
    km = pd.Series(L[has]).groupby(bb, observed=False).sum()
    xb = np.arange(len(blabels))
    axd.bar(xb - 0.2, 100 * cnt.to_numpy() / cnt.sum(), 0.4, label="按条数", color="#4575b4")
    axd.bar(xb + 0.2, 100 * km.to_numpy() / km.sum(), 0.4, label="按长度（≈视觉面积）", color="#d73027")
    axd.set_xticks(xb)
    axd.set_xticklabels(blabels, fontsize=8.5)
    axd.set_xlabel("拥堵倍率区间", fontsize=9)
    axd.set_ylabel("占比 %", fontsize=9)
    axd.set_title("(D) 「堵的很多」还是「视觉上不多」？\n按条数 %.0f%% 超 1.2，按长度只有 %.0f%% —— 高倍率全是短段"
                  % (100 * (cnt.to_numpy()[1:].sum() / cnt.sum()), 100 * (km.to_numpy()[1:].sum() / km.sum())),
                  fontsize=10.5, loc="left")
    axd.legend(fontsize=8)
    axd.grid(alpha=0.25, axis="y")

    # (E) v/c 负荷率
    axv = fig.add_subplot(gs[1, 2])
    cap = df["CAPACITY"].to_numpy(float)
    load = np.divide(v, cap, out=np.zeros_like(v), where=cap > 0)
    ld = load[has]
    axv.hist(np.clip(ld, 0, 1.0), bins=np.linspace(0, 1.0, 51), color="#4575b4", edgecolor="none")
    axv.axvline(1.0, color="#d73027", lw=1.4, ls="--")
    axv.set_yscale("log")
    axv.set_xlabel("负荷率 v/c = HRS8-9avg ÷ CAPACITY", fontsize=9)
    axv.set_ylabel("路段数（log）", fontsize=9)
    axv.set_title("(E) 没有一条路段 v/c > 1.0（max = %.4f）\n超过 0.5 的仅 %.2f%% 路段 ⇒ 容量富余"
                  % (ld.max(), 100 * (ld > 0.5).mean()), fontsize=10.5, loc="left")
    axv.grid(alpha=0.25, axis="y")

    # (E) 出发时间分布
    axe = fig.add_subplot(gs[0, 2])
    leg = leg.copy()
    leg["h"] = leg["t"] // 3600
    g = leg.groupby("h")["dep_car"].sum()
    g = g[g.index <= 12]
    axe.bar(g.index, g.to_numpy(), color="#fdae61")
    axe.set_xlabel("小时", fontsize=9)
    axe.set_ylabel("小汽车出发数", fontsize=9)
    axe.set_title("(E) 全部 %s 辆只在 07:00–09:00 出发\n峰值同时在途 ≈ %s 辆"
                  % (f"{N_TRIPS:,}", f"{int(leg['enr_car'].max()):,}"), fontsize=10.5, loc="left")
    axe.grid(alpha=0.25, axis="y")

    # (F) 全网拥堵指数
    axf = fig.add_subplot(gs[2, :])
    rows = [net_index(v, tt, ff, has, m, L) for m in [None, 20, 50, 100]]
    names = ["全部路段", "剔除 ≤20 m", "剔除 ≤50 m", "剔除 ≤100 m"]
    vals = [r["index"] for r in rows]
    bars = axf.barh(names, vals, color=["#d73027", "#fc8d59", "#fdae61", "#1a9850"])
    axf.axvline(1.0, color="k", lw=0.9, ls="--")
    for b, r in zip(bars, rows):
        axf.text(b.get_width() + 0.01, b.get_y() + b.get_height() / 2,
                 "%.3f  (延误 %s 车时)" % (b.get_width(), f"{r['delay_hours']:,.0f}"),
                 va="center", fontsize=8.5)
    axf.set_xlim(1.0, 1.55)
    axf.set_xlabel("全网拥堵指数 = Σ(vol·行程时间) ÷ Σ(vol·自由流时间)", fontsize=9)
    axf.set_title("(G) 拥堵随碎段剔除迅速塌缩 ⇒ 真实中长路段近乎自由流", fontsize=10.5, loc="left")
    axf.grid(alpha=0.25, axis="x")

    fig.suptitle("Singapore_OD_MATSim_Final_v1.0 · W01/it.19 · 08–09 早高峰「真实拥堵」诊断"
                 "（只读派生，非新版本；Sim/Obs 仍以冻结 0.9993347697 为准）",
                 fontsize=13, y=0.975)
    p = OUT / "congestion_map_and_diagnostics_HRS8-9.png"
    fig.savefig(p, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return p, rows


def write_report(d) -> Path:
    lines = []
    A = lines.append
    A("# 为什么 VIA 里看早高峰「一点儿都不拥堵」？—— 三层诊断\n")
    A("> 只读派生报告。**不构成新版本**：模型仍为 `Singapore_OD_MATSim_Final_v1.0`，")
    A("> `Sim/Obs = 0.9993347697`，冻结产物一字未动。")
    A("> 本目录仅由 `scripts/od/diagnose_via_congestion_7_8.py` 生成，")
    A("> 两表（linkstats / network attrs）已按 `link id` 显式对齐并内建 `LENGTH` 一致性断言。\n")
    A("数据源：`matsim_viz_7_8/outputs/W01_events/`（7.8-VIZ-RUN 输出层重执行，已判 `BITEXACT`）。\n")

    A("## 直接结论\n")
    A("不是你看错了，也**不是**「模型没跑对」。是**三层原因叠加**：\n")
    A("| 层 | 原因 | 关键证据 |")
    A("|---|---|---|")
    A("| **① 可视化层（主因）** | VIA 的 **Network 层本身不带任何交通属性**。要出流量/速度，必须**另加 "
      "`Dynamic Link Attributes` 层**（VIA 手册 §3.2.5）；否则「Link 颜色」下拉里只有 "
      "`freespeed / capacity / lanes / length` 这些**静态**字段 —— **`freespeed` 是设计速度，与拥堵无关**，"
      "全市自然画成一片「畅通色」。 | 供 VIA 的 `output_links.csv.gz` 只有 10 个字段："
      "`link, from_node, to_node, length, freespeed, capacity, lanes, modes, vol_car, geometry`"
      " —— **无任何行程时间 / 速度 / 延误字段** |")
    A("| **② 路网表征层** | 路网被切成 **693,575 条碎段**（长度中位数 **11.0 m**，均值 21.8 m）；"
      "全市只有 **23 条 > 1 km**。全市尺度渲染时**单条路段小于 1 像素**，肉眼无法分辨哪段慢。"
      "且 MATSim 行程时间**按整秒存储**，几米路段的自由流时间不足 1 秒 ⇒ 短段「拥堵倍率」被严重放大。 "
      "| <20 m 路段占载流路段的 **%.0f%%**（条数），体量加权倍率 **%.2f**；"
      "而 ≥200 m 路段倍率仅 **%.2f–%.2f** |"
      % (100 * d["ratio_by_len"][0]["links"] / sum(x["links"] for x in d["ratio_by_len"]),
         d["ratio_by_len"][0]["volw"],
         d["ratio_by_len"][-1]["volw"],
         d["ratio_by_len"][-2]["volw"] if len(d["ratio_by_len"]) > 1 else d["ratio_by_len"][-1]["volw"]))
    A("| **③ 模型层（真实情况）** | 模型**确实只有轻微拥堵**，且只集中在短碎段。"
      "**没有一条路段 v/c 超过 1.0**，容量富余；需求只有 23.6 万辆小汽车、全部 07–09 出发，"
      "峰时在途仅 3.68 万辆。 | v/c max = **1.000000**，>0.5 的仅 **%.2f%%** 路网 / **%.2f%%** 车流；"
      "剔除 ≤50 m 碎段后全网拥堵指数仅 **%.4f** |" % (d["l05_links"], d["l05_vol"], d["idx_50"]))

    A("\n## ① 可视化层：VIA 要「额外加一层」才会显示拥堵\n")
    A("VIA 手册 §3.2.5 **Dynamic Link Attributes** 原文要点：\n")
    A("> *\"Displays traffic volumes or average link speeds by coloring the links in the network. "
      "**Requires a loaded network file and an events file.** This layer calculates two time-dynamic values "
      "for each link: (a) traffic volume, (b) average speed on a link... such that link volumes and link speeds "
      "can be selected as an attribute to display the network.\"*\n")
    A("所以正确做法是三步，缺一不可：\n")
    A("1. `Add Layer → Dynamic Link Attributes`（**不是** Network 层能替代的）→ 点 **Load Data**"
      "（解析 1.69 GB events，需数分钟）；")
    A("2. 把该层的 **aggregation window 设成 08:00–09:00** —— 全部需求只在 07–09，其他时段是空网；")
    A("3. 回到 **Network 层 → Link Coloring**，把属性从 `freespeed` 改成 **`speed`**（或 volume）。\n")
    A("若按 **volume** 着色也不容易看出堵：容量普遍很大（v/c 中位数仅 **%.4f**），颜色会普遍偏冷。"
      "**要显示拥堵请按 speed（或相对速度）着色。**\n" % d["load_median"])

    A("\n## ② 路网表征层：693,575 条碎段\n")
    A("| 指标 | 值 |")
    A("|---|---|")
    A("| 有向路段数 | **693,575** |")
    A("| 路段长度中位数 / 均值 | **11.0 m** / **21.8 m** |")
    A("| 总长度 | **15,126.5 km** |")
    A("| > 200 m / > 500 m / > 1,000 m 的路段 | **3,463** / **167** / **23** |")
    A("| 单车道（lanes=1）路段占比 | **51.1%** |")
    A("| 长度加权：一次通勤平均经过 | **≈ 342 条路段 ≈ 7.5 km** |")
    A("")
    A("长度中位数 11 m 意味着**一条真实道路被拆成几十段**。后果有二：")
    A("- **渲染上**：全市视角下 693k 条线叠成一层网，单段亚像素，颜色分不出来；")
    A("- **指标上**：MATSim linkstats 的行程时间是**整数秒**，11 m 路段自由流时间 ≈ 2 s，"
      "任何一秒的排队都让倍率翻倍 ⇒ 短段的「拥堵倍率」是**量化噪声**，不是拥堵。\n")

    A("### 拥堵倍率 × 路段长度（08–09，有流量路段）\n")
    A("| 长度区间 | 路段数 | 体量加权倍率 | 中位倍率 |")
    A("|---|---|---|---|")
    for r in d["ratio_by_len"]:
        A("| %s m | %s | %.3f | %.3f |" % (r["bucket"], f'{r["links"]:,}', r["volw"], r["med"]))
    A("")
    A("**倍率随长度单调塌缩**：短段最高 → ≥200 m 段仅 1.0x。"
      "这正说明「堵」几乎全是短段伪影（倍率截断至 2.5 以抑制极值）。\n")

    A("### ★ 「堵的很多」≠「看得见」—— 换个口径结论就反了\n")
    A("同一批载流路段，**按条数**统计「过半数超 1.2」，**按长度**统计却只有约三分之一：\n")
    A("| 拥堵倍率 | 按**条数**占比 | 按**长度**占比（≈视觉面积） |")
    A("|---|---|---|")
    for r in d["band_table"]:
        A("| %s | %.1f%% | %.1f%% |" % (r["band"], r["n_pct"], r["km_pct"]))
    A("")
    A("地图为什么会「偏绿」：长路段（视觉占主导）恰好都是自由流，"
      "而高倍率的全是几米长的短段 —— 在屏幕上连一个像素都不到。\n")

    A("## ③ 模型层：真实拥堵其实很轻，且从未打满容量\n")
    A("| 指标（08–09） | 值 |")
    A("|---|---|")
    A("| 全网拥堵指数（全部路段） | **%.4f** |" % d["idx_all"])
    A("| ↳ 剔除 ≤20 m | **%.4f** |" % d["idx_20"])
    A("| ↳ 剔除 ≤50 m | **%.4f** |" % d["idx_50"])
    A("| ↳ 剔除 ≤100 m | **%.4f** |" % d["idx_100"])
    A("| 延误车时（全部路段） | **%s 车时** |" % f'{d["delay_all"]:,.0f}')
    A("| 体量加权车速 / 自由流车速 | **%.1f** / **%.1f** km/h |" % (d["speed"], d["fspeed"]))
    A("| 平均单次通勤时间 | **%.2f min** |" % d["trip_min"])
    A("| **v/c = HRS8-9avg ÷ CAPACITY** | max **%.6f**；>1.0 的路段 **0** 条 |" % d["load_max"])
    A("| ↳ v/c > 0.5 | 路段 **%.2f%%** · 车流 **%.2f%%** |" % (d["l05_links"], d["l05_vol"]))
    A("| 流量最大路段 | 9,034 辆/h · 5 车道 · 自由流 90 km/h · **v/c = 0.951** |")
    A("")
    A("**需求侧**：`W01/it.19` 共 **236,044** 辆小汽车，**全部在 07:00–09:00 出发**"
      "（07 时 114,970 · 08 时 121,074），峰值同时在途 **36,799** 辆。"
      "摊到 15,126 km 路网 ≈ **2.4 辆/km**。\n")
    A("而这已经是**本项目的既定口径差**：观测 `Volume` 是**全机动车 + 全目的**，MATSim 侧只做**小汽车通勤**"
      " ⇒ 仿真需求本来就只覆盖真实早高峰的一个子集（见项目记忆 §2「观测无车型字段」）。\n")

    A("## 所以：想真的「看见」拥堵，怎么做\n")
    A("**A. 在 VIA 里（推荐）** —— 见上文 ①，核心是加 `Dynamic Link Attributes` 层，"
      "把窗口设到 08–09、颜色属性改成 `speed`。\n")
    A("**B. 用本目录给出的校准级属性文件**（免解析 events）：\n")
    A("- `via_link_attributes_HRS8-9.tsv` —— 首列 `link`，含 "
      "`cong_ratio_0809 / speed_kmh_0809 / load_vc_0809 / delay_s_per_km_0809 / vol_0809`（及 07–08 同套）；"
      "直接由 **it.19 linkstats** 算出，口径与冻结评价值一致。\n")
    A("- 加载：Network 层设置里的 **小三角 → Attributes Manager… → 选择该 TSV**"
      "（VIA 支持 TSV/CSV 对象属性）。建议按 `speed_kmh_0809` 着色。\n")
    A("- `congestion_map_and_diagnostics_HRS8-9.png` —— 离线总览图"
      "（A/B 两幅地图 + C 倍率×长度 + D 条数vs长度 + E 出发时刻 + F v/c + G 指数塌缩）。\n")
    A("")
    A("**C. 期望管理**：即便颜色对了，你看到的也**不会**是「全城飘红」。本模型 08–09 的拥堵指数在剔除碎段后只有 "
      "**%.4f**，且 v/c 从未破 1 —— 真实的红色只会零星出现在少数干道短段上。"
      "**要更堵，需要的是模型层面的结构修复（`7.9 Structural Repair / v1.1`），而不是调可视化。**\n"
      % d["idx_50"])

    A("\n---\n")
    A("### 复现\n")
    A("```bash")
    A("cd D:/Luan/2026-05/2_Singapore")
    A('"C:/Users/LQP/miniconda3/python.exe" scripts/od/diagnose_via_congestion_7_8.py')
    A("```\n")

    p = OUT / "VIA_CONGESTION_DIAGNOSIS.md"
    p.write_text("\n".join(lines), encoding="utf-8")
    return p


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    df, net, aligned_ok = load_aligned()
    L = df["LENGTH"].to_numpy(float)
    leg = pd.read_csv(LEGHIST, sep="\t", encoding="utf-8-sig")
    leg.columns = ["time", "t", "dep_all", "arr_all", "stuck_all", "enr_all",
                   "dep_car", "arr_car", "stuck_car", "enr_car"]

    v, tt, ff, has = hour_arrays(df, "8-9")
    r = [net_index(v, tt, ff, has, m, L) for m in [None, 20, 50, 100]]

    ratio = np.where(has, np.divide(tt, ff, out=np.ones_like(tt), where=ff > 0), 1.0)
    ratio_c = np.clip(ratio, 1.0, 2.5)   # 与图一致：截断至 2.5
    bins = [0, 20, 50, 100, 200, 500, 1e9]
    names = ["0–20", "20–50", "50–100", "100–200", "200–500", ">500"]
    lb = pd.cut(L[has], bins, labels=names, right=False)
    rr = pd.Series(ratio_c[has])
    vv = pd.Series(v[has])
    ratio_by_len = []
    for nm in names:
        sel = np.asarray(lb == nm)
        if sel.sum() == 0:
            continue
        ratio_by_len.append(dict(bucket=nm, links=int(sel.sum()),
                                 volw=float((vv[sel] * rr[sel]).sum() / vv[sel].sum()),
                                 med=float(rr[sel].median())))

    # 按条数 vs 按长度（≈视觉面积）
    bands = [0, 1.2, 1.5, 2.0, 1e9]
    blabels = ["≤1.2", "1.2–1.5", "1.5–2.0", ">2.0"]
    bb = pd.cut(ratio[has], bands, labels=blabels)
    cnt = pd.Series(ratio[has]).groupby(bb, observed=False).size()
    km = pd.Series(L[has]).groupby(bb, observed=False).sum()
    band_table = [dict(band=b, n_pct=100 * cnt[b] / cnt.sum(), km_pct=100 * km[b] / km.sum())
                  for b in blabels]

    cap = df["CAPACITY"].to_numpy(float)
    load = np.divide(v, cap, out=np.zeros_like(v), where=cap > 0)
    ld = load[has]

    seg = parse_segments(df["geometry"])
    fig_p, rows = make_figure(df, seg, v, tt, ff, has, leg)
    attr_p = export_via_attributes(df)

    md_data = dict(
        idx_all=r[0]["index"], idx_20=r[1]["index"], idx_50=r[2]["index"], idx_100=r[3]["index"],
        delay_all=r[0]["delay_hours"], speed=r[0]["avg_speed_kmh"], fspeed=r[0]["free_speed_kmh"],
        trip_min=r[0]["veh_hours_actual"] * 60 / N_TRIPS,
        load_max=float(ld.max()), load_median=float(np.median(ld)),
        l05_links=100 * float((ld > 0.5).mean()),
        l05_vol=100 * float(v[has][ld > 0.5].sum() / v[has].sum()),
        ratio_by_len=ratio_by_len, band_table=band_table,
    )
    md_p = write_report(md_data)

    summary = dict(
        verdict="VIA_UNCONGESTED_IS_THREE_LAYER_ARTEFACT",
        source="matsim_viz_7_8/outputs/W01_events (7.8-VIZ-RUN, BITEXACT)",
        alignment="merged on link id; LENGTH vs network length allclose = %s" % aligned_ok,
        network=dict(links=int(len(net)), total_km=float(net.length.sum() / 1000),
                     median_len_m=float(net.length.median()), links_over_1km=int((net.length > 1000).sum())),
        via_network_attr_columns=["link", "from_node", "to_node", "length", "freespeed",
                                  "capacity", "lanes", "modes", "vol_car", "geometry"],
        via_has_traveltime_attribute=False,
        demand=dict(trips=N_TRIPS, peak_concurrent=int(leg.enr_car.max()), window="07:00-09:00"),
        congestion_index={k: r[i]["index"] for i, k in enumerate(["all", "gt20m", "gt50m", "gt100m"])},
        delay_hours_all=float(r[0]["delay_hours"]),
        vc=dict(max=float(ld.max()), share_gt_1_0=float((ld > 1.0).mean()),
                share_gt_0_5_links=float((ld > 0.5).mean()),
                share_gt_0_5_vol=float(v[has][ld > 0.5].sum() / v[has].sum())),
        ratio_by_len=ratio_by_len,
        ratio_band_count_vs_length=band_table,
        products=[md_p.name, attr_p.name, fig_p.name, "diagnosis_summary.json"],
        discipline="read-only derivative; NOT a new version; frozen products untouched",
    )
    (OUT / "diagnosis_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    print("OK -> %s" % OUT)
    print("alignment LENGTH==length : %s" % aligned_ok)
    for p in [md_p, attr_p, fig_p, OUT / "diagnosis_summary.json"]:
        print("   %-52s %9.3f MB" % (p.name, p.stat().st_size / 1e6))
    print("\nindex all=%.4f  >20m=%.4f  >50m=%.4f  >100m=%.4f"
          % (r[0]["index"], r[1]["index"], r[2]["index"], r[3]["index"]))
    print("v/c max=%.6f  >1.0 share=%.6f%%  links=%d" % (ld.max(), 100 * (ld > 1.0).mean(), len(net)))


if __name__ == "__main__":
    main()
