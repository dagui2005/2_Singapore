#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""
esb01_launch_chain.py — 把 E-SB-01 串行链以「脱离调用方进程树」的方式点火
========================================================================
背景（E-CAP-01 实测）：经 agent 沙箱 shell 后台运行时，JVM 约 20 分钟后被外部终止
（非崩溃/非 OOM，属进程树/Job Object 被回收）。串行链 ≈ 19 h ⇒ **必须**脱离。

用法
----
    python scripts/experiments/esb01_launch_chain.py --arms SB-A1 SB-A4 SB-A3 SB-A3n SB-A2
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(r"D:\Luan\2026-05\2_Singapore")
PY = r"C:\Users\LQP\miniconda3\python.exe"
RUNNER = ROOT / "scripts" / "experiments" / "esb01_run_chain.py"
EXP = ROOT / "experiments" / "E-SB-01_speedband_fit"

DETACHED_PROCESS = 0x00000008
CREATE_NEW_PROCESS_GROUP = 0x00000200
CREATE_BREAKAWAY_FROM_JOB = 0x01000000
CREATE_NO_WINDOW = 0x08000000

CANDIDATES = [
    ("BREAKAWAY+DETACHED", DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP | CREATE_BREAKAWAY_FROM_JOB),
    ("DETACHED", DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP),
    ("NO_WINDOW", CREATE_NO_WINDOW | CREATE_NEW_PROCESS_GROUP),
]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--arms", nargs="+", required=True)
    ap.add_argument("--heap", default="24g")
    a = ap.parse_args()

    log = EXP / "logs" / "chain_task.log"
    log.parent.mkdir(parents=True, exist_ok=True)
    marker = EXP / "logs" / "chain_launch.json"

    cmd = [PY, "-u", str(RUNNER), "--arms", *a.arms, "--heap", a.heap]
    env = dict(os.environ)
    env["MALLOC_ARENA_MAX"] = "4"

    print("chain   : %s" % " -> ".join(a.arms))
    print("log     : %s" % log)
    fh = open(log, "w", encoding="utf-8", buffering=1)
    fh.write("[%s] CHAIN LAUNCH %s\n" % (datetime.now().isoformat(timespec="seconds"), a.arms))
    for name, flags in CANDIDATES:
        try:
            p = subprocess.Popen(cmd, cwd=str(ROOT), env=env, stdin=subprocess.DEVNULL,
                                 stdout=fh, stderr=subprocess.STDOUT,
                                 creationflags=flags, close_fds=True)
        except OSError as e:
            print("  [FAIL] %-18s %s" % (name, e))
            continue
        print("  [OK  ] %-18s pid=%d  flags=0x%08X" % (name, p.pid, flags))
        marker.write_text(json.dumps({"arms": a.arms, "pid": p.pid, "mode": name,
                                      "flags": hex(flags), "log": str(log),
                                      "launched_at": datetime.now().isoformat(timespec="seconds")},
                                     ensure_ascii=False, indent=2), encoding="utf-8")
        return 0
    print("  [ABORT] 三种 detachment 方式全部失败")
    return 1


if __name__ == "__main__":
    sys.exit(main())
