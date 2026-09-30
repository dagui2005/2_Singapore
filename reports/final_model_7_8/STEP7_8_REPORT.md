# STEP 7.8 — Final Model Freeze & Validation Package

> Singapore_OD_MATSim_Final_v1.0｜判决 **`FINAL_MODEL_FROZEN_AND_REPRODUCIBLE`**｜硬门 23/23｜零仿真｜0.1 s


## 0. 定位

7.8 从「研究」切换到「定版」：不再产生新分析结论，而是把 7.3→7.7D 的证据链整理成不可歧义、可复现、可引用的最终版本。


## 1. 交付产品（6 件）

| 文件 | 字节 | sha256(16) |
|---|---|---|
| FINAL_MODEL_SPECIFICATION.md | 4227 | 4e4d40876f1cfc86 |
| FINAL_VALIDATION_REPORT.md | 3863 | b002cb5ef7fe7bd4 |
| FINAL_PARAMETER_FREEZE.json | 2988 | 168ef3328946ce79 |
| FINAL_VALIDATION_METRICS.csv | 1058 | af38a8a06ae479fc |
| FINAL_SPATIAL_RESIDUAL_BOUNDARY.csv | 5647 | fd729d28bf09328c |
| FINAL_MODEL_MANIFEST.json | 8242 | fc84f5fdb2735ce3 |

## 2. 模型身份

```json
{
  "step": "7.8",
  "f_work": 1.180222,
  "lambda_ref": 0.075,
  "scale": 2.29897,
  "f_cap": 1.0,
  "route_choice": "R01_rc_min",
  "sim_agents": 236044,
  "n_base": 200000,
  "crosswalk": "7.3.6A",
  "calibration_target": 0.8589732,
  "validation": "W01",
  "spatial_residual_status": "UNRESOLVED_STRUCTURAL_LAYER",
  "primary_metric": "MATCHED Sim/Obs (08-09)",
  "primary_window": "Qbar_10:19",
  "reference_window": "Q_19"
}
```


## 3. 完整性门（#168，23 条）

| 门 | 检查 | 结论 | 证据 |
|---|---|---|---|
| G1 | FINAL f_work == 7.6H working_point.f_demand_ref（逐位） | PASS | 1.180222 vs 1.180222 |
| G2 | FINAL lambda_ref == 7.6H working_point.lambda_ref（逐位） | PASS | 0.075 vs 0.075 |
| G3 | FINAL SCALE == 2.29897 == 7.6H scale_used（逐位） | PASS | 2.29897 vs 2.29897 |
| G4 | FINAL sim_agents == 236,044 == 7.6H h1.N_sim | PASS | 236044 |
| G5 | FINAL Sim/Obs FROZEN == 7.6H h1.SimObs_FROZEN（逐位） | PASS | 0.9993347696792919 |
| G6 | FINAL calibration_target 复现 7.6C-2 R01.FROZEN（tol 1e-6） | PASS | ours=0.8589731566853055 published=0.8589732 Δ=4.331e-08 |
| G7 | FINAL implied f* == 7.6H h1.implied_fstar_FROZEN（逐位） | PASS | 1.180865862869697 |
| G8 | W01 config route-choice 继承 7.6E 四项 | PASS | innov=0.8 strat={'ReRoute': '0.15', 'ChangeExpBeta': '0.85'} lr=0.5 rnd=0.0 |
| G9 | W01 config 运行控制（seed/iters/algo/mobsim/f_cap） | PASS | seed=4711 it=19 algo=SpeedyALT mobsim=qsim fcap=1.0 |
| G10 | 全部冻结输入存在（14 件） | PASS | n=14 missing=[] |
| G11 | config 引用的 network / plans 文件存在 | PASS | network=True plans=True |
| G12 | OD 结构不变：正 cell == 71,136 | PASS | 71136 |
| G13 | car_od_total == 459,794（口径锚） | PASS | 459793.999993 |
| G14 | 三层带独立、未合并为单区间 | PASS | bands_merged=False |
| G15 | 空间残差仍存在（EAST / radial_in 未消失） | PASS | EAST=-31.75% radial_in=-30.67% |
| G16 | 7.7D 收口判决一致（未解释层 = 结构性层） | PASS | verdict=SPATIAL_RESIDUAL_ATTRIBUTION_CLOSED_WITH_UNRESOLVED_STRUCTURAL_LAYER unresolved=4 |
| G17 | 7.7C-1 时段上界门 = FAIL_DEFER_HTS（口径一致） | PASS | TEMPORAL_SPATIAL_SENSITIVITY_FAIL_DEFER_HTS |
| G18 | 7.7C-0 归因基线已落盘（eta2 排序可用） | PASS | n_dims=11 top=pa_location |
| G19 | 7.7A 构成归因已落盘（解释总体量级） | PASS | VEHICLE_TYPE_VOLUME_UNAVAILABLE |
| G20 | 本步纪律：zero_simulation / 未改任何冻结参数 | PASS | params_changed=False lambda_selected=False demand_scale_selected=False |
| G21 | 六件正式产品全部落盘且非空 | PASS | present=6/6 |
| G22 | 所有冻结输入跑前后 mtime+sha256 逐位未变（read-only 证据） | PASS | changed=[] |
| G23 | W01 验证臂 it.19 产物存在 | PASS | outputs=True it19=True |

## 4. 空间残差边界（保留，不消除）

- 状态：**`UNRESOLVED_STRUCTURAL_LAYER`**（55 行边界表）

- 未解释结构性层：PA/OD spatial allocation、reciprocal/twin network representation、directionality、section-to-network correspondence at twin/direction level

- 结论边界：本步骤不证明 twin/directionality 已构成因果机制，仅证明当前证据链下其他已检验层不足以解释剩余空间残差，故剩余问题被收缩到结构性层


## 5. 版本线与停止规则
```text

7.3 Calibration Crosswalk Freeze
7.4 Capacity / Sampling Freeze
7.6E Route-choice Freeze
7.6F Demand Working Point
7.6G Lambda Identification Boundary
7.6H Independent Validation
7.7A Vehicle/Mode Exclusion
7.7C-0 Spatial Attribution
7.7C-1 Temporal Upper Bound
7.7D Spatial Residual Closure
7.8 FINAL MODEL FREEZE -> Singapore_OD_MATSim_Final_v1.0

```


- **停止规则**：7.8 完成后 STOP。若继续研究，属新研究问题 7.9 Structural Repair / Model v1.1，而非继续把 v1.0 的 Sim/Obs 从 0.9993 调到 1.00。


## 6. 纪律

- `zero_simulation=True` / `matsim_rerun=False` / `parameters_changed=False` / `lambda_selected=False` / `demand_scale_selected=False` / `frozen_artifacts_touched=False`

- 全部冻结输入跑前后 mtime+sha256 逐位未变（G22）

