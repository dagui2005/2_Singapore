# PREREG_7_9F0 — Highway Grade × Capacity/Speed Structural Audit

**Step**: 7.9F-0  
**Scope**: zero-simulation, read-only, structural diagnostic  
**Purpose**: 承接 7.9E-2 的道路等级残差梯度，检查 `highway × lanes × capacity × speed` 的网络表达是否存在可描述的系统性结构差异，并判断残差梯度是否主要表现为道路等级之间的固定参数层级、车道数变化，或模拟/容量代理之间的异常关系。

## 1. Frozen boundary

本步骤不得修改：

- `Singapore_OD_MATSim_FinalData` 原始观测；
- MATSim network / capacity / route-choice / scoring / QSim；
- 7.3.6A 正式 calibration target；
- 7.6H W01 仿真输出；
- 7.7C-0 / 7.9E-0 / 7.9E-1 / 7.9E-2 已冻结产物；
- `v1.0` 模型。

本步骤不启动 MATSim、不调用 Java、不修改 network/capacity/lanes/speed、不重新估计 SCALE，只写入独立的 `reports/highway_grade_capacity_7_9f0/`。

## 2. Fixed inputs

### 2.1 MATSim network

`reports/matsim_network/network_links_source_copy.csv`

必需：`from_node, to_node, length_m, highway, lanes, capacity`。允许 `matsim_link_id, speed_kmh, travel_time_s, name`。

若不存在 `matsim_link_id`，按冻结网络规则重建：`e{from_node}_{to_node}`。

### 2.2 Expanded diagnostic residual

使用 7.9E-2 已冻结产物：

`reports/arterial_expanded_residual_7_9e2/e2_section_residual_main.csv`

使用字段：`LinkID, RoadCat, obs_8_9, sim_8_9_scaled, diagnostic_ratio_8_9, diagnostic_residual_8_9, diagnostic_highway, representative_matsim_link_id, valid_residual`。

该 residual 永远属于 expanded diagnostic domain，不回写 7.3.6A。

## 3. Frozen class definitions

核心 highway classes：`motorway, motorway_link, trunk, primary, secondary, tertiary`。

`arterial_core = primary ∪ secondary ∪ tertiary` 继续保留，但本步骤主要分析 highway grade，不以 arterial 聚合均值作判据。

## 4. Capacity expression audit

来源于冻结网络构建规则的 capacity-per-lane reference：

| highway | canonical capacity/lane (veh/h) |
|---|---:|
| motorway | 1900 |
| motorway_link | 1700 |
| trunk | 1800 |
| trunk_link | 1600 |
| primary | 1500 |
| primary_link | 1300 |
| secondary | 1200 |
| secondary_link | 1100 |
| tertiary | 900 |
| tertiary_link | 800 |
| residential | 700 |
| service | 400 |
| unclassified | 600 |

实际：`capacity_per_lane = capacity / lanes`。

报告 median/P10/P90、unique values、lookup-match（容差 1%）、相对偏差、lanes 分布、`lanes == frozen class default` share。

lookup-match 只能证明当前网络采用了该表达，不证明参数正确。

## 5. Speed expression audit

不预设速度正确值。按 highway 报告 median/P10/P90、mean、unique speed count，以及 speed 与 residual/lanes/capacity 的关系。

## 6. Capacity adequacy proxies

仅作为诊断代理，不称为 realized v/c：

`obs_to_capacity_proxy = obs_8_9 / capacity`

`sim_to_capacity_proxy = sim_8_9_scaled / capacity`

不修改 QSim capacity，也不作为新的 calibration target。

## 7. Residual-grade analysis

重点链：`trunk → secondary → tertiary`。

报告每类 n、mean/median、P10/P90、observed-flow-weighted residual、simulated-flow-weighted residual，以及 residual 与 lanes/speed/capacity proxies 的关系。

## 8. Between-grade vs within-grade

同时计算：

1. raw between-grade Spearman；
2. grade-demeaned Pearson；
3. grade-demeaned Spearman。

grade-demeaned 仅用于描述同一级别内部的关系。raw correlation 可能被 highway class 本身驱动；within-grade 更接近检验同一级别内部的参数变化是否与 residual 共同变化。

## 9. Hard gates

1. prereg SHA256 运行时 MATCH；
2. AST zero-simulation audit PASS；
3. network 必需字段完整；
4. E2 residual 字段完整；
5. representative link join coverage ≥ 95%；
6. valid residual n ≥ 500；
7. 六个核心 highway class 均有 ≥ 20 个 valid residual sections；
8. capacity / lanes 覆盖 ≥ 95%；
9. speed 覆盖 ≥ 90%；
10. observed/simulated capacity proxies 覆盖 ≥ 80%；
11. 输出全部位于独立 F-0 目录；
12. provenance manifest 完整。

## 10. Output

`reports/highway_grade_capacity_7_9f0/`

至少：

- `f0_link_diagnostic.csv`
- `f0_grade_summary.csv`
- `f0_capacity_lookup_audit.csv`
- `f0_grade_trend.csv`
- `f0_residual_relationships.csv`
- `f0_correlations.csv`
- `f0_checks.csv`
- `f0_input_manifest.json`
- `f0_summary.json`
- `STEP7_9F0_REPORT.md`

## 11. Decision boundary

### `GRADE_CAPACITY_AUDIT_READY`

所有 hard gates PASS。允许进入下一步机制解释。

### `GRADE_CAPACITY_AUDIT_BLOCKED`

任一 hard gate FAIL。不得依据本步骤对 grade/capacity 关系作强机制结论。

真正的 capacity 参数修改必须另立版本、重新预注册，不得修改 v1.0。

## 12. Permanent rules

### R-GRADE-1
7.9E-2 expanded residual 永远是 diagnostic，不进入 calibration target。

### R-GRADE-2
highway grade 与 LTA RoadCat 永久分开，不互相替代。

### R-GRADE-3
capacity-per-lane lookup-match 只能证明参数表达，不证明参数正确性。

### R-GRADE-4
raw between-grade correlation 与 within-grade correlation 必须同时报告。

### R-GRADE-5
observed/simulated capacity proxy 只作结构诊断，不称为 realized v/c。

### R-GRADE-6
本步骤零仿真、只读，不产生 v1.1。
