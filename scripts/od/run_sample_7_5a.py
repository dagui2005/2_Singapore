#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""
run_sample_7_5a.py — Step 7.5A（三）：固定样本量实验运行器。

做什么
------
按 `reports/od_sample_7_5a/sample_matrix.csv`（7.5A 单一事实源）逐实验：
    1. `make_config_6_3.build_one(ltag, pop_dir=<样本人口目录>, ...)` 生成同源 config；
    2. 最小 patch（**唯一实验变量 = 采样率 / capacity**）：
         controller.outputDirectory / runId
         controller.lastIteration = 19        （20 it；ReRoute weight=1.0 已在基线 → 拥堵反馈启用）
         write{Events,Plans,Trips,Snapshots}Interval = 0   （磁盘控制）
         qsim.flowCapacityFactor = storageCapacityFactor = <matrix 指定>
    3. `verify_patch` 断言 f_cap / lastIteration / seed / ReRoute / routingRandomness / plans 路径；
    4. 运行 MATSim，逐迭代落 linkstats。

完全不动
--------
    λ（固定 0.075）/ network_cleaned.xml.gz / 7.3.6A Final Crosswalk / 7.1 观测靶场 /
    departure profile（沿用 6.3.3A 方法、同 seed）/ randomSeed=4711 /
    routingRandomness=0 / routingAlgorithm=SpeedyALT。

复用的关键点
------------
    人口来自 `prepare_sample_7_5a.py` 产出的 **100k 三阶段管线**
    （`reports/matsim_departure_6_3_3a_s100k/`），与 200k 冻结件**互不覆盖**。

断点续跑
--------
    每个实验输出 `reports/od_sample_7_5a/<EID>_lam0p075_cap*/`；运行前检查目标
    it.19 linkstats 是否已存在，存在即跳过 → 中断后可安全重启。

用法
----
    python scripts/od/run_sample_7_5a.py --gen-only                # 只生成/校验 config
    python scripts/od/run_sample_7_5a.py --smoke 2000              # 2000 agents × 3 it 冒烟
    python scripts/od/run_sample_7_5a.py --experiments S100        # 全量 S100
    python scripts/od/run_sample_7_5a.py --experiments S100 S100c  # S100 + 采样一致对照
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
import make_config_6_3 as cfgmod           # noqa: E402
import run_demand_scale_7_4_3 as r43       # noqa: E402  (复用 patch/verify 口径)

OUT_ROOT = ROOT / "reports" / "od_sample_7_5a"
MATRIX = OUT_ROOT / "sample_matrix.csv"
CONFIG_DIR = cfgmod.CONFIG_DIR
LOG_DIR = CONFIG_DIR / "logs"
MANIFEST = OUT_ROOT / "sample_run_manifest.json"

LAMBDA_TAG = "0p075"
EXPECTED_ITER = 19
TOTAL_ITER = 20

DOCTYPE = r43.DOCTYPE
setp = r43.setp
module_of = r43.module_of


def read_matrix(path: Path = MATRIX) -> dict[str, dict]:
    with open(path, encoding="utf-8-sig", newline="") as f:
        return {r["experiment_id"]: r for r in csv.DictReader(f)}


def cap_tag(f_cap: float) -> str:
    return f"{float(f_cap):.2f}".replace(".", "p")   # 1.00 -> 1p00


def cfg_path_of(eid: str, f_cap: float) -> Path:
    return CONFIG_DIR / f"config_{eid}_lam{LAMBDA_TAG}_cap{cap_tag(f_cap)}.xml"


def final_linkstats(out_dir: Path, run_id: str) -> Path | None:
    return r43.final_linkstats(out_dir, run_id)


def gen_experiment(eid: str, spec: dict, *, log=print):
    out_dir = ROOT / spec["output_dir"]
    dep_dir = ROOT / spec["population_dir"]
    f_cap = float(spec["f_cap"])
    cfg_path = cfg_path_of(eid, f_cap)

    pop = dep_dir / f"population_lambda_{LAMBDA_TAG}.xml.gz"
    if not pop.exists():
        raise FileNotFoundError(
            f"{pop} 不存在；请先运行 prepare_sample_7_5a.py 构建 {spec['sample_agents']} 样本人口")

    cfgmod.build_one(LAMBDA_TAG, pop_dir=dep_dir, out_root=OUT_ROOT,
                     run_prefix=f"{eid}_", cfg_path=cfg_path)
    r43.patch_config(cfg_path, out_dir=out_dir, run_id=eid,
                     f_cap=f_cap, last_iteration=EXPECTED_ITER)
    v = r43.verify_patch(cfg_path, expect_f=f_cap, expect_iter=EXPECTED_ITER,
                         expect_plans_contains=str(dep_dir.name))
    return cfg_path, out_dir, v, pop


def run_matsim(cfg_path: Path, log_name: str, heap: str) -> int:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    log = LOG_DIR / log_name
    print(f"=== 运行 {cfg_path.name} -> {log} ===")
    t0 = time.time()
    rc = matsim_env.run_java_streaming(
        ["org.matsim.run.RunMatsim", str(cfg_path)], log_path=log, heap=heap)
    print(f"--- {cfg_path.name}: exit={rc}  耗时 {(time.time()-t0)/60:.2f} min ---\n")
    return rc


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--experiments", nargs="*", default=["S100"],
                    help="要运行的 experiment_id（默认 S100；S100c 为采样一致对照）")
    ap.add_argument("--heap", default="12g")
    ap.add_argument("--smoke", type=int, default=0,
                    help="先跑 n agents × 3 迭代冒烟（验证样本人口 + config patch 生效）")
    ap.add_argument("--gen-only", action="store_true")
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()

    OUT_ROOT.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    matrix = read_matrix()

    runnable = [e for e, s in matrix.items() if str(s["mode"]).startswith("RUN")]
    unknown = [e for e in args.experiments if e not in matrix]
    if unknown:
        print(f"ERROR: 实验不在矩阵中: {unknown}")
        return 1
    skipped = [e for e in args.experiments if not str(matrix[e]["mode"]).startswith("RUN")]
    if skipped:
        print(f"NOTE: {skipped} 为 REUSE（复用既有输出），本运行器不执行。")

    print("=== MATSim 运行时 ===")
    for k, v in matsim_env.describe().items():
        print(f"  {k}: {v}")
    print(f"  output root : {OUT_ROOT}")
    print(f"  experiments : {args.experiments}   (runnable: {runnable})")
    print(f"  λ fixed     : 0.075   it: {TOTAL_ITER}\n")

    # --- 冒烟 ------------------------------------------------------------
    if args.smoke:
        eid = "S100"
        spec = matrix[eid]
        cfg_path, _, _, pop = gen_experiment(eid, spec)
        smoke_pop = CONFIG_DIR / "_smoke_7_5a_population.xml.gz"
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
        setp(module_of(root, "plans"), "inputPlansFile", str(smoke_pop.resolve()))
        setp(module_of(root, "controller"), "outputDirectory",
             str((OUT_ROOT / "_smoke_7_5a").resolve()))
        setp(module_of(root, "controller"), "runId", "smoke_7_5a")
        setp(module_of(root, "controller"), "lastIteration", "2")
        smoke_cfg = CONFIG_DIR / "_smoke_7_5a_config.xml"
        smoke_cfg.write_text(DOCTYPE + ET.tostring(root, encoding="unicode") + "\n",
                             encoding="utf-8")
        r43.verify_patch(smoke_cfg, expect_f=float(spec["f_cap"]), expect_iter=2)
        rc = run_matsim(smoke_cfg, "smoke_7_5a.log", args.heap)
        it_dir = OUT_ROOT / "_smoke_7_5a" / "ITERS"
        stats = sorted(it_dir.glob("it.*/smoke_7_5a.*.linkstats.txt.gz")) if it_dir.exists() else []
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
            continue
        cfg_path, out_dir, v, pop = gen_experiment(eid, spec)
        print(f"[{eid}] N_sample={int(spec['sample_agents']):,} f_cap={v['flowCapacityFactor']} "
              f"SCALE={float(spec['scale']):.5f} lastIter={v['lastIteration']} "
              f"seed={v['randomSeed']} alg={v['routingAlgorithmType']}")
        print(f"        population: {pop}")
        print(f"        -> {out_dir}")

        entry = {"experiment_id": eid, "role": spec["role"],
                 "sample_agents": int(spec["sample_agents"]),
                 "f_cap": float(spec["f_cap"]), "scale": float(spec["scale"]),
                 "config": str(cfg_path), "outputDirectory": str(out_dir),
                 "population": str(pop), "verified": v}

        if args.gen_only:
            entry["status"] = "GEN_ONLY"
            manifest.append(entry)
            continue

        done = final_linkstats(out_dir, eid)
        if done and not args.force:
            print(f"        已存在 {done.name} -> 跳过（断点续跑）\n")
            entry.update({"status": "SKIPPED_DONE", "linkstats": str(done)})
            manifest.append(entry)
            continue

        rc = run_matsim(cfg_path, f"{eid}_run.log", args.heap)
        rc_all |= rc
        dl = final_linkstats(out_dir, eid)
        entry.update({"status": "PASS" if rc == 0 and dl else "FAIL", "rc": rc,
                      "linkstats": str(dl) if dl else None})
        manifest.append(entry)

    MANIFEST.write_text(json.dumps(
        {"step": "7.5A", "sweep_variable": "sample_size (with capacity companion)",
         "lambda_fixed": 0.075, "iterations": TOTAL_ITER,
         "experiments": manifest,
         "lambda_selected": False, "capacity_frozen_except_sample_consistent_control": True},
        ensure_ascii=False, indent=2), encoding="utf-8")

    print("STATUS:", "PASS" if rc_all == 0 else "FAIL")
    print(f"manifest -> {MANIFEST}")
    return rc_all


if __name__ == "__main__":
    raise SystemExit(main())
