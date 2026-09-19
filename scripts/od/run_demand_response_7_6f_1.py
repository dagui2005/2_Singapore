#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""
run_demand_response_7_6f_1.py — Step 7.6F-1 **点火器**（本项目唯一会启动 MATSim 的 7.6F-1 脚本）。

纪律（用户 2026-09-17 20:17 裁定）
----------------------------------
1. **只运行已通过 67/67 校验的那份 config**：运行前对 config 做 sha256 钉扎，
   运行后再哈希一次断言**逐字节未变**（被执行的 = 被验证的）。
2. 运行前对每个 run **重跑 `prepare_demand_response_7_6f_1.validate()`**
   （与 R01 逐参数 diff 白名单 + 7.6E route-choice 4 项继承 + f_cap/seed/lastIter/λ）。
3. ★**SCALE 冻结 = 2.29897，全档统一**；**不得**按各档 `ΣEF / N_sim` 重算
   （否则把「加真实车辆数」与「改扩展权重」混成两个 demand 操作）。
4. 单机**串行**执行：本机 RAM 63.7 GB（可用 ≈38 GB），24g/run ⇒ 三档并行必 OOM。
5. **断点续跑**：`outputs/<run_id>/ITERS/it.19/<run_id>.*.linkstats.txt.gz` 存在 → 跳过。
6. 不改 7.1 / 7.3.6A / OD / network / capacity / population / route-choice 任何冻结件。

用法
----
    python scripts/od/run_demand_response_7_6f_1.py --status          # 只看状态
    python scripts/od/run_demand_response_7_6f_1.py --dry-run         # 只做前置核验
    python scripts/od/run_demand_response_7_6f_1.py --experiments F05 # 点火单档
    python scripts/od/run_demand_response_7_6f_1.py                   # 三档串行（约 4.7 h）
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(r"D:\Luan\2026-05\2_Singapore")
sys.path.insert(0, str(ROOT / "scripts" / "od"))
sys.path.insert(0, str(ROOT / "scripts" / "matsim"))

import matsim_env                              # noqa: E402
import prepare_demand_response_7_6f_1 as prep  # noqa: E402  ★ 单一事实源（配置/校验/人口）
import run_demand_scale_7_4_3 as ds743         # noqa: E402  人口统计工具

MANIFEST = prep.NEW_ROOT / "demand_response_7_6f_1_run_manifest.json"
SCALE_FROZEN = 2.29897          # ★ 全档统一，禁止按 ΣEF 重算


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def iters_present(out_dir: Path, run_id: str) -> list[int]:
    """返回已落盘的迭代号（依据 linkstats 文件）。"""
    got = []
    d = out_dir / "ITERS"
    if not d.exists():
        return got
    for sub in sorted(d.glob("it.*")):
        try:
            i = int(sub.name.split(".")[1])
        except (IndexError, ValueError):
            continue
        if list(sub.glob(f"{run_id}.*.linkstats.txt.gz")) or list(sub.glob("*.linkstats.txt.gz")):
            got.append(i)
    return got


def preflight(eid: str, f: float, n: int, *, heap: str) -> dict:
    """运行前核验：config / 人口 / diff 白名单 / 冻结口径。返回该 run 的前置记录。"""
    cfg = prep.cfg_of(eid)
    pop = prep.pop_file_of(eid)
    out_dir = prep.out_dir_of(eid)
    run_id = prep.run_id_of(eid)

    if not cfg.exists():
        raise FileNotFoundError(f"[{eid}] config 缺失: {cfg}")
    if not pop.exists():
        raise FileNotFoundError(f"[{eid}] 人口缺失: {pop}")

    st = ds743.population_stats(pop)
    if st["persons"] != n:
        raise ValueError(f"[{eid}] persons={st['persons']:,} != 期望 {n:,}")
    s_ef = st["sum_expansion_factor"]
    f_realized = s_ef / prep.REAL_CAR_OD_TOTAL
    scale_if_recomputed = s_ef / n
    if abs(f_realized - f) > 0.01:
        raise ValueError(f"[{eid}] f_realized={f_realized:.6f} 偏离标称 {f:.2f} 超过 0.01")

    # ★ 复跑 prepare 的严格校验（与 R01 逐参数 diff + 7.6E route-choice 继承）
    prep._ck_rows.clear()
    checks = prep.validate(cfg, eid, n, smoke=0)
    fails = [c for c in checks if not c["pass"]]
    if fails:
        raise AssertionError(f"[{eid}] 配置校验失败 {len(fails)} 项: "
                             f"{[c['check'] for c in fails][:5]}")

    return {
        "experiment_id": eid, "run_id": run_id, "f_demand": f,
        "n_agents_requested": n, "persons_actual": st["persons"],
        "sum_expansion_factor": s_ef, "f_realized": f_realized,
        "scale_used": SCALE_FROZEN,
        "scale_if_recomputed_sumEF_over_N": scale_if_recomputed,
        "scale_recompute_delta_ppm": (scale_if_recomputed - SCALE_FROZEN) / SCALE_FROZEN * 1e6,
        "scale_rule": "FROZEN 2.29897 for ALL runs; NOT recomputed from sum_EF",
        "config": str(cfg), "config_sha256_before": sha256_file(cfg),
        "population": str(pop), "population_sha256_content": prep.sha256_of_xml(pop),
        "output_dir": str(out_dir), "heap": heap,
        "checks_total": len(checks), "checks_pass": len(checks) - len(fails),
    }


def status_table() -> None:
    print("--- 当前 3 档状态 ---")
    for eid, f, n in prep.SPEC:
        out_dir = prep.out_dir_of(eid)
        rid = prep.run_id_of(eid)
        its = iters_present(out_dir, rid)
        dl = prep.final_linkstats(out_dir, rid)
        print(f"  {eid}  f={f:.2f}  N={n:,}  iters={len(its)}/20"
              f"  it.19={'OK' if dl else '--'}  {out_dir}")
    print()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--experiments", nargs="*", default=[e for e, _f, _n in prep.SPEC])
    ap.add_argument("--heap", default="24g",
                    help="★ 100k+ 必须 24g（12g 在 it.2/it.5 PlanRouter 被硬杀）")
    ap.add_argument("--dry-run", action="store_true", help="只做前置核验，不点火")
    ap.add_argument("--status", action="store_true", help="只打印状态")
    ap.add_argument("--force", action="store_true", help="忽略 it.19 存在，强制重跑")
    args = ap.parse_args()

    status_table()
    if args.status:
        return 0

    spec_map = {e: (f, n) for e, f, n in prep.SPEC}
    unknown = [e for e in args.experiments if e not in spec_map]
    if unknown:
        print(f"ERROR: 未知实验 {unknown}")
        return 1
    order = [e for e, _f, _n in prep.SPEC if e in set(args.experiments)]

    print("=" * 84)
    print("Step 7.6F-1 RUN — 稳定分配底座上的粗档 demand-response（物理加车）")
    print("=" * 84)
    for k, v in matsim_env.describe().items():
        print(f"  {k}: {v}")
    print(f"  heap        : {args.heap}   （串行：本机 63.7 GB RAM，不可并行）")
    print(f"  SCALE       : {SCALE_FROZEN:.5f} ★全档统一，不按 ΣEF 重算")
    print(f"  f_cap       : {prep.F_CAP:.2f}   λ={prep.LAMBDA_FIXED}（仅保持）  20 it")
    print(f"  crosswalk   : 7.3.6A Frozen（只读）")
    print(f"  experiments : {order}")
    print()

    # ---- 前置核验 --------------------------------------------------------
    print("[pre-flight] 逐档核验（config sha256 钉扎 + 与 R01 diff 白名单）")
    pre: dict[str, dict] = {}
    for eid in order:
        f, n = spec_map[eid]
        rec = preflight(eid, f, n, heap=args.heap)
        pre[eid] = rec
        print(f"  [{eid}] PASS  persons={rec['persons_actual']:,}  "
              f"ΣEF={rec['sum_expansion_factor']:,.1f}  f_realized={rec['f_realized']:.6f}")
        print(f"        SCALE_used={rec['scale_used']:.5f}  "
              f"scale_if_recomputed={rec['scale_if_recomputed_sumEF_over_N']:.6f}  "
              f"delta={rec['scale_recompute_delta_ppm']:+.1f} ppm（**不采用**）")
        print(f"        cfg sha256[:16]={rec['config_sha256_before'][:16]}  "
              f"checks={rec['checks_pass']}/{rec['checks_total']}")

    if args.dry_run:
        print("\n[dry-run] 未点火。")
        return 0

    # ---- 逐档点火（串行） -------------------------------------------------
    entries: list[dict] = []
    rc_all = 0
    for eid in order:
        run_id = prep.run_id_of(eid)
        out_dir = prep.out_dir_of(eid)
        cfg = prep.cfg_of(eid)

        print("\n" + "-" * 84)
        print(f"[{eid}] f_demand={pre[eid]['f_demand']:.2f}  agents={pre[eid]['n_agents_requested']:,}")
        done = prep.final_linkstats(out_dir, run_id)
        if done and not args.force:
            print(f"[{eid}] 已存在 {done.name} -> 跳过（断点续跑）")
            e = dict(pre[eid]); e.update({"status": "SKIPPED_DONE", "exit_code": None,
                                          "wall_minutes": 0.0,
                                          "iters_present": len(iters_present(out_dir, run_id))})
            entries.append(e)
            continue

        t0 = time.time()
        rc = prep.run_matsim(cfg, f"{run_id}_run.log", args.heap)
        wall = (time.time() - t0) / 60.0
        rc_all |= rc

        sha_after = sha256_file(cfg)
        dl = prep.final_linkstats(out_dir, run_id)
        its = iters_present(out_dir, run_id)

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
            "log": str(prep.LOG_DIR / f"{run_id}_run.log"),
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
        "step": "7.6F-1",
        "title": "Coarse demand-response on stabilized assignment base (physical agent replication)",
        "updated_at": datetime.now().isoformat(timespec="seconds"),
        "scale_frozen_for_all_runs": SCALE_FROZEN,
        "scale_rule": "SCALE = 459794/200000 = 2.29897 constant; sum_EF/N MUST NOT be used",
        "f_cap": prep.F_CAP, "lambda_fixed": prep.LAMBDA_FIXED, "iterations": prep.TOTAL_ITER,
        "heap": args.heap, "execution": "sequential (RAM-bound)",
        "route_choice": "R01_rc_min (7.6E frozen)",
        "target": "7.3.6A Frozen crosswalk (576 pooled; MUST NOT be replaced)",
        "primary_metric": "MATCHED Sim/Obs(08-09)", "primary_window": "Qbar_10:19",
        "reference_window": "Q_19",
        "demand_scale_selected": False, "lambda_selected": False,
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
    print("下一步：python scripts/od/evaluate_demand_response_7_6f_1.py")
    return rc_all


if __name__ == "__main__":
    raise SystemExit(main())
