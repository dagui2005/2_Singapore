# Step 7.9B-0 — 交通动力学机制审计（零仿真 · 只读）

> 定性：**7.9 第一阶段结构审查**，v1.0 冻结后的只读诊断；⛔ 非 7.8 前置、不回灌 v1.0。
> 判决：**`TRAFFIC_DYNAMICS_MECHANISM_AUDIT_COMPLETE`**，门 **16/16 PASS**。
> 零仿真：`matsim_rerun=False`；冻结件 `changed=0`（201 件 mtime+size 快照）。

源：`tools/matsim-2026.0/matsim-2026.0-sources.jar`（逐条重新核对，非凭记忆）
## B1 — 当前真正生效的交通动力学

| 项 | 值 | 是否生效 |
|---|---|---|
| `controller.mobsim` | qsim | ✅ 决定一切 |
| `qsim.trafficDynamics` | queue | ✅ **真实运行** |
| `dsim.trafficDynamics` | kinematicWaves | ⛔ 惰性（mobsim=qsim） |
| `qsim.inflowCapacitySetting` | INFLOW_FROM_FDIAG (MATSim default, not set in cfg) | ✅ MATSim 默认值 |
| `qsim.flowCapacityFactor` | 1.0 | ✅ |
| `qsim.storageCapacityFactor` | 1.0 | ✅ |
| `qsim.timeStepSize` | 00:00:01 | ✅ |
| `qsim.stuckTime` | 10.0 | ✅（保留观察） |
| `qsim.removeStuckVehicles` | false | ✅ |

⇒ 真正运行的是 **qsim = `queue`**；`kinematicWaves` 只出现在惰性的 `dsim` 模块。判断与 7.9A-0 一致。

## B2 — 当前 `queue` 是否有 inflow 约束

**没有。** 源码 `QueueWithBuffer`（`initializeQSim` 内的 `switch(trafficDynamics)`）：

```java
this.maxInflowUsedInQsim = this.flowCapacityPerTimeStep;
switch (context.qsimConfig.getTrafficDynamics()) {
  case queue:
  case withHoles:
    break;                       // <-- 不改动 maxInflowUsedInQsim
  case kinematicWaves:
    ... final double maxFlowFromFdiag = (lanes/cellSize) / (1/v_hole + 1/v_free); ...
}
```
⇒ `queue` 下 `maxInflowUsedInQsim` 恒等于 `flowCapacityPerTimeStep`（= 路网容量 × `flowCapFactor`），
即**路网自带容量就是入口约束**，没有额外的基本图入口限制。
`kinematicWaves` 才会写入 `maxInflowUsedInQsim` 覆盖它。
与项目既有认识一致：**`queue` 只约束「储存容量耗尽后的进入」，不提供入口流量约束**。

## B3 — 换成 `kinematicWaves` 后，有多少道路会真正被新增入口约束卡住

基本图入口上限（源码 `L414`，`INFLOW_FROM_FDIAG` 生效分支）：

```
q_fdiag(link) = (permlanes / 7.5) / (1/(15/3.6) + 1/freespeed)   [veh/s]
判定： r_fdiag = q_fdiag / network_capacity ;  r_fdiag < 1  ⇒ 该 link 被新增约束卡住
```
> ⚠️ 关键：`maxFlowFromFdiag` **不乘 `flowCapFactor`**（源码 L407-412 明确写着「leave the inflow capacity (unscaled)」）。
> 而 `flowCapacityPerTimeStep` **乘** `flowCapFactor`。⇒ 两个约束的尺度不同，这一点决定了 A×B 的交互（见下）。

| 口径 | r<1 的 link 数 | link 占比 | 里程 (km) | 里程占比 |
|---|---|---|---|---|
| INFLOW_FROM_FDIAG（默认） | 21670 | 3.1244% | 869.589 | 5.7488% |
| MAX_CAP_FOR_ONE_LANE（旧行为） | 21670 | 3.1244% | 869.589 | 5.7488% |

> 注：`MAX_CAP_FOR_ONE_LANE` 与 `INFLOW_FROM_FDIAG` 的 **r<1 集合代数恒等**
> （`r_lane = fd_lane × lanes / cap ≡ fd_link / cap = r_link`）；两者差异只在被写入的**上限数值**。

**按自由流速度分级**：

| 自由流分级 | links | 本类 link 占比 | 本类里程 (km) | 中位单车道容量 | 中位 FD 天花板/车道 | r<1 links | 本类 r<1 占比 | 本类里程占比 | 中位 r |
|---|---|---|---|---|---|---|---|---|---|
| local <30 | 448972 | 64.7 | 2.405 | 400.0 | 1142.9 | 132 | 0.029% | 0.03 | 2.86 |
| collector 30-50 | 49555 | 7.1 | 23.831 | 700.0 | 1454.5 | 1005 | 2.028% | 2.14 | 2.08 |
| arterial 50-70 | 189968 | 27.4 | 492.408 | 700.0 | 1538.5 | 15526 | 8.173% | 10.26 | 2.20 |
| fast 70-90 | 2386 | 0.3 | 138.056 | 1900.0 | 1684.2 | 2386 | 100.000% | 100.00 | 0.89 |
| expressway >=90 | 2694 | 0.4 | 212.888 | 1900.0 | 1714.3 | 2621 | 97.290% | 97.98 | 0.90 |

> 解读：r<1 只发生在 **`network_capacity/lane > FD 天花板`** 的道路上。
> FD 天花板随速度上升（30 km/h≈1333 → 120 km/h≈1778 veh/h/lane），
> 因此**再次验证用户的判断：`kinematicWaves` 不会把全网简单变堵**——它只挑出「路网给定容量高于基本图」的那一部分。

## B4 — 这些被卡住的 link 是否集中在 merge / diverge

节点度定义：`merge` = link 的 **from-node** 入度 ≥2；`diverge` = link 的 **to-node** 出度 ≥2。

| 位置 | 全部 link 占比 | 被卡住 link 占比 | 富集倍数 |
|---|---|---|---|
| merge（节点汇入） | 71.6067% | 19.1970% | **0.268×** |
| diverge（节点分流） | 71.6770% | 19.3355% | **0.270×** |

⇒ 未见显著富集 ⇒ 新增入口约束并非集中于 junction


⇒ **预登记假设 B4 被证伪**：三个独立口径一致给出**负富集**——全样本 0.268×、同类别 0.18–0.65×、
严格 junction（in-degree≥3）**0.090×**；被卡 link 的 from-node 平均入度 1.207，低于全样本 1.882。
**机制含义**：`kinematicWaves` 的入口上限**不是**节点级瓶颈机制，而是对**高容量 / 高速度路段**的
**整体性 ~10–11% 入口削流**（expressway 中位 r = 0.90、fast 类 0.89）。
⚠️ 由此产生一个与您红线同构的风险：**KW 可能让地图「变堵」，却不提升结构性保真度**——
它是均匀削流，而非复现真实瓶颈。⇒ 7.9B-1 判据必须**同时**看 (i) 拥堵是否形成、(ii) 拥堵
**位置**是否落在 7.7E 已识别的 CTE / `service` 短段上，而不是均匀铺开。

**同类别对照**（在同一自由流分级内部比较，排除「车型构成」混淆）：
| 自由流分级 | 本类 links | 其中 r<1 | 本类 merge 占比 | r<1 merge 占比 | 同类别富集 |
|---|---|---|---|---|---|
| local <30 | 448972 | 132 | 0.793 | 0.515 | 0.650 |
| collector 30-50 | 49555 | 1005 | 0.734 | 0.130 | 0.178 |
| arterial 50-70 | 189968 | 15526 | 0.542 | 0.176 | 0.324 |
| fast 70-90 | 2386 | 2386 | 0.368 | 0.368 | 1.000 |
| expressway >=90 | 2694 | 2621 | 0.135 | 0.135 | 1.000 |

被移除的入口容量合计 = **8784415 veh/h**（Σ(路网容量 − FD 天花板)，仅统计 r<1 的 link）。
**稳健性检查**（排除「阈值人为造成」）：from-node 平均入度 全部=1.882 vs 被卡=1.207；以 in-degree≥3 为严格 junction 判据的富集仅 **0.090×**。⇒ 换阈值不改变结论。
## B5 — 碎片化网络里瓶颈的有效空间尺度

| 指标 | 值 |
|---|---|
| link 长度中位数 | 11.0 m |
| link 长度 p90 | 52.0 m |
| < 20 m 的 link 里程占比 | 24.34% |
| corridor（度-2 链）条数 | 514557 |
| corridor 长度中位数 | 12.5 m |
| corridor 内 link 数中位数 | 1.0 |
| 连续被卡链条数 | 36 |
| 最长连续被卡链 | 857.6863 km |
| `queue` 下储存被自动放大的 link | 0（0.0000%） |
| `kinematicWaves` 下储存被放大的 link | 20922（3.0165%） |

⇒ 结论指向：**单 link 级指标在该路网上不可解释**；瓶颈应按 corridor/junction chain 聚合。
这正是 7.9C 的问题域。

**按节点间距看碎片化**：
节点间距均值 = **35.9 m**（27.9 nodes/km）；度-3 以上节点 **242388** 个（**16.0 个/km**）；度-2 直通节点占 **42.5%**。
⇒ **不存在长「度-2 链」可供聚合**（中位 corridor = 1.0 条 link）：分片发生在**节点级**（junction 每 ~62 m 一个），因此 7.9C 应做**junction cluster 聚合**，而不是 corridor 聚合。

## A × B 交互（重要的非可加性）

- `flowCapacityFactor` 同时缩放 `flowCapacityPerTimeStep` **与** `storageCapacity`（源码 L386 / L487）；
- 但 `maxFlowFromFdiag` **不缩放**（源码 L407-412）。

| 配置 | r<1 的 link 数 |
|---|---|
| `f_cap = 1.0`（v1.0） | 21670 |
| `f_cap = 1/SCALE ≈ 0.435`（A-1） | 0 |

⇒ 降低 `f_cap` 会把路网容量压到 0.435×，使 FD 天花板（不变）相对**更宽松**，
**被卡的 link 反而减少**。因此在 0.435 容量下测 `kinematicWaves`，B 效应会被 A 掩盖。
**这从机制上支持「先 B1（`f_cap=1.0` + `queue→kinematicWaves`）、再 B2（叠加 0.435）」的串行设计。**

**但注意（重要）**：KW 的**储存 / 空洞**机制是 `f_cap`-**不变**的——`minStorCapForHoles` 与几何储存
都随 `f_cap` 同比缩放，判据是**比值**。⇒ 在 0.435 下，KW 与 `queue` 的差别**只剩储存侧**，
影响约 **3.02%** 的 link（20,922 条）。**入口削流侧在 0.435 下完全消失。**

## 源码证据（逐条重新核对）

| probe | file | line | code |
|---|---|---|---|
| hole_speed | QueueWithBuffer.java | 175 | `final static double HOLE_SPEED_KM_H = 15.0;` |
| fd_formula | QueueWithBuffer.java | 414 | `final double maxFlowFromFdiag = (this.effectiveNumberOfLanes/context.effectiveCellSize)` |
| fd_setting | QueueWithBuffer.java | 447 | `if (inflowCapacitySetting == QSimConfigGroup.InflowCapacitySetting.INFLOW_FROM_FDIAG) {` |
| fd_assign | QueueWithBuffer.java | 460 | `this.maxInflowUsedInQsim = maxFlowFromFdiag;` |
| queue_noop | QueueWithBuffer.java | 394 | `case queue:` |
| init_inflow | QueueWithBuffer.java | 391 | `this.maxInflowUsedInQsim = this.flowCapacityPerTimeStep;` |
| storage_basic | QueueWithBuffer.java | 487 | `storageCapacity = this.length * this.effectiveNumberOfLanesUsedInQsim / context.effectiveCellSize * context.qsimConfig.getStorageCapFactor();` |
| storage_enlarge | QueueWithBuffer.java | 509 | `double tempStorageCapacity = freespeedTravelTime * unscaledFlowCapacity_s * context.qsimConfig.getFlowCapFactor();` |
| kw_storage_min | QueueWithBuffer.java | 547 | `final double minStorCapForHoles = length * flowCapacityPerTimeStep * (freeSpeed + holeSpeed) / freeSpeed / holeSpeed;` |
| kw_unscaled_nt | QueueWithBuffer.java | 411 | `* here (car mode shares go significantly down!). This has to be investigated further! For now, we leave the inflow capacity (unscaled)` |
| default_inflow_setting | QSimConfigGroup.java | 73 | `private InflowCapacitySetting inflowCapacitySetting = InflowCapacitySetting.INFLOW_FROM_FDIAG;` |
| default_trafficdyn | QSimConfigGroup.java | 143 | `private TrafficDynamics trafficDynamics = TrafficDynamics.queue;` |
| default_stuck | QSimConfigGroup.java | 95 | `private double stuckTime = 10;` |
| default_removestuck | QSimConfigGroup.java | 96 | `private boolean removeStuckVehicles = false;` |
| default_cellsize | NetworkImpl.java | 59 | `private static final double DEFAULT_EFFECTIVE_CELL_SIZE = 7.5;` |

## 7.9B-1 预登记（尚待批准）

**B1 首选配置**：`f_cap=1.0`、`storage_cap=1.0`，**仅** `qsim.trafficDynamics: queue → kinematicWaves`；
其余全部继承 v1.0（含 route-choice 锁、`stuckTime=10`、`removeStuckVehicles=false`）。
**观测口径**：`Sim/Obs` 仅作崩解护栏（≥0.85），⛔ 不再作目标；主看**拥堵状态**指标：
`v/c` 分布、饱和里程、`aggV/C` 峰值、真实超额 `TT/FF − ceil(FF)/FF`、队列回溢链长度。
**预登记预测**：被卡住 link 约 **21670**（里程占比 **5.7488%**）；若 B4 富集成立，预计拥堵状态改善**首先出现在 merge 型 junction**，而非全网。
⛔ **B4 已证伪**：预测「改善首先出现在 merge 型 junction」**不成立**。据 B4 修正为：若 KW 生效，
新增拥堵应**均匀出现在高速 / 高容量路段**（expressway + fast + 多车道 arterial），而非集中于 junction。

**决断规则**：若 B1 相对 v1.0 在拥堵状态指标上无实质变化（且 `Sim/Obs` 未崩塌），
则判定 **`TIMEDYNAMICS_NOT_PRIMARY`**，转入 7.9C（瓶颈/回溢结构）。

## 门

| id | 判据 | 结果 | 细节 |
|---|---|---|---|
| B0.S | source evidence re-verified in matsim-2026.0-sources.jar | PASS | 15 probes, 15 found |
| B0.01 | effective mobsim is qsim | PASS | controller.mobsim=['qsim'] |
| B0.02 | effective trafficDynamics is queue | PASS | qsim.trafficDynamics=['queue'] |
| B0.03 | dsim.trafficDynamics is present but inert | PASS | dsim=kinematicWaves while mobsim=qsim |
| B0.04 | inflowCapacitySetting not overridden -> MATSim default | PASS | default = INFLOW_FROM_FDIAG |
| B0.05 | queue branch performs no inflow modification | PASS | QueueWithBuffer L393-396 (case queue -> break) + L391 (init to flowCapacityPerTimeStep) |
| B0.06 | r_fdiag computed for every link | PASS | n=693575 |
| B0.07 | kinematicWaves binding set quantified (links & km) | PASS | links=21670 km=869.589 |
| B0.08 | merge/diverge enrichment computed | PASS | enr_merge=0.268 enr_diverge=0.270 |
| B0.12 | B4 robustness: graded + stricter-junction variants | PASS | enr_merge3=0.090 mean_indeg_all=1.882 mean_indeg_bind=1.207 |
| B0.11 | class-matched control computed + removed inflow quantified | PASS | removed_inflow=8784415 veh/h |
| B0.09 | fragmentation metrics computed | PASS | corridors=514557 |
| B0.10 | A x B non-additivity quantified | PASS | r<1 collapses from 21670 to 0 when f_cap falls to 1/SCALE |
| B0.20 | zero simulation: MATSim not re-run | PASS | matsim_rerun=False |
| B0.21 | frozen artifacts untouched (mtime+size) | PASS | files=201 changed=0 |
| B0.22 | config unmodified | PASS | f_cap=[('hermes', '1.0'), ('qsim', '1.0')] |
