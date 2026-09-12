"""
快速验证分页优化
检查代码修改是否正确
"""
import ast
import sys

def check_pagination_optimization():
    """检查分页优化是否正确实施"""
    print("=" * 80)
    print("验证分页优化")
    print("=" * 80)
    
    # 读取源代码
    with open("lta_dynamic_data_downloader.py", "r", encoding="utf-8") as f:
        source_code = f.read()
    
    checks = []
    
    # 检查1: download_with_pagination 是否有 target_subdir 参数
    if "target_subdir=\"historical_data\"" in source_code:
        checks.append(("✅", "download_with_pagination 支持 target_subdir 参数"))
    else:
        checks.append(("❌", "download_with_pagination 缺少 target_subdir 参数"))
    
    # 检查2: realtime_apis 是否有 need_pagination 标志
    if "need_pagination" in source_code and "True)" in source_code:
        checks.append(("✅", "realtime_apis 包含 need_pagination 标志"))
    else:
        checks.append(("❌", "realtime_apis 缺少 need_pagination 标志"))
    
    # 检查3: TrafficSpeedBands 是否标记为需要分页
    if '"v4/TrafficSpeedBands",   None, "TrafficSpeedBands",    2, True' in source_code:
        checks.append(("✅", "TrafficSpeedBands 标记为需要分页"))
    else:
        checks.append(("❌", "TrafficSpeedBands 未标记为需要分页"))
    
    # 检查4: CarParkAvailability 是否标记为需要分页
    if '"CarParkAvailabilityv2",  None, "CarparkAvailability",  2, True' in source_code:
        checks.append(("✅", "CarParkAvailability 标记为需要分页"))
    else:
        checks.append(("❌", "CarParkAvailability 未标记为需要分页"))
    
    # 检查5: EstTravelTimes 是否标记为需要分页
    if '"EstTravelTimes",          None, "EstimatedTravelTimes", 2, True' in source_code:
        checks.append(("✅", "EstTravelTimes 标记为需要分页"))
    else:
        checks.append(("❌", "EstTravelTimes 未标记为需要分页"))
    
    # 检查6: 实时监控循环是否处理 need_pagination
    if "for endpoint, params, filename, sleep_sec, need_pagination in realtime_apis:" in source_code:
        checks.append(("✅", "实时监控循环正确处理 need_pagination"))
    else:
        checks.append(("❌", "实时监控循环未正确处理 need_pagination"))
    
    # 检查7: 分页下载逻辑是否存在
    if "if need_pagination:" in source_code and "download_with_pagination(endpoint, params=params" in source_code:
        checks.append(("✅", "存在分页下载逻辑"))
    else:
        checks.append(("❌", "缺少分页下载逻辑"))
    
    # 打印检查结果
    print("\n检查结果:\n")
    all_passed = True
    for status, message in checks:
        print(f"{status} {message}")
        if "❌" in status:
            all_passed = False
    
    print("\n" + "=" * 80)
    if all_passed:
        print("✅ 所有检查通过！分页优化已正确实施。")
    else:
        print("❌ 部分检查失败，请检查代码。")
    print("=" * 80)
    
    return all_passed

if __name__ == "__main__":
    success = check_pagination_optimization()
    sys.exit(0 if success else 1)
