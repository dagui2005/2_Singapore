#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""
E-SB-02C ｜ SB-A5ind 独立需求（零 SpeedBand）—— **全链派生器 v2（修订）**
================================================================================
★ 为什么是 v2（真缺陷，非风格）
--------------------------------------------------------------------------------
v1 只跑了「Step 6.2」一步，就直接把它写出的 `population_lambda_*.xml.gz` 当作
SB-A5ind 的需求。**三处致命错**：

  (1) **格式**：Step 6.2 用 `xml.etree` 直写，**缺 `<!DOCTYPE ...population_v6.dtd>`**
      且把属性写成 `<attribute ... value="..."/>` 自闭合形式。MATSim 的
      `PopulationReader` 靠 DOCTYPE 选 delegate ⇒ 从 **line 2, column 1** 就 FATAL：
      `Cannot invoke "...MatsimXmlParser.startTag(...)" because "this.delegate" is null`。
      （SB-A5ind 因此 rc=4，**从未真正跑起来**；SB-A5 的 rc=0 与它无关。）

  (2) **跳步**：v1.0 的需求链是
        先验 OD → **6.2** → **6.2B（空间实现）** → **连通性修复** → **6.3.3A（出发时刻）**
        → **7.4.3 复制到 N_sim**（逐行保留式）。
      v1 只做了 6.2。

  (3) **样本量错配**：SB-A5 对照用的 v1.0 `pop_W01` 是 **236,044** agent
      （= round(1.180222 × 200,000)），v1 的需求只有 **200,000** ⇒ 两臂**样本量不同 = 混杂**，
      即便修好格式也不可比。

★ v2 修正
--------------------------------------------------------------------------------
按 **与原链完全相同的冻结脚本**（仅 monkeypatch「先验 OD 目录 / 输入输出目录」，不复制逻辑、
不改任何脚本）重跑整条链，把先验 OD 从 `reports/od_prior_5c1`（AM 阻抗，含 SpeedBand）
换成 `reports/od_prior_5b`（自由流阻抗，**零 SpeedBand**）。

链（与 v1.0 逐位同源）：
    5B 先验 OD
      → Step 6.2   build_matsim_population.py          → car_prior_od_lambda_0p075.parquet
      → Step 6.2B  build_matsim_population_6_2b.py     → 200,000 native population
      → 连通性修复  prepare_connected_scenario.repair_population（**不跑 main()，不碰冻结报告**）
      → Step 6.3.3A build_departure_profile_6_3_3a.py  → 出发时刻
      → Step 7.4.3  run_demand_scale_7_4_3.build_population → 236,044
    产物 = populations/population_SB-A5ind_lambda_0p075.xml.gz

★ 冻结链复现证据（本轮另立）：对 5C.1 的 6.3.3A 人口做同样的 236,044 复制，
  sha256 与 `matsim_final_7_6h/populations/pop_W01/…` **逐位一致** ⇒ 链理解无误。

★ 门禁（含**真解析门**）
--------------------------------------------------------------------------------
D1..D9 见 CHECKS；末尾用 `matsim_pop_probe.py`（官方 `PopulationReader`）实际解析产物。
⛔ 红线：不改 v1.0 / OD 冻结件 / crosswalk / TrafficFlow / SpeedBand 原始值 / 评价器阈值；
        不写 `reports/matsim_network/connectivity_repair.json`（冻结件）；不产生 v1.1。
"""
from __future__ import annotations
import csv
import json
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(r"D:\Luan\2026-05\2_Singapore")
sys.path.insert(0, str(ROOT / "scripts" / "od"))
sys.path.insert(0, str(ROOT / "scripts" / "matsim"))
sys.path.insert(0, str(ROOT / "scripts" / "experiments"))

import build_matsim_population as B            # Step 6.2
import build_matsim_population_6_2b as B2      # Step 6.2B
import prepare_connected_scenario as C         # 连通性修复
import build_departure_profile_6_3_3a as D     # Step 6.3.3A
import run_demand_scale_7_4_3 as ds            # Step 7.4.3 复制机制

EXP = ROOT / "experiments" / "E-SB-02_night_freeflow"
AUDIT = EXP / "audit"
PRIOR_5B = Path("reports/od_prior_5b")
# 实验专属链目录（⛔ 全部落在 experiment 内，绝不写 reports/ 冻结件）
CHAIN_62 = EXP / "matsim_population_6_2b"
CHAIN_CONN = EXP / "matsim_population_6_2b_connected"
CHAIN_DEP = EXP / "matsim_departure_6_3_3a"
POP_DIR = EXP / "populations"
FINAL_POP = POP_DIR / "population_SB-A5ind_lambda_0p075.xml.gz"

LAM = 0.075
TAG = "0p075"
N_BASE = 200_000
N_SIM = 236_044                     # = round(1.180222 × 200,000)，与 v1.0 pop_W01 同
DUP_SEED = 20260912
V10_CAR_OD = ROOT / "reports/matsim_population/car_prior_od_lambda_0p075.parquet"
V10_POP = ROOT / "matsim_final_7_6h/populations/pop_W01/population_lambda_0p075.xml.gz"
NET_CLEAN = ROOT / "reports/matsim_network/network_cleaned.xml.gz"
TV_EXPECT = 0.0346                  # E-SB-02B 冻结口径

CHECKS: list[dict] = []


def gate(cid, name, ok, detail="", hard=True):
    CHECKS.append({"check": cid, "name": name, "pass": bool(ok), "detail": str(detail)})
    print(f"  [{'PASS' if ok else 'FAIL'}] {cid:<5} {name}" + (f"  ({detail})" if detail else ""), flush=True)
    return bool(ok)


def sha256_content(p: Path) -> str:
    import gzip, hashlib
    h = hashlib.sha256()
    with gzip.open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def count_persons(p: Path) -> int:
    import gzip
    n = 0
    with gzip.open(p, "rt", encoding="utf-8", errors="replace") as f:
        for line in f:
            if "<person " in line and "</person>" not in line:
                n += 1
    return n


def head_lines(p: Path, k=3):
    import gzip
    out = []
    with gzip.open(p, "rt", encoding="utf-8", errors="replace") as f:
        for i, ln in enumerate(f):
            if i >= k:
                break
            out.append(ln.rstrip("\n"))
    return out


def car_od_tv(a: Path, b: Path) -> float:
    def load(p):
        d = pd.read_parquet(p)
        return (d.origin_zone.astype(int).to_numpy(), d.destination_zone.astype(int).to_numpy(),
                d.trips.to_numpy(float))
    oa, da, ta = load(a)
    ob, db, tb = load(b)
    ids = sorted(set(oa) | set(ob) | set(da) | set(db))
    pos = {z: i for i, z in enumerate(ids)}
    n = len(ids)
    A = np.zeros((n, n)); Bm = np.zeros((n, n))
    np.add.at(A, (np.array([pos[x] for x in oa]), np.array([pos[x] for x in da])), ta)
    np.add.at(Bm, (np.array([pos[x] for x in ob]), np.array([pos[x] for x in db])), tb)
    return float(np.abs(A / A.sum() - Bm / Bm.sum()).sum() / 2)


# ------------------------------------------------------------------ phases ----
def phase_62() -> bool:
    print("\n[Phase 1] Step 6.2 —— 先验 OD(5B) → car_prior_od")
    src = ROOT / PRIOR_5B / "prior_od_5b_lambda_0p075.parquet"
    if not gate("D1", "Step5B（零 SpeedBand）先验 OD 存在", src.exists(), f"{PRIOR_5B}/{src.name}"):
        return False

    def locate_prior_5b(root: Path, lam: float):
        t = f"{lam:.3f}".replace(".", "p")
        for n in (f"prior_od_5b_lambda_{t}.parquet", f"prior_od_5b_lambda_{t}.csv"):
            p = root / B.PRIOR_DIR / n
            if p.exists():
                return p
        raise FileNotFoundError(f"5B prior OD not found: {n}")

    B.PRIOR_DIR = PRIOR_5B
    B.OUT = POP_DIR.relative_to(ROOT)
    B.locate_prior = locate_prior_5b
    sys.argv = ["esb02_build_ind_demand", "--project-root", str(ROOT),
                "--lambdas", str(LAM), "--target-agents", str(N_BASE), "--seed", "20260912"]
    rc = B.main()
    parq = POP_DIR / f"car_prior_od_lambda_{TAG}.parquet"
    ok = gate("D2", "Step 6.2 返回 0 且先验 OD parquet 已生成",
              rc in (0, None) and parq.exists(), f"rc={rc} {parq.name}")
    if ok and V10_CAR_OD.exists():
        tv = car_od_tv(V10_CAR_OD, parq)
        gate("D3", "车行 OD 层 TV(5C.1, 5B) == 冻结 0.0346",
             abs(tv - TV_EXPECT) < 5e-4, f"TV={tv:.4f}")
    return ok


def phase_62b() -> bool:
    print("\n[Phase 2] Step 6.2B —— 空间实现（native population, 200,000）")
    B2.OD_DIR = POP_DIR.relative_to(ROOT)
    B2.OUT = CHAIN_62.relative_to(ROOT)
    sys.argv = ["esb02_build_ind_demand", "--project-root", str(ROOT),
                "--lambdas", str(LAM), "--target-agents", str(N_BASE), "--seed", "20260912"]
    B2.main()
    pop = CHAIN_62 / f"population_lambda_{TAG}.xml.gz"
    if not gate("D4", "Step 6.2B 产物存在", pop.exists(), pop.name):
        return False
    n = count_persons(pop)
    hd = head_lines(pop, 3)
    has_doctype = any("<!DOCTYPE population" in x for x in hd)
    gate("D5", "6.2B 人口 persons == 200,000", n == N_BASE, f"persons={n}")
    gate("D6", "6.2B 人口为 MATSim 原生格式（含 DOCTYPE）", has_doctype, hd[1] if len(hd) > 1 else "")
    return True


def phase_repair() -> bool:
    print("\n[Phase 3] 连通性修复（直接调 repair_population，不跑 main()、不写冻结报告）")
    orig_links, orig_nodes = C.read_network(ROOT / "reports/matsim_network/network.xml.gz")
    c_links, c_nodes = C.read_network(NET_CLEAN)
    C.POP_IN = CHAIN_62
    C.POP_OUT = CHAIN_CONN
    stats = C.repair_population(TAG, c_links, c_nodes, orig_links, orig_nodes)
    pop = CHAIN_CONN / f"population_lambda_{TAG}.xml.gz"
    if not gate("D7", "连通性修复产物存在", pop.exists(), pop.name):
        return False
    n = count_persons(pop)
    desc = head_lines(pop, 3)[2] if len(head_lines(pop, 3)) > 2 else ""
    gate("D8", "修复人口 persons == 200,000 且 desc 含 (connectivity-repaired)",
         n == N_BASE and "connectivity-repaired" in desc, f"persons={n}")
    gate("D9", "修复确实发生（affected > 0）",
         stats.get("home_link_repaired", 0) + stats.get("work_link_repaired", 0) > 0,
         f"home={stats.get('home_link_repaired')} work={stats.get('work_link_repaired')}")
    return True


def phase_633a() -> bool:
    print("\n[Phase 4] Step 6.3.3A —— 出发时刻（源 = 实验内修复人口）")
    D.POP_DIR = CHAIN_CONN.relative_to(ROOT)
    D.FALLBACK_POP_DIR = Path("experiments/E-SB-02_night_freeflow/__no_fallback__")
    D.OUT = CHAIN_DEP.relative_to(ROOT)
    sys.argv = ["esb02_build_ind_demand", "--project-root", str(ROOT),
                "--lambdas", str(LAM), "--seed", "20260912"]
    D.main()
    pop = CHAIN_DEP / f"population_lambda_{TAG}.xml.gz"
    if not gate("D10", "6.3.3A 产物存在", pop.exists(), pop.name):
        return False
    n = count_persons(pop)
    gate("D11", "6.3.3A 人口 persons == 200,000", n == N_BASE, f"persons={n}")
    # 出发时刻不再是全体 08:00:00。
    # ★判据修正（v2.1）：6.3.3A 是「均匀秒级抽样」，恰好抽中整点 08:00:00 的是极少数。
    #   冻结的 5C.1 同类产物里同样有 33 个 ⇒ 正确判据是「占比 < 0.1%」，不是「== 0」。
    import gzip
    n8000 = 0
    n_end = 0
    with gzip.open(pop, "rt", encoding="utf-8", errors="replace") as f:
        for ln in f:
            if "end_time=" in ln:
                n_end += 1
                if 'end_time="08:00:00"' in ln:
                    n8000 += 1
    frac = (n8000 / n_end) if n_end else 1.0
    gate("D12", "出发时刻已打散（08:00:00 占比 < 0.1%）", frac < 1e-3,
         f"08:00:00={n8000}/{n_end} ({frac*100:.4f}%)；冻结 5C.1 同类产物=33")
    return True


def phase_dup() -> bool:
    print("\n[Phase 5] Step 7.4.3 —— 复制到 N_sim")
    src = CHAIN_DEP / f"population_lambda_{TAG}.xml.gz"
    rep = ds.build_population(src, FINAL_POP, N_SIM, seed=DUP_SEED, log=lambda *a: None)
    n = rep["persons"]
    gate("D13", f"最终人口 persons == {N_SIM:,}", n == N_SIM, f"persons={n} n_dup={rep['n_dup_written']}")
    return n == N_SIM


# ------------------------------------------------------------------- 真门 -----
def real_parse_gate() -> bool:
    print("\n[Gate] 真解析门：MATSim PopulationReader 实际解析产物")
    r = subprocess.run([sys.executable, str(ROOT / "scripts" / "experiments" / "matsim_pop_probe.py"),
                        str(FINAL_POP)], capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    out = (r.stdout or "") + (r.stderr or "")
    m = re.search(r"PROBE_OK=1\s+persons=(\d+)\s+sumEF=([\d.]+)\s+withEF=(\d+)\s+missingEF=(\d+)", out)
    if m:
        persons, sumef, withef, miss = int(m.group(1)), float(m.group(2)), int(m.group(3)), int(m.group(4))
        gate("D14", f"真解析门通过：persons=={N_SIM:,} 且 attribute 全为正文形式",
             persons == N_SIM and withef == N_SIM and miss == 0,
             f"persons={persons} sumEF={sumef:.1f} withEF={withef} missingEF={miss}")
        return persons == N_SIM and withef == N_SIM and miss == 0
    gate("D14", "真解析门通过", False, out.strip().splitlines()[-1][:160] if out.strip() else "no output")
    return False


def identity_gate() -> bool:
    print("\n[Gate] 产物身份：必须与 v1.0 pop_W01 不同（OD 不同）但同 N")
    if not V10_POP.exists():
        return True
    a = sha256_content(FINAL_POP); b = sha256_content(V10_POP)
    gate("D15", "SB-A5ind 人口内容 ≠ v1.0 pop_W01（5B vs 5C.1，必须不同）",
         a != b, f"sha256={a[:16]} vs {b[:16]}")
    return a != b


def main() -> int:
    AUDIT.mkdir(parents=True, exist_ok=True)
    print("=" * 88)
    print("E-SB-02C v2 | SB-A5ind 独立需求（5B，零 SpeedBand）—— 全链派生")
    print("=" * 88)
    ok = True
    for fn in (phase_62, phase_62b, phase_repair, phase_633a, phase_dup):
        try:
            if not fn():
                ok = False
                break
        except Exception as e:  # noqa: BLE001
            gate(f"X[{fn.__name__}]", "阶段异常", False, f"{type(e).__name__}: {e}")
            ok = False
            break
    if ok:
        ok = real_parse_gate() and identity_gate() and ok
    else:
        gate("D14", "真解析门（未执行：上游失败）", False, "skipped")
        gate("D15", "产物身份（未执行：上游失败）", False, "skipped")

    res = {
        "generated": datetime.now().isoformat(timespec="seconds"),
        "builder": "esb02_build_ind_demand.py v2（全链：6.2 → 6.2B → repair → 6.3.3A → dup）",
        "nature": "DEMAND-SIDE change（仅先验 OD：5C.1→5B）；网络/SCALE/seed/迭代 均不变",
        "prior_dir": str(PRIOR_5B), "lambda": LAM, "n_base": N_BASE, "n_sim": N_SIM,
        "final_population": str(FINAL_POP.relative_to(ROOT)),
        "final_sha256_content": sha256_content(FINAL_POP) if FINAL_POP.exists() else None,
        "checks": CHECKS,
        "verdict": "READY" if all(c["pass"] for c in CHECKS) else "FAILED",
    }
    (AUDIT / "esb02_ind_demand_gates.json").write_text(
        json.dumps(res, ensure_ascii=False, indent=2), encoding="utf-8")
    pd.DataFrame(CHECKS).to_csv(AUDIT / "esb02_ind_demand_gates.csv", index=False, encoding="utf-8-sig")
    print("\n" + "=" * 88)
    print(f"判决：{res['verdict']}（门禁 {sum(c['pass'] for c in CHECKS)}/{len(CHECKS)}）")
    print("=" * 88)
    return 0 if res["verdict"] == "READY" else 1


if __name__ == "__main__":
    raise SystemExit(main())
