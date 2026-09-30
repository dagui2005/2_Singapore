# PREREG_7_9F1 — Section Aggregation Sensitivity Audit

**Step**: 7.9F-1  
**Scope**: zero-simulation, read-only, diagnostic-only  
**Purpose**: 承接 7.9F-0 v2 与 7.9E-2 已发现的 83 个 `sim_8_9_median_raw == 0` 断面，检验 section-level matched-link aggregation rule 是否系统性影响 residual，尤其检验 median 是否将“部分匹配边有流量、部分匹配边为 0”的断面压成零，并判断该效应在 corridor 层是否仍然存在。

## 1. Frozen boundary

本步骤不得修改：

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
- 不把任何替代聚合结果回写 E2 或正式 calibration target；
- 只写入 `reports/section_aggregation_7_9f1/`。

## 2. Fixed inputs

### 2.1 TrafficFlow

`Singapore_OD_MATSim_FinalData/08_TrafficCount/TrafficFlow_Data.json`

固定观测口径：

- 工作日；
- `HourOfDate = 8`；
- 同一 `LinkID × Date` 先取该日代表值；
- 再按 `LinkID` 对工作日取 median；
- 得到 `obs_8_9`。

### 2.2 E1 diagnostic crosswalk candidates

`reports/arterial_observability_7_9e1/e1_crosswalk_candidates.csv`

F-1 不重新搜索空间候选，不改变 E1 的 A/B/C 规则。

### 2.3 W01 linkstats

冻结 W01：

`reports/matsim_final_7_6h/outputs/W01_rc_min/ITERS/it.19/`

必需：`LINK`, `HRS8-9avg`。

### 2.4 E2 canonical section residual

`reports/arterial_expanded_residual_7_9e2/e2_section_residual_main.csv`

用于验证 F-1 canonical median 与 E2 一致，不替换 E2。

## 3. Fixed selected matched-link set

严格复刻 7.9E-2 A+B main 的 selection hierarchy：

- 对每个 TrafficFlow `LinkID`，若存在 A candidates，只使用该 LinkID 的全部 A candidates；
- 若不存在 A，则使用全部 B candidates；
- C 不进入 canonical set。

在同一 selected tier 内：

- 去重 `matsim_link_id`；
- 保留全部 selected directed MATSim links；
- 不按距离重新截断候选集；
- 不重新定义 representative link。

该 selected link set 是四种 aggregation method 的唯一共同输入。

## 4. Fixed aggregation methods

对一个 TrafficFlow section 的 selected matched directed MATSim links，读取冻结 W01 `HRS8-9avg`：

### A. CANONICAL_MEDIAN

`sim_raw = median(all selected HRS8-9avg)`

这是 7.9E-2 / 7.3.6B 的 canonical metric，仅用于复现与对比。

### B. POSITIVE_MEDIAN

`sim_raw = median(HRS8-9avg where HRS8-9avg > 0)`；若一个 section 没有任何正流量 matched link，则 `sim_raw = 0`。

该量专门检验 zero-flow matched edges 是否造成 median collapse。

### C. MEAN

`sim_raw = mean(all selected HRS8-9avg)`。

### D. MAX

`sim_raw = max(all selected HRS8-9avg)`。

四种方法全部乘同一个冻结：

`SCALE = 459794 / 200000 = 2.29897`

随后统一计算：

`diagnostic_ratio = sim_scaled / obs_8_9`

`diagnostic_residual = diagnostic_ratio - 1`

除 positive-median 的“无正流量时为 0”定义外，不允许任何方法使用额外筛选。

## 5. Section-level outputs

每个 LinkID、每种 aggregation method 固定输出：

- matched edge count；
- zero-flow edge count；
- positive-flow edge count；
- raw mean；
- raw median；
- raw max；
- raw positive-median；
- scaled simulated flow；
- `obs_8_9`；
- ratio；
- residual；
- diagnostic highway；
- RoadCat；
- RoadName。

特别报告：

- zero-median section count；
- zero-median observed-flow share；
- zero-median 且 mean_raw > 0 的数量；
- 每种 aggregation 相对 canonical median 的 residual delta。

## 6. Highway-grade comparison

固定使用 E2 `diagnostic_highway`：

`motorway, motorway_link, trunk, primary, secondary, tertiary`

每种 aggregation × highway 输出：

- n；
- mean / median residual；
- P10 / P90；
- observed-flow-weighted residual；
- simulated-flow-weighted residual；
- zero-residual / negative-residual / positive-residual shares；
- zero-section count。

不得改变 `arterial_core = primary ∪ secondary ∪ tertiary` 定义。

## 7. Corridor-level aggregation

为避免把 section-level 极值直接当作 corridor 结论，固定构造 corridor proxy：

`corridor_id = normalized(RoadName)`

仅保留 `RoadName` 非空且同一 corridor 至少包含 **2 个 valid sections** 的 corridor。

对每个 corridor × aggregation：

`obs_corridor = Σ obs_8_9`

`sim_corridor = Σ sim_scaled`

`corridor_ratio = sim_corridor / obs_corridor`

`corridor_residual = corridor_ratio - 1`

同时报告：

- corridor n；
- sections per corridor；
- mean / median corridor residual；
- observed-flow-weighted corridor residual；
- sign agreement with canonical median；
- corridor residual delta relative to canonical.

该 corridor 是 diagnostic proxy，不宣称等同真实交通走廊。

## 8. Prespecified robustness comparisons

固定输出四组 pairwise comparison：

1. positive-median vs canonical median；
2. mean vs canonical median；
3. max vs canonical median；
4. corridor-level sign agreement。

报告：

- Pearson / Spearman residual correlation；
- mean residual delta；
- MAE of residual delta；
- proportion of sections whose residual sign changes；
- proportion of corridors whose residual sign changes。

不定义“最佳聚合方法”。

## 9. Main falsification questions

### Q1
83 个 canonical zero-median sections 是否主要来自：

`zero matched edges + positive matched edges`

的混合？

### Q2
把 zero-flow matched edges 排除后，section residual 是否发生系统性变化？

### Q3
这种变化是否仍存在于 corridor-level aggregate？

### Q4
trunk / secondary / tertiary 的 residual gradient 是否在替代 aggregation 下保持，还是主要由 canonical median 制造？

这些都是诊断问题，不预设答案。

## 10. Hard gates

1. prereg SHA256 MATCH；
2. AST zero-simulation PASS；
3. TrafficFlow unique LinkID ≥ 1,278；
4. E1 candidate file complete；
5. W01 `LINK/HRS8-9avg` complete and unique；
6. canonical selected link set coverage ≥95%；
7. valid observed section n ≥500；
8. four aggregation outputs each valid for ≥95% of canonical valid sections；
9. core six highway classes each n≥20；
10. canonical median reproduces E2 `sim_8_9_median_raw` with max absolute delta = 0；
11. corridor proxy has ≥30 valid corridors；
12. output isolation + provenance complete。

## 11. Output

`reports/section_aggregation_7_9f1/`

- `f1_section_aggregation_long.csv`
- `f1_section_summary.csv`
- `f1_highway_aggregation_summary.csv`
- `f1_zero_median_audit.csv`
- `f1_corridor_aggregation.csv`
- `f1_robustness_pairwise.csv`
- `f1_checks.csv`
- `f1_input_manifest.json`
- `f1_summary.json`
- `STEP7_9F1_REPORT.md`

## 12. Decision boundary

### `AGGREGATION_AUDIT_READY`

所有 hard gates PASS。允许进行下一阶段机制解释。

### `AGGREGATION_AUDIT_BLOCKED`

任一 hard gate FAIL。不得据此作 aggregation mechanism 强结论。

本步骤不自动选择 median / positive-median / mean / max 中的任一方法作为替代模型。

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
