#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
run_capacity_sweep_7_2_2.py — Step 7.2.2 Capacity-only Sensitivity（λ=0.05，5 档）。

严格只改一个参数组：capacity factor f ∈ {0.50, 0.75, 1.00, 1.25, 1.50}。
其余全部保持 7.2.1 审计冻结的基线（config_lambda_0p050_6_3_3b.xml 语义）：
    OD / λ / population(6.3.3A departure profile) / departure time /
    network topology(network_cleaned.xml.gz) / permlanes / route choice(SpeedyALT, 单迭代) /
    randomSeed=4711 / threads=8

⚠️ 引擎硬约束（冒烟实测 + GlobalConfigGroup.java 源码确认）：
MATSim 2026.0 的 GlobalConfigGroup.checkConsistency 强制
    |storageCapacityFactor − flowCapacityFactor| 相对容差 = 0
且对应 @StringSetter 被注释掉 → **无法通过 XML 放宽**。
因此 sweep 把 qsim.flowCapacityFactor 与 qsim.storageCapacityFactor **同时设为 f**
（这正是 MATSim 官方 sampled-population 语义：两个 factor 是同一语义单元）。

实现方式：用 make_config_6_3.build_one 生成 6.3.3B 同源 config（保证除本参数外逐字节同源），
再对生成的 config 做最小 patch：
    controller.outputDirectory → reports/od_calibration_7_2_2/capacity_factor_<tag>
    controller.runId           → cap_f_<tag>
    qsim.flowCapacityFactor    → f
config 落盘 matsim/step6_3/config_capf_<tag>_lam0p050.xml，日志 matsim/step6_3/logs/cap_f_<tag>.log。

用法
----
    python scripts/od/run_capacity_sweep_7_2_2.py --smoke 2000        # 先冒烟（f=0.75 验证 patch）
    python scripts/od/run_capacity_sweep_7_2_2.py                     # 全量 5 档（每档 ~18 min）
    python scripts/od/run_capacity_sweep_7_2_2.py --factors 0.50 1.50 # 只跑指定档
    python scripts/od/run_capacity_sweep_7_2_2.py --gen-only          # 只生成 config 不跑
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

CAP_ROOT = ROOT / "reports" / "od_calibration_7_2_2"
CONFIG_DIR = cfgmod.CONFIG_DIR
LOG_DIR = CONFIG_DIR / "logs"
POP_DIR = ROOT / "reports" / "matsim_departure_6_3_3a"   # 6.3.3A 冻结出发时刻剖面
DOCTYPE = (
    '<?xml version="1.0" encoding="UTF-8"?>\n'
    '<!DOCTYPE config SYSTEM "http://www.matsim.org/files/dtd/config_v2.dtd">\n'
)


def factor_tag(f: float) -> str:
    return f"{f:.2f}".replace(".", "p")   # 0.50→0p50, 1.00→1p00


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


def patch_config(cfg_path: Path, *, out_dir: Path, run_id: str,
                 flow_capacity_factor: float, plans_file: Path | None = None) -> None:
    """对 build_one 生成的 config 做最小 patch（唯一实验变量 = capacity factor）。

    ⚠️ flowCapacityFactor 与 storageCapacityFactor 必须同时设为 f：
    MATSim 2026.0 GlobalConfigGroup.checkConsistency 强制两者相对容差=0，
    且该容差的 @StringSetter 已被注释（无法经 XML 放宽）。
    """
    tree = ET.parse(cfg_path)
    root = tree.getroot()
    setp(module_of(root, "controller"), "outputDirectory", str(out_dir))
    setp(module_of(root, "controller"), "runId", run_id)
    setp(module_of(root, "qsim"), "flowCapacityFactor", f"{flow_capacity_factor:g}")
    setp(module_of(root, "qsim"), "storageCapacityFactor", f"{flow_capacity_factor:g}")
    if plans_file is not None:
        setp(module_of(root, "plans"), "inputPlansFile", str(plans_file))
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


def gen_factor_config(f: float, lam: str = "0p050") -> tuple[Path, Path]:
    """生成并 patch 单档 config，返回 (cfg_path, out_dir)。"""
    tag = factor_tag(f)
    out_dir = CAP_ROOT / f"capacity_factor_{tag}"
    cfg_path = CONFIG_DIR / f"config_capf_{tag}_lam{lam}.xml"
    cfgmod.build_one(
        lam,
        pop_dir=POP_DIR,
        out_root=CAP_ROOT,
        run_prefix=f"cap_f_{tag}_",
        cfg_path=cfg_path,
    )
    patch_config(cfg_path, out_dir=out_dir, run_id=f"cap_f_{tag}",
                 flow_capacity_factor=f)
    return cfg_path, out_dir


def verify_patch(cfg_path: Path) -> str:
    """读回 config 确认 patch 生效（防呆：唯一变量必须真实落到盘上）。"""
    root = ET.parse(cfg_path).getroot()
    q = module_of(root, "qsim")
    fcp = next(p.get("value") for p in q.findall("param")
               if p.get("name") == "flowCapacityFactor")
    st = next(p.get("value") for p in q.findall("param")
              if p.get("name") == "storageCapacityFactor")
    c = module_of(root, "controller")
    rid = next(p.get("value") for p in c.findall("param")
               if p.get("name") == "runId")
    plans = next(p.get("value") for p in module_of(root, "plans").findall("param")
                 if p.get("name") == "inputPlansFile")
    print(f"  [verify] {cfg_path.name}: flowCapacityFactor={fcp} "
          f"storageCapacityFactor={st} runId={rid}")
    print(f"           plans={plans}")
    assert float(fcp) > 0
    assert abs(float(st) - float(fcp)) < 1e-12, "MATSim 2026 要求 storage==flow"
    return fcp


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--factors", nargs="*", type=float,
                    default=[0.50, 0.75, 1.00, 1.25, 1.50])
    ap.add_argument("--lam", default="0p050")
    ap.add_argument("--heap", default="12g")
    ap.add_argument("--smoke", type=int, default=0,
                    help="先跑 n agents 冒烟（用 f=0.75 验证 patch 真实生效）")
    ap.add_argument("--gen-only", action="store_true")
    args = ap.parse_args()

    CAP_ROOT.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    print("=== MATSim 运行时 ===")
    for k, v in matsim_env.describe().items():
        print(f"  {k}: {v}")
    print(f"  capacity factors: {args.factors}")
    print(f"  lambda          : {args.lam}（冻结，单 λ 实验）")
    print(f"  population      : {POP_DIR}")
    print(f"  output root     : {CAP_ROOT}")
    print()

    # --- 冒烟：验证 patched config 可跑、fcp 真实生效 -------------------
    if args.smoke:
        f = 0.75
        tag = factor_tag(f)
        pop_src = POP_DIR / f"population_lambda_{args.lam}.xml.gz"
        pop_dst = CONFIG_DIR / "_smoke_capf_population.xml.gz"
        got = truncate_population(pop_src, pop_dst, args.smoke)
        print(f"[smoke] 截断人口 {got} persons -> {pop_dst}")
        cfg_path, _ = gen_factor_config(f, args.lam)
        # 冒烟专用输出目录 + 截断人口
        tree = ET.parse(cfg_path)
        root = tree.getroot()
        setp(module_of(root, "plans"), "inputPlansFile", str(pop_dst.resolve()))
        setp(module_of(root, "controller"), "outputDirectory",
             str((CAP_ROOT / "_smoke_capf").resolve()))
        setp(module_of(root, "controller"), "runId", f"smoke_capf_{tag}")
        body = ET.tostring(root, encoding="unicode")
        smoke_cfg = CONFIG_DIR / "_smoke_capf_config.xml"
        smoke_cfg.write_text(DOCTYPE + body + "\n", encoding="utf-8")
        verify_patch(smoke_cfg)
        log = LOG_DIR / f"smoke_capf_{tag}.log"
        rc = matsim_env.run_java_streaming(
            ["org.matsim.run.RunMatsim", str(smoke_cfg)], log_path=log, heap=args.heap)
        print(f"[smoke] exit={rc}  log={log}")
        return rc

    # --- 全量：逐档 生成 → 验证 → 运行 --------------------------------
    rc_all = 0
    for f in args.factors:
        tag = factor_tag(f)
        cfg_path, out_dir = gen_factor_config(f, args.lam)
        fcp = verify_patch(cfg_path)
        if args.gen_only:
            continue
        log = LOG_DIR / f"cap_f_{tag}.log"
        print(f"=== 运行 cap_f_{tag} (flowCapacityFactor={fcp}) -> {log} ===")
        t0 = time.time()
        rc = matsim_env.run_java_streaming(
            ["org.matsim.run.RunMatsim", str(cfg_path)], log_path=log, heap=args.heap)
        dt = time.time() - t0
        print(f"--- cap_f_{tag}: exit={rc}  耗时 {dt/60:.2f} min ---\n")
        rc_all |= rc

    print("STATUS:", "PASS" if rc_all == 0 else "FAIL")
    return rc_all


if __name__ == "__main__":
    sys.exit(main())
