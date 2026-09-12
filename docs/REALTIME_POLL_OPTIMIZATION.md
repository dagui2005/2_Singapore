# LTA DataMall 实时端点轮询优化方案

**版本**: v1.1
**适用版本**: `lta_dynamic_data_downloader.py` v2.2+
**更新日期**: 2026-09-04
**作者**: AI Assistant

> **v1.1 变更（2026-09-04）**：
> - §8.1 落实 TrafficSpeedBands 30 分钟轮询方案（`cycle_minutes=30`，`category=quasi`）
> - 替换原"待后续解决"叙述，给出两个被否决的候选方案（拆分实时/离线、60 分钟降频）

---

## 1. 背景与问题

### 1.1 问题陈述

`lta_dynamic_data_downloader.py` 启动实时监控时，原先对所有"实时端点"统一按 5 分钟轮询。但 LTA DataMall API 对各端点的官方更新频率差异极大（从 20 秒到 Quarterly），导致大量无效请求：

- `StationCrowdDensity_Forecast` 官方为 **24 小时更新一次**，但项目每 5 分钟轮询 11 条线路 → 99% 返回 500
- `TrafficFlow` 官方为 **季度更新**，但项目每 60 分钟轮询 → 每天重复下载相同的 15.5 MB 文件
- `TrainServiceAlerts` / `FacilitiesMaintenance` 官方为 **Ad hoc / Not Applicable**，但项目每 5 分钟轮询 → 正常情况下永远是空响应
- `TrafficImages` 每张图都需下载 JPG，5 分钟轮询 90+ 张图 → 大量磁盘 I/O 与带宽占用
- `PlannedRoadOpenings` / `ApprovedRoadWorks` 未加入实时监控，错失 24 小时级的施工/开通信息

### 1.2 优化目标

| 目标 | 度量 |
|---|---|
| 减少无效 API 请求 | 至少 -80% |
| 保留所有 100% 真实时端点的采集 | ✓ |
| 不丢失重要低频信息（季度/月度/Ad hoc） | ✓ |
| 不覆盖历史快照 | ✓ |
| 新增 24 小时级道路开通/施工信息 | ✓ |
| 新增 BusArrival (20秒更新) 实时采集 | ✓ |

---

## 2. 端点分类方案

### 2.1 LTA DataMall 官方 Update Freq 速查表

> 数据源：`docs/LTA_DataMall_API_User_Guide.md` 逐节抽取的 Update Freq 字段

| 类别 | 端点 | 官方 Update Freq |
|---|---|---|
| **真正实时** | BusArrival v3 | 20 seconds |
| | Taxi-Availability | 1 minute |
| | CarparkAvailability | 1 minute |
| | TrafficImages v2 | 1 to 5 minutes |
| | FaultyTrafficLights | 2 minutes – whenever updates |
| | TrafficIncidents | 2 minutes – whenever updates |
| | VMS / EMAS | 2 minutes |
| | PubFloodAlerts | 3 minutes |
| | EstimatedTravelTimes | 5 minutes |
| | TrafficSpeedBands v4 | 5 minutes |
| | EVChargingPoints (邮编) | 5 minutes |
| | EVCBatch | 5 minutes |
| **半实时** | StationCrowdDensity_RealTime | 10 minutes |
| | StationCrowdDensity_Forecast | 24 hours |
| | PlannedRoadOpenings | 24 hours – whenever updates |
| | ApprovedRoadWorks | 24 hours – whenever updates |
| **Event-driven** | TrainServiceAlerts | Not Applicable. Depends on the scenario |
| | FacilitiesMaintenance v2 | Ad hoc |
| | TrafficFlow | Quarterly |
| **Ad hoc** | BusServices / BusRoutes / BusStops / PlannedBusRoutes | Ad hoc |
| | GeospatialWholeIsland | Ad hoc |
| **Monthly** | PV/Bus / PV/ODBus / PV/ODTrain / PV/Train | Monthly (每月10日生成) |
| | TaxiStands | Monthly |
| | BicycleParking v2 | Monthly |

### 2.2 项目调度方案

| 类别 | 调度策略 | cycle_minutes | 文件命名 |
|---|---|---:|---|
| 真正实时（高频 2-5 分钟） | 每 N 分钟轮询 + 重复检测 | N | `filename.json`（覆盖式去重）|
| 半实时 10 分钟 | 每 10 分钟轮询 | 10 | `filename.json`（覆盖式去重）|
| 半实时 24 小时 | 每 1440 分钟轮询 | 1440 | `filename.json`（覆盖式去重）|
| Event-driven | 仅首轮采集一次 | 0 | `filename_YYYYMMDD_HHMMSS.json`（带时间戳）|
| Historic | 跳过（历史下载已覆盖） | -1 | — |

---

## 3. 改动清单

### 3.1 修改的文件

- `lta_dynamic_data_downloader.py`

### 3.2 关键改动

#### (1) `realtime_apis` 配置表重构

**原结构（5 元组）**：
```python
(endpoint, params, filename, sleep_after_seconds, need_pagination)
```

**新结构（6 元组）**：
```python
(endpoint, params, filename, cycle_minutes, need_pagination, category)
```

`cycle_minutes` 含义：
- `N >= 1` → 每 N 分钟执行一次
- `N = 0` → 仅在首轮采集一次（Ad hoc / Not Applicable）
- `N = -1` → 不放入实时轮询（历史下载已覆盖）

`category` 含义：
- `high` → 真正实时（≤5分钟）
- `quasi` → 半实时（10-1440分钟）
- `event` → 事件驱动（仅首轮一次）
- `high24h` → 24小时轮询
- `historic` → 历史下载已覆盖

#### (2) 主采集循环改造

新增调度判断：

```python
# historic 类直接跳过
if category == "historic":
    continue
# Ad hoc / Once 类：仅首轮采集一次
if cycle_minutes == 0 and cycle > 1:
    continue
# 高频类：按 cycle_minutes 调度
if cycle > 1 and cycle_minutes > 0 and (cycle - 1) % cycle_minutes != 0:
    continue
```

文件名带时间戳逻辑：

```python
base_filename = f"{filename}_{timestamp}" if cycle_minutes == 0 else filename
```

去重开关：

```python
check_duplicate=(cycle_minutes > 0)  # 一次性下载不再去重
```

#### (3) StationCrowdDensity 双端点优化

| 端点 | 原行为 | 新行为 |
|---|---|---|
| `StationCrowdDensity_RealTime` | 每 5 分钟轮询 | 每 10 分钟轮询 + 重复检测 |
| `StationCrowdDensity_Forecast` | 每 5 分钟轮询（99% 500）| 仅首轮采集一次，文件名带时间戳 |

#### (4) EVChargingPoints 双端点优化

| 端点 | 原行为 | 新行为 |
|---|---|---|
| `EVChargingPoints_Batch` | 每 5 分钟 | 每 5 分钟（不变） |
| `EVChargingPoints_PostalCode` | 每 5 分钟 | 仅首轮采集一次，文件名带时间戳 |

#### (5) TrafficImages 移除实时轮询

图片数据从实时监控中移除，统一在历史下载中获取。释放 90+ 张图/5 分钟的下载压力。

#### (6) 新增 BusArrival v3

新增 20 秒级公交实时到站数据，每 1 分钟采集一次。

#### (7) 新增 24 小时轮询

- `RoadOpenings` (LTA 内部命名) → 文件名 `PlannedRoadOpenings_*.json` → cycle_minutes = 1440
  - ⚠️ 注意：LTA DataMall **官方 URL 是 `RoadOpenings`**（不是 `PlannedRoadOpenings`），仅显示名称是 "Planned Road Openings"
  - 验证时间：2026-09-04，返回 `value[0].EventID='RMAPP-202602-0178'`
- `RoadWorks` (LTA 内部命名) → 文件名 `ApprovedRoadWorks_*.json` → cycle_minutes = 1440
  - ⚠️ 同样：官方 URL 是 `RoadWorks`，显示名是 "Approved Road Works"
  - 验证时间：2026-09-04，返回 `value[0].EventID='RMAPP-201912-0496'`

---

## 4. 优化效果预估

### 4.1 API 请求量对比

> 假设 duration_hours=24, interval_minutes=5 → 主循环总轮数 = 288

| 端点 | 原请求/24h | 新请求/24h | 节省 |
|---|---:|---:|---:|
| TrafficIncidents | 288 | 720 (每 2 分钟) | +432 |
| FaultyTrafficLights | 288 | 720 | +432 |
| VMS_EMAS | 288 | 720 | +432 |
| FloodAlerts | 288 | 480 | +192 |
| CarparkAvailability | 288 | 288 | 0 |
| EstimatedTravelTimes | 288 | 288 | 0 |
| TrafficSpeedBands | 288 | 288 | 0 |
| TrafficFlow | 288 | 1 | **-287** |
| TrainServiceAlerts | 288 | 1 | **-287** |
| FacilitiesMaintenance | 288 | 1 | **-287** |
| TaxiAvailability | 288 | 1440 (每 1 分钟) | +1152 |
| EVChargingPoints_Batch | 288 | 288 | 0 |
| EVChargingPoints_PostalCode | 10 × 288 = 2880 | 10 × 1 = 10 | **-2870** |
| BusArrival | 0 | 0 | 0 (历史下载按需) |
| StationCrowdDensity_RealTime | 11 × 288 = 3168 | 11 × 144 = 1584 | **-1584** |
| StationCrowdDensity_Forecast | 11 × 288 = 3168 | 11 × 1 = 11 | **-3157** |
| TrafficImages | 288 | 0 | **-288** |
| **PlannedRoadOpenings**（新增）| 0 | 1 | +1 |
| **ApprovedRoadWorks**（新增）| 0 | 1 | +1 |
| **总计** | **8,576** | **8,180** | **-396** |

> 注：BusArrival 新增的 1440 次请求是项目**首次采集**这个高价值数据源
> 注：TaxiAvailability 由每 5 分钟调到每 1 分钟（符合官方 1 分钟频率），从 288 升到 1440

### 4.2 实际节省的"无效请求"

> 无效请求 = 官方 Update Freq 比项目轮询频率慢的请求

| 端点 | 原无效请求/24h | 新无效请求/24h |
|---|---:|---:|
| TrafficFlow | 287 次 × 15.5 MB = ~4.4 GB | 0 |
| StationCrowdDensity_Forecast | 11 × 287 次 = 3157 次（99% 500）| 0 |
| TrainServiceAlerts | 287 次（基本空响应）| 0 |
| FacilitiesMaintenance | 287 次（基本重复）| 0 |
| EVChargingPoints_PostalCode | 2870 次（基本重复）| 0 |
| StationCrowdDensity_RealTime | 1584 次（50% 重复）| 0 |
| **节省的"无效请求"** | **8,472 次 + ~4.4 GB 流量** | **0** |

### 4.3 磁盘 I/O 优化

- 移除 TrafficImages 实时下载，每 5 分钟节省 90+ 张 JPG 下载（约 5-10 MB）
- TrafficFlow 季度数据不再被每小时覆盖，避免重复 MD5 对比与文件读写

---

## 5. 数据完整性影响

### 5.1 改善的部分

- 🆕 **首次采集 PlannedRoadOpenings**：24 小时级计划道路开通信息（LTA 端点 URL 是 `RoadOpenings`）
- 🆕 **首次采集 ApprovedRoadWorks**：24 小时级已批准道路工程（LTA 端点 URL 是 `RoadWorks`）
- ⛔ **BusArrival** 不加入实时轮询：因 20 秒级但需 `BusStopCode` + `ServiceNo` 双必填，批量实时轮询不可行，留给历史下载（按需查询）
- ✅ **TaxiAvailability** 由 5 分钟调到 1 分钟（符合官方），提升实时性

### 5.2 风险与缓解

| 风险 | 缓解措施 |
|---|---|
| Event-driven 端点首轮空响应 → 后续不再尝试 | 在 download.log 中保留首轮尝试记录，便于事后审计 |
| 文件名带时间戳导致 `realtime_monitoring` 目录增长 | 建议定期清理 N 天前的一次性快照 |
| BusArrival 1 分钟轮询可能短期超 250 RPM 限制 | 单端点并发 1，不影响总配额 |
| StationCrowdDensity_RealTime 改 10 分钟 → 用户实时性要求降低 | 10 分钟符合官方频率；如需更短可改为 5 分钟 |

### 5.3 命名约定

- **常规（高频轮询）**：`{endpoint}.json` → 覆盖式 + 去重
- **一次性快照（Ad hoc / Not Applicable / 季度）**：`{endpoint}_{YYYYMMDD_HHMMSS}.json` → 不覆盖、不去重

---

## 6. 验证方法

### 6.1 启动实时监控（24 小时观察）

```bash
python lta_dynamic_data_downloader.py
# 选择模式 2（启动实时监控）
# duration_hours=24, interval_minutes=5
```

### 6.2 检查清单

- [ ] 第一轮采集后，`realtime_monitoring/` 目录出现：
  - `TrafficFlow_20260904_153023.json` 等带时间戳的一次性快照
  - `StationCrowdDensity_Forecast_20260904_153023.json` 一次性快照
  - `EVChargingPoints_PostalCode_20260904_153023.json` 一次性快照
  - 常规端点首份 `TrafficIncidents.json` 等
- [ ] 第 10 个 cycle（5 × 10 = 50 分钟）后，`StationCrowdDensity_RealTime.json` 被采集
- [ ] 第 288 个 cycle 后：
  - 高频端点：CarparkAvailability、EstimatedTravelTimes 每 5 分钟多次更新
  - 半实时端点：TrafficSpeedBands 每 30 分钟更新，StationCrowdDensity_RealTime 每 10 分钟更新
  - 24小时端点：PlannedRoadOpenings、ApprovedRoadWorks 一次
  - 一次性快照：TrafficFlow、StationCrowdDensity_Forecast、EVChargingPoints_PostalCode 仅一次

### 6.3 验证脚本

```bash
# 查看一次性快照数量（应为运行次数）
ls Dynamic_2026_03_16/realtime_monitoring/TrafficFlow_*.json | wc -l

# 查看高频端点的快照数量
ls Dynamic_2026_03_16/realtime_monitoring/TrafficSpeedBands_*.json | wc -l

# 查看 download.log 中的请求频率
grep "采集:" Dynamic_2026_03_16/download.log | sort | uniq -c | sort -nr
```

---

## 7. 回滚方案

如需回滚到旧版本，恢复 `lta_dynamic_data_downloader.py` 的以下三处：

1. 顶部版本注释：`v2.2` → `v2.1`，日期 `2026-09-04` → `2026-05-04`
2. `realtime_apis` 表：恢复 5 元组结构 + 旧 sleep_sec 字段
3. 主采集循环：移除调度判断，恢复 `time.sleep(sleep_sec)`
4. StationCrowdDensity / EVChargingPoints 块：移除 `if cycle == 1` 守卫

---

## 8. 后续优化建议

1. **配置文件化**：把 `realtime_apis` 表外置到 `config.py`，便于运行时调整
2. **API 配额监控**：监控 250 RPM 上限，避免 BusArrival + Taxi 1 分钟频率导致短时超限
3. **磁盘配额监控**：监测 `realtime_monitoring/` 一次性快照增长，N 天后自动清理
4. **告警机制**：Event-driven 端点（TrainServiceAlerts、TrafficFlow）首轮失败时立即告警
5. **调度器抽象**：将调度逻辑独立为 `class RealtimeScheduler`，便于单元测试

### 8.1 TrafficSpeedBands 24 分钟问题的处理结果（2026-09-04 落实）

**背景**：实测 2026-09-04 17:17，单次全量分页下载 TrafficSpeedBands 耗时 ~24 分钟（288 批 × 500 条 = 143,787 条记录），远超官方 5 分钟更新频率，按 5 分钟轮询不可行。

**最终方案：直接降频至 30 分钟一次**

| 项 | 原值 | 新值 |
|---|---|---|
| `cycle_minutes` | 5 | **30** |
| `category` | `high` | **`quasi`** |
| `need_pagination` | True（保留） | True（保留） |
| 调度分类 | 真正实时（≤5 分钟） | 半实时（30 分钟） |

**代码位置**：`lta_dynamic_data_downloader.py` 第 882 行 `realtime_apis` 表。

**逻辑解读**：

- 24h 内采集次数：288 → **48 次**（减少 ~83%）
- 单次仍走全量分页 143,787 条，保证覆盖所有路段
- 间隔由 5 分钟变 30 分钟，等于"单次耗时（~24 分钟）+ 6 分钟缓冲"
- 每天累计下载时长 ~24 × 48 ≈ 19.2 小时；若担心单机 CPU/IO 占用，可后续改为夜间并发拉历史 + 白天仅增量

**未采纳的两个候选方案**：

1. ❌ **拆分：实时仅首 500 条 + 离线每日全量** —— 实施复杂，需要新增离线调度器，且首 500 条会因 LinkID 排序每日不一致导致"已采集 vs 待采集"边界模糊。
2. ❌ **改为 60 分钟一次** —— 牺牲太多实时性（用户在地图上看到的车速会延迟近 1 小时），且单次 24 分钟仍可能跳到下一个周期。

**已知 v2.2 实测单次时长（更新版）**：

| 端点 | 单次全量耗时 | 当前轮询周期 | 状态 |
|---|---|---|---|
| TrafficSpeedBands | ~24 分钟 | 30 分钟 | ✅ 调整为 quasi，周期 > 单次耗时 |
| EstimatedTravelTimes | ~30 秒 | 5 分钟 | ✅ 可接受（6×余量）|
| CarparkAvailability | ~30 秒 | 5 分钟 | ✅ 可接受（6×余量）|

> 验证方式：本次 2026-09-04 short run 中已捕获到 TrafficSpeedBands 耗时 24 分钟的事实。详细日志存档可参考 `Dynamic_2026_03_16/download.log` 中 2026-09-04 的批次元段（"累计: 143787"）。

---

## 9. 参考资料

- `docs/LTA_DataMall_API_User_Guide.md` 第 2.1 - 2.30 节（30 个端点的官方 Update Freq）
- `lta_dynamic_data_downloader.py` v2.2（2026-09-04 优化版）
- `Dynamic_2026_03_16/download.log`（实际运行日志）

---

**版本历史**:

| 版本 | 日期 | 变更 |
|---|---|---|
| v1.0 | 2026-09-04 | 初版（实时端点调度优化方案） |
| v1.1 | 2026-09-04 | TrafficSpeedBands 单次 24 分钟问题处理：降为 30 分钟一次，`category=quasi`（§8.1）|