#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""
run_lambda_sensitivity_7_6g.py — Step 7.6G **点火器**（本项目唯一会启动 7.6G MATSim 的脚本）。

设计：**单点重绑定，不复制逻辑**
--------------------------------
7.6F-1 的点火器 `run_demand_response_7_6f_1.py` 已经把「前置核验 / sha256 钉扎 /
断点续跑 / iters 计数」写成了与 run 表无关的函数（全部经模块全局 `prep.` 访问）。
本脚本只做一件事：把 `R.prep` 重绑到 7.6G 的 prepare 模块，然后复用同一套函数。
⇒ **零公式/零逻辑复制**，7.6F-1 的点火器保持原封不动。

纪律
----
1. **只运行已通过校验的那份 config**：运行前 sha256 钉扎，运行后断言**逐字节未变**。
2. 运行前逐档 **复跑 `prepare_lambda_sensitivity_7_6g.validate()`**
   （复用 7.6F-1 的 W1–W6 + 本步骤 L1–L5）。
3. ★ **SCALE = 2.29897 全档统一**；**不得**按各档 `ΣEF / N_sim` 重算。
4. **唯一被扫的量 = λ**；demand level 固定 f = 1.18（N_sim = 236,000）。
5. 单机**串行**：本机 RAM 63.7 GB（可用 ≈38 GB），24g/run ⇒ 三档并行必 OOM。
6. **断点续跑**：`outputs/<run_id>/ITERS/it.19/<run_id>.*.linkstats.txt.gz` 存在 → 跳过。
7. 不改 7.1 / 7.3.6A / OD / network / capacity / 200k 源人口 / route-choice 任何冻结件。

用法
----
    python scripts/od/run_lambda_sensitivity_7_6g.py --status          # 只看状态
    python scripts/od/run_lambda_sensitivity_7_6g.py --dry-run         # 只做前置核验
    python scripts/od/run_lambda_sensitivity_7_6g.py --experiments L05 # 点火单档
    python scripts/od/run_lambda_sensitivity_7_6g.py                   # 三档串行（约 4.3 h）
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(r"D:\Luan\2026-05\2_Singapore")
sys.path.insert(0, str(ROOT / "scripts" / "od"))
sys.path.insert(0, str(ROOT / "scripts" / "matsim"))

import matsim_env                                       # noqa: E402
import run_demand_response_7_6f_1 as R                  # noqa: E402  ★ 复用其核验/点火函数
import prepare_lambda_sensitivity_7_6g as P             # noqa: E402  ★ 7.6G 单一事实源

# ★★ 单点重绑定：此后 R.preflight / R.iters_present / R.status_table 全部按 7.6G 运行
R.prep = P
SCALE_FROZEN = P.SCALE_CONST          # 2.29897，全档统一
MANIFEST = P.NEW_ROOT / "lambda_sensitivity_7_6g_run_manifest.json"


def status_table() -> None:
    print("--- 当前 3 档状态（λ 为唯一被扫变量）---")
    for eid, lam, n in P.SPEC:
        out_dir = P.out_dir_of(eid)
        rid = P.run_id_of(eid)
        its = R.iters_present(out_dir, rid)
        dl = P.final_linkstats(out_dir, rid)
        print(f"  {eid}  λ={lam:.3f}  N={n:,}  iters={len(its)}/20"
              f"  it.19={'OK' if dl else '--'}  {out_dir}")
    print()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--experiments", nargs="*", default=[e for e, _l, _n in P.SPEC])
    ap.add_argument("--heap", default="24g",
                    help="★ 100k+ 必须 24g（12g 在 it.2/it.5 PlanRouter 被硬杀）")
    ap.add_argument("--dry-run", action="store_true", help="只做前置核验，不点火")
    ap.add_argument("--status", action="store_true", help="只打印状态")
    ap.add_argument("--force", action="store_true", help="忽略 it.19 存在，强制重跑")
    args = ap.parse_args()

    status_table()
    if args.status:
        return 0

    spec_map = {e: (l, n) for e, l, n in P.SPEC}
    unknown = [e for e in args.experiments if e not in spec_map]
    if unknown:
        print(f"ERROR: 未知实验 {unknown}")
        return 1
    order = [e for e, _l, _n in P.SPEC if e in set(args.experiments)]

    print("=" * 84)
    print("Step 7.6G RUN — λ 敏感度 screening（三档 λ × 单一 demand level f=1.18）")
    print("=" * 84)
    for k, v in matsim_env.describe().items():
        print(f"  {k}: {v}")
    print(f"  heap        : {args.heap}   （串行：本机 63.7 GB RAM，不可并行）")
    print(f"  SCALE       : {SCALE_FROZEN:.5f} ★全档统一，不按 ΣEF 重算")
    print(f"  demand level: f = {P.F_LAMBDA}  -> N_sim = {P.N_SIM:,}")
    print(f"  f_cap       : {P.F_CAP:.2f}   λ∈{P.LAMS}（唯一被扫变量）  20 it")
    print(f"  crosswalk   : 7.3.6A Frozen（只读）")
    print(f"  experiments : {order}")
    print()

    # ---- 前置核验（复用 7.6F-1 的 preflight；f 位置传 F_LAMBDA） --------------
    print("[pre-flight] 逐档核验（config sha256 钉扎 + 与 R01 diff 白名单 + λ 门）")
    pre: dict[str, dict] = {}
    for eid in order:
        _lam, n = spec_map[eid]
        rec = R.preflight(eid, P.F_LAMBDA, n, heap=args.heap)
        rec["lambda"] = P.lam_of(eid)
        rec["lambda_tag"] = P.tag_of(eid)
        pre[eid] = rec
        print(f"  [{eid}] PASS  λ={rec['lambda']:.3f}  persons={rec['persons_actual']:,}  "
              f"ΣEF={rec['sum_expansion_factor']:,.1f}  f_realized={rec['f_realized']:.7f}")
        print(f"        SCALE_used={rec['scale_used']:.5f}  "
              f"scale_if_recomputed={rec['scale_if_recomputed_sumEF_over_N']:.6f}  "
              f"delta={rec['scale_recompute_delta_ppm']:+.2f} ppm（**不采用**）")
        print(f"        cfg sha256[:16]={rec['config_sha256_before'][:16]}  "
              f"checks={rec['checks_pass']}/{rec['checks_total']}")

    if args.dry_run:
        print("\n[dry-run] 未点火。")
        return 0

    # ---- 逐档点火（串行） ---------------------------------------------------
    entries: list[dict] = []
    rc_all = 0
    for eid in order:
        run_id = P.run_id_of(eid)
        out_dir = P.out_dir_of(eid)
        cfg = P.cfg_of(eid)

        print("\n" + "-" * 84)
        print(f"[{eid}] λ={pre[eid]['lambda']:.3f}  agents={pre[eid]['n_agents_requested']:,}")
        done = P.final_linkstats(out_dir, run_id)
        if done and not args.force:
            print(f"[{eid}] 已存在 {done.name} -> 跳过（断点续跑）")
            e = dict(pre[eid])
            e.update({"status": "SKIPPED_DONE", "exit_code": None, "wall_minutes": 0.0,
                      "iters_present": len(R.iters_present(out_dir, run_id))})
            entries.append(e)
            continue

        t0 = time.time()
        rc = P.run_matsim(cfg, f"{run_id}_run.log", args.heap)
        wall = (time.time() - t0) / 60.0
        rc_all |= rc

        sha_after = R.sha256_file(cfg)
        dl = P.final_linkstats(out_dir, run_id)
        its = R.iters_present(out_dir, run_id)

        e = dict(pre[eid])
        e.update({
            "status": "PASS" if (rc == 0 and dl) else "FAIL",
            "exit_code": rc, "wall_minutes": round(wall, 3),
            "started_at": datetime.fromtimestamp(t0).isoformat(timespec="seconds"),
            "finished_at": datetime.now().isoformat(timespec="seconds"),
            "iters_present": len(its), "iters": its,
            "it19_linkstats": str(dl) if dl else None,
            "config_sha256_after": sha_after,
            "config_unchanged_after_run": sha_after == pre[eid]["config_sha256_before"],
            "log": str(P.LOG_DIR / f"{run_id}_run.log"),
        })
        entries.append(e)
        print(f"[{eid}] exit={rc}  {wall:.2f} min  iters={len(its)}/20  "
              f"it.19={'OK' if dl else 'MISSING'}  cfg_unchanged={e['config_unchanged_after_run']}")
        if rc != 0 or not dl:
            print(f"[{eid}] 失败 -> 中止后续档（可修复后重跑；已完成的档会被跳过）")
            break

    # ---- manifest（合并历史，append-only 语义） ----------------------------
    hist = []
    if MANIFEST.exists():
        try:
            hist = json.loads(MANIFEST.read_text(encoding="utf-8")).get("runs", [])
        except Exception:
            hist = []
    keep = [r for r in hist if r.get("experiment_id") not in {e["experiment_id"] for e in entries}]
    runs = keep + entries
    payload = {
        "step": "7.6G",
        "title": "Lambda sensitivity screening at fixed demand level (f=1.18)",
        "updated_at": datetime.now().isoformat(timespec="seconds"),
        "swept_variable": "lambda",
        "lambda_grid": P.LAMS,
        "demand_level_f": P.F_LAMBDA,
        "n_sim": P.N_SIM,
        "scale_frozen_for_all_runs": SCALE_FROZEN,
        "scale_rule": "SCALE = 459794/200000 = 2.29897 constant; sum_EF/N MUST NOT be used",
        "lambda_invariance": "sum_EF, od_total, car_od_total identical across lambda (verified)",
        "f_cap": P.F_CAP, "iterations": P.TOTAL_ITER,
        "heap": args.heap, "execution": "sequential (RAM-bound)",
        "route_choice": "R01_rc_min (7.6E frozen)",
        "target": "7.3.6A Frozen crosswalk (576 pooled; MUST NOT be replaced)",
        "primary_metric": "MATCHED Sim/Obs(08-09)", "primary_window": "Qbar_10:19",
        "reference_window": "Q_19",
        "demand_scale_selected": False, "lambda_selected": False,
        "parameters_changed": False, "lambda_swept_by_population": True,
        "matsim_env": matsim_env.describe(),
        "runs": runs,
        "status": ("PASS" if rc_all == 0 and all(
            r["status"] in ("PASS", "SKIPPED_DONE") for r in runs) else "PARTIAL_OR_FAIL"),
    }
    MANIFEST.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str),
                        encoding="utf-8")
    print("\n" + "=" * 84)
    print(f"RUN STATUS: {payload['status']}")
    print(f"manifest -> {MANIFEST}")
    print("下一步：python scripts/od/evaluate_lambda_sensitivity_7_6g.py")
    return rc_all


if __name__ == "__main__":
    raise SystemExit(main())
