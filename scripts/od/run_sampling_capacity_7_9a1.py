#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
run_sampling_capacity_7_9a1.py — Step 7.9A-1 采样一致性容量（sample-consistent capacity）单因子实验

设计（★判据运行前已冻结，见 reports/sampling_capacity_7_9a1/PREREG_7_9A1.md）
--------------------------------------------------------------------------
唯一结构变化（单因子、单点、不扫描）：

    qsim.flowCapacityFactor     1.0 -> 0.434977      # = 1/SCALE = 1/2.29897
    qsim.storageCapacityFactor  1.0 -> 0.434977

+ 输出层 3 项（不改模型）：outputDirectory / runId / writeEventsInterval 0 -> 19

⇒ 与冻结 config 的**全展开参数 diff 必须恰为 5 项**；第 6 项 ⇒ FAIL 中止。

★ 与 7.8-VIZ-RUN 的关键差异
---------------------------
那次是「模型不变、只改输出层」，所以判据是 **BITEXACT 重放**。
本次**模型确实变了**（f_cap），因此**不做重放一致性判定**；改为：

    M1  配置 diff 恰为 5 项白名单（含 <parameterset> 全展开）
    M2  单因子隔离：除这 2 个 qsim 容量参数外，<module name="qsim"> 块内其余参数逐位不变
    M3  hermes.*CapacityFactor 保持 1.0（惰性，不得顺手改）
    M4  实际生效配置 output_config.xml 里 qsim.flowCapacityFactor == 0.434977
    M5  运行完整性：departure == arrival == 236,044（或按 pre-reg 报出差额）
    M6  冻结件只读：14 件冻结输入 + 3 个冻结目录 0 漂移
    M7  ★CAPACITY 语义消解（PREREG §11）：linkstats.CAPACITY 是基础容量还是有效容量

运行
----
    python scripts/od/run_sampling_capacity_7_9a1.py                  # 准备（零仿真）
    python scripts/od/run_sampling_capacity_7_9a1.py --run --heap 24g # 点火（~2 h）
    python scripts/od/run_sampling_capacity_7_9a1.py --verify         # 只复核
"""
from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
import math
import os
import re
import sys
import time
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path

ROOT = Path(r"D:\Luan\2026-05\2_Singapore")
sys.path.insert(0, str(ROOT / "scripts" / "matsim"))

# --------------------------------------------------------------------------
# 路径
# --------------------------------------------------------------------------
SRC_MANIFEST = ROOT / "reports" / "final_model_7_8" / "FINAL_MODEL_MANIFEST.json"
SRC_CONFIG = ROOT / "matsim_final_7_6h" / "configs" / "config_W01_rc_min.xml"
SRC_OUT_DIR = ROOT / "matsim_final_7_6h" / "outputs" / "W01_rc_min"
SRC_LINKSTATS = SRC_OUT_DIR / "ITERS" / "it.19" / "W01_rc_min.19.linkstats.txt.gz"

PREREG = ROOT / "reports" / "sampling_capacity_7_9a1" / "PREREG_7_9A1.md"
PREREG_SHA = ROOT / "reports" / "sampling_capacity_7_9a1" / "a1_prereg_sha.json"

NEW_ROOT = ROOT / "matsim_sampling_capacity_7_9a1"
CONFIG_DIR = NEW_ROOT / "configs"
OUT_ROOT = NEW_ROOT / "outputs"
LOG_DIR = NEW_ROOT / "logs"
AUDIT_DIR = NEW_ROOT / "audit"

RUN_ID = "A1_capf0p435"
OUT_DIR = OUT_ROOT / RUN_ID
NEW_CONFIG = CONFIG_DIR / f"config_{RUN_ID}.xml"
NEW_LINKSTATS = OUT_DIR / "ITERS" / "it.19" / f"{RUN_ID}.19.linkstats.txt.gz"

GUARD_DIRS = [
    ROOT / "matsim_final_7_6h",
    ROOT / "matsim_viz_7_8",
    ROOT / "reports" / "final_model_7_8",
]

# --------------------------------------------------------------------------
# 冻结真值（从 7.8 manifest / 冻结产物读，不手抄）
# --------------------------------------------------------------------------
EXPECT_SRC_CONFIG_SHA16 = "8f44fb349bff9cf1"
EXPECT_POP_SHA16 = "e96ed83ff59c0f5e"
EXPECT_F_WORK = 1.180222
EXPECT_LAMBDA = 0.075
EXPECT_SCALE = 2.29897
EXPECT_ITER = 19
EXPECT_N_SIM = 236_044
EXPECT_SIM_OBS = 0.9993347697

F_CAP_NEW = "0.434977"                      # 1/SCALE 6dp
F_CAP_FLOAT = 0.434977

WHITELIST = {
    "flowCapacityFactor": F_CAP_NEW,
    "storageCapacityFactor": F_CAP_NEW,
    "outputDirectory": str(OUT_DIR),
    "runId": RUN_ID,
    "writeEventsInterval": str(EXPECT_ITER),
}

# linkstats 列索引（154 列，已实测）
C_LINK, C_ORIG, C_FROM, C_TO, C_LEN, C_FS, C_CAP = 0, 1, 2, 3, 4, 5, 6
C_H89, C_TT89 = 32, 107

CHECKS: list[dict] = []


def gate(cid: str, name: str, ok: bool, detail: str = "") -> bool:
    CHECKS.append({"check": cid, "name": name, "pass": bool(ok), "detail": detail})
    print(f"  [{'PASS' if ok else 'FAIL'}] {cid} {name}" + (f"  ({detail})" if detail else ""))
    return bool(ok)


def warn(cid: str, name: str, detail: str) -> None:
    CHECKS.append({"check": cid, "name": name, "pass": "WARN", "detail": detail})
    print(f"  [WARN] {cid} {name}  ({detail})")


def sha_full(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def sha16(p: Path) -> str:
    return sha_full(p)[:16]


def stamp(p: Path) -> str:
    return datetime.fromtimestamp(p.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S")


def dump_json(p: Path, obj) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w", encoding="utf-8") as fh:
        json.dump(obj, fh, ensure_ascii=False, indent=2)


def dir_listing(d: Path) -> dict[str, int]:
    """递归 (相对路径 -> 字节数)。用于冻结目录漂移检测（比全量 sha 便宜）。"""
    out: dict[str, int] = {}
    if not d.exists():
        return out
    for base, _dirs, files in os.walk(d):
        for f in files:
            p = Path(base) / f
            try:
                out[str(p.relative_to(d))] = p.stat().st_size
            except OSError:
                out[str(p.relative_to(d))] = -1
    return out


# --------------------------------------------------------------------------
def frozen_inputs() -> list[dict]:
    return json.loads(SRC_MANIFEST.read_text(encoding="utf-8"))["evidence_manifest"]


def snapshot_inputs() -> list[dict]:
    out = []
    for it in frozen_inputs():
        p = ROOT / it["path"]
        out.append({
            "path": it["path"],
            "exists": p.exists(),
            "bytes": p.stat().st_size if p.exists() else 0,
            "mtime": stamp(p) if p.exists() else "",
            "sha256_16": sha16(p) if p.exists() else "",
            "sha256_16_at_freeze": it["sha256_16"],
            "mtime_at_freeze": it["mtime"],
        })
    return out


def all_params(path: Path) -> dict[str, str]:
    """配置展开为 扁平键 -> 值（含 <parameterset> 子节点）。"""
    r = ET.parse(path).getroot()
    d: dict[str, str] = {}
    for mod in r.findall("module"):
        mn = mod.get("name") or "?"
        for pm in mod.findall("param"):
            d[f"{mn}.{pm.get('name')}"] = pm.get("value") or ""
        for i, ps in enumerate(mod.findall("parameterset")):
            t = ps.get("type") or ps.get("name") or "ps"
            for pm in ps.findall("param"):
                d[f"{mn}[{i}:{t}].{pm.get('name')}"] = pm.get("value") or ""
    return d


def module_block(txt: str, module: str) -> tuple[int, int]:
    m = re.search(r'<module name="%s">.*?</module>' % re.escape(module), txt, re.S)
    if not m:
        raise RuntimeError(f"未找到 module {module}")
    return m.start(), m.end()


def set_param_in_module(txt: str, module: str, name: str, new_value: str) -> tuple[str, int, str]:
    """只在该 module 块内替换 name 的 value。返回 (新文本, 命中数, 旧值)。"""
    s, e = module_block(txt, module)
    block = txt[s:e]
    pat = r'(<param name="%s" value=")([^"]*)(" />)' % re.escape(name)
    hits = re.findall(pat, block)
    if len(hits) != 1:
        return txt, len(hits), ""
    old = hits[0][1]
    block2 = re.sub(pat, lambda m: m.group(1) + new_value + m.group(3), block, count=1)
    return txt[:s] + block2 + txt[e:], 1, old


def set_unique_param(txt: str, name: str, new_value: str) -> tuple[str, int, str]:
    pat = r'(<param name="%s" value=")([^"]*)(" />)' % re.escape(name)
    hits = re.findall(pat, txt)
    if len(hits) != 1:
        return txt, len(hits), ""
    old = hits[0][1]
    return re.sub(pat, lambda m: m.group(1) + new_value + m.group(3), txt, count=1), 1, old


def strategy_weights(path: Path) -> dict[str, str]:
    r = ET.parse(path).getroot()
    out: dict[str, str] = {}
    for mod in r.findall("module"):
        if mod.get("name") != "replanning":
            continue
        for ps in mod.findall("parameterset"):
            nm = val = None
            for pm in ps.findall("param"):
                if pm.get("name") == "strategyName":
                    nm = pm.get("value")
                elif pm.get("name") == "weight":
                    val = pm.get("value")
            if nm:
                out[nm] = val or ""
    return out


# --------------------------------------------------------------------------
def build_config() -> dict:
    print("\n[1] 由冻结 W01 配置派生 A-1 配置（2 项模型 + 3 项输出层 = 5 项）")

    # --- 预注册身份 ---
    if PREREG_SHA.exists():
        pj = json.loads(PREREG_SHA.read_text(encoding="utf-8"))
        cur = sha_full(PREREG)
        gate("A0", "预注册 PREREG_7_9A1.md sha256 与登记值一致（未被事后改写）",
             cur == pj["sha256"], f"{cur[:16]}… vs {pj['sha256_16']}…")
    else:
        gate("A0", "预注册登记文件存在", False, str(PREREG_SHA))

    src_sha = sha16(SRC_CONFIG)
    gate("A1", "源配置 == 7.8 登记的冻结 sha256_16",
         src_sha == EXPECT_SRC_CONFIG_SHA16, f"{src_sha} vs {EXPECT_SRC_CONFIG_SHA16}")

    txt = SRC_CONFIG.read_text(encoding="utf-8")
    orig_param_count = len(re.findall(r"<param\b", txt))
    applied: list[dict] = []

    # --- (1)(2) 模型：只在 qsim 块内改，且必须命中 1 次 ---
    for name in ("flowCapacityFactor", "storageCapacityFactor"):
        txt, n, old = set_param_in_module(txt, "qsim", name, F_CAP_NEW)
        if not gate(f"A2-{name}", f"qsim.{name} 命中唯一（n={n}）且旧值 = 1.0",
                    n == 1 and old in ("1.0", "1.00", "1"), f"old={old!r} n={n}"):
            return {"ok": False}
        applied.append({"module": "qsim", "param": name, "old": old, "new": F_CAP_NEW})

    # --- (3)(4)(5) 输出层：全文件唯一 ---
    for name, val in (("outputDirectory", WHITELIST["outputDirectory"]),
                      ("runId", WHITELIST["runId"]),
                      ("writeEventsInterval", WHITELIST["writeEventsInterval"])):
        txt, n, old = set_unique_param(txt, name, val)
        if not gate(f"A3-{name}", f"controller.{name} 命中唯一（n={n}）", n == 1,
                    f"old={old[:52]!r}"):
            return {"ok": False}
        applied.append({"module": "controller", "param": name, "old": old, "new": val})

    new_param_count = len(re.findall(r"<param\b", txt))
    gate("A4", "param 标签总数不变（无结构性改动）",
         new_param_count == orig_param_count, f"{orig_param_count} -> {new_param_count}")

    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    NEW_CONFIG.write_text(txt, encoding="utf-8")

    # --- 语义级 diff：含 parameterset 全展开 ---
    a, b = all_params(SRC_CONFIG), all_params(NEW_CONFIG)
    diff = [{"key": k, "src": a.get(k), "new": b.get(k)}
            for k in sorted(set(a) | set(b)) if a.get(k) != b.get(k)]
    rows = [{**d, "whitelisted": d["key"].split(".")[-1] in WHITELIST} for d in diff]
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    with open(AUDIT_DIR / "config_diff_whitelist.csv", "w", newline="", encoding="utf-8-sig") as fh:
        w = csv.DictWriter(fh, fieldnames=["key", "src", "new", "whitelisted"])
        w.writeheader()
        w.writerows(rows)

    non_wl = [d for d in rows if not d["whitelisted"]]
    gate("M1", "配置 diff 恰为 5 项白名单（无越界改动）",
         len(diff) == 5 and not non_wl,
         f"全展开参数={len(b)} diff={len(diff)} 非白名单={len(non_wl)}"
         + (f" {[d['key'] for d in non_wl][:4]}" if non_wl else ""))

    # --- M2 单因子隔离：qsim 块内除 2 个容量参数外逐位不变 ---
    qa = {k[len("qsim."):]: v for k, v in a.items() if k.startswith("qsim.")}
    qb = {k[len("qsim."):]: v for k, v in b.items() if k.startswith("qsim.")}
    qdiff = {k: (qa.get(k), qb.get(k)) for k in sorted(set(qa) | set(qb)) if qa.get(k) != qb.get(k)}
    gate("M2", "qsim 块内仅 2 个容量参数变化（其余逐位不变）",
         set(qdiff) == {"flowCapacityFactor", "storageCapacityFactor"},
         f"qsim diff keys = {sorted(qdiff)} (n_qsim_params={len(qb)})")

    # --- M3 hermes 惰性参数保持 1.0 ---
    hf, hs = b.get("hermes.flowCapacityFactor"), b.get("hermes.storageCapacityFactor")
    gate("M3", "hermes.*CapacityFactor 保持 1.0（惰性，未被顺手改）",
         hf in ("1.0", "1.00", "1") and hs in ("1.0", "1.00", "1"), f"flow={hf} storage={hs}")

    # --- 继承断言 ---
    sw = strategy_weights(NEW_CONFIG)
    inher = [
        ("A5", "controller.lastIteration = 19", b.get("controller.lastIteration") == "19", b.get("controller.lastIteration")),
        ("A6", "controller.mobsim = qsim", b.get("controller.mobsim") == "qsim", b.get("controller.mobsim")),
        ("A7", "plans.inputPlansFile == 冻结人口 pop_W01",
         "populations\\pop_W01\\population_lambda_0p075.xml.gz" in (b.get("plans.inputPlansFile") or ""),
         (b.get("plans.inputPlansFile") or "")[-58:]),
        ("A8", "network.inputNetworkFile == 冻结路网 network_cleaned",
         "network_cleaned.xml.gz" in (b.get("network.inputNetworkFile") or ""),
         (b.get("network.inputNetworkFile") or "")[-38:]),
        ("A9", "qsim.trafficDynamics = queue（本步不动）", b.get("qsim.trafficDynamics") == "queue", b.get("qsim.trafficDynamics")),
        ("A10", "qsim.linkDynamics = FIFO", b.get("qsim.linkDynamics") == "FIFO", b.get("qsim.linkDynamics")),
        ("A11", "global.randomSeed = 4711", b.get("global.randomSeed") == "4711", b.get("global.randomSeed")),
        ("A12", "7.6E：ReRoute 0.15 / ChangeExpBeta 0.85",
         sw.get("ReRoute") == "0.15" and sw.get("ChangeExpBeta") == "0.85", str(sw)),
        ("A13", "7.6E：disableInnovation 0.8 / lr 0.5 / randomness 0.0",
         b.get("replanning.fractionOfIterationsToDisableInnovation") == "0.8"
         and b.get("scoring.learningRate") == "0.5"
         and b.get("routing.routingRandomness") == "0.0",
         f"{b.get('replanning.fractionOfIterationsToDisableInnovation')} / "
         f"{b.get('scoring.learningRate')} / {b.get('routing.routingRandomness')}"),
        ("A14", "writeEventsInterval 新值 = 19", b.get("controller.writeEventsInterval") == "19", b.get("controller.writeEventsInterval")),
        ("A15", "outputDirectory 指向新目录（未覆盖冻结产物）",
         (b.get("controller.outputDirectory") or "").startswith(str(NEW_ROOT)),
         b.get("controller.outputDirectory")),
        ("A16", "vspExperimental.writingOutputEvents = true", b.get("vspExperimental.writingOutputEvents") == "true",
         b.get("vspExperimental.writingOutputEvents")),
        ("A17", "controller.dumpDataAtEnd = true", b.get("controller.dumpDataAtEnd") == "true", b.get("controller.dumpDataAtEnd")),
    ]
    for cid, nm, ok, det in inher:
        gate(cid, nm, ok, str(det))

    return {"ok": True, "applied": applied, "diff": rows, "n_params": len(b)}


# --------------------------------------------------------------------------
def parse_linkstats(p: Path) -> dict[str, tuple[float, float]]:
    """LINK -> (HRS8-9avg, CAPACITY)"""
    out: dict[str, tuple[float, float]] = {}
    with gzip.open(p, "rt", encoding="utf-8", errors="replace") as fh:
        rd = csv.reader(fh, delimiter="\t")
        next(rd, None)
        for row in rd:
            if len(row) <= C_TT89:
                continue
            try:
                out[row[C_LINK]] = (float(row[C_H89]), float(row[C_CAP]))
            except (ValueError, IndexError):
                continue
    return out


def count_events(p: Path) -> dict:
    cnt: dict[str, int] = {}
    n = 0
    with gzip.open(p, "rt", encoding="utf-8", errors="replace") as fh:
        for line in fh:
            if "<event " not in line:
                continue
            n += 1
            i = line.find('type="')
            if i < 0:
                continue
            j = line.find('"', i + 6)
            cnt[line[i + 6:j]] = cnt.get(line[i + 6:j], 0) + 1
    return {
        "entered_link": cnt.get("entered link", 0),
        "left_link": cnt.get("left link", 0),
        "departure": cnt.get("departure", 0),
        "arrival": cnt.get("arrival", 0),
        "stuckAndAbort": cnt.get("stuckAndAbort", 0),
        "PersonEntersVehicle": cnt.get("PersonEntersVehicle", 0),
        "vehicle_enters_traffic": cnt.get("vehicle enters traffic", 0),
        "total_event_records": n,
        "all_types": dict(sorted(cnt.items(), key=lambda kv: -kv[1])),
    }


def verify(expect_run: bool = False) -> dict:
    print("\n[verify] 冻结只读 + 运行完整性 + CAPACITY 语义消解")
    res: dict = {}

    # ---- 冻结输入只读 ----
    after = snapshot_inputs()
    with open(AUDIT_DIR / "frozen_inputs_after.csv", "w", newline="", encoding="utf-8-sig") as fh:
        w = csv.DictWriter(fh, fieldnames=list(after[0].keys()))
        w.writeheader()
        w.writerows(after)
    before_f = AUDIT_DIR / "frozen_inputs_before.csv"
    if before_f.exists():
        before = {r["path"]: r for r in csv.DictReader(open(before_f, encoding="utf-8-sig"))}
        changed = [r["path"] for r in after
                   if r["path"] in before
                   and (before[r["path"]]["sha256_16"] != r["sha256_16"]
                        or before[r["path"]]["mtime"] != r["mtime"])]
        gate("M6a", "14 件冻结输入跑前后 sha256 + mtime 逐位未变", not changed,
             f"变化={len(changed)}" + (f" {changed[:3]}" if changed else ""))
    gate("M6b", "14 件冻结输入 sha256 == 7.8 登记值",
         all(r["sha256_16"] == r["sha256_16_at_freeze"] for r in after),
         f"{sum(1 for r in after if r['sha256_16'] != r['sha256_16_at_freeze'])} 处不一致")
    gate("M6c", "冻结 W01 配置未被改写（其 qsim.f_cap 仍 = 1.0）",
         '<module name="qsim">' in SRC_CONFIG.read_text(encoding="utf-8")
         and 'name="flowCapacityFactor" value="1.0"' in SRC_CONFIG.read_text(encoding="utf-8"))
    n_ev_src = len(list(SRC_OUT_DIR.glob("**/*events*")))
    gate("M6d", "冻结 W01 输出目录仍无 events（未被本次运行污染）", n_ev_src == 0, f"{n_ev_src} 个")

    # ---- 冻结目录递归清单漂移 ----
    cur_listing = {str(d.relative_to(ROOT)): dir_listing(d) for d in GUARD_DIRS}
    lp = AUDIT_DIR / "guard_listing.json"
    if lp.exists():
        prev = json.loads(lp.read_text(encoding="utf-8"))
        bad = []
        for g, cur in cur_listing.items():
            pv = prev.get(g, {})
            add = sorted(set(cur) - set(pv))
            rm = sorted(set(pv) - set(cur))
            ch = sorted(k for k in set(cur) & set(pv) if cur[k] != pv[k])
            if add or rm or ch:
                bad.append(f"{g}: +{len(add)} -{len(rm)} ~{len(ch)}")
        gate("M6e", "3 个冻结目录跑前后递归清单 0 漂移", not bad, "; ".join(bad) if bad else "clean")
    res["guard_listing_current"] = {k: len(v) for k, v in cur_listing.items()}

    if not NEW_LINKSTATS.exists():
        if not expect_run:
            res["state"] = "PENDING_RUN"
            print("     （尚未运行：运行完整性核对挂起）")
            return res
        gate("M5", "A-1 it.19 linkstats 存在", False, str(NEW_LINKSTATS))
        return res

    gate("M5a", "A-1 it.19 linkstats 存在", True, f"{NEW_LINKSTATS.stat().st_size/1e6:.1f} MB")

    # ---- M4 实际生效配置 ----
    eff = OUT_DIR / f"{RUN_ID}.output_config.xml"
    if eff.exists():
        eb = all_params(eff)
        gate("M4", "实际生效配置 qsim.flowCapacityFactor == 0.434977",
             eb.get("qsim.flowCapacityFactor") in ("0.434977",),
             f"qsim.f_cap={eb.get('qsim.flowCapacityFactor')} qsim.s_cap={eb.get('qsim.storageCapacityFactor')}")
    else:
        gate("M4", "实际生效配置 output_config.xml 存在", False, str(eff))

    # ---- ★M7 CAPACITY 语义消解（PREREG §11） ----
    B = parse_linkstats(NEW_LINKSTATS)
    A = parse_linkstats(SRC_LINKSTATS)
    common = sorted(set(A) & set(B))
    ident = sum(1 for k in common if A[k][1] == B[k][1])
    ratio_ok = 0
    for k in common:
        c0, c1 = A[k][1], B[k][1]
        if c0 > 0 and abs(c1 / c0 - F_CAP_FLOAT) <= 1e-6:
            ratio_ok += 1
    if ident == len(common) and len(common) == len(A) == len(B):
        semantics = "BASE_CAPACITY"          # => CAPACITY_eff = CAPACITY * f_cap
    elif ratio_ok == len(common) and ident == 0:
        semantics = "EFFECTIVE_CAPACITY"     # => CAPACITY_eff = CAPACITY
    else:
        semantics = "UNRESOLVED"
    gate("M7", "CAPACITY 语义消解成功（PREREG §11）", semantics != "UNRESOLVED",
         f"{semantics}  n={len(common)}  identical={ident}  scaled≈f_cap={ratio_ok}")
    res["capacity_semantics"] = semantics
    res["capacity_semantics_counts"] = {"n_common": len(common), "identical": ident, "scaled_ratio_ok": ratio_ok}

    # 交叉验证：max(HRS8-9avg) 与 CAPACITY_eff 量级
    cap_eff_max = 0.0
    mx_vol = 0.0
    n_over = 0
    for k in common:
        v, c = B[k]
        ce = c * F_CAP_FLOAT if semantics == "BASE_CAPACITY" else c
        if ce > cap_eff_max:
            cap_eff_max = ce
        if v > mx_vol:
            mx_vol = v
        if ce > 0 and v > ce * (1.0 + 1e-9):
            n_over += 1
    if semantics != "UNRESOLVED" and n_over > 100:
        warn("M7-W", "大量 HRS8-9avg > CAPACITY_eff（> 100 条）⇒ 消解规则可能选错",
             f"n_over={n_over}  max_vol={mx_vol:.1f}  max_cap_eff={cap_eff_max:.1f}")
    res["implied_capacity_check"] = {"max_vol": mx_vol, "max_cap_eff": cap_eff_max, "n_over": n_over}
    print(f"     ★ CAPACITY 语义 = {semantics} | max_vol={mx_vol:.1f} max_cap_eff={cap_eff_max:.1f} n_over={n_over}")

    # ---- M5 运行完整性 ----
    ev_iter = OUT_DIR / "ITERS" / f"it.{EXPECT_ITER}" / f"{RUN_ID}.{EXPECT_ITER}.events.xml.gz"
    ev_root = OUT_DIR / f"{RUN_ID}.output_events.xml.gz"
    ev0 = OUT_DIR / "ITERS" / "it.0" / f"{RUN_ID}.0.events.xml.gz"
    for cid, nm, p in [("M5b", f"ITERS/it.{EXPECT_ITER} events 存在", ev_iter),
                       ("M5c", "根目录 output_events 存在", ev_root)]:
        gate(cid, nm, p.exists(), f"{p.name} {p.stat().st_size/1e9:.2f} GB" if p.exists() else "缺失")
    if ev_iter.exists():
        t0 = time.time()
        st = count_events(ev_iter)
        st["count_seconds"] = round(time.time() - t0, 1)
        res["events"] = st
        print("     events 统计（%.1fs）：%s" % (st["count_seconds"],
              json.dumps({k: v for k, v in st.items() if k != "all_types"}, ensure_ascii=False)))
        gate("M5d", f"departure == 冻结 N_sim = {EXPECT_N_SIM:,}",
             st.get("departure", 0) == EXPECT_N_SIM, f"departure={st.get('departure')}")
        # ★滞留是「情形 B（网络崩解）」的**观测结果**，不是基础设施失败 ⇒ 只记录，不作硬门。
        na = st.get("departure", 0) - st.get("arrival", 0)
        res["never_arrived"] = na
        res["stuckAndAbort"] = st.get("stuckAndAbort", 0)
        if na == 0 and st.get("stuckAndAbort", 0) == 0:
            gate("M5e", "arrival == departure（无滞留）", True,
                 f"arrival={st.get('arrival')} departure={st.get('departure')}")
        else:
            warn("M5e", "出现滞留/stuck ⇒ 按 PREREG §7 情形 B 处置（⛔ 不把容量调回）",
                 f"never_arrived={na} stuckAndAbort={st.get('stuckAndAbort', 0)}")
    # 清 it.0 events
    if ev0.exists():
        sz = ev0.stat().st_size
        ev0.unlink()
        gate("M5f", "删除 it.0 events（未收敛路线）", True, f"释放 {sz/1e9:.2f} GB")

    return res


# --------------------------------------------------------------------------
def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--heap", default="24g")
    ap.add_argument("--run", action="store_true", help="点火（1 跑，~2 h；需用户明确指令）")
    ap.add_argument("--verify", action="store_true", help="只复核，不重跑")
    args = ap.parse_args()

    for d in (CONFIG_DIR, OUT_ROOT, LOG_DIR, AUDIT_DIR):
        d.mkdir(parents=True, exist_ok=True)

    print("=" * 88)
    print("Step 7.9A-1 — 采样一致性容量（sample-consistent capacity）· 单因子实验")
    print("=" * 88)
    print("  冻结源配置 : matsim_final_7_6h/configs/config_W01_rc_min.xml")
    print(f"  新配置     : {NEW_CONFIG.relative_to(ROOT)}")
    print(f"  新输出     : {OUT_DIR.relative_to(ROOT)}")
    print(f"  runId      : {RUN_ID}")
    print(f"  N_sim      : {EXPECT_N_SIM:,}   f_work={EXPECT_F_WORK}   λ={EXPECT_LAMBDA}   SCALE={EXPECT_SCALE}")
    print(f"  ★单因子    : qsim.flowCapacityFactor / storageCapacityFactor 1.0 -> {F_CAP_NEW}  (= 1/SCALE)")
    print(f"  events     : writeEventsInterval 0 -> {EXPECT_ITER}（输出层 3 项之一）")
    print(f"  预注册     : {PREREG.relative_to(ROOT)}")
    print("=" * 88)

    if not args.verify:
        snap = snapshot_inputs()
        with open(AUDIT_DIR / "frozen_inputs_before.csv", "w", newline="", encoding="utf-8-sig") as fh:
            w = csv.DictWriter(fh, fieldnames=list(snap[0].keys()))
            w.writeheader()
            w.writerows(snap)
        print("\n[0] 冻结输入快照 14 件 -> audit/frozen_inputs_before.csv")
        gate("A-1", "14 件冻结输入均存在且 sha256 == 7.8 登记值",
             all(r["exists"] and r["sha256_16"] == r["sha256_16_at_freeze"] for r in snap),
             f"{sum(1 for r in snap if r['sha256_16'] != r['sha256_16_at_freeze'])} 处不一致")

        dump_json(AUDIT_DIR / "guard_listing.json",
                  {str(d.relative_to(ROOT)): dir_listing(d) for d in GUARD_DIRS})
        print("[0] 冻结目录递归清单 -> audit/guard_listing.json")

        r = build_config()
        if not r.get("ok"):
            print("\n!! 配置派生失败，中止")
            dump_json(AUDIT_DIR / "a1_run_integrity.json", {"checks": CHECKS})
            return 2

    if args.run:
        pre = snapshot_inputs()
        if not all(x["sha256_16"] == x["sha256_16_at_freeze"] for x in pre):
            gate("A18", "点火前冻结输入未漂移", False)
            print("\n!! 冻结输入已漂移，拒绝点火")
            return 2
        gate("A18", "点火前冻结输入未漂移", True)

        print(f"\n[RUN] 点火 {NEW_CONFIG.name}（heap {args.heap}）…")
        t0 = time.time()
        import matsim_env  # noqa: E402
        rc = matsim_env.run_java_streaming(["org.matsim.run.RunMatsim", str(NEW_CONFIG)],
                                           log_path=LOG_DIR / f"{RUN_ID}_run.log", heap=args.heap)
        el = (time.time() - t0) / 60
        print(f"--- exit={rc}  耗时 {el:.2f} min ---")
        gate("A19", "RunMatsim 退出码 = 0", rc == 0, f"exit={rc}")
        gate("A20", "运行耗时在预期量级（> 30 min）", el > 30, f"{el:.2f} min")

    res = verify(expect_run=args.run)

    hard = [c for c in CHECKS if c["pass"] is False]
    if hard:
        verdict = "FAILED"
    elif res.get("state") == "PENDING_RUN":
        verdict = "PREPARED_AWAITING_RUN"
    else:
        verdict = "A1_RUN_COMPLETE"

    summary = {
        "step": "7.9A-1",
        "title": "采样一致性容量（sample-consistent capacity）单因子实验",
        "verdict": verdict,
        "n_checks": len(CHECKS),
        "n_pass": sum(1 for c in CHECKS if c["pass"] is True),
        "n_warn": sum(1 for c in CHECKS if c["pass"] == "WARN"),
        "failed": [c["check"] for c in hard],
        "run_id": RUN_ID,
        "new_config": str(NEW_CONFIG.relative_to(ROOT)),
        "new_out_dir": str(OUT_DIR.relative_to(ROOT)),
        "prereg": str(PREREG.relative_to(ROOT)),
        "prereg_sha256": sha_full(PREREG) if PREREG.exists() else None,
        "single_factor": {"qsim.flowCapacityFactor": F_CAP_NEW, "qsim.storageCapacityFactor": F_CAP_NEW},
        "whitelist": WHITELIST,
        "frozen_sim_obs_reference": EXPECT_SIM_OBS,
        "verify": res,
        "checks": CHECKS,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
    dump_json(AUDIT_DIR / "a1_run_integrity.json", summary)
    with open(AUDIT_DIR / "a1_checks.csv", "w", newline="", encoding="utf-8-sig") as fh:
        w = csv.DictWriter(fh, fieldnames=["check", "name", "pass", "detail"])
        w.writeheader()
        w.writerows(CHECKS)

    print("\n" + "=" * 88)
    print(f"  verdict : {verdict}")
    print(f"  checks  : {summary['n_pass']}/{len(CHECKS)} PASS"
          + (f"  WARN {summary['n_warn']}" if summary["n_warn"] else "")
          + (f"  失败 {[c['check'] for c in hard]}" if hard else ""))
    print("=" * 88)
    return 0 if not hard else 1


if __name__ == "__main__":
    sys.exit(main())
