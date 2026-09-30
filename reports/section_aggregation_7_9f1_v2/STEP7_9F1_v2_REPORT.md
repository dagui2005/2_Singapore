# Step 7.9F-1 v2 — Section Aggregation Sensitivity Audit

**STATUS: AGGREGATION_AUDIT_READY**

正式 v2 重跑；零仿真、只读、diagnostic-only。

## Input resolution

- W01 runtime source: project-root `matsim_final_7_6h/outputs/W01_rc_min/ITERS/it.19`
- E1 selected set: A if available, else B; all selected directed links retained
- E2 main: used only for canonical reproduction check

## Zero-median audit

| Aggregation | n | Zero sections | Zero obs-flow share | True zero n | Median-collapse n | Zero with mean_raw>0 | Obs-weighted residual | Sim-weighted residual |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| CANONICAL_MEDIAN | 1311 | 83 | 6.36% | 68 | 15 | 15 | -0.0139 | 0.8127 |
| POSITIVE_MEDIAN | 1311 | 68 | 3.60% | — | — | 0 | 0.0110 | 0.8239 |
| MEAN | 1311 | 68 | 3.60% | — | — | 0 | -0.0048 | 0.7933 |
| MAX | 1311 | 68 | 3.60% | — | — | 0 | 0.1313 | 1.1048 |

## Highway × aggregation

| Aggregation | Highway | n | Mean | Obs-weighted | Sim-weighted | Zero sections | Negative share | Positive share |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| CANONICAL_MEDIAN | motorway | 336 | 0.1815 | 0.0200 | 0.8303 | 29 | 43.75% | 56.25% |
| CANONICAL_MEDIAN | motorway_link | 263 | 0.1461 | -0.0631 | 1.1418 | 24 | 61.60% | 38.40% |
| CANONICAL_MEDIAN | primary | 433 | 0.1106 | 0.0755 | 0.8822 | 19 | 59.58% | 40.42% |
| CANONICAL_MEDIAN | primary_link | 1 | -0.1695 | -0.1695 | -0.1695 | 0 | 100.00% | 0.00% |
| CANONICAL_MEDIAN | secondary | 89 | -0.3955 | -0.3461 | 0.0604 | 3 | 76.40% | 23.60% |
| CANONICAL_MEDIAN | service | 1 | -0.8828 | -0.8828 | -0.8828 | 0 | 100.00% | 0.00% |
| CANONICAL_MEDIAN | tertiary | 20 | -0.5602 | -0.4174 | -0.0383 | 2 | 85.00% | 15.00% |
| CANONICAL_MEDIAN | trunk | 135 | -0.2358 | -0.2017 | 0.3274 | 6 | 65.93% | 34.07% |
| CANONICAL_MEDIAN | nan | 33 | nan | nan | nan | 0 | 0.00% | 0.00% |
| MAX | motorway | 336 | 0.3834 | 0.1413 | 1.1090 | 21 | 41.37% | 58.63% |
| MAX | motorway_link | 263 | 0.3978 | 0.1955 | 1.7572 | 21 | 53.23% | 46.77% |
| MAX | primary | 433 | 0.2270 | 0.1948 | 1.0865 | 17 | 56.35% | 43.65% |
| MAX | primary_link | 1 | 0.0174 | 0.0174 | 0.0174 | 0 | 0.00% | 100.00% |
| MAX | secondary | 89 | -0.3662 | -0.3196 | 0.0798 | 3 | 76.40% | 23.60% |
| MAX | service | 1 | -0.8828 | -0.8828 | -0.8828 | 0 | 100.00% | 0.00% |
| MAX | tertiary | 20 | -0.4684 | -0.3411 | 0.0135 | 1 | 80.00% | 20.00% |
| MAX | trunk | 135 | -0.0308 | 0.0433 | 0.5913 | 5 | 55.56% | 44.44% |
| MAX | nan | 33 | nan | nan | nan | 0 | 0.00% | 0.00% |
| MEAN | motorway | 336 | 0.2091 | 0.0300 | 0.8223 | 21 | 43.15% | 56.85% |
| MEAN | motorway_link | 263 | 0.1514 | -0.0492 | 1.0224 | 21 | 61.22% | 38.78% |
| MEAN | primary | 433 | 0.1191 | 0.0838 | 0.8813 | 17 | 58.89% | 41.11% |
| MEAN | primary_link | 1 | -0.1869 | -0.1869 | -0.1869 | 0 | 100.00% | 0.00% |
| MEAN | secondary | 89 | -0.4042 | -0.3610 | 0.0286 | 3 | 77.53% | 22.47% |
| MEAN | service | 1 | -0.9062 | -0.9062 | -0.9062 | 0 | 100.00% | 0.00% |
| MEAN | tertiary | 20 | -0.5478 | -0.4148 | -0.0566 | 1 | 85.00% | 15.00% |
| MEAN | trunk | 135 | -0.2404 | -0.1933 | 0.2972 | 5 | 66.67% | 33.33% |
| MEAN | nan | 33 | nan | nan | nan | 0 | 0.00% | 0.00% |
| POSITIVE_MEDIAN | motorway | 336 | 0.2171 | 0.0538 | 0.8430 | 21 | 43.15% | 56.85% |
| POSITIVE_MEDIAN | motorway_link | 263 | 0.1869 | -0.0202 | 1.1795 | 21 | 59.70% | 40.30% |
| POSITIVE_MEDIAN | primary | 433 | 0.1132 | 0.0783 | 0.8807 | 17 | 59.35% | 40.65% |
| POSITIVE_MEDIAN | primary_link | 1 | -0.1695 | -0.1695 | -0.1695 | 0 | 100.00% | 0.00% |
| POSITIVE_MEDIAN | secondary | 89 | -0.3955 | -0.3461 | 0.0604 | 3 | 76.40% | 23.60% |
| POSITIVE_MEDIAN | service | 1 | -0.8828 | -0.8828 | -0.8828 | 0 | 100.00% | 0.00% |
| POSITIVE_MEDIAN | tertiary | 20 | -0.5078 | -0.3954 | -0.0397 | 1 | 85.00% | 15.00% |
| POSITIVE_MEDIAN | trunk | 135 | -0.2268 | -0.1916 | 0.3174 | 5 | 65.93% | 34.07% |
| POSITIVE_MEDIAN | nan | 33 | nan | nan | nan | 0 | 0.00% | 0.00% |

## Corridor diagnostic proxy

- Canonical corridor proxy count (≥2 sections): **124**

## Pairwise robustness

| Level | Comparison | n | Pearson | Spearman | Mean Δ | MAE Δ | Sign-change share |
|---|---|---:|---:|---:|---:|---:|---:|
| SECTION | POSITIVE_MEDIAN_vs_CANONICAL_MEDIAN | 1278 | 0.9819 | 0.9783 | 0.0204 | 0.0204 | 0.63% |
| SECTION | MEAN_vs_CANONICAL_MEDIAN | 1278 | 0.9802 | 0.9706 | 0.0103 | 0.0612 | 2.82% |
| SECTION | MAX_vs_CANONICAL_MEDIAN | 1278 | 0.8611 | 0.9255 | 0.1696 | 0.1696 | 4.69% |
| CORRIDOR | POSITIVE_MEDIAN_vs_CANONICAL | 124 | 0.9965 | 0.9936 | 0.0105 | 0.0105 | 0.00% |
| CORRIDOR | MEAN_vs_CANONICAL | 124 | 0.9857 | 0.9846 | 0.0012 | 0.0409 | 2.42% |
| CORRIDOR | MAX_vs_CANONICAL | 124 | 0.9133 | 0.9140 | 0.1436 | 0.1436 | 8.06% |

## Gates

| Check | Result | Detail |
|---|---|---|
| F1V2.01_PREREG_HASH | PASS | 75bab7e20affa1583dcb7520e5f63b9f32da53d43ee405e2e32766a8d0a396e7 |
| F1V2.02_ZERO_SIMULATION | PASS | AST no subprocess/Java |
| F1V2.03_TRAFFIC_UNIVERSE | PASS | traffic_links=1311 |
| F1V2.04_E1_CANDIDATES | PASS | candidate_rows=15,783 |
| F1V2.05_W01_LINKSTATS | PASS | linkstats_links=693,575 |
| F1V2.06_SELECTED_COVERAGE_GE95PCT | PASS | coverage=0.974828 |
| F1V2.07_VALID_SECTION_N_GE500 | PASS | valid_n=1311 |
| F1V2.08_CANONICAL_MEDIAN_VALID_GE95PCT | PASS | coverage=0.974828 |
| F1V2.08_POSITIVE_MEDIAN_VALID_GE95PCT | PASS | coverage=0.974828 |
| F1V2.08_MEAN_VALID_GE95PCT | PASS | coverage=0.974828 |
| F1V2.08_MAX_VALID_GE95PCT | PASS | coverage=0.974828 |
| F1V2.09_CORE_HIGHWAY_SUPPORT | PASS | missing_or_small=[]; counts={'primary': 433, 'motorway': 336, 'motorway_link': 263, 'trunk': 135, 'secondary': 89, 'tertiary': 20, 'primary_link': 1, 'service': 1} |
| F1V2.10_CANONICAL_REPRODUCES_E2 | PASS | overlap=1278; max_abs_delta_median_raw=0.0; max_abs_delta_scaled=1.8189894035458565e-12 |
| F1V2.11_CORRIDOR_N_GE30 | PASS | corridors=124 |
| F1V2.12_OUTPUT_PROVENANCE | PASS | artifacts=8 missing=[]; outside_out=[]; manifest_entries=8; rehash_mismatch=[]; R0_f1v2_leak_count=0 |
| F1V2.13_W01_RUNTIME_PATH | PASS | resolved=D:\Luan\2026-05\2_Singapore\matsim_final_7_6h\outputs\W01_rc_min\ITERS\it.19\W01_rc_min.19.linkstats.txt.gz |
| F1V2.14_E2_CANONICAL_REPRODUCTION | PASS | E2 main equivalence recorded in f1v2_input_resolution.csv |
| F1V2.15_R0_ARTIFACT_ISOLATION | PASS | R0_f1v2_leak_count=0 |

## Boundary

本步骤不定义新的 calibration aggregation；替代方法只用于 diagnostic sensitivity / falsification，不回写 E2、7.3.6A 或 v1.0。
