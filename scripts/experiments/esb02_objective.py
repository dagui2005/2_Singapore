#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
esb02_objective.py — E-SB-02 联合目标评分（复用 E-SB-01 的评价机制，同源口径）
=============================================================================
对 v1.0 / E-CAP-01 / SB-A1..A4 / SB-A5 / SB-A5ind 统一出：
  TrafficFlow：Sim/Obs(cycle it.10–19) · Sim/Obs(it.19) · GEH/Pearson/WMAPE
  SpeedBand  ：bias/MAE/RMSE/r(Spearman) + shuffle 负例 + band 精确/±1
用法：python scripts/experiments/esb02_objective.py [--runs SB-A5 SB-A5ind]
"""
from __future__ import annotations
import argparse, json, sys
from pathlib import Path

import pandas as pd

ROOT = Path(r"D:\Luan\2026-05\2_Singapore")
sys.path.insert(0, str(ROOT / "scripts" / "experiments"))
sys.path.insert(0, str(ROOT / "scripts" / "od"))

import esb01_objective as O  # noqa: E402

E1 = ROOT / "experiments" / "E-SB-01_speedband_fit"
E2 = ROOT / "experiments" / "E-SB-02_night_freeflow"
AUDIT = E2 / "audit"
F_DEMAND = 1.180222


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", nargs="*", default=["SB-A5", "SB-A5ind"])
    a = ap.parse_args()
    AUDIT.mkdir(parents=True, exist_ok=True)

    A1 = O.A1
    A1.OUT = AUDIT
    A1.CYCLE_DIR = AUDIT / "_cycle_linkstats"
    A1.GR_DIR = AUDIT / "_guardrail_cache"
    A1.CYCLE_DIR.mkdir(parents=True, exist_ok=True)
    A1.GR_DIR.mkdir(parents=True, exist_ok=True)

    print("=" * 92)
    print("E-SB-02 联合目标评分（TrafficFlow 冻结口径 + SpeedBand 拟合）")
    print("=" * 92)

    xw = A1.load_crosswalk_raw()
    ctx = A1.guardrail_ctx(xw)
    obs = O._obs_speed_table()
    print(f"[obs] SpeedBand 覆盖 MATSim 链路 {len(obs):,}")

    todo = {
        "v1.0": (ROOT / "matsim_final_7_6h" / "outputs" / "W01_rc_min", "W01_rc_min", F_DEMAND, "冻结 v1.0"),
        "E-CAP-01": (ROOT / "experiments" / "E-CAP-01_scale_capacity" / "outputs" / "E-CAP-01",
                     "E-CAP-01", F_DEMAND, "E-CAP-01 (f_cap=0.434977)"),
    }
    for arm in ["SB-A1", "SB-A2", "SB-A3", "SB-A3n", "SB-A4"]:
        todo[arm] = (E1 / "outputs" / arm, arm, F_DEMAND, f"E-SB-01 {arm}")
    for arm in a.runs:
        todo[arm] = (E2 / "outputs" / arm, arm, F_DEMAND, f"E-SB-02 {arm}")

    rows = []
    for label, (out_dir, run_id, f_demand, desc) in todo.items():
        flow = O._flow_fit(label, out_dir, run_id, f_demand, ctx)
        speed = O._speed_fit(out_dir, run_id, obs)
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
            print(f"   F_flow  Sim/Obs(cycle)={flow['sim_obs_cycle']:.7f}  it.19={flow['sim_obs_it19']:.7f}")
        if speed:
            print(f"   F_speed n={speed['n']:,} bias={speed['bias_kmh']:+.2f} RMSE={speed['RMSE_kmh']:.2f} "
                  f"r={speed['pearson_r']:.3f} band_exact={speed['band_exact_pct']:.1f}%")

    df = pd.DataFrame(rows)
    df.to_csv(AUDIT / "esb02_joint_scorecard.csv", index=False, encoding="utf-8-sig")
    with open(AUDIT / "esb02_joint_scorecard.json", "w", encoding="utf-8") as fh:
        json.dump(rows, fh, ensure_ascii=False, indent=2, default=str)
    print(f"\n落盘：{AUDIT / 'esb02_joint_scorecard.csv'}（{len(rows)} 行）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
