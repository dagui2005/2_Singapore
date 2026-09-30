# Step 7.7D — Spatial Residual Attribution Closure

## 0. 判决问题

> 在不新增任何 calibration knob 的前提下，现有证据链是否足以 **关闭空间残差归因**？
> 即：模型总体交通量已完成独立验证，而空间残差不能由需求规模 / 阻抗参数 /
> 车型构成 / 时段实现等 **标量/时序** 因素消除，其剩余差异收敛于
> **OD 空间配置 + 观测断面-网络 方向/对偶链路对应关系**？

本步骤是 **收口审计**，不是新分析模型；不创造任何新的解释变量。

## 1. 方法

跨步骤一致性审计 + 未解释残差边界收口。只读复用 7.6H W01 / 7.7A / 7.7C-0 / 7.7C-1。
**缺证据 => BLOCKED，有证据但不满足 => FAIL；不猜。**

- MATSim rerun: **False** ｜ parameters changed: **False**
- 新增解释变量: **False**

## 2. Gates（hard 7/7 PASS）

| check | type | status | evidence |
|---|---|---|---|
| G1_W01_ANCHOR | hard | PASS | {"sim_obs": 0.9993347696792919, "east": -0.3175244561953319, "radial_in": -0.3067274364274516, "ne": 0.3388326175136829} |
| G2_C0_ARTIFACT_CHAIN | hard | PASS | {"summary": "D:\\Luan\\2026-05\\2_Singapore\\reports\\spatial_residual_7_7c0\\step7_7c0_summary.json", "rank": "D:\\Luan\\2026-05\\2_Singapore\\report |
| G3_DEMAND_SCALE_SPATIAL_PERSISTENCE | soft | PASS | {"runs": ["R01", "F05", "F15", "F25"], "order_preserved": true, "max_span_pp": 1.851} |
| G4_LAMBDA_SPATIAL_INERT | soft | PASS | {"runs": ["R01", "L05", "L75", "L10"], "order_preserved": true, "max_span_pp": 3.227} |
| G5_TWIN_DIRECTION_STRUCTURE | hard | PASS | {"radial_in_recip_false": 0.991541483270678, "radial_out_recip_false": 1.3546078387934963, "radial_in_recip_true": 0.1738224662140466, "cells_total":  |
| G6_TEMPORAL_BOUND | hard | PASS | {"ratio": 0.11040439333313766, "gate": "TEMPORAL_SPATIAL_SENSITIVITY_FAIL_DEFER_HTS"} |
| G7_VEHICLE_MODE_SPATIAL_EXCLUSION | hard | PASS | {"judgment": "VEHICLE_TYPE_VOLUME_UNAVAILABLE / COMPOSITION_EXPLAINS_GLOBAL_LEVEL_NOT_SPATIAL_PATTERN", "checks": "6/6"} |
| G8_EXCLUDED_LAYERS | hard | PASS | {"metric": "eta2_excess", "layers": {"section_crosswalk": -0.0021, "observation_semantics": -0.0004, "network_representation": -0.0017, "road_class":  |
| G9_UNRESOLVED_BOUNDARY_EXPLICIT | hard | PASS | {"unresolved": ["PA/OD spatial allocation", "reciprocal/twin network representation", "directionality", "section-to-network correspondence at twin/dir |

## 3. 归因三类

### 已解释（explained）

| 类别 | 结论 |
|---|---|
| global | f_work = 1.180222（7.6F-1/7.6H：Sim/Obs FROZEN=0.9993348） |
| impedance | λ_ref=0.075，λ 敏带 [1.1637,1.1938]（7.6G：可检测不可识别/空间惰性） |
| mode | car_share_pmv=0.682452↔D01 Sim/Obs 0.6830（7.7A：仅总体水平） |

### 已排除（excluded）

`global demand level`, `lambda as spatial explanation`, `vehicle/mode composition as spatial explanation`, `temporal realization as primary spatial explanation`, `section_crosswalk`, `observation_semantics`, `network_representation`, `road_class`

### 尚未解释（unexplained，收缩到结构性层）

- `PA/OD spatial allocation`
- `reciprocal/twin network representation`
- `directionality`
- `section-to-network correspondence at twin/direction level`

## 4. 冻结工作点

| 参数 | 值 |
|---|---|
| λ_ref | 0.075 |
| f_work | 1.180222 |
| N_sim | 236,044 |
| SCALE | 2.29897 |
| λ 敏感带 | [1.1637, 1.1938] |
| 静态靶场带 | [1.06945, 1.16418] |

## 5. 结论边界（必须随结论引用）

> 本步骤不证明 twin/directionality 已构成因果机制，仅证明当前证据链下其他已检验层不足以解释剩余空间残差，故剩余问题被收缩到结构性层。

因此结论 **不是**「残差就是 twin/directionality 导致的」，
而是 **「其他已检验层不足以解释剩余空间残差，问题被收缩到结构性层」**。

## 6. 证据清单（只读输入）

| artifact | exists | sha256_16 | mtime |
|---|---|---|---|
| matsim_final_7_6h/audit/od_final_workingpoint_7_6h_summary.json | OK | c9965daf52789107 | 2026-09-18 23:11:16 |
| matsim_final_7_6h/audit/final_workingpoint_7_6h_h3_spatial.csv | OK | d802c980e5d2fa97 | 2026-09-18 23:11:16 |
| reports/spatial_residual_7_7c0/step7_7c0_summary.json | OK | 82e4336f780804b3 | 2026-09-19 08:02:35 |
| reports/spatial_residual_7_7c0/c0_rank_eta2.csv | OK | f7af3432b974b2e4 | 2026-09-19 08:02:35 |
| reports/spatial_residual_7_7c0/c0_4_radial_x_reciprocal.csv | OK | 853d19c298527303 | 2026-09-19 08:02:34 |
| reports/spatial_residual_7_7c0/c0_2_directionality_stability_across_f_lambda.csv | OK | 0da7eadd68f82f2f | 2026-09-19 08:02:34 |
| reports/spatial_temporal_sensitivity_7_7c1/c1_summary.json | OK | 704b9a1c7543d1f6 | 2026-09-19 09:08:09 |
| reports/spatial_temporal_sensitivity_7_7c1/c1_radial_reciprocal.csv | OK | 668d5bb0cfd38da3 | 2026-09-19 09:08:09 |
| reports/external_validation_7_7/step7_7a_summary.json | OK | 65b7c61bb0399116 | 2026-09-19 07:14:50 |
| matsim_demand_7_6f_1/audit/demand_response_spatial_residuals.csv | OK | bc9cd4f145cf2c78 | 2026-09-18 00:14:59 |
| matsim_lambda_7_6g/audit/lambda_sensitivity_spatial_residuals.csv | OK | 0edeae5d32d5ee6e | 2026-09-18 20:42:58 |

## 7. 收口判决

**`SPATIAL_RESIDUAL_ATTRIBUTION_CLOSED_WITH_UNRESOLVED_STRUCTURAL_LAYER`**

- 硬门 7/7 PASS ｜ 软门 2/2 PASS
- 零仿真 / 未跑 MATSim / 未改冻结件：**True**
- 运行 0.1 s

## 8. 产物清单（`reports/spatial_residual_closure_7_7d/`）

- `d_checks.csv`
- `d_closure_summary.json`
- `STEP7_7D_REPORT.md`
