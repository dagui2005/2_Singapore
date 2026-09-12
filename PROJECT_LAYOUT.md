# 2_Singapore 项目实际目录与文件结构

> **生成时间**：2026-09-11  
> **项目根**：`d:\Luan\2026-05\2_Singapore\`  
> **项目类型**：PyCharm Python 工程（多数据源 + 实时/历史抓取 + MATSim 仿真准备）  
> **Git 状态**：master 分支无 commit，工作区已有大量待提交文件（详见 `git status`）  
> **总体积 / 总文件数**：≈ 27.92 GB / 19,589 个文件（含 `.gitignore` 未追踪的二进制/数据文件）

---

## 0. 一页总览

| 指标 | 数值 |
|---|---|
| 根级文件 | 11 个（4 文档 + 1 启动器 + 2 关键 Python + 1 配置 + 1 Key + 2 杂项） |
| 根级文件夹 | 12 个（代码 / 文档 / 数据 / 仿真 / 输出 / 缓存） |
| Python 源文件 | `main.py` / `lta_dynamic_data_downloader.py` / `scripts/*.py` (18) / `osm-expand/*.py` (5) / `project_structure_docs/*.py` (2) = **28 个** |
| 文档 (md/pdf/docx) | README / QUICK_START / PROJECT_MANIFEST + `docs/` (9) + `project_structure_docs/` (5) + `reports/` (6) + `sg_feasibility_outputs/` (1) + `osm/OSM_属性表结构说明.md` = **≥ 25 份** |
| 实时数据抓取 | `lta_dynamic_data_downloader.py` v2.2，覆盖 LTA DataMall 17 端点 + 24h 调度 |
| 历史数据 | `Dynamic_2026_03_16/historical_data/` 共 35 类 json + 1 套 SHP 压缩包（97 MB） |
| 静态数据 | `Static_2026_03/` ≈ 2.26 GB / 578 文件（GEOSPATIAL 267 / OTHER 301 / PUBLIC TRANSPORT 6 / 其它 4） |
| 实时图片 | `Dynamic_2026_03_16/realtime_monitoring/images/` ≈ 7.65 GB / 8,552 张 JPG |
| 仿真数据 | `Singapore_OD_MATSim_FinalData/` ≈ 8.88 GB / 194 文件（OSM 路网 7.5 GB） |
| 大型 TIF 栅格 | `Static_2026_03/OTHER/Population/` ≈ 685 MB / 249 张 100m/1km WorldPop 栅格 |
| 隐藏配置 | `.idea/`（PyCharm 项目配置） |

---

## 1. 根目录文件清单

| 文件 | 大小 | 类型 | 作用 |
|---|---|---|---|
| `main.py` | < 5 KB | Python 入口 | 项目顶层调度（实际为早期入口，新工作由 `lta_dynamic_data_downloader.py` 接管） |
| `lta_dynamic_data_downloader.py` | ~90 KB | Python 核心 | LTA DataMall 30 个端点的历史下载 + 实时监控（v2.2，含 TrafficSpeedBands 30 分钟优化） |
| `config.py` | < 2 KB | Python 配置 | API Key / 路径 / 调度参数统一配置 |
| `requirements.txt` | < 1 KB | 依赖清单 | pandas / geopandas / requests / pyshp / openpyxl 等 |
| `run.bat` | < 1 KB | Windows 启动器 | `python main.py` 双击启动 |
| `API_Key.txt` | < 1 KB | 凭据 | LTA DataMall AccountKey（已 .gitignore 候选） |
| `README.md` | ~30 KB | 项目说明 | 入口文档（含 2026-09-04 新增的"工程目录结构说明"） |
| `QUICK_START.md` | < 2 KB | 速通指南 | 30 秒启动步骤 |
| `PROJECT_MANIFEST.md` | ~5 KB | 清单 | 数据 / 模型 / 仿真依赖关系总图 |
| `无标题.mxd` | < 5 KB | ArcMap 工程 | 残留的旧版 GIS 工程文件 |
| `.idea/` | < 1 MB | PyCharm | IDE 配置（.iml / .gitignore / misc.xml / vcs.xml / dbnavigator.xml） |

---

## 2. 根级文件夹结构

```
2_Singapore/
├── docs/                                  # 全局技术文档
├── scripts/                               # Python 工具脚本
├── project_structure_docs/                # 旧版结构归档
├── reports/                               # 报告产物
├── sg_feasibility_outputs/                # SG 可行性分析输出
├── osm/                                   # OSM 路网 shp/qmd
├── osm-expand/                            # OSM 扩展工具（Python）
├── Static_ 2026_03/                       # 静态底层数据（2.26 GB）
├── Dynamic_2026_03_16/                    # 动态数据缓存（7.7 GB）
├── Singapore_OD_MATSim_FinalData/         # MATSim 仿真数据包（8.9 GB）
├── NeuroGravitySingapore/                 # 神经引力线应用
├── .idea/                                 # PyCharm 配置
└── (根级 11 个文件，详见 §1)
```

### 2.1 `docs/` （9 文件，~30 KB + 1 PDF）

| 文件 | 用途 |
|---|---|
| `LTA_DataMall_API_User_Guide.md` | LTA 30 个端点官方指南摘录 |
| `LTA_DataMall_API_User_Guide.pdf` | 同上 PDF 版 |
| `REALTIME_POLL_OPTIMIZATION.md` | v1.1 实时轮询优化方案（2026-09-04 增 §11 后暂无更新） |
| `8ca9f0f0-*.md` 等其它 md | 临时分析笔记 |

### 2.2 `scripts/` （18 个 .py）

按子目录划分（仅 1 层，但下挂若干 .py）：

- `scripts/analysis/` — 分析工具
- `scripts/feasibility/` — 可行性脚本
- `scripts/osm/` — OSM 辅助脚本
- `scripts/scripts/matsim/network/` — MATSim 路网生成
- `scripts/tests/` — 单元测试
- 根级 .py — 入口与通用工具

### 2.3 `project_structure_docs/` （5 文件）

历史项目结构文档归档（`PROJECT_STRUCTURE.md` 115 KB、`PROJECT_STRUCTURE_SIMPLE.md` 12.7 KB 等），新文档以本文件与 `README.md` 为准。

### 2.4 `reports/` （6 文件）

| 文件 | 用途 |
|---|---|
| `2_Singapore_项目概述.pdf` | 项目阶段交付报告 |
| `NeuroGravity_Progress_Report.pdf` | 神经引力线专题报告 |
| `NeuroGravity_Progress_Report.docx` | 同上 Word 版 |
| `progress_check.xlsx` | 进度追踪表 |
| 其它 1 份 | 备注 |

### 2.5 `sg_feasibility_outputs/` （1 .md）

Singapore 可行性研究的中期分析（说明文档 1 份）。

### 2.6 `osm/` （27 文件，含多份 SHP/QMD）

| 类别 | 文件 | 用途 |
|---|---|---|
| `osm-lines.*` | 8 文件（shp/dbf/shx/prj/cpg + qmd） | OSM 道路线（dbf 634 MB） |
| `osm-multiline.*` | 6 文件 | OSM 多线要素 |
| `osm-points.*` | 6 文件 | OSM 点要素 |
| `osm-polygon.*` | 6 文件 | OSM 多边形 |
| `*_expanded.*` | 4 套 | 扩展版（含全部属性） |
| `OSM_属性表结构说明.md` | 1 份 | OSM 数据字典（94 KB） |
| `relations.csv` + `.qmd` | 2 文件 | 关系表与说明 |

### 2.7 `osm-expand/` （5 个 .py + 1 .md）

OSM 扩展工具集（脚本集 + 说明文档）。

### 2.8 `NeuroGravitySingapore/` （SINGAPORE/ 11 文件）

| 文件 | 用途 |
|---|---|
| `*.geojson` | 神经引力线输入 |
| `*.png` | 可视化图片 |
| `*.cpg` / `*.shp` / `*.shx` / `*.prj` / `*.dbf` | 路网 shp |
| `*.py` | 神经引力线算法 |
| `*.html` | 报告 HTML |

### 2.9 `Static_ 2026_03/` （2.26 GB / 578 文件）

```
Static_ 2026_03/
├── .workbuddy/memory/                    # 2 份 AI 记忆 markdown
├── GEOSPATIAL/                           # 267 文件 / 1.53 GB  ─ 29 套 SHP
├── OTHER/                                # 301 文件 / 0.73 GB
│   ├── goverment_open/                   # 44 文件（GHS 2025 + 早期统计）
│   ├── Population/                       # 249 张 WorldPop 100m/1km TIF
│   ├── siteselect_sg-main/               # 7 文件（站点选址 Python 工具）
│   ├── anchorlayers/                     # 海洋锚点 SHP
│   └── OTHER_DATA_DOCUMENTATION.md       # 综合说明（1 份 v1.1）
└── PUBLIC TRANSPORT/                     # 6 文件（4 个子目录各 1 份）
    ├── Monthly Taxi Population/
    ├── Number of MRT  LRT Station/
    ├── PremiumBusServices/
    └── Rail Length/
```

**GEOSPATIAL/ 关键图层**（29 套，列代表性）：

- `ArrowMarking_Mar2026/` — 路面箭头标注
- `BusStopLocation_Mar2026/` — 公交站点（含 5,000+ 站点）
- `MasterPlan2019LandUselayer.geojson` — 2019 总规土地利用
- `HDBExistingBuilding.geojson` — HDB 既有建筑（57 MB）
- `MasterPlan2019Buildinglayer.geojson` — 总规建筑层（53 MB）
- `URANoofDwellingUnits.geojson` — URA 住宅单元数（39 MB）
- 等等（含 TrafficCamera / CyclingPath / HawkerCentres / Parks / PreSchools / TouristAttractions 等）

**OTHER/ 详细清单**：

| 子目录 | 文件数 | 体积 | 关键文件 |
|---|---|---|---|
| `OTHER/goverment_open/` | 44 | ~30 MB | `outputFile.xlsx` 19 张子表、`hsetod2025e.xlsx`、`respopagesex*.xlsx`、`hsefa2025e.xlsx` 等 GHS 2025 数据 |
| `OTHER/Population/` | 249 | ~685 MB | WorldPop 2025/2026 100m + 1km 栅格 × 4 类（按年龄+性别） |
| `OTHER/siteselect_sg-main/` | 7 | < 5 MB | 站点选址 Python 工具源码 |
| `OTHER/anchorlayers/` | 1 | < 1 MB | 海洋锚点 shp |
| `OTHER/OTHER_DATA_DOCUMENTATION.md` | 1 | ~40 KB | 综合说明 v1.1（含 §11 GHS 2025 详表） |

**PUBLIC TRANSPORT/ 详细清单**：4 个子目录各 1 份 CSV/XLSX（出租车月度数量、MRT/LRT 站数、优质巴士、轨道长度）。

### 2.10 `Dynamic_2026_03_16/` （7.68 GB / 8,553 文件）

```
Dynamic_2026_03_16/
├── historical_data/                      # 历史抓取
│   ├── *.json                            # 35 份 LTA 端点历史全量（~3 GB）
│   └── geospatial/                       # 1 份 SHP 压缩包（97 MB）
└── realtime_monitoring/
    └── images/                           # 8,552 张交通监控 JPG（7.65 GB）
```

**historical_data 涵盖端点**（35 份 json）：

| 端点 | 类别 | 体量 |
|---|---|---|
| TrafficIncidents / FaultyTrafficLights | 事件 | 小 |
| VMS / PubFloodAlerts | 道路态势 | 中 |
| Taxi-Availability | 1 分钟刷新 | 大 |
| BusArrival v3 | 20 秒 | 巨大 |
| TrafficSpeedBands | 24 分钟全量 | **143,787 条**（最大） |
| EstTravelTimes | 5 分钟 | 5,556 条 |
| CarParkAvailability v2 | 5 分钟 | ~2,000 停车场 |
| StationCrowdDensity_RealTime / _Forecast | 10 分钟 / 24h | 中 |
| EVChargingPoints_Batch / _PostalCode | 5 分钟 / 月 | 中 |
| TrainServiceAlerts / FacilitiesMaintenance | Ad hoc | 小 |
| TrafficFlow | 季度（S3 链接） | 巨型 SHP |
| RoadOpenings / RoadWorks | 24h | 小 |

**realtime_monitoring/images/**：8,552 张 JPG = 至少 6 个摄像头点位 × 1,427 个时间戳，平均每张 ~900 KB（凌晨时段高压缩、白天高峰时段较高）。

### 2.11 `Singapore_OD_MATSim_FinalData/` （8.88 GB / 194 文件）

MATSim 仿真所需的"最终数据"包，按用途分 10 个子目录：

| 编号 | 子目录 | 文件数 | 体积 | 关键内容 |
|---|---|---|---|---|
| 01 | `01_Boundary_TAZ` | 3 | 0.01 GB | 规划区 / TAZ 边界 shp |
| 02 | `02_Population_Residence` | 19 | 0.03 GB | GHS 2025 xlsx + csv（19 文件，多版本冗余）|
| 03 | `03_Workplace_Employment` | 12 | 0.00 GB | 就业岗位分布 csv |
| 04 | `04_LandUse_Building` | 4 | 0.30 GB | 4 份大 geojson（建筑 57/53/174/39 MB）|
| 05 | `05_POI_Enterprise` | 5 | 0.33 GB | POI 与企业（poi.csv 7.4 MB）|
| 06 | `06_Census_TravelBehavior` | 60 | 0.00 GB | 3 套 outputFile (3/4/5) + T1-T21 CSV（约 60 个文件，含 4-5 份冗余）|
| 07 | `07_RoadNetwork` | 49 | **8.18 GB** | OSM 路网原始 / expanded 双向，详见下表 |
| 08 | `08_TrafficCount` | 6 | 0.02 GB | 6 个路口流量检测站 |
| 09 | `09_Auxiliary` | 19 | 0.02 GB | POI_Background（19 个 shp/geojson）|
| 10 | `10_Documentation` | 1 | 0.00 GB | 1 份说明文档 |

**07_RoadNetwork 8.18 GB 拆分**（最重）：

- `osm-lines.dbf` 634 MB / `osm-polygon.dbf` 985 MB
- `osm-lines_expanded.dbf` **3.23 GB**（最大）
- `osm-polygon_expanded.dbf` 1.69 GB
- `osm-points_expanded.dbf` 1.72 GB
- `MasterPlan2019RoadGraphiclayer.geojson` 5.9 MB
- `relations.csv` 6.6 MB

> ⚠️ **数据冗余提示**：`osm/` 与 `Singapore_OD_MATSim_FinalData/07_RoadNetwork/` 内容高度重叠，存储合计 ~3.6 GB 的 OSM 完整 dbf（4 份），可通过 `scripts/osm/` 工具按需生成而避免重复存储。

### 2.12 `NeuroGravitySingapore/SINGAPORE/` （11 文件）

神经引力线（Neural Gravity）应用专题：输入 geojson + Python 算法 + 可视化 PNG/HTML。

---

## 3. 文件类型分布

| 扩展名 | 文件数 | 估算体积 | 用途 |
|---|---|---|---|
| `.py` | 28 | < 5 MB | 全部 Python 源码 |
| `.md` | ≥ 25 | ~500 KB | 全部说明文档 |
| `.xlsx` | ≥ 30 | ~30 MB | 数据表（主要是 GHS 2025）|
| `.csv` | ≥ 60 | ~30 MB | 数据表 / 中间产物 |
| `.json` | 36 | ~2 GB | LTA 历史数据（每份 50-500 MB）|
| `.shp` + `.dbf` + `.shx` | 各 ~50 | **~7 GB** | 矢量数据 |
| `.geojson` | 11 | ~340 MB | 矢量轻量交换 |
| `.tif` | 249 | ~685 MB | WorldPop 栅格 |
| `.jpg` | **8,552** | **7.65 GB** | 实时监控图像 |
| `.pdf` | 4 | ~10 MB | 报告 |
| `.docx` | 1 | < 1 MB | 报告 |
| `.bat` | 1 | < 1 KB | 启动器 |
| `.qmd` | 5 | < 50 KB | Quarto 说明 |
| `.cpg` / `.prj` | 若干 | < 100 KB | SHP 配套 |
| `.cfg` | 85 | < 1 MB | 配置（多为 SHP 同名）|
| `.lyr` | 29 | < 1 MB | ArcMap 图层文件 |
| `.sbn` / `.sbx` | 56 | < 5 MB | SHP 空间索引 |
| `.mxd` | 1 | < 5 KB | ArcMap 工程 |

---

## 4. 数据流与依赖关系

```
LTA DataMall API
        │
        ▼
[lta_dynamic_data_downloader.py v2.2]
        │
        ├── 历史模式 ──► Dynamic_2026_03_16/historical_data/*.json (35)
        │                       │
        │                       ▼
        │              scripts/analysis/* ──► 仿真/报告
        │
        └── 实时模式 ──► Dynamic_2026_03_16/realtime_monitoring/{json,images}/
                                │
                                ▼
                        scripts/feasibility/* ──► sg_feasibility_outputs/

Static_ 2026_03/  ────────────────────► 仿真底图
Singapore_OD_MATSim_FinalData/  ─────► MATSim 网络生成
osm/ + osm-expand/  ────────────────► scripts/scripts/matsim/network/
                                            │
                                            ▼
                                   NeuroGravitySingapore/SINGAPORE/
                                            │
                                            ▼
                                       reports/
```

---

## 5. 已知问题与改进建议

1. **数据冗余**
   - `02_Population_Residence/` 与 `Static_2026_03/OTHER/goverment_open/` 同时存有 GHS 2025 同源表，但前者是 19 份旧版（多含 `outputFile (2)/(3)/(4)/(5).xlsx`），后者是 6 份最新版。建议以 `OTHER/goverment_open/` 为准，把 02/06 中的 `outputFile (2)..(5).xlsx` 系列迁至 `archive/`。
   - `osm/` 与 `07_RoadNetwork/` 内容高度重叠（合计约 3.6 GB 重复 dbf）。建议保留 `07_RoadNetwork/` 作为权威，删除 `osm/` 的 expanded 系列。
2. **空文件 / 占位符**
   - `08_TrafficCount/` 仅 6 个文件（典型路口流量检测站），若 6 个检测站不足以代表全市路网，应补充数据。
   - `01_Boundary_TAZ/` 仅 3 文件，需确认是否齐全（典型应 ≥ 5 类边界：PA/Subzone/TAZ/Road/Rail）。
3. **监控图片量级**
   - 8,552 张 JPG = 7.65 GB，建议每月清理一次（保留最近 30 天），或迁移到 NAS。
4. **实时数据调度**
   - `lta_dynamic_data_downloader.py` 已优化至 v2.2，TrafficSpeedBands 单次 24 分钟问题已通过 30 分钟轮询缓解。
5. **未使用文件**
   - `无标题.mxd`、`.idea/`（PyCharm 缓存）建议加入 `.gitignore`。
   - `API_Key.txt` 强烈建议立即加入 `.gitignore`（如尚未加入），改为 `.env` + `python-dotenv` 读取。

---

## 6. 维护说明

- 本文档**仅描述实际物理结构**，不包含代码实现细节。
- 字段、列结构、枚举值等元信息请查阅 `Static_2026_03/OTHER/OTHER_DATA_DOCUMENTATION.md`（v1.1 §11 已收录 GHS 2025 全部 19 张子表）。
- 实时端点调度策略与优化过程请查阅 `docs/REALTIME_POLL_OPTIMIZATION.md`（v1.1）。
- 若 `git status` 中的 `new file:` 列表出现新文件或被清理，请同步更新本文档。
- 与 `README.md` 的"工程目录结构说明"互补：README 偏向"作用描述"，本文件偏向"实物清单 + 体积/数量"。

---

*文档版本：v1.0（2026-09-11 首版） · 维护者：AI Assistant · 数据采集：PowerShell 递归 + 列表比对*
