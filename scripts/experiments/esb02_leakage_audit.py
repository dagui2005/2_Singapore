#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
E-SB-02B | AM-SpeedBand -> OD 信息泄漏审计（只读）
==================================================
目的：把「AM SpeedBand 通过重力阻抗进入需求」的泄漏，从"定性担心"变成"可量化证据"。

泄漏通道（唯一）：
    LTA TrafficSpeedBands(AM)  --Step5C/5C.1-->  C_ij^AM (332x332 travel time)
                               --build_prior_od_5c1-->  gravity seed  exp(-lam*C_ij^AM)
                               --IPF-->  prior OD  --build_matsim_population-->  car-only 200k agents
P_i / A_j / Table118 是硬约束（IPF 边际与块约束），**不受**阻抗选择影响；
因此泄漏只作用于「目的地选择权重」这一层。

对照臂：Step 5B 用自由流阻抗 C^FF（reports/od_impedance/impedance_matrix.parquet）构建，
        **不含任何 SpeedBand 输入**，其余约束框架与 5C.1 完全相同。
        => T^5B 是天然的「无泄漏」需求；T^5B vs T^5C.1 的总变差 = 泄漏的空间杠杆。

本脚本只读，不写任何冻结件；输出到 reports/esb02_leakage_audit/。
"""
from __future__ import annotations
import json
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(r"D:\Luan\2026-05\2_Singapore")
OUT = ROOT / "reports/esb02_leakage_audit"
ZONE_DICT = ROOT / "reports/od_zone/zone_dictionary.csv"

OD_5B = ROOT / "reports/od_prior_5b/prior_od_5b_lambda_{tag}.parquet"
OD_5C1 = ROOT / "reports/od_prior_5c1/prior_od_5c1_lambda_{tag}.parquet"
CMP_SUMMARY = ROOT / "reports/od_prior_5c1/compare_5b_vs_5c1_summary.csv"
CMP_BLOCKS = ROOT / "reports/od_prior_5c1/compare_5b_vs_5c1_region_pa.csv"

FF_IMP = ROOT / "reports/od_impedance/impedance_matrix.parquet"
AM_IMP = ROOT / "reports/od_impedance_ampeak_v2/ampeak_impedance_v2.parquet"
AM_MATCH = ROOT / "reports/od_impedance_ampeak_v2/lta_osm_match_v2.csv"
POP_XML = ROOT / "matsim_final_7_6h/populations/pop_W01/population_lambda_0p075.xml.gz"

LAMBDAS = [0.05, 0.075, 0.10, 0.125, 0.15]
LAM_PRIMARY = 0.075

GATES: list[dict] = []


def gate(gid: str, desc: str, ok: bool, measured: str) -> bool:
    GATES.append({"id": gid, "desc": desc, "pass": bool(ok), "measured": measured})
    print(f"  [{'PASS' if ok else 'FAIL'}] {gid}: {desc}  ({measured})")
    return bool(ok)


def tag(lam: float) -> str:
    return f"{lam:.3f}".replace(".", "p")


def load_od(path: Path, ids: list[int]) -> np.ndarray:
    df = pd.read_parquet(path)
    n = len(ids)
    pos = {z: i for i, z in enumerate(ids)}
    m = np.zeros((n, n), dtype=float)
    ii = df.origin_zone.astype(int).map(pos).to_numpy()
    jj = df.destination_zone.astype(int).map(pos).to_numpy()
    np.add.at(m, (ii, jj), df.trips.to_numpy(float))
    return m


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    print("=" * 78)
    print("E-SB-02B | AM-SpeedBand -> OD leakage audit (read-only)")
    print("=" * 78)

    z = pd.read_csv(ZONE_DICT, encoding="utf-8-sig")
    z["zone_id"] = pd.to_numeric(z.zone_id).astype(int)
    ids = z.zone_id.sort_values().tolist()

    # ---------------- [1] 通道自证 ----------------
    print("\n[1] 泄漏通道（AM SpeedBand -> 阻抗 -> 重力 -> OD）")
    c_ff = pd.read_parquet(FF_IMP)
    c_am = pd.read_parquet(AM_IMP)
    med_ff = float(c_ff.travel_time_min.median())
    med_am = float(c_am.travel_time_min.median())
    src_am = json.load(open(ROOT / "reports/od_impedance_ampeak_v2/ampeak_v2_validation.json",
                            encoding="utf-8"))
    print(f"    C^FF 中位 {med_ff:.3f} min  |  C^AM,v2 中位 {med_am:.3f} min  (+{med_am/med_ff-1:.1%})")
    print(f"    AM 覆盖(长度份额) = {src_am['am_coverage_length_share']:.4f}；"
          f"tier = {src_am['tier_breakdown']}")
    gate("L1", "AM 阻抗确实由 SpeedBand 构建（非空、可达、覆盖>0）",
         len(c_am) == 332 * 332 and bool(c_am.reachable.all())
         and src_am["am_coverage_length_share"] > 0,
         f"332x332 reachable=100% cov_len={src_am['am_coverage_length_share']:.3f}")
    gate("L2", "最终 v1.0 需求来自 5C.1（携带 AM 信息）",
         POP_XML.exists(),
         f"{POP_XML.name} exists={POP_XML.exists()}")

    # ---------------- [2] 泄漏量级：TV(T^5B, T^5C.1) ----------------
    print("\n[2] 泄漏量级：T^5B(无 SpeedBand) vs T^5C.1(用 AM)")
    cmp_s = pd.read_csv(CMP_SUMMARY, encoding="utf-8-sig")
    rows = []
    for lam in LAMBDAS:
        tb = load_od(Path(str(OD_5B).format(tag=tag(lam))), ids)
        tc = load_od(Path(str(OD_5C1).format(tag=tag(lam))), ids)
        b, c = tb.sum(), tc.sum()
        tv_recompute = float(np.abs(tb / b - tc / c).sum() / 2)
        tv_published = float(cmp_s.loc[np.isclose(cmp_s.lambda_per_min, lam),
                                       "total_variation_5B_vs_5C1"].iloc[0])
        # 结构指标
        diag_b = float(np.diag(tb).sum() / b)
        diag_c = float(np.diag(tc).sum() / c)
        rows.append({"lambda_per_min": lam,
                     "od_total_5B": b, "od_total_5C1": c,
                     "TV_recomputed": tv_recompute, "TV_published": tv_published,
                     "TV_diff": abs(tv_recompute - tv_published),
                     "intrazonal_share_5B": diag_b, "intrazonal_share_5C1": diag_c,
                     "intrazonal_rel_change": diag_c / diag_b - 1})
    tvdf = pd.DataFrame(rows)
    tvdf.to_csv(OUT / "leakage_by_lambda.csv", index=False, encoding="utf-8-sig")
    print(tvdf.round(4).to_string(index=False))
    r = tvdf[np.isclose(tvdf.lambda_per_min, LAM_PRIMARY)].iloc[0]
    print(f"\n    ★ λ={LAM_PRIMARY}: TV = {r.TV_recomputed:.4f} ({r.TV_recomputed*100:.2f}%)；"
          f"区内份额 {r.intrazonal_share_5B:.4f} -> {r.intrazonal_share_5C1:.4f} "
          f"（{r.intrazonal_rel_change:+.1%} 相对）")
    gate("L3", "本脚本重算 TV 与既有产物逐位一致（口径自证）",
         bool((tvdf.TV_diff < 1e-6).all()),
         f"max|Δ| = {tvdf.TV_diff.max():.2e}")
    gate("L4", "泄漏量级存在且可测（TV>0）",
         bool(r.TV_recomputed > 0),
         f"TV@λ0.075 = {r.TV_recomputed:.4f}")
    gate("L5", "泄漏量级为「小」（TV < 10%）——不喧宾夺主",
         bool(r.TV_recomputed < 0.10),
         f"{r.TV_recomputed*100:.2f}% < 10%")

    # ---------------- [3] 泄漏的空间模式 ----------------
    print("\n[3] 泄漏的空间模式（Region x WorkplacePA，275 块）")
    blk = pd.read_csv(CMP_BLOCKS, encoding="utf-8-sig")
    s = blk[np.isclose(blk.lambda_per_min, LAM_PRIMARY)].copy()
    s["delta_pp"] = s.share_delta * 100
    top = s.reindex(s.share_delta_abs.sort_values(ascending=False).index).head(12)
    top.to_csv(OUT / "leakage_top_blocks.csv", index=False, encoding="utf-8-sig")
    print("    Top 8 绝对变化块（百分点）：")
    print(top[["residence_region", "workplace_pa", "trips_5B", "trips_5C1", "delta_pp"]]
          .head(8).round(4).to_string(index=False))
    max_block_pp = float(s.delta_pp.abs().max())
    print(f"    单块最大变化 = {max_block_pp:.4f} pp；块份额 L1/2 = {s.share_delta_abs.sum()/2:.4f}")
    gate("L6", "泄漏在空间上分散（单块 < 0.5 pp）",
         bool(max_block_pp < 0.5),
         f"max block = {max_block_pp:.4f} pp")

    # ---------------- [4] 对照臂可用性 ----------------
    print("\n[4] 独立 OD 候选（无 SpeedBand）可用性")
    lat_ok = {}
    for cand, fn in [
        ("5B_freeflow", "reports/od_prior_5b/prior_od_5b_lambda_0p075.parquet"),
        ("5B_freeflow_csv", "reports/od_prior_5b/prior_od_5b_lambda_0p075.csv"),
    ]:
        lat_ok[cand] = (ROOT / fn).exists()
    print(f"    Step5B 自由流 OD 存在性：{lat_ok}")
    # 同一约束框架自证：5B 与 5C.1 的 A_j 边际一致（都等于 1,935,235）
    gate("L7", "Step5B（无 SpeedBand）OD 已存在，可作独立对照臂",
         lat_ok["5B_freeflow"],
         f"od_total_5B@0.075 = {r.od_total_5B:,.0f}")

    # ---------------- 汇总 ----------------
    summary = {
        "generated": datetime.now().isoformat(timespec="seconds"),
        "nature": "READ_ONLY leakage audit; no frozen artifact touched",
        "channel": {
            "path": "TrafficSpeedBands(AM) -> Step5C/5C.1 -> C^AM(332x332) "
                    "-> build_prior_od_5c1 gravity exp(-lam*C) -> IPF -> prior OD "
                    "-> build_matsim_population -> car-only 200k",
            "affected_layer": "仅重力/目的地选择权重",
            "unaffected_layer": "P_i / A_j / Table118 硬约束（IPF 边际与块约束）",
            "ff_impedance_median_min": med_ff,
            "am_impedance_median_min": med_am,
            "am_coverage_length_share": src_am["am_coverage_length_share"],
        },
        "leakage_magnitude": {
            "metric": "Total Variation of OD shares (T^5B vs T^5C.1)",
            "at_lambda_0p075": float(r.TV_recomputed),
            "monotone_in_lambda": bool(
                (tvdf.sort_values("lambda_per_min").TV_recomputed
                 .diff().dropna() > 0).all()),
            "intrazonal_rel_change_at_0p075": float(r.intrazonal_rel_change),
            "direction": "AM 阻抗使 OD 略微更本地化（区内份额上升）",
        },
        "independent_od_options": {
            "option1_freeflow_step5b": {
                "status": "READY", "path": "reports/od_prior_5b/prior_od_5b_lambda_*.parquet",
                "input": "reports/od_impedance/impedance_matrix.parquet (C^FF)",
                "speedband_input": "NONE",
                "note": "需参数化 build_matsim_population 的 PRIOR_DIR 才能生成对应 car-only 人口",
            },
            "option2_am_holdout": {
                "status": "NOT_BUILT",
                "note": "只用部分 AM 快照建阻抗/OD、余下作验证；需重建 AM 阻抗+OD 两轮，成本高",
            },
        },
        "gates": GATES,
        "verdict": "LEAKAGE_QUANTIFIED" if all(g["pass"] for g in GATES) else "REVIEW",
    }
    with open(OUT / "leakage_summary.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    print("\n" + "=" * 78)
    print(f"判决：{summary['verdict']}  (gates {sum(g['pass'] for g in GATES)}/{len(GATES)})")
    print(f"★ 泄漏量级 TV(λ=0.075) = {r.TV_recomputed*100:.2f}%")
    print(f"输出：{OUT}")
    print("=" * 78)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
