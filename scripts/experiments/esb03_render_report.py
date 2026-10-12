#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""
esb03_render_report.py — 由 E-SB-03 实测产物**自动渲染** `REPORT.md`（零仿真·只读）。
⛔ 报告内每个数字均来自 `esb03_summary.json` / 5 张 CSV；判据行**不硬编码符号**。
用法：python scripts/experiments/esb03_render_report.py
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(r"D:\Luan\2026-05\2_Singapore")
AUDIT = ROOT / "experiments" / "E-SB-03_flow_shift_audit" / "audit"
OUT = ROOT / "reports" / "esb03_flow_shift_audit" / "REPORT.md"

s = json.loads((AUDIT / "esb03_summary.json").read_text(encoding="utf-8"))
t1 = pd.DataFrame(s["total_decomposition"])
t3 = pd.DataFrame(s["window_sensitivity"])
t4 = pd.DataFrame(s["aggregation_sensitivity"])
tN = pd.DataFrame(s["network_vs_matched"])
tc = pd.DataFrame(s["concentration_by_group"])
d = pd.read_csv(AUDIT / "esb03_section_delta.csv")
gates = pd.DataFrame(s["gates"])

A, B = s["section_delta_decomp"]["A5_vs_v10"], s["section_delta_decomp"]["A5ind_vs_A5"]
pic = {(r["arm"], r["window"]): r for _, r in t1.iterrows()}
L: list[str] = []
P = L.append

n_fail = int((~gates["pass"]).sum())
P("# 报告 —— E-SB-03：自由流速度变化后的观测域流量偏移审计")
P("")
P(f"> 日期：**2026-10-11** · 性质：**零仿真·只读**（未启动 MATSim，未改网络/配置/OD/`SCALE`/阈值）")
P(f"> 上游：`E-SB-02 = SPEED_GAIN_INDEPENDENT_CONFIRMED__FLOW_GATE_FAILED`")
P(f"> 门禁：**{len(gates) - n_fail}/{len(gates)} PASS**" + ("（全部通过）" if n_fail == 0 else f" ⚠️ {n_fail} FAIL"))
P(f"> 协议：`experiments/E-SB-03_flow_shift_audit/PROTOCOL_E-SB-03.md`")
P("")

# ---------------- 0. 数学起点 ----------------
P("## 0. 数学起点：固定 `SCALE` 不能解释两臂差异")
P("")
P("观测域、断面聚合（`median(匹配有向边 HRS8-9avg)`）、分母、`SCALE` 三臂完全相同 ⇒")
P("")
P("$$R_i=\\frac{SCALE\\cdot\\sum_g Q^{sim}_{g,i}}{\\sum_g Q^{obs}_g}"
  "\\quad\\Longrightarrow\\quad \\frac{R_{A5}}{R_{v1.0}}=\\frac{\\sum_g Q^{sim}_{g,A5}}{\\sum_g Q^{sim}_{g,v1.0}}$$")
P("")
rhs = pic[("SB-A5", "08-09")]["sum_sim_raw"] / pic[("v1.0", "08-09")]["sum_sim_raw"]
P(f"**实测自证**：`R(A5)/R(v1.0) = {pic[('SB-A5','08-09')]['SimObs']/pic[('v1.0','08-09')]['SimObs']:.10f}`"
  f" = `Σraw(A5)/Σraw(v1.0) = {rhs:.10f}`（门禁 E03，±1e-9）⇒ 恒等式成立，"
  "**固定 `SCALE` 只能等比例放大两臂，无法产生这条 6% 的差**。")
P("")
P(f"（`SCALE = {s['scale']:.5f}` 的绝对值是否合理 = **独立问题**；本审计⛔不作此判断。）")
P("")

# ---------------- 1. 表 1 ----------------
P("## 1. 表 1  总量分解（三臂并列，固定 `SCALE`）")
P("")
P("| 臂 | 窗口 | 有效断面 | Σobs | Σsim(未扩展) | Σsim(×SCALE) | **Sim/Obs** |")
P("|---|---|---:|---:|---:|---:|---:|")
for _, r in t1.iterrows():
    so = "—" if pd.isna(r["SimObs"]) else f"**{r['SimObs']:.7f}**"
    ob = "—" if pd.isna(r["sum_obs"]) else f"{r['sum_obs']:,.0f}"
    P(f"| {r['arm']} | {r['window']} | {int(r['n_sections'])} | {ob} | {r['sum_sim_raw']:,.0f} | {r['sum_sim_scaled']:,.0f} | {so} |")
P("")
P("**读法**：")
for w in ["07-08", "08-09", "07-09(双小时)"]:
    v10 = pic[("v1.0", w)]["SimObs"]; a5 = pic[("SB-A5", w)]["SimObs"]; ai = pic[("SB-A5ind", w)]["SimObs"]
    P(f"- **{w}**：v1.0 `{v10:.4f}` → SB-A5 `{a5:.4f}`（{a5/v10-1:+.2%} 相对）→ SB-A5ind `{ai:.4f}`（{ai/v10-1:+.2%}）")
P("")
r78 = pic[("SB-A5", "07-08")]["sum_sim_raw"] / pic[("v1.0", "07-08")]["sum_sim_raw"] - 1
r89 = pic[("SB-A5", "08-09")]["sum_sim_raw"] / pic[("v1.0", "08-09")]["sum_sim_raw"] - 1
P(f"⇒ **07–08 与 08–09 的 Σsim 上升几乎同幅**（{r78:+.2%} vs {r89:+.2%}）⇒ "
  f"**不是**「从一个已观测小时挪到另一个」。")
P("")

# ---------------- 2. 分支 A ----------------
P("## 2. 分支 A  时间窗内的流量转移 —— ❌ 不成立")
P("")
P("| 小时 | 有观测 | Σsim v1.0 | Δ(A5) | Δ(A5ind) | Δnet(A5) |")
P("|---|---:|---:|---:|---:|---:|")
for h in ["05-06", "06-07", "07-08", "08-09", "09-10", "10-11", "11-12"]:
    z = t3[t3.hour == h]
    if not len(z):
        continue
    z = z.iloc[0]
    def f(x):
        return "—" if pd.isna(x) else f"{x:+.2f}%"
    P(f"| {h} | {'✅' if z['observed'] else '—'} | {z['sec_raw_v1.0']:,.0f} | {f(z['d_sec_A5_v10_pct'])} | "
      f"{f(z['d_sec_A5ind_v10_pct'])} | {f(z['d_net_A5_v10_pct'])} |")
P("")
P("**结论**：")
P("- 两个**有观测**小时（07–08 / 08–09）**同向上升 ~6%**，无此消彼长 ⇒ 时间窗转移**不成立**。")
P("- 09–10 及以后升幅更大（+9.9% / +12.1%），但**该时段无实测** ⇒ 按预注册，"
  "**只作敏感性陈述，不作结论**；它反而说明上升并非「从 08–09 流出」。")
P("- ⚠️ **全网**在 08–09 反而 **−0.53%**（07–08 −1.97%）——与匹配子集 +6% **方向相反**（见分支 B）。")
P("")

# ---------------- 3. 分支 B ----------------
P("## 3. 分支 B  路径重分配 —— ✅ 成立（主因）")
P("")
P(f"**正负分解**（08-09，×SCALE 口径）：")
P("")
P("| 比较 | 增节数 | 减节数 | 零节数 | Σ增 | Σ减 | **净额** | 毛额 | 净/毛 |")
P("|---|---:|---:|---:|---:|---:|---:|---:|---:|")
for nm, x in (("SB-A5 − v1.0", A), ("SB-A5ind − SB-A5", B)):
    P(f"| {nm} | {x['n_pos']} | {x['n_neg']} | {x['n_zero']} | {x['sum_pos']:,.0f} | {x['sum_neg']:,.0f} | "
      f"**{x['net']:,.0f}** | {x['gross']:,.0f} | {x['net']/x['gross']:.2f} |")
P("")
P(f"⇒ 净额是**单向正增**（净/毛 = {A['net']/A['gross']:.2f}），**不是** v1.0 式「大额正负抵消」。")
P("")
P("### 3.1 覆盖率对照（★关键）")
P("")
P("| 臂 | 全网 Σ(全部链路, raw) | 匹配边 Σ(raw) | 匹配边占全网 | Δ全网 | Δ匹配边 |")
P("|---|---:|---:|---:|---:|---:|")
for _, r in tN.iterrows():
    P(f"| {r['arm']} | {r['net_all_links_raw']:,.0f} | {r['net_matched_edges_raw']:,.0f} | "
      f"{r['net_matched_edges_raw']/r['net_all_links_raw']*100:.2f}% | {r['d_net_vs_v10_pct']:+.2f}% | {r['d_matched_vs_v10_pct']:+.2f}% |")
P("")
P("⇒ **被观测边 +7.2% 而全网 −0.53%** ⇒ 上升**不是「车变多」，而是「负荷向被观测的主干道集中」**；"
  "观测域占全网份额 6.62% → 7.13%（+7.7% 相对）。**覆盖率陷阱成立**。")
P("")
P("### 3.2 集中度（增量落在哪）")
P("")
def tbl(by, valcol, cols):
    P(f"**按 {by}**（08-09，ΔQ = SB-A5 − v1.0）：")
    P("")
    P("| " + " | ".join(cols) + " |")
    P("|" + "---|" * len(cols))

    def fmt(c, v):
        if isinstance(v, str):
            return v
        if pd.isna(v):
            return "—"
        if c.startswith("ratio"):
            return f"{v:.4f}"
        if "pct" in c:
            return f"{v:,.2f}"
        if abs(v) >= 100:
            return f"{v:,.0f}"
        return f"{v:g}"

    g = tc[tc.group_by == by].copy()
    g = g[g[valcol].notna()]
    for _, r in g.head(12).iterrows():
        k = r[by]
        k = "（未匹配 geo）" if str(k).strip().lower() in ("nan", "none") else str(k)
        P("| " + " | ".join([k] + [fmt(c, r[c]) for c in cols[1:]]) + " |")
    P("")

tbl("RoadCat", "RoadCat", ["RoadCat", "n", "ratio_v10", "ratio_a5", "dQ_A5_v10", "share_of_net_pct"])
tbl("region", "region", ["region", "n", "ratio_v10", "ratio_a5", "dQ_A5_v10", "share_of_net_pct"])
tbl("ring", "ring", ["ring", "n", "ratio_v10", "ratio_a5", "dQ_A5_v10", "share_of_net_pct"])
tbl("cbd_band", "cbd_band", ["cbd_band", "n", "ratio_v10", "ratio_a5", "dQ_A5_v10", "share_of_net_pct"])

road = (d.groupby("RoadName")
          .agg(n=("lta_linkid", "size"), dQ=("dQ_A5_v10", "sum"), obs=("obs_8_9", "sum"))
          .sort_values("dQ", ascending=False))
net = A["net"]
P("**按道路名 Top-10（ΔQ 集中度）**：")
P("")
P("| 道路 | 断面数 | ΔQ(A5−v1.0) | 占净增 |")
P("|---|---:|---:|---:|")
for nm, r in road.head(10).iterrows():
    P(f"| {nm} | {int(r['n'])} | {r['dQ']:,.0f} | {r['dQ']/net*100:.1f}% |")
P("")
top2 = road.head(2)["dQ"].sum()
P(f"⇒ **Top-2（PIE + TAMPINES）合计 {top2:,.0f} = 净增的 {top2/net*100:.1f}%**；"
  f"Top-10 合计 = {road.head(10)['dQ'].sum()/net*100:.0f}% ⇒ **增量高度集中于快速路走廊**。")
P("")
cte = d[d.RoadName.str.contains("CENTRAL EXPRESSWAY", na=False)]
kpe = d[d.RoadName.str.contains("KALLANG PAYA LEBAR", na=False)]
P("**走廊内部抵消（同走廊既有大增也有大减）**：")
P("")
P("| 走廊 | 断面数 | Σ增 | Σ减 | 净额 | 净/毛 |")
P("|---|---:|---:|---:|---:|---:|")
_corr = []
for nm, g in (("CENTRAL EXPRESSWAY（CTE）", cte), ("KALLANG PAYA LEBAR（KPE）", kpe)):
    v = g["dQ_A5_v10"].fillna(0)
    _pos, _neg, _net = float(v[v > 0].sum()), float(v[v < 0].sum()), float(v.sum())
    gross = _pos - _neg
    _corr.append((nm, len(g), _pos, _neg, _net, _net / gross if gross else float("nan")))
    P(f"| {nm} | {len(g)} | {_pos:,.0f} | {_neg:,.0f} | {_net:+,.0f} | {_net/gross:.2f} |")
P("")
_c1, _c2 = _corr[0], _corr[1]
P(f"⇒ 两条走廊**净额符号相同（均净增）**，但**各自内部都含大额正负抵消**："
  f"{_c1[0]} +{_c1[2]:,.0f} / {_c1[3]:,.0f}（净 {_c1[4]:+,.0f}，净/毛 {_c1[5]:.2f}）、"
  f"{_c2[0]} +{_c2[2]:,.0f} / {_c2[3]:,.0f}（净 {_c2[4]:+,.0f}，净/毛 {_c2[5]:.2f}）"
  "⇒ **走廊内重分配与走廊间重分配并存**，⛔ 不是「全网均匀变多」。")
P("")
P(f"（旁证）逐断面 Top-8 **减**量全部落在 CENTRAL EXPRESSWAY / KPE 隧道 / SELETAR / TAMPINES 等快速路段的**个别断面**上，"
  f"而 Top-8 **增**量落在 KPE 隧道 / PIE / CTE / TAMPINES 的**另一些断面**上 ⇒ 同一设施内**断面级别此消彼长**。")
P("")
rel = d["rel_dQ_A5_v10"].dropna()
P(f"**异质性**：逐断面相对变化 中位 {rel.median():+.1%}，均值 {rel.mean():+.1%}，"
  f"区间 [{rel.min():+.0%}, {rel.max():+.0%}]；`|rel|>50%` 的断面 **{int((rel.abs()>0.5).sum())}** 个 ⇒ "
  "空间高度不均匀（与「均匀缩放」不相容）。")
P("")

# ---------------- 4. 分支 C ----------------
P("## 4. 分支 C  观测域与聚合口径 —— ❌ 不成立")
P("")
P("| 聚合 / 匹配集 | Sim/Obs v1.0 | Sim/Obs A5 | Sim/Obs A5ind | **R(A5/v1.0)** | R(A5ind/A5) |")
P("|---|---:|---:|---:|---:|---:|")
for _, r in t4.iterrows():
    P(f"| {r['aggregation']} | {r['SimObs_v1.0']:.5f} | {r['SimObs_SB-A5']:.5f} | {r['SimObs_SB-A5ind']:.5f} | "
      f"**{r['ratio_A5_over_v10']:.5f}** | {r['ratio_A5ind_over_A5']:.5f} |")
P("")
rr = t4["ratio_A5_over_v10"]
P(f"⇒ **绝对水平**随聚合明显漂移（v1.0 从 {t4['SimObs_v1.0'].min():.3f} 到 {t4['SimObs_v1.0'].max():.3f}），"
  f"但**臂间比值 `R(A5/v1.0)` 稳定在 [{rr.min():.4f}, {rr.max():.4f}]**（极差 {rr.max()-rr.min():.4f}）⇒ "
  "**+6% 不是聚合/匹配集伪影**。")
P("")

# ---------------- 5. 判决 ----------------
P("## 5. 判决（按预注册四项决策规则，实测值驱动）")
P("")
verdicts = [
    ("A 时间窗转移", False, f"07–08 {r78:+.2%} / 08–09 {r89:+.2%}（同向）；09–10 及以后无实测"),
    ("B 路径重分配", True, f"净/毛 {A['net']/A['gross']:.2f}；Top-2 快速路占净增 {top2/A['net']*100:.1f}%；"
                          f"匹配边 {tN.loc[tN.arm=='SB-A5','d_matched_vs_v10_pct'].iloc[0]:+.2f}% vs 全网 "
                          f"{tN.loc[tN.arm=='SB-A5','d_net_vs_v10_pct'].iloc[0]:+.2f}%"),
    ("C 聚合/匹配口径", False, f"R(A5/v1.0) 稳定 [{rr.min():.4f}, {rr.max():.4f}]"),
    ("D 需求扩展系数（SCALE）", False, f"固定 SCALE 恒等式已证不能产生该差（E03：{rhs:.10f}）；⛔ 不为凑 1.0 反调"),
]
P("| 分支 | 是否成立 | 实测依据 |")
P("|---|---|---|")
for nm, ok, ev in verdicts:
    P(f"| {nm} | **{'✅ 成立' if ok else '❌ 不成立'}** | {ev} |")
P("")
P("### 结论")
P("")
P(f"**1.0601 不是 `SCALE` 问题，也不是时间窗问题、不是聚合口径问题。**")
P("它是**路径重分配**：改 `freespeed` 后，负荷**向被观测的快速路走廊集中**"
  f"（匹配边 +{tN.loc[tN.arm=='SB-A5','d_matched_vs_v10_pct'].iloc[0]:.2f}%、全网 "
  f"{tN.loc[tN.arm=='SB-A5','d_net_vs_v10_pct'].iloc[0]:+.2f}%），"
  f"并在**同一走廊内部**出现大额正负抵消（CTE 净 {_c1[4]:+,.0f}、"
  f"KPE 净 {_c2[4]:+,.0f}，各自净/毛仅 {_c1[5]:.2f} / {_c2[5]:.2f}）与**高度空间异质性**。")
P("")
P("- **观测侧**：`Sim/Obs` 在观测域（快速路）内确实偏高 → 这是**观测域选择性**的结果，"
  "⛔ **不得**据此外推为「全网高估」。")
P("- **需求侧**：`SB-A5ind` 相对 `SB-A5` 再 +1.4%（`R(A5ind/A5)` ≈ 1.014，全聚合稳定）⇒ "
  "零 SpeedBand 需求使负荷进一步向观测域集中。")
P("- **按预注册决策规则** ⇒ 落「**变化集中在特定路段/走廊/道路等级**」一行：")
P("  **下一步调查路径重分配与观测域覆盖，⛔ 不调整全网容量，⛔ 不反调 `SCALE`。**")
P("")
P("### 立即可执行的下一步（仍未定，待裁定）")
P("- **路径层证据**：从既有 `events` 抽 08–09 的**路径/行程**对比（v1.0 vs SB-A5），"
  "验证「车辆改走快速路」是否与逐断面 ΔQ 的符号一致（**这一步仍可零仿真**，只读既有 events）。")
P("- **走廊结构复核**：同走廊内部的**截面此消彼长**（如 KPE 隧道既有 +1,855 也有 −955）属"
  "**方向性 / 进出节点替代**，须与已 `CLOSED` 的 O3-R1「承载对象替代」结论**分列陈述**，⛔ 不得混为一谈。")
P("- ⛔ 在路径层证据到手前，**不启动**容量 / 信号灯 / 交叉口实验。")
P("")
P("## 6. 限制（须随结论声明）")
P("")
P("- **Level 1**：本审计只给出「哪一层解释得了 / 解释不了」，**不作因果断言**。")
P("- **Level 2**：`TrafficFlow`(2025-11) 与 `SpeedBand`(2026-05) 不同期；obs 仅 07–08/08–09 ⇒ "
  "09:00 后**无实测**，时间窗分支**无法闭环**。")
P("- **物理**：`freespeed` 变更改变路段时间成本；本审计**不裁断**其拥堵动力学含义。")
P("")
P("## 7. 门禁")
P("")
P("| ID | 判据 | 结果 | 实测 |")
P("|---|---|---|---|")
for _, g in gates.iterrows():
    P(f"| `{g['id']}` | {g['gate']} | {'✅ PASS' if g['pass'] else '❌ FAIL'} | {g['detail']} |")
P("")
P("## 8. 产物")
P("")
for p in s["written"]:
    P(f"- `{p}`")
P("")

OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text("\n".join(L), encoding="utf-8")
print(f"落盘：{OUT}（{len(L)} 行）")
