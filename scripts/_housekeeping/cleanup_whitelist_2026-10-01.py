#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
cleanup_whitelist_2026-10-01.py — MATSim 仿真结果清理（逐目录白名单 + 留痕清单）

设计纪律
--------
1. **默认只建清单，不删任何东西**（`--execute` 才动手）。
2. **白名单粒度 = 目录**：只删 `ITERS/it.<n>` 目录（除每个 ITERS 的**最后一个迭代**）。
   ⇒ 任何 ITERS 只有 1 个迭代（如 it.0）时，**自动 0 删除**（该迭代即最终态）。
3. **A 类**：`根层 events` 与 `ITERS/it.19/events` 字节相同 ⇒ 删 `it.19` 那份，留根层。
   ⛔ 执行前必须**双方 sha256 全部一致**，否则该条 SKIP（不删）。
4. **⛔ 硬豁免**：`matsim_final_7_6h/`（v1.0 冻结运行）整树**永不进入**删除集。
   ⛔ MUST KEEP 报告目录（`final_model_7_8` / `corridor_scale_audit_7_9i` /
   `via_congestion_diagnosis_7_8` / `sampling_capacity_7_9a1`）不在 C 类候选内。
5. 留痕：`CLEANUP_MANIFEST.csv`（class, action, path, bytes, mtime, sha256_short, note）
   + `CLEANUP_SUMMARY.json`。

用法
----
    python scripts/_housekeeping/cleanup_whitelist_2026-10-01.py                # 建清单（只读）
    python scripts/_housekeeping/cleanup_whitelist_2026-10-01.py --verify       # 复核清单
    python scripts/_housekeeping/cleanup_whitelist_2026-10-01.py --execute      # 执行（需先确认）
    python scripts/_housekeeping/cleanup_whitelist_2026-10-01.py --execute --mode=archive
        archive 模式：C 类**移动**到 K:\\_sg_matsim_cleanup_2026-10-01\\（默认 delete）
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
OUTDIR = os.path.join(ROOT, "reports", "_cleanup_2026-10-01")
ARCHIVE_ROOT = r"K:\_sg_matsim_cleanup_2026-10-01"

# ---- 硬豁免（永不删除）------------------------------------------------------
FROZEN_TREES = [
    os.path.join(ROOT, "matsim_final_7_6h"),                 # v1.0 冻结运行
]
KEEP_REPORT_DIRS = [
    "final_model_7_8", "corridor_scale_audit_7_9i",
    "via_congestion_diagnosis_7_8", "sampling_capacity_7_9a1",
]

# ---- B 类：非冻结 run 目录 --------------------------------------------------
B_RUNS = {
    "matsim_demand_7_6f_1": ["F05_rc_min", "F15_rc_min", "F25_rc_min"],
    "matsim_lambda_7_6g": ["L05_rc_min", "L10_rc_min", "L75_rc_min"],
    "matsim_routechoice_7_6d": ["R01_rc_min", "S100k_rc_min"],
    "matsim_kw_7_9b1": ["W01_kw"],
    "matsim_sampling_capacity_7_9a1": ["A1_capf0p435"],
    "matsim_viz_7_8": ["W01_events"],
}

# ---- A 类：重复 events（删除 it.19 那份，保留根层）---------------------------
A_PAIRS = [
    ("matsim_kw_7_9b1", "W01_kw"),
    ("matsim_sampling_capacity_7_9a1", "A1_capf0p435"),
    ("matsim_viz_7_8", "W01_events"),
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


def walk_files(p: str):
    for r, ds, fs in os.walk(p):
        for f in fs:
            yield os.path.join(r, f)


def dir_stat(p: str):
    tot = n = 0
    for f in walk_files(p):
        try:
            tot += os.path.getsize(f); n += 1
        except OSError:
            pass
    return tot, n


def share(base: str) -> str:
    return os.path.relpath(base, ROOT)


# ---------------------------------------------------------------------------
def build_rows(do_hash: bool = True):
    rows = []           # dicts
    notes = []

    def emit(cls, action, path, kind, note, hash_it):
        if under(path, FROZEN_TREES):
            notes.append("SKIP(frozen) %s" % path)
            return
        if kind == "dir":
            b, n = dir_stat(path)
            hh = ""
        else:
            b = os.path.getsize(path); n = 1
            hh = sha256(path)[:16] if (do_hash and hash_it) else ""
        rows.append(dict(cls=cls, action=action, kind=kind, path=path,
                         rel=share(path), bytes=b, files=n,
                         mtime=datetime.fromtimestamp(os.path.getmtime(path)).strftime("%Y-%m-%d %H:%M"),
                         sha256_16=hh, note=note))

    # ---------- A 类 ----------
    for run_dir, rid in A_PAIRS:
        base = os.path.join(ROOT, run_dir, "outputs", rid)
        root_ev = os.path.join(base, "%s.output_events.xml.gz" % rid)
        it19_ev = os.path.join(base, "ITERS", "it.19", "%s.19.events.xml.gz" % rid)
        if not (os.path.exists(root_ev) and os.path.exists(it19_ev)):
            notes.append("A SKIP(missing): %s" % base); continue
        h_root, h_it = sha256(root_ev), sha256(it19_ev)
        if h_root != h_it:
            notes.append("A SKIP(hash differs!) %s" % base); continue
        emit("A", "delete", it19_ev, "file",
             "duplicate of root events (sha256 identical: %s)" % h_root[:16], True)
        rows.append(dict(cls="A", action="keep", kind="file", path=root_ev,
                         rel=share(root_ev), bytes=os.path.getsize(root_ev), files=1,
                         mtime=datetime.fromtimestamp(os.path.getmtime(root_ev)).strftime("%Y-%m-%d %H:%M"),
                         sha256_16=h_root[:16], note="kept twin (byte-identical)"))

    # ---------- B 类 ----------
    for run_dir, rids in B_RUNS.items():
        for rid in rids:
            iters = os.path.join(ROOT, run_dir, "outputs", rid, "ITERS")
            _collect_iters(emit, iters, "B", run_dir, notes)

    # ---------- C 类 ----------
    rp = os.path.join(ROOT, "reports")
    for d in sorted(os.listdir(rp)):
        if d in KEEP_REPORT_DIRS:
            notes.append("C SKIP(keep-list) reports/%s" % d); continue
        base = os.path.join(rp, d)
        if not os.path.isdir(base):
            continue
        for r, ds, fs in os.walk(base):
            for x in ds:
                if x.lower() == "iters":
                    _collect_iters(emit, os.path.join(r, x), "C", "reports/" + d, notes)
    return rows, notes


def _collect_iters(emit, iters_dir, cls, owner, notes):
    if not os.path.isdir(iters_dir):
        return
    subs = [y for y in os.listdir(iters_dir) if re.match(r"^it\.\d+$", y)]
    if not subs:
        return
    ns = sorted(int(y.split(".")[1]) for y in subs)
    keep = "it.%d" % ns[-1]
    for n in ns[:-1]:
        emit(cls, "delete", os.path.join(iters_dir, "it.%d" % n), "dir",
             "intermediate iteration (owner=%s, keep=%s)" % (owner, keep), False)
    if len(ns) == 1:
        notes.append("no-op (single iteration %s): %s" % (keep, iters_dir))


# ---------------------------------------------------------------------------
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
        k = r["cls"]
        a = by.setdefault(k, dict(n=0, files=0, bytes=0))
        a["n"] += 1; a["files"] += r["files"]; a["bytes"] += r["bytes"]
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
        policy="delete ITERS/it.<n> except the LAST iteration of each ITERS dir; single-iteration dirs are no-ops",
        notes=notes,
    )
    with io.open(os.path.join(OUTDIR, "CLEANUP_SUMMARY.json"), "w", encoding="utf-8") as f:
        json.dump(summ, f, ensure_ascii=False, indent=2)
    return mp, summ


def _eff_mode(r, mode):
    """mixed = A/B 删除、C 归档到 K:（用户 2026-10-01 裁定）。"""
    if mode == "archive":
        return "archive"
    if mode == "mixed":
        return "archive" if r["cls"] == "C" else "delete"
    return "delete"


def preflight(rows):
    """执行前硬门：① 冻结豁免 ② A 类双方 sha256 仍一致 ③ 目标仍存在。"""
    dele = [r for r in rows if r["action"] == "delete"]
    bad = [r for r in dele if under(r["path"], FROZEN_TREES)]
    ok = not bad
    print("PREFLIGHT frozen-in-delete-set = %d -> %s" % (len(bad), "PASS" if ok else "FAIL"))
    for r in rows:
        if r["cls"] == "A" and r["action"] == "keep":
            twin = r["path"].replace(".output_events.xml.gz", "")
            it19 = os.path.join(os.path.dirname(twin), "ITERS", "it.19",
                                os.path.basename(twin) + ".19.events.xml.gz")
            if os.path.exists(it19):
                same = sha256(r["path"]) == sha256(it19)
                print("A re-hash %-52s %s" % (os.path.basename(r["path"])[:52],
                                              "IDENTICAL" if same else "### DRIFT ###"))
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
    done = errs = 0
    n_del = n_arc = 0
    log = []
    for i, r in enumerate(dele, 1):
        p = r["path"]
        em = _eff_mode(r, mode)
        try:
            if not os.path.exists(p):
                log.append("MISSING %s" % r["rel"]); continue
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
            log.append("%s %s -> %s" % ("ARCH" if em == "archive" else "DEL", r["rel"], em))
        except Exception as e:                                    # noqa: BLE001
            errs += 1
            log.append("ERR %s :: %s" % (r["rel"], e))
        if i % 50 == 0:
            print("  ... %d/%d  (del=%d arch=%d err=%d)" % (i, len(dele), n_del, n_arc, errs), flush=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    with io.open(os.path.join(OUTDIR, "CLEANUP_EXECUTION_%s.log" % stamp),
                 "w", encoding="utf-8") as f:
        f.write("mode=%s  deleted=%d  archived=%d  errors=%d\n\n" % (mode, n_del, n_arc, errs))
        f.write("\n".join(log))
    print("EXEC done=%d deleted=%d archived=%d errors=%d" % (done, n_del, n_arc, errs))
    return done, errs


# ---------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--execute", action="store_true")
    ap.add_argument("--verify", action="store_true")
    ap.add_argument("--mode", choices=["delete", "archive", "mixed"], default="delete",
                    help="mixed = A/B 删除、C 归档到 K:")
    ap.add_argument("--no-hash", action="store_true")
    ap.add_argument("--only-class", choices=["A", "B", "C"], default=None,
                    help="只处理指定类（分批用）")
    ap.add_argument("--limit", type=int, default=None, help="本轮最多处理 N 项")
    a = ap.parse_args()

    t0 = time.time()
    rows, notes = build_rows(do_hash=not a.no_hash)
    mp, summ = write_manifest(rows, notes)
    d = [r for r in rows if r["action"] == "delete"]
    print("=" * 74)
    print("MANIFEST -> %s" % mp)
    print("delete items=%d  files=%d  size=%.3f GB" %
          (summ["totals"]["items"], summ["totals"]["files"], summ["totals"]["gb"]))
    for k in sorted(summ["by_class"]):
        v = summ["by_class"][k]
        print("  %-3s items=%-5d files=%-6d %.3f GB" % (k, v["n"], v["files"], v["bytes"] / 2 ** 30))
    if summ["notes"]:
        print("--- notes (%d) ---" % len(summ["notes"]))
        for x in summ["notes"][:20]:
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
