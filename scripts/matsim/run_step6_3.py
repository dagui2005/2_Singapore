#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
run_step6_3.py — Step 6.3 极小 MATSim runner：Prior OD → QSim AM assignment。

它做三件事，且**只驱动真正的 MATSim**（不写任何 Python 版假模拟）：

1. 用 `make_config_6_3.py` 生成 / 刷新每套 λ 的 `config.xml`
2. 用项目本地 JDK25 + MATSim2026.0 运行 `org.matsim.run.RunMatsim`
3. 把日志写进 `matsim/step6_3/logs/`，运行完打印产物清单

用法
----
    python scripts/matsim/run_step6_3.py                 # 三套 λ，各 20 万 agents
    python scripts/matsim/run_step6_3.py --lambdas 0p050
    python scripts/matsim/run_step6_3.py --smoke 2000    # 2000 agents 冒烟测试
    python scripts/matsim/run_step6_3.py --heap 16g

Step 6.3 的语义
---------------
单次迭代（firstIteration=lastIteration=0）：
    人口(无 route) --ReRoute 权重1.0--> 最短路 route --QSim--> link volume / traveltime
输出 `ITERS/it.0/0.linkstats.txt` 给出每 link 每小时的 volume 与 traveltime，
即 q_a^sim 与 t_a^sim（v_a^sim = length / traveltime）。
"""
from __future__ import annotations

import argparse
import gzip
import shutil
import sys
import time
import xml.etree.ElementTree as ET
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import matsim_env  # noqa: E402
import make_config_6_3 as cfgmod  # noqa: E402

ROOT = cfgmod.PROJECT_ROOT
CONFIG_DIR = cfgmod.CONFIG_DIR
LOG_DIR = CONFIG_DIR / "logs"
DOCTYPE = ('<?xml version="1.0" encoding="UTF-8"?>\n'
           '<!DOCTYPE config SYSTEM "http://www.matsim.org/files/dtd/config_v2.dtd">\n')


def write_config(root: ET.Element, path: Path) -> None:
    body = ET.tostring(root, encoding="unicode")
    path.write_text(DOCTYPE + body + "\n", encoding="utf-8")


def truncate_population(src: Path, dst: Path, n: int) -> int:
    """取前 n 个 <person> 生成一个小人口，用于配置冒烟测试。"""
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


def prepare_smoke(n: int, lam: str, pop_dir: Path, out_root: Path,
                  cfg_src: Path) -> Path:
    pop_src = pop_dir / f"population_lambda_{lam}.xml.gz"
    pop_dst = CONFIG_DIR / "_smoke_population.xml.gz"
    got = truncate_population(pop_src, pop_dst, n)
    print(f"[smoke] 截断人口 {got} persons -> {pop_dst}")

    t = ET.parse(cfg_src)
    root = t.getroot()

    def mod(name):
        return next(m for m in root.findall("module") if m.get("name") == name)

    def setp(m, k, v):
        for p in m.findall("param"):
            if p.get("name") == k:
                p.set("value", v)
                return
        ET.SubElement(m, "param", {"name": k, "value": v})

    setp(mod("plans"), "inputPlansFile", str(pop_dst.resolve()))
    setp(mod("controller"), "outputDirectory",
         str((out_root / "_smoke").resolve()))
    setp(mod("controller"), "runId", "smoke")
    cfg = CONFIG_DIR / "_smoke_config.xml"
    write_config(root, cfg)
    return cfg


def list_outputs(out_dir: Path) -> None:
    if not out_dir.exists():
        print(f"  (输出目录不存在: {out_dir})")
        return
    for p in sorted(out_dir.rglob("*")):
        if p.is_file():
            rel = p.relative_to(out_dir)
            print(f"  {rel}  ({p.stat().st_size/1e6:.2f} MB)")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--lambdas", nargs="*", default=cfgmod.LAMBDAS)
    ap.add_argument("--smoke", type=int, default=0,
                    help="跑 n 个 agents 的冒烟测试（不产出正式结果）")
    ap.add_argument("--heap", default="12g")
    ap.add_argument("--skip-config", action="store_true",
                    help="不重新生成 config")
    # --- 以下允许切换 population / 输出目录，用于 Step 6.3.3B 等复用 ---
    ap.add_argument("--pop-dir", default=None,
                    help="population 目录（默认 6.2B_connected）；6.3.3B 用 "
                         "reports/matsim_departure_6_3_3a")
    ap.add_argument("--out-root", default=str(ROOT / "reports" / "matsim_assignment"),
                    help="MATSim 输出根目录（默认 reports/matsim_assignment）")
    ap.add_argument("--run-prefix", default="step6_3_lambda_",
                    help="runId 前缀（6.3.3B 用 step6_3_3b_lambda_）")
    ap.add_argument("--cfg-suffix", default="",
                    help="config 文件名后缀（6.3.3B 用 _6_3_3b，避免覆盖 6.3 config）")
    args = ap.parse_args()

    pop_dir = Path(args.pop_dir) if args.pop_dir else cfgmod.POP_DIR
    out_root = Path(args.out_root)

    def cfg_path_for(lam: str) -> Path:
        return cfgmod.CONFIG_DIR / f"config_lambda_{lam}{args.cfg_suffix}.xml"

    print("=== MATSim 运行时 ===")
    for k, v in matsim_env.describe().items():
        print(f"  {k}: {v}")
    print(f"  population_dir: {pop_dir}")
    print(f"  output_root   : {out_root}")
    print(f"  run_id_prefix : {args.run_prefix}")
    print()

    if not args.skip_config:
        print("=== 生成 config ===")
        for lam in cfgmod.LAMBDAS:
            print("  ", cfgmod.build_one(
                lam, pop_dir=pop_dir, out_root=out_root,
                run_prefix=args.run_prefix, cfg_path=cfg_path_for(lam)))
        print()

    targets: list[tuple[str, Path]] = []
    if args.smoke:
        lam = args.lambdas[0]
        targets.append(("smoke", prepare_smoke(
            args.smoke, lam, pop_dir, out_root, cfg_path_for(lam))))
    else:
        for lam in args.lambdas:
            targets.append((lam, cfg_path_for(lam)))

    LOG_DIR.mkdir(parents=True, exist_ok=True)
    rc_all = 0
    for name, cfg in targets:
        log = LOG_DIR / f"{name}.log"
        print(f"=== 运行 {name} -> {log} ===")
        t0 = time.time()
        rc = matsim_env.run_java_streaming(
            ["org.matsim.run.RunMatsim", str(cfg)], log_path=log, heap=args.heap)
        dt = time.time() - t0
        print(f"--- {name}: exit={rc}  耗时 {dt/60:.2f} min ---\n")
        rc_all |= rc

        out_dir = out_root / ("_smoke" if name == "smoke" else f"lambda_{name}")
        print(f"=== {name} 产物 ===")
        list_outputs(out_dir)
        print()

    print("STATUS:", "PASS" if rc_all == 0 else "FAIL")
    return rc_all


if __name__ == "__main__":
    sys.exit(main())
