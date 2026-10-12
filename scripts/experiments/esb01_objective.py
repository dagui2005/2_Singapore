#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""
esb01_objective.py — E-SB-01 联合目标评分器（只读 · 零仿真）
==============================================================
对任意 run 目录同时给出**两把尺子**：

  [F_flow]  TrafficFlow 对账（冻结口径，复用 audit_sampling_capacity_7_9a1）
            Sim/Obs(cycle it.10-19) · Sim/Obs(it.19) · GEH/Pearson/WMAPE · 面指标
  [F_speed] SpeedBand 拟合（与 7 诊断同源）
            bias / MAE / RMSE / Pearson r / Spearman / band 精确·±1·band bias
            主域 = 08-09 有车链（obs 覆盖 ∩ in-network ∩ HRS8-9avg>0）

联合判据（预注册）
------------------
  改善 = ΔRMSE_speed < 0 **且** F_flow ∈ [0.95, 1.05]（不牺牲流量对账）。
  负例臂（SB-A3n）若与正向臂同等改善 ⇒ 判为「非空间效应」。
  ⛔ 不以「图更好看」为目的调参；每次只评已完成的 run。

用法
----
    python scripts/experiments/esb01_objective.py                      # 评 v1.0 + E-CAP-01 + 已有 sbs 臂
    python scripts/experiments/esb01_objective.py --runs SB-A1         # 指定臂
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(r"D:\Luan\2026-05\2_Singapore")
sys.path.insert(0, str(ROOT / "scripts" / "od"))
sys.path.insert(0, str(ROOT / "scripts" / "experiments"))

import audit_sampling_capacity_7_9a1 as A1              # noqa: E402  冻结评价器
import build_speedband_fit_diagnostic as SBD            # noqa: E402  SpeedBand 拟合（同源）

EXP_ROOT = ROOT / "experiments" / "E-SB-01_speedband_fit"
AUDIT_DIR = EXP_ROOT / "audit"

KNOWN_RUNS = {
    "v1.0": (ROOT / "matsim_final_7_6h" / "outputs" / "W01_rc_min", "W01_rc_min", 1.180222, "冻结 v1.0（queue, f_cap=1.0）"),
    "E-CAP-01": (ROOT / "experiments" / "E-CAP-01_scale_capacity" / "outputs" / "E-CAP-01", "E-CAP-01", 1.180222, "E-CAP-01（queue, f_cap=0.434977）"),
}
ARM_RUNS = ["SB-A1", "SB-A2", "SB-A3", "SB-A3n", "SB-A4"]


def _obs_speed_table() -> pd.DataFrame:
    return SBD.build_obs()


def _speed_fit(out_dir: Path, run_id: str, obs: pd.DataFrame) -> dict | None:
    ls = out_dir / "ITERS" / "it.19" / f"{run_id}.19.linkstats.txt.gz"
    if not ls.exists():
        return None
    L = SBD.load_linkstats(ls)
    d = obs.merge(L, left_on="matsim_link", right_on="LINK", how="inner")
    d["sim_W89"] = SBD.window_sim_speed(d, ["TRAVELTIME8-9avg"])
    d["sim_W710"] = SBD.window_sim_speed(d, ["TRAVELTIME7-8avg", "TRAVELTIME8-9avg", "TRAVELTIME9-10avg"])
    d["ff_speed_kmh"] = d.FREESPEED.to_numpy(float) * 3.6
    v = d[(d["HRS8-9avg"].fillna(0) > 0) & d["sim_W89"].notna()].copy()
    if v.empty:
        return None
    st = SBD.metrics(v, "sim_W89")
    st["n_obs_in_net"] = int(len(d))
    st["flow_cov_pct"] = float((d["HRS8-9avg"].fillna(0) > 0).mean() * 100)
    # 按观测档（关键诊断）
    by_band = []
    for ob, g in v.groupby("obs_band"):
        s = g.sim_W89.to_numpy(float)
        by_band.append({"obs_band": int(ob), "n": int(len(g)), "sim_mean_kmh": float(np.mean(s)),
                        "sim_mean_band": float(SBD.band_of_speed(s).mean())})
    st["by_obs_band"] = by_band
    return st


def _flow_fit(label: str, out_dir: Path, run_id: str, f_demand: float, ctx) -> dict | None:
    ls19 = out_dir / "ITERS" / "it.19" / f"{run_id}.19.linkstats.txt.gz"
    if not ls19.exists():
        return None
    run = {"label": label, "role": "esb01_arm", "lambda": 0.075, "f_demand": f_demand,
           "N": A1.N_SIM, "out_dir": out_dir, "run_id": run_id, "stage": "E-SB-01",
           "desc": label}
    try:
        g = A1.guardrail_eval(run, ctx)
        return {"sim_obs_cycle": float(g["q"]["FROZEN"]),
                "sim_obs_it19": float(g["q_19"]["FROZEN"]),
                "n_sections": int(g["n_sections"]),
                "n_zero_sim": int(g.get("n_zero_sim", -1)),
                "flow_quality": g.get("flow_quality")}
    except Exception as exc:
        return {"error": str(exc)}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", nargs="*", default=None)
    a = ap.parse_args()

    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    # ★把冻结评价器的写目录重定向到本实验 audit/，绝不落 A-1 / sampling_capacity 目录
    A1.OUT = AUDIT_DIR
    A1.CYCLE_DIR = AUDIT_DIR / "_cycle_linkstats"
    A1.GR_DIR = AUDIT_DIR / "_guardrail_cache"
    A1.CYCLE_DIR.mkdir(parents=True, exist_ok=True)
    A1.GR_DIR.mkdir(parents=True, exist_ok=True)

    print("=" * 92)
    print("E-SB-01 联合目标评分（TrafficFlow 冻结口径 + SpeedBand 拟合）")
    print("=" * 92)

    xw = A1.load_crosswalk_raw()
    ctx = A1.guardrail_ctx(xw)
    obs = _obs_speed_table()
    print(f"[obs] SpeedBand 覆盖 MATSim 链路 {len(obs):,}")

    todo = dict(KNOWN_RUNS)
    for arm in (a.runs or ARM_RUNS):
        todo[arm] = (EXP_ROOT / "outputs" / arm, arm, 1.180222, f"{arm}")

    rows = []
    for label, (out_dir, run_id, f_demand, desc) in todo.items():
        flow = _flow_fit(label, out_dir, run_id, f_demand, ctx)
        speed = _speed_fit(out_dir, run_id, obs)
        if flow is None and speed is None:
            print(f"\n[{label}] 尚无 it.19 linkstats ⇒ 跳过")
            continue
        row = {"run": label, "desc": desc}
        if flow and "sim_obs_cycle" in flow:
            row.update({"sim_obs_cycle": flow["sim_obs_cycle"], "sim_obs_it19": flow["sim_obs_it19"],
                        "n_sections": flow["n_sections"], "n_zero_sim": flow["n_zero_sim"],
                        "flow_quality": flow.get("flow_quality")})
        if speed:
            row.update({k: speed[k] for k in
                        ("n", "obs_mean_kmh", "sim_mean_kmh", "bias_kmh", "MAE_kmh", "RMSE_kmh",
                         "pearson_r", "spearman_rho", "shuffle_r_negctrl", "band_exact_pct",
                         "band_within1_pct", "band_bias", "flow_cov_pct")})
            row["by_obs_band"] = json.dumps(speed.get("by_obs_band", []), ensure_ascii=False)
        rows.append(row)
        print(f"\n[{label}]")
        if flow and "sim_obs_cycle" in flow:
            print(f"   F_flow  Sim/Obs(cycle)={flow['sim_obs_cycle']:.7f}  it.19={flow['sim_obs_it19']:.7f}  "
                  f"sections={flow['n_sections']} zero_sim={flow['n_zero_sim']}")
        if speed:
            print(f"   F_speed n={speed['n']:,} bias={speed['bias_kmh']:+.2f} MAE={speed['MAE_kmh']:.2f} "
                  f"RMSE={speed['RMSE_kmh']:.2f} r={speed['pearson_r']:.3f} "
                  f"band_exact={speed['band_exact_pct']:.1f}% band_bias={speed['band_bias']:+.2f}")

    df = pd.DataFrame(rows)
    df.to_csv(AUDIT_DIR / "esb01_joint_scorecard.csv", index=False, encoding="utf-8-sig")
    with open(AUDIT_DIR / "esb01_joint_scorecard.json", "w", encoding="utf-8") as fh:
        json.dump(rows, fh, ensure_ascii=False, indent=2, default=str)
    print(f"\n落盘：{AUDIT_DIR / 'esb01_joint_scorecard.csv'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
