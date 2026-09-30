# PREREG_7_9F2_Q4_R1 — Nearest-Single-Link Local Capture

**Step**: F-2 Q4-R1  
**Scope**: zero-simulation / read-only / diagnostic-only

## 1. Frozen boundary

Do not modify TrafficFlow, E1/E2, MATSim network/nodes/capacity/lanes/speed,
QSim, route-choice, 7.3.6A, 7.6H, F-0/F-1/F-2 v2, F-2 v2.1-R2,
v1.0/v1.1, or SCALE.

No MATSim/Java. No E1 rerun. No residual re-estimation.
Only write to:
`reports/secondary_tertiary_residual_7_9f2_Q4_R1/`

Prereg:
`reports/secondary_tertiary_residual_7_9f2_Q4_R1_PREREG/`

## 2. Frozen target

Target:
`diagnostic_highway ∈ {secondary, tertiary}`
`valid_residual == True`
`obs_8_9 > 0`

Expected: secondary=89, tertiary=20, total=109.

Canonical baseline:
`canonical_ratio_e2 = sim_8_9_scaled / obs_8_9`
`canonical_abs_error_e2 = |canonical_ratio_e2 - 1|`

## 3. Frozen anchor domain

Reproduce F-1/E2 A+B hierarchy:
- if A exists, use all A;
- otherwise use all B;
- C is not an anchor;
- deduplicate by `matsim_link_id`.

Expected selected anchors=593; target coverage=109/109.

## 4. Neighbor eligibility

For each target section and selected A+B focal anchor:
- radius = 20/50/100 m;
- physical distance = minimum midpoint-to-midpoint distance to any focal anchor;
- parallel: heading difference <=30°;
- twin: heading difference >=150°.

Exclude:
1. focal selected anchors;
2. target-section SELF.

SELF is not defined by zero distance.  
Frozen definition:

> SELF(sid) = the E1 stored candidate with minimum `distance_m`; ties:
> `direction_diff_deg`, `tier`, `matsim_link_id`.

## 5. Selection rule

For each section × radius × neighbor type:

`min physical distance`
→ `min direction difference`
→ `min matsim_link_id`

W01 flow, residual, ratio and residual rank are forbidden from selection.

## 6. Primary Q4 statistic

`nearest_single_link_ratio = selected_neighbor_W01_flow × SCALE / obs_8_9`

`capture_error_change =
 |nearest_single_link_ratio - 1|
 - |canonical_ratio_e2 - 1|`

`capture_improved = capture_error_change < 0`

`ratio_unavailable_reason ∈ {OK, NO_CANDIDATE, SELECTED_LINK_NOT_IN_W01}`

## 7. Mandatory traceability fields (23)

1. LinkID
2. diagnostic_highway
3. diagnostic_residual_8_9
4. obs_8_9
5. canonical_ratio_e2
6. canonical_abs_error_e2
7. radius_m
8. neighbor_type
9. n_candidates
10. n_positive_flow
11. selected_neighbor_link_id
12. selected_neighbor_distance_m
13. selected_neighbor_direction_diff_deg
14. selected_neighbor_name
15. selected_neighbor_highway
16. selected_neighbor_W01_flow
17. selection_rule
18. nearest_single_link_ratio
19. nearest_single_link_abs_error
20. capture_error_change
21. capture_improved
22. ratio_unavailable_reason
23. selected_is_same_section_e1_candidate

Additional diagnostic fields are permitted, including `selected_is_self`.

## 8. Hard gates — 25

`Q4R1.01_PREREG_HASH`  
Prereg SHA matches embedded value.

`Q4R1.02_ZERO_SIMULATION`  
AST confirms no Java/MATSim/subprocess execution.

`Q4R1.03_E1_RAW_QUALITY`  
E1 raw schema and raw-quality fields are complete.

`Q4R1.04_E2_TARGET_UNIQUE`  
Target exists and LinkID is unique.

`Q4R1.05_NETWORK_PREFLIGHT`  
Network/node preflight passes before strict loading.

`Q4R1.06_W01_PREFLIGHT`  
W01 preflight passes before strict loading.

`Q4R1.07_TARGET_TOTAL_GE100`  
Target total >=100.

`Q4R1.08_SECONDARY_GE80`  
Secondary >=80.

`Q4R1.09_TERTIARY_GE15`  
Tertiary >=15.

`Q4R1.10_AB_ANCHOR_COVERAGE_GE95`  
A+B anchor coverage >=95%.

`Q4R1.11_ANCHOR_COORD_GE99`  
Anchor coordinate coverage >=99%.

`Q4R1.12_E2_CANONICAL_COMPLETE`  
All target canonical ratios finite.

`Q4R1.13_W01_CAPTURE_COVERAGE`  
Selected-anchor W01 coverage >=95%.

`Q4R1.14_OUTPUT_PROVENANCE`  
All declared outputs exist, are non-empty, and no undeclared non-transient
file exists.

`Q4R1.15_ISOLATION`  
No Q4-R1 artifact contaminates earlier node directories.

`Q4R1.16_FINAL_CLOSURE_FILES`  
Final closure and summary artifacts exist.

`Q4R1.17_LOADER_CHECKS_CONTRACT`  
Loader/check referenced-key contract is valid.

`Q4R1.18_GRID_COMPLETE`  
All target × radius × neighbor-type cells exist, including explicit
`NO_CANDIDATE` cells.

`Q4R1.19_SCHEMA_AND_MISSINGNESS_ACCOUNTING`  
All mandatory fields exist and reason values are in the frozen closed set.

`Q4R1.20_SELECTION_REDERIVED`  
Independent deterministic selection audit agrees with the stored selection.

`Q4R1.21_RADIUS_MONOTONE_DISTANCE`  
For comparable selections, d20 >= d50 >= d100. This guards the
nearest-link rule against the prior max-over-N selection behavior; it does
not prove all statistical bias has disappeared.

`Q4R1.22_EXCLUSION_AND_CONTAINMENT`  
Focal anchors and SELF are excluded; radius candidate sets are nested.

`Q4R1.23_SELECTION_FLOW_BLIND`  
Static audit confirms selection does not reference W01 flow, residual or ratio.

`Q4R1.24_Q4_TRACEABILITY`  
Every valid selected row has ID, distance, direction, name, highway, flow,
candidate count and selection rule.

`Q4R1.25_NON_Q4_ARTIFACTS_UNCHANGED_VS_R2`  
Inherited non-Q4 artifacts are byte-identical to the frozen R2 node.

## 9. Negative tests

N1 missing traceability column -> schema gate FAIL.  
N2 invalid reason state -> missingness gate FAIL.  
N3 altered tie-break -> re-derivation FAIL.  
N4 max-W01-flow selection -> flow-blind and/or re-derivation FAIL.  
N5 radius inversion -> monotone-distance FAIL.  
N6 selected anchor allowed through -> exclusion FAIL.  
N7 SELF allowed through -> exclusion FAIL.  
N8 selected ID altered after W01 lookup -> traceability FAIL.  
N9 R2 directory contamination -> isolation FAIL.  
N10 inherited non-Q4 artifact overwritten -> R2 comparison FAIL.

## 10. Frozen feasibility observations

Read-only probe before prereg freeze established:
- target grid = 1,308 section × radius × type cells;
- zero-distance candidates = 0/109 sections;
- SELF is not equivalent to A+B anchor for 25/109 sections;
- selected SELF overlap in the feasibility probe = 0/1,308;
- selected-link-not-in-W01 = 0;
- 1,121/1,308 prior feasible selections were also stored E1 candidates of
  the same target section;
- prior max-flow statistic showed strong dependence on candidate count.

These are frozen expectations, not results to be absorbed.

## 11. Decision boundary

`Q4_LOCAL_CAPTURE_READY` = all 25 gates PASS.  
This means only that the nearest-single-link diagnostic is executable and
auditable.

It does not establish functional substitution, causality, or network flow
conservation.

`Q4_LOCAL_CAPTURE_BLOCKED` = any gate FAIL.

## 12. Required outputs

Directory:
`reports/secondary_tertiary_residual_7_9f2_Q4_R1/`

- q4r1_target_sections.csv
- q4r1_selected_ab_candidates.csv
- q4r1_self_definition.csv
- q4r1_candidate_grid.csv
- q4r1_single_link_capture.csv
- q4r1_summary.csv
- q4r1_group_summary.csv
- q4r1_selection_audit.csv
- q4r1_checks.csv
- q4r1_closure_check.csv
- q4r1_input_manifest.json
- q4r1_summary.json
- STEP7_9F2_Q4_R1_REPORT.md

## 13. Version boundary

Q4-R1 changes only the Q4 diagnostic quantity and its traceability.
It does not alter Q2, E1, E2, F-2 v2.1-R2, v1.0, or the model.

Any model modification requires a separate preregistration.
