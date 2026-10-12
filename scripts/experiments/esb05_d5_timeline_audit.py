#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""
esb05_d5_timeline_audit.py — D5 判据修订时间线客观核实（★只读，零仿真、零改判）
==============================================================================
目的：核实 E-SB-05 的 D5 判据修订，发生在**执行级指标计算之前还是之后**。

只使用客观证据：
  ① Git 跟踪状态 / 提交历史（若被跟踪则可回放历史版本）
  ② 文件系统 mtime（只反映「写入时刻」，⛔ 不反映「决策时刻」）

⛔ 本脚本**不采信**协议文本中的「执行前登记」等自述；只在证据不足时明确写出「不足」。

输出：experiments/E-SB-05_exec_level_events/audit/esb05_d5_timeline_audit.json
"""
from __future__ import annotations

import datetime as _dt
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(r"D:\Luan\2026-05\2_Singapore")
EXP = ROOT / "experiments" / "E-SB-05_exec_level_events"
AUDIT = EXP / "audit"
OUT = AUDIT / "esb05_d5_timeline_audit.json"

# 关键节点（按语义分组）
NODES = {
    "protocol": EXP / "PROTOCOL_E-SB-05.md",                    # 协议（含 D5 修订说明）
    "cmp_script": ROOT / "scripts/experiments/esb05_exec_compare.py",   # 含 D5 实现
    "render_script": ROOT / "scripts/experiments/esb05_verdict_render.py",
    "readme": EXP / "README.md",
    "data_v10_exec": AUDIT / "_exec_cache/exec_V10.pkl",        # v1.0 执行级数据（早于 SB-A5）
    "data_new_exec": AUDIT / "_exec_cache/exec_NEW.pkl",        # ★SB-A5 执行级数据（关键数据点）
    "run_events": EXP / "outputs/SB-A5_EVT19_CHECK/ITERS/it.19/SB-A5_EVT19_CHECK.19.events.xml.gz",
    "run_stamp": AUDIT / "SB-A5_EVT19_CHECK_run_stamp.json",
}


def mtime(p: Path):
    if not p.exists():
        return None
    return _dt.datetime.fromtimestamp(p.stat().st_mtime)


def iso(t):
    return None if t is None else t.strftime("%Y-%m-%d %H:%M:%S")


def git_tracked(p: Path) -> bool:
    try:
        r = subprocess.run(["git", "ls-files", "--error-unmatch", str(p)],
                           cwd=str(ROOT), capture_output=True, text=True, timeout=30)
        return r.returncode == 0
    except Exception:
        return False


def git_commits(p: Path) -> list:
    try:
        r = subprocess.run(["git", "log", "--oneline", "--", str(p)],
                           cwd=str(ROOT), capture_output=True, text=True, timeout=30)
        return [ln for ln in r.stdout.splitlines() if ln.strip()]
    except Exception:
        return []


def main() -> int:
    mt = {k: mtime(v) for k, v in NODES.items()}
    tracked = {k: git_tracked(v) for k, v in NODES.items()}
    commits = {k: git_commits(v) for k, v in NODES.items()}

    t_cmp = mt["cmp_script"]       # D5 实现所在脚本的最后写入时刻
    t_proto = mt["protocol"]       # 协议（含修订说明）的最后写入时刻
    t_data = mt["data_new_exec"]   # ★SB-A5 执行级数据首次产生时刻
    t_ev = mt["run_events"]
    t_v10 = mt["data_v10_exec"]

    pre_data_by_mtime = (t_cmp is not None and t_data is not None and t_cmp < t_data)
    proto_pre_data_by_mtime = (t_proto is not None and t_data is not None and t_proto < t_data)
    gap_min = None
    if pre_data_by_mtime:
        gap_min = round((t_data - t_cmp).total_seconds() / 60.0, 1)

    any_tracked = any(tracked.values())

    # ★观察者破坏性：本轮为「恢复原始 D5」而编辑了 cmp_script，其 mtime 已被覆盖。
    #   下列快照采集于**本轮修正动作之前**（同一会话的工具输出），⛔ 修正后不可再独立复核。
    PRE_REV_SNAPSHOT = {
        "esb05_exec_compare.py": "2026-10-11 23:11:42",
        "PROTOCOL_E-SB-05.md": "2026-10-11 23:06:25",
        "_exec_cache/exec_V10.pkl": "2026-10-11 23:11:19",
        "note": ("采集于本轮 D5 修正**之前**的同一会话工具输出；"
                 "修正后 cmp_script 的 mtime 已被覆盖（见 key_points.t_d5_impl_script_mtime），"
                 "⛔ 脚本层的「修订写入时刻」已不可独立复核。"),
    }

    notes = []
    if not any_tracked:
        notes.append("Git：`esb05_*` 脚本与协议**均未被 git 跟踪** ⇒ 无提交历史可供回放 ⇒ Git 通道**不可用**。")
    if pre_data_by_mtime:
        notes.append(
            f"mtime：`esb05_exec_compare.py`（含 D5 实现）最后写入 {iso(t_cmp)}，"
            f"早于 SB-A5 执行级数据 `exec_NEW.pkl` {iso(t_data)}，间隔 {gap_min} 分钟 ⇒ "
            f"**与「修订写入先于数据」一致**。")
        notes.append(
            f"⚠️ 但 `exec_V10.pkl`（v1.0 执行级数据）在 {iso(t_v10)} 已生成，"
            f"该时点早于脚本最后写入；mtime **只记录写入时刻、不记录决策时刻** ⇒ "
            f"无法排除「构思/决定更早形成」。")
    notes.append(
        "⚠️ 观察者破坏性：本轮为**恢复原始 D5** 而编辑 `esb05_exec_compare.py`，其 mtime 已被覆盖 ⇒ "
        "脚本层「修订写入时刻」**已不可独立复核**；目前仅 `PROTOCOL`（23:06:25）与数据点"
        "（events 00:51:29 / exec_NEW 01:20:38）的 mtime 仍未被本轮动作改写。")
    notes.append("结论：mtime 证据**方向有利但不足以自证**「修订先于数据」（协议 mtime 早于数据，"
                 "且脚本层 mtime 已毁）⇒ 本审计**不主张**该结论；"
                 "D5 一律按**原始预注册判据**处置（保留 FAIL），修订版降为补充分析。")

    res = {
        "audit": "D5 修订时间线客观核实",
        "built": _dt.datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
        "evidence_channels": {
            "git": {"available": any_tracked,
                     "tracked": tracked, "commits": commits},
            "mtime": {k: iso(v) for k, v in mt.items()},
        },
        "key_points": {
            "t_d5_impl_script_mtime": iso(t_cmp),
            "t_protocol_mtime": iso(t_proto),
            "t_sba5_exec_data_mtime": iso(t_data),
            "t_sba5_events_mtime": iso(t_ev),
            "t_v10_exec_data_mtime": iso(t_v10),
            "mtime_supports_revision_before_data": bool(pre_data_by_mtime),
            "protocol_mtime_before_data": bool(proto_pre_data_by_mtime),
            "gap_script_to_data_min": gap_min,
        },
        "pre_revision_mtime_snapshot": PRE_REV_SNAPSHOT,
        "verdict": "EVIDENCE_CHANNELS_EXHAUSTED__REVISION_TIMING_UNVERIFIABLE",
        "verdict_short": "MTIME_FAVORABLE_BUT_NOT_SELF_PROVING_AND_NOW_DESTROYED",
        "disposition": {
            "d5_original": "RETAINED_AS_HARD_GATE",
            "d5_revision": "DEMOTED_TO_SUPPLEMENTARY_A5",
            "claim_original_17of17": "RETRACTED",
            "rationale": "无独立可验证通道（Git 不可用；mtime 不记录决策时刻）⇒ 不主张修订先于数据。",
        },
        "notes": notes,
    }
    AUDIT.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(res, ensure_ascii=False, indent=2), encoding="utf-8")

    print("=" * 100)
    print("D5 修订时间线核实（客观证据）")
    print("=" * 100)
    print(f"Git 通道可用：{any_tracked}")
    for k in NODES:
        print(f"  {iso(mt[k]) or 'MISSING':<20}  tracked={str(tracked[k]):<5}  {k}")
    print("-" * 100)
    for n in notes:
        print(" • " + n)
    print("-" * 100)
    print(f"[判决] {res['verdict']}")
    print(f"[处置] 原 D5 = {res['disposition']['d5_original']}；"
          f"修订版 = {res['disposition']['d5_revision']}；"
          f"「原协议 17/17」= {res['disposition']['claim_original_17of17']}")
    print(f"[out] {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
