# -*- coding: utf-8 -*-
"""
Singapore Open Data Feasibility Audit for Traffic Digital Twin

功能：
1. 检查LTA静态路网与车道级地图生成可行性
2. 检查动态交通数据作为流量/速度校准基准的可行性
3. 检查人口、HDB、POI、用地数据用于OD生成的可行性
4. 输出 report.md 和若干中间csv

使用：
python sg_feasibility_audit.py

请根据本地目录修改 CONFIG。
"""

from pathlib import Path
import json
import warnings
warnings.filterwarnings("ignore")

import numpy as np
import pandas as pd
import geopandas as gpd
import networkx as nx

from shapely.geometry import Point, LineString
from shapely.ops import unary_union

try:
    import rasterio
except Exception:
    rasterio = None


# =========================
# 0. 配置区
# =========================

CONFIG = {
    # 注意：文件夹名包含空格 "Static_ 2026_03"
    "static_root": r"./Static_ 2026_03/GEOSPATIAL",  # LTA地理空间数据
    "dynamic_root": r"./Dynamic_2026_03_16",  # 动态交通数据
    "other_root": r"./Static_ 2026_03/OTHER",  # 其他公开数据
    "output_root": r"./sg_feasibility_outputs",

    # 新加坡本地投影，单位米，便于距离/面积计算
    "work_crs": "EPSG:3414",

    # 空间匹配参数，可根据结果调整
    "road_buffer_m": 15,
    "endpoint_signal_search_m": 30,
    "graph_snap_tolerance_m": 5,
}


# =========================
# 1. 通用工具函数
# =========================

def ensure_dir(p):
    Path(p).mkdir(parents=True, exist_ok=True)


def find_files(root, keywords=None, suffixes=None):
    root = Path(root)
    if keywords is None:
        keywords = []
    if suffixes is None:
        suffixes = [".shp", ".geojson", ".json", ".csv", ".tif"]

    out = []
    if not root.exists():
        return out

    for p in root.rglob("*"):
        if not p.is_file():
            continue
        if p.suffix.lower() not in suffixes:
            continue
        name = str(p).lower()
        if all(k.lower() in name for k in keywords):
            out.append(p)
    return sorted(out)


def find_first(root, keywords=None, suffixes=None):
    files = find_files(root, keywords, suffixes)
    return files[0] if files else None


def guess_and_set_crs(gdf):
    """
    如果文件没有CRS，粗略判断：
    - 坐标像经纬度：EPSG:4326
    - 坐标像米制：EPSG:3414
    """
    if gdf.crs is not None:
        return gdf

    bounds = gdf.total_bounds
    minx, miny, maxx, maxy = bounds
    if -180 <= minx <= 180 and -90 <= miny <= 90 and -180 <= maxx <= 180 and -90 <= maxy <= 90:
        gdf = gdf.set_crs("EPSG:4326")
    else:
        gdf = gdf.set_crs("EPSG:3414")
    return gdf


def read_vector(path, work_crs="EPSG:3414"):
    if path is None:
        return None
    gdf = gpd.read_file(path)
    gdf = gdf[~gdf.geometry.isna()].copy()
    gdf = guess_and_set_crs(gdf)
    try:
        gdf = gdf.to_crs(work_crs)
    except Exception as e:
        print(f"[WARN] CRS转换失败: {path}, {e}")
    return gdf


def find_col(df, candidates, contains=True):
    """
    在DataFrame中寻找可能字段名。
    """
    if df is None or len(df.columns) == 0:
        return None

    lower_map = {c.lower(): c for c in df.columns}

    for cand in candidates:
        if cand.lower() in lower_map:
            return lower_map[cand.lower()]

    if contains:
        for cand in candidates:
            cl = cand.lower()
            for c in df.columns:
                if cl in c.lower():
                    return c
    return None


def load_json_records(path):
    """
    兼容：
    - list json
    - {"value": [...]}
    - {"data": [...]}
    """
    if path is None:
        return []

    with open(path, "r", encoding="utf-8") as f:
        obj = json.load(f)

    if isinstance(obj, list):
        return obj

    if isinstance(obj, dict):
        for k in ["value", "Value", "data", "Data", "records", "Records", "items", "Items"]:
            if k in obj and isinstance(obj[k], list):
                return obj[k]

        # 如果是单对象，也返回一条
        return [obj]

    return []


def flatten_json(path):
    records = load_json_records(path)
    if not records:
        return pd.DataFrame()

    # 处理SpeedBandInformation这类嵌套数组
    if isinstance(records[0], dict) and "SpeedBandInformation" in records[0]:
        base = pd.DataFrame(records)
        base = base.explode("SpeedBandInformation").reset_index(drop=True)
        info = pd.json_normalize(base["SpeedBandInformation"]).add_prefix("SpeedBandInformation.")
        base = base.drop(columns=["SpeedBandInformation"])
        df = pd.concat([base.reset_index(drop=True), info.reset_index(drop=True)], axis=1)
        return df

    return pd.json_normalize(records, sep=".")


def summarize_series(s):
    if s is None or len(s) == 0:
        return {}
    return {
        "count": int(s.count()),
        "nunique": int(s.nunique(dropna=True)),
        "missing": int(s.isna().sum()),
        "sample_values": list(s.dropna().astype(str).unique()[:10])
    }


# =========================
# 2. 静态路网和车道地图可行性
# =========================

def line_geometries(gdf):
    if gdf is None or gdf.empty:
        return gdf

    gdf = gdf.explode(index_parts=False).reset_index(drop=True)
    mask = gdf.geometry.geom_type.isin(["LineString"])
    return gdf[mask].copy()


def polygon_geometries(gdf):
    if gdf is None or gdf.empty:
        return gdf
    gdf = gdf.explode(index_parts=False).reset_index(drop=True)
    mask = gdf.geometry.geom_type.isin(["Polygon"])
    return gdf[mask].copy()


def point_geometries(gdf):
    if gdf is None or gdf.empty:
        return gdf
    gdf = gdf.explode(index_parts=False).reset_index(drop=True)
    mask = gdf.geometry.geom_type.isin(["Point"])
    return gdf[mask].copy()


def build_road_graph_stats(roads, snap_tol=5):
    """
    基于RoadSectionLine构建粗略无向图，用于判断网络连通性。
    注意：RoadSectionLine未必天然有方向，这里只做拓扑质量检查。
    """
    roads = line_geometries(roads)
    G = nx.Graph()

    def snap(x, y):
        return (round(x / snap_tol) * snap_tol, round(y / snap_tol) * snap_tol)

    total_len = 0.0
    valid_edges = 0

    for idx, row in roads.iterrows():
        geom = row.geometry
        if geom is None or geom.length <= 0:
            continue

        coords = list(geom.coords)
        if len(coords) < 2:
            continue

        u = snap(coords[0][0], coords[0][1])
        v = snap(coords[-1][0], coords[-1][1])
        length = float(geom.length)

        if u == v:
            continue

        G.add_edge(u, v, length=length, road_idx=idx)
        total_len += length
        valid_edges += 1

    comps = list(nx.connected_components(G))
    comps_size = sorted([len(c) for c in comps], reverse=True)
    largest_ratio = comps_size[0] / G.number_of_nodes() if G.number_of_nodes() > 0 else 0

    return {
        "road_features": int(len(roads)),
        "valid_graph_edges": int(valid_edges),
        "graph_nodes": int(G.number_of_nodes()),
        "graph_edges": int(G.number_of_edges()),
        "connected_components": int(len(comps)),
        "largest_component_node_ratio": round(float(largest_ratio), 4),
        "total_road_length_km": round(total_len / 1000, 2),
        "avg_edge_length_m": round(total_len / valid_edges, 2) if valid_edges else None
    }


def spatial_association_stats(roads, lanes=None, arrows=None, lights=None, loops=None, cfg=None, out_dir=None):
    """
    检查LaneMarking、ArrowMarking、TrafficLight、DetectorLoop与RoadSectionLine的空间匹配程度。
    """
    if cfg is None:
        cfg = CONFIG

    stats = {}

    roads = line_geometries(roads)
    roads = roads.reset_index(drop=True)
    roads["road_idx"] = roads.index
    roads["road_len_m"] = roads.geometry.length

    road_buf = roads[["road_idx", "road_len_m", "geometry"]].copy()
    road_buf["geometry"] = road_buf.geometry.buffer(cfg["road_buffer_m"])

    total_roads = len(roads)
    total_len = roads["road_len_m"].sum()

    # LaneMarking覆盖
    if lanes is not None and not lanes.empty:
        lanes = line_geometries(lanes)
        try:
            join = gpd.sjoin(
                lanes[["geometry"]],
                road_buf[["road_idx", "geometry"]],
                how="inner",
                predicate="intersects"
            )
            matched_roads = set(join["road_idx"].unique())
            matched_len = roads.loc[list(matched_roads), "road_len_m"].sum() if matched_roads else 0
            stats["lane_marking_features"] = int(len(lanes))
            stats["roads_with_lane_marking_ratio"] = round(len(matched_roads) / total_roads, 4) if total_roads else 0
            stats["road_length_with_lane_marking_ratio"] = round(matched_len / total_len, 4) if total_len else 0
        except Exception as e:
            stats["lane_marking_spatial_join_error"] = str(e)
    else:
        stats["lane_marking_features"] = 0

    # ArrowMarking覆盖
    if arrows is not None and not arrows.empty:
        arrows = arrows.copy()
        arrows["geometry"] = arrows.geometry.centroid
        try:
            join = gpd.sjoin(
                arrows[["geometry"]],
                road_buf[["road_idx", "geometry"]],
                how="inner",
                predicate="within"
            )
            matched_roads = set(join["road_idx"].unique())
            matched_len = roads.loc[list(matched_roads), "road_len_m"].sum() if matched_roads else 0
            stats["arrow_features"] = int(len(arrows))
            stats["roads_with_arrow_ratio"] = round(len(matched_roads) / total_roads, 4) if total_roads else 0
            stats["road_length_with_arrow_ratio"] = round(matched_len / total_len, 4) if total_len else 0

            # 箭头类型字段统计
            arrow_type_col = find_col(arrows, ["ARROW_TYPE", "arrow_type", "TYPE"])
            if arrow_type_col:
                arrow_summary = arrows[arrow_type_col].value_counts(dropna=False).head(20)
                arrow_summary.to_csv(Path(out_dir) / "arrow_type_counts.csv", encoding="utf-8-sig")
                stats["arrow_type_field"] = arrow_type_col
        except Exception as e:
            stats["arrow_spatial_join_error"] = str(e)
    else:
        stats["arrow_features"] = 0

    # 路口端点附近信号灯覆盖
    if lights is not None and not lights.empty:
        lights = lights.copy()
        if not all(lights.geometry.geom_type == "Point"):
            lights["geometry"] = lights.geometry.centroid

        endpoints = []
        for idx, geom in enumerate(roads.geometry):
            coords = list(geom.coords)
            if len(coords) >= 2:
                endpoints.append({"road_idx": idx, "endpoint": "start", "geometry": Point(coords[0])})
                endpoints.append({"road_idx": idx, "endpoint": "end", "geometry": Point(coords[-1])})

        ep_gdf = gpd.GeoDataFrame(endpoints, crs=roads.crs)
        try:
            near = gpd.sjoin_nearest(
                ep_gdf,
                lights[["geometry"]],
                how="left",
                max_distance=cfg["endpoint_signal_search_m"],
                distance_col="dist_m"
            )
            stats["traffic_light_features"] = int(len(lights))
            stats["road_endpoints_total"] = int(len(ep_gdf))
            stats["road_endpoints_near_signal_ratio"] = round(near["index_right"].notna().mean(), 4)
        except Exception as e:
            stats["traffic_light_nearest_error"] = str(e)
    else:
        stats["traffic_light_features"] = 0

    # 检测线圈覆盖
    if loops is not None and not loops.empty:
        loops = loops.copy()
        if not all(loops.geometry.geom_type == "Point"):
            loops["geometry"] = loops.geometry.centroid
        try:
            join = gpd.sjoin(
                loops[["geometry"]],
                road_buf[["road_idx", "geometry"]],
                how="inner",
                predicate="within"
            )
            matched_roads = set(join["road_idx"].unique())
            stats["detector_loop_features"] = int(len(loops))
            stats["roads_with_detector_loop_ratio"] = round(len(matched_roads) / total_roads, 4) if total_roads else 0
        except Exception as e:
            stats["detector_loop_join_error"] = str(e)
    else:
        stats["detector_loop_features"] = 0

    return stats


def audit_static_map(static_root, out_dir):
    static_root = Path(static_root)
    work_crs = CONFIG["work_crs"]

    paths = {
        "roads": find_first(static_root, ["RoadSectionLine"], [".shp"]),
        "lanes": find_first(static_root, ["LaneMarking"], [".shp"]),
        "arrows": find_first(static_root, ["ArrowMarking"], [".shp"]),
        "lights": find_first(static_root, ["TrafficLight"], [".shp"]),
        "loops": find_first(static_root, ["DetectorLoop"], [".shp"]),
        "kerb": find_first(static_root, ["KerbLine"], [".shp"]),
    }

    report = {}
    report["paths"] = {k: str(v) if v else None for k, v in paths.items()}

    roads = read_vector(paths["roads"], work_crs)
    lanes = read_vector(paths["lanes"], work_crs)
    arrows = read_vector(paths["arrows"], work_crs)
    lights = read_vector(paths["lights"], work_crs)
    loops = read_vector(paths["loops"], work_crs)

    if roads is None or roads.empty:
        report["error"] = "未找到RoadSectionLine，无法评估路网构建。"
        return report

    # 基础字段
    report["road_columns"] = list(roads.columns)
    report["road_crs"] = str(roads.crs)
    report["road_bounds"] = [round(x, 2) for x in roads.total_bounds]

    # 图连通性
    report["road_graph_stats"] = build_road_graph_stats(
        roads, CONFIG["graph_snap_tolerance_m"]
    )

    # 空间关联
    report["spatial_association_stats"] = spatial_association_stats(
        roads, lanes, arrows, lights, loops, CONFIG, out_dir
    )

    return report


# =========================
# 3. 动态交通数据可行性
# =========================

def select_largest_file(files):
    if not files:
        return None
    return sorted(files, key=lambda p: p.stat().st_size, reverse=True)[0]


def analyze_dynamic_spatial_coverage(dynamic_root, hist_dir, static_report, work_crs, out_dir):
    """
    基于SHP文件分析动态数据的空间覆盖范围。
    
    分析内容：
    1. TrafficSpeedBands_Links.shp 和 TrafficFlow_Links.shp 的覆盖范围
    2. 与静态 RoadSectionLine 的空间重叠度
    3. 两种动态数据之间的路段重合度
    4. 地理覆盖面积和比例
    """
    analysis = {
        "note": "使用历史数据生成的SHP文件进行空间覆盖分析",
    }
    
    # 查找SHP文件
    speed_shp = find_first(hist_dir, ["TrafficSpeedBands_Links"], [".shp"])
    flow_shp = find_first(hist_dir, ["TrafficFlow_Links"], [".shp"])
    
    analysis["speed_links_shp"] = str(speed_shp) if speed_shp else None
    analysis["flow_links_shp"] = str(flow_shp) if flow_shp else None
    
    # 读取静态路网
    roads = None
    if static_report and "paths" in static_report:
        road_path = static_report["paths"].get("roads")
        if road_path:
            roads = read_vector(Path(road_path), work_crs)
    
    # 读取动态SHP文件
    speed_gdf = read_vector(speed_shp, work_crs) if speed_shp else None
    flow_gdf = read_vector(flow_shp, work_crs) if flow_shp else None
    
    # =========================
    # 1. SpeedBands 空间分析
    # =========================
    if speed_gdf is not None and not speed_gdf.empty:
        speed_analysis = {}
        speed_analysis["total_features"] = int(len(speed_gdf))
        speed_analysis["crs"] = str(speed_gdf.crs)
        
        # 检查LinkID字段
        link_col = find_col(speed_gdf, ["LinkID", "link_id", "LINK_ID"])
        
        # 去重：按LinkID保留唯一记录（取第一条）
        if link_col:
            unique_links_count = speed_gdf[link_col].nunique()
            speed_analysis["unique_link_ids"] = int(unique_links_count)
            
            # 创建去重后的GeoDataFrame用于空间分析
            speed_unique = speed_gdf.drop_duplicates(subset=[link_col], keep='first').copy()
            speed_analysis["features_after_dedup"] = int(len(speed_unique))
        else:
            speed_unique = speed_gdf.copy()
        
        # 计算总长度（使用去重后的数据）
        speed_unique["length_m"] = speed_unique.geometry.length
        total_speed_length_km = speed_unique["length_m"].sum() / 1000
        speed_analysis["total_length_km"] = round(total_speed_length_km, 2)
        
        # 如果有RoadName，统计道路类型
        roadname_col = find_col(speed_gdf, ["RoadName", "road_name", "ROAD_NAME"])
        if roadname_col:
            unique_roads = speed_gdf[roadname_col].nunique()
            speed_analysis["unique_road_names"] = int(unique_roads)
        
        analysis["speedbands_spatial"] = speed_analysis
        # 保存去重后的数据供后续使用
        analysis["_speed_gdf_unique"] = speed_unique
    else:
        analysis["speedbands_spatial"] = {"error": "未找到TrafficSpeedBands_Links.shp"}
    
    # =========================
    # 2. TrafficFlow 空间分析
    # =========================
    if flow_gdf is not None and not flow_gdf.empty:
        flow_analysis = {}
        flow_analysis["total_features"] = int(len(flow_gdf))
        flow_analysis["crs"] = str(flow_gdf.crs)
        
        # 计算总长度
        flow_gdf["length_m"] = flow_gdf.geometry.length
        total_flow_length_km = flow_gdf["length_m"].sum() / 1000
        flow_analysis["total_length_km"] = round(total_flow_length_km, 2)
        
        # 检查LinkID字段
        link_col = find_col(flow_gdf, ["LinkID", "link_id", "LINK_ID"])
        if link_col:
            unique_links = flow_gdf[link_col].nunique()
            flow_analysis["unique_link_ids"] = int(unique_links)
        
        analysis["trafficflow_spatial"] = flow_analysis
    else:
        analysis["trafficflow_spatial"] = {"error": "未找到TrafficFlow_Links.shp"}
    
    # =========================
    # 3. 静态-动态空间重叠分析
    # =========================
    if roads is not None and not roads.empty:
        static_analysis = {}
        
        # 静态路网总长度
        roads["length_m"] = roads.geometry.length
        total_static_length_km = roads["length_m"].sum() / 1000
        static_analysis["static_total_length_km"] = round(total_static_length_km, 2)
        
        # SpeedBands 与静态路网的重叠（使用去重后的数据）
        speed_unique = analysis.get("_speed_gdf_unique")
        if speed_unique is not None and not speed_unique.empty:
            try:
                # 创建静态路网的缓冲区（15米）
                static_buf = roads.buffer(CONFIG["road_buffer_m"])
                static_union = unary_union(static_buf)
                
                # 计算SpeedBands在缓冲区内 的长度
                speed_in_buffer = speed_unique[speed_unique.geometry.within(static_union)]
                covered_length_km = speed_in_buffer["length_m"].sum() / 1000
                
                coverage_ratio = covered_length_km / total_static_length_km if total_static_length_km > 0 else 0
                
                # 覆盖率可能超过100%，因为动态数据可能有更细的路段划分或双向分开
                interpretation = (
                    f"SpeedBands覆盖了{round(coverage_ratio*100, 1)}%的静态路网长度。"
                    if coverage_ratio >= 0.9 else
                    f"SpeedBands覆盖率中等({round(coverage_ratio*100, 1)}%)，主要干道可能有数据。"
                    if coverage_ratio >= 0.5 else
                    f"SpeedBands覆盖率较低({round(coverage_ratio*100, 1)}%)，可能只覆盖关键路段。"
                )
                
                static_analysis["speedbands_coverage"] = {
                    "covered_length_km": round(covered_length_km, 2),
                    "coverage_ratio": round(coverage_ratio, 4),
                    "interpretation": interpretation,
                    "note": "覆盖率>100%表示动态数据路段划分更细或包含双向分开统计，实际覆盖充分。"
                }
            except Exception as e:
                static_analysis["speedbands_coverage_error"] = str(e)
        
        # TrafficFlow 与静态路网的重叠
        if flow_gdf is not None and not flow_gdf.empty:
            try:
                # 创建静态路网的缓冲区（15米）
                static_buf = roads.buffer(CONFIG["road_buffer_m"])
                static_union = unary_union(static_buf)
                
                # 计算TrafficFlow在缓冲区内 的长度
                flow_in_buffer = flow_gdf[flow_gdf.geometry.within(static_union)]
                covered_length_km = flow_in_buffer["length_m"].sum() / 1000
                
                coverage_ratio = covered_length_km / total_static_length_km if total_static_length_km > 0 else 0
                
                static_analysis["trafficflow_coverage"] = {
                    "covered_length_km": round(covered_length_km, 2),
                    "coverage_ratio": round(coverage_ratio, 4),
                    "interpretation": (
                        f"TrafficFlow覆盖了{round(coverage_ratio*100, 1)}%的静态路网长度。"
                        if coverage_ratio > 0.7 else
                        f"TrafficFlow覆盖率较低({round(coverage_ratio*100, 1)}%)，可能只覆盖关键路段。"
                    )
                }
            except Exception as e:
                static_analysis["trafficflow_coverage_error"] = str(e)
        
        analysis["static_dynamic_overlap"] = static_analysis
    
    # =========================
    # 4. SpeedBands 与 TrafficFlow 的空间重叠
    # =========================
    if speed_gdf is not None and not speed_gdf.empty and flow_gdf is not None and not flow_gdf.empty:
        try:
            overlap_analysis = {}
            
            # 计算两者的空间交集
            # 使用buffer来容忍小的几何偏差
            speed_buf = speed_gdf.buffer(10)  # 10米缓冲
            flow_buf = flow_gdf.buffer(10)
            
            # 简化：计算有交集的路段数量
            # 这里使用边界框快速筛选
            speed_bounds = speed_gdf.total_bounds
            flow_bounds = flow_gdf.total_bounds
            
            # 计算包围盒重叠区域
            x_min = max(speed_bounds[0], flow_bounds[0])
            y_min = max(speed_bounds[1], flow_bounds[1])
            x_max = min(speed_bounds[2], flow_bounds[2])
            y_max = min(speed_bounds[3], flow_bounds[3])
            
            if x_min < x_max and y_min < y_max:
                overlap_area = (x_max - x_min) * (y_max - y_min)
                total_area_speed = (speed_bounds[2] - speed_bounds[0]) * (speed_bounds[3] - speed_bounds[1])
                total_area_flow = (flow_bounds[2] - flow_bounds[0]) * (flow_bounds[3] - flow_bounds[1])
                
                overlap_analysis["bbox_overlap_area_km2"] = round(overlap_area / 1e6, 2)
                overlap_analysis["overlap_ratio_to_speed_bbox"] = round(overlap_area / total_area_speed, 4) if total_area_speed > 0 else 0
                overlap_analysis["overlap_ratio_to_flow_bbox"] = round(overlap_area / total_area_flow, 4) if total_area_flow > 0 else 0
            
            # LinkID 重叠（如果都有LinkID字段）
            speed_link_col = find_col(speed_gdf, ["LinkID", "link_id"])
            flow_link_col = find_col(flow_gdf, ["LinkID", "link_id"])
            
            if speed_link_col and flow_link_col:
                s_links = set(speed_gdf[speed_link_col].dropna().astype(str).unique())
                f_links = set(flow_gdf[flow_link_col].dropna().astype(str).unique())
                common_links = s_links & f_links
                
                overlap_analysis["link_id_overlap"] = {
                    "speed_links": len(s_links),
                    "flow_links": len(f_links),
                    "common_links": len(common_links),
                    "overlap_ratio_to_speed": round(len(common_links) / len(s_links), 4) if s_links else 0,
                    "overlap_ratio_to_flow": round(len(common_links) / len(f_links), 4) if f_links else 0,
                }
            
            analysis["speed_flow_spatial_overlap"] = overlap_analysis
        except Exception as e:
            analysis["speed_flow_overlap_error"] = str(e)
    
    # =========================
    # 5. 生成可视化数据（可选）
    # =========================
    try:
        # 保存覆盖统计数据到CSV
        coverage_stats = []
        
        if "speedbands_spatial" in analysis and "total_length_km" in analysis["speedbands_spatial"]:
            coverage_stats.append({
                "dataset": "TrafficSpeedBands",
                "total_length_km": analysis["speedbands_spatial"]["total_length_km"],
                "unique_links": analysis["speedbands_spatial"].get("unique_link_ids", 0),
            })
        
        if "trafficflow_spatial" in analysis and "total_length_km" in analysis["trafficflow_spatial"]:
            coverage_stats.append({
                "dataset": "TrafficFlow",
                "total_length_km": analysis["trafficflow_spatial"]["total_length_km"],
                "unique_links": analysis["trafficflow_spatial"].get("unique_link_ids", 0),
            })
        
        if coverage_stats:
            pd.DataFrame(coverage_stats).to_csv(
                Path(out_dir) / "dynamic_coverage_stats.csv",
                index=False,
                encoding="utf-8-sig"
            )
    except Exception as e:
        print(f"[WARN] 保存覆盖统计失败: {e}")
    
    return analysis


def audit_dynamic_data(dynamic_root, static_report=None, out_dir=None):
    """
    审计动态交通数据，包括：
    1. JSON数据分析（SpeedBands、TrafficFlow等）
    2. 使用SHP文件进行空间覆盖分析（如果存在）
    3. 静态-动态路网匹配度评估
    """
    dynamic_root = Path(dynamic_root)
    hist = dynamic_root / "historical_data"
    realtime = dynamic_root / "realtime_monitoring"

    # 查找JSON文件
    speed_files = find_files(dynamic_root, ["TrafficSpeedBands"], [".json"])
    flow_files = find_files(dynamic_root, ["TrafficFlow"], [".json"])
    ett_files = find_files(dynamic_root, ["EstimatedTravelTimes"], [".json"])
    incident_files = find_files(dynamic_root, ["TrafficIncidents"], [".json"])

    speed_file = select_largest_file(speed_files)
    flow_file = select_largest_file(flow_files)
    ett_file = select_largest_file(ett_files)
    incident_file = select_largest_file(incident_files)

    report = {
        "selected_files": {
            "speed_file": str(speed_file) if speed_file else None,
            "flow_file": str(flow_file) if flow_file else None,
            "estimated_travel_time_file": str(ett_file) if ett_file else None,
            "incident_file": str(incident_file) if incident_file else None,
        }
    }

    # =========================
    # 1. JSON数据分析
    # =========================
    
    # SpeedBands
    speed_df = flatten_json(speed_file) if speed_file else pd.DataFrame()
    report["speed_records"] = int(len(speed_df))
    report["speed_columns"] = list(speed_df.columns)

    speed_link_col = find_col(speed_df, ["LinkID", "link_id", "ROAD_ID", "RoadID"])
    speed_roadname_col = find_col(speed_df, ["RoadName", "road_name", "ROAD_NAME"])
    speed_avg_col = find_col(speed_df, ["AverageSpeed", "average_speed", "Speed", "speed"])
    speed_band_col = find_col(speed_df, ["CongestionLevel", "SpeedBand", "speed_band"])
    speed_time_col = find_col(speed_df, ["Timestamp", "StartTime", "SpeedBandInformation.StartTime", "StartDate"])

    report["speed_key_fields"] = {
        "link_col": speed_link_col,
        "roadname_col": speed_roadname_col,
        "avg_speed_col": speed_avg_col,
        "band_col": speed_band_col,
        "time_col": speed_time_col,
    }

    if speed_link_col:
        report["speed_link_summary"] = summarize_series(speed_df[speed_link_col])
    if speed_avg_col or speed_band_col:
        col_to_use = speed_avg_col if speed_avg_col else speed_band_col
        speed_num = pd.to_numeric(speed_df[col_to_use], errors="coerce")
        report["speed_value_summary"] = {
            "count": int(speed_num.count()),
            "mean": round(float(speed_num.mean()), 2) if speed_num.count() else None,
            "p10": round(float(speed_num.quantile(0.1)), 2) if speed_num.count() else None,
            "p50": round(float(speed_num.quantile(0.5)), 2) if speed_num.count() else None,
            "p90": round(float(speed_num.quantile(0.9)), 2) if speed_num.count() else None,
        }

    if len(speed_df) > 0:
        speed_df.head(5000).to_csv(Path(out_dir) / "speedbands_sample.csv", index=False, encoding="utf-8-sig")

    # TrafficFlow
    flow_df = flatten_json(flow_file) if flow_file else pd.DataFrame()
    report["flow_records"] = int(len(flow_df))
    report["flow_columns"] = list(flow_df.columns)

    flow_link_col = find_col(flow_df, ["LinkID", "link_id", "ROAD_ID", "RoadID"])
    flow_volume_col = find_col(flow_df, ["Volume", "volume", "COUNT", "count", "Flow"])
    flow_time_col = find_col(flow_df, ["Timestamp", "timestamp", "StartTime", "DateTime"])
    flow_vtype_col = find_col(flow_df, ["VehicleType", "vehicle_type", "TYPE"])

    report["flow_key_fields"] = {
        "link_col": flow_link_col,
        "volume_col": flow_volume_col,
        "time_col": flow_time_col,
        "vehicle_type_col": flow_vtype_col,
    }

    if flow_link_col:
        report["flow_link_summary"] = summarize_series(flow_df[flow_link_col])
    if flow_volume_col:
        vol = pd.to_numeric(flow_df[flow_volume_col], errors="coerce")
        report["flow_value_summary"] = {
            "count": int(vol.count()),
            "mean": round(float(vol.mean()), 2) if vol.count() else None,
            "p10": round(float(vol.quantile(0.1)), 2) if vol.count() else None,
            "p50": round(float(vol.quantile(0.5)), 2) if vol.count() else None,
            "p90": round(float(vol.quantile(0.9)), 2) if vol.count() else None,
        }

    if len(flow_df) > 0:
        flow_df.head(5000).to_csv(Path(out_dir) / "trafficflow_sample.csv", index=False, encoding="utf-8-sig")

    # Speed 与 Flow 的 LinkID重合度
    if speed_link_col and flow_link_col and len(speed_df) > 0 and len(flow_df) > 0:
        s_links = set(speed_df[speed_link_col].dropna().astype(str).unique())
        f_links = set(flow_df[flow_link_col].dropna().astype(str).unique())
        inter = s_links & f_links
        report["speed_flow_link_overlap"] = {
            "speed_links": len(s_links),
            "flow_links": len(f_links),
            "overlap_links": len(inter),
            "overlap_ratio_to_speed": round(len(inter) / len(s_links), 4) if s_links else 0,
            "overlap_ratio_to_flow": round(len(inter) / len(f_links), 4) if f_links else 0,
        }

    # EstimatedTravelTimes
    ett_df = flatten_json(ett_file) if ett_file else pd.DataFrame()
    report["estimated_travel_time_records"] = int(len(ett_df))
    report["estimated_travel_time_columns"] = list(ett_df.columns)

    if len(ett_df) > 0:
        ett_df.head(5000).to_csv(Path(out_dir) / "estimated_travel_time_sample.csv", index=False, encoding="utf-8-sig")

    # Incidents
    inc_df = flatten_json(incident_file) if incident_file else pd.DataFrame()
    report["incident_records"] = int(len(inc_df))
    report["incident_columns"] = list(inc_df.columns)

    if len(inc_df) > 0:
        inc_df.head(5000).to_csv(Path(out_dir) / "incident_sample.csv", index=False, encoding="utf-8-sig")

    # =========================
    # 2. 基于SHP文件的空间覆盖分析（新增）
    # =========================
    work_crs = CONFIG["work_crs"]
    spatial_analysis = analyze_dynamic_spatial_coverage(
        dynamic_root, hist, static_report, work_crs, out_dir
    )
    report["spatial_coverage_analysis"] = spatial_analysis

    # =========================
    # 3. 静态-动态直接关联风险检查
    # =========================
    road_columns = []
    if static_report and "road_columns" in static_report:
        road_columns = static_report["road_columns"]

    possible_static_link_cols = [
        c for c in road_columns
        if c.lower() in ["linkid", "link_id", "roadid", "road_id", "rd_cd", "roadname", "road_name"]
    ]

    report["static_dynamic_key_risk"] = {
        "static_possible_key_columns": possible_static_link_cols,
        "dynamic_speed_link_col": speed_link_col,
        "dynamic_speed_roadname_col": speed_roadname_col,
        "dynamic_flow_link_col": flow_link_col,
        "comment": (
            "如果静态RoadSectionLine没有LinkID/RoadName等可与动态数据直接匹配的字段，"
            "则需要通过RoadName、几何、LTA额外Link Geometry或地图匹配方法建立映射。"
        )
    }

    return report


# =========================
# 4. 人口、POI、HDB、用地与OD代理可行性
# =========================

def audit_population_raster(other_root, out_dir):
    if rasterio is None:
        return {"error": "rasterio未安装，跳过人口栅格检查。"}

    other_root = Path(other_root)
    pop_dir = other_root / "Population"
    
    # 优先查找2026年100m分辨率的总人口数据
    pop_file = find_first(pop_dir, ["sgp_pop_2026", "100m"], [".tif"])
    if pop_file is None:
        pop_file = find_first(pop_dir, ["sgp_pop_2025", "100m"], [".tif"])
    if pop_file is None:
        pop_file = find_first(pop_dir, ["sgp_pop_2026", "1km"], [".tif"])
    if pop_file is None:
        pop_file = find_first(pop_dir, ["sgp_pop_2025", "1km"], [".tif"])

    if pop_file is None:
        return {"error": "未找到人口栅格tif。请检查Population文件夹。"}

    report = {"population_file": str(pop_file)}

    with rasterio.open(pop_file) as src:
        arr = src.read(1, masked=True)
        data = arr.compressed()
        report["crs"] = str(src.crs)
        report["bounds"] = [round(x, 6) for x in src.bounds]
        report["resolution"] = src.res
        report["valid_cells"] = int(data.size)
        report["positive_cells"] = int((data > 0).sum())
        report["total_population_sum"] = round(float(data[data > 0].sum()), 2) if (data > 0).sum() else 0
        report["population_mean_positive"] = round(float(data[data > 0].mean()), 2) if (data > 0).sum() else 0
        report["population_p90_positive"] = round(float(np.quantile(data[data > 0], 0.9)), 2) if (data > 0).sum() else 0

    return report


def read_csv_if_exists(path):
    if path is None:
        return pd.DataFrame()
    try:
        return pd.read_csv(path)
    except UnicodeDecodeError:
        return pd.read_csv(path, encoding="latin1")
    except Exception as e:
        print(f"[WARN] 读取CSV失败: {path}, {e}")
        return pd.DataFrame()


def make_point_gdf_from_latlng(df, lat_col=None, lng_col=None, work_crs="EPSG:3414"):
    if df is None or df.empty:
        return None

    if lat_col is None:
        lat_col = find_col(df, ["lat", "latitude", "LATTD_TXT", "LATITUDE"])
    if lng_col is None:
        lng_col = find_col(df, ["lng", "lon", "longitude", "LONGTD_TXT", "LONGTITUDE"])

    if lat_col is None or lng_col is None:
        return None

    tmp = df.copy()
    tmp[lat_col] = pd.to_numeric(tmp[lat_col], errors="coerce")
    tmp[lng_col] = pd.to_numeric(tmp[lng_col], errors="coerce")
    tmp = tmp.dropna(subset=[lat_col, lng_col])

    gdf = gpd.GeoDataFrame(
        tmp,
        geometry=gpd.points_from_xy(tmp[lng_col], tmp[lat_col]),
        crs="EPSG:4326"
    ).to_crs(work_crs)

    return gdf


def audit_hdb_poi_landuse(other_root, out_dir):
    other_root = Path(other_root)
    work_crs = CONFIG["work_crs"]
    report = {}

    # HDB - 优先使用LTSG数据集的hdb.csv（包含完整属性字段）
    ltsg_dir = other_root / "siteselect_sg-main" / "dataset"
    hdb_file = ltsg_dir / "hdb.csv"
    
    # 如果LTSG数据不存在，尝试从goverment_open查找
    if not hdb_file.exists():
        gov_dir = other_root / "goverment_open"
        hdb_geojson = find_first(gov_dir, ["HDBExistingBuilding"], [".geojson"])
        if hdb_geojson:
            hdb_gdf_temp = read_vector(hdb_geojson, work_crs)
            if hdb_gdf_temp is not None and not hdb_gdf_temp.empty:
                hdb_df = pd.DataFrame(hdb_gdf_temp.drop(columns=['geometry']))
            else:
                hdb_df = pd.DataFrame()
        else:
            hdb_df = pd.DataFrame()
    else:
        hdb_df = read_csv_if_exists(hdb_file)
    
    report["hdb_file"] = str(hdb_file) if hdb_file.exists() else None
    report["hdb_records"] = int(len(hdb_df))
    report["hdb_columns"] = list(hdb_df.columns)

    hdb_zone_col = find_col(hdb_df, ["PLN_AREA_N", "planning_area", "pln_area", "SUBZONE_N"])
    hdb_units_col = find_col(hdb_df, ["total_dwelling_units", "dwelling", "units"])
    hdb_gdf = make_point_gdf_from_latlng(hdb_df, work_crs=work_crs)

    if hdb_units_col:
        hdb_df[hdb_units_col] = pd.to_numeric(hdb_df[hdb_units_col], errors="coerce")
        report["hdb_total_dwelling_units"] = int(hdb_df[hdb_units_col].sum(skipna=True))
    report["hdb_zone_col"] = hdb_zone_col
    report["hdb_units_col"] = hdb_units_col
    report["hdb_has_geometry"] = hdb_gdf is not None

    if hdb_zone_col and hdb_units_col:
        hdb_zone = hdb_df.groupby(hdb_zone_col)[hdb_units_col].sum().sort_values(ascending=False)
        hdb_zone.to_csv(Path(out_dir) / "hdb_dwelling_by_zone.csv", encoding="utf-8-sig")

    # POI - 优先使用LTSG数据集的poi.csv
    poi_file = ltsg_dir / "poi.csv"
    if not poi_file.exists():
        poi_df = pd.DataFrame()
    else:
        poi_df = read_csv_if_exists(poi_file)
    
    report["poi_file"] = str(poi_file) if poi_file.exists() else None
    report["poi_records"] = int(len(poi_df))
    report["poi_columns_count"] = int(len(poi_df.columns))
    report["poi_columns_sample"] = list(poi_df.columns[:30])

    poi_zone_col = find_col(poi_df, ["planning_area", "PLN_AREA_N", "pln_area"])
    poi_gdf = make_point_gdf_from_latlng(poi_df, work_crs=work_crs)

    report["poi_zone_col"] = poi_zone_col
    report["poi_has_geometry"] = poi_gdf is not None

    # 简单POI吸引权重
    if not poi_df.empty:
        poi_weight = pd.Series(1.0, index=poi_df.index)

        category_weights = {
            "shopping_mall": 5,
            "supermarket": 3,
            "restaurant": 2,
            "cafe": 1.5,
            "school": 3,
            "university": 5,
            "hospital": 5,
            "doctor": 2,
            "pharmacy": 1.5,
            "tourist_attraction": 3,
            "park": 1.5,
            "subway_station": 2,
            "bus_station": 1,
        }

        used_cols = []
        for col, w in category_weights.items():
            if col in poi_df.columns:
                vals = poi_df[col].astype(str).str.lower().isin(["true", "1", "yes"])
                poi_weight += vals.astype(float) * w
                used_cols.append(col)

        poi_df["_poi_attraction_weight"] = poi_weight
        report["poi_weight_used_category_cols"] = used_cols

        if poi_zone_col:
            poi_zone = poi_df.groupby(poi_zone_col)["_poi_attraction_weight"].sum().sort_values(ascending=False)
            poi_zone.to_csv(Path(out_dir) / "poi_attraction_by_zone.csv", encoding="utf-8-sig")

    # LandUse - 从goverment_open查找Master Plan土地用途数据
    gov_dir = other_root / "goverment_open"
    landuse_file = find_first(gov_dir, ["MasterPlan2019LandUselayer"], [".geojson"])
    landuse_gdf = read_vector(landuse_file, work_crs) if landuse_file else None

    report["landuse_file"] = str(landuse_file) if landuse_file else None
    report["landuse_records"] = int(len(landuse_gdf)) if landuse_gdf is not None else 0

    if landuse_gdf is not None and not landuse_gdf.empty:
        report["landuse_columns"] = list(landuse_gdf.columns)
        # Master Plan 2019的土地用途字段通常是'DEV_TYPE'或'LAND_USE'
        lu_col = find_col(
            landuse_gdf,
            ["DEV_TYPE", "LAND_USE", "LU_DESC", "LANDUSE", "PLN_AREA_N"],
            contains=True
        )
        report["landuse_type_col_guess"] = lu_col

        landuse_gdf["_area_km2"] = landuse_gdf.geometry.area / 1e6
        if lu_col:
            lu_area = landuse_gdf.groupby(lu_col)["_area_km2"].sum().sort_values(ascending=False)
            lu_area.to_csv(Path(out_dir) / "landuse_area_by_type.csv", encoding="utf-8-sig")

    # 生成一个很粗的OD代理矩阵：基于HDB居住单元和POI吸引
    od_report = build_proxy_od(hdb_df, poi_df, hdb_zone_col, hdb_units_col, poi_zone_col, out_dir)
    report["proxy_od"] = od_report

    return report


def build_proxy_od(hdb_df, poi_df, hdb_zone_col, hdb_units_col, poi_zone_col, out_dir):
    """
    基于规划区的极简OD代理。
    目的：不是产出最终OD，而是检查数据是否足够支撑OD生成。
    """
    if hdb_df.empty or poi_df.empty or hdb_zone_col is None or hdb_units_col is None or poi_zone_col is None:
        return {
            "status": "failed",
            "reason": "缺少HDB居住区字段、住宅单元字段或POI规划区字段。"
        }

    hdb_df = hdb_df.copy()
    poi_df = poi_df.copy()

    hdb_df[hdb_units_col] = pd.to_numeric(hdb_df[hdb_units_col], errors="coerce")
    origins = hdb_df.groupby(hdb_zone_col)[hdb_units_col].sum()
    origins = origins[origins > 0]

    if "_poi_attraction_weight" not in poi_df.columns:
        poi_df["_poi_attraction_weight"] = 1.0
    attractions = poi_df.groupby(poi_zone_col)["_poi_attraction_weight"].sum()
    attractions = attractions[attractions > 0]

    zones = sorted(set(origins.index.astype(str)) & set(attractions.index.astype(str)))
    if len(zones) < 5:
        return {
            "status": "weak",
            "reason": "HDB和POI可共同识别的zone数量过少。",
            "common_zones": len(zones)
        }

    origins.index = origins.index.astype(str)
    attractions.index = attractions.index.astype(str)

    # 如果没有zone中心距离，这里先用无距离阻抗版本，只生成潜在OD强度
    O = origins.loc[zones]
    A = attractions.loc[zones]

    total_daily_car_trip_scale = float(O.sum()) * 1.0  # 每住宅单元1次车出行，粗略占位
    od_rows = []

    for i in zones:
        denom = A.sum()
        if denom <= 0:
            continue
        for j in zones:
            if i == j:
                impedance = 0.5
            else:
                impedance = 1.0
            val = O.loc[i] * A.loc[j] * impedance / denom
            od_rows.append({
                "origin_zone": i,
                "destination_zone": j,
                "od_weight_raw": val
            })

    od = pd.DataFrame(od_rows)
    scale = total_daily_car_trip_scale / od["od_weight_raw"].sum()
    od["daily_trip_proxy"] = od["od_weight_raw"] * scale
    od = od.sort_values("daily_trip_proxy", ascending=False)

    od.to_csv(Path(out_dir) / "proxy_od_by_planning_area.csv", index=False, encoding="utf-8-sig")

    return {
        "status": "ok",
        "common_zones": len(zones),
        "origin_total_dwelling_units": round(float(O.sum()), 2),
        "attraction_total_weight": round(float(A.sum()), 2),
        "proxy_daily_trips_sum": round(float(od["daily_trip_proxy"].sum()), 2),
        "output_file": "proxy_od_by_planning_area.csv",
        "note": "该OD仅用于可行性检查。正式OD需加入距离/时间阻抗、就业、用地、公共交通分担率和流量校准。"
    }


# =========================
# 5. 生成最终报告
# =========================

def risk_level_from_reports(static_report, dynamic_report, demand_report):
    risks = []

    # 地图风险
    assoc = static_report.get("spatial_association_stats", {})
    graph = static_report.get("road_graph_stats", {})

    lc_ratio = assoc.get("road_length_with_lane_marking_ratio", 0)
    largest = graph.get("largest_component_node_ratio", 0)

    if largest < 0.7:
        risks.append(("高", "RoadSectionLine连通性较弱，路网拓扑需要大量修复。"))
    elif largest < 0.85:
        risks.append(("中", "RoadSectionLine存在一定连通性问题，需要局部拓扑清洗。"))

    if lc_ratio < 0.3:
        risks.append(("高", "LaneMarking覆盖道路长度比例较低，车道级地图只能在局部区域可靠生成。"))
    elif lc_ratio < 0.6:
        risks.append(("中", "LaneMarking覆盖中等，主干路可能可做，局部道路需要规则补全。"))

    # 动态数据风险 - 基于空间覆盖分析（新增）
    spatial = dynamic_report.get("spatial_coverage_analysis", {})
    
    # 检查 SpeedBands 覆盖率
    if "static_dynamic_overlap" in spatial:
        sdo = spatial["static_dynamic_overlap"]
        if "speedbands_coverage" in sdo:
            sb_cov = sdo["speedbands_coverage"].get("coverage_ratio", 0)
            if sb_cov >= 0.9:  # 包括 > 100% 的情况
                risks.append(("低", f"SpeedBands覆盖{round(sb_cov*100, 1)}%的静态路网，覆盖度良好。"))
            elif sb_cov >= 0.7:
                risks.append(("中", f"SpeedBands覆盖{round(sb_cov*100, 1)}%的静态路网，主要干道可能有数据，但支路覆盖不足。"))
            else:
                risks.append(("高", f"SpeedBands仅覆盖{round(sb_cov*100, 1)}%的静态路网，覆盖率严重不足。"))
        
        # 检查 TrafficFlow 覆盖率
        if "trafficflow_coverage" in sdo:
            tf_cov = sdo["trafficflow_coverage"].get("coverage_ratio", 0)
            if tf_cov < 0.3:
                risks.append(("高", f"TrafficFlow仅覆盖{round(tf_cov*100, 1)}%的静态路网，流量校准将非常困难。"))
            elif tf_cov < 0.5:
                risks.append(("中", f"TrafficFlow覆盖{round(tf_cov*100, 1)}%的静态路网，只能校准部分关键路段。"))
            else:
                risks.append(("低", f"TrafficFlow覆盖{round(tf_cov*100, 1)}%的静态路网，覆盖度可接受。"))
    
    # Speed-Flow LinkID 重叠度（改进版）
    if "speed_flow_spatial_overlap" in spatial and "link_id_overlap" in spatial["speed_flow_spatial_overlap"]:
        lio = spatial["speed_flow_spatial_overlap"]["link_id_overlap"]
        overlap_ratio = min(
            lio.get("overlap_ratio_to_speed", 0),
            lio.get("overlap_ratio_to_flow", 0)
        )
        if overlap_ratio < 0.3:
            risks.append(("高", f"SpeedBands与TrafficFlow的LinkID重叠率仅{round(overlap_ratio*100, 1)}%，联合校准极其困难。"))
        elif overlap_ratio < 0.6:
            risks.append(("中", f"SpeedBands与TrafficFlow的LinkID重叠率为{round(overlap_ratio*100, 1)}%，部分路段可同时使用速度和流量数据。"))
        else:
            risks.append(("低", f"SpeedBands与TrafficFlow的LinkID重叠率为{round(overlap_ratio*100, 1)}%，适合联合校准。"))
    elif dynamic_report.get("speed_flow_link_overlap"):
        # 回退到旧的JSON分析方法
        overlap = dynamic_report.get("speed_flow_link_overlap", {})
        r = min(
            overlap.get("overlap_ratio_to_speed", 0),
            overlap.get("overlap_ratio_to_flow", 0)
        )
        if r < 0.3:
            risks.append(("中", "TrafficSpeedBands与TrafficFlow的LinkID重合较低，速度和流量联合校准困难。"))

    # 静态-动态键值匹配风险
    key_risk = dynamic_report.get("static_dynamic_key_risk", {})
    static_keys = key_risk.get("static_possible_key_columns", [])
    speed_link = key_risk.get("dynamic_speed_link_col")
    flow_link = key_risk.get("dynamic_flow_link_col")

    if (speed_link or flow_link) and not static_keys:
        risks.append(("高", "动态TrafficSpeed/Flow存在LinkID，但静态RoadSectionLine缺少明显对应键，地图匹配是核心风险。"))

    if dynamic_report.get("speed_records", 0) == 0:
        risks.append(("高", "未成功读取TrafficSpeedBands，无法用速度校准仿真。"))
    if dynamic_report.get("flow_records", 0) == 0:
        risks.append(("中", "未成功读取TrafficFlow，OD反推会缺少流量约束。"))

    # 需求数据风险
    od_status = demand_report.get("proxy_od", {}).get("status")
    if od_status != "ok":
        risks.append(("中", "HDB/POI规划区级OD代理生成不完整，需要改用人口栅格或土地利用重新构建交通小区。"))

    if not risks:
        risks.append(("低", "从自动检查结果看，数据具备开展开放数据交通数字孪生PoC的基础条件。"))

    return risks


def write_report(static_report, dynamic_report, pop_report, demand_report, out_dir):
    out_dir = Path(out_dir)
    lines = []

    lines.append("# Singapore Traffic Digital Twin Feasibility Audit Report")
    lines.append("")
    lines.append("## 1. Static Map Audit")
    lines.append("")
    lines.append("### 1.1 Input Paths")
    for k, v in static_report.get("paths", {}).items():
        lines.append(f"- {k}: `{v}`")

    lines.append("")
    lines.append("### 1.2 Road Graph Stats")
    for k, v in static_report.get("road_graph_stats", {}).items():
        lines.append(f"- {k}: {v}")

    lines.append("")
    lines.append("### 1.3 Spatial Association Stats")
    for k, v in static_report.get("spatial_association_stats", {}).items():
        lines.append(f"- {k}: {v}")

    lines.append("")
    lines.append("## 2. Dynamic Traffic Audit")
    lines.append("")
    lines.append("### 2.1 Selected Files")
    for k, v in dynamic_report.get("selected_files", {}).items():
        lines.append(f"- {k}: `{v}`")

    lines.append("")
    lines.append("### 2.2 SpeedBands")
    lines.append(f"- records: {dynamic_report.get('speed_records')}")
    lines.append(f"- key fields: {dynamic_report.get('speed_key_fields')}")
    lines.append(f"- link summary: {dynamic_report.get('speed_link_summary')}")
    lines.append(f"- speed summary: {dynamic_report.get('speed_value_summary')}")

    lines.append("")
    lines.append("### 2.3 TrafficFlow")
    lines.append(f"- records: {dynamic_report.get('flow_records')}")
    lines.append(f"- key fields: {dynamic_report.get('flow_key_fields')}")
    lines.append(f"- link summary: {dynamic_report.get('flow_link_summary')}")
    lines.append(f"- volume summary: {dynamic_report.get('flow_value_summary')}")

    lines.append("")
    lines.append("### 2.4 Speed-Flow Link Overlap")
    lines.append(str(dynamic_report.get("speed_flow_link_overlap")))

    lines.append("")
    lines.append("### 2.5 Spatial Coverage Analysis (基于SHP)")
    spatial = dynamic_report.get("spatial_coverage_analysis", {})
    
    # SpeedBands 空间统计
    if "speedbands_spatial" in spatial:
        sb = spatial["speedbands_spatial"]
        lines.append(f"- **SpeedBands SHP**: {spatial.get('speed_links_shp', 'N/A')}")
        lines.append(f"  - 路段数量: {sb.get('total_features', 'N/A')}")
        lines.append(f"  - 唯一LinkID数: {sb.get('unique_link_ids', 'N/A')}")
        if "unique_road_names" in sb:
            lines.append(f"  - 唯一道路名数: {sb.get('unique_road_names', 'N/A')}")
        lines.append(f"  - 总长度: {sb.get('total_length_km', 'N/A')} km")
    
    # TrafficFlow 空间统计
    if "trafficflow_spatial" in spatial:
        tf = spatial["trafficflow_spatial"]
        lines.append(f"- **TrafficFlow SHP**: {spatial.get('flow_links_shp', 'N/A')}")
        lines.append(f"  - 路段数量: {tf.get('total_features', 'N/A')}")
        lines.append(f"  - 唯一LinkID数: {tf.get('unique_link_ids', 'N/A')}")
        lines.append(f"  - 总长度: {tf.get('total_length_km', 'N/A')} km")
    
    # 静态-动态覆盖度
    if "static_dynamic_overlap" in spatial:
        sdo = spatial["static_dynamic_overlap"]
        lines.append(f"- **与静态路网重叠度**:")
        if "static_total_length_km" in sdo:
            lines.append(f"  - 静态路网总长度: {sdo['static_total_length_km']} km")
        if "speedbands_coverage" in sdo:
            sc = sdo["speedbands_coverage"]
            lines.append(f"  - SpeedBands覆盖长度: {sc.get('covered_length_km', 'N/A')} km")
            lines.append(f"  - SpeedBands覆盖率: {round(sc.get('coverage_ratio', 0)*100, 1)}%")
            if "interpretation" in sc:
                lines.append(f"  - 评估: {sc['interpretation']}")
        if "trafficflow_coverage" in sdo:
            fc = sdo["trafficflow_coverage"]
            lines.append(f"  - TrafficFlow覆盖长度: {fc.get('covered_length_km', 'N/A')} km")
            lines.append(f"  - TrafficFlow覆盖率: {round(fc.get('coverage_ratio', 0)*100, 1)}%")
            if "interpretation" in fc:
                lines.append(f"  - 评估: {fc['interpretation']}")
    
    # Speed-Flow 空间重叠
    if "speed_flow_spatial_overlap" in spatial:
        sfo = spatial["speed_flow_spatial_overlap"]
        lines.append(f"- **SpeedBands与TrafficFlow空间重叠**:")
        if "link_id_overlap" in sfo:
            lio = sfo["link_id_overlap"]
            lines.append(f"  - SpeedBands LinkID数: {lio.get('speed_links', 'N/A')}")
            lines.append(f"  - TrafficFlow LinkID数: {lio.get('flow_links', 'N/A')}")
            lines.append(f"  - 共同LinkID数: {lio.get('common_links', 'N/A')}")
            lines.append(f"  - 相对SpeedBands的重叠率: {round(lio.get('overlap_ratio_to_speed', 0)*100, 1)}%")
            lines.append(f"  - 相对TrafficFlow的重叠率: {round(lio.get('overlap_ratio_to_flow', 0)*100, 1)}%")

    lines.append("")
    lines.append("### 2.6 Static-Dynamic Key Risk")
    lines.append(str(dynamic_report.get("static_dynamic_key_risk")))

    lines.append("")
    lines.append("## 3. Population / HDB / POI / LandUse Audit")
    lines.append("")
    lines.append("### 3.1 Population Raster")
    for k, v in pop_report.items():
        lines.append(f"- {k}: {v}")

    lines.append("")
    lines.append("### 3.2 Demand Proxy Data")
    keys = [
        "hdb_file", "hdb_records", "hdb_total_dwelling_units",
        "hdb_zone_col", "hdb_units_col", "hdb_has_geometry",
        "poi_file", "poi_records", "poi_zone_col", "poi_has_geometry",
        "landuse_file", "landuse_records", "landuse_type_col_guess",
    ]
    for k in keys:
        lines.append(f"- {k}: {demand_report.get(k)}")

    lines.append("")
    lines.append("### 3.3 Proxy OD")
    lines.append(str(demand_report.get("proxy_od")))

    lines.append("")
    lines.append("## 4. Risk Assessment")
    risks = risk_level_from_reports(static_report, dynamic_report, demand_report)
    for level, msg in risks:
        lines.append(f"- **{level}风险**: {msg}")

    lines.append("")
    lines.append("## 5. Suggested Interpretation")
    lines.append("")
    lines.append("### 5.1 Lane-level map feasibility")
    lines.append("- `largest_component_node_ratio > 0.85`：RoadSectionLine基本适合构图。")
    lines.append("- `road_length_with_lane_marking_ratio > 0.6`：车道标线覆盖较好，可尝试大范围车道中心线生成。")
    lines.append("- `roads_with_arrow_ratio` 越高，越有利于自动识别车道转向。")
    lines.append("")
    lines.append("### 5.2 Dynamic calibration feasibility")
    lines.append("- SpeedBands和TrafficFlow都能读出LinkID，并且LinkID重合度高，则适合联合校准。")
    lines.append("- 如果动态LinkID无法与静态RoadSectionLine匹配，则需要优先解决LinkID—Geometry映射。")
    lines.append("- **基于SHP的空间覆盖分析**：")
    lines.append("  - `coverage_ratio > 0.7`：动态数据覆盖度良好，可进行大范围校准。")
    lines.append("  - `coverage_ratio 0.3-0.7`：中等覆盖，主要干道可能有数据，但需要补充支路。")
    lines.append("  - `coverage_ratio < 0.3`：覆盖率低，只能进行局部或关键路段校准。")
    lines.append("  - SpeedBands与TrafficFlow的LinkID重叠率越高，越有利于速度和流量联合校准。")
    lines.append("")
    lines.append("### 5.3 OD synthesis feasibility")
    lines.append("- HDB、POI、人口栅格、土地利用均可读出，则具备构建初始OD的基础。")
    lines.append("- 当前proxy OD只是数据检查结果，不代表正式交通需求。")

    report_path = out_dir / "report.md"
    report_path.write_text("\n".join(lines), encoding="utf-8")
    return report_path


def main():
    out_dir = Path(CONFIG["output_root"])
    ensure_dir(out_dir)

    print("[1/4] Auditing static map data...")
    static_report = audit_static_map(CONFIG["static_root"], out_dir)

    print("[2/4] Auditing dynamic traffic data...")
    dynamic_report = audit_dynamic_data(CONFIG["dynamic_root"], static_report, out_dir)

    print("[3/4] Auditing population raster...")
    pop_report = audit_population_raster(CONFIG["other_root"], out_dir)

    print("[4/4] Auditing HDB/POI/LandUse and building proxy OD...")
    demand_report = audit_hdb_poi_landuse(CONFIG["other_root"], out_dir)

    report_path = write_report(static_report, dynamic_report, pop_report, demand_report, out_dir)

    print("")
    print("Audit finished.")
    print(f"Report saved to: {report_path.resolve()}")
    print("Other CSV outputs are saved in:", out_dir.resolve())


if __name__ == "__main__":
    main()