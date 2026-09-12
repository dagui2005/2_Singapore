#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Step 6.3.3A
TrafficFlow-driven AM departure-time profile.

Purpose:
    Replace the artificial "all agents depart at 08:00" pulse in the frozen
    Step-6.2B MATSim population.

Method:
    1. Read TrafficFlow_Data.json.
    2. Keep workdays and HourOfDate 7/8.
    3. For every LinkID x hour, compute the median of daily observed volume.
    4. Sum these per-link medians over links to obtain a robust network-level
       temporal shape.
    5. Assign that 07:00-08:00 / 08:00-09:00 share to every car agent,
       preserving all OD fields and expansion factors.
    6. Within the selected hour, draw a deterministic uniform second-level
       departure time. Thus agents are temporally dispersed, not synchronized
       to the hour boundary.

Frozen model quantities NOT changed:
    OD trips, expansion factor, home link, work link, lambda.

This is a temporal-shape prior derived from observed network traffic, not a
claim that TrafficFlow directly observes resident departure-time behavior.
"""

from __future__ import annotations

import argparse
import gzip
import json
import re
from pathlib import Path

import numpy as np
import pandas as pd


ROOT_DEFAULT = Path(r"D:\Luan\2026-05\2_Singapore")
FLOW_FILE = Path(
    "Singapore_OD_MATSim_FinalData/08_TrafficCount/TrafficFlow_Data.json"
)
POP_DIR = Path("reports/matsim_population_6_2b_connected")
FALLBACK_POP_DIR = Path("reports/matsim_population_6_2b")
OUT = Path("reports/matsim_departure_6_3_3a")

DEFAULT_LAMBDAS = [0.05, 0.075, 0.10]
DEFAULT_SEED = 20260912


def parse_volume(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["LinkID"] = df["LinkID"].astype(str).str.strip()
    df["Date"] = pd.to_datetime(
        df["Date"],
        dayfirst=True,
        errors="coerce",
    )
    df["HourOfDate"] = pd.to_numeric(
        df["HourOfDate"],
        errors="coerce",
    )
    df["Volume"] = pd.to_numeric(
        df["Volume"].astype(str).str.replace(",", "", regex=False),
        errors="coerce",
    )
    return df


def load_flow_profile(root: Path):
    path = root / FLOW_FILE
    with path.open("r", encoding="utf-8") as f:
        obj = json.load(f)

    records = obj["Value"] if isinstance(obj, dict) else obj
    df = parse_volume(pd.DataFrame(records))

    df = df[
        df["Date"].notna()
        & df["Date"].dt.weekday.lt(5)
        & df["HourOfDate"].isin([7, 8])
        & df["Volume"].notna()
    ].copy()

    if df.empty:
        raise ValueError("TrafficFlow 中没有可用的工作日 07/08 时段记录")

    # Robust per-link daily representative.
    daily = (
        df.groupby(
            ["LinkID", "Date", "HourOfDate"],
            as_index=False,
        )["Volume"]
        .mean()
    )

    link_hour = (
        daily.groupby(
            ["LinkID", "HourOfDate"],
            as_index=False,
        )["Volume"]
        .median()
    )

    totals = (
        link_hour.groupby(
            "HourOfDate",
        )["Volume"]
        .sum()
    )

    v7 = float(totals.get(7, 0.0))
    v8 = float(totals.get(8, 0.0))

    if v7 <= 0 or v8 <= 0:
        raise ValueError(
            f"07/08 网络流量不能用于比例估计: {v7=}, {v8=}"
        )

    total = v7 + v8

    profile = pd.DataFrame(
        [
            {
                "hour": 7,
                "window": "07:00:00-08:00:00",
                "network_volume_index": v7,
                "share": v7 / total,
            },
            {
                "hour": 8,
                "window": "08:00:00-09:00:00",
                "network_volume_index": v8,
                "share": v8 / total,
            },
        ]
    )

    return profile, link_hour


def locate_population(root: Path, lam: float):
    tag = f"{lam:.3f}".replace(".", "p")

    dirs = [
        root / POP_DIR,
        root / FALLBACK_POP_DIR,
    ]

    for d in dirs:
        csv_path = d / f"agent_spatial_assignment_lambda_{tag}.csv"
        xml_path = d / f"population_lambda_{tag}.xml.gz"

        if csv_path.exists():
            return csv_path, (xml_path if xml_path.exists() else None)

    raise FileNotFoundError(
        f"找不到 lambda={lam} 的 6.2B population CSV"
    )


def assign_departures(df, shares, rng):
    n = len(df)

    n7 = int(
        round(
            n * float(
                shares.loc[
                    shares["hour"].eq(7),
                    "share",
                ].iloc[0]
            )
        )
    )
    n7 = max(0, min(n, n7))

    # Shuffle deterministically so the temporal pattern is not correlated
    # with OD-cell/order in the source CSV.
    idx = np.arange(n)
    rng.shuffle(idx)

    chosen7 = idx[:n7]
    chosen8 = idx[n7:]

    departure = np.empty(
        n,
        dtype=float,
    )

    departure[chosen7] = 7 * 3600 + rng.uniform(
        0,
        3600,
        size=len(chosen7),
    )
    departure[chosen8] = 8 * 3600 + rng.uniform(
        0,
        3600,
        size=len(chosen8),
    )

    df = df.copy()
    df["departure_time_s"] = departure
    df["departure_time"] = pd.to_timedelta(
        departure,
        unit="s",
    ).map(
        lambda x: (
            f"{int(x.total_seconds() // 3600):02d}:"
            f"{int(x.total_seconds() % 3600 // 60):02d}:"
            f"{int(x.total_seconds() % 60):02d}"
        )
    )

    return df


def update_population_xml_streaming(
    input_xml,
    output_xml,
    departure_by_agent,
):
    """
    Streaming line transformation.

    The existing 6.2B writer emits:
      <person id="...">
        ...
        <activity type="home" ... end_time="08:00:00" />
    Therefore only the home activity's end_time is replaced.

    We intentionally do not rewrite or reserialize the whole XML tree.
    """

    person_re = re.compile(
        rb'<person\s+id="([^"]+)"'
    )
    home_re = re.compile(
        rb'(<activity\b[^>]*\btype="home"[^>]*\bend_time=")[^"]+(")'
    )

    current_agent = None
    changed = 0
    persons = 0

    output_xml.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with gzip.open(
        input_xml,
        "rb",
    ) as src, gzip.open(
        output_xml,
        "wb",
        compresslevel=6,
    ) as dst:

        for raw in src:
            m = person_re.search(raw)
            if m:
                current_agent = (
                    m.group(1)
                    .decode("utf-8")
                )
                persons += 1

            if (
                current_agent is not None
                and b'type="home"' in raw
                and b'end_time="' in raw
            ):
                dep = departure_by_agent.get(
                    current_agent
                )
                if dep is not None:
                    raw2, n = home_re.subn(
                        (
                            rb'\g<1>'
                            + dep.encode("ascii")
                            + rb'\g<2>'
                        ),
                        raw,
                        count=1,
                    )
                    if n:
                        raw = raw2
                        changed += 1

            dst.write(raw)

    return {
        "persons_seen": persons,
        "home_activities_updated": changed,
    }


def validate_times(df):
    dep = pd.to_numeric(
        df["departure_time_s"],
        errors="coerce",
    )

    return {
        "min_departure_s": float(dep.min()),
        "max_departure_s": float(dep.max()),
        "count_07_08": int(
            ((dep >= 7 * 3600) & (dep < 8 * 3600)).sum()
        ),
        "count_08_09": int(
            ((dep >= 8 * 3600) & (dep < 9 * 3600)).sum()
        ),
        "duplicate_agents": int(
            df["agent_id"].duplicated().sum()
        ),
        "missing_times": int(
            dep.isna().sum()
        ),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--project-root",
        type=Path,
        default=ROOT_DEFAULT,
    )
    parser.add_argument(
        "--lambdas",
        nargs="+",
        type=float,
        default=DEFAULT_LAMBDAS,
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=DEFAULT_SEED,
    )
    args = parser.parse_args()

    root = args.project_root
    out = root / OUT
    out.mkdir(
        parents=True,
        exist_ok=True,
    )

    profile, link_hour = load_flow_profile(root)

    profile.to_csv(
        out / "departure_profile.csv",
        index=False,
        encoding="utf-8-sig",
    )

    link_hour.to_csv(
        out / "trafficflow_link_hour_basis.csv",
        index=False,
        encoding="utf-8-sig",
    )

    summaries = []

    for lam in args.lambdas:
        tag = f"{lam:.3f}".replace(".", "p")
        rng = np.random.default_rng(
            args.seed
            + int(round(lam * 1000))
        )

        csv_path, xml_path = locate_population(
            root,
            lam,
        )

        pop = pd.read_csv(
            csv_path,
            encoding="utf-8-sig",
            low_memory=False,
        )

        required = {
            "agent_id",
            "origin_zone",
            "destination_zone",
            "home_link",
            "work_link",
            "expansion_factor",
        }

        missing = required - set(pop.columns)
        if missing:
            raise ValueError(
                f"{csv_path} 缺字段: {sorted(missing)}"
            )

        shares = profile[
            [
                "hour",
                "share",
            ]
        ]

        pop2 = assign_departures(
            pop,
            shares,
            rng,
        )

        # Preserve all prior fields; only append departure columns.
        output_csv = (
            out
            / f"agent_departure_assignment_lambda_{tag}.csv"
        )
        pop2.to_csv(
            output_csv,
            index=False,
            encoding="utf-8-sig",
        )

        xml_summary = None

        # XML is optional when running purely as a profile generator.
        if xml_path is not None:
            output_xml = (
                out
                / f"population_lambda_{tag}.xml.gz"
            )

            dep_map = dict(
                zip(
                    pop2["agent_id"].astype(str),
                    pop2["departure_time"],
                )
            )

            xml_summary = update_population_xml_streaming(
                xml_path,
                output_xml,
                dep_map,
            )

        time_summary = validate_times(
            pop2
        )

        # Check that expansion factors and OD support are unchanged.
        od_total = float(
            pop2["expansion_factor"].sum()
        )

        # Realized trip-weighted (EF-weighted) temporal share. Because the
        # assignment is done on the agent count, the EF-weighted share is only
        # approximately equal to the network-derived share; reporting both
        # documents that the temporal profile does NOT change total demand.
        ef = pd.to_numeric(
            pop2["expansion_factor"],
            errors="coerce",
        ).fillna(0.0)
        dep_s = pd.to_numeric(
            pop2["departure_time_s"],
            errors="coerce",
        )
        in7 = (dep_s >= 7 * 3600) & (dep_s < 8 * 3600)
        ef_total = float(ef.sum())
        ef7 = float(ef[in7].sum())

        summaries.append(
            {
                "lambda_per_min": lam,
                "agents": int(len(pop2)),
                "real_trip_equivalent": od_total,
                "departure_share_07_08": float(
                    profile.loc[
                        profile["hour"].eq(7),
                        "share",
                    ].iloc[0]
                ),
                "departure_share_08_09": float(
                    profile.loc[
                        profile["hour"].eq(8),
                        "share",
                    ].iloc[0]
                ),
                "departure_ef_share_07_08": (
                    ef7 / ef_total if ef_total else None
                ),
                "departure_ef_share_08_09": (
                    (ef_total - ef7) / ef_total if ef_total else None
                ),
                **time_summary,
                "xml_updated_persons": (
                    xml_summary["persons_seen"]
                    if xml_summary
                    else None
                ),
                "xml_updated_home_activities": (
                    xml_summary["home_activities_updated"]
                    if xml_summary
                    else None
                ),
            }
        )

    summary_df = pd.DataFrame(
        summaries
    )

    summary_df.to_csv(
        out / "departure_assignment_summary.csv",
        index=False,
        encoding="utf-8-sig",
    )

    status = (
        "PASS"
        if (
            summary_df["missing_times"].eq(0).all()
            and summary_df["duplicate_agents"].eq(0).all()
            and summary_df["count_07_08"].gt(0).all()
            and summary_df["count_08_09"].gt(0).all()
        )
        else "FAIL"
    )

    with open(
        out / "departure_profile_validation.json",
        "w",
        encoding="utf-8",
    ) as f:
        json.dump(
            {
                "status": status,
                "method": (
                    "workday LinkID×hour daily median, then sum over LinkIDs"
                ),
                "profile": profile.to_dict(
                    orient="records"
                ),
                "summary": summaries,
                "frozen_quantities": [
                    "OD trips",
                    "expansion_factor",
                    "home_link",
                    "work_link",
                    "lambda",
                ],
                "interpretation": (
                    "TrafficFlow-derived temporal shape prior, not direct resident "
                    "departure-time observation."
                ),
            },
            f,
            ensure_ascii=False,
            indent=2,
        )

    print("=" * 72)
    print("Step 6.3.3A | Departure-time profile")
    print("=" * 72)
    print(profile.to_string(index=False))
    print("-" * 72)
    print(summary_df.to_string(index=False))
    print(f"STATUS: {status}")
    print(f"OUTPUT: {out}")
    print("=" * 72)


if __name__ == "__main__":
    main()
