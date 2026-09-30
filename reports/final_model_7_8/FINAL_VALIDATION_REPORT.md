# FINAL_VALIDATION_REPORT — Singapore_OD_MATSim_Final_v1.0

> Step 7.8C｜主验证臂 **W01**｜零仿真只读｜生成 2026-09-19 21:44:51


## 1. 主结果（W01）

| 项 | 值 |
|---|---|
| N_sim | 236,044 |
| f_work | 1.180222 |
| f_realized | 1.1801564117192442 |
| FROZEN Sim/Obs | 0.9993347697 |
| implied f* | 1.180865862869697 |

## 2. 稳定性

| 指标 | 值 | 阈值 | 结论 |
|---|---|---|---|
| A_10:19 MATCHED | 0.8899% | < 3.0% | PASS |
| A_10:19 CATA | 0.9038% | < 3.0% | PASS |
| A_10:19 SLIP | 0.8568% | < 5.0% | PASS |
| parity gap | 0.0964% | < 5.0% | PASS |
| Q19/Qbar | 1.001972 | |x-1| <= 1% | PASS |
| never_arrived | 0 | == 0 | PASS |
| max_stuck_car | 0 | == 0 | PASS |
| departure | 236,044 | = | OK |
| arrival | 236,044 | = | OK |

## 3. 口径未漂移（跨步对账）

| 对账项 | 本步值 | 参照 | |Δ| | 容差 | 结论 |
|---|---|---|---|---|---|
| R01.FROZEN | 0.8589731566853055 | 0.8589732 | 4.331e-08 | 1e-06 | PASS |
| R01.POSITIVE_ONLY | 0.9350621136690538 | 0.9350621 | 1.367e-08 | 1e-06 | PASS |
| R01.BEST_DIRECTION | 0.8909673512315488 | 0.8909674 | 4.877e-08 | 1e-06 | PASS |
| R01.Qbar_10_19.MATCHED | 4567961.5 | 4567961.5 | 0.000e+00 | 1e-09 | PASS |
| R01.Qbar_10_19.CATA | 3210503.5 | 3210503.5 | 0.000e+00 | 1e-09 | PASS |
| R01.Qbar_10_19.SLIP | 1357458.0 | 1357458.0 | 0.000e+00 | 1e-09 | PASS |
| R01.Qbar_10_19.ALL | 68252699.5 | 68252699.5 | 0.000e+00 | 1e-09 | PASS |

## 4. 空间残差（保留，不消除）

> **Final Model — Known Spatial Residual Boundary**。7.7D 已证：需求规模 / λ / 车型构成 / 时间实现均**不能**解释；road class / aggregation / observation semantics 已**排除**；剩余收缩到 **PA/OD spatial allocation · twin representation · directionality · section-network correspondence** ⇒ `UNRESOLVED_STRUCTURAL_LAYER`。

| 层级 | 组 | n_sections | ratio | rel_dev vs global |
|---|---|---|---|---|
| region | CENTRAL REGION | 112 | 0.9212 | -7.82% |
| region | EAST REGION | 133 | 0.682 | -31.75% |
| region | NORTH REGION | 72 | 1.2301 | +23.09% |
| region | NORTH-EAST REGION | 77 | 1.3379 | +33.88% |
| region | WEST REGION | 180 | 1.0277 | +2.84% |
| radial | circumferential | 154 | 1.0954 | +9.61% |
| radial | radial_in | 164 | 0.6928 | -30.67% |
| radial | radial_out | 256 | 1.1442 | +14.50% |

### 关键 PA

| PA | n_sections | ratio | rel_dev vs global |
|---|---|---|---|
| ORCHARD | 2 | 2.4184 | +142.00% |
| BUKIT TIMAH | 15 | 2.3845 | +138.61% |
| OUTRAM | 4 | 2.3154 | +131.69% |
| MUSEUM | 2 | 1.9696 | +97.10% |
| TUAS | 11 | 0.13 | -86.99% |
| HOUGANG | 1 | 0.1301 | -86.98% |
| NOVENA | 11 | 1.8405 | +84.17% |
| YISHUN | 14 | 1.7803 | +78.15% |
| KALLANG | 20 | 0.2707 | -72.91% |
| ANG MO KIO | 28 | 1.6804 | +68.15% |

## 5. 归因收口三类（7.7D 继承）

**已解释**

- `global_level_f`：f_work = 1.180222（7.6F-1/7.6H：Sim/Obs FROZEN=0.9993348）
- `impedance_lambda`：λ_ref=0.075，λ 敏带 [1.1637,1.1938]（7.6G：可检测不可识别/空间惰性）
- `mode_composition_global`：car_share_pmv=0.682452↔D01 Sim/Obs 0.6830（7.7A：仅总体水平）

**已排除**

- global demand level
- lambda as spatial explanation
- vehicle/mode composition as spatial explanation
- temporal realization as primary spatial explanation
- section_crosswalk
- observation_semantics
- network_representation
- road_class

**未解释（结构性层）**

- PA/OD spatial allocation
- reciprocal/twin network representation
- directionality
- section-to-network correspondence at twin/direction level

> 结论边界：本步骤不证明 twin/directionality 已构成因果机制，仅证明当前证据链下其他已检验层不足以解释剩余空间残差，故剩余问题被收缩到结构性层

