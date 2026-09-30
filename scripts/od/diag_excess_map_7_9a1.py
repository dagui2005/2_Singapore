# -*- coding: utf-8 -*-
"""7.9A-1 补充（DIAGNOSTIC）：以**预注册主判据口径** `excess_s > 0` 绘制「哪里堵」的位置图。

**为什么必需**：预注册 §4.4-5 的正式图 `congestion_map_A1_HRS8-9.png` 用 `speed_ratio` 上色，
而 `speed_ratio < 1` 在 v1.0 下就有 **117,168 条（载流链的 52.2%）** —— 几乎全是
`LENGTH < 50 m` 短链的 `TT = ceil(FF)` **量化伪影**（见报告 §10 条目 6）⇒ 两幅图看起来**都"全红"**，
**无法回答"拥堵在哪"**。本图改用 `excess_s = TRAVELTIME8-9avg − ceil(ff)`（= 7.9A-1 主判据口径），
只画 `excess_s > 0` 的链路，并按 `excess_s` 上色/加粗。

⛔ 本件是**诊断补充**，不替换预注册产物、不改任何判据；命名带 `_DIAGNOSTIC` 以免混淆。
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(r"D:\Luan\2026-05\2_Singapore")
sys.path.insert(0, str(ROOT / "scripts" / "od"))

import audit_sampling_capacity_7_9a1 as A   # noqa: E402

OUT = A.OUT


def excess_of(d) -> float:
    if d["fs"] <= 0 or d["h89"] <= 0 or d["tt89"] <= 0:
        return 0.0
    return d["tt89"] - A.ceil_ff(d["length"] / d["fs"])


def main() -> int:
    t0 = time.time()
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.font_manager as mfont
    import matplotlib.pyplot as plt
    from matplotlib.collections import LineCollection
    from matplotlib.colors import LinearSegmentedColormap, LogNorm

    for f in [r"C:\Windows\Fonts\msyh.ttc", r"C:\Windows\Fonts\simhei.ttf"]:
        if Path(f).exists():
            try:
                mfont.fontManager.addfont(f)
            except Exception:
                pass
    plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False

    print("载入 linkstats / 网络标签 / 靶场 …", flush=True)
    L_v10 = A.load_linkstats(A.V10_LS)
    L_a1 = A.load_linkstats(A.A1_LS)
    labels = A.load_net_labels()
    xw = A.load_crosswalk_raw()
    tgt = set(A.target_anchor(xw)["links_primary_set"])
    print(f"  v1.0 {len(L_v10):,} / A-1 {len(L_a1):,} / 靶场链 {len(tgt):,}")

    nx = dict(zip(labels["node_ids"].tolist(), labels["node_x"].tolist()))
    ny = dict(zip(labels["node_ids"].tolist(), labels["node_y"].tolist()))
    pos = {lid: i for i, lid in enumerate(labels["ids"])}

    def segs(L, only_target=False):
        out, vals = [], []
        for k, d in L.items():
            ex = excess_of(d)
            if ex <= 0:
                continue
            if only_target and k not in tgt:
                continue
            i = pos.get(k)
            if i is None:
                continue
            f_, t_ = labels["frm"][i], labels["to"][i]
            if f_ not in nx or t_ not in nx:
                continue
            out.append([(nx[f_], ny[f_]), (nx[t_], ny[t_])])
            vals.append(ex)
        return out, np.array(vals, dtype=float)

    cmap = LinearSegmentedColormap.from_list("cong", ["#ffffb2", "#fecc5c", "#fd8d3c", "#f03b20", "#7f0000"])
    panels = [("v1.0（f_cap = 1.0）", L_v10, False),
              ("A-1（f_cap = 0.434977 = 1/SCALE）", L_a1, False),
              ("A-1 ∩ 7.3.6A 靶场链", L_a1, True)]

    rec = {"step": "7.9A-1/diagnostic-excess-map", "panels": {}}
    fig, axes = plt.subplots(1, 3, figsize=(30, 11))
    vmax = 60.0
    for ax, (ttl, L, ot) in zip(axes, panels):
        s, v = segs(L, ot)
        n_cong_all = sum(1 for d in L.values() if excess_of(d) > 0)
        km = sum(d["length"] for d in L.values() if excess_of(d) > 0) / 1000.0
        if ot:
            n_cong_all = sum(1 for k, d in L.items() if excess_of(d) > 0 and k in tgt)
            km = sum(d["length"] for k, d in L.items()
                     if excess_of(d) > 0 and k in tgt) / 1000.0
        rec["panels"][ttl] = {"n_cong": n_cong_all, "km_cong": km, "n_segments_drawn": len(s)}
        if s:
            lc = LineCollection(s, cmap=cmap, norm=LogNorm(vmin=1.0, vmax=vmax),
                                linewidths=np.clip(v / 8.0, 0.6, 3.2))
            lc.set_array(v)
            ax.add_collection(lc)
        tx = [nx[labels["frm"][pos[k]]] for k in list(tgt)[:4000]
              if k in pos and labels["frm"][pos[k]] in nx]
        ty = [ny[labels["frm"][pos[k]]] for k in list(tgt)[:4000]
              if k in pos and labels["frm"][pos[k]] in ny]
        if tx and not ot:
            ax.scatter(tx, ty, s=0.6, c="#333333", alpha=0.25, marker=".", label="7.3.6A 靶场链")
            ax.legend(fontsize=9, loc="upper left")
        ax.set_aspect("equal")
        ax.set_xlim(2000, 52000)
        ax.set_ylim(21000, 51500)
        ax.set_title(f"{ttl}\n拥堵链 {n_cong_all:,} 条 / {km:,.1f} km"
                     f"（仅画 excess_s > 0；线宽∝excess）", fontsize=13, loc="left")
        ax.set_xlabel("EPSG:3414 (m)")
        print(f"  [{ttl}] n_cong={n_cong_all:,} km={km:,.1f} drawn={len(s):,}")

    # A-1 与 v1.0 的差异摘要
    ex1 = {k: excess_of(d) for k, d in L_v10.items()}
    ex2 = {k: excess_of(d) for k, d in L_a1.items()}
    both = set(ex1) & set(ex2)
    dlt = {k: ex2[k] - ex1[k] for k in both}
    tot = sum(abs(v) for v in dlt.values())
    net = abs(sum(dlt.values()))
    rec["delta"] = {
        "n_common": len(both),
        "sum_excess_v10_s": sum(v for v in ex1.values() if v > 0),
        "sum_excess_a1_s": sum(v for v in ex2.values() if v > 0),
        "L1_over_L0_excess": (tot / net) if net > 0 else None,
        "n_excess_up": sum(1 for v in dlt.values() if v > 1.0),
        "n_excess_down": sum(1 for v in dlt.values() if v < -1.0),
        "n_target_cong_a1": sum(1 for k in tgt if ex2.get(k, 0) > 0),
        "n_target_cong_v10": sum(1 for k in tgt if ex1.get(k, 0) > 0),
    }
    print(f"  [Δexcess] L1/L0 = {rec['delta']['L1_over_L0_excess']:.4f}；"
          f"升 {rec['delta']['n_excess_up']:,} / 降 {rec['delta']['n_excess_down']:,}；"
          f"靶场拥堵链 v1.0 {rec['delta']['n_target_cong_v10']:,} → A-1 "
          f"{rec['delta']['n_target_cong_a1']:,}")

    sm = plt.cm.ScalarMappable(cmap=cmap, norm=LogNorm(vmin=1.0, vmax=vmax))
    sm.set_array([])
    cb = fig.colorbar(sm, ax=axes, fraction=0.015, pad=0.015)
    cb.set_label("excess_s = TRAVELTIME8-9avg − ceil(自由流行程时间)  [s]", fontsize=11)
    fig.suptitle("Step 7.9A-1 · 补充诊断：以预注册主判据口径（excess_s > 0）定位拥堵\n"
                 "Singapore_OD_MATSim · it.19 · EPSG:3414 · ⛔ 不替换预注册产物",
                 fontsize=15, y=0.99)
    p = OUT / "congestion_map_A1_excess_DIAGNOSTIC.png"
    fig.savefig(p, bbox_inches="tight", facecolor="white", dpi=130)
    plt.close(fig)
    rec["image"] = p.name
    rec["elapsed_s"] = round(time.time() - t0, 1)
    (OUT / "_diag_excess_map.json").write_text(
        json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n[out] {p}  （{rec['elapsed_s']} s）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
