#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Independent validation of Step 6.2B MATSim population files.

Re-parses population_lambda_*.xml.gz from scratch (does NOT trust
population_6_2b_validation.json) and checks structural + conservation invariants
against network.xml.gz and the frozen car Prior OD.

Checks per lambda:
  1. persons == expected agent count.
  2. Exactly one selected plan; plan shape == activity -> leg(car) -> activity.
  3. Element name is <activity> (i.e. MATSim population_v6 readable), not <act>.
  4. Every activity 'link' exists in network.xml.gz AND equal to a real link id.
  5. homeNode/workNode equal the from-node of the activity link (link<->node
     consistency after spatial down-scaling).
  6. expansionFactor finite and > 0.
  7. expanded OD (sum EF per originZone,destinationZone) reconstructs every
     positive car-OD cell exactly (<=1e-8) and matches its trips.
  8. OD-cell coverage == 100% and every positive cell has >=1 agent.
  9. sum(EF) == car OD total (459,794).
"""
from __future__ import annotations
import gzip, json, xml.etree.ElementTree as ET
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(r"D:\Luan\2026-05\2_Singapore")
NET = ROOT / "reports/matsim_network/network.xml.gz"
POP_DIR = ROOT / "reports/matsim_population"
B_DIR = ROOT / "reports/matsim_population_6_2b"
LAMBDAS = [0.05, 0.075, 0.10]
TARGET_AGENTS = 200_000
CAR_OD_TOTAL = 459_794.0


def load_network():
    links, frm = set(), {}
    with gzip.open(NET, "rb") as fh:
        for _, el in ET.iterparse(fh, events=("end",)):
            if el.tag == "link":
                links.add(el.get("id"))
                frm[el.get("id")] = el.get("from")
                el.clear()
    return links, frm


def car_od_cells(lam):
    tag = f"{lam:.3f}".replace(".", "p")
    od = pd.read_parquet(POP_DIR / f"car_prior_od_lambda_{tag}.parquet")
    od = od[od.trips > 1e-12]
    return {(int(a), int(b)): float(t) for a, b, t in zip(od.origin_zone, od.destination_zone, od.trips)}


def validate(lam, links, frm):
    tag = f"{lam:.3f}".replace(".", "p")
    path = B_DIR / f"population_lambda_{tag}.xml.gz"
    res = dict(lambda_per_min=lam, xml=str(path.name), persons=0, selected_plan_bad=0,
               shape_bad=0, activity_elements=0, leg_elements=0, homes=0, works=0,
               link_not_in_network=0, node_link_mismatch=0, exp_nonpos=0, exp_nonfinite=0,
               exp_sum=0.0, cells=0)
    cellsum = {}
    with gzip.open(path, "rb") as fh:
        for _, el in ET.iterparse(fh, events=("end",)):
            if el.tag != "person":
                continue
            res["persons"] += 1
            plans = [c for c in el if c.tag == "plan"]
            sel = [c for c in plans if c.get("selected") == "yes"]
            if len(sel) != 1:
                res["selected_plan_bad"] += 1
            plan = sel[0] if sel else (plans[0] if plans else None)
            attrs = {}
            at = el.find("attributes")
            if at is not None:
                for a in at.findall("attribute"):
                    attrs[a.get("name")] = a.get("value")
            if plan is None:
                res["shape_bad"] += 1
                el.clear()
                continue
            acts = [c for c in plan if c.tag == "activity"]
            legs = [c for c in plan if c.tag == "leg"]
            res["activity_elements"] += len(acts)
            res["leg_elements"] += len(legs)
            if len(acts) != 2 or len(legs) != 1 or legs[0].get("mode") != "car":
                res["shape_bad"] += 1
            else:
                htype, wtype = acts[0].get("type"), acts[1].get("type")
                if htype == "home":
                    res["homes"] += 1
                if wtype == "work":
                    res["works"] += 1
                hl, wl = acts[0].get("link"), acts[1].get("link")
                if hl not in links:
                    res["link_not_in_network"] += 1
                if wl not in links:
                    res["link_not_in_network"] += 1
                if str(attrs.get("homeNode")) != str(frm.get(hl)):
                    res["node_link_mismatch"] += 1
                if str(attrs.get("workNode")) != str(frm.get(wl)):
                    res["node_link_mismatch"] += 1
            ef = float(attrs.get("expansionFactor", "nan"))
            if not np.isfinite(ef):
                res["exp_nonfinite"] += 1
            elif ef <= 0:
                res["exp_nonpos"] += 1
            else:
                res["exp_sum"] += ef
                key = (int(attrs["originZone"]), int(attrs["destinationZone"]))
                cellsum[key] = cellsum.get(key, 0.0) + ef
            el.clear()
    res["cells"] = len(cellsum)
    od = car_od_cells(lam)
    res["positive_od_cells"] = len(od)
    # conservation
    missing = [k for k in od if k not in cellsum]
    res["cells_missing_agent"] = len(missing)
    maxerr = max((abs(cellsum.get(k, 0.0) - v) for k, v in od.items()), default=0.0)
    res["max_cell_error"] = float(maxerr)
    res["coverage"] = float(1.0 - len(missing) / len(od))
    res["car_od_total"] = float(sum(od.values()))
    return res


def main():
    print("Loading network link index...")
    links, frm = load_network()
    print(f"  links={len(links)}")
    out = {"network_links": len(links), "target_agents": TARGET_AGENTS, "per_lambda": []}
    for lam in LAMBDAS:
        r = validate(lam, links, frm)
        ok = (r["persons"] == TARGET_AGENTS and r["selected_plan_bad"] == 0 and r["shape_bad"] == 0
              and r["activity_elements"] == 2 * TARGET_AGENTS and r["leg_elements"] == TARGET_AGENTS
              and r["link_not_in_network"] == 0 and r["node_link_mismatch"] == 0
              and r["exp_nonpos"] == 0 and r["exp_nonfinite"] == 0
              and r["cells"] == r["positive_od_cells"] and r["cells_missing_agent"] == 0
              and r["max_cell_error"] < 1e-8 and abs(r["exp_sum"] - CAR_OD_TOTAL) < 1e-3)
        r["PASS"] = bool(ok)
        out["per_lambda"].append(r)
        print(f"lambda {lam:.3f}: persons={r['persons']} cells={r['cells']}/{r['positive_od_cells']} "
              f"coverage={r['coverage']:.4f} exp_sum={r['exp_sum']:.3f} max_cell_err={r['max_cell_error']:.2e} "
              f"node_mismatch={r['node_link_mismatch']} link_missing={r['link_not_in_network']} -> {'PASS' if ok else 'FAIL'}")
    out["ALL_CHECKS_PASS"] = bool(all(x["PASS"] for x in out["per_lambda"]))
    with open(B_DIR / "population_6_2b_independent_check.json", "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print("ALL_CHECKS_PASS:", out["ALL_CHECKS_PASS"])


if __name__ == "__main__":
    main()
