"""
从LTA动态交通数据JSON文件中提取静态路段信息并生成Shapefile
- 只保留LinkID、StartLon、StartLat、EndLon、EndLat、RoadName、RoadCategory/RoadCat字段
- 去除重复的LinkID（只保留第一次出现的记录）
- 生成包含线几何的SHP文件
"""

import json
import pandas as pd
import geopandas as gpd
from shapely.geometry import LineString
from pathlib import Path
import logging

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def extract_static_links_from_speedbands(json_path, output_path):
    """
    从TrafficSpeedBands_v4.json提取静态路段信息
    
    Args:
        json_path: JSON文件路径
        output_path: 输出SHP文件路径
    """
    logger.info(f"开始处理: {json_path}")
    
    # 读取JSON文件
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    logger.info(f"读取到 {len(data)} 条记录")
    
    # 转换为DataFrame
    df = pd.DataFrame(data)
    
    # 选择需要的字段（注意：RoadCategory字段名）
    columns_to_keep = ['LinkID', 'StartLon', 'StartLat', 'EndLon', 'EndLat', 
                       'RoadName', 'RoadCategory']
    
    # 检查字段是否存在
    available_columns = [col for col in columns_to_keep if col in df.columns]
    logger.info(f"可用字段: {available_columns}")
    
    df_static = df[available_columns].copy()
    
    # 去除重复的LinkID，保留第一次出现的记录
    before_count = len(df_static)
    df_static = df_static.drop_duplicates(subset=['LinkID'], keep='first')
    after_count = len(df_static)
    logger.info(f"去重前: {before_count} 条记录, 去重后: {after_count} 条记录")
    
    # 转换坐标为数值类型
    df_static['StartLon'] = pd.to_numeric(df_static['StartLon'], errors='coerce')
    df_static['StartLat'] = pd.to_numeric(df_static['StartLat'], errors='coerce')
    df_static['EndLon'] = pd.to_numeric(df_static['EndLon'], errors='coerce')
    df_static['EndLat'] = pd.to_numeric(df_static['EndLat'], errors='coerce')
    
    # 删除坐标无效的记录
    df_static = df_static.dropna(subset=['StartLon', 'StartLat', 'EndLon', 'EndLat'])
    logger.info(f"有效坐标记录数: {len(df_static)}")
    
    # 创建LineString几何对象
    geometries = []
    for idx, row in df_static.iterrows():
        line = LineString([
            (row['StartLon'], row['StartLat']),
            (row['EndLon'], row['EndLat'])
        ])
        geometries.append(line)
    
    # 创建GeoDataFrame
    gdf = gpd.GeoDataFrame(df_static, geometry=geometries, crs="EPSG:4326")
    
    # 保存为Shapefile
    gdf.to_file(output_path, driver='ESRI Shapefile', encoding='utf-8')
    logger.info(f"✓ 已保存: {output_path}")
    logger.info(f"  记录数: {len(gdf)}")
    logger.info(f"  字段: {list(gdf.columns)}")
    
    return gdf


def extract_static_links_from_trafficflow(json_path, output_path):
    """
    从TrafficFlow_Data.json提取静态路段信息
    
    Args:
        json_path: JSON文件路径
        output_path: 输出SHP文件路径
    """
    logger.info(f"开始处理: {json_path}")
    
    # 读取JSON文件
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # TrafficFlow_Data的结构是 {"LastUpdatedDate": "...", "Value": [...]}
    traffic_records = data.get('Value', [])
    logger.info(f"读取到 {len(traffic_records)} 条记录")
    
    # 转换为DataFrame
    df = pd.DataFrame(traffic_records)
    
    # 选择需要的字段（注意：RoadCat字段名）
    columns_to_keep = ['LinkID', 'StartLon', 'StartLat', 'EndLon', 'EndLat', 
                       'RoadName', 'RoadCat']
    
    # 检查字段是否存在
    available_columns = [col for col in columns_to_keep if col in df.columns]
    logger.info(f"可用字段: {available_columns}")
    
    df_static = df[available_columns].copy()
    
    # 重命名RoadCat为RoadCategory以保持一致性
    if 'RoadCat' in df_static.columns:
        df_static = df_static.rename(columns={'RoadCat': 'RoadCategory'})
    
    # 去除重复的LinkID，保留第一次出现的记录
    before_count = len(df_static)
    df_static = df_static.drop_duplicates(subset=['LinkID'], keep='first')
    after_count = len(df_static)
    logger.info(f"去重前: {before_count} 条记录, 去重后: {after_count} 条记录")
    
    # 转换坐标为数值类型
    df_static['StartLon'] = pd.to_numeric(df_static['StartLon'], errors='coerce')
    df_static['StartLat'] = pd.to_numeric(df_static['StartLat'], errors='coerce')
    df_static['EndLon'] = pd.to_numeric(df_static['EndLon'], errors='coerce')
    df_static['EndLat'] = pd.to_numeric(df_static['EndLat'], errors='coerce')
    
    # 删除坐标无效的记录
    df_static = df_static.dropna(subset=['StartLon', 'StartLat', 'EndLon', 'EndLat'])
    logger.info(f"有效坐标记录数: {len(df_static)}")
    
    # 创建LineString几何对象
    geometries = []
    for idx, row in df_static.iterrows():
        line = LineString([
            (row['StartLon'], row['StartLat']),
            (row['EndLon'], row['EndLat'])
        ])
        geometries.append(line)
    
    # 创建GeoDataFrame
    gdf = gpd.GeoDataFrame(df_static, geometry=geometries, crs="EPSG:4326")
    
    # 保存为Shapefile
    gdf.to_file(output_path, driver='ESRI Shapefile', encoding='utf-8')
    logger.info(f"✓ 已保存: {output_path}")
    logger.info(f"  记录数: {len(gdf)}")
    logger.info(f"  字段: {list(gdf.columns)}")
    
    return gdf


def main():
    """主函数"""
    # 基础路径
    base_dir = Path(r"D:\Luan\2026-05\2_Singapore")
    historical_dir = base_dir / "Dynamic_2026_03_16" / "historical_data"
    output_dir = base_dir / "Dynamic_2026_03_16" / "static_links"
    
    # 创建输出目录
    output_dir.mkdir(parents=True, exist_ok=True)
    
    logger.info("=" * 80)
    logger.info("从LTA动态交通数据提取静态路段信息")
    logger.info("=" * 80)
    
    # 处理TrafficSpeedBands_v4.json
    speedbands_json = historical_dir / "TrafficSpeedBands_v4.json"
    speedbands_shp = output_dir / "TrafficSpeedBands_Links.shp"
    
    if speedbands_json.exists():
        gdf_speedbands = extract_static_links_from_speedbands(
            speedbands_json, speedbands_shp
        )
    else:
        logger.error(f"文件不存在: {speedbands_json}")
    
    logger.info("")
    
    # 处理TrafficFlow_Data.json
    trafficflow_json = historical_dir / "TrafficFlow_Data.json"
    trafficflow_shp = output_dir / "TrafficFlow_Links.shp"
    
    if trafficflow_json.exists():
        gdf_trafficflow = extract_static_links_from_trafficflow(
            trafficflow_json, trafficflow_shp
        )
    else:
        logger.error(f"文件不存在: {trafficflow_json}")
    
    logger.info("")
    logger.info("=" * 80)
    logger.info("处理完成！")
    logger.info("=" * 80)
    logger.info(f"输出目录: {output_dir}")
    logger.info(f"生成的文件:")
    logger.info(f"  1. {speedbands_shp.name}")
    logger.info(f"  2. {trafficflow_shp.name}")


if __name__ == "__main__":
    main()
