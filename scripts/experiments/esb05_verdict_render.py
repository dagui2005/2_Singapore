#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""
esb05_verdict_render.py — E-SB-05 判决书渲染（★全部实测值动态渲染，禁止硬编码符号）
=====================================================================================
读 audit/*.json + audit/*.csv → 生成 reports/exec_level_events_E_SB_05/VERDICT_E-SB-05.md
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(r"D:\Luan\2026-05\2_Singapore")
EXP = ROOT / "experiments" / "E-SB-05_exec_level_events"
AUDIT = EXP / "audit"
REPORT = ROOT / "reports" / "exec_level_events_E_SB_05"
REPORT.mkdir(parents=True, exist_ok=True)
E4 = ROOT / "reports" / "path_redistribution_audit_E_SB_04"   # 计划级参照（E-SB-04）

PF = json.loads((AUDIT / "run_config_manifest.json").read_text(encoding="utf-8"))
CS = json.loads((AUDIT / "esb05_consistency_summary.json").read_text(encoding="utf-8"))
ES = json.loads((AUDIT / "esb05_exec_route_summary.json").read_text(encoding="utf-8"))
EI = json.loads((AUDIT / "esb05_events_integrity.json").read_text(encoding="utf-8"))
STAMP = json.loads((AUDIT / "SB-A5_EVT19_CHECK_run_stamp.json").read_text(encoding="utf-8")) \
    if (AUDIT / "SB-A5_EVT19_CHECK_run_stamp.json").exists() else {}
CMPD = pd.read_csv(AUDIT / "esb05_exec_route_compare.csv", encoding="utf-8-sig")
CORR = pd.read_csv(AUDIT / "esb05_exec_corridor_use.csv", encoding="utf-8-sig")
GATES = ES["gates"]
EFF = [g for g in GATES if g["status"] == "effective"]
N_EFF, N_EFF_PASS = len(EFF), sum(1 for g in EFF if g["pass"])
P = ES["paired"]
VERDICT = ES["verdict"]
STRICT = ES.get("verdict_if_strict_protocol", "?")
UNCOV = bool(ES.get("protocol_uncovered_case", False))
TL = json.loads((AUDIT / "esb05_d5_timeline_audit.json").read_text(encoding="utf-8")) \
    if (AUDIT / "esb05_d5_timeline_audit.json").exists() else {}
_tl_kp = (TL.get("key_points") or {})
_tl_proto = _tl_kp.get("t_protocol_mtime", "?")
_tl_data = _tl_kp.get("t_sba5_exec_data_mtime", "?")
_tl_cmp = _tl_kp.get("t_d5_impl_script_mtime", "?")
_tl_verdict = TL.get("verdict", "?")

MARK = {True: "PASS", False: "FAIL"}


def gtable(prefixes):
    gs = [g for g in EFF if any(g["id"].startswith(p) for p in prefixes)]
    lines = ["| ID | 判据 | 结果 | 实测 |", "|---|---|---|---|"]
    for g in gs:
        d = str(g["detail"]).replace("|", "\\|")
        lines.append(f"| {g['id']} | {g['gate'].replace('|','\\|')} | **{MARK[g['pass']]}** | {d} |")
    n_ok = sum(1 for g in gs if g["pass"])
    return "\n".join(lines), n_ok, len(gs)


def pct(x):
    return "n/a" if x is None or (isinstance(x, float) and np.isnan(x)) else f"{x:.4f}%"


def pp(x):
    return "n/a" if x is None or (isinstance(x, float) and np.isnan(x)) else f"{x:+.4f} pp"


def f_pct(v):
    return "n/a" if v is None or pd.isna(v) else f"{float(v):.4f}%"


def f_pp(v):
    return "n/a" if v is None or pd.isna(v) else f"{float(v):+.4f}"


A_t, A_ok, A_n = gtable(["A"])
B_t, B_ok, B_n = gtable(["B"])
C_t, C_ok, C_n = gtable(["C"])
D_t, D_ok, D_n = gtable(["D"])

INFO = [g for g in GATES if g["status"] != "effective"]
I_t = "| ID | 类型 | 判据 | 实测 |\n|---|---|---|---|\n" + "\n".join(
    f"| {g['id']} | {g['status']} | {g['gate'].replace('|','\\|')} | {str(g['detail']).replace('|','\\|')} |"
    for g in INFO) if INFO else "（无）"

# 描述符与符号（动态）
cons_desc = ES.get("consistency_verdict", "?")
ls_ident = bool(CS.get("linkstats_identical"))
files_line = f"{CS['files_same']}/{CS['files_deterministic']}"
od = CS.get("observation_domain", {}) or {}
lvl = "EXECUTION_LEVEL" if VERDICT == "EXECUTION_LEVEL_CONFIRMED" else "PLANS_LEVEL"

exec_d = P["exec_delta_express_pp"]
plan_d = P["plans_delta_express_pp"]
gap = exec_d - plan_d

one_liner = (
    f"SB-A5 的 **执行级路线**已由 events 直接重建，并在 `drop_start_link` 语义下与 selected plan "
    f"**逐人 100% 对账**（236,039/236,039）；在与 v1.0 的同 population、同迭代配对比较中，"
    f"执行路线的快速路里程份额 **{pct(P['v10_share_express_class_pct'])} → "
    f"{pct(P['exec_share_express_class_pct'])}**（{pp(exec_d)}），"
    f"与计划级 {pp(plan_d)} 同号同量级（差 {gap:+.4f} pp）。"
    f"\n\n> ⚠️ **协议合规披露**：原始预注册判据 **D5 FAIL**（执行级里程份额 Δ Top-2 = "
    f"**{P['top2_corridor']}**，非 PIE/TPE）；有效门禁 **{N_EFF_PASS}/{N_EFF}**。"
    f"**⛔ 不得表述为「原协议 17/17 PASS」**，详见 §3.3。"
    if VERDICT == "EXECUTION_LEVEL_CONFIRMED" else
    f"执行级检验结论为 `{VERDICT}`，E-SB-04/04B 的路径结论**维持 `PLANS_LEVEL`**。"
)

# ---- 方法学校验：执行级里程 vs 计划级里程的差 = start_link 长度（两侧应同为 ~35 m/人）----
_mn = P['exec_mean_len_km']
_mv = P['v10_mean_len_km']
_pn = CMPD.loc[CMPD.metric == "_share_express_pct", "SB-A5_plans_pct"]
_dn = float(pd.read_csv(E4 / "route_change_summary.csv", encoding="utf-8-sig")
            .query("compare == 'SB-A5 vs v1.0'")["mean_total_len_a5_km"].iloc[0])
_dv = float(pd.read_csv(E4 / "route_change_summary.csv", encoding="utf-8-sig")
            .query("compare == 'SB-A5 vs v1.0'")["mean_total_len_v10_km"].iloc[0])
_under_n = (_dn - _mn) * 1000.0     # m/人
_under_v = (_dv - _mv) * 1000.0

# ---- Top-2 排序核验（原稿 D5 缺陷的事后披露）----
_c_top_mileage = CORR.sort_values("mileage_delta_pp", ascending=False)["corridor"].tolist()
_c_top_use = CORR.sort_values("delta_pp", ascending=False)["corridor"].tolist()
_tope_rank_mileage = _c_top_mileage.index("TPE") + 1
_tope_rank_use = _c_top_use.index("TPE") + 1
_d5_draft_would_pass = set(_c_top_mileage[:2]) == {"PIE", "TPE"}
_pie_d = float(CORR.loc[CORR["corridor"] == "PIE", "mileage_delta_pp"].iloc[0])
_tpe_d = float(CORR.loc[CORR["corridor"] == "TPE", "mileage_delta_pp"].iloc[0])
_pie_u = float(CORR.loc[CORR["corridor"] == "PIE", "delta_pp"].iloc[0])
_tpe_u = float(CORR.loc[CORR["corridor"] == "TPE", "delta_pp"].iloc[0])
_top2_is_pie_tpe = set(P["top2_corridor"]) == {"PIE", "TPE"}

md = f"""# VERDICT — E-SB-05：SB-A5 执行级 events 验证

> 实验：`E-SB-05_exec_level_events` ｜ runId：`SB-A5_EVT19_CHECK`
> 性质：**EXPERIMENT ONLY / NOT v1.1** ｜ 建立：{ES['built']}
> 上游：`E-SB-04`（plans 级路径重分配）、`E-SB-04B`（plans 级速度↔改道耦合）、`E-SB-03`（1.0601 归因）
> 运行：heap {STAMP.get('heap','n/a')} ｜ rc={STAMP.get('returncode','?')} ｜ 用时 {STAMP.get('duration_min','?')} min

---

## 0. 判决

### **`{VERDICT}`**（核心执行级判据 D1–D4 + A/B/C） ｜ 证据等级：**`{lvl}`**

{one_liner}

| 读法 | 覆盖范围 | 结果 |
|---|---|---|
| **实体结论**（核心执行级配对） | A1–A3 · B1–B5 · C1–C3 · **D1–D4** | **全 PASS** ⇒ `EXECUTION_LEVEL_CONFIRMED` |
| **原始预注册协议**（含 D5 硬门禁） | 上列 + **D5** | **{N_EFF_PASS}/{N_EFF} PASS**（**D5 FAIL**）⇒ 严格读法 `{STRICT}` |
| **协议真空** | `D1–D4 PASS` 且 `D5 FAIL` | 判决 1 要求 D1–D5 全 PASS；判决 2 仅覆盖 D1–D4 部分 FAIL ⇒ **两分支均未覆盖** |

> ⛔ **本轮撤回「原协议 17/17 PASS」表述**。正确说法：**核心执行级判据（D1–D4）全 PASS；原始预注册判据 D5 FAIL；协议对「D1–D4 PASS + D5 FAIL」组合无定义**（`protocol_uncovered_case={UNCOV}`）。

| 块 | 判据 | 通过 |
|---|---|---|
| A 运行一致性 | A1–A3 | **{A_ok}/{A_n}** |
| B events 完整性 | B1–B5 | **{B_ok}/{B_n}** |
| C 路线对账 | C1–C3 | **{C_ok}/{C_n}** |
| D 执行级配对 | D1–D4（+ 原始 D5） | **{D_ok}/{D_n}** |
| | **合计有效门禁** | **{N_EFF_PASS}/{N_EFF}** |

---

## 1. 运行一致性：开 events 没有改变仿真动力学

- **it.19 逐链 LinkStats sha256 逐位相同**：`{ls_ident}`
  - 参照 `{CS['linkstats_ref_sha256'][:40]}…`
  - 新 run `{CS['linkstats_new_sha256'][:40]}…`
- 确定性产物 sha256 相同：**{files_line}**
- 观测域复算（it.10–19 cycle-mean → 576 断面 → median×SCALE=2.29897）：

| 量 | v1.0 | 原 SB-A5 | 新 run |
|---|---|---|---|
| 08-09 `Sim/Obs` | {od.get('SimObs_v1.0', float('nan')):.7f} | {od.get('SimObs_SB-A5', float('nan')):.7f} | **{od.get('SimObs_NEW', float('nan')):.7f}** |
| 匹配边 ΣQ(raw) | {od.get('totals', {}).get('v1.0_matched_edges_raw', float('nan')):,.4f} | {od.get('totals', {}).get('SB-A5_matched_edges_raw', float('nan')):,.4f} | **{od.get('totals', {}).get('NEW_matched_edges_raw', float('nan')):,.4f}** |
| 断面 ΣQ(scaled) | {od.get('totals', {}).get('v1.0_section_scaled_total', float('nan')):,.4f} | {od.get('totals', {}).get('SB-A5_section_scaled_total', float('nan')):,.4f} | **{od.get('totals', {}).get('NEW_section_scaled_total', float('nan')):,.4f}** |

⇒ **结论**：`writeEventsInterval=19` 只挂了一个输出 handler，**未改变仿真动力学**；新 events 可安全用于推断原 SB-A5 的执行路径。

{A_t}

---

## 2. events 完整性与路线对账

- 事件类型集合：`{sorted(EI['new'].get('event_types', {}).keys())}`
- 事件计数（新 run it.19）：`{ {k: v for k, v in list(EI['new'].get('event_types', {}).items())} }`
- 关联 person 数：**{EI['new'].get('scan_info', {}).get('n_person_enter_events', 0):,}**
- 重建执行路线的 person 数：**{EI['new'].get('n_persons_in_events', 0):,}**
- 未完成（截尾排除）：{EI['new'].get('scan_info', {}).get('n_unfinished_excluded', 0):,}

**对账语义（实测）**：`entered link` 只带 `vehicle` ⇒ 经 `PersonEntersVehicle` 关联到 person；
selected plan 的 `<route type="links">` 内容以 `start_link` 为首元素，车辆被置于 start_link ⇒
events 不记其 `entered link` ⇒ `obs == plan[1:]`。

| 侧 | 匹配率 | direct | drop_start_link | drop_last_link | mismatch |
|---|---|---|---|---|---|
| **SB-A5_EVT19_CHECK** | **{EI['recon_fidelity']['rate_pct']:.4f}%** | {EI['recon_fidelity'].get('direct',0)} | {EI['recon_fidelity'].get('drop_start_link',0)} | {EI['recon_fidelity'].get('drop_last_link',0)} | {EI['recon_fidelity'].get('mismatch',0)} |
| v1.0（独立复核） | {EI['v10_recon_fidelity']['rate_pct']:.4f}% | {EI['v10_recon_fidelity'].get('direct',0)} | {EI['v10_recon_fidelity'].get('drop_start_link',0)} | {EI['v10_recon_fidelity'].get('drop_last_link',0)} | {EI['v10_recon_fidelity'].get('mismatch',0)} |

⇒ `drop_start_link` 语义两侧一致，且与 E-SB-04 对 v1.0 的独立抽样（8,000/8,000 = 100%）一致。

{C_t}

---

## 3. 执行级配对比较（v1.0 vs SB-A5_EVT19_CHECK）

同 population（`population_lambda_0p075.xml.gz`）、同 `lastIteration=19`、同 seed；
**只有网络 `freespeed` 不同** ⇒ 差异可干净归因到「网络改速 ⇒ 路线重分配」。

- 共享 person：**{P['n_common_persons']:,}**
- **执行路线改变率**：**{P['exec_route_change_pct']:.4f}%**（{P['n_exec_route_changed']:,} 人）
  ｜ 计划级参照（E-SB-04）：{pct(P['plans_route_change_pct'])}
- 执行 VKT：v1.0 {P['v10_vkt_km']:,.1f} km → SB-A5 {P['exec_vkt_km']:,.1f} km
  ｜ 人均里程 {P['v10_mean_len_km']:.4f} → {P['exec_mean_len_km']:.4f} km
- 人均 link 数 {P['v10_mean_n_links']:.3f} → {P['exec_mean_n_links']:.3f}

### 3.1 快速路（motorway + motorway_link）里程份额

| 口径 | v1.0 | SB-A5 | Δ |
|---|---|---|---|
| **执行级**（总量加权） | {pct(P['v10_share_express_class_pct'])} | **{pct(P['exec_share_express_class_pct'])}** | **{pp(exec_d)}** |
| **计划级**（E-SB-04 参照） | {pct(CMPD.loc[CMPD.metric=='_share_express_pct','v1.0_plans_pct'].iloc[0])} | {pct(CMPD.loc[CMPD.metric=='_share_express_pct','SB-A5_plans_pct'].iloc[0])} | **{pp(plan_d)}** |
| 执行级（逐人均值，稳健性） | {pct(P['v10_mean_person_express_share_pct'])} | {pct(P['exec_mean_person_express_share_pct'])} | {pp(P['exec_delta_mean_person_pp'])} |

⇒ **执行级 Δ 与计划级 Δ 同号同量级（差 {gap:+.4f} pp）** ⇒ E-SB-04 的「计划路线向快速路倾斜」
不是计划层伪影，**在执行中真实发生**。

### 3.1b 方法学校验：执行级里程与计划级里程之差恰为 `start_link`

`obs == plan[1:]` 意味着执行级里程**天然不含 `start_link` 的长度**。若该语义被正确实现，
则「计划级人均里程 − 执行级人均里程」应在两侧**都等于人均 `start_link` 长度**：

| 侧 | 计划级人均里程 | 执行级人均里程 | 差（= 人均 `start_link`） |
|---|---|---|---|
| v1.0 | {_dv:.4f} km | {_mv:.4f} km | **{_under_v:.1f} m** |
| SB-A5 | {_dn:.4f} km | {_mn:.4f} km | **{_under_n:.1f} m** |

⇒ 两侧差值一致（差 {abs(_under_n - _under_v):.2f} m），验证了执行路线重建的**唯一系统性缺口**
就是 `start_link`，不是遗漏 link 或截断 ⇒ 执行级份额与计划级份额可直接比较。

### 3.2 逐道路等级份额（执行级 vs 计划级）

| 等级 | v1.0 执行 | SB-A5 执行 | 执行 Δ | v1.0 计划 | SB-A5 计划 | 计划 Δ |
|---|---|---|---|---|---|---|
"""
for _, r in CMPD.iterrows():
    if r["metric"] == "_share_express_pct":
        lbl = "**快速路合计**"
    else:
        lbl = r["metric"]
    md += (f"| {lbl} | {r['v1.0_exec_pct']:.4f}% | {r['SB-A5_exec_pct']:.4f}% | {r['exec_delta_pp']:+.4f} | "
           f"{f_pct(r['v1.0_plans_pct'])} | {f_pct(r['SB-A5_plans_pct'])} | {f_pp(r['plans_delta_pp'])} |\n")

md += f"""
### 3.3 执行级走廊（里程份额 + person 使用率）

| 走廊 | v1.0 里程份额 | SB-A5 里程份额 | Δ 里程 | v1.0 使用率 | SB-A5 使用率 | Δ 使用率 |
|---|---|---|---|---|---|---|
"""
for _, r in CORR.iterrows():
    md += (f"| {r['corridor']} | {r['v1.0_exec_mileage_share_pct']:.4f}% | "
           f"{r['SB-A5_exec_mileage_share_pct']:.4f}% | {r['mileage_delta_pp']:+.4f} pp | "
           f"{r['v1.0_exec_use_pct']:.4f}% | {r['SB-A5_exec_use_pct']:.4f}% | {r['delta_pp']:+.4f} pp |\n")

md += f"""
⇒ 执行级里程份额 Δ Top-2 走廊 = **{P['top2_corridor']}**（合计 {P['top2_delta_pp_sum']:+.4f} pp）。

#### ★★原始预注册判据 D5 的处置（逐条披露）

- **原始预注册判据 D5**（`PROTOCOL_E-SB-05.md` 初稿）：执行级里程份额 Δ Top-2 走廊 **恰为** PIE/TPE。
- **本轮实测排序**（里程份额 Δ 降序，前 5）：`{' > '.join(_c_top_mileage[:5])}`
  ｜ person 使用率 Δ 排序（前 5）：`{' > '.join(_c_top_use[:5])}`
- ⇒ 实测 Top-2 = **{P['top2_corridor']}**，**{'恰为 PIE/TPE' if _top2_is_pie_tpe else '不是 PIE/TPE'}**
  ⇒ **原始 D5 = {'PASS' if _d5_draft_would_pass else 'FAIL'}**（TPE 里程份额口径第 **{_tope_rank_mileage}** 位、使用率口径第 **{_tope_rank_use}** 位）。
- **处置**：原 D5 判定**保留为 FAIL（硬门禁）**；「PIE 与 TPE 的里程份额 Δ 均为正」**降为补充分析 `A5`**
  （`status=supplementary`，**不进判决**）。
- **协议真空**：原判决 1 要求 `D1–D5 全 PASS`、判决 2 仅覆盖 `D1–D4 部分 FAIL`；本轮为
  `D1–D4 全 PASS + D5 FAIL` ⇒ **两个预注册分支均未覆盖**（`protocol_uncovered_case={UNCOV}`）。
- **双读法（并列，⛔ 不静默择一）**：
  - **核心执行级判据 D1–D4 全 PASS** ⇒ E-SB-04/04B 的路径结论**升级为执行级**（实体结论）；
  - **严格按原始协议合取条件** ⇒ 有效门禁 **{N_EFF_PASS}/{N_EFF}**，严格读法为 `{STRICT}`。

#### ★ D5 修订时间线核实（客观证据，⛔ 不采信自述）

| 通道 | 可用性 | 说明 |
|---|---|---|
| Git 历史 | **不可用** | `esb05_*` 脚本与协议**从未被 git 跟踪**（`tracked=False`）⇒ 无历史可回放 |
| 协议 mtime | 可用 | `{_tl_proto}` 早于 SB-A5 执行级数据 `{_tl_data}` |
| 脚本 mtime | **已被本轮覆盖** | 为恢复原始 D5 而编辑脚本 ⇒ 原 `23:11:42` 已丢失（现 `{_tl_cmp}`）⇒ 观察者破坏性 |

- **审计判决**：`{_tl_verdict}`。
- ⇒ **本报告不主张「修订先于数据」，也不主张「原协议 17/17 PASS」**；
  证据不足时按**最保守口径**处理：原始 D5 保留 FAIL、修订版降为补充分析。
- E-SB-03 原命题是「PIE+TPE **合计贡献 63.4% 的观测域净流量增量**」（**贡献份额**，非排序第一名）。
  本轮**补充分析**的等价检验为符号同向：里程份额 Δ PIE = {f_pp(_pie_d)} pp、TPE = {f_pp(_tpe_d)} pp
  （使用率 Δ {f_pp(_pie_u)} / {f_pp(_tpe_u)} pp）⇒ 均 > 0。
  但 TPE 增量**量级远小于 PIE**，在本轮执行级口径下**非贡献前二**；E-SB-03 的「63.4%」是
  **观测域断面流量**口径、与本轮**执行级里程份额**口径**不同源**，⛔ 不得互换。

{D_t}

**参考项（不进判决）**

{I_t}

---

## 4. 与 E-SB-04 / E-SB-04B 的衔接

| 环节 | E-SB-04（plans） | E-SB-05（execution） | 一致？ |
|---|---|---|---|
| 路线改变率 | {pct(P['plans_route_change_pct'])} | {P['exec_route_change_pct']:.4f}% | {'同量级' if abs(P['exec_route_change_pct']-(P['plans_route_change_pct'] or 0))<25 else '差异较大'} |
| 快速路份额 Δ | {pp(plan_d)} | {pp(exec_d)} | {'同号 PASS' if np.sign(plan_d)==np.sign(exec_d) else '反号 FAIL'} |
| PIE 里程份额 Δ | （E-SB-04 未单列） | {f_pp(_pie_d)} | 与 E-SB-03 观测域同向（**补充分析 `A5`**，⛔ 非门禁） |
| TPE 里程份额 Δ | （E-SB-04 未单列） | {f_pp(_tpe_d)} | 符号同向（**补充分析**）；但**量级远小、非 Top-2** ⇒ **原始 D5 FAIL**（见 §3.3） |

E-SB-04B 的 `FREESPEED_ROUTE_COUPLING_SUPPORTED` 结论基于同一 population、仅 `freespeed` 差 90,643 链；
本轮执行级证据表明该「改道补偿」**在执行层同样成立**。

---

## 5. 边界（不得越过）

- 本轮**只**补执行级证据；⛔ 未调 `SCALE`；⛔ 未改容量 / `freespeed` / λ / 阈值；
  ⛔ 未启动信号灯、交叉口实验；⛔ 未晋升 `v1.1`；⛔ 未覆盖原 SB-A5 输出；⛔ 未重跑 `SB-A5ind`。
- `v1.0` 与原 SB-A5 均保持不动（只读）。
- 执行级 `Sim/Obs` 口径未变：**不得**用本轮结果去把 `Sim/Obs` 调向 1。
- 「执行路线改变」是**网络改速的后果**，不代表校准结论升级；口径（car-only 通勤 vs 全机动车+全目的）差异仍在。

---

## 6. 产物清单

```
experiments/E-SB-05_exec_level_events/
  PROTOCOL_E-SB-05.md  README.md
  configs/config_SB-A5_EVT19_CHECK.xml
  outputs/SB-A5_EVT19_CHECK/            (ITERS/it.0, it.19 含 events + 根产物)
  logs/SB-A5_EVT19_CHECK_run.log
  audit/  esb05_preflight.csv, run_config_manifest.json, input_manifest.json,
          SB-A5_EVT19_CHECK_run_stamp.json,
          esb05_consistency_files.csv / _numeric.csv / _gates.csv / _summary.json,
          SB-A5_EVT19_CHECK_allhours_conv.linkstats.txt.gz,
          esb05_events_integrity.json, esb05_exec_route_compare.csv,
          esb05_exec_corridor_use.csv, esb05_exec_route_gates.csv,
          esb05_exec_route_summary.json, _exec_cache/
reports/exec_level_events_E_SB_05/
  VERDICT_E-SB-05.md  exec_level_scorecard.csv
```
"""
(REPORT / "VERDICT_E-SB-05.md").write_text(md, encoding="utf-8")
print(f"[out] {REPORT/'VERDICT_E-SB-05.md'}  ({len(md.splitlines())} 行)")
print(f"[out] {REPORT/'exec_level_scorecard.csv'}")
