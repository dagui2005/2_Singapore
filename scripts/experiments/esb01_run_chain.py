#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""
esb01_run_chain.py — E-SB-01 串行链：逐臂 运行前硬门 → MATSim → 联合目标评分
==========================================================================
用户裁定 2026-10-07：**按序串行全跑** A1 → A4 → A3 → A3n → A2。
单臂全量 20 迭代 ≈ 3.7 h；本器**必须**经 `esb01_launch_chain.py` 脱离进程点火。

行为
----
- 每臂：`esb01_run_arm.preflight` → MATSim → `esb01_objective` 追加评分卡。
- 某臂失败**不中断**链（记录 rc 继续下一臂），最终汇总 chain_state.json。
- ⛔ 不改任何冻结件；产物只在 experiments/E-SB-01_speedband_fit/。

用法
----
    python scripts/experiments/esb01_run_chain.py --arms SB-A1 SB-A4 SB-A3 SB-A3n SB-A2 --heap 24g
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(r"D:\Luan\2026-05\2_Singapore")
PY = r"C:\Users\LQP\miniconda3\python.exe"
EXP = ROOT / "experiments" / "E-SB-01_speedband_fit"
LOGS = EXP / "logs"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--arms", nargs="+", required=True)
    ap.add_argument("--heap", default="24g")
    ap.add_argument("--skip-objective", action="store_true")
    a = ap.parse_args()

    LOGS.mkdir(parents=True, exist_ok=True)
    state_path = LOGS / "chain_state.json"
    state = {"started_at": datetime.now().isoformat(timespec="seconds"),
             "arms": a.arms, "results": []}
    if state_path.exists():
        try:
            state = json.loads(state_path.read_text(encoding="utf-8"))
            state.setdefault("results", [])
        except Exception:
            pass

    def done(arm: str) -> bool:
        """断点续跑：该臂 it.19 linkstats 已存在则跳过。"""
        p = EXP / "outputs" / arm / "ITERS" / "it.19" / f"{arm}.19.linkstats.txt.gz"
        return p.exists()

    def flush():
        state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")

    flush()
    for i, arm in enumerate(a.arms, 1):
        if done(arm):
            print(f"\n[{i}/{len(a.arms)}] {arm} 已存在 it.19 linkstats ⇒ 跳过（断点续跑）", flush=True)
            continue
        print(f"\n{'='*88}\n[{i}/{len(a.arms)}] {arm}  start {datetime.now():%H:%M:%S}\n{'='*88}", flush=True)
        rec = {"arm": arm, "started_at": datetime.now().isoformat(timespec="seconds")}

        # 1) 运行前硬门 + 点火（前台阻塞在 workdir：run_arm 内部先 preflight 再跑）
        t0 = time.time()
        run_log = LOGS / f"{arm}_run.log"
        with open(run_log, "a", encoding="utf-8") as fh:
            fh.write("\n[chain] %s run start\n" % datetime.now().isoformat(timespec="seconds"))
        p = subprocess.run([PY, "-u", str(ROOT / "scripts" / "experiments" / "esb01_run_arm.py"),
                            "--arm", arm, "--run", "--heap", a.heap],
                           cwd=str(ROOT))
        rec["run_rc"] = p.returncode
        rec["run_min"] = round((time.time() - t0) / 60, 1)

        # 2) 评分
        if not a.skip_objective:
            t1 = time.time()
            q = subprocess.run([PY, "-u", str(ROOT / "scripts" / "experiments" / "esb01_objective.py"),
                                "--runs", arm], cwd=str(ROOT))
            rec["objective_rc"] = q.returncode
            rec["objective_min"] = round((time.time() - t1) / 60, 1)

        rec["finished_at"] = datetime.now().isoformat(timespec="seconds")
        state["results"].append(rec)
        state["last_update"] = rec["finished_at"]
        flush()
        print(f"[{arm}] done rc={rec['run_rc']} in {rec['run_min']} min", flush=True)

    state["finished_at"] = datetime.now().isoformat(timespec="seconds")
    flush()
    print("\nCHAIN FINISHED", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
