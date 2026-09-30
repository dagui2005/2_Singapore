# -*- coding: utf-8 -*-
"""Step 7.9H · 拥堵可视化重建（弃用 `speed_ratio` 直接着色）

背景（领导反馈：VIA 画面「看起来不像真实城市交通」）
--------------------------------------------------
既有正式图用 `speed_ratio = v / free_speed` 上色，而 v1.0 下 `speed_ratio < 1` 的链路有
**117,168 条（载流链 52.2%）**，其中 99% 是 `LENGTH < 50 m` 短链的 `TT = ceil(FF)`
**量化伪影**（11 m 链 ff=0.79 s 被记为 1 s ⇒ `speed_ratio` 掉到 0.40）。
⇒ 「正常速度折损 / 稍慢 / 真拥堵」被染成同一档，**图上全是红，无法回答"哪里堵"**。
**这不是"全城拥堵"，是仪器坏了。**

本脚本产出 5 张可直接给领导看的图（v1.0 / A-1 双版对照），**不改任何判据、不重跑仿真**：

  F1 `fig_why_speedratio_fails_*.png`     2×2：旧指标 vs 新指标 ⇒ 证明"全红"是仪器问题
  F2 `congestion_map_vc_5bin_*.png`       方案 A：`v/c` 五档（"这条路是否接近容量？"）
  F3 `congestion_map_delay_*.png`         主图：`delay = TT − FF`（过滤 len≥50 m 且 vol>0）
  F4 `congestion_map_ttratio_major_*.png` 辅助图：`TT_ratio` 仅干道（排除 service/connector）
  F5 `congestion_corridors_*.png`         方案 C：拥堵事件 + 连续相邻合并成**拥堵走廊**

口径（全部显式，可复算）
--------------------------------------------------
  ff         = LENGTH / FREESPEED（**原始**，非 ceil）
  ff_ceil    = max(1, ceil(ff − 1e-9))            ← 量化基线（`timeStepSize = 1 s`）
  speed_ratio= ff / TRAVELTIME8-9avg              ← canonical（= VIA TSV `speed_ratio_0809`）
  TT_ratio   = TRAVELTIME8-9avg / ff              ← 即 1 / speed_ratio
  delay      = TRAVELTIME8-9avg − ff              ← 主图（只画 delay ≥ 1 s）
  vc         = HRS8-9avg / (CAPACITY × cap_mul)   ← cap_mul: v1.0 = 1.0 / A-1 = 0.434977
  MAJOR      = motorway(_link) / trunk(_link) / primary(_link) / secondary(_link)

拥堵事件（方案 C）：`len ≥ 50 m` 且 `vol > 0`
  严格档 = `vc ≥ 0.85` 且 `speed_ratio < 0.70`（= 速度低于自由流 30%）
  宽松档 = `vc ≥ 0.60` 且 `speed_ratio < 0.75`（仅用于可读的展示图）
拥堵走廊：按**最小转角**（≤55°）把连续相邻的拥堵链串成长链，保留 ≥ `CORR_MIN_KM`。
持续时间：linkstats 逐小时 `TRAVELTIMEh-h+1avg` / `HRSh-h+1avg` ⇒ **小时级**下界
          （`hours_cong` = 整点满足 `speed_ratio < 0.70` 的点数；≥1 即 ≈ ≥5 min，方向保守）。
"""
from __future__ import annotations

import csv
import gzip
import json
import math
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(r"D:\Luan\2026-05\2_Singapore")
sys.path.insert(0, str(ROOT / "scripts" / "od"))

import audit_sampling_capacity_7_9a1 as A   # noqa: E402

OUT = ROOT / "reports" / "dynamic_realism_audit_7_9"
OUT.mkdir(parents=True, exist_ok=True)

LEN_MIN = 50.0           # m
VC_CONG = 0.85           # 严格档：接近容量
SR_CONG = 0.70           # 严格档：速度 < 70% 自由流
VC_LOOSE = 0.60          # 宽松档：仅用于「可读的展示图」
SR_LOOSE = 0.75
SR_BAD = 0.80            # 旧指标「看起来慢」的阈值（= face_metrics `SPEED_RATIO_SLOW`）
CORR_MIN_KM = 0.30
TURN_MAX_DEG = 55.0
DELAY_DRAW_MIN_S = 1.0   # 主图只画 delay ≥ 1 s（= 1 个 timeStepSize，低于此不可分辨）

MAJOR = ("motorway", "motorway_link", "trunk", "trunk_link",
         "primary", "primary_link", "secondary", "secondary_link")

RUNS = (("v1.0", A.V10_LS, 1.0), ("A-1", A.A1_LS, A.F_CAP))


# --------------------------------------------------------------------------- 读取
def read_full(p: Path, cap_mul: float) -> dict:
    """读 linkstats：标量全量 + 候选拥堵链的逐小时 TT/VOL（省内存）。

    ★ `cap_mul` 必须传入：linkstats 的 `CAPACITY` 是**基础容量**（不随
    `flowCapacityFactor` 缩放，已由 `_precheck_capacity_semantics.json` 实测确认），
    因此有效容量 = `CAPACITY × cap_mul`。
    """
    with gzip.open(p, "rt", encoding="utf-8", errors="replace") as fh:
        rd = csv.reader(fh, delimiter="\t")
        hdr = next(rd)
        c = {n: i for i, n in enumerate(hdr)}
        i_link, i_len, i_fs, i_cap = c["LINK"], c["LENGTH"], c["FREESPEED"], c["CAPACITY"]
        i_h89, i_tt89 = c["HRS8-9avg"], c["TRAVELTIME8-9avg"]
        i_h78, i_tt78 = c["HRS7-8avg"], c["TRAVELTIME7-8avg"]
        hcols = [c[f"HRS{h}-{h + 1}avg"] for h in range(24)]
        tcols = [c[f"TRAVELTIME{h}-{h + 1}avg"] for h in range(24)]
        need = max(hcols[-1], tcols[-1])
        ids, ln, fs, cap, h89, tt89, h78, tt78 = ([] for _ in range(8))
        hourly: dict[str, tuple[list[float], list[float]]] = {}
        for r in rd:
            if len(r) <= need:
                continue
            try:
                L = float(r[i_len]); F = float(r[i_fs])
                V = float(r[i_h89]); T = float(r[i_tt89]); cp = float(r[i_cap])
            except ValueError:
                continue
            ids.append(r[i_link]); ln.append(L); fs.append(F); cap.append(cp)
            h89.append(V); tt89.append(T)
            h78.append(float(r[i_h78])); tt78.append(float(r[i_tt78]))
            if L >= LEN_MIN and V > 0 and F > 0 and T > 0:
                ff = L / F
                eff_cap = cp * cap_mul
                if (V / eff_cap if eff_cap > 0 else 0.0) >= 0.45 and (ff / T) < 0.85:
                    hourly[r[i_link]] = ([float(r[i]) for i in hcols],
                                         [float(r[i]) for i in tcols])
    return {"ids": ids,
            "len": np.array(ln), "fs": np.array(fs), "cap": np.array(cap),
            "h89": np.array(h89), "tt89": np.array(tt89),
            "h78": np.array(h78), "tt78": np.array(tt78),
            "hourly": hourly}


def vec(d: dict, cap_mul: float) -> dict:
    """★ `sr` / `ttr` / `delay` 一律用**原始** `ff = LENGTH / FREESPEED`。

    `speed_ratio = ff_raw / TT` 是 canonical 口径（与 VIA TSV 的 `speed_ratio_0809`
    逐位一致），也正是产生「117,168 条 / 载流链 52.2% 全红」的那个指标。
    `ffc = ceil(ff)` 仅用于 `delay_ceil`（去量化伪影版），不得用于 `speed_ratio`。
    """
    ln, fs, cap, tt, v = d["len"], d["fs"], d["cap"], d["tt89"], d["h89"]
    with np.errstate(divide="ignore", invalid="ignore"):
        ff = np.where(fs > 0, ln / fs, np.nan)
    ffc = np.maximum(1.0, np.ceil(np.where(np.isfinite(ff), ff, 1.0) - 1e-9))
    keep = (ln >= LEN_MIN) & (v > 0) & np.isfinite(ff) & (tt > 0)
    loaded = (v > 0) & np.isfinite(ff) & (tt > 0)
    with np.errstate(divide="ignore", invalid="ignore"):
        vce = np.where(cap * cap_mul > 0, cap * cap_mul, np.nan)
        sr = np.where(loaded, ff / np.where(tt > 0, tt, np.nan), np.nan)
    return {"ff": ff, "ffc": ffc, "keep": keep, "loaded": loaded,
            "delay": np.where(keep, tt - ff, np.nan),
            "delay_ceil": np.where(keep, tt - ffc, np.nan),
            "sr": sr,
            "ttr": np.where(np.isfinite(sr) & (sr > 0), 1.0 / sr, np.nan),
            "vc": np.where(keep, v / vce, np.nan)}


def hourly_profile(d: dict) -> dict:
    """逐小时持续时间下界（**小时级**，已声明为保守下界）。

    `hours_cong`      : 该小时 `speed_ratio < SR_CONG` 且该小时有流 的整点数
    `hours_cong_am`   : 其中落在 06–10 时的整点数（早高峰窗口）
    `hours_any_delay` : 该小时 `TT > ff`（即 speed_ratio < 1）的整点数
    """
    ff_of = d["_ff_of"]
    out: dict[str, dict] = {}
    for k, (hv, tv) in d["hourly"].items():
        fl = ff_of.get(k)
        if not fl:
            continue
        hrs = hrs_am = hrs_delay = 0
        for h in range(24):
            if hv[h] <= 0 or tv[h] <= 0:
                continue
            sr = fl / tv[h]
            if sr < 1.0:
                hrs_delay += 1
            if sr < SR_CONG:
                hrs += 1
                if 6 <= h <= 10:
                    hrs_am += 1
        out[k] = {"hours_cong": hrs, "hours_cong_am": hrs_am,
                  "hours_any_delay": hrs_delay}
    return out


class Geo:
    def __init__(self):
        lab = A.load_net_labels()
        self.lab = lab
        self.pos = {lid: i for i, lid in enumerate(lab["ids"])}
        self.nx = dict(zip(lab["node_ids"].tolist(), lab["node_x"].tolist()))
        self.ny = dict(zip(lab["node_ids"].tolist(), lab["node_y"].tolist()))
        self.hwy = lab["highway"]
        self.nm = lab["name"]
        self.is_major_geo = np.array([h in MAJOR for h in self.hwy.tolist()])

    def seg(self, keys):
        segs = []
        pos = self.pos; lab = self.lab; nx = self.nx; ny = self.ny
        for k in keys:
            i = pos.get(k)
            if i is None:
                continue
            f_, t_ = lab["frm"][i], lab["to"][i]
            if f_ not in nx or t_ not in nx:
                continue
            segs.append([(nx[f_], ny[f_]), (nx[t_], ny[t_])])
        return segs


def is_major_vec(geo: Geo, ids) -> np.ndarray:
    """按 linkstats 的 id 顺序取 highway ∈ MAJOR 的布尔数组。"""
    m = dict(zip(geo.lab["ids"].tolist(), geo.is_major_geo.tolist()))
    return np.array([bool(m.get(k, False)) for k in ids])


def frame(ax, title, fs=12):
    ax.set_aspect("equal")
    ax.set_xlim(2000, 52000)
    ax.set_ylim(21000, 51500)
    ax.set_title(title, fontsize=fs, loc="left")
    ax.set_xticks([]); ax.set_yticks([])
    for s in ax.spines.values():
        s.set_color("#bbbbbb")


def add_cbar(fig, ax, cmap, norm, label):
    import matplotlib.pyplot as plt
    sm = plt.cm.ScalarMappable(cmap=cmap, norm=norm)
    sm.set_array([])
    cb = fig.colorbar(sm, ax=ax, fraction=0.020, pad=0.012)
    cb.set_label(label, fontsize=9)


# --------------------------------------------------------------------------- 走廊
def _wrap(a):
    while a > math.pi:
        a -= 2 * math.pi
    while a < -math.pi:
        a += 2 * math.pi
    return a


def build_corridors(d, dv, geo, prof, vc_min: float, sr_max: float):
    """拥堵事件 = `len≥50 m` 且 `vol>0` 且 `vc ≥ vc_min` 且 `speed_ratio < sr_max`；
    再按**最小转角**（≤55°）串成长链，保留 ≥ `CORR_MIN_KM`。"""
    vc, sr, ln = dv["vc"], dv["sr"], d["len"]
    idx = np.where(dv["keep"] & np.isfinite(vc) & np.isfinite(sr)
                   & (vc >= vc_min) & (sr < sr_max))[0]
    cong = {}
    for i in idx:
        k = d["ids"][i]
        j = geo.pos.get(k)
        if j is None:
            continue
        f_, t_ = geo.lab["frm"][j], geo.lab["to"][j]
        if f_ not in geo.nx or t_ not in geo.nx:
            continue
        hd = math.atan2(geo.ny[t_] - geo.ny[f_], geo.nx[t_] - geo.nx[f_])
        p = prof.get(k, {})
        cong[k] = {"frm": f_, "to": t_, "hd": hd, "len": float(ln[i]), "v": float(d["h89"][i]),
                   "vc": float(vc[i]), "sr": float(sr[i]),
                   "hwy": str(geo.hwy[j]), "name": str(geo.nm[j]),
                   "hc": int(p.get("hours_cong", 0)), "hcam": int(p.get("hours_cong_am", 0))}
    out_of: dict = {}
    in_of: dict = {}
    for k, c in cong.items():
        out_of.setdefault(c["frm"], []).append(k)
        in_of.setdefault(c["to"], []).append(k)

    def pick(cur, cands, used):
        best, bd = None, None
        for m in cands:
            if m in used or m not in cong:
                continue
            dh = abs(_wrap(cong[m]["hd"] - cong[cur]["hd"]))
            if bd is None or dh < bd:
                best, bd = m, dh
        if best is not None and bd is not None and bd <= math.radians(TURN_MAX_DEG):
            return best
        return None

    used: set = set()
    corridors = []
    for seed in sorted(cong, key=lambda k: -cong[k]["v"]):
        if seed in used:
            continue
        used.add(seed)
        pre, cur = [], seed
        while True:
            nxt = pick(cur, in_of.get(cong[cur]["frm"], []), used)
            if nxt is None:
                break
            used.add(nxt); pre.append(nxt); cur = nxt
        chain = list(reversed(pre)) + [seed]
        cur = seed
        while True:
            nxt = pick(cur, out_of.get(cong[cur]["to"], []), used)
            if nxt is None:
                break
            used.add(nxt); chain.append(nxt); cur = nxt
        km = sum(cong[k]["len"] for k in chain) / 1000.0
        if km < CORR_MIN_KM:
            continue
        names: dict = {}
        for k in chain:
            nm = cong[k]["name"] or cong[k]["hwy"]
            names[nm] = names.get(nm, 0) + 1
        top = sorted(names.items(), key=lambda x: (-x[1], x[0]))[:3]
        corridors.append({
            "n_links": len(chain), "km": round(km, 4),
            "sum_flow": round(sum(cong[k]["v"] for k in chain), 1),
            "mean_vc": round(sum(cong[k]["vc"] for k in chain) / len(chain), 4),
            "mean_speed_ratio": round(sum(cong[k]["sr"] for k in chain) / len(chain), 4),
            "max_hours_cong": max(cong[k]["hc"] for k in chain),
            "hours_cong_am_max": max(cong[k]["hcam"] for k in chain),
            "top_names": "; ".join(f"{a}({b})" for a, b in top),
            "keys": chain,
        })
    corridors.sort(key=lambda c: -c["km"])
    return cong, corridors


# --------------------------------------------------------------------------- main
def main() -> int:
    t0 = time.time()
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.font_manager as mfont
    import matplotlib.pyplot as plt
    from matplotlib.collections import LineCollection
    from matplotlib.colors import ListedColormap, LogNorm
    from matplotlib.lines import Line2D
    for f in (r"C:\Windows\Fonts\msyh.ttc", r"C:\Windows\Fonts\simhei.ttf"):
        if Path(f).exists():
            try:
                mfont.fontManager.addfont(f)
            except Exception:
                pass
    plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False

    print("载入 linkstats（含候选链逐小时列）…", flush=True)
    full = {}
    for tag, p, cm in RUNS:
        d = read_full(p, cm)
        posmap = {k: i for i, k in enumerate(d["ids"])}
        d["_ff_of"] = {}
        for k in d["hourly"]:
            i = posmap[k]
            fs_ = float(d["fs"][i]); ln_ = float(d["len"][i])
            d["_ff_of"][k] = (ln_ / fs_) if fs_ > 0 else 0.0
        dv = vec(d, cm)
        prof = hourly_profile(d)
        full[tag] = (d, dv, cm, prof)
        print(f"  {tag}: links={len(d['ids']):,}  keep(len>=50&vol>0)={int(dv['keep'].sum()):,}"
              f"  loaded={int(dv['loaded'].sum()):,}  hourly_kept={len(d['hourly']):,}", flush=True)

    geo = Geo()
    print(f"  网络标签 {len(geo.lab['ids']):,} 链 / {len(geo.nx):,} 节点", flush=True)

    rec: dict = {"step": "7.9H/congestion-visualization-rebuild",
                 "lens_min_m": LEN_MIN, "vc_strict": VC_CONG, "sr_strict": SR_CONG,
                 "vc_loose": VC_LOOSE, "sr_loose": SR_LOOSE, "sr_bad": SR_BAD,
                 "delay_draw_min_s": DELAY_DRAW_MIN_S,
                 "corr_min_km": CORR_MIN_KM, "turn_max_deg": TURN_MAX_DEG,
                 "major_classes": list(MAJOR), "runs": {}}

    # ---------- 量化伪影量化 ----------
    q = {}
    for tag, (d, dv, cm, prof) in full.items():
        sr = dv["sr"]
        loaded = dv["loaded"]
        bad = np.isfinite(sr) & (sr < SR_BAD)
        short = d["len"] < LEN_MIN
        kept = dv["keep"]
        srf = np.where(kept, sr, np.nan)
        ok = np.isfinite(srf)
        q[tag] = {
            "n_loaded": int(loaded.sum()),
            "n_sr_lt_080": int(bad.sum()),
            "share_sr_lt_080_of_loaded": round(float(bad.sum()) / max(1, int(loaded.sum())), 6),
            "share_of_bad_on_len_lt50": round(float((bad & short).sum()) / max(1, int(bad.sum())), 6),
            "n_kept": int(kept.sum()),
            "n_kept_sr_lt_080": int((ok & (srf < SR_BAD)).sum()),
            "share_kept_sr_lt_080": round(float((ok & (srf < SR_BAD)).sum()) / max(1, int(ok.sum())), 6),
        }
    rec["quantization_pollution"] = q

    # ---------- F1 ----------
    fig, axes = plt.subplots(2, 2, figsize=(19, 17))
    for row, (tag, (d, dv, cm, prof)) in enumerate(full.items()):
        ax = axes[row][0]
        bs = geo.seg([d["ids"][i] for i in np.where(dv["loaded"])[0]])
        if bs:
            ax.add_collection(LineCollection(bs, colors="#e6e6e6", linewidths=0.3))
        sr = dv["sr"]
        sel = np.where(np.isfinite(sr) & (sr < SR_BAD))[0]
        s2 = geo.seg([d["ids"][i] for i in sel])
        if s2:
            ax.add_collection(LineCollection(s2, colors="#d73027", linewidths=0.45))
        r = q[tag]
        frame(ax, f"{tag} · 旧指标 speed_ratio < 0.80（= 官方图口径）\n"
                  f"红链 {r['n_sr_lt_080']:,} 条 = 载流链 {100 * r['share_sr_lt_080_of_loaded']:.1f}%；"
                  f"其中 {100 * r['share_of_bad_on_len_lt50']:.0f}% 是 LENGTH<50 m 短链"
                  f" ⇒ 满屏红", 12)

        ax = axes[row][1]
        bs = geo.seg([d["ids"][i] for i in np.where(dv["keep"])[0]])
        if bs:
            ax.add_collection(LineCollection(bs, colors="#f0f0f0", linewidths=0.3))
        dl = dv["delay"]
        pos_i = np.where(np.isfinite(dl) & (dl >= DELAY_DRAW_MIN_S))[0]
        if pos_i.size:
            s3 = geo.seg([d["ids"][i] for i in pos_i])
            vals = dl[pos_i]
            lc = LineCollection(s3, cmap=plt.get_cmap("YlOrRd"), norm=LogNorm(vmin=1.0, vmax=300.0),
                                linewidths=np.clip(np.log1p(vals) / 2.2, 0.6, 3.0))
            lc.set_array(vals)
            ax.add_collection(lc)
        frame(ax, f"{tag} · 新主图 delay = TT − FF（len≥50 m 且 vol>0，只画 delay≥1 s）\n"
                  f"{int(pos_i.size):,} 条 / "
                  f"{float(d['len'][pos_i].sum()) / 1000:,.1f} km"
                  f" ⇒ 有梯度、能读出「哪里堵」", 12)
    fig.suptitle("Step 7.9H · 为什么旧图「全红」：speed_ratio 把「正常速度折损」与「真拥堵」混为一谈\n"
                 "Singapore_OD_MATSim · it.19 · EPSG:3414 · ⛔ 任何判据均未改动",
                 fontsize=15, y=0.995)
    p1 = OUT / "fig_why_speedratio_fails_v10_A1.png"
    fig.savefig(p1, bbox_inches="tight", facecolor="white", dpi=120)
    plt.close(fig)
    print(f"  [F1] {p1.name}", flush=True)

    # ---------- F2 v/c 五档 ----------
    vbins = [0.0, 0.50, 0.70, 0.85, 1.00, 1e9]
    vlabs = ["<0.50", "0.50–0.70", "0.70–0.85", "0.85–1.00", ">1.00"]
    vcols = ["#4575b4", "#74add1", "#fee090", "#fdae61", "#d73027"]
    fig, axes = plt.subplots(1, 2, figsize=(22, 10))
    vc_hist = {}
    for ax, (tag, (d, dv, cm, prof)) in zip(axes, full.items()):
        bs = geo.seg([d["ids"][i] for i in np.where(dv["keep"])[0]])
        if bs:
            ax.add_collection(LineCollection(bs, colors="#ececec", linewidths=0.3))
        vc = dv["vc"]; cnt = []; kms = []
        for a, b, c in zip(vbins[:-1], vbins[1:], vcols):
            sel = np.where(dv["keep"] & np.isfinite(vc) & (vc >= a) & (vc < b))[0]
            cnt.append(int(sel.size))
            kms.append(round(float(d["len"][sel].sum()) / 1000.0, 3) if sel.size else 0.0)
            s = geo.seg([d["ids"][i] for i in sel])
            if s:
                ax.add_collection(LineCollection(s, colors=c, linewidths=0.8))
        vc_hist[tag] = {"n": dict(zip(vlabs, cnt)), "km": dict(zip(vlabs, kms))}
        frame(ax, f"{tag} · 方案 A：v/c 五档（载流链 {int(dv['keep'].sum()):,} 条，len≥50 m）\n"
                  + " / ".join(f"{l}:{n:,}" for l, n in zip(vlabs, cnt)))
        ax.legend(handles=[Line2D([], [], color=c, lw=2.4, label=l) for l, c in zip(vlabs, vcols)],
                  fontsize=10, loc="upper left", framealpha=0.9)
    fig.suptitle("Step 7.9H · 方案 A：主图为 v/c —— 「这条路到底是不是接近容量？」\n"
                 "Singapore_OD_MATSim · it.19 · EPSG:3414 · 过滤 len≥50 m 且 vol>0",
                 fontsize=15, y=0.99)
    p2 = OUT / "congestion_map_vc_5bin_v10_A1.png"
    fig.savefig(p2, bbox_inches="tight", facecolor="white", dpi=130)
    plt.close(fig)
    rec["vc_hist"] = vc_hist
    print(f"  [F2] {p2.name}", flush=True)

    # ---------- F3 delay 主图 ----------
    fig, axes = plt.subplots(1, 2, figsize=(22, 10))
    dstat = {}
    for ax, (tag, (d, dv, cm, prof)) in zip(axes, full.items()):
        bs = geo.seg([d["ids"][i] for i in np.where(dv["keep"])[0]])
        if bs:
            ax.add_collection(LineCollection(bs, colors="#f0f0f0", linewidths=0.3))
        dl = dv["delay"]
        sel = np.where(np.isfinite(dl) & (dl >= DELAY_DRAW_MIN_S))[0]
        vals = dl[sel]
        if sel.size:
            lc = LineCollection(geo.seg([d["ids"][i] for i in sel]),
                                cmap=plt.get_cmap("YlOrRd"), norm=LogNorm(vmin=1, vmax=300),
                                linewidths=np.clip(np.log1p(vals) / 2.0, 0.6, 3.4))
            lc.set_array(vals)
            ax.add_collection(lc)
            add_cbar(fig, ax, plt.get_cmap("YlOrRd"), LogNorm(vmin=1, vmax=300),
                     "delay [s] = TT − 自由流行程时间")
        km = float(d["len"][sel].sum()) / 1000.0 if sel.size else 0.0
        km_kept = float(d["len"][dv["keep"]].sum()) / 1000.0
        dstat[tag] = {"n": int(sel.size), "km": round(km, 3),
                      "km_share_of_filtered": round(km / max(1e-9, km_kept), 5),
                      "median_delay_s": round(float(np.median(vals)), 3) if sel.size else 0.0,
                      "p90_delay_s": round(float(np.percentile(vals, 90)), 3) if sel.size else 0.0,
                      "max_delay_s": round(float(vals.max()), 3) if sel.size else 0.0,
                      "sum_delay_veh_h": round(float((vals * d["h89"][sel]).sum()) / 3600.0, 1)
                      if sel.size else 0.0}
        frame(ax, f"{tag} · 主图：拥堵延误 delay = TT − FF（len≥50 m 且 vol>0，只画 delay≥1 s）\n"
                  f"{int(sel.size):,} 条 / {km:,.1f} km（占过滤后里程 "
                  f"{100 * dstat[tag]['km_share_of_filtered']:.1f}%）；"
                  f"中位 {dstat[tag]['median_delay_s']:.1f} s，"
                  f"总延误 {dstat[tag]['sum_delay_veh_h']:,.0f} veh·h")
    fig.suptitle("Step 7.9H · 主图：拥堵延误 —— 回答「到底哪里堵」\n"
                 "Singapore_OD_MATSim · it.19 · EPSG:3414 · 过滤 length≥50 m 且 volume>0",
                 fontsize=15, y=0.99)
    p3 = OUT / "congestion_map_delay_v10_A1.png"
    fig.savefig(p3, bbox_inches="tight", facecolor="white", dpi=130)
    plt.close(fig)
    rec["delay_map"] = dstat
    print(f"  [F3] {p3.name}", flush=True)

    # ---------- F4 TT_ratio（仅干道） ----------
    tbins = [1.00, 1.15, 1.43, 2.00, 1e9]
    tlabs = ["<1.00", "1.00–1.15", "1.15–1.43", "1.43–2.00", ">2.00"]
    tcols = ["#91bfdb", "#abd9e9", "#ffffbf", "#fdae61", "#d73027"]
    fig, axes = plt.subplots(1, 2, figsize=(22, 10))
    thist = {}
    for ax, (tag, (d, dv, cm, prof)) in zip(axes, full.items()):
        maj = is_major_vec(geo, d["ids"])
        base = dv["keep"] & maj
        bs = geo.seg([d["ids"][i] for i in np.where(base)[0]])
        if bs:
            ax.add_collection(LineCollection(bs, colors="#ededed", linewidths=0.5))
        ttr = dv["ttr"]; cnt = []
        for a, b, c in zip(tbins[:-1], tbins[1:], tcols):
            sel = np.where(base & np.isfinite(ttr) & (ttr >= a) & (ttr < b))[0]
            cnt.append(int(sel.size))
            s = geo.seg([d["ids"][i] for i in sel])
            if s:
                ax.add_collection(LineCollection(s, colors=c, linewidths=0.9))
        thist[tag] = dict(zip(tlabs, cnt))
        frame(ax, f"{tag} · 方案 B：TT_ratio（仅干道 motorway/trunk/primary/secondary）\n"
                  f"干道载流链 {int(base.sum()):,} 条 / "
                  + " / ".join(f"{l}:{n:,}" for l, n in zip(tlabs, cnt)))
        ax.legend(handles=[Line2D([], [], color=c, lw=2.4, label=l) for l, c in zip(tlabs, tcols)],
                  fontsize=10, loc="upper left", framealpha=0.9)
    fig.suptitle("Step 7.9H · 辅助图：旅行时间倍率 TT_ratio（已排除 service / connector / 极短链）\n"
                 "Singapore_OD_MATSim · it.19 · EPSG:3414 · 过滤 len≥50 m 且 vol>0",
                 fontsize=15, y=0.99)
    p4 = OUT / "congestion_map_ttratio_major_v10_A1.png"
    fig.savefig(p4, bbox_inches="tight", facecolor="white", dpi=130)
    plt.close(fig)
    rec["ttratio_major_hist"] = thist
    print(f"  [F4] {p4.name}", flush=True)

    # ---------- F5 拥堵走廊（双档） ----------
    corr_all = {}
    for tag, (d, dv, cm, prof) in full.items():
        c_l, k_l = build_corridors(d, dv, geo, prof, VC_LOOSE, SR_LOOSE)
        c_s, k_s = build_corridors(d, dv, geo, prof, VC_CONG, SR_CONG)
        corr_all[tag] = {"loose": (c_l, k_l), "strict": (c_s, k_s)}
        print(f"  [{tag}] 宽松档 拥堵链 {len(c_l):,} → 走廊 {len(k_l)} 条"
              f"（{sum(c['km'] for c in k_l):,.1f} km）｜ 严格档 拥堵链 {len(c_s):,} → "
              f"走廊 {len(k_s)} 条（{sum(c['km'] for c in k_s):,.1f} km）", flush=True)
    fig, axes = plt.subplots(1, 2, figsize=(22, 10))
    for ax, (tag, (d, dv, cm, prof)) in zip(axes, full.items()):
        cc = corr_all[tag]
        bs = geo.seg([d["ids"][i] for i in np.where(dv["keep"])[0]])
        if bs:
            ax.add_collection(LineCollection(bs, colors="#f4f4f4", linewidths=0.3))
        for c in cc["loose"][1]:
            s = geo.seg(c["keys"])
            if s:
                ax.add_collection(LineCollection(s, colors="#f4a582", linewidths=1.6))
        for c in cc["strict"][1]:
            s = geo.seg(c["keys"])
            if s:
                ax.add_collection(LineCollection(
                    s, colors="#b2182b",
                    linewidths=float(np.clip(1.0 + c["sum_flow"] / 12000.0, 1.6, 4.0))))
        ks = cc["strict"][1]
        frame(ax, f"{tag} · 方案 C：拥堵走廊（连续相邻按最小转角合并）\n"
                  f"严格档（vc≥{VC_CONG} 且 speed_ratio<{SR_CONG}）：{len(ks)} 条 / "
                  f"{sum(c['km'] for c in ks):,.1f} km；"
                  f"宽松档（vc≥{VC_LOOSE} 且 sr<{SR_LOOSE}）："
                  f"{len(cc['loose'][1])} 条 / {sum(c['km'] for c in cc['loose'][1]):,.1f} km\n"
                  f"最长持续 {max([c['max_hours_cong'] for c in ks] or [0])} h")
        for c in ks[:6]:
            mid = c["keys"][len(c["keys"]) // 2]
            j = geo.pos.get(mid)
            if j is None:
                continue
            f_ = geo.lab["frm"][j]
            nm = c["top_names"].split(";")[0].strip()
            ax.annotate(f"{nm} · {c['km']:.1f} km · {c['max_hours_cong']}h",
                        (geo.nx[f_], geo.ny[f_]), fontsize=8, color="#67001f",
                        ha="center", va="bottom")
        ax.legend(handles=[Line2D([], [], color="#f4a582", lw=2.6, label="宽松档（接近容量）"),
                           Line2D([], [], color="#b2182b", lw=2.6, label="严格档（真拥堵）")],
                  fontsize=10, loc="upper left", framealpha=0.9)
    fig.suptitle("Step 7.9H · 方案 C：拥堵走廊 —— 给领导的图应该是「几条走廊」，不是「全岛一片红」\n"
                 "Singapore_OD_MATSim · it.19 · EPSG:3414 · 持续时间 = 小时级下界",
                 fontsize=15, y=0.99)
    p5 = OUT / "congestion_corridors_v10_A1.png"
    fig.savefig(p5, bbox_inches="tight", facecolor="white", dpi=130)
    plt.close(fig)
    print(f"  [F5] {p5.name}", flush=True)

    for tag in ("v1.0", "A-1"):
        suf = "v10" if tag == "v1.0" else "A1"
        with open(OUT / f"congestion_corridors_{suf}.csv", "w", newline="",
                  encoding="utf-8-sig") as fh:
            w = csv.writer(fh)
            w.writerow(["tier", "rank", "n_links", "km", "sum_flow_veh_h", "mean_vc",
                        "mean_speed_ratio", "max_hours_congested", "top_road_names"])
            for tier in ("strict", "loose"):
                cong, cors = corr_all[tag][tier]
                for i, c in enumerate(cors, 1):
                    w.writerow([tier, i, c["n_links"], c["km"], c["sum_flow"], c["mean_vc"],
                                c["mean_speed_ratio"], c["max_hours_cong"], c["top_names"]])
        rec["corridors_" + suf] = {}
        for tier in ("strict", "loose"):
            cong, cors = corr_all[tag][tier]
            rec["corridors_" + suf][tier] = {
                "n_congestion_links": len(cong), "n_corridors": len(cors),
                "km_total": round(sum(c["km"] for c in cors), 3),
                "max_hours_congested": max([c["max_hours_cong"] for c in cors] or [0]),
                "top10": [{k: v for k, v in c.items() if k != "keys"} for c in cors[:10]],
            }

    rec["images"] = [p.name for p in (p1, p2, p3, p4, p5)]
    rec["elapsed_s"] = round(time.time() - t0, 1)
    (OUT / "_congestion_maps_7_9h.json").write_text(
        json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n[out] {OUT / '_congestion_maps_7_9h.json'}  （{rec['elapsed_s']} s）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
