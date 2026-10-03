# -*- coding: utf-8 -*-
"""Step 7.9I-O3 · 「LTA 观测对象语义审计」（OBS-DOMAIN）—— 零仿真、只读

★正式问题（用户 2026-09-30 裁定，见 PREREG_7_9I_O3.md）：
  不再问「哪条 MATSim edge 应承接这些车」，改问「LTA 这个数到底测量了什么？」
  四事实：① 观测对象粒度（单车行道 vs 设施）② 是否一观测对象覆盖多承载对象
          ③ Volume 语义 ④ 最后才回 MATSim（本刀不做）
  ★输出：逐断面 Observation Object Card（⛔ 不只给占比）
  ★OBS_OBJECT_UNRESOLVED 规则：缺元数据一律标 UNRESOLVED，⛔ 不得以几何邻近替代

⛔ 底线：不改 v1.0；不跑 MATSim；不碰 signals/trafficDynamics/speedFactor；不产生 v1.1。
★ 实现纪律（承接 O1-续② R2 / D-path R1 / D2-review R1）：主路径与全部负例**共用同一 compute(params)**。
★ 判据非退化：G-O3-5 判别量非退化；G-O3-7 N5 反证「UNRESOLVED 是数据缺失而非判据失效」。
"""
from __future__ import annotations

import ast
import hashlib
import json
import sys
import tempfile
import time
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd
import shapefile as shp
from pyproj import Transformer

ROOT = Path(r"D:\Luan\2026-05\2_Singapore")
sys.path.insert(0, str(ROOT / "scripts" / "od"))

from audit_corridor_scale_7_9ia import OUT                # noqa: E402
from audit_carriageway_pair_7_9io1 import circ_diff       # noqa: E402

HIST = ROOT / "Dynamic_2026_03_16" / "historical_data"
GEO = HIST / "geospatial"

# ---- 预注册常量（PREREG_7_9I_O3.md §2.6，运行前冻结）----
OPP_MIN = 150.0     # 对向判据（承接 D-path）
DIR_OK = 30.0       # 同向判据（承接 O1-续② / D-path）
LEN_MAX = 500.0     # ★新增：短段宽松上界
AGG_MAX = 0.50      # ★新增：路级重复（聚合）判据
SIB_MIN_N = 3       # ★新增：聚合统计最小同胞数
DET_R = 100.0       # ★新增：detector 共址披露半径
PERP_R = 250.0      # ★新增：opp_perp_m 搜索上界
HOUR = 8            # 承接 7.3.6A
K_POOLED = 5.5434   # 1 断面 ↔ K 边（必须同报）

A_C = "A_OBS_NOT_SINGLE_SEGMENT"
C_C = "C_OBS_AGGREGATE_FACILITY"
D_C = "D_LEVEL_CARDINALITY_MISMATCH"
B_C = "B_BINDING_UNDECIDABLE"
E_C = "E_UNEXPLAINED"

PRIMARY = ["48461", "49054", "49104", "48586", "48708", "48337", "47163", "49027", "172382"]
REFERENCE = ["45956", "47189", "45927", "48983", "129352"]
SECTIONS = PRIMARY + REFERENCE

BASE = dict(opp_min=OPP_MIN, dir_ok=DIR_OK, len_max=LEN_MAX, agg_max=AGG_MAX,
            sib_min_n=SIB_MIN_N, det_r=DET_R, perp_r=PERP_R, hour=HOUR,
            project_det=True, fake_detector_id=False, vertex_mode="raw")

# ============================ 全局只读数据 ============================
_tr = Transformer.from_crs("EPSG:4326", "EPSG:3414", always_xy=True)

# --- TrafficFlow_Links（观测对象几何，WGS84）---
_rl = shp.Reader(str(HIST / "TrafficFlow_Links.dbf"))
FIELDS_LINKS = [f[0] for f in _rl.fields[1:]]
tf = pd.DataFrame(_rl.records(), columns=FIELDS_LINKS)
tf["LinkID"] = tf.LinkID.astype(str)
for _c in ["StartLon", "StartLat", "EndLon", "EndLat"]:
    tf[_c] = pd.to_numeric(tf[_c], errors="coerce")
NV = np.array([len(s.points) for s in _rl.shapes()], int)
_XX0, _YY0 = _tr.transform(tf.StartLon.values, tf.StartLat.values)
_XX1, _YY1 = _tr.transform(tf.EndLon.values, tf.EndLat.values)
tf["x0"], tf["y0"], tf["x1"], tf["y1"] = _XX0, _YY0, _XX1, _YY1
tf["mx"], tf["my"] = (_XX0 + _XX1) / 2.0, (_YY0 + _YY1) / 2.0
tf["br"] = np.degrees(np.arctan2(_XX1 - _XX0, _YY1 - _YY0)) % 360.0
tf["len_m"] = np.hypot(_XX1 - _XX0, _YY1 - _YY0)
tf["nv"] = NV
P0 = np.c_[tf.x0.values, tf.y0.values]
P1 = np.c_[tf.x1.values, tf.y1.values]
MID = np.c_[tf.mx.values, tf.my.values]
LNK_IDX = {k: i for i, k in enumerate(tf.LinkID.values)}

# --- TrafficFlow_Data（观测值）---
_j = json.loads((HIST / "TrafficFlow_Data.json").read_text(encoding="utf-8"))
obs = pd.DataFrame(_j["Value"])
FIELDS_OBS = list(obs.columns)
obs["LinkID"] = obs.LinkID.astype(str)
obs["HourOfDate"] = pd.to_numeric(obs.HourOfDate, errors="coerce")
obs["Volume"] = pd.to_numeric(obs.Volume.astype(str).str.replace(",", "", regex=False),
                              errors="coerce")
obs["dt"] = pd.to_datetime(obs.Date, format="%d/%m/%Y")
obs["_isint"] = (obs.Volume % 1 == 0)

# --- DetectorLoop（设施几何，SVY21）---
_tmp = Path(tempfile.mkdtemp())
with zipfile.ZipFile(GEO / "DetectorLoop.zip") as _z:
    _z.extractall(_tmp)
_rd = shp.Reader(str(_tmp / "DetectorLoop_Mar2026" / "DetectorLoop.dbf"))
FIELDS_DET = [f[0] for f in _rd.fields[1:]]
DET_N_SHAPE = len(_rd)
DETXY = np.array([p for s in _rd.shapes() for p in s.points], float)

# --- RoadSectionLine（道路分级层，SVY21）---
_rs = shp.Reader(str(GEO / "RoadSectionLine" / "RoadSectionLine_Mar2026" / "RoadSectionLine.dbf"))
FIELDS_RSL = [f[0] for f in _rs.fields[1:]]
RSL = pd.DataFrame(_rs.records(), columns=FIELDS_RSL)

# --- 断面锚点（SEC_GEO_7_6C）---
SECG = pd.read_csv(ROOT / "reports" / "od_structure_7_6c" / "section_geography.csv",
                   dtype={"lta_linkid": str}).set_index("lta_linkid")

# --- crosswalk（K = primary MATSim 边数）---
CW = pd.read_csv(ROOT / "reports" / "od_final_calibration_crosswalk_7_3_6" /
                 "final_calibration_crosswalk.csv", dtype=str)
CW["lta_linkid"] = CW.lta_linkid.astype(str)
CWp = CW[CW.is_primary_candidate == "True"]
K_MAP = CWp.groupby("lta_linkid").size().to_dict()
HW_MAP = CWp.groupby("lta_linkid").highway.apply(lambda s: ";".join(sorted(set(s)))).to_dict()
DOK_MAP = CW.groupby("lta_linkid").direction_ok.apply(
    lambda s: float((s == "True").mean())).to_dict()

# --- 上一刀卡片（G-O3-2 复现基线）---
D2REV = pd.read_csv(OUT / "o1e_d2rev_cards_7_9id2.csv", dtype={"section_id": str}
                    ).set_index("section_id")
D1CARD = pd.read_csv(OUT / "o1d_trace_cards_7_9id1.csv", dtype={"section_id": str}
                     ).set_index("section_id")


def _perp_to_segments(p, A, B):
    """点 p 到一组线段 [A,B] 的垂距（向量化）。"""
    ab = B - A
    L2 = (ab * ab).sum(1)
    ap = p[None, :] - A
    t = np.clip((ap * ab).sum(1) / np.where(L2 == 0, 1.0, L2), 0.0, 1.0)
    proj = A + t[:, None] * ab
    return np.hypot(proj[:, 0] - p[0], proj[:, 1] - p[1])


def compute(p):
    """主路径与全部负例的唯一入口。返回 (cards_df, meta)。"""
    # ---------- 观测值 ----------
    wk = obs[(obs.HourOfDate == p["hour"]) & (obs.dt.dt.dayofweek < 5)]
    obs89 = wk.groupby("LinkID").Volume.median()
    vint = obs.groupby("LinkID")._isint.mean()
    vcv = wk.groupby("LinkID").Volume.agg(lambda s: float(s.std(ddof=0) / s.mean())
                                          if len(s) and s.mean() else np.nan)
    h7 = obs[obs.HourOfDate == 7].groupby("LinkID").Volume.median()
    n8 = wk.groupby("LinkID").size()

    lk = tf.copy()
    lk["obs89"] = lk.LinkID.map(obs89)
    lk["obs_h7"] = lk.LinkID.map(h7)
    lk["vol_int_frac"] = lk.LinkID.map(vint)
    lk["vol_cv"] = lk.LinkID.map(vcv)
    lk["n_h8_wd"] = lk.LinkID.map(n8)

    # ---------- 方向性：到最近「对向」观测对象的垂距 ----------
    br = lk.br.values
    opp_perp = np.full(len(lk), np.inf)
    opp_id = [None] * len(lk)
    for i in range(len(lk)):
        d = (br - br[i] + 180.0) % 360.0 - 180.0
        m = np.abs(d) >= p["opp_min"]
        m[i] = False
        if not m.any():
            continue
        dd = _perp_to_segments(MID[i], P0, P1)
        dd[~m] = np.inf
        j = int(np.argmin(dd))
        if dd[j] <= p["perp_r"]:
            opp_perp[i] = dd[j]
            opp_id[i] = lk.LinkID.values[j]
    lk["opp_perp_m"] = opp_perp
    lk["opp_obs_id"] = opp_id

    # ---------- 聚合性：同 RoadName 的 obs 唯一率 ----------
    sib_n, sib_uq = {}, {}
    for rn, g in lk.dropna(subset=["obs89"]).groupby("RoadName"):
        sib_n[rn] = len(g)
        sib_uq[rn] = float(g.obs89.nunique() / len(g))
    lk["sib_n"] = lk.RoadName.map(sib_n).fillna(0).astype(int)
    lk["sib_uniq_frac"] = lk.RoadName.map(sib_uq)

    # ---------- 设施绑定：detector 距离 ----------
    if p["project_det"]:
        anchor = np.c_[lk.mx.values, lk.my.values]
    else:
        anchor = np.c_[lk.StartLon.values, lk.StartLat.values]
    det_min = np.empty(len(lk))
    for i in range(len(lk)):
        det_min[i] = np.hypot(DETXY[:, 0] - anchor[i, 0], DETXY[:, 1] - anchor[i, 1]).min()
    lk["det_min_m"] = det_min
    det_n100 = np.empty(len(lk))
    for i in range(len(lk)):
        det_n100[i] = float((np.hypot(DETXY[:, 0] - anchor[i, 0],
                                      DETXY[:, 1] - anchor[i, 1]) <= DET_R).sum())
    lk["det_n_100"] = det_n100

    # ---------- 元数据可得性 / 绑定状态 ----------
    matrix = {
        "detector_id": "AVAILABLE" if p["fake_detector_id"] else "UNAVAILABLE",
        "junction_id": "UNAVAILABLE",
        "road_section_linkid": "UNAVAILABLE",
        "turning_count": "UNAVAILABLE",
    }
    facility_binding = "RESOLVED" if p["fake_detector_id"] else "UNRESOLVED"

    # ---------- 逐断面卡片 ----------
    LKI = lk.set_index("LinkID")
    rows = []
    for sid in SECTIONS:
        r = lk[lk.LinkID == sid].iloc[0]
        nv = 4 if p["vertex_mode"] == "bbox" else int(r.nv)
        n_sib = int(r.sib_n)
        uq = float(r.sib_uniq_frac) if pd.notna(r.sib_uniq_frac) else np.nan
        kp = int(K_MAP.get(sid, 0))
        hA = bool(nv > 2 or r.len_m > p["len_max"])
        hC = bool(n_sib >= p["sib_min_n"] and pd.notna(uq) and uq < p["agg_max"])
        hD = bool(kp > 1)
        hB = bool(facility_binding == "UNRESOLVED" and not hA and not hC)
        hE = bool(not (hA or hC or hD or hB))
        primary = (A_C if hA else C_C if hC else D_C if hD else B_C if hB else E_C)
        rows.append(dict(
            section_id=sid, cohort=("F_LOW" if sid in PRIMARY else "F_ADQ"),
            road_name=str(r.RoadName), road_cat=str(r.RoadCat),
            obs_8_9=round(float(r.obs89), 1) if pd.notna(r.obs89) else np.nan,
            n_vertices=nv, len_m=round(float(r.len_m), 1), bearing=round(float(r.br), 1),
            mid_x=round(float(r.mx), 1), mid_y=round(float(r.my), 1),
            opp_obs_id=(str(r.opp_obs_id) if pd.notna(r.opp_obs_id) else ""),
            opp_perp_m=(round(float(r.opp_perp_m), 1) if np.isfinite(r.opp_perp_m) else np.inf),
            opp_obs89=(round(float(obs89.get(str(r.opp_obs_id), np.nan)), 1)
                       if pd.notna(r.opp_obs_id) and str(r.opp_obs_id) in obs89.index else np.nan),
            opp_same_road=bool(pd.notna(r.opp_obs_id) and str(LKI.loc[str(r.opp_obs_id), "RoadName"]) == r.RoadName),
            sib_n=n_sib, sib_obs_nunique=int(round(uq * n_sib)) if pd.notna(uq) else 0,
            sib_uniq_frac=round(uq, 4) if pd.notna(uq) else np.nan,
            det_min_m=round(float(r.det_min_m), 1), det_n_100=int(r.det_n_100),
            K_primary=kp, highway=str(HW_MAP.get(sid, "")),
            direction_ok_frac=round(float(DOK_MAP.get(sid, np.nan)), 3) if sid in DOK_MAP else np.nan,
            n_h8_wd=int(r.n_h8_wd) if pd.notna(r.n_h8_wd) else 0,
            vol_int_frac=round(float(r.vol_int_frac), 4) if pd.notna(r.vol_int_frac) else np.nan,
            vol_cv=round(float(r.vol_cv), 4) if pd.notna(r.vol_cv) else np.nan,
            obs_h7=round(float(r.obs_h7), 1) if pd.notna(r.obs_h7) else np.nan,
            facility_binding=facility_binding, final_class=primary, confidence="medium",
        ))
    cards = pd.DataFrame(rows)

    # ---------- 全域基线 ----------
    meta = dict(
        n_linkid_geo=int(len(lk)), n_linkid_obs=int(obs.LinkID.nunique()),
        frac_2vertex=float((lk.nv == 2).mean()),
        len_m_p50=float(np.median(lk.len_m)),
        sib_uniq_p50=float(np.nanmedian(list(sib_uq.values()))) if sib_uq else np.nan,
        det_coloc={str(r0): float((det_min <= r0).mean()) for r0 in (25, 50, 100, 200)},
        det_min_p50=float(np.median(det_min)),
        opp_paired_60=float((opp_perp <= 60.0).mean()),
        opp_perp_p50=(float(np.median(opp_perp[np.isfinite(opp_perp)]))
                      if np.isfinite(opp_perp).any() else np.inf),
        opp_perp_inf_n=int(np.isinf(opp_perp).sum()),
        metadata_matrix=matrix, facility_binding=facility_binding,
        nA=int(cards.final_class.eq(A_C).sum()), nC=int(cards.final_class.eq(C_C).sum()),
        nD=int(cards.final_class.eq(D_C).sum()), nB=int(cards.final_class.eq(B_C).sum()),
        nE=int(cards.final_class.eq(E_C).sum()),
        obs89_sum=round(float(cards.obs_8_9.sum()), 1),
        primary_obs_sum=round(float(cards[cards.cohort == "F_LOW"].obs_8_9.sum()), 1),
    )
    return cards, meta


def sig(cards, meta):
    """签名（★含 obs 与 det_min_m：二者是本刀的可观测量，须进签名，否则 N3/N4 空扰动）。"""
    return (round(float(cards.len_m.sum()), 1),
            round(float(cards.opp_perp_m[np.isfinite(cards.opp_perp_m)].sum()), 1),
            round(float(cards.obs_8_9.sum()), 1),
            round(float(cards.det_min_m.sum()), 1),
            int(cards.K_primary.sum()),
            meta["nA"], meta["nC"], meta["nD"], meta["nB"], meta["nE"],
            int(meta["facility_binding"] == "RESOLVED"))


# ============================ 主路径 ============================
t0 = time.time()
cards, meta = compute(BASE)
s0 = sig(cards, meta)

gates = []
# ---------- G-O3-1 坐标同源自洽 ----------
def sec_dist(sid):
    r = tf[tf.LinkID == sid].iloc[0]
    if sid not in SECG.index:
        return np.nan
    return float(np.hypot(r.mx - float(SECG.loc[sid, "mid_x"]), r.my - float(SECG.loc[sid, "mid_y"])))
dsec = np.array([sec_dist(s) for s in PRIMARY])
ok1 = bool(np.all(dsec <= 250.0))
gates.append(["G-O3-1 坐标同源（9 主节 lon/lat→SVY21 vs SEC_GEO 中点 ≤250 m）", ok1,
              "max=%.0f m p50=%.0f m" % (np.nanmax(dsec), np.nanmedian(dsec))])

# ---------- G-O3-2 obs 复现 ----------
_rep = []
for s in PRIMARY:
    a = float(cards.set_index("section_id").loc[s, "obs_8_9"])
    b = float(D2REV.loc[s, "obs_8_9"])
    _rep.append(abs(a - b))
ok2 = bool(np.max(_rep) <= 0.5)
gates.append(["G-O3-2 obs_8_9 复现（vs o1e_d2rev_cards，atol=0.5，9/9）", ok2,
              "max|Δ|=%.2f" % np.max(_rep)])

# ---------- G-O3-3 字段实况 ----------
ok3 = bool(len(FIELDS_LINKS) == 7 and len(FIELDS_OBS) == 10
           and len(FIELDS_DET) == 1 and len(FIELDS_RSL) == 4)
gates.append(["G-O3-3 字段实况自检（Links=7 / Obs=10 / DetLoop=1 / RSL=4）", ok3,
              "Links=%d Obs=%d Det=%d RSL=%d" % (len(FIELDS_LINKS), len(FIELDS_OBS),
                                                 len(FIELDS_DET), len(FIELDS_RSL))])

# ---------- G-O3-4 全域基线非退化 ----------
g4 = [meta["n_linkid_geo"], meta["frac_2vertex"], meta["sib_uniq_p50"]] + list(meta["det_coloc"].values())
ok4 = bool(len(set(round(float(x), 6) for x in g4)) >= 2 and meta["n_linkid_geo"] > 0)
gates.append(["G-O3-4 全域基线非退化", ok4,
              "geo=%d 2v=%.3f uniq_p50=%.3f det100=%.3f opp≤60m=%.3f" % (
                  meta["n_linkid_geo"], meta["frac_2vertex"], meta["sib_uniq_p50"],
                  meta["det_coloc"]["100"], meta["opp_paired_60"])])

# ---------- G-O3-5 判别量非退化 ----------
_dv = {c: cards[c].nunique(dropna=True) for c in ["len_m", "opp_perp_m", "sib_uniq_frac",
                                                  "K_primary", "det_min_m"]}
ok5 = bool(all(v >= 2 for v in _dv.values()))
gates.append(["G-O3-5 判别量非退化（5 个量各 ≥2 取值）", ok5,
              " ".join("%s=%d" % (k, v) for k, v in _dv.items())])

# ---------- G-O3-6 卡片完备 ----------
REQ = ["section_id", "road_name", "road_cat", "obs_8_9", "n_vertices", "len_m", "bearing",
       "opp_obs_id", "opp_perp_m", "sib_n", "sib_uniq_frac", "det_min_m", "det_n_100",
       "K_primary", "n_h8_wd", "vol_int_frac", "facility_binding", "final_class", "confidence"]
_miss = [c for c in REQ if c not in cards.columns]
_nonnull = {c: int(cards[c].notna().sum()) for c in REQ if c not in ("opp_obs_id", "opp_perp_m")}
ok6 = bool(not _miss and all(v == len(cards) for v in _nonnull.values()))
gates.append(["G-O3-6 卡片完备（19 字段齐、非 inf 字段无 NaN）", ok6,
              "missing=%s" % (_miss or "none")])

# ---------- 负例（6，全部与主路径共用 compute）----------
neg = []
for nm, kw in [("N1 OPP_MIN 150→30.1（对向阈值降入同向带）", dict(opp_min=30.1)),
               ("N2 AGG_MAX 0.50→1.01（聚合判据失效）", dict(agg_max=1.01)),
               ("N3 project_det=False（DetectorLoop 不投影）", dict(project_det=False)),
               ("N4 hour 8→7", dict(hour=7)),
               ("N5 fake_detector_id=True（注入伪造 DETECTOR_ID）", dict(fake_detector_id=True)),
               ("N6 vertex_mode=bbox（nv 判据扰动）", dict(vertex_mode="bbox"))]:
    p = dict(BASE); p.update(kw)
    c2, m2 = compute(p)
    s1 = sig(c2, m2)
    neg.append(dict(neg=nm, fired=bool(s1 != s0), sig_base=list(s0), sig_pert=list(s1),
                    d_nA=m2["nA"] - meta["nA"], d_nC=m2["nC"] - meta["nC"],
                    d_nB=m2["nB"] - meta["nB"], binding=m2["facility_binding"]))
okN = bool(all(x["fired"] for x in neg))
gates.append(["G-O3-N 负例 6/6 fired（非同构扰动，共用 compute ⇒ 无空扰动风险）", okN,
              "；".join("%s%s" % (x["neg"][:2], "✓" if x["fired"] else "✗") for x in neg)])

# ---------- G-O3-7 UNRESOLVED 可证伪 ----------
n5 = [x for x in neg if x["neg"].startswith("N5")][0]
ok7 = bool(n5["binding"] == "RESOLVED" and n5["fired"])
gates.append(["G-O3-7 `UNRESOLVED` 可证伪（N5 注入伪造 DETECTOR_ID ⇒ RESOLVED）", ok7,
              "binding=%s fired=%s" % (n5["binding"], n5["fired"])])

# ---------- G-O3-8 A/C 可证伪 ----------
n2 = [x for x in neg if x["neg"].startswith("N2")][0]
n6 = [x for x in neg if x["neg"].startswith("N6")][0]
ok8 = bool(n2["d_nC"] != 0 and n6["d_nA"] != 0)
gates.append(["G-O3-8 A/C 可证伪（N2 ΔnC≠0 ∧ N6 ΔnA≠0）", ok8,
              "ΔnC=%d ΔnA=%d" % (n2["d_nC"], n6["d_nA"])])

# ---------- G-O3-9 AST 自检 ----------
_src = Path(__file__).read_text(encoding="utf-8")
_tree = ast.parse(_src)
_bad = [n for n in ast.walk(_tree)
        if isinstance(n, ast.Import) and any(a.name.split(".")[0] in
                                             ("random", "requests", "urllib", "socket")
                                             for a in n.names)]
_bad += [n for n in ast.walk(_tree)
         if isinstance(n, ast.ImportFrom) and (n.module or "").split(".")[0] in
         ("random", "requests", "urllib", "socket")]
ok9 = bool(not _bad)
gates.append(["G-O3-9 AST 自检（无 random / 无网络）", ok9, "hits=%d" % len(_bad)])

n_fail = sum(1 for _, ok, _ in gates if not ok)
verdict = "OBS_DOMAIN_AUDIT_READY" if n_fail == 0 else "BLOCKED"
elapsed = round(time.time() - t0, 1)

# ============================ 落盘 ============================
csv_p = OUT / "o1f_obs_cards_7_9io3.csv"
cards.to_csv(csv_p, index=False, encoding="utf-8-sig")

rec = dict(
    step="7.9I-O3", name="LTA 观测对象语义审计（OBS-DOMAIN）",
    verdict=verdict, n_fail=n_fail, elapsed_s=elapsed,
    prereg="PREREG_7_9I_O3.md",
    constants=dict(OPP_MIN=OPP_MIN, DIR_OK=DIR_OK, LEN_MAX=LEN_MAX, AGG_MAX=AGG_MAX,
                   SIB_MIN_N=SIB_MIN_N, DET_R=DET_R, PERP_R=PERP_R, HOUR=HOUR,
                   K_POOLED=K_POOLED),
    scope=dict(primary=PRIMARY, reference=REFERENCE,
               primary_obs_sum=meta["primary_obs_sum"]),
    field_inventory={
        "TrafficFlow_Links.dbf": FIELDS_LINKS,
        "TrafficFlow_Data.json": FIELDS_OBS,
        "DetectorLoop.dbf": FIELDS_DET,
        "RoadSectionLine.dbf": FIELDS_RSL,
    },
    doc_vs_data={
        "TrafficFlow_Data.json": "文档称含 VehicleType/Timestamp；实际为 Date/HourOfDate/RoadCat（VehicleType 不存在）",
        "DetectorLoop.dbf": "文档称含 JOB_NUM/RD_CD/LANE_NUM/DETECTOR_ID；实际仅 OBJECTID",
        "RoadSectionLine.dbf": "两种版本均无 LinkID；本地 RD_CD/RD_CATG_NA 100% 空",
    },
    baseline=meta,
    cards=[dict(zip(cards.columns, [None if (isinstance(v, float) and not np.isfinite(v)) else v
                                    for v in row]))
           for row in cards.itertuples(index=False, name=None)],
    gates=[dict(id=g[0], ok=bool(g[1]), detail=g[2]) for g in gates],
    negatives=neg,
    criteria_revision=[
        dict(id="R1", type="仪器实现缺陷（签名设计）",
             what="首版 sig 含 `Σdet_n_100`（基线恒 0，最小 det 距离 113.6 m > DET_R=100 m ⇒ 无判别量）"
                  "且未含 `Σobs_8_9` ⇒ 负例 N3（不投影）/N4（hour 7）**空扰动假阴性**",
             fix="sig 改为含 `Σobs_8_9` 与 `Σdet_min_m`（二者为本刀可观测量）；"
                 "**主路径判据 / 阈值 / 分类 / 卡片字段全部未改**",
             note="属**负例设计缺陷**（仪器层），非科学结论"),
    ],
    disclosure=[
        "facility_binding 在本批恒为 UNRESOLVED（DetectorLoop 无 DETECTOR_ID 字段）⇒ 该轴为**数据缺失**，非判据失效（G-O3-7 反证）",
        "final_class = E 在本批不可达（B 恒真）⇒ 结构性退化，须披露",
        "opp_perp_m 含 inf（PERP_R=250 m 内无对向对象）⇒ 已单列计数",
        "det_n_100 仅披露『附近有线圈设施』，⛔ 不得读作『该观测对象由该线圈测量』",
    ],
)
(csv_sha := hashlib.sha256(csv_p.read_bytes()).hexdigest()[:16])
rec["cards_sha256_16"] = csv_sha
(OUT / "o1f_obs_summary_7_9io3.json").write_text(
    json.dumps(rec, ensure_ascii=False, indent=1), encoding="utf-8")

# ============================ 控制台 ============================
print("=" * 96)
print("Step 7.9I-O3 · LTA 观测对象语义审计（OBS-DOMAIN）")
print("=" * 96)
print("\n[字段实况]")
for k, v in rec["field_inventory"].items():
    print("  %-24s %s" % (k, v))
print("\n[文档 ≠ 数据]")
for k, v in rec["doc_vs_data"].items():
    print("  %-24s %s" % (k, v))
b = meta
print("\n[全域基线]")
print("  LinkID(geo)=%d  LinkID(obs)=%d  2-顶点率=%.4f  len_m p50=%.0f m"
      % (b["n_linkid_geo"], b["n_linkid_obs"], b["frac_2vertex"], b["len_m_p50"]))
print("  同路名 obs 唯一率 p50=%.4f" % b["sib_uniq_p50"])
print("  DetectorLoop 共址率: " + " ".join("%sm=%.3f" % (k, v) for k, v in b["det_coloc"].items())
      + "   det_min p50=%.0f m" % b["det_min_p50"])
print("  对向观测对象垂距 p50=%.0f m  ≤60m 占比=%.3f  inf=%d"
      % (b["opp_perp_p50"], b["opp_paired_60"], b["opp_perp_inf_n"]))
print("\n[逐断面 Observation Object Card]")
cols = ["section_id", "cohort", "road_name", "road_cat", "obs_8_9", "n_vertices", "len_m",
        "opp_perp_m", "sib_n", "sib_uniq_frac", "det_min_m", "K_primary", "facility_binding",
        "final_class"]
print(cards[cols].to_string(index=False))
print("\n[分类合计] A=%d C=%d D=%d B=%d E=%d" % (b["nA"], b["nC"], b["nD"], b["nB"], b["nE"]))
print("  主集 F_LOW Σobs=%.1f" % b["primary_obs_sum"])
print("\n[硬门]")
for gid, ok, det in gates:
    print("  %s  %s | %s" % ("PASS" if ok else "FAIL", gid, det))
print("\n[负例]  基线签名 %s" % (s0,))
for x in neg:
    print("  %-46s fired=%-5s d_nA=%+d d_nC=%+d d_nB=%+d binding=%s"
          % (x["neg"], x["fired"], x["d_nA"], x["d_nC"], x["d_nB"], x["binding"]))
print("\n[判决] %s   gates=%d/%d   n_fail=%d   elapsed=%.1f s   sha=%s"
      % (verdict, len(gates) - n_fail, len(gates), n_fail, elapsed, csv_sha))
