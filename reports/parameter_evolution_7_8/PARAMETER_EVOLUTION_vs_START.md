# 7.8 定版参数 vs 起点 —— 逐项对照

- 起点：`matsim\step6_3\config_lambda_0p075.xml`（6.3 最初的 MATSim 分配配置）
- 定版：`matsim_final_7_6h\configs\config_W01_rc_min.xml`（Singapore_OD_MATSim_Final_v1.0 / W01）
- 全展开键数 **195**（含 `<parameterset>`）；起点↔定版差异 **14** 项，其中**实质参数 11** 项。

## 0. 各阶段的策略集（单列，因通用键会合并同名策略）

| 阶段 | route-choice 策略集 |
|---|---|
| S0 起点 6.3 起点：最早 MATSim 分配（单迭代） | `ReRoute:1.0` |
| S1 6.3.3B：逐小时出发剖面 | `ReRoute:1.0` |
| S2 7.2.2：容量敏感性（仍单迭代） | `ReRoute:1.0` |
| S2b 7.4.2 Phase 1（E01–E03：λ0.050 × capacity 扫描，首个 20 迭代） | `ReRoute:1.0` |
| S3 7.4.3 D02：demand scale 校准期（20 迭代） | `ReRoute:1.0` |
| S4 7.6D R01：route-choice 修复 | `ReRoute:0.15 + ChangeExpBeta:0.85` |
| S5 定版 7.8 W01：定版运行 | `ReRoute:0.15 + ChangeExpBeta:0.85` |
| S6 7.8-VIZ：仅输出层重跑（非新版本） | `ReRoute:0.15 + ChangeExpBeta:0.85` |

## A. 实质参数变化（按机制）

### 收敛/迭代

| 参数 | 起点 | 定版 | 首次变更于 |
|---|---|---|---|
| `controller.lastIteration` | 0 | **19** | 7.4.2 Phase 1（E01–E03：λ0.050 × capacity 扫描，首个 20 迭代） |

### 输出开关

| 参数 | 起点 | 定版 | 首次变更于 |
|---|---|---|---|
| `controller.writeEventsInterval` | 1 | **0** | 7.4.2 Phase 1（E01–E03：λ0.050 × capacity 扫描，首个 20 迭代） |
| `controller.writePlansInterval` | 1 | **0** | 7.4.2 Phase 1（E01–E03：λ0.050 × capacity 扫描，首个 20 迭代） |
| `controller.writeSnapshotsInterval` | 1 | **0** | 7.4.2 Phase 1（E01–E03：λ0.050 × capacity 扫描，首个 20 迭代） |
| `controller.writeTripsInterval` | 1 | **0** | 7.4.2 Phase 1（E01–E03：λ0.050 × capacity 扫描，首个 20 迭代） |

### qsim 车辆识别

| 参数 | 起点 | 定版 | 首次变更于 |
|---|---|---|---|
| `qsim.usePersonIdForMissingVehicleId` | true | **false** | 6.3.3B：逐小时出发剖面 |

### 路径选择扰动

| 参数 | 起点 | 定版 | 首次变更于 |
|---|---|---|---|
| `routing.routingRandomness` | 3.0 | **0.0** | 6.3.3B：逐小时出发剖面 |

### ★route-choice 策略集

| 参数 | 起点 | 定版 | 首次变更于 |
|---|---|---|---|
| `replanning.<strategysettings>.strategyName` | ReRoute | **ChangeExpBeta** | 7.6D R01：route-choice 修复 |
| `replanning.<strategysettings>.weight` | 1.0 | **0.85** | 7.6D R01：route-choice 修复 |
| `replanning.fractionOfIterationsToDisableInnovation` | Infinity | **0.8** | 7.6D R01：route-choice 修复 |
| `scoring.learningRate` | 1.0 | **0.5** | 7.6D R01：route-choice 修复 |

## B. 需求 / 评价层（不全是 config 参数）

| 项 | 类别 | 起点 | 定版 | 依据 |
|---|---|---|---|---|
| 需求规模 f | 需求 | 1.00（无缩放，200,000 agent 全量投递） | **1.180222** | 7.6G L75 直跑实测隐含 f*；7.6H 冻结 |
| 被仿真 agent 数 N_sim | 需求 | 200,000 | **236,044** | W01 = round(f_work × N_base)，物理加车 |
| 采样基准 N_base | 采样 | 200,000 | **200,000（未变）** | 7.4.3′ 冻结；100k 方案已否决（7.5A/7.5B） |
| 重力衰减 λ | OD 构造 | 未选定；5A/5C1 起即 5 档扫描 {0.05,0.075,0.10,0.125,0.15} | **0.075（工作中心，⛔ 非最优 λ）** | 7.6G 敏感度中心；λ 由人口承载，config 内无形参 |
| 扩样系数 SCALE | 评价层（不进仿真） | 未引入（评价用原始 linkstats 加总） | **2.29897 = ΣT/N_base** | 7.5A 审计：MATSim 不消费 expansionFactor/odTrips |
| 供给容量 f_cap | 供给 | 1.00 | **1.00（未变）** | 7.4.1 矩阵扫 0.50/0.75/1.00 ⇒ f=1.00 全面占优 |
| 随机种子 randomSeed | 运行 | 4711 | **4711（未变）** | 6.3 起硬编码；7.4.1 曾纠正草案误写 20260912 |
| 迭代数 | 运行 | 1（lastIteration=0） | **20（lastIteration=19）** | 7.4.1 校准矩阵起 |
| 观测靶场 | 评价层 | 6.3.2 crosswalk（1,278 断面，it.0） | **7.1 冻结观测 + 7.3.6A（576 断面 / 574 primary）** | 7.3.6A 冻结；主口径池化 FROZEN |
| 标定靶值 | 评价层 | 逐窗口 sim_obs_ratio（无单一靶值） | **0.8589732（576 断面池化）** | 7.6C-2 FROZEN 主口径 |
| 稳定性判据 | 评价层 | 无（单迭代） | **双口径 A_10:19 + Q_19，须 MATCHED** | 7.6B′ 裁定 / 7.6E 冻结 |

## C. 非实质差异（不计入参数变化）

| 参数 | 类别 | 起点 | 定版 |
|---|---|---|---|
| `controller.outputDirectory` | 路径/命名（provenance） | D:\Luan\2026-05\2_Singapore\reports\matsim_assignment\lambda_0p075 | D:\Luan\2026-05\2_Singapore\matsim_final_7_6h\outputs\W01_rc_min |
| `controller.runId` | 路径/命名（provenance） | step6_3_lambda_0p075 | W01_rc_min |
| `plans.inputPlansFile` | 路径/命名（provenance） | D:\Luan\2026-05\2_Singapore\reports\matsim_population_6_2b_connected\population_lambda_0p075.xml.gz | D:\Luan\2026-05\2_Singapore\matsim_final_7_6h\populations\pop_W01\population_lambda_0p075.xml.gz |

## D. 阶段图例

| 代号 | 含义 | 配置 |
|---|---|---|
| S0 起点 | 6.3 起点：最早 MATSim 分配（单迭代） | `matsim\step6_3\config_lambda_0p075.xml` |
| S1 | 6.3.3B：逐小时出发剖面 | `matsim\step6_3\config_lambda_0p075_6_3_3b.xml` |
| S2 | 7.2.2：容量敏感性（仍单迭代） | `reports\od_calibration_7_2_2\capacity_factor_1p00\cap_f_1p00.output_config.xml` |
| S2b | 7.4.2 Phase 1（E01–E03：λ0.050 × capacity 扫描，首个 20 迭代） | `reports\od_calibration_7_4_2\E03_lam0p050_cap1p00\E03.output_config.xml` |
| S3 | 7.4.3 D02：demand scale 校准期（20 迭代） | `reports\od_calibration_7_4_3\D02_lam0p075\D02.output_config.xml` |
| S4 | 7.6D R01：route-choice 修复 | `matsim_routechoice_7_6d\configs\config_R01_rc_min.xml` |
| S5 定版 | 7.8 W01：定版运行 | `matsim_final_7_6h\configs\config_W01_rc_min.xml` |
| S6 | 7.8-VIZ：仅输出层重跑（非新版本） | `matsim_viz_7_8\configs\config_W01_events.xml` |

## E. 校验：19/19 PASS

| 门 | 说明 | 结果 |
|---|---|---|
| K1 | 起点与定版的 config 键集完全一致（同一模板） | ✅ PASS |
| K1b | 其余阶段多出的键仅为 MATSim 转储的序列化项 | ✅ PASS |
| K-RC-fractionOfIteratio | 定版继承 7.6D 的 replanning.fractionOfIterationsToDisableInnovation | ✅ PASS |
| K-RC-learningRate | 定版继承 7.6D 的 scoring.learningRate | ✅ PASS |
| K-RC-strategyName | 定版继承 7.6D 的 replanning.<strategysettings>.strategyName | ✅ PASS |
| K-RC-weight | 定版继承 7.6D 的 replanning.<strategysettings>.weight | ✅ PASS |
| K-SAME-randomSeed | global.randomSeed 起点=定版（未变） | ✅ PASS |
| K-SAME-flowCapacityFactor | qsim.flowCapacityFactor 起点=定版（未变） | ✅ PASS |
| K-SAME-storageCapacityFac | qsim.storageCapacityFactor 起点=定版（未变） | ✅ PASS |
| K-SAME-inputNetworkFile | network.inputNetworkFile 起点=定版（未变） | ✅ PASS |
| K-SAME-coordinateSystem | global.coordinateSystem 起点=定版（未变） | ✅ PASS |
| K-SAME-mainMode | qsim.mainMode 起点=定版（未变） | ✅ PASS |
| K-SAME-routingAlgorithmTy | controller.routingAlgorithmType 起点=定版（未变） | ✅ PASS |
| K-EVENTS | 定版 writeEventsInterval=0（VIA 无 events 的根因） | ✅ PASS |
| K-VIZ | 7.8-VIZ 白名单差异恰好 3 项（含 outputDirectory/runId） | ✅ PASS |
| K-RC-PAIR | 策略集：起点 ReRoute:1.0 单策略 → 定版 ReRoute:0.15 + ChangeExpBeta:0.85 | ✅ PASS |
| K-RC-PAIR-N | 定版策略权重和 == 1.0 | ✅ PASS |
| K-FWORK | 定版 f_work == 1.180222 | ✅ PASS |
| K-NSIM | N_sim == round(f_work × 200000) | ✅ PASS |

> ⛔ 本件为 **read-only 附加件**，不属 7.8 冻结产品；未改任何冻结输入，未启动 MATSim。
