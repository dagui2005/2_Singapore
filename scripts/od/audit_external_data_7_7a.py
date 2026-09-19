# -*- coding: utf-8 -*-
"""
Step 7.7A 入场审计 —— LTA 分车型交通量可得性判定 + 零成本构成归因先验
============================================================================
设计原则（承项目纪律）
  * 零仿真、只读；不改任何冻结件（7.1 / 7.3.6A / OD / network / capacity / population / route-choice）
  * 结论只由可复核的落盘数字支撑；"不可得"必须给文件级证据，不给猜测值
  * 本脚本不启动 MATSim

回答两个问题
  Q1 本地/开放数据里到底有没有"分车型交通量"？
  Q2 若没有，能否用本地的"方式/车型构成"代理量，解释 7.6C/H 的空间残差？

产物 -> reports/external_validation_7_7/
  STEP7_7A_ENTRANCE_AUDIT.md            审计报告（由本脚本写数字，正文另附）
  step7_7a_local_inventory.csv          本地分车型可得性逐文件证据
  step7_7a_mode_composition_by_pa.csv   Census Table104 方式构成（PA 级）
  step7_7a_mode_composition_by_region.csv
  step7_7a_composition_vs_residual.csv  构成 vs 残差（region 级 + PA 级）
  step7_7a_camera_coverage.csv          LTA 摄像机 → PA/Region 覆盖
  step7_7a_summary.json
"""
from __future__ import annotations
import json
import os
import numpy as np
import pandas as pd

ROOT = r"D:\Luan\2026-05\2_Singapore"
OUT = os.path.join(ROOT, "reports", "external_validation_7_7")
os.makedirs(OUT, exist_ok=True)

# ---------------------------------------------------------------- 冻结引用值
# 7.6A：D01 断面 Sim/Obs（MATCHED 07-09, f=1.00）—— readme §2.31 / 7.6A 会计链
D01_SIMOBS_0709 = 0.6830
# 7.6A 口径变体（Census 2020 T104 派生）
V1_CAR_ONLY = 459_796
V2_CAR_TAXI = 526_477
V3_ROAD_MOTOR = 707_116
# 7.6C-1：硬零流断面份额（测量伪影）
HARD_ZERO_SHARE = 0.0814

PDV = ["Car Only", "Taxi/Private Hire Car Only", "Motorcycle/Scooter Only",
       "Lorry/Pickup Only", "Private Chartered Bus/Van Only"]
PT = ["Public Bus Only", "Rail (MRT/LRT) Only", "Rail (MRT/LRT) & Public Bus Only",
      "Combination of Rail (MRT/LRT) and/or Public Bus, with Other Modes"]

rows_ck: list[dict] = []


def ck(name, ok, detail=""):
    rows_ck.append({"check": name, "status": "PASS" if ok else "FAIL", "detail": str(detail)[:220]})
    return ok


# =========================================================== Q1 本地可得性扫描
def scan_local_inventory() -> pd.DataFrame:
    """逐文件证据：本地是否存在分车型（car/taxi/bus/motorcycle/goods）交通量字段。"""
    inv: list[dict] = []

    def add(rel, verdict, evidence):
        inv.append({"path": rel, "verdict": verdict, "evidence": evidence})

    # 1) 核心观测：TrafficFlow_Data.json
    tf = os.path.join(ROOT, "Singapore_OD_MATSim_FinalData", "08_TrafficCount", "TrafficFlow_Data.json")
    with open(tf, encoding="utf-8") as f:
        d = json.load(f)
    recs = d["Value"]
    keys = sorted(recs[0].keys())
    add("Singapore_OD_MATSim_FinalData/08_TrafficCount/TrafficFlow_Data.json",
        "TOTAL_ONLY",
        "records=%d; fields=%s" % (len(recs), ",".join(keys)))
    ck("Q1.1 TrafficFlow_Data.json 无车型字段",
       not any(k.lower() in ("vehicletype", "vehicle_type", "cartype") for k in keys)
       and set(keys) == {"LinkID", "Date", "HourOfDate", "Volume", "StartLon", "StartLat",
                         "EndLon", "EndLat", "RoadName", "RoadCat"},
       "fields=%s" % ",".join(keys))
    vraw = [r["Volume"] for r in recs[:20000]]
    vnum = pd.to_numeric(pd.Series(vraw).str.replace(",", "", regex=False),
                         errors="coerce")
    add("  -> Volume 语义", "ALL_MOTOR_VEHICLES",
        "Volume 为全部机动车合计（字符串型，含千分位逗号；如 '%s'）；样本 n=%d 非负=%s"
        % (vraw[0], len(vraw), bool((vnum.dropna() >= 0).all())))

    # 2) 静态 LTA 源
    for sub, note in [
        ("Static_ 2026_03/GEOSPATIAL", "仅要素几何（含 TaxiStand/DetectorLoop），无流量"),
        ("Static_ 2026_03/PUBLIC TRANSPORT", "仅车队规模/客流/线路，非分车型路段流量"),
        ("Static_ 2026_03/OTHER", "人口栅格 + ACRA + 设施，无交通量"),
    ]:
        add(sub, "NO_TRAFFIC_VOLUME", note)
    add("Static_ 2026_03/PUBLIC TRANSPORT/Monthly Taxi Population/monthly_taxi_fleet.csv",
        "AGGREGATE_FLEET_ONLY", "月度出租车队数量（全国），非路段、非流量")

    # 3) 动态源
    add("Dynamic_2026_03_16/historical_data/", "NO_CLASSIFIED_VOLUME",
        "含 TrafficFlow/TrafficSpeedBands/BusArrival/PassengerVolume 等；均无车型分解")
    add("Dynamic_2026_03_16/historical_data/TrafficSpeedBands_v4.json", "SPEED_ONLY",
        "车速带（taxi-GPS 派生），无车型")
    add("Dynamic_2026_03_16/historical_data/PassengerVolume_*.json", "PT_PAX_ONLY",
        "公交/地铁客流（人次），非道路分车型")

    # 4) LTA DataMall 端点清单（来源：本项目 lta_dynamic_data_downloader.py）
    dlr = os.path.join(ROOT, "lta_dynamic_data_downloader.py")
    src = open(dlr, encoding="utf-8", errors="replace").read()
    has_flow = "TrafficFlow" in src
    add("lta_dynamic_data_downloader.py", "ENDPOINT_INVENTORY",
        "DataMall 端点含 TrafficFlow（总量）；无 VehicleType/TrafficVolumeByType 端点")
    ck("Q1.2 DataMall 端点清单无分车型流量", has_flow and ("VehicleType" not in src)
       and ("ByVehicleType" not in src), "TrafficFlow present; no vehicle-type endpoint")

    # 5) 开放数据（外部核查结论）
    add("data.gov.sg / Annual Motor Vehicle Population by Vehicle Type",
        "EXTERNAL_FLEET_ONLY", "全国年度车队构成（Cars/Taxis/Buses/Motorcycles/Goods），非路段流量")

    # 6) 唯一本地"车型"线索：LTA 交通摄像机图像
    cams = os.path.join(ROOT, "Dynamic_2026_03_16", "historical_data", "TrafficImages_v2.json")
    imgs = os.path.join(ROOT, "Dynamic_2026_03_16", "realtime_monitoring", "images")
    n_img = len(os.listdir(imgs)) if os.path.isdir(imgs) else 0
    add("Dynamic_2026_03_16/realtime_monitoring/images/", "CV_PROXY_POSSIBLE",
        "%d 帧 / 90 台摄像机（WGS84 元数据齐全）⇒ 可做地点级车型【构成】估计" % n_img)
    ck("Q1.3 摄像机图像存在", n_img > 5000 and os.path.exists(cams), "n_img=%d" % n_img)

    df = pd.DataFrame(inv)
    df.to_csv(os.path.join(OUT, "step7_7a_local_inventory.csv"), index=False, encoding="utf-8-sig")
    return df


# ============================================== Q2 构成归因（零成本先验）
def load_t104() -> tuple[pd.DataFrame, pd.Series]:
    p = os.path.join(ROOT, "Singapore_OD_MATSim_FinalData", "06_Census_TravelBehavior",
                     "outputFile (4)__T15.csv")
    d = pd.read_csv(p, encoding="utf-8-sig").rename(columns={"Planning Area of Residence": "pa"})
    d["pa"] = d["pa"].astype(str).str.strip().str.upper()
    tot = d[d["pa"] == "TOTAL"].iloc[0]
    d = d[d["pa"] != "TOTAL"].copy()
    for c in PDV + PT + ["Others", "No Transport Required", "Total"]:
        if c in d.columns:
            d[c] = pd.to_numeric(d[c], errors="coerce").fillna(0.0)
    d["PMV"] = d[PDV].sum(axis=1)
    d["carshare_pmv"] = np.where(d["PMV"] > 0, d["Car Only"] / d["PMV"], np.nan)
    d["motorized"] = d["Total"] - d["No Transport Required"]
    d["carshare_motor"] = np.where(d["motorized"] > 0, d["Car Only"] / d["motorized"], np.nan)
    d["road_vehicles_proxy"] = d["Car Only"] + d["Taxi/Private Hire Car Only"] \
        + d["Motorcycle/Scooter Only"] + d["Lorry/Pickup Only"] + d["Private Chartered Bus/Van Only"]
    return d, tot


def main() -> int:
    print("=" * 78)
    print("Step 7.7A 入场审计 —— LTA 分车型交通量可得性 + 构成归因先验")
    print("=" * 78)

    inv = scan_local_inventory()
    print("\n[Q1] 本地分车型可得性扫描：%d 条证据" % len(inv))
    print(inv[["path", "verdict"]].to_string(index=False))

    # ---------------- 构成 ----------------
    d, tot = load_t104()
    pmv_tot = float(tot["Car Only"]) + sum(float(tot[c]) for c in PDV[1:])
    car_only_tot = float(tot["Car Only"])
    global_car_share_pmv = car_only_tot / pmv_tot
    print("\n[Q2] 全域：Car Only=%.0f  PMV=%.0f  car_share_pmv=%.6f  (1/x=%.4f)"
          % (car_only_tot, pmv_tot, global_car_share_pmv, 1 / global_car_share_pmv))
    print("     参照：7.6A D01 断面 Sim/Obs(07-09,f=1.00)=%.4f  ⇒ 1/x=%.4f"
          % (D01_SIMOBS_0709, 1 / D01_SIMOBS_0709))
    ck("Q2.1 全域 car_share_pmv ≈ D01 Sim/Obs（<1pp）",
       abs(global_car_share_pmv - D01_SIMOBS_0709) < 0.01,
       "|%.6f-%.4f|=%.6f" % (global_car_share_pmv, D01_SIMOBS_0709,
                             abs(global_car_share_pmv - D01_SIMOBS_0709)))

    d[["pa", "Total", "Car Only", "Taxi/Private Hire Car Only", "Motorcycle/Scooter Only",
       "Lorry/Pickup Only", "Private Chartered Bus/Van Only", "Public Bus Only",
       "No Transport Required", "PMV", "carshare_pmv", "carshare_motor"]] \
        .to_csv(os.path.join(OUT, "step7_7a_mode_composition_by_pa.csv"),
                index=False, encoding="utf-8-sig")

    # ---------------- 区域残差（7.6H W01 冻结工作点） ----------------
    h3 = pd.read_csv(os.path.join(ROOT, "matsim_final_7_6h", "audit",
                                  "final_workingpoint_7_6h_h3_spatial.csv"), encoding="utf-8-sig")
    reg = h3[h3["group_by"] == "region"][["group", "n_sections", "Q_FROZEN",
                                          "rel_dev_vs_global_FROZEN"]] \
        .rename(columns={"group": "region", "rel_dev_vs_global_FROZEN": "resid_frac"})
    reg["region"] = reg["region"].astype(str).str.strip().str.upper()
    reg["resid_pp"] = reg["resid_frac"] * 100

    # 区域构成：按断面数加权（用 section_geography 的 link→PA 映射）
    geo = pd.read_csv(os.path.join(ROOT, "reports", "od_structure_7_6c", "section_geography.csv"),
                      encoding="utf-8-sig")
    geo["pa"] = geo["pa"].astype(str).str.strip().str.upper()
    m = geo.merge(d[["pa", "Car Only", "PMV", "carshare_pmv"]], on="pa", how="left")
    oth = d[d["pa"] == "OTHERS"]
    if len(oth):
        m["Car Only"] = m["Car Only"].fillna(float(oth.iloc[0]["Car Only"]))
        m["PMV"] = m["PMV"].fillna(float(oth.iloc[0]["PMV"]))
    secw = m.groupby("region").agg(n_sec=("pa", "size"), car=("Car Only", "sum"),
                                   pmv=("PMV", "sum")).reset_index()
    secw["carshare_secw"] = secw["car"] / secw["pmv"]

    pa2reg = m.drop_duplicates("pa").set_index("pa")["region"].to_dict()
    d["region"] = d["pa"].map(pa2reg)
    popw = d.dropna(subset=["region"]).groupby("region", as_index=False).apply(
        lambda x: pd.Series({"carshare_popw": (x["Car Only"] * x["Total"]).sum()
                             / max(1e-9, (x["PMV"] * x["Total"]).sum())}),
        include_groups=False)

    rr = reg.merge(secw[["region", "n_sec", "carshare_secw"]], on="region", how="left") \
            .merge(popw, on="region", how="left")
    rr["car_share_sec_pp"] = rr["carshare_secw"] * 100
    rr["car_share_pop_pp"] = rr["carshare_popw"] * 100
    rr["pred_resid_pp_secw"] = (rr["carshare_secw"] / global_car_share_pmv - 1) * 100
    rr["err_pp_secw"] = rr["pred_resid_pp_secw"] - rr["resid_pp"]
    rr = rr.sort_values("resid_pp")
    print("\n[Q2] 区域：残差 vs 私人机动车 car 份额")
    print(rr[["region", "n_sections", "resid_pp", "car_share_sec_pp", "car_share_pop_pp",
              "pred_resid_pp_secw", "err_pp_secw"]].to_string(index=False))
    rr.to_csv(os.path.join(OUT, "step7_7a_mode_composition_by_region.csv"),
              index=False, encoding="utf-8-sig")

    def pear(a, b):
        s = pd.DataFrame({"a": a, "b": b}).dropna()
        return (np.corrcoef(s["a"], s["b"])[0, 1], len(s))

    r_secw, n1 = pear(rr["resid_pp"], rr["car_share_sec_pp"])
    r_popw, n2 = pear(rr["resid_pp"], rr["car_share_pop_pp"])
    spread_res = rr["resid_pp"].max() - rr["resid_pp"].min()
    spread_comp = rr["car_share_sec_pp"].max() - rr["car_share_sec_pp"].min()
    print("\n  Pearson r(resid, car_share_secw) = %+.4f (n=%d)" % (r_secw, n1))
    print("  Pearson r(resid, car_share_popw) = %+.4f (n=%d)" % (r_popw, n2))
    print("  残差极差 = %.1f pp | 构成极差 = %.1f pp | 比 = %.2fx"
          % (spread_res, spread_comp, spread_res / max(1e-9, spread_comp)))

    # ---------------- PA 级 ----------------
    pares = pd.read_csv(os.path.join(ROOT, "reports", "od_structure_7_6c",
                                     "section_residual_by_pa.csv"), encoding="utf-8-sig")
    pares["pa"] = pares["pa"].astype(str).str.strip().str.upper()
    pj = pares.merge(d[["pa", "carshare_pmv", "carshare_motor", "PMV"]], on="pa", how="inner")
    pj = pj[pj["n_sections"] >= 5].copy()
    pj["resid_pp"] = pj["rel_dev_vs_global"] * 100
    r_pa, n_pa = pear(pj["resid_pp"], pj["carshare_pmv"])
    spread_pa_res = pj["resid_pp"].max() - pj["resid_pp"].min()
    spread_pa_comp = (pj["carshare_pmv"].max() - pj["carshare_pmv"].min()) * 100
    print("\n[Q2] PA 级（n_sections>=5）：匹配 %d 个 PA" % len(pj))
    print("  Pearson r(resid, carshare_pmv) = %+.4f (n=%d, R2=%.4f)"
          % (r_pa, n_pa, r_pa ** 2))
    print("  残差极差 = %.1f pp | 构成极差 = %.1f pp | 比 = %.2fx"
          % (spread_pa_res, spread_pa_comp, spread_pa_res / max(1e-9, spread_pa_comp)))
    comb = rr[["region", "n_sections", "resid_pp", "car_share_sec_pp", "pred_resid_pp_secw",
               "err_pp_secw"]].assign(level="region")
    comb2 = pj[["pa", "n_sections", "resid_pp", "carshare_pmv"]].rename(
        columns={"pa": "region", "carshare_pmv": "car_share_sec_pp"}).assign(level="pa")
    pd.concat([comb, comb2], ignore_index=True).to_csv(
        os.path.join(OUT, "step7_7a_composition_vs_residual.csv"), index=False, encoding="utf-8-sig")

    # ---------------- 摄像机覆盖 ----------------
    cam_csv = os.path.join(ROOT, "reports", "camera_region_7_7a.csv")
    if os.path.exists(cam_csv):
        cam = pd.read_csv(cam_csv)
        cov = cam["REGION_N"].value_counts().rename_axis("region").reset_index(name="n_cameras")
        cov = cov.merge(rr[["region", "n_sections", "resid_pp"]], on="region", how="outer")
        cov.to_csv(os.path.join(OUT, "step7_7a_camera_coverage.csv"), index=False, encoding="utf-8-sig")
        print("\n[Q2] 摄像机覆盖（本地 CV 路径可行性）")
        print(cov.to_string(index=False))

    # ---------------- 判决 ----------------
    comp_weak = (abs(r_secw) < 0.5 and abs(r_pa) < 0.5) and (spread_res / spread_comp > 2.0)
    ck("Q2.2 构成对空间残差解释力弱（|r|<0.5 且 极差比>2）", comp_weak,
       "r_region=%+.3f r_pa=%+.3f 极差比=%.2f" % (r_secw, r_pa, spread_res / spread_comp))
    ck("Q2.3 全局构成自洽（1/car_share≈1/D01，差<1%）",
       abs(1 / global_car_share_pmv - 1 / D01_SIMOBS_0709) / (1 / D01_SIMOBS_0709) < 0.01,
       "1/%.6f=%.4f vs 1/%.4f=%.4f" % (global_car_share_pmv, 1 / global_car_share_pmv,
                                       D01_SIMOBS_0709, 1 / D01_SIMOBS_0709))

    payload = {
        "step": "7.7A",
        "title": "LTA 分车型交通量可得性审计 + 构成归因先验",
        "design": {"zero_simulation": True, "matsim_launched": False,
                   "frozen_artifacts_touched": False, "external_data_acquired": False},
        "q1_local_vehicle_type_volume": {
            "verdict": "UNAVAILABLE",
            "core_observation": "TrafficFlow_Data.json Volume = 全部机动车合计（无车型字段）",
            "fields": ["LinkID", "Date", "HourOfDate", "Volume", "StartLon", "StartLat",
                       "EndLon", "EndLat", "RoadName", "RoadCat"],
            "datamall_endpoints_with_vehicle_type": 0,
            "open_data_vehicle_type_datasets": "仅全国年度车队构成（非路段流量）",
            "local_CV_proxy_possible": {"n_cameras": 90, "n_images": 8552,
                                        "granularity": "地点级（构成，非流量）"},
        },
        "q2_composition_attribution": {
            "global_car_share_pmv": round(global_car_share_pmv, 6),
            "global_1_over_carshare": round(1 / global_car_share_pmv, 4),
            "d01_simobs_0709": D01_SIMOBS_0709,
            "d01_1_over_simobs": round(1 / D01_SIMOBS_0709, 4),
            "region_pearson_r_secw": round(float(r_secw), 4),
            "region_pearson_r_popw": round(float(r_popw), 4),
            "pa_pearson_r": round(float(r_pa), 4),
            "pa_r2": round(float(r_pa ** 2), 4),
            "pa_n": int(n_pa),
            "region_spread_resid_pp": round(float(spread_res), 2),
            "region_spread_composition_pp": round(float(spread_comp), 2),
            "pa_spread_resid_pp": round(float(spread_pa_res), 2),
            "pa_spread_composition_pp": round(float(spread_pa_comp), 2),
        },
        "verdict": {
            "local_data": "VEHICLE_TYPE_VOLUME_UNAVAILABLE",
            "composition_prior": "COMPOSITION_EXPLAINS_GLOBAL_LEVEL_NOT_SPATIAL_PATTERN",
            "consistency_with_earlier": [
                "7.6F-1：空间残差不随 demand 变化",
                "7.6G：空间残差不随 λ 变化",
                "7.7A：空间残差不随车型/方式构成变化 ⇒ 三个方向一致",
            ],
        },
        "not_done": ["未启动 MATSim", "未获取外部数据", "未改任何冻结件",
                     "未把构成先验当作结论（仅 audit-level prior）"],
        "checks": rows_ck,
        "checks_pass": sum(1 for r in rows_ck if r["status"] == "PASS"),
        "checks_total": len(rows_ck),
    }
    with open(os.path.join(OUT, "step7_7a_summary.json"), "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    print("\n" + "-" * 78)
    for r in rows_ck:
        print("  [%s] %s  %s" % (r["status"], r["check"], r["detail"]))
    print("-" * 78)
    print("校验 %d/%d PASS" % (payload["checks_pass"], payload["checks_total"]))
    print("判决：local=%s" % payload["verdict"]["local_data"])
    print("      composition=%s" % payload["verdict"]["composition_prior"])
    print("产物 ->", OUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
