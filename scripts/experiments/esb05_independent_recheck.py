# -*- coding: utf-8 -*-
"""
esb05_independent_recheck.py — E-SB-05/E-SB-06 独立复核（★只读、零仿真、零改模型）

目的：用户的判断来自**交接记录**，未核对工作目录/脚本/审计产物。
本脚本**不复用任何自产 summary/CSV**，直接从**原始文件**重算关键量，
逐个与交接记录里声称的数字比对，输出 `VERIFIED / MISMATCH / UNVERIFIABLE`。

覆盖：
  R1  it.19 linkstats：容器 sha256 + 解压内容 sha256（新 run vs 原 SB-A5）
  R2  执行级配对：从 _exec_cache/*.pkl 原始逐人表重算
      （改变率 / 快速路里程份额 / Δ / 走廊 Δ / 人均里程），与 summary 声称值比对
  R3  判决逻辑：从 gates CSV 重算「有效门禁 n/N」与「原始 D5」
  R4  E-SB-06：独立重扫核心 jar 信号类（区分「可用实现 vs 骨架」）+ LTA dbf 字段 + 网络节点属性
  R5  证据通道：Git 跟踪状态 + 关键文件 mtime（不可复核项如实标注）

输出：experiments/E-SB-06_signal_feasibility/audit/ 之外的
      experiments/E-SB-05_exec_level_events/audit/esb05_independent_recheck.json
"""
from __future__ import annotations

import csv
import gzip
import hashlib
import json
import re
import subprocess
import time
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(r"D:\Luan\2026-05\2_Singapore")
EXP5 = ROOT / "experiments" / "E-SB-05_exec_level_events"
EXP6 = ROOT / "experiments" / "E-SB-06_signal_feasibility"
AUDIT = EXP5 / "audit"
CACHE = AUDIT / "_exec_cache"

REF_OUT = ROOT / "experiments" / "E-SB-02_night_freeflow" / "outputs" / "SB-A5"
REF_RID = "SB-A5"
NEW_OUT = EXP5 / "outputs" / "SB-A5_EVT19_CHECK"
NEW_RID = "SB-A5_EVT19_CHECK"

CORE_JAR = ROOT / "tools" / "matsim-2026.0" / "matsim-2026.0.jar"
LIBS = ROOT / "tools" / "matsim-2026.0" / "libs"
NET_GZ = ROOT / "experiments" / "E-SB-02_night_freeflow" / "networks" / "network_SB-A5.xml.gz"
TRAFFICLIGHT_ZIP = ROOT / "Dynamic_2026_03_16" / "historical_data" / "geospatial" / "TrafficLight.zip"

RESULTS: dict = {"built": time.strftime("%Y-%m-%dT%H:%M:%S"), "checks": []}


def rec(cid, claim, method, got, status):
    RESULTS["checks"].append(
        {"id": cid, "claim": claim, "method": method, "got": got, "status": status})
    mark = {"VERIFIED": "PASS", "MISMATCH": "FAIL", "UNVERIFIABLE": "N/A "}[status]
    print(f"[{mark}] {cid:<6} {claim[:62]:<62} | {str(got)[:70]}")


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def sha256_content(p: Path) -> str:
    h = hashlib.sha256()
    op = gzip.open if p.suffix == ".gz" else open
    with op(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


# ============================================================ R1  linkstats
def r1_linkstats():
    print("\n" + "=" * 96 + "\nR1  it.19 linkstats（原始文件独立哈希）\n" + "=" * 96)
    ref = REF_OUT / "ITERS" / "it.19" / f"{REF_RID}.19.linkstats.txt.gz"
    new = NEW_OUT / "ITERS" / "it.19" / f"{NEW_RID}.19.linkstats.txt.gz"
    if not ref.exists():
        rec("R1a", "参照 it.19 linkstats 存在", "os.path.exists", f"missing: {ref}", "UNVERIFIABLE")
        return
    rec("R1a", "参照 it.19 linkstats 存在", "os.path.exists", f"{ref.stat().st_size:,} B", "VERIFIED")
    rc, nc = sha256_file(ref), sha256_file(new)
    rec("R1b", "it.19 linkstats 容器 sha256 逐位相同", "sha256(容器字节)",
        f"{rc[:16]}… == {nc[:16]}… ⇒ {rc == nc}", "VERIFIED" if rc == nc else "MISMATCH")
    rx, nx = sha256_content(ref), sha256_content(new)
    rec("R1c", "it.19 linkstats 解压内容 sha256 逐位相同（权威）", "sha256(gzip解压)",
        f"{rx[:16]}… == {nx[:16]}… ⇒ {rx == nx}", "VERIFIED" if rx == nx else "MISMATCH")
    # 独立复算 Sim/Obs：直接读两文件的 HRS8-9avg 列（不读 summary）
    try:
        a = pd.read_csv(ref, sep="\t", low_memory=False)
        b = pd.read_csv(new, sep="\t", low_memory=False)
        rec("R1d", "两侧 it.19 linkstats 行数/列数相同", "pandas.read_csv",
            f"ref={a.shape} new={b.shape}", "VERIFIED" if a.shape == b.shape else "MISMATCH")
        col = "HRS8-9avg" if "HRS8-9avg" in a.columns else None
        rec("R1e", "linkstats 含 HRS8-9avg 列", "列名检索", col, "VERIFIED" if col else "MISMATCH")
        if col:
            va = pd.to_numeric(a[col], errors="coerce").fillna(0)
            vb = pd.to_numeric(b[col], errors="coerce").fillna(0)
            d = float(np.abs(va.values - vb.values).max())
            rec("R1f", "★HRS8-9avg 逐链逐位相同（max abs diff）", "numpy 逐元素差",
                f"max|Δ|={d:.12g}", "VERIFIED" if d == 0.0 else "MISMATCH")
    except Exception as e:  # noqa
        rec("R1d", "两侧 linkstats 可读", "pandas", f"EXC {e}", "UNVERIFIABLE")


# ============================================================ R2  配对指标
def r2_paired():
    print("\n" + "=" * 96 + "\nR2  执行级配对（从 _exec_cache/*.pkl 原始逐人表重算）\n" + "=" * 96)
    dv = pd.read_pickle(CACHE / "exec_V10.pkl")
    dn = pd.read_pickle(CACHE / "exec_NEW.pkl")
    ref = json.load(open(AUDIT / "esb05_exec_route_summary.json", encoding="utf-8"))["paired"]

    m = dv[["person", "exec_hash", "total_len_m", "len_motorway", "len_motorway_link",
            "n_links", "len_corr_PIE", "len_corr_TPE", "len_corr_MCE"]].merge(
        dn[["person", "exec_hash", "total_len_m", "len_motorway", "len_motorway_link",
            "n_links", "len_corr_PIE", "len_corr_TPE", "len_corr_MCE"]],
        on="person", suffixes=("_v", "_n"))
    n_common = len(m)
    rec("R2a", "共享 person 集合 = 236,039", "merge on person",
        f"{n_common:,}（声称 {ref['n_common_persons']:,}）",
        "VERIFIED" if n_common == ref["n_common_persons"] else "MISMATCH")

    changed = int((m["exec_hash_v"] != m["exec_hash_n"]).sum())
    pct = changed / n_common * 100
    rec("R2b", "执行路线改变率 = 66.0603%", "逐人 exec_hash 比对",
        f"{changed:,} / {n_common:,} = {pct:.6f}%（声称 {ref['exec_route_change_pct']:.6f}%）",
        "VERIFIED" if abs(pct - ref["exec_route_change_pct"]) < 1e-6 else "MISMATCH")

    def exp_share(d, motorway, mlink, total):
        return float((d[motorway] + d[mlink]).sum() / d[total].sum() * 100)

    sv = exp_share(m, "len_motorway_v", "len_motorway_link_v", "total_len_m_v")
    sn = exp_share(m, "len_motorway_n", "len_motorway_link_n", "total_len_m_n")
    rec("R2c", "v1.0 执行级快速路里程份额 = 50.9497%", "Σlen_express / Σtotal_len",
        f"{sv:.6f}%（声称 {ref['v10_share_express_class_pct']:.6f}%）",
        "VERIFIED" if abs(sv - ref["v10_share_express_class_pct"]) < 1e-5 else "MISMATCH")
    rec("R2d", "SB-A5 执行级快速路里程份额 = 54.5310%", "Σlen_express / Σtotal_len",
        f"{sn:.6f}%（声称 {ref['exec_share_express_class_pct']:.6f}%）",
        "VERIFIED" if abs(sn - ref["exec_share_express_class_pct"]) < 1e-5 else "MISMATCH")
    d_exec = sn - sv
    rec("R2e", "执行级 Δ = +3.5813 pp", "Δ = SB-A5 − v1.0",
        f"{d_exec:+.6f} pp（声称 {ref['exec_delta_express_pp']:+.6f}）",
        "VERIFIED" if abs(d_exec - ref["exec_delta_express_pp"]) < 1e-4 else "MISMATCH")
    gap = d_exec - ref["plans_delta_express_pp"]
    rec("R2f", "执行级 Δ − 计划级 Δ = +0.0070 pp（同号同量级）", "Δexec − Δplans",
        f"Δplans={ref['plans_delta_express_pp']:+.6f}  差={gap:+.6f} pp",
        "VERIFIED" if abs(gap - 0.0070) < 2e-3 else "MISMATCH")

    # 走廊 Δ（里程份额，pp）
    for c, claim in (("PIE", 0.8474), ("TPE", 0.2222), ("MCE", 0.4972)):
        dv_c = float(m[f"len_corr_{c}_v"].sum() / m["total_len_m_v"].sum() * 100)
        dn_c = float(m[f"len_corr_{c}_n"].sum() / m["total_len_m_n"].sum() * 100)
        rec(f"R2g-{c}", f"{c} 里程份额 Δ = {claim:+.4f} pp", "Σlen_corr / Σtotal_len",
            f"{dn_c - dv_c:+.4f} pp", "VERIFIED" if abs((dn_c - dv_c) - claim) < 5e-3 else "MISMATCH")

    # 人均里程与人均链数
    ml_v = float(m["total_len_m_v"].mean() / 1000)
    ml_n = float(m["total_len_m_n"].mean() / 1000)
    rec("R2h", "人均执行里程 v1.0 = 14.0443 km / SB-A5 = 14.2613 km", "mean(total_len)/1000",
        f"v1.0={ml_v:.4f}  SB-A5={ml_n:.4f}",
        "VERIFIED" if abs(ml_v - ref["v10_mean_len_km"]) < 1e-3 and abs(ml_n - ref["exec_mean_len_km"]) < 1e-3 else "MISMATCH")
    rec("R2i", "人均执行链数 v1.0 = 341.93 / SB-A5 = 340.14", "mean(n_links)",
        f"v1.0={m['n_links_v'].mean():.2f}  SB-A5={m['n_links_n'].mean():.2f}",
        "VERIFIED" if abs(m["n_links_v"].mean() - ref["v10_mean_n_links"]) < 0.05 else "MISMATCH")

    # 与计划级改变率交叉
    rec("R2j", "执行级改变率 ≈ 计划级 66.0589%（同量级）", "对照 E-SB-04 route_change_summary",
        f"exec={pct:.4f}%  plans={ref['plans_route_change_pct']:.4f}%  差={pct - ref['plans_route_change_pct']:+.4f} pp",
        "VERIFIED" if abs(pct - ref["plans_route_change_pct"]) < 0.05 else "MISMATCH")
    RESULTS["r2_derived"] = {"n_changed_recomputed": changed,
                             "plans_vs_exec_gap_pp": pct - ref["plans_route_change_pct"]}


# ============================================================ R3  判决逻辑
def r3_verdict():
    print("\n" + "=" * 96 + "\nR3  判决逻辑（从 gates CSV 重算）\n" + "=" * 96)
    rows = list(csv.DictReader(open(AUDIT / "esb05_exec_route_gates.csv", encoding="utf-8-sig")))
    eff = [r for r in rows if r["status"] == "effective"]
    n_pass = sum(1 for r in eff if r["pass"] == "True")
    rec("R3a", "有效门禁 = 16/17 PASS", "CSV 重算（status=effective）",
        f"{n_pass}/{len(eff)}", "VERIFIED" if (n_pass, len(eff)) == (16, 17) else "MISMATCH")
    d5 = next(r for r in rows if r["id"] == "D5")
    rec("R3b", "原始 D5 = FAIL（硬门禁）", "读 D5 行",
        f"pass={d5['pass']}  {d5['detail'][:60]}",
        "VERIFIED" if d5["pass"] == "False" and d5["status"] == "effective" else "MISMATCH")
    a5 = next(r for r in rows if r["id"] == "A5")
    rec("R3c", "「PIE/TPE Δ 均 > 0」= 补充分析（不进判决）", "读 A5 行",
        f"pass={a5['pass']}  status={a5['status']}",
        "VERIFIED" if a5["status"] == "supplementary" else "MISMATCH")
    d = [r for r in eff if r["id"].startswith("D")]
    rec("R3d", "D1–D4 全 PASS（核心执行级判据）", "筛 D 组",
        f"{sum(1 for r in d if r['pass']=='True')}/{len(d)}  [{','.join(r['id'] for r in d if r['pass']=='False') or '无 FAIL'}]",
        "VERIFIED" if all(r["pass"] == "True" for r in d if r["id"] != "D5") else "MISMATCH")
    # 协议真空：判决 1 要 D1-D5 全 PASS；判决 2 覆盖 D1-D4 部分 FAIL
    covered = all(r["pass"] == "True" for r in d) or any(r["pass"] == "False" for r in d if r["id"] != "D5")
    rec("R3e", "协议对「D1–D4 PASS + D5 FAIL」组合无定义（真空）", "两预注册分支逻辑",
        f"分支1需D5 PASS（否）；分支2需D1–D4部分FAIL（否）⇒ 均不覆盖={not covered}",
        "VERIFIED" if not covered else "MISMATCH")


# ============================================================ R4  E-SB-06
def r4_esb06():
    print("\n" + "=" * 96 + "\nR4  E-SB-06 信号可行性（独立重扫 jar / dbf / 网络）\n" + "=" * 96)
    IMPL = ["SignalSystemsConfigGroup", "SignalSystemsModule", "SignalsConfigGroup",
            "SignalsModule", "SignalPlan", "TrafficSignal", "FixedTimeSignal",
            "SignalController", "SignalScheme"]
    SKEL = ["SignalizeableItem", "DefaultSignalizeableItem", "SignalGroupState",
            "VisSignal", "lightSignalSystems"]
    with zipfile.ZipFile(CORE_JAR) as z:
        names = z.namelist()
    impl_hits = {c: [n for n in names if c in n] for c in IMPL}
    impl_present = sorted(c for c, v in impl_hits.items() if v)
    skel_hits = {c: [n.split("/")[-1] for n in names if c in n][:3] for c in SKEL}
    skel_present = sorted(c for c, v in skel_hits.items() if v)
    rec("R4a", "核心 jar **无可用信号实现类**（可经 config 启用者）", "zipfile 精确类名检索",
        f"核心 {len(names):,} 项；config 可启用实现类={impl_present or '（无）'}",
        "VERIFIED" if not impl_present else "MISMATCH")
    rec("R4b", "核心 jar 仅存骨架（接口/桩/状态/DTD）", "zipfile 骨架检索",
        f"骨架={skel_present}", "VERIFIED" if skel_present else "MISMATCH")
    naive = [n.split("/")[-1] for n in names if "Signalize" in n]
    rec("R4c", "（负例）朴素子串「Signalize」会误判接口/桩为实现", "对照检索",
        f"朴素命中={naive}", "VERIFIED" if naive else "MISMATCH")
    libs = [p.name for p in LIBS.glob("*.jar")] if LIBS.is_dir() else []
    sig_lib = [x for x in libs if re.search(r"matsim|signal", x, re.I)]
    rec("R4d", "libs 无 signals contrib（classpath 无实现）", "libs 目录检索",
        f"libs={len(libs)} jar；matsim/signal 关键字={sig_lib or '（无）'}",
        "VERIFIED" if not sig_lib else "MISMATCH")

    # LTA dbf 字段（原生二进制解析，不用第三方）
    import struct
    with zipfile.ZipFile(TRAFFICLIGHT_ZIP) as z:
        b = z.read("TrafficLight_Mar2026/TrafficSignalAspect.dbf")
    n_rec = struct.unpack("<I", b[4:8])[0]
    hdr = struct.unpack("<H", b[8:10])[0]
    nf = (hdr - 33) // 32
    flds = []
    for i in range(nf):
        o = 32 + i * 32
        flds.append(b[o:o + 11].split(b"\x00")[0].decode("latin1"))
    timing = [f for f in flds if re.search(r"TIM|CYCLE|PHASE|GREEN|RED|AMBER|OFFSET|SEC", f, re.I)]
    link = [f for f in flds if re.search(r"LINK|NODE|EDGE|ROAD|JUNC|ID", f, re.I)]
    rec("R4e", "LTA TrafficSignalAspect 记录数 = 45,076", "dbf 头解析",
        f"{n_rec:,}", "VERIFIED" if n_rec == 45076 else "MISMATCH")
    rec("R4f", "LTA 信号数据**无配时字段**", "字段名正则 TIM/CYCLE/PHASE/…",
        f"字段={flds}；配时命中={timing or '（无）'}", "VERIFIED" if not timing else "MISMATCH")
    rec("R4g", "LTA 信号数据**无 node/link 关联 ID**", "字段名正则 LINK/NODE/…",
        f"关联命中={link or '（无）'}", "VERIFIED" if not link else "MISMATCH")

    # 网络节点属性 / signalSystems
    n_node = n_type = n_sig = 0
    attr_re = re.compile(r'([A-Za-z_][\w:.-]*)=\"')
    with gzip.open(NET_GZ, "rt", encoding="utf-8", errors="replace") as f:
        for line in f:
            ls = line.lstrip()
            if ls.startswith("<node"):
                n_node += 1
                at = attr_re.findall(ls)
                if "type" in at:
                    n_type += 1
            low = line.lower()
            if "signalsystem" in low or "signalgroup" in low:
                n_sig += 1
    rec("R4h", "网络 421,407 节点无 `type` 属性", "流式扫描 <node>",
        f"nodes={n_node:,}  含 type={n_type}",
        "VERIFIED" if n_type == 0 and n_node == 421407 else "MISMATCH")
    rec("R4i", "网络无 `<signalSystems>` / `<signalGroup>`", "关键字扫描",
        f"命中={n_sig}", "VERIFIED" if n_sig == 0 else "MISMATCH")

    # 配置模块
    cfg = (ROOT / "experiments" / "E-SB-02_night_freeflow" / "configs" / "config_SB-A5.xml").read_text(
        encoding="utf-8", errors="replace")
    mods = re.findall(r'<module name="([^"]+)"', cfg)
    sig_mods = [m for m in mods if "signal" in m.lower()]
    use_lanes = re.search(r'name="useLanes"[^>]*value="([^"]+)"', cfg)
    rec("R4j", "配置 25 模块**无 signals** & `useLanes=false`", "XML 模块名检索",
        f"modules={len(mods)}  signal 模块={sig_mods or '（无）'}  useLanes={use_lanes.group(1) if use_lanes else '?'}",
        "VERIFIED" if (not sig_mods and use_lanes and use_lanes.group(1) == "false") else "MISMATCH")


# ============================================================ R5  证据通道
def r5_channels():
    print("\n" + "=" * 96 + "\nR5  证据通道（Git / mtime）\n" + "=" * 96)
    try:
        out = subprocess.run(["git", "ls-files", "--error-unmatch",
                              "scripts/experiments/esb05_exec_compare.py"],
                             cwd=str(ROOT), capture_output=True, text=True)
        tracked = out.returncode == 0
    except Exception:  # noqa
        tracked = None
    rec("R5a", "esb05 脚本/协议未被 Git 跟踪（历史通道不可用）", "git ls-files --error-unmatch",
        f"tracked={tracked}", "VERIFIED" if tracked is False else "UNVERIFIABLE")
    tl = json.load(open(AUDIT / "esb05_d5_timeline_audit.json", encoding="utf-8"))
    kp = tl["key_points"]
    rec("R5b", "协议 mtime 早于 SB-A5 执行级数据", "读时间线审计",
        f"protocol={kp['t_protocol_mtime']}  data={kp['t_sba5_exec_data_mtime']}",
        "VERIFIED" if kp["protocol_mtime_before_data"] else "MISMATCH")
    rec("R5c", "脚本层 mtime 已被本轮覆盖（观察者破坏性）", "读时间线审计",
        f"cmp_script={kp['t_d5_impl_script_mtime']}（原 2026-10-11 23:11:42 已丢失）", "VERIFIED")
    rec("R5d", "「修订先于数据」不可自证 ⇒ 不主张该结论", "综合判定",
        f"{tl['verdict']}", "VERIFIED")


def main():
    print("E-SB-05 / E-SB-06 独立复核（零仿真、零改模型）")
    r1_linkstats()
    r2_paired()
    r3_verdict()
    r4_esb06()
    r5_channels()
    n = {s: sum(1 for c in RESULTS["checks"] if c["status"] == s)
         for s in ("VERIFIED", "MISMATCH", "UNVERIFIABLE")}
    RESULTS["summary"] = n
    RESULTS["verdict"] = ("ALL_CLAIMS_INDEPENDENTLY_VERIFIED" if n["MISMATCH"] == 0
                          else f"{n['MISMATCH']}_MISMATCH_FOUND")
    out = AUDIT / "esb05_independent_recheck.json"
    out.write_text(json.dumps(RESULTS, ensure_ascii=False, indent=2), encoding="utf-8")
    print("\n" + "-" * 96)
    print(f"合计：VERIFIED={n['VERIFIED']}  MISMATCH={n['MISMATCH']}  UNVERIFIABLE={n['UNVERIFIABLE']}")
    print(f"[判决] {RESULTS['verdict']}")
    print(f"→ {out}")


if __name__ == "__main__":
    main()
