# 数据集下载与同步指南

> 本仓库**不包含任何大型数据集**。本文件给出所有数据集的官方下载链接、目录约定以及建议的同步方式。

## 快速索引

| 数据族 | 目录约定 | 大小 | 入口 |
| --- | --- | --- | --- |
| LTA DataMall（动态）| `Dynamic_*/` | ~2 GB | [lta_dynamic_data_downloader.py](../lta_dynamic_data_downloader.py) 自动抓取 |
| 静态 2026-03 数据集 | `Static_ 2026_03/` | ~5 GB | 本文件 § 1 |
| OD 矩阵 + MATSim 完整数据 | `Singapore_OD_MATSim_FinalData/` | ~9 GB | 本文件 § 2 |
| 政府开放数据 | `Static_ 2026_03/OTHER/goverment_open/` | ~700 MB | 本文件 § 3 |
| NeuroGravity 神经引力模型数据 | `NeuroGravitySingapore/` | ~10 MB | 自行生成 |
| OSM 子区域扩展数据 | `osm/` | ~30 MB | [`osm-expand/`](../osm-expand/) 自带脚本生成 |

---

## 1. 静态 2026-03 数据集（Static_ 2026_03/）

由 [`lta_dynamic_data_downloader.py`](../lta_dynamic_data_downloader.py) 不抓取的 **官方静态** 数据，按月份快照。

### 1.1 子目录布局

```
Static_ 2026_03/
├── GEOSPATIAL/                # 1:10k 数字地图（shapefile），由 SLA / OneMap 提供
├── PUBLIC TRANSPORT/          # 公共交通统计数据（csv）
├── PARKING/                   # 停车数据
├── TRAFFIC/                   # 交通数据
├── TAXI/                      # 出租车数据
├── COACH_BUS/                 # 长途巴士数据
├── LANDSLIDE/                 # 滑坡风险图（GeoTIFF）
├── DEVELOPMENT_CONTROL/       # 发展控制数据
├── CROSS_BORDER/              # 跨境数据
└── OTHER/                     # 政府开放数据集
```

### 1.2 PUBLIC TRANSPORT 含 6 个 CSV（小数据，已随源码入仓）

| 文件名 | 来源 | 估算大小 |
| --- | --- | --- |
| `monthly_ave_daily_pt_ridership.csv` | https://datamall.lta.gov.sg | 30 KB |
| `yearly_ave_daily_pt_ridership.csv` | https://datamall.lta.gov.sg | 40 KB |
| `Rail Length/Rail Length/yearly_rail_length.csv` | https://datamall.lta.gov.sg | 5 KB |
| `Number of MRT  LRT Station/annual_rts_stations.csv` | https://datamall.lta.gov.sg | 2 KB |
| `Monthly Taxi Population/monthly_taxi_fleet.csv` | https://datamall.lta.gov.sg | 5 KB |
| `PremiumBusServices/PremiumBusServicesCSV20260121.csv` | https://datamall.lta.gov.sg | 200 KB |

### 1.3 GEOSPATIAL 与 GeoTIFF

可通过以下来源获取 shapefile 与 GeoTIFF：

| 子目录 | 数据源 |
| --- | --- |
| `GEOSPATIAL/ArrowMarking_Mar2026/` | SLA MasterPlan (ArrowMarking) — 由 LTA 接口解析 |
| `GEOSPATIAL/Building_Mar2026/` | https://data.gov.sg/dataset/building-outline |
| `GEOSPATIAL/Road_Mar2026/` | https://data.gov.sg/dataset/master-plan-2019-road-layer |
| `GEOSPATIAL/SchoolZone_Mar2026/` | https://www.google.com/maps/d/SchoolZoneSG |
| `TRAFFIC/*.tif` | LTA 实时摄像头缩略图 + GeoTIFF 拼接 |

---

## 2. OD 矩阵 + MATSim 完整数据（Singapore_OD_MATSim_FinalData/）

约 **9 GB**，包含 OD 矩阵生成与 MATSim 仿真所需的全部数据，详见 [目录内 README](../Singapore_OD_MATSim_FinalData/README.md)。

### 2.1 来源

| 子目录 | 公开来源 |
| --- | --- |
| `01_Boundary_TAZ/` | URA MasterPlan 2019 Subzone/Planning Area |
| `02_Population_Residence/` | SingStat Census 2020 + HDB 住址坐标 |
| `03_Workplace_Employment/` | Census 2020 Working Population + ACRA |
| `04_LandUse_Building/` | URA MasterPlan 2019 Land Use + Building |
| `05_POI_Enterprise/ACRA/` | https://www.acra.gov.sg (bulk) |
| `05_POI_Enterprise/HealthFacilities/` | https://www.moh.gov.sg |
| `06_Census_TravelBehavior/` | SingStat Census 2020 Travel |
| `07_RoadNetwork/RoadSectionLine_Mar2026/` | OneMap / SLA / LTA |
| `08_TrafficCount/` | https://datamall.lta.gov.sg |
| `09_Auxiliary/` | LTA MyTransport.sg |

---

## 3. 政府开放数据（Static_ 2026_03/OTHER/goverment_open/）

约 **670 MB**，详见 [`目录内 README`](../Static_%202026_03/OTHER/goverment_open/README.md)。

### 3.1 出处

| 来源 | URL |
| --- | --- |
| data.gov.sg (主门户) | https://data.gov.sg |
| URA GIS 数据集 | https://www.ura.gov.sg/Corporate/GIS-Datasets |
| HDB GHS 数据集 | https://www.hdb.gov.sg/residential/salesofnewflats/datatabasestats/GHS |
| ACRA 全字母企业注册 | https://www.acra.gov.sg |
| SingStat 人口数据 | https://www.singstat.gov.sg |
| OneMap | https://onemap.sg |

---

## 4. LTA DataMall 动态数据（Dynamic_*/）

由 [`lta_dynamic_data_downloader.py`](../lta_dynamic_data_downloader.py) 自动抓取，无需手动下载。

参考:
- 接口列表：[docs/LTA_DataMall_API_User_Guide.md](LTA_DataMall_API_User_Guide.md)
- 轮询策略：[docs/REALTIME_POLL_OPTIMIZATION.md](REALTIME_POLL_OPTIMIZATION.md)

需要 API Key：本地 `API_Key.txt`（**不入库**），按 [PROJECT_MANIFEST.md §…](../PROJECT_MANIFEST.md) 配置。

---

## 5. 推荐的同步工作流

### 5.1 直接 wget + 解压（最简单）

```bash
# Static_ 2026_03/PUBLIC TRANSPORT/ 已随源码入仓，可直接使用。
# 其它数据按需下载到对应目录。
```

### 5.2 用 DVC（推荐团队协作）

```bash
pip install dvc
dvc init  # 在仓库根目录
dvc add Singapore_OD_MATSim_FinalData
dvc remote add -d myremote s3://bucket/singapore-od
dvc push
# 同事合作时：dvc pull Singapore_OD_MATSim_FinalData
```

### 5.3 用 git-lfs（仅对单文件大对象）

不推荐（数据规模大但文件数中等，DVC 更合适）。

---

## 6. 维护提示

- 数据集大、入库慢、变化多，请使用 DVC 或外部云盘（百度网盘、企业 NAS）。
- 在 PR 中不直接附数据；只修改 **脚本** 和 **README.md** 引用本文件。
- 任何路径变更必须同步更新 [`Singapore_OD_MATSim_FinalData/README.md`](../Singapore_OD_MATSim_FinalData/README.md)。
