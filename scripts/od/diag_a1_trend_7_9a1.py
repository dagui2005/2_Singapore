#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""
diag_a1_trend_7_9a1.py — **提前诊断**：A-1 逐迭代拥堵趋势（非权威，不替代正式评价）

定位
----
正式评价必须用 **cycle 均值（it.10–19）** 与 **it.19 单点**（预注册 §2/§5 ③）。
本脚本在仿真**仍在进行**时，对**已落盘**的逐迭代 linkstats 计算面部指标，用于
① 早发现"容量因子未生效 / 网络崩解"这类致命问题；② 预判 §7 四种读法（A/B/C/D）落点。

⛔ 判据声明：本脚本输出**全部为 diagnostic**，⛔ **不得**写入 `a1_summary.json`、⛔ **不得**作为判决依据、
⛔ **不得**替代 `STEP7_9A1_REPORT.md`。正式判决仍由 `audit_sampling_capacity_7_9a1.py` 给出。

口径
----
`cap_mul = 0.434977`（§2 冻结）：linkstats 的 `CAPACITY` 列是**网络原始容量**（A-1 配置只改
`qsim.flowCapacityFactor`，不改 `links.capacity`）⇒ A-1 的有效容量 = `CAPACITY × 0.434977`。

用法
----
    python scripts/od/diag_a1_trend_7_9a1.py            # 全部已落盘迭代
    python scripts/od/diag_a1_trend_7_9a1.py --iters 0,5,10
"""
from __future__ import annotations

import argparse
import csv
import gc
import json
import sys
import time
from pathlib import Path

ROOT = Path(r"D:\Luan\2026-05\2_Singapore")
sys.path.insert(0, str(ROOT / "scripts" / "od"))

import audit_sampling_capacity_7_9a1 as A  # noqa: E402

A1_ITERS = A.A1_OUT / "ITERS"
OUT = A.REPORT_ROOT


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--iters", default="", help="逗号分隔的迭代号；缺省=全部已落盘")
    args = ap.parse_args()

    t0 = time.time()
    pat = f"{A.A1_RUN}.*.linkstats.txt.gz"
    files = sorted(A1_ITERS.glob(f"it.*/{pat}"),
                   key=lambda p: int(p.name.split(".")[1]))
    if args.iters:
        want = {int(x) for x in args.iters.split(",") if x.strip()}
        files = [f for f in files if int(f.name.split(".")[1]) in want]
    print("=" * 118)
    print(f"A-1 逐迭代拥堵趋势（diagnostic，⛔ 非判决依据）  cap_mul={A.F_CAP}  已落盘 {len(files)} 个迭代")
    print("=" * 118)
    if not files:
        print("!! 尚无 linkstats")
        return 1

    # v1.0 it.19 同口径参照（cap_mul=1.0）
    v10 = A.load_linkstats(A.V10_LS)
    vm = A.face_metrics(v10, 1.0)

    hdr = (f"{'iter':>5s} {'n_loaded':>9s} {'max_vc':>8s} {'n>=0.5':>8s} {'n>=0.9':>8s} "
           f"{'n>=1.0':>8s} {'sat_km':>9s} {'n_cong0':>9s} {'n_cong50':>9s} {'aggV/C':>8s} "
           f"{'delay_h':>10s} {'tot_flow':>12s}")
    print(f"\n参照 v1.0 it.19（cap_mul=1.0）：n_loaded={vm['n_loaded']:,} max_vc={vm['max_vc']:.6f} "
          f"n>=1.0={vm['n_vc_ge_10']} sat_km={vm['sat_km']:.4f} n_cong0={vm['n_cong_cut0']:,} "
          f"aggV/C={vm['peak_agg_vc']:.6f} delay_h={vm['delay_h']:,.1f}")
    print(hdr)
    print("-" * len(hdr))

    rows = []
    for p in files:
        it = int(p.name.split(".")[1])
        L = A.load_linkstats(p)
        m = A.face_metrics(L, A.F_CAP)
        rows.append({"iter": it, **{k: m[k] for k in (
            "n_loaded", "max_vc", "n_vc_ge_05", "n_vc_ge_09", "n_vc_ge_10", "sat_km",
            "n_cong_cut0", "n_cong_cut50", "peak_agg_vc", "delay_h", "total_flow",
            "share_len_saturated", "share_flow_on_saturated")}})
        print(f"{it:>5d} {m['n_loaded']:>9,d} {m['max_vc']:>8.4f} {m['n_vc_ge_05']:>8,d} "
              f"{m['n_vc_ge_09']:>8,d} {m['n_vc_ge_10']:>8,d} {m['sat_km']:>9.4f} "
              f"{m['n_cong_cut0']:>9,d} {m['n_cong_cut50']:>9,d} {m['peak_agg_vc']:>8.5f} "
              f"{m['delay_h']:>10,.1f} {m['total_flow']:>12,.0f}", flush=True)
        del L, m
        gc.collect()          # ★每次迭代后强制回收：12 × 693,575 条目字典会累积到 GB 级（首版已被 OOM/超时杀死）

    # 首/末对照 + 倍率
    f_, l_ = rows[0], rows[-1]
    print("-" * len(hdr))
    print(f"\n首({f_['iter']}) → 末({l_['iter']}) 倍率：")
    for k in ("n_vc_ge_05", "n_vc_ge_09", "n_vc_ge_10", "sat_km", "n_cong_cut0",
              "n_cong_cut50", "peak_agg_vc", "delay_h"):
        a, b = f_[k], l_[k]
        r = (b / a) if a else float("inf")
        print(f"  {k:20s} {a:>14,.4f} → {b:>14,.4f}   ×{r:.3f}")

    print(f"\nvs v1.0 it.19（末迭代 {l_['iter']}）：")
    for k, vk in (("n_vc_ge_05", "n_vc_ge_05"), ("n_vc_ge_09", "n_vc_ge_09"),
                  ("n_vc_ge_10", "n_vc_ge_10"), ("sat_km", "sat_km"),
                  ("n_cong_cut0", "n_cong_cut0"), ("n_cong_cut50", "n_cong_cut50"),
                  ("peak_agg_vc", "peak_agg_vc"), ("delay_h", "delay_h")):
        b, a = l_[vk], vm[vk]
        print(f"  {k:20s} v1.0={a:>14,.4f}  A-1={b:>14,.4f}   ×{(b/a if a else float('inf')):.3f}")

    # 情形预判（★diagnostic 专用启发式，与 §7 正式判据不同）
    print("\n★ diagnostic 预判（⛔ 非 §7 判决）：")
    sat_r = l_["sat_km"] / vm["sat_km"] if vm["sat_km"] else float("inf")
    ge1_r = l_["n_vc_ge_10"] / vm["n_vc_ge_10"] if vm["n_vc_ge_10"] else float("inf")
    print(f"  sat_km 倍率 = ×{sat_r:.2f}    n(v/c>=1) 倍率 = ×{ge1_r:.2f}"
          f"（A-0 上界投影分别 ×154.69 / ×51.06）")
    if sat_r < 2:
        print("  ⇒ 接近「情形 C」：拥堵增强很少 ⇒ sample inconsistency 可能**不是**主因（第二刀 = trafficDynamics）")
    elif sat_r < 30:
        print("  ⇒ 介于「情形 A 偏弱」与「情形 C」之间：需正式 cycle 均值确认")
    else:
        print("  ⇒ 接近「情形 A」：拥堵显著增强 ⇒ 主因 = sample-capacity inconsistency")

    rep = {"script": Path(__file__).name, "nature": "DIAGNOSTIC_ONLY_NOT_A_VERDICT",
           "cap_mul": A.F_CAP, "v10_it19_reference": {k: vm[k] for k in (
               "n_loaded", "max_vc", "n_vc_ge_05", "n_vc_ge_09", "n_vc_ge_10", "sat_km",
               "n_cong_cut0", "n_cong_cut50", "peak_agg_vc", "delay_h", "total_flow")},
           "a1_by_iter": rows, "warning": "⛔ 本文件为 diagnostic；判决以 a1_summary.json / "
           "STEP7_9A1_REPORT.md 为准（须用 cycle 均值 it.10–19 + it.19）",
           "elapsed_s": round(time.time() - t0, 1),
           "generated_at": time.strftime("%Y-%m-%d %H:%M:%S")}
    (OUT / "_diag_a1_trend.json").write_text(json.dumps(rep, ensure_ascii=False, indent=2),
                                             encoding="utf-8")
    with open(OUT / "_diag_a1_trend.csv", "w", newline="", encoding="utf-8-sig") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print(f"\n落盘：_diag_a1_trend.json / _diag_a1_trend.csv    耗时 {rep['elapsed_s']} s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
