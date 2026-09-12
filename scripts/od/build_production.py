#!/usr/bin/env python3
# -*- coding: utf-8 -*-

r"""
Singapore OD -> MATSim
Step 2: Build residence-side production (P_i^work / P_i^car)

输入：
    reports/od_zone/zone_dictionary.csv
        -> Step 1 产出的 332 个 Subzone 空间单元
    Singapore_OD_MATSim_FinalData/02_Population_Residence/outputFile (2)__T1.csv
        -> Table 88  Resident Population by PA/Subzone of Residence, Age Group and Sex
    Singapore_OD_MATSim_FinalData/06_Census_TravelBehavior/outputFile (4)__T8.csv
        -> Table 97  Resident Population Aged 15+ by PA of Residence, Labour Force Status and Sex
    Singapore_OD_MATSim_FinalData/06_Census_TravelBehavior/outputFile (4)__T15.csv
        -> Table 104 Employed Residents Aged 15+ by PA of Residence and Usual Mode of Transport to Work

输出：
    reports/od_production/
        production.csv              每个 zone_id 的 P_i^work / P_i^car
        pa_control_totals.csv       控制层（30 PA + Others）的就业总量与汽车分担
        zone_mode_shares.csv        每个 zone 的完整通勤方式分担（后续多方式模型用）
        production_validation.json  守恒与覆盖校验

方法（不是"总人口 x 一个比例"）：
    1. 分配键：Subzone 15 岁及以上人口（分男/女），来自 Table 88。
    2. 控制量：PA 级就业居民（分男/女），来自 Table 97。
    3. 下分：P_i^work = sum_sex [ Employed_g,sex * Pop15+_i,sex / sum_{j in g} Pop15+_j,sex ]
       其中 g 是 Subzone i 所属的"控制组"：
         - 若该 PA 属于 Census 地理分布表的 30 个指名 PA -> g = 该 PA
         - 否则（其余 25 个 PA）                                -> g = "Others"
    4. 恒等式：对每个控制组 g，sum_{i in g} P_i^work == Employed_g  (逐组精确守恒)
    5. P_i^car = P_i^work * (Car Only_g / Employed_g)
       分母刻意使用 Employed_g（而非 Table 104 的合计），以保证总量守恒：
       sum_i P_i^car == sum_g Car Only_g == 459,796

口径说明（重要）：
    - Table 97  Employed 合计         = 2,208,358
    - Table 104 合计（含 No Transport Required 212,907）= 2,177,456
    - 二者相差 30,902（1.40%），且该差额不等于 No Transport Required，
      来源未在本地数据中说明 -> 作为显式口径差异参数记录，不做人为修正。
    - Census 未区分 Car driver / Car passenger，"Car Only" 是合并口径。
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import pandas as pd


DEFAULT_PROJECT_ROOT = Path(r"D:\Luan\2026-05\2_Singapore")
DEFAULT_DATA_ROOT_NAME = "Singapore_OD_MATSim_FinalData"

ZONE_DICT = Path("reports/od_zone/zone_dictionary.csv")
T88 = Path("02_Population_Residence/outputFile (2)__T1.csv")
T97 = Path("06_Census_TravelBehavior/outputFile (4)__T8.csv")
T104 = Path("06_Census_TravelBehavior/outputFile (4)__T15.csv")

EXPECTED_ZONES = 332
EXPECTED_PHYSICAL_PA = 55
EXPECTED_TRAVEL_PA = 30

# 国家锚点（Census 2020）
ANCHOR_EMPLOYED_TOTAL = 2_208_358     # Table 97 / Table 111
ANCHOR_TABLE104_TOTAL = 2_177_456     # Table 104 / Table 118
ANCHOR_CAR_ONLY = 459_796             # Table 104 "Car Only"

PA_TOTAL_RE = re.compile(r"^(.+?)\s*-\s*Total$", re.I)

MODE_COLUMNS = [
    "Public Bus Only",
    "Rail (MRT/LRT) Only",
    "Rail (MRT/LRT) & Public Bus Only",
    "Combination of Rail (MRT/LRT) and/or Public Bus, with Other Modes",
    "Taxi/Private Hire Car Only",
    "Car Only",
    "Private Chartered Bus/Van Only",
    "Lorry/Pickup Only",
    "Motorcycle/Scooter Only",
    "Others",
    "No Transport Required",
]

AGE_GROUPS = [
    "0 - 4", "5 - 9", "10 - 14", "15 - 19", "20 - 24", "25 - 29",
    "30 - 34", "35 - 39", "40 - 44", "45 - 49", "50 - 54", "55 - 59",
    "60 - 64", "65 - 69", "70 - 74", "75 - 79", "80 - 84", "85 - 89",
    "90 & Over",
]
AGE_15PLUS = AGE_GROUPS[3:]       # 15-19 ... 90 & Over
AGE_15_64 = AGE_GROUPS[3:13]      # 15-19 ... 60-64


def norm_text(value) -> str:
    if value is None:
        return ""
    s = str(value).replace("\xa0", " ").strip()
    return re.sub(r"\s+", " ", s)


def norm_key(value) -> str:
    return norm_text(value).upper()


def to_num(value) -> float:
    if value is None:
        return 0.0
    s = str(value).replace(",", "").replace("\xa0", "").strip()
    if s in ("", "-", "na", "NA", "n/a", "nan"):
        return 0.0
    try:
        return float(s)
    except ValueError:
        return 0.0


def col_by_suffix(df: pd.DataFrame, suffix: str, prefix: str | None = None):
    """在列名中定位形如 'Total_15 - 19' / 'Males_15 - 19' 的列。"""
    target = f"_{suffix}"
    for c in df.columns:
        name = norm_text(c)
        if not name.endswith(target):
            continue
        head = name[: -len(target)]
        if prefix is None or head.upper() == prefix.upper():
            return c
    return None


def parse_table88(path: Path):
    """解析 Table 88，返回每个 Subzone 的人口结构。

    返回 list[dict]:
        planning_area, subzone_name, pop_total,
        pop_15plus, pop_15plus_male, pop_15plus_female, pop_15_64
    """
    df = pd.read_csv(path, encoding="utf-8-sig", low_memory=False)
    label_col = df.columns[0]

    # 逐列定位（Total / Males / Females 各 19 个年龄组）
    total_age_cols = [col_by_suffix(df, a, "Total") for a in AGE_GROUPS]
    male_age_cols = [col_by_suffix(df, a, "Males") for a in AGE_GROUPS]
    female_age_cols = [col_by_suffix(df, a, "Females") for a in AGE_GROUPS]
    if any(c is None for c in total_age_cols + male_age_cols + female_age_cols):
        raise ValueError("Table 88 年龄组列定位失败。")

    idx_15plus = [AGE_GROUPS.index(a) for a in AGE_15PLUS]
    idx_15_64 = [AGE_GROUPS.index(a) for a in AGE_15_64]

    def sum_at(cols, idxs):
        return sum(to_num(row[cols[i]]) for i in idxs)

    records = []
    current_pa = None
    skipped_no_pa = 0

    for _, row in df.iterrows():
        raw_label = norm_text(row[label_col])
        if not raw_label:
            continue
        if raw_label.upper() == "TOTAL":
            continue

        m = PA_TOTAL_RE.match(raw_label)
        if m:
            current_pa = norm_text(m.group(1))
            continue

        if current_pa is None:
            skipped_no_pa += 1
            continue

        records.append({
            "planning_area": current_pa,
            "subzone_name": raw_label,
            "pop_total": to_num(row[df.columns[1]]),  # 'Total' 列
            "pop_15plus": sum_at(total_age_cols, idx_15plus),
            "pop_15plus_male": sum_at(male_age_cols, idx_15plus),
            "pop_15plus_female": sum_at(female_age_cols, idx_15plus),
            "pop_15_64": sum_at(total_age_cols, idx_15_64),
        })

    if skipped_no_pa:
        raise ValueError(f"Table 88 有 {skipped_no_pa} 行落在任何 PA-Total 之前。")
    return records


def parse_pa_table(path: Path, value_cols: dict[str, str]):
    """解析 PA 级表（Table 97 / 104），返回 {PA_norm: {alias: value}}。"""
    df = pd.read_csv(path, encoding="utf-8-sig", low_memory=False)
    label_col = df.columns[0]
    for c in value_cols.values():
        if c not in df.columns:
            raise ValueError(f"{path.name} 缺少列：{c}")

    out = {}
    for _, row in df.iterrows():
        label = norm_text(row[label_col])
        if not label or label.upper() == "TOTAL":
            continue
        out[norm_key(label)] = {a: to_num(row[c]) for a, c in value_cols.items()}
    return out


def build_zone_dictionary_join(zone_df: pd.DataFrame):
    """建立 (PA_norm, subzone_norm) -> zone 记录的索引，并返回 55 个物理 PA。"""
    idx = {}
    for _, r in zone_df.iterrows():
        k = (norm_key(r["planning_area"]), norm_key(r["subzone_name"]))
        if k in idx:
            raise ValueError(f"zone_dictionary 存在重复键：{k}")
        idx[k] = r

    physical_pa = sorted(zone_df["planning_area"].dropna().unique())
    return idx, physical_pa


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, default=DEFAULT_PROJECT_ROOT)
    parser.add_argument("--data-root", type=Path, default=None)
    parser.add_argument("--out-dir", type=Path, default=None)
    args = parser.parse_args()

    project_root: Path = args.project_root
    data_root: Path = args.data_root or (project_root / DEFAULT_DATA_ROOT_NAME)
    out_dir: Path = args.out_dir or (project_root / "reports" / "od_production")

    zone_path = project_root / ZONE_DICT
    t88_path = data_root / T88
    t97_path = data_root / T97
    t104_path = data_root / T104

    for p in (zone_path, t88_path, t97_path, t104_path):
        if not p.exists():
            raise FileNotFoundError(f"输入文件不存在：{p}")

    checks: dict = {"status": "PASS"}

    # ---------- 1. 空间字典 ----------
    print("[1/6] 读取 zone_dictionary")
    zone = pd.read_csv(zone_path, encoding="utf-8-sig", dtype=str)
    for c in ("zone_id",):
        zone[c] = pd.to_numeric(zone[c])
    if len(zone) != EXPECTED_ZONES:
        raise ValueError(f"zone_dictionary 行数异常：{len(zone)} != {EXPECTED_ZONES}")

    z_idx, physical_pa = build_zone_dictionary_join(zone)
    checks["zones"] = int(len(zone))
    checks["physical_pa"] = len(physical_pa)
    if len(physical_pa) != EXPECTED_PHYSICAL_PA:
        raise ValueError(f"物理 PA 数异常：{len(physical_pa)} != {EXPECTED_PHYSICAL_PA}")

    # ---------- 2. Table 88 ----------
    print("[2/6] 解析 Table 88（Subzone 人口结构）")
    t88 = parse_table88(t88_path)
    checks["table88_subzone_rows"] = len(t88)
    if len(t88) != EXPECTED_ZONES:
        raise ValueError(f"Table 88 Subzone 行数异常：{len(t88)} != {EXPECTED_ZONES}")

    # Subzone -> 人口结构（以名称 + PA 双键匹配）
    pop_by_zone: dict[int, dict] = {}
    unmatched = []
    for rec in t88:
        key = (norm_key(rec["planning_area"]), norm_key(rec["subzone_name"]))
        zr = z_idx.get(key)
        if zr is None:
            unmatched.append(rec)
            continue
        pop_by_zone[int(zr["zone_id"])] = rec
    if unmatched:
        raise ValueError(
            "Table 88 有 Subzone 无法匹配 zone_dictionary："
            + str([(r["planning_area"], r["subzone_name"]) for r in unmatched][:20])
        )
    checks["table88_matched"] = len(pop_by_zone)

    # PA 层面自洽性：Subzone 聚合 15+ 人口 应等于该 PA 的 Total 行 15+ 合计
    df88 = pd.read_csv(t88_path, encoding="utf-8-sig", low_memory=False)
    label88 = df88.columns[0]
    total_age_cols88 = [col_by_suffix(df88, a, "Total") for a in AGE_GROUPS]
    idx_15plus88 = [AGE_GROUPS.index(a) for a in AGE_15PLUS]
    pa_total_15plus = {}
    for _, row in df88.iterrows():
        m = PA_TOTAL_RE.match(norm_text(row[label88]))
        if m:
            pa_total_15plus[norm_key(m.group(1))] = sum(
                to_num(row[total_age_cols88[i]]) for i in idx_15plus88
            )

    group_sum: dict[str, float] = {}
    for rec in pop_by_zone.values():
        g = norm_key(rec["planning_area"])
        group_sum[g] = group_sum.get(g, 0.0) + rec["pop_15plus"]

    parse_gap = []
    for g, s in group_sum.items():
        if g in pa_total_15plus:
            d = abs(s - pa_total_15plus[g])
            if d > 1.0:
                parse_gap.append({"pa": g, "subzone_sum": round(s, 3),
                                  "pa_total_row": round(pa_total_15plus[g], 3),
                                  "abs_diff": round(d, 3)})
    checks["table88_pa_blocks"] = len(group_sum)
    checks["table88_pa_parse_gaps"] = parse_gap

    # Table 88 全局取整口径说明：Subzone / PA / 全表三级合计互不相等
    grand_row = df88.iloc[0]
    grand_15plus = sum(to_num(grand_row[total_age_cols88[i]]) for i in idx_15plus88)
    subzone_15plus = sum(rec["pop_15plus"] for rec in pop_by_zone.values())
    checks["table88_rounding"] = {
        "note": "Census 2020 地理分布表按最接近 10 取整，三级合计不闭合（非解析错误）。",
        "grand_total_row_15plus": round(grand_15plus, 3),
        "subzone_sum_15plus": round(subzone_15plus, 3),
        "subzone_minus_grand": round(subzone_15plus - grand_15plus, 3),
        "pa_blocks_with_gap": len(parse_gap),
        "max_pa_gap": round(max([p["abs_diff"] for p in parse_gap], default=0.0), 3),
    }

    # ---------- 3. Table 97 ----------
    print("[3/6] 解析 Table 97（PA 就业居民，分男女）")
    t97 = parse_pa_table(t97_path, {
        "employed_total": "Labour Force - Employed_Total",
        "employed_male": "Labour Force - Employed_Males",
        "employed_female": "Labour Force - Employed_Females",
        "lf_total": "Labour Force - Total_Total",
        "pop_total": "Total",
    })
    travel_pa = sorted(t97.keys() - {"OTHERS"})
    checks["travel_pa"] = len(travel_pa)
    if len(travel_pa) != EXPECTED_TRAVEL_PA:
        raise ValueError(f"Table 97 指名 PA 数异常：{len(travel_pa)} != {EXPECTED_TRAVEL_PA}")
    if "OTHERS" not in t97:
        raise ValueError("Table 97 缺少 Others 行。")

    # ---------- 3b. Table 104（PA 通勤方式）----------
    print("[3b/6] 解析 Table 104（PA 通勤方式分担）")
    t104 = parse_pa_table(t104_path, {m: m for m in MODE_COLUMNS})
    missing_mode_pa = sorted(set(t97.keys()) - set(t104.keys()))
    if missing_mode_pa:
        raise ValueError(f"Table 104 缺少 PA 行：{missing_mode_pa}")
    t104_car = {g: v.get("Car Only", 0.0) for g, v in t104.items()}
    t104_share = {}
    for g, v in t104.items():
        tot = sum(v.values())
        t104_share[g] = {
            m: (v[m] / tot if tot > 0 else 0.0) for m in MODE_COLUMNS
        }
    checks["table104_total"] = round(sum(sum(v.values()) for v in t104.values()), 3)

    # ---------- 4. 控制组映射 ----------
    print("[4/6] 映射 55 物理 PA -> 控制组（30 PA 或 Others）")
    pa_to_group = {}
    for pa in physical_pa:
        k = norm_key(pa)
        pa_to_group[k] = k if k in t97 and k != "OTHERS" else "OTHERS"

    group_members: dict[str, list[str]] = {}
    for k, g in pa_to_group.items():
        group_members.setdefault(g, []).append(k)

    checks["groups"] = len(group_members)
    others_members = sorted(group_members.get("OTHERS", []))
    checks["others_physical_pa_count"] = len(others_members)

    # ---------- 5. 下分 ----------
    print("[5/6] 下分 P_i^work / P_i^car")
    # 组内人口基
    group_pop = {}
    for zid, rec in pop_by_zone.items():
        g = pa_to_group[norm_key(rec["planning_area"])]
        d = group_pop.setdefault(g, {"m": 0.0, "f": 0.0, "t": 0.0})
        d["m"] += rec["pop_15plus_male"]
        d["f"] += rec["pop_15plus_female"]
        d["t"] += rec["pop_15plus"]

    # --- Pass 1：按分配键算 raw，并累计各组 raw 之和 ---
    raw: dict[int, dict] = {}
    raw_group_sum: dict[str, float] = {}
    for _, zr in zone.iterrows():
        zid = int(zr["zone_id"])
        rec = pop_by_zone.get(zid)
        if rec is None:
            raise ValueError(f"zone_id={zid} 缺 Table 88 人口记录。")
        g = pa_to_group[norm_key(rec["planning_area"])]
        ctrl = t97[g]
        gp = group_pop[g]

        share_m = (rec["pop_15plus_male"] / gp["m"]) if gp["m"] > 0 else 0.0
        share_f = (rec["pop_15plus_female"] / gp["f"]) if gp["f"] > 0 else 0.0

        if gp["m"] <= 0 and gp["f"] <= 0 and gp["t"] > 0:
            # 极端退化：无性别基，回退到总量口径
            share_t = rec["pop_15plus"] / gp["t"]
            raw_m = ctrl["employed_total"] * share_t * (
                rec["pop_15plus_male"] / rec["pop_15plus"] if rec["pop_15plus"] > 0 else 0.0
            )
            raw_f = ctrl["employed_total"] * share_t - raw_m
        else:
            raw_m = ctrl["employed_male"] * share_m
            raw_f = ctrl["employed_female"] * share_f

        raw[zid] = {"m": raw_m, "f": raw_f, "g": g}
        raw_group_sum[g] = raw_group_sum.get(g, 0.0) + raw_m + raw_f

    # 组内归一：源表 Employed_total 未必等于 male + female（Census 取整），
    # 这里统一缩放到控制总量，保证逐组精确守恒。
    group_scale = {}
    for g, s in raw_group_sum.items():
        target = t97[g]["employed_total"]
        group_scale[g] = (target / s) if s > 0 else 0.0

    # --- Pass 2：应用缩放并组装输出 ---
    rows = []
    for _, zr in zone.iterrows():
        zid = int(zr["zone_id"])
        rec = pop_by_zone[zid]
        g = raw[zid]["g"]
        ctrl = t97[g]
        sc = group_scale[g]

        p_work_m = raw[zid]["m"] * sc
        p_work_f = raw[zid]["f"] * sc
        p_work = p_work_m + p_work_f

        # Car Only / Employed（分母用 Employed，保证总量守恒）
        employed_g = ctrl["employed_total"]
        car_only_g = t104_car.get(g, 0.0)
        car_share = (car_only_g / employed_g) if employed_g > 0 else 0.0
        p_car = p_work * car_share

        rows.append({
            "zone_id": zid,
            "subzone_code": zr["subzone_code"],
            "subzone_name": zr["subzone_name"],
            "planning_area_code": zr["planning_area_code"],
            "planning_area": zr["planning_area"],
            "planning_region_code": zr["planning_region_code"],
            "planning_region": zr["planning_region"],
            "population": round(rec["pop_total"], 3),
            "pop_15plus": round(rec["pop_15plus"], 3),
            "pop_15plus_male": round(rec["pop_15plus_male"], 3),
            "pop_15plus_female": round(rec["pop_15plus_female"], 3),
            "pop_15_64": round(rec["pop_15_64"], 3),
            "control_group": g,
            "group_employed_total": round(ctrl["employed_total"], 3),
            "work_trip_production": round(p_work, 6),
            "work_trip_production_male": round(p_work_m, 6),
            "work_trip_production_female": round(p_work_f, 6),
            "group_car_share": round(car_share, 8),
            "car_work_trip_production": round(p_car, 6),
        })

    prod = pd.DataFrame(rows).sort_values("zone_id").reset_index(drop=True)

    # ---------- 6. 校验 ----------
    print("[6/6] 守恒校验")
    sum_work = prod["work_trip_production"].sum()
    sum_car = prod["car_work_trip_production"].sum()

    # 逐组守恒
    group_check = []
    tmp = prod.copy()
    tmp["phys_pa_key"] = tmp["planning_area"].map(norm_key)
    tmp["group"] = tmp["phys_pa_key"].map(pa_to_group)
    for g, sub in tmp.groupby("group"):
        got = sub["work_trip_production"].sum()
        want = t97[g]["employed_total"]
        group_check.append({
            "group": g,
            "zones": int(len(sub)),
            "production_sum": round(got, 6),
            "control_employed": round(want, 3),
            "abs_diff": round(abs(got - want), 6),
        })

    max_group_diff = max(g["abs_diff"] for g in group_check)
    checks["sum_work_production"] = round(sum_work, 3)
    checks["anchor_employed_total"] = ANCHOR_EMPLOYED_TOTAL
    checks["work_vs_anchor_diff"] = round(sum_work - ANCHOR_EMPLOYED_TOTAL, 3)
    checks["sum_car_production"] = round(sum_car, 3)
    checks["anchor_car_only"] = ANCHOR_CAR_ONLY
    checks["car_vs_anchor_diff"] = round(sum_car - ANCHOR_CAR_ONLY, 3)
    checks["max_group_conservation_diff"] = round(max_group_diff, 6)
    checks["group_control_table"] = group_check
    checks["others_groups"] = others_members

    # 口径差异（显式记录，不修正）
    checks["caliber_gap_table118_vs_workplaceT4"] = {
        "table104_total": ANCHOR_TABLE104_TOTAL,
        "workplace_T4_total": ANCHOR_EMPLOYED_TOTAL,
        "abs_diff": ANCHOR_EMPLOYED_TOTAL - ANCHOR_TABLE104_TOTAL,
        "pct": round(
            (ANCHOR_EMPLOYED_TOTAL - ANCHOR_TABLE104_TOTAL) / ANCHOR_EMPLOYED_TOTAL * 100, 4
        ),
        "note": (
            "差额 30,902 且不等于 No Transport Required(212,907)，"
            "来源未在本地数据说明；Step 5 Census 约束时作为显式口径参数处理。"
        ),
    }

    if abs(checks["work_vs_anchor_diff"]) > 5:
        checks["status"] = "WARN"
    if max_group_diff > 1e-3:
        checks["status"] = "WARN"
    if abs(checks["car_vs_anchor_diff"]) > 5:
        checks["status"] = "WARN"

    # ---------- 输出 ----------
    out_dir.mkdir(parents=True, exist_ok=True)

    # 控制层表
    ctrl_rows = []
    for g, members in sorted(group_members.items()):
        c = t97[g]
        car_share = (t104_car.get(g, 0.0) / c["employed_total"]) if c["employed_total"] else 0.0
        ctrl_rows.append({
            "control_group": g,
            "n_physical_pa": len(members),
            "physical_pa": "|".join(sorted(members)),
            "pop_total_15plus": round(c["pop_total"], 3),
            "labour_force": round(c["lf_total"], 3),
            "employed_total": round(c["employed_total"], 3),
            "employed_male": round(c["employed_male"], 3),
            "employed_female": round(c["employed_female"], 3),
            "employed_m_plus_f_minus_total": round(
                c["employed_male"] + c["employed_female"] - c["employed_total"], 3
            ),
            "normalization_scale": round(group_scale.get(g, 1.0), 10),
            "car_only": round(t104_car.get(g, 0.0), 3),
            "car_share_of_employed": round(car_share, 8),
        })
    ctrl_df = pd.DataFrame(ctrl_rows).sort_values("control_group").reset_index(drop=True)

    # 每个 zone 的完整通勤方式分担
    mode_rows = []
    for _, zr in zone.iterrows():
        zid = int(zr["zone_id"])
        rec = pop_by_zone[zid]
        g = pa_to_group[norm_key(rec["planning_area"])]
        row = {
            "zone_id": zid,
            "subzone_code": zr["subzone_code"],
            "planning_area": zr["planning_area"],
            "control_group": g,
        }
        row.update({f"share__{m}": t104_share.get(g, {}).get(m, 0.0) for m in MODE_COLUMNS})
        mode_rows.append(row)
    mode_df = pd.DataFrame(mode_rows).sort_values("zone_id").reset_index(drop=True)

    prod_path = out_dir / "production.csv"
    ctrl_path = out_dir / "pa_control_totals.csv"
    mode_path = out_dir / "zone_mode_shares.csv"
    report_path = out_dir / "production_validation.json"

    prod.to_csv(prod_path, index=False, encoding="utf-8-sig")
    ctrl_df.to_csv(ctrl_path, index=False, encoding="utf-8-sig")
    mode_df.to_csv(mode_path, index=False, encoding="utf-8-sig")
    with report_path.open("w", encoding="utf-8") as f:
        json.dump(checks, f, ensure_ascii=False, indent=2)

    print("\n" + "=" * 72)
    print("Step 2 | Residence Production (P_i^work / P_i^car)")
    print("=" * 72)
    print(f"Zones                  : {len(prod)}")
    print(f"Control groups         : {len(group_members)} (30 PA + Others)")
    print(f"Sum P^work             : {sum_work:,.0f}   (anchor {ANCHOR_EMPLOYED_TOTAL:,})")
    print(f"Sum P^car              : {sum_car:,.0f}   (anchor {ANCHOR_CAR_ONLY:,})")
    print(f"Max group conservation : {max_group_diff:.6f}")
    print(f"Output                 : {prod_path}")
    print(f"Output                 : {ctrl_path}")
    print(f"Output                 : {mode_path}")
    print(f"Report                 : {report_path}")
    print(f"Status                 : {checks['status']}")
    print("=" * 72)

    return prod, ctrl_df, mode_df, checks


if __name__ == "__main__":
    main()
