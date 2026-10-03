#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""
ecap01_static_figs.py — E-CAP-01 结果静态图集（只读；不改任何冻结件）

定位：`EXPERIMENT ONLY / NOT v1.1 / NOT BASELINE / NOT CALIBRATED / NOT CONCLUSION`
—— 本脚本**只读取** E-CAP-01 的运行产物与 v1.0 冻结产物，生成静态图，用于演示/汇报。

与既有 fig1–fig3 的关系（**不重复**）：
  fig1 = 1 km 网格负荷对照（v1.0 vs E-CAP-01，聚合口径，对比）
  fig2 = LTA 实测观测（现实参照）
  fig3 = 倍率柱（相对现状）
⇒ 本图集补 **E-CAP-01 自身的绝对态**（逐链 v/c · 流量 · 延误）、**分布**、**时间演化**与**走廊排序**。

图（落 `experiments/E-CAP-01_scale_capacity/figures/`）：
  fig4_vc_map_ecap.png              —— 早高峰 08–09 链路 v/c（全网绝对态 + 近/超饱和明细 2 面板）
  fig5_flow_map_ecap.png            —— 早高峰 08–09 链路流量（veh/h，对数色标）
  fig6_delay_map_ecap.png           —— 早高峰 08–09 链路延误（excess s ≥ 3，剔除量化残差）
  fig7_vc_distribution_v10_vs_ecap.png —— 链路 v/c 分布对照（v1.0 vs E-CAP-01；直方 + 累计）
  fig8_network_timeseries_ecap.png  —— 全网逐小时流量曲线 + 出行时间线（出发/到达/在途）
  fig9_top_corridors_ecap.png       —— Top 拥堵走廊（具名道路，按 车·小时延误 排序）
  fig10_congestion_status_map_ecap.png —— ★早高峰拥堵态势图（单张自包含：v/c 五级着色 + Top 8 走廊标注 + 分级里程构成）

口径纪律（照抄 A1 冻结评价器，⛔ 不改）：
  · v/c = HRS8-9avg / (CAPACITY × cap_mul)；cap_mul：v1.0 = 1.0，E-CAP-01 = 1/SCALE = 0.434977
  · 延误 excess = TRAVELTIME8-9avg − ceil(自由流时间)   ← 量化消除（7.7E 根因）
  · 车·小时延误 = Σ h89 × excess / 3600
  · ⛔ 不用 speed_ratio 红绿图作主图（短链量化伪影）
  · ⛔ TT/速度/延误不乘 SCALE；流量比较口径才用 Q_full = Q_sim × SCALE

用法：python scripts/experiments/ecap01_static_figs.py
"""
from __future__ import annotations

import csv
import gzip
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

ROOT = Path(r"D:\Luan\2026-05\2_Singapore")
sys.path.insert(0, str(ROOT / "scripts" / "od"))

import audit_sampling_capacity_7_9a1 as A1  # noqa: E402

ECAP = ROOT / "experiments" / "E-CAP-01_scale_capacity"
FIGS = ECAP / "figures"
ECAP_OUT = ECAP / "outputs" / "E-CAP-01"
ECAP_LS19 = ECAP_OUT / "ITERS" / "it.19" / "E-CAP-01.19.linkstats.txt.gz"
ECAP_LH19 = ECAP_OUT / "ITERS" / "it.19" / "E-CAP-01.19.legHistogram.txt"

F_CAP = A1.F_CAP          # 0.434977
FIGS.mkdir(parents=True, exist_ok=True)

X0, X1, Y0, Y1 = 2000.0, 52000.0, 21000.0, 51500.0


def setup_mpl():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.font_manager as mfont
    import matplotlib.pyplot as plt
    for f in [r"C:\Windows\Fonts\msyh.ttc", r"C:\Windows\Fonts\simhei.ttf"]:
        if Path(f).exists():
            try:
                mfont.fontManager.addfont(f)
            except Exception:
                pass
    plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False
    return plt


def load_hourly_totals(p: Path) -> np.ndarray:
    """Σ over links of HRS{h}-{h+1}avg  —— 全网逐小时流量曲线（linkstats 头名解析）。"""
    tot = np.zeros(24)
    with gzip.open(p, "rt", encoding="utf-8", errors="replace") as fh:
        rd = csv.reader(fh, delimiter="\t")
        hdr = next(rd, None)
        if not hdr:
            return tot
        idx = {h: hdr.index(f"HRS{h}-{h + 1}avg") for h in range(24)
               if f"HRS{h}-{h + 1}avg" in hdr}
        for r in rd:
            for h, i in idx.items():
                if i < len(r):
                    try:
                        tot[h] += float(r[i])
                    except ValueError:
                        pass
    return tot


def build_segments(L: dict, labels: dict) -> tuple[list, dict]:
    nx = dict(zip(labels["node_ids"].tolist(), labels["node_x"].tolist()))
    ny = dict(zip(labels["node_ids"].tolist(), labels["node_y"].tolist()))
    pos = {lid: i for i, lid in enumerate(labels["ids"])}
    segs, idx = [], {}
    for k, d in L.items():
        if d["h89"] <= 0:
            continue
        i = pos.get(k)
        if i is None:
            continue
        f_, t_ = labels["frm"][i], labels["to"][i]
        if f_ not in nx or t_ not in nx or f_ not in ny or t_ not in ny:
            continue
        segs.append([(nx[f_], ny[f_]), (nx[t_], ny[t_])])
        idx[k] = len(segs) - 1
    return segs, idx


def target_scatter(labels, xw):
    nx = dict(zip(labels["node_ids"].tolist(), labels["node_x"].tolist()))
    ny = dict(zip(labels["node_ids"].tolist(), labels["node_y"].tolist()))
    pos = {lid: i for i, lid in enumerate(labels["ids"])}
    tgt = list(xw.loc[xw["is_primary_candidate"] == True, "matsim_link_id"].unique())[:5000]  # noqa: E712
    tx = [nx[labels["frm"][pos[k]]] for k in tgt if k in pos and labels["frm"][pos[k]] in nx]
    ty = [ny[labels["frm"][pos[k]]] for k in tgt if k in pos and labels["frm"][pos[k]] in ny]
    return tx, ty


def _decorate(ax, title, note, legend_loc="upper left"):
    ax.set_xlim(X0, X1)
    ax.set_ylim(Y0, Y1)
    ax.set_aspect("equal")
    ax.set_xlabel("EPSG:3414 (m)", fontsize=9)
    ax.set_title(title, fontsize=11.5, loc="left")
    ax.text(0.99, 0.02, note, transform=ax.transAxes, ha="right", va="bottom",
            fontsize=8.2, color="#222222",
            bbox=dict(boxstyle="round", fc="white", ec="#bbbbbb", alpha=0.85))


def main() -> int:
    plt = setup_mpl()
    from matplotlib.collections import LineCollection
    from matplotlib.colors import BoundaryNorm, Normalize, LogNorm, LinearSegmentedColormap

    print("[load] labels / linkstats(v10, ecap) / crosswalk")
    labels = A1.load_net_labels()
    v10 = A1.load_linkstats(A1.V10_LS)
    ecap = A1.load_linkstats(ECAP_LS19)
    xw = A1.load_crosswalk_raw()
    tx, ty = target_scatter(labels, xw)

    segs, idx = build_segments(ecap, labels)
    n_seg = len(segs)
    name_of = {}
    hw_of = {}
    pos = {lid: i for i, lid in enumerate(labels["ids"])}
    for k in idx:
        i = pos.get(k)
        if i is not None:
            name_of[k] = str(labels["name"][i]).strip()
            hw_of[k] = str(labels["highway"][i])
    print(f"    loaded links (h89>0) = {n_seg}")

    def vals_by_link(fn):
        v = np.full(n_seg, np.nan)
        for k, j in idx.items():
            v[j] = fn(ecap[k])
        return v

    ff_ceil = lambda d: A1.ceil_ff(d["length"] / d["fs"] if d["fs"] > 0 else 0.0)
    vc = vals_by_link(lambda d: d["h89"] / (d["cap"] * F_CAP) if d["cap"] > 0 else np.nan)
    flow = vals_by_link(lambda d: d["h89"])
    excess = vals_by_link(lambda d: max(d["tt89"] - ff_ceil(d), 0.0))
    delayvh = vals_by_link(lambda d: d["h89"] * max(d["tt89"] - ff_ceil(d), 0.0) / 3600.0)

    # ---------------- Fig 4：v/c（全网绝对态 + 近/超饱和明细） ----------------
    print("[fig4] E-CAP-01 v/c map (2 panels)")
    bins = [0, 0.3, 0.5, 0.7, 0.85, 1.0, 1.3, 2.0, 1e9]
    cols = ["#1a9850", "#66bd63", "#a6d96a", "#d9ef8b", "#fee08b", "#f46d43", "#d73027", "#7f0000"]
    cmap_vc = LinearSegmentedColormap.from_list("vc", cols, N=len(cols))
    norm_vc = BoundaryNorm(bins, cmap_vc.N)
    fig, axes = plt.subplots(1, 2, figsize=(22, 10.8))
    vcf = np.nan_to_num(vc, nan=0.0)
    lc = LineCollection(segs, cmap=cmap_vc, norm=norm_vc, linewidths=0.65)
    lc.set_array(vcf)
    axes[0].add_collection(lc)
    axes[0].scatter(tx, ty, s=0.4, c="#333333", alpha=0.20, marker=".", zorder=3)
    n_sat = int(np.nansum(vc >= 1.0))
    n_loaded = int(np.sum(~np.isnan(vc)))
    _decorate(axes[0], "(a) 全网绝对态：全部有流量路段",
              "线 = MATSim 有向路段\nv/c = 流量 ÷ (CAPACITY × 1/SCALE)\n灰点 = 7.3.6A 靶场链")
    axes[0].text(0.01, 0.98, f"有流量路段 {n_loaded:,} 条\n其中 v/c ≥ 1.0 共 {n_sat:,} 条 ({n_sat / n_loaded:.2%})",
                 transform=axes[0].transAxes, ha="left", va="top", fontsize=10, color="#111111",
                 bbox=dict(boxstyle="round", fc="#fffbe6", ec="#d4a017", alpha=0.95))

    # (b) 仅 v/c ≥ 0.85 明细（色标 0.85–2.0）；全网作灰色底图作空间参照
    m2 = np.nan_to_num(vc, nan=0.0) >= 0.85
    segs2 = [s for s, ok in zip(segs, m2) if ok]
    vc2 = np.nan_to_num(vc, nan=0.0)[m2]
    n2 = len(segs2)
    cols2 = ["#fee08b", "#f46d43", "#d73027", "#7f0000"]
    cmap2 = LinearSegmentedColormap.from_list("vc2", cols2, N=len(cols2))
    norm2 = BoundaryNorm([0.85, 1.0, 1.3, 2.0, 1e9], cmap2.N)
    lcb = LineCollection(segs, colors="#d9d9d9", linewidths=0.4, zorder=1)
    axes[1].add_collection(lcb)
    if segs2:
        lc2 = LineCollection(segs2, cmap=cmap2, norm=norm2, linewidths=1.8, zorder=2)
        lc2.set_array(vc2)
        axes[1].add_collection(lc2)
    axes[1].scatter(tx, ty, s=0.4, c="#999999", alpha=0.25, marker=".", zorder=3)
    _decorate(axes[1], "(b) 明细：仅 v/c ≥ 0.85 的路段（拥堵集中在哪里）",
              "灰 = 全网路网底图（空间参照）\n色标放大到 0.85–2.0；黄→深红 = 接近/超过饱和")
    axes[1].text(0.01, 0.98, f"v/c ≥ 0.85 共 {n2:,} 条\n占全部有流量路段 {n2 / n_loaded:.2%}",
                 transform=axes[1].transAxes, ha="left", va="top", fontsize=10, color="#111111",
                 bbox=dict(boxstyle="round", fc="#fffbe6", ec="#d4a017", alpha=0.95))
    sm = plt.cm.ScalarMappable(cmap=cmap_vc, norm=norm_vc)
    sm.set_array([])
    cb = fig.colorbar(sm, ax=axes[0], fraction=0.03, pad=0.02, ticks=[0, 0.3, 0.5, 0.7, 0.85, 1.0, 1.3, 2.0])
    cb.set_label("v/c，(a) 全网色标（左）", fontsize=10)
    sm2 = plt.cm.ScalarMappable(cmap=cmap2, norm=norm2)
    sm2.set_array([])
    cb2 = fig.colorbar(sm2, ax=axes[1], fraction=0.03, pad=0.02, ticks=[0.85, 1.0, 1.3, 2.0])
    cb2.set_label("v/c，(b) 明细色标（右）", fontsize=10)
    fig.suptitle("E-CAP-01 尺度统一试验 · 早高峰 08–09 道路负荷 v/c（绝对量）\n"
                 "左：全网同尺度看总量（以绿为主，说明超饱和是少数）　右：放大看这少数在哪里（沿高速走廊集中）",
                 fontsize=15, y=0.995)
    p4 = FIGS / "fig4_vc_map_ecap.png"
    fig.savefig(p4, bbox_inches="tight", facecolor="white", dpi=140)
    plt.close(fig)
    print(f"   -> {p4}  | v/c>=1: {n_sat}  v/c>=0.85: {n2}  loaded: {n_loaded}")

    # ---------------- Fig 5：流量地图 ----------------
    print("[fig5] E-CAP-01 flow map")
    fv = np.nan_to_num(flow, nan=0.0)
    fpos = fv[fv > 0]
    vmax_f = float(np.percentile(fpos, 99)) if fpos.size else 1.0
    fig, ax = plt.subplots(figsize=(13, 12))
    lc = LineCollection(segs, cmap="YlOrRd", norm=LogNorm(vmin=1.0, vmax=max(vmax_f, 10.0)), linewidths=0.65)
    lc.set_array(np.clip(fv, 1.0, None))
    ax.add_collection(lc)
    ax.scatter(tx, ty, s=0.4, c="#333333", alpha=0.22, marker=".", zorder=3)
    _decorate(ax, "E-CAP-01 · 早高峰 08–09 路段流量（veh/h，对数色标）",
              "流量 = linkstats HRS8-9avg（采样规模 43.5%）\n灰点 = 7.3.6A 靶场链")
    cb = fig.colorbar(lc, ax=ax, fraction=0.03, pad=0.02)
    cb.set_label("流量 (veh/h，log)", fontsize=10)
    fig.suptitle(f"E-CAP-01 早高峰路段流量空间格局（最大 {fv.max():,.0f} veh/h；色标上限 = 99 分位 {vmax_f:,.0f}）",
                 fontsize=14, y=0.995)
    p5 = FIGS / "fig5_flow_map_ecap.png"
    fig.savefig(p5, bbox_inches="tight", facecolor="white", dpi=150)
    plt.close(fig)
    print("   ->", p5)

    # ---------------- Fig 6：延误地图 ----------------
    print("[fig6] E-CAP-01 delay map")
    ex = np.nan_to_num(excess, nan=0.0)
    EX_MIN = 3.0                     # 剔除 1–2 s 量化残差，保留可辨延误
    m = ex >= EX_MIN
    segs_c = [s for s, ok in zip(segs, m) if ok]
    ex_c = ex[m]
    # 延误重尾（p50=9.5s / p95≈171s / p99≈3037s）⇒ 必用对数色标，否则中位值全被压白
    vmax_e = max(float(np.percentile(ex_c, 99)), EX_MIN * 10) if ex_c.size else 30.0
    norm_e = LogNorm(vmin=EX_MIN, vmax=vmax_e)
    fig, ax = plt.subplots(figsize=(13, 12))
    if segs_c:
        lc = LineCollection(segs_c, cmap="YlOrRd", norm=norm_e, linewidths=1.3)
        lc.set_array(ex_c)
        ax.add_collection(lc)
    ax.scatter(tx, ty, s=0.4, c="#333333", alpha=0.18, marker=".", zorder=3)
    _decorate(ax, "E-CAP-01 · 早高峰 08–09 路段延误（仅显示延误 ≥ 3 s 的路段，对数色标）",
              "延误 = TT − ceil(自由流时间)，已消量化伪影\n"
              "剔除 1–2 s 量化残差；灰点 = 7.3.6A 靶场链")
    cb = fig.colorbar(lc, ax=ax, fraction=0.03, pad=0.02, ticks=[3, 10, 30, 100, 300, 1000, 3000]) if segs_c else None
    if cb is not None:
        cb.set_label("延误 (s，log)", fontsize=10)
    km_c = sum(ecap[k]["length"] for k, j in idx.items() if ex[j] >= EX_MIN) / 1000.0
    n_all_cong = int((ex > 0).sum())
    med = float(np.median(ex_c)) if ex_c.size else float("nan")
    p95 = float(np.percentile(ex_c, 95)) if ex_c.size else float("nan")
    fig.suptitle(f"E-CAP-01 拥堵空间位置（延误 ≥ 3 s 共 {int(m.sum()):,} 条链 · 合计 {km_c:,.1f} km · "
                 f"中位 {med:.1f} s / p95 {p95:.0f} s / 最大 {ex_c.max():.0f} s）\n"
                 f"全部拥堵链（excess>0）{n_all_cong:,} 条；色标上限 = 99 分位 {vmax_e:,.0f} s（对数）",
                 fontsize=13.5, y=0.995)
    p6 = FIGS / "fig6_delay_map_ecap.png"
    fig.savefig(p6, bbox_inches="tight", facecolor="white", dpi=150)
    plt.close(fig)
    print("   ->", p6)

    # ---------------- Fig 7：v/c 分布对照 ----------------
    print("[fig7] v/c distribution")
    vc10 = np.array([d["h89"] / d["cap"] for d in v10.values() if d["h89"] > 0 and d["cap"] > 0])
    vc01 = np.array([d["h89"] / (d["cap"] * F_CAP) for d in ecap.values() if d["h89"] > 0 and d["cap"] > 0])
    c10 = int((vc10 >= 1.0).sum())
    c01 = int((vc01 >= 1.0).sum())
    fig, axes = plt.subplots(1, 2, figsize=(15, 6))
    b = np.linspace(0, 2.0, 81)
    axes[0].hist(np.clip(vc10, 0, 2), bins=b, density=True, alpha=0.55, color="#2e86c1", label=f"现状 v1.0（容量 100%，n={vc10.size:,}）")
    axes[0].hist(np.clip(vc01, 0, 2), bins=b, density=True, alpha=0.55, color="#c0392b", label=f"E-CAP-01（容量 43.5%，n={vc01.size:,}）")
    axes[0].axvline(1.0, color="#555555", ls="--", lw=1.2)
    axes[0].set_xlabel("v/c（截断于 2.0）", fontsize=10.5)
    axes[0].set_ylabel("密度", fontsize=10.5)
    axes[0].set_title("链路 v/c 分布（有流量路段）", fontsize=12, loc="left")
    axes[0].legend(fontsize=9.5)
    axes[0].grid(ls=":", alpha=0.5)

    def cdf(a):
        xs = np.sort(a)
        ys = np.arange(1, xs.size + 1) / xs.size
        return xs, ys
    for a, c, lab in [(vc10, "#2e86c1", "v1.0"), (vc01, "#c0392b", "E-CAP-01")]:
        xs, ys = cdf(a)
        axes[1].plot(xs, ys, color=c, lw=2, label=f"{lab}（n={a.size:,}）")
    axes[1].axvline(1.0, color="#555555", ls="--", lw=1.2)
    axes[1].set_xlim(0, 2.0)
    axes[1].set_ylim(0, 1.0)
    axes[1].set_xlabel("v/c", fontsize=10.5)
    axes[1].set_ylabel("累计占比", fontsize=10.5)
    axes[1].set_title("v/c 累计分布（曲线越靠右下 = 越拥堵）", fontsize=12, loc="left")
    axes[1].legend(fontsize=9.5)
    axes[1].grid(ls=":", alpha=0.5)
    fig.suptitle(f"需求—容量尺度统一的直接后果：饱和路段（v/c≥1.0）{c10:,} → {c01:,} 条（×{c01 / max(c10, 1):.2f}）\n"
                 "左：分布右移；右：累计曲线整体右移 = 全网负荷水平抬升", fontsize=13.5, y=0.99)
    fig.text(0.5, -0.03, "注：v/c 分母 = CAPACITY × cap_mul（v1.0 为 1.0，E-CAP-01 为 1/SCALE = 0.434977）；"
                         "仅统计 08–09 有流量路段；两版「有流量路段」集合不全等，故占比基数略有差异。"
                         "E-CAP-01 为旁路演示，非 v1.1、非正式基线。",
             ha="center", fontsize=9, color="#555555")
    p7 = FIGS / "fig7_vc_distribution_v10_vs_ecap.png"
    fig.savefig(p7, bbox_inches="tight", facecolor="white", dpi=150)
    plt.close(fig)
    print(f"   -> {p7}  | n(v/c>=1): {c10} -> {c01}")

    # ---------------- Fig 8：时间序列 ----------------
    print("[fig8] network time series")
    h10 = load_hourly_totals(A1.V10_LS)
    h01 = load_hourly_totals(ECAP_LS19)
    lh = A1.load_leg_hist(ECAP_LH19)
    fig, axes = plt.subplots(1, 2, figsize=(15.5, 5.6))
    hrs = np.arange(24)
    axes[0].plot(hrs, h10 / 1e6, "-o", ms=3.2, color="#2e86c1", lw=1.8, label="现状 v1.0")
    axes[0].plot(hrs, h01 / 1e6, "-o", ms=3.2, color="#c0392b", lw=1.8, label="E-CAP-01")
    axes[0].axvspan(8, 9, color="#f9e79f", alpha=0.55, zorder=0, label="早高峰 08–09")
    axes[0].set_xlabel("小时", fontsize=10.5)
    axes[0].set_ylabel("全网路段流量合计 (百万 veh·段/h)", fontsize=10.5)
    axes[0].set_title("全网逐小时负荷曲线（Σ 链路 HRS{h} 流量）", fontsize=12, loc="left")
    axes[0].legend(fontsize=9.5)
    axes[0].grid(ls=":", alpha=0.5)
    axes[0].set_xticks(range(0, 24, 2))

    t = np.array([r["t"] for r in lh]) / 3600.0
    for key, c, lab in [("enroute", "#c0392b", "在途车辆（瞬时）"),
                        ("dep", "#2e86c1", "出发（每 5 分钟）"),
                        ("arr", "#27ae60", "到达（每 5 分钟）")]:
        y = np.array([r[key] for r in lh], dtype=float)
        axes[1].plot(t, y, color=c, lw=1.8, label=lab)
    axes[1].axvline(8, color="#999999", ls=":", lw=1)
    axes[1].axvline(9, color="#999999", ls=":", lw=1)
    axes[1].set_xlabel("时刻 (h)", fontsize=10.5)
    axes[1].set_ylabel("车辆数", fontsize=10.5)
    axes[1].set_title("E-CAP-01 出行时间线（出发 / 到达 / 在途）", fontsize=12, loc="left")
    axes[1].legend(fontsize=9.5)
    axes[1].grid(ls=":", alpha=0.5)
    axes[1].set_xlim(0, 24)
    sum_dep = sum(r["dep"] for r in lh)
    sum_arr = sum(r["arr"] for r in lh)
    max_stuck = max(int(r["stuck"]) for r in lh)
    max_enr = max(int(r["enroute"]) for r in lh)
    fig.suptitle(f"E-CAP-01 时间面：全网流量曲线与出行过程（Σ出发={sum_dep:,} · Σ到达={sum_arr:,} · 峰值在途={max_enr:,} · 最大滞留={max_stuck}）",
                 fontsize=13.5, y=0.995)
    p8 = FIGS / "fig8_network_timeseries_ecap.png"
    fig.savefig(p8, bbox_inches="tight", facecolor="white", dpi=150)
    plt.close(fig)
    print(f"   -> {p8}  | sum_dep={sum_dep} sum_arr={sum_arr} max_enroute={max_enr} max_stuck={max_stuck}")

    # ---------------- Fig 9：Top 拥堵走廊（仅具名道路） ----------------
    print("[fig9] top congested corridors (named roads only)")
    agg = defaultdict(lambda: {"vh": 0.0, "flow": 0.0, "km": 0.0, "n": 0})
    vh_unnamed = 0.0
    vh_total = 0.0
    for k, j in idx.items():
        d = ecap[k]
        vh = delayvh[j]
        if not np.isfinite(vh) or vh <= 0:
            continue
        vh_total += vh
        nm = name_of.get(k) or ""
        if not nm:                     # ⛔ 无路名者不参与走廊排序（避免 service/_link 假合并）
            vh_unnamed += vh
            continue
        a = agg[nm]
        a["vh"] += vh
        a["flow"] += d["h89"]
        a["km"] += d["length"] / 1000.0
        a["n"] += 1
    top = sorted(((n, a) for n, a in agg.items() if a["km"] >= 1.0),
                 key=lambda kv: -kv[1]["vh"])[:15]
    n_drop_short = sum(1 for n, a in agg.items() if a["km"] < 1.0)
    names = [n for n, _ in top][::-1]
    vhs = [a["vh"] for _, a in top][::-1]
    fig, ax = plt.subplots(figsize=(12.5, 8))
    ypos = np.arange(len(names))
    bars = ax.barh(ypos, vhs, color="#c0392b", alpha=0.85)
    ax.set_yticks(ypos)
    ax.set_yticklabels(names, fontsize=10)
    ax.set_xlabel("早高峰 08–09 车·小时延误（veh·h）", fontsize=11)
    ax.set_title("E-CAP-01 · Top 15 拥堵走廊（具名道路 ≥ 1 km，按 车·小时延误 排序）", fontsize=13.5, loc="left")
    ax.grid(axis="x", ls=":", alpha=0.5)
    for b, (nm, a) in zip(bars, top[::-1]):
        ax.annotate(f"{a['vh']:,.0f} veh·h · {a['n']} 链 · {a['km']:.1f} km",
                    (b.get_width(), b.get_y() + b.get_height() / 2),
                    xytext=(4, 0), textcoords="offset points", va="center", fontsize=8.8)
    ax.set_xlim(0, max(vhs) * 1.35)
    fig.text(0.5, -0.02,
             f"注：车·小时延误 = Σ h89 × max(TT − ceil(自由流时间), 0) / 3600，按 MATSim 路段 RoadName 聚合。"
             f"「走廊」定义为具名道路且合计长度 ≥ 1 km（另剔除 {n_drop_short} 条同名短段，如巴士转换站内部道路）。"
             f"具名道路承担全部延误的 {100 * (vh_total - vh_unnamed) / max(vh_total, 1e-9):.1f}%（无路名路段 {vh_unnamed:,.0f} veh·h 不参与排序）。"
             f"E-CAP-01 为旁路演示，非 v1.1、非正式基线。",
             ha="center", fontsize=8.6, color="#555555")
    p9 = FIGS / "fig9_top_corridors_ecap.png"
    fig.savefig(p9, bbox_inches="tight", facecolor="white", dpi=150)
    plt.close(fig)
    print("   ->", p9)
    for nm, a in top[:8]:
        print(f"      {nm}: {a['vh']:.1f} veh·h, {a['n']} links, {a['km']:.2f} km")

    # ---------------- Fig 10：早高峰拥堵态势图（单张自包含） ----------------
    print("[fig10] morning-peak congestion status overview")
    nxd = dict(zip(labels["node_ids"].tolist(), labels["node_x"].tolist()))
    nyd = dict(zip(labels["node_ids"].tolist(), labels["node_y"].tolist()))
    midx = np.full(n_seg, np.nan)
    midy = np.full(n_seg, np.nan)
    for k, j in idx.items():
        i = pos.get(k)
        if i is None:
            continue
        f_, t_ = labels["frm"][i], labels["to"][i]
        if f_ in nxd and t_ in nxd and f_ in nyd and t_ in nyd:
            midx[j] = 0.5 * (nxd[f_] + nxd[t_])
            midy[j] = 0.5 * (nyd[f_] + nyd[t_])

    vcfull = np.nan_to_num(vc, nan=0.0)
    tiers_def = [
        ("畅通　v/c < 0.5", 0.0, 0.5, "#cfcfcf", 0.35),
        ("基本畅通　0.5 – 0.7", 0.5, 0.7, "#a6d96a", 0.95),
        ("接近饱和　0.7 – 0.85", 0.7, 0.85, "#fee08b", 1.15),
        ("饱和　0.85 – 1.0", 0.85, 1.0, "#f46d43", 1.5),
        ("超饱和　v/c ≥ 1.0", 1.0, 1e9, "#a50026", 2.2),
    ]
    tier_stats = []
    for lab_t, lo, hi, col, lw in tiers_def:
        mm = (vcfull >= lo) & (vcfull < hi)
        n_t = int(mm.sum())
        km_t = sum(ecap[k]["length"] for k, j in idx.items() if mm[j]) / 1000.0
        tier_stats.append({"label": lab_t, "n": n_t, "km": km_t, "color": col, "lw": lw,
                           "lo": lo, "hi": hi})
    tot_cap = sum(ecap[k]["cap"] * F_CAP for k in idx if ecap[k]["cap"] > 0)
    tot_flow = sum(ecap[k]["h89"] for k in idx)
    peak_vc = tot_flow / tot_cap if tot_cap else float("nan")
    km_loaded_all = sum(s["km"] for s in tier_stats)
    km_sat = tier_stats[4]["km"]
    n_sat = tier_stats[4]["n"]
    km_sat_plus = tier_stats[3]["km"] + tier_stats[4]["km"]
    n_sat_plus = tier_stats[3]["n"] + tier_stats[4]["n"]
    km_ge07 = tier_stats[2]["km"] + km_sat_plus
    n_ge07 = tier_stats[2]["n"] + n_sat_plus

    # 走廊短名
    ABBR = {"Pan-Island Expressway": "PIE", "Central Expressway": "CTE",
            "Ayer Rajah Expressway": "AYE", "Bukit Timah Expressway": "BKE",
            "Seletar Expressway": "SLE", "Tampines Expressway": "TPE",
            "East Coast Parkway": "ECP", "Kranji Expressway": "KJE",
            "Marina Coastal Expressway": "MCE", "Upper Serangoon Road": "Upper Serangoon Rd",
            "Yio Chu Kang Road": "Yio Chu Kang Rd", "Marymount Road": "Marymount Rd",
            "Upper Thomson Road": "Upper Thomson Rd", "Braddell Road": "Braddell Rd"}
    ord_labels = {n: r for r, (n, _) in enumerate(top[:8], 1)}
    # 各走廊「延误最大」路段位置（质心会全部落在市中心 ⇒ 标签重叠）
    best_pos = {}
    for k, j in idx.items():
        nmk = name_of.get(k) or ""
        if nmk not in ord_labels:
            continue
        w = delayvh[j]
        if not np.isfinite(w) or w <= 0 or not np.isfinite(midx[j]):
            continue
        cur = best_pos.get(nmk)
        if cur is None or w > cur[0]:
            best_pos[nmk] = (w, midx[j], midy[j])

    from matplotlib.gridspec import GridSpec
    from matplotlib.lines import Line2D
    fig = plt.figure(figsize=(19, 11))
    gs = GridSpec(1, 2, width_ratios=[3.4, 1.0], wspace=0.04, figure=fig)
    axm = fig.add_subplot(gs[0, 0])
    axb = fig.add_subplot(gs[0, 1])

    for st in tier_stats:
        mm = (vcfull >= st["lo"]) & (vcfull < st["hi"])
        segs_t = [s for s, ok in zip(segs, mm) if ok]
        if not segs_t:
            continue
        axm.add_collection(LineCollection(segs_t, colors=st["color"],
                                          linewidths=(0.30 if st["lo"] == 0.0 else st["lw"]),
                                          zorder=2 if st["lo"] > 0 else 1))
    axm.scatter(tx, ty, s=0.4, c="#888888", alpha=0.20, marker=".", zorder=3)
    axm.set_xlim(X0, X1)
    axm.set_ylim(Y0, Y1)
    axm.set_aspect("equal")
    axm.set_xlabel("EPSG:3414 (m)", fontsize=9.5)
    axm.set_title("E-CAP-01 路网拥堵态势（链路按 v/c 分级；浅灰 = 有流量路段底图）", fontsize=13, loc="left")

    # 走廊标注（落在各走廊延误最大的路段；沿「地图中心→该点」径向外推 + 贪心去重叠）
    CX, CY = 0.5 * (X0 + X1), 0.5 * (Y0 + Y1)
    placed: list[tuple[float, float]] = []
    for nmk, (w, x, y) in sorted(best_pos.items(), key=lambda kv: ord_labels[kv[0]]):
        r = ord_labels[nmk]
        vx, vy = x - CX, y - CY
        d = float(np.hypot(vx, vy)) or 1.0
        sc = max(0.16, 3200.0 / d)
        lx, ly = x + vx * sc, y + vy * sc
        for _ in range(30):                      # 贪心纵向错位，避免标签框重叠
            for px_, py_ in placed:
                if abs(lx - px_) < 3600.0 and abs(ly - py_) < 1400.0:
                    ly -= 1700.0
                    break
            else:
                break
        placed.append((lx, ly))
        axm.annotate(f"{r}. {ABBR.get(nmk, nmk)}", (x, y), xytext=(lx, ly),
                     textcoords="data", fontsize=10.5, fontweight="bold",
                     color="#7f0000", ha="center", va="center", zorder=7,
                     arrowprops=dict(arrowstyle="-", color="#c0392b", lw=1.2,
                                     shrinkA=2, shrinkB=2, connectionstyle="arc3,rad=0.0"),
                     bbox=dict(boxstyle="round,pad=0.32", fc="#fffbe6", ec="#c0392b", lw=1.1, alpha=0.97))

    handles = [Line2D([0], [0], color=st["color"], lw=max(st["lw"], 1.6)) for st in tier_stats]
    leg_labels = [f"{st['label']}　{st['n']:,} 链 / {st['km']:,.1f} km" for st in tier_stats]
    axm.legend(handles, leg_labels, loc="lower left", fontsize=9.5, framealpha=0.95,
               title="v/c 分级（分母 = CAPACITY × 1/SCALE）", title_fontsize=10)

    # 右：分级里程构成
    show = tier_stats[1:]
    yposb = np.arange(len(show))[::-1]
    axb.barh(yposb, [s["km"] for s in show], color=[s["color"] for s in show],
             edgecolor="#666666", lw=0.5, height=0.62)
    axb.set_yticks(yposb)
    axb.set_yticklabels([s["label"].split("　")[0] for s in show], fontsize=10.5)
    axb.set_xlabel("里程 (km)", fontsize=10.5)
    axb.set_xlim(0, max(s["km"] for s in show) * 1.55)
    axb.set_title("拥堵分级里程构成", fontsize=12, loc="left")
    axb.grid(axis="x", ls=":", alpha=0.5)
    for yb, s in zip(yposb, show):
        axb.annotate(f"{s['km']:,.1f} km\n{s['n']:,} 链（{s['km'] / km_loaded_all:.1%} 有流量里程）",
                     (s["km"], yb), xytext=(5, 0), textcoords="offset points",
                     va="center", fontsize=8.8)
    axb.text(0.5, -0.14,
             f"有流量里程合计 {km_loaded_all:,.0f} km\n（全网 {A1.NET_KM_FULL:,.0f} km）",
             transform=axb.transAxes, ha="center", va="top", fontsize=9, color="#444444")

    fig.suptitle(
        f"E-CAP-01 尺度统一试验 · 早高峰 08–09 路网拥堵态势\n"
        f"超饱和（v/c ≥ 1.0）：{n_sat:,} 链 / {km_sat:,.1f} km　|　"
        f"饱和及以上（≥0.85）：{n_sat_plus:,} 链 / {km_sat_plus:,.1f} km　|　"
        f"v/c ≥ 0.7：{n_ge07:,} 链 / {km_ge07:,.1f} km　|　全网负荷 Σ流量/Σ容量 = {peak_vc:.3f}",
        fontsize=14.5, y=0.995)
    fig.text(0.5, 0.012,
             "口径：v/c = HRS8-9avg ÷ (CAPACITY × 1/SCALE = 0.434977)；仅显示 08–09 有流量的 "
             f"{n_seg:,} 条有向路段；编号 = Top 8 拥堵走廊（按 车·小时延误，详见 fig9）。"
             "E-CAP-01 为旁路演示：EXPERIMENT ONLY / NOT v1.1 / NOT BASELINE / NOT CALIBRATED / NOT CONCLUSION。",
             ha="center", fontsize=9, color="#555555")
    p10 = FIGS / "fig10_congestion_status_map_ecap.png"
    fig.savefig(p10, bbox_inches="tight", facecolor="white", dpi=150)
    plt.close(fig)
    print(f"   -> {p10}  | sat {n_sat}/{km_sat:.2f}km  sat+ {n_sat_plus}/{km_sat_plus:.2f}km  ge0.7 {n_ge07}/{km_ge07:.2f}km  peak_vc={peak_vc:.4f}")

    print("[done]")
    return 0


if __name__ == "__main__":
    sys.exit(main())
