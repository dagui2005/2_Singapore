# Step 3B — Attraction v2 运行与 v1 对比报告

- 生成时间：2026-09-11
- 脚本：`scripts/od/build_attraction_v2.py`（+ `scripts/od/attraction_diagnostics.py`）
- 状态：**PASS**（运行 1m58s）
- 输出目录：`reports/od_attraction_v2/`
- Step 3A 基线：`reports/od_attraction_v1/`（快照保留，未覆盖）

---

## 1. 运行结果

| 指标 | v2 数值 |
|---|---|
| Subzone 数 | 332 |
| 物理工作地 PA / 特殊节点 | 44 / 3 |
| Census 物理控制总量 | 1,935,235 |
| Attraction 合计 | 1,935,235 |
| PA 守恒最大绝对 / 相对误差 | 7.28e-12 / 1.98e-16 |
| ACRA 记录 | 1,049,322 |
| 零 Attraction Subzone | 25（与 v1 相同） |
| ACRA=0 但 A>0 | 17（v1: 13） |
| GFA=0 但 A>0 | 0 |
| 单 zone 占 PA >50% | 7（v1: 9） |
| 单 zone 占 PA >60% | 6（v1: 7） |

权重（未改动）：`ACRA 0.55 / GFA 0.30 / LandUse 0.10 / POI 0.05`

---

## 2. 修复的 3 个运行级 bug（均为读表/合并问题，非权重值问题）

| # | 位置 | 问题 | 修复 |
|---|---|---|---|
| 1 | `buildings()` | `gpd.read_file(osm-polygon.shp, encoding="latin-1")` 被 pyogrio 忽略，`other_tags` 字段非法字节触发 `UnicodeDecodeError`（byte 0xe5） | 改读 `osm-polygon_expanded.shp` 的 ASCII 列 `building:l` / `height` / `building`，1.1s 读入 155,074 条，彻底绕开该字段 |
| 2 | `acra_zone()` | 返回表带 `planning_area_norm`，按 `subzone_code` merge 回 z 时列名冲突被拆成 `_x/_y` → `KeyError` | 只返回 `subzone_code` + 统计量 |
| 3 | `acra_zone()` | 同上，返回表还带 `zone_id` → 后续 `groupby.agg(zone_id=...)` `KeyError` | 一并移除 |

> 这三点与 Step 0 记录的"OSM 编码坑"同源。**结论：涉及 `osm-*.dbf` 的读取，一律改用 `*_expanded.shp` + 只取 ASCII 列，或用 pyshp `encoding="latin-1"`。**

---

## 3. 决定性发现：建筑层数覆盖率仅 20.6%

```
building_polygons : 155,074
levels_from_osm   :  30,866  (19.9%)   building:levels 有值
levels_from_height:   1,140  ( 0.7%)   height/3.2 回退
levels_default_1  : 123,068  (79.4%)   缺失 → 保守 1 层
levels_coverage   :  20.6%
```

**后果：79.4% 的建筑 GFA = footprint × 1，GFA 实质上退化为"又一次建筑面积权重"**，未能引入"垂直强度"信息。这正是本轮要解决的核心问题未被解决的原因。

组件相关性（v2，非零 zone）：

| 组件 | 与 Attraction 相关系数 |
|---|---|
| ACRA | 0.761 |
| **POI** | **0.551** |
| GFA | 0.184 |
| LandUse | 0.171 |

GFA 相关性（0.184）甚至低于 POI（0.551）——因为 80% 建筑层数缺省为 1。

---

## 4. v1 vs v2 关键错配对比（上一轮被点名的对象）

| Subzone | PA | v1 占比 | v2 占比 | 判定 |
|---|---|---|---|---|
| JURONG ISLAND AND BUKOM | WESTERN ISLANDS | 90.72% | **91.06%** | ❌ 未解决，略恶化 |
| MURAI | WESTERN WATER CATCHMENT | 78.87% | **79.66%** | ❌ 未解决，略恶化 |
| UPPER THOMSON | BISHAN | 79.86% | 62.99% | ✅ 改善 17pp |
| CHANGI AIRPORT | CHANGI | 76.42% | 68.24% | ✅ 改善 8pp |
| DHOBY GHAUT | MUSEUM | 62.92% | 61.03% | ➖ 基本不变 |

整体结构变化：
- 总重分配量 `Σ|A_v2 − A_v1| = 497,969` 人，占控制总量 **25.7%**
- Spearman(share_v1, share_v2) = **0.815**
- 最大单 zone 变动：ANSON DOWNTOWN CORE **+16,873**；MARINA CENTRE −9,477；TOH TUCK −6,996；BISHAN EAST +6,878

**v2 确实改变了空间结构（25.7% 重分配），但没有定向修复"大面积低强度地块被放大"。**

---

## 5. 根因诊断（两个结构性原因，均与 0.55/0.30/0.10/0.05 无关）

### 5.1 组内 min-max 归一化是"无量纲"的（主因）
```python
z["acra_component"] = g.acra_activity_weight.transform(norm)   # min-max to [0.05,1.05]
```
min-max 把每个 PA 内的最大值拉到 1.0，**绝对量级被抹平**：
- Jurong Island 仅 5 家注册企业 vs 同 PA 内其他 zone 的 0 家 → minmax 判为"最强"
- 而同 PA 内即使有 5,000 家企业的 zone，minmax 后同为 1.0

→ 因此 v1/v2 都给出 ~91%，且 0.05 下限让"零活动 zone"仍分得份额。

### 5.2 GFA 因层数缺失退化为 footprint（次因）
见第 3 节。

### 5.3 附带发现：Lu 类别映射键名错位（已修）
v2 的 `LU_FACTOR` 只匹配 **23/33** 类，10 类误落默认 0.20：

| 真实 LU_DESC | 多边形数 | v2 实际 factor | 应映射键（v2 写的） |
|---|---|---|---|
| UTILITY | 1,067 | 0.20 | 未写 |
| COMMERCIAL / INSTITUTION | 533 | 0.20 | 未写 |
| HOTEL | 285 | 0.20 | **v2 漏写（v1 原有 1.5）** |
| MASS RAPID TRANSIT | 49 | 0.20 | 未写 |
| **PORT / AIRPORT** | 49 | **0.20** | 写了 `PORT`/`AIRPORT`/`PORT-AIRPORT` → 键名不含空格斜杠，全错 |
| BUSINESS 1 - WHITE | 45 | 0.20 | 写了 `B1-WHITE` → 错 |
| BEACH AREA | 35 | 0.20 | 写了 `BEACH` → 错 |
| LIGHT RAPID TRANSIT | 15 | 0.20 | 未写 |
| BUSINESS 2 - WHITE | 14 | 0.20 | 写了 `B2-WHITE` → 错 |
| BUSINESS PARK - WHITE | 12 | 0.20 | 写了 `BUSINESS PARK-WHITE` → 错 |

即"airport/port 应明显高于空地"的意图**完全未生效**。

**已交付修复**：`reports/od_attraction_v2/landuse_class_mapping.csv`（33/33 覆盖，键名严格对齐真实 `LU_DESC`；含 `employment_factor` / `building_factor` / `allow_employment` / `calibrated` / `note` 五列）。其中 5 类标记 `calibrated=N`（UTILITY、COMMERCIAL / INSTITUTION、HOTEL、MASS RAPID TRANSIT、LIGHT RAPID TRANSIT）留待后续标定，其余沿用你已给出的因子值，未新增凭经验数值。

---

## 6. 结论与建议（待你决策是否冻结 v2）

**不建议直接冻结 `attraction_v2.csv`**：GFA 组件当前无效，Lu 映射错位，且主因（min-max 无量纲化）未动。

建议 **Step 3B.1**，只动结构、不动 4 个组件权重：

| 项 | 现状 | 建议 |
|---|---|---|
| A. 归一化 | PA 内 min-max（量级无关） | 改为**保序保量级**：`log1p(·)` 后按 PA 求和归一化；去除 0.05 下限的"雨露均沾" |
| B. 建筑层数 | 79.4% 缺省 1 层 | 用 `building` / `residentia` 类型给**典型层数先验**（HDB≈12、公寓/共管≈10、排屋/有地≈2、工业≈3…），再叠加实测 levels |
| C. Lu 映射 | 23/33 匹配 | 用 `landuse_class_mapping.csv` 驱动（已交付），PORT / AIRPORT 等归位 |
| D. POI | 权重仅 0.05、相关性却 0.551 | 属于"信息量高于其权重"的组件，B.1 后可考虑上调（属参数标定，留待 TrafficFlow 校准阶段） |

补充事实（供决策）：Jurong Island & Bukom 现实中为新加坡石化集群、确有大量在岗作业人员，而 ACRA 仅登记 5 家实体——**ACRA 登记数 ≠ 作业强度**，因此"Jurong Island 占比高"未必是错，但当前是"靠 min-max 凑出来的高"，不是"靠证据支撑的高"。B.1 的保量级归一化才能区分这两种情况。

Step 4 输入仍已就绪（`P_i` 332 行 + `A_j` 332 行），但**建议先完成 B.1 再冻结 A_j**。
