#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""
esb04b_coupling_audit.py — E-SB-04B 阶段 1–4：自由流速度变更与路径重分配的空间耦合审计
=========================================================================================
★零仿真 · 只读。⛔ 不启动 MATSim；不改 network / population / capacity / freespeed /
SCALE / lambda / 阈值 / 任何冻结配置；⛔ 不生成 v1.1。

预注册协议：experiments/E-SB-04B_path_freespeed_coupling/PROTOCOL_E-SB-04B.md

阶段 1  门禁 G01–G09（输入存在性 / 可比性 / 变更链非空）
阶段 2  检查1：freespeed 变更的空间特征（按 highway / 走廊 / Δ 幅度）
阶段 3  检查2：路线变化 ↔ 速度变更（逐人；含 route-effect/network-effect 分解）
阶段 4  检查3：观测域 ΔQ ↔ freespeed 变更（逐匹配边 / 走廊）
        （负例 N1–N3 见 esb04b_negcontrol_verdict.py；本脚本已导出其所需聚合向量）

产物 → reports/path_redistribution_audit_E_SB_04B/
用法：python scripts/experiments/esb04b_coupling_audit.py
"""
from __future__ import annotations

import gzip
import hashlib
import json
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(r"D:\Luan\2026-05\2_Singapore")
OUT = ROOT / "reports" / "path_redistribution_audit_E_SB_04B"
EXP = ROOT / "experiments" / "E-SB-04B_path_freespeed_coupling"
E4_OUT = ROOT / "reports" / "path_redistribution_audit_E_SB_04"
E4_CACHE = ROOT / "experiments" / "E-SB-04_path_redistribution_audit" / "_cache"
E3_AUDIT = ROOT / "experiments" / "E-SB-03_flow_shift_audit" / "audit"
NET_SRC = ROOT / "reports" / "matsim_network" / "network_links_source_copy.csv"
CW = ROOT / "reports" / "od_final_calibration_crosswalk_7_3_6" / "final_calibration_crosswalk.csv"

OUT.mkdir(parents=True, exist_ok=True)
CACHE = EXP / "_cache"
CACHE.mkdir(parents=True, exist_ok=True)

V10 = {"run": ROOT / "matsim_final_7_6h" / "outputs" / "W01_rc_min", "rid": "W01_rc_min"}
A5 = {"run": ROOT / "experiments" / "E-SB-02_night_freeflow" / "outputs" / "SB-A5", "rid": "SB-A5"}

SCALE = 459794.0 / 200000.0

CORRIDORS = {
    "PIE": r"pan[- ]?island expressway", "TPE": r"tampines expressway",
    "CTE": r"central expressway", "KPE": r"kallang[- ]?paya lebar expressway",
    "KJE": r"kranji expressway", "AYE": r"ayer rajah expressway",
    "SLE": r"seletar expressway", "BKE": r"bukit timah expressway",
    "MCE": r"marina co[a-z]*tal expressway", "ECP": r"east coast parkway",
}
SURFACE = ["primary", "trunk", "secondary"]
EXPRESS = ["motorway", "motorway_link"]

GATES: list[dict] = []


def gate(cid, name, ok, detail="", status="effective"):
    GATES.append({"id": cid, "gate": name, "pass": bool(ok), "status": status, "detail": detail})
    tag = "" if status == "effective" else f"  «{status}»"
    print(f"  [{'PASS' if ok else 'FAIL'}] {cid}  {name}" + (f"  | {detail}" if detail else "") + tag, flush=True)
    return bool(ok)


def sha256_file(p: Path, chunk=1 << 22) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        while True:
            b = f.read(chunk)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def parse_config(path: Path) -> dict:
    txt = path.read_text(encoding="utf-8", errors="replace")
    params = {}
    for m in re.finditer(r'<param\s+name="([^"]+)"\s+value="([^"]*)"', txt):
        params.setdefault(m.group(1), m.group(2))
    for modname, body in re.findall(r'<module\s+name="([^"]+)"(.*?)</module>', txt, re.S):
        for m in re.finditer(r'<param\s+name="([^"]+)"\s+value="([^"]*)"', body):
            params[f"{modname}.{m.group(1)}"] = m.group(2)
    return params


LINK_RE = re.compile(
    r'<link\s+id="([^"]+)"\s+from="([^"]+)"\s+to="([^"]+)"\s+length="([^"]+)"'
    r'\s+freespeed="([^"]+)"\s+capacity="([^"]+)"\s+permlanes="([^"]+)"')


def parse_network(path: Path) -> dict:
    """id → (length_m, freespeed_m_s, capacity, permlanes, from, to)。"""
    d = {}
    with gzip.open(path, "rt", encoding="utf-8", errors="replace") as f:
        for line in f:
            if '<link ' not in line:
                continue
            m = LINK_RE.search(line)
            if m:
                d[m.group(1)] = (float(m.group(4)), float(m.group(5)),
                                 float(m.group(6)), float(m.group(7)), m.group(2), m.group(3))
    return d


def main() -> int:
    print("=" * 100)
    print("E-SB-04B 自由流速度变更与路径重分配的空间耦合审计 · 阶段 1–4")
    print("=" * 100)

    # ===================== 阶段 1：门禁 =====================
    inputs = {
        "v1.0.network": V10["run"] / f"{V10['rid']}.output_network.xml.gz",
        "SB-A5.network": A5["run"] / f"{A5['rid']}.output_network.xml.gz",
        "v1.0.plans": V10["run"] / f"{V10['rid']}.output_plans.xml.gz",
        "SB-A5.plans": A5["run"] / f"{A5['rid']}.output_plans.xml.gz",
        "v1.0.config_full": V10["run"] / f"{V10['rid']}.output_config.xml",
        "SB-A5.config_full": A5["run"] / f"{A5['rid']}.output_config.xml",
        "net_src_copy": NET_SRC,
        "crosswalk": CW,
        "e4_edge_level_delta": E4_OUT / "edge_level_delta.csv",
        "e4_corridor_route_use": E4_OUT / "corridor_route_use.csv",
        "e4_corridor_decomp": E4_OUT / "corridor_delta_decomposition.csv",
        "esb03_section_delta": E3_AUDIT / "esb03_section_delta.csv",
        "cache.cls_v1.0": E4_CACHE / "cls_v1.0.pkl",
        "cache.cls_SB-A5": E4_CACHE / "cls_SB-A5.pkl",
        "cache.routes_v1.0": E4_CACHE / "routes_v1.0.pkl",
        "cache.routes_SB-A5": E4_CACHE / "routes_SB-A5.pkl",
    }
    manifest = {}
    mcache = CACHE / "manifest_cache.json"
    prev = json.loads(mcache.read_text(encoding="utf-8")) if mcache.exists() else {}

    def file_rec(p: Path):
        ex = p.exists()
        rec = {"path": str(p), "exists": ex}
        if ex:
            st = p.stat()
            rec["size_bytes"] = st.st_size
            rec["mtime_ns"] = st.st_mtime_ns
            old = prev.get(str(p))
            if old and old.get("size_bytes") == st.st_size and old.get("mtime_ns") == st.st_mtime_ns \
               and old.get("sha256"):
                rec["sha256"] = old["sha256"]
                rec["sha256_cached"] = True
            else:
                rec["sha256"] = sha256_file(p)
        return rec

    print("\n[阶段1] 输入清单")
    for k, p in inputs.items():
        manifest[k] = file_rec(p)
        print(f"    {k:26s} exists={manifest[k]['exists']!s:5s} "
              f"size={manifest[k].get('size_bytes',0):>15,}", flush=True)
    mcache.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    gate("G01", "三臂 network 与 plans 均存在",
         all(manifest[k]["exists"] for k in ("v1.0.network", "SB-A5.network",
                                             "v1.0.plans", "SB-A5.plans")))
    gate("G05.cache", "路线缓存与 cls 缓存均可用",
         all(manifest[k]["exists"] for k in ("cache.cls_v1.0", "cache.cls_SB-A5",
                                             "cache.routes_v1.0", "cache.routes_SB-A5")))

    print("\n[阶段1] 网络比对（link id 集合 / 拓扑 / freespeed）")
    n10 = parse_network(inputs["v1.0.network"])
    n5 = parse_network(inputs["SB-A5.network"])
    print(f"    v1.0 links={len(n10):,}  SB-A5 links={len(n5):,}")
    ids10, ids5 = set(n10), set(n5)
    gate("G02", "v1.0 与 SB-A5 网络 link id 集合逐位相同", ids10 == ids5,
         f"∩={len(ids10 & ids5):,} A={len(ids10):,} B={len(ids5):,}")

    ALL = sorted(ids10)
    idx = {l: i for i, l in enumerate(ALL)}
    N = len(ALL)
    LEN = np.array([n10[l][0] for l in ALL], dtype=np.float64)
    FS10 = np.array([n10[l][1] for l in ALL], dtype=np.float64)
    FS5 = np.array([n5[l][1] for l in ALL], dtype=np.float64)
    DFREE = FS5 - FS10

    n_topo = 0
    for l in ids10:
        a, b = n10[l], n5[l]
        if a[4] != b[4] or a[5] != b[5] or abs(a[0] - b[0]) > 1e-6 \
           or abs(a[2] - b[2]) > 1e-6 or abs(a[3] - b[3]) > 1e-6:
            n_topo += 1
    n_chg = int((np.abs(DFREE) > 1e-9).sum())
    n_up = int((DFREE > 1e-9).sum())
    n_dn = int((DFREE < -1e-9).sum())
    print(f"    拓扑(from/to/length/cap/lanes)差异={n_topo:,}")
    print(f"    freespeed 变更链={n_chg:,}  升={n_up:,}  降={n_dn:,}  未变={N-n_chg:,}")
    gate("G03", "SB-A5 相对 v1.0 仅 freespeed 变化（拓扑零差异）", n_topo == 0, f"topo_diff={n_topo}")
    gate("G08", "freespeed 变更链 > 0 且升/降两侧均非空", n_chg > 0 and n_up > 0 and n_dn > 0,
         f"n_chg={n_chg:,} up={n_up:,} down={n_dn:,}")

    cfg10 = parse_config(inputs["v1.0.config_full"])
    cfg5 = parse_config(inputs["SB-A5.config_full"])
    pop10 = cfg10.get("plans.inputPlansFile", "<absent>")
    pop5 = cfg5.get("plans.inputPlansFile", "<absent>")
    gate("G04", "v1.0 与 SB-A5 使用同一 inputPlansFile（需求可比）", pop10 == pop5,
         f"v1.0={Path(pop10).name} | SB-A5={Path(pop5).name}")

    # 属性：highway / corridor
    src = pd.read_csv(NET_SRC, encoding="utf-8-sig", low_memory=False,
                      usecols=["from_node", "to_node", "highway", "name"])
    src["matsim_link_id"] = "e" + src["from_node"].astype(str) + "_" + src["to_node"].astype(str)
    src["highway"] = src["highway"].astype(str).str.lower().str.strip()
    nm = src["name"].astype(str).str.lower()
    corr = pd.Series("", index=src.index)
    for code, pat in CORRIDORS.items():
        corr = corr.mask(nm.str.contains(pat, regex=True) & (corr == ""), code)
    src["corridor"] = corr
    src = src.drop_duplicates("matsim_link_id").set_index("matsim_link_id")
    HW_L = np.array([src["highway"].get(l, "NA") for l in ALL], dtype=object)
    CO_L = np.array([src["corridor"].get(l, "") for l in ALL], dtype=object)
    cov = int(np.sum(HW_L != "NA"))
    print(f"    等级映射覆盖 {cov:,}/{N:,}（{cov/N*100:.2f}%）")
    gate("G10", "network→highway 源表覆盖 ≥ 99%", cov / N >= 0.99, f"{cov}/{N}")

    # ===================== 阶段 2：检查1 速度变更空间特征 =====================
    print("\n[阶段2] 检查1：freespeed 变更的空间特征（单位 m/s；km/h = ×3.6）")
    lk = pd.DataFrame({"link": ALL, "len_m": LEN, "fs_v10": FS10, "fs_a5": FS5,
                       "dfree": DFREE, "highway": HW_L, "corridor": CO_L})
    lk["changed"] = lk["dfree"].abs() > 1e-9
    lk["w"] = lk["len_m"] / lk["len_m"].sum()

    def agg_class(g):
        ch = g[g["changed"]]
        return pd.Series({
            "n_links": len(g), "n_changed": int(g["changed"].sum()),
            "chg_pct": g["changed"].mean() * 100,
            "len_changed_km": ch["len_m"].sum() / 1000,
            "fs_v10_ms": g["fs_v10"].mean(), "fs_a5_ms": g["fs_a5"].mean(),
            "dfree_mean_ms": g["dfree"].mean(), "dfree_median_ms": g["dfree"].median(),
            "dfree_wmean_ms": float((g["len_m"] * g["dfree"]).sum() / g["len_m"].sum()),
            "dfree_wmean_kmh": float((g["len_m"] * g["dfree"]).sum() / g["len_m"].sum() * 3.6),
            "n_up": int((g["dfree"] > 1e-9).sum()), "n_down": int((g["dfree"] < -1e-9).sum()),
            "d_min_ms": g["dfree"].min(), "d_max_ms": g["dfree"].max(),
        })

    fs_cls = lk.groupby("highway", dropna=False).apply(agg_class, include_groups=False).reset_index()
    fs_cls = fs_cls.sort_values("n_changed", ascending=False)
    fs_cls.to_csv(OUT / "freespeed_change_summary.csv", index=False, encoding="utf-8-sig")
    print("    —— 按道路等级 ——")
    for _, r in fs_cls.iterrows():
        print(f"      {str(r['highway']):16s} n={int(r['n_links']):>7,} 变更={int(r['n_changed']):>6,} "
              f"({r['chg_pct']:5.1f}%)  里程加权Δ={r['dfree_wmean_ms']:+7.3f} m/s "
              f"({r['dfree_wmean_kmh']:+6.2f} km/h)  升{int(r['n_up']):,}/降{int(r['n_down']):,}")

    # 走廊
    ch = lk[lk["changed"]]
    fs_cor = ch.groupby("corridor", dropna=False).apply(
        lambda g: pd.Series({"n_changed": len(g), "len_changed_km": g["len_m"].sum() / 1000,
                             "dfree_mean_ms": g["dfree"].mean(),
                             "dfree_median_ms": g["dfree"].median(),
                             "dfree_kmh": g["dfree"].mean() * 3.6,
                             "n_up": int((g["dfree"] > 1e-9).sum()),
                             "n_down": int((g["dfree"] < -1e-9).sum())}),
        include_groups=False).reset_index().sort_values("n_changed", ascending=False)
    fs_cor["corridor"] = fs_cor["corridor"].fillna("")          # ★非识别走廊统一为空串，避免 CSV 出现 nan
    fs_cor.to_csv(OUT / "freespeed_change_by_corridor.csv", index=False, encoding="utf-8-sig")
    print("    —— 按走廊（仅变更链）——")
    for _, r in fs_cor.head(12).iterrows():
        print(f"      {str(r['corridor']) or '(非识别走廊)':14s} 变更={int(r['n_changed']):>6,}  "
              f"里程={r['len_changed_km']:9.2f} km  Δ均值={r['dfree_mean_ms']:+7.3f} m/s  升{int(r['n_up'])}/降{int(r['n_down'])}")

    # Δ 幅度分布（km/h）
    bins_kmh = [-np.inf, -15, -10, -5, -2, -1, -0.1, 0.1, 1, 2, 5, 10, 15, np.inf]
    labels = ["≤-15", "(-15,-10]", "(-10,-5]", "(-5,-2]", "(-2,-1]", "(-1,-0.1]",
              "[-0.1,0.1]", "[0.1,1)", "[1,2)", "[2,5)", "[5,10)", "[10,15)", ">15"]
    dk = DFREE * 3.6
    dist = pd.cut(dk, bins=bins_kmh, labels=labels).value_counts().reindex(labels).fillna(0)
    dist_df = pd.DataFrame({"dfree_bin_kmh": labels, "n_links": dist.values.astype(int)})
    dist_df["pct"] = dist_df["n_links"] / N * 100
    dist_df.to_csv(OUT / "freespeed_change_distribution.csv", index=False, encoding="utf-8-sig")

    # 判据 A
    wd_surf = float((lk.loc[lk["highway"].isin(SURFACE), "len_m"] * lk.loc[lk["highway"].isin(SURFACE), "dfree"]).sum()
                    / lk.loc[lk["highway"].isin(SURFACE), "len_m"].sum())
    wd_exp = float((lk.loc[lk["highway"].isin(EXPRESS), "len_m"] * lk.loc[lk["highway"].isin(EXPRESS), "dfree"]).sum()
                   / lk.loc[lk["highway"].isin(EXPRESS), "len_m"].sum())
    net_signed = float((LEN * DFREE).sum())
    len_chg = float(LEN[np.abs(DFREE) > 1e-9].sum())
    len_all = float(LEN.sum())
    print(f"    里程加权Δ：路面干道({'+'.join(SURFACE)})={wd_surf:+.4f} m/s  快速路({'+'.join(EXPRESS)})={wd_exp:+.4f} m/s")
    print(f"    净 signed Σlen·Δfree={net_signed:,.0f} m²/s   变更里程={len_chg/1000:,.0f} km / 全网{len_all/1000:,.0f} km"
          f"（{len_chg/len_all*100:.2f}%）")
    A1 = (0 < n_chg < N) and net_signed < 0
    A2 = wd_surf < wd_exp
    A3 = len_chg / len_all >= 0.01
    gate("A1", "变更链 ∈ (0,N) 且净降速（Σlen·Δfree<0）", A1,
         f"n_chg={n_chg:,} net={net_signed:,.0f}")
    gate("A2", "相对速度：路面干道里程加权Δ < 快速路里程加权Δ（快速路相对变快）", A2,
         f"surface={wd_surf:+.4f} express={wd_exp:+.4f} m/s")
    gate("A3", "变更覆盖里程 ≥ 全网 1%", A3, f"{len_chg/len_all*100:.2f}%")

    # ===================== 阶段 3：检查2 路线 ↔ 速度（逐人） =====================
    print("\n[阶段3] 检查2：路线变化 ↔ 速度变更（逐 person）")
    c10 = pd.read_pickle(E4_CACHE / "cls_v1.0.pkl")[["person", "route_hash", "total_len_m", "mw_segments"]]
    c5 = pd.read_pickle(E4_CACHE / "cls_SB-A5.pkl")[["person", "route_hash", "total_len_m", "mw_segments"]]
    h10 = c10.set_index("person")["route_hash"]
    h5 = c5.set_index("person")["route_hash"]
    persons = h10.index.intersection(h5.index)
    changed_mask = (h10.loc[persons].values != h5.loc[persons].values)
    changed_persons = set(persons[changed_mask])
    unchanged_persons = set(persons[~changed_mask])
    nc, nu = len(changed_persons), len(unchanged_persons)
    print(f"    persons={len(persons):,}  路线变化={nc:,}（{nc/len(persons)*100:.2f}%）  未变化={nu:,}")
    gate("G05.persons", "person 集合 = 236,044（与 E-SB-04 一致）", len(persons) == 236044,
         f"persons={len(persons):,}")

    # 聚合权重向量（供置换检验）：A=changed@R10, B=changed@R5, C=unchanged@R10
    # ★单次逐臂加载：指标 + 权重累积同轮完成（避免重复读取 1.15GB pickle）
    A = np.zeros(N); B = np.zeros(N); C = np.zeros(N)
    TGT_R10 = {p: (A if p in changed_persons else C) for p in persons}
    TGT_R5 = {p: B for p in changed_persons}

    def pass_arm(pkl, tgt_map):
        """返回 dict person -> (tot, s10, s5, slow_len, fast_len, n_chg_links, mw_len)；
        同时把里程份额权重累加到 tgt_map[person]。"""
        print(f"    <- {pkl.name} ...", flush=True)
        d = pd.read_pickle(pkl)[["person", "links"]]
        res = {}
        for p, links in zip(d["person"].values, d["links"].values):
            j = np.fromiter((idx[l] for l in links.split()), dtype=np.int32)
            L = LEN[j]
            tot = float(L.sum())
            if tot <= 0:
                continue
            res[p] = (tot, float((L * FS10[j]).sum()), float((L * FS5[j]).sum()),
                      float(L[DFREE[j] < 0].sum()), float(L[DFREE[j] > 0].sum()),
                      int((DFREE[j] != 0).sum()), float(L[HW_L[j] == "motorway"].sum()))
            t = tgt_map.get(p)
            if t is not None:
                np.add.at(t, j, L / tot)
        del d
        print(f"      done {len(res):,} routes", flush=True)
        return res

    r10 = pass_arm(E4_CACHE / "routes_v1.0.pkl", TGT_R10)
    r5 = pass_arm(E4_CACHE / "routes_SB-A5.pkl", TGT_R5)

    # 组装逐人表
    rows = []
    for p in persons:
        if p not in r10 or p not in r5:
            continue
        t10, s10_10, s5_10, sl10, fa10, nchg10, mw10 = r10[p]
        t5, s10_5, s5_5, sl5, fa5, nchg5, mw5 = r5[p]
        fsv10_r10 = s10_10 / t10
        fsa5_r10 = s5_10 / t10
        fsv10_r5 = s10_5 / t5
        fsa5_r5 = s5_5 / t5
        dfs = fsa5_r5 - fsv10_r10
        rows.append({
            "person": p, "changed": p in changed_persons,
            "tot10": t10, "tot5": t5,
            "fsV10_onR10": fsv10_r10, "fsA5_onR10": fsa5_r10,
            "fsV10_onR5": fsv10_r5, "fsA5_onR5": fsa5_r5,
            "dfs_ms": dfs,
            "route_effect_ms": fsa5_r5 - fsa5_r10,
            "network_effect_ms": fsa5_r10 - fsv10_r10,
            "slow_share10": sl10 / t10, "slow_share5": sl5 / t5,
            "chg_share10": (sl10 + fa10) / t10, "chg_share5": (sl5 + fa5) / t5,
            "mw_len10": mw10, "mw_len5": mw5,
            "n_chg_links10": nchg10, "n_chg_links5": nchg5,
        })
    rr = pd.DataFrame(rows)
    rr.to_csv(OUT / "route_delta_exposure.csv", index=False, encoding="utf-8-sig",
              float_format="%.6g")
    print(f"    逐人表落盘 rows={len(rr):,}")

    def grp(df):
        return pd.Series({
            "n": len(df),
            "fs_v10_ms": df["fsV10_onR10"].mean(), "fs_a5_ms": df["fsA5_onR5"].mean(),
            "dfs_mean_ms": df["dfs_ms"].mean(), "dfs_mean_kmh": df["dfs_ms"].mean() * 3.6,
            "dfs_median_ms": df["dfs_ms"].median(),
            "route_effect_mean_ms": df["route_effect_ms"].mean(),
            "network_effect_mean_ms": df["network_effect_ms"].mean(),
            "slow_share10_mean": df["slow_share10"].mean(),
            "slow_share5_mean": df["slow_share5"].mean(),
            "mw_len10_mean_km": df["mw_len10"].mean() / 1000,
            "mw_len5_mean_km": df["mw_len5"].mean() / 1000,
            "n_chg_links10_mean": df["n_chg_links10"].mean(),
            "n_chg_links5_mean": df["n_chg_links5"].mean(),
        })

    grp_tbl = rr.groupby("changed").apply(grp, include_groups=False).reset_index()
    grp_tbl.to_csv(OUT / "route_freespeed_coupling.csv", index=False, encoding="utf-8-sig")
    print("    —— 分组（changed vs unchanged）——")
    for _, r in grp_tbl.iterrows():
        print(f"      changed={str(r['changed']):5s} n={int(r['n']):>7,}  "
              f"Δfs={r['dfs_mean_ms']:+8.4f} m/s ({r['dfs_mean_kmh']:+7.3f} km/h)  "
              f"route_eff={r['route_effect_mean_ms']:+8.4f}  net_eff={r['network_effect_mean_ms']:+8.4f}  "
              f"slow_share10={r['slow_share10_mean']:.4f}  mw_len10={r['mw_len10_mean_km']:.3f}km")

    ch_rows = rr[rr["changed"]]
    un_rows = rr[~rr["changed"]]
    # ---- 原判据（保留实录；B1/B2/B5 经复核为「协议内部自相矛盾」，见 PROTOCOL §11）----
    B1 = float(np.abs(un_rows["dfs_ms"]).max()) < 1e-9
    B2 = ch_rows["dfs_ms"].mean() > 0
    B3 = ch_rows["dfs_ms"].mean() > un_rows["dfs_ms"].mean()
    B4 = ch_rows["slow_share10"].mean() > un_rows["slow_share10"].mean()
    B5 = (np.sign(ch_rows["route_effect_ms"].mean()) == np.sign(ch_rows["network_effect_ms"].mean())
          and abs(ch_rows["route_effect_ms"].mean()) > 0)
    # ---- 修正判据（作用在分解项上；Δfs = route_effect + network_effect）----
    B1c = float(np.abs(un_rows["route_effect_ms"]).max()) < 1e-9   # placebo 应作用于 route-effect
    B2c = ch_rows["route_effect_ms"].mean() > 0                    # 改道方向 = 走向新网络下更快的路线
    B5c = (ch_rows["route_effect_ms"].mean() > 0) and (ch_rows["network_effect_ms"].mean() < 0) \
        and abs(ch_rows["route_effect_ms"].mean()) > 0             # 路由器对网络降速作补偿性改道
    _retr = "retracted_misspecified"
    gate("B1", "placebo：未变化路线 Δfs == 0", B1, f"max|Δfs|={np.abs(un_rows['dfs_ms']).max():.3e}", status=_retr)
    gate("B2", "变化路线 Δfs > 0（改后更快）", B2, f"mean Δfs={ch_rows['dfs_ms'].mean():+.4f} m/s", status=_retr)
    gate("B3", "变化者 Δfs > 未变化者 Δfs", B3,
         f"changed={ch_rows['dfs_ms'].mean():+.4f} vs unchanged={un_rows['dfs_ms'].mean():+.4f}")
    gate("B4", "变化者在 v1.0 路线上对降速链暴露占比 > 未变化者", B4,
         f"changed={ch_rows['slow_share10'].mean():.4f} vs unchanged={un_rows['slow_share10'].mean():.4f}")
    gate("B5", "分解：route-effect 与 network-effect 同号且 |route-effect|>0", B5,
         f"route_eff={ch_rows['route_effect_ms'].mean():+.4f} net_eff={ch_rows['network_effect_ms'].mean():+.4f}",
         status=_retr)
    gate("B1c", "placebo（修正）：未变化路线 route-effect ≡ 0", B1c,
         f"max|route_effect|={np.abs(un_rows['route_effect_ms']).max():.3e}")
    gate("B2c", "变化者 route-effect > 0（改道走向新网络下更快的路线）", B2c,
         f"mean route-effect={ch_rows['route_effect_ms'].mean():+.4f} m/s")
    gate("B5c", "分解：route-effect>0 且 network-effect<0（补偿性改道）", B5c,
         f"route_eff={ch_rows['route_effect_ms'].mean():+.4f} net_eff={ch_rows['network_effect_ms'].mean():+.4f}")

    # 保存置换检验所需聚合向量与观测量
    # ★FS10 一并保存：route-effect 统计量需含常量项 Σ FS10·(B−A)/nc，
    #   否则置换表「观测值」与 §2 的 route-effect 均值**口径不一致**。
    np.savez_compressed(CACHE / "perm_inputs.npz", A=A, B=B, C=C, DFREE=DFREE, FS10=FS10)
    json.dump({"n_changed": nc, "n_unchanged": nu,
               "obs_route_effect_mean": float(ch_rows["route_effect_ms"].mean()),
               "obs_slow_share10_changed": float(ch_rows["slow_share10"].mean()),
               "obs_slow_share10_unchanged": float(un_rows["slow_share10"].mean()),
               "obs_dfs_changed_mean": float(ch_rows["dfs_ms"].mean())},
              open(CACHE / "perm_inputs.json", "w", encoding="utf-8"), ensure_ascii=False, indent=2)

    # ===================== 阶段 4：检查3 ΔQ ↔ freespeed =====================
    print("\n[阶段4] 检查3：观测域逐边 ΔQ ↔ freespeed 变更")
    e = pd.read_csv(E4_OUT / "edge_level_delta.csv", encoding="utf-8-sig", low_memory=False)
    e["matsim_link_id"] = e["matsim_link_id"].astype(str)
    gate("G06", "crosswalk=3193边/576断面 且 edge_level_delta=3193行",
         len(e) == 3193 and pd.read_csv(CW, encoding="utf-8-sig", low_memory=False)["lta_linkid"].nunique() == 576,
         f"edges={len(e)} sections=576")
    e["i"] = e["matsim_link_id"].map(idx)
    gate("G09", "每条匹配边均可取到 freespeed（覆盖 100%）", int(e["i"].notna().sum()) == len(e),
         f"{int(e['i'].notna().sum())}/{len(e)}")
    ei = e["i"].fillna(-1).astype(int).values
    e["dfree_ms"] = np.where(ei >= 0, DFREE[np.clip(ei, 0, N - 1)], np.nan)
    e["fs_changed"] = e["dfree_ms"].abs() > 1e-9
    e["hw2"] = np.where(ei >= 0, HW_L[np.clip(ei, 0, N - 1)], "NA")
    e.to_csv(OUT / "section_delta_coupling.csv", index=False, encoding="utf-8-sig")

    def dec(g):
        v = g["dQ_edge_raw"]
        p, ng = v[v > 0].sum(), v[v < 0].sum()
        return pd.Series({"n_edges": len(g), "sum_pos": float(p), "sum_neg": float(ng),
                          "net": float(v.sum()), "gross": float(p - ng),
                          "net_per_link": float(v.sum() / len(g)),
                          "share_of_net_pct": float(v.sum() / e["dQ_edge_raw"].sum() * 100),
                          "dfree_mean_ms": g["dfree_ms"].mean()})

    sc = e.groupby("fs_changed").apply(dec, include_groups=False).reset_index()
    sc.to_csv(OUT / "section_delta_coupling_by_changed.csv", index=False, encoding="utf-8-sig")
    print("    —— 匹配边按 freespeed 是否变更 ——")
    for _, r in sc.iterrows():
        print(f"      fs_changed={str(r['fs_changed']):5s} n={int(r['n_edges']):>5,}  净={r['net']:+11,.1f}  "
              f"占净增={r['share_of_net_pct']:6.1f}%  单位边净增={r['net_per_link']:+8.2f}")

    # 走廊级（复算 Spearman）
    cru = pd.read_csv(E4_OUT / "corridor_route_use.csv", encoding="utf-8-sig")
    cdd = pd.read_csv(E4_OUT / "corridor_delta_decomposition.csv", encoding="utf-8-sig")
    jc = cru.merge(cdd.rename(columns={"corridor": "code"}), left_on="corridor", right_on="code", how="inner")
    jc = jc[["corridor", "rate_v10_pct", "rate_a5_pct", "d_rate_pp", "gained_users", "lost_users",
             "n_sections", "net", "gross", "net_over_gross", "share_of_net_pct"]]
    # 走廊 freespeed 变更量（匹配边口径）
    cor_fs = e.groupby("corridor").agg(n_matched=("dQ_edge_raw", "size"),
                                       n_fs_changed=("fs_changed", "sum"),
                                       dfree_wmean_ms=("dfree_ms", "mean")).reset_index()
    jc = jc.merge(cor_fs, on="corridor", how="left")
    sp = jc["d_rate_pp"].rank().corr(jc["net"].rank())
    jc["spearman_drate_vs_net"] = sp
    jc.to_csv(OUT / "corridor_coupling_decomposition.csv", index=False, encoding="utf-8-sig")
    print(f"    走廊 route-use Δ vs ΔQ 净额 Spearman={sp:.3f}")

    net_all = float(e["dQ_edge_raw"].sum())
    p_chg = float(sc.loc[sc["fs_changed"] == True, "net"].iloc[0])
    p_unc = float(sc.loc[sc["fs_changed"] == False, "net"].iloc[0])
    share_unc = p_unc / net_all * 100
    rpl_chg = float(sc.loc[sc["fs_changed"] == True, "net_per_link"].iloc[0])
    rpl_unc = float(sc.loc[sc["fs_changed"] == False, "net_per_link"].iloc[0])
    ratio = rpl_chg / rpl_unc if rpl_unc else float("nan")
    gate("C1", "fs-未变更匹配边承担净增 > 50%（本地速度效应不足以解释）", share_unc > 50,
         f"未变更边净增占比={share_unc:.1f}%（{p_unc:,.0f}/{net_all:,.0f}）")
    gate("C2", "fs-变更边 与 未变更边 单位边净增同量级（比值∈[0.25,4]）", 0.25 <= ratio <= 4,
         f"变更={rpl_chg:.2f} 未变更={rpl_unc:.2f} 比值={ratio:.3f}")
    gate("C3", "走廊 route-use Δ 与 ΔQ 净额 Spearman > 0", sp > 0, f"spearman={sp:.3f}")

    # ===================== 汇总 =====================
    summ = {
        "audit": "E-SB-04B", "date": "2026-10-11", "scale": SCALE,
        "evidence_level": "PLANS_LEVEL（SB-A5 无 events；v1.0 plans↔events 100% 支撑计划路线可信度）",
        "n_links": N, "n_freespeed_changed": n_chg, "n_up": n_up, "n_down": n_dn,
        "len_changed_km": len_chg / 1000, "len_all_km": len_all / 1000,
        "net_signed_len_dfree": net_signed,
        "wmean_dfree_surface_ms": wd_surf, "wmean_dfree_express_ms": wd_exp,
        "freespeed_by_highway": fs_cls.to_dict("records"),
        "freespeed_by_corridor": fs_cor.to_dict("records"),
        "route_change_pct": nc / len(persons) * 100,
        "route_coupling": grp_tbl.to_dict("records"),
        "route_decomp": {"route_effect_mean_ms": float(ch_rows["route_effect_ms"].mean()),
                         "network_effect_mean_ms": float(ch_rows["network_effect_ms"].mean()),
                         "compensation_ratio": float(abs(ch_rows["route_effect_ms"].mean())
                                                     / abs(ch_rows["network_effect_ms"].mean()))
                         if ch_rows["network_effect_ms"].mean() else None},
        "section_by_fs_changed": sc.to_dict("records"),
        "corridor_coupling": jc.to_dict("records"),
        "spearman_drate_vs_net": float(sp),
        "gates": GATES,
    }
    (OUT / "esb04b_summary.json").write_text(json.dumps(summ, ensure_ascii=False, indent=2, default=str),
                                             encoding="utf-8")
    pd.DataFrame(GATES).to_csv(OUT / "gate_checks.csv", index=False, encoding="utf-8-sig")
    (OUT / "input_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    n_fail = sum(1 for g in GATES if not g["pass"] and g["status"] == "effective")
    n_retr = sum(1 for g in GATES if g["status"] != "effective")
    n_eff = len(GATES) - n_retr
    print("\n" + "=" * 100)
    print(f"E-SB-04B 阶段1–4 有效门禁：{n_eff-n_fail}/{n_eff} PASS"
          + (f"  ⚠️ {n_fail} FAIL" if n_fail else "  ✅")
          + (f"  （另有 {n_retr} 项已撤回判据，实录于 gate_checks.csv）" if n_retr else ""))
    print(f"落盘：{OUT}")
    return 0 if n_fail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
