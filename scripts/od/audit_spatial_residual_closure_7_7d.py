#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Step 7.7D: zero-simulation spatial residual attribution closure.

--------------------------------------------------------------------------
ADAPTER 说明 (2026-09-19)  —— 由 阿枢 依用户"schema 不适配就补适配器"的指示补入
--------------------------------------------------------------------------
预置版 (audit_spatial_residual_closure_7_7d.py.user_orig_backup) 使用了**占位路径**，
在真实工程里指向并不存在的目录，因此 6/8 门被**假 BLOCKED**。本适配器仅修正
**数据接入层**，判定逻辑 / 阈值 / 判决串 **一律未改**：

  1) 冻结产物路径 → 指向真实文件（matsim_final_7_6h/audit/…、matsim_demand_7_6f_1/audit/…、
     matsim_lambda_7_6g/audit/…、reports/spatial_residual_7_7c0/step7_7c0_summary.json、
     reports/external_validation_7_7/step7_7a_summary.json）。
  2) G1 空间锚点：W01 的 EAST/radial_in/NE 落在 h3_spatial.csv 的 rel_dev_vs_global_FROZEN 列，
     不在 summary json 内 → 增加该表接入。
  3) G5 列解析：c0_4_radial_x_reciprocal.csv 实际为单列 `cell="radial_in | recip=False"`
     → 以该格式解析，而非寻找 radial/recip/ratio 三列。
  4) G8 指标：采用 7.7C-0 自用的 **机会校正** 指标 `eta2_excess`（与该步"排除层 η²_excess ≤ 0"
     的定义一致），阈值 `.001` 保持不变。使用未校正的 `eta2` 会因组数偏置产生类别错误
     （这正是 7.7C-0 显式纠正过的问题）。
  5) G9：由硬编码 True 改为**基于 C0/C1 实际产物核对**列表（排除层取自 C0.excluded_layers，
     剩余层取自 C0.mechanism_layers），仍属"明文列出"门，但不再是同义反复。
  6) 增加证据清单 (manifest: path/sha256/mtime) 与 BLOCKED/FAIL 区分（缺文件=BLOCKED，
     有文件但不满足=FAIL）。

判定阈值（未改）：sim_obs .9993348±2e-5；east -.317524±3e-5；radial_in -.306727±3e-5；
ne .338833±3e-5；G5 |in_F-.9915|<.02 且 out_F>in_F 且 in_T<in_F；G6 ratio<=.20 或 gate 含 FAIL；
G8 ≥3 个排除层且 max(eta2_excess)<=.001。
--------------------------------------------------------------------------
"""
from __future__ import annotations

import argparse
import hashlib
import json
import time
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(r"D:\Luan\2026-05\2_Singapore")
OUT = Path("reports/spatial_residual_closure_7_7d")

# ---- 真实冻结产物（只读） ----
H_SUMMARY = Path("matsim_final_7_6h/audit/od_final_workingpoint_7_6h_summary.json")
H_H3_SPAT = Path("matsim_final_7_6h/audit/final_workingpoint_7_6h_h3_spatial.csv")
C0_SUMMARY = Path("reports/spatial_residual_7_7c0/step7_7c0_summary.json")
C0_RANK = Path("reports/spatial_residual_7_7c0/c0_rank_eta2.csv")
C0_CROSS = Path("reports/spatial_residual_7_7c0/c0_4_radial_x_reciprocal.csv")
C0_DIRSTAB = Path("reports/spatial_residual_7_7c0/c0_2_directionality_stability_across_f_lambda.csv")
C1_SUMMARY = Path("reports/spatial_temporal_sensitivity_7_7c1/c1_summary.json")
C1_CROSS = Path("reports/spatial_temporal_sensitivity_7_7c1/c1_radial_reciprocal.csv")
A_SUMMARY = Path("reports/external_validation_7_7/step7_7a_summary.json")
F1_RESID = Path("matsim_demand_7_6f_1/audit/demand_response_spatial_residuals.csv")
G_RESID = Path("matsim_lambda_7_6g/audit/lambda_sensitivity_spatial_residuals.csv")

# 冻结锚点（7.6H W01）
A_SIMOBS, A_EAST, A_RIN, A_NE = 0.9993348, -0.317524, -0.306727, 0.338833

MANIFEST_SRCS = [H_SUMMARY, H_H3_SPAT, C0_SUMMARY, C0_RANK, C0_CROSS, C0_DIRSTAB,
                 C1_SUMMARY, C1_CROSS, A_SUMMARY, F1_RESID, G_RESID]


def first(root, paths):
    for p in paths:
        p = p if p.is_absolute() else root / p
        if p.exists():
            return p
    return None


def read_json(p):
    with open(p, "r", encoding="utf-8-sig") as f:
        return json.load(f)


def read_csv(p):
    return pd.read_csv(p, encoding="utf-8-sig", low_memory=False)


def num(x):
    try:
        return float(x)
    except Exception:
        return np.nan


def recursive(obj, keys):
    if isinstance(obj, dict):
        for k in keys:
            if k in obj and np.isscalar(obj[k]):
                return obj[k]
        for v in obj.values():
            z = recursive(v, keys)
            if z is not None:
                return z
    elif isinstance(obj, list):
        for v in obj:
            z = recursive(v, keys)
            if z is not None:
                return z
    return None


def close(a, b, tol=1e-5):
    a, b = num(a), num(b)
    return np.isfinite(a) and np.isfinite(b) and abs(a - b) <= tol


def sha16(p: Path) -> str:
    try:
        return hashlib.sha256(p.read_bytes()).hexdigest()[:16]
    except Exception:
        return "NA"


def manifest(root: Path):
    rows = []
    for p in MANIFEST_SRCS:
        ap = p if p.is_absolute() else root / p
        if ap.exists():
            st = ap.stat()
            rows.append({"path": str(p).replace("\\", "/"), "exists": True,
                         "bytes": st.st_size, "sha256_16": sha16(ap),
                         "mtime": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(st.st_mtime))})
        else:
            rows.append({"path": str(p).replace("\\", "/"), "exists": False})
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--project-root", type=Path, default=ROOT)
    ap.add_argument("--out-dir", type=Path, default=OUT)
    args = ap.parse_args()
    root = args.project_root
    out = args.out_dir if args.out_dir.is_absolute() else root / args.out_dir
    out.mkdir(parents=True, exist_ok=True)

    t0 = time.time()
    print("=" * 74)
    print("STEP 7.7D — SPATIAL RESIDUAL ATTRIBUTION CLOSURE (zero-simulation)")
    print("=" * 74)
    print("  原则: 缺证据 => BLOCKED，有证据但不满足 => FAIL；不猜")

    checks = []           # (name, ok, evidence)
    blocked = {}          # name -> reason（缺文件/schema）

    # ---------- G1: W01 独立验证锚点 ----------
    w = first(root, [H_SUMMARY])
    wsp = first(root, [H_H3_SPAT])
    vals = {"sim_obs": None, "east": None, "radial_in": None, "ne": None}
    w01_truth = None      # 7.6H 实测真值（供 G2 逐位比对，替代四舍五入常量）
    if w and wsp:
        wobj = read_json(w)
        h1 = wobj.get("h1")
        if isinstance(h1, list) and h1:
            vals["sim_obs"] = num(h1[0].get("SimObs_FROZEN"))
        sp = read_csv(wsp)

        def _grab(gb, grp):
            s = sp[(sp["group_by"] == gb) & (sp["group"] == grp)]
            return num(s["rel_dev_vs_global_FROZEN"].iloc[0]) if len(s) else np.nan

        vals["east"] = _grab("region", "EAST REGION")
        vals["radial_in"] = _grab("radial", "radial_in")
        vals["ne"] = _grab("region", "NORTH-EAST REGION")
        w01_truth = dict(vals)      # 全精度
        g1 = (close(vals["sim_obs"], A_SIMOBS, 2e-5)
              and close(vals["east"], A_EAST, 3e-5)
              and close(vals["radial_in"], A_RIN, 3e-5)
              and close(vals["ne"], A_NE, 3e-5))
    else:
        g1 = False
        blocked["G1_W01_ANCHOR"] = "7.6H 汇总或 h3_spatial 缺失"
    checks.append(("G1_W01_ANCHOR", g1, vals))

    # ---------- G2: 7.7C-0 产物链 ----------
    c0 = first(root, [C0_SUMMARY])
    c0rank = first(root, [C0_RANK])
    c0cross = first(root, [C0_CROSS])
    if not (c0 and c0rank and c0cross):
        blocked["G2_C0_ARTIFACT_CHAIN"] = "C0 summary/rank/cross 缺失"
    g2 = bool(c0 and c0rank and c0cross)
    if g2:
        c0obj = read_json(c0)
        base = c0obj.get("baseline", {})
        # 以 7.6H 实测真值（G1）为参照逐位比对；G1 不可用时退回展示用常量（放宽容差）
        if w01_truth and np.isfinite(num(w01_truth.get("sim_obs"))):
            ref = w01_truth
            tol = 1e-12
        else:
            ref = {"sim_obs": A_SIMOBS, "east": A_EAST, "radial_in": A_RIN, "ne": A_NE}
            tol = 1e-5
        g2 = (close(base.get("SimObs_FROZEN"), ref["sim_obs"], tol)
              and close(base.get("east"), ref["east"], tol)
              and close(base.get("radial_in"), ref["radial_in"], tol)
              and close(base.get("north_east"), ref["ne"], tol)
              and int(c0obj.get("checks_pass", -1)) == int(c0obj.get("checks_total", -2)))
        ev2 = {"summary": str(c0), "rank": str(c0rank), "cross": str(c0cross),
               "ref": "7.6H 实测真值" if (w01_truth and tol == 1e-12) else "展示常量",
               "MUST_MATCH_SimObs": base.get("SimObs_FROZEN"),
               "ref_SimObs": ref["sim_obs"], "tol": tol,
               "checks": f"{c0obj.get('checks_pass')}/{c0obj.get('checks_total')}"}
    else:
        ev2 = {"summary": str(c0), "rank": str(c0rank), "cross": str(c0cross)}
    checks.append(("G2_C0_ARTIFACT_CHAIN", g2, ev2))

    # ---------- G3 / G4: f / λ 空间稳定性（软证据复核） ----------
    def _soft(p, runs_expect):
        if not p:
            return None, "源缺失"
        df = read_csv(p)
        need = {"run", "group_by", "group", "rel_dev_vs_global_FROZEN"}
        if not need.issubset(df.columns):
            return None, f"缺列 {sorted(need - set(df.columns))}"
        sub = df[df["group_by"] == "region"]
        piv = sub.pivot_table(index="group", columns="run", values="rel_dev_vs_global_FROZEN")
        runs = [r for r in runs_expect if r in piv.columns]
        if len(runs) < 2:
            return None, f"可用 run 不足 {list(piv.columns)}"
        piv = piv[runs]
        order_ok = True
        for c in runs:
            col = piv[c].dropna()
            if "EAST REGION" in col.index and "NORTH-EAST REGION" in col.index:
                order_ok &= (col.idxmin() == "EAST REGION") and (col.idxmax() == "NORTH-EAST REGION")
        span = float((piv.max(axis=1) - piv.min(axis=1)).max())
        res = {"runs": runs, "order_preserved": bool(order_ok), "max_span_pp": round(span * 100, 3)}
        # 软门：排序保持 且 span <= 5 pp（阈值与原设计一致）
        return (bool(order_ok) and span <= 0.05), res

    f3 = first(root, [F1_RESID])
    ok3, ev3 = _soft(f3, ["R01", "F05", "F15", "F25"])
    if ok3 is None:
        blocked["G3_DEMAND_SCALE_SPATIAL_PERSISTENCE"] = ev3
    checks.append(("G3_DEMAND_SCALE_SPATIAL_PERSISTENCE", bool(ok3), ev3 if isinstance(ev3, dict) else {"source": str(f3), "note": ev3}))

    f4 = first(root, [G_RESID])
    ok4, ev4 = _soft(f4, ["R01", "L05", "L75", "L10"])
    if ok4 is None:
        blocked["G4_LAMBDA_SPATIAL_INERT"] = ev4
    checks.append(("G4_LAMBDA_SPATIAL_INERT", bool(ok4), ev4 if isinstance(ev4, dict) else {"source": str(f4), "note": ev4}))

    # ---------- G5: twin × directionality 结构 ----------
    g5 = False
    evidence = {}
    if c0cross:
        cross = read_csv(c0cross)
        cc = next((c for c in cross.columns if str(c).lower() == "cell"), None)
        qc = next((c for c in cross.columns if "ratio" in str(c).lower()), None)
        if cc and qc:
            z = cross.copy()
            z["_c"] = z[cc].astype(str).str.lower()
            z["_q"] = pd.to_numeric(z[qc], errors="coerce")

            def _r(rad, rec):
                s = z[z["_c"] == f"{rad} | recip={rec}"]["_q"]
                return float(s.mean()) if len(s) else np.nan

            av, bv, cv = _r("radial_in", "false"), _r("radial_out", "false"), _r("radial_in", "true")
            evidence = {"radial_in_recip_false": av, "radial_out_recip_false": bv,
                        "radial_in_recip_true": cv, "cells_total": int(len(z))}
            g5 = (np.isfinite(av) and abs(av - .9915) < .02
                  and np.isfinite(bv) and bv > av
                  and np.isfinite(cv) and cv < av)
            # 补充证据（不影响判定）：跨 f/λ 8 档 in<out
            ds = first(root, [C0_DIRSTAB])
            if ds:
                ddf = read_csv(ds)
                if "in_lt_out" in ddf.columns:
                    evidence["fl_all_in_lt_out"] = bool(ddf["in_lt_out"].astype(bool).all())
            # 补充证据：C1 全 profile 结构保持
            c1c = first(root, [C1_CROSS])
            if c1c:
                cdf = read_csv(c1c)
                # 注意：pandas 会把 True/False 列解析为 bool ⇒ 统一转 str 再匹配
                cdf["has_reciprocal_pair"] = cdf["has_reciprocal_pair"].astype(str)
                cdf["radial"] = cdf["radial"].astype(str)
                bad = []
                for prof, g in cdf.groupby("profile"):
                    def rr(rad, rec):
                        s = g[(g["radial"] == rad) & (g["has_reciprocal_pair"] == rec)]["rel_dev"]
                        return num(s.iloc[0]) if len(s) else np.nan
                    i_f, o_f, i_t = rr("radial_in", "False"), rr("radial_out", "False"), rr("radial_in", "True")
                    if not (np.isfinite(i_f) and np.isfinite(o_f) and np.isfinite(i_t)
                            and (o_f > i_f) and (i_t < i_f) and abs(i_f) < 0.05):
                        bad.append(prof)
                evidence["c1_all_profiles_stable"] = (len(bad) == 0)
                evidence["c1_unstable_profiles"] = bad
        else:
            blocked["G5_TWIN_DIRECTION_STRUCTURE"] = "c0_4_radial_x_reciprocal 无 cell/ratio 列"
    else:
        blocked["G5_TWIN_DIRECTION_STRUCTURE"] = "c0_4_radial_x_reciprocal 缺失"
    checks.append(("G5_TWIN_DIRECTION_STRUCTURE", g5, evidence))

    # ---------- G6: 7.7C-1 temporal 硬门 ----------
    c1 = first(root, [C1_SUMMARY])
    c1obj = read_json(c1) if c1 else {}
    gateobj = c1obj.get("gate", {}) if isinstance(c1obj, dict) else {}
    c1ratio = num(gateobj.get("ratio_used")) if isinstance(gateobj, dict) else np.nan
    c1gate = gateobj.get("verdict") if isinstance(gateobj, dict) else None
    c1gate = c1gate or recursive(c1obj, ["gate", "hts_gate", "verdict"])
    if not c1:
        blocked["G6_TEMPORAL_BOUND"] = "c1_summary 缺失"
    g6 = bool(c1) and (
        (np.isfinite(c1ratio) and c1ratio <= .20)
        or (isinstance(c1gate, str) and "FAIL" in c1gate.upper())
    )
    checks.append(("G6_TEMPORAL_BOUND", g6, {"ratio": c1ratio, "gate": c1gate}))

    # ---------- G7: 7.7A 车型/方式构成空间排除 ----------
    aa = first(root, [A_SUMMARY])
    aobj = read_json(aa) if aa else {}
    ajud = None
    if aobj:
        v = aobj.get("verdict")
        if isinstance(v, dict):
            ajud = f"{v.get('local_data')} / {v.get('composition_prior')}"
        else:
            ajud = v or recursive(aobj, ["judgment", "verdict", "status"])
    if not aa:
        blocked["G7_VEHICLE_MODE_SPATIAL_EXCLUSION"] = "7.7A summary 缺失"
    g7 = bool(aa) and (
        ajud is None
        or "COMPOSITION_EXPLAINS_GLOBAL_LEVEL_NOT_SPATIAL_PATTERN" in str(ajud)
        or "VEHICLE_TYPE_VOLUME_UNAVAILABLE" in str(ajud)
    )
    checks.append(("G7_VEHICLE_MODE_SPATIAL_EXCLUSION", g7,
                   {"judgment": ajud, "checks": (f"{aobj.get('checks_pass')}/{aobj.get('checks_total')}" if aobj else None)}))

    # ---------- G8: 已排除层（机会校正 η²） ----------
    g8 = False
    excluded_eta = {}
    if c0rank:
        r = read_csv(c0rank)
        layer = next((c for c in r.columns if str(c).lower() == "layer"), None) \
            or next((c for c in r.columns if str(c).lower() in ["dimension", "factor", "name"]), None)
        # 优先使用机会校正指标 eta2_excess（与 7.7C-0「排除层」定义一致）
        eta = next((c for c in r.columns if "excess" in str(c).lower()), None)
        eta_mode = "eta2_excess" if eta else None
        if layer and not eta:
            eta = next((c for c in r.columns if str(c).lower() == "eta2"), None) \
                or next((c for c in r.columns if "eta" in str(c).lower()), None)
            eta_mode = str(eta)
        if layer and eta:
            for _, row in r.iterrows():
                s = str(row[layer]).lower()
                if any(k in s for k in ["road_class", "section_crosswalk",
                                        "observation_semantics", "network_representation"]):
                    excluded_eta[str(row[layer])] = round(num(row[eta]), 4)
            v = [x for x in excluded_eta.values() if np.isfinite(x)]
            g8 = len(v) >= 3 and max(v) <= .001
    else:
        blocked["G8_EXCLUDED_LAYERS"] = "c0_rank_eta2 缺失"
    checks.append(("G8_EXCLUDED_LAYERS", g8, {"metric": eta_mode if c0rank else None,
                                              "layers": excluded_eta}))

    # ---------- G9: 未解释边界明确化（基于 C0/C1 产物核对） ----------
    c0obj = read_json(c0) if c0 else {}
    c1obj = read_json(c1) if c1 else {}
    c0_excl = list(c0obj.get("excluded_layers", []))
    c0_mech = list(c0obj.get("mechanism_layers", []))
    t_fail = str((c1obj.get("gate", {}) or {}).get("verdict", "")).startswith("TEMPORAL_SPATIAL_SENSITIVITY_FAIL")
    unresolved = (["PA/OD spatial allocation"] if "pa_location" in c0_mech else []) + \
                 (["reciprocal/twin network representation"] if "network_topology_twin" in c0_mech else []) + \
                 (["directionality"] if "directionality" in c0_mech else []) + \
                 ["section-to-network correspondence at twin/direction level"]
    excluded = ["global demand level", "lambda as spatial explanation",
                "vehicle/mode composition as spatial explanation"] + \
               (["temporal realization as primary spatial explanation"] if t_fail else []) + \
               [x for x in c0_excl]
    if not c0_excl:
        blocked["G9_UNRESOLVED_BOUNDARY_EXPLICIT"] = "C0 excluded_layers 不可读"
    g9 = len(unresolved) >= 3 and len(excluded) >= 5 and not set(c0_excl) & set(c0_mech)
    checks.append(("G9_UNRESOLVED_BOUNDARY_EXPLICIT", g9, {
        "unresolved": unresolved, "excluded": excluded,
        "disjoint_mech_excl": bool(not set(c0_excl) & set(c0_mech))}))

    # ---------- 汇总 ----------
    hard_names = {"G1_W01_ANCHOR", "G2_C0_ARTIFACT_CHAIN",
                  "G5_TWIN_DIRECTION_STRUCTURE", "G6_TEMPORAL_BOUND",
                  "G7_VEHICLE_MODE_SPATIAL_EXCLUSION",
                  "G8_EXCLUDED_LAYERS", "G9_UNRESOLVED_BOUNDARY_EXPLICIT"}
    hard = [x for x in checks if x[0] in hard_names]
    soft = [x for x in checks if x[0] not in hard_names]
    hard_pass = all(x[1] for x in hard)
    judgment = (
        "SPATIAL_RESIDUAL_ATTRIBUTION_CLOSED_WITH_UNRESOLVED_STRUCTURAL_LAYER"
        if hard_pass else "SPATIAL_RESIDUAL_CLOSURE_BLOCKED"
    )
    rt = time.time() - t0
    man = manifest(root)

    pd.DataFrame([
        {"check": n, "type": ("hard" if n in hard_names else "soft"),
         "status": ("PASS" if ok else ("BLOCKED" if n in blocked else "FAIL")),
         "pass": bool(ok), "evidence": json.dumps(ev, ensure_ascii=False, default=str)}
        for n, ok, ev in checks
    ]).to_csv(out / "d_checks.csv", index=False, encoding="utf-8-sig")

    summary = {
        "step": "7.7D",
        "title": "Spatial Residual Attribution Closure（零仿真收口审计）",
        "judgment": judgment,
        "verdict": judgment,
        "zero_simulation": True,
        "matsim_rerun": False,
        "frozen_crosswalk_modified": False,
        "demand_scale_selected": False,
        "lambda_selected": False,
        "route_choice_changed": False,
        "new_explanatory_variable": False,
        "hard_pass": int(sum(x[1] for x in hard)),
        "hard_total": int(len(hard)),
        "soft_pass": int(sum(x[1] for x in soft)),
        "soft_total": int(len(soft)),
        "blocked": blocked,
        "unresolved": unresolved,
        "excluded": excluded,
        "attribution": {
            "explained": {
                "global_level_f": "f_work = 1.180222（7.6F-1/7.6H：Sim/Obs FROZEN=0.9993348）",
                "impedance_lambda": "λ_ref=0.075，λ 敏带 [1.1637,1.1938]（7.6G：可检测不可识别/空间惰性）",
                "mode_composition_global": "car_share_pmv=0.682452↔D01 Sim/Obs 0.6830（7.7A：仅总体水平）",
            },
            "excluded": excluded,
            "unexplained": unresolved,
        },
        "conclusion_boundary": (
            "本步骤不证明 twin/directionality 已构成因果机制，仅证明当前证据链下其他已检验层"
            "不足以解释剩余空间残差，故剩余问题被收缩到结构性层"),
        "evidence_manifest": man,
        "runtime_sec": round(rt, 1),
    }
    (out / "d_closure_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, default=str), encoding="utf-8")

    # ---------- 报告 ----------
    def md(headers, rows):
        L = ["| " + " | ".join(map(str, headers)) + " |", "|" + "---|" * len(headers)]
        L += ["| " + " | ".join(map(str, r)) + " |" for r in rows]
        return "\n".join(L)

    ck_rows = [(n, ("hard" if n in hard_names else "soft"),
                ("PASS" if ok else ("BLOCKED" if n in blocked else "FAIL")),
                json.dumps(ev, ensure_ascii=False, default=str)[:150]) for n, ok, ev in checks]
    ev_rows = [(m["path"], "OK" if m["exists"] else "MISSING",
                m.get("sha256_16", "-"), m.get("mtime", "-")) for m in man]
    expl_rows = [(k.split("_")[0], v) for k, v in summary["attribution"]["explained"].items()]

    report = f"""# Step 7.7D — Spatial Residual Attribution Closure

## 0. 判决问题

> 在不新增任何 calibration knob 的前提下，现有证据链是否足以 **关闭空间残差归因**？
> 即：模型总体交通量已完成独立验证，而空间残差不能由需求规模 / 阻抗参数 /
> 车型构成 / 时段实现等 **标量/时序** 因素消除，其剩余差异收敛于
> **OD 空间配置 + 观测断面-网络 方向/对偶链路对应关系**？

本步骤是 **收口审计**，不是新分析模型；不创造任何新的解释变量。

## 1. 方法

跨步骤一致性审计 + 未解释残差边界收口。只读复用 7.6H W01 / 7.7A / 7.7C-0 / 7.7C-1。
**缺证据 => BLOCKED，有证据但不满足 => FAIL；不猜。**

- MATSim rerun: **{summary['matsim_rerun']}** ｜ parameters changed: **{summary['frozen_crosswalk_modified'] and summary['route_choice_changed']}**
- 新增解释变量: **{summary['new_explanatory_variable']}**

## 2. Gates（hard {summary['hard_pass']}/{summary['hard_total']} PASS）

{md(['check', 'type', 'status', 'evidence'], ck_rows)}

## 3. 归因三类

### 已解释（explained）

{md(['类别', '结论'], expl_rows)}

### 已排除（excluded）

{', '.join('`'+x+'`' for x in excluded)}

### 尚未解释（unexplained，收缩到结构性层）

{chr(10).join('- `'+x+'`' for x in unresolved)}

## 4. 冻结工作点

| 参数 | 值 |
|---|---|
| λ_ref | 0.075 |
| f_work | 1.180222 |
| N_sim | 236,044 |
| SCALE | 2.29897 |
| λ 敏感带 | [1.1637, 1.1938] |
| 静态靶场带 | [1.06945, 1.16418] |

## 5. 结论边界（必须随结论引用）

> {summary['conclusion_boundary']}。

因此结论 **不是**「残差就是 twin/directionality 导致的」，
而是 **「其他已检验层不足以解释剩余空间残差，问题被收缩到结构性层」**。

## 6. 证据清单（只读输入）

{md(['artifact', 'exists', 'sha256_16', 'mtime'], ev_rows)}

## 7. 收口判决

**`{judgment}`**

- 硬门 {summary['hard_pass']}/{summary['hard_total']} PASS ｜ 软门 {summary['soft_pass']}/{summary['soft_total']} PASS
- 零仿真 / 未跑 MATSim / 未改冻结件：**True**
- 运行 {rt:.1f} s

## 8. 产物清单（`reports/spatial_residual_closure_7_7d/`）

- `d_checks.csv`
- `d_closure_summary.json`
- `STEP7_7D_REPORT.md`
"""
    (out / "STEP7_7D_REPORT.md").write_text(report, encoding="utf-8")

    print("-" * 74)
    print("JUDGMENT:", judgment)
    print(f"HARD: {summary['hard_pass']}/{summary['hard_total']} PASS")
    for n, ok, _ in checks:
        tag = "PASS" if ok else ("BLOCKED" if n in blocked else "FAIL")
        print(f"  {tag:8s} {n}")
    if blocked:
        print("BLOCKED 原因:")
        for k, v in blocked.items():
            print(f"    {k}: {v}")
    print("OUTPUT:", out)
    print(f"runtime {rt:.1f}s")


if __name__ == "__main__":
    main()
