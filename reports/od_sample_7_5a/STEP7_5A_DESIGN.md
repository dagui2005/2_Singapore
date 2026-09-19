# Step 7.5A（二）— 固定样本量 + 可变需求权重（采样—扩样架构）

**零仿真**。本文件是 7.5A 的设计单一事实源：确定「样本率—扩样系数」解耦方案，并给出 100k 人口的构建与校验。

## 1. 为什么不靠降低道路容量省时间

`flowCapacityFactor` 是**供给物理参数**，不是性能旋钮：

- Phase 1 已证 `capacity 0.50→0.75→1.00` 显著改变 CATA/SLIP 结构（其结构影响大于 λ）；
- Phase 2 / 7.4.3 又证需求变化本身也改变结构；
- 7.4.3 的 D 系列已出现非单调（峰 @f=1.20），此时再动 capacity 将无法归因。

→ **capacity 继续作为物理参数冻结（=1.00），不作计算性能旋钮。**

## 2. 真正可调的是「样本率」，它与需求量原则上可解耦

7.5A 审计（见 `STEP7_5A_DEMAND_CHAIN_AUDIT.md`）已确证：

```text
MATSim QSim 只消费 person/vehicle 数（agents）
expansionFactor / odTrips：仅人口 XML 自定义属性，MATSim 自身 class 零命中 -> 不消费
=> linkstats 原始口径 ~ 线性于 agent 数
=> 扩样权重必须在评价层施加：SCALE = ΣT / N_sample
```

## 3. 三层需求（论文口径）

| 层 | 量 | 符号 | λ=0.075 基准值 | 决定什么 |
|---|---|---|---:|---|
| 1 | 真实需求 | `ΣT` | 459,794 | 现实机动车 OD 总量（与 N 无关） |
| 2 | 采样率 | `N_sample` | 200,000 / **100,000** | **只决定计算量** |
| 3 | 有效需求权重 | `SCALE = ΣT/N_sample` | 2.29897 / **4.59794** | 把链接车数换算成现实车次 |

## 4. ★硬约束：N_sample 下限 = 正 OD cell 数

- λ=0.075 的**正 OD cell 数 = 71,136**（6.2B `allocate_cells` 要求每个正 cell ≥1 agent）。
- 因此 `target_agents ≥ 71,136`；**50k 会直接 `ValueError`（不可行）**；100k 是可行且推荐的最低标定档。
- 均值 EF @100k = ΣT/100k = 4.59794（@200k = 2.29897）。

## 5. ★容量与采样率的耦合（本步最需要你裁定的点）

若 N_sample 从 200k 降到 100k 而 **f_cap 固定 1.00**，则车密度减半 → **每车经历的供给饱和度被改变** → S100 与 S200 的差异混杂了「采样效应」与「供给/需求比效应」，无法判定 100k 是否为可替代样本。

要保持**同一物理交通场景**，`flowCapacityFactor` 必须随采样率同比缩放：

| 变体 | N_sample | f_cap | 物理含义 |
|---|---:|---:|---|
| S200（=D01/E06） | 200,000 | 1.00 | 参考场景 |
| S100 | 100,000 | **1.00** | 用户指定：同容量减样本（供给/需求比改变） |
| S100c | 100,000 | **0.50** | 采样一致：f_cap = N/200k，**保持同一物理场景** |

> 判定逻辑：若 `S100c×SCALE ≈ S200×SCALE` 而 `S100×SCALE` 明显偏离，则可同时得到两个结论——（a）100k 是可替代样本；（b）**一旦改变采样率，capacity 就不能再独立冻结 1.00**（这是采样一致性的数学要求，不是把 capacity 当性能旋钮）。

## 6. 实验矩阵

| 实验 | 角色 | N_sample | f_cap | SCALE | 模式 |
|---|---|---:|---:|---:|---|
| **S200** | reference_200k | 200,000 | 1.00 | 2.29897 | `REUSE_E06` |
| **S100** | calibration_sample_100k | 100,000 | 1.00 | 4.59794 | `RUN` |
| **S100c** | sample_consistent_100k | 100,000 | 0.50 | 4.59794 | `RUN_OPTIONAL` |

## 7. 100k 人口管线（本脚本执行，全部写入新目录）

| 阶段 | 脚本（冻结件，仅 patch 目录常量） | 输出 |
|---|---|---|
| 1 | `build_matsim_population_6_2b.py --target-agents 100000` | `reports/matsim_population_6_2b_s100k/` |
| 2 | `prepare_connected_scenario.py`（复用冻结 `network_cleaned.xml.gz`） | `reports/matsim_population_6_2b_connected_s100k/` |
| 3 | `build_departure_profile_6_3_3a.py` | `reports/matsim_departure_6_3_3a_s100k/` |

> **不覆盖**冻结 200k 三阶段产物（`matsim_population_6_2b` / `..._connected` / `matsim_departure_6_3_3a`）；只 monkeypatch 目录常量，构建逻辑与守恒校验逐字节复用。

## 8. 本次构建校验

| 阶段 | persons | ΣEF | ΣodTrips | 复用 |
|---|---:|---:|---:|---|
| 6.2B_population | 100,000 | 459,794.0 | 1,366,823.4 | False |
| connectivity_repair | 100,000 | 459,794.0 | 1,366,823.4 | False |
| departure_profile | 100,000 | 459,794.0 | 1,366,823.4 | False |

**构建状态：PASS**（判据：persons == 100,000 且 ΣEF == 459,794）

## 9. 已识别但本步不做的

- 不继续 7.4.3 的 f=1.15/1.20/1.25 细扫；不动 capacity（除 S100c 的采样一致对照）。
- λ 仍不冻结（本轮所有实验固定 λ=0.075 仅为控制变量）。
- 50k 探索档当前**不可行**（< 正 OD cell 数 71,136）。

---

口径：观测 7.1 冻结；仿真 `median(edges HRSx-yavg) × SCALE`；crosswalk = 7.3.6A Final；randomSeed=4711；20 it；ReRoute 拥堵反馈启用。
