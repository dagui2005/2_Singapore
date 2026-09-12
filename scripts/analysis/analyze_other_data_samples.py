"""
深入分析OTHER文件夹中的关键数据文件
提取字段信息和样例数据
"""

import pandas as pd
import json
import os

BASE_DIR = r"D:\Luan\2026-05\2_Singapore\Static_ 2026_03\OTHER"

def analyze_acra_sample():
    """分析ACRA企业数据样例"""
    print("="*80)
    print("分析 ACRA 企业信息数据")
    print("="*80)
    
    sample_file = os.path.join(BASE_DIR, "goverment_open", "ACRAInformationonCorporateEntitiesA.csv")
    
    if os.path.exists(sample_file):
        # 只读取前5行
        df = pd.read_csv(sample_file, nrows=5)
        
        print(f"\n文件: {os.path.basename(sample_file)}")
        print(f"列数: {len(df.columns)}")
        print(f"列名:")
        for i, col in enumerate(df.columns, 1):
            print(f"  {i}. {col}")
        
        print(f"\n样例数据 (前3行):")
        print(df.head(3).to_string())
        
        return {
            'columns': list(df.columns),
            'sample': df.head(3).to_dict('records')
        }
    
    return None

def analyze_health_facilities():
    """分析医疗设施数据"""
    print("\n" + "="*80)
    print("分析 医疗设施数据")
    print("="*80)
    
    health_dir = os.path.join(BASE_DIR, "goverment_open", "HealthFacilitiesandBedsinInpatientFacilities")
    
    for filename in os.listdir(health_dir):
        if filename.endswith('.csv'):
            filepath = os.path.join(health_dir, filename)
            df = pd.read_csv(filepath, nrows=3)
            
            print(f"\n文件: {filename}")
            print(f"列名: {', '.join(df.columns)}")
            print(f"样例:")
            print(df.head(2).to_string())

def analyze_geojson_sample():
    """分析GeoJSON文件样例"""
    print("\n" + "="*80)
    print("分析 GeoJSON 空间数据")
    print("="*80)
    
    geojson_files = [
        "HawkerCentresGEOJSON.geojson",
        "LTAMRTStationExitGEOJSON.geojson",
        "TouristAttractions.geojson"
    ]
    
    gov_dir = os.path.join(BASE_DIR, "goverment_open")
    
    for filename in geojson_files:
        filepath = os.path.join(gov_dir, filename)
        
        if os.path.exists(filepath):
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            print(f"\n文件: {filename}")
            print(f"类型: {data.get('type')}")
            print(f"要素数量: {len(data.get('features', []))}")
            
            if data.get('features') and len(data['features']) > 0:
                first = data['features'][0]
                print(f"几何类型: {first.get('geometry', {}).get('type')}")
                
                if 'properties' in first:
                    print(f"属性字段:")
                    for key in first['properties'].keys():
                        print(f"  - {key}")
                    
                    print(f"样例属性 (第一个要素):")
                    for key, value in list(first['properties'].items())[:5]:
                        print(f"  {key}: {value}")

def analyze_ltsg_dataset():
    """分析LTSG数据集"""
    print("\n" + "="*80)
    print("分析 LTSG 数据集 (siteselect_sg-main)")
    print("="*80)
    
    dataset_dir = os.path.join(BASE_DIR, "siteselect_sg-main", "dataset")
    
    files_info = {
        'poi.csv': '兴趣点数据',
        'hdb.csv': 'HDB组屋数据',
        'bus_line.csv': '巴士线路数据',
        'bus_vol.csv': '巴士客流量数据',
        'mrt.csv': '地铁数据'
    }
    
    for filename, description in files_info.items():
        filepath = os.path.join(dataset_dir, filename)
        
        if os.path.exists(filepath):
            df = pd.read_csv(filepath, nrows=3)
            
            print(f"\n{description} ({filename})")
            print(f"总列数: {len(df.columns)}")
            print(f"列名: {', '.join(df.columns)}")
            print(f"样例数据:")
            print(df.head(2).to_string())
            print()

def generate_enhanced_report():
    """生成增强版报告"""
    
    print("开始深入分析数据文件...\n")
    
    acra_info = analyze_acra_sample()
    analyze_health_facilities()
    analyze_geojson_sample()
    analyze_ltsg_dataset()
    
    print("\n" + "="*80)
    print("✅ 分析完成！")
    print("="*80)
    print("\n建议:")
    print("1. 使用QGIS或ArcGIS查看GeoJSON空间数据")
    print("2. 使用Python pandas分析CSV数据")
    print("3. 人口栅格数据需要使用rasterio或GIS软件打开")
    print("4. ACRA数据量大，建议使用数据库导入后查询")

if __name__ == "__main__":
    generate_enhanced_report()
