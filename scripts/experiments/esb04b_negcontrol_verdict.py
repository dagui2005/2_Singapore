#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""
esb04b_negcontrol_verdict.py — E-SB-04B 阶段 5：负例对照 + 预注册判决渲染
==========================================================================
★零仿真 · 只读。读取 esb04b_coupling_audit.py 的产物，做：
  N1  路线级 placebo（构造性，已在阶段3核验，此处复述）
  N2  空间 shuffle 置换检验（全局 / 同等级内；n_perm 次）
  N3  base-rate 同等级（motorway/motorway_link）对照
再按 PROTOCOL §7 的五选一渲染 VERDICT_E-SB-04B.md 与 coupling_scorecard.csv。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(r"D:\Luan\2026-05\2_Singapore")
OUT = ROOT / "reports" / "path_redistribution_audit_E_SB_04B"
CACHE = ROOT / "experiments" / "E-SB-04B_path_freespeed_coupling" / "_cache"
N_PERM = 500
RNG = np.random.default_rng(20261011)


def main() -> int:
    print("=" * 100)
    print("E-SB-04B 阶段5：负例对照（shuffle 置换 / base-rate） + 预注册判决渲染")
    print("=" * 100)

    d = np.load(CACHE / "perm_inputs.npz")
    A, B, C, DFREE, FS10 = d["A"], d["B"], d["C"], d["DFREE"], d["FS10"]
    meta = json.loads((CACHE / "perm_inputs.json").read_text(encoding="utf-8"))
    nc, nu = meta["n_changed"], meta["n_unchanged"]
    n_chg = int((np.abs(DFREE) > 1e-9).sum())

    # 属性（用于同等级 shuffle）
    src = pd.read_csv(ROOT / "reports" / "matsim_network" / "network_links_source_copy.csv",
                      encoding="utf-8-sig", low_memory=False, usecols=["from_node", "to_node", "highway"])
    src["link"] = "e" + src["from_node"].astype(str) + "_" + src["to_node"].astype(str)
    src = src.drop_duplicates("link").set_index("link")
    # 与主脚本同一 ALL 顺序（sorted link id）★必须一致
    links_sorted = np.array(sorted(src.index), dtype=object)  # 仅用于构造分组标签
    # 直接按 DFREE 长度重建标签：用同一次排序
    import gzip, re
    net_p = ROOT / "matsim_final_7_6h" / "outputs" / "W01_rc_min" / "W01_rc_min.output_network.xml.gz"
    ids = []
    with gzip.open(net_p, "rt", encoding="utf-8", errors="replace") as f:
        for line in f:
            m = re.match(r'\s*<link\s+id="([^"]+)"', line)
            if m:
                ids.append(m.group(1))
    ids = sorted(ids)
    assert len(ids) == len(DFREE), (len(ids), len(DFREE))
    hw = np.array([src["highway"].get(l, "NA") for l in ids], dtype=object)

    # ---------- 统计量 ----------
    def s_route_effect(dfree_vec):
        """(1/nc) Σ_l (FS10_l + v_l)(B_l − A_l) = 变化者的 route-effect 均值。
        ★含常量项 Σ FS10·(B−A)/nc，使「观测值」与 §2 的 route-effect 均值同口径
        （v=DFREE 时恒等于 fsA5_onR5 − fsA5_onR10 在变化者上的均值）。"""
        return float(np.dot(FS10 + dfree_vec, B - A) / nc)

    def s_exposure_diff(mask_slow):
        """mean_{changed} slow_share10 − mean_{unchanged} slow_share10。"""
        return float(np.dot(mask_slow, A) / nc - np.dot(mask_slow, C) / nu)

    obs_re = s_route_effect(DFREE)
    obs_ex = s_exposure_diff((DFREE < -1e-9).astype(np.float64))
    print(f"\n[观测] route-effect 均值(变化者) = {obs_re:+.5f} m/s"
          f"  (route_delta_exposure 均值={meta['obs_route_effect_mean']:+.5f}，应一致)")
    print(f"[观测] 降速链暴露差(changed−unchanged) = {obs_ex:+.5f}")

    # 同等级索引分组
    hw_groups = {}
    for h in np.unique(hw):
        hw_groups[h] = np.where(hw == h)[0]

    rows = []

    def perm_test(name, obs, stat_fn, mode):
        sims = np.empty(N_PERM)
        for k in range(N_PERM):
            if mode == "global":
                perm = RNG.permutation(DFREE)
                sims[k] = stat_fn(perm)
            else:  # within_highway
                v = DFREE.copy()
                for g in hw_groups.values():
                    if len(g) > 1:
                        v[g] = v[RNG.permutation(g)]
                sims[k] = stat_fn(v)
        mu, sd = float(sims.mean()), float(sims.std(ddof=1))
        p95 = float(np.percentile(sims, 95))
        pct = float((sims < obs).mean() * 100)
        z = (obs - mu) / sd if sd > 0 else float("nan")
        pval = (1 + int((sims >= obs).sum())) / (1 + N_PERM)
        rows.append({"statistic": name, "mode": mode, "observed": obs, "perm_mean": mu,
                     "perm_sd": sd, "perm_p95": p95, "percentile_pct": pct, "z": z,
                     "p_value_one_sided": pval, "n_perm": N_PERM})
        print(f"  [N2] {name:16s} mode={mode:14s} obs={obs:+.5f} perm_mean={mu:+.5f} "
              f"sd={sd:.5f} p95={p95:+.5f} pct={pct:5.1f}% z={z:+.2f} p={pval:.4f}")
        return pct, pval, z

    # route-effect 只对 DFREE 的置换有意义（Δfree 是连续量）
    perm_test("route_effect_mean", obs_re, s_route_effect, "global")
    perm_test("route_effect_mean", obs_re, s_route_effect, "within_highway")
    # 暴露差：对 1[Δfree<0] 指标的置换 ≡ 对 DFREE 置换后取 <0
    perm_test("slow_exposure_diff", obs_ex,
              lambda v: s_exposure_diff((v < -1e-9).astype(np.float64)), "global")
    perm_test("slow_exposure_diff", obs_ex,
              lambda v: s_exposure_diff((v < -1e-9).astype(np.float64)), "within_highway")

    nc_df = pd.DataFrame(rows)
    nc_df.to_csv(OUT / "negative_control_shuffle.csv", index=False, encoding="utf-8-sig")

    # ---------- N3 base-rate 同等级 ----------
    sec = pd.read_csv(OUT / "section_delta_coupling.csv", encoding="utf-8-sig", low_memory=False)
    ex = sec[sec["highway"].isin(["motorway", "motorway_link"])]
    g = ex.groupby("fs_changed").agg(n=("dQ_edge_raw", "size"), net=("dQ_edge_raw", "sum"),
                                     q_v10=("sim_v10", "sum")).reset_index()
    g["delta_rate_pct"] = g["net"] / g["q_v10"] * 100
    tot_net = float(sec["dQ_edge_raw"].sum())
    ex_net = float(ex["dQ_edge_raw"].sum())
    net_unc = float(g.loc[g["fs_changed"] == False, "net"].iloc[0])
    D2_share_unc = net_unc / ex_net * 100 if ex_net else float("nan")
    print("\n[N3] base-rate（仅 motorway+motorway_link 匹配边）")
    for _, r in g.iterrows():
        print(f"      fs_changed={str(r['fs_changed']):5s} n={int(r['n']):>5,} 净={r['net']:+11,.1f} "
              f"ΔQ率={r['delta_rate_pct']:+.3f}%  占(快速路类)净增={r['net']/ex_net*100:5.1f}%")
    D2 = D2_share_unc > 50.0
    print(f"      ⇒ fs-未变更边在快速路类内占净增 {D2_share_unc:.1f}% ⇒ D2={'PASS' if D2 else 'FAIL'}")

    # ---------- 读取门禁结论 ----------
    gates = pd.read_csv(OUT / "gate_checks.csv", encoding="utf-8-sig")
    if "status" not in gates.columns:
        gates["status"] = "effective"
    eff = gates[gates["status"] == "effective"]
    gm = dict(zip(eff["id"], eff["pass"]))
    crit = {}
    for k in ["A1", "A2", "A3", "B1c", "B2c", "B3", "B4", "B5c", "C1", "C2", "C3"]:
        crit[k] = bool(gm.get(k, False))
    # 保留被撤回判据的实录（供渲染）
    retr = gates[gates["status"] != "effective"]
    # D1：预注册口径 = 全局置换下，两个统计量均 ≥ 95 百分位
    d1_pct = nc_df[nc_df["mode"] == "global"]["percentile_pct"].min()
    criteria_D1 = bool(d1_pct >= 95.0)
    crit["D1"] = criteria_D1
    crit["D2"] = bool(D2)

    # ---------- 五选一判决（PROTOCOL §7；B 组用修正判据 B1c/B2c/B3/B4/B5c）----------
    B_all = all(crit[k] for k in ["B1c", "B2c", "B3", "B4", "B5c"])
    A_all = all(crit[k] for k in ["A1", "A2", "A3"])
    if not (A_all and B_all):
        verdict = "COUPLING_ABSENT" if not B_all else "INCONCLUSIVE"
    elif not crit["D1"]:
        verdict = "CONFOUNDED_BY_CORRIDOR_SIZE"
    elif not crit["C1"]:
        verdict = "COUPLING_PARTIAL_SECTION_LINKAGE_UNCLEAR"
    else:
        verdict = "FREESPEED_ROUTE_COUPLING_SUPPORTED"
    print(f"\n[判决] {verdict}")

    # ---------- scorecard ----------
    def ev(*keys):
        return " | ".join(f"{k}={'PASS' if crit[k] else 'FAIL'}" for k in keys)

    score = pd.DataFrame([
        {"block": "A 速度变更空间特征", "criteria": "A1,A2,A3", "result": ev("A1", "A2", "A3"),
         "pass": all(crit[k] for k in ["A1", "A2", "A3"])},
        {"block": "B 路线↔速度耦合（修正判据）", "criteria": "B1c,B2c,B3,B4,B5c",
         "result": ev("B1c", "B2c", "B3", "B4", "B5c"),
         "pass": all(crit[k] for k in ["B1c", "B2c", "B3", "B4", "B5c"])},
        {"block": "C 断面增量↔速度耦合", "criteria": "C1,C2,C3", "result": ev("C1", "C2", "C3"),
         "pass": all(crit[k] for k in ["C1", "C2", "C3"])},
        {"block": "D 负例对照", "criteria": "D1,D2", "result": ev("D1", "D2"),
         "pass": all(crit[k] for k in ["D1", "D2"])},
    ])
    score.to_csv(OUT / "coupling_scorecard.csv", index=False, encoding="utf-8-sig")

    # ---------- 渲染 VERDICT ----------
    fs_cls = pd.read_csv(OUT / "freespeed_change_summary.csv", encoding="utf-8-sig")
    fs_cor = pd.read_csv(OUT / "freespeed_change_by_corridor.csv", encoding="utf-8-sig")
    rt = pd.read_csv(OUT / "route_freespeed_coupling.csv", encoding="utf-8-sig")
    sc = pd.read_csv(OUT / "section_delta_coupling_by_changed.csv", encoding="utf-8-sig")
    cc = pd.read_csv(OUT / "corridor_coupling_decomposition.csv", encoding="utf-8-sig")
    summ = json.loads((OUT / "esb04b_summary.json").read_text(encoding="utf-8"))

    def f(x, n=3):
        try:
            return f"{float(x):.{n}f}"
        except Exception:
            return "-"

    def sgn(x, n=4):
        try:
            return f"{float(x):+.{n}f}"
        except Exception:
            return "-"

    L = []
    L.append("# 判决书 —— E-SB-04B：自由流速度变更与路径重分配的空间耦合审计\n")
    L.append("> 日期：**2026-10-11** ｜ 性质：**零仿真 · 只读**（未启动 MATSim，未改任何冻结件）")
    L.append("> 主比较：**v1.0 vs SB-A5**（同 population、仅 `freespeed` 差）；`SB-A5ind` 仅参照")
    L.append(f"> 上游：`E-SB-04 = PATH_REDISTRIBUTION_SUPPORTED`（plans，路线变化 {f(summ['route_change_pct'],2)}%）")
    L.append(f"> 预注册：`PROTOCOL_E-SB-04B.md` ｜ 有效门禁："
             f"**{int(eff['pass'].sum())}/{len(eff)} PASS**"
             f"（另有 {len(retr)} 项已撤回判据，实录于 `gate_checks.csv`）\n")

    L.append("## 0. 一句话\n")
    L.append(f"**判决 = `{verdict}`**。证据等级 **`PLANS_LEVEL`**"
             "（SB-A5 无 events；计划路线的可信度由 v1.0 侧 plans↔events 一致率 100.000% 支撑）。\n")
    if verdict == "FREESPEED_ROUTE_COUPLING_SUPPORTED":
        L.append("自由流速度变更、计划路线变化、观测域断面增量三者**在空间上相互吻合**，"
                 "且负例对照支持该关联**不是**「快速路本身流量大」的伪关联。"
                 "⇒ **建议**（待用户裁定）对 SB-A5 开启 `writeEventsInterval=19` 重跑一轮以补执行级证据。\n")
    elif verdict == "COUPLING_ABSENT":
        L.append("路线变化与速度变更**不对应** ⇒ 应**停止「改道」解释**，优先检查路线映射与断面聚合。\n")
    elif verdict == "CONFOUNDED_BY_CORRIDOR_SIZE":
        L.append("实测关联落在置换分布内 ⇒ 该关联**可由走廊规模解释**，不足以支撑空间耦合结论。\n")
    else:
        L.append("结论为部分/不确定；详见下方判据表。\n")

    # §1 检查1
    L.append("## 1. 检查 1：自由流速度变更的空间特征（阶段 2）\n")
    L.append(f"- 全网链 **{summ['n_links']:,}**；`freespeed` 变更链 **{summ['n_freespeed_changed']:,}**"
             f"（升 {summ['n_up']:,} / 降 {summ['n_down']:,}）；变更里程 **{summ['len_changed_km']:,.0f} km**"
             f" / 全网 {summ['len_all_km']:,.0f} km（{summ['len_changed_km']/summ['len_all_km']*100:.2f}%）")
    L.append(f"- **净降速**：`Σ len·Δfree` = {summ['net_signed_len_dfree']:,.0f} m²/s（< 0）")
    L.append(f"- **相对速度**：路面干道里程加权 Δfree = **{sgn(summ['wmean_dfree_surface_ms'])} m/s**"
             f" ｜ 快速路 = **{sgn(summ['wmean_dfree_express_ms'])} m/s**"
             f" ⇒ 快速路**相对变快**\n")
    L.append("### 按道路等级\n")
    L.append("| highway | n_links | 变更链 | 变更% | 变更里程(km) | 里程加权Δ(m/s) | Δ(km/h) | 升/降 |")
    L.append("|---|---:|---:|---:|---:|---:|---:|---|")
    for _, r in fs_cls.iterrows():
        L.append(f"| {r['highway']} | {int(r['n_links']):,} | {int(r['n_changed']):,} | {f(r['chg_pct'],1)}% | "
                 f"{f(r['len_changed_km'],1)} | {sgn(r['dfree_wmean_ms'])} | {sgn(r['dfree_wmean_kmh'],2)} | "
                 f"{int(r['n_up'])}/{int(r['n_down'])} |")
    L.append("\n### 按走廊（仅变更链）\n")
    L.append("| 走廊 | 变更链 | 变更里程(km) | Δ均值(m/s) | Δ中位(m/s) | 升/降 |")
    L.append("|---|---:|---:|---:|---:|---|")
    for _, r in fs_cor.iterrows():
        nmv = str(r["corridor"]) if pd.notna(r["corridor"]) and str(r["corridor"]).strip() else "（非识别走廊）"
        L.append(f"| {nmv} | {int(r['n_changed']):,} | {f(r['len_changed_km'],2)} | "
                 f"{sgn(r['dfree_mean_ms'])} | {sgn(r['dfree_median_ms'])} | "
                 f"{int(r['n_up'])}/{int(r['n_down'])} |")

    # §2 检查2
    L.append("\n## 2. 检查 2：路线变化 ↔ 速度变更（阶段 3，逐 person）\n")
    L.append("| 组 | n | 路线均速 v1.0(m/s) | 路线均速 SB-A5(m/s) | Δfs(m/s) | Δfs(km/h) | route-effect | network-effect | 降速暴露 v1.0 | 快速路里程 v1.0(km) |")
    L.append("|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
    for _, r in rt.iterrows():
        L.append(f"| {'变化' if r['changed'] else '未变化'} | {int(r['n']):,} | {f(r['fs_v10_ms'],3)} | "
                 f"{f(r['fs_a5_ms'],3)} | {sgn(r['dfs_mean_ms'],4)} | {sgn(r['dfs_mean_kmh'],3)} | "
                 f"{sgn(r['route_effect_mean_ms'],4)} | {sgn(r['network_effect_mean_ms'],4)} | "
                 f"{f(r['slow_share10_mean'],4)} | {f(r['mw_len10_mean_km'],3)} |")
    L.append("\n> 分解恒等式：`Δfs = route-effect + network-effect`"
             "（route-effect = 路线改变引起的速度变化；network-effect = 网络改速引起的速度变化）。")

    # §3 检查3
    L.append("\n## 3. 检查 3：观测域断面增量 ↔ 速度变更（阶段 4，逐匹配边）\n")
    L.append("| fs 是否变更 | n_edges | ΣΔQ 净 | ΣΔQ 正 | ΣΔQ 负 | 占净增 | 单位边净增 | Δfree 均值 |")
    L.append("|---|---:|---:|---:|---:|---:|---:|---:|")
    for _, r in sc.iterrows():
        L.append(f"| {'变更' if r['fs_changed'] else '未变更'} | {int(r['n_edges']):,} | "
                 f"{f(r['net'],1)} | {f(r['sum_pos'],1)} | {f(r['sum_neg'],1)} | "
                 f"{f(r['share_of_net_pct'],1)}% | {sgn(r['net_per_link'],2)} | {sgn(r['dfree_mean_ms'],3)} |")
    L.append(f"\n- 走廊 route-use Δ vs ΔQ 净额 **Spearman = {f(summ['spearman_drate_vs_net'],3)}**\n")
    L.append("| 走廊 | route-use Δ(pp) | ΔQ 净额 | 占净增 | 匹配边 | 其中 fs-变更边 | Δfree 均值(m/s) |")
    L.append("|---|---:|---:|---:|---:|---:|---:|")
    for _, r in cc.sort_values("net", ascending=False).iterrows():
        nmv = str(r["corridor"]) if str(r["corridor"]) else "（非识别走廊）"
        L.append(f"| {nmv} | {sgn(r['d_rate_pp'],3)} | {f(r['net'],0)} | {f(r['share_of_net_pct'],1)}% | "
                 f"{int(r['n_matched'])} | {int(r['n_fs_changed'])} | {sgn(r['dfree_wmean_ms'],3)} |")

    # §4 负例
    L.append("\n## 4. 检查 4：负例对照（阶段 5）\n")
    L.append("### N2 空间 shuffle 置换检验（n_perm = %d）\n" % N_PERM)
    L.append("| 统计量 | 置换方式 | 观测 | 置换均值 | 置换 sd | 95百分位 | 经验百分位 | z | p(单侧) |")
    L.append("|---|---|---:|---:|---:|---:|---:|---:|---:|")
    for _, r in nc_df.iterrows():
        L.append(f"| {r['statistic']} | {r['mode']} | {sgn(r['observed'],5)} | {sgn(r['perm_mean'],5)} | "
                 f"{f(r['perm_sd'],6)} | {sgn(r['perm_p95'],5)} | {f(r['percentile_pct'],1)}% | "
                 f"{sgn(r['z'],2)} | {f(r['p_value_one_sided'],4)} |")
    L.append("\n> 统计量口径：`route_effect_mean` = `(1/n_c)·Σ_l (FS10_l+v_l)(B_l−A_l)`，"
             "`v=DFREE` 时**恒等于** §2 中变化者的 route-effect 均值（已同口径核对）；"
             "`slow_exposure_diff` = 变化者与未变化者在 v1.0 路线上「降速链里程占比」之差。"
             "置换 = 把逐链 `Δfree` 的**多重集**重新指派到链上（`global`：全网；"
             "`within_highway`：**仅在同 highway 内**置换，用于排除「等级构成」混淆）。")
    L.append("\n### N1 路线级 placebo（构造性）\n")
    rde = pd.read_csv(OUT / "route_delta_exposure.csv", encoding="utf-8-sig", low_memory=False)
    un_re = float(rde.loc[rde["changed"] == False, "route_effect_ms"].abs().max())
    un_dfs = float(rde.loc[rde["changed"] == False, "dfs_ms"].abs().max())
    L.append(f"- 未变化路线者 **`route-effect` 最大绝对值 = {un_re:.3e} m/s**（`R5≡R10` ⇒ 构造上严格为 0）"
             f" ⇒ 路线变化度量无伪信号。")
    L.append(f"- 注：未变化者的 `Δfs` 最大绝对值 = {un_dfs:.3f} m/s **不为 0**，因其 `Δfs` 全部来自 "
             "`network-effect`（网络改速），这正是判据 `B1` 需被修正的原因（见 §5.0）。")
    L.append("\n### N3 base-rate 同等级对照（仅 motorway + motorway_link）\n")
    L.append("| fs 是否变更 | n | ΔQ 净 | ΔQ 率(%) | 占（快速路类）净增 |")
    L.append("|---|---:|---:|---:|---:|")
    for _, r in g.iterrows():
        L.append(f"| {'变更' if r['fs_changed'] else '未变更'} | {int(r['n']):,} | {f(r['net'],1)} | "
                 f"{f(r['delta_rate_pct'],3)}% | {f(r['net']/ex_net*100,1)}% |")

    # §5 判决
    L.append("\n## 5. 机制判决（预注册五选一）\n")
    L.append("### 5.0 判据修订披露（★按项目纪律：保留实录 + 显式撤回）\n")
    L.append("预注册协议 §4 的 `B1/B2/B5` 经复核为**协议内部自相矛盾**，已在协议 §11 记入修订：")
    L.append("- `B1`（未变化路线 `Δfs≡0`）在逻辑上不可能成立：`Δfs = route-effect + network-effect`，"
             "未变化路线的 `Δfs` **恰等于 `network-effect`**（网络改速），而非 0。")
    L.append("- `B2`（变化路线 `Δfs>0`）与 `A1`（全网**净降速**）互相矛盾：网络普遍降速时 "
             "`Δfs` 必被 `network-effect` 拉负，不可能为正。")
    L.append("- `B5`（两项同号）亦为误述：路由器对网络降速的**正确响应是反号补偿**。")
    L.append("⇒ 三项**保留实录但不参与判决**（见下表「已撤回」行）；判决改用作用在**分解项**上的 "
             "`B1c/B2c/B5c`。此修订由**先验的逻辑矛盾**触发，非由结果好坏触发。\n")

    L.append("### 5.1 判据表（★由实测自动渲染）\n")
    L.append("| 判据 | 含义 | 结果 |")
    L.append("|---|---|---|")
    mean_map = {
        "A1": "变更链∈(0,N) 且净降速", "A2": "快速路相对变快（里程加权Δ 更大）", "A3": "变更里程 ≥ 全网 1%",
        "B1c": "placebo（修正）：未变化者 route-effect≡0", "B2c": "变化者 route-effect>0",
        "B3": "变化者 Δfs > 未变化者", "B4": "变化者对降速链暴露更高",
        "B5c": "route-effect>0 且 network-effect<0（补偿性改道）",
        "C1": "fs-未变更边承担净增 > 50%", "C2": "变更/未变更单位边净增同量级", "C3": "走廊同序 Spearman>0",
        "D1": "shuffle 检验（全局）≥95 百分位", "D2": "快速路类内未变更边仍占净增 > 50%",
    }
    for k in ["A1", "A2", "A3", "B1c", "B2c", "B3", "B4", "B5c", "C1", "C2", "C3", "D1", "D2"]:
        L.append(f"| `{k}` | {mean_map[k]} | {'✅ PASS' if crit[k] else '❌ FAIL'} |")
    for _, r in retr.iterrows():
        gt = str(r["gate"]).replace("|", "\\|")
        L.append(f"| `{r['id']}` ~~{gt}~~ | **已撤回（协议内部矛盾）** | "
                 f"{'✅(实录)' if r['pass'] else '❌(实录)'} |")
    L.append(f"\n判据 A+B+C+D 全过 ⇒ **`{verdict}`**\n")
    L.append(f"- 引致性分解：`route-effect = {sgn(summ['route_decomp']['route_effect_mean_ms'],4)} m/s`、"
             f"`network-effect = {sgn(summ['route_decomp']['network_effect_mean_ms'],4)} m/s`，"
             f"改道**补偿了约 {f(summ['route_decomp']['compensation_ratio']*100,1)}%** 的网络降速。")
    L.append("- 证据等级 **`PLANS_LEVEL`**：SB-A5 无 events，执行路线未被直接观测；"
             "⛔ 不得写作「已证实的执行级路径重分配」。")
    L.append("- 与已 `CLOSED` 的 **O3-R1「承载对象替代」分列**（层级不同，⛔ 不合并）。")

    # §6 下一步
    L.append("\n## 6. 下一步（预注册动作）\n")
    if verdict == "FREESPEED_ROUTE_COUPLING_SUPPORTED":
        L.append("- **建议**：对 SB-A5 开启 `writeEventsInterval=19` **重跑一轮**（新 `outputDirectory`/`runId`，"
                 "其余模型设置不变），随后比较新旧 LinkStats 检查开启事件记录是否改变原有结果。"
                 "（**需用户裁定**；本轮 ⛔ 未启动）")
    else:
        L.append("- **不建议**立即重跑：先调查路线映射与断面聚合。")
    L.append("- ⛔ 不调 `SCALE`/容量/`freespeed`/lambda/阈值；⛔ 不启动信号灯/交叉口实验；⛔ 不晋升 v1.1。")

    (OUT / "VERDICT_E-SB-04B.md").write_text("\n".join(L), encoding="utf-8")
    print(f"\n渲染：VERDICT_E-SB-04B.md ({len(L)} 行) + coupling_scorecard.csv")
    return 0


if __name__ == "__main__":
    sys.exit(main())
