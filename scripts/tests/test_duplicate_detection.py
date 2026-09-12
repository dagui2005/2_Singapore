"""
测试重复检测功能
模拟保存相同和不同的数据，验证去重逻辑是否正常工作
"""

import json
import os
import sys
from datetime import datetime

# 添加主脚本路径
sys.path.insert(0, r"D:\Luan\2026-05\2_Singapore")

from lta_dynamic_data_downloader import save_realtime_data, calculate_data_hash

def test_duplicate_detection():
    """测试重复检测功能"""
    
    print("="*80)
    print("实时数据重复检测功能测试")
    print("="*80)
    
    # 测试目录
    test_dir = r"D:\Luan\2026-05\2_Singapore\test_duplicate"
    os.makedirs(test_dir, exist_ok=True)
    
    # 临时修改OUTPUT_DIR
    import lta_dynamic_data_downloader as downloader
    original_output_dir = downloader.OUTPUT_DIR
    downloader.OUTPUT_DIR = test_dir
    
    try:
        # 测试1: 保存相同的数据3次
        print("\n【测试1】保存完全相同的数据")
        print("-"*80)
        
        test_data_1 = {
            "value": [
                {"ID": "1", "Status": "Normal"},
                {"ID": "2", "Status": "Normal"}
            ]
        }
        
        result1 = save_realtime_data(test_data_1, "TestData", subdir="test_subdir")
        print(f"第1次保存: {result1}")
        
        import time
        time.sleep(1)  # 等待1秒，确保时间戳不同
        
        result2 = save_realtime_data(test_data_1, "TestData", subdir="test_subdir")
        print(f"第2次保存: {result2}")
        assert result2 is None, "第二次应该检测到重复并返回None"
        
        time.sleep(1)
        
        result3 = save_realtime_data(test_data_1, "TestData", subdir="test_subdir")
        print(f"第3次保存: {result3}")
        assert result3 is None, "第三次应该检测到重复并返回None"
        
        print("✓ 测试1通过：重复数据被正确跳过\n")
        
        # 测试2: 保存不同的数据
        print("【测试2】保存不同的数据")
        print("-"*80)
        
        test_data_2 = {
            "value": [
                {"ID": "1", "Status": "Changed"},  # 状态改变
                {"ID": "2", "Status": "Normal"}
            ]
        }
        
        result4 = save_realtime_data(test_data_2, "TestData", subdir="test_subdir")
        print(f"变化后保存: {result4}")
        assert result4 is not None, "数据变化后应该保存"
        
        print("✓ 测试2通过：变化的数据被正确保存\n")
        
        # 测试3: 哈希值计算
        print("【测试3】哈希值计算一致性")
        print("-"*80)
        
        hash1 = calculate_data_hash({"b": 2, "a": 1})
        hash2 = calculate_data_hash({"a": 1, "b": 2})  # 键顺序不同
        
        print(f"哈希1 (b,a): {hash1}")
        print(f"哈希2 (a,b): {hash2}")
        assert hash1 == hash2, "相同内容不同顺序应该产生相同哈希"
        
        hash3 = calculate_data_hash({"a": 1, "b": 3})  # 值不同
        print(f"哈希3 (a=1,b=3): {hash3}")
        assert hash1 != hash3, "不同内容应该产生不同哈希"
        
        print("✓ 测试3通过：哈希计算正确\n")
        
        # 测试4: 禁用重复检测
        print("【测试4】禁用重复检测")
        print("-"*80)
        
        result5 = save_realtime_data(test_data_1, "TestData", 
                                     subdir="test_subdir", 
                                     check_duplicate=False)
        print(f"禁用检测后保存: {result5}")
        assert result5 is not None, "禁用检测后应该强制保存"
        
        print("✓ 测试4通过：禁用检测时强制保存\n")
        
        # 统计结果
        output_subdir = os.path.join(test_dir, "test_subdir")
        files = [f for f in os.listdir(output_subdir) if f.endswith('.json')]
        print("="*80)
        print(f"测试结果总结")
        print("="*80)
        print(f"生成的文件数: {len(files)}")
        print(f"文件列表:")
        for f in sorted(files):
            filepath = os.path.join(output_subdir, f)
            size = os.path.getsize(filepath)
            print(f"  - {f} ({size} bytes)")
        
        print("\n✅ 所有测试通过！")
        print("\n预期行为:")
        print("  - 相同数据只保存1次")
        print("  - 变化数据正常保存")
        print("  - 禁用检测时强制保存")
        
    finally:
        # 恢复原始设置
        downloader.OUTPUT_DIR = original_output_dir
        
        # 清理测试文件
        import shutil
        if os.path.exists(test_dir):
            shutil.rmtree(test_dir)
            print(f"\n已清理测试目录: {test_dir}")

if __name__ == "__main__":
    test_duplicate_detection()
