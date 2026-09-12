"""
从 TrafficSpeedBands_v4.json 和 TrafficFlow_Data.json 提取静态路网信息，
输出两份 Shapefile（线要素），仅保留：
  LinkID, StartLon, StartLat, EndLon, EndLat, RoadName, RoadCat/RoadCategory
不记录重复 LinkID。
"""

import json
import os
import shapefile  # pyshp

OUTPUT_DIR = "Dynamic_2026_03_16/realtime_monitoring"


def to_float(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def write_shp(records, out_name, road_cat_field):
    """
    records: list of dict，已去重
    out_name: 输出文件路径（不含扩展名）
    road_cat_field: 该 JSON 中道路类别字段名
    """
    w = shapefile.Writer(out_name, shapeType=shapefile.POLYLINE)
    w.field("LinkID",   "C", size=20)
    w.field("RoadName", "C", size=100)
    w.field("RoadCat",  "C", size=20)
    w.field("StartLon", "N", decimal=7)
    w.field("StartLat", "N", decimal=7)
    w.field("EndLon",   "N", decimal=7)
    w.field("EndLat",   "N", decimal=7)

    skipped = 0
    written = 0
    for rec in records:
        slon = to_float(rec.get("StartLon"))
        slat = to_float(rec.get("StartLat"))
        elon = to_float(rec.get("EndLon"))
        elat = to_float(rec.get("EndLat"))
        if None in (slon, slat, elon, elat):
            skipped += 1
            continue

        w.line([[[slon, slat], [elon, elat]]])
        w.record(
            LinkID=str(rec.get("LinkID", "")),
            RoadName=str(rec.get("RoadName", "")),
            RoadCat=str(rec.get(road_cat_field, "")),
            StartLon=slon,
            StartLat=slat,
            EndLon=elon,
            EndLat=elat,
        )
        written += 1

    w.close()

    # 写 .prj (WGS84)
    prj_content = (
        'GEOGCS["GCS_WGS_1984",'
        'DATUM["D_WGS_1984",'
        'SPHEROID["WGS_1984",6378137.0,298.257223563]],'
        'PRIMEM["Greenwich",0.0],'
        'UNIT["Degree",0.0174532925199433]]'
    )
    with open(out_name + ".prj", "w") as f:
        f.write(prj_content)

    print(f"  写入 {written} 条记录，跳过坐标缺失 {skipped} 条")
    print(f"  输出：{out_name}.shp / .dbf / .shx / .prj")


# ─── 1. TrafficSpeedBands_v4.json ───────────────────────────────────────────
print("处理 TrafficSpeedBands_v4.json ...")
with open(os.path.join(OUTPUT_DIR, "TrafficSpeedBands_20260505_080735.json"), encoding="utf-8") as f:
    speed_data = json.load(f)

# 顶层即为列表
speed_list = speed_data if isinstance(speed_data, list) else speed_data.get("value", speed_data.get("Value", []))
print(f"  原始记录数：{len(speed_list)}")

seen = set()
speed_dedup = []
for rec in speed_list:
    lid = str(rec.get("LinkID", ""))
    if lid and lid not in seen:
        seen.add(lid)
        speed_dedup.append(rec)
print(f"  去重后 LinkID 数：{len(speed_dedup)}")

write_shp(
    speed_dedup,
    os.path.join(OUTPUT_DIR, "TrafficSpeedBands_050508_Links"),
    road_cat_field="RoadCategory",
)


# ─── 2. TrafficFlow_Data.json ────────────────────────────────────────────────
print("\n处理 TrafficFlow_Data.json ...")
with open(os.path.join(OUTPUT_DIR, "TrafficFlow_Data_20260505_080737.json"), encoding="utf-8") as f:
    flow_data = json.load(f)

# 顶层 key = "Value"
flow_list = flow_data.get("Value", flow_data.get("value", flow_data if isinstance(flow_data, list) else []))
print(f"  原始记录数：{len(flow_list)}")

seen = set()
flow_dedup = []
for rec in flow_list:
    lid = str(rec.get("LinkID", ""))
    if lid and lid not in seen:
        seen.add(lid)
        flow_dedup.append(rec)
print(f"  去重后 LinkID 数：{len(flow_dedup)}")

write_shp(
    flow_dedup,
    os.path.join(OUTPUT_DIR, "TrafficFlow_050508_Links"),
    road_cat_field="RoadCat",
)

print("\n完成。")
