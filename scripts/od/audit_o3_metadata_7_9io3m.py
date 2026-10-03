# -*- coding: utf-8 -*-
"""audit_o3_metadata_7_9io3m.py — Step 7.9I-O3-METADATA 零仿真审计引擎

目的：恢复 TrafficFlow → Detector / 道路设施 的可连接身份链（第一步：把「缺什么」钉死）
纪律：零仿真；不改模型/评价器；不跑 MATSim；缺元数据一律 UNRESOLVED/ABSENT/BLOCKED
判据来源：reports/corridor_scale_audit_7_9i/PREREG_7_9I_O3METADATA.md（运行前冻结）
产物：o3m_schema_reconciliation.csv / o3m_field_fill.csv / o3m_m_gates.json
"""
from __future__ import annotations

import ast
import csv
import hashlib
import json
import re
import zipfile
from pathlib import Path

ROOT = Path(r"D:\Luan\2026-05\2_Singapore")
STATIC = ROOT / "Static_ 2026_03"
DYN = ROOT / "Dynamic_2026_03_16"
OUT = ROOT / "reports" / "corridor_scale_audit_7_9i"
OUT.mkdir(parents=True, exist_ok=True)

GEO = STATIC / "GEOSPATIAL"
DET_SHPX = GEO / "DetectorLoop_Mar2026/DetectorLoop_Mar2026/DetectorLoop.shp.xml"
DET_DBF = GEO / "DetectorLoop_Mar2026/DetectorLoop_Mar2026/DetectorLoop.dbf"
RSL_SHPX = GEO / "RoadSectionLine_Mar2026/RoadSectionLine_Mar2026/RoadSectionLine.shp.xml"
RSL_DBF = GEO / "RoadSectionLine_Mar2026/RoadSectionLine_Mar2026/RoadSectionLine.dbf"
DET_ZIP = DYN / "historical_data/geospatial/DetectorLoop.zip"
DET_ZIP_ENTRY = "DetectorLoop_Mar2026/DetectorLoop.dbf"
TF_LINKS_DBF = DYN / "historical_data/TrafficFlow_Links.dbf"
TF_DATA_JSON = DYN / "historical_data/TrafficFlow_Data.json"
DOC_STATIC = STATIC / "DATA_DOCUMENTATION.md"
DOC_DYN = DYN / "DATA_README.md"

# ---------------- 冻结常量 ----------------
EXP_DET_OFFICIAL_N = 12
EXP_RSL_OFFICIAL_N = 11
EXP_DET_DELIVERED = {"OBJECTID"}
EXP_RSL_DELIVERED = {"RD_CD", "RD_CATG_NA", "RD_CATG__1", "RD_CD_DESC"}
EXP_DOC_FABRICATED_DET = {"LANE_NUM", "DETECTOR_ID", "REMARKS"}   # DetectorLoop 文档独有
EXP_DET_OFFICIAL_ONLY_N = 10                                      # 官方有、DetectorLoop 文档无
EXP_FILL = {"RD_CD": 0.0000, "RD_CATG_NA": 0.0000, "RD_CATG__1": 1.0000, "RD_CD_DESC": 1.0000}
FILL_TOL = 1e-4
IMPLICIT = {"OBJECTID", "SHAPE"}                                  # shapefile 隐式字段
EXP_M_STATE = {"M1a": "ABSENT", "M1b": "ABSENT", "M2": "BLOCKED",
               "M3": "BLOCKED", "M4": "BLOCKED"}
EXP_ZIP_FIELDS = {"OBJECTID"}
EXP_NEG = {"N1": "M1b", "N2": "M2", "N3": "key_available", "N4": "official_n", "N5": "M3"}


def norm(s: str) -> str:
    """字段名规范化：shapefile 中 `SHAPE.LEN` 与 `SHAPE_LEN` 指同一字段。"""
    return s.replace(".", "_")

MCODE = {"ABSENT": 0, "BLOCKED": 1, "UNRESOLVED": 2, "EVALUABLE": 3, "PRESENT": 4}

FIELD_RE = re.compile(
    r"([A-Za-z_][A-Za-z0-9_\.]*)\s+'([^']*)'\s+(?:true|false)\s+(?:true|false)\s+(?:true|false)\s+"
    r"(\d+)\s+(Text|Date|Double|Short|Long|Integer|Single)")

BASE = dict(official_source="shp_xml", key_tier="code", nonempty_thresh=1,
            inject_detector_id=False, inject_rd_cd=False, inject_lane=False)


# ---------------- 基础读取 ----------------
def _dbf_header(b: bytes):
    nrec = int.from_bytes(b[4:8], "little")
    hlen = int.from_bytes(b[8:10], "little")
    fields, off = [], 32
    while off < hlen and b[off] != 0x0D:
        name = b[off:off + 11].split(b"\x00")[0].decode("ascii", "replace")
        fields.append((name, chr(b[off + 11]), b[off + 16]))
        off += 32
    return fields, nrec


def dbf_scan(path: Path):
    """返回 (fields, nrec, fill_frac) —— 纯字节解析，无第三方依赖。"""
    b = path.read_bytes()
    fields, nrec = _dbf_header(b)
    hlen = int.from_bytes(b[8:10], "little")
    rlen = int.from_bytes(b[10:12], "little")
    cnt = {f[0]: 0 for f in fields}
    for i in range(nrec):
        rec = b[hlen + i * rlen: hlen + (i + 1) * rlen]
        off = 1
        for name, _t, flen in fields:
            if rec[off:off + flen].strip(b" \x00"):
                cnt[name] += 1
            off += flen
    fill = {k: (v / nrec if nrec else 0.0) for k, v in cnt.items()}
    return fields, nrec, fill


def official_schema(path: Path) -> set:
    t = path.read_text(encoding="utf-8", errors="replace")
    return {norm(m.group(1)) for m in FIELD_RE.finditer(t)}


def doc_fields_bullet(path: Path, anchor: str):
    """解析 `  - \\`FIELD\\`: 说明` 形式的字段清单（DATA_README.md 用此风格）。"""
    lines = path.read_text(encoding="utf-8").splitlines()
    i = next(k for k, l in enumerate(lines) if anchor in l)
    out = []
    for l in lines[i + 1:]:
        s = l.strip()
        if re.match(r"^-\s*\*\*", s):          # 下一个顶层条目
            if out:
                break
            continue
        m = re.match(r"^-\s*`([^`]+)`\s*[:：]", s)
        if m:
            out.append(norm(m.group(1)))
        elif out:
            break
    return out


def doc_fields(path: Path, anchor: str):
    """解析 markdown 表格形式的字段清单（DATA_DOCUMENTATION.md 用此风格）。"""
    lines = path.read_text(encoding="utf-8").splitlines()
    i = next(k for k, l in enumerate(lines) if anchor in l)
    out, started = [], False
    for l in lines[i + 1:]:
        s = l.strip()
        if s.startswith("|"):
            cells = [c.strip() for c in s.strip("|").split("|")]
            c0 = cells[0] if cells else ""
            if c0 == "字段名" or (c0 and set(c0) <= set("-: ")):
                continue
            if c0:
                out.append(norm(c0))
                started = True
        elif started:
            break
    return out


# ---------------- 唯一入口 ----------------
def compute(p):
    # (1) 官方 GDM schema
    if p["official_source"] == "shp_xml":
        det_off = official_schema(DET_SHPX)
        rsl_off = official_schema(RSL_SHPX)
    else:                                     # N4：退化到交付 dbf
        det_off = {f[0] for f in _dbf_header(DET_DBF.read_bytes())[0]}
        rsl_off = {f[0] for f in _dbf_header(RSL_DBF.read_bytes())[0]}

    # (2) 交付字段 + 填充率
    det_f, det_n, det_fill = dbf_scan(DET_DBF)
    rsl_f, rsl_n, rsl_fill = dbf_scan(RSL_DBF)
    det_fill = {norm(k): v for k, v in det_fill.items()}
    rsl_fill = {norm(k): v for k, v in rsl_fill.items()}
    det_del = {norm(f[0]) for f in det_f}
    rsl_del = {norm(f[0]) for f in rsl_f}
    if p["inject_detector_id"]:               # N1
        det_del = det_del | {"DETECTOR_ID"}
    if p["inject_lane"]:                      # N5
        det_del = det_del | {"LANE_NUM"}
    if p["inject_rd_cd"]:                     # N2：模拟「属性完整版 DetectorLoop 到手」
        det_del = det_del | {"RD_CD"}
        det_fill = dict(det_fill, RD_CD=1.0)
        rsl_fill = dict(rsl_fill, RD_CD=1.0)

    # (3) 第二获取路径（zip）
    with zipfile.ZipFile(DET_ZIP) as z:
        zf, zn = _dbf_header(z.read(DET_ZIP_ENTRY))
    det_zip = {norm(f[0]) for f in zf}

    # (4) 文档声明
    det_doc = doc_fields(DOC_STATIC, "### 8. DetectorLoop_Mar2026")
    rsl_doc = doc_fields(DOC_STATIC, "### 22. RoadSectionLine_Mar2026")
    tf_doc = doc_fields_bullet(DOC_DYN, "#### **TrafficFlow_Data.json**")

    # (5) 三方差集
    det_doc_only = set(det_doc) - det_off - IMPLICIT
    det_off_only = det_off - set(det_doc)
    det_del_only = det_del - det_off - IMPLICIT
    rsl_doc_only = set(rsl_doc) - rsl_off - IMPLICIT
    rsl_off_only = rsl_off - set(rsl_doc)
    rsl_del_only = rsl_del - rsl_off - IMPLICIT

    # (6) TrafficFlow_Data 实际字段
    tf_actual = set()
    with open(TF_DATA_JSON, encoding="utf-8") as fh:
        head = fh.read(400000)
    m = re.search(r'"value"\s*:\s*\[\s*\{', head, re.I)
    if m:
        seg = head[m.end() - 1:]
        keys = re.findall(r'"([A-Za-z_0-9]+)"\s*:', seg[:4000])
        tf_actual = set(keys)

    thr = p["nonempty_thresh"]
    det_rd_cd_ok = ("RD_CD" in det_del) and (det_fill.get("RD_CD", 0.0) >= thr)
    rsl_rd_cd_ok = (rsl_fill.get("RD_CD", 0.0) >= thr)

    # (7) M 门
    M = {}
    M["M1a"] = "PRESENT" if det_rd_cd_ok else "ABSENT"
    M["M1b"] = "PRESENT" if (("DETECTOR_ID" in det_del) or ("DETECTOR_ID" in det_zip)) else "ABSENT"
    M["M2"] = "EVALUABLE" if (M["M1a"] == "PRESENT" and rsl_rd_cd_ok) else "BLOCKED"
    M["M3"] = "PRESENT" if (("LANE_NUM" in det_del) or ("LANE_NUM" in rsl_del)
                            or ("DIR" in det_del)) else "BLOCKED"
    M["M4"] = "EVALUABLE" if (M["M1a"] == "PRESENT" and M["M1b"] == "PRESENT"
                              and M["M3"] == "PRESENT") else "BLOCKED"

    # (8) 连接键可用性（键「层级」选择可扰动 ⇒ N3：code 级 vs name 级）
    name_level_ok = bool(("RD_NAM" in rsl_off) and ("RD_CD_DESC" in rsl_del)
                         and rsl_fill.get("RD_CD_DESC", 0.0) >= thr)
    if p["key_tier"] == "code":
        key_available = bool(M["M1a"] == "PRESENT" and rsl_rd_cd_ok)
    else:                                     # name 级：RD_CD_DESC ↔ RD_NAM
        key_available = name_level_ok
    name_level_available = name_level_ok

    official_n = len(det_off) + len(rsl_off)
    delivered_n = len(det_del) + len(rsl_del)

    return dict(
        p=dict(p),
        official={"DetectorLoop": sorted(det_off), "RoadSectionLine": sorted(rsl_off)},
        delivered={"DetectorLoop": sorted(det_del), "RoadSectionLine": sorted(rsl_del)},
        zip_fields=sorted(det_zip),
        fill={"DetectorLoop": {k: round(v, 6) for k, v in sorted(det_fill.items())},
              "RoadSectionLine": {k: round(v, 6) for k, v in sorted(rsl_fill.items())}},
        doc={"DetectorLoop": det_doc, "RoadSectionLine": rsl_doc, "TrafficFlow_Data": tf_doc},
        diff=dict(det_doc_only=sorted(det_doc_only), det_off_only=sorted(det_off_only),
                  det_del_only=sorted(det_del_only), rsl_doc_only=sorted(rsl_doc_only),
                  rsl_off_only=sorted(rsl_off_only), rsl_del_only=sorted(rsl_del_only),
                  tf_doc_claim=sorted(set(tf_doc)), tf_actual=sorted(tf_actual),
                  tf_missing=sorted(set(tf_doc) - tf_actual)),
        M=M, key_available=key_available, name_level_available=name_level_available,
        official_n=official_n, delivered_n=delivered_n,
        counts=dict(det_n=det_n, rsl_n=rsl_n, det_zip_n=zn,
                    det_official_n=len(det_off), rsl_official_n=len(rsl_off)),
    )


def sig(res):
    """负例签名 —— 必含可观测量。"""
    return (res["official_n"], res["delivered_n"],
            round(sum(res["fill"]["DetectorLoop"].values())
                  + sum(res["fill"]["RoadSectionLine"].values()), 4),
            sum(MCODE[res["M"][k]] for k in ("M1a", "M1b", "M2", "M3", "M4")),
            int(res["key_available"]))


def observable(res, which):
    if which == "M1b":
        return res["M"]["M1b"]
    if which == "M2":
        return res["M"]["M2"]
    if which == "M3":
        return res["M"]["M3"]
    if which == "key_available":
        return int(res["key_available"])
    if which == "official_n":
        return res["official_n"]
    raise KeyError(which)


# ---------------- 主流程 ----------------
def main():
    log = []

    def say(s):
        print(s)
        log.append(s)

    say("== Step 7.9I-O3-METADATA 零仿真审计 ==")
    base = compute(dict(BASE))
    gate = {}
    base_sig = sig(base)

    # G-M1 官方 schema
    det_o, rsl_o = base["counts"]["det_official_n"], base["counts"]["rsl_official_n"]
    gate["G-M1"] = dict(passed=(det_o == EXP_DET_OFFICIAL_N and rsl_o == EXP_RSL_OFFICIAL_N),
                        measured=dict(DetectorLoop=det_o, RoadSectionLine=rsl_o,
                                      expect=[EXP_DET_OFFICIAL_N, EXP_RSL_OFFICIAL_N]),
                        src="*.shp.xml (LTA GDM FGDC 字段映射)")
    say("G-M1 官方 schema: DetectorLoop=%d RoadSectionLine=%d" % (det_o, rsl_o))

    # G-M2 交付字段
    det_d, rsl_d = set(base["delivered"]["DetectorLoop"]), set(base["delivered"]["RoadSectionLine"])
    gate["G-M2"] = dict(passed=(det_d == EXP_DET_DELIVERED and rsl_d == EXP_RSL_DELIVERED),
                        measured=dict(DetectorLoop=sorted(det_d), RoadSectionLine=sorted(rsl_d)),
                        expect=dict(DetectorLoop=sorted(EXP_DET_DELIVERED),
                                    RoadSectionLine=sorted(EXP_RSL_DELIVERED)))
    say("G-M2 交付字段: DetectorLoop=%s RoadSectionLine=%s" % (sorted(det_d), sorted(rsl_d)))

    # G-M3 填充率
    fill = base["fill"]["RoadSectionLine"]
    ok3 = all(abs(fill.get(k, -1) - v) <= FILL_TOL for k, v in EXP_FILL.items())
    gate["G-M3"] = dict(passed=ok3, measured={k: fill.get(k) for k in EXP_FILL}, expect=EXP_FILL)
    say("G-M3 填充率: %s" % {k: fill.get(k) for k in EXP_FILL})

    # G-M4 文档 ≠ 官方
    dfab = set(base["diff"]["det_doc_only"])
    gate["G-M4"] = dict(passed=(dfab == EXP_DOC_FABRICATED_DET
                                and len(base["diff"]["det_off_only"]) == EXP_DET_OFFICIAL_ONLY_N),
                        measured=dict(det_doc_only=sorted(dfab),
                                      det_off_only=base["diff"]["det_off_only"],
                                      n_det_off_only=len(base["diff"]["det_off_only"]),
                                      rsl_doc_only=base["diff"]["rsl_doc_only"]),
                        expect=dict(det_doc_only=sorted(EXP_DOC_FABRICATED_DET),
                                    n_det_off_only=EXP_DET_OFFICIAL_ONLY_N))
    say("G-M4 文档臆造字段(DetectorLoop)=%s ; 官方独有=%d ; RSL 文档独有=%s"
        % (sorted(dfab), len(base["diff"]["det_off_only"]), base["diff"]["rsl_doc_only"]))

    # G-M5 连接键
    gate["G-M5"] = dict(passed=(base["key_available"] is False and base["name_level_available"] is True),
                        measured=dict(RD_CD_both_sides_usable=base["key_available"],
                                      name_level_usable=base["name_level_available"],
                                      det_RD_CD_fill=base["fill"]["DetectorLoop"].get("RD_CD"),
                                      rsl_RD_CD_fill=fill.get("RD_CD")),
                        expect=dict(RD_CD_both_sides_usable=False, name_level_usable=True))
    say("G-M5 连接键: RD_CD 双侧可用=%s ; 道路名级可用=%s"
        % (base["key_available"], base["name_level_available"]))

    # G-M6 双路径一致
    same6 = set(base["zip_fields"]) == EXP_ZIP_FIELDS
    gate["G-M6"] = dict(passed=same6, measured=dict(zip=base["zip_fields"], static=sorted(det_d)),
                        expect=dict(zip=sorted(EXP_ZIP_FIELDS)))
    say("G-M6 双获取路径: zip=%s static=%s" % (base["zip_fields"], sorted(det_d)))

    # G-M7 M 状态机
    gate["G-M7"] = dict(passed=(base["M"] == EXP_M_STATE), measured=base["M"], expect=EXP_M_STATE)
    say("G-M7 M 门: %s" % base["M"])
    say("TrafficFlow_Data 文档声称=%s ; 实际=%s ; 缺=%s"
        % (base["diff"]["tf_doc_claim"], base["diff"]["tf_actual"], base["diff"]["tf_missing"]))

    # G-M8 负例
    NEG = {
        "N1": dict(inject_detector_id=True),
        "N2": dict(inject_rd_cd=True),
        "N3": dict(key_tier="name"),
        "N4": dict(official_source="dbf"),
        "N5": dict(inject_lane=True),
    }
    neg = {}
    for k, patch in NEG.items():
        pp = dict(BASE)
        pp.update(patch)
        r = compute(pp)
        s = sig(r)
        fired = (s != base_sig)
        hit = observable(r, EXP_NEG[k]) != observable(base, EXP_NEG[k])
        neg[k] = dict(patch=patch, fired=bool(fired), hit_designed_observable=bool(hit),
                      sig_pre=s, sig_post=s,
                      observable_target=EXP_NEG[k],
                      before=observable(base, EXP_NEG[k]), after=observable(r, EXP_NEG[k]))
        say("%s fired=%s hit=%s  %s: %s -> %s" % (k, fired, hit, EXP_NEG[k],
                                                  observable(base, EXP_NEG[k]), observable(r, EXP_NEG[k])))
    gate["G-M8"] = dict(passed=all(v["fired"] and v["hit_designed_observable"] for v in neg.values()),
                        measured=neg, expect=EXP_NEG)

    # G-M9 AST 自检
    src = Path(__file__).read_text(encoding="utf-8")
    tree = ast.parse(src)
    banned = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and node.id in ("random", "time", "datetime", "np"):
            banned.append(node.id)
        if isinstance(node, ast.Attribute) and node.attr in ("random", "now", "today", "shuffle"):
            banned.append("attr:" + node.attr)
    gate["G-M9"] = dict(passed=(len(banned) == 0), measured=dict(banned=sorted(set(banned))),
                        expect=dict(banned=[]))
    say("G-M9 AST 无随机源: %s" % (sorted(set(banned)) or "OK"))

    # ---- 写盘 ----
    # 1) 三方对账
    rows = []
    for layer, off, deliv, doc in (
            ("DetectorLoop", set(base["official"]["DetectorLoop"]), det_d, set(base["doc"]["DetectorLoop"])),
            ("RoadSectionLine", set(base["official"]["RoadSectionLine"]), rsl_d, set(base["doc"]["RoadSectionLine"]))):
        for f in sorted(off | deliv | doc | IMPLICIT):
            rows.append(dict(layer=layer, field=f,
                             in_official=int(f in off), in_delivered=int(f in deliv),
                             in_doc=int(f in doc), implicit=int(f in IMPLICIT),
                             status=("IMPLICIT" if f in IMPLICIT else
                                     "BOTH" if f in off and f in deliv else
                                     "OFFICIAL_ONLY" if f in off else
                                     "DELIVERED_ONLY" if f in deliv else "DOC_ONLY")))
    for f in sorted(set(base["doc"]["TrafficFlow_Data"]) | set(base["diff"]["tf_actual"])):
        rows.append(dict(layer="TrafficFlow_Data", field=f,
                         in_official=int(f in base["diff"]["tf_actual"]),
                         in_delivered=int(f in base["diff"]["tf_actual"]),
                         in_doc=int(f in set(base["doc"]["TrafficFlow_Data"])), implicit=0,
                         status=("BOTH" if f in base["diff"]["tf_actual"] and f in set(base["doc"]["TrafficFlow_Data"])
                                 else "DELIVERED_ONLY" if f in base["diff"]["tf_actual"] else "DOC_ONLY")))
    p1 = OUT / "o3m_schema_reconciliation.csv"
    with open(p1, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=["layer", "field", "in_official", "in_delivered",
                                           "in_doc", "implicit", "status"])
        w.writeheader()
        w.writerows(rows)

    # 2) 填充率
    p2 = OUT / "o3m_field_fill.csv"
    with open(p2, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["layer", "field", "n_records", "fill_frac"])
        for layer, n in (("DetectorLoop", base["counts"]["det_n"]),
                         ("RoadSectionLine", base["counts"]["rsl_n"])):
            for f, v in base["fill"][layer].items():
                w.writerow([layer, f, n, "%.6f" % v])

    # 3) M 门 + 硬门
    verdict = "O3_METADATA_AUDIT_CLOSED" if all(g["passed"] for g in gate.values()) else "O3_METADATA_AUDIT_FAILED"
    payload = dict(step="7.9I-O3-METADATA", verdict=verdict,
                   n_gates=len(gate), n_pass=sum(1 for g in gate.values() if g["passed"]),
                   state_in="7.9I_FROZEN_CLOSED → … → D2-review ✓ → O3 ✓",
                   state_out="O3 ✓ → READY(O3-METADATA) → METADATA_GAP_QUANTIFIED",
                   M_gates=base["M"], M_expect=EXP_M_STATE,
                   key_available=base["key_available"], name_level_available=base["name_level_available"],
                   official=base["official"], delivered=base["delivered"], zip_fields=base["zip_fields"],
                   fill=base["fill"], doc=base["doc"], diff=base["diff"], counts=base["counts"],
                   gates=gate, sig_base=base_sig, negatives=neg,
                   acquisition_targets=[
                       dict(priority=1, item="属性完整版 DetectorLoop（LTA 公开 geospatial）",
                            fields=base["official"]["DetectorLoop"],
                            caveat="即使成功也不含 DETECTOR_ID ⇒ 只能到 RD_CD 道路码级"),
                       dict(priority=2, item="On-Request Indicative Traffic Counts at Junctions by Loop Detectors",
                            fields=["Junction ID", "Detector ID", "Date and time", "Indicative traffic counts"],
                            caveat="DETECTOR_ID 的唯一可能来源；与 LinkID 可连接性须到手后实测，不预设"),
                   ],
                   boundary_frozen=["B=BINDING_UNDECIDABLE 不升级", "TWIN_GEOMETRIC_SUBSTITUTE 仅几何证据",
                                    "F_LOW ≠ 需求不足", "v1.0 冻结", "signals/trafficDynamics/speedFactor 不碰",
                                    "零仿真、不改模型、不改评价器"],
                   note="本节点不产生 F_LOW 成因新结论；只更新「缺什么、从哪补」")
    p3 = OUT / "o3m_m_gates.json"
    p3.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    say("")
    say("verdict = %s   gates=%d/%d" % (verdict, payload["n_pass"], payload["n_gates"]))
    say("sig_base = %s" % (base_sig,))
    for f in (p1, p2, p3):
        say("  wrote %s (%d B)" % (f.name, f.stat().st_size))
    (OUT / "_run_7_9io3m.log").write_text("\n".join(log) + "\n", encoding="utf-8")
    return 0 if verdict.endswith("CLOSED") else 1


if __name__ == "__main__":
    raise SystemExit(main())
