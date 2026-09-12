"""
数据处理示例 - 展示如何读取和分析下载的LTA数据
"""

import json
import os
from pathlib import Path
import pandas as pd

OUTPUT_DIR = "Dynamic_2026_03_16"


def load_json_file(filepath):
    """加载JSON文件"""
    with open(filepath, 'r', encoding='utf-8') as f:
        return json.load(f)


def example_bus_stops():
    """示例：分析巴士站点数据"""
    print("\n" + "=" * 80)
    print("示例1：巴士站点数据分析")
    print("=" * 80)
    
    filepath = os.path.join(OUTPUT_DIR, "historical_data", "BusStops.json")
    
    if not os.path.exists(filepath):
        print(f"文件不存在: {filepath}")
        return
    
    data = load_json_file(filepath)
    
    # 转换为DataFrame
    df = pd.DataFrame(data)
    
    print(f"\n总巴士站数量: {len(df)}")
    print(f"\n前5个巴士站:")
    print(df.head())
    
    print(f"\n字段信息:")
    print(df.columns.tolist())
    
    # 统计道路名称
    if 'RoadName' in df.columns:
        print(f"\n最常见的道路名称 (Top 10):")
        print(df['RoadName'].value_counts().head(10))


def example_taxi_availability():
    """示例：分析出租车位置数据"""
    print("\n" + "=" * 80)
    print("示例2：出租车可用性分析")
    print("=" * 80)
    
    # 查找最新的出租车数据文件
    realtime_dir = os.path.join(OUTPUT_DIR, "realtime_monitoring")
    
    if not os.path.exists(realtime_dir):
        print(f"目录不存在: {realtime_dir}")
        return
    
    files = [f for f in os.listdir(realtime_dir) if f.startswith('TaxiAvailability')]
    
    if not files:
        print("未找到出租车数据文件")
        return
    
    # 使用最新的文件
    latest_file = sorted(files)[-1]
    filepath = os.path.join(realtime_dir, latest_file)
    
    print(f"\n使用文件: {latest_file}")
    
    data = load_json_file(filepath)
    
    if isinstance(data, list):
        print(f"可用出租车数量: {len(data)}")
        
        # 转换为DataFrame
        df = pd.DataFrame(data)
        
        if 'Latitude' in df.columns and 'Longitude' in df.columns:
            print(f"\n位置范围:")
            print(f"  纬度: {df['Latitude'].min():.4f} - {df['Latitude'].max():.4f}")
            print(f"  经度: {df['Longitude'].min():.4f} - {df['Longitude'].max():.4f}")
            
            # 计算中心点
            center_lat = df['Latitude'].mean()
            center_lon = df['Longitude'].mean()
            print(f"\n平均位置: ({center_lat:.4f}, {center_lon:.4f})")


def example_traffic_incidents():
    """示例：分析交通事故数据"""
    print("\n" + "=" * 80)
    print("示例3：交通事故分析")
    print("=" * 80)
    
    filepath = os.path.join(OUTPUT_DIR, "historical_data", "TrafficIncidents.json")
    
    if not os.path.exists(filepath):
        print(f"文件不存在: {filepath}")
        return
    
    data = load_json_file(filepath)
    
    if isinstance(data, list):
        print(f"当前事故数量: {len(data)}")
        
        df = pd.DataFrame(data)
        
        if 'Type' in df.columns:
            print(f"\n事故类型分布:")
            print(df['Type'].value_counts())
        
        if 'Message' in df.columns:
            print(f"\n前5条事故信息:")
            for i, msg in enumerate(df['Message'].head(), 1):
                print(f"  {i}. {msg}")


def example_carpark_availability():
    """示例：分析停车场空位数据"""
    print("\n" + "=" * 80)
    print("示例4：停车场空位分析")
    print("=" * 80)
    
    filepath = os.path.join(OUTPUT_DIR, "historical_data", "CarparkAvailability_v2.json")
    
    if not os.path.exists(filepath):
        print(f"文件不存在: {filepath}")
        return
    
    data = load_json_file(filepath)
    
    if isinstance(data, list):
        df = pd.DataFrame(data)
        
        print(f"停车场总数: {len(df)}")
        
        if 'Agency' in df.columns:
            print(f"\n按机构分类:")
            print(df['Agency'].value_counts())
        
        if 'AvailableLots' in df.columns and 'LotType' in df.columns:
            print(f"\n各类型车位平均空位数:")
            avg_lots = df.groupby('LotType')['AvailableLots'].mean()
            print(avg_lots)
            
            print(f"\n空位最多的前10个停车场:")
            top10 = df.nlargest(10, 'AvailableLots')[['CarParkID', 'Development', 'AvailableLots', 'LotType']]
            print(top10.to_string(index=False))


def example_passenger_volume():
    """示例：分析客流量数据"""
    print("\n" + "=" * 80)
    print("示例5：客流量数据分析")
    print("=" * 80)
    
    filepath = os.path.join(OUTPUT_DIR, "historical_data", "PassengerVolume_BusStops_202603.json")
    
    if not os.path.exists(filepath):
        print(f"文件不存在: {filepath}")
        return
    
    data = load_json_file(filepath)
    
    # 客流量API返回的是下载链接
    if isinstance(data, dict) and 'Link' in data:
        print(f"客流量数据下载链接:")
        print(data['Link'])
        print(f"\n注意: 链接5分钟后过期，需要及时下载")
        print("下载后可以使用pandas读取CSV文件进行分析")


def example_station_crowd_density():
    """示例：分析站台拥挤度"""
    print("\n" + "=" * 80)
    print("示例6：站台拥挤度分析")
    print("=" * 80)
    
    filepath = os.path.join(OUTPUT_DIR, "realtime_monitoring", "StationCrowdDensity_RealTime.json")
    
    if not os.path.exists(filepath):
        print(f"文件不存在: {filepath}")
        return
    
    data = load_json_file(filepath)
    
    if isinstance(data, dict):
        print(f"监控的线路数量: {len(data)}")
        
        for line, line_data in data.items():
            print(f"\n线路 {line}:")
            if isinstance(line_data, list) and len(line_data) > 0:
                # 统计拥挤度等级
                crowd_levels = {}
                for station in line_data:
                    if 'CrowdLevel' in station:
                        level = station['CrowdLevel']
                        crowd_levels[level] = crowd_levels.get(level, 0) + 1
                
                print(f"  车站数量: {len(line_data)}")
                print(f"  拥挤度分布: {crowd_levels}")


def list_all_files():
    """列出所有下载的文件"""
    print("\n" + "=" * 80)
    print("已下载的文件列表")
    print("=" * 80)
    
    if not os.path.exists(OUTPUT_DIR):
        print(f"输出目录不存在: {OUTPUT_DIR}")
        return
    
    for root, dirs, files in os.walk(OUTPUT_DIR):
        level = root.replace(OUTPUT_DIR, '').count(os.sep)
        indent = '  ' * level
        print(f"{indent}{os.path.basename(root)}/")
        
        subindent = '  ' * (level + 1)
        for file in sorted(files):
            if file.endswith('.json'):
                filepath = os.path.join(root, file)
                size = os.path.getsize(filepath)
                size_kb = size / 1024
                print(f"{subindent}{file} ({size_kb:.1f} KB)")


def main():
    """运行所有示例"""
    print("=" * 80)
    print("LTA DataMall 数据处理示例")
    print("=" * 80)
    
    # 首先列出所有文件
    list_all_files()
    
    # 运行各个示例
    examples = [
        ("巴士站点分析", example_bus_stops),
        ("出租车可用性分析", example_taxi_availability),
        ("交通事故分析", example_traffic_incidents),
        ("停车场空位分析", example_carpark_availability),
        ("客流量分析", example_passenger_volume),
        ("站台拥挤度分析", example_station_crowd_density),
    ]
    
    print("\n请选择要运行的示例（输入编号，多个用逗号分隔，或按回车运行全部）:")
    for i, (name, _) in enumerate(examples, 1):
        print(f"  {i}. {name}")
    
    choice = input("\n选择: ").strip()
    
    if choice:
        try:
            indices = [int(x.strip()) - 1 for x in choice.split(',')]
            selected_examples = [examples[i] for i in indices if 0 <= i < len(examples)]
        except:
            print("无效输入，运行全部示例")
            selected_examples = examples
    else:
        selected_examples = examples
    
    for name, func in selected_examples:
        try:
            func()
        except Exception as e:
            print(f"\n示例 '{name}' 运行失败: {e}")
            import traceback
            traceback.print_exc()
    
    print("\n" + "=" * 80)
    print("示例运行完成")
    print("=" * 80)


if __name__ == "__main__":
    main()
