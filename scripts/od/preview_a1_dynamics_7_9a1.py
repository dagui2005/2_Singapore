# -*- coding: utf-8 -*-
"""
preview_a1_dynamics_7_9a1.py —— 等待正式评价期间，用 legHistogram 出「人眼可读」的动态画像

回应用户要求：判据不能只有 Sim/Obs、Pearson、RMSE，必须增加
  ① 拥堵链路数量  ② v/c ≥ 1 的链路数量  ③ 拥堵持续时间/排队形成与消散
  ④ 拥堵空间位置
本脚本只做 ③ 的**独立、可读**侧写（与评价器 events 口径互为交叉验证），
读 v1.0 与 A-1 的 `it.19.legHistogram.txt`（5 分钟 bin，全天）。

legHistogram 列（★首两列同名 time，须按位置/序号解析）：
  0,1=time  2=departures_all  3=arrivals_all  4=stuck_all  5=en-route_all
  6=departures_car  7=arrivals_car  8=stuck_car  9=en-route_car

输出：reports/sampling_capacity_7_9a1/_preview_a1_dynamics.json
"""
from __future__ import annotations

import json
import time
from pathlib import Path

ROOT = Path(r"D:\Luan\2026-05\2_Singapore")
OUT = ROOT / "reports" / "sampling_capacity_7_9a1" / "_preview_a1_dynamics.json"

RUNS = {
    "v1.0": (ROOT / "matsim_final_7_6h" / "outputs" / "W01_rc_min" / "ITERS" / "it.19"
             / "W01_rc_min.19.legHistogram.txt"),
    "A-1": (ROOT / "matsim_sampling_capacity_7_9a1" / "outputs" / "A1_capf0p435"
            / "ITERS" / "it.19" / "A1_capf0p435.19.legHistogram.txt"),
}
# it.19 linkstats 用于并列流量面
LS_RUNS = {
    "v1.0": (RUNS["v1.0"].parent / "W01_rc_min.19.linkstats.txt.gz"),
    "A-1": (RUNS["A-1"].parent / "A1_capf0p435.19.linkstats.txt.gz"),
}


def hms(sec: float) -> str:
    s = int(round(sec))
    return f"{s // 3600:02d}:{(s % 3600) // 60:02d}:{s % 60:02d}"


def read_hist(p: Path) -> dict:
    rows = []
    with p.open("r", encoding="utf-8", errors="replace") as fh:
        head = fh.readline().rstrip("\n").split("\t")
        for line in fh:
            tk = line.rstrip("\n").split("\t")
            if len(tk) < 10:
                continue
            try:
                # ★列 0 = "HH:MM:SS" 字符串；列 1 = 秒数
                rows.append({"t": float(tk[1]), "dep": float(tk[2]), "arr": float(tk[3]),
                             "stuck": float(tk[4]), "enroute": float(tk[5]),
                             "dep_car": float(tk[6]), "arr_car": float(tk[7]),
                             "stuck_car": float(tk[8]), "enroute_car": float(tk[9])})
            except ValueError:
                continue
    return {"header": head, "rows": rows}


def profile(h: dict) -> dict:
    rows = h["rows"]
    if not rows:
        return {}
    peak = max(rows, key=lambda r: r["enroute"])
    stuck_peak = max(rows, key=lambda r: r["stuck"])
    tot_dep = sum(r["dep"] for r in rows)
    tot_arr = sum(r["arr"] for r in rows)
    # 队列形成 / 消散：en-route 首次 >= 50% 峰、末次 >= 50% 峰
    thr = 0.5 * peak["enroute"]
    above = [r for r in rows if r["enroute"] >= thr]
    onset = above[0]["t"] if above else None
    clear = above[-1]["t"] if above else None
    dur_h = (clear - onset) / 3600.0 if (onset is not None and clear is not None) else None
    # 出发时刻形状（07-08 / 08-09）
    d78 = sum(r["dep"] for r in rows if 7 * 3600 <= r["t"] < 8 * 3600)
    d89 = sum(r["dep"] for r in rows if 8 * 3600 <= r["t"] < 9 * 3600)
    return {
        "n_bins": len(rows),
        "sum_dep": tot_dep, "sum_arr": tot_arr,
        "peak_enroute": peak["enroute"], "peak_enroute_t": peak["t"],
        "peak_enroute_hms": hms(peak["t"]),
        "stuck_peak": stuck_peak["stuck"], "stuck_peak_hms": hms(stuck_peak["t"]),
        "enroute_ge_50pct_onset_hms": hms(onset) if onset is not None else None,
        "enroute_ge_50pct_clear_hms": hms(clear) if clear is not None else None,
        "enroute_ge_50pct_duration_h": dur_h,
        "dep_07_08": d78, "dep_08_09": d89,
        "share_dep_07_08": (d78 / tot_dep) if tot_dep else None,
        "share_dep_08_09": (d89 / tot_dep) if tot_dep else None,
    }


def read_ls_congestion(p: Path, cap_mul: float) -> dict:
    """it.19 linkstats：读 LENGTH/HRS8-9avg/CAPACITY ⇒ 饱和里程、n(v/c>=1)。"""
    import gzip
    n = 0
    loaded = 0
    km_all = 0.0
    km_sat = 0.0
    n_vc_ge1 = 0
    n_len_ge50 = 0
    n_short = 0
    with gzip.open(p, "rt", encoding="utf-8", newline="") as fh:
        hdr = fh.readline().rstrip("\n").split("\t")
        i_len, i_cap, i_h89 = hdr.index("LENGTH"), hdr.index("CAPACITY"), hdr.index("HRS8-9avg")
        for line in fh:
            tk = line.split("\t")
            if len(tk) <= i_h89:
                continue
            n += 1
            L = float(tk[i_len]); C = float(tk[i_cap]); F = float(tk[i_h89])
            km_all += L / 1000.0
            if F > 0:
                loaded += 1
            if L < 50.0:
                n_short += 1
            else:
                n_len_ge50 += 1
            ce = C * cap_mul
            if ce > 0 and F >= ce:
                n_vc_ge1 += 1
                km_sat += L / 1000.0
    return {"n_links": n, "n_loaded": loaded, "km_all": km_all, "km_saturated": km_sat,
            "share_len_saturated_pct": 100.0 * km_sat / km_all if km_all else None,
            "n_vc_ge_1": n_vc_ge1, "n_len_ge_50m": n_len_ge50, "n_len_lt_50m": n_short}


def main() -> int:
    t0 = time.time()
    res = {"generated_at": time.strftime("%Y-%m-%d %H:%M:%S"), "runs": {}}
    print("=" * 84)
    print("A-1 动态画像侧写（legHistogram 口径，it.19 全天）")
    print("=" * 84)
    hdr_shown = False
    for tag, p in RUNS.items():
        if not p.exists():
            print(f"  [MISS] {tag}: {p}")
            continue
        h = read_hist(p)
        if not hdr_shown:
            print(f"  legHistogram 表头 = {h['header']}")
            hdr_shown = True
        pr = profile(h)
        ls = read_ls_congestion(LS_RUNS[tag], 1.0 if tag == "v1.0" else 0.434977)
        res["runs"][tag] = {"legHistogram": pr, "linkstats": ls, "path": p.name}
        print(f"\n[{tag}]  {p.name}")
        print(f"  出发 {pr['sum_dep']:,.0f} / 到达 {pr['sum_arr']:,.0f} / "
              f"峰 stuck {pr['stuck_peak']:.0f} @{pr['stuck_peak_hms']}")
        print(f"  在网峰 = {pr['peak_enroute']:,.0f} @{pr['peak_enroute_hms']}")
        print(f"  排队形成→消散（en-route≥50%峰）: {pr['enroute_ge_50pct_onset_hms']}"
              f" → {pr['enroute_ge_50pct_clear_hms']}  持续 {pr['enroute_ge_50pct_duration_h']:.2f} h")
        print(f"  出发分布 07-08 = {pr['share_dep_07_08']*100:.2f}% / "
              f"08-09 = {pr['share_dep_08_09']*100:.2f}%")
        print(f"  链路 {ls['n_links']:,}（有流 {ls['n_loaded']:,}）| "
              f"n(v/c≥1) = {ls['n_vc_ge_1']:,} | 饱和里程 {ls['km_saturated']:,.4f} km "
              f"= {ls['share_len_saturated_pct']:.5f}% of {ls['km_all']:,.1f} km")
    OUT.write_text(json.dumps(res, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n落盘 {OUT.name} ({OUT.stat().st_size:,} B)  耗时 {time.time()-t0:.1f} s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
