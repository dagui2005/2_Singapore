#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Step 7.2 — MATSim parameter audit + capacity-only sensitivity scaffold.

Purpose
-------
Audit the currently frozen MATSim setup before changing any parameter.

Frozen:
  OD / lambda / network topology / population / departure profile / crosswalk.

Audited:
  * MATSim config XML:
      qsim.flowCapacityFactor
      qsim.storageCapacityFactor
      qsim.numberOfThreads
      routing-related settings
      travelTimeCalculator settings
      replanning/strategy modules
      input network and population paths
  * Network:
      permlanes distribution
      capacity distribution
      capacity-per-lane by highway
      freespeed distribution
      zero/invalid values
  * Existing Step 7.1 target:
      calibration_target_summary.csv

Outputs:
  reports/od_calibration_7_2/
      parameter_audit.csv
      network_capacity_audit.csv
      calibration_target_baseline.csv
      step7_2_audit.json

No calibration is performed by this script.

Optional capacity sweep
-----------------------
A separate script should generate copies of the frozen network with a
multiplicative capacity factor and rerun the same population/config.
This file only provides the audited baseline and a machine-readable plan.
"""
from __future__ import annotations

import argparse
import csv
import gzip
import json
import math
import re
import xml.etree.ElementTree as ET
from pathlib import Path

import numpy as np
import pandas as pd


ROOT_DEFAULT = Path(r"D:\Luan\2026-05\2_Singapore")

CONFIG_CANDIDATES = [
    Path("matsim/step6_3"),              # 实际 CONFIG_DIR（6.3 / 6.3.3B 全部 config 在此）
    Path("scripts/matsim/configs"),
    Path("reports/matsim_assignment_6_3_3b"),
    Path("reports/matsim_assignment"),
]

NETWORK_CSV = Path(
    "reports/matsim_network/network_links_source_copy.csv"
)

TARGET_SUMMARY = Path(
    "reports/od_calibration_7_1/calibration_target_summary.csv"
)

OUT = Path(
    "reports/od_calibration_7_2"
)


def find_xml_configs(root: Path):
    files = []
    for base in CONFIG_CANDIDATES:
        p = root / base
        if p.exists():
            files.extend(p.rglob("*.xml"))
    # Ignore generic sample/config backups where possible.
    return sorted(set(files))


def text_value(elem):
    if elem is None:
        return None
    if elem.text is None:
        return ""
    return elem.text.strip()


def flatten_xml(root_elem):
    """展平 MATSim config XML。

    关键：config_v2 的参数是 ``<param name="..." value="..."/>`` **属性**而非文本，
    module 名在 ``<module name="..."/>`` 属性里。为让 path 可检索：
      * module 名嵌入 path（如 ``module[qsim]/param[flowCapacityFactor]``）；
      * param 的 ``value`` 作为 text。
    """
    rows = []

    def walk(elem, path):
        tag = elem.tag
        name = elem.attrib.get("name")
        here = f"{path}/{tag}" if path else tag
        if name:
            here = f"{here}[{name}]"

        if tag == "param":
            rows.append(
                {
                    "path": here,
                    "tag": tag,
                    "text": elem.attrib.get("value", ""),
                    "attrs": json.dumps(
                        dict(elem.attrib),
                        ensure_ascii=False,
                    ),
                }
            )
        elif len(elem) == 0:
            rows.append(
                {
                    "path": here,
                    "tag": tag,
                    "text": text_value(elem),
                    "attrs": json.dumps(
                        dict(elem.attrib),
                        ensure_ascii=False,
                    ),
                }
            )

        for child in elem:
            walk(child, here)

    walk(root_elem, "")
    return pd.DataFrame(rows)


def audit_config(path: Path):
    # MATSim config is plain XML.
    try:
        tree = ET.parse(path)
    except ET.ParseError as e:
        return {
            "config_file": str(path),
            "status": "FAIL",
            "error": f"XML parse error: {e}",
        }, pd.DataFrame()

    root = tree.getroot()
    flat = flatten_xml(root)

    wanted_fragments = [
        "flowCapacityFactor",
        "storageCapacityFactor",
        "numberOfThreads",
        "routingAlgorithm",
        "networkModes",
        "travelTimeCalculator",
        "inputNetwork",
        "inputPlans",
        "firstIteration",
        "lastIteration",
        "fractionOfIterationsToDisableInnovation",
        "strategy",
        "replanning",
        "controler",
        "qsim",
    ]

    mask = flat["path"].str.contains(
        "|".join(
            re.escape(x)
            for x in wanted_fragments
        ),
        case=False,
        regex=True,
    )

    selected = flat[mask].copy()
    selected.insert(
        0,
        "config_file",
        str(path),
    )

    summary = {
        "config_file": str(path),
        "status": "PASS",
        "xml_root": root.tag,
        "flowCapacityFactor": None,
        "storageCapacityFactor": None,
        "numberOfThreads": None,
        "inputNetwork": None,
        "inputPlans": None,
        "firstIteration": None,
        "lastIteration": None,
    }

    def get_last(fragment):
        q = flat[
            flat["path"].str.contains(
                re.escape(fragment),
                case=False,
                regex=True,
            )
        ]
        if q.empty:
            return None
        return q.iloc[-1]["text"]

    summary["flowCapacityFactor"] = get_last(
        "flowCapacityFactor"
    )
    summary["storageCapacityFactor"] = get_last(
        "storageCapacityFactor"
    )
    summary["numberOfThreads"] = get_last(
        "numberOfThreads"
    )
    summary["inputNetwork"] = get_last(
        "inputNetwork"
    )
    summary["inputPlans"] = get_last(
        "inputPlans"
    )
    summary["firstIteration"] = get_last(
        "firstIteration"
    )
    summary["lastIteration"] = get_last(
        "lastIteration"
    )

    return summary, selected


NETWORK_XML = Path(
    "reports/matsim_network/network_cleaned.xml.gz"   # 6.3a 仿真实际使用的网络（含逐边 capacity/permlanes/freespeed）
)


def parse_network_xml(root: Path) -> pd.DataFrame:
    """从 MATSim 网络 XML（gz）逐边抽取 capacity / permlanes / freespeed / length。

    link id 形如 ``e{from_node}_{to_node}``，可反解出 from/to 以便与
    ``network_links_source_copy.csv``（含 highway 等级）合并。
    """
    path = root / NETWORK_XML
    if not path.exists():
        raise FileNotFoundError(path)

    rows = []
    with gzip.open(path, "rb") as f:
        for event, elem in ET.iterparse(f, events=("end",)):
            if elem.tag != "link":
                continue
            a = elem.attrib
            link_id = a.get("id", "")
            m = re.match(r"^e(\d+)_(\d+)$", link_id)
            rows.append(
                {
                    "link_id": link_id,
                    "from_node": int(m.group(1)) if m else None,
                    "to_node": int(m.group(2)) if m else None,
                    "capacity": a.get("capacity"),
                    "permlanes": a.get("permlanes"),
                    "freespeed": a.get("freespeed"),
                    "length": a.get("length"),
                }
            )
            elem.clear()

    df = pd.DataFrame(rows)
    if df.empty:
        raise ValueError(f"{path} 中未解析到任何 <link>")

    for c in ["capacity", "permlanes", "freespeed", "length"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")

    return df


def load_network(root: Path):
    # ① 拓扑 + highway 等级来自 Step 6.1 source copy（无 capacity 列）。
    path = root / NETWORK_CSV
    if not path.exists():
        raise FileNotFoundError(path)

    e = pd.read_csv(
        path,
        encoding="utf-8-sig",
        low_memory=False,
    )

    required = {
        "from_node",
        "to_node",
        "length_m",
        "speed_kmh",
        "highway",
        "lanes",
    }

    missing = required - set(e.columns)
    if missing:
        raise ValueError(
            f"network_links_source_copy 缺字段: {sorted(missing)}"
        )

    for c in [
        "length_m",
        "speed_kmh",
        "lanes",
    ]:
        e[c] = pd.to_numeric(
            e[c],
            errors="coerce",
        )

    e["highway"] = (
        e["highway"]
        .astype(str)
        .str.lower()
        .str.strip()
    )

    # ② 逐边 capacity / permlanes / freespeed 来自 MATSim 网络 XML（6.3a cleaned = 仿真实际用网）。
    nx = parse_network_xml(root)

    e = e.merge(
        nx,
        on=["from_node", "to_node"],
        how="inner",
        suffixes=("", "_xml"),
    )

    # capacity = lanes × highway-class 默认 veh/h/lane（见 network_validation.json）
    e["capacity_per_lane"] = e["capacity"] / e["permlanes"].replace(0, np.nan)

    # 一致性核查：XML permlanes 是否等于 CSV lanes
    e["lanes_match"] = np.isclose(
        e["lanes"],
        e["permlanes"],
        rtol=1e-6,
        equal_nan=False,
    )

    return e


def summarize_network(e):
    out = {
        "links": int(len(e)),
        "invalid_length": int(
            (e["length_m"] <= 0).sum()
        ),
        "invalid_speed": int(
            (
                (~np.isfinite(e["speed_kmh"]))
                | (e["speed_kmh"] <= 0)
            ).sum()
        ),
        "invalid_lanes": int(
            (
                (~np.isfinite(e["permlanes"]))
                | (e["permlanes"] <= 0)
            ).sum()
        ),
        "csv_lanes_missing": int(
            (~np.isfinite(e["lanes"])).sum()
        ),
        "invalid_capacity": int(
            (
                (~np.isfinite(e["capacity"]))
                | (e["capacity"] <= 0)
            ).sum()
        ),
        "invalid_permlanes": int(
            (
                (~np.isfinite(e["permlanes"]))
                | (e["permlanes"] <= 0)
            ).sum()
        ),
        "lanes_mismatch_vs_xml": int(
            (
                np.isfinite(e["lanes"])
                & (~e["lanes_match"])
            ).sum()
        ),
        "speed_median_kmh": float(
            e["speed_kmh"].median()
        ),
        "speed_p95_kmh": float(
            e["speed_kmh"].quantile(0.95)
        ),
        "freespeed_median_kmh": float(
            (e["freespeed"] * 3.6).median()
        ),
        "freespeed_max_kmh": float(
            (e["freespeed"] * 3.6).max()
        ),
        "lanes_median": float(
            e["lanes"].median()
        ),
        "lanes_p95": float(
            e["lanes"].quantile(0.95)
        ),
        "capacity_median_vph": float(
            e["capacity"].median()
        ),
        "capacity_p95_vph": float(
            e["capacity"].quantile(0.95)
        ),
        "capacity_per_lane_median": float(
            e["capacity_per_lane"].median()
        ),
        "capacity_per_lane_p95": float(
            e["capacity_per_lane"].quantile(0.95)
        ),
    }

    group = (
        e.groupby("highway", dropna=False)
        .agg(
            links=("highway", "size"),
            lanes_median=("lanes", "median"),
            permlanes_median=("permlanes", "median"),
            capacity_median=("capacity", "median"),
            capacity_per_lane_median=(
                "capacity_per_lane",
                "median",
            ),
            freespeed_median_kmh=(
                "freespeed",
                lambda s: float((s * 3.6).median()),
            ),
            speed_median=("speed_kmh", "median"),
            length_km=("length_m", lambda s: s.sum()/1000.0),
        )
        .reset_index()
        .sort_values(
            "links",
            ascending=False,
        )
    )

    return out, group


def load_target(root: Path):
    path = root / TARGET_SUMMARY
    if not path.exists():
        return pd.DataFrame()

    return pd.read_csv(
        path,
        encoding="utf-8-sig",
    )


def infer_current_config(config_summaries):
    # Prefer authored 6.3.3B configs; MATSim 的 *.output_config*.xml 是运行导出物，不是基线。
    authored = [
        x for x in config_summaries
        if "output_config" not in Path(str(x["config_file"])).name
    ]
    if not authored:
        return None

    scored = []
    for x in authored:
        s = 0
        name = str(x["config_file"]).lower()

        if "6_3_3b" in name:
            s += 10
        if "lambda_0p050" in name or "0p050" in name:
            s += 3
        if "connected" in name:
            s += 2

        scored.append(
            (s, x)
        )

    scored.sort(
        key=lambda q: (
            q[0],
            str(q[1]["config_file"]),
        ),
        reverse=True,
    )

    return scored[0][1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--project-root",
        type=Path,
        default=ROOT_DEFAULT,
    )
    args = parser.parse_args()

    root = args.project_root
    out = root / OUT
    out.mkdir(
        parents=True,
        exist_ok=True,
    )

    print("=" * 72)
    print("Step 7.2 | MATSim parameter + capacity baseline audit")
    print("=" * 72)

    configs = find_xml_configs(root)
    print(
        f"Candidate XML configs: {len(configs)}"
    )

    config_summaries = []
    config_details = []

    for p in configs:
        try:
            summary, detail = audit_config(p)
            config_summaries.append(summary)
            if not detail.empty:
                config_details.append(detail)
        except Exception as e:
            config_summaries.append(
                {
                    "config_file": str(p),
                    "status": "FAIL",
                    "error": str(e),
                }
            )

    if config_details:
        pd.concat(
            config_details,
            ignore_index=True,
        ).to_csv(
            out / "parameter_audit.csv",
            index=False,
            encoding="utf-8-sig",
        )
    else:
        pd.DataFrame().to_csv(
            out / "parameter_audit.csv",
            index=False,
            encoding="utf-8-sig",
        )

    pd.DataFrame(
        config_summaries
    ).to_csv(
        out / "config_summary.csv",
        index=False,
        encoding="utf-8-sig",
    )

    current_config = infer_current_config(
        config_summaries
    )

    print(
        "Selected baseline config:",
        current_config["config_file"]
        if current_config
        else "NONE",
    )

    network = load_network(root)

    net_summary, by_class = summarize_network(
        network
    )

    by_class.to_csv(
        out / "network_capacity_audit.csv",
        index=False,
        encoding="utf-8-sig",
    )

    target = load_target(root)

    if not target.empty:
        target.to_csv(
            out / "calibration_target_baseline.csv",
            index=False,
            encoding="utf-8-sig",
        )

    # Capacity sensitivity is a design scaffold only.
    sweep_factors = [
        0.50,
        0.75,
        1.00,
        1.25,
        1.50,
    ]

    plan = pd.DataFrame(
        {
            "capacity_factor": sweep_factors,
            "network_topology_changed": False,
            "od_changed": False,
            "lambda_changed": False,
            "population_changed": False,
            "departure_profile_changed": False,
            "route_choice_changed": False,
            "purpose": [
                "capacity-only sensitivity"
            ] * len(sweep_factors),
        }
    )

    plan.to_csv(
        out / "capacity_sweep_plan.csv",
        index=False,
        encoding="utf-8-sig",
    )

    validation = {
        "step": "7.2",
        "status": (
            "PASS"
            if (
                current_config is not None
                and net_summary["links"] > 0
                and net_summary["invalid_lanes"] == 0
                and net_summary["invalid_capacity"] == 0
            )
            else "WARN"
        ),
        "baseline_config": current_config,
        "network_summary": net_summary,
        "capacity_sweep_factors": sweep_factors,
        "model_parameters_changed": False,
        "lambda_selected": False,
        "next_step": (
            "Run capacity-only sensitivity after verifying "
            "the baseline config and preserving all frozen inputs."
        ),
    }

    with open(
        out / "step7_2_audit.json",
        "w",
        encoding="utf-8",
    ) as f:
        json.dump(
            validation,
            f,
            ensure_ascii=False,
            indent=2,
            default=str,
        )

    print("-" * 72)
    print(
        "Network links:",
        net_summary["links"],
    )
    print(
        "Median capacity:",
        net_summary["capacity_median_vph"],
    )
    print(
        "Median capacity/lane:",
        net_summary["capacity_per_lane_median"],
    )
    print(
        "Invalid capacity:",
        net_summary["invalid_capacity"],
    )
    print(
        "Capacity sweep:",
        sweep_factors,
    )
    print(
        "Output:",
        out,
    )
    print("=" * 72)


if __name__ == "__main__":
    main()
