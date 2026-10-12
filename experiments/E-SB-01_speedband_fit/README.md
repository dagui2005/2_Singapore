# E-SB-01 — SpeedBand 拟合旁路实验

> `EXPERIMENT ONLY / NOT v1.1 / NOT FORMAL BASELINE / NOT CALIBRATED MODEL`
> 建立：2026-10-07 ｜ 协议见 [`PROTOCOL_E-SB-01.md`](PROTOCOL_E-SB-01.md)

## 目的

把 SpeedBand 从「上游先验」升级为与 TrafficFlow **并列的第二个拟合目标**：在不让 TrafficFlow 对账恶化的前提下，降低仿真对 LTA AM 高峰速度带（SpeedBand）的拟合误差。允许的杠杆（用户裁定）：**供给/容量侧** 或 **网络机制（信号/交叉口/排队）**。

## 臂表

| 臂 | 层 | 唯一改动 | 状态 | ΔRMSE | Sim/Obs |
|---|---|---|---|---|---|
| SB-A1 | 网络机制（排队） | `qsim.trafficDynamics: queue → kinematicWaves` | ✅ rc=0 (109 min) | **+0.07** | 0.851 |
| SB-A2 | 机制（存储） | `qsim.storageCapacityFactor: 1.0 → 0.434977` | ⛔ **BLOCKED_BY_FRAMEWORK** | — | — |
| SB-A3 | 供给（定向容量） | 新网络 `capacity ← c·m(l)` | ✅ rc=0 (132 min) | **+0.99** | 0.501 |
| SB-A3n | **负例** | 同 A3，`(c,m)` 边际不变、空间打乱 | ✅ rc=0 (201 min) | **+2.57** | 0.053 |
| SB-A4 | **供给（自由流速度）freespeed 标定** | 新网络 `freespeed ← max(v_obs, 5)` | ✅ rc=0 (77 min) | **−9.85** | 1.0524 |

**结论见[`VERDICT_E-SB-01.md`](VERDICT_E-SB-01.md)**：唯一显著改善 SpeedBand 的是 `SB-A4`（供给侧自由流速度，RMSE 18.24→8.38）；机制/容量/需求类杠杆无效或有害；`SB-A2` 因 MATSim 2026 强制 flow/storage 耦合而架构性不可实现（证据见 `audit/SB-A2_BLOCKED.json`）。

## 关键使能：SpeedBand 可 1:1 对接 MATSim 链路

```
LTA SpeedBand LinkID → lta_osm_ampeak_speed_match.csv 的 osm_edge_index
                     → network_links.csv 行号 → MATSim link id = e{from}_{to}
```
91,956 / 92,149（99.79%）匹配链存在于仿真网络内。

## ★可行性预筛（零仿真，已算出）

| 量 | 值 |
|---|---|
| 匹配链 | 91,956（2,812.1 km） |
| `v/c` 中位 / 均值 | **0.0063 / 0.0457** |
| `v/c ≥ 1` | **0.00%** |
| **A3 可饱和（可减速）** | **4,838 链 / 236.5 km（5.3%）** |
| **A3 不可行（需求过低）** | **87,100 链 / 2,574.9 km（94.7%）** |
| A4 将改变 | 91,956 链（100%） |

按等级，A3 可行率：motorway **62.8%** · motorway_link 31.9% · trunk 26.4% · primary 11.6% · **residential 0.66%**。
⇒ **A3 结构上无法修地方道路（最大偏差来源）**。

同时：MATSim 网络自由流 vs 观测 AM 速度 = residential **46.7 vs 20.7 km/h（2.26×）**、service 21.8 vs 20.0、motorway 85.5 vs 62.8。
⇒ 主缺口是**自由流速度水平**，不是流量-容量比。

## 基线（v1.0 冻结，即对照）

| 指标 | 值 |
|---|---|
| `Sim/Obs`(cycle it.10–19) | **0.9993347696792919** |
| SpeedBand RMSE / band 精确 | **18.235 km/h / 21.68%** |

## 运行

```bash
# 1) 建臂 + 硬门（零仿真）
python scripts/experiments/esb01_build_arms.py

# 2) 单臂运行前硬门
python scripts/experiments/esb01_run_arm.py --arm SB-A1

# 3) ★串行链全跑（脱离进程；A1→A4→A3→A3n→A2，约 19 h）
python scripts/experiments/esb01_launch_chain.py --arms SB-A1 SB-A4 SB-A3 SB-A3n SB-A2

# 单臂脱离点火（备选）
python scripts/experiments/esb01_launch_detached.py --arm SB-A4

# 4) 评分（TrafficFlow + SpeedBand 双尺子）
python scripts/experiments/esb01_objective.py
```

进度落点：`logs/chain_state.json`（逐臂 rc / 耗时）· `logs/chain_task.log`（链总日志）· `audit/esb01_joint_scorecard.csv`（逐臂追加）。

## 产物

- `configs/`、`networks/`、`audit/`（`esb01_build_gates.csv` = 44/44 PASS、`esb01_feasibility_*`、`esb01_joint_scorecard.csv`）
- `outputs/<ARM>/` 运行产物 · `logs/`

## 红线

⛔ 不改 v1.0 / `network_cleaned` / plans / crosswalk / `TrafficFlow` / `SpeedBand` 原始值 / 评价器阈值；⛔ 不重启「观测尺度 × 残差」；⛔ 与已 `CLOSED` 的 O3-R1 隔离。
