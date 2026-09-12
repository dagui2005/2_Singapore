# 新加坡交通数据项目 - 简明结构说明

**文档版本**: v2.0 整理后版本  
**生成时间**: 2026-07-04  
**适用对象**: 项目开发者和维护者

---

## 快速导航

- **想运行程序?** → 查看 [使用指南](#使用指南)
- **想了解文件用途?** → 查看 [核心文件说明](#核心文件说明)
- **想了解目录结构?** → 查看 [目录结构概览](#目录结构概览)

---

## 项目概述

本项目是一个完整的新加坡交通数据下载、处理和分析工具集，包含：

1. **LTA DataMall API数据下载** - 支持30个API的历史和实时数据
2. **静态数据管理** - 人口、交通、公共交通等静态数据集
3. **OSM数据解析** - OpenStreetMap数据的解析和处理
4. **可行性评估** - 交通数字孪生可行性评估

**技术栈**: Python 3.x + requests + pandas + GeoPandas

---

## 目录结构概览

```
2_Singapore/                          # 项目根目录
│
├── [核心程序文件 - 留在根目录]
├── lta_dynamic_data_downloader.py    # ⭐ 核心程序 - LTA数据下载工具
├── main.py                           # 简化入口
├── config.py                         # 配置文件
├── run.bat                           # Windows快速启动脚本
├── README.md                         # 项目主文档
├── QUICK_START.md                    # 快速入门指南
├── PROJECT_MANIFEST.md               # 项目文件清单
├── requirements.txt                  # Python依赖
├── API_Key.txt                       # LTA API密钥备份
├── 无标题.mxd                        # ArcGIS地图文档
│
├── scripts/                          # [工具] 辅助脚本目录
│   ├── analysis/                     # 数据分析与处理脚本
│   │   ├── analyze_other_data.py     # 分析其他数据源
│   │   ├── analyze_other_data_samples.py  # 分析数据样本
│   │   ├── example_data_analysis.py  # 数据分析示例
│   │   ├── extract_static_links.py   # 提取静态数据链接
│   │   ├── extract_traffic_links_shp.py   # 提取交通路段SHP文件
│   │   └── check_duplicate_files.py  # 检查重复文件
│   │
│   ├── osm/                          # OSM数据处理脚本
│   │   ├── parse_osm_final.py        # OSM最终解析脚本
│   │   ├── parse_osm_geopandas.py    # GeoPandas版本解析
│   │   ├── parse_osm_other_tags_optimized.py  # 其他标签优化解析
│   │   ├── split_typ_cd_des.py       # 拆分类型代码（pandas版）
│   │   └── split_typ_cd_des_pyshp.py # 拆分类型代码（pyshp版）
│   │
│   ├── tests/                        # 测试与验证脚本
│   │   ├── test_duplicate_detection.py  # 测试重复检测功能
│   │   ├── test_pagination.py           # 测试分页下载功能
│   │   ├── verify_duplicate_detection.py # 验证重复检测
│   │   └── verify_pagination.py          # 验证分页功能
│   │
│   └── feasibility/                  # 可行性评估脚本
│       └── sg_feasibility_audit.py   # 可行性审计主脚本
│
├── docs/                             # [文档] 参考文档与技术报告
│   ├── LTA_DataMall_API_User_Guide.md    # LTA API官方文档（Markdown）
│   ├── LTA_DataMall_API_User_Guide.pdf   # LTA API官方文档（PDF）
│   ├── AUDIT_OPTIMIZATION_SUMMARY.md    # 审计优化总结
│   ├── AUDIT_QUICK_REFERENCE.md         # 审计快速参考
│   ├── DUPLICATE_DETECTION_SUMMARY.md   # 重复检测总结
│   ├── FEASIBILITY_AUDIT_FIXES.md       # 可行性审计修复记录
│   ├── OSM_OTHER_TAGS_PROCESSING_REPORT.md  # OSM标签处理报告
│   └── REALTIME_DUPLICATE_DETECTION.md  # 实时重复检测文档
│
├── reports/                          # [报告] 研究报告与参考资料
│   ├── 新加坡开放数据交通数字孪生可行性评估报告.docx
│   ├── 新加坡开放数据交通数字孪生可行性评估报告.pdf
│   ├── 余老师对于建设科研智能开放数据的想法.pdf
│   ├── 城市道路交通科研开放数据标准体系技术梳理.xlsx
│   └── Sheet_20260530.csv
│
├── project_structure_docs/           # [文档] 项目结构说明文件夹
│   ├── PROJECT_STRUCTURE_SIMPLE.md  # 本文件（简明版）
│   ├── PROJECT_STRUCTURE.md         # 详细版结构文档
│   ├── README.md                    # 文档说明
│   ├── generate_project_structure_simple.py  # 生成简明版文档的脚本
│   └── generate_project_structure.py         # 生成详细版文档的脚本
│
├── Dynamic_2026_03_16/              # [数据] LTA动态数据目录
│   ├── historical_data/             # 历史数据（JSON + SHP文件）
│   └── realtime_monitoring/         # 实时监控数据（按时间戳命名）
│
├── Static_ 2026_03/                 # [数据] 静态数据目录
│   ├── PUBLIC TRANSPORT/            # 公共交通数据（MRT站点、出租车等）
│   ├── GEOSPATIAL/                  # 地理空间数据
│   └── OTHER/                       # 其他数据（人口年龄结构等）
│
├── osm/                             # [数据] 解析后的OSM数据
│   ├── osm-lines.*                  # 道路线路（SHP+DBF+SHX）
│   ├── osm-points.*                 # 点数据（如公交站）
│   └── osm-polygon.*               # 面数据（如建筑物）
│
├── osm-expand/                      # [工具] OSM原始解析工具（历史遗留）
│
├── NeuroGravitySingapore/           # [数据] 神经重力模型数据
│
└── sg_feasibility_outputs/          # [输出] 可行性评估结果
```

---

## 核心文件说明

### 1. 主程序文件（根目录）

| 文件 | 大小 | 说明 |
|------|------|------|
| `lta_dynamic_data_downloader.py` | ~30 KB | **⭐ 核心程序** - LTA数据下载工具（完整集成版） |
| `main.py` | <1 KB | 简化入口，调用主程序 |
| `config.py` | <1 KB | 配置文件模板 |
| `run.bat` | <1 KB | Windows快速启动脚本 |

**功能特性**:
- 支持30个LTA API的数据下载
- 历史数据下载 + 实时监控（17种API）
- 自动处理链接过期、分页下载、速率控制

### 2. 数据分析脚本（scripts/analysis/）

| 文件 | 说明 |
|------|------|
| `analyze_other_data.py` | 分析其他数据源 |
| `analyze_other_data_samples.py` | 分析数据样本 |
| `example_data_analysis.py` | 数据分析示例代码 |
| `extract_static_links.py` | 提取静态数据链接 |
| `extract_traffic_links_shp.py` | 从TrafficFlow/SpeedBands JSON提取路段SHP |
| `check_duplicate_files.py` | 检查重复文件 |

### 3. OSM处理脚本（scripts/osm/）

| 文件 | 说明 |
|------|------|
| `parse_osm_final.py` | OSM数据最终解析脚本 |
| `parse_osm_geopandas.py` | 使用GeoPandas解析OSM |
| `parse_osm_other_tags_optimized.py` | 优化版其他标签解析 |
| `split_typ_cd_des.py` | 拆分SHP类型代码（pandas版） |
| `split_typ_cd_des_pyshp.py` | 拆分SHP类型代码（pyshp版） |

### 4. 可行性评估（scripts/feasibility/）

| 文件 | 说明 |
|------|------|
| `sg_feasibility_audit.py` | 可行性审计主脚本 |
| `sg_feasibility_outputs/` | 审计输出目录（根目录下） |
| `reports/新加坡开放数据交通数字孪生可行性评估报告.*` | 可行性评估报告 |

### 5. 文档和配置

| 文件 | 说明 |
|------|------|
| `README.md` | 项目主文档（完整使用说明） |
| `PROJECT_MANIFEST.md` | 项目清单（文件列表） |
| `QUICK_START.md` | 快速入门指南 |
| `requirements.txt` | Python依赖（requests, pandas） |
| `API_Key.txt` | LTA API密钥备份 |
| `docs/LTA_DataMall_API_User_Guide.*` | LTA API官方参考文档 |

---

## 数据目录说明

### Dynamic_2026_03_16/ - 动态数据

**用途**: 存储从LTA API下载的动态数据

**子目录**:
- `historical_data/` - 历史数据（25+ JSON文件 + SHP文件）
- `realtime_monitoring/` - 实时监控数据（按时间戳命名）

**主要文件**:
- `TrafficSpeedBands_v4.json` - 路段速度带数据（~53 MB）
- `TrafficFlow_Data.json` - 交通流量数据（~15 MB）
- `BusRoutes.json` - 巴士路线（~8 MB）
- `TrafficSpeedBands_Links.shp` - 速度带路段SHP（143,787条）
- `TrafficFlow_Links.shp` - 交通流量路段SHP（1,278条）

### Static_ 2026_03/ - 静态数据

**用途**: 存储静态的交通相关数据

**子目录**:
- `PUBLIC TRANSPORT/` - 公共交通数据（MRT站点、出租车等）
- `GEOSPATIAL/` - 地理空间数据
- `OTHER/` - 其他数据（人口年龄结构等）

### osm/ - OpenStreetMap数据

**用途**: 存储解析后的OSM数据

**主要文件**:
- `osm-lines.*` - 道路线路（SHP + DBF + SHX）
- `osm-points.*` - 点数据（如公交站）
- `osm-polygon.*` - 面数据（如建筑物）
- `osm-multiline.*` - 复杂线路数据

---

## 使用指南

### 快速开始

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 运行主程序
python lta_dynamic_data_downloader.py

# 3. 选择运行模式
#   1 - 下载历史数据
#   2 - 启动实时监控
#   3 - 两者都执行
```

### 常见任务

#### 任务1: 下载LTA数据

```bash
python lta_dynamic_data_downloader.py
# 选择模式1（下载所有历史和静态数据）
```

**输出**: `Dynamic_2026_03_16/historical_data/`

#### 任务2: 解析OSM数据

```bash
cd scripts/osm/
python parse_osm_final.py
```

**输出**: `osm/osm-*.shp` 文件

#### 任务3: 提取交通路段SHP

```bash
python scripts/analysis/extract_traffic_links_shp.py
```

**输出**: `Dynamic_2026_03_16/historical_data/TrafficSpeedBands_Links.shp` 等

#### 任务4: 运行可行性评估

```bash
python scripts/feasibility/sg_feasibility_audit.py
```

**输出**: `sg_feasibility_outputs/`

---

## 开发和调试

### 测试脚本（scripts/tests/）

- `test_duplicate_detection.py` - 测试重复检测功能
- `test_pagination.py` - 测试分页下载功能
- `verify_duplicate_detection.py` - 验证重复检测
- `verify_pagination.py` - 验证分页功能

### 技术文档（docs/）

- `AUDIT_OPTIMIZATION_SUMMARY.md` - 审计优化总结
- `FEASIBILITY_AUDIT_FIXES.md` - 审计修复文档
- `DUPLICATE_DETECTION_SUMMARY.md` - 重复检测说明
- `REALTIME_DUPLICATE_DETECTION.md` - 实时重复检测

---

## 维护和更新

### 定期任务

1. **清理旧数据** - 删除 `realtime_monitoring/` 中超过30天的数据
2. **备份重要数据** - 备份 `Static_ 2026_03/` 和 `osm/` 目录
3. **更新文档** - 当添加新功能时，更新 `README.md`
4. **检查API** - 定期检查LTA API是否有更新

### 添加新功能

1. 根据功能类型，在 `scripts/` 下合适的子目录创建脚本
2. 更新 `README.md` 中的功能说明
3. 更新 `PROJECT_MANIFEST.md` 中的文件清单
4. 重新生成项目结构文档（运行 `project_structure_docs/generate_project_structure_simple.py`）

---

## 常见问题

### Q1: 为什么有些JSON文件只有几KB？

**A**: 这些文件可能只包含链接而不是实际数据。工具会自动处理并下载实际数据，保存为 `*_Data.json` 文件。

示例:
- `TrafficFlow.json` (1.9 KB) → `TrafficFlow_Data.json` (15.5 MB)

### Q2: 实时监控产生太多文件怎么办？

**A**: 建议：
1. 增加采集间隔（修改代码中的间隔时间）
2. 定期清理旧文件
3. 使用数据库存储而非JSON文件

### Q3: 如何只下载部分数据？

**A**: 修改 `lta_dynamic_data_downloader.py` 中的 `download_all_historical_data()` 函数，注释掉不需要的下载调用。

### Q4: OSM数据如何更新？

**A**: 
1. 从OpenStreetMap官网下载最新的Singapore OSM数据（.pbf格式）
2. 使用 `scripts/osm/` 中的脚本重新解析
3. 更新 `osm/` 目录中的文件

---

## 参考文档

- **LTA API文档**: `docs/LTA_DataMall_API_User_Guide.md`
- **项目清单**: `PROJECT_MANIFEST.md`
- **快速入门**: `QUICK_START.md`
- **数据字典**: `Dynamic_2026_03_16/DATA_DICTIONARY.md`
- **OSM处理报告**: `docs/OSM_OTHER_TAGS_PROCESSING_REPORT.md`

---

## 联系和支持

- **查看日志**: `Dynamic_2026_03_16/download.log`
- **查看文档**: 阅读 `README.md` 获取详细说明
- **问题反馈**: 记录到项目Issue跟踪系统

---

**文档版本**: v2.0 整理后版本  
**最后更新**: 2026-07-04  
**维护者**: AI Assistant
