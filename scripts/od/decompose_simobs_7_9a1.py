# -*- coding: utf-8 -*-
"""7.9A-1 机制分解：`Sim/Obs` 由 0.9993 → 0.7665 的**成因**（逐断面，零仿真 / 只读）。

回答一个问题：A-1 的断面池化流量下降 23.3%，是
  (a) **近似均匀的整体缩放**（则 ~ 全断面同等变稀），还是
  (b) **空间重分配**（主干道掉、支路涨，正负抵消后净值下降）？

判别量：`L1/L0 = Σ|Δ_sim| / |ΣΔ_sim|`
  - ≈ 1.0  ⇒ 近乎单向缩放（(a)）
  - >> 1.0 ⇒ 大量正负抵消（(b)）

⛔ 本脚本**不**写任何冻结产物、**不**改任何口径；只做只读分解 + 落一份 JSON 留痕。
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(r"D:\Luan\2026-05\2_Singapore")
sys.path.insert(0, str(ROOT / "scripts" / "od"))

import audit_sampling_capacity_7_9a1 as A          # noqa: E402
from audit_sampling_capacity_7_9a1 import (         # noqa: E402
    A1_OUT, A1_RUN, CYCLE_DIR, N_SIM, OUT, SCALE, V10_OUT, V10_RUN,
)

E = A.E

RUN_V1 = {"label": "V1", "role": "frozen_v1_0_queue", "lambda": 0.075,
          "f_demand": 1.180222, "N": N_SIM, "out_dir": V10_OUT, "run_id": V10_RUN,
          "stage": "7.6H", "desc": "v1.0 冻结（queue, f_cap=1.0）"}
RUN_A1 = {"label": "A1", "role": "sampling_capacity_1overSCALE", "lambda": 0.075,
          "f_demand": 1.180222, "N": N_SIM, "out_dir": A1_OUT, "run_id": A1_RUN,
          "stage": "7.9A-1", "desc": "7.9A-1（queue, f_cap=0.434977）"}


def quant(x, ps=(0.05, 0.25, 0.5, 0.75, 0.95)):
    x = np.asarray([v for v in x if np.isfinite(v)], dtype=float)
    if x.size == 0:
        return {}
    return {f"P{int(p*100)}": float(np.quantile(x, p)) for p in ps}


def main() -> int:
    t0 = time.time()
    print("=" * 92)
    print("7.9A-1 机制分解 —— 断面池化 Sim/Obs 下降的成因（零仿真 / 只读）")
    print("=" * 92)

    xw = A.load_crosswalk_raw()
    ctx = A.guardrail_ctx(xw)
    E.OUT = OUT
    E.CYCLE_DIR = CYCLE_DIR

    out = {"step": "7.9A-1/decompose", "note": "diagnostic only, read-only"}

    for tag, run in (("v1.0", RUN_V1), ("A-1", RUN_A1)):
        print(f"\n[{tag}] eval_run（冻结模块，cycle linkstats 走磁盘缓存）…", flush=True)
        r = E.eval_run(run, ctx["cw_n"], ctx["cw_prim"], ctx["obs_df"], ctx["geo"],
                       ctx["matched"], ctx["cata"], ctx["slip"], force_cycle=False)
        out[tag] = r
    r1, r2 = out["v1.0"], out["A-1"]

    s1, s2 = r1["sec"].copy(), r2["sec"].copy()
    print("\n[cols] sec 列 =", list(s1.columns))

    for s in (s1, s2):
        s["lta_linkid"] = s["lta_linkid"].astype(str).str.strip()
    m = s1.merge(s2, on="lta_linkid", suffixes=("_v10", "_a1"), how="inner")
    print(f"[merge] 断面数 v1.0={len(s1)}  A-1={len(s2)}  内连接={len(m)}")

    sim1 = m["sim_8_9_scaled_v10"].astype(float).to_numpy()
    sim2 = m["sim_8_9_scaled_a1"].astype(float).to_numpy()
    obs = m["obs_8_9_v10"].astype(float).to_numpy()
    d = sim2 - sim1

    S1, S2, O = float(sim1.sum()), float(sim2.sum()), float(obs.sum())
    L1, L0 = float(np.abs(d).sum()), abs(float(d.sum()))
    rec = {
        "n_sections": int(len(m)),
        "sum_sim_v10": S1, "sum_sim_a1": S2, "sum_obs": O,
        "pooled_v10": S1 / O, "pooled_a1": S2 / O,
        "delta_sum": float(d.sum()), "delta_rel": float(d.sum() / S1),
        "L1_abs_sum": L1, "L0_abs_net": L0,
        "L1_over_L0": (L1 / L0) if L0 > 0 else float("inf"),
        "n_down": int((d < 0).sum()), "n_up": int((d > 0).sum()), "n_flat": int((d == 0).sum()),
        "obs_weighted_down_share": float(obs[d < 0].sum() / O) if O else float("nan"),
        "obs_weighted_up_share": float(obs[d > 0].sum() / O) if O else float("nan"),
        "ratio_v10_q": quant(sim1 / np.where(obs > 0, obs, np.nan)),
        "ratio_a1_q": quant(sim2 / np.where(obs > 0, obs, np.nan)),
        "delta_q": quant(d),
    }

    print("\n" + "-" * 92)
    print("[A] 池化口径")
    print(f"    Σsim   v1.0 = {S1:,.1f}  →  A-1 = {S2:,.1f}   （{100*(S2/S1-1):+.4f} %）")
    print(f"    Σobs   = {O:,.1f}（冻结，两版相同）")
    print(f"    Sim/Obs  v1.0 = {S1/O:.7f}  →  A-1 = {S2/O:.7f}")
    print("\n[B] ★核心判别量：L1 / L0")
    print(f"    Σ|Δ| = {L1:,.1f}      |ΣΔ| = {L0:,.1f}")
    print(f"    L1/L0 = {rec['L1_over_L0']:.4f}   "
          f"（≈1 ⇒ 单向缩放；>>1 ⇒ 正负抵消的空间重分配）")
    print(f"    降的断面 {rec['n_down']} / 升的 {rec['n_up']} / 持平 {rec['n_flat']}"
          f"（共 {rec['n_sections']}）")
    print(f"    按 obs 加权：降的断面担 Σobs 的 {100*rec['obs_weighted_down_share']:.2f} %、"
          f"升的担 {100*rec['obs_weighted_up_share']:.2f} %")
    print("\n[C] 逐断面前后比（sim/obs）分位")
    print(f"    v1.0: {rec['ratio_v10_q']}")
    print(f"    A-1 : {rec['ratio_a1_q']}")

    # 按 RoadCat
    cat_col = "RoadCat_v10" if "RoadCat_v10" in m.columns else (
        "RoadCat" if "RoadCat" in m.columns else None)
    if cat_col:
        m["_d"] = d
        g = m.groupby(cat_col).apply(
            lambda t: pd.Series({"n": len(t), "sum_sim_v10": t["sim_8_9_scaled_v10"].sum(),
                                 "sum_sim_a1": t["sim_8_9_scaled_a1"].sum(),
                                 "sum_obs": t["obs_8_9_v10"].sum(), "delta": t["_d"].sum()}),
            include_groups=False).reset_index()
        g["ratio_v10"] = g["sum_sim_v10"] / g["sum_obs"]
        g["ratio_a1"] = g["sum_sim_a1"] / g["sum_obs"]
        print("\n[D] 按 RoadCat 分组")
        print(g.to_string(index=False))
        rec["by_roadcat"] = g.to_dict("records")

    # top-20 绝对变化
    top = m.assign(_d=d).reindex(m.assign(_d=d)["_d"].abs().sort_values(ascending=False).index).head(20)
    keep = [c for c in ("lta_linkid", "RoadName_v10", "RoadCat_v10", "obs_8_9_v10",
                        "sim_8_9_scaled_v10", "sim_8_9_scaled_a1", "_d") if c in top.columns]
    print("\n[E] |Δ| 最大的 20 个断面")
    print(top[keep].to_string(index=False))

    rec["elapsed_s"] = round(time.time() - t0, 1)
    p = OUT / "_decompose_simobs_a1.json"
    p.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n[out] {p}  （{rec['elapsed_s']} s）")
    print("=" * 92)
    return 0


if __name__ == "__main__":
    sys.exit(main())
