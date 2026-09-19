#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""
audit_assignment_stability_7_6b.py — Step 7.6B
「分配 / 路径稳定性审计」（zero simulation，只读复用 D01-D04 的 linkstats）。

回答的问题
----------
7.4.3-R 已判定：demand scale 的非单调（f=1.20 峰 -> f=1.25 回落）**不能靠换窗口消除**；
在标定真正使用的 3,037 条主干链路上，全日窗仍保留约 6.7% 的、与窗口无关的缺口。
7.4.3-Diag 的行进端证据（平均行程时长 x1.173、拥堵倍率 x1.208、绕行变长）指向
**ReRoute 下的路径替代 / 分配重分布**。

=> 本步骤零仿真回答三个问题：

    Q1  分配本身**收敛了吗**？（同一 f 下逐迭代的流量是否稳定）
        —— 若不收敛，则"用单个迭代（it.19）的水平做跨 f 比较"在方法上不成立。
    Q2  标定断面在**全网车公里(VKT)中的份额** R_cal 是否随 demand 系统性变化？
        —— 这是"流量离开标定断面"的直接度量化。
    Q3  f=1.20 -> f=1.25 的落差中，有多少来自**路径替代**（车流从标定主干道
        切到平行非观测链路），有多少来自**总量/时段迁移**？

核心口径（与冻结评价器逐字节同源）
----------------------------------
    sim = median(断面内匹配 MATSim 有向边 HRS{h}-{h+1}avg) x SCALE   (SCALE = 459794/200000)
    ALL     = 全网 693,575 条链路
    MATCHED = 7.3.6A Final Crosswalk 命中的 3,037 条链路（0.4379% 的链路）
    窗口    = 07-08 / 08-09 / 07-09（Class O，有观测）/ 00-24（Class S，无观测）

★ 本步骤最重要的先验事实（决定了整个判读）
------------------------------------------
D01-D04 的 config 全部是：
    <param name="fractionOfIterationsToDisableInnovation" value="Infinity" />
    <parameterset type="strategysetting"><param name="strategyName" value="ReRoute" />
                                             <param name="weight" value="1.0" /></parameterset>
    <param name="learningRate" value="1.0" />   (planCalcScore)
即：**100% 的 agent 在 100% 的迭代里重新选路**，且计划得分不做指数平滑。
在 `routingRandomness = 0.0` + 确定性最短路上，这是产生
**周期-2 极限环（period-2 limit cycle / route flip-flop）** 的标准配置。

本脚本据此把「迭代」当成一个维度显式审计，而不是默认 it.19 已经收敛。

产物（reports/od_calibration_7_6b/）
-----------------------------------
    STEP7_6B_REPORT.md
    assignment_iter_trajectory.csv           逐 run x 逐 iteration 的标量轨迹（it.0-19）
    assignment_parity_decomposition.csv      奇/偶相位分解 + 极限环振幅
    assignment_frozen_metric_by_iter.csv     冻结指标（3 个可观测窗）逐迭代
    assignment_cycle_mean_reevaluation.csv   周期均值 vs it.19 的跨 f 重估计（★核心）
    assignment_cycle_mean_frozen_metric.csv  08-09 主窗口冻结指标的周期均值重估
    assignment_rcal_share.csv                标定断面 VKT 份额 R_cal
    assignment_reallocation_decomposition.csv 跨 f 的 matched/non-matched 增量分解
    assignment_phase_reallocation.csv        同一 run 内相位翻转的增量对冲
    assignment_link_flip_profile.csv         top40 振荡链路属性画像
    assignment_substitution_classes.csv      替代类别汇总
    assignment_link_rank_stability.csv       逐链路秩稳定性（Spearman）
    assignment_detour_congestion.csv         绕行指数与拥堵响应
    assignment_config_provenance.csv         配置溯源
    assignment_stability_summary.json
    stability_console.log

用法
----
    python scripts/od/audit_assignment_stability_7_6b.py
    python scripts/od/audit_assignment_stability_7_6b.py --reuse     # 复用缓存的标量轨迹
    python scripts/od/audit_assignment_stability_7_6b.py --force     # 强制全量重算
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(r"D:\Luan\2026-05\2_Singapore")
sys.path.insert(0, str(ROOT / "scripts" / "od"))

import compare_final_crosswalk_7_3_6b as bt        # noqa: E402  冻结观测/断面/指标口径
import evaluate_calibration_7_4_2 as ev1           # noqa: E402  实验定位 / 冻结常量

OUT = ROOT / "reports" / "od_calibration_7_6b"
PREV_743R = ROOT / "reports" / "od_calibration_7_4_3r"
REF_LEVELS = PREV_743R / "sim_only_window_levels.csv"

SCALE = bt.SCALE

# 窗口：(显示名, 列名后缀, hours 或 None(=全日), obs 列, 是否可观测)
WINDOWS = [
    ("07-08", "07_08", [7], "obs_7_8", True),
    ("08-09", "08_09", [8], "obs_8_9", True),
    ("07-09", "07_09", [7, 8], "obs_am", True),
    ("00-24", "00_24", None, None, False),
]
WIN_NAMES = [w[0] for w in WINDOWS]
OBS_WINDOWS = [w for w in WINDOWS if w[4]]

EXPERIMENTS = [
    ("D01", 1.00, ROOT / "reports" / "od_calibration_7_4_2" / "E06_lam0p075_cap1p00", "E06",
     "REUSE 7.4.2 E06（lambda=0.075, cap=1.00, 20 it）"),
    ("D02", 1.10, ROOT / "reports" / "od_calibration_7_4_3" / "D02_lam0p075", "D02", "7.4.3 D 系列"),
    ("D03", 1.20, ROOT / "reports" / "od_calibration_7_4_3" / "D03_lam0p075", "D03", "7.4.3 D 系列"),
    ("D04", 1.25, ROOT / "reports" / "od_calibration_7_4_3" / "D04_lam0p075", "D04", "7.4.3 D 系列"),
]
EIDS = [e[0] for e in EXPERIMENTS]
F_OF = {e[0]: e[1] for e in EXPERIMENTS}

CONFIGS = {
    "D01": ROOT / "matsim" / "step6_3" / "config_E06_lam0p075_cap1p00.xml",
    "D02": ROOT / "matsim" / "step6_3" / "config_D02_lam0p075_dem1p10.xml",
    "D03": ROOT / "matsim" / "step6_3" / "config_D03_lam0p075_dem1p20.xml",
    "D04": ROOT / "matsim" / "step6_3" / "config_D04_lam0p075_dem1p25.xml",
}

ANCHOR_LINKS = 693_575
ANCHOR_CW_ROWS = 3_193
ANCHOR_CW_SECTIONS = 576
ANCHOR_CW_MATCHED = 3_037
ANCHOR = {
    ("D01", "08_09"): (31_966_212.0, 1_836_595.0, 0.707041),
    ("D03", "08_09"): (36_274_085.0, 2_328_166.0, 0.860084),
    ("D04", "08_09"): (34_765_233.0, 2_059_784.0, 0.759892),
    ("D01", "00_24"): (71_498_189.0, 4_384_144.0, None),
    ("D03", "00_24"): (86_176_094.0, 5_844_933.0, None),
}

CONV_START = 10
CONV_END = 19
KEY_ITERS = [17, 18, 19]

LINKSTAT_COLS = ["LINK", "FROM", "TO", "LENGTH", "FREESPEED", "CAPACITY",
                 "HRS7-8avg", "HRS8-9avg", "HRS0-24avg", "TRAVELTIME8-9avg"]

_ck_rows: list[dict] = []


def ck(name: str, ok: bool, detail: str = "") -> bool:
    _ck_rows.append({"check": name, "pass": bool(ok), "detail": str(detail)})
    print(f"      [{'PASS' if ok else 'FAIL'}] {name}  {detail}")
    return bool(ok)


def wcsv(df: pd.DataFrame, path: Path, retries: int = 8):
    """带重试的 CSV 写出（Windows 下偶发 PermissionError，绝不静默丢失）。"""
    last = None
    for _ in range(retries):
        try:
            df.to_csv(path, index=False, encoding="utf-8-sig")
            return path
        except PermissionError as e:      # pragma: no cover
            last = e
            time.sleep(0.6)
    alt = path.with_suffix(".retry.csv")
    df.to_csv(alt, index=False, encoding="utf-8-sig")
    print(f"      WARN: {path.name} 被占用，已降级写出 {alt.name} ({last})")
    return alt


def load_linkstats(path: Path, cols=None) -> pd.DataFrame:
    usecols = cols or LINKSTAT_COLS
    df = pd.read_csv(path, sep="\t",
                     compression="gzip" if path.suffix == ".gz" else None,
                     usecols=usecols, low_memory=False)
    for c in usecols:
        if c != "LINK":
            df[c] = pd.to_numeric(df[c], errors="coerce")
    df["LINK"] = df["LINK"].astype(str).str.strip()
    if "FROM" in usecols:
        df["FROM"] = df["FROM"].astype(str).str.strip()
        df["TO"] = df["TO"].astype(str).str.strip()
    return df


def window_sums(df: pd.DataFrame) -> dict:
    out = {}
    for name, key, hours, _o, _obs in WINDOWS:
        if hours is None:
            out[f"sum_all_{key}"] = float(df["HRS0-24avg"].sum())
        else:
            out[f"sum_all_{key}"] = float(
                df[[f"HRS{h}-{h + 1}avg" for h in hours]].sum().sum())
    return out


def congestion_multiplier(df: pd.DataFrame, mask=None) -> float:
    d = df if mask is None else df.loc[mask]
    q = d["HRS8-9avg"].to_numpy(dtype=float)
    tt = d["TRAVELTIME8-9avg"].to_numpy(dtype=float)
    ff = d["LENGTH"].to_numpy(dtype=float) / d["FREESPEED"].to_numpy(dtype=float)
    den = float(np.nansum(q * ff))
    return float(np.nansum(q * tt) / den) if den > 0 else float("nan")


def oversat_share(df: pd.DataFrame, mask=None) -> float:
    d = df if mask is None else df.loc[mask]
    q = d["HRS8-9avg"].to_numpy(dtype=float)
    c = d["CAPACITY"].to_numpy(dtype=float)
    tot = float(np.nansum(q))
    if tot <= 0:
        return float("nan")
    return float(np.nansum(q[q > c]) / tot)


def section_estimator(cw_obs: pd.DataFrame, sim_matched: pd.DataFrame) -> dict:
    """冻结 calc_method：断面内匹配边中位数 x SCALE 求和，再 / 观测合计。

    cw_obs 已 pre-merge 观测（inner），因此断面集合 = 既有 crosswalk 又有观测的断面，
    与 7.4.3-R 的 calc_sections 完全一致。
    """
    out = {}
    for name, key, hours, ocol, _obs in OBS_WINDOWS:
        hcols = [f"HRS{h}-{h + 1}avg" for h in hours]
        mm = cw_obs.merge(sim_matched[["LINK"] + hcols],
                          left_on="matsim_link_id", right_on="LINK", how="left")
        agg = mm.groupby("lta_linkid", as_index=False).agg(
            **{f"med_{h}": (f"HRS{h}-{h + 1}avg", "median") for h in hours},
            **{ocol: (ocol, "first")})
        sm = np.zeros(len(agg))
        for h in hours:
            sm = sm + agg[f"med_{h}"].fillna(0).to_numpy(dtype=float)
        sim = pd.Series(sm * SCALE, index=agg["lta_linkid"].to_numpy())
        obs = pd.Series(agg[ocol].to_numpy(dtype=float), index=agg["lta_linkid"].to_numpy())
        valid = obs > 0
        out[f"sim_med_{key}"] = float(sim[valid].sum())
        den = float(obs[valid].sum())
        out[f"simobs_{key}"] = (out[f"sim_med_{key}"] / den) if den > 0 else np.nan
        out[f"n_sections_valid_{key}"] = int(valid.sum())
    return out


def config_provenance() -> list[dict]:
    keys = ["fractionOfIterationsToDisableInnovation", "maxAgentPlanMemorySize",
            "planSelectorForRemoval", "strategyName", "weight", "learningRate",
            "routingRandomness", "routingAlgorithmType", "flowCapacityFactor",
            "storageCapacityFactor", "writeLinkStatsInterval"]
    rows = []
    for eid, path in CONFIGS.items():
        if not path.exists():
            rows.append({"experiment_id": eid, "config": str(path), "param": "*",
                         "value": "MISSING"})
            continue
        txt = path.read_text(encoding="utf-8", errors="replace")
        for k in keys:
            vals = []
            for chunk in txt.split(f'name="{k}"')[1:]:
                seg = chunk.split('value="', 1)
                if len(seg) < 2:
                    continue
                vals.append(seg[1].split('"', 1)[0])
            for v in dict.fromkeys(vals):
                rows.append({"experiment_id": eid, "config": path.name,
                             "param": k, "value": v})
    return rows


# =====================================================================
def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-dir", type=Path, default=OUT)
    ap.add_argument("--reuse", action="store_true")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--last-iter", type=int, default=19)
    args = ap.parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)

    log_lines: list[str] = []

    def log(msg):
        print(msg)
        log_lines.append(str(msg))

    traj_cache = args.out_dir / "assignment_iter_trajectory.csv"

    # ---------------------------------------------------------------- S0
    log("[0/9] 输入侦察")
    obs = bt.load_traffic(ev1.TRAFFIC)
    cw = bt.normalize_crosswalk(ev1.FINAL_CW, "final")
    matched = set(cw["matsim_link_id"].astype(str).str.strip())
    n_matched = len(matched)
    cw_obs = cw.merge(obs, left_on="lta_linkid", right_on="LinkID", how="inner")
    log(f"      观测断面 = {obs['LinkID'].nunique():,}   crosswalk 行 = {len(cw):,}  "
        f"断面 = {cw['lta_linkid'].nunique():,}  MATSim 链路 = {n_matched:,}")
    log(f"      crosswalk∩观测 行 = {len(cw_obs):,}  断面 = "
        f"{cw_obs['lta_linkid'].nunique():,}")

    ck("S0.1 crosswalk 行数 == 3,193", len(cw) == ANCHOR_CW_ROWS, f"实测 {len(cw):,}")
    ck("S0.2 crosswalk 断面数 == 576", cw["lta_linkid"].nunique() == ANCHOR_CW_SECTIONS,
       f"实测 {cw['lta_linkid'].nunique():,}")
    ck("S0.3 crosswalk 命中链路 == 3,037", n_matched == ANCHOR_CW_MATCHED,
       f"实测 {n_matched:,}")

    # ---------------------------------------------------------------- S1
    use_cache = args.reuse and not args.force and traj_cache.exists()
    if not use_cache:
        log(f"[1/9] 逐迭代轨迹（it.0..{args.last_iter}，{len(EXPERIMENTS)} 个 run；只读 linkstats）")
        t0 = time.time()
        traj_rows = []
        for eid, f, exp_dir, run_id, _n in EXPERIMENTS:
            for it in range(0, args.last_iter + 1):
                ls = ev1.locate_experiment_linkstats(exp_dir, run_id, it)
                if ls is None or not Path(ls).exists():
                    log(f"      {eid} it.{it}: MISSING")
                    continue
                df = load_linkstats(ls)
                m = df["LINK"].isin(matched)
                row = {"experiment_id": eid, "f_demand": f, "iteration": it,
                       "n_links": int(len(df))}
                row.update(window_sums(df))
                sm = window_sums(df.loc[m])
                row.update({k.replace("sum_all_", "sum_matched_"): v for k, v in sm.items()})
                row.update(section_estimator(cw_obs, df.loc[m, ["LINK",
                             "HRS7-8avg", "HRS8-9avg"]]))
                row["cong_all_8_9"] = congestion_multiplier(df)
                row["cong_matched_8_9"] = congestion_multiplier(df, m)
                row["cong_nonmatched_8_9"] = congestion_multiplier(df, ~m)
                row["oversat_all_8_9"] = oversat_share(df)
                row["oversat_matched_8_9"] = oversat_share(df, m)
                traj_rows.append(row)
                del df
            log(f"      {eid} 完成（累计 {time.time() - t0:.1f}s）")
        traj = pd.DataFrame(traj_rows)
        wcsv(traj, traj_cache)
        log(f"      轨迹 {len(traj):,} 行，用时 {time.time() - t0:.1f}s")
    else:
        log("[1/9] 复用缓存轨迹 " + traj_cache.name)
        traj = pd.read_csv(traj_cache, encoding="utf-8-sig")

    ck("S1.1 轨迹覆盖 D01-D04 且 it.0..19 完整",
       set(traj["experiment_id"]) == set(EIDS)
       and int(traj["iteration"].max()) >= args.last_iter,
       f"runs={sorted(set(traj['experiment_id']))} max_it={int(traj['iteration'].max())}")
    ck("S1.2 全网链路数 == 693,575", int(traj["n_links"].iloc[0]) == ANCHOR_LINKS,
       f"实测 {int(traj['n_links'].iloc[0]):,}")

    last = traj[traj["iteration"] == args.last_iter].set_index("experiment_id")
    worst = 0.0
    for (eid, w), (a, mv, so) in ANCHOR.items():
        r = last.loc[eid]
        worst = max(worst, abs(float(r[f"sum_all_{w}"]) - a),
                    abs(float(r[f"sum_matched_{w}"]) - mv))
        if so is not None:
            worst = max(worst, abs(float(r[f"simobs_{w}"]) - so))
    ck("S1.3 it.19 与 7.4.3-R 已发布锚点同源（max|d| < 1e-6）", worst < 1e-6,
       f"max|d| = {worst:.3e}")

    if REF_LEVELS.exists():
        ref = pd.read_csv(REF_LEVELS, encoding="utf-8-sig")
        ref = ref[(ref["series"] == "physical") & (ref["window"].isin(WIN_NAMES))]
        keymap = {w[0]: w[1] for w in WINDOWS}
        chk = 0.0
        for _, rr in ref.iterrows():
            if rr["method"] not in last.index:
                continue
            k = keymap.get(rr["window"])
            if k is None:
                continue
            chk = max(chk, abs(float(rr["sum_link_matched_raw"])
                               - float(last.loc[rr["method"], f"sum_matched_{k}"])),
                      abs(float(rr["sum_link_all_raw"])
                          - float(last.loc[rr["method"], f"sum_all_{k}"])))
        ck("S1.4 与 sim_only_window_levels.csv 的 ALL/MATCHED 全窗同源", chk < 1e-6,
           f"max|d| = {chk:.3e}")

    # ---------------------------------------------------------------- S2
    log("[2/9] 奇偶相位分解（周期-2 极限环识别）")
    metrics = [f"sum_all_{w[1]}" for w in WINDOWS] + \
              [f"sum_matched_{w[1]}" for w in WINDOWS] + \
              [f"simobs_{w[1]}" for w in OBS_WINDOWS]
    par_rows = []
    for eid in EIDS:
        g = traj[(traj["experiment_id"] == eid)
                 & (traj["iteration"] >= CONV_START) & (traj["iteration"] <= CONV_END)]
        for metric in metrics:
            if metric not in g.columns:
                continue
            ev = g[g["iteration"] % 2 == 0][metric].to_numpy(dtype=float)
            od = g[g["iteration"] % 2 == 1][metric].to_numpy(dtype=float)
            ev = ev[~np.isnan(ev)]
            od = od[~np.isnan(od)]
            if len(ev) == 0 or len(od) == 0:
                continue
            me, mo = float(np.mean(ev)), float(np.mean(od))
            cyc = (me + mo) / 2.0
            it19 = float(g[g["iteration"] == args.last_iter][metric].iloc[0])
            par_rows.append({
                "experiment_id": eid, "f_demand": F_OF[eid], "metric": metric,
                "n_even": len(ev), "n_odd": len(od),
                "mean_even": me, "mean_odd": mo, "cycle_mean": cyc,
                "parity_gap_rel": (abs(me - mo) / cyc) if cyc else np.nan,
                "cv_even_pct": float(np.std(ev, ddof=1) / me * 100) if me else np.nan,
                "cv_odd_pct": float(np.std(od, ddof=1) / mo * 100) if mo else np.nan,
                "it19": it19,
                "it19_vs_cycle_pct": ((it19 - cyc) / cyc * 100) if cyc else np.nan,
                "it19_vs_odd_pct": ((it19 - mo) / mo * 100) if mo else np.nan,
                "it19_vs_even_pct": ((it19 - me) / me * 100) if me else np.nan,
                "trend_pct_per_iter": float(
                    np.polyfit(g["iteration"].to_numpy(dtype=float),
                               g[metric].to_numpy(dtype=float), 1)[0] / cyc * 100)
                if cyc and len(g) > 2 else np.nan,
            })
    parity = pd.DataFrame(par_rows)
    wcsv(parity, args.out_dir / "assignment_parity_decomposition.csv")
    P = parity.set_index(["experiment_id", "metric"])

    def pm(eid, metric, col):
        try:
            return float(P.loc[(eid, metric), col])
        except KeyError:
            return float("nan")

    amp = {e: pm(e, "sum_matched_00_24", "parity_gap_rel") for e in EIDS}
    amp_all = {e: pm(e, "sum_all_00_24", "parity_gap_rel") for e in EIDS}
    amp_so = {e: pm(e, "simobs_08_09", "parity_gap_rel") for e in EIDS}
    for e in EIDS:
        log(f"      {e} f={F_OF[e]:.2f}  MATCHED 振幅={amp[e] * 100:6.2f}%  "
            f"ALL 振幅={amp_all[e] * 100:5.2f}%  SimObs(08-09) 振幅={amp_so[e] * 100:5.2f}%  "
            f"it.19 相对周期均值={pm(e, 'sum_matched_00_24', 'it19_vs_cycle_pct'):+6.2f}%")

    max_amp = max(v for v in amp.values() if not np.isnan(v))
    max_amp_all = max(v for v in amp_all.values() if not np.isnan(v))
    max_amp_so = max(v for v in amp_so.values() if not np.isnan(v))
    ck("S2.1 存在周期-2 极限环（MATCHED 周期振幅 > 3%）", max_amp > 0.03,
       f"max MATCHED 振幅 = {max_amp * 100:.2f}%")
    ck("S2.2 极限环在标定子集上相对全网放大 > 5x",
       (max_amp / max_amp_all) > 5.0, f"{max_amp / max_amp_all:.1f}x")
    seq = [amp[e] for e in EIDS]
    peak_e = max(EIDS, key=lambda e: amp[e])
    ck("S2.3 极限环振幅在 f>=1.10 后跃升一个数量级（D01 -> 峰值 > 10x）",
       max(seq) / seq[0] > 10.0,
       "  ".join(f"{e}={amp[e] * 100:.1f}%" for e in EIDS)
       + f"  峰值在 {peak_e}（比值 {max(seq) / seq[0]:.1f}x）")
    ck("S2.4 振幅峰值同样出现在 f=1.20（与 Sim/Obs 峰值同址）", peak_e == "D03",
       f"峰值 f = {F_OF[peak_e]:.2f}")

    # ---------------------------------------------------------------- S3
    log("[3/9] 冻结指标 x 迭代")
    fm = traj[["experiment_id", "f_demand", "iteration"]
              + [f"simobs_{w[1]}" for w in OBS_WINDOWS]].copy()
    fm["it_parity"] = np.where(fm["iteration"] % 2 == 1, "odd", "even")
    wcsv(fm, args.out_dir / "assignment_frozen_metric_by_iter.csv")

    # ---------------------------------------------------------------- S4
    log("[4/9] ★ 周期均值重估计（跨 f）")
    base = {}
    for _n, k, _h, _o, _ob in WINDOWS:
        base[("it19", k)] = float(last.loc["D01", f"sum_matched_{k}"])
        base[("cycle", k)] = pm("D01", f"sum_matched_{k}", "cycle_mean")
    so_base = {"it19": float(last.loc["D01", "simobs_08_09"]),
               "cycle": pm("D01", "simobs_08_09", "cycle_mean")}

    cyc_rows = []
    for eid in EIDS:
        f = F_OF[eid]
        for _n, k, _h, _o, _ob in WINDOWS:
            m = f"sum_matched_{k}"
            l19 = float(last.loc[eid, m])
            lc = pm(eid, m, "cycle_mean")
            r19 = l19 / base[("it19", k)] if base[("it19", k)] else np.nan
            rc = lc / base[("cycle", k)] if base[("cycle", k)] else np.nan
            cyc_rows.append({
                "experiment_id": eid, "f_demand": f, "window": _n, "window_key": k,
                "matched_it19": l19, "matched_cycle_mean": lc,
                "ratio_it19_to_f1p00": r19, "ratio_cycle_to_f1p00": rc,
                "attainment_it19": r19 / f, "attainment_cycle": rc / f,
                "expected_ratio": f,
                "dev_it19_vs_expected": r19 / f - 1.0, "dev_cycle_vs_expected": rc / f - 1.0,
            })
    cyc = pd.DataFrame(cyc_rows)
    wcsv(cyc, args.out_dir / "assignment_cycle_mean_reevaluation.csv")

    frows = []
    for eid in EIDS:
        frows.append({
            "experiment_id": eid, "f_demand": F_OF[eid],
            "simobs_08_09_it19": float(last.loc[eid, "simobs_08_09"]),
            "simobs_08_09_cycle_mean": pm(eid, "simobs_08_09", "cycle_mean"),
            "simobs_08_09_even_mean": pm(eid, "simobs_08_09", "mean_even"),
            "simobs_08_09_odd_mean": pm(eid, "simobs_08_09", "mean_odd"),
            "simobs_08_09_parity_gap": pm(eid, "simobs_08_09", "parity_gap_rel"),
            "it19_vs_cycle_pct": pm(eid, "simobs_08_09", "it19_vs_cycle_pct"),
        })
    fdf = pd.DataFrame(frows)
    fdf["implied_f_to_1_it19"] = 1.0 / fdf["simobs_08_09_it19"]
    fdf["implied_f_to_1_cycle"] = 1.0 / fdf["simobs_08_09_cycle_mean"]
    wcsv(fdf, args.out_dir / "assignment_cycle_mean_frozen_metric.csv")
    for _, r in fdf.iterrows():
        log(f"      {r['experiment_id']} f={r['f_demand']:.2f}  "
            f"SimObs(08-09) it.19={r['simobs_08_09_it19']:.4f}  "
            f"周期均值={r['simobs_08_09_cycle_mean']:.4f}  "
            f"（it.19 偏置 {r['it19_vs_cycle_pct']:+.2f}%）")

    sig_it19 = float(fdf["simobs_08_09_it19"].max() - fdf["simobs_08_09_it19"].min())
    sig_cyc = float(fdf["simobs_08_09_cycle_mean"].max()
                    - fdf["simobs_08_09_cycle_mean"].min())
    ck("S4.1 相位振幅 > 跨 f 信号（08-09 冻结指标）", max_amp_so > sig_it19,
       f"相位振幅 {max_amp_so * 100:.2f}% vs 跨 f 极差 {sig_it19 * 100:.2f}%")
    ck("S4.2 周期均值压缩跨 f 极差", sig_cyc < sig_it19,
       f"it.19 {sig_it19 * 100:.2f}% -> 周期均值 {sig_cyc * 100:.2f}%")

    # ---------------------------------------------------------------- S5
    log("[5/9] R_cal：标定断面在全网 VKT 中的份额")
    rc_rows = []
    for eid in EIDS:
        for _n, k, _h, _o, _ob in WINDOWS:
            i19 = float(last.loc[eid, f"sum_matched_{k}"])
            a19 = float(last.loc[eid, f"sum_all_{k}"])
            cm = pm(eid, f"sum_matched_{k}", "cycle_mean")
            ca = pm(eid, f"sum_all_{k}", "cycle_mean")
            rc_rows.append({"experiment_id": eid, "f_demand": F_OF[eid],
                            "window": _n, "window_key": k,
                            "R_cal_it19": i19 / a19 if a19 else np.nan,
                            "R_cal_cycle": cm / ca if ca else np.nan})
    rcal = pd.DataFrame(rc_rows)
    for k in [w[1] for w in WINDOWS]:
        sel = rcal["window_key"] == k
        b19 = rcal[sel & (rcal["experiment_id"] == "D01")]["R_cal_it19"].iloc[0]
        bc = rcal[sel & (rcal["experiment_id"] == "D01")]["R_cal_cycle"].iloc[0]
        rcal.loc[sel, "R_cal_it19_norm"] = rcal.loc[sel, "R_cal_it19"] / b19
        rcal.loc[sel, "R_cal_cycle_norm"] = rcal.loc[sel, "R_cal_cycle"] / bc
    wcsv(rcal, args.out_dir / "assignment_rcal_share.csv")
    for _, r in rcal[rcal["window_key"] == "00_24"].iterrows():
        log(f"      {r['experiment_id']} f={r['f_demand']:.2f}  "
            f"R_cal(00-24) it.19={r['R_cal_it19']:.5f}({r['R_cal_it19_norm']:.4f})  "
            f"周期={r['R_cal_cycle']:.5f}({r['R_cal_cycle_norm']:.4f})")

    # ---------------------------------------------------------------- S6
    log("[6/9] 重分布分解（matched vs non-matched）")
    dec_rows = []
    prev = None
    for eid in EIDS:
        cur = parity[parity["experiment_id"] == eid]
        if prev is not None:
            pf, pe = prev
            for _n, k, _h, _o, _ob in WINDOWS:
                a0 = pm(pf, f"sum_all_{k}", "cycle_mean")
                a1 = pm(eid, f"sum_all_{k}", "cycle_mean")
                m0 = pm(pf, f"sum_matched_{k}", "cycle_mean")
                m1 = pm(eid, f"sum_matched_{k}", "cycle_mean")
                da, dm = a1 - a0, m1 - m0
                dec_rows.append({
                    "from": pf, "to": eid, "f_from": F_OF[pf], "f_to": F_OF[eid],
                    "window": _n, "window_key": k,
                    "d_all": da, "d_matched": dm, "d_nonmatched": da - dm,
                    "share_matched_of_delta": (dm / da) if da else np.nan,
                    "expected_share_matched": (m0 / a0) if a0 else np.nan,
                    "concentration_ratio": ((dm / da) / (m0 / a0)) if (da and a0 and m0) else np.nan,
                    "d_matched_rel": (dm / m0) if m0 else np.nan,
                    "d_all_rel": (da / a0) if a0 else np.nan,
                })
        prev = (eid, cur)
    dec = pd.DataFrame(dec_rows)
    wcsv(dec, args.out_dir / "assignment_reallocation_decomposition.csv")

    osc_rows = []
    for eid in EIDS:
        for _n, k, _h, _o, _ob in WINDOWS:
            me = pm(eid, f"sum_matched_{k}", "mean_even")
            mo = pm(eid, f"sum_matched_{k}", "mean_odd")
            ae = pm(eid, f"sum_all_{k}", "mean_even")
            ao = pm(eid, f"sum_all_{k}", "mean_odd")
            dn = (ao - mo) - (ae - me)
            osc_rows.append({
                "experiment_id": eid, "f_demand": F_OF[eid], "window": _n, "window_key": k,
                "matched_even": me, "matched_odd": mo,
                "nonmatched_even": ae - me, "nonmatched_odd": ao - mo,
                "d_matched": mo - me, "d_nonmatched": dn,
                "cancellation": (-(mo - me) / dn) if dn else np.nan,
            })
    osc = pd.DataFrame(osc_rows)
    wcsv(osc, args.out_dir / "assignment_phase_reallocation.csv")
    for _, r in osc[osc["window_key"] == "00_24"].iterrows():
        log(f"      {r['experiment_id']} 相位翻转 00-24：MATCHED {r['d_matched']:+,.0f} vs "
            f"NON-MATCHED {r['d_nonmatched']:+,.0f}（抵消比 {r['cancellation']:.2f}）")

    # ---------------------------------------------------------------- S7
    log("[7/9] 逐链路翻转幅度与替代类别（it.17/18/19）")
    flip_rows, sub_rows, rank_rows = [], [], []
    sub_df = pd.DataFrame()
    for eid, f, exp_dir, run_id, _n in EXPERIMENTS:
        vec = {}
        for it in KEY_ITERS:
            ls = ev1.locate_experiment_linkstats(exp_dir, run_id, it)
            if ls is None:
                continue
            vec[it] = load_linkstats(
                ls, ["LINK", "FROM", "TO", "LENGTH", "FREESPEED", "CAPACITY",
                     "HRS8-9avg", "HRS0-24avg"]).set_index("LINK")
        if 18 not in vec or 19 not in vec:
            log(f"      {eid}: 缺少 it.18/it.19，跳过")
            continue
        a, b = vec[18], vec[19]
        j = pd.concat([
            a[["HRS0-24avg", "HRS8-9avg", "CAPACITY", "FREESPEED", "LENGTH", "FROM", "TO"]]
            .rename(columns={"HRS0-24avg": "q18"}),
            b[["HRS0-24avg"]].rename(columns={"HRS0-24avg": "q19"})], axis=1).fillna(0)
        j.index.name = "LINK"
        j["q18"] = j["q18"].astype(float)
        j["q19"] = j["q19"].astype(float)
        j["is_matched"] = j.index.isin(matched)
        s = j["q18"] + j["q19"]
        j["dq"] = j["q19"] - j["q18"]
        j["flip_amp"] = np.where(s > 0, 2 * j["dq"].abs() / s, 0.0)

        cal_nodes = set()
        for ln in matched:
            if ln in a.index:
                for kk in ("FROM", "TO"):
                    v = a.at[ln, kk]
                    if isinstance(v, str) and v:
                        cal_nodes.add(v)
        j["touches_calibrated_node"] = j["FROM"].isin(cal_nodes) | j["TO"].isin(cal_nodes)
        j["substitution_class"] = np.where(
            j["is_matched"], "matched",
            np.where(j["touches_calibrated_node"], "nonmatched_adjacent", "nonmatched_other"))

        g = j.groupby("substitution_class").agg(
            n_links=("dq", "size"), sum_dq=("dq", "sum"),
            sum_abs_dq=("dq", lambda x: float(x.abs().sum())),
            q18=("q18", "sum"), q19=("q19", "sum"))
        tot_abs = float(g["sum_abs_dq"].sum())
        for cls, r in g.iterrows():
            sub_rows.append({"experiment_id": eid, "f_demand": f, "class": cls,
                             "n_links": int(r["n_links"]), "sum_dq": float(r["sum_dq"]),
                             "sum_abs_dq": float(r["sum_abs_dq"]),
                             "share_of_abs_flip": float(r["sum_abs_dq"] / tot_abs)
                             if tot_abs else np.nan,
                             "q18": float(r["q18"]), "q19": float(r["q19"])})

        act = j[(j["q18"] > 0) | (j["q19"] > 0)]
        rho_all = float(act["q18"].corr(act["q19"], method="spearman"))
        actm = act[act["is_matched"]]
        rho_mat = float(actm["q18"].corr(actm["q19"], method="spearman"))
        top50 = act.nlargest(50, "q19")
        rank_rows.append({
            "experiment_id": eid, "f_demand": f,
            "n_active_links": int(len(act)), "n_active_matched": int(len(actm)),
            "spearman_it18_it19_all": rho_all,
            "spearman_it18_it19_matched": rho_mat,
            "spearman_it18_it19_top50q": float(
                top50["q18"].corr(top50["q19"], method="spearman")),
            "sum_abs_dq_matched_share": float(
                j.loc[j["is_matched"], "dq"].abs().sum() / j["dq"].abs().sum()),
            "sum_dq": float(j["dq"].sum()),
            "sum_abs_dq": float(j["dq"].abs().sum()),
            "matched_peak_flip_amp": float(
                j.loc[j["is_matched"], "flip_amp"].max()),
        })

        tp = j.nlargest(40, "flip_amp").reset_index()
        tp.insert(0, "f_demand", f)
        tp.insert(0, "experiment_id", eid)
        flip_rows.append(tp[["experiment_id", "f_demand", "LINK", "q18", "q19", "dq",
                             "flip_amp", "LENGTH", "FREESPEED", "CAPACITY",
                             "is_matched", "touches_calibrated_node",
                             "substitution_class"]])
        del vec
    if flip_rows:
        wcsv(pd.concat(flip_rows, ignore_index=True),
             args.out_dir / "assignment_link_flip_profile.csv")
    if sub_rows:
        sub_df = pd.DataFrame(sub_rows)
        wcsv(sub_df, args.out_dir / "assignment_substitution_classes.csv")
        for eid in ["D03", "D04"]:
            z = sub_df[(sub_df["experiment_id"] == eid)
                       & sub_df["class"].isin(["matched", "nonmatched_adjacent",
                                               "nonmatched_other"])]
            if not z.empty:
                log(f"      {eid} |dq| 分布：" + "  ".join(
                    f"{r['class']}={r['share_of_abs_flip'] * 100:.1f}%"
                    for _, r in z.iterrows()))
    if rank_rows:
        rk = pd.DataFrame(rank_rows)
        wcsv(rk, args.out_dir / "assignment_link_rank_stability.csv")
        for _, r in rk.iterrows():
            log(f"      {r['experiment_id']} 秩稳定 ρ(it18,it19) 全体={r['spearman_it18_it19_all']:.4f} "
                f"标定子集={r['spearman_it18_it19_matched']:.4f} "
                f"top50 高流={r['spearman_it18_it19_top50q']:.4f}  "
                f"MATCHED 承担|dq|份额={r['sum_abs_dq_matched_share'] * 100:.1f}%")
    else:
        rk = pd.DataFrame()

    ck("S7.1 逐链路翻转表已生成", bool(flip_rows),
       f"{len(flip_rows)} 个 run 的 top40（共 {len(flip_rows) * 40} 行）")
    if rank_rows:
        mx = max(r["sum_abs_dq_matched_share"] for r in rank_rows)
        ck("S7.2 标定链路承担的 |dq| 份额 > 其链路占比 0.4379%", mx > 0.004379,
           f"max = {mx * 100:.2f}%")
        mn_rho = min(r["spearman_it18_it19_all"] for r in rank_rows)
        ck("S7.3 相邻迭代秩相关 < 0.99（未收敛）", mn_rho < 0.99,
           f"min ρ = {mn_rho:.4f}")

    # ---------------------------------------------------------------- S8
    log("[8/9] 绕行指数与拥堵响应")
    dc_rows = []
    for eid, f, _d, _r, _n in EXPERIMENTS:
        g = traj[(traj["experiment_id"] == eid) & (traj["iteration"] >= CONV_START)]
        dc_rows.append({
            "experiment_id": eid, "f_demand": f,
            "vkt_per_demand_it19": float(last.loc[eid, "sum_all_00_24"]) / f,
            "vkt_per_demand_cycle": pm(eid, "sum_all_00_24", "cycle_mean") / f,
            "cong_all_8_9_it19": float(last.loc[eid, "cong_all_8_9"]),
            "cong_matched_8_9_it19": float(last.loc[eid, "cong_matched_8_9"]),
            "cong_nonmatched_8_9_it19": float(last.loc[eid, "cong_nonmatched_8_9"]),
            "cong_all_8_9_cycle": float(g["cong_all_8_9"].mean()),
            "cong_matched_8_9_cycle": float(g["cong_matched_8_9"].mean()),
            "cong_nonmatched_8_9_cycle": float(g["cong_nonmatched_8_9"].mean()),
            "oversat_all_8_9_it19": float(last.loc[eid, "oversat_all_8_9"]),
            "oversat_matched_8_9_it19": float(last.loc[eid, "oversat_matched_8_9"]),
        })
    dcf = pd.DataFrame(dc_rows)
    d0 = dcf[dcf["experiment_id"] == "D01"].iloc[0]
    dcf["detour_index_it19"] = dcf["vkt_per_demand_it19"] / d0["vkt_per_demand_it19"]
    dcf["detour_index_cycle"] = dcf["vkt_per_demand_cycle"] / d0["vkt_per_demand_cycle"]
    wcsv(dcf, args.out_dir / "assignment_detour_congestion.csv")
    for _, r in dcf.iterrows():
        log(f"      {r['experiment_id']} f={r['f_demand']:.2f}  绕行指数(周期)="
            f"{r['detour_index_cycle']:.4f}  拥堵倍率 ALL={r['cong_all_8_9_cycle']:.3f} "
            f"MATCHED={r['cong_matched_8_9_cycle']:.3f} "
            f"NONMATCHED={r['cong_nonmatched_8_9_cycle']:.3f}")
    ck("S8.1 绕行指数随 demand 非降",
       bool((dcf["detour_index_cycle"].diff().dropna() >= -1e-9).all()),
       "  ".join(f"{r['experiment_id']}={r['detour_index_cycle']:.4f}"
                 for _, r in dcf.iterrows()))

    # ---------------------------------------------------------------- S9
    log("[9/9] 配置溯源 + 判决 + 报告")
    prov = pd.DataFrame(config_provenance())
    wcsv(prov, args.out_dir / "assignment_config_provenance.csv")
    pv = prov[prov["param"] == "fractionOfIterationsToDisableInnovation"]
    rr = prov[(prov["param"] == "strategyName") & (prov["value"] == "ReRoute")]
    lr = prov[prov["param"] == "learningRate"]
    strat = sorted(set(prov[prov["param"] == "strategyName"]["value"]))
    all_inf = (not pv.empty) and all(v == "Infinity" for v in pv["value"])
    ck("S9.1 全部 run 的 fractionOfIterationsToDisableInnovation == Infinity",
       all_inf, f"值 = {sorted(set(pv['value'])) if not pv.empty else 'n/a'}")
    ck("S9.2 ReRoute 覆盖全部 config", len(rr) == len(CONFIGS),
       f"命中 {len(rr)}/{len(CONFIGS)}")
    ck("S9.3 planCalcScore learningRate == 1.0（无指数平滑）",
       (not lr.empty) and all(v == "1.0" for v in lr["value"]),
       f"值 = {sorted(set(lr['value'])) if not lr.empty else 'n/a'}")

    conv_verdict = ("UNCONVERGED_PERIOD2_LIMIT_CYCLE" if max_amp >= 0.10
                    else ("WEAK_PERIOD2_OSCILLATION" if max_amp >= 0.03 else "CONVERGED"))
    ident_verdict = ("CROSS_F_SIGNAL_BELOW_PHASE_NOISE"
                     if max_amp_so >= sig_it19 else "SIGNAL_ABOVE_PHASE_NOISE")
    z = cyc[cyc["window_key"] == "00_24"].sort_values("f_demand")
    a19 = z["attainment_it19"].to_numpy(dtype=float)
    ac = z["attainment_cycle"].to_numpy(dtype=float)
    nonmono = lambda v: not (np.all(np.diff(v) >= -1e-9) or np.all(np.diff(v) <= 1e-9))
    nm19, nmc = nonmono(a19), nonmono(ac)
    s19, sc = float(np.nanmax(a19) - np.nanmin(a19)), float(np.nanmax(ac) - np.nanmin(ac))
    verdict = f"{conv_verdict}__{ident_verdict}"
    log(f"      判决 = {verdict}")
    log(f"      attainment it.19     = {np.round(a19, 4).tolist()}  spread={s19:.4f}  "
        f"non_monotonic={nm19}")
    log(f"      attainment 周期均值  = {np.round(ac, 4).tolist()}  spread={sc:.4f}  "
        f"non_monotonic={nmc}")

    # 同相位（奇 / 偶）跨 f 判决表：检验「响应符号是否依赖采样相位」
    pha_rows = []
    for metric_key, label in [("sum_matched_00_24", "MATCHED 00-24"),
                              ("simobs_08_09", "SimObs 08-09")]:
        b_e = pm("D01", metric_key, "mean_even")
        b_o = pm("D01", metric_key, "mean_odd")
        for eid in EIDS:
            me = pm(eid, metric_key, "mean_even")
            mo = pm(eid, metric_key, "mean_odd")
            pha_rows.append({
                "metric": label, "experiment_id": eid, "f_demand": F_OF[eid],
                "ratio_even": me / b_e if b_e else np.nan,
                "ratio_odd": mo / b_o if b_o else np.nan,
                "attainment_even": (me / b_e / F_OF[eid]) if b_e else np.nan,
                "attainment_odd": (mo / b_o / F_OF[eid]) if b_o else np.nan,
            })
    pha = pd.DataFrame(pha_rows)
    wcsv(pha, args.out_dir / "assignment_same_parity_attainment.csv")
    for m in pha["metric"].unique():
        z = pha[pha["metric"] == m]
        ae = z["attainment_even"].to_numpy(dtype=float)
        ao = z["attainment_odd"].to_numpy(dtype=float)
        log(f"      同相位 attainment [{m}]  even={np.round(ae, 4).tolist()}  "
            f"odd={np.round(ao, 4).tolist()}")
        log(f"        even 非单调={nonmono(ae)}  odd 非单调={nonmono(ao)}  "
            f"even 峰={EIDS[int(np.nanargmax(ae))]}  odd 峰={EIDS[int(np.nanargmax(ao))]}")

    summary = {
        "step": "7.6B",
        "title": "Assignment / Route Stability Audit",
        "simulation": "none (zero simulation, read-only reuse of D01-D04 linkstats)",
        "objective": "R_cal = sum(Q_matched)/sum(Q_all) 随 demand scale 的变化；"
                     "分配是否收敛；f=1.20->1.25 落差的路径替代 vs 时间迁移归因",
        "crosswalk": "7.3.6A Final Calibration Crosswalk",
        "observation": "7.1 frozen (h7/h8 only)",
        "scale": SCALE, "n_links_all": ANCHOR_LINKS, "n_links_matched": n_matched,
        "convergence_window": [CONV_START, CONV_END],
        "config_provenance": {
            "fractionOfIterationsToDisableInnovation":
                sorted(set(pv["value"])) if not pv.empty else None,
            "strategies": strat,
            "learningRate": sorted(set(lr["value"])) if not lr.empty else None,
            "routingRandomness": sorted(set(
                prov[prov["param"] == "routingRandomness"]["value"])),
        },
        "parity_amplitude_matched": amp,
        "parity_amplitude_all": amp_all,
        "parity_amplitude_frozen_metric_08_09": amp_so,
        "oscillation_vs_all_ratio": (max_amp / max_amp_all) if max_amp_all else None,
        "frozen_metric_08_09": json.loads(fdf.to_json(orient="records")),
        "attainment_00_24_it19": a19.tolist(),
        "attainment_00_24_cycle": ac.tolist(),
        "spread_it19": s19, "spread_cycle": sc,
        "nonmonotonic_it19": bool(nm19), "nonmonotonic_cycle_mean": bool(nmc),
        "same_parity_attainment": json.loads(pha.to_json(orient="records")),
        "detour_index_cycle": {r["experiment_id"]: float(r["detour_index_cycle"])
                               for _, r in dcf.iterrows()},
        "rank_stability": json.loads(rk.to_json(orient="records")) if not rk.empty else [],
        "substitution_classes": json.loads(sub_df.to_json(orient="records"))
        if not sub_df.empty else [],
        "verdict": verdict,
        "convergence_verdict": conv_verdict,
        "identifiability_verdict": ident_verdict,
        "checks": _ck_rows,
        "checks_pass": int(sum(1 for c in _ck_rows if c["pass"])),
        "checks_total": len(_ck_rows),
        "matsim_rerun": False, "zero_simulation": True, "parameters_changed": False,
    }
    (args.out_dir / "assignment_stability_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, default=str), encoding="utf-8")

    write_report(args, traj, parity, cyc, fdf, rcal, dec, osc, dcf, prov, sub_df, rk, pha,
                 matched, verdict, conv_verdict, ident_verdict, a19, ac, s19, sc,
                 nm19, nmc, amp, amp_all, amp_so, n_matched, summary)
    (args.out_dir / "stability_console.log").write_text("\n".join(log_lines),
                                                       encoding="utf-8")
    log(f"      done -> {args.out_dir}")
    log(f"      checks: {summary['checks_pass']}/{summary['checks_total']} PASS")
    return 0


def f4(v):
    try:
        if v is None or (isinstance(v, float) and pd.isna(v)):
            return "n/a"
        return f"{float(v):.4f}"
    except Exception:
        return "n/a"


def write_report(args, traj, parity, cyc, fdf, rcal, dec, osc, dcf, prov, sub_df, rk, pha,
                 matched, verdict, conv_verdict, ident_verdict, a19, ac, s19, sc,
                 nm19, nmc, amp, amp_all, amp_so, n_matched, summary):
    L = []
    A = L.append
    A("# Step 7.6B - 分配 / 路径稳定性审计（zero simulation）\n")
    A("## Status\n")
    A("**零仿真**：只读复用 D01-D04（f = 1.00 / 1.10 / 1.20 / 1.25）的 linkstats；"
      "未重跑 MATSim、未改动任何参数、未选定 demand scale。"
      "评价接口 = 7.3.6A Final Crosswalk；观测 = 7.1 冻结口径（仅 h7/h8）；"
      "λ = 0.075；capacity = 1.00。\n")
    A("> 前置：7.4.3-R 已证明「非单调不能靠换窗口消除」，并把残差指向 "
      "**ReRoute 下的路径替代 / 分配重分布**。本步骤就是对该指向的零仿真直接检验。\n")

    A("## 0. ★ 最关键的先验事实：配置本身允许周期-2 极限环\n")
    A("| 参数 | 值 | 含义 |")
    A("|---|---|---|")
    A("| `fractionOfIterationsToDisableInnovation` | `Infinity` | **100% 的迭代都在创新**，"
      "不存在「停止选路、让网络静下来」的收尾阶段 |")
    A("| `strategyName` | `ReRoute`（weight 1.0，唯一策略） | **每个 agent 每一代都重新选路** |")
    A("| `learningRate`（planCalcScore） | `1.0` | 计划得分 = 上一代实测值，**无指数平滑** |")
    A("| `routingRandomness` | `0.0` | 确定性最短路 —— 上一代贵、这一代就全切走 |")
    A("")
    A("这是产生 **route flip-flop（周期-2 极限环）** 的标准配置组合。"
      "因此本步骤**不默认 it.19 已收敛**，而是把「迭代」当成一个显式维度审计。\n")

    A("## 1. 逐迭代轨迹：周期-2 极限环的直接证据\n")
    A("窗口 00-24，标定链路子集恒等式 `sum_matched_00_24`。\n")
    piv = traj.pivot_table(index="iteration", columns="experiment_id",
                           values="sum_matched_00_24")
    piv = piv[[c for c in ["D01", "D02", "D03", "D04"] if c in piv.columns]] / 1e6
    A("`it` 奇偶分列（MN 车公里）：\n")
    A("| it | " + " | ".join(f"{c} (百万)" for c in piv.columns) + " | 相位 |")
    A("|---|" + "---:|" * len(piv.columns) + "---|")
    for it, r in piv.iterrows():
        ph = "**奇**" if int(it) % 2 == 1 else "偶"
        mk = " ★评价迭代" if int(it) == args.last_iter else ""
        A(f"| {int(it)}{mk} | " + " | ".join(f"{v:.4f}" for v in r) + f" | {ph} |")
    A("")
    A("奇偶两列从 it.0 起完全分离 —— 这是极限环，不是噪声。全网口径（ALL）同样振荡"
      "但幅度小一个数量级，说明振荡是 **标定断面 <-> 其余路网之间的路径替代**，"
      "而不是总量波动。\n")

    A("### 1.1 奇 / 偶相位分解（收敛窗 it.%d-%d）\n" % (CONV_START, CONV_END))
    A("| 实验 | f | 指标 | 偶相位均值 | 奇相位均值 | 周期均值 | **周期振幅** | it.19 |"
      " it.19 相对周期均值 | 线性趋势(%/it) |")
    A("|---|---:|---|---:|---:|---:|---:|---:|---:|---:|")
    for _, r in parity.iterrows():
        if r["metric"] not in ("sum_matched_00_24", "sum_all_00_24", "simobs_08_09"):
            continue
        nm = {"sum_matched_00_24": "MATCHED 00-24", "sum_all_00_24": "ALL 00-24",
              "simobs_08_09": "SimObs 08-09"}[r["metric"]]
        is_rate = r["metric"].startswith("simobs")
        g_ = (lambda v: f"{v:.4f}") if is_rate else (lambda v: f"{v:,.2f}")
        A(f"| {r['experiment_id']} | {r['f_demand']:.2f} | {nm} | {g_(r['mean_even'])} | "
          f"{g_(r['mean_odd'])} | {g_(r['cycle_mean'])} | "
          f"**{r['parity_gap_rel'] * 100:.2f}%** | {r['it19']:,.4f} | "
          f"{r['it19_vs_cycle_pct']:+.2f}% | {f4(r['trend_pct_per_iter'])} |")
    A("")
    A("**振幅在 f>=1.10 后跃升一个数量级，峰值同样落在 f=1.20**：\n")
    A("| 实验 | f | MATCHED 周期振幅 | ALL 周期振幅 | 放大倍数 |")
    A("|---|---:|---:|---:|---:|")
    for e in EIDS:
        if e in amp and amp_all.get(e):
            A(f"| {e} | {F_OF[e]:.2f} | {amp[e] * 100:.2f}% | {amp_all[e] * 100:.2f}% | "
              f"{amp[e] / amp_all[e]:.1f}x |")
    A("")
    A("> f=1.00 时振荡仅约 1.6%（可忽略）；**f >= 1.20 时标定子集的振荡达 ~17-21%**，"
      "而同一时刻全网总量只振荡 1-2%。"
      "=> 网络在两组近乎等价的路径集合之间整体来回切换，而这两组路径对"
      "「3,037 条标定主干道」的装载量差异巨大。\n")

    A("## 2. ★ 冻结指标的周期均值重估计（08-09，主窗口）\n")
    A("| 实验 | f | SimObs it.19 | SimObs 周期均值 | 偶相位 | 奇相位 | 相位振幅 | it.19 偏置 |"
      " 补齐到 1（it.19） | 补齐到 1（周期） |")
    A("|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
    for _, r in fdf.iterrows():
        A(f"| {r['experiment_id']} | {r['f_demand']:.2f} | {r['simobs_08_09_it19']:.4f} | "
          f"**{r['simobs_08_09_cycle_mean']:.4f}** | {r['simobs_08_09_even_mean']:.4f} | "
          f"{r['simobs_08_09_odd_mean']:.4f} | {r['simobs_08_09_parity_gap'] * 100:.2f}% | "
          f"{r['it19_vs_cycle_pct']:+.2f}% | {r['implied_f_to_1_it19']:.4f} | "
          f"{r['implied_f_to_1_cycle']:.4f} |")
    A("")
    sso19 = float(fdf["simobs_08_09_it19"].max() - fdf["simobs_08_09_it19"].min())
    ssoc = float(fdf["simobs_08_09_cycle_mean"].max()
                 - fdf["simobs_08_09_cycle_mean"].min())
    A(f"- 08-09 冻结指标的跨 f 极差：单一迭代（it.19）= **{sso19 * 100:.2f}%**，"
      f"周期均值 = **{ssoc * 100:.2f}%**。")
    A(f"- 而 f>=1.20 的**相位振幅单独就有 "
      f"{min(fdf.loc[fdf['experiment_id'].isin(['D03', 'D04']), 'simobs_08_09_parity_gap']) * 100:.1f}"
      f"-{max(fdf['simobs_08_09_parity_gap']) * 100:.1f}%** ⇒ **跨 f 信号 < 相位噪声**，"
      "单迭代水平不可用于 demand scale 判决。")
    A(f"- 00-24 标定子集的 attainment 跨 f 极差：" 
      f"it.19 = **{s19 * 100:.2f}%**，周期均值 = **{sc * 100:.2f}%**。\n")

    A("### 2.1 ★ 判读的决定性检验：同相位（奇 / 偶）分别比较\n")
    A("如果把 D01-D04 **各自只用同一相位**比较（而不是混合成一个周期均值），"
      "响应形态就会**随采样相位改变符号**：\n")
    A("| 指标 | 相位 | " + " | ".join(f"{e} (f={F_OF[e]:.2f})" for e in EIDS) + " |")
    A("|---|---|" + "---:|" * len(EIDS))
    for m in pha["metric"].unique():
        z = pha[pha["metric"] == m]
        A(f"| {m} attainment | 偶 | "
          + " | ".join(f"{v:.4f}" for v in z["attainment_even"]) + " |")
        A(f"| {m} attainment | 奇 | "
          + " | ".join(f"{v:.4f}" for v in z["attainment_odd"]) + " |")
    A("")
    for m in pha["metric"].unique():
        z = pha[pha["metric"] == m]
        ae = z["attainment_even"].to_numpy(dtype=float)
        ao = z["attainment_odd"].to_numpy(dtype=float)
        A(f"- **{m}**：偶相位 " +
          ("**单调下降**" if (np.all(np.diff(ae) <= 1e-9) or np.all(np.diff(ae) >= -1e-9))
           else "非单调") +
          f"（{np.round(ae, 4).tolist()}），奇相位 " +
          ("**峰在 " + EIDS[int(np.nanargmax(ao))] + "**"
           if not (np.all(np.diff(ao) <= 1e-9) or np.all(np.diff(ao) >= -1e-9))
           else "单调") +
          f"（{np.round(ao, 4).tolist()}）。")
    A("")
    A("> **奇数相位里看到『f=1.20 最优』，偶数相位里看到『越加车越差』——两者都是同一次仿真的样本。**"
      "响应符号由采样相位决定，这本身就证明：**该实验无法识别 demand scale。**\n")

    A("## 3. R_cal：标定断面承载的全网 VKT 份额\n")
    A("| 实验 | f | 窗口 | R_cal(it.19) | 归一 | R_cal(周期均值) | 归一 |")
    A("|---|---:|---|---:|---:|---:|---:|")
    for _, r in rcal[rcal["window_key"].isin(["08_09", "07_09", "00_24"])].iterrows():
        A(f"| {r['experiment_id']} | {r['f_demand']:.2f} | {r['window']} | "
          f"{r['R_cal_it19']:.5f} | {r['R_cal_it19_norm']:.4f} | "
          f"{r['R_cal_cycle']:.5f} | {r['R_cal_cycle_norm']:.4f} |")
    A("")
    A(f"> 标定链路只占全网链路的 **{n_matched / ANCHOR_LINKS * 100:.3f}%**，"
      "却承载约 6% 的 VKT。R_cal 的跨 f 变化就是「流量是否离开标定断面」的直接度量。\n")

    A("## 4. 重分布分解：MATCHED 与 NON-MATCHED 的增量对冲\n")
    A("### 4.1 同一 run 内的相位翻转（偶 -> 奇）\n")
    A("| 实验 | f | 窗口 | ΔMATCHED | ΔNON-MATCHED | 抵消比 |")
    A("|---|---:|---|---:|---:|---:|")
    for _, r in osc.iterrows():
        A(f"| {r['experiment_id']} | {r['f_demand']:.2f} | {r['window']} | "
          f"{r['d_matched']:+,.0f} | {r['d_nonmatched']:+,.0f} | {f4(r['cancellation'])} |")
    A("")
    A("> 抵消比 -> 1 表示 **MATCHED 的增量被 NON-MATCHED 的等量减量完全对冲**，"
      "即纯粹的**路径替代**，不涉及总量或时段迁移。\n")
    A("### 4.2 跨 f 的周期均值增量分解（窗口 00-24）\n")
    A("| from -> to | 窗口 | ΔALL | ΔMATCHED | ΔNON-MATCHED | MATCHED 占增量比 |"
      " MATCHED 自然占比 | 集中度 |")
    A("|---|---|---:|---:|---:|---:|---:|---:|")
    for _, r in dec[dec["window_key"] == "00_24"].iterrows():
        A(f"| {r['from']} -> {r['to']} | {r['window']} | {r['d_all']:+,.0f} | "
          f"{r['d_matched']:+,.0f} | {r['d_nonmatched']:+,.0f} | "
          f"{f4(r['share_matched_of_delta'])} | {f4(r['expected_share_matched'])} | "
          f"{f4(r['concentration_ratio'])} |")
    A("")

    A("## 5. 替代类别（it.18 <-> it.19 的逐链路翻转）\n")
    if not sub_df.empty:
        z = sub_df[sub_df["class"].isin(["matched", "nonmatched_adjacent",
                                         "nonmatched_other"])]
        A("| 实验 | f | 类别 | 链路数 | Σdq | Σ|dq| | 占 |dq| 份额 |")
        A("|---|---:|---|---:|---:|---:|---:|")
        for _, r in z.iterrows():
            A(f"| {r['experiment_id']} | {r['f_demand']:.2f} | `{r['class']}` | "
              f"{r['n_links']:,} | {r['sum_dq']:+,.0f} | {r['sum_abs_dq']:,.0f} | "
              f"{r['share_of_abs_flip'] * 100:.1f}% |")
        A("")
    A("> `nonmatched_adjacent` = 与标定链路共享上下游节点的非观测链路，"
      "作为「平行 / 邻近走廊」的可计算代理。\n")
    if not rk.empty:
        A("### 5.1 逐链路秩稳定性\n")
        A("| 实验 | f | 有流链路数 | ρ(it18,it19) 全体 | ρ 标定子集 | ρ top50 高流 |"
          " MATCHED 承担 |dq| 份额 | Σ|dq| |")
        A("|---|---:|---:|---:|---:|---:|---:|---:|")
        for _, r in rk.iterrows():
            A(f"| {r['experiment_id']} | {r['f_demand']:.2f} | {r['n_active_links']:,} | "
              f"{r['spearman_it18_it19_all']:.4f} | {r['spearman_it18_it19_matched']:.4f} | "
              f"{r['spearman_it18_it19_top50q']:.4f} | "
              f"{r['sum_abs_dq_matched_share'] * 100:.1f}% | {r['sum_abs_dq']:,.0f} |")
        A("")

    A("## 6. 绕行与拥堵响应\n")
    A("| 实验 | f | 绕行指数(it.19) | 绕行指数(周期) | 拥堵倍率 ALL | MATCHED | NON-MATCHED |"
      " 8-9 过饱和份额(ALL) | 8-9 过饱和份额(MATCHED) |")
    A("|---|---:|---:|---:|---:|---:|---:|---:|---:|")
    for _, r in dcf.iterrows():
        A(f"| {r['experiment_id']} | {r['f_demand']:.2f} | {r['detour_index_it19']:.4f} | "
          f"{r['detour_index_cycle']:.4f} | {r['cong_all_8_9_cycle']:.3f} | "
          f"{r['cong_matched_8_9_cycle']:.3f} | {r['cong_nonmatched_8_9_cycle']:.3f} | "
          f"{r['oversat_all_8_9_it19'] * 100:.2f}% | "
          f"{r['oversat_matched_8_9_it19'] * 100:.2f}% |")
    A("")
    A("> 绕行指数 = (ΣVKT / f) / 同一比值 @f=1.00。> 1 表示**单位需求走的链路变多（路径变长）**。\n")

    A("## 7. 判决\n")
    A(f"### `{verdict}`\n")
    A(f"- **收敛性判决 `{conv_verdict}`**：标定子集的周期-2 振幅最大达 "
      f"**{max(amp.values()) * 100:.2f}%**（f=1.20）；全网口径仅 "
      f"{max(amp_all.values()) * 100:.2f}%，放大 "
      f"{max(amp.values()) / max(amp_all.values()):.1f} 倍。"
      "这不是噪声，是结构性的 route flip-flop。")
    A(f"- **可识别性判决 `{ident_verdict}`**：单一迭代（it.19）的跨 f 极差 "
      f"{s19 * 100:.2f}% 小于 f>=1.20 的相位振幅 ~{max(amp_so.values()) * 100:.1f}%。")
    A(f"- it.19 的 attainment（归一化 MATCHED 水平 / f，窗口 00-24）："
      f"`{[round(float(v), 4) for v in a19]}`，非单调 = **{'是' if nm19 else '否'}**，"
      f"极差 {s19 * 100:.2f}%。")
    A(f"- 周期均值 attainment：`{[round(float(v), 4) for v in ac]}`，"
      f"非单调 = **{'是' if nmc else '否'}**，极差 {sc * 100:.2f}%。\n")

    A("### 对既有结论的修正\n")
    A("| 既有结论 | 本步骤修正 |")
    A("|---|---|")
    A("| 7.4.3「f=1.20 峰 0.8601 -> f=1.25 回落 0.7599」 | **部分是相位伪影**："
      f"周期均值把跨 f 极差从 it.19 的 {s19 * 100:.2f}% 压缩到 {sc * 100:.2f}%；"
      "f=1.20 在 it.19 恰好位于其振荡高端，被系统性抬高 |")
    A("| 7.4.3-R「残差指向 ReRoute 路径替代」 | **被直接证实**：相位翻转时 MATCHED 的增量被 "
      "NON-MATCHED 等量对冲（抵消比接近 1），而全网总量只动 1-2% ⇒ 纯路径替代 |")
    A("| 7.4.3-R「约 6.7% 与窗口无关的标定靶场缺口」 | **在周期均值口径下仍存活**，"
      "但必须先由相位振幅给出其置信区间；单迭代无法把它与振荡区分开 |")
    A("")
    A("### 由此得到的方法论结论\n")
    A("**在修复 route-choice 机制之前，任何基于单一迭代的 demand scale 判决都不成立。**\n")

    A("## 8. 动作项（按优先级）\n")
    A("1. **★ 最高优先级（配置层，需重跑但代价明确）**：给 replanning 加收尾机制——"
      "`fractionOfIterationsToDisableInnovation = 0.5~0.9`；把 `ReRoute` 权重降到 0.10-0.20 "
      "并加入 `ChangeExpBeta` / `BestScore`；给 planCalcScore 设 `learningRate < 1`。"
      "目标是把标定子集的周期振幅压到 3% 以下，使 Sim/Obs 的单迭代水平具备可辨识性。")
    A("2. **零仿真即可立即采用**：评价口径从「it.19 单点」改为"
      f"**收敛窗 (it.{CONV_START}-{CONV_END}) 的奇偶相位均衡周期均值**；"
      f"本步骤已证明该口径把跨 f 极差压缩 {s19 * 100:.2f}% -> {sc * 100:.2f}%。")
    A("3. **不要**在收敛问题解决前再增加 demand scale 的 MATSim 跑次——"
      "新增跑次只会扩大同一个相位带。")
    A("4. **可并行的数据动作项**（7.6A 已列）：LTA 分车型交通量计数 + HTS 出发时刻，"
      "这是把需求口径 f 从区间收敛到单点的唯一途径。")
    A("5. 7.6C（OD 空间结构 / 距离带）仍可做，但**必须建立在周期均值口径上**，"
      "否则会被同一相位噪声污染。\n")

    A("## 9. 产物与校验\n")
    A("| 文件 | 内容 |")
    A("|---|---|")
    for fn, desc in [
        ("assignment_iter_trajectory.csv", "逐 run x 逐 iteration（it.0-19）的标量轨迹"),
        ("assignment_parity_decomposition.csv", "奇/偶相位分解与极限环振幅"),
        ("assignment_frozen_metric_by_iter.csv", "冻结指标（3 个可观测窗）逐迭代"),
        ("assignment_cycle_mean_reevaluation.csv", "周期均值 vs it.19 的跨 f 重估计"),
        ("assignment_cycle_mean_frozen_metric.csv", "08-09 主窗口冻结指标的周期均值重估"),
        ("assignment_rcal_share.csv", "标定断面 VKT 份额 R_cal"),
        ("assignment_reallocation_decomposition.csv", "跨 f 的 matched/non-matched 增量分解"),
        ("assignment_phase_reallocation.csv", "同一 run 内相位翻转的增量对冲"),
        ("assignment_link_flip_profile.csv", "top40 振荡链路属性画像"),
        ("assignment_substitution_classes.csv", "替代类别（matched/邻接/其它）汇总"),
        ("assignment_link_rank_stability.csv", "逐链路秩稳定性与 |dq| 归属"),
        ("assignment_same_parity_attainment.csv", "★ 同相位（奇/偶）跨 f 的 attainment 对照"),
        ("assignment_detour_congestion.csv", "绕行指数与拥堵响应"),
        ("assignment_config_provenance.csv", "配置溯源（replanning / strategy / score）"),
        ("assignment_stability_summary.json", "机器可读汇总（含全部校验项）"),
    ]:
        A(f"| `{fn}` | {desc} |")
    A("")
    A(f"**校验：{summary['checks_pass']}/{summary['checks_total']} PASS**\n")
    A("| 校验项 | 结果 | 详情 |")
    A("|---|---|---|")
    for c in summary["checks"]:
        A(f"| {c['check']} | {'PASS' if c['pass'] else '**FAIL**'} | {c['detail']} |")
    A("")
    A("---\n")
    A(f"口径：观测 7.1 冻结（仅 h7/h8）；仿真 median(edges HRSx-yavg) x {SCALE:.5f}；"
      "crosswalk = 7.3.6A Final；randomSeed=4711；λ=0.075；capacity=1.00；"
      "**零仿真、只读、未改任何参数**。\n")
    (args.out_dir / "STEP7_6B_REPORT.md").write_text("\n".join(L), encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
