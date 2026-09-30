# Step 7.9F-2 v2.1-R2 — Execution / Contract Closure Repair

**STATUS: LOCAL_CAPTURE_DIAGNOSTIC_READY**

ZERO SIMULATION / READ-ONLY / DIAGNOSTIC ONLY.

## Domain
- target=109; secondary=89; tertiary=20

## Q2

| Highway | n | median forward | median reverse | median neutral | median direction |
|---|---:|---:|---:|---:|---:|
| secondary | 89 | 0.2375 | 0.2208 | 0.5500 | 89.93 |
| tertiary | 20 | 0.2330 | 0.2404 | 0.5390 | 90.01 |

| Metric | n | Spearman |
|---|---:|---:|
| reverse_share | 109 | 0.0558 |
| forward_share | 109 | 0.0509 |
| median_direction_diff_deg | 109 | -0.0482 |
| reverse_any | 109 | NaN |
| C_GEOMETRY_ONLY_reverse_share | 109 | 0.1156 |
| C_GEOMETRY_ONLY_forward_share | 109 | 0.0006 |

## Q4

| Highway | Radius | Type | n all | n valid | median best ratio | median error change | improved share valid | missing share |
|---|---:|---|---:|---:|---:|---:|---:|---:|
| secondary | 20 | parallel | 89 | 52 | 0.1562 | 0.0017 | 23.08% | 41.57% |
| secondary | 20 | same_name_parallel | 89 | 32 | 0.3245 | 0.0000 | 25.00% | 64.04% |
| secondary | 20 | same_name_twin | 89 | 77 | 0.5143 | 0.0730 | 44.16% | 13.48% |
| secondary | 20 | twin | 89 | 80 | 0.5045 | 0.0774 | 42.50% | 10.11% |
| secondary | 50 | parallel | 89 | 88 | 0.4563 | 0.0000 | 47.73% | 1.12% |
| secondary | 50 | same_name_parallel | 89 | 79 | 0.4628 | 0.0000 | 49.37% | 11.24% |
| secondary | 50 | same_name_twin | 89 | 87 | 0.5617 | 0.0730 | 42.53% | 2.25% |
| secondary | 50 | twin | 89 | 88 | 0.5711 | 0.0732 | 42.05% | 1.12% |
| secondary | 100 | parallel | 89 | 89 | 0.5212 | -0.0039 | 59.55% | 0.00% |
| secondary | 100 | same_name_parallel | 89 | 89 | 0.4971 | -0.0039 | 59.55% | 0.00% |
| secondary | 100 | same_name_twin | 89 | 87 | 0.5960 | 0.0730 | 44.83% | 2.25% |
| secondary | 100 | twin | 89 | 89 | 0.5960 | 0.0734 | 43.82% | 0.00% |
| tertiary | 20 | parallel | 20 | 9 | 0.1106 | 0.0000 | 22.22% | 55.00% |
| tertiary | 20 | same_name_parallel | 20 | 6 | 0.8435 | 0.0000 | 33.33% | 70.00% |
| tertiary | 20 | same_name_twin | 20 | 18 | 0.3605 | 0.1623 | 38.89% | 10.00% |
| tertiary | 20 | twin | 20 | 18 | 0.3605 | 0.1623 | 38.89% | 10.00% |
| tertiary | 50 | parallel | 20 | 20 | 0.4631 | 0.0000 | 45.00% | 0.00% |
| tertiary | 50 | same_name_parallel | 20 | 18 | 0.3902 | 0.0000 | 44.44% | 10.00% |
| tertiary | 50 | same_name_twin | 20 | 20 | 0.3018 | 0.1314 | 40.00% | 0.00% |
| tertiary | 50 | twin | 20 | 20 | 0.3018 | 0.1314 | 40.00% | 0.00% |
| tertiary | 100 | parallel | 20 | 20 | 0.6092 | -0.0012 | 55.00% | 0.00% |
| tertiary | 100 | same_name_parallel | 20 | 20 | 0.5034 | 0.0000 | 45.00% | 0.00% |
| tertiary | 100 | same_name_twin | 20 | 20 | 0.3605 | 0.1314 | 45.00% | 0.00% |
| tertiary | 100 | twin | 20 | 20 | 0.3647 | 0.1239 | 45.00% | 0.00% |

## Gates

| Check | Result | Detail |
|---|---|---|
| F2V21R2.01_PREREG_HASH | PASS | 0a0c61336056a66d5ea1506215b1680d3920aef2cb804a221571812e9de18a19 |
| F2V21R2.02_ZERO_SIMULATION | PASS | AST no subprocess/Java |
| F2V21R2.03_E1_RAW_QUALITY | PASS | {"raw_rows": 67471, "kept_rows": 67471, "dropped_rows": 0, "raw_id_missing": 0, "raw_bad_tier": 0, "tier_counts": {"C_GEOMETRY_ONLY": 51688, "B_DIRECTION_GEOMETRY": 9328, "A_STRICT_SEMANTIC_DIRECTION": 6455}} |
| F2V21R2.04_E2_TARGET_UNIQUE | PASS | target_n=109 |
| F2V21R2.05_NETWORK_PREFLIGHT | PASS | {"network_duplicate_link_id": 0, "node_duplicate_id": 0, "node_required_missing": [], "error": ""} |
| F2V21R2.06_W01_PREFLIGHT | PASS | {"missing": [], "duplicate_link": 0, "error": ""} |
| F2V21R2.07_TARGET_TOTAL_GE100 | PASS | target_n=109 |
| F2V21R2.08_SECONDARY_GE80 | PASS | secondary=89 |
| F2V21R2.09_TERTIARY_GE15 | PASS | tertiary=20 |
| F2V21R2.10_E1_COVERAGE_GE95 | PASS | coverage=1.000000 |
| F2V21R2.11_DIRECTION_COVERAGE_GE95 | PASS | coverage=1.000000 |
| F2V21R2.12_AB_ANCHOR_COVERAGE_GE95 | PASS | coverage=1.000000 |
| F2V21R2.13_ANCHOR_COORD_GE99 | PASS | coverage=1.000000 |
| F2V21R2.14_NEIGHBOR_GE95_EACH_RADIUS | PASS | {"20.0": 1.0, "50.0": 1.0, "100.0": 1.0} |
| F2V21R2.15_OUTPUT_PROVENANCE | PASS | declared=15; all_exist=True; nonempty=True; unknown=[] |
| F2V21R2.16_ISOLATION | PASS | [] |
| F2V21R2.17_WRITEBACK_VERIFICATION | PASS | f2v21r2_target_sections.csv:OK; f2v21r2_all_e1_candidates.csv:OK; f2v21r2_selected_ab_candidates.csv:OK; f2v21r2_direction_candidate_summary.csv:OK; f2v21r2_direction_candidate_long.csv:OK; f2v21r2_q2_correlations.csv:OK; f2v21r2_group_summary.csv:OK; f2v21r2_single_link_capture.csv:OK; f2v21r2_q4_summary.csv:OK; f2v21r2_obs_rebuild_check.csv:OK |
| F2V21R2.18_LOADER_CHECKS_CONTRACT | PASS | {"loader_fn_found": true, "checks_fn_found": true, "declared_keys": ["raw_rows", "kept_rows", "dropped_rows", "raw_id_missing", "raw_bad_tier", "tier_counts"], "loader_return_keys": ["raw_rows", "kept_rows", "dropped_rows", "raw_id_missing", "raw_bad_tier", "tier_counts"], "checks_param": "cand_detail", "checks_referenced_keys": ["raw_bad_tier", "raw_id_missing", "raw_rows"], "missing_from_loader": [], "referenced_not_declared": [], "pass": true} |

## Boundary

R2 仅修复执行/契约/闭环问题（R2-1/2/3）；Q2/Q4 定义、阈值、样本域、SCALE、E2 frozen residual 未变。P2-8/P2-10/P2-11 不在本版本中处理。Q4 仍为 diagnostic single-link capture，不是网络守恒或因果证明。
