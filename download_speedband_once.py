"""一次性完整下载 SpeedBand，测试分页耗时和记录数"""
import sys
import os
import json
import time
from datetime import datetime

# 复用现有脚本的配置和函数
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lta_dynamic_data_downloader import (
    download_with_pagination, logger, OUTPUT_DIR,
    API_BASE_URL, headers
)

print(f"[{datetime.now()}] 开始完整下载 TrafficSpeedBands...")
start = time.time()

data = download_with_pagination(
    "v4/TrafficSpeedBands",
    filename=None,
    max_records=None,
    target_subdir="realtime_monitoring"
)

elapsed = time.time() - start

if data:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    formatted_data = {
        "odata.metadata": "https://datamall2.mytransport.sg/ltaodataservice/$metadata#TrafficSpeedBands",
        "lastUpdatedTime": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "value": data
    }
    filename = f"TrafficSpeedBands_{timestamp}.json"
    filepath = os.path.join(OUTPUT_DIR, "realtime_monitoring", filename)
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(formatted_data, f, ensure_ascii=False, indent=2)
    file_size = os.path.getsize(filepath)
    print(f"[{datetime.now()}] ✓ 完成: {filename}")
    print(f"  记录数: {len(data)}")
    print(f"  耗时: {elapsed:.1f} 秒")
    print(f"  文件大小: {file_size/1024/1024:.1f} MB")
else:
    print(f"[{datetime.now()}] ✗ 下载失败")
