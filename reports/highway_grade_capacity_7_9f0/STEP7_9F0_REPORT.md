# Step 7.9F-0 — Highway Grade x Capacity/Speed Structural Audit

**STATUS: GRADE_CAPACITY_AUDIT_READY**

零仿真、只读；不修改 v1.0，不产生 v1.1。

- frozen network: `reports/matsim_network/network.xml.gz` (706,554 directed links)
- residual domain: 7.9E-2 expanded, `tier_output=A+B_MAIN`, valid n = **1,278**

## 0. Input resolution (deviation from PREREG section 2)

预注册 §2 对两个输入的字段声明均不成立，实际解析如下（详见 `f0_input_resolution.csv`）：

| declared input | declared field | actual resolution |
|---|---|---|
| `network_links_source_copy.csv` | `capacity` | 该 CSV 无此列（仅 8 列）；capacity 取自冻结 `network.xml.gz` 的 link 属性 |
| `e2_section_residual_main.csv` | `representative_matsim_link_id` | 该表 17 列无此字段；取自 `e2_section_residual_all_tiers.csv` 的 `A+B_MAIN` 切片 |

A+B_MAIN 切片与 main 表等价性：LinkID 集合相同 = **True**，valid 标记差异 = **0**，max|Δresidual| = **0.0**。

## 1. Core result by highway grade

| Highway | n | Mean res | Obs-w res | Sim-w res | Lanes med | Lanes fallback | Cap/lane | Speed med | Obs/cap P50 | Sim/cap P50 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| motorway | 336 | 0.1815 | 0.0200 | 0.8303 | 3.00 | 0.00% | 1900.0 | 90.0 | 0.5633 | 0.6166 |
| motorway_link | 263 | 0.1461 | -0.0631 | 1.1418 | 1.00 | 0.76% | 1700.0 | 50.0 | 0.3588 | 0.2448 |
| primary | 433 | 0.1106 | 0.0755 | 0.8822 | 3.00 | 0.23% | 1500.0 | 60.0 | 0.2517 | 0.1990 |
| secondary | 89 | -0.3955 | -0.3461 | 0.0604 | 2.00 | 0.00% | 1200.0 | 60.0 | 0.2858 | 0.1121 |
| tertiary | 20 | -0.5602 | -0.4174 | -0.0383 | 2.00 | 20.00% | 900.0 | 60.0 | 0.3033 | 0.0779 |
| trunk | 135 | -0.2358 | -0.2017 | 0.3274 | 3.00 | 1.48% | 1800.0 | 70.0 | 0.2918 | 0.1402 |

## 2. Capacity/lane lookup (tautology check)

| Highway | n | Canonical | Actual P50 | Unique | Match ≤1% | Rel diff P50 | Default-lanes share |
|---|---:|---:|---:|---:|---:|---:|---:|
| motorway | 336 | 1900 | 1900.0 | 1 | 100.00% | 0.0000 | 7.74% |
| trunk | 135 | 1800 | 1800.0 | 1 | 100.00% | 0.0000 | 15.56% |
| motorway_link | 263 | 1700 | 1700.0 | 1 | 100.00% | 0.0000 | 61.98% |
| primary | 433 | 1500 | 1500.0 | 1 | 100.00% | 0.0000 | 18.01% |
| primary_link | 1 | 1300 | 1300.0 | 1 | 100.00% | 0.0000 | 0.00% |
| secondary | 89 | 1200 | 1200.0 | 1 | 100.00% | 0.0000 | 65.17% |
| tertiary | 20 | 900 | 900.0 | 1 | 100.00% | 0.0000 | 20.00% |
| service | 1 | 400 | 400.0 | 1 | 100.00% | 0.0000 | 100.00% |

## 3. Lane expression (OSM present vs class default)

| Highway | Links | OSM lanes present | Fallback to default | Effective med | OSM raw med | Class default |
|---|---:|---:|---:|---:|---:|---:|
| service | 460544 | 42.91% | 57.09% | 1.00 | 2.00 | 1.0 |
| residential | 121519 | 89.56% | 10.44% | 2.00 | 2.00 | 1.0 |
| primary | 25821 | 98.35% | 1.65% | 3.00 | 3.00 | 2.0 |
| tertiary | 23642 | 94.79% | 5.21% | 2.00 | 2.00 | 1.0 |
| secondary | 19806 | 96.31% | 3.69% | 2.00 | 2.00 | 2.0 |
| unclassified | 18650 | 83.54% | 16.46% | 2.00 | 2.00 | 1.0 |
| motorway_link | 9086 | 96.30% | 3.70% | 1.00 | 2.00 | 1.0 |
| primary_link | 8087 | 92.43% | 7.57% | 1.00 | 1.00 | 1.0 |
| trunk | 6208 | 81.06% | 18.94% | 3.00 | 3.00 | 2.0 |
| motorway | 4780 | 99.58% | 0.42% | 3.00 | 3.00 | 2.0 |
| secondary_link | 3492 | 85.17% | 14.83% | 1.00 | 1.00 | 1.0 |
| trunk_link | 2714 | 94.22% | 5.78% | 1.00 | 1.00 | 1.0 |
| tertiary_link | 2205 | 87.85% | 12.15% | 1.00 | 1.00 | 1.0 |

## 4. Speed ladder

| Highway | Links | P10 | Median | P90 | Max | Unique | Top speeds (km/h x n) |
|---|---:|---:|---:|---:|---:|---:|---|
| motorway | 4780 | 80.0 | 90.0 | 90.0 | 90.0 | 5 | 90x2657; 80x1750; 70x324; 50x45; 60x4 |
| trunk | 6208 | 60.0 | 70.0 | 80.0 | 80.0 | 7 | 70x2495; 80x1597; 60x1524; 50x488; 40x59 |
| primary | 25821 | 50.0 | 60.0 | 70.0 | 70.0 | 5 | 60x13766; 70x7054; 50x4578; 40x399; 30x24 |
| primary_link | 8087 | 50.0 | 50.0 | 50.0 | 70.0 | 5 | 50x7336; 40x590; 70x82; 60x72; 30x7 |
| motorway_link | 9086 | 50.0 | 50.0 | 50.0 | 90.0 | 8 | 50x8287; 40x413; 70x160; 60x77; 90x73 |
| residential | 121519 | 40.0 | 50.0 | 50.0 | 70.0 | 9 | 50x78785; 40x36164; 30x5587; 60x527; 20x136 |
| secondary | 19806 | 50.0 | 50.0 | 60.0 | 70.0 | 5 | 50x10193; 60x6952; 40x1858; 70x770; 30x33 |
| tertiary | 23642 | 40.0 | 50.0 | 50.0 | 70.0 | 5 | 50x16615; 40x4749; 60x1693; 70x551; 20x34 |
| secondary_link | 3492 | 40.0 | 50.0 | 50.0 | 60.0 | 3 | 50x3007; 40x471; 60x14 |
| trunk_link | 2714 | 50.0 | 50.0 | 50.0 | 70.0 | 5 | 50x2236; 40x134; 70x133; 60x122; 30x89 |
| tertiary_link | 2205 | 30.0 | 50.0 | 50.0 | 50.0 | 3 | 50x1764; 30x338; 40x103 |
| unclassified | 18650 | 30.0 | 50.0 | 50.0 | 60.0 | 6 | 50x14113; 30x2667; 40x1070; 60x691; 20x96 |
| service | 460544 | 20.0 | 20.0 | 20.0 | 70.0 | 10 | 20x446106; 50x5908; 40x4399; 15x2494; 30x472 |

## 5. Trunk -> Secondary -> Tertiary gradient

| Highway | Ordinal | n | Mean | Obs-weighted | Sim-weighted | Lanes fallback | Cap/lane | Speed med |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| trunk | 1 | 135 | -0.2358 | -0.2017 | 0.3274 | 1.48% | 1800.0 | 70.0 |
| secondary | 2 | 89 | -0.3955 | -0.3461 | 0.0604 | 0.00% | 1200.0 | 60.0 |
| tertiary | 3 | 20 | -0.5602 | -0.4174 | -0.0383 | 20.00% | 900.0 | 60.0 |

- Trend Spearman(mean) = **-1.0000**
- Trend Spearman(obs-weighted) = **-1.0000**
- Trend Spearman(sim-weighted) = **-1.0000**
- Companion structural trend: capacity/lane = -1.0000, speed = -0.8660, lane-fallback = 0.5000

## 6. Zero-median sections and the weighting-base flip

断面值 = `sim_8_9_median_raw × SCALE`，即**匹配边上的中位数**。一支断面的匹配边若多数无流量，该断面被压成 0，残差恒为 **−1.0**，因而成为任何 *observed-flow-weighted* 聚合的一阶驱动量。

- 零中位断面数 = **83**，其中 `sim_8_9_mean_raw > 0`（中位数塌陷而均值不塌陷）的有 **15** （18.1%）
- 这些断面的匹配边数中位 = 3，最大 = 17
- 规则：section value = sim_8_9_median_raw scaled by SCALE; a section whose matched edges are mostly unused collapses to 0

| Highway | n all | obs all | n zero-sim | obs share zero-sim | obs-w all | obs-w excl-zero | Δ | sim-w all | sim-w excl-zero |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| __ALL_VALID__ | 1278 | 2,385,571 | 83 | 6.45% | -0.0139 | +0.0542 | +0.0680 | +0.8127 | +0.8127 |
| motorway | 336 | 1,308,488 | 29 | 8.23% | +0.0200 | +0.1114 | +0.0914 | +0.8303 | +0.8303 |
| motorway_link | 263 | 253,247 | 24 | 7.04% | -0.0631 | +0.0079 | +0.0709 | +1.1418 | +1.1418 |
| primary | 433 | 491,128 | 19 | 3.38% | +0.0755 | +0.1132 | +0.0377 | +0.8822 | +0.8822 |
| primary_link | 1 | 1,414 | 0 | 0.00% | -0.1695 | -0.1695 | +0.0000 | -0.1695 | -0.1695 |
| secondary | 89 | 73,192 | 3 | 2.99% | -0.3461 | -0.3259 | +0.0202 | +0.0604 | +0.0604 |
| service | 1 | 353 | 0 | 0.00% | -0.8828 | -0.8828 | +0.0000 | -0.8828 | -0.8828 |
| tertiary | 20 | 11,389 | 2 | 5.39% | -0.4174 | -0.3842 | +0.0332 | -0.0383 | -0.0383 |
| trunk | 135 | 246,360 | 6 | 3.69% | -0.2017 | -0.1711 | +0.0306 | +0.3274 | +0.3274 |

## 7. Raw vs grade-demeaned correlations

| Attribute | n | Pearson (demeaned) | Spearman (demeaned) |
|---|---:|---:|---:|
| lanes_effective | 1278 | 0.0702 | 0.0939 |
| speed_kmh | 1278 | 0.1005 | 0.0661 |
| capacity | 1278 | 0.0775 | 0.0917 |
| capacity_per_lane | 1278 | nan | nan |
| capacity_per_obs_flow | 1278 | 0.1997 | -0.0054 |
| obs_to_capacity_proxy | 1278 | -0.1565 | 0.0288 |
| sim_to_capacity_proxy | 1278 | 0.6297 | 0.8739 |

## 8. Gates

| Class | Check | Result | Detail |
|---|---|---|---|
| PREREG | F0.01_PREREG_HASH | PASS | 1e058914d8e3a9768a76d69c021b2e91dede22d91db240f4a1a333d9505e166b |
| PREREG | F0.02_ZERO_SIMULATION | PASS | AST: no subprocess/jpype/py4j, no run/system/popen attribute call |
| PREREG | F0.03_NETWORK_FIELDS | PASS | missing=[]; capacity from network.xml.gz, raw lanes from network_links_source_copy.csv |
| PREREG | F0.04_E2_RESIDUAL_FIELDS | PASS | missing=[]; rep link id from all_tiers tier_output=A+B_MAIN |
| PREREG | F0.05_REP_LINK_JOIN_GE_95PCT | PASS | join_coverage=1.000000 (1278/1278) |
| PREREG | F0.06_VALID_RESIDUAL_N_GE_500 | PASS | valid_residual_n=1278 |
| PREREG | F0.07_CORE_HIGHWAY_SUPPORT | PASS | below_20=[]; counts={'primary': 433, 'motorway': 336, 'motorway_link': 263, 'trunk': 135, 'secondary': 89, 'tertiary': 20, 'primary_link': 1, 'service': 1} |
| PREREG | F0.08_CAP_LANES_COVERAGE_GE_95PCT | PASS | coverage=1.000000 |
| PREREG | F0.09_SPEED_COVERAGE_GE_90PCT | PASS | coverage=1.000000 |
| PREREG | F0.10_CAPACITY_PROXY_COVERAGE_GE_80PCT | PASS | coverage=1.000000 |
| PREREG | F0.11_OUTPUT_ISOLATION | PASS | files_written=18; outside_out_dir=[]; frozen_paths_touched=[] |
| PREREG | F0.12_PROVENANCE | PASS | manifest_keys=['e2_all_tiers', 'e2_main', 'network_csv', 'network_xml', 'prereg', 'script']; sha256+size re-verified=True |
| SUPPLEMENTARY | F0.13_INPUT_SCHEMA_DEVIATION_DOCUMENTED | PASS | f0_input_resolution.csv records both PREREG section-2 deviations |
| SUPPLEMENTARY | F0.14_E2_MAIN_TIER_EQUIVALENCE | PASS | {"main_file_present": true, "same_linkid_set": true, "valid_flag_discrepant": 0, "max_abs_residual_delta": 0.0, "n_slice": 1311} |
| SUPPLEMENTARY | F0.15_XML_CSV_LINK_PARITY | PASS | links=706554; dup=0; xml_csv_speed_mismatch=0 |

## Interpretation boundary

- **obs-weighted 与 sim-weighted 不是同一件事**：obs-weighted = `Σsim/Σobs − 1`（流量守恒），sim-weighted = `Σsim·r / Σsim`（模拟流量的所在之处）。两者在本数据上系统性背离，主因是零中位断面的 −1.0 只进入 obs 基数。任何等级梯度结论**必须双基数并报**。
- capacity/lane 在该网络中由 `lanes × CAPACITY_PER_LANE[highway]` 解析生成；若 lookup-match 接近 100%，说明 capacity 层**不含 link 级信息**，lookup-match 只证明参数表达，不证明参数正确（R-GRADE-3）。
- raw between-grade correlation 可能被 highway class 本身驱动，必须结合 grade-demeaned 结果（R-GRADE-4）。
- observed/simulated capacity proxy 只是诊断代理，不等价于 realized v/c（R-GRADE-5）。
- 本步骤零仿真、只读，不产生 v1.1；不得回写 v1.0 或 7.3.6A target（R-GRADE-1 / R-GRADE-6）。
