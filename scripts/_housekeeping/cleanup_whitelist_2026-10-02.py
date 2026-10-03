#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
cleanup_whitelist_2026-10-02.py — MATSim 仿真结果清理（第二轮，逐目录白名单 + 留痕）

与 2026-10-01 版的差异
----------------------
1. 新增 E-CAP-01（`experiments/E-CAP-01_scale_capacity/outputs/E-CAP-01/`）。
2. **评价窗护栏**：本项目的评价器主口径 = 「收敛窗 it.10–it.19 逐链路周期均值」，
   且护栏缓存键含 `it.10–19 linkstats sha16`。
   ⇒ **⛔ 硬规则：任何 run 的 `it.10`–`it.19`（含末迭代）linkstats 永不删除。**
   ⇒ 中间迭代的「非 linkstats 大产物」（如 it.0 的 events.xml.gz）可删；
      `it.0`–`it.9` 的 linkstats **保留**（体积小、避免破坏护栏可复算性）。
3. `matsim_viz_7_8`（VIA 回放源）升为**硬豁免**，整树不动。

三类
----
- **A 逐位重复副本**：根层 `{run}.output_{kind}.xml.gz` 与 `ITERS/it.<n>/{run}.<n>.<kind>.xml.gz`
  **双方 sha256 全量一致** ⇒ 删迭代份、留根层。任一不一致 ⇒ 该条 SKIP。
- **B 中间迭代事件**：`it.0`（或任何**非收敛窗末迭代**）目录里的 `*.events.xml.gz`。
  ⛔ 不动任何 `*.linkstats.txt.gz`。
- **C 已固化实验的原始轨迹**：已进报告/已冻结的 run 的根层 `output_events.xml.gz` /
  `output_plans.xml.gz`（**保留 linkstats 与 reports 全部表格**）。删除 or 归档由模式决定。

用法
----
    python scripts/_housekeeping/cleanup_whitelist_2026-10-02.py            # 建清单（只读）
    python scripts/_housekeeping/cleanup_whitelist_2026-10-02.py --verify   # 复核
    python scripts/_housekeeping/cleanup_whitelist_2026-10-02.py --execute [--only-class A]
    python scripts/_housekeeping/cleanup_whitelist_2026-10-02.py --execute --mode=mixed
        mixed = A/B 删除、C **移动**到 K:\\_sg_matsim_cleanup_2026-10-02\\
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import os
import re
import shutil
import sys
import time
from datetime import datetime

ROOT = r"D:\Luan\2026-05\2_Singapore"
OUTDIR = os.path.join(ROOT, "reports", "_cleanup_2026-10-02")
ARCHIVE_ROOT = r"K:\_sg_matsim_cleanup_2026-10-02"

# ---- 硬豁免（永不删除）------------------------------------------------------
FROZEN_TREES = [
    os.path.join(ROOT, "matsim_final_7_6h"),      # v1.0 冻结运行
    os.path.join(ROOT, "matsim_viz_7_8"),         # VIA 回放源（用户在用）
]
KEEP_REPORT_DIRS = [
    "final_model_7_8", "corridor_scale_audit_7_9i",
    "via_congestion_diagnosis_7_8", "sampling_capacity_7_9a1",
    "_cleanup_2026-10-01", "_cleanup_2026-10-02",
]

# ---- A 类候选：(run 绝对目录, runId, 迭代号, [kind...]) ----------------------
A_CANDIDATES = [
    (os.path.join(ROOT, "experiments", "E-CAP-01_scale_capacity", "outputs", "E-CAP-01"),
     "E-CAP-01", 19, ["events"]),
    (os.path.join(ROOT, "reports", "matsim_assignment", "lambda_0p050"),
     "step6_3_lambda_0p050", 0, ["experienced_plans", "plans"]),
    (os.path.join(ROOT, "reports", "matsim_assignment", "lambda_0p075"),
     "step6_3_lambda_0p075", 0, ["experienced_plans", "plans"]),
    (os.path.join(ROOT, "reports", "matsim_assignment", "lambda_0p100"),
     "step6_3_lambda_0p100", 0, ["experienced_plans", "plans"]),
    (os.path.join(ROOT, "reports", "matsim_assignment_6_3_3b", "lambda_0p050"),
     "step6_3_3b_lambda_0p050", 0, ["experienced_plans", "plans"]),
    (os.path.join(ROOT, "reports", "matsim_assignment_6_3_3b", "lambda_0p075"),
     "step6_3_3b_lambda_0p075", 0, ["experienced_plans", "plans"]),
    (os.path.join(ROOT, "reports", "matsim_assignment_6_3_3b", "lambda_0p100"),
     "step6_3_3b_lambda_0p100", 0, ["experienced_plans", "plans"]),
]

# ---- B 类：中间迭代事件（目录级，仅删 events；⛔ 不动 linkstats）------------
B_EVENT_DIRS = [
    os.path.join(ROOT, "experiments", "E-CAP-01_scale_capacity", "outputs", "E-CAP-01", "ITERS", "it.0"),
]

# ---- C 类：已固化实验的原始轨迹（根层 events / plans）-----------------------
C_FILES = [
    # 7.9A-1 —— 判决已冻结；E-CAP-01 逐位复现其数值（链路层等价）
    (os.path.join(ROOT, "matsim_sampling_capacity_7_9a1", "outputs", "A1_capf0p435",
                  "A1_capf0p435.output_events.xml.gz"), "7.9A-1 原始轨迹(events)"),
    (os.path.join(ROOT, "matsim_sampling_capacity_7_9a1", "outputs", "A1_capf0p435",
                  "A1_capf0p435.output_plans.xml.gz"), "7.9A-1 末迭代计划(plans)"),
    # 7.9B1 —— KW 敏感性，已出报告
    (os.path.join(ROOT, "matsim_kw_7_9b1", "outputs", "W01_kw",
                  "W01_kw.output_events.xml.gz"), "7.9B1 原始轨迹(events)"),
    (os.path.join(ROOT, "matsim_kw_7_9b1", "outputs", "W01_kw",
                  "W01_kw.output_plans.xml.gz"), "7.9B1 末迭代计划(plans)"),
    # 7.6D route-choice —— 已出报告
    (os.path.join(ROOT, "matsim_routechoice_7_6d", "outputs", "R01_rc_min",
                  "R01_rc_min.output_plans.xml.gz"), "7.6D R01 计划(plans)"),
    (os.path.join(ROOT, "matsim_routechoice_7_6d", "outputs", "S100k_rc_min",
                  "S100k_rc_min.output_plans.xml.gz"), "7.6D S100k 计划(plans)"),
    # 6.3 assignment —— 已出报告（根层 plans；experienced_plans 走 A 类）
    (os.path.join(ROOT, "reports", "matsim_assignment", "lambda_0p050",
                  "step6_3_lambda_0p050.output_plans.xml.gz"), "6.3 分配 lambda0.050 计划(plans)"),
    (os.path.join(ROOT, "reports", "matsim_assignment_6_3_3b", "lambda_0p050",
                  "step6_3_3b_lambda_0p050.output_plans.xml.gz"), "6.3.3B 分配 lambda0.050 计划(plans)"),
]

# ⛔ 永不删除的 basename 模式（护栏依赖 / VIA 回放 / 冻结基线）
NEVER_DELETE_PATTERNS = [
    re.compile(r"\.linkstats\.txt\.gz$"),
    re.compile(r"\.legHistogram\.txt$"),
]


def under(p: str, trees) -> bool:
    ap = os.path.abspath(p)
    return any(ap == t or ap.startswith(t + os.sep) for t in trees)


def sha256(p: str, blk: int = 4 << 20) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        while True:
            b = f.read(blk)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def share(p: str) -> str:
    return os.path.relpath(p, ROOT)


def _rec(cls, action, kind, path, note, do_hash=False):
    if under(path, FROZEN_TREES):
        return None
    if any(rx.search(os.path.basename(path)) for rx in NEVER_DELETE_PATTERNS):
        return None
    if os.path.isdir(path):
        b = sum(os.path.getsize(os.path.join(r, f))
                for r, _, fs in os.walk(path) for f in fs)
        n, hh = sum(len(fs) for _, _, fs in os.walk(path)), ""
    else:
        b, n = os.path.getsize(path), 1
        hh = sha256(path)[:16] if do_hash else ""
    return dict(cls=cls, action=action, kind=kind, path=path, rel=share(path),
                bytes=b, files=n,
                mtime=datetime.fromtimestamp(os.path.getmtime(path)).strftime("%Y-%m-%d %H:%M"),
                sha256_16=hh, note=note)


def build_rows(do_hash=True):
    rows, notes = [], []

    # ---------- A：逐位重复副本 ----------
    for run_dir, rid, itn, kinds in A_CANDIDATES:
        for kind in kinds:
            root_f = os.path.join(run_dir, "%s.output_%s.xml.gz" % (rid, kind))
            it_f = os.path.join(run_dir, "ITERS", "it.%d" % itn,
                                "%s.%d.%s.xml.gz" % (rid, itn, kind))
            if not (os.path.exists(root_f) and os.path.exists(it_f)):
                notes.append("A SKIP(missing) %s kind=%s" % (share(run_dir), kind))
                continue
            hr, hi = sha256(root_f), sha256(it_f)
            if hr != hi:
                notes.append("A SKIP(hash differs) %s kind=%s  %s vs %s"
                             % (share(run_dir), kind, hr[:12], hi[:12]))
                continue
            r = _rec("A", "delete", "file", it_f,
                     "duplicate of root %s.output_%s.xml.gz (sha256 identical %s)"
                     % (rid, kind, hr[:16]), True)
            if r:
                r["twin"] = root_f          # ★仅供 preflight 再校验，不入 CSV
                rows.append(r)
                rows.append(dict(cls="A", action="keep", kind="file", path=root_f,
                                 rel=share(root_f), bytes=os.path.getsize(root_f), files=1,
                                 mtime=r["mtime"], sha256_16=hr[:16],
                                 note="kept twin (byte-identical)"))

    # ---------- B：中间迭代事件 ----------
    for d in B_EVENT_DIRS:
        if not os.path.isdir(d):
            notes.append("B SKIP(missing) %s" % share(d))
            continue
        evs = [f for f in os.listdir(d) if f.endswith(".events.xml.gz")]
        if not evs:
            notes.append("B no-op (no events) %s" % share(d))
            continue
        for f in evs:
            r = _rec("B", "delete", "file", os.path.join(d, f),
                     "intermediate-iteration events (not in convergence window it.10-19)", False)
            if r:
                rows.append(r)

    # ---------- C：已固化实验的原始轨迹 ----------
    for p, note in C_FILES:
        if not os.path.exists(p):
            notes.append("C SKIP(missing) %s" % share(p))
            continue
        r = _rec("C", "delete", "file", p, note, False)
        if r:
            rows.append(r)

    return rows, notes


def write_manifest(rows, notes):
    os.makedirs(OUTDIR, exist_ok=True)
    header = ["cls", "action", "kind", "rel", "bytes", "files", "mtime", "sha256_16", "note"]
    mp = os.path.join(OUTDIR, "CLEANUP_MANIFEST.csv")
    with io.open(mp, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(header)
        for r in sorted(rows, key=lambda z: (z["action"] != "delete", z["cls"], z["rel"])):
            w.writerow([r["cls"], r["action"], r["kind"], r["rel"], r["bytes"],
                        r["files"], r["mtime"], r["sha256_16"], r["note"]])
    d = [r for r in rows if r["action"] == "delete"]
    by = {}
    for r in d:
        a = by.setdefault(r["cls"], dict(n=0, files=0, bytes=0))
        a["n"] += 1
        a["files"] += r["files"]
        a["bytes"] += r["bytes"]
    summ = dict(
        generated=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        status="WHITELIST_BUILT",
        engine=os.path.abspath(__file__),
        product_root=ROOT,
        totals=dict(items=len(d), files=sum(x["files"] for x in d),
                    bytes=sum(x["bytes"] for x in d),
                    gb=round(sum(x["bytes"] for x in d) / 2 ** 30, 3)),
        by_class=by,
        frozen_exempt=[share(t) for t in FROZEN_TREES],
        keep_report_dirs=KEEP_REPORT_DIRS,
        policy=("A = byte-identical duplicates (keep root, delete iteration twin); "
                "B = intermediate-iteration events only; "
                "C = raw trajectories of already-reported runs (linkstats & reports kept). "
                "HARD: it.10-19 linkstats and any *.linkstats/*.legHistogram never deleted; "
                "matsim_final_7_6h & matsim_viz_7_8 wholly exempt."),
        notes=notes,
    )
    with io.open(os.path.join(OUTDIR, "CLEANUP_SUMMARY.json"), "w", encoding="utf-8") as f:
        json.dump(summ, f, ensure_ascii=False, indent=2)
    return mp, summ


def _eff_mode(r, mode):
    if mode == "archive":
        return "archive"
    if mode == "mixed":
        return "archive" if r["cls"] == "C" else "delete"
    return "delete"


def preflight(rows):
    dele = [r for r in rows if r["action"] == "delete"]
    bad = [r for r in dele if under(r["path"], FROZEN_TREES)]
    ok = not bad
    print("PREFLIGHT frozen-in-delete-set = %d -> %s" % (len(bad), "PASS" if ok else "FAIL"))
    for r in dele:
        if any(rx.search(os.path.basename(r["path"])) for rx in NEVER_DELETE_PATTERNS):
            print("PREFLIGHT !!! linkstats/legHistogram in delete set: %s" % r["rel"])
            ok = False
    # A 类双方再校验（★只校验真正进入删除集的 A 项与孪生；跳过项不参与）
    for r in dele:
        if r["cls"] != "A" or "twin" not in r:
            continue
        it_f, root_f = r["path"], r["twin"]
        if os.path.exists(it_f) and os.path.exists(root_f):
            same = sha256(root_f) == sha256(it_f)
            print("  A re-hash %-58s %s" % (share(it_f)[-58:], "IDENTICAL" if same else "### DRIFT ###"))
            ok = ok and same
    return ok


def execute(rows, mode="delete", only_class=None, limit=None):
    dele = [r for r in rows if r["action"] == "delete"]
    if only_class:
        dele = [r for r in dele if r["cls"] == only_class]
    if limit:
        dele = dele[:limit]
    if not dele:
        print("EXEC nothing to do (only_class=%s)" % only_class)
        return 0, 0
    if any(_eff_mode(r, mode) == "archive" for r in dele):
        os.makedirs(ARCHIVE_ROOT, exist_ok=True)
    done = errs = n_del = n_arc = 0
    log = []
    for i, r in enumerate(dele, 1):
        p, em = r["path"], _eff_mode(r, mode)
        try:
            if not os.path.exists(p):
                log.append("MISSING %s" % r["rel"])
                continue
            if em == "archive":
                dst = os.path.join(ARCHIVE_ROOT, r["rel"])
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                shutil.move(p, dst)
                n_arc += 1
            else:
                if r["kind"] == "dir":
                    shutil.rmtree(p)
                else:
                    os.remove(p)
                n_del += 1
            done += 1
            log.append("%s %s" % ("ARCH" if em == "archive" else "DEL", r["rel"]))
        except Exception as e:                                        # noqa: BLE001
            errs += 1
            log.append("ERR %s :: %s" % (r["rel"], e))
        if i % 50 == 0:
            print("  ... %d/%d (del=%d arch=%d err=%d)" % (i, len(dele), n_del, n_arc, errs), flush=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    with io.open(os.path.join(OUTDIR, "CLEANUP_EXECUTION_%s.log" % stamp), "w", encoding="utf-8") as f:
        f.write("mode=%s deleted=%d archived=%d errors=%d\n\n" % (mode, n_del, n_arc, errs))
        f.write("\n".join(log))
    print("EXEC done=%d deleted=%d archived=%d errors=%d" % (done, n_del, n_arc, errs))
    return done, errs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--execute", action="store_true")
    ap.add_argument("--verify", action="store_true")
    ap.add_argument("--mode", choices=["delete", "archive", "mixed"], default="delete")
    ap.add_argument("--only-class", choices=["A", "B", "C"], default=None)
    ap.add_argument("--limit", type=int, default=None)
    a = ap.parse_args()

    t0 = time.time()
    rows, notes = build_rows()
    mp, summ = write_manifest(rows, notes)
    d = [r for r in rows if r["action"] == "delete"]
    print("=" * 74)
    print("MANIFEST -> %s" % mp)
    print("delete items=%d files=%d size=%.3f GB" %
          (summ["totals"]["items"], summ["totals"]["files"], summ["totals"]["gb"]))
    for k in sorted(summ["by_class"]):
        v = summ["by_class"][k]
        print("  %-3s items=%-4d files=%-4d %8.3f GB" % (k, v["n"], v["files"], v["bytes"] / 2 ** 30))
    if summ["notes"]:
        print("--- notes (%d) ---" % len(summ["notes"]))
        for x in summ["notes"][:24]:
            print("   ", x)
    print("elapsed %.1f s" % (time.time() - t0))

    if a.verify:
        bad = [r for r in d if under(r["path"], FROZEN_TREES)]
        print("VERIFY frozen-in-delete-set:", len(bad), "->", "PASS" if not bad else "FAIL")
        return 0 if not bad else 1
    if a.execute:
        if not preflight(rows):
            print("!!! PREFLIGHT FAIL — ABORT, nothing touched")
            return 2
        print("!!! EXECUTING mode=%s only_class=%s limit=%s on %d items" %
              (a.mode, a.only_class, a.limit, len(d)))
        done, errs = execute(rows, a.mode, a.only_class, a.limit)
        return 0 if errs == 0 else 3
    return 0


if __name__ == "__main__":
    sys.exit(main())
