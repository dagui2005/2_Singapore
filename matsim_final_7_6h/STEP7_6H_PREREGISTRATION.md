# Step 7.6H 预注册 — **最终工作点确定与独立验证**（不是「最终标定」，也不是参数搜索）

> 冻结时间：**2026-09-18T21:09**  
> 上游：7.6G 已闭环并**按现口径冻结**（`LAMBDA_DETECTABLE_NOT_IDENTIFIABLE / SPATIAL_INERT`），
> 本步**不在 λ 网格上继续消耗算力**，仅在**一个已确定的工作点**上做一次独立验证。

## 0. 第一层：冻结工作点（全部只读引用，本步骤不重估）

| 项 | 冻结值 | 来源 / 规则 |
|---|---|---|
| `lambda_ref` | **0.075** | 7.6G 敏感度中心（⛔ 非数据最优 λ） |
| `f_demand_ref` | **1.180222** | 7.6G L75 直跑实测隐含 f* |
| `f_demand_interp` | **1.1803** | 7.6F-1 曲线插值（对照，非主值） |
| `N_base` | **200,000** | 采样基准（仅作 SCALE 锚） |
| `N_sim` | **236,044** | round(f_ref × 200,000) ⇒ 物理加车 |
| `SCALE` | **2.29897** | ★ΣT/N_base；⛔ 不得改为 459,794/N_sim |
| `f_cap` | **1.00** | 冻结（非性能旋钮） |
| `route_choice` | **R01_rc_min** | 7.6E 冻结：innovation 0.8 / [ReRoute .15, ChangeExpBeta .85] / lr .5 / randomness 0 |
| `iterations` | **20** | 判据取 it.19 linkstats |
| `target` | **7.3.6A Frozen Final Crosswalk** | 只读；要改须另立 7.3.6A-b |
| `primary_metric` | **MATCHED Sim/Obs 08-09** | HRS8-9avg |
| `primary_window` | **Qbar_10:19** | ΣHRS0-24avg（与 Sim/Obs 窗口⛔不可混用） |
| `reference_window` | **Q_19** | 同上 |
| `band_lambda` | **[1.1637, 1.1938]** | 7.6G λ 敏感带（动态响应） |
| `band_static_target` | **[1.06945, 1.16418]** | 7.6C-2 静态靶场带（⛔ 不与 λ 带合并） |

> `N_sim = round(1.180222 × 200,000) = **236,044**`；若把 f 四舍五入为 1.1802 则得 236,040（差 **4 agent**，均已披露）。
> **★SCALE 冻结披露**：若误按 `459,794 / 236,044` 重算得 `1.947916`，相对冻结值漂 **-152700 ppm** ⇒ **NOT USED**。

## 1. 第二层：一次独立 200k 最终验证

| 项 | 值 |
|---|---|
| 实验臂 | `W01`（λ=0.075，唯一臂，⛔ 不扫 λ、不扫 demand） |
| 被仿真 agent | **236,044** |
| 配置 | `config_W01_rc_min.xml`（与 R01 差异须**恰为 3 项白名单**） |
| 迭代 | 20（判据取 `it.19` linkstats） |
| 与 7.6G `L75` 的关系 | **独立实例化**（agent 数 236,044 vs 236,000 ⇒ `ΣEF` 分布不同） |

## 2. 本步只回答 5 个问题（H1–H5）与预注册判据

### H1｜可复现性（工作点是否复现 7.6G）

| 判据 | 阈值 | 说明 |
|---|---:|---|
| `\|Sim/Obs_FROZEN − 1.000\|` | ≤ **1.0 pp** | 达标即「总体量级匹配」 |
| `\|implied f*_H − 1.180222\|` | ≤ **0.005** | 与 7.6G `L75` 直跑值一致 |
| `\|f_realized − 1.180222\|` | ≤ **0.001** | 人口产物实测 |
| `\|Sim/Obs_H − Sim/Obs_L75\|`（= 0.9998291） | ≤ **1.0 pp** | 独立复现 |
> ⛔ 参照值 `R01` 的隐含 f\* = 1.36356 **不参与 H1**：局部割线向低需求侧外推的参照值，⛔ 不作需求尺度估计、不参与 λ 比较。

### H2｜稳定性（在最终工作点上是否重新产生不稳定）

| 判据 | 阈值 |
|---|---:|
| `A_10:19`(MATCHED) | < **3.0%** |
| `A_10:19`(CATA) | < **3.0%** |
| `A_10:19`(SLIP) | < **5.0%** |
| `parity_gap_rel`(MATCHED) | < **5.0%** |
| `\|Q_19/Q̄_10:19 − 1\|` | < **1.0%** |
| `never_arrived`（it.19） | == **0**（承 7.6E G5，严格 0） |
| `max_stuck_car`（it.19） | == **0**（承 7.6E G5，严格 0） |

### H3｜空间残差是否仍然存在（**不追求消除**）

报告 `EAST / CENTRAL / NORTH / NORTH-EAST / radial_in / radial_out` 及关键 PA 的 `rel_dev`，
并与 7.6G `L75`（同工作点）、7.6F-1 的空间格局对照：

- 判据（**格局保持**）：每个分组的 `\|rel_dev_H − rel_dev_L75\|` ≤ **2.0 pp**
- 若保持 ⇒ 结论：**最终需求标定只解决总体量级，不改变既有空间结构残差**（`SPATIAL_RESIDUAL_PERSISTS`）
- ⛔ **不得**为「把空间误差消掉」而回头调 demand / λ（7.6F-1/7.6G 已证两者都压不平，且均 < 3 pp）

### H4｜λ 敏感性边界（表述层硬约束）

最终报告**不得**只写「λ=0.075」，必须写成三层、且**三层来源不同不得合并**：

| 层 | 区间 / 值 | 来源 |
|---|---|---|
| 基准工作点 | `λ = 0.075`，`f* = 1.180222` | 7.6G `L75` 直跑 |
| λ 敏感带 | `[1.1637, 1.1938]` | 7.6G λ=0.05/0.10 两端（**动态响应**不确定） |
| 静态靶场带 | `[1.06945, 1.16418]` | 7.6C-2 `TARGET_MARGINAL_COARSE_ONLY` |

### H5｜哪些问题**没有**解决（必须保留）

最终报告必须显式声明（而非「所有指标都很好」）：

> **总体交通量尺度已达到可接受的匹配水平，但 EAST / NE / radial 等空间残差仍然存在；其对需求尺度与 λ 的敏感性都较低，因此不宜通过继续调整需求尺度或 λ 强行消除。**

另须保留三项**本地不可定量**（须外部数据）：① 观测车型构成；② AM 峰占日通勤比重；③ 平均载客率。

## 3. 判决空间（预注册）

| 维度 | 取值 | 条件 |
|---|---|---|
| 主 | `WORKING_POINT_FROZEN_AND_REPRODUCIBLE` | H1 全过 且 H2 全过 |
| 主 | `WORKING_POINT_NOT_REPRODUCIBLE` | H1 有不过 |
| 主 | `WORKING_POINT_FROZEN_BUT_UNSTABLE` | H1 全过 且 H2 有不过 |
| 空间 | `SPATIAL_RESIDUAL_PERSISTS` | H3 全过（格局保持） |
| 空间 | `SPATIAL_SHIFTED` | H3 有不过（空间格局被改变 ⇒ 需登记） |

## 4. 本步**明确不做**（用户 2026-09-18 21:05 裁定）

- ✗ **不再细搜 λ**（7.6G 已判 `DETECTABLE_NOT_IDENTIFIABLE`，边际收益已很低）
- ✗ **不再细化 demand grid**（不做 1.17/1.18/1.19/1.20 细扫，不做 3×4 λ×demand 网格）
- ✗ **不做** crosswalk-b（靶场保持 7.3.6A Frozen，**未修改**）
- ✗ 不改 7.1 / 7.3.6A / OD / network / capacity / route-choice 任一冻结件
- ✗ 不把 `POSITIVE_ONLY` / `BEST_DIRECTION` 升格为正式标定靶场
- ✗ 不把三层不确定带压成单一「最终置信区间」

## 5. 冻结件未变（本步骤隔离性证据）

- 监视冻结件 **8** 个；mtime 变化 **0** 个
- ✅ 全部未变（mtime 逐项一致）

## 6. 零仿真校验（复用 7.6G 机器）

共 **24** 项，PASS **24**。

（全部通过）

## 7. 产物

- `final_workingpoint_7_6h_matrix.csv`
- `final_workingpoint_7_6h_frozen_parameters.csv`
- `final_workingpoint_7_6h_config_provenance.csv`
- `final_workingpoint_7_6h_source_invariance.csv`
- `final_workingpoint_7_6h_config_validation.json`
- `STEP7_6H_PREREGISTRATION.md`
- `README.md`
- `populations/pop_W01/…`
- `configs/config_W01_rc_min.xml`
- `outputs/W01_rc_min/…（run 后）`
- `audit/…（评价后）`
