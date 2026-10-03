# -*- coding: utf-8 -*-
"""Step 7.9I-O3-R1 · 「观测域重建（Observation-Domain Reconstruction）」—— 零仿真 / 只读

★正式问题（用户 2026-10-01 18:00 裁定，见 PREREG_7_9I_O3R1.md）：
  放弃「必须恢复 DetectorLoop → Detector ID → Junction ID」这条链；
  把研究对象重定义为「LTA 道路观测段 — RoadSectionLine — MATSim 道路对象」的空间观测单元；
  DetectorLoop 退为**辅助空间证据**。
  正式问句：**LTA 的一个交通流观测量，对应 MATSim 中哪些道路对象？**

⛔ 底线：不改 v1.0；不跑 MATSim；不碰 signals/trafficDynamics/speedFactor；不产生 v1.1；
        ⛔ 不覆盖 canonical（median 口径）；⛔ 不用几何邻近冒充设施身份。
★ 实现纪律（承接 O3 / O3-METADATA / O3-DATA-RECOVERY）：主路径与全部负例**共用同一 compute(params)**；
  门禁**必携带实测值**；⛔ 不得写死 `True`（假门禁纪律）。
"""
from __future__ import annotations

import ast
import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
import shapefile as shp
from pyproj import Transformer
from shapely.geometry import LineString, Point, Polygon
from shapely.strtree import STRtree

ROOT = Path(r"D:\Luan\2026-05\2_Singapore")
sys.path.insert(0, str(ROOT / "scripts" / "od"))

from audit_o3_recovery_7_9io3r import official_schema   # noqa: E402  FGDC ∪ AddField

OUT = ROOT / "reports" / "corridor_scale_audit_7_9i"
REC = ROOT / "recovery_7_9io3r"
HIST = ROOT / "Dynamic_2026_03_16" / "historical_data"
FINAL = ROOT / "Singapore_OD_MATSim_FinalData"
V10_DIR = ROOT / "matsim_final_7_6h" / "outputs" / "W01_rc_min"
NETNPZ = ROOT / "scripts" / "od" / "_cache_network_7_9c0.npz"
CW_CSV = ROOT / "reports" / "od_final_calibration_crosswalk_7_3_6" / "final_calibration_crosswalk.csv"
SECG_CSV = ROOT / "reports" / "od_structure_7_6c" / "section_geography.csv"
SSV10_CSV = OUT / "section_scale_v10.csv"
CANON = [OUT / "section_scale_v10.csv", OUT / "section_scale_A1.csv",
         OUT / "corridor_scale_v10.csv", OUT / "corridor_scale_A1.csv"]

# ---------- 冻结常量（PREREG §3）----------
CONST = dict(rsl_max=25.0, rsl_ang=30.0, msim_max=25.0, msim_ang=30.0,
             tierA_score=0.70, tierB_loop=50.0, unique_gap=10.0, rc_len=6)
PLACEHOLDER = ("NONAME", "")
BASE = dict(**CONST, placeholder_active=True, inject_det_rd_cd=False, disable_detector=False,
            rsl_axial=False, uniq_mode="tie")

F_LOW = ["48461", "49054", "49104", "48586", "48708", "48337", "47163", "49027", "172382"]
B_SET = ["48461", "49054", "47189"]
F_ADQ = ["45956", "47189", "45927", "48983", "129352"]

EXP_TF_N = 1278
EXP_RSL_N = 15354
EXP_RSL_FIELDS = 11
EXP_RSL_RDCD_DISTINCT = 3825
EXP_RSL_UNION = 12
EXP_DET_N = 16275
EXP_DET_FIELDS = 1
EXP_DET_UNION = 12
EXP_PLACEHOLDER_NONAME = 355

INPUT_SPECS = {
    "RoadSectionLine": dict(
        declared=[str(REC / "RoadSectionLine" / "RoadSectionLine.dbf")],
        fallbacks=[str(REC / "RoadSectionLine" / "*.dbf"),
                   str(FINAL / "**" / "RoadSectionLine*.dbf")]),
    "DetectorLoop": dict(
        declared=[str(REC / "DetectorLoop" / "DetectorLoop.dbf")],
        fallbacks=[str(REC / "DetectorLoop" / "*.dbf"),
                   str(FINAL / "**" / "DetectorLoop*.dbf")]),
    "TrafficFlow_Links": dict(declared=[str(HIST / "TrafficFlow_Links.dbf")], fallbacks=[]),
    "TrafficFlow_Data": dict(declared=[str(HIST / "TrafficFlow_Data.json")], fallbacks=[]),
    "MatSimNetworkCache": dict(declared=[str(NETNPZ)], fallbacks=[]),
    "Crosswalk576": dict(declared=[str(CW_CSV)], fallbacks=[]),
    "SectionGeography": dict(declared=[str(SECG_CSV)], fallbacks=[]),
    "SectionScaleV10": dict(declared=[str(SSV10_CSV)], fallbacks=[]),
}


def _expand(pattern: str):
    p = Path(pattern)
    if not any(c in p.name for c in "*?["):
        return [p]
    anc = p
    while any(c in anc.name for c in "*?["):
        anc = anc.parent
    if not anc.exists():
        return []
    return sorted(anc.glob(str(p.relative_to(anc))))


def resolve_inputs():
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


def circ_diff(a, b):
    d = abs(a - b) % 360.0
    return min(d, 360.0 - d)


def _adiff(a, b, axial):
    """方向差。`axial=False`（冻结原文）= 有向；`axial=True`（§0 更正）= 轴向（无向）。"""
    d = circ_diff(a, b)
    return min(d, 180.0 - d) if axial else d


# ============================ 载入 ============================
def load_all(D_res):
    D = {}
    tr = Transformer.from_crs("EPSG:4326", "EPSG:3414", always_xy=True)

    rl = shp.Reader(str(HIST / "TrafficFlow_Links.dbf"))
    cols = [f[0] for f in rl.fields[1:]]
    tf = pd.DataFrame(rl.records(), columns=cols)
    tf["LinkID"] = tf.LinkID.astype(str)
    for c in ["StartLon", "StartLat", "EndLon", "EndLat"]:
        tf[c] = pd.to_numeric(tf[c], errors="coerce")
    x0, y0 = tr.transform(tf.StartLon.values, tf.StartLat.values)
    x1, y1 = tr.transform(tf.EndLon.values, tf.EndLat.values)
    tf["x0"], tf["y0"], tf["x1"], tf["y1"] = x0, y0, x1, y1
    tf["len_m"] = np.hypot(x1 - x0, y1 - y0)
    tf["br"] = (np.degrees(np.arctan2(x1 - x0, y1 - y0)) + 360.0) % 360.0
    tf["mx"], tf["my"] = 0.5 * (x0 + x1), 0.5 * (y0 + y1)
    D["tf"] = tf
    D["tf_geom"] = [LineString([(a, b), (c, d)]) for a, b, c, d in zip(tf.x0, tf.y0, tf.x1, tf.y1)]
    D["tf_mid"] = [Point(a, b) for a, b in zip(tf.mx, tf.my)]

    rsl_path, det_path = D_res["RoadSectionLine"], D_res["DetectorLoop"]
    D["rsl_path"], D["det_path"] = (str(rsl_path) if rsl_path else None), (str(det_path) if det_path else None)

    rs = shp.Reader(str(rsl_path))
    rcols = [f[0] for f in rs.fields[1:]]
    D["rsl_fields"] = rcols
    D["rsl_records"] = rs.records()
    ci = rcols.index("RD_CD") if "RD_CD" in rcols else None
    segs, seg_par, seg_bear, rd_by_rec = [], [], [], []
    for i, s in enumerate(rs.shapes()):
        pts = s.points
        rd_by_rec.append(str(rs.record(i)[ci]).strip() if ci is not None else "")
        for a, b in zip(pts[:-1], pts[1:]):
            if a == b:
                continue
            segs.append(LineString([a, b]))
            seg_par.append(i)
            seg_bear.append((np.degrees(np.arctan2(b[0] - a[0], b[1] - a[1])) + 360.0) % 360.0)
    D["rsl_segs"] = segs
    D["rsl_seg_parent"] = np.array(seg_par, int)
    D["rsl_seg_bear"] = np.array(seg_bear, float)
    D["rsl_rdcd_by_rec"] = rd_by_rec
    D["rsl_tree"] = STRtree(segs) if segs else None
    xs = [p[0] for s in rs.shapes() for p in s.points]
    ys = [p[1] for s in rs.shapes() for p in s.points]
    D["rsl_bbox"] = (min(xs), min(ys), max(xs), max(ys)) if xs else None

    rd = shp.Reader(str(det_path))
    dcols = [f[0] for f in rd.fields[1:]]
    D["det_fields"] = dcols
    D["det_n"] = len(rd)
    polys, pxs, pys = [], [], []
    for s in rd.shapes():
        try:
            pg = Polygon(s.points)
            if not pg.is_valid:
                pg = pg.buffer(0)
        except Exception:
            pg = Point(s.points[0])
        polys.append(pg)
        pxs += [p[0] for p in s.points]
        pys += [p[1] for p in s.points]
    D["det_geom"] = polys
    D["det_tree"] = STRtree(polys) if polys else None
    D["det_has_rdcd_native"] = "RD_CD" in [c.upper() for c in dcols]
    D["det_bbox"] = (min(pxs), min(pys), max(pxs), max(pys)) if pxs else None

    z = np.load(NETNPZ, allow_pickle=True)
    D["ms_ids"] = z["ids"]
    D["ms_len"] = z["len_m"]
    D["ms_hw"] = z["highway"]
    nid, nx, ny = z["node_ids"], z["node_x"], z["node_y"]
    nidx = {str(k): i for i, k in enumerate(nid)}
    frm, to = z["frm"], z["to"]
    fi = np.array([nidx.get(str(k), -1) for k in frm])
    ti = np.array([nidx.get(str(k), -1) for k in to])
    ok = (fi >= 0) & (ti >= 0)
    fx = np.where(ok, nx[np.clip(fi, 0, None)], np.nan)
    fy = np.where(ok, ny[np.clip(fi, 0, None)], np.nan)
    tx = np.where(ok, nx[np.clip(ti, 0, None)], np.nan)
    ty = np.where(ok, ny[np.clip(ti, 0, None)], np.nan)
    D["ms_mx"], D["ms_my"] = 0.5 * (fx + tx), 0.5 * (fy + ty)
    D["ms_br"] = (np.degrees(np.arctan2(tx - fx, ty - fy)) + 360.0) % 360.0
    D["ms_idx"] = np.where(ok)[0]
    D["ms_tree"] = STRtree([Point(a, b) for a, b in zip(D["ms_mx"][ok], D["ms_my"][ok])])
    D["ms_n"] = int(len(D["ms_ids"]))

    cw = pd.read_csv(CW_CSV, dtype=str)
    cw["lta_linkid"] = cw.lta_linkid.astype(str)
    cwp = cw[cw.is_primary_candidate == "True"]
    D["cw_K"] = cwp.groupby("lta_linkid").size().to_dict()
    D["cw_set"] = set(cw.lta_linkid.unique())
    D["cw_rows"] = len(cw)

    sg = pd.read_csv(SECG_CSV, dtype=str)
    D["secg_set"] = set(sg.lta_linkid.astype(str))
    D["secg_xy"] = np.c_[pd.to_numeric(sg.mid_x, errors="coerce"),
                         pd.to_numeric(sg.mid_y, errors="coerce")]

    D["s10"] = None
    if SSV10_CSV.exists():
        s10 = pd.read_csv(SSV10_CSV, dtype=str)
        s10["lta_linkid"] = s10.lta_linkid.astype(str)
        for c in ["obs_8_9", "sim_median_xS", "sim_sum_xS", "len_sum", "n_edges"]:
            if c in s10.columns:
                s10[c] = pd.to_numeric(s10[c], errors="coerce")
        D["s10"] = s10

    D["schema"] = {}
    for ly, tag in (("RoadSectionLine", "rsl"), ("DetectorLoop", "det")):
        xml = Path(rsl_path if ly == "RoadSectionLine" else det_path).with_suffix(".shp.xml")
        D["schema"][tag] = (len(official_schema(xml)[0]), len(official_schema(xml)[1]),
                            len(official_schema(xml)[2])) if xml.exists() else None
    return D


# ============================ 核心：唯一入口 ============================
def compute(p, D):
    rsl_max, rsl_ang = p["rsl_max"], p["rsl_ang"]
    msim_max, msim_ang = p["msim_max"], p["msim_ang"]
    tierA_score, tierB_loop = p["tierA_score"], p["tierB_loop"]
    gap = p["unique_gap"]
    axial = bool(p.get("rsl_axial", False))
    ph = PLACEHOLDER if p["placeholder_active"] else tuple()

    tf = D["tf"]
    seg_tree, segs = D["rsl_tree"], D["rsl_segs"]
    seg_bear, seg_par = D["rsl_seg_bear"], D["rsl_seg_parent"]
    rdcd_rec = D["rsl_rdcd_by_rec"]
    qbuf = rsl_max + float(tf.len_m.max())
    rows = []

    for i in range(len(tf)):
        g = D["tf_geom"][i]
        br = float(tf.br.values[i])
        hits = []
        for j in (seg_tree.query(g.buffer(qbuf)) if seg_tree is not None else []):
            j = int(j)
            d = g.distance(segs[j])
            if d > rsl_max:
                continue
            ang = _adiff(br, float(seg_bear[j]), axial)
            if ang > rsl_ang:
                continue
            hits.append((d, ang, rdcd_rec[seg_par[j]]))
        hits.sort(key=lambda x: x[0])
        if hits:
            d0 = hits[0][0]
            ang0 = hits[0][1]
            uniq_tie = len([h for h in hits if abs(h[0] - d0) <= gap]) == 1
            rcs = []
            for h in hits:
                if h[2] and h[2] not in rcs:
                    rcs.append(h[2])
            n_rsl, rc_top = len(rcs), hits[0][2]
            uniq_rdcd = (n_rsl == 1)
        else:
            d0, ang0, uniq_tie, uniq_rdcd, n_rsl, rc_top = np.nan, np.nan, False, False, 0, ""
        uniq = uniq_tie if p.get("uniq_mode", "tie") == "tie" else uniq_rdcd

        code_term = 1 if (rc_top and len(rc_top) == p["rc_len"] and rc_top not in ph) else 0
        d_term = max(0.0, min(1.0, 1.0 - d0 / rsl_max)) if np.isfinite(d0) else 0.0
        a_term = max(0.0, min(1.0, 1.0 - ang0 / rsl_ang)) if np.isfinite(ang0) else 0.0
        score = 0.5 * d_term + 0.3 * a_term + 0.2 * code_term
        n_ph = sum(1 for h in hits if h[2] in ph)

        # ★诊断（不受阈值裁剪）：最近 RSL 段的真实距离/方向差 —— 用于「阈值敏感度披露」
        if seg_tree is not None:
            jn = int(seg_tree.nearest(g))
            d_near = float(g.distance(segs[jn]))
            ang_near = float(_adiff(br, float(seg_bear[jn]), axial))
            rd_near = rdcd_rec[seg_par[jn]]
        else:
            d_near, ang_near, rd_near = np.nan, np.nan, ""

        mp = D["tf_mid"][i]
        ms_hit = []
        for jj in D["ms_tree"].query(mp.buffer(msim_max)):
            k = int(D["ms_idx"][int(jj)])
            if np.hypot(D["ms_mx"][k] - mp.x, D["ms_my"][k] - mp.y) > msim_max:
                continue
            if circ_diff(br, float(D["ms_br"][k])) > msim_ang:
                continue
            ms_hit.append(k)
        ms_ids = sorted({str(D["ms_ids"][k]) for k in ms_hit})
        m_len = float(sum(D["ms_len"][k] for k in ms_hit))
        hw = sorted({str(D["ms_hw"][k]) for k in ms_hit})

        loop_near = []
        if p["disable_detector"] or D["det_tree"] is None:
            d_loop, band = np.nan, "LOOP_UNRESOLVED"
        else:
            for jn in D["det_tree"].query(g.buffer(tierB_loop)):
                jn = int(jn)
                if g.distance(D["det_geom"][jn]) <= tierB_loop:
                    loop_near.append(jn)
            idx = int(D["det_tree"].nearest(g))
            d_min = g.distance(D["det_geom"][idx])
            for jn in loop_near:
                d_min = min(d_min, g.distance(D["det_geom"][jn]))
            d_loop = float(d_min)
            band = ("LOOP_NEAR" if d_loop <= 25 else "LOOP_ASSOCIATED" if d_loop <= 50
                    else "LOOP_WEAK" if d_loop <= 100 else "LOOP_UNRESOLVED")

        matched = bool(hits)
        hi_conf = (matched and uniq and np.isfinite(d0) and d0 <= rsl_max
                   and ang0 <= rsl_ang and code_term == 1 and score >= tierA_score and len(ms_ids) > 0)
        if not matched:
            tier = "X"
        elif hi_conf:
            tier = "A"
        elif np.isfinite(d_loop) and d_loop <= tierB_loop:
            tier = "B"
        else:
            tier = "C"

        rows.append(dict(
            LinkID=str(tf.LinkID.values[i]), RoadName=str(tf.RoadName.values[i]),
            RoadCat=str(tf.RoadCat.values[i]), TF_LENGTH=round(float(tf.len_m.values[i]), 3),
            d_rsl=(round(float(d0), 3) if np.isfinite(d0) else ""),
            ang_rsl=(round(float(ang0), 3) if np.isfinite(ang0) else ""),
            RD_CD=rc_top, n_rsl=n_rsl, rsl_unique=int(uniq),
            uniq_tie=int(uniq_tie), uniq_rdcd=int(uniq_rdcd), code_term=code_term,
            MATCH_SCORE=round(float(score), 4), n_placeholder=int(n_ph),
            d_rsl_near=(round(d_near, 3) if np.isfinite(d_near) else ""),
            ang_rsl_near=(round(ang_near, 3) if np.isfinite(ang_near) else ""),
            RD_CD_near=rd_near,
            N_MATSIM=len(ms_ids), MATSIM_LENGTH=round(m_len, 3), hw_mix=";".join(hw),
            crosswalk_K=D["cw_K"].get(str(tf.LinkID.values[i]), ""),
            LOOP_DISTANCE=(round(float(d_loop), 3) if np.isfinite(d_loop) else ""),
            N_LOOP_NEAR=len(loop_near), LOOP_BAND=band, TIER=tier,
            _ms_ids=ms_ids, _loops=loop_near))

    df = pd.DataFrame(rows)

    # 双唯一性轴：Tier 在两轴上分别重算（保证 TIER 与 tier_counts 同源）
    dd = pd.to_numeric(df.d_rsl, errors="coerce")
    aa = pd.to_numeric(df.ang_rsl, errors="coerce")
    sc = pd.to_numeric(df.MATCH_SCORE, errors="coerce")
    dl = pd.to_numeric(df.LOOP_DISTANCE, errors="coerce")
    mm = dd.notna()

    def _tier(uniq_col):
        hi = (mm & (uniq_col == 1) & (dd <= rsl_max) & (aa <= rsl_ang)
              & (df.code_term == 1) & (sc >= tierA_score) & (df.N_MATSIM > 0))
        return np.where(~mm, "X", np.where(hi, "A", np.where(dl <= tierB_loop, "B", "C")))

    df["TIER_ALTTIE"] = _tier(df.uniq_tie)
    df["TIER_ALTRDCD"] = _tier(df.uniq_rdcd)
    df["TIER"] = _tier(df.uniq_tie if p.get("uniq_mode", "tie") == "tie" else df.uniq_rdcd)
    tc = df.TIER.value_counts().to_dict() if len(df) else {}
    tc_tie = df.TIER_ALTTIE.value_counts().to_dict() if len(df) else {}

    def hop_stats(edges, universe_right):
        """§4 逐跳计量。`universe_right` = 右键**全域基数**（coverage 的分母，非命中数）。"""
        L, R = {}, {}
        for a, b in edges:
            if not a or b is None or b == "":
                continue
            L.setdefault(a, set()).add(b)
            R.setdefault(b, set()).add(a)
        kl = {k: len(v) for k, v in L.items()}
        ml = {k: len(v) for k, v in R.items()}
        c = dict(c_1_1=0, c_1_N=0, c_N_1=0, c_N_M=0)
        for k, kk in kl.items():
            mk = max(ml[x] for x in L[k])
            if kk == 1 and mk == 1:
                c["c_1_1"] += 1
            elif kk == 1 and mk > 1:
                c["c_1_N"] += 1
            elif kk > 1 and mk == 1:
                c["c_N_1"] += 1
            else:
                c["c_N_M"] += 1
        nm_l, nm_r = len(L), len(R)
        return dict(n_left=len({a for a, _ in edges}), n_right_universe=int(universe_right),
                    n_matched_left=nm_l, n_matched_right=nm_r,
                    coverage_left=round(nm_l / EXP_TF_N, 6),
                    coverage_right=round(nm_r / max(1, int(universe_right)), 6),
                    K_pooled=round(sum(kl.values()) / nm_l, 6) if nm_l else None, **c)

    e1 = [(r["LinkID"], r["RD_CD"]) for r in rows if r["RD_CD"]]
    e2 = [(r["LinkID"], m) for r in rows for m in r["_ms_ids"]]
    e3 = [(r["LinkID"], "L%d" % li) for r in rows for li in r["_loops"]]
    n_rdcd = len({rdcd_rec[i] for i in range(len(rdcd_rec)) if rdcd_rec[i]})
    return dict(params=dict(p), n_tf=int(len(df)),
                tier_counts={k: int(tc.get(k, 0)) for k in ["A", "B", "C", "X"]},
                tier_counts_alt_tie={k: int(tc_tie.get(k, 0)) for k in ["A", "B", "C", "X"]},
                det_has_rdcd=bool(D["det_has_rdcd_native"]) or bool(p["inject_det_rd_cd"]),
                hop1=hop_stats(e1, n_rdcd), hop2=hop_stats(e2, D["ms_n"]),
                hop3=hop_stats(e3, D["det_n"]),
                df=df, e1=e1, e2=e2, e3=e3)


def anchors(R, D):
    df = R["df"].set_index("LinkID")
    s10 = D["s10"]
    s10i = s10.set_index("lta_linkid") if s10 is not None else None
    out, summary = [], {}
    for group, ids in (("F_LOW", F_LOW), ("B_SET", B_SET), ("F_ADQ", F_ADQ)):
        for sid in ids:
            rec = dict(group=group, section_id=str(sid),
                       TIER=df.TIER.get(str(sid), "NA"),
                       in_576=int(str(sid) in D["cw_set"]))
            if str(sid) in df.index:
                r = df.loc[str(sid)]
                rec.update(RD_CD=r.RD_CD, d_rsl=r.d_rsl, MATCH_SCORE=r.MATCH_SCORE,
                           N_MATSIM=r.N_MATSIM, MATSIM_LENGTH=r.MATSIM_LENGTH,
                           LOOP_DISTANCE=r.LOOP_DISTANCE, LOOP_BAND=r.LOOP_BAND)
            if s10i is not None and str(sid) in s10i.index:
                z = s10i.loc[str(sid)]
                obs = float(z.obs_8_9) if pd.notna(z.obs_8_9) else np.nan
                rec.update(obs_8_9=z.obs_8_9,
                           R_median=round(float(z.sim_median_xS) / obs, 6) if obs else "",
                           R_sum=round(float(z.sim_sum_xS) / obs, 6) if obs else "")
            out.append(rec)
    if s10 is not None:
        z = s10.copy()
        z["R_median"] = z.sim_median_xS / z.obs_8_9
        z["R_sum"] = z.sim_sum_xS / z.obs_8_9
        z["TIER"] = z.lta_linkid.map(lambda s: df.TIER.get(s, "NA"))
        summary = dict(n=int(len(z)),
                       R_median_median=round(float(z.R_median.median()), 6),
                       R_sum_median=round(float(z.R_sum.median()), 6),
                       n_R_median_below1=int((z.R_median < 1).sum()),
                       n_R_sum_below1=int((z.R_sum < 1).sum()),
                       n_med_below1_but_sum_ge1=int(((z.R_sum >= 1) & (z.R_median < 1)).sum()),
                       tier_counts={k: int((z.TIER == k).sum()) for k in ["A", "B", "C", "X"]},
                       crosswalk_K_mean=round(float(s10.n_edges.mean()), 4))
    return out, summary


def snapshot(paths):
    return {str(p): (p.stat().st_mtime_ns if p.exists() else None) for p in paths}


def sig(res):
    return dict(tier=res["tier_counts"], det=res["det_has_rdcd"],
                nph=int(res["df"].n_placeholder.sum()),
                h1=res["hop1"]["n_matched_left"], h2=res["hop2"]["n_matched_left"],
                h3=res["hop3"]["n_matched_left"])


def main() -> int:
    t0 = time.time()
    say = print
    say("== Step 7.9I-O3-R1 观测域重建（零仿真/只读）==")
    can_before = snapshot(CANON)
    v10_before = None
    if V10_DIR.exists():
        v10_before = {str(f.relative_to(V10_DIR)): f.stat().st_mtime_ns
                      for f in sorted(V10_DIR.rglob("*")) if f.is_file()}
    resolution, eff = resolve_inputs()
    say("[1] 输入解析：" + " · ".join("%s=%s" % (k, "OK" if v["resolved_path"] else "MISSING")
                                      for k, v in resolution.items()))

    D = load_all(eff)
    say("[2] 载入：TF=%d · RSL=%d(字段%d,段%d) · DET=%d(字段%d) · MATSim 边=%d"
        % (len(D["tf"]), len(D["rsl_records"]), len(D["rsl_fields"]), len(D["rsl_segs"]),
           D["det_n"], len(D["det_fields"]), D["ms_n"]))
    say("    官方 schema (FGDC/AddField/∪)：RSL=%s DET=%s" % (D["schema"]["rsl"], D["schema"]["det"]))

    # ★§0 正式更正：TF→RSL 采用**轴向**判据（RSL 无方向语义；实测 730/1,234 为反向）
    # ★§0.2 判据细化：Tier A 的「唯一性」改用「命中 `RD_CD` 去重 = 1」（预注册的 10 m 间隔轴并报）
    EFF = dict(BASE); EFF["rsl_axial"] = True; EFF["uniq_mode"] = "rdcd"
    frozen = compute(BASE, D)
    base = compute(EFF, D)
    say("[3-frozen] 有向轴（预注册 §3 原文）：Tier=%s · ①命中 %d"
        % (frozen["tier_counts"], frozen["hop1"]["n_matched_left"]))
    say("[3] 轴向（§0 更正后生效）：Tier=%s · ①/②/③ 命中 %d/%d/%d"
        % (base["tier_counts"], base["hop1"]["n_matched_left"],
           base["hop2"]["n_matched_left"], base["hop3"]["n_matched_left"]))
    anchors_rows, s576 = anchors(base, D)

    # ---------- ★阈值敏感度披露（不改冻结判据；只回答「低比例是判据伪影还是数据事实」）----------
    dbase = base["df"]
    dn = pd.to_numeric(dbase.d_rsl_near, errors="coerce")
    an = pd.to_numeric(dbase.ang_rsl_near, errors="coerce")
    fn = frozen["df"]
    fdn = pd.to_numeric(fn.d_rsl_near, errors="coerce")
    fan = pd.to_numeric(fn.ang_rsl_near, errors="coerce")
    near_diag = dict(
        axis="axial(§0 更正)",
        d_near_med=round(float(dn.median()), 3), d_near_p90=round(float(dn.quantile(0.90)), 3),
        n_le_25=int((dn <= 25).sum()), n_le_50=int((dn <= 50).sum()),
        n_le_100=int((dn <= 100).sum()), n_le_200=int((dn <= 200).sum()),
        n_le_25_ang_le30=int(((dn <= 25) & (an <= 30)).sum()),
        n_le_25_ang_gt30=int(((dn <= 25) & (an > 30)).sum()),
        n_le_50_ang_le30=int(((dn <= 50) & (an <= 30)).sum()),
        frozen_directed=dict(
            n_le_25_ang_le30=int(((fdn <= 25) & (fan <= 30)).sum()),
            n_le_25_ang_gt30=int(((fdn <= 25) & (fan > 30)).sum())))
    SENS = [("base_axial+uniq_rdcd(§0 生效)", {}),
            ("frozen_directed+uniq_tie(预注册原文)", dict(rsl_axial=False, uniq_mode="tie")),
            ("axial+uniq_tie", dict(uniq_mode="tie")),
            ("rsl50", dict(rsl_max=50.0)), ("ang45", dict(rsl_ang=45.0)),
            ("rsl50_ang45", dict(rsl_max=50.0, rsl_ang=45.0)),
            ("gap0(tie)", dict(unique_gap=0.0, uniq_mode="tie")),
            ("gap25(tie)", dict(unique_gap=25.0, uniq_mode="tie")),
            ("score0.50", dict(tierA_score=0.50)), ("matsim50", dict(msim_max=50.0))]
    sens_rows = []
    for tag, patch in SENS:
        pp = dict(EFF); pp.update(patch)
        rr = compute(pp, D) if patch else base
        tc = rr["tier_counts"]
        sens_rows.append(dict(config=tag, **{k: tc[k] for k in ["A", "B", "C", "X"]},
                              tierA_cov=round(tc["A"] / EXP_TF_N, 4),
                              tierX_cov=round(tc["X"] / EXP_TF_N, 4),
                              hop1_matched=rr["hop1"]["n_matched_left"]))
    say("[3b] 敏感度：" + " · ".join("%s→A=%d/X=%d" % (r["config"], r["A"], r["X"])
                                     for r in sens_rows))
    say("    最近距诊断：p50=%.1f m · ≤25m %d（轴向：方向>30° 的 %d）· ≤50m %d"
        % (near_diag["d_near_med"], near_diag["n_le_25"],
           near_diag["n_le_25_ang_gt30"], near_diag["n_le_50"]))

    # ---------- ★逐判据贡献（回答「哪个判据才是卡点」，不靠调参）----------
    m_d = pd.to_numeric(dbase.d_rsl, errors="coerce").notna()
    m_a = pd.to_numeric(dbase.ang_rsl, errors="coerce").notna()
    crit = dict(n=len(dbase),
                d_ok=int(m_d.sum()), ang_ok=int((m_d & m_a).sum()),
                code_ok=int((m_d & m_a & (dbase.code_term == 1)).sum()),
                score_ok=int((m_d & m_a & (dbase.code_term == 1)
                              & (pd.to_numeric(dbase.MATCH_SCORE) >= BASE["tierA_score"])).sum()),
                msim_ok=int((dbase.N_MATSIM > 0).sum()),
                uniq_tie_ok=int(dbase.uniq_tie.sum()),
                uniq_rdcd_ok=int(dbase.uniq_rdcd.sum()),
                all_uniq_tie=int((dbase.TIER_ALTTIE == "A").sum()),
                all_uniq_rdcd=int((dbase.TIER_ALTRDCD == "A").sum()))
    say("[3c] 逐判据：距离通过 %d · 距离∧方向 %d · ∧合法码 %d · ∧分数 %d · ∧MATSim %d"
        % (crit["d_ok"], crit["ang_ok"], crit["code_ok"], crit["score_ok"], crit["msim_ok"]))
    say("     唯一性：tie 轴 %d · rdcd 轴 %d（TierA tie=%d / rdcd=%d）"
        % (crit["uniq_tie_ok"], crit["uniq_rdcd_ok"],
           base["tier_counts_alt_tie"]["A"], base["tier_counts"]["A"]))

    NEGS = {"N1": dict(rsl_max=5.0), "N2": dict(rsl_max=200.0),
            "N3": dict(placeholder_active=False), "N4": dict(inject_det_rd_cd=True),
            "N5": dict(msim_max=1.0), "N6": dict(disable_detector=True)}
    neg, sb = [], sig(base)
    for k, patch in NEGS.items():
        pp = dict(EFF); pp.update(patch)
        rr = compute(pp, D)
        sr = sig(rr)
        designed = {"N1": sr["h1"] < sb["h1"], "N2": sr["h1"] > sb["h1"],
                    "N3": (rr["df"].n_placeholder.sum() == 0) or (rr["tier_counts"]["A"] != sb["tier"]["A"]),
                    "N4": sr["det"] and not sb["det"], "N5": sr["h2"] < sb["h2"],
                    "N6": rr["tier_counts"]["B"] == 0}[k]
        neg.append(dict(id=k, patch=patch, fired=bool(sr != sb), hit=bool(designed), base=sb, pert=sr))
        say("  %s fired=%s hit=%s  base=%s -> pert=%s" % (k, sr != sb, designed, sb, sr))

    # ---------- 硬门 ----------
    rsl_rdcd = [str(r[D["rsl_fields"].index("RD_CD")]).strip() for r in D["rsl_records"]] \
        if "RD_CD" in D["rsl_fields"] else []
    rdcd_fill = (sum(1 for v in rsl_rdcd if v) / len(rsl_rdcd)) if rsl_rdcd else 0.0
    rdcd_dist = len(set(v for v in rsl_rdcd if v))
    noname = sum(1 for v in rsl_rdcd if v == "NONAME")
    n_len5 = sum(1 for v in rsl_rdcd if len(v) == 5)
    gates = []
    gates.append(("G-O3R1-1", all(v["resolved_path"] for v in resolution.values()),
                  {k: v["resolved_path"] for k, v in resolution.items()}))
    gates.append(("G-O3R1-2",
                  len(D["rsl_records"]) == EXP_RSL_N and abs(rdcd_fill - 1.0) < 1e-9
                  and rdcd_dist == EXP_RSL_RDCD_DISTINCT and len(D["rsl_fields"]) == EXP_RSL_FIELDS,
                  dict(n=len(D["rsl_records"]), fields=len(D["rsl_fields"]),
                       rdcd_fill=round(rdcd_fill, 6), rdcd_distinct=rdcd_dist)))
    gates.append(("G-O3R1-3",
                  D["det_n"] == EXP_DET_N and len(D["det_fields"]) == EXP_DET_FIELDS
                  and not D["det_has_rdcd_native"],
                  dict(n=D["det_n"], fields=len(D["det_fields"]), has_rdcd=D["det_has_rdcd_native"])))
    s_rsl, s_det = D["schema"]["rsl"], D["schema"]["det"]
    gates.append(("G-O3R1-4",
                  bool(s_rsl) and bool(s_det) and s_rsl[2] == EXP_RSL_UNION and s_det[2] == EXP_DET_UNION,
                  dict(rsl=dict(fgdc=s_rsl[0], addfield=s_rsl[1], union=s_rsl[2]) if s_rsl else None,
                       det=dict(fgdc=s_det[0], addfield=s_det[1], union=s_det[2]) if s_det else None,
                       exp=dict(rsl_union=EXP_RSL_UNION, det_union=EXP_DET_UNION))))
    rb, db = D["rsl_bbox"], D["det_bbox"]
    secg_ok = bool(len(D["secg_xy"])) and bool(np.nanmin(D["secg_xy"][:, 0]) > 1000) \
        and bool(np.nanmax(D["secg_xy"][:, 0]) < 60000)
    same_domain = bool(rb and db and rb[0] < db[2] and db[0] < rb[2]
                       and rb[1] < db[3] and db[1] < rb[3] and secg_ok)
    gates.append(("G-O3R1-5", same_domain,
                  dict(rsl_bbox=[round(x, 1) for x in rb] if rb else None,
                       det_bbox=[round(x, 1) for x in db] if db else None,
                       secg_x_range=[round(float(np.nanmin(D["secg_xy"][:, 0])), 1),
                                     round(float(np.nanmax(D["secg_xy"][:, 0])), 1)] if secg_ok else None,
                       crs="EPSG:3414")))
    gates.append(("G-O3R1-6", noname == EXP_PLACEHOLDER_NONAME, dict(noname=noname, len5=n_len5)))
    gates.append(("G-O3R1-7",
                  base["hop1"]["n_matched_left"] > 0 and base["hop2"]["n_matched_left"] > 0
                  and base["hop3"]["n_matched_left"] > 0,
                  dict(h1=base["hop1"]["n_matched_left"], h2=base["hop2"]["n_matched_left"],
                       h3=base["hop3"]["n_matched_left"])))
    tot = sum(base["tier_counts"].values())
    gates.append(("G-O3R1-8", tot == EXP_TF_N, dict(total=tot, **base["tier_counts"])))
    src = Path(__file__).read_text(encoding="utf-8")
    banned_hits = set()
    for n in ast.walk(ast.parse(src)):
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) \
                and n.func.attr in {"system", "popen", "run", "Popen", "call", "check_output"}:
            banned_hits.add(n.func.attr)
        if isinstance(n, ast.Import):
            for a in n.names:
                if a.name.split(".")[0] in {"subprocess", "java"}:
                    banned_hits.add("import:" + a.name)
    gates.append(("G-O3R1-9", len(banned_hits) == 0, dict(banned=sorted(banned_hits))))
    v10_after = None
    if V10_DIR.exists():
        v10_after = {str(f.relative_to(V10_DIR)): f.stat().st_mtime_ns
                     for f in sorted(V10_DIR.rglob("*")) if f.is_file()}
    changed_v10 = sorted(k for k in set(v10_before or {}) | set(v10_after or {})
                         if (v10_before or {}).get(k) != (v10_after or {}).get(k))
    gates.append(("G-O3R1-10", len(changed_v10) == 0,
                  dict(n_files=len(v10_before or {}), changed=changed_v10)))
    can_after = snapshot(CANON)
    changed_can = sorted(k for k in can_before if can_before[k] != can_after[k])
    gates.append(("G-O3R1-11", len(changed_can) == 0,
                  dict(canonical_files=[Path(k).name for k in can_before], changed=changed_can)))
    gates.append(("G-O3R1-13",
                  sum(frozen["tier_counts"].values()) == EXP_TF_N
                  and sum(base["tier_counts"].values()) == EXP_TF_N
                  and frozen["tier_counts"] != base["tier_counts"],
                  dict(frozen_directed=frozen["tier_counts"], axial_corrected=base["tier_counts"],
                       note="§0 方向轴更正（有向→轴向）：两轴均完备(Tier 合计=1,278)且互异 ⇒ 非死代码")))
    gates.append(("G-O3R1-14",
                  base["tier_counts"]["A"] != base["tier_counts_alt_tie"]["A"]
                  and sum(base["tier_counts"].values()) == EXP_TF_N
                  and sum(base["tier_counts_alt_tie"].values()) == EXP_TF_N,
                  dict(uniq_rdcd=base["tier_counts"], uniq_tie=base["tier_counts_alt_tie"],
                       note="§0.2 唯一性细化轴：rdcd（生效）vs tie（预注册原文），两轴均完备且互异")))

    n = EXP_TF_N
    tierA_cov, tierX_cov = base["tier_counts"]["A"] / n, base["tier_counts"]["X"] / n
    fA_cov = frozen["tier_counts"]["A"] / n
    if not all(v["resolved_path"] for v in resolution.values()):
        verdict, status = "O3R1_BLOCKED_INPUT", "BLOCKED"
    elif tierA_cov < 0.50:
        verdict, status = "OBSERVATION_DOMAIN_PARTIAL", "PARTIAL"
    elif tierX_cov <= 0.10:
        verdict, status = "FACILITY_IDENTITY_UNAVAILABLE_BUT_OBSERVATION_DOMAIN_RECOVERABLE", "RECOVERED"
    else:
        verdict, status = "OBSERVATION_DOMAIN_RECOVERABLE_WITH_UNMAPPED", "RECOVERED_PARTIAL"

    say("[4] 判决：status=%s verdict=%s（轴向 TierA 覆盖=%.4f · TierX 覆盖=%.4f；有向 TierA 覆盖=%.4f）"
        % (status, verdict, tierA_cov, tierX_cov, fA_cov))

    # ---------- 落盘 ----------
    def wj(name, obj):
        p = OUT / name
        p.write_text(json.dumps(obj, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
        say("  wrote %s (%d B)" % (name, p.stat().st_size))

    df = base["df"].copy()
    df["in_576"] = df.LinkID.map(lambda s: int(s in D["cw_set"]))
    df["is_F_LOW"] = df.LinkID.map(lambda s: int(s in F_LOW))
    df["is_B_SET"] = df.LinkID.map(lambda s: int(s in B_SET))
    df["is_F_ADQ"] = df.LinkID.map(lambda s: int(s in F_ADQ))
    cols = ["LinkID", "RoadName", "RoadCat", "in_576", "is_F_LOW", "is_B_SET", "is_F_ADQ",
            "TF_LENGTH", "d_rsl", "ang_rsl", "RD_CD", "n_rsl", "rsl_unique",
            "uniq_tie", "uniq_rdcd", "code_term",
            "MATCH_SCORE", "n_placeholder", "N_MATSIM", "MATSIM_LENGTH", "hw_mix",
            "crosswalk_K", "LOOP_DISTANCE", "N_LOOP_NEAR", "LOOP_BAND", "TIER"]
    df[cols].to_csv(OUT / "o3r1_tier_cards.csv", index=False, encoding="utf-8-sig")
    df[["LinkID", "d_rsl", "ang_rsl", "RD_CD", "n_rsl", "rsl_unique", "uniq_tie", "uniq_rdcd",
        "code_term", "MATCH_SCORE", "n_placeholder", "d_rsl_near", "ang_rsl_near",
        "RD_CD_near"]].to_csv(OUT / "o3r1_tf_to_rsl.csv", index=False, encoding="utf-8-sig")
    df[["LinkID", "N_MATSIM", "MATSIM_LENGTH", "hw_mix", "crosswalk_K"]].to_csv(
        OUT / "o3r1_tf_to_matsim.csv", index=False, encoding="utf-8-sig")
    df[["LinkID", "LOOP_DISTANCE", "N_LOOP_NEAR", "LOOP_BAND"]].to_csv(
        OUT / "o3r1_loop_proximity.csv", index=False, encoding="utf-8-sig")
    pd.DataFrame(anchors_rows).to_csv(OUT / "o3r1_anchor_audit.csv", index=False, encoding="utf-8-sig")
    hs = pd.DataFrame([dict(hop="1_TF_to_RSL", **base["hop1"]),
                       dict(hop="2_TF_to_MATSim", **base["hop2"]),
                       dict(hop="3_TF_to_LOOP", **base["hop3"])])
    hs.to_csv(OUT / "o3r1_hop_stats.csv", index=False, encoding="utf-8-sig")
    pd.DataFrame(sens_rows).to_csv(OUT / "o3r1_threshold_sensitivity.csv", index=False,
                                   encoding="utf-8-sig")
    scale = dict(
        n=int(len(df)),
        by_tier={t: dict(n=int((df.TIER == t).sum()),
                         TF_LENGTH_med=round(float(df.loc[df.TIER == t, "TF_LENGTH"].median()), 2)
                         if (df.TIER == t).any() else None,
                         N_MATSIM_med=float(df.loc[df.TIER == t, "N_MATSIM"].median())
                         if (df.TIER == t).any() else None,
                         MATSIM_LENGTH_med=round(float(df.loc[df.TIER == t, "MATSIM_LENGTH"].median()), 2)
                         if (df.TIER == t).any() else None,
                         LOOP_DISTANCE_med=round(float(df.loc[df.TIER == t, "LOOP_DISTANCE"].apply(
                             pd.to_numeric, errors="coerce").median()), 2) if (df.TIER == t).any() else None)
                 for t in ["A", "B", "C", "X"]},
        overall=dict(TF_LENGTH_med=round(float(df.TF_LENGTH.median()), 2),
                     N_MATSIM_med=float(df.N_MATSIM.median()),
                     MATSIM_LENGTH_med=round(float(df.MATSIM_LENGTH.median()), 2)),
        near_distance_diagnostic=near_diag,
        threshold_sensitivity=sens_rows,
        criterion_contribution=crit,
        tier_counts_alt_tie=base["tier_counts_alt_tie"],
        target576=s576)
    df[["LinkID", "TF_LENGTH", "N_MATSIM", "MATSIM_LENGTH", "N_LOOP_NEAR", "LOOP_DISTANCE",
        "MATCH_SCORE", "TIER"]].to_csv(OUT / "o3r1_obs_scale.csv", index=False, encoding="utf-8-sig")
    wj("o3r1_input_resolution.json", resolution)
    wj("o3r1_rsl_identity.json", dict(
        rsl=dict(n=len(D["rsl_records"]), fields=D["rsl_fields"], rdcd_fill=round(rdcd_fill, 6),
                 rdcd_distinct=rdcd_dist, noname=noname, len5=n_len5, bbox=D["rsl_bbox"]),
        det=dict(n=D["det_n"], fields=D["det_fields"], has_rdcd=D["det_has_rdcd_native"],
                 bbox=D["det_bbox"]),
        schema=D["schema"], paths=dict(rsl=D["rsl_path"], det=D["det_path"]),
        obs=dict(rd_nam_stripped=True, placeholder_noname=noname)))
    wj("o3r1_obs_scale.json", scale)

    def write_closure(extra=None):
        row = dict(state_in="O3-DATA-RECOVERY ✓ → READY(O3-R1)", status=status, verdict=verdict,
                   tier_A=base["tier_counts"]["A"], tier_B=base["tier_counts"]["B"],
                   tier_C=base["tier_counts"]["C"], tier_X=base["tier_counts"]["X"],
                   tier_A_frozen_directed=frozen["tier_counts"]["A"],
                   tier_X_frozen_directed=frozen["tier_counts"]["X"],
                   tier_A_uniq_tie_axis=base["tier_counts_alt_tie"]["A"],
                   axis_correction="axial (§0) + uniq_rdcd (§0.2)",
                   tierA_coverage=round(tierA_cov, 6), tierX_coverage=round(tierX_cov, 6),
                   n_tf=EXP_TF_N, det_has_rdcd=int(base["det_has_rdcd"]),
                   B_BINDING_UNDECIDABLE="UNCHANGED", canonical_median_overwritten=0,
                   v1_0_changed=len(changed_v10), produces_v1_1=0)
        if extra:
            row.update(extra)
        pd.DataFrame([{"item": k, "value": v} for k, v in row.items()]).to_csv(
            OUT / "o3r1_closure.csv", index=False, encoding="utf-8-sig")

    write_closure()
    n_pass0 = sum(1 for _, o, _ in gates if o)
    neg_ok = all(r["fired"] and r["hit"] for r in neg)
    gates.append(("G-O3R1-12", (n_pass0 == len(gates)) and neg_ok,
                  dict(n_before=len(gates), n_pass_before=n_pass0, neg_all=neg_ok)))
    n_pass = sum(1 for _, o, _ in gates if o)
    pd.DataFrame([dict(gate=g, ok=int(bool(o)), detail=json.dumps(d, ensure_ascii=False))
                  for g, o, d in gates]).to_csv(OUT / "o3r1_checks.csv", index=False,
                                                encoding="utf-8-sig")
    write_closure(extra=dict(gates_verdict="O3R1_GATES_PASS" if n_pass == len(gates)
                             else "O3R1_GATES_FAIL", n_gates_pass="%d/%d" % (n_pass, len(gates))))
    say("gates = %s (%d/%d)"
        % ("O3R1_GATES_PASS" if n_pass == len(gates) else "O3R1_GATES_FAIL", n_pass, len(gates)))
    say("  neg: " + ", ".join("%s=%d/%d" % (r["id"], r["fired"], r["hit"]) for r in neg))

    wj("o3r1_summary.json", dict(step="7.9I-O3-R1", verdict=verdict, status=status,
                                 tier_counts=base["tier_counts"],
                                 tier_counts_frozen_directed=frozen["tier_counts"],
                                 tier_counts_alt_tie=base["tier_counts_alt_tie"],
                                 axis_correction="axial (§0) + uniq_rdcd (§0.2)",
                                 criterion_contribution=crit,
                                 hop1=base["hop1"], hop2=base["hop2"], hop3=base["hop3"],
                                 anchors=anchors_rows, target576=s576, obs_scale=scale,
                                 gates=[dict(g=g, ok=int(bool(o)), d=d) for g, o, d in gates],
                                 negatives=neg, params_effective=EFF, params_frozen=BASE))
    prods = sorted(p.name for p in OUT.glob("o3r1_*") if p.name != "o3r1_manifest.json")
    wj("o3r1_manifest.json", dict(step="7.9I-O3-R1", generated_last=True, self_hashed=False,
                                  products=[dict(name=x, size=(OUT / x).stat().st_size) for x in prods],
                                  n_products=len(prods),
                                  note="manifest 在本步最后生成；不参与自哈希（承 readme §4 契约纪律）"))
    say("done in %.1fs" % (time.time() - t0))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
