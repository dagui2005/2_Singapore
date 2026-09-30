# Step 7.9F-0 v2 — Highway Grade × Capacity/Speed Structural Audit

**STATUS: GRADE_CAPACITY_AUDIT_READY**

正式 v2 重跑；零仿真、只读；不修改 v1.0、不产生 v1.1。

## Core results

| Highway | n | Mean | Obs-w | Sim-w | Raw lanes P50 | XML lanes P50 | Cap/lane P50 | Speed P50 | Obs/cap P50 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| motorway | 336 | 0.1815 | 0.0200 | 0.8303 | 3.00 | 3.00 | 1900.0 | 90.0 | 0.5633 |
| motorway_link | 263 | 0.1461 | -0.0631 | 1.1418 | 1.00 | 1.00 | 1700.0 | 50.0 | 0.3588 |
| primary | 433 | 0.1106 | 0.0755 | 0.8822 | 3.00 | 3.00 | 1500.0 | 60.0 | 0.2517 |
| secondary | 89 | -0.3955 | -0.3461 | 0.0604 | 2.00 | 2.00 | 1200.0 | 60.0 | 0.2858 |
| tertiary | 20 | -0.5602 | -0.4174 | -0.0383 | 2.00 | 2.00 | 900.0 | 60.0 | 0.3033 |
| trunk | 135 | -0.2358 | -0.2017 | 0.3274 | 3.00 | 3.00 | 1800.0 | 70.0 | 0.2918 |

## Zero-median robustness

| Scope | n | Zero-median n | Obs-flow share | Zero with mean_raw>0 | Obs-w residual | Sim-w residual |
|---|---:|---:|---:|---:|---:|---:|
| FULL | 1278 | 83 | 6.45% | 15 | -0.0139 | 0.8127 |
| EXCLUDING_ZERO_MEDIAN | 1195 | 0 | 0.00% | 0 | 0.0542 | 0.8127 |

## Trend

| Highway | Ordinal | n | Mean | Obs-w | Sim-w |
|---|---:|---:|---:|---:|---:|
| trunk | 1 | 135 | -0.2358 | -0.2017 | 0.3274 |
| secondary | 2 | 89 | -0.3955 | -0.3461 | 0.0604 |
| tertiary | 3 | 20 | -0.5602 | -0.4174 | -0.0383 |

## Grade-demeaned correlations

| Attribute | n | Pearson | Spearman |
|---|---:|---:|---:|
| raw_lanes | 1269 | 0.0703 | 0.0939 |
| xml_permlanes | 1278 | 0.0702 | 0.0939 |
| speed_kmh | 1278 | 0.1005 | 0.0661 |
| capacity_per_lane | 1278 | nan | nan |
| obs_to_capacity | 1278 | -0.1565 | 0.0288 |
| sim_to_capacity | 1278 | 0.6297 | 0.8739 |
| xml_capacity | 1278 | 0.0775 | 0.0917 |

## Gates

| Check | Result | Detail |
|---|---|---|
| F0V2.01_PREREG_HASH | PASS | 31d61dc8a9e608ce1feb30a0ffb583f3a94ded3507e090f829bb6dc265019248 |
| F0V2.02_ZERO_SIMULATION | PASS | AST no Java/subprocess |
| F0V2.03_NETWORK_SOURCE_FIELDS | PASS | source structural fields |
| F0V2.04_E2_ALL_TIERS_FIELDS | PASS | E2 A+B_MAIN source |
| F0V2.05_REP_JOIN_GE_95PCT | PASS | coverage=1.000000 |
| F0V2.06_VALID_RESIDUAL_N_GE_500 | PASS | n=1278 |
| F0V2.07_CORE_HIGHWAY_SUPPORT | PASS | missing=[]; counts={'primary': 433, 'motorway': 336, 'motorway_link': 263, 'trunk': 135, 'secondary': 89, 'tertiary': 20, 'primary_link': 1, 'service': 1} |
| F0V2.08_CAP_LANES_COVERAGE_GE_95PCT | PASS | coverage=1.000000 |
| F0V2.09_SPEED_COVERAGE_GE_90PCT | PASS | coverage=1.000000 |
| F0V2.10_CAPACITY_PROXY_COVERAGE_GE_80PCT | PASS | coverage=1.000000 |
| F0V2.11_OUTPUT_ISOLATION | PASS | out=D:\Luan\2026-05\2_Singapore\reports\highway_grade_capacity_7_9f0_v2; artifacts=12 all_in_dir=True; R0_dir_clean=True |
| F0V2.12_PROVENANCE | PASS | manifest_entries=6; rehash_mismatch=[] |
| F0V2.13_RUNTIME_XML_PARAMETER_SOURCE | PASS | XML links=706554; capacity/permlanes/freespeed all non-null |
| F0V2.14_E2_AB_MAIN_SOURCE | PASS | A+B_MAIN rows=1311; tier uniform; LinkID unique |
| F0V2.15_MAIN_EQUIVALENCE | PASS | LinkID_set_equal=True (ab=1311, main=1311); max|dresidual|=0.0 |

## Boundary

- lookup-match 只证明当前冻结网络参数表达符合既定 lookup，不证明 lookup 数值本身正确。
- raw grade relationship 与 within-grade relationship 必须联合解释。
- capacity proxy 不是 realized v/c。
- 不回写 calibration target 或 v1.0。
