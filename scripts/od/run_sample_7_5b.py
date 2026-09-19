#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""
run_sample_7_5b.py — Step 7.5B：Sampling Rule Sensitivity 运行器（只跑 S100r）。

做什么
------
按 `reports/od_sample_7_5b/sample_matrix_7_5b.csv`（7.5B 单一事实源）：
    1. `make_config_6_3.build_one(ltag, pop_dir=<S100r 出发剖面目录>, ...)`（与 7.5A 同源）；
    2. 最小 patch（**唯一实验变量 = 采样规则**；config 与 S100c **逐字节同类**）：
         controller.outputDirectory / runId
         controller.lastIteration = 19
         write{Events,Plans,Trips,Snapshots}Interval = 0
         qsim.flowCapacityFactor = storageCapacityFactor = 0.50   （= N/N_ref，采样一致校正）
    3. `verify_patch` 断言 f_cap / lastIteration / seed / ReRoute / routingRandomness / plans 路径；
    4. 运行 MATSim，逐迭代落 linkstats。

完全冻结（与 S100c 相同）
------------------------
    λ=0.075 / N_sample=100,000 / network_cleaned.xml.gz / 7.3.6A Final Crosswalk /
    7.1 观测靶场 / departure profile（同类方法、同 seed）/ randomGenerationSeed=4711 /
    routingRandomness=0 / routingAlgorithm=SpeedyALT / 20 iterations。
    **变动的只有人口的空间分配规则**（纯 trips-proportional，无保底）。

断点续跑
--------
    输出 `reports/od_sample_7_5b/S100r_lam0p075_cap0p50/`；运行前检查 it.19 linkstats 是否存在。

用法
----
    python scripts/od/run_sample_7_5b.py --gen-only          # 只生成/校验 config
    python scripts/od/run_sample_7_5b.py --smoke 2000        # 2000 agents × 3 it 冒烟
    python scripts/od/run_sample_7_5b.py --experiments S100r # 全量
"""
from __future__ import annotations

import argparse
import csv
import gzip
import json
import sys
import time
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(r"D:\Luan\2026-05\2_Singapore")
sys.path.insert(0, str(ROOT / "scripts" / "matsim"))
sys.path.insert(0, str(ROOT / "scripts" / "od"))

import matsim_env                          # noqa: E402
import run_sample_7_5a as r75a             # noqa: E402  (复用 gen_experiment / run_matsim)
import run_demand_scale_7_4_3 as r43       # noqa: E402

OUT_ROOT = ROOT / "reports" / "od_sample_7_5b"
MATRIX = OUT_ROOT / "sample_matrix_7_5b.csv"
MANIFEST = OUT_ROOT / "sample_run_manifest_7_5b.json"
CONFIG_DIR = r75a.CONFIG_DIR
LOG_DIR = CONFIG_DIR / "logs"

# 让复用的 7.5A 助手函数写入 7.5B 的目录空间
r75a.OUT_ROOT = OUT_ROOT

LAMBDA_TAG = "0p075"
TOTAL_ITER = 20
EXPECTED_ITER = 19


def read_matrix(path: Path = MATRIX) -> dict[str, dict]:
    with open(path, encoding="utf-8-sig", newline="") as f:
        return {r["experiment_id"]: r for r in csv.DictReader(f)}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--experiments", nargs="*", default=["S100r"])
    ap.add_argument("--heap", default="12g")
    ap.add_argument("--smoke", type=int, default=0)
    ap.add_argument("--gen-only", action="store_true")
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()

    OUT_ROOT.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    matrix = read_matrix()

    unknown = [e for e in args.experiments if e not in matrix]
    if unknown:
        print(f"ERROR: 实验不在 7.5B 矩阵中: {unknown}")
        return 1

    print("=== MATSim 运行时 ===")
    for k, v in matsim_env.describe().items():
        print(f"  {k}: {v}")
    print(f"  output root : {OUT_ROOT}")
    print(f"  experiments : {args.experiments}")
    print(f"  step        : 7.5B  (single variable = sampling rule)")
    print(f"  λ fixed     : 0.075   it: {TOTAL_ITER}\n")

    # --- 冒烟 ------------------------------------------------------------
    if args.smoke:
        eid = args.experiments[0] if args.experiments else "S100r"
        spec = matrix[eid]
        cfg_path, _, _, pop = r75a.gen_experiment(eid, spec)
        smoke_pop = CONFIG_DIR / "_smoke_7_5b_population.xml.gz"
        buf, cnt, done = [], 0, False
        with gzip.open(pop, "rt", encoding="utf-8", errors="replace") as fh:
            for line in fh:
                if not done:
                    buf.append(line)
                    if line.strip().startswith("</person>"):
                        cnt += 1
                        if cnt >= args.smoke:
                            done = True
        buf.append("</population>\n")
        with gzip.open(smoke_pop, "wt", encoding="utf-8") as fh:
            fh.write("".join(buf))
        print(f"[smoke] 截断人口 {cnt} persons -> {smoke_pop}")

        root = ET.parse(cfg_path).getroot()
        r75a.setp(r75a.module_of(root, "plans"), "inputPlansFile", str(smoke_pop.resolve()))
        r75a.setp(r75a.module_of(root, "controller"), "outputDirectory",
                  str((OUT_ROOT / "_smoke_7_5b").resolve()))
        r75a.setp(r75a.module_of(root, "controller"), "runId", "smoke_7_5b")
        r75a.setp(r75a.module_of(root, "controller"), "lastIteration", "2")
        smoke_cfg = CONFIG_DIR / "_smoke_7_5b_config.xml"
        smoke_cfg.write_text(r75a.DOCTYPE + ET.tostring(root, encoding="unicode") + "\n",
                             encoding="utf-8")
        r43.verify_patch(smoke_cfg, expect_f=float(spec["f_cap"]), expect_iter=2)
        rc = r75a.run_matsim(smoke_cfg, "smoke_7_5b.log", args.heap)
        it_dir = OUT_ROOT / "_smoke_7_5b" / "ITERS"
        stats = sorted(it_dir.glob("it.*/smoke_7_5b.*.linkstats.txt.gz")) if it_dir.exists() else []
        print(f"[smoke] 每迭代 linkstats 共 {len(stats)} 份（期望 3）")
        print("STATUS:", "PASS" if rc == 0 else "FAIL")
        return rc

    # --- 全量 ------------------------------------------------------------
    manifest: list[dict] = []
    rc_all = 0
    for eid in args.experiments:
        spec = matrix[eid]
        if not str(spec["mode"]).startswith("RUN"):
            manifest.append({"experiment_id": eid, "status": "SKIPPED_REUSE",
                             "note": spec["note"], "output_dir": spec["output_dir"]})
            print(f"[{eid}] mode={spec['mode']} -> 复用既有输出，不执行\n")
            continue
        cfg_path, out_dir, v, pop = r75a.gen_experiment(eid, spec)
        print(f"[{eid}] rule={spec['sampling_rule']} N_sample={int(spec['sample_agents']):,} "
              f"f_cap={v['flowCapacityFactor']} SCALE={float(spec['scale']):.5f} "
              f"lastIter={v['lastIteration']} seed={v['randomSeed']} alg={v['routingAlgorithmType']}")
        print(f"        population: {pop}")
        print(f"        -> {out_dir}")

        entry = {"experiment_id": eid, "role": spec["role"],
                 "sampling_rule": spec["sampling_rule"],
                 "sample_agents": int(spec["sample_agents"]),
                 "f_cap": float(spec["f_cap"]), "scale": float(spec["scale"]),
                 "config": str(cfg_path), "outputDirectory": str(out_dir),
                 "population": str(pop), "verified": v}

        if args.gen_only:
            entry["status"] = "GEN_ONLY"
            manifest.append(entry)
            continue

        done = r75a.final_linkstats(out_dir, eid)
        if done and not args.force:
            print(f"        已存在 {done.name} -> 跳过（断点续跑）\n")
            entry.update({"status": "SKIPPED_DONE", "linkstats": str(done)})
            manifest.append(entry)
            continue

        rc = r75a.run_matsim(cfg_path, f"{eid}_run.log", args.heap)
        rc_all |= rc
        dl = r75a.final_linkstats(out_dir, eid)
        entry.update({"status": "PASS" if rc == 0 and dl else "FAIL", "rc": rc,
                      "linkstats": str(dl) if dl else None})
        manifest.append(entry)

    MANIFEST.write_text(json.dumps(
        {"step": "7.5B", "sweep_variable": "sampling_rule", "lambda_fixed": 0.075,
         "iterations": TOTAL_ITER, "n_sample": 100000,
         "rules": {"S100c": "FLOOR_PLUS_1", "S100r": "PURE_TRIPS_PROP"},
         "experiments": manifest,
         "lambda_selected": False,
         "capacity_frozen_except_sample_consistent_control": True},
        ensure_ascii=False, indent=2), encoding="utf-8")

    print("STATUS:", "PASS" if rc_all == 0 else "FAIL")
    print(f"manifest -> {MANIFEST}")
    return rc_all


if __name__ == "__main__":
    raise SystemExit(main())
