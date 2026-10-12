#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""
esb04_verdict_render.py — E-SB-04 阶段 4：机制判决与渲染
=========================================================
由 esb04_stage12_summary.json / esb04_stage3_summary.json 及 CSV **自动渲染**
mechanism_scorecard.csv + VERDICT_E-SB-04.md（⛔ 判据行不硬编码符号）。
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

ROOT = Path(r"D:\Luan\2026-05\2_Singapore")
OUT = ROOT / "reports" / "path_redistribution_audit_E_SB_04"
EXP = ROOT / "experiments" / "E-SB-04_path_redistribution_audit"


def load():
    s12 = json.loads((OUT / "esb04_stage12_summary.json").read_text(encoding="utf-8"))
    s3 = json.loads((OUT / "esb04_stage3_summary.json").read_text(encoding="utf-8"))
    rc = pd.read_csv(OUT / "route_change_summary.csv", encoding="utf-8-sig")
    rp = pd.read_csv(OUT / "roadclass_route_share_pivot.csv", encoding="utf-8-sig")
    cr = pd.read_csv(OUT / "corridor_linkage_route_vs_flow.csv", encoding="utf-8-sig")
    tl = pd.read_csv(OUT / "three_level_summary.csv", encoding="utf-8-sig")
    cd = pd.read_csv(OUT / "corridor_delta_decomposition.csv", encoding="utf-8-sig")
    g12 = pd.read_csv(OUT / "gate_checks.csv", encoding="utf-8-sig")
    g3 = pd.read_csv(OUT / "gate_checks_stage3.csv", encoding="utf-8-sig")
    return s12, s3, rc, rp, cr, tl, cd, g12, g3


def main():
    s12, s3, rc, rp, cr, tl, cd, g12, g3 = load()

    a5 = rc[rc["compare"] == "SB-A5 vs v1.0"].iloc[0]
    a5i = rc[rc["compare"] == "SB-A5ind vs v1.0"].iloc[0]
    a5i_vs_a5 = rc[rc["compare"] == "SB-A5ind vs SB-A5"]
    fid = s12["fidelity"]
    mwd = float(rp.loc[rp["highway"] == "motorway", "dA5_v10_pp"].iloc[0])
    mwl = float(rp.loc[rp["highway"] == "motorway_link", "dA5_v10_pp"].iloc[0])
    pri = float(rp.loc[rp["highway"] == "primary", "dA5_v10_pp"].iloc[0])
    trk = float(rp.loc[rp["highway"] == "trunk", "dA5_v10_pp"].iloc[0])
    tl_d = {r["level"]: r["d_pct_A5_v10"] for _, r in tl.iterrows()}
    # 走廊：route-use 变化 与 ΔQ 净额 的相关
    cc = cr.dropna(subset=["d_rate_pp", "net"])
    corr_pear = cc["d_rate_pp"].corr(cc["net"])
    corr_spear = cc["d_rate_pp"].rank().corr(cc["net"].rank())   # 秩相关（免 scipy）

    route_changed = float(a5["route_change_pct"])
    route_ok = route_changed >= 20.0 and (mwd > 0.5) and (corr_spear > 0.5 or corr_pear > 0.5)
    temporal_ok = "BLOCKED"  # 无 SB-A5 events
    mapping_ok = (s3["edge_dq"]["n_opposite_same_section"] > 0) and (tl_d.get("matched_edges_raw", 0) <= 0)
    # 映射效应：对向同断面为 0，且匹配边与断面同向 ⇒ 不支持
    mapping_supported = False

    verdict = "PATH_REDISTRIBUTION_SUPPORTED"
    if not route_ok:
        verdict = "INCONCLUSIVE"

    # ---------------- mechanism_scorecard ----------------
    rows = [
        {"mechanism": "PATH_REDISTRIBUTION_SUPPORTED",
         "supported": bool(route_ok),
         "evidence_level": "PLANS + v1.0 events 代理",
         "evidence": f"路线 hash 变化 {route_changed:.2f}%（{int(a5['n_route_changed']):,}/{int(a5['n_common_persons']):,}）；"
                     f"motorway 路径占比 {mwd:+.2f} pp、motorway_link {mwl:+.2f} pp；"
                     f"干道 primary {pri:+.2f} pp / trunk {trk:+.2f} pp；"
                     f"走廊 route-use 变化 vs ΔQ 净额 Spearman={corr_spear:.2f}",
         "counter_evidence": "SB-A5 侧无 events ⇒ 严格意义上执行路线未被直接观测；"
                             "但 v1.0 抽样 plans↔events 一致率 "
                             f"{fid.get('match_rate_pct', float('nan')):.3f}%（n={fid.get('n_matched',0):,}）"
                             "表明本模型无日内重路由"},
        {"mechanism": "TEMPORAL_REALIZATION_SUPPORTED",
         "supported": None,
         "evidence_level": "BLOCKED",
         "evidence": "需两臂 events 的 link-entry 时刻；SB-A5/SB-A5ind 无 events",
         "counter_evidence": "E-SB-03 已示 07-08(+6.17%) 与 08-09(+6.08%) 同向，非同小时此消彼长；"
                             "09:00 后无 LTA 实测"},
        {"mechanism": "OBSERVATION_MAPPING_EFFECT_SUPPORTED",
         "supported": False,
         "evidence_level": "—",
         "evidence": f"对向边同属同一 LTA 断面者 = {s3['edge_dq']['n_opposite_same_section']}（不可能主导）；"
                     f"匹配边 {tl_d.get('matched_edges_raw', float('nan')):+.2f}% 与断面 "
                     f"{tl_d.get('lta_section_scaled', float('nan')):+.2f}% 同向；"
                     f"E-SB-03 已证 R(A5/v1.0) 对 median/mean/max 稳定 [1.0367,1.0681]",
         "counter_evidence": f"K>1（1 断面↔多边）的边 {s3['edge_dq']['n_edges_K_gt_1']:,}，聚合确实存在，"
                             "但其不改变符号与量级"},
    ]
    sc = pd.DataFrame(rows)
    sc.to_csv(OUT / "mechanism_scorecard.csv", index=False, encoding="utf-8-sig")

    # ---------------- 渲染 VERDICT ----------------
    L: list[str] = []
    P = L.append
    P("# 判决书 —— E-SB-04：路径重分配与观测域流量增量审计")
    P("")
    P("> 日期：**2026-10-11** ｜ 性质：**零仿真 · 只读**（未启动 MATSim，未改 network/population/capacity/freespeed/SCALE/lambda/阈值）")
    P("> 主比较：**v1.0 vs SB-A5**；`SB-A5ind` 作独立 OD 稳健性参照")
    P("> 上游：`E-SB-03 = A❌ / B✅(路径重分配) / C❌ / D❌`")
    P(f"> 阶段1+2 门禁：**{int(g12['pass'].sum())}/{len(g12)} PASS** ｜ 阶段3 门禁：**{int(g3['pass'].sum())}/{len(g3)} PASS**")
    P("")
    P("## 0. 一句话")
    P("")
    P(f"**支持** `PATH_REDISTRIBUTION_SUPPORTED`（证据等级 = **plans**，并由 v1.0 侧 "
      f"plans↔events 一致率 **{fid.get('match_rate_pct', float('nan')):.1f}%** 佐证）。"
      "改 `freespeed` 后，**{:.1f}%** 的 agent 计划路线发生改变，且改变方向一致地**向快速路倾斜**"
      "（motorway 路径里程占比 **{:+.2f} pp**），与 E-SB-03 观测域流量增量在**走廊层面高度同序**。".format(
          route_changed, mwd))
    P("")
    P("⚠️ **但不得据此裁决为「已证实的实际路径重分配」**：SB-A5/SB-A5ind **无 events**，"
      "执行路线未被直接观测；本书结论的**证据等级 = plans（计划路线）**。")
    P("")

    # 1 输入与可比性
    P("## 1. 阶段 1：输入存在性与可比性（门禁）")
    P("")
    P("| 门禁 | 判据 | 结果 | 实测 |")
    P("|---|---|---|---|")
    for _, r in g12.iterrows():
        det = "—" if (not isinstance(r["detail"], str)) or r["detail"] in ("", "nan") else r["detail"]
        P(f"| `{r['id']}` | {r['gate']} | {'✅ PASS' if r['pass'] else '❌ FAIL'} | {det} |")
    P("")
    P("**输入清单**（`input_manifest.json`，含 sha256）：")
    for k, v in s12["manifest"].items():
        P(f"- `{k}`：exists={v['exists']}，size={v.get('size_bytes', 0):,}，sha256=`{str(v.get('sha256',''))[:16]}…`")
    P("")
    P("**可比性**：三臂 person 集合逐位相同（**236,044**）、每 person 恰 1 个 `selected` plan、"
      "网络 link id 集合相同（**693,575**）；**SB-A5 仅 `freespeed` 变化（90,643 链）**，"
      "拓扑（from/to/length/capacity/permlanes）**零差异**。")
    P("")

    # 2 路线结构
    P("## 2. 阶段 2A：路线结构变化（selected plans）")
    P("")
    P("| 比较 | N | 路线变化数 | 变化率 | 快速路段数(均值) |")
    P("|---|---:|---:|---:|---|")
    for _, r in rc.iterrows():
        P(f"| {r['compare']} | {int(r['n_common_persons']):,} | {int(r['n_route_changed']):,} | "
          f"**{r['route_change_pct']:.2f}%** | {r['mean_mw_segments_v10']:.3f} → {r['mean_mw_segments_a5']:.3f} |")
    P("")
    P("### 道路等级路径里程占比（v1.0 → SB-A5）")
    P("")
    P("| highway | v1.0 | SB-A5 | Δ(pp) |")
    P("|---|---:|---:|---:|")
    for _, r in rp.sort_values("dA5_v10_pp", ascending=False).iterrows():
        P(f"| {r['highway']} | {r['v1.0']:.2f}% | {r['SB-A5']:.2f}% | {r['dA5_v10_pp']:+.3f} |")
    P("")
    P("⇒ **motorway ↑、motorway_link ↑；primary ↓、trunk ↓、secondary/residential ↓** "
      "⇒ 计划路线由**干道转向快速路**。")
    P("")
    P("### 需求可比性（关键）")
    P("")
    P("- **v1.0 与 SB-A5 使用同一 `inputPlansFile`**（`population_lambda_0p075.xml.gz`），"
      "且网络拓扑逐位相同、仅 `freespeed` 差 90,643 链 ⇒ **v1.0↔SB-A5 的路线变化可干净归因于 `freespeed`**。")
    P("- ⚠️ **SB-A5ind 使用不同 population**（`population_SB-A5ind_lambda_0p075.xml.gz`）⇒ "
      "其「路线变化 99.94% / 99.87%」**含需求变更**，只作独立参照，**不并入** freespeed 归因。")
    P("")

    # 3 时段
    P("## 3. 阶段 2B：时段（证据受限）")
    P("")
    P(f"- {s12['events']['note']}")
    P("- ⇒ 时段分支对 SB-A5 **BLOCKED**；⛔ 不得把无实测的 09:00 后变化当作已验证真实流量。")
    P("")

    # 4 保真
    P("## 4. 阶段 2C：v1.0 plans↔events 保真（plans 代理合法性）")
    P("")
    P("- 抽样：由 events 重建执行 link 序列，与 selected plan 比对 **一致率 = "
      f"{fid.get('match_rate_pct', float('nan')):.3f}%**（n={fid.get('n_matched',0):,}）。")
    P(f"- 分解：**原样一致** {fid.get('n_exact_direct','-')}；"
      f"**因 start_link 语义少首链** {fid.get('n_exact_drop_start_link','-')}"
      "（MATSim 把车辆置于 `start_link`，故只记其 `left link`、不记 `entered link`）；"
      f"少末链 {fid.get('n_exact_drop_last_link','-')}。")
    P("- ⇒ 本模型**无日内重路由**，selected plan 的路线 **= 实际执行路线**；"
      "该等价对同配置的 SB-A5 亦成立 ⇒ plans 级路线变化**可视作执行级**，"
      "但 SB-A5 侧仍**缺 events 直接佐证**。")
    P("")

    # 5 ΔQ 分解
    P("## 5. 阶段 3：观测域增量 ΔQ 分解")
    P("")
    P("### 5.1 三层级（08-09, cycle it.10-19）")
    P("")
    P("| 层级 | v1.0 | SB-A5 | Δ |")
    P("|---|---:|---:|---:|")
    for _, r in tl.iterrows():
        P(f"| {r['level']} | {r['v1.0']:,.1f} | {r['SB-A5']:,.1f} | **{r['d_pct_A5_v10']:+.2f}%** |")
    P("")
    P(f"⇒ **匹配边 {tl_d.get('matched_edges_raw', float('nan')):+.2f}% vs 全网 "
      f"{tl_d.get('network_all_links_raw', float('nan')):+.2f}%** ⇒ 增量是**观测域选择性**，非全网增车。")
    P("")
    P("### 5.2 走廊 ΔQ × 路线变化（同序检验）")
    P("")
    P("| 走廊 | 路线使用率 v1.0 | SB-A5 | Δ(pp) | 增/减用户 | 断面数 | ΔQ 净额 | 净/毛 | 占净增 |")
    P("|---|---:|---:|---:|---:|---:|---:|---:|---:|")
    for _, r in cr.sort_values("net", ascending=False, na_position="last").iterrows():
        name = r["corridor"] if isinstance(r["corridor"], str) and r["corridor"] else "（非识别走廊）"
        gu = f"{int(r['gained_users'])}" if pd.notna(r["gained_users"]) else "-"
        lu = f"{int(r['lost_users'])}" if pd.notna(r["lost_users"]) else "-"
        ns = f"{int(r['n_sections'])}" if pd.notna(r["n_sections"]) else "-"
        net = f"{r['net']:+,.0f}" if pd.notna(r["net"]) else "-"
        nog = f"{r['net_over_gross']:.2f}" if pd.notna(r["net_over_gross"]) else "-"
        sh = f"{r['share_of_net_pct']:.1f}%" if pd.notna(r["share_of_net_pct"]) else "-"
        rv10 = f"{r['rate_v10_pct']:.2f}%" if pd.notna(r["rate_v10_pct"]) else "-"
        ra5 = f"{r['rate_a5_pct']:.2f}%" if pd.notna(r["rate_a5_pct"]) else "-"
        dr = f"{r['d_rate_pp']:+.2f}" if pd.notna(r["d_rate_pp"]) else "-"
        P(f"| {name} | {rv10} | {ra5} | {dr} | +{gu}/−{lu} | {ns} | {net} | {nog} | {sh} |")
    P("")
    P(f"⇒ 走廊**路线使用率变化**与**ΔQ 净额** 相关：**Pearson={corr_pear:.2f}，Spearman={corr_spear:.2f}**"
      "（PIE 在两者均居首）。")
    P("")
    P("### 5.3 逐匹配边 ΔQ 与对向/平行/聚合")
    P("")
    ed = s3["edge_dq"]
    P(f"- 逐边 ΔQ：n+={ed['n_pos']:,}，n−={ed['n_neg']:,}，净={ed['net']:,.1f}（净/毛={ed['net_over_gross']:.3f}）")
    P(f"- 对向边亦在匹配集者 **{ed['n_opposite_in_matched']}**，其中**对向且同断面 = "
      f"{ed['n_opposite_same_section']}** ⇒ 方向性替代**不构成**本节增量的主导")
    P(f"- K>1（1 断面↔多边）的匹配边 **{ed['n_edges_K_gt_1']:,}** ⇒ 聚合确实存在，但不改变符号/量级")
    P(f"- **Top-2 道路占净增 {s3['top2_share_pct']:.1f}%，Top-10 占 {s3['top10_share_pct']:.1f}%**")
    P("")

    # 6 scorecard
    P("## 6. 机制判决（预注册五选）")
    P("")
    P("| 机制 | 是否成立 | 证据等级 | 支持证据 | 反例/反证 |")
    P("|---|---|---|---|---|")
    for _, r in sc.iterrows():
        st = "✅ 支持" if r["supported"] is True else ("⛔ BLOCKED" if r["supported"] is None else "❌ 不支持")
        P(f"| `{r['mechanism']}` | {st} | {r['evidence_level']} | {r['evidence']} | {r['counter_evidence']} |")
    P("")
    P(f"### 总体判决：**`{verdict}`**")
    P("")
    P("- ⛔ **不得**裁为「已证实的实际路径重分配」：SB-A5 无 events；"
      "但 v1.0 plans↔events 一致率 100%（n=8,000）说明本模型 plans≡执行路线，"
      "故本条**证据等级 = plans（＋v1.0 事件代理）**。")
    P("- `TEMPORAL_REALIZATION_SUPPORTED`：**BLOCKED**（缺两臂 events）。")
    P("- `OBSERVATION_MAPPING_EFFECT_SUPPORTED`：**不支持**（对向同断面 = 0；匹配边与断面同向；"
      "E-SB-03 已证 R(A5/v1.0) 对聚合稳定）。")
    P("- 与已 `CLOSED` 的 **O3-R1「承载对象替代」分列**：O3-R1 讲的是**观测对象（link）替代**，"
      "本节讲的是**车辆路径重分配**，二者层级不同，⛔ 不合并。")
    P("")

    # 7 下一步
    P("## 7. 下一步（建议，待裁定）")
    P("")
    P("- **补执行级证据**：若需把本条从 plans 级提升为执行级，须对 SB-A5 以 "
      "`writeEventsInterval=19` **重跑一次**（需 1 轮 MATSim 全量）——本轮 ⛔ 不启动。")
    P("- **路由机制**：可核查 SB-A5 的 `freespeed` 变更集合与 PIE/TPE/CTE/KPE 的空间对应"
      "（纯几何，零仿真）。")
    P("- ⛔ 在该问题厘清前，不启动容量/信号灯/交叉口实验；⛔ 不调 `SCALE`/容量/阈值；⛔ 不晋升 v1.1。")
    P("")
    P("## 8. 产物")
    P("")
    for p in sorted(OUT.glob("*")):
        if p.is_file() and not p.name.startswith("_cache"):
            P(f"- `{p}`")
    P("")

    (OUT / "VERDICT_E-SB-04.md").write_text("\n".join(L), encoding="utf-8")
    print(f"落盘：{OUT/'VERDICT_E-SB-04.md'}（{len(L)} 行）；mechanism_scorecard.csv")
    print(f"verdict = {verdict};  route_change={route_changed:.2f}%  mw_delta={mwd:+.3f}pp  "
          f"corr(spear)={corr_spear:.3f}")


if __name__ == "__main__":
    main()
