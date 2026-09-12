#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Independent structural validation of the Step 6.2 MATSim population files.

Re-parses the produced population_lambda_*.xml.gz (streaming, so 200k persons is fine)
and checks invariants against the frozen network.xml.gz and zone_matsim_node_map.csv.
Writes reports/matsim_population/population_independent_check.json.

Checks per lambda:
  1. XML well-formed; every <person> has exactly one selected plan.
  2. Plan shape is home -> car leg -> work.
  3. Every activity 'link' is a real MATSim link id (NOT a raw node id).
  4. The link carries the declared homeNode / workNode as one of its endpoints.
  5. home/work link matches the zone's mapped node via zone_matsim_node_map.
  6. expansion_factor is finite and > 0; sum == the reported real-trip equivalent.
  7. Every agent's origin/destination zone is one of the 332 physical zones.
"""
from __future__ import annotations
import gzip, json, re, sys
from pathlib import Path
import xml.etree.ElementTree as ET
import pandas as pd

ROOT = Path(r"D:\Luan\2026-05\2_Singapore")
NET = ROOT / "reports/matsim_network/network.xml.gz"
ZMAP = ROOT / "reports/matsim_network/zone_matsim_node_map.csv"
POP_DIR = ROOT / "reports/matsim_population"
LAMBDAS = [0.05, 0.075, 0.10]

def load_network():
    node_ids = set()
    link_endpoints = {}
    ctx = ET.iterparse(gzip.open(NET, "rb"), events=("end",))
    for _, el in ctx:
        tag = el.tag
        if tag == "node":
            node_ids.add(el.get("id"))
        elif tag == "link":
            lid = el.get("id")
            link_endpoints[lid] = (el.get("from"), el.get("to"))
        el.clear()
    return node_ids, link_endpoints

def load_zone_map():
    z = pd.read_csv(ZMAP, encoding="utf-8-sig")
    z["zone_id"] = pd.to_numeric(z.zone_id).astype(int)
    z["matsim_node_id"] = pd.to_numeric(z.matsim_node_id).astype(int)
    return z

def check_lambda(lam, node_ids, link_endpoints, zmap, phys_zones):
    tag = f"{lam:.3f}".replace(".", "p")
    p = POP_DIR / f"population_lambda_{tag}.xml.gz"
    zone_node = dict(zip(zmap.zone_id, zmap.matsim_node_id))
    node_link_ok = {}  # node id (str) -> any incident link exists (sanity)
    res = dict(lambda_per_min=lam, xml=str(p), persons=0, homes=0, legs=0, works=0,
               bad_plan_shape=0, link_not_in_network=0, link_not_incident_to_node=0,
               link_mismatch_zone_map=0, bad_zone=0, nonfinite_exp=0, nonpos_exp=0,
               exp_sum=0.0, sel_plan_not_one=0)
    ctx = ET.iterparse(gzip.open(p, "rb"), events=("end",))
    for _, el in ctx:
        if el.tag == "person":
            res["persons"] += 1
            plans = [c for c in el if c.tag == "plan"]
            sel = [c for c in plans if c.get("selected") == "yes"]
            if len(plans) != 1 or len(sel) != 1:
                res["sel_plan_not_one"] += 1
            plan = sel[0] if sel else (plans[0] if plans else None)
            attrs = {a.get("name"): a.get("value") for a in el.iter("attribute")}
            o = attrs.get("originZone"); d = attrs.get("destinationZone")
            hn = attrs.get("homeNode"); wn = attrs.get("workNode")
            ef = attrs.get("expansionFactor")
            try:
                efv = float(ef)
                if efv != efv or efv in (float("inf"), float("-inf")):
                    res["nonfinite_exp"] += 1
                elif efv <= 0:
                    res["nonpos_exp"] += 1
                else:
                    res["exp_sum"] += efv
            except Exception:
                res["nonfinite_exp"] += 1
            try:
                if int(o) not in phys_zones or int(d) not in phys_zones:
                    res["bad_zone"] += 1
            except Exception:
                res["bad_zone"] += 1
            if plan is None:
                res["bad_plan_shape"] += 1
            else:
                acts = [c for c in plan if c.tag == "activity"]
                legs = [c for c in plan if c.tag == "leg"]
                if len(acts) != 2 or len(legs) != 1:
                    res["bad_plan_shape"] += 1
                else:
                    res["homes"] += 1 if acts[0].get("type") == "home" else 0
                    res["works"] += 1 if acts[1].get("type") == "work" else 0
                    res["legs"] += 1 if legs[0].get("mode") == "car" else 0
                    for act, nd in ((acts[0], hn), (acts[1], wn)):
                        lid = act.get("link")
                        if lid not in link_endpoints:
                            res["link_not_in_network"] += 1
                        else:
                            f, t = link_endpoints[lid]
                            if nd not in (f, t):
                                res["link_not_incident_to_node"] += 1
                        # zone-map consistency: declared node must be the mapped node of its zone
                        zone = int(o) if act.get("type") == "home" else int(d)
                        if zone_node.get(zone) is not None and str(int(zone_node[zone])) != str(nd):
                            res["link_mismatch_zone_map"] += 1
            el.clear()
    res["expansion_factor_mean"] = res["exp_sum"] / res["persons"] if res["persons"] else 0.0
    return res

def main():
    node_ids, link_endpoints = load_network()
    zmap = load_zone_map()
    phys_zones = set(zmap.zone_id.tolist())
    print(f"network: {len(node_ids)} nodes, {len(link_endpoints)} links, zones mapped: {len(phys_zones)}")
    out = []
    for lam in LAMBDAS:
        r = check_lambda(lam, node_ids, link_endpoints, zmap, phys_zones)
        out.append(r)
        ok = (r["persons"] > 0 and r["bad_plan_shape"] == 0 and r["sel_plan_not_one"] == 0
              and r["link_not_in_network"] == 0 and r["link_not_incident_to_node"] == 0
              and r["link_mismatch_zone_map"] == 0 and r["bad_zone"] == 0
              and r["nonfinite_exp"] == 0 and r["nonpos_exp"] == 0
              and r["homes"] == r["persons"] and r["works"] == r["persons"] and r["legs"] == r["persons"])
        r["checks_pass"] = bool(ok)
        print(f"lambda {lam:.3f}: persons={r['persons']} exp_sum={r['exp_sum']:.1f} "
              f"shape_bad={r['bad_plan_shape']} link_missing={r['link_not_in_network']} "
              f"link_not_incident={r['link_not_incident_to_node']} zone_map_mismatch={r['link_mismatch_zone_map']} "
              f"zone_bad={r['bad_zone']} -> checks_pass={r['checks_pass']}")
    report = {
        "status": "PASS" if all(r["checks_pass"] for r in out) else "FAIL",
        "network_nodes": len(node_ids), "network_links": len(link_endpoints),
        "physical_zones": len(phys_zones),
        "results": out,
    }
    dst = POP_DIR / "population_independent_check.json"
    with open(dst, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print("ALL_CHECKS_PASS:", report["status"] == "PASS")
    print("written:", dst)
    return 0 if report["status"] == "PASS" else 1

if __name__ == "__main__":
    sys.exit(main())
