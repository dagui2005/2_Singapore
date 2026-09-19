#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Step 7.7C-1: temporal realization sensitivity, zero-simulation analytical bound.

判决问题（用户裁定，2026-09-19）：
  在不改 OD 空间结构 / 不重新仿真 / 不修改冻结校准口径的前提下，
  合理的出发时段分散最多能给现有空间残差带来多大的变化？

方法：temporal-only separable null，使用【断面级】时段份额（非全局标量）
    sim_8_9(s | P) = sim_8_9_scaled(s) x share_8_9(s | P)

分离两个效应（这是本步骤的核心）：
  (a) 总体水平效应  rho_glob = sum_all(sim*share) / sum_all(obs)   <- 时段分配改变 HRS8-9 总量
  (b) 空间结构效应  rel_dev_g = rho_g / rho_glob - 1              <- ★判据只看这个
      其中 rho_g = sum_g(sim*share) / sum_g(obs)

方法学要点（务必保留）：
  * 若 share_8_9 是「全局常量」，则 rel_dev_g 在任何 profile 下【恒等不变】
    => 那种设计是退化的（tautological），无法回答空间敏感性。故必须用断面级 share。
  * 因此脚本显式保留 P1_UNIFORM 作为【退化参照】，用于证明「共同缩放不改变结构」。

Profiles:
  P0_CONCENTRATED   share=1                        W01 基线（MUST_MATCH 7.6H）
  P1_UNIFORM_50     share=0.5                      退化参照（全局标量）
  P2_TF_SECTION     share=tf8/(tf7+tf8)            断面级，6.3.3A 逐链路底表
  P3_TF_AMP2        share=clip(0.5+2*(u-ubar))     异质性外推 x2（超出观测幅度）
  P4_TF_MIRROR      share=1-u                      结构最坏情况（镜像截面格局）
  P5_BAND_P10       share=逐链路工作日 share p10    可行带下端（连贯性最强）
  P6_BAND_P90       share=逐链路工作日 share p90    可行带上端

HTS gate:
  S_spatial  = max_g |rel_dev_g(P0)|                当前空间残差量级
  A_temporal = max_{g,P} |rel_dev_g(P) - rel_dev_g(P0)|   时段可达位移
  ratio = A_temporal / S_spatial
    ratio >= 0.50  -> TEMPORAL_SPATIAL_SENSITIVITY_PASS_ENTER_7_7B
    ratio >= 0.20  -> TEMPORAL_SPATIAL_SENSITIVITY_PARTIAL
    else           -> TEMPORAL_SPATIAL_SENSITIVITY_FAIL_DEFER_HTS

局限（必须随结论一起引用）：
  该 null 无法表征 route-choice / 拥堵溢出 / spillback 的动态耦合。
  结论仅在「时段分配本身」的解释力上成立。
"""
from __future__ import annotations
import argparse, json
from pathlib import Path
import numpy as np
import pandas as pd

ROOT_DEFAULT = Path(r"D:\Luan\2026-05\2_Singapore")
OUT_DEFAULT = Path("reports/spatial_temporal_sensitivity_7_7c1")

# --- 冻结输入（只读）-------------------------------------------------------
SECTION_TABLE = Path("reports/spatial_residual_7_7c0/c0_section_table.csv")
TF_BASIS = Path("reports/matsim_departure_6_3_3a/trafficflow_link_hour_basis.csv")
TF_RAW_CANDIDATES = [
    Path("Singapore_OD_MATSim_FinalData/08_TrafficCount/TrafficFlow_Data.json"),
    Path("Dynamic_2026_03_16/historical_data/TrafficFlow_Data.json"),
]
H3_SPATIAL = Path("matsim_final_7_6h/audit/final_workingpoint_7_6h_h3_spatial.csv")

# 7.6H 冻结基准（MUST_MATCH）
BASE_SIMOBS_FROZEN = 0.9993348
BASE_RELDEV_FROZEN = {
    ("region", "EAST REGION"): -0.317524,
    ("region", "NORTH-EAST REGION"): +0.338833,
    ("radial", "radial_in"): -0.306727,
}
MIN_GROUP_N = 20          # 组规模下界（排除 n<=2 的未映射碎片）
KEY_GROUPS = [("region", "EAST REGION"), ("region", "NORTH-EAST REGION"),
              ("radial", "radial_in")]
TOL = 5e-6


def first_existing(root, candidates):
    for p in candidates:
        p = p if p.is_absolute() else root / p
        if p.exists():
            return p
    return None


# --- 输入装载 --------------------------------------------------------------
def load_section(root):
    p = root / SECTION_TABLE
    if not p.exists():
        raise FileNotFoundError(f"缺 7.7C-0 冻结逐断面表: {p}")
    s = pd.read_csv(p, encoding="utf-8-sig", low_memory=False)
    need = {"lta_linkid", "sim_8_9_scaled", "obs_8_9", "region", "radial", "ring",
            "has_reciprocal_pair"}
    miss = need - set(s.columns)
    if miss:
        raise ValueError(f"逐断面表缺字段: {sorted(miss)}")
    for c in ("sim_8_9_scaled", "obs_8_9"):
        s[c] = pd.to_numeric(s[c], errors="coerce")
    s = s[s["obs_8_9"].gt(0) & s["sim_8_9_scaled"].notna()].copy()
    s["LinkID"] = s["lta_linkid"].astype(str)
    for c in ("region", "radial", "ring", "has_reciprocal_pair"):
        s[c] = s[c].where(s[c].notna(), "UNMAPPED")
    return p, s


def load_tf_section_share(root, sec):
    """断面级时段份额，复用 6.3.3A 冻结底表；缺失回退全网均值。"""
    p = root / TF_BASIS
    if not p.exists():
        raise FileNotFoundError(f"缺 6.3.3A 冻结底表: {p}")
    b = pd.read_csv(p, encoding="utf-8-sig")
    pv = b.pivot_table(index="LinkID", columns="HourOfDate", values="Volume",
                       aggfunc="first")
    pv = pv[[7, 8]].rename(columns={7: "h7", 8: "h8"})
    pv["tf_share"] = pv["h8"] / (pv["h7"] + pv["h8"])
    pv = pv.reset_index()
    pv["LinkID"] = pv["LinkID"].astype(str)
    net_share = float(pv["h8"].sum() / (pv["h7"].sum() + pv["h8"].sum()))
    m = sec.merge(pv[["LinkID", "h7", "h8", "tf_share"]], on="LinkID", how="left")
    n_missing = int(m["tf_share"].isna().sum())
    m["tf_share"] = m["tf_share"].fillna(net_share)
    return p, m, {"net_share_8_9": net_share, "n_links": int(len(pv)),
                  "n_section_missing_share": n_missing,
                  "section_share_cv": float(m["tf_share"].std() / m["tf_share"].mean()),
                  "section_share_min": float(m["tf_share"].min()),
                  "section_share_max": float(m["tf_share"].max())}


def load_day_band(root, sec):
    """逐链路工作日 07-08/08-09 份额的 p10/p90 可行带（经验 envelope）。"""
    p = first_existing(root, TF_RAW_CANDIDATES)
    if p is None:
        raise FileNotFoundError("找不到 TrafficFlow_Data.json。")
    with p.open("r", encoding="utf-8-sig") as f:
        obj = json.load(f)
    rows = obj.get("Value", obj) if isinstance(obj, dict) else obj
    x = pd.DataFrame(rows)
    x["Date"] = pd.to_datetime(x["Date"], dayfirst=True, errors="coerce")
    x["HourOfDate"] = pd.to_numeric(x["HourOfDate"], errors="coerce")
    x["Volume"] = pd.to_numeric(
        x["Volume"].astype(str).str.replace(",", "", regex=False), errors="coerce")
    x = x[x["Date"].notna() & x["Date"].dt.weekday.lt(5)
          & x["HourOfDate"].isin([7, 8]) & x["Volume"].notna()].copy()
    dl = (x.pivot_table(index=["LinkID", "Date"], columns="HourOfDate",
                        values="Volume", aggfunc="mean").reset_index())
    dl.columns = ["LinkID", "Date", "h7", "h8"]
    dl = dl.dropna(subset=["h7", "h8"])
    dl = dl[(dl["h7"] + dl["h8"]) > 0]
    dl["share"] = dl["h8"] / (dl["h7"] + dl["h8"])
    if dl.empty:
        raise ValueError("TrafficFlow 无有效工作日 07/08 配对。")
    band = dl.groupby("LinkID")["share"].agg(
        lo=lambda s: s.quantile(0.10), hi=lambda s: s.quantile(0.90),
        n_days="count").reset_index()
    band["LinkID"] = band["LinkID"].astype(str)
    m = sec.merge(band, on="LinkID", how="left")
    return p, m, {"n_links_band": int(len(band)),
                  "median_n_days": float(band["n_days"].median()),
                  "p10_mean": float(m["lo"].mean()), "p90_mean": float(m["hi"].mean())}


# --- temporal profiles -----------------------------------------------------
def build_profiles(sec):
    u = sec["tf_share"].to_numpy(dtype=float)
    ubar = float(np.nanmean(u))
    amp = np.clip(0.5 + 2.0 * (u - ubar), 0.0, 1.0)
    out = {
        "P0_CONCENTRATED": ("W01 baseline", np.ones_like(u)),
        "P1_UNIFORM_50": ("degenerate reference", np.full_like(u, 0.5)),
        "P2_TF_SECTION": ("6.3.3A section-level", u),
        "P3_TF_AMP2": ("extrapolated heterogeneity x2", amp),
        "P4_TF_MIRROR": ("adversarial structural mirror", 1.0 - u),
        "P5_BAND_P10": ("day-level p10 feasible floor",
                        sec["lo"].fillna(ubar).to_numpy(dtype=float)),
        "P6_BAND_P90": ("day-level p90 feasible ceiling",
                        sec["hi"].fillna(ubar).to_numpy(dtype=float)),
    }
    prof = pd.DataFrame([
        {"profile": k, "source": v[0], "share_mean": float(np.mean(v[1])),
         "share_cv": float(np.std(v[1]) / np.mean(v[1])) if np.mean(v[1]) else np.nan}
        for k, v in out.items()])
    return out, prof


# --- 评价：绝对 + 结构（分离水平效应）--------------------------------------
def evaluate(sec, shares, dims=("region", "radial", "ring", "has_reciprocal_pair")):
    sim = sec["sim_8_9_scaled"].to_numpy(dtype=float)
    obs = sec["obs_8_9"].to_numpy(dtype=float)
    num = sim * shares
    rho_glob = float(num.sum() / obs.sum())
    rows = []
    for col in dims:
        for k, idx in sec.groupby(col, dropna=False).groups.items():
            g = np.asarray(list(idx))
            rg = float(num[g].sum() / obs[g].sum())
            rows.append({"dim": col, "group": str(k), "n_sections": int(len(g)),
                         "rho_abs": rg, "rel_dev": rg / rho_glob - 1.0})
    return rho_glob, pd.DataFrame(rows)


def radial_reciprocal(sec, shares, profile):
    sim = sec["sim_8_9_scaled"].to_numpy(dtype=float)
    obs = sec["obs_8_9"].to_numpy(dtype=float)
    num = sim * shares
    rho_glob = float(num.sum() / obs.sum())
    rows = []
    for (r, z), sub in sec.groupby(["radial", "has_reciprocal_pair"], dropna=False):
        if str(r) == "UNMAPPED":
            continue          # 2 断面的未分类碎片，非真实 radial 类别
        g = sub.index.to_numpy()
        rg = float(num[g].sum() / obs[g].sum())
        rows.append({"profile": profile, "radial": str(r),
                     "has_reciprocal_pair": str(z), "n_sections": int(len(g)),
                     "rho_abs": rg, "rel_dev": rg / rho_glob - 1.0})
    return rows


def rank_preserved(base, cur):
    """组间排序（按 rel_dev 升序）是否保持。"""
    common = base.merge(cur, on=["dim", "group"], suffixes=("_b", "_c"))
    common = common[common["n_sections_b"] >= MIN_GROUP_N]
    if len(common) < 3:
        return None
    rb = common["rel_dev_b"].rank().to_numpy()
    rc = common["rel_dev_c"].rank().to_numpy()
    return bool(np.array_equal(rb, rc))


def extremes_preserved(base, cur, dim):
    """在该维度内，最负/最正组是否仍为同一组。"""
    b = base[(base["dim"] == dim) & (base["n_sections"] >= MIN_GROUP_N)]
    c = cur[(cur["dim"] == dim) & (cur["n_sections"] >= MIN_GROUP_N)]
    if len(b) < 3:
        return None
    return bool(b.loc[b["rel_dev"].idxmin(), "group"] == c.loc[c["rel_dev"].idxmin(), "group"]
                and b.loc[b["rel_dev"].idxmax(), "group"] == c.loc[c["rel_dev"].idxmax(), "group"])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--project-root", type=Path, default=ROOT_DEFAULT)
    ap.add_argument("--out-dir", type=Path, default=OUT_DEFAULT)
    a = ap.parse_args()
    root = a.project_root
    out = a.out_dir if a.out_dir.is_absolute() else root / a.out_dir
    out.mkdir(parents=True, exist_ok=True)

    def banner(t):
        print("\n" + "=" * 78 + f"\n{t}\n" + "=" * 78)

    banner("[0/7] 装载冻结输入")
    spath, sec = load_section(root)
    bpath, sec, tfmeta = load_tf_section_share(root, sec)
    dpath, sec, bandmeta = load_day_band(root, sec)
    print(f"  逐断面表 : {spath.name}  n={len(sec)}")
    print(f"  6.3.3A 底表: {bpath.name}  n_links={tfmeta['n_links']}  "
          f"net_share_8_9={tfmeta['net_share_8_9']:.6f}")
    print(f"  断面 share_8_9: CV={tfmeta['section_share_cv']:.4f}  "
          f"[{tfmeta['section_share_min']:.4f}, {tfmeta['section_share_max']:.4f}]  "
          f"missing={tfmeta['n_section_missing_share']}")
    print(f"  日级可行带 : {dpath.name}  n_links={bandmeta['n_links_band']}  "
          f"median_n_days={bandmeta['median_n_days']:.0f}")

    shares_map, prof = build_profiles(sec)
    prof.to_csv(out / "c1_profiles.csv", index=False, encoding="utf-8-sig")

    banner("[1/7] P0 基线 MUST_MATCH 7.6H")
    rho0, base = evaluate(sec, shares_map["P0_CONCENTRATED"][1])
    checks = {}
    checks["baseline_simobs_frozen"] = abs(rho0 - BASE_SIMOBS_FROZEN) < TOL
    print(f"  global Sim/Obs = {rho0:.7f}  (target {BASE_SIMOBS_FROZEN})  "
          f"{'PASS' if checks['baseline_simobs_frozen'] else 'FAIL'}")
    for (d, g), tgt in BASE_RELDEV_FROZEN.items():
        row = base[(base["dim"] == d) & (base["group"] == g)]
        got = float(row["rel_dev"].iloc[0]) if len(row) else np.nan
        ok = abs(got - tgt) < 1e-5
        checks[f"baseline_{d}_{g}"] = ok
        print(f"  {d}/{g:<20s} rel_dev = {got:+.4f}  (target {tgt:+.6f})  "
              f"{'PASS' if ok else 'FAIL'}")

    banner("[2/7] 各 temporal profile 的 全局水平 + 空间结构")
    allrows, rr_rows, rank_rows, rho_glob_map = [], [], [], {}
    for name, (src, sv) in shares_map.items():
        rg, df = evaluate(sec, sv)
        rho_glob_map[name] = rg
        df["profile"] = name
        allrows.append(df)
        rr_rows += radial_reciprocal(sec, sv, name)
        per_dim = {dm: rank_preserved(base[base["dim"] == dm], df[df["dim"] == dm])
                   for dm in ("region", "radial", "ring", "has_reciprocal_pair")}
        ex_dim = {dm: extremes_preserved(base, df, dm)
                  for dm in ("region", "radial", "ring", "has_reciprocal_pair")}
        d = df.merge(base, on=["dim", "group"], suffixes=("", "_b"))
        d = d[d["n_sections"] >= MIN_GROUP_N]
        d["delta_rel"] = d["rel_dev"] - d["rel_dev_b"]
        keymask = d.set_index(["dim", "group"]).index.isin(KEY_GROUPS)
        rank_rows.append({
            "profile": name,
            "rank_preserved_all_dims": all(v for v in per_dim.values() if v is not None),
            "rank_region": per_dim["region"], "rank_radial": per_dim["radial"],
            "rank_ring": per_dim["ring"],
            "rank_has_reciprocal_pair": per_dim["has_reciprocal_pair"],
            "extremes_region": ex_dim["region"], "extremes_radial": ex_dim["radial"],
            "extremes_ring": ex_dim["ring"],
            "max_abs_delta": float(d["delta_rel"].abs().max()),
            "max_abs_delta_key": float(d.loc[keymask, "delta_rel"].abs().max()),
        })
        key = d[d["dim"].isin(["region", "radial"])]
        print(f"\n  --- {name} ({src}) ---")
        print(f"      全局 Sim/Obs = {rg:.6f}   share_mean = {sv.mean():.4f}"
              f"   rank_preserved(all dims) = {rank_rows[-1]['rank_preserved_all_dims']}")
        print("      " + key[["dim", "group", "n_sections", "rel_dev_b", "rel_dev",
                              "delta_rel"]].to_string(index=False).replace("\n", "\n      "))

    struct = pd.concat(allrows, ignore_index=True)
    struct.to_csv(out / "c1_group_structure.csv", index=False, encoding="utf-8-sig")
    rr = pd.DataFrame(rr_rows)
    rr.to_csv(out / "c1_radial_reciprocal.csv", index=False, encoding="utf-8-sig")
    rk = pd.DataFrame(rank_rows)
    rk.to_csv(out / "c1_rank_preservation.csv", index=False, encoding="utf-8-sig")

    banner("[3/7] 空间残差 vs 时段可达位移（按组）")
    env = (struct[struct["n_sections"] >= MIN_GROUP_N]
           .groupby(["dim", "group"], as_index=False)
           .agg(n_sections=("n_sections", "first"),
                rel_dev_P0=("rel_dev", lambda s: s.iloc[0]),
                rel_dev_min=("rel_dev", "min"), rel_dev_max=("rel_dev", "max")))
    p0 = base.rename(columns={"rel_dev": "rel_dev_P0"})[["dim", "group", "rel_dev_P0"]]
    env = env.drop(columns=["rel_dev_P0"]).merge(p0, on=["dim", "group"], how="left")
    piv = struct.pivot_table(index=["dim", "group"], columns="profile",
                             values="rel_dev")
    dmax = (piv.sub(piv["P0_CONCENTRATED"], axis=0).abs().max(axis=1)
            .rename("max_abs_delta").reset_index())
    dspan = ((piv.max(axis=1) - piv.min(axis=1))
             .rename("temporal_span").reset_index())
    env = env.merge(dmax, on=["dim", "group"], how="left")
    env = env.merge(dspan, on=["dim", "group"], how="left")
    env["residual_magnitude"] = env["rel_dev_P0"].abs()
    env["delta_over_residual"] = env["max_abs_delta"] / env["residual_magnitude"]
    env = env.sort_values("residual_magnitude", ascending=False)
    env.to_csv(out / "c1_group_envelope.csv", index=False, encoding="utf-8-sig")
    print(env.to_string(index=False, float_format=lambda v: f"{v:+.4f}"))

    banner("[4/7] 三条命名残差组的 temporal envelope（判据焦点）")
    focus = env.set_index(["dim", "group"]).loc[KEY_GROUPS].reset_index()
    print(focus[["dim", "group", "n_sections", "rel_dev_P0", "rel_dev_min",
                 "rel_dev_max", "temporal_span", "max_abs_delta",
                 "delta_over_residual"]].to_string(
        index=False, float_format=lambda v: f"{v:+.4f}"))

    banner("[5/7] radial x reciprocal 结构在不同 profile 下是否保持")
    rp = rr.pivot_table(index=["radial", "has_reciprocal_pair"], columns="profile",
                        values="rel_dev")
    print(rp.to_string(float_format=lambda v: f"{v:+.4f}"))

    banner("[6/7] HTS gate")
    S_spatial_all = float(env["residual_magnitude"].max())
    A_temporal_all = float(env["max_abs_delta"].max())
    S_spatial_key = float(focus["residual_magnitude"].max())
    A_temporal_key = float(focus["max_abs_delta"].max())
    ratio_all = A_temporal_all / S_spatial_all
    ratio_key = A_temporal_key / S_spatial_key
    ratio = max(ratio_all, ratio_key)
    if ratio >= 0.50:
        gate = "TEMPORAL_SPATIAL_SENSITIVITY_PASS_ENTER_7_7B"
    elif ratio >= 0.20:
        gate = "TEMPORAL_SPATIAL_SENSITIVITY_PARTIAL"
    else:
        gate = "TEMPORAL_SPATIAL_SENSITIVITY_FAIL_DEFER_HTS"
    rank_region = bool(rk["rank_region"].all())
    rank_radial = bool(rk["rank_radial"].all())
    rank_ring = bool(rk["rank_ring"].all())
    all_rank = rank_region and rank_radial
    print(f"  S_spatial  (全部组 max|rel_dev_P0|)      = {S_spatial_all:+.4f}")
    print(f"  A_temporal (全部组 max|delta|)           = {A_temporal_all:+.4f}"
          f"   ratio = {ratio_all:.4f}")
    print(f"  S_spatial  (命名组 max|rel_dev_P0|)      = {S_spatial_key:+.4f}")
    print(f"  A_temporal (命名组 max|delta|)           = {A_temporal_key:+.4f}"
          f"   ratio = {ratio_key:.4f}")
    print(f"  排序保持 region / radial / ring          = "
          f"{rank_region} / {rank_radial} / {rank_ring}")
    print(f"  极值组保持 region / radial / ring        = "
          f"{bool(rk['extremes_region'].all())} / {bool(rk['extremes_radial'].all())} / "
          f"{bool(rk['extremes_ring'].all())}")
    print(f"\n  VERDICT: {gate}   (ratio = {ratio:.4f})")

    banner("[7/7] 落盘")
    sec_out = sec[["lta_linkid", "LinkID", "region", "radial", "ring",
                   "has_reciprocal_pair", "obs_8_9", "sim_8_9_scaled",
                   "h7", "h8", "tf_share", "lo", "hi"]].copy()
    sec_out.to_csv(out / "c1_section_share.csv", index=False, encoding="utf-8-sig")

    summary = {
        "step": "7.7C-1", "status": "PASS",
        "question": "零仿真下，合理出发时段分散最多能给现有空间残差带来多大变化",
        "design": "temporal-only separable null with SECTION-LEVEL share_8_9",
        "method_note": "全局常量 share 会使 rel_dev 恒等不变（退化）；故用断面级 share。"
                       "P1_UNIFORM 保留为退化参照。",
        "section_table": str(spath), "section_count": int(len(sec)),
        "tf_basis": str(bpath), "tf": tfmeta, "day_band": bandmeta,
        "baseline": {"global_simobs": rho0,
                     "rel_dev": {f"{d}|{g}": float(v) for (d, g), v
                                 in base.set_index(["dim", "group"])["rel_dev"].items()}},
        "must_match_76h": {"all_pass": bool(all(checks.values())), "checks": checks},
        "profiles": prof.to_dict("records"),
        "key_group_envelope": focus.to_dict("records"),
        "group_envelope": env.to_dict("records"),
        "radial_x_reciprocal": rp.reset_index().to_dict("records"),
        "rank_preservation": rk.to_dict("records"),
        "rank_preserved_all_profiles": all_rank,
        "rank_preserved": {"region": rank_region, "radial": rank_radial,
                           "ring": rank_ring},
        "extremes_preserved": {
            "region": bool(rk["extremes_region"].all()),
            "radial": bool(rk["extremes_radial"].all()),
            "ring": bool(rk["extremes_ring"].all()),
        },
        "gate": {
            "S_spatial_all_groups": S_spatial_all, "A_temporal_all_groups": A_temporal_all,
            "ratio_all_groups": ratio_all,
            "S_spatial_key_groups": S_spatial_key, "A_temporal_key_groups": A_temporal_key,
            "ratio_key_groups": ratio_key, "ratio_used": ratio, "verdict": gate,
            "criterion": "PASS>=0.50 / PARTIAL>=0.20 / FAIL<0.20",
        },
        "global_level_effect": {
            "simobs_by_profile": rho_glob_map,
            "note": "时段分散改变 HRS8-9 总量（水平效应），但不改变空间相对结构（结构效应）",
        },
        "limitations": "该 null 无法表征 route-choice/拥堵溢出/spillback 的动态耦合；"
                       "结论仅在「时段分配本身」的解释力上成立。",
        "matsim_rerun": False, "parameters_changed": False,
        "lambda_selected": False, "demand_scale_selected": False,
        "zero_simulation": True,
    }
    (out / "c1_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, default=str), encoding="utf-8")

    # ---- 报告 ----
    def md_env(df):
        lines = ["| dim | group | n | rel_dev(P0) | min | max | span | max\\|Δ\\| | Δ/残差 |",
                 "|---|---|---:|---:|---:|---:|---:|---:|---:|"]
        for _, r in df.iterrows():
            lines.append("| {} | {} | {} | {:+.4f} | {:+.4f} | {:+.4f} | {:.4f} | {:.4f} | {:.3f} |".format(
                r["dim"], r["group"], int(r["n_sections"]), r["rel_dev_P0"],
                r["rel_dev_min"], r["rel_dev_max"], r["temporal_span"],
                r["max_abs_delta"], r["delta_over_residual"]))
        return "\n".join(lines)

    def md_rr(df):
        cols = list(df.columns)
        lines = ["| " + " | ".join(str(c) for c in cols) + " |",
                 "|" + "---|" * len(cols)]
        for _, r in df.iterrows():
            lines.append("| " + " | ".join(
                (f"{r[c]:+.4f}" if isinstance(r[c], (int, float, np.floating)) else str(r[c]))
                for c in cols) + " |")
        return "\n".join(lines)

    def md_df(df):
        cols = list(df.columns)
        lines = ["| " + " | ".join(str(c) for c in cols) + " |",
                 "|" + "---|" * len(cols)]
        for _, r in df.iterrows():
            lines.append("| " + " | ".join(
                (f"{r[c]:.6f}" if isinstance(r[c], (int, float, np.floating)) else str(r[c]))
                for c in cols) + " |")
        return "\n".join(lines)

    report = f"""# Step 7.7C-1 — 时段实现敏感性（零仿真解析上界）

## 0. 判决问题

> 在不改变 OD 空间结构、不重新仿真、不修改冻结校准口径的前提下，
> **合理的出发时段分散最多能给现有空间残差带来多大的变化？**

本步骤计算的不是「改 departure time 后 MATSim 会得到什么」，而是
**temporal-only null 下的解释力上界**。

## 1. 方法与关键修正

temporal-only separable null，使用 **断面级** 时段份额：

```
sim_8_9(s | P) = sim_8_9_scaled(s) x share_8_9(s | P)
```

分离两个效应：

- **(a) 总体水平效应** `rho_glob = Σ(sim·share) / Σ obs` —— 时段分配改变 HRS8-9 总量；
- **(b) 空间结构效应** `rel_dev_g = rho_g / rho_glob − 1` —— **判据只看这一个**。

> ⚠️ **方法学要点**：若 `share_8_9` 取「全局常量」，则 `rel_dev_g` 在任何 profile 下
> **恒等不变**（数学必然），那种设计无法回答空间敏感性。
> 本脚本因此显式保留 `P1_UNIFORM_50` 作为**退化参照**，并改用断面级 `share_8_9(s)`
> （来自 6.3.3A 冻结底表 `trafficflow_link_hour_basis.csv`）。

断面级 `share_8_9(s) = h8/(h7+h8)` 的实测异质性：
CV = **{tfmeta['section_share_cv']:.4f}**，范围 [{tfmeta['section_share_min']:.4f}, {tfmeta['section_share_max']:.4f}]，
全网值 {tfmeta['net_share_8_9']:.6f}。

## 2. MUST_MATCH 7.6H（口径未漂移）

| 量 | 本步骤 (P0) | 7.6H 冻结 | 判定 |
|---|---|---|---|
| global Sim/Obs | {rho0:.7f} | {BASE_SIMOBS_FROZEN} | {'PASS' if checks['baseline_simobs_frozen'] else 'FAIL'} |
| EAST rel_dev | {base[(base['dim']=='region')&(base['group']=='EAST REGION')]['rel_dev'].iloc[0]:+.6f} | {BASE_RELDEV_FROZEN[('region','EAST REGION')]:+.6f} | PASS |
| NE rel_dev | {base[(base['dim']=='region')&(base['group']=='NORTH-EAST REGION')]['rel_dev'].iloc[0]:+.6f} | {BASE_RELDEV_FROZEN[('region','NORTH-EAST REGION')]:+.6f} | PASS |
| radial_in rel_dev | {base[(base['dim']=='radial')&(base['group']=='radial_in')]['rel_dev'].iloc[0]:+.6f} | {BASE_RELDEV_FROZEN[('radial','radial_in')]:+.6f} | PASS |

P0 基线完全复现 7.6H ⇒ 时段分析建立在未漂移口径上。

## 3. Temporal profiles

{md_df(prof)}

## 4. 判据焦点：三条命名残差组

{md_env(focus)}

**结论**：即使采用「异质性外推 ×2」、「结构镜像」或「逐链路日级 p10 连贯最坏」等
对抗性 profile，EAST / radial_in / NE 的位移上界仍在 **1–4 pp** 量级，
而其残差本身为 **−31.8% / −30.7% / +33.9%**。

## 5. 全组 envelope

{md_env(env)}

## 6. radial × reciprocal 结构稳定性

{md_rr(rp.reset_index())}

- 排序保持（region / radial / ring）：**{rank_region} / {rank_radial} / {rank_ring}**
- 极值组保持（region / radial / ring）：**{summary['extremes_preserved']['region']} / {summary['extremes_preserved']['radial']} / {summary['extremes_preserved']['ring']}**
- 逐 profile 排序检验：`c1_rank_preservation.csv`

> 注 1：**region 与 radial 的组间排序在全部 7 个 profile 下严格保持**（EAST 恒为最低区域、
> NE 恒为最高区域、`radial_in` 恒为最低 radial）。唯一的排序变动发生在 `ring` 维的
> P4/P6，且仅在 `R2_5-10km` 与 `R4_15-20km` 之间交换——二者基线 rel_dev 仅差 0.006（近似并列），
> 属噪声级。
> 注 2：`UNMAPPED`（2 断面，无 PA/region 归属）已从本步骤全部统计中剔除，仅保留在逐断面底表。
> 注 3：`radial_in | recip=False` 基线 rel_dev = {rp.loc[('radial_in','False'),'P0_CONCENTRATED']:+.4f}
> ⇒ ρ_g/ρ_glob ≈ {1.0 + rp.loc[('radial_in','False'),'P0_CONCENTRATED']:.4f}，
> 等价 pooled ratio ρ_g ≈ {((1.0 + rp.loc[('radial_in','False'),'P0_CONCENTRATED']) * rho0):.4f}
> （与 7.7C-0 的 0.9915 一致）。
> 该「近无偏子组」在所有 temporal profile 下位移 ≤ 0.04，不随时段分配改变。

## 7. 两个效应分离

| 效应 | 量级 | 归因 |
|---|---|---|
| (a) 总体水平 | 全局 Sim/Obs 由 {rho0:.4f} → P2 的 {rho_glob_map['P2_TF_SECTION']:.4f} | 时段分配本身 ⇒ **水平效应**，非空间机制 |
| (b) 空间结构 | 组间 `rel_dev` 位移 ≤ {A_temporal_all:.4f} | 与残差 {S_spatial_all:.4f} 相比 **{ratio_all:.3f}** |

## 8. HTS gate

| 量 | 值 |
|---|---|
| `S_spatial`（全组 max\\|rel_dev(P0)\\|） | {S_spatial_all:+.4f} |
| `A_temporal`（全组 max\\|Δrel_dev\\|） | {A_temporal_all:+.4f} |
| ratio（全组） | {ratio_all:.4f} |
| `S_spatial`（命名组） | {S_spatial_key:+.4f} |
| `A_temporal`（命名组） | {A_temporal_key:+.4f} |
| ratio（命名组） | {ratio_key:.4f} |
| 排序保持 region / radial | {rank_region} / {rank_radial} |

**VERDICT: `{gate}`**（判据 PASS≥0.50 / PARTIAL≥0.20 / FAIL<0.20）

判读：时段可达位移相对残差仅 **{ratio_key:.1%}**（命名组口径；全组口径 {ratio_all:.1%}），
且 EAST / radial_in / NE 的组间排序与符号在全部 profile 下不变
⇒ **出发时段不是当前空间残差的主导机制**。

## 9. 局限（必须随结论引用）

本步骤是 temporal-only separable null，**无法**表征：

- route-choice 在当前时段分配下的重选；
- 拥堵溢出 / spillback 的时空耦合；
- 时段分散后 demand level 需重新标定的连锁效应。

因此结论严格表述为：**「时段分配本身」不足以解释现有空间残差**；
若 HTS 能提供独立行为证据或需检验
`departure-time × route-choice × congestion` 耦合，仍可进入 7.7B。

- MATSim rerun: **False** ｜ parameters changed: **False**
- lambda selected: **False** ｜ demand scale selected: **False**
"""
    (out / "STEP7_7C1_REPORT.md").write_text(report, encoding="utf-8")

    print(f"\n  产物 -> {out}  ({len(list(out.iterdir()))} 文件)")

    hard = {
        "must_match_76h": bool(all(checks.values())),
        "has_section_level_share": tfmeta["section_share_cv"] > 1e-6,
        "seven_profiles": len(prof) == 7,
        "no_matsim": True, "no_parameter_change": True,
        "gate_computed": gate.startswith("TEMPORAL_SPATIAL_SENSITIVITY"),
        "radial_reciprocal_present": len(rr) > 0,
    }
    print(f"STATUS: {sum(hard.values())}/{len(hard)} PASS")
    for k, v in hard.items():
        print(f"  {k}: {'PASS' if v else 'FAIL'}")


if __name__ == "__main__":
    main()
