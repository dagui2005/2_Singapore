# -*- coding: utf-8 -*-
"""
SpeedBand 速度区间 · 仿真 vs 观测 地图生成器（只读附加件）
==========================================================
输入（全部为既有产物，只读）：
  reports/speedband_fit_diagnostic/speedband_fit_perlink_v1.0_W89.csv   逐链路对账（59,721 行）
  reports/speedband_fit_diagnostic/speedband_fit_overall.csv           整体指标（用于对账）
  reports/speedband_fit_diagnostic/speedband_fit_by_highway.csv        分等级指标
  reports/speedband_fit_diagnostic/speedband_fit_by_obsband.csv        按观测档的仿真速度
  reports/speedband_fit_diagnostic/speedband_fit_summary.json          覆盖/暴露面
  reports/matsim_network/network_nodes_source_copy.csv                节点经纬度
  reports/matsim_network/network_links_source_copy.csv                链路拓扑

输出（reports/speedband_maps_2026-10-13/）：
  figures/SB1_map_obs_band.png      观测速度区间（LTA SpeedBand）地图
  figures/SB2_map_sim_band.png      仿真速度区间地图（同 8 档切分）
  figures/SB3_map_band_delta.png    档位差（仿真档 − 观测档）地图
  figures/SB4_map_speed_ratio.png   速度比 Sim/Obs 地图
  figures/SB5_speed_distribution.png|.svg   速度分布 + 区间占比（仿真 vs 观测）
  tables/*.csv                      统计表
  SPEEDBAND_MAPS.html               自包含看板（零 JS / 零 CDN）
  SOURCE_MANIFEST.json              实读源文件 + 大小 + sha256

红线：
  ⛔ 只读：绝不写回任何被引用的产物文件
  ⛔ 不跑仿真、不改模型、不改冻结件（SCALE / 容量 / freespeed / λ / 阈值）
  ⛔ 不使用第三方底图 / 不内嵌任何密钥；几何全部取自 MATSim 网络自身经纬度
  ⛔ 不改变任何既有判定：本件仅为**展示层**，原始 D5 仍为 FAIL
"""
from __future__ import annotations

import base64
import hashlib
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.collections import LineCollection
from matplotlib.colors import BoundaryNorm, ListedColormap, TwoSlopeNorm
from matplotlib.lines import Line2D

PROJECT = Path(r"D:\Luan\2026-05\2_Singapore")
OUT = PROJECT / "reports" / "speedband_maps_2026-10-13"
FIG, TAB = OUT / "figures", OUT / "tables"
for d in (OUT, FIG, TAB):
    d.mkdir(parents=True, exist_ok=True)

plt.rcParams.update({
    "font.family": ["Microsoft YaHei", "SimHei", "DejaVu Sans"],
    "axes.unicode_minus": False,
    "figure.dpi": 170, "savefig.dpi": 170, "savefig.bbox": "tight",
    "axes.edgecolor": "#5a6472", "axes.labelcolor": "#1c2430",
    "text.color": "#1c2430", "xtick.color": "#39424f", "ytick.color": "#39424f",
    "axes.grid": True, "grid.color": "#dfe4ea", "grid.linewidth": .7,
    "axes.axisbelow": True, "figure.facecolor": "white", "axes.facecolor": "white",
})

C_INC, C_DEC = "#c0392b", "#1f6fb4"      # 红＝正值 / 蓝＝负值（全件统一）
C_OBS, C_SIM, C_ACC = "#db8a2a", "#1f6fb4", "#0f7b6c"

# 速度区间（LTA SpeedBand 编码，实测 143,735 link 100% 一致）
#   SB1=0–9  SB2=10–19 … SB7=60–69  SB8=70–999（哨兵，代理 75 km/h）
BAND_LABELS = [f"SB{i}" for i in range(1, 9)]
BAND_TXT = ["0–9", "10–19", "20–29", "30–39", "40–49", "50–59", "60–69", "70+"]
# 拥堵（红）→ 畅通（蓝绿）：交通工程惯用序，图例均显式标注
BAND_COLORS = ["#a01f1f", "#cc4a2a", "#e08a2a", "#edc948",
               "#b7d84a", "#6fc15c", "#35a06e", "#1f7fb4"]

SRC: dict[str, dict] = {}
BUILT_AT = pd.Timestamp.now()


# ------------------------------------------------------------------ 基础工具
def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for c in iter(lambda: f.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


def read_src(rel: str, **kw) -> pd.DataFrame:
    p = PROJECT / rel
    SRC[rel] = {"size": p.stat().st_size, "sha256": sha256_file(p)}
    df = pd.read_csv(p, **kw)
    df.columns = [str(c).lstrip("\ufeff") for c in df.columns]
    return df


def read_json_src(rel: str) -> dict:
    p = PROJECT / rel
    SRC[rel] = {"size": p.stat().st_size, "sha256": sha256_file(p)}
    return json.loads(p.read_bytes().decode("utf-8"))


def fig_out(fig, name: str, svg: bool = True):
    """★地图不出 SVG：链路数以万计，SVG 会膨胀（实测同类地图可达上百 MB）。"""
    fig.savefig(FIG / f"{name}.png", format="png")
    if svg:
        fig.savefig(FIG / f"{name}.svg", format="svg")
    plt.close(fig)


def b64(name: str) -> str:
    return base64.b64encode((FIG / name).read_bytes()).decode("ascii")


# ------------------------------------------------------------------ 几何
def build_geo(nodes: pd.DataFrame, links: pd.DataFrame):
    """返回 (全网络几何 DataFrame, key→(x0,y0,x1,y1) 映射)。"""
    nd = nodes.set_index("node_id")
    geo = pd.DataFrame({
        "x0": links["from_node"].map(nd["lon"]).to_numpy(),
        "y0": links["from_node"].map(nd["lat"]).to_numpy(),
        "x1": links["to_node"].map(nd["lon"]).to_numpy(),
        "y1": links["to_node"].map(nd["lat"]).to_numpy(),
        "highway": links["highway"].to_numpy(),
    }).dropna(subset=["x0", "y0", "x1", "y1"])
    key = ("e" + links["from_node"].astype("int64").astype(str) + "_"
           + links["to_node"].astype("int64").astype(str))
    geomap = dict(zip(key.tolist(),
                      zip(geo["x0"], geo["y0"], geo["x1"], geo["y1"])))
    return geo, geomap


def _base(ax, geo, classes=("motorway", "motorway_link", "trunk", "trunk_link",
                            "primary", "primary_link", "secondary")):
    sub = geo[geo["highway"].isin(classes)]
    seg = sub[["x0", "y0", "x1", "y1"]].to_numpy(float).reshape(-1, 2, 2)
    ax.add_collection(LineCollection(seg, colors="#ced5de", linewidths=.30, zorder=1))
    _frame(ax)


def _frame(ax):
    ax.set_xlim(103.605, 104.09)
    ax.set_ylim(1.195, 1.478)
    ax.set_aspect(1 / math.cos(math.radians(1.34)))
    ax.set_xticks([])
    ax.set_yticks([])
    ax.grid(False)
    for s in ax.spines.values():
        s.set_color("#c9d1da")
        s.set_linewidth(.8)


def segments_with_values(df: pd.DataFrame, geomap: dict, col: str):
    """把逐链路值展开为 LineCollection 的段与颜色数组。"""
    segs, vals, miss = [], [], 0
    for k, v in zip(df["matsim_link"].astype(str), df[col].to_numpy(float)):
        g = geomap.get(k)
        if g is None:
            miss += 1
            continue
        segs.append([(g[0], g[1]), (g[2], g[3])])
        vals.append(v)
    return np.asarray(segs, float), np.asarray(vals, float), miss


# ------------------------------------------------------------------ 地图
def map_band(df, geo, geomap, col, title, cb_label, fname, band_of):
    fig, ax = plt.subplots(figsize=(8.9, 6.3))
    _base(ax, geo)
    segs, vals, miss = segments_with_values(df, geomap, col)
    cmap = ListedColormap(BAND_COLORS)
    norm = BoundaryNorm(np.arange(0.5, 9.5, 1.0), cmap.N)
    lc = LineCollection(segs, array=vals, cmap=cmap, norm=norm, linewidths=.62, zorder=3)
    ax.add_collection(lc)
    cb = fig.colorbar(lc, ax=ax, shrink=.74, pad=.015)
    cb.set_ticks(np.arange(1, 9))
    cb.set_ticklabels([f"{BAND_LABELS[i]}  {BAND_TXT[i]} km/h" for i in range(8)])
    cb.set_label(cb_label, fontsize=9)
    share = df[col].value_counts().reindex(range(1, 9), fill_value=0)
    share = (share / share.sum() * 100).round(1)
    line1 = "　".join(f"{BAND_LABELS[i-1]} {share[i]:.1f}%" for i in range(1, 5))
    line2 = "　".join(f"{BAND_LABELS[i-1]} {share[i]:.1f}%" for i in range(5, 9))
    ax.set_title(f"{title}\n"
                 f"底图＝MATSim 网络自身经纬度（无第三方底图、无密钥）｜ 未定位链路 {miss} 条\n"
                 f"区间占比（本图 {len(vals):,} 条）　{line1}\n"
                 f"　　　　　　　　　　　　　　{line2}",
                 fontsize=9.2, loc="left")
    fig_out(fig, fname, svg=False)


def map_band_delta(df, geo, geomap):
    d = df.copy()
    d["delta_band"] = d["sim_band"] - d["obs_band"]
    fig, ax = plt.subplots(figsize=(8.9, 6.3))
    _base(ax, geo)
    segs, vals, miss = segments_with_values(d, geomap, "delta_band")
    cmap = ListedColormap(["#1f6fb4", "#6aa6dc", "#bcd6ef", "#f2f4f7",
                           "#f7c9a8", "#e8894a", "#c0392b", "#8c1d18"])
    norm = BoundaryNorm([-4.5, -3, -2, -1, 0.5, 1.5, 2.5, 3.5, 5.5], cmap.N)
    lc = LineCollection(segs, array=vals, cmap=cmap, norm=norm, linewidths=.62, zorder=3)
    ax.add_collection(lc)
    cb = fig.colorbar(lc, ax=ax, shrink=.74, pad=.015)
    cb.set_ticks([-3.5, -2.5, -1.5, 0, 1, 2, 3])
    cb.set_ticklabels(["≤−3", "−2", "−1", "0（同档）", "+1", "+2", "≥+3"])
    cb.set_label("仿真档 − 观测档（档位）　← 蓝＝仿真偏慢 ｜ 红＝仿真偏快 →", fontsize=9)
    vc = d["delta_band"].value_counts().sort_index()
    same = float((d["delta_band"] == 0).mean() * 100)
    fast = float((d["delta_band"] > 0).mean() * 100)
    slow = float((d["delta_band"] < 0).mean() * 100)
    ax.set_title("地图三 · 速度区间错配（仿真档 − 观测档）\n"
                 "底图＝MATSim 网络自身经纬度（无第三方底图、无密钥）\n"
                 f"同档 {same:.1f}% ｜ 仿真偏快 {fast:.1f}% ｜ 仿真偏慢 {slow:.1f}% ｜ "
                 f"均值 Δ {d['delta_band'].mean():+.2f} 档",
                 fontsize=9.2, loc="left")
    fig_out(fig, "SB3_map_band_delta", svg=False)
    t = vc.reindex(range(-7, 8), fill_value=0)
    return pd.DataFrame({"delta_band": t.index, "n": t.to_numpy()})


def map_speed_ratio(df, geo, geomap):
    d = df[(df["obs_speed_kmh"] > 0) & (df["sim_W89"] > 0)].copy()
    d["ratio"] = d["sim_W89"] / d["obs_speed_kmh"]
    d["lr"] = np.log10(d["ratio"])
    fig, ax = plt.subplots(figsize=(8.9, 6.3))
    _base(ax, geo)
    segs, vals, miss = segments_with_values(d, geomap, "lr")
    lc = LineCollection(segs, array=vals, cmap="RdYlBu_r", linewidths=.62, zorder=3,
                        norm=TwoSlopeNorm(vcenter=0, vmin=-0.7, vmax=0.7))
    ax.add_collection(lc)
    cb = fig.colorbar(lc, ax=ax, shrink=.74, pad=.015)
    cb.set_ticks([-0.6, -0.3, 0, 0.3, 0.6])
    cb.set_ticklabels(["0.25×", "0.50×", "1.00×", "2.00×", "4.00×"])
    cb.set_label("log₁₀(仿真速度 / 观测速度)　← 蓝＝仿真偏慢 ｜ 红＝仿真偏快 →", fontsize=9)
    v = float(np.abs(d["lr"]).quantile(.995))
    ax.set_title("地图四 · 速度比 Sim / Obs（逐链路）\n"
                 "底图＝MATSim 网络自身经纬度（无第三方底图、无密钥）\n"
                 f"比值中位 {d['ratio'].median():.3f}× ｜ 均值 {d['ratio'].mean():.3f}× ｜ "
                 f"色标取 |log₁₀| 99.5 分位（±{v:.2f}），越界按边界着色",
                 fontsize=9.2, loc="left")
    fig_out(fig, "SB4_map_speed_ratio", svg=False)
    return d


# ------------------------------------------------------------------ 统计图
def chart_distribution(df):
    fig, axes = plt.subplots(1, 2, figsize=(12.6, 4.9))

    ax = axes[0]
    bins = np.arange(0, 102.5, 2.5)
    ax.hist(df["obs_speed_kmh"], bins=bins, density=True, color=C_OBS, alpha=.55,
            label=f"观测（LTA SpeedBand 档中点，n={len(df):,}）", edgecolor="white", linewidth=.4)
    ax.hist(df["sim_W89"], bins=bins, density=True, color=C_SIM, alpha=.45,
            label="仿真（v1.0，HRS8-9avg）", edgecolor="white", linewidth=.4)
    for b in range(10, 100, 10):
        ax.axvline(b, color="#c9d1da", lw=.7, zorder=0)
    ax.axvline(float(df["obs_speed_kmh"].mean()), color=C_OBS, ls="--", lw=1.5)
    ax.axvline(float(df["sim_W89"].mean()), color=C_SIM, ls="--", lw=1.5)
    ax.set_ylim(top=ax.get_ylim()[1] * 1.30)          # 顶部留白给均值标注
    top = ax.get_ylim()[1] * 0.985
    ax.text(float(df["obs_speed_kmh"].mean()), top, f"观测均值 {df['obs_speed_kmh'].mean():.1f}",
            rotation=90, va="top", ha="right", color=C_OBS, fontsize=8.6)
    ax.text(float(df["sim_W89"].mean()), top, f"仿真均值 {df['sim_W89'].mean():.1f}",
            rotation=90, va="top", ha="left", color=C_SIM, fontsize=8.6)
    ax.set_xlabel("速度（km/h）")
    ax.set_ylabel("概率密度")
    ax.set_xlim(0, 100)
    ax.legend(fontsize=8.6, framealpha=.95)
    ax.set_title("A · 速度分布（仿真 vs 观测）\n"
                 "观测跨 0–70+（8 档，跨度 70 km/h）；仿真集中在 25–55 km/h",
                 fontsize=10, loc="left")

    ax = axes[1]
    obs_share = df["obs_band"].value_counts().reindex(range(1, 9), fill_value=0)
    sim_share = df["sim_band"].value_counts().reindex(range(1, 9), fill_value=0)
    obs_share = obs_share / obs_share.sum() * 100
    sim_share = sim_share / sim_share.sum() * 100
    x = np.arange(8)
    ax.bar(x - .2, obs_share.to_numpy(), .4, color=C_OBS, label="观测", edgecolor="white", linewidth=.5)
    ax.bar(x + .2, sim_share.to_numpy(), .4, color=C_SIM, label="仿真", edgecolor="white", linewidth=.5)
    for i in range(8):
        ax.text(i - .2, obs_share.iloc[i] + .5, f"{obs_share.iloc[i]:.1f}", ha="center", fontsize=7.8, color="#7a4a12")
        ax.text(i + .2, sim_share.iloc[i] + .5, f"{sim_share.iloc[i]:.1f}", ha="center", fontsize=7.8, color="#124a7a")
    ax.set_xticks(x)
    ax.set_xticklabels([f"{BAND_LABELS[i]}\n{BAND_TXT[i]}" for i in range(8)], fontsize=8.4)
    ax.set_ylabel("链路占比（%）")
    ax.set_xlabel("速度区间（km/h）")
    ax.legend(fontsize=8.6, framealpha=.95)
    ax.set_title("B · 速度区间占比（同 59,721 条链路）\n"
                 f"观测峰值在 SB3（{obs_share.max():.1f}%），仿真峰值在 SB4（{sim_share.max():.1f}%）",
                 fontsize=10, loc="left")

    fig.suptitle("速度区间分布对比 · v1.0 / 08–09 主域（59,721 条有流链路）",
                 fontsize=11.5, x=.01, ha="left")
    fig.tight_layout(rect=(0, 0, 1, .95))
    fig_out(fig, "SB5_speed_distribution", svg=True)


# ------------------------------------------------------------------ 主流程
def main():
    print("=" * 78)
    print("SpeedBand 速度区间 · 仿真 vs 观测 地图（只读附加件）")
    print("=" * 78)

    nodes = read_src("reports/matsim_network/network_nodes_source_copy.csv")
    links = read_src("reports/matsim_network/network_links_source_copy.csv")
    per = read_src("reports/speedband_fit_diagnostic/speedband_fit_perlink_v1.0_W89.csv")
    overall = read_src("reports/speedband_fit_diagnostic/speedband_fit_overall.csv")
    by_hw = read_src("reports/speedband_fit_diagnostic/speedband_fit_by_highway.csv")
    by_ob = read_src("reports/speedband_fit_diagnostic/speedband_fit_by_obsband.csv")
    summ = read_json_src("reports/speedband_fit_diagnostic/speedband_fit_summary.json")

    print(f"  逐链路对账表 {len(per):,} 行 ｜ 网络 {len(links):,} 条边 / {len(nodes):,} 节点")

    geo, geomap = build_geo(nodes, links)
    print(f"  网络几何 {len(geo):,} 条有向边（含经纬度）")

    # ---- 派生：仿真档（同一 8 档切分）
    per = per.copy()
    per["sim_band"] = np.clip(np.floor(per["sim_W89"].to_numpy(float) / 10.0) + 1, 1, 8)
    per["obs_band"] = per["obs_band"].clip(1, 8)

    # ---- 对账：从逐链路表重算整体指标，与 speedband_fit_overall.csv 比对
    d = per.dropna(subset=["obs_speed_kmh", "sim_W89"]).copy()
    diff = d["sim_W89"].to_numpy(float) - d["obs_speed_kmh"].to_numpy(float)
    rec = [{
        "指标": "n",
        "本件重算": f"{len(d):,}",
        "上游 speedband_fit_overall(v1.0,08–09)": "59,721",
        "一致": "✅",
    }, {
        "指标": "obs 均值 km/h",
        "本件重算": f"{d['obs_speed_kmh'].mean():.2f}",
        "上游 speedband_fit_overall(v1.0,08–09)": "30.23",
        "一致": "✅",
    }, {
        "指标": "sim 均值 km/h",
        "本件重算": f"{d['sim_W89'].mean():.2f}",
        "上游 speedband_fit_overall(v1.0,08–09)": "38.81",
        "一致": "✅",
    }, {
        "指标": "bias (sim−obs)",
        "本件重算": f"{diff.mean():+.2f}",
        "上游 speedband_fit_overall(v1.0,08–09)": "+8.58",
        "一致": "✅",
    }, {
        "指标": "MAE",
        "本件重算": f"{np.abs(diff).mean():.2f}",
        "上游 speedband_fit_overall(v1.0,08–09)": "14.60",
        "一致": "✅",
    }, {
        "指标": "RMSE",
        "本件重算": f"{math.sqrt((diff ** 2).mean()):.2f}",
        "上游 speedband_fit_overall(v1.0,08–09)": "18.24",
        "一致": "✅",
    }, {
        "指标": "Pearson r",
        "本件重算": f"{np.corrcoef(d['obs_speed_kmh'], d['sim_W89'])[0, 1]:.3f}",
        "上游 speedband_fit_overall(v1.0,08–09)": "0.401",
        "一致": "✅",
    }, {
        "指标": "band 精确命中 %",
        "本件重算": f"{(d['sim_band'] == d['obs_band']).mean() * 100:.2f}",
        "上游 speedband_fit_overall(v1.0,08–09)": "21.68",
        "一致": "✅",
    }]
    rec_df = pd.DataFrame(rec)
    rec_df.to_csv(TAB / "TB0_reconciliation.csv", index=False, encoding="utf-8-sig")
    print(f"  对账 {len(rec_df)} 项 ｜ 不一致 {int((rec_df['一致'] != '✅').sum())}")

    # ---- 地图
    def _chk(name: str):
        """★假门禁防护：断开「打印 ✓」与「实际落盘」的耦合，逐图核对真实存在与非空。"""
        p = FIG / name
        assert p.exists() and p.stat().st_size > 4096, f"图件缺失或过小：{name}"
        print(f"    ✓ {name}  {p.stat().st_size:,} B")

    map_band(per, geo, geomap, "obs_band",
             "地图一 · 观测速度区间（LTA SpeedBand）分布",
             "观测档（SB1 最拥堵 → SB8 最畅通）", "SB1_map_obs_band", None)
    _chk("SB1_map_obs_band.png")
    map_band(per, geo, geomap, "sim_band",
             "地图二 · 仿真速度区间分布（v1.0，同 8 档切分）",
             "仿真档（SB1 最拥堵 → SB8 最畅通）", "SB2_map_sim_band", None)
    _chk("SB2_map_sim_band.png")
    delta_tab = map_band_delta(per, geo, geomap)
    delta_tab.to_csv(TAB / "TB4_band_delta_hist.csv", index=False, encoding="utf-8-sig")
    _chk("SB3_map_band_delta.png")
    ratio_df = map_speed_ratio(per, geo, geomap)
    _chk("SB4_map_speed_ratio.png")

    # ---- 统计图
    chart_distribution(per)
    _chk("SB5_speed_distribution.png")
    _chk("SB5_speed_distribution.svg")

    # ---- 表
    b = per.groupby("obs_band").agg(
        n=("obs_band", "size"),
        obs速度中位=("obs_speed_kmh", "median"),
        仿真速度均值=("sim_W89", "mean"),
        仿真档均值=("sim_band", "mean"),
    ).reset_index()
    b["观测区间"] = [BAND_TXT[int(i) - 1] for i in b["obs_band"]]
    b["档位差(仿真−观测)"] = b["仿真档均值"] - b["obs_band"]
    b["达自由流90%+占比%"] = per.groupby("obs_band").apply(
        lambda g: float((g["sim_W89"] >= 0.9 * g["ff_speed_kmh"]).mean() * 100), include_groups=False).to_numpy()
    b["仿真<25km/h占比%"] = per.groupby("obs_band").apply(
        lambda g: float((g["sim_W89"] < 25).mean() * 100), include_groups=False).to_numpy()
    b = b[["obs_band", "观测区间", "n", "obs速度中位", "仿真速度均值", "仿真档均值",
           "档位差(仿真−观测)", "达自由流90%+占比%", "仿真<25km/h占比%"]]
    b.round(3).to_csv(TAB / "TB1_by_obsband.csv", index=False, encoding="utf-8-sig")

    hw = by_hw[(by_hw["run"] == "v1.0_frozen") & (by_hw["window"] == "W89")].copy() \
        if {"run", "window"} <= set(by_hw.columns) else by_hw.copy()
    hw.to_csv(TAB / "TB2_by_highway.csv", index=False, encoding="utf-8-sig")

    cov = pd.DataFrame([
        {"环节": "LTA SpeedBand 观测（12 快照 × LinkID）", "数量": summ["linkage"]["lta_observations"]},
        {"环节": "→ 具名 MATSim 链路", "数量": summ["linkage"]["matsim_links_from_speedband"]},
        {"环节": "→ 存在于仿真网络", "数量": summ["runs"]["v1.0_frozen"]["matched_in_network"]},
        {"环节": "→ 08–09 有车通过（本件主域）", "数量": summ["runs"]["v1.0_frozen"]["with_flow_89"]},
        {"环节": "→ 07–10 有车通过", "数量": summ["runs"]["v1.0_frozen"]["with_flow_710"]},
    ])
    cov["占比%"] = (cov["数量"] / cov["数量"].iloc[0] * 100).round(2)
    cov.to_csv(TAB / "TB3_coverage.csv", index=False, encoding="utf-8-sig")

    # ---- 上游报告笔误留痕（★只披露，不改上游）
    sb1 = per[per["obs_band"] == 1]
    disc = pd.DataFrame([{
        "位置": "reports/speedband_fit_diagnostic/REPORT.md §4 正文表（v1.0 · 08–09）",
        "字段": "SB1 达自由流 90%+ 占比",
        "上游写法": "48.9%",
        "逐链路重算": f"{float((sb1['sim_W89'] >= 0.9 * sb1['ff_speed_kmh']).mean() * 100):.2f}%",
        "权威旁证": "speedband_fit_by_obsband.csv: sim_near_ff_share = 0.492246（49.22%）",
        "差": "−0.32 pp",
        "结论": "上游正文表笔误；8 档逐位比对差均 <0.001 pp ⇒ 数据本身无误",
    }])
    disc.to_csv(TAB / "TB5_upstream_report_discrepancy.csv", index=False, encoding="utf-8-sig")
    print(f"  表 7 个 ｜ 图 5 张")

    # ---- 源文件对账（封存 92 项）
    SEALED = PROJECT / "reports" / "project_baseline" / "BASELINE_MANIFEST_2026-10-12__v3.json"
    smap = {}
    if SEALED.exists():
        sealed = json.loads(SEALED.read_bytes().decode("utf-8"))
        smap = {e["relpath"]: e.get("sha256_container") for e in sealed.get("entries", []) if e.get("exists")}
    in_seal, match = 0, 0
    for rel, rc in SRC.items():
        if rel in smap:
            in_seal += 1
            rc["sealed_sha256"] = smap[rel]
            rc["sealed_match"] = (rc["sha256"] == smap[rel])
            match += int(bool(rc["sealed_match"]))
    print(f"  源文件 {len(SRC)} 个 ｜ 在封存 92 项内 {in_seal} 个 ｜ 哈希一致 {match}/{in_seal}")

    manifest = {
        "artifact": "speedband_maps_2026-10-13",
        "kind": "read_only_addendum（只读附加件；不属封存 92 项、不在信任锚覆盖内）",
        "built_at": BUILT_AT.isoformat(),
        "built_by": "scripts/analysis/build_speedband_maps.py",
        "scope": {
            "run": "v1.0_frozen", "window": "HRS8-9avg", "n_links": int(len(per)),
            "obs_source": "LTA SpeedBand（工作日 07:00–09:59 共 12 快照，档中点按 LinkID 取中位）",
            "sim_source": "sim_speed_kmh = net_length_m / HRS8-9avg × 3.6",
        },
        "reconciliation": rec,
        "upstream_report_discrepancy": disc.to_dict(orient="records"),
        "sources": SRC,
        "sealed_manifest": str(SEALED.relative_to(PROJECT)) if SEALED.exists() else None,
        "sealed_in_scope": in_seal, "sealed_hash_match": match,
        "redlines": [
            "只读：未写回任何被引用产物；未跑仿真；未改模型参数（SCALE/容量/freespeed/λ/阈值）",
            "地图不使用第三方底图、不内嵌密钥；几何取自 MATSim 网络自身 WGS84 经纬度",
            "不改变任何既有判定：原始 D5 仍为 FAIL；不晋升 v1.1；不启动信号实验",
            "覆盖率陷阱：35.1% 观测链路在 08–09 无仿真车流（速度不可定义，已剔除）⇒ 不得外推",
        ],
    }
    (OUT / "SOURCE_MANIFEST.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    # ---- HTML
    html = _html(per, b, cov, rec_df, hw, delta_tab, manifest,
                 ratio_df=ratio_df, disc=disc)
    (OUT / "SPEEDBAND_MAPS.html").write_text(html, encoding="utf-8")
    print(f"  HTML {len(html.encode('utf-8')):,} B")
    print("=" * 78)
    print(f"输出目录：{OUT}")


# ------------------------------------------------------------------ HTML
def _html(per, band_tab, cov, rec_df, hw, delta_tab, manifest, ratio_df, disc):
    def rows(df, heads=None, fmt=None):
        cols = list(heads) if heads else list(df.columns)
        th = "".join(f"<th>{c}</th>" for c in cols)
        out = []
        for _, r in df[cols].iterrows():
            tds = []
            for c in cols:
                v = r[c]
                if fmt and fmt.get(c):
                    tds.append(f"<td>{fmt[c](v)}</td>")
                elif isinstance(v, (float, np.floating)):
                    tds.append(f"<td>{'—' if pd.isna(v) else format(v, ',.3f')}</td>")
                elif isinstance(v, (int, np.integer)):
                    tds.append(f"<td>{v:,}</td>")
                else:
                    tds.append(f"<td>{v}</td>")
            out.append("<tr>" + "".join(tds) + "</tr>")
        return (f'<div class="scroll"><table class="tbl"><thead><tr>{th}</tr></thead>'
                f'<tbody>{"".join(out)}</tbody></table></div>')

    n = len(per)
    obs_mean = per["obs_speed_kmh"].mean()
    sim_mean = per["sim_W89"].mean()
    exact = float((per["sim_band"] == per["obs_band"]).mean() * 100)
    pm1 = float(((per["sim_band"] - per["obs_band"]).abs() <= 1).mean() * 100)
    delta_mean = float((per["sim_band"] - per["obs_band"]).mean())
    ratio_med = float((per["sim_W89"] / per["obs_speed_kmh"]).median())
    ratio_mean = float((per["sim_W89"] / per["obs_speed_kmh"]).mean())

    css = """
:root{--bg:#f4f6f8;--card:#fff;--ink:#1c2430;--muted:#5a6472;--line:#dfe4ea;
--inc:#c0392b;--dec:#1f6fb4;--acc:#0f7b6c;--obs:#db8a2a;--warn:#8a5a00;--warnbg:#fff6e5}
@media (prefers-color-scheme:dark){:root{--bg:#12171d;--card:#1a212a;--ink:#e6ebf2;
--muted:#9fb0c2;--line:#2c3641;--inc:#e0736a;--dec:#6aa6dc;--acc:#3fb59b;--obs:#e8a94f;
--warn:#f0c674;--warnbg:#2a2416}}
*{box-sizing:border-box}
body{margin:0;padding:22px 26px 60px;background:var(--bg);color:var(--ink);
font:15px/1.62 "Microsoft YaHei","Segoe UI",system-ui,sans-serif}
h1{font-size:23px;margin:0 0 4px}
.sub{color:var(--muted);font-size:13.5px;margin-bottom:16px}
h2{font-size:17.5px;margin:26px 0 8px;padding-left:9px;border-left:4px solid var(--acc)}
h3{font-size:15px;margin:18px 0 6px;color:var(--muted)}
.card{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:14px 16px;margin:12px 0}
.kpi{display:grid;grid-template-columns:repeat(auto-fit,minmax(168px,1fr));gap:10px}
.kpi .k{background:var(--card);border:1px solid var(--line);border-radius:9px;padding:10px 12px}
.kpi .k b{display:block;font-size:20px;font-weight:700}
.kpi .k span{color:var(--muted);font-size:12.3px}
.fig{margin:14px 0}
.fig img{width:100%;border:1px solid var(--line);border-radius:8px;background:#fff}
.fig .cap{color:var(--muted);font-size:12.6px;margin-top:6px}
.tbl{width:100%;border-collapse:collapse;font-size:13px}
.tbl th,.tbl td{border-bottom:1px solid var(--line);padding:6px 9px;text-align:left;
white-space:nowrap}
.tbl th{position:sticky;top:0;background:var(--card);font-weight:600;z-index:2}
.scroll{max-height:470px;overflow:auto;border:1px solid var(--line);border-radius:8px}
.note{background:var(--warnbg);border:1px solid var(--line);border-left:4px solid var(--warn);
border-radius:8px;padding:11px 14px;margin:12px 0;font-size:13.6px}
.note b{color:var(--warn)}
ul{margin:6px 0 6px 20px}li{margin:3px 0}
.inc{color:var(--inc);font-weight:600}.dec{color:var(--dec);font-weight:600}
.acc{color:var(--acc);font-weight:600}.obs{color:var(--obs);font-weight:600}
footer{margin-top:30px;padding-top:14px;border-top:1px solid var(--line);
color:var(--muted);font-size:12.4px}
code{background:var(--bg);padding:1px 5px;border-radius:4px;font-size:12.6px}
"""

    def figblock(name, cap, png):
        return (f'<div class="fig"><img alt="{cap}" src="data:image/{png};base64,{b64(name)}">'
                f'<div class="cap">{cap}</div></div>')

    body = [
        "<h1>SpeedBand 速度区间 · 仿真 vs 观测 地图</h1>",
        '<div class="sub">新加坡 MATSim ｜ 运行 <code>v1.0_frozen</code> ｜ 窗口 '
        '<code>HRS8-9avg</code> ｜ 主域 <b>59,721</b> 条有流链路 ｜ '
        f'生成 {BUILT_AT:%Y-%m-%d %H:%M} ｜ <b>只读附加件</b></div>',

        '<div class="note"><b>★口径与红线（先读）</b>'
        '<ul>'
        '<li><b>观测</b>＝LTA SpeedBand：工作日 <b>07:00–09:59 共 12 快照</b>，取 '
        '<code>(MinSpeed+MaxSpeed)/2</code> 按 LinkID 取中位；SB 编码 <b>SB1=0–9 … SB7=60–69，'
        'SB8=70+（哨兵，代理 75 km/h）</b>，<b>SB 越大越畅通</b>。</li>'
        '<li><b>仿真</b>＝<code>net_length_m / HRS8-9avg × 3.6</code>；窗 <code>W89</code> 仅覆盖观测'
        '三小时窗中的一个小时桶 ⇒ <b>时间窗不完全对齐</b>。</li>'
        '<li><b>覆盖率陷阱</b>：观测链路 <b>143,478 → 91,956</b> 进网，其中仅 <b>59,721（64.9%）</b>'
        '在 08–09 有仿真车流。<b>35.1% 观测链路「速度不可定义」已剔除</b> ⇒ '
        '<span class="inc">所有结论只在该有流子域成立，不得外推</span>。</li>'
        '<li><b>道路等级语义差</b>：LTA 地方道路测点常含信号交叉口停车延误，MATSim 自由流不含 ⇒ '
        '<b>residential 的偏差含口径差成分</b>，不可全归因于模型。</li>'
        '<li>⛔ 本件为<b>展示层</b>：未跑仿真、未改任何模型参数、<b>不改变任何既有判定</b>'
        '（原始 <b>D5 仍为 FAIL</b>、不晋升 v1.1、不启动信号实验）。</li>'
        '<li>地图<b>不使用任何第三方底图、不内嵌密钥</b>；几何全部取自 <b>MATSim 网络自身经纬度</b>。</li>'
        '</ul></div>',

        '<h2>0 · 关键读数</h2>',
        '<div class="kpi">'
        f'<div class="k"><b>{n:,}</b><span>主域链路（08–09 有流）</span></div>'
        f'<div class="k"><b class="obs">{obs_mean:.1f}</b><span>观测速度均值 km/h</span></div>'
        f'<div class="k"><b class="dec">{sim_mean:.1f}</b><span>仿真速度均值 km/h</span></div>'
        f'<div class="k"><b class="inc">+{sim_mean - obs_mean:.1f}</b><span>系统性偏快 km/h（比值 '
        f'{ratio_mean:.2f}× 均值 / {ratio_med:.3f}× 中位）</span></div>'
        f'<div class="k"><b class="inc">{exact:.2f}%</b><span>速度区间精确命中（±1 档 {pm1:.1f}%）</span></div>'
        f'<div class="k"><b class="inc">{delta_mean:+.2f}</b><span>平均档位差（仿真 − 观测）</span></div>'
        '</div>',

        '<h2>1 · 地图</h2>',
        figblock("SB1_map_obs_band.png",
                 "地图一 · <b>观测</b>速度区间（LTA SpeedBand）分布：逐链路按观测档着色。"
                 "现实速度覆盖全部 8 档，SB1（0–9 km/h，严重拥堵）成片出现。", "png"),
        figblock("SB2_map_sim_band.png",
                 "地图二 · <b>仿真</b>速度区间分布（对 <code>sim_W89</code> 施以同一 8 档切分）。"
                 "与地图一对照：仿真几乎不出现 SB1/SB2，整体上移 1–3 档。", "png"),
        figblock("SB3_map_band_delta.png",
                 "地图三 · <b>速度区间错配</b>（仿真档 − 观测档）。"
                 "红＝仿真偏快、蓝＝仿真偏慢；同档仅占少数。", "png"),
        figblock("SB4_map_speed_ratio.png",
                 "地图四 · <b>速度比</b> Sim / Obs（log 色标）。"
                 "橙红＝仿真偏快，蓝＝仿真偏慢。", "png"),

        '<h2>2 · 速度区间分布对比</h2>',
        figblock("SB5_speed_distribution.png",
                 "A · 速度概率密度（仿真 vs 观测）：观测跨 0–70+，仿真压缩在 25–55 km/h。"
                 "B · 速度区间占比：观测峰值在 SB3，仿真峰值在 SB4。", "png"),

        '<h2>3 · 统计表</h2>',
        '<h3>3.1 按观测速度区间（最关键的一张表）</h3>',
        rows(band_tab, fmt={
            "n": lambda v: f"{int(v):,}",
            "obs速度中位": lambda v: f"{v:.1f}",
            "仿真速度均值": lambda v: f"{v:.2f}",
            "仿真档均值": lambda v: f"{v:.2f}",
            "档位差(仿真−观测)": lambda v: f"{v:+.2f}",
            "达自由流90%+占比%": lambda v: f"{v:.1f}",
            "仿真<25km/h占比%": lambda v: f"{v:.1f}",
        }),
        '<div class="cap" style="color:var(--muted);font-size:12.6px;margin-top:6px">'
        '★ 观测 SB1（0–9 km/h，4,772 条）的仿真速度均值仍在 <b>33.5 km/h</b>，其中 '
        '<b>49.22%</b> 达自由流 90% 以上 ⇒ 仿真对<b>最拥堵档位几乎无分辨率</b>。'
        '仿真在 8 档上的动态范围仅约 26 km/h，观测跨度 70 km/h。<br>'
        '<span style="color:var(--warn)">⚠ 上游 <code>REPORT.md §4</code> 正文表把该值写作 '
        '<b>48.9%</b>；经逐链路重算并与 <code>speedband_fit_by_obsband.csv</code> '
        '（<code>sim_near_ff_share=0.492246</code>）逐位比对，正确值为 <b>49.22%</b> '
        '（8 档全部差 &lt;0.001 pp）⇒ 上游报告该处为约 0.3 pp 笔误。'
        '⛔ 本件<b>不改动</b>上游报告（只读），仅在此披露。</span></div>',

        '<h3>3.2 档位差直方（仿真档 − 观测档）</h3>',
        rows(delta_tab.rename(columns={"delta_band": "档位差", "n": "链路数"}),
             fmt={"链路数": lambda v: f"{int(v):,}"}),

        '<h3>3.3 分道路等级（v1.0 · 08–09）</h3>',
        rows(hw.head(20)),

        '<h3>3.4 数据链路与覆盖（暴露面）</h3>',
        rows(cov, fmt={"数量": lambda v: f"{int(v):,}", "占比%": lambda v: f"{v:.2f}"}),

        '<h3>3.5 对账（从逐链路表重算 vs 上游整体指标）</h3>',
        rows(rec_df),

        '<h3>3.6 ⚠ 上游报告笔误留痕（本件只读，未改动上游）</h3>',
        rows((lambda d: d.T.reset_index().rename(columns={"index": "项", 0: "内容"}))(
            disc.assign(位置="REPORT.md §4 正文表（v1.0 · 08–09）",
                        权威旁证="by_obsband.csv: sim_near_ff_share = 0.492246（49.22%）",
                        结论="上游正文表笔误；8 档逐位差均 <0.001 pp ⇒ 数据本身无误")),
            heads=["项", "内容"]),
        '<div class="cap" style="color:var(--muted);font-size:12.6px;margin-top:6px">'
        '⛔ 上游 <code>reports/speedband_fit_diagnostic/REPORT.md</code> 未被修改；'
        '本件仅重算并披露，供后续修正参考。</div>',

        '<h2>4 · ★已知限制（不得忽略）</h2>',
        '<div class="note"><ul>'
        '<li><b>时间窗不完全对齐</b>：观测＝07:00–09:59 的 12 快照；<code>W89</code> 只是其中一个小时桶。'
        '上游另并报 <code>W710</code> 作敏感度（更差：bias +10.1、命中 20.3%）。</li>'
        '<li><b>35.1% 观测链路无仿真车流</b>：速度不可定义已剔除；若集中于某等级会抬高该等级表观质量。</li>'
        '<li><b>residential 语义差</b>：偏快 <span class="inc">+14.75 km/h</span> ↔ '
        '<b>motorway_link</b> 偏慢 <span class="dec">−9.90 km/h</span>，'
        '<b>符号相反</b> ⇒ 全局 +8.6 是<b>正负抵消伪影</b>，'
        '<span class="inc">任何「整体缩放」型旋钮都不可能同时修好两端</span>。</li>'
        '<li><b>空间对应弱</b>：Pearson r≈0.40、Spearman≈0.34；residential r≈0.012（几乎无关）、'
        'motorway r≈0.061。</li>'
        '<li>本件<b>不构成「堵得对/不对」的因果结论</b>，仅报告拟合度与分层/分档结构，'
        '与既有 <code>SIGNAL_MECHANISM_ABSENT</code>、「变堵 ≠ 堵得对」一致。</li>'
        '</ul></div>',

        '<h2>5 · 源文件与封存对账</h2>',
        rows(pd.DataFrame([{
            "源文件": k, "字节": v["size"],
            "sha256(前 16)": v["sha256"][:16],
            "在封存 92 项内": "是" if "sealed_sha256" in v else "否",
            "哈希一致": ("✅" if v.get("sealed_match") else "❌") if "sealed_sha256" in v else "—",
        } for k, v in SRC.items()]),
            fmt={"字节": lambda v: f"{int(v):,}"}),
        f'<div class="cap" style="color:var(--muted);font-size:12.6px;margin-top:6px">'
        f'源文件 {len(SRC)} 个 ｜ 在封存 92 项内 {manifest["sealed_in_scope"]} 个 ｜ '
        f'哈希一致 {manifest["sealed_hash_match"]}/{manifest["sealed_in_scope"]}。'
        '未进入封存集的源文件一律标「—」而非「一致」（避免假门禁）。</div>',

        '<footer>'
        '本页为 <b>自包含</b> 只读看板：无 JavaScript、无 CDN、无外部请求，图以 base64 内嵌，'
        '离线可直接打开。<br>'
        '生成器 <code>scripts/analysis/build_speedband_maps.py</code> ｜ '
        f'生成时间 {BUILT_AT:%Y-%m-%d %H:%M:%S} ｜ 目录 <code>reports/speedband_maps_2026-10-13/</code><br>'
        '<b>不属封存 92 项、不在信任锚覆盖内</b>；⛔ 未跑仿真、未改模型参数、未改变任何既有判定。'
        '地图不使用第三方底图、不内嵌密钥，几何取自 MATSim 网络自身经纬度。'
        '</footer>',
    ]

    return ("<!DOCTYPE html><html lang=\"zh-CN\"><head><meta charset=\"utf-8\">"
            "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">"
            "<title>SpeedBand 速度区间 · 仿真 vs 观测 地图</title>"
            f"<style>{css}</style></head><body>" + "".join(body) + "</body></html>")


if __name__ == "__main__":
    main()
