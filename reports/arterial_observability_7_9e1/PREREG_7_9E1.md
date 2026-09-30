# PREREG_7_9E1 — Arterial Observability Expansion

**Step**: 7.9E-1  
**Scope**: zero-simulation, read-only, independent diagnostic crosswalk  
**Target question**: 在不替换 7.3.6A 正式 crosswalk、也不修改冻结模型的条件下，利用全部可用 TrafficFlow 路段，判断 `arterial_core = primary ∪ secondary ∪ tertiary` 是否因正式标定样本覆盖不足而处于系统性“不可观测”状态。

## 1. Frozen boundary

本步骤只读取既有文件，不修改：

- OD / population / departure profile
- MATSim network / capacity / route-choice / scoring / QSim config
- 7.3.6A final calibration crosswalk
- 7.6H W01 仿真输出
- 7.7C-0 / 7.7D / 7.9E-0 已冻结结果

本步骤不启动 MATSim、不调用 Java、不产生 v1.1，也不用于 demand scale、capacity factor、lambda 或 endpoint snapping 调参。

## 2. Fixed inputs

### 2.1 TrafficFlow

优先：`Singapore_OD_MATSim_FinalData/08_TrafficCount/TrafficFlow_Links.shp`

属性与时序补充：`Singapore_OD_MATSim_FinalData/08_TrafficCount/TrafficFlow_Data.json`

固定字段：`LinkID, RoadName, RoadCat, StartLon, StartLat, EndLon, EndLat`。

若 shapefile 可读，则优先使用其完整几何；否则退回 JSON 起终点直线几何。

### 2.2 MATSim network

`reports/matsim_network/network_links_source_copy.csv`

必需：`from_node, to_node, length_m, highway, name`。

### 2.3 MATSim node coordinates

`reports/matsim_network/network_nodes_source_copy.csv`

识别以下任一组：

- `node_id / id / node`
- `x / x_svy21_m / easting`
- `y / y_svy21_m / northing`

统一到 SVY21 / EPSG:3414。

### 2.4 Existing residual table

优先：`reports/spatial_residual_7_7c0/c0_section_table.csv`

要求：`lta_linkid, ratio_8_9, dominant_highway, length_m`。

若存在则保留：`pa / region / radial / reciprocal / has_reciprocal_pair`。

## 3. Independent diagnostic crosswalk

7.9E-1 建立 **TrafficFlow → directed MATSim representative-link diagnostic crosswalk**。

它与 7.3.6A 永久分离：

> 7.3.6A 是正式 calibration crosswalk；7.9E-1 是独立 observability diagnostic crosswalk。

不得回写、替换或覆盖 7.3.6A。

### 3.1 Candidate discovery

对每条 TrafficFlow unique `LinkID`：

1. 在 SVY21 中沿 LTA 几何折线按约 50 m 采样；短线至少 5 个采样点；最多 25 个采样点。
2. 对 MATSim directed-link midpoint 建立 KD-tree。
3. 搜索半径固定 80 m。
4. 对候选 directed links 计算几何距离、方向差、RoadName 相似度、semantic compatibility。
5. 每档次选一个最佳代表 link；完整候选保留在 `e1_crosswalk_candidates.csv`，每个 LTA LinkID 最多保留 80 条候选。

### 3.2 Direction

LTA 方向优先来自完整 geometry 首尾方向；若无 geometry，则使用 `StartLon/StartLat → EndLon/EndLat`。

MATSim 方向为 `from_node → to_node`。

方向差：`min(|a-b|, 360-|a-b|)`。

### 3.3 Functional compatibility

仅用于独立诊断：

| LTA RoadCat | compatible OSM highway |
|---|---|
| CATA | motorway |
| SLIP_ROAD | motorway_link |
| CATB | trunk / primary / secondary |
| CATC | primary / secondary / tertiary |
| CATD | secondary / tertiary / residential |
| CATE | tertiary / residential / service / unclassified |

`#N/A` 等值不参与 semantic compatibility，但仍可进入 C-tier geometry sensitivity。

### 3.4 Confidence tiers

**A — `A_STRICT_SEMANTIC_DIRECTION`**

- distance ≤ 25 m
- direction ≤ 30°
- semantic compatible

**B — `B_DIRECTION_GEOMETRY`**

- distance ≤ 50 m
- direction ≤ 30°
- 不要求 semantic compatible

**C — `C_GEOMETRY_ONLY`**

- distance ≤ 80 m
- 不要求 direction / semantic

### 3.5 Main analysis

主分析固定为 **A+B**：优先 A；无 A 时使用 B。

C 只用于 sensitivity，不进入主结论。

## 4. Observability metrics

全部 TrafficFlow unique LinkID 均进入分母，报告：

- total LTA links
- A / A+B / A+B+C matched count 与 coverage
- median / P90 distance
- median direction difference
- per-RoadCat coverage
- representative highway distribution
- residual-linked arterial-core sample

### 4.1 Hard quality thresholds

1. A+B coverage ≥ 80%
2. A+B distance P90 ≤ 50 m
3. TrafficFlow unique LinkID ≥ 1,278
4. residual sections ≥ 576
5. A+B residual-linked `arterial_core` valid sample ≥ 30

## 5. LTA functional-category audit

固定输出 `RoadCat × representative OSM highway` 矩阵。

逐 RoadCat 报告：

- traffic links
- A+B matched links
- A+B coverage
- mapped-to-arterial-core share
- dominant highway
- median / P90 distance
- median direction difference

不得事后把 CATB/CATC/CATD/CATE 强合并为某个 OSM highway。

## 6. Residual coupling

A+B representative highway 与冻结 7.7C-0 residual 按 `lta_linkid` 连接。

`residual = ratio_8_9 - 1`

主结果：

- valid residual n
- arterial-core n / non-arterial n
- mean / median residual
- Spearman(residual, arterial flag)
- η²
- unstratified permutation p
- 若存在 `pa` 或 `region`，做分层 permutation，并保留 within-stratum arterial count

不预注册 residual 方向，也不预注册 arterial 必然为高残差层。

### 6.1 Interpretation boundary

A+B arterial valid sample ≥30：说明具备进入机制审计的可观测性，不等于 capacity 错误已被证明。

A+B <30 而 C ≥30：标记 `C_ONLY_OBSERVABILITY`，主结论不得依赖 C。

A+B coverage / distance 不达门槛：标记 `OBSERVABILITY_BLOCKED`。

## 7. Sensitivity

固定三档：

- `A_STRICT`
- `A+B_MAIN`
- `A+B+C_RELAXED`

分别报告 coverage、distance、arterial-core residual sample 与 residual coupling。

## 8. Hard gates

1. prereg SHA256 一致
2. zero-simulation
3. network required fields 完整
4. node coordinate coverage 可重建 directed-link midpoint
5. directed-link ID 唯一
6. TrafficFlow unique LinkID ≥ 1,278
7. A+B coverage ≥ 80%
8. A+B P90 distance ≤ 50 m
9. residual ≥ 576 sections
10. A+B residual coupling 可计算
11. A+B arterial residual sample ≥ 30
12. provenance 完整

## 9. Decision states

- `OBSERVABILITY_PASS`
- `C_ONLY_OBSERVABILITY`
- `OBSERVABILITY_BLOCKED`

`OBSERVABILITY_PASS`：进入 `7.9E-2 arterial mechanism audit`。

`C_ONLY_OBSERVABILITY`：不得直接作 arterial mechanism attribution；优先重新审视 semantic boundary 或获取更细独立 LTA data。

`OBSERVABILITY_BLOCKED`：转向外部 LTA 数据或其他独立观测，不得继续用现有样本作强机制结论。

## 10. Frozen outputs

输出目录：`reports/arterial_observability_7_9e1/`

- `e1_crosswalk_candidates.csv`
- `e1_crosswalk_best.csv`
- `e1_section_summary.csv`
- `e1_roadcat_highway_matrix.csv`
- `e1_observability_by_roadcat.csv`
- `e1_residual_coupling.csv`
- `e1_residual_permutation.csv`
- `e1_sensitivity_summary.csv`
- `e1_checks.csv`
- `e1_input_manifest.json`
- `e1_summary.json`
- `STEP7_9E1_REPORT.md`

## 11. Permanent rules

### R-OBS-1
正式 calibration crosswalk 与 diagnostic observability crosswalk 永久分离。

### R-OBS-2
RoadCat → highway 的 semantic mapping 只能作为诊断映射，不能事后制造 arterial sample。

### R-OBS-3
主分析使用 A+B，C 只能做 sensitivity。

### R-OBS-4
任何“某道路类别是否是 residual 主场”的判断必须先证明该类别具备足够 observability。

### R-OBS-5
匹配质量必须同时报告 coverage、distance、direction。

## 12. Version boundary

本步骤不是 v1.1。

任何 network representation / capacity / QSim / demand / route-choice 修改必须另立版本、另立 prereg。
