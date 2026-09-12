# Step 7.2.1 —— MATSim 参数审计（PASS，只审计不改模型）

> 目标：校准前先把当前 MATSim 配置的**实际参数**完整抽取成基线，并给出 capacity-only sensitivity 的实验计划。
> **本阶段不改任何模型参数**：`model_parameters_changed=false`、`lambda_selected=false`。
> 冻结保持不动：3B.1 / 4 / 5B / 5C.1 / 6.1 / 6.2 / 6.2B / 6.3.2 / 6.3.3A / 6.3.3B / 7.1 靶场。

**脚本**：`scripts/od/audit_matsim_calibration_7_2.py`（用户交付，运行前修复 3 处缺陷，见 §4）

---

## 1. 基线 config（`matsim/step6_3/config_lambda_0p050_6_3_3b.xml`）

| 模块 | 参数 | 值 | 审计判读 |
|---|---|---|---|
| qsim | `flowCapacityFactor` | **1.0** | ⚠️ **重大发现：不是预想的 0.435**。0.435 抽样率下网络容量相对需求过剩 ~**2.3×**，QSim 内几乎不形成拥堵 |
| qsim | `storageCapacityFactor` | **1.0** | 同上 |
| qsim | `stuckTime` / `mainMode` | 10.0 / car | — |
| controller | `routingAlgorithmType` | **SpeedyALT** | 最短路路由 |
| controller | `firstIteration` / `lastIteration` | **0 / 0** | 单迭代 ⇒ **`ReRoute` 策略（`maxAgentPlanMemorySize=5`）完全无效**，route choice = 一次性 freespeed 最短路 |
| travelTimeCalculator | `travelTimeBinSize` / `aggregator` / `getter` | 900 s / **optimistic** / average | 单迭代下 TT 估计 = freespeed，无拥堵反馈 |
| controller | `inputNetwork` | `network_cleaned.xml.gz` | 与 6.3a 冻结口径一致 |
| controller | `inputPlans` | `matsim_departure_6_3_3a/population_lambda_0p050.xml.gz` | 与 6.3.3A 冻结口径一致 |

## 2. 网络容量审计（693,575 边，0 无效值）

- capacity 语义 = `permlanes × 等级默认 veh/h/lane`（见 `network_validation.json`）。
- 全网：capacity median **800** / p95 **3,600** veh/h；capacity/lane median **400** / p95 **1,500**。
- XML `permlanes` 全齐且与 CSV lanes 在非缺失处 **0 失配**（CSV lanes 有 272,860 行缺失——service 类为主——已被 6.1 默认值补齐）。

| highway | 边数 | capacity/lane (veh/h) | freespeed 中位 (km/h) |
|---|---:|---:|---:|
| service | 450,486 | 400 | 20 |
| residential | 120,396 | 700 | 50 |
| primary | 25,798 | 1,500 | 60 |
| tertiary | 23,278 | 900 | 50 |
| secondary | 19,806 | 1,200 | 50 |
| motorway_link | 9,026 | 1,700 | 50 |
| primary_link | 8,077 | 1,300 | 50 |
| trunk | 5,091 | 1,800 | 70 |
| **motorway** | **4,744** | **1,900** | **90** |

## 3. 对 7.2.2 capacity-only sweep 的判据（预先固定）

保持 OD / λ / population / departure / topology / route-choice **全部冻结**，只扫 capacity factor **0.50 / 0.75 / 1.00 / 1.25 / 1.50**（见 `capacity_sweep_plan.csv`，**仅计划，不自动执行**）：

- **CATA 显著回升（0.584/0.739 → 1）且 SLIP_ROAD 回落（1.594/2.033 → 1）** ⇒ capacity 主导 → 先校 capacity / `flowCapacityFactor`（理论一致值 0.435）。
- **几乎不动** ⇒ **route choice 效用主导**（freespeed 最短路 + 无拥堵反馈 + 无偏好项）→ 直接进 Step 7.3。
- 观察指标沿用 7.1 靶场：CATA/SLIP_ROAD/CATB 的 Sim/Obs + GEH/RMSE/Pearson r。

**先验判断**：当前系统处于"容量严重过剩"区（1.0 × 0.435 抽样），容量下调到拥堵形成前，路径选择对 capacity factor 的弹性可能很小——若扫描证实，则 route choice 是主因的证据链将闭合。

## 4. 运行前修复的 3 处缺陷

1. **config 参数全 null**：MATSim config_v2 参数在 `<param name="..." value="..."/>` **属性**里而非元素文本，原 `flatten_xml` 只取叶子文本 → 重写为 module/param 名嵌入 path、`value` 作 text。
2. **baseline 误选导出物**：`*.output_config_reduced.xml` 是 MATSim 运行导出物 → 过滤所有 `output_config` 文件，正确选中 authored `config_lambda_0p050_6_3_3b.xml`。
3. **capacity 列不存在**：`network_links_source_copy.csv` 无 capacity 列（原脚本必 KeyError）→ 改为解析 `network_cleaned.xml.gz` 逐边 capacity/permlanes/freespeed，按 `e{from}_{to}` 与 source copy 合并；无效/失配判定以 XML `permlanes` 为准。

## 5. 产物

| 文件 | 说明 |
|---|---|
| `parameter_audit.csv` | 全部 25 个 config XML 逐参数展开（module[param] → value） |
| `config_summary.csv` | config 概览（含基线 config 关键参数） |
| `network_capacity_audit.csv` | 逐 highway 等级：边数 / lanes / permlanes / capacity / capacity-per-lane / freespeed / 长度 |
| `calibration_target_baseline.csv` | 7.1 靶场 summary 基线复制（扫描对照用） |
| `capacity_sweep_plan.csv` | capacity-only 扫描计划（0.50–1.50，**仅计划**） |
| `step7_2_audit.json` | `status=PASS`、`model_parameters_changed=false`、`lambda_selected=false` |

**下一步**：7.2.2 capacity-only sweep（扫描脚本待审计结论确认后编写，勿提前写死）。
