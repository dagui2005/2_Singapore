"""
测试分页下载功能
验证TrafficSpeedBands、CarParkAvailability、EstTravelTimes等API的分页下载
"""
import json
import os
from lta_dynamic_data_downloader import download_with_pagination, OUTPUT_DIR

def test_pagination():
    """测试分页下载功能"""
    print("=" * 80)
    print("测试分页下载功能")
    print("=" * 80)
    
    # 测试1: TrafficSpeedBands
    print("\n[测试1] TrafficSpeedBands (v4/TrafficSpeedBands)")
    print("-" * 80)
    try:
        data = download_with_pagination(
            "v4/TrafficSpeedBands", 
            filename="Test_TrafficSpeedBands",
            target_subdir="historical_data"
        )
        if data:
            print(f"✓ 成功获取 {len(data)} 条记录")
            if len(data) > 500:
                print(f"✓ 分页功能正常：记录数 > 500")
            else:
                print(f"⚠ 记录数 <= 500，可能数据本身就不多")
        else:
            print("✗ 未获取到数据")
    except Exception as e:
        print(f"✗ 测试失败: {e}")
    
    # 测试2: CarParkAvailability
    print("\n[测试2] CarParkAvailability (CarParkAvailabilityv2)")
    print("-" * 80)
    try:
        data = download_with_pagination(
            "CarParkAvailabilityv2",
            filename="Test_CarparkAvailability",
            target_subdir="historical_data"
        )
        if data:
            print(f"✓ 成功获取 {len(data)} 条记录")
            if len(data) > 500:
                print(f"✓ 分页功能正常：记录数 > 500")
            else:
                print(f"ℹ 记录数 <= 500")
        else:
            print("✗ 未获取到数据")
    except Exception as e:
        print(f"✗ 测试失败: {e}")
    
    # 测试3: EstTravelTimes
    print("\n[测试3] EstTravelTimes (EstTravelTimes)")
    print("-" * 80)
    try:
        data = download_with_pagination(
            "EstTravelTimes",
            filename="Test_EstTravelTimes",
            target_subdir="historical_data"
        )
        if data:
            print(f"✓ 成功获取 {len(data)} 条记录")
            if len(data) > 500:
                print(f"✓ 分页功能正常：记录数 > 500")
            else:
                print(f"ℹ 记录数 <= 500")
        else:
            print("✗ 未获取到数据")
    except Exception as e:
        print(f"✗ 测试失败: {e}")
    
    # 测试4: TrafficIncidents（通常数据量少）
    print("\n[测试4] TrafficIncidents (TrafficIncidents)")
    print("-" * 80)
    try:
        data = download_with_pagination(
            "TrafficIncidents",
            filename="Test_TrafficIncidents",
            target_subdir="historical_data"
        )
        if data:
            print(f"✓ 成功获取 {len(data)} 条记录")
        else:
            print("✗ 未获取到数据")
    except Exception as e:
        print(f"✗ 测试失败: {e}")
    
    print("\n" + "=" * 80)
    print("测试完成！")
    print("=" * 80)
    
    # 清理测试文件
    print("\n清理测试文件...")
    test_files = [
        "Test_TrafficSpeedBands.json",
        "Test_CarparkAvailability.json",
        "Test_EstTravelTimes.json",
        "Test_TrafficIncidents.json"
    ]
    for test_file in test_files:
        filepath = os.path.join(OUTPUT_DIR, "historical_data", test_file)
        if os.path.exists(filepath):
            os.remove(filepath)
            print(f"  ✓ 已删除: {test_file}")
    
    print("\n所有测试文件已清理")

if __name__ == "__main__":
    test_pagination()

