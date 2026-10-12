#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""
esb05_run.py — E-SB-05 点火（运行前硬门 -> MATSim）
===================================================
用法：
    python scripts/experiments/esb05_run.py            # 只跑运行前硬门
    python scripts/experiments/esb05_run.py --run      # 硬门 + 点火
    python scripts/experiments/esb05_run.py --run --heap 24g

⛔ 不改任何冻结件；产物只落 experiments/E-SB-05_exec_level_events/
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(r"D:\Luan\2026-05\2_Singapore")
EXP = ROOT / "experiments" / "E-SB-05_exec_level_events"
CFG_DIR = EXP / "configs"
LOG_DIR = EXP / "logs"
AUDIT = EXP / "audit"
RUN_ID = "SB-A5_EVT19_CHECK"

sys.path.insert(0, str(ROOT / "scripts" / "experiments"))
sys.path.insert(0, str(ROOT / "scripts" / "matsim"))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", action="store_true", help="通过硬门后点火")
    ap.add_argument("--heap", default="24g")
    ap.add_argument("--skip-preflight", action="store_true")
    args = ap.parse_args()

    if not args.skip_preflight:
        import esb05_preflight as PF  # noqa: E402
        rc = PF.main()
        if rc != 0:
            print("\n[ABORT] 运行前硬门未全通过 ⇒ 不点火。")
            return rc
    else:
        man = json.loads((AUDIT / "run_config_manifest.json").read_text(encoding="utf-8"))
        if man.get("verdict") != "READY":
            print("[ABORT] 已有 manifest 非 READY。")
            return 3
        print("[SKIP] 复用已通过的运行前硬门记录。")

    if not args.run:
        print("\n[OK] 运行前硬门全通过。点火：--run --heap 24g")
        return 0

    LOG_DIR.mkdir(parents=True, exist_ok=True)
    log = LOG_DIR / f"{RUN_ID}_run.log"
    cfg = CFG_DIR / f"config_{RUN_ID}.xml"

    from matsim_env import run_java_streaming, describe  # noqa: E402
    d = describe()
    print("=" * 88)
    print(f"[RUN] 点火 {RUN_ID}（heap {args.heap}）")
    print(f"      config = {cfg}")
    print(f"      java   = {d['java']}")
    print(f"      jar    = {d['matsim_jar']}  (+libs/{d['libs_count']} jars)")
    print(f"      log    = {log}")
    print("=" * 88, flush=True)

    t0 = time.time()
    rc = run_java_streaming(["org.matsim.run.RunMatsim", str(cfg)], log_path=log, heap=args.heap)
    dur = time.time() - t0
    print(f"[RUN] rc={rc}  用时 {dur/60:.1f} min", flush=True)

    stamp = {
        "run_id": RUN_ID,
        "started_finished_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "duration_sec": round(dur, 1),
        "duration_min": round(dur / 60, 1),
        "returncode": rc,
        "heap": args.heap,
        "log": str(log),
    }
    (AUDIT / f"{RUN_ID}_run_stamp.json").write_text(
        json.dumps(stamp, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0 if rc == 0 else 4


if __name__ == "__main__":
    sys.exit(main())
