#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
compare_capacity_sweep_7_2_2.py — Step 7.2.2 Capacity-only Sensitivity 对照。

完全复用 Step 7.1 冻结靶场口径（obs_load / cross_load / metric 直接 import 自
build_calibration_target_7_1.py）：
    观测  = TrafficFlow 工作日逐日中位 → LinkID×Hour 中位
    仿真  = 各 capacity_factor 目录 it.0 linkstats HRS7-8avg/HRS8-9avg × scale 2.29897
    断面  = 6.3.2 tight crosswalk，断面内匹配边取中位数
    分层  = LTA RoadCat

对每个 f ∈ {0.50,0.75,1.00,1.25,1.50} 输出总体 + RoadCat 指标；另附：
  * f=1.00 与冻结 6.3.3B（7.1 靶场）的一致性核对（同参数应复现 0.744/0.889）
  * CATA↑ / SLIP_ROAD↓ 的流量转移判据（各档 vs f=1.00）

用法：
    python scripts/od/compare_capacity_sweep_7_2_2.py
"""
from __future__ import annotations

import gzip
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(r"D:\Luan\2026-05\2_Singapore")
sys.path.insert(0, str(ROOT / "scripts" / "od"))
import build_calibration_target_7_1 as b71  # noqa: E402  复用冻结靶场口径

SWEEP = ROOT / "reports" / "od_calibration_7_2_2"
OUT = SWEEP
FACTORS = [0.50, 0.75, 1.00, 1.25, 1.50]
SCALE = b71.SCALE
WINDOWS = [("07-08", "obs_7_8", "sim_7_8"),
           ("08-09", "obs_8_9", "sim_8_9"),
           ("AM", "obs_am", "sim_am")]


def find_stats_for_factor(tag: str) -> Path:
    d = SWEEP / f"capacity_factor_{tag}"
    files = [p for p in d.rglob("*.linkstats.txt.gz")
             if "it.0" in str(p).lower() and "_smoke" not in str(p)]
    if not files:
        raise FileNotFoundError(f"capacity_factor_{tag} 下找不到 it.0 linkstats")
    return sorted(files, key=lambda p: (len(str(p)), str(p)))[0]


def sim_load_file(p: Path) -> pd.DataFrame:
    with gzip.open(p, "rt", encoding="latin-1", errors="replace") as f:
        header = f.readline().rstrip("\n").split("\t")
    wanted = ["LINK", "HRS7-8avg", "HRS8-9avg"]
    pos = {x: header.index(x) for x in wanted if x in header}
    if set(pos) != set(wanted):
        raise ValueError(f"{p}: linkstats 缺字段 {sorted(set(wanted)-set(pos))}")
    use = sorted(pos.values())
    d = pd.read_csv(p, sep="\t", usecols=use, compression="gzip",
                    encoding="latin-1", low_memory=False)
    ren = {d.columns[use.index(i)]: c for c, i in pos.items()}
    d = d.rename(columns=ren)
    d["LINK"] = d.LINK.astype(str)
    for c in wanted[1:]:
        d[c] = pd.to_numeric(d[c], errors="coerce").fillna(0.0)
    return d


def sections_for_factor(tag: str, cross: pd.DataFrame, obs: pd.DataFrame) -> pd.DataFrame:
    """与 7.1 完全一致的断面聚合（中位数），只是 linkstats 换成本档产物。"""
    path = find_stats_for_factor(tag)
    sim = sim_load_file(path)
    x = cross[["LinkID", "matsim_link_id", "name_match", "RoadCat"]].drop_duplicates()
    x = x.merge(sim.rename(columns={"LINK": "matsim_link_id"}),
                on="matsim_link_id", how="left").fillna(
        {"HRS7-8avg": 0, "HRS8-9avg": 0})
    sec = x.groupby("LinkID", as_index=False).agg(
        matched_matsim_edges=("matsim_link_id", "nunique"),
        sim_7_8_raw=("HRS7-8avg", "median"),
        sim_8_9_raw=("HRS8-9avg", "median"),
        name_match_rate=("name_match", "mean"),
        RoadCat=("RoadCat", "first"))
    sec = sec.merge(obs, on="LinkID", how="inner")
    sec["sim_7_8"] = sec.sim_7_8_raw * SCALE
    sec["sim_8_9"] = sec.sim_8_9_raw * SCALE
    sec["sim_am"] = sec.sim_7_8 + sec.sim_8_9
    sec["capacity_factor"] = float(tag.replace("p", "."))
    sec["linkstats_file"] = str(path)
    return sec


def main() -> int:
    obs = b71.obs_load(ROOT)
    cross = b71.cross_load(ROOT)
    cross = cross[cross.LinkID.isin(set(obs.LinkID))].copy()
    if cross.empty:
        raise ValueError("crosswalk 与观测 LinkID 无交集")

    allsum, rc_rows, sec_frames = [], [], []
    for f in FACTORS:
        tag = b71_tag = f"{f:.2f}".replace(".", "p")
        sec = sections_for_factor(tag, cross, obs)
        sec_frames.append(sec)
        for tw, o, s in WINDOWS:
            allsum.append({"capacity_factor": f, "time_window": tw,
                           **b71.metric(sec[o], sec[s])})
        for tw, o, s in WINDOWS:
            for cat, g in sec.groupby("RoadCat", dropna=False):
                rc_rows.append({"capacity_factor": f, "time_window": tw,
                                "roadcat": str(cat), **b71.metric(g[o], g[s])})
        print(f"[done] f={f:.2f}  sections={len(sec)}")

    sm = pd.DataFrame(allsum)
    rr = pd.DataFrame(rc_rows)
    secs = pd.concat(sec_frames, ignore_index=True)

    sm.to_csv(OUT / "capacity_sensitivity_summary.csv", index=False, encoding="utf-8-sig")
    rr.to_csv(OUT / "capacity_sensitivity_by_roadcat.csv", index=False, encoding="utf-8-sig")
    secs.to_csv(OUT / "capacity_sensitivity_sections.csv", index=False, encoding="utf-8-sig")

    # --- CATA / SLIP_ROAD 响应透视（核心判据） --------------------------
    piv = rr.pivot_table(index="roadcat", columns=["capacity_factor", "time_window"],
                         values="sim_obs_ratio", dropna=False)
    piv.to_csv(OUT / "capacity_sensitivity_ratio_pivot.csv", encoding="utf-8-sig")

    # --- f=1.00 vs 冻结 6.3.3B（7.1 靶场）一致性核对 --------------------
    ref_path = ROOT / "reports/od_calibration_7_1/calibration_target_summary.csv"
    consistency = None
    if ref_path.exists():
        ref = pd.read_csv(ref_path, encoding="utf-8-sig")
        r05 = ref[ref.lambda_per_min == 0.05].set_index("time_window")
        f100 = sm[sm.capacity_factor == 1.00].set_index("time_window")
        consistency = []
        for tw, _, _ in WINDOWS:
            consistency.append({
                "time_window": tw,
                "f1p00_ratio": float(f100.loc[tw, "sim_obs_ratio"]),
                "frozen_633b_ratio": float(r05.loc[tw, "sim_obs_ratio"]),
                "f1p00_r": float(f100.loc[tw, "pearson_r"]),
                "frozen_633b_r": float(r05.loc[tw, "pearson_r"]),
            })
        (OUT / "f1p00_vs_frozen_633b_consistency.json").write_text(
            json.dumps(consistency, ensure_ascii=False, indent=2), encoding="utf-8")

    definition = {
        "step": "7.2.2", "status": "PASS",
        "experiment": "capacity-only sensitivity, lambda=0.05 single-lambda",
        "changed_parameters": ["qsim.flowCapacityFactor", "qsim.storageCapacityFactor"],
        "storage_equals_flow_reason": "MATSim 2026.0 GlobalConfigGroup.checkConsistency enforces "
                                      "storage==flow (relativeTolerance hard-coded 0, @StringSetter commented out)",
        "factors": FACTORS, "scale": SCALE,
        "frozen": ["OD", "lambda", "population(6.3.3A departure profile)",
                   "departure time", "network topology", "permlanes",
                   "route choice(SpeedyALT, single iteration)", "randomSeed=4711"],
        "observed_source": str(b71.FLOW), "crosswalk_source": str(b71.CROSS),
        "lambda_selected": False, "route_choice_changed": False,
    }
    (OUT / "capacity_sensitivity_definition.json").write_text(
        json.dumps(definition, ensure_ascii=False, indent=2), encoding="utf-8")

    print("\n=== 总体（capacity_factor × time_window）===")
    cols = ["capacity_factor", "time_window", "n", "pearson_r", "spearman_rho",
            "sim_obs_ratio", "geh_lt_5_rate", "rmse", "mae"]
    print(sm[cols].to_string(index=False))
    print("\n=== RoadCat Sim/Obs（07-08 / 08-09）===")
    sub = rr[rr.time_window.isin(["07-08", "08-09"])][
        ["capacity_factor", "time_window", "roadcat", "sim_obs_ratio", "pearson_r"]]
    print(sub.to_string(index=False))
    if consistency:
        print("\n=== f=1.00 vs 冻结 6.3.3B 一致性 ===")
        print(pd.DataFrame(consistency).to_string(index=False))
    print(f"\nOutput: {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
