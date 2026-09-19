# matsim_routechoice_7_6d — Step 7.6D Route-choice Stabilization

> 本目录是 **Step 7.6D 的隔离工作区**。依据用户 2026-09-16 裁定建立：
> **不修改任何现有 7.1 / 7.3.6A / OD / network / capacity 产物**；旧结果
> （`reports/od_calibration_7_4_2`、`7_4_3`、`7_4_3r`、`7_6a`、`7_6b` 等）**完全保留**。

## 为什么需要这一步

7.6B（`reports/od_calibration_7_6b/STEP7_6B_REPORT.md`）证明 D01-D04 的分配**从未收敛**，
而是 **周期-2 极限环（route flip-flop）**：

| 口径 | D01 (f=1.00) | D02 (1.10) | D03 (1.20) | D04 (1.25) |
|---|---:|---:|---:|---:|
| MATCHED 周期振幅 | 1.59% | 3.77% | **20.75%** | **16.22%** |
| ALL 周期振幅 | 0.39% | 1.34% | 1.13% | 1.40% |
| 放大倍数 | 4.0x | 2.8x | 18.3x | 11.6x |

根因是**配置组合**（D01-D04 四份 config 完全一致）：

| 参数 | 基线值 | 后果 |
|---|---|---|
| `replanning.fractionOfIterationsToDisableInnovation` | `Infinity` | 100% 迭代都在创新，无收尾沉降阶段 |
| `replanning` 策略集 | `[ReRoute 1.00]` | 每个 agent 每一代全部重新选路 |
| `scoring.learningRate` | `1.0` | 计划得分无指数平滑 |
| `routing.routingRandomness` | `0.0` | 确定性最短路 ⇒ 上代贵、这代全切走 |

## 最小修复（唯一变量）

**只改 3 个标量 + 1 个策略集**，针对「学习过猛 + 持续创新」两个机制：

| 参数 | 基线 | 修复后 |
|---|---|---|
| `replanning.fractionOfIterationsToDisableInnovation` | `Infinity` | **`0.8`** |
| `replanning` 策略集 | `[ReRoute 1.00]` | **`[ReRoute 0.15, ChangeExpBeta 0.85]`** |
| `scoring.learningRate` | `1.0` | **`0.5`** |
| `routing.routingRandomness` | `0.0` | `0.0`（保留） |

其余一切（network / population / OD / capacity / seed / threads / travelTimeCalculator /
crosswalk / 观测靶场）**逐参数不变**，见 `routechoice_7_6d_config_provenance.csv`。

**为什么加 `ChangeExpBeta`**：`fractionOfIterationsToDisableInnovation = 0.8` 意味着
**迭代 16 之后禁用创新策略**；若策略集里没有 plan-selection 算子，禁用创新后网络无法沉降。

**本轮唯一目标**：把 assignment 从周期-2 振荡变成可接受稳定状态。
**不做**：调 demand scale / λ / capacity；**不追求** Sim/Obs 变好（单变量纪律）。

## 目录

| 路径 | 内容 |
|---|---|
| `configs/config_R01_rc_min.xml` | 修复后的正式 config（20 迭代） |
| `configs/config_R01_rc_min_smoke.xml` | 冒烟 config（截断人口 × 3 迭代） |
| `routechoice_7_6d_config_provenance.csv` | 与基线逐参数 diff（唯一权威差异表） |
| `routechoice_7_6d_strategy_provenance.csv` | 策略集前后对照 |
| `routechoice_7_6d_config_validation.json` | 配置验证结果（机器可读） |
| `STEP7_6D_PREREGISTRATION.md` | 预注册稳定性判据（先于运行冻结） |
| `outputs/` | MATSim 输出（正式 run 尚未启动） |
| `logs/` | MATSim 运行日志 |
| `audit/` | 7.6D 稳定性评价产物 |

## 配置验证

**19/19 PASS**（零仿真，见 `routechoice_7_6d_config_validation.json`）。

## 运行

```
python scripts/od/prepare_routechoice_7_6d.py --smoke 2000   # 冒烟（配置可运行性预检）
python scripts/od/prepare_routechoice_7_6d.py --run          # 正式 20 迭代
python scripts/od/audit_routechoice_stability_7_6d.py        # 稳定性评价（零仿真）
```

run_id = `R01_rc_min`；population = population_lambda_0p075.xml.gz；λ = 0.075；f_cap = 1.00；seed = 4711。
