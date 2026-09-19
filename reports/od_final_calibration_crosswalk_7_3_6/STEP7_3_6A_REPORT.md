# Step 7.3.6A — Final Calibration Crosswalk

## Status

**PASS** — 零仿真；不修改 MATSim 网络/模型参数，不改 OD / λ / Population /
Departure / Capacity / Route-Choice，7.1 冻结靶场保持不动。本步产出**新的、
语义正确的评价映射**，供 7.3.6B 与后续 7.4 使用。

### Scope（重要）

本表覆盖 7.3 诊断所锁定的两类错配断面：**CATA** 与 **SLIP_ROAD**
（合计 590 / 1,311 断面）。其余 RoadCat
（CATB / CATC / CATD / CATE）**不在本表内**，其评价仍沿用 6.3.2 / 7.3.4 基底。
若 7.4 需要全网分等级校准，应按同一规则另行扩展（后续步骤）。

### Hard semantic rules

- `CATA` → **motorway**（direction ≤ 30°，name 仅辅助）
- `SLIP_ROAD` → **motorway_link**（direction + geometry，**RoadName 不作硬约束**）

### Tier（分层选择）

- CATA：`CATA_T1_DIRECTION_SEMANTIC`
- SLIP：`SLIP_T1_DIRECTION_NAME` → `SLIP_T2_DIRECTION_GEOMETRY` →
  `SLIP_T3_GEOMETRY_ONLY`（geometry fallback，带 flag）
- 无可靠候选 → **UNMATCHED**（不强行匹配）

### N 上限

CATA ≤ 10，SLIP ≤ 8；超出 → `selection_status = REVIEW`
（保留但标记，不自动采信）。

## Results

| 指标 | CATA | SLIP_ROAD |
|---|---:|---:|
| 观测断面数 | 339 | 251 |
| 匹配断面数 | 326 | 250 |
| 覆盖率 | 96.17% | 99.60% |
| 纯度（全部边=期望等级） | 100.00% | 100.00% |
| UNMATCHED | 13 | 1 |

- Final crosswalk rows: **3,193**
- mean links / section: **5.54**
- median links / section: **4**
- max links / section: **31**（p90 = 11）
- REVIEW sections: **109**（18.47%；N 超上限，保留但标记）
- shared MATSim edge rate: **4.87%**
- residual opposite-direction share: **1.10%**
- tier counts (edges) — CATA: {'CATA_T1_DIRECTION_SEMANTIC': 1046} / SLIP: {'SLIP_T2_DIRECTION_GEOMETRY': 1515, 'SLIP_T1_DIRECTION_NAME': 597, 'SLIP_T3_GEOMETRY_ONLY': 35}

### 断面边数分布（已匹配断面）

| RoadCat | mean | median | p90 | max | REVIEW (N 超限) |
|---|---:|---:|---:|---:|---:|
| CATA | 3.21 | 3 | 6 | 17 | 4 |
| SLIP_ROAD | 8.59 | 8 | 15 | 31 | 105 |

> SLIP 中位边数 ≈ 8，恰在 N≤8 上限附近，
> 故 REVIEW 比例偏高（SLIP 105/251）。
> 这是 OSM 匝道微段化的正常结果，**REVIEW 只是标记**；若需收紧，可调高
> `--slip-n-max`（例如 12）重跑，聚合口径仍为 median。

## Gates

| Gate | 判据 | 实测 | 结果 |
|---|---|---|---|
| G1 CATA 语义 | >95% | 100.00% | ✅ |
| G1 SLIP 语义 | >90% | 100.00% | ✅ |
| G2 对向边 | <10% | 1.10% | ✅ |
| G3 CATA 覆盖 | >95% | 96.17% | ✅ |
| G3 SLIP 覆盖 | >95% | 99.60% | ✅ |

> 说明：纯度由构造保证（CATA 仅保留 `motorway`、SLIP 仅保留 `motorway_link`），
> 因此 G1 的判别力主要在**覆盖率**与**未匹配断面**；真正的差异在 7.3.6B 的
> Sim/Obs 回测中体现。
>
> **REVIEW 语义**：N 超上限的断面**仍保留在 crosswalk 中**，只是被标记为
> `REVIEW`；由于 7.1 口径的断面聚合采用 **median**，微段链较长本身不会引入
> 系统性偏差，故 REVIEW 是"待人工复核"标记而非剔除条件。
>
> **UNMATCHED 语义**：找不到方向+语义一致的候选时保留 `UNMATCHED`，
> **不强行匹配**（部分 CATA 未匹配断面只有方向相反的主线候选，宁缺勿滥）。

## Interpretation

这张 Final Calibration Crosswalk 才允许进入后续 TrafficFlow calibration。
它不改变 MATSim 模型本身，也不覆盖 7.1 冻结靶场。

7.3.6B 将用本表 + 已运行的 6.3.3B linkstats 做 old / 7.3.4 / final 三方回测，
直接回答 CATA / SLIP 的 Sim/Obs 是否收敛到 1。

## Outputs

- `final_calibration_crosswalk.csv`
- `final_section_summary.csv`
- `final_cata_summary.csv`
- `final_slip_summary.csv`
- `crosswalk_edge_overlap.csv`
- `crosswalk_quality_summary.csv`
- `step7_3_6a_summary.json`
- `STEP7_3_6A_REPORT.md`
