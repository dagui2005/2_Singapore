# FINAL_DATA_DICTIONARY.md
## Singapore OD → MATSim 建模最终数据集 · 数据字典

| 项目 | 内容 |
|------|------|
| **数据集名称** | Singapore_OD_MATSim_FinalData |
| **数据集根目录** | `D:\Luan\2026-05\2_Singapore\Singapore_OD_MATSim_FinalData\` |
| **文档版本** | v1.0 |
| **生成日期** | 2026-09-11 |
| **覆盖范围** | 10 个一级子目录，183 个文件（不含 `.xlsx`） |
| **建模目标** | 构建 Traffic-count-calibrated OD，支撑 MATSim 交通分配 |
| **数据主来源** | Singapore LTA DataMall、SingStat（DOS）、URA Master Plan 2019、OneMap/SLA、ACRA、OSM、HDB、NEA、NParks、MOH |
| **排除说明** | 本文档**不描述任何 `.xlsx` 文件**。所有 `.xlsx` 均已转换为同目录下同名 `.csv`（多子表拆分为 `原名__<sheet名>.csv`），因此**字段与取值一律以 CSV 为准**；`.xlsx` 原文件保留在同一目录内，仅作归档用途。 |

---

## 目录

- [0. 总览](#0-总览)
- [1. 01_Boundary_TAZ — 交通分区与空间边界](#1-01_boundary_taz--交通分区与空间边界)
- [2. 02_Population_Residence — 居住人口与 HOME 端](#2-02_population_residence--居住人口与-home-端)
- [3. 03_Workplace_Employment — 工作地与就业吸引](#3-03_workplace_employment--工作地与就业吸引)
- [4. 04_LandUse_Building — 土地利用与建筑](#4-04_landuse_building--土地利用与建筑)
- [5. 05_POI_Enterprise — POI 与企业](#5-05_poi_enterprise--poi-与企业)
- [6. 06_Census_TravelBehavior — 出行行为与方式选择](#6-06_census_travelbehavior--出行行为与方式选择)
- [7. 07_RoadNetwork — 交通网络与阻抗](#7-07_roadnetwork--交通网络与阻抗)
- [8. 08_TrafficCount — 实测交通流量](#8-08_trafficcount--实测交通流量)
- [9. 09_Auxiliary — 辅助数据](#9-09_auxiliary--辅助数据)
- [10. 10_Documentation — 说明文档](#10-10_documentation--说明文档)
- [附录 A. 统一空间单元字典](#附录-a-统一空间单元字典)
- [附录 B. CSV 转换规则（xlsx → csv）](#附录-b-csv-转换规则xlsx--csv)
- [附录 C. 字段类型与缺失值约定](#附录-c-字段类型与缺失值约定)
- [附录 D. 建模数据链与文件映射](#附录-d-建模数据链与文件映射)
- [附录 E. 已知问题与避坑清单](#附录-e-已知问题与避坑清单)
- [附录 F. 读取代码样例](#附录-f-读取代码样例)

---

# 0. 总览

## 0.1 目录结构

```text
Singapore_OD_MATSim_FinalData/
│
├─ 01_Boundary_TAZ/            空间骨架：Planning Area / Subzone 边界
├─ 02_Population_Residence/    居住端（HOME）人口与住房
├─ 03_Workplace_Employment/    工作端（WORK）就业
├─ 04_LandUse_Building/        土地利用与建筑（就业空间下分依据）
├─ 05_POI_Enterprise/          POI + ACRA 企业（活动吸引 / 就业下分）
├─ 06_Census_TravelBehavior/   出行行为、方式选择、时间分布
├─ 07_RoadNetwork/             路网与阻抗（OSM + LTA 道路）
├─ 08_TrafficCount/            实测流量（OD 校准与验证）
├─ 09_Auxiliary/               辅助数据（HDB / Transit）
└─ 10_Documentation/           说明文档（含本文件）
```

## 0.2 文件清单与统计

| 目录 | CSV | GeoJSON | SHP（含侧车） | JSON | MD | 小计（不含 xlsx） |
|------|-----|---------|--------------|------|----|------------------|
| 01_Boundary_TAZ | 0 | 3 | 0 | 0 | 0 | **3** |
| 02_Population_Residence | 13 | 0 | 0 | 0 | 0 | **13** |
| 03_Workplace_Employment | 11 | 0 | 0 | 0 | 0 | **11** |
| 04_LandUse_Building | 0 | 4 | 0 | 0 | 0 | **4** |
| 05_POI_Enterprise | 17 | 4 | 0 | 0 | 0 | **21** |
| 06_Census_TravelBehavior | 57 | 0 | 0 | 0 | 0 | **57** |
| 07_RoadNetwork | 1 | 1 | 8 组 | 0 | 1 | **~48** |
| 08_TrafficCount | 0 | 0 | 1 组 | 2 | 0 | **6** |
| 09_Auxiliary | 4 | 1 | 2 组 | 0 | 0 | **~19** |
| 10_Documentation | 0 | 0 | 0 | 0 | 1 | **1** |
| **合计** | **103** | **13** | **11 组** | **2** | **2** | **~183** |

> 说明：
> - `.shp` 必须与其同名侧车文件（`.dbf` 属性表、`.shx` 索引、`.prj` 坐标系、`.cpg` 编码声明、`.qmd` QGIS 元数据、`.sbn/.sbx` 空间索引）放在同一目录才能被读取，**不可单独移动 `.shp`**。
> - **`.xlsx` 未计入**：02 目录 5 个、03 目录 1 个、06 目录 3 个，共 9 个，均已由同名 CSV 替代，仅作归档。

## 0.3 通用约定

| 约定 | 说明 |
|------|------|
| **字符编码** | 所有 CSV 为 **UTF-8 with BOM（utf-8-sig）**，Excel 直接双击不乱码；GeoJSON 为 UTF-8 |
| **分隔符** | CSV 统一逗号 `,`，字段内含逗号时用双引号包裹（标准 RFC 4180） |
| **字段名** | 统一置于每个 CSV 的**第 1 行**；合并单元格已展开，多级表头以 `_` 连接（见 [附录 B](#附录-b-csv-转换规则xlsx--csv)） |
| **空间坐标** | GeoJSON 为 **WGS84 经纬度（EPSG:4326 / CRS84）**；SHP 中 **LTA/URA 系为 SVY21（EPSG:3414，米制）**，**OSM 系为 WGS84（EPSG:4326，度）**——务必按文件逐个确认，见各章 `prj` 字段 |
| **计数口径** | SingStat 表格通常以 **"Total" 行为第一行**，随后为各分区行；工作表级统计值多为**人数 / 户数 / 单元数** |
| **舍入规则** | SingStat 对小于阈值的数据做**取整与抑制**处理，故最小值常为 10（或 5），不会出现 1~9 的真实计数 |
| **占位符** | `-` 表示"零或可忽略"；`na` 表示"不适用"；空字符串表示"未采集"（详见 [附录 C](#附录-c-字段类型与缺失值约定)） |
| **典型时间截面** | Census 类 = **2020 年人口普查**；respopagesex* = **2025 年 6 月**估计；GHS 类 = **2025 年住户调查**；TrafficFlow = **2025 年 11 月**逐小时；URA 图层 = **MP2019**；OSM = **2026 年 4 月抓取** |

---

# 1. 01_Boundary_TAZ — 交通分区与空间边界

> **作用**：整个 OD 建模的**空间骨架**。所有表格数据的行标签最终都要通过名称/编码关联到这里的几何。

## 目录结构

```text
01_Boundary_TAZ/
├─ MasterPlan2019PlanningAreaBoundaryNoSea.geojson
├─ MasterPlan2019SubzoneBoundaryNoSeaGEOJSON.geojson
└─ SINGAPORE.geojson
```

## 1.1 文件明细

### `MasterPlan2019PlanningAreaBoundaryNoSea.geojson`
| 项目 | 内容 |
|------|------|
| 来源 | URA Master Plan 2019（陆地版，剔除水域） |
| 几何 | Polygon |
| 要素数 | **55** |
| 坐标系 | WGS84 经纬度（lon, lat；`urn:ogc:def:crs:OGC:1.3:CRS84`） |
| 用途 | **Planning Area 级统计控制单元**；Census 表 92–117 的行维度参照此分区；就业/居住总量在此层对齐 |
| 文件大小 | ≈2.0 MB |

**字段说明**

| 字段 | 类型 | 说明 | 取值 |
|------|------|------|------|
| `OBJECTID` | int | 要素对象 ID | 1 … 55 |
| `PLN_AREA_N` | text | Planning Area 名称 | 例：`BEDOK`、`CLEMENTI`、`DOWNTOWN CORE` |
| `PLN_AREA_C` | text | Planning Area 两字母编码 | 例：`BD`、`CL`、`DT` |
| `CA_IND` | text | 是否中央活动区（Central Area） | `Y` / `N` |
| `REGION_N` | text | 所属规划区域名称 | `CENTRAL REGION` / `EAST REGION` / `NORTH REGION` / `NORTH-EAST REGION` / `WEST REGION` |
| `REGION_C` | text | 规划区域编码 | `CR` / `ER` / `NR` / `NER` / `WR` |
| `INC_CRC` | text | 增量校验码（增量更新用） | 16 位十六进制 |
| `FMEL_UPD_D` | text | 源库最后更新时刻 | `YYYYMMDDHHMMSS` |
| `SHAPE.AREA` | float | 面积（**SVY21 米²**，非经纬度度²） | 例 `21733966.97` |
| `SHAPE.LEN` | float | 周长（米） | 例 `21864.23` |

> ⚠️ **注意**：`SHAPE.AREA` / `SHAPE.LEN` 是**源库中按 SVY21 计算的米制值**，而几何坐标是经纬度。若要重算面积，必须先投影到 EPSG:3414。

### `MasterPlan2019SubzoneBoundaryNoSeaGEOJSON.geojson`
| 项目 | 内容 |
|------|------|
| 来源 | URA Master Plan 2019 |
| 几何 | Polygon |
| 要素数 | **332** |
| 坐标系 | WGS84 经纬度（CRS84） |
| 用途 | **基础 OD / TAZ 单元（最终计算层级）**；Table 88–91（居住）以此为最细粒度 |
| 文件大小 | ≈3.0 MB |

**字段说明**

| 字段 | 类型 | 说明 | 取值 |
|------|------|------|------|
| `OBJECTID` | int | 要素对象 ID | 675 … 1007（继承 URA 主键） |
| `SUBZONE_NO` | int | Subzone 分区序号 | 1 … 17 |
| `SUBZONE_N` | text | Subzone 名称 | 例：`DEPOT ROAD`、`CITY HALL`、`BEDOK SOUTH` |
| `SUBZONE_C` | text | Subzone 编码（**5 位，PA 前缀 + SZ + 序号**） | 例：`BMSZ12`（Bukit Merah 第 12 区）、`DTSZ02` |
| `CA_IND` | text | 是否中央活动区 | `Y` / `N` |
| `PLN_AREA_N` | text | 所属 Planning Area 名称 | 例：`BUKIT MERAH` |
| `PLN_AREA_C` | text | 所属 Planning Area 编码 | 例：`BM` |
| `REGION_N` / `REGION_C` | text | 所属规划区域 | 同 Planning Area 表 |
| `INC_CRC` / `FMEL_UPD_D` | text | 增量校验码 / 更新时间 | — |
| `SHAPE.AREA` / `SHAPE.LEN` | float | 面积（米²）/ 周长（米） | — |

### `SINGAPORE.geojson`
| 项目 | 内容 |
|------|------|
| 来源 | 第三方汇总（GEOID 编码，非 URA 官方分区） |
| 几何 | Polygon |
| 要素数 | **98** |
| 坐标系 | WGS84 经纬度（CRS84 显式声明） |
| 用途 | **粗粒度人口参考**：自带 `population` 字段，可直接做全国人口量的快速校验；**不建议作为 TAZ** |

**字段说明**

| 字段 | 类型 | 说明 | 取值 |
|------|------|------|------|
| `GEOID` | int | 要素序号 | 0 … 97 |
| `NAME_0` | text | 国家名 | 恒为 `Singapore` |
| `NAME_1` | text | 规划区域 | `CENTRAL REGION` 等 |
| `NAME_2` | text | 分区名（**与 URA Subzone 命名体系不一致**） | 例：`Swiss Club`、`Tampines West` |
| `population` | int | 该区人口 | 例 `82196`、`16942` |
| `area` | float | 面积（**经纬度度²，非米²**） | 例 `3.5005` |

> ⚠️ **口径警告**：本文件为 **98 个分区**，与 URA 的 **332 个 Subzone / 55 个 Planning Area** 均不匹配，且 `NAME_2` 命名体系独立。**只可用于量级校验，不可与 Census 表格直接 join**。

---

# 2. 02_Population_Residence — 居住人口与 HOME 端

> **作用**：OD 的 **Production / Origin 基础数据**，即每个 Subzone 的人口与潜在出行产生量 `P_i`。

## 目录结构

```text
02_Population_Residence/
├─ hsefa2025e.csv                              HDB/住宅 按建筑面积
├─ hsetod2025e.csv                             HDB/住宅 按住宅类型
├─ outputFile (2)__T1.csv                      Table 88  居住 PA/Subzone × 年龄 × 性别
├─ outputFile (2)__T2.csv                      Table 89  居住 PA/Subzone × 种族 × 性别
├─ outputFile (2)__T3.csv                      Table 90  居住 PA/Subzone × 住宅类型
├─ outputFile (2)__T4.csv                      Table 91  居住 PA/Subzone × 年龄 × 建筑面积
├─ respopagesex2025e.csv                       人口 按 PA/Subzone × 单岁年龄 × 性别
├─ respopagesexfa2025e__Total.csv              人口 按 PA/Subzone × 年龄组 × 建筑面积
├─ respopagesexfa2025e__Male.csv
├─ respopagesexfa2025e__Female.csv
├─ respopagesextod2025e__2025(Total).csv       人口 按 PA/Subzone × 年龄组 × 住宅类型
├─ respopagesextod2025e__2025(Male).csv
└─ respopagesextod2025e__2025(Female).csv
```

## 2.1 Census 2020 居住地分布（Table 88–91）

**来源**：SingStat Census of Population 2020 — Geographic Distribution
**空间粒度**：Planning Area（55）+ Subzone（332）
**行结构**：第 1 行 = `Total`（全国）；其后为 55 个 PA 行（标签形式 `<PA名> - Total`）+ 其下 332 个 Subzone 行 → **共 388 行**

### `outputFile (2)__T1.csv` — Table 88 · 规模 388×61
> Resident Population by Planning Area/Subzone of Residence, **Age Group and Sex**

| 列 | 说明 | 取值 |
|----|------|------|
| `Planning Area/Subzone of Residence` | **行主键** | `Total`；`<PA> - Total`；`<Subzone>` |
| `Total` | 总人口 | 10 … 4,044,210 |
| `Total_<年龄组>` | 总人口 × 19 个年龄组 | 组别：`0 - 4`、`5 - 9`、`10 - 14`、`15 - 19`、`20 - 24`、`25 - 29`、`30 - 34`、`35 - 39`、`40 - 44`、`45 - 49`、`50 - 54`、`55 - 59`、`60 - 64`、`65 - 69`、`70 - 74`、`75 - 79`、`80 - 84`、`85 - 89`、`90 & Over` |
| `Males_Total` / `Males_<年龄组>` | 男性同结构 | — |
| `Females_Total` / `Females_<年龄组>` | 女性同结构 | — |

### `outputFile (2)__T2.csv` — Table 89 · 规模 388×16
> … by Planning Area/Subzone of Residence, **Ethnic Group and Sex**

列 = `Total` + 4 个种族（`Chinese_`、`Malays_`、`Indians_`、`Others_`）× 3 个性别维度（`Total`/`Males`/`Females`）。
取值示例：全国华人 3,006,770；马来人 545,500；印度人 362,270。

### `outputFile (2)__T3.csv` — Table 90 · 规模 388×10
> … by Planning Area/Subzone of Residence and **Type of Dwelling**

列：`Total`；`HDB Dwellings_Total`、`HDB Dwellings_1- & 2- Room Flats1/`、`HDB Dwellings_3-Room Flats`、`HDB Dwellings_4-Room Flats`、`HDB Dwellings_5-Room & Executive Flats`；`Condominiums & Other Apartments`；`Landed Properties`；`Others`。

### `outputFile (2)__T4.csv` — Table 91 · 规模 388×121
> … by Planning Area/Subzone of Residence, **Age Group and Floor Area of Residence**

结构 = **6 个建筑面积档** × **20 个年龄维度列**（`Total` + 19 组）+ 总 `Total`：
`Total1/`、`≤ 60 sq m`、`> 60 - 80 sq m`、`> 80 - 100 sq m`、`> 100 - 120 sq m`、`> 120 sq m`
列名形如 `> 80 - 100 sq m_35 - 39`。**本表是 02 目录中信息量最大的表**，可同时支撑"人口 × 年龄 × 住房面积"三维下分。

> ⚠️ 列名后缀 `1/`、`2/`（如 `Total1/`、`Others1/`）是 **SingStat 脚注标记**（指向表下注释），不是数据内容，join 时需先剥离。

## 2.2 2025 年居民人口空间统计（DOS 估计）

### `respopagesex2025e.csv` · 规模 107,088×5
> 长表（long format）：每行一个「PA × Subzone × 单岁年龄 × 性别」组合

| 字段 | 类型 | 说明 | 取值 |
|------|------|------|------|
| `Planning Area` | text | 规划区（**已前向填充**） | `Total` + 55 PA |
| `Subzone` | text | 子区（**已前向填充**） | `Total` + 332 Subzone |
| `Age` | text | 年龄 | `Total`；单岁 `0`…`89`；`90 & Over` |
| `Sex` | text | 性别 | `Total` / `Males` / `Females` |
| `2025` | int | 人口数 | 10 … 4,204,520 |

### `respopagesexfa2025e__{Total,Male,Female}.csv` · 各 46,560×5
> 人口 × 建筑面积（Floor Area）

| 字段 | 取值 |
|------|------|
| `Planning Area` | `Total` + PA（前向填充） |
| `Subzone` | `Total` + Subzone（前向填充） |
| `Age Group` | `Total` + 19 个年龄组 |
| `Floor Area` | `Total*`、`≤ 60`、`> 60 - 80`、`> 80 - 100`、`> 100 - 120`、`> 120` |
| `2025` | 人口数（Total 表全国 4,161,310；Male 2,021,570；Female 2,139,750） |

### `respopagesextod2025e__2025({Total,Male,Female}).csv` · 各 69,840×5
> 人口 × 住宅类型（Type of Dwelling）

| 字段 | 取值 |
|------|------|
| `Planning Area` / `Subzone` | 同上（前向填充） |
| `Age Group` | `Total` + 19 组 |
| `Type of Dwelling` | `Total`、`Total HDB^`、`1- and 2-Room Flats*`、`3-Room Flats`、`4-Room Flats`、`5-Room and Executive Flats`、`Condominiums and Other Apartments`、`Landed Properties`、`Others` |
| `2025` | 人口数（Total 表全国 4,204,520） |

> ⚠️ 三份 `respopagesex*` 文件的**排序列不固定**（`Total` 在最前，其余按名称排序），并不完全按行政区顺序。若需空间 join，务必先用 `(PA, Subzone)` 建键，**不要依赖行序**。

## 2.3 住房库存（HDB 住房 2025 估计）

### `hsetod2025e.csv` · 规模 388×11
> Dwelling Units by Planning Area/Subzone and **Type of Dwelling**

| 字段 | 说明 | 值域 |
|------|------|------|
| `Planning Area` | 规划区 | `Total` + 55 PA |
| `Subzone` | 子区 | `Total` + 332 Subzone |
| `Total` | 住宅单元总数 | 110 … 1,623,240 |
| `HDB Dwellings_Total HDB` | HDB 单元小计 | 30 … 1,160,540 |
| `HDB Dwellings_1- and 2-Room Flats*` | 1–2 房式 | 20 … 120,160 |
| `HDB Dwellings_3-Room Flats` | 3 房式 | 20 … 253,800 |
| `HDB Dwellings_4-Room Flats` | 4 房式 | 40 … 460,900 |
| `HDB Dwellings_5-Room and Executive Flats` | 5 房式及执行公寓 | 10 … 325,670 |
| `Condominiums and Other Apartments` | 公寓及其他 | 20 … 375,610 |
| `Landed Properties` | 有地住宅 | 10 … 75,340 |
| `Others` | 其他 | 10 … 11,760 |

### `hsefa2025e.csv` · 规模 388×8
> Dwelling Units by Planning Area/Subzone and **Floor Area of Residence**

| 字段 | 值域 |
|------|------|
| `Planning Areas` | `Total` + 55 PA |
| `Subzones` | `Total` + 332 Subzone |
| `Total*` | 110 … 1,607,430 |
| `≤ 60 sqm` | 10 … 196,950 |
| `> 60 - 80 sqm` | 10 … 261,740 |
| `> 80 - 100 sqm` | 10 … 400,300 |
| `> 100 - 120 sqm` | 10 … 380,350 |
| `> 120 sqm` | 10 … 368,090 |

> ⚠️ **命名不一致**：`hsefa2025e` 用复数 `Planning Areas` / `Subzones`，`hsetod2025e` 用单数 `Planning Area` / `Subzone`。两表虽同源同类，但**列名不同名**，合并前必须统一。
> ⚠️ `hsefa2025e` 的列名含 `≤`、`>` 等**数学符号**，在部分 GIS/数据库工具中需转义。

## 2.4 后续开发参考

- **Synthetic Population 生成**：以 `outputFile (2)__T1`（年龄×性别）为边际分布，用 `respopagesexfa` / `respopagesextod` 做二维联合分布（IPF / 迭代比例拟合），再以 `hdb.csv`（09 目录）+ `URANoofDwellingUnits`（04 目录）下沉到建筑级 HOME 点。
- **行标签解析**：PA 行以 `" - Total"` 结尾，Subzone 行不含该后缀 → 可据此拆分层级。
- **数值下限 10** 说明计数已被取整，做人口合成时**不要假设低于 10 的真实值**。
---

# 3. 03_Workplace_Employment — 工作地与就业吸引

> **作用**：OD 的 **Attraction / Destination 基础数据**，对应 `A_j^work`。**是全部数据中第二重要的一组**。

## 目录结构

```text
03_Workplace_Employment/
├─ outputFile (3)__T1.csv   规划区域 × 行业 × 性别（无表号，Region 级）
├─ outputFile (3)__T2.csv   规划区域 × 职业 × 性别（无表号，Region 级）
├─ outputFile (3)__T3.csv   规划区域 × 年龄 × 性别（无表号，Region 级）
├─ outputFile (3)__T4.csv   Table 111  工作 PA × 年龄 × 性别
├─ outputFile (3)__T5.csv   Table 112  工作 PA × 最高学历 × 性别
├─ outputFile (3)__T6.csv   Table 113  工作 PA × 行业
├─ outputFile (3)__T7.csv   Table 114  工作 PA × 职业
├─ outputFile (3)__T8.csv   Table 115  工作 PA × 月收入
├─ outputFile (3)__T9.csv   Table 116  工作 PA × 通勤方式
├─ outputFile (3)__T10.csv  Table 117  工作 PA × 通勤时间
└─ outputFile (3)__T11.csv  Table 118  工作 PA × 通勤方式 × 居住区域  ★核心
```

**来源**：SingStat Census of Population 2020
**口径**：**Employed Residents Aged 15 Years and Over**（15 岁及以上在职居民）
**行标签约定（Region 级表）**：`Total`、`Central`、`East`、`North`、`North-East`、`West`、`Others2/`

## 3.1 Region 级（T1–T3）

### `outputFile (3)__T1.csv` · 规模 7×52 — Region × Industry × Sex
列结构 = `Total_/Males_/Females_` × 18 个行业维度：
`Total`、`Manufacturing`、`Construction`、`Services_Total`、`Services_Wholesale & Retail Trade`、`Services_Transportation & Storage`、`Services_Accommodation & Food Services`、`Services_Information & Communications`、`Services_Financial & Insurance Services`、`Services_Real Estate Services`、`Services_Professional Services`、`Services_Administrative & Support Services`、`Services_Public Administration & Education`、`Services_Health & Social Services`、`Services_Arts, Entertainment & Recreation`、`Services_Other Community, Social & Personal Services`、`Others1/`

### `outputFile (3)__T2.csv` · 规模 7×31 — Region × Occupation × Sex
列结构 = 3 个性别维度 × 10 个职业大类：
`Legislators, Senior Officials & Managers`、`Professionals`、`Associate Professionals & Technicians`、`Clerical Support Workers`、`Service & Sales Workers`、`Craftsmen & Related Trades Workers`、`Plant & Machine Operators & Assemblers`、`Cleaners, Labourers & Related Workers`、`Others1/`

### `outputFile (3)__T3.csv` · 规模 7×34 — Region × Age Group × Sex
年龄组：`Below 25`、`25 - 29`、`30 - 34`、`35 - 39`、`40 - 44`、`45 - 49`、`50 - 54`、`55 - 59`、`60 - 64`、`65 & Over`

## 3.2 Planning Area 级（T4–T11）

**行主键**：`Planning Area of Workplace`，**48 行**（`Total` + 44 个工作端 PA + 3 个特殊类）
> 44 个 PA 含：Ang Mo Kio, Bedok, Bishan, Boon Lay, Bukit Batok, Bukit Merah, Bukit Panjang, Bukit Timah, Changi, Choa Chu Kang, Clementi, Downtown Core, Geylang, Hougang, Jurong East, Jurong West, Kallang, Marine Parade, Museum, Newton, Novena, Orchard, Outram, Pasir Ris, Paya Lebar, Pioneer, Punggol, Queenstown, Rochor, Seletar, Sembawang, Sengkang, Serangoon, Singapore River, Southern Islands, Sungei Kadut, Tampines, Tanglin, Toa Payoh, Tuas, Western Islands, Western Water Catchment, Woodlands, Yishun
> 3 个特殊类：`Other Planning Areas or Outside Singapore`、`No Fixed Location for Work`、`Works from Home`

| 文件 | 表号 | 规模 | 列维度 |
|------|------|------|--------|
| `T4` | 111 | 48×34 | `Total/Males/Females` × 10 个年龄组（`Below 25` … `65 & Over`） |
| `T5` | 112 | 48×28 | 最高学历（`No Qualification`、`Primary`、`Lower Secondary`、`Secondary`、`Post-Secondary (Non-Tertiary)`、`Polytechnic Diploma`、`Professional Qualification and Other Diploma`、`University`）× `Total/Males/Females` |
| `T6` | 113 | 48×18 | 行业（同 T1 的 18 维，列名**不带**前缀） |
| `T7` | 114 | 48×11 | 职业（同 T2 的 10 维） |
| `T8` | 115 | 48×16 | 月收入：`Below $1,000`、`$1,000 - $1,999`、…、`$11,000 - $11,999`、`$12,000 - $14,999`、`$15,000 & Over` |
| `T9` | 116 | 48×13 | 通勤方式 11 类：`Public Bus Only`、`Rail (MRT/LRT) Only`、`Rail (MRT/LRT) & Public Bus Only`、`Combination of Rail (MRT/LRT) and/or Public Bus, with Other Modes`、`Taxi/Private Hire Car Only`、`Car Only`、`Private Chartered Bus/Van Only`、`Lorry/Pickup Only`、`Motorcycle/Scooter Only`、`Others`、`No Transport Required` |
| `T10` | 117 | **47×7** | 通勤时间：`Up to 15 mins`、`16 - 30 mins`、`31 - 45 mins`、`46 - 60 mins`、`More than 60 mins` |
| `T11` | **118** | 48×31 | ★ **三维交叉**：列 = `Total_Mode of Transport_*` + 5 个居住区域 × `Mode of Transport_*` 4 类 |

### ★ `outputFile (3)__T11.csv`（Table 118）—— 本项目最有价值的一张表

**结构**：行 = 工作地 Planning Area（48），列 = **居住区域（6 档）× 通勤方式（4 类）**

- 通勤方式 4 类：`Combinations of Rail (MRT/LRT) or Public Bus`、`Car or Taxi/Private Hire Car Only`、`Other Modes`、`No Transport Required`
- 居住区域 6 档：`Total`、`Central Region`、`East Region`、`North Region`、`North-East Region`、`West Region`

**它实际给出**：`ResidenceRegion × WorkplacePA × TravelMode` 三维 OD 结构。
**价值**：虽不是完整的 `ResidencePA × WorkplacePA`，更不是 `ResidenceSubzone × WorkplaceSubzone`，但**已可作为粗粒度 OD 结构约束**（对 `T_ij^prior` 施加宏观约束、校准重力模型的距离衰减与方式划分）。
**取值范围**：全国口径 `Total` 行 = 2,177,456；单元格最小 6。

> ⚠️ **T11 有 48 行但 T10 只有 47 行**——因为通勤时间表**不含 `Works from Home` 行**（居家工作者无通勤时间）。若做 join，需**取交集并对缺失类单独处理**。

## 3.3 后续开发参考

- **就业吸引权重**：`T6`（行业结构）用于给土地利用类型赋就业权重；`T7`（职业）用于区分通勤弹性。
- **吸附总量控制**：以 `T4` 的 PA 级就业总量 `E_p` 作为控制数，再经 ACRA + 土地利用下沉到 Subzone / 建筑。
- **通勤方式校准**：`T9` 提供工作端方式划分，`T11` 提供"居住区域 → 工作 PA"的方式结构，二者结合可反推 `P(mode | residence region, workplace PA)`。
- **⚠️ 空间单元不一致**：03 目录的 PA 集合（44 个）与 02 目录的 PA 集合（55 个）**并不相同**——居住端含更多住宅型 PA（如 `Bukit Panjang`、`Sengkang` 等在职工作端被合并为 `Other Planning Areas`）。**做 OD 时必须先对齐：取 02 与 03 的 PA 交集，并把 `Other Planning Areas or Outside Singapore` 作为"域外"虚拟吸引区单独建节点。**

---

# 4. 04_LandUse_Building — 土地利用与建筑

> **作用**：把 Census 的 **Planning Area 级就业人口进一步下沉到 Subzone / 建筑 / 活动点**，是**就业空间下分的核心依据**（不是普通背景底图）。

## 目录结构

```text
04_LandUse_Building/
├─ HDBExistingBuilding.geojson               HDB 存量建筑轮廓
├─ MasterPlan2019Buildinglayer.geojson        MP2019 建筑轮廓
├─ MasterPlan2019LandUselayer.geojson         MP2019 土地利用分区 ★
└─ URANoofDwellingUnits.geojson               URA 住宅单元点（含 DU 数）
```

## 4.1 `MasterPlan2019LandUselayer.geojson` ★
| 项目 | 内容 |
|------|------|
| 来源 | URA Master Plan 2019 Land Use Layer |
| 几何 | Polygon |
| 要素数 | **113,214** |
| 坐标系 | WGS84 经纬度（CRS84） |
| 大小 | ≈166 MB |
| **用途** | **就业/活动吸引权重的核心依据**。按 `LU_DESC` 给不同用途赋不同就业吸引权重 |

**字段说明**

| 字段 | 类型 | 说明 | 取值 |
|------|------|------|------|
| `OBJECTID` | int | 要素 ID | — |
| `LU_DESC` | text | **土地利用类型描述** | 见下表 33 类 |
| `LU_TEXT` | text | 用地附加文本标注 | 常为空串 `" "` |
| `GPR` | text | 总容积率（Gross Plot Ratio） | 数字串或 `EVA`（待评估） |
| `WHI_Q_MX` | float | White 用地数量上限 | 多为 `null` |
| `GPR_B_MN` | float | GPR 下限 | 多为 `null` |
| `INC_CRC` / `FMEL_UPD_D` | text | 增量校验码 / 更新时间 | — |
| `SHAPE.AREA` / `SHAPE.LEN` | float | 面积（米²）/ 周长（米） | — |

**`LU_DESC` 全部 33 类取值（含样本频次，按 113,214 条统计）**

| 用地类型 | 频次 | 用地类型 | 频次 |
|---------|------|---------|------|
| `RESIDENTIAL` | 79,121 | `BUSINESS PARK` | 200 |
| `ROAD` | 6,623 | `HEALTH & MEDICAL CARE` | 195 |
| `COMMERCIAL` | 5,983 | `WHITE` | 163 |
| `BUSINESS 2` | 5,976 | `SPECIAL USE` | 61 |
| `RESIDENTIAL WITH COMMERCIAL AT 1ST STOREY` | 2,821 | `MASS RAPID TRANSIT` | 49 |
| `BUSINESS 1` | 1,505 | `PORT / AIRPORT` | 49 |
| `PARK` | 1,425 | `BUSINESS 1 - WHITE` | 45 |
| `UTILITY` | 1,067 | `BEACH AREA` | 35 |
| `WATERBODY` | 1,015 | `CEMETERY` | 17 |
| `RESIDENTIAL / INSTITUTION` | 960 | `LIGHT RAPID TRANSIT` | 15 |
| `COMMERCIAL & RESIDENTIAL` | 905 | `BUSINESS 2 - WHITE` | 14 |
| `OPEN SPACE` | 762 | `BUSINESS PARK - WHITE` | 12 |
| `RESERVE SITE` | 665 | | |
| `PLACE OF WORSHIP` | 645 | | |
| `CIVIC & COMMUNITY INSTITUTION` | 629 | | |
| `EDUCATIONAL INSTITUTION` | 608 | | |
| `COMMERCIAL / INSTITUTION` | 533 | | |
| `TRANSPORT FACILITIES` | 349 | | |
| `HOTEL` | 285 | | |
| `SPORTS & RECREATION` | 241 | | |
| `AGRICULTURE` | 239 | | |

> 💡 **建议的就业吸引权重**（可按此初始设定，后续用 T6 行业结构标定）：
> `COMMERCIAL` / `BUSINESS 1` / `BUSINESS 2` / `BUSINESS PARK` > `HOTEL` / `CIVIC & COMMUNITY INSTITUTION` / `HEALTH & MEDICAL CARE` / `EDUCATIONAL INSTITUTION` > `COMMERCIAL & RESIDENTIAL` / `RESIDENTIAL WITH COMMERCIAL AT 1ST STOREY` > `RESIDENTIAL` > `PARK` / `WATERBODY` / `ROAD`（≈0）

## 4.2 `MasterPlan2019Buildinglayer.geojson`
| 项目 | 内容 |
|------|------|
| 来源 | URA MP2019 Building Layer |
| 几何 | Polygon / MultiPolygon |
| 要素数 | **14,355** |
| 坐标系 | WGS84 经纬度（CRS84） |
| 大小 | ≈50 MB |
| 用途 | **建筑级分配底图**（就业/人口下沉到建筑） |

**字段说明**

| 字段 | 类型 | 说明 | 取值 |
|------|------|------|------|
| `OBJECTID` | int | 要素 ID | — |
| `BLDG_TYPE` | text | 建筑类型 | **抽样 20,000 条中全为 `null`**——该字段实际不可用 |
| `INC_CRC` / `FMEL_UPD_D` | text | 增量校验码 / 更新时间 | — |
| `SHAPE.AREA` / `SHAPE.LEN` | float | 面积（米²）/ 周长（米） | — |

> ⚠️ **`BLDG_TYPE` 全空**，且**无楼层数/高度字段**。若需要建筑体量，应改从 `07_RoadNetwork/osm-polygon.shp` 的 `other_tags`（含 `"building:levels"=>"12"`、`"height"=>"70"`）或 `osm-polygon_expanded.dbf` 提取。

## 4.3 `HDBExistingBuilding.geojson`
| 项目 | 内容 |
|------|------|
| 来源 | HDB / OneMap 存量建筑 |
| 几何 | Polygon |
| 要素数 | **13,404** |
| 坐标系 | WGS84 经纬度（CRS84） |
| 大小 | ≈54 MB |
| 用途 | HDB 住宅建筑的精确空间位置与街区定位 |

**字段说明**

| 字段 | 类型 | 说明 | 取值 |
|------|------|------|------|
| `OBJECTID` | int | 要素 ID | 例 `931094` |
| `BLK_NO` | text | 楼号 | 例 `41A`、`2E` |
| `ST_COD` | text | 街道/统计代码 | 例 `MAD03B` |
| `ENTITYID` | int | 实体 ID | — |
| `POSTAL_COD` | text | 邮编（**文本型，前导 0 保留**） | 例 `143041` |
| `INC_CRC` / `FMEL_UPD_D` | text | 增量校验码 / 更新时间 | — |
| `SHAPE.AREA` / `SHAPE.LEN` | float | 面积（米²）/ 周长（米） | — |

## 4.4 `URANoofDwellingUnits.geojson`
| 项目 | 内容 |
|------|------|
| 来源 | URA 住宅单元数图层（No. of Dwelling Units） |
| 几何 | **Point** |
| 要素数 | **83,541** |
| 坐标系 | **坐标字段为 SVY21 米制**（`X_ADDR`/`Y_ADDR`），几何为 WGS84 经纬度 |
| 大小 | ≈37 MB |
| 用途 | **HOME 点下沉的关键数据**：每个住宅楼点自带居住单元数 `DU`，可直接把 Subzone 人口按 `DU` 比例分配到点 |

**字段说明**

| 字段 | 类型 | 说明 | 取值 |
|------|------|------|------|
| `OBJECTID` | int | 要素 ID | — |
| `POSTALCODE` | text | 邮编 | 例 `466993` |
| `BLK_NO` | text | 楼号 | 例 `2E`、`45` |
| `PROJ_NAME` | text | 项目名 | 可为 `null`，例 `TAI HWAN GARDEN` |
| `PROP_TYPE` | text | **物业类型** | `Landed`(73,043)、`Non-Landed`(9,898)、`EC`(603) |
| `X_ADDR` / `Y_ADDR` | float | **SVY21 坐标（米）** | 例 `39741.74` / `33364.74` |
| `DU` | int | **该点住宅单元数（Dwelling Units）** | 通常 ≥1，Landed 多为 1 |
| `INC_CRC` / `FMEL_UPD_D` | text | 增量校验码 / 更新时间 | 例 `20250311155836` |

## 4.5 后续开发参考

- **WORK 侧下分链**：`E_p`（来自 03 目录 PA 级就业）→ 按 `LU_DESC` 权重 × `SHAPE.AREA` 分配到 Subzone → 建筑。
- **HOME 侧下分链**：`Population_Subzone`（02 目录）→ 按 `DU` 比例分配到 `URANoofDwellingUnits` 的点，或按 `HDBExistingBuilding` 的建筑 → 生成合成人口点。
- **面积字段单位陷阱**：`SHAPE.AREA` 是**米²**（SVY21 计算），而几何是经纬度；若用 GeoPandas 的 `.area` 会得到**度²**，两者相差约 10¹⁰ 量级，务必统一。

---

# 5. 05_POI_Enterprise — POI 与企业

> **作用**：解决 Census 的关键盲区——"某 PA 有多少就业人口"是已知的，但"这些岗位在哪些建筑、哪个 Subzone"未知。用 **POI + ACRA** 做空间下分。

## 目录结构

```text
05_POI_Enterprise/
├─ ACRA/
│  ├─ ACRAInformationonCorporateEntitiesA.csv   （UEN 首字符 A）
│  ├─ ACRAInformationonCorporateEntitiesB.csv
│  ├─ ACRAInformationonCorporateEntitiesE.csv
│  ├─ ACRAInformationonCorporateEntitiesH.csv
│  ├─ ACRAInformationonCorporateEntitiesI.csv
│  ├─ ACRAInformationonCorporateEntitiesM.csv
│  ├─ ACRAInformationonCorporateEntitiesN.csv
│  ├─ ACRAInformationonCorporateEntitiesO.csv
│  ├─ ACRAInformationonCorporateEntitiesS.csv   （最大，230,152 行）
│  ├─ ACRAInformationonCorporateEntitiesU.csv
│  ├─ ACRAInformationonCorporateEntitiesW.csv
│  └─ ACRAInformationonCorporateEntitiesX.csv
├─ HealthFacilities/
│  ├─ Health Facilities (Dental Clinics and Pharmacies).csv
│  ├─ Health Facilities (Primary Care, Dental Clinics and Pharmacies).csv
│  ├─ Health Facilities and Beds in Inpatient Facilities.csv
│  └─ Health Facilities and Beds in Inpatient Facilities (Public Not-for-Profit Private).csv
├─ HawkerCentresGEOJSON.geojson
├─ NParksParksandNatureReserves.geojson
├─ PreSchoolsLocation.geojson
├─ TouristAttractions.geojson
└─ poi.csv
```

## 5.1 ACRA 企业注册数据（12 个 CSV）

| 项目 | 内容 |
|------|------|
| 来源 | ACRA（Accounting and Corporate Regulatory Authority）企业注册信息 |
| 分片依据 | **按 UEN 首字符分片**（A/B/E/H/I/M/N/O/S/U/W/X，**缺 C/D/F/G/J/K/L/P/Q/R/T/V/Y/Z 等字母片**，说明为**部分导出**） |
| 字段数 | 每个文件 **53 列**（完全一致） |
| 坐标系 | 无几何；通过 `block + street_name + postal_code` 落点 |
| **总记录数** | **≈ 1,049,322 条** |
| 用途 | ★ **就业空间位置 + 行业结构**（不是直接统计就业人数） |

**各分片记录数**

| 文件 | 行数 | 文件 | 行数 |
|------|------|------|------|
| `A` | 171,522 | `M` | 122,035 |
| `B` | 93,281 | `N` | 59,533 |
| `E` | 85,151 | `O` | 40,571 |
| `H` | 93,135 | `S` | 230,152 |
| `I` | 59,895 | `U` | 24,129 |
| `W` | 57,055 | `X` | 12,863 |

**字段说明（53 列，全部为文本或数值）**

| 字段 | 说明 | 取值 / 备注 |
|------|------|-------------|
| `uen` | **统一实体编号（主键）** | 例 `00021800J` |
| `issuance_agency_id` | 签发机构 | 恒为 `ACRA` |
| `entity_name` | 企业名称 | 例 `SIN HUP HO` |
| `entity_type_description` | **实体类型** | 5 类：`Local Company`、`Sole Proprietorship/ Partnership`、`Limited Liability Partnership`、`Foreign Company Branch`、`Limited Partnership` |
| `business_constitution_description` | 商业组织形式 | `na`、`Sole-Proprietor`、`Partnership` |
| `company_type_description` | 公司类型 | 6 类：`na`、`Exempt Private Company Limited by Shares`、`Private Company Limited by Shares`、`Public Company Limited by Guarantee`、`Public Company Limited by Shares`、`Unlimited Exempt Private Company` |
| `paf_constitution_description` | 合伙/独资章程 | 抽样中恒为 `na` |
| `entity_status_description` | **经营状态** | 21 类，主要为 `Live Company`、`Struck Off`、`Cancelled`、`Terminated`、`Live`、`Cancelled (Non-Renewal)`、`Ceased Registration`、`Dissolved - Members Voluntary Winding Up`、`Gazetted To Be Struck Off`、`Converted To LLP`、`In Liquidation - Creditors voluntary winding up`、`Dissolved - Compulsory Winding Up (Insolvency)` 等 |
| `registration_incorporation_date` | 注册/成立日期 | `YYYY-MM-DD`，例 `1974-09-13` |
| `uen_issue_date` | UEN 签发日期 | `YYYY-MM-DD` |
| `address_type` | 地址类型 | 抽样恒为 `LOCAL` |
| `block` | 门牌号 | 数值 1 … 9012 |
| `street_name` | 街道名 | 文本 |
| `level_no` | 楼层 | 0 … 445（**可为 `na`**） |
| `unit_no` | 单元号 | 0 … 75,915（**可为 `na`**，偶见负值 `-3`） |
| `building_name` | 建筑名 | 文本或 `na` |
| `postal_code` | **邮编** | 数值 1 … 829,333（⚠️ **前导 0 已丢失**，作为文本才能复原） |
| `other_address_line1` / `other_address_line2` | 其他地址行 | 多为 `na` |
| `account_due_date` / `annual_return_date` | 账目/年报到期日 | 多为 `na` |
| `primary_ssic_code` | **主要行业代码（SSIC 2020）** | 例 `47539`、`47714`、`43210` |
| `primary_ssic_description` | 主要行业描述 | 文本（部分分片中出现**数值污染**，如 `47214`，为导出缺陷） |
| `primary_user_described_activity` | 用户自述主营 | 多为 `na` |
| `secondary_ssic_code` / `secondary_ssic_description` / `secondary_user_described_activity` | 次要行业三件套 | 结构同上 |
| `no_of_officers` | **企业高管/负责人人数** | 0 … 489；分布以 `1` 最多（4,531/12,863 例），⚠️ **不是员工人数，不可用作就业量** |
| `former_entity_name1` … `former_entity_name15` | 曾用名（最多 15 个） | 多为 `na` |
| `uen_of_audit_firm1`…`5` / `name_of_audit_firm1`…`5` | 审计事务所（最多 5 家） | 多为 `na` |

### ★ ACRA 的正确用法（重要）

> **误区**：`Employment_e = no_of_officers` ❌
> **正确**：ACRA 的价值是「**企业空间位置 + 行业结构**」，就业量必须用 Census 总量控制后按权重分摊：

```
E_e = E_p × w_e / Σ_{e∈p} w_e ,
其中  w_e = w_SSIC × w_entity × w_building × w_officer
```

其中 `E_p` 为 03 目录中该 PA 的就业总量（Table 111），权重项可按需取用/组合。

**建模实际使用的字段（建议优先级）**：`uen` → `entity_name` → `entity_type_description` → `entity_status_description` → `block`/`street_name`/`building_name`/`postal_code` → `primary_ssic_code`/`primary_ssic_description` → `secondary_ssic_*` → `no_of_officers`
> **重要性排序**：**地址 > SSIC 行业 > 企业类型 > no_of_officers**

## 5.2 `poi.csv` · 规模 8,672×125

| 项目 | 内容 |
|------|------|
| 来源 | Google Places / OneMap 风格 POI 抓取 |
| 字段数 | **125 列** = 1 序号列 + 10 基础列 + 100+ 类别标签列 + 7 空间列 |
| 用途 | 活动吸引（Activity Attraction）、就业辅助下分、目的地生成 |

**基础字段**

| 字段 | 类型 | 说明 | 取值 |
|------|------|------|------|
| *（无名首列）* | int | 行序号 | 0 … 8,671 |
| `place_id` | text | POI 唯一 ID | — |
| `name` | text | 地点名称 | — |
| `lat` / `lng` | float | 纬度 / 经度（WGS84） | lat 1.2457 … 1.4616；lng 103.6146 … 104.0325 |
| `rating` | float | 评分 | **0.0 … 5.0** |
| `user_ratings_total` | int | 评价总数 | 0 … 19,146 |
| `price_level` | float | 价格档位 | **1 … 4**（**约 97% 为空**） |
| `formatted_address` | text | 格式化地址 | — |
| `global_code` / `compound_code` | text | Plus Code 全局码/复合码 | — |
| `planning_area` | text | 规划区名称 | — |

**类别标签列（约 100 列）**

| 说明 | 内容 |
|------|------|
| 类型 | **布尔型文本** `True` / `False`（one-hot 稀疏标签，**不是 Y/N**） |
| 已确认标签 | `brand`（抽样全空）、`establishment`、`point_of_interest`（≈100% True）、`store`、`food`、`health`、`restaurant`、`hospital`、`lodging`、`finance`、`cafe`、`convenience_store`、`clothing_store`、`atm`、`shopping_mall`、`grocery_or_supermarket`、`home_goods_store`、`school`、`bakery`、`beauty_salon`、`transit_station`、`place_of_worship`、`pharmacy`、`meal_takeaway`、`furniture_store`、`tourist_attraction`、`secondary_school`、`supermarket`、`doctor`、`shoe_store`、`dentist`、`jewelry_store`、`church`、`bank`、`primary_school`、`electronics_store`、`gym`、`spa`、`car_repair`、`pet_store`、`bus_station`、`university`、`park`、`general_contractor`、`subway_station`、`real_estate_agency`、`florist`、`hair_care`、`department_store`、`hardware_store`、`car_dealer`、`veterinary_care`、`travel_agency`、`bicycle_store`、`book_store`、`laundry`、`plumber`、`meal_delivery`、`lawyer`、`parking`、`mosque`、`physiotherapist`、`art_gallery`、`insurance_agency`、`bar`、`museum`、`storage`、`movie_theater`、`moving_company`、`liquor_store`、`gas_station`、`electrician`、`car_rental`、`locksmith`、`car_wash`、`post_office`、`embassy`、`night_club`、`fire_station`、`amusement_park`、`library`、`hindu_temple`、`local_government_office`、`funeral_home`、`bowling_alley`、`cemetery`、`aquarium`、`roofing_contractor`、`stadium`、`painter`、`courthouse`、`drugstore`、`campground`、`accounting`、`airport`、`zoo`、`casino`、`synagogue`、`premise`、`taxi_stand`、`police`、`light_rail_station`、`city_hall`、`train_station`、`natural_feature`、`subpremise`（约 100 列） |

**空间归属字段（末尾 7 列）**

| 字段 | 类型 | 说明 | 取值 |
|------|------|------|------|
| `SUBZONE_NO` | int | Subzone 序号 | 1 … 17 |
| `SUBZONE_N` | text | Subzone 名称 | — |
| `SUBZONE_C` | text | Subzone 编码（5 位） | 例 `DTSZ02` |
| `PLN_AREA_N` | text | Planning Area 名称 | — |
| `PLN_AREA_C` | text | Planning Area 编码 | — |
| `REGION_N` | text | 规划区域名称 | `CENTRAL REGION` 等 |
| `REGION_C` | text | 规划区域编码 | `CR` / `ER` / `NR` / `NER` / `WR` |

> ✅ **关键优势**：`poi.csv` **已自带 `planning_area` 与完整 Subzone/PA/Region 归属**，无需再做空间连接即可与 Census 表 join。

## 5.3 专题 POI（GeoJSON）

| 文件 | 几何 | 要素数 | 关键字段 | 用途 |
|------|------|--------|---------|------|
| `HawkerCentresGEOJSON.geojson` | Point | **129** | `OBJECTID`、`ADDRESSBUILDINGNAME`、`ADDRESSPOSTALCODE`、`ADDRESSSTREETNAME`、`NAME`、`STATUS`、`NUMBER_OF_COOKED_FOOD_STALLS`、`DESCRIPTION`、`AWARDED_DATE`、`IMPLEMENTATION_DATE`、`INFO_ON_CO_LOCATORS`、`ADDRESS_MYENV`、`EST_ORIGINAL_COMPLETION_DATE`、`HUP_COMPLETION_DATE`、`PHOTOURL`、`ADDRESSBLOCKHOUSENUMBER`、`LANDXADDRESSPOINT`、`LANDYADDRESSPOINT`、`INC_CRC`、`FMEL_UPD_D` | 小贩中心作为**午餐时段活动吸引**；`STATUS` 取值 `Existing`(103)、`Existing (new)`(16)、`Under Construction`(6)、`Existing (replacement)`(3)、`Interim Centre`(1) |
| `NParksParksandNatureReserves.geojson` | MultiPolygon | **459** | `OBJECTID_1`、`L_CODE`、`NAME`、`N_RESERVE`（0/1 是否自然保护区）、`INC_CRC`、`FMEL_UPD_D`、`SHAPE_1.AREA`、`SHAPE_1.LEN` | 休闲出行目的地 |
| `PreSchoolsLocation.geojson` | Point | **2,290** | `Name`、`Description` | ⚠️ **字段内嵌 HTML 表格**：`Description` 形如 `<center><table>…<th>CENTRE_NAME</th><td>…</td>…`。**必须先解析 HTML 才能取到 `CENTRE_NAME` / `CENTRE_CODE` / `INC_CRC` / `FMEL_UPD_D`**。用于就学出行（家长接送）分析 |
| `TouristAttractions.geojson` | Point | **109** | `OBJECTID_1`、`PAGETITLE`、`URL_PATH`、`IMAGE_PATH`、`IMAGE_ALT_TEXT`、`PHOTOCREDITS`、`LASTMODIFIED`、`LATITUDE`、`LONGTITUDE`、`ADDRESS`、`POSTALCODE`、`OVERVIEW`、`EXTERNAL_LINK`、`META_DESCRIPTION`、`OPENING_HOURS`、`INC_CRC`、`FMEL_UPD_D` | 旅游活动吸引 |

> ⚠️ `TouristAttractions.geojson` 的经度字段拼写为 **`LONGTITUDE`（多了一个 T）**，不是 `LONGITUDE`；且坐标以**独立字段**给出（`LATITUDE`/`LONGTITUDE`），与几何可能不完全一致。

## 5.4 医疗机构统计（HealthFacilities 4 个 CSV）

**来源**：MOH 年度统计（**时间序列，非空间数据**）；年份覆盖 **2009 – 2022**。**无几何坐标**——仅作设施供给参考，不宜直接用于空间下分。

| 文件 | 规模 | 字段 | 说明 |
|------|------|------|------|
| `Health Facilities (Dental Clinics and Pharmacies).csv` | 84×4 | `year`、`institution_type`{`Pharmacies`,`Dental Clinics`}、`sector`{`Total`,`Public`,`Private`}、`no_of_facilities` | 设施数 50 … 1,204 |
| `Health Facilities (Primary Care, Dental Clinics and Pharmacies).csv` | 112×5 | + `facility_type_b`{`Polyclinics`、`Public Pharmacies`、`Private Pharmacies`、`School Dental Clinics`、`Private Dental Clinics`、`Polyclinic Dental Clinics`、`General Practioner Clinics`、`Hospital/Institution Dental Clinic`} | 设施数 5 … 2,481 |
| `Health Facilities and Beds in Inpatient Facilities.csv` | 70×5 | `year`、`institution_type`{`Hospital`,`Residential Long-Term`}、`facility_type_a`{`Acute`,`Nursing Homes`,`Inpatient Hospices`,`Community Hospitals`,`Psychiatric Hospitals`,`Inpatient Hospice Palliative Care Service`}、`no_of_facilities`、`no_beds` | 设施 1 … 83；床位 123 … 18,029 |
| `Health Facilities and Beds in Inpatient Facilities (Public Not-for-Profit Private).csv` | 210×6 | + `public_private`{`Public`,`Private`,`Not-for-Profit`} | 设施 0 … 34；床位 0 … 9,820 |

> ⚠️ 表中 `General Practioner Clinics` 为**源数据拼写错误**（应为 Practitioner），清洗时注意保留原值或统一修正。

## 5.5 后续开发参考

- **统一 POI 中间层**：建议把 `poi.csv` + 4 个专题 GeoJSON 合并为 `POI_Cleaned.geojson`，字段统一为 `poi_id, category, sub_category, lon, lat, planning_area, subzone, weight`。
- **不建议全量入库**：专题 POI 应作为**加权项**而非独立控制数，避免重复计数。
- **ACRA 落点策略**：优先用 `postal_code`（最可靠）→ 失败则 `building_name` → 再失败用 `street_name` 匹配 `HDBExistingBuilding` / `osm-polygon`。
---

# 6. 06_Census_TravelBehavior — 出行行为与方式选择

> **作用**：提供方式选择 `P(mode|…)` 与通勤时间分布 `P(travelTime|…)`，用于生成 MATSim person 与校准方式划分。**本目录是文件数最多的一组（57 个 CSV）**。

## 目录结构

```text
06_Census_TravelBehavior/
├─ outputFile (4)__T1.csv … __T21.csv     Census 2020 居住端（PA 粒度），共 21 个
├─ outputFile (5)__T1.csv … __T17.csv     Census 2020 出行方式（全国口径），共 17 个
└─ outputFile__T1.csv    … __T19.csv      GHS 2025 出行方式（全国口径），共 19 个
```

> **三组数据的年份与口径完全不同**（见下表），**不可直接拼表**。

| 组 | 来源 | 年份 | 空间粒度 | 用途定位 |
|----|------|------|---------|---------|
| `outputFile (4)` | Census 2020 | 2020 | **Planning Area（30 + Total + Others = 32 行）** | 空间结构与基础控制 |
| `outputFile (5)` | Census 2020 | 2020 | **全国（无地理维度）** | 交叉表最完整，方式选择参数 |
| `outputFile` | GHS 2025 | 2025 | **全国（无地理维度）** | **行为参数更新**（不与 2020 拼表） |

## 6.1 `outputFile (4)` — Census 2020 居住端（Planning Area 粒度）

**行主键**：`Planning Area of Residence`，**32 行** = `Total` + 30 个 PA + `Others`
> 30 个 PA：Ang Mo Kio, Bedok, Bishan, Bukit Batok, Bukit Merah, Bukit Panjang, Bukit Timah, Choa Chu Kang, Clementi, Downtown Core, Geylang, Hougang, Jurong East, Jurong West, Kallang, Marine Parade, Novena, Outram, Pasir Ris, Punggol, Queenstown, River Valley, Sembawang, Sengkang, Serangoon, Tampines, Tanglin, Toa Payoh, Woodlands, Yishun

| 文件 | 表号 | 规模 | 行维度 | 列维度（取值） |
|------|------|------|--------|---------------|
| `T1` | — | 6×52 | `Planning Region of Residence`（6 行：`Total`+5 Region） | 行业 × 性别（同 03 目录 T1 的 18 行业 × 3 性别） |
| `T2` | — | 6×31 | 同上 | 职业 × 性别（10 职业 × 3 性别） |
| `T3` | 92 | 32×29 | PA | 语言（家中最常/次常用语）：`English_*`、`Mandarin_*`、`Chinese Dialects_*`、`Malay_*`、`Indian Languages - Tamil_*`、`Indian Languages - Other Indian Languages_*`、`Other Languages_*` |
| `T4` | 93 | 32×9 | PA | 就学阶段：`Pre-Primary`、`Primary`、`Secondary`、`Post-Secondary (Non-Tertiary)`、`Polytechnic Diploma`、`Professional Qualification and Other Diploma`、`University` |
| `T5` | 94 | 32×13 | PA | **就学通勤方式**：11 类 + `Total` + `Others` |
| `T6` | 95 | 32×7 | PA | **就学通勤时间**：`Up to 15 mins`、`16 - 30 mins`、`31 - 45 mins`、`46 - 60 mins`、`More than 60 mins` |
| `T7` | 96 | 32×16 | PA | 婚姻状况 × 性别：`Single/Married/Widowed/Divorced/Separated` × `Total/Males/Females` |
| `T8` | 97 | 32×16 | PA | 劳动力状态 × 性别：`Labour Force - Total/Employed/Unemployed`、`Outside the Labour Force` |
| `T9` | 98 | 32×17 | PA | 语言识字：`Not Literate`、`Literate`、`One Language Only_*`、`Two Languages Only_*` |
| `T10` | 99 | 32×11 | PA | 宗教 |
| `T11` | 100 | 32×10 | PA | **最高学历**：`No Qualification`、`Primary`、`Lower Secondary`、`Secondary`、`Post-Secondary (Non-Tertiary)`、`Polytechnic Diploma`、`Professional Qualification and Other Diploma`、`University` |
| `T12` | 101 | 32×18 | PA | **行业**（18 维，同 03 T6） |
| `T13` | 102 | 32×11 | PA | **职业**（10 维） |
| `T14` | 103 | 32×16 | PA | **月收入**（15 档，同 03 T8） |
| `T15` | 104 | 32×13 | PA | ★ **居住端 → 通勤方式**（11 类）→ `P(mode \| residence)` |
| `T16` | 105 | 32×7 | PA | ★ **居住端 → 通勤时间**（5 档）→ `P(travelTime \| residence)` |
| `T17` | 106 | 32×10 | PA | 住户 × 住宅类型 |
| `T18` | 107 | 32×5 | PA | 住户 × 住房权属（Tenancy） |
| `T19` | 108 | 32×9 | PA | 住户 × 家庭结构（Household Structure） |
| `T20` | 109 | 32×10 | PA | 住户 × 家庭规模（Household Size） |
| `T21` | 110 | 32×21 | PA | 住户 × 家庭月收入 |

## 6.2 `outputFile (5)` — Census 2020 出行方式（全国口径）

**行主键**：**出行方式（12 行）** 或 **行业/职业（17/10 行）**
出行方式 12 类：`Total`、`Public Bus Only`、`Rail (MRT/LRT) Only`、`Rail (MRT/LRT) & Public Bus Only`、`Combination of Rail (MRT/LRT) and/or Public Bus, with Other Modes`、`Taxi/Private Hire Car Only`、`Car Only`、`Private Chartered Bus/Van Only`、`Lorry/Pickup Only`、`Motorcycle/Scooter Only`、`Others`、`No Transport Required`

| 文件 | 表号 | 规模 | 行维度 | 交叉维度 |
|------|------|------|--------|---------|
| `T1` | 119 | 12×16 | 就学方式 | × 年龄组 × 性别 |
| `T2` | 120 | 12×25 | 就学方式 | × 就学阶段 × 性别 |
| `T3` | 121 | 12×61 | 就学方式 | × 家庭月收入 × 性别 |
| `T4` | 122 | 12×28 | 就学方式 | × 住宅类型 × 性别 |
| `T5` | 123 | 12×19 | 就学方式 | × 就学通勤时间 × 性别 |
| `T6` | 124 | 6×25 | 就学通勤时间 | × 就学阶段 × 性别 |
| `T7` | 125 | 12×16 | 通勤方式 | × 年龄组 × 性别 |
| `T8` | 126 | 12×28 | 通勤方式 | × 最高学历 × 性别 |
| `T9` | 127 | 12×16 | 通勤方式 | × 就业身份 × 性别（`Employers`/`Own Account Workers`/`Employees`/`Contributing Family Workers`） |
| `T10` | 128 | 12×52 | 通勤方式 | × 行业 × 性别 |
| `T11` | 129 | 12×31 | 通勤方式 | × 职业 × 性别 |
| `T12` | 130 | 12×46 | 通勤方式 | × 个人月收入 × 性别 |
| `T13` | 131 | 12×58 | 通勤方式 | × 家庭月收入 × 性别 |
| `T14` | 132 | 12×28 | 通勤方式 | × 住宅类型 × 性别 |
| `T15` | 133 | 12×19 | 通勤方式 | × 通勤时间 × 性别 |
| `T16` | 134 | **17×19** | **行业**（17 行） | × 通勤时间 × 性别 |
| `T17` | 135 | **10×19** | **职业**（10 行） | × 通勤时间 × 性别 |

> 可直接构建：`P(mode | age, income, industry, travelTime, …)`

## 6.3 `outputFile` — GHS 2025 出行方式（全国口径）

**来源**：General Household Survey 2025（发布时间 2026-06-30）
**行主键**：就学方式（11 类，**不含 `No Transport Required`**）/ 通勤方式（11 类）/ 行业（17）/ 职业（10）

| 文件 | 表号 | 规模 | 行维度 | 交叉维度 |
|------|------|------|--------|---------|
| `T1` | 141 | 11×16 | 就学方式 | × 年龄组 × 性别 |
| `T2` | 142 | 11×25 | 就学方式 | × 就学阶段 × 性别 |
| `T3` | 143 | 11×70 | 就学方式 | × 家庭**就业**收入 × 性别 |
| `T4` | 144 | 11×67 | 就学方式 | × 家庭**市场**收入 × 性别 |
| `T5` | 145 | 11×25 | 就学方式 | × 住宅类型 × 性别 |
| `T6` | 146 | 11×19 | 就学方式 | × 就学通勤时间 × 性别 |
| `T7` | 147 | 6×25 | 就学通勤时间 | × 就学阶段 × 性别 |
| `T8` | 148 | 12×19 | 通勤方式 | × 年龄组 × 性别 |
| `T9` | 149 | 12×22 | 通勤方式 | × 学历 × 性别 |
| `T10` | 150 | 12×16 | 通勤方式 | × 就业身份 × 性别 |
| `T11` | 151 | 12×52 | 通勤方式 | × 行业 × 性别 |
| `T12` | 152 | 12×31 | 通勤方式 | × 职业 × 性别 |
| `T13` | 153 | 12×49 | 通勤方式 | × 个人**就业**收入 × 性别 |
| `T14` | 154 | 12×67 | 通勤方式 | × 家庭**就业**收入 × 性别 |
| `T15` | 155 | 12×67 | 通勤方式 | × 家庭**市场**收入 × 性别 |
| `T16` | 156 | 12×25 | 通勤方式 | × 住宅类型 × 性别 |
| `T17` | 157 | 12×19 | 通勤方式 | × 通勤时间 × 性别 |
| `T18` | 158 | 12×19 | 行业 | × 通勤时间 × 性别 |
| `T19` | 159 | 12×19 | 职业 | × 通勤时间 × 性别 |

> ⚠️ **GHS 2025 与 Census 2020 的收入档位不同**：Census 2020 最高档为 `$15,000 & Over`（部分表 `$20,000 & Over`），GHS 2025 细化为 `$20,000 - $24,999`、`$25,000 - $29,999`、`$30,000 - $34,999`、`$35,000 & Over`。**跨年对比必须先重分箱（rebin）**。

## 6.4 后续开发参考

- **方式选择模型**：用 `outputFile (4)__T15` 提供居住地维度约束，用 `outputFile (5)__T7–T15` 提供个体属性维度的条件概率，二者乘积归一化 → `P(mode)`。
- **通勤时间分布**：`outputFile (4)__T16`（PA 级）+ `outputFile (5)__T15`（属性级），用于校准 MATSim 出行时长分布。
- **GHS 2025 的角色**：**只做参数更新与敏感性分析**，不做空间计算（无地理维度）。

---

# 7. 07_RoadNetwork — 交通网络与阻抗

> **作用**：重力模型 / NeuroGravity 与 MATSim 的**共同输入**，用于计算阻抗 `c_ij`。

## 目录结构

```text
07_RoadNetwork/
├─ RoadSectionLine_Mar2026/         LTA 官方路段（SVY21）
│  └─ RoadSectionLine.shp / .dbf / .shx / .prj / .cpg
├─ osm-lines.shp +侧车               OSM 道路中心线（含 highway 分级）
├─ osm-lines_expanded.shp +侧车      OSM 道路 + other_tags 展开（47 字段）
├─ osm-multiline.shp +侧车           OSM 多线要素（公交/轨道线路）
├─ osm-multiline_expanded.shp +侧车
├─ osm-points.shp +侧车              OSM 点要素
├─ osm-points_expanded.shp +侧车
├─ osm-polygon.shp +侧车             OSM 面要素（建筑/土地利用）
├─ osm-polygon_expanded.shp +侧车
├─ relations.csv                     OSM relation 索引
├─ relations.qmd
└─ OSM_属性表结构说明.md              expanded 文件的完整字段文档（4,217 行）
```

## 7.1 `RoadSectionLine.shp` — LTA 官方路段
| 项目 | 内容 |
|------|------|
| 来源 | LTA DataMall（2026 年 3 月版） |
| 几何 | **POLYLINE** |
| 记录数 | **15,329** |
| 坐标系 | **SVY21 / EPSG:3414（米制）** — `PROJCS["SVY21", … Transverse_Mercator]` |
| bbox | x 3,248 … 50,044；y 22,755 … 50,136（米） |
| 用途 | **道路等级（`RD_CATG__1`）**，用于给 OSM 路网赋速度/通行能力 |

**字段说明**

| 字段 | DBF 类型 | 说明 | 取值 |
|------|---------|------|------|
| `RD_CD` | C(6) | 道路代码 | **全空（15,329 条中 0 个非空）** |
| `RD_CATG_NA` | C(20) | 道路类别名称 | **全空** |
| `RD_CATG__1` | C(254) | ★ **道路等级**（DBF 10 字符截断后重命名） | `Category 1`、`Category 2`、`Category 3`、`Category 4`、`Category 5`、`No Category` |
| `RD_CD_DESC` | C(254) | 街道名称 | 1,896 个不同值，例 `JOO CHIAT TERRACE`、`BEDOK GARDEN` |

> ⚠️ **DBF 字段名被截断为 10 字符**：`RD_CATG__1` 实际源于 `RD_CATG_NAME`（或类似），`RD_CATG_NA` 与之同源但内容为空。**建模只需 `RD_CATG__1`。**
> ⚠️ 坐标系是 **SVY21 而非 WGS84**！与 OSM 数据叠加前必须投影转换。

## 7.2 OSM 主文件（未展开 `other_tags`）

| 文件 | 几何 | 记录数 | 坐标系 | 字段数 |
|------|------|--------|--------|--------|
| `osm-lines.shp` | POLYLINE | **275,996** | WGS84（度） | 10 |
| `osm-multiline.shp` | POLYLINE | **1,002** | WGS84（度） | 4 |
| `osm-points.shp` | POINT | **110,907** | WGS84（度） | 9 |
| `osm-polygon.shp` | POLYGON | **155,074** | WGS84（度） | 27 |

### `osm-lines.shp` 字段（道路中心线，**MATSim 路网首选底图**）

| 字段 | 类型 | 说明 | 取值 / 值域 |
|------|------|------|-------------|
| `osm_id` | text | OSM 要素 ID | 4,386,520 … 41,566,024 |
| `name` | text | 道路名称（**约 19% 为空**） | 例 `Orchard Road`、`Hougang Avenue 1` |
| `highway` | text | ★ **道路等级标签** | 21 类：`construction`、`cycleway`、`footway`、`living_street`、`motorway`、`motorway_link`、`path`、`pedestrian`、`primary`、`primary_link`、`residential`、`secondary`、`secondary_link`、`service`、`steps`、`tertiary`、`tertiary_link`、`track`、`trunk`、`trunk_link`、`unclassified` |
| `waterway` | text | 水系（**99.6% 为空**） | `canal`、`drain`、`weir` |
| `aerialway` | text | 索道（近乎全空） | `gondola` |
| `barrier` | text | 障碍物 | 抽样全空 |
| `man_made` | text | 人造物 | 抽样全空 |
| `railway` | text | 铁路（**99.3% 为空**） | `monorail`、`subway` |
| `z_order` | N(10) | 图层叠加次序 | **-45 … 39** |
| `other_tags` | text | ★ **其余 OSM 标签（`=>` 分隔的准 JSON）** | 2,258 个不同值，例 `"lanes"=>"5","maxspeed"=>"50","oneway"=>"yes","surface"=>"asphalt"` |

> ★ **`other_tags` 是速度建模的关键**：内含 `maxspeed`（限速）、`lanes`（车道数）、`oneway`（单行）、`surface`（路面）、`turn:lanes`（转向车道）等。**需要先解析此字段才能构建可用的通行速度。**

### `osm-points.shp` 关键字段
`osm_id`、`name`（**约 51% 为空**）、`highway`（12 类：`bus_stop`、`crossing`、`elevator`、`mini_roundabout`、`motorway_junction`、`speed_camera`、`stop`、`toll_gantry`、`traffic_signals`、`traffic_signals_emergency`、`turning_circle`、`turning_loop`）、`barrier`、`ref`、`address`、`is_in`、`place`、`man_made`、`other_tags`

### `osm-polygon.shp` 关键字段
`osm_id`、`osm_way_id`、`name`、`type`（`boundary` / `multipolygon`）、`aeroway`、`amenity`（34 类）、`admin_leve`（5/6/7/11）、`barrier`、`boundary`、`building`（41 类）、`craft`、`geological`、`historic`、`land_area`、`landuse`（23 类）、`leisure`（18 类）、`man_made`（11 类）、`military`、`natural`（13 类）、`office`、`place`、`shop`、`sport`、`tourism`、`other_tags`
> 💡 `other_tags` 中含 `"building:levels"=>"12"`、`"height"=>"70"`、`"building:use"=>"residential"` → **是补充 04 目录建筑信息缺失（`BLDG_TYPE` 全空）的唯一途径**。

## 7.3 OSM 展开版（`*_expanded.shp`）

> 由 `other_tags` 展开为独立字段的中间产物，**文件体积极大**（合计约 6.5 GB），**默认不进入建模流程**，仅在需要具体标签时按需读取。

| 文件 | 字段数 | 记录数 | 大小（.dbf） |
|------|--------|--------|-------------|
| `osm-lines_expanded.shp` | **47** | 275,996 | **3.1 GB** |
| `osm-multiline_expanded.shp` | **29** | 1,002 | 7.1 MB |
| `osm-points_expanded.shp` | **61** | 110,907 | **1.7 GB** |
| `osm-polygon_expanded.shp` | **43** | 155,074 | **1.6 GB** |

**字段清单（完整文档见同目录 `OSM_属性表结构说明.md`）**

- `osm-lines_expanded`（47）：`osm_id`, `name`, `highway`, `waterway`, `aerialway`, `barrier`, `man_made`, `railway`, `z_order`, `lanes`, `surface`, `oneway`, `maxspeed`, `lanes:forw`, `lanes:back`, `service`, `name:zh`, `turn:lanes`(×3), `access`, `lit`, `sidewalk`, `name:en`, `covered`, `bicycle`, `layer`, `foot`, `sidewalk:l`, `sidewalk:r`, `footway`, `building:p`, `building:l`, `sidewalk:b`, `bridge`, `name:ms`, `name:ta`, `tunnel`, `constructi`, `maxheight`, `horse`, `smoothness`, `lanes:bus`, `lanes:bus:`, `busway:lef`, `crossing`, `ref`
- `osm-multiline_expanded`（29）：`osm_id`, `name`, `type`, `network`, `from`, `direction`, `fee`, `network:wi`, `network:sh`, `name:en`, `operator`, `route`, `ref`, `public_tra`, `distance`, `operator:w`, `colour`, `duration`, `descriptio`, `to`, `roundtrip`, `name:zh`, `wikidata`, `opening_ho`, `wikipedia`, `from:ref`, `name:ms` 等
- `osm-points_expanded`（61 字段）、`osm-polygon_expanded`（43 字段）—— 详见该文档

> ⚠️ 上述 DBF 字段名同样**被截断为 10 字符**（如 `lanes:forw` ← `lanes:forward`），文档中保留了截断后的原名。

## 7.4 `relations.csv` · 规模 113,941×4
| 字段 | 类型 | 说明 | 取值 |
|------|------|------|------|
| `osm_id` | text | relation ID | 例 `274002` |
| `name` | text | relation 名称 | — |
| `type` | text | relation 类型 | 例 `associatedStreet` |
| `other_tags` | text | 其他标签 | 多为空 |

## 7.5 后续开发参考

- **阻抗构造**：**不要用欧氏距离 `d_ij`**，应构造最短出行时间 `c_ij = ShortestTravelTime(i, j)`；重力模型采用 `f(c_ij) = exp(-λ·c_ij)`。
- **速度赋值建议链**：`highway`（OSM 等级）→ `maxspeed`（`other_tags` / expanded）→ 缺失时回退到 `RD_CATG__1`（LTA Category）分级默认速度。
- **坐标系统一**：建议**全流程统一到 SVY21（EPSG:3414）**做距离/时间计算（米制），仅在可视化时转 WGS84。LTA 路段（`RoadSectionLine`）与 `BusStop` / `RapidTransitSystemStation` 已是 SVY21，可直接与 MATSim 网络叠加。
- **MATSim 网络生成**：以 `osm-lines.shp` 为底图过滤 `highway ∈ {motorway, trunk, primary, secondary, tertiary, residential, service, unclassified, *_link}`（剔除 `footway`、`steps`、`cycleway`、`path`、`pedestrian`），再按上表赋速度/车道数，导出 `network.xml.gz`。
  > ⚠️ **`network.xml.gz` 目前尚未生成**，目录中不存在该文件。

---

# 8. 08_TrafficCount — 实测交通流量

> **作用**：决定 OD 最终是 "Synthetic OD" 还是 **"Traffic-count-calibrated OD"**。**本目录是校准闭环的关键。**

## 目录结构

```text
08_TrafficCount/
├─ TrafficFlow.json          ⚠️ LTA API 元数据封装（非数据本体）
├─ TrafficFlow_Data.json     ★ 逐小时实测流量（15.5 MB）
├─ TrafficFlow_Links.shp / .dbf / .shx / .prj
```

## 8.1 `TrafficFlow_Data.json` ★

| 项目 | 内容 |
|------|------|
| 来源 | LTA DataMall — Traffic Flow（Historical） |
| 大小 | 15.53 MB |
| `LastUpdatedDate` | **2026-03-18** |
| 记录数 | **≈75,899** 条 |
| 结构 | JSON 对象：`{"LastUpdatedDate": "...", "Value": [ {...}, ... ]}` |

**字段说明**

| 字段 | 类型 | 说明 | 取值 |
|------|------|------|------|
| `LinkID` | text | **路段 ID（与 `TrafficFlow_Links.shp` 的 `LinkID` 一致）** | 例 `143599` |
| `Date` | text | 日期（**DD/MM/YYYY**） | 例 `01/11/2025`（**2025 年 11 月**） |
| `HourOfDate` | text | 小时（0–23，**字符串**） | 例 `7` |
| `Volume` | text | **小时流量（辆，字符串）** | 例 `523`、`309`、`894` |
| `StartLon` / `StartLat` | text | 起点经纬度（WGS84） | 例 `103.7672285` / `1.43001094` |
| `EndLon` / `EndLat` | text | 终点经纬度 | 例 `103.766757` / `1.42921249` |
| `RoadName` | text | 道路名称 | 例 `WOODLANDS AVENUE 3` |
| `RoadCat` | text | 道路等级 | `CATA` / `CATB` / `CATC` / `CATD` / `CATE` / `SLIP_ROAD` |

> ⚠️ **所有数值均为字符串类型**，读取后必须显式转数值。
> ⚠️ 同一条 `LinkID` 在不同 `Date`/`HourOfDate` 上重复出现（长表结构），典型为"7 天 × 若干小时"的重复观测 → **校准时建议取多工作日中位数**，而非单日值。

**建议的校准中间产物** `TrafficFlow_AMPeak.csv`：`LinkID, hour, median_volume, geometry, MATSim_link_id`
- 第一阶段建议只使用**工作日 07:00–10:00**
- 流量取**多个工作日的 `Median(Volume)`**

## 8.2 `TrafficFlow_Links.shp` · 记录 1,278

| 项目 | 内容 |
|------|------|
| 几何 | **POLYLINE** |
| 记录数 | **1,278** |
| 坐标系 | **WGS84（度）** |
| bbox | lon 103.6355 … 103.9817；lat 1.2656 … 1.4388 |
| 用途 | 提供 `LinkID` 的**几何线形**，用于与 MATSim 网络做**空间匹配** |

**字段说明**

| 字段 | 类型 | 说明 | 取值 |
|------|------|------|------|
| `LinkID` | C(20) | ★ 路段 ID（**与流量 JSON 关联的外键**） | 4,048 … 219,831 |
| `RoadName` | C(100) | 道路名称 | 160 个不同值，例 `WOODLANDS ROAD` |
| `RoadCat` | C(20) | 道路等级 | `CATA`、`CATB`、`CATC`、`CATD`、`CATE`、`SLIP_ROAD` |
| `StartLon` / `StartLat` | N(50) | 起点经纬度 | — |
| `EndLon` / `EndLat` | N(50) | 终点经纬度 | — |

> 💡 **流量观测覆盖 1,278 条 link（全部为 CATA–E 干道 + 匝道）**，而 OSM 路网有 27 万条线。校准时只需在这 1,278 条上匹配，**无需全校准**。

## 8.3 `TrafficFlow.json` ⚠️ 使用注意

| 项目 | 内容 |
|------|------|
| 大小 | 4 KB |
| 实际内容 | LTA DataMall 的 `$metadata` 风格封装：`{"odata.metadata": "...", "value": [{"Link": "https://dmprod-datasets.s3...X-Amz-Signature=..."}]}` |

> ⚠️ **这不是流量数据**，而是**指向 S3 预签名下载链接的一层元数据包装**，且其中的 `X-Amz-Expires=300`（**5 分钟即失效**，采样时的时间戳为 `20260504T024646Z`）。
> **结论：应忽略此文件，实际数据用 `TrafficFlow_Data.json`。**

## 8.4 后续开发参考

**校准目标函数**（双约束 + 流量最小二乘）：

```
min_T [ Σ_a w_a · (q_a_sim − q_a_obs)² + λ · D(T, T_prior) ]  ⇒  T_ij_final
```

- `q_a^obs` ← 本目录 `TrafficFlow_Data.json`（按 link 取工作日高峰中位数）
- `q_a^sim` ← MATSim 分配结果
- `T^prior` ← 重力模型先验 OD
- `w_a` ← 可按 `RoadCat` 分级赋权（如 `CATA` 权重高于 `SLIP_ROAD`）

---

# 9. 09_Auxiliary — 辅助数据

> **作用**：非 OD 必需项，但显著提升模型质量（尤其 HDB 用于 HOME 点下沉、Transit 用于多方式扩展）。

## 目录结构

```text
09_Auxiliary/
├─ POI_Background/
│  └─ hdb.csv                                     HDB 楼栋明细（★HOME 点下沉）
└─ Transit/
   ├─ BusStopLocation/BusStop.shp +侧车            公交站
   ├─ RapidTransitSystemStation/…shp +侧车         轨道交通车站
   ├─ LTAMRTStationExitGEOJSON.geojson            MRT 站出入口
   ├─ bus_line.csv                                 公交线路—站点序列表
   ├─ bus_vol.csv                                  ★公交站点逐小时客流
   └─ mrt.csv                                      MRT 车站清单
```

## 9.1 `POI_Background/hdb.csv` · 规模 12,442×37 ★

| 项目 | 内容 |
|------|------|
| 来源 | HDB 楼栋数据（含 OneMap 空间归属） |
| 用途 | ★ **HOME 端建筑级下沉的核心数据**：楼栋级住宅单元数与户型构成 |

**字段说明**

| 字段 | 类型 | 说明 | 取值 / 值域 |
|------|------|------|-------------|
| *（无名首列）* | int | 行序号 | 0 … 12,441 |
| `blk_no` | text | 楼号 | 例 `1`、`213` |
| `street` | text | 街道名 | 例 `BEACH RD`、`BEDOK STH AVE 1` |
| `max_floor_lvl` | int | 最高楼层 | **1 … 50** |
| `year_completed` | int | 建成年份 | **1949 … 2021** |
| `residential` | text | 是否住宅 | `Y` / `N` |
| `commercial` | text | 是否商用 | `Y` / `N` |
| `market_hawker` | text | 是否含市场/小贩中心 | `Y` / `N` |
| `miscellaneous` | text | 是否杂项用途 | `Y` / `N` |
| `multistorey_carpark` | text | 是否多层停车楼 | `Y` / `N` |
| `precinct_pavilion` | text | 是否组屋区亭 | `Y` / `N` |
| `bldg_contract_town` | text | 建屋局承包镇区代号 | 例 `KWN`、`BD` |
| `total_dwelling_units` | int | **住宅单元总数** | 0 … 539 |
| `1room_sold` | int | 1 房式（售出） | 0 … 0（该批数据无 1 房） |
| `2room_sold` / `3room_sold` / `4room_sold` / `5room_sold` / `exec_sold` | int | 2/3/4/5 房式、执行公寓（售出） | 0 … 528 |
| `multigen_sold` | int | 多代同堂户型 | 0 … 48 |
| `studio_apartment_sold` | int | Studio Apartment | 0 … 164 |
| `1room_rental` / `2room_rental` / `3room_rental` / `other_room_rental` | int | 租赁房型 | 0 … 386 |
| `lat` / `lng` | float | 纬度 / 经度（WGS84） | lat 1.2715 … 1.4548；lng 103.7082 … 103.9883 |
| `building` | text | 建筑名 | 例 `RAFFLES HOTEL`、`NIL` |
| `addr` | text | 完整地址 | 例 `1 BEACH ROAD RAFFLES HOTEL SINGAPORE 189673` |
| `postal` | int | 邮编 | 80001 … 825195（⚠️ **数值型，前导 0 丢失**） |
| `SUBZONE_NO` | int | Subzone 序号 | 1 … 16 |
| `SUBZONE_N` / `SUBZONE_C` | text | Subzone 名称 / 编码 | 例 `CITY HALL` / `DTSZ02` |
| `PLN_AREA_N` / `PLN_AREA_C` | text | Planning Area 名称 / 编码 | 例 `DOWNTOWN CORE` / `DT` |
| `REGION_N` / `REGION_C` | text | 规划区域名称 / 编码 | 例 `CENTRAL REGION` / `CR` |

## 9.2 公交与轨道设施

### `Transit/BusStopLocation/BusStop.shp` · 记录 5,177
| 字段 | 类型 | 说明 | 取值 |
|------|------|------|------|
| `BUS_STOP_N` | C(65) | **公交站编号（5 位，文本）** | 例 `65059`、`01239`（**前导 0 有意义，勿转数值**） |
| `LOC_DESC` | C(254) | 站点位置描述 | 例 `BLK 120`、`SULTAN PLAZA` |
| 几何 | POINT | 站点点位 | — |
| 坐标系 | **SVY21（EPSG:3414，米制）** | bbox x 3,970 … 48,286；y 26,482 … 52,984 | — |

### `Transit/RapidTransitSystemStation/RapidTransitSystemStation.shp` · 记录 231
| 字段 | 类型 | 说明 | 取值 |
|------|------|------|------|
| `TYP_CD` | N(5) | 类型代码 | 恒为 `0`（无区分度） |
| `STN_NAM` | C(250) | 站名 | **全空（231 条全为 null）** |
| `ATTACHEMEN` | C(100) | 附属设施压缩包名 | 51 个值，例 `NE14_HGN STN.zip`（180 条为空） |
| `SHAPE_AREA` | F(19) | 面积（米²） | 228.41 … 311,932.90 |
| `SHAPE_LEN` | F(19) | 周长（米） | 68.30 … 4,316.56 |
| `TYP_CD_DES` | C(254) | ★ **线路制式** | `MRT` / `LRT` |
| `STN_NAM_DE` | C(254) | ★ **站名（完整）** | 204 个不同值，例 `HOUGANG MRT STATION`、`CORAL EDGE LRT STATION` |
| 坐标系 | SVY21（EPSG:3414，米制） | — | — |

> ⚠️ **站名在 `STN_NAM` 全空，实际要用 `STN_NAM_DE`**；制式用 `TYP_CD_DES`（不是 `TYP_CD`）。

### `Transit/LTAMRTStationExitGEOJSON.geojson` · 要素 597
| 字段 | 类型 | 说明 | 取值 |
|------|------|------|------|
| `OBJECTID` | int | 要素 ID | 例 `18062` |
| `STATION_NA` | text | 车站名称 | 例 `TANJONG PAGAR MRT STATION` |
| `EXIT_CODE` | text | 出入口编号 | 例 `Exit G` |
| `INC_CRC` / `FMEL_UPD_D` | text | 增量校验码 / 更新时间 | 例 `20251202172807` |
| 几何 | Point | 出入口点位（WGS84） | — |

### `Transit/mrt.csv` · 规模 247×14
| 字段 | 类型 | 说明 | 取值 |
|------|------|------|------|
| *（无名首列）* | int | 行序号 | 0 … 246 |
| `name` | text | 车站名称 | 例 `EUNOS MRT STATION` |
| `stop_id` | text | 站点代码 | 例 `EW7`、`EW25` |
| `line` | text | ★ **线路代码** | `BP`、`CC`、`CE`、`CG`、`DT`、`EW`、`NE`、`NS`、`PE`、`PW`、`SE`、`SW`、`TE` |
| `no` | int | 站序 | 0 … 165 |
| `lng` / `lat` | float | 经度 / 纬度（WGS84） | lng 103.6369 … 103.9884；lat 1.2655 … 1.4491 |
| `SUBZONE_NO` / `SUBZONE_N` / `SUBZONE_C` | — | Subzone 归属 | — |
| `PLN_AREA_N` / `PLN_AREA_C` | — | Planning Area 归属 | — |
| `REGION_N` / `REGION_C` | — | 规划区域 | `EAST REGION`/`ER`、`WEST REGION`/`WR`、`NORTH REGION`/`NR`、`CENTRAL REGION`/`CR`、`NORTH-EAST REGION`/`NER` |

### `Transit/bus_line.csv` · 规模 26,317×13
| 字段 | 类型 | 说明 | 取值 |
|------|------|------|------|
| *（无名首列）* | int | 行序号 | — |
| `line` | text | 公交线路号 | 例 `10` … `136` |
| `operator` | text | 运营商 | 例 `SBST`、`SMRT` |
| `direction` | int | 方向 | `1` / `2` |
| `sequence` | int | 站点在路线中的顺序 | 1 … 82 |
| `stop_id` | int | 站点编号（**与 `BusStop.shp` 的 `BUS_STOP_N` 关联**） | 例 `75009` |
| `distance` | float | 距起点的累计里程（km） | 0 … 39.9 |
| `WD_FirstBus` / `WD_LastBus` | int | 工作日首/末班（**HHMM 整型**） | 15 … 2400 |
| `SAT_FirstBus` / `SAT_LastBus` | int | 周六首/末班 | 15 … 2400 |
| `SUN_FirstBus` / `SUN_LastBus` | int | 周日首/末班 | 15 … 2400 |

> ⚠️ 时刻以 **HHMM 整数**表示（`2353` = 23:53），非 `HH:MM`；末班最大 `2400` = 24:00。

### `Transit/bus_vol.csv` · 规模 580,972×7 ★
| 字段 | 类型 | 说明 | 取值 |
|------|------|------|------|
| *（无名首列）* | int | 行序号 | — |
| `day` | text | 日类型 | **`WD`（工作日）/ `H`（假日）** |
| `hour` | int | 小时 | 0 … 23 |
| `stop_id` | int | 站点编号 | 1211 … 99139 |
| `in` | int | **上车人数** | 0 … 16,971 |
| `out` | int | **下车人数** | 0 … 19,584 |
| `month` | int | 月份 | 恒为 `202107`（**2021 年 7 月**） |

> 💡 **这是唯一的逐小时公交客流上/下车数据**，可用于校准公交方式分担与验证 Transit 分配；但**时间截面是 2021 年 7 月（疫情期）**，与 2025 年流量数据存在年份错配，使用时需说明。

## 9.3 后续开发参考

- **第一阶段（car-only OD）**：Transit 四件套**可不进入计算**，只需 `hdb.csv`。
- **多方式 MATSim 扩展时**：用 `bus_line.csv` 构建公交线网、`BusStop.shp` + `RapidTransitSystemStation.shp` 建站点、`bus_vol.csv` 做客流标定、`mrt.csv` + `LTAMRTStationExitGEOJSON` 建轨道供给。
- **⚠️ 关联键注意**：`bus_line.csv.stop_id`（整型）↔ `BusStop.shp.BUS_STOP_N`（**文本，保留前导 0**），join 时需统一为 **5 位零填充字符串**。
- **⚠️ `hdb.csv.postal` 为数值型**，前导 0 已丢失；若需与 ACRA 的 `postal_code`（同为数值）或 `poi.csv` 的地址比对，建议统一转为 **6 位零填充字符串**。

---

# 10. 10_Documentation — 说明文档

## 目录结构

```text
10_Documentation/
└─ FINAL_DATA_DICTIONARY.md      本文件
```

| 文件 | 说明 |
|------|------|
| `FINAL_DATA_DICTIONARY.md` | **本数据字典**：记录数据名、来源、年份、空间尺度、主要字段、模型用途 |
| （待建）配套文档 | 建议后续补充：`METHODS.md`（预处理方法）、`README.md`（快速上手） |

> 建议按需求继续补充的文档：**预处理方法说明**（投影、清洗、下分算法）、**最终输出清单**（每次运行的产物与版本）、**复现实验步骤**。
> 另注：`07_RoadNetwork/OSM_属性表结构说明.md` 已存在于 07 目录（4,217 行），是 OSM expanded 文件的权威字段文档，可与本文件交叉引用。
---

# 附录 A. 统一空间单元字典

## A.1 三级空间体系

```
Subzone  →  Planning Area  →  Planning Region
```

| 层级 | 数量 | 角色 | 主要数据 |
|------|------|------|---------|
| **Subzone** | **332** | **基础 OD / TAZ 单元（最终计算层级）** | Table 88–91（居住）、`hdb.csv`、`poi.csv`、`URANoofDwellingUnits` |
| **Planning Area** | 居住端 **55** / 工作端 **44** / Census 旅行表 **30** | **Census 统计控制单元** | Table 92–117、ACRA 落点、土地利用下分 |
| **Planning Region** | **5**（+ `Others`） | **Table 118 粗粒度 OD 约束单元** | Table 118、Region 级 T1–T3、GHS 2025 |

## A.2 规划区域（Planning Region）编码对照

| `REGION_N` | `REGION_C` | 中文 |
|-----------|-----------|------|
| `CENTRAL REGION` | `CR` | 中区 |
| `EAST REGION` | `ER` | 东区 |
| `NORTH REGION` | `NR` | 北区 |
| `NORTH-EAST REGION` | `NER` | 东北区 |
| `WEST REGION` | `WR` | 西区 |

## A.3 Subzone 编码规则

`SUBZONE_C` 为 **5 位**：`<PA 2 字母编码><SZ><2 位序号>`
例：`DTSZ02` = Downtown Core（`DT`）第 **02** 号 Subzone；`BMSZ12` = Bukit Merah（`BM`）第 12 号。
`SUBZONE_NO` 为 **PA 内部**序号（1–17），**不是全国唯一键**。

## A.4 ⚠️ 分区数量不一致对照表（关键）

| 数据集 | PA 数 | Subzone 数 | 说明 |
|--------|-------|-----------|------|
| `MasterPlan2019PlanningAreaBoundaryNoSea` | **55** | — | URA 官方 PA |
| `MasterPlan2019SubzoneBoundaryNoSeaGEOJSON` | — | **332** | URA 官方 Subzone |
| `outputFile (2)__T1–T4`（居住 Census） | 55（含 Total） | 332 | 与 URA 一致 ✅ |
| `hsefa2025e` / `hsetod2025e` | 55 | 332 | 与 URA 一致 ✅ |
| `outputFile (4)__T*`（居住旅行 Census） | **30** + Others | — | **少于 55**，住宅型 PA 被合并 |
| `outputFile (3)__T4–T11`（工作 Census） | **44** + 3 特殊类 | — | **与居住端不同集** |
| `SINGAPORE.geojson` | — | **98** | **独立命名体系，不可 join** |
| `poi.csv` 空间归属 | — | — | 引用 URA 体系 ✅ |

> **建模必须做的事**：
> 1. `居住 PA(55) ∩ 工作 PA(44) ∩ 旅行表 PA(30)` → 取交集作为建模核心区；
> 2. 把 `Other Planning Areas or Outside Singapore`、`No Fixed Location for Work`、`Works from Home`、`Others` 作为**特殊虚拟区**单独建节点，**不要丢弃**（否则总量不守恒）；
> 3. 所有 join **以名称/编码为准，禁止依赖行序**。

---

# 附录 B. CSV 转换规则（xlsx → csv）

本目录所有 `.xlsx` 已转换为 CSV，规则如下（便于复现与论文方法章节引用）：

| # | 规则 | 具体做法 |
|---|------|---------|
| 1 | **多子表拆分** | 每个**非空** sheet 生成一个独立 CSV。单 sheet 文件 → `原名.csv`；多 sheet 文件 → `原名__<sheet名>.csv` |
| 2 | **合并单元格展开** | 先按合并区域把值填充到区域内所有单元格，再取表头。例 `hsetod` 的 `D3:H3`（`HDB Dwellings`）横向铺满 |
| 3 | **多级表头合并** | 多行表头自上而下用 `_` 连接，**连续同名段只保留一次**。例三级 → `Total_Mode of Transport_Car or Taxi/Private Hire Car Only`；二级 → `HDB Dwellings_3-Room Flats` |
| 4 | **首行为字段名** | 输出 CSV 第 1 行为字段名，第 2 行起为数据 |
| 5 | **表头自动定位** | 不假设从 A1 开始。实测：SingStat 表头在第 10 行（且深度 1–3 行不等）；`hsefa` 在第 3 行；`hsetod` 在第 3–4 行；`Content` 索引表前 4 行为空、第 6 行起 |
| 6 | **层级行标签前向填充** | `hsefa` / `hsetod` 的 Subzone 行原本 Planning Area 列为空，已填充（各 332 格），否则无法判断子区归属 |
| 7 | **脚注剔除** | 去掉表尾 `Note:` 等说明行（如 `respopagesex2025e` 尾部 6 行），CSV 仅保留数据 |
| 8 | **全空列裁剪** | 裁掉整列为空的列（如 `outputFile (2)__T1` 源 max_col=62，实测末列全空 → 61 列） |
| 9 | **换行清理** | 表头中的换行转空格，并做**保守断字合并**：仅当 `-` 紧邻换行时才合并（`Condo-`+换行+`miniums` → `Condominiums`），避免破坏 `3-Room`、`Non-Tertiary` 等真连字符 |
| 10 | **编码** | 统一 `utf-8-sig`（带 BOM），保证 Excel 双击不乱码 |
| 11 | **原文保留** | `.xlsx` **不删除**，与 CSV 同目录并存 |

**命名映射示例**

| 原 xlsx | 生成 CSV |
|---------|---------|
| `outputFile (2).xlsx` | `outputFile (2)__T1.csv` … `__T4.csv` |
| `outputFile (3).xlsx` | `outputFile (3)__T1.csv` … `__T11.csv` |
| `outputFile (4).xlsx` | `outputFile (4)__T1.csv` … `__T21.csv` |
| `outputFile (5).xlsx` | `outputFile (5)__T1.csv` … `__T17.csv` |
| `outputFile.xlsx` | `outputFile__T1.csv` … `__T19.csv` |
| `hsefa2025e.xlsx` | `hsefa2025e.csv` |
| `hsetod2025e.xlsx` | `hsetod2025e.csv` |
| `respopagesex2025e.xlsx` | `respopagesex2025e.csv` |
| `respopagesexfa2025e.xlsx` | `respopagesexfa2025e__Total.csv` / `__Male.csv` / `__Female.csv` |
| `respopagesextod2025e.xlsx` | `respopagesextod2025e__2025(Total).csv` / `__2025(Male).csv` / `__2025(Female).csv` |

> ⚠️ **技术要点**：`openpyxl` 的 `read_only=True` 模式**读不到合并单元格**。正确做法是先用 `zipfile` 检查 `xl/worksheets/sheet*.xml` 中是否存在 `<mergeCells>`，有则用完整加载、无则用 `read_only`，兼顾正确性与内存占用（`respopagesex*` 达 21 万行）。

---

# 附录 C. 字段类型与缺失值约定

## C.1 类型标注约定

| 标注 | 含义 | 读取建议 |
|------|------|---------|
| `text` | 字符串 | 直接读 |
| `number` / `float` | 浮点 | `float()` |
| `int` | 整数 | `int(float())`，注意有些为字符串 |
| `C(n)` | DBF 字符型，长度 n | 字符串 |
| `N(n)` | DBF 数值型 | 可能含前导 0 丢失问题 |
| `F(n)` | DBF 浮点型 | — |

## C.2 缺失值 / 占位符

| 占位符 | 出现位置 | 含义 | 处理建议 |
|--------|---------|------|---------|
| 空字符串 `""` | 全部 | 未采集 / 不适用 | 按缺测处理 |
| `-` | SingStat Census 表格 | **零或可忽略（<阈值被抑制）** | 视为 `0` 或 `NA`，**不要**当文本 |
| `na` | ACRA、部分 Census | **不适用（Not Applicable）** | 视为 `NULL` |
| `Total` / `Total*` / `Total1/` / `Others1/` | Census 表 | **汇总行/列标签**，非数据；`1/`、`2/` 是脚注标记 | join 前剥离后缀 |
| `NIL` | `hdb.csv.building` 等 | 无建筑名 | 视为空 |
| `null` | GeoJSON properties | JSON 空值 | 视为空 |

## C.3 数据类型陷阱清单

| 陷阱 | 位置 | 说明 |
|------|------|------|
| **前导 0 丢失** | `hdb.csv.postal`、ACRA `postal_code`/`block`、`BusStop.shp.BUS_STOP_N` | 数值化后 `01239` → `1239`。**必须按文本读或零填充复原** |
| **数值以字符串存储** | `TrafficFlow_Data.json` 全部数值字段 | `Volume`、`HourOfDate` 均为字符串 |
| **坐标单位混用** | 04/07/09 目录 | `SHAPE.AREA` 为米²（SVY21），几何为经纬度；`X_ADDR`/`Y_ADDR` 为 SVY21 米 |
| **DBF 字段名截断** | 07 目录全部 SHP、08 目录 | 超过 10 字符被截断（`RD_CATG__1`、`lanes:forw`） |
| **列名含特殊字符** | `hsefa2025e`（`≤`、`>`）、Census（`$`、`&`、`/`、`(`、`)`） | SQL / 部分工具需转义或用引号 |
| **同义异名** | 02 目录 | `Planning Areas` vs `Planning Area`；`Subzones` vs `Subzone` |
| **字段内容为 HTML** | `PreSchoolsLocation.geojson.Description` | 需解析 HTML 表格才能取到属性 |
| **拼写错误** | `TouristAttractions.geojson.LONGTITUDE`；HealthFacilities 的 `General Practioner Clinics` | 按原样匹配，勿"纠正"后 join |
| **年份错配** | `bus_vol.csv`（2021-07）vs `TrafficFlow_Data.json`（2025-11） | 同一模型内混用需在论文中说明 |
| **Census 年份识别** | 02/03/06 目录 | `Data last updated: 18/08/2026` 仅为 **SingStat 表维护日期**，**不是数据年份**；年份须看**表题/表号**（Census 2020 vs GHS 2025） |

---

# 附录 D. 建模数据链与文件映射

## D.1 七步流程与文件对应

| 步骤 | 目标 | 输入文件 |
|------|------|---------|
| **① 居住人口** | `P_i`（Subzone 通勤产生量） | `02/` 全部 CSV + `09/POI_Background/hdb.csv` + `04/URANoofDwellingUnits` + `04/HDBExistingBuilding` |
| **② 工作岗位** | `E_p` → `E_j` → `A_j` | `03/outputFile (3)__T4`（PA 就业总量）+ `05/ACRA/*` + `04/MasterPlan2019LandUselayer` + `04/MasterPlan2019Buildinglayer` + `05/poi.csv` |
| **③ 道路阻抗** | `c_ij` | `07/osm-lines` + `07/RoadSectionLine`（分级）+ `other_tags`（限速）+ `osm-polygon`（建筑体量） |
| **④ 先验 OD** | `T_ij^prior` | ①②③ 输出，双约束重力 / NeuroGravity |
| **⑤ Census OD / Mode 约束** | 宏观结构约束 | `03/outputFile (3)__T11`（Table 118）★ + `06/outputFile (4)__T15/T16` + `06/outputFile (5)__T7–T15` |
| **⑥ MATSim 分配** | `q_a^sim` | ④⑤ + `07` 生成 `network.xml.gz` |
| **⑦ 流量校准** | `q_a^obs` → `T_ij^final` | `08/TrafficFlow_Data.json` + `08/TrafficFlow_Links.shp` |

## D.2 双约束重力模型

```
T_ij_prior = α_i · β_j · P_i · A_j · exp(-λ·c_ij) ,
约束： Σ_j T_ij = P_i ,  Σ_i T_ij = A_j
```

## D.3 最终冻结的数据方案

```
Residence + Workplace + ACRA + LandUse/Building/POI + CensusTravelBehavior + RoadNetwork + TrafficFlow
```

**创新链条**：

```
Census 约束 → 静态空间数据构造 Prior OD → MATSim 网络分配 → 真实 TrafficFlow 校准
```

## D.4 15 类核心数据（主干清单）

| 优先级 | 数据 | 位置 | 最终作用 |
|--------|------|------|---------|
| ★★★★★ | Subzone 边界（332） | `01/...SubzoneBoundary...geojson` | OD / TAZ |
| ★★★★★ | Planning Area 边界（55） | `01/...PlanningAreaBoundary...geojson` | Census 控制区 |
| ★★★★★ | Planning Region | 由 PA 的 `REGION_N` 聚合 | Table 118 约束 |
| ★★★★★ | `outputFile (2)__T1` | `02/` | 居住人口 / Production |
| ★★★★★ | `outputFile (3)__T4` | `03/` | 工作地 / Attraction |
| ★★★★★ | `outputFile (3)__T11` | `03/` | 粗粒度 OD 约束 ★ |
| ★★★★★ | `outputFile (4)__T15/T16` | `06/` | 居住端方式/时间分布 |
| ★★★★☆ | `outputFile (5)__T7–T15` | `06/` | Mode Choice |
| ★★★★☆ | `outputFile__T*`（GHS 2025） | `06/` | 行为参数更新 |
| ★★★★★ | ACRA 12 CSV | `05/ACRA/` | 就业空间下分 |
| ★★★★★ | LandUse layer | `04/` | 就业/活动权重 |
| ★★★★★ | Building / DU 点 | `04/` | 建筑级分配 |
| ★★★★☆ | `poi.csv` | `05/` | 活动吸引 |
| ★★★★★ | OSM 路网 | `07/osm-lines` | MATSim Network |
| ★★★★★ | Road speed / travel time | `07/RoadSectionLine` + `other_tags` | Gravity 阻抗 |
| ★★★★★ | `TrafficFlow_Data.json` | `08/` | OD 校准与验证 |

---

# 附录 E. 已知问题与避坑清单

| # | 问题 | 影响 | 应对 |
|---|------|------|------|
| 1 | **文件名与主题错位** | `outputFile (N).xlsx` 的编号与内容主题**无对应关系**（旧版曾把工作地标为 Transport） | **一律以本文件各章标明的主题为准**，勿凭文件序号推断 |
| 2 | **PA 分区数三套并存**（55 / 44 / 30） | 直接 join 会大量丢失 | 取交集 + 特殊类单独建节点（见附录 A.4） |
| 3 | **`SINGAPORE.geojson` 98 分区** | 与 URA 体系不兼容 | 只做量级校验 |
| 4 | **`TrafficFlow.json` 是空壳** | 误当数据源会得到 5 分钟后失效的 S3 链接 | 忽略，用 `TrafficFlow_Data.json` |
| 5 | **`network.xml.gz` 未生成** | MATSim 无法直接跑 | 需从 `07/osm-lines.shp` 现场生成 |
| 6 | **`BLDG_TYPE` 全空 / 无楼层** | 建筑体量不可用 | 从 `07/osm-polygon` 的 `other_tags` 提取 `building:levels`、`height` |
| 7 | **`STN_NAM` 全空** | 轨道站无站名 | 改用 `STN_NAM_DE` |
| 8 | **`RD_CD` / `RD_CATG_NA` 全空** | 道路编码不可用 | 改用 `RD_CATG__1` + `RD_CD_DESC` |
| 9 | **`RapidTransitSystemStation.TYP_CD` 恒 0** | 无区分度 | 改用 `TYP_CD_DES` |
| 10 | **坐标系统一** | 距离/面积算错 10¹⁰ 量级 | 全流程统一 SVY21（EPSG:3414） |
| 11 | **DBF 字段名截断 10 字符** | 按原名字段报错 | 用截断名（见 07 章） |
| 12 | **前导 0 丢失**（postal / block / bus stop） | join 失败 | 零填充为定长字符串 |
| 13 | **`other_tags` 需解析** | 无 maxspeed 则速度只能默认 | 解析 `=>` 风格的键值对 |
| 14 | **Census `-` 是抑制值** | 当 0 处理会低估 | 明确标注为"零或可忽略" |
| 15 | **GHS 2025 与 Census 2020 收入档位不同** | 跨年对比失真 | 先重分箱 |
| 16 | **`bus_vol.csv` 为 2021-07** | 年份错配 | 使用时显式声明 |
| 17 | **列名含 `1/`、`2/` 脚注标记** | join 键不匹配 | 剥离后缀 |
| 18 | **`PreSchoolsLocation` 属性在 HTML 里** | 取不到字段 | 解析 `Description` 的 HTML 表格 |
| 19 | **`LONGTITUDE` 拼写错误** | 按 `LONGITUDE` 取值为空 | 用原名 `LONGTITUDE` |
| 20 | **`hsefa`/`hsetod` 列名单复数不一致** | 合并报错 | 先统一列名 |
| 21 | **CSV 一行内含逗号** | 用 `split(',')` 会错列 | 用标准 CSV 解析器 |

---

# 附录 F. 读取代码样例

## F.1 读取 Census CSV（含行层级解析）

```python
import csv

def load_census(path):
    """读取 Census 表格，自动拆出 Total / PA / Subzone 三级行标签。"""
    with open(path, encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))

    key = list(rows[0].keys())[0]          # 首列为行主键
    out = {"Total": None, "PA": {}, "Subzone": {}}
    for r in rows:
        label = (r[key] or "").strip()
        if label == "Total":
            out["Total"] = r
        elif label.endswith(" - Total"):
            out["PA"][label[:-len(" - Total")]] = r
        else:
            out["Subzone"][label] = r
    return out

# 用法
d = load_census(r"02_Population_Residence\outputFile (2)__T1.csv")
print(len(d["PA"]), len(d["Subzone"]))   # -> 55 332
```

## F.2 解析 OSM `other_tags`

```python
import re

def parse_other_tags(s: str) -> dict:
    """把 '"maxspeed"=>"50","lanes"=>"2"' 解析成 dict。"""
    if not s:
        return {}
    return {k: v for k, v in re.findall(r'"([^"]+)"\s*=>\s*"([^"]*)"', s)}

tags = parse_other_tags('"lanes"=>"5","maxspeed"=>"50","oneway"=>"yes","surface"=>"asphalt"')
# -> {'lanes': '5', 'maxspeed': '50', 'oneway': 'yes', 'surface': 'asphalt'}
```

## F.3 读取 SHP 并统一到 SVY21（EPSG:3414）

```python
import geopandas as gpd

gdf = gpd.read_file(r"07_RoadNetwork\RoadSectionLine_Mar2026\RoadSectionLine.shp")
print(gdf.crs)                      # PROJCS["SVY21", ...] = EPSG:3414
gdf["len_m"] = gdf.length           # 投影坐标下 length 即米

# OSM 是 WGS84，需转换后再做距离/时间计算
osm = gpd.read_file(r"07_RoadNetwork\osm-lines.shp").to_crs(3414)
osm["len_m"] = osm.length
```

## F.4 读取实测流量并按工作日高峰取中位数

```python
import json, statistics
from collections import defaultdict

with open(r"08_TrafficCount\TrafficFlow_Data.json", encoding="utf-8") as f:
    raw = json.load(f)

buckets = defaultdict(list)
for rec in raw["Value"]:
    h = int(rec["HourOfDate"])
    if 7 <= h <= 9:                                  # 早高峰 07:00-10:00
        buckets[(rec["LinkID"], h)].append(float(rec["Volume"]))

am_peak = {k: statistics.median(v) for k, v in buckets.items()}
print(len(am_peak), "个 (LinkID, hour) 组合")
```

## F.5 解析 `PreSchoolsLocation` 内嵌 HTML

```python
import re, html

def parse_kml_description(desc: str) -> dict:
    """从 '<th>KEY</th> <td>VAL</td>' 结构提取属性。"""
    if not desc:
        return {}
    return {html.unescape(k).strip(): html.unescape(v).strip()
            for k, v in re.findall(r"<th>(.*?)</th>\s*<td>(.*?)</td>", desc, re.S)}
    # -> {'CENTRE_NAME': "...", 'CENTRE_CODE': "...", ...}
```

## F.6 零填充还原前导 0

```python
def postal6(x) -> str:
    """邮编统一为 6 位字符串。"""
    return str(int(x)).zfill(6)

def busstop5(x) -> str:
    """公交站号统一为 5 位字符串。"""
    return str(int(x)).zfill(5)
```

---

**文档结束**

| 版本 | 日期 | 变更 |
|------|------|------|
| v1.0 | 2026-09-11 | 首次生成。覆盖 10 个一级子目录、103 个 CSV、13 个 GeoJSON、11 组 SHP、2 个 JSON；含三级空间体系说明、转换规则、字段字典与避坑清单。 |
