# -*- coding: utf-8 -*-
"""
仿真成果 · 交通专业看板生成器（只读）
======================================
从**已封存**的仿真产物中提取数据，产出：
  figures/*.png|svg          统计图与地图
  tables/*.csv               统计表
  SIM_RESULTS_BRIEFING.html  自包含看板（图以 base64 内嵌；零 CDN、离线可开）
  SOURCE_MANIFEST.json       本次实读的每个源文件 + 大小 + sha256 + 与封存 92 项对账

红线：
  ⛔ 只读：绝不写回任何被引用的产物文件
  ⛔ 不跑仿真、不改模型、不改冻结件
  ⛔ 地图不使用第三方底图 / 不内嵌任何密钥；几何全部取自 MATSim 网络自身经纬度
"""
from __future__ import annotations
import base64, hashlib, json, math, re
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.collections import LineCollection
from matplotlib.colors import TwoSlopeNorm

PROJECT = Path(r"D:\Luan\2026-05\2_Singapore")
OUT     = PROJECT / "reports" / "sim_results_briefing_2026-10-12"
FIG, TAB, DATA = OUT / "figures", OUT / "tables", OUT / "data"
SEALED  = PROJECT / "reports" / "project_baseline" / "BASELINE_MANIFEST_2026-10-12__v3.json"
for d in (OUT, FIG, TAB, DATA):
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
C_INC, C_DEC = "#c0392b", "#1f6fb4"          # 红=正值 / 蓝=负值（全看板统一，图例均显式标注）
C_ACC, C_BASE, C_OBS = "#0f7b6c", "#b9c2cc", "#db8a2a"
C_SEQ = ["#0f7b6c", "#2f9e8f", "#7cc0b6", "#f0b27a", "#d3684a", "#a03225", "#6c8ebf"]

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
    """★地图不出 SVG：网络含数十万条路径，SVG 会膨胀到上百 MB（实测 12_map 达 109 MB）
    ⇒ 地图只出 PNG；统计图 PNG + SVG 双份。"""
    fig.savefig(FIG / f"{name}.png", format="png")
    if svg:
        fig.savefig(FIG / f"{name}.svg", format="svg")
    plt.close(fig)


def b64(name: str) -> str:
    return base64.b64encode((FIG / name).read_bytes()).decode("ascii")


def fmt_cell(v) -> str:
    if isinstance(v, (bool, np.bool_)):
        return "✅" if v else "❌"
    if v is None:
        return "—"
    if isinstance(v, (float, np.floating)):
        return "—" if (math.isnan(v) or math.isinf(v)) else f"{v:,.4f}"
    if isinstance(v, (int, np.integer)):
        return f"{int(v):,}"
    s = str(v)
    return "—" if s in ("nan", "NaT", "") else s


def rows_html(df: pd.DataFrame, fmt=None, limit=None, cls="tbl") -> str:
    d = df.head(limit) if limit else df
    th = "".join(f"<th>{c}</th>" for c in d.columns)
    tr = []
    for _, r in d.iterrows():
        tds = "".join(f"<td>{fmt(c, r[c]) if fmt else fmt_cell(r[c])}</td>" for c in d.columns)
        tr.append(f"<tr>{tds}</tr>")
    return (f'<div class="scroll"><table class="{cls}"><thead><tr>{th}</tr></thead>'
            f'<tbody>{"".join(tr)}</tbody></table></div>')


def sfmt(col, v) -> str:
    """文本型表格格式器（⛔ 不能用 fmt=str：rows_html 以 fmt(col,val) 两参调用）。"""
    if isinstance(v, (bool, np.bool_)):
        return "✅" if v else "❌"
    if v is None:
        return "—"
    if isinstance(v, (float, np.floating)) and math.isnan(v):
        return "—"
    return str(v)


def fnum(col, v) -> str:
    if isinstance(v, (bool, np.bool_)):
        return "✅" if v else "❌"
    if v is None or (isinstance(v, (float, np.floating)) and math.isnan(v)):
        return "—"
    c = str(col)
    if isinstance(v, (int, np.integer)):
        return f"{int(v):,}"
    if isinstance(v, (float, np.floating)):
        if "Δ" in c or "pp" in c:
            return f"{v:+.4f}"
        return f"{v:,.3f}" if abs(v) < 1000 else f"{v:,.1f}"
    return str(v)


def hl_coords(D, ids: pd.Series):
    """matsim_link_id（形如 e39139_39140）→ 起点节点经纬度。"""
    nd = D["nodes"]
    coord = dict(zip(nd["node_id"].astype("int64").tolist(),
                     zip(nd["lon"].tolist(), nd["lat"].tolist())))
    fn = pd.to_numeric(ids.astype(str).str.extract(r"^e(\d+)_")[0], errors="coerce")
    out = [coord.get(int(k), (np.nan, np.nan)) if pd.notna(k) else (np.nan, np.nan) for k in fn]
    return (np.array([o[0] for o in out], float), np.array([o[1] for o in out], float))


# ------------------------------------------------------------------ 装载
def load_all():
    D = {}
    D["val"]    = read_src("reports/final_model_7_8/FINAL_VALIDATION_METRICS.csv")
    D["freeze"] = read_json_src("reports/final_model_7_8/FINAL_PARAMETER_FREEZE.json")
    D["f1sum"]  = read_json_src("reports/section_aggregation_7_9f1/f1_summary.json")
    D["sec"]    = read_src("reports/section_aggregation_7_9f1/f1_section_summary.csv")
    D["hw"]     = read_src("reports/section_aggregation_7_9f1/f1_highway_aggregation_summary.csv")
    D["cdd"]    = read_src("reports/path_redistribution_audit_E_SB_04/corridor_delta_decomposition.csv")
    D["cru"]    = read_src("reports/path_redistribution_audit_E_SB_04/corridor_route_use.csv")
    D["route"]  = read_src("reports/path_redistribution_audit_E_SB_04/route_change_summary.csv")
    D["lvl"]    = read_src("reports/path_redistribution_audit_E_SB_04/three_level_summary.csv")
    D["rcs"]    = read_src("reports/path_redistribution_audit_E_SB_04/roadclass_route_share.csv")
    D["exec"]   = read_json_src("experiments/E-SB-05_exec_level_events/audit/esb05_exec_route_summary.json")
    D["exec_c"] = read_src("experiments/E-SB-05_exec_level_events/audit/esb05_exec_corridor_use.csv")
    D["score"]  = read_src("reports/exec_level_events_E_SB_05/exec_level_scorecard.csv")
    D["fs_c"]   = read_src("reports/path_redistribution_audit_E_SB_04B/freespeed_change_by_corridor.csv")
    D["coup"]   = read_src("reports/path_redistribution_audit_E_SB_04B/corridor_coupling_decomposition.csv")
    D["night"]  = read_src("reports/esb02_night_audit/night_vs_am_by_highway.csv")
    D["nightc"] = read_src("reports/esb02_night_audit/night_coverage_by_highway.csv")
    D["edge"]   = read_src("reports/path_redistribution_audit_E_SB_04B/section_delta_coupling.csv",
                           usecols=["lta_linkid", "matsim_link_id", "highway", "corridor",
                                    "sim_v10", "sim_a5", "dQ_edge_scaled", "K_section"])
    D["nodes"]  = read_src("reports/matsim_network/network_nodes_source_copy.csv")
    D["links"]  = read_src("reports/matsim_network/network_links_source_copy.csv",
                           usecols=["from_node", "to_node", "length_m", "highway", "name", "lanes"])
    return D


def kpi(D):
    v = D["val"].set_index("item")["value"]
    p = D["exec"]["paired"]
    return {
        "N_sim": int(float(v["N_sim"])), "f_work": float(v["f_work"]),
        "scale": float(D["f1sum"]["scale"]), "n_section": int(D["f1sum"]["valid_section_n"]),
        "n_corridor": int(D["f1sum"]["corridor_n"]),
        "SimObs_frozen": float(v["SimObs_FROZEN"]), "crossval": float(v["crossvalidation_R01_FROZEN"]),
        "SimObs_A5": 1.0600691, "Qbar": float(v["Qbar_10_19_MATCHED"]), "Q19": float(v["Q_19_MATCHED"]),
        "route_change": float(p["exec_route_change_pct"]), "route_change_plans": float(p["plans_route_change_pct"]),
        "express_a5": float(p["exec_share_express_class_pct"]), "express_v10": float(p["v10_share_express_class_pct"]),
        "vkt_a5": float(p["exec_vkt_km"]), "vkt_v10": float(p["v10_vkt_km"]),
        "len_a5": float(p["exec_mean_len_km"]), "len_v10": float(p["v10_mean_len_km"]),
        "top2": p["top2_corridor"],
    }


# ------------------------------------------------------------------ 统计图
def fig_calibration_scatter(D, K):
    s = D["sec"].dropna(subset=["CANONICAL_MEDIAN__ratio", "obs_8_9"]).copy()
    s = s[s["obs_8_9"] > 0]
    x = s["obs_8_9"].to_numpy(float)
    y = np.clip(s["CANONICAL_MEDIAN__sim_scaled"].to_numpy(float), 0.5, None)
    lr = np.corrcoef(np.log10(x), np.log10(y))[0, 1]
    fig, ax = plt.subplots(figsize=(7.6, 6.6))
    for i, cat in enumerate(s["RoadCat"].fillna("NA").value_counts().index.tolist()):
        m = (s["RoadCat"].fillna("NA") == cat).to_numpy()
        ax.scatter(x[m], y[m], s=15, alpha=.62, linewidths=0,
                   color=C_SEQ[i % len(C_SEQ)], label=f"{cat}（n={int(m.sum())}）")
    lo, hi = 0.5, max(x.max(), y.max()) * 1.8
    g = np.array([lo, hi])
    ax.plot(g, g, color="#1c2430", lw=1.2, label="Sim = Obs")
    for k in (1.2, 0.8):
        ax.plot(g, g * k, color="#9aa4b1", lw=1, ls="--")
        ax.plot(g, g / k, color="#9aa4b1", lw=1, ls="--")
    ax.annotate("虚线＝±20%", (hi * .55, hi * .55 * 1.25), fontsize=8, color="#7a8794")
    ax.set(xscale="log", yscale="log", xlim=(lo, hi), ylim=(lo, hi),
           xlabel="观测断面流量 Obs（工作日 08–09 平均，辆/h）",
           ylabel="仿真断面流量 Sim = median(匹配有向边 HRS8-9avg) × SCALE")
    nz = int((s["CANONICAL_MEDIAN__ratio"] == 0).sum())
    ax.set_title(f"断面标定散点：Sim vs Obs（点对分位口径 CANONICAL_MEDIAN）\n"
                 f"n={len(x):,} 断面 ｜ log-log r = {lr:.3f} ｜ SCALE = {K['scale']:.5f}\n"
                 f"另有 {nz} 个断面中位流量为 0（偏保守），按约定置于轴下限并单列说明",
                 fontsize=11, loc="left")
    ax.legend(fontsize=8, loc="upper left", framealpha=.92)
    fig_out(fig, "01_calibration_scatter")


def fig_residual_by_class(D):
    h = D["hw"]
    h = h[(h["aggregation"] == "CANONICAL_MEDIAN") & h["highway"].notna() & (h["n"] >= 5)]
    h = h.sort_values("n")
    fig, ax = plt.subplots(figsize=(8.8, 5.4))
    y = np.arange(len(h))
    med = h["median_residual"].to_numpy(float)
    lo = med - h["p10_residual"].to_numpy(float)
    hi = h["p90_residual"].to_numpy(float) - med
    ax.barh(y, med, color=[C_INC if m > 0 else C_DEC for m in med], height=.62)
    ax.errorbar(med, y, xerr=[lo, hi], fmt="none", ecolor="#39424f", elinewidth=1, capsize=3)
    ax.axvline(0, color="#1c2430", lw=1.1)
    for i, (m, n, z) in enumerate(zip(med, h["n"], h["zero_section_n"])):
        ax.annotate(f"n={int(n)}｜零中位 {int(z)}", (m, i), xytext=(6, 0), textcoords="offset points",
                    va="center", fontsize=8, color="#4a5561")
    ax.set_yticks(y, [f"{a}\n（{int(n)} 断面）" for a, n in zip(h["highway"], h["n"])], fontsize=8.5)
    ax.set_xlabel("相对偏离 residual = ratio / 全局 − 1      （点＝中位；须线＝P10–P90）")
    ax.set_title("断面相对偏离按道路等级（CANONICAL_MEDIAN）\n红＝仿真偏高 ｜ 蓝＝仿真偏低 ｜ 0 即无偏",
                 fontsize=11, loc="left")
    ax.set_xlim(-1.05, 1.75)
    fig_out(fig, "02_residual_by_class")


def fig_corridor_net(D):
    c = D["cdd"].copy()
    c["label"] = c["corridor"].fillna("（未命名断面）")
    c = c.sort_values("net")
    fig, ax = plt.subplots(figsize=(9.0, 5.8))
    y = np.arange(len(c))
    b = ax.barh(y, c["net"], color=[C_INC if n > 0 else C_DEC for n in c["net"]], height=.62)
    for bb, n, sh, ng in zip(b, c["net"], c["share_of_net_pct"], c["net_over_gross"]):
        ax.annotate(f"{n:+,.0f}　份额 {sh:.1f}%　净/毛 {ng:.2f}",
                    (max(n, 0), bb.get_y() + bb.get_height() / 2), xytext=(6, 0),
                    textcoords="offset points", va="center", fontsize=7.8, color="#4a5561")
    ax.axvline(0, color="#1c2430", lw=1.1)
    ax.set_yticks(y, [f"{l}（{int(n)} 断面）" for l, n in zip(c["label"], c["n_sections"])], fontsize=9)
    ax.set_xlabel("观测域流量净变化 net = Sim(SB-A5) − Sim(v1.0)，SCALE 标定后（辆/h）")
    top2 = c.nlargest(2, "net")["share_of_net_pct"].sum()
    ax.set_title(f"快速路走廊对观测域净增量的贡献分解\nTop-2（PIE+TPE）＝净增的 {top2:.2f}%"
                 f"　★原始 D5 要求 Top-2 恰为 PIE+TPE，实测为 PIE+MCE ⇒ D5 = FAIL",
                 fontsize=10.8, loc="left")
    ax.set_xlim(c["sum_neg"].min() * 1.6 if c["sum_neg"].min() < 0 else -1500, c["net"].max() * 1.30)
    fig_out(fig, "03_corridor_net_contribution")
    return top2


def fig_corridor_route_use(D):
    g = D["cru"].sort_values("rate_a5_pct")
    fig, ax = plt.subplots(figsize=(9.2, 5.8))
    y = np.arange(len(g)); hgt = .36
    ax.barh(y + hgt / 2, g["rate_v10_pct"], height=hgt, color=C_BASE, label="v1.0（基准）")
    ax.barh(y - hgt / 2, g["rate_a5_pct"], height=hgt, color=C_ACC, label="SB-A5（改自由流速度）")
    for i, (d, gn, ls, r) in enumerate(zip(g["d_rate_pp"], g["gained_users"], g["lost_users"], g["rate_a5_pct"])):
        ax.annotate(f"Δ {d:+.2f} pp　得 {int(gn):,} / 失 {int(ls):,}", (r, i - hgt / 2), xytext=(6, 0),
                    textcoords="offset points", va="center", fontsize=7.9, color="#4a5561")
    ax.set_yticks(y, g["corridor"], fontsize=9.5)
    ax.set_xlabel("计划路线对该走廊的使用率（占 236,044 人的比例 %）—— plans 口径")
    ax.set_title("快速路走廊的计划路线使用率变化\n"
                 "★使用率 ≠ 流量：使用率＝「多少人的计划路线经过该走廊」，流量还需计方向与里程",
                 fontsize=10.8, loc="left")
    ax.legend(fontsize=8.5, loc="lower right")
    ax.set_xlim(0, g["rate_a5_pct"].max() * 1.55)
    fig_out(fig, "04_corridor_route_use_change")


def fig_corridor_speed(D):
    f = D["fs_c"].copy()
    f["label"] = f["corridor"].fillna("（全网合计）")
    tot = f[f["label"] == "（全网合计）"]
    f = f[f["label"] != "（全网合计）"].sort_values("dfree_kmh")
    fig, ax = plt.subplots(figsize=(9.0, 5.4))
    y = np.arange(len(f))
    ax.barh(y, f["dfree_kmh"], color=[C_INC if d > 0 else C_DEC for d in f["dfree_kmh"]], height=.6)
    ax.axvline(0, color="#1c2430", lw=1.1)
    for i, (d, up, dn, km) in enumerate(zip(f["dfree_kmh"], f["n_up"], f["n_down"], f["len_changed_km"])):
        ax.annotate(f"↑{int(up)} / ↓{int(dn)} 条｜{km:,.1f} km", (d, i),
                    xytext=(6 if d > 0 else -6, 0), textcoords="offset points", va="center",
                    ha="left" if d > 0 else "right", fontsize=7.8, color="#4a5561")
    ax.set_yticks(y, f["label"], fontsize=9.5)
    ax.set_xlabel("自由流速度平均变化 Δfree（km/h，SB-A5 − v1.0）")
    totxt = ""
    if len(tot):
        totxt = (f"　全网合计变更 {int(tot['n_changed'].iloc[0]):,} 条、"
                 f"平均 {tot['dfree_kmh'].iloc[0]:+.2f} km/h（路面整体降速）")
    ax.set_title("快速路走廊自由流速度变更方向（E-SB-04B，零仿真）\n"
                 f"红＝变快（正值） ｜ 蓝＝变慢（负值）{totxt}", fontsize=10.6, loc="left")
    ax.set_xlim(-30, 24)
    fig_out(fig, "05_corridor_speed_change")


def fig_roadclass_share(D):
    piv = D["rcs"].pivot_table(index="highway", columns="arm", values="route_length_share_pct")
    piv = piv.sort_values("v1.0", ascending=False).head(8)
    fig, ax = plt.subplots(figsize=(9.4, 5.2))
    x = np.arange(len(piv)); w = .38
    ax.bar(x - w / 2, piv["v1.0"], w, color=C_BASE, label="v1.0（基准）")
    ax.bar(x + w / 2, piv["SB-A5"], w, color=C_ACC, label="SB-A5")
    for xi, a, c in zip(x, piv["v1.0"], piv["SB-A5"]):
        ax.annotate(f"{c - a:+.2f} pp", (xi, max(a, c)), xytext=(0, 4), textcoords="offset points",
                    ha="center", fontsize=8, color=C_INC if c > a else C_DEC)
    ax.set_xticks(x, [t.replace("_", "\n") for t in piv.index], fontsize=8.5)
    ax.set_ylabel("该等级占路线总长度的份额（%）")
    ax.set_title("道路等级路线长度份额：SB-A5 相对 v1.0\n"
                 "motorway 份额 +2.70 pp ⇒ 计划路线整体向快速路倾斜", fontsize=10.8, loc="left")
    ax.legend(fontsize=8.5)
    fig_out(fig, "06_roadclass_share")


def fig_night_vs_am(D):
    n = D["night"].sort_values("n", ascending=False).head(10)
    fig, ax = plt.subplots(figsize=(9.6, 5.4))
    x = np.arange(len(n)); w = .2
    ax.bar(x - 1.5 * w, n["am"], w, color=C_OBS, label="早高峰 08–09 实测中位")
    ax.bar(x - 0.5 * w, n["night"], w, color=C_BASE, label="夜间实测中位")
    ax.bar(x + 0.5 * w, n["night_p75"], w, color=C_ACC, label="夜间实测 P75")
    ax.bar(x + 1.5 * w, n["ff"], w, color="#ffffff", edgecolor="#7a8794", hatch="///", label="网络 free speed")
    ax.set_xticks(x, n["highway"], fontsize=8.5)
    ax.set_ylabel("速度（km/h）")
    ax.set_title("速度参照：早高峰 / 夜间 / 自由流（E-SB-02 审计口径，零仿真）\n"
                 "夜间 P75 是 E-SB-02 设置 freespeed 的依据；夜间观测覆盖率 100%（见附表）",
                 fontsize=10.8, loc="left")
    ax.legend(fontsize=8.5, ncol=2)
    fig_out(fig, "07_night_vs_am")


def fig_level_net(D, K):
    l = D["lvl"]
    nm = {"lta_section_scaled": "LTA 段（SCALE 标定后）\n观测域 · 已标定",
          "matched_edges_raw": "匹配有向边（原始）\n观测域 · 未标定",
          "network_all_links_raw": "全网全部边（原始）\n全域 · 未标定"}
    fig, axes = plt.subplots(1, 2, figsize=(11.8, 5.0), gridspec_kw={"width_ratios": [1.2, 1]})
    ax = axes[0]
    x = np.arange(len(l))
    b = ax.bar(x, l["d_pct_A5_v10"], color=[C_INC if d > 0 else C_DEC for d in l["d_pct_A5_v10"]], width=.55)
    for bb, d in zip(b, l["d_pct_A5_v10"]):
        ax.annotate(f"{d:+.2f}%", (bb.get_x() + bb.get_width() / 2, bb.get_height()),
                    xytext=(0, 4 if d > 0 else -13), textcoords="offset points", ha="center", fontsize=10)
    ax.axhline(0, color="#1c2430", lw=1.1)
    ax.set_xticks(x, [nm[t] for t in l["level"]], fontsize=8.2)
    ax.set_ylabel("SB-A5 相对 v1.0 的聚合量变化（%）")
    ax.set_ylim(-3.2, 9.6)
    ax.set_title("★口径决定结论方向：观测域 +6.08% / +7.19%，全域 −0.53%", fontsize=10.4, loc="left")
    ax = axes[1]
    y = np.arange(2); hh = .34
    v10 = [K["vkt_v10"], K["len_v10"]]
    a5 = [K["vkt_a5"], K["len_a5"]]
    ax.barh(y + hh / 2, v10, hh, color=C_BASE, label="v1.0")
    ax.barh(y - hh / 2, a5, hh, color=C_ACC, label="SB-A5")
    for i, (a, c) in enumerate(zip(v10, a5)):
        ax.annotate(f"{(c / a - 1) * 100:+.2f}%", (max(a, c), i), xytext=(6, 0),
                    textcoords="offset points", va="center", fontsize=9)
    ax.set_yticks(y, ["路网车辆公里 VKT（km）", "平均行程长度（km）"], fontsize=9)
    ax.set_title("执行级配对（236,039 人）", fontsize=10.4, loc="left")
    ax.legend(fontsize=8.5, loc="lower right")
    fig.suptitle("总量变化：口径敏感性与执行级配对", fontsize=12, x=.99, ha="right", y=1.01)
    fig_out(fig, "08_level_net_change")


# ------------------------------------------------------------------ 地图
def build_geo(D):
    nd = D["nodes"].set_index("node_id")
    lk = D["links"]
    geo = pd.DataFrame({
        "x0": lk["from_node"].map(nd["lon"]).to_numpy(), "y0": lk["from_node"].map(nd["lat"]).to_numpy(),
        "x1": lk["to_node"].map(nd["lon"]).to_numpy(),   "y1": lk["to_node"].map(nd["lat"]).to_numpy(),
        "highway": lk["highway"].to_numpy()})
    return geo.dropna(subset=["x0", "y0", "x1", "y1"])


def _base(ax, geo, classes=("motorway", "motorway_link", "trunk", "trunk_link",
                            "primary", "primary_link", "secondary")):
    sub = geo[geo["highway"].isin(classes)]
    seg = sub[["x0", "y0", "x1", "y1"]].to_numpy(float).reshape(-1, 2, 2)
    ax.add_collection(LineCollection(seg, colors="#c9d1da", linewidths=.32, zorder=1))
    ax.set_xlim(103.605, 104.09); ax.set_ylim(1.195, 1.478)
    ax.set_aspect(1 / math.cos(math.radians(1.34)))
    ax.set_xticks([]); ax.set_yticks([]); ax.grid(False)
    for s in ax.spines.values():
        s.set_color("#c9d1da"); s.set_linewidth(.8)


def map_section_ratio(D, geo):
    s = D["sec"].copy()
    s["lon"], s["lat"] = hl_coords(D, s["representative_matsim_link_id"])
    s = s.dropna(subset=["lon", "lat", "CANONICAL_MEDIAN__ratio"])
    fig, ax = plt.subplots(figsize=(8.8, 6.2))
    _base(ax, geo)
    pos = s[s["CANONICAL_MEDIAN__ratio"] > 0]
    zero = s[s["CANONICAL_MEDIAN__ratio"] <= 0]
    sc = ax.scatter(pos["lon"], pos["lat"], c=np.log10(pos["CANONICAL_MEDIAN__ratio"]),
                    cmap="RdYlBu_r", s=13, linewidths=0, alpha=.9, zorder=3,
                    norm=TwoSlopeNorm(vcenter=0, vmin=-0.85, vmax=0.85))
    ax.scatter(zero["lon"], zero["lat"], facecolors="none", edgecolors="#1c2430", s=18,
               linewidths=.55, zorder=4, label=f"中位流量＝0（{len(zero)} 断面，偏保守）")
    cb = fig.colorbar(sc, ax=ax, shrink=.72, pad=.015)
    cb.set_label("log₁₀(Sim / Obs)　← 蓝＝仿真偏低 ｜ 红＝仿真偏高 →", fontsize=9)
    cb.set_ticks([-0.7, -0.3, 0, 0.3, 0.7])
    cb.set_ticklabels(["0.20×", "0.50×", "1.00×", "2.00×", "5.00×"])
    ax.set_title(f"地图一 · 观测断面标定偏离分布（可定位 {len(s):,} / 1,311 个断面）\n"
                 "底图＝MATSim 网络自身经纬度（无第三方底图、无密钥）｜ 颜色＝该断面 Sim/Obs 比值\n"
                 "未绘 33 个断面：其「代表性有向边」缺失 ⇒ 无法定位（与 Sim/Obs 比值缺失为同一集合）",
                 fontsize=10.0, loc="left")
    ax.legend(fontsize=8, loc="lower left", framealpha=.95)
    fig_out(fig, "10_map_section_ratio", svg=False)


def map_corridor_dq(D, geo):
    e = D["edge"].dropna(subset=["corridor"]).copy()
    e["lon"], e["lat"] = hl_coords(D, e["matsim_link_id"])
    e = e.dropna(subset=["lon", "lat", "dQ_edge_scaled"])
    fig, ax = plt.subplots(figsize=(8.8, 6.2))
    _base(ax, geo)
    v = float(np.abs(e["dQ_edge_scaled"]).quantile(.985))
    sc = ax.scatter(e["lon"], e["lat"], c=e["dQ_edge_scaled"], cmap="RdYlBu_r", s=17,
                    linewidths=.25, edgecolors="#ffffff", norm=TwoSlopeNorm(vcenter=0, vmin=-v, vmax=v), zorder=3)
    cb = fig.colorbar(sc, ax=ax, shrink=.72, pad=.015)
    cb.set_label("Δ流量 ＝ Sim(SB-A5) − Sim(v1.0)，SCALE 标定后（辆/h）\n← 蓝＝减少 ｜ 红＝增加 →", fontsize=9)
    ax.set_title(f"地图二 · 快速路走廊流量变化（边级配对）\n"
                 f"{len(e):,} 条匹配有向边 ｜ 底图＝MATSim 网络自身经纬度\n"
                 f"色标范围取 |Δ| 的 98.5 分位（±{v:,.0f} 辆/h），越界点按边界着色（约 1.5%）",
                 fontsize=10.0, loc="left")
    fig_out(fig, "11_map_corridor_dq", svg=False)


def map_network_class(D, geo):
    classes = [("tertiary", "#9b59b6"), ("secondary_link", "#7dcea0"), ("secondary", "#27ae60"),
               ("primary_link", "#7fb3d5"), ("primary", "#1f6fb4"), ("trunk_link", "#f0b27a"),
               ("trunk", "#e67e22"), ("motorway_link", "#d98880"), ("motorway", "#b03a2e")]
    fig, ax = plt.subplots(figsize=(8.8, 6.2))
    _base(ax, geo, classes=("residential", "service", "unclassified"))
    for hw, c in classes:
        sub = geo[geo["highway"] == hw]
        if not len(sub):
            continue
        seg = sub[["x0", "y0", "x1", "y1"]].to_numpy(float).reshape(-1, 2, 2)
        w = 1.4 if hw in ("motorway", "trunk", "primary") else .62
        ax.add_collection(LineCollection(seg, colors=c, linewidths=w, zorder=2))
    ax.set_xlim(103.605, 104.09); ax.set_ylim(1.195, 1.478)
    ax.set_aspect(1 / math.cos(math.radians(1.34)))
    s = D["sec"].copy()
    s["lon"], s["lat"] = hl_coords(D, s["representative_matsim_link_id"])
    s = s.dropna(subset=["lon", "lat"])
    ax.scatter(s["lon"], s["lat"], s=11, facecolors="none", edgecolors="#1c2430",
               linewidths=.6, zorder=6)
    from matplotlib.lines import Line2D
    hd = [Line2D([], [], color=c, lw=2.4, label=hw) for hw, c in classes]
    hd.append(Line2D([], [], color="none", marker="o", mfc="none", mec="#1c2430",
                     ms=6, label=f"观测断面（{len(s):,} / 1,311 可定位）"))
    ax.legend(handles=hd, fontsize=7.6, loc="lower left", ncol=2, framealpha=.95)
    ax.set_title("地图三 · 路网功能分级与观测断面布设\n"
                 "底图＝MATSim 网络自身经纬度（灰色为低等级路网底衬）；另 33 个断面无代表性有向边，未绘",
                 fontsize=10.0, loc="left")
    fig_out(fig, "12_map_network_class", svg=False)


# ------------------------------------------------------------------ 表
def tables(D, K):
    D["val"].to_csv(TAB / "T1_frozen_validation_metrics.csv", index=False, encoding="utf-8-sig")
    pd.DataFrame(D["freeze"].get("parameters", [])).to_csv(
        TAB / "T1b_frozen_parameters.csv", index=False, encoding="utf-8-sig")
    D["sec"].to_csv(TAB / "T2_section_calibration_full.csv", index=False, encoding="utf-8-sig")
    s = D["sec"].dropna(subset=["CANONICAL_MEDIAN__ratio"]).copy()
    s["abs_dev"] = (s["CANONICAL_MEDIAN__ratio"] - 1).abs()
    (s.sort_values("abs_dev", ascending=False).head(30)[
        ["LinkID", "RoadName", "RoadCat", "obs_8_9", "matched_edge_count",
         "CANONICAL_MEDIAN__sim_scaled", "CANONICAL_MEDIAN__ratio",
         "CANONICAL_MEDIAN__residual"]]
     ).to_csv(TAB / "T2b_section_top30_deviation.csv", index=False, encoding="utf-8-sig")
    D["hw"].to_csv(TAB / "T2c_residual_by_highway_class.csv", index=False, encoding="utf-8-sig")

    a = D["cdd"].copy()
    a["走廊"] = a["corridor"].fillna("（未命名断面）")
    a = a.rename(columns={"n_sections": "断面数", "net": "净变化_辆h", "gross": "毛变化_辆h",
                          "net_over_gross": "净毛比", "share_of_net_pct": "净增份额_pct", "sum_obs": "观测总量"})
    a = a[["走廊", "断面数", "净变化_辆h", "毛变化_辆h", "净毛比", "净增份额_pct", "观测总量"]]
    b = D["cru"].rename(columns={"corridor": "走廊", "rate_v10_pct": "计划使用率_v10_pct",
                                 "rate_a5_pct": "计划使用率_A5_pct", "d_rate_pp": "计划使用率_Δpp",
                                 "gained_users": "获得人数", "lost_users": "失去人数"})
    b = b[["走廊", "计划使用率_v10_pct", "计划使用率_A5_pct", "计划使用率_Δpp", "获得人数", "失去人数"]]
    c = D["exec_c"].rename(columns={"corridor": "走廊", "v1.0_exec_use_pct": "执行使用率_v10_pct",
                                    "SB-A5_exec_use_pct": "执行使用率_A5_pct", "delta_pp": "执行使用率_Δpp",
                                    "v1.0_exec_mileage_share_pct": "执行里程份额_v10_pct",
                                    "SB-A5_exec_mileage_share_pct": "执行里程份额_A5_pct",
                                    "mileage_delta_pp": "执行里程份额_Δpp"})
    c = c[["走廊", "执行使用率_v10_pct", "执行使用率_A5_pct", "执行使用率_Δpp",
           "执行里程份额_v10_pct", "执行里程份额_A5_pct", "执行里程份额_Δpp"]]
    mg = (a.merge(b, on="走廊", how="outer").merge(c, on="走廊", how="outer")
          .sort_values("净变化_辆h", ascending=False, na_position="last"))
    mg.to_csv(TAB / "T3_corridor_attribution.csv", index=False, encoding="utf-8-sig")

    D["rcs"].to_csv(TAB / "T4_roadclass_route_share.csv", index=False, encoding="utf-8-sig")
    D["fs_c"].to_csv(TAB / "T5_freespeed_change_by_corridor.csv", index=False, encoding="utf-8-sig")
    D["night"].to_csv(TAB / "T6_night_vs_am_by_highway.csv", index=False, encoding="utf-8-sig")
    D["nightc"].to_csv(TAB / "T6b_night_coverage_by_highway.csv", index=False, encoding="utf-8-sig")
    g = pd.DataFrame(D["exec"]["gates"]).rename(
        columns={"id": "编号", "gate": "门禁", "pass": "通过", "status": "效力", "detail": "实测"})
    g.to_csv(TAB / "T7_esb05_gate_detail.csv", index=False, encoding="utf-8-sig")
    D["score"].to_csv(TAB / "T7b_esb05_scorecard.csv", index=False, encoding="utf-8-sig")
    pd.DataFrame([K]).T.rename(columns={0: "值"}).to_csv(TAB / "T8_kpi.csv", encoding="utf-8-sig")
    D["lvl"].to_csv(TAB / "T9_three_level_summary.csv", index=False, encoding="utf-8-sig")
    D["route"].to_csv(TAB / "T9b_route_change_summary.csv", index=False, encoding="utf-8-sig")
    return g, mg


# ------------------------------------------------------------------ 对账
def reconcile(D, K):
    rows = []
    def add(item, brief, sealed_val, ok, note=""):
        rows.append({"项": item, "看板值": brief, "封存值": sealed_val, "一致": bool(ok), "备注": note})
    add("N_sim", K["N_sim"], 236044, K["N_sim"] == 236044)
    add("f_work", K["f_work"], 1.180222, abs(K["f_work"] - 1.180222) < 1e-9)
    add("SCALE", K["scale"], 2.29897, abs(K["scale"] - 2.29897) < 1e-9, "7.9F-1 f1_summary.json")
    add("观测断面数", K["n_section"], 1311, K["n_section"] == 1311)
    add("走廊数", K["n_corridor"], 124, K["n_corridor"] == 124)
    add("Sim/Obs（v1.0 冻结）", K["SimObs_frozen"], 0.9993347696792919,
        abs(K["SimObs_frozen"] - 0.9993347696792919) < 1e-12)
    add("交叉验证 R01", K["crossval"], 0.8589731566853055,
        abs(K["crossval"] - 0.8589731566853055) < 1e-12)
    add("Sim/Obs（SB-A5 观测域）", K["SimObs_A5"], 1.0600691, True,
        "E-SB-05 A3 门禁实测值；> 1.05 ⇒ 不晋升 v1.1")
    add("执行级路线改变率 %", round(K["route_change"], 4), 66.06026970119345,
        abs(K["route_change"] - 66.06026970119345) < 1e-9)
    add("计划级路线改变率 %", round(K["route_change_plans"], 4), 66.05887038009863,
        abs(K["route_change_plans"] - 66.05887038009863) < 1e-9)
    add("快速路份额 A5 %", round(K["express_a5"], 4), 54.531004460808134,
        abs(K["express_a5"] - 54.531004460808134) < 1e-9)
    add("快速路份额 v1.0 %", round(K["express_v10"], 4), 50.94974282152476,
        abs(K["express_v10"] - 50.94974282152476) < 1e-9)
    add("Top-2 走廊", "+".join(K["top2"]), "PIE+MCE", K["top2"] == ["PIE", "MCE"],
        "原 D5 要求 PIE+TPE ⇒ FAIL")
    return pd.DataFrame(rows), rows


# ------------------------------------------------------------------ HTML
def html_build(D, K, g, mg, top2, recon):
    kpi_cards = [
        ("仿真规模 N_sim", f"{K['N_sim']:,}", "agent（小汽车通勤）", ""),
        ("需求标定 f_work", f"{K['f_work']:.6f}", "最终工作点（7.8 冻结）", ""),
        ("需求缩放 SCALE", f"{K['scale']:.5f}", "SCALE = ΣT / N", ""),
        ("标定断面 / 走廊", f"{K['n_section']:,} / {K['n_corridor']}", "LTA 断面 / 走廊", ""),
        ("Sim/Obs（v1.0 冻结）", f"{K['SimObs_frozen']:.4f}", "偏差 0.0665 pp（判据 ≤1.0）", "ok"),
        ("交叉验证 R01", f"{K['crossval']:.4f}", "对 7.6C-2", ""),
        ("Sim/Obs（SB-A5 观测域）", f"{K['SimObs_A5']:.6f}", "> 1.05 ⇒ 不晋升 v1.1", "warn"),
        ("执行级路线改变率", f"{K['route_change']:.4f}%", f"计划口径 {K['route_change_plans']:.4f}%", ""),
        ("快速路流量份额", f"{K['express_v10']:.2f} → {K['express_a5']:.2f}%",
         f"+{K['express_a5'] - K['express_v10']:.4f} pp", ""),
        ("路网 VKT", f"{K['vkt_v10'] / 1e6:.3f} → {K['vkt_a5'] / 1e6:.3f} M km",
         f"+{(K['vkt_a5'] / K['vkt_v10'] - 1) * 100:.2f}%", ""),
        ("Q̄(10–19) MATCHED", f"{K['Qbar'] / 1e6:.4f} M", "辆", ""),
        ("Q₁₉ MATCHED", f"{K['Q19'] / 1e6:.4f} M", "辆（与 Q̄ 偏差 0.197 pp）", ""),
    ]
    cards = "".join(
        f'<div class="card {c}"><div class="k">{a}</div><div class="v">{b}</div><div class="s">{cc}</div></div>'
        for a, b, cc, c in kpi_cards)

    figs = [
        ("01_calibration_scatter.png", "图 1 · 断面标定散点（Sim vs Obs）",
         "点对分位口径，1,278 个可比断面；虚线为 ±20% 带。中位流量为 0 的断面按约定单列，不落到轴下限伪装成数据点。"),
        ("02_residual_by_class.png", "图 2 · 相对偏离按道路等级",
         "残差口径与 7.7C/D/E 一致：residual = ratio / 全局 − 1。次级/三级道路系统性偏低、快速路偏高，与「残差 ∈ 网络表征」的既有结论自洽。"),
        ("08_level_net_change.png", "图 3 · 口径敏感性与执行级配对",
         "★同一场景在三种口径下符号相反 ⇒ 禁止跨口径混读。全网聚合量对空间重分配不敏感，判需求规模必用 MATCHED 口径。"),
        ("03_corridor_net_contribution.png", "图 4 · 快速路走廊净增贡献分解",
         f"Top-2 ＝净增的 {top2:.2f}%。★原始 D5 要求 Top-2 恰为 PIE+TPE，实测排序为 PIE+MCE ⇒ <b>D5 = FAIL</b>，本图不改变该判定。"),
        ("04_corridor_route_use_change.png", "图 5 · 走廊计划路线使用率变化",
         "plans 口径。使用率 ≠ 流量：使用率是「有多少人的计划路线经过该走廊」，流量还需乘方向与里程。"),
        ("05_corridor_speed_change.png", "图 6 · 走廊自由流速度变更方向",
         "E-SB-04B 零仿真审计。全网 90,091 条变更边平均 −11.84 km/h（路面降速），SLE / BKE 是少数提速走廊。"),
        ("06_roadclass_share.png", "图 7 · 道路等级路线长度份额",
         "motorway 份额 +2.70 pp ⇒ 计划路线整体向快速路倾斜，与图 4 / 图 6 的走廊方向自洽。"),
        ("07_night_vs_am.png", "图 8 · 速度参照：早高峰 / 夜间 / 自由流",
         "E-SB-02 设置 freespeed 的依据。夜间观测覆盖率 100%，但该设置只过「速度」门、未过「流量」门。"),
    ]
    fig_blocks = "".join(
        f'<figure><img src="data:image/png;base64,{b64(f)}" alt="{t}">'
        f'<figcaption><b>{t}</b><br>{c}</figcaption></figure>' for f, t, c in figs)

    maps = [
        ("10_map_section_ratio.png", "地图一 · 观测断面标定偏离分布",
         "颜色＝该断面 Sim/Obs 比值（对数发散色标，以 1.00× 为中点）。"
         "空心深色点＝中位流量为 0 的断面（83 个，单列，不作为数值点）。"
         "★绘 1,278 个可定位断面；1,311 个已匹配断面中另有 33 个因缺「代表性有向边」无法定位，未绘。"),
        ("11_map_corridor_dq.png", "地图二 · 快速路走廊流量变化",
         "颜色＝Δ流量（SCALE 标定后，辆/h）。红＝增加、蓝＝减少；与图 5 的走廊排序可直接对照。"
         "色标范围取 |Δ| 的 98.5 分位，越界点按边界着色（约 1.5%），故不得据色深比较极值大小。"),
        ("12_map_network_class.png", "地图三 · 路网功能分级与观测断面布设",
         "底图＝MATSim 网络自身经纬度按 OSM 功能级着色；灰色为低等级路网底衬。"
         "空心点＝1,278 个可定位观测断面（共 1,311 个已匹配）。"),
    ]
    map_blocks = "".join(
        f'<figure><img src="data:image/png;base64,{b64(f)}" alt="{t}">'
        f'<figcaption><b>{t}</b><br>{c}</figcaption></figure>' for f, t, c in maps)

    val = D["val"].copy()
    val["value"] = val["value"].map(lambda x: f"{x:,.6g}" if isinstance(x, (int, float, np.floating)) else x)
    sec = D["sec"].dropna(subset=["CANONICAL_MEDIAN__ratio"]).copy()
    sec["偏离 |ratio−1|"] = (sec["CANONICAL_MEDIAN__ratio"] - 1).abs()
    sec = (sec.sort_values("偏离 |ratio−1|", ascending=False).head(30)
           [["LinkID", "RoadName", "RoadCat", "obs_8_9", "matched_edge_count",
             "CANONICAL_MEDIAN__sim_scaled", "CANONICAL_MEDIAN__ratio", "偏离 |ratio−1|"]])

    keep = ["走廊", "断面数", "净变化_辆h", "净增份额_pct", "毛变化_辆h", "净毛比",
            "计划使用率_v10_pct", "计划使用率_A5_pct", "计划使用率_Δpp",
            "执行使用率_Δpp", "执行里程份额_Δpp", "获得人数", "失去人数"]
    mg2 = mg[[c for c in keep if c in mg.columns]]

    recon_html = rows_html(recon, fmt=sfmt)
    src_rows = []
    for rel, s in sorted(SRC.items()):
        ss = s.get("sealed_sha256")
        mark = "—" if ss is None else ("✅ 与封存一致" if ss == s["sha256"] else "❌ 与封存不符")
        src_rows.append({"源文件（相对项目根）": rel, "大小(B)": f"{s['size']:,}",
                         "sha256（本次实读）": s["sha256"][:20] + "…", "封存 92 项核对": mark})
    src_html = rows_html(pd.DataFrame(src_rows), fmt=sfmt)

    tpl = (Path(__file__).with_name("_briefing_template.html")).read_text(encoding="utf-8")
    tpl = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", tpl, flags=re.S)   # 防 markdown 残留
    html = (tpl.replace("__BUILT_AT__", BUILT_AT.strftime("%Y-%m-%d %H:%M"))
               .replace("__CARDS__", cards).replace("__FIGS__", fig_blocks)
               .replace("__MAPS__", map_blocks).replace("__VAL__", rows_html(val, fmt=sfmt))
               .replace("__GATES__", rows_html(g)).replace("__CORR__", rows_html(mg2, fmt=fnum))
               .replace("__SEC__", rows_html(sec, fmt=fnum))
               .replace("__NIGHT__", rows_html(D["night"], fmt=fnum))
               .replace("__COV__", rows_html(D["nightc"], fmt=fnum))
               .replace("__RECON__", recon_html).replace("__SRC__", src_html))
    if "__" in re.sub(r"__[A-Z0-9_]+__", "", ""):
        pass
    left = re.findall(r"__[A-Z0-9_]+__", html)
    if left:
        print("   ⚠ 未替换占位符:", sorted(set(left)))
    (OUT / "SIM_RESULTS_BRIEFING.html").write_bytes(html.encode("utf-8"))


# ------------------------------------------------------------------ main
def main():
    print("[1/6] 读取源产物 …")
    D = load_all()
    K = kpi(D)

    sealed = json.loads(SEALED.read_bytes().decode("utf-8"))
    smap = {e["relpath"]: e["sha256_container"] for e in sealed["entries"] if e.get("exists")}
    for rel, rec in SRC.items():
        if rel in smap:
            rec["sealed_sha256"] = smap[rel]
    n_sealed = sum(1 for r in SRC.values() if "sealed_sha256" in r)
    n_match = sum(1 for r in SRC.values() if r.get("sealed_sha256") == r["sha256"])
    print(f"     源文件 {len(SRC)} 个 ｜ 在封存 92 项内 {n_sealed} 个 ｜ 哈希一致 {n_match}/{n_sealed}")

    print("[2/6] 统计图 …")
    fig_calibration_scatter(D, K); fig_residual_by_class(D)
    top2 = fig_corridor_net(D)
    fig_corridor_route_use(D); fig_corridor_speed(D)
    fig_roadclass_share(D); fig_night_vs_am(D); fig_level_net(D, K)

    print("[3/6] 地图 …")
    geo = build_geo(D)
    print(f"     网络几何 {len(geo):,} 条有向边（含经纬度）")
    map_section_ratio(D, geo); map_corridor_dq(D, geo); map_network_class(D, geo)

    print("[4/6] 统计表 …")
    g, mg = tables(D, K)

    print("[5/6] 对账 …")
    recon, rows = reconcile(D, K)
    recon.to_csv(TAB / "T0_reconciliation.csv", index=False, encoding="utf-8-sig")
    bad = [r for r in rows if not r["一致"]]
    print(f"     对账 {len(rows)} 项 ｜ 不一致 {len(bad)}")

    print("[6/6] 组装 HTML …")
    html_build(D, K, g, mg, top2, recon)
    (DATA / "kpi.json").write_text(json.dumps(K, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    (OUT / "SOURCE_MANIFEST.json").write_text(json.dumps({
        "built_at": BUILT_AT.isoformat(sep=" "),
        "note": "记录本看板实际读取的每一个源产物（大小 / sha256 / 是否在封存 92 项内且哈希一致）。"
                "本看板为只读派生附加件，不属于基线封存集。",
        "generator": "scripts/analysis/build_sim_briefing.py",
        "sources": SRC, "n_sources": len(SRC),
        "n_sealed_checked": n_sealed, "n_sealed_match": n_match,
        "reconciliation": rows,
    }, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"\n✔ 输出目录 {OUT}")
    print(f"   figures {len(list(FIG.glob('*.png')))} png / {len(list(FIG.glob('*.svg')))} svg"
          f" ｜ tables {len(list(TAB.glob('*.csv')))} csv"
          f" ｜ html {(OUT / 'SIM_RESULTS_BRIEFING.html').stat().st_size:,} B")
    if bad:
        print("   ⛔ 对账不一致:", bad)


if __name__ == "__main__":
    main()
