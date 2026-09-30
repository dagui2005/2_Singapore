# Step 7.9E-1 — Arterial Observability Expansion

## Status
**OBSERVABILITY_BLOCKED**

## Scope
零仿真、只读；独立 diagnostic crosswalk；不替换 7.3.6A。

## TrafficFlow universe
- unique TrafficFlow links: **1,311**
- geometry source: **shapefile_geometry(1278/1311)**
- usable directed MATSim links: **706,554**

## Observability
| Tier | Coverage | Median distance (m) | P90 distance (m) | Arterial-core residual links |
|---|---:|---:|---:|---:|
| A_STRICT | 95.19% | 0.56 | 2.88 | 538 |
| A+B_MAIN | 97.48% | 0.57 | 2.92 | 542 |
| A+B+C_RELAXED | 97.48% | 0.57 | 2.92 | 542 |

## Per-RoadCat observability (A+B)
| RoadCat | traffic links | A+B matched | coverage | arterial-core share | dominant highway | median dist (m) | P90 dist (m) |
|---|---:|---:|---:|---:|---|---:|---:|
| CATA | 339 | 339 | 100.00% | 0.29% | motorway | 0.60 | 2.86 |
| CATB | 634 | 634 | 100.00% | 77.29% | primary | 0.55 | 2.88 |
| CATC | 46 | 46 | 100.00% | 97.83% | secondary | 0.65 | 2.85 |
| CATD | 7 | 7 | 100.00% | 85.71% | tertiary | 1.80 | 8.53 |
| CATE | 1 | 1 | 100.00% | 0.00% | service | 0.00 | 0.00 |
| SLIP_ROAD | 251 | 251 | 100.00% | 0.00% | motorway_link | 0.52 | 3.15 |

## RoadCat × OSM highway (A+B)
| RoadCat | highway | n | share within RoadCat |
|---|---|---:|---:|
| CATA | motorway | 330 | 97.35% |
| CATA | motorway_link | 8 | 2.36% |
| CATA | primary | 1 | 0.29% |
| CATB | primary | 418 | 65.93% |
| CATB | trunk | 135 | 21.29% |
| CATB | secondary | 70 | 11.04% |
| CATB | motorway_link | 8 | 1.26% |
| CATB | tertiary | 2 | 0.32% |
| CATB | motorway | 1 | 0.16% |
| CATC | secondary | 19 | 41.30% |
| CATC | primary | 13 | 28.26% |
| CATC | tertiary | 13 | 28.26% |
| CATC | motorway_link | 1 | 2.17% |
| CATD | tertiary | 5 | 71.43% |
| CATD | motorway_link | 1 | 14.29% |
| CATD | primary | 1 | 14.29% |
| CATE | service | 1 | 100.00% |
| SLIP_ROAD | motorway_link | 245 | 97.61% |
| SLIP_ROAD | motorway | 5 | 1.99% |
| SLIP_ROAD | primary_link | 1 | 0.40% |

## Residual section universe
- residual sections: **576**
- residual RoadCat composition: **{'CATA': 326, 'SLIP_ROAD': 250}**
- residual representative highway (A+B): **{'motorway': 328, 'motorway_link': 247, 'primary_link': 1}**
- arterial residual n — A: **0** / A+B: **0** / A+B+C: **0**

## Residual coupling (A+B)
- valid residual sample: **576**
- arterial-core sample: **0**
- non-arterial sample: **576**
- Spearman: **nan**
- eta²: **nan**
- permutation p (unstratified): **nan**
- permutation p (stratified): **nan**

## Boundary
A+B 达到 ≥30 个 arterial residual sections 只表示可观测性得到支持，不直接证明 arterial capacity 错误。

## Decision state
- **OBSERVABILITY_BLOCKED**
- `OBSERVABILITY_PASS` -> 7.9E-2 arterial mechanism audit
- `C_ONLY_OBSERVABILITY` -> 不得直接作 arterial mechanism attribution
- `OBSERVABILITY_BLOCKED` -> 转向外部 LTA 数据或其他独立观测

## Gates
| Check | Result | Detail |
|---|---|---|
| E1.01_PREREG_HASH | PASS | 4d5ee3e171674ee75094d3aa3eabc09ab8d0591abd9821fe20199cd8ed46751d |
| E1.02_ZERO_SIMULATION | PASS | ast audit: banned_modules=[] spawn_attr_calls=[] |
| E1.03_NETWORK_FIELDS_AND_UNIQUE | PASS | usable_directed_links=706,554 |
| E1.04_NODE_COORDINATE_COVERAGE | PASS | links_with_endpoint_xy=706,554 |
| E1.05_TRAFFIC_LINK_UNIVERSE | PASS | traffic_links=1,311; minimum=1,278 |
| E1.06_AB_COVERAGE_GE_80PCT | PASS | coverage=0.974828 |
| E1.07_AB_P90_DISTANCE_LE_50M | PASS | p90_distance_m=2.923 |
| E1.08_RESIDUAL_SECTIONS_GE_576 | PASS | sections=576 |
| E1.09_RESIDUAL_COUPLING_SUPPORT | FAIL | valid_residual=576; arterial=0 |
| E1.10_ARTERIAL_OBSERVABILITY_GE_30 | FAIL | AB_arterial_residual_n=0; required=30 |
| E1.11_OUTPUT_ISOLATION | PASS | outputs isolated under reports/arterial_observability_7_9e1 |
| E1.12_PROVENANCE_READY | PASS | manifest includes sha256/mtime/size |

Script SHA256: `74491d9daaf995b3a1df53d300b10b6abbe6e2a1a0e2ff2ce80ff5ceb0981a3c`
