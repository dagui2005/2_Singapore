#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""
ecap01_demo_figs.py — E-CAP-01 领导展示 3 图（只读；不改任何冻结件）

按 PROTOCOL §8 与用户约束重做：
  · 主图**不用** `speed_ratio` / 逐链 `cong_ratio` 红绿图（短链量化伪影）。
  · 图 1 改用 **§8 优先项 1「按长度/流量聚合后的负荷」**：1 km 网格内
        `load_cell = Σ h89 / Σ cap_eff`（cap_eff = CAPACITY × 1/SCALE）
    两版**同一色标** ⇒ 直接看「需求—容量同尺度后负荷如何抬升、在哪些走廊抬升」。
  · 三图叙事：**现实(LTA 观测) → 现状(v1.0) → 尺度统一试验(E-CAP-01)**。

产物（落 `experiments/E-CAP-01_scale_capacity/figures/`）：
  fig1_load_grid_v10_vs_ecap.png  —— 2 面板 1 km 网格负荷（Σ流量/Σ容量）
  fig2_lta_observed_map.png       —— LTA 观测 08–09 断面流量（现实参照）
  fig3_metrics_ratio_bars.png     —— E-CAP-01 / v1.0 倍率柱（同报绝对值）

用法：python scripts/experiments/ecap01_demo_figs.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(r"D:\Luan\2026-05\2_Singapore")
SCRIPTS_OD = ROOT / "scripts" / "od"
sys.path.insert(0, str(SCRIPTS_OD))

import audit_sampling_capacity_7_9a1 as A1  # noqa: E402

ECAP = ROOT / "experiments" / "E-CAP-01_scale_capacity"
AUDIT = ECAP / "audit"
FIGS = ECAP / "figures"
FIGS.mkdir(parents=True, exist_ok=True)
ECAP_OUT = ECAP / "outputs" / "E-CAP-01"
ECAP_LS19 = ECAP_OUT / "ITERS" / "it.19" / "E-CAP-01.19.linkstats.txt.gz"
F_CAP = 0.434977
METRICS_JSON = AUDIT / "ecap01_postrun_metrics.json"
CELL = 1000.0


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


def main() -> int:
    plt = setup_mpl()
    import matplotlib.colors as mcolors

    print("[load] network geometry / linkstats")
    labels = A1.load_net_labels()
    v10 = A1.load_linkstats(A1.V10_LS)
    ecap = A1.load_linkstats(ECAP_LS19)
    nx = dict(zip(labels["node_ids"].tolist(), labels["node_x"].tolist()))
    ny = dict(zip(labels["node_ids"].tolist(), labels["node_y"].tolist()))
    pos = {lid: i for i, lid in enumerate(labels["ids"])}

    X0, X1, Y0, Y1 = 0.0, 52000.0, 20000.0, 52000.0
    ncx = int((X1 - X0) / CELL) + 1
    ncy = int((Y1 - Y0) / CELL) + 1

    def cell_load(L, cap_mul):
        sflow = np.zeros((ncy, ncx))
        scap = np.zeros((ncy, ncx))
        for k, d in L.items():
            if d["h89"] <= 0:
                continue
            i = pos.get(k)
            if i is None:
                continue
            f_, t_ = labels["frm"][i], labels["to"][i]
            if f_ not in nx or t_ not in nx:
                continue
            mx = 0.5 * (nx[f_] + nx[t_])
            my = 0.5 * (ny[f_] + ny[t_])
            cx = int((mx - X0) // CELL)
            cy = int((my - Y0) // CELL)
            if 0 <= cx < ncx and 0 <= cy < ncy:
                sflow[cy, cx] += d["h89"]
                scap[cy, cx] += d["cap"] * cap_mul
        with np.errstate(divide="ignore", invalid="ignore"):
            grid = np.where(scap > 0, sflow / scap, np.nan)
        return np.ma.masked_invalid(grid), sflow, scap

    g_v10, f0, c0 = cell_load(v10, 1.0)
    g_ecap, f1, c1 = cell_load(ecap, F_CAP)
    vmax = float(np.nanpercentile(np.concatenate([g_v10.compressed(), g_ecap.compressed()]), 99))
    vmax = max(vmax, 0.3)
    norm = mcolors.Normalize(0.0, vmax)
    cmap = plt.get_cmap("YlOrRd").copy()

    print(f"[fig1] 1km load grid (Σflow/Σcap), vmax(p99)={vmax:.3f}")
    _xw = A1.load_crosswalk_raw()
    _tgt_ids = list(_xw.loc[_xw["is_primary_candidate"] == True, "matsim_link_id"].unique())[:5000]  # noqa: E712
    tx = [nx[labels["frm"][pos[k]]] for k in _tgt_ids if k in pos and labels["frm"][pos[k]] in nx]
    ty = [ny[labels["frm"][pos[k]]] for k in _tgt_ids if k in pos and labels["frm"][pos[k]] in ny]
    fig, axes = plt.subplots(1, 2, figsize=(21, 11))
    panels = [("现状 v1.0：需求 43.5% + 容量 100%（负荷被稀释，偏通畅）", g_v10),
              ("尺度统一 E-CAP-01：需求 43.5% + 容量 43.5%（=1/SCALE）", g_ecap)]
    ext = [X0, X1, Y0, Y1]
    for ax, (ttl, gg) in zip(axes, panels):
        im = ax.imshow(gg, origin="lower", extent=ext, cmap=cmap, norm=norm,
                       interpolation="nearest", aspect="equal")
        ax.set_title(ttl, fontsize=12.5, loc="left")
        ax.set_xlabel("EPSG:3414 (m)")
        # 叠加 7.3.6A 靶场链位置（灰点，作空间参照）
        if tx:
            ax.scatter(tx, ty, s=0.4, c="#333333", alpha=0.25, marker=".")
        ax.text(0.99, 0.02,
                "色 = 1 km 网格负荷 Σ(流量)/Σ(有效容量)\n两图同一色标；灰点 = 7.3.6A 靶场链",
                transform=ax.transAxes, ha="right", va="bottom", fontsize=9, color="#222222",
                bbox=dict(boxstyle="round", fc="white", ec="#bbbbbb", alpha=0.85))
    sm = plt.cm.ScalarMappable(cmap=cmap, norm=norm)
    sm.set_array([])
    cb = fig.colorbar(sm, ax=axes, fraction=0.025, pad=0.02)
    cb.set_label("负荷 = Σ流量 / Σ有效容量（>1 表示超饱和）", fontsize=10)
    fig.suptitle("新加坡早高峰 08–09 · 道路负荷空间格局对照（尺度统一试验 E-CAP-01）\n"
                 "左：现状 v1.0（偏通畅）  |  右：需求与容量同尺度后  ——  拥堵是否出现、出现在哪些走廊",
                 fontsize=15, y=0.99)
    p1 = FIGS / "fig1_load_grid_v10_vs_ecap.png"
    fig.savefig(p1, bbox_inches="tight", facecolor="white", dpi=150)
    plt.close(fig)
    print("   ->", p1)

    # ---------------- Fig 2：LTA 观测（现实） ----------------
    print("[fig2] LTA observed 08-09 map")
    obs = A1.load_observed()
    geo = pd.read_csv(A1.SEC_GEO)
    geo["lta_linkid"] = geo["lta_linkid"].astype(str).str.strip()
    xw = A1.load_crosswalk_raw()
    prim_ids = set(xw.loc[xw["is_primary_candidate"] == True, "lta_linkid"].astype(str).str.strip())  # noqa: E712
    geo = geo[geo["lta_linkid"].isin(prim_ids)].copy()
    geo["obs0809"] = geo["lta_linkid"].map(lambda s: obs.get(s, {}).get(8, np.nan))
    gd = geo.dropna(subset=["obs0809", "mid_x", "mid_y"])
    fig, ax = plt.subplots(figsize=(12, 11))
    sc = ax.scatter(gd["mid_x"], gd["mid_y"], c=gd["obs0809"], s=16,
                    cmap="YlOrRd", norm=mcolors.Normalize(0, float(np.percentile(gd["obs0809"], 98)),
                                                          clip=True))
    ax.set_aspect("equal")
    ax.set_xlim(2000, 52000)
    ax.set_ylim(21000, 51500)
    ax.set_title(f"LTA 实测断面流量（现实参照）——早高峰 08–09，共 {len(gd)} 个观测断面",
                 fontsize=13, loc="left")
    ax.set_xlabel("EPSG:3414 (m)")
    cb = fig.colorbar(sc, ax=ax, fraction=0.03, pad=0.02)
    cb.set_label("观测流量 (veh/h)", fontsize=10)
    fig.suptitle("现实 → 现状模型 → 尺度统一试验：本图 = 真实观测的空间格局", fontsize=14, y=0.98)
    p2 = FIGS / "fig2_lta_observed_map.png"
    fig.savefig(p2, bbox_inches="tight", facecolor="white", dpi=150)
    plt.close(fig)
    print("   ->", p2)

    # ---------------- Fig 3：倍率柱（自动取 postrun 实测） ----------------
    print("[fig3] metrics ratio bars")
    m = json.loads(METRICS_JSON.read_text(encoding="utf-8"))
    fm0, fm1 = m["face_metrics_v10"], m["face_metrics_ecap"]
    g = m.get("guardrail") or {}
    so0, so1 = g.get("V1", {}).get("q_FROZEN"), g.get("ECAP", {}).get("q_FROZEN")
    items = [
        ("Sim/Obs\n(流量对账) ↓", so0, so1, "{:.3f}"),
        ("拥堵链数\nN_cong ↑", fm0["n_cong_cut0"], fm1["n_cong_cut0"], "{:,.0f}"),
        ("n(v/c≥1.0) ↑", fm0["n_vc_ge_10"], fm1["n_vc_ge_10"], "{:,.0f}"),
        ("饱和里程\nkm ↑", fm0["sat_km"], fm1["sat_km"], "{:.2f}"),
        ("Σ流量/Σ容量 ↑", fm0["peak_agg_vc"], fm1["peak_agg_vc"], "{:.3f}"),
        ("总延误\nveh·h ↑", fm0["delay_h"], fm1["delay_h"], "{:,.0f}"),
    ]
    ratios = [float(x[2]) / float(x[1]) if float(x[1]) else float("nan") for x in items]
    labels_b = [x[0] for x in items]
    xpos = np.arange(len(items))
    colors = ["#c0392b" if r > 1 else "#2e86c1" for r in ratios]
    fig, ax = plt.subplots(figsize=(13, 6.8))
    bars = ax.bar(xpos, ratios, 0.6, color=colors)
    ax.axhline(1.0, color="#555555", ls="--", lw=1.2)
    ax.set_xticks(xpos)
    ax.set_xticklabels(labels_b, fontsize=10.5)
    ax.set_ylabel("E-CAP-01 ÷ v1.0（倍率）", fontsize=11)
    ax.set_title("尺度统一试验相对现状的倍率（1.0 = 与现状相同）", fontsize=14, loc="left")
    ax.grid(axis="y", ls=":", alpha=0.5)
    for r, val, item in zip(bars, ratios, items):
        ax.annotate(f"×{val:.3f}\n({item[3].format(float(item[1]))} → {item[3].format(float(item[2]))})",
                    (r.get_x() + r.get_width() / 2, r.get_height()),
                    ha="center", va="bottom", fontsize=9)
    ax.set_ylim(0, max(ratios) * 1.32)
    fig.text(0.5, -0.06,
             "注：Sim/Obs 为冻结口径（LTA 观测段 → MATSim 必用 Q_sim,g=Σ_{l∈M_g}Q_l），×0.767 表示流量对账变差；"
             "拥堵/饱和/延误按 08–09 it.19。E-CAP-01 为旁路演示，非 v1.1、非正式基线。",
             ha="center", fontsize=9, color="#555555")
    p3 = FIGS / "fig3_metrics_ratio_bars.png"
    fig.savefig(p3, bbox_inches="tight", facecolor="white", dpi=150)
    plt.close(fig)
    print("   ->", p3)

    print("done.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
