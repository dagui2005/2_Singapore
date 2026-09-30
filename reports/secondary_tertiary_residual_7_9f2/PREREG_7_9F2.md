# PREREG_7_9F2 — Secondary/Tertiary Residual Mechanism Audit

**Step**: 7.9F-2  
**Scope**: zero-simulation, read-only, diagnostic-only  
**Purpose**: 在 7.9F-1 已排除 section aggregation 作为 secondary/tertiary residual 主要解释后，检查剩余 residual 是否与匹配结构、方向一致性、邻近平行/双向道路流量落点以及局地流量包络有关。

## 1. Frozen boundary

本步骤不得修改 TrafficFlow、E1/E2、MATSim network/capacity/lanes/speed、route-choice/scoring/QSim、7.3.6A、7.6H、F-0/F-1、v1.0/v1.1。

本步骤不启动 MATSim、不调用 Java、不修改模型、不重新估计 SCALE、不重新设计 E1 candidate search；只写入 `reports/secondary_tertiary_residual_7_9f2/`。

## 2. Fixed inputs

### TrafficFlow
`Singapore_OD_MATSim_FinalData/08_TrafficCount/TrafficFlow_Data.json`

工作日、`HourOfDate=8`；同一 `LinkID × Date` 先取日代表值，再按 LinkID 取工作日 median，得到 `obs_8_9`。

### TrafficFlow geometry
`Singapore_OD_MATSim_FinalData/08_TrafficCount/TrafficFlow_Links.shp`

字段：`LinkID, RoadName, RoadCat, StartLon, StartLat, EndLon, EndLat, geometry`。几何统一 EPSG:3414，用于独立计算 LTA directed heading。

### E1
`reports/arterial_observability_7_9e1/e1_crosswalk_candidates.csv`

严格复刻 F-1/E2 A+B main：有 A 用全部 A，否则全部 B；C 不进入主诊断；selected tier 内按 `matsim_link_id` 去重，保留全部 selected directed links。

### E2
`reports/arterial_expanded_residual_7_9e2/e2_section_residual_main.csv`

只读取 `LinkID, obs_8_9, diagnostic_residual_8_9, diagnostic_highway, valid_residual`，作为 frozen diagnostic target；F-2 不重算 residual。

### MATSim network
`reports/matsim_network/network_links_source_copy.csv`，必需 `from_node,to_node,length_m,highway,name`。

### MATSim nodes
`reports/matsim_network/network_nodes_source_copy.csv`，识别 `node_id/id/node` 与 `x/x_svy21_m/easting`、`y/y_svy21_m/northing`，统一 EPSG:3414。

### W01
真实冻结运行结果：`matsim_final_7_6h/outputs/W01_rc_min/ITERS/it.19/`，使用 `LINK,HRS8-9avg`。

## 3. Frozen analysis domain

只分析：`diagnostic_highway ∈ {secondary, tertiary}`、`valid_residual=True`、`obs_8_9>0`。预期约 secondary=89、tertiary=20、合计约109；不足则 BLOCKED。

## 4. Matching-structure diagnostics

每个目标 LinkID 固定报告 selected_total_n、selected_A_n、selected_B_n、A_available、B_available、selected_highway_n、distance min/median、direction min/median/max、direction_good_share (`direction_diff_deg<=30°`)、direction_twin_share (`>=150°`)、same_highway_share、matched-flow sum diagnostic。

## 5. Directionality diagnostics

由 TrafficFlow_Links.shp 独立计算 LTA heading；由 network node 坐标计算 MATSim directed heading；报告重算后的 direction difference，并与 E1 `direction_diff_deg` 做一致性记录。阈值固定 30° / 150°，不得按 residual 调整。

## 6. Parallel / twin diagnostics

真实物理米制距离，不用 hop count。固定半径：20m、50m、100m。

- parallel：heading difference <=30°；
- twin/opposite：heading difference >=150°；
- 排除自身及 selected matched-link set；
- same-name / same-highway 仅作 diagnostic subclass，不是主定义。

## 7. Local-flow-envelope diagnostic

本步骤核心概念为 **local flow envelope diagnostic**，不是 observed network flow conservation，也不是 OD-level conservation。

### matched-flow baseline
`matched_flow_raw = Σ HRS8-9avg(selected matched directed links)`

`matched_flow_scaled = matched_flow_raw × SCALE`，其中 `SCALE=459794/200000=2.29897`。

### added flow
分别计算 20/50/100m 下的 parallel、twin、same-name parallel、same-name twin added W01 flow；不得重新运行 MATSim。

### envelope ratio
`(matched_flow_scaled + nearby_added_flow_scaled) / obs_8_9`。

固定报告 added share、envelope ratio、以及
`|envelope_ratio-1|-|matched_ratio-1|`。

这些指标只表示局地流量包络在数值上的覆盖程度，不证明真实守恒。

## 8. Prespecified mechanism questions

Q1：secondary/tertiary residual 是否与 selected candidate count、distance、direction quality、highway heterogeneity 存在单调关系？使用 Spearman。

Q2：residual 是否与 median direction difference、direction-good share、reverse-candidate share 存在单调关系？使用 Spearman。

Q3：20/50/100m 内是否存在有非零 W01 flow 的 parallel/twin/same-name neighbors？报告 prevalence 和 observed-flow-weighted added share。

Q4：20/50/100m 的 matched baseline、parallel envelope、twin envelope、all-direction envelope 是否呈系统性不同？报告 mean/median/paired change；不选择“最佳半径”。

## 9. Non-circularity / permanent rules

### R-F2-1
E2 frozen residual 永久不被 F-2 包络重定义。

### R-F2-2
20/50/100m、30°、150° 运行前固定。

### R-F2-3
neighbor search 不使用 residual sign、magnitude 或 rank 筛选。

### R-F2-4
只使用冻结 W01 HRS8-9avg；不重跑 MATSim。

### R-F2-5
matched baseline 使用 selected A+B directed links 的 W01 flow sum，仅为 F-2 diagnostic；F-1 canonical median 不改写。

### R-F2-6
same-name / same-highway 只是 diagnostic subclass。

### R-F2-7
主空间尺度永远是 physical meters；hop count 只能辅助记录。

### R-F2-8
secondary 与 tertiary 分开报告。

### R-F2-9
local flow envelope 数值改善不能表述为真实 network flow conservation 证明。

### R-F2-10
不得据 F-2 结果直接修改 capacity/speed/route-choice/demand/crosswalk。

## 10. Hard gates

1. prereg SHA256 MATCH；
2. AST zero-simulation PASS；
3. TrafficFlow JSON 与 geometry 输入完整；
4. E1 candidates 完整；
5. E2 frozen residual 完整；
6. network link/node 完整；
7. W01 LINK/HRS8-9avg complete and unique；
8. target valid total >=100；
9. secondary >=80；
10. tertiary >=15；
11. selected A+B coverage >=95% of target；
12. selected network coordinate coverage >=99%；
13. direction recomputed coverage >=95%；
14. 20/50/100m neighborhood diagnostics >=95%；
15. output isolation + provenance complete；所有声明产物必须实际存在于 F-2 目录。

## 11. Decision boundary

`MECHANISM_AUDIT_READY`：全部 hard gates PASS，表示诊断链可用于后续 mechanism interpretation，不代表某个机制已被证明。

`MECHANISM_AUDIT_BLOCKED`：任一 gate FAIL，只能报告输入/contract 问题。

## 12. Output

固定目录：`reports/secondary_tertiary_residual_7_9f2/`

- `f2_target_sections.csv`
- `f2_selected_candidates.csv`
- `f2_candidate_structure.csv`
- `f2_direction_diagnostics.csv`
- `f2_direction_candidate_long.csv`
- `f2_local_neighbors.csv
- `f2_mechanism_summary.csv`
- `f2_group_summary.csv`
- `f2_checks.csv`
- `f2_input_manifest.json`
- `f2_summary.json`
- `STEP7_9F2_REPORT.md`
