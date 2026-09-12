"""
解析OSM SHP文件中的other_tags字段，将其拆分为多个独立字段
最终优化版 - 只保留常见字段以避免Shapefile限制
"""
import os
import re
from pathlib import Path
import shapefile
from collections import defaultdict


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
    
    if not other_tags_str or len(str(other_tags_str).strip()) == 0:
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
        max_fields: 最大新增字段数（默认200，避免超过Shapefile限制）
        
    Returns:
        bool: 是否成功
    """
    print(f"\n{'='*80}")
    print(f"处理文件: {os.path.basename(shp_path)}")
    print(f"{'='*80}")
    
    try:
        # 读取SHP文件
        sf = shapefile.Reader(shp_path, encoding='utf-8', encodingErrors='replace')
        
        # 获取字段信息
        field_names = [field[0] for field in sf.fields[1:]]
        original_field_count = len(field_names)
        print(f"原始字段数: {original_field_count}")
        
        if 'other_tags' not in field_names:
            print("警告: 文件中没有 'other_tags' 字段")
            return False
        
        other_tags_idx = field_names.index('other_tags')
        
        # 读取所有记录
        records = sf.records()
        total_records = len(records)
        print(f"总记录数: {total_records}")
        
        # 第一步：解析所有记录的other_tags，统计字段频率
        print("\n正在解析 other_tags 字段...")
        all_parsed = []
        key_count = defaultdict(int)
        
        for i, record in enumerate(records):
            other_tags_value = record[other_tags_idx]
            parsed = parse_other_tags(other_tags_value)
            all_parsed.append(parsed)
            
            for key in parsed.keys():
                key_count[key] += 1
            
            if (i + 1) % 10000 == 0:
                print(f"  已解析 {i + 1}/{total_records} 条记录")
        
        print(f"✓ 完成解析 {total_records} 条记录")
        print(f"发现 {len(key_count)} 个唯一字段")
        
        # 第二步：筛选常见字段
        min_count = int(total_records * min_frequency)
        common_keys = [(key, count) for key, count in key_count.items() if count >= min_count]
        
        # 按出现频率排序，取前max_fields个
        common_keys.sort(key=lambda x: x[1], reverse=True)
        selected_keys = [key for key, count in common_keys[:max_fields]]
        
        print(f"\n筛选条件: 最小出现次数 {min_count} ({min_frequency*100}%)")
        print(f"符合条件的字段: {len(common_keys)} 个")
        print(f"最终选择字段: {len(selected_keys)} 个（最多{max_fields}个）")
        
        # 显示选中的字段
        print(f"\n选中的字段（按频率排序）:")
        for i, (key, count) in enumerate(common_keys[:min(len(selected_keys), 30)], 1):
            percentage = (count / total_records) * 100
            marker = " ✓" if key in selected_keys else ""
            print(f"  {i:2d}. {key:40s} ({count:6d}条, {percentage:5.1f}%){marker}")
        
        if len(selected_keys) < len(common_keys):
            print(f"  ... 还有 {len(common_keys) - len(selected_keys)} 个字段未显示")
        
        # 第三步：创建输出文件路径
        base_path = Path(shp_path)
        output_path = str(base_path.parent / f"{base_path.stem}_expanded{base_path.suffix}")
        
        # 删除已存在的输出文件
        for ext in ['.shp', '.shx', '.dbf', '.prj']:
            file_to_delete = output_path.replace('.shp', ext)
            if os.path.exists(file_to_delete):
                try:
                    os.remove(file_to_delete)
                    print(f"\n已删除旧文件: {os.path.basename(file_to_delete)}")
                except Exception as e:
                    print(f"无法删除 {file_to_delete}: {e}")
                    return False
        
        print(f"\n保存到: {output_path}")
        
        # 第四步：创建新的SHP写入器
        w = shapefile.Writer(output_path)
        
        # 添加原有字段（排除other_tags）
        for field in sf.fields[1:]:
            field_name = field[0]
            if field_name != 'other_tags':
                w.field(*field)
        
        # 添加新字段（限制字段名长度为10）
        for key in selected_keys:
            short_key = key[:10]
            short_key = re.sub(r'[^a-zA-Z0-9_]', '_', short_key)
            w.field(short_key, 'C', 254)
        
        # 设置几何类型
        w._shapeType = sf.shapeType
        
        # 第五步：写入数据
        print("\n正在写入数据...")
        shapes = sf.shapes()
        
        for i, (record, shape) in enumerate(zip(records, shapes)):
            # 构建新记录
            new_record = []
            
            # 添加原有字段值（排除other_tags）
            for j, field_name in enumerate(field_names):
                if field_name != 'other_tags':
                    new_record.append(record[j])
            
            # 添加新字段值
            parsed = all_parsed[i]
            for key in selected_keys:
                value = parsed.get(key, '')
                new_record.append(value)
            
            # 写入记录和几何形状
            w.record(*new_record)
            if hasattr(shape, 'points') and shape.points:
                w._shapes.append(shape)
            
            if (i + 1) % 10000 == 0:
                print(f"  已写入 {i + 1}/{total_records} 条记录")
        
        w.close()
        print(f"✓ 成功保存文件")
        
        # 验证
        sf_verify = shapefile.Reader(output_path, encoding='utf-8', encodingErrors='replace')
        verify_fields = [f[0] for f in sf_verify.fields[1:]]
        print(f"✓ 验证: 输出文件包含 {len(sf_verify.records())} 条记录, {len(verify_fields)} 个字段")
        print(f"  原始字段: {original_field_count - 1} 个（排除other_tags）")
        print(f"  新增字段: {len(selected_keys)} 个")
        
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
    print("OSM SHP文件 other_tags 字段解析工具 (最终优化版)")
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
