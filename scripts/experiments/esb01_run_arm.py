#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""
esb01_run_arm.py — E-SB-01 单臂点火（运行前硬门 + MATSim）
==========================================================
用法
----
    python scripts/experiments/esb01_run_arm.py --arm SB-A1                 # 只跑运行前硬门
    python scripts/experiments/esb01_run_arm.py --arm SB-A1 --run --heap 24g # 点火

⛔ 不改任何冻结件；输出只落 experiments/E-SB-01_speedband_fit/outputs/<ARM>/
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from pathlib import Path

ROOT = Path(r"D:\Luan\2026-05\2_Singapore")
sys.path.insert(0, str(ROOT / "scripts" / "experiments"))
sys.path.insert(0, str(ROOT / "scripts" / "matsim"))

import esb01_build_arms as B  # noqa: E402

CHECKS: list[dict] = []


def gate(cid, name, ok, detail=""):
    CHECKS.append({"check": cid, "name": name, "pass": bool(ok), "detail": str(detail)})
    print("  [%s] %-10s %s%s" % ("PASS" if ok else "FAIL", cid, name,
                                ("  (%s)" % detail) if detail else ""), flush=True)
    return bool(ok)


def preflight(arm: str) -> bool:
    cfg = B.CONFIG_DIR / f"config_{arm}.xml"
    if not gate("R-00", f"{arm} 配置存在", cfg.exists(), str(cfg.name)):
        return False
    gate("R-01", "源配置 sha16 == 冻结", B.sha16(B.SRC_CONFIG) == B.EXPECT_SRC_CONFIG_SHA16)
    gate("R-02", "源网络 sha16 == 冻结", B.sha16(B.SRC_NETWORK) == B.EXPECT_NETWORK_SHA16)
    gate("R-03", "plans sha16 == 冻结", B.sha16(B.SRC_PLANS) == B.EXPECT_PLANS_SHA16)

    a, b = B.all_params(B.SRC_CONFIG), B.all_params(cfg)
    diff = [k for k in sorted(set(a) | set(b)) if a.get(k) != b.get(k)]
    wl_keys = set(B.config_whitelist(arm, B.OUT_ROOT / arm,
                                     None if arm in ("SB-A1", "SB-A2") else B.NET_DIR / f"network_{arm}.xml.gz"))
    non_wl = [k for k in diff if k.split(".")[-1] not in wl_keys]
    gate("R-04", f"{arm} 配置 diff == 白名单", len(diff) == len(wl_keys) and not non_wl,
         "diff=%d wl=%d 非白名单=%s" % (len(diff), len(wl_keys), non_wl[:3]))

    od = b.get("controller.outputDirectory", "")
    inside = str(B.EXP_ROOT).lower() in str(od).lower()
    not_v10 = str(ROOT / "matsim_final_7_6h").lower() not in str(od).lower()
    gate("R-05", "输出目录为实验专属且不在 v1.0 内", inside and not_v10, od)

    if arm in ("SB-A3", "SB-A3n", "SB-A4"):
        net = Path(b.get("network.inputNetworkFile", ""))
        gate("R-06", f"{arm} 网络存在且为实验专属", net.exists() and str(B.NET_DIR) in str(net), net.name)
    gate("R-07", "linkStats.writeLinkStatsInterval == 1",
         b.get("linkStats.writeLinkStatsInterval") == "1")
    gate("R-08", "randomSeed == 4711 且迭代 == 19",
         b.get("global.randomSeed") == "4711" and b.get("controller.lastIteration") == "19",
         "seed=%s it=%s" % (b.get("global.randomSeed"), b.get("controller.lastIteration")))
    return all(c["pass"] for c in CHECKS)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--arm", required=True, choices=["SB-A1", "SB-A2", "SB-A3", "SB-A3n", "SB-A4"])
    ap.add_argument("--run", action="store_true")
    ap.add_argument("--heap", default="24g")
    args = ap.parse_args()

    B.AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    (B.OUT_ROOT / args.arm).mkdir(parents=True, exist_ok=True)
    B.LOG_DIR.mkdir(parents=True, exist_ok=True)

    print("=" * 84)
    print("E-SB-01 单臂点火：%s  (EXPERIMENT ONLY / NOT v1.1)" % args.arm)
    print("=" * 84)
    ok = preflight(args.arm)

    with open(B.AUDIT_DIR / f"{args.arm}_run_gates.csv", "w", newline="", encoding="utf-8-sig") as fh:
        w = csv.DictWriter(fh, fieldnames=["check", "name", "pass", "detail"])
        w.writeheader()
        w.writerows(CHECKS)
    if not ok:
        print("\n[ABORT] 运行前硬门失败 ⇒ %s = INVALID，不点火。" % args.arm)
        return 3

    if not args.run:
        print("\n[OK] 运行前硬门全通过。点火：--run --heap 24g")
        return 0

    from matsim_env import run_java_streaming  # noqa: E402
    log = B.LOG_DIR / f"{args.arm}_run.log"
    print("\n[RUN] 点火 %s（heap %s）→ %s" % (args.arm, args.heap, log))
    t0 = time.time()
    rc = run_java_streaming(["org.matsim.run.RunMatsim", str(B.CONFIG_DIR / f"config_{args.arm}.xml")],
                            log_path=log, heap=args.heap)
    print("[RUN] rc=%s 用时 %.1f min" % (rc, (time.time() - t0) / 60))
    return 0 if rc == 0 else 4


if __name__ == "__main__":
    sys.exit(main())
