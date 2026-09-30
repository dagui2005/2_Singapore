# Step 7.9F-1 — Section Aggregation Sensitivity Audit

**STATUS: AGGREGATION_AUDIT_READY**

零仿真、只读、diagnostic-only。

- TrafficFlow unique LinkID: **1,311**
- E1 candidate rows: **15,783**
- W01 links: **693,575**

## Zero-median audit

| Aggregation | n | Zero sections | Zero obs-flow share | Zero with mean_raw>0 | Obs-weighted residual | Sim-weighted residual |
|---|---:|---:|---:|---:|---:|---:|
| CANONICAL_MEDIAN | 1311 | 83 | 6.36% | 15 | -0.0139 | 0.8127 |
| POSITIVE_MEDIAN | 1311 | 68 | 3.60% | 0 | 0.0110 | 0.8239 |
| MEAN | 1311 | 68 | 3.60% | 0 | -0.0048 | 0.7933 |
| MAX | 1311 | 68 | 3.60% | 0 | 0.1313 | 1.1048 |

## Highway × aggregation

| Aggregation | Highway | n | Mean | Obs-weighted | Sim-weighted | Zero sections |
|---|---|---:|---:|---:|---:|---:|
| CANONICAL_MEDIAN | motorway | 336 | 0.1815 | 0.0200 | 0.8303 | 29 |
| CANONICAL_MEDIAN | motorway_link | 263 | 0.1461 | -0.0631 | 1.1418 | 24 |
| CANONICAL_MEDIAN | primary | 433 | 0.1106 | 0.0755 | 0.8822 | 19 |
| CANONICAL_MEDIAN | primary_link | 1 | -0.1695 | -0.1695 | -0.1695 | 0 |
| CANONICAL_MEDIAN | secondary | 89 | -0.3955 | -0.3461 | 0.0604 | 3 |
| CANONICAL_MEDIAN | service | 1 | -0.8828 | -0.8828 | -0.8828 | 0 |
| CANONICAL_MEDIAN | tertiary | 20 | -0.5602 | -0.4174 | -0.0383 | 2 |
| CANONICAL_MEDIAN | trunk | 135 | -0.2358 | -0.2017 | 0.3274 | 6 |
| CANONICAL_MEDIAN | nan | 33 | nan | nan | nan | 0 |
| MAX | motorway | 336 | 0.3834 | 0.1413 | 1.1090 | 21 |
| MAX | motorway_link | 263 | 0.3978 | 0.1955 | 1.7572 | 21 |
| MAX | primary | 433 | 0.2270 | 0.1948 | 1.0865 | 17 |
| MAX | primary_link | 1 | 0.0174 | 0.0174 | 0.0174 | 0 |
| MAX | secondary | 89 | -0.3662 | -0.3196 | 0.0798 | 3 |
| MAX | service | 1 | -0.8828 | -0.8828 | -0.8828 | 0 |
| MAX | tertiary | 20 | -0.4684 | -0.3411 | 0.0135 | 1 |
| MAX | trunk | 135 | -0.0308 | 0.0433 | 0.5913 | 5 |
| MAX | nan | 33 | nan | nan | nan | 0 |
| MEAN | motorway | 336 | 0.2091 | 0.0300 | 0.8223 | 21 |
| MEAN | motorway_link | 263 | 0.1514 | -0.0492 | 1.0224 | 21 |
| MEAN | primary | 433 | 0.1191 | 0.0838 | 0.8813 | 17 |
| MEAN | primary_link | 1 | -0.1869 | -0.1869 | -0.1869 | 0 |
| MEAN | secondary | 89 | -0.4042 | -0.3610 | 0.0286 | 3 |
| MEAN | service | 1 | -0.9062 | -0.9062 | -0.9062 | 0 |
| MEAN | tertiary | 20 | -0.5478 | -0.4148 | -0.0566 | 1 |
| MEAN | trunk | 135 | -0.2404 | -0.1933 | 0.2972 | 5 |
| MEAN | nan | 33 | nan | nan | nan | 0 |
| POSITIVE_MEDIAN | motorway | 336 | 0.2171 | 0.0538 | 0.8430 | 21 |
| POSITIVE_MEDIAN | motorway_link | 263 | 0.1869 | -0.0202 | 1.1795 | 21 |
| POSITIVE_MEDIAN | primary | 433 | 0.1132 | 0.0783 | 0.8807 | 17 |
| POSITIVE_MEDIAN | primary_link | 1 | -0.1695 | -0.1695 | -0.1695 | 0 |
| POSITIVE_MEDIAN | secondary | 89 | -0.3955 | -0.3461 | 0.0604 | 3 |
| POSITIVE_MEDIAN | service | 1 | -0.8828 | -0.8828 | -0.8828 | 0 |
| POSITIVE_MEDIAN | tertiary | 20 | -0.5078 | -0.3954 | -0.0397 | 1 |
| POSITIVE_MEDIAN | trunk | 135 | -0.2268 | -0.1916 | 0.3174 | 5 |
| POSITIVE_MEDIAN | nan | 33 | nan | nan | nan | 0 |

## Corridor support

Canonical corridor proxy count (≥2 sections): **124**

## Pairwise robustness

| Level | Comparison | n | Pearson | Spearman | Mean Δ | MAE Δ | Sign-change share |
|---|---|---:|---:|---:|---:|---:|
| SECTION | POSITIVE_MEDIAN_vs_CANONICAL_MEDIAN | 1278 | 0.9819 | 0.9783 | 0.0204 | 0.0204 | 0.63% |
| SECTION | MEAN_vs_CANONICAL_MEDIAN | 1278 | 0.9802 | 0.9706 | 0.0103 | 0.0612 | 2.82% |
| SECTION | MAX_vs_CANONICAL_MEDIAN | 1278 | 0.8611 | 0.9255 | 0.1696 | 0.1696 | 4.69% |
| CORRIDOR | POSITIVE_MEDIAN_vs_CANONICAL | 124 | 0.9965 | 0.9936 | 0.0105 | 0.0105 | 0.00% |
| CORRIDOR | MEAN_vs_CANONICAL | 124 | 0.9857 | 0.9846 | 0.0012 | 0.0409 | 2.42% |
| CORRIDOR | MAX_vs_CANONICAL | 124 | 0.9133 | 0.9140 | 0.1436 | 0.1436 | 8.06% |

## Gates

| Check | Result | Detail |
|---|---|---|
| F1.01_PREREG_HASH | PASS | d3ea2d20cb4ff58d32c17f9db324bae2f2673ae444ad20b3e61483e4aef80e09 |
| F1.02_ZERO_SIMULATION | PASS | AST no subprocess/Java |
| F1.03_TRAFFIC_UNIVERSE | PASS | traffic_links=1311 |
| F1.04_E1_CANDIDATES | PASS | candidate_rows=15,783 |
| F1.05_W01_LINKSTATS | PASS | linkstats_links=693,575 |
| F1.06_SELECTED_COVERAGE_GE95PCT | PASS | coverage=0.974828 |
| F1.07_VALID_SECTION_N_GE500 | PASS | valid_n=1311 |
| F1.08_CANONICAL_MEDIAN_VALID_GE95PCT | PASS | coverage=0.974828 |
| F1.08_POSITIVE_MEDIAN_VALID_GE95PCT | PASS | coverage=0.974828 |
| F1.08_MEAN_VALID_GE95PCT | PASS | coverage=0.974828 |
| F1.08_MAX_VALID_GE95PCT | PASS | coverage=0.974828 |
| F1.09_CORE_HIGHWAY_SUPPORT | PASS | missing_or_small=[]; counts={'primary': 433, 'motorway': 336, 'motorway_link': 263, 'trunk': 135, 'secondary': 89, 'tertiary': 20, 'primary_link': 1, 'service': 1} |
| F1.10_CANONICAL_REPRODUCES_E2 | PASS | overlap=1278; max_abs_delta_sim_8_9_median_raw=0.0; max_abs_delta_scaled=1.8189894035458565e-12 |
| F1.11_CORRIDOR_N_GE30 | PASS | corridors=124 |
| F1.12_OUTPUT_PROVENANCE | PASS | output_dir_name_ok=True; artifacts_in_output_dir=True; rehash_mismatch=[] |

## Input resolution disclosure

- 预注册 §2.3 声明的 W01 路径 `reports/matsim_final_7_6h/outputs/W01_rc_min/ITERS/it.19/` **在磁盘上不存在**；
  实际解析到项目根的同名冻结产物 `matsim_final_7_6h/outputs/W01_rc_min/ITERS/it.19/`（文件身份相同，仅目录前缀偏差）。
  权威记录见 `f1_checks.csv` 的 `F1.S1_INPUT_RESOLUTION` / `F1.S2_DECLARED_PATH_ABSENT_TRACED` 与 `f1_input_manifest.json` 的 `w01_declared_vs_resolved`。
- 本步骤不选择新的 calibration aggregation；替代方法仅作 sensitivity / falsification diagnostic，不回写 E2 或 v1.0。
