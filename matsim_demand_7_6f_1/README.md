# matsim_demand_7_6f_1 — Step 7.6F-1 粗档 demand-response 曲线

> 本目录是 **Step 7.6F-1 的隔离工作区**（依据用户 2026-09-17 裁定建立）。
> **不修改** 7.1 / 7.3.6A / OD / network / capacity / route-choice 任何冻结件；
> 旧结果（`reports/*`、`matsim_routechoice_7_6d/**`）**完全保留**。

## 做什么

在 **route-choice 已冻结**（7.6E `STABILITY_PASS`）的稳定分配底座上，扫

```
f_demand = 1.05 / 1.15 / 1.25      （采样基准仍为 200,000；被仿真 agent 数 = f x 200,000）
```

建立 `f_demand -> Q_MATCHED -> Sim/Obs` 的**粗档响应关系**，并**同时报告 frozen target 不确定性**。

## 关键机制（详见 STEP7_6F_1_PREREGISTRATION.md §0）

| 量 | 值 | 说明 |
|---|---:|---|
| 采样基准 `N`（SCALE 锚） | 200,000 | 冻结 |
| 被仿真 agent 数 | 210,000 / 230,000 / 250,000 | = f x 200,000 |
| `f_cap` | 1.00 | **不随 N 缩放**（物理加车，非采样一致性） |
| `SCALE` | 2.29897 | 复制机制下平均 EF 不变 ⇒ 恒定 |
| route-choice | `R01_rc_min` | 7.6E 冻结 |

## 目录

| 路径 | 内容 |
|---|---|
| `STEP7_6F_1_PREREGISTRATION.md` | 预注册（**先于运行冻结**） |
| `demand_response_7_6f_1_matrix.csv` | 实验矩阵（单一事实源） |
| `demand_response_7_6f_1_config_provenance.csv` | 与 R01 逐参数 diff |
| `demand_response_7_6f_1_config_validation.json` | 配置验证（机器可读） |
| `populations/` | 三档复制人口 |
| `configs/` | 三份 config |
| `outputs/` | MATSim 输出（run 后产生） |
| `logs/` | 运行日志 |
| `audit/` | 响应曲线评价产物 |

## 配置验证

**67/67 PASS**（零仿真）。

## 运行

```
python scripts/od/prepare_demand_response_7_6f_1.py              # 零仿真：人口 + config + 预注册
python scripts/od/prepare_demand_response_7_6f_1.py --smoke 2000 # 冒烟（需显式指定）
python scripts/od/prepare_demand_response_7_6f_1.py --run        # 正式 3 档（需用户明确启动指令）
python scripts/od/evaluate_demand_response_7_6f_1.py             # 响应曲线评价（零仿真）
```
