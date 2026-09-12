"""
分析Static_2026_03/OTHER文件夹下的所有数据
生成详细的数据说明文档
"""

import os
import json
import csv
import pandas as pd
from pathlib import Path
from datetime import datetime

BASE_DIR = r"D:\Luan\2026-05\2_Singapore\Static_ 2026_03\OTHER"

def analyze_csv_file(filepath, max_rows=5):
    """分析CSV文件"""
    try:
        # 读取前几行
        df = pd.read_csv(filepath, nrows=max_rows)
        
        info = {
            'filename': os.path.basename(filepath),
            'size_mb': os.path.getsize(filepath) / 1024 / 1024,
            'total_rows': None,
            'columns': list(df.columns),
            'column_count': len(df.columns),
            'sample_data': df.head(max_rows).to_dict('records'),
            'dtypes': df.dtypes.astype(str).to_dict()
        }
        
        # 获取总行数
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            line_count = sum(1 for _ in f)
            info['total_rows'] = line_count - 1  # 减去表头
        
        return info
    except Exception as e:
        return {'filename': os.path.basename(filepath), 'error': str(e)}

def analyze_geojson_file(filepath):
    """分析GeoJSON文件"""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        info = {
            'filename': os.path.basename(filepath),
            'size_mb': os.path.getsize(filepath) / 1024 / 1024,
            'type': data.get('type', 'Unknown'),
            'feature_count': len(data.get('features', [])),
        }
        
        # 提取属性字段
        if data.get('features') and len(data['features']) > 0:
            first_feature = data['features'][0]
            if 'properties' in first_feature:
                info['properties'] = list(first_feature['properties'].keys())
                info['property_count'] = len(first_feature['properties'])
                info['sample_properties'] = first_feature['properties']
            
            # 几何类型
            if 'geometry' in first_feature:
                info['geometry_type'] = first_feature['geometry']['type']
        
        return info
    except Exception as e:
        return {'filename': os.path.basename(filepath), 'error': str(e)}

def analyze_tif_file(filepath):
    """分析TIFF文件（仅基本信息）"""
    try:
        size_mb = os.path.getsize(filepath) / 1024 / 1024
        
        # 尝试从文件名提取信息
        filename = os.path.basename(filepath)
        
        info = {
            'filename': filename,
            'size_mb': size_mb,
            'format': 'GeoTIFF',
            'note': '需要GIS软件查看详细内容'
        }
        
        # 从文件名解析可能的信息
        parts = filename.replace('.tif', '').split('_')
        if len(parts) >= 4:
            info['year'] = parts[2] if len(parts) > 2 else None
            info['resolution'] = parts[4] if len(parts) > 4 else None
        
        return info
    except Exception as e:
        return {'filename': os.path.basename(filepath), 'error': str(e)}

def analyze_directory(dir_path, level=0):
    """递归分析目录"""
    results = {
        'dir_name': os.path.basename(dir_path),
        'path': dir_path,
        'files': [],
        'subdirs': []
    }
    
    try:
        for item in sorted(os.listdir(dir_path)):
            item_path = os.path.join(dir_path, item)
            
            if os.path.isfile(item_path):
                ext = os.path.splitext(item)[1].lower()
                
                if ext == '.csv':
                    file_info = analyze_csv_file(item_path)
                    file_info['type'] = 'CSV'
                elif ext == '.geojson':
                    file_info = analyze_geojson_file(item_path)
                    file_info['type'] = 'GeoJSON'
                elif ext in ['.tif', '.tiff']:
                    file_info = analyze_tif_file(item_path)
                    file_info['type'] = 'GeoTIFF'
                else:
                    file_info = {
                        'filename': item,
                        'size_mb': os.path.getsize(item_path) / 1024 / 1024,
                        'type': ext.upper(),
                        'note': '未分析的文件类型'
                    }
                
                results['files'].append(file_info)
            
            elif os.path.isdir(item_path) and not item.startswith('.'):
                subdir_result = analyze_directory(item_path, level + 1)
                results['subdirs'].append(subdir_result)
    
    except Exception as e:
        results['error'] = str(e)
    
    return results

def generate_markdown_report(results, output_path):
    """生成Markdown报告"""
    
    report = []
    report.append("# 新加坡公开数据集说明文档\n")
    report.append(f"**数据来源**: Static_2026_03/OTHER 文件夹\n")
    report.append(f"**分析时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    report.append(f"**数据用途**: 互联网公开渠道下载的新加坡多源数据，可用于城市研究、交通分析、人口统计等\n\n")
    
    report.append("---\n\n")
    report.append("## 📁 目录结构\n\n")
    
    def print_tree(results, prefix="", level=0):
        """打印目录树"""
        indent = "  " * level
        report.append(f"{indent}- 📂 **{results['dir_name']}/**\n")
        
        for file_info in results.get('files', []):
            icon = "📄"
            if file_info.get('type') == 'CSV':
                icon = "📊"
            elif file_info.get('type') == 'GeoJSON':
                icon = "🗺️"
            elif file_info.get('type') == 'GeoTIFF':
                icon = "🌍"
            
            size_str = f"{file_info.get('size_mb', 0):.2f} MB"
            report.append(f"{indent}  {icon} `{file_info['filename']}` ({size_str})\n")
        
        for subdir in results.get('subdirs', []):
            print_tree(subdir, prefix, level + 1)
    
    print_tree(results)
    
    report.append("\n---\n\n")
    
    # 详细分析每个主要类别
    report.append("## 📊 详细数据说明\n\n")
    
    for subdir in results.get('subdirs', []):
        analyze_subdir_detail(subdir, report)
    
    # 写入文件
    with open(output_path, 'w', encoding='utf-8') as f:
        f.writelines(report)
    
    print(f"✓ 报告已生成: {output_path}")

def analyze_subdir_detail(subdir, report):
    """分析子目录详情"""
    
    dir_name = subdir['dir_name']
    report.append(f"### {dir_name}\n\n")
    
    if dir_name == 'Population':
        report.append("**数据类型**: 人口统计数据（栅格格式）\n\n")
        report.append("**来源**: 可能是WorldPop或其他人口分布数据集\n\n")
        report.append("**内容**:\n")
        report.append("- 新加坡人口分布的栅格数据\n")
        report.append("- 包含2025年和2026年两个年份\n")
        report.append("- 两种分辨率：100米和1公里\n")
        report.append("- 按年龄和性别结构化的人口数据\n\n")
        
        report.append("**文件格式**: GeoTIFF (.tif)\n\n")
        report.append("**适用场景**:\n")
        report.append("- 人口密度分析\n")
        report.append("- 城市规划和服务设施布局\n")
        report.append("- 交通需求预测\n")
        report.append("- 公共服务可达性分析\n\n")
        
        report.append("**使用建议**: 需要GIS软件（如QGIS、ArcGIS）或Python库（rasterio、geopandas）打开\n\n")
    
    elif dir_name == 'goverment_open':
        report.append("**数据类型**: 新加坡政府开放数据\n\n")
        report.append("**来源**: data.gov.sg 等新加坡政府开放数据平台\n\n")
        
        # 分类统计
        csv_files = [f for f in subdir['files'] if f.get('type') == 'CSV']
        geojson_files = [f for f in subdir['files'] if f.get('type') == 'GeoJSON']
        
        report.append(f"**文件统计**:\n")
        report.append(f"- CSV文件: {len(csv_files)} 个\n")
        report.append(f"- GeoJSON文件: {len(geojson_files)} 个\n\n")
        
        # ACRA企业数据
        acra_files = [f for f in csv_files if 'ACRA' in f['filename']]
        if acra_files:
            report.append("#### 🏢 ACRA企业信息数据\n\n")
            report.append(f"**文件数量**: {len(acra_files)} 个（按字母A-Z分组）\n\n")
            report.append("**内容**: 新加坡会计与企业管理局（ACRA）注册的企业实体信息\n\n")
            report.append("**可能包含字段**:\n")
            report.append("- 企业名称 (Entity Name)\n")
            report.append("- 企业编号 (UEN)\n")
            report.append("- 注册地址\n")
            report.append("- 企业类型\n")
            report.append("- 注册日期\n")
            report.append("- 经营状态\n\n")
            
            total_size = sum(f.get('size_mb', 0) for f in acra_files)
            report.append(f"**总大小**: {total_size:.1f} MB\n\n")
            report.append("**适用场景**: 商业分析、企业分布研究、经济活动分析\n\n")
        
        # Master Plan规划数据
        master_plan_files = [f for f in geojson_files if 'MasterPlan' in f['filename']]
        if master_plan_files:
            report.append("#### 🏗️ URA总体规划数据 (Master Plan 2019)\n\n")
            report.append(f"**文件数量**: {len(master_plan_files)} 个\n\n")
            report.append("**内容**: 新加坡市区重建局（URA）2019年总体规划的空间数据\n\n")
            
            for f in master_plan_files:
                report.append(f"- **{f['filename']}**: ")
                if 'LandUse' in f['filename']:
                    report.append("土地用途分区\n")
                elif 'Building' in f['filename']:
                    report.append("建筑物图层\n")
                elif 'RailLine' in f['filename']:
                    report.append("铁路线路\n")
                elif 'RailStation' in f['filename']:
                    report.append("铁路站点\n")
                elif 'PlanningArea' in f['filename']:
                    report.append("规划区域边界\n")
                elif 'Subzone' in f['filename']:
                    report.append("分区边界\n")
                else:
                    report.append("其他规划数据\n")
            
            report.append("\n**适用场景**: 城市规划、土地利用分析、开发潜力评估\n\n")
        
        # HDB组屋数据
        hdb_files = [f for f in geojson_files if 'HDB' in f['filename']]
        if hdb_files:
            report.append("#### 🏠 HDB组屋数据\n\n")
            for f in hdb_files:
                report.append(f"- **{f['filename']}**: HDB现有建筑物位置\n\n")
            
            report.append("**适用场景**: 住房研究、社区分析、公共服务规划\n\n")
        
        # 交通数据
        transport_files = [f for f in geojson_files if any(kw in f['filename'] for kw in ['MRT', 'Rail', 'Bus'])]
        if transport_files:
            report.append("#### 🚇 交通基础设施数据\n\n")
            for f in transport_files:
                report.append(f"- **{f['filename']}**\n")
            report.append("\n**适用场景**: 交通网络分析、可达性研究、TOD规划\n\n")
        
        # 设施数据
        facility_files = [f for f in geojson_files if any(kw in f['filename'] for kw in ['Hawker', 'Parks', 'Schools', 'Tourist', 'Health'])]
        if facility_files:
            report.append("#### 🏫 公共设施数据\n\n")
            for f in facility_files:
                desc = ""
                if 'Hawker' in f['filename']:
                    desc = "小贩中心位置"
                elif 'Parks' in f['filename']:
                    desc = "公园和自然保护区"
                elif 'Schools' in f['filename']:
                    desc = "学前班位置"
                elif 'Tourist' in f['filename']:
                    desc = "旅游景点"
                elif 'Health' in f['filename']:
                    desc = "医疗设施"
                
                report.append(f"- **{f['filename']}**: {desc}\n")
            
            report.append("\n**适用场景**: 公共服务可达性、生活便利性分析、旅游规划\n\n")
        
        # 健康设施CSV
        health_dir = next((sd for sd in subdir.get('subdirs', []) if 'Health' in sd['dir_name']), None)
        if health_dir:
            report.append("#### 🏥 医疗设施详细数据\n\n")
            for f in health_dir.get('files', []):
                if f.get('type') == 'CSV':
                    report.append(f"- **{f['filename']}**\n")
            report.append("\n**内容**: 医院、诊所、药房等医疗设施的详细信息和床位数量\n\n")
    
    elif dir_name == 'siteselect_sg-main':
        report.append("**数据类型**: Land & Transport Singapore (LTSG) 数据集\n\n")
        report.append("**来源**: 南洋理工大学研究项目\n\n")
        report.append("**论文**: [Site Selection via Learning Graph Convolutional Neural Networks](https://doi.org/10.3390/rs14153579)\n\n")
        
        dataset_dir = next((sd for sd in subdir.get('subdirs', []) if sd['dir_name'] == 'dataset'), None)
        if dataset_dir:
            report.append("**包含文件**:\n\n")
            
            for f in dataset_dir.get('files', []):
                if f.get('type') == 'CSV':
                    report.append(f"- **{f['filename']}**\n")
                    
                    if 'poi' in f['filename']:
                        report.append("  - 8,672个兴趣点（POI）\n")
                        report.append("  - 包含评分、评论数、类型、地址等\n")
                        report.append("  - 类型包括：学校、超市、公园、酒吧等\n\n")
                    
                    elif 'hdb' in f['filename']:
                        report.append("  - 12,442个HDB组屋建筑\n")
                        report.append("  - 包含楼号、地址、邮编、建造年份、单元数等\n\n")
                    
                    elif 'bus_line' in f['filename']:
                        report.append("  - 5,049个巴士站点及路线信息\n\n")
                    
                    elif 'bus_vol' in f['filename']:
                        report.append("  - 5,018个巴士站点的客流量数据\n")
                        report.append("  - 时间段：2021年7-9月\n\n")
                    
                    elif 'mrt' in f['filename']:
                        report.append("  - 166个地铁站及路线信息\n\n")
            
            report.append("\n**特点**: 所有数据都包含经纬度坐标和行政区划信息（分区、规划区、区域）\n\n")
            report.append("**适用场景**:\n")
            report.append("- 选址分析（商店、服务等）\n")
            report.append("- 城市活动模式研究\n")
            report.append("- 交通与土地利用关系分析\n")
            report.append("- 图神经网络空间分析\n")
            report.append("- 居住-就业平衡研究\n\n")
            
            report.append("**引用要求**: 使用时需引用上述论文\n\n")
    
    report.append("---\n\n")

def main():
    print("="*80)
    print("分析 Static_2026_03/OTHER 文件夹数据")
    print("="*80)
    
    print("\n正在扫描文件...")
    results = analyze_directory(BASE_DIR)
    
    print(f"\n找到 {len(results.get('subdirs', []))} 个主要类别")
    print("正在生成报告...")
    
    output_path = os.path.join(BASE_DIR, "OTHER_DATA_DOCUMENTATION.md")
    generate_markdown_report(results, output_path)
    
    print("\n✅ 分析完成！")
    print(f"📄 报告位置: {output_path}")

if __name__ == "__main__":
    main()
