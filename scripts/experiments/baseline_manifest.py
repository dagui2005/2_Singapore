# -*- coding: utf-8 -*-
"""基线 SHA-256 清单（E-SB-05 / E-SB-06 证据封存）

目的：回答一个比「结论对不对」更基础的问题——
    **今天用来支撑这些结论的文件，是否就是当时真正生成和复核过的那一批文件？**

做法：
  (1) 对用户点名覆盖的 5 类对象逐文件登记：相对路径 / 大小 / sha256(容器) / sha256(内容)
      / gz 原始大小与头 mtime / **证据角色** / 所属结论；
  (2) 关系式复核（不靠硬编码，直接比两侧原始文件）：
        R1 EVT19 it.19 linkstats ≡ SB-A5 it.19 linkstats（容器+内容）
        R2 v1.0 W01_events it.19 linkstats ≡ v1.0 W01_rc_min it.19 linkstats（容器+内容）
        R3 EVT19 config vs SB-A5 config 参数差 == 白名单 3 项
        R4 W01_events config vs W01_rc_min config 参数差 == 白名单 3 项
      ⇒ 把「开 events 未改动力学」从**单侧**提升为**双侧对称**证据；
  (3) 在项目工作目录**之外**留一份副本（清单 + 证据文件），并**只增不改**：
      目标版本目录已存在 ⇒ 自动改用 `__v2/__v3/...`，⛔ 绝不覆盖；
  (4) 生成外部**独立核验器** `VERIFY_BASELINE_MANIFEST.py`（零依赖），
      以后接手者可在任何机器上重算并比对，无需本项目环境。

哈希口径（★必须区分，勿混用）：
  - `sha256_container`：文件字节本身。**用于「是否同一批文件」的同一性/防篡改核验**
    （容器字节相同 ⟺ 文件完全相同，逻辑上充分）。
  - `sha256_content`：gz 解压后的**内容**哈希。**用于跨运行的可比性判断**
    （同内容可能因 deflate 分块不同而容器字节不同）。
  本清单对 ≤ CONTENT_HASH_MAX 的 gz 计算内容哈希；超过阈值者只登记容器哈希并显式标注
  （理由：事件文件 ~1.7 GB/个，解压后 ~14.7 GB，容器同一性已足以支撑封存目的）。

本脚本不改动任何被登记文件（只读），不改模型、不跑仿真。
"""
from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
import os
import re
import shutil
import struct
import sys
import time
from pathlib import Path

# ------------------------------------------------------------------ 常量
PROJECT = Path(r"D:\Luan\2026-05\2_Singapore")
EXT_BASE = Path(r"K:\_sg_matsim_baseline_freeze")
STAMP = "2026-10-12"
CONTENT_HASH_MAX = 300_000_000      # 超过此体积的 gz 只登记容器哈希
MANIFEST_BASENAME = "BASELINE_MANIFEST_%s" % STAMP

# 冻结锚点（来自 E-SB-05 运行前硬门 / 一致性门，独立重算应逐位复现）
ANCHOR_NET_SB_A5 = "7978681b2a4ab54d1c14890943bf37012d51a003dd14c10dcfd447776eca6dab"
ANCHOR_POP_W01 = "e96ed83ff59c0f5ecb50c9d9ff2d42a4b4bdbebf2bbfe81a1e0604fb94921fbd"
ANCHOR_EVT19_LS_CT = "ddc879a07dfedb429367e90b8f880afc6ee630886d1d0bfc1129297bd43f9d3e"
ANCHOR_EVT19_LS_CONTENT = "fdc6ff5cd7e40000ad673f20d7adf698741dcb533162570c5833d57f0e5e96cf"

# 白名单 3 项（param 名；XML 内 param 不带 module 前缀）
WHITELIST_3 = {"outputDirectory", "runId", "writeEventsInterval"}
WHITELIST_3_FQ = {"controller." + k for k in WHITELIST_3}
W01_EVENTS_CFG = "matsim_viz_7_8/configs/config_W01_events.xml"

EVT = "experiments/E-SB-05_exec_level_events"
V10_OUT = "matsim_final_7_6h/outputs/W01_rc_min"
V10_EVT = "matsim_viz_7_8/outputs/W01_events"
SBA5_OUT = "experiments/E-SB-02_night_freeflow/outputs/SB-A5"
EVT19_OUT = EVT + "/outputs/SB-A5_EVT19_CHECK"

# ------------------------------------------------------------------ 清单定义
# (组键, 组标签, 相对路径, 证据角色, 关联结论)
E = []
def add(gk, gl, rel, role, claim):
    E.append({"group": gk, "group_label": gl, "rel": rel, "role": role, "claim": claim})

GA, GB, GC, GD, GE, GF, GG = (
    "A", "B", "C", "D", "E", "F", "G")
LA = "A 冻结声明 / 协议 / 判决书（可读证据链主干）"
LB = "B 复核与判定脚本（可复算入口）"
LC = "C 原始门禁 / 逐文件哈希 / 独立复核原始结果"
LD = "D 逐人配对缓存（执行级重建产物）"
LE = "E 配置与输入（三侧：v1.0 / SB-A5 / EVT19）"
LF = "F 运行产物与锚点（events / linkstats / 日志）"
LG = "G 上游计划级参照（E-SB-04 / 04B）"

# ---- A
add(GA, LA, "reports/project_baseline/BASELINE_FREEZE_2026-10-12.md", "基线冻结声明（含本清单保护节）", "全局状态")
add(GA, LA, EVT + "/PROTOCOL_E-SB-05.md", "E-SB-05 预注册协议（含原 D5 保留 FAIL 与协议真空披露）", "O2/O3")
add(GA, LA, EVT + "/README.md", "E-SB-05 实验说明", "O2/O3")
add(GA, LA, "reports/exec_level_events_E_SB_05/VERDICT_E-SB-05.md", "E-SB-05 判决书（并列双读法）", "E1–E3 / O2/O3")
add(GA, LA, "reports/exec_level_events_E_SB_05/exec_level_scorecard.csv", "E-SB-05 评分卡（门禁逐项）", "O2")
add(GA, LA, "experiments/E-SB-06_signal_feasibility/PROTOCOL_E-SB-06.md", "E-SB-06 可行性审查协议", "E5")
add(GA, LA, "experiments/E-SB-06_signal_feasibility/README.md", "E-SB-06 实验说明", "E5")
add(GA, LA, "reports/esb06_signal_feasibility/FEASIBILITY_E-SB-06.md", "E-SB-06 可行性审查报告", "E5")

# ---- B
add(GB, LB, "scripts/experiments/esb05_independent_recheck.py", "★独立复核脚本（37/37，绕过自产 summary 直算原始层）", "全局状态")
add(GB, LB, "scripts/experiments/esb05_exec_compare.py", "E-SB-05 判决合成（D5 已恢复原始预注册判据）", "O2/O3")
add(GB, LB, "scripts/experiments/esb05_verdict_render.py", "E-SB-05 判决书渲染（全动态）", "O2/O3")
add(GB, LB, "scripts/experiments/esb05_events_exec_route.py", "执行路线重建（events → 逐人链路序列）", "E2/E3")
add(GB, LB, "scripts/experiments/esb05_consistency_check.py", "运行一致性检查（A/B/C 判定）", "E1")
add(GB, LB, "scripts/experiments/esb05_preflight.py", "运行前硬门 G00–G13（含负例门禁）", "E1")
add(GB, LB, "scripts/experiments/esb05_build_config.py", "配置派生（白名单 3 项 + 逐字节回填断言）", "E1")
add(GB, LB, "scripts/experiments/esb05_run.py", "仿真驱动（heap 24g）", "E1")
add(GB, LB, "scripts/experiments/esb05_d5_timeline_audit.py", "D5 修订时间线核实（含观察者破坏性）", "O4")
add(GB, LB, "scripts/experiments/esb06_signal_feasibility_probe.py", "信号可行性探针（零仿真静态审计）", "E5")
add(GB, LB, "scripts/experiments/baseline_manifest.py", "★本清单生成器（自登记：日后被改动可检出）", "全局状态")
add(GB, LB, "scripts/matsim/matsim_env.py", "MATSim 运行环境封装（两侧共用）", "E1")

# ---- C
add(GC, LC, EVT + "/audit/esb05_preflight.csv", "运行前 16 项硬门明细（实测值）", "E1")
add(GC, LC, EVT + "/audit/input_manifest.json", "输入哈希登记（网络/人口）", "E1")
add(GC, LC, EVT + "/audit/run_config_manifest.json", "配置清单（白名单 diff 与逐字节回填）", "E1")
add(GC, LC, EVT + "/audit/SB-A5_EVT19_CHECK_run_stamp.json", "运行时刻 / 耗时 / heap", "E1")
add(GC, LC, EVT + "/audit/esb05_consistency_gates.csv", "运行一致性门禁 A/B/C 明细", "E1")
add(GC, LC, EVT + "/audit/esb05_consistency_files.csv", "★79/79 逐文件双侧哈希（确定性产物）", "E1")
add(GC, LC, EVT + "/audit/esb05_consistency_summary.json", "运行一致性判决 CONSISTENT_STRICT", "E1")
add(GC, LC, EVT + "/audit/esb05_events_integrity.json", "events 完整性（10 类 / 236,044）", "E1")
add(GC, LC, EVT + "/audit/esb05_exec_route_gates.csv", "★执行级门禁 16/17（含原 D5 FAIL）", "E2/E3 / O2")
add(GC, LC, EVT + "/audit/esb05_exec_route_compare.csv", "执行路线逐人配对（改变率 66.060270%）", "E2")
add(GC, LC, EVT + "/audit/esb05_exec_corridor_use.csv", "走廊里程份额 / 使用率 Δ（PIE/TPE 等）", "E3 / O2")
add(GC, LC, EVT + "/audit/esb05_exec_route_summary.json", "执行级配对汇总 + 双读法判定 + 协议真空标记", "E2/E3 / O2/O3")
add(GC, LC, EVT + "/audit/esb05_independent_recheck.json", "★独立复核原始结果（37/37，0 MISMATCH）", "全局状态")
add(GC, LC, EVT + "/audit/esb05_d5_timeline_audit.json", "★D5 修订时间线核实（证据通道穷尽）", "O4")
add(GC, LC, EVT + "/audit/SB-A5_EVT19_CHECK_allhours_conv.linkstats.txt.gz", "全时段 cycle-mean linkstats（08-09 口径复核用）", "E1")
add(GC, LC, "experiments/E-SB-06_signal_feasibility/audit/esb06_probe.json", "E-SB-06 探针原始结果（网络/配置/jar/LTA 数据）", "E5")
add(GC, LC, "experiments/E-SB-06_signal_feasibility/audit/esb06_feasibility_gates.csv", "E-SB-06 可行性门禁明细（有效 5/14）", "E5")
for _f in ("esb05_exec_corridor_use.csv", "esb05_exec_route_compare.csv",
           "esb05_exec_route_gates.csv", "esb05_exec_route_summary.json",
           "exec_level_scorecard.csv", "VERDICT_E-SB-05.md"):
    add(GC, LC, EVT + "/audit/_revision_history/v1_17of17/" + _f,
        "版本留痕：已撤回的「17/17」版产物（只增不改）", "O2/O4")

# ---- D
add(GD, LD, EVT + "/audit/_exec_cache/exec_V10.pkl", "★v1.0 逐人执行路线（236,039 人）", "E2/E3")
add(GD, LD, EVT + "/audit/_exec_cache/exec_V10.meta.json", "v1.0 执行路线扫描元数据（单侧 events 来源）", "E2/E3")
add(GD, LD, EVT + "/audit/_exec_cache/exec_NEW.pkl", "★EVT19 逐人执行路线（236,039 人）", "E2/E3")
add(GD, LD, EVT + "/audit/_exec_cache/exec_NEW.meta.json", "EVT19 执行路线扫描元数据", "E2/E3")

# ---- E
add(GE, LE, EVT + "/configs/config_SB-A5_EVT19_CHECK.xml", "EVT19 配置（与 SB-A5 仅差白名单 3 项）", "E1")
add(GE, LE, "experiments/E-SB-02_night_freeflow/configs/config_SB-A5.xml", "SB-A5 配置（原方案）", "E1/E3")
add(GE, LE, "matsim_final_7_6h/configs/config_W01_rc_min.xml", "v1.0 冻结配置（W01 工作点）", "E1/E2")
add(GE, LE, W01_EVENTS_CFG, "v1.0 侧 events 重跑配置（配对**双侧对称**的证据）", "E1")
add(GE, LE, "experiments/E-SB-02_night_freeflow/networks/network_SB-A5.xml.gz", "关键网络：SB-A5 / EVT19 输入", "E1/E3")
add(GE, LE, "reports/matsim_network/network_cleaned.xml.gz", "关键网络：v1.0 输入", "E1/E2")
add(GE, LE, "matsim_final_7_6h/populations/pop_W01/population_lambda_0p075.xml.gz", "共用人口（三侧同源，236,044 人）", "E1/E2/E3")
add(GE, LE, "matsim_final_7_6h/final_workingpoint_7_6h_frozen_parameters.csv", "7.6H 冻结参数表", "E1")
add(GE, LE, "matsim_final_7_6h/final_workingpoint_7_6h_config_validation.json", "7.6H 配置校验", "E1")
add(GE, LE, "matsim_final_7_6h/final_workingpoint_7_6h_config_provenance.csv", "7.6H 配置来源链", "E1")
add(GE, LE, "matsim_final_7_6h/final_workingpoint_7_6h_source_invariance.csv", "7.6H 来源不变性", "E1")
add(GE, LE, "matsim_final_7_6h/final_workingpoint_7_6h_matrix.csv", "7.6H 工作点矩阵", "E1")

# ---- F
add(GF, LF, EVT19_OUT + "/ITERS/it.0/SB-A5_EVT19_CHECK.0.events.xml.gz", "EVT19 it.0 events（earlyIteration 语义产物）", "E1")
add(GF, LF, EVT19_OUT + "/ITERS/it.19/SB-A5_EVT19_CHECK.19.events.xml.gz", "★EVT19 it.19 events（执行级重建的原始输入）", "E2/E3")
add(GF, LF, EVT19_OUT + "/SB-A5_EVT19_CHECK.output_events.xml.gz", "EVT19 收尾事件副本（DumpDataAtEnd 同源）", "E1/E2")
add(GF, LF, EVT19_OUT + "/SB-A5_EVT19_CHECK.output_plans.xml.gz", "EVT19 输出计划（路线对账的另一侧）", "E2")
add(GF, LF, EVT19_OUT + "/SB-A5_EVT19_CHECK.output_network.xml.gz", "EVT19 运行期网络（证明网络未被改动）", "E1")
add(GF, LF, EVT19_OUT + "/ITERS/it.19/SB-A5_EVT19_CHECK.19.linkstats.txt.gz", "★锚点：EVT19 it.19 linkstats（容器+内容双双逐位同）", "E1")
add(GF, LF, EVT19_OUT + "/ITERS/it.19/SB-A5_EVT19_CHECK.19.legHistogram.txt", "确定性产物（79/79 成员）", "E1")
add(GF, LF, EVT19_OUT + "/ITERS/it.19/SB-A5_EVT19_CHECK.19.legdurations.txt", "确定性产物（79/79 成员）", "E1")
add(GF, LF, EVT19_OUT + "/SB-A5_EVT19_CHECK.scorestats.csv", "评分轨迹（逐迭代）", "E1")
add(GF, LF, EVT19_OUT + "/SB-A5_EVT19_CHECK.stopwatch.csv", "阶段耗时", "E1")
add(GF, LF, EVT19_OUT + "/SB-A5_EVT19_CHECK.logfileWarningsErrors.log", "收尾 5 类可选 dump ERROR（与 SB-A5 逐项相同）", "E1（日志特征）")
add(GF, LF, SBA5_OUT + "/SB-A5.logfileWarningsErrors.log", "SB-A5 侧同项日志（对照）", "E1（日志特征）")
add(GF, LF, SBA5_OUT + "/ITERS/it.19/SB-A5.19.linkstats.txt.gz", "★参照锚点：SB-A5 it.19 linkstats", "E1")
add(GF, LF, SBA5_OUT + "/ITERS/it.19/SB-A5.19.legHistogram.txt", "参照：SB-A5 确定性产物", "E1")
add(GF, LF, SBA5_OUT + "/ITERS/it.19/SB-A5.19.legdurations.txt", "参照：SB-A5 确定性产物", "E1")
add(GF, LF, V10_OUT + "/ITERS/it.19/W01_rc_min.19.linkstats.txt.gz", "★锚点：v1.0 冻结模型 it.19 linkstats", "E1/E2")
add(GF, LF, V10_EVT + "/ITERS/it.19/W01_events.19.linkstats.txt.gz", "★锚点：v1.0 侧 events 重跑 it.19 linkstats（≡ 冻结模型）", "E1")
add(GF, LF, V10_EVT + "/W01_events.output_events.xml.gz", "★v1.0 执行级重建的原始输入（exec_V10 来源）", "E2/E3")
add(GF, LF, V10_EVT + "/W01_events.output_plans.xml.gz", "v1.0 输出计划（对账另一侧）", "E2")
add(GF, LF, EVT + "/logs/SB-A5_EVT19_CHECK_run.log", "EVT19 运行日志（rc=0 / 125.7 min）", "E1")
add(GF, LF, EVT + "/logs/esb05_scan_NEW.log", "EVT19 执行路线扫描日志", "E2")
add(GF, LF, EVT + "/logs/esb05_compare_v2.log", "★恢复原始 D5 后的判决合成日志（现行版本）", "O2")
add(GF, LF, EVT + "/logs/esb05_compare.log", "首轮（已撤回）判决合成日志（留痕）", "O2/O4")

# ---- G
for _n, _r in (("routes_v1.0.pkl", "v1.0 逐人计划路线（计划级）"),
               ("routes_SB-A5.pkl", "SB-A5 逐人计划路线（计划级）"),
               ("cls_v1.0.pkl", "v1.0 逐人等级里程分类"),
               ("cls_SB-A5.pkl", "SB-A5 逐人等级里程分类")):
    add(GG, LG, "experiments/E-SB-04_path_redistribution_audit/_cache/" + _n, _r, "E2/E3")
for _n, _r in (("fidelity.json", "plans↔events 保真抽样（8,000/8,000）"),
               ("info_v1.0.json", "v1.0 计划结构信息"),
               ("info_SB-A5.json", "SB-A5 计划结构信息")):
    add(GG, LG, "experiments/E-SB-04_path_redistribution_audit/_cache/" + _n, _r, "E2")
add(GG, LG, "reports/path_redistribution_audit_E_SB_04/route_change_summary.csv", "计划级改变率 66.058870%", "E2")
add(GG, LG, "reports/path_redistribution_audit_E_SB_04/roadclass_route_share_pivot.csv", "计划级等级份额（+3.5742 pp）", "E3")
add(GG, LG, "reports/path_redistribution_audit_E_SB_04/VERDICT_E-SB-04.md", "E-SB-04 判决书（计划级）", "E2/E3")

# 显式排除（必须写明，避免「清单像全量」的错觉）
EXCLUDED = [
    ("experiments/E-SB-02_night_freeflow/outputs/SB-A5ind/**",
     "SB-A5ind 全链（population 异于 SB-A5 ⇒ 不可与 SB-A5 路线差配对；不支撑冻结结论）"),
    ("experiments/E-SB-04_path_redistribution_audit/_cache/routes_SB-A5ind.pkl 等 SB-A5ind 缓存",
     "同上（仅参照，未被任何冻结结论引用）"),
    ("tools/matsim-2026.0/matsim-2026.0.jar 与 libs/**.jar",
     "发行版二进制（可重新获取；E-SB-06 已记录版本与类清单结论）"),
    ("experiments/E-SB-05_exec_level_events/outputs/SB-A5_EVT19_CHECK/ITERS/it.1–it.18",
     "中间迭代产物（结论仅依赖 it.0 / it.19 与确定性产物哈希表）"),
]

# ------------------------------------------------------------------ 工具函数
def sha256_file(p: Path, chunk: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for c in iter(lambda: f.read(chunk), b""):
            h.update(c)
    return h.hexdigest()


def sha256_gz_content(p: Path, chunk: int = 1 << 20):
    """返回 (sha256(解压内容), 解压字节数)。gz 内容才是跨运行可比的权威口径。"""
    h = hashlib.sha256()
    n = 0
    with gzip.open(p, "rb") as f:
        for c in iter(lambda: f.read(chunk), b""):
            h.update(c)
            n += len(c)
    return h.hexdigest(), n


def gz_header_mtime(p: Path):
    try:
        with open(p, "rb") as f:
            hdr = f.read(10)
        if len(hdr) < 10:
            return None
        return struct.unpack("<I", hdr[4:8])[0]
    except Exception:
        return None


def is_gz(p: Path) -> bool:
    return p.suffix.lower() in (".gz", ".tgz") or p.name.lower().endswith(".gz")


def rel_files(root: Path, prefix: str):
    """列目录下所有文件（相对 root 的 POSIX 相对路径）"""
    base = root / prefix
    if not base.exists():
        return []
    return sorted(str(p.relative_to(root)).replace("\\", "/")
                  for p in base.rglob("*") if p.is_file())


def next_free(path: Path) -> Path:
    """★只增不改：目标已存在 ⇒ 用 `__v2/__v3/...` 递增，绝不覆盖既有版本。
    版本标记插在**扩展名之前**（`NAME__v2.json`），对目录同样成立（`2026-10-12__v2`）。"""
    if not path.exists():
        return path
    k = 2
    while True:
        cand = path.with_name("%s__v%d%s" % (path.stem, k, path.suffix))
        if not cand.exists():
            return cand
        k += 1


def params_of(cfg: Path):
    s = cfg.read_text(encoding="utf-8", errors="replace")
    return dict(re.findall(r'<param name="([^"]+)" value="([^"]*)"', s))


GATES = []
def gate(gid, desc, ok, detail):
    GATES.append({"id": gid, "gate": desc, "pass": bool(ok), "detail": detail})
    print(f"[{'PASS' if ok else 'FAIL'}] {gid:<5} {desc}  | {detail}")


# ------------------------------------------------------------------ 主流程
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-copy", action="store_true", help="只生成清单，不做外部副本")
    ap.add_argument("--ext", default=str(EXT_BASE), help="外部副本根目录")
    args = ap.parse_args()

    t0 = time.time()
    print("=" * 108)
    print(f"基线 SHA-256 清单生成 ｜ 项目根 {PROJECT} ｜ 戳记 {STAMP}")
    print("=" * 108)

    # ---------------- 1. 逐文件登记
    rows = []
    for e in E:
        p = PROJECT / e["rel"]
        rec = {"group": e["group"], "group_label": e["group_label"],
               "relpath": e["rel"], "role": e["role"], "claim": e["claim"],
               "exists": p.exists()}
        if p.exists():
            rec["size_bytes"] = p.stat().st_size
            rec["mtime"] = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(p.stat().st_mtime))
            rec["sha256_container"] = sha256_file(p)
            rec["gz_uncompressed_bytes"] = None
            rec["gz_header_mtime"] = None
            rec["sha256_content"] = None
            if is_gz(p):
                rec["gz_header_mtime"] = gz_header_mtime(p)
                if rec["size_bytes"] <= CONTENT_HASH_MAX:
                    h, n = sha256_gz_content(p)
                    rec["sha256_content"] = h
                    rec["gz_uncompressed_bytes"] = n
                else:
                    rec["content_note"] = ("体积 %.2f GB > %.0f MB ⇒ 仅登记容器哈希；"
                                           "容器字节相同 ⟺ 文件完全相同，足以支撑同一性核验"
                                           % (rec["size_bytes"] / 2**30, CONTENT_HASH_MAX / 2**20))
        else:
            rec.update({"size_bytes": None, "mtime": None, "sha256_container": None,
                        "sha256_content": None, "gz_uncompressed_bytes": None,
                        "gz_header_mtime": None})
        rows.append(rec)

    by_rel = {r["relpath"]: r for r in rows}
    n_missing = sum(1 for r in rows if not r["exists"])
    total_bytes = sum(r["size_bytes"] or 0 for r in rows)

    print(f"\n登记条目 {len(rows)} 项 ｜ 总计 {total_bytes/2**30:.2f} GiB ｜ 缺失 {n_missing}")
    for gk in (GA, GB, GC, GD, GE, GF, GG):
        sub = [r for r in rows if r["group"] == gk]
        print(f"  {gk}: {len(sub):>3} 项  {sum(r['size_bytes'] or 0 for r in sub)/2**20:>10.1f} MiB  {sub[0]['group_label'] if sub else ''}")

    # ---------------- 2. 门禁
    print("\n" + "-" * 108)
    gate("M00", "登记条目数 ≥ 40（防空表假门禁）", len(rows) >= 40, f"n={len(rows)}")
    gate("M01", "全部登记文件存在", n_missing == 0, f"missing={n_missing}")
    gate("M02", "7 个组均非空（覆盖用户点名的全部对象类）",
         all(any(r["group"] == gk for r in rows) for gk in (GA, GB, GC, GD, GE, GF, GG)),
         "A/B/C/D/E/F/G 各 ≥1")
    gate("M03", "无零字节文件", all((r["size_bytes"] or 0) > 0 for r in rows),
         f"zero={sum(1 for r in rows if (r['size_bytes'] or 0) == 0)}")

    # 负例：哈希有分辨力
    probe = PROJECT / "experiments/E-SB-05_exec_level_events/audit/esb05_exec_route_gates.csv"
    if probe.exists():
        orig = sha256_file(probe)
        tmp = Path(os.environ.get("TEMP", ".")) / "_baseline_neg_probe.bin"
        data = bytearray(probe.read_bytes())
        data[len(data) // 2] ^= 0x01
        tmp.write_bytes(bytes(data))
        alt = sha256_file(tmp)
        tmp.unlink(missing_ok=True)
        gate("M04", "（负例）改 1 字节 ⇒ sha256 必变（登记有分辨力）", orig != alt,
             f"orig={orig[:16]}… alt={alt[:16]}…")

    # 锚点（独立重算 vs 冻结值）
    r = by_rel.get("experiments/E-SB-02_night_freeflow/networks/network_SB-A5.xml.gz", {})
    gate("M05", "锚点：SB-A5/EVT19 输入网络 sha256 == 运行前硬门登记值",
         r.get("sha256_container") == ANCHOR_NET_SB_A5,
         f"got={(r.get('sha256_container') or '')[:24]}… exp={ANCHOR_NET_SB_A5[:24]}…")
    r = by_rel.get("matsim_final_7_6h/populations/pop_W01/population_lambda_0p075.xml.gz", {})
    gate("M06", "锚点：共用人口 sha256 == 运行前硬门登记值",
         r.get("sha256_container") == ANCHOR_POP_W01,
         f"got={(r.get('sha256_container') or '')[:24]}… exp={ANCHOR_POP_W01[:24]}…")
    r = by_rel.get(EVT19_OUT + "/ITERS/it.19/SB-A5_EVT19_CHECK.19.linkstats.txt.gz", {})
    gate("M07", "锚点：EVT19 it.19 linkstats 容器 + 内容 sha256 双双 == 冻结值",
         r.get("sha256_container") == ANCHOR_EVT19_LS_CT and
         r.get("sha256_content") == ANCHOR_EVT19_LS_CONTENT,
         f"ct={(r.get('sha256_container') or '')[:20]}… content={(r.get('sha256_content') or '')[:20]}…")

    # 关系式 R1：EVT19 ≡ SB-A5（运行一致性锚）
    a = by_rel.get(EVT19_OUT + "/ITERS/it.19/SB-A5_EVT19_CHECK.19.linkstats.txt.gz", {})
    b = by_rel.get(SBA5_OUT + "/ITERS/it.19/SB-A5.19.linkstats.txt.gz", {})
    gate("M08", "★关系式 R1：EVT19 it.19 linkstats ≡ SB-A5 it.19（容器+内容）⇒ 开 events 未改动力学",
         a.get("sha256_container") and a.get("sha256_container") == b.get("sha256_container")
         and a.get("sha256_content") == b.get("sha256_content"),
         f"ct_eq={a.get('sha256_container') == b.get('sha256_container')} "
         f"content_eq={a.get('sha256_content') == b.get('sha256_content')}")

    # 关系式 R2：v1.0 侧对称（W01_events ≡ W01_rc_min）
    c = by_rel.get(V10_EVT + "/ITERS/it.19/W01_events.19.linkstats.txt.gz", {})
    d = by_rel.get(V10_OUT + "/ITERS/it.19/W01_rc_min.19.linkstats.txt.gz", {})
    gate("M09", "★关系式 R2：v1.0 侧 W01_events it.19 ≡ W01_rc_min it.19（容器+内容）⇒ 配对**双侧对称**",
         c.get("sha256_container") and c.get("sha256_container") == d.get("sha256_container")
         and c.get("sha256_content") == d.get("sha256_content"),
         f"ct_eq={c.get('sha256_container') == d.get('sha256_container')} "
         f"content_eq={c.get('sha256_content') == d.get('sha256_content')}")

    # 关系式 R3 / R4：配置差异恰为白名单 3 项
    def cfg_diff(p_new, p_old):
        A, B = params_of(PROJECT / p_new), params_of(PROJECT / p_old)
        diff = {k for k in set(A) | set(B) if A.get(k) != B.get(k)}
        return diff, {k.split(".", 1)[-1] for k in diff}

    d3, _ = cfg_diff(EVT + "/configs/config_SB-A5_EVT19_CHECK.xml",
                     "experiments/E-SB-02_night_freeflow/configs/config_SB-A5.xml")
    gate("M10", "★关系式 R3：EVT19 vs SB-A5 配置差异 == 白名单 3 项",
         d3 == WHITELIST_3, f"diff={sorted(d3)}({len(d3)})")
    d4, _ = cfg_diff(W01_EVENTS_CFG, "matsim_final_7_6h/configs/config_W01_rc_min.xml")
    gate("M11", "★关系式 R4：v1.0 侧 events 重跑 vs 冻结配置差异 == 白名单 3 项",
         d4 == WHITELIST_3, f"diff={sorted(d4)}({len(d4)})")

    # 负例：目标版本目录已存在时，next_free 取 `__v2` 且**不触碰**既有目录（只增不改）
    import tempfile
    _t = Path(tempfile.mkdtemp(prefix="_bl_neg_"))
    (_t / "S").mkdir()
    _keep = _t / "S" / "keep.txt"
    _keep.write_text("KEEP", encoding="utf-8")
    _got = next_free(_t / "S")
    gate("M12", "（负例）目标版本目录已存在 ⇒ next_free 取 `__v2` 且既有目录**内容未变**（只增不改）",
         _got.name == "S__v2" and _keep.read_text(encoding="utf-8") == "KEEP" and not _got.exists(),
         f"got={_got.name} keep_intact={_keep.read_text(encoding='utf-8') == 'KEEP'}")
    shutil.rmtree(_t, ignore_errors=True)

    n_eff = len(GATES)
    n_pass = sum(1 for g in GATES if g["pass"])
    print("-" * 108)

    # ---------------- 3. 清单落盘（项目内，版本化不覆盖）
    out_dir = PROJECT / "reports" / "project_baseline"
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = next_free(out_dir / (MANIFEST_BASENAME + ".json"))
    csv_path = next_free(out_dir / (MANIFEST_BASENAME + ".csv"))
    md_path = next_free(out_dir / (MANIFEST_BASENAME + ".md"))

    meta = {
        "built": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "stamp": STAMP,
        "project_root": str(PROJECT),
        "generator": "scripts/experiments/baseline_manifest.py",
        "purpose": "回答「今天支撑结论的文件是否就是当时生成并复核过的那一批」——逐文件相对路径/大小/sha256/证据角色，外部留只增不改副本",
        "hash_convention": {
            "sha256_container": "文件字节本身；用于同一性/防篡改核验（容器相同 ⟺ 文件完全相同）",
            "sha256_content": "gz 解压内容；用于跨运行可比性判断（同内容可能容器字节不同）",
            "content_hash_threshold_bytes": CONTENT_HASH_MAX,
        },
        "entries": rows,
        "excluded": [{"pattern": p, "reason": r} for p, r in EXCLUDED],
        "gates": GATES,
        "summary": {
            "n_entries": len(rows), "n_missing": n_missing,
            "total_bytes": total_bytes,
            "total_gib": round(total_bytes / 2**30, 3),
            "n_gates": n_eff, "n_gates_pass": n_pass,
            "verdict": ("BASELINE_MANIFEST_SEALED" if n_missing == 0 else
                        "BASELINE_MANIFEST_INCOMPLETE"),
        },
        "elapsed_sec": None,
    }

    csv_cols = ["group", "group_label", "relpath", "role", "claim", "exists",
                "size_bytes", "mtime", "sha256_container", "sha256_content",
                "gz_uncompressed_bytes", "gz_header_mtime", "content_note"]
    with open(csv_path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=csv_cols, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow(r)

    # ---------------- 4. 外部副本（只增不改）
    ext_info = {"enabled": False}
    if not args.no_copy:
        ext_base = Path(args.ext)
        ext_base.mkdir(parents=True, exist_ok=True)
        ver_dir = next_free(ext_base / STAMP)
        chosen_existed_before = ver_dir.exists()
        existed = sorted(x.name for x in ext_base.iterdir()
                         if x.is_dir() and x.name.startswith(STAMP))
        ver_dir.mkdir(parents=True, exist_ok=False)
        files_dir = ver_dir / "files"
        man_dir = ver_dir / "manifest"
        files_dir.mkdir(parents=True, exist_ok=True)
        man_dir.mkdir(parents=True, exist_ok=True)

        copied, copy_rows, mismatch = 0, [], 0
        for r in rows:
            if not r["exists"]:
                continue
            src = PROJECT / r["relpath"]
            dst = files_dir / r["relpath"]
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
            h_dst = sha256_file(dst)
            ok = (h_dst == r["sha256_container"])
            if not ok:
                mismatch += 1
            copy_rows.append({"relpath": r["relpath"], "size_bytes": r["size_bytes"],
                              "src_sha256_container": r["sha256_container"],
                              "dst_sha256_container": h_dst, "identical": ok})
            copied += 1

        # 独立核验器（零依赖，可拷到任意机器运行）
        (ver_dir / "VERIFY_BASELINE_MANIFEST.py").write_text(VERIFIER_SRC, encoding="utf-8")

        with open(ver_dir / "COPY_VERIFICATION.csv", "w", newline="", encoding="utf-8-sig") as f:
            w = csv.DictWriter(f, fieldnames=["relpath", "size_bytes", "src_sha256_container",
                                              "dst_sha256_container", "identical"])
            w.writeheader()
            for c in copy_rows:
                w.writerow(c)

        ext_info = {"enabled": True, "root": str(ext_base), "version_dir": str(ver_dir),
                    "chosen_existed_before": chosen_existed_before,
                    "n_copied": copied, "n_mismatch": mismatch,
                    "bytes_copied": sum(c["size_bytes"] for c in copy_rows),
                    "preexisting_versions": existed,
                    "manifest_copy": str(man_dir), "verifier": str(ver_dir / "VERIFY_BASELINE_MANIFEST.py"),
                    "manifest_sha256sums": str(man_dir / "SHA256SUMS.txt")}
        print(f"\n外部副本：{ver_dir}  ({copied} 文件, {ext_info['bytes_copied']/2**30:.2f} GiB)")
        print(f"  既有版本（未被覆盖）：{existed or '（无）'}")

    print("\n" + "-" * 108)
    if not args.no_copy:
        gate("M13", "外部副本逐文件容器 sha256 == 源（源→副本 忠实性）",
             ext_info.get("n_mismatch") == 0,
             f"copied={ext_info.get('n_copied')} mismatch={ext_info.get('n_mismatch')}")
        gate("M14", "外部副本未覆盖既有版本（本次版本目录在写入前不存在）",
             not ext_info.get("chosen_existed_before", True),
             f"既有={ext_info.get('preexisting_versions') or '（无）'} 本次={Path(ext_info['version_dir']).name}")
        gate("M15", "外部副本含零依赖独立核验器",
             Path(ext_info["verifier"]).exists(),
             f"verifier={Path(ext_info['verifier']).name}")

    meta["external_copy"] = ext_info
    meta["summary"]["n_gates"] = len(GATES)
    meta["summary"]["n_gates_pass"] = sum(1 for g in GATES if g["pass"])
    meta["summary"]["verdict"] = (
        "BASELINE_MANIFEST_SEALED" if (n_missing == 0 and
                                       all(g["pass"] for g in GATES)) else
        "BASELINE_MANIFEST_INCOMPLETE_OR_GATE_FAILED")
    meta["elapsed_sec"] = round(time.time() - t0, 1)

    json_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

    # ---------------- 5. 人读版 MD
    L = []
    L.append("# 基线 SHA-256 清单 — %s\n" % STAMP)
    L.append("> **判决**：`%s` ｜ 门禁 **%d/%d PASS** ｜ 条目 **%d** ｜ 总计 **%.2f GiB** ｜ 缺失 **%d**\n"
             % (meta["summary"]["verdict"], meta["summary"]["n_gates_pass"],
                meta["summary"]["n_gates"], len(rows),
                meta["summary"]["total_gib"], n_missing))
    L.append("> 生成器 `%s`（自登记，可检出日后改动）｜ 生成于 %s ｜ 用时 %.1f s\n"
             % (meta["generator"], meta["built"], meta["elapsed_sec"]))
    L.append("> **目的**：回答「今天用来支撑这些结论的文件，是否就是当时真正生成和复核过的那一批文件」。\n")
    L.append("## 哈希口径（★勿混用）\n")
    L.append("| 字段 | 含义 | 用途 |\n|---|---|---|")
    L.append("| `sha256_container` | 文件字节本身 | 同一性 / 防篡改（容器相同 ⟺ 文件完全相同） |")
    L.append("| `sha256_content` | gz **解压内容** | 跨运行**可比性**（同内容可能容器字节不同） |")
    L.append("\n> 超过 %.0f MB 的 gz 只登记容器哈希并显式标注（事件文件 ~1.7 GB/个，解压约 14.7 GB）。\n"
             % (CONTENT_HASH_MAX / 2**20))
    L.append("## 门禁\n")
    L.append("| ID | 判据 | 结果 | 实测 |\n|---|---|---|---|")
    for g in GATES:
        L.append("| `%s` | %s | **%s** | %s |" % (g["id"], g["gate"], "PASS" if g["pass"] else "FAIL", g["detail"]))
    L.append("\n## 登记条目（按组）\n")
    for gk in (GA, GB, GC, GD, GE, GF, GG):
        sub = [r for r in rows if r["group"] == gk]
        if not sub:
            continue
        L.append("### %s\n" % sub[0]["group_label"])
        L.append("| 相对路径 | 字节 | sha256(容器) | sha256(内容) | 证据角色 |\n|---|---|---|---|---|")
        for r in sub:
            ct = (r["sha256_container"] or "—")[:16] + "…" if r["sha256_container"] else "**MISSING**"
            co = ((r["sha256_content"] or "")[:16] + "…") if r["sha256_content"] else (
                "（>阈值，仅容器）" if r.get("content_note") else "—")
            L.append("| `%s` | %s | `%s` | `%s` | %s |"
                     % (r["relpath"], f"{r['size_bytes']:,}" if r["size_bytes"] else "—",
                        ct, co, r["role"]))
        L.append("")
    L.append("## 显式排除（避免「清单像全量」的错觉）\n")
    L.append("| 对象 | 理由 |\n|---|---|")
    for p, rsn in EXCLUDED:
        L.append("| `%s` | %s |" % (p, rsn))
    L.append("\n## 外部副本（项目工作目录之外，只增不改）\n")
    if ext_info.get("enabled"):
        L.append("| 项 | 值 |\n|---|---|")
        L.append("| 版本目录 | `%s` |" % ext_info["version_dir"])
        L.append("| 文件数 / 体积 | %d / %.2f GiB |" % (ext_info["n_copied"], ext_info["bytes_copied"] / 2**30))
        L.append("| 源→副本 哈希不一致 | **%d** |" % ext_info["n_mismatch"])
        L.append("| 本次之前已存在的版本（未被覆盖） | %s |" % (ext_info["preexisting_versions"] or "（无）"))
        L.append("| 清单副本 / 校验和边车 | `manifest/` + `manifest/SHA256SUMS.txt` |")
        L.append("| 独立核验器 | `%s`（零依赖） |" % Path(ext_info["verifier"]).name)
        L.append("\n核验命令：\n")
        L.append("```bash\npython \"%s\"            # 核验外部副本\npython \"%s\" --root \"%s\"  # 核验项目内原件\n```\n"
                 % (ext_info["verifier"], ext_info["verifier"], PROJECT))
    else:
        L.append("（本次以 `--no-copy` 运行，未创建外部副本。）\n")
    L.append("## 只增不改规则\n")
    L.append("- 项目内清单：目标文件已存在 ⇒ 自动落为 `…__v2/__v3/…`，⛔ 不覆盖。\n")
    L.append("- 外部副本：`%s/<戳记>` 已存在 ⇒ 自动落为 `<戳记>__v2/…`，⛔ 不覆盖。\n" % EXT_BASE)
    L.append("- 任何后续变更**新增版本**；已冻结副本**原样保留**，作为「当时那一批文件」的锚。\n")
    md_path.write_text("\n".join(L), encoding="utf-8")

    # ---------------- 6. 清单副本 → 外部（清单**最后**生成；SHA256SUMS 边车不自哈希）
    if ext_info.get("enabled"):
        man_dir = Path(ext_info["manifest_copy"])
        man_dir.mkdir(parents=True, exist_ok=True)
        for p in (json_path, csv_path, md_path):
            shutil.copy2(p, man_dir / p.name)
        with open(man_dir / "SHA256SUMS.txt", "w", encoding="utf-8") as f:
            for p in (json_path, csv_path, md_path):
                f.write("%s  %s\n" % (sha256_file(man_dir / p.name), p.name))
        ext_info["manifest_sha256sums"] = str(man_dir / "SHA256SUMS.txt")
        print("清单副本 + 校验和边车已写入：%s" % man_dir)

    print(f"\n清单已落盘：\n  {json_path}\n  {csv_path}\n  {md_path}")
    print(f"\n[判决] {meta['summary']['verdict']}  （门禁 {meta['summary']['n_gates_pass']}/{meta['summary']['n_gates']} PASS，"
          f"条目 {len(rows)}，{meta['summary']['total_gib']} GiB，用时 {meta['elapsed_sec']} s）")
    return 0 if meta["summary"]["n_gates_pass"] == meta["summary"]["n_gates"] else 3


VERIFIER_SRC = '''# -*- coding: utf-8 -*-
"""基线清单独立核验器（零依赖，可拷贝到任意机器运行）

用法：
  python VERIFY_BASELINE_MANIFEST.py                 # 核验本目录下 files/ 副本
  python VERIFY_BASELINE_MANIFEST.py --root <项目根>  # 核验项目内原件

判据：逐文件重算 sha256(容器) 与清单登记值比对；gz 且清单含 content 哈希者，
      再重算解压内容哈希比对。任意不一致即 FAIL。
"""
import argparse, csv, gzip, hashlib, json, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def sha256_file(p, chunk=1 << 20):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for c in iter(lambda: f.read(chunk), b""):
            h.update(c)
    return h.hexdigest()


def sha256_gz(p, chunk=1 << 20):
    h = hashlib.sha256()
    with gzip.open(p, "rb") as f:
        for c in iter(lambda: f.read(chunk), b""):
            h.update(c)
    return h.hexdigest()


def resolve_manifest(root):
    """未显式指定清单时，自动发现**编号最大**的清单（版本号不写死，避免改版后失效）。"""
    cands = []
    if (HERE / "manifest").is_dir():
        cands += list((HERE / "manifest").glob("BASELINE_MANIFEST_*.json"))
    if root:
        pb = Path(root) / "reports" / "project_baseline"
        if pb.is_dir():
            cands += list(pb.glob("BASELINE_MANIFEST_*.json"))
    cands = sorted(c for c in cands if c.is_file())
    return cands[-1] if cands else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=None, help="项目根（缺省则核验本目录 files/）")
    ap.add_argument("--manifest", default=None, help="清单路径（缺省则自动发现编号最大者）")
    a = ap.parse_args()
    mp = Path(a.manifest) if a.manifest else resolve_manifest(a.root)
    if mp is None or not mp.is_file():
        print("找不到清单：请用 --manifest 显式指定。")
        return 2
    a.manifest = str(mp)
    man = json.loads(mp.read_text(encoding="utf-8"))
    base = Path(a.root) if a.root else (HERE / "files")
    mode = "项目内原件" if a.root else "外部副本 files/"
    ok = bad = miss = 0
    details = []
    for e in man["entries"]:
        p = base / e["relpath"]
        if not p.exists():
            miss += 1; details.append(("MISSING", e["relpath"], "", "")); continue
        ct = sha256_file(p)
        if ct != e["sha256_container"]:
            bad += 1; details.append(("CONTAINER_DIFF", e["relpath"], ct[:16], (e["sha256_container"] or "")[:16])); continue
        if e.get("sha256_content"):
            co = sha256_gz(p)
            if co != e["sha256_content"]:
                bad += 1; details.append(("CONTENT_DIFF", e["relpath"], co[:16], e["sha256_content"][:16])); continue
        ok += 1
    print("=" * 90)
    print("基线清单核验 ｜ 模式：%s ｜ 基准目录：%s" % (mode, base))
    print("  清单：%s（生成于 %s）" % (a.manifest, man["built"]))
    print("-" * 90)
    for st, rp, g, x in details:
        print("  [%s] %s  got=%s exp=%s" % (st, rp, g, x))
    print("-" * 90)
    print("  VERIFIED=%d  MISMATCH=%d  MISSING=%d  共 %d" % (ok, bad, miss, len(man["entries"])))
    verdict = "ALL_FILES_MATCH_THE_SEALED_SET" if (bad == 0 and miss == 0) else "BASELINE_DRIFT_DETECTED"
    print("  [判决] %s" % verdict)
    return 0 if verdict == "ALL_FILES_MATCH_THE_SEALED_SET" else 3


if __name__ == "__main__":
    sys.exit(main())
'''

if __name__ == "__main__":
    sys.exit(main())
