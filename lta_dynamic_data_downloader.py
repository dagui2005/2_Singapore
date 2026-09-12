"""
LTA DataMall 动态交通数据下载工具（完整版）
==========================================

功能特性：
1. 下载所有历史和静态动态数据（30个API）
2. 实时监控：按官方 Update Freq 调度（2026-09-04 优化版）
   - 真正实时（≤5分钟）：每 N 分钟一次，含重复检测
   - 半实时（10-1440分钟）：按各自官方频率采集
     · TrafficSpeedBands 单次分页约 24 分钟（288 批 × 500 条 = 143,787 条），特殊处理为 30 分钟一次
   - Event-driven (Ad hoc / Not Applicable)：仅首轮一次，文件名带时间戳
   - Historic（历史下载已覆盖）：跳过实时轮询
3. 自动处理链接过期问题（TrafficFlow、EV充电点等）
4. 自动下载地理空间SHP文件（34个图层）和交通图像
5. 为无时间戳的数据添加采集时间
6. 智能分页下载和速率控制
7. 客流量历史数据支持下载至2026年4月
8. 新增 RoadOpenings / RoadWorks（显示名 PlannedRoadOpenings / ApprovedRoadWorks）24 小时轮询
9. BusArrival v3 (20秒) 暂不实时轮询（需按 BusStopCode + ServiceNo 双必填，留给历史）

作者: AI Assistant
版本: 2.2 (实时轮询优化版)
日期: 2026-09-04

修改历史:
  - 2026-09-04 v2.2 实时监控按官方 Update Freq 重新调度（见 docs/REALTIME_POLL_OPTIMIZATION.md）
  - 2026-05-04 v2.1 完整修复版
"""

import requests
import json
import os
import time
import hashlib
from datetime import datetime, timedelta
import logging
from pathlib import Path

# ==================== 配置 ====================
API_BASE_URL = "https://datamall2.mytransport.sg/ltaodataservice"
API_KEY = "zv7bb9ZNTVKLgh4cMALjMQ=="
OUTPUT_DIR = "Dynamic_2026_03_16"
STATIC_DATA_DIR = "Static_ 2026_03"

# 创建输出目录结构
os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(os.path.join(OUTPUT_DIR, "realtime_monitoring"), exist_ok=True)
os.makedirs(os.path.join(OUTPUT_DIR, "historical_data"), exist_ok=True)
os.makedirs(os.path.join(OUTPUT_DIR, "historical_data", "geospatial"), exist_ok=True)
os.makedirs(os.path.join(OUTPUT_DIR, "historical_data", "images"), exist_ok=True)

# 日志配置
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(OUTPUT_DIR, 'download.log'), encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# 请求头
headers = {
    "AccountKey": API_KEY,
    "Accept": "application/json"
}


# ==================== 工具函数 ====================

def save_json_data(data, filename, subdir=None):
    """保存JSON数据到文件（历史数据用）"""
    if subdir:
        filepath = os.path.join(OUTPUT_DIR, subdir, filename)
    else:
        filepath = os.path.join(OUTPUT_DIR, filename)
    
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    logger.info(f"✓ 已保存: {filename}")
    return filepath


def calculate_data_hash(data):
    """计算数据的MD5哈希值（用于检测重复）"""
    # 将数据转换为JSON字符串（排序键以确保一致性）
    json_str = json.dumps(data, sort_keys=True, ensure_ascii=False)
    return hashlib.md5(json_str.encode('utf-8')).hexdigest()


def save_realtime_data(data, filename, subdir="realtime_monitoring", auto_download_link=True, download_images=False, check_duplicate=True):
    """
    保存实时数据，自动处理链接下载、图片下载和重复检测
    
    Args:
        data: API返回的数据
        filename: 文件名（不含时间戳）
        subdir: 子目录
        auto_download_link: 是否自动检测并下载S3链接（TrafficFlow、EVChargingPoints等）
        download_images: 是否自动下载ImageLink中的图片（TrafficImages）
        check_duplicate: 是否检查重复数据（默认True）
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filepath = os.path.join(OUTPUT_DIR, subdir, f"{filename}_{timestamp}.json")
    
    # 检查是否是S3链接格式（TrafficFlow、EVChargingPoints_Batch等）
    if auto_download_link and isinstance(data, dict) and 'value' in data:
        if len(data['value']) > 0 and isinstance(data['value'][0], dict):
            if 'Link' in data['value'][0]:
                link = data['value'][0]['Link']
                logger.info(f"    检测到S3链接，正在下载实际数据...")
                
                # 生成实际数据的文件名
                actual_filename = f"{filename}_Data_{timestamp}.json"
                actual_filepath = os.path.join(OUTPUT_DIR, subdir, actual_filename)
                
                success, file_size = download_from_link(link, actual_filepath, timeout=300)
                if success:
                    logger.info(f"  ✓ 实际数据已保存: {actual_filename} ({file_size/1024:.1f} KB)")
                    # 同时保存原始链接文件作为记录
                    os.makedirs(os.path.dirname(filepath), exist_ok=True)
                    with open(filepath, 'w', encoding='utf-8') as f:
                        json.dump(data, f, ensure_ascii=False, indent=2)
                    return filepath
                else:
                    logger.warning(f"  ⚠ 链接下载失败，保存原始链接文件")
    
    # 检查是否需要下载图片（TrafficImages）
    if download_images and isinstance(data, dict) and 'value' in data:
        images_dir = os.path.join(OUTPUT_DIR, subdir, "images")
        os.makedirs(images_dir, exist_ok=True)
        
        downloaded_count = 0
        failed_count = 0
        
        for item in data['value']:
            if isinstance(item, dict) and 'ImageLink' in item:
                camera_id = item.get('CameraID', 'unknown')
                image_url = item['ImageLink']
                
                # 从URL提取文件扩展名，默认jpg
                if '.' in image_url.split('?')[0]:
                    ext = image_url.split('?')[0].split('.')[-1]
                else:
                    ext = 'jpg'
                
                image_filename = f"{camera_id}_{timestamp}.{ext}"
                image_path = os.path.join(images_dir, image_filename)
                
                try:
                    logger.debug(f"    下载摄像头 {camera_id} 的图片...")
                    response = requests.get(image_url, timeout=30, stream=True)
                    response.raise_for_status()
                    
                    with open(image_path, 'wb') as f:
                        for chunk in response.iter_content(chunk_size=8192):
                            if chunk:
                                f.write(chunk)
                    
                    downloaded_count += 1
                    logger.debug(f"    ✓ 已下载: {image_filename}")
                except Exception as e:
                    failed_count += 1
                    logger.debug(f"    ✗ 下载失败 {camera_id}: {str(e)[:50]}")
        
        if downloaded_count > 0:
            logger.info(f"  ✓ 已下载 {downloaded_count} 张图片到 images/ 文件夹")
        if failed_count > 0:
            logger.warning(f"  ⚠ {failed_count} 张图片下载失败")
    
    # 检查是否与上一个文件重复（仅对普通JSON数据）
    if check_duplicate:
        # 查找该数据类型最近的文件
        output_dir = os.path.join(OUTPUT_DIR, subdir)
        
        # 如果目录不存在，直接保存（首次运行）
        if not os.path.exists(output_dir):
            os.makedirs(output_dir, exist_ok=True)
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            logger.info(f"✓ 已保存: {os.path.basename(filepath)}")
            return filepath
        
        recent_files = []
        for f in os.listdir(output_dir):
            if f.startswith(filename + "_") and f.endswith('.json'):
                full_path = os.path.join(output_dir, f)
                recent_files.append((full_path, os.path.getmtime(full_path)))
        
        # 按修改时间排序，取最近的3个文件
        recent_files.sort(key=lambda x: x[1], reverse=True)
        recent_files = recent_files[:3]
        
        # 计算当前数据的哈希值
        current_hash = calculate_data_hash(data)
        
        # 检查是否与最近的文件相同
        is_duplicate = False
        duplicate_with = None
        
        for recent_path, _ in recent_files:
            try:
                with open(recent_path, 'r', encoding='utf-8') as f:
                    recent_data = json.load(f)
                recent_hash = calculate_data_hash(recent_data)
                
                if current_hash == recent_hash:
                    is_duplicate = True
                    duplicate_with = os.path.basename(recent_path)
                    break
            except Exception:
                continue
        
        if is_duplicate:
            logger.info(f"  ⊘ 数据未变化，跳过保存（与 {duplicate_with} 相同）")
            return None
    
    # 正常保存JSON数据
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    logger.info(f"✓ 已保存: {os.path.basename(filepath)}")
    return filepath


def load_static_data(filename):
    """从静态数据目录加载数据"""
    search_dirs = [
        os.path.join(STATIC_DATA_DIR, "GEOSPATIAL"),
        os.path.join(STATIC_DATA_DIR, "PUBLIC TRANSPORT")
    ]
    
    for search_dir in search_dirs:
        for root, dirs, files in os.walk(search_dir):
            if filename in files:
                filepath = os.path.join(root, filename)
                try:
                    if filepath.endswith('.json'):
                        with open(filepath, 'r', encoding='utf-8') as f:
                            return json.load(f)
                    elif filepath.endswith('.csv'):
                        import pandas as pd
                        return pd.read_csv(filepath)
                except Exception as e:
                    logger.warning(f"加载静态数据失败 {filepath}: {e}")
    return None


def extract_bus_stop_codes():
    """从静态数据中提取巴士站代码"""
    bus_stops_file = load_static_data("BusStop.json")
    if bus_stops_file:
        if isinstance(bus_stops_file, list):
            return [stop.get('BusStopCode') for stop in bus_stops_file if 'BusStopCode' in stop]
        elif isinstance(bus_stops_file, dict) and 'value' in bus_stops_file:
            return [stop.get('BusStopCode') for stop in bus_stops_file['value'] if 'BusStopCode' in stop]
    
    logger.info("从静态数据中未找到巴士站信息，将从API获取...")
    return None


def safe_api_call(endpoint, params=None, max_retries=3, timeout=30):
    """安全的API调用，包含重试机制"""
    url = f"{API_BASE_URL}/{endpoint}"
    
    for attempt in range(max_retries):
        try:
            response = requests.get(url, headers=headers, params=params, timeout=timeout)
            response.raise_for_status()
            
            content_type = response.headers.get('Content-Type', '')
            if 'application/json' in content_type:
                return response.json()
            else:
                return response.text
                
        except requests.exceptions.RequestException as e:
            logger.warning(f"API调用失败 (尝试 {attempt + 1}/{max_retries}): {endpoint} - {str(e)}")
            if attempt < max_retries - 1:
                wait_time = 2 ** attempt
                logger.info(f"等待 {wait_time} 秒后重试...")
                time.sleep(wait_time)
            else:
                logger.error(f"API调用最终失败: {endpoint}")
                return None
    
    return None


def download_from_link(url, save_path, timeout=300):
    """从S3链接下载文件（处理过期链接）"""
    try:
        logger.info(f"  正在下载...")
        response = requests.get(url, timeout=timeout, stream=True)
        response.raise_for_status()
        
        os.makedirs(os.path.dirname(save_path), exist_ok=True)
        
        with open(save_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
        
        file_size = os.path.getsize(save_path)
        logger.info(f"  ✓ 下载完成: {os.path.basename(save_path)} ({file_size/1024:.1f} KB)")
        return True, file_size
    except Exception as e:
        logger.error(f"  ✗ 下载失败: {str(e)[:100]}")
        return False, 0


def download_with_pagination(endpoint, params=None, filename=None, max_records=None, target_subdir="historical_data"):
    """
    下载支持分页的API数据
    
    Args:
        endpoint: API端点
        params: 查询参数
        filename: 文件名（不含扩展名）
        max_records: 最大记录数限制（None表示无限制）
        target_subdir: 目标子目录（historical_data 或 realtime_monitoring）
    """
    all_data = []
    skip = 0
    batch_num = 0
    
    while True:
        paginated_params = params.copy() if params else {}
        paginated_params['$skip'] = skip
        
        data = safe_api_call(endpoint, params=paginated_params)
        
        if not data:
            break
        
        if isinstance(data, dict) and 'value' in data:
            records = data['value']
        elif isinstance(data, list):
            records = data
        else:
            records = [data]
        
        if not records:
            break
        
        all_data.extend(records)
        batch_num += 1
        logger.info(f"  - 批次 {batch_num}: 获取 {len(records)} 条记录 (累计: {len(all_data)})")
        
        if max_records and len(all_data) >= max_records:
            all_data = all_data[:max_records]
            break
        
        if len(records) < 500:
            break
        
        skip += 500
        time.sleep(1)
    
    if not filename:
        filename = f"{endpoint.replace('/', '_').replace('v3_', '').replace('v4_', '').replace('v2_', '')}.json"
    
    save_json_data(all_data, filename, subdir=target_subdir)
    return all_data


def add_timestamp_to_file(filepath):
    """为JSON文件添加时间戳（用于没有时间戳的API）"""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        file_mtime = os.path.getmtime(filepath)
        data_time = datetime.fromtimestamp(file_mtime).isoformat()
        
        if isinstance(data, list):
            for record in data:
                if isinstance(record, dict):
                    record['Timestamp'] = data_time
                    record['DataCollectionTime'] = data_time
        elif isinstance(data, dict):
            data['Timestamp'] = data_time
            data['DataCollectionTime'] = data_time
        
        backup_file = filepath.replace('.json', '_backup.json')
        if not os.path.exists(backup_file):
            os.rename(filepath, backup_file)
            logger.info(f"  已备份原文件: {os.path.basename(backup_file)}")
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        logger.info(f"  ✓ 已添加时间戳: {data_time}")
        return True
    except Exception as e:
        logger.error(f"  ✗ 添加时间戳失败: {e}")
        return False


# ==================== 数据下载函数 ====================

def download_bus_services():
    """下载巴士服务信息"""
    logger.info("\n[1/30] 下载巴士服务信息 (Bus Services)...")
    return download_with_pagination("BusServices", filename="BusServices.json")


def download_bus_routes():
    """下载巴士路线信息"""
    logger.info("\n[2/30] 下载巴士路线信息 (Bus Routes)...")
    return download_with_pagination("BusRoutes", filename="BusRoutes.json")


def download_bus_stops():
    """下载巴士站点信息"""
    logger.info("\n[3/30] 下载巴士站点信息 (Bus Stops)...")
    return download_with_pagination("BusStops", filename="BusStops.json")


def download_bus_arrival(sample_size=50):
    """下载巴士到站信息（实时数据）"""
    logger.info(f"\n[4/30] 下载巴士到站信息 (Bus Arrival) - 采样 {sample_size} 个站点...")
    
    bus_stop_codes = extract_bus_stop_codes()
    
    if not bus_stop_codes:
        stops_data = download_bus_stops()
        if stops_data:
            bus_stop_codes = [stop.get('BusStopCode') for stop in stops_data if 'BusStopCode' in stop]
    
    if not bus_stop_codes:
        logger.error("无法获取巴士站代码列表")
        return []
    
    sample_codes = bus_stop_codes[:sample_size]
    arrival_data = []
    
    for i, stop_code in enumerate(sample_codes, 1):
        logger.info(f"  - 获取巴士站 {stop_code} ({i}/{len(sample_codes)})...")
        data = safe_api_call("v3/BusArrival", params={"BusStopCode": stop_code})
        if data:
            arrival_data.append(data)
        time.sleep(0.5)
    
    save_json_data(arrival_data, f"BusArrival_sample_{sample_size}.json", subdir="realtime_monitoring")
    logger.info(f"✓ 已下载 {len(arrival_data)} 个巴士站的到站信息")
    return arrival_data


def download_passenger_volume(month="202603"):
    """下载客流量数据（支持历史月份）"""
    logger.info(f"\n[5-8/30] 下载客流量数据 ({month})...")
    
    datasets = [
        ("PV/Bus", f"PassengerVolume_BusStops_{month}.json", "按巴士站"),
        ("PV/ODBus", f"PassengerVolume_ODBus_{month}.json", "按起终点巴士站"),
        ("PV/ODTrain", f"PassengerVolume_ODTrain_{month}.json", "按起终点地铁站"),
        ("PV/Train", f"PassengerVolume_TrainStations_{month}.json", "按地铁站"),
    ]
    
    results = {}
    for endpoint, filename, desc in datasets:
        logger.info(f"  - 下载{desc}客流量...")
        # max_retries=1：客流量数据文件每月10日生成，不存在时返回500，不重试
        data = safe_api_call(endpoint, params={"Date": month}, max_retries=1)
        if data:
            save_json_data(data, filename, subdir="historical_data")
            results[endpoint] = data
        time.sleep(1)
    
    return results


def download_taxi_availability():
    """下载可用出租车位置（实时数据）"""
    logger.info("\n[9/30] 下载可用出租车位置 (Taxi Availability)...")
    data = safe_api_call("Taxi-Availability")
    if data:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        save_json_data(data, f"TaxiAvailability_{timestamp}.json", subdir="realtime_monitoring")
    return data


def download_taxi_stands():
    """下载出租车站信息"""
    logger.info("\n[10/30] 下载出租车站信息 (Taxi Stands)...")
    return download_with_pagination("TaxiStands", filename="TaxiStands.json")


def download_train_service_alerts():
    """下载列车服务警报"""
    logger.info("\n[11/30] 下载列车服务警报 (Train Service Alerts)...")
    data = safe_api_call("TrainServiceAlerts")
    if data:
        save_json_data(data, "TrainServiceAlerts.json", subdir="historical_data")
    return data


def download_facilities_maintenance():
    """下载设施维护信息"""
    logger.info("\n[12/30] 下载设施维护信息 (Facilities Maintenance v2)...")
    return download_with_pagination("v2/FacilitiesMaintenance", filename="FacilitiesMaintenance_v2.json")


def download_station_crowd_density():
    """下载站台拥挤度（实时和预测）"""
    logger.info("\n[13-14/30] 下载站台拥挤度数据...")
    
    train_lines = ["CCL", "CEL", "CGL", "DTL", "EWL", "NEL", "NSL", "BPL", "SLRT", "PLRT", "TEL"]
    
    realtime_data = {}
    for line in train_lines:
        logger.info(f"  - 获取线路 {line} 的实时拥挤度...")
        data = safe_api_call("PCDRealTime", params={"TrainLine": line})
        if data:
            realtime_data[line] = data
        time.sleep(0.5)
    
    save_json_data(realtime_data, "StationCrowdDensity_RealTime.json", subdir="realtime_monitoring")
    
    forecast_data = {}
    for line in train_lines:
        logger.info(f"  - 获取线路 {line} 的预测拥挤度...")
        # max_retries=1：该API 24小时更新一次，非更新时段返回500，不重试以节省时间
        data = safe_api_call("PCDForecast", params={"TrainLine": line}, max_retries=1)
        if data:
            forecast_data[line] = data
        time.sleep(0.5)
    
    if forecast_data:
        save_json_data(forecast_data, "StationCrowdDensity_Forecast.json", subdir="historical_data")
    else:
        logger.info("  StationCrowdDensity_Forecast 暂无可用数据（API可能处于非更新时段）")
    
    return realtime_data, forecast_data


def download_planned_bus_routes():
    """下载计划巴士路线"""
    logger.info("\n[15/30] 下载计划巴士路线 (Planned Bus Routes)...")
    return download_with_pagination("PlannedBusRoutes", filename="PlannedBusRoutes.json")


def download_carpark_availability():
    """下载停车场空位（实时数据）"""
    logger.info("\n[16/30] 下载停车场空位 (Carpark Availability)...")
    return download_with_pagination("CarParkAvailabilityv2", filename="CarparkAvailability_v2.json", target_subdir="historical_data")


def download_estimated_travel_times():
    """下载预计行驶时间"""
    logger.info("\n[17/30] 下载预计行驶时间 (Estimated Travel Times)...")
    data = download_with_pagination("EstTravelTimes", filename="EstimatedTravelTimes.json", target_subdir="historical_data")
    if data:
        filepath = os.path.join(OUTPUT_DIR, "historical_data", "EstimatedTravelTimes.json")
        add_timestamp_to_file(filepath)
    return data


def download_faulty_traffic_lights():
    """下载故障交通灯"""
    logger.info("\n[18/30] 下载故障交通灯 (Faulty Traffic Lights)...")
    return download_with_pagination("FaultyTrafficLights", filename="FaultyTrafficLights.json")


def download_planned_road_openings():
    """下载计划道路开放"""
    logger.info("\n[19/30] 下载计划道路开放 (Planned Road Openings)...")
    return download_with_pagination("RoadOpenings", filename="PlannedRoadOpenings.json")


def download_approved_road_works():
    """下载批准的道路工程"""
    logger.info("\n[20/30] 下载批准的道路工程 (Approved Road Works)...")
    return download_with_pagination("RoadWorks", filename="ApprovedRoadWorks.json")


def download_traffic_images(download_sample=False, sample_count=5):
    """下载交通图像链接（可选下载示例图像）"""
    logger.info("\n[21/30] 下载交通图像链接 (Traffic Images)...")
    data = download_with_pagination("Traffic-Imagesv2", filename="TrafficImages_v2.json")
    
    if download_sample and data:
        logger.info(f"  下载 {sample_count} 张示例图像...")
        images_dir = os.path.join(OUTPUT_DIR, "historical_data", "images")
        
        if isinstance(data, list):
            image_list = data
        elif isinstance(data, dict) and 'value' in data:
            image_list = data['value']
        else:
            image_list = []
        
        downloaded = 0
        for i, record in enumerate(image_list[:sample_count]):
            if 'ImageLink' not in record:
                continue
            
            camera_id = record.get('CameraID', f'unknown_{i}')
            link = record['ImageLink']
            save_path = os.path.join(images_dir, f"Camera_{camera_id}.jpg")
            
            success, _ = download_from_link(link, save_path, timeout=60)
            if success:
                downloaded += 1
            time.sleep(1)
        
        logger.info(f"  ✓ 已下载 {downloaded}/{sample_count} 张图像")
    
    return data


def download_traffic_incidents():
    """下载交通事故"""
    logger.info("\n[22/30] 下载交通事故 (Traffic Incidents)...")
    return download_with_pagination("TrafficIncidents", filename="TrafficIncidents.json")


def download_traffic_speed_bands():
    """下载交通速度带"""
    logger.info("\n[23/30] 下载交通速度带 (Traffic Speed Bands v4)...")
    data = download_with_pagination("v4/TrafficSpeedBands", filename="TrafficSpeedBands_v4.json", target_subdir="historical_data")
    if data:
        filepath = os.path.join(OUTPUT_DIR, "historical_data", "TrafficSpeedBands_v4.json")
        add_timestamp_to_file(filepath)
    return data


def download_vms_emas():
    """下载可变消息标志"""
    logger.info("\n[24/30] 下载可变消息标志 (VMS / EMAS)...")
    return download_with_pagination("VMS", filename="VMS_EMAS.json")


def download_traffic_flow():
    """下载交通流量（自动处理链接过期）"""
    logger.info("\n[25/30] 下载交通流量 (Traffic Flow)...")
    
    # 第一次调用获取链接
    data = safe_api_call("TrafficFlow")
    if not data or 'value' not in data or len(data['value']) == 0:
        logger.error("无法获取TrafficFlow数据")
        return None
    
    link = data['value'][0].get('Link')
    if not link:
        logger.error("未找到下载链接")
        return None
    
    logger.info("  获取到最新链接，立即下载实际数据...")
    save_path = os.path.join(OUTPUT_DIR, "historical_data", "TrafficFlow_Data.json")
    
    success, file_size = download_from_link(link, save_path, timeout=300)
    if success:
        logger.info(f"✓ TrafficFlow数据已保存 ({file_size/1024:.1f} KB)")
        
        # 验证数据
        try:
            with open(save_path, 'r', encoding='utf-8') as f:
                flow_data = json.load(f)
            if isinstance(flow_data, list):
                logger.info(f"  数据记录数: {len(flow_data)}")
            elif isinstance(flow_data, dict):
                logger.info(f"  数据类型: {list(flow_data.keys())}")
        except Exception as e:
            logger.warning(f"  数据验证失败: {e}")
        
        return flow_data
    else:
        logger.error("✗ 下载失败")
        return None


def download_flood_alerts():
    """下载洪水警报"""
    logger.info("\n[26/30] 下载洪水警报 (Flood Alerts)...")
    return download_with_pagination("PubFloodAlerts", filename="FloodAlerts.json")


def download_bicycle_parking():
    """下载自行车停放点"""
    logger.info("\n[27/30] 下载自行车停放点 (Bicycle Parking)...")
    
    locations = [
        {"lat": 1.3521, "lon": 103.8198, "name": "City_Center"},
        {"lat": 1.3649, "lon": 103.9916, "name": "Tampines"},
        {"lat": 1.2839, "lon": 103.8607, "name": "Marina_Bay"},
        {"lat": 1.3114, "lon": 103.8480, "name": "Orchard"},
        {"lat": 1.3437, "lon": 103.8636, "name": "Novena"},
    ]
    
    all_data = {}
    for loc in locations:
        logger.info(f"  - 获取区域 {loc['name']} 的自行车停放点...")
        params = {
            "Lat": loc["lat"],
            "Long": loc["lon"],
            "Dist": 2
        }
        data = safe_api_call("BicycleParkingv2", params=params)
        if data:
            all_data[loc['name']] = data
        time.sleep(1)
    
    save_json_data(all_data, "BicycleParking.json", subdir="historical_data")
    return all_data


def download_ev_charging_points():
    """下载电动车充电点（自动处理批量数据链接）"""
    logger.info("\n[28-29/30] 下载电动车充电点数据...")
    
    # 批量数据 - 需要处理链接
    logger.info("  - 下载批量充电点数据...")
    batch_link_data = safe_api_call("EVCBatch")
    
    if batch_link_data and 'value' in batch_link_data and len(batch_link_data['value']) > 0:
        link = batch_link_data['value'][0].get('Link')
        if link:
            logger.info("    获取到最新链接，立即下载...")
            save_path = os.path.join(OUTPUT_DIR, "historical_data", "EVChargingPoints_Batch_Data.json")
            success, file_size = download_from_link(link, save_path, timeout=300)
            if success:
                logger.info(f"    ✓ EV充电点批量数据已保存 ({file_size/1024:.1f} KB)")
            batch_data = {"link_downloaded": success}
        else:
            batch_data = None
    else:
        batch_data = None
    
    # 按邮政编码查询
    postal_codes = ["018956", "138623", "238840", "308318", "545043"]
    postal_data = {}
    
    for code in postal_codes:
        logger.info(f"  - 获取邮编 {code} 的充电点...")
        data = safe_api_call("EVChargingPoints", params={"PostalCode": code})
        if data:
            postal_data[code] = data
        time.sleep(1)
    
    save_json_data(postal_data, "EVChargingPoints_by_PostalCode.json", subdir="historical_data")
    
    return batch_data, postal_data


def download_geospatial_layers(download_all=True, priority_only=False):
    """下载地理空间图层（自动下载SHP文件）"""
    logger.info("\n[额外] 下载地理空间图层...")
    
    all_layer_ids = [
        "ArrowMarking", "Bollard", "BusStopLocation", "ControlBox",
        "ConvexMirror", "CoveredLinkWay", "CyclingPath", "DetectorLoop",
        "ERPGantry", "Footpath", "GuardRail", "KerbLine", "LampPost",
        "LaneMarking", "ParkingStandardsZone", "PassengerPickupBay",
        "PedestrainOverheadbridge_UnderPass", "RailConstruction", "Railing",
        "RetainingWall", "RoadCrossing", "RoadHump", "RoadSectionLine",
        "SchoolZone", "SilverZone", "SpeedRegulatingStrip", "StreetPaint",
        "TaxiStand", "TrafficLight", "TrafficSign", "TrainStation",
        "TrainStationExit", "VehicularBridge_Flyover_Underpass", "WordMarking"
    ]
    
    # 优先下载的图层
    priority_layers = [
        "RoadSectionLine", "BusStopLocation", "TrafficLight", 
        "ERPGantry", "TaxiStand"
    ]
    
    layer_ids = priority_layers if priority_only else all_layer_ids
    
    geospatial_links = {}
    geospatial_dir = os.path.join(OUTPUT_DIR, "historical_data", "geospatial")
    
    downloaded = 0
    failed = 0
    
    for i, layer_id in enumerate(layer_ids, 1):
        logger.info(f"  [{i}/{len(layer_ids)}] 获取图层 {layer_id}...")
        data = safe_api_call("GeospatialWholeIsland", params={"ID": layer_id})
        
        if not data:
            logger.warning(f"    ✗ 无法获取 {layer_id}")
            failed += 1
            continue
        
        geospatial_links[layer_id] = data
        
        # 提取链接并下载
        link = None
        if isinstance(data, dict):
            if 'Link' in data:
                link = data['Link']
            elif 'value' in data and len(data['value']) > 0:
                link = data['value'][0].get('Link')
        
        if link:
            save_path = os.path.join(geospatial_dir, f"{layer_id}.zip")
            
            # 检查是否已存在
            if os.path.exists(save_path):
                logger.info(f"    ⊘ 文件已存在，跳过")
                downloaded += 1
                continue
            
            success, file_size = download_from_link(link, save_path, timeout=300)
            if success:
                downloaded += 1
            else:
                failed += 1
        else:
            logger.warning(f"    ✗ 未找到下载链接")
            failed += 1
        
        time.sleep(2)
    
    # 保存链接信息
    save_json_data(geospatial_links, "GeospatialWholeIsland_Links.json", subdir="historical_data")
    logger.info(f"  ✓ 地理空间图层下载完成: {downloaded} 成功, {failed} 失败")
    
    return geospatial_links


# ==================== 实时监控功能 ====================

def start_realtime_monitoring(duration_hours=24, interval_minutes=5):
    """
    启动实时监控，按 LTA DataMall 官方 Update Freq 调度各端点采集频率。

    调度规则（见 realtime_apis 表的 cycle_minutes 字段）：
      - high 类（官方 ≤5 分钟更新）→ 按官方频率轮询，含重复检测
      - quasi 类（官方 10-1440 分钟）→ 按各自频率轮询
      - event 类（Ad hoc / Not Applicable）→ 仅首轮采集一次，文件名带时间戳
      - historic 类（历史下载已覆盖）→ 跳过

    Args:
        duration_hours: 监控持续时间（小时），默认 24
        interval_minutes: 主循环轮询间隔（分钟），默认 5。
                          注意：各端点实际采集频率受 cycle_minutes 控制，
                          与本参数不同。
    Note:
        2026-09-04 优化后，端点按官方 Update Freq 分级调度：
          - 真正实时（≤5分钟）：TrafficIncidents, FaultyTrafficLights, VMS_EMAS,
              FloodAlerts, CarparkAvailability, EstimatedTravelTimes,
              TrafficSpeedBands, TaxiAvailability, EVChargingPoints_Batch
              (BusArrival 20秒但需按站点+线路查询，不适合批量实时轮询，留历史)
          - 半实时：StationCrowdDensity_RealTime (10min),
              StationCrowdDensity_Forecast (1440min)，
              PlannedRoadOpenings (1440min, 新增),
              ApprovedRoadWorks (1440min, 新增)
          - Event-driven：TrainServiceAlerts, FacilitiesMaintenance, TrafficFlow
              （仅首轮一次，文件名带时间戳避免覆盖）
          - 已移除：TrafficImages（图片走历史下载）
        详见 docs/REALTIME_POLL_OPTIMIZATION.md
    """
    logger.info("=" * 80)
    logger.info("启动实时监控模式")
    logger.info(f"监控时长: {duration_hours} 小时")
    logger.info(f"采集间隔: {interval_minutes} 分钟")
    logger.info("=" * 80)
    
    start_time = datetime.now()
    end_time = start_time + timedelta(hours=duration_hours)
    cycle = 0
    
    # 实时数据类型及其采集间隔（按 LTA DataMall 官方 Update Freq 配置）
    # 格式：(endpoint, params, filename, cycle_minutes, need_pagination, category)
    # cycle_minutes 含义:
    #   N >= 1     每 N 分钟执行一次
    #   N = 0      仅在首轮采集一次 (用于 Ad hoc / Not Applicable)
    #   N = -1     不放入实时轮询 (历史下载已覆盖)
    # category: high(真实时≤5m) / quasi(半实时10m+) / event(Ad hoc一次性)
    realtime_apis = [
        # === 真正实时（高频 2-5 分钟更新）===
        ("TrafficIncidents",         None, "TrafficIncidents",          2, False, "high"),
        ("FaultyTrafficLights",      None, "FaultyTrafficLights",       2, False, "high"),
        ("VMS",                      None, "VMS_EMAS",                  2, False, "high"),
        ("PubFloodAlerts",           None, "FloodAlerts",               3, False, "high"),
        ("CarParkAvailabilityv2",    None, "CarparkAvailability",       5, True,  "high"),
        ("EstTravelTimes",           None, "EstimatedTravelTimes",      5, True,  "high"),
        ("v4/TrafficSpeedBands",     None, "TrafficSpeedBands",        30, True,  "quasi"),  # 单次全量分页约 24 分钟，按 30 分钟轮询
        ("Taxi-Availability",        None, "TaxiAvailability",          1, False, "high"),
        ("EVCBatch",                 None, "EVChargingPoints_Batch",    5, False, "high"),

        # === BusArrival (20秒) 需按 BusStopCode + ServiceNo 双必填，不能批量实时轮询，留历史 ===
        ("v3/BusArrival",            None, "BusArrival",               -1, False, "historic"),

        # === 半实时 10 分钟更新 ===
        ("PCDRealTime",              None, "StationCrowdDensity_RealTime", 10, False, "quasi"),

        # === Event-driven / Ad hoc → 仅首轮一次 ===
        ("TrainServiceAlerts",       None, "TrainServiceAlerts",        0, False, "event"),
        ("v2/FacilitiesMaintenance", None, "FacilitiesMaintenance",     0, False, "event"),
        ("TrafficFlow",              None, "TrafficFlow",               0, False, "event"),

        # === 24 小时轮询 (新增) ===
        ("RoadOpenings",             None, "PlannedRoadOpenings",    1440, False, "high24h"),
        ("RoadWorks",                None, "ApprovedRoadWorks",      1440, False, "high24h"),

        # === TrafficImages 不再实时轮询（图片走历史下载）===
        ("TrafficImages",            None, "TrafficImages",            -1, False, "historic"),
    ]

    # 需要按线路逐一查询的车站拥挤度 API（TrainLine 为必填参数）
    train_lines = ["CCL", "CEL", "CGL", "DTL", "EWL", "NEL", "NSL", "BPL", "SLRT", "PLRT", "TEL"]

    # 需要按邮编逐一查询的 EV 充电点 API（PostalCode 为必填参数）
    ev_postal_codes = ["018956", "138623", "238840", "308318", "545043",
                       "048624", "068896", "117438", "189702", "529509"]

    while datetime.now() < end_time:
        cycle += 1
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        logger.info(f"\n{'='*60}")
        logger.info(f"采集周期 #{cycle} - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info(f"{'='*60}")

        # 采集普通实时 API（按 cycle_minutes 调度）
        for endpoint, params, filename, cycle_minutes, need_pagination, category in realtime_apis:
            # historic 类直接跳过（历史下载已覆盖）
            if category == "historic":
                continue
            # Ad hoc / Once 类：仅首轮采集一次
            if cycle_minutes == 0 and cycle > 1:
                continue
            # 高频类：按 cycle_minutes 调度（每 N 分钟一次）
            if cycle > 1 and cycle_minutes > 0 and (cycle - 1) % cycle_minutes != 0:
                continue

            try:
                logger.info(f"  采集: {filename}{' (分页)' if need_pagination else ''}...")

                if need_pagination:
                    data = download_with_pagination(endpoint, params=params, filename=None,
                                                   max_records=None, target_subdir="realtime_monitoring")
                    if data:
                        formatted_data = {
                            "odata.metadata": f"https://datamall2.mytransport.sg/ltaodataservice/$metadata#{endpoint.split('/')[-1]}",
                            "lastUpdatedTime": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                            "value": data
                        }
                        # save_realtime_data() 内部会自动追加时间戳，避免重复后缀
                        result = save_realtime_data(formatted_data, filename,
                                                   subdir="realtime_monitoring",
                                                   auto_download_link=False,
                                                   download_images=False,
                                                   check_duplicate=(cycle_minutes > 0))
                        if result:
                            logger.info(f"  ✓ {filename} 已保存 ({len(data)} 条记录)")
                        else:
                            logger.info(f"  ⊘ {filename} 数据未变化，跳过保存")
                else:
                    data = safe_api_call(endpoint, params=params)
                    if data:
                        # save_realtime_data() 内部会自动追加时间戳
                        save_realtime_data(data, filename, subdir="realtime_monitoring",
                                         auto_download_link=True, download_images=False,
                                         check_duplicate=(cycle_minutes > 0))
                time.sleep(1)
            except Exception as e:
                logger.error(f"采集失败 {filename}: {e}")

        # 车站实时拥挤度 (官方 10 分钟更新)
        # 仅当本轮符合 "每 10 分钟一次" 才采集
        if (cycle - 1) % 10 == 0:
            try:
                logger.info("  采集: StationCrowdDensity_RealTime (按线路, 10分钟)...")
                realtime_crowd = {}
                for line in train_lines:
                    data = safe_api_call("PCDRealTime", params={"TrainLine": line})
                    if data:
                        realtime_crowd[line] = data
                    time.sleep(0.5)
                if realtime_crowd:
                    result = save_realtime_data(realtime_crowd, "StationCrowdDensity_RealTime",
                                               subdir="realtime_monitoring",
                                               auto_download_link=False,
                                               download_images=False,
                                               check_duplicate=True)
                    if result:
                        logger.info(f"  ✓ StationCrowdDensity_RealTime 已保存")
                    else:
                        logger.info(f"  ⊘ StationCrowdDensity_RealTime 数据未变化，跳过保存")
            except Exception as e:
                logger.error(f"采集失败 StationCrowdDensity_RealTime: {e}")

        # 车站预测拥挤度 (官方 24 小时更新) → 改为仅首轮采一次，文件名带时间戳
        if cycle == 1:
            try:
                logger.info("  采集: StationCrowdDensity_Forecast (按线路, 24小时, 一次性快照)...")
                forecast_crowd = {}
                for line in train_lines:
                    data = safe_api_call("PCDForecast", params={"TrainLine": line}, max_retries=1)
                    if data:
                        forecast_crowd[line] = data
                    time.sleep(0.5)
                if forecast_crowd:
                    # save_realtime_data() 内部会自动追加时间戳，避免重复
                    result = save_realtime_data(forecast_crowd, "StationCrowdDensity_Forecast",
                                               subdir="realtime_monitoring",
                                               auto_download_link=False,
                                               download_images=False,
                                               check_duplicate=False)
                    if result:
                        logger.info(f"  ✓ StationCrowdDensity_Forecast 一次性快照已保存")
                else:
                    logger.info("  StationCrowdDensity_Forecast 暂无可用数据（API可能处于非更新时段）")
            except Exception as e:
                logger.error(f"采集失败 StationCrowdDensity_Forecast: {e}")

        # EV 充电点按邮编查询 (官方 5 分钟更新)
        # 文件名带时间戳，避免覆盖上一次下载 (一次性快照留存)
        if cycle == 1:
            try:
                logger.info("  采集: EVChargingPoints_PostalCode (按邮编, 一次性快照)...")
                ev_postal_data = {}
                for code in ev_postal_codes:
                    data = safe_api_call("EVChargingPoints", params={"PostalCode": code})
                    if data:
                        ev_postal_data[code] = data
                    time.sleep(0.5)
                if ev_postal_data:
                    # save_realtime_data() 内部会自动追加时间戳
                    result = save_realtime_data(ev_postal_data, "EVChargingPoints_PostalCode",
                                               subdir="realtime_monitoring",
                                               auto_download_link=False,
                                               download_images=False,
                                               check_duplicate=False)
                    if result:
                        logger.info(f"  ✓ EVChargingPoints_PostalCode 一次性快照已保存")
            except Exception as e:
                logger.error(f"采集失败 EVChargingPoints_PostalCode: {e}")
        
        # 计算下次采集时间
        next_cycle_time = start_time + timedelta(minutes=cycle * interval_minutes)
        sleep_duration = (next_cycle_time - datetime.now()).total_seconds()
        
        if sleep_duration > 0 and datetime.now() < end_time:
            logger.info(f"\n等待 {sleep_duration:.0f} 秒后进行下一轮采集...")
            time.sleep(sleep_duration)
    
    logger.info("\n实时监控结束")


# ==================== 主程序 ====================

def download_all_historical_data():
    """下载所有可用的历史和静态动态数据（完整30个API）"""
    logger.info("=" * 80)
    logger.info("开始下载 LTA DataMall 动态交通数据")
    logger.info(f"下载时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info(f"输出目录: {OUTPUT_DIR}")
    logger.info("=" * 80)
    
    try:
        # 公共交通相关数据
        download_bus_services()
        time.sleep(2)
        
        download_bus_routes()
        time.sleep(2)
        
        download_bus_stops()
        time.sleep(2)
        
        download_bus_arrival(sample_size=50)
        time.sleep(2)
        
        # 客流量数据：下载最近3个可用历史月份（API最多支持近3个月）
        # 规则：数据在每月10日生成，当前为2026-05，可用最近月份为202604/202603/202602
        available_pv_months = ["202604", "202603", "202602"]
        for pv_month in available_pv_months:
            download_passenger_volume(pv_month)
            time.sleep(2)
        
        download_taxi_availability()
        time.sleep(2)
        
        download_taxi_stands()
        time.sleep(2)
        
        download_train_service_alerts()
        time.sleep(2)
        
        download_facilities_maintenance()
        time.sleep(2)
        
        download_station_crowd_density()
        time.sleep(2)
        
        download_planned_bus_routes()
        time.sleep(2)
        
        # 交通相关数据
        download_carpark_availability()
        time.sleep(2)
        
        download_estimated_travel_times()
        time.sleep(2)
        
        download_faulty_traffic_lights()
        time.sleep(2)
        
        download_planned_road_openings()
        time.sleep(2)
        
        download_approved_road_works()
        time.sleep(2)
        
        download_traffic_images(download_sample=True, sample_count=5)
        time.sleep(2)
        
        download_traffic_incidents()
        time.sleep(2)
        
        download_traffic_speed_bands()
        time.sleep(2)
        
        download_vms_emas()
        time.sleep(2)
        
        download_traffic_flow()
        time.sleep(2)
        
        download_flood_alerts()
        time.sleep(2)
        
        # 主动出行相关
        download_bicycle_parking()
        time.sleep(2)
        
        # 电动车相关
        download_ev_charging_points()
        time.sleep(2)
        
        # 地理空间数据（下载所有34个图层的SHP文件）
        download_geospatial_layers(download_all=True, priority_only=False)
        
        logger.info("\n" + "=" * 80)
        logger.info("✓ 所有历史数据下载完成！")
        logger.info("=" * 80)
        
    except Exception as e:
        logger.error(f"下载过程中出现错误: {e}", exc_info=True)


if __name__ == "__main__":
    import sys
    
    print("=" * 80)
    print("LTA DataMall 动态交通数据下载工具（完整版）")
    print("=" * 80)
    print("\n请选择运行模式:")
    print("1. 下载所有可用的历史和静态动态数据（30个API）")
    print("2. 启动实时监控（17种实时数据，100%覆盖）")
    print("3. 两者都执行（先下载历史数据，再启动监控）")
    print("=" * 80)
    
    choice = input("\n请输入选择 (1/2/3，默认1): ").strip() or "1"
    
    if choice == "1":
        download_all_historical_data()
    elif choice == "2":
        duration = input("请输入监控时长（小时，默认24）: ").strip()
        interval = input("请输入采集间隔（分钟，默认5）: ").strip()
        
        duration_hours = float(duration) if duration else 24
        interval_minutes = float(interval) if interval else 5
        
        start_realtime_monitoring(duration_hours, interval_minutes)
    elif choice == "3":
        download_all_historical_data()
        
        print("\n" + "=" * 80)
        print("历史数据下载完成，即将启动实时监控...")
        print("=" * 80)
        
        duration = input("请输入监控时长（小时，默认24）: ").strip()
        interval = input("请输入采集间隔（分钟，默认5）: ").strip()
        
        duration_hours = float(duration) if duration else 24
        interval_minutes = float(interval) if interval else 5
        
        start_realtime_monitoring(duration_hours, interval_minutes)
    else:
        print("无效选择，退出程序")
