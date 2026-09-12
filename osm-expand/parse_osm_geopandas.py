"""
解析OSM SHP文件中的other_tags字段，将其拆分为多个独立字段
使用GeoPandas处理（更可靠）
"""
import os
import re
from pathlib import Path
from collections import defaultdict

try:
    import geopandas as gpd
    import pandas as pd
except ImportError:
    print("正在安装必要的库...")
    os.system("pip install geopandas pandas")
    import geopandas as gpd
    import pandas as pd


def parse_other_tags(other_tags_str):
    """
    解析other_tags字符串，提取键值对
    
    实际格式: "key1"=>"value1","key2"=>"value2"
    
    Args:
        other_tags_str: other_tags字段的字符串
        
    Returns:
        dict: 解析后的键值对字典
    """
    result = {}
    
    if not other_tags_str or pd.isna(other_tags_str) or len(str(other_tags_str).strip()) == 0:
        return result
    
    content = str(other_tags_str)
    
    # 使用正则表达式匹配 "key"=>"value" 模式
    pattern = r'"([^"]+)"\s*=>\s*"([^"]*)"'
    matches = re.findall(pattern, content)
    
    for key, value in matches:
        # 清理键名：替换特殊字符为下划线，但保留冒号和连字符
        clean_key = re.sub(r'[^a-zA-Z0-9_:\-]', '_', key)
        result[clean_key] = value
    
    return result


def process_shp_file(shp_path, min_frequency=0.01, max_fields=200):
    """
    处理单个SHP文件，解析other_tags字段
    
    Args:
        shp_path: SHP文件路径
        min_frequency: 最小出现频率（默认1%）
        max_fields: 最大新增字段数（默认200）
        
    Returns:
        bool: 是否成功
    """
    print(f"\n{'='*80}")
    print(f"处理文件: {os.path.basename(shp_path)}")
    print(f"{'='*80}")
    
    try:
        # 读取SHP文件
        print("正在读取SHP文件...")
        df = None
        encodings = ['utf-8', 'latin1', 'cp1252', 'iso-8859-1']
        
        for encoding in encodings:
            try:
                df = gpd.read_file(shp_path, encoding=encoding)
                print(f"✓ 使用编码 '{encoding}' 成功读取 {len(df)} 条记录")
                break
            except Exception as e:
                print(f"  尝试编码 '{encoding}' 失败")
                continue
        
        if df is None:
            raise Exception("无法使用任何编码读取文件")
        
        print(f"原始字段数: {len(df.columns)}")
        
        if 'other_tags' not in df.columns:
            print("警告: 文件中没有 'other_tags' 字段")
            return False
        
        # 第一步：解析所有记录的other_tags
        print("\n正在解析 other_tags 字段...")
        all_parsed = []
        key_count = defaultdict(int)
        
        for i, row in df.iterrows():
            parsed = parse_other_tags(row['other_tags'])
            all_parsed.append(parsed)
            
            for key in parsed.keys():
                key_count[key] += 1
            
            if (i + 1) % 10000 == 0:
                print(f"  已解析 {i + 1}/{len(df)} 条记录")
        
        print(f"✓ 完成解析 {len(df)} 条记录")
        print(f"发现 {len(key_count)} 个唯一字段")
        
        # 第二步：筛选常见字段
        total_records = len(df)
        min_count = int(total_records * min_frequency)
        common_keys = [(key, count) for key, count in key_count.items() if count >= min_count]
        
        # 按出现频率排序，取前max_fields个
        common_keys.sort(key=lambda x: x[1], reverse=True)
        selected_keys = [key for key, count in common_keys[:max_fields]]
        
        print(f"\n筛选条件: 最小出现次数 {min_count} ({min_frequency*100}%)")
        print(f"符合条件的字段: {len(common_keys)} 个")
        print(f"最终选择字段: {len(selected_keys)} 个（最多{max_fields}个）")
        
        # 显示选中的字段
        print(f"\n选中的字段（按频率排序，前30个）:")
        for i, (key, count) in enumerate(common_keys[:min(len(selected_keys), 30)], 1):
            percentage = (count / total_records) * 100
            print(f"  {i:2d}. {key:40s} ({count:6d}条, {percentage:5.1f}%)")
        
        if len(selected_keys) < len(common_keys):
            print(f"  ... 还有 {len(common_keys) - len(selected_keys)} 个字段")
        
        # 第三步：创建新列
        print("\n正在添加新字段...")
        for key in selected_keys:
            col_values = [parsed.get(key, '') for parsed in all_parsed]
            df[key] = col_values
        
        print(f"✓ 添加了 {len(selected_keys)} 个新字段")
        
        # 第四步：删除other_tags列
        df = df.drop(columns=['other_tags'])
        print(f"处理后总字段数: {len(df.columns)}（包含geometry）")
        
        # 第五步：保存文件
        base_path = Path(shp_path)
        output_path = str(base_path.parent / f"{base_path.stem}_expanded{base_path.suffix}")
        
        # 删除已存在的输出文件
        for ext in ['.shp', '.shx', '.dbf', '.prj']:
            file_to_delete = output_path.replace('.shp', ext)
            if os.path.exists(file_to_delete):
                try:
                    os.remove(file_to_delete)
                except Exception as e:
                    print(f"警告: 无法删除 {file_to_delete}: {e}")
        
        print(f"\n保存到: {output_path}")
        df.to_file(output_path, driver='ESRI Shapefile', encoding='utf-8')
        print(f"✓ 成功保存文件")
        
        # 验证
        df_verify = gpd.read_file(output_path)
        print(f"✓ 验证: 输出文件包含 {len(df_verify)} 条记录, {len(df_verify.columns)} 个字段")
        
        return True
        
    except Exception as e:
        print(f"错误: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """主函数"""
    osm_dir = r"D:\Luan\2026-05\2_Singapore\osm"
    
    files_to_process = [
        "osm-lines.shp",
        "osm-multiline.shp",
        "osm-points.shp",
        "osm-polygon.shp"
    ]
    
    print("="*80)
    print("OSM SHP文件 other_tags 字段解析工具 (GeoPandas版)")
    print("策略: 只保留出现频率>=1%的字段，最多200个字段")
    print("="*80)
    
    results = {}
    
    for filename in files_to_process:
        shp_path = os.path.join(osm_dir, filename)
        
        if not os.path.exists(shp_path):
            print(f"\n文件不存在: {shp_path}")
            continue
        
        success = process_shp_file(shp_path, min_frequency=0.01, max_fields=200)
        results[filename] = success
    
    print("\n" + "="*80)
    print("处理完成摘要")
    print("="*80)
    
    for filename, success in results.items():
        status = "成功" if success else "失败"
        symbol = "[OK]" if success else "[FAIL]"
        print(f"{symbol} {filename}: {status}")
    
    print("\n" + "="*80)
    print("所有文件处理完成！")
    print("="*80)


if __name__ == "__main__":
    main()
