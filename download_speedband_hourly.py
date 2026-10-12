"""
TrafficSpeedBands 每小时定时下载器
===================================
运行到指定结束时间，每小时整点触发一次完整分页下载。

用法:
    python download_speedband_hourly.py

配置:
    END_TIME    默认明天 09:00（可修改）
    OUTPUT_DIR  与主项目一致: Dynamic_2026_03_16/realtime_monitoring/
"""
import sys
import os
import json
import time
import logging
from datetime import datetime, timedelta

# 复用主项目配置
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lta_dynamic_data_downloader import (
    download_with_pagination, OUTPUT_DIR
)

# ==================== 用户配置 ====================
# 结束时间：默认明天早上 9:00
END_TIME = datetime.now().replace(hour=9, minute=0, second=0, microsecond=0)
if END_TIME <= datetime.now():
    END_TIME += timedelta(days=1)

# 输出子目录
SUBDIR = "realtime_monitoring"
LOG_FILE = os.path.join(OUTPUT_DIR, "speedband_hourly.log")

# ==================== 日志 ====================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE, encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# ==================== 下载函数 ====================
def download_one():
    """执行一次完整的 SpeedBand 分页下载并保存。"""
    start = time.time()
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    logger.info(f">>> 开始下载 TrafficSpeedBands (批次 {ts})")

    try:
        data = download_with_pagination(
            "v4/TrafficSpeedBands",
            filename=None,
            max_records=None,
            target_subdir=SUBDIR
        )
    except Exception as e:
        logger.error(f"分页下载异常: {e}")
        return False

    elapsed = time.time() - start

    if not data:
        logger.warning("下载返回空数据，跳过保存")
        return False

    # 重新组织为标准格式并带时间戳保存
    formatted = {
        "odata.metadata": "https://datamall2.mytransport.sg/ltaodataservice/$metadata#TrafficSpeedBands",
        "lastUpdatedTime": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "value": data
    }

    filename = f"TrafficSpeedBands_{ts}.json"
    filepath = os.path.join(OUTPUT_DIR, SUBDIR, filename)
    os.makedirs(os.path.dirname(filepath), exist_ok=True)

    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(formatted, f, ensure_ascii=False, indent=2)

    size_mb = os.path.getsize(filepath) / 1024 / 1024
    logger.info(
        f"<<< 完成: {filename} | "
        f"记录={len(data)} | 大小={size_mb:.1f}MB | 耗时={elapsed:.0f}s"
    )
    return True

# ==================== 主循环 ====================
def main():
    logger.info("=" * 70)
    logger.info("TrafficSpeedBands 每小时下载器启动")
    logger.info(f"当前时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info(f"计划结束: {END_TIME.strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info(f"预计下载次数: ~{int((END_TIME - datetime.now()).total_seconds() / 3600)} 次")
    logger.info("=" * 70)

    # 如果当前不是整点，先等到下一个整点
    now = datetime.now()
    next_hour = now.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
    wait = (next_hour - now).total_seconds()
    if wait > 0:
        logger.info(f"等待到下一个整点 ({next_hour.strftime('%H:%M')})，还需 {wait/60:.0f} 分钟...")
        time.sleep(wait)

    while datetime.now() < END_TIME:
        cycle_start = datetime.now()
        success = download_one()

        # 计算到下一个整点的等待时间
        next_hour = cycle_start.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
        # 如果下载跨过了整点，直接取再下一个
        while next_hour <= datetime.now():
            next_hour += timedelta(hours=1)

        sleep_sec = (next_hour - datetime.now()).total_seconds()
        if sleep_sec > 0:
            logger.info(f"下次下载: {next_hour.strftime('%H:%M')} (等待 {sleep_sec/60:.0f} 分钟)\n")
            time.sleep(sleep_sec)
        else:
            # 以防万一
            time.sleep(60)

    logger.info("=" * 70)
    logger.info(f"到达结束时间 {END_TIME.strftime('%Y-%m-%d %H:%M:%S')}，下载器退出")
    logger.info("=" * 70)


if __name__ == "__main__":
    main()
