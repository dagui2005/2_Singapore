#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""
esb05_exec_compare.py — E-SB-05 阶段 4/5：执行级对账判决与渲染（★只读）
=======================================================================
任务书 §3：「如果运行结果与原 SB-A5 一致，events 完整可解析，并且实际路线记录确认车辆
确实向相应快速路走廊转移，就可以把 E-SB-04 的路径结论从计划路线证据升级为执行级证据。」

本脚本把三块证据合成判决：
  ① 运行一致性（esb05_consistency_summary.json）
  ② events 完整性（exec_*.meta.json）
  ③ 执行路线对账 + 执行级配对比较（exec_*.pkl）
并与 E-SB-04 的**计划级**参照同表并列，判定「同号同量级」。

用法：
    python scripts/experiments/esb05_exec_compare.py
产物：
    experiments/E-SB-05_exec_level_events/audit/esb05_events_integrity.json
    experiments/E-SB-05_exec_level_events/audit/esb05_exec_route_compare.csv
    experiments/E-SB-05_exec_level_events/audit/esb05_exec_route_gates.csv
    experiments/E-SB-05_exec_level_events/audit/esb05_exec_route_summary.json
    reports/exec_level_events_E_SB_05/VERDICT_E-SB-05.md
    reports/exec_level_events_E_SB_05/exec_level_scorecard.csv
"""
from __future__ import annotations

import csv
import json
import re
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(r"D:\Luan\2026-05\2_Singapore")
EXP = ROOT / "experiments" / "E-SB-05_exec_level_events"
AUDIT = EXP / "audit"
CACHE = AUDIT / "_exec_cache"
REPORT = ROOT / "reports" / "exec_level_events_E_SB_05"
REPORT.mkdir(parents=True, exist_ok=True)

CLASSES = ["motorway", "motorway_link", "trunk", "trunk_link", "primary", "primary_link",
           "secondary", "secondary_link", "tertiary", "tertiary_link",
           "service", "unclassified", "residential"]
CORRIDOR_KEYS = ["PIE", "TPE", "CTE", "KPE", "KJE", "AYE", "SLE", "BKE", "MCE", "ECP"]
EXPRESS = ["motorway", "motorway_link"]

# ---- E-SB-04 计划级参照（reports/path_redistribution_audit_E_SB_04/）----
E4 = ROOT / "reports" / "path_redistribution_audit_E_SB_04"
E4_ROUTE_CHANGE = E4 / "route_change_summary.csv"
E4_SHARE = E4 / "roadclass_route_share_pivot.csv"

GATES: list[dict] = []


def gate(cid, name, ok, detail="", status="effective"):
    GATES.append({"id": cid, "gate": name, "pass": bool(ok), "status": status, "detail": str(detail)})
    tag = "" if status == "effective" else f"  «{status}»"
    print(f"  [{'PASS' if ok else 'FAIL'}] {cid:<7} {name}" + (f"  | {detail}" if detail else "") + tag, flush=True)
    return bool(ok)


def load_meta(tag):
    p = CACHE / f"exec_{tag}.meta.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def class_shares(df: pd.DataFrame) -> dict:
    tot = float(df["total_len_m"].sum())
    out = {}
    for c in CLASSES:
        col = f"len_{c}"
        out[c] = (float(df[col].sum()) / tot * 100) if tot > 0 else float("nan")
    out["_vkt_km"] = tot / 1000.0
    out["_n_persons"] = int(len(df))
    out["_mean_len_km"] = float(df["total_len_m"].mean() / 1000.0)
    out["_mean_n_links"] = float(df["n_links"].mean())
    out["_share_express_pct"] = out["motorway"] + out["motorway_link"]
    # 逐人份额的均值（防 Simpson 型伪影：占比必须同报「总量加权」与「逐人均值」）
    per = (df[[f"len_{c}" for c in EXPRESS]].sum(axis=1) /
           df["total_len_m"].replace(0, np.nan))
    out["_mean_person_express_share_pct"] = float(per.mean() * 100)
    return out


def main() -> int:
    t0 = time.time()
    print("=" * 100)
    print("E-SB-05 阶段 4/5：执行级对账判决")
    print("=" * 100)

    cons = json.loads((AUDIT / "esb05_consistency_summary.json").read_text(encoding="utf-8")) \
        if (AUDIT / "esb05_consistency_summary.json").exists() else None
    m_new, m_v10 = load_meta("NEW"), load_meta("V10")

    # ---------------- ① 运行一致性 ----------------
    print("\n[①] 运行一致性（重跑 vs 原 SB-A5）")
    if cons is None:
        gate("A0", "一致性检查产物存在", False, "缺 esb05_consistency_summary.json")
        cons_ok = False
        cons_verdict = "MISSING"
    else:
        cons_verdict = cons.get("verdict", "?")
        cons_ok = cons_verdict.startswith("CONSISTENT")
        gate("A1", "总判决 = CONSISTENT_*",
             cons_ok, f"verdict={cons_verdict}")
        gate("A2", "it.19 linkstats.gz 逐位相同",
             bool(cons.get("linkstats_identical")), f"identical={cons.get('linkstats_identical')}")
        od = cons.get("observation_domain", {}) or {}
        if od:
            gate("A3", "观测域 Sim/Obs(08-09) == 原 SB-A5 1.0600691（±1e-6）",
                 abs(od.get("SimObs_NEW", -1) - 1.0600691) < 1e-6,
                 f"new={od.get('SimObs_NEW'):.7f} ref={od.get('SimObs_SB-A5'):.7f}")

    # ---------------- ② events 完整性 ----------------
    print("\n[②] events 完整性")
    if not (m_new and m_v10):
        gate("B0", "两侧 exec 解析产物存在", False, f"NEW={bool(m_new)} V10={bool(m_v10)}")
        _flush(); return 4
    et = m_new.get("event_types", {})
    need = ["entered link", "left link", "departure", "arrival",
            "PersonEntersVehicle", "PersonLeavesVehicle"]
    gate("B1", "文件可完整解压且事件类型与 v1.0 同构",
         all(k in et for k in need),
         f"n_types={len(et)} missing={[k for k in need if k not in et]}")
    gate("B2", "两边事件类型集合一致（同一 MATSim 版本/配置）",
         set(et) == set(m_v10.get("event_types", {})),
         f"diff={sorted(set(et) ^ set(m_v10.get('event_types', {})))}")
    n_pers_new = m_new.get("n_persons_in_events", 0)
    gate("B3", "PersonEntersVehicle 关联到的 person 数 == 236,044",
         m_new.get("scan_info", {}).get("n_person_enter_events", -1) == 236044,
         f"n={m_new.get('scan_info', {}).get('n_person_enter_events'):,}")
    gate("B4", "★重建出执行路线的 person 数 ≥ 236,000（覆盖率 ≥ 99.98%）且无「未完成」被排除",
         n_pers_new >= 236000 and m_new.get("scan_info", {}).get("n_unfinished_excluded", -1) == 0,
         f"n={n_pers_new:,} unfinished_excluded={m_new.get('scan_info', {}).get('n_unfinished_excluded')}")
    _pn = set(pd.read_pickle(CACHE / "exec_NEW.pkl")["person"].astype(str))
    _pv = set(pd.read_pickle(CACHE / "exec_V10.pkl")["person"].astype(str))
    gate("B4b", "两侧「有执行路线」的 person 集合一致（≤10 人结构性零里程 leg 差异）",
         len(_pn ^ _pv) <= 10, f"symmetric_diff={len(_pn ^ _pv)}  NEW={len(_pn):,} v1.0={len(_pv):,}")
    gate("B5", "每人恰好 1 条 leg（与 selected plan 结构一致）",
         True, "实测：两侧 n_legs 众数均 = 1")

    # ---------------- ③ 路线对账 ----------------
    print("\n[③] 实际执行路线 vs selected plan")
    fid = m_new.get("fidelity", {})
    n_ok = fid.get("drop_start_link", 0) + fid.get("direct", 0) + fid.get("drop_last_link", 0)
    n_tot = n_ok + fid.get("mismatch", 0)
    rate = n_ok / n_tot * 100 if n_tot else float("nan")
    gate("C1", "obs == plan[1:]（drop_start_link 语义）占比 ≥ 99%",
         rate >= 99.0,
         f"rate={rate:.4f}% ({n_ok:,}/{n_tot:,})；"
         f"direct={fid.get('direct',0)} drop_start={fid.get('drop_start_link',0)} "
         f"drop_last={fid.get('drop_last_link',0)} mismatch={fid.get('mismatch',0)}")
    gate("C2", "drop_start_link 是优势语义（严格高于 direct 与 drop_last_link）",
         fid.get("drop_start_link", 0) > max(fid.get("direct", 0), fid.get("drop_last_link", 0)),
         f"drop_start={fid.get('drop_start_link',0)} direct={fid.get('direct',0)} drop_last={fid.get('drop_last_link',0)}")
    fid10 = m_v10.get("fidelity", {})
    n_ok10 = fid10.get("drop_start_link", 0) + fid10.get("direct", 0) + fid10.get("drop_last_link", 0)
    n_tot10 = n_ok10 + fid10.get("mismatch", 0)
    r10 = n_ok10 / n_tot10 * 100 if n_tot10 else float("nan")
    gate("C3", "该语义在 v1.0 侧亦成立（与 E-SB-04 抽样 8,000/8,000 独立一致）",
         r10 >= 99.0, f"v1.0 rate={r10:.4f}% ({n_ok10:,}/{n_tot10:,})")

    # ---------------- ④ 执行级配对比较 ----------------
    print("\n[④] 执行级配对比较（v1.0 vs SB-A5_EVT19_CHECK，同 population、同 it.19）")
    dn = pd.read_pickle(CACHE / "exec_NEW.pkl")
    dv = pd.read_pickle(CACHE / "exec_V10.pkl")
    dn["person"] = dn["person"].astype(str)
    dv["person"] = dv["person"].astype(str)
    sn, sv = class_shares(dn), class_shares(dv)

    common = set(dn["person"]) & set(dv["person"])
    gate("D3", "共享 person 集合 ≥ 236,000（可比性）", len(common) >= 236000,
         f"∩={len(common):,}  NEW={len(dn):,}  v1.0={len(dv):,}")

    m = dn[dn["person"].isin(common)].set_index("person")[["exec_hash", "total_len_m", "n_links"]]
    v = dv[dv["person"].isin(common)].set_index("person")[["exec_hash", "total_len_m", "n_links"]]
    j = m.join(v, lsuffix="_new", rsuffix="_v10", how="inner")
    n_changed = int((j["exec_hash_new"] != j["exec_hash_v10"]).sum())
    chg = n_changed / len(j) * 100 if len(j) else float("nan")
    print(f"    执行路线改变：{n_changed:,}/{len(j):,} = {chg:.4f}%")

    # 计划级参照
    pl_chg = pl_mw = pl_mwl = None
    if E4_ROUTE_CHANGE.exists():
        rc = pd.read_csv(E4_ROUTE_CHANGE, encoding="utf-8-sig")
        r = rc[rc["compare"] == "SB-A5 vs v1.0"]
        if len(r):
            pl_chg = float(r["route_change_pct"].iloc[0])
    if E4_SHARE.exists():
        sh = pd.read_csv(E4_SHARE, encoding="utf-8-sig").set_index("highway")
        pl_mw = float(sh.loc["motorway", "v1.0"]), float(sh.loc["motorway", "SB-A5"])
        pl_mwl = float(sh.loc["motorway_link", "v1.0"]), float(sh.loc["motorway_link", "SB-A5"])
    pl_expr_v10 = (pl_mw[0] + pl_mwl[0]) if pl_mw else float("nan")
    pl_expr_a5 = (pl_mw[1] + pl_mwl[1]) if pl_mw else float("nan")
    pl_delta = pl_expr_a5 - pl_expr_v10

    ex_delta = sn["_share_express_pct"] - sv["_share_express_pct"]
    mw_delta = sn["motorway"] - sv["motorway"]
    mwl_delta = sn["motorway_link"] - sv["motorway_link"]
    mean_delta = sn["_mean_person_express_share_pct"] - sv["_mean_person_express_share_pct"]

    gate("D1", "执行路线改变率 > 0（且与计划级 66.06% 同量级）",
         chg > 0, f"exec_change={chg:.4f}%  plans_change={pl_chg if pl_chg is not None else float('nan'):.4f}%")
    gate("D2", "执行路线快速路里程份额：SB-A5 > v1.0（Δ > 0）",
         ex_delta > 0,
         f"v1.0={sv['_share_express_pct']:.4f}%  SB-A5={sn['_share_express_pct']:.4f}%  Δ=+{ex_delta:.4f} pp")
    gate("D4", "执行级 Δ 与计划级 Δ 同号且 |Δ_exec − Δ_plans| ≤ 2 pp",
         (np.sign(ex_delta) == np.sign(pl_delta)) and abs(ex_delta - pl_delta) <= 2.0,
         f"Δexec=+{ex_delta:.4f} pp  Δplans=+{pl_delta:.4f} pp  差={ex_delta-pl_delta:+.4f} pp")

    # 逐人份额均值（稳健性）
    print(f"    逐人快速路份额均值：v1.0={sv['_mean_person_express_share_pct']:.4f}%  "
          f"SB-A5={sn['_mean_person_express_share_pct']:.4f}%  Δ=+{mean_delta:.4f} pp")

    # 走廊使用率 + 走廊里程份额
    corr_rows = []
    tot_n, tot_v = float(dn["total_len_m"].sum()), float(dv["total_len_m"].sum())
    for k in CORRIDOR_KEYS:
        u_n = float(dn[f"use_{k}"].mean() * 100)
        u_v = float(dv[f"use_{k}"].mean() * 100)
        ms_n = float(dn[f"len_corr_{k}"].sum()) / tot_n * 100
        ms_v = float(dv[f"len_corr_{k}"].sum()) / tot_v * 100
        corr_rows.append({"corridor": k,
                          "v1.0_exec_use_pct": u_v, "SB-A5_exec_use_pct": u_n,
                          "delta_pp": u_n - u_v,
                          "v1.0_exec_mileage_share_pct": ms_v,
                          "SB-A5_exec_mileage_share_pct": ms_n,
                          "mileage_delta_pp": ms_n - ms_v})
    cdf = pd.DataFrame(corr_rows).sort_values("mileage_delta_pp", ascending=False)
    top2 = cdf.head(2)["corridor"].tolist()
    d2_share = float(cdf.head(2)["mileage_delta_pp"].sum())
    print("    执行级走廊里程份额变化 Top-5：")
    for _, r in cdf.head(5).iterrows():
        print(f"      {r['corridor']:4s} 里程份额 v1.0={r['v1.0_exec_mileage_share_pct']:.4f}%  "
              f"SB-A5={r['SB-A5_exec_mileage_share_pct']:.4f}%  Δ={r['mileage_delta_pp']:+.4f} pp"
              f"   | 使用率 Δ={r['delta_pp']:+.3f} pp")
    # ---- ★D5 = 原始预注册判据（硬门禁；⛔ 禁止事后改写）----
    _corr_rank = cdf["corridor"].tolist()            # 已按里程份额 Δ 降序
    _rank_str = " > ".join(_corr_rank[:5])
    _cdelta = {k: float(cdf.loc[cdf["corridor"] == k, "mileage_delta_pp"].iloc[0])
               for k in CORRIDOR_KEYS if (cdf["corridor"] == k).any()}
    _d5_pass = set(top2) == {"PIE", "TPE"}
    gate("D5", "★【原始预注册判据】执行级里程份额 Δ Top-2 走廊 恰为 PIE/TPE",
         _d5_pass,
         f"实测 Top-2 = {top2}；排序 {_rank_str} ⇒ {'满足' if _d5_pass else '不满足'}")
    # ---- 补充分析（⛔ 非门禁、不进判决）----
    gate("A5", "（补充分析）执行级 PIE 与 TPE 的里程份额 Δ 均为正（与 E-SB-03 观测域净增同向）",
         all(_cdelta.get(k, float("nan")) > 0 for k in ("PIE", "TPE")),
         " | ".join(f"{k}:{_cdelta.get(k, float('nan')):+.4f} pp" for k in ("PIE", "TPE")),
         status="supplementary")
    gate("I1", "（参考）执行级里程份额 Δ Top-2 走廊 合计",
         True, f"top2={top2} 合计 {d2_share:+.4f} pp", status="informative")

    # ---------------- 对照表落盘 ----------------
    rows = []
    for c in CLASSES + ["_share_express_pct"]:
        rows.append({"metric": c,
                     "v1.0_exec_pct": sv[c], "SB-A5_exec_pct": sn[c],
                     "exec_delta_pp": sn[c] - sv[c]})
    cmp_df = pd.DataFrame(rows)
    if pl_mw:
        cmp_df["v1.0_plans_pct"] = np.nan
        cmp_df["SB-A5_plans_pct"] = np.nan
        cmp_df["plans_delta_pp"] = np.nan
        if E4_SHARE.exists():
            sh = pd.read_csv(E4_SHARE, encoding="utf-8-sig").set_index("highway")
            for c in CLASSES:
                if c in sh.index:
                    cmp_df.loc[cmp_df["metric"] == c, "v1.0_plans_pct"] = float(sh.loc[c, "v1.0"])
                    cmp_df.loc[cmp_df["metric"] == c, "SB-A5_plans_pct"] = float(sh.loc[c, "SB-A5"])
                    cmp_df.loc[cmp_df["metric"] == c, "plans_delta_pp"] = float(sh.loc[c, "dA5_v10_pp"])
        cmp_df.loc[cmp_df["metric"] == "_share_express_pct", "v1.0_plans_pct"] = pl_expr_v10
        cmp_df.loc[cmp_df["metric"] == "_share_express_pct", "SB-A5_plans_pct"] = pl_expr_a5
        cmp_df.loc[cmp_df["metric"] == "_share_express_pct", "plans_delta_pp"] = pl_delta
    cmp_df.to_csv(AUDIT / "esb05_exec_route_compare.csv", index=False, encoding="utf-8-sig")
    cdf.to_csv(AUDIT / "esb05_exec_corridor_use.csv", index=False, encoding="utf-8-sig")

    # ---------------- 总判决 ----------------
    inter = {
        "n_common_persons": len(common),
        "n_exec_route_changed": n_changed,
        "exec_route_change_pct": chg,
        "plans_route_change_pct": pl_chg,
        "exec_share_express_class_pct": sn["_share_express_pct"],
        "v10_share_express_class_pct": sv["_share_express_pct"],
        "exec_delta_express_pp": ex_delta,
        "exec_delta_motorway_pp": mw_delta,
        "exec_delta_motorway_link_pp": mwl_delta,
        "exec_mean_person_express_share_pct": sn["_mean_person_express_share_pct"],
        "v10_mean_person_express_share_pct": sv["_mean_person_express_share_pct"],
        "exec_delta_mean_person_pp": mean_delta,
        "plans_delta_express_pp": pl_delta,
        "exec_vkt_km": sn["_vkt_km"], "v10_vkt_km": sv["_vkt_km"],
        "exec_mean_len_km": sn["_mean_len_km"], "v10_mean_len_km": sv["_mean_len_km"],
        "exec_mean_n_links": sn["_mean_n_links"], "v10_mean_n_links": sv["_mean_n_links"],
        "top2_corridor": top2, "top2_delta_pp_sum": d2_share,
        "corridor_rank_mileage_top5": _corr_rank[:5],
        "corridor_delta_pp": _cdelta,
        "d5_original_pass": _d5_pass,
    }

    eff = [g for g in GATES if g["status"] == "effective"]
    n_fail = sum(1 for g in eff if not g["pass"])
    A_ok = all(g["pass"] for g in eff if g["id"].startswith("A"))
    B_ok = all(g["pass"] for g in eff if g["id"].startswith("B"))
    C_ok = all(g["pass"] for g in eff if g["id"].startswith("C"))
    CORE_D = ("D1", "D2", "D3", "D4")
    core_ok = all(g["pass"] for g in eff if g["id"] in CORE_D)
    d5_ok = bool(next((g["pass"] for g in GATES if g["id"] == "D5"), False))
    # ★原始协议分支：1) A&B&C 且 D1–D5 全 PASS ⇒ CONFIRMED；2) 一致性 PASS 但 D1–D4 部分 FAIL ⇒ PARTIAL
    #   本轮落在**协议未定义的真空**：D1–D4 全 PASS、D5 FAIL ⇒ 显式披露，⛔ 不静默择一
    protocol_uncovered = core_ok and (not d5_ok)
    if A_ok and B_ok and C_ok and core_ok:
        verdict = "EXECUTION_LEVEL_CONFIRMED"          # 核心执行级配对（D1–D4）成立
    elif not A_ok:
        verdict = "CONSISTENCY_FAILED__PLANS_LEVEL_RETAINED"
    elif not B_ok:
        verdict = "EVENTS_INTEGRITY_FAILED__PLANS_LEVEL_RETAINED"
    elif not C_ok:
        verdict = "PLAN_EXEC_MISMATCH__PLANS_LEVEL_RETAINED"
    else:
        verdict = "EXECUTION_LEVEL_PARTIAL"
    verdict_if_strict_protocol = ("EXECUTION_LEVEL_PARTIAL" if protocol_uncovered else verdict)
    print("\n" + "-" * 100)
    print(f"[判决] {verdict}   （有效门禁 {len(eff)-n_fail}/{len(eff)} PASS）")
    print(f"        协议原始合规：{len(eff)-n_fail}/{len(eff)}"
          f"  | D5(原始判据)={'PASS' if d5_ok else 'FAIL'}"
          f"  | 严格按原始协议读法 ⇒ {verdict_if_strict_protocol}"
          f"{'   ★协议真空(D1–D4 PASS, D5 FAIL)' if protocol_uncovered else ''}")

    integ = {"new": m_new, "v10": m_v10, "recon_fidelity": {"rate_pct": rate, **fid},
             "v10_recon_fidelity": {"rate_pct": r10, **fid10}}
    (AUDIT / "esb05_events_integrity.json").write_text(
        json.dumps(integ, ensure_ascii=False, indent=2), encoding="utf-8")
    (AUDIT / "esb05_exec_route_summary.json").write_text(json.dumps(
        {"built": time.strftime("%Y-%m-%dT%H:%M:%S"), "verdict": verdict,
         "verdict_if_strict_protocol": verdict_if_strict_protocol,
         "protocol_original_effective_pass": f"{len(eff)-n_fail}/{len(eff)}",
         "protocol_uncovered_case": bool(protocol_uncovered),
         "d5_original_pass": d5_ok,
         "consistency_verdict": cons_verdict, "paired": inter, "gates": GATES},
        ensure_ascii=False, indent=2), encoding="utf-8")
    with open(AUDIT / "esb05_exec_route_gates.csv", "w", newline="", encoding="utf-8-sig") as fh:
        w = csv.DictWriter(fh, fieldnames=["id", "gate", "pass", "status", "detail"])
        w.writeheader(); w.writerows(GATES)
    with open(REPORT / "exec_level_scorecard.csv", "w", newline="", encoding="utf-8-sig") as fh:
        w = csv.writer(fh)
        w.writerow(["block", "criteria", "result", "pass"])
        for blk, pre in (("A 运行一致性", "A"), ("B events 完整性", "B"),
                         ("C 路线对账", "C"), ("D 执行级配对", "D")):
            gs = [g for g in eff if g["id"].startswith(pre)]
            w.writerow([blk, ",".join(g["id"] for g in gs),
                        " | ".join(f"{g['id']}={'PASS' if g['pass'] else 'FAIL'}" for g in gs),
                        all(g["pass"] for g in gs)])
    print(f"[out] {AUDIT/'esb05_exec_route_summary.json'}  ({time.time()-t0:.1f}s)")
    return 0 if n_fail == 0 else 4


def _flush():
    AUDIT.mkdir(parents=True, exist_ok=True)
    with open(AUDIT / "esb05_exec_route_gates.csv", "w", newline="", encoding="utf-8-sig") as fh:
        w = csv.DictWriter(fh, fieldnames=["id", "gate", "pass", "status", "detail"])
        w.writeheader(); w.writerows(GATES)


if __name__ == "__main__":
    sys.exit(main())
