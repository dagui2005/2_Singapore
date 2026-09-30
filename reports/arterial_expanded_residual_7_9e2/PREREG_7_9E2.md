# PREREG_7_9E2 — Expanded Diagnostic Residual Domain

**Step**: 7.9E-2  
**Scope**: zero-simulation, read-only, diagnostic only  
**Purpose**: 在不替换 7.3.6A 正式 calibration crosswalk 的前提下，将既有 TrafficFlow 观测域从正式的 `CATA + SLIP_ROAD` 靶场扩展到全部可观测 TrafficFlow LinkID，并用与 7.7C-0 / 7.3.6B 相同的 `Sim/Obs/SCALE` 口径构造诊断 residual，以判断 arterial (`primary + secondary + tertiary`) 的空间残差是否第一次具备可检验性。

## 1. Frozen boundary

本步骤不得修改：

- `Singapore_OD_MATSim_FinalData` 原始 TrafficFlow 数据；
- MATSim network / capacity / route-choice / scoring / QSim；
- 7.3.6A `final_calibration_crosswalk.csv`；
- 7.6H W01 仿真输出；
- 7.7C-0 / 7.7D / 7.9E-0 / 7.9E-1 已冻结产物；
- `v1.0` 模型及其 calibration target。

本步骤：

- 不启动 MATSim；
- 不调用 Java；
- 不产生 v1.1；
- 不重新选择 `lambda`；
- 不修改 SCALE；
- 不修改 endpoint snapping；
- 不修改 service capacity；
- 只写入新的 `reports/arterial_expanded_residual_7_9e2/`。

## 2. Fixed model quantities

### 2.1 Population scale

固定：

`SCALE = 459794 / 200000 = 2.29897`

诊断 residual **不得重新估计 SCALE**。

### 2.2 Canonical simulated section flow

遵循 7.3.6B 已冻结的 section-level metric：

`sim_section_8_9_scaled = median(HRS8-9avg of matched MATSim links) × SCALE`

即：

1. 对一个 LTA `LinkID` 的诊断 crosswalk selected MATSim links；
2. 从冻结 W01 linkstats 读取 `HRS8-9avg`；
3. 对这些 matched directed links 取 median；
4. 乘固定 `SCALE`。

不得把多条 matched MATSim links 先求和再与单条 LTA section 比较。

### 2.3 Canonical observed flow

遵循 7.1 / 7.3.6B：

- 只使用工作日；
- `HourOfDate = 8`；
- 对每个 `LinkID × Date × Hour` 先得到该日代表值；
- 再按 `LinkID × Hour` 对工作日取 median。

主比较使用：

`obs_8_9 = median weekday Volume at hour 8`

不把 07–08 与 08–09 相加后再定义 residual，因为本步骤要复刻 7.7C-0 的 `ratio_8_9`。

## 3. Diagnostic crosswalk

### 3.1 Source

读取 7.9E-1 已经冻结生成的：

`reports/arterial_observability_7_9e1/e1_crosswalk_candidates.csv`

以及：

`reports/arterial_observability_7_9e1/e1_crosswalk_best.csv`

本步骤不重新设计几何匹配算法，不再次搜索空间候选。

### 3.2 Selection hierarchy

对每个 LTA `LinkID`：

**A+B 主分析：**

- 如果存在 A candidate，只使用该 section 的全部 A candidates；
- 如果不存在 A，则使用全部 B candidates；
- C 不进入主分析。

**A-only 敏感性：**

- 仅使用 A candidates。

**A+B+C relaxed 敏感性：**

- A 存在 → A；
- 否则 B 存在 → B；
- 否则 C。

因此一个 LTA section 对应一个 tier 内的 directed MATSim link 集合，允许 1:N，但不得跨 tier 混合。

### 3.3 Representative highway

为便于定义 `arterial_core`：

- 在 selected tier 内选最优代表 link；
- 排序优先级固定为：geometry distance → direction difference → semantic compatibility → name similarity → MATSim link ID；
- 其 `highway` 作为 section-level `diagnostic_highway`。

同时保留 selected links 的完整 `highway` 集合。

## 4. Diagnostic residual

对每一个成功匹配、且 `obs_8_9 > 0` 的 TrafficFlow Link：

`diagnostic_ratio_8_9 = sim_section_8_9_scaled / obs_8_9`

`diagnostic_residual_8_9 = diagnostic_ratio_8_9 - 1`

这是诊断指标，不得替换 7.7C-0 正式 residual 表。

## 5. Expanded domain

主诊断域为 TrafficFlow 的全部 unique `LinkID`，但只有：

- 能够由 7.9E-1 A+B 匹配；
- 能够在 W01 linkstats 中找到模拟值；
- `obs_8_9 > 0`

的 section 才能进入 residual analysis。

正式 RoadCat：

`CATA, CATB, CATC, CATD, CATE, SLIP_ROAD`

`#N/A` 等其他值保留在 coverage 统计，但不进入主 RoadCat semantic interpretation。

## 6. Arterial definition

### 6.1 OSM structural arterial

固定：

`arterial_core = primary ∪ secondary ∪ tertiary`

不得把 `trunk`、`primary_link`、`secondary_link`、`tertiary_link` 等辅助类别事后并入 arterial_core。

### 6.2 LTA functional category

同时保留 LTA `RoadCat`，不声称：

`CATB/CATC/CATD/CATE == primary/secondary/tertiary`

7.9E-1 已经显示 RoadCat 到 OSM highway 是多对多关系，因此本步骤同时报告 LTA functional view 与 OSM structural view。

## 7. Main tests

### 7.1 Arterial vs non-arterial

主分析对 A+B residual：

- n；
- mean；
- median；
- P10 / P90；
- Spearman(residual, arterial_flag)；
- η²；
- absolute mean difference。

### 7.2 RoadCat-stratified permutation

由于 expanded domain 中 LTA `RoadCat` 是独立观测分类，主置换检验按 RoadCat 分层：

- 在每个 RoadCat 内固定 arterial / non-arterial 样本数；
- 随机打乱 arterial label；
- 计算加权 absolute mean difference；
- `N_PERM = 2000`；
- seed = `79201`。

同时输出 unstratified permutation：

- `N_PERM = 2000`；
- seed = `79200`。

## 8. Formal-domain bridge audit

将 expanded diagnostic residual 与冻结的：

`reports/spatial_residual_7_7c0/c0_section_table.csv`

按 `lta_linkid` 做 overlap bridge。

报告：

- overlap n；
- Pearson / Spearman；
- mean bias；
- MAE；
- RMSE。

该 bridge 仅用于方法一致性诊断，不允许把 expanded residual 回写为正式 target。

## 9. Hard gates

1. prereg SHA256 与运行时文件一致；
2. zero-simulation；
3. 固定 `SCALE = 2.29897`；
4. TrafficFlow unique LinkID ≥ 1,278；
5. 7.9E-1 A+B candidate 文件存在并可读取；
6. W01 linkstats `LINK/HRS8-9avg` 可读取且 LINK 唯一；
7. A+B section simulated coverage ≥ 80%；
8. A+B valid residual sample ≥ 30；
9. A+B `arterial_core` residual sample ≥ 30；
10. 输出全部落在独立目录；
11. formal-domain bridge overlap ≥ 500（正式 residual 为 576 时）；
12. provenance 完整。

### Gate 9 的含义

Gate 9 只表示 arterial residual 已经具备最小统计可观测性，不表示 arterial 已被证明是 residual 主场。

## 10. Next-step decision rule

当 Gate 9 PASS 后，才允许根据统计结果进行机制分叉：

### `ARTERIAL_COUPLING_SIGNAL`

满足：

- RoadCat-stratified permutation `p < 0.05`；
- 同时报告效应方向、绝对均值差、η²。

这表示 expanded diagnostic domain 中存在可检验的 arterial residual coupling signal。

下一步：`7.9E-3 arterial mechanism audit`。

不得直接等同于 capacity error。

### `NO_ARTERIAL_COUPLING_SIGNAL`

若 RoadCat-stratified permutation `p >= 0.05`，记录：

> 在当前 expanded diagnostic domain 与当前 W01 realization 下，未观察到足以支持 arterial residual coupling 的统计证据。

下一步转向 service / endpoint / other structural mechanism。

### `EXPANDED_DOMAIN_BLOCKED`

任何 hard gate 不满足。不得继续对 arterial residual 作强机制解释。

## 11. Sensitivity requirements

固定输出：

- A-only；
- A+B main；
- A+B+C relaxed。

三档报告 coverage、valid residual n、arterial n、residual mean、stratified permutation p。

敏感性只能回答结论是否依赖 crosswalk 严格程度，不得据此回改 A/B/C 阈值。

## 12. Output

输出目录：

`reports/arterial_expanded_residual_7_9e2/`

至少：

- `e2_section_residual_main.csv`
- `e2_section_residual_all_tiers.csv`
- `e2_roadcat_highway_matrix.csv`
- `e2_roadcat_summary.csv`
- `e2_arterial_coupling.csv`
- `e2_permutation.csv`
- `e2_sensitivity_summary.csv`
- `e2_formal_bridge.csv`
- `e2_checks.csv`
- `e2_input_manifest.json`
- `e2_summary.json`
- `STEP7_9E2_REPORT.md`

## 13. Permanent rules

### R-RES-1

正式 calibration residual 与 expanded diagnostic residual 永久分离。

### R-RES-2

expanded residual 只能用于结构归因审计，不得进入 v1.0 calibration target。

### R-RES-3

section-level simulation flow 必须使用 matched directed links 的 median，再乘冻结 SCALE。

### R-RES-4

Arterial coupling 必须同时控制 / 报告 LTA RoadCat composition。

### R-RES-5

LTA functional road class 与 OSM structural highway 永久分开表述。

### R-RES-6

只有通过 observability gate 的道路层才允许进入 mechanism attribution。

## 14. Version boundary

7.9E-2 不产生 v1.1。

任何 network / capacity / demand / route-choice 修改必须另立版本并重新预注册。
