# Step 7.2.2 — Capacity-only Sensitivity 报告（λ=0.05，f ∈ {0.50, 0.75, 1.00, 1.25, 1.50}）

**日期**：2026-09-12
**性质**：受控单因子实验。唯一变量 = `qsim.flowCapacityFactor`（因 MATSim 2026.0 引擎硬约束 `storageCapacityFactor` 同步取同值，见 7.2.1/冒烟记录）。OD / λ / population（6.3.3A 冻结出发剖面）/ departure time / network topology / permlanes / route choice（SpeedyALT 单迭代）/ randomSeed 全部冻结不动。

---

## 1. 实验设置

| 项 | 值 |
|---|---|
| 基线 config | `matsim/step6_3/config_lambda_0p050_6_3_3b.xml`（经 `make_config_6_3.build_one` 同源重建后 patch） |
| 唯一变量 | `flowCapacityFactor = storageCapacityFactor = f ∈ {0.50, 0.75, 1.00, 1.25, 1.50}` |
| population | 6.3.3A 冻结出发时刻剖面（200,000 agents，ΣEF=459,794） |
| network | `network_cleaned.xml.gz`（6.1 冻结） |
| scale | 2.29897（459,794 / 200,000） |
| 评价口径 | **Step 7.1 冻结靶场**（n=1,278，LTA RoadCat 分层，断面内中位数），对照脚本直接 import 7.1 的 `obs_load / cross_load / metric` |
| 运行 | 5 × 单迭代 QSim，约 45 min（后台），产物 `reports/od_calibration_7_2_2/capacity_factor_*/` |

**确定性核对（PASS）**：`f=1.00` 档与冻结 6.3.3B 逐位复现（见 `f1p00_vs_frozen_633b_consistency.json`）：
07-08 ratio 0.7441053260989662 = 0.7441053260989662；08-09 0.8892666387118214 = 同；r 三窗亦逐位一致。 ⇒ 对照管线无泄漏、随机种子稳定、patch 精确。

## 2. 总体响应（n=1,278）

| f | r(07-08) | r(08-09) | Sim/Obs(07-08) | Sim/Obs(08-09) | GEH<5(07-08) | WMAPE(AM) |
|---|---|---|---|---|---|---|
| 0.50 | 0.298 | 0.260 | 0.596 | 0.602 | 9.4% | 0.644 |
| 0.75 | 0.286 | 0.264 | 0.699 | 0.784 | 10.0% | 0.672 |
| 1.00 | 0.279 | 0.249 | 0.744 | 0.889 | 10.0% | 0.711 |
| 1.25 | 0.279 | 0.247 | 0.761 | 0.924 | 9.8% | 0.723 |
| 1.50 | 0.279 | 0.247 | 0.767 | 0.935 | 9.4% | 0.727 |

- **Pearson r 对 f 完全不敏感**（07-08 稳定 0.28–0.30，08-09 稳定 0.25–0.26）。
- Sim/Obs 单调随 f 上升（容量越小 → 拥堵/流失越多 → 完成流量越少），但全程 <1，f=1.5 也只到 0.767/0.935。

## 3. 结构信号判读（本轮核心）

### 3.1 CATA（快速路）与 SLIP_ROAD（匝道）随 f 的响应

| f | CATA 07-08 | CATA 08-09 | SLIP_ROAD 07-08 | SLIP_ROAD 08-09 | **CATA/SLIP 比值(07-08)** | **CATA/SLIP 比值(08-09)** |
|---|---|---|---|---|---|---|
| 0.50 | 0.474 | 0.498 | 1.291 | 1.384 | **0.367** | **0.360** |
| 0.75 | 0.552 | 0.669 | 1.512 | 1.827 | **0.365** | **0.366** |
| 1.00 | 0.584 | 0.739 | 1.594 | 2.033 | **0.366** | **0.364** |
| 1.25 | 0.598 | 0.767 | 1.632 | 2.107 | **0.366** | **0.364** |
| 1.50 | 0.603 | 0.777 | 1.645 | 2.133 | **0.367** | **0.364** |

**关键观察：CATA 与 SLIP_ROAD 同向、近比例地随 f 移动，两者的比值在全部 5 档、两个时间窗内恒定在 0.36–0.37。**

- 预注册判据一（f↓ ⇒ CATA↑ 且 SLIP_ROAD↓ = capacity 改变路径结构）：**不成立**。f↓ 时 CATA 与 SLIP_ROAD **同时下降**，是全网通量的整体收缩，不是"匝道→快速路"的相对转移。
- 预注册判据二（capacity 扫描几乎不改变 CATA/SLIP_ROAD 相对结构 ⇒ route choice 主导）：**成立，且为最强形式**——相对结构不是"几乎不变"，是**逐档严格不变**（比值极差 ≤0.007）。
- CATA 内部 Pearson r 在全部 5 档保持 ≈0 甚至轻微为负（−0.06 ~ −0.01）；Spearman 稳定在 0.25–0.28。容量变化完全无法恢复快速路断面内的流量排序。
- CATB/CATC 的 ratio 随 f 有轻微改善（CATB 0.57→0.78/0.85），说明容量主要影响整体拥挤水平，与结构错配无关。

### 3.2 结论

$$
\boxed{\text{Capacity 不是 CATA↔SLIP\_ROAD 结构错配的杠杆 —— 快速路低估归因于 route choice / 路径效用结构}}
$$

机理上完全自洽：当前单迭代 + SpeedyALT + freespeed TT ⇒ 路径选择对拥堵**零反馈**，capacity 只决定 QSim 里"能挤过去多少车"（整体通量），不决定"谁走快速路、谁走匝道"（相对分配）。因此 f 的扫描只移动 Sim/Obs 的整体水平，不改变类别间比例。

### 3.3 对 7.2.1 审计两个发现的回应

- `flowCapacityFactor=1.0`（容量相对抽样需求过剩 ~2.3×）：本轮证实即使压到 0.5，结构依旧 ⇒ **不存在一个"正确的 f"能修复快速路低估**；f 的选择应回到规模一致性语义（0.435 候选值），留待 Step 7.4/7.5 与 λ 一起做联合辨析，**本轮不选定**。
- 单迭代 ReRoute 无效：本轮结果正是其直接后果，进入 7.3 的动机进一步加固。

## 4. 下一步 → Step 7.3 Route Choice

按主线路线：**7.3 route-choice sensitivity**（多迭代 ReRoute / 计划评分权重 / TravelTimeCalculator 拥堵反馈 / SpeedyALT→常规模拟迭代），目标检验"给路径选择加上拥堵反馈后，CATA 能否回升、SLIP_ROAD 能否回落、CATA 内部 r 能否脱离 0"。判据沿用本轮同款预注册式：若多迭代后 CATA/SLIP 比值显著偏离 0.366 ⇒ route choice 是结构主因。

## 5. 产物清单

```text
reports/od_calibration_7_2_2/
├─ capacity_factor_0p50/ … capacity_factor_1p50/   5 × MATSim 输出（linkstats 等）
├─ capacity_sensitivity_summary.csv                总体指标 × 5f × 3窗
├─ capacity_sensitivity_by_roadcat.csv             LTA RoadCat 分层 × 5f × 3窗
├─ capacity_sensitivity_sections.csv               断面级明细
├─ capacity_sensitivity_ratio_pivot.csv            Sim/Obs 透视表
├─ f1p00_vs_frozen_633b_consistency.json           f=1.00 与冻结 6.3.3B 逐位核对（PASS）
├─ capacity_sensitivity_definition.json            实验定义（含 storage=flow 的引擎约束说明）
└─ STEP7_2_2_REPORT.md                             本报告
```

脚本：`scripts/od/run_capacity_sweep_7_2_2.py`（`--smoke` 冒烟 + `verify_patch` 防呆）、`scripts/od/compare_capacity_sweep_7_2_2.py`（复用 7.1 冻结口径）。

## 6. 冻结状态

| Step | 状态 |
|---|---|
| 7.1 校准靶场 | 🔒 冻结 |
| 7.2.1 参数审计 | 🔒 冻结（flowCapacityFactor=1.0 / storage=1.0 / 单迭代 / SpeedyALT 基线） |
| **7.2.2 capacity-only sweep** | ✅ **本轮 PASS / 可冻结**（`parameters_changed` 仅 f，结论：capacity 非结构杠杆） |
| 7.3 route choice | ⬜ 下一步 |
| λ | 仍冻结（0.05 代表跑，未辨识） |
