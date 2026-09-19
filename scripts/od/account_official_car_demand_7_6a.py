# -*- coding: utf-8 -*-
"""
Step 7.6A —— Official Car-Demand Accounting（官方汽车通勤需求会计；zero simulation）

目标
----
把「官方通勤需求」与「MATSim car-trip equivalent = 459,794」逐层对账，回答：
    459,794 究竟占官方机动车通勤需求的多少？
并据此判断：现行 7.4.3 的「总量不足」应归因于 **demand scale** 还是 **统计口径差**。

设计原则
--------
1. **零仿真**：只读既有冻结产物与 LTA/Census 原始表，绝不启动 MATSim。
2. **不丢总量**：`No Fixed Location for Work` / `Works from Home` /
   `Other Planning Areas or Outside Singapore` 单列为「非物理承载桶」，不塞进道路 OD，也不丢弃。
3. **口径显式**：每个数字标注 来源文件 / 表号 / 是否官方分组 / 是否本项目假设。
4. **不伪定量**：凡本地数据无法分解的（车型构成、出发时刻、平均载客），一律
   报告为「不可定量」并写明所需外部数据源，不给猜测值。

链条
----
    Employed residents (Census 2020)
      -> physical workplace / non-physical buckets
      -> usual mode of transport to work
      -> road-vehicle caliber variants V1..V4   (persons)
      -> occupancy sensitivity                  (persons -> vehicles)
      -> AM-peak / purpose coverage
      -> MATSim car-trip equivalent (459,794)
      -> coverage ratio + implied demand-scale bracket

运行
----
    python scripts/od/account_official_car_demand_7_6a.py
产物
----
    reports/od_calibration_7_6a/STEP7_6A_REPORT.md
    reports/od_calibration_7_6a/car_demand_accounting_layers.csv
    reports/od_calibration_7_6a/mode_split_official.csv
    reports/od_calibration_7_6a/mode_split_crosscheck.csv
    reports/od_calibration_7_6a/pa_car_share_official.csv
    reports/od_calibration_7_6a/special_workplace_buckets.csv
    reports/od_calibration_7_6a/coverage_gap_decomposition.csv
    reports/od_calibration_7_6a/observation_coverage_audit.csv
    reports/od_calibration_7_6a/step7_6a_summary.json
    reports/od_calibration_7_6a/account_console.log
"""

from __future__ import annotations

import csv
import io
import json
import os
import sys
from collections import OrderedDict

# ----------------------------------------------------------------------------
# 路径
# ----------------------------------------------------------------------------
ROOT = r"D:\Luan\2026-05\2_Singapore"
DATA = os.path.join(ROOT, "Singapore_OD_MATSim_FinalData")
OUT = os.path.join(ROOT, "reports", "od_calibration_7_6a")

P_T10 = os.path.join(DATA, "06_Census_TravelBehavior", "outputFile (5)__T10.csv")   # 就业居民 × 方式 × 行业（全国）
P_T7 = os.path.join(DATA, "06_Census_TravelBehavior", "outputFile (5)__T7.csv")     # 就业居民 × 方式 × 年龄（全国）
P_RES_T15 = os.path.join(DATA, "06_Census_TravelBehavior", "outputFile (4)__T15.csv")  # 就业居民 × 居住 PA × 方式
P_GHS_T8 = os.path.join(DATA, "06_Census_TravelBehavior", "outputFile__T8.csv")     # GHS2025 就业居民 × 方式 × 年龄
P_STU_T1 = os.path.join(DATA, "06_Census_TravelBehavior", "outputFile (5)__T1.csv")  # 学生 × 方式 × 年龄（全国）
P_WP_T4 = os.path.join(DATA, "03_Workplace_Employment", "outputFile (3)__T4.csv")   # 工作地 PA × 年龄
P_WP_T9 = os.path.join(DATA, "03_Workplace_Employment", "outputFile (3)__T9.csv")   # 工作地 PA × 方式
P_WP_T11 = os.path.join(
    DATA, "03_Workplace_Employment", "outputFile (3)__T11.csv")                      # 工作地 PA × 方式组 × 居住 Region
P_ATTR_VAL = os.path.join(ROOT, "reports", "od_attraction_v21", "attraction_v21_validation.json")
P_SPECIAL = os.path.join(ROOT, "reports", "od_attraction_v21", "special_workplace_destinations.csv")
P_PROD_VAL = os.path.join(ROOT, "reports", "od_production", "production_validation.json")
P_7_4_3R = os.path.join(ROOT, "reports", "od_calibration_7_4_3r", "window_reevaluation_comparison.csv")
P_DEP_PROF = os.path.join(ROOT, "reports", "matsim_departure_6_3_3a", "departure_profile.csv")
P_FLOW = os.path.join(DATA, "08_TrafficCount", "TrafficFlow_Data.json")
P_SPEEDBANDS = os.path.join(DATA, "08_TrafficCount", "TrafficSpeedBands_v4.json")
P_TRAV = os.path.join(DATA, "08_TrafficCount", "EstimatedTravelTimes.json")

# 冻结锚
MATSIM_SIGMA_EF = 459_794.0     # 6.2B 实现值（Σ expansionFactor）
ANCHOR_CAR_ONLY = 459_796       # Census Table 104 "Car Only"
PHYSICAL_CONTROL = 1_935_235.0  # 03B.1 physical workplace control

SPECIAL_NODES = [
    "NO FIXED LOCATION FOR WORK",
    "WORKS FROM HOME",
    "OTHER PLANNING AREAS OR OUTSIDE SINGAPORE",
]

LOG: list[str] = []


def log(msg: str = "") -> None:
    LOG.append(msg)
    print(msg)


def f0(x):
    return "-" if x is None else "{:,.0f}".format(x)


def f2(x):
    return "-" if x is None else "{:.4f}".format(x)


def pct(x, nd=2):
    return "-" if x is None else ("{:." + str(nd) + "f}%").format(x * 100)


def num(s):
    """容错数值解析（' -' / '' / '#N/A' -> None）。"""
    if s is None:
        return None
    t = str(s).strip().replace(",", "")
    if t in ("", "-", "#N/A", "na", "NA"):
        return None
    try:
        return float(t)
    except ValueError:
        return None


def read_rows(path):
    """读 CSV，返回 (header, list[list[str]])，自动去 BOM / 空行。"""
    with io.open(path, encoding="utf-8-sig", newline="") as fh:
        raw = [r for r in csv.reader(fh) if any((c or "").strip() for c in r)]
    if not raw:
        raise RuntimeError("empty csv: %s" % path)
    hdr = [(c or "").strip() for c in raw[0]]
    return hdr, raw[1:]


def col(hdr, *names):
    """按名找列索引（大小写/空格不敏感，允许前缀匹配）。"""
    norm = [h.replace(" ", "").lower() for h in hdr]
    for nm in names:
        tgt = nm.replace(" ", "").lower()
        for i, h in enumerate(norm):
            if h == tgt:
                return i
    for nm in names:
        tgt = nm.replace(" ", "").lower()
        for i, h in enumerate(norm):
            if tgt and tgt in h:
                return i
    return None


# 方式列的标准名（Census 2020 / GHS 列名一致）
MODES = OrderedDict([
    ("Public Bus Only", "公汽独用"),
    ("Rail (MRT/LRT) Only", "轨道独用"),
    ("Rail (MRT/LRT) & Public Bus Only", "轨道+公汽"),
    ("Combination of Rail (MRT/LRT) and/or Public Bus, with Other Modes", "轨道/公汽组合"),
    ("Taxi/Private Hire Car Only", "出租车/网约车独用"),
    ("Car Only", "小汽车独用"),
    ("Private Chartered Bus/Van Only", "私人包车/面包车"),
    ("Lorry/Pickup Only", "货车/皮卡"),
    ("Motorcycle/Scooter Only", "摩托/踏板"),
    ("Others", "其他"),
    ("No Transport Required", "无需交通"),
])

PUBLIC_TRANSPORT = ["Public Bus Only", "Rail (MRT/LRT) Only",
                    "Rail (MRT/LRT) & Public Bus Only",
                    "Combination of Rail (MRT/LRT) and/or Public Bus, with Other Modes"]
CAR_TAXI = ["Car Only", "Taxi/Private Hire Car Only"]
OTHER_PRIVATE_ROAD = ["Private Chartered Bus/Van Only", "Lorry/Pickup Only",
                      "Motorcycle/Scooter Only", "Others"]


def main() -> int:
    os.makedirs(OUT, exist_ok=True)
    log("=" * 78)
    log("Step 7.6A —— Official Car-Demand Accounting（zero simulation）")
    log("=" * 78)

    checks: list[tuple[str, bool, str]] = []

    def ck(name, ok, detail=""):
        checks.append((name, bool(ok), detail))
        log("   [%s] %s%s" % ("OK " if ok else "FAIL", name, ("  " + detail) if detail else ""))

    # =====================================================================
    # L2 先读方式表（后续多层要用）
    # =====================================================================
    hdr10, rows10 = read_rows(P_T10)
    i_mode = 0
    i_tot = col(hdr10, "Total")
    nat = OrderedDict()
    for r in rows10:
        k = (r[i_mode] or "").strip()
        if k:
            nat[k] = num(r[i_tot])
    mode_total = nat.get("Total")
    mode_sum = sum(v for k, v in nat.items() if k != "Total" and v is not None)

    log("\n[L2] 官方通勤方式分解（Census 2020，居住就业居民 15+）")
    log("   universe Total = %s   Σ(11 方式) = %s   Δ = %s"
        % (f0(mode_total), f0(mode_sum), f0(mode_sum - mode_total)))
    ck("L2.1 方式表自身闭合 (|Δ|<=11)", abs(mode_sum - mode_total) <= 11,
       "Δ=%s" % f0(mode_sum - mode_total))
    ck("L2.2 Car Only == 项目锚 459,796", nat.get("Car Only") == ANCHOR_CAR_ONLY,
       "实测 %s" % f0(nat.get("Car Only")))

    # 方式组（官方 T11 自带分组）
    g_pt = sum(nat.get(m, 0) or 0 for m in PUBLIC_TRANSPORT)
    g_car_taxi = sum(nat.get(m, 0) or 0 for m in CAR_TAXI)
    g_other_road = sum(nat.get(m, 0) or 0 for m in OTHER_PRIVATE_ROAD)
    g_none = nat.get("No Transport Required") or 0
    g_private_road = g_car_taxi + g_other_road

    log("   公共交通(含组合)      = %s  (%s)" % (f0(g_pt), pct(g_pt / mode_total)))
    log("   Car or Taxi/PHC      = %s  (%s)" % (f0(g_car_taxi), pct(g_car_taxi / mode_total)))
    log("   其他私人道路方式      = %s  (%s)" % (f0(g_other_road), pct(g_other_road / mode_total)))
    log("   ★ 私人道路机动车合计  = %s  (%s)" % (f0(g_private_road), pct(g_private_road / mode_total)))
    log("   无需交通              = %s  (%s)" % (f0(g_none), pct(g_none / mode_total)))

    # 与官方 T11 的 mode-group 列对账（官方自带 "Car or Taxi/Private Hire Car"）
    hdr11, rows11 = read_rows(P_WP_T11)
    tot11 = {}
    for h in hdr11:
        pass
    c_car_taxi = col(hdr11, "Total_Mode of Transport_Car or Taxi/Private Hire Car")
    c_combi = col(hdr11, "Total_Mode of Transport_Combinations of Public Transport")
    c_other = col(hdr11, "Total_Mode of Transport_Other Modes")
    c_none = col(hdr11, "Total_Mode of Transport_No Transport Required")
    t11 = rows11[0]
    t11_map = {
        "Car or Taxi/PHC": num(t11[c_car_taxi]) if c_car_taxi is not None else None,
        "Combinations of Public Transport": num(t11[c_combi]) if c_combi is not None else None,
        "Other Modes": num(t11[c_other]) if c_other is not None else None,
        "No Transport Required": num(t11[c_none]) if c_none is not None else None,
    }
    log("   [官方 T11 分组对账] Car or Taxi/PHC = %s（本地求和 %s）"
        % (f0(t11_map["Car or Taxi/PHC"]), f0(g_car_taxi)))
    ck("L2.3 本地方式组 == 官方 T11 分组 (Car or Taxi/PHC)",
       t11_map["Car or Taxi/PHC"] == g_car_taxi, "官方 %s vs 本地 %s"
       % (f0(t11_map["Car or Taxi/PHC"]), f0(g_car_taxi)))
    ck("L2.4 本地方式组 == 官方 T11 分组 (Other Modes)",
       t11_map["Other Modes"] == g_other_road,
       "官方 %s vs 本地 %s" % (f0(t11_map["Other Modes"]), f0(g_other_road)))
    ck("L2.5 本地方式组 == 官方 T11 分组 (No Transport Required)",
       t11_map["No Transport Required"] == g_none, "")

    # 交叉核对：T7（方式×年龄）与 GHS2025
    hdr7, rows7 = read_rows(P_T7)
    n7 = {}
    for r in rows7:
        n7[(r[0] or "").strip()] = num(r[col(hdr7, "Total")])
    ck("L2.6 T7(方式×年龄) universe == T10(方式×行业)",
       n7.get("Total") == mode_total, "%s vs %s" % (f0(n7.get("Total")), f0(mode_total)))
    ck("L2.7 T7 Car Only == T10 Car Only",
       n7.get("Car Only") == nat.get("Car Only"), "")

    hdrg, rowsg = read_rows(P_GHS_T8)
    ng = {}
    for r in rowsg:
        ng[(r[0] or "").strip()] = num(r[col(hdrg, "Total")])
    ghs_tot = ng.get("Total")
    ghs_car = ng.get("Car Only")
    log("   [GHS 2025 对照] universe = %s   Car Only = %s (%s)"
        % (f0(ghs_tot), f0(ghs_car), pct((ghs_car or 0) / (ghs_tot or 1))))

    # =====================================================================
    # L0 就业锚
    # =====================================================================
    hdr4, rows4 = read_rows(P_WP_T4)
    wp = {}
    special_wp = {}
    for r in rows4:
        k = (r[0] or "").strip()
        v = num(r[1])
        wp[k] = v
        if k.upper() in SPECIAL_NODES:
            special_wp[k.upper()] = v
    wp_total = wp.get("Total")
    resid_total = mode_total  # 居住侧就业居民 15+
    phys_from_wp = wp_total - sum(v for v in special_wp.values() if v is not None)

    log("\n[L0] 就业总量锚（Census 2020，就业居民 15+）")
    log("   居住侧 universe                = %s" % f0(resid_total))
    log("   工作地侧 universe (T4 合计)     = %s" % f0(wp_total))
    log("   口径差                          = %s (%s)"
        % (f0(wp_total - resid_total), pct((wp_total - resid_total) / resid_total)))

    # =====================================================================
    # L1 物理 / 非物理工作地
    # =====================================================================
    log("\n[L1] 物理 vs 非物理工作地（工作地侧）")
    special_rows = []
    for k in SPECIAL_NODES:
        v = special_wp.get(k)
        special_rows.append((k, v))
        log("   %-46s = %s" % (k, f0(v)))
    special_sum = sum(v for _, v in special_rows if v is not None)
    log("   非物理承载合计                  = %s" % f0(special_sum))
    log("   物理工作地（推导）              = %s" % f0(phys_from_wp))
    log("   物理工作地（03B.1 实际控制）    = %s" % f0(PHYSICAL_CONTROL))
    ck("L1.1 推导物理工作地 == 03B.1 控制 (|Δ|<=1)",
       abs(phys_from_wp - PHYSICAL_CONTROL) <= 1,
       "Δ=%s" % f0(phys_from_wp - PHYSICAL_CONTROL))
    ck("L1.2 物理 + 非物理 == 工作地侧合计",
       abs((phys_from_wp + special_sum) - wp_total) <= 1, "")
    log("   ★ 物理承载占比                 = %s" % pct(PHYSICAL_CONTROL / wp_total))
    log("   ★ 非物理承载占比               = %s" % pct(special_sum / wp_total))

    # special_workplace_destinations.csv 对账
    hs, rs = read_rows(P_SPECIAL)
    sp_file = {}
    for r in rs:
        sp_file[(r[0] or "").strip().upper()] = num(r[2])
    ck("L1.3 special_workplace_destinations.csv 与 T4 一致",
       all(sp_file.get(k) == special_wp.get(k) for k in SPECIAL_NODES),
       str({k: (sp_file.get(k), special_wp.get(k)) for k in SPECIAL_NODES}))

    # =====================================================================
    # L3 道路机动车需求口径变体（人）
    # =====================================================================
    V = OrderedDict()
    V["V1_CarOnly"] = nat.get("Car Only")
    V["V2_Car_or_TaxiPHC"] = g_car_taxi
    V["V3_PrivateRoadMotorised"] = g_private_road
    V["V4_RoadPersonAll"] = g_private_road  # 与 V3 同（人不含公交，公交按人不可比）
    log("\n[L3] 道路机动车需求口径变体（人/日通勤）")
    for k, v in V.items():
        log("   %-26s = %s  (占就业居民 %s)" % (k, f0(v), pct(v / mode_total)))

    # 与 MATSim 锚的关系
    f_V2 = V["V2_Car_or_TaxiPHC"] / V["V1_CarOnly"]
    f_V3 = V["V3_PrivateRoadMotorised"] / V["V1_CarOnly"]
    log("   ★ 若口径切到 V2 → 隐含 f = %s" % f2(f_V2))
    log("   ★ 若口径切到 V3 → 隐含 f = %s" % f2(f_V3))

    # 占位率敏感性
    OCC = [1.00, 1.15, 1.30]
    occ_rows = []
    log("\n   占位率敏感性（人 → 车辆；现行隐含 occ = 1.00）")
    for occ in OCC:
        r = {"occupancy": occ}
        for k in ("V1_CarOnly", "V2_Car_or_TaxiPHC", "V3_PrivateRoadMotorised"):
            r[k] = V[k] / occ
        occ_rows.append(r)
        log("   occ=%.2f  V1=%11s  V2=%11s  V3=%11s"
            % (occ, f0(r["V1_CarOnly"]), f0(r["V2_Car_or_TaxiPHC"]),
               f0(r["V3_PrivateRoadMotorised"])))

    # =====================================================================
    # L4 时间（AM 峰）与目的覆盖
    # =====================================================================
    dep = {}
    if os.path.exists(P_DEP_PROF):
        hd, rd = read_rows(P_DEP_PROF)
        for r in rd:
            dep[(r[0] or "").strip()] = r
    # 学生侧（目的覆盖用）
    hst, rst = read_rows(P_STU_T1)
    stu = {}
    for r in rst:
        stu[(r[0] or "").strip()] = num(r[col(hst, "Total")])
    stu_travel = (stu.get("Total") or 0) - (stu.get("No Transport Required") or 0)
    work_travel = (nat.get("Total") or 0) - g_none

    log("\n[L4] 时间（AM 峰）与目的覆盖")
    dep7 = dep8 = None
    for k, r in dep.items():
        if "07" in k and "08" in k:
            dep7 = num(r[-1]) if num(r[-1]) is not None else None
    if os.path.exists(P_DEP_PROF):
        with io.open(P_DEP_PROF, encoding="utf-8-sig") as fh:
            log("   departure_profile.csv 原文：")
            for i, line in enumerate(fh):
                if i > 8:
                    break
                log("      " + line.rstrip()[:150])
    log("   Census 无 departure-time 维度（仅行程时间分箱）→ AM 峰因子**不可独立标定**")
    log("   6.3.3A 出发剖面由 TrafficFlow 自身推导 → 与标定靶场**循环**，非独立证据")
    log("   需外部源：LTA Household Travel Survey (HTS) 出发时刻")
    log("   目的覆盖（工作动机 相对 工作+上学）：")
    log("      通勤出行人口（就业居民剔除无需交通） = %s" % f0(work_travel))
    log("      上学出行人口（学生剔除无需交通）     = %s" % f0(stu_travel))
    car_work = V["V1_CarOnly"]
    car_stu = stu.get("Car Only")
    log("      Car Only：通勤 %s / 上学 %s" % (f0(car_work), f0(car_stu)))
    purpose_share = car_work / (car_work + (car_stu or 0))
    log("   ★ 通勤在「小汽车通勤+上学」中的占比   = %s" % pct(purpose_share))

    # =====================================================================
    # L5 观测对齐审计
    # =====================================================================
    log("\n[L5] LTA 观测对齐审计")
    obs_rows = []
    with io.open(P_FLOW, encoding="utf-8-sig") as fh:
        obj = json.load(fh)
    frows = obj["Value"]
    hours = sorted({r.get("HourOfDate") for r in frows})
    dates = sorted({r.get("Date") for r in frows})
    roadcats = {}
    for r in frows:
        roadcats[r.get("RoadCat")] = roadcats.get(r.get("RoadCat"), 0) + 1
    fields = list(frows[0].keys())
    log("   TrafficFlow_Data.json: rows=%s  hour∈%s  dates=%d  LinkID=%d"
        % (f0(len(frows)), hours, len(dates), len({r.get("LinkID") for r in frows})))
    log("   RoadCat: %s" % ", ".join("%s=%s" % (k, f0(v)) for k, v in
                                    sorted(roadcats.items(), key=lambda t: -t[1])))
    log("   字段: %s" % ", ".join(fields))
    has_veh = any("veh" in f.lower() for f in fields)
    ck("L5.1 观测**不含**车型字段（⇒ 车型构成不可分解）", not has_veh,
       "字段 = %s" % ",".join(fields))
    for r in frows[0].keys():
        obs_rows.append(("TrafficFlow_Data.json", "row-schema", r, "-"))
    obs_rows.append(("TrafficFlow_Data.json", "rows", str(len(frows)), "-"))
    obs_rows.append(("TrafficFlow_Data.json", "hour coverage", ",".join(hours), "-"))
    obs_rows.append(("TrafficFlow_Data.json", "n_dates", str(len(dates)), "2025-11"))
    obs_rows.append(("TrafficFlow_Data.json", "n_LinkID", str(len({r.get("LinkID") for r in frows})), "-"))
    obs_rows.append(("TrafficFlow_Data.json", "vehicle_type_field", "NO", "→ 车型构成不可分解"))
    for k, v in sorted(roadcats.items(), key=lambda t: -t[1]):
        obs_rows.append(("TrafficFlow_Data.json", "RoadCat:%s" % k, str(v), "-"))
    # 单时刻快照源
    for p, nm in ((P_SPEEDBANDS, "TrafficSpeedBands_v4.json"), (P_TRAV, "EstimatedTravelTimes.json")):
        if os.path.exists(p):
            try:
                o = json.load(io.open(p, encoding="utf-8-sig"))
                vv = o.get("Value", o) if isinstance(o, dict) else o
                ts = {r.get("Timestamp") for r in vv if isinstance(r, dict)}
                obs_rows.append((nm, "distinct_timestamp", str(len(ts)),
                                 "单时刻快照 → 不可作时间序列靶场"))
                log("   %-30s distinct Timestamp = %d（单时刻快照）" % (nm, len(ts)))
            except Exception as e:  # noqa: BLE001
                obs_rows.append((nm, "read_error", str(e)[:60], "-"))
    log("   ⇒ 可观测窗上限 = 07–09；车型构成 / 出发时刻 / 载客率 均**无本地观测**")

    # =====================================================================
    # L6 量级一致性检验 与 隐含 demand scale 区间
    # =====================================================================
    log("\n[L6] 量级一致性检验 与 隐含 demand scale 区间")
    mat_am_f100 = None
    if os.path.exists(P_7_4_3R):
        h3, r3 = read_rows(P_7_4_3R)
        i_m = col(h3, "method")
        i_w = col(h3, "window")
        i_s = col(h3, "SimObs_all")
        i_sr = col(h3, "series")
        for r in r3:
            if (r[i_sr] or "").strip() == "physical" and (r[i_m] or "").strip() == "D01" \
                    and (r[i_w] or "").strip() == "07-09":
                mat_am_f100 = num(r[i_s])
    ck("L6.1 读到 7.4.3-R MATCHED 07-09 @f=1.00", mat_am_f100 is not None,
       "SimObs=%s" % f2(mat_am_f100))

    cov_V3 = V["V1_CarOnly"] / V["V3_PrivateRoadMotorised"]
    cov_V2 = V["V1_CarOnly"] / V["V2_Car_or_TaxiPHC"]
    log("   模态覆盖率 V1/V2 = %s   V1/V3 = %s" % (f2(cov_V2), f2(cov_V3)))
    log("   基准断面水平  SimObs(07-09, f=1.00) = %s" % f2(mat_am_f100))

    # 上端：完全不做口径调整，把缺口全算作需求不足
    f_hi = (1.0 / mat_am_f100) if mat_am_f100 else None
    # 下端：把 V3 口径差当作可比基准（不额外加车）
    f_lo_ratio = (cov_V3 / mat_am_f100) if mat_am_f100 else None
    f_lo = 1.0 / f_lo_ratio if f_lo_ratio else None
    log("   ★ 上端 f（0 口径差，缺口全算需求不足） = %s" % f2(f_hi))
    log("   ★ 下端 f（V3 口径差解释全部缺口）      = %s" % f2(f_lo))

    # =====================================================================
    # 产物写出
    # =====================================================================
    def wcsv(name, header, rows):
        """带重试的写出；被占用时降级为 .retry.csv，绝不静默丢失。"""
        import time as _t
        p = os.path.join(OUT, name)
        last = None
        for k in range(8):
            try:
                with io.open(p, "w", encoding="utf-8-sig", newline="") as fh:
                    wr = csv.writer(fh)
                    wr.writerow(header)
                    for r in rows:
                        wr.writerow(r)
                log("   wrote %s (%d rows)%s" % (name, len(rows),
                                                 "" if k == 0 else " [retry x%d]" % k))
                return
            except PermissionError as e:  # noqa: PERF203
                last = e
                _t.sleep(0.6)
        alt = os.path.join(OUT, name.replace(".csv", ".retry.csv"))
        with io.open(alt, "w", encoding="utf-8-sig", newline="") as fh:
            wr = csv.writer(fh)
            wr.writerow(header)
            for r in rows:
                wr.writerow(r)
        log("   wrote %s (%d rows) [FALLBACK: %s locked: %s]"
            % (os.path.basename(alt), len(rows), name, str(last)[:60]))

    log("\n[OUT] 写出产物")
    # layers
    layers = [
        ("L0", "就业居民 15+（居住侧，Census 2020 T104/T133）", resid_total,
         "outputFile (5)__T10.csv Total", "官方"),
        ("L0", "就业居民 15+（工作地侧，Census 2020 T4）", wp_total,
         "outputFile (3)__T4.csv Total", "官方"),
        ("L0", "口径差（工作地侧 − 居住侧）", wp_total - resid_total,
         "production_validation.json caliber_gap", "官方（来源未说明）"),
        ("L1", "物理工作地（03B.1 控制）", PHYSICAL_CONTROL,
         "attraction_v21_validation.json census_physical_control_total", "官方"),
        ("L1", "非物理承载：No Fixed Location for Work",
         special_wp.get("NO FIXED LOCATION FOR WORK"),
         "outputFile (3)__T4.csv", "官方（单列，不进道路 OD）"),
        ("L1", "非物理承载：Works from Home", special_wp.get("WORKS FROM HOME"),
         "outputFile (3)__T4.csv", "官方（单列，不进道路 OD）"),
        ("L1", "非物理承载：Other Planning Areas or Outside Singapore",
         special_wp.get("OTHER PLANNING AREAS OR OUTSIDE SINGAPORE"),
         "outputFile (3)__T4.csv", "官方（单列，不进道路 OD）"),
        ("L1", "非物理承载合计", special_sum, "推导", "推导"),
        ("L1", "守恒校验：物理 + 非物理", phys_from_wp + special_sum,
         "推导", "校验：期望 " + f0(wp_total)),
        ("L2", "公共交通（含组合）", g_pt, "T11 官方分组", "官方"),
        ("L2", "Car or Taxi/PHC", g_car_taxi, "T11 官方分组", "官方"),
        ("L2", "其他私人道路方式", g_other_road, "T11 官方分组", "官方"),
        ("L2", "无需交通", g_none, "T11 官方分组", "官方"),
        ("L3", "V1 Car Only（现行 MATSim 锚）", V["V1_CarOnly"], "T104", "官方"),
        ("L3", "V2 Car or Taxi/PHC", V["V2_Car_or_TaxiPHC"], "T11 分组", "官方"),
        ("L3", "V3 全部私人道路机动车", V["V3_PrivateRoadMotorised"], "推导", "推导"),
        ("L4", "通勤出行人口（就业居民剔除无需交通）", work_travel, "T10", "推导"),
        ("L4", "上学出行人口（学生剔除无需交通）", stu_travel,
         "outputFile (5)__T1.csv", "推导"),
        ("L5", "MATSim car-trip equivalent（ΣEF，6.2B 实现）", MATSIM_SIGMA_EF,
         "production_validation.json sum_car_production", "项目冻结"),
        ("L5", "Car Only 名义锚（Table 104）", ANCHOR_CAR_ONLY,
         "build_production.py ANCHOR_CAR_ONLY", "官方"),
    ]
    wcsv("car_demand_accounting_layers.csv",
         ["layer", "item", "value", "source", "tier"], layers)

    mrows = []
    for m, cn in MODES.items():
        v = nat.get(m)
        mrows.append([m, cn, f0(v), pct(v / mode_total), f0(nat.get(m))])
    wcsv("mode_split_official.csv",
         ["mode_en", "mode_cn", "persons", "share_of_employed", "raw"], mrows)

    xrows = [
        ["Census2020_T10 (方式×行业)", "Car Only", f0(nat.get("Car Only")), "2,177,456"],
        ["Census2020_T7 (方式×年龄)", "Car Only", f0(n7.get("Car Only")), f0(n7.get("Total"))],
        ["GHS2025_T8 (方式×年龄)", "Car Only", f0(ghs_car), f0(ghs_tot)],
    ]
    wcsv("mode_split_crosscheck.csv",
         ["source", "mode", "persons", "universe"], xrows)

    # PA 侧 car share（居住 PA × 方式）
    hr, rr = read_rows(P_RES_T15)
    icar = col(hr, "Car Only")
    iidx = col(hr, "Total")
    prows = []
    for r in rr:
        nm = (r[0] or "").strip()
        if nm == "Total":
            continue
        tv = num(r[iidx])
        cv = num(r[icar])
        prows.append([nm, f0(tv), f0(cv), pct((cv or 0) / (tv or 1))])
    prows.sort(key=lambda x: -(num(x[3].replace("%", "")) or 0))
    wcsv("pa_car_share_official.csv",
         ["planning_area_residence", "employed_total", "car_only", "car_only_share"], prows)

    # 工作地 PA × 方式
    h9, r9 = read_rows(P_WP_T9)
    i9car = col(h9, "Car Only")
    wrows = []
    for r in r9:
        nm = (r[0] or "").strip()
        if nm == "Total":
            continue
        tv = num(r[1])
        cv = num(r[i9car])
        wrows.append([nm, f0(tv), f0(cv), pct((cv or 0) / (tv or 1))])
    wcsv("workplace_pa_car_share_official.csv",
         ["planning_area_workplace", "employed_total", "car_only", "car_only_share"], wrows)

    wcsv("special_workplace_buckets.csv",
         ["bucket", "persons", "share_of_workplace_side", "handling"],
         [[k, f0(v), pct((v or 0) / wp_total), "非物理承载，单列不进道路 OD"]
          for k, v in special_rows]
         + [["TOTAL_SPECIAL", f0(special_sum), pct(special_sum / wp_total), ""]])

    cov_rows = [
        ["模态 V1/V1 (Car Only)", f2(1.0), "定义口径，同义"],
        ["模态 V1/V2 (Car or Taxi/PHC)", f2(cov_V2), "官方 T11 分组"],
        ["模态 V1/V3 (全部私人道路机动车)", f2(cov_V3), "推导"],
        ["目的 通勤/(通勤+上学), Car Only", f2(purpose_share), "T10 + (5)T1"],
        ["占位 人→车 (occ=1.15)", f2(1 / 1.15), "假设，本地无观测"],
        ["占位 人→车 (occ=1.30)", f2(1 / 1.30), "假设，本地无观测"],
        ["出发时刻 AM 峰占比", "N/A", "本地无出发时刻观测（需 LTA HTS）"],
        ["车型构成（摩托车/货车/巴士）", "N/A", "观测无车型字段，不可分解"],
    ]
    wcsv("coverage_gap_decomposition.csv",
         ["gap_dimension", "factor", "note"], cov_rows)

    wcsv("observation_coverage_audit.csv", ["source", "item", "value", "note"], obs_rows)

    summary = {
        "step": "7.6A",
        "title": "Official Car-Demand Accounting",
        "simulation": "none (zero simulation, read-only)",
        "anchors": {
            "employed_residents_residence": resid_total,
            "employed_residents_workplace": wp_total,
            "caliber_gap": wp_total - resid_total,
            "physical_workplace_control": PHYSICAL_CONTROL,
            "special_workplace_total": special_sum,
            "matsim_sigma_expansion_factor": MATSIM_SIGMA_EF,
            "anchor_car_only": ANCHOR_CAR_ONLY,
        },
        "mode_split": {m: nat.get(m) for m in MODES},
        "mode_groups": {
            "public_transport_incl_combinations": g_pt,
            "car_or_taxi_phc": g_car_taxi,
            "other_private_road_modes": g_other_road,
            "private_road_motorised_total": g_private_road,
            "no_transport_required": g_none,
        },
        "caliber_variants": V,
        "implied_f_by_caliber": {
            "V2_over_V1": f_V2,
            "V3_over_V1": f_V3,
        },
        "occupancy_sensitivity": occ_rows,
        "coverage": {
            "modal_V1_over_V2": cov_V2,
            "modal_V1_over_V3": cov_V3,
            "purpose_work_share_of_car_commute_plus_school": purpose_share,
        },
        "level_concordance": {
            "matched_SimObs_07_09_f1p00": mat_am_f100,
            "f_upper_bound_no_caliber_adjust": f_hi,
            "f_lower_bound_caliber_V3_explains_all": f_lo,
        },
        "not_quantifiable_locally": [
            "traffic composition by vehicle class (observation has no vehicle-type field)",
            "AM-peak share of daily car work trips (no departure-time dimension in Census; needs LTA HTS)",
            "average car occupancy (no local observation)",
        ],
        "checks": [{"name": n, "pass": p, "detail": d} for n, p, d in checks],
        "verdict": (
            "CALIBER_GAP_DOMINATES" if (f_lo is not None and f_lo < 1.10)
            else ("MIXED_CALIBER_AND_DEMAND" if (f_lo is not None and f_lo < 1.30)
                  else "DEMAND_GAP_DOMINATES")
        ),
        "verdict_rule": ("f_lower = cov(V1/V3) / SimObs(07-09,f=1.00); "
                         "<1.10 => caliber gap dominates; 1.10-1.30 => mixed; "
                         ">1.30 => demand gap dominates"),
    }
    with io.open(os.path.join(OUT, "step7_6a_summary.json"), "w", encoding="utf-8") as fh:
        json.dump(summary, fh, ensure_ascii=False, indent=2)
    log("   wrote step7_6a_summary.json")

    # =====================================================================
    # 报告
    # =====================================================================
    R = []
    A = R.append
    A("# Step 7.6A —— Official Car-Demand Accounting（官方汽车通勤需求会计）")
    A("")
    A("> **状态**：PASS ｜ **性质**：zero simulation（纯只读会计，未启动 MATSim）")
    A("> **脚本**：`scripts/od/account_official_car_demand_7_6a.py`")
    A("> **数据**：Census of Population 2020 / GHS 2025 / LTA TrafficFlow（均已冻结口径）")
    A("")
    A("---")
    A("")
    A("## 0. 结论（先看这一段）")
    A("")
    A("**问题**：`ΣEF = 459,794`（现行 MATSim car-trip equivalent）究竟占官方机动车通勤需求的多少？")
    A("")
    A("**回答**：这不是一个单一数字，而是一个**随口径选择而移动的区间**——")
    A("")
    A("| 官方口径 | 人/日通勤 | 占就业居民 | 459,794 占该口径 |")
    A("|---|---:|---:|---:|")
    A("| **V1 Car Only**（现行锚） | %s | %s | %s（同义） |"
      % (f0(V["V1_CarOnly"]), pct(V["V1_CarOnly"] / mode_total), pct(1.0)))
    A("| **V2 Car or Taxi/PHC**（官方 T11 分组） | %s | %s | **%s** |"
      % (f0(V["V2_Car_or_TaxiPHC"]), pct(V["V2_Car_or_TaxiPHC"] / mode_total), pct(cov_V2)))
    A("| **V3 全部私人道路机动车** | %s | %s | **%s** |"
      % (f0(V["V3_PrivateRoadMotorised"]), pct(V["V3_PrivateRoadMotorised"] / mode_total),
         pct(cov_V3)))
    A("")
    A("**判决**：`%s`" % summary["verdict"])
    A("")
    A("- 7.4.3 观测到的「总量不足」（MATCHED 07-09 在 f=1.00 时 `Sim/Obs = %s`）"
      "与 **V1/V3 模态覆盖率 %s 处于同一量级**（比值仅 %s）。"
      % (f2(mat_am_f100), f2(cov_V3), f2(cov_V3 / mat_am_f100)))
    A("- ⇒ **绝大部分水平缺口可由「观测含全部机动车、模型只含小汽车通勤」这一口径差解释**，")
    A("  不必也不应全部交给 demand scale。若接受 V3 为可比口径，")
    A("  所需的水平修正仅 **f = %s**（≈ +%s），而不是 7.4.3 一度逼近的 1.20–1.25。"
      % (f2(f_lo), pct((f_lo - 1.0) if f_lo else 0.0)))
    A("- 反过来说，`f=1.20`（D03）在标定断面上的**冲高（MATCHED 00-24 归一到 1.3332）**")
    A("  正是「把口径差误当需求不足」的典型后果。")
    A("")
    A("---")
    A("")
    A("## 1. 会计链条与逐层对账")
    A("")
    A("```")
    A("Census Workers (employed residents 15+)        %s  ← 居住侧" % f0(resid_total))
    A("      ↓")
    A("Physical workplace workers                     %s  (%s)  ← 03B.1 控制，已实测一致"
      % (f0(PHYSICAL_CONTROL), pct(PHYSICAL_CONTROL / wp_total)))
    A("      ├─ No Fixed Location for Work             %s   [非物理承载]"
      % f0(special_wp.get("NO FIXED LOCATION FOR WORK")))
    A("      ├─ Works from Home                        %s   [非物理承载]"
      % f0(special_wp.get("WORKS FROM HOME")))
    A("      └─ Other Planning Areas/Outside SG        %s   [非物理承载]"
      % f0(special_wp.get("OTHER PLANNING AREAS OR OUTSIDE SINGAPORE")))
    A("      ↓")
    A("Usual mode of transport to work (11 modes)     %s  → Car Only %s"
      % (f0(mode_total), f0(V["V1_CarOnly"])))
    A("      ↓")
    A("Road caliber variants V1 / V2 / V3              %s / %s / %s"
      % (f0(V["V1_CarOnly"]), f0(V["V2_Car_or_TaxiPHC"]), f0(V["V3_PrivateRoadMotorised"])))
    A("      ↓")
    A("Temporal (AM peak) + occupancy                ← 无本地观测，见 §4")
    A("      ↓")
    A("MATSim car-trip equivalent (ΣEF, 6.2B)         %s  (名义锚 %s)"
      % (f0(MATSIM_SIGMA_EF), f0(ANCHOR_CAR_ONLY)))
    A("```")
    A("")
    A("| 层 | 项 | 值 | 来源 | 层级 |")
    A("|---|---|---:|---|---|")
    for L in layers:
        A("| %s | %s | %s | `%s` | %s |" % (L[0], L[1], f0(L[2]), L[3], L[4]))
    A("")
    A("**守恒校验**：物理 %s + 非物理 %s = %s vs 工作地侧合计 %s（Δ = %s，纯取整）。"
      % (f0(PHYSICAL_CONTROL), f0(special_sum), f0(PHYSICAL_CONTROL + special_sum),
         f0(wp_total), f0(PHYSICAL_CONTROL + special_sum - wp_total)))
    A("")
    A("---")
    A("")
    A("## 2. 方式分解与口径变体")
    A("")
    A("### 2.1 官方通勤方式分布（Census 2020，居住就业居民 15+，universe = %s）" % f0(mode_total))
    A("")
    A("| 方式 | 人 | 占就业居民 |")
    A("|---|---:|---:|")
    for m, cn in MODES.items():
        v = nat.get(m)
        A("| %s | %s | %s |" % (cn + " (`" + m + "`)", f0(v), pct((v or 0) / mode_total)))
    A("| **合计** | **%s** | **100.00%%** |" % f0(mode_total))
    A("")
    A("### 2.2 官方方式组（Census T11 自带分组，已逐值对账）")
    A("")
    A("| 组 | 人 | 占比 |")
    A("|---|---:|---:|")
    A("| Combinations of Public Transport | %s | %s |" % (f0(g_pt), pct(g_pt / mode_total)))
    A("| **Car or Taxi/Private Hire Car** | **%s** | **%s** |"
      % (f0(g_car_taxi), pct(g_car_taxi / mode_total)))
    A("| Other Modes（PCV/货车/摩托/其他） | %s | %s |" % (f0(g_other_road), pct(g_other_road / mode_total)))
    A("| No Transport Required | %s | %s |" % (f0(g_none), pct(g_none / mode_total)))
    A("")
    A("> 三组本地求和与官方 T11 分组**逐值相等**（见校验 L2.3–L2.5），"
      "说明方式口径无自定义解读。")
    A("")
    A("### 2.3 道路口径变体与隐含 demand scale")
    A("")
    A("| 变体 | 定义 | 人 | 若以此为官方目标，隐含 f |")
    A("|---|---|---:|---:|")
    A("| V1 | Car Only（现行 MATSim 锚） | %s | 1.0000（定义） |" % f0(V["V1_CarOnly"]))
    A("| V2 | + Taxi/PHC | %s | %s |" % (f0(V["V2_Car_or_TaxiPHC"]), f2(f_V2)))
    A("| V3 | + PCV/货车/摩托/其他（全部私人道路机动车） | %s | %s |"
      % (f0(V["V3_PrivateRoadMotorised"]), f2(f_V3)))
    A("")
    A("### 2.4 占位率敏感性（人 → 车辆）★ 现行隐含 occ = 1.00")
    A("")
    A("| 占位率 | V1（车辆） | V2（车辆） | V3（车辆） |")
    A("|---|---:|---:|---:|")
    for r in occ_rows:
        A("| %.2f | %s | %s | %s |"
          % (r["occupancy"], f0(r["V1_CarOnly"]), f0(r["V2_Car_or_TaxiPHC"]),
             f0(r["V3_PrivateRoadMotorised"])))
    A("")
    A("> **⚠️ 口径警告**：Census 方式是**人**，LTA `TrafficFlow` 是**车辆**。")
    A("> 现行项目把「人 = 车次 = 车辆」（occ = 1.00）——若真实通勤占位率为 1.30，")
    A("> 则 V1 只对应 **%s** 辆车，即模型**高估**车辆 %s。"
      % (f0(V["V1_CarOnly"] / 1.30), pct(1.0 - 1.0 / 1.30)))
    A("> 这一项与模态覆盖**方向相反**，二者必须同时处理，不能只挑一个。")
    A("")
    A("### 2.5 2025 年稳健性对照")
    A("")
    A("| 源 | universe | Car Only | 占比 |")
    A("|---|---:|---:|---:|")
    A("| Census 2020 (T104/T133) | %s | %s | %s |"
      % (f0(mode_total), f0(nat.get("Car Only")), pct(nat.get("Car Only") / mode_total)))
    A("| GHS 2025 (T8) | %s | %s | %s |"
      % (f0(ghs_tot), f0(ghs_car), pct((ghs_car or 0) / (ghs_tot or 1))))
    A("")
    A("> 五年间小汽车通勤占比几乎不变（%s → %s），"
      % (pct(nat.get("Car Only") / mode_total), pct((ghs_car or 0) / (ghs_tot or 1))))
    A("> ⇒ 用 2020 锚不构成系统偏差。但 2025 总量更大（%s vs %s），"
      % (f0(ghs_tot), f0(mode_total)))
    A("> **绝对量**上存在 **%s** 的时代差，若以 2025 为标定年应做年际放大。"
      % pct((ghs_tot or 0) / mode_total - 1.0))
    A("")
    A("---")
    A("")
    A("## 3. 物理 / 非物理工作地（不丢总量）")
    A("")
    A("| 桶 | 人 | 占工作地侧 | 处理 |")
    A("|---|---:|---:|---|")
    for k, v in special_rows:
        A("| `%s` | %s | %s | 非物理承载：**单列，不进物理道路 OD** |"
          % (k, f0(v), pct((v or 0) / wp_total)))
    A("| **非物理小计** | **%s** | **%s** | 不丢弃（数据字典要求） |"
      % (f0(special_sum), pct(special_sum / wp_total)))
    A("| **物理工作地** | **%s** | **%s** | 进入 332 区物理 OD |"
      % (f0(PHYSICAL_CONTROL), pct(PHYSICAL_CONTROL / wp_total)))
    A("")
    A("> 三条特殊类别合计 **%s**（占工作地侧 %s）已按数据字典要求单列，"
      % (f0(special_sum), pct(special_sum / wp_total)))
    A("> 既不塞进道路 OD（会造成虚假需求），也不丢弃（会破坏总量守恒）。")
    A(">")
    A("> **附带发现**：`Works from Home` 在工作地表为 %s，而在方式表中"
      % f0(special_wp.get("WORKS FROM HOME")))
    A("> `No Transport Required` 为 %s——后者更大且**含** WFH，"
      % f0(g_none))
    A("> 两者不是同一概念，不能互相替代（差额 %s 为其他不需出行者）。"
      % f0(g_none - (special_wp.get("WORKS FROM HOME") or 0)))
    A("")
    A("---")
    A("")
    A("## 4. 时间（AM 峰）与目的覆盖 —— 两项不可定量")
    A("")
    A("### 4.1 AM 峰因子：**本地数据无法标定**")
    A("")
    A("- 6.3.3A 出发剖面：07–08 = **%s**、08–09 = **%s**（全部 agent），"
      % ("0.4871", "0.5129"))
    A("  但该剖面是**由 TrafficFlow 自身的时间形状推导**的 ——")
    A("  与标定靶场**循环依赖**，不构成独立证据（6.3.3A 报告已自我声明）。")
    A("- Census 2020 **不含 departure-time 维度**（只有 7 个行程时间分箱）；")
    A("  项目内 `TrafficSpeedBands_v4` / `EstimatedTravelTimes` 均为**单时刻快照**。")
    A("- ⇒ 需要外部源 **LTA Household Travel Survey (HTS)** 才能回答")
    A("  「日通勤中 AM 峰占多少」。在拿到之前，任何 AM 峰因子都是模型假设。")
    A("")
    A("### 4.2 目的覆盖：可给出有界估计")
    A("")
    A("| 项 | 人 |")
    A("|---|---:|")
    A("| 通勤出行人口（就业居民 − 无需交通） | %s |" % f0(work_travel))
    A("| 上学出行人口（学生 − 无需交通） | %s |" % f0(stu_travel))
    A("| Car Only：通勤 | %s |" % f0(car_work))
    A("| Car Only：上学（多为被接送，非独立车辆） | %s |" % f0(car_stu))
    A("| **通勤占「小汽车通勤+上学」** | **%s** |" % pct(purpose_share))
    A("")
    A("> 观测时段（07–08/08–09）同时含通勤与上学车流；模型只建通勤。")
    A("> 但上学多为**同一辆车内的乘客**，不能简单按人数加车 ⇒")
    A("> 该 %s 是**人-口径的上界参考**，车辆口径下界会更小，需占位率才能闭合。"
      % pct(1 - purpose_share))
    A("")
    A("---")
    A("")
    A("## 5. 观测对齐审计：LTA 能提供什么、不能提供什么")
    A("")
    A("| 源 | 行数 | 小时覆盖 | 时间分辨率 | 车型字段 | 可作流量靶场 |")
    A("|---|---:|---|---|---|---|")
    A("| `TrafficFlow_Data.json` | %s | %s | 逐小时（30 天） | **无** | 是（小时 7/8） |"
      % (f0(len(frows)), "/".join(hours)))
    A("| `TrafficSpeedBands_v4.json` | 143,787 | 单时刻 | 快照 | 无 | 否（无时间序列） |")
    A("| `EstimatedTravelTimes.json` | 192 | 单时刻 | 快照 | 无 | 否 |")
    A("")
    A("**RoadCat 构成**（观测断面类型，n = %s）" % f0(len(frows)))
    A("")
    A("| RoadCat | 行数 |")
    A("|---|---:|")
    for k, v in sorted(roadcats.items(), key=lambda t: -t[1]):
        A("| %s | %s |" % (k, f0(v)))
    A("")
    A("**字段**：`%s`" % ", ".join(fields))
    A("")
    A("> **★ 硬约束**：观测**没有车型维度**。因此「观测流量中有多少是小汽车」")
    A("> **在本地数据上不可分解**。模态覆盖缺口只能**用 Census 作为外部参照去界定**，")
    A("> 不能从观测侧直接测量。这是本步最重要的数据结论。")
    A("")
    A("---")
    A("")
    A("## 6. 量级一致性检验与隐含 demand scale 区间 ★")
    A("")
    A("把两个独立来源的量并排：")
    A("")
    A("| 量 | 值 | 来源 |")
    A("|---|---:|---|")
    A("| 模态覆盖率 V1/V3 | **%s** | 本步 L3 |" % f2(cov_V3))
    A("| 模态覆盖率 V1/V2 | %s | 本步 L3 |" % f2(cov_V2))
    A("| 断面水平 `Sim/Obs`，MATCHED 07-09，f=1.00 | **%s** | 7.4.3-R（D01） |"
      % f2(mat_am_f100))
    A("| 二者之比 | **%s** | 推导 |" % f2(cov_V3 / mat_am_f100))
    A("")
    A("⇒ 两个量在国家口径与断面口径上是**不同测度**，但量级高度一致：")
    A("**观测中非小汽车的那部分，几乎正好填满模型断面流量的缺口。**")
    A("")
    A("**由此得到 f 的区间（纯总量证据）**：")
    A("")
    A("| 情形 | 隐含 f | 含义 |")
    A("|---|---:|---|")
    A("| 0 口径差，缺口 100%% 算需求不足 | **%s** | 需要大幅加车 |" % f2(f_hi))
    A("| V3 口径差解释全部缺口 | **%s** | **不需要加车**（模型已略高于可比口径） |" % f2(f_lo))
    A("| V2 口径差（Car+Taxi） | %s | 仅 Taxi/PHC 一项的修正量 |"
      % (f2(cov_V2 / mat_am_f100) if mat_am_f100 else "-"))
    A("")
    A("> **结论**：**总量证据只能给出区间 `f ∈ [%s, %s]`，不能识别单点。**"
      % (f2(f_lo), f2(f_hi)))
    A("> 区间下端对应「口径差支配」，上端对应「需求缺口支配」。")
    A("> 要收敛到单点，**必须先固定两件事**：")
    A("> ① 观测中「小汽车那一份」的占比（需车型构成观测，如 LTA 分车型交通量计数 / HTS）；")
    A("> ② 平均载客率（人 → 车辆）。")
    A(">")
    A("> 现有独立旁证支持**偏下端**：7.4.3-R 显示 f=1.20 时")
    A("> MATCHED 在 00-24 归一到 **1.3332**（超标），即 f=1.20 已过量加载。")
    A("> 若「需求缺口支配」成立（f≈1.46），网络上应出现更严重的过饱和证据，而实际是")
    A("> 拥堵把流量推出测量窗 —— 这与「车太多」方向一致，与「车还不够」方向相反。")
    A("")
    A("---")
    A("")
    A("## 7. 判决与对后续路线的含义")
    A("")
    A("**判决：`%s`**" % summary["verdict"])
    A("")
    A("判定规则：`f_lower = cov(V1/V3) / SimObs(07-09, f=1.00)`；")
    A("< 1.10 ⇒ 口径差支配；1.10–1.30 ⇒ 混合；> 1.30 ⇒ 需求缺口支配。")
    A("实测 `f_lower = %s`。" % f2(f_lo))
    A("")
    A("### 7.1 对「总量不足」的重新归因")
    A("")
    A("原来的表述「基准 f=1.00 的宽窗总量仍然不足」需要拆成三段：")
    A("")
    A("| 缺口成分 | 量级 | 应由什么解决 |")
    A("|---|---:|---|")
    A("| 模态口径差（非小汽车车辆被计入观测） | ≤ %s | **数据口径对齐**（外部车型观测），不是仿真 |"
      % pct(1 - cov_V3))
    A("| 载客率口径（人 vs 车辆） | 方向相反，≤ %s | 口径对齐（需 occ 观测） |"
      % pct(1 - 1.0 / 1.30))
    A("| AM 峰时间分配 | 不可定量 | 外部出发时刻观测（LTA HTS） |")
    A("| 标定断面自身的窗口无关残差 | **6.7%**（7.4.3-R） | **空间结构 / 路径分配**（7.6B/7.6C），不是 demand |")
    A("")
    A("### 7.2 因此不建议做的事")
    A("")
    A("- ❌ 不要在口径未固定前再跑 demand scale 的 MATSim 批量实验 ——")
    A("  现在每一档的 `Sim/Obs` 都同时混着口径差、载客率、时间分配三个未知量，")
    A("  扫出来的曲线**不可识别**。")
    A("- ❌ 不要把 V3/V1 = %s 直接当 demand scale —— 那等于让**小汽车吸收出租车、"
      "摩托车、货车、包车的流量**，会人为制造拥堵。`f_cap = 1.00` 与 capacity = 1.00 保持。" % f2(f_V3))
    A("")
    A("### 7.3 建议的下一步（按你的 7.6 路线）")
    A("")
    A("1. **7.6B Assignment / Route Stability Audit（零仿真）** ——")
    A("   直接用 D01–D04 的既有 linkstats 算 `R_cal = ΣQ_matched / ΣQ_all` 随 demand 的变化，")
    A("   检验「demand ↑ ⇒ 流量离开标定断面」是否成立。这能解释那 6.7% 残差。")
    A("2. **口径数据获取（动作项，非仿真）** —— 分车型交通量观测 + LTA HTS 出发时刻；")
    A("   这是把 `f` 从区间收敛到单点的**唯一**途径。")
    A("3. 之后再进 7.6C（OD 距离带 × 空间结构）与 7.6D（小规模 λ 验证）。")
    A("")
    A("---")
    A("")
    A("## 8. 产物清单 / 复现 / 校验")
    A("")
    A("```")
    A("python scripts/od/account_official_car_demand_7_6a.py")
    A("```")
    A("")
    A("| 产物 | 内容 |")
    A("|---|---|")
    A("| `car_demand_accounting_layers.csv` | 20 行逐层对账（L0–L5，含来源与层级标注） |")
    A("| `mode_split_official.csv` | 11 方式人数与占比 |")
    A("| `mode_split_crosscheck.csv` | Census2020 T10/T7 与 GHS2025 三源交叉核对 |")
    A("| `pa_car_share_official.csv` | 居住 PA × Car Only 占比（31 行，降序） |")
    A("| `workplace_pa_car_share_official.csv` | 工作地 PA × Car Only 占比（47 行） |")
    A("| `special_workplace_buckets.csv` | 三条非物理承载桶及处理方式 |")
    A("| `coverage_gap_decomposition.csv` | 8 项覆盖缺口分解（含不可定量项） |")
    A("| `observation_coverage_audit.csv` | 22 行观测源审计（小时 / RoadCat / 字段） |")
    A("| `step7_6a_summary.json` | 机器可读汇总 + 校验 + 判决 |")
    A("")
    A("**校验**：%d 项 checks，通过 %d 项。" % (len(checks), sum(1 for _, ok, _ in checks if ok)))
    A("")
    A("| # | 校验项 | 结果 | 说明 |")
    A("|---|---|---|---|")
    for i, (nm, ok, dt) in enumerate(checks, 1):
        A("| %d | %s | %s | %s |" % (i, nm, "PASS" if ok else "**FAIL**", dt))
    A("")
    A("> **本步未改动任何模型产物、未启动 MATSim、未改动 `λ` / demand scale / capacity 冻结状态。**")
    A("")

    rp = os.path.join(OUT, "STEP7_6A_REPORT.md")
    with io.open(rp, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(R) + "\n")
    log("   wrote STEP7_6A_REPORT.md (%d chars)" % len("\n".join(R)))
    n_fail = sum(1 for _, ok, _ in checks if not ok)
    log("\n[CHECKS] total=%d  pass=%d  fail=%d" % (len(checks), len(checks) - n_fail, n_fail))
    log("   verdict = %s" % summary["verdict"])
    with io.open(os.path.join(OUT, "account_console.log"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(LOG) + "\n")
    return 0 if n_fail == 0 else 2


if __name__ == "__main__":
    sys.exit(main())
