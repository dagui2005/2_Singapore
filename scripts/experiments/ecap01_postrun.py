#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""
ecap01_postrun.py — E-CAP-01 运行后验收门 + 冻结口径复算（零仿真 / 只读）

定位：`E-CAP-01` 是 `7.9A-1 / A1_capf0p435` 的**干净重跑**（模型层 0 差异）。
本器**不改任何冻结件**，只做两件事：

  [§11.3] 运行后硬门
    P-01  v1.0 冻结目录 mtime 未变（对照 audit/ecap01_v10_mtime_before.json）
    P-02  E-CAP-01 输出目录为实验专属、不在 v1.0 内
    P-03  never_arrived == 0（legHistogram 全天口径：Σdep − Σarr）
    P-04  max stuck_car == 0（legHistogram 逐 bin 峰值）
    P-05  CAPACITY 语义消解（BASE_CAPACITY ⇒ E-CAP-01 用 cap_mul=1/SCALE）
    P-06  v1.0 face_metrics 自校验（82 / 1.1514 km / 2813 / 220 / 7985）

  [复现靶] 与 7.9A-1 的冻结护栏逐位对账
    P-07  冻结模块复算 v1.0 Sim/Obs == 0.9993347696792919（±1e-9）
    P-08  冻结模块复算 E-CAP-01 Sim/Obs == A-1 0.7664760994478101（cycle）/ 0.7725115296237909（it.19）

★口径：`Sim/Obs(FROZEN)` = Σ_{g} sim_8_9_scaled / Σ_g obs_8_9（LTA 段 ↔ MATSim 必用 Q_sim,g = Σ_{l∈M_g} Q_l，
   K 基数并报）。全部复用 `evaluate_demand_response_7_6f_1.eval_run`（与 v1.0 冻结值同源）。

⛔ 不改 v1.0 / A-1 / crosswalk / TrafficFlow；⛔ 不写 A-1 报告目录（全部落 E-CAP-01 自己的 audit/）。

用法
----
    python scripts/experiments/ecap01_postrun.py            # 全量（含 cycle-mean 护栏，≈1–3 min）
    python scripts/experiments/ecap01_postrun.py --no-cycle # 只用 it.19（快，跳过 cycle 聚合）
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(r"D:\Luan\2026-05\2_Singapore")
SCRIPTS_OD = ROOT / "scripts" / "od"
sys.path.insert(0, str(SCRIPTS_OD))

import audit_sampling_capacity_7_9a1 as A1  # noqa: E402  ★ 冻结评价器（只读复用）

# --------------------------------------------------------------------------
# 路径（全部只读；写入仅限 E-CAP-01/audit）
# --------------------------------------------------------------------------
ECAP = ROOT / "experiments" / "E-CAP-01_scale_capacity"
ECAP_AUDIT = ECAP / "audit"
ECAP_OUT = ECAP / "outputs" / "E-CAP-01"
ECAP_RUN = "E-CAP-01"
ECAP_LS19 = ECAP_OUT / "ITERS" / "it.19" / f"{ECAP_RUN}.19.linkstats.txt.gz"
ECAP_LH19 = ECAP_OUT / "ITERS" / "it.19" / f"{ECAP_RUN}.19.legHistogram.txt"
MTIME_BEFORE = ECAP_AUDIT / "ecap01_v10_mtime_before.json"

A1_GR_CACHE = ROOT / "reports" / "sampling_capacity_7_9a1" / "_guardrail_cache"

# 冻结靶值（来自 reports/sampling_capacity_7_9a1/_guardrail_cache/，2026-09-29 冻结）
V10_SIM_OBS_CYCLE = 0.9993347696792919
V10_SIM_OBS_IT19 = 1.0014525031000747
A1_SIM_OBS_CYCLE = 0.7664760994478101
A1_SIM_OBS_IT19 = 0.7725115296237909

CHECKS: list[dict] = []
NOTES: list[str] = []


def gate(cid: str, name: str, ok: bool, detail: str = "") -> bool:
    CHECKS.append({"check": cid, "name": name, "pass": bool(ok), "detail": str(detail)})
    print(f"  [{'PASS' if ok else 'FAIL'}] {cid:<6} {name}  ({detail})", flush=True)
    return bool(ok)


def mtime_now() -> dict:
    snap = {}
    for rel in ("matsim_final_7_6h", r"matsim_final_7_6h\configs",
                r"matsim_final_7_6h\outputs\W01_rc_min"):
        p = ROOT / rel
        snap[rel] = p.stat().st_mtime if p.exists() else None
    return snap


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-cycle", action="store_true", help="跳过 cycle-mean 护栏（快）")
    args = ap.parse_args()

    t0 = time.time()
    ECAP_AUDIT.mkdir(parents=True, exist_ok=True)
    # ★把冻结评价器的写目录重定向到 E-CAP-01 自己的 audit/，绝不落 A-1 报告目录
    A1.OUT = ECAP_AUDIT
    A1.CYCLE_DIR = ECAP_AUDIT / "_cycle_linkstats"
    A1.GR_DIR = ECAP_AUDIT / "_guardrail_cache"
    A1.CYCLE_DIR.mkdir(parents=True, exist_ok=True)
    A1.GR_DIR.mkdir(parents=True, exist_ok=True)

    print("=" * 92)
    print("E-CAP-01 运行后验收门 + 冻结口径复算（零仿真 / 只读）")
    print("=" * 92)

    if not ECAP_LS19.exists():
        print(f"!! 未找到 E-CAP-01 it.19 linkstats：{ECAP_LS19}")
        return 3

    # ---------------- [P-01/P-02] 冻结件漂移 + 输出目录专属 ----------------
    print("\n[1] 冻结件核验")
    before = json.loads(MTIME_BEFORE.read_text(encoding="utf-8"))
    now = mtime_now()
    drift = {k: (now.get(k), v) for k, v in before.items()}
    drift_ok = all(now.get(k) == v for k, v in before.items())
    gate("P-01", "v1.0 冻结目录 mtime 未变（0 漂移）", drift_ok,
         "drift=NONE" if drift_ok else f"drift={ {k: d for k, d in drift.items() if d[0] != d[1]} }")

    out_resolved = ECAP_OUT.resolve()
    ecap_root = ECAP.resolve()
    v10_root = (ROOT / "matsim_final_7_6h").resolve()
    inside_ecap = str(out_resolved).lower().startswith(str(ecap_root).lower())
    inside_v10 = str(out_resolved).lower().startswith(str(v10_root).lower())
    gate("P-02", "输出目录为实验专属且不在 v1.0 内", inside_ecap and not inside_v10,
         str(out_resolved))

    # ---------------- [load] linkstats + legHistogram ----------------
    print("\n[2] 载入 v1.0 / E-CAP-01 it.19")
    v10_L = A1.load_linkstats(A1.V10_LS)
    ecap_L = A1.load_linkstats(ECAP_LS19)
    v10_lh = A1.load_leg_hist(A1.V10_LH)
    ecap_lh = A1.load_leg_hist(ECAP_LH19)
    gate("E01", "v1.0 it.19 linkstats 载入", len(v10_L) == 693575, f"n_links={len(v10_L)}")
    gate("E01b", "E-CAP-01 it.19 linkstats 载入（同一网络 ⇒ 同链数）",
         len(ecap_L) == len(v10_L), f"n_links={len(ecap_L)}")

    # ---------------- [P-03/P-04] never_arrived / stuck ----------------
    d1 = sum(r["dep"] for r in ecap_lh)
    a1 = sum(r["arr"] for r in ecap_lh)
    never = d1 - a1
    stuck_max = max((r["stuck"] for r in ecap_lh), default=0)
    gate("P-03", "never_arrived == 0（legHistogram 全天口径）", never == 0,
         f"dep={d1:,} arr={a1:,} 未到达={never} ({100*never/d1 if d1 else float('nan'):.4f}%)")
    gate("P-04", "max stuck_car == 0（legHistogram 逐 bin 峰值）", stuck_max == 0,
         f"max stuck_car={stuck_max}")

    # ---------------- [P-05/P-06] capacity 语义 + v1.0 自校验 ----------------
    print("\n[3] CAPACITY 语义消解 + v1.0 基线自校验")
    cs = A1.resolve_capacity_semantics(v10_L, ecap_L)
    gate("P-05", "CAPACITY 语义消解成功（BASE_CAPACITY ⇒ E-CAP-01 用 cap_mul=1/SCALE）",
         cs["mode"] in ("BASE_CAPACITY", "EFFECTIVE_CAPACITY"),
         f"mode={cs['mode']} n_common={cs['n_common']} 同值={cs['n_identical']} 比值命中={cs['n_ratio_match']}")
    cap_mul_ecap = cs["cap_mul_a1"]
    if cap_mul_ecap is None:
        print("!! CAPACITY 语义 UNRESOLVED ⇒ 不得解释交通效果")
        return 4

    v10_m = A1.face_metrics(v10_L, 1.0)
    gate("P-06", "v1.0 face_metrics 复现基线（82 / 1.1514 km / 2813 / 220 / 7985）",
         v10_m["n_vc_ge_10"] == 82 and abs(v10_m["sat_km"] - 1.1514) < 0.01
         and v10_m["n_vc_ge_05"] == 2813 and v10_m["n_vc_ge_09"] == 220
         and v10_m["n_cong_cut0"] == 7985,
         f"n_ge1={v10_m['n_vc_ge_10']} sat_km={v10_m['sat_km']:.4f} "
         f"n_ge0.5={v10_m['n_vc_ge_05']} n_ge0.9={v10_m['n_vc_ge_09']} n_cong0={v10_m['n_cong_cut0']}")

    # ---------------- [face metrics] v1.0 vs E-CAP-01 ----------------
    print("\n[4] 面指标（it.19）：v1.0 vs E-CAP-01")
    ecap_m = A1.face_metrics(ecap_L, cap_mul_ecap)
    KEY_ROWS = [
        ("n_loaded", "载流链数", "{:,}"),
        ("n_cong_cut0", "拥堵链数 N_cong(cut0, excess>0)", "{:,}"),
        ("n_cong_cut50", "拥堵链数 N_cong(cut50)", "{:,}"),
        ("n_cong_ge1s", "拥堵链数 N_cong(excess≥1.0s)", "{:,}"),
        ("n_vc_ge_05", "n(v/c≥0.5)", "{:,}"),
        ("n_vc_ge_09", "n(v/c≥0.9)", "{:,}"),
        ("n_vc_ge_10", "n(v/c≥1.0)", "{:,}"),
        ("sat_km", "饱和里程 (km)", "{:.4f}"),
        ("share_len_saturated", "饱和里程占比", "{:.6f}"),
        ("max_vc", "max v/c", "{:.6f}"),
        ("peak_agg_vc", "Σ流量/Σ容量", "{:.6f}"),
        ("delay_h", "总延误 (veh·h)", "{:,.1f}"),
        ("total_flow", "Σ HRS8-9avg（全网）", "{:,.0f}"),
    ]
    table = []
    for k, lab, fmt in KEY_ROWS:
        v0, v1 = float(v10_m[k]), float(ecap_m[k])
        rr = (v1 / v0) if v0 else float("nan")
        table.append({"key": k, "label": lab, "v10": v0, "ecap": v1, "ratio_ecap_over_v10": rr})
        print(f"     {lab:<30} v1.0={fmt.format(v0):>14}  E-CAP={fmt.format(v1):>14}  ×{rr:.3f}")

    # Σsim 全网（HRS8-9avg 求和，不含 SCALE）——与 7.9A-1 的 −23.30% 对账
    sum_v10 = v10_m["total_flow"]
    sum_ecap = ecap_m["total_flow"]
    rel = (sum_ecap / sum_v10 - 1.0) if sum_v10 else float("nan")
    NOTES.append(f"全网 ΣHRS8-9avg：v1.0={sum_v10:,.0f} → E-CAP-01={sum_ecap:,.0f}（{rel:+.4%}）；"
                 f"7.9A-1 记录 −23.30% ⇒ 用此核对复现。")

    # ---------------- [P-07/P-08] 冻结护栏复算 ----------------
    gr = {}
    if not args.no_cycle:
        print("\n[5] ★冻结护栏复算（复用 evaluate_demand_response_7_6f_1.eval_run）")
        xw = A1.load_crosswalk_raw()
        ctx = A1.guardrail_ctx(xw)
        RUN_V1 = {"label": "V1", "role": "frozen_v1_0_queue", "lambda": 0.075,
                  "f_demand": 1.180222, "N": A1.N_SIM, "out_dir": A1.V10_OUT,
                  "run_id": A1.V10_RUN, "stage": "7.6H", "desc": "v1.0 冻结（queue, f_cap=1.0）"}
        RUN_ECAP = {"label": "ECAP", "role": "experiment_scale_unified", "lambda": 0.075,
                    "f_demand": 1.180222, "N": A1.N_SIM, "out_dir": ECAP_OUT,
                    "run_id": ECAP_RUN, "stage": "E-CAP-01", "desc": "E-CAP-01（queue, f_cap=0.434977）"}
        gr["V1"] = A1.guardrail_eval(RUN_V1, ctx)
        gr["ECAP"] = A1.guardrail_eval(RUN_ECAP, ctx)

        v1_cycle = float(gr["V1"]["q"]["FROZEN"])
        ec_cycle = float(gr["ECAP"]["q"]["FROZEN"])
        v1_it19 = float(gr["V1"]["q_19"]["FROZEN"])
        ec_it19 = float(gr["ECAP"]["q_19"]["FROZEN"])
        gate("P-07", f"冻结模块复算 v1.0 Sim/Obs == {V10_SIM_OBS_CYCLE}（±1e-9，cycle）",
             abs(v1_cycle - V10_SIM_OBS_CYCLE) < 1e-9,
             f"recomputed={v1_cycle:.13f} n_sections={gr['V1']['n_sections']}")
        gate("P-08a", f"E-CAP-01 Sim/Obs(cycle) == A-1 {A1_SIM_OBS_CYCLE}（±1e-6，逐位复现）",
             abs(ec_cycle - A1_SIM_OBS_CYCLE) < 1e-6,
             f"E-CAP={ec_cycle:.13f}  Δ={ec_cycle - A1_SIM_OBS_CYCLE:+.3e}")
        gate("P-08b", f"E-CAP-01 Sim/Obs(it.19) == A-1 {A1_SIM_OBS_IT19}（±1e-6）",
             abs(ec_it19 - A1_SIM_OBS_IT19) < 1e-6,
             f"E-CAP={ec_it19:.13f}  Δ={ec_it19 - A1_SIM_OBS_IT19:+.3e}")
        NOTES.append(f"护栏断面数：v1.0={gr['V1']['n_sections']} / E-CAP-01={gr['ECAP']['n_sections']} "
                     f"（冻结靶场 576 断面；K 基数并报见 crosswalk）。")
        print(f"     Sim/Obs(cycle):  v1.0={v1_cycle:.7f} → E-CAP-01={ec_cycle:.7f}")
        print(f"     Sim/Obs(it.19):  v1.0={v1_it19:.7f} → E-CAP-01={ec_it19:.7f}")

    # ---------------- 落盘 ----------------
    payload = {
        "experiment": "E-CAP-01",
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "source_note": "E-CAP-01 = 7.9A-1/A1_capf0p435 的干净重跑（模型层 0 差异）",
        "frozen_targets": {
            "v10_sim_obs_cycle": V10_SIM_OBS_CYCLE, "v10_sim_obs_it19": V10_SIM_OBS_IT19,
            "a1_sim_obs_cycle": A1_SIM_OBS_CYCLE, "a1_sim_obs_it19": A1_SIM_OBS_IT19},
        "capacity_semantics": cs,
        "cap_mul_ecap": cap_mul_ecap,
        "leg_hist": {"dep": d1, "arr": a1, "never_arrived": never, "max_stuck": stuck_max},
        "face_metrics_v10": v10_m,
        "face_metrics_ecap": ecap_m,
        "comparison": table,
        "network_flow": {"sum_h89_v10": sum_v10, "sum_h89_ecap": sum_ecap, "rel": rel},
        "guardrail": ({k: {"q_FROZEN": v["q"]["FROZEN"], "q_19_FROZEN": v["q_19"]["FROZEN"],
                           "n_sections": v["n_sections"],
                           "flow_quality": v.get("flow_quality")}
                       for k, v in gr.items()} if gr else None),
        "gates": CHECKS,
        "notes": NOTES,
    }
    (ECAP_AUDIT / "ecap01_postrun_metrics.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    with open(ECAP_AUDIT / "ecap01_postrun_gates.csv", "w", encoding="utf-8-sig", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["check", "name", "pass", "detail"])
        for c in CHECKS:
            w.writerow([c["check"], c["name"], c["pass"], c["detail"]])
    with open(ECAP_AUDIT / "ecap01_postrun_comparison.csv", "w", encoding="utf-8-sig", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["key", "label", "v10", "ecap", "ratio_ecap_over_v10"])
        for r in table:
            w.writerow([r["key"], r["label"], r["v10"], r["ecap"], r["ratio_ecap_over_v10"]])

    n_pass = sum(1 for c in CHECKS if c["pass"] is True)
    n_all = len(CHECKS)
    print("\n" + "=" * 92)
    print(f"  运行后验收门 {n_pass}/{n_all} PASS   耗时 {time.time()-t0:.1f}s")
    fails = [c["check"] for c in CHECKS if not c["pass"]]
    if fails:
        print(f"  ⛔ 失败：{fails} ⇒ E-CAP-01 = INVALID，不得解释交通效果")
    print(f"  产物：{ECAP_AUDIT / 'ecap01_postrun_metrics.json'}")
    print("=" * 92)
    return 0 if not fails else 1


if __name__ == "__main__":
    sys.exit(main())
