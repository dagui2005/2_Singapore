# Step 7.9E-2 — Expanded Diagnostic Residual Domain

**Status: NO_ARTERIAL_COUPLING_SIGNAL**

零仿真、只读；expanded residual 是诊断层，不替换 7.3.6A 正式 residual。

## Fixed scale and domain

- TrafficFlow unique LinkID: **1,311**
- SCALE: **2.29897000**
- A+B valid residual: **1278**
- A+B arterial residual: **542**

## Sensitivity

| Tier | Matched | Coverage | Valid residual | Arterial n | Median distance m | P90 distance m |
|---|---:|---:|---:|---:|---:|---:|
| A_ONLY | 1248 | 95.19% | 1248 | 538 | 0.56 | 2.88 |
| A+B_MAIN | 1278 | 97.48% | 1278 | 542 | 0.57 | 2.92 |
| A+B+C_RELAXED | 1278 | 97.48% | 1278 | 542 | 0.57 | 2.92 |

## Arterial coupling

- valid residual n: **1278**
- arterial n: **542**
- non-arterial n: **736**
- arterial mean residual: **0.002734**
- non-arterial mean residual: **0.090369**
- Spearman: **-0.021553**
- eta²: **0.001300**
- unstratified p: **0.196902**
- RoadCat-stratified p: **0.052474**

## Formal-domain bridge

- overlap n: **576**
- Spearman: **0.966222**
- Pearson: **0.939750**
- mean bias diagnostic-formal: **0.022919**
- MAE: **0.072180**
- RMSE: **0.465548**

## RoadCat × diagnostic highway

| RoadCat | diagnostic_highway | n | share | arterial share |
|---|---|---:|---:|---:|
| CATA | motorway | 330 | 97.35% | 0.29% |
| CATA | motorway_link | 8 | 2.36% | 0.29% |
| CATA | primary | 1 | 0.29% | 0.29% |
| CATB | primary | 418 | 65.93% | 77.29% |
| CATB | trunk | 135 | 21.29% | 77.29% |
| CATB | secondary | 70 | 11.04% | 77.29% |
| CATB | motorway_link | 8 | 1.26% | 77.29% |
| CATB | tertiary | 2 | 0.32% | 77.29% |
| CATB | motorway | 1 | 0.16% | 77.29% |
| CATC | secondary | 19 | 41.30% | 97.83% |
| CATC | primary | 13 | 28.26% | 97.83% |
| CATC | tertiary | 13 | 28.26% | 97.83% |
| CATC | motorway_link | 1 | 2.17% | 97.83% |
| CATD | tertiary | 5 | 71.43% | 85.71% |
| CATD | motorway_link | 1 | 14.29% | 85.71% |
| CATD | primary | 1 | 14.29% | 85.71% |
| CATE | service | 1 | 100.00% | 0.00% |
| SLIP_ROAD | motorway_link | 245 | 97.61% | 0.00% |
| SLIP_ROAD | motorway | 5 | 1.99% | 0.00% |
| SLIP_ROAD | primary_link | 1 | 0.40% | 0.00% |

## Gates

| Check | Result | Detail |
|---|---|---|
| E2.01_PREREG_HASH | PASS | c9e68272cf07c8872f87eebd0d75af28dacd73db4de04d78d90b69ee30a7e6cc |
| E2.02_ZERO_SIMULATION | PASS | AST audit: no subprocess / Java launch |
| E2.03_SCALE_FROZEN | PASS | SCALE=2.29897000 |
| E2.04_TRAFFIC_UNIVERSE | PASS | traffic_links=1311 |
| E2.05_E1_CROSSWALK | PASS | candidate_rows=67,471 |
| E2.06_W01_LINKSTATS | PASS | linkstats_links=693,575 |
| E2.07_AB_COVERAGE_GE_80PCT | PASS | coverage=0.974828 |
| E2.08_VALID_RESIDUAL_SUPPORT | PASS | valid_residual_n=1278 |
| E2.09_ARTERIAL_RESIDUAL_N_GE_30 | PASS | arterial_residual_n=542 |
| E2.10_FORMAL_BRIDGE_GE_500 | PASS | formal_overlap_n=576 |
| E2.11_OUTPUT_ISOLATION | PASS | all outputs written only under 7.9E-2 |
| E2.12_PROVENANCE_READY | PASS | hash/mtime/size manifest will be written |

## Supplementary robustness (post-hoc; NOT in frozen prereg)

冻结判决规则（RoadCat 分层置换 `p < 0.05`）**未改变**。以下为事后稳健性诊断，用于说明该分层统计量是否依赖结构退化层。

| Variant | Strata | n | arterial n | observed abs mean diff | p |
|---|---:|---:|---:|---:|---:|
| ALL_MIXED_STRATA | 4 | 1026 | 542 | 0.576505 | 0.052474 |
| RESTRICTED_MIN_N30_ARM5 | 1 | 634 | 490 | 0.251044 | 0.007996 |
| LEAVE_OUT_CATA | 3 | 687 | 541 | 0.264656 | 0.039980 |
| LEAVE_OUT_CATB | 3 | 392 | 52 | 1.102886 | 0.167916 |
| LEAVE_OUT_CATC | 3 | 980 | 497 | 0.585722 | 0.042979 |
| LEAVE_OUT_CATD | 3 | 1019 | 536 | 0.575391 | 0.060470 |

Within-RoadCat arterial / non-arterial decomposition:

| RoadCat | n arterial | n non-arterial | mean arterial | mean non-arterial | abs diff |
|---|---:|---:|---:|---:|---:|
| CATA | 1 | 338 | -1.000000 | 0.208481 | 1.208481 |
| CATB | 490 | 144 | 0.006105 | -0.244940 | 0.251044 |
| CATC | 45 | 1 | 0.013818 | -0.366323 | 0.380142 |
| CATD | 6 | 1 | -0.188517 | -0.927076 | 0.738559 |
| CATE | 0 | 1 | nan | -0.882772 | nan |
| SLIP_ROAD | 0 | 251 | nan | 0.133435 | nan |

## Residual structure by OSM highway class (post-hoc)

| highway | n | arterial-core n | mean residual | median residual | flow-weighted residual |
|---|---:|---:|---:|---:|---:|
| primary | 433 | 433 | 0.110581 | -0.186087 | 0.075508 |
| motorway | 336 | 0 | 0.181503 | 0.156470 | 0.019996 |
| motorway_link | 263 | 0 | 0.146064 | -0.269898 | -0.063063 |
| trunk | 135 | 0 | -0.235825 | -0.345030 | -0.201706 |
| secondary | 89 | 89 | -0.395460 | -0.560551 | -0.346104 |
| tertiary | 20 | 20 | -0.560181 | -0.665905 | -0.417435 |
| primary_link | 1 | 0 | -0.169478 | -0.169478 | -0.169478 |
| service | 1 | 0 | -0.882772 | -0.882772 | -0.882772 |

注意：`arterial_core = primary ∪ secondary ∪ tertiary` 的三类残差**符号相反**（primary 正、secondary/tertiary 负）⇒ 该聚合量存在**符号抵消**，聚合均值不可作为「arterial 是否残差主场」的依据。


## Boundary

该 residual 只用于结构诊断；不得进入正式 calibration target、v1.0 或 v1.1。
