# Step 7.6C-2 — Calibration Target Integrity Gate

**Verdict: `TARGET_MARGINAL_COARSE_ONLY`**  — 零仿真、只读；未修改 crosswalk / OD / lambda；未启动 MATSim。

## 0. 它回答什么问题

> 当前 **7.3.6A frozen crosswalk**，是否仍然足以支持 demand scale 的**绝对识别**？

7.6C-1 已证明：54 个断面（占观测量 **8.137%**）匹配到了 router 从不使用的孤儿边 / 双向混配边（中位塔 0）。这是 **comparator** 的性质，不是 demand 的性质。因此在此步之前跑 1.10/1.20/1.25，会把 `demand response + comparator artifact` 混在同一条曲线里。

**本步不做**：不修改冻结件；不把 `0.9351` 升格为新靶场；不选 demand scale；不选 lambda；不跑 MATSim。

## 1. 三口径定义（按用户规定）

| 口径 | 含义 | 用途 |
|---|---|---|
| `FROZEN` | 全部断面池化 `Sum(sim)/Sum(obs)` | **主口径，不能擅改** |
| `POSITIVE_ONLY` | 仅 `sim>0` 断面池化 | **敏感性口径** |
| `BEST_DIRECTION` | `max(median(正向),median(反向)) x SCALE` | **误差边界，不作正式靶场** |

为保证 `Delta_target` 只反映**断面排除效应**而非定义变化，`FROZEN` 与 `POSITIVE_ONLY` 采用**同一函数形式**（池化比）。若改用 `FROZEN` 的另一种定义（逐断面比的 obs 加权均值），结论不变（见 §2）。

## 2. 口径值与交叉校验

| 口径 | Sim/Obs | 角色 |
|---|---|---|
| `FROZEN` | **0.858973** | 主口径，不能擅改 |
| `POSITIVE_ONLY` | **0.935062** | 敏感性口径 |
| `BEST_DIRECTION` | **0.890967** | 误差边界，不作正式靶场 |
| `MATCH_NEAREST_LOWER` | **0.820521** | 外包络下偏（探究） |
| `MATCH_SAMENAME_UPPER` | **1.064596** | 外包络上偏（探究） |

- `FROZEN`（改用逐断面加权均值定义）= `0.8589732`；与池化口径差 0.000000 ⇒ 结论不敏感。
- 7.6F-0 官方锚 `ANCHOR_SIM_OBS = 0.8590`（四舍五入）。
- 零流断面 **54/576**，承载 **123,217.0** obs veh/h = **8.137%**。
- **断面集口径澄清**：7.6C 的 `section_geography.csv` 只覆盖 **574/576** 个断面（缺 190339 YIO CHU KANG ROAD 与 195768 PAN ISLAND EXPRESSWAY，两者 obs/sim 均 > 0）。本步 **主口径统一取 576 全集**；7.6C-1 的 repair-bounds CSV 因其内部 `dropna` 实际按 **574** 计算，两者相差 4.06e-4（已在交叉校验中分开复现）。
- **断面集稳健性**：改用 574 子集，`Delta_target` = **7.619 pp**（主口径 7.609 pp），SNR 粗/1.053、细/0.527 ⇒ **结论不变**。

所有重算量均与 **7.6C / 7.6C-1 已落盘 CSV**逐位对齐（见 `target_integrity_crossvalidation.csv`）。

## 3. 核心量：靶场不确定性 vs demand 增量

### 3.1 Sim/Obs 单位

    Delta_target = Q_POSITIVE_ONLY - Q_FROZEN = 0.076089 = 7.609 pp

可接受口径带宽（FROZEN / POSITIVE_ONLY / BEST_DIRECTION）= **7.609 pp**；外包络 `0.8205 .. 1.0646`（24.408 pp，探究性）。

### 3.2 demand factor 单位（口径间的识别区间）

在 f* = Q^(-1/ε)（参考弹性 ε = 1）下：

| 口径 | Q | f* |
|---|---|---|
| `FROZEN` | 0.858973 | 1.16418 |
| `POSITIVE_ONLY` | 0.935062 | 1.06945 |
| `BEST_DIRECTION` | 0.890967 | 1.12238 |

    f* identification interval = [1.06945, 1.16418]
    Delta_f_target              = 0.09473

### 3.3 信噪比（项目自己的正式判据：SNR < 1 ⇒ 不可用于推断）

| 7.6F-1 阶跃 | 阶跃大小 Δf | Delta_f_target | SNR = Δf / Delta_f_target | 判定 | 需要的 ε |
|---|---|---|---|---|---|
| 粗档 1.10→1.20 | 0.10 | 0.09473 | **1.056** | 可用（勉强） | ≥ 0.947 |
| 细档 1.20→1.25 | 0.05 | 0.09473 | **0.528** | **不可用** | ≥ 1.895 |

即 **靶场不确定性与粗档 demand 增量同量级**（0.095 vs 0.10），是细档增量的 **0.53 倍倒数**（1/ε = 10.56）。

## 4. demand-响应网格与口径一致性

`Sim/Obs(f, caliber) = Q_caliber x f^eps`，参考弹性 eps = 1：

| f | FROZEN | POSITIVE_ONLY | BEST_DIRECTION | 口径一致 | 在 F-1 网格 |
|---|---|---|---|---|---|
| 1.00 | 0.8590 | 0.9351 | 0.8910 | 是 |  |
| 1.05 | 0.9019 | 0.9818 | 0.9355 | 是 |  |
| 1.10 ← | 0.9449 | 1.0286 | 0.9801 | **否** | 是 |
| 1.15 | 0.9878 | 1.0753 | 1.0246 | **否** |  |
| 1.20 ← | 1.0308 | 1.1221 | 1.0692 | 是 | 是 |
| 1.25 ← | 1.0737 | 1.1688 | 1.1137 | 是 | 是 |
| 1.30 | 1.1167 | 1.2156 | 1.1583 | 是 |  |
| 1.35 | 1.1596 | 1.2623 | 1.2028 | 是 |  |

### 4.1 网格位置诊断

- f* 可识别区间 = **[1.06945, 1.16418]**
- 提议网格 `[1.1, 1.2, 1.25]` 是否跨越该区间：**否**
- 落在区间**内部**（结论随口径而变）的网格点：**[1.1]**
- 3 次跑实际只能读出 **2** 个不同区制。

| f | 在 f* 区间内 | 口径一致 | 越过 1.0 的口径数 | 解释 |
|---|---|---|---|---|
| 1.10 | 是 | **否** | 1/3 | 口径分歧（结论不确定） |
| 1.20 | 否 | 是 | 3/3 | 全部越过 1.0 |
| 1.25 | 否 | 是 | 3/3 | 全部越过 1.0 |

### 4.2 网格重排建议

判据：最小间距 ≥ `Delta_f_target` = 0.09473，且网格必须跨越 [1.06945, 1.16418]。

| 候选网格 | 跑数 | 最小间距 | 间距 ≥ Delta_f_target | 跨越 f* 区间 | 可接受 |
|---|---|---|---|---|---|
| 1.00 / 1.10 / 1.20 | 3 | 0.10 | 是 | 是 | **是** |
| 1.05 / 1.15 / 1.25 | 3 | 0.10 | 是 | 是 | **是** |
| 1.10 / 1.20 / 1.30 | 3 | 0.10 | 是 | 否 | 否 |
| 1.00 / 1.05 / 1.10 / 1.15 / 1.20 / 1.25 | 6 | 0.05 | 否 | 是 | 否 |

**建议：`1.00 / 1.10 / 1.20`**（保留 3 次跑，且每个阶跃都不小于靶场不确定性）。

## 5. Delta_target 的空间分布

池化 Sim/Obs（按 Planning Region）：

| Region | N | 零流 N | 零流观测占比 | Q_FROZEN | Q_POSITIVE_ONLY | Delta_local | 相对全局(FROZEN) | 相对全局(POS) |
|---|---|---|---|---|---|---|---|---|
| WEST REGION | 180 | 27 | 12.30% | 0.8796 | 1.0030 | +0.1234 | +0.0240 | +0.0727 |
| CENTRAL REGION | 112 | 6 | 10.38% | 0.7903 | 0.8819 | +0.0916 | -0.0799 | -0.0569 |
| EAST REGION | 133 | 15 | 6.70% | 0.5824 | 0.6242 | +0.0418 | -0.3220 | -0.3325 |
| NORTH REGION | 72 | 4 | 2.38% | 1.0673 | 1.0933 | +0.0260 | +0.2425 | +0.1692 |
| NORTH-EAST REGION | 77 | 2 | 2.02% | 1.1579 | 1.1817 | +0.0238 | +0.3480 | +0.2638 |

池化 Sim/Obs（按 CBD 径向）：

| Radial | N | 零流 N | Q_FROZEN | Q_POSITIVE_ONLY | Delta_local | 相对全局(FROZEN) | 相对全局(POS) |
|---|---|---|---|---|---|---|---|
| radial_in | 164 | 39 | 0.6116 | 0.7834 | +0.1717 | -0.2880 | -0.1622 |
| circumferential | 154 | 8 | 0.9360 | 0.9618 | +0.0257 | +0.0897 | +0.0286 |
| radial_out | 256 | 7 | 0.9762 | 0.9991 | +0.0229 | +0.1365 | +0.0685 |

## 6. 结构结论是否被污染

- Planning Region 跨度（Q_POSITIVE_ONLY）= **0.5576**
- `Delta_target` = **0.0761**
- 倍数 = **7.33 x**（阈值 ≥ 5，判定 **PASS**）

⇒ 结构结论（7.6C 的区域缺口、7.6C-1 的 graded 缺口对修正稳健）**不受**靶场不确定性污染；但**绝对规模**受到。

## 7. 判据与裁定

| 判据 | 值 | 通过 |
|---|---|---|
| `P1.sections_missing_geography` | 2 | ✅ |
| `P1.directional_repair_reproduces_7_6C_1` | 0.0 | ✅ |
| `P1.crossvalidation_all_match` | 7 | ✅ |
| `G1.target_uncertainty_exists` | 0.076089 | ✅ |
| `G2.coarse_step_resolvable` | 1.0556 | ✅ |
| `G3.fine_step_resolvable` | 0.5278 | ❌ |
| `P2.verdict_invariant_to_section_set` | True | ✅ |
| `G4.caliber_agreement_on_grid` | 2 | ❌ |
| `G5.grid_brackets_fstar_interval` | False | ❌ |
| `G6.structural_separability` | 7.328 | ✅ |

### VERDICT = `TARGET_MARGINAL_COARSE_ONLY`

靶场不确定性与粗档 demand 增量同量级 ⇒ 7.6F-1 只能读“带靶场不确定性的粗档响应关系”，不能声称绝对 scale 已识别；网格需重排以使间距 >= Delta_f_target。

## 8. 分歧说明（为什么不是 ADEQUATE，也不是 INADEQUATE）

- **不是 `TARGET_ADEQUATE_FOR_ABSOLUTE_SCALE`**：细档 SNR = 0.528 < 1，且 f = 1.10 落在 f* 区间内部（口径分歧），且网格未跨越整个区间。
- **不是 `TARGET_INADEQUATE`**：粗档 SNR = 1.056 ≥ 1，且三口径在 **方向上一致**（f* > 1，需上调）。

⇒ 7.6F-1 可以进入，但**性质必须降级**：它读出的是“**带靶场不确定性的粗档 demand 响应关系**”，而不是“绝对 demand scale”。

## 9. 后续分支

```text
7.3.6A Frozen Target
   ↓
7.6C-1 comparator artifact 发现
   ↓
7.6C-2 Target Integrity Gate  ← 本步：TARGET_MARGINAL_COARSE_ONLY
   ├─ target uncertainty 可接受      → 7.6F-1（绝对 scale 可读）
   ├─ 仅粗档可读（本步）      → 7.6F-1（降级为粗档响应，网格重排）
   └─ target uncertainty 不可接受  → 新建 crosswalk 修复实验（7.3.6A-b）
```

**硬约束**：“发现校准靶场存在可修正伪影”≠“已允许修改冻结靶场”。后者必须另立版本、另留证据链。

## 10. 环境与产物

- 运行耗时：**16.7 s**；`zero_simulation = True`；`matsim_rerun = False`；`parameters_changed = False`
- 依赖：`compare_final_crosswalk_7_3_6b` / `diagnose_od_spatial_structure_7_6c` / `audit_anomaly_trace_7_6c_1`（均以 import 方式复用，未复制公式）
- 产物：`od_target_integrity_7_6c_2_summary.json`、`target_integrity_crossvalidation.csv`、`target_response_grid.csv`、`target_step_snr.csv`、`target_grid_placement.csv`、`target_uncertainty_localisation.csv`
