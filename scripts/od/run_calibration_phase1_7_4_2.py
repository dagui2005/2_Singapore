#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""
run_calibration_phase1_7_4_2.py — Step 7.4.2 Phase 1：λ=0.050 下 capacity 三档联合校准。

预注册口径（来自 reports/od_calibration_7_4_1/calibration_experiment_matrix.csv）
-------------------------------------------------------------------------
    第一阶段只跑 E01 / E02 / E03：
        E01  λ=0.050  f_cap=0.50  20 it
        E02  λ=0.050  f_cap=0.75  20 it
        E03  λ=0.050  f_cap=1.00  20 it
    唯一打开的变量 = flowCapacityFactor（storage=flow 同值）。

完全冻结（本脚本不改）
--------------------
    OD / population(6.3.3A departure profile) / departure time / network topology
    (network_cleaned.xml.gz) / permlanes / crosswalk(7.3.6A) / routing(SpeedyALT,
    routingRandomness=0.0) / randomSeed=4711 / threads=8。
    Final Calibration Crosswalk 只在**评价阶段**使用，不写入 MATSim config。

两个 MATSim 2026 约束（已实测）
------------------------------
1. GlobalConfigGroup.checkConsistency 强制 |storage − flow| 相对容差 = 0，且 setter 被注释
   → 无法经 XML 放宽 ⇒ patch 时两者必须**同时**设为 f（这正是 sampled-population 语义）。
2. route choice 固定 20 iterations：lastIteration=19；ReRoute weight=1.0 已在基线 config，
   travelTimeCalculator 已配好 → 多迭代即自动启用拥堵反馈。

磁盘控制：20 迭代 × 200k agents 若写 events/plans/trips 会产生数十 GB。故
writeEventsInterval / writePlansInterval / writeTripsInterval / writeSnapshotsInterval = 0，
只保留每迭代 linkstats（writeLinkStatsInterval=1，本实验唯一测量需求）。

断点续跑
--------
每个实验的输出落在独立目录 reports/od_calibration_7_4_2/<EID>_lam*/。运行前检查
目标 it.19 linkstats 是否已存在，存在即跳过 → 中断后可安全重启。

用法
----
    python scripts/od/run_calibration_phase1_7_4_2.py --gen-only     # 只生成并校验 config
    python scripts/od/run_calibration_phase1_7_4_2.py --smoke 2000   # 2000 agents × 3 it 冒烟
    python scripts/od/run_calibration_phase1_7_4_2.py                # 全量 Phase1（E01-E03）
    python scripts/od/run_calibration_phase1_7_4_2.py --experiments E02 E03
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

import matsim_env            # noqa: E402
import make_config_6_3 as cfgmod  # noqa: E402

MATRIX_CSV = ROOT / "reports" / "od_calibration_7_4_1" / "calibration_experiment_matrix.csv"
OUT_ROOT = ROOT / "reports" / "od_calibration_7_4_2"
CONFIG_DIR = cfgmod.CONFIG_DIR
LOG_DIR = CONFIG_DIR / "logs"
POP_DIR = ROOT / "reports" / "matsim_departure_6_3_3a"   # 6.3.3A 冻结出发时刻剖面
MANIFEST = OUT_ROOT / "phase1_run_manifest.json"

PHASE1_DEFAULT = ["E01", "E02", "E03"]
FROZEN_SEED = "4711"
EXPECTED_ITER = 19          # lastIteration
TOTAL_ITER = 20

DOCTYPE = (
    '<?xml version="1.0" encoding="UTF-8"?>\n'
    '<!DOCTYPE config SYSTEM "http://www.matsim.org/files/dtd/config_v2.dtd">\n'
)


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------
def lam_tag(lam: float) -> str:
    return f"{lam:.3f}".replace(".", "p")     # 0.050 -> 0p050


def cap_tag(f: float) -> str:
    return f"{f:.2f}".replace(".", "p")       # 0.50  -> 0p50


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


def exp_out_dir(eid: str, lam: float, f: float) -> Path:
    return OUT_ROOT / f"{eid}_lam{lam_tag(lam)}_cap{cap_tag(f)}"


def final_linkstats(out_dir: Path, run_id: str) -> Path | None:
    """返回 20 迭代运行中最末迭代（it.19）的 linkstats 路径（若已完成）。"""
    cand = sorted((out_dir / "ITERS").glob(
        f"it.{EXPECTED_ITER}/{run_id}.*.linkstats.txt.gz")) if (out_dir / "ITERS").exists() else []
    return cand[0] if cand else None


# --------------------------------------------------------------------------
# config build + patch
# --------------------------------------------------------------------------
def patch_config(cfg_path: Path, *, out_dir: Path, run_id: str,
                 f_cap: float, last_iteration: int) -> None:
    """对 build_one 生成的 config 做最小 patch。

    唯一实验变量 = qsim.flowCapacityFactor（= storageCapacityFactor，MATSim 硬约束）
    + controller.lastIteration（route-choice 固定 20 it）。
    其余（seed / network / plans / permlanes / routing / TTC / strategy）保持基线逐字节不变。
    """
    tree = ET.parse(cfg_path)
    root = tree.getroot()
    c = module_of(root, "controller")
    setp(c, "outputDirectory", str(out_dir))
    setp(c, "runId", run_id)
    setp(c, "lastIteration", str(last_iteration))
    # 磁盘控制：中间迭代不写 events/plans/trips/snapshots（linkstats 保留每迭代）
    setp(c, "writeEventsInterval", "0")
    setp(c, "writePlansInterval", "0")
    setp(c, "writeTripsInterval", "0")
    setp(c, "writeSnapshotsInterval", "0")

    q = module_of(root, "qsim")
    setp(q, "flowCapacityFactor", f"{f_cap:g}")
    setp(q, "storageCapacityFactor", f"{f_cap:g}")

    cfg_path.write_text(DOCTYPE + ET.tostring(root, encoding="unicode") + "\n",
                        encoding="utf-8")


def verify_patch(cfg_path: Path, *, expect_f: float, expect_iter: int) -> dict:
    """读回 config 做防呆断言，返回关键值 dict。"""
    root = ET.parse(cfg_path).getroot()
    q = module_of(root, "qsim")
    c = module_of(root, "controller")
    g = module_of(root, "global")

    def pget(mod, name):
        return next((p.get("value") for p in mod.findall("param") if p.get("name") == name), None)

    fcp = pget(q, "flowCapacityFactor")
    st = pget(q, "storageCapacityFactor")
    last = pget(c, "lastIteration")
    rid = pget(c, "runId")
    outdir = pget(c, "outputDirectory")
    seed = pget(g, "randomSeed")
    plans = pget(module_of(root, "plans"), "inputPlansFile")
    net = pget(module_of(root, "network"), "inputNetworkFile")
    rnd = pget(module_of(root, "routing"), "routingRandomness")
    strategies = [p.get("value") for ps in module_of(root, "replanning").findall("parameterset")
                  for p in ps.findall("param") if p.get("name") == "strategyName"]

    assert abs(float(fcp) - expect_f) < 1e-12, f"flowCapacityFactor {fcp} != {expect_f}"
    assert abs(float(st) - expect_f) < 1e-12, f"storageCapacityFactor {st} != {expect_f}"
    assert int(last) == expect_iter, f"lastIteration {last} != {expect_iter}"
    assert seed == FROZEN_SEED, f"randomSeed {seed} != {FROZEN_SEED}"
    assert "ReRoute" in strategies, "缺少 ReRoute 策略（拥堵反馈载体）"
    assert rnd is not None and abs(float(rnd)) < 1e-12, f"routingRandomness={rnd} 必须为 0"

    return {
        "flowCapacityFactor": fcp, "storageCapacityFactor": st,
        "lastIteration": last, "runId": rid, "outputDirectory": outdir,
        "randomSeed": seed, "routingRandomness": rnd,
        "inputPlansFile": plans, "inputNetworkFile": net,
        "strategies": strategies,
    }


def gen_experiment(eid: str, spec: dict) -> tuple[Path, Path, dict]:
    """生成并 patch 单实验 config，返回 (cfg_path, out_dir, verify_dict)。"""
    lam = float(spec["lambda"])
    f = float(spec["capacity_factor"])
    ltag = lam_tag(lam)
    out_dir = exp_out_dir(eid, lam, f)
    cfg_path = CONFIG_DIR / f"config_{eid}_lam{ltag}_cap{cap_tag(f)}.xml"

    # 注意：build_one 的 lam 形参是**标签字符串**（如 "0p050"），不是浮点。
    cfgmod.build_one(ltag, pop_dir=POP_DIR, out_root=OUT_ROOT,
                     run_prefix=f"{eid}_", cfg_path=cfg_path)
    patch_config(cfg_path, out_dir=out_dir, run_id=eid,
                 f_cap=f, last_iteration=EXPECTED_ITER)
    v = verify_patch(cfg_path, expect_f=f, expect_iter=EXPECTED_ITER)
    return cfg_path, out_dir, v


def truncate_population(src: Path, dst: Path, n: int) -> int:
    buf, cnt, done = [], 0, False
    with gzip.open(src, "rt", encoding="utf-8") as fh:
        for line in fh:
            if not done:
                buf.append(line)
                if line.strip().startswith("</person>"):
                    cnt += 1
                    if cnt >= n:
                        done = True
    buf.append("</population>\n")
    with gzip.open(dst, "wt", encoding="utf-8") as fh:
        fh.write("".join(buf))
    return cnt


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
    ap.add_argument("--experiments", nargs="*", default=PHASE1_DEFAULT,
                    help="要运行的 experiment_id（默认 E01 E02 E03）")
    ap.add_argument("--phase", type=int, default=1,
                    help="写入 manifest 的 phase 号（默认 1；Phase 2 λ 扫描用 2）")
    ap.add_argument("--manifest", type=Path, default=None,
                    help="manifest 输出路径（默认按 phase 命名：phase<phase>_run_manifest.json）")
    ap.add_argument("--heap", default="12g")
    ap.add_argument("--smoke", type=int, default=0,
                    help="先跑 n agents × 3 迭代冒烟（验证组合 patch 生效）")
    ap.add_argument("--gen-only", action="store_true")
    ap.add_argument("--force", action="store_true",
                    help="忽略断点续跑检查，强制重跑")
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
    print(f"  population     : {POP_DIR}")
    print(f"  output root    : {OUT_ROOT}")
    print(f"  experiments    : {args.experiments}")
    print(f"  frozen seed    : {FROZEN_SEED}")
    print(f"  iterations     : {TOTAL_ITER} (lastIteration={EXPECTED_ITER})")
    print()

    # --- 冒烟 ------------------------------------------------------------
    if args.smoke:
        spec = matrix["E02"]                       # f=0.75 验证 patch
        lam = float(spec["lambda"])
        f = float(spec["capacity_factor"])
        pop_src = POP_DIR / f"population_lambda_{lam_tag(lam)}.xml.gz"
        if not pop_src.exists():
            print(f"ERROR: population 缺失 {pop_src}")
            return 1
        pop_dst = CONFIG_DIR / "_smoke_7_4_2_population.xml.gz"
        got = truncate_population(pop_src, pop_dst, args.smoke)
        print(f"[smoke] 截断人口 {got} persons -> {pop_dst}")

        cfg_path, _, _ = gen_experiment("E02", spec)
        tree = ET.parse(cfg_path)
        root = tree.getroot()
        setp(module_of(root, "plans"), "inputPlansFile", str(pop_dst.resolve()))
        setp(module_of(root, "controller"), "outputDirectory",
             str((OUT_ROOT / "_smoke_7_4_2").resolve()))
        setp(module_of(root, "controller"), "runId", "smoke_7_4_2")
        setp(module_of(root, "controller"), "lastIteration", "2")   # 3 迭代
        smoke_cfg = CONFIG_DIR / "_smoke_7_4_2_config.xml"
        smoke_cfg.write_text(DOCTYPE + ET.tostring(root, encoding="unicode") + "\n",
                             encoding="utf-8")
        verify_patch(smoke_cfg, expect_f=f, expect_iter=2)
        rc = run_matsim(smoke_cfg, "smoke_7_4_2.log", args.heap)
        it_dir = OUT_ROOT / "_smoke_7_4_2" / "ITERS"
        stats = sorted(it_dir.glob("it.*/smoke_7_4_2.*.linkstats.txt.gz")) if it_dir.exists() else []
        print(f"[smoke] 每迭代 linkstats 共 {len(stats)} 份（期望 3）")
        print("STATUS:", "PASS" if rc == 0 else "FAIL")
        return rc

    # --- 全量 ------------------------------------------------------------
    manifest: list[dict] = []
    rc_all = 0
    for eid in args.experiments:
        spec = matrix[eid]
        lam = float(spec["lambda"])
        f = float(spec["capacity_factor"])
        cfg_path, out_dir, v = gen_experiment(eid, spec)
        print(f"[{eid}] λ={lam:.3f} f_cap={v['flowCapacityFactor']} "
              f"storage={v['storageCapacityFactor']} lastIter={v['lastIteration']} "
              f"seed={v['randomSeed']}")
        print(f"        -> {out_dir}")

        done = final_linkstats(out_dir, eid)
        if args.gen_only:
            manifest.append({"experiment_id": eid, "status": "GEN_ONLY",
                             "config": str(cfg_path), "outputDirectory": str(out_dir)})
            continue

        if done and not args.force:
            print(f"        已存在 {done.name} -> 跳过（断点续跑）\n")
            manifest.append({"experiment_id": eid, "status": "SKIPPED_DONE",
                             "config": str(cfg_path), "outputDirectory": str(out_dir),
                             "linkstats": str(done)})
            continue

        rc = run_matsim(cfg_path, f"{eid}_run.log", args.heap)
        rc_all |= rc
        dl = final_linkstats(out_dir, eid)
        manifest.append({
            "experiment_id": eid, "status": "PASS" if rc == 0 and dl else "FAIL",
            "rc": rc, "config": str(cfg_path), "outputDirectory": str(out_dir),
            "linkstats": str(dl) if dl else None,
        })

    manifest_path = args.manifest or (OUT_ROOT / f"phase{args.phase}_run_manifest.json")
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(
        {"step": "7.4.2", "phase": args.phase, "experiments": manifest,
         "frozen_seed": FROZEN_SEED, "iterations": TOTAL_ITER,
         "lambda_selected": False, "parameters_changed": True},
        ensure_ascii=False, indent=2), encoding="utf-8")

    print("STATUS:", "PASS" if rc_all == 0 else "FAIL")
    print(f"manifest -> {manifest_path}")
    return rc_all


if __name__ == "__main__":
    raise SystemExit(main())
