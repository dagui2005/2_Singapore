# PREREG_7_9F2_v2.1 — Direction-Relaxed Candidate & Local Single-Link Capture Diagnostic

**Step**: 7.9F-2 v2.1  
**Scope**: zero-simulation, read-only, diagnostic-only  
**Purpose**: 专门处理 F-2 v2 中 Q2/Q4 的可解释性问题。Q2 使用 E1 已保存的完整 A/B/C candidate evidence，避免在方向阈值已筛选的 A/B selected set 上循环检验方向性；Q4 改为 single-link local capture diagnostic，避免将多个链路求和后与单一 TrafficFlow section observation 直接比较。

## 1. Frozen boundary

不得修改 TrafficFlow、E1/E2、MATSim network/capacity/lanes/speed、route-choice/scoring/QSim、7.3.6A、7.6H、F-0/F-1/F-2 v2、v1.0/v1.1。

本步骤不启动 MATSim、不调用 Java、不重跑 E1 candidate search、不重新估计 SCALE、不回写 E1/E2；只写入：

`reports/secondary_tertiary_residual_7_9f2_v2_1/`

## 2. Frozen inputs

### 2.1 E2 frozen residual target

`reports/arterial_expanded_residual_7_9e2/e2_section_residual_main.csv`

使用：`LinkID, obs_8_9, sim_8_9_scaled, diagnostic_residual_8_9, diagnostic_highway, valid_residual`。

目标域固定：

`diagnostic_highway ∈ {secondary, tertiary}`、`valid_residual=True`、`obs_8_9>0`。

v2.1 不重算 E2 residual。

### 2.2 E1 stored candidate evidence

`reports/arterial_observability_7_9e1/e1_crosswalk_candidates.csv`

Q2 使用 E1 已保存的 A/B/C 全部 candidate rows；不重新搜索空间、不重新赋 tier、不修改 E1 的 search radius / sampling / candidate cap。

### 2.3 A+B anchor set

Q4 严格复刻 F-1/E2 主选择：有 A 用全部 A，否则全部 B；C 不作为 matched anchor；selected tier 内 `matsim_link_id` 去重。

### 2.4 MATSim network / nodes

`reports/matsim_network/network_links_source_copy.csv`  
`reports/matsim_network/network_nodes_source_copy.csv`

网络必需 `from_node,to_node,length_m,highway,name`；节点识别 `node_id/id/node`、`x/x_svy21_m/easting`、`y/y_svy21_m/northing`，统一 SVY21 / EPSG:3414。

### 2.5 W01

`matsim_final_7_6h/outputs/W01_rc_min/ITERS/it.19/`

使用 `LINK,HRS8-9avg`，冻结：

`SCALE = 459794 / 200000 = 2.29897`

## 3. Q2 — Direction-relaxed candidate diagnostic

对每个 target LinkID 的全部 E1 stored candidates：

- `FORWARD`: `direction_diff_deg <= 30°`
- `REVERSE`: `direction_diff_deg >= 150°`
- `NEUTRAL`: `30° < direction_diff_deg < 150°`

输出 candidate count、各类 count/share、median/P90 direction、reverse-any、A/B/C reverse share。

固定 Spearman：

- residual vs reverse share；
- residual vs forward share；
- residual vs median direction difference；
- residual vs reverse-any；
- residual vs C-tier reverse share / forward share。

这里的 reverse share 是 **E1 stored candidate evidence**，不是整个网络的 reverse-link prevalence。

## 4. Q4 — Single-link local capture diagnostic

section baseline 直接使用 E2：

`canonical_ratio = sim_8_9_scaled / obs_8_9`  
`canonical_abs_error = |canonical_ratio - 1|`

对于每个 A+B selected anchor，读取冻结 W01 单链路 `HRS8-9avg`。

邻域固定：20m / 50m / 100m；parallel=`heading_diff<=30°`；twin=`heading_diff>=150°`。排除自身及 selected anchors。

每个 radius × neighbor type 只选 **W01 HRS8-9avg 最大的单条邻近 link**：

`best_single_link_ratio = best_neighbor_flow × SCALE / obs`

`capture_error_change = |best_single_link_ratio-1| - |canonical_ratio-1|`

`capture_error_change<0` 表示某条单一邻近 link 在数值上比 frozen canonical ratio 更接近 observed；不表示因果机制或网络守恒成立。

same-name parallel/twin 仅为 diagnostic subclass。

## 5. Non-circularity rules

### R-F2V21-1
Q2 使用 E1 stored full A/B/C candidate evidence，不在 A/B selected domain 上检验其自身方向筛选条件。

### R-F2V21-2
Q2 不重新运行 candidate search。

### R-F2V21-3
Q4 使用 frozen E2 canonical ratio 作为 section baseline。

### R-F2V21-4
Q4 的 alternative 只取单条 neighbor link，不做多-link 求和。

### R-F2V21-5
neighbor selection 不使用 residual sign、magnitude 或 rank。

### R-F2V21-6
single-link capture 是 diagnostic capture，不是 observed network flow conservation。

### R-F2V21-7
20/50/100m、30°、150° 运行前固定。

### R-F2V21-8
secondary / tertiary 分开报告。

### R-F2V21-9
v2.1 不回写 v2、F-1、E1、E2、7.3.6A、v1.0 或 network。

## 6. Hard gates

1. prereg SHA256 MATCH；
2. AST zero-simulation PASS；
3. E1 A/B/C candidates 字段完整；
4. E2 frozen target 字段完整；
5. network link/node 字段完整且唯一；
6. W01 `LINK/HRS8-9avg` complete and unique；
7. target total >=100；
8. secondary >=80；
9. tertiary >=15；
10. target sections with E1 candidate >=95%；
11. target sections with valid candidate direction >=95%；
12. A+B anchor coverage >=95%；
13. anchor network coordinate coverage >=99%；
14. 20/50/100m single-link diagnostics each cover >=95% target；
15. output isolation + provenance complete，所有声明产物实际存在于 v2.1 目录；
16. v2.1 outputs 与 F-2 v2 目录隔离。

## 7. Decision boundary

### `LOCAL_CAPTURE_DIAGNOSTIC_READY`

全部 hard gates PASS。仅表示 Q2/Q4 diagnostic chain 可计算，不表示任何机制已被证明。

### `LOCAL_CAPTURE_DIAGNOSTIC_BLOCKED`

任一 hard gate FAIL，只能报告输入/contract/coverage 问题。

## 8. Outputs

固定目录：`reports/secondary_tertiary_residual_7_9f2_v2_1/`

- `f2v21_target_sections.csv`
- `f2v21_all_e1_candidates.csv`
- `f2v21_selected_ab_candidates.csv`
- `f2v21_direction_candidate_summary.csv`
- `f2v21_direction_candidate_long.csv`
- `f2v21_q2_correlations.csv`
- `f2v21_group_summary.csv`
- `f2v21_single_link_anchor_summary.csv`
- `f2v21_single_link_capture.csv`
- `f2v21_q4_summary.csv`
- `f2v21_obs_rebuild_check.csv`
- `f2v21_checks.csv`
- `f2v21_input_manifest.json`
- `f2v21_summary.json`
- `STEP7_9F2_v2_1_REPORT.md`

## 9. Version boundary

本版本只解决 F-2 v2 的 D4/Q2 与 D5/Q4 可解释性；不修改既有 frozen analysis，任何模型修改另行预注册。
