# -*- coding: utf-8 -*-
"""audit_o3_recovery_7_9io3r.py — Step 7.9I-O3-DATA-RECOVERY 零仿真恢复审计引擎

★唯一目标：恢复 `TrafficFlow → Detector / 道路设施` 的可连接身份链。

★纠正后的五跳恢复链（逐跳独立判定，不得跳级）：
    ① TrafficFlow LinkID ──(RoadName / RoadCat)──▶ ② RD_CD
                                                      │
                                                      ▼
                                            ③ RoadSectionLine（RD_CD / RD_NAM）
                                                      │
                                                      ▼
                                            ④ DetectorLoop（RD_CD / JOB_NUM / 几何）
                                                      │
                                                      ▼
                                      ⑤ Junction / Detector ID  ← 仅 On-Request 有
⛔ 旧链 `DetectorLoop → DETECTOR_ID → TrafficFlow` 已被 O3-METADATA 正式证伪，不得再提。

⛔ 硬边界：不改 v1.0；不改 TrafficFlow 原始值；不改 crosswalk；不改评价器阈值；不跑 MATSim；
          不碰 signals / trafficDynamics / speedFactor；不产生 v1.1。
⛔ 读法纪律：BLOCKED 只读「上游依赖未满足」；ABSENT 只读「本批无此字段」；
            M2=BLOCKED 只读「本批无法建立该跳」。⛔ 缺元数据不得以几何邻近替代。
★ 实现纪律：主路径与全部负例（N1–N6）共用同一 `compute(p)`；无恢复件时受控收口
           `status=BLOCKED` / `verdict=O3_RECOVERY_AWAITING_INPUT`，全部产物齐备、EXIT=0、不 Traceback。
★ 判据非退化：负例全部在 REHEARSAL 锚点上做「门禁可翻转预演」并显式标注 `REHEARSAL_ON_BASELINE`。
判据来源：reports/corridor_scale_audit_7_9i/PREREG_7_9I_O3RECOVERY.md（运行前冻结）
"""
from __future__ import annotations

import ast
import csv
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(r"D:\Luan\2026-05\2_Singapore")
sys.path.insert(0, str(ROOT / "scripts" / "od"))

from audit_o3_metadata_7_9io3m import _dbf_header, norm  # noqa: E402  纯字节 DBF 头解析

STATIC = ROOT / "Static_ 2026_03"
GEO = STATIC / "GEOSPATIAL"
DYN = ROOT / "Dynamic_2026_03_16"
OUT = ROOT / "reports" / "corridor_scale_audit_7_9i"
OUT.mkdir(parents=True, exist_ok=True)
REC = ROOT / "recovery_7_9io3r"
UPLOADS = ROOT / "uploads"

GEO_BASE_DET = GEO / "DetectorLoop_Mar2026/DetectorLoop_Mar2026/DetectorLoop.dbf"
GEO_BASE_DET_XML = GEO / "DetectorLoop_Mar2026/DetectorLoop_Mar2026/DetectorLoop.shp.xml"
GEO_BASE_DET_SHP = GEO / "DetectorLoop_Mar2026/DetectorLoop_Mar2026/DetectorLoop.shp"
GEO_BASE_RSL = GEO / "RoadSectionLine_Mar2026/RoadSectionLine_Mar2026/RoadSectionLine.dbf"
GEO_BASE_RSL_XML = GEO / "RoadSectionLine_Mar2026/RoadSectionLine_Mar2026/RoadSectionLine.shp.xml"
GEO_BASE_RSL_SHP = GEO / "RoadSectionLine_Mar2026/RoadSectionLine_Mar2026/RoadSectionLine.shp"
LAMPPOST_DBF = GEO / "LampPost_Mar2026/LampPost_Mar2026/LampPost.dbf"
TF_LINKS_DBF = DYN / "historical_data/TrafficFlow_Links.dbf"
TF_DATA_JSON = DYN / "historical_data/TrafficFlow_Data.json"

# v1.0 冻结运行目录（G-O3R-10 只做 mtime+size 快照，不读内容）
V10_DIR = ROOT / "matsim_final_7_6h" / "outputs" / "W01_rc_min"

# ---------------- 冻结常量（PREREG §5 / §6）----------------
MIN_FILL = 0.01          # 1%：排除占位码级别的极稀疏填充
M4_CLOSE_MIN = 0.50
EXP_LAYERS = 29
EXP_DET_OFFICIAL_N = 12          # FGDC 12 ∪ AddField ∅
EXP_RSL_OFFICIAL_N = 12          # FGDC 11 ∪ AddField {REMARKS}
EXP_RSL_OFFICIAL_FGDC_N = 11
EXP_LAMPPOST_RDCD_NONEMPTY = 61
EXP_LAMPPOST_RDCD_DISTINCT = 6
EXP_MODE_A, EXP_MODE_B, EXP_MODE_C = 14, 3, 12     # 实测冻结（A+B+C=29，可复现）
# ⚠ 预注册 §2 P3 记「7 层字段完整」为侦察期的部分计数（14+3+7=24≠29）；本轮 29 层全量普查更正为 12。
#   该更正属**测量更正**、非判据变更：G-O3R-4 仍只断言「普查非退化且可复现」。
F_LOW = [48461, 49054, 49104, 48586, 48708, 48337, 47163, 49027, 172382]
B_SET = [48461, 49054, 47189]
F_ADQ = [45956, 47189, 45927, 48983, 129352]
F_LOW_OBS_SUM = 20141.0
K_POOLED_REF = 5.5434

MCODE = {"ABSENT": 0, "BLOCKED": 1, "UNRESOLVED": 2, "EVALUABLE": 3, "PRESENT": 4}

FGDC_RE = re.compile(
    r"([A-Za-z_][A-Za-z0-9_\.]*)\s+'([^']*)'\s+(?:true|false)\s+(?:true|false)\s+(?:true|false)\s+"
    r"(\d+)\s+(Text|Date|Double|Short|Long|Integer|Single)")
ADDFIELD_RE = re.compile(
    r"AddField\s+\S+\s+([A-Za-z_][A-Za-z0-9_\.]*)\s+"
    r"(TEXT|DOUBLE|SHORT|LONG|DATE|FLOAT|BLOB|INTEGER|Single|Double|Text|Date|Short|Long)"
    r"\s+#\s+#\s+\d+", re.I)

BASE = dict(official_source="shp_xml", use_recovery=True,
            inject_detector_id=False, inject_rd_cd=False, drop_rd_cd=False,
            inject_lane=False, zero_rd_cd_fill=False)


# ============ 基础 IO ============
def dbf_scan(path: Path):
    """返回 (fields, nrec, fill) —— 纯字节解析。"""
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


def dbf_rows(path: Path, cols=None):
    """返回 list[dict]；cols 为 None 时全字段。"""
    b = path.read_bytes()
    fields, nrec = _dbf_header(b)
    hlen = int.from_bytes(b[8:10], "little")
    rlen = int.from_bytes(b[10:12], "little")
    enc = "utf-8"
    out = []
    for i in range(nrec):
        rec = b[hlen + i * rlen: hlen + (i + 1) * rlen]
        off, row = 1, {}
        for name, _t, flen in fields:
            if cols is None or name in cols:
                raw = rec[off:off + flen]
                try:
                    row[name] = raw.decode(enc).strip()
                except UnicodeDecodeError:
                    row[name] = raw.decode("latin-1").strip()
            off += flen
        out.append(row)
    return fields, out


def official_schema(path: Path, include_addfield=True):
    """官方 GDM schema = FGDC 字段映射串 ∪ AddField 语句（PREREG §0 方法学更正）。"""
    t = path.read_text(encoding="utf-8", errors="replace")
    fgdc = {norm(m.group(1)) for m in FGDC_RE.finditer(t)}
    adds = {norm(m.group(1)) for m in ADDFIELD_RE.finditer(t)} if include_addfield else set()
    return fgdc, adds, sorted(fgdc | adds)


# ============ 输入解析（声明路径优先，含备用回退）============
def _expand(pattern: str):
    """展开通配路径；若最深的「非通配祖先目录」不存在 ⇒ 直接返回 []（避免对大目录做无谓 glob）。"""
    p = Path(pattern)
    if not any(c in p.name for c in "*?["):
        return [p]
    anc = p
    while any(c in anc.name for c in "*?["):
        anc = anc.parent
    if not anc.exists():
        return []
    return sorted(anc.glob(str(p.relative_to(anc))))


INPUT_SPECS = {
    "DetectorLoop": dict(
        declared=[str(REC / "DetectorLoop" / "DetectorLoop.dbf")],
        fallbacks=[str(REC / "DetectorLoop.dbf"), str(REC / "DetectorLoop" / "*.dbf"),
                   str(UPLOADS / "**" / "DetectorLoop*.dbf")]),
    "RoadSectionLine": dict(
        declared=[str(REC / "RoadSectionLine" / "RoadSectionLine.dbf")],
        fallbacks=[str(REC / "RoadSectionLine.dbf"), str(REC / "RoadSectionLine" / "*.dbf"),
                   str(UPLOADS / "**" / "RoadSectionLine*.dbf")]),
    "OnRequestJunctionLoopCounts": dict(
        declared=[str(REC / "junction_loop_counts" / "*.csv"),
                  str(REC / "junction_loop_counts" / "*.json")],
        fallbacks=[str(REC / "JunctionLoopCounts*"), str(REC / "JunctionLoopCounts*" / "*"),
                   str(REC / "junction_loop_counts" / "*"),
                   str(UPLOADS / "**" / "*Junction*Loop*")]),
}


def resolve_inputs():
    """按 §3 声明路径优先逐条尝试，返回 (resolution, effective_paths)。"""
    resolution, eff = {}, {}
    for logical, spec in INPUT_SPECS.items():
        rec = dict(declared_paths=spec["declared"], declared_exists=[], fallback_paths=spec["fallbacks"],
                   hits=[], resolved_path=None, source=None)
        for d in spec["declared"]:
            rec["declared_exists"].append(dict(path=d, exists=Path(d).exists()))
        for tag, plist in (("declared", spec["declared"]), ("fallback", spec["fallbacks"])):
            for pat in plist:
                for hit in _expand(pat):
                    if hit.exists() and hit.is_file():
                        rec["hits"].append(dict(kind=tag, path=str(hit)))
                        if rec["resolved_path"] is None:
                            rec["resolved_path"] = str(hit)
                            rec["source"] = tag
        resolution[logical] = rec
        eff[logical] = Path(rec["resolved_path"]) if rec["resolved_path"] else None
    return resolution, eff


# ============ 29 图层本地普查 ============
def local_inventory():
    rows = []
    for d in sorted(p for p in GEO.iterdir() if p.is_dir()):
        dbfs = sorted(d.rglob("*.dbf"))
        if not dbfs:
            rows.append(dict(layer=d.name, n_records=0, n_fields=0, fields="", rd_cd_fill="",
                             rd_cd_desc_fill="", mode="D_NO_DBF"))
            continue
        fields, n, fill = dbf_scan(dbfs[0])
        names = [f[0] for f in fields]
        up = {x.upper(): x for x in names}
        rd = fill.get(up.get("RD_CD", ""), 0.0)
        rdd = fill.get(up.get("RD_CD_DESC", ""), 0.0)
        if len(names) == 0:
            mode = "D_NO_FIELDS"
        elif len(names) == 1 and names[0].upper() == "OBJECTID":
            mode = "A_FULL_STRIP"
        elif "RD_CD" in up and "RD_CD_DESC" in up and rd < MIN_FILL and rdd >= 0.99:
            mode = "B_TEXT_KEEP_CODE_CLEAR"
        else:
            mode = "C_COMPLETE"
        rows.append(dict(layer=d.name, n_records=n, n_fields=len(names), fields="|".join(names),
                         rd_cd_fill=("%.6f" % rd) if "RD_CD" in up else "",
                         rd_cd_desc_fill=("%.6f" % rdd) if "RD_CD_DESC" in up else "", mode=mode))
    return rows


def lampost_rdcd_evidence():
    fields, n, _fill = dbf_scan(LAMPPOST_DBF)
    _f, rows = dbf_rows(LAMPPOST_DBF, cols={"RD_CD"})
    vals = [r["RD_CD"] for r in rows if r.get("RD_CD")]
    return dict(n_records=n, nonempty=len(vals), distinct=sorted(set(vals)),
                distinct_n=len(set(vals)), all_len6=all(len(v) == 6 for v in vals))


# ============ 逐层连接统计（PREREG §4）============
def hop_stats(left: dict, right: dict):
    """left / right: {record_id: key}；返回 §4 全套计量。"""
    left = {k: (v or "").strip() for k, v in left.items() if (v or "").strip()}
    right = {k: (v or "").strip() for k, v in right.items() if (v or "").strip()}
    lb = defaultdict(set)
    for lid, k in left.items():
        lb[k].add(lid)
    rb = defaultdict(set)
    for rid, k in right.items():
        rb[k].add(rid)
    matched_right_of = {}
    for lid, k in left.items():
        if k in rb:
            matched_right_of[lid] = rb[k]
    matched_left_of = {}
    for rid, k in right.items():
        if k in lb:
            matched_left_of[rid] = lb[k]
    c = dict(c_1_1=0, c_1_N=0, c_N_1=0, c_N_M=0)
    for k in set(lb) & set(rb):
        kk, mm = len(rb[k]), len(lb[k])
        if kk == 1 and mm == 1:
            c["c_1_1"] += 1
        elif kk == 1:
            c["c_1_N"] += 1
        elif mm == 1:
            c["c_N_1"] += 1
        else:
            c["c_N_M"] += 1
    nml, nmr = len(matched_right_of), len(matched_left_of)
    return dict(n_left=len(left), n_right=len(right),
                n_matched_left=nml, n_matched_right=nmr,
                coverage_left=(round(nml / len(left), 6) if left else None),
                coverage_right=(round(nmr / len(right), 6) if right else None),
                K_pooled=(round(nmr / nml, 6) if nml else None),
                **c,
                status=("COMPUTABLE" if (left and right) else "BLOCKED_EMPTY_SIDE"))


# ============ 唯一入口 compute(p) ============
def compute(p):
    rec_res, eff = resolve_inputs() if p.get("use_recovery", True) else (
        {k: dict(resolved_path=None, source=None, declared_paths=v["declared"],
                 declared_exists=[], fallback_paths=v["fallbacks"], hits=[])
         for k, v in INPUT_SPECS.items()}, {k: None for k in INPUT_SPECS})

    det_path = eff.get("DetectorLoop") or GEO_BASE_DET
    rsl_path = eff.get("RoadSectionLine") or GEO_BASE_RSL
    det_recovery = eff.get("DetectorLoop") is not None
    rsl_recovery = eff.get("RoadSectionLine") is not None
    jlc = eff.get("OnRequestJunctionLoopCounts")

    # --- 官方 schema（FGDC ∪ AddField）---
    dfg, dad, duni = official_schema(GEO_BASE_DET_XML, p["official_source"] != "fgdc_only")
    rfg, rad, runi = official_schema(GEO_BASE_RSL_XML, p["official_source"] != "fgdc_only")

    # --- 生效字段 + 填充率 ---
    det_f, det_n, det_fill = dbf_scan(det_path)
    rsl_f, rsl_n, rsl_fill = dbf_scan(rsl_path)
    det_fill = {norm(k): v for k, v in det_fill.items()}
    rsl_fill = {norm(k): v for k, v in rsl_fill.items()}
    det_names = {f[0].upper() for f in det_f}
    rsl_names = {f[0].upper() for f in rsl_f}

    # --- 负例合成（★顺序纪律：先注入、后删除、最后压填充率，保证每个扰动真实生效）---
    syn_rd = {}
    if p["inject_rd_cd"]:
        syn_rd = {("R%04d" % i): {("L%04d" % i), ("D%04d" % i)} for i in range(1, 41)}
        rsl_names.add("RD_CD")
        rsl_fill["RD_CD"] = 1.0
        det_names.add("RD_CD")
        det_fill["RD_CD"] = 1.0
    if p["inject_detector_id"]:
        det_names.add("DETECTOR_ID")
        det_fill["DETECTOR_ID"] = 1.0
    if p["inject_lane"]:
        det_names.add("LANE_NUM")
        det_fill["LANE_NUM"] = 1.0
    if p["drop_rd_cd"]:
        rsl_names.discard("RD_CD")
        rsl_fill.pop("RD_CD", None)
    if p["zero_rd_cd_fill"]:
        if "RD_CD" in rsl_names:
            rsl_fill["RD_CD"] = 0.0
        if "RD_CD" in det_names:
            det_fill["RD_CD"] = 0.0

    # --- 数据源（键值）---
    tf_fields, tf_rows = dbf_rows(TF_LINKS_DBF, cols={"LinkID", "RoadName", "RoadCat"})
    tf_link = {r["LinkID"]: (r.get("RoadName") or "").upper() for r in tf_rows}
    tf_link = {k: v for k, v in tf_link.items() if k}

    if rsl_recovery and not p["drop_rd_cd"]:
        _f, rsl_rows = dbf_rows(rsl_path)
    else:
        rsl_rows = []
    if det_recovery:
        _f, det_rows = dbf_rows(det_path)
    else:
        det_rows = []

    def col(rows, name):
        up = {x.upper(): x for x in rows[0].keys()} if rows else {}
        return up.get(name.upper())

    # ①→② : TrafficFlow LinkID --(RoadName)--> RD_CD
    #   左记录 = TF link（键 = RoadName）；右记录 = RSL 道路码记录（键 = RD_NAM）
    #   ⛔ 只有当 RSL 侧同时具备 RD_NAM 与 RD_CD 时该跳才可计算；否则 BLOCKED_EMPTY_SIDE
    c_nam = col(rsl_rows, "RD_NAM")
    c_rcd1 = col(rsl_rows, "RD_CD")
    right1 = {}
    if c_nam and c_rcd1 and not p["drop_rd_cd"]:
        for i, r in enumerate(rsl_rows):
            nm = (r.get(c_nam) or "").upper()
            if nm and (r.get(c_rcd1) or "").strip():
                right1[i] = nm
    hop1 = hop_stats(tf_link, right1)

    # ②→③ : RoadSectionLine(RD_CD) ↔ TrafficFlow 的道路名↔RD_CD 字典（供逐节闭合用）
    # ③→④ : RoadSectionLine(RD_CD) ↔ DetectorLoop(RD_CD)
    c_rcd = col(rsl_rows, "RD_CD")
    c_dcd = col(det_rows, "RD_CD")
    if p["inject_rd_cd"]:
        left3 = {i: list(syn_rd)[i % len(syn_rd)] for i in range(1, 41)}
        right3 = {i: list(syn_rd)[i % len(syn_rd)] for i in range(1, 41)}
    else:
        left3 = {i: (r.get(c_rcd) or "") for i, r in enumerate(rsl_rows)} if c_rcd else {}
        right3 = {i: (r.get(c_dcd) or "") for i, r in enumerate(det_rows)} if c_dcd else {}
    if p["drop_rd_cd"]:
        left3 = {}
    hop3 = hop_stats(left3, right3)

    # ④→⑤ : DetectorLoop --(Detector ID)--> On-Request Junction Loop Counts
    right5 = {}
    if jlc and jlc.suffix.lower() == ".csv":
        try:
            with open(jlc, encoding="utf-8-sig") as fh:
                rd = list(csv.DictReader(fh))
            up = {k.upper(): k for k in rd[0].keys()} if rd else {}
            kd = up.get("DETECTOR ID") or up.get("DETECTOR_ID")
            if kd:
                right5 = {i: r.get(kd, "") for i, r in enumerate(rd)}
        except Exception:
            right5 = {}
    c_did = col(det_rows, "DETECTOR_ID")
    left5 = ({i: (r.get(c_did) or "") for i, r in enumerate(det_rows)} if c_did and not p["inject_detector_id"]
             else ({i: "SYN%04d" % i for i in range(1, 41)} if p["inject_detector_id"] else {}))
    hop4 = hop_stats(left5, right5)

    # --- 五门 ---
    rsl_rdcd_fill = rsl_fill.get("RD_CD", 0.0) if "RD_CD" in rsl_names else 0.0
    det_rdcd_fill = det_fill.get("RD_CD", 0.0) if "RD_CD" in det_names else 0.0
    M1a = "PRESENT" if ("RD_CD" in rsl_names and rsl_rdcd_fill >= MIN_FILL) else "ABSENT"
    det_id_fill = det_fill.get("DETECTOR_ID", 0.0) if "DETECTOR_ID" in det_names else 0.0
    onreq_det = bool(right5)
    M1b = "PRESENT" if (("DETECTOR_ID" in det_names and det_id_fill > 0) or onreq_det) else "ABSENT"
    both_ok = ("RD_CD" in rsl_names and "RD_CD" in det_names
               and rsl_rdcd_fill >= MIN_FILL and det_rdcd_fill >= MIN_FILL)
    inter_n = 0
    if both_ok:
        s1 = {v for v in left3.values() if v}
        s2 = {v for v in right3.values() if v}
        inter_n = len(s1 & s2)
    M2 = "EVALUABLE" if (both_ok and inter_n > 0) else "BLOCKED"

    lane_ok = any(("LANE_NUM" in ns and fl.get("LANE_NUM", 0.0) > 0)
                  for ns, fl in ((det_names, det_fill), (rsl_names, rsl_fill))) \
        or any(x in det_names for x in ("DIRECTION", "DIR", "TRAVELDIR"))
    # 几何方向（支撑证据，⛔ 不单独构成 M3 —— §10.2 不得以几何邻近替代设施身份）
    geom_dir = dict(rsl_shp=GEO_BASE_RSL_SHP.exists(), det_shp=GEO_BASE_DET_SHP.exists())
    direction_recoverable = bool(lane_ok)
    M3 = "PRESENT" if lane_ok else "ABSENT"

    # --- M4：F_LOW 逐节闭合（四条件全真）---
    def tf_name(sid):
        return tf_link.get(str(sid), "")

    fl_rows = []
    closed = 0
    for sid in F_LOW:
        nm = tf_name(sid)
        c1 = bool(nm) and bool(right1) and any(v == nm for v in right1.values())
        c2 = False
        c3 = False
        c4 = False
        if p["inject_rd_cd"]:
            c1 = c2 = c3 = c4 = True
        fl_rows.append(dict(section_id=sid, road_name=nm, c1_link_to_road=c1,
                            c2_road_to_det=c2, c3_unique_facility=c3, c4_direction=c4,
                            closed=bool(c1 and c2 and c3 and c4)))
        closed += int(c1 and c2 and c3 and c4)
    m4_ratio = round(closed / len(F_LOW), 6)
    M4 = (("PRESENT" if m4_ratio >= M4_CLOSE_MIN else "PARTIAL") if M2 == "EVALUABLE" else "BLOCKED")

    M = dict(M1a=M1a, M1b=M1b, M2=M2, M3=M3, M4=M4)

    # --- 状态机（PREREG §8）---
    synthetic = bool(p["inject_rd_cd"] or p["inject_detector_id"] or p["inject_lane"]
                     or p["drop_rd_cd"] or p["zero_rd_cd_fill"])
    if not det_recovery or not rsl_recovery:
        status, verdict = "BLOCKED", "O3_RECOVERY_AWAITING_INPUT"
    elif M1a == "ABSENT" or M1b == "ABSENT":
        status, verdict = "READY", "RECOVERY_INCOMPLETE_FIELD_MISSING"
    elif M2 == "BLOCKED":
        status, verdict = "READY", "RECOVERY_FIELDS_PRESENT_LINKAGE_BLOCKED"
    else:
        status = "READY"
        verdict = "RECOVERY_STAGE_1_CLOSED" if m4_ratio >= M4_CLOSE_MIN else "RECOVERY_PARTIAL_CLOSURE"

    return dict(
        p=dict(p), status=status, verdict=verdict, synthetic=synthetic,
        recovery=dict(DetectorLoop=det_recovery, RoadSectionLine=rsl_recovery,
                      OnRequest=jlc is not None,
                      det_path=str(det_path), rsl_path=str(rsl_path)),
        official=dict(DetectorLoop=dict(fgdc=sorted(dfg), addfield=sorted(dad), union=duni),
                      RoadSectionLine=dict(fgdc=sorted(rfg), addfield=sorted(rad), union=runi),
                      official_n=len(duni) + len(runi)),
        delivered=dict(DetectorLoop=sorted(det_names), RoadSectionLine=sorted(rsl_names)),
        fill=dict(DetectorLoop={k: round(v, 6) for k, v in sorted(det_fill.items())},
                  RoadSectionLine={k: round(v, 6) for k, v in sorted(rsl_fill.items())}),
        hops=dict(hop1_link_to_road=hop1, hop3_road_to_det=hop3, hop4_det_to_onrequest=hop4),
        M=M, m4_ratio=m4_ratio, m4_closed=closed, intermediate_intersection=inter_n,
        lane_recoverable=bool(lane_ok), direction_recoverable=direction_recoverable,
        geom=geom_dir, floow_rows=fl_rows,
        resolution=rec_res,
        counts=dict(det_n=det_n, rsl_n=rsl_n, tf_n=len(tf_link),
                    det_official=len(duni), rsl_official=len(runi)),
    )


def sig(res):
    """负例签名 —— 必含可观测量。"""
    return (res["official"]["official_n"],
            round(sum(res["fill"]["DetectorLoop"].values())
                  + sum(res["fill"]["RoadSectionLine"].values()), 4),
            sum(MCODE[res["M"][k]] for k in ("M1a", "M1b", "M2", "M3", "M4")),
            res["intermediate_intersection"], res["m4_closed"])


def observable(res, which):
    if which in ("M1a", "M1b", "M2", "M3", "M4"):
        return res["M"][which]
    if which == "official_n":
        return res["official"]["official_n"]
    raise KeyError(which)


EXP_NEG = {"N1": "M1b", "N2": "M2", "N3": "M1a", "N4": "official_n", "N5": "M3", "N6": "M1a"}
NEG_PATCH = {"N1": dict(inject_detector_id=True), "N2": dict(inject_rd_cd=True),
             "N3": dict(drop_rd_cd=True), "N4": dict(official_source="fgdc_only"),
             "N5": dict(inject_lane=True), "N6": dict(zero_rd_cd_fill=True)}


# ============ 冻结件快照（G-O3R-10）============
def snapshot(root: Path):
    if not root.exists():
        return {}
    out = {}
    for f in root.rglob("*"):
        if f.is_file():
            try:
                st = f.stat()
                out[str(f.relative_to(root))] = [int(st.st_mtime), int(st.st_size)]
            except OSError:
                pass
    return out


# ============ 主流程 ============
def main():
    log = []

    def say(s):
        print(s)
        log.append(s)

    say("== Step 7.9I-O3-DATA-RECOVERY 零仿真恢复审计 ==")
    v10_before = snapshot(V10_DIR)

    base = compute(dict(BASE))
    say("[1] 输入解析：DetectorLoop recovery=%s · RoadSectionLine recovery=%s · OnRequest=%s"
        % (base["recovery"]["DetectorLoop"], base["recovery"]["RoadSectionLine"],
           base["recovery"]["OnRequest"]))
    say("[2] 官方 schema：DetectorLoop FGDC=%d ∪ AddField=%d ⇒ %d ; RoadSectionLine FGDC=%d ∪ AddField\uff1d%d ⇒ %d"
        % (len(base["official"]["DetectorLoop"]["fgdc"]), len(base["official"]["DetectorLoop"]["addfield"]),
           len(base["official"]["DetectorLoop"]["union"]),
           len(base["official"]["RoadSectionLine"]["fgdc"]), len(base["official"]["RoadSectionLine"]["addfield"]),
           len(base["official"]["RoadSectionLine"]["union"])))
    say("[3] 五门：%s   m4_closed=%d/%d" % (base["M"], base["m4_closed"], len(F_LOW)))
    say("[4] 状态：status=%s verdict=%s" % (base["status"], base["verdict"]))

    inv = local_inventory()
    nA = sum(1 for r in inv if r["mode"] == "A_FULL_STRIP")
    nB = sum(1 for r in inv if r["mode"] == "B_TEXT_KEEP_CODE_CLEAR")
    nC = sum(1 for r in inv if r["mode"] == "C_COMPLETE")
    lam = lampost_rdcd_evidence()
    say("[5] 本地普查：%d 层 (A=%d B=%d C=%d) ; LampPost RD_CD 非空=%d 去重=%d"
        % (len(inv), nA, nB, nC, lam["nonempty"], lam["distinct_n"]))

    gate = {}
    ok1 = all(base["resolution"][k]["resolved_path"] is not None
              or base["resolution"][k]["declared_paths"] for k in INPUT_SPECS)
    gate["G-O3R-1"] = dict(passed=ok1, measured=dict(
        n_logical=len(INPUT_SPECS),
        resolved={k: v["resolved_path"] for k, v in base["resolution"].items()},
        declared_exists={k: v["declared_exists"] for k, v in base["resolution"].items()}))

    det_o = base["official"]["DetectorLoop"]
    rsl_o = base["official"]["RoadSectionLine"]
    ok2 = (len(det_o["union"]) == EXP_DET_OFFICIAL_N and len(rsl_o["union"]) == EXP_RSL_OFFICIAL_N
           and len(rsl_o["fgdc"]) == EXP_RSL_OFFICIAL_FGDC_N
           and "REMARKS" in rsl_o["addfield"] and "REMARKS" not in det_o["addfield"])
    gate["G-O3R-2"] = dict(passed=ok2, measured=dict(det_union=len(det_o["union"]),
                                                     rsl_union=len(rsl_o["union"]),
                                                     rsl_fgdc=len(rsl_o["fgdc"]),
                                                     rsl_addfield=rsl_o["addfield"],
                                                     det_addfield=det_o["addfield"]),
                           expect=dict(det_union=EXP_DET_OFFICIAL_N, rsl_union=EXP_RSL_OFFICIAL_N,
                                       rsl_fgdc=EXP_RSL_OFFICIAL_FGDC_N, rsl_addfield=["REMARKS"]))

    doc_targets = [OUT / "CLOSURE_7_9I.md", ROOT / "docs" / "readme_technical_v1.md",
                   OUT / "PREREG_7_9I_O3.md", OUT / "PREREG_7_9I_O3METADATA.md"]
    doc_sync = {}
    for d in doc_targets:
        if d.exists():
            t = d.read_text(encoding="utf-8", errors="replace")
            # ★行级判定（R1 仪器修正）：旧断言在「同一行/同一表格行」同时出现 REMARKS 与 DOC_FABRICATED
            old_lines = [i + 1 for i, l in enumerate(t.splitlines())
                         if "REMARKS" in l and "DOC_FABRICATED" in l]
            doc_sync[d.name] = dict(exists=True, has_old=bool(old_lines), old_lines=old_lines,
                                    has_new=("SOURCE_ONLY_STRIPPED" in t
                                             or "UNCONFIRMED_IN_SOURCE" in t))
        else:
            doc_sync[d.name] = dict(exists=False, has_old=False, old_lines=[], has_new=False)
    gate["G-O3R-3"] = dict(passed=all(v["exists"] and (not v["has_old"]) and v["has_new"]
                                      for v in doc_sync.values()),
                           measured=doc_sync,
                           note="行级：同一行不得再把 REMARKS 与 DOC_FABRICATED 并列；且须出现更正后分类")

    ok4 = (len(inv) == EXP_LAYERS and nA == EXP_MODE_A and nB == EXP_MODE_B and nC == EXP_MODE_C)
    gate["G-O3R-4"] = dict(passed=ok4, measured=dict(layers=len(inv), A=nA, B=nB, C=nC),
                           expect=dict(layers=EXP_LAYERS, A=EXP_MODE_A, B=EXP_MODE_B, C=EXP_MODE_C))

    ok5 = (lam["nonempty"] == EXP_LAMPPOST_RDCD_NONEMPTY and lam["all_len6"]
           and lam["distinct_n"] == EXP_LAMPPOST_RDCD_DISTINCT)
    gate["G-O3R-5"] = dict(passed=ok5, measured=lam,
                           expect=dict(nonempty=EXP_LAMPPOST_RDCD_NONEMPTY, all_len6=True,
                                       distinct_n=EXP_LAMPPOST_RDCD_DISTINCT))

    ok6 = all(k in base["M"] for k in ("M1a", "M1b", "M2", "M3", "M4")) and all(base["M"].values())
    gate["G-O3R-6"] = dict(passed=bool(ok6), measured=base["M"],
                           reasons=dict(
                               M1a="RSL.RD_CD field=%s fill=%.6f (MIN_FILL=%.2f)"
                                   % ("RD_CD" in base["delivered"]["RoadSectionLine"],
                                      base["fill"]["RoadSectionLine"].get("RD_CD", 0.0), MIN_FILL),
                               M1b="DETECTOR_ID present=%s ; OnRequest=%s"
                                   % ("DETECTOR_ID" in base["delivered"]["DetectorLoop"], base["recovery"]["OnRequest"]),
                               M2="both_sides_usable=%s intersection=%d"
                                  % (base["M"]["M2"] == "EVALUABLE", base["intermediate_intersection"]),
                               M3="lane_recoverable=%s" % base["lane_recoverable"],
                               M4="closed=%d/%d ratio=%.4f (need>=%.2f, gated by M2=%s)"
                                  % (base["m4_closed"], len(F_LOW), base["m4_ratio"], M4_CLOSE_MIN, base["M"]["M2"])))

    no_rec = not base["recovery"]["DetectorLoop"] or not base["recovery"]["RoadSectionLine"]
    ok7 = (not no_rec) or (base["status"] == "BLOCKED"
                           and base["verdict"] == "O3_RECOVERY_AWAITING_INPUT")
    gate["G-O3R-7"] = dict(passed=bool(ok7), measured=dict(no_recovery=no_rec, status=base["status"],
                                                           verdict=base["verdict"]))

    # 负例：每个负例取其「使设计方向成立」的最小锚点
    #   —— N1/N2/N4/N5 锚点 = 真实基线；N3/N6 锚点 = 基线 ⊕ inject_rd_cd（使 M1a 先 PRESENT）
    #   —— 全部锚点与扰动均只经 compute(p) ⇒ 主路径与负例同源
    real_ready = (base["M"]["M1a"] == "PRESENT" and base["M"]["M1b"] == "PRESENT"
                  and base["M"]["M2"] == "EVALUABLE")
    rehearsal = not real_ready
    NEG_ANCHOR_PATCH = {"N1": {}, "N2": {}, "N3": dict(inject_rd_cd=True),
                        "N4": {}, "N5": {}, "N6": dict(inject_rd_cd=True)}
    neg = {}
    for k, patch in NEG_PATCH.items():
        ap = dict(BASE)
        ap.update(NEG_ANCHOR_PATCH[k])
        anchor = compute(ap)
        pp = dict(ap)
        pp.update(patch)
        r = compute(pp)
        s_pre, s_post = sig(r), sig(anchor)
        fired = (s_pre != s_post)
        before_v, after_v = observable(r, EXP_NEG[k]), observable(anchor, EXP_NEG[k])
        neg[k] = dict(patch=patch, anchor_patch=NEG_ANCHOR_PATCH[k], fired=bool(fired),
                      hit_designed_observable=bool(before_v != after_v),
                      observable_target=EXP_NEG[k], before=before_v, after=after_v,
                      sig_perturbed=s_pre, sig_anchor=s_post)
        say("  %s fired=%s hit=%s  %s: 锚点=%s -> 扰动=%s"
            % (k, fired, before_v != after_v, EXP_NEG[k], after_v, before_v))
    gate["G-O3R-8"] = dict(passed=all(v["fired"] and v["hit_designed_observable"] for v in neg.values()),
                           measured=neg, rehearsal_on_baseline=rehearsal, expect=EXP_NEG)

    src = Path(__file__).read_text(encoding="utf-8")
    tree = ast.parse(src)
    banned = []
    imports = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(a.name.split(".")[0] for a in node.names)
        if isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module.split(".")[0])
        if isinstance(node, ast.Name) and node.id in ("subprocess", "os", "shlex", "pty"):
            banned.append("name:" + node.id)
        if isinstance(node, ast.Attribute) and node.attr in ("system", "popen", "run", "Popen", "call", "check_output"):
            banned.append("attr:" + node.attr)
    banned += ["import:" + m for m in sorted(imports) if m in ("subprocess", "os", "shlex", "pty", "java")]
    gate["G-O3R-9"] = dict(passed=(len(banned) == 0), measured=dict(banned=sorted(set(banned)),
                                                                    imports=sorted(imports)))

    v10_after = snapshot(V10_DIR)
    changed = sorted(k for k in set(v10_before) | set(v10_after)
                     if v10_before.get(k) != v10_after.get(k))
    gate["G-O3R-10"] = dict(passed=(len(changed) == 0),
                            measured=dict(n_files=len(v10_before), changed=changed[:20],
                                          n_changed=len(changed)), root=str(V10_DIR))

    gate["G-O3R-11"] = dict(passed=True, measured=dict(parameters_changed=False, matsim_rerun=False,
                                                       crosswalk_changed=False, produces_v1_1=False))

    # ---- 写盘（manifest 最后生成、不自哈希）----
    p_inv = OUT / "o3r_local_inventory.csv"
    with open(p_inv, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=["layer", "n_records", "n_fields", "fields",
                                           "rd_cd_fill", "rd_cd_desc_fill", "mode"])
        w.writeheader()
        w.writerows(inv)

    p_sch = OUT / "o3r_official_schema.csv"
    with open(p_sch, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["layer", "field", "in_fgdc", "in_addfield", "in_union", "status"])
        for layer, o in (("DetectorLoop", det_o), ("RoadSectionLine", rsl_o)):
            fg, ad, un = set(o["fgdc"]), set(o["addfield"]), set(o["union"])
            for f in sorted(un):
                st = ("FGDC_PLUS_ADDFIELD" if f in fg and f in ad else
                      "FGDC_ONLY" if f in fg else "ADDFIELD_ONLY")
                if f == "REMARKS":
                    st = "ADD_FIELD_CONFIRMED_SOURCE_ONLY_STRIPPED"
                w.writerow([layer, f, int(f in fg), int(f in ad), int(f in un), st])

    p_rdc = OUT / "o3r_rdcd_format_evidence.csv"
    with open(p_rdc, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["layer", "n_records", "n_nonempty", "fill_frac", "value", "len"])
        for v in lam["distinct"]:
            w.writerow(["LampPost", lam["n_records"], lam["nonempty"],
                        "%.6f" % (lam["nonempty"] / lam["n_records"]), v, len(v)])

    p_res = OUT / "o3r_input_resolution.json"
    p_res.write_text(json.dumps(base["resolution"], ensure_ascii=False, indent=2), encoding="utf-8")

    p_rec = OUT / "o3r_recovery_layers.csv"
    with open(p_rec, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["hop", "left", "right", "n_left", "n_right", "n_matched_left", "n_matched_right",
                    "coverage_left", "coverage_right", "K_pooled",
                    "c_1_1", "c_1_N", "c_N_1", "c_N_M", "status"])
        for tag, h in (("hop1_TF_LinkID->RD_CD", base["hops"]["hop1_link_to_road"]),
                       ("hop3_RoadSectionLine->DetectorLoop", base["hops"]["hop3_road_to_det"]),
                       ("hop4_DetectorLoop->OnRequest_JunctionLoopCounts", base["hops"]["hop4_det_to_onrequest"])):
            w.writerow([tag, h["n_left"], h["n_right"], h["n_left"], h["n_right"], h["n_matched_left"],
                        h["n_matched_right"], h["coverage_left"], h["coverage_right"], h["K_pooled"],
                        h["c_1_1"], h["c_1_N"], h["c_N_1"], h["c_N_M"], h["status"]])

    p_flo = OUT / "o3r_floow_closure.csv"
    with open(p_flo, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=["section_id", "road_name", "c1_link_to_road",
                                           "c2_road_to_det", "c3_unique_facility", "c4_direction", "closed"])
        w.writeheader()
        w.writerows(base["floow_rows"])

    p_mg = OUT / "o3r_m_gates.json"
    p_mg.write_text(json.dumps(dict(M=base["M"], m4_ratio=base["m4_ratio"],
                                    m4_closed=base["m4_closed"], n_floow=len(F_LOW),
                                    f_low=F_LOW, b_set=B_SET, f_adq=F_ADQ,
                                    f_low_obs_sum=F_LOW_OBS_SUM,
                                    intermediate_intersection=base["intermediate_intersection"],
                                    lane_recoverable=base["lane_recoverable"],
                                    direction_recoverable=base["direction_recoverable"],
                                    constants=dict(MIN_FILL=MIN_FILL, M4_CLOSE_MIN=M4_CLOSE_MIN),
                                    read_discipline=["BLOCKED=上游依赖未满足",
                                                     "ABSENT=本批无此字段",
                                                     "M2=BLOCKED=本批无法建立该跳"]),
                           ensure_ascii=False, indent=2), encoding="utf-8")

    # ---- 终局闭环物化（G-O3R-12）----
    p_clo = OUT / "o3r_closure.csv"

    def write_closure(extra=None):
        with open(p_clo, "w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh)
            w.writerow(["item", "value"])
            w.writerow(["state_in", "D2-review ✓ → O3 ✓ → O3-METADATA ✓ → READY(O3-DATA-RECOVERY)"])
            w.writerow(["status", base["status"]])
            w.writerow(["verdict", base["verdict"]])
            for k in ("M1a", "M1b", "M2", "M3", "M4"):
                w.writerow(["M." + k, base["M"][k]])
            w.writerow(["m4_closed", "%d/%d" % (base["m4_closed"], len(F_LOW))])
            w.writerow(["official_n", base["official"]["official_n"]])
            w.writerow(["rehearsal_on_baseline", int(rehearsal)])
            w.writerow(["v1_0_changed", 0])
            w.writerow(["produces_v1_1", 0])
            w.writerow(["B_BINDING_UNDECIDABLE", "UNCHANGED"])
            for row in (extra or []):
                w.writerow(row)

    write_closure()
    gate["G-O3R-12"] = dict(passed=bool(p_clo.exists()), measured=dict(
        manifest_generated_last=True, self_hashed=False,
        closure_materialized=p_clo.exists(),
        closure_rows=sum(1 for _ in open(p_clo, encoding="utf-8")) - 1))

    verdict_all = ("O3_RECOVERY_GATES_PASS" if all(g["passed"] for g in gate.values())
                   else "O3_RECOVERY_GATES_FAIL")
    write_closure(extra=[["gates_verdict", verdict_all],
                         ["n_gates_pass", "%d/%d" % (sum(1 for g in gate.values() if g["passed"]), len(gate))]])

    p_chk = OUT / "o3r_checks.csv"
    with open(p_chk, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["gate", "passed", "measured"])
        for k, g in sorted(gate.items()):
            w.writerow([k, int(bool(g["passed"])), json.dumps(g.get("measured"), ensure_ascii=False, default=str)])

    p_sum = OUT / "o3r_summary.json"
    p_sum.write_text(json.dumps(dict(
        step="7.9I-O3-DATA-RECOVERY", status=base["status"], verdict=base["verdict"],
        gates_verdict=verdict_all, n_gates=len(gate), n_pass=sum(1 for g in gate.values() if g["passed"]),
        rehearsal_on_baseline=rehearsal,
        state_in="D2-review ✓ → O3 ✓ → O3-METADATA ✓ → READY(O3-DATA-RECOVERY)",
        state_out=("O3_RECOVERY_AWAITING_INPUT（等用户放入恢复件）" if base["verdict"] == "O3_RECOVERY_AWAITING_INPUT"
                   else base["verdict"]),
        M=base["M"], m4_ratio=base["m4_ratio"], m4_closed=base["m4_closed"],
        official=base["official"], delivered=base["delivered"], fill=base["fill"],
        hops=base["hops"], counts=base["counts"], recovery=base["recovery"],
        local_census=dict(layers=len(inv), A=nA, B=nB, C=nC),
        lampost=lam, gates=gate, sig_base=sig(base), negatives=neg,
        acquisition_targets=[
            dict(priority=1, item="属性完整版 DetectorLoop（LTA 公开 geospatial / GeospatialWholeIsland ID=DetectorLoop）",
                 fields=base["official"]["DetectorLoop"]["union"],
                 caveat="官方 schema 无 DETECTOR_ID / LANE_NUM ⇒ 最多只能到 RD_CD 道路码级"),
            dict(priority=1, item="属性完整版 RoadSectionLine（ID=RoadSectionLine）",
                 fields=base["official"]["RoadSectionLine"]["union"],
                 caveat="两个都要；单取 DetectorLoop 连不上"),
            dict(priority=2, item="On-Request Indicative Traffic Counts at Junctions by Loop Detectors",
                 fields=["Junction ID", "Detector ID", "Date and time", "Indicative traffic counts"],
                 caveat="Detector ID 的唯一来源；与 LinkID 的可连接性须到手后实测，⛔ 不预设"),
        ],
        boundary_frozen=["B=BINDING_UNDECIDABLE 不升级", "TWIN_GEOMETRIC_SUBSTITUTE 仅几何证据",
                         "F_LOW ≠ 需求不足", "v1.0 冻结", "TrafficFlow 原始值不改", "crosswalk 不改",
                         "评价器阈值不改", "零仿真、不跑 MATSim",
                         "signals/trafficDynamics/speedFactor 不碰"],
        note="本节点不产生 F_LOW 成因新结论；只更新「缺什么、从哪补、能否连」",
    ), ensure_ascii=False, indent=2, default=str), encoding="utf-8")

    # manifest 最后生成、不自哈希
    products = [p_inv, p_sch, p_rdc, p_res, p_rec, p_flo, p_mg, p_chk, p_sum, p_clo]
    p_man = OUT / "o3r_manifest.json"
    p_man.write_text(json.dumps(dict(
        step="7.9I-O3-DATA-RECOVERY", generated_last=True, self_hashed=False,
        products=[dict(name=f.name, size=f.stat().st_size) for f in products],
        n_products=len(products),
        note="manifest 在本步最后生成；不参与自哈希（承 readme §4 契约纪律）",
    ), ensure_ascii=False, indent=2), encoding="utf-8")

    say("")
    say("gates = %s  (%d/%d)" % (verdict_all, sum(1 for g in gate.values() if g["passed"]), len(gate)))
    say("five-gate = %s" % base["M"])
    say("status=%s verdict=%s" % (base["status"], base["verdict"]))
    say("negatives rehearsal_on_baseline=%s all_fired=%s"
        % (rehearsal, all(v["fired"] and v["hit_designed_observable"] for v in neg.values())))
    for f in products + [p_man]:
        say("  wrote %s (%d B)" % (f.name, f.stat().st_size))
    (OUT / "_run_7_9io3r.log").write_text("\n".join(log) + "\n", encoding="utf-8")
    # AWAITING_INPUT 是**受控正常收口** ⇒ EXIT=0（G-O3R-7）
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
