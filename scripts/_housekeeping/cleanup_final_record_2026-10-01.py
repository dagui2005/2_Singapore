#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
cleanup_final_record_2026-10-01.py — 从**清理后的当前状态**确定性反推「已移除」清单

原理（可自证）
--------------
清理规则 = 「每个 `ITERS/` 只保留最后一个迭代」。
⇒ 清理后每个被处理过的 `ITERS/` 里只剩 `it.<K>`，其被移除集 = `it.0 … it.(K-1)`。
⇒ 未被处理的 `ITERS/` 里也只有 `it.0`（K=0）⇒ 移除集为空。
⇒ 因此「已移除集」可由当前磁盘状态**唯一确定**，无需依赖可能被覆盖的中间产物。

输出
----
    reports/_cleanup_2026-10-01/CLEANUP_DONE_MANIFEST.csv   （逐项：类/动作/路径/保留项）
    reports/_cleanup_2026-10-01/CLEANUP_DONE_SUMMARY.json
"""
from __future__ import annotations

import csv
import io
import json
import os
import re
from datetime import datetime

ROOT = r"D:\Luan\2026-05\2_Singapore"
OUT = os.path.join(ROOT, "reports", "_cleanup_2026-10-01")
ARCH = r"K:\_sg_matsim_cleanup_2026-10-01"

B_RUNS = {
    "matsim_demand_7_6f_1", "matsim_lambda_7_6g", "matsim_routechoice_7_6d",
    "matsim_kw_7_9b1", "matsim_sampling_capacity_7_9a1", "matsim_viz_7_8",
}
FROZEN = [os.path.join(ROOT, "matsim_final_7_6h")]

# A 类：字节重复的 it.19 events（sha256 全量校验一致后删除）
A_DELETED = [
    (r"matsim_kw_7_9b1\outputs\W01_kw\ITERS\it.19\W01_kw.19.events.xml.gz",
     1778049358, "1e6b1049e223c385", r"matsim_kw_7_9b1\outputs\W01_kw\W01_kw.output_events.xml.gz"),
    (r"matsim_sampling_capacity_7_9a1\outputs\A1_capf0p435\ITERS\it.19\A1_capf0p435.19.events.xml.gz",
     1932894470, "4fbf6869c3c8fd52", r"matsim_sampling_capacity_7_9a1\outputs\A1_capf0p435\A1_capf0p435.output_events.xml.gz"),
    (r"matsim_viz_7_8\outputs\W01_events\ITERS\it.19\W01_events.19.events.xml.gz",
     1694011331, "c9b61fba06d8a9b0", r"matsim_viz_7_8\outputs\W01_events\W01_events.output_events.xml.gz"),
]


def under_frozen(p):
    ap = os.path.abspath(p)
    return any(ap == t or ap.startswith(t + os.sep) for t in FROZEN)


def main():
    rows = []

    # ---- A ----
    for rel, nbytes, h, twin in A_DELETED:
        rows.append(dict(cls="A", action="DELETED", path=rel, bytes=nbytes, files=1,
                         note="duplicate of %s (sha256 %s verified identical); twin kept" % (twin, h)))

    # ---- B / C：反推 ----
    rp = os.path.join(ROOT, "reports")
    for r, ds, fs in os.walk(ROOT):
        if os.path.basename(r).lower() != "iters":
            continue
        if under_frozen(r):
            continue                                   # ⛔ 冻结树永不入册
        subs = [y for y in os.listdir(r) if re.match(r"^it\.\d+$", y)]
        if not subs:
            continue
        k = max(int(y.split(".")[1]) for y in subs)
        if k == 0:
            continue                                   # 未处理（原本即单迭代）
        rel = os.path.relpath(r, ROOT)
        top = rel.split(os.sep)[0]
        if top in B_RUNS:
            cls = "B"
        elif rel.startswith("reports"):
            cls = "C"
        else:
            continue                                   # 未知归属 ⇒ 不入册
        act = "ARCHIVED" if cls == "C" else "DELETED"
        for n in range(k):
            p = os.path.join(r, "it.%d" % n)
            rows.append(dict(cls=cls, action=act, path=os.path.relpath(p, ROOT),
                             bytes="", files="",
                             note="intermediate iteration; %s kept" % ("it.%d" % k)))

    with io.open(os.path.join(OUT, "CLEANUP_DONE_MANIFEST.csv"), "w",
                 encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["cls", "action", "path", "bytes", "files", "note"])
        for r_ in sorted(rows, key=lambda z: (z["cls"], z["action"], z["path"])):
            w.writerow([r_["cls"], r_["action"], r_["path"], r_["bytes"], r_["files"], r_["note"]])

    by = {}
    for r_ in rows:
        a = by.setdefault((r_["cls"], r_["action"]), dict(items=0, bytes=0))
        a["items"] += 1
        if isinstance(r_["bytes"], int):
            a["bytes"] += r_["bytes"]

    arch_files = arch_bytes = 0
    if os.path.isdir(ARCH):
        for rr, dd, ff in os.walk(ARCH):
            for x in ff:
                try:
                    arch_bytes += os.path.getsize(os.path.join(rr, x)); arch_files += 1
                except OSError:
                    pass

    summ = dict(
        generated=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        status="CLEANUP_EXECUTED",
        policy="keep the LAST iteration of every ITERS dir; delete/archive the rest",
        by_class_action={("%s/%s" % k): v for k, v in by.items()},
        archived_to=ARCH, archived_files=arch_files,
        archived_bytes=arch_bytes, archived_gb=round(arch_bytes / 2 ** 30, 3),
        deleted_a_bytes=sum(r_["bytes"] for r_ in rows if r_["cls"] == "A"),
        frozen_untouched=[os.path.relpath(t, ROOT) for t in FROZEN],
    )
    with io.open(os.path.join(OUT, "CLEANUP_DONE_SUMMARY.json"), "w", encoding="utf-8") as f:
        json.dump(summ, f, ensure_ascii=False, indent=2)

    print(json.dumps(summ, ensure_ascii=False, indent=2))
    print("\nrows=%d" % len(rows))
    bad = [r_ for r_ in rows if under_frozen(os.path.join(ROOT, r_["path"]))]
    print("frozen-in-record:", len(bad), "->", "PASS" if not bad else "FAIL")


if __name__ == "__main__":
    main()
