#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
compare_congestion_feedback_7_3_1.py — Step 7.3.1 Congestion-feedback Sensitivity 对照。

完全复用 Step 7.1 冻结靶场口径（obs_load / cross_load / metric 直接 import 自
build_calibration_target_7_1.py），对 20 迭代主运行的**每一个迭代** linkstats 计算：

  * 总体指标（r / ρ / Sim/Obs / GEH / RMSE / WMAPE）
  * LTA RoadCat 分层（重点 CATA / SLIP_ROAD）
  * 预注册结构判据：CATA/SLIP_ROAD Sim/Obs 比值 与 r_CATA 的**逐迭代轨迹**
    —— 若比值显著偏离 0.366（7.2.2 冻结的 capacity-only 基线）⇒ 拥堵反馈改变了路径结构
  * 预注册检查点 {1,5,10,20} 迭代 ↔ it.0/4/9/19 的抽取表
  * 嵌套性验证：5 迭代运行的 it.0–it.4 与 20 迭代运行逐位一致（gzip 解压后内容哈希）
  * it.0 与冻结 6.3.3B（7.1 靶场）一致性核对

用法：
    python scripts/od/compare_congestion_feedback_7_3_1.py
"""
from __future__ import annotations

import gzip
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(r"D:\Luan\2026-05\2_Singapore")
sys.path.insert(0, str(ROOT / "scripts" / "od"))
import build_calibration_target_7_1 as b71  # noqa: E402  复用冻结靶场口径

CF = ROOT / "reports" / "od_calibration_7_3_1"
OUT = CF
SCALE = b71.SCALE
WINDOWS = [("07-08", "obs_7_8", "sim_7_8"),
           ("08-09", "obs_8_9", "sim_8_9"),
           ("AM", "obs_am", "sim_am")]
CHECKPOINTS = {1: 0, 5: 4, 10: 9, 20: 19}   # n_iterations -> it.k
CAP_ONLY_BASELINE_RATIO = 0.366             # 7.2.2 冻结的 capacity-only CATA/SLIP 基线


def iter_stats_files(n_iter: int) -> list[Path]:
    d = CF / f"iterations_{n_iter:02d}" / "ITERS"
    files = sorted(d.glob("it.*/cf_it*.*.linkstats.txt.gz"),
                   key=lambda p: int(p.parent.name.split(".")[1]))
    if not files:
        raise FileNotFoundError(f"iterations_{n_iter:02d} 下无 linkstats")
    return files


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


def sections_for_iter(path: Path, cross: pd.DataFrame, obs: pd.DataFrame) -> pd.DataFrame:
    """与 7.1 完全一致的断面聚合（中位数），只是 linkstats 换成指定迭代产物。"""
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
    sec["iteration"] = int(path.parent.name.split(".")[1])
    sec["n_iterations"] = sec["iteration"] + 1
    sec["linkstats_file"] = str(path)
    return sec


def content_hash(p: Path) -> str:
    h = hashlib.sha256()
    with gzip.open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    obs = b71.obs_load(ROOT)
    cross = b71.cross_load(ROOT)
    cross = cross[cross.LinkID.isin(set(obs.LinkID))].copy()

    files = iter_stats_files(20)
    print(f"主运行：{len(files)} 个迭代的 linkstats（it.0–it.{len(files)-1}）")

    allsum, rc_rows, sec_frames = [], [], []
    for p in files:
        sec = sections_for_iter(p, cross, obs)
        sec_frames.append(sec)
        k = sec["iteration"].iloc[0]
        for tw, o, s in WINDOWS:
            allsum.append({"iteration": k, "n_iterations": k + 1, "time_window": tw,
                           **b71.metric(sec[o], sec[s])})
        for tw, o, s in WINDOWS:
            for cat, g in sec.groupby("RoadCat", dropna=False):
                rc_rows.append({"iteration": k, "n_iterations": k + 1,
                                "time_window": tw, "roadcat": str(cat),
                                **b71.metric(g[o], g[s])})
        print(f"  [done] it.{k}")

    sm = pd.DataFrame(allsum)
    rr = pd.DataFrame(rc_rows)
    secs = pd.concat(sec_frames, ignore_index=True)
    sm.to_csv(OUT / "congestion_feedback_iterations_summary.csv",
              index=False, encoding="utf-8-sig")
    rr.to_csv(OUT / "congestion_feedback_by_roadcat.csv",
              index=False, encoding="utf-8-sig")
    secs.to_csv(OUT / "congestion_feedback_sections_all_iterations.csv",
                index=False, encoding="utf-8-sig")

    # --- 逐迭代结构轨迹（预注册判据）------------------------------------
    traj_rows = []
    for k in sorted(rr.iteration.unique()):
        row = {"iteration": k, "n_iterations": k + 1}
        for tw in ["07-08", "08-09", "AM"]:
            s = sm[(sm.iteration == k) & (sm.time_window == tw)]
            row[f"overall_r_{tw}"] = float(s.pearson_r.iloc[0]) if len(s) else np.nan
            row[f"overall_ratio_{tw}"] = float(s.sim_obs_ratio.iloc[0]) if len(s) else np.nan
            cat_r = rr[(rr.iteration == k) & (rr.time_window == tw)]
            cata = cat_r[cat_r.roadcat == "CATA"]
            slip = cat_r[cat_r.roadcat == "SLIP_ROAD"]
            r_cata = float(cata.pearson_r.iloc[0]) if len(cata) else np.nan
            rho_cata = float(cata.spearman_rho.iloc[0]) if len(cata) else np.nan
            ratio_c = float(cata.sim_obs_ratio.iloc[0]) if len(cata) else np.nan
            ratio_s = float(slip.sim_obs_ratio.iloc[0]) if len(slip) else np.nan
            row[f"cata_ratio_{tw}"] = ratio_c
            row[f"slip_ratio_{tw}"] = ratio_s
            row[f"cata_over_slip_{tw}"] = (ratio_c / ratio_s
                                           if ratio_s and np.isfinite(ratio_s) and ratio_s != 0
                                           else np.nan)
            row[f"r_cata_{tw}"] = r_cata
            row[f"rho_cata_{tw}"] = rho_cata
        traj_rows.append(row)
    traj = pd.DataFrame(traj_rows)
    traj.to_csv(OUT / "congestion_feedback_structure_trajectory.csv",
                index=False, encoding="utf-8-sig")

    # --- 预注册检查点表 {1,5,10,20} 迭代 --------------------------------
    cp_rows = []
    for n, k in CHECKPOINTS.items():
        if k > int(sm.iteration.max()):
            continue
        row = {"n_iterations": n, "iteration": k}
        for tw, _, _ in WINDOWS:
            s = sm[(sm.iteration == k) & (sm.time_window == tw)].iloc[0]
            row[f"overall_r_{tw}"] = s.pearson_r
            row[f"overall_ratio_{tw}"] = s.sim_obs_ratio
        for tw in ["07-08", "08-09"]:
            cat_r = rr[(rr.iteration == k) & (rr.time_window == tw)]
            cata = cat_r[cat_r.roadcat == "CATA"].iloc[0]
            slip = cat_r[cat_r.roadcat == "SLIP_ROAD"].iloc[0]
            row[f"cata_ratio_{tw}"] = cata.sim_obs_ratio
            row[f"slip_ratio_{tw}"] = slip.sim_obs_ratio
            row[f"cata_over_slip_{tw}"] = cata.sim_obs_ratio / slip.sim_obs_ratio
            row[f"r_cata_{tw}"] = cata.pearson_r
        cp_rows.append(row)
    cp = pd.DataFrame(cp_rows)
    cp.to_csv(OUT / "congestion_feedback_checkpoints.csv",
              index=False, encoding="utf-8-sig")

    # --- 嵌套性验证：5 迭代运行 vs 20 迭代运行 it.0–it.4 ----------------
    nesting = {"status": "SKIPPED", "detail": []}
    nest_dir = CF / "iterations_05" / "ITERS"
    if nest_dir.exists():
        nest_files = sorted(nest_dir.glob("it.*/cf_it5.*.linkstats.txt.gz"),
                            key=lambda p: int(p.parent.name.split(".")[1]))
        detail = []
        for p in nest_files:
            k = int(p.parent.name.split(".")[1])
            twin = files[k]
            h1, h2 = content_hash(p), content_hash(twin)
            detail.append({"iteration": k, "nesting_run": p.name,
                           "main_run": twin.name,
                           "identical": h1 == h2})
        nesting = {"status": "PASS" if all(d["identical"] for d in detail) else "FAIL",
                   "note": "同 seed + 确定性 ReRoute ⇒ lastIteration 只是截断；"
                           "若 PASS，检查点 {1,5,10,20} 全部由 20 迭代运行覆盖",
                   "detail": detail}
    (OUT / "nesting_check.json").write_text(
        json.dumps(nesting, ensure_ascii=False, indent=2), encoding="utf-8")

    # --- it.0 vs 冻结 6.3.3B 一致性 --------------------------------------
    ref_path = ROOT / "reports/od_calibration_7_1/calibration_target_summary.csv"
    consistency = None
    if ref_path.exists():
        ref = pd.read_csv(ref_path, encoding="utf-8-sig")
        r05 = ref[ref.lambda_per_min == 0.05].set_index("time_window")
        it0 = sm[sm.iteration == 0].set_index("time_window")
        consistency = []
        for tw, _, _ in WINDOWS:
            consistency.append({
                "time_window": tw,
                "it0_ratio": float(it0.loc[tw, "sim_obs_ratio"]),
                "frozen_633b_ratio": float(r05.loc[tw, "sim_obs_ratio"]),
                "it0_r": float(it0.loc[tw, "pearson_r"]),
                "frozen_633b_r": float(r05.loc[tw, "pearson_r"]),
            })
        (OUT / "it0_vs_frozen_633b_consistency.json").write_text(
            json.dumps(consistency, ensure_ascii=False, indent=2), encoding="utf-8")

    definition = {
        "step": "7.3.1", "status": "PASS",
        "experiment": "congestion-feedback sensitivity, lambda=0.05 single-lambda",
        "changed_parameters": ["controller.lastIteration (0 -> 19)"],
        "activated_mechanism": "ReRoute(weight=1.0, 基线已有) + travelTimeCalculator 逐轮拥堵反馈",
        "frozen": ["OD", "lambda=0.05", "population(6.3.3A)", "departure time",
                   "network topology", "permlanes", "capacity(flow=storage=1.0)",
                   "routingRandomness=0.0", "randomSeed=4711",
                   "timeAllocationMutator 不在策略中（出发时刻不漂移）"],
        "checkpoints_iterations_to_its": CHECKPOINTS,
        "nested_design": "同 seed + 确定性 ReRoute ⇒ lastIteration 仅截断；"
                         "5 迭代运行做嵌套性验证（nesting_check.json）",
        "capacity_only_baseline_cata_over_slip": CAP_ONLY_BASELINE_RATIO,
        "decision_rule": "CATA/SLIP 比值显著偏离 0.366 且 r_CATA 改善 ⇒ 拥堵反馈改变路径结构 "
                         "-> 7.3.2 route-choice 参数；否则 MATSim 迭代配置本身需先处理",
        "scale": SCALE, "lambda_selected": False,
    }
    (OUT / "congestion_feedback_definition.json").write_text(
        json.dumps(definition, ensure_ascii=False, indent=2), encoding="utf-8")

    print("\n=== 逐迭代总体 r 与结构轨迹（07-08 / 08-09）===")
    show = traj[["n_iterations", "overall_r_07-08", "overall_r_08-09",
                 "cata_ratio_07-08", "cata_ratio_08-09",
                 "slip_ratio_07-08", "slip_ratio_08-09",
                 "cata_over_slip_07-08", "cata_over_slip_08-09",
                 "r_cata_07-08", "r_cata_08-09"]]
    print(show.to_string(index=False, float_format=lambda v: f"{v:.4f}"))
    print(f"\ncapacity-only 基线 CATA/SLIP = {CAP_ONLY_BASELINE_RATIO}（7.2.2 冻结）")
    print(f"\n=== 嵌套性验证：{nesting['status']} ===")
    print(f"\nOutput: {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
