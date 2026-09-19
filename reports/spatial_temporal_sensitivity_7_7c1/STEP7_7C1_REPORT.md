# Step 7.7C-1 — 时段实现敏感性（零仿真解析上界）

## 0. 判决问题

> 在不改变 OD 空间结构、不重新仿真、不修改冻结校准口径的前提下，
> **合理的出发时段分散最多能给现有空间残差带来多大的变化？**

本步骤计算的不是「改 departure time 后 MATSim 会得到什么」，而是
**temporal-only null 下的解释力上界**。

## 1. 方法与关键修正

temporal-only separable null，使用 **断面级** 时段份额：

```
sim_8_9(s | P) = sim_8_9_scaled(s) x share_8_9(s | P)
```

分离两个效应：

- **(a) 总体水平效应** `rho_glob = Σ(sim·share) / Σ obs` —— 时段分配改变 HRS8-9 总量；
- **(b) 空间结构效应** `rel_dev_g = rho_g / rho_glob − 1` —— **判据只看这一个**。

> ⚠️ **方法学要点**：若 `share_8_9` 取「全局常量」，则 `rel_dev_g` 在任何 profile 下
> **恒等不变**（数学必然），那种设计无法回答空间敏感性。
> 本脚本因此显式保留 `P1_UNIFORM_50` 作为**退化参照**，并改用断面级 `share_8_9(s)`
> （来自 6.3.3A 冻结底表 `trafficflow_link_hour_basis.csv`）。

断面级 `share_8_9(s) = h8/(h7+h8)` 的实测异质性：
CV = **0.0909**，范围 [0.2783, 0.7931]，
全网值 0.512897。

## 2. MUST_MATCH 7.6H（口径未漂移）

| 量 | 本步骤 (P0) | 7.6H 冻结 | 判定 |
|---|---|---|---|
| global Sim/Obs | 0.9993348 | 0.9993348 | PASS |
| EAST rel_dev | -0.317524 | -0.317524 | PASS |
| NE rel_dev | +0.338833 | +0.338833 | PASS |
| radial_in rel_dev | -0.306727 | -0.306727 | PASS |

P0 基线完全复现 7.6H ⇒ 时段分析建立在未漂移口径上。

## 3. Temporal profiles

| profile | source | share_mean | share_cv |
|---|---|---|---|
| P0_CONCENTRATED | W01 baseline | 1.000000 | 0.000000 |
| P1_UNIFORM_50 | degenerate reference | 0.500000 | 0.000000 |
| P2_TF_SECTION | 6.3.3A section-level | 0.501478 | 0.090857 |
| P3_TF_AMP2 | extrapolated heterogeneity x2 | 0.499855 | 0.180576 |
| P4_TF_MIRROR | adversarial structural mirror | 0.498522 | 0.091395 |
| P5_BAND_P10 | day-level p10 feasible floor | 0.462486 | 0.137244 |
| P6_BAND_P90 | day-level p90 feasible ceiling | 0.536377 | 0.081102 |

## 4. 判据焦点：三条命名残差组

| dim | group | n | rel_dev(P0) | min | max | span | max\|Δ\| | Δ/残差 |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| region | EAST REGION | 133 | -0.3175 | -0.3549 | -0.2992 | 0.0557 | 0.0374 | 0.118 |
| region | NORTH-EAST REGION | 77 | +0.3388 | +0.3285 | +0.3417 | 0.0131 | 0.0103 | 0.030 |
| radial | radial_in | 164 | -0.3067 | -0.3283 | -0.2983 | 0.0301 | 0.0216 | 0.070 |

**结论**：即使采用「异质性外推 ×2」、「结构镜像」或「逐链路日级 p10 连贯最坏」等
对抗性 profile，EAST / radial_in / NE 的位移上界仍在 **1–4 pp** 量级，
而其残差本身为 **−31.8% / −30.7% / +33.9%**。

## 5. 全组 envelope

| dim | group | n | rel_dev(P0) | min | max | span | max\|Δ\| | Δ/残差 |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| has_reciprocal_pair | True | 98 | -0.6286 | -0.6416 | -0.6021 | 0.0395 | 0.0265 | 0.042 |
| ring | R5_20km+ | 34 | -0.5590 | -0.5960 | -0.5408 | 0.0551 | 0.0370 | 0.066 |
| region | NORTH-EAST REGION | 77 | +0.3388 | +0.3285 | +0.3417 | 0.0131 | 0.0103 | 0.030 |
| region | EAST REGION | 133 | -0.3175 | -0.3549 | -0.2992 | 0.0557 | 0.0374 | 0.118 |
| radial | radial_in | 164 | -0.3067 | -0.3283 | -0.2983 | 0.0301 | 0.0216 | 0.070 |
| region | NORTH REGION | 72 | +0.2309 | +0.1865 | +0.2377 | 0.0512 | 0.0443 | 0.192 |
| ring | R1_0-5km | 61 | -0.2287 | -0.2557 | -0.1713 | 0.0845 | 0.0574 | 0.251 |
| has_reciprocal_pair | False | 478 | +0.2043 | +0.1957 | +0.2085 | 0.0128 | 0.0086 | 0.042 |
| ring | R3_10-15km | 244 | +0.1952 | +0.1594 | +0.2127 | 0.0532 | 0.0357 | 0.183 |
| radial | radial_out | 256 | +0.1450 | +0.1397 | +0.1768 | 0.0371 | 0.0318 | 0.219 |
| radial | circumferential | 154 | +0.0961 | +0.0660 | +0.1020 | 0.0360 | 0.0302 | 0.314 |
| region | CENTRAL REGION | 112 | -0.0782 | -0.0991 | -0.0201 | 0.0790 | 0.0581 | 0.743 |
| ring | R4_15-20km | 163 | -0.0330 | -0.0805 | -0.0178 | 0.0626 | 0.0475 | 1.441 |
| region | WEST REGION | 180 | +0.0284 | +0.0023 | +0.0391 | 0.0368 | 0.0261 | 0.918 |
| ring | R2_5-10km | 72 | -0.0267 | -0.0378 | +0.0192 | 0.0570 | 0.0458 | 1.719 |

## 6. radial × reciprocal 结构稳定性

| radial | has_reciprocal_pair | P0_CONCENTRATED | P1_UNIFORM_50 | P2_TF_SECTION | P3_TF_AMP2 | P4_TF_MIRROR | P5_BAND_P10 | P6_BAND_P90 |
|---|---|---|---|---|---|---|---|---|
| circumferential | False | +0.1626 | +0.1626 | +0.1634 | +0.1642 | +0.1618 | +0.1300 | +0.1695 |
| circumferential | True | -0.4170 | -0.4170 | -0.4303 | -0.4438 | -0.4039 | -0.4286 | -0.4200 |
| radial_in | False | -0.0078 | -0.0078 | -0.0243 | -0.0411 | +0.0085 | -0.0413 | -0.0106 |
| radial_in | True | -0.8261 | -0.8261 | -0.8208 | -0.8155 | -0.8312 | -0.8269 | -0.8226 |
| radial_out | False | +0.3555 | +0.3555 | +0.3545 | +0.3534 | +0.3565 | +0.3827 | +0.3464 |
| radial_out | True | -0.5078 | -0.5078 | -0.4827 | -0.4572 | -0.5326 | -0.4616 | -0.4963 |

- 排序保持（region / radial / ring）：**True / True / False**
- 极值组保持（region / radial / ring）：**True / True / True**
- 逐 profile 排序检验：`c1_rank_preservation.csv`

> 注 1：**region 与 radial 的组间排序在全部 7 个 profile 下严格保持**（EAST 恒为最低区域、
> NE 恒为最高区域、`radial_in` 恒为最低 radial）。唯一的排序变动发生在 `ring` 维的
> P4/P6，且仅在 `R2_5-10km` 与 `R4_15-20km` 之间交换——二者基线 rel_dev 仅差 0.006（近似并列），
> 属噪声级。
> 注 2：`UNMAPPED`（2 断面，无 PA/region 归属）已从本步骤全部统计中剔除，仅保留在逐断面底表。
> 注 3：`radial_in | recip=False` 基线 rel_dev = -0.0078
> ⇒ ρ_g/ρ_glob ≈ 0.9922，
> 等价 pooled ratio ρ_g ≈ 0.9915
> （与 7.7C-0 的 0.9915 一致）。
> 该「近无偏子组」在所有 temporal profile 下位移 ≤ 0.04，不随时段分配改变。

## 7. 两个效应分离

| 效应 | 量级 | 归因 |
|---|---|---|
| (a) 总体水平 | 全局 Sim/Obs 由 0.9993 → P2 的 0.4972 | 时段分配本身 ⇒ **水平效应**，非空间机制 |
| (b) 空间结构 | 组间 `rel_dev` 位移 ≤ 0.0581 | 与残差 0.6286 相比 **0.092** |

## 8. HTS gate

| 量 | 值 |
|---|---|
| `S_spatial`（全组 max\|rel_dev(P0)\|） | +0.6286 |
| `A_temporal`（全组 max\|Δrel_dev\|） | +0.0581 |
| ratio（全组） | 0.0924 |
| `S_spatial`（命名组） | +0.3388 |
| `A_temporal`（命名组） | +0.0374 |
| ratio（命名组） | 0.1104 |
| 排序保持 region / radial | True / True |

**VERDICT: `TEMPORAL_SPATIAL_SENSITIVITY_FAIL_DEFER_HTS`**（判据 PASS≥0.50 / PARTIAL≥0.20 / FAIL<0.20）

判读：时段可达位移相对残差仅 **11.0%**（命名组口径；全组口径 9.2%），
且 EAST / radial_in / NE 的组间排序与符号在全部 profile 下不变
⇒ **出发时段不是当前空间残差的主导机制**。

## 9. 局限（必须随结论引用）

本步骤是 temporal-only separable null，**无法**表征：

- route-choice 在当前时段分配下的重选；
- 拥堵溢出 / spillback 的时空耦合；
- 时段分散后 demand level 需重新标定的连锁效应。

因此结论严格表述为：**「时段分配本身」不足以解释现有空间残差**；
若 HTS 能提供独立行为证据或需检验
`departure-time × route-choice × congestion` 耦合，仍可进入 7.7B。

- MATSim rerun: **False** ｜ parameters changed: **False**
- lambda selected: **False** ｜ demand scale selected: **False**
