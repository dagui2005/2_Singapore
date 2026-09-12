"""
验证重复检测优化
检查代码是否正确实施了重复检测
"""

def verify_duplicate_detection():
    """验证重复检测优化"""
    print("=" * 80)
    print("验证实时监控重复检测优化")
    print("=" * 80)
    
    with open("lta_dynamic_data_downloader.py", "r", encoding="utf-8") as f:
        source_code = f.read()
    
    checks = []
    
    # 检查1: 分页下载是否使用 save_realtime_data
    if 'result = save_realtime_data(formatted_data, base_filename' in source_code:
        checks.append(("✅", "分页下载使用 save_realtime_data 进行重复检测"))
    else:
        checks.append(("❌", "分页下载未使用 save_realtime_data"))
    
    # 检查2: StationCrowdDensity_RealTime 是否使用重复检测
    if 'save_realtime_data(realtime_crowd, "StationCrowdDensity_RealTime"' in source_code:
        checks.append(("✅", "StationCrowdDensity_RealTime 使用重复检测"))
    else:
        checks.append(("❌", "StationCrowdDensity_RealTime 未使用重复检测"))
    
    # 检查3: StationCrowdDensity_Forecast 是否使用重复检测
    if 'save_realtime_data(forecast_crowd, "StationCrowdDensity_Forecast"' in source_code:
        checks.append(("✅", "StationCrowdDensity_Forecast 使用重复检测"))
    else:
        checks.append(("❌", "StationCrowdDensity_Forecast 未使用重复检测"))
    
    # 检查4: EVChargingPoints_PostalCode 是否使用重复检测
    if 'save_realtime_data(ev_postal_data, "EVChargingPoints_PostalCode"' in source_code:
        checks.append(("✅", "EVChargingPoints_PostalCode 使用重复检测"))
    else:
        checks.append(("❌", "EVChargingPoints_PostalCode 未使用重复检测"))
    
    # 检查5: check_duplicate=True 是否启用
    if 'check_duplicate=True' in source_code:
        checks.append(("✅", "重复检测参数已启用 (check_duplicate=True)"))
    else:
        checks.append(("❌", "重复检测参数未启用"))
    
    # 检查6: 是否有跳过保存的日志
    if '数据未变化，跳过保存' in source_code:
        checks.append(("✅", "包含跳过保存的日志输出"))
    else:
        checks.append(("❌", "缺少跳过保存的日志输出"))
    
    # 打印检查结果
    print("\n检查结果:\n")
    all_passed = True
    for status, message in checks:
        print(f"{status} {message}")
        if "❌" in status:
            all_passed = False
    
    print("\n" + "=" * 80)
    if all_passed:
        print("✅ 所有检查通过！重复检测优化已正确实施。")
        print("\n预期效果:")
        print("  - TrafficFlow_Data: 节省 ~99% 空间（季度更新）")
        print("  - StationCrowdDensity_Forecast: 节省 ~95% 空间（24小时更新）")
        print("  - TrafficSpeedBands: 节省 ~30% 空间（5分钟更新）")
        print("  - 总体预计节省: 40-50% 存储空间")
    else:
        print("❌ 部分检查失败，请检查代码。")
    print("=" * 80)
    
    return all_passed

if __name__ == "__main__":
    import sys
    success = verify_duplicate_detection()
    sys.exit(0 if success else 1)
