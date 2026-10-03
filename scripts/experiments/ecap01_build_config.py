#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ecap01_build_config.py — E-CAP-01 抽样需求—道路供给尺度统一试验：配置派生 + 硬门

定位（★非 v1.1、非基线、非校准结论；仅作演示/旁路试验）
--------------------------------------------------------
    EXPERIMENT ONLY / NOT v1.1 / NOT FORMAL BASELINE / NOT CALIBRATED MODEL

唯一模型改动（单因子、单点、不扫描）：

    qsim.flowCapacityFactor     1.0 -> 0.434977      # = 1/SCALE = 1/2.29897
    qsim.storageCapacityFactor  1.0 -> 0.434977

+ 输出层 3 项（不改模型）：outputDirectory / runId / writeEventsInterval 0 -> 19
⇒ 与冻结 config 的 **全展开参数 diff 必须恰为 5 项**；出现第 6 项 ⇒ FAIL 并中止。

⛔ 不动：network / plans(OD) / routing / scoring / trafficDynamics / signals /
        speedFactor / replanning / lastIteration / randomSeed / numberOfThreads
⛔ 不动 hermes.*CapacityFactor（惰性：mobsim=qsim，hermes 不生效）

运行
----
    python scripts/experiments/ecap01_build_config.py              # 派生 + 硬门（零仿真）
    python scripts/experiments/ecap01_build_config.py --verify     # 只复核既有配置
    python scripts/experiments/ecap01_build_config.py --run --heap 24g   # 点火
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path
import xml.etree.ElementTree as ET

ROOT = Path(r"D:\Luan\2026-05\2_Singapore")
sys.path.insert(0, str(ROOT / "scripts" / "matsim"))

# --------------------------------------------------------------------------
# 冻结源（只读）
# --------------------------------------------------------------------------
SRC_CONFIG = ROOT / "matsim_final_7_6h" / "configs" / "config_W01_rc_min.xml"
SRC_NETWORK = ROOT / "reports" / "matsim_network" / "network_cleaned.xml.gz"
SRC_PLANS = (ROOT / "matsim_final_7_6h" / "populations" / "pop_W01"
             / "population_lambda_0p075.xml.gz")
V10_OUT_DIR = ROOT / "matsim_final_7_6h" / "outputs" / "W01_rc_min"

# --------------------------------------------------------------------------
# 独立试验根（★旁路：绝不写 v1.0）
# --------------------------------------------------------------------------
EXP_ROOT = ROOT / "experiments" / "E-CAP-01_scale_capacity"
CONFIG_DIR = EXP_ROOT / "configs"
OUT_ROOT = EXP_ROOT / "outputs"
LOG_DIR = EXP_ROOT / "logs"
AUDIT_DIR = EXP_ROOT / "audit"

RUN_ID = "E-CAP-01"
OUT_DIR = OUT_ROOT / RUN_ID
NEW_CONFIG = CONFIG_DIR / f"config_{RUN_ID}.xml"

# --------------------------------------------------------------------------
# 冻结真值（实测登记，不手抄臆造）
# --------------------------------------------------------------------------
EXPECT_SRC_CONFIG_SHA16 = "8f44fb349bff9cf1"
EXPECT_NETWORK_SHA16 = "f55795995b87d330"
EXPECT_PLANS_SHA16 = "e96ed83ff59c0f5e"
EXPECT_SEED = "4711"
EXPECT_THREADS = "8"
EXPECT_ITER = 19
EXPECT_N_SIM = 236_044
EXPECT_SCALE = 2.29897
EXPECT_SIM_OBS = 0.9993347697

F_CAP = "0.434977"                     # 1/SCALE，写 6 位小数
F_CAP_EXACT = 1.0 / EXPECT_SCALE       # 0.43497740292391806…

WHITELIST = {
    "flowCapacityFactor": F_CAP,
    "storageCapacityFactor": F_CAP,
    "outputDirectory": str(OUT_DIR),
    "runId": RUN_ID,
    "writeEventsInterval": str(EXPECT_ITER),
}

CHECKS: list[dict] = []


# --------------------------------------------------------------------------
# 工具
# --------------------------------------------------------------------------
def sha_hex(p: Path, full: bool = False) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    d = h.hexdigest()
    return d if full else d[:16]


def rd(p: Path) -> str:
    """保留行尾（newline=''）读取。"""
    return io.open(p, encoding="utf-8", newline="").read()


def wr(p: Path, s: str) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    with io.open(p, "w", encoding="utf-8", newline="") as f:
        f.write(s)


def gate(cid: str, name: str, ok: bool, detail: str = "") -> bool:
    CHECKS.append({"check": cid, "name": name, "pass": bool(ok), "detail": detail})
    print("  [%s] %-4s %s%s" % ("PASS" if ok else "FAIL", cid, name,
                               ("  (%s)" % detail) if detail else ""))
    return bool(ok)


def all_params(path: Path) -> dict:
    """把 config 展开成 module[.parameterset…].param -> value。"""
    root = ET.parse(str(path)).getroot()
    out: dict[str, str] = {}

    def walk_ps(ps, prefix):
        for p in ps.findall("param"):
            out["%s.%s" % (prefix, p.get("name"))] = p.get("value")
        for sub in ps.findall("parameterset"):
            walk_ps(sub, "%s.%s" % (prefix, sub.get("name")))

    for mod in root.findall("module"):
        mn = mod.get("name")
        for p in mod.findall("param"):
            out["%s.%s" % (mn, p.get("name"))] = p.get("value")
        for ps in mod.findall("parameterset"):
            walk_ps(ps, "%s.%s" % (mn, ps.get("name")))
    return out


def _module_span(txt: str, module: str):
    m = re.search(r'<module\s+name="%s"\s*>' % re.escape(module), txt)
    if not m:
        return None
    s = m.end()
    e = txt.find("</module>", s)
    if e < 0:
        return None
    return s, e


def set_param_in_module(txt: str, module: str, name: str, value: str):
    """只在指定 module 块内替换；必须命中唯一 1 次。"""
    span = _module_span(txt, module)
    if span is None:
        return txt, 0, None
    s, e = span
    body = txt[s:e]
    pat = re.compile(r'(<param\s+name="%s"\s+value=")([^"]*)(")' % re.escape(name))
    hits = pat.findall(body)
    n = len(hits)
    if n != 1:
        return txt, n, (hits[0][1] if hits else None)
    old = hits[0][1]
    new_body = pat.sub(lambda m: m.group(1) + value + m.group(3), body, count=1)
    return txt[:s] + new_body + txt[e:], 1, old


def set_unique_param(txt: str, name: str, value: str):
    """全文件替换；必须命中唯一 1 次。"""
    pat = re.compile(r'(<param\s+name="%s"\s+value=")([^"]*)(")' % re.escape(name))
    hits = pat.findall(txt)
    n = len(hits)
    if n != 1:
        return txt, n, (hits[0][1] if hits else None)
    return pat.sub(lambda m: m.group(1) + value + m.group(3), txt, count=1), 1, hits[0][1]


def mtime_snapshot() -> dict:
    out = {}
    for p in (ROOT / "matsim_final_7_6h",
              ROOT / "matsim_final_7_6h" / "configs",
              V10_OUT_DIR):
        out[str(p.relative_to(ROOT))] = os.path.getmtime(p) if p.exists() else None
    return out


# --------------------------------------------------------------------------
# 1) 派生配置
# --------------------------------------------------------------------------
def build_config() -> bool:
    print("\n[1] 由冻结 W01 配置派生 E-CAP-01（2 项模型 + 3 项输出层 = 5 项）")

    src_sha = sha_hex(SRC_CONFIG)
    if not gate("A1", "源配置 == 7.8 登记的冻结 sha256_16",
                src_sha == EXPECT_SRC_CONFIG_SHA16, "%s vs %s" % (src_sha, EXPECT_SRC_CONFIG_SHA16)):
        return False

    txt = rd(SRC_CONFIG)
    orig_param_count = len(re.findall(r"<param\b", txt))
    applied: list[dict] = []

    # (1)(2) 模型：只在 qsim 块内改，各命中唯一 1 次
    for name in ("flowCapacityFactor", "storageCapacityFactor"):
        txt, n, old = set_param_in_module(txt, "qsim", name, F_CAP)
        if not gate("A2-%s" % name, "qsim.%s 命中唯一（n=%d）且旧值 1.0" % (name, n),
                    n == 1 and old in ("1.0", "1.00", "1"), "old=%r n=%d" % (old, n)):
            return False
        applied.append({"module": "qsim", "param": name, "old": old, "new": F_CAP})

    # (3)(4)(5) 输出层：全文件唯一
    for name, val in (("outputDirectory", WHITELIST["outputDirectory"]),
                      ("runId", WHITELIST["runId"]),
                      ("writeEventsInterval", WHITELIST["writeEventsInterval"])):
        txt, n, old = set_unique_param(txt, name, val)
        if not gate("A3-%s" % name, "controller.%s 命中唯一（n=%d）" % (name, n), n == 1,
                    "old=%r" % (old[:60] if old else old,)):
            return False
        applied.append({"module": "controller", "param": name, "old": old, "new": val})

    new_param_count = len(re.findall(r"<param\b", txt))
    gate("A4", "param 标签总数不变（无结构性改动）",
         new_param_count == orig_param_count, "%d -> %d" % (orig_param_count, new_param_count))

    wr(NEW_CONFIG, txt)

    # ---- 语义级全展开 diff ----
    a, b = all_params(SRC_CONFIG), all_params(NEW_CONFIG)
    diff = [{"key": k, "src": a.get(k), "new": b.get(k)}
            for k in sorted(set(a) | set(b)) if a.get(k) != b.get(k)]
    rows = [{**d, "whitelisted": d["key"].split(".")[-1] in WHITELIST} for d in diff]
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    with io.open(AUDIT_DIR / "ecap01_config_diff_whitelist.csv", "w",
                 newline="", encoding="utf-8-sig") as fh:
        w = csv.DictWriter(fh, fieldnames=["key", "src", "new", "whitelisted"])
        w.writeheader()
        w.writerows(rows)

    non_wl = [d for d in rows if not d["whitelisted"]]
    gate("M1", "配置 diff 恰为 5 项白名单（无越界改动）",
         len(diff) == 5 and not non_wl,
         "全展开参数=%d diff=%d 非白名单=%d %s"
         % (len(b), len(diff), len(non_wl), [d["key"] for d in non_wl][:4] if non_wl else ""))

    # ---- M2 单因子隔离 ----
    qa = {k[5:]: v for k, v in a.items() if k.startswith("qsim.")}
    qb = {k[5:]: v for k, v in b.items() if k.startswith("qsim.")}
    qdiff = {k: (qa.get(k), qb.get(k)) for k in sorted(set(qa) | set(qb)) if qa.get(k) != qb.get(k)}
    gate("M2", "qsim 块内仅 2 个容量参数变化（其余逐位不变）",
         set(qdiff) == {"flowCapacityFactor", "storageCapacityFactor"},
         "qsim diff = %s (n_qsim=%d)" % (sorted(qdiff), len(qb)))

    # ---- M3 hermes 惰性参数保持 1.0 ----
    hf, hs = b.get("hermes.flowCapacityFactor"), b.get("hermes.storageCapacityFactor")
    gate("M3", "hermes.*CapacityFactor 保持 1.0（惰性，未被顺手改）",
         hf in ("1.0", "1.00", "1") and hs in ("1.0", "1.00", "1"),
         "flow=%s storage=%s" % (hf, hs))

    # ---- M4 继承断言（不得漂移的关键项） ----
    inherit = {
        "global.randomSeed": EXPECT_SEED,
        "global.numberOfThreads": EXPECT_THREADS,
        "controller.lastIteration": str(EXPECT_ITER),
        "network.inputNetworkFile": str(SRC_NETWORK),
        "plans.inputPlansFile": str(SRC_PLANS),
        "qsim.trafficDynamics": a.get("qsim.trafficDynamics"),
        "qsim.timeStepSize": a.get("qsim.timeStepSize"),
        "qsim.stuckTime": a.get("qsim.stuckTime"),
        "qsim.linkDynamics": a.get("qsim.linkDynamics"),
        "qsim.removeStuckVehicles": a.get("qsim.removeStuckVehicles"),
        "qsim.isSeepModeStorageFree": a.get("qsim.isSeepModeStorageFree"),
        "replanning.strategy": a.get("replanning.strategy"),
        "routing.networkModes": a.get("routing.networkModes"),
        "scoring.modeParams.0.utilityOfLineSwitch": a.get("scoring.modeParams.0.utilityOfLineSwitch"),
        "travelTimeCalculator.travelTimeCalculatorType": a.get("travelTimeCalculator.travelTimeCalculatorType"),
    }
    bad = {k: (v, b.get(k)) for k, v in inherit.items() if b.get(k) != v}
    gate("M5", "继承断言：seed/线程/迭代/network/plans/动力学/路由/评分逐位不变",
         not bad, "drift=%s" % (bad if bad else "NONE"))

    # ---- M6 linkStats 必须仍为 1（评价口径依赖） ----
    gate("M6", "linkStats.writeLinkStatsInterval == 1（评价口径依赖）",
         b.get("linkStats.writeLinkStatsInterval") == "1",
         "=%s" % b.get("linkStats.writeLinkStatsInterval"))

    json.dump({"applied": applied, "diff": rows, "n_params_src": len(a), "n_params_new": len(b)},
              io.open(AUDIT_DIR / "ecap01_config_applied.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)
    return True


# --------------------------------------------------------------------------
# 2) 运行前硬门（§11）
# --------------------------------------------------------------------------
def preflight() -> bool:
    print("\n[2] 运行前硬门（§11）")

    gate("G-01", "网络 SHA16 == 冻结值（与 v1.0 同一网络）",
         sha_hex(SRC_NETWORK) == EXPECT_NETWORK_SHA16,
         "%s vs %s" % (sha_hex(SRC_NETWORK), EXPECT_NETWORK_SHA16))
    gate("G-02", "OD/plans SHA16 == 冻结值（与 v1.0 同一人口）",
         sha_hex(SRC_PLANS) == EXPECT_PLANS_SHA16,
         "%s vs %s" % (sha_hex(SRC_PLANS), EXPECT_PLANS_SHA16))

    p = all_params(NEW_CONFIG) if NEW_CONFIG.exists() else {}
    gate("G-03", "生效配置 qsim.flowCapacityFactor == 0.434977",
         p.get("qsim.flowCapacityFactor") == F_CAP, "=%s" % p.get("qsim.flowCapacityFactor"))
    gate("G-04", "生效配置 qsim.storageCapacityFactor == 0.434977",
         p.get("qsim.storageCapacityFactor") == F_CAP, "=%s" % p.get("qsim.storageCapacityFactor"))
    gate("G-05", "randomSeed 与 v1.0 相同（4711）",
         p.get("global.randomSeed") == EXPECT_SEED, "=%s" % p.get("global.randomSeed"))
    gate("G-06", "numberOfThreads 与 v1.0 相同（8）",
         p.get("global.numberOfThreads") == EXPECT_THREADS, "=%s" % p.get("global.numberOfThreads"))
    gate("G-07", "lastIteration == 19（不得为展示效果加迭代）",
         p.get("controller.lastIteration") == str(EXPECT_ITER),
         "=%s" % p.get("controller.lastIteration"))

    od = p.get("controller.outputDirectory", "")
    inside_v10 = str(ROOT / "matsim_final_7_6h").lower() in str(od).lower()
    gate("G-08", "输出目录为实验专属且不在 v1.0 内",
         str(EXP_ROOT).lower() in str(od).lower() and not inside_v10, od)

    snap = json.loads((AUDIT_DIR / "ecap01_v10_mtime_before.json").read_text(encoding="utf-8")) \
        if (AUDIT_DIR / "ecap01_v10_mtime_before.json").exists() else {}
    now = mtime_snapshot()
    drift = {k: (snap.get(k), now.get(k)) for k in now if snap.get(k) is not None
             and abs((now.get(k) or 0) - snap[k]) > 1e-6}
    gate("G-09", "v1.0 目录 mtime 未变（冻结件 0 漂移）", not drift,
         "drift=%s" % (drift if drift else "NONE"))

    gate("G-10", "1/SCALE 与写入值自洽（|1/2.29897 - 0.434977| < 5e-7）",
         abs(F_CAP_EXACT - float(F_CAP)) < 5e-7, "exact=%.12f" % F_CAP_EXACT)

    ok = all(c["pass"] for c in CHECKS)
    print("\n  硬门合计: %d/%d %s" % (sum(c["pass"] for c in CHECKS), len(CHECKS),
                                     "PASS" if ok else "FAIL"))
    with io.open(AUDIT_DIR / "ecap01_checks.csv", "w", newline="", encoding="utf-8-sig") as fh:
        w = csv.DictWriter(fh, fieldnames=["check", "name", "pass", "detail"])
        w.writeheader()
        w.writerows(CHECKS)
    return ok


# --------------------------------------------------------------------------
def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--verify", action="store_true", help="只复核，不重建配置")
    ap.add_argument("--run", action="store_true", help="派生后点火 MATSim")
    ap.add_argument("--heap", default="24g")
    a = ap.parse_args()

    for d in (CONFIG_DIR, OUT_ROOT, LOG_DIR, AUDIT_DIR):
        d.mkdir(parents=True, exist_ok=True)

    print("=" * 74)
    print("E-CAP-01  抽样需求—道路供给尺度统一试验  (EXPERIMENT ONLY / NOT v1.1)")
    print("  冻结源配置 : %s" % SRC_CONFIG.relative_to(ROOT))
    print("  独立试验根 : %s" % EXP_ROOT.relative_to(ROOT))
    print("  唯一模型改 : qsim.flowCapacityFactor / storageCapacityFactor 1.0 -> %s" % F_CAP)
    print("=" * 74)

    if not a.verify:
        (AUDIT_DIR / "ecap01_v10_mtime_before.json").write_text(
            json.dumps(mtime_snapshot(), indent=2), encoding="utf-8")
        if not build_config():
            print("\n[ABORT] 配置派生阶段硬门失败 —— 未点火。")
            return 2
    ok = preflight()
    if not ok:
        print("\n[ABORT] 运行前硬门失败 ⇒ E-CAP-01 = INVALID，不点火。")
        return 3

    if a.run:
        from matsim_env import run_java_streaming  # noqa: E402
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        log = LOG_DIR / ("%s_run.log" % RUN_ID)
        print("\n[RUN] 点火 %s（heap %s）→ %s" % (NEW_CONFIG.name, a.heap, log))
        t0 = time.time()
        rc = run_java_streaming(["org.matsim.run.RunMatsim", str(NEW_CONFIG)],
                                log_path=log, heap=a.heap)
        print("[RUN] rc=%s  用时 %.1f min" % (rc, (time.time() - t0) / 60))
        return 0 if rc == 0 else 4

    print("\n[OK] 配置与硬门就绪。点火命令：\n"
          "   python scripts/experiments/ecap01_build_config.py --run --heap 24g")
    return 0


if __name__ == "__main__":
    sys.exit(main())
