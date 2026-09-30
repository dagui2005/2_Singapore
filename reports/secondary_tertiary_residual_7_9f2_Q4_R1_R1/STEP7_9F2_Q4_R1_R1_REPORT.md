# F-2 Q4-R1-R1 — Nearest-Single-Link Local Capture

**STATUS: Q4_LOCAL_CAPTURE_READY**
**CLOSURE: OK**

ZERO SIMULATION / READ-ONLY / DIAGNOSTIC ONLY.

PREREG SHA256: `82a03eb8aac0dc5d7ba610f8f0e3ba53e1cc1e0bd92ca00f60dbc8fdcd7c5f7f`

Neighbor types (4, frozen): `parallel`, `twin`, `same_name_parallel`, `same_name_twin`

## Domain

- target=109; secondary=89; tertiary=20
- grid rows=1,308

## Q4 summary

| Highway | Radius | Type | n | Valid change | Median distance | Median ratio | Median error change | Improved valid | Missing |
|---|---:|---|---:|---:|---:|---:|---:|---:|---:|
| secondary | 20 | parallel | 89 | 52 | 12.081 | 0.0324 | 0.1522 | 15.38% | 41.57% |
| secondary | 20 | same_name_parallel | 89 | 32 | 16.839 | 0.2891 | 0.0000 | 25.00% | 64.04% |
| secondary | 20 | same_name_twin | 89 | 77 | 9.012 | 0.4633 | 0.0255 | 45.45% | 13.48% |
| secondary | 20 | twin | 89 | 80 | 9.171 | 0.4431 | 0.0340 | 43.75% | 10.11% |
| secondary | 50 | parallel | 89 | 88 | 17.727 | 0.0656 | 0.1225 | 21.59% | 1.12% |
| secondary | 50 | same_name_parallel | 89 | 79 | 20.999 | 0.3989 | 0.0000 | 37.97% | 11.24% |
| secondary | 50 | same_name_twin | 89 | 87 | 9.532 | 0.4633 | 0.0255 | 45.98% | 2.25% |
| secondary | 50 | twin | 89 | 88 | 9.673 | 0.4431 | 0.0340 | 44.32% | 1.12% |
| secondary | 100 | parallel | 89 | 89 | 17.891 | 0.0525 | 0.1124 | 21.35% | 0.00% |
| secondary | 100 | same_name_parallel | 89 | 89 | 23.769 | 0.4092 | 0.0000 | 38.20% | 0.00% |
| secondary | 100 | same_name_twin | 89 | 87 | 9.532 | 0.4633 | 0.0255 | 45.98% | 2.25% |
| secondary | 100 | twin | 89 | 89 | 9.815 | 0.4398 | 0.0425 | 43.82% | 0.00% |
| tertiary | 20 | parallel | 20 | 9 | 15.795 | 0.0972 | 0.0170 | 11.11% | 55.00% |
| tertiary | 20 | same_name_parallel | 20 | 6 | 14.836 | 0.8435 | 0.0000 | 33.33% | 70.00% |
| tertiary | 20 | same_name_twin | 20 | 18 | 9.978 | 0.3605 | 0.1415 | 44.44% | 10.00% |
| tertiary | 20 | twin | 20 | 18 | 9.653 | 0.3018 | 0.1639 | 33.33% | 10.00% |
| tertiary | 50 | parallel | 20 | 20 | 21.036 | 0.1039 | 0.0091 | 15.00% | 0.00% |
| tertiary | 50 | same_name_parallel | 20 | 18 | 25.662 | 0.3864 | 0.0000 | 27.78% | 10.00% |
| tertiary | 50 | same_name_twin | 20 | 20 | 10.349 | 0.3018 | 0.0658 | 45.00% | 0.00% |
| tertiary | 50 | twin | 20 | 20 | 9.916 | 0.2140 | 0.1415 | 30.00% | 0.00% |
| tertiary | 100 | parallel | 20 | 20 | 21.036 | 0.1039 | 0.0091 | 15.00% | 0.00% |
| tertiary | 100 | same_name_parallel | 20 | 20 | 30.103 | 0.3180 | 0.0000 | 25.00% | 0.00% |
| tertiary | 100 | same_name_twin | 20 | 20 | 10.349 | 0.3018 | 0.0658 | 45.00% | 0.00% |
| tertiary | 100 | twin | 20 | 20 | 9.916 | 0.2140 | 0.1415 | 30.00% | 0.00% |

## Group summary (name-agnostic types, 100 m)

| Highway | n | Median parallel candidates | Median twin candidates | Same-section E1 parallel | Same-section E1 twin | Self-selected | Exact-zero |
|---|---:|---:|---:|---:|---:|---:|---:|
| secondary | 89 | 23.0 | 26.0 | 98.88% | 100.00% | 0.00% | 10.17% |
| tertiary | 20 | 24.0 | 23.5 | 100.00% | 100.00% | 0.00% | 20.00% |

## Gate evidence

- Q4R1.20 independent re-derivation: cells=1308; mismatched=0; max|delta distance|=0.0; max|delta direction|=0.0
- Q4R1.25 R2 comparison: see `q4r1r1_closure_check.csv` and `q4r1r1_r2_artifact_compare.csv`

## Gates

| Check | Result | Detail |
|---|---|---|
| Q4R1.01_PREREG_HASH | PASS | 82a03eb8aac0dc5d7ba610f8f0e3ba53e1cc1e0bd92ca00f60dbc8fdcd7c5f7f |
| Q4R1.02_ZERO_SIMULATION | PASS | AST no subprocess/Java |
| Q4R1.03_E1_RAW_QUALITY | PASS | {"raw_rows": 67471, "kept_rows": 67471, "raw_id_missing": 0, "raw_bad_tier": 0, "raw_direction_missing": 0, "duplicate_rows_removed": 0} |
| Q4R1.04_E2_TARGET_UNIQUE | PASS | target=109 |
| Q4R1.05_NETWORK_PREFLIGHT | PASS | network=706,554 |
| Q4R1.06_W01_PREFLIGHT | PASS | W01=693,575 |
| Q4R1.07_TARGET_TOTAL_GE100 | PASS | target=109 |
| Q4R1.08_SECONDARY_GE80 | PASS | secondary=89 |
| Q4R1.09_TERTIARY_GE15 | PASS | tertiary=20 |
| Q4R1.10_AB_ANCHOR_COVERAGE_GE95 | PASS | coverage=1.000000 |
| Q4R1.11_ANCHOR_COORD_GE99 | PASS | coverage=1.000000 |
| Q4R1.12_E2_CANONICAL_COMPLETE | PASS | canonical ratios finite |
| Q4R1.13_W01_CAPTURE_COVERAGE | PASS | coverage=1.000000 |
| Q4R1.14_OUTPUT_PROVENANCE | PASS | unknown=[]; analytical_ok=True |
| Q4R1.15_ISOLATION | PASS | [] |
| Q4R1.16_WRITEBACK_VERIFICATION | PASS | manifest_set_ok=True; closure_set_ok=True; disk_set_ok=True; byte_mismatch=[]; terminal_ok=True; n_byte_compared=12; err=none |
| Q4R1.17_LOADER_CHECKS_CONTRACT | PASS | referenced=['raw_bad_tier', 'raw_id_missing', 'raw_rows']; returned=['duplicate_rows_removed', 'kept_rows', 'raw_bad_tier', 'raw_direction_missing', 'raw_id_missing', 'raw_rows']; err= |
| Q4R1.18_GRID_COMPLETE | PASS | actual=1308; expected=1308 (109x3x4) |
| Q4R1.19_SCHEMA_AND_MISSINGNESS_ACCOUNTING | PASS | trace=True; reasons=True |
| Q4R1.20_SELECTION_REDERIVED | PASS | cells_rederived=1308; cells_expected=1308; mismatched_cells=0; max_abs_delta_distance_m=0.000e+00; max_abs_delta_direction_deg=0.000e+00 |
| Q4R1.21_RADIUS_MONOTONE_DISTANCE | PASS | d20>=d50>=d100; violating_cells=0 |
| Q4R1.22_EXCLUSION_AND_CONTAINMENT | PASS | self_violations=0; anchor_violations=0; pool_self_violations=0; pool_anchor_violations=0; radius_containment_violations=0; type_containment_violations=0 |
| Q4R1.23_SELECTION_FLOW_BLIND_STATIC | PASS | region_lines=875-890; banned_hits=[]; first_flow_map_load_line=900; flow_after_selection=True |
| Q4R1.24_Q4_TRACEABILITY | PASS | valid_trace_rows=1146 |
| Q4R1.25_NON_Q4_ARTIFACTS_UNCHANGED_VS_R2 | PASS | identical=8/8; r2_frozen_ok=8/8; local_recompute_identical=2/2; missing=[] |

## Boundary

nearest-single-link is a geometry-defined diagnostic. The selected link is the geometrically closest known link, not a functionally comparable link; in most cells it is the target section's own lower-tier E1 candidate. This node does not establish functional substitution, causality, or observed network flow conservation.

Write-back verification and status closure: `q4r1r1_closure_check.csv`.
