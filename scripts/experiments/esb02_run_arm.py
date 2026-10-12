#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""
esb02_run_arm.py — E-SB-02 单臂点火（运行前硬门 + MATSim）
=========================================================
用法：
    python scripts/experiments/esb02_run_arm.py --arm SB-A5                 # 只跑运行前硬门
    python scripts/experiments/esb02_run_arm.py --arm SB-A5 --run --heap 24g # 点火

⛔ 不改任何冻结件；输出只落 experiments/E-SB-02_night_freeflow/outputs/<ARM>/
"""
from __future__ import annotations
import argparse, csv, json, sys, time
from pathlib import Path

ROOT = Path(r"D:\Luan\2026-05\2_Singapore")
sys.path.insert(0, str(ROOT / "scripts" / "experiments"))
sys.path.insert(0, str(ROOT / "scripts" / "matsim"))

import esb02_build_arms as B  # noqa: E402

EXPECT_SRC_CONFIG_SHA16 = "8f44fb349bff9cf1"   # 非压缩源配置，内容哈希稳定
ARMS = ["SB-A5", "SB-A5ind"]

CHECKS: list[dict] = []


def gate(cid, name, ok, detail=""):
    CHECKS.append({"check": cid, "name": name, "pass": bool(ok), "detail": str(detail)})
    print(f"  [{'PASS' if ok else 'FAIL'}] {cid:<6} {name}" + (f"  ({detail})" if detail else ""), flush=True)
    return bool(ok)


def preflight(arm: str) -> bool:
    cfg = B.CONFIG_DIR / f"config_{arm}.xml"
    if not gate("R-00", f"{arm} 配置存在", cfg.exists(), cfg.name):
        return False
    # ★期望哈希来自派生门禁记录（与重跑同步，不硬编码）
    gj = json.load(open(B.AUDIT_DIR / "esb02_build_gates.json", encoding="utf-8"))
    exp_src_net = gj["source_network"]["sha16"]
    exp_new_net = gj["new_network"]["sha16"]
    gate("R-01", "源配置 sha16 == 冻结", B.sha16(B.SRC_CONFIG) == EXPECT_SRC_CONFIG_SHA16, B.sha16(B.SRC_CONFIG))
    gate("R-02", "源网络内容 sha16 == 派生记录（v1.0 未被改）",
         B.sha16(B.SRC_NETWORK) == exp_src_net, B.sha16(B.SRC_NETWORK))
    b = B.all_params(cfg)
    a = B.all_params(B.SRC_CONFIG)
    net = Path(b.get("network.inputNetworkFile", ""))
    gate("R-03", "使用 SB-A5 网络且内容 sha16 == 派生记录（可复现）",
         net.exists() and B.sha16(net) == exp_new_net and str(B.NET_DIR) in str(net),
         f"{net.name} sha16={B.sha16(net) if net.exists() else 'NA'}")
    wl = {"network.inputNetworkFile", "controller.outputDirectory", "controller.runId"} | (
        {"plans.inputPlansFile"} if arm == "SB-A5ind" else set())
    diff = {k for k in set(a) | set(b) if a.get(k) != b.get(k)}
    gate("R-04", f"{arm} 配置 diff == 白名单", diff == wl, f"diff={sorted(diff)}")
    gate("R-04b", f"{arm} controller.runId == 臂名（输出文件命名正确）",
         b.get("controller.runId") == arm, f"runId={b.get('controller.runId')}")
    od = b.get("controller.outputDirectory", "")
    gate("R-05", "输出目录为实验专属且不在 v1.0 内",
         str(B.EXP).lower() in str(od).lower() and str(ROOT / "matsim_final_7_6h").lower() not in str(od).lower(), od)
    if arm == "SB-A5":
        gate("R-06", "需求 = v1.0 pop_W01（未改需求）",
             Path(b.get("plans.inputPlansFile", "")).exists()
             and "pop_W01" in b.get("plans.inputPlansFile", ""), Path(b.get("plans.inputPlansFile", "")).name)
    else:
        pl = Path(b.get("plans.inputPlansFile", ""))
        gate("R-06", "需求 = SB-A5ind 独立人口（Step5B）",
             pl.exists() and pl.name == "population_SB-A5ind_lambda_0p075.xml.gz", pl.name)
    gate("R-07", "linkStats.writeLinkStatsInterval == 1", b.get("linkStats.writeLinkStatsInterval") == "1")
    gate("R-08", "randomSeed == 4711 且 lastIteration == 19",
         b.get("global.randomSeed") == "4711" and b.get("controller.lastIteration") == "19",
         f"seed={b.get('global.randomSeed')} it={b.get('controller.lastIteration')}")
    # ★ R-09 真解析门（★第 8 次「假门禁」修正）：只查「存在 + 文件名」放行过一个
    #    从 line 2 就 FATAL 的 population（缺 DOCTYPE / 属性写成 value= 形式）。
    #    这里直接调 MATSim 官方 PopulationReader 实际解析 ⇒ 「门过 ⇔ 能读进去」。
    pl = Path(b.get("plans.inputPlansFile", ""))
    probe = ROOT / "scripts" / "experiments" / "matsim_pop_probe.py"
    if pl.exists():
        import re as _re
        import subprocess as _sp
        try:
            r = _sp.run([sys.executable, str(probe), str(pl)], capture_output=True, text=True,
                        encoding="utf-8", errors="replace", timeout=600)
            out = (r.stdout or "") + (r.stderr or "")
            m = _re.search(r"PROBE_OK=1\s+persons=(\d+)\s+sumEF=([\d.]+)\s+withEF=(\d+)\s+missingEF=(\d+)", out)
            n_pers = int(m.group(1)) if m else -1
            exp_n = 236044 if arm == "SB-A5ind" else 236044
            if m:
                gate("R-09", f"{arm} 需求可被 MATSim PopulationReader 真解析（真门禁）",
                     n_pers == exp_n and int(m.group(3)) == exp_n and int(m.group(4)) == 0,
                     f"persons={n_pers} sumEF={m.group(2)} withEF={m.group(3)} missingEF={m.group(4)}")
            else:
                tail = out.strip().splitlines()[-1][:140] if out.strip() else "no output"
                gate("R-09", f"{arm} 需求可被 MATSim PopulationReader 真解析（真门禁）", False, tail)
        except Exception as e:  # noqa: BLE001
            gate("R-09", f"{arm} 需求可被 MATSim PopulationReader 真解析（真门禁）", False,
                 f"{type(e).__name__}: {e}")
    else:
        gate("R-09", f"{arm} 需求可被 MATSim PopulationReader 真解析（真门禁）", False, "file missing")
    return all(c["pass"] for c in CHECKS)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--arm", required=True, choices=ARMS)
    ap.add_argument("--run", action="store_true")
    ap.add_argument("--heap", default="24g")
    args = ap.parse_args()

    for d in (B.AUDIT_DIR, B.LOG_DIR):
        d.mkdir(parents=True, exist_ok=True)
    (B.OUT_ROOT / args.arm).mkdir(parents=True, exist_ok=True)

    print("=" * 84)
    print(f"E-SB-02 单臂点火：{args.arm}  (EXPERIMENT ONLY / NOT v1.1)")
    print("=" * 84)
    ok = preflight(args.arm)
    with open(B.AUDIT_DIR / f"{args.arm}_run_gates.csv", "w", newline="", encoding="utf-8-sig") as fh:
        w = csv.DictWriter(fh, fieldnames=["check", "name", "pass", "detail"])
        w.writeheader(); w.writerows(CHECKS)
    if not ok:
        print(f"\n[ABORT] 运行前硬门失败 ⇒ {args.arm} = INVALID，不点火。")
        return 3
    if not args.run:
        print("\n[OK] 运行前硬门全通过。点火：--run --heap 24g")
        return 0

    from matsim_env import run_java_streaming  # noqa: E402
    log = B.LOG_DIR / f"{args.arm}_run.log"
    print(f"\n[RUN] 点火 {args.arm}（heap {args.heap}）→ {log}")
    t0 = time.time()
    rc = run_java_streaming(["org.matsim.run.RunMatsim", str(B.CONFIG_DIR / f"config_{args.arm}.xml")],
                            log_path=log, heap=args.heap)
    print(f"[RUN] rc={rc} 用时 {(time.time()-t0)/60:.1f} min")
    return 0 if rc == 0 else 4


if __name__ == "__main__":
    sys.exit(main())
