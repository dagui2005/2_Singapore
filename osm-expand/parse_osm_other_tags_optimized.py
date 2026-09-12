"""
解析OSM SHP文件中的other_tags字段，将其拆分为多个独立字段
优化版本 - 基于实际数据格式
"""
import os
import re
from pathlib import Path
import shapefile
from collections import defaultdict


def parse_other_tags_optimized(other_tags_str):
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
    # 这个模式能正确处理各种情况
    pattern = r'"([^"]+)"\s*=>\s*"([^"]*)"'
    matches = re.findall(pattern, content)
    
    for key, value in matches:
        # 清理键名：替换特殊字符为下划线，但保留冒号（OSM标签常用）
        # 将非字母数字、下划线、冒号、连字符的字符替换为下划线
        clean_key = re.sub(r'[^a-zA-Z0-9_:\-]', '_', key)
        result[clean_key] = value
    
    return result


def process_shp_file(shp_path, output_path=None):
    """
    处理单个SHP文件，解析other_tags字段
    
    Args:
        shp_path: SHP文件路径
        output_path: 输出文件路径（可选）
        
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
        print(f"原始字段数: {len(field_names)}")
        
        if 'other_tags' not in field_names:
            print("警告: 文件中没有 'other_tags' 字段")
            return False
        
        other_tags_idx = field_names.index('other_tags')
        
        # 读取所有记录
        records = sf.records()
        shapes = sf.shapes()
        print(f"总记录数: {len(records)}")
        
        # 第一步：解析所有记录的other_tags，收集所有唯一的键
        print("\n正在解析 other_tags 字段...")
        all_parsed = []
        all_keys_set = set()
        
        for i, record in enumerate(records):
            other_tags_value = record[other_tags_idx]
            parsed = parse_other_tags_optimized(other_tags_value)
            all_parsed.append(parsed)
            all_keys_set.update(parsed.keys())
            
            if (i + 1) % 1000 == 0:
                print(f"  已解析 {i + 1}/{len(records)} 条记录")
        
        print(f"✓ 完成解析 {len(records)} 条记录")
        print(f"发现 {len(all_keys_set)} 个唯一字段")
        
        # 显示前20个最常见的字段
        key_count = defaultdict(int)
        for parsed in all_parsed:
            for key in parsed.keys():
                key_count[key] += 1
        
        sorted_keys = sorted(key_count.items(), key=lambda x: x[1], reverse=True)
        print(f"\n最常见的前20个字段:")
        for i, (key, count) in enumerate(sorted_keys[:20], 1):
            percentage = (count / len(records)) * 100
            print(f"  {i:2d}. {key:40s} ({count:5d}条, {percentage:5.1f}%)")
        
        # 第二步：创建新的字段列表（排除other_tags）
        new_field_names = [name for name in field_names if name != 'other_tags']
        
        # 添加解析出的新字段
        new_keys_sorted = sorted(all_keys_set)
        new_field_names.extend(new_keys_sorted)
        
        print(f"\n新增字段数: {len(new_keys_sorted)}")
        print(f"处理后总字段数: {len(new_field_names)}")
        
        # 第三步：创建新的SHP写入器
        if output_path is None:
            base_path = Path(shp_path)
            output_path = str(base_path.parent / f"{base_path.stem}_expanded{base_path.suffix}")
        
        print(f"\n保存到: {output_path}")
        
        # 复制字段定义（排除other_tags）
        w = shapefile.Writer(output_path)
        
        # 添加原有字段（排除other_tags）
        for field in sf.fields[1:]:  # 跳过第一个删除字段
            field_name = field[0]
            if field_name != 'other_tags':
                # field结构: (name, type code, size, decimal places)
                w.field(*field)
        
        # 添加新字段
        for key in new_keys_sorted:
            # Shapefile字段名最长10个字符
            short_key = key[:10] if len(key) > 10 else key
            # 确保字段名有效
            short_key = re.sub(r'[^a-zA-Z0-9_]', '_', short_key)
            w.field(short_key, 'C', 254)  # 字符型，长度254
        
        # 设置几何类型
        w._shapeType = sf.shapeType
        
        # 第四步：写入数据
        print("\n正在写入数据...")
        for i, (record, shape) in enumerate(zip(records, shapes)):
            # 构建新记录
            new_record = []
            
            # 添加原有字段值（排除other_tags）
            for j, field_name in enumerate(field_names):
                if field_name != 'other_tags':
                    new_record.append(record[j])
            
            # 添加新字段值
            parsed = all_parsed[i]
            for key in new_keys_sorted:
                value = parsed.get(key, '')
                new_record.append(value)
            
            # 写入记录和几何形状
            w.record(*new_record)
            if shape.points:
                w._shapes.append(shape)
            
            if (i + 1) % 1000 == 0:
                print(f"  已写入 {i + 1}/{len(records)} 条记录")
        
        w.close()
        print(f"✓ 成功保存文件")
        
        # 验证
        sf_verify = shapefile.Reader(output_path, encoding='utf-8', encodingErrors='replace')
        verify_fields = [f[0] for f in sf_verify.fields[1:]]
        print(f"✓ 验证: 输出文件包含 {len(sf_verify.records())} 条记录, {len(verify_fields)} 个字段")
        
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
    print("OSM SHP文件 other_tags 字段解析工具 (优化版)")
    print("="*80)
    
    results = {}
    
    for filename in files_to_process:
        shp_path = os.path.join(osm_dir, filename)
        
        if not os.path.exists(shp_path):
            print(f"\n文件不存在: {shp_path}")
            continue
        
        success = process_shp_file(shp_path)
        results[filename] = success
    
    print("\n" + "="*80)
    print("处理完成摘要")
    print("="*80)
    
    for filename, success in results.items():
        status = "成功" if success else "失败"
        symbol = "✓" if success else "✗"
        print(f"{symbol} {filename}: {status}")
    
    print("\n" + "="*80)
    print("所有文件处理完成！")
    print("="*80)


if __name__ == "__main__":
    main()
