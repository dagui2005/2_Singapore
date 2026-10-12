# E-SB-02 —— 夜间自由流速度代理 × 独立 OD 口径

> 状态：**已跑完并裁定**（2026-10-10）— 判决 **`SPEED_GAIN_INDEPENDENT_CONFIRMED__FLOW_GATE_FAILED`**
> 判决链：`E-SB-02A = AVAILABLE(6/6)` → `E-SB-02B = LEAKAGE_QUANTIFIED(7/7)` → `派生 = READY` → `SB-A5 rc=0` · `SB-A5ind rc=0 (73.1 min)` → `裁定 = VERDICT_E-SB-02.md`
> 协议：`PROTOCOL_E-SB-02.md` ｜ 裁定：`VERDICT_E-SB-02.md` ｜ 红线：不改 v1.0 / OD 冻结件 / crosswalk / TrafficFlow / SpeedBand；不产生 v1.1

## 一句话
用**夜间** SpeedBand（≠AM）的 **p75** 估计自由流速度，写入新网络；在**已隔离 AM 泄漏**的口径下，检验能否**同时**通过 AM 速度区间与 TrafficFlow 两类检验。

## ★结论（2026-10-10）
| 判据 | 裁定 | 实测 |
|---|---|---|
| 速度区间 | ✅ PASS | RMSE 18.235→**10.527**（−42.3%）· band 21.68→**40.58%**（+18.9 pp）· r 0.401→**0.771** |
| 流量必要条件 `[0.95,1.05]` | ❌ **FAIL** | cycle **1.0601**（it.19 1.0618；SB-A5ind **1.0751**）⇒ **无晋升 v1.1** |
| 拥堵机制分辨率 | ✅ PASS | 按观测档 spread 25.7→**53.2**（obs 54.5）· 残差 = **均匀 +5 km/h 偏置**（非形变、非钉中点） |
| 独立验证 | ✅ PASS | `SB-A5ind`（零 SpeedBand）仍 −42.2% RMSE；**≈ SB-A5**（ΔRMSE 0.007 km/h）⇒ 泄漏无关 |

> **主结论**：夜间自由流速度 = **已验证的样本外供给速度信息源**；但流量必要条件未过 ⇒ `SB-A5` 只作**候选网络**，⛔ 不产生 v1.1。
> `SB-A4` 的 RMSE 8.38 仍是上界，但**循环**（freespeed←AM 观测、评 AM 观测），**不可作独立证据**。

## 目录
```
configs/     config_SB-A5.xml / config_SB-A5ind.xml
networks/    network_SB-A5.xml.gz          （内容 sha16 = 7a2a81f925c5c560，可复现）
populations/ population_SB-A5ind_lambda_0p075.xml.gz  （Step5B，零 SpeedBand）
audit/       esb02_build_gates.{json,csv} · esb02_ind_demand_gates.{json,csv} · <ARM>_run_gates.csv · **esb02_joint_scorecard.csv**（8 行）
logs/        <ARM>_run.log · chain_state.json
outputs/     SB-A5/ · SB-A5ind/
```

## 两个臂
| 臂 | 需求 | 网络 | 目的 |
|---|---|---|---|
| **SB-A5** | v1.0 `pop_W01`（含 AM 泄漏 3.49%） | `network_SB-A5`（夜间 p75） | 单因子：夜间自由流是否同时改善速度+流量 |
| **SB-A5ind** | **Step 5B**（自由流阻抗，**零 SpeedBand**） | 同上 | 让「AM 速度拟合」真正样本外 |

`Δ(SB-A5, SB-A5ind)` = AM SpeedBand 泄漏的下游影响。

## 供给层规则（已冻结）
- 夜晚 = `N_adjacent{2026-05-06, 2026-05-07}`（29 次观测/链）
- 分位数 = **p75**（自由流中位 34.5 km/h）
- **SB8** = `max(75, v1.0 自由流)`，仅对 SB8 来源生效
- 只改 `freespeed`：改 **91,532 / 91,956** 在网目标链；其余参数、需求、seed、迭代数**不动**

## 判定门槛（三组共同判断）
- **速度**：RMSE 明确降 + band 命中升，**不得有符号相反的分等级亚类被均值掩盖**
- **流量**：`Sim/Obs∈[0.95,1.05]`（**必要条件**）且空间不恶化
- **拥堵机制**：按观测档的仿真速度**分辨率须真实提升**（⛔ 不靠压低自由流造漂亮 band）
- **独立验证**：`SB-A5ind` / `N_distant` 样本外仍改善

## 运行
```bash
python scripts/experiments/esb02_build_arms.py
python scripts/experiments/esb02_build_ind_demand.py
python scripts/experiments/esb02_run_arm.py --arm SB-A5            # 运行前硬门
python scripts/experiments/esb02_run_chain.py --arms SB-A5 SB-A5ind --heap 24g
python scripts/experiments/esb02_objective.py
```
> 长跑须用工具后台（脱离进程方案在本机不可用：`CREATE_BREAKAWAY_FROM_JOB` 被拒；`schtasks` 被策略拉黑）。链带**断点续跑**。

## 限制（须随结果声明）
- **Level 1**：夜→设 freespeed、AM→评价 ⇒ 摆脱 A4 的 AM→AM 循环；`SB-A5ind` 进一步消除需求层 3.49% 泄漏 ⇒ 可称**样本外速度拟合**。但 λ、`SCALE` 曾由 TrafficFlow 选定 ⇒ 流量仍是**样本内**。
- **Level 2**：`TrafficFlow`=2025-11 vs `SpeedBand`=2026-05 **不同期** ⇒ ⛔ 不得称"通过真实流量与速度观测联合校准"。
- **物理**：夜间速度仍含信号/路口延误 ⇒ 设为 freespeed 等于把信号延误折进自由流（与 A4 同性质）。
