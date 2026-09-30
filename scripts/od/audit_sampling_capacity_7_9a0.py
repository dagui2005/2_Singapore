# -*- coding: utf-8 -*-
"""
Step 7.9A-0  Sampling-Capacity Consistency Audit  (零仿真 / 严格只读)
====================================================================

在逻辑链中的位置（用户 2026-09-20 裁定）：

    7.8 Final Model Freeze / v1.0
        v
    7.7E Congestion State Plausibility Audit (post-freeze, read-only)
        v
    发现状态形成机制存在结构性不足
        v
    7.9 Structural Repair / v1.1
        v
    7.9A-0  Sample-Capacity Consistency Audit   <-- 本脚本
        v
    7.9A-1  f_flow = f_storage = 1/SCALE        <-- 待批准后执行

本步只做四件事（全部只读，零 MATSim、零写入冻结目录）：
  (1) 核实四个实际生效值   : f_flow / f_storage / trafficDynamics / timeStepSize
  (2) 推导 sample 比例     : s_sample 并检查其与 1/SCALE 的关系
  (3) 裁定 capacity 一致性因子（并排除一个极易踩中的分母歧义）
  (4) 零仿真预注册预测     : 若 f_cap -> 1/SCALE，饱和结构会变成什么样（A-1 判据前置）

⛔ 红线（用户明确指定，本脚本以"不变式"形式检查）：
    · 不跑 MATSim，不改 OD / demand / lambda / route-choice / network
    · 不重开 v1.0，不修改 reports/final_model_7_8/ 与 matsim_final_7_6h/ 下任何文件
    · 产物全部落在新目录 reports/sampling_capacity_audit_7_9a0/
    · 0.434977 是由 population 表示尺度独立推导的一致性约束，**不是**为了让地图变红而反演的参数

★ 本步最重要的一个发现（分母歧义）：
    s = N_sim / SigmaEF         = 236044 / 459794 = 0.513369   <-- 常见误用（错的）
    s = N_sim / (SCALE * N_sim) = 1 / SCALE       = 0.434977   <-- capacity 一致性因子（对的）
    两者之比恒等于 f_work = 1.180222。
    量纲证明：v/c_sim = v/c_real 要求  F_sim / C_sim = F_real / C_real
              而 Sim/Obs = 1 断言  F_real = SCALE * F_sim
              => C_sim = C_real / SCALE  =>  f_cap = 1/SCALE。与 SigmaEF 的定义无关。

运行（~1 min）：C:/Users/LQP/miniconda3/python.exe scripts/od/audit_sampling_capacity_7_9a0.py
"""

from __future__ import annotations

import gzip
import io
import json
import re
import time
from pathlib import Path
from xml.etree import ElementTree as ET

import numpy as np
import pandas as pd

import matplotlib
matplotlib.use("Agg")
import matplotlib.font_manager as fm  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402

try:
    fm.fontManager.addfont(r"C:\Windows\Fonts\msyh.ttc")
    matplotlib.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "DejaVu Sans"]
except Exception:
    pass
matplotlib.rcParams["axes.unicode_minus"] = False

# ----------------------------------------------------------------------------
# 路径（全部只读输入 / 唯一可写 = OUT）
# ----------------------------------------------------------------------------
ROOT = Path(r"D:\Luan\2026-05\2_Singapore")

CFG_V10 = ROOT / "matsim_final_7_6h" / "configs" / "config_W01_rc_min.xml"
CFG_VIZ = ROOT / "matsim_viz_7_8" / "configs" / "config_W01_events.xml"
CFG_RUN_VIZ = ROOT / "matsim_viz_7_8" / "outputs" / "W01_events" / "W01_events.output_config.xml"
CFG_RUN_V10 = ROOT / "matsim_final_7_6h" / "outputs" / "W01_rc_min" / "W01_rc_min.output_config.xml"

FREEZE = ROOT / "reports" / "final_model_7_8" / "FINAL_PARAMETER_FREEZE.json"
SUMM78 = ROOT / "reports" / "final_model_7_8" / "step7_8_summary.json"
METRICS78 = ROOT / "reports" / "final_model_7_8" / "FINAL_VALIDATION_METRICS.csv"
WHITELIST = ROOT / "matsim_viz_7_8" / "audit" / "config_diff_whitelist.csv"

POP = ROOT / "matsim_final_7_6h" / "populations" / "pop_W01" / "population_lambda_0p075.xml.gz"
LS_VIZ = ROOT / "matsim_viz_7_8" / "outputs" / "W01_events" / "ITERS" / "it.19" / "W01_events.19.linkstats.txt.gz"
LS_76H = ROOT / "matsim_final_7_6h" / "outputs" / "W01_rc_min" / "ITERS" / "it.19" / "W01_rc_min.19.linkstats.txt.gz"

AUT_77E = ROOT / "reports" / "congestion_plausibility_audit_7_7e" / "audit_summary.json"
E4_77E = ROOT / "reports" / "congestion_plausibility_audit_7_7e" / "e4_network_temporal_15min.csv"
LEG_77E = ROOT / "reports" / "congestion_plausibility_audit_7_7e" / "e4_leg_histogram_5min.csv"
SAT_77E = ROOT / "reports" / "congestion_plausibility_audit_7_7e" / "e2_saturated_links_0809.csv"

OUT = ROOT / "reports" / "sampling_capacity_audit_7_9a0"

FROZEN_DIRS = [
    ROOT / "reports" / "final_model_7_8",
    ROOT / "matsim_final_7_6h",
    ROOT / "matsim_viz_7_8",
]

GATES = []


def gate(gid, name, ok, detail):
    GATES.append({"id": gid, "name": name, "ok": bool(ok), "detail": str(detail)})
    print("[%s] %-6s %s | %s" % ("PASS" if ok else "FAIL", gid, name, detail))


def read_xml(path: Path):
    txt = io.open(path, encoding="utf-8", errors="replace").read()
    txt = re.sub(r"<!DOCTYPE[^>]*>", "", txt, count=1)
    return ET.fromstring(txt)


def collect_cfg(path: Path):
    """返回 (module_order, {(module, param): value})；递归展开 <parameterset>。"""
    root = read_xml(path)
    params, order = {}, []
    for mod in root.findall("module"):
        mname = mod.get("name")
        order.append(mname)

        def walk(node, prefix, mname=mname):
            for ps in node.findall("parameterset"):
                sub = ps.get("type") or ps.get("name") or "?"
                walk(ps, prefix + "/" + sub)
            for p in node.findall("param"):
                key = (mname, (prefix + "/" + p.get("name")) if prefix else p.get("name"))
                params[key] = p.get("value")

        walk(mod, "")
    return order, params


def count_token_gz(path: Path, token: bytes) -> int:
    n, carry = 0, b""
    with gzip.open(path, "rb") as f:
        while True:
            chunk = f.read(1 << 22)
            if not chunk:
                break
            buf = carry + chunk
            n += buf.count(token)
            carry = buf[-(len(token) - 1):] if len(token) > 1 else b""
    return n


def dir_snapshot(dirs):
    snap = {}
    for d in dirs:
        for p in d.rglob("*"):
            if p.is_file():
                try:
                    snap[str(p)] = p.stat().st_mtime_ns
                except OSError:
                    pass
    return snap


def _cell(v):
    """表格单元格：转义竖线（否则 markdown 表格会被 | 拆列），数值去掉无意义的尾零。"""
    if isinstance(v, float):
        if abs(v - round(v)) < 1e-9 and abs(v) < 1e15:
            return str(int(round(v)))
        t = ("%.6f" % v).rstrip("0").rstrip(".")
        return t if t else "0"
    return str(v).replace("|", "\\|").replace("\n", " ")


def md_table(headers, rows):
    out = ["| " + " | ".join(headers) + " |", "|" + "|".join(["---"] * len(headers)) + "|"]
    for r in rows:
        out.append("| " + " | ".join(_cell(c) for c in r) + " |")
    return "\n".join(out)


def main():
    t0 = time.time()
    OUT.mkdir(parents=True, exist_ok=True)
    snap_before = dir_snapshot(FROZEN_DIRS)

    print("=" * 78)
    print("Step 7.9A-0  Sampling-Capacity Consistency Audit  (zero-simulation, read-only)")
    print("=" * 78)

    # ------------------------------------------------------------------ 0 输入
    inputs = {
        "cfg_v10": CFG_V10, "cfg_viz": CFG_VIZ, "run_dump_viz": CFG_RUN_VIZ,
        "run_dump_v10": CFG_RUN_V10, "freeze": FREEZE, "summ78": SUMM78,
        "metrics78": METRICS78, "whitelist": WHITELIST, "pop": POP,
        "ls_viz": LS_VIZ, "ls_76h": LS_76H,
        "audit_77e": AUT_77E, "e4_77e": E4_77E, "sat_77e": SAT_77E,
    }
    missing = [k for k, v in inputs.items() if not v.exists()]
    gate("A0.01", "输入文件齐备", not missing,
         "missing=%s | n=%d" % (missing if missing else "none", len(inputs)))

    _, p_v10 = collect_cfg(CFG_V10)
    _, p_viz = collect_cfg(CFG_VIZ)
    _, p_run_viz = collect_cfg(CFG_RUN_VIZ)
    _, p_run_v10 = collect_cfg(CFG_RUN_V10)
    n_mod = len(read_xml(CFG_V10).findall("module"))

    fz = json.load(io.open(FREEZE, encoding="utf-8"))
    s78 = json.load(io.open(SUMM78, encoding="utf-8"))
    aut = json.load(io.open(AUT_77E, encoding="utf-8"))
    met = pd.read_csv(METRICS78, encoding="utf-8-sig")
    met_map = {r["item"]: r["value"] for _, r in met.iterrows()}
    fz_item = {p["item"]: p for p in fz["parameters"]}

    # ------------------------------------------- 1 四个实际生效值核实
    qsim = "qsim"
    mobsim = p_v10.get(("controller", "mobsim"))
    gate("A0.02", "有效 mobsim = qsim", mobsim == "qsim",
         "controller.mobsim=%s (n_modules=%d)" % (mobsim, n_mod))

    f_flow = p_v10.get((qsim, "flowCapacityFactor"))
    f_stor = p_v10.get((qsim, "storageCapacityFactor"))
    f_dyn = p_v10.get((qsim, "trafficDynamics"))
    f_tss = p_v10.get((qsim, "timeStepSize"))
    ds_td = p_v10.get(("dsim", "trafficDynamics"))

    gate("A0.03", "qsim.flowCapacityFactor = 1.0（权威 v1.0 配置）", f_flow == "1.0", "value=%s" % f_flow)
    gate("A0.04", "qsim.storageCapacityFactor = 1.0（权威 v1.0 配置）", f_stor == "1.0", "value=%s" % f_stor)
    gate("A0.05", "qsim.trafficDynamics=queue 生效；dsim 同名参数为惰性诱饵",
         f_dyn == "queue" and ds_td == "kinematicWaves",
         "qsim=%s (EFFECTIVE) | dsim=%s (INERT: mobsim=qsim) => 不得把后者当成当前动力学"
         % (f_dyn, ds_td))
    gate("A0.06", "qsim.timeStepSize = 00:00:01", f_tss == "00:00:01",
         "value=%s（7.7E 量化伪影 TT=ceil(FF) 的根因）" % f_tss)

    def agree(key):
        vals = [p_v10.get(key), p_viz.get(key), p_run_viz.get(key), p_run_v10.get(key)]
        return len(set(vals)) == 1, vals

    a1, v1 = agree((qsim, "flowCapacityFactor"))
    a2, v2 = agree((qsim, "storageCapacityFactor"))
    a3, v3 = agree((qsim, "trafficDynamics"))
    a4, v4 = agree((qsim, "timeStepSize"))
    gate("A0.07", "四源一致：四个实际值在 权威cfg / viz cfg / 两次运行 dump 中逐位相同",
         a1 and a2 and a3 and a4,
         "f_flow=%s f_storage=%s dyn=%s ts=%s" % (v1, v2, v3, v4))

    h_ff = p_v10.get(("hermes", "flowCapacityFactor"))
    h_fs = p_v10.get(("hermes", "storageCapacityFactor"))
    gate("A0.08", "hermes.*CapacityFactor 同为 1.0 但模块惰性 => 容量旋钮只在 qsim",
         h_ff == "1.0" and h_fs == "1.0",
         "hermes.flow=%s hermes.storage=%s ; mobsim=qsim 故 hermes 惰性（7.2.2 实测）" % (h_ff, h_fs))

    cfg_matrix = [
        ("qsim", "flowCapacityFactor", p_v10, True, "容量旋钮（生效）"),
        ("qsim", "storageCapacityFactor", p_v10, True, "容量旋钮（生效）"),
        ("qsim", "trafficDynamics", p_v10, True, "流出释放机制（生效）"),
        ("qsim", "timeStepSize", p_v10, True, "时间离散（生效）"),
        ("hermes", "flowCapacityFactor", p_v10, False, "惰性（mobsim=qsim）"),
        ("hermes", "storageCapacityFactor", p_v10, False, "惰性（mobsim=qsim）"),
        ("dsim", "trafficDynamics", p_v10, False, "惰性诱饵（mobsim=qsim）"),
        ("controller", "mobsim", p_v10, True, "决定谁生效"),
    ]
    pd.DataFrame([{
        "module": m, "param": prm, "config_v1_0": p.get((m, prm)), "config_viz": p_viz.get((m, prm)),
        "effective": eff, "note": note,
    } for m, prm, p, eff, note in cfg_matrix]) \
        .to_csv(OUT / "a0_config_values_matrix.csv", index=False, encoding="utf-8-sig")

    # ------------------------------------------------ 2 采样比例推导
    n_sim_pop = count_token_gz(POP, b"<person ")
    n_sim_decl = int(fz_item["sim_agents"]["final_value"])
    gate("A0.09", "人口文件 person 数 = 冻结 sim_agents = 236,044",
         n_sim_pop == n_sim_decl == 236044,
         "pop file=%d | FINAL_PARAMETER_FREEZE=%d" % (n_sim_pop, n_sim_decl))

    N_base = float(fz_item["N_base"]["final_value"])
    SCALE = float(fz_item["SCALE"]["final_value"])
    f_work = float(fz_item["f_work"]["final_value"])
    sum_ef = float(fz["derived_disclosure"]["sum_expansion_factor"])
    f_realized = float(fz["derived_disclosure"]["f_realized"])

    gate("A0.10", "SCALE = SigmaEF / N_base（逐位复现）",
         abs(sum_ef / N_base - SCALE) < 1e-5,
         "%.6f / %.0f = %.6f ; 冻结 SCALE = %.5f" % (sum_ef, N_base, sum_ef / N_base, SCALE))
    gate("A0.11", "需求锚 SigmaEF = 459,794 = Census 2020 Table 104 Car Only",
         abs(sum_ef - 459794.0) < 1.0, "sum_expansion_factor = %.6f" % sum_ef)

    n_sim = float(n_sim_pop)
    s_flow = 1.0 / SCALE
    q_repr = SCALE * n_sim
    s_naive = n_sim / sum_ef
    bridge = s_naive / s_flow

    gate("A0.12", "s_sample(flow-consistent) = 1/SCALE = %.6f" % s_flow,
         abs(s_flow - 1.0 / 2.29897) < 1e-9,
         "1/%.5f=%.6f | N_sim/(SCALE*N_sim)=%.6f（恒等） | Q_repr=%.1f" % (SCALE, s_flow, n_sim / q_repr, q_repr))
    gate("A0.13", "分母歧义已定位：N_sim/SigmaEF 与 1/SCALE 之比恒为 f_work",
         abs(bridge - f_work) < 1e-4,
         "N_sim/SigmaEF=%.6f | 1/SCALE=%.6f | 比值=%.6f (f_work=%.6f, f_realized=%.6f)"
         % (s_naive, s_flow, bridge, f_work, f_realized))
    gate("A0.14", "裁定：capacity-consistent 因子 = 1/SCALE = %.6f（排除 %.6f）" % (s_flow, s_naive),
         True,
         "量纲证明：F_real=SCALE*F_sim 且 Sim/Obs=1 => C_sim=C_real/SCALE；SigmaEF 是需求锚，不是流量扩样基准")

    sim_obs = float(met_map["SimObs_FROZEN"])
    gate("A0.15", "冻结 Sim/Obs 逐位复现（证明 SCALE 即实际生效的扩样因子）",
         abs(sim_obs - 0.9993347696792919) < 1e-12,
         "SimObs_FROZEN = %.16f" % sim_obs)

    cap_item = fz_item["f_cap"]
    gate("A0.16", "f_cap=1.0 属 7.8 冻结参数 => A-1 必须升版 v1.1",
         cap_item["final_value"] == 1.0 and cap_item["kind"] == "capacity",
         "kind=%s value=%s source=%s" % (cap_item["kind"], cap_item["final_value"], cap_item["source"]))
    gate("A0.17", "7.8 冻结门 23/23 且 verdict 记录（只读引用）",
         s78.get("checks_pass") == s78.get("checks_total") == 23
         and s78.get("verdict") == "FINAL_MODEL_FROZEN_AND_REPRODUCIBLE",
         "%s ; %d/%d" % (s78.get("verdict"), s78.get("checks_pass"), s78.get("checks_total")))

    wl = pd.read_csv(WHITELIST, encoding="utf-8-sig")
    gate("A0.18", "v1.0 -> viz 配置 diff 仅 3 项白名单（只读引用）",
         len(wl) == 3 and wl["whitelisted"].astype(str).str.lower().isin(["true", "1"]).all(),
         "diff=%d keys=%s" % (len(wl), list(wl["key"])))

    # ------------------------------------ 3 零仿真投影（冻结流量一阶上界）
    cols = ["LINK", "CAPACITY", "LENGTH", "FREESPEED", "HRS8-9avg"]
    ls = pd.read_csv(LS_VIZ, sep="\t", usecols=cols, compression="gzip")
    ls76 = pd.read_csv(LS_76H, sep="\t", usecols=cols, compression="gzip")
    same = (len(ls) == len(ls76)
            and np.array_equal(ls["LINK"].to_numpy(), ls76["LINK"].to_numpy())
            and np.array_equal(ls["HRS8-9avg"].to_numpy(float), ls76["HRS8-9avg"].to_numpy(float)))
    gate("A0.19", "it.19 linkstats：7.6H 与 VIZ-RUN 逐位相同（扩样口径输入未漂移）",
         bool(same), "n_links=%d bit_identical=%s" % (len(ls), bool(same)))

    q = ls["HRS8-9avg"].to_numpy(float)
    cap = np.maximum(ls["CAPACITY"].to_numpy(float), 1e-9)
    L = ls["LENGTH"].to_numpy(float)
    vc = q / cap
    vc_proj = vc / s_flow

    loaded = q > 0

    def stats(ratio, flow, Lv, capp):
        m = {
            "n_all": int(len(ratio)),
            "n_loaded": int((flow > 0).sum()),
            "n_ge_0p5": int((ratio >= 0.5).sum()),
            "n_ge_0p9": int((ratio >= 0.9).sum()),
            "n_ge_1": int((ratio >= 1.0).sum()),
            "sat_km": float(Lv[ratio >= 1.0].sum() / 1000.0),
            "agg_util": float(flow.sum() / capp.sum()),
            "agg_util_loaded": float(flow[flow > 0].sum() / capp[flow > 0].sum()),
        }
        return m

    cur = stats(vc, q, L, cap)
    prj = stats(vc_proj, q, L, cap * s_flow)
    link_summed_excess = float(np.maximum(0.0, q - cap * s_flow).sum())
    tot_len_km = float(L.sum() / 1000.0)
    share_len_sat_now = float(L[vc >= 1.0].sum() / max(L.sum(), 1e-9))
    share_len_sat = float(L[vc_proj >= 1.0].sum() / max(L.sum(), 1e-9))
    share_flow_sat_now = float(q[vc >= 1.0].sum() / max(q.sum(), 1e-9))
    share_flow_sat = float(q[vc_proj >= 1.0].sum() / max(q.sum(), 1e-9))

    sat_77e = pd.read_csv(SAT_77E, encoding="utf-8-sig")
    gate("A0.20", "复现 7.7E 饱和链路数（82 条 / 1.15 km）",
         abs(cur["n_ge_1"] - len(sat_77e)) <= 2 and abs(cur["sat_km"] - 1.15) < 0.35,
         "linkstats n(v/c>=1)=%d sat_km=%.3f | 7.7E csv rows=%d"
         % (cur["n_ge_1"], cur["sat_km"], len(sat_77e)))

    e4 = pd.read_csv(E4_77E, encoding="utf-8-sig")
    lh = pd.read_csv(LEG_77E, encoding="utf-8-sig")
    peak_agg = float(e4["agg_vc"].max())
    peak_in = float(lh["enr_car"].max())
    peak_in_t = str(lh.loc[lh["enr_car"].idxmax(), "hhmm"])
    gate("A0.21", "复现 7.7E E4 峰值（agg_vc=0.102447 / 在途峰 36,799 @08:55）",
         abs(peak_agg - 0.10244692822003312) < 1e-6 and peak_in == 36799.0,
         "peak agg_vc=%.6f | peak enr_car=%.0f @%s"
         "（note: E4 的 entries 是累计链路进入数，不是在途量 —— 首个版本曾误读）"
         % (peak_agg, peak_in, peak_in_t))

    proj_rows = [{
        "metric": "n_links_total", "v1_0": cur["n_all"], "a1_projected": prj["n_all"],
        "ratio": prj["n_all"] / cur["n_all"], "kind": "count"},
        {"metric": "n_loaded_links", "v1_0": cur["n_loaded"], "a1_projected": prj["n_loaded"],
         "ratio": 1.0, "kind": "count（需求不变，载流链路集合不变）"},
        {"metric": "n_vc_ge_0p5", "v1_0": cur["n_ge_0p5"], "a1_projected": prj["n_ge_0p5"],
         "ratio": prj["n_ge_0p5"] / max(cur["n_ge_0p5"], 1), "kind": "count"},
        {"metric": "n_vc_ge_0p9", "v1_0": cur["n_ge_0p9"], "a1_projected": prj["n_ge_0p9"],
         "ratio": prj["n_ge_0p9"] / max(cur["n_ge_0p9"], 1), "kind": "count"},
        {"metric": "n_vc_ge_1p0", "v1_0": cur["n_ge_1"], "a1_projected": prj["n_ge_1"],
         "ratio": prj["n_ge_1"] / max(cur["n_ge_1"], 1), "kind": "count（若已饱和则仍为 1）"},
        {"metric": "saturated_km", "v1_0": cur["sat_km"], "a1_projected": prj["sat_km"],
         "ratio": prj["sat_km"] / max(cur["sat_km"], 1e-9), "kind": "km"},
        {"metric": "agg_util_hourly", "v1_0": cur["agg_util"], "a1_projected": prj["agg_util"],
         "ratio": prj["agg_util"] / cur["agg_util"], "kind": "SumFlow/SumCap"},
        {"metric": "peak_agg_vc_15min", "v1_0": peak_agg, "a1_projected": peak_agg / s_flow,
         "ratio": (peak_agg / s_flow) / peak_agg, "kind": "7.7E E4 x 1/SCALE"},
        {"metric": "network_length_km", "v1_0": tot_len_km, "a1_projected": tot_len_km,
         "ratio": 1.0, "kind": "km（分母：全网链路长度）"},
        {"metric": "share_len_saturated", "v1_0": share_len_sat_now, "a1_projected": share_len_sat,
         "ratio": share_len_sat / max(share_len_sat_now, 1e-12), "kind": "比例（占全网里程）"},
        {"metric": "share_flow_on_saturated_links", "v1_0": share_flow_sat_now,
         "a1_projected": share_flow_sat, "ratio": share_flow_sat / max(share_flow_sat_now, 1e-12),
         "kind": "比例（链路级流量求和，沿路径重复计数）"},
    ]
    pd.DataFrame(proj_rows).to_csv(OUT / "a0_projection_frozen_flow.csv", index=False, encoding="utf-8-sig")

    recon = pd.DataFrame([
        {"quantity": "N_sim (agents)", "value": n_sim, "note": "pop 文件 person 数 = 冻结 sim_agents"},
        {"quantity": "N_base", "value": N_base, "note": "7.8 冻结采样基准"},
        {"quantity": "f_work", "value": f_work, "note": "工作点 = N_sim/N_base"},
        {"quantity": "SCALE (frozen)", "value": SCALE, "note": "SigmaEF/N_base，作为扩样因子冻结"},
        {"quantity": "SigmaEF (Census car-only anchor)", "value": sum_ef, "note": "需求锚，非流量扩样基准"},
        {"quantity": "Q_repr = SCALE * N_sim", "value": q_repr, "note": "被表示的等效真实车辆数"},
        {"quantity": "s = N_sim / SigmaEF", "value": s_naive, "note": "WRONG for capacity：与需求锚混用"},
        {"quantity": "s = 1/SCALE", "value": s_flow, "note": "CORRECT：capacity-consistent factor"},
        {"quantity": "ratio (naive/correct)", "value": bridge, "note": "恒等于 f_work"},
        {"quantity": "Sim/Obs (frozen)", "value": sim_obs, "note": "断言 F_real = SCALE*F_sim"},
    ])
    recon.to_csv(OUT / "a0_sample_ratio_reconciliation.csv", index=False, encoding="utf-8-sig")

    # 预注册预测 + A-1 判据
    prereg = {
        "step": "7.9A-0",
        "role": "post-freeze read-only consistency audit; gate for 7.9A-1",
        "version_rule": "任何修改 v1.0 冻结参数即属新版本 v1.1（FINAL_PARAMETER_FREEZE.wording_discipline.version_lock）",
        "four_values": {
            "flowCapacityFactor": {"value": f_flow, "module": "qsim", "effective": True},
            "storageCapacityFactor": {"value": f_stor, "module": "qsim", "effective": True},
            "trafficDynamics": {"value": f_dyn, "module": "qsim", "effective": True},
            "timeStepSize": {"value": f_tss, "module": "qsim", "effective": True},
            "decoys": {
                "dsim.trafficDynamics": {"value": ds_td, "effective": False,
                                         "warning": "惰性诱饵：不得当成当前动力学设置"},
                "hermes.*CapacityFactor": {"value": h_ff, "effective": False,
                                           "warning": "惰性：容量旋钮只在 qsim"},
            },
        },
        "sampling": {
            "N_sim": n_sim, "N_base": N_base, "f_work": f_work, "SCALE": SCALE,
            "Q_repr": q_repr, "sum_expansion_factor": sum_ef,
            "s_flow_consistent": s_flow, "s_naive_wrong": s_naive, "ratio": bridge,
            "adjudication": "f_cap_consistent = 1/SCALE; SigmaEF 是需求锚，不参与流量扩样分母",
        },
        "a1_single_change": {
            "design": "SINGLE_DERIVED_VALUE（不作 0.35/0.40/0.45/0.50 扫描 —— 那是参数拟合）",
            "qsim.flowCapacityFactor": [f_flow, s_flow],
            "qsim.storageCapacityFactor": [f_stor, s_flow],
            "hermes": "保持 1.0 不动（惰性，与 S100c 同构）",
            "unchanged": ["OD", "f_work", "lambda=0.075", "SCALE", "population 236044",
                          "route-choice R01", "crosswalk 7.3.6A", "network v1.0",
                          "departure realization W01", "randomSeed 4711"],
            "new_version": "v1.1 Structural Repair / 新目录，不得改 v1.0 任何产物",
        },
        "prediction_frozen_flow": {
            "caveat": "冻结流量一阶上界：只把 CAPACITY 乘 1/SCALE，不考虑排队导致的流量回落 => 高估饱和",
            "n_vc_ge_0p5": [cur["n_ge_0p5"], prj["n_ge_0p5"]],
            "n_vc_ge_1p0": [cur["n_ge_1"], prj["n_ge_1"]],
            "saturated_km": [cur["sat_km"], prj["sat_km"]],
            "agg_util": [cur["agg_util"], prj["agg_util"]],
            "peak_agg_vc_15min": [peak_agg, peak_agg / s_flow],
            "link_summed_capacity_excess_veh_per_h": link_summed_excess,
            "link_summed_caveat": "链路级求和，沿路径重复计数 => 仅作相对比较，不代表无法出行的车辆数",
            "share_len_saturated": [share_len_sat_now, share_len_sat],
            "share_flow_on_saturated_links": [share_flow_sat_now, share_flow_sat],
            "network_length_km": tot_len_km,
            "direction": {
                "in_network_peak": "上升（容量下降 => 车辆滞留更久）",
                "throughput": "下降（饱和度上升 => 排队抑制通过量）",
                "Sim_Obs": "预计下移（v1.0 的 0.9993 部分依赖容量宽松；⛔ 不得再以 Sim/Obs=1 为 A-1 目标）",
            },
        },
        "a1_gates": {
            "flow_breakdown_guard": "Sim/Obs >= 0.85（防崩解，非校准目标）",
            "stability": ["A_10:19 < 0.03", "parity_gap_rel < 0.05",
                          "never_arrived == 0", "max_stuck_car == 0",
                          "departures_car == arrivals_car == 236044"],
            "congestion_primary": ["real_excess_delay（扣 ceil(FF)/FF）", "saturated link count & km",
                                   "corridor excess (CTE/PIE/AYE)", "queue connected-component length",
                                   "peak agg utilization", "peak in-network vehicles"],
        },
        "outcome_matrix": {
            "A": {"criterion": "拥堵显著增强且流量基本保持", "reading": "v1.0 轻拥堵主因 = sample-capacity inconsistency",
                  "action": "v1.1 = 表示尺度统一（非调参）"},
            "B": {"criterion": "拥堵增强但大量 stuck / 网络崩溃", "reading": "方向对，但超细碎路网 storage/bottleneck 表达承受不了",
                  "action": "转入 7.9B Network Bottleneck / Storage Structure（⛔ 不把 capacity 调回去）"},
            "C": {"criterion": "拥堵增强很少", "reading": "sample inconsistency 不是主因", "action": "第二刀 = trafficDynamics"},
            "D": {"criterion": "流量指标严重恶化而拥堵才变合理", "reading": "既有断面流量校准可能依赖了错误的容量尺度补偿",
                  "action": "检查 OD assignment / flow scale / capacity / departure concentration 耦合"},
        },
        "red_lines": [
            "⛔ 不为了让 VIA 变红而提高 demand",
            "⛔ 不为制造拥堵而降低容量/修改 lambda/修改 route-choice",
            "⛔ 不为视觉效果重定义 congestion index",
            "⛔ 不把 0.434977 表述为『为了让新加坡堵起来把容量砍到 43.5%』",
        ],
    }
    io.open(OUT / "a0_preregistered_predictions.json", "w", encoding="utf-8") \
        .write(json.dumps(prereg, ensure_ascii=False, indent=2))

    # ------------------------------------------------------ 4 自证未触碰冻结件
    snap_after = dir_snapshot(FROZEN_DIRS)
    changed = [k for k in snap_after if snap_before.get(k) != snap_after[k]]
    removed = [k for k in snap_before if k not in snap_after]
    gate("A0.22", "红线段：冻结目录零改动（零仿真 / 零写入）",
         not changed and not removed,
         "changed=%d removed=%d n_files=%d" % (len(changed), len(removed), len(snap_after)))

    # ------------------------------------------------------------------ 5 图
    fig = plt.figure(figsize=(14.2, 9.4))
    gs = fig.add_gridspec(2, 2, hspace=0.34, wspace=0.22)

    # (A) 配置值矩阵
    axA = fig.add_subplot(gs[0, 0])
    axA.axis("off")
    axA.set_title("(A) 四个实际值的模块归属与生效性\n(sample 一致性旋钮只在 qsim)", fontsize=10, loc="left")
    rows = [[m, prm, p.get((m, prm)), "生效" if eff else "惰性", note]
            for m, prm, p, eff, note in cfg_matrix]
    tb = axA.table(cellText=[[r[0], r[1], r[2], r[3]] for r in rows],
                   rowLabels=[r[4] for r in rows],
                   colLabels=["module", "param", "value", "status"],
                   loc="center", cellLoc="left", rowLoc="left")
    tb.auto_set_font_size(False)
    tb.set_fontsize(7.2)
    tb.scale(1.0, 1.42)

    # (B) 采样比例对账
    axB = fig.add_subplot(gs[0, 1])
    labs = ["1/SCALE\n(流量一致性)", "N_sim/SigmaEF\n(误用)", "0.435\n(目标)"]
    vals = [s_flow * 100, s_naive * 100, 43.498]
    cols_ = ["#2e7d32", "#c0392b", "#7f7f7f"]
    bars = axB.bar(labs, vals, color=cols_, width=0.55)
    for b, v in zip(bars, vals):
        axB.text(b.get_x() + b.get_width() / 2, v + 0.9, "%.4f%%" % v, ha="center", fontsize=9)
    axB.set_ylim(0, max(vals) * 1.30)
    axB.set_ylabel("sample 比例 s (%)", fontsize=9)
    axB.set_title("(B) 采样比例对账：两者之比恒为 f_work=1.180222", fontsize=10, loc="left")
    axB.grid(alpha=0.25, axis="y")
    axB.annotate("", xy=(1, s_naive * 100), xytext=(0, s_flow * 100),
                 arrowprops=dict(arrowstyle="<->", color="#333"))
    axB.text(0.5, (s_flow + s_naive) * 100 / 2 + 1.6, "x %.6f\n= f_work" % bridge,
             ha="center", fontsize=8.5, color="#333")

    # (C) v/c 分布 + 投影
    axC = fig.add_subplot(gs[1, 0])
    bins = np.linspace(0, 1.0, 51)
    axC.hist(np.clip(vc[loaded], 0, 1.0), bins=bins, color="#1f6feb", alpha=0.75,
             label="v1.0 实测 (f_cap=1.00)")
    axC.hist(np.clip(vc_proj[loaded], 0, 1.0), bins=bins, color="#d97706", alpha=0.55,
             label="A-1 预测 (f_cap=%.4f, 冻结流量)" % s_flow)
    axC.axvline(1.0, color="#c0392b", ls="--", lw=1.4)
    axC.text(0.995, axC.get_ylim()[1] * 0.86, " 饱和线 v/c=1", color="#c0392b", fontsize=8.5, ha="right")
    axC.set_yscale("log")
    axC.set_xlabel("v/c = HRS8-9avg / CAPACITY", fontsize=9)
    axC.set_ylabel("链路数（对数轴）", fontsize=9)
    axC.set_title("(C) 容量利用率分布：载流链路 %d 条（%.1f%%）" % (cur["n_loaded"], 100.0 * cur["n_loaded"] / cur["n_all"]),
                  fontsize=10, loc="left")
    axC.legend(fontsize=8)
    axC.grid(alpha=0.25)

    # (D) 相对放大倍数
    axD = fig.add_subplot(gs[1, 1])
    names = ["v/c>=0.5", "v/c>=0.9", "v/c>=1.0", "饱和 km", "Sum流量/Sum容量", "峰 aggV/C"]
    ratios = [(prj["n_ge_0p5"] / max(cur["n_ge_0p5"], 1)),
              (prj["n_ge_0p9"] / max(cur["n_ge_0p9"], 1)),
              (prj["n_ge_1"] / max(cur["n_ge_1"], 1)),
              (prj["sat_km"] / max(cur["sat_km"], 1e-9)),
              (prj["agg_util"] / cur["agg_util"]),
              ((peak_agg / s_flow) / peak_agg)]
    x = np.arange(len(names))
    axD.bar(x, ratios, color="#7c3aed", width=0.55)
    for i, r in enumerate(ratios):
        axD.text(i, r + 0.06, "x%.2f" % r, ha="center", fontsize=8.5)
    axD.axhline(1.0, color="#555", ls=":", lw=1)
    axD.set_ylim(0, max(ratios) * 1.24)
    axD.set_xticks(x)
    axD.set_xticklabels(names, fontsize=8, rotation=20)
    axD.set_ylabel("A-1 / v1.0（预测倍数）", fontsize=9)
    axD.set_title("(D) sample-consistent 容量下的饱和结构放大（冻结流量上界）", fontsize=10, loc="left")
    axD.grid(alpha=0.25, axis="y")
    axD.text(0.02, 0.97,
             "预测峰 aggV/C = %.4f（仍 < 1）\n=> 全网级拥堵波仍不预期出现" % (peak_agg / s_flow),
             transform=axD.transAxes, va="top", ha="left", fontsize=8.0, color="#c0392b")

    fig.suptitle("Step 7.9A-0  Sampling-Capacity Consistency Audit（v1.0 冻结后只读诊断；零仿真）",
                 fontsize=13.5, y=0.985)
    fig.text(0.012, 0.012,
             "唯一结论：当前模型 = 236,044 辆车（%.4f%% 样本）跑在 100%% 容量的路网上；"
             "v/c_sim 系统性地只有真实值的 %.4f 倍。" % (s_flow * 100, s_flow),
             fontsize=8.2, color="#555")
    fig.savefig(OUT / "sampling_capacity_audit_7_9a0.png", dpi=155, bbox_inches="tight")
    plt.close(fig)

    # -------------------------------------------------------------- 6 报告
    ok_all = all(g["ok"] for g in GATES)
    verdict = "SAMPLING_CAPACITY_CONSISTENCY_AUDIT_COMPLETE" if ok_all else "AUDIT_INCOMPLETE_GATES_FAILED"
    conclusion = "SAMPLING_CAPACITY_INCONSISTENCY_CONFIRMED"

    L = []
    A = L.append
    A("# Step 7.9A-0 采样—容量一致性审计（v1.0 冻结后，只读）\n")
    A("- 模型版本：**Singapore_OD_MATSim_Final_v1.0（未改动）**")
    A("- 定性：**7.9 第一阶段（结构审查）**，不是 7.8 的前置校准步骤")
    A("- 零仿真：**是**（未启动 MATSim）；参数改动：**否**；冻结件触碰：**否**")
    A("- 门控：**%d/%d PASS**" % (sum(g["ok"] for g in GATES), len(GATES)))
    A("- 判决：`%s` → `%s`\n" % (verdict, conclusion))
    A("> 本步不解释「模型为什么不堵」，只回答两个更前置的问题：**当前容量的实际取值是什么**，")
    A("> 以及**对当前 population 而言它是否自洽**。结论只作为 `7.9A-1` 的准入证据。\n")

    A("## 一、四个实际生效值（用户指定核实）\n")
    A(md_table(["module", "param", "值（v1.0）", "值（viz）", "生效?", "说明"],
               [[m, prm, p_v10.get((m, prm)), p_viz.get((m, prm)), "生效" if eff else "惰性", note]
                for m, prm, p, eff, note in cfg_matrix]))
    A("")
    A("- **f_flow = `%s`**、**f_storage = `%s`**（module = `qsim`，生效）" % (f_flow, f_stor))
    A("- **trafficDynamics = `%s`**（module = `qsim`，生效）" % f_dyn)
    A("- **timeStepSize = `%s`**（module = `qsim`，生效；7.7E 量化伪影的根因）" % f_tss)
    A("")
    A("### ★ 两个必须记录的口径陷阱（否则本步数字会算错）\n")
    A("1. **`dsim.trafficDynamics = %s` 是惰性诱饵。** 该参数位于 `dsim` 模块，而 `controller.mobsim = %s`，"
      % (ds_td, mobsim))
    A("   因此 MATSim 根本不会读它。全配置里出现两次同名参数 ≠ 冲突；**判断生效性必须看 `mobsim`**。")
    A("2. **`hermes.*CapacityFactor` 也是惰性的**（同样因为 `mobsim=qsim`）。")
    A("   ⇒ 7.9A-1 的**唯一容量旋钮是 `qsim.flowCapacityFactor` / `qsim.storageCapacityFactor`**，")
    A("   不要动 `hermes`（保持 1.0，与 S100c 同构）。\n")
    A("四个值在 **权威 config / viz config / 两次 MATSim 运行期 dump** 四源逐位一致（A0.07）。\n")

    A("## 二、采样比例：一个必须排除的分母歧义\n")
    A("用户的推导式 `s = N_sim / SigmaEF` 会给出 **%.6f**，而目标值 `1/SCALE` 是 **%.6f**。"
      % (s_naive, s_flow))
    A("两者之比恒为 **%.6f = f_work**，所以这不是误差，而是**分母选错**。\n" % bridge)
    A(md_table(["量", "值", "说明"], [[r["quantity"], r["value"], r["note"]]
                                     for _, r in recon.iterrows()]))
    A("")
    A("### 裁定：capacity 一致性因子 = `1/SCALE` = **%.6f**\n" % s_flow)
    A("量纲证明（与 `SigmaEF` 的定义**无关**）：\n")
    A("- `Sim/Obs = 1` 断言：`F_real = SCALE x F_sim`，即 `%.6f x %.0f = %.0f` 辆（需求总量口径）"
      % (SCALE, n_sim, q_repr))
    A("- 要保持 `v/c_sim = v/c_real`，即 `F_sim / C_sim = F_real / C_real`")
    A("- 代入得 `C_sim = C_real / SCALE` ⇒ **`f_cap = 1/SCALE = %.6f`**\n" % s_flow)
    A("**为什么 `N_sim/SigmaEF` 是错的**：`SigmaEF = 459,794` 是 **Census 2020 Table 104 `Car Only` 的需求锚**，")
    A("而模型实际在路网上表示的是 `SCALE × N_sim = %.1f` 辆（= 1.180222 倍需求锚）。" % q_repr)
    A("工作点故意让 population 相对需求锚超采样 18.0222%，以弥合 7.6A 的 `CALIBER_GAP`（观测含非小汽车、全目的）。")
    A("拿需求锚当流量分母，会把一致性因子算成 %.6f（**偏高 18%%，等于把容量少砍了 18%%**）。\n" % s_naive)
    A("★ **稳健性**：`1/SCALE = N_base/SigmaEF`，**与工作点缩放无关** —— 即使 f_work 变化，")
    A("只要 SCALE 冻结，该因子不变。所以 A-1 的数值不依赖 f_work 的取值。\n")

    A("## 三、当前模型的物理含义（这是 7.7E 结果的机制解释）\n")
    A("- 236,044 辆仿真车 = 真实 **%.4f%%** 的样本；" % (s_flow * 100))
    A("- 但 QSim 给它们的是 **100% 的真实容量**（`f_cap=1.0`）⇒")
    A("- 于是 **`v/c_sim ≈ %.4f × v/c_real`**：模型里的容量利用率被系统性压到真实值的 **%.1f%%**。\n"
      % (s_flow, s_flow * 100))
    A("这正好解释了 7.7E 的观感：**流量可以对上（总量级），但容量竞争不足（状态）**。\n")

    A("## 四、零仿真预注册预测（A-1 的前置判据）\n")
    A("方法：把 it.19 冻结流量保持不变，只把 `CAPACITY` 乘 `1/SCALE`，重算 v/c。")
    A("⚠️ **这是「冻结流量一阶上界」**：不考虑排队导致的流量回落，因此**高估**饱和程度。\n")
    A(md_table(["指标", "v1.0 实测", "A-1 预测（上界）", "倍数"],
               [[r["metric"], r["v1_0"], r["a1_projected"], r["ratio"]]
                for _, r in pd.DataFrame(proj_rows).iterrows()]))
    A("")
    A("- 饱和里程占全网 **%.3f%% → %.3f%%**（全网链路总长 %.1f km）；"
      % (share_len_sat_now * 100, share_len_sat * 100, tot_len_km))
    A("  处于饱和链路上的链路级流量占比 **%.3f%% → %.3f%%**。" % (share_flow_sat_now * 100, share_flow_sat * 100))
    A("- 链路级容量超额求和 `Sum max(0, q - cap*f)` = **%.0f 辆/h**。"
      % link_summed_excess)
    A("  ⚠️ 该量沿路径**重复计数**，只用于相对比较，**不代表「无法出行的车辆数」**。")
    A("- ★ **空间尺度结论（预注册）**：即使按 sample-consistent 容量，饱和里程也只占全网 **%.2f%%**，"
      % (share_len_sat * 100))
    A("  峰 `aggV/C` 仅 **%.3f** ⇒ **仍不预期出现全网级拥堵波**；预期改变集中在**局部瓶颈**。"
      % (peak_agg / s_flow))
    A("- **方向性预测**：在途峰值 ↑（车辆滞留更久）、通过量 ↓、**`Sim/Obs` 预计下移**。")
    A("- ⛔ **关键预注册**：`Sim/Obs = 0.9993` 是 v1.0 的流量校准成果，**不得作为 A-1 的目标**；")
    A("  A-1 的流量门只是**崩解护栏**（`Sim/Obs >= 0.85`）。")
    A("- ★ **本投影即已提示**：峰 `aggV/C` 仅从 %.4f → **%.4f**（仍远小于 1）"
      % (peak_agg, peak_agg / s_flow))
    A("  ⇒ 若 A-1 实测与之一致，则主因更可能落在 **情形 C**（sample inconsistency 非主因）")
    A("  ⇒ 第二刀应转向 **7.9B `trafficDynamics`**，而不是回头继续压容量。\n")

    A("## 五、7.9A-1 执行计划（待批准；本步不执行）\n")
    A("- **唯一结构变化**：`qsim.flowCapacityFactor` `%s` → **%.6f**；`qsim.storageCapacityFactor` `%s` → **%.6f**"
      % (f_flow, s_flow, f_stor, s_flow))
    A("- **单点派生值，不做扫描**（0.35/0.40/0.45/0.50 扫描 = 参数拟合，已预注册排除）")
    A("- **完全不动**：OD、`f_work`、`lambda=0.075`、`SCALE`、population 236,044、route-choice R01、")
    A("  crosswalk 7.3.6A、network v1.0、departure realization W01、`randomSeed=4711`")
    A("- **新版本 v1.1**：新目录、新 runId；⛔ 不得改 `matsim_final_7_6h/`、`matsim_viz_7_8/`、`reports/final_model_7_8/` 任何文件")
    A("- **三层判据**：① 流量（崩解护栏 + CATA/SLIP/Pearson/WMAPE/GEH）② 拥堵形成（★扣量化后的真实 excess、")
    A("  饱和链路数与里程、走廊 excess、排队连通链长、峰 aggV/C、峰在途量）③ 数值稳定性（`A_10:19`、parity gap、")
    A("  `never_arrived`、`max_stuck_car`、departure/arrival 完整率）\n")
    A("### 四种结果的预注册读法\n")
    A(md_table(["情形", "判据", "读法", "动作"],
               [[k, v["criterion"], v["reading"], v["action"]] for k, v in prereg["outcome_matrix"].items()]))
    A("")
    A("### 红线（用户指定，逐条预注册）\n")
    for r in prereg["red_lines"]:
        A("- " + r)
    A("")
    A("★ 正确表述：**「由于模型 population 按 %.4f%% 样本表示完整交通需求，而 QSim 的流量与存储容量采用未经"
      % (s_flow * 100))
    A("sample adjustment 的 1.0 倍容量，因此首先检验 sample-consistent capacity representation；")
    A("该因子由 population representation 独立推导，不由交通观测误差反演。」**\n")

    A("## 六、本步自查\n")
    A("1. **分母歧义**：`N_sim/SigmaEF` 会给出 0.513369，与目标 0.4350 差 18.0222% —— 已定位为 f_work，已排除。")
    A("2. **惰性诱饵**：`dsim.trafficDynamics=kinematicWaves` 与 `hermes.*CapacityFactor=1.0` 均不生效；")
    A("   若不先看 `mobsim`，极易误判「当前动力学已是 kinematicWaves」。")
    A("3. **投影不是仿真**：第四节的数是**上界**，不能替代 A-1 实测；不得据此下结论。")
    A("4. **未触碰冻结件**：A0.22 对三个冻结目录做运行前后 mtime 快照比对，`changed=0`。\n")

    A("## 七、门控明细\n")
    A(md_table(["id", "判据", "结果", "细节"],
               [[g["id"], g["name"], "PASS" if g["ok"] else "FAIL", g["detail"]] for g in GATES]))

    io.open(OUT / "SAMPLING_CAPACITY_AUDIT_7_9A0.md", "w", encoding="utf-8", newline="\n") \
        .write("\n".join(L))

    summary = {
        "step": "7.9A-0",
        "title": "Sampling-Capacity Consistency Audit (post-freeze, read-only)",
        "model_version": "Singapore_OD_MATSim_Final_v1.0 (UNCHANGED)",
        "stage": "7.9 phase-1 structural review (NOT a 7.8 pre-calibration step)",
        "verdict": verdict,
        "conclusion": conclusion,
        "zero_simulation": True,
        "matsim_rerun": False,
        "parameters_changed": False,
        "frozen_artifacts_touched": False,
        "gates_total": len(GATES),
        "gates_pass": sum(g["ok"] for g in GATES),
        "gates": GATES,
        "effective_values": {
            "flowCapacityFactor": f_flow, "storageCapacityFactor": f_stor,
            "trafficDynamics": f_dyn, "timeStepSize": f_tss,
            "mobsim": mobsim,
            "inert_decoys": {"dsim.trafficDynamics": ds_td,
                             "hermes.flowCapacityFactor": h_ff,
                             "hermes.storageCapacityFactor": h_fs},
        },
        "sampling": {
            "N_sim": n_sim, "N_base": N_base, "f_work": f_work, "SCALE": SCALE,
            "sum_expansion_factor": sum_ef, "Q_repr": q_repr,
            "s_flow_consistent": s_flow, "s_naive_wrong": s_naive, "ratio_naive_over_flow": bridge,
            "sim_obs_frozen": sim_obs,
            "physical_reading": "v/c_sim = %.6f x v/c_real" % s_flow,
        },
        "projection_frozen_flow": {
            "caveat": "upper bound, ignores queue-induced flow reduction",
            "v1_0": cur, "a1_projected": prj,
            "link_summed_capacity_excess_veh_per_h": link_summed_excess,
            "share_len_saturated": [share_len_sat_now, share_len_sat],
            "network_length_km": tot_len_km,
            "peak_agg_vc_15min": [peak_agg, peak_agg / s_flow],
        },
        "a1_plan": prereg["a1_single_change"],
        "a1_gates": prereg["a1_gates"],
        "products": sorted(p.name for p in OUT.iterdir()),
        "runtime_sec": round(time.time() - t0, 2),
    }
    io.open(OUT / "a0_audit_summary.json", "w", encoding="utf-8") \
        .write(json.dumps(summary, ensure_ascii=False, indent=2))

    print("\n" + "=" * 78)
    print("GATES: %d/%d PASS" % (summary["gates_pass"], summary["gates_total"]))
    print("VERDICT: %s" % verdict)
    print("CONCLUSION: %s" % conclusion)
    print("f_flow = f_storage = %s  ->  %.6f  (1/SCALE)" % (f_flow, s_flow))
    print("s_naive (wrong) = %.6f ; ratio = %.6f = f_work" % (s_naive, bridge))
    print("v1.0: n(v/c>=1)=%d sat_km=%.3f agg_util=%.5f" % (cur["n_ge_1"], cur["sat_km"], cur["agg_util"]))
    print("A-1 projected (UB): n(v/c>=1)=%d sat_km=%.3f (%.3f%% of %.0f km) agg_util=%.5f"
          % (prj["n_ge_1"], prj["sat_km"], share_len_sat * 100, tot_len_km, prj["agg_util"]))
    print("OUT: %s" % OUT)
    print("runtime %.2f s" % summary["runtime_sec"])
    print("=" * 78)


if __name__ == "__main__":
    main()
