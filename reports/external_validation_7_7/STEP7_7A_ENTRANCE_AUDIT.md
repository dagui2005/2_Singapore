# Step 7.7A 入场审计 —— LTA 分车型交通量可得性判定

> **阶段**：7.7 外部观测验证与空间残差归因 → **7.7A LTA 分车型交通量**
> **性质**：入场审计（gate）。**零仿真、只读**；未启动 MATSim；未改任何冻结件；未获取外部数据。
> **脚本**：`scripts/od/audit_external_data_7_7a.py`　**产物**：本目录 6 个文件
> **校验**：**6/6 PASS**　**日期**：2026-09-19

---

## 0. 结论摘要（先给答案）

| 问题 | 结论 |
|---|---|
| 本地有「分车型交通量」吗？ | **没有。`VEHICLE_TYPE_VOLUME_UNAVAILABLE`** —— 核心观测 `TrafficFlow_Data.json` 的 `Volume` 是**全部机动车合计**，无 car/taxi/bus/motorcycle/goods 分解；LTA DataMall 端点清单中亦**无**分车型流量端点 |
| 那 7.7A 就做不了？ | **不。** 本地存在**两条不必获取外部数据**的替代路径：① Census 方式构成（PA 级）；② **90 台 LTA 交通摄像机 × 8,552 帧**（地点级车型**构成**） |
| 用①做了零成本先验，结果？ | **构成解释"总体量级"，但解释不了"空间残差"**：区域 r = **−0.36**、PA 级 r = **+0.25（R²=0.064）**；构成极差（17.1 / 36.5 pp）**≤ 残差极差的 1/3** |
| 与已有结论的关系 | 与 **7.6F-1（不随 f）+ 7.6G（不随 λ）** 完全一致 ⇒ **「空间残差 ⊥ 全局参数」在 demand / λ / 车型构成三个方向同时成立** |
| 一个额外自洽点 | 全域 `car/(car+taxi+moto+lorry+chbus) = 0.6825`，与 7.6A 的 D01 断面 `Sim/Obs = 0.6830` 相差 **0.07%** |

---

## 1. Q1 —— 本地/开放数据的分车型可得性（逐层证据）

证据表：`step7_7a_local_inventory.csv`（12 条）。

### 1.1 核心观测：确证无车型字段

`Singapore_OD_MATSim_FinalData/08_TrafficCount/TrafficFlow_Data.json`（16.3 MB，75,899 条）

```
{"LinkID":"143599","Date":"01/11/2025","HourOfDate":"7","Volume":"523",
 "StartLon":"103.7672285","StartLat":"1.43001094","EndLon":"103.766757",
 "EndLat":"1.42921249","RoadName":"WOODLANDS AVENUE 3","RoadCat":"CATB"}
```

- **字段全集 = 10 个**：`LinkID / Date / HourOfDate / Volume / StartLon / StartLat / EndLon / EndLat / RoadName / RoadCat`
- `Volume` 是**全部机动车合计**，且为**字符串型（含千分位逗号，如 `"1,069"`）**
- `RoadCat` 是**道路等级**（CAT A/B/C…），**不是**车型
- ⇒ **「观测流量里有多少是小汽车」在本地不可分解**。此结论与 7.6A 的前置发现一致，本轮给出字段级复核。

### 1.2 其余本地数据源

| 范围 | 内容 | 车型结论 |
|---|---|---|
| `Static_ 2026_03/GEOSPATIAL`（29 类要素） | 标线/护栏/路灯/`TaxiStand`/`DetectorLoop` 等 | 仅几何，**无流量** |
| `Static_ 2026_03/PUBLIC TRANSPORT` | 车队规模（`monthly_taxi_fleet.csv`）、PT 客流、线路、轨道长度 | **聚合车队量**，非路段流量 |
| `Static_ 2026_03/OTHER` | 人口栅格（WorldPop 100m/1km）、ACRA、设施 | **无交通量** |
| `Dynamic_2026_03_16/historical_data`（55 项） | `TrafficFlow`、`TrafficSpeedBands_v4`（taxi-GPS 派生，**仅速度**）、`PassengerVolume_*`（**公交/地铁人次**）、`BusArrival`… | **无分车型流量** |
| `Singapore_OD_MATSim_FinalData/09_Auxiliary/Transit` | `bus_vol.csv`（17.9 MB） | **公交客流**，非道路分车型 |

### 1.3 LTA DataMall 端点清单（来源：本项目 `lta_dynamic_data_downloader.py`）

端点含：`TrafficFlow` / `TrafficSpeedBands` / `TrafficImages` / `TrafficIncidents` / `EstimatedTravelTimes` /
`PassengerVolume{BusStops,ODBus,ODTrain,TrainStations}` / `BusArrival` / `TaxiAvailability` / `CarparkAvailability` / …
⇒ **无任何 `VehicleType` / `ByType` / 分类计数端点**。项目根 `API_Key.txt` 存在（DataMall 风格），但**即便调用也不存在分车型流量端点**。

### 1.4 开放数据（外部核查）

- `data.gov.sg → Annual Motor Vehicle Population by Vehicle Type`（LTA，2005–2024，412 行）
  ⇒ **全国年度车队构成**（Cars & Station-wagons / Taxis / Buses / Goods & Other / Motorcycles & Scooters / Tax Exempted）—— **是车队，不是路段流量**
- 另有 `Annual Car Population by CC`、`Annual Type and Number of Motor Vehicles Transferred`
  ⇒ 同样是**全国年度车队/过户**口径
- **未发现**任何 link 级 / 断面级的分车型交通量开放数据

### 1.5 唯一本地「车型」线索：LTA 交通摄像机（★）

- `Dynamic_2026_03_16/historical_data/TrafficImages_v2.json` → **90 台摄像机**，含 WGS84 `Latitude/Longitude`
- `Dynamic_2026_03_16/realtime_monitoring/images/` → **8,552 帧**（每台 96 帧），命名 `{CameraID}_{ts}.jpg`
- ⇒ 可经 CV 车辆检测得到**点位级车型【构成】**（car / motorcycle / bus / truck / van / lorry）
- **局限（必须披露）**：① 这是**构成**不是**流量**；② 90 点 vs 576 断面；③ 摄像机以**高速/主干道**为主；
  ④ 图像时窗 **2026-05-05~07**，与 `TrafficFlow_Data.json`（**2025-11**）**时间错配**；
  ⑤ 本地**无 CV 依赖**（`cv2`/`torch`/`ultralytics` 均 MISSING，仅 `PIL 12.0.0` + `numpy`）

**排查范围声明**：以上覆盖 `Static_ 2026_03`、`Dynamic_2026_03_16`、`Singapore_OD_MATSim_FinalData`、
`lta_dynamic_data_downloader.py` 端点清单、`data.gov.sg` 外部核查。**7.1 冻结观测口径即建立在 1.1 的观测上。**

---

## 2. Q2 —— 零成本构成归因先验（audit-level prior，非正式 7.7A 评价）

### 2.1 构思（为什么这条路是有效的）

- 观测 `Volume` = **全部机动车**；模型 sim = **car-only**
- 若空间残差源于车型组成，则 **`Sim/Obs_region` 应≈ 该区域「私人机动车中 car 的份额」**
- 该份额可从 **Census 2020 Table 104**（`outputFile (4)__T15.csv`，居住端 PA × 11 方式）**本地算出**

口径（`PMV` = 私人机动车）：

```
PMV = Car Only + Taxi/PHC Only + Motorcycle/Scooter Only + Lorry/Pickup Only + Private Chartered Bus/Van Only
car_share_pmv = Car Only / PMV
```

### 2.2 全域一致性（★ 出乎意料地干净）

| 量 | 值 | 来源 |
|---|---:|---|
| Car Only | 459,796 | Census T104（= 需求锚 V1） |
| PMV | 673,741 | T104 派生 |
| **car_share_pmv** | **0.682452** | 本轮 |
| **1 / car_share_pmv** | **1.4653** | 本轮 |
| D01 断面 `Sim/Obs`（07-09, f=1.00） | **0.6830** | 7.6A / 7.4.3-R |
| 1 / D01 `Sim/Obs` | 1.4641 | 7.6A |

- `|0.682452 − 0.6830| = 5.5e-4`（**0.08%**）
- 机制上自洽：**f=1.00 时 car-only 模型正好复现「私人机动车中 car 的份额」**
- ⇒ 与 7.6A 判决 `CALIBER_GAP_DOMINATES`（"观测里非小汽车的部分几乎正好填满模型缺口"）**互相印证**
- ⚠️ **口径护栏**：`1.4653`（Census 构成比）与 7.6A 的 `1.4641`（`=1/D01`）**数值接近但概念不同**，
  属**两条独立证据链的巧合吻合**；⛔ **不得**据此宣称二者等价，也不得由任一者反推 demand scale。

### 2.3 区域级（7.6H W01 冻结工作点残差）

| region | 断面 | 残差 (pp) | car_share 断面加权 (%) | 构成预测残差 (pp) | 误差 (pp) |
|---|---:|---:|---:|---:|---:|
| EAST REGION | 133 | **−31.75** | 68.38 | +0.20 | **+31.95** |
| CENTRAL REGION | 112 | −7.82 | 74.01 | +8.45 | +16.27 |
| WEST REGION | 180 | +2.84 | 63.58 | −6.84 | −9.68 |
| NORTH REGION | 72 | **+23.09** | 56.88 | −16.65 | **−39.74** |
| NORTH-EAST REGION | 77 | **+33.88** | 69.61 | +2.00 | **−31.89** |

- **Pearson r(残差, car_share) = −0.3600**（n=5，**符号与预期相反**）
- **残差极差 65.6 pp vs 构成极差 17.1 pp ⇒ 3.83×**
- 反例最刺眼：**NORTH 是 car 份额最低（56.9%）的区域，却是 sim 超额最高的区域（+23.1%）** ⇒ 直接推翻"低 car 份额 ⇒ 低估"的朴素假设
- 仅 **EAST** 一例巧合对齐（构成 68.4% ↔ 区域 `Sim/Obs` 0.682）

### 2.4 PA 级（n_sections ≥ 5，匹配 21 个 PA）

- **Pearson r(残差, car_share_pmv) = +0.2533 ⇒ R² = 0.0641**（符号正确但**仅解释 6.4% 方差**）
- **残差极差 206.4 pp vs 构成极差 36.5 pp ⇒ 5.66×**
- 反例：`KALLANG` car 份额 0.677 ≈ 全域 0.682，残差却是 **−73.5%**；`MARINE PARADE` 份额 0.805（高）却 **−52.5%**

### 2.5 先验判决

> **`COMPOSITION_EXPLAINS_GLOBAL_LEVEL_NOT_SPATIAL_PATTERN`**
> 车型/方式构成是**总体量级**的一侧解释（全域 0.6825 ↔ 1.4653），但对**空间分布**几乎无解释力
> （区域 r=−0.36 且符号相反；PA 级 R²=0.064；构成动态范围只有残差的 1/3~1/6）。

**局限（必须随结论一并引用）**
1. 区域加权用 `section_geography` 的 PA 词表，与 Census PA 词表**不同**：12 个 PA（TUAS/PIONEER/ORCHARD/MUSEUM…）未匹配，回退 `Others`；6 个 Census PA（BISHAN/QUEENSTOWN/RIVER VALLEY/SEMBAWANG/TANGLIN/OTHERS）无对应断面
2. 人-次 ≠ 车-次（公交需载客率折算；本地无 `occ` 观测）
3. 区域残差含 7.6C-1 已识别的 **8.14% 硬零流测量伪影**
4. n=5（区域）/ n=21（PA）—— 只作**方向性先验**，不作定论

---

## 3. 本地 CV 路径可行性（路径 B）

`step7_7a_camera_coverage.csv`（摄像机 → PA/Region 空间归并，89/90 成功）：

| region | 摄像机数 | 断面数 | 残差 (pp) |
|---|---:|---:|---:|
| CENTRAL REGION | **35** | 112 | −7.82 |
| EAST REGION | 14 | 133 | **−31.75** |
| NORTH REGION | 15 | 72 | **+23.09** |
| NORTH-EAST REGION | **7** | 77 | **+33.88** |
| WEST REGION | 18 | 180 | +2.84 |

- **覆盖与残差错位**：残差最大的 **NE（+33.9%）仅 7 台**、EAST（−31.8%）14 台；而残差最小的 CENTRAL 反而最多（35 台）
- ⇒ 即便做 CV，也**难以直接覆盖残差最大区**；须与断面做空间近邻匹配后外推，**证据强度有限**
- 且需新增依赖（`ultralytics`/`torch` ≈ 数 GB），属**独立子课题**，不宜混入本轮

---

## 4. 三条路径与建议

| 路径 | 内容 | 外部数据? | 状态 | 评估 |
|---|---|---|---|---|
| **A1** | Census 方式构成（PA 级）归因 | 否 | **本轮已完成（audit-level prior）** | 已有方向性结论：解释力弱 |
| **B** | LTA 摄像机图像 CV 车型构成 | 否 | 待定 | 覆盖错位 + 需 CV 依赖 + 时序错配 ⇒ 证据强度有限 |
| **C** | 向 LTA 获取**断面级分车型计数** | **是** | **BLOCKED** | 唯一能严格回答"观测车型构成"的路径；须申请（见 `STEP7_7A_EXTERNAL_DATA_REQUEST.md`） |

**建议**
1. 承认 **A1 已完成其使命**：它把「车型构成」正式从空间残差主因名单中**排除**（与 f、λ 并列）
2. **7.7A 的严格版（路径 C）标记 `BLOCKED_ON_EXTERNAL_DATA`**，不阻塞主线
3. **不把 A1 升级为正式 7.7A 评价**（n 太小、口径混杂）；若要形式化，应升格为 **7.7A-1（本地方案构成代理）** 并接受其局限
4. **主线建议前移至 7.7B（HTS 出发时刻）与 7.7C（空间残差归因）** —— 前者所需数据在本地 `06_Census_TravelBehavior` 有部分支撑（T105/T16 通勤时间分布、Table 117 PA × 通勤时间），后者零外部依赖

---

## 5. 判据草案（若用户裁定形式化 7.7A-1）

- **A1.1 全局自洽**：`|car_share_pmv − D01_SimObs| / D01_SimObs < 2%`　→ 实测 **0.08%** ✅
- **A1.2 空间解释力**：区域 `|r| ≥ 0.5` **且** 构成极差 ≥ 残差极差 **⇒ FAIL** ⇒ 判 `COMPOSITION_NOT_SPATIAL_DRIVER`
- **A1.3 符号一致**：区域 r 与 PA r **同号** ⇒ 实测 **−0.36 vs +0.25，异号** ⇒ 进一步支持 FAIL
- **判决空间**：`COMPOSITION_SPATIAL_DRIVER` | `COMPOSITION_GLOBAL_ONLY`（本轮）| `COMPOSITION_INERT`

---

## 6. 明确未做

- ❌ 未启动 MATSim（`matsim_launched=False`）
- ❌ 未获取任何外部数据（`external_data_acquired=False`）
- ❌ 未改动 7.1 / 7.3.6A / OD / network / capacity / population / route-choice 任何冻结件
- ❌ 未把构成先验当作结论（仅 audit-level prior）
- ❌ 未安装 CV 依赖、未做图像检测
- ❌ 未细扫 λ / demand；未做 crosswalk-b（承 7.6G/H 裁定）

---

## 7. 产物清单

| 文件 | 内容 |
|---|---|
| `STEP7_7A_ENTRANCE_AUDIT.md` | 本报告 |
| `STEP7_7A_EXTERNAL_DATA_REQUEST.md` | 路径 C 的外部数据获取说明 |
| `step7_7a_local_inventory.csv` | 本地分车型可得性逐文件证据（12 条） |
| `step7_7a_mode_composition_by_pa.csv` | Census T104 方式构成（PA 级，31 行） |
| `step7_7a_mode_composition_by_region.csv` | 区域构成 + 构成预测残差 + 误差 |
| `step7_7a_composition_vs_residual.csv` | 构成 vs 残差（region 5 行 + PA 21 行） |
| `step7_7a_camera_coverage.csv` | 摄像机 → PA/Region 覆盖 |
| `step7_7a_summary.json` | 机读汇总（含 6 项校验、判决、局限） |
