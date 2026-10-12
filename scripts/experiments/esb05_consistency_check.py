#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""
esb05_consistency_check.py — E-SB-05 阶段 2：重跑 vs 原 SB-A5 的运行一致性检查（★只读）
========================================================================================
任务书 §2.1 要求：「比较 it.19 的逐链 LinkStats、HRS8-9avg、观测域流量总量和 Sim/Obs。
事件输出不应改变仿真动力学；若出现超出预定容差的差异，应先查明原因。」

本脚本给出**分级证据**：
  L1 字节级：it.19 linkstats.gz / legHistogram / legdurations / output_links / output_plans /
             output_network / vehicles / counts / scorestats 的 sha256 逐位比较。
  L2 数值级：若 L1 任一不同，逐链解析 154 列做差值统计（max|Δ|、n_diff、相对差分位）。
  L3 口径级：构造 it.10-19 全时段 cycle-mean，复算观测域 ΣQ 与 Sim/Obs（08-09），
             与 E-SB-03/E-SB-04 记录的 SB-A5 = 1.0600691 对齐（±1e-6）。

预注册容差（写入 PROTOCOL §3）
  T1  it.19 linkstats.gz sha256 相同                 -> PASS_STRICT（首要）
  T2  全部对比文件 sha256 相同                        -> PASS_STRICT
  T3  若 sha256 不同而所有数值列 max|Δ| == 0          -> PASS_EQUIVALENT（仅容器/顺序差异）
  T4  若 max 相对差 < 1e-9                            -> PASS_TOLERATED
  T5  否则                                            -> FAIL ⇒ 保留 PLANS_LEVEL

产物 → experiments/E-SB-05_exec_level_events/audit/
        esb05_consistency_files.csv
        esb05_consistency_numeric.csv
        esb05_consistency_summary.json
"""
from __future__ import annotations

import csv
import gzip
import hashlib
import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(r"D:\Luan\2026-05\2_Singapore")
EXP = ROOT / "experiments" / "E-SB-05_exec_level_events"
AUDIT = EXP / "audit"
AUDIT.mkdir(parents=True, exist_ok=True)

REF_OUT = ROOT / "experiments" / "E-SB-02_night_freeflow" / "outputs" / "SB-A5"
REF_RID = "SB-A5"
NEW_OUT = EXP / "outputs" / "SB-A5_EVT19_CHECK"
NEW_RID = "SB-A5_EVT19_CHECK"

E3_AUDIT = ROOT / "experiments" / "E-SB-03_flow_shift_audit" / "audit"
V10_ALL = E3_AUDIT / "v1.0_allhours_conv.linkstats.txt.gz"
A5_ALL = E3_AUDIT / "SB-A5_allhours_conv.linkstats.txt.gz"

CW = ROOT / "reports" / "od_final_calibration_crosswalk_7_3_6" / "final_calibration_crosswalk.csv"
TRAFFIC = ROOT / "Singapore_OD_MATSim_FinalData" / "08_TrafficCount" / "TrafficFlow_Data.json"
SEC_GEO = ROOT / "reports" / "od_structure_7_6c" / "section_geography.csv"

SCALE = 459794.0 / 200000.0
EXPECTED = {"v1.0": 0.9993348, "SB-A5": 1.0600691}
CYCLE_ITERS = list(range(10, 20))
HOUR_COLS = [f"HRS{h}-{h+1}avg" for h in range(24)] + ["HRS0-24avg"]

REF_IT19_SHA = "ddc879a07dfedb429367e90b8f880afc6ee630886d1d0bfc1129297bd43f9d3e"
REF_IT19_SIZE = 23055353

# 运行无关的「外观文件」（含 runId / 输出路径 / 墙钟时间），不参与一致性判定
EXCLUDE_PATTERNS = (
    "output_config.xml", "output_config_reduced.xml",
    "logfile.log", "logfileWarningsErrors.log", "stopwatch.csv",
)
EXCLUDE_DIRS = ("tmp",)

GATES: list[dict] = []


def gate(cid, name, ok, detail="", status="effective"):
    GATES.append({"id": cid, "gate": name, "pass": bool(ok), "status": status, "detail": str(detail)})
    tag = "" if status == "effective" else f"  «{status}»"
    print(f"  [{'PASS' if ok else 'FAIL'}] {cid:<7} {name}" + (f"  | {detail}" if detail else "") + tag, flush=True)
    return bool(ok)


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 22), b""):
            h.update(b)
    return h.hexdigest()


def sha256_content(p: Path) -> str:
    """★内容级哈希：gz 先解压。容器字节可能因 deflate 分块不同而不同，内容才是权威。"""
    if str(p).endswith(".gz"):
        h = hashlib.sha256()
        with gzip.open(p, "rb") as f:
            for b in iter(lambda: f.read(1 << 22), b""):
                h.update(b)
        return h.hexdigest()
    return sha256_file(p)


def rel_files(root: Path, rid: str) -> dict[str, Path]:
    """相对路径 **归一化掉 runId** —— 否则两侧文件名永不相等（SB-A5.* vs SB-A5_EVT19_CHECK.*），
    文件表会静默变成空比对（本项目第 9 次「假门禁」）。长 runId 先替换，避免前缀吞并。"""
    out: dict[str, Path] = {}
    for p in root.rglob("*"):
        if not p.is_file():
            continue
        rel = p.relative_to(root).as_posix()
        if any(seg in rel for seg in EXCLUDE_DIRS):
            continue
        rel = rel.replace(rid, "<RID>")
        out[rel] = p
    if not out:
        raise RuntimeError(f"rel_files 为空：{root}")
    return out


# --------------------------------------------------------------------------
# L3：观测域口径复算（复刻 esb03_flow_shift_audit.section_table / pooled）
# --------------------------------------------------------------------------
def build_allhour_cycle(out_dir: Path, run_id: str, dest: Path) -> tuple[pd.DataFrame, int]:
    if dest.exists():
        return pd.read_csv(dest, sep="\t", dtype={c: "float64" for c in HOUR_COLS}), 10
    acc, ref_index, n = None, None, 0
    for it in CYCLE_ITERS:
        p = out_dir / "ITERS" / f"it.{it}" / f"{run_id}.{it}.linkstats.txt.gz"
        if not p.exists():
            continue
        df = pd.read_csv(p, sep="\t", usecols=["LINK"] + HOUR_COLS,
                         dtype={c: "float64" for c in HOUR_COLS}, low_memory=False)
        df = df.set_index("LINK")
        if ref_index is None:
            ref_index, acc = df.index, df
        else:
            if not ref_index.equals(df.index):
                raise RuntimeError(f"{run_id} it.{it} LINK 索引与 it.{CYCLE_ITERS[0]} 不一致")
            acc = acc.add(df, fill_value=0.0)
        n += 1
    if acc is None:
        raise RuntimeError(f"{run_id}: 无 it.10-19 linkstats")
    acc = (acc / n).reset_index()
    acc.to_csv(dest, sep="\t", index=False)
    return acc, n


def section_table(cw, obs, sim, col="HRS8-9avg", agg="median"):
    x = cw.merge(obs[["LinkID", "RoadCat", "RoadName", "obs_7_8", "obs_8_9", "obs_am"]],
                 left_on="lta_linkid", right_on="LinkID", how="inner")
    x = x.merge(sim[["LINK", col]], left_on="matsim_link_id", right_on="LINK", how="left")

    def f(s):
        s = s.dropna()
        if not len(s):
            return np.nan
        return float(s.median()) if agg == "median" else float(s.mean())

    g = x.groupby("lta_linkid")
    out = pd.DataFrame({
        "val_raw": g[col].apply(f),
        "n_edges": g["matsim_link_id"].nunique(),
        "RoadCat": g["RoadCat"].first(),
        "RoadName": g["RoadName"].first(),
        "obs_8_9": g["obs_8_9"].first(),
    }).reset_index()
    out["val_scaled"] = out["val_raw"] * SCALE
    return out


def pooled(df, sim_col, obs_col):
    o = df[obs_col].sum()
    return float(df[sim_col].sum() / o) if o else float("nan")


def main() -> int:
    t0 = time.time()
    print("=" * 100)
    print("E-SB-05 阶段 2：重跑 vs 原 SB-A5 运行一致性检查")
    print("=" * 100)
    if not (NEW_OUT / "ITERS" / "it.19").exists():
        print(f"[ABORT] 新 run it.19 尚不存在：{NEW_OUT / 'ITERS' / 'it.19'}")
        return 3

    # ---------------- L1 字节级 ----------------
    print("\n[L1] 字节级比较（sha256，排除 runId/路径/墙钟类外观文件）")
    rf = rel_files(REF_OUT, REF_RID)
    nf = rel_files(NEW_OUT, NEW_RID)
    print(f"    归一化后参照 {len(rf)} 项 / 新 run {len(nf)} 项（文件名中的 runId 已折叠为 <RID>）")
    rows = []
    for rel in sorted(set(rf) | set(nf)):
        if any(pat in rel for pat in EXCLUDE_PATTERNS):
            rows.append({"file": rel, "class": "cosmetic_skipped",
                         "ref_bytes": rf[rel].stat().st_size if rel in rf else None,
                         "new_bytes": nf[rel].stat().st_size if rel in nf else None,
                         "same": None, "note": "含 runId/路径/墙钟，不判一致性"})
            continue
        if rel not in rf:
            rows.append({"file": rel, "class": "new_only", "ref_bytes": None,
                         "new_bytes": nf[rel].stat().st_size, "same": None,
                         "note": "本次新增（events 产物，符合预期）"})
            continue
        if rel not in nf:
            rows.append({"file": rel, "class": "missing_in_new", "ref_bytes": rf[rel].stat().st_size,
                         "new_bytes": None, "same": None, "note": "新 run 缺失"})
            continue
        sr, sn = rf[rel].stat().st_size, nf[rel].stat().st_size
        # ★以「解压后内容」为权威判据；容器字节仅作参考（gz 分块可能不同）
        same = (sr == sn) and (sha256_content(rf[rel]) == sha256_content(nf[rel]))
        rows.append({"file": rel, "class": "deterministic", "ref_bytes": sr, "new_bytes": sn,
                     "same": bool(same), "note": ""})
    fdf = pd.DataFrame(rows)
    fdf.to_csv(AUDIT / "esb05_consistency_files.csv", index=False, encoding="utf-8-sig")
    det = fdf[fdf["class"] == "deterministic"]
    n_same, n_det = int(det["same"].sum()), len(det)
    gate("C00", "文件比对**非空**（≥10 项确定性产物参与；防空表假门禁）",
         n_det >= 10, f"n_deterministic={n_det} n_same={n_same}")
    for _, r in det.iterrows():
        flag = "SAME" if r["same"] else "DIFF"
        print(f"    {flag}  {int(r['new_bytes']):>12,} B  {r['file']}")
    for _, r in fdf[fdf["class"] != "deterministic"].iterrows():
        print(f"    ----  {r['class']:<17} {r['file']}")

    # ---------------- L1 主门：it.19 linkstats ----------------
    print("\n[L1-主门] it.19 逐链 LinkStats")
    ref_ls = REF_OUT / "ITERS" / "it.19" / f"{REF_RID}.19.linkstats.txt.gz"
    new_ls = NEW_OUT / "ITERS" / "it.19" / f"{NEW_RID}.19.linkstats.txt.gz"
    ref_sha, new_sha = sha256_file(ref_ls), sha256_file(new_ls)
    ref_ct, new_ct = sha256_content(ref_ls), sha256_content(new_ls)
    ref_sz, new_sz = ref_ls.stat().st_size, new_ls.stat().st_size
    gate("C01", "it.19 linkstats.gz 存在且可读", True, f"new={new_sz:,} B")
    gate("C02", "it.19 linkstats.gz 容器 sha256 == 参照哈希在册", ref_sha == REF_IT19_SHA, ref_sha[:24] + "…")
    gate("C03", "it.19 linkstats.gz 体积逐字节相同", ref_sz == new_sz, f"ref={ref_sz:,} new={new_sz:,}")
    ls_same = (ref_sha == new_sha)
    gate("C03b", "it.19 linkstats.gz 容器 sha256 逐位相同", ls_same,
         f"ref={ref_sha[:24]}… new={new_sha[:24]}…")
    ls_same_ct = (ref_ct == new_ct)
    gate("C03c", "★it.19 linkstats 解压内容 sha256 逐位相同（全 154 列，含 HRS8-9avg）",
         ls_same_ct, f"content={new_ct[:24]}… ref={ref_ct[:24]}…")
    ls_same = ls_same_ct

    # ---------------- L2 数值级（仅当 L1 不同） ----------------
    num_rows = []
    num_verdict = "NOT_NEEDED"
    if not ls_same:
        print("\n[L2] 数值级：逐链逐列差值（L1 不同，故必须做）")
        a = pd.read_csv(ref_ls, sep="\t", low_memory=False)
        b = pd.read_csv(new_ls, sep="\t", low_memory=False)
        gate("C04", "两文件行数相同", len(a) == len(b), f"ref={len(a)} new={len(b)}")
        gate("C05", "LINK 集合逐位相同", set(a["LINK"]) == set(b["LINK"]),
             f"∩={len(set(a['LINK']) & set(b['LINK']))}")
        a = a.set_index("LINK").sort_index()
        b = b.set_index("LINK").sort_index()
        cols = [c for c in a.columns if pd.api.types.is_numeric_dtype(a[c]) and c in b.columns]
        worst_abs, worst_rel = 0.0, 0.0
        n_diff_cols = 0
        for c in cols:
            d = (b[c] - a[c])
            mabs = float(np.nanmax(np.abs(d.values))) if len(d) else 0.0
            denom = np.maximum(np.abs(a[c].values), 1e-12)
            mrel = float(np.nanmax(np.abs(d.values) / denom)) if len(d) else 0.0
            ndiff = int(np.nansum(d.values != 0))
            if ndiff:
                n_diff_cols += 1
            num_rows.append({"column": c, "max_abs_diff": mabs, "max_rel_diff": mrel, "n_rows_diff": ndiff})
            worst_abs = max(worst_abs, mabs)
            worst_rel = max(worst_rel, mrel)
        pd.DataFrame(num_rows).to_csv(AUDIT / "esb05_consistency_numeric.csv",
                                      index=False, encoding="utf-8-sig")
        gate("C06", "全部数值列 max|Δ| == 0", worst_abs == 0.0,
             f"max|Δ|={worst_abs:.3e} max_rel={worst_rel:.3e} diff_cols={n_diff_cols}/{len(cols)}")
        num_verdict = ("IDENTICAL_NUMERIC" if worst_abs == 0.0
                       else ("TOLERATED" if worst_rel < 1e-9 else "FAIL"))

    # ---------------- L3 口径级 ----------------
    print("\n[L3] 观测域口径复算（it.10-19 cycle-mean → 576 断面 → Sim/Obs）")
    sys.path.insert(0, str(ROOT / "scripts" / "od"))
    try:
        import compare_final_crosswalk_7_3_6b as bt  # noqa: E402
        cw = bt.normalize_crosswalk(CW, "final")
        obs = bt.load_traffic(TRAFFIC)
        ok_in = True
    except Exception as e:  # noqa: BLE001
        print(f"    [WARN] 冻结口径模块不可用：{type(e).__name__}: {e}")
        cw = pd.read_csv(CW, encoding="utf-8-sig", low_memory=False); ok_in = False
        obs = None
    gate("C07", "crosswalk 归一化 = 3,193 匹配边 / 576 断面",
         ok_in and len(cw) == 3193 and cw["lta_linkid"].nunique() == 576,
         f"edges={len(cw)} sections={cw['lta_linkid'].nunique()}")

    res = {}
    if obs is not None:
        # v1.0（冻结 cycle 文件，直接复用 E-SB-03 产物）
        sim_v10 = pd.read_csv(V10_ALL, sep="\t", dtype={c: "float64" for c in HOUR_COLS}, low_memory=False)
        s_v10 = section_table(cw, obs, sim_v10)
        r_v10 = pooled(s_v10, "val_scaled", "obs_8_9")
        gate("C08", f"复算 v1.0 FROZEN(08-09) == {EXPECTED['v1.0']}（±1e-6）",
             abs(r_v10 - EXPECTED["v1.0"]) < 1e-6, f"got={r_v10:.7f}")

        # SB-A5（复用 E-SB-03 冻结 cycle 文件）
        sim_a5 = pd.read_csv(A5_ALL, sep="\t", dtype={c: "float64" for c in HOUR_COLS}, low_memory=False)
        s_a5 = section_table(cw, obs, sim_a5)
        r_a5 = pooled(s_a5, "val_scaled", "obs_8_9")
        gate("C09", f"复算原 SB-A5 cycle(08-09) == {EXPECTED['SB-A5']}（±1e-6）",
             abs(r_a5 - EXPECTED["SB-A5"]) < 1e-6, f"got={r_a5:.7f}")

        # ★新 run：自行构造 it.10-19 cycle-mean
        new_conv = AUDIT / f"{NEW_RID}_allhours_conv.linkstats.txt.gz"
        sim_new, n_used = build_allhour_cycle(NEW_OUT, NEW_RID, new_conv)
        print(f"    新 run it.10-19 cycle-mean：iters={n_used} links={len(sim_new):,} -> {new_conv.name}")
        s_new = section_table(cw, obs, sim_new)
        r_new = pooled(s_new, "val_scaled", "obs_8_9")
        gate("C10", f"★新 run cycle(08-09) Sim/Obs == 原 SB-A5 {EXPECTED['SB-A5']}（±1e-6）",
             abs(r_new - EXPECTED["SB-A5"]) < 1e-6, f"got={r_new:.7f}")

        # 观测域流量总量
        tot = {
            "observed_total_obs_8_9": float(s_new["obs_8_9"].sum()),
            "v1.0_matched_edges_raw": float(sim_v10.set_index("LINK")["HRS8-9avg"].reindex(
                cw["matsim_link_id"]).fillna(0).sum()),
            "SB-A5_matched_edges_raw": float(sim_a5.set_index("LINK")["HRS8-9avg"].reindex(
                cw["matsim_link_id"]).fillna(0).sum()),
            "NEW_matched_edges_raw": float(sim_new.set_index("LINK")["HRS8-9avg"].reindex(
                cw["matsim_link_id"]).fillna(0).sum()),
            "SB-A5_section_scaled_total": float(s_a5["val_scaled"].sum()),
            "NEW_section_scaled_total": float(s_new["val_scaled"].sum()),
            "v1.0_section_scaled_total": float(s_v10["val_scaled"].sum()),
        }
        print("    观测域总量（raw = 匹配边 HRS8-9avg 直接求和；scaled = 断面 median×SCALE 求和）")
        for k, v in tot.items():
            print(f"      {k:34s} {v:>16,.4f}")
        gate("C11", "★新 run 匹配边 ΣQ(raw) == 原 SB-A5（±1e-9 相对）",
             abs(tot["NEW_matched_edges_raw"] - tot["SB-A5_matched_edges_raw"]) <= 1e-9 * max(1.0, abs(tot["SB-A5_matched_edges_raw"])),
             f"new={tot['NEW_matched_edges_raw']:,.4f} ref={tot['SB-A5_matched_edges_raw']:,.4f}")
        gate("C12", "★新 run 断面 ΣQ(scaled) == 原 SB-A5（±1e-9 相对）",
             abs(tot["NEW_section_scaled_total"] - tot["SB-A5_section_scaled_total"]) <= 1e-9 * max(1.0, abs(tot["SB-A5_section_scaled_total"])),
             f"new={tot['NEW_section_scaled_total']:,.4f} ref={tot['SB-A5_section_scaled_total']:,.4f}")
        # ★负例（分辨力）：新 run 必须 ≠ v1.0
        gate("C13", "负例：新 run 的 Sim/Obs ≠ v1.0 的 0.9993348（检查有分辨力）",
             abs(r_new - EXPECTED["v1.0"]) > 1e-3, f"new={r_new:.7f} vs v1.0={EXPECTED['v1.0']}")
        res = {"SimObs_v1.0": r_v10, "SimObs_SB-A5": r_a5, "SimObs_NEW": r_new,
               "cycle_iters_used": n_used, "totals": tot}
    else:
        for cid in ("C08", "C09", "C10", "C11", "C12", "C13"):
            gate(cid, "（口径复算，冻结模块不可用）", False, "BLOCKED", status="blocked")

    # ---------------- 总判决 ----------------
    eff = [g for g in GATES if g["status"] == "effective"]
    n_fail = sum(1 for g in eff if not g["pass"])
    if n_fail == 0 and ls_same:
        verdict = "CONSISTENT_STRICT"
    elif n_fail == 0:
        verdict = f"CONSISTENT_{num_verdict}"
    else:
        verdict = "INCONSISTENT"
    summary = {
        "built": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "elapsed_sec": round(time.time() - t0, 1),
        "ref_run": REF_RID, "new_run": NEW_RID,
        "files_same": n_same, "files_deterministic": n_det,
        "linkstats_identical": bool(ls_same),
        "linkstats_ref_sha256": ref_sha, "linkstats_new_sha256": new_sha,
        "numeric_verdict": num_verdict,
        "observation_domain": res,
        "gates": GATES,
        "verdict": verdict,
    }
    (AUDIT / "esb05_consistency_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    with open(AUDIT / "esb05_consistency_gates.csv", "w", newline="", encoding="utf-8-sig") as fh:
        w = csv.DictWriter(fh, fieldnames=["id", "gate", "pass", "status", "detail"])
        w.writeheader(); w.writerows(GATES)

    print("-" * 100)
    print(f"确定性产物 sha256 相同：{n_same}/{n_det}")
    print(f"it.19 linkstats 逐位相同：{ls_same}")
    print(f"有效门禁：{len(eff) - n_fail}/{len(eff)} PASS")
    print(f"[判决] {verdict}")
    print(f"产物：{AUDIT/'esb05_consistency_summary.json'}  ({summary['elapsed_sec']}s)")
    return 0 if n_fail == 0 else 4


if __name__ == "__main__":
    sys.exit(main())
