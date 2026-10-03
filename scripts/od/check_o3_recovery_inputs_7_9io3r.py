# -*- coding: utf-8 -*-
"""check_o3_recovery_inputs_7_9io3r.py — O3-DATA-RECOVERY 输入自检（只读、零副作用）

用途：用户在本地重新下载「属性完整版」`DetectorLoop` / `RoadSectionLine` 后，
      **先跑本脚本自检**，确认字段与填充率再交给主引擎。

用法：
    python scripts/od/check_o3_recovery_inputs_7_9io3r.py

它会：
  1. 按 PREREG_7_9I_O3RECOVERY.md §3 的候选顺序找文件（声明路径优先）
  2. 打印 字段清单 / 记录数 / 关键字段填充率
  3. 与官方 schema（FGDC ∪ AddField）对比，给出「缺什么」
  4. 判断五个能力门 `M1a/M1b/M2/M3/M4` 的**当前可达状态**

⛔ 只读：不写任何文件、不改任何冻结件、不跑 MATSim。
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(r"D:\Luan\2026-05\2_Singapore")
sys.path.insert(0, str(ROOT / "scripts" / "od"))

from audit_o3_metadata_7_9io3m import _dbf_header  # noqa: E402
from audit_o3_recovery_7_9io3r import (  # noqa: E402
    GEO_BASE_DET, GEO_BASE_DET_XML, GEO_BASE_RSL, GEO_BASE_RSL_XML,
    MIN_FILL, M4_CLOSE_MIN, dbf_scan, official_schema, resolve_inputs, INPUT_SPECS,
)


def report(logical, xml, base_dbf):
    res = resolve_inputs()[0][logical]
    print("=" * 78)
    print("## %s" % logical)
    print("  声明路径（优先）:")
    for d in res["declared_paths"]:
        print("     %s   [exists=%s]" % (d, Path(d).exists()))
    if res["resolved_path"]:
        print("  ✅ 已找到: %s   (来源=%s)" % (res["resolved_path"], res["source"]))
    else:
        print("  ⛔ 未找到 —— 请把文件放到上面任一「声明路径」")
        return None

    path = Path(res["resolved_path"])
    fields, n, fill = dbf_scan(path)
    names = [f[0] for f in fields]
    fg, ad, uni = official_schema(xml)
    have = {x.upper() for x in names}
    missing = [x for x in uni if x.upper() not in have]
    print("  记录数 = %d ; 字段数 = %d" % (n, len(names)))
    print("  实际字段: %s" % names)
    print("  官方 schema（FGDC ∪ AddField = %d）: %s" % (len(uni), uni))
    print("  缺失官方字段: %s" % (missing or "∅ ✅"))
    key = [k for k in ("RD_CD", "RD_NAM", "JOB_NUM", "TYP_CD", "LVL_NUM",
                       "DETECTOR_ID", "LANE_NUM") if k in have]
    for k in key:
        v = fill.get(next(f[0] for f in fields if f[0].upper() == k), 0.0)
        flag = "✅" if v >= MIN_FILL else ("⚠ 近空（<%.0f%%）" % (MIN_FILL * 100))
        print("    %-12s 填充率 = %.6f   %s" % (k, v, flag))
    return dict(n=n, names=names, fill=fill, official=uni, missing=missing)


def main():
    print("== O3-DATA-RECOVERY 输入自检（只读） ==")
    print("常量：MIN_FILL=%.2f ; M4_CLOSE_MIN=%.2f" % (MIN_FILL, M4_CLOSE_MIN))
    det = report("DetectorLoop", GEO_BASE_DET_XML, GEO_BASE_DET)
    rsl = report("RoadSectionLine", GEO_BASE_RSL_XML, GEO_BASE_RSL)
    onr = resolve_inputs()[0]["OnRequestJunctionLoopCounts"]
    print("=" * 78)
    print("## OnRequestJunctionLoopCounts")
    print("  声明路径: %s" % onr["declared_paths"])
    print("  %s" % ("✅ 已找到: %s" % onr["resolved_path"] if onr["resolved_path"]
                    else "⛔ 未找到（第二优先，可后补）"))

    print("=" * 78)
    print("## 能力门预判（自检口径，与主引擎一致）")
    if rsl:
        rd = rsl["fill"].get("RD_CD", 0.0)
        print("  M1a: %s  (RoadSectionLine.RD_CD 填充率 %.6f %s %.2f)"
              % ("PRESENT" if rd >= MIN_FILL else "ABSENT", rd,
                 ">=" if rd >= MIN_FILL else "<", MIN_FILL))
    if det:
        did = det["fill"].get("DETECTOR_ID", 0.0)
        print("  M1b: %s  (DetectorLoop.DETECTOR_ID %s)"
              % ("PRESENT" if did > 0 else "ABSENT", "有填充" if did > 0 else "无/缺"))
    print("  M2 : %s" % ("EVALUABLE（需实测交集）"
                         if (det and rsl and "RD_CD" in det["names"] and "RD_CD" in rsl["names"])
                         else "BLOCKED（RD_CD 尚未双侧可用）"))
    print("  M3 : %s" % ("PRESENT" if (det and ("LANE_NUM" in det["names"])) else "ABSENT"))
    print("  M4 : 需主引擎按 F_LOW 9 节逐节判定")
    print()
    print("⇒ 自检通过后，运行主引擎：")
    print("   python scripts/od/audit_o3_recovery_7_9io3r.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
