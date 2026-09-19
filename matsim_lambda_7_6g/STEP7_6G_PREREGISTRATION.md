# Step 7.6G 预注册 — λ 敏感度 screening（三档 λ × 单一 demand level）

> 冻结时间：**2026-09-18T08:52**  
> 状态：三档人口与 config 已就位并验证；**正式 run 未启动**（需用户明确启动指令）。

---

## 0. 机制事实：λ 作用在 OD 构建层，不是 MATSim 运行参数

| 步骤 | 脚本 | λ 处理 | 产物 |
|---|---|---|---|
| 5C1 | `build_prior_od_5c1.py` | `LAMBDAS=[.05,.075,.10,.125,.15]` | `prior_od_5c1_lambda_*.parquet` |
| 6.2B | `build_matsim_population_6_2b.py` | `DEFAULT_LAMBDAS=[0.05,0.075,0.10]` | `population_lambda_*.xml.gz` |
| 6.3.3A | `build_departure_profile_6_3_3a.py` | `DEFAULT_LAMBDAS=[0.05,0.075,0.10]` | 出发时刻剖面人口 |
| 7.4.3 / 7.6F-1 | `run_demand_scale_7_4_3.py` | 复制机制 | `f × 200,000` persons |

**⇒ 三档 λ 的 200,000 人冻结人口已存在**（`reports/matsim_departure_6_3_3a/`），
7.6G **不重建任何上游**，只做「复制到 N_sim + 换 config + 20 迭代」。

## 1. λ 不变性门（本步骤的结构性保障）

| 量 | λ=0.05 | λ=0.075 | λ=0.10 | 判定 |
|---|---:|---:|---:|---|
| ΣT（5C1 OD 总量） | 1,935,235 | 1,935,235 | 1,935,235 | **逐位一致** |
| car_od_total（6.2B） | 459,794.0 | 459,794.0 | 459,794.0 | **逐位一致** |
| ΣEF（6.3.3A 人口） | 459,794.0000 | 459,794.0000 | 459,794.0000 | **逐位一致** |
| persons | 200,000 | 200,000 | 200,000 | **逐位一致** |

⇒ **`SCALE = 2.29897` 对三档 λ 自动成立**；不存在「λ 改总量」与「λ 改空间」的混杂。
用户 2026-09-17 硬约束（不得按 ΣEF 重算 SCALE）在 λ 维度上**天然满足**。

★ λ 确实改变的东西（上游 5C1 实测，机制预信号）：

| λ | `weighted_mean_travel_time_min` | `nonzero_od_cells` |
|---|---:|---:|
| 0.05 | 18.082 | 71,136 |
| 0.075 | 17.811 | 71,136 |
| 0.10 | 17.533 | 71,136 |

## 2. 网格与 demand level 的理由

**唯一被扫的量 = λ ∈ {0.05, 0.075, 0.10}；demand level 固定为 f = 1.18（N_sim = 236,000）。**

| run | λ | N_sim | SCALE | route-choice |
|---|---:|---:|---:|---|
| L05 | 0.050 | 236,000 | 2.29897 | R01_rc_min |
| L75 | 0.075 | 236,000 | 2.29897 | R01_rc_min |
| L10 | 0.100 | 236,000 | 2.29897 | R01_rc_min |

理由：
1. **f = 1.18 = 7.6F-1 的 FROZEN 条件估计 f\* = 1.1803**，
   即把 demand level 钉在「当前最佳条件估计」上，使 λ 成为唯一变量；
2. 三档 λ 落在 5C1 原始扫描的中心区（0.125/0.15 使 Table118 约束残差劣化到 3.67%/5.76%，不取）；
3. **不做 3×4 demand×λ 全网格**（12 次仿真不必要）：先做 λ screening，
   仅当 λ 显著改变 demand response 时才在相邻 λ 上补小型 demand refinement。

### ★ 一处必须点明的口径澄清

用户表格把 `λ=0.075 @ f=1.18` 标为「已有/基准」。**实际上 7.6F-1 只跑了 f = 1.00 / 1.05 / 1.15 / 1.25，从未跑过 1.18。** 因此：

| 方案 | 成本 | FROZEN 值 | 说明 |
|---|---:|---:|---|
| (A) **实跑 L75**（本预注册采用） | +1 run ≈85 min | 待测 | 兼作响应曲线可复现性与插值可信度对照 |
| (B) 插值 | 0 | **0.99978468**（线性） | 二次 0.99983318 / 三次 0.99959237；**极差仅 0.0860%** |

插值极差 0.086% 远小于靶场不确定性 7.609 pp，但方案 (A) 可把插值误差从 λ 效应的
分子中彻底移除，且提供一次**独立复现控制**。本步骤按 (A) 冻结。

## 3. 零成本机制预探（已有 it.0 λ 分档 linkstats）

> ⚠️ **口径声明**：这些 it.0 来自旧配置（`Innovation=Infinity` / `lr=1.0` / `lastIteration=0`）且人口为 `6_2b_connected`（**无 6.3.3A 出发剖面**）。
> **不是 7.6G 结果**，只作**期望效应量先验**，用于给 §5 判据设定合理量级。

| 指标 | λ=0.05 | λ=0.075 | λ=0.10 | Δ(0.10−0.05) |
|---|---:|---:|---:|---:|
| 冻结口径 pooled Sim/Obs（primary） | 1.063027 | 1.063662 | 1.068318 | **+0.5291 pp** |
| 全链路 Σ(HRS8-9avg) | 48,087,442 | 48,002,925 | 48,049,640 | **−0.0786%**（非单调） |

区域/径向 rel_dev(%)：EAST −29.23 → −28.60 → −28.27（极差 **0.96 pp**）；
`radial_in` −27.85 → −27.77 → −28.19（极差 **0.42 pp**）；NORTH-EAST 极差 1.35 pp。

**对照 7.6F-1 的 demand 方向**（f=1.00→1.25）：EAST 极差 **1.05 pp**、`radial_in` **2.16 pp**。

⇒ **先验判读：λ 的移动能力与 demand 同量级（约 1 pp），而 EAST 缺口是 −28 pp ⇒ 期望判决 `LAMBDA_WEAK`。**
⇒ 但这是 it.0/旧配置的先验 —— **必须用冻结口径实测**（项目纪律：测量而非推断）。
若实测与先验冲突，需在报告中说明收敛/route-choice 放大的机制。

## 4. 口径（冻结，不可混用）

| 口径 | 定义 | 角色 |
|---|---|---|
| `FROZEN` | 全 576 池化（primary candidate） | **正式主靶场**（不得擅改） |
| `POSITIVE_ONLY` | 仅 sim>0 池化 | 敏感性（**不得升格**） |
| `BEST_DIRECTION` | `max(median(fwd),median(rev)) × SCALE` | 误差边界（**不得升格**） |

- 双口径：Primary `Q̄_10:19`（收敛窗 it.10–19 周期均值）/ Reference `Q_19`（单点）
- 窗口纪律：Sim/Obs 用 `HRS8-9avg`；稳定性 `Q`/`Q̄` 用 `Σ HRS0-24avg`，**永不混用**
- 目标不确定性（7.6C-2）：`Δ_target` = **7.609 pp**，`Δ_f_target` = **0.09473**

## 5. 判据 G1–G8 与判决空间（预注册，冻结）

**判据（全部要求 PASS 才算本步骤技术有效）**

| # | 判据 | 阈值 |
|---|---|---|
| G1 | 三档 linkstats 齐备（it.0–19） | 3/3 档 × 20/20 迭代 |
| G2 | 与 7.6C-2 对账（R01 三口径） | 逐位（tol 1e-6） |
| G3 | 与 7.6D 审计缓存对账（R01 Q̄_10:19 四项） | 逐位 |
| G4 | SCALE 全档统一 2.29897，ΣEF/N 仅披露 | P1b/P1c PASS |
| G5 | 稳定性 `A_10:19`(MATCHED) | < 3.0% |
| G6 | 收敛窗 `parity_gap_rel` | < 5.0% |
| G7 | 空间残差**只报告不压平**（EAST / radial_in 登记为已知偏差） | 无调参 |
| G8 | λ=0.075 @ f=1.18 与 7.6F-1 插值基准的一致性 | |Δ| 记录（不设硬阈，作复现控制） |

**判决空间（两维）**

| 维度 | 判据 | 标签 |
|---|---|---|
| 全局 λ 可辨性 | `|Δ Sim/Obs(0.05→0.10)| < 1.0 pp` | `LAMBDA_WEAK`（情况 A） |
| | `1.0 ≤ |Δ| < 7.609 pp` | `LAMBDA_DETECTABLE_NOT_IDENTIFIABLE` |
| | `|Δ| ≥ 7.609 pp`（= Δ_target） | `LAMBDA_IDENTIFIABLE`（情况 B） |
| 空间活跃性 | 区域/径向 rel_dev 极差 `≥ 3.0 pp` | `SPATIAL_ACTIVE` |
| | `< 3.0 pp` | `SPATIAL_INERT` |

**判决 = (全局标签) / (空间标签)**，例如 `LAMBDA_WEAK / SPATIAL_INERT`。

阈值依据：① 1.0 pp ≈ 7.6F-1 中 demand 全幅（f=1.00→1.25，19.5 pp）的 1/20，
低于此即「杠杆可忽略」；② 7.609 pp = 7.6C-2 的 `Δ_target`，是**绝对**识别的下限；
③ 空间 3.0 pp 阈值基于：7.6F-1 中 demand 对 EAST / radial_in 的移动仅 1.05 / 2.16 pp，
若 λ 不能超过此量级，则面对 −28 ~ −32 pp 的结构缺口**不构成修复路径**。

**λ 对 f\* 的影响（估计，不是直接观测）**

- 参考斜率（7.6F-1 的 1.15–1.25 局部割线）：`s_ref = 0.768286`（每单位 f）
- `f*_λ ≈ f_0 + (1 − SimObs_λ)/s_ref`，`f_0 = 1.18`；`Δf*_λ ≈ −ΔSim/Obs_λ / s_ref`
- 换算：`|ΔSim/Obs| = 7.609 pp ⟺ |Δf*| ≈ 0.09904`（与 7.6C-2 的 `Δ_f_target` = 0.09473 自洽）
- ⚠️ **该估计假设局部斜率 λ 不变**；只有一次 demand level/λ，**不能**直接观测 `f*_λ`。

## 6. 明确不做

```text
x 不做 crosswalk-b（7.3.6A 保持冻结）
x 不做新的 demand 细扫（1.17/1.18/1.19/1.20）
x 不做 3×4 demand×λ 全网格
x 不把 0.8590 / 0.9351 或任何倒数值预先用于选 λ 或 demand scale
x 不把 POSITIVE_ONLY / BEST_DIRECTION 升格为正式靶场
x 不用调 demand 或 λ 去压平 EAST / radial_in
x 不改任何模型参数（本步骤的唯一变量是 λ，且 λ 由人口文件承载）
```

## 7. 冻结不变量（机器校验）

由 `scripts/od/prepare_lambda_sensitivity_7_6g.py` 的 W1–W6（复用 7.6F-1 `validate()`，
**不复制逻辑**）+ L1–L6 共 **72 项校验**保证：
- 与 **R01 config** 的差异**仅限** `plans.inputPlansFile` + `controller.{outputDirectory,runId}`；
- route-choice 4 项、`f_cap`、seed 4711、network、threads、travelTimeCalculator、
  linkStats 间隔、`networkRouteType`、hermes capacity 与 R01 **逐值相同**；
- 三档 **SCALE 统一 2.29897**，`ΣEF/N_sim` 仅披露（NOT USED）。

冻结件 mtime 快照（**运行前后均须不变**）：

| 文件 | mtime |
|---|---|
| `config_R01_rc_min.xml` | 1789602663.646397 |
| `population_lambda_0p050.xml.gz` | 1789185745.8939092 |
| `population_lambda_0p075.xml.gz` | 1789185757.169695 |
| `population_lambda_0p100.xml.gz` | 1789185768.231971 |
| `network.xml.gz` | 1789180172.5391662 |
| `final_calibration_crosswalk.csv` | 1789275047.377488 |
| `prior_od_5c1_summary.csv` | 1789112466.3463762 |
| `population_6_2b_summary.csv` | 1789180396.3352377 |

## 8. 产物与复现

- 入场准备：`scripts/od/prepare_lambda_sensitivity_7_6g.py`
- 点火器：`scripts/od/run_lambda_sensitivity_7_6g.py`
- 预注册分析：`scripts/od/evaluate_lambda_sensitivity_7_6g.py`
- 工作区：`matsim_lambda_7_6g/`（`configs/config_L05|L75|L10_rc_min.xml` + `populations/pop_L05|L75|L10/` + 本预注册 + matrix/provenance/validation/lambda-invariance）
- 状态：**三档人口与 config 已就位；`outputs/` 与 `logs/` 为空 —— 正式 run 未启动。**

```bash
python scripts/od/prepare_lambda_sensitivity_7_6g.py            # 生成 + 校验（已完成）
python scripts/od/run_lambda_sensitivity_7_6g.py --dry-run      # 前置核验
python scripts/od/run_lambda_sensitivity_7_6g.py --experiments L05 --heap 24g
python scripts/od/evaluate_lambda_sensitivity_7_6g.py           # 网格未齐时输出 AWAITING_RUNS
```

**冻结不动**：7.1 / 7.3.6A / OD / network / capacity / population(200k 源) / route-choice 任何冻结件；
**未启动任何 MATSim 仿真；未选 demand scale / 未评价最终 λ**。
