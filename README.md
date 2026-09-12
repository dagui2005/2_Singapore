# Singapore 城市交通仿真与分析数据仓库

> 新加坡陆路交通管理局（LTA）DataMall 完整数据下载工具 + MATSim 仿真流水线 + 开放数据治理分析。
> 代码 + 文档仓库 ≈ **11.92 MB**。大型数据集按 [`docs/DATASETS.md`](docs/DATASETS.md) 描述下载到本地。

## 📋 项目简介

新加坡陆路交通管理局（LTA）DataMall API的完整数据下载工具，支持：
- ✅ **30个API**的历史和静态数据下载
- ✅ **17种实时数据**的持续监控（100%覆盖率）
- ✅ 自动处理链接过期问题
- ✅ 自动下载地理空间SHP文件和交通图像
- ✅ 智能分页下载和速率控制（TrafficSpeedBands 30 分钟 quasi 调度）

---

## 🚀 快速开始

### 1. 安装依赖

```bash
pip install requests
```

### 2. 运行工具

```bash
python lta_dynamic_data_downloader.py
```

### 3. 选择模式

```
请选择运行模式:
1. 下载所有可用的历史和静态动态数据（30个API）
2. 启动实时监控（17种实时数据，100%覆盖）
3. 两者都执行（先下载历史数据，再启动监控）
```

---

## 📊 功能特性

### 模式1：历史数据下载

下载以下30个API的完整数据：

#### 公共交通相关（15个）
- Bus Services - 巴士服务信息
- Bus Routes - 巴士路线信息
- Bus Stops - 巴士站点信息
- Bus Arrival - 巴士到站信息（采样50个站点）
- Passenger Volume - 客流量数据（4种类型）
- Taxi Availability - 出租车可用性
- Taxi Stands - 出租车站信息
- Train Service Alerts - 列车服务警报
- Facilities Maintenance - 设施维护信息
- Station Crowd Density - 车站拥挤度（实时+预测）
- Planned Bus Routes - 计划巴士路线

#### 交通相关（11个）
- Carpark Availability - 停车场空位
- Estimated Travel Times - 预计行程时间 ⭐
- Faulty Traffic Lights - 故障交通灯
- Planned Road Openings - 计划道路开放
- Approved Road Works - 批准的道路工程
- Traffic Images - 交通图像（含5张示例下载）
- Traffic Incidents - 交通事故
- **Traffic Speed Bands** - 路段速度带 ⭐⭐⭐
- VMS / EMAS - 可变消息标志
- **Traffic Flow** - 交通流量 ⭐⭐
- Flood Alerts - 洪水警报

#### 其他（4个）
- Bicycle Parking - 自行车停放点
- EV Charging Points - 电动车充电点（批量+按邮编）
- Geospatial Layers - 地理空间图层（29个SHP文件）

**特殊处理**：
- ✅ TrafficFlow：自动获取最新链接并立即下载
- ✅ EVChargingPoints_Batch：自动获取最新链接并立即下载
- ✅ TrafficSpeedBands & EstimatedTravelTimes：自动添加时间戳
- ✅ TrafficImages：可选下载5张示例图像
- ✅ GeospatialLayers：自动下载所有29个图层的SHP文件

### 模式2：实时监控

持续采集17种实时数据（100%覆盖率）：

| 数据类型 | 更新频率 | 采集间隔 |
|---------|---------|---------|
| TrafficIncidents | 2分钟 | 2分钟 |
| FaultyTrafficLights | 2分钟 | 2分钟 |
| VMS_EMAS | 2分钟 | 2分钟 |
| FloodAlerts | 3分钟 | 3分钟 |
| CarparkAvailability | 5分钟 | 5分钟 |
| **EstimatedTravelTimes** | 5分钟 | 5分钟 |
| TrafficImages | 5分钟 | 5分钟 |
| **TrafficSpeedBands** | 5分钟 | 5分钟 |
| **TrafficFlow** | 每小时 | 60分钟 |
| **TrainServiceAlerts** | 实时 | 5分钟 |
| **FacilitiesMaintenance** | 实时 | 5分钟 |
| **StationCrowdDensity_RealTime** | 10分钟 | 10分钟 |
| **StationCrowdDensity_Forecast** | 5分钟 | 5分钟 |
| TaxiAvailability | 5分钟 | 5分钟 |
| **EVChargingPoints_PostalCode** | 5分钟 | 5分钟 |
| **EVChargingPoints_Batch** | 5分钟 | 5分钟 |

**配置选项**：
- 监控时长：默认24小时（可自定义）
- 采集间隔：默认5分钟（可自定义）

### 模式3：组合模式

先执行模式1（下载历史数据），然后自动进入模式2（实时监控）。

---

## 📁 输出目录结构

```
Dynamic_2026_03_16/
├── historical_data/              # 历史数据
│   ├── geospatial/               # 地理空间SHP文件（29个ZIP）
│   ├── images/                   # 交通图像示例（5张JPEG）
│   ├── BusServices.json
│   ├── BusRoutes.json
│   ├── TrafficSpeedBands_v4.json (含时间戳)
│   ├── TrafficSpeedBands_v4_backup.json (原始备份)
│   ├── EstimatedTravelTimes.json (含时间戳)
│   ├── EstimatedTravelTimes_backup.json (原始备份)
│   ├── TrafficFlow_Data.json (实际数据)
│   ├── EVChargingPoints_Batch_Data.json (实际数据)
│   └── ... (共25+个文件)
│
├── realtime_monitoring/          # 实时监控数据
│   ├── TrafficIncidents_20260504_131500.json
│   ├── TrafficSpeedBands_20260504_131500.json
│   ├── CarparkAvailability_20260504_131500.json
│   └── ... (按时间戳命名)
│
└── download.log                  # 下载日志
```

---

## ⚙️ 配置说明

### API密钥

在代码第28行修改：
```python
API_KEY = "zv7bb9ZNTVKLgh4cMALjMQ=="
```

### 输出目录

在代码第29行修改：
```python
OUTPUT_DIR = "Dynamic_2026_03_16"
```

### 采样数量

巴士到站采样数量（第227行）：
```python
download_bus_arrival(sample_size=50)  # 默认50个站点
```

交通图像示例数量（第693行）：
```python
download_traffic_images(download_sample=True, sample_count=5)  # 默认5张
```

---

## 💡 使用建议

### 首次使用

1. **测试运行**：先运行模式1，下载少量数据验证配置
2. **检查输出**：确认文件正确保存到指定目录
3. **正式运行**：根据需要选择模式1或模式3

### 实时监控

1. **短期测试**：1-2小时，验证所有API正常工作
2. **日常监控**：24小时，收集一天的完整数据
3. **长期研究**：7天或更长，分析交通模式

**注意**：TrafficSpeedBands会产生大量数据（55 MB × 288次/天 ≈ 15.8 GB/天），建议：
- 使用外部硬盘存储
- 或定期清理旧数据
- 或修改代码只保存汇总统计

### 数据存储优化

如果需要长期监控，可以修改代码压缩数据：

```python
import gzip

# 在 save_json_data 函数中
with gzip.open(filepath + '.gz', 'wb') as f:
    json.dump(data, f)
```

---

## 🔧 技术细节

### 自动链接处理

某些API返回的是S3预签名URL（有效期5分钟），工具会自动：
1. 调用API获取最新链接
2. 立即下载实际数据
3. 保存到正确的文件名

涉及的API：
- TrafficFlow
- EVChargingPoints_Batch
- GeospatialWholeIsland（29个图层）
- TrafficImages（90个摄像头）

### 时间戳添加

部分API不返回时间戳字段，工具会自动：
1. 使用文件修改时间作为数据采集时间
2. 为每条记录添加 `Timestamp` 和 `DataCollectionTime` 字段
3. 备份原始文件

涉及的API：
- TrafficSpeedBands_v4
- EstimatedTravelTimes

### 分页下载

大数据集自动分页下载：
- 每批500条记录
- 自动检测最后一页
- 指数退避重试机制
- 请求间隔控制（避免被封号）

---

## 📝 常见问题

### Q1: 为什么有些文件只有几KB？

A: 这些文件可能只包含链接而不是实际数据。工具会自动处理：
- TrafficFlow → 保存为 `TrafficFlow_Data.json`
- EVChargingPoints_Batch → 保存为 `EVChargingPoints_Batch_Data.json`

### Q2: 地理空间图层下载失败怎么办？

A: S3链接有效期仅5分钟，如果下载失败：
1. 重新运行工具
2. 或手动从 `GeospatialWholeIsland_Links.json` 获取最新链接
3. 立即下载使用 `download_from_link()` 函数

### Q3: 实时监控产生太多文件怎么办？

A: 建议：
1. 增加采集间隔（如改为10分钟）
2. 定期清理旧文件
3. 使用数据库存储而非JSON文件
4. 只监控关键API（修改 `realtime_apis` 列表）

### Q4: 如何只下载部分数据？

A: 修改 `download_all_historical_data()` 函数，注释掉不需要的下载调用。

---

## 📄 许可证

本工具仅供学习和研究使用，请遵守LTA DataMall API的使用条款。

---

## 📞 支持

如有问题，请查看 `download.log` 日志文件获取详细错误信息。

## 📂 工程目录结构说明

本节说明工程根目录下每个文件夹与文件的用途、来源与典型内容。

### 根目录文件（保留）

| 文件 | 用途 |
|------|------|
| `lta_dynamic_data_downloader.py` | **核心程序**：LTA DataMall API数据下载器，支持30个API的历史下载与17个API的实时监控 |
| `main.py` | 简化入口，调用主程序 |
| `config.py` | 配置文件（API Key、运行模式等参数） |
| `run.bat` | Windows一键启动脚本 |
| `README.md` | 本文件，项目总览与使用文档 |
| `QUICK_START.md` | 快速入门指南 |
| `PROJECT_MANIFEST.md` | 项目文件清单与版本记录 |
| `requirements.txt` | Python依赖列表（requests, pandas 等） |
| `API_Key.txt` | LTA API 密钥备份 |
| `无标题.mxd` | ArcGIS 地图工程文件 |

---

### `scripts/` — 辅助脚本目录

按用途分类组织的 Python 工具脚本。

- **`scripts/analysis/`** — 数据分析与处理脚本
  - `analyze_other_data.py` / `analyze_other_data_samples.py` — 分析其他数据源与样本
  - `example_data_analysis.py` — 数据分析示例代码
  - `extract_static_links.py` — 从静态数据中提取链接信息
  - `extract_traffic_links_shp.py` — 从 TrafficFlow / SpeedBands JSON 提取路段 SHP 文件
  - `check_duplicate_files.py` — 检查目录内重复文件

- **`scripts/osm/`** — OpenStreetMap 数据处理脚本
  - `parse_osm_final.py` — OSM 数据最终解析脚本（主用）
  - `parse_osm_geopandas.py` — 基于 GeoPandas 的 OSM 解析版本
  - `parse_osm_other_tags_optimized.py` — 其他标签优化解析版本
  - `split_typ_cd_des.py` / `split_typ_cd_des_pyshp.py` — 拆分 SHP 中的类型代码字段

- **`scripts/tests/`** — 测试与验证脚本
  - `test_duplicate_detection.py` — 测试重复检测功能
  - `test_pagination.py` — 测试分页下载功能
  - `verify_duplicate_detection.py` — 验证重复检测运行结果
  - `verify_pagination.py` — 验证分页功能运行结果

- **`scripts/feasibility/`** — 可行性评估脚本
  - `sg_feasibility_audit.py` — 新加坡交通数字孪生可行性审计主脚本

- **`scripts/scripts/matsim/network/`** — MATSim 仿真网络数据（嵌套历史遗留目录）
  - 包含 MATSim 交通仿真所需的路网 XML 文件

---

### `docs/` — 参考文档与技术报告

存放 API 官方文档、技术报告与方案说明。

- `LTA_DataMall_API_User_Guide.md` / `.pdf` — LTA DataMall API 官方使用指南（Markdown 与 PDF 双版本）
- `AUDIT_OPTIMIZATION_SUMMARY.md` — 可行性审计的优化总结
- `AUDIT_QUICK_REFERENCE.md` — 审计功能的快速参考卡
- `DUPLICATE_DETECTION_SUMMARY.md` — 重复检测机制说明
- `FEASIBILITY_AUDIT_FIXES.md` — 可行性审计修复记录
- `OSM_OTHER_TAGS_PROCESSING_REPORT.md` — OSM 其他标签处理过程报告
- `REALTIME_DUPLICATE_DETECTION.md` — 实时监控中重复检测的实现文档

---

### `reports/` — 研究报告与参考资料

存放研究报告、项目参考资料及数据表。

- `新加坡开放数据交通数字孪生可行性评估报告.docx` / `.pdf` — 项目核心可行性评估报告（Word 与 PDF 版本）
- `余老师对于建设科研智能开放数据的想法.pdf` — 项目导师对科研智能开放数据建设的思考文档
- `城市道路交通科研开放数据标准体系技术梳理.xlsx` — 数据标准体系技术梳理表
- `Sheet_20260530.csv` — 2026-05-30 的数据表格

---

### `Dynamic_2026_03_16/` — LTA 动态数据

存放通过 LTA DataMall API 下载的动态交通数据。

- `historical_data/` — 历史数据目录
  - 各类 API 的 JSON 文件（如 `TrafficFlow_Data.json`、`TrafficSpeedBands_v4.json` 等）
  - 提取的 SHP 文件（如 `TrafficSpeedBands_Links.shp`、`TrafficFlow_Links.shp`）
  - 子目录 `geospatial/`（地理空间数据）、`images/`（交通图像）等
- `realtime_monitoring/` — 实时监控数据，按时间戳命名（如 `2026-07-04_15-30-00/`）
- `download.log` — 下载日志
- `DATA_DICTIONARY.md` — 数据字典说明

---

### `Static_ 2026_03/` — 静态数据

存放从 LTA 下载的静态交通相关数据。

- `PUBLIC TRANSPORT/` — 公共交通数据：MRT 站点、出租车停靠点、巴士站等
- `GEOSPATIAL/` — 地理空间数据：箭头标记、车道线等 SHP 格式数据
- `OTHER/` — 其他静态数据：人口年龄结构、统计区等
- `.workbuddy/memory/` — 配套的工作记录文件

---

### `osm/` — OpenStreetMap 解析数据

存放解析后的新加坡 OSM 数据（SHP 格式）。

- `osm-lines.*` / `osm-multiline.*` — 道路线路数据（SHP + DBF + SHX）
- `osm-points.*` — 点数据（如公交站、信号灯）
- `osm-polygon.*` — 面数据（如建筑物、绿地）

---

### `osm-expand/` — OSM 原始解析工具（历史遗留）

早期版本的 OSM 解析工具与中间产物，作为历史参考保留。

---

### `NeuroGravitySingapore/` — 神经重力模型数据

存放用于神经重力模型（Neural Gravity Model）研究的输入数据与中间结果。

---

### `sg_feasibility_outputs/` — 可行性评估输出

`scripts/feasibility/sg_feasibility_audit.py` 运行的输出结果目录，包含审计报告、统计图表等。

---

### `project_structure_docs/` — 项目结构说明文档

存放本项目的结构说明文档与文档生成脚本。

- `PROJECT_STRUCTURE_SIMPLE.md` — 简明版结构说明（推荐阅读）
- `PROJECT_STRUCTURE.md` — 详细版结构文档（含完整文件树）
- `README.md` — 文档说明与索引
- `generate_project_structure_simple.py` — 简明版结构文档的生成脚本
- `generate_project_structure.py` — 详细版结构文档的生成脚本

---

### `__pycache__/` — Python 缓存目录

Python 解释器自动生成的字节码缓存目录（`.pyc` 文件），无需手动管理。

### `.idea/` — IDE 配置目录

JetBrains IDE（如 PyCharm）的项目配置文件，包括 `.iml`、`vcs.xml`、数据源配置等。

---

**版本**: 3.0（2026-08-31 增加工程目录说明）  
**更新日期**: 2026-08-31  
**API文档**: docs/LTA_DataMall_API_User_Guide.md
