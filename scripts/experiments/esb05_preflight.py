#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""
esb05_preflight.py — E-SB-05 运行前硬门（只读，不点火）
=====================================================
对应任务书 §1「启动前必须验证三件事」：
  ① 完整配置差异严格符合白名单（3 项）
  ② 网络与人口的内容哈希与原 SB-A5 完全一致
  ③ 磁盘空间足以容纳事件文件与运行日志

另附项目纪律要求的 **负例门禁**（证明门禁非恒真）。

产物：
  experiments/E-SB-05_exec_level_events/audit/esb05_preflight.csv
  experiments/E-SB-05_exec_level_events/audit/run_config_manifest.json
  experiments/E-SB-05_exec_level_events/audit/input_manifest.json

用法：
    python scripts/experiments/esb05_preflight.py
"""
from __future__ import annotations

import csv
import gzip
import hashlib
import json
import os
import re
import shutil
import sys
import time
from pathlib import Path
import xml.etree.ElementTree as ET

ROOT = Path(r"D:\Luan\2026-05\2_Singapore")
EXP = ROOT / "experiments" / "E-SB-05_exec_level_events"
AUDIT = EXP / "audit"

SRC_ARM = "SB-A5"
SRC_CFG = ROOT / "experiments" / "E-SB-02_night_freeflow" / "configs" / f"config_{SRC_ARM}.xml"
SRC_OUT = ROOT / "experiments" / "E-SB-02_night_freeflow" / "outputs" / SRC_ARM

NEW_RUNID = "SB-A5_EVT19_CHECK"
NEW_CFG = EXP / "configs" / f"config_{NEW_RUNID}.xml"
NEW_OUT = EXP / "outputs" / NEW_RUNID

V10_OUT = ROOT / "matsim_viz_7_8" / "outputs" / "W01_events"   # v1.0 + events 的历史参照

# ★冻结期望值（来源：esb02_build_gates.json / 上次实测）
EXP_SRC_CFG_SHA256 = "d560bd89c27068c12b5ebbe82255f3e90a99c1b9a314a5f9861f5885e2a2c088"
EXP_NET_SHA256 = "7978681b2a4ab54d1c14890943bf37012d51a003dd14c10dcfd447776eca6dab"
EXP_POP_SHA256 = "e96ed83ff59c0f5ecb50c9d9ff2d42a4b4bdbebf2bbfe81a1e0604fb94921fbd"
EXP_NET_SHA16 = "7a2a81f925c5c560"
EXP_SBA5_LINKSTATS_SHA256 = "ddc879a07dfedb429367e90b8f880afc6ee630886d1d0bfc1129297bd43f9d3e"

WHITELIST = {"controller.outputDirectory", "controller.runId", "controller.writeEventsInterval"}

# ★原 SB-A5 的核心模型指纹：这些参数必须逐项相同
CORE_FINGERPRINT = [
    "controller.lastIteration",
    "controller.firstIteration",
    "controller.mobsim",
    "controller.writeLinkStatsInterval",   # 占位，真名在 linkStats 模块，见下
    "linkStats.writeLinkStatsInterval",
    "linkStats.averageLinkStatsOverIterations",
    "global.randomSeed",
    "global.numberOfThreads",
    "qsim.numberOfThreads",
    "qsim.flowCapacityFactor",
    "qsim.storageCapacityFactor",
    "qsim.trafficDynamics",
    "qsim.linkDynamics",
    "qsim.stuckTime",
    "hermes.flowCapacityFactor",
    "hermes.storageCapacityFactor",
    "replanning.fractionOfIterationsToDisableInnovation",
    "replanning.maxAgentPlanMemorySize",
    "replanning.planSelectorForRemoval",
    "scoring.learningRate",
    "scoring.brainExpBeta",
    "scoring.pathSizeLogitBeta",
    "routing.routingRandomness",
    "routing.networkRouteConsistencyCheck",
    "plans.networkRouteType",
    "network.timeVariantNetwork",
    "controller.routingAlgorithmType",
    "controller.eventsFileFormat",
    "controller.compressionType",
    "controller.cleanItersAtEnd",
    "controller.dumpDataAtEnd",
    "vspExperimental.writingOutputEvents",
]

# 事件文件体积预估（实测参照）
REF_EVENTS_BYTES = {
    "v1.0_W01_events.output_events.xml.gz": 1694011331,
    "SB-A1.19.events.xml.gz": 1781073359,
    "E-CAP-01.output_events.xml.gz": 1925806193,
}

# 预计写出 3 份 events（it.0 / it.19 / output_events 副本）+ 其它产物
EST_EVENTS_BYTES = 3 * 1950000000          # ~5.85 GB
EST_OTHER_BYTES = 800_000_000              # ~0.8 GB (plans/links/network/linkstats…)
SAFETY_FACTOR = 2.0
NEED_BYTES = int((EST_EVENTS_BYTES + EST_OTHER_BYTES) * SAFETY_FACTOR)

GATES: list[dict] = []


def gate(cid, name, ok, detail=""):
    GATES.append({"id": cid, "gate": name, "pass": bool(ok), "detail": str(detail)})
    print(f"  [{'PASS' if ok else 'FAIL'}] {cid:<6} {name}" + (f"  | {detail}" if detail else ""), flush=True)
    return bool(ok)


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


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 22), b""):
            h.update(b)
    return h.hexdigest()


def sha16_content(p: Path) -> str:
    """确定性内容哈希（gz 先解压），与 esb02_build_arms.sha16 同口径。"""
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


def file_rec(p: Path) -> dict:
    rec = {"path": str(p), "exists": p.exists()}
    if p.exists():
        st = p.stat()
        rec.update({"size_bytes": st.st_size, "mtime": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(st.st_mtime))})
        rec["sha256"] = sha256_file(p)
    return rec


def dir_size(p: Path) -> int:
    tot = 0
    for r, _, fs in os.walk(p):
        for f in fs:
            try:
                tot += os.path.getsize(Path(r) / f)
            except OSError:
                pass
    return tot


def main() -> int:
    AUDIT.mkdir(parents=True, exist_ok=True)
    print("=" * 88)
    print("E-SB-05 运行前硬门（SB-A5 执行级 events 验证 / EXPERIMENT ONLY / NOT v1.1）")
    print("=" * 88)

    # ---------- G00 输入存在性 ----------
    gate("G00", "源配置 / 派生配置 / 源输出目录均存在",
         SRC_CFG.exists() and NEW_CFG.exists() and SRC_OUT.exists(),
         f"src_cfg={SRC_CFG.exists()} new_cfg={NEW_CFG.exists()} src_out={SRC_OUT.exists()}")
    if not (SRC_CFG.exists() and NEW_CFG.exists()):
        _flush(); return 3

    # ---------- G01 源配置未被改动 ----------
    src_cfg_sha = sha256_file(SRC_CFG)
    gate("G01", "原 SB-A5 配置 sha256 == 冻结值（未被改动）",
         src_cfg_sha == EXP_SRC_CFG_SHA256, src_cfg_sha[:32] + "…")

    # ---------- G02 参数 diff 白名单 ----------
    a = all_params(SRC_CFG)
    b = all_params(NEW_CFG)
    diff = {k for k in set(a) | set(b) if a.get(k) != b.get(k)}
    gate("G02", "派生配置参数 diff == 白名单 3 项", diff == WHITELIST, f"diff={sorted(diff)}")

    # ---------- G02b 负例门禁：故意少改一项必须被判 FAIL ----------
    b_bad = dict(b)
    b_bad["controller.writeEventsInterval"] = a["controller.writeEventsInterval"]
    diff_bad = {k for k in set(a) | set(b_bad) if a.get(k) != b_bad.get(k)}
    gate("G02b", "负例：writeEventsInterval 未改时该门禁必须 FAIL（非恒真）",
         diff_bad != WHITELIST, f"diff_bad={sorted(diff_bad)}")

    # ---------- G03 writeEventsInterval ----------
    wve = b.get("controller.writeEventsInterval")
    gate("G03", "controller.writeEventsInterval == 19（仅第 19 迭代及第 0 迭代写事件）",
         wve == "19", f"value={wve}")

    # ---------- G04/G05 runId 与输出目录 ----------
    rid = b.get("controller.runId")
    odir = b.get("controller.outputDirectory", "")
    gate("G04", "controller.runId == SB-A5_EVT19_CHECK 且 != 原 SB-A5",
         rid == NEW_RUNID and rid != SRC_ARM, f"runId={rid}")
    od_norm = odir.replace("/", "\\").lower()
    gate("G05", "outputDirectory 位于 E-SB-05 目录内且不与原 SB-A5 / v1.0 输出重叠",
         str(EXP).lower() in od_norm
         and str(SRC_OUT).lower() not in od_norm
         and str(V10_OUT).lower() not in od_norm
         and od_norm.endswith(NEW_RUNID.lower()),
         odir)

    # ---------- G06 输出目录不得已存在（防覆盖） ----------
    gate("G06", "输出目录尚不存在或为空（绝不覆盖原 SB-A5 输出）",
         (not NEW_OUT.exists()) or (NEW_OUT.is_dir() and not any(NEW_OUT.iterdir())),
         f"exists={NEW_OUT.exists()} n_items={len(list(NEW_OUT.iterdir())) if NEW_OUT.exists() else 0}")

    # ---------- G07 网络内容哈希 ----------
    net = Path(b.get("network.inputNetworkFile", ""))
    net_ok = net.exists() and sha256_file(net) == EXP_NET_SHA256
    gate("G07", "网络文件 sha256 == 原 SB-A5 所用（内容逐位一致）",
         net_ok, f"{net.name} sha256={sha256_file(net)[:32] + '…' if net.exists() else 'NA'}")
    net16 = sha16_content(net) if net.exists() else "NA"
    gate("G07b", "网络内容 sha16 == 派生门禁记录 7a2a81f925c5c560",
         net16 == EXP_NET_SHA16, f"sha16={net16}")

    # ---------- G08 人口内容哈希 ----------
    pop = Path(b.get("plans.inputPlansFile", ""))
    pop_sha = sha256_file(pop) if pop.exists() else "NA"
    gate("G08", "人口文件 sha256 == 原 SB-A5 所用（需求 236,044 未改）",
         pop.exists() and pop_sha == EXP_POP_SHA256, f"{pop.name} sha256={str(pop_sha)[:32]}…")

    # ---------- G09 核心模型指纹逐项相同 ----------
    miss, bad = [], []
    for k in CORE_FINGERPRINT:
        if k not in a or k not in b:
            if k == "controller.writeLinkStatsInterval":   # 占位项，跳过
                continue
            miss.append(k)
            continue
        if a[k] != b[k]:
            bad.append(f"{k}:{a[k]}->{b[k]}")
    gate("G09", "核心模型指纹逐项相同（seed/线程/容量因子/评课/routing/qsim…）",
         not miss and not bad, f"missing={miss} changed={bad}")

    # ---------- G10 磁盘 ----------
    du = shutil.disk_usage(str(EXP))
    gate("G10", f"磁盘余量 ≥ {NEED_BYTES/2**30:.1f} GiB（预估 events {EST_EVENTS_BYTES/2**30:.1f} GiB ×{SAFETY_FACTOR} 安全系数）",
         du.free >= NEED_BYTES, f"free={du.free/2**30:.1f} GiB need={NEED_BYTES/2**30:.1f} GiB")

    # ---------- G11 事件格式/压缩 ----------
    gate("G11", "eventsFileFormat==xml 且 compressionType==gzip（决定体积与解析方式）",
         b.get("controller.eventsFileFormat") == "xml" and b.get("controller.compressionType") == "gzip",
         f"fmt={b.get('controller.eventsFileFormat')} comp={b.get('controller.compressionType')}")

    # ---------- G12 运行时 ----------
    try:
        sys.path.insert(0, str(ROOT / "scripts" / "matsim"))
        import matsim_env  # noqa: E402
        d = matsim_env.describe()
        rt_ok = Path(d["java"]).exists() and Path(d["matsim_jar"]).exists()
        rt_detail = f"java={Path(d['java']).name} jar={Path(d['matsim_jar']).name} libs={d['libs_count']}"
    except Exception as e:  # noqa: BLE001
        rt_ok, rt_detail = False, f"{type(e).__name__}: {e}"
    gate("G12", "MATSim 运行时（本地 JDK25 + matsim-2026.0.jar + libs）可用", rt_ok, rt_detail)

    # ---------- G13 参照校验：原 SB-A5 it.19 linkstats 哈希在册 ----------
    ref_ls = SRC_OUT / "ITERS" / "it.19" / f"{SRC_ARM}.19.linkstats.txt.gz"
    ref_sha = sha256_file(ref_ls) if ref_ls.exists() else "NA"
    gate("G13", "原 SB-A5 it.19 linkstats.gz sha256 == 冻结参照（一致性检查基准在册）",
         ref_sha == EXP_SBA5_LINKSTATS_SHA256, str(ref_sha)[:32] + "…")

    # ---------- 留痕 ----------
    man = {
        "built": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "experiment": "E-SB-05_exec_level_events",
        "purpose": "SB-A5 执行级 events 验证（writeEventsInterval=19），补 E-SB-04/04B 的执行级证据",
        "not_v1_1": True,
        "src_arm": SRC_ARM,
        "new_runid": NEW_RUNID,
        "config": file_rec(NEW_CFG),
        "src_config": file_rec(SRC_CFG),
        "network": file_rec(net),
        "population": file_rec(pop),
        "output_dir": str(NEW_OUT),
        "writeEventsInterval": wve,
        "param_diff": sorted(diff),
        "core_fingerprint": {k: b.get(k) for k in CORE_FINGERPRINT if k in b},
        "disk_free_bytes": du.free,
        "disk_total_bytes": du.total,
        "est_events_bytes": EST_EVENTS_BYTES,
        "est_other_bytes": EST_OTHER_BYTES,
        "need_bytes": NEED_BYTES,
        "ref_events_sizes": REF_EVENTS_BYTES,
        "ref_sba5_linkstats_sha256": ref_sha,
        "gates": GATES,
        "verdict": "READY" if all(g["pass"] for g in GATES) else "NOT_READY",
    }
    (AUDIT / "run_config_manifest.json").write_text(json.dumps(man, ensure_ascii=False, indent=2), encoding="utf-8")
    (AUDIT / "input_manifest.json").write_text(json.dumps({
        "built": man["built"],
        "network": man["network"],
        "population": man["population"],
        "src_config": man["src_config"],
        "new_config": man["config"],
        "src_sba5_it19_linkstats": file_rec(ref_ls),
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    _flush()

    ok = all(g["pass"] for g in GATES)
    n_pass = sum(1 for g in GATES if g["pass"])
    print("-" * 88)
    print(f"{'[OK]' if ok else '[ABORT]'} 运行前硬门 {n_pass}/{len(GATES)} PASS"
          + ("" if ok else " ⇒ 不点火。"))
    print(f"产物：{AUDIT / 'run_config_manifest.json'}")
    return 0 if ok else 4


def _flush():
    AUDIT.mkdir(parents=True, exist_ok=True)
    with open(AUDIT / "esb05_preflight.csv", "w", newline="", encoding="utf-8-sig") as fh:
        w = csv.DictWriter(fh, fieldnames=["id", "gate", "pass", "detail"])
        w.writeheader()
        w.writerows(GATES)


if __name__ == "__main__":
    sys.exit(main())
