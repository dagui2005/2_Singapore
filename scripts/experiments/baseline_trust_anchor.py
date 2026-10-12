# -*- coding: utf-8 -*-
"""基线封存的**独立信任锚**（E-SB-05 / E-SB-06 证据封存 · 第 2 层）

要回答的问题（用户原话）：
    「在封存目录之外保存 v3 清单自身的 SHA-256，并由独立位置核验外部副本。
      这样可以进一步区分两件事：
        (1) 文件是否与封存清单一致；                  ← 已有记录支持
        (2) 封存清单本身是否还是当时认可的那份清单。    ← 需要独立保存的校验值来加强」

本脚本只补**第 2 层**：给「清单自身」加一道独立锚。
  ⛔ 不改变 D5 的 FAIL；⛔ 不替代科学结论复核；⛔ 不重跑任何仿真；⛔ 不改动任何被登记文件。

信任链（自顶向下，单向无环 —— 见门禁 P13）：
    POINT_OF_TRUST.txt
      └─ sha256(ANCHOR_ROOT.txt)                    ← ★唯一需离线/异地记录的单值
         ANCHOR_ROOT.txt
           ├─ sha256(TRUST_ANCHOR.json)             （锚件内**不含** PT，以断环）
           ├─ sha256(TRUST_ANCHOR.md)
           ├─ sha256(VERIFY_TRUST_ANCHOR.py)
           ├─ sha256(PAYLOAD_ROLLUP.txt)
           ├─ sha256(ANCHOR_SHA256SUMS.txt)
           └─ manifest/ 三件 sha256                 ← 封存清单（json/csv/md）自身
                 PAYLOAD_ROLLUP.txt
                   └─ 92 行 (relpath, size, sha256_container)
                      ⇒ payload_root = sha256(本文件)（可手工复算）
                         manifest/*  → 92 个证据文件（逐文件容器 / 内容哈希）

哈希口径（与基线清单一致，★勿混用）：
  - sha256_container：文件字节本身 ⇒ 同一性 / 防篡改
  - sha256_content  ：gz 解压内容 ⇒ 跨运行可比性
  - 全部文本锚件以 `newline="\\n"` 写出（LF，无 CR 翻译）⇒ 任何平台复算得同一字节与同一哈希。

介质拓扑（本机探测：Get-Partition / Get-Disk，2026-10-12）：
    D: → disk 0  BG6 KIOXIA 512GB       (NVMe 内置)  ← 项目工作目录
    C: → disk 1  P41PL SOLIDGM 512GB    (NVMe 内置)  ← ★主锚点（与 D: / K: 均不同物理设备）
    K: → disk 2  Realtek RTL9210 NVME   (USB 外置)   ← 封存副本
    L: → disk 2  同上 —— **与 K: 同一物理介质**      ← 次锚点（仅可用性 / 交叉核验）
  ⚠️ 因此 L: **不提供介质级独立性**，已在锚件与报告中如实标注。

★边界（必须与结论同时传播）：
  单机环境下 PT 无法自证。PT 的离线/异地记录是**不可再约简的人工步骤**。
  本锚只证明「文件是那一批、清单是那一份」，**不提升也不降低任何门禁判定**（D5 仍 FAIL）。
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
import shutil
import sys
import time
from pathlib import Path

# ------------------------------------------------------------------ 常量
PROJECT = Path(r"D:\Luan\2026-05\2_Singapore")
SEALED_ROOT = Path(r"K:\_sg_matsim_baseline_freeze")
STAMP = "2026-10-12"

# 锚点位置：主锚点必须在**不同于封存副本**的物理介质上
ANCHOR_PRIMARY = Path(r"C:\Users\LQP\sg_baseline_trust_anchor")      # disk 1（独立于 D:/K:）
ANCHOR_SECONDARY = Path(r"L:\_sg_matsim_trust_anchor")               # disk 2（= K: 同一介质）

# 锚件（被 ANCHOR_ROOT.txt 覆盖者；⛔ 其中不含 PT 值，否则成环）
COVERED_ARTIFACTS = [
    "TRUST_ANCHOR.json", "TRUST_ANCHOR.md", "VERIFY_TRUST_ANCHOR.py",
    "PAYLOAD_ROLLUP.txt", "ANCHOR_SHA256SUMS.txt",
    "manifest/BASELINE_MANIFEST_%s.json", "manifest/BASELINE_MANIFEST_%s.csv",
    "manifest/BASELINE_MANIFEST_%s.md", "manifest/SHA256SUMS.txt",
]
UNCOVERED = ["POINT_OF_TRUST.txt", "ANCHOR_ROOT.txt"]

# 介质拓扑（探测结果，如实登记；非本脚本推导）
MEDIA_TOPOLOGY = [
    {"drive": "D:", "disk": 0, "model": "BG6 KIOXIA 512GB", "bus": "NVMe-internal",
     "role": "项目工作目录", "independent_of_sealed": True},
    {"drive": "C:", "disk": 1, "model": "P41PL NVMe SOLIDGM 512GB", "bus": "NVMe-internal",
     "role": "★主锚点", "independent_of_sealed": True},
    {"drive": "K:", "disk": 2, "model": "Realtek RTL9210 NVME", "bus": "USB-external",
     "role": "封存副本", "independent_of_sealed": False},
    {"drive": "L:", "disk": 2, "model": "Realtek RTL9210 NVME", "bus": "USB-external",
     "role": "次锚点（与 K: 同一物理介质）", "independent_of_sealed": False},
]

# 被锚定的「已认可判决」——连同其失败项一起锚定，⛔ 不得只锚成功项
APPROVED_JUDGEMENT = {
    "sealed_set": "BASELINE_MANIFEST_SEALED",
    "strict_protocol_verdict": "EXECUTION_LEVEL_PARTIAL",
    "core_exec_evidence": "D1-D4 成立（执行级路线证据）",
    "original_d5": "FAIL（原预注册判据：Top-2 应为 PIE+TPE，实际为 PIE+MCE）",
    "a5": "补充分析（独立报告，⛔ 不替代 D5）",
    "v1_1_promotion": "不晋升（Sim/Obs = 1.0600691 > 1.05）",
    "esb06": "不启动（SIGNAL_CONTROL_NOT_FEASIBLE__DATA_AND_IMPLEMENTATION_GAP）",
}


# ------------------------------------------------------------------ 工具
def sha256_file(p: Path, chunk: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for c in iter(lambda: f.read(chunk), b""):
            h.update(c)
    return h.hexdigest()


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def sha256_gz(p: Path, chunk: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with gzip.open(p, "rb") as f:
        for c in iter(lambda: f.read(chunk), b""):
            h.update(c)
    return h.hexdigest()


def wtext(p: Path, s: str):
    """★定死 LF：任何平台复算得同一字节 ⇒ 同一哈希（可手工 sha256sum 复核）"""
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w", encoding="utf-8", newline="\n") as f:
        f.write(s)


def next_free(path: Path) -> Path:
    """★只增不改：目标已存在 ⇒ `__v2/__v3/…`，绝不覆盖既有版本。"""
    if not path.exists():
        return path
    k = 2
    while True:
        cand = path.with_name("%s__v%d%s" % (path.stem, k, path.suffix))
        if not cand.exists():
            return cand
        k += 1


def is_within(child: Path, parent: Path) -> bool:
    try:
        Path(os.path.abspath(str(child))).relative_to(Path(os.path.abspath(str(parent))))
        return True
    except ValueError:
        return False


def resolve_sealed_dir() -> Path:
    """自动发现封存根下**编号最大**的版本目录（版本号不写死）。"""
    import re
    cands = []
    for d in SEALED_ROOT.iterdir():
        if d.is_dir() and d.name.startswith(STAMP):
            m = re.match(r"%s(?:__v(\d+))?$" % re.escape(STAMP), d.name)
            if m:
                cands.append((int(m.group(1) or 1), d))
    if not cands:
        raise SystemExit("封存根下找不到 %s 的版本目录：%s" % (STAMP, SEALED_ROOT))
    return max(cands, key=lambda x: x[0])[1]


def resolve_manifest() -> Path:
    """自动发现项目内**编号最大**的封存清单。"""
    import re
    pb = PROJECT / "reports" / "project_baseline"
    cands = []
    for p in pb.glob("BASELINE_MANIFEST_%s*.json" % STAMP):
        m = re.search(r"__v(\d+)\.json$", p.name)
        cands.append((int(m.group(1)) if m else 1, p))
    if not cands:
        raise SystemExit("找不到封存清单：%s" % pb)
    return max(cands, key=lambda x: x[0])[1]


GATES = []


def gate(gid, desc, ok, detail):
    GATES.append({"id": gid, "gate": desc, "pass": bool(ok), "detail": detail})
    print(f"[{'PASS' if ok else 'FAIL'}] {gid:<5} {desc}  | {detail}")


# ------------------------------------------------------------------ 零依赖核验器（写进锚点包）
VERIFIER_SRC = r'''# -*- coding: utf-8 -*-
"""信任锚独立核验器（零依赖 · 可拷到任意机器/介质运行）

用法：
  python VERIFY_TRUST_ANCHOR.py                          # 只核验锚点包自洽（秒级）
  python VERIFY_TRUST_ANCHOR.py --expect <PT>            # 再比对离线记录的点信任值
  python VERIFY_TRUST_ANCHOR.py --payload <目录>          # 用锚内清单核验某副本（重算 92 件哈希）

判据：
  1) sha256(ANCHOR_ROOT.txt) == POINT_OF_TRUST.txt 记录值（可再用 --expect 比对离线记录）
  2) ANCHOR_ROOT.txt 所列各锚件哈希 == 实测
  3) payload_root == sha256(PAYLOAD_ROLLUP.txt)；卷宗行数 == 清单条目数
  4) 清单自身三件 sha256 == ANCHOR_ROOT.txt 记录（(2) 已含），并 == 项目侧同件
  5) 若给 --payload：F_ 组逐文件容器（+内容）哈希比对
"""
import argparse, gzip, hashlib, json, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def sh_file(p, chunk=1 << 20):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for c in iter(lambda: f.read(chunk), b""):
            h.update(c)
    return h.hexdigest()


def sh_gz(p, chunk=1 << 20):
    h = hashlib.sha256()
    with gzip.open(p, "rb") as f:
        for c in iter(lambda: f.read(chunk), b""):
            h.update(c)
    return h.hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--expect", default=None, help="离线记录的点信任值（sha256 of ANCHOR_ROOT.txt）")
    ap.add_argument("--payload", default=None, help="待核验副本目录（如 K:\\...\\<ver>\\files）")
    a = ap.parse_args()
    bad = 0

    root_txt = HERE / "ANCHOR_ROOT.txt"
    pot = HERE / "POINT_OF_TRUST.txt"
    if not root_txt.is_file() or not pot.is_file():
        print("锚点包不完整：缺 ANCHOR_ROOT.txt 或 POINT_OF_TRUST.txt")
        return 2

    pt_calc = sh_file(root_txt)
    pt_rec = None
    for line in pot.read_text(encoding="utf-8").splitlines():
        if line.startswith("point_of_trust_sha256"):
            pt_rec = line.split("=", 1)[1].strip()
    print("=" * 92)
    print("信任锚核验 ｜ 锚点包 %s" % HERE)
    print("-" * 92)
    ok = (pt_rec == pt_calc)
    bad += 0 if ok else 1
    print("  [%s] PT 复算          calc=%s rec=%s" % ("OK" if ok else "BAD", pt_calc[:24], (pt_rec or "")[:24]))
    if a.expect:
        ok = (a.expect.strip() == pt_calc)
        bad += 0 if ok else 1
        print("  [%s] PT 对离线记录    expect=%s" % ("OK" if ok else "BAD", a.expect.strip()[:24]))

    # ANCHOR_ROOT.txt -> 结构化键值
    rec = {}
    for line in root_txt.read_text(encoding="utf-8").splitlines():
        if " = " in line and not line.startswith(" "):
            k, v = line.split(" = ", 1)
            rec[k.strip()] = v.strip()

    for key, rel in [(k, k) for k in sorted(rec) if k.endswith((".json", ".md", ".py", ".txt"))]:
        p = HERE / key
        if not p.is_file():
            print("  [BAD] 锚件缺失        %s" % key); bad += 1; continue
        got = sh_file(p)
        ok = (got == rec[key])
        bad += 0 if ok else 1
        print("  [%s] 锚件 %-46s got=%s exp=%s" % ("OK" if ok else "BAD", key, got[:16], rec[key][:16]))

    # payload_root
    roll = HERE / "PAYLOAD_ROLLUP.txt"
    if roll.is_file():
        pr = sh_file(roll)
        ok = (rec.get("payload_root") == pr)
        bad += 0 if ok else 1
        n = len(roll.read_text(encoding="utf-8").rstrip("\n").splitlines())
        print("  [%s] payload_root     calc=%s rec=%s  (行数 %d / 期望 %s)"
              % ("OK" if ok else "BAD", pr[:24], (rec.get("payload_root") or "")[:24], n, rec.get("n_entries")))

    # 可选：核验某个副本
    if a.payload:
        man = json.loads((HERE / "manifest" / ("BASELINE_MANIFEST_%s.json" % rec.get("stamp", ""))).read_text(encoding="utf-8")) \
            if (HERE / "manifest").is_dir() else None
        if man is None:
            cands = sorted((HERE / "manifest").glob("BASELINE_MANIFEST_*.json"))
            man = json.loads(cands[-1].read_text(encoding="utf-8"))
        base = Path(a.payload)
        nok = nbad = nmiss = 0
        for e in man["entries"]:
            p = base / e["relpath"]
            if not p.exists():
                nmiss += 1; print("  [MISSING] %s" % e["relpath"]); continue
            if sh_file(p) != e["sha256_container"]:
                nbad += 1; print("  [CONTAINER_DIFF] %s" % e["relpath"]); continue
            if e.get("sha256_content") and sh_gz(p) != e["sha256_content"]:
                nbad += 1; print("  [CONTENT_DIFF] %s" % e["relpath"]); continue
            nok += 1
        print("-" * 92)
        print("  载荷核验 %s：VERIFIED=%d MISMATCH=%d MISSING=%d 共 %d"
              % (base, nok, nbad, nmiss, len(man["entries"])))
        bad += nbad + nmiss

    print("-" * 92)
    print("  [判决] %s  (bad=%d)" % ("TRUST_ANCHOR_INTACT" if bad == 0 else "TRUST_ANCHOR_BROKEN", bad))
    return 0 if bad == 0 else 3


if __name__ == "__main__":
    sys.exit(main())
'''


# ------------------------------------------------------------------ 主流程
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-copy", action="store_true", help="只在主锚点生成，不做第二位置")
    ap.add_argument("--skip-payload", action="store_true", help="跳过外部副本载荷核验（省时）")
    args = ap.parse_args()

    t0 = time.time()
    print("=" * 112)
    print(f"基线封存 · 独立信任锚生成 ｜ 项目根 {PROJECT} ｜ 戳记 {STAMP}")
    print("=" * 112)

    sealed_dir = resolve_sealed_dir()
    manifest_path = resolve_manifest()
    man = json.loads(manifest_path.read_text(encoding="utf-8"))
    entries = man["entries"]
    n_entries = len(entries)
    payload_root_declared = man.get("summary", {})
    print(f"封存版本目录：{sealed_dir}")
    print(f"封存清单    ：{manifest_path.name}（built={man.get('built')}）")
    print(f"清单条目    ：{n_entries} ｜ 判决 {man['summary']['verdict']} "
          f"｜ 门禁 {man['summary']['n_gates_pass']}/{man['summary']['n_gates']}")

    # ---------------- 1. 载荷卷宗（payload_root 的可复算载体）
    roll_lines = ["%s\t%s\t%s" % (e["relpath"], e["size_bytes"], e["sha256_container"])
                  for e in sorted(entries, key=lambda x: x["relpath"])]
    roll_text = "\n".join(roll_lines) + "\n"
    payload_root = sha256_bytes(roll_text.encode("utf-8"))

    # ---------------- 2. 主锚点：先写**暂存区**，全部门禁通过后才发布
    #    ★「发布」动作本身即判决：版本目录存在 ⟺ 该次锚点门禁全通过
    #      ⇒ 失败的尝试不会留下一个看似有效的版本目录（避免污染版本序列）
    ANCHOR_PRIMARY.mkdir(parents=True, exist_ok=True)
    _cand = ANCHOR_PRIMARY / STAMP
    final_name = next_free(_cand).name        # ★名称在写入前即确定，避免与 anchor_version 成环
    preexisting = sorted(p.name for p in ANCHOR_PRIMARY.iterdir()
                         if p.is_dir() and p.name.startswith(STAMP)
                         and not p.name.startswith(".staging"))
    supersedes = []
    for d in preexisting:
        pp = ANCHOR_PRIMARY / d / "POINT_OF_TRUST.txt"
        h = None
        if pp.is_file():
            for line in pp.read_text(encoding="utf-8", errors="ignore").splitlines():
                if line.startswith("point_of_trust_sha256"):
                    h = line.split("=", 1)[1].strip()
        supersedes.append({"version_dir": d, "point_of_trust": h})
    adir = ANCHOR_PRIMARY / (".staging_%s" % STAMP)
    if adir.exists():
        shutil.rmtree(adir, ignore_errors=True)
    adir.mkdir(parents=True, exist_ok=False)
    print(f"前序锚点版本（原样保留，只增不改）：{preexisting or '（无）'}")
    print(f"本次拟发布版本：{final_name}")
    man_dir = adir / "manifest"
    man_dir.mkdir(parents=True, exist_ok=True)
    print(f"\n主锚点目录  ：{adir}")

    # 2a. 封存清单副本（三件）+ 边车（不自哈希）
    for p in (PROJECT / "reports" / "project_baseline" / manifest_path.name,
              PROJECT / "reports" / "project_baseline" / manifest_path.with_suffix(".csv").name,
              PROJECT / "reports" / "project_baseline" / manifest_path.with_suffix(".md").name):
        if p.is_file():
            shutil.copy2(p, man_dir / p.name)
    man_names = sorted(p.name for p in man_dir.glob("BASELINE_MANIFEST_*") if p.is_file())
    wtext(man_dir / "SHA256SUMS.txt",
          "".join("%s  %s\n" % (sha256_file(man_dir / n), n) for n in man_names))

    # 2b. 载荷卷宗 + 核验器
    wtext(adir / "PAYLOAD_ROLLUP.txt", roll_text)
    wtext(adir / "VERIFY_TRUST_ANCHOR.py", VERIFIER_SRC)

    # 清单自身哈希（项目侧 vs 锚点副本侧，三方一致由 P04 判）
    man_hashes = {("manifest/" + n): sha256_file(man_dir / n) for n in man_names}
    man_side_project = {}
    for n in man_names:
        pp = PROJECT / "reports" / "project_baseline" / n
        man_side_project[n] = sha256_file(pp) if pp.is_file() else None

    # ---------------- 3. 人读 / 机读锚件（★不含 PT，断环）
    anchor_meta = {
        "built": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "stamp": STAMP,
        "purpose": "给「封存清单自身」加一道独立锚：区分「文件≡清单」与「清单≡当时认可的那份」",
        "project_root": str(PROJECT),
        "sealed_version_dir": str(sealed_dir),
        "sealed_manifest_project": str(manifest_path),
        "sealed_manifest_sha256_project": {n: man_side_project[n] for n in man_names},
        "sealed_manifest_sha256_anchor_copy": man_hashes,
        "sealed_manifest_summary": man.get("summary"),
        "anchor_version": final_name,
        "supersedes_anchor_versions": supersedes,
        "approved_judgement": APPROVED_JUDGEMENT,
        "n_entries": n_entries,
        "payload_root": payload_root,
        "payload_root_recipe": "sha256(PAYLOAD_ROLLUP.txt) ；卷宗 = 92 行 `relpath\\tsize_bytes\\tsha256_container`，按 relpath 升序，LF 行尾，末尾单个换行",
        "chain": {
            "POINT_OF_TRUST.txt": "sha256(ANCHOR_ROOT.txt)  ← ★唯一需离线/异地记录的单值",
            "ANCHOR_ROOT.txt": "覆盖全部锚件哈希 + payload_root（不含 PT，避免成环）",
            "PAYLOAD_ROLLUP.txt": "→ payload_root → manifest/* → 92 个证据文件",
        },
        "media_topology": MEDIA_TOPOLOGY,
        "boundary": ("单机环境 PT 无法自证：其离线/异地记录是不可再约简的人工步骤。"
                     "本锚只证明「文件是那一批、清单是那一份」，不提升也不降低任何门禁判定（D5 仍 FAIL）。"),
    }

    md = []
    md.append("# 基线封存 · 独立信任锚 — %s\n" % STAMP)
    md.append("> 目的：区分两件事 —— **(1)** 文件是否与封存清单一致；**(2)** 封存清单本身是否还是当时认可的那份。\n")
    md.append("> 本锚只补 (2)。⛔ 不改变 D5 的 FAIL，⛔ 不替代科学结论复核。\n")
    md.append("## 信任链（单向无环）\n")
    md.append("```")
    md.append("POINT_OF_TRUST.txt  = sha256(ANCHOR_ROOT.txt)      ← ★唯一需离线记录的单值")
    md.append("  ANCHOR_ROOT.txt   = 各锚件哈希 + payload_root + 门禁/判决（不含 PT）")
    md.append("    PAYLOAD_ROLLUP.txt = 92 行 relpath\\tsize\\tsha256_container")
    md.append("      payload_root  = sha256(PAYLOAD_ROLLUP.txt)")
    md.append("        manifest/*  → 92 个证据文件（逐文件容器/内容哈希）")
    md.append("```\n")
    md.append("## 关键值\n")
    md.append("| 项 | 值 |\n|---|---|")
    md.append("| 封存版本目录 | `%s` |" % sealed_dir)
    md.append("| 封存清单 | `%s` |" % manifest_path.name)
    md.append("| 清单判决 / 门禁 | **%s** / %d-%d |" % (man["summary"]["verdict"],
                                                    man["summary"]["n_gates_pass"], man["summary"]["n_gates"]))
    md.append("| 条目 / 体积 | %d / %.2f GiB |" % (n_entries, man["summary"]["total_gib"]))
    md.append("| **payload_root** | `%s` |" % payload_root)
    md.append("\n### 清单自身 SHA-256（本项目侧 == 锚点副本侧）\n")
    md.append("| 文件 | sha256 |\n|---|---|")
    for n in man_names:
        md.append("| `%s` | `%s` |" % (n, man_side_project.get(n) or "**MISSING**"))
    md.append("\n## 已认可的判决（连同失败项一起锚定）\n")
    md.append("| 项 | 值 |\n|---|---|")
    for k, v in APPROVED_JUDGEMENT.items():
        md.append("| `%s` | %s |" % (k, v))
    md.append("\n## 介质拓扑（本机探测，2026-10-12）\n")
    md.append("| 盘符 | 物理盘 | 型号 | 总线 | 角色 | 与封存副本独立 |\n|---|---|---|---|---|---|")
    for m in MEDIA_TOPOLOGY:
        md.append("| `%s` | disk %d | %s | %s | %s | %s |"
                  % (m["drive"], m["disk"], m["model"], m["bus"], m["role"],
                     "✔" if m["independent_of_sealed"] else "✘"))
    md.append("\n> ⚠️ `L:` 与 `K:` 位于**同一物理盘**（disk 2，USB）⇒ 次锚点**不提供介质级独立性**，"
              "仅用于可用性与「两份锚点是否仍一致」的交叉核验。\n")
    md.append("## 边界（必须与结论同时传播）\n")
    md.append("- 单机环境下 PT 无法自证；**PT 的离线/异地记录是不可再约简的人工步骤**。\n")
    md.append("- 本锚只回答「是不是那一批文件、那一份清单」，**不回答「结论对不对」**。\n")
    md.append("- ⛔ 不提升、不降低任何门禁判定：**原始 D5 仍为 FAIL**。\n")
    wtext(adir / "TRUST_ANCHOR.md", "\n".join(md))

    wtext(adir / "TRUST_ANCHOR.json", json.dumps(anchor_meta, ensure_ascii=False, indent=2) + "\n")

    # ---------------- 4. ANCHOR_SHA256SUMS.txt（覆盖 json/md/verifier/rollup/manifest/*）
    sums_targets = ["TRUST_ANCHOR.json", "TRUST_ANCHOR.md", "VERIFY_TRUST_ANCHOR.py",
                    "PAYLOAD_ROLLUP.txt"] + sorted(man_hashes)
    wtext(adir / "ANCHOR_SHA256SUMS.txt",
          "".join("%s  %s\n" % (sha256_file(adir / r), r) for r in sums_targets))

    # ---------------- 5. ANCHOR_ROOT.txt（覆盖 ANCHOR_SHA256SUMS + 其余锚件 + payload_root）
    root_hashes = {}
    for r in ["TRUST_ANCHOR.json", "TRUST_ANCHOR.md", "VERIFY_TRUST_ANCHOR.py",
              "PAYLOAD_ROLLUP.txt", "ANCHOR_SHA256SUMS.txt"] + sorted(man_hashes):
        root_hashes[r] = sha256_file(adir / r)
    L = []
    L.append("# ANCHOR_ROOT — %s" % STAMP)
    L.append("stamp = %s" % STAMP)
    L.append("anchor_version = %s" % final_name)
    L.append("supersedes_anchor_versions = %s"
             % (",".join(d["version_dir"] for d in supersedes) or "NONE"))
    L.append("built = %s" % anchor_meta["built"])
    L.append("sealed_version_dir = %s" % sealed_dir)
    L.append("sealed_manifest = %s" % manifest_path.name)
    L.append("sealed_verdict = %s" % man["summary"]["verdict"])
    L.append("sealed_gates = %d/%d" % (man["summary"]["n_gates_pass"], man["summary"]["n_gates"]))
    L.append("n_entries = %d" % n_entries)
    L.append("total_gib = %s" % man["summary"]["total_gib"])
    L.append("payload_root = %s" % payload_root)
    L.append("original_d5 = FAIL")
    L.append("strict_protocol_verdict = EXECUTION_LEVEL_PARTIAL")
    L.append("")
    L.append("# 各锚件 sha256（本文件不覆盖自身与 POINT_OF_TRUST.txt）")
    for r in sorted(root_hashes):
        L.append("%s = %s" % (r, root_hashes[r]))
    wtext(adir / "ANCHOR_ROOT.txt", "\n".join(L) + "\n")

    # ---------------- 6. POINT_OF_TRUST.txt（★唯一需离线记录的单值）
    pt = sha256_file(adir / "ANCHOR_ROOT.txt")
    pot = (
        "# POINT_OF_TRUST — %s\n"
        "# ★把下面这一个值**离线/异地**记录下来（手抄、自寄邮件、另一台机器均可）。\n"
        "# 它不从属于本机任何一份副本，因此是整条链唯一不可自证、也不可被本机篡改抹平的一环。\n"
        "point_of_trust_sha256 = %s\n"
        "subject = sha256(ANCHOR_ROOT.txt)\n"
        "reproduce = python -c \"import hashlib,sys;print(hashlib.sha256(open(sys.argv[1],'rb').read()).hexdigest())\" ANCHOR_ROOT.txt\n"
        "anchors_below = TRUST_ANCHOR.json / TRUST_ANCHOR.md / VERIFY_TRUST_ANCHOR.py / "
        "PAYLOAD_ROLLUP.txt / ANCHOR_SHA256SUMS.txt / manifest/*\n"
        "boundary = 只证明「文件是那一批、清单是那一份」；⛔ 不改变 D5 的 FAIL，⛔ 不替代科学结论复核。\n"
        % (STAMP, pt)
    )
    wtext(adir / "POINT_OF_TRUST.txt", pot)
    print(f"锚点包已生成：{adir}")
    print(f"  ★POINT_OF_TRUST = {pt}")

    # ---------------- 7. 门禁
    print("\n" + "-" * 112)

    # P00 位置独立性
    locs = [ANCHOR_PRIMARY] + ([] if args.no_copy else [ANCHOR_SECONDARY])
    proj_reports = PROJECT / "reports" / "project_baseline"
    inside = [str(x) for x in locs if is_within(x, SEALED_ROOT)]
    same_as_proj = [str(x) for x in locs if is_within(x, proj_reports)]
    gate("P00", "锚点位置 ≥1 且全部在封存根之外、不在项目 reports 目录内（位置独立）",
         len(locs) >= 1 and not inside and not same_as_proj,
         f"locs={[str(x) for x in locs]} inside_sealed={inside} inside_reports={same_as_proj}")

    # P01 锚件齐全
    need = (["ANCHOR_ROOT.txt", "POINT_OF_TRUST.txt", "TRUST_ANCHOR.json", "TRUST_ANCHOR.md",
             "VERIFY_TRUST_ANCHOR.py", "PAYLOAD_ROLLUP.txt", "ANCHOR_SHA256SUMS.txt"] +
            ["manifest/" + n for n in man_names] + ["manifest/SHA256SUMS.txt"])
    miss = [r for r in need if not (adir / r).is_file() or (adir / r).stat().st_size == 0]
    gate("P01", "锚点包完整（必需锚件齐全且非零字节）", not miss, f"n={len(need)} missing={miss}")

    # P02 卷宗行数
    n_roll = len(roll_text.rstrip("\n").splitlines())
    gate("P02", "载荷卷宗行数 == 清单条目数（卷宗未漏项）", n_roll == n_entries,
         f"roll={n_roll} entries={n_entries}")

    # P03 payload_root 可复算
    pr_recalc = sha256_file(adir / "PAYLOAD_ROLLUP.txt")
    gate("P03", "payload_root 由卷宗文件重算 == 记录值（可手工复核）", pr_recalc == payload_root,
         f"calc={pr_recalc[:24]} rec={payload_root[:24]}")

    # P04 清单自身哈希三方一致
    tri = [(n, man_side_project.get(n), man_hashes.get("manifest/" + n)) for n in man_names]
    ok4 = all(a and b and a == b for _, a, b in tri)
    gate("P04", "★清单自身 SHA-256：项目侧 == 锚点副本侧（清单即当时那一份）", ok4,
         "; ".join("%s %s" % (n, (a or "")[:12]) for n, a, b in tri))

    # P05 已认可判决被锚定（含失败项）
    ok5 = (man["summary"]["verdict"] == "BASELINE_MANIFEST_SEALED"
           and man["summary"]["n_gates_pass"] == man["summary"]["n_gates"]
           and "FAIL" in APPROVED_JUDGEMENT["original_d5"])
    gate("P05", "清单判决与门禁被锚定，且**原始 D5 FAIL 一并锚定**（⛔ 不只锚成功项）", ok5,
         f"{man['summary']['verdict']} {man['summary']['n_gates_pass']}/{man['summary']['n_gates']} d5=FAIL")

    # P06 负例：卷宗改 1 字节 ⇒ payload_root 变
    tmp = Path(os.environ.get("TEMP", ".")) / "_anchor_neg_roll.txt"
    b = bytearray(roll_text.encode("utf-8"))
    b[len(b) // 2] ^= 0x01
    tmp.write_bytes(bytes(b))
    pr_alt = sha256_file(tmp)
    tmp.unlink(missing_ok=True)
    gate("P06", "（负例）载荷卷宗改 1 字节 ⇒ payload_root 必变（锚有分辨力）",
         pr_alt != payload_root, f"orig={payload_root[:16]}… alt={pr_alt[:16]}…")

    # P07 负例：清单某条容器哈希被改 ⇒ 由该清单生成的卷宗/payload_root 必变
    ent2 = [dict(e) for e in entries]
    tgt = next((e for e in ent2 if e.get("sha256_container")), None)
    tgt["sha256_container"] = "0" * 64
    roll2 = "\n".join("%s\t%s\t%s" % (e["relpath"], e["size_bytes"], e["sha256_container"])
                      for e in sorted(ent2, key=lambda x: x["relpath"])) + "\n"
    gate("P07", "（负例）清单任一条目哈希被改 ⇒ 卷宗重算必不同（清单改动可检出）",
         sha256_bytes(roll2.encode()) != payload_root,
         f"mutated={tgt['relpath']}")

    # P08 负例：登记文件改 1 字节 ⇒ 容器哈希必变
    small = next((e for e in entries if e.get("size_bytes") and e["size_bytes"] < 5_000_000
                  and (PROJECT / e["relpath"]).is_file()), None)
    if small:
        src = PROJECT / small["relpath"]
        tmp2 = Path(os.environ.get("TEMP", ".")) / "_anchor_neg_file.bin"
        d = bytearray(src.read_bytes())
        d[len(d) // 2] ^= 0x01
        tmp2.write_bytes(bytes(d))
        alt = sha256_file(tmp2)
        tmp2.unlink(missing_ok=True)
        gate("P08", "（负例）登记文件改 1 字节 ⇒ 容器哈希必变（逐文件核验有分辨力）",
             alt != small["sha256_container"], f"probe={small['relpath']}")
    else:
        gate("P08", "（负例）登记文件改 1 字节 ⇒ 容器哈希必变", False, "找不到可用小文件作探针")

    # P09 ★由独立位置核验外部副本（用户点名的要求）
    if not args.skip_payload:
        sealed_files = sealed_dir / "files"
        nok = nbad = nmiss = 0
        bad_rels = []
        for e in entries:
            p = sealed_files / e["relpath"]
            if not p.exists():
                nmiss += 1; bad_rels.append(e["relpath"]); continue
            if sha256_file(p) != e["sha256_container"]:
                nbad += 1; bad_rels.append(e["relpath"]); continue
            if e.get("sha256_content") and sha256_gz(p) != e["sha256_content"]:
                nbad += 1; bad_rels.append(e["relpath"]); continue
            nok += 1
        print(f"  [载荷核验] {sealed_files}  VERIFIED={nok} MISMATCH={nbad} MISSING={nmiss}")
        gate("P09", "★由独立位置（锚点目录）核验封存副本 files/ ⇒ 全部一致",
             nbad == 0 and nmiss == 0,
             f"VERIFIED={nok} MISMATCH={nbad} MISSING={nmiss} 共 {len(entries)}"
             + (f" 异常={bad_rels[:3]}" if bad_rels else ""))
    else:
        print("  [载荷核验] 已按 --skip-payload 跳过")

    # ---------------- 8. 第二位置（只增不改）+ 跨位置一致性
    sec_info = {"enabled": False}
    if not args.no_copy:
        ANCHOR_SECONDARY.mkdir(parents=True, exist_ok=True)
        sec_pre = sorted(p.name for p in ANCHOR_SECONDARY.iterdir()
                         if p.is_dir() and p.name.startswith(STAMP)
                         and not p.name.startswith(".staging"))
        sec_supersedes = []
        for n in sec_pre:
            pp = ANCHOR_SECONDARY / n / "POINT_OF_TRUST.txt"
            h = None
            if pp.is_file():
                for line in pp.read_text(encoding="utf-8", errors="ignore").splitlines():
                    if line.startswith("point_of_trust_sha256"):
                        h = line.split("=", 1)[1].strip()
            sec_supersedes.append({"version_dir": n, "point_of_trust": h})
        sec_final_name = next_free(ANCHOR_SECONDARY / STAMP).name
        sdir = ANCHOR_SECONDARY / (".staging_%s" % STAMP)
        if sdir.exists():
            shutil.rmtree(sdir, ignore_errors=True)
        shutil.copytree(adir, sdir)
        n_copied, n_diff = 0, 0
        for r in need:
            a_p, s_p = adir / r, sdir / r
            if not s_p.is_file():
                n_diff += 1; continue
            if sha256_file(a_p) != sha256_file(s_p):
                n_diff += 1
            n_copied += 1
        pt_sec = sha256_file(sdir / "ANCHOR_ROOT.txt")
        print(f"\n次锚点暂存：{sdir}（{n_copied} 件，不一致 {n_diff}）  拟发布 {sec_final_name}")
        print(f"  既有版本（未被覆盖）：{sec_pre or '（无）'}")
        sec_info = {"enabled": True, "dir": str(ANCHOR_SECONDARY / sec_final_name),
                    "staging": str(sdir), "n_copied": n_copied, "n_diff": n_diff,
                    "preexisting": sec_pre, "point_of_trust": pt_sec,
                    "final_name": sec_final_name}
        gate("P10", "★跨位置锚点一致：次锚点 PT == 主锚点 PT",
             pt_sec == pt, f"prim={pt[:24]} sec={pt_sec[:24]}")
        # ★正确语义：不是「不存在前序版本」（重跑时必然存在），而是「前序版本**未被改动**」
        prev_intact = all(
            (ANCHOR_PRIMARY / s["version_dir"] / "ANCHOR_ROOT.txt").is_file()
            and sha256_file(ANCHOR_PRIMARY / s["version_dir"] / "ANCHOR_ROOT.txt") == s["point_of_trust"]
            for s in supersedes) and all(
            (ANCHOR_SECONDARY / s["version_dir"] / "ANCHOR_ROOT.txt").is_file()
            and sha256_file(ANCHOR_SECONDARY / s["version_dir"] / "ANCHOR_ROOT.txt") == s["point_of_trust"]
            for s in sec_supersedes)
        not_clobber = (final_name not in preexisting) and (sec_final_name not in sec_pre)
        gate("P11", "只增不改：前序锚点版本**原样保留**（PT 逐位不变）、本次不覆盖既有版本、次锚点逐件一致",
             prev_intact and not_clobber and n_diff == 0,
             f"前序完好={prev_intact} 未覆盖={not_clobber} n_diff={n_diff} "
             f"主既有={preexisting or '（无）'} 次既有={sec_pre or '（无）'}")

    # P12 PT 可复算且等于记录值
    pt2 = sha256_file(adir / "ANCHOR_ROOT.txt")
    pot_rec = None
    for line in (adir / "POINT_OF_TRUST.txt").read_text(encoding="utf-8").splitlines():
        if line.startswith("point_of_trust_sha256"):
            pot_rec = line.split("=", 1)[1].strip()
    gate("P12", "PT 可复算（两次一致）且 == POINT_OF_TRUST.txt 记录值", pt2 == pt and pot_rec == pt,
         f"calc={pt2[:24]} rec={(pot_rec or '')[:24]}")

    # P13 ★非循环：PT 值不得出现在任何被覆盖锚件中
    hit = []
    for r in ["TRUST_ANCHOR.json", "TRUST_ANCHOR.md", "PAYLOAD_ROLLUP.txt", "ANCHOR_SHA256SUMS.txt"] + sorted(man_hashes):
        try:
            if pt in (adir / r).read_text(encoding="utf-8", errors="ignore"):
                hit.append(r)
        except Exception:
            pass
    gate("P13", "★非循环结构：PT 值不出现在任何被覆盖锚件中（信任链无环）", not hit, f"hit={hit}")

    # P14 ANCHOR_ROOT 所载锚件哈希 == 实测
    rec_root = {}
    for line in (adir / "ANCHOR_ROOT.txt").read_text(encoding="utf-8").splitlines():
        if " = " in line and line[0] not in "# ":
            k, v = line.split(" = ", 1)
            if len(v.strip()) == 64:
                rec_root[k.strip()] = v.strip()
    mism = [k for k, v in rec_root.items()
            if (adir / k).is_file() and sha256_file(adir / k) != v]
    # ★结构性判据（⛔ 不写死条目阈值——那会把「漏列」误判成「数量不足」）：
    #   每一个被覆盖锚件都必须在 ANCHOR_ROOT.txt 中被列出，且哈希与实测一致。
    missing_keys = sorted(set(root_hashes) - set(rec_root))
    gate("P14", "ANCHOR_ROOT.txt 所列锚件哈希 == 实测，且**覆盖全部被覆盖锚件**（无漏列）",
         not mism and not missing_keys,
         f"列出={len(rec_root)} 应有={len(root_hashes)} 漏列={missing_keys} 不符={mism}")

    # P15 介质独立性如实标注
    prim_dev = next((m["disk"] for m in MEDIA_TOPOLOGY if m["drive"].startswith("C")), None)
    sealed_dev = next((m["disk"] for m in MEDIA_TOPOLOGY if m["drive"].startswith("K")), None)
    gate("P15", "主锚点与封存副本位于**不同物理设备**（介质独立性如实成立）",
         prim_dev is not None and sealed_dev is not None and prim_dev != sealed_dev,
         f"C:=disk{prim_dev} K:=disk{sealed_dev}")

    # P16 零依赖核验器在位
    gate("P16", "锚点包含零依赖核验器（任何机器可复核）",
         (adir / "VERIFY_TRUST_ANCHOR.py").is_file(),
         "VERIFY_TRUST_ANCHOR.py")

    # ---------------- 8b. ★发布：仅在**全部门禁通过**时把暂存区落为版本目录
    n_pass_now = sum(1 for g in GATES if g["pass"])
    published = None
    if n_pass_now == len(GATES):
        tgt = ANCHOR_PRIMARY / final_name
        if tgt.exists():
            tgt = next_free(tgt)
        os.replace(adir, tgt)
        adir = tgt
        published = tgt
        print(f"\n★已发布主锚点：{tgt}")
        if sec_info.get("enabled"):
            stgt = ANCHOR_SECONDARY / sec_info["final_name"]
            if stgt.exists():
                stgt = next_free(stgt)
            os.replace(sec_info["staging"], stgt)
            sec_info["dir"] = str(stgt)
            print(f"★已发布次锚点：{stgt}")
    else:
        print(f"\n⛔ 门禁未全通过（{n_pass_now}/{len(GATES)}）⇒ **不发布**；"
              f"暂存区保留于 {adir}（不构成锚点版本）")

    # ---------------- 9. 项目内人读报告（**不纳入覆盖集**：含 PT ⇒ 纳入将成环）
    rep = PROJECT / "reports" / "project_baseline" / ("BASELINE_TRUST_ANCHOR_%s.md" % STAMP)
    R = []
    R.append("# 基线封存 · 独立信任锚记录 — %s\n" % STAMP)
    R.append("> 锚点版本 **`%s`** ｜ 发布状态：**%s** ｜ 生成器门禁 **%d/%d** ｜ 生成于 %s\n"
             % (final_name, "已发布" if published else "未发布（门禁未全通过）",
                n_pass_now, len(GATES), anchor_meta["built"]))
    R.append("> 对应第 2 层保护：**给「封存清单自身」加独立锚**。第 1 层（文件 ≡ 清单）见 `%s`。\n" % manifest_path.name)
    R.append("> 本文件**不在** 92 项封存集内（锚点必须位于被它证明的对象之外）⇒ 改动它不会触发封存漂移。\n")
    R.append("## ★点信任值（Point of Trust）\n")
    R.append("```")
    R.append(pt)
    R.append("```\n")
    R.append("该值 = `sha256(ANCHOR_ROOT.txt)`。请**离线/异地**留存（手抄、自寄邮件、另一台机器）。\n")
    R.append("> 单机环境下此值无法自证；**离线记录是不可再约简的人工步骤**。\n")
    R.append("\n> 本文件描述锚点版本 **`%s`**。\n" % adir.name)
    if supersedes:
        R.append("\n### 前序锚点版本（原样保留，只增不改）\n")
        R.append("| 版本 | 前序 PT |\n|---|---|")
        for s in supersedes:
            R.append("| `%s` | `%s` |" % (s["version_dir"], s["point_of_trust"] or "—"))
        R.append("\n> 若前序 PT 与当前 PT 不同，属**重新生成**所致，非篡改；差异原因见项目日志 `2026-10-12.md`。\n")
    R.append("## 锚点位置\n")
    R.append("| 位置 | 路径 | 介质 | 介质独立于封存副本 |\n|---|---|---|---|")
    R.append("| 主锚点 | `%s` | disk 1（NVMe 内置） | ✔ |" % adir)
    if sec_info.get("enabled"):
        R.append("| 次锚点 | `%s` | disk 2（USB，**同 K:**） | ✘ 仅可用性/交叉核验 |" % sec_info["dir"])
    R.append("\n## 关键值\n")
    R.append("| 项 | 值 |\n|---|---|")
    R.append("| 封存版本目录 | `%s` |" % sealed_dir)
    R.append("| 封存清单 | `%s` |" % manifest_path.name)
    R.append("| 清单判决 / 门禁 | **%s** / %d-%d |" % (man["summary"]["verdict"],
                                                    man["summary"]["n_gates_pass"], man["summary"]["n_gates"]))
    R.append("| 条目 / 体积 | %d / %.3f GiB |" % (n_entries, man["summary"]["total_gib"]))
    R.append("| **payload_root** | `%s` |" % payload_root)
    R.append("\n### 清单自身 SHA-256（项目侧 == 锚点副本侧）\n")
    R.append("| 文件 | sha256 |\n|---|---|")
    for n in man_names:
        R.append("| `%s` | `%s` |" % (n, man_side_project.get(n) or "**MISSING**"))
    R.append("\n## 已认可判决（连同失败项一起锚定）\n")
    R.append("| 项 | 值 |\n|---|---|")
    for k, v in APPROVED_JUDGEMENT.items():
        R.append("| `%s` | %s |" % (k, v))
    R.append("\n## 核验方式\n")
    R.append("```bash")
    R.append("python \"%s\"                                  # 锚点包自洽（秒级）" % (adir / "VERIFY_TRUST_ANCHOR.py"))
    R.append("python \"%s\" --expect <%s>   # 再比对离线记录" % (adir / "VERIFY_TRUST_ANCHOR.py", "PT"))
    R.append("python \"%s\" --payload \"%s\"   # 用锚内清单核验封存副本" % (adir / "VERIFY_TRUST_ANCHOR.py", sealed_dir / "files"))
    R.append("```\n")
    R.append("## 边界\n")
    R.append("- 本锚只回答「**文件是不是那一批、清单是不是那一份**」，**不回答「结论对不对」**。\n")
    R.append("- ⛔ 不提升、不降低任何门禁判定：**原始 D5 仍为 FAIL**，`A5` 仍仅为补充分析。\n")
    R.append("- ⛔ 本轮未改 SCALE / 容量 / freespeed / λ / 阈值；未跑仿真；未晋升 v1.1。\n")
    wtext(rep, "\n".join(R))

    n_pass = sum(1 for g in GATES if g["pass"])
    print("\n" + "=" * 112)
    if not args.no_copy:
        print(f"次锚点：{sec_info.get('dir')}  件数 {sec_info.get('n_copied')}  不一致 {sec_info.get('n_diff')}")
    print(f"[判决] {'TRUST_ANCHOR_ESTABLISHED' if n_pass == len(GATES) else 'TRUST_ANCHOR_GATE_FAILED'}"
          f"  （门禁 {n_pass}/{len(GATES)} PASS，用时 {time.time() - t0:.1f} s）")
    print(f"★POINT_OF_TRUST = {pt}")
    print(f"人读报告：{rep}")
    return 0 if n_pass == len(GATES) else 3


if __name__ == "__main__":
    sys.exit(main())
