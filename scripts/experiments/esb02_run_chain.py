#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""
esb02_run_chain.py — E-SB-02 串行链（断点续跑）
==============================================
    python scripts/experiments/esb02_run_chain.py --arms SB-A5 SB-A5ind --heap 24g

- 逐臂调用 esb02_run_arm.py（每臂先跑运行前硬门；失败即中止该臂并继续记录）。
- **断点续跑**：若某臂已有 it.19 linkstats，自动跳过。
- 状态：experiments/E-SB-02_night_freeflow/logs/chain_state.json
"""
from __future__ import annotations
import argparse, json, subprocess, sys, time
from datetime import datetime
from pathlib import Path

ROOT = Path(r"D:\Luan\2026-05\2_Singapore")
EXP = ROOT / "experiments" / "E-SB-02_night_freeflow"
LOGS = EXP / "logs"
OUTS = EXP / "outputs"
RUNNER = ROOT / "scripts" / "experiments" / "esb02_run_arm.py"
PY = sys.executable


def done(arm: str) -> bool:
    it = OUTS / arm / "ITERS" / "it.19"
    return it.exists() and any(it.glob("*.linkstats.txt.gz"))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--arms", nargs="+", default=["SB-A5", "SB-A5ind"])
    ap.add_argument("--heap", default="24g")
    a = ap.parse_args()
    LOGS.mkdir(parents=True, exist_ok=True)
    state_p = LOGS / "chain_state.json"
    state = {"started_at": datetime.now().isoformat(timespec="seconds"),
             "arms": a.arms, "results": []}

    def flush():
        state_p.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")

    flush()
    for i, arm in enumerate(a.arms, 1):
        if done(arm):
            print(f"\n[{i}/{len(a.arms)}] {arm}: 已有 it.19 linkstats ⇒ 跳过（续跑）", flush=True)
            state["results"].append({"arm": arm, "status": "skipped_already_done"})
            flush()
            continue
        t0 = time.time()
        print(f"\n{'='*88}\n[{i}/{len(a.arms)}] {arm}  start {datetime.now():%H:%M:%S}\n{'='*88}", flush=True)
        rc = subprocess.call([PY, "-u", str(RUNNER), "--arm", arm, "--run", "--heap", a.heap])
        state["results"].append({"arm": arm, "rc": rc, "minutes": round((time.time()-t0)/60, 1)})
        flush()
        print(f"[{i}/{len(a.arms)}] {arm}  rc={rc}  {(time.time()-t0)/60:.1f} min", flush=True)

    print("\n" + "=" * 88)
    print("链完成：", json.dumps(state["results"], ensure_ascii=False))
    print("评分：python scripts/experiments/esb02_objective.py")
    print("=" * 88)
    return 0


if __name__ == "__main__":
    sys.exit(main())
