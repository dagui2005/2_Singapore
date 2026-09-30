#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""
xcheck_flow_quality_7_9a1.py — **独立复核** §5 ① 流量层质量三项（Pearson r / WMAPE / GEH 分布）

动机
----
`flow_quality()` 给出的 v1.0 数值（`Pearson r = 0.3452`、`WMAPE = 0.7176`、GEH 中位 `26.09`、
GEH<5 占比 `8.51 %`）与「池化 `Sim/Obs = 0.9993`」形成强烈张力 ⇒ 属**头条数字**，按纪律必须独立复核。

独立性声明（本脚本与 `flow_quality()` 的差异）
----
1. 断面级 `(Sim, Obs)` 对**重新从冻结输入复算**：`ev1.backtest_one` + `V1_conv.linkstats.txt.gz`
   （与 `E.eval_run` 内部所用**同一路径、同一函数**；⛔ 不复用 `guardrail` 缓存里的任何数值）。
2. 三项统计量用 **numpy / pandas 向量化实现**重算（`np.corrcoef` / `pd.Series.corr` / 向量化 GEH），
   ⛔ **不调用** `A.pearson` / `A.geh` / `A.flow_quality` 的任何被测量函数。
3. 新增**口径敏感性**：零流断面（`sim == 0`，共 53 条、占 `Σobs` ≈8 %）对 Pearson 的影响。

⛔ 只读输入；只写 `reports/sampling_capacity_7_9a1/_xcheck_flowq_v10.csv` 与 `_xcheck_flowq_v10.json`。

用法
----
    python scripts/od/xcheck_flow_quality_7_9a1.py
"""
from __future__ import annotations

import json
import math
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(r"D:\Luan\2026-05\2_Singapore")
SCRIPTS_OD = ROOT / "scripts" / "od"
sys.path.insert(0, str(SCRIPTS_OD))

import audit_sampling_capacity_7_9a1 as A        # noqa: E402  仅取路径常量与 ctx
import evaluate_calibration_7_4_2 as ev1         # noqa: E402
import compare_final_crosswalk_7_3_6b as bt      # noqa: E402

OUT = A.REPORT_ROOT


# ---------------- 独立实现（numpy/pandas；⛔ 不用 A.* 的统计函数） ----------------
def ind_pearson(x: np.ndarray, y: np.ndarray) -> float:
    """np.corrcoef 版（dof=1 归一化与 A.pearson 同为总体式，仅数值路径不同）。"""
    if x.size < 3:
        return float("nan")
    sx, sy = x.std(), y.std()
    if sx == 0 or sy == 0 or not np.isfinite(sx) or not np.isfinite(sy):
        # 与 Pearson 定义一致：任一序列常值 ⇒ 无相关可言
        if sx == 0 and sy == 0:
            return float("nan")
        return float("nan")
    return float(np.corrcoef(x, y)[0, 1])


def ind_wmape(sim: np.ndarray, obs: np.ndarray) -> float:
    so = float(obs.sum())
    return float(np.abs(sim - obs).sum() / so) if so > 0 else float("nan")


def ind_geh(sim: np.ndarray, obs: np.ndarray) -> np.ndarray:
    tot = sim + obs
    out = np.zeros_like(sim, dtype=float)
    m = tot > 0
    out[m] = np.sqrt(2.0 * (sim[m] - obs[m]) ** 2 / tot[m])
    return out


def block(sim: np.ndarray, obs: np.ndarray) -> dict:
    g = ind_geh(sim, obs)
    n = sim.size
    gs = np.sort(g)
    med = float(gs[n // 2]) if n % 2 else float(0.5 * (gs[n // 2 - 1] + gs[n // 2]))
    lt5 = int((g < 5.0).sum())
    mid = int(((g >= 5.0) & (g < 10.0)).sum())
    return {"n": n,
            "pearson_np": ind_pearson(sim, obs),
            "pearson_pd": float(pd.Series(sim).corr(pd.Series(obs))),
            "wmape": ind_wmape(sim, obs),
            "sum_sim": float(sim.sum()), "sum_obs": float(obs.sum()),
            "pooled_sim_obs": float(sim.sum() / obs.sum()) if obs.sum() > 0 else float("nan"),
            "geh_median": med, "geh_mean": float(g.mean()),
            "geh_lt5": lt5, "geh_5to10": mid, "geh_ge10": n - lt5 - mid,
            "share_geh_lt5": lt5 / n,
            "obs_share": float(obs.sum())}


def main() -> int:
    t0 = time.time()
    print("=" * 92)
    print("7.9A-1 §5 ① 流量层质量 —— 独立复核（numpy/pandas 重算；不复用 flow_quality 输出）")
    print("=" * 92)

    xw = A.load_crosswalk_raw()
    ctx = A.guardrail_ctx(xw)
    cycle_ls = A.CYCLE_DIR / "V1_conv.linkstats.txt.gz"
    print(f"[1] cycle linkstats = {cycle_ls.name}  存在={cycle_ls.exists()}"
          f"  大小={cycle_ls.stat().st_size/2**20:.2f} MiB" if cycle_ls.exists() else "!! 缺失")
    assert cycle_ls.exists(), "缺少 V1_conv.linkstats.txt.gz（先跑 --check-v10）"

    # ★与 E.eval_run 内部**逐参数相同**的调用
    sec = ev1.backtest_one("V1|cycle", ctx["cw_n"].copy(), ctx["obs_df"], cycle_ls)
    sec["lta_linkid"] = sec["lta_linkid"].astype(str).str.strip()
    print(f"[2] 复算断面级 sim/obs：n={len(sec)}")
    assert len(sec) == 576, f"断面数异常 {len(sec)}"

    sim = sec["sim_8_9_scaled"].to_numpy(dtype=float)
    obs = sec["obs_8_9"].to_numpy(dtype=float)
    nan_n = int(np.isnan(sim).sum() + np.isnan(obs).sum())
    print(f"    NaN 计数 = {nan_n}（0 表示全部断面均有匹配链路）")

    # ---- 与 A.flow_quality 对照 ----
    fq = A.flow_quality(sec)
    print(f"[3] A.flow_quality(): r={fq['pearson_r']!r} WMAPE={fq['wmape']!r} "
          f"GEH中位={fq['geh_median']!r} GEH<5={fq['geh_lt5']}/{fq['n_used']}")

    res = {}
    res["ALL_576"] = block(sim, obs)
    m_pos = sim > 0
    res["POSITIVE_ONLY"] = block(sim[m_pos], obs[m_pos])
    m_zero = sim <= 0
    res["ZERO_SIM_53"] = {"n": int(m_zero.sum()), "sum_obs": float(obs[m_zero].sum()),
                          "obs_share": float(obs[m_zero].sum() / obs.sum()),
                          "geh": [float(x) for x in ind_geh(sim[m_zero], obs[m_zero])]}
    for k in (10.0, 50.0, 100.0, 200.0):
        mk = obs >= k
        res[f"OBS_GE_{int(k)}"] = block(sim[mk], obs[mk])

    print("\n[4] 独立重算（分口径）")
    hdr = f"{'口径':16s} {'n':>5s} {'Pearson_np':>11s} {'Pearson_pd':>11s} {'WMAPE':>8s} " \
          f"{'GEH中位':>9s} {'GEH<5':>6s} {'池化Sim/Obs':>12s} {'Σobs占比':>9s}"
    print(hdr)
    print("-" * len(hdr))
    for k, v in res.items():
        if k == "ZERO_SIM_53":
            print(f"{k:16s} {v['n']:>5d} {'—':>11s} {'—':>11s} {'—':>8s} {'—':>9s} {'—':>6s} "
                  f"{'—':>12s} {v['obs_share']:>9.4f}")
            continue
        print(f"{k:16s} {v['n']:>5d} {v['pearson_np']:>11.4f} {v['pearson_pd']:>11.4f} "
              f"{v['wmape']:>8.4f} {v['geh_median']:>9.3f} {v['geh_lt5']:>6d} "
              f"{v['pooled_sim_obs']:>12.6f} {v['obs_share']:>9.4f}")

    # ---- 一致性断言（与 flow_quality 必须逐位一致）----
    a = res["ALL_576"]
    checks = {
        "n == n_used": a["n"] == fq["n_used"],
        "pearson_np == flow_quality.pearson_r": abs(a["pearson_np"] - fq["pearson_r"]) < 1e-12,
        "pearson_pd == flow_quality.pearson_r": abs(a["pearson_pd"] - fq["pearson_r"]) < 1e-12,
        "wmape 逐位": abs(a["wmape"] - fq["wmape"]) < 1e-15,
        "geh_median 逐位": abs(a["geh_median"] - fq["geh_median"]) < 1e-12,
        "geh_mean 逐位": abs(a["geh_mean"] - fq["geh_mean"]) < 1e-12,
        "geh_lt5 逐位": a["geh_lt5"] == fq["geh_lt5"],
        "geh_5to10 逐位": a["geh_5to10"] == fq["geh_5to10"],
        "geh_ge10 逐位": a["geh_ge10"] == fq["geh_ge10"],
        "share_geh_lt5 逐位": abs(a["share_geh_lt5"] - fq["share_geh_lt5"]) < 1e-15,
        "池化 Sim/Obs == 0.9993347697 (FROZEN)":
            abs(a["pooled_sim_obs"] - A.SIM_OBS_FROZEN) < 1e-9,
        "零流断面数 == 53": int(m_zero.sum()) == 53,
    }
    print("\n[5] 一致性断言")
    ok = True
    for k, v in checks.items():
        ok &= bool(v)
        print(f"    [{'OK' if v else 'FAIL'}] {k}")

    # ---- 落盘 ----
    sec[["lta_linkid", "RoadCat", "RoadName", "matched_matsim_edges",
         "sim_8_9_scaled", "obs_8_9", "ratio_8_9"]].to_csv(
        OUT / "_xcheck_flowq_v10.csv", index=False, encoding="utf-8-sig")
    verdict = "FLOW_QUALITY_XCHECK_OK" if ok else "FLOW_QUALITY_XCHECK_MISMATCH"
    rep = {"script": Path(__file__).name, "verdict": verdict, "n_checks": len(checks),
           "n_pass": sum(1 for v in checks.values() if v), "checks": {k: bool(v) for k, v in checks.items()},
           "flow_quality_reported": fq, "independent": res, "nan_count": nan_n,
           "note": "独立重算：sim/obs 由 ev1.backtest_one 复算；统计量由 numpy/pandas 实现，"
                   "⛔ 不调用 A.pearson / A.geh / A.flow_quality 的被测函数",
           "elapsed_s": round(time.time() - t0, 1),
           "generated_at": time.strftime("%Y-%m-%d %H:%M:%S")}
    (OUT / "_xcheck_flowq_v10.json").write_text(
        json.dumps(rep, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n{'=' * 92}\n判决 = {verdict}   {rep['n_pass']}/{rep['n_checks']}   "
          f"耗时 {rep['elapsed_s']} s\n{'=' * 92}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
