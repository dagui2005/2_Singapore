#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""
prewarm_events_7_9a1.py — 预热 / 校验 Step 7.9A-1 的 events 解析缓存（零仿真 / 只读输入）

背景
----
`audit_sampling_capacity_7_9a1.py` 的 `events_cached()` 在 2026-09-29 11:09 的「缓存键重构」中
被**误改为裸调用** `events_time_series()`（调用点丢失）⇒ 缓存与 `parser_fingerprint` 双双成为死代码，
正式评价会白付 ~20 min × 2（v1.0 + A-1）解析成本。该缺陷已修复（调用点重接回 `events_cached`）。

本脚本做三件事（全部只读输入，只写 `reports/sampling_capacity_7_9a1/_events_cache/`）：
  1. 按**正式评价完全相同的参数**调用 `A.events_cached("v1.0", V10_EV, ..., cap_mul=1.0)`
     ⇒ 产出带新解析器指纹的缓存，正式评价可直接命中（省 ~20 min）。
  2. **往返一致性证明**：断言「返回对象 == 落盘 JSON 的 payload」且「再次调用（缓存命中）== 首次返回」。
     这是缓存正确性的充要断言 —— 命中时 `events_cached` 返回的就是 `c["payload"]`。
  3. 打印头部指标，与 2026-09-29 10:40 旧缓存基线**逐位对照**（下表中 `BASE_*`）。

⛔ 本脚本不修改任何冻结产物；⛔ 不触发仿真；⛔ 不改变任何口径常量。

用法
----
    python scripts/od/prewarm_events_7_9a1.py            # 计算（首次 ~20 min）并校验
    python scripts/od/prewarm_events_7_9a1.py --check    # 仅读缓存校验（~1 min）
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(r"D:\Luan\2026-05\2_Singapore")
SCRIPTS_OD = ROOT / "scripts" / "od"
sys.path.insert(0, str(SCRIPTS_OD))

import audit_sampling_capacity_7_9a1 as A  # noqa: E402

# 2026-09-29 10:40 旧缓存（evaluator 8a559bac1c034af1）基线 —— 必须逐位复现
BASE = {
    "n_lines": 163_305_991,
    "n_cells": 4_470_362,
    "n_unknown_link": 0,
    "n_leave_traffic": 235_940,
    "n_pair_miss": 236_039,
    "n_pair_net": 236_039,
    "n_stuck": 0,
    "sum_dep": 236_044,
    "sum_arr": 235_940,
}
BASE_PROFILE = {"enroute_max": 36_176, "enroute_peak_hms": "08:55",
                "queued_max": 57, "n_slow_max": 30_706, "n_slow_peak_hms": "08:25",
                "agg_vc_max": 0.102603}


def _argmax(a):
    return max(range(len(a)), key=lambda i: a[i])


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="仅读缓存校验，不重算")
    args = ap.parse_args()

    t0 = time.time()
    print("=" * 92)
    print("7.9A-1 events 缓存预热 / 校验")
    print("=" * 92)

    fp = A.parser_fingerprint()
    print(f"[1] parser_fingerprint = {fp}")
    print(f"    冻结常量：BIN_S={A.BIN_S}  T_LO={A.T_LO}  T_HI={A.T_HI}  "
          f"EV_SLOW={A.EV_SLOW}  EV_MIN_N={A.EV_MIN_N}")
    print(f"    events 文件：{A.V10_EV}")
    print(f"    存在={A.V10_EV.exists()}  "
          f"大小={A.V10_EV.stat().st_size/2**30:.3f} GiB" if A.V10_EV.exists() else "    !! 缺失")

    print("\n[2] 载入 v1.0 linkstats 并建索引")
    v10 = A.load_linkstats(A.V10_LS)
    print(f"    n_links={len(v10):,}")
    idx, L_arr, FS_arr, CAP_arr = A.build_link_index(v10)
    assert len(idx) == 693_575, f"索引条目数异常 {len(idx)}"
    print(f"    索引条目={len(idx):,}  （期望 693,575）")

    print("\n[3] 调用 events_cached（缓存缺失则解析；已存在则命中，幂等）")
    t1 = time.time()
    r1 = A.events_cached("v1.0", A.V10_EV, idx, L_arr, FS_arr, CAP_arr, 1.0, force=False)
    dt1 = time.time() - t1
    print(f"    返回：lines={r1['n_lines']:,}  cells={r1['n_cells']:,}  "
          f"dep={r1['sum_dep']:,}  arr={r1['sum_arr']:,}  ({dt1:.0f}s)")
    if args.check and dt1 > 120:
        print("    !! --check 却发生了重算（>120 s）⇒ 缓存未命中，请检查指纹/路径")
        return 2

    # ---- 定位刚写的缓存文件（键 = tag_文件名_sha16_cm1_fp{fp}.json）----
    d = A.OUT / "_events_cache"
    cand = sorted(d.glob(f"v1.0_{A.V10_EV.name}_*_cm1_fp{fp}.json"))
    assert len(cand) == 1, f"预期恰 1 个新键缓存，实得 {len(cand)}：{[c.name for c in cand]}"
    cache_p = cand[0]
    print(f"\n[4] 往返一致性断言  缓存文件 = {cache_p.name}")

    disk = json.loads(cache_p.read_text(encoding="utf-8"))
    ok_meta = (disk.get("parser_fingerprint") == fp and disk.get("cap_mul") == 1.0
               and disk.get("tag") == "v1.0")
    assert ok_meta, f"元数据不符：{ {k: disk.get(k) for k in ('parser_fingerprint','cap_mul','tag')} }"
    print(f"    [OK] 元数据：parser_fingerprint={disk['parser_fingerprint']}  cap_mul={disk['cap_mul']}  "
          f"tag={disk['tag']}  evaluator_sha256[:16]={disk['evaluator_sha256'][:16]}")

    # (a) 返回对象 == 落盘 payload（逐位）
    same_disk = (disk["payload"] == r1)
    print(f"    [{'OK' if same_disk else 'FAIL'}] 返回对象 == 落盘 payload（逐位）")
    assert same_disk, "落盘 payload 与返回对象不一致 ⇒ 序列化有损（疑似 numpy 标量被 default=str 变字符串）"

    # (b) 再次调用（缓存命中）== 首次返回（逐位）
    r2 = A.events_cached("v1.0", A.V10_EV, idx, L_arr, FS_arr, CAP_arr, 1.0)
    same_hit = (r2 == r1)
    print(f"    [{'OK' if same_hit else 'FAIL'}] 缓存命中返回值 == 首次返回值（逐位）")
    assert same_hit, "缓存命中返回值与首次不一致"

    # ---- 头部指标 vs 10:40 基线 ----
    print("\n[5] 头部指标 vs 10:40 基线（当前解析器）")
    allok = True
    for k, v in BASE.items():
        got = r1[k]
        ok = (got == v)
        allok &= ok
        print(f"    [{'OK' if ok else 'FAIL'}] {k:16s} got={got:>12,}  base={v:>12,}")
    b = r1["bins"]
    enr = [x["enroute_end"] for x in b]
    q = [x["queued_end"] for x in b]
    sl = [x["n_slow_links"] for x in b]
    agg = [x["agg_vc"] for x in r1["agg15"]]
    got_p = {"enroute_max": max(enr), "enroute_peak_hms": b[_argmax(enr)]["t_hms"],
             "queued_max": max(q), "n_slow_max": max(sl), "n_slow_peak_hms": b[_argmax(sl)]["t_hms"],
             "agg_vc_max": round(max(agg), 6)}
    for k, v in BASE_PROFILE.items():
        got = got_p[k]
        ok = bool(got == v)
        allok &= ok
        print(f"    [{'OK' if ok else 'FAIL'}] {k:16s} got={got!s:>12}  base={v!s:>12}")

    # ---- 结构性不变量（★常数经实测：窗口内 Σenter−Σleft = n_pair_miss = n_pair_net = 236,039）----
    print("\n[6] 结构性不变量")
    se = sum(x["n_enter"] for x in b)
    lf = sum(x["n_left"] for x in b)
    inv = {
        "窗口内 Σenter − Σleft == n_pair_miss == 236,039（末链不发 `left link`）":
            (se - lf) == 236_039 and r1["n_pair_miss"] == 236_039,
        "n_pair_miss == n_pair_net（配对差无额外损耗）":
            r1["n_pair_miss"] == r1["n_pair_net"] == 236_039,
        "n_stuck == 0": r1["n_stuck"] == 0,
        "sum_dep == 236,044": r1["sum_dep"] == 236_044,
        "n_leave_traffic == 235,940（= dep − 104，104 条窗外迟到）":
            r1["n_leave_traffic"] == 235_940 and r1["sum_arr"] == r1["sum_dep"] - 104,
        "enroute_max <= sum_dep": max(enr) <= r1["sum_dep"],
        "n_slow_max > 0（v1.0 不堵却有大量未达自由流 ⇒ 短链量化特征）": max(sl) > 0,
    }
    for k, ok in inv.items():
        allok &= bool(ok)
        print(f"    [{'OK' if ok else 'FAIL'}] {k}")

    verdict = "PREWARM_OK" if (allok and same_disk and same_hit) else "PREWARM_FAILED"
    receipt = {"script": Path(__file__).name, "verdict": verdict,
               "parser_fingerprint": fp, "cache_file": cache_p.name,
               "cache_bytes": cache_p.stat().st_size,
               "computed_in_s": round(dt1, 1), "total_in_s": round(time.time() - t0, 1),
               "roundtrip_payload_identical": same_disk,
               "cache_hit_identical": same_hit,
               "headline": {**{k: r1[k] for k in BASE}, **got_p},
               "baseline_match_all": bool(allok),
               "generated_at": time.strftime("%Y-%m-%d %H:%M:%S")}
    out = A.OUT / "_events_cache" / f"prewarm_receipt_{fp}.json"
    out.write_text(json.dumps(receipt, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n{'=' * 92}")
    print(f"判决 = {verdict}    （凭证 {out.name}）")
    print(f"总耗时 {receipt['total_in_s']} s（其中解析/读缓存 {receipt['computed_in_s']} s）")
    print("=" * 92)
    return 0 if verdict == "PREWARM_OK" else 1


if __name__ == "__main__":
    raise SystemExit(main())
