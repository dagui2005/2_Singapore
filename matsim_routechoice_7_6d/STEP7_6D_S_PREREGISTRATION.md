# Step 7.6D-S 预注册 — 低样本（100k）「稳定性筛查」

> **预注册声明**：本文件在 **7.6D-S 的任何 MATSim 运行启动之前** 冻结。
> 判据、阈值、口径、窗口在此确定；**运行之后不得回溯修改**。
> 若确需修改，必须新建 `7.6D-S-b` 并说明理由。
>
> 冻结时间：**2026-09-16 22:29**
> 状态：100k 人口已就位（复用 S100c 冻结件）；config 已生成并验证 **25/25 PASS**；正式 run 未启动。

---

## 0. ★与原设计的偏离（必须先读）

原定 **N = 50,000, f_cap = 0.25**。实测**不可行**：

    6.2B `allocate_cells` 的 FLOOR_PLUS_1 保底规则 = 「每个正 OD cell 至少 1 个 agent」
    而正 OD cell 数恒为 **71,136**（Σtrips 459,794 的全部非空格）
    -> ValueError: agents 50000 < positive OD cells 71136

即 50k **不是「跑得慢」，而是「建不出来」**。用户裁定改选 **N = 100,000, f_cap = 0.50**，
并**复用 S100c 已冻结的 100k 人口**（`reports/matsim_departure_6_3_3a_s100k/`）。

候选样本量实测形态（零仿真复现，与 7.5B 实测一致）：

| N | f_cap | 每 cell 最大 agent | 保底 cell 占比 | 可行性 |
|---:|---:|---:|---:|---|
| 50,000 | 0.25 | — | — | ❌ **不可行（< 71,136）** |
| 71,136 | 0.35568 | 1（完全退化） | 100.0% | 可行但退化 |
| 80,000 | 0.40 | 9 | 88.5% | 可行 |
| **100,000** | **0.50** | **26** | **70.5%** | ✅ **采用** |
| 200,000（正式档） | 1.00 | 114 | 41.5% | 正式档 |

**为什么选 100k 而不是更便宜的 80k**：① 复用 S100c 人口，**零人口重建**；
② 与 S100c 构成**同 N、同 f_cap、同采样规则、同 seed** 的严格对照（见 §5）——
把判决从「绝对门槛」升级为「绝对门槛 + 同 N 相对变化」；③ 成本仍仅为 200k 正式档的一半。

---

## 1. 本步骤**唯一**要回答的问题

> **新 route-choice 配置有没有让 assignment 从不稳定变成稳定？**

**不评价** demand scale、**不评价** λ、**不评价** OD 空间结构 / 距离带。
**不追求** Sim/Obs 变好 —— 只要稳定性达标即判成功（Sim/Obs 属 7.6E）。

## 2. 设计：只缩样本，不动机制

| 项 | 200k 正式档 | **7.6D-S** | 说明 |
|---|---:|---:|---|
| 人口 N | 200,000 | **100,000** | 低样本筛查 |
| `qsim.flowCapacityFactor` | `1.00` | **`0.50`** | = 100,000 / 200,000（采样一致性） |
| `qsim.storageCapacityFactor` | `1.00` | **`0.50`** | 同上 |
| `hermes.*CapacityFactor` | `1.00` | `1.00` | 不缩放（与 S100c 同构） |
| 采样规则 | `FLOOR_PLUS_1` | **`FLOOR_PLUS_1`** | 与 200k 基准**同规则**，不重构 |
| `λ` | 0.075 | 0.075 | 冻结 |
| seed | 4711 / 20260912 | 同 | 冻结 |

理由 `f_cap = 100,000/200,000`：保持与 S100c 相同的**采样一致性**思想 ——
样本量与容量同比缩放，使「物理供需比」不变，从而隔离出「样本量 ↓」的影响，
而不引入「拥堵水平变化」这一混杂因素。

## 3. route-choice 修复：与 7.6D **完全一致**（本轮不新增任何机制变量）

| 参数 | 基线 | 7.6D / 7.6D-S |
|---|---|---|
| `replanning.fractionOfIterationsToDisableInnovation` | `Infinity` | **`0.8`** |
| `replanning` 策略集 | `[ReRoute 1.00]` | **`[ReRoute 0.15, ChangeExpBeta 0.85]`** |
| `scoring.learningRate` | `1.0` | **`0.5`** |
| `routing.routingRandomness` | `0.0` | `0.0`（保留） |

其余一切（network / OD / 剖面 / threads / travelTimeCalculator / crosswalk / 观测靶场）
**逐参数不变**，见 `routechoice_7_6d_s_config_provenance.csv`。

## 4. 预注册判据（**稳定性筛查门槛**，不是拟合优劣门槛）

### 4.1 统计量定义

```
A_10:19(X) = ( max_{k in 10..19} X_k − min_{k in 10..19} X_k ) / mean_{k in 10..19} X_k
parity_gap_rel(X) = | even_mean − odd_mean | / mean        （周期结构诊断）
```

`X` 取 4 个口径：`ALL` / `MATCHED`(3,037) / `CATA`(1,020) / `SLIP`(2,017)。

### 4.2 门槛（**运行前固定**）

| 口径 | 门槛 | 性质 |
|---|---|---|
| **MATCHED** | `A_10:19 < 3%` | **正式稳定性判据** |
| **CATA** | `A_10:19 < 3%` | **正式稳定性判据** |
| **SLIP** | `A_10:19 < 5%` | **正式稳定性判据**（匝道侧放宽至 5%） |
| `ALL` | 仅报告 | 不设门槛（全网总量对空间重分配不敏感） |
| `parity_gap_rel` | 仅报告 | **辅助诊断**，不作为判据 |

### 4.3 ★统计量纪律（用户明确要求保持区分）

- **`A_10:19` = 正式稳定性判据**（含奇偶分离 + 窗内非周期漂移，更严格）。
- **`parity_gap_rel` = 周期结构诊断**（只含奇偶相位分离）。
- **两者不得再统称为「周期振幅」。** 7.6B 报的「20.75%」是 D03 的 `parity_gap_rel`，
  而同一档的 `A_10:19` 是 **23.25%**；D01 的二者为 **1.59% vs 8.48%（5.3×）**。

## 5. ★修复前 / 修复后：同 N 严格对照（本步骤最大信息增益）

| run | N | f_cap | 采样规则 | route-choice | 角色 |
|---|---:|---:|---|---|---|
| **REF_S100c_N100k** | 100,000 | 0.50 | FLOOR_PLUS_1 | 旧（ReRoute 1.0 / innovation=∞ / lr=1.0） | **修复前** |
| **S100k_rc_min** | 100,000 | 0.50 | FLOOR_PLUS_1 | 新（ReRoute 0.15 + ChangeExpBeta 0.85 / 0.8 / lr=0.5） | **修复后** |

两者除 route-choice 4 项外**完全一致**（同人口文件、同网络、同 seed、同窗口、
同 crosswalk）。S100c 已有完整 20 迭代 linkstats（it.0–it.19），故对照**边际成本为零**。

补充的跨样本量 before 参照（200k 档，零仿真复用）：

| run | N | MATCHED `A_10:19` | 判定 |
|---|---:|---:|---|
| BASELINE_D01 (E06) | 200,000 | **8.48%** | PARTIAL |
| REF_D02 (f=1.10) | 200,000 | **11.10%** | UNSTABLE |
| REF_D03 (f=1.20) | 200,000 | **23.25%** | UNSTABLE |
| REF_D04 (f=1.25) | 200,000 | **20.32%** | UNSTABLE |

## 6. 判决与后续动作（**运行前固定**）

```
若 MATCHED < 3% 且 CATA < 3% 且 SLIP < 5%
    -> SCREENING_PASS -> 再跑 200k x 20 it 正式稳定化
否则
    -> SCREENING_FAIL -> 暂停，**不消耗 200k 算力**，继续修 route-choice
```

辅助读法（不改变判决）：修复后 `A_10:19` 相对 S100c 的变化方向与幅度。
**注意**：即使绝对门槛未达标，只要相对 S100c 出现数量级下降，也说明修复方向正确。

无论 PASS / FAIL，均继续并报 `Q̄_10:19`（Primary）与 `Q_19`（Reference）双口径，
以及 `parity_gap_rel` 辅助诊断。

## 7. 冻结不变量（机器校验，非人工承诺）

由 `scripts/od/prepare_routechoice_7_6d_s.py` 的 V1–V6 共 **25 项校验** 保证：
network / seed / coordinateSystem / threads / routingAlgorithm / travelTimeCalculator /
linkStats 间隔 / networkRouteType / hermes capacity 与基线**逐值相同**。
实际 diff 见 `routechoice_7_6d_s_config_provenance.csv`。

## 8. 产物

| 路径 | 内容 |
|---|---|
| `configs/config_S100k_rc_min.xml` | 7.6D-S 正式 config（20 迭代） |
| `configs/config_S100k_rc_min_smoke.xml` | 冒烟 config（截断人口 × 3 迭代） |
| `routechoice_7_6d_s_config_provenance.csv` | 与基线逐参数 diff |
| `routechoice_7_6d_s_config_validation.json` | 配置验证（机器可读） |
| `outputs/S100k_rc_min/` | MATSim 输出（本步骤运行后产生） |
| `logs/S100k_rc_min_run.log` | 运行日志 |
| `audit/routechoice_stability_screening_7_6d_s.csv` | 稳定性筛查判决（含 S100c 对照） |

## 9. 人口

- persons = **100,000**（期望 100,000）
- ΣEF = **459794.0**（名义 459,794）
- 采样规则 = **FLOOR_PLUS_1**（6.2B 原生，**未重构**）
- 来源 = `reports/matsim_departure_6_3_3a_s100k/`（S100c 冻结件，**未重建**）

## 10. 配置验证

**25/25 PASS**（零仿真）—— 明细见 `routechoice_7_6d_s_config_validation.json`。
