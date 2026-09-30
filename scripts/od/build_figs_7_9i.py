# -*- coding: utf-8 -*-
"""Step 7.9I · 图（零仿真只读）：走廊去尺度残差 + M1 分类构成

图 1  走廊级 `ratio_simobs` vs `K_c`（1:K 计数诊断）
        ── 若「1:K 计数」是唯一机制，点应落在 y = x 线上。
        落在 y ≪ x 的走廊 = 扣掉计数基数后**仍真实缺载**。
图 2  M1（133 节）后验分类构成（按 `Σobs` 加权）
"""
from __future__ import annotations

import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(r"D:\Luan\2026-05\2_Singapore")
OUT = ROOT / "reports" / "corridor_scale_audit_7_9i"
plt.rcParams.update({"font.size": 9, "axes.grid": True, "grid.alpha": 0.25,
                     "figure.facecolor": "white", "axes.facecolor": "white",
                     "font.sans-serif": ["Microsoft YaHei", "SimHei",
                                         "Noto Sans CJK SC", "DejaVu Sans"],
                     "axes.unicode_minus": False})

c = pd.read_csv(OUT / "corridor_scale_v10.csv", encoding="utf-8-sig")
d = pd.read_csv(OUT / "m1_cards_7_9ib.csv", encoding="utf-8-sig")

fig, (ax, bx) = plt.subplots(1, 2, figsize=(13.2, 5.4))

# ---------------- 图 1 ----------------
sub = c[(c.K_c.notna()) & (c.ratio_simobs.notna()) & (c.obs_flow > 0)].copy()
sz = 14 + 460 * (sub.obs_flow / sub.obs_flow.max()) ** 0.6
norm = sub.ratio_simobs / sub.K_c
col = np.where(norm < 0.5, "#b2182b", np.where(norm > 1.5, "#2166ac", "#7f7f7f"))
ax.scatter(sub.K_c, sub.ratio_simobs, s=sz, c=col, alpha=0.82,
           edgecolors="white", linewidths=0.6, zorder=3)
kk = np.linspace(2, 15, 50)
ax.plot(kk, kk, "--", color="#333333", lw=1.4, zorder=2,
        label="1:K 计数线  y = x  （偏差可被计数完全解释）")
ax.plot(kk, 0.5 * kk, ":", color="#b2182b", lw=1.2, zorder=2, label="y = 0.5x（真实缺载阈值）")

LAB = {
    "KALLANG PAYA LEBAR EXPRESSWAY TUNNEL": ("KPE 隧道", (10, -26)),
    "EAST COAST PARKWAY": ("ECP", (22, 22)),
    "KALLANG PAYA LEBAR EXPRESSWAY": ("KPE", (34, -6)),
    "PAN ISLAND EXPRESSWAY": ("PIE", (6, 34)),
    "SELETAR EXPRESSWAY": ("SLE", (4, 24)),
    "CENTRAL EXPRESSWAY": ("CTE", (34, 12)),
    "BUKIT TIMAH EXPRESSWAY": ("BKE", (6, 18)),
    "AYER RAJAH EXPRESSWAY": ("AYE", (2, 6)),
    "TAMPINES EXPRESSWAY": ("TPE", (20, -22)),
}
for nm, (lab, (dx, dy)) in LAB.items():
    r = sub[sub.RoadName == nm]
    if not len(r):
        continue
    x0, y0 = float(r.K_c.iloc[0]), float(r.ratio_simobs.iloc[0])
    red = (y0 / x0) < 0.5
    ax.annotate(lab, (x0, y0), xytext=(x0 + dx * 0.10, y0 + dy * 0.10),
                fontsize=8.5, fontweight="bold" if red else "normal",
                color="#b2182b" if red else "#333333",
                arrowprops=dict(arrowstyle="-", color="#999999", lw=0.7))
ax.set_xlabel("K_c ＝ 每 LTA 断面平均匹配的 MATSim 有向边数")
ax.set_ylabel("ratio_simobs ＝ Σsim(断面级累加×SCALE) / Σobs")
ax.set_title("① 走廊级 1:K 计数诊断（v1.0，气泡＝Σobs）\n"
             "落在 y≈x ⇒ 偏差=计数基数错配；落在 y << x ⇒ 真实缺载",
             fontsize=10.5)
ax.legend(fontsize=8, loc="upper left", framealpha=0.92)
ax.set_xlim(1.5, 15.5)

# ---------------- 图 2 ----------------
o = ["X1_CHAIN_DEFECT", "X2_RAMP_OR_STRUCTURE", "X3_PARALLEL_BYPASS",
     "X4_ISOLATED_FROM_MAIN_FLOW", "X0_UNEXPLAINED"]
o = [k for k in o if k in set(d.class_exploratory)]
cnt = [int((d.class_exploratory == k).sum()) for k in o]
obs = [float(d.loc[d.class_exploratory == k, "obs_8_9"].sum()) for k in o]
tot = float(d.obs_8_9.sum())
labs = [k.split("_", 1)[1].replace("_", " ") for k in o]
cols = ["#b2182b", "#ef8a62", "#fddbc7", "#4393c3", "#bbbbbb"]
y = np.arange(len(o))[::-1]
bx.barh(y, np.array(obs) / tot * 100, color=cols[:len(o)], edgecolor="white", height=0.62)
for yi, oi, ni, ki in zip(y, obs, cnt, o):
    bx.text(oi / tot * 100 + 1.0, yi, f"{oi/tot*100:.1f}%  ({ni} 节)",
            va="center", fontsize=9, fontweight="bold", color="#333333")
bx.set_yticks(y); bx.set_yticklabels(labs, fontsize=9)
bx.set_xlabel("占 M1 总观测流量 Σobs 的比例（%）")
bx.set_xlim(0, 82)
bx.set_title("② M1（133 节）后验分类构成 · 按 Σobs 加权\n"
             "（EXPLORATORY：冻结 M1-E 无区分度，见报告 §3.3）", fontsize=10.5)

fig.suptitle("Step 7.9I · 观测域尺度与局部可达性诊断（零仿真，v1.0 it.19）",
             fontsize=12, y=1.005)
fig.tight_layout()
p = OUT / "fig_7_9i_corridor_scale_and_m1.png"
fig.savefig(p, dpi=155, bbox_inches="tight")
print(f"[out] {p}")

# 附：控制台复核
print("panel1 n=", len(sub), " | norm<0.5 =", int((norm < 0.5).sum()))
print("panel2:", dict(zip(o, [f"{x/tot*100:.1f}%" for x in obs])))
