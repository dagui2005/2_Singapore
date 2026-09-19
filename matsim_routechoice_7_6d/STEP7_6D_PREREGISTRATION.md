# Step 7.6D 预注册 — Route-choice 稳定性判据

> **预注册声明**：本文件在 **任何 7.6D MATSim 运行启动之前** 冻结。判据、阈值、口径、
> 窗口、量纲在此确定；**运行之后不得回溯修改**。若确需修改，必须新建 `7.6D-b` 并说明理由。
>
> 冻结时间：2026-09-16（用户裁定后、正式 run 启动前）
> 状态：**配置已生成并验证 19/19 PASS；冒烟预检已执行；正式 20 迭代 run 尚未启动**

---

## 1. 目的（唯一）

把 assignment **从周期-2 振荡变成可接受的稳定状态**。

> **不追求 Sim/Obs 变好。** 7.6B 已证明「让 Sim/Obs 更接近 1」在当前机制下可以通过
> 挑选相位（奇/偶）人为实现 —— 那正是本步骤要消除的假象。若本轮 Sim/Obs 变差，
> 只要振幅达标，仍判定成功。

---

## 2. 唯一变量（最小修复）

针对 7.6B 定位的**两个**机制 —— 「学习过猛」+「持续创新」：

| # | 参数 | 基线（修复前） | 修复后 | 针对机制 |
|---|---|---|---|---|
| 1 | `replanning.fractionOfIterationsToDisableInnovation` | `Infinity` | **`0.8`** | 持续创新（无收尾沉降阶段） |
| 2 | `replanning` 策略集 | `[ReRoute 1.00]` | **`[ReRoute 0.15, ChangeExpBeta 0.85]`** | 持续创新 + 无计划选择算子 |
| 3 | `scoring.learningRate` | `1.0` | **`0.5`** | 学习过猛（得分无指数平滑） |
| 4 | `routing.routingRandomness` | `0.0` | `0.0`（**保留**） | 确定性最短路（显式冻结） |

**为什么保留一个 plan-selection 策略**：`fractionOfIterationsToDisableInnovation = 0.8`
的语义是**迭代 16 起禁用创新策略**；若策略集里没有 `ChangeExpBeta`/`BestScore`，
禁用创新后就没有任何计划选择算子，网络无法沉降。

**为什么第一轮不做参数网格**：若同时改 3 类假设，即使变稳也不知道是哪项起作用
（这正是 7.5A/7.5B 已暴露的「多变量同时变动导致不可识别」问题）。先验证单一组合，
再按 §7 的判读规则决定是否需要第二轮。

---

## 3. 冻结不变量（机器校验，非人工承诺）

以下全部冻结，由 `scripts/od/prepare_routechoice_7_6d.py` 的 **V1–V6 共 19 项校验** 保证：

| 类别 | 冻结项 |
|---|---|
| 网络 | `network.inputNetworkFile` = `reports/matsim_network/network_cleaned.xml.gz` |
| 需求 | `plans.inputPlansFile` = `reports/matsim_departure_6_3_3a/population_lambda_0p075.xml.gz`（**f = 1.00，不加车**） |
| 容量 | `qsim.flowCapacityFactor` = `qsim.storageCapacityFactor` = **`1.00`**（`hermes` 同值） |
| 随机性 | `global.randomSeed` = **`4711`**；`routing.routingRandomness` = **`0.0`** |
| 路由 | `controller.routingAlgorithmType` = `SpeedyALT` |
| 时间分配 | `travelTimeCalculator.travelTimeBinSize` = `900.0`；`travelTimeAggregator` = `optimistic` |
| 测量 | `linkStats.writeLinkStatsInterval` = **`1`**（每迭代 linkstats = 唯一测量需求） |
| 磁盘 | `writeEvents/Plans/Trips/SnapshotsInterval` = `0`（20 it × 200k 不写中间产物） |
| OD / λ | **不重建**；λ = 0.075 的 prior OD 与 6.3.3A 剖面均不动 |
| 靶场 | 7.1 冻结观测 + 7.3.6A Final Crosswalk **不参与 config**，只在评价阶段使用 |

实际 diff：**仅 4 处** —— `controller.outputDirectory`、`controller.runId`（新目录/新 ID）
+ `replanning.fractionOfIterationsToDisableInnovation` + `scoring.learningRate`。
策略集变化在 `<parameterset>` 内（由 V1 校验）。逐参数明细见
`matsim_routechoice_7_6d/routechoice_7_6d_config_provenance.csv`。

---

## 4. 预注册判据

### 4.1 定义

对每个量 `X` 与窗口 `W = [a, b]`：

```
A_W(X) = ( max_{k in W} X_k − min_{k in W} X_k ) / mean_{k in W} X_k
```

严格按用户 2026-09-16 给出的形式：`A_{10:19} = (Q_max − Q_min) / Q̄`。

`X` 取 **4 个口径**（均为 Σ`HRS0-24avg`，即标定口径下的车公里）：

| 口径 | 链路集合 | 链路数 | 物理含义 |
|---|---|---:|---|
| `ALL` | 全网 | 693,575 | 总车公里（对空间重分布不敏感） |
| `MATCHED` | 7.3.6A Final Crosswalk 命中 | **3,037** | **★主判据** |
| `CATA` | 命中链路中 `RoadCat = CATA` | 1,020 | 快速路主线 |
| `SLIP` | 命中链路中 `RoadCat = SLIP_ROAD` | 2,017 | 匝道 |

窗口：

| 窗口 | 迭代 | 角色 |
|---|---|---|
| `pre_05_09` | it.5–9 | 短程预检（冒烟/中途检查） |
| **`conv_10_19`** | **it.10–19** | **★主判据窗口** |
| `full_00_19` | it.0–19 | 全程（未收敛期的调试信息，非判据） |

### 4.2 判决阈值（`MATCHED`，窗口 `it.10–19`）

| `A_10:19(MATCHED)` | 判决 | 含义与后续动作 |
|---|---|---|
| **< 3.0%** | **`STABLE`** | 通过 → 进入 7.6E，并把新配置定为后续所有实验的分配底座 |
| 3.0% – 10.0% | `PARTIAL` | 部分改善 → 按 §7 决定第二轮 |
| ≥ 10.0% | `UNSTABLE` | 最小修复不足 → 换机制（见 §7） |

> 阈值来源：用户明确要求「**先要求 MATCHED 不再出现 16–20% 级别的周期振荡**」。
> 3% 取作「与 7.6B 头部最小值（D01 parity-gap 1.59%）同量级」的保守目标。

### 4.3 辅助判据（必须同时披露，不参与判决）

- `ALL` / `CATA` / `SLIP` 的 `A_10:19`（观察是否结构性偏科）
- `parity_gap_rel = |even_mean − odd_mean| / cycle_mean`（7.6B 口径，用于连续性对照）
- `slope_pct_per_iter`（收敛窗线性趋势，正=仍在爬升/未沉降）
- **`ALL` 与 `MATCHED` 的振幅比**（7.6B 的「放大倍数」；基线 14.8×）

---

## 5. ★统计量口径的重要说明（与 7.6B 的差别，必须显式披露）

**7.6B 报出的「周期振幅」与本步骤的 `A` 不是同一个量：**

| 统计量 | 公式 | 捕捉什么 |
|---|---|---|
| 7.6B「周期振幅」（现记 `parity_gap_rel`） | `\|even_mean − odd_mean\| / cycle_mean` | **仅**奇/偶相位分离 |
| **本步骤 `A_10:19`（用户预注册）** | `(max − min) / mean` | 相位分离 **+ 窗内非交替漂移** |

**基线 D01（`MATCHED`，窗口 it.10–19）实测**：

```
parity_gap_rel = 1.59%          ← 7.6B 曾报出的数
A_10:19       = 8.48%           ← 用户预注册口径，是前者的 5.3×
```

**⇒ 结论比 7.6B 更严峻**：D01 的奇/偶两相位**各自内部**也在大幅漂移
（偶相位 it.10–18 极差 ≈ 5.0%、奇相位 ≈ 8.3%），
即当前的「周期-2」不是干净的 2-循环，而是**一个弱交替叠加在大幅非交替漂移之上**。
因此 `A` 是更诚实、更严格的「分配是否稳定」度量 —— 这也正是它被定为**主判据**的原因。

> ⚠️ 后续任何引用「20.75%」的地方，必须说明那是 **D03 的 `parity_gap_rel`**，
> 而非 `A_10:19`。两者不可混用。

---

## 6. 修复前基线（before，零仿真复用，不新增仿真）

`X` = Σ`HRS0-24avg`；`A` 见 §4.1。**四档 demand 的完整 before 谱**（跨口径对照）：

| run | f_demand | `A_10:19` ALL | **`A_10:19` MATCHED** | `A_10:19` CATA | `A_10:19` SLIP | 判决 |
|---|---:|---:|---:|---:|---:|---|
| **BASELINE_D01**（= 7.4.2 E06） | 1.00 | 3.96% | **8.48%** | 10.14% | 8.93% | `PARTIAL` |
| REF_D02（7.4.3 D02） | 1.10 | 2.71% | **11.10%** | 8.97% | 18.05% | `UNSTABLE` |
| REF_D03（7.4.3 D03） | 1.20 | 1.51% | **23.25%** | 18.15% | 35.51% | `UNSTABLE` |
| REF_D04（7.4.3 D04） | 1.25 | 2.32% | **20.32%** | 15.43% | 33.94% | `UNSTABLE` |

D01 的窗口分解与奇偶相位：

| run | 口径 | `A_pre_05_09` | **`A_conv_10_19`** | `A_full_00_19` | `parity_gap_rel` | `slope` %/it |
|---|---|---:|---:|---:|---:|---:|
| BASELINE_D01 | ALL | 2.67% | **3.96%** | 3.98% | 0.39% | +0.27 |
| BASELINE_D01 | MATCHED | 10.85% | **8.48%** | 12.30% | 1.59% | −0.26 |
| BASELINE_D01 | CATA | 9.90% | **10.14%** | 10.79% | 2.63% | −0.28 |
| BASELINE_D01 | SLIP | 13.01% | **8.93%** | 17.89% | 0.78% | −0.21 |

**四条读数**：

1. **`ALL` 振幅在所有 demand 档都只有 1.5–4.0%，而 `MATCHED` 达 8.5–23.3%** ⇒
   振荡**集中在标定断面上**，与 7.6B 的「放大 14.8×」方向一致（倍数差异来自统计量不同，见 §5）。
2. **`MATCHED` 振幅随 demand 放大并在 f=1.20 达峰**（8.48% → 11.10% → **23.25%** → 20.32%），
   与 7.6B 的「振幅峰值与 Sim/Obs 峰值同址」完全一致 ⇒ **交叉印证**。
3. **`SLIP`（匝道）是最不稳的口径**（最高 **35.51%**，约为 `CATA` 的 2 倍）⇒
   匝道流量在替代路径之间反复搬运，与 7.3.5/7.3.6 已记录的「匝道微段化 + 替代关系密集」一致。
4. **即使最温和的 f=1.00 也只是 `PARTIAL`（8.48%）** ⇒
   **当前机制下不存在任何一个 demand 档是稳定的** ⇒ 这**不是 demand 选得不好，而是机制问题**，
   直接支持用户「先修 route-choice、不继续扫 demand」的裁定。

> 完整数值见 `audit/routechoice_stability_amplitude.csv`（含 `role = before_ref` 行）
> 与 `audit/routechoice_stability_dual_caliber.csv`。

---

## 7. 判读规则（预注册）

| 结果 | 判定 | 下一步 |
|---|---|---|
| `A_10:19(MATCHED) < 3%` 且 `ALL` 振幅未反向恶化 | **通过** | 进入 **7.6E**（新配置稳定性验证：用新配置重算 Sim/Obs 双口径并在 4 口径上确认），随后才解冻 7.6C（OD 空间结构） |
| `3% ≤ A < 10%`（部分改善） | **PARTIAL** | 第二轮可选（**在本轮结果之后再预注册**）：`fractionOfIterationsToDisableInnovation = 0.9` / `learningRate = 0.3` / `fractionOfIterationsToStartScoreMSA = 0.5`，仍不引入新变量类别 |
| `A ≥ 10%`（无改善） | **UNSTABLE** | 判定「最小修复不足」→ 换机制：`BestScore` 取代 `ChangeExpBeta`、或 `routingRandomness > 0`（打破确定性全切走）、或检查 `maxAgentPlanMemorySize = 5` 是否足够承载计划多样性 |
| 出现 `PARTIAL` 但 `A` 反而 > 基线 | **REGRESSION** | 视为失败，回到基线配置并重新归因 |

**无论哪种结果**，以下保持不变：`N_sample = 200,000`、`f_cap = 1.00`、capacity = 1.00、
`λ` 不冻结、demand scale 不冻结、**7.6C 暂缓**。

---

## 8. 明确不做（用户 2026-09-16 裁定）

1. **不调 λ** —— λ 辨识（原 7.6D/7.6E，现编号 7.6F）必须在分配稳定之后。
2. **不调 demand scale** —— 不新增任何 demand 档次的 MATSim 跑次。
3. **不调 capacity** —— `f_cap` 仍是 1.00，不作性能旋钮。
4. **不改 network / OD / population / 7.1 靶场 / 7.3.6A crosswalk**。
5. **不改任何现有产物** —— 旧结果（`reports/od_calibration_7_4_2` / `7_4_3` / `7_4_3r` /
   `7_6a` / `7_6b` …）**完全保留**；新配置与新输出一律落在
   **`matsim_routechoice_7_6d/`** 独立目录。
6. **不进入 7.6C**（OD 空间结构 / 距离带）—— 在分配稳定之前，OD 空间效应
   会被 route-choice 相位噪声污染。

---

## 9. 运行计划

| 阶段 | 命令 | 规模 | 预估 | 状态 |
|---|---|---|---|---|
| 配置生成 + 校验 | `python scripts/od/prepare_routechoice_7_6d.py` | 零仿真 | 秒级 | ✅ **19/19 PASS** |
| 冒烟预检 | `... --smoke 2000 --heap 8g` | 2,000 agents × 3 it | ~1 min | ✅ **PASS** |
| 正式 run | `... --run --heap 24g` | 200,000 agents × 20 it | ~8–9 h（参照 D04 492.94 min） | ⏳ **待用户批准** |
| 稳定性评价 | `python scripts/od/audit_routechoice_stability_7_6d.py` | 零仿真 | ~5 min | ⏳ 待 run 完成 |

**堆内存**：200k 规模必须 `--heap 24g`（12g 会在 it.2/it.5 的 PlanRouter 处被硬杀，
见项目记忆）。

---

## 10. 产物清单

`matsim_routechoice_7_6d/`（本步骤隔离工作区）：

| 文件 | 内容 |
|---|---|
| `STEP7_6D_PREREGISTRATION.md` | **本文件** |
| `README.md` | 目录说明 + 机制 + 修复规格 + 运行方式 |
| `configs/config_R01_rc_min.xml` | 修复后正式 config（20 迭代） |
| `configs/config_R01_rc_min_smoke.xml` | 冒烟 config（3 迭代） |
| `routechoice_7_6d_config_provenance.csv` | 与基线逐参数 diff（唯一权威差异表） |
| `routechoice_7_6d_strategy_provenance.csv` | 策略集前后对照 |
| `routechoice_7_6d_config_validation.json` | 配置验证结果（19 项，机器可读） |
| `logs/` | MATSim 运行日志 |
| `outputs/R01_rc_min/` | MATSim 输出（正式 run） |
| `audit/routechoice_stability_by_iter.csv` | 逐迭代 4 口径数值（缓存） |
| `audit/routechoice_stability_amplitude.csv` | 各 run × 各口径 × 各窗口的 `A` |
| `audit/routechoice_stability_dual_caliber.csv` | **双口径**（`Q̄_10:19` 主 / `Q_19` 参考） |
| `audit/routechoice_stability_summary.json` | 机器可读汇总 |

---

## 11. 评价口径（用户裁定 ①，立即生效）

**双口径并报，不以周期均值「替代」it.19：**

```
Primary   (诊断/参数敏感性主看)  Q̄_10:19 = (1/10) Σ_{k=10..19} Q_k     奇偶相位均衡周期均值
Reference (保留可追溯性)          Q_19                                      单点，不丢弃
```

理由：it.19 可能落在周期-2 两个相位中的**任一**相位，直接当最终状态会把
phase noise 混进 demand/λ 判断。两者**同时输出**（见
`audit/routechoice_stability_dual_caliber.csv` 的 `Q_conv_mean` 与 `Q_19` 两列）。

**在分配稳定性（本步骤）解决之前，冻结一切基于单迭代的 demand scale / λ 判决。**
