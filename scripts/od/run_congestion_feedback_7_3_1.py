#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
run_congestion_feedback_7_3_1.py — Step 7.3.1 Congestion-feedback Sensitivity（λ=0.05）。

实验口径（用户预注册）：
    λ=0.05；capacity 固定 1.0（7.2.1 冻结基线，storage=flow 同值）；
    OD / population(6.3.3A) / departure profile / network topology / permlanes / crosswalk 全冻结。
    唯一打开：多迭代拥堵反馈 —— lastIteration ↑（ReRoute weight=1.0 已在基线 config 中，
    单迭代下被旁路；travelTimeCalculator 已配好 car/binSize 900/optimistic/average，
    多迭代即自动启用）。routingRandomness=0.0（确定性最短路），timeAllocationMutator 与
    mode choice 均不在策略中 → 出发时刻与方式不会漂移。

嵌套设计（同 seed + 确定性 ReRoute ⇒ lastIteration 只是截断）：
    预注册检查点 {1, 5, 10, 20} 迭代 ↔ it.0 / it.4 / it.9 / it.19，全部由**一次**
    lastIteration=19 的全量运行覆盖（it.k = 第 k+1 次迭代后的状态）；
    1 迭代锚点 = 冻结 6.3.3B（7.2.2 已逐位复现 f=1.00 档）。
    另跑一次 lastIteration=4 的 5 迭代运行做**嵌套性验证**（其 it.0–it.4 应与
    20 迭代运行逐位一致）；若不一致 ⇒ 存在隐藏状态，检查点必须改为独立运行。

磁盘控制（20 迭代 × 200k agents）：
    writeEventsInterval / writePlansInterval / writeTripsInterval / writeSnapshotsInterval
    置 0（只保留最终迭代输出与每迭代 linkstats：writeLinkStatsInterval=1、
    averageLinkStatsOverIterations=1 保持不变——这是本实验的全部测量需求）。

用法
----
    python scripts/od/run_congestion_feedback_7_3_1.py --smoke 2000   # 冒烟：2000 agents × 3 迭代
    python scripts/od/run_congestion_feedback_7_3_1.py                # 全量：20 迭代 + 5 迭代验证
    python scripts/od/run_congestion_feedback_7_3_1.py --gen-only
"""
from __future__ import annotations

import argparse
import gzip
import sys
import time
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(r"D:\Luan\2026-05\2_Singapore")
sys.path.insert(0, str(ROOT / "scripts" / "matsim"))
sys.path.insert(0, str(ROOT / "scripts" / "od"))

import matsim_env  # noqa: E402
import make_config_6_3 as cfgmod  # noqa: E402

OUT_ROOT = ROOT / "reports" / "od_calibration_7_3_1"
CONFIG_DIR = cfgmod.CONFIG_DIR
LOG_DIR = CONFIG_DIR / "logs"
POP_DIR = ROOT / "reports" / "matsim_departure_6_3_3a"   # 6.3.3A 冻结出发时刻剖面
DOCTYPE = (
    '<?xml version="1.0" encoding="UTF-8"?>\n'
    '<!DOCTYPE config SYSTEM "http://www.matsim.org/files/dtd/config_v2.dtd">\n'
)


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


def patch_config(cfg_path: Path, *, out_dir: Path, run_id: str, last_iteration: int) -> None:
    """对 build_one 生成的 config 做最小 patch。

    唯一实验变量 = controller.lastIteration（其余：qsim 两 factor 保持 1.0、
    strategy 保持基线 ReRoute weight=1.0、TTC 保持基线）。
    另做磁盘控制：中间迭代不写 events/plans/trips/snapshots（linkstats 保留每迭代）。
    """
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
    body = ET.tostring(root, encoding="unicode")
    cfg_path.write_text(DOCTYPE + body + "\n", encoding="utf-8")


def truncate_population(src: Path, dst: Path, n: int) -> int:
    buf, cnt, done = [], 0, False
    with gzip.open(src, "rt", encoding="utf-8") as f:
        for line in f:
            if not done:
                buf.append(line)
                if line.strip().startswith("</person>"):
                    cnt += 1
                    if cnt >= n:
                        done = True
    buf.append("</population>\n")
    with gzip.open(dst, "wt", encoding="utf-8") as f:
        f.write("".join(buf))
    return cnt


def gen_iter_config(n_iter: int, lam: str = "0p050") -> tuple[Path, Path]:
    """生成并 patch 单个迭代档 config，返回 (cfg_path, out_dir)。

    n_iter = 迭代次数（1 → lastIteration=0 → it.0；20 → lastIteration=19 → it.0..19）。
    """
    tag = f"it{n_iter}"
    out_dir = OUT_ROOT / f"iterations_{n_iter:02d}"
    cfg_path = CONFIG_DIR / f"config_cf_{tag}_lam{lam}.xml"
    cfgmod.build_one(
        lam,
        pop_dir=POP_DIR,
        out_root=OUT_ROOT,
        run_prefix=f"cf_{tag}_",
        cfg_path=cfg_path,
    )
    patch_config(cfg_path, out_dir=out_dir, run_id=f"cf_{tag}",
                 last_iteration=n_iter - 1)
    return cfg_path, out_dir


def verify_patch(cfg_path: Path) -> int:
    """读回 config 确认 patch 生效（防呆）。"""
    root = ET.parse(cfg_path).getroot()
    c = module_of(root, "controller")
    last = next(p.get("value") for p in c.findall("param") if p.get("name") == "lastIteration")
    rid = next(p.get("value") for p in c.findall("param") if p.get("name") == "runId")
    q = module_of(root, "qsim")
    fcp = next(p.get("value") for p in q.findall("param") if p.get("name") == "flowCapacityFactor")
    st = next(p.get("value") for p in q.findall("param") if p.get("name") == "storageCapacityFactor")
    rep = module_of(root, "replanning")
    strategies = [p.get("value") for ps in rep.findall("parameterset")
                  for p in ps.findall("param") if p.get("name") == "strategyName"]
    ttc = module_of(root, "travelTimeCalculator")
    ttc_modes = next(p.get("value") for p in ttc.findall("param") if p.get("name") == "analyzedModes")
    plans = next(p.get("value") for p in module_of(root, "plans").findall("param")
                 if p.get("name") == "inputPlansFile")
    print(f"  [verify] {cfg_path.name}: lastIteration={last} runId={rid} "
          f"flowCap={fcp} storageCap={st}")
    print(f"           strategies={strategies} ttcModes={ttc_modes}")
    print(f"           plans={plans}")
    assert int(last) >= 0
    assert abs(float(fcp) - 1.0) < 1e-12 and abs(float(st) - 1.0) < 1e-12, \
        "7.3.1 口径：capacity 必须固定 1.0"
    assert "ReRoute" in strategies, "ReRoute 策略必须存在（拥堵反馈的唯一载体）"
    return int(last)


def run_matsim(cfg_path: Path, log_name: str, heap: str) -> int:
    log = LOG_DIR / log_name
    print(f"=== 运行 {cfg_path.name} -> {log} ===")
    t0 = time.time()
    rc = matsim_env.run_java_streaming(
        ["org.matsim.run.RunMatsim", str(cfg_path)], log_path=log, heap=heap)
    print(f"--- {cfg_path.name}: exit={rc}  耗时 {(time.time()-t0)/60:.2f} min ---\n")
    return rc


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--lam", default="0p050")
    ap.add_argument("--heap", default="12g")
    ap.add_argument("--max-iter", type=int, default=20,
                    help="全量运行的总迭代数（默认 20）")
    ap.add_argument("--skip-nesting-check", action="store_true",
                    help="跳过 5 迭代嵌套性验证运行")
    ap.add_argument("--smoke", type=int, default=0,
                    help="先跑 n agents × 3 迭代冒烟（验证 ReRoute 真实生效）")
    ap.add_argument("--gen-only", action="store_true")
    args = ap.parse_args()

    OUT_ROOT.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    print("=== MATSim 运行时 ===")
    for k, v in matsim_env.describe().items():
        print(f"  {k}: {v}")
    print(f"  lambda        : {args.lam}（冻结，实验基准 λ）")
    print(f"  capacity      : 1.0（7.2.2 判定 capacity 非结构杠杆后固定不动）")
    print(f"  population    : {POP_DIR}")
    print(f"  checkpoints   : 1/5/10/{args.max_iter} 迭代 = it.0/4/9/{args.max_iter-1}（嵌套设计）")
    print(f"  output root   : {OUT_ROOT}")
    print()

    # --- 冒烟：2000 agents × 3 迭代，验证 ReRoute 逐轮生效 + 每迭代 linkstats ---
    if args.smoke:
        pop_src = POP_DIR / f"population_lambda_{args.lam}.xml.gz"
        pop_dst = CONFIG_DIR / "_smoke_cf_population.xml.gz"
        got = truncate_population(pop_src, pop_dst, args.smoke)
        print(f"[smoke] 截断人口 {got} persons -> {pop_dst}")
        cfg_path, _ = gen_iter_config(3, args.lam)
        tree = ET.parse(cfg_path)
        root = tree.getroot()
        setp(module_of(root, "plans"), "inputPlansFile", str(pop_dst.resolve()))
        setp(module_of(root, "controller"), "outputDirectory",
             str((OUT_ROOT / "_smoke_cf").resolve()))
        setp(module_of(root, "controller"), "runId", "smoke_cf_it3")
        body = ET.tostring(root, encoding="unicode")
        smoke_cfg = CONFIG_DIR / "_smoke_cf_config.xml"
        smoke_cfg.write_text(DOCTYPE + body + "\n", encoding="utf-8")
        verify_patch(smoke_cfg)
        rc = run_matsim(smoke_cfg, "smoke_cf_it3.log", args.heap)
        it_dir = OUT_ROOT / "_smoke_cf" / "ITERS"
        stats = sorted(it_dir.glob("it.*/smoke_cf_it3.*.linkstats.txt.gz")) if it_dir.exists() else []
        print(f"[smoke] 每迭代 linkstats 共 {len(stats)} 份（期望 3）")
        return rc

    # --- 全量：主运行（max_iter）+ 嵌套验证（5 迭代） ---------------------
    rc_all = 0
    cfg_main, out_main = gen_iter_config(args.max_iter, args.lam)
    verify_patch(cfg_main)
    if not args.gen_only:
        rc_all |= run_matsim(cfg_main, f"cf_it{args.max_iter}.log", args.heap)

    if not args.skip_nesting_check:
        cfg_nest, out_nest = gen_iter_config(5, args.lam)
        verify_patch(cfg_nest)
        if not args.gen_only:
            rc_all |= run_matsim(cfg_nest, "cf_it5.log", args.heap)

    print("STATUS:", "PASS" if rc_all == 0 else "FAIL")
    return rc_all


if __name__ == "__main__":
    sys.exit(main())
