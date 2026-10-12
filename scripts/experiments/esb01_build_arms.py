#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""
esb01_build_arms.py — E-SB-01「SpeedBand 拟合」旁路实验：臂派生 + 硬门 + 可行性预筛
====================================================================================
定位（★非 v1.1、非基线、非校准结论；仅作旁路试验）
--------------------------------------------------
    EXPERIMENT ONLY / NOT v1.1 / NOT FORMAL BASELINE / NOT CALIBRATED MODEL

允许的杠杆（用户裁定 2026-10-07）：**供给/容量侧** 或 **网络机制（信号/交叉口/排队）**。
每个臂 = **单因子**，与冻结 W01 配置全展开 diff 必须**恰为白名单集合**；多一项 ⇒ FAIL 并中止。

臂表
----
  SB-A1  网络机制(排队) : qsim.trafficDynamics  queue -> kinematicWaves        [配置层]
  SB-A2  机制(存储)     : qsim.storageCapacityFactor 1.0 -> 0.434977           [配置层]
  SB-A3  供给(定向容量) : 新网络, capacity *= m(l)（由 obs-sim 缺口反演）      [网络层]
  SB-A3n 负例(打乱)     : 同 A3 的 m 边际分布，但**空间打乱**                [网络层]
  SB-A4  oracle(自由流) : 新网络, 匹配链 freespeed <- 观测 AM 速度（上界参考） [网络层]

基线
----
  **v1.0 冻结模型本身即 20 迭代基线**（Sim/Obs cycle = 0.9993347696792919，SpeedBand RMSE=18.235）。
  不另设 S0 臂；所有臂与 v1.0 同迭代、同 seed、同人口、同网络（除网络层臂）。

⛔ 不动：v1.0 目录 / network_cleaned / plans / crosswalk / TrafficFlow / SpeedBand 原始值 / 评价器阈值。
   网络层臂的产物写入实验专属 networks/，**绝不覆盖** reports/matsim_network/。

用法
----
    python scripts/experiments/esb01_build_arms.py                  # 建全部臂 + 硬门 + 可行性预筛（零仿真）
    python scripts/experiments/esb01_build_arms.py --arms SB-A1     # 只建指定臂
    python scripts/experiments/esb01_build_arms.py --verify         # 只复核既有臂
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import os
import re
import sys
import gzip
from datetime import datetime
from pathlib import Path
import numpy as np
import pandas as pd
import xml.etree.ElementTree as ET

ROOT = Path(r"D:\Luan\2026-05\2_Singapore")

# --------------------------------------------------------------------------
# 冻结源（只读）
# --------------------------------------------------------------------------
SRC_CONFIG = ROOT / "matsim_final_7_6h" / "configs" / "config_W01_rc_min.xml"
SRC_NETWORK = ROOT / "reports" / "matsim_network" / "network_cleaned.xml.gz"
SRC_PLANS = ROOT / "matsim_final_7_6h" / "populations" / "pop_W01" / "population_lambda_0p075.xml.gz"
V10_OUT = ROOT / "matsim_final_7_6h" / "outputs" / "W01_rc_min"
V10_LS = V10_OUT / "ITERS" / "it.19" / "W01_rc_min.19.linkstats.txt.gz"

# LTA 观测 ↔ MATSim 链路（已核验三跳）
NETWORK_LINKS = ROOT / "reports" / "od_impedance" / "network_links.csv"
SB_MATCH = ROOT / "reports" / "od_impedance_ampeak" / "lta_osm_ampeak_speed_match.csv"

# --------------------------------------------------------------------------
# 实验根（旁路）
# --------------------------------------------------------------------------
EXP_ROOT = ROOT / "experiments" / "E-SB-01_speedband_fit"
CONFIG_DIR = EXP_ROOT / "configs"
NET_DIR = EXP_ROOT / "networks"
OUT_ROOT = EXP_ROOT / "outputs"
LOG_DIR = EXP_ROOT / "logs"
AUDIT_DIR = EXP_ROOT / "audit"

# --------------------------------------------------------------------------
# 冻结真值（实测登记）
# --------------------------------------------------------------------------
EXPECT_SRC_CONFIG_SHA16 = "8f44fb349bff9cf1"
EXPECT_NETWORK_SHA16 = "f55795995b87d330"
EXPECT_PLANS_SHA16 = "e96ed83ff59c0f5e"
EXPECT_SEED = "4711"
EXPECT_THREADS = "8"
EXPECT_ITER = 19
EXPECT_N_LINKS = 693575
SCALE = 2.29897
F_CAP_EQ = "0.434977"          # 1/SCALE
BAND8_PROXY = 75.0

# 定向容量反演
M_FLOOR = 0.15                 # capacity 乘子下限（避免退化网络）
V_FLOOR_KMH = 5.0              # freespeed 下限

CHECKS: list[dict] = []


# --------------------------------------------------------------------------
# 工具
# --------------------------------------------------------------------------
def sha16(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()[:16]


def rd(p: Path) -> str:
    return io.open(p, encoding="utf-8", newline="").read()


def gate(cid: str, name: str, ok: bool, detail: str = "") -> bool:
    CHECKS.append({"check": cid, "name": name, "pass": bool(ok), "detail": str(detail)})
    print("  [%s] %-12s %s%s" % ("PASS" if ok else "FAIL", cid, name,
                                ("  (%s)" % detail) if detail else ""), flush=True)
    return bool(ok)


def all_params(path: Path) -> dict:
    root = ET.parse(str(path)).getroot()
    out: dict[str, str] = {}

    def walk_ps(ps, prefix):
        for p in ps.findall("param"):
            out["%s.%s" % (prefix, p.get("name"))] = p.get("value")
        for sub in ps.findall("parameterset"):
            walk_ps(sub, "%s.%s" % (prefix, sub.get("name")))

    for mod in root.findall("module"):
        mn = mod.get("name")
        for p in mod.findall("param"):
            out["%s.%s" % (mn, p.get("name"))] = p.get("value")
        for ps in mod.findall("parameterset"):
            walk_ps(ps, "%s.%s" % (mn, ps.get("name")))
    return out


def _module_span(txt: str, module: str):
    m = re.search(r'<module\s+name="%s"\s*>' % re.escape(module), txt)
    if not m:
        return None
    s = m.end()
    e = txt.find("</module>", s)
    return (s, e) if e >= 0 else None


def set_param_in_module(txt: str, module: str, name: str, value: str):
    span = _module_span(txt, module)
    if span is None:
        return txt, 0, None
    s, e = span
    body = txt[s:e]
    pat = re.compile(r'(<param\s+name="%s"\s+value=")([^"]*)(")' % re.escape(name))
    hits = pat.findall(body)
    if len(hits) != 1:
        return txt, len(hits), (hits[0][1] if hits else None)
    return txt[:s] + pat.sub(lambda m: m.group(1) + value + m.group(3), body, count=1) + txt[e:], 1, hits[0][1]


def set_unique_param(txt: str, name: str, value: str):
    pat = re.compile(r'(<param\s+name="%s"\s+value=")([^"]*)(")' % re.escape(name))
    hits = pat.findall(txt)
    if len(hits) != 1:
        return txt, len(hits), (hits[0][1] if hits else None)
    return pat.sub(lambda m: m.group(1) + value + m.group(3), txt, count=1), 1, hits[0][1]


# --------------------------------------------------------------------------
# 观测层：LTA SpeedBand → MATSim 链路（与诊断同源）
# --------------------------------------------------------------------------
def band_of_speed(v):
    v = np.asarray(v, float)
    return np.clip(np.floor(v / 10.0) + 1.0, 1, 8).astype(int)


def build_obs_links() -> pd.DataFrame:
    net = pd.read_csv(NETWORK_LINKS, encoding="utf-8-sig", low_memory=False,
                      usecols=["from_node", "to_node", "length_m", "highway", "name"])
    m = pd.read_csv(SB_MATCH, encoding="utf-8-sig")
    idx = m.osm_edge_index.to_numpy(int)
    m = m.assign(
        matsim_link=["e%d_%d" % (a, b) for a, b in
                     zip(net.from_node.to_numpy(int)[idx], net.to_node.to_numpy(int)[idx])],
        highway=net.highway.astype(str).str.lower().str.strip().to_numpy()[idx])
    obs = (m.groupby("matsim_link", as_index=False)
             .agg(obs_speed_kmh=("am_speed_kmh", "median"),
                  n_lta=("LinkID", "size"), highway=("highway", "first")))
    obs["obs_band"] = band_of_speed(obs.obs_speed_kmh)
    return obs


def load_v10_linkstats() -> pd.DataFrame:
    return pd.read_csv(V10_LS, sep="\t", compression="gzip",
                       usecols=["LINK", "LENGTH", "FREESPEED", "CAPACITY", "HRS8-9avg"],
                       dtype={"LINK": str}, low_memory=False)


# --------------------------------------------------------------------------
# 网络层臂：定向修改
# --------------------------------------------------------------------------
LINK_RE = re.compile(r'<link\s+([^>]*?)/?>')
ATTR_RE = re.compile(r'(\w+)="([^"]*)"')


def _read_network_lines(path: Path):
    with gzip.open(path, "rt", encoding="utf-8") as f:
        return f.readlines()


def build_network_arm(arm: str, mod: dict[str, dict[str, str]]) -> Path:
    """按 arm 生成新网络（逐行改属性，其余字节不变）。"""
    NET_DIR.mkdir(parents=True, exist_ok=True)
    out = NET_DIR / f"network_{arm}.xml.gz"
    n_link = 0
    n_touched = 0
    lines = _read_network_lines(SRC_NETWORK)
    with gzip.open(out, "wt", encoding="utf-8", newline="") as f:
        for ln in lines:
            if "<link " in ln and 'id="' in ln:
                n_link += 1
                m = LINK_RE.search(ln)
                if m:
                    attrs = dict(ATTR_RE.findall(m.group(1)))
                    lid = attrs.get("id", "")
                    if lid in mod:
                        new_ln = ln
                        for k, v in mod[lid].items():
                            new_ln = re.sub(r'(\b%s=")([^"]*)(")' % re.escape(k),
                                            lambda mm: mm.group(1) + v + mm.group(3), new_ln, count=1)
                        if new_ln != ln:
                            n_touched += 1
                        ln = new_ln
            f.write(ln)
    gate(f"{arm}-N1", f"{arm} 网络链路数 == {EXPECT_N_LINKS}",
         n_link == EXPECT_N_LINKS, "n=%d" % n_link)
    gate(f"{arm}-N2", f"{arm} 实际改动链路数 == 目标数（无越界）",
         n_touched == len(mod), "touched=%d target=%d" % (n_touched, len(mod)))
    return out


# --------------------------------------------------------------------------
# 臂注册
# --------------------------------------------------------------------------
def config_whitelist(arm: str, out_dir: Path, net_override: Path | None) -> dict:
    wl = {
        "outputDirectory": str(out_dir),
        "runId": arm,
        "writeEventsInterval": str(EXPECT_ITER),
    }
    if arm == "SB-A1":
        wl["trafficDynamics"] = "kinematicWaves"
    elif arm == "SB-A2":
        wl["storageCapacityFactor"] = F_CAP_EQ
    if net_override is not None:
        wl["inputNetworkFile"] = str(net_override)
    return wl


def build_config(arm: str, net_override: Path | None) -> Path:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    out_dir = OUT_ROOT / arm
    new_cfg = CONFIG_DIR / f"config_{arm}.xml"
    wl = config_whitelist(arm, out_dir, net_override)

    txt = rd(SRC_CONFIG)
    n0 = len(re.findall(r"<param\b", txt))
    applied = []

    # 输出层
    for name in ("outputDirectory", "runId", "writeEventsInterval"):
        txt, n, old = set_unique_param(txt, name, wl[name])
        if not gate(f"{arm}-C-{name}", f"{arm} controller.{name} 唯一命中", n == 1, "old=%r" % (old,)):
            return new_cfg
        applied.append({"module": "controller", "param": name, "old": old, "new": wl[name]})

    if not gate(f"{arm}-C-chk", f"{arm} param 总数不变", len(re.findall(r"<param\b", txt)) == n0):
        return new_cfg

    # 网络
    if net_override is not None:
        txt, n, old = set_unique_param(txt, "inputNetworkFile", str(net_override))
        if not gate(f"{arm}-C-net", f"{arm} network.inputNetworkFile 唯一命中", n == 1,
                    "old=%s" % Path(old).name if old else "None"):
            return new_cfg
        applied.append({"module": "network", "param": "inputNetworkFile", "old": old, "new": str(net_override)})

    # 机制层（只在该 module 内改）
    if arm == "SB-A1":
        txt, n, old = set_param_in_module(txt, "qsim", "trafficDynamics", "kinematicWaves")
        if not gate(f"{arm}-C-dyn", f"{arm} qsim.trafficDynamics 唯一命中且旧值=queue",
                    n == 1 and old == "queue", "old=%r n=%d" % (old, n)):
            return new_cfg
        applied.append({"module": "qsim", "param": "trafficDynamics", "old": old, "new": "kinematicWaves"})
    if arm == "SB-A2":
        txt, n, old = set_param_in_module(txt, "qsim", "storageCapacityFactor", F_CAP_EQ)
        if not gate(f"{arm}-C-sto", f"{arm} qsim.storageCapacityFactor 唯一命中且旧值=1.0",
                    n == 1 and old in ("1.0", "1.00", "1"), "old=%r n=%d" % (old, n)):
            return new_cfg
        applied.append({"module": "qsim", "param": "storageCapacityFactor", "old": old, "new": F_CAP_EQ})

    io.open(new_cfg, "w", encoding="utf-8", newline="").write(txt)

    # ---- 全展开 diff ----
    a, b = all_params(SRC_CONFIG), all_params(new_cfg)
    diff = [{"key": k, "src": a.get(k), "new": b.get(k)} for k in sorted(set(a) | set(b)) if a.get(k) != b.get(k)]
    wlkeys = set(wl)
    non_wl = [d for d in diff if d["key"].split(".")[-1] not in wlkeys]
    gate(f"{arm}-M1", f"{arm} 配置 diff == 白名单（{len(wl)} 项）",
         len(diff) == len(wl) and not non_wl,
         "diff=%d 非白名单=%s" % (len(diff), [d['key'] for d in non_wl][:4]))

    # ---- 继承断言 ----
    inherit = {
        "global.randomSeed": EXPECT_SEED,
        "global.numberOfThreads": EXPECT_THREADS,
        "controller.lastIteration": str(EXPECT_ITER),
        "plans.inputPlansFile": str(SRC_PLANS),
        "qsim.flowCapacityFactor": a.get("qsim.flowCapacityFactor"),
        "qsim.timeStepSize": a.get("qsim.timeStepSize"),
        "qsim.stuckTime": a.get("qsim.stuckTime"),
        "qsim.linkDynamics": a.get("qsim.linkDynamics"),
        "replanning.fractionOfIterationsToDisableInnovation": a.get("replanning.fractionOfIterationsToDisableInnovation"),
        "scoring.learningRate": a.get("scoring.learningRate"),
        "linkStats.writeLinkStatsInterval": "1",
    }
    if arm not in ("SB-A1",):
        inherit["qsim.trafficDynamics"] = a.get("qsim.trafficDynamics")
    if arm not in ("SB-A2",):
        inherit["qsim.storageCapacityFactor"] = a.get("qsim.storageCapacityFactor")
    if net_override is None:
        inherit["network.inputNetworkFile"] = str(SRC_NETWORK)
    bad = {k: (v, b.get(k)) for k, v in inherit.items() if b.get(k) != v}
    gate(f"{arm}-M2", f"{arm} 继承断言（seed/线程/迭代/人口/未触碰参数逐位不变）",
         not bad, "drift=%s" % (bad if bad else "NONE"))

    json.dump({"arm": arm, "applied": applied, "diff": diff, "whitelist": wl,
               "n_params_src": len(a), "n_params_new": len(b)},
              io.open(AUDIT_DIR / f"{arm}_config_applied.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)
    return new_cfg


# --------------------------------------------------------------------------
# 定向供给派生 + 可行性预筛（零仿真）
# --------------------------------------------------------------------------
def make_target_layers():
    obs = build_obs_links()
    ls = load_v10_linkstats()
    d = obs.merge(ls, left_on="matsim_link", right_on="LINK", how="inner")
    d["v_f"] = d.FREESPEED.to_numpy(float) * 3.6
    d["q"] = d["HRS8-9avg"].fillna(0.0)
    d["c"] = d["CAPACITY"].fillna(0.0)
    d["vc"] = np.where(d.c > 0, d.q / d.c, np.nan)
    d["km"] = d["LENGTH"].to_numpy(float) / 1000.0

    # --- A3: 容量乘子反演 m = clip( (q/c) * (v_o / v_f), M_FLOOR, 1 ) ---
    with np.errstate(divide="ignore", invalid="ignore"):
        m = (d.q / d.c) * (d.obs_speed_kmh / d.v_f)
    d["m_raw"] = m
    d["m"] = np.clip(np.where(np.isfinite(m), m, 1.0), M_FLOOR, 1.0)
    d["feasible_A3"] = (d.m_raw >= M_FLOOR) & (d.m_raw < 1.0)      # 真正可被削到饱和的链
    d["infeasible_A3"] = (d.m_raw < M_FLOOR)                       # 需求太低,削容量也无法饱和

    # --- A4: freespeed <- max(obs, floor) ---
    d["fs_new_ms"] = np.maximum(d.obs_speed_kmh, V_FLOOR_KMH) / 3.6
    d["fs_old_ms"] = d.FREESPEED.to_numpy(float)

    # 可行性预筛（按道路等级）
    rows = []
    for hw, g in d.groupby("highway"):
        rows.append({
            "highway": hw, "n": int(len(g)), "km": float(g.km.sum()),
            "obs_mean": float(g.obs_speed_kmh.mean()), "sim_ff_mean": float(g.v_f.mean()),
            "vc_median": float(np.nanmedian(g.vc)), "vc_ge_1_pct": float((g.vc >= 1).mean() * 100),
            "m_median": float(np.median(g.m)),
            "A3_feasible_pct": float(g.feasible_A3.mean() * 100),
            "A3_feasible_km": float(g.loc[g.feasible_A3, "km"].sum()),
            "A4_changed_pct": float((np.abs(g.fs_new_ms - g.fs_old_ms) > 1e-9).mean() * 100),
        })
    feas = pd.DataFrame(rows).sort_values("n", ascending=False)
    feas.to_csv(AUDIT_DIR / "esb01_feasibility_by_highway.csv", index=False, encoding="utf-8-sig")

    overall = {
        "n_matched_links": int(len(d)), "km_matched": float(d.km.sum()),
        "n_with_flow": int((d.q > 0).sum()),
        "A3_feasible_n": int(d.feasible_A3.sum()),
        "A3_feasible_pct": float(d.feasible_A3.mean() * 100),
        "A3_feasible_km": float(d.loc[d.feasible_A3, "km"].sum()),
        "A3_infeasible_demand_too_low_n": int(d.infeasible_A3.sum()),
        "A3_infeasible_pct": float(d.infeasible_A3.mean() * 100),
        "A3_infeasible_km": float(d.loc[d.infeasible_A3, "km"].sum()),
        "vc_ge_1_pct": float((d.vc >= 1).mean() * 100),
        "vc_median": float(np.nanmedian(d.vc)), "vc_mean": float(np.nanmean(d.vc)),
        "m_median": float(np.median(d.m)), "m_min": float(d.m.min()),
        "M_FLOOR": M_FLOOR, "V_FLOOR_KMH": V_FLOOR_KMH,
        # 注：A3 只纳入「数值确实变化」的链；A4 同理
        "A3_ndiff": int((d.m < 1.0 - 1e-9).sum()),
        "A4_ndiff": int((np.abs(d.fs_new_ms - d.fs_old_ms) > 1e-9).sum()),
        "A4_changed_pct": float((np.abs(d.fs_new_ms - d.fs_old_ms) > 1e-9).mean() * 100),
    }
    print("\n  [可行性预筛]")
    print("     匹配链 %d (%.1f km)；有流 %d" %
          (overall["n_matched_links"], overall["km_matched"], overall["n_with_flow"]))
    print("     v/c 中位 %.4f 均值 %.4f；v/c≥1 仅 %.2f%%" %
          (overall["vc_median"], overall["vc_mean"], overall["vc_ge_1_pct"]))
    print("     A3 定向容量: 可饱和(可减速) %d 链 / %.1f km (%.1f%%)；需求过低不可行 %d 链 / %.1f km (%.1f%%)" %
          (overall["A3_feasible_n"], overall["A3_feasible_km"], overall["A3_feasible_pct"],
           overall["A3_infeasible_demand_too_low_n"], overall["A3_infeasible_km"], overall["A3_infeasible_pct"]))
    print("     A4 抑制自由流: 将改变 %d 链 (%.1f%%)" % (overall["A4_ndiff"], overall["A4_ndiff"] / len(d) * 100))

    # 生成 mod 字典（★按**网络写入格式的字符串**判定真变化，杜绝四舍五入伪改动）
    # 源网络写入格式: freespeed = '%.6f', capacity = '%.3f'
    fs_new_s = np.array(["%.6f" % x for x in d.fs_new_ms.to_numpy(float)])
    fs_old_s = np.array(["%.6f" % x for x in d.fs_old_ms.to_numpy(float)])
    cap_new_s = np.array(["%.3f" % max(a * b, 1.0) for a, b in zip(d.c.to_numpy(float), d.m.to_numpy(float))])
    cap_old_s = np.array(["%.3f" % x for x in d.c.to_numpy(float)])

    mA3 = (cap_new_s != cap_old_s) & (d.c.to_numpy(float) > 0) & (d.m.to_numpy(float) < 1.0)
    m3 = {d.iloc[i].matsim_link: {"capacity": cap_new_s[i]} for i in np.where(mA3)[0]}

    # 打乱负例：同 (c,m) 边际分布，空间错配
    idx3 = np.where(mA3)[0]
    rng = np.random.default_rng(20261007)
    perm = rng.permutation(len(idx3))
    m3n = {d.iloc[idx3[i]].matsim_link: {"capacity": cap_new_s[idx3[perm[i]]]}
           for i in range(len(idx3))}

    mA4 = fs_new_s != fs_old_s
    m4 = {d.iloc[i].matsim_link: {"freespeed": fs_new_s[i]} for i in np.where(mA4)[0]}
    return overall, {"SB-A3": m3, "SB-A3n": m3n, "SB-A4": m4}


# --------------------------------------------------------------------------
def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--arms", nargs="*", default=None)
    ap.add_argument("--verify", action="store_true")
    a = ap.parse_args()

    for d in (CONFIG_DIR, NET_DIR, OUT_ROOT, LOG_DIR, AUDIT_DIR):
        d.mkdir(parents=True, exist_ok=True)

    print("=" * 84)
    print("E-SB-01  SpeedBand 拟合旁路实验  (EXPERIMENT ONLY / NOT v1.1)")
    print("  冻结源配置 : %s" % SRC_CONFIG.relative_to(ROOT))
    print("  冻结源网络 : %s" % SRC_NETWORK.relative_to(ROOT))
    print("=" * 84)

    gate("F1", "源配置 sha16 == 冻结登记", sha16(SRC_CONFIG) == EXPECT_SRC_CONFIG_SHA16, sha16(SRC_CONFIG))
    gate("F2", "源网络 sha16 == 冻结登记", sha16(SRC_NETWORK) == EXPECT_NETWORK_SHA16, sha16(SRC_NETWORK))
    gate("F3", "plans sha16 == 冻结登记", sha16(SRC_PLANS) == EXPECT_PLANS_SHA16, sha16(SRC_PLANS))

    print("\n[1] 定向供给层派生 + 可行性预筛（零仿真）")
    overall, netmods = make_target_layers()
    json.dump(overall, io.open(AUDIT_DIR / "esb01_feasibility_overall.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)

    arms = a.arms or ["SB-A1", "SB-A2", "SB-A3", "SB-A3n", "SB-A4"]

    print("\n[2] 逐臂派生（配置 + 网络）+ 硬门")
    for arm in arms:
        print(f"\n  --- {arm} ---")
        net_override = None
        if arm in netmods:
            net_override = build_network_arm(arm, netmods[arm])
        build_config(arm, net_override)

    n_pass = sum(1 for c in CHECKS if c["pass"])
    fails = [c["check"] for c in CHECKS if not c["pass"]]
    print("\n" + "=" * 84)
    print("  硬门合计 %d/%d %s" % (n_pass, len(CHECKS), "PASS" if not fails else "FAIL"))
    if fails:
        print("  ⛔ 失败：%s ⇒ E-SB-01 = INVALID，不得点火。" % fails)
    with io.open(AUDIT_DIR / "esb01_build_gates.csv", "w", newline="", encoding="utf-8-sig") as fh:
        w = csv.DictWriter(fh, fieldnames=["check", "name", "pass", "detail"])
        w.writeheader()
        w.writerows(CHECKS)
    print("  产物：%s" % AUDIT_DIR)
    print("=" * 84)
    return 0 if not fails else 1


if __name__ == "__main__":
    sys.exit(main())
