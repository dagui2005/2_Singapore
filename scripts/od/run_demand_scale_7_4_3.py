#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""
run_demand_scale_7_4_3.py — Step 7.4.3：demand scale 运行器（真实加车）。

做什么
------
按 `reports/od_calibration_7_4_3/demand_scale_matrix.csv`（7.4.3 单一事实源）逐实验：
    1. 以 6.3.3A 冻结人口 `population_lambda_0p075.xml.gz` 为源，
       **按 seed=20260912 的 permutation 前缀复制 agent**（嵌套子集 D02⊂D03⊂D04）
       → `reports/matsim_demand_7_4_3/pop_<EID>/population_lambda_0p075.xml.gz`
       * 每 agent 的 expansionFactor / home_link / work_link / departure end_time 逐字节不变；
       * 复制概率对每个 agent 相同 → 增量空间无偏。
    2. `make_config_6_3.build_one(ltag, pop_dir=...)` 生成同源 config，最小 patch：
         qsim.flowCapacityFactor = storageCapacityFactor = 1.00  （唯一实验外变量已冻结）
         controller.lastIteration = 19  （20 it；ReRoute weight=1.0 已在基线 → 拥堵反馈启用）
         write{Events,Plans,Trips,Snapshots}Interval = 0  （20it × 240k agents 的磁盘控制）
    3. 运行 MATSim，逐迭代落 linkstats。

完全不动
--------
    λ（固定 0.075）/ network_cleaned.xml.gz / 7.3.6A Final Crosswalk / 7.1 观测靶场 /
    departure profile / randomSeed=4711 / routingRandomness=0 / routingAlgorithm=SpeedyALT。

断点续跑
--------
每个实验输出落 `reports/od_calibration_7_4_3/<EID>_lam0p075/`。运行前检查目标 it.19
linkstats 是否已存在，存在即跳过 → 中断后可安全重启（人口文件亦复用已生成者）。

用法
----
    python scripts/od/run_demand_scale_7_4_3.py --gen-only          # 只造人口 + 生成/校验 config
    python scripts/od/run_demand_scale_7_4_3.py --smoke 2000        # 2000 agents × 3 it 冒烟
    python scripts/od/run_demand_scale_7_4_3.py                     # 全量 D02 D03 D04
    python scripts/od/run_demand_scale_7_4_3.py --experiments D03
"""
from __future__ import annotations

import argparse
import csv
import gzip
import json
import re
import sys
import time
import xml.etree.ElementTree as ET
from pathlib import Path

import numpy as np

ROOT = Path(r"D:\Luan\2026-05\2_Singapore")
sys.path.insert(0, str(ROOT / "scripts" / "matsim"))
sys.path.insert(0, str(ROOT / "scripts" / "od"))

import matsim_env                    # noqa: E402
import make_config_6_3 as cfgmod     # noqa: E402

OUT_ROOT = ROOT / "reports" / "od_calibration_7_4_3"
MATRIX_CSV = OUT_ROOT / "demand_scale_matrix.csv"
POP_STAGE = ROOT / "reports" / "matsim_demand_7_4_3"
CONFIG_DIR = cfgmod.CONFIG_DIR
LOG_DIR = CONFIG_DIR / "logs"
MANIFEST = OUT_ROOT / "demand_run_manifest.json"

LAMBDA_TAG = "0p075"
LAMBDA_FIXED = 0.075
CAP_FIXED = 1.00
FROZEN_SEED = "4711"
EXPECTED_ITER = 19
TOTAL_ITER = 20
DUP_SEED = 20260912

DOCTYPE = (
    '<?xml version="1.0" encoding="UTF-8"?>\n'
    '<!DOCTYPE config SYSTEM "http://www.matsim.org/files/dtd/config_v2.dtd">\n'
)


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------
def setp(mod_el: ET.Element, name: str, value: str) -> None:
    for p in mod_el.findall("param"):
        if p.get("name") == name:
            p.set("value", value)
            return
    ET.SubElement(mod_el, "param", {"name": name, "value": value})


def module_of(root: ET.Element, name: str) -> ET.Element:
    for m in root.findall("module"):
        if m.get("name") == name:
            return m
    raise KeyError(name)


def read_matrix(path: Path = MATRIX_CSV) -> dict[str, dict]:
    rows = {}
    with open(path, encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            rows[r["experiment_id"]] = r
    return rows


def pop_dir(eid: str) -> Path:
    return POP_STAGE / f"pop_{eid}"


def pop_file(eid: str) -> Path:
    return pop_dir(eid) / f"population_lambda_{LAMBDA_TAG}.xml.gz"


def exp_out_dir(eid: str) -> Path:
    return OUT_ROOT / f"{eid}_lam{LAMBDA_TAG}"


def dem_tag(f: float) -> str:
    return f"{float(f):.2f}".replace(".", "p")      # 1.10 -> 1p10


def final_linkstats(out_dir: Path, run_id: str) -> Path | None:
    d = out_dir / "ITERS" / f"it.{EXPECTED_ITER}"
    if not d.exists():
        return None
    cand = sorted(d.glob(f"{run_id}.*.linkstats.txt.gz")) or sorted(d.glob("*.linkstats.txt.gz"))
    return cand[0] if cand else None


# --------------------------------------------------------------------------
# population replication
# --------------------------------------------------------------------------
def count_persons(xml_path: Path) -> int:
    n = 0
    with gzip.open(xml_path, "rt", encoding="utf-8", errors="replace") as fh:
        for line in fh:
            if line.lstrip().startswith("<person "):
                n += 1
    return n


def population_stats(xml_path: Path) -> dict:
    """复核复制后人口：persons / Σ expansion_factor / Σ od_trips。"""
    n = 0
    s_ef = 0.0
    s_od = 0.0
    with gzip.open(xml_path, "rt", encoding="utf-8", errors="replace") as fh:
        for line in fh:
            if line.lstrip().startswith("<person "):
                n += 1
            m = re.search(r'name="expansionFactor" class="java.lang.Double">([0-9eE\.\-\+]+)<', line)
            if m:
                s_ef += float(m.group(1))
            m2 = re.search(r'name="odTrips" class="java.lang.Double">([0-9eE\.\-\+]+)<', line)
            if m2:
                s_od += float(m2.group(1))
    return {"persons": n, "sum_expansion_factor": s_ef, "sum_od_trips": s_od}


def _dup_block(block: list[str]) -> list[str]:
    first = block[0]
    m = re.search(r'id="([^"]+)"', first)
    if not m:
        raise ValueError(f"无法解析 person id: {first[:120]}")
    oid = m.group(1)
    nid = f"{oid}_dup"
    first2 = first.replace(f'id="{oid}"', f'id="{nid}"', 1)
    # 防止极端情况下原文件已存在 _dup 后缀：确保不以 _dup 结尾的原 id 才可复制
    if oid.endswith("_dup"):
        raise ValueError(f"源人口已含 _dup 后缀 id，拒绝二次复制: {oid}")
    return [first2] + block[1:]


def build_population(src: Path, dst: Path, n_target: int,
                     seed: int = DUP_SEED, log=print) -> dict:
    """以 seed 的 permutation 前缀复制 agent 至 n_target 人。嵌套、无偏、可复现。"""
    n0 = count_persons(src)
    if n_target < n0:
        raise ValueError(f"n_target({n_target}) < 源人口({n0})；本步骤只做需求放大")
    k = n_target - n0
    perm = np.random.default_rng(seed).permutation(n0)
    dup_ord = set(int(x) for x in perm[:k].tolist())

    dst.parent.mkdir(parents=True, exist_ok=True)
    header_done = False
    in_person = False
    idx = -1
    written = 0
    dup_written = 0
    block: list[str] = []

    with gzip.open(src, "rt", encoding="utf-8", errors="replace") as fin, \
            gzip.open(dst, "wt", encoding="utf-8", compresslevel=6) as fout:
        for line in fin:
            if not in_person:
                if line.lstrip().startswith("<person "):
                    in_person = True
                    idx += 1
                    block = [line]
                    continue
                if not header_done:
                    fout.write(line)
                    if line.lstrip().startswith("<population"):
                        header_done = True
                continue
            block.append(line)
            if "</person>" in line:
                in_person = False
                if idx in dup_ord:
                    fout.writelines(_dup_block(block))
                    dup_written += 1
                fout.writelines(block)
                written += 1
                block = []
        fout.write("</population>\n")

    st = population_stats(dst)
    return {
        "source": str(src), "target": str(dst),
        "n_source": n0, "n_target_requested": n_target,
        "n_written_total": written, "n_dup_written": dup_written,
        **st,
    }


# --------------------------------------------------------------------------
# config build + patch
# --------------------------------------------------------------------------
def patch_config(cfg_path: Path, *, out_dir: Path, run_id: str,
                 f_cap: float, last_iteration: int) -> None:
    tree = ET.parse(cfg_path)
    root = tree.getroot()
    c = module_of(root, "controller")
    setp(c, "outputDirectory", str(out_dir))
    setp(c, "runId", run_id)
    setp(c, "lastIteration", str(last_iteration))
    setp(c, "writeEventsInterval", "0")
    setp(c, "writePlansInterval", "0")
    setp(c, "writeTripsInterval", "0")
    setp(c, "writeSnapshotsInterval", "0")

    q = module_of(root, "qsim")
    setp(q, "flowCapacityFactor", f"{f_cap:g}")
    setp(q, "storageCapacityFactor", f"{f_cap:g}")

    cfg_path.write_text(DOCTYPE + ET.tostring(root, encoding="unicode") + "\n",
                        encoding="utf-8")


def verify_patch(cfg_path: Path, *, expect_f: float, expect_iter: int,
                 expect_plans_contains: str = "") -> dict:
    root = ET.parse(cfg_path).getroot()
    q = module_of(root, "qsim")
    c = module_of(root, "controller")
    g = module_of(root, "global")

    def pget(mod, name):
        return next((p.get("value") for p in mod.findall("param") if p.get("name") == name), None)

    fcp = pget(q, "flowCapacityFactor")
    st = pget(q, "storageCapacityFactor")
    last = pget(c, "lastIteration")
    seed = pget(g, "randomSeed")
    plans = pget(module_of(root, "plans"), "inputPlansFile")
    rnd = pget(module_of(root, "routing"), "routingRandomness")
    alg = pget(module_of(root, "controller"), "routingAlgorithmType")
    strategies = [p.get("value") for ps in module_of(root, "replanning").findall("parameterset")
                  for p in ps.findall("param") if p.get("name") == "strategyName"]

    assert abs(float(fcp) - expect_f) < 1e-12, f"flowCapacityFactor {fcp} != {expect_f}"
    assert abs(float(st) - expect_f) < 1e-12, f"storageCapacityFactor {st} != {expect_f}"
    assert int(last) == expect_iter, f"lastIteration {last} != {expect_iter}"
    assert seed == FROZEN_SEED, f"randomSeed {seed} != {FROZEN_SEED}"
    assert "ReRoute" in strategies, "缺少 ReRoute 策略（拥堵反馈载体）"
    assert rnd is not None and abs(float(rnd)) < 1e-12, f"routingRandomness={rnd} 必须为 0"
    assert alg == "SpeedyALT", f"routingAlgorithmType={alg} != SpeedyALT"
    if expect_plans_contains:
        assert expect_plans_contains in plans, f"inputPlansFile={plans} 未指向 {expect_plans_contains}"

    return {
        "flowCapacityFactor": fcp, "storageCapacityFactor": st,
        "lastIteration": last, "randomSeed": seed, "routingRandomness": rnd,
        "routingAlgorithmType": alg, "inputPlansFile": plans,
        "strategies": strategies,
    }


def gen_experiment(eid: str, spec: dict, *, build_pop: bool, log=print):
    """造人口（如需）+ 生成 config。返回 (cfg_path, out_dir, verify, pop_report|None)。"""
    out_dir = exp_out_dir(eid)
    cfg_path = CONFIG_DIR / f"config_{eid}_lam{LAMBDA_TAG}_dem{dem_tag(spec['f_demand'])}.xml"
    pdir = pop_dir(eid)
    pfile = pop_file(eid)

    pop_report = None
    if build_pop:
        src = ROOT / spec["population_source"]
        if not src.exists():
            raise FileNotFoundError(src)
        n_target = int(spec["n_agents"])
        if pfile.exists():
            st = population_stats(pfile)
            if st["persons"] == n_target:
                log(f"[{eid}] 人口已存在且 persons={st['persons']:,} -> 复用 {pfile}")
                pop_report = {"reused": True, "target": str(pfile), **st}
            else:
                log(f"[{eid}] 人口 persons={st['persons']:,} != {n_target:,} -> 重建")
                pop_report = build_population(src, pfile, n_target, log=log)
        else:
            log(f"[{eid}] 复制人口 -> {n_target:,} persons ...")
            pop_report = build_population(src, pfile, n_target, log=log)

    cfgmod.build_one(LAMBDA_TAG, pop_dir=pdir, out_root=OUT_ROOT,
                     run_prefix=f"{eid}_", cfg_path=cfg_path)
    patch_config(cfg_path, out_dir=out_dir, run_id=eid,
                 f_cap=CAP_FIXED, last_iteration=EXPECTED_ITER)
    v = verify_patch(cfg_path, expect_f=CAP_FIXED, expect_iter=EXPECTED_ITER,
                     expect_plans_contains=f"pop_{eid}")
    return cfg_path, out_dir, v, pop_report


def run_matsim(cfg_path: Path, log_name: str, heap: str) -> int:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    log = LOG_DIR / log_name
    print(f"=== 运行 {cfg_path.name} -> {log} ===")
    t0 = time.time()
    rc = matsim_env.run_java_streaming(
        ["org.matsim.run.RunMatsim", str(cfg_path)], log_path=log, heap=heap)
    print(f"--- {cfg_path.name}: exit={rc}  耗时 {(time.time()-t0)/60:.2f} min ---\n")
    return rc


# --------------------------------------------------------------------------
# main
# --------------------------------------------------------------------------
def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--experiments", nargs="*", default=["D02", "D03", "D04"],
                    help="要运行的 experiment_id（默认 D02 D03 D04；D01 复用 E06）")
    ap.add_argument("--heap", default="12g")
    ap.add_argument("--smoke", type=int, default=0,
                    help="先跑 n agents × 3 迭代冒烟（验证复制人口 + 组合 patch 生效）")
    ap.add_argument("--gen-only", action="store_true")
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()

    OUT_ROOT.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    matrix = read_matrix()

    unknown = [e for e in args.experiments if e not in matrix]
    if unknown:
        print(f"ERROR: 实验不在矩阵中: {unknown}")
        return 1

    print("=== MATSim 运行时 ===")
    for k, v in matsim_env.describe().items():
        print(f"  {k}: {v}")
    print(f"  population stage : {POP_STAGE}")
    print(f"  output root      : {OUT_ROOT}")
    print(f"  experiments      : {args.experiments}")
    print(f"  λ fixed          : {LAMBDA_FIXED}   f_cap fixed: {CAP_FIXED}   it: {TOTAL_ITER}")
    print()

    # --- 冒烟 ------------------------------------------------------------
    if args.smoke:
        eid = "D02"
        spec = matrix[eid]
        cfg_path, _, _, pop_rep = gen_experiment(eid, spec, build_pop=True)
        spec_pop = pop_file(eid)
        # 截断冒烟人口
        smoke_pop = CONFIG_DIR / "_smoke_7_4_3_population.xml.gz"
        buf, cnt, done = [], 0, False
        with gzip.open(spec_pop, "rt", encoding="utf-8", errors="replace") as fh:
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
        setp(module_of(root, "controller"), "outputDirectory", str((OUT_ROOT / "_smoke_7_4_3").resolve()))
        setp(module_of(root, "controller"), "runId", "smoke_7_4_3")
        setp(module_of(root, "controller"), "lastIteration", "2")
        smoke_cfg = CONFIG_DIR / "_smoke_7_4_3_config.xml"
        smoke_cfg.write_text(DOCTYPE + ET.tostring(root, encoding="unicode") + "\n", encoding="utf-8")
        verify_patch(smoke_cfg, expect_f=CAP_FIXED, expect_iter=2)
        rc = run_matsim(smoke_cfg, "smoke_7_4_3.log", args.heap)
        it_dir = OUT_ROOT / "_smoke_7_4_3" / "ITERS"
        stats = sorted(it_dir.glob("it.*/smoke_7_4_3.*.linkstats.txt.gz")) if it_dir.exists() else []
        print(f"[smoke] 每迭代 linkstats 共 {len(stats)} 份（期望 3）")
        if pop_rep:
            print(f"[smoke] 复制人口 ΣEF={pop_rep.get('sum_expansion_factor'):,.1f} "
                  f"persons={pop_rep.get('persons'):,}")
        print("STATUS:", "PASS" if rc == 0 else "FAIL")
        return rc

    # --- 全量 ------------------------------------------------------------
    manifest: list[dict] = []
    rc_all = 0
    for eid in args.experiments:
        spec = matrix[eid]
        cfg_path, out_dir, v, pop_rep = gen_experiment(eid, spec, build_pop=True)
        print(f"[{eid}] f_demand={spec['f_demand']} agents={spec['n_agents']} "
              f"f_cap={v['flowCapacityFactor']} lastIter={v['lastIteration']} seed={v['randomSeed']} alg={v['routingAlgorithmType']}")
        if pop_rep:
            print(f"        population: persons={pop_rep.get('persons'):,} "
                  f"ΣEF={pop_rep.get('sum_expansion_factor'):,.1f}")
        print(f"        -> {out_dir}")

        entry = {"experiment_id": eid, "f_demand": float(spec["f_demand"]),
                 "n_agents": int(spec["n_agents"]),
                 "config": str(cfg_path), "outputDirectory": str(out_dir),
                 "population": str(pop_file(eid)),
                 "population_stats": pop_rep}

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
        {"step": "7.4.3", "sweep_variable": "f_demand",
         "lambda_fixed": LAMBDA_FIXED, "capacity_fixed": CAP_FIXED,
         "iterations": TOTAL_ITER, "frozen_seed": FROZEN_SEED,
         "experiments": manifest,
         "lambda_selected": False, "parameters_changed": True},
        ensure_ascii=False, indent=2), encoding="utf-8")

    print("STATUS:", "PASS" if rc_all == 0 else "FAIL")
    print(f"manifest -> {MANIFEST}")
    return rc_all


if __name__ == "__main__":
    raise SystemExit(main())
