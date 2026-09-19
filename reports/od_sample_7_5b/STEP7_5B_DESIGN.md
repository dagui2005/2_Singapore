# Step 7.5B — Sampling Rule Sensitivity（采样规则敏感性）

**零仿真设计 + 100k 人口管线 + 一份 MATSim 实验**。核心问题：100k 的残余非线性，究竟来自**样本数量**，还是来自**低样本下「每正 OD cell ≥1 agent」保底采样规则**本身？

## 1. 为什么先做 7.5B，而不是 125k/150k/175k knee 扫描

7.5A 的 S100c（100k, f_cap=0.50）给出两条**同时成立**的信号：

| 信号 | 数值 | 含义 |
|---|---|---|
| (a) `CATA/SLIP` 漂移 | 0.0480（S100）→ **0.0233**（S100c），C6 PASS | 「采样导致的供需密度变化」是重要机制，且**可被容量同比缩放吸收** |
| (b) `raw ratio` / `Pearson` | **0.5799**（≠0.50）；Pearson 0.9006 → **0.8557** | 仍存在**第二层：样本空间分布偏差** |

6.2B `allocate_cells` 规定「**每个正 OD cell 至少 1 个 agent**，余量按 trips largest-remainder 分配」。该保底规则让小 trips 的 cell 获得**相对过多**代表个体，且畸变随 N 减小而急剧放大：

| N_sample | 保底 agent 数 | 占全部 agent 比例 |
|---:|---:|---:|
| 200,000 | 71,136 | **35.6%** |
| 100,000 | 71,136 | **71.1%** |

→ 因此在做任何样本量扫描之前，必须先回答：**保底采样到底是不是残余非线性的主因。**两者后续处理完全不同：若 S100r 改善 → 保留 100k 但改采样算法；若 S100r 仍偏离 → 才可认定存在 sample-size dependence。

## 2. 单变量设计（只改采样规则）

```text
S100c（现有规则）  每正 OD cell >= 1 agent  + largest-remainder    已完成，复用
S100r（纯比例）    不设保底；按 OD trips 比例直接抽 100k（允许 cell = 0 agent）  ← 本步
```

**完全冻结**：`N_sample=100,000` / `λ=0.075` / `flowCapacityFactor=storageCapacityFactor=0.50`（= N/N_ref，采样一致性校正）/ 20 iterations / `seed=4711` / `routingRandomness=0` / 同一 network / 同一 OD / 同一 departure profile / 同一 7.3.6A Final Crosswalk / 同一 7.1 观测靶场。

> `f_cap=0.50` 在此**仅作采样一致性校正**（保持同一物理供需比），**不是**交通供给标定参数——与 Phase 1 的 `capacity_factor` 严格区分。

## 3. 采样规则诊断（零仿真，本脚本直接算）

λ=0.075 正 OD cell 数 = **71,136**，ΣT = **459,794**。

| N_sample | 采样规则 | sampled cells | zero-sampled cells | OD coverage | 丢弃 trips | ΣEF | `f_realized` | agent 数 min/中位/max |
|---:|---|---:|---:|---:|---:|---:|---:|---|
| 100,000 | `FLOOR_PLUS_1` | 71,136 | **0** | 1.0000 | 0 (0.00%) | 459,794 | 1.00000 | 1/1/26 |
| 100,000 | `PURE_TRIPS_PROP` | 38,350 | **32,786** | 0.5391 | 21,528 (4.68%) | 438,266 | 0.95318 | 0/1/87 |
| 200,000 | `FLOOR_PLUS_1` | 71,136 | **0** | 1.0000 | 0 (0.00%) | 459,794 | 1.00000 | 1/2/114 |
| 200,000 | `PURE_TRIPS_PROP` | 46,843 | **24,293** | 0.6585 | 8,644 (1.88%) | 451,150 | 0.98120 | 0/1/175 |

> **读法**：保底规则下**零 cell 被遗漏**（coverage = 1.0），但小 cell 被系统性高估；纯比例规则下 100k 有大量 cell 被抽到 0（其 trips 无代表个体），agent 集中到高 trips 的 cell（max 26 → 87）。

## 4. 实验矩阵

| 实验 | 角色 | 采样规则 | N_sample | f_cap | SCALE | 模式 |
|---|---|---|---:|---:|---:|---|
| **S200** | reference_200k | `FLOOR_PLUS_1` | 200,000 | 1.00 | 2.29897 | `REUSE_E06` |
| **S100c** | baseline_rule_100k | `FLOOR_PLUS_1` | 100,000 | 0.50 | 4.59794 | `REUSE_EXISTING` |
| **S100r** | pure_proportional_100k | `PURE_TRIPS_PROP` | 100,000 | 0.50 | 4.59794 | `RUN` |

## 5. S100r 人口管线（本脚本执行，全部写入新目录）

| 阶段 | 脚本（冻结件，仅 patch 目录常量 + 替换采样函数） | 输出 |
|---|---|---|
| 1 | `build_matsim_population_6_2b.py`（`allocate_cells` → 纯比例） `--target-agents 100000` | `reports/matsim_population_6_2b_s100r/` |
| 2 | `prepare_connected_scenario.py`（复用冻结 `network_cleaned.xml.gz`） | `reports/matsim_population_6_2b_connected_s100r/` |
| 3 | `build_departure_profile_6_3_3a.py` | `reports/matsim_departure_6_3_3a_s100r/` |

> **不覆盖**冻结件（200k 三阶段产物、7.5A 的 `*_s100k` 三阶段产物、S100c 输出）。空间实现逻辑（URANOF/POI→link 抽样、XML 写出、守恒校验）**逐字节复用**，只替换 `allocate_cells`。

## 6. 本次构建校验

| 阶段 | persons | ΣEF | ΣodTrips | 复用 |
|---|---:|---:|---:|---|
| 6.2B_population_pure_prop | 100,000 | 438,266.0 | 3,008,263.8 | False |
| connectivity_repair | 100,000 | 438,266.0 | 3,008,263.8 | False |
| departure_profile | 100,000 | 438,266.0 | 3,008,263.8 | False |

**OD 覆盖与守恒（7.5B 要求输出的 6 项）**

| 量 | 值 |
|---|---:|
| positive OD cells | 71,136 |
| sampled OD cells | 38,350 |
| **zero-sampled OD cells** | **32,786** |
| **OD coverage** | **0.5391** |
| 未承载 trips（dropped） | 21,528 |
| `f_realized` = ΣEF/ΣT | **0.95318** |
| 逐 cell 重构误差 max（全体） | 2.0468 |
| 逐 cell 重构误差 max（被采样 cell） | 5.684e-14 |

**构建状态：PASS**（判据：persons == 100,000；采样 cell 逐 cell 守恒误差 ≈ 0）

## 7. 已识别但本步不做的

- 不做 125k/150k/175k 样本量 knee 扫描（须待 7.5B 机制结论）；
- 不动 capacity（`f_cap=0.50` 仅作采样一致性校正）；
- 不跑纯比例 @200k（可作为后续对称对照）；
- **λ 仍不冻结**（固定 0.075 仅为控制变量）。

---

口径：观测 7.1 冻结；仿真 `median(edges HRSx-yavg) × SCALE`；crosswalk = 7.3.6A Final；randomSeed=4711；20 it；ReRoute 拥堵反馈启用。
