#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""
esb05_build_config.py — E-SB-05 执行级 events 验证：由原 SB-A5 配置派生 EVT19 配置
=================================================================================
设计原则（对应任务书「只允许改变三个配置项」）

* 逐字节复制 `config_SB-A5.xml`，**只**对其中的 3 个 `<param>` 的 value 做定点替换；
  任何一处匹配数 != 1 立即抛错（不静默生成半成品配置）。
* 生成后用 **XML 参数解析器**（与 esb02_build_arms.all_params 同口径）重新读取两份
  配置，断言 diff 恰等于白名单 3 项。⇒ 「改了 3 项」是**被验证过的**，不是被声称的。
* 不覆盖原 SB-A5 配置；不写任何冻结件。

用法：
    python scripts/experiments/esb05_build_config.py
"""
from __future__ import annotations

import hashlib
import re
import sys
from pathlib import Path
import xml.etree.ElementTree as ET

ROOT = Path(r"D:\Luan\2026-05\2_Singapore")
SRC_CFG = ROOT / "experiments" / "E-SB-02_night_freeflow" / "configs" / "config_SB-A5.xml"
EXP = ROOT / "experiments" / "E-SB-05_exec_level_events"
OUT_CFG = EXP / "configs" / "config_SB-A5_EVT19_CHECK.xml"

RUN_ID = "SB-A5_EVT19_CHECK"
OUT_DIR = rf"D:\Luan\2026-05\2_Singapore\experiments\E-SB-05_exec_level_events\outputs\{RUN_ID}"
WRITE_EVENTS_INTERVAL = "19"

# ★白名单：除这 3 项外，任何参数差异都视为越权
WHITELIST = {"controller.outputDirectory", "controller.runId", "controller.writeEventsInterval"}

CHANGES = [
    ("controller.outputDirectory", OUT_DIR),
    ("controller.runId", RUN_ID),
    ("controller.writeEventsInterval", WRITE_EVENTS_INTERVAL),
]


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


def main() -> int:
    if not SRC_CFG.exists():
        print(f"[FATAL] 源配置不存在：{SRC_CFG}")
        return 2
    raw = SRC_CFG.read_bytes()
    if raw.startswith(b"\xef\xbb\xbf"):
        print("[FATAL] 源配置带 BOM，未预期。")
        return 2
    txt = raw.decode("utf-8")
    src_sha = hashlib.sha256(raw).hexdigest()

    print("=" * 84)
    print(f"E-SB-05 配置派生：{SRC_CFG.name}  ->  {OUT_CFG.name}")
    print("=" * 84)
    print(f"[IN ] 源配置 sha256 = {src_sha}")

    for key, value in CHANGES:
        name = key.split(".", 1)[1]
        pat = re.compile(r'(<param name="%s" value=")([^"]*)(" />)' % re.escape(name))
        hits = pat.findall(txt)
        if len(hits) != 1:
            print(f"[FATAL] 参数 {name} 在源配置中匹配 {len(hits)} 次（应为 1）")
            return 3
        old = hits[0][1]
        txt, n = pat.subn(lambda m: m.group(1) + value + m.group(3), txt)
        assert n == 1
        print(f"[SET] {key}\n        {old}\n     -> {value}")

    OUT_CFG.parent.mkdir(parents=True, exist_ok=True)
    OUT_CFG.write_bytes(txt.encode("utf-8"))
    out_sha = sha256_file(OUT_CFG)
    print(f"[OUT] 派生配置已写出 sha256 = {out_sha}")

    # ---- 断言：参数级 diff 恰等于白名单 ----
    a = all_params(SRC_CFG)
    b = all_params(OUT_CFG)
    diff = {k for k in set(a) | set(b) if a.get(k) != b.get(k)}
    print(f"[GATE] 参数 diff = {sorted(diff)}")
    ok = diff == WHITELIST
    print(f"[{'PASS' if ok else 'FAIL'}] 参数 diff == 白名单 3 项")
    if not ok:
        return 4

    # ---- 断言：字节级差异仅限这 3 个 value ----
    # 用占位把 3 个新 value 换回旧 value，应能与源文件逐字节相同
    # ⚠️ 必须 read_bytes().decode()，不可用 read_text()（会把 CRLF 归一化成 LF，制造假差异）
    back = OUT_CFG.read_bytes().decode("utf-8")
    for key, value in CHANGES:
        name = key.split(".", 1)[1]
        back = back.replace(f'<param name="{name}" value="{value}" />',
                            f'<param name="{name}" value="{a[key]}" />')
    same = back.encode("utf-8") == raw
    print(f"[{'PASS' if same else 'FAIL'}] 回填 3 项后与源配置逐字节相同（无其它改动）")
    if not same:
        return 5
    print("\n[OK] EVT19 配置生成完毕，等待运行前硬门。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
