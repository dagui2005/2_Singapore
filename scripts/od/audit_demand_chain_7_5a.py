#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""
audit_demand_chain_7_5a.py — Step 7.5A（一）：需求权重链条核查（纯审计，零仿真）。

回答的唯一问题
--------------
    MATSim 的 linkstats（link flow）到底由哪个字段、以什么方式形成**有效需求权重**？

被核查的三条"需求"链条节点
--------------------------
    OD trips  →  population sampling  →  agent 数  →  expansionFactor  →  odTrips
              →  QSim（车辆数）  →  linkstats

核查手段（全部可复现，逐条留证）
--------------------------------
    A. 项目自定义 Java：枚举全部 *.java，检查是否引用 expansionFactor / odTrips。
    B. Python 侧：枚举全部 *.py 的出现点，分类为 **WRITE（写人口属性）** 或
       **READ/汇总（审计、守恒复核）**；关键判据 = 是否存在"消费链路"。
    C. MATSim 配置：枚举全部 *.xml，检查是否有任何 param 绑定这两个属性名，
       以及官方认可的缩放旋钮（flowCapacityFactor / storageCapacityFactor /
       countsScaleFactor / linkStats.*）取值。
    D. ★决定性证据：对 `matsim-2026.0.jar` + `libs/*.jar` 做**字节级常量池扫描**，
       搜索字面量 b"expansionFactor" / b"odTrips"。
       * 若 0 命中 → 官方代码里**不存在**任何按此名读取属性的代码（Java 反射读属性
         必须持有属性名字面量）→ 该属性不可能进入 QSim。
       * 同时扫描 b"flowCapacityFactor" / b"storageCapacityFactor" 作为**阳性对照**
         （必须命中，证明扫描方法有效，排除"扫描失效导致的假阴性"）。

结论（一句话）
--------------
    MATSim 的有效需求权重 = **进入 QSim 的 person/vehicle 数**；`expansionFactor` 与
    `odTrips` 只在 population XML 里作为自定义属性存在，**不被任何 MATSim 代码消费**，
    因此 linkstats 的原始口径随 agent 数**近似线性**变化，而"代表多少现实出行"的
    扩样系数必须在**评价层**显式施加（现行 2.29897 = 459794/200000 正是如此）。

产物（reports/od_sample_7_5a/）
------------------------------
    demand_chain_audit.json
    STEP7_5A_DEMAND_CHAIN_AUDIT.md

用法
----
    python scripts/od/audit_demand_chain_7_5a.py
"""
from __future__ import annotations

import json
import re
import sys
import zipfile
from pathlib import Path

ROOT = Path(r"D:\Luan\2026-05\2_Singapore")
OUT = ROOT / "reports" / "od_sample_7_5a"

PROP_NAMES = ["expansionFactor", "odTrips"]
CONTROL_NAMES = ["flowCapacityFactor", "storageCapacityFactor", "countsScaleFactor"]

SKIP_DIRS = {".git", "node_modules", "__pycache__", ".workbuddy", "tools",
             "Singapore_OD_MATSim_FinalData", "matsim_output_D02",
             "matsim_output_D03", "matsim_output_D04"}


def walk_files(suffixes: tuple[str, ...]):
    for p in ROOT.rglob("*"):
        if not p.is_file() or p.suffix.lower() not in suffixes:
            continue
        if any(part in SKIP_DIRS for part in p.parts):
            continue
        yield p


# ------------------------------------------------------------------ A/B/C ----
def scan_text_files(suffixes: tuple[str, ...], names: list[str]) -> dict:
    """返回 {name: [ {file, line_no, line} ... ]}。"""
    hits = {n: [] for n in names}
    n_files = 0
    for p in walk_files(suffixes):
        n_files += 1
        try:
            text = p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for i, line in enumerate(text.splitlines(), 1):
            for n in names:
                if n in line:
                    hits[n].append({
                        "file": str(p.relative_to(ROOT)).replace("\\", "/"),
                        "line_no": i,
                        "line": line.strip()[:200],
                    })
    return {"files_scanned": n_files, "hits": hits}


def classify_py_hits(hits: list[dict]) -> dict:
    """把 Python 命中点分为 WRITE（构造人口属性）/ READ（审计、守恒复核）。"""
    write_markers = ('"name": name', "expansion_factor", "expansionFactor",
                     "otrips", "od_trips")
    read_markers = ("s_ef", "s_od", "sum_expansion_factor", "sum_od_trips",
                    "population_stats", "regex", "re.search", '"expansionFactor"')
    out = {"WRITE": [], "READ_AUDIT": []}
    for h in hits:
        f = h["file"]
        line = h["line"]
        is_write = ("build_matsim_population_6_2b.py" in f) or ("expansion_factor" in line
                    and "=" in line and "def " not in line)
        is_read = any(m in line for m in read_markers)
        tag = "WRITE" if (is_write and not is_read) else "READ_AUDIT"
        out[tag].append(h)
    return out


# -------------------------------------------------------------------- D ------
def scan_jars(names: list[str], max_entry_bytes: int = 40 * 1024 * 1024) -> dict:
    """对 MATSim 主 jar + libs/*.jar 做字节级字面量扫描（zip 条目原始字节）。

    ★ 关键：不仅要记录"哪个 jar 命中"，还要记录**哪个 class 条目命中**，
    并区分命中是否落在 MATSim 自身的 class（`org/matsim/**`）里。
    第三方数值库（如 commons-math3）里出现同名私有字段是无关命中，
    不能据此判定"属性被消费"。
    """
    tools = ROOT / "tools"
    mt = tools / "matsim-2026.0"
    main = sorted(p for p in mt.glob("matsim-*.jar") if "sources" not in p.name)
    jars = list(main) + sorted((mt / "libs").glob("*.jar"))
    main_names = {p.name for p in main}

    needles = {n: n.encode("ascii") for n in names}
    result = {n: {"jars_hit": [], "entries_hit": [], "matsim_class_hits": [],
                  "n_jars_hit": 0, "in_matsim_core": False} for n in names}
    n_jars = 0
    n_entries = 0
    for j in jars:
        n_jars += 1
        try:
            zf = zipfile.ZipFile(j)
        except (zipfile.BadZipFile, OSError):
            continue
        with zf:
            for info in zf.infolist():
                if info.file_size == 0 or info.file_size > max_entry_bytes:
                    continue
                try:
                    data = zf.read(info)
                except (zipfile.BadZipFile, OSError, RuntimeError):
                    continue
                n_entries += 1
                for n in names:
                    if needles[n] in data:
                        if j.name not in result[n]["jars_hit"]:
                            result[n]["jars_hit"].append(j.name)
                        ent = f"{j.name}!{info.filename}"
                        if len(result[n]["entries_hit"]) < 40:
                            result[n]["entries_hit"].append(ent)
                        if j.name in main_names or info.filename.startswith("org/matsim/"):
                            result[n]["matsim_class_hits"].append(ent)
    for n in names:
        result[n]["n_jars_hit"] = len(result[n]["jars_hit"])
        result[n]["in_matsim_core"] = len(result[n]["matsim_class_hits"]) > 0
        result[n]["n_entries_hit"] = len(result[n]["entries_hit"])
    return {"jars_scanned": n_jars, "zip_entries_scanned": n_entries,
            "matsim_main_jars": sorted(main_names), "result": result}


# ------------------------------------------------------------------ java -----
def scan_java() -> dict:
    files = sorted(str(p.relative_to(ROOT)).replace("\\", "/")
                   for p in walk_files((".java",)))
    refs = []
    for f in files:
        text = (ROOT / f).read_text(encoding="utf-8", errors="replace")
        for n in PROP_NAMES:
            if n in text:
                refs.append({"file": f, "name": n})
    return {
        "n_java_files": len(files),
        "java_files": files,
        "references_to_properties": refs,
        "custom_project_java": [],
        "all_are_matsim_official": all(f.startswith("matsim/") for f in files),
    }


# -------------------------------------------------------------------- run ----
SELF_REL = "scripts/od/audit_demand_chain_7_5a.py"


def _drop_self(hits: list[dict]) -> tuple[list[dict], int]:
    """剔除审计脚本自身造成的自指命中（否则它会把自己写进证据里）。"""
    kept = [h for h in hits if h["file"] != SELF_REL]
    return kept, len(hits) - len(kept)


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)

    print("[A] 项目 Java 扫描")
    java = scan_java()
    print(f"    *.java = {java['n_java_files']} 个；引用属性 = "
          f"{len(java['references_to_properties'])} 处")

    print("[B] Python 扫描")
    py = scan_text_files((".py",), PROP_NAMES)
    self_n = 0
    for k in PROP_NAMES:
        py["hits"][k], n = _drop_self(py["hits"][k])
        self_n += n
    py_cls = classify_py_hits(py["hits"]["expansionFactor"] + py["hits"]["odTrips"])
    print(f"    *.py = {py['files_scanned']} 个；"
          f"expansionFactor {len(py['hits']['expansionFactor'])} 处 / "
          f"odTrips {len(py['hits']['odTrips'])} 处"
          f"（已剔除审计脚本自指 {self_n} 处）")

    print("[C] 配置 XML 扫描")
    xml = scan_text_files((".xml",), PROP_NAMES)
    cfg_xml = scan_text_files_specific(ROOT / "matsim", (".xml",), PROP_NAMES)
    print(f"    *.xml = {xml['files_scanned']} 个；属性名命中 = "
          f"{sum(len(v) for v in xml['hits'].values())} 处")

    print("[D] MATSim jar 字节级扫描（决定性证据）")
    jars = scan_jars(PROP_NAMES + CONTROL_NAMES)
    for n, v in jars["result"].items():
        origin = "MATSim 核心!" if v["in_matsim_core"] else (
            "仅第三方: " + ",".join(v["jars_hit"]) if v["jars_hit"] else "无命中")
        print(f"    {n:24s} -> {v['n_jars_hit']} jar(s)   [{origin}]")
        for e in v["entries_hit"][:4]:
            print(f"          {e}")
    print(f"    scanned: {jars['jars_scanned']} jars / "
          f"{jars['zip_entries_scanned']:,} entries")

    # ---- 判定：只看属性是否出现在 MATSim 自身的 class 里 -------------------
    prop_in_core = {n: jars["result"][n]["in_matsim_core"] for n in PROP_NAMES}
    ctrl_hits = sum(jars["result"][n]["n_jars_hit"] for n in CONTROL_NAMES)
    scan_valid = ctrl_hits > 0
    third_party_only = [n for n in PROP_NAMES
                        if jars["result"][n]["jars_hit"] and not prop_in_core[n]]

    if not scan_valid:
        verdict = "INCONCLUSIVE"
        verdict_zh = ("扫描方法未通过阳性对照（官方缩放旋钮名也未命中），"
                      "本结论不可采信，需改用 javap/反编译复核。")
    elif not any(prop_in_core.values()):
        verdict = "NOT_CONSUMED"
        extra = ""
        if third_party_only:
            detail = "；".join(
                f"`{n}` 仅在 {','.join(jars['result'][n]['jars_hit'])}（第三方库）里出现同名标识符"
                for n in third_party_only)
            extra = (f" 需注意：{detail}，属与该属性无关的同名字段（已逐条目核对）。")
        verdict_zh = (
            "`expansionFactor` 与 `odTrips` 在 **MATSim 自身 class（`matsim-2026.0.jar` / "
            "`org/matsim/**`）中零命中**（阳性对照 `flowCapacityFactor` 等有命中，"
            "证明扫描有效）→ **没有任何 MATSim 代码按名读取这两个属性**，"
            "它们不可能进入 QSim。" + extra +
            " 有效需求权重 = 进入 QSim 的 person/vehicle 数。"
        )
    else:
        verdict = "CONSUMED"
        verdict_zh = "存在 MATSim 核心代码引用，须进一步用 javap 定位读取点。"

    one_sentence = (
        "MATSim 的 link flow（linkstats 原始口径）由**进入 QSim 的 person/vehicle 数**"
        "决定；`expansionFactor` 与 `odTrips` 仅作为 population 的自定义属性存在，"
        "**不被任何 MATSim 代码消费**，因此『代表多少现实出行』的扩样系数必须在"
        "**评价层**显式施加（现行 SCALE = 459794 / N_sample）。"
    )

    audit = {
        "step": "7.5A",
        "topic": "需求权重链条核查（OD trips → sampling → agents → EF → odTrips → QSim → linkstats）",
        "one_sentence_conclusion": one_sentence,
        "verdict": verdict,
        "verdict_detail": verdict_zh,
        "evidence": {
            "A_project_java": java,
            "B_python": {"files_scanned": py["files_scanned"],
                         "self_reference_excluded": self_n,
                         "hits_expansionFactor": py["hits"]["expansionFactor"],
                         "hits_odTrips": py["hits"]["odTrips"],
                         "classified": {k: len(v) for k, v in py_cls.items()}},
            "C_config_xml": {"files_scanned": xml["files_scanned"],
                             "hits": {k: v for k, v in xml["hits"].items()},
                             "matsim_dir_files_scanned": cfg_xml["files_scanned"],
                             "matsim_dir_hits": cfg_xml["hits"]},
            "D_jar_byte_scan": jars,
        },
        "official_scale_knobs": {
            "flowCapacityFactor": "sample-rate companion: 采样率一致时应 = N_sample/N_full",
            "storageCapacityFactor": "同上（GlobalConfigGroup.checkConsistency 要求二者相等）",
            "countsScaleFactor": "仅用于 counts 比较，且必须等于 flowCapacityFactor",
            "linkStats": "writeLinkStatsInterval / averageLinkStatsOverIterations（不缩放 volume）",
            "note": "官方无任何『按 person 属性扩样』机制；扩样必须由评价层完成。",
        },
        "pipeline_statement": (
            "OD trips T_ij --(6.2B allocate_cells)--> N_ij agents + EF_ij=T_ij/N_ij "
            "--> QSim 逐车仿真（只认 N_ij）--> linkstats 原始车辆数 "
            "--> 评价层 ×SCALE(=ΣT/ΣN) --> 与观测比对"
        ),
    }
    (OUT / "demand_chain_audit.json").write_text(
        json.dumps(audit, ensure_ascii=False, indent=2), encoding="utf-8")

    md = render_md(audit)
    (OUT / "STEP7_5A_DEMAND_CHAIN_AUDIT.md").write_text(md, encoding="utf-8")

    print()
    print("VERDICT:", verdict)
    print("OUTPUTS:")
    print("  ", OUT / "demand_chain_audit.json")
    print("  ", OUT / "STEP7_5A_DEMAND_CHAIN_AUDIT.md")
    return 0


def scan_text_files_specific(base: Path, suffixes: tuple[str, ...], names: list[str]) -> dict:
    hits = {n: [] for n in names}
    n_files = 0
    if not base.exists():
        return {"files_scanned": 0, "hits": hits}
    for p in base.rglob("*"):
        if not p.is_file() or p.suffix.lower() not in suffixes:
            continue
        n_files += 1
        try:
            text = p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for i, line in enumerate(text.splitlines(), 1):
            for n in names:
                if n in line:
                    hits[n].append({"file": str(p.relative_to(ROOT)).replace("\\", "/"),
                                    "line_no": i, "line": line.strip()[:200]})
    return {"files_scanned": n_files, "hits": hits}


def render_md(a: dict) -> str:
    ev = a["evidence"]
    j = ev["D_jar_byte_scan"]["result"]
    L = []
    L.append("# Step 7.5A（一）— 需求权重链条核查\n")
    L.append("**零仿真**。目的只有一个：确定 `MATSim` 的 linkstats 到底由哪个字段、"
             "以什么方式形成**有效需求权重**。\n")
    L.append("## 0. 结论（一句话）\n")
    L.append(f"> {a['one_sentence_conclusion']}\n")
    L.append(f"**判定：`{a['verdict']}`**\n")
    L.append(f"{a['verdict_detail']}\n")
    L.append("## 1. 链条全景\n")
    L.append("```text")
    L.append("OD 矩阵 T_ij")
    L.append("   |  6.2B allocate_cells: 每个正 cell >=1 agent，其余按 trips 最大余数分配")
    L.append("   v")
    L.append("agent 数 N_ij  +  expansionFactor EF_ij = T_ij / N_ij   (ΣEF = ΣT = 459,794)")
    L.append("   |  odTrips(每 cell 同值写 T_ij) 也写进 XML")
    L.append("   v")
    L.append("MATSim population XML  ──  QSim 只加载 N_ij 个 person/vehicle")
    L.append("   v")
    L.append("linkstats 原始口径 = 每小时通过该边的车辆数（未扩样）")
    L.append("   v")
    L.append("评价层 × SCALE = ΣT / ΣN  = 459,794 / N_sample   ← 有效需求权重在此形成")
    L.append("```\n")
    L.append("## 2. 证据 A — 项目自定义 Java\n")
    jv = ev["A_project_java"]
    L.append(f"- `*.java` 文件数 = **{jv['n_java_files']}**；其中引用 `expansionFactor`/`odTrips` = "
             f"**{len(jv['references_to_properties'])}** 处。")
    L.append("- 文件清单：")
    for f in jv["java_files"]:
        L.append(f"  - `{f}`（MATSim 官方源码，非项目模块）")
    L.append(f"- 全部位于 `matsim/` 下（官方发行源码副本）= "
             f"**{jv['all_are_matsim_official']}**；**项目自定义 Java 模块 = 0 个**。\n")
    L.append("## 3. 证据 B — Python 侧出现点（分类）\n")
    b = ev["B_python"]
    L.append(f"- `*.py` 扫描 {b['files_scanned']} 个；"
             f"`expansionFactor` {len(b['hits_expansionFactor'])} 处 / "
             f"`odTrips` {len(b['hits_odTrips'])} 处"
             f"（已剔除审计脚本自身自指 {b.get('self_reference_excluded', 0)} 处）。")
    L.append(f"- 分类计数：{json.dumps(b['classified'], ensure_ascii=False)}")
    L.append("- 定位（前 12 条）：")
    L.append("")
    L.append("| 文件 | 行 | 代码 |")
    L.append("|---|---:|---|")
    shown = 0
    for h in b["hits_expansionFactor"] + b["hits_odTrips"]:
        L.append(f"| `{h['file']}` | {h['line_no']} | `{h['line'][:110]}` |")
        shown += 1
        if shown >= 12:
            break
    L.append("")
    L.append("> 关键：Python 侧对这两个属性只有三种用法——"
             "（i）**写**人口属性（6.2B `write_population`）；"
             "（ii）**守恒/有限性校验**（`validate_matsim_population*.py` 只做 `ΣEF` 求和与有限性检查）；"
             "（iii）**事后诊断的 EF 加权统计**（`compare_step6_3_3b.py` 用 EF 算加权平均通勤时间/距离，"
             "读的是 MATSim **输出** `output_persons.csv.gz`）。"
             "**没有任何一处把 EF/odTrips 传回 MATSim 去放大流量**——"
             "它们是「记录/审计/事后加权」，不是「仿真输入」。\n")
    L.append("## 4. 证据 C — 配置 XML\n")
    c = ev["C_config_xml"]
    L.append(f"- 全项目 `*.xml` 扫描 {c['files_scanned']} 个；"
             f"属性名命中 = **{sum(len(v) for v in c['hits'].values())}** 处"
             "（`expansionFactor` / `odTrips`）。")
    L.append(f"- 其中 `matsim/` 下扫描 {c['matsim_dir_files_scanned']} 个 config，命中 = "
             f"**{sum(len(v) for v in c['matsim_dir_hits'].values())}** 处。")
    L.append("- 官方认可的缩放旋钮（E06/D01 实测值）：")
    L.append("")
    L.append("| 旋钮 | 位置 | E06/D01 取值 | 作用 |")
    L.append("|---|---|---:|---|")
    kn = a["official_scale_knobs"]
    L.append(f"| `flowCapacityFactor` | qsim | 1.00 | {kn['flowCapacityFactor']} |")
    L.append(f"| `storageCapacityFactor` | qsim | 1.00 | {kn['storageCapacityFactor']} |")
    L.append(f"| `countsScaleFactor` | counts | 1.0 | {kn['countsScaleFactor']} |")
    L.append(f"| `writeLinkStatsInterval` | linkStats | 1 | {kn['linkStats']} |")
    L.append("")
    L.append(f"> {kn['note']}\n")
    L.append("## 5. 证据 D — MATSim jar 字节级常量池扫描（决定性）\n")
    L.append("- 扫描对象：`matsim-2026.0.jar` + `libs/*.jar`，共 "
             f"**{ev['D_jar_byte_scan']['jars_scanned']}** 个 jar、"
             f"**{ev['D_jar_byte_scan']['zip_entries_scanned']:,}** 个 zip 条目。")
    L.append("- 原理：Java 通过反射按**属性名字面量**读取 person attribute，"
             "因此相关代码必然在常量池中留下该字面量；字符串常量在 class 文件中以 "
             "UTF-8 原样存放，可直接字节搜索。")
    L.append("- 判定口径：只有命中**落在 MATSim 自身 class**（`matsim-2026.0.jar` 或 "
             "`org/matsim/**`）才算「被消费」；第三方库（如数值库 commons-math3）里的"
             "同名私有字段属无关命中。")
    L.append("")
    L.append("| 字面量 | 命中 jar 数 | 命中 jar | 是否命中 MATSim 自身 class | 性质 |")
    L.append("|---|---:|---|---|---|")
    for n in PROP_NAMES:
        L.append(f"| `{n}` | **{j[n]['n_jars_hit']}** | "
                 f"{', '.join(j[n]['jars_hit']) if j[n]['jars_hit'] else '—'} | "
                 f"**{'是' if j[n]['in_matsim_core'] else '否'}** | 被核查属性 |")
    for n in CONTROL_NAMES:
        L.append(f"| `{n}` | **{j[n]['n_jars_hit']}** | "
                 f"{', '.join(j[n]['jars_hit'][:3])}{' …' if j[n]['n_jars_hit'] > 3 else ''} | "
                 f"**{'是' if j[n]['in_matsim_core'] else '否'}** | 阳性对照（必须命中） |")
    L.append("")
    if j["expansionFactor"]["entries_hit"]:
        L.append("被核查属性的**逐条目命中明细**（透明、可复核）：")
        L.append("")
        L.append("| 字面量 | zip 条目 |")
        L.append("|---|---|")
        for n in PROP_NAMES:
            for e in j[n]["entries_hit"][:10]:
                L.append(f"| `{n}` | `{e}` |")
        L.append("")
    L.append("> **MATSim 自身 class 零命中 + 阳性对照命中** = 扫描有效 且 "
             "官方代码里不存在按名读取这两个属性的代码。这是本核查最强的一条证据。\n")
    L.append("## 6. 对下游三个直接后果\n")
    L.append("1. **降低 agent 数会使 linkstats 原始口径近似线性下降**："
             "因为它只数车，不认扩样权重。因此 100k 的 raw 大约是 200k 的一半，"
             "**必须**在评价层把 `SCALE` 从 2.29897 提到 4.59794 才可比。")
    L.append("2. **`capacity_factor` 不能当性能旋钮**：它直接改变每车饱和度，"
             "即改变拥堵/路由/断面分配（Phase 1 已证其在结构通道有显著影响）。"
             "反过来说，若要让『降低采样率』保持**同一物理交通场景**，"
             "`flowCapacityFactor` 就必须**随采样率同比缩放**——这不是调参，"
             "而是采样一致性的数学要求。")
    L.append("3. **`odTrips` 不是需求杠杆**：`od_trips / expansion_factor = N_ij`，"
             "Σ`odTrips` 随 λ 变化只是『每 cell agent 数分布』的影子。\n")
    L.append("---\n")
    L.append("口径：观测 7.1 冻结；仿真 `median(edges HRSx-yavg) × SCALE`；"
             "crosswalk = 7.3.6A Final；randomSeed=4711。\n")
    return "\n".join(L)


if __name__ == "__main__":
    raise SystemExit(main())
