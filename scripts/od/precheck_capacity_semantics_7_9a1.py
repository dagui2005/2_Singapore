# -*- coding: utf-8 -*-
"""
precheck_capacity_semantics_7_9a1.py  ——  7.9A-1 §11「CAPACITY 语义」提前解算

背景
----
`audit_sampling_capacity_7_9a1.py : resolve_capacity_semantics()` 会拿
  v1.0(it.19) 与 A-1(it.19) 两份 linkstats 的 `CAPACITY` 列做对比：
    * 逐位相同            -> BASE_CAPACITY      (评价器自己 ×F_CAP)
    * 恰好 = ×0.434977    -> EFFECTIVE_CAPACITY (评价器 ×1.0)
    * 其余                -> CAPACITY_SEMANTICS_UNRESOLVED (⚠ 正式报告不报 v/c)

若为第三种，必须在正式评价前定位原因（否则 A04 会挂、§11 全空）。
本脚本用**已经落盘的 A-1 中间迭代**（默认 it.12）提前给出同一个判定，
以便在仿真结束前就能排除/发现风险。

注意：本脚本只复用评价器里的 `resolve_capacity_semantics` 与 `capacity_crossval`，
      不重写判据（避免"两套口径"）。
输出：reports/sampling_capacity_7_9a1/_precheck_capacity_semantics.json
"""
from __future__ import annotations

import argparse
import gzip
import json
import sys
import time
from pathlib import Path

ROOT = Path(r"D:\Luan\2026-05\2_Singapore")
SCRIPTS_OD = ROOT / "scripts" / "od"
sys.path.insert(0, str(SCRIPTS_OD))

import audit_sampling_capacity_7_9a1 as A  # noqa: E402

REPORT_DIR = ROOT / "reports" / "sampling_capacity_7_9a1"
OUT_JSON = REPORT_DIR / "_precheck_capacity_semantics.json"

V10_LS = ROOT / "matsim_final_7_6h" / "outputs" / "W01_rc_min" / "ITERS" / "it.19" / "W01_rc_min.19.linkstats.txt.gz"
A1_ITERS = ROOT / "matsim_sampling_capacity_7_9a1" / "outputs" / "A1_capf0p435" / "ITERS"


def pick_a1_linkstats() -> Path:
    """取 A-1 已落盘的最大迭代 linkstats（.gz 完整写出后才算数）。"""
    best: tuple[int, Path] | None = None
    for d in A1_ITERS.glob("it.*"):
        try:
            it = int(d.name.split(".")[1])
        except (IndexError, ValueError):
            continue
        f = d / f"A1_capf0p435.{it}.linkstats.txt.gz"
        if f.exists() and f.stat().st_size > 1_000_000:
            if best is None or it > best[0]:
                best = (it, f)
    if best is None:
        raise SystemExit("FATAL: 找不到任何 A-1 linkstats")
    return best[1]


def read_caps(path: Path) -> tuple[dict, int, list[str]]:
    """返回 {link: cap}, 列数, 表头。CAPACITY 列索引从表头定位（防列序漂移）。"""
    with gzip.open(path, "rt", encoding="utf-8", newline="") as fh:
        header = fh.readline().rstrip("\n").split("\t")
        try:
            icap = header.index("CAPACITY")
        except ValueError:
            raise SystemExit(f"FATAL: {path.name} 表头无 CAPACITY 列：{header[:12]}")
        caps: dict[str, float] = {}
        for line in fh:
            tk = line.split("\t")
            if len(tk) <= icap:
                continue
            try:
                caps[tk[0]] = float(tk[icap])
            except ValueError:
                continue
    return caps, len(header), header


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--a1", default=None, help="显式指定 A-1 linkstats 路径")
    args = ap.parse_args()

    t0 = time.time()
    a1_path = Path(args.a1) if args.a1 else pick_a1_linkstats()
    a1_it = a1_path.name.split(".")[1]

    print("=" * 78)
    print("7.9A-1 §11 CAPACITY 语义 · 提前解算")
    print("=" * 78)
    print(f"v1.0 : {V10_LS.name}  ({V10_LS.stat().st_size/1048576:.2f} MiB)")
    print(f"A-1  : {a1_path.name}  ({a1_path.stat().st_size/1048576:.2f} MiB, 迭代 {a1_it})")
    print(f"F_CAP = {A.F_CAP}")

    cap10, ncol10, hdr10 = read_caps(V10_LS)
    cap1, ncol1, hdr1 = read_caps(a1_path)
    print(f"\n列数  v1.0={ncol10}  A-1={ncol1}   表头一致={hdr10 == hdr1}")
    print(f"行数  v1.0={len(cap10):,}  A-1={len(cap1):,}")

    # 复用评价器构造的 dict 形态（只需 cap 字段即可完成消解）
    ls_v10 = {k: {"cap": v} for k, v in cap10.items()}
    ls_a1 = {k: {"cap": v} for k, v in cap1.items()}
    cs = A.resolve_capacity_semantics(ls_v10, ls_a1)

    print("\n[判定]")
    print(f"  公共链路          = {cs['n_common']:,}")
    print(f"  CAPACITY 逐位相同 = {cs['n_identical']:,}")
    print(f"  = cap×F_CAP 命中  = {cs['n_ratio_match']:,}")
    print(f"  MODE              = {cs['mode']}")
    print(f"  cap_mul_v10 / a1  = {cs['cap_mul_v10']} / {cs['cap_mul_a1']}")

    # 抽几个不同量级的公共链路做人工核对
    common = sorted(set(cap10) & set(cap1))
    common.sort(key=lambda k: cap10[k])
    picks = []
    if common:
        idxs = sorted({0, len(common) // 4, len(common) // 2, (3 * len(common)) // 4, len(common) - 1})
        for i in idxs:
            k = common[i]
            c0, c1 = cap10[k], cap1[k]
            picks.append({"link": k, "cap_v10": round(c0, 6), "cap_a1": round(c1, 6),
                          "ratio": round(c1 / c0, 9) if c0 else None})
    print("\n[抽样核对：按 v1.0 容量升序取 5 分位]")
    for p in picks:
        print(f"  {p['link']:<24} v1.0={p['cap_v10']:>12.3f}  A-1={p['cap_a1']:>12.3f}  ratio={p['ratio']}")

    # 容量分布（确认"文件里的容量没被动过"）
    def q(d: dict, p: float) -> float:
        xs = sorted(d.values())
        return xs[min(len(xs) - 1, int(p * len(xs)))] if xs else 0.0
    print("\n[CAPACITY 分位]  (veh/h)")
    for lbl, d in (("v1.0", cap10), ("A-1", cap1)):
        print(f"  {lbl:<5} P0={q(d,0):.0f}  P25={q(d,.25):.0f}  P50={q(d,.5):.0f}  "
              f"P75={q(d,.75):.0f}  P100={q(d,1):.0f}  sum={sum(d.values()):.0f}")

    verdict = "CAPACITY_SEMANTICS_RESOLVED"
    if cs["mode"] == "BASE_CAPACITY":
        note = "linkstats.CAPACITY = 基础容量（未被 flowCapacityFactor 缩放）⇒ 评价器 ×F_CAP 正确"
    elif cs["mode"] == "EFFECTIVE_CAPACITY":
        note = "linkstats.CAPACITY 已被缩放 ⇒ 评价器应 ×1.0（脚本已按此设 cap_mul_a1）"
    else:
        verdict = "CAPACITY_SEMANTICS_UNRESOLVED"
        note = "⚠ 两版容量既不逐位相同、也不成 F_CAP 比例 ⇒ A04 会挂、§11 不报 v/c，需先定位"

    rec = {
        "verdict": verdict,
        "note": note,
        "a1_iteration_used": int(a1_it),
        "a1_linkstats": a1_path.name,
        "v10_linkstats": V10_LS.name,
        "f_cap": A.F_CAP,
        "resolve": cs,
        "n_rows_v10": len(cap10),
        "n_rows_a1": len(cap1),
        "n_cols_v10": ncol10,
        "n_cols_a1": ncol1,
        "header_identical": hdr10 == hdr1,
        "sample_pairs": picks,
        "cap_sum_v10": sum(cap10.values()),
        "cap_sum_a1": sum(cap1.values()),
        "elapsed_s": round(time.time() - t0, 2),
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")

    print("\n[判决] " + verdict)
    print("       " + note)
    print(f"落盘   {OUT_JSON}  ({OUT_JSON.stat().st_size:,} B)")
    print(f"耗时   {rec['elapsed_s']} s")
    return 0 if verdict == "CAPACITY_SEMANTICS_RESOLVED" else 2


if __name__ == "__main__":
    raise SystemExit(main())
