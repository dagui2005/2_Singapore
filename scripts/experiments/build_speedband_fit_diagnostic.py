#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SpeedBand 拟合诊断（只读 · 分层全报 · 双口径 · 双时间窗）
==========================================================
用户裁定（2026-10-07）：拟合杠杆=仅先做诊断（不改模型）；观测域=分层全报；
指标=数值速度+band 一致性双口径；时间窗=08-09 与 07-10 并报。

链路（已核验）
--------------
  LTA SpeedBand LinkID
    -> reports/od_impedance_ampeak/lta_osm_ampeak_speed_match.csv 的 osm_edge_index
       (= reports/od_impedance/network_links.csv 行号)
    -> MATSim link id = f"e{from_node}_{to_node}"
  覆盖: 143,478 LTA 观测 -> 92,149 具名 MATSim 链 -> 91,956 (99.79%) 在仿真网络内。

口径
----
  观测 Obs : 工作日 07:00-09:59 共 12 快照，(MinSpeed+MaxSpeed)/2 按 LinkID 取中位
             SpeedBand 编码 (实测): 1:0-9 2:10-19 ... 7:60-69 8:70+(999 哨兵,代理75)
  仿真 Sim : sim_speed_kmh = LENGTH / TRAVELTIME{h}avg * 3.6
  时间窗   : W89  = HRS8-9avg
             W710 = mean( HRS7-8, HRS8-9, HRS9-10 )  (三个小时桶速度的简单均值)
  有效域   : 窗体 HRS*h*avg > 0 (该链在该小时有车通过)；HRS=0 时 MATSim 回填自由流时间,
             会给出假的"自由流速度",故必须剔除。

本脚本**只读**：不改 config/网络/需求/评价器/原始观测。
"""
from __future__ import annotations
import gzip
import json
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(r"D:\Luan\2026-05\2_Singapore")
OUT = ROOT / "reports" / "speedband_fit_diagnostic"

NETWORK_LINKS = ROOT / "reports/od_impedance/network_links.csv"
SB_MATCH = ROOT / "reports/od_impedance_ampeak/lta_osm_ampeak_speed_match.csv"

RUNS = {
    "v1.0_frozen": ROOT / "matsim_final_7_6h/outputs/W01_rc_min/ITERS/it.19/W01_rc_min.19.linkstats.txt.gz",
    "E-CAP-01": ROOT / "experiments/E-CAP-01_scale_capacity/outputs/E-CAP-01/ITERS/it.19/E-CAP-01.19.linkstats.txt.gz",
}
PRIMARY = "v1.0_frozen"
LEAD_RUNS = ["v1.0_frozen", "E-CAP-01"]

WANT = ["LINK", "LENGTH", "FREESPEED", "CAPACITY",
        "HRS7-8avg", "HRS8-9avg", "HRS9-10avg",
        "TRAVELTIME7-8avg", "TRAVELTIME8-9avg", "TRAVELTIME9-10avg"]

# 道路等级排序（展示用）
HW_ORDER = ["motorway", "motorway_link", "trunk", "trunk_link",
            "primary", "primary_link", "secondary", "secondary_link",
            "tertiary", "tertiary_link", "residential", "service",
            "unclassified", "living_street", "road", "other", "nan"]


def band_of_speed(v) -> np.ndarray:
    v = np.asarray(v, dtype=float)
    b = np.clip(np.floor(v / 10.0) + 1.0, 1, 8)
    return b.astype(int)


def load_linkstats(path: Path) -> pd.DataFrame:
    return pd.read_csv(path, sep="\t", compression="gzip", usecols=WANT,
                       dtype={"LINK": str}, low_memory=False)


def build_obs() -> pd.DataFrame:
    net = pd.read_csv(NETWORK_LINKS, encoding="utf-8-sig", low_memory=False,
                      usecols=["from_node", "to_node", "length_m", "highway", "name"])
    m = pd.read_csv(SB_MATCH, encoding="utf-8-sig")
    idx = m.osm_edge_index.to_numpy(int)
    m = m.assign(
        matsim_link=["e%d_%d" % (a, b) for a, b in
                     zip(net.from_node.to_numpy(int)[idx], net.to_node.to_numpy(int)[idx])],
        net_length_m=net.length_m.to_numpy(float)[idx],
        highway=net.highway.astype(str).str.lower().str.strip().to_numpy()[idx],
        road_name=net.name.astype(str).to_numpy()[idx],
    )
    obs = (m.groupby("matsim_link", as_index=False)
             .agg(obs_speed_kmh=("am_speed_kmh", "median"),
                  n_lta=("LinkID", "size"),
                  highway=("highway", "first"),
                  road_name=("road_name", "first"),
                  net_length_m=("net_length_m", "median")))
    obs["obs_band"] = band_of_speed(obs.obs_speed_kmh)
    return obs


def window_sim_speed(d: pd.DataFrame, cols) -> np.ndarray:
    """cols: list of TRAVELTIME*h*avg column(s); 取每桶速度再简单均值。"""
    speeds = []
    ln = d["LENGTH"].to_numpy(float)
    for c in cols:
        tt = d[c].to_numpy(float)
        s = np.full(len(d), np.nan)
        ok = np.isfinite(tt) & (tt > 0) & np.isfinite(ln)
        s[ok] = ln[ok] / tt[ok] * 3.6
        speeds.append(s)
    return np.nanmean(np.vstack(speeds), axis=0)


def metrics(x: pd.DataFrame, sim_col: str) -> dict:
    o = x.obs_speed_kmh.to_numpy(float)
    s = x[sim_col].to_numpy(float)
    e = s - o
    ob = band_of_speed(o)
    sb = band_of_speed(s)
    be = sb - ob
    # Spearman（无 scipy 时用秩相关近似）
    try:
        from scipy.stats import spearmanr
        rho = float(spearmanr(o, s).statistic)
    except Exception:
        rho = float("nan")
    # shuffle 负例：打乱 sim 与 obs 的配对
    rng = np.random.default_rng(20261007)
    s_sh = rng.permutation(s)
    r_sh = float(np.corrcoef(o, s_sh)[0, 1])
    return {
        "n": int(len(x)),
        "obs_mean_kmh": float(np.mean(o)),
        "sim_mean_kmh": float(np.mean(s)),
        "bias_kmh": float(np.mean(e)),
        "MAE_kmh": float(np.mean(np.abs(e))),
        "RMSE_kmh": float(np.sqrt(np.mean(e ** 2))),
        "pearson_r": float(np.corrcoef(o, s)[0, 1]) if len(x) > 2 else float("nan"),
        "spearman_rho": rho,
        "shuffle_r_negctrl": r_sh,
        "speed_ratio_median": float(np.median(s / o)),
        "band_exact_pct": float((be == 0).mean() * 100),
        "band_within1_pct": float((np.abs(be) <= 1).mean() * 100),
        "band_bias": float(be.mean()),
        "band_MAE": float(np.mean(np.abs(be))),
        "obs_band_mean": float(ob.mean()),
        "sim_band_mean": float(sb.mean()),
        "sim_slower_share": float((e < 0).mean()),
        "sim_saturated_n": int((s < 5).sum()),
        "sim_near_ff_share": float((s >= 0.9 * x.FREESPEED.to_numpy(float) * 3.6).mean()),
        "length_km": float(x.net_length_m.sum() / 1000.0),
    }


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    obs = build_obs()
    print(f"[obs] SpeedBand 覆盖 MATSim 链路: {len(obs):,}")

    summary = {
        "linkage": {
            "lta_observations": int(len(pd.read_csv(SB_MATCH, encoding="utf-8-sig", usecols=["LinkID"]))),
            "matsim_links_from_speedband": int(len(obs)),
        },
        "runs": {}, "windows": {"W89": "HRS8-9avg", "W710": "mean(HRS7-8,8-9,9-10)"},
    }

    rows_overall, rows_hw = [], []
    perlink_out = None

    for name in LEAD_RUNS:
        p = RUNS.get(name)
        if not p or not p.exists():
            print(f"[WARN] 缺 linkstats: {p}")
            continue
        ls = load_linkstats(p)
        d = obs.merge(ls, left_on="matsim_link", right_on="LINK", how="inner")
        d["sim_W89"] = window_sim_speed(d, ["TRAVELTIME8-9avg"])
        d["sim_W710"] = window_sim_speed(d, ["TRAVELTIME7-8avg", "TRAVELTIME8-9avg", "TRAVELTIME9-10avg"])
        d["has_flow_89"] = d["HRS8-9avg"].fillna(0) > 0
        d["has_flow_710"] = (d[["HRS7-8avg", "HRS8-9avg", "HRS9-10avg"]]
                             .fillna(0).sum(axis=1) > 0)
        d["ff_speed_kmh"] = d.FREESPEED.to_numpy(float) * 3.6

        summary["runs"][name] = {
            "matched_in_network": int(len(d)),
            "with_flow_89": int(d.has_flow_89.sum()),
            "with_flow_710": int(d.has_flow_710.sum()),
            "flow_coverage_89_pct": float(d.has_flow_89.mean() * 100),
        }

        for win, col, flowcol in [("W89", "sim_W89", "has_flow_89"),
                                  ("W710", "sim_W710", "has_flow_710")]:
            v = d[d[flowcol] & d[col].notna()].copy()
            st = metrics(v, col)
            st.update({"run": name, "window": win})
            rows_overall.append(st)
            for hw, g in v.groupby("highway"):
                r = metrics(g, col)
                r.update({"run": name, "window": win, "highway": hw})
                rows_hw.append(r)
            if name == PRIMARY and win == "W89":
                perlink_out = v.assign(window=win, run=name)
            print(f"[{name}/{win}] n={st['n']:,} bias={st['bias_kmh']:+.2f} "
                  f"MAE={st['MAE_kmh']:.2f} r={st['pearson_r']:.3f} "
                  f"band_exact={st['band_exact_pct']:.1f}%")

    ov = pd.DataFrame(rows_overall)
    hw = pd.DataFrame(rows_hw)
    # 排序
    hw["hw_rank"] = hw.highway.map({h: i for i, h in enumerate(HW_ORDER)}).fillna(99)
    hw = hw.sort_values(["window", "run", "hw_rank"]).drop(columns="hw_rank")

    ov.to_csv(OUT / "speedband_fit_overall.csv", index=False, encoding="utf-8-sig")
    hw.to_csv(OUT / "speedband_fit_by_highway.csv", index=False, encoding="utf-8-sig")
    if perlink_out is not None:
        cols = ["matsim_link", "road_name", "highway", "net_length_m",
                "obs_speed_kmh", "obs_band", "sim_W89", "ff_speed_kmh",
                "HRS8-9avg", "HRS7-8avg", "HRS9-10avg"]
        perlink_out[cols].to_csv(OUT / "speedband_fit_perlink_v1.0_W89.csv",
                                 index=False, encoding="utf-8-sig")

    # ---- 按观测档看仿真（关键：仿真是否在"观测说堵"处也堵） ----
    rows_ob = []
    for name in LEAD_RUNS:
        p = RUNS.get(name)
        if not p or not p.exists():
            continue
        ls = load_linkstats(p)
        d = obs.merge(ls, left_on="matsim_link", right_on="LINK", how="inner")
        d["sim_W89"] = window_sim_speed(d, ["TRAVELTIME8-9avg"])
        d["ff_speed_kmh"] = d.FREESPEED.to_numpy(float) * 3.6
        v = d[(d["HRS8-9avg"].fillna(0) > 0) & d.sim_W89.notna()].copy()
        for ob, g in v.groupby("obs_band"):
            s = g.sim_W89.to_numpy(float)
            rows_ob.append({
                "run": name, "obs_band": int(ob), "obs_range_kmh": f"{(ob-1)*10}-{ob*10-1}",
                "n": int(len(g)),
                "obs_mid_kmh": float(((ob - 1) * 10 + ob * 10 - 1) / 2),
                "sim_mean_kmh": float(np.mean(s)),
                "sim_mean_band": float(band_of_speed(s).mean()),
                "sim_near_ff_share": float((s >= 0.9 * g.ff_speed_kmh.to_numpy(float)).mean()),
                "sim_below25_share": float((s < 25).mean()),
            })
    obdf = pd.DataFrame(rows_ob)
    obdf.to_csv(OUT / "speedband_fit_by_obsband.csv", index=False, encoding="utf-8-sig")
    summary["by_obs_band"] = obdf.to_dict("records")

    with open(OUT / "speedband_fit_summary.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    _figures(ov, hw, perlink_out, obdf)
    print(f"\n落盘: {OUT}")


def _figures(ov, hw, perlink, obdf):
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except Exception as exc:
        print(f"[WARN] matplotlib 不可用: {exc}")
        return
    plt.rcParams["font.family"] = ["Microsoft YaHei", "SimHei", "DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False

    # ---- fig1: 分等级 obs vs sim 均值（W89, v1.0） ----
    h = hw[(hw.run == "v1.0_frozen") & (hw.window == "W89")].copy()
    h = h.sort_values("n", ascending=False).head(12)
    fig, ax = plt.subplots(figsize=(11, 5.2))
    y = np.arange(len(h)); w = 0.38
    ax.barh(y - w / 2, h.obs_mean_kmh, w, label="观测 SpeedBand", color="#4C78A8")
    ax.barh(y + w / 2, h.sim_mean_kmh, w, label="仿真 MATSim", color="#F58518")
    ax.set_yticks(y); ax.set_yticklabels([f"{a}  (n={b:,})" for a, b in zip(h.highway, h.n)])
    ax.invert_yaxis(); ax.set_xlabel("路段平均速度 (km/h)")
    ax.set_title("SpeedBand 拟合诊断 · 分道路等级 · v1.0 冻结模型 · 08–09")
    ax.legend(); ax.grid(axis="x", alpha=.3)
    for i, (o, s) in enumerate(zip(h.obs_mean_kmh, h.sim_mean_kmh)):
        ax.text(max(o, s) + 1, i, f"{s - o:+.1f}", va="center", fontsize=8,
                color="#C00" if s - o > 0 else "#0A0")
    fig.tight_layout(); fig.savefig(OUT / "fig_sb_by_highway.png", dpi=150); plt.close(fig)

    # ---- fig2: obs vs sim 散点（W89, v1.0） ----
    if perlink is not None:
        v = perlink.dropna(subset=["sim_W89"])
        fig, ax = plt.subplots(figsize=(6.2, 6.2))
        hb = ax.hexbin(v.obs_speed_kmh, v.sim_W89, gridsize=45, bins="log", cmap="viridis", mincnt=1)
        lim = [0, max(v.obs_speed_kmh.max(), v.sim_W89.max()) * 1.02]
        ax.plot(lim, lim, "r--", lw=1.2, label="y = x")
        ax.set_xlim(lim); ax.set_ylim(lim)
        ax.set_xlabel("观测速度 (km/h)"); ax.set_ylabel("仿真速度 (km/h)")
        ax.set_title("SpeedBand 拟合诊断 · 逐链路 · v1.0 · 08–09")
        fig.colorbar(hb, label="链路数(log)"); ax.legend()
        fig.tight_layout(); fig.savefig(OUT / "fig_sb_scatter.png", dpi=150); plt.close(fig)

        # ---- fig3: band 混淆矩阵 ----
        ob = band_of_speed(v.obs_speed_kmh.to_numpy())
        sb = band_of_speed(v.sim_W89.to_numpy())
        M = np.zeros((8, 8), dtype=int)
        for a, b in zip(ob, sb):
            M[a - 1, b - 1] += 1
        Mp = M / M.sum() * 100
        fig, ax = plt.subplots(figsize=(7, 6))
        im = ax.imshow(Mp, cmap="magma_r", vmin=0, vmax=np.percentile(Mp[Mp > 0], 98))
        for i in range(8):
            for j in range(8):
                if Mp[i, j] >= 0.05:
                    ax.text(j, i, f"{Mp[i, j]:.1f}", ha="center", va="center",
                            fontsize=7.5, color="white" if Mp[i, j] > Mp.max() * .5 else "black")
        ax.set_xticks(range(8)); ax.set_yticks(range(8))
        ax.set_xticklabels([f"{b}" for b in range(1, 9)])
        ax.set_yticklabels([f"{b}" for b in range(1, 9)])
        ax.set_xlabel("仿真 SpeedBand"); ax.set_ylabel("观测 SpeedBand")
        ax.set_title("SpeedBand 混淆矩阵 (%链路) · v1.0 · 08–09")
        fig.colorbar(im, label="%链路")
        fig.tight_layout(); fig.savefig(OUT / "fig_sb_band_confusion.png", dpi=150); plt.close(fig)

    print("[fig] fig_sb_by_highway / fig_sb_scatter / fig_sb_band_confusion")

    # ---- fig4: 按观测档看仿真速度 ----
    if obdf is not None and len(obdf):
        o = obdf[obdf.run == "v1.0_frozen"].sort_values("obs_band")
        fig, ax = plt.subplots(figsize=(9.2, 5))
        x = np.arange(len(o))
        ax.bar(x - 0.2, o.obs_mid_kmh, 0.4, label="观测档中点", color="#4C78A8")
        ax.bar(x + 0.2, o.sim_mean_kmh, 0.4, label="仿真均值", color="#F58518")
        for i, (s, n) in enumerate(zip(o.sim_mean_kmh, o.n)):
            ax.text(i, s + 1, f"n={n:,}", ha="center", fontsize=7)
        ax.set_xticks(x)
        ax.set_xticklabels([f"SB{b}\n{r}" for b, r in zip(o.obs_band, o.obs_range_kmh)])
        ax.set_xlabel("观测 SpeedBand 档（1=最堵 8=畅通）")
        ax.set_ylabel("速度 (km/h)")
        ax.set_title("按观测拥堵档看仿真速度 · v1.0 · 08–09  (仿真把拥堵档整体抬高 ~1–2 档)")
        ax.legend(); ax.grid(axis="y", alpha=.3)
        fig.tight_layout(); fig.savefig(OUT / "fig_sb_by_obsband.png", dpi=150); plt.close(fig)
        print("[fig] fig_sb_by_obsband")


if __name__ == "__main__":
    main()
