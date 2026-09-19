#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""
evaluate_demand_response_7_6f_1.py — Step 7.6F-1：稳定底座上的粗档 demand-response 曲线评价
（零仿真；只读既有 linkstats；不启动 MATSim；不改任何参数）。

回答的问题
----------
在 route-choice 已冻结（7.6E `STABILITY_PASS`）的稳定分配底座上：

    f_demand  ->  Q_MATCHED  ->  Sim/Obs

是否存在**可复现、单调、稳定**的响应关系？（并同时报告 frozen target 不确定性）

★ 本步**不选 demand scale**、**不评价 λ**、**不评价 OD 空间结构**。

口径纪律（与 7.3.6B / 7.4.2 / 7.4.3 / 7.5A / 7.5B / 7.6B–7.6F-0 逐字节同源）
--------------------------------------------------------------------------
    obs  = 7.1 冻结口径（工作日 -> 日内均值 -> LinkID x hour 日中位；hour = 7,8）
    sim  = median(匹配 MATSim 有向边 HRSx-yavg) x SCALE
    SCALE = 2.29897（= 459794/200000；**复制机制下恒定**，与 N 无关）
    ★ 全档统一 2.29897；**不得**按各档 Sigma EF / N_sim 重算（用户 2026-09-17 20:17 硬约束）
    headline 窗口 = 08-09；另出 07-08 / AM
    Primary   = 收敛窗 it.10–19 逐链路周期均值（与稳定性审计同窗）
    Reference = it.19 单点
评价函数**直接 import 冻结模块（复用而非复制）**：
    compare_final_crosswalk_7_3_6b (SCALE / load_traffic / normalize_crosswalk /
                                     load_linkstats / calc_method / WINDOWS)
    evaluate_calibration_7_4_2      (TRAFFIC / FINAL_CW / backtest_one / summarize)
    diagnose_od_spatial_structure_7_6c (load_all / wmean / 7.6C 产物)
    audit_anomaly_trace_7_6c_1      (directional_repair -> BEST_DIRECTION 口径)
    evaluate_demand_scale_7_6f_0    (build_cycle_linkstats / iter_linkstats)

★ 窗口辨析（易错）
----------------
稳定性审计的 Q / Qbar_10:19 用 **Σ HRS0-24avg**（0–24 全天箱；由 6.3.3A「全部 08:00
出发」决定其≈AM 脉冲）；Sim/Obs 用 **HRS8-9avg**。两者**不混用**。

三口径（同函数形式，**不可混用**；仅 FROZEN 是正式靶场）
------------------------------------------------------
    FROZEN         全 576 池化                     —— 正式主靶场（不得擅改）
    POSITIVE_ONLY  仅 sim>0 池化                   —— 敏感性口径（**不得升格**）
    BEST_DIRECTION max(median(fwd f89), median(rev f89)) x SCALE —— 误差边界（**不得升格**）

断点/增量
--------
本脚本可**在任何时刻**运行：只评价「linkstats 已齐（it.0–19）」的 run。
若网格 run 未齐，输出 `status = AWAITING_RUNS` 并列出缺失项，仍然：
  * 复算 R01 锚点；
  * 与 7.6C-2 已公布的三口径逐位对账（**口径未漂移的硬证据**）。

用法
----
    python scripts/od/evaluate_demand_response_7_6f_1.py
    python scripts/od/evaluate_demand_response_7_6f_1.py --runs R01 F05
    python scripts/od/evaluate_demand_response_7_6f_1.py --force-cycle
"""
from __future__ import annotations

import argparse
import gzip
import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(r"D:\Luan\2026-05\2_Singapore")
SCRIPTS_OD = ROOT / "scripts" / "od"
sys.path.insert(0, str(SCRIPTS_OD))

import compare_final_crosswalk_7_3_6b as bt            # noqa: E402  冻结 SCALE / 指标口径
import evaluate_calibration_7_4_2 as ev1               # noqa: E402  冻结 TRAFFIC / FINAL_CW / backtest
import diagnose_od_spatial_structure_7_6c as d76        # noqa: E402  7.6C 产物与聚合
import audit_anomaly_trace_7_6c_1 as a761              # noqa: E402  ★ BEST_DIRECTION 口径
import evaluate_demand_scale_7_6f_0 as e7_6f0          # noqa: E402  cycle-mean linkstats 构造

# --------------------------------------------------------------------------
# 路径
# --------------------------------------------------------------------------
F1_ROOT = ROOT / "matsim_demand_7_6f_1"
OUT = F1_ROOT / "audit"
CYCLE_DIR = OUT / "_cycle_linkstats"
R01_ROOT = ROOT / "matsim_routechoice_7_6d"
SEC_GEO_7_6C = d76.OUT_DIR / "section_geography.csv"
AUDIT_CACHE_7_6D = R01_ROOT / "audit" / "routechoice_stability_by_iter.csv"
MATRIX_CSV = F1_ROOT / "demand_response_7_6f_1_matrix.csv"
RUN_MANIFEST = F1_ROOT / "demand_response_7_6f_1_run_manifest.json"
SCALE_FROZEN = 2.29897                     # ★ 全档统一（用户 2026-09-17 20:17 硬约束）

SCALE = float(bt.SCALE)                    # 2.29897
CONV_START, CONV_END = 10, 19
REF_ITER = 19
TOTAL_ITER = 20

# 7.6C-2 已公布量（只读引用，用于对账；不作修改）
TARGET_7_6C_2 = {
    "FROZEN": 0.8589732,
    "POSITIVE_ONLY": 0.9350621,
    "BEST_DIRECTION": 0.8909674,
    "delta_target": 0.076089,
    "delta_target_pp": 7.609,
    "fstar_low": 1.06945,
    "fstar_high": 1.16418,
    "snr_coarse_0p10": 1.056,
    "snr_fine_0p05": 0.528,
    "verdict": "TARGET_MARGINAL_COARSE_ONLY",
}
ANCHOR_R01_SIMOBS = 0.8589732              # 7.6F-0 正式 demand=1.00 参照

# 预注册门槛（与 7.6D-S / 7.6E 一致）
TH = {"MATCHED": 0.030, "CATA": 0.030, "SLIP": 0.050}
MONO_TOL = 0.005                            # 单调性容差 ±0.5%

# --------------------------------------------------------------------------
# run 表（全部 SCALE = 2.29897；唯一变量 = f_demand）
# --------------------------------------------------------------------------
RUNS = [
    {"label": "R01", "role": "anchor_f1.00", "f_demand": 1.00, "N": 200_000,
     "out_dir": R01_ROOT / "outputs" / "R01_rc_min", "run_id": "R01_rc_min",
     "stage": "7.6E/7.6F-0", "desc": "稳定底座 demand=1.00 锚点"},
    {"label": "F05", "role": "grid", "f_demand": 1.05, "N": 210_000,
     "out_dir": F1_ROOT / "outputs" / "F05_rc_min", "run_id": "F05_rc_min",
     "stage": "7.6F-1", "desc": "f=1.05（f* 区间下方）"},
    {"label": "F15", "role": "grid", "f_demand": 1.15, "N": 230_000,
     "out_dir": F1_ROOT / "outputs" / "F15_rc_min", "run_id": "F15_rc_min",
     "stage": "7.6F-1", "desc": "f=1.15（f* 区间内部附近）"},
    {"label": "F25", "role": "grid", "f_demand": 1.25, "N": 250_000,
     "out_dir": F1_ROOT / "outputs" / "F25_rc_min", "run_id": "F25_rc_min",
     "stage": "7.6F-1", "desc": "f=1.25（f* 区间上方）"},
]
GRID_LABELS = ["F05", "F15", "F25"]

_ck: list[dict] = []


def ck(name: str, ok: bool, detail: str = "") -> bool:
    _ck.append({"check": name, "pass": bool(ok), "detail": str(detail)})
    print(f"   [{'PASS' if ok else 'FAIL'}] {name}  {detail}")
    return bool(ok)


def log(msg: str = "") -> None:
    print(msg)


def banner(msg: str) -> None:
    print("\n" + "=" * 84)
    print(msg)
    print("=" * 84)


# --------------------------------------------------------------------------
# ★ SCALE 冻结审计（用户 2026-09-17 20:17 硬约束）
# --------------------------------------------------------------------------
def scale_audit() -> pd.DataFrame:
    """披露「若按各档 Sigma EF / N_sim 重算 SCALE 会得到什么」，但**一律采用 2.29897**。

    用户硬约束：**不得**根据 F05/F15/F25 的 `Sigma EF` 重新计算 SCALE；
    三档统一使用冻结基准 `SCALE = 2.29897`。否则会把「增加真实车辆数」与
    「改变扩展权重」混成两个不同的 demand 操作。

    只读 `demand_response_7_6f_1_matrix.csv`（配置阶段实测的 persons / Sigma EF）。
    """
    rows = [{
        "run": "R01", "f_demand": 1.00, "n_agents": 200_000,
        "sum_expansion_factor": 459_794.0,
        "scale_used": SCALE_FROZEN,
        "scale_if_recomputed_sumEF_over_N": 459_794.0 / 200_000,
        "scale_recompute_delta_ppm": (459_794.0 / 200_000 - SCALE_FROZEN) / SCALE_FROZEN * 1e6,
        "adopted": "FROZEN_CONST",
        "rule": "SCALE = 459794/200000 = 2.29897 for ALL runs; sum_EF/N MUST NOT be used",
    }]
    if MATRIX_CSV.exists():
        m = pd.read_csv(MATRIX_CSV, encoding="utf-8-sig")
        for _i, r in m.iterrows():
            s_ef = float(r["sum_expansion_factor"])
            n = int(r["n_agents"])
            rec = s_ef / n
            rows.append({
                "run": str(r["experiment_id"]), "f_demand": float(r["f_demand_nominal"]),
                "n_agents": n, "sum_expansion_factor": s_ef,
                "f_realized": float(r["f_realized"]),
                "scale_used": SCALE_FROZEN,
                "scale_if_recomputed_sumEF_over_N": rec,
                "scale_recompute_delta_ppm": (rec - SCALE_FROZEN) / SCALE_FROZEN * 1e6,
                "adopted": "FROZEN_CONST",
                "rule": "SCALE = 459794/200000 = 2.29897 for ALL runs; sum_EF/N MUST NOT be used",
            })
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------
# 基础量
# --------------------------------------------------------------------------
def pooled(df: pd.DataFrame, sim: str = "sim_8_9_scaled",
           obs: str = "obs_8_9") -> float:
    """池化（obs 加权）Sim/Obs —— 所有口径使用同一函数形式。"""
    o = float(df[obs].sum())
    return float(df[sim].sum() / o) if o > 0 else float("nan")


def n_complete_iters(run: dict) -> int:
    return sum(1 for it in range(TOTAL_ITER)
               if e7_6f0.iter_linkstats(run["out_dir"], run["run_id"], it))


def load_ls_dict(path: Path) -> dict:
    """{link_id: (f78, f89, f24)} —— 与 a761 / d76 的 ls 语义一致。"""
    out: dict[str, tuple] = {}
    with gzip.open(str(path), "rt", encoding="utf-8", errors="replace") as fh:
        hdr = fh.readline().rstrip("\n").split("\t")
        assert hdr[:4] == ["LINK", "HRS7-8avg", "HRS8-9avg", "HRS0-24avg"], hdr[:4]
        for line in fh:
            p = line.rstrip("\n").split("\t")
            if len(p) >= 4:
                try:
                    out[p[0]] = (float(p[1]), float(p[2]), float(p[3]))
                except ValueError:
                    pass
    return out


def q_series_multi(run: dict, sets: dict, col: str = "HRS0-24avg") -> dict:
    """逐迭代 Σ(col | link_set) —— **每个 linkstats 文件只读一次**，同时算全部集合。

    sets: {name: link_set or None}；None 表示全网（ALL）。
    （早先按集合分别读 20 次的写法会把 I/O 放大 4 倍，已改成单遍多集合。）
    """
    out: dict[str, list[float]] = {k: [] for k in sets}
    for it in range(TOTAL_ITER):
        p = e7_6f0.iter_linkstats(run["out_dir"], run["run_id"], it)
        if p is None:
            for k in out:
                out[k].append(float("nan"))
            continue
        df = pd.read_csv(p, sep="\t", compression="gzip",
                         usecols=["LINK", col], low_memory=False)
        df["LINK"] = df["LINK"].astype(str).str.strip()
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)
        s = df.groupby("LINK")[col].sum()
        total = float(s.sum())
        for k, ls in sets.items():
            out[k].append(total if ls is None
                          else float(s.reindex(list(ls)).fillna(0.0).sum()))
    return out


def a_10_19(ser: list[float]) -> float:
    v = np.array([x for x in ser[CONV_START:CONV_END + 1] if np.isfinite(x)], float)
    if v.size == 0 or v.mean() == 0:
        return float("nan")
    return float((v.max() - v.min()) / v.mean())


def qbar_10_19(ser: list[float]) -> float:
    v = np.array([x for x in ser[CONV_START:CONV_END + 1] if np.isfinite(x)], float)
    return float(v.mean()) if v.size else float("nan")


def parity_gap_rel(ser: list[float]) -> float:
    v = np.array([x for x in ser[CONV_START:CONV_END + 1] if np.isfinite(x)], float)
    if v.size < 2 or v.mean() == 0:
        return float("nan")
    even = v[0::2].mean()
    odd = v[1::2].mean()
    return float(abs(even - odd) / v.mean())


# --------------------------------------------------------------------------
# 每 run：三口径 + 稳定性 + 空间残差
# --------------------------------------------------------------------------
def eval_run(run: dict, cw: pd.DataFrame, cw_prim: pd.DataFrame, obs: pd.DataFrame,
             geo: pd.DataFrame, matched: set, cata: set, slip: set, *,
             force_cycle: bool) -> dict:
    banner(f"run {run['label']}  f_demand={run['f_demand']:.2f}  "
           f"N={run['N']:,}  ({run['stage']})")

    dest = CYCLE_DIR / f"{run['label']}_conv.linkstats.txt.gz"
    cycle_ls, n_used = e7_6f0.build_cycle_linkstats(
        run, list(range(CONV_START, CONV_END + 1)), dest, force=force_cycle)
    log(f"cycle-mean linkstats over {n_used} iters -> {dest.name}")

    # ---- Primary（收敛窗周期均值） ---------------------------------------
    sec = ev1.backtest_one(f"{run['label']}|cycle", cw.copy(), obs, cycle_ls)
    if sec.empty:
        raise RuntimeError(f"{run['label']}: empty backtest")
    sec["run"] = run["label"]
    sec["lta_linkid"] = sec["lta_linkid"].astype(str).str.strip()
    sec = sec.merge(geo, on="lta_linkid", how="left")
    n_geo = int(sec["region"].notna().sum())

    lsdict = load_ls_dict(cycle_ls)

    # ---- Reference（it.19 单点） ----------------------------------------
    p19 = e7_6f0.iter_linkstats(run["out_dir"], run["run_id"], REF_ITER)
    sec19 = ev1.backtest_one(f"{run['label']}|it19", cw.copy(), obs, p19) \
        if p19 is not None else pd.DataFrame()
    if not sec19.empty:
        sec19["run"] = run["label"]

    # ---- 三口径 ----------------------------------------------------------
    sub = sec.copy()
    sub["zero_sim"] = sub["sim_8_9_scaled"] <= 0
    q = {}
    q["FROZEN"] = pooled(sub)
    q["POSITIVE_ONLY"] = pooled(sub[~sub["zero_sim"]])
    dirfix_raw = a761.directional_repair({"cw_prim": cw_prim, "ls": lsdict}, sub)
    # 7.6C-1 的 directional_repair 以 int(lta_linkid) 为键；此处统一为 str 后再映射，
    # 否则 str 值 ↔ int 键失配 → 全部 NaN（静默退化）。口径与 7.6C-2 完全一致。
    dirfix = {str(k): v for k, v in dirfix_raw.items()}
    s2 = sub.copy()
    s2["sim_dirfix"] = s2["lta_linkid"].map(dirfix)
    n_nodir = int(s2["sim_dirfix"].isna().sum())
    s2["sim_dirfix"] = s2["sim_dirfix"].fillna(s2["sim_8_9_scaled"])
    q["BEST_DIRECTION"] = pooled(s2, sim="sim_dirfix")
    q["FROZEN_WMEAN_OF_RATIOS"] = float(d76.wmean(sub["ratio_8_9"], sub["obs_8_9"]))
    q_19 = {"FROZEN": pooled(sec19)} if not sec19.empty else {"FROZEN": float("nan")}

    log(f"三口径（08-09, PRIMARY cycle）: "
        f"FROZEN={q['FROZEN']:.7f}  POSITIVE_ONLY={q['POSITIVE_ONLY']:.7f}  "
        f"BEST_DIRECTION={q['BEST_DIRECTION']:.7f}")
    log(f"  sections={len(sub)}  零流={int(sub['zero_sim'].sum())}  "
        f"方向修复={len(sub)-n_nodir}/{len(sub)}  geography={n_geo}/{len(sub)}")

    # ---- 稳定性（Σ HRS0-24avg，与 7.6B/7.6D/7.6E 同口径） ----------------
    series = q_series_multi(run, {"MATCHED": matched, "CATA": cata,
                                  "SLIP": slip, "ALL": None})
    stab = {}
    for kind, ser in series.items():
        stab[kind] = {"A_10_19": a_10_19(ser), "Qbar_10_19": qbar_10_19(ser),
                      "Q_19": ser[REF_ITER] if np.isfinite(ser[REF_ITER]) else float("nan"),
                      "parity_gap_rel": parity_gap_rel(ser),
                      "series": ser}
    log(f"稳定性 A_10:19（ΣHRS0-24avg）: MATCHED={stab['MATCHED']['A_10_19']:.4%}  "
        f"CATA={stab['CATA']['A_10_19']:.4%}  SLIP={stab['SLIP']['A_10_19']:.4%}  "
        f"ALL={stab['ALL']['A_10_19']:.4%}")

    # ---- 空间残差（region / radial；**只报告，不调参**） -----------------
    spac = []
    for key in ("region", "radial"):
        for k, x in sub.dropna(subset=[key]).groupby(key):
            xp = x[~x["zero_sim"]]
            spac.append({"run": run["label"], "group_by": key, "group": k,
                         "n_sections": int(len(x)),
                         "n_zero_sim": int(x["zero_sim"].sum()),
                         "Q_FROZEN": pooled(x),
                         "Q_POSITIVE_ONLY": pooled(xp),
                         "rel_dev_vs_global_FROZEN": pooled(x) / q["FROZEN"] - 1.0,
                         "rel_dev_vs_global_POS": (
                             (pooled(xp) / q["POSITIVE_ONLY"] - 1.0)
                             if np.isfinite(q["POSITIVE_ONLY"]) else float("nan"))})
    spac = pd.DataFrame(spac)

    return {"run": run, "sec": sub, "sec19": sec19, "s2": s2, "q": q, "q_19": q_19,
            "stab": stab, "spatial": spac, "n_geo": n_geo,
            "n_zero_sim": int(sub["zero_sim"].sum()),
            "n_dirfix": len(sub) - n_nodir, "cycle_ls": str(cycle_ls)}


# --------------------------------------------------------------------------
# main
# --------------------------------------------------------------------------
def main() -> int:
    global OUT, CYCLE_DIR
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", nargs="*", default=[r["label"] for r in RUNS])
    ap.add_argument("--force-cycle", action="store_true")
    ap.add_argument("--out-dir", type=Path, default=OUT)
    args = ap.parse_args()

    OUT = args.out_dir
    CYCLE_DIR = OUT / "_cycle_linkstats"
    OUT.mkdir(parents=True, exist_ok=True)

    banner("Step 7.6F-1 — 稳定底座上的粗档 demand-response 曲线（零仿真、只读）")
    t0 = time.time()

    # ---- [0] 前置 --------------------------------------------------------
    log("[0/6] 前置核验")
    ck("P1 SCALE == 2.29897（复制机制下恒定）", abs(SCALE - 2.29897) < 1e-9, f"{SCALE:.5f}")

    # ★ P1b：SCALE 冻结审计（不得按各档 ΣEF/N_sim 重算）
    sa = scale_audit()
    sa.to_csv(OUT / "demand_response_7_6f_1_scale_audit.csv", index=False, encoding="utf-8-sig")
    _uniform = bool(len(sa) and (sa["scale_used"] - SCALE_FROZEN).abs().max() < 1e-12
                    and abs(SCALE - SCALE_FROZEN) < 1e-9)
    _detail = (f"n_runs={len(sa)}  max|delta_ppm|={sa['scale_recompute_delta_ppm'].abs().max():.2f}"
               if len(sa) else "n/a")
    ck("P1b SCALE 全档统一 = 2.29897（★不按 ΣEF/N 重算；ΣEF 仅作披露）", _uniform, _detail)
    log(sa[["run", "f_demand", "n_agents", "sum_expansion_factor", "scale_used",
            "scale_if_recomputed_sumEF_over_N", "scale_recompute_delta_ppm"]]
        .to_string(index=False, float_format=lambda v: f"{v:.6f}"))
    log("   ↑ scale_if_recomputed 仅作披露，**一律 NOT USED**；三档统一 2.29897")
    if RUN_MANIFEST.exists():
        try:
            mf = json.loads(RUN_MANIFEST.read_text(encoding="utf-8"))
            ck("P1c run manifest 记录的 SCALE 亦为 2.29897",
               abs(float(mf.get("scale_frozen_for_all_runs", -1)) - SCALE_FROZEN) < 1e-12,
               f"{mf.get('scale_frozen_for_all_runs')}  status={mf.get('status')}")
        except Exception as exc:   # noqa: BLE001
            ck("P1c run manifest 可解析", False, f"{type(exc).__name__}: {exc}")

    ck("P2 7.3.6A Final Crosswalk 存在", ev1.FINAL_CW.exists(), ev1.FINAL_CW.name)
    ck("P3 7.1 冻结观测存在", ev1.TRAFFIC.exists(), ev1.TRAFFIC.name)
    ck("P4 7.6C section_geography 存在", SEC_GEO_7_6C.exists(), SEC_GEO_7_6C.name)

    avail, missing = {}, []
    for r in RUNS:
        n = n_complete_iters(r)
        avail[r["label"]] = n
        if n < TOTAL_ITER:
            missing.append((r["label"], n))
    log("   linkstats 完备度：" +
        "  ".join(f"{k}={v}/{TOTAL_ITER}" for k, v in avail.items()))
    grid_missing = [lab for lab, n in missing if lab in GRID_LABELS]
    awaiting = bool(grid_missing)
    if awaiting:
        log(f"   [AWAITING_RUNS] 网格档未齐：{grid_missing} —— "
            f"本次只评价已齐 run，并照常复算 R01 锚点与 7.6C-2 对账。")

    # ---- [1] 冻结件 ------------------------------------------------------
    log("\n[1/6] 载入 7.1 观测 + 7.3.6A crosswalk + 7.6C 地理")
    obs = bt.load_traffic(ev1.TRAFFIC)
    cw = bt.normalize_crosswalk(ev1.FINAL_CW, "final")
    cwraw = pd.read_csv(ev1.FINAL_CW, encoding="utf-8-sig")
    cwraw["matsim_link_id"] = cwraw["matsim_link_id"].astype(str).str.strip()
    cw_prim = cwraw[cwraw["is_primary_candidate"]].copy() \
        if "is_primary_candidate" in cwraw.columns else cwraw.copy()

    matched = set(cwraw["matsim_link_id"])
    cata = set(cwraw.loc[cwraw["RoadCat"] == "CATA", "matsim_link_id"])
    slip = set(cwraw.loc[cwraw["RoadCat"] == "SLIP_ROAD", "matsim_link_id"])
    log(f"      observed sections = {obs['LinkID'].nunique():,}   "
        f"crosswalk rows = {len(cwraw):,}   sections = {cwraw['lta_linkid'].nunique()}")
    log(f"      link sets: MATCHED={len(matched):,}  CATA={len(cata):,}  "
        f"SLIP={len(slip):,}  (CATA+SLIP={len(cata)+len(slip):,})")
    ck("P5 CATA + SLIP == MATCHED（口径分区完整）",
       len(cata) + len(slip) == len(matched), f"{len(cata)}+{len(slip)} vs {len(matched)}")

    geo = pd.read_csv(SEC_GEO_7_6C)[["lta_linkid", "mid_x", "mid_y", "d_cbd_m",
                                     "n_links", "radial", "ring", "region", "pa"]]
    # section_geography.csv 的 lta_linkid 以 int64 落盘；断面统计以 str 落盘 ⇒ 统一为 str，
    # 否则 merge 抛 ValueError（str vs int64）。此归一化不改变任何数值口径。
    geo["lta_linkid"] = geo["lta_linkid"].astype(str).str.strip()
    ck("P6 section_geography 覆盖 >= 570/576", int(geo["region"].notna().sum()) >= 570,
       f"{int(geo['region'].notna().sum())}/{len(geo)}")

    # ---- [2] 逐 run ------------------------------------------------------
    sel = [r for r in RUNS if r["label"] in args.runs and avail[r["label"]] == TOTAL_ITER]
    if not sel:
        log("\n没有可评价的 run（linkstats 未齐）。终止。")
        (OUT / "od_demand_response_7_6f_1_summary.json").write_text(
            json.dumps({"step": "7.6F-1", "status": "AWAITING_RUNS",
                        "linkstats_availability": avail,
                        "missing": missing, "zero_simulation": True,
                        "matsim_rerun": False}, ensure_ascii=False, indent=2),
            encoding="utf-8")
        return 2

    log(f"\n[2/6] 逐 run 评价（{len(sel)} 档）")
    res = {}
    for r in sel:
        res[r["label"]] = eval_run(r, cw, cw_prim, obs, geo, matched, cata, slip,
                                   force_cycle=args.force_cycle)

    # ---- [2b] ★ 与 7.6C-2 对账（口径未漂移的硬证据） ---------------------
    log("\n[2b/6] ★ 与 7.6C-2 已公布三口径逐位对账（R01）")
    xr = []
    if "R01" in res:
        q0 = res["R01"]["q"]
        for k in ["FROZEN", "POSITIVE_ONLY", "BEST_DIRECTION"]:
            mine, pub = q0[k], TARGET_7_6C_2[k]
            xr.append({"quantity": f"Q_{k}(R01)", "recomputed": mine,
                       "published_7_6c_2": pub, "abs_diff": abs(mine - pub),
                       "tol": 1e-6, "match": abs(mine - pub) <= 1e-6})
        for c in xr:
            ck(f"C1.{c['quantity']} 复现 7.6C-2", c["match"],
               f"{c['recomputed']:.7f} vs {c['published_7_6c_2']:.7f}")
    xdf = pd.DataFrame(xr)
    if not xdf.empty:
        xdf.to_csv(OUT / "demand_response_crossvalidation.csv",
                   index=False, encoding="utf-8-sig")

    # 与 7.6D/7.6E 稳定性审计缓存对账
    if AUDIT_CACHE_7_6D.exists() and "R01" in res:
        au = pd.read_csv(AUDIT_CACHE_7_6D, encoding="utf-8-sig")
        z = au[(au["run"] == "R01_rc_min")
               & (au["iteration"].between(CONV_START, CONV_END))]
        for kind, col in (("MATCHED", "MATCHED"), ("ALL", "ALL"),
                          ("CATA", "CATA"), ("SLIP", "SLIP")):
            exp = float(z[col].mean())
            got = res["R01"]["stab"][kind]["Qbar_10_19"]
            ck(f"C2.R01 Qbar_10:19({kind}) == 7.6D 审计缓存", abs(got - exp) / exp < 1e-9,
               f"{got:,.1f} vs {exp:,.1f}")

    # ---- [3] 响应曲线 ----------------------------------------------------
    log("\n[3/6] ★ 响应曲线 f_demand -> Sim/Obs")
    rows = []
    for r in sorted([x for x in RUNS if x["label"] in res], key=lambda d: d["f_demand"]):
        e = res[r["label"]]
        rows.append({
            "run": r["label"], "f_demand": r["f_demand"], "N": r["N"],
            "role": r["role"], "SCALE": SCALE,
            "SimObs_FROZEN": e["q"]["FROZEN"],
            "SimObs_POSITIVE_ONLY": e["q"]["POSITIVE_ONLY"],
            "SimObs_BEST_DIRECTION": e["q"]["BEST_DIRECTION"],
            "SimObs_wmean_of_ratios": e["q"]["FROZEN_WMEAN_OF_RATIOS"],
            "SimObs_FROZEN_it19_ref": e["q_19"]["FROZEN"],
            "Qbar_10_19_MATCHED": e["stab"]["MATCHED"]["Qbar_10_19"],
            "Q_19_MATCHED": e["stab"]["MATCHED"]["Q_19"],
            "A_10_19_MATCHED": e["stab"]["MATCHED"]["A_10_19"],
            "A_10_19_CATA": e["stab"]["CATA"]["A_10_19"],
            "A_10_19_SLIP": e["stab"]["SLIP"]["A_10_19"],
            "A_10_19_ALL": e["stab"]["ALL"]["A_10_19"],
            "parity_gap_MATCHED": e["stab"]["MATCHED"]["parity_gap_rel"],
            "n_zero_sim_sections": e["n_zero_sim"],
            "n_dirfix_sections": e["n_dirfix"],
        })
    curve = pd.DataFrame(rows)
    curve.to_csv(OUT / "demand_response_curve.csv", index=False, encoding="utf-8-sig")
    log(curve[["run", "f_demand", "SimObs_FROZEN", "SimObs_POSITIVE_ONLY",
               "SimObs_BEST_DIRECTION", "A_10_19_MATCHED"]]
        .to_string(index=False, float_format=lambda v: f"{v:.6f}"))

    # ---- [4] 算术参照 + 拥堵阻尼 ----------------------------------------
    log("\n[4/6] 算术参照（零仿真上界）与拥堵阻尼比 rho(f)")
    base = curve[curve["run"] == "R01"]
    arith = pd.DataFrame()
    if not base.empty:
        b = float(base["SimObs_FROZEN"].iloc[0])
        arith = curve[["run", "f_demand", "SimObs_FROZEN"]].copy()
        arith["arith_FROZEN_R01xf"] = b * arith["f_demand"]
        arith["rho"] = arith["SimObs_FROZEN"] / arith["arith_FROZEN_R01xf"]
        arith.to_csv(OUT / "demand_response_arithmetic_reference.csv",
                     index=False, encoding="utf-8-sig")
        log(arith.to_string(index=False, float_format=lambda v: f"{v:.6f}"))

    # ---- [5] 空间残差（G6） ---------------------------------------------
    log("\n[5/6] 空间残差（region / radial）—— **只报告，不得用 demand 压平**")
    sp = pd.concat([res[k]["spatial"] for k in res], ignore_index=True)
    sp.to_csv(OUT / "demand_response_spatial_residuals.csv",
              index=False, encoding="utf-8-sig")
    rr = sp[sp["group_by"].isin(["region", "radial"])]
    log(rr[["run", "group_by", "group", "n_sections", "Q_FROZEN",
            "rel_dev_vs_global_FROZEN"]].to_string(
        index=False, float_format=lambda v: f"{v:.4f}"))

    # ---- [6] 判据与判决 --------------------------------------------------
    log("\n[6/6] 预注册判据 G1–G7")
    grid = curve[curve["run"].isin(GRID_LABELS)]
    # G1 稳定性承继
    g1 = bool(len(grid) == 3 and (
        (grid["A_10_19_MATCHED"] < TH["MATCHED"]).all()
        and (grid["A_10_19_CATA"] < TH["CATA"]).all()
        and (grid["A_10_19_SLIP"] < TH["SLIP"]).all())) if len(grid) else False
    ck("G1 稳定性承继（三档 A_10:19 < 门槛）", g1,
       "MATCHED/CATA<3%, SLIP<5%" if len(grid) else "网格未齐")
    # G2 单调性
    g2, mono_detail = False, "网格未齐"
    if len(curve) >= 3:
        v = curve.sort_values("f_demand")["SimObs_FROZEN"].to_numpy(float)
        diffs = np.diff(v)
        g2 = bool((diffs > -MONO_TOL * v[:-1]).all())
        mono_detail = "  ".join(f"{d:+.5f}" for d in diffs)
    ck("G2 单调性（Sim/Obs(FROZEN) 随 f 单调不减，容差 ±0.5%）", g2, mono_detail)
    # G4 是否跨越 1.000
    crosses = None
    if len(curve) >= 2:
        v = curve.sort_values("f_demand")["SimObs_FROZEN"].to_numpy(float)
        crosses = bool(v.min() <= 1.0 <= v.max())
    ck("G4 曲线跨越 Sim/Obs = 1.000", bool(crosses),
       f"min={curve['SimObs_FROZEN'].min():.6f} max={curve['SimObs_FROZEN'].max():.6f}"
       if len(curve) else "n/a")
    # G5 靶场不确定性并报
    ck("G5 三口径并报（POSITIVE_ONLY / BEST_DIRECTION 不得升格）",
       all(k in curve.columns for k in ["SimObs_POSITIVE_ONLY", "SimObs_BEST_DIRECTION"]),
       f"Delta_target={TARGET_7_6C_2['delta_target_pp']:.3f} pp（承自 7.6C-2）")
    # G6 空间残差报告
    ck("G6 空间残差已报告（EAST / radial_in）",
       bool(len(rr)), f"{len(rr)} 行（region+radial）")
    # G7 双口径
    ck("G7 双口径并报（Qbar_10:19 + Q_19）",
       {"Qbar_10_19_MATCHED", "Q_19_MATCHED"} <= set(curve.columns), "ok")

    if awaiting:
        vdict = "AWAITING_RUNS"
    elif not g1:
        vdict = "RESPONSE_UNSTABLE"
    elif not g2:
        vdict = "RESPONSE_NON_MONOTONIC"
    elif crosses:
        vdict = "RESPONSE_STABLE_CROSSES"
    else:
        vdict = "RESPONSE_STABLE_PARTIAL"
    log(f"\n★ 判决：**{vdict}**")

    # ---- 落盘 ------------------------------------------------------------
    npass = sum(1 for c in _ck if c["pass"])
    summary = {
        "step": "7.6F-1",
        "title": "Coarse demand-response curve on the stabilized assignment base",
        "status": vdict,
        "zero_simulation": True, "matsim_rerun": False, "parameters_changed": False,
        "lambda_selected": False, "demand_scale_selected": False,
        "checks_pass": npass, "checks_total": len(_ck), "checks": _ck,
        "linkstats_availability": avail, "missing": missing,
        "runs_evaluated": sorted(res),
        "scale": SCALE,
        "scale_frozen_for_all_runs": SCALE_FROZEN,
        "scale_rule": "SCALE = 459794/200000 = 2.29897 for ALL runs; sum_EF/N MUST NOT be used",
        "scale_audit": sa.to_dict("records"),
        "caliber": {
            "primary_target": "FROZEN (576 pooled, 7.3.6A) -- MUST NOT be replaced",
            "not_promoted": ["POSITIVE_ONLY", "BEST_DIRECTION"],
            "primary_metric": "MATCHED Sim/Obs(08-09)",
            "headline_window": "08-09", "windows": ["07-08", "08-09", "AM"],
            "scale_rule": "SCALE = 459794/200000 = 2.29897 (constant under replication)",
            "frozen_lineage": "bt / ev1 / d76 / a761 / e7_6f0 imported, not copied",
        },
        "target_reference_7_6c_2": TARGET_7_6C_2,
        "crossvalidation_7_6c_2": xr,
        "response_curve": rows,
        "arithmetic_reference": arith.to_dict("records") if not arith.empty else [],
        "spatial_residuals_rows": int(len(rr)),
        "preregistered": {"G1_stability": g1, "G2_monotonicity": g2,
                          "G4_crosses_1.0": crosses, "thresholds": TH,
                          "mono_tol": MONO_TOL},
        "runtime_sec": round(time.time() - t0, 1),
        "explicitly_not_doing": [
            "不选 demand scale", "不评价 lambda", "不评价 OD 空间结构",
            "不把 POSITIVE_ONLY / BEST_DIRECTION 升格为正式靶场",
            "不修改 7.3.6A crosswalk", "不用 0.9351/1.1642 反推 demand scale",
            "不用调 demand 压平 EAST / radial_in",
        ],
    }
    (OUT / "od_demand_response_7_6f_1_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, default=str), encoding="utf-8")

    # ---------------- REPORT ----------------
    def f6(v):
        return "n/a" if v is None or (isinstance(v, float) and pd.isna(v)) else f"{float(v):.6f}"

    def fp(v):
        return "n/a" if v is None or (isinstance(v, float) and pd.isna(v)) else f"{float(v):+.4%}"

    L = []
    L.append("# Step 7.6F-1 — 稳定分配底座上的粗档 demand-response 曲线\n")
    L.append("## Status\n")
    L.append(f"**{vdict}**（零仿真；只读既有 linkstats；**未启动 MATSim、未改任何参数**；"
             f"校验 {npass}/{len(_ck)}）\n")
    if awaiting:
        L.append(f"> ⏸️ **AWAITING_RUNS**：网格档 `{grid_missing}` 的 linkstats 未齐 —— "
                 f"本节仅含已完成的 run，R01 锚点与 7.6C-2 对账**已执行**。\n")
    L.append("> **唯一变量** = `f_demand`；采样基准 `N`=200,000 与 `f_cap`=1.00 冻结；")
    L.append("> `SCALE = 2.29897` **恒定**（复制机制下平均 EF 不变）；"
             "route-choice 继承 7.6E 冻结。\n")

    L.append("## 1. ★ 响应曲线 `f_demand -> Sim/Obs`（MATCHED，08-09）\n")
    L.append("| run | f_demand | N | Sim/Obs **FROZEN**(主靶场) | POSITIVE_ONLY | BEST_DIRECTION | "
             "Reference (it.19) | `Q̄_10:19`(MATCHED) | `A_10:19`(MATCHED) |")
    L.append("|---|---:|---:|---:|---:|---:|---:|---:|---:|")
    for r in rows:
        L.append(f"| {r['run']} | {r['f_demand']:.2f} | {r['N']:,} | "
                 f"**{f6(r['SimObs_FROZEN'])}** | {f6(r['SimObs_POSITIVE_ONLY'])} | "
                 f"{f6(r['SimObs_BEST_DIRECTION'])} | {f6(r['SimObs_FROZEN_it19_ref'])} | "
                 f"{r['Qbar_10_19_MATCHED']:,.1f} | {r['A_10_19_MATCHED']:.4%} |")
    L.append("")
    L.append(f"> 主靶场 `FROZEN` = **{TARGET_7_6C_2['FROZEN']:.7f}**（7.3.6A，**不得擅改**）；")
    L.append(f"> `Delta_target` = **{TARGET_7_6C_2['delta_target_pp']:.3f} pp**；"
             f"`f*` 区间 = **[{TARGET_7_6C_2['fstar_low']:.5f}, {TARGET_7_6C_2['fstar_high']:.5f}]**。")
    L.append("> **POSITIVE_ONLY / BEST_DIRECTION 不得升格为正式靶场。**\n")

    L.append("## 2. 稳定性承继（Σ HRS0-24avg，与 7.6B/7.6D/7.6E 同口径）\n")
    L.append("| run | `A_10:19` MATCHED | CATA | SLIP | ALL | `parity_gap_rel`(MATCHED) | 门槛 |")
    L.append("|---|---:|---:|---:|---:|---:|---|")
    for r in rows:
        L.append(f"| {r['run']} | {r['A_10_19_MATCHED']:.4%} | {r['A_10_19_CATA']:.4%} | "
                 f"{r['A_10_19_SLIP']:.4%} | {r['A_10_19_ALL']:.4%} | "
                 f"{r['parity_gap_MATCHED']:.4%} | MATCHED/CATA<3%, SLIP<5% |")
    L.append("")

    L.append("## 3. 算术参照（零仿真上界）与拥堵阻尼比 ρ(f)\n")
    if not arith.empty:
        L.append("| run | f_demand | 实测 Sim/Obs(FROZEN) | 算术 `R01×f` | ρ = 实测/算术 |")
        L.append("|---|---:|---:|---:|---:|")
        for r in arith.to_dict("records"):
            L.append(f"| {r['run']} | {r['f_demand']:.2f} | {f6(r['SimObs_FROZEN'])} | "
                     f"{f6(r['arith_FROZEN_R01xf'])} | {f6(r['rho'])} |")
        L.append("")
        L.append("> ρ ≈ 1 ⇒ 网络未饱和（纯量级问题）；ρ < 1 ⇒ 加车被拥堵吸收。")
        L.append("> **不设阈值**（7.6C-2 已判只能粗档识别）。\n")

    L.append("## 4. 空间残差（EAST / `radial_in`）—— **只报告，不得用 demand 压平**\n")
    if len(rr):
        L.append("| run | 分组 | 组 | sections | `Q_FROZEN` | 相对全局偏差 |")
        L.append("|---|---|---|---:|---:|---:|")
        for r in rr.to_dict("records"):
            L.append(f"| {r['run']} | {r['group_by']} | {r['group']} | {r['n_sections']} | "
                     f"{f6(r['Q_FROZEN'])} | {fp(r['rel_dev_vs_global_FROZEN'])} |")
        L.append("")
        L.append("> 7.6C/7.6C-1 已登记：EAST 与 `radial_in` 存在**真实**残余低估；"
                 "本步**不得**通过调 `f_demand` 使其趋于 1。\n")

    L.append("## 5. 判据与判决\n")
    L.append("| # | 判据 | 结果 |")
    L.append("|---|---|---|")
    L.append(f"| G1 | 稳定性承继（三档 `A_10:19` 达标） | **{'PASS' if g1 else 'FAIL'}** |")
    L.append(f"| G2 | 单调性（容差 ±0.5%） | **{'PASS' if g2 else 'FAIL'}** |")
    L.append(f"| G4 | 曲线跨越 1.000 | {'是' if crosses else '否'} |")
    L.append(f"| G5 | 三口径并报（不升格） | PASS |")
    L.append(f"| G6 | 空间残差已报告 | PASS |")
    L.append(f"| G7 | 双口径并报 | PASS |")
    L.append("")
    L.append(f"**判决：`{vdict}`**\n")

    L.append("## 6. 口径与纪律\n")
    L.append("- 观测：7.1 冻结（工作日 → 日内均值 → `LinkID × hour` 日中位；hour = 7,8）。")
    L.append("- 仿真：`median(匹配 MATSim 有向边 HRSx-yavg) × SCALE`，**`SCALE = 459794/200000 = 2.29897`**"
             "（复制机制下恒定，**与 N 无关**）。")
    L.append(f"- Primary = 收敛窗 it.{CONV_START}–{CONV_END} **逐链路周期均值**；"
             f"Reference = it.{REF_ITER} 单点。")
    L.append("- 评价函数 **import** 自 `compare_final_crosswalk_7_3_6b` / "
             "`evaluate_calibration_7_4_2` / `audit_anomaly_trace_7_6c_1`"
             "（冻结模块），口径逐字节同源。")
    L.append("- 窗口辨析：稳定性审计的 `Q` 用 **Σ HRS0-24avg**，Sim/Obs 用 **HRS8-9avg** —— **不混用**。")
    L.append("- **未改动** 7.1 / 7.3.6A / OD / network / capacity / population / route-choice 任何冻结件。\n")
    L.append("---\n")
    L.append(f"校验：{npass}/{len(_ck)} PASS   运行 {summary['runtime_sec']} s   "
             f"产物目录：`{OUT}`\n")
    (OUT / "STEP7_6F_1_REPORT.md").write_text("\n".join(L), encoding="utf-8")

    banner(f"完成：{vdict}   校验 {npass}/{len(_ck)}   用时 {summary['runtime_sec']} s")
    print(f"产物 -> {OUT}")
    return 0 if npass == len(_ck) else 2


if __name__ == "__main__":
    raise SystemExit(main())
