"""
修复OSM SHP文件的中文编码问题
重新生成*_expanded.shp文件，确保中文字段正确保存
"""
import os
import re
from pathlib import Path
from collections import defaultdict
import shapefile
import pandas as pd

def parse_other_tags(other_tags_str):
    """解析other_tags字符串，提取键值对"""
    result = {}
    
    if not other_tags_str or pd.isna(other_tags_str) or len(str(other_tags_str).strip()) == 0:
        return result
    
    # 关键修复：从SHP文件读取的other_tags_str已经是UTF-8字节被latin1错误解码的结果
    # 需要先将其转回正确的Unicode字符串
    try:
        content_str = str(other_tags_str)
        # 检测是否包含非ASCII字符
        has_non_ascii = any(ord(c) > 127 for c in content_str)
        if has_non_ascii and content_str.strip():
            # 转回UTF-8字节
            utf8_bytes = content_str.encode('latin1')
            # 正确解码为Unicode
            content = utf8_bytes.decode('utf-8')
        else:
            content = content_str
    except (UnicodeDecodeError, UnicodeEncodeError):
        # 如果转换失败，使用原始字符串
        content = str(other_tags_str)
    
    pattern = r'"([^"]+)"\s*=>\s*"([^"]*)"'
    matches = re.findall(pattern, content)
    
    for key, value in matches:
        # 清理键名：替换特殊字符为下划线，但保留冒号和连字符
        clean_key = re.sub(r'[^a-zA-Z0-9_:\-]', '_', key)
        result[clean_key] = value
    
    return result


def process_with_pyshp(shp_path, min_frequency=0.01, max_fields=200):
    """
    使用pyshp处理SHP文件，确保中文编码正确
    """
    print(f"\n{'='*80}")
    print(f"处理文件: {os.path.basename(shp_path)}")
    print(f"{'='*80}")
    
    try:
        # 第一步：读取原始文件（使用latin1保留原始字节）
        print("正在读取SHP文件...")
        sf = shapefile.Reader(shp_path, encoding='latin1')
        
        fields = sf.fields[1:]  # 跳过第一个删除标记字段
        field_names = [field[0] for field in fields]
        
        print(f"[OK] 成功读取 {sf.numRecords} 条记录")
        print(f"原始字段数: {len(field_names)}")
        
        if 'other_tags' not in field_names:
            print("警告: 文件中没有 'other_tags' 字段")
            return False
        
        other_tags_idx = field_names.index('other_tags')
        
        # 第二步：解析所有记录的other_tags
        print("\n正在解析 other_tags 字段...")
        records = sf.records()
        all_parsed = []
        key_count = defaultdict(int)
        
        for i, record in enumerate(records):
            parsed = parse_other_tags(record[other_tags_idx])
            all_parsed.append(parsed)
            
            for key in parsed.keys():
                key_count[key] += 1
            
            if (i + 1) % 10000 == 0:
                print(f"  已解析 {i + 1}/{sf.numRecords} 条记录")
        
        print(f"[OK] 完成解析 {sf.numRecords} 条记录")
        print(f"发现 {len(key_count)} 个唯一字段")
        
        # 第三步：筛选常见字段
        total_records = sf.numRecords
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
        
        # 第四步：创建新的shapefile
        base_path = Path(shp_path)
        output_path = str(base_path.parent / f"{base_path.stem}_expanded{base_path.suffix}")
        
        # 删除已存在的输出文件
        for ext in ['.shp', '.shx', '.dbf', '.prj', '.cpg']:
            file_to_delete = output_path.replace('.shp', ext)
            if os.path.exists(file_to_delete):
                try:
                    os.remove(file_to_delete)
                except Exception as e:
                    print(f"警告: 无法删除 {file_to_delete}: {e}")
        
        print(f"\n创建新文件: {output_path}")
        
        # 创建writer，使用UTF-8编码
        # pyshp会将Unicode字符串自动编码为UTF-8字节保存
        w = shapefile.Writer(output_path, encoding='utf-8')
        
        # 复制原有字段（排除other_tags）
        print("正在创建字段结构...")
        for field in fields:
            field_name = field[0]
            if field_name == 'other_tags':
                continue
            
            # Shapefile字段名最长10字符
            short_name = field_name[:10] if len(field_name) > 10 else field_name
            
            field_type = field[1]  # 'C'=字符, 'N'=数字
            field_size = field[2]
            field_decimal = field[3]
            
            if field_type == 'C':
                w.field(short_name, 'C', size=min(field_size, 254))
            elif field_type == 'N':
                w.field(short_name, 'N', size=min(field_size, 20), decimal=field_decimal)
        
        # 添加新字段
        for key in selected_keys:
            # Shapefile字段名最长10字符
            short_name = key[:10] if len(key) > 10 else key
            w.field(short_name, 'C', size=254)  # 字符型字段最大254
        
        print(f"[OK] 创建了 {len(w.fields) - 1} 个字段")
        
        # 第五步：写入数据
        print("正在写入数据...")
        shapes = sf.shapes()
        
        for i in range(sf.numRecords):
            record = records[i]
            shape = shapes[i]
            
            # 构建新记录（排除other_tags）
            new_record = []
            for j, field in enumerate(fields):
                if field[0] == 'other_tags':
                    continue
                
                value = record[j]
                
                # 处理None值和编码
                if value is None:
                    value = ''
                else:
                    value_str = str(value)
                    # 关键修复：从latin1读取的值实际上是UTF-8字节被当作latin1解码的结果
                    # 需要先转回UTF-8字节，再正确解码为Unicode
                    try:
                        # 检测是否包含非ASCII字符（包括双重编码的情况）
                        has_non_ascii = any(ord(c) > 127 for c in value_str)
                        if has_non_ascii and value_str.strip():  # 只处理非空且有非ASCII字符的值
                            # 转回UTF-8字节
                            utf8_bytes = value_str.encode('latin1')
                            # 正确解码为Unicode
                            decoded_value = utf8_bytes.decode('utf-8')
                            value = decoded_value
                        else:
                            value = value_str
                    except (UnicodeDecodeError, UnicodeEncodeError) as e:
                        # 如果转换失败，保留原始值
                        value = value_str
                
                new_record.append(value)
            
            # 添加新字段的值
            for key in selected_keys:
                value = all_parsed[i].get(key, '')
                if value is None:
                    value = ''
                else:
                    # 新解析的值已经是正确的Unicode字符串，直接使用
                    value = str(value)
                new_record.append(value)
            
            # 写入记录和几何形状
            w.record(*new_record)
            w.shape(shape)
            
            if (i + 1) % 10000 == 0:
                print(f"  已写入 {i + 1}/{sf.numRecords} 条记录")
        
        w.close()
        
        print(f"[OK] 成功保存 {sf.numRecords} 条记录")
        
        # 第六步：验证
        print("\n验证输出文件...")
        sf_verify = shapefile.Reader(output_path, encoding='utf-8')
        verify_fields = [f[0] for f in sf_verify.fields[1:]]
        
        print(f"[OK] 输出文件包含 {sf_verify.numRecords} 条记录")
        print(f"[OK] 字段数: {len(verify_fields)}")
        
        if 'other_tags' in verify_fields:
            print("[WARN] 警告: 仍包含 'other_tags' 字段")
        else:
            print("[OK] 确认: 'other_tags' 字段已被移除")
        
        # 检查中文字段
        zh_fields = [f for f in verify_fields if 'zh' in f.lower()]
        if zh_fields:
            print(f"[OK] 包含中文字段: {', '.join(zh_fields)}")
        
        sf.close()
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
    print("OSM SHP文件 other_tags 字段解析工具 (pyshp版 - UTF-8编码)")
    print("策略: 只保留出现频率>=1%的字段，最多200个字段")
    print("="*80)
    
    results = {}
    
    for filename in files_to_process:
        shp_path = os.path.join(osm_dir, filename)
        
        if not os.path.exists(shp_path):
            print(f"\n文件不存在: {shp_path}")
            continue
        
        success = process_with_pyshp(shp_path, min_frequency=0.01, max_fields=200)
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
