# PREREG_7_9F0_v2 — Highway Grade × Capacity/Speed Structural Audit

**Step**: 7.9F-0 v2  
**Status**: formal rerun protocol after R0 input-contract resolution  
**Scope**: zero-simulation, read-only, structural diagnostic

## 1. Purpose

承接 7.9E-2 的道路等级 residual gradient，检查 `highway × lanes × capacity × speed` 的网络表达是否存在系统性结构差异，以及 residual 梯度是否主要表现为 highway grade 的组间差异、lanes 表达及默认回填、capacity-per-lane 参数表达、freespeed 层级，或 observed/simulated flow 相对于 capacity 的结构关系。

本版本仅修正 7.9F-0-R0 已暴露的输入 schema 契约，不修改分析问题、统计阈值或判据。

## 2. Frozen boundary

不得修改：原始 TrafficFlow；MATSim network XML；network source CSV；7.3.6A calibration target/crosswalk；7.6H W01 输出；7.7C-0 / 7.9E-0 / 7.9E-1 / 7.9E-2 产物；v1.0。

本步骤不启动 MATSim、不调用 Java、不修改 network/capacity/lanes/speed、不重新估计 SCALE、不产生 v1.1。

## 3. Resolved input contract

### 3.1 Structural/source network

`reports/matsim_network/network_links_source_copy.csv`

负责提供：`from_node, to_node, length_m, highway, lanes`。

本文件不要求 `capacity` 字段。

### 3.2 Actual MATSim runtime parameters

冻结运行网络：`reports/matsim_network/network.xml.gz`

从 XML 读取：`id, length, freespeed, capacity, permlanes`。

其中 XML `capacity / permlanes` 为 actual capacity-per-lane。F-0 中不得依据 canonical lookup 自行生成 capacity 后再审计。

### 3.3 Expanded residual

正式使用：`reports/arterial_expanded_residual_7_9e2/e2_section_residual_all_tiers.csv`

固定选择：`tier_output == A+B_MAIN`，并读取 `representative_matsim_link_id`。

R0 已验证该切片与 `e2_section_residual_main.csv` 的 LinkID 域一致且 residual 数值差为 0。

## 4. Frozen class definitions

核心 highway：`motorway, motorway_link, trunk, primary, secondary, tertiary`。

`arterial_core = primary ∪ secondary ∪ tertiary`，但本步骤不以 arterial 聚合均值作判据。

## 5. Capacity-per-lane reference

沿用冻结网络构建规则：

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

报告 actual capacity/lane 的 median/P10/P90、unique values、lookup-match（≤1%）、relative difference，以及 raw lanes 缺失/默认回填与 XML permlanes 分布。

lookup-match 只能证明当前参数表达符合既定 lookup，不能证明 lookup 数值本身正确。

## 6. Speed expression audit

使用 XML `freespeed × 3.6` 得到 km/h。报告每个 highway 的 median、P10、P90、mean、unique count 及其与 residual 的关系。不预设速度值正确与否。

## 7. Capacity adequacy proxies

仅作为结构诊断代理：

`obs_to_capacity_proxy = obs_8_9 / XML_capacity`

`sim_to_capacity_proxy = sim_8_9_scaled / XML_capacity`

不称为 realized v/c，不修改 QSim capacity，也不进入 calibration target。

## 8. Residual-grade analysis

重点链：`trunk → secondary → tertiary`。报告 n、mean/median、P10/P90、observed-flow-weighted residual、simulated-flow-weighted residual、lanes、XML permlanes、capacity、actual capacity/lane、speed、obs/sim capacity proxies。

## 9. Within-grade analysis

同时计算：

1. raw between-grade Spearman；
2. grade-demeaned Pearson；
3. grade-demeaned Spearman。

grade-demeaned 仅用于描述同一 highway 级别内部关系，不作因果解释。

## 10. Zero-median robustness carried from R0

固定报告：83 个 `sim_8_9_median_raw == 0` 的断面数、其 observed-flow share、其中 `mean_raw > 0` 的数量、剔除后的 observed-weighted residual，以及 full-domain 与 sim-weighted residual 对照。

该项不改变 E2 residual 定义，不回写正式 target。

## 11. Hard gates

沿用 R0 原定 12 个 formal hard gates：

1. prereg SHA256 MATCH；
2. AST zero-simulation audit PASS；
3. network source structural fields complete；
4. E2 residual fields complete；
5. representative-link join coverage ≥95%；
6. valid residual n ≥500；
7. six core highway classes each n≥20；
8. capacity/lanes effective coverage ≥95%；
9. speed coverage ≥90%；
10. observed/simulated capacity-proxy coverage ≥80%；
11. output isolation；
12. provenance completeness。

另外报告三个 protocol-resolution supplementary gates：

- F0V2.13：capacity/permlanes/freespeed 来自冻结 network.xml.gz；
- F0V2.14：representative link 来自 E2 A+B_MAIN slice；
- F0V2.15：A+B_MAIN 与 E2 main 的 LinkID 域一致且 residual max|Δ|=0。

## 12. Decision boundary

`GRADE_CAPACITY_AUDIT_READY`：12 个 formal hard gates 全 PASS。仅表示输入、可观测性与计算链满足要求，不表示 capacity 参数已被证明正确。

`GRADE_CAPACITY_AUDIT_BLOCKED`：任一 formal hard gate FAIL；不得据此作强机制结论。

## 13. Output isolation

v2 固定输出：`reports/highway_grade_capacity_7_9f0_v2/`。

R0 输出目录 `reports/highway_grade_capacity_7_9f0/` 不得覆盖。

## 14. Output files

- `f0v2_link_diagnostic.csv`
- `f0v2_grade_summary.csv`
- `f0v2_capacity_lookup_audit.csv`
- `f0v2_grade_trend.csv`
- `f0v2_residual_relationships.csv`
- `f0v2_correlations.csv`
- `f0v2_zero_median_robustness.csv`
- `f0v2_checks.csv`
- `f0v2_input_resolution.csv`
- `f0v2_input_manifest.json`
- `f0v2_summary.json`
- `STEP7_9F0_v2_REPORT.md`

## 15. Permanent rules

**R-GRADE-1** expanded residual 永远是 diagnostic，不进入 calibration target。  
**R-GRADE-2** highway grade 与 LTA RoadCat 永久分开。  
**R-GRADE-3** lookup-match 只证明当前参数表达，不证明参数本身正确。  
**R-GRADE-4** raw between-grade 与 within-grade 相关必须同时报告。  
**R-GRADE-5** capacity proxies 只作结构诊断，不称为 realized v/c。  
**R-GRADE-6** 本步骤零仿真、只读，不产生 v1.1。  
**R-GRADE-7** 实际 MATSim capacity/permlanes/freespeed 的运行期来源固定为冻结 network.xml.gz。  
**R-GRADE-8** E2 representative link 唯一来源固定为 all_tiers 的 A+B_MAIN slice。  
**R-GRADE-9** R0 schema mismatch 不通过静默修改原 prereg 消除；v2 单独备案。  
**R-GRADE-10** R0 与 v2 产物物理隔离。
