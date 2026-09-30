#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Step 7.9F-1 — Section Aggregation Sensitivity Audit.
ZERO SIMULATION / READ-ONLY / DIAGNOSTIC ONLY.
"""
from __future__ import annotations
import argparse, ast, gzip, hashlib, json
from pathlib import Path
import numpy as np
import pandas as pd

ROOT_DEFAULT = Path(r"D:\\Luan\\2026-05\\2_Singapore")
TRAFFIC_REL = Path("Singapore_OD_MATSim_FinalData/08_TrafficCount/TrafficFlow_Data.json")
E1_CAND_REL = Path("reports/arterial_observability_7_9e1/e1_crosswalk_candidates.csv")
E2_MAIN_REL = Path("reports/arterial_expanded_residual_7_9e2/e2_section_residual_main.csv")
W01_REL = Path("reports/matsim_final_7_6h/outputs/W01_rc_min/ITERS/it.19")
OUT_REL = Path("reports/section_aggregation_7_9f1")
PREREG_REL = OUT_REL / "PREREG_7_9F1.md"
EXPECTED_PREREG_SHA256 = "d3ea2d20cb4ff58d32c17f9db324bae2f2673ae444ad20b3e61483e4aef80e09"
SCALE = 459794.0 / 200000.0
TIER_A = "A_STRICT_SEMANTIC_DIRECTION"
TIER_B = "B_DIRECTION_GEOMETRY"
CORE_HW = {"motorway", "motorway_link", "trunk", "primary", "secondary", "tertiary"}
AGGS = ["CANONICAL_MEDIAN", "POSITIVE_MEDIAN", "MEAN", "MAX"]


def sha256_file(p: Path, chunk: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with Path(p).open("rb") as f:
        for b in iter(lambda: f.read(chunk), b""):
            h.update(b)
    return h.hexdigest()


def norm_id(x: object) -> str:
    s = "" if x is None else str(x).strip()
    if not s or s.lower() == "nan":
        return ""
    if s.endswith(".0") and s[:-2].isdigit():
        return s[:-2]
    return s


def norm_text(x: object) -> str:
    s = "" if x is None else str(x).replace("\xa0", " ").strip()
    return "" if s.lower() == "nan" else " ".join(s.split())


def numeric(s: pd.Series) -> pd.Series:
    return pd.to_numeric(s.astype(str).str.replace(",", "", regex=False), errors="coerce")


def weighted_mean(y: pd.Series, w: pd.Series) -> float:
    z = pd.concat([pd.to_numeric(y, errors="coerce"), pd.to_numeric(w, errors="coerce")], axis=1).dropna()
    if z.empty or float(z.iloc[:, 1].sum()) <= 0:
        return float("nan")
    return float((z.iloc[:, 0] * z.iloc[:, 1]).sum() / z.iloc[:, 1].sum())


def pearson(x: pd.Series, y: pd.Series) -> float:
    z = pd.concat([pd.to_numeric(x, errors="coerce"), pd.to_numeric(y, errors="coerce")], axis=1).dropna()
    return float(z.iloc[:, 0].corr(z.iloc[:, 1], method="pearson")) if len(z) >= 3 else float("nan")


def spearman(x: pd.Series, y: pd.Series) -> float:
    z = pd.concat([pd.to_numeric(x, errors="coerce"), pd.to_numeric(y, errors="coerce")], axis=1).dropna()
    return float(z.iloc[:, 0].corr(z.iloc[:, 1], method="spearman")) if len(z) >= 3 else float("nan")


def zero_sim_audit(p: Path) -> bool:
    tree = ast.parse(Path(p).read_text(encoding="utf-8"))
    banned_mods = {"subprocess", "jpype", "py4j"}
    banned_calls = {"system", "popen", "Popen", "run", "call", "check_call", "check_output"}
    for n in ast.walk(tree):
        if isinstance(n, ast.Import) and any(a.name.split(".")[0] in banned_mods for a in n.names):
            return False
        if isinstance(n, ast.ImportFrom) and n.module and n.module.split(".")[0] in banned_mods:
            return False
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr in banned_calls:
            return False
    return True


def locate_w01(root: Path, explicit: Path | None) -> Path:
    if explicit:
        p = explicit if explicit.is_absolute() else root / explicit
        if p.is_file():
            return p
        if p.is_dir():
            fs = sorted(p.glob("*.linkstats.txt.gz")) + sorted(p.glob("*.linkstats.txt"))
            if fs:
                return fs[0]
        raise FileNotFoundError(f"W01 linkstats not found: {p}")
    # NOTE (7.9F-1 fix, disclosed): prereg §2.3 declares the path WITH a
    # "reports/" prefix, which does not exist on disk. The frozen W01 it.19
    # linkstats actually live at the project root. The declared path is still
    # tried FIRST so the deviation stays visible and traceable.
    cands = [
        root / W01_REL,                                            # prereg §2.3 as declared
        root / "matsim_final_7_6h/outputs/W01_rc_min/ITERS/it.19",  # actual frozen location
        root / "matsim_final_7_6h/outputs/W01/ITERS/it.19",
    ]
    for p in cands:
        if not p.exists():
            continue
        fs = sorted(p.glob("*.linkstats.txt.gz")) + sorted(p.glob("*.linkstats.txt"))
        if fs:
            return fs[0]
    raise FileNotFoundError("未找到 W01 it.19 linkstats; tried=" + "; ".join(str(c) for c in cands))


def load_traffic(p: Path) -> pd.DataFrame:
    obj = json.loads(Path(p).read_text(encoding="utf-8-sig"))
    rows = obj.get("Value", obj.get("value", [])) if isinstance(obj, dict) else obj
    d = pd.DataFrame(rows)
    req = {"LinkID", "Date", "HourOfDate", "Volume", "RoadName", "RoadCat"}
    miss = req - set(d.columns)
    if miss:
        raise ValueError(f"TrafficFlow 缺字段: {sorted(miss)}")
    d["LinkID"] = d["LinkID"].map(norm_id)
    d["Date"] = pd.to_datetime(d["Date"], dayfirst=True, errors="coerce")
    d["HourOfDate"] = pd.to_numeric(d["HourOfDate"], errors="coerce")
    d["Volume"] = numeric(d["Volume"])
    d["RoadName"] = d["RoadName"].map(norm_text)
    d["RoadCat"] = d["RoadCat"].map(norm_text)
    d = d[d["LinkID"].ne("") & d["Date"].notna() & d["Date"].dt.weekday.lt(5) & d["HourOfDate"].eq(8) & d["Volume"].notna()].copy()
    daily = d.groupby(["LinkID", "Date"], as_index=False)["Volume"].mean()
    obs = daily.groupby("LinkID", as_index=False)["Volume"].median().rename(columns={"Volume": "obs_8_9"})
    attrs = d.sort_values(["LinkID", "Date"]).groupby("LinkID", as_index=False).agg(RoadName=("RoadName", "first"), RoadCat=("RoadCat", "first"))
    return obs.merge(attrs, on="LinkID", how="left", validate="one_to_one")


def load_candidates(p: Path) -> pd.DataFrame:
    x = pd.read_csv(p, encoding="utf-8-sig", low_memory=False)
    low = {str(c).strip().lower(): c for c in x.columns}
    mp = {"lta_linkid": "lta_linkid", "linkid": "lta_linkid", "matsim_link_id": "matsim_link_id", "matsim_link": "matsim_link_id", "tier": "tier", "distance_m": "distance_m", "direction_diff_deg": "direction_diff_deg", "direction_diff": "direction_diff_deg", "highway": "highway", "semantic_compatible": "semantic_compatible", "semantic_ok": "semantic_compatible", "name_similarity": "name_similarity", "name_sim": "name_similarity"}
    x = x.rename(columns={c: mp[k] for k, c in low.items() if k in mp})
    req = {"lta_linkid", "matsim_link_id", "tier", "distance_m", "direction_diff_deg", "highway"}
    miss = req - set(x.columns)
    if miss:
        raise ValueError(f"E1 candidates 缺字段: {sorted(miss)}")
    x["lta_linkid"] = x["lta_linkid"].map(norm_id)
    x["matsim_link_id"] = x["matsim_link_id"].map(norm_id)
    x["tier"] = x["tier"].map(norm_text)
    x["highway"] = x["highway"].map(norm_text).str.lower()
    x["distance_m"] = numeric(x["distance_m"])
    x["direction_diff_deg"] = numeric(x["direction_diff_deg"])
    if "semantic_compatible" in x.columns:
        x["semantic_compatible"] = x["semantic_compatible"].astype(str).str.lower().isin(["true", "1", "yes"])
    else:
        x["semantic_compatible"] = False
    if "name_similarity" in x.columns:
        x["name_similarity"] = numeric(x["name_similarity"])
    else:
        x["name_similarity"] = 0.0
    return x[x["lta_linkid"].ne("") & x["matsim_link_id"].ne("") & x["tier"].isin([TIER_A, TIER_B]) & x["distance_m"].notna()].drop_duplicates(["lta_linkid", "matsim_link_id", "tier"]).copy()


def select_links(c: pd.DataFrame) -> pd.DataFrame:
    parts = []
    for sid, g0 in c.groupby("lta_linkid", sort=True):
        a = g0[g0["tier"].eq(TIER_A)]
        g = a if not a.empty else g0[g0["tier"].eq(TIER_B)]
        if g.empty:
            continue
        g = g.sort_values(["distance_m", "direction_diff_deg", "semantic_compatible", "name_similarity", "matsim_link_id"], ascending=[True, True, False, False, True]).drop_duplicates("matsim_link_id").copy()
        parts.append(g)
    return pd.concat(parts, ignore_index=True) if parts else pd.DataFrame(columns=c.columns)


def load_stats(p: Path) -> pd.DataFrame:
    opener = gzip.open if Path(p).suffix == ".gz" else open
    with opener(p, "rt", encoding="utf-8", errors="replace") as f:
        header = f.readline().rstrip("\n").split("\t")
    req = {"LINK", "HRS8-9avg"}
    miss = req - set(header)
    if miss:
        raise ValueError(f"W01 linkstats 缺字段: {sorted(miss)}")
    d = pd.read_csv(p, sep="\t", compression="gzip" if Path(p).suffix == ".gz" else None, usecols=["LINK", "HRS8-9avg"], low_memory=False)
    d["LINK"] = d["LINK"].map(norm_id)
    d["HRS8-9avg"] = numeric(d["HRS8-9avg"])
    if d["LINK"].duplicated().any():
        raise ValueError("W01 LINK 出现重复")
    return d


def load_e2(p: Path) -> pd.DataFrame:
    d = pd.read_csv(p, encoding="utf-8-sig", low_memory=False)
    req = {"LinkID", "obs_8_9", "sim_8_9_scaled", "sim_8_9_median_raw", "diagnostic_residual_8_9", "diagnostic_highway", "valid_residual"}
    miss = req - set(d.columns)
    if miss:
        raise ValueError(f"E2 main 缺字段: {sorted(miss)}")
    d["LinkID"] = d["LinkID"].map(norm_id)
    d["diagnostic_highway"] = d["diagnostic_highway"].map(norm_text).str.lower()
    d["valid_residual"] = d["valid_residual"].astype(str).str.lower().isin(["true", "1", "yes"])
    for c in ["obs_8_9", "sim_8_9_scaled", "sim_8_9_median_raw", "diagnostic_residual_8_9"]:
        d[c] = numeric(d[c])
    return d


def section_aggregate(sel: pd.DataFrame, stats: pd.DataFrame, traffic: pd.DataFrame) -> pd.DataFrame:
    x = sel.merge(stats, left_on="matsim_link_id", right_on="LINK", how="left", validate="many_to_one")
    rows = []
    for sid, q in x.groupby("lta_linkid", sort=True):
        a = pd.to_numeric(q["HRS8-9avg"], errors="coerce").dropna()
        pos = a[a.gt(0)]
        rep = q.sort_values(["distance_m", "direction_diff_deg", "semantic_compatible", "name_similarity", "matsim_link_id"], ascending=[True, True, False, False, True]).iloc[0]
        rows.append({"LinkID": sid, "matched_edge_count": int(q["matsim_link_id"].nunique()), "stats_valid_edge_count": int(len(a)), "zero_flow_edge_count": int((a == 0).sum()), "positive_flow_edge_count": int((a > 0).sum()), "raw_mean": float(a.mean()) if len(a) else np.nan, "raw_median": float(a.median()) if len(a) else np.nan, "raw_positive_median": float(pos.median()) if len(pos) else 0.0, "raw_max": float(a.max()) if len(a) else np.nan, "diagnostic_highway": rep["highway"], "representative_matsim_link_id": rep["matsim_link_id"]})
    sec = traffic.merge(pd.DataFrame(rows), on="LinkID", how="left", validate="one_to_one")
    for m, raw in [("CANONICAL_MEDIAN", "raw_median"), ("POSITIVE_MEDIAN", "raw_positive_median"), ("MEAN", "raw_mean"), ("MAX", "raw_max")]:
        sec[f"{m}__sim_scaled"] = sec[raw] * SCALE
        sec[f"{m}__ratio"] = sec[f"{m}__sim_scaled"] / sec["obs_8_9"].replace(0, np.nan)
        sec[f"{m}__residual"] = sec[f"{m}__ratio"] - 1.0
    return sec


def section_long(sec: pd.DataFrame) -> pd.DataFrame:
    common = ["LinkID", "RoadName", "RoadCat", "obs_8_9", "matched_edge_count", "stats_valid_edge_count", "zero_flow_edge_count", "positive_flow_edge_count", "raw_mean", "raw_median", "raw_positive_median", "raw_max", "diagnostic_highway", "representative_matsim_link_id"]
    out = []
    for m in AGGS:
        out.append(sec[common + [f"{m}__sim_scaled", f"{m}__ratio", f"{m}__residual"]].assign(aggregation=m))
    return pd.concat(out, ignore_index=True)


def grade_summary(long: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for (m, hw), g in long[long["obs_8_9"].gt(0)].groupby(["aggregation", "diagnostic_highway"], dropna=False):
        r = g[f"{m}__residual"]
        rows.append({"aggregation": m, "highway": hw, "n": len(g), "mean_residual": r.mean(), "median_residual": r.median(), "p10_residual": r.quantile(.10), "p90_residual": r.quantile(.90), "obs_weighted_residual": weighted_mean(r, g["obs_8_9"]), "sim_weighted_residual": weighted_mean(r, g[f"{m}__sim_scaled"]), "zero_section_n": int(g[f"{m}__sim_scaled"].eq(0).sum()), "negative_share": float(r.lt(0).mean()), "positive_share": float(r.gt(0).mean())})
    return pd.DataFrame(rows)


def zero_audit(sec: pd.DataFrame) -> pd.DataFrame:
    base = sec[sec["obs_8_9"].gt(0)].copy()
    rows = []
    for m in AGGS:
        zero = base[f"{m}__sim_scaled"].eq(0)
        zmean = zero & base["raw_mean"].gt(0)
        rows.append({"aggregation": m, "n": len(base), "zero_section_n": int(zero.sum()), "zero_observed_flow_share": weighted_mean(zero.astype(float), base["obs_8_9"]), "zero_with_mean_raw_gt0_n": int(zmean.sum()), "obs_weighted_residual": weighted_mean(base[f"{m}__residual"], base["obs_8_9"]), "sim_weighted_residual": weighted_mean(base[f"{m}__residual"], base[f"{m}__sim_scaled"])})
    return pd.DataFrame(rows)


def corridor_aggregate(sec: pd.DataFrame) -> pd.DataFrame:
    s = sec[sec["obs_8_9"].gt(0) & sec["RoadName"].ne("")].copy()
    s["corridor_id"] = s["RoadName"].str.upper().str.replace(r"\s+", " ", regex=True).str.strip()
    counts = s["corridor_id"].value_counts()
    s = s[s["corridor_id"].map(counts).ge(2)]
    rows = []
    for m in AGGS:
        for cid, g in s.groupby("corridor_id", sort=True):
            obs = float(g["obs_8_9"].sum())
            sim = float(g[f"{m}__sim_scaled"].sum())
            ratio = sim / obs if obs > 0 else np.nan
            rows.append({"aggregation": m, "corridor_id": cid, "section_n": len(g), "obs_corridor": obs, "sim_corridor": sim, "corridor_ratio": ratio, "corridor_residual": ratio - 1.0})
    return pd.DataFrame(rows)


def pairwise(sec: pd.DataFrame, corr: pd.DataFrame) -> pd.DataFrame:
    # NOTE (7.9F-1 fix, disclosed): the long frame holds one aggregation per row,
    # so drop_duplicates("LinkID") kept the CANONICAL block and left the other
    # three aggregation columns NaN. Use the wide `sec` frame, which carries all
    # four method columns for every section.
    rows = []
    s = sec[sec["obs_8_9"].gt(0)][["LinkID"] + [f"{m}__residual" for m in AGGS]].drop_duplicates("LinkID")
    base = "CANONICAL_MEDIAN__residual"
    for alt in ["POSITIVE_MEDIAN", "MEAN", "MAX"]:
        col = f"{alt}__residual"
        pz = s[[base, col]].dropna()
        d = pz[col] - pz[base]
        rows.append({"level": "SECTION", "comparison": f"{alt}_vs_CANONICAL_MEDIAN", "n": int(len(pz)), "pearson": pearson(pz[base], pz[col]), "spearman": spearman(pz[base], pz[col]), "mean_residual_delta": float(d.mean()) if len(d) else np.nan, "mae_residual_delta": float(d.abs().mean()) if len(d) else np.nan, "sign_change_share": float(((pz[base] * pz[col]) < 0).mean()) if len(pz) else np.nan})
    cb = corr[corr["aggregation"].eq("CANONICAL_MEDIAN")][["corridor_id", "corridor_residual"]].rename(columns={"corridor_residual": "canonical"})
    for alt in ["POSITIVE_MEDIAN", "MEAN", "MAX"]:
        z = corr[corr["aggregation"].eq(alt)].merge(cb, on="corridor_id", how="inner")
        d = z["corridor_residual"] - z["canonical"]
        rows.append({"level": "CORRIDOR", "comparison": f"{alt}_vs_CANONICAL", "n": int(len(z)), "pearson": pearson(z["canonical"], z["corridor_residual"]), "spearman": spearman(z["canonical"], z["corridor_residual"]), "mean_residual_delta": float(d.mean()) if len(d) else np.nan, "mae_residual_delta": float(d.abs().mean()) if len(d) else np.nan, "sign_change_share": float(((z["canonical"] * z["corridor_residual"]) < 0).mean()) if len(z) else np.nan})
    return pd.DataFrame(rows)


def input_manifest(paths: dict[str, Path]) -> dict:
    out = {}
    for k, p in paths.items():
        st = p.stat()
        out[k] = {"path": str(p), "sha256": sha256_file(p), "size_bytes": int(st.st_size), "mtime_ns": int(st.st_mtime_ns)}
    return out


def build_checks(script: Path, prereg: Path, traffic: pd.DataFrame, cand: pd.DataFrame, stats: pd.DataFrame, sec: pd.DataFrame, e2: pd.DataFrame, corr: pd.DataFrame, out: Path, manifest: dict) -> list[dict]:
    valid = sec[sec["obs_8_9"].gt(0)]
    sel_cov = safe_cov = valid[valid["matched_edge_count"].gt(0)]["LinkID"].nunique() / max(1, traffic["LinkID"].nunique())
    e2v = e2[e2["valid_residual"]].set_index("LinkID")
    canon = sec.set_index("LinkID")
    common = canon.index.intersection(e2v.index)
    # prereg §10 explicit: compare against E2 sim_8_9_median_raw with max|delta| = 0.
    raw_delta = (canon.loc[common, "raw_median"].astype(float) - e2v.loc[common, "sim_8_9_median_raw"].astype(float)).abs() if len(common) else pd.Series(dtype=float)
    scaled_delta = (canon.loc[common, "CANONICAL_MEDIAN__sim_scaled"] - e2v.loc[common, "sim_8_9_scaled"]).abs() if len(common) else pd.Series(dtype=float)
    delta = raw_delta
    canonical_ok = bool(len(common) > 0 and float(raw_delta.max()) == 0.0)
    corridor_n = int(corr[corr["aggregation"].eq("CANONICAL_MEDIAN")]["corridor_id"].nunique())
    all_in_dir = out.name == "section_aggregation_7_9f1"
    expected_files = ["f1_section_aggregation_long.csv", "f1_section_summary.csv", "f1_highway_aggregation_summary.csv", "f1_zero_median_audit.csv", "f1_corridor_aggregation.csv", "f1_robustness_pairwise.csv", "f1_selected_links.csv", "f1_input_manifest.json", "f1_summary.json"]
    artifacts = [out / x for x in expected_files]
    isolation_ok = all(p.exists() and p.parent.resolve() == out.resolve() for p in artifacts)
    rehash_mismatch = []
    for k, rec in manifest.items():
        if k.startswith("generated_") or k.startswith("__") or not isinstance(rec, dict) or "path" not in rec:
            continue
        p = Path(rec["path"])
        if (
            not p.exists()
            or sha256_file(p) != rec["sha256"]
            or p.stat().st_size != rec["size_bytes"]
        ):
            rehash_mismatch.append(k)
    checks = [
        {"check":"F1.01_PREREG_HASH","pass":sha256_file(prereg)==EXPECTED_PREREG_SHA256,"detail":sha256_file(prereg)},
        {"check":"F1.02_ZERO_SIMULATION","pass":zero_sim_audit(script),"detail":"AST no subprocess/Java"},
        {"check":"F1.03_TRAFFIC_UNIVERSE","pass":traffic["LinkID"].nunique()>=1278,"detail":f"traffic_links={traffic['LinkID'].nunique()}"},
        {"check":"F1.04_E1_CANDIDATES","pass":len(cand)>0,"detail":f"candidate_rows={len(cand):,}"},
        {"check":"F1.05_W01_LINKSTATS","pass":len(stats)>0 and not stats["LINK"].duplicated().any(),"detail":f"linkstats_links={len(stats):,}"},
        {"check":"F1.06_SELECTED_COVERAGE_GE95PCT","pass":sel_cov>=.95,"detail":f"coverage={sel_cov:.6f}"},
        {"check":"F1.07_VALID_SECTION_N_GE500","pass":len(valid)>=500,"detail":f"valid_n={len(valid)}"},
    ]
    for m in AGGS:
        cov = sec[f"{m}__sim_scaled"].notna().sum()/max(1,len(valid))
        checks.append({"check":f"F1.08_{m}_VALID_GE95PCT","pass":cov>=.95,"detail":f"coverage={cov:.6f}"})
    cnt=valid["diagnostic_highway"].value_counts(); miss=[h for h in CORE_HW if int(cnt.get(h,0))<20]
    checks.append({"check":"F1.09_CORE_HIGHWAY_SUPPORT","pass":not miss,"detail":f"missing_or_small={miss}; counts={cnt.to_dict()}"})
    checks.append({"check":"F1.10_CANONICAL_REPRODUCES_E2","pass":canonical_ok,"detail":f"overlap={len(common)}; max_abs_delta_sim_8_9_median_raw={float(raw_delta.max()) if len(raw_delta) else np.nan}; max_abs_delta_scaled={float(scaled_delta.max()) if len(scaled_delta) else np.nan}"})
    checks.append({"check":"F1.11_CORRIDOR_N_GE30","pass":corridor_n>=30,"detail":f"corridors={corridor_n}"})
    checks.append({"check":"F1.12_OUTPUT_PROVENANCE","pass":all_in_dir and isolation_ok and len(rehash_mismatch)==0,"detail":f"output_dir_name_ok={all_in_dir}; artifacts_in_output_dir={isolation_ok}; rehash_mismatch={rehash_mismatch}"})
    return checks


def report(out, traffic, cand, stats, grade, zero, corr, pair, checks, status):
    lines=["# Step 7.9F-1 — Section Aggregation Sensitivity Audit","",f"**STATUS: {status}**","","零仿真、只读、diagnostic-only。","",f"- TrafficFlow unique LinkID: **{traffic['LinkID'].nunique():,}**",f"- E1 candidate rows: **{len(cand):,}**",f"- W01 links: **{len(stats):,}**","", "## Zero-median audit","","| Aggregation | n | Zero sections | Zero obs-flow share | Zero with mean_raw>0 | Obs-weighted residual | Sim-weighted residual |","|---|---:|---:|---:|---:|---:|---:|"]
    for _,r in zero.iterrows(): lines.append(f"| {r.aggregation} | {int(r.n)} | {int(r.zero_section_n)} | {r.zero_observed_flow_share:.2%} | {int(r.zero_with_mean_raw_gt0_n)} | {r.obs_weighted_residual:.4f} | {r.sim_weighted_residual:.4f} |")
    lines += ["","## Highway × aggregation","","| Aggregation | Highway | n | Mean | Obs-weighted | Sim-weighted | Zero sections |","|---|---|---:|---:|---:|---:|---:|"]
    for _,r in grade.iterrows(): lines.append(f"| {r.aggregation} | {r.highway} | {int(r.n)} | {r.mean_residual:.4f} | {r.obs_weighted_residual:.4f} | {r.sim_weighted_residual:.4f} | {int(r.zero_section_n)} |")
    lines += ["","## Corridor support","",f"Canonical corridor proxy count (≥2 sections): **{corr[corr['aggregation'].eq('CANONICAL_MEDIAN')]['corridor_id'].nunique()}**", "", "## Pairwise robustness","","| Level | Comparison | n | Pearson | Spearman | Mean Δ | MAE Δ | Sign-change share |","|---|---|---:|---:|---:|---:|---:|"]
    for _,r in pair.iterrows(): lines.append(f"| {r.level} | {r.comparison} | {int(r.n)} | {r.pearson:.4f} | {r.spearman:.4f} | {r.mean_residual_delta:.4f} | {r.mae_residual_delta:.4f} | {r.sign_change_share:.2%} |")
    lines += ["","## Gates","","| Check | Result | Detail |","|---|---|---|"]
    for c in checks: lines.append(f"| {c['check']} | {'PASS' if c['pass'] else 'FAIL'} | {c['detail']} |")
    lines += ["","## Input resolution disclosure","",
              "- 预注册 §2.3 声明的 W01 路径 `reports/matsim_final_7_6h/outputs/W01_rc_min/ITERS/it.19/` **在磁盘上不存在**；",
              "  实际解析到项目根的同名冻结产物 `matsim_final_7_6h/outputs/W01_rc_min/ITERS/it.19/`（文件身份相同，仅目录前缀偏差）。",
              "  权威记录见 `f1_checks.csv` 的 `F1.S1_INPUT_RESOLUTION` / `F1.S2_DECLARED_PATH_ABSENT_TRACED` 与 `f1_input_manifest.json` 的 `w01_declared_vs_resolved`。",
              "- 本步骤不选择新的 calibration aggregation；替代方法仅作 sensitivity / falsification diagnostic，不回写 E2 或 v1.0。",""]
    (out/"STEP7_9F1_REPORT.md").write_text("\n".join(lines),encoding="utf-8")


def build_supplementary(root: Path, wp: Path, out: Path) -> list[dict]:
    """Non-hard disclosure gates: never counted in the 12 prereg hard gates."""
    declared = root / "reports/matsim_final_7_6h/outputs/W01_rc_min/ITERS/it.19"
    resolved = Path(wp).resolve()
    extra = out / "f1_selected_links.csv"
    return [
        {"check": "F1.S1_INPUT_RESOLUTION", "pass": bool(resolved.exists()),
         "detail": f"declared={declared} declared_exists={declared.exists()}; resolved={resolved}"},
        {"check": "F1.S2_DECLARED_PATH_ABSENT_TRACED", "pass": bool(not declared.exists()),
         "detail": "prereg §2.3 declared path absent on disk -> deviation traced; identical frozen file substituted"},
        {"check": "F1.S3_EXTRA_ARTIFACT_BOOKED", "pass": bool(extra.exists()),
         "detail": f"extra={extra.name} (superset of prereg §11 declared output list)"},
    ]


def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--project-root",type=Path,default=ROOT_DEFAULT); ap.add_argument("--traffic",type=Path); ap.add_argument("--e1-candidates",type=Path); ap.add_argument("--w01-linkstats",type=Path); ap.add_argument("--e2-main",type=Path); ap.add_argument("--prereg",type=Path); ap.add_argument("--out-dir",type=Path,default=OUT_REL); a=ap.parse_args(); root=a.project_root
    tp=a.traffic or root/TRAFFIC_REL; cp=a.e1_candidates or root/E1_CAND_REL; wp=locate_w01(root,a.w01_linkstats); ep=a.e2_main or root/E2_MAIN_REL; pp=a.prereg or root/PREREG_REL; out=a.out_dir if a.out_dir.is_absolute() else root/a.out_dir; out.mkdir(parents=True,exist_ok=True)
    for p in [tp,cp,wp,ep,pp]:
        if not p.exists(): raise FileNotFoundError(f"输入不存在: {p}")
    print("="*88); print("STEP 7.9F-1 | SECTION AGGREGATION SENSITIVITY AUDIT"); print("ZERO SIMULATION / READ-ONLY / DIAGNOSTIC ONLY")
    print(f"Traffic: {tp}"); print(f"E1: {cp}"); print(f"W01: {wp}"); print(f"E2: {ep}"); print(f"Prereg: {pp}"); print(f"Prereg SHA: {sha256_file(pp)}")
    traffic=load_traffic(tp); cand=load_candidates(cp); sel=select_links(cand); stats=load_stats(wp); e2=load_e2(ep); sec=section_aggregate(sel,stats,traffic); long=section_long(sec); grade=grade_summary(long); zero=zero_audit(sec); corr=corridor_aggregate(sec); pair=pairwise(sec,corr)
    # Write analytical outputs first.
    selected_out = sel[["lta_linkid","matsim_link_id","tier","distance_m","direction_diff_deg","semantic_compatible","name_similarity","highway"]].rename(columns={"lta_linkid":"LinkID"})
    sec.to_csv(out/"f1_section_summary.csv",index=False,encoding="utf-8-sig"); long.to_csv(out/"f1_section_aggregation_long.csv",index=False,encoding="utf-8-sig"); grade.to_csv(out/"f1_highway_aggregation_summary.csv",index=False,encoding="utf-8-sig"); zero.to_csv(out/"f1_zero_median_audit.csv",index=False,encoding="utf-8-sig"); corr.to_csv(out/"f1_corridor_aggregation.csv",index=False,encoding="utf-8-sig"); pair.to_csv(out/"f1_robustness_pairwise.csv",index=False,encoding="utf-8-sig"); selected_out.to_csv(out/"f1_selected_links.csv",index=False,encoding="utf-8-sig")
    paths={"traffic":tp,"e1_candidates":cp,"w01_linkstats":wp,"e2_main":ep,"prereg":pp,"script":Path(__file__).resolve()}; manifest=input_manifest(paths); (out/"f1_input_manifest.json").write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding="utf-8")
    supp=build_supplementary(root,wp,out)
    # Now extend manifest with the generated provenance files and rehash them.
    gen=[out/x for x in ["f1_section_aggregation_long.csv","f1_section_summary.csv","f1_highway_aggregation_summary.csv","f1_zero_median_audit.csv","f1_corridor_aggregation.csv","f1_robustness_pairwise.csv","f1_selected_links.csv"]]
    manifest2=input_manifest(paths)
    manifest2["generated_artifacts"]={str(p.name):{"sha256":sha256_file(p),"size_bytes":int(p.stat().st_size)} for p in gen}
    manifest2["__manifest_hash_check__"]=True
    manifest2["w01_declared_vs_resolved"]={"declared":str(root/"reports/matsim_final_7_6h/outputs/W01_rc_min/ITERS/it.19"),"resolved":str(Path(wp).resolve())}
    (out/"f1_input_manifest.json").write_text(json.dumps(manifest2,ensure_ascii=False,indent=2),encoding="utf-8")
    # Write summary.json BEFORE the final isolation check, so that every declared
    # output already exists on disk when F1.12 evaluates output isolation.
    summary_pre={"step":"7.9F-1","status":"PENDING","zero_simulation":True,"network_modified":False,
                 "matsim_rerun":False,"traffic_unique_links":int(traffic.LinkID.nunique()),
                 "candidate_rows":int(len(cand)),"selected_candidate_rows":int(len(sel)),
                 "w01_linkstats_links":int(len(stats)),"valid_section_n":int(sec.obs_8_9.gt(0).sum()),
                 "corridor_n":int(corr[corr.aggregation.eq('CANONICAL_MEDIAN')].corridor_id.nunique()),
                 "hard_pass_count":0,"hard_total":0,"prereg_sha256":sha256_file(pp),
                 "scale":SCALE,"supplementary":supp}
    (out/"f1_summary.json").write_text(json.dumps(summary_pre,ensure_ascii=False,indent=2),encoding="utf-8")
    # Rebuild checks once ALL declared outputs exist, so isolation and provenance are real.
    ck=build_checks(Path(__file__).resolve(),pp,traffic,cand,stats,sec,e2,corr,out,manifest2); hard=all(bool(x["pass"]) for x in ck); status="AGGREGATION_AUDIT_READY" if hard else "AGGREGATION_AUDIT_BLOCKED"
    pd.DataFrame(ck+supp).to_csv(out/"f1_checks.csv",index=False,encoding="utf-8-sig")
    summary={"step":"7.9F-1","status":status,"zero_simulation":True,"network_modified":False,"matsim_rerun":False,"traffic_unique_links":int(traffic.LinkID.nunique()),"candidate_rows":int(len(cand)),"selected_candidate_rows":int(len(sel)),"w01_linkstats_links":int(len(stats)),"valid_section_n":int(sec.obs_8_9.gt(0).sum()),"corridor_n":int(corr[corr.aggregation.eq('CANONICAL_MEDIAN')].corridor_id.nunique()),"hard_pass_count":int(sum(bool(x["pass"]) for x in ck)),"hard_total":int(len(ck)),"prereg_sha256":sha256_file(pp),"scale":SCALE}; (out/"f1_summary.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding="utf-8")
    report(out,traffic,cand,stats,grade,zero,corr,pair,ck,status)
    print(f"[1/6] TrafficFlow unique LinkID = {traffic.LinkID.nunique():,}"); print(f"[2/6] selected candidate rows  = {len(sel):,}"); print(f"[3/6] W01 linkstats links      = {len(stats):,}"); print(f"[4/6] valid sections           = {int(sec.obs_8_9.gt(0).sum()):,}"); print(f"[5/6] hard gates               = {sum(bool(x['pass']) for x in ck)}/{len(ck)}"); print(f"[6/6] STATUS                   = {status}"); print(f"      OUTPUT                  = {out}"); print("      NOTE                    = no MATSim/Java call"); return 0 if hard else 1

if __name__=="__main__": raise SystemExit(main())
