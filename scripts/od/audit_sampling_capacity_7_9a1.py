#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""
audit_sampling_capacity_7_9a1.py — Step 7.9A-1 评价器（零仿真 / 只读）

判据来源：reports/sampling_capacity_7_9a1/PREREG_7_9A1.md（运行前冻结，sha256 de15361a…）
  §4  四动态指标（① 拥堵链路数 ② v/c>=1 链路数 ③ 形成—消散时间过程 ④ 拥堵空间位置）
  §5  三层判据（流量护栏 / 拥堵形成 / 数值稳定性）
  §6  零仿真先验（A-0 上界投影，仅作预期）
  §7  四种结果读法 A/B/C/D
  §9  必需产物        §10 判决闭集        §11 v/c 分母消解规则     §12 明确排除

★统一仪器原则（PREREG §4.0）：A-1 与 v1.0 的**全部**动态指标用**同一段代码、同一口径**计算
  ⇒ 判据全部**相对**（A-1 vs v1.0），不依赖事后挑选的绝对阈值。

★口径决议（本评价器记录；**不改预注册文件**，sha 保持 de15361a…）
  E04：预注册 §4.1 正文写 `excess_s >= 1.0 s`，但其登记基线 `N_cong = 7,985 / 3.56 %` 只能由
       `excess_s > 0` 复现（实测 `>=1.0 s` 为 **1,308**）。⇒ 二者**同时报出**：
         `N_cong`      = `excess_s > 0`（**主**，= 预注册登记基线 7,985）
         `N_cong_ge1s` = `excess_s >= 1.0`（**辅**，= 1,308）
       两项在 A-1 与 v1.0 上**同口径**计算，故全部**相对**判据不受影响。

★冻结护栏口径**直接 import 冻结模块** `evaluate_demand_response_7_6f_1.eval_run`
  （复用而非复制；与 `analyze_kw_7_9b1.py : L0` 同源），并内建自校验 `FROZEN(v1.0) == 0.9993347697`。

用法
----
    python scripts/od/audit_sampling_capacity_7_9a1.py --check-v10            # v1.0 侧口径自检（快）
    python scripts/od/audit_sampling_capacity_7_9a1.py --check-v10 --guardrail # 含冻结模块护栏复算
    python scripts/od/audit_sampling_capacity_7_9a1.py --no-events            # 跳过 events（中）
    python scripts/od/audit_sampling_capacity_7_9a1.py                        # 完整评价（需 A-1 产物）
"""
from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
import math
import sys
import time
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(r"D:\Luan\2026-05\2_Singapore")
SCRIPTS_OD = ROOT / "scripts" / "od"
sys.path.insert(0, str(SCRIPTS_OD))

import compare_final_crosswalk_7_3_6b as bt          # noqa: E402
import evaluate_calibration_7_4_2 as ev1             # noqa: E402
import diagnose_od_spatial_structure_7_6c as d76     # noqa: E402
import evaluate_demand_response_7_6f_1 as E          # noqa: E402  ★ 冻结护栏口径（复用）

# --------------------------------------------------------------------------
# 路径
# --------------------------------------------------------------------------
OUT = ROOT / "reports" / "sampling_capacity_7_9a1"
OUT.mkdir(parents=True, exist_ok=True)
REPORT_ROOT = OUT          # ★报告根（dry-run 时 OUT 会指向沙盒，本常量**不随之改变**，用于产物存在性断言）
CYCLE_DIR = OUT / "_cycle_linkstats"
CYCLE_DIR.mkdir(parents=True, exist_ok=True)

# v1.0（冻结，只读）
V10_RUN = "W01_rc_min"
V10_OUT = ROOT / "matsim_final_7_6h" / "outputs" / V10_RUN
V10_LS = V10_OUT / "ITERS" / "it.19" / f"{V10_RUN}.19.linkstats.txt.gz"
V10_LH = V10_OUT / "ITERS" / "it.19" / f"{V10_RUN}.19.legHistogram.txt"
V10_EV = (ROOT / "matsim_viz_7_8" / "outputs" / "W01_events" / "ITERS" / "it.19"
          / "W01_events.19.events.xml.gz")

# A-1（本步运行）
A1_ROOT = ROOT / "matsim_sampling_capacity_7_9a1"
A1_RUN = "A1_capf0p435"
A1_OUT = A1_ROOT / "outputs" / A1_RUN
A1_LS = A1_OUT / "ITERS" / "it.19" / f"{A1_RUN}.19.linkstats.txt.gz"
A1_LH = A1_OUT / "ITERS" / "it.19" / f"{A1_RUN}.19.legHistogram.txt"
A1_EV = A1_OUT / "ITERS" / "it.19" / f"{A1_RUN}.19.events.xml.gz"
A1_INTEGRITY = A1_ROOT / "audit" / "a1_run_integrity.json"

# 观测 / 靶场 / 网络标签（全部只读）
OBS_CSV = ROOT / "reports" / "od_audit" / "audit_trafficflow.csv"
XWALK = ROOT / "reports" / "od_final_calibration_crosswalk_7_3_6" / "final_calibration_crosswalk.csv"
CACHE_NET = SCRIPTS_OD / "_cache_network_7_9c0.npz"
SEC_GEO = d76.OUT_DIR / "section_geography.csv"

# --------------------------------------------------------------------------
# 冻结常量
# --------------------------------------------------------------------------
SCALE = 2.29897
F_CAP = 0.434977
N_SIM = 236_044
SIM_OBS_FROZEN = 0.9993347697
NET_KM_FULL = 15126.5                 # 全网 693,575 段总里程（km，冻结）
GUARDRAIL_SIM_OBS = 0.85
THREE_FACTOR = 3.0                    # §4.3 t_onset 判据：v1.0 同 bin 值的 3 倍

# linkstats 列索引（154 列，已实测）
C_LINK, C_ORIG, C_FROM, C_TO, C_LEN, C_FS, C_CAP = 0, 1, 2, 3, 4, 5, 6
C_H78, C_H89, C_TT89 = 29, 32, 107

CUTS = [0, 50, 100, 200]              # §4.1 长度 cut（m）
BIN_S = 300                           # §4.3 5 分钟 bin
T_LO, T_HI = 6 * 3600, 12 * 3600      # 06:00–12:00
SPEED_RATIO_SLOW = 0.80               # §4.1 N_slow
EV_SLOW = 0.60                        # §4.3 车辆级平均速度比阈值
EV_MIN_N = 3                          # §4.3 每 (link,bin) 最少样本

CHECKS: list[dict] = []
NOTES: list[str] = []


# --------------------------------------------------------------------------
# 工具
# --------------------------------------------------------------------------
def gate(cid, name, ok, detail=""):
    CHECKS.append({"check": cid, "name": name, "pass": bool(ok), "detail": str(detail)})
    print(f"  [{'PASS' if ok else 'FAIL'}] {cid} {name}" + (f"  ({detail})" if detail else ""),
          flush=True)
    return bool(ok)


def record(cid, name, detail):
    """记录项：不参与 PASS/FAIL（用于崩解检测等『观测结果』）。"""
    CHECKS.append({"check": cid, "name": name, "pass": "REC", "detail": str(detail)})
    print(f"  [REC ] {cid} {name}  ({detail})", flush=True)


def wcsv(p: Path, header, rows):
    with open(p, "w", newline="", encoding="utf-8-sig") as fh:
        w = csv.DictWriter(fh, fieldnames=header, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def wjson(p: Path, obj):
    with open(p, "w", encoding="utf-8") as fh:
        json.dump(obj, fh, ensure_ascii=False, indent=2, default=str)


def sha16(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()[:16]


def sha256(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def pearson(xs, ys):
    n = len(xs)
    if n < 3:
        return float("nan")
    mx, my = sum(xs) / n, sum(ys) / n
    sxy = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    sxx = sum((x - mx) ** 2 for x in xs)
    syy = sum((y - my) ** 2 for y in ys)
    if sxx <= 0 or syy <= 0:
        return float("nan")
    return sxy / math.sqrt(sxx * syy)


def rankdata(v):
    order = sorted(range(len(v)), key=lambda i: v[i])
    r = [0.0] * len(v)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and v[order[j + 1]] == v[order[i]]:
            j += 1
        avg = (i + j) / 2.0 + 1.0
        for k in range(i, j + 1):
            r[order[k]] = avg
        i = j + 1
    return r


def spearman(xs, ys):
    """⚠ **UNUSED**（保留但未纳入任何判据）：预注册 §4/§5 未要求秩相关。

    ★本评价器死代码审计记录：`pearson` 与 `geh` 曾同样「定义但从未被调用」，
    而预注册 §5 ① **明文要求** Pearson r / WMAPE / GEH ⇒ 已由 `flow_quality()` 起用（补齐缺门禁）。
    `spearman`/`rankdata` 仍属**非预注册指标**，⛔ 不得据此另立判据。
    """
    return pearson(rankdata(xs), rankdata(ys))


def geh(sim, obs):
    """GEH 统计量（英国 Highways Agency 标准）：GEH<5 优 / 5–10 可接受 / >10 需关注。"""
    if sim + obs <= 0:
        return 0.0
    return math.sqrt(2.0 * (sim - obs) ** 2 / (sim + obs))


FLOWQ_KEYS = ("n_used", "pearson_r", "wmape", "geh_median", "geh_mean",
              "geh_lt5", "geh_5to10", "geh_ge10", "share_geh_lt5")


def flow_quality(sec: pd.DataFrame) -> dict:
    """★预注册 §5 ① 「流量（崩解护栏）」明文要求的三项：Pearson r、WMAPE、GEH 分布。

    背景（本评价器死代码审计）：`pearson()` 与 `geh()` 早已定义但**从未被任何代码调用**
    ⇒ §5 ① 的这三项在 **A-0 与 A-1 评价器中均未实际产出**（A-0 脚本第 683 行只是把
    「Pearson/WMAPE/GEH」写进了一句**前向描述字符串**）。本函数予以补齐。
    ⛔ **不改任何判据阈值**：§5 ① 的硬门仍是 `Sim/Obs >= 0.85`（门 `A09`），
       本函数产出的是**报告量**（写入 `a1_guardrails.csv`），由门 `A09b` 断言「确实产出」。

    口径（与 `pooled()` 同源、**全断面池化、含零流断面**）：
      `Sim = sec['sim_8_9_scaled']`（= median(匹配有向边 HRS8-9avg) × SCALE）
      `Obs = sec['obs_8_9']`
      Pearson r = 断面级线性相关（`pearson`）
      WMAPE     = Σ|Sim-Obs| / ΣObs（**obs 加权**，非按断面平均）
      GEH       = sqrt(2(Sim-Obs)^2/(Sim+Obs))（`geh`；Sim+Obs<=0 ⇒ 0）
    """
    sim = [float(x) for x in sec["sim_8_9_scaled"].tolist()]
    obs = [float(x) for x in sec["obs_8_9"].tolist()]
    n = len(sim)
    if n == 0:
        return {k: float("nan") for k in FLOWQ_KEYS}
    so = sum(obs)
    g = [geh(a, b) for a, b in zip(sim, obs)]
    gs = sorted(g)
    med = gs[n // 2] if n % 2 else 0.5 * (gs[n // 2 - 1] + gs[n // 2])
    lt5 = sum(1 for x in g if x < 5.0)
    mid = sum(1 for x in g if 5.0 <= x < 10.0)
    return {"n_used": n,
            "pearson_r": pearson(sim, obs),
            "wmape": (sum(abs(a - b) for a, b in zip(sim, obs)) / so) if so > 0 else float("nan"),
            "geh_median": med, "geh_mean": sum(g) / n,
            "geh_lt5": lt5, "geh_5to10": mid, "geh_ge10": n - lt5 - mid,
            "share_geh_lt5": lt5 / n}


def ceil_ff(ff):
    """★量化消除（7.7E 根因：MATSim 行程时间取整 ⇒ TT = ceil(FF)）。"""
    return math.ceil(ff - 1e-9)


def hms(t: int) -> str:
    return f"{t // 3600:02d}:{(t % 3600) // 60:02d}"


def _fv(v, p: int = 4) -> str:
    """报告渲染用安全格式化：None → 'None'；数值 → 定点 p 位（nan → 'nan'）；其余 str()。"""
    if v is None:
        return "None"
    if isinstance(v, bool):
        return str(v)
    if isinstance(v, (int, float)):
        return f"{v:.{p}f}"
    return str(v)


# --------------------------------------------------------------------------
# 载入 linkstats / legHistogram / 观测 / 靶场
# --------------------------------------------------------------------------
def load_linkstats(p: Path) -> dict[str, dict]:
    out: dict[str, dict] = {}
    with gzip.open(p, "rt", encoding="utf-8", errors="replace") as fh:
        rd = csv.reader(fh, delimiter="\t")
        next(rd, None)
        for r in rd:
            if len(r) <= C_TT89:
                continue
            try:
                out[r[C_LINK]] = {
                    "orig": r[C_ORIG], "length": float(r[C_LEN]), "fs": float(r[C_FS]),
                    "cap": float(r[C_CAP]), "h78": float(r[C_H78]), "h89": float(r[C_H89]),
                    "tt89": float(r[C_TT89]),
                }
            except ValueError:
                continue
    return out


def load_leg_hist(p: Path) -> list[dict]:
    """legHistogram.txt 首两列同名 `time`（HH:MM:SS + 秒）⇒ 按列名/位置显式解析。"""
    with open(p, encoding="utf-8-sig") as fh:
        lines = fh.read().splitlines()
    hdr = lines[0].split("\t")
    i_dep = hdr.index("departures_car")
    i_arr = hdr.index("arrivals_car")
    i_stk = hdr.index("stuck_car")
    i_enr = hdr.index("en-route_car")
    rows = []
    for ln in lines[1:]:
        f = ln.split("\t")
        if len(f) <= max(i_dep, i_arr, i_stk, i_enr):
            continue
        try:
            rows.append({"t": int(float(f[1])), "dep": int(f[i_dep]), "arr": int(f[i_arr]),
                         "stuck": int(f[i_stk]), "enroute": int(f[i_enr])})
        except ValueError:
            continue
    return rows


def load_observed() -> dict[str, dict[int, float]]:
    out: dict[str, dict[int, float]] = defaultdict(dict)
    with open(OBS_CSV, encoding="utf-8-sig", newline="") as fh:
        for r in csv.DictReader(fh):
            try:
                out[str(r["LinkID"])][int(r["hour"])] = float(r["median_volume"])
            except (ValueError, KeyError):
                continue
    return dict(out)


def load_crosswalk_raw() -> pd.DataFrame:
    df = pd.read_csv(XWALK, encoding="utf-8-sig")
    df["matsim_link_id"] = df["matsim_link_id"].astype(str).str.strip()
    df["lta_linkid"] = df["lta_linkid"].astype(str).str.strip()
    return df


# --------------------------------------------------------------------------
# 指标 ① ②（linkstats 面）
# --------------------------------------------------------------------------
def face_metrics(L: dict[str, dict], cap_mul: float | None) -> dict:
    """① N_cong / N_slow（多 cut）；② v/c 计数与饱和里程。"""
    res = {"n_links": len(L), "n_loaded": 0, "net_km": 0.0, "loaded_km": 0.0}
    for d in L.values():
        res["net_km"] += d["length"] / 1000.0
    # ①
    for cut in CUTS:
        res[f"n_cong_cut{cut}"] = 0
        res[f"km_cong_cut{cut}"] = 0.0
        res[f"n_slow_cut{cut}"] = 0
        res[f"km_slow_cut{cut}"] = 0.0
    res["n_cong_ge1s"] = 0
    # ②
    res.update({"n_vc_ge_05": 0, "n_vc_ge_09": 0, "n_vc_ge_10": 0,
                "n_vc_ge_15": 0, "n_vc_ge_20": 0, "sat_km": 0.0,
                "flow_on_sat": 0.0, "max_vc": 0.0, "max_vol": 0.0,
                "peak_agg_vc": 0.0, "delay_h": 0.0})
    tot_cap_flow = 0.0
    for d in L.values():
        km = d["length"] / 1000.0
        if d["h89"] <= 0:
            continue
        res["n_loaded"] += 1
        res["loaded_km"] += km
        res["max_vol"] = max(res["max_vol"], d["h89"])
        ff = d["length"] / d["fs"] if d["fs"] > 0 else 0.0
        ffc = ceil_ff(ff)
        ex = d["tt89"] - ffc
        sp_ratio = (ff / d["tt89"]) if d["tt89"] > 0 else float("nan")
        for cut in CUTS:
            if d["length"] >= cut:
                if ex > 0:
                    res[f"n_cong_cut{cut}"] += 1
                    res[f"km_cong_cut{cut}"] += km
                if d["fs"] > 0 and d["tt89"] > 0 and sp_ratio < SPEED_RATIO_SLOW:
                    res[f"n_slow_cut{cut}"] += 1
                    res[f"km_slow_cut{cut}"] += km
        if ex >= 1.0:
            res["n_cong_ge1s"] += 1
        res["delay_h"] += d["h89"] * max(ex, 0.0) / 3600.0
        if cap_mul is not None:
            cap = d["cap"] * cap_mul
            if cap > 0:
                vc = d["h89"] / cap
                res["max_vc"] = max(res["max_vc"], vc)
                tot_cap_flow += cap
                if vc >= 0.5:
                    res["n_vc_ge_05"] += 1
                if vc >= 0.9:
                    res["n_vc_ge_09"] += 1
                if vc >= 1.0:
                    res["n_vc_ge_10"] += 1
                    res["sat_km"] += km
                    res["flow_on_sat"] += d["h89"]
                if vc >= 1.5:
                    res["n_vc_ge_15"] += 1
                if vc >= 2.0:
                    res["n_vc_ge_20"] += 1
    res["peak_agg_vc"] = (sum(d["h89"] for d in L.values()) / tot_cap_flow) if tot_cap_flow > 0 else float("nan")
    res["total_flow"] = sum(d["h89"] for d in L.values())
    res["share_len_saturated"] = res["sat_km"] / NET_KM_FULL
    # 两种基数并报（A-0 §6 的 share_flow_on_saturated 未注明分母 ⇒ 同时给出，运行期核对哪个复现 0.226%）
    res["share_flow_on_saturated_vs_maxvol"] = (res["flow_on_sat"] / res["max_vol"]) if res["max_vol"] else float("nan")
    res["share_flow_on_saturated_vs_total"] = (res["flow_on_sat"] / res["total_flow"]) if res["total_flow"] else float("nan")
    # ★A-0 §6 的 share_flow_on_saturated 已核实分母 = **全网总流量**（v1.0 = 0.226% 逐位复现）
    res["share_flow_on_saturated"] = res["share_flow_on_saturated_vs_total"]
    return res


# --------------------------------------------------------------------------
# §11 CAPACITY 语义消解（A-1 vs v1.0）
# --------------------------------------------------------------------------
def resolve_capacity_semantics(ls_v10: dict, ls_a1: dict) -> dict:
    common = [k for k in ls_v10 if k in ls_a1]
    n = len(common)
    same = 0
    ratio_ok = 0
    for k in common:
        c0 = ls_v10[k]["cap"]
        c1 = ls_a1[k]["cap"]
        if c0 == c1:
            same += 1
        if c0 > 0 and abs(c1 / (c0 * F_CAP) - 1.0) <= 1e-6:
            ratio_ok += 1
    if n and same == n:
        mode, mul_v10, mul_a1 = "BASE_CAPACITY", 1.0, F_CAP
    elif n and ratio_ok == n and same == 0:
        mode, mul_v10, mul_a1 = "EFFECTIVE_CAPACITY", 1.0, 1.0
    else:
        mode, mul_v10, mul_a1 = "CAPACITY_SEMANTICS_UNRESOLVED", None, None
    return {"mode": mode, "n_common": n, "n_identical": same, "n_ratio_match": ratio_ok,
            "cap_mul_v10": mul_v10, "cap_mul_a1": mul_a1}


def capacity_crossval(ls_a1: dict, cap_mul_a1: float | None, ls_v10: dict = None) -> dict:
    """§11 第 2 条：交叉验证 HRS8-9avg 是否大量超过 CAPACITY_eff。"""
    if cap_mul_a1 is None:
        return {"status": "NA", "n_over": None}
    over = 0
    n_flow = 0
    for d in ls_a1.values():
        if d["h89"] <= 0:
            continue
        n_flow += 1
        cap = d["cap"] * cap_mul_a1
        if cap > 0 and d["h89"] > cap:
            over += 1
    return {"status": "OK" if over <= 100 else "WARN_RULE_SUSPECT",
            "n_over": over, "n_flow": n_flow,
            "full_cap_over": None if ls_v10 is None else sum(
                1 for k, d in ls_v10.items() if d["h89"] > 0 and d["cap"] > 0 and d["h89"] > d["cap"])}


# --------------------------------------------------------------------------
# §5 （无落盘：由 face_metrics 直接给出）
# --------------------------------------------------------------------------


# --------------------------------------------------------------------------
# ③ events 时间过程（车辆级，5-min bin）
# --------------------------------------------------------------------------
def build_link_index(L: dict[str, dict]) -> tuple[dict[str, int], np.ndarray, np.ndarray, np.ndarray]:
    keys = list(L.keys())
    idx = {k: i for i, k in enumerate(keys)}
    L_arr = np.array([L[k]["length"] for k in keys], dtype=np.float64)
    FS_arr = np.array([L[k]["fs"] for k in keys], dtype=np.float64)
    CAP_arr = np.array([L[k]["cap"] for k in keys], dtype=np.float64)
    return idx, L_arr, FS_arr, CAP_arr


def events_time_series(ev: Path, link_index: dict[str, int], L_arr: np.ndarray,
                       FS_arr: np.ndarray, CAP_arr: np.ndarray,
                       cap_mul: float = 1.0, bin_s: int = BIN_S,
                       t_lo: int = T_LO, t_hi: int = T_HI) -> dict:
    """逐行流式解析（PREREG §4.3 仪器）。5-min bin，窗口 06:00–12:00。

    ★2026-09-29 实测两处**关键口径**（第 1 版曾因此产出 `unknown_link=161M` / `enroute=236k` 假值）：

    **(1) 属性顺序随事件类型而变**（不能统一取 tk[5]/tk[7]）：

    | 事件类型 | 属性顺序 | link | vehicle |
    |---|---|---|---|
    | `entered link` / `left link` | `time, type, **link**, vehicle` | `tk[5]` | `tk[7]` |
    | `departure` / `arrival` / `vehicle enters traffic` / `vehicle leaves traffic` | `time, type, person, link, …` | 靠 `attr()` 按名取 | 靠 `attr()` |

    **(2) 每辆车恰有 1 个 `entered link` 无配对 `left link`**（MATSim 末链不发 `left link`）
        ⇒ `entered − left` 恒虚高 **+1 / 车**（v1.0 实测 `miss = 236,039 = 车辆数`，且随出发数同步增长）。
        故 `enroute(t)` 采用**在网车辆**口径 `n_on(=enters traffic − leaves traffic) − |pending|`；
        原始配对差保留为 `enroute_pair_end`（**伪影留痕，不作判据**）。
        该伪影使 `acc_n` 少 1/车 条链路样本（≈0.29 %），**A-1 与 v1.0 同源** ⇒ 相对判据免疫。
    """
    nb = (t_hi - t_lo) // bin_s
    acc_tt: dict[tuple[int, int], float] = {}
    acc_n: dict[tuple[int, int], int] = {}
    n_enter = [0] * nb
    n_left = [0] * nb
    vkm = [0.0] * nb
    vh = [0.0] * nb
    dep = [0] * nb
    arr = [0] * nb
    stuck = [0] * nb
    q_end = [0] * nb
    enr_end = [0] * nb
    enr_pair_end = [0] * nb
    veh: dict[str, tuple[int, float]] = {}
    pending: set[str] = set()
    n_on = 0                # 在网车辆 = enters traffic − leaves traffic
    n_pair = 0              # 原始配对计数（含结构性 +1/车 伪影）
    n_lines = 0
    last_k = 0
    n_unknown_link = 0
    n_leave_traffic = 0
    n_pair_miss = 0

    def bidx(t):
        k = int((t - t_lo) // bin_s)
        return k if 0 <= k < nb else None

    def advance(k):
        """跨 bin 时把存量快照写进已结束的 bin（events 为**时间有序**，实测 n_back = 0）。"""
        nonlocal last_k
        if k > last_k:
            q = len(pending)
            e = n_on - q
            for kk in range(last_k, k):
                q_end[kk] = q
                enr_end[kk] = e
                enr_pair_end[kk] = n_pair
            last_k = k

    def attr(line, name):
        i = line.find(f'{name}="')
        if i < 0:
            return None
        j = line.find('"', i + len(name) + 2)
        return line[i + len(name) + 2:j]

    with gzip.open(ev, "rt", encoding="utf-8", errors="replace") as fh:
        for line in fh:
            n_lines += 1
            # ★实测：文本模式 + split('"', 8) 最快（0.54M 行/s；bytes 模式反而 0.32M/s）
            tk = line.split('"', 8)
            if len(tk) < 8:
                continue
            typ = tk[3]
            if typ == "entered link" or typ == "left link":
                t = float(tk[1])
                k = bidx(t)
                if k is None:
                    continue
                advance(k)
                lk = tk[5]
                vid = tk[7]
                idx = link_index.get(lk)
                if idx is None:
                    n_unknown_link += 1
                    continue
                pending.discard(vid)
                if typ == "entered link":
                    veh[vid] = (idx, t)
                    n_pair += 1
                    n_enter[k] += 1
                else:
                    e = veh.pop(vid, None)
                    if e is None:
                        n_pair_miss += 1
                        continue
                    n_pair -= 1
                    tt = t - e[1]
                    n_left[k] += 1
                    vkm[k] += L_arr[idx] / 1000.0
                    vh[k] += tt / 3600.0
                    key = (idx, k)
                    acc_tt[key] = acc_tt.get(key, 0.0) + tt
                    acc_n[key] = acc_n.get(key, 0) + 1
            elif typ in ("vehicle enters traffic", "vehicle leaves traffic",
                         "departure", "arrival", "stuck"):
                t = float(tk[1])
                k = bidx(t)
                if k is None:
                    continue
                advance(k)
                if typ == "vehicle enters traffic":
                    v = attr(line, "vehicle")
                    if v:
                        pending.add(v)
                    n_on += 1
                elif typ == "vehicle leaves traffic":
                    v = attr(line, "vehicle")
                    if v:
                        pending.discard(v)
                    n_on -= 1
                    n_leave_traffic += 1
                elif typ == "departure":
                    dep[k] += 1
                elif typ == "arrival":
                    arr[k] += 1
                else:
                    stuck[k] += 1

    q = len(pending)
    e = n_on - q
    for kk in range(last_k, nb):
        q_end[kk] = q
        enr_end[kk] = e
        enr_pair_end[kk] = n_pair

    # 慢链路计数（单遍，O(|cells|)）
    slow_by_bin = [0] * nb
    for (idx, k), n in acc_n.items():
        if n < EV_MIN_N:
            continue
        tt = acc_tt[(idx, k)] / n
        L = L_arr[idx]
        fs = FS_arr[idx]
        if L <= 0 or fs <= 0 or tt <= 0:
            continue
        if (L / tt) / fs < EV_SLOW:
            slow_by_bin[k] += 1

    bins = []
    for k in range(nb):
        vkm_k, vh_k = vkm[k], vh[k]
        bins.append({"t": t_lo + k * bin_s, "t_hms": hms(t_lo + k * bin_s),
                     "n_enter": n_enter[k], "n_left": n_left[k], "vkm": vkm_k, "vh": vh_k,
                     "dep": dep[k], "arr": arr[k], "stuck": stuck[k],
                     "n_slow_links": slow_by_bin[k],
                     "mean_speed_kmh": (vkm_k / vh_k) if vh_k > 0 else 0.0,
                     "queued_end": q_end[k], "enroute_end": enr_end[k],
                     "enroute_pair_end": enr_pair_end[k]})

    # ★7.7E E4 同口径 aggV/C（15 min bin）：agg_vc = Σ(该 bin 内逐链路流率) / Σ(该 bin 内被触达链路的容量)
    per15: dict[int, list] = {}
    for (idx, k), n in acc_n.items():
        a = per15.setdefault(k // 3, [0.0, 0.0, set()])
        a[0] += n * (3600.0 / (bin_s * 3))     # rate_veh_h
        a[1] += n                               # entries
        a[2].add(idx)
    agg15 = []
    for k15 in sorted(per15):
        rate, entries, links = per15[k15]
        capsum = sum(CAP_arr[i] * cap_mul for i in links)
        agg15.append({"t": t_lo + k15 * bin_s * 3, "t_hms": hms(t_lo + k15 * bin_s * 3),
                      "entries": entries, "n_links": len(links),
                      "rate_sum": rate, "cap_sum": capsum,
                      "agg_vc": (rate / capsum) if capsum > 0 else float("nan")})

    return {"bins": bins, "agg15": agg15, "n_lines": n_lines, "n_cells": len(acc_n),
            "n_unknown_link": n_unknown_link, "n_leave_traffic": n_leave_traffic,
            "n_pair_miss": n_pair_miss, "n_pair_net": n_pair,
            "n_stuck": sum(stuck),
            "sum_dep": sum(dep), "sum_arr": sum(arr)}


def ts_profile(ts: dict) -> dict:
    """从 5-min 曲线提取 onset / peak / clear / duration（§4.3）。"""
    bins = ts["bins"]
    slow = [b["n_slow_links"] for b in bins]
    peak_i = int(np.argmax(slow)) if slow else 0
    g = ts.get("agg15") or []
    pk = max(g, key=lambda r: (r["agg_vc"] if r["agg_vc"] == r["agg_vc"] else -1)) if g else None
    return {"n_slow_max": int(max(slow)) if slow else 0, "t_peak": bins[peak_i]["t"],
            "t_peak_hms": bins[peak_i]["t_hms"], "slow_series": slow,
            "enroute_max": int(max(b["enroute_end"] for b in bins)) if bins else 0,
            "enroute_pair_max": int(max(b["enroute_pair_end"] for b in bins)) if bins else 0,
            "queued_max": int(max(b["queued_end"] for b in bins)) if bins else 0,
            "stuck_max": int(max(b["stuck"] for b in bins)) if bins else 0,
            "peak_agg_vc_15min": (pk["agg_vc"] if pk else float("nan")),
            "peak_agg_vc_15min_hhmm": (pk["t_hms"] if pk else None),
            "agg15": g,
            "sum_dep": ts["sum_dep"], "sum_arr": ts["sum_arr"]}


def onset_vs_reference(ts_a1: dict, ts_v10: dict) -> dict:
    """`t_onset`：A-1 的 `n_slow_links(t)` 首次 ≥ v1.0 同 bin 值的 **3 倍**（PREREG §4.3 冻结判据）。

    另给出 **1.5 倍次级阈值**（仅作敏感性参考，⛔ 不替代主判据）；两者都未命中时判 `NO_3X_ONSET`。
    """
    a = [b["n_slow_links"] for b in ts_a1["bins"]]
    v = [b["n_slow_links"] for b in ts_v10["bins"]]

    def first_cross(mult):
        on = cl = None
        for k, (av, vv) in enumerate(zip(a, v)):
            if av >= max(mult * vv, 1.0):
                on = ts_a1["bins"][k]["t"]
                break
        if on is not None:
            for k in range(len(a) - 1, -1, -1):
                if a[k] >= max(mult * v[k], 1.0):
                    cl = ts_a1["bins"][k]["t"]
                    break
        return on, cl

    t_on, t_cl = first_cross(THREE_FACTOR)
    s_on, s_cl = first_cross(1.5)
    return {"t_onset": t_on, "t_onset_hms": hms(t_on) if t_on is not None else None,
            "t_clear": t_cl, "t_clear_hms": hms(t_cl) if t_cl is not None else None,
            "duration_min": (None if (t_on is None or t_cl is None) else (t_cl - t_on) / 60.0),
            "criterion": ("THREE_X" if t_on is not None else "NO_3X_ONSET"),
            "t_onset_1p5x": s_on, "t_onset_1p5x_hms": hms(s_on) if s_on is not None else None,
            "duration_min_1p5x": (None if (s_on is None or s_cl is None) else (s_cl - s_on) / 60.0)}


def parser_fingerprint() -> str:
    """★解析器指纹 = `events_time_series` + `hms` 源码 + 相关常量值。

    设计意图：缓存只在**解析逻辑真的变了**时失效；改报告渲染 / 门禁文案**不会**触发 ~20 min 重解析。
    ⛔ 若改动 `events_time_series` 依赖的任何函数，请一并加入本指纹。

    ★★脆弱性与其守卫（2026-09-29 实测教训）
      `inspect.getsource` 用函数的 `co_firstlineno`（**编译时**行号）去索引**当前磁盘上**的文件行。
      若本源文件在本进程**加载之后**被编辑（行号漂移），取到的就是**错误的代码块** ⇒ 指纹静默漂移
      ⇒ 缓存未命中 ⇒ 白跑一次全量重解析。实测：prewarm 进程 11:13:30 加载，源文件 11:21:43 被编辑，
      其第二次 `events_cached()` 因此多跑了 ~22 min（磁盘实测 2 GB/s ⇒ 排除 I/O 慢，坐实为重复解析）。
      **该失效原本是静默的** ⇒ 此处加**硬性守卫**：一旦漂移，立即显式报错，⛔ 不允许静默重算。
      ★纪律：**不得在被测进程运行期间编辑本文件**。
    """
    import inspect
    src_ts = inspect.getsource(events_time_series)
    src_hms = inspect.getsource(hms)
    if not src_ts.lstrip().startswith("def events_time_series(") or \
            not src_hms.lstrip().startswith("def hms("):
        raise RuntimeError(
            "★解析器指纹不可靠：inspect.getsource 未取到函数头（行号漂移）。"
            "通常是**源码在本进程加载后被编辑** ⇒ 会静默触发全量重解析。"
            f"  ts_head={src_ts[:48]!r}  hms_head={src_hms[:48]!r}")
    h = hashlib.sha256()
    h.update(src_ts.encode())
    h.update(src_hms.encode())
    h.update(f"{BIN_S}|{T_LO}|{T_HI}|{EV_SLOW}|{EV_MIN_N}|EV2".encode())
    return h.hexdigest()[:16]


def events_cached(tag: str, ev: Path, link_index, L_arr, FS_arr, CAP_arr,
                  cap_mul: float, force: bool = False) -> dict:
    """events 解析带缓存（键 = 文件名 sha16 + cap_mul + **解析器指纹**）。

    ⚠ 只有 `bins` / `agg15` / 计数被缓存（JSON 可序列化）；解析逻辑本身不变 ⇒ 仪器口径不变。
    ⚠ payload 内记录本次写缓存时的评价器整文件 sha（审计留痕）。
    """
    d = OUT / "_events_cache"
    d.mkdir(parents=True, exist_ok=True)
    fp = parser_fingerprint()
    base = f"{tag}_{ev.name}"
    if ev.exists():
        base += f"_{sha16(ev)}"
    p = d / (base + f"_cm{cap_mul:g}_fp{fp}.json")
    if p.exists() and not force:
        c = json.loads(p.read_text(encoding="utf-8"))
        if c.get("parser_fingerprint") == fp:
            print(f"     [events] {tag} 复用缓存 {p.name}", flush=True)
            return c["payload"]
        print(f"     [events] {tag} 缓存指纹不符（{c.get('parser_fingerprint')} != {fp}）⇒ 重算")
    r = events_time_series(ev, link_index, L_arr, FS_arr, CAP_arr, cap_mul=cap_mul)
    wjson(p, {"parser_fingerprint": fp, "evaluator_sha256": sha256(Path(__file__)),
              "tag": tag, "file": str(ev), "cap_mul": cap_mul,
              "frozen_at": time.strftime("%Y-%m-%d %H:%M:%S"), "payload": r})
    return r


# --------------------------------------------------------------------------
# ④ 空间位置 / 靶场锚定
# --------------------------------------------------------------------------
def load_net_labels() -> dict:
    z = np.load(CACHE_NET, allow_pickle=True)
    return {"ids": np.array([str(x) for x in z["ids"]]),
            "frm": np.array([str(x) for x in z["frm"]]),
            "to": np.array([str(x) for x in z["to"]]),
            "lanes": z["lanes"].astype(float),
            "highway": np.array([str(x) for x in z["highway"]]),
            "name": np.array([str(x) for x in z["name"]]),
            "node_ids": np.array([str(x) for x in z["node_ids"]]),
            "node_x": z["node_x"].astype(float), "node_y": z["node_y"].astype(float)}


def target_anchor(xw: pd.DataFrame) -> dict:
    prim = xw[xw["is_primary_candidate"] == True]  # noqa: E712
    return {"rows_total": int(len(xw)), "rows_primary": int(len(prim)),
            "sections_primary": int(prim["lta_linkid"].nunique()),
            "links_primary": int(prim["matsim_link_id"].nunique()),
            "links_primary_set": set(prim["matsim_link_id"].tolist())}


def overlap_metrics(L: dict[str, dict], cong_links: list[str], target_set: set) -> dict:
    km_cong = sum(L[k]["length"] for k in cong_links if k in L) / 1000.0
    ov = [k for k in cong_links if k in target_set and k in L]
    km_ov = sum(L[k]["length"] for k in ov) / 1000.0
    km_tgt = sum(d["length"] for k, d in L.items() if k in target_set) / 1000.0
    km_loaded = sum(d["length"] for d in L.values() if d["h89"] > 0) / 1000.0
    o = km_ov / km_cong if km_cong > 0 else float("nan")
    b_full = km_tgt / NET_KM_FULL if NET_KM_FULL > 0 else float("nan")
    b_load = km_tgt / km_loaded if km_loaded > 0 else float("nan")
    return {"n_cong": len(cong_links), "km_cong": km_cong, "n_overlap": len(ov), "km_overlap": km_ov,
            "n_target": len([k for k in L if k in target_set]), "km_target": km_tgt,
            "km_loaded": km_loaded,
            "overlap_len_share": o,
            "base_rate_len_share_fullnet": b_full,
            "base_rate_len_share_loaded": b_load,
            "concentration_ratio": (o / b_full) if (b_full and b_full > 0) else float("nan"),
            "concentration_ratio_loaded_denom": (o / b_load) if (b_load and b_load > 0) else float("nan")}


def top_congestion(L: dict[str, dict], labels: dict, xw_meta: dict, n_top: int = 500) -> list[dict]:
    rows = []
    pos = {lid: i for i, lid in enumerate(labels["ids"])}
    for k, d in L.items():
        if d["h89"] <= 0:
            continue
        ff = d["length"] / d["fs"] if d["fs"] > 0 else 0.0
        ex = d["tt89"] - ceil_ff(ff)
        if ex <= 0:
            continue
        rows.append((k, d, ex, (ff / d["tt89"]) if d["tt89"] > 0 else float("nan")))
    rows.sort(key=lambda x: (-x[2], x[0]))
    out = []
    for r, (k, d, ex, sr) in enumerate(rows[:n_top], 1):
        i = pos.get(k)
        out.append({"rank": r, "LINK": k, "ORIG_ID": d["orig"],
                    "highway": (labels["highway"][i] if i is not None else ""),
                    "RoadName": (labels["name"][i] if i is not None else ""),
                    "RoadCat": xw_meta.get(k, {}).get("roadcat", ""),
                    "is_target_primary": k in xw_meta,
                    "LENGTH_m": round(d["length"], 3), "h89": d["h89"],
                    "TRAVELTIME8-9avg_s": round(d["tt89"], 3),
                    "ff_ceil_s": ceil_ff(d["length"] / d["fs"] if d["fs"] > 0 else 0.0),
                    "excess_s": round(ex, 3), "speed_ratio": round(sr, 5),
                    "CAPACITY": d["cap"], "v_c_base": round(d["h89"] / d["cap"], 5) if d["cap"] > 0 else None})
    return out


def by_roadcat(L: dict[str, dict], xw: pd.DataFrame) -> list[dict]:
    prim = xw[xw["is_primary_candidate"] == True]  # noqa: E712
    m = {}
    for _, r in prim.iterrows():
        m.setdefault(r["matsim_link_id"], r["RoadCat"])
    agg = defaultdict(lambda: {"n_cong": 0, "km_cong": 0.0, "excess_h": 0.0, "n_links": 0,
                               "km_links": 0.0, "flow": 0.0, "n_sat": 0})
    for k, d in L.items():
        cat = m.get(k)
        if cat is None:
            continue
        a = agg[cat]
        a["n_links"] += 1
        a["km_links"] += d["length"] / 1000.0
        if d["h89"] <= 0:
            continue
        a["flow"] += d["h89"]
        ff = d["length"] / d["fs"] if d["fs"] > 0 else 0.0
        ex = d["tt89"] - ceil_ff(ff)
        if ex > 0:
            a["n_cong"] += 1
            a["km_cong"] += d["length"] / 1000.0
            a["excess_h"] += d["h89"] * ex / 3600.0
        if d["cap"] > 0 and d["h89"] / d["cap"] >= 1.0:
            a["n_sat"] += 1
    return [{"RoadCat": c, **v} for c, v in sorted(agg.items())]


# --------------------------------------------------------------------------
# VIA 属性层 + 空间位置图
# --------------------------------------------------------------------------
def write_via_tsv(p: Path, L: dict[str, dict], labels: dict, cap_mul: float):
    """与 reports/via_congestion_diagnosis_7_8/via_link_attributes_HRS8-9.tsv **同构**
    （同 15 列 + 追加 3 列：cap_eff_veh_h / excess_s_0809 / speed_ratio_0809）。

    ⚠ 与 v1.0 版一致：linkstats 未提供逐小时行程时间列，`speed_kmh_0708` 与 `speed_kmh_0809`
      使用**同一** TRAVELTIME8-9avg 派生速度（v1.0 版 e0_1 两列同为 22.871 ⇒ 同源约定）。
    """
    pos = {lid: i for i, lid in enumerate(labels["ids"])}
    header = ["link", "link_len_m", "freespeed_mps", "capacity_veh_h", "lanes",
              "vol_0708", "speed_kmh_0708", "cong_ratio_0708", "load_vc_0708", "delay_s_per_km_0708",
              "vol_0809", "speed_kmh_0809", "cong_ratio_0809", "load_vc_0809", "delay_s_per_km_0809",
              "cap_eff_veh_h", "excess_s_0809", "speed_ratio_0809"]

    def one(d, tt):
        fs = d["fs"]
        sp = (d["length"] / tt) if tt > 0 else fs
        cr = (fs / sp) if sp > 0 else float("nan")
        dly = (((d["length"] / sp) - (d["length"] / fs)) / (d["length"] / 1000.0)
               if (sp > 0 and fs > 0 and d["length"] > 0) else 0.0)
        return sp * 3.6, cr, dly

    n = 0
    with open(p, "w", newline="", encoding="utf-8") as fh:
        fh.write("\t".join(header) + "\n")
        for k, d in L.items():
            i = pos.get(k)
            lanes = labels["lanes"][i] if i is not None else 0.0
            tt = d["tt89"] if d["tt89"] > 0 else (d["length"] / d["fs"] if d["fs"] > 0 else 1.0)
            sp8, cr8, dl8 = one(d, tt)
            sp7, cr7, dl7 = sp8, cr8, dl8
            cap_eff = d["cap"] * cap_mul
            ff = d["length"] / d["fs"] if d["fs"] > 0 else 0.0
            ex = d["tt89"] - ceil_ff(ff)
            fh.write("\t".join([
                k, f"{d['length']:.3f}", f"{d['fs']:.6f}", f"{d['cap']:.1f}", f"{lanes:.1f}",
                f"{d['h78']:.1f}", f"{sp7:.3f}", f"{cr7:.4f}",
                f"{(d['h78'] / cap_eff if cap_eff > 0 else 0.0):.5f}", f"{dl7:.3f}",
                f"{d['h89']:.1f}", f"{sp8:.3f}", f"{cr8:.4f}",
                f"{(d['h89'] / cap_eff if cap_eff > 0 else 0.0):.5f}", f"{dl8:.3f}",
                f"{cap_eff:.1f}", f"{ex:.3f}",
                f"{(ff / d['tt89'] if d['tt89'] > 0 else float('nan')):.5f}"]) + "\n")
            n += 1
    return n


def draw_map(p: Path, L_v10: dict, L_a1: dict, labels: dict, tgt: set):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.font_manager as mfont
    import matplotlib.pyplot as plt
    from matplotlib.collections import LineCollection
    from matplotlib.colors import LinearSegmentedColormap, Normalize

    for f in [r"C:\Windows\Fonts\msyh.ttc", r"C:\Windows\Fonts\simhei.ttf"]:
        if Path(f).exists():
            try:
                mfont.fontManager.addfont(f)
            except Exception:
                pass
    plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False
    cmap = LinearSegmentedColormap.from_list(
        "traffic", ["#1a9850", "#91cf60", "#d9ef8b", "#fee08b", "#fc8d59", "#d73027", "#7f0000"])
    nx = dict(zip(labels["node_ids"].tolist(), labels["node_x"].tolist()))
    ny = dict(zip(labels["node_ids"].tolist(), labels["node_y"].tolist()))
    pos = {lid: i for i, lid in enumerate(labels["ids"])}

    def segs(L):
        out, vals = [], []
        for k, d in L.items():
            if d["h89"] <= 0 or d["tt89"] <= 0 or d["fs"] <= 0:
                continue
            i = pos.get(k)
            if i is None:
                continue
            f_, t_ = labels["frm"][i], labels["to"][i]
            if f_ not in nx or t_ not in nx:
                continue
            sr = (d["length"] / d["tt89"]) / d["fs"]
            if sr >= 0.999:
                continue
            out.append([(nx[f_], ny[f_]), (nx[t_], ny[t_])])
            vals.append(sr)
        return out, vals

    fig, axes = plt.subplots(1, 2, figsize=(20, 11))
    for ax, (ttl, L) in zip(axes, [("v1.0（f_cap = 1.0，现状）", L_v10),
                                   ("A-1（f_cap = %.6f = 1/SCALE）" % F_CAP, L_a1)]):
        s, v = segs(L)
        if s:
            lc = LineCollection(s, cmap=cmap, norm=Normalize(0.4, 1.0), linewidths=1.0)
            lc.set_array(np.array(v))
            ax.add_collection(lc)
        # 靶场链位置（灰点）
        tx = [nx[labels["frm"][pos[k]]] for k in list(tgt)[:4000] if k in pos and labels["frm"][pos[k]] in nx]
        ty = [ny[labels["frm"][pos[k]]] for k in list(tgt)[:4000] if k in pos and labels["frm"][pos[k]] in ny]
        if tx:
            ax.scatter(tx, ty, s=0.6, c="#444444", alpha=0.30, marker=".", label="7.3.6A 靶场链")
        ax.set_aspect("equal")
        ax.set_xlim(2000, 52000)
        ax.set_ylim(21000, 51500)
        ax.set_title(f"{ttl}\n早高峰 08–09 行程速度比（仅显示 < 1.0 的链路）", fontsize=12, loc="left")
        ax.set_xlabel("EPSG:3414 (m)")
        ax.legend(fontsize=8, loc="upper left")
    sm = plt.cm.ScalarMappable(cmap=cmap, norm=Normalize(0.4, 1.0))
    sm.set_array([])
    cb = fig.colorbar(sm, ax=axes, fraction=0.025, pad=0.02)
    cb.set_label("speed_ratio = 自由流速度 / 实际速度", fontsize=10)
    fig.suptitle("Step 7.9A-1 · 采样一致性容量（1/SCALE = %.6f）· 拥堵空间位置对照\n"
                 "Singapore_OD_MATSim · W01_it.19 · EPSG:3414" % F_CAP, fontsize=14, y=0.98)
    fig.savefig(p, bbox_inches="tight", facecolor="white", dpi=140)
    plt.close(fig)
    return p


# --------------------------------------------------------------------------
# ★冻结模块护栏（复用 + 带 key 的缓存，避免重复 ~7 min 复算）
# --------------------------------------------------------------------------
GR_DIR = OUT / "_guardrail_cache"


def guardrail_ctx(xw: pd.DataFrame) -> dict:
    obs_df = bt.load_traffic(ev1.TRAFFIC)
    cw_n = bt.normalize_crosswalk(ev1.FINAL_CW, "final")
    cw_prim = xw[xw["is_primary_candidate"] == True].copy()  # noqa: E712
    geo = pd.read_csv(SEC_GEO)[["lta_linkid", "mid_x", "mid_y", "d_cbd_m",
                                "n_links", "radial", "ring", "region", "pa"]]
    geo["lta_linkid"] = geo["lta_linkid"].astype(str).str.strip()
    return {"cw_n": cw_n, "cw_prim": cw_prim, "obs_df": obs_df, "geo": geo,
            "matched": set(xw["matsim_link_id"]),
            "cata": set(xw.loc[xw["RoadCat"] == "CATA", "matsim_link_id"]),
            "slip": set(xw.loc[xw["RoadCat"] == "SLIP_ROAD", "matsim_link_id"])}


def guardrail_key(run: dict) -> str:
    """护栏缓存键 = 4 个冻结模块 sha16 + it.10–19 linkstats sha16。

    ★刻意**不含**评价器整文件 sha：护栏数值完全由**冻结模块**（`E.eval_run`）决定，
    评价器只做搬运 ⇒ 改报告/门禁文案不应触发 ~7 min 重算。评价器 sha 记入 payload 留痕。
    """
    h = hashlib.sha256()
    # ★缓存 schema 版本：payload 结构变化时**必须**递增，否则旧缓存会被误当作有效。
    #   SCHEMA2（2026-09-29）：新增 `flow_quality`（§5 ① Pearson/WMAPE/GEH 补齐）。
    h.update(b"SCHEMA2_flow_quality")
    for mod in ("compare_final_crosswalk_7_3_6b", "evaluate_calibration_7_4_2",
                "diagnose_od_spatial_structure_7_6c", "evaluate_demand_response_7_6f_1"):
        p = SCRIPTS_OD / f"{mod}.py"
        if p.exists():
            h.update(sha16(p).encode())
    for it in range(10, 20):
        p = run["out_dir"] / "ITERS" / f"it.{it}" / f"{run['run_id']}.{it}.linkstats.txt.gz"
        if p.exists():
            h.update(sha16(p).encode())
    return h.hexdigest()[:16]


def guardrail_eval(run: dict, ctx: dict, force: bool = False) -> dict:
    GR_DIR.mkdir(parents=True, exist_ok=True)
    key = guardrail_key(run)
    p = GR_DIR / f"{run['label']}_{run['run_id']}_{key}.json"
    if p.exists() and not force:
        d = json.loads(p.read_text(encoding="utf-8"))
        print(f"     [guardrail] {run['label']} 复用缓存 {p.name}", flush=True)
        return d
    E.OUT = OUT
    E.CYCLE_DIR = CYCLE_DIR
    r = E.eval_run(run, ctx["cw_n"], ctx["cw_prim"], ctx["obs_df"], ctx["geo"],
                   ctx["matched"], ctx["cata"], ctx["slip"], force_cycle=False)
    d = {"label": run["label"], "key": key,
         "q": {k: (float(v) if isinstance(v, (int, float)) else v) for k, v in r["q"].items()},
         "q_19": {k: (float(v) if isinstance(v, (int, float)) else v) for k, v in r["q_19"].items()},
         "n_sections": int(len(r["sec"])), "n_zero_sim": int(r["n_zero_sim"]),
         "flow_quality": flow_quality(r["sec"]),   # ★§5 ① Pearson r / WMAPE / GEH 分布
         "stab": {k: {"A_10_19": float(v["A_10_19"]), "Qbar_10_19": float(v["Qbar_10_19"]),
                      "Q_19": float(v["Q_19"]), "parity_gap_rel": float(v["parity_gap_rel"]),
                      "series": [float(x) for x in v["series"]]}
                  for k, v in r["stab"].items()},
         "spatial": r["spatial"].to_dict("records") if hasattr(r["spatial"], "to_dict") else []}
    wjson(p, d)
    return d


def write_report(s: dict) -> Path:
    """★从 `a1_summary.json` **自动渲染**报告（杜绝手工转抄；每个数字均来自实测）。"""
    vm, am, ra = s["v10_baseline"], s["a1_baseline"], s["ratios"]
    tp, ov, ta = s.get("time_profile", {}), s["spatial_overlap"], s["target_anchor"]
    cs, g = s["capacity_semantics"], s["guardrail"]
    L = []
    A = L.append
    A("# Step 7.9A-1 报告 —— 采样一致性容量（sample-consistent capacity）单因子动态实验\n")
    A(f"> **判决：`{s['verdict']}`**\n>\n> {s['reading']}\n")
    A("> 本报告由 `scripts/od/audit_sampling_capacity_7_9a1.py` 从 `a1_summary.json` **自动渲染**，")
    A("> 所有数字均来自实测产物。**零仿真评价**；评价过程不改任何 MATSim 输入。\n")
    A(f"- 预注册：`PREREG_7_9A1.md` sha256 `{s.get('prereg_sha256')}`（运行前冻结，未修改）")
    A(f"- 评价器 sha256 `{s.get('evaluator_sha256')}`")
    A(f"- 口径决议备忘：`CALIBER_RESOLUTION_NCONG.md`（`N_cong` 阈值歧义，双口径并报）\n")

    A("## 1. 本步回答了什么 / 没回答什么\n")
    A("**回答**：把 QSim 流量与存储容量按 population 表示比例 `1/SCALE` 缩放后，")
    A("① 全网拥堵是否出现**量级**变化；② 是否出现在**正确空间位置**（锚 7.3.6A 靶场）；")
    A("③ 是否呈现正常的**形成—消散**时间过程；④ 是否触发**崩解护栏**。\n")
    A("**不回答**：不重定 `λ / f_work / OD / 路网 / route-choice / 出发时刻`；")
    A("不回答「`0.434977` 是不是真实容量」；⛔ 不把本步结果写成「最优容量」。\n")

    A("## 2. 唯一结构变化（单因子、单点、不扫描）\n")
    A("| # | 参数 | v1.0 冻结 | A-1 | 性质 |")
    A("|---|---|---|---|---|")
    A(f"| 1 | `qsim.flowCapacityFactor` | `1.0` | **`{s['f_cap_6dp']}`** | 模型 |")
    A(f"| 2 | `qsim.storageCapacityFactor` | `1.0` | **`{s['f_cap_6dp']}`** | 模型 |")
    A("| 3–5 | `outputDirectory` / `runId` / `writeEventsInterval` | — | 输出层 | 非模型 |")
    A(f"\n`1/SCALE = {s['one_over_SCALE']:.17f}`；写入配置 6 位小数 `{s['f_cap_6dp']}`。")
    A("全展开参数 diff **恒为 5 项**（含 `<parameterset>` 展开）。\n")

    A("## 3. §11 `CAPACITY` 语义消解\n")
    A(f"- 判定：**`{cs['mode']}`**（`identical={cs['n_identical']}/{cs['n_common']}`，")
    A(f"`ratio_match={cs['n_ratio_match']}`）")
    A(f"- 有效容量乘子：v1.0 `×{cs['cap_mul_v10']}`，A-1 `×{cs['cap_mul_a1']}`")
    cv = s.get("capacity_crossval", {})
    A(f"- 交叉验证：`HRS8-9avg > CAPACITY_eff` 条数 = `{cv.get('n_over')}`（状态 `{cv.get('status')}`）\n")

    A("## 4. 指标① 拥堵链路数（`N_cong` / `N_slow`，五口径 × 四长度 cut）\n")
    A("| 指标 | cut (m) | v1.0 | A-1 | 倍率 | 里程 A-1 (km) |")
    A("|---|---:|---:|---:|---:|---:|")
    for k in ("n_cong_cut0", "n_cong_cut50", "n_cong_cut100", "n_cong_cut200",
              "n_slow_cut0", "n_slow_cut50", "n_slow_cut100", "n_slow_cut200"):
        cut = int(k.split("cut")[1])
        v0, v1 = vm[k], am[k]
        r = (v1 / v0) if v0 else float("inf")
        A(f"| `{k.split('_cut')[0]}` | {cut} | {v0:,} | {v1:,} | ×{r:.3f} | {am.get(k.replace('n_', 'km_'), 0):.3f} |")
    A(f"\n- **主判据口径**（`excess_s > 0`，= 预注册登记基线 7,985）："
      f"v1.0 `{vm['n_cong_cut0']:,}` → A-1 `{am['n_cong_cut0']:,}`（×{ra['n_cong_cut0']['ratio']:.3f}）")
    A(f"- 辅口径（`excess_s ≥ 1.0`）：v1.0 `{vm['n_cong_ge1s']:,}` → A-1 `{am['n_cong_ge1s']:,}`")
    A(f"- `N_slow`（`speed_ratio < 0.80`，**不依赖容量口径**）：cut0 ×{ra['n_slow_cut0']['ratio']:.3f}、"
      f"cut50 ×{ra.get('n_slow_cut50', {}).get('ratio', float('nan')):.3f}、"
      f"cut100 ×{ra.get('n_slow_cut100', {}).get('ratio', float('nan')):.3f}\n")

    A("## 5. 指标② `v/c` 与饱和\n")
    A("| 指标 | v1.0 | A-1 | 倍率 |")
    A("|---|---:|---:|---:|")
    for k, lab in (("n_vc_ge_05", "`n(v/c ≥ 0.5)`"), ("n_vc_ge_09", "`n(v/c ≥ 0.9)`"),
                   ("n_vc_ge_10", "`n(v/c ≥ 1.0)`"), ("n_vc_ge_15", "`n(v/c ≥ 1.5)`"),
                   ("n_vc_ge_20", "`n(v/c ≥ 2.0)`"), ("sat_km", "饱和里程 (km)"),
                   ("share_len_saturated", "饱和里程占比"), ("share_flow_on_saturated", "饱和链流量占比"),
                   ("max_vc", "`max v/c`"), ("peak_agg_vc", "`Σ流量/Σ容量`")):
        v0, v1 = vm.get(k), am.get(k)
        r = ra.get(k, {}).get("ratio")
        rs = f"×{r:.3f}" if isinstance(r, (int, float)) and r == r else "—"
        f0 = f"{v0:.6f}" if isinstance(v0, float) else f"{v0:,}"
        f1 = f"{v1:.6f}" if isinstance(v1, float) else f"{v1:,}"
        A(f"| {lab} | {f0} | {f1} | {rs} |")
    A("")

    A("## 6. 指标③ 拥堵形成—消散（events，5-min bin，06:00–12:00）\n")
    if tp:
        pv, pa, on = tp["v1.0"], tp["A-1"], tp["onset"]
        A("| 量 | v1.0 | A-1 | 倍率 |")
        A("|---|---:|---:|---:|")
        for key, lab in (("n_slow_max", "`max_t n_slow_links`"), ("enroute_max", "峰在途"),
                         ("queued_max", "峰排队"), ("stuck_max", "峰 stuck"),
                         ("peak_agg_vc_15min", "峰 `aggV/C`(15min)")):
            v0, v1 = pv[key], pa[key]
            rr = (v1 / v0) if v0 else float("nan")
            A(f"| {lab} | {v0:,.6g} | {v1:,.6g} | ×{rr:.3f} |")
        A(f"| 峰时刻 | `{pv['t_peak_hms']}` | `{pa['t_peak_hms']}` | — |")
        A(f"\n- 主判据（**3 倍**，PREREG §4.3 冻结）：`criterion = {on.get('criterion')}`；"
          f"`t_onset` = `{on['t_onset_hms']}`，`t_clear` = `{on['t_clear_hms']}`，"
          f"`duration` = `{on['duration_min']}` min")
        A(f"- 次级敏感性（1.5 倍，⛔ 不替代主判据）：`t_onset` = `{on.get('t_onset_1p5x_hms')}`，"
          f"`duration` = `{on.get('duration_min_1p5x')}` min")
        A(f"- ★口径自校验：v1.0 峰 `aggV/C`(15min) = **{pv['peak_agg_vc_15min']:.6f}** "
          f"@`{pv['peak_agg_vc_15min_hhmm']}` vs 7.7E E4 / A-0 §6 引用值 **0.102447**\n")
        A("[留痕] 原始配对差 `enroute_pair`（含 **+1/车** 结构性伪影）："
          f"v1.0 `{pv['enroute_pair_max']:,}` / A-1 `{pa['enroute_pair_max']:,}`；"
          "`enroute` 采用**在网车辆**口径，已与 legHistogram 交叉核对。\n")

    A("## 7. 指标④ 拥堵空间位置 + 7.3.6A 靶场锚定\n")
    A(f"靶场对账：crosswalk `{ta['rows_total']:,}` 行 / 主候选 `{ta['rows_primary']:,}` 行 / "
      f"唯一断面 `{ta['sections_primary']}` / 唯一匹配链 `{ta['links_primary']:,}`"
      f"（预注册预期 ≈576 / ≈3,015）。\n")
    A("| 量 | v1.0 | A-1 |")
    A("|---|---:|---:|")
    for key, lab in (("n_cong", "拥堵链数"), ("km_cong", "拥堵链里程 (km)"),
                     ("n_overlap", "∩靶场链数"), ("km_overlap", "∩靶场里程 (km)"),
                     ("overlap_len_share", "`overlap_len_share`"),
                     ("concentration_ratio", "`concentration_ratio`（全网上限分母）"),
                     ("concentration_ratio_loaded_denom", "`concentration_ratio`（载流链分母）")):
        A(f"| {lab} | {ov['v1.0'][key]:.4f} | {ov['A-1'][key]:.4f} |")
    cr = ov["A-1"]["concentration_ratio"]
    read = ("拥堵**向靶场聚集**（位置可能对）" if cr > 1.5 else
            "comparable（无证据）" if cr >= 0.67 else "拥堵**避开靶场**（= 堵错地方）")
    A(f"\n- 读法（§4.4）：`{cr:.3f}` ⇒ **{read}**\n")
    A("### 分道路类别（A-1）\n")
    A("| RoadCat | 链数 | 里程 km | 流量 | 拥堵链 | 拥堵里程 km | 真实延误车时 | 饱和链 |")
    A("|---|---:|---:|---:|---:|---:|---:|---:|")
    for r in s.get("by_roadcat", []):
        A(f"| {r['RoadCat']} | {r['n_links']:,} | {r['km_links']:.1f} | {r['flow']:,.0f} | "
          f"{r['n_cong']:,} | {r['km_cong']:.3f} | {r['excess_h']:,.1f} | {r['n_sat']:,} |")
    A("")

    A("## 8. 三层护栏\n")
    A("| run | 层 | 值 |")
    A("|---|---|---:|")
    for (rk, rv) in g.items():
        for lab, val in (("08-09 FROZEN Sim/Obs", rv["FROZEN"]),
                         ("POSITIVE_ONLY", rv["POSITIVE_ONLY"]),
                         ("BEST_DIRECTION", rv["BEST_DIRECTION"]),
                         ("it.19 FROZEN", rv["it19_FROZEN"]),
                         ("断面数", rv["n_sections"]), ("零流断面数", rv["n_zero_sim"])):
            A(f"| {rk} | {lab} | {val} |")
        fq = rv.get("flow_quality") or {}
        if fq:
            A(f"| {rk} | §5① Pearson r | {_fv(fq.get('pearson_r'))} |")
            A(f"| {rk} | §5① WMAPE | {_fv(fq.get('wmape'))} |")
            A(f"| {rk} | §5① GEH 中位数 | {_fv(fq.get('geh_median'), 3)} |")
            A(f"| {rk} | §5① GEH<5 / 5-10 / ≥10（断面数） | "
              f"{fq.get('geh_lt5')} / {fq.get('geh_5to10')} / {fq.get('geh_ge10')} |")
            A(f"| {rk} | §5① GEH<5 占比 | {_fv(fq.get('share_geh_lt5'))} |")
            A(f"| {rk} | §5① 口径断面数 | {fq.get('n_used')} |")
    # ★修复报告渲染硬编码：原文本恒定写 `≥ 0.85`（即使实测 0.7665 也照写"≥"），
    #   会把读者直接带到错误结论 ⇒ 现按**实测比较结果**动态渲染符号与判定。
    _so_a1 = g.get("A1", {}).get("FROZEN")
    _so_ok = (isinstance(_so_a1, (int, float)) and float(_so_a1) >= GUARDRAIL_SIM_OBS)
    A(f"\n★崩解护栏：`Sim/Obs(A-1) = {_so_a1}` "
      f"**{'>=' if _so_ok else '<'}** `{GUARDRAIL_SIM_OBS}` ⇒ "
      f"**{'未触发（PASS）' if _so_ok else '★触发（FAIL）'}**；")
    if not _so_ok:
        A("★ 该护栏触发 ⇒ 判决取 `SAMPLING_CAPACITY_NETWORK_BREAKDOWN`（预注册 §10），"
          "但**读法按 §7 情形分类**（见 §1 判决行与 "
          "`CALIBER_RESOLUTION_BREAKDOWN.md` 的**子义消歧**）："
          "本次是**流量层崩解**（断面级流量水平对不上），"
          "**不是** `stuck` / `never_arrived` 的**网络崩解**。")
    A(f"⛔ `Sim/Obs = 0.9993347697` **不是**本步目标；A-1 的 `Sim/Obs` **不得**被引用为对 v1.0 的标定证据。")
    A("")
    A("★§5 ① 的 `Pearson r / WMAPE / GEH 分布` 由 `flow_quality()` 计算（全断面池化、含零流断面），"
      "门 `A09b` 断言其**确实产出**。")
    A("⚠ **留痕**：该三项在 2026-09-29 的**死代码审计前从未被任何代码计算过** —— "
      "`pearson()`/`geh()` 自写下起就一直未被调用，A-0 脚本第 683 行只是把这三个词写进了**前向描述字符串**。")
    A("  ⇒ 本轮将其**补齐**，⛔ 未改动 §5 ① 的任何阈值（硬门仍是 `Sim/Obs ≥ 0.85`）。\n")

    A("## 9. 与 A-0 §6 零仿真上界投影对照\n")
    A("| 指标 | v1.0 实测 | A-0 上界投影 | A-1 实测 | 投影倍数 |")
    A("|---|---:|---:|---:|---:|")
    for lab, key, proj in (("`n(v/c ≥ 1.0)`", "n_vc_ge_10", 4187),
                           ("饱和里程 km", "sat_km", 178.114),
                           ("`n(v/c ≥ 0.5)`", "n_vc_ge_05", 16049),
                           ("`n(v/c ≥ 0.9)`", "n_vc_ge_09", 5413)):
        A(f"| {lab} | {vm[key]:,} | {proj:,} | {am[key]:,} | ×{proj/vm[key]:.2f} |")
    A("\n★ A-0 预先提示：即使按 sample-consistent 容量，峰 `aggV/C` 也只到 **0.236**、饱和里程只占 **1.18 %**")
    A("⇒ **仍不预期出现全网级拥堵波**。\n")

    A("## 10. 口径决议与留痕（⛔ 不改预注册）\n")
    A("1. **`N_cong` 阈值歧义**：预注册 §4.1 正文写 `excess_s ≥ 1.0`，但其登记基线 `7,985 / 3.56 %` ")
    A("   只能由 `excess_s > 0` 复现 ⇒ 双口径并报，主判据 = 登记基线。详见 `CALIBER_RESOLUTION_NCONG.md`。")
    A("2. **events 属性顺序**随事件类型而变（`entered link` 的 link 在 `tk[5]`，`departure` 的在 `tk[7]`）")
    A("   ⇒ 首版曾产出 `unknown_link = 161,380,248` 假值，已加硬门 `unknown_link == 0`。")
    A("3. **每辆车恰有 1 个未配对 `entered link`**（MATSim 末链不发 `left link`；实测 `n_pair_miss = 236,039`）")
    A("   ⇒ §4.3 对 `enroute(t)` 的**字面定义会产生物理上不可能的曲线**（峰 **236,039 @09:50** ≈ 全部车辆、")
    A("   随出发数单调增长）⇒ 改用**在网车辆**口径 `enroute = (#enters traffic − #leaves traffic) − |pending|`，")
    A("   字面口径保留为 `enroute_pair`。**交叉验证**：峰 **36,176 @08:55** vs 独立来源 `legHistogram.en-route`")
    A("   **36,799 @08:55** ⇒ **−1.69 %**（门 `B02` ±3 % 内，峰时完全一致）。影响 `acc_n` ≈0.29 %，两侧同源 ⇒ 相对判据免疫。")
    A("   ⇔ 详见 `CALIBER_RESOLUTION_ENROUTE.md`（本备忘为 `CALIBER_RESOLUTION_NCONG.md` 的姊妹件）。")
    A("4. **A-0 口径补齐**：`share_flow_on_saturated` 分母 = 全网总流量（v1.0 = 0.226 % 复现）；")
    A("   `peak_agg_vc_15min` = 7.7E E4 口径（`Σ rate / Σ capacity`，15 min bin）。")
    A("5. **出发/到达完整率（两口径，勿混用）**：**legHistogram 全天**口径下预注册 §10 字面要求")
    A("   `arrival == departure == 236,044` **成立**；但 **events 06:00–12:00 窗**口径会少 104 条")
    A("   `arrival`（落在窗外的迟到到达）⇒ 该窗口径不得用于完整性判据（见门禁 `A10/A10b/A11`）。")
    A("6. **★短链量化伪影 —— `N_slow` / `n_slow_links` 的绝对量不可直读**：指标① 的 `N_slow(cut)` 实测")
    A(f"   `cut=0 → {vm['n_slow_cut0']:,}`（占 `loaded` {vm['n_loaded']:,} 的 "
      f"**{100*vm['n_slow_cut0']/vm['n_loaded']:.1f} %**）→ `cut=50 → {vm['n_slow_cut50']:,}` → "
      f"`cut=100 → {vm['n_slow_cut100']:,}` → `cut=200 → {vm['n_slow_cut200']:,}`")
    A("   ⇒ 绝对量的 **≈99 %** 来自 **`LENGTH < 50 m`** 的短链（全网中位段长 11.0 m、`service` 占 65 %）。")
    A("   机制：`timeStepSize = 1 s` + `TT = ceil(FF)` ⇒ 11 m / 13.9 m·s⁻¹ 的自由流链（`ff` 仅 **0.79 s**）")
    A("   一旦被记为 **2 s**，`speed_ratio` 立刻跌到 **0.40** ⇒ **短链上「多 1 秒」= 速度比腰斩**。")
    A("   ⇒ **`N_slow` 与 events 侧 `n_slow_links(t)` 只能读「A-1 相对 v1.0 的同口径倍率」，绝对条数**")
    A("   **⛔ 不得解释为拥堵规模**。这也解释了为何 v1.0 `N_slow(cut=0)` 高达 117,168 而饱和链路只有 82：")
    A("   `N_slow` **不度量拥堵**，只度量「未达自由流」。该危害由 §4.1 的 `cut ∈ {0,50,100,200}` 四档并列呈现。")
    A("7. **★死代码审计（本轮新增，两类真实缺陷）**：")
    A("   (a) `events_cached()` 曾**定义但从未被调用**（调用点于 2026-09-29 11:09 的缓存键重构中丢失）")
    A("   ⇒ 缓存与 `parser_fingerprint()` 双双失效、正式跑白付 ~20 min × 2；**已重接并用")
    A("   `scripts/od/prewarm_events_7_9a1.py` 逐位证明缓存往返无损**。")
    A("   (b) `pearson()` / `geh()` 曾**定义但从未被调用**，而预注册 §5 ① **明文要求** Pearson r / WMAPE /")
    A("   GEH 分布 ⇒ 该三项在 **A-0 与 A-1 均未实际产出**（A-0 脚本第 683 行只是把这几个词写进了**前向")
    A("   描述字符串**）⇒ 本轮以 `flow_quality()` **补齐**，门 `A09b` 断言其确实产出。⛔ 未改动任何阈值。")
    A("8. **`CATB` / `CATC` 不存在**：预注册 §4.4 第 4 条与 §5 ① 所列 `RoadCat ∈ {CATA, CATB, CATC, SLIP_ROAD}`，")
    A("   而冻结靶场 `RoadCat` 实测**仅** `CATA`/`SLIP_ROAD` ⇒ `CATB`/`CATC` 按**空集**处理（**非缺失门禁**）。")
    A("   与 `\"CTE\" in name` 命中 0 同类：**过度规定**，已在 `NOTES` 与本节显式声明。\n")

    A("## 11. 红线复述（逐条继承 A-0 / PREREG §8）\n")
    for t in ("⛔ 不为了让 VIA 变红而提高 `demand`；",
              "⛔ 不为制造拥堵而降低容量 / 修改 `λ` / 修改 route-choice；",
              "⛔ 不为视觉效果重定义 congestion index；",
              "⛔ **不把 `0.434977` 表述为「为了让新加坡堵起来把容量砍到 43.5 %」**。"):
        A("- " + t)
    A("\n★ 正确表述：**「由于模型 population 按 43.4977 % 样本表示完整交通需求，而 QSim 的流量与存储容量")
    A("采用未经 sample adjustment 的 1.0 倍容量，因此首先检验 sample-consistent capacity representation；")
    A("该因子由 population representation 独立推导，不由交通观测误差反演。」**\n")

    A("## 12. 复现\n")
    A("```bash")
    A("python scripts/od/run_sampling_capacity_7_9a1.py --run --heap 24g   # 点火（20 迭代）")
    A("python scripts/od/audit_sampling_capacity_7_9a1.py                 # 完整评价（本报告）")
    A("python scripts/od/audit_sampling_capacity_7_9a1.py --check-v10     # v1.0 侧口径自检")
    A("```\n")
    A("## 附录 A：口径与审计备注（NOTES，逐条来自实测）\n")
    for i, t in enumerate(s.get("notes", []), 1):
        A(f"{i}. {t}")
    A("")
    A("## 附录：门禁清单（含实测值）\n")
    A("| 门 | 名称 | 结果 | 实测 |")
    A("|---|---|---|---|")
    for c in s["checks"]:
        tag = "PASS" if c["pass"] is True else ("FAIL" if c["pass"] is False else str(c["pass"]))
        A(f"| `{c['check']}` | {c['name']} | {tag} | {c['detail']} |")
    p = OUT / "STEP7_9A1_REPORT.md"
    p.write_text("\n".join(L) + "\n", encoding="utf-8")
    return p


# --------------------------------------------------------------------------
# main
# --------------------------------------------------------------------------
def main() -> int:
    global OUT, A1_LS, A1_LH, A1_EV, A1_OUT, A1_RUN, A1_INTEGRITY
    ap = argparse.ArgumentParser()
    ap.add_argument("--check-v10", action="store_true")
    ap.add_argument("--guardrail", action="store_true", help="含冻结模块护栏复算（较慢）")
    ap.add_argument("--no-events", action="store_true")
    ap.add_argument("--force-events", action="store_true")
    ap.add_argument("--dry-run-v10", action="store_true",
                    help="★空跑：把 A-1 输入指向 v1.0 自身产物（写沙盒 _dryrun_v10/），全部比值必须 == 1.0")
    args = ap.parse_args()

    DRY = bool(args.dry_run_v10)
    if DRY:
        OUT = OUT / "_dryrun_v10"
        OUT.mkdir(parents=True, exist_ok=True)
        A1_LS, A1_LH, A1_EV = V10_LS, V10_LH, V10_EV
        A1_OUT, A1_RUN = V10_OUT, V10_RUN
        A1_INTEGRITY = OUT / "_no_integrity.json"
        print("!! DRY-RUN：A-1 输入 = v1.0 自身产物（沙盒 %s）⇒ 全部比值必须 1.0" % OUT)

    t_start = time.time()
    print("=" * 92)
    print("Step 7.9A-1 评价器 — 采样一致性容量（sample-consistent capacity）（零仿真 / 只读）")
    print("=" * 92)

    # ---------------- [1] v1.0 载入 ----------------
    print("\n[1] 载入 v1.0 冻结产物")
    v10 = load_linkstats(V10_LS)
    gate("E01", "v1.0 it.19 linkstats 载入", len(v10) == 693575, f"n_links={len(v10)}")
    v10_lh = load_leg_hist(V10_LH)
    gate("E02", "v1.0 it.19 legHistogram 载入（5-min bin）", len(v10_lh) > 200,
         f"n_rows={len(v10_lh)}  span={v10_lh[0]['t']}..{v10_lh[-1]['t']}")

    # ---------------- [2] v1.0 基线 + 口径自检 ----------------
    print("\n[2] v1.0 基线（同时用于口径自检）")
    v10_m = face_metrics(v10, 1.0)
    gate("E03", "v1.0 复现 A-0 基线（82 / 1.151 km / 2,813 / 220）",
         v10_m["n_vc_ge_10"] == 82 and abs(v10_m["sat_km"] - 1.1514) < 0.01
         and v10_m["n_vc_ge_05"] == 2813 and v10_m["n_vc_ge_09"] == 220,
         f"n_ge1={v10_m['n_vc_ge_10']} sat_km={v10_m['sat_km']:.4f} "
         f"n_ge0.5={v10_m['n_vc_ge_05']} n_ge0.9={v10_m['n_vc_ge_09']}")
    # ★E04 双口径（预注册 §4.1 正文 >=1.0 与其登记基线 7,985 自相矛盾 ⇒ 双报，主判据取登记基线）
    gate("E04a", "v1.0 N_cong(cut=0, excess>0) == 预注册登记 7,985  ← 主判据",
         v10_m["n_cong_cut0"] == 7985, f"{v10_m['n_cong_cut0']}")
    record("E04b", "v1.0 N_cong_ge1s(cut=0, excess>=1.0) —— 预注册正文阈值（辅）",
           f"{v10_m['n_cong_ge1s']}  （占比 {100*v10_m['n_cong_ge1s']/v10_m['n_loaded']:.4f}%）")
    record("E04c", "口径决议：主判据 = excess>0（登记基线 7,985 / 3.56%），辅 = excess>=1.0（1,308）",
           "A-1 与 v1.0 同口径 ⇒ 相对判据不受影响；⛔ 不修改预注册（sha de15361a…）")
    print(f"     v1.0 基线 = " + json.dumps(
        {k: (round(v, 5) if isinstance(v, float) else v) for k, v in v10_m.items()},
        ensure_ascii=False))

    obs = load_observed()
    gate("E05", "观测 audit_trafficflow.csv 载入", len(obs) > 1000, f"n_LinkID={len(obs)}")
    xw = load_crosswalk_raw()
    tgt = target_anchor(xw)
    print(f"     7.3.6A crosswalk: rows={tgt['rows_total']} primary_rows={tgt['rows_primary']} "
          f"sections={tgt['sections_primary']} links={tgt['links_primary']}")
    NOTES.append(f"靶场对账：crosswalk rows={tgt['rows_total']} / primary={tgt['rows_primary']} / "
                 f"唯一断面={tgt['sections_primary']} / 唯一链={tgt['links_primary']}；"
                 f"预注册预期 ≈576 断面 / ≈3,015 匹配链。")
    _rc = xw.loc[xw["is_primary_candidate"] == True, "RoadCat"].value_counts().to_dict()  # noqa: E712
    NOTES.append(f"★RoadCat 构成（primary）：{_rc} ⇒ 预注册 §4.4 第 4 条与 §5 ① 原文所列 `CATB` / `CATC` "
                 f"在**冻结靶场中均不存在**（`RoadCat` 仅 {'/'.join(sorted(_rc))}）⇒ 按**空集**处理，"
                 f"**不是缺失门禁**；分组 ratio 按实际存在的 {'/'.join(sorted(_rc))} 出。")
    NOTES.append("★死代码审计（本轮新增）：`events_cached()` 曾定义但从未被调用（调用点于 2026-09-29 11:09 "
                 "的缓存键重构中丢失）⇒ 已重接；`pearson()`/`geh()` 曾定义但从未被调用 ⇒ 已由 "
                 "`flow_quality()` 起用，以补齐预注册 §5 ① 的 Pearson r / WMAPE / GEH 分布。"
                 "新增门 `A09b` 专防「预注册要求静默缺席」。")
    NOTES.append("★两份口径决议备忘（评价器侧，⛔ 预注册 sha `de15361a…` 一字未改）："
                 "① `CALIBER_RESOLUTION_NCONG.md` —— §4.1 `excess` 阈值文本缺陷（正文 `>=1.0` vs "
                 "登记基线 7,985 只能由 `>0` 复现）⇒ 双口径并报、主判据 = 登记基线；"
                 "② `CALIBER_RESOLUTION_ENROUTE.md` —— §4.3 `enroute(t)` 字面定义结构性不自洽"
                 "（末链不发 `left link` ⇒ 字面峰 236,039 @09:50 ≈ 全部车辆）⇒ 改用「在网车辆」口径，"
                 "与独立来源 `legHistogram.en-route` 36,799 @08:55 相差 −1.69 %（门 `B02` ±3 %）。"
                 "门 `A09c` 断言两份备忘均存在。")

    # ---------------- [2b] ★冻结模块护栏（统一口径） ----------------
    gr = {}
    if args.check_v10 or args.guardrail:
        print("\n[2b] ★冻结模块护栏复算（直接 import evaluate_demand_response_7_6f_1.eval_run）")
        ctx = guardrail_ctx(xw)
        RUN_V1 = {"label": "V1", "role": "frozen_v1_0_queue", "lambda": 0.075,
                  "f_demand": 1.180222, "N": N_SIM, "out_dir": V10_OUT, "run_id": V10_RUN,
                  "stage": "7.6H", "desc": "v1.0 冻结（queue, f_cap=1.0）"}
        gr["V1"] = guardrail_eval(RUN_V1, ctx)
        gate("E06", f"★口径自校验：冻结模块复算 v1.0 Sim/Obs == {SIM_OBS_FROZEN}（±1e-6）",
             abs(float(gr["V1"]["q"]["FROZEN"]) - SIM_OBS_FROZEN) < 1e-6,
             f"recomputed={float(gr['V1']['q']['FROZEN']):.10f}  sections={gr['V1']['n_sections']}  "
             f"零流={gr['V1']['n_zero_sim']}")
        print(f"     三口径（v1.0, 08-09, PRIMARY cycle）：FROZEN={gr['V1']['q']['FROZEN']:.7f}  "
              f"POSITIVE_ONLY={gr['V1']['q']['POSITIVE_ONLY']:.7f}  "
              f"BEST_DIRECTION={gr['V1']['q']['BEST_DIRECTION']:.7f}")
        NOTES.append(f"护栏断面数（冻结模块返回）={gr['V1']['n_sections']}；"
                     f"本评价器 crosswalk 主候选唯一断面={tgt['sections_primary']}"
                     f"（差 {tgt['sections_primary'] - gr['V1']['n_sections']:+d}），"
                     f"主候选唯一链={tgt['links_primary']}。")
        _fq = gr["V1"].get("flow_quality") or {}
        print(f"     ★§5 ① 流量层质量（v1.0，全断面池化含零流）："
              f"Pearson r={_fq.get('pearson_r')}  WMAPE={_fq.get('wmape')}  "
              f"GEH 中位={_fq.get('geh_median')}  "
              f"GEH<5={_fq.get('geh_lt5')}/{_fq.get('n_used')}")
        NOTES.append(f"§5 ① 流量层质量（v1.0）：Pearson r={_fq.get('pearson_r')} / "
                     f"WMAPE={_fq.get('wmape')} / GEH 中位={_fq.get('geh_median')} / "
                     f"GEH<5={_fq.get('geh_lt5')}、5-10={_fq.get('geh_5to10')}、"
                     f"≥10={_fq.get('geh_ge10')}（共 {_fq.get('n_used')} 断面）。")

    # ---------------- 输出 v1.0 自检 ----------------
    wjson(OUT / "_v10_selfcheck.json", {
        "v10_metrics": v10_m, "target_anchor": {k: v for k, v in tgt.items() if k != "links_primary_set"},
        "frozen_sim_obs": SIM_OBS_FROZEN, "guardrail_v1": gr.get("V1"),
        "notes": NOTES,
    })
    wcsv(OUT / "_a1_checks_partial.csv", ["check", "name", "pass", "detail"], CHECKS)

    if args.check_v10:
        hard = [c for c in CHECKS if c["pass"] is False]
        print("\n" + "=" * 92)
        n_gate = len([c for c in CHECKS if isinstance(c["pass"], bool)])
        n_pass = len([c for c in CHECKS if c["pass"] is True])
        print(f"  [--check-v10] v1.0 侧自检完成  {n_pass}/{n_gate} PASS"
              + (f"  失败 {[c['check'] for c in hard]}" if hard else ""))
        print(f"  耗时 {time.time()-t_start:.1f}s")
        print("=" * 92)
        return 0 if not hard else 1

    # ================= A-1 侧 =================
    if not A1_LS.exists():
        print(f"\n!! 尚未找到 A-1 linkstats：{A1_LS}")
        print("   请等待 run_sampling_capacity_7_9a1.py --run 完成。")
        return 3

    # 记录评价器自身 sha（跑前）
    ev_sha = {"script": "scripts/od/audit_sampling_capacity_7_9a1.py",
              "sha256": sha256(Path(__file__)), "frozen_at": time.strftime("%Y-%m-%d %H:%M:%S")}
    wjson(OUT / "a1_evaluator_sha.json", ev_sha)

    print("\n[3] 载入 A-1 产物")
    a1 = load_linkstats(A1_LS)
    gate("A01", "A-1 it.19 linkstats 载入且链路集与 v1.0 一致",
         len(a1) == 693575 and set(a1.keys()) == set(v10.keys()),
         f"n_links={len(a1)}  ∩v1.0={len(set(a1) & set(v10))}")
    if A1_LH.exists():
        a1_lh = load_leg_hist(A1_LH)
        gate("A02", "A-1 it.19 legHistogram 载入", len(a1_lh) > 200,
             f"n_rows={len(a1_lh)}  max_stuck_car={max(r['stuck'] for r in a1_lh)}")
    else:
        a1_lh = []
        gate("A02", "A-1 it.19 legHistogram 存在", False, "缺失")

    # 运行契约（来自 runner 的 integrity json）
    if A1_INTEGRITY.exists():
        integ = json.loads(A1_INTEGRITY.read_text(encoding="utf-8"))
        vd = str(integ.get("verdict") or integ.get("status") or "")
        # ★修复（假门禁，第 7 次同类复现）：
        #   原判据写死 `vd.startswith("PREPARED") or integ.get("ok") is True`。
        #   但 runner 在**跑完后会合法地**把 verdict 从 `PREPARED_AWAITING_RUN` 改写为
        #   `A1_RUN_COMPLETE`（该 json 内**没有** `ok` 键）⇒ A03 必然 FAIL
        #   ⇒ 因 `hard_fail` 非空把总判决压成 `FAILED`，**整轮结论被误毁**。
        #   正确语义（跑前 / 跑后 两个合法态都算通过）：
        #     跑前：verdict 以 `PREPARED` 开头；
        #     跑后：verdict ∈ 完成态 且 `failed == []`（允许存在 `WARN`，但不得有失败项）。
        _failed = integ.get("failed")
        _done = vd in ("A1_RUN_COMPLETE", "RUN_COMPLETE", "COMPLETE")
        ok_a03 = (vd.startswith("PREPARED") or integ.get("ok") is True
                  or (_done and (not _failed)))
        gate("A03", "A-1 运行契约门（verdict ∈ {PREPARED_AWAITING_RUN（跑前）, "
                    "A1_RUN_COMPLETE 且 failed==[]（跑后）}）",
             ok_a03,
             f"verdict={vd}  n_checks={integ.get('n_checks')}  n_pass={integ.get('n_pass')}  "
             f"failed={integ.get('failed')}")
        gate("A03b", "A-1 预注册 sha 与 runner 登记一致",
             str(integ.get("prereg_sha256")) == str(
                 json.loads((OUT / "a1_prereg_sha.json").read_text(encoding="utf-8"))["sha256"])
             if (OUT / "a1_prereg_sha.json").exists() else False,
             str(integ.get("prereg_sha256"))[:24] + "…")
        # config diff 白名单（恰 5 项、全部 whitelisted、两个 qsim 参数值为 0.434977）
        dcsv = A1_ROOT / "audit" / "config_diff_whitelist.csv"
        if dcsv.exists():
            rows = list(csv.DictReader(open(dcsv, encoding="utf-8-sig")))
            qs = [r for r in rows if r["key"].startswith("qsim.")]
            gate("A03c", "A-1 config diff 恰 5 项且全部白名单，qsim 两项 = 1.0→0.434977",
                 len(rows) == 5 and all(str(r["whitelisted"]).strip().lower() == "true" for r in rows)
                 and len(qs) == 2 and all(r["new"] == "0.434977" and r["src"] == "1.0" for r in qs),
                 f"n_diff={len(rows)}  n_qsim={len(qs)}  keys=" + ",".join(r["key"] for r in rows))
        else:
            record("A03c", "A-1 config diff 白名单", "缺失")
    else:
        integ = {}
        record("A03", "A-1 runner integrity json", "缺失（不阻断，但需人工确认）")

    # ---- §11 容量语义消解 ----
    print("\n[4] §11 CAPACITY 语义消解")
    cs = resolve_capacity_semantics(v10, a1)
    if DRY:
        cs = {**cs, "mode": "DRY_RUN_FORCED_EFFECTIVE", "cap_mul_v10": 1.0, "cap_mul_a1": 1.0,
              "note": "空跑：同一文件 ⇒ CAPACITY 逐位相同；为构成真正的零假设，强制两侧均按有效容量（×1.0）"}
    gate("A04", "§11 CAPACITY 语义已消解（三选一；空跑为 DRY_RUN_FORCED_EFFECTIVE）",
         cs["mode"] in ("BASE_CAPACITY", "EFFECTIVE_CAPACITY", "DRY_RUN_FORCED_EFFECTIVE"),
         f"mode={cs['mode']} identical={cs['n_identical']}/{cs['n_common']} "
         f"ratio_match={cs['n_ratio_match']}")
    cv = capacity_crossval(a1, cs["cap_mul_a1"], v10)
    capmul_a1_pre = cs["cap_mul_a1"] if cs["cap_mul_a1"] is not None else F_CAP
    if cs["cap_mul_a1"] is None:
        record("A05", "§11 交叉验证", "CAPACITY_SEMANTICS_UNRESOLVED ⇒ 不报 v/c（§11 第 1 条第三分支）")
    elif cv["status"] == "OK":
        gate("A05", "§11 交叉验证（HRS8-9avg > CAPACITY_eff 的条数 ≤ 100）", True,
             f"n_over={cv['n_over']}/{cv['n_flow']}")
    else:
        record("A05", "§11 交叉验证：大量流量超有效容量 ⇒ 规则可疑（两版数字同时报出）",
               f"n_over={cv['n_over']}/{cv['n_flow']} full_cap_over={cv['full_cap_over']}")

    # ---- ①② 指标 ----
    print("\n[5] 指标 ① ②（A-1 vs v1.0，同口径）")
    a1_m = face_metrics(a1, cs["cap_mul_a1"])
    v10_m2 = face_metrics(v10, cs["cap_mul_v10"] if cs["cap_mul_v10"] is not None else 1.0)
    if DRY:
        def _eq(x, y):
            if isinstance(x, float) and isinstance(y, float):
                return (x == y) or (x != x and y != y)
            return x == y
        diffs = [k for k in v10_m if not _eq(v10_m[k], a1_m[k])]
        gate("DRY1", "★空跑零假设：A-1 全部面部指标与 v1.0 逐位相同", not diffs,
             f"diffs={diffs[:8]}" if diffs else f"n_keys={len(v10_m)} 全部一致")
    rows = []
    for metric in ("n_cong_cut0", "n_cong_cut50", "n_cong_cut100", "n_cong_cut200",
                   "n_slow_cut0", "n_slow_cut50", "n_slow_cut100", "n_slow_cut200",
                   "n_cong_ge1s", "n_loaded"):
        for run, m in (("v1.0", v10_m2), ("A-1", a1_m)):
            rows.append({"metric": metric, "run": run, "value": m[metric],
                         "km": m.get(metric.replace("n_", "km_"), ""),
                         "share_of_loaded": (m[metric] / m["n_loaded"]) if m["n_loaded"] else float("nan")})
    for k in ("n_vc_ge_05", "n_vc_ge_09", "n_vc_ge_10", "n_vc_ge_15", "n_vc_ge_20"):
        for run, m in (("v1.0", v10_m2), ("A-1", a1_m)):
            rows.append({"metric": k, "run": run, "value": m[k], "km": "", "share_of_loaded": ""})
    for k in ("sat_km", "share_len_saturated", "share_flow_on_saturated", "max_vc", "max_vol",
              "peak_agg_vc", "delay_h", "net_km", "loaded_km"):
        for run, m in (("v1.0", v10_m2), ("A-1", a1_m)):
            rows.append({"metric": k, "run": run, "value": m[k], "km": "", "share_of_loaded": ""})
    wcsv(OUT / "a1_face_metrics.csv", ["metric", "run", "value", "km", "share_of_loaded"], rows)

    ratio = {}
    for k in ("n_cong_cut0", "n_cong_cut50", "n_cong_cut100", "n_cong_cut200",
              "n_slow_cut0", "n_slow_cut50", "n_slow_cut100", "n_slow_cut200",
              "n_cong_ge1s", "n_vc_ge_10", "n_vc_ge_05", "n_vc_ge_09", "n_vc_ge_15", "n_vc_ge_20",
              "sat_km", "delay_h", "peak_agg_vc", "share_len_saturated", "share_flow_on_saturated"):
        v0, v1 = v10_m2[k], a1_m[k]
        ratio[k] = {"v10": v0, "a1": v1, "ratio": (v1 / v0) if v0 else float("inf")}
    print("     ① 拥堵链路：N_cong(cut0) v1.0=%s → A-1=%s  (×%.3f)；N_slow(cut0) %s → %s (×%.3f)"
          % (v10_m2["n_cong_cut0"], a1_m["n_cong_cut0"], ratio["n_cong_cut0"]["ratio"],
             v10_m2["n_slow_cut0"], a1_m["n_slow_cut0"], ratio["n_slow_cut0"]["ratio"]))
    print("     ② 饱和：n(v/c>=1) %s → %s (×%.3f)；sat_km %.4f → %.4f (×%.3f)；max_v/c %.6f → %.6f"
          % (v10_m2["n_vc_ge_10"], a1_m["n_vc_ge_10"], ratio["n_vc_ge_10"]["ratio"],
             v10_m2["sat_km"], a1_m["sat_km"], ratio["sat_km"]["ratio"],
             v10_m2["max_vc"], a1_m["max_vc"]))
    print("     ①② 上界投影（A-0 §6）：n_ge1 4,187 / sat_km 178.114 / n_ge0.5 16,049 / n_ge0.9 5,413")

    # ---- ③ events ----
    ts_v10 = ts_a1 = None
    prof = {}
    if not args.no_events:
        print("\n[6] 指标 ③ events 时间过程（5-min bin，06:00–12:00）")
        link_index, L_arr, FS_arr, CAP_arr = build_link_index(v10)
        for tag, ev, cm in (("v1.0", V10_EV, 1.0), ("A-1", A1_EV, capmul_a1_pre)):
            if DRY and tag == "A-1":
                print("     [dry-run] A-1 events 直接复用 v1.0（同一文件）")
                ts_a1 = ts_v10
                continue
            if not ev.exists():
                print(f"     !! {tag} events 缺失：{ev}")
                continue
            t0 = time.time()
            # ★必须走 events_cached：v1.0 events 解析 ≈20 min，A-1 同量级。
            #   键 = 文件名 sha16 + cap_mul + 解析器指纹（见 parser_fingerprint）⇒
            #   改报告/门禁文案不会触发重解析；改 events_time_series 才会。
            r = events_cached(tag, ev, link_index, L_arr, FS_arr, CAP_arr, cm,
                              force=args.force_events)
            print(f"     {tag}: lines={r['n_lines']:,}  cells={r['n_cells']:,}  "
                  f"dep={r['sum_dep']:,}  arr={r['sum_arr']:,}  "
                  f"leave_traffic={r['n_leave_traffic']:,}  stuck={r['n_stuck']:,}  "
                  f"unknown_link={r['n_unknown_link']:,}  ({time.time()-t0:.0f}s)")
            cid = "C01" if tag == "v1.0" else "C02"
            gate(cid + "a", f"{tag} events 链路 id 全部命中 linkstats（unknown == 0）",
                 r["n_unknown_link"] == 0,
                 f"unknown={r['n_unknown_link']:,} / lines={r['n_lines']:,}")
            gate(cid + "b", f"{tag} events 出发数 == {N_SIM:,}", r["sum_dep"] == N_SIM,
                 f"dep={r['sum_dep']:,}  arr={r['sum_arr']:,}")
            if tag == "v1.0":
                ts_v10 = r
            else:
                ts_a1 = r
        wcsv(OUT / "a1_time_series.csv",
             ["run", "t", "t_hms", "n_slow_links", "n_queued", "enroute",
              "departures", "arrivals", "stuck", "n_enter", "n_left", "vkm", "veh_hours", "mean_speed_kmh"],
             [{"run": tag, "t": b["t"], "t_hms": b["t_hms"], "n_slow_links": b["n_slow_links"],
               "n_queued": b["queued_end"], "enroute": b["enroute_end"], "departures": b["dep"],
               "arrivals": b["arr"], "stuck": b["stuck"], "n_enter": b["n_enter"], "n_left": b["n_left"],
               "vkm": round(b["vkm"], 3), "veh_hours": round(b["vh"], 3),
               "mean_speed_kmh": round(b["mean_speed_kmh"], 3)}
              for tag, ts in (("v1.0", ts_v10), ("A-1", ts_a1)) if ts for b in ts["bins"]])
        if ts_v10 and ts_a1:
            pv, pa = ts_profile(ts_v10), ts_profile(ts_a1)
            ov = onset_vs_reference(ts_a1, ts_v10)
            prof = {"v1.0": pv, "A-1": pa, "onset": ov}
            # ★口径自校验：复现 7.7E E4 的 15-min 峰 aggV/C（A-0 §6 引用值 0.102447）
            gate("B01", "★口径自校验：v1.0 峰 aggV/C(15min) 复现 7.7E E4 = 0.102447（±2e-3）",
                 abs(pv["peak_agg_vc_15min"] - 0.10244692822003312) < 2e-3,
                 f"recomputed={pv['peak_agg_vc_15min']:.6f} @{pv['peak_agg_vc_15min_hhmm']}")
            print(f"     峰 aggV/C(15min)：v1.0={pv['peak_agg_vc_15min']:.6f} @{pv['peak_agg_vc_15min_hhmm']}"
                  f" → A-1={pa['peak_agg_vc_15min']:.6f} @{pa['peak_agg_vc_15min_hhmm']}"
                  f"  (×{pa['peak_agg_vc_15min']/pv['peak_agg_vc_15min'] if pv['peak_agg_vc_15min'] else float('nan'):.3f})"
                  f"   [A-0 §6 上界投影 0.235522]")
            print(f"     n_slow_links 峰值：v1.0={pv['n_slow_max']} → A-1={pa['n_slow_max']}"
                  f"  (×{pa['n_slow_max']/pv['n_slow_max'] if pv['n_slow_max'] else float('inf'):.3f})")
            print(f"     峰时刻：v1.0={pv['t_peak_hms']} → A-1={pa['t_peak_hms']}；"
                  f"onset={ov['t_onset_hms']} clear={ov['t_clear_hms']} duration={ov['duration_min']}")
            print(f"     峰在途：v1.0={pv['enroute_max']:,} → A-1={pa['enroute_max']:,}；"
                  f"峰排队（enters-traffic 未进链）：v1.0={pv['queued_max']:,} → A-1={pa['queued_max']:,}；"
                  f"stuck 峰：v1.0={pv['stuck_max']:,} → A-1={pa['stuck_max']:,}")
            print(f"     [留痕] 原始配对差 enroute_pair（含 +1/车 结构性伪影）："
                  f"v1.0={pv['enroute_pair_max']:,} / A-1={pa['enroute_pair_max']:,}"
                  f"  （v1.0 车辆数 = {N_SIM:,} ⇒ 伪影 = {pv['enroute_pair_max'] - N_SIM:+,}）")
            # ★与 legHistogram（MATSim 官方统计）交叉核对
            lh_v10_max = max(r["enroute"] for r in v10_lh) if v10_lh else None
            gate("B02", f"★③ 在途曲线交叉核对：events 峰在途 ≈ legHistogram 峰 en-route_car（±3%）",
                 lh_v10_max is not None and abs(pv["enroute_max"] - lh_v10_max) <= 0.03 * lh_v10_max,
                 f"events={pv['enroute_max']:,}  legHistogram={lh_v10_max:,}  "
                 f"Δ={100.0*(pv['enroute_max']-lh_v10_max)/lh_v10_max:+.3f}%")
            if a1_lh:
                lh_a1_max = max(r["enroute"] for r in a1_lh)
                print(f"     [核对] 峰在途 legHistogram：v1.0={lh_v10_max:,} → A-1={lh_a1_max:,}"
                      f"  (×{lh_a1_max/lh_v10_max if lh_v10_max else float('nan'):.3f})")
            # 与 legHistogram 交叉核对
            if a1_lh and v10_lh:
                record("A06", "③ 交叉核对 legHistogram：max stuck_car / max en-route_car",
                       f"v1.0 stuck={max(r['stuck'] for r in v10_lh):,} enroute={max(r['enroute'] for r in v10_lh):,}"
                       f" | A-1 stuck={max(r['stuck'] for r in a1_lh):,} enroute={max(r['enroute'] for r in a1_lh):,}")

    # ---- ④ 空间位置 ----
    print("\n[7] 指标 ④ 拥堵空间位置 + 7.3.6A 靶场锚定")
    labels = load_net_labels()
    xw_meta = {r["matsim_link_id"]: {"roadcat": r["RoadCat"]}
               for _, r in xw[xw["is_primary_candidate"] == True].iterrows()}  # noqa: E712
    a1_m_top = top_congestion(a1, labels, xw_meta)
    v10_m_top = top_congestion(v10, labels, xw_meta)
    wcsv(OUT / "a1_spatial_top500.csv",
         ["run", "rank", "LINK", "ORIG_ID", "highway", "RoadName", "RoadCat", "is_target_primary",
          "LENGTH_m", "h89", "TRAVELTIME8-9avg_s", "ff_ceil_s", "excess_s", "speed_ratio",
          "CAPACITY", "v_c_base"],
         [{"run": "A-1", **r} for r in a1_m_top] + [{"run": "v1.0", **r} for r in v10_m_top])

    cong_a1 = [k for k, d in a1.items()
               if d["h89"] > 0 and (d["tt89"] - ceil_ff(d["length"] / d["fs"] if d["fs"] > 0 else 0.0)) > 0]
    cong_v10 = [k for k, d in v10.items()
                if d["h89"] > 0 and (d["tt89"] - ceil_ff(d["length"] / d["fs"] if d["fs"] > 0 else 0.0)) > 0]
    ov_a1 = overlap_metrics(a1, cong_a1, tgt["links_primary_set"])
    ov_v10 = overlap_metrics(v10, cong_v10, tgt["links_primary_set"])
    wcsv(OUT / "a1_target_overlap.csv", ["run", *ov_a1.keys()],
         [{"run": "v1.0", **ov_v10}, {"run": "A-1", **ov_a1}])
    print(f"     靶场锚：{tgt['sections_primary']} 断面 / {tgt['links_primary']} 链"
          f"（预注册预期 576 / 3,015）")
    print(f"     overlap_len_share：v1.0={ov_v10['overlap_len_share']:.4f} → A-1={ov_a1['overlap_len_share']:.4f}")
    print(f"     base_rate（全网分母 15,126.5 km）= {ov_a1['base_rate_len_share_fullnet']:.4f}；"
          f"concentration_ratio：v1.0={ov_v10['concentration_ratio']:.3f} → A-1={ov_a1['concentration_ratio']:.3f}")
    rcat = by_roadcat(a1, xw)
    wcsv(OUT / "a1_by_roadcat.csv", ["RoadCat", "n_links", "km_links", "flow", "n_cong", "km_cong",
                                     "excess_h", "n_sat"], rcat)

    # ---- VIA 层 + 图 ----
    print("\n[8] VIA 属性层 + 空间位置图")
    capmul_a1 = cs["cap_mul_a1"] if cs["cap_mul_a1"] is not None else F_CAP
    n_tsv = write_via_tsv(OUT / "via_link_attributes_HRS8-9_A1.tsv", a1, labels, capmul_a1)
    gate("A07", "VIA 属性层写出（行数 == 693,575）", n_tsv == 693575, f"rows={n_tsv}")
    try:
        draw_map(OUT / "congestion_map_A1_HRS8-9.png", v10, a1, labels, tgt["links_primary_set"])
        gate("A08", "拥堵空间位置图写出（EPSG:3414）",
             (OUT / "congestion_map_A1_HRS8-9.png").exists(),
             f"{(OUT / 'congestion_map_A1_HRS8-9.png').stat().st_size} bytes")
    except Exception as exc:  # noqa: BLE001
        gate("A08", "拥堵空间位置图写出", False, f"{type(exc).__name__}: {exc}")

    # ---- 护栏 + 判决 ----
    print("\n[9] 护栏与判决")
    sim_obs_a1 = None
    ctx = guardrail_ctx(xw)
    if "V1" not in gr:
        RUN_V1 = {"label": "V1", "role": "frozen_v1_0_queue", "lambda": 0.075,
                  "f_demand": 1.180222, "N": N_SIM, "out_dir": V10_OUT, "run_id": V10_RUN,
                  "stage": "7.6H", "desc": "v1.0 冻结（queue, f_cap=1.0）"}
        gr["V1"] = guardrail_eval(RUN_V1, ctx)
        gate("E06", f"★口径自校验：冻结模块复算 v1.0 Sim/Obs == {SIM_OBS_FROZEN}（±1e-6）",
             abs(float(gr["V1"]["q"]["FROZEN"]) - SIM_OBS_FROZEN) < 1e-6,
             f"recomputed={float(gr['V1']['q']['FROZEN']):.10f}  sections={gr['V1']['n_sections']}")
    RUN_A1 = {"label": "A1", "role": "sampling_capacity_1overSCALE", "lambda": 0.075,
              "f_demand": 1.180222, "N": N_SIM, "out_dir": A1_OUT, "run_id": A1_RUN,
              "stage": "7.9A-1", "desc": "7.9A-1（queue, f_cap=0.434977，其余继承 v1.0）"}
    if DRY:
        print("     [dry-run] A-1 护栏直接复用 V1（同一产物，无需复算）")
        gr["A1"] = dict(gr["V1"])
    else:
        gr["A1"] = guardrail_eval(RUN_A1, ctx)
    sim_obs_a1 = float(gr["A1"]["q"]["FROZEN"])
    grid = []
    for run, r in (("v1.0", gr["V1"]), ("A-1", gr["A1"])):
        grid.append({"run": run, "layer": "流量层 08-09 FROZEN Sim/Obs", "value": r["q"]["FROZEN"]})
        grid.append({"run": run, "layer": "流量层 POSITIVE_ONLY", "value": r["q"]["POSITIVE_ONLY"]})
        grid.append({"run": run, "layer": "流量层 BEST_DIRECTION", "value": r["q"]["BEST_DIRECTION"]})
        grid.append({"run": run, "layer": "流量层 WMEAN_OF_RATIOS",
                     "value": r["q"].get("FROZEN_WMEAN_OF_RATIOS")})
        grid.append({"run": run, "layer": "流量层 断面数", "value": r["n_sections"]})
        grid.append({"run": run, "layer": "流量层 零流断面数", "value": r["n_zero_sim"]})
        grid.append({"run": run, "layer": "流量层 it.19 Sim/Obs", "value": r["q_19"]["FROZEN"]})
        # ★§5 ① 明文要求：Pearson r / WMAPE / GEH 分布（全断面池化，含零流断面）
        fq = r.get("flow_quality") or {}
        for lbl, key in (("Pearson r", "pearson_r"), ("WMAPE", "wmape"),
                         ("GEH 中位数", "geh_median"), ("GEH 均值", "geh_mean"),
                         ("GEH<5 断面数", "geh_lt5"), ("GEH 5-10 断面数", "geh_5to10"),
                         ("GEH>=10 断面数", "geh_ge10"), ("GEH<5 占比", "share_geh_lt5")):
            grid.append({"run": run, "layer": f"流量层 {lbl}", "value": fq.get(key)})
        grid.append({"run": run, "layer": "流量层 流量质量口径断面数", "value": fq.get("n_used")})
        for kind in ("MATCHED", "CATA", "SLIP", "ALL"):
            s = r["stab"].get(kind)
            if not s:
                continue
            grid.append({"run": run, "layer": f"稳定性层 {kind} A_10:19", "value": s["A_10_19"]})
            grid.append({"run": run, "layer": f"稳定性层 {kind} Qbar_10:19", "value": s["Qbar_10_19"]})
            grid.append({"run": run, "layer": f"稳定性层 {kind} Q_19", "value": s["Q_19"]})
            grid.append({"run": run, "layer": f"稳定性层 {kind} parity_gap_rel", "value": s["parity_gap_rel"]})
    # ★门禁名只写**判据**（不带实测值），实测值与比较符号放 detail —— 否则表格里会出现
    #   「Sim/Obs = 0.7664761 >= 0.85 | FAIL」这种**看起来自相矛盾**的行。
    gate("A09", f"★崩解护栏判据：Sim/Obs(A-1) >= {GUARDRAIL_SIM_OBS}",
         sim_obs_a1 >= GUARDRAIL_SIM_OBS,
         f"实测 {sim_obs_a1:.7f} {'>=' if sim_obs_a1 >= GUARDRAIL_SIM_OBS else '<'} "
         f"{GUARDRAIL_SIM_OBS}  （v1.0={gr['V1']['q']['FROZEN']:.7f}）")
    wcsv(OUT / "a1_guardrails.csv", ["run", "layer", "value"], grid)
    # ★存在性门禁（专防「预注册要求静默缺席」——本评价器已实际发生过的缺陷类型：
    #   `events_cached` 死代码、`pearson`/`geh` 死代码 ⇒ §5 ① 三项一度完全未产出）
    need = ("流量层 Pearson r", "流量层 WMAPE", "流量层 GEH 中位数",
            "流量层 GEH 5-10 断面数", "流量层 GEH<5 占比")
    have = {g["layer"] for g in grid if g.get("value") is not None}
    missing = [k for k in need if k not in have]
    fq_v1, fq_a1 = gr["V1"].get("flow_quality") or {}, gr["A1"].get("flow_quality") or {}
    gate("A09b", "★预注册 §5 ① 三项（Pearson r / WMAPE / GEH 分布）已**实际产出**（非死代码）",
         not missing,
         f"missing={missing}  rows={len(grid)}  "
         f"v1.0: r={fq_v1.get('pearson_r')!r} WMAPE={fq_v1.get('wmape')!r} "
         f"GEH<5={fq_v1.get('share_geh_lt5')!r}  "
         f"A-1: r={fq_a1.get('pearson_r')!r} WMAPE={fq_a1.get('wmape')!r}")
    print(f"     ★流量层质量（§5 ①）：v1.0  r={fq_v1.get('pearson_r'):.4f}  "
          f"WMAPE={fq_v1.get('wmape'):.4f}  GEH中位={fq_v1.get('geh_median'):.3f}  "
          f"GEH<5={fq_v1.get('geh_lt5')}/{fq_v1.get('n_used')}")
    print(f"                          A-1   r={fq_a1.get('pearson_r'):.4f}  "
          f"WMAPE={fq_a1.get('wmape'):.4f}  GEH中位={fq_a1.get('geh_median'):.3f}  "
          f"GEH<5={fq_a1.get('geh_lt5')}/{fq_a1.get('n_used')}")
    # ★备忘存在性门禁：报告引用的两份口径决议备忘必须真实存在（防「引用不存在的文件」）
    memos = ("CALIBER_RESOLUTION_NCONG.md", "CALIBER_RESOLUTION_ENROUTE.md")
    miss_memo = [m for m in memos if not (REPORT_ROOT / m).exists()]
    gate("A09c", "★报告引用的两份口径决议备忘均存在（§4.1 `excess` 阈值 / §4.3 `enroute`）",
         not miss_memo, f"memos={list(memos)}  missing={miss_memo}")
    # ★第三份决议备忘：§10 判决子义消歧（BREAKDOWN 的两类子义 + A03/A09 实现修复留痕）
    _memo_bd = "CALIBER_RESOLUTION_BREAKDOWN.md"
    gate("A09d", "★§10 判决子义消歧备忘存在（BREAKDOWN 子义分离 + A03/A09 实现修复留痕）",
         (REPORT_ROOT / _memo_bd).exists(), f"memo={_memo_bd}")
    print(f"     ★护栏（冻结模块，同口径）：v1.0 FROZEN={gr['V1']['q']['FROZEN']:.7f} → "
          f"A-1 FROZEN={sim_obs_a1:.7f}")
    print(f"       断面数：v1.0={gr['V1']['n_sections']}  A-1={gr['A1']['n_sections']}；"
          f"零流断面：v1.0={gr['V1']['n_zero_sim']}  A-1={gr['A1']['n_zero_sim']}")

    # 出发/到达完整率
    dep_arr_ok = None
    nonarr = {}
    if v10_lh:
        d0 = sum(r["dep"] for r in v10_lh)
        a0 = sum(r["arr"] for r in v10_lh)
        nonarr["v1.0"] = (d0 - a0) / d0 if d0 else float("nan")
    if a1_lh:
        d1 = sum(r["dep"] for r in a1_lh)
        a1v = sum(r["arr"] for r in a1_lh)
        nonarr["A-1"] = (d1 - a1v) / d1 if d1 else float("nan")
        record("A10", "③ 出发/到达完整率（legHistogram 全天合计）",
               f"v1.0 dep={d0:,} arr={a0:,} 未到达={d0-a0:,} ({100*nonarr['v1.0']:.4f}%) | "
               f"A-1 dep={d1:,} arr={a1v:,} 未到达={d1-a1v:,} ({100*nonarr['A-1']:.4f}%)")
        # ★预注册 §10 字面要求 arrival == departure == 236,044。
        #   ★实测（本题关键纠正）：用 **legHistogram 全天**口径时 v1.0 的未到达 = 0（满足字面）；
        #     但用 **events 06:00–12:00 窗**口径时会少 104 条 `arrival`（落在 12:00 之后）
        #     ⇒ 两个口径必须分开报，且判据取「相对 + 绝对上限」。
        dep_arr_ok = bool(nonarr["A-1"] <= max(0.01, 3.0 * nonarr["v1.0"]))
        gate("A10b", "③ 崩解口径：A-1 未到达率 ≤ 1 % 且 ≤ 3×v1.0（legHistogram 全天口径）",
             dep_arr_ok, f"A-1={100*nonarr['A-1']:.4f}%  v1.0={100*nonarr['v1.0']:.4f}%")
        NOTES.append(f"出发/到达完整率（两个口径，勿混用）："
                     f"**legHistogram 全天** v1.0 未到达 = {d0-a0}（{100*nonarr['v1.0']:.4f} %）、"
                     f"A-1 未到达 = {d1-a1v}（{100*nonarr['A-1']:.4f} %）⇒ 预注册 §10 字面 "
                     f"`arrival == departure == {N_SIM:,}` 在 legHistogram 口径下**成立**；"
                     f"而 **events 06:00–12:00 窗**会少 104 条 `arrival`（落在窗外的迟到到达）"
                     f"⇒ 该窗口径不得用于完整性判据。")
    if ts_a1:
        record("A11", "③ events 级完整率",
               f"dep={ts_a1['sum_dep']:,} arr={ts_a1['sum_arr']:,} "
               f"leave_traffic={ts_a1['n_leave_traffic']:,} unknown_link={ts_a1['n_unknown_link']:,} "
               f"pair_net={ts_a1['n_pair_net']:,}（结构性 +1/车 伪影）")

    # ---- 情形判定（§7）+ 判决（§10） ----
    # ★修复（判决实现偏离冻结文本；与 A03 同属「判决/门禁实现偏离」缺陷类）：
    #   原实现 `hard_fail = [c for c in CHECKS if c["pass"] is False]` 收录**全部** False 门，
    #   其中含崩解护栏门 `A09`（`Sim/Obs >= 0.85`）⇒ 只要 Sim/Obs < 0.85，A09 即 False
    #   ⇒ hard_fail 非空 ⇒ 直接命中首分支 `FAILED`；
    #   于是 `elif sim_obs_a1 < GUARDRAIL_SIM_OBS: NETWORK_BREAKDOWN` **永远不可达（死代码）**。
    #   预注册 §10 明文：`FAILED` = **契约门 / 冻结只读门**失败（或运行非 0 退出）；
    #   `Sim/Obs < 0.85`（及 `never_arrived` / `max_stuck_car` 超阈）⇒
    #   `SAMPLING_CAPACITY_NETWORK_BREAKDOWN`。⇒ 按 §10 把「崩解护栏门」从 hard_fail 中**分离**。
    #   ⛔ 未改任何阈值（`GUARDRAIL_SIM_OBS` 仍 = 0.85）；⛔ 未改预注册（sha `de15361a…` 不动）。
    BREAKDOWN_GATES = ("A09", "A10b")
    fails = [c["check"] for c in CHECKS if c["pass"] is False]
    breakdown = [c for c in fails if c in BREAKDOWN_GATES]
    hard_fail = [c for c in fails if c not in BREAKDOWN_GATES]

    r_sat = ratio["sat_km"]["ratio"]
    r_nc = ratio["n_cong_cut0"]["ratio"]
    flow_r = (sim_obs_a1 / gr["V1"]["q"]["FROZEN"]) if (sim_obs_a1 and "V1" in gr) else float("nan")
    if r_sat < 2.0:
        case = "C"
        case_txt = (f"情形 C：拥堵增强很少（sat_km ×{r_sat:.2f}、N_cong ×{r_nc:.2f}，均未跨数量级）"
                    f" ⇒ sample-capacity inconsistency 非主因；第二刀转 7.9B trafficDynamics")
    elif flow_r < 0.95:
        case = "D"
        case_txt = (f"情形 D：拥堵才变合理但流量指标恶化（sat_km ×{r_sat:.2f}、"
                    f"N_cong ×{r_nc:.2f}、Sim/Obs ×{flow_r:.3f}）"
                    f" ⇒ 检查 OD assignment / flow scale / capacity / departure 耦合")
    else:
        case = "A"
        case_txt = (f"情形 A：拥堵显著增强而流量基本保持（sat_km ×{r_sat:.2f}、"
                    f"Sim/Obs ×{flow_r:.3f}）"
                    f" ⇒ v1.0 轻拥堵主因 = sample-capacity representation inconsistency")
    print(f"     ★情形 = {case}")
    print(f"     {case_txt}")

    stuck_a1 = max((r["stuck"] for r in a1_lh), default=None)
    nonarr_a1 = nonarr.get("A-1")
    if hard_fail:
        verdict = "FAILED"
        reading = (f"契约门 / 冻结只读门失败：{hard_fail}（§7 情形 {case}）")
    elif breakdown or dep_arr_ok is False:
        verdict = "SAMPLING_CAPACITY_NETWORK_BREAKDOWN"
        reading = (f"崩解护栏触发 {breakdown or ['A10b（派生：dep_arr_ok = False）']}（§10）"
                   f" ⇒ 按 §7 情形 B 处置，⛔ **不把容量调回**。"
                   f"★子义消歧：本次触发的是 **流量层崩解护栏 `Sim/Obs < "
                   f"{GUARDRAIL_SIM_OBS}`**（实测 {sim_obs_a1:.7f}），"
                   f"**不是**「`stuck` / `never_arrived`」的网络崩解子义"
                   f"（A-1 max `stuck_car` = {stuck_a1}、legHistogram 全天未到达 = "
                   f"{100*nonarr_a1 if nonarr_a1 is not None else float('nan'):.4f} %）"
                   f"⇒ §7 情形分类实为 **{case}**：{case_txt}")
    else:
        verdict = "SAMPLING_CAPACITY_R0_READY"
        reading = f"§7 情形 {case}：{case_txt}"

    NOTES.append(
        f"★判决口径消歧（预注册 §10 的子义分离；⛔ 未改预注册 sha `de15361a…`）：§10 的 "
        f"`SAMPLING_CAPACITY_NETWORK_BREAKDOWN` 实际混装两类子义 —— "
        f"(i) **流量层崩解护栏**（`Sim/Obs < 0.85`，门 `A09`）；"
        f"(ii) **网络崩解**（`never_arrived` 或 `max_stuck_car` 超阈，门 `A10b`）。"
        f"本次实测：(i) **触发**（A-1 = {sim_obs_a1:.7f} < {GUARDRAIL_SIM_OBS}）；"
        f"(ii) **未触发**（max `stuck_car` = {stuck_a1}、全天未到达 = "
        f"{100*nonarr_a1 if nonarr_a1 is not None else float('nan'):.4f} %、"
        f"dep = arr = {N_SIM:,}）⇒ 判决取 `SAMPLING_CAPACITY_NETWORK_BREAKDOWN`，"
        f"但其**读法应按 §7 情形 {case}**，而非字面「网络崩解」。"
        f"⛔ 两种子义都**不**允许「把容量调回去」（§7 情形 B / §8 红线）。")
    NOTES.append(
        "★实现缺陷修复（本轮；与 A03 同属「判决实现偏离冻结文本」类）：原 `hard_fail` 收录"
        "**全部** False 门 ⇒ 崩解护栏门 `A09` 失败时总判决恒为 `FAILED`，"
        "预注册 §10 的 `SAMPLING_CAPACITY_NETWORK_BREAKDOWN` 分支为**死代码**。"
        "现按 §10 分离 `BREAKDOWN_GATES = ('A09', 'A10b')`。"
        "⛔ 阈值未动（`GUARDRAIL_SIM_OBS` = 0.85）；⛔ 判据未动；⛔ 预注册未动。")
    NOTES.append(
        "★`onset` 判据（预注册 §4.3）口径警告：`t_onset` = A-1 `n_slow_links(t)` "
        "**首次 ≥ v1.0 同一 bin 值的 3 倍**。v1.0 的 `n_slow_links` 在 07:00–08:55 基本"
        "**平台化**（≈2.9–3.07 万；短链量化伪影所致，见 §10 条目 6）⇒ A-1（峰值 3.79 万）"
        "在 07:00–09:00 内**根本达不到** 3 倍 ⇒ `t_onset = 09:20` **不代表拥堵自 09:20 才出现**，"
        "而代表「v1.0 曲线 09:00 后回落、A-1 仍高」的**交叉时刻**。"
        "⇒ 报告同时给出 1.5× 次级判据（`t_onset_1p5x`）；⛔ 不得把 `duration = 155 min` "
        "读作『拥堵总时长』，它只是该交叉判据下的相对时长。")

    # ---- summary ----
    summary = {
        "step": "7.9A-1", "verdict": verdict, "reading": reading,
        "prereg_sha256": json.loads((OUT / "a1_prereg_sha.json").read_text(encoding="utf-8"))["sha256"]
        if (OUT / "a1_prereg_sha.json").exists() else None,
        "evaluator_sha256": ev_sha["sha256"],
        "single_factor": {"qsim.flowCapacityFactor": F_CAP, "qsim.storageCapacityFactor": F_CAP},
        "one_over_SCALE": 1.0 / SCALE, "f_cap_6dp": F_CAP,
        "capacity_semantics": cs, "capacity_crossval": cv,
        "v10_baseline": v10_m, "a1_baseline": a1_m, "ratios": ratio,
        "time_profile": prof,
        "spatial_overlap": {"v1.0": ov_v10, "A-1": ov_a1},
        "target_anchor": {k: v for k, v in tgt.items() if k != "links_primary_set"},
        "guardrail": {k: {"FROZEN": v["q"]["FROZEN"], "POSITIVE_ONLY": v["q"]["POSITIVE_ONLY"],
                          "BEST_DIRECTION": v["q"]["BEST_DIRECTION"],
                          "it19_FROZEN": v["q_19"]["FROZEN"], "n_sections": v["n_sections"],
                          "n_zero_sim": v["n_zero_sim"],
                          "flow_quality": v.get("flow_quality")} for k, v in gr.items()},
        "by_roadcat": rcat, "notes": NOTES,
        "checks": CHECKS,
        "case_7_7": case, "case_text": case_txt,
        "hard_fail": hard_fail, "breakdown": breakdown,
        "zero_simulation_eval": True, "matsim_rerun_in_eval": False,
    }
    wjson(OUT / "a1_summary.json", summary)
    wcsv(OUT / "_a1_checks_partial.csv", ["check", "name", "pass", "detail"], CHECKS)
    rp = write_report(summary)
    print(f"     报告：{rp.relative_to(ROOT)}")

    print("\n" + "=" * 92)
    n_hard = len([c for c in CHECKS if c["pass"] is not False])
    print(f"  A-1 评价完成  判决 = {verdict}")
    print(f"  记录项 {len([c for c in CHECKS if c['pass'] == 'REC'])}  硬门失败 "
          f"{len(hard_fail)}  耗时 {time.time()-t_start:.0f}s")
    print("=" * 92)
    return 0 if verdict != "FAILED" else 1


if __name__ == "__main__":
    sys.exit(main())
