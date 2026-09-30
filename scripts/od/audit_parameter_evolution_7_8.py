"""Step 7.8-REF —— 参数演变对照：7.8 定版 vs 起点（零仿真、只读）。

目的：回答「7.8 定版的仿真参数，与一开始比有哪些变化？」
做法：把项目全生命周期的关键 config 全展开（含 <parameterset>），
      逐键对照起点与定版，并自动归因「该项首次等于定版值发生在哪一步」。

⛔ 只读：不写任何冻结目录；仅写 reports/parameter_evolution_7_8/。
⛔ 不启动 MATSim。constants_only。
"""
from __future__ import annotations

import csv
import json
import xml.etree.ElementTree as ET
from collections import OrderedDict
from pathlib import Path

ROOT = Path(r"D:\Luan\2026-05\2_Singapore")
OUT = ROOT / "reports" / "parameter_evolution_7_8"

# ---------------------------------------------------------------- 阶段序列
STAGES = [
    ("S0 起点", "6.3 起点：最早 MATSim 分配（单迭代）",
     r"matsim\step6_3\config_lambda_0p075.xml"),
    ("S1", "6.3.3B：逐小时出发剖面",
     r"matsim\step6_3\config_lambda_0p075_6_3_3b.xml"),
    ("S2", "7.2.2：容量敏感性（仍单迭代）",
     r"reports\od_calibration_7_2_2\capacity_factor_1p00\cap_f_1p00.output_config.xml"),
    ("S2b", "7.4.2 Phase 1（E01–E03：λ0.050 × capacity 扫描，首个 20 迭代）",
     r"reports\od_calibration_7_4_2\E03_lam0p050_cap1p00\E03.output_config.xml"),
    ("S3", "7.4.3 D02：demand scale 校准期（20 迭代）",
     r"reports\od_calibration_7_4_3\D02_lam0p075\D02.output_config.xml"),
    ("S4", "7.6D R01：route-choice 修复",
     r"matsim_routechoice_7_6d\configs\config_R01_rc_min.xml"),
    ("S5 定版", "7.8 W01：定版运行",
     r"matsim_final_7_6h\configs\config_W01_rc_min.xml"),
    ("S6", "7.8-VIZ：仅输出层重跑（非新版本）",
     r"matsim_viz_7_8\configs\config_W01_events.xml"),
]
FINAL = "S5 定版"

PATH_KEYS = {"controller.outputDirectory", "controller.runId", "plans.inputPlansFile"}
SERIALIZATION_TOKENS = {"<absent>", "null", "-1"}

# 机制归类（仅用于报告分组；不影响判定）
MECHANISM = OrderedDict([
    ("收敛/迭代", ["controller.lastIteration"]),
    ("输出开关", ["controller.writeEventsInterval", "controller.writePlansInterval",
                  "controller.writeSnapshotsInterval", "controller.writeTripsInterval"]),
    ("qsim 车辆识别", ["qsim.usePersonIdForMissingVehicleId"]),
    ("路径选择扰动", ["routing.routingRandomness"]),
    ("★route-choice 策略集", ["replanning.fractionOfIterationsToDisableInnovation",
                              "scoring.learningRate",
                              "replanning.<strategysettings>.strategyName",
                              "replanning.<strategysettings>.weight"]),
])


def strategy_list(path: Path) -> str:
    """逐 parameterset 展开策略集（flatten 的通用键会合并同名策略，故单列）。"""
    root = ET.parse(path).getroot()
    out = []
    for mod in root.findall("module"):
        if mod.get("name") != "replanning":
            continue
        for ps in mod.findall("parameterset"):
            if ps.get("type") != "strategysettings":
                continue
            nm = wt = None
            for pm in ps.findall("param"):
                if pm.get("name") == "strategyName":
                    nm = pm.get("value")
                elif pm.get("name") == "weight":
                    wt = pm.get("value")
            out.append(f"{nm}:{wt}")
    return " + ".join(out) if out else "<none>"


def flatten(path: Path) -> dict:
    out = {}
    root = ET.parse(path).getroot()
    for mod in root.findall("module"):
        mn = mod.get("name")
        for pm in mod.findall("param"):
            out[f"{mn}.{pm.get('name')}"] = pm.get("value")
        for i, ps in enumerate(mod.findall("parameterset")):
            t = ps.get("type") or f"ps{i}"
            for pm in ps.findall("param"):
                out[f"{mn}.<{t}>.{pm.get('name')}"] = pm.get("value")
    return out


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    CHECKS = []

    def chk(cid, desc, ok, detail=""):
        CHECKS.append({"check": cid, "desc": desc, "pass": bool(ok), "detail": detail})
        print(f"[{'PASS' if ok else 'FAIL'}] {cid} {desc} — {detail}")

    flats, meta = OrderedDict(), []
    for sid, label, rel in STAGES:
        p = ROOT / rel
        if not p.exists():
            chk(f"E-{sid}", f"配置存在 {rel}", False, "MISSING")
            return 2
        flats[sid] = flatten(p)
        meta.append({"stage": sid, "label": label, "config": rel,
                     "n_keys": len(flats[sid]),
                     "strategies": strategy_list(p)})
        print(f"  {sid:8s} {len(flats[sid]):4d} keys  {Path(rel).name}")

    s0, sf = flats["S0 起点"], flats[FINAL]
    order = [st[0] for st in STAGES]
    chk("K1", "起点与定版的 config 键集完全一致（同一模板）",
        set(s0) == set(sf), f"对称差={sorted(set(s0) ^ set(sf))}")
    extra = {s: sorted(set(flats[s]) - set(s0)) for s in order}
    extra = {k: v for k, v in extra.items() if v}
    chk("K1b", "其余阶段多出的键仅为 MATSim 转储的序列化项",
        all(set(v) <= {"replanning.<strategysettings>.disableAfterIteration",
                       "replanning.<strategysettings>.executionPath",
                       "replanning.<strategysettings>.subpopulation"}
            for v in extra.values()),
        f"{ {k: len(v) for k, v in extra.items()} }")

    all_keys = sorted(set().union(*[set(f) for f in flats.values()]))

    rows = []
    for k in all_keys:
        v0, vf = s0.get(k, "<absent>"), sf.get(k, "<absent>")
        if v0 == vf:
            continue
        vals = [flats[s].get(k, "<absent>") for s in order]
        # 首次等于定版值的阶段（且前一阶段不同）
        origin = ""
        for i in range(1, len(order)):
            if vals[i] == vf and vals[i - 1] != vf:
                origin = order[i]
                break
        if all(v in SERIALIZATION_TOKENS for v in vals):
            cat = "序列化差异（非物理）"
        elif k in PATH_KEYS:
            cat = "路径/命名（provenance）"
        else:
            cat = "★实质参数"
        mech = next((g for g, ks in MECHANISM.items() if k in ks), "—")
        rows.append({"param": k, "category": cat, "mechanism": mech,
                     "start_value": v0, "final_value": vf,
                     "first_changed_at": origin,
                     "values_by_stage": " | ".join(vals)})

    real = [r for r in rows if r["category"] == "★实质参数"]
    print(f"\n差异键 {len(rows)} / 全键 {len(all_keys)}；"
          f"其中实质参数 {len(real)}、路径命名 "
          f"{sum(1 for r in rows if r['category'].startswith('路径'))}、"
          f"序列化 {sum(1 for r in rows if r['category'].startswith('序列化'))}")

    # ---------------- 继承性核验
    def stage_path(sid: str) -> Path:
        return ROOT / next(x[2] for x in STAGES if x[0] == sid)

    r01 = flatten(stage_path("S4"))
    for k in MECHANISM["★route-choice 策略集"]:
        chk(f"K-RC-{k.split('.')[-1][:18]}", f"定版继承 7.6D 的 {k}",
            sf.get(k) == r01.get(k), f"{sf.get(k)!r} == {r01.get(k)!r}")
    for k in ["global.randomSeed", "qsim.flowCapacityFactor",
              "qsim.storageCapacityFactor", "network.inputNetworkFile",
              "global.coordinateSystem", "qsim.mainMode", "controller.routingAlgorithmType"]:
        chk(f"K-SAME-{k.split('.')[-1][:18]}", f"{k} 起点=定版（未变）",
            s0.get(k) == sf.get(k), f"{sf.get(k)!r}")
    chk("K-EVENTS", "定版 writeEventsInterval=0（VIA 无 events 的根因）",
        sf.get("controller.writeEventsInterval") == "0",
        f"{sf.get('controller.writeEventsInterval')!r}")

    viz = flats["S6"]
    viz_diff = sorted(k for k in set(viz) | set(sf) if viz.get(k) != sf.get(k))
    chk("K-VIZ", "7.8-VIZ 白名单差异恰好 3 项（含 outputDirectory/runId）",
        len(viz_diff) == 3 and "controller.writeEventsInterval" in viz_diff,
        f"{viz_diff}")

    st0 = meta[0]["strategies"]
    stf = next(m["strategies"] for m in meta if m["stage"] == FINAL)
    chk("K-RC-PAIR", "策略集：起点 ReRoute:1.0 单策略 → 定版 ReRoute:0.15 + ChangeExpBeta:0.85",
        st0 == "ReRoute:1.0" and stf == "ReRoute:0.15 + ChangeExpBeta:0.85",
        f"S0=[{st0}] → {FINAL}=[{stf}]")
    chk("K-RC-PAIR-N", "定版策略权重和 == 1.0",
        abs(sum(float(x.split(":")[1]) for x in stf.split(" + ")) - 1.0) < 1e-12, stf)

    # ---------------- 需求层（来自冻结件，逐位读）
    fz = json.loads((ROOT / "reports/final_model_7_8/FINAL_PARAMETER_FREEZE.json")
                    .read_text(encoding="utf-8"))
    piv = {p["item"]: p["final_value"] for p in fz["parameters"]}
    chk("K-FWORK", "定版 f_work == 1.180222", piv["f_work"] == 1.180222, str(piv["f_work"]))
    chk("K-NSIM", "N_sim == round(f_work × 200000)",
        piv["sim_agents"] == round(piv["f_work"] * 200000),
        f"{piv['sim_agents']} vs {round(piv['f_work'] * 200000)}")

    demand = [
        {"item": "需求规模 f", "start": "1.00（无缩放，200,000 agent 全量投递）",
         "final": "1.180222", "kind": "需求",
         "source": "7.6G L75 直跑实测隐含 f*；7.6H 冻结"},
        {"item": "被仿真 agent 数 N_sim", "start": "200,000", "final": "236,044",
         "kind": "需求", "source": "W01 = round(f_work × N_base)，物理加车"},
        {"item": "采样基准 N_base", "start": "200,000", "final": "200,000（未变）",
         "kind": "采样", "source": "7.4.3′ 冻结；100k 方案已否决（7.5A/7.5B）"},
        {"item": "重力衰减 λ", "start": "未选定；5A/5C1 起即 5 档扫描 {0.05,0.075,0.10,0.125,0.15}",
         "final": "0.075（工作中心，⛔ 非最优 λ）", "kind": "OD 构造",
         "source": "7.6G 敏感度中心；λ 由人口承载，config 内无形参"},
        {"item": "扩样系数 SCALE", "start": "未引入（评价用原始 linkstats 加总）",
         "final": "2.29897 = ΣT/N_base", "kind": "评价层（不进仿真）",
         "source": "7.5A 审计：MATSim 不消费 expansionFactor/odTrips"},
        {"item": "供给容量 f_cap", "start": "1.00", "final": "1.00（未变）",
         "kind": "供给", "source": "7.4.1 矩阵扫 0.50/0.75/1.00 ⇒ f=1.00 全面占优"},
        {"item": "随机种子 randomSeed", "start": "4711", "final": "4711（未变）",
         "kind": "运行", "source": "6.3 起硬编码；7.4.1 曾纠正草案误写 20260912"},
        {"item": "迭代数", "start": "1（lastIteration=0）", "final": "20（lastIteration=19）",
         "kind": "运行", "source": "7.4.1 校准矩阵起"},
        {"item": "观测靶场", "start": "6.3.2 crosswalk（1,278 断面，it.0）",
         "final": "7.1 冻结观测 + 7.3.6A（576 断面 / 574 primary）",
         "kind": "评价层", "source": "7.3.6A 冻结；主口径池化 FROZEN"},
        {"item": "标定靶值", "start": "逐窗口 sim_obs_ratio（无单一靶值）",
         "final": "0.8589732（576 断面池化）", "kind": "评价层",
         "source": "7.6C-2 FROZEN 主口径"},
        {"item": "稳定性判据", "start": "无（单迭代）",
         "final": "双口径 A_10:19 + Q_19，须 MATCHED", "kind": "评价层",
         "source": "7.6B′ 裁定 / 7.6E 冻结"},
    ]

    # ---------------- 落盘
    with open(OUT / "parameter_evolution_diff.csv", "w", newline="",
              encoding="utf-8-sig") as fh:
        w = csv.DictWriter(fh, fieldnames=["param", "category", "mechanism",
                                           "start_value", "final_value",
                                           "first_changed_at", "values_by_stage"])
        w.writeheader()
        w.writerows(rows)

    with open(OUT / "parameter_evolution_demand_layer.csv", "w", newline="",
              encoding="utf-8-sig") as fh:
        w = csv.DictWriter(fh, fieldnames=["item", "kind", "start", "final", "source"])
        w.writeheader()
        w.writerows(demand)

    summary = {
        "step": "7.8-REF",
        "title": "Parameter evolution: Final v1.0 vs project start",
        "zero_simulation": True,
        "matsim_rerun": False,
        "stages": meta,
        "n_keys_total": len(all_keys),
        "n_keys_changed_start_vs_final": len(rows),
        "n_real_parameters": len(real),
        "grouping": {g: [r["param"] for r in rows if r["mechanism"] == g]
                     for g in MECHANISM},
        "checks_passed": f"{sum(1 for c in CHECKS if c['pass'])}/{len(CHECKS)}",
        "checks": CHECKS,
    }
    (OUT / "parameter_evolution_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    LAB = {m["stage"]: m["label"] for m in meta}

    md = ["# 7.8 定版参数 vs 起点 —— 逐项对照", "",
          f"- 起点：`{STAGES[0][2]}`（6.3 最初的 MATSim 分配配置）",
          f"- 定版：`{next(x[2] for x in STAGES if x[0] == FINAL)}`"
          "（Singapore_OD_MATSim_Final_v1.0 / W01）",
          f"- 全展开键数 **{len(all_keys)}**（含 `<parameterset>`）；"
          f"起点↔定版差异 **{len(rows)}** 项，其中**实质参数 {len(real)}** 项。", "",
          "## 0. 各阶段的策略集（单列，因通用键会合并同名策略）", "",
          "| 阶段 | route-choice 策略集 |", "|---|---|"]
    md += [f"| {m['stage']} {m['label']} | `{m['strategies']}` |" for m in meta]
    md += ["", "## A. 实质参数变化（按机制）", ""]
    for g, ks in MECHANISM.items():
        sel = [r for r in rows if r["mechanism"] == g]
        if not sel:
            continue
        md += [f"### {g}", "",
               "| 参数 | 起点 | 定版 | 首次变更于 |", "|---|---|---|---|"]
        for r in sel:
            md.append(f"| `{r['param']}` | {r['start_value']} | "
                      f"**{r['final_value']}** | "
                      f"{LAB.get(r['first_changed_at'], r['first_changed_at'])} |")
        md.append("")
    md += ["## B. 需求 / 评价层（不全是 config 参数）", "",
           "| 项 | 类别 | 起点 | 定版 | 依据 |", "|---|---|---|---|---|"]
    for d in demand:
        md.append(f"| {d['item']} | {d['kind']} | {d['start']} | **{d['final']}** | {d['source']} |")
    md += ["", "## C. 非实质差异（不计入参数变化）", "",
           "| 参数 | 类别 | 起点 | 定版 |", "|---|---|---|---|"]
    for r in rows:
        if r["category"] != "★实质参数":
            md.append(f"| `{r['param']}` | {r['category']} | {r['start_value']} | {r['final_value']} |")
    md += ["", "## D. 阶段图例", "",
           "| 代号 | 含义 | 配置 |", "|---|---|---|"]
    md += [f"| {m['stage']} | {m['label']} | `{m['config']}` |" for m in meta]
    md += ["", f"## E. 校验：{summary['checks_passed']} PASS", "",
           "| 门 | 说明 | 结果 |", "|---|---|---|"]
    md += [f"| {c['check']} | {c['desc']} | {'✅ PASS' if c['pass'] else '❌ FAIL'} |"
           for c in CHECKS]
    md += ["", "> ⛔ 本件为 **read-only 附加件**，不属 7.8 冻结产品；"
           "未改任何冻结输入，未启动 MATSim。", ""]
    (OUT / "PARAMETER_EVOLUTION_vs_START.md").write_text("\n".join(md), encoding="utf-8")

    print(f"\nwritten -> {OUT}")
    n_pass = sum(1 for c in CHECKS if c["pass"])
    print(f"checks {n_pass}/{len(CHECKS)}")
    return 0 if n_pass == len(CHECKS) else 1


if __name__ == "__main__":
    raise SystemExit(main())
