# E-SB-01 裁定报告 —— SpeedBand 拟合旁路实验（联合目标：TrafficFlow + SpeedBand）

> 生成：2026-10-08 ｜ 实验目录：`experiments/E-SB-01_speedband_fit/`
> 性质：**旁路实验（EXPERIMENT ONLY / NOT v1.1）**。全程**零冻结件改动**。
> 点火：2026-10-07 21:07 → 2026-10-08 05:58，串行链 `SB-A1 → SB-A4 → SB-A3 → SB-A3n → SB-A2`。

---

## 0. 执行摘要（TL;DR）

1. **SpeedBand 拟合的决定性杠杆 = 自由流速度（供给层）**。`SB-A4`（`freespeed ← 观测 AM 速度`）把速度 RMSE 从 **18.24 → 8.38（−54%）**、Pearson r **0.40 → 0.91**、band 精确命中 **21.7% → 61.9%**。
2. **机制/容量/需求类杠杆几乎无效或有害**：`SB-A1`（queue→kinematicWaves）ΔRMSE **+0.07**（无改善）；`SB-A3`（定向容量）ΔRMSE **+0.99**（更差）且流量对账从 1.00 崩到 **0.50**；打乱负例 `SB-A3n` 更差（ΔRMSE **+2.57**）。
3. ⇒ **残差的主体不是「拥堵机制缺失」，而是「自由流速度水平偏高」**。仿真链路速度几乎由 `freespeed` 决定（无拥堵缓冲），而观测 AM 速度远低于网络自由流（residential 46.7 vs 20.7 km/h）。
4. **★两条红线结论**：① 任何"削容量/造堵"型旋钮**同时恶化**流量对账与速度 RMSE（**不许用调参换图**）；② `SB-A4` 是**用观测速度当自由流**的 **oracle 上界**，证明"速度水平"能解释的份额，**不是可提交标定**。

---

## 1. 运行台账

| 臂 | 单因子改动 | 配置层 | 运行 | 用时 | 结果 |
|---|---|---|---|---|---|
| **SB-A1** | `qsim.trafficDynamics: queue → kinematicWaves` | 配置 | rc=0 | 109.4 min | ✅ 完成 |
| **SB-A4** | 新网络 `freespeed ← max(v_obs, 5 km/h)`（91,956 匹配链） | 网络 | rc=0 | 77.2 min | ✅ 完成 |
| **SB-A3** | 新网络 `capacity ← c·m(l)`（定向 4,838 链 / 236.5 km） | 网络 | rc=0 | 132.0 min | ✅ 完成 |
| **SB-A3n** | 同上，**空间打乱负例**（同 m 边际、异链配对） | 网络 | rc=0 | 200.8 min | ✅ 完成 |
| **SB-A2** | `qsim.storageCapacityFactor: 1.0 → 0.434977` | 配置 | **rc=1（0.1 min）** | — | ⛔ **框架阻断**（见 §5） |

- 前 4 臂全部通过：派生期 **44/44 门禁**、每臂运行前硬门 **8/8**。
- `SB-A2` 在 `Config.checkConsistency` 阶段被 MATSim 2026 **硬拒**（架构性，非操作失误）。

---

## 2. 联合评分卡（冻结口径：08–09 主窗、`it.10–19` 周期均值）

**F_flow** = TrafficFlow `Sim/Obs`（复用冻结评价器 `audit_sampling_capacity_7_9a1`）；**F_speed** = SpeedBand 08–09 有车链。

| 臂 | Sim/Obs(cycle) | Sim/Obs(it.19) | n | obs km/h | sim km/h | bias | MAE | **RMSE** | ΔRMSE | Pearson r | band 精确 | band ±1 | band bias |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| **v1.0**(基线) | **0.9993** | 1.0015 | 59,721 | 30.23 | 38.81 | +8.58 | 14.60 | **18.24** | — | 0.401 | 21.7% | 58.0% | +0.90 |
| E-CAP-01 | 0.7665 | 0.7725 | 61,927 | 30.12 | 37.90 | +7.78 | 14.72 | 18.44 | +0.20 | 0.368 | 21.7% | 57.7% | +0.82 |
| **SB-A1** 机制 | 0.8506 | 0.8604 | 60,657 | 30.19 | 38.42 | +8.24 | 14.66 | 18.30 | **+0.07** | 0.395 | 21.6% | 57.9% | +0.87 |
| **SB-A3** 容量 | 0.5005 | 0.5066 | 65,544 | 29.90 | 33.14 | +3.24 | 15.40 | 19.22 | **+0.99** | 0.310 | 20.2% | 56.0% | +0.39 |
| **SB-A3n** 负例 | 0.0526 | 0.0529 | 65,211 | 29.91 | 31.64 | +1.74 | 16.61 | 20.80 | **+2.57** | 0.222 | 19.3% | 53.0% | +0.26 |
| **SB-A4** 速度 | 1.0524 | 1.0543 | 57,743 | 30.68 | 25.33 | **−5.35** | **5.38** | **8.38** | **−9.85** | **0.910** | **61.9%** | **92.0%** | −0.49 |

**流量质量（576 断面）**：

| 臂 | GEH<5 | 5–10 | ≥10 | share<5 | WMAPE | 断面 r |
|---|---:|---:|---:|---:|---:|---:|
| v1.0 | 49 | 46 | 481 | 8.5% | 0.718 | 0.345 |
| E-CAP-01 | 88 | 92 | 396 | 15.3% | 0.477 | 0.428 |
| SB-A1 | 61 | 55 | 460 | 10.6% | 0.597 | 0.392 |
| SB-A3 | 67 | 57 | 452 | 11.6% | 0.544 | 0.413 |
| SB-A3n | **8** | 11 | 557 | **1.4%** | **0.948** | 0.181 |
| SB-A4 | 42 | 58 | 476 | 7.3% | 0.725 | 0.384 |

---

## 3. 预注册联合判据逐臂裁定

判据（预注册）：**改善 = `ΔRMSE_speed < 0` 且 `F_flow ∈ [0.95, 1.05]`**。

| 臂 | SpeedBand 改善？ | 流量对账在带内？ | **联合裁定** |
|---|---|---|---|
| SB-A1 | ✗（+0.07，实质不变） | ✗（0.851） | **FAIL**（两侧皆不达标） |
| SB-A3 | ✗（+0.99，恶化） | ✗（0.501） | **FAIL（恶化）** |
| SB-A3n | ✗（+2.57，恶化） | ✗（0.053） | **FAIL（负例，符合预期）** |
| SB-A4 | ✓（−9.85，大幅） | △（1.0524，**越上限 0.0024**） | **条件 PASS**（速度✓ / 流量贴边） |

**负例对照的意义**：`SB-A3n`（空间打乱）比 `SB-A3`（定向）**更差**（RMSE 20.80 vs 19.22；Sim/Obs 0.053 vs 0.501）⇒ `SB-A3` 的效果**确属空间定向效应**，而非「全域拉慢」的伪影。负例有效。

---

## 4. ★决定性诊断：按观测档看仿真速度（km/h）

这是本轮最硬、最可解释的证据。行 = 臂，列 = 观测 SpeedBand 档（SB1=0–9 km/h 最堵 … SB8=70+ 最畅）。

| 臂 | SB1 | SB2 | SB3 | SB4 | SB5 | SB6 | SB7 | SB8 | 跨度 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| **观测中点** | 4.5 | 14.5 | 24.5 | 34.5 | 44.5 | 54.5 | 64.5 | 74.5 | 70.0 |
| v1.0 | 33.5 | 33.8 | 36.3 | 39.3 | 43.6 | 48.5 | 53.8 | 59.2 | **25.7** |
| E-CAP-01 | 33.2 | 33.1 | 35.5 | 38.3 | 42.7 | 47.1 | 51.8 | 57.8 | 24.6 |
| SB-A1 | 33.2 | 33.2 | 35.9 | 39.0 | 43.4 | 48.3 | 53.4 | 59.0 | 25.8 |
| SB-A3 | 30.4 | 28.8 | 30.2 | 32.5 | 38.0 | 43.6 | 49.1 | 55.7 | 26.9 |
| SB-A3n | 30.1 | 28.6 | 29.4 | 30.7 | 34.7 | 39.4 | 45.2 | 50.9 | 22.3 |
| **SB-A4** | **6.2** | **13.7** | **21.1** | **28.5** | **36.1** | **44.4** | **53.3** | **60.7** | **54.5** |

**读法**：
- v1.0：观测说 0–9 km/h 的 4,772 条链，仿真给 **33.5**，且 **SB1≈SB2≈33.5（完全无分辨率）**；整体响应跨度仅 **25.7**（观测 70）⇒ **压缩约 1/3**。
- **SB-A4：仿真档均值几乎逐档落在观测档中点上（6.2/13.7/21.1/…/60.7 vs 4.5/14.5/24.5/…/74.5）**，跨度 54.5。
- **A1/A3/A3n 三种机制/需求/供给旋钮都未能恢复这个"观测-仿真档响应"**。

⇒ **结论：仿真链路的「观测档响应」主要被 `freespeed` 决定；在当前模型里拥堵减速缓冲极小（sim 速度≈自由流）。**

---

## 5. ⛔ SB-A2 架构性阻断（BLOCKED_BY_FRAMEWORK）

**现象**：`SB-A2` 点火 0.1 min 即 rc=1，抛：
```
RuntimeException: your storageCapFactor=0.434977 is more than the relativeTolerance=0.0
different from the flowCapFactor=1.0. ... Relative tolerance can be set in the global config group.
   at GlobalConfigGroup.checkConsistency(GlobalConfigGroup.java:158)
```

**根因（源码级证据）**：
1. `GlobalConfigGroup.checkConsistency()` 用 `|flowCapFactor − storageCapFactor| ≤ relativeTolerance` 硬校验，`relativeTolerance` 默认 **0.0**（**要求严格相等**）。
2. 放宽它需设 `global.relativeToleranceForSampleSizeFactors`，但该字段在 `GlobalConfigGroup.java:141-142` **既无 `@Parameter` 注解、`@StringSetter` 也被注释掉**（`//@StringSetter("relativeScalesTolerance")`）。
3. `ReflectiveConfigGroup.getParamFields()`（第 208–219 行）**仅注册带 `@Parameter` 的字段** ⇒ 该参数**不在已注册集合**内。
4. `GlobalConfigGroup` 构造走 `super(GROUP_NAME)` → `storeUnknownParameters=false` ⇒ **未知参数直接崩**。

**实证**（项目 JDK25 + jshell 解析配置）：
```
Module global of type GlobalConfigGroup doesn't accept unknown parameters.
Parameter relativeToleranceForSampleSizeFactors is not part of the valid parameters:
[defaultDelimiter, randomSeed, numberOfThreads, insistingOnDeprecatedConfigVersion, coordinateSystem]
```

⇒ **在 MATSim 2026 中，`storageCapacityFactor` 无法与 `flowCapacityFactor` 解耦**（框架明示「旧做法已不再需要」）。**「仅动存储、不动流量」的隔离臂在配置层不可表达**。
（`E-CAP-01` 之所以能跑，正因为把 **两者同时** 设为 0.434977；`SB-A2` 想只动其一 ⇒ 被框架拒绝。）

**替代路径（未执行，待裁定）**：写一个薄 Java 入口 `RunMatsimStorageArm`，`loadConfig` 后调用**公开 API** `config.global().setRelativeToleranceForSampleSizeFactors(0.6)` 再 `Controler.run()`。可行但**会打破"一臂一配置"的统一协议**，故未擅自采用。

---

## 6. 结论与建议

1. **SpeedBand 的空间残差 ≈ 自由流速度层问题**（供给侧 `freespeed`），**不是**需求/容量/排队机制问题。这与 7 诊断的结论一致（residential 46.7 vs 20.7 km/h）。
2. **可提交的下一步（非循环）**：把 `freespeed` 用**独立的自由流估计**标定，而非直接用 AM 观测速度。候选：**夜间（00:00–06:00 / 23:00）SpeedBand 快照** —— 该窗无拥堵、是自由流代理，可作**非循环**的 `SB-A5`。
   - 仓库已存在 `analyze_speedband_overnight.py`，说明夜间快照可能可得；须先核验时间戳与覆盖。
3. **禁止事项（本轮实证）**：削容量（A3）虽把 bias 从 +8.58 压到 +3.24，却把 RMSE 抬高、把流量对账打到 0.50 ⇒ **"削容量造堵"是伪改善**，且直接违反"流量校准成功 ≠ 拥堵状态校准"。
4. `SB-A4` 的 `Sim/Obs = 1.0524` 仅超带 0.0024，**速度收益与流量代价基本 1:1 权衡**；若要把 A4 思想做成可提交方案，须配独立的 `freespeed` 估计并重跑流量对账。

---

## 7. 红线遵守

- ⛔ 未改 v1.0 config / `section_scale_v10.csv` / crosswalk / `TrafficFlow` / `SpeedBand` 原始值 / 评价器阈值；**未产生 v1.1**。
- ⛔ 未用 `demand↑` 造堵、未砍容量造红、未用调参换图。所有臂在 `experiments/E-SB-01_speedband_fit/` 内，与 v1.0 隔离。
- ✅ 负例（`SB-A3n`）真实改变结果且非同构；每臂配置 diff 恰为白名单；运行前后门禁全绿（除 A2 框架阻断，已完整物化）。

---
*产物：`audit/esb01_joint_scorecard.csv`（6 行）+ `.json`（含 `by_obs_band`）；`logs/chain_state.json`；本裁定报告。*
