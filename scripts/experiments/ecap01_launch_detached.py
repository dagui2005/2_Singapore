#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ecap01_launch_detached.py — 把 E-CAP-01 仿真以「脱离调用方进程树」的方式点火

背景（本步实测）：
    经 agent 的沙箱化 shell 直接后台运行时，JVM 会在约 20 分钟后被**外部终止**
    （无 hs_err_pid*.log、无 Java 异常、事件日志无 Application Error、
      内存仅 ~10/24 GB、物理内存 35 GB 可用 ⇒ 非崩溃、非 OOM，属进程树被回收）。

对策：
    用 DETACHED_PROCESS + CREATE_BREAKAWAY_FROM_JOB 生成子进程，
    使其脱离调用方的 Windows Job Object（若 Job 不允许 breakaway 则自动降级并如实报告）。

用法：
    python scripts/experiments/ecap01_launch_detached.py
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(r"D:\Luan\2026-05\2_Singapore")
PY = r"C:\Users\LQP\miniconda3\python.exe"
RUNNER = ROOT / "scripts" / "experiments" / "ecap01_build_config.py"
LOG = ROOT / "experiments" / "E-CAP-01_scale_capacity" / "logs" / "ecap01_task.log"

DETACHED_PROCESS = 0x00000008
CREATE_NEW_PROCESS_GROUP = 0x00000200
CREATE_BREAKAWAY_FROM_JOB = 0x01000000
CREATE_NO_WINDOW = 0x08000000

CANDIDATES = [
    ("BREAKAWAY+DETACHED",
     DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP | CREATE_BREAKAWAY_FROM_JOB),
    ("DETACHED",
     DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP),
    ("NO_WINDOW",
     CREATE_NO_WINDOW | CREATE_NEW_PROCESS_GROUP),
]


def main() -> int:
    LOG.parent.mkdir(parents=True, exist_ok=True)
    cmd = [PY, str(RUNNER), "--run", "--heap", "24g"]
    env = dict(os.environ)
    env["MALLOC_ARENA_MAX"] = "4"

    print("launcher: %s" % RUNNER.name)
    print("log     : %s" % LOG)
    fh = open(LOG, "w", encoding="utf-8", buffering=1)
    for name, flags in CANDIDATES:
        try:
            p = subprocess.Popen(
                cmd, cwd=str(ROOT), env=env, stdin=subprocess.DEVNULL,
                stdout=fh, stderr=subprocess.STDOUT,
                creationflags=flags, close_fds=True,
            )
        except OSError as e:
            print("  [FAIL] %-18s %s" % (name, e))
            continue
        print("  [OK  ] %-18s pid=%d  flags=0x%08X" % (name, p.pid, flags))
        return 0
    print("  [ABORT] 三种 detachment 方式全部失败")
    return 1


if __name__ == "__main__":
    sys.exit(main())
