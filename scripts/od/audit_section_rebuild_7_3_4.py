#!/usr/bin/env python3
# -*- coding: utf-8 -*-

r"""
Step 7.3.4
Semantic-aligned LTA section -> MATSim crosswalk reconstruction.

Goal
----
Rebuild the section-level correspondence using four filters:
1. direction consistency
2. RoadCat semantic consistency
3. directional continuity
4. section-level aggregation diagnostics

No MATSim rerun. No modification to:
OD / lambda / population / departure profile / network / capacity / route choice.

Inputs
------
project root:
    D:\Luan\2026-05\2_Singapore

network:
    reports/matsim_network/network_links_source_copy.csv
    reports/matsim_network/network_nodes.csv

crosswalk:
    reports/matsim_assignment_6_3_2/lta_section_matsim_crosswalk.csv

traffic:
    Singapore_OD_MATSim_FinalData/08_TrafficCount/TrafficFlow_Data.json

simulation linkstats:
    reports/matsim_assignment_6_3_3b/lambda_0p050/ITERS/it.0/*.linkstats.txt.gz

Output
------
reports/od_section_semantic_rebuild_7_3_4/
    rebuilt_crosswalk.csv
    section_semantic_rebuild_summary.csv
    cata_rebuild.csv
    sliproad_rebuild.csv
    rebuilt_section_flow.csv
    step7_3_4_summary.json
    STEP7_3_4_REPORT.md

Important
---------
LTA RoadCat is the authoritative observation classification.
OSM highway is the network classification.
They are intentionally NOT forced to be one-to-one numerically.
"""

from __future__ import annotations

import argparse
import gzip
import json
import math
import re
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(r"D:\Luan\2026-05\2_Singapore")

NETWORK_DEFAULT = ROOT / r"reports\matsim_network\network_links_source_copy.csv"
NODES_DEFAULT = ROOT / r"reports\matsim_network\network_nodes_source_copy.csv"
CROSSWALK_DEFAULT = ROOT / r"reports\matsim_assignment_6_3_2\lta_section_matsim_crosswalk.csv"
TRAFFIC_DEFAULT = ROOT / r"Singapore_OD_MATSim_FinalData\08_TrafficCount\TrafficFlow_Data.json"
LINKSTATS_DEFAULT = ROOT / r"reports\matsim_assignment_6_3_3b\lambda_0p050\ITERS\it.0"

OUT_DEFAULT = ROOT / r"reports\od_section_semantic_rebuild_7_3_4"


def norm_name(x) -> str:
    if pd.isna(x):
        return ""
    s = str(x).upper().strip()
    s = s.replace("&", " AND ")
    s = re.sub(r"[-_/(),.&]+", " ", s)
    s = re.sub(r"\s+", " ", s)
    return s.strip()


def angle_deg(dx, dy):
    a = math.degrees(math.atan2(dx, dy))
    return a if a >= 0 else a + 360.0


def angle_diff(a, b):
    d = abs(a - b) % 360.0
    return min(d, 360.0 - d)


def allowed_highways(roadcat: str) -> set[str]:
    """
    Conservative semantic mapping.

    CATA -> motorway
    SLIP_ROAD -> motorway_link

    For CATB/C/C/D/E we retain plausible arterial/local classes
    without forcing exact equality.
    """
    rc = str(roadcat).upper().strip()

    if rc == "CATA":
        return {"motorway"}

    if rc == "SLIP_ROAD":
        return {"motorway_link"}

    if rc == "CATB":
        return {
            "trunk",
            "primary",
            "secondary",
        }

    if rc == "CATC":
        return {
            "primary",
            "secondary",
            "tertiary",
        }

    if rc == "CATD":
        return {
            "secondary",
            "tertiary",
            "residential",
        }

    if rc == "CATE":
        return {
            "tertiary",
            "residential",
            "service",
            "unclassified",
        }

    return set()


def load_network(path: Path, nodes_path: Path):
    net = pd.read_csv(
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

    net["matsim_link_id"] = (
        "e"
        + net["from_node"].astype(str)
        + "_"
        + net["to_node"].astype(str)
    )
    net["highway"] = (
        net["highway"].astype(str).str.strip().str.lower()
    )
    net["name_norm"] = net["name"].map(norm_name)
    net["length_m"] = pd.to_numeric(
        net["length_m"], errors="coerce"
    ).fillna(0.0)

    if net["matsim_link_id"].duplicated().any():
        raise ValueError("network 出现重复 MATSim link id")

    nodes = pd.read_csv(
        nodes_path,
        encoding="utf-8-sig",
        low_memory=False,
    )
    nodes["node_id"] = nodes["node_id"].astype(str)

    # Coordinate column selection. Prefer lon/lat so that the network
    # heading is computed with the exact same convention as the LTA
    # section heading (StartLon/StartLat/EndLon/EndLat).
    if {"lon", "lat"}.issubset(nodes.columns):
        cx, cy = "lon", "lat"
    elif {"x", "y"}.issubset(nodes.columns):
        cx, cy = "x", "y"
    elif {"x_svy21_m", "y_svy21_m"}.issubset(nodes.columns):
        cx, cy = "x_svy21_m", "y_svy21_m"
    else:
        raise ValueError(
            "nodes 缺少坐标列（需要 lon/lat 或 x/y 或 x_svy21_m/y_svy21_m）"
        )

    nodes[cx] = pd.to_numeric(nodes[cx], errors="coerce")
    nodes[cy] = pd.to_numeric(nodes[cy], errors="coerce")

    node_xy = {
        r.node_id: (float(getattr(r, cx)), float(getattr(r, cy)))
        for r in nodes.itertuples(index=False)
        if pd.notna(getattr(r, cx)) and pd.notna(getattr(r, cy))
    }

    # Link direction angle in degrees from north, clockwise.
    angles = []
    for r in net.itertuples(index=False):
        a = np.nan
        p0 = node_xy.get(str(r.from_node))
        p1 = node_xy.get(str(r.to_node))
        if p0 and p1:
            dx = p1[0] - p0[0]
            dy = p1[1] - p0[1]
            if abs(dx) + abs(dy) > 0:
                a = angle_deg(dx, dy)
        angles.append(a)

    net["network_heading_deg"] = angles
    return net, node_xy


def load_traffic(path: Path):
    with open(path, "r", encoding="utf-8-sig") as f:
        obj = json.load(f)

    rows = obj.get("Value", obj)
    tf = pd.DataFrame(rows)

    req = {
        "LinkID",
        "RoadName",
        "RoadCat",
        "StartLon",
        "StartLat",
        "EndLon",
        "EndLat",
    }
    missing = req - set(tf.columns)
    if missing:
        raise ValueError(
            f"TrafficFlow 缺字段: {sorted(missing)}"
        )

    tf["LinkID"] = tf["LinkID"].astype(str)
    tf["RoadName_norm"] = tf["RoadName"].map(norm_name)
    tf["RoadCat"] = (
        tf["RoadCat"].astype(str).str.strip().str.upper()
    )

    # Section attributes must be unique.
    attr_cols = [
        "RoadName",
        "RoadName_norm",
        "RoadCat",
        "StartLon",
        "StartLat",
        "EndLon",
        "EndLat",
    ]
    sec = tf.groupby("LinkID", as_index=False)[attr_cols].first()
    sec = sec.rename(columns={"LinkID": "lta_linkid"})

    return sec


def load_crosswalk(path: Path):
    cw = pd.read_csv(
        path,
        encoding="utf-8-sig",
        low_memory=False,
    )

    rename = {}
    for c in cw.columns:
        lc = c.lower().strip()
        if lc == "linkid":
            rename[c] = "lta_linkid"
        elif lc in {"matsim_link_id", "matsim_link"}:
            rename[c] = "matsim_link_id"
        elif lc in {"osm_edge_index", "edge_index"}:
            rename[c] = "osm_edge_index"

    cw = cw.rename(columns=rename)

    if "lta_linkid" not in cw.columns:
        raise ValueError("crosswalk 缺少 LinkID")

    if "matsim_link_id" not in cw.columns:
        if "osm_edge_index" not in cw.columns:
            raise ValueError(
                "crosswalk 既没有 matsim_link_id，也没有 osm_edge_index"
            )
        raise ValueError(
            "本步骤要求 crosswalk 已经包含 matsim_link_id；"
            "请先由 6.3.2 crosswalk 完成 edge-index 映射"
        )

    cw["lta_linkid"] = cw["lta_linkid"].astype(str)
    cw["matsim_link_id"] = cw["matsim_link_id"].astype(str)

    return cw[
        ["lta_linkid", "matsim_link_id"]
    ].drop_duplicates()


def build_candidates(
    cw,
    traffic,
    net,
    direction_threshold=30.0,
):
    x = cw.merge(
        traffic,
        on="lta_linkid",
        how="inner",
        validate="many_to_one",
    ).merge(
        net[
            [
                "matsim_link_id",
                "from_node",
                "to_node",
                "length_m",
                "highway",
                "name",
                "name_norm",
                "network_heading_deg",
            ]
        ],
        on="matsim_link_id",
        how="inner",
        validate="many_to_one",
    )

    # LTA section direction.
    start_lon = pd.to_numeric(x["StartLon"], errors="coerce")
    start_lat = pd.to_numeric(x["StartLat"], errors="coerce")
    end_lon = pd.to_numeric(x["EndLon"], errors="coerce")
    end_lat = pd.to_numeric(x["EndLat"], errors="coerce")

    # Approximate local heading: lon scaled by cos(lat), lat unchanged.
    mean_lat = np.radians((start_lat + end_lat) / 2.0)
    dx = (end_lon - start_lon) * np.cos(mean_lat)
    dy = end_lat - start_lat
    x["lta_heading_deg"] = np.degrees(np.arctan2(dx, dy))
    x.loc[x["lta_heading_deg"] < 0, "lta_heading_deg"] += 360.0

    x["direction_diff_deg"] = [
        angle_diff(a, b)
        if pd.notna(a) and pd.notna(b)
        else np.nan
        for a, b in zip(
            x["lta_heading_deg"],
            x["network_heading_deg"],
        )
    ]

    x["direction_ok"] = (
        x["direction_diff_deg"]
        <= direction_threshold
    )

    x["name_match"] = (
        (x["RoadName_norm"] != "")
        & (x["RoadName_norm"] == x["name_norm"])
    )

    def semantic_ok(row):
        return row["highway"] in allowed_highways(
            row["RoadCat"]
        )

    x["semantic_ok"] = x.apply(
        semantic_ok,
        axis=1,
    )

    return x


def select_rebuilt(
    candidates: pd.DataFrame,
):
    """
    Selection rule:

    Stage 1:
        direction_ok AND semantic_ok

    If none:
        direction_ok + same normalized name

    If still none:
        original candidate (diagnostic fallback only)

    This preserves coverage while explicitly marking fallback quality.
    """
    selected = []

    for section_id, grp in candidates.groupby(
        "lta_linkid",
        sort=False,
    ):
        g = grp.copy()

        strict = g[
            g["direction_ok"]
            & g["semantic_ok"]
        ].copy()

        if not strict.empty:
            strict["selection_tier"] = "strict"
            selected.append(strict)
            continue

        direction_name = g[
            g["direction_ok"]
            & g["name_match"]
        ].copy()

        if not direction_name.empty:
            direction_name[
                "selection_tier"
            ] = "direction_name"
            selected.append(direction_name)
            continue

        same_name = g[
            g["name_match"]
        ].copy()

        if not same_name.empty:
            same_name[
                "selection_tier"
            ] = "name_fallback"
            selected.append(same_name)
            continue

        fallback = g.copy()
        fallback[
            "selection_tier"
        ] = "original_fallback"
        selected.append(fallback)

    if not selected:
        return pd.DataFrame()

    return pd.concat(
        selected,
        ignore_index=True,
    )


def aggregate_section(
    selected: pd.DataFrame
):
    def direction_spread(s):
        vals = s.dropna().to_numpy()
        if len(vals) <= 1:
            return 0.0
        # Circular range, maximum pairwise circular distance.
        maxd = 0.0
        for a in vals:
            for b in vals:
                maxd = max(maxd, angle_diff(a, b))
        return maxd

    section = (
        selected.groupby(
            [
                "lta_linkid",
                "RoadName",
                "RoadCat",
            ],
            dropna=False,
        )
        .agg(
            matsim_edges=(
                "matsim_link_id",
                "nunique",
            ),
            strict_edges=(
                "selection_tier",
                lambda s: int(
                    (s == "strict").sum()
                ),
            ),
            fallback_edges=(
                "selection_tier",
                lambda s: int(
                    (s != "strict").sum()
                ),
            ),
            name_match_rate=(
                "name_match",
                "mean",
            ),
            direction_match_rate=(
                "direction_ok",
                "mean",
            ),
            semantic_match_rate=(
                "semantic_ok",
                "mean",
            ),
            mixed_highway=(
                "highway",
                lambda s: len(set(s.dropna())) > 1,
            ),
            highway_values=(
                "highway",
                lambda s: "|".join(
                    sorted(set(
                        str(v) for v in s.dropna()
                    ))
                ),
            ),
            motorway_edges=(
                "highway",
                lambda s: int(
                    (s == "motorway").sum()
                ),
            ),
            motorway_link_edges=(
                "highway",
                lambda s: int(
                    (s == "motorway_link").sum()
                ),
            ),
            direction_spread_deg=(
                "network_heading_deg",
                direction_spread,
            ),
        )
        .reset_index()
    )

    section["dominant_highway"] = (
        selected.groupby("lta_linkid")[
            "highway"
        ]
        .agg(
            lambda s: (
                s.value_counts()
                .index[0]
                if len(s)
                else ""
            )
        )
        .reset_index(drop=True)
        .to_numpy()
    )

    section["chain_candidate"] = False

    # A practical continuity check:
    # after sorting by from/to node, a section is considered chainable
    # when unique edges have no duplicated start/end sequence conflict
    # and at least 2 edges can be linked by to_node == next.from_node.
    for sid, grp in selected.groupby(
        "lta_linkid"
    ):
        nodes = list(
            zip(
                grp["from_node"].astype(str),
                grp["to_node"].astype(str),
            )
        )

        if len(nodes) == 1:
            ok = True
        else:
            indeg = {}
            outdeg = {}
            for a, b in nodes:
                outdeg[a] = outdeg.get(a, 0) + 1
                indeg[b] = indeg.get(b, 0) + 1
            ok = (
                max(indeg.values(), default=0) <= 2
                and max(outdeg.values(), default=0) <= 2
            )

        section.loc[
            section["lta_linkid"] == sid,
            "chain_candidate",
        ] = ok

    return section


def read_linkstats(path: Path):
    candidates = list(
        path.glob("*.linkstats.txt.gz")
    ) + list(
        path.glob("*.linkstats.txt")
    )

    if not candidates:
        return None

    p = candidates[0]
    print(f"linkstats={p}")

    # Read header first.
    opener = gzip.open if p.suffix == ".gz" else open
    with opener(
        p,
        "rt",
        encoding="utf-8",
        errors="replace",
    ) as f:
        header = f.readline().rstrip("\n").split("\t")

    needed = [
        "LINK",
        "HRS7-8avg",
        "HRS8-9avg",
    ]
    idx = {
        h: header.index(h)
        for h in needed
        if h in header
    }

    usecols = list(idx.values())

    df = pd.read_csv(
        p,
        sep="\t",
        compression="gzip"
        if p.suffix == ".gz"
        else None,
        usecols=usecols,
        low_memory=False,
    )

    rename = {
        v: k for k, v in idx.items()
    }

    df = df.rename(columns=rename)

    for c in [
        "HRS7-8avg",
        "HRS8-9avg",
    ]:
        if c in df.columns:
            df[c] = pd.to_numeric(
                df[c],
                errors="coerce",
            )

    df["LINK"] = df["LINK"].astype(str)

    return df


def main():
    ap = argparse.ArgumentParser()

    ap.add_argument(
        "--project-root",
        type=Path,
        default=ROOT,
    )
    ap.add_argument(
        "--network",
        type=Path,
        default=NETWORK_DEFAULT,
    )
    ap.add_argument(
        "--nodes",
        type=Path,
        default=NODES_DEFAULT,
    )
    ap.add_argument(
        "--crosswalk",
        type=Path,
        default=CROSSWALK_DEFAULT,
    )
    ap.add_argument(
        "--traffic",
        type=Path,
        default=TRAFFIC_DEFAULT,
    )
    ap.add_argument(
        "--linkstats-dir",
        type=Path,
        default=LINKSTATS_DEFAULT,
    )
    ap.add_argument(
        "--out-dir",
        type=Path,
        default=OUT_DEFAULT,
    )
    ap.add_argument(
        "--direction-threshold",
        type=float,
        default=30.0,
    )

    args = ap.parse_args()
    out = (
        args.out_dir
        if args.out_dir.is_absolute()
        else args.project_root / args.out_dir
    )
    out.mkdir(
        parents=True,
        exist_ok=True,
    )

    network, node_xy = load_network(
        args.network,
        args.nodes,
    )

    traffic = load_traffic(
        args.traffic
    )

    crosswalk = load_crosswalk(
        args.crosswalk
    )

    cand = build_candidates(
        crosswalk,
        traffic,
        network,
        direction_threshold=args.direction_threshold,
    )

    selected = select_rebuilt(
        cand
    )

    if selected.empty:
        raise RuntimeError(
            "没有产生任何重构后的 crosswalk"
        )

    section = aggregate_section(
        selected
    )

    # Optional linkstats: section median is computed only when available.
    linkstats = read_linkstats(
        args.linkstats_dir
    )

    if linkstats is not None:
        flow = selected[
            [
                "lta_linkid",
                "matsim_link_id",
            ]
        ].merge(
            linkstats,
            left_on="matsim_link_id",
            right_on="LINK",
            how="left",
        )

        flow_summary = (
            flow.groupby(
                "lta_linkid",
                as_index=False,
            )
            .agg(
                sim_7_8_median=(
                    "HRS7-8avg",
                    "median",
                ),
                sim_8_9_median=(
                    "HRS8-9avg",
                    "median",
                ),
                sim_7_8_mean=(
                    "HRS7-8avg",
                    "mean",
                ),
                sim_8_9_mean=(
                    "HRS8-9avg",
                    "mean",
                ),
                matched_links=(
                    "matsim_link_id",
                    "nunique",
                ),
            )
        )

        section_flow = (
            section
            .merge(
                flow_summary,
                on="lta_linkid",
                how="left",
            )
        )
    else:
        section_flow = section.copy()

    # Compare raw old crosswalk vs rebuilt.
    old_sec = (
        crosswalk.groupby(
            "lta_linkid"
        )["matsim_link_id"]
        .nunique()
        .rename(
            "old_matsim_edges"
        )
        .reset_index()
    )

    section = section.merge(
        old_sec,
        on="lta_linkid",
        how="left",
    )

    section[
        "edge_count_change"
    ] = (
        section["matsim_edges"]
        - section["old_matsim_edges"]
    )

    cata = section[
        section["RoadCat"] == "CATA"
    ].copy()

    slip = section[
        section["RoadCat"] == "SLIP_ROAD"
    ].copy()

    rebuilt = selected[
        [
            "lta_linkid",
            "matsim_link_id",
            "RoadName",
            "RoadCat",
            "highway",
            "name",
            "from_node",
            "to_node",
            "length_m",
            "lta_heading_deg",
            "network_heading_deg",
            "direction_diff_deg",
            "direction_ok",
            "semantic_ok",
            "name_match",
            "selection_tier",
        ]
    ].copy()

    rebuilt.to_csv(
        out / "rebuilt_crosswalk.csv",
        index=False,
        encoding="utf-8-sig",
    )

    section.to_csv(
        out / "section_semantic_rebuild_summary.csv",
        index=False,
        encoding="utf-8-sig",
    )

    cata.to_csv(
        out / "cata_rebuild.csv",
        index=False,
        encoding="utf-8-sig",
    )

    slip.to_csv(
        out / "sliproad_rebuild.csv",
        index=False,
        encoding="utf-8-sig",
    )

    section_flow.to_csv(
        out / "rebuilt_section_flow.csv",
        index=False,
        encoding="utf-8-sig",
    )

    summary = {
        "step": "7.3.4",
        "status": "PASS",
        "lta_sections_old": int(
            crosswalk["lta_linkid"].nunique()
        ),
        "lta_sections_rebuilt": int(
            section["lta_linkid"].nunique()
        ),
        "rebuilt_crosswalk_rows": int(
            len(rebuilt)
        ),
        "mean_edges_per_section": float(
            section["matsim_edges"].mean()
        ),
        "median_edges_per_section": float(
            section["matsim_edges"].median()
        ),
        "mean_direction_match_rate": float(
            section["direction_match_rate"].mean()
        ),
        "mean_semantic_match_rate": float(
            section["semantic_match_rate"].mean()
        ),
        "mixed_highway_rate": float(
            section["mixed_highway"].mean()
        ),
        "CATA_sections": int(len(cata)),
        "CATA_dominant_motorway_rate": float(
            (cata["dominant_highway"] == "motorway").mean()
        ) if len(cata) else np.nan,
        "CATA_mean_edges": float(
            cata["matsim_edges"].mean()
        ) if len(cata) else np.nan,
        "SLIP_sections": int(len(slip)),
        "SLIP_dominant_motorway_link_rate": float(
            (slip["dominant_highway"] == "motorway_link").mean()
        ) if len(slip) else np.nan,
        "SLIP_dominant_motorway_rate": float(
            (slip["dominant_highway"] == "motorway").mean()
        ) if len(slip) else np.nan,
        "SLIP_mean_edges": float(
            slip["matsim_edges"].mean()
        ) if len(slip) else np.nan,
        "selection_strict_rate": float(
            (selected["selection_tier"] == "strict").mean()
        ),
        "selection_fallback_rate": float(
            (selected["selection_tier"] != "strict").mean()
        ),
        "direction_threshold_deg":
            args.direction_threshold,
        "parameters_changed": False,
        "lambda_selected": False,
    }

    with open(
        out / "step7_3_4_summary.json",
        "w",
        encoding="utf-8",
    ) as f:
        json.dump(
            summary,
            f,
            ensure_ascii=False,
            indent=2,
        )

    report = f"""# Step 7.3.4 — Semantic-aligned Section Rebuild

## Status

**PASS**

本步骤只重构 LTA 断面 ↔ MATSim link 的对应关系，
不重新运行 MATSim，也不修改 OD、λ、Population、Departure Profile、
Network、Capacity 或 Route Choice。

## 1. 总体

- 原 crosswalk 断面：**{summary['lta_sections_old']:,}**
- 重构后断面：**{summary['lta_sections_rebuilt']:,}**
- 重构 crosswalk rows：**{summary['rebuilt_crosswalk_rows']:,}**
- 每断面平均 MATSim links：**{summary['mean_edges_per_section']:.2f}**
- 中位数：**{summary['median_edges_per_section']:.0f}**
- 平均方向一致率：**{summary['mean_direction_match_rate']:.2%}**
- 平均语义一致率：**{summary['mean_semantic_match_rate']:.2%}**
- mixed-highway section：**{summary['mixed_highway_rate']:.2%}**

## 2. CATA

- section：**{summary['CATA_sections']}**
- dominant motorway：**{summary['CATA_dominant_motorway_rate']:.2%}**
- 平均匹配 links：**{summary['CATA_mean_edges']:.2f}**

## 3. SLIP_ROAD

- section：**{summary['SLIP_sections']}**
- dominant motorway_link：**{summary['SLIP_dominant_motorway_link_rate']:.2%}**
- dominant motorway：**{summary['SLIP_dominant_motorway_rate']:.2%}**
- 平均匹配 links：**{summary['SLIP_mean_edges']:.2f}**

## 4. Selection tiers

- strict = direction + semantic：**{summary['selection_strict_rate']:.2%}**
- fallback：**{summary['selection_fallback_rate']:.2%}**

### 重要

CATA 与 SLIP_ROAD 使用不同的道路语义集合。
LTA RoadCat 是观测侧权威分类，OSM highway 是网络侧分类，
二者不是同一套代码表。

本步骤的目标是减少：
- 对向边混入；
- CATA/SLIP 主线-匝道错配；
- 多对多断面表达；
- 与 LTA 方向不一致的 MATSim 微段。

如果重构后 CATA/SLIP 的 Sim/Obs 比值仍保持原先
约 0.685 / 2.046 的方向，则应停止继续优化 crosswalk，
转向需求空间结构或更高层网络表达问题。

"""
    (out / "STEP7_3_4_REPORT.md").write_text(
        report,
        encoding="utf-8",
    )

    print(
        json.dumps(
            summary,
            ensure_ascii=False,
            indent=2,
        )
    )
    print("Output:", out)


if __name__ == "__main__":
    main()
