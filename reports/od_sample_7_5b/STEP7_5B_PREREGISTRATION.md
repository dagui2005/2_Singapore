# Step 7.5B — Sampling Rule Sensitivity 预注册判据（跑前固定）

**登记对象**：S100r (N=100,000, f_cap=0.50, PURE_TRIPS_PROP) vs S100c (N=100,000, f_cap=0.50, FLOOR_PLUS_1) vs S200 (N=200,000, f_cap=1.00)

**唯一变量**：sampling_rule（其余：λ=0.075 / N=100k / f_cap=0.50 / 20 it / seed=4711 / 同网络·OD·出发剖面·crosswalk·靶场）

**要回答的机制问题**：100k 的残余非线性来自「样本数量不足」还是「保底采样规则的系统性空间偏差」？

## 判据表

| ID | 组 | 判据 | 门槛 |
|---|---|---|---|
| D1 | absolute | 动力学等价性：raw flow ratio 中位 ≈0.50 | **硬门槛** |
| D2 | absolute | 扩样后等价性：scaled S100r/S200 中位 ≈1.00 | **硬门槛** |
| D3 | absolute | scaled ratio ±10% 内占比（仅报告） | —（仅报告） |
| D4 | absolute | scaled ratio ±20% 内占比 ≥0.80 | **硬门槛** |
| D5 | absolute | Pearson≥0.90 且 Spearman≥0.95 | **硬门槛** |
| D6 | absolute | 结构保持：|Δ(CATA÷SLIP) vs S200| ≤0.05（08-09） | **硬门槛** |
| D7 | absolute | 三窗口方向一致（|Δ|≤0.05 且同号） | **硬门槛** |
| M1 | mechanism | raw ratio 比 S100c 更接近 0.50 | **硬门槛** |
| M2 | mechanism | scaled ±20% 内占比 ≥ S100c | **硬门槛** |
| M3 | mechanism | Pearson ≥ S100c | **硬门槛** |
| M4 | mechanism | |Δ(CATA÷SLIP)| ≤ S100c | **硬门槛** |

**D 组 = 绝对判据**（与 7.5A 的 C1–C7 同阈值，便于与 S100c 直接比较）；
**M 组 = 机制判据**（差分：S100r 相对 S100c 是否改善）。

## 判决规则

- **`SAMPLING_RULE_WAS_THE_CAUSE`**：D1–D7 全 PASS → 100k 可用，但必须改采样算法（去保底）
- **`PARTIAL_IMPROVEMENT`**：M 组 ≥3 项改善但 D 未全过 → 保底规则是残余偏差的**贡献来源**之一，仍不足以让 100k 达标
- **`SAMPLE_SIZE_DEPENDENT`**：M 组改善 <3 项 → 保底规则**不是**主因；残余非线性来自样本量本身（此时 knee 扫描才有意义）

## 阈值依据

- **D1**：与 7.5A 的 C1 同阈值；S100c 实测 0.5799 未过
- **D2**：与 7.5A 的 C2 同阈值；S100c 实测 1.1537 未过
- **D3**：用户口径：仅要求尽可能高
- **D4**：与 7.5A 的 C4 同阈值；S100c 实测 0.2648
- **D5**：与 7.5A 的 C5 同阈值；S100c 实测 0.8557/0.9344
- **D6**：与 7.5A 的 C6 同阈值；S100c 实测 0.0233 PASS
- **D7**：与 7.5A 的 C7 同阈值；S100c 实测符号不一致（FAIL）
- **M1**：机制判据：去保底后采样非线性是否缩小
- **M2**：机制判据：逐断面等价性是否回升
- **M3**：机制判据：空间形态相关性是否回升（S100c 相对 S100 反而下降）
- **M4**：机制判据：结构漂移是否不再变差

## 口径与语义

- **容量语义**：f_cap=0.50 = N_sample/N_ref，仅作**采样一致性校正**（保持同一物理供需比），不是交通供给标定参数。
- **缩放语义**：主口径 SCALE = ΣT/N_sample（三方名义需求相同，隔离采样规则效应）；S100r 的 raw-EF 敏感性口径 = ΣEF_sampled/N = 4.38266（整体 ×0.95318）。

> 本文件与 `preregistered_criteria_7_5b.json` 在 **S100r 评价运行之前**生成；判据不得因结果而事后调整。
