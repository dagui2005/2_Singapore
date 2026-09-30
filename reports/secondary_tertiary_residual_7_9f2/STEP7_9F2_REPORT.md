# Step 7.9F-2 — Secondary/Tertiary Residual Mechanism Audit

**STATUS: MECHANISM_AUDIT_READY**

零仿真、只读、diagnostic-only。

## Domain

- target valid sections: **109**
- secondary: **89**
- tertiary: **20**

## Group summary

| Highway | n | Mean frozen residual | Median frozen residual | Median matched-sum ratio | Median direction (deg) | Positive parallel flow @100m | Positive twin flow @100m |
|---|---:|---:|---:|---:|---:|---:|---:|
| secondary | 89 | -0.3955 | -0.5606 | 2.0281 | 1.16 | 96.63% | 97.75% |
| tertiary | 20 | -0.5602 | -0.6659 | 1.6541 | 1.22 | 95.00% | 100.00% |

## Local flow envelope

| Radius | Mean matched ratio | Median matched ratio | Mean all-direction envelope | Median all-direction envelope |
|---:|---:|---:|---:|---:|
| 20 | 3.1653 | 1.9282 | 6.4906 | 4.5272 |
| 50 | 3.1653 | 1.9282 | 11.1491 | 7.6632 |
| 100 | 3.1653 | 1.9282 | 16.1881 | 12.1201 |

## Prespecified correlations

| Family | Metric | Spearman with frozen residual |
|---|---|---:|
| MATCHING_STRUCTURE | selected_total_n | 0.0064 |
| MATCHING_STRUCTURE | selected_distance_median_m | 0.1443 |
| MATCHING_STRUCTURE | selected_direction_median_deg | 0.1986 |
| MATCHING_STRUCTURE | selected_direction_good_share | nan |
| MATCHING_STRUCTURE | selected_direction_twin_share | nan |
| MATCHING_STRUCTURE | same_highway_share | 0.1807 |
| DIRECTIONALITY | direction_median_recomputed_deg | 0.1986 |
| DIRECTIONALITY | direction_good_share_recomputed | nan |
| DIRECTIONALITY | direction_twin_share_recomputed | nan |
| LOCAL_FLOW_ENVELOPE | parallel_added_share@20m | 0.1361 |
| LOCAL_FLOW_ENVELOPE | twin_added_share@20m | -0.0330 |
| LOCAL_FLOW_ENVELOPE | same_name_parallel_added_share@20m | 0.0546 |
| LOCAL_FLOW_ENVELOPE | same_name_twin_added_share@20m | -0.0579 |
| LOCAL_FLOW_ENVELOPE | all_direction_envelope_abs_residual_change@20m | 0.1754 |
| LOCAL_FLOW_ENVELOPE | parallel_added_share@50m | 0.6190 |
| LOCAL_FLOW_ENVELOPE | twin_added_share@50m | 0.0263 |
| LOCAL_FLOW_ENVELOPE | same_name_parallel_added_share@50m | 0.5907 |
| LOCAL_FLOW_ENVELOPE | same_name_twin_added_share@50m | 0.0229 |
| LOCAL_FLOW_ENVELOPE | all_direction_envelope_abs_residual_change@50m | 0.2899 |
| LOCAL_FLOW_ENVELOPE | parallel_added_share@100m | 0.6980 |
| LOCAL_FLOW_ENVELOPE | twin_added_share@100m | -0.0220 |
| LOCAL_FLOW_ENVELOPE | same_name_parallel_added_share@100m | 0.7637 |
| LOCAL_FLOW_ENVELOPE | same_name_twin_added_share@100m | -0.0231 |
| LOCAL_FLOW_ENVELOPE | all_direction_envelope_abs_residual_change@100m | 0.3012 |

## Gates

| Check | Result | Detail |
|---|---|---|
| F2.01_PREREG_HASH | PASS | 5c361b2de1731d6b4325bbcb3b739e85ce5fcc4fb02640e03a14239d5f968bec |
| F2.02_ZERO_SIMULATION | PASS | AST no Java/subprocess execution |
| F2.03_TRAFFIC_INPUTS | PASS | traffic_json=1311; geometry=1278 |
| F2.04_E1_CANDIDATES | PASS | candidate_rows=15,783 |
| F2.05_E2_TARGET_FIELDS | PASS | e2_rows=1,311 |
| F2.06_NETWORK_FIELDS_AND_COORDS | PASS | network_links_with_coords=706,554 |
| F2.07_W01_LINKSTATS | PASS | w01_links=693,575 |
| F2.08_TARGET_TOTAL_GE100 | PASS | target_n=109 |
| F2.09_SECONDARY_GE80 | PASS | secondary=89 |
| F2.10_TERTIARY_GE15 | PASS | tertiary=20 |
| F2.11_SELECTED_COVERAGE_GE95 | PASS | coverage=1.000000 |
| F2.12_SELECTED_NETWORK_COORD_GE99 | PASS | coverage=1.000000 |
| F2.13_DIRECTION_RECOMPUTED_GE95 | PASS | coverage=1.000000 |
| F2.14_NEIGHBOR_DIAGNOSTICS_GE95 | PASS | section_coverage=1.000000; rows=1635; expected=1635 |
| F2.15_OUTPUT_PROVENANCE | PASS | output_dir=D:\Luan\2026-05\2_Singapore\reports\secondary_tertiary_residual_7_9f2; declared_outputs_exist=True |

## Boundary

local flow envelope 是 diagnostic proxy，不是 observed network flow conservation 证明；任何数值改善均不得回写 E2、7.3.6A、v1.0 或 MATSim network。
