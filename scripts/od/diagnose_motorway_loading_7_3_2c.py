#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Step 7.3.2C
Motorway Spatial Loading Audit

目的
----
利用 MATSim 的 plans.xml.gz + network_links_source_copy.csv，
诊断实际路线对 motorway / motorway_link 的空间装载情况。

本步骤：
    不修改 OD
    不修改 lambda
    不修改 population
    不修改 departure profile
    不修改 network
    不修改 capacity
    不修改 route-choice

核心问题
--------
1. 实际 route 中，有多少比例经过 motorway？
2. 有多少 motorway edge 实际被使用？
3. 高速流量是否集中在少量 motorway edge？
4. motorway_link 是否高度集中？
5. motorway / motorway_link 的路径转移结构是什么？

输入
----
plans:
    reports/matsim_assignment_6_3_3b/
    lambda_0p050/
    ITERS/it.0/output_plans.xml.gz

network:
    reports/matsim_network/network_links_source_copy.csv

输出
----
reports/od_route_diagnosis_7_3_2c/

    edge_route_loading.csv
    top_motorway_edges.csv
    top_motorway_link_edges.csv
    route_class_spatial_loading.csv
    route_transition_matrix.csv
    step7_3_2c_summary.json
    STEP7_3_2C_REPORT.md

注意
----
这里只统计 route 使用次数，不把它解释成真实小时交通流量。
它是 route-structure / spatial-loading 诊断指标。
"""


from __future__ import annotations

import argparse
import collections
import gzip
import json
import re
import time
from pathlib import Path

import pandas as pd
import numpy as np


# ============================================================
# 默认路径
# ============================================================

ROOT_DEFAULT = Path(
    r"D:\Luan\2026-05\2_Singapore"
)

NETWORK_DEFAULT = Path(
    r"reports\matsim_network\network_links_source_copy.csv"
)

PLANS_DEFAULT = Path(
    r"reports\matsim_assignment_6_3_3b"
    r"\lambda_0p050"
    r"\ITERS\it.0"
    r"\output_plans.xml.gz"
)

OUT_DEFAULT = Path(
    r"reports\od_route_diagnosis_7_3_2c"
)


# ============================================================
# 工具
# ============================================================

def find_file(
    root: Path,
    explicit: Path,
    patterns: list[str],
) -> Path:

    p = (
        explicit
        if explicit.is_absolute()
        else root / explicit
    )

    if p.exists():
        return p

    matches = []

    for pattern in patterns:
        matches.extend(
            root.rglob(pattern)
        )

    if not matches:
        raise FileNotFoundError(
            f"无法找到文件: {explicit}\n"
            f"patterns={patterns}"
        )

    matches = sorted(
        set(matches),
        key=lambda x: (
            "lambda_0p050" not in str(x),
            "it.0" not in str(x).lower(),
            len(str(x)),
            str(x),
        ),
    )

    return matches[0]


# ============================================================
# network
# ============================================================

def load_network(
    root: Path,
    network_path: Path,
):
    path = find_file(
        root,
        network_path,
        [
            "network_links_source_copy.csv",
        ],
    )

    print(f"[1/4] loading network: {path}")

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

    required = {
        "from_node",
        "to_node",
        "length_m",
        "highway",
        "name",
    }

    missing = (
        required
        - set(net.columns)
    )

    if missing:
        raise ValueError(
            f"network 缺字段: {sorted(missing)}"
        )

    net["link"] = (
        "e"
        + net["from_node"].astype(str)
        + "_"
        + net["to_node"].astype(str)
    )

    net["highway"] = (
        net["highway"]
        .astype(str)
        .str.strip()
        .str.lower()
    )

    net["length_m"] = pd.to_numeric(
        net["length_m"],
        errors="coerce",
    ).fillna(0.0)

    duplicated = (
        net["link"].duplicated().sum()
    )

    if duplicated:
        raise ValueError(
            f"network 中存在 {duplicated} 个重复 MATSim link"
        )

    link_class = dict(
        zip(
            net["link"],
            net["highway"],
        )
    )

    link_length = dict(
        zip(
            net["link"],
            net["length_m"],
        )
    )

    link_name = dict(
        zip(
            net["link"],
            net["name"].astype(str),
        )
    )

    motorway_links = set(
        net.loc[
            net["highway"] == "motorway",
            "link",
        ]
    )

    motorway_ramp_links = set(
        net.loc[
            net["highway"] == "motorway_link",
            "link",
        ]
    )

    print(
        f"    links={len(net):,}"
    )

    print(
        f"    motorway={len(motorway_links):,}"
    )

    print(
        f"    motorway_link={len(motorway_ramp_links):,}"
    )

    return (
        net,
        link_class,
        link_length,
        link_name,
        motorway_links,
        motorway_ramp_links,
        path,
    )


# ============================================================
# route parser
# ============================================================

# MATSim plans writer 当前格式：
#
# <route type="links">
# e1_2 e2_3 e3_4 ...
# </route>
#
# 某些版本可能 route 整行出现，因此这里允许跨字符。
#
# 使用二进制正则，避免 UTF-8 decode 开销。

ROUTE_RE = re.compile(
    rb'<route\b[^>]*\btype="links"[^>]*>(.*?)</route>',
    flags=re.DOTALL,
)


def parse_routes(
    plans_path: Path,
    link_class: dict,
    link_length: dict,
):

    print(
        f"[2/4] streaming plans: {plans_path}"
    )

    route_count = 0

    motorway_routes = 0
    motorway_ramp_routes = 0

    total_route_length = 0.0
    motorway_route_length = 0.0
    motorway_ramp_route_length = 0.0

    motorway_edge_use = collections.Counter()
    motorway_ramp_edge_use = collections.Counter()

    class_length = collections.Counter()
    class_route_use = collections.Counter()

    transition_counter = collections.Counter()

    unknown_links = 0

    t0 = time.time()

    with gzip.open(
        plans_path,
        "rb",
    ) as f:

        for raw_line in f:

            if (
                b"<route" not in raw_line
                or b'type="links"' not in raw_line
            ):
                continue

            match = ROUTE_RE.search(
                raw_line
            )

            if not match:
                continue

            raw_links = (
                match
                .group(1)
                .strip()
                .split()
            )

            if not raw_links:
                continue

            route_count += 1

            previous_class = None

            route_classes = set()

            has_motorway = False
            has_ramp = False

            route_total_length = 0.0

            for raw_id in raw_links:

                try:
                    link_id = (
                        raw_id
                        .decode("ascii")
                    )
                except UnicodeDecodeError:
                    link_id = (
                        raw_id
                        .decode(
                            "utf-8",
                            errors="replace",
                        )
                    )

                highway = link_class.get(
                    link_id,
                    "UNKNOWN",
                )

                length = float(
                    link_length.get(
                        link_id,
                        0.0,
                    )
                )

                if highway == "UNKNOWN":
                    unknown_links += 1

                route_total_length += length

                class_length[highway] += (
                    length
                )

                route_classes.add(
                    highway
                )

                if highway == "motorway":

                    has_motorway = True

                    motorway_route_length += (
                        length
                    )

                    motorway_edge_use[
                        link_id
                    ] += 1

                elif highway == "motorway_link":

                    has_ramp = True

                    motorway_ramp_route_length += (
                        length
                    )

                    motorway_ramp_edge_use[
                        link_id
                    ] += 1

                if previous_class is not None:
                    transition_counter[
                        (
                            previous_class,
                            highway,
                        )
                    ] += 1

                previous_class = highway

            total_route_length += (
                route_total_length
            )

            if has_motorway:
                motorway_routes += 1

            if has_ramp:
                motorway_ramp_routes += 1

            # 每条 route 只算一次是否使用该道路等级
            for highway in route_classes:
                class_route_use[
                    highway
                ] += 1

            if route_count % 25_000 == 0:

                elapsed = (
                    time.time()
                    - t0
                )

                print(
                    f"    routes={route_count:,}"
                    f" elapsed={elapsed:.1f}s"
                )

    elapsed = (
        time.time()
        - t0
    )

    print(
        f"    parsed routes={route_count:,}"
        f" elapsed={elapsed:.1f}s"
    )

    return {
        "route_count": route_count,
        "motorway_routes": motorway_routes,
        "motorway_ramp_routes":
            motorway_ramp_routes,
        "total_route_length":
            total_route_length,
        "motorway_route_length":
            motorway_route_length,
        "motorway_ramp_route_length":
            motorway_ramp_route_length,
        "motorway_edge_use":
            motorway_edge_use,
        "motorway_ramp_edge_use":
            motorway_ramp_edge_use,
        "class_length":
            class_length,
        "class_route_use":
            class_route_use,
        "transition_counter":
            transition_counter,
        "unknown_links":
            unknown_links,
        "elapsed_s": elapsed,
    }


# ============================================================
# 输出
# ============================================================

def top_share(
    counter,
    n,
):
    total = sum(
        counter.values()
    )

    if total <= 0:
        return np.nan

    return (
        sum(
            count
            for _, count
            in counter.most_common(n)
        )
        / total
    )


def write_outputs(
    root: Path,
    out: Path,
    result,
    net,
    link_name,
):

    out.mkdir(
        parents=True,
        exist_ok=True,
    )

    edge_use = (
        result["motorway_edge_use"]
    )

    ramp_use = (
        result["motorway_ramp_edge_use"]
    )

    edge_df = net[
        [
            "link",
            "from_node",
            "to_node",
            "highway",
            "name",
            "length_m",
        ]
    ].copy()

    edge_df["motorway_route_count"] = (
        edge_df["link"]
        .map(edge_use)
        .fillna(0)
        .astype(int)
    )

    edge_df["motorway_link_route_count"] = (
        edge_df["link"]
        .map(ramp_use)
        .fillna(0)
        .astype(int)
    )

    edge_df["motorway_route_use_rate"] = (
        edge_df[
            "motorway_route_count"
        ]
        / result["route_count"]
    )

    edge_df[
        "motorway_link_route_use_rate"
    ] = (
        edge_df[
            "motorway_link_route_count"
        ]
        / result["route_count"]
    )

    edge_df.to_csv(
        out / "edge_route_loading.csv",
        index=False,
        encoding="utf-8-sig",
    )

    motorway_df = (
        edge_df[
            edge_df["highway"]
            == "motorway"
        ]
        .sort_values(
            "motorway_route_count",
            ascending=False,
        )
    )

    motorway_df.head(
        200
    ).to_csv(
        out
        / "top_motorway_edges.csv",
        index=False,
        encoding="utf-8-sig",
    )

    ramp_df = (
        edge_df[
            edge_df["highway"]
            == "motorway_link"
        ]
        .sort_values(
            "motorway_link_route_count",
            ascending=False,
        )
    )

    ramp_df.head(
        200
    ).to_csv(
        out
        / "top_motorway_link_edges.csv",
        index=False,
        encoding="utf-8-sig",
    )

    total_len = (
        result["total_route_length"]
    )

    class_rows = []

    for highway, length in (
        result[
            "class_length"
        ]
        .most_common()
    ):

        class_rows.append(
            {
                "highway": highway,
                "route_length_km":
                    length / 1000.0,
                "route_length_share":
                    length / total_len
                    if total_len > 0
                    else np.nan,
                "routes_using_class":
                    result[
                        "class_route_use"
                    ][highway],
                "route_use_rate":
                    result[
                        "class_route_use"
                    ][highway]
                    / result[
                        "route_count"
                    ],
            }
        )

    pd.DataFrame(
        class_rows
    ).to_csv(
        out
        / "route_class_spatial_loading.csv",
        index=False,
        encoding="utf-8-sig",
    )

    transition_rows = []

    for (
        (from_class, to_class),
        count,
    ) in result[
        "transition_counter"
    ].most_common():

        transition_rows.append(
            {
                "from_highway":
                    from_class,
                "to_highway":
                    to_class,
                "transition_count":
                    count,
            }
        )

    pd.DataFrame(
        transition_rows
    ).to_csv(
        out
        / "route_transition_matrix.csv",
        index=False,
        encoding="utf-8-sig",
    )

    route_count = result[
        "route_count"
    ]

    n_mw = int(
        (
            net["highway"]
            == "motorway"
        ).sum()
    )

    n_ramp = int(
        (
            net["highway"]
            == "motorway_link"
        ).sum()
    )

    summary = {
        "step": "7.3.2C",
        "status": (
            "PASS"
            if (
                route_count > 0
                and result["unknown_links"] == 0
            )
            else "WARN"
        ),
        "route_count": int(
            route_count
        ),
        "network_motorway_edges":
            n_mw,
        "network_motorway_link_edges":
            n_ramp,
        "motorway_edges_used":
            len(edge_use),
        "motorway_edge_use_rate":
            len(edge_use) / n_mw
            if n_mw
            else np.nan,
        "motorway_link_edges_used":
            len(ramp_use),
        "motorway_link_edge_use_rate":
            len(ramp_use) / n_ramp
            if n_ramp
            else np.nan,
        "routes_using_motorway":
            result["motorway_routes"],
        "routes_using_motorway_rate":
            result[
                "motorway_routes"
            ] / route_count,
        "routes_using_motorway_link":
            result[
                "motorway_ramp_routes"
            ],
        "routes_using_motorway_link_rate":
            result[
                "motorway_ramp_routes"
            ] / route_count,
        "motorway_route_length_share":
            (
                result[
                    "motorway_route_length"
                ]
                / total_len
                if total_len > 0
                else np.nan
            ),
        "motorway_link_route_length_share":
            (
                result[
                    "motorway_ramp_route_length"
                ]
                / total_len
                if total_len > 0
                else np.nan
            ),
        "motorway_plus_ramp_route_length_share":
            (
                (
                    result[
                        "motorway_route_length"
                    ]
                    + result[
                        "motorway_ramp_route_length"
                    ]
                )
                / total_len
                if total_len > 0
                else np.nan
            ),
        "top10_motorway_usage_share":
            top_share(
                edge_use,
                10,
            ),
        "top50_motorway_usage_share":
            top_share(
                edge_use,
                50,
            ),
        "top100_motorway_usage_share":
            top_share(
                edge_use,
                100,
            ),
        "top10_motorway_link_usage_share":
            top_share(
                ramp_use,
                10,
            ),
        "top50_motorway_link_usage_share":
            top_share(
                ramp_use,
                50,
            ),
        "unknown_link_uses":
            int(
                result[
                    "unknown_links"
                ]
            ),
        "frozen_inputs_unchanged":
            True,
        "lambda_selected":
            False,
    }

    with open(
        out / "step7_3_2c_summary.json",
        "w",
        encoding="utf-8",
    ) as f:

        json.dump(
            summary,
            f,
            ensure_ascii=False,
            indent=2,
        )

    report = f"""# Step 7.3.2C — Motorway Spatial Loading Audit

## 状态

**{summary['status']}**

本步骤只进行 route-structure / spatial-loading 诊断，
不修改 OD、lambda、population、departure profile、
network topology、capacity 或 route-choice。

## 1. Route 使用

- route 数：**{route_count:,}**
- 使用 motorway 的 route：**{summary['routes_using_motorway']:,}**
- motorway route 使用率：**{summary['routes_using_motorway_rate']:.2%}**
- 使用 motorway_link 的 route：**{summary['routes_using_motorway_link']:,}**
- motorway_link route 使用率：**{summary['routes_using_motorway_link_rate']:.2%}**

## 2. Motorway edge 空间装载

- motorway edges：**{n_mw:,}**
- 实际被 route 使用：**{len(edge_use):,}**
- edge use rate：**{summary['motorway_edge_use_rate']:.2%}**
- Top 10 motorway edges 占 motorway route-use count：
  **{summary['top10_motorway_usage_share']:.2%}**
- Top 50：**{summary['top50_motorway_usage_share']:.2%}**
- Top 100：**{summary['top100_motorway_usage_share']:.2%}**

## 3. Ramp edge 空间装载

- motorway_link edges：**{n_ramp:,}**
- 实际被 route 使用：**{len(ramp_use):,}**
- edge use rate：**{summary['motorway_link_edge_use_rate']:.2%}**
- Top 10 motorway_link 占 ramp route-use count：
  **{summary['top10_motorway_link_usage_share']:.2%}**
- Top 50：**{summary['top50_motorway_link_usage_share']:.2%}**

## 4. Route length structure

- motorway route-length share：
  **{summary['motorway_route_length_share']:.2%}**
- motorway_link route-length share：
  **{summary['motorway_link_route_length_share']:.2%}**
- motorway + motorway_link：
  **{summary['motorway_plus_ramp_route_length_share']:.2%}**

> 注意：这里的 route-length share 是路径结构指标，
> 不是交通流量份额。

## 5. 后续判读

本步骤应与 Step 7.1 的 CATA 断面靶场联合使用。

核心问题不是“是否使用 motorway”，而是：

1. LTA CATA 观测点附近对应 motorway edge 是否具有较高 route loading；
2. 仿真高速使用是否集中在与观测点不同的 corridor；
3. motorway loading 是否被大量分散到平行 motorway edges；
4. motorway_link 是否承担异常高的路径使用。

只有在完成上述空间对应后，才能决定是否继续进行 route-choice parameter calibration。

## 6. 数据质量

- unknown route links：**{summary['unknown_link_uses']}**
- 输入 lambda：**0.05（诊断基准）**
- lambda 最终选择：**False**
"""

    (out / "STEP7_3_2C_REPORT.md").write_text(
        report,
        encoding="utf-8",
    )

    return summary


# ============================================================
# main
# ============================================================

def main():

    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--project-root",
        type=Path,
        default=ROOT_DEFAULT,
    )

    parser.add_argument(
        "--network",
        type=Path,
        default=NETWORK_DEFAULT,
    )

    parser.add_argument(
        "--plans",
        type=Path,
        default=PLANS_DEFAULT,
    )

    parser.add_argument(
        "--out-dir",
        type=Path,
        default=OUT_DEFAULT,
    )

    args = parser.parse_args()

    root = args.project_root

    out = (
        args.out_dir
        if args.out_dir.is_absolute()
        else root / args.out_dir
    )

    (
        net,
        link_class,
        link_length,
        link_name,
        motorway_links,
        motorway_ramp_links,
        network_path,
    ) = load_network(
        root,
        args.network,
    )

    plans_path = find_file(
        root,
        args.plans,
        [
            "output_plans.xml.gz",
            "*plans*.xml.gz",
        ],
    )

    result = parse_routes(
        plans_path,
        link_class,
        link_length,
    )

    print(
        "[3/4] writing outputs..."
    )

    summary = write_outputs(
        root,
        out,
        result,
        net,
        link_name,
    )

    print(
        "[4/4] validation"
    )

    print(
        json.dumps(
            summary,
            ensure_ascii=False,
            indent=2,
        )
    )

    print(
        f"\nOutput directory:\n{out}"
    )


if __name__ == "__main__":
    main()
