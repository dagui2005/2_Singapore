# Step 7.6E 预注册 — 200k × 20 it 正式稳定化（route-choice 正式冻结门）

> **预注册声明**：本文件在 **7.6E 的任何 MATSim 运行启动之前** 冻结。
> 判据、阈值、口径、窗口在此确定；**运行之后不得回溯修改**。
> 若确需修改，必须新建 `7.6E-b` 并说明理由。
>
> 冻结时间：**2026-09-17 07:55**
> 状态：200k 人口已就位（6.3.3A 冻结件，persons = **200,000**）；config 已生成并验证 **19/19 PASS**；
> 冒烟 PASS；**正式 run 未启动**。

---

## 0. 为什么现在做 7.6E（用户裁定 2026-09-17）

7.6D-S（100k × 20 it）已判 **`SCREENING_PASS`**：同 N、同 `f_cap`、同采样规则的严格对照下，
MATCHED `A_10:19` **5.84% → 0.71%**、SLIP **10.86% → 0.60%**、`parity_gap_rel` 4.07% → 0.09%，
且**逐迭代行为从「周期-2 极限环」变为「单调指数收敛」**（it.13 起 `1.000±0.002`）。

据此用户裁定：

1. **route-choice 修复已有强证据** ⇒ 不再做新的低样本试验；
2. **修复已改变机制性质** ⇒ 继续纠结旧配置下 D01–D04 的非单调 demand 响应已无意义；
3. **200k 是最终冻结样本规模** ⇒ 100k 只能证明「修复有效」，不能作为最终模型规模。

⇒ **现在直接进入 7.6E：把同一套修复配置提升到冻结的 N = 200,000、f_cap = 1.00。**

**7.6E 的分工（重要）**：本步骤**不**同时承担「找参数」与「找机制」。
route-choice 已由 100k 筛查通过；**200k 只负责确认「规模提升后机制仍然成立」**。

---

## 1. 本步骤**唯一**要回答的问题

> **200k 在修复后的 route-choice 下是否稳定收敛？**

**不是**「Sim/Obs 有没有接近 1」。**不评价** demand scale、**不评价** λ、**不评价** OD 空间结构 / 距离带。
**不选** demand scale —— 运行结束后**先只做稳定性审计**。

## 2. 冻结不动（逐项，不得修改）

| 项 | 值 | 冻结依据 |
|---|---|---|
| 人口 `N` | **200,000** | 正式标定基准（6.3.3A 冻结件，已核 persons = 200,000） |
| 采样规则 | **`FLOOR_PLUS_1`** | 不重构（6.2B 原生；下界 = 正 OD cell 71,136） |
| `qsim.flowCapacityFactor` | **`1.00`** | 正式档冻结（**不是**性能旋钮） |
| `qsim.storageCapacityFactor` | **`1.00`** | 同上 |
| `λ` | **0.075** | 不冻结但**本轮不变动** |
| 7.3.6A crosswalk | `reports/od_final_calibration_crosswalk_7_3_6/final_calibration_crosswalk.csv` | 靶场冻结（MATCHED 3,037 / CATA 1,020 / SLIP 2,017） |
| network | `reports/matsim_network/network_cleaned.xml.gz` | 冻结（0 删除） |
| departure profile | `reports/matsim_departure_6_3_3a/population_lambda_0p075.xml.gz` | 冻结 |
| OD matrix | 6.2B `FLOOR_PLUS_1` 采样产物 | 冻结 |
| demand scale | **暂不调整** | 属 7.6F |

## 3. 唯一改变：route-choice 最小修复（与 7.6D / 7.6D-S **完全一致**）

| 参数 | 基线（D01 / E06） | **7.6E（= 7.6D-S）** |
|---|---|---|
| `replanning.fractionOfIterationsToDisableInnovation` | `Infinity` | **`0.8`** |
| `replanning` 策略集 | `[ReRoute 1.00]` | **`[ReRoute 0.15, ChangeExpBeta 0.85]`** |
| `scoring.learningRate` | `1.0` | **`0.5`** |
| `routing.routingRandomness` | `0.0` | `0.0`（保留，显式冻结） |

其余一切**逐参数不变**，见 `routechoice_7_6d_config_provenance.csv`（与基线 diff 仅 4 处：
`outputDirectory` / `runId` + 2 个标量）。

## 4. 设计：200k 正式档

| 项 | 值 |
|---|---|
| run_id | **`R01_rc_min`** |
| 输出目录 | `matsim_routechoice_7_6d/outputs/R01_rc_min/` |
| 迭代数 | **20**（it.0 – it.19） |
| 人口 | 200,000 |
| 墙钟预估 | 参考 100k 实测 33.20 min ⇒ 约 **1–1.5 h**（★原估 8–9 h 已被 100k 实测推翻） |

### 4.1 ★★本步骤自带两组严格对照（零额外成本）

**（a）200k 同 N 单变量对照**（本步骤最大信息增益）：

| run | N | f_cap | 人口 / 网络 / seed | route-choice | 角色 |
|---|---:|---:|---|---|---|
| **BASELINE_D01**（E06, 7.4.2） | 200,000 | 1.00 | 同 | 旧（ReRoute 1.0 / innovation=∞ / lr=1.0） | **200k 修复前** |
| **R01_rc_min**（7.6E） | 200,000 | 1.00 | 同 | 新（0.15 + ChangeExpBeta 0.85 / 0.8 / lr=0.5） | **200k 修复后** |

⇒ D01 与 R01 **除 route-choice 4 项外完全一致**（同人口文件、同网络、同 seed 4711、同窗 08-09、同 crosswalk）
⇒ **200k 档的单变量 before/after**，无需任何新仿真即可对照（D01 已有完整 20 迭代 linkstats）。

**（b）跨规模一致性对照**（验证机制对样本量稳健）：

| run | N | f_cap | route-choice | 角色 |
|---|---:|---:|---|---|
| **S100k_rc_min**（7.6D-S） | 100,000 | 0.50 | 新 | **100k 修复后** |
| **R01_rc_min**（7.6E） | 200,000 | 1.00 | 新 | **200k 修复后** |

⇒ 两者均持修复配置；若**都稳定**，则机制对样本量稳健。

**（c）既有 200k before 全谱**（零仿真复用）：

| run | N | MATCHED `A_10:19` | 判定 |
|---|---:|---:|---|
| BASELINE_D01 (f=1.00) | 200,000 | 8.48% | PARTIAL |
| REF_D02 (f=1.10) | 200,000 | 11.10% | UNSTABLE |
| REF_D03 (f=1.20) | 200,000 | 23.25% | UNSTABLE |
| REF_D04 (f=1.25) | 200,000 | 20.32% | UNSTABLE |

## 5. 统计量定义（严格区分，不得混称）

```
A_10:19(X)        = ( max_{k∈10..19} X_k − min_{k∈10..19} X_k ) / mean_{k∈10..19} X_k
A_full_00_19(X)   = 同上但 k∈0..19            ← 含 burn-in 瞬态，仅报告，绝不作判据
parity_gap_rel(X) = | even_mean − odd_mean | / mean     （周期结构诊断，非判据）
Q̄_10:19(X)        = mean_{k∈10..19} X_k                 （Primary 口径，用户裁定 ①）
Q_19(X)           = 单点                                   （Reference 口径，用户裁定 ①）
Q19_over_Qbar(X)  = Q_19 / Q̄_10:19
sign_consistency  = #{ k∈0..12 : Q_{k+1} ≥ Q_k − 0.002·Q̄ } / 13     （单调性，0.2% 容差）
```

`X` 取 4 个口径：`ALL`(693,575) / `MATCHED`(3,037) / `CATA`(1,020) / `SLIP`(2,017)。

> **★统计量纪律**：`A_10:19` = 正式稳定性判据；`parity_gap_rel` = 周期结构诊断。
> **两者不得再统称为「周期振幅」。** 7.6B 报的「20.75%」是 D03 的 `parity_gap_rel`；
> 同一档的 `A_10:19` 是 **23.25%**；D01 二者为 **1.59% vs 8.48%（5.3×）**。
> **`A_full_00_19` 不可用作判据**：新配置 100k 的 `A_full` = 9.25% 纯属 burn-in 瞬态（**单调**），
> 与极限环的本质区别在于**是否单调**，不是振幅大小。

## 6. 预注册判据（**运行前固定**，第一关 = 稳定性，不是拟合）

### 6.1 主判据（6 项，**全部**通过才判 `STABILITY_PASS`）

| # | 判据 | 阈值 | 说明 |
|---|---|---|---|
| **G1** | 单调收敛 | `sign_consistency(MATCHED, it.0→13) ≥ 0.85` | 从初始计划单调抬升，**无奇偶交替** |
| **G2** | 收敛窗振幅（正式） | MATCHED `A_10:19 < 3%` **且** CATA `A_10:19 < 3%` **且** SLIP `A_10:19 < 5%` | 与 7.6D-S 同门槛 |
| **G3** | 无周期结构 | `parity_gap_rel < 1%`（MATCHED / CATA / SLIP 三者） | ≈ 0 的量化门槛（100k 实测 0.07–0.09%） |
| **G4** | 单点代表性 | `\|Q19_over_Qbar − 1\| < 2%`（MATCHED） | 用户裁定 ① 双口径的自洽检查（100k 实测 +0.10%） |
| **G5** | 无 agent 丢失 | `never_arrived = 0` **且** `max_stuck_car = 0`（it.19） | 源 = `it.19/*.legHistogram.txt`，与 7.4.3 同源同口径 |
| **G6** | 跨规模不恶化 | `A_10:19(200k, MATCHED) < 3%` 且 `A_10:19(200k) / A_10:19(100k) < 5` | 机制对样本量稳健 |

`ALL` 口径**仅报告**（全网总量对空间重分配不敏感）；`A_full_00_19` **仅报告**；
`never_arrived / max_stuck_car` 同时按 `it.19` 与逐迭代轨迹输出。

### 6.2 辅助读数（**不改变判决**）

- 四口径逐迭代轨迹（it.0–it.19）——**"是否仍存在周期振荡" 由轨迹判定，不只由振幅数字判定**。
- 200k 同 N 相对变化：`A_10:19` 与 `Q̄_10:19` 相对 `BASELINE_D01` 的变化。
- 双口径：`Q̄_10:19` 与 `Q_19` **并报**（用户裁定 ①，不简单替代）。
- 8-9 加权拥堵倍率、平均行程时长（`legdurations`）——供 7.6F 参考。

## 7. 判决与后续动作（**运行前固定**）

```
若 G1..G6 全部通过
    -> STABILITY_PASS -> **route-choice 层正式冻结**
                        （config 提升为正式标定 baseline，进入 7.6F）
否则
    -> STABILITY_FAIL -> 暂停，**不进入 7.6F / 7.6C**，继续修 route-choice 机制
```

**不论 PASS / FAIL**：均**不选 demand scale**、**不评价 λ**、**不评价 OD 空间结构**。

### 后续主线（用户裁定 2026-09-17）

```
7.6E  route-choice 正式冻结          ← 本步
  ↓
7.6F  重新评价 demand scale
  ↓
7.6C  OD 空间结构 / 距离带
  ↓
λ / impedance
  ↓
最终 200k 验证
```

## 8. 冻结不变量（机器校验，非人工承诺）

由 `scripts/od/prepare_routechoice_7_6d.py` 的 V1–V6 共 **19 项校验** 保证：
network / plans / seed / coordinateSystem / threads / qsim capacity ×2 / SpeedyALT / travelTimeCalculator /
linkStats 间隔 / networkRouteType / hermes capacity 与基线**逐值相同**。
实际 diff 见 `routechoice_7_6d_config_provenance.csv`。

## 9. 产物

| 路径 | 内容 |
|---|---|
| `configs/config_R01_rc_min.xml` | 7.6E 正式 config（200k，20 迭代） |
| `configs/config_R01_rc_min_smoke.xml` | 冒烟 config（截断人口 × 3 迭代） |
| `routechoice_7_6d_config_provenance.csv` | 与基线逐参数 diff |
| `routechoice_7_6d_config_validation.json` | 配置验证（机器可读，19/19 PASS） |
| `outputs/R01_rc_min/` | MATSim 输出（本步骤运行后产生） |
| `logs/R01_rc_min_run.log` | 运行日志 |
| `audit/routechoice_stability_7_6e.csv` | 7.6E 逐口径稳定性判决表 |
| `audit/routechoice_stability_7_6e_by_iter.csv` | 逐迭代轨迹 |
| `audit/routechoice_stability_7_6e_summary.json` | 机器可读汇总 + 判决 |

## 10. 运行命令

```bash
python scripts/od/prepare_routechoice_7_6d.py                                    # 生成 + 19 项校验（已完成 PASS）
python scripts/od/prepare_routechoice_7_6d.py --run --heap 24g                    # 正式 200k x 20 it
python scripts/od/audit_routechoice_stability_7_6d.py --stability-7_6e --reuse    # 稳定性审计 + 判决
```

返回码：`0` = STABILITY_PASS ／ `2` = STABILITY_FAIL ／ `3` = NO_RUN。
