# Step 7.3.4 — LTA 断面语义 ↔ MATSim 微段：重构与 Sim/Obs 收敛判别（PASS）

> 目标：把 `LTA section` 重建为「同向 + 同类 + 连续」的 MATSim link 集，再复算 `q_sim/q_obs`，
> 检验 CATA 0.685 / SLIP 2.046 是否向 1 收敛。
> **零仿真**：不改 OD / λ / population / departure profile / network / capacity / route choice。

## Part A. 重构结果（audit_section_rebuild_7_3_4.py）

| 指标 | 值 |
|---|---|
| 原断面 / 重构断面 | 1278 / 1278 |
| 重构 crosswalk 边数 | 6008 |
| 每断面平均边 / 中位 | 4.70 / 4 |
| 平均方向一致率 | 97.51% |
| 平均语义一致率 | 88.48% |
| CATA dominant=motorway | 97.64% |
| SLIP dominant=motorway_link | 52.99% |
| SLIP dominant=motorway | 41.43% |
| strict / fallback | 87.47% / 12.53% |

## Part B. Sim/Obs 收敛判别（analyze_section_rebuild_flow_7_3_4.py）

### B-1 明细口径

> 口径（与 7.1 冻结一致）：`sim = median(匹配边 HRSx-yavg) × 2.29897`；`obs_am = obs_7_8 + obs_8_9`。
> 唯一变量 = 匹配边集（old 6.3.2 crosswalk vs rebuilt）。不改 OD/λ/population/departure/network/capacity/route choice。

## 1. 08–09 时段 Σsim/Σobs（主判据）

| crosswalk | CATA Σsim/Σobs | SLIP Σsim/Σobs | CATA/SLIP |
|---|---|---|---|
| old (7.1 冻结) | 0.7388 | 2.0333 | 0.3633 |
| rebuilt (full) | 0.7707 | 1.8796 | 0.4100 |
| rebuilt (strict-only) | 0.7797 | 0.8535 | 0.9135 |

## 2. 逐时段 × 等级 明细

### CATA

| crosswalk | window | n | Σsim | Σobs | Σsim/Σobs | mean-ratio |
|---|---|---|---|---|---|---|
| old_7_1 | 07-08 | 339 | 752958 | 1289714 | 0.5838 | 0.7598 |
| old_7_1 | 08-09 | 339 | 971641 | 1315205 | 0.7388 | 1.0293 |
| old_7_1 | AM | 339 | 1724599 | 2604919 | 0.6621 | 0.8844 |
| rebuilt_full | 07-08 | 339 | 774560 | 1289714 | 0.6006 | 0.7140 |
| rebuilt_full | 08-09 | 339 | 1013604 | 1315205 | 0.7707 | 0.9244 |
| rebuilt_full | AM | 339 | 1788164 | 2604919 | 0.6865 | 0.8110 |
| rebuilt_strict_only | 07-08 | 339 | 763104 | 1255518 | 0.6078 | 0.7200 |
| rebuilt_strict_only | 08-09 | 339 | 999315 | 1281694 | 0.7797 | 0.9390 |
| rebuilt_strict_only | AM | 339 | 1762419 | 2537212 | 0.6946 | 0.8212 |

### SLIP_ROAD

| crosswalk | window | n | Σsim | Σobs | Σsim/Σobs | mean-ratio |
|---|---|---|---|---|---|---|
| old_7_1 | 07-08 | 251 | 377040 | 236535 | 1.5940 | 2.3469 |
| old_7_1 | 08-09 | 251 | 481928 | 237022 | 2.0333 | 3.0269 |
| old_7_1 | AM | 251 | 858969 | 473557 | 1.8139 | 2.6578 |
| rebuilt_full | 07-08 | 251 | 348119 | 236535 | 1.4717 | 2.1043 |
| rebuilt_full | 08-09 | 251 | 445500 | 237022 | 1.8796 | 2.7655 |
| rebuilt_full | AM | 251 | 793619 | 473557 | 1.6759 | 2.4060 |
| rebuilt_strict_only | 07-08 | 251 | 81773 | 117918 | 0.6935 | 0.7847 |
| rebuilt_strict_only | 08-09 | 251 | 100235 | 117443 | 0.8535 | 0.9591 |
| rebuilt_strict_only | AM | 251 | 182008 | 235362 | 0.7733 | 0.8663 |

## 3. 重构边集的方向/语义审计

| RoadCat | edges | direction_ok | opposite_edge | semantic_ok | mean|Δdir| |
|---|---|---|---|---|---|
| CATA | 1145 | 0.9493 | 0.0507 | 0.9214 | 9.83 |
| CATB | 3453 | 0.9734 | 0.0266 | 0.9458 | 6.49 |
| CATC | 265 | 0.9660 | 0.0340 | 1.0000 | 10.07 |
| CATD | 40 | 0.9500 | 0.0500 | 0.7000 | 13.74 |
| CATE | 2 | 1.0000 | 0.0000 | 1.0000 | 17.14 |
| SLIP_ROAD | 1103 | 0.9048 | 0.0952 | 0.6283 | 17.54 |

## 3.5 过滤归因（方向 vs 语义）——08-09 Σsim/Σobs

| 过滤 | CATA | SLIP_ROAD | CATA/SLIP |
|---|---|---|---|
| full | 0.7707 | 1.8796 | 0.4100 |
| dir_only | 0.7773 | 1.8513 | 0.4199 |
| sem_only | 0.7779 | 0.8055 | 0.9658 |
| strict | 0.7797 | 0.8535 | 0.9135 |

## 3.6 strict 过滤的断面覆盖（选择偏差检查）

| RoadCat | n | kept(strict) | dropped | obs_am kept 占比 |
|---|---|---|---|---|
| CATA | 339 | 326 | 13 | 0.9740 |
| CATB | 634 | 613 | 21 | 0.9723 |
| CATC | 46 | 45 | 1 | 0.9741 |
| CATD | 7 | 5 | 2 | 0.2530 |
| CATE | 1 | 1 | 0 | 1.0000 |
| SLIP_ROAD | 251 | 129 | 122 | 0.4970 |
| __ALL__ | 1278 | 1119 | 159 | 0.9224 |

## 4. 判读

- CATA/SLIP 相对比：old **0.3633** → rebuilt(full) **0.4100** → rebuilt(strict) **0.9135**。
- **strict 下明显向 1 收敛** ⇒ crosswalk 语义对齐是有效杠杆；full 未收敛是因未过滤断面稀释（见 3.6 覆盖率）。

> 注意：重构受**基座 crosswalk 候选集**约束——若某 SLIP 断面在 6.3.2 候选中本就不含 `motorway_link`，语义过滤无法凭空生成匝道边，纯度存在上界。
## Part D. 验收对照

| 指标 | 目标 | 实测 | 判定 |
|---|---|---|---|
| CATA motorway purity | >95% | 97.64% | ✅ |
| SLIP motorway_link purity | >90% | 52.99% | ❌（受候选集上界约束） |
| 对向边混入 | <10% | CATA 5.07% / SLIP 9.52% | ✅ |
| 断面中位边数 | 明显<8–12 | 4 | ✅ |
| CATA Sim/Obs→1 | — | 0.739 → 0.780 | ✅ 小幅 |
| SLIP Sim/Obs→1 | — | 2.033 → 0.853 | ✅✅ |
| CATA/SLIP 相对比 | 明显偏离0.36 | 0.363 → 0.914 | ✅✅ |

## Part E. 结论

1. **收敛成立，且归因明确**：08-09 时段 `CATA/SLIP` Σsim/Σobs 由 **0.363** →
   **0.914**（strict）。
2. **主因=语义而非方向**：仅加方向过滤几乎不动（0.42）；仅加语义过滤即达
   **0.966**。
   说明误差源于「SLIP 观测断面被匹配到 motorway 主线而非 motorway_link 匝道」。
3. **残差=覆盖缺口**：strict 下 SLIP 仅保留 **129/251** 断面（obs 覆盖 49.7%）；**117/251（46.6%）** 断面在基座
   crosswalk 中**根本没有 motorway_link 候选**（其中 104 个 dominant=motorway 主线）。
4. **CATA 稳定**：各过滤下 CATA 恒 ≈0.78（old 0.739），说明其 ~22% 系统性低估与 crosswalk 无关，
   属需求量级/全局尺度问题，非结构错配。
5. **技术路线判决**：**停止 route-choice 参数扫描**；下一步 = **network representation /
   crosswalk 覆盖修正**（对 ~47% 无匝道候选的 SLIP 断面重新推导断面语义），随后再议 λ / 需求尺度。

> 依赖说明：本步骤只在**既有候选集**内做方向+语义过滤，无法凭空生成匝道几何；
> 因此 SLIP 纯度存在由基座 crosswalk 决定的上界。