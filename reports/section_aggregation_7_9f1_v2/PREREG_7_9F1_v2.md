# PREREG_7_9F1_v2 — Section Aggregation Sensitivity Audit

**Step**: 7.9F-1 v2  
**Status**: formal rerun protocol after F-1 R0 input-contract resolution  
**Scope**: zero-simulation, read-only, diagnostic-only

## 1. Purpose

承接 7.9F-0 v2 与 7.9E-2 已发现的 `sim_8_9_median_raw == 0` 断面，检验 section-level matched-link aggregation rule 是否系统性影响 residual，尤其检验 median 是否把“部分匹配边有流量、部分匹配边为 0”的断面压成零，并判断该效应在 corridor diagnostic proxy 层是否仍然存在。

本版本只修正 F-1 R0 已暴露的输入路径与执行契约，不修改 aggregation 定义、阈值、判据或解释边界。

## 2. Frozen boundary

不得修改：

- TrafficFlow 原始数据；
- E1 diagnostic crosswalk；
- E2 expanded residual；
- MATSim network / capacity / route-choice / scoring / QSim；
- 7.3.6A calibration target；
- 7.6H W01 输出；
- v1.0 / v1.1。

本步骤：

- 不启动 MATSim；
- 不调用 Java；
- 不修改 network / capacity / lanes / speed；
- 不重新估计 SCALE；
- 不把任何替代 aggregation 回写 E2 或正式 calibration target；
- 只写入 `reports/section_aggregation_7_9f1_v2/`。

## 3. Resolved input contract

### 3.1 TrafficFlow

`Singapore_OD_MATSim_FinalData/08_TrafficCount/TrafficFlow_Data.json`

固定：

- 工作日；
- `HourOfDate = 8`；
- 同一 `LinkID × Date` 先取该日代表值；
- 再按 `LinkID` 对工作日取 median；
- 得到 `obs_8_9`。

### 3.2 E1 candidates

`reports/arterial_observability_7_9e1/e1_crosswalk_candidates.csv`

不重新搜索空间候选。

固定只允许：

- `A_STRICT_SEMANTIC_DIRECTION`；
- `B_DIRECTION_GEOMETRY`。

对每个 LinkID：

- 若存在 A，则使用全部 A candidates；
- 否则使用全部 B candidates；
- C 不进入 F-1。

同一 selected tier 内去重 `matsim_link_id`，保留全部 selected directed links。

### 3.3 W01 linkstats

**F-1 v2 固定真实路径：**

`matsim_final_7_6h/outputs/W01_rc_min/ITERS/it.19/`

本版本不再把 `reports/` 前缀作为解析路径。

必需：

`LINK, HRS8-9avg`

### 3.4 E2 canonical residual

`reports/arterial_expanded_residual_7_9e2/e2_section_residual_main.csv`

仅用于复现检查，不替换 E2。

## 4. Fixed aggregation methods

四种方法必须使用完全相同的 selected matched-link set 和同一 W01 `HRS8-9avg`：

1. `CANONICAL_MEDIAN`
   - all selected HRS8-9avg 的 median；
2. `POSITIVE_MEDIAN`
   - 仅正流量 matched edges 的 median；
   - 若不存在正流量 edge，则为 0；
3. `MEAN`
   - all selected HRS8-9avg 的 mean；
4. `MAX`
   - all selected HRS8-9avg 的 max。

统一：

`SCALE = 459794 / 200000 = 2.29897`

`diagnostic_ratio = sim_scaled / obs_8_9`

`diagnostic_residual = diagnostic_ratio - 1`

## 5. Zero-median diagnostic

固定识别 canonical：

`CANONICAL_MEDIAN__sim_scaled == 0`

并区分：

- 所有 matched edges 均为 0；
- 存在正流量 edge，但 median=0。

同时报告：

- count；
- observed-flow share；
- `raw_mean > 0` count；
- 四种 aggregation 的 observed-weighted residual；
- 四种 aggregation 的 simulated-flow-weighted residual。

## 6. Highway-grade comparison

固定使用 E2 `diagnostic_highway`：

`motorway, motorway_link, trunk, primary, secondary, tertiary`

每种 aggregation × highway 报告：

- n；
- mean / median residual；
- P10 / P90；
- observed-flow-weighted residual；
- simulated-flow-weighted residual；
- zero-section count；
- negative share；
- positive share。

不得改变：

`arterial_core = primary ∪ secondary ∪ tertiary`

## 7. Corridor diagnostic proxy

定义：

`corridor_id = normalized(RoadName)`

仅保留：

- `RoadName` 非空；
- 同一 corridor 至少 2 个 valid sections。

对于每种 aggregation：

`obs_corridor = Σ obs_8_9`

`sim_corridor = Σ sim_scaled`

`corridor_ratio = sim_corridor / obs_corridor`

`corridor_residual = corridor_ratio - 1`

corridor 仅为 diagnostic proxy，不等同真实 corridor。

## 8. Pairwise robustness

固定比较：

1. POSITIVE_MEDIAN vs CANONICAL_MEDIAN；
2. MEAN vs CANONICAL_MEDIAN；
3. MAX vs CANONICAL_MEDIAN；
4. corridor-level sign agreement。

报告：

- n；
- Pearson；
- Spearman；
- mean residual delta；
- MAE residual delta；
- section/corridor sign-change share。

不定义“最佳 aggregation”。

## 9. Formal hard gates

原 F-1 的 12 个 hard-gate categories 原样保留：

1. prereg SHA256 MATCH；
2. AST zero-simulation PASS；
3. TrafficFlow unique LinkID ≥ 1,278；
4. E1 candidate file complete；
5. W01 `LINK/HRS8-9avg` complete and unique；
6. canonical selected-link coverage ≥95%；
7. valid observed section n ≥500；
8. four aggregation outputs each valid for ≥95% of canonical valid sections；
9. core six highway classes each n≥20；
10. canonical median reproduces E2 `sim_8_9_median_raw` with max absolute delta = 0；
11. corridor proxy ≥30 valid corridors；
12. output isolation + provenance complete。

实现中 Gate 8 展开为四个 method-level subchecks，因此检查表共有 15 行，但 formal category 仍为 12。

## 10. Protocol-resolution supplementary gates

另外固定报告三个输入解析 supplementary checks：

- `F1V2.13_W01_RUNTIME_PATH`：resolved W01 path 必须为 `matsim_final_7_6h/outputs/W01_rc_min/ITERS/it.19`；
- `F1V2.14_E2_CANONICAL_REPRODUCTION`：selected set + W01 median 与 E2 main `sim_8_9_scaled` 最大绝对差 ≤1e-12；
- `F1V2.15_R0_ARTIFACT_ISOLATION`：R0 目录不得出现任何 `f1v2_*` 产物。

Supplementary checks 不改变 formal decision。

## 11. Decision boundary

### `AGGREGATION_AUDIT_READY`

12 个 formal hard-gate categories 全 PASS。

仅表示输入、可观测性与计算链满足协议要求。

### `AGGREGATION_AUDIT_BLOCKED`

任一 formal category FAIL。

不得据此作 aggregation mechanism 强结论。

## 12. Output

固定目录：

`reports/section_aggregation_7_9f1_v2/`

至少：

- `f1v2_section_aggregation_long.csv`
- `f1v2_section_summary.csv`
- `f1v2_highway_aggregation_summary.csv`
- `f1v2_zero_median_audit.csv`
- `f1v2_corridor_aggregation.csv`
- `f1v2_robustness_pairwise.csv`
- `f1v2_selected_links.csv`
- `f1v2_input_resolution.csv`
- `f1v2_checks.csv`
- `f1v2_input_manifest.json`
- `f1v2_summary.json`
- `STEP7_9F1_v2_REPORT.md`

## 13. Permanent rules

### R-AGG-1
E2 canonical median 永久保留；替代 aggregation 只能作 diagnostic sensitivity。

### R-AGG-2
四种 aggregation 必须使用完全相同的 selected matched-link set 与同一 W01 HRS8-9avg。

### R-AGG-3
positive-median 只用于检验 zero-flow edge 对 median 的影响，不得重新解释为新的 calibration metric。

### R-AGG-4
section-level 与 corridor-level aggregation 永久分开报告。

### R-AGG-5
corridor_id=normalized(RoadName) 仅为 diagnostic proxy，不等于真实 corridor。

### R-AGG-6
任何 aggregation 结果不得回写 7.3.6A / E2 / v1.0。

### R-AGG-7
本步骤零仿真、只读，不产生 v1.1。

### R-AGG-8
F-1 v2 的 W01 linkstats 解析路径固定为项目根 `matsim_final_7_6h/outputs/W01_rc_min/ITERS/it.19`。

### R-AGG-9
F-1 canonical selected-link set 必须与 E2 main 的 diagnostic median 做显式复现校验。

### R-AGG-10
R0 与 v2 输出目录物理隔离，R0 不得被 v2 覆盖。

## 14. Version boundary

F-1 v2 不产生 v1.1。

任何 aggregation、network、capacity、demand、route-choice 或 target 定义修改必须另立版本并重新预注册。
