#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
E-SB-02C 派生器 | SB-A5 网络 + SB-A5 / SB-A5ind 配置（零仿真）
================================================================
用户裁定（2026-10-09）：
  夜晚 = N_adjacent{2026-05-06, 2026-05-07}
  分位 = p75
  SB8  = freespeed_new = max(75, 该链 v1.0 自由流)，仅对 SB8 来源生效
  臂   = SB-A5（v1.0 需求）+ SB-A5ind（Step5B 无 SpeedBand 需求）

只改一件事：把匹配链的 `freespeed` 换成夜间 p75 自由流代理，其余字节不变。
- 源网络 : reports/matsim_network/network_cleaned.xml.gz（冻结，只读）
- 目标   : experiments/E-SB-02_night_freeflow/networks/network_SB-A5.xml.gz
配置白名单：SB-A5 = {network.inputNetworkFile, controler.outputDirectory}
            SB-A5ind = 上述 + {plans.inputPlansFile}
"""
from __future__ import annotations
import gzip, hashlib, io, json, re, sys
from datetime import datetime
from pathlib import Path
import xml.etree.ElementTree as ET

import numpy as np
import pandas as pd

ROOT = Path(r"D:\Luan\2026-05\2_Singapore")
EXP = ROOT / "experiments" / "E-SB-02_night_freeflow"
CONFIG_DIR, NET_DIR = EXP / "configs", EXP / "networks"
POP_DIR, AUDIT_DIR, LOG_DIR, OUT_ROOT = EXP / "populations", EXP / "audit", EXP / "logs", EXP / "outputs"

SRC_CONFIG = ROOT / "matsim_final_7_6h" / "configs" / "config_W01_rc_min.xml"
SRC_NETWORK = ROOT / "reports" / "matsim_network" / "network_cleaned.xml.gz"
SRC_PLANS_V10 = ROOT / "matsim_final_7_6h" / "populations" / "pop_W01" / "population_lambda_0p075.xml.gz"
NETWORK_LINKS = ROOT / "reports" / "od_impedance" / "network_links.csv"
PREVIEW = ROOT / "reports" / "esb02_night_audit" / "night_network_preview.csv"

EXPECT_N_LINKS = 693575
FS_MIN_MS, FS_MAX_MS = 5.0 / 3.6, 90.0 / 3.6 + 1e-6
BAND8_PROXY = 75.0

CHECKS: list[dict] = []


def gate(cid, name, ok, detail=""):
    CHECKS.append({"check": cid, "name": name, "pass": bool(ok), "detail": str(detail)})
    print(f"  [{'PASS' if ok else 'FAIL'}] {cid:<6} {name}" + (f"  ({detail})" if detail else ""), flush=True)
    return bool(ok)


def sha16(p: Path) -> str:
    """★确定性内容哈希：解压后再哈希，避免 gzip 头 mtime 造成的不稳定。"""
    h = hashlib.sha256()
    if str(p).endswith(".gz"):
        with gzip.open(p, "rb") as f:
            for b in iter(lambda: f.read(1 << 20), b""):
                h.update(b)
    else:
        with open(p, "rb") as f:
            for b in iter(lambda: f.read(1 << 20), b""):
                h.update(b)
    return h.hexdigest()[:16]


LINK_RE = re.compile(r'<link\s+([^>]*?)/?>')
ATTR_RE = re.compile(r'(\w+)="([^"]*)"')


def all_params(path: Path) -> dict:
    out: dict[str, str] = {}

    def walk(ps, prefix):
        for p in ps.findall("param"):
            out[f"{prefix}.{p.get('name')}"] = p.get("value")
        for sub in ps.findall("parameterset"):
            walk(sub, f"{prefix}.{sub.get('name')}")

    root = ET.parse(str(path)).getroot()
    for mod in root.findall("module"):
        mn = mod.get("name")
        for p in mod.findall("param"):
            out[f"{mn}.{p.get('name')}"] = p.get("value")
        for ps in mod.findall("parameterset"):
            walk(ps, f"{mn}.{ps.get('name')}")
    return out


def set_param(txt: str, name: str, value: str):
    pat = re.compile(r'(<param\s+name="%s"\s+value=")([^"]*)(")' % re.escape(name))
    hits = pat.findall(txt)
    if len(hits) != 1:
        return txt, len(hits)
    return pat.sub(lambda m: m.group(1) + value + m.group(3), txt, count=1), 1


def build_mod_table() -> tuple[dict[str, str], dict]:
    """osm_edge_index -> matsim_link；夜间 p75 -> freespeed(m/s) 字符串。"""
    prev = pd.read_csv(PREVIEW, encoding="utf-8-sig")
    net = pd.read_csv(NETWORK_LINKS, encoding="utf-8-sig", low_memory=False,
                      usecols=["from_node", "to_node"])
    idx = prev.osm_edge_index.to_numpy(int)
    prev = prev.assign(matsim_link=[f"e{a}_{b}" for a, b in
                                    zip(net.from_node.to_numpy(int)[idx], net.to_node.to_numpy(int)[idx])])
    stat = {"n_preview_edges": int(len(prev)),
            "n_unique_links": int(prev.matsim_link.nunique()),
            "n_collisions": int(len(prev) - prev.matsim_link.nunique())}
    # 同一 matsim_link 多行（平行 LTA 边）取中位
    g = prev.groupby("matsim_link").agg(fs_new_kmh=("fs_SB5_p75", "median"),
                                        fs_v10_kmh=("fs_v1p0", "median"),
                                        highway=("highway", "first")).reset_index()
    g["fs_new_str"] = (g.fs_new_kmh / 3.6).map(lambda v: f"{v:.6f}")
    return dict(zip(g.matsim_link, g.fs_new_str)), {"stat": stat, "df": g}


EXPECT_IN_NET = 91956   # 既有已证事实：92,149 具名链中 91,956 在仿真网络内（另 193 不在）
EXPECT_MISSING = 193


def build_network(mod: dict[str, str]):
    NET_DIR.mkdir(parents=True, exist_ok=True)
    out = NET_DIR / "network_SB-A5.xml.gz"
    # 先读源网络的 id->freespeed 字符串，决定"真正变化"的集合
    src_fs: dict[str, str] = {}
    n_link = 0
    with gzip.open(SRC_NETWORK, "rt", encoding="utf-8", newline="") as f:
        for ln in f:
            if "<link " in ln and 'id="' in ln:
                n_link += 1
                m = LINK_RE.search(ln)
                if m:
                    a = dict(ATTR_RE.findall(m.group(1)))
                    src_fs[a.get("id", "")] = a.get("freespeed", "")
    gate("N1", f"源网络链路数 == {EXPECT_N_LINKS}", n_link == EXPECT_N_LINKS, f"n={n_link}")
    missing = [k for k in mod if k not in src_fs]
    present = {k: v for k, v in mod.items() if k in src_fs}
    gate("N2a", "在网目标链数 == 既有已证事实 91,956", len(present) == EXPECT_IN_NET,
         f"in_network={len(present)}")
    gate("N2b", "不在网链数 == 既有已证事实 193（非映射错误）", len(missing) == EXPECT_MISSING,
         f"missing={len(missing)}")
    changed = {k: v for k, v in present.items() if src_fs[k] != v}
    unchanged = len(present) - len(changed)
    print(f"       在网目标 {len(present):,} 链；字符串真变化 {len(changed):,}；四舍五入后不变 {unchanged:,}")

    # ★确定性写出：mtime=0、无 filename，逐字节可复现
    with open(out, "wb") as raw:
        with gzip.GzipFile(filename="", mode="wb", compresslevel=6, fileobj=raw, mtime=0) as gz:
            with gzip.open(SRC_NETWORK, "rt", encoding="utf-8", newline="") as g:
                for ln in g:
                    if "<link " in ln and 'id="' in ln:
                        m = LINK_RE.search(ln)
                        if m:
                            lid = dict(ATTR_RE.findall(m.group(1))).get("id", "")
                            if lid in changed:
                                ln = re.sub(r'(\bfreespeed=")([^"]*)(")',
                                            lambda mm: mm.group(1) + changed[lid] + mm.group(3), ln, count=1)
                    gz.write(ln.encode("utf-8"))
    return out, changed, src_fs


def verify_network(out: Path, changed: dict[str, str]):
    """逐行对比源 vs 输出：差异集合必须恰等于 changed。"""
    diff_ids: set[str] = set()
    n_out = 0
    with gzip.open(SRC_NETWORK, "rt", encoding="utf-8", newline="") as a, \
         gzip.open(out, "rt", encoding="utf-8", newline="") as b:
        for la, lb in zip(a, b):
            if "<link " in lb and 'id="' in lb:
                n_out += 1
            if la != lb:
                m = LINK_RE.search(lb)
                if m:
                    diff_ids.add(dict(ATTR_RE.findall(m.group(1))).get("id", ""))
    gate("N3", "输出网络链路数 == 源", n_out == EXPECT_N_LINKS, f"n={n_out}")
    gate("N4", "逐行差异集合恰等于目标变化集合（无越界/无遗漏）",
         diff_ids == set(changed), f"diff={len(diff_ids)} mod={len(changed)}")
    # SB8/范围
    fs = []
    with gzip.open(out, "rt", encoding="utf-8", newline="") as g:
        for ln in g:
            if "<link " in ln and 'id="' in ln:
                m = LINK_RE.search(ln)
                if m:
                    a = dict(ATTR_RE.findall(m.group(1)))
                    fs.append(float(a["freespeed"]))
    fs = np.array(fs)
    gate("N5", "freespeed 全部落入 [5 km/h, 90 km/h]", bool(fs.min() >= FS_MIN_MS - 1e-9 and fs.max() <= FS_MAX_MS),
         f"min={fs.min()*3.6:.2f} max={fs.max()*3.6:.2f} km/h")
    return True


def build_configs(net_path: Path, ind_pop: Path | None):
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    src = io.open(SRC_CONFIG, encoding="utf-8", newline="").read()
    out = {}
    # ---- SB-A5（需求 = v1.0）
    t, nk = set_param(src, "inputNetworkFile", str(net_path))
    assert nk == 1, "inputNetworkFile not unique"
    t, nk = set_param(t, "outputDirectory", str(OUT_ROOT / "SB-A5"))
    assert nk == 1, "outputDirectory not unique"
    t, nk = set_param(t, "runId", "SB-A5")          # ★否则继承 v1.0 的 W01_rc_min
    assert nk == 1, "runId not unique"
    p = CONFIG_DIR / "config_SB-A5.xml"
    io.open(p, "w", encoding="utf-8", newline="").write(t)
    out["SB-A5"] = p
    # ---- SB-A5ind（需求 = Step5B 无 SpeedBand）
    t2 = io.open(SRC_CONFIG, encoding="utf-8", newline="").read()
    t2, nk = set_param(t2, "inputNetworkFile", str(net_path))
    assert nk == 1
    t2, nk = set_param(t2, "outputDirectory", str(OUT_ROOT / "SB-A5ind"))
    assert nk == 1
    t2, nk = set_param(t2, "runId", "SB-A5ind")
    assert nk == 1
    t2, nk = set_param(t2, "inputPlansFile", str(ind_pop))
    assert nk == 1, "inputPlansFile not unique"
    p2 = CONFIG_DIR / "config_SB-A5ind.xml"
    io.open(p2, "w", encoding="utf-8", newline="").write(t2)
    out["SB-A5ind"] = p2

    # 门禁：diff 白名单
    base = all_params(SRC_CONFIG)
    exp_a5 = {"network.inputNetworkFile", "controller.outputDirectory", "controller.runId"}
    exp_ind = exp_a5 | {"plans.inputPlansFile"}
    for arm, path, expect in [("SB-A5", out["SB-A5"], exp_a5), ("SB-A5ind", out["SB-A5ind"], exp_ind)]:
        cur = all_params(path)
        diff = {k for k in set(base) | set(cur) if base.get(k) != cur.get(k)}
        gate(f"C-{arm}", f"{arm} 配置 diff == 预期白名单 {len(expect)} 项",
             diff == expect, f"diff={sorted(diff)}")
    return out


def main():
    for d in (CONFIG_DIR, NET_DIR, POP_DIR, AUDIT_DIR, LOG_DIR, OUT_ROOT):
        d.mkdir(parents=True, exist_ok=True)
    print("=" * 84)
    print("E-SB-02C 派生 | SB-A5 网络 + 配置（零仿真）")
    print("=" * 84)
    print(f"  源网络 : {SRC_NETWORK.relative_to(ROOT)}  sha16={sha16(SRC_NETWORK)}")
    print(f"  源配置 : {SRC_CONFIG.relative_to(ROOT)}  sha16={sha16(SRC_CONFIG)}")

    mod, meta = build_mod_table()
    s = meta["stat"]
    print(f"\n[1] 目标链：preview {s['n_preview_edges']:,} 边 -> 唯一 matsim_link {s['n_unique_links']:,} "
          f"(平行合并 {s['n_collisions']})")
    net_path, changed, src_fs = build_network(mod)
    verify_network(net_path, changed)
    print(f"       输出网络 sha16={sha16(net_path)}  size={net_path.stat().st_size/1e6:.1f} MB")

    # 分等级改动统计
    g = meta["df"].copy()
    g["chg"] = g.matsim_link.map(lambda k: k in changed)
    summ = (g.groupby("highway").agg(n=("matsim_link", "size"), n_chg=("chg", "sum"),
                                     fs_v10=("fs_v10_kmh", "median"), fs_new=("fs_new_kmh", "median"))
            .reset_index().sort_values("n", ascending=False))
    summ["chg_pct"] = summ.n_chg / summ.n * 100
    summ.to_csv(AUDIT_DIR / "esb02_network_change_by_highway.csv", index=False, encoding="utf-8-sig")
    print("\n[2] 分等级改动（Top 10）：")
    print(summ.head(10).round(2).to_string(index=False))

    ind_pop = POP_DIR / "population_SB-A5ind_lambda_0p075.xml.gz"
    cfgs = build_configs(net_path, ind_pop)
    print(f"\n[3] 配置：{ {k: str(v.relative_to(ROOT)) for k, v in cfgs.items()} }")

    result = {
        "generated": datetime.now().isoformat(timespec="seconds"),
        "decisions": {"nights": "N_adjacent{2026-05-06,2026-05-07}", "quantile": "p75",
                      "band8_rule": "max(75, v1.0 freespeed) for SB8 only",
                      "arms": ["SB-A5", "SB-A5ind"]},
        "source_network": {"path": str(SRC_NETWORK.relative_to(ROOT)), "sha16": sha16(SRC_NETWORK)},
        "new_network": {"path": str(net_path.relative_to(ROOT)), "sha16": sha16(net_path),
                        "n_target_links": len(mod), "n_changed_links": len(changed)},
        "source_config": {"path": str(SRC_CONFIG.relative_to(ROOT)), "sha16": sha16(SRC_CONFIG)},
        "configs": {k: str(v.relative_to(ROOT)) for k, v in cfgs.items()},
        "ind_population_expected": str(ind_pop.relative_to(ROOT)),
        "checks": CHECKS,
        "verdict": "READY" if all(c["pass"] for c in CHECKS) else "FAILED",
    }
    with open(AUDIT_DIR / "esb02_build_gates.json", "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    pd.DataFrame(CHECKS).to_csv(AUDIT_DIR / "esb02_build_gates.csv", index=False, encoding="utf-8-sig")
    n_pass = sum(c["pass"] for c in CHECKS)
    print("\n" + "=" * 84)
    print(f"判决：{result['verdict']}  （门禁 {n_pass}/{len(CHECKS)}）")
    print("=" * 84)
    return 0 if result["verdict"] == "READY" else 1


if __name__ == "__main__":
    raise SystemExit(main())
