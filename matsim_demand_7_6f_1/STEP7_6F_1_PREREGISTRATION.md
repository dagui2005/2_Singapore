# Step 7.6F-1 预注册 — 稳定分配底座上的**粗档 demand-response 曲线**

> **预注册声明**：本文件在 **7.6F-1 的任何 MATSim 运行启动之前**冻结。
> 判据、阈值、口径、窗口、判决空间在此确定；**运行之后不得回溯修改**。
> 若确需修改，必须新建 `7.6F-1-b` 并说明理由。

> 冻结时间：**2026-09-17 19:21**  
> 状态：三档人口与 config 已就位并验证（**67/67 PASS**）；**正式 run 未启动**。

---

## 0. ★ 必须点明的一处机制推论（否则设计自相矛盾）

用户冻结清单同时给出 `N = 200,000` 与 `f_demand = 1.05 / 1.15 / 1.25`。
**二者不是同一个量**，因为：

| 量 | 值 | 性质 |
|---|---:|---|
| 采样基准 `N`（= SCALE 锚） | **200,000** | 冻结，**不改** |
| 被仿真的 agent 数 | **210,000, 230,000, 250,000** | = f × 200,000 |
| `SCALE = ΣT / N` | **2.29897**（恒定） | 复制机制下平均 EF 不变 |

**为什么必须这样**（三条闭合论证）：

1. **7.4.3 已证**：只缩放 `expansion_factor` / `od_trips` 而**不动 agent 数**是对仿真的
   **no-op** —— `HRSx-yavg` 一个数都不变，Sim/Obs 只是被算术地乘 f。那样的
   「三档实验」会得到三份**完全相同**的 linkstats，跑 MATSim **毫无信息**。
2. **`f_cap = 1.00` 冻结**（而非 `N/200,000`）**排除**了 7.6D-S 的
   「采样一致性」约定，锁定 7.4.3 的「**物理加车**」约定。
3. **`SCALE` 恒定**：复制 agent 会连同其 `expansion_factor` 一并复制 ⇒ 平均 EF 不变
   ⇒ `SCALE = ΣT/200,000 = 2.29897` 对三档**全部适用**。
   此点已由 7.6F-0 `demand_scale_7_6f_0_decomposition.csv` 实证：
   **D01–D04 的 SCALE 列全为 2.29897**（而非 459794/220000 等）。

**因此本预注册按「f_demand 缩放被仿真 agent 数」冻结。**

> **✅ 门控已解除（2026-09-17 20:17 用户裁定）**：采用 **「物理加车」** 路径 ——
> 正式确认 `N_base = 200,000`（SCALE 锚）、`N_sim = f × 200,000`（QSim 中真实参与分配的车辆数），
> **不采用**「agent 数恒为 200,000、仅做算术倍乘」的方案。
> 三个量的区分（用户原话口径）：
> ```text
> 200k        = 冻结的采样基准 / SCALE 分母
> 210k/230k/250k = QSim 中真正参与交通分配的车辆数
> 2.29897     = 每个模拟 agent 对应的 OD 扩展权重
> ```
> 这与 6.2B 人口实现逻辑一致：`expansion_factor` 用于在统计上恢复冻结 OD，
> 而**不是**代替 QSim 中真实车辆数。

---

## 1. 本步骤**唯一**要回答的问题

> 在 **route-choice 已冻结**（7.6E `STABILITY_PASS`）的稳定分配底座上，
> `f_demand` 与 `Q_MATCHED / Sim/Obs` 之间是否存在**可复现、单调、稳定**的响应关系？

**核心输出不是「哪个 factor 最好」**，而是那条响应关系本身：

```
f_demand  ->  Q_MATCHED  ->  Sim/Obs      （并同时报告 frozen target 不确定性）
```
**不选 demand scale、不评价 λ、不评价 OD 空间结构。**

## 2. 为什么网格是 `1.05 / 1.15 / 1.25` 而不是 `1.10 / 1.20 / 1.25`

7.6C-2（`TARGET_MARGINAL_COARSE_ONLY`）给出：

| 量 | 值 |
|---|---:|
| `Delta_target`（靶场不确定性） | **7.609 pp** |
| `f*` 识别区间（`f*=Q^(-1/eps)`, eps=1） | **[1.06945, 1.16418]** |
| SNR 粗档 step=0.10 | **1.056 ✓**（需 eps>=0.947） |
| SNR 细档 step=0.05 | **0.528 ✗**（需 eps>=1.895） |

原网格 `1.10 / 1.20 / 1.25` **不合格**：
- `f=1.10` 落在 f\* 区间 **[1.06945, 1.16418]** **内部** ⇒ 结论随口径而变（仅 POSITIVE_ONLY 越过 1.0）；
- `1.20` 与 `1.25` 均在区间之上且三口径一致 ⇒ **3 次跑只辨 2 个区制**。

新网格 `1.05 / 1.15 / 1.25` 的原由（用户裁定）：分别落在 f\* 区间的
**下方 / 内部附近 / 上方**，且步长恒为 **0.10 >= `Delta_f_target`**（粗档 SNR ≥ 1），信息利用率更高。

## 3. 设计：唯一变量 = `f_demand`；其余逐项冻结

| 项 | 取值 | 性质 |
|---|---|---|
| **`f_demand`** | **1.05, 1.15, 1.25** | ★ **唯一被扫的量** |
| route-choice | `R01_rc_min`（innovation 0.8 / `[ReRoute 0.15, ChangeExpBeta 0.85]` / lr 0.5 / randomness 0.0） | 7.6E 冻结 |
| 采样基准 `N` | 200,000 | 冻结（SCALE 锚） |
| `f_cap` = flow/storage CapacityFactor | **1.00** | 冻结（**不随 N 缩放**） |
| `SCALE` | **2.29897** | 恒定（复制机制） |
| λ | 0.075 | 本轮**仅保持**，不作评价 |
| capacity / storage | 1.00 / 1.00 | 冻结 |
| 迭代 | 20（评估窗 it.10–19） | 冻结 |
| seed | 4711（MATSim）/ 20260912（复制） | 冻结 |
| network | `network_cleaned.xml.gz` | 冻结 |
| 人口源 | `reports\matsim_departure_6_3_3a\population_lambda_0p075.xml.gz` | 冻结（6.3.3A） |
| 观测靶场 | 7.1 冻结 + **7.3.6A Final Crosswalk**（576 断面） | 冻结，**不得擅改** |

## 4. 人口机制（受控性）

以 6.3.3A 冻结 200k 人口为源，按 **seed=20260912 的 permutation 前缀**做**嵌套随机子集复制**（F05 ⊂ F15 ⊂ F25 = 7.4.3 D04 人口）：

- 每 agent 的 `expansionFactor` / `home_link` / `work_link` / departure `end_time` **逐字节不变** ⇒ 唯一变化 = 车辆数；
- 复制概率对**每个 agent 相同** ⇒ 增量在空间上**无偏**（不会被「每 cell 保底 1 agent」扭曲）；
- 目标 `ΣEF = f × 459,794`，**实测值见本表**并给 `f_realized`；
- `FLOOR_PLUS_1` 硬下界 **71,136** 正 OD cell：三档 N = 210,000, 230,000, 250,000 **均满足**。

| Exp | f_demand | agents | persons(实测) | ΣEF(实测) | f_realized |
|---|---:|---:|---:|---:|---:|
| **F05** | 1.05 | 210,000 | 210,000 | 482,591.7 | 1.049582421838319 |
| **F15** | 1.15 | 230,000 | 230,000 | 528,733.5 | 1.1499355629970853 |
| **F25** | 1.25 | 250,000 | 250,000 | 574,710.1 | 1.2499295942628457 |

## 5. 预注册判据（**运行前固定**）

### 5.1 统计量定义

```
Sim/Obs(08-09)  = median(匹配 MATSim 有向边 HRS8-9avg) * SCALE   [冻结口径，逐年同源]
Q_bar_10:19(X)  = mean_{k=10..19} X_k                            [主口径，X = Sigma HRS0-24avg]
Q_19(X)        = X_{19}                                          [参考口径]
A_10:19(X)     = (max_{k} X_k - min_{k} X_k) / mean_{k} X_k      [稳定性判据]
rho(f)         = Sim/Obs_run(f) / ( Sim/Obs_R01 * f )            [拥堵阻尼比]
```
主口径 = **MATCHED**（`3,037` 全 crosswalk 匹配链；其中 3,015 primary）；
`CATA` / `SLIP_ROAD` / `ALL` 仅作辅助。

### 5.2 判据

| # | 判据 | 门槛 | 性质 |
|---|---|---|---|
| **G1** | **稳定性承继**：三档 `A_10:19`(MATCHED/CATA/SLIP) | MATCHED<3% 且 CATA<3% 且 SLIP<5% | **硬门槛**（不达标 ⇒ 响应曲线不可用） |
| **G2** | **单调性**：Sim/Obs(08-09, MATCHED, Primary) 在 f∈{1.00,1.05,1.15,1.25} 上单调递增 | 容差 ±0.5%（数值噪声） | **硬门槛** |
| **G3** | **算术参照与阻尼**：`rho(f)` 逐档 | 仅报告（**不设阈值**） | 诊断 |
| **G4** | **与 frozen target 的关系**：各档 Sim/Obs 相对 `FROZEN` 靶场的位置，曲线是否**跨越 1.000** | 仅报告 | 诊断 |
| **G5** | **靶场不确定性并报**：每档同时报 3 口径 | 必须同时输出 | **纪律** |
| **G6** | **空间残差不得压平**：EAST / `radial_in` 逐档报告 | 不得用 f 压平 | **纪律** |
| **G7** | **双口径**：`Q̄_10:19`(Primary) + `Q_19`(Reference) | 必须同时输出 | **纪律** |

### 5.3 判决空间（**运行前固定**）

```
G1 不过                                    -> RESPONSE_UNSTABLE
G1 过 + G2 不过                             -> RESPONSE_NON_MONOTONIC
G1 过 + G2 过 + 曲线未跨越 1.000            -> RESPONSE_STABLE_PARTIAL
G1 过 + G2 过 + 曲线跨越 1.000              -> RESPONSE_STABLE_CROSSES
```
- `RESPONSE_UNSTABLE`：暂停；回到 route-choice / OD 结构，**不消耗 7.6F-2 算力**。
- `RESPONSE_NON_MONOTONIC`：**只记录形态**，不得解释为需求响应。
- `RESPONSE_STABLE_PARTIAL`：需求规模不足仍未被完全解释；继续沿 f 方向或转结构。
- `RESPONSE_STABLE_CROSSES`：f 方向可解释量级缺口，可进入 λ / impedance。

**注意（7.6C-2 门后含义，当前生效）**：靶场不确定性 **7.609 pp** ≈ 粗档增量 ⇒
本步骤**只能**给出「带靶场不确定性的粗档响应关系」，**不能**给出「绝对 demand scale」。
`0.9351`/`1.1642` **不得**用于反推 demand scale；`0.8590` 仍是唯一正式 demand=1.00 参照。

## 6. 靶场口径（并报，**不升格**）

| 口径 | 值 | 角色 | 可否作正式靶场 |
|---|---:|---|---|
| `FROZEN`（全 576 池化） | **0.8589732** | **正式主靶场** | ✅ |
| `POSITIVE_ONLY`（`sim>0`） | 0.9350621 | 敏感性口径 | ❌ **不得升格** |
| `BEST_DIRECTION` | 0.8909674 | 误差边界 | ❌ **不得升格** |

`Delta_target = 7.609 pp`；`f*` 区间 `[1.06945, 1.16418]`；
SNR 粗档 `1.056` / 细档 `0.528`。
8-9 过饱和份额恒 0% ⇒ 无容量反馈 ⇒ `eps ~ 1` 是物理预期。

## 7. 明确不做（清单）

```text
x 不选 demand scale（本步只建立响应关系）
x 不评价 lambda（本轮仅保持 0.075）
x 不评价 OD 空间结构 / 距离带
x 不把 POSITIVE_ONLY / BEST_DIRECTION 升格为正式靶场
x 不修改 7.3.6A crosswalk（若确需修，必须另立 7.3.6A-b + 另留证据链）
x 不用 0.9351 / 1.1642 反推 demand scale
x 不用调 demand 去压平 EAST / radial_in 的已知空间残差
x 不用 (1+delta) 修正因子平移旧 D01-D04
x 不加 1.00 以外的第五档；不改网格
x 不用 F05/F15/F25 各自的 Sigma EF / N_sim 重算 SCALE（全档统一 2.29897，见 §11）
```

---

## 8. 冻结不变量（机器校验，非人工承诺）

由 `scripts/od/prepare_demand_response_7_6f_1.py` 的 **P1–P9 + W1–W6 共 67 项校验**保证：
与 **R01 config** 的差异**仅限** `plans.inputPlansFile` + `controller.{outputDirectory,runId}`；
route-choice 4 项、`f_cap`、seed、network、threads、travelTimeCalculator、
linkStats 间隔、`networkRouteType`、hermes capacity 与 R01 **逐值相同**。
另由 P 系列校验 `ΣEF` 与 `persons` 的实测值。
实际 diff 见 `demand_response_7_6f_1_config_provenance.csv`。

## 9. 产物

| 路径 | 内容 |
|---|---|
| `populations/pop_<EID>/population_lambda_0p075.xml.gz` | 三档复制人口 |
| `configs/config_<RUN_ID>.xml` | 三份 config（20 迭代） |
| `demand_response_7_6f_1_matrix.csv` | 实验矩阵（单一事实源） |
| `demand_response_7_6f_1_config_provenance.csv` | 与 R01 逐参数 diff |
| `demand_response_7_6f_1_config_validation.json` | 配置验证（机器可读） |
| `outputs/<RUN_ID>/` | MATSim 输出（**本步骤运行后**产生） |
| `logs/<RUN_ID>_run.log` | 运行日志 |
| `demand_response_7_6f_1_run_manifest.json` | **运行清单**（点火器写入：sha256 前后、exit code、wall min、iters、SCALE 审计） |
| `audit/` | 响应曲线评价产物 |

## 10. 配置验证

**67/67 PASS**（零仿真）—— 明细见 `demand_response_7_6f_1_config_validation.json`。
点火器 `run_demand_response_7_6f_1.py` 在每次点火前**重跑逐档 `validate()`**（18/18）
并对 config 做 **sha256 前后钉扎**，保证「被执行的 config = 被验证的 config」。

---

## 11. 启动许可与追加硬约束（2026-09-17 20:17 用户裁定）

**启动形式**：`7.6F-1 RUNNING`，三档串行点火（本机 RAM 63.7 GB，24g/run ⇒ 不可并行）。

| run | `f_demand` | simulated agents | SCALE | route-choice |
|---|---:|---:|---:|---|
| F05 | 1.05 | 210,000 | 2.29897 | R01_rc_min |
| F15 | 1.15 | 230,000 | 2.29897 | R01_rc_min |
| F25 | 1.25 | 250,000 | 2.29897 | R01_rc_min |

**★追加硬约束（用户原话）**：

> **不得根据 F05/F15/F25 的 `Sigma EF` 重新计算 SCALE；三档统一使用冻结基准 `SCALE = 2.29897`。**
> 否则就会把「增加真实车辆数」和「改变扩展权重」混成两个不同的 demand 操作。

**实现与审计**：
- 运行器 `run_demand_response_7_6f_1.py` 对三档一律注入 `SCALE_FROZEN = 2.29897`，
  并逐档落盘 `scale_if_recomputed_sumEF_over_N` 与 `scale_recompute_delta_ppm` **仅作披露**，
  明确标注 **NOT USED**（实测：F05 `-397.7 ppm` / F15 `-56.0 ppm` / F25 `-56.3 ppm`，
  全部来自 `FLOOR_PLUS_1` 保底取整，量级 1e-4 相对值，**不改变任何结论**）；
- 评价器 `evaluate_demand_response_7_6f_1.py` 的 **P1** 断言 `SCALE == 2.29897`（全局唯一），
  产出 `demand_response_7_6f_1_scale_audit.csv`。

**其它继续保持**：`f_cap = 1.00`；λ = 0.075（仅保持，不评价）；crosswalk = 7.3.6A Frozen；
Primary = **MATCHED `Qbar_10:19`**；Reference = **MATCHED `Q_19`**；
**`0.8590` / `0.9351` 或任何倒数值均不得预先用于选择 demand scale**。

**`f_realized` 如实报告**（复制后实际 `Sigma EF` 的实现值，**不四舍五入**）：
F05 `1.0495824` / F15 `1.1499356` / F25 `1.2499296`。

---

生成脚本：`scripts/od/prepare_demand_response_7_6f_1.py`  评价脚本（预注册分析）：`scripts/od/evaluate_demand_response_7_6f_1.py`
