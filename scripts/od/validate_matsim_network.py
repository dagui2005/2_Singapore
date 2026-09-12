#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Independent validation of reports/matsim_network/network.xml.gz.

This does NOT trust network_validation.json: it re-parses the produced XML and
re-checks the structural invariants MATSim relies on, plus cross-checks the
Zone -> MATSim node map against the network.

Output:
    reports/matsim_network/network_independent_check.json
"""
from __future__ import annotations
import gzip, json
from pathlib import Path
import xml.etree.ElementTree as ET

ROOT = Path(r"D:\Luan\2026-05\2_Singapore")
NET = ROOT / "reports/matsim_network/network.xml.gz"
ZMAP = ROOT / "reports/matsim_network/zone_matsim_node_map.csv"


def main() -> None:
    node_ids: set[str] = set()
    dup_node = 0
    n_nodes = 0
    link_ids: set[str] = set()
    dup_link = 0
    n_links = 0
    bad_ref = 0
    self_loop = 0
    fs_min, fs_max = 1e9, -1e9
    cap_min, cap_max = 1e18, -1e18
    lane_min, lane_max = 1e9, -1e9
    missing_attr = 0
    with gzip.open(NET, "rb") as f:
        for event, el in ET.iterparse(f, events=("end",)):
            if el.tag == "node":
                nid = el.get("id")
                if nid in node_ids:
                    dup_node += 1
                node_ids.add(nid); n_nodes += 1
                el.clear()
            elif el.tag == "link":
                lid = el.get("id"); frm = el.get("from"); to = el.get("to")
                if lid in link_ids:
                    dup_link += 1
                link_ids.add(lid); n_links += 1
                if None in (lid, frm, to, el.get("length"), el.get("freespeed"),
                            el.get("capacity"), el.get("permlanes")):
                    missing_attr += 1
                else:
                    if frm == to:
                        self_loop += 1
                    fs = float(el.get("freespeed")) * 3.6
                    ca = float(el.get("capacity"))
                    ln = float(el.get("permlanes"))
                    fs_min, fs_max = min(fs_min, fs), max(fs_max, fs)
                    cap_min, cap_max = min(cap_min, ca), max(cap_max, ca)
                    lane_min, lane_max = min(lane_min, ln), max(lane_max, ln)
                el.clear()

    # references resolved against the (now fully read) node id set
    with gzip.open(NET, "rb") as f:
        for event, el in ET.iterparse(f, events=("end",)):
            if el.tag == "link":
                if el.get("from") not in node_ids or el.get("to") not in node_ids:
                    bad_ref += 1
                el.clear()

    # zone map cross-check
    import csv
    zmap_rows = 0
    z_bad = 0
    z_missing_col = False
    max_snap = 0.0
    with open(ZMAP, encoding="utf-8-sig") as fh:
        rd = csv.DictReader(fh)
        if not {"zone_id", "matsim_node_id"}.issubset(rd.fieldnames or []):
            z_missing_col = True
        for r in rd:
            zmap_rows += 1
            if str(int(float(r["matsim_node_id"]))) not in node_ids:
                z_bad += 1
            if r.get("snap_distance_m"):
                max_snap = max(max_snap, float(r["snap_distance_m"]))

    res = {
        "xml_nodes": n_nodes,
        "xml_links": n_links,
        "duplicate_node_ids": dup_node,
        "duplicate_link_ids": dup_link,
        "links_with_bad_node_ref": bad_ref,
        "self_loops": self_loop,
        "links_missing_attribute": missing_attr,
        "freespeed_kmh_min": round(fs_min, 3),
        "freespeed_kmh_max": round(fs_max, 3),
        "capacity_min": round(cap_min, 3),
        "capacity_max": round(cap_max, 3),
        "permlanes_min": lane_min,
        "permlanes_max": lane_max,
        "zone_map_rows": zmap_rows,
        "zone_map_bad_node_ref": z_bad,
        "zone_map_max_snap_m": round(max_snap, 3),
        "zone_map_missing_column": z_missing_col,
    }
    res["ALL_CHECKS_PASS"] = (
        dup_node == 0 and dup_link == 0 and bad_ref == 0 and self_loop == 0
        and missing_attr == 0 and n_nodes == 429032 and n_links == 706554
        and zmap_rows == 332 and z_bad == 0 and not z_missing_col
    )
    out = ROOT / "reports/matsim_network/network_independent_check.json"
    with open(out, "w", encoding="utf-8") as f:
        json.dump(res, f, ensure_ascii=False, indent=2)
    print(json.dumps(res, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
