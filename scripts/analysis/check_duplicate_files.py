"""
检查实时监控目录中的重复文件
"""
import os
import hashlib
from collections import defaultdict

def check_duplicate_files():
    """检查实时监控目录中的重复文件"""
    dir_path = "Dynamic_2026_03_16/realtime_monitoring"
    
    if not os.path.exists(dir_path):
        print(f"目录不存在: {dir_path}")
        return
    
    # 获取所有JSON文件
    files = [f for f in os.listdir(dir_path) if f.endswith('.json')]
    print(f"总文件数: {len(files)}")
    
    # 按文件名前缀分组（去掉时间戳）
    file_groups = defaultdict(list)
    for filename in files:
        # 提取文件名前缀（例如：TrafficSpeedBands_20260505_180736.json -> TrafficSpeedBands）
        parts = filename.rsplit('_', 2)  # 从右边分割2次
        if len(parts) >= 1:
            prefix = parts[0]
            file_groups[prefix].append(filename)
    
    print(f"\n数据类型数量: {len(file_groups)}")
    print("\n各数据类型的文件数量:")
    for prefix, filenames in sorted(file_groups.items()):
        print(f"  {prefix}: {len(filenames)} 个文件")
    
    # 检查每个组内的重复文件
    print("\n" + "="*80)
    print("检查重复文件...")
    print("="*80)
    
    total_duplicates = 0
    total_wasted_space = 0
    
    for prefix, filenames in sorted(file_groups.items()):
        if len(filenames) < 2:
            continue
        
        # 计算每个文件的哈希值
        hash_map = {}
        duplicates_in_group = []
        
        for filename in filenames:
            filepath = os.path.join(dir_path, filename)
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    content = f.read()
                    h = hashlib.md5(content.encode()).hexdigest()
                    size = os.path.getsize(filepath)
                    
                    if h in hash_map:
                        duplicates_in_group.append((filename, size, hash_map[h]))
                    else:
                        hash_map[h] = (filename, size)
            except Exception as e:
                print(f"  错误: {filename} - {e}")
        
        # 显示重复文件
        if duplicates_in_group:
            print(f"\n{prefix} ({len(duplicates_in_group)} 个重复文件):")
            for dup_filename, dup_size, (orig_filename, orig_size) in duplicates_in_group:
                print(f"  ⊘ {dup_filename} ({dup_size/1024:.1f}KB) == {orig_filename}")
                total_duplicates += 1
                total_wasted_space += dup_size
    
    print("\n" + "="*80)
    print(f"统计结果:")
    print(f"  重复文件总数: {total_duplicates}")
    print(f"  浪费空间: {total_wasted_space/1024/1024:.2f} MB")
    print("="*80)
    
    return total_duplicates, total_wasted_space

if __name__ == "__main__":
    check_duplicate_files()
