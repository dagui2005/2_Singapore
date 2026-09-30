# FINAL_MODEL_SPECIFICATION — Singapore_OD_MATSim_Final_v1.0

> Step 7.8A（参数冻结）+ 7.8B（输入与算法冻结）｜生成 2026-09-19 21:44:51｜**零仿真定版**

> 本文件是最终模型的**版本锁**。7.8 之后任何修改下列条目，都属于**新模型版本**，不属于「最终模型参数调整」。


## 1. 7.8A 参数冻结（Final Parameter Freeze）

| 项目 | 最终值 | 来源 | 类型 |
|---|---|---|---|
| f_work | 1.180222 | 7.6G L75 direct（7.6H 冻结） | working_point |
| lambda_ref | 0.075 | 7.6G sensitivity center（⛔ 非最优 λ） | working_point |
| SCALE | 2.29897 | 7.4/全流程冻结；ΣT/N_base | sampling_anchor |
| f_cap | 1.0 | 7.4 capacity freeze | capacity |
| route_choice | R01_rc_min | 7.6E route-choice freeze | route_choice |
| sim_agents | 236044 | W01 = round(f_work × N_base) | validation |
| crosswalk | 7.3.6A | 7.3.6A Frozen Final Crosswalk（只读） | target |
| calibration_target | 0.8589732 | 7.6C-2 FROZEN 三口径之主口径 | target |
| N_base | 200000 | 采样基准 / SCALE 分母 | sampling_anchor |
| iterations | 20 | 判据取 it.19 linkstats | run |

### 措辞纪律（强制）

> **λ（lambda）**：λ=0.075 作为经过灵敏度分析后的工作中心参数；7.6G 表明 λ 对总体水平具有可检测影响，但在现有观测与误差边界下不足以实现可靠参数识别。⛔ 不得写作『最优 λ / 数据最优 λ』。

> **f_work**：f_work=1.180222 是最终工作点，不意味着需求规模参数具有唯一真实值（总量证据只能给出区间，见 7.6A/7.6G）。


### 三层带（⛔ 不得合并）

| 层 | 值 | 含义 |
|---|---|---|
| working_point | λ=0.075, f*=1.180222 | 条件点估计（7.6G L75 直跑实测） |
| lambda_sensitivity_band | [1.1637, 1.1938] | λ=0.05/0.10 两端的动态响应不确定带 |
| static_target_band | [1.06945, 1.16418] | 7.6C-2 静态靶场识别不确定带 |

- 披露量：`f_realized` = **1.1801564117192442**、`implied_fstar` = **1.180865862869697**、`sum_expansion_factor` = **459793.999993**（`SCALE` 若按 ΣEF/N_sim 重算 = **NOT USED**）


## 2. 7.8B 输入与算法冻结（Input & Algorithm Lock）

| 层 | 冻结条目 |
|---|---|
| Input | Census 2020；ACRA / building / landuse / POI；OSM network；LTA TrafficFlow；existing network / zone mappings |
| OD | 332 Subzones；gravity model；λ = 0.075；IPF；Census workplace controls；attraction disaggregation |
| Sampling | FLOOR_PLUS_1；N_base = 200000；SCALE = 2.29897 |
| Network | frozen MATSim network；f_cap = 1.0；frozen zone → node/link realization |
| Route_Choice | R01_rc_min |
| Calibration_Crosswalk | 7.3.6A |

### 版本线
```text

Singapore_OD_MATSim_Final_v1.0
    ↓ 若发现 twin mapping 等结构问题
不得直接修改 v1.0
    ↓
新建 v1.1 / Structural Repair
```


### 配置指纹（W01 实跑 config）

| 项 | 值 |
|---|---|
| config | matsim_final_7_6h/configs/config_W01_rc_min.xml |
| network | D:\Luan\2026-05\2_Singapore\reports\matsim_network\network_cleaned.xml.gz |
| plans | D:\Luan\2026-05\2_Singapore\matsim_final_7_6h\populations\pop_W01\population_lambda_0p075.xml.gz |
| runId | W01_rc_min |
| lastIteration | 19 |
| randomSeed | 4711 |
| routingAlgorithmType | SpeedyALT |
| mobsim | qsim |
| flowCapacityFactor | 1.0 |
| storageCapacityFactor | 1.0 |
| fractionOfIterationsToDisableInnovation | 0.8 |
| strategies | {"ReRoute": "0.15", "ChangeExpBeta": "0.85"} |
| learningRate | 0.5 |
| routingRandomness | 0.0 |

- 7.6H 相对 R01 的 config 差异**仅 3 项白名单**：

| 模块 | 参数 | R01 值 | W01 值 | 白名单 |
|---|---|---|---|---|
| controller | outputDirectory | D:\Luan\2026-05\2_Singapore\matsim_routechoice_7_6d\outputs\R01_rc_min | D:\Luan\2026-05\2_Singapore\matsim_final_7_6h\outputs\W01_rc_min | True |
| controller | runId | R01_rc_min | W01_rc_min | True |
| plans | inputPlansFile | D:\Luan\2026-05\2_Singapore\reports\matsim_departure_6_3_3a\population_lambda_0p075.xml.gz | D:\Luan\2026-05\2_Singapore\matsim_final_7_6h\populations\pop_W01\population_lambda_0p075.xml.gz | True |
