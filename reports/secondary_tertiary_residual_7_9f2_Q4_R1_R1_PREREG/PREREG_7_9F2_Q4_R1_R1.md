# PREREG_7_9F2_Q4_R1_R1 — Nearest-Single-Link Local Capture (4 neighbor types, 25 real gates)

**Step**: F-2 Q4-R1-R1
**Supersedes**: F-2 Q4-R1 (as-provided, BLOCKED)
**Scope**: zero-simulation / read-only / diagnostic-only

This revision changes **only the execution layer** of Q4-R1:

1. restores the four frozen neighbor types;
2. makes the three previously toothless gates real (16 / 20 / 22);
3. makes the flow-blind gate structural instead of a text window (23);
4. repairs and makes executable the R2 non-Q4 comparison gate (25);
5. materializes a complete BLOCKED node instead of an aborted half-node.

The nearest-single-link **definition itself is not modified**.

---

## 1. Frozen boundary

Do not modify TrafficFlow, E1/E2, MATSim network/nodes/capacity/lanes/speed,
QSim, route-choice, 7.3.6A, 7.6H, F-0/F-1/F-2 v2, F-2 v2.1-R2,
v1.0/v1.1, SCALE, or any earlier node directory.

No MATSim/Java. No E1 rerun. No residual re-estimation. No E2 writeback.

Only write to:
`reports/secondary_tertiary_residual_7_9f2_Q4_R1_R1/`

Prereg:
`reports/secondary_tertiary_residual_7_9f2_Q4_R1_R1_PREREG/`

Read-only reference (never written):
`reports/secondary_tertiary_residual_7_9f2_v2_1_R2/`

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

## 4. Neighbor eligibility — four frozen types

For each target section and selected A+B focal anchor:
- radius = 20 / 50 / 100 m;
- physical distance = minimum midpoint-to-midpoint distance to any focal anchor;
- `hd` = minimum heading difference to any focal anchor.

`neighbor_type` is frozen at four values. `parallel` and `twin` are the base
heading classes; `same_name_parallel` and `same_name_twin` are the
**name-restricted subsets** of them (this is a superset/subset relation, not a
disjoint partition — it is the definition frozen in the Q4-R1 lineage):

| neighbor_type | eligibility predicate |
|---|---|
| `parallel` | `hd <= 30` |
| `twin` | `hd >= 150` |
| `same_name_parallel` | `hd <= 30` **and** `name_norm(L) ∈ {name_norm(F) : F ∈ focal(sid)}` |
| `same_name_twin` | `hd >= 150` **and** `name_norm(L) ∈ {name_norm(F) : F ∈ focal(sid)}` |

`name_norm` comes from the **network** table (`name`), not from W01 or E1.

Full cross product is mandatory: `109 × 3 × 4 = 1,308` rows.
An empty eligible pool produces an explicit row, never a dropped row.

Exclude:
1. focal selected anchors;
2. target-section SELF.

SELF is not defined by zero distance.
Frozen definition:

> SELF(sid) = the E1 stored candidate with minimum `distance_m`; ties:
> `direction_diff_deg`, `tier`, `matsim_link_id`.

SELF is defined over **all** stored E1 candidates of `sid`, independent of tier.

## 5. Selection rule

For each section × radius × neighbor type:

`min physical distance`
→ `min direction difference`
→ `min matsim_link_id`

W01 flow, residual, ratio, `capture_error_change` and residual rank are
forbidden from selection. The W01 lookup must occur strictly **after** the
selected ID has been determined.

## 6. Primary Q4 statistic

`nearest_single_link_ratio = selected_neighbor_W01_flow × SCALE / obs_8_9`

`capture_error_change =
 |nearest_single_link_ratio - 1|
 - |canonical_ratio_e2 - 1|`

`capture_improved = capture_error_change < 0`

`ratio_unavailable_reason ∈ {OK, NO_CANDIDATE, SELECTED_LINK_NOT_IN_W01}`

The reason value is a **closed set of three explicit tokens**. The empty
string is forbidden: after a CSV round trip an empty string is parsed as
`NaN` and "no reason" becomes indistinguishable from "missing value".

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

Additional diagnostic fields are permitted, including `selected_is_self` and
`selected_is_same_name`.

### 7.1 Serialized candidate evidence (required for independent re-derivation)

`q4r1r1_candidate_pool.csv` — one row per
`(LinkID, radius_m, candidate_link_id)` **after** focal-anchor and SELF
exclusion, **before** neighbor-type filtering:

`LinkID, radius_m, candidate_link_id, distance_m, direction_diff_deg, same_name, name_norm, highway`

This table is the evidence base from which gate 20 re-derives the selection.
It must not contain any focal-anchor link or SELF link of that section.

## 8. Hard gates — 25

Gate identifiers are frozen exactly as written.

`Q4R1.01_PREREG_HASH`
Prereg SHA matches the value embedded in the script.

`Q4R1.02_ZERO_SIMULATION`
AST confirms no Java/MATSim/subprocess execution.

`Q4R1.03_E1_RAW_QUALITY`
E1 raw schema and raw-quality fields are complete.

`Q4R1.04_E2_TARGET_UNIQUE`
Target exists and LinkID is unique.

`Q4R1.05_NETWORK_PREFLIGHT`
Network/node preflight passes before strict loading. Evaluated even when it
is the failing gate.

`Q4R1.06_W01_PREFLIGHT`
W01 preflight passes before strict loading. Evaluated even when it is the
failing gate.

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
file exists in the node directory.

`Q4R1.15_ISOLATION`
No Q4 artifact contaminates any earlier node directory.

`Q4R1.16_WRITEBACK_VERIFICATION`
Three-way write-back verification between the manifest, the closure table and
the disk.

Declared sets, over the full 15-artifact declared set:

- the manifest declares exactly the declared set minus
  `q4r1r1_input_manifest.json` and `q4r1r1_closure_check.csv` (a file cannot
  hash itself, and the closure is written after the manifest);
- the closure table declares exactly the declared set minus
  `q4r1r1_closure_check.csv`;
- the disk set equals the full declared set.

Byte comparison, over every declared artifact except
`q4r1r1_checks.csv`, `q4r1r1_input_manifest.json` and
`q4r1r1_closure_check.csv` — twelve artifacts on a baseline run:

1. the artifact exists and is non-empty on disk;
2. its size recorded in the manifest equals the actual size;
3. its SHA256 recorded in the manifest equals the actual SHA256;
4. its size and SHA256 recorded in `closure_check` equal the actual values.

`checks.csv` is excluded from the byte comparison because it is rewritten
after the manifest and its content depends on this gate's own result;
excluding it makes the gate result independent of `checks.csv` content, so
the terminal state is a fixed point rather than a self-referential loop.

Every declared artifact, including the three excluded from the byte
comparison, must still exist and be non-empty.

The manifest is generated **last** among the artifacts it covers.
`summary.json` and the report are regenerated **after** the final
`checks.csv` write. The terminal state is iterated to a fixed point; a run
that does not converge is itself a failure.

`Q4R1.17_LOADER_CHECKS_CONTRACT`
Every `e1_detail` key referenced by `checks()` is present in the loader's
returned dictionary. Evaluated before any loader runs, on the AST of this
file.

`Q4R1.18_GRID_COMPLETE`
The `(LinkID, radius_m, neighbor_type)` key set equals the full
`109 × 3 × 4 = 1,308` cross product; no duplicate keys; no target dropped
for having an empty pool.

`Q4R1.19_SCHEMA_AND_MISSINGNESS_ACCOUNTING`
All 23 mandatory fields exist and all reason values are in the frozen closed
set.

`Q4R1.20_SELECTION_REDERIVED`
Independent re-derivation. A second, separately written implementation reads
`q4r1r1_candidate_pool.csv` (geometry only), re-applies the four type
predicates, re-sorts by `(distance_m, direction_diff_deg, candidate_link_id)`
and re-computes the selection for all 1,308 cells, then compares cell by cell
with the stored `selected_neighbor_link_id` and
`selected_neighbor_distance_m`.

Pass condition: zero mismatches across 1,308 cells, and the re-derived
`n_candidates` equals the recorded `n_candidates` in every cell.

Pre-registered expectation (from a read-only feasibility probe):
`1,308/1,308` identical; `max |Δ ratio| = 0`; `max |Δ distance| <= 1e-9`.

The stored `selection_rule` string is **not** used as evidence by this gate.

`Q4R1.21_RADIUS_MONOTONE_DISTANCE`
For comparable selections, `d20 >= d50 >= d100`.
This verifies that the nearest-single-link rule does not reproduce the prior
max-over-N selection mechanism, in which the selected statistic rises
mechanically with candidate count. The gate must **not** be stated as a proof
that all statistical bias has been eliminated.

`Q4R1.22_EXCLUSION_AND_CONTAINMENT`
Three separate checks, reported separately:

(a) SELF exclusion. SELF(sid) is **independently re-derived from the raw E1
candidate table**, not read from the `selected_is_self` derived column.
Then `selected_neighbor_link_id != SELF(sid)` for all 1,308 cells.

(b) Anchor exclusion. `selected_neighbor_link_id ∉ focal anchors(sid)` for all
1,308 cells.

(c) Containment. Candidate pools are nested in radius:
`pool(20) ⊆ pool(50) ⊆ pool(100)` for every `(sid, neighbor_type)`.

Violations must be 0 for all three.

`Q4R1.23_SELECTION_FLOW_BLIND_STATIC`
Structural AST audit of the selection region of `build_grid`: from the start
of the neighbor-type eligibility loop through the statement that assigns
`selected_id`, the set of loaded names must be disjoint from

`{flow_map, HRS8-9avg, capture_error_change, capture_improved,
  nearest_single_link_ratio, canonical_ratio_e2, canonical_abs_error_e2,
  diagnostic_residual_8_9}`

and the first load of `flow_map` in `build_grid` must occur on a line
**after** the `selected_id` assignment.

The audit is structural (AST statement ranges), not a text window, and may
not be satisfied by moving a reference outside a character window.

`Q4R1.24_Q4_TRACEABILITY`
Every valid selected row has ID, distance, direction, name, highway, flow,
candidate count and selection rule.

`Q4R1.25_NON_Q4_ARTIFACTS_UNCHANGED_VS_R2`
Eight non-Q4 inherited artifacts are compared byte-for-byte against the
frozen R2 node `reports/secondary_tertiary_residual_7_9f2_v2_1_R2/`:

| artifact | frozen SHA256 | bytes |
|---|---|---|
| `f2v21r2_target_sections.csv` | `e7bd590fb0b49581f148b29b904426338f3aab8f0a59360fc4441a0ef76a5776` | 18767 |
| `f2v21r2_all_e1_candidates.csv` | `89a83b29074690397465c870a92d9e2b735d6d64f5502f8c18d87e1a31ff23b7` | 929020 |
| `f2v21r2_selected_ab_candidates.csv` | `159581fd953ead61a8894bf977dcd75d61f61ce9e5c386ff497c1eab1e428014` | 86519 |
| `f2v21r2_direction_candidate_summary.csv` | `cff9fcd1113895ee0d4efff69eb06a815817ecc632c896f07e8c33c840f6c56e` | 21550 |
| `f2v21r2_direction_candidate_long.csv` | `e69df9864237522ffaddd22ccf061e4c6eb002a204a9e9a9eedaea82d0563598` | 933721 |
| `f2v21r2_q2_correlations.csv` | `fd4a8d084daf1d91b8a2ab77ad805b4ca30ab2ee2a504bf1004c1573a22b1d6e` | 303 |
| `f2v21r2_group_summary.csv` | `d384f1148abdc7b293f654b38e2130194c2e6a50ddb4fc895a246be0c922b1e4` | 424 |
| `f2v21r2_obs_rebuild_check.csv` | `5db00d70a035c8b6b0c465f58d968dc680470d58297c3bc306f14139dd7e00cc` | 2659 |

Two directions must both hold:

(A) **R2 not polluted.** For each of the 8 files, the SHA256 currently on
disk under the R2 node equals the frozen value above.

(B) **Local inheritance identical.** For each of the 8 files, a byte copy
placed in this node under `inherited_r2/` has the same SHA256 as the R2 copy.

Reported as `8/8 identical`.

Additional teeth (reported in the same gate detail): the two artifacts this
node also computes natively — `target_sections` and `selected_ab_candidates`
— are recomputed from the raw inputs and must be byte-identical to the frozen
R2 copies.

## 9. Negative tests

N1 missing traceability column → 19 SCHEMA FAIL.
N2 invalid reason state → 19 SCHEMA FAIL.
N3 two references to the same link type with a forced non-nearest pick →
20 SELECTION_REDERIVED FAIL.
N4 max-W01-flow selection → 23 FLOW_BLIND_STATIC FAIL and/or 20 FAIL.
N5 radius inversion → 21 RADIUS_MONOTONE FAIL.
N6 selected focal anchor allowed through → 22 EXCLUSION FAIL.
N7 SELF allowed through → 22 EXCLUSION FAIL.
N8 selected ID altered after W01 lookup → 24 TRACEABILITY FAIL.
N9 R2 directory contamination → 15 ISOLATION FAIL.
N10 inherited non-Q4 artifact overwritten → 25 R2_COMPARE FAIL.

## 10. Frozen feasibility observations

Read-only probes established before this freeze:

- target grid = 1,308 section × radius × type cells;
- SELF is not equivalent to an A+B anchor for 25/109 sections;
- selected-link-not-in-W01 = 0 under the frozen anchor domain;
- under the nearest rule the selected link is frequently the target section's
  **own** lower-tier E1 candidate; `same_section_e1_share` was 0.988764 for
  `secondary/parallel` and 1.0 for `tertiary/parallel` at 100 m;
- prior max-over-N statistic showed strong dependence on candidate count
  (`ρ(N, improved) = 0.9429`), which the nearest rule removes
  (median ratio drift 20→100 m: R2 `+0.365` / `+0.499` → Q4 `+0.020` / `+0.007`).

These are frozen expectations, not results to be absorbed. The median-ratio
comparison against R2 is an observation to be re-confirmed by this node's own
25 gates before it is recorded as a result.

## 11. Decision boundary

`Q4_LOCAL_CAPTURE_READY` = all 25 gates PASS.
This means only that the nearest-single-link diagnostic is executable and
auditable.

It does not establish functional substitution, causality, or network flow
conservation. Under the nearest rule the selected link is usually the
section's own lower-tier E1 candidate; "nearest" means geometrically closest
known link, not functionally comparable link.

`Q4_LOCAL_CAPTURE_BLOCKED` = any gate FAIL.

**BLOCKED must still be a complete, auditable node**: full 25-row
`checks.csv` (unevaluated gates explicitly marked), `summary.json`,
`input_manifest.json`, `closure_check.csv`, report, and exit code 1.
An aborted half-node is not an acceptable terminal state.

## 12. Required outputs

Directory:
`reports/secondary_tertiary_residual_7_9f2_Q4_R1_R1/`

Analytical and terminal artifacts (15):

- q4r1r1_target_sections.csv
- q4r1r1_selected_ab_candidates.csv
- q4r1r1_self_definition.csv
- q4r1r1_candidate_pool.csv
- q4r1r1_candidate_grid.csv
- q4r1r1_single_link_capture.csv
- q4r1r1_summary.csv
- q4r1r1_group_summary.csv
- q4r1r1_selection_audit.csv
- q4r1r1_writeback_verification.csv
- q4r1r1_r2_artifact_compare.csv
- q4r1r1_checks.csv
- q4r1r1_closure_check.csv
- q4r1r1_input_manifest.json
- q4r1r1_summary.json
- STEP7_9F2_Q4_R1_R1_REPORT.md

Inherited reference copies (8), in `inherited_r2/`:

- f2v21r2_target_sections.csv
- f2v21r2_all_e1_candidates.csv
- f2v21r2_selected_ab_candidates.csv
- f2v21r2_direction_candidate_summary.csv
- f2v21r2_direction_candidate_long.csv
- f2v21r2_q2_correlations.csv
- f2v21r2_group_summary.csv
- f2v21r2_obs_rebuild_check.csv

`inherited_r2/` is a declared set of its own and is covered by
`closure_check.csv`; it is excluded from the 15-artifact provenance set only
because it lives in a subdirectory.

`closure_check.csv` records one `artifact` row per declared artifact
**except itself** — a file cannot record its own hash and a self-referential
size row prevents the terminal state from converging. Its own existence,
non-emptiness and membership in the declared set are still verified through
the declared-set equality of gate 16.

## 13. Version boundary

Q4-R1-R1 changes only the execution layer of Q4-R1.

It does not alter Q2, E1, E2, F-2 v2.1-R2, v1.0, the model, the target, the
anchor domain, the radii, the heading thresholds, SCALE, or the
nearest-single-link definition.

Any model modification requires a separate preregistration.
