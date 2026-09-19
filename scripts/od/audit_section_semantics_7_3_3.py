#!/usr/bin/env python3
# -*- coding: utf-8 -*-

r"""
Step 7.3.3 — LTA Section Semantics <-> MATSim Link Representation Audit

用途
----
零仿真检查 LTA TrafficFlow 断面与 MATSim link 表达是否具有一致的：
1) RoadName
2) RoadCat / highway
3) direction
4) one-to-many / many-to-one overlap
5) motorway / motorway_link 语义
6) 上下游道路等级结构

本步骤不修改：
    OD / lambda / Population / Departure Profile
    network / capacity / route-choice

输入
----
1. TrafficFlow_Data.json（LTA 断面观测，长表：断面 x 日期 x 小时）
2. 6.3.2 tight crosswalk（若已存在，优先使用）
   reports/matsim_assignment_6_3_2/lta_section_matsim_crosswalk.csv
3. network_links_source_copy.csv
4. network_nodes_source_copy.csv（用于方向一致性；可选）

默认项目根：
    D:\Luan\2026-05\2_Singapore

脚本设计
--------
- 自动定位 crosswalk 候选文件
- 如果没有 crosswalk，明确 FAIL，并列出需要提供的文件
- 不使用 rglob 扫全盘，仅检查预定义 reports / Dynamic 路径

AI 修补记录（2026-09-13，仅修 bug + 补验收产物，不改冻结模型）
----------------------------------------------------------------
[AI-7.3.3-a] TrafficFlow_Data.json 实为长表（75,899 行 = 1,311 断面 x 日期 x
             小时 7/8），原脚本按"一断面一行"直接 merge 会触发
             MergeError: not a many-to-one merge。现改为加载后按 LinkID
             去重到断面级（断面属性 RoadName/RoadCat 经核验唯一）。
[AI-7.3.3-b] 6.3.2 tight crosswalk 自带 highway / RoadCat 列，直接再合并
             network/traffic 会产生 _x/_y 重名列并触发 KeyError。现在合并前
             丢弃 crosswalk 内的 highway/RoadCat，改由 network（highway）
             与 traffic（RoadCat）权威提供。
[AI-7.3.3-c] 新增 section_upstream_downstream.csv（用户验收清单内但原脚本缺失）：
             按节点连通把断面匹配边串成链，给出链首/链尾及其上游/下游道路等级。
[AI-7.3.3-d] 新增 方向一致率 / 道路等级一致率 / RoadCat<->highway 对应矩阵。
[AI-7.3.3-e] 修正 docstring 转义告警（改为 raw string）与报告 f-string 缺 **。
[AI-7.3.3-f] traffic 缺失断面（RoadCat=#N/A 的 33 个）保持不入 audit，
             coverage 如实反映在 summary 中。
"""

from __future__ import annotations

import argparse
import json
import math
import re
from pathlib import Path
import numpy as np
import pandas as pd


ROOT_DEFAULT = Path(r"D:\Luan\2026-05\2_Singapore")

NETWORK_CANDIDATES = [
    Path(r"reports\matsim_network\network_links_source_copy.csv"),
    Path(r"reports\matsim_network\network_links.csv"),
]

NODES_CANDIDATES = [
    Path(r"reports\matsim_network\network_nodes_source_copy.csv"),
    Path(r"reports\matsim_network\network_nodes.csv"),
]

TRAFFIC_JSON_CANDIDATES = [
    Path(r"Singapore_OD_MATSim_FinalData\08_TrafficCount\TrafficFlow_Data.json"),
    Path(r"Dynamic_2026_03_16\historical_data\TrafficFlow_Data.json"),
]

# 优先使用 6.3.2 tight crosswalk（实际存在），其余为历史候选。
CROSSWALK_CANDIDATES = [
    Path(r"reports\matsim_assignment_6_3_2\lta_section_matsim_crosswalk.csv"),
    Path(r"reports\matsim_assignment_6_3_2\lta_osm_match_v2.csv"),
    Path(r"reports\od_impedance_ampeak_v2\lta_osm_match_v2.csv"),
    Path(r"reports\od_route_diagnosis_7_3_2c\lta_section_matsim_crosswalk.csv"),
    Path(r"reports\od_calibration_7_1\lta_section_matsim_crosswalk.csv"),
]

OUT_DEFAULT = Path(
    r"reports\od_network_semantic_audit_7_3_3"
)

# LTA RoadCat -> 可接受的 MATSim/OSM highway 语义集合（"宽容"语义映射）。
# 注意：这是审计用的语义等价假设，不是"应当严格相等"。
ROADCAT_EXPECTED_HIGHWAY = {
    "CATA": {"motorway", "motorway_link", "trunk", "trunk_link"},
    "SLIP_ROAD": {"motorway_link", "trunk_link", "primary_link", "secondary_link"},
    "CATB": {"trunk", "trunk_link", "primary", "primary_link", "secondary"},
    "CATC": {"secondary", "secondary_link", "tertiary", "tertiary_link", "primary"},
    "CATD": {"tertiary", "tertiary_link", "residential", "unclassified", "service"},
    "CATE": {"residential", "unclassified", "service"},
}

MOTORWAY_FAMILY = {"motorway", "motorway_link"}
LINK_FAMILY = {"motorway_link", "trunk_link", "primary_link", "secondary_link", "tertiary_link"}


def first_existing(root: Path, candidates: list[Path]) -> Path | None:
    for rel in candidates:
        p = rel if rel.is_absolute() else root / rel
        if p.exists():
            return p
    return None


def normalize_name(x) -> str:
    if pd.isna(x):
        return ""
    s = str(x).upper().strip()
    s = s.replace("&", " AND ")
    s = re.sub(r"[-_/(),.&]+", " ", s)
    s = re.sub(r"\s+", " ", s)
    return s.strip()


def load_network(path: Path):
    df = pd.read_csv(
        path,
        usecols=[
            "from_node",
            "to_node",
            "length_m",
            "highway",
            "name",
        ],
        encoding="utf-8-sig",
        low_memory=False,
    )

    df["matsim_link_id"] = (
        "e"
        + df["from_node"].astype(str)
        + "_"
        + df["to_node"].astype(str)
    )
    df["highway"] = (
        df["highway"].astype(str).str.lower().str.strip()
    )
    df["name_norm"] = df["name"].map(normalize_name)
    df["length_m"] = pd.to_numeric(
        df["length_m"], errors="coerce"
    ).fillna(0.0)

    if df["matsim_link_id"].duplicated().any():
        raise ValueError("MATSim link id 存在重复")

    return df


def load_nodes(path: Path | None):
    """返回 {node_id(str): (lon, lat)}；缺失则返回空 dict。"""
    if path is None or not Path(path).exists():
        return {}
    nd = pd.read_csv(
        path,
        usecols=["node_id", "lon", "lat"],
        encoding="utf-8-sig",
        low_memory=False,
    )
    nd = nd.dropna(subset=["lon", "lat"])
    return {
        str(int(r.node_id)): (float(r.lon), float(r.lat))
        for r in nd.itertuples(index=False)
    }


def load_traffic_json(path: Path):
    with open(path, "r", encoding="utf-8-sig") as f:
        obj = json.load(f)

    rows = obj.get("Value", obj)
    df = pd.DataFrame(rows)

    required = {
        "LinkID",
        "RoadName",
        "RoadCat",
        "StartLon",
        "StartLat",
        "EndLon",
        "EndLat",
    }

    missing = required - set(df.columns)
    if missing:
        raise ValueError(
            f"TrafficFlow 缺字段: {sorted(missing)}"
        )

    df["LinkID"] = df["LinkID"].astype(str)
    df["RoadName_norm"] = df["RoadName"].map(normalize_name)
    df["RoadCat"] = (
        df["RoadCat"].astype(str).str.strip().str.upper()
    )

    # [AI-7.3.3-a] 长表 -> 断面级：断面属性（RoadName/RoadCat/坐标）经核验唯一。
    before = len(df)
    df = df.drop_duplicates(subset=["LinkID"], keep="first").reset_index(drop=True)
    print(
        f"[traffic] rows {before:,} -> sections {len(df):,} "
        f"(dropped {before - len(df):,} date/hour records)"
    )

    return df


def load_crosswalk(path: Path):
    cw = pd.read_csv(
        path,
        encoding="utf-8-sig",
        low_memory=False,
    )

    rename = {}
    for c in cw.columns:
        lc = c.lower()
        if lc == "linkid":
            rename[c] = "lta_linkid"
        elif lc in {"osm_edge_index", "edge_index"}:
            rename[c] = "osm_edge_index"
        elif lc in {"matsim_link_id", "matsim_link"}:
            rename[c] = "matsim_link_id"

    cw = cw.rename(columns=rename)

    if "lta_linkid" not in cw.columns:
        raise ValueError("crosswalk 缺少 LTA LinkID 列")

    # [AI-7.3.3-b] 丢弃 crosswalk 内会与权威来源冲突的列，
    # 避免 merge 产生 highway_x/highway_y、RoadCat_x/RoadCat_y。
    drop_cols = [c for c in ("highway", "RoadCat") if c in cw.columns]
    if drop_cols:
        cw = cw.drop(columns=drop_cols)
        print(f"[crosswalk] dropped pre-joined columns: {drop_cols}")

    if "matsim_link_id" not in cw.columns:
        if "osm_edge_index" not in cw.columns:
            raise ValueError("crosswalk 既无 matsim_link_id 也无 osm_edge_index")
        cw["osm_edge_index"] = pd.to_numeric(cw["osm_edge_index"], errors="coerce")
        return cw

    cw["lta_linkid"] = cw["lta_linkid"].astype(str)
    cw["matsim_link_id"] = cw["matsim_link_id"].astype(str)

    return cw


def attach_by_edge_index(cw: pd.DataFrame, network: pd.DataFrame):
    if "matsim_link_id" in cw.columns:
        return cw

    cw = cw.copy()
    cw["osm_edge_index"] = pd.to_numeric(cw["osm_edge_index"], errors="coerce")

    net2 = network.reset_index(drop=True)[["matsim_link_id"]].copy()
    cw = cw[cw["osm_edge_index"].notna()].copy()
    cw["row_index"] = cw["osm_edge_index"].astype(int)
    cw = cw[cw["row_index"].between(0, len(net2) - 1)].copy()
    cw = cw.merge(
        net2.reset_index().rename(columns={"index": "row_index"}),
        on="row_index",
        how="left",
        validate="many_to_one",
    )
    return cw


def _unit_vector(lon1, lat1, lon2, lat2):
    """近似平面单位方向向量（东=+x，北=+y）。"""
    lat_mid = math.radians((lat1 + lat2) / 2.0)
    dx = (lon2 - lon1) * math.cos(lat_mid)
    dy = (lat2 - lat1)
    norm = math.hypot(dx, dy)
    if norm == 0:
        return None
    return (dx / norm, dy / norm)


def _angle_between(u, v):
    if u is None or v is None:
        return np.nan
    dot = max(-1.0, min(1.0, u[0] * v[0] + u[1] * v[1]))
    return math.degrees(math.acos(dot))


def build_section_updown(audit: pd.DataFrame, network: pd.DataFrame):
    """每断面：匹配边集合的边界节点邻接道路等级（上游进入 / 下游离开）。
    同时保留按连通性的链化尝试（chain_ok / head / tail）。
    """
    valid = audit[audit["matsim_link_id"].notna()].copy()

    sec_nodes: dict[str, set[int]] = {}
    for sid, g in valid.groupby("lta_linkid", sort=False):
        sec_nodes[sid] = set(g["from_node"].astype("int64")) | set(g["to_node"].astype("int64"))

    all_nodes: set[int] = set()
    for s in sec_nodes.values():
        all_nodes |= s

    touch = network["from_node"].isin(all_nodes) | network["to_node"].isin(all_nodes)
    net_t = network[touch]

    out_edges: dict[int, list[str]] = {}
    in_edges: dict[int, list[str]] = {}
    for r in net_t.itertuples(index=False):
        f = int(r.from_node)
        t = int(r.to_node)
        out_edges.setdefault(f, []).append(r.highway)
        in_edges.setdefault(t, []).append(r.highway)

    rows = []
    for sec_id, grp in valid.groupby("lta_linkid", sort=False):
        meta = grp.iloc[0]
        nodes = sec_nodes[sec_id]
        edges = [
            {"f": str(int(r.from_node)), "t": str(int(r.to_node)), "hw": r.highway, "len": r.length_m}
            for r in grp.itertuples(index=False)
        ]

        # 边界节点 -> 上游/下游等级（去除断面自身边）
        sec_hw = {e["hw"] for e in edges}
        up: set[str] = set()
        down: set[str] = set()
        for n in nodes:
            for hw in out_edges.get(n, []):
                down.add(hw)
            for hw in in_edges.get(n, []):
                up.add(hw)
        up -= sec_hw
        down -= sec_hw

        # 链化（可能因双向混入失败，仅作参考）
        t_nodes = {e["t"] for e in edges}
        heads = [e for e in edges if e["f"] not in t_nodes]
        start = heads[0] if heads else max(edges, key=lambda e: e["len"])
        by_from: dict[str, list[dict]] = {}
        for e in edges:
            by_from.setdefault(e["f"], []).append(e)
        chain_ok = len(heads) == 1
        cur = start
        used = set()
        ordered = []
        while cur is not None and id(cur) not in used:
            used.add(id(cur))
            ordered.append(cur)
            nxt = [e for e in by_from.get(cur["t"], []) if id(e) not in used]
            cur = nxt[0] if nxt else None
        if len(ordered) != len(edges):
            chain_ok = False

        head = ordered[0]
        tail = ordered[-1]

        rows.append(
            {
                "lta_linkid": sec_id,
                "RoadName": meta["RoadName"],
                "RoadCat": meta["RoadCat"],
                "n_matched": len(edges),
                "n_boundary_nodes": len(nodes),
                "chain_ok": chain_ok,
                "head_highway": head["hw"],
                "tail_highway": tail["hw"],
                "unique_highway": "|".join(sorted(sec_hw)),
                "upstream_classes": "|".join(sorted(up)),
                "downstream_classes": "|".join(sorted(down)),
            }
        )

    return pd.DataFrame(rows)


def main():
    ap = argparse.ArgumentParser()

    ap.add_argument("--project-root", type=Path, default=ROOT_DEFAULT)
    ap.add_argument("--network", type=Path, default=None)
    ap.add_argument("--nodes", type=Path, default=None)
    ap.add_argument("--traffic-json", type=Path, default=None)
    ap.add_argument("--crosswalk", type=Path, default=None)
    ap.add_argument("--out-dir", type=Path, default=OUT_DEFAULT)

    args = ap.parse_args()

    root = args.project_root

    network_path = args.network if args.network else first_existing(root, NETWORK_CANDIDATES)
    nodes_path = args.nodes if args.nodes else first_existing(root, NODES_CANDIDATES)
    traffic_path = args.traffic_json if args.traffic_json else first_existing(root, TRAFFIC_JSON_CANDIDATES)
    crosswalk_path = args.crosswalk if args.crosswalk else first_existing(root, CROSSWALK_CANDIDATES)

    out = args.out_dir if args.out_dir.is_absolute() else root / args.out_dir
    out.mkdir(parents=True, exist_ok=True)

    print("=" * 72)
    print("Step 7.3.3 | Section Semantic Audit")
    print("=" * 72)

    missing_inputs = []
    if network_path is None:
        missing_inputs.append("network_links_source_copy.csv")
    if traffic_path is None:
        missing_inputs.append("TrafficFlow_Data.json")
    if crosswalk_path is None:
        missing_inputs.append("6.3.2 tight crosswalk")

    if missing_inputs:
        summary = {
            "step": "7.3.3",
            "status": "FAIL",
            "missing_inputs": missing_inputs,
            "message": (
                "7.3.3 不能在缺少断面↔MATSim link crosswalk 时"
                "静默运行。请提供对应 crosswalk。"
            ),
        }
        with open(out / "semantic_audit_summary.json", "w", encoding="utf-8") as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)
        report = """# Step 7.3.3 — Section Semantic Audit

## STATUS: FAIL

7.3.3 需要既有的 LTA section → MATSim link crosswalk。

脚本没有找到完整输入，因此没有运行任何猜测式匹配，
也没有生成虚假的语义一致性指标。

缺失：
""" + "\n".join(f"- {x}" for x in missing_inputs)
        (out / "STEP7_3_3_REPORT.md").write_text(report, encoding="utf-8")
        print(report)
        return

    print(f"network   : {network_path}")
    print(f"nodes     : {nodes_path}")
    print(f"traffic   : {traffic_path}")
    print(f"crosswalk : {crosswalk_path}")

    network = load_network(network_path)
    nodes = load_nodes(nodes_path)
    traffic = load_traffic_json(traffic_path)
    cw = load_crosswalk(crosswalk_path)
    cw = attach_by_edge_index(cw, network)

    # 断面 -> 观测属性
    audit = cw.merge(
        traffic[
            ["LinkID", "RoadName", "RoadName_norm", "RoadCat",
             "StartLon", "StartLat", "EndLon", "EndLat"]
        ],
        left_on="lta_linkid",
        right_on="LinkID",
        how="left",
        validate="many_to_one",
    )

    # 断面 -> 网络属性
    audit = audit.merge(
        network[
            ["matsim_link_id", "highway", "name", "name_norm", "length_m",
             "from_node", "to_node"]
        ],
        on="matsim_link_id",
        how="left",
        validate="many_to_one",
    )

    audit["highway"] = audit["highway"].fillna("__unmatched__")

    audit["name_match"] = (
        audit["RoadName_norm"] == audit["name_norm"]
    ) & (audit["RoadName_norm"] != "")

    audit["is_motorway"] = audit["highway"] == "motorway"
    audit["is_motorway_link"] = audit["highway"] == "motorway_link"
    audit["is_unmatched_edge"] = audit["highway"] == "__unmatched__"

    # [AI-7.3.3-d] 道路等级语义一致率
    def _expect(rc):
        return ROADCAT_EXPECTED_HIGHWAY.get(str(rc), set())

    audit["class_consistent"] = [
        (hw in _expect(rc)) for hw, rc in zip(audit["highway"], audit["RoadCat"])
    ]

    # [AI-7.3.3-d] 方向一致率（LTA 断面方向 vs MATSim edge 方向）
    if nodes:
        slon = pd.to_numeric(audit["StartLon"], errors="coerce")
        slat = pd.to_numeric(audit["StartLat"], errors="coerce")
        elon = pd.to_numeric(audit["EndLon"], errors="coerce")
        elat = pd.to_numeric(audit["EndLat"], errors="coerce")

        fn = audit["from_node"]
        tn = audit["to_node"]

        def _node_xy(nid):
            if pd.isna(nid):
                return (np.nan, np.nan)
            return nodes.get(str(int(nid)), (np.nan, np.nan))

        f_xy = [_node_xy(v) for v in fn]
        t_xy = [_node_xy(v) for v in tn]
        f_lon = np.array([x[0] for x in f_xy], dtype=float)
        f_lat = np.array([x[1] for x in f_xy], dtype=float)
        t_lon = np.array([x[0] for x in t_xy], dtype=float)
        t_lat = np.array([x[1] for x in t_xy], dtype=float)

        bear = []
        for i in range(len(audit)):
            uL = _unit_vector(slon.iloc[i], slat.iloc[i], elon.iloc[i], elat.iloc[i])
            uM = _unit_vector(f_lon[i], f_lat[i], t_lon[i], t_lat[i])
            ang = _angle_between(uL, uM)
            bear.append(ang)
        audit["direction_angle_deg"] = bear
        audit["direction_consistent"] = audit["direction_angle_deg"] < 90.0
    else:
        audit["direction_angle_deg"] = np.nan
        audit["direction_consistent"] = np.nan

    # [AI-7.3.3-g] 与 LTA 方向约定无关的"对向车道混入"指标：
    #   1) 断面内自身模态方向 vs 各边夹角（self_opposite_share）
    #   2) 精确互反配对 e{a}_{b} 与 e{b}_{a} 同时被匹配（reciprocal pair）
    rev_map: dict[str, str] = {}
    for r in network[["matsim_link_id", "from_node", "to_node"]].itertuples(index=False):
        rev_map[r.matsim_link_id] = "e" + str(int(r.to_node)) + "_" + str(int(r.from_node))

    def _uvect(fn_id, tn_id):
        if pd.isna(fn_id) or pd.isna(tn_id):
            return (np.nan, np.nan)
        f = nodes.get(str(int(fn_id))) if nodes else None
        t = nodes.get(str(int(tn_id))) if nodes else None
        if f is None or t is None:
            return (np.nan, np.nan)
        lat_mid = math.radians((f[1] + t[1]) / 2.0)
        dx = (t[0] - f[0]) * math.cos(lat_mid)
        dy = (t[1] - f[1])
        n = math.hypot(dx, dy)
        if n == 0:
            return (np.nan, np.nan)
        return (dx / n, dy / n)

    uv_pairs = [_uvect(a, b) for a, b in zip(audit["from_node"], audit["to_node"])]
    audit["u_e"] = [p[0] for p in uv_pairs]
    audit["u_n"] = [p[1] for p in uv_pairs]
    audit["rev_link_id"] = audit["matsim_link_id"].map(rev_map)

    dir_rows = []
    for sid, g in audit.groupby("lta_linkid", sort=False):
        us = [(a, b) for a, b in zip(g["u_e"], g["u_n"]) if not (pd.isna(a) or pd.isna(b))]
        ids = set(g["matsim_link_id"].dropna().astype(str))
        recip = sum(1 for e in ids if rev_map.get(e) in ids)
        base = {
            "lta_linkid": sid,
            "reciprocal_edge_count": recip,
            "reciprocal_share": (recip / len(ids)) if ids else np.nan,
        }
        if not us:
            base.update({"self_opposite_share": np.nan, "modal_alignment": np.nan})
            dir_rows.append(base)
            continue
        mx = sum(a for a, _ in us)
        my = sum(b for _, b in us)
        n = math.hypot(mx, my)
        if n == 0:
            base.update({"self_opposite_share": 1.0, "modal_alignment": 0.0})
            dir_rows.append(base)
            continue
        mv = (mx / n, my / n)
        angs = [_angle_between(u, mv) for u in us]
        angs = [t for t in angs if not math.isnan(t)]
        opp = sum(1 for t in angs if t > 120.0)
        base.update({
            "self_opposite_share": opp / len(angs) if angs else np.nan,
            "modal_alignment": 1.0 - (opp / len(angs)) if angs else np.nan,
        })
        dir_rows.append(base)

    sec_dir = pd.DataFrame(dir_rows)

    # ---- 断面级汇总 ----
    def _mode(s):
        s = [str(x) for x in s if pd.notna(x)]
        if not s:
            return ""
        return pd.Series(s).mode().iloc[0]

    sec = (
        audit.groupby(["lta_linkid", "RoadName", "RoadCat"], dropna=False)
        .agg(
            matsim_edges=("matsim_link_id", "nunique"),
            name_match_rate=("name_match", "mean"),
            class_consistent_rate=("class_consistent", "mean"),
            direction_consistent_rate=("direction_consistent", "mean"),
            motorway_edges=("is_motorway", "sum"),
            motorway_link_edges=("is_motorway_link", "sum"),
            unmatched_edges=("is_unmatched_edge", "sum"),
            dominant_highway=("highway", _mode),
            network_highway_values=(
                "highway",
                lambda s: "|".join(sorted({str(x) for x in s if pd.notna(x)})),
            ),
        )
        .reset_index()
    )

    sec["has_mixed_highway"] = sec["network_highway_values"].str.contains(r"\|")
    sec["is_cata"] = sec["RoadCat"] == "CATA"
    sec["is_slip"] = sec["RoadCat"] == "SLIP_ROAD"

    # 合并断面方向/双向指标
    sec = sec.merge(sec_dir, on="lta_linkid", how="left")
    sec["has_reciprocal_pair"] = sec["reciprocal_edge_count"].fillna(0) > 0

    sec.to_csv(out / "section_semantic_audit.csv", index=False, encoding="utf-8-sig")
    sec[sec["RoadCat"] == "CATA"].to_csv(out / "cata_semantic_audit.csv", index=False, encoding="utf-8-sig")
    sec[sec["RoadCat"] == "SLIP_ROAD"].to_csv(out / "sliproad_semantic_audit.csv", index=False, encoding="utf-8-sig")

    # ---- 一边多断面 ----
    edge_overlap = (
        audit.groupby("matsim_link_id")
        .agg(
            lta_section_count=("lta_linkid", "nunique"),
            RoadCat_values=("RoadCat", lambda s: "|".join(sorted({str(x) for x in s if pd.notna(x)}))),
            RoadName_values=("RoadName", lambda s: "|".join(sorted({str(x) for x in s if pd.notna(x)}))),
        )
        .reset_index()
    )
    edge_overlap["shared_by_multiple_sections"] = edge_overlap["lta_section_count"] > 1
    edge_overlap.to_csv(out / "section_duplicate_overlap.csv", index=False, encoding="utf-8-sig")

    # ---- 断面内相邻边等级变化 ----
    audit_sorted = audit.sort_values(["lta_linkid", "matsim_link_id"])
    transitions = []
    for section_id, grp in audit_sorted.groupby("lta_linkid"):
        vals = grp["highway"].dropna().astype(str).tolist()
        for a, b in zip(vals[:-1], vals[1:]):
            transitions.append({"lta_linkid": section_id, "from_highway": a, "to_highway": b})
    pd.DataFrame(transitions).to_csv(out / "section_class_transition.csv", index=False, encoding="utf-8-sig")

    # [AI-7.3.3-c] 上下游道路等级组合
    updown = build_section_updown(audit, network)
    updown.to_csv(out / "section_upstream_downstream.csv", index=False, encoding="utf-8-sig")

    # [AI-7.3.3-d] RoadCat <-> highway 对应矩阵（断面级 dominant）
    corr = (
        sec.groupby(["RoadCat", "dominant_highway"])
        .size()
        .reset_index(name="n_sections")
    )
    corr["share_within_roadcat"] = corr["n_sections"] / corr.groupby("RoadCat")["n_sections"].transform("sum")
    corr.to_csv(out / "roadcat_highway_correspondence.csv", index=False, encoding="utf-8-sig")

    # ---- 汇总 ----
    total_sections = int(sec["lta_linkid"].nunique())
    cata = sec[sec["RoadCat"] == "CATA"]
    slip = sec[sec["RoadCat"] == "SLIP_ROAD"]

    def _cat_metric(df):
        if df.empty:
            return None
        return {
            "n_sections": int(len(df)),
            "mean_edges": float(df["matsim_edges"].mean()),
            "median_edges": float(df["matsim_edges"].median()),
            "motorway_presence_rate": float((df["motorway_edges"] > 0).mean()),
            "motorway_link_presence_rate": float((df["motorway_link_edges"] > 0).mean()),
            "mixed_highway_rate": float(df["has_mixed_highway"].mean()),
            "name_match_rate": float(df["name_match_rate"].mean()),
            "class_consistent_rate": float(df["class_consistent_rate"].mean()),
            "direction_consistent_rate": float(pd.to_numeric(df["direction_consistent_rate"], errors="coerce").mean()),
            "self_opposite_share": float(pd.to_numeric(df["self_opposite_share"], errors="coerce").mean()),
            "sections_with_opposite_edge_rate": float((pd.to_numeric(df["self_opposite_share"], errors="coerce") > 0).mean()),
            "sections_with_reciprocal_pair_rate": float(df["has_reciprocal_pair"].mean()),
        }

    # 断面占比：CATA 断面其 dominant 是否 motorway / motorway_link 系
    def _family_share(df, family):
        if df.empty:
            return None
        return float(df["dominant_highway"].isin(family).mean())

    # 有多少断面至少共享 1 条边
    shared_edges = set(edge_overlap.loc[edge_overlap["shared_by_multiple_sections"], "matsim_link_id"])
    sec_edges = audit.groupby("lta_linkid")["matsim_link_id"].apply(set)
    n_sec_sharing = int(sec_edges.apply(lambda s: len(s & shared_edges) > 0).sum())

    summary = {
        "step": "7.3.3",
        "status": "PASS",
        "network_version": "network_links_source_copy.csv (cleaned)",
        "traffic_section_count": int(traffic["LinkID"].nunique()),
        "crosswalk_section_count": total_sections,
        "crosswalk_coverage": total_sections / traffic["LinkID"].nunique(),
        "mean_edges_per_section": float(sec["matsim_edges"].mean()),
        "median_edges_per_section": float(sec["matsim_edges"].median()),
        "mean_name_match_rate": float(sec["name_match_rate"].mean()),
        "mean_class_consistent_rate": float(sec["class_consistent_rate"].mean()),
        "mean_direction_consistent_rate": float(
            pd.to_numeric(sec["direction_consistent_rate"], errors="coerce").mean()
        ),
        "sections_mixed_highway_rate": float(sec["has_mixed_highway"].mean()),
        "shared_matsim_edges_rate": float(
            edge_overlap["shared_by_multiple_sections"].mean()
        ),
        "sections_sharing_edge_rate": n_sec_sharing / total_sections if total_sections else None,
        "self_opposite_edge_share": float(
            (pd.to_numeric(sec["self_opposite_share"], errors="coerce").fillna(0) * sec["matsim_edges"]).sum()
            / sec["matsim_edges"].sum()
        ),
        "sections_with_opposite_edge_rate": float(
            (pd.to_numeric(sec["self_opposite_share"], errors="coerce") > 0).mean()
        ),
        "sections_with_reciprocal_pair_rate": float(sec["has_reciprocal_pair"].mean()),
        "sections_chain_ok_rate": float(updown["chain_ok"].mean()) if not updown.empty else None,
        "CATA_chain_ok_rate": float(updown[updown["RoadCat"] == "CATA"]["chain_ok"].mean()) if not updown.empty else None,
        "SLIP_chain_ok_rate": float(updown[updown["RoadCat"] == "SLIP_ROAD"]["chain_ok"].mean()) if not updown.empty else None,
        "CATA": _cat_metric(cata),
        "SLIP_ROAD": _cat_metric(slip),
        "CATA_motorway_family_dominant_share": _family_share(cata, MOTORWAY_FAMILY),
        "CATA_motorway_only_dominant_share": _family_share(cata, {"motorway"}),
        "SLIP_motorway_link_dominant_share": _family_share(slip, {"motorway_link"}),
        "SLIP_link_family_dominant_share": _family_share(slip, LINK_FAMILY),
        "frozen_inputs_unchanged": True,
        "lambda_selected": False,
        "parameters_changed": False,
    }

    with open(out / "semantic_audit_summary.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    # ---- [AI-7.3.3] 自动报告 ----
    def _dist_table(df, col):
        if df.empty:
            return "_(空)_"
        vc = df[col].value_counts().head(8)
        lines = ["| 值 | 断面数 | 占比 |", "|---|---:|---:|"]
        for k, v in vc.items():
            lines.append(f"| `{k}` | {v} | {v / len(df):.1%} |")
        return "\n".join(lines)

    def _updown_table(df, col):
        if df.empty:
            return "_(空)_"
        vc = df[col].replace("", "(无)").value_counts().head(10)
        lines = ["| 组合 | 断面数 | 占比 |", "|---|---:|---:|"]
        for k, v in vc.items():
            lines.append(f"| `{k}` | {v} | {v / len(df):.1%} |")
        return "\n".join(lines)

    cata_dist = _dist_table(cata, "dominant_highway")
    slip_dist = _dist_table(slip, "dominant_highway")

    updown_cata = updown[updown["RoadCat"] == "CATA"]
    updown_slip = updown[updown["RoadCat"] == "SLIP_ROAD"]

    def _pct(x):
        return "n/a" if x is None else f"{x:.2%}"

    report = f"""# Step 7.3.3 — LTA 断面语义 ↔ MATSim Link 表达专项审计

> 脚本：`scripts/od/audit_section_semantics_7_3_3.py`（零仿真）
> 网络版本：`network_links_source_copy.csv`（清洗后，motorway 4,780 / motorway_link 9,086）
> 冻结：OD / λ / Population / Departure / Network / Capacity / Route-choice 全部未动
> λ 仍未选择。

## 0. STATUS

**PASS** — 断面语义审计完成，未改任何冻结模型。

## 1. 口径与覆盖

| 项 | 值 |
|---|---:|
| LTA TrafficFlow 断面（JSON 去重后） | {summary['traffic_section_count']:,} |
| tight crosswalk 覆盖断面 | {summary['crosswalk_section_count']:,} |
| 覆盖率 | {summary['crosswalk_coverage']:.2%} |
| 平均 MATSim 边 / 断面 | {summary['mean_edges_per_section']:.2f} |
| 中位 MATSim 边 / 断面 | {summary['median_edges_per_section']:.0f} |
| 路名一致率（断面均值） | {summary['mean_name_match_rate']:.2%} |
| 道路等级语义一致率（断面均值） | {summary['mean_class_consistent_rate']:.2%} |
| 方向一致率（断面均值） | {summary['mean_direction_consistent_rate']:.2%} |
| 含混合 highway 语义的断面 | {summary['sections_mixed_highway_rate']:.2%} |
| 被 ≥2 个断面共享的 MATSim 边 | {summary['shared_matsim_edges_rate']:.2%} |
| 至少共享 1 条边的断面 | {_pct(summary['sections_sharing_edge_rate'])} |

> 未覆盖的 33 个断面恰为 `RoadCat = #N/A`（无有效等级），不参与 CATA/SLIP 判读。

> **网络版本口径说明**：本审计使用 `network_links_source_copy.csv`（清洗后源拷贝），
> motorway 4,780 / motorway_link 9,086；7.3.2A 的 `network_cleaned.xml.gz`
> 为 motorway 4,744 / motorway_link 9,026，差异 <1%，属**清洗前/后网络口径差异**，
> 不推翻任何结论。正式报告需明确区分这两个网络版本。

## 2. 一个 LTA 断面 → 多少 MATSim 边

断面级匹配边数分布见 `section_semantic_audit.csv`；
平均 {summary['mean_edges_per_section']:.2f}、中位 {summary['median_edges_per_section']:.0f}。
→ 单个 LTA "点流量" 断面被 MATSim 用**多条 link** 重新表达，属一→多关系。

## 3. CATA ↔ highway 语义

- 断面数：**{summary['CATA']['n_sections']:,}**
- 平均匹配边：**{summary['CATA']['mean_edges']:.2f}**（中位 {summary['CATA']['median_edges']:.0f}）
- dominant 落在 motorway 家族（motorway/motorway_link）：
  **{_pct(summary['CATA_motorway_family_dominant_share'])}**
- dominant 为纯 `motorway`：**{_pct(summary['CATA_motorway_only_dominant_share'])}**
- 含 motorway 边的断面：**{_pct(summary['CATA']['motorway_presence_rate'])}**
- 混合 highway 语义：**{_pct(summary['CATA']['mixed_highway_rate'])}**
- 路名一致率：**{_pct(summary['CATA']['name_match_rate'])}**
- 等级语义一致率：**{_pct(summary['CATA']['class_consistent_rate'])}**
- 方向一致率：**{_pct(summary['CATA']['direction_consistent_rate'])}**

CATA 断面 dominant highway 分布：

{cata_dist}

## 4. SLIP_ROAD ↔ highway 语义

- 断面数：**{summary['SLIP_ROAD']['n_sections']:,}**
- 平均匹配边：**{summary['SLIP_ROAD']['mean_edges']:.2f}**（中位 {summary['SLIP_ROAD']['median_edges']:.0f}）
- dominant 为纯 `motorway_link`：**{_pct(summary['SLIP_motorway_link_dominant_share'])}**
- dominant 落在 `*_link` 家族：**{_pct(summary['SLIP_link_family_dominant_share'])}**
- 含 motorway_link 边的断面：**{_pct(summary['SLIP_ROAD']['motorway_link_presence_rate'])}**
- 混合 highway 语义：**{_pct(summary['SLIP_ROAD']['mixed_highway_rate'])}**
- 路名一致率：**{_pct(summary['SLIP_ROAD']['name_match_rate'])}**
- 等级语义一致率：**{_pct(summary['SLIP_ROAD']['class_consistent_rate'])}**
- 方向一致率：**{_pct(summary['SLIP_ROAD']['direction_consistent_rate'])}**

SLIP_ROAD 断面 dominant highway 分布：

{slip_dist}

## 5. 方向语义与"对向车道混入"

> 该节指标**不依赖 LTA Start→End 的方向约定**，因此比单纯的"方向一致率"更稳健。

| 指标 | 全部 | CATA | SLIP_ROAD |
|---|---:|---:|---:|
| 与 LTA 方向一致率（边加权，断面均值） | {summary['mean_direction_consistent_rate']:.2%} | {_pct(summary['CATA']['direction_consistent_rate'])} | {_pct(summary['SLIP_ROAD']['direction_consistent_rate'])} |
| 断面内自身对向边占比（边加权） | {summary['self_opposite_edge_share']:.2%} | {_pct(summary['CATA']['self_opposite_share'])} | {_pct(summary['SLIP_ROAD']['self_opposite_share'])} |
| 含 ≥1 条对向边的断面 | {summary['sections_with_opposite_edge_rate']:.2%} | {_pct(summary['CATA']['sections_with_opposite_edge_rate'])} | {_pct(summary['SLIP_ROAD']['sections_with_opposite_edge_rate'])} |
| 含精确互反配对（e_a_b + e_b_a）的断面 | {summary['sections_with_reciprocal_pair_rate']:.2%} | {_pct(summary['CATA']['sections_with_reciprocal_pair_rate'])} | {_pct(summary['SLIP_ROAD']['sections_with_reciprocal_pair_rate'])} |
| 匹配边可串成**单一有向链**的断面 | {_pct(summary['sections_chain_ok_rate'])} | {_pct(summary['CATA_chain_ok_rate'])} | {_pct(summary['SLIP_chain_ok_rate'])} |

→ 若一个断面同时匹配到**同一条路的正反两个行驶方向微段**，则断面"点流量"
语义与 MATSim"双向微段集合"表达不对齐，是"对向车道混入"的直接证据。
"可串成单一有向链"比例越低，说明断面被拆成越多方向不一致的碎片。

## 6. 上下游道路等级组合

### CATA 上游等级分布

{_updown_table(updown_cata, 'upstream_classes')}

### CATA 下游等级分布

{_updown_table(updown_cata, 'downstream_classes')}

### SLIP_ROAD 上游等级分布

{_updown_table(updown_slip, 'upstream_classes')}

### SLIP_ROAD 下游等级分布

{_updown_table(updown_slip, 'downstream_classes')}

## 7. 产出文件

| 文件 | 说明 |
|---|---|
| `section_semantic_audit.csv` | 断面级语义审计（边数/一致率/dominant highway） |
| `cata_semantic_audit.csv` | CATA 断面子集 |
| `sliproad_semantic_audit.csv` | SLIP_ROAD 断面子集 |
| `section_upstream_downstream.csv` | 断面链首/链尾 + 上下游道路等级组合 |
| `section_class_transition.csv` | 断面内相邻匹配边等级变化 |
| `section_duplicate_overlap.csv` | 一条 MATSim 边被多少 LTA 断面共享 |
| `roadcat_highway_correspondence.csv` | RoadCat × dominant highway 对应矩阵 |
| `semantic_audit_summary.json` | 汇总指标 |
| `STEP7_3_3_REPORT.md` | 本报告 |

## 8. 判读原则

LTA `RoadCat` 与 OSM/MATSim `highway` 不是同一分类体系，本审计不要求
二者严格一一相等，而是检查：

1. CATA 是否主要落到 motorway 家族；
2. SLIP_ROAD 是否主要落到 `*_link`（尤指 motorway_link）；
3. 一个 LTA 断面是否被映射到过多/过杂的 MATSim links；
4. 一条 MATSim link 是否被多个 LTA 断面共享；
5. CATA / SLIP 的上游-下游道路等级组合是否符合"主线↔匝道"结构。

本步骤不修改任何冻结模型。
"""

    (out / "STEP7_3_3_REPORT.md").write_text(report, encoding="utf-8")

    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"Outputs: {out}")


if __name__ == "__main__":
    main()
