# PROTOCOL — E-SB-04：路径重分配与观测域流量增量审计（预注册）

> 创建：**2026-10-11** ｜ 上游：`E-SB-03 = A❌/B✅(路径重分配)/C❌/D❌`（`Sim/Obs` 1.0601 = 负荷向被观测快速路集中）
> 性质：**零仿真 · 只读**。不启动 MATSim；不改 `network`/`population`/`capacity`/`freespeed`/`SCALE`/`lambda`/阈值/任何冻结配置；不生成 v1.1。
> 主比较：**v1.0 vs SB-A5**；`SB-A5ind` 仅作独立 OD 稳健性参照。
> 目标：回答**一个问题** —— E-SB-03 观察到的观测域流量增量，**是否由实际路径重分配解释**；若否，现有数据能否把**时间窗效应**与**观测域映射效应**区分开。

---

## 0. 输入前提（阶段 1 必须先坐实）

| 臂 | 运行目录 | plans | network | events |
|---|---|---|---|---|
| v1.0 | `matsim_final_7_6h/outputs/W01_rc_min` | ✅ | ✅ | ⛔ 无（`writeEventsInterval=0`）→ 由 `matsim_viz_7_8/outputs/W01_events` 重跑提供 |
| SB-A5 | `experiments/E-SB-02_night_freeflow/outputs/SB-A5` | ✅ | ✅ | ⛔ **无**（`writeEventsInterval=0`） |
| SB-A5ind | `experiments/E-SB-02_night_freeflow/outputs/SB-A5ind` | ✅ | ✅ | ⛔ **无** |

- **v1.0 events 合法性**：`W01_events` 与 `W01_rc_min` 的 reduced-config **实质差异仅 `writeEventsInterval`（0→19）**（`outputDirectory`/`runId` 属外观）⇒ `W01_events` 即 v1.0 冻结模型开启事件输出的重跑，其 it.19 事件代表 v1.0 执行路线。
- **无可比迭代 events**：SB-A5/SB-A5ind 无 events，**不得**用 LinkStats 推断其「实际路线已改变」；按任务单 §2 **降级为 plans 路线结构诊断**，并在结论标注**证据等级**。
- **trips**：三臂均无 `output_trips.csv.gz` ⇒ 无 person↔trip 连接；OD 由 **selected plan 的首/末 link** 与 person 属性（`originZone`/`destinationZone`）推导。
- **道路等级源**：MATSim `output_network.xml` **不含 `highway`** ⇒ 等级/路名一律取自 `reports/matsim_network/network_links_source_copy.csv`（按 `e{from}_{to}` 连接）；**长度**取自 `output_network.xml` 的 `length`（权威、单位=米，⛔ 不用 `src_copy.length_m`，已知漂移）。

---

## 1. 阶段 1：输入存在性与可比性门禁

逐一核实（`input_manifest.json` 记录路径/大小/sha256）：

1. 两主臂的 `output_plans.xml.gz` / `output_network.xml.gz` 是否存在且可解析；
2. `output_events.xml.gz`（v1.0 侧）是否存在且可解析；
3. network 与 LinkID/highway 映射是否可得；
4. E-SB-03 的逐断面增量表与匹配边清单是否可得。

比较前逐项确认 **population/person ID、OD 起终点、agent 数、seed、迭代号、网络拓扑** 可比；**SB-A5 允许 `freespeed` 不同，其余差异必须逐项列明**。

判据：`G01–G10`（见 §7）。

---

## 2. 阶段 2：区分路线变化与时段变化

### A 实际路线变化（plans 级 + v1.0 events 侧保真）
- 取每人 **`selected="yes"`** 的 plan，重建**有向 link 序列**；逐 person 比较 v1.0 vs SB-A5：
  路线序列是否变化、**route hash 变化率**、`motorway/motorway_link/trunk/primary/secondary/tertiary/service` 的**路径长度占比**、快速路**进出次数**、道路等级**转换序列**、同 OD 下路径变化是否**集中于 PIE/TPE/CTE/KPE** 等 E-SB-03 已识别走廊。
- v1.0 侧另做 **plans↔events 保真抽样**（有界，收满即停）：由 events 重建执行 link 序列，与 selected plan 比对 ⇒ 证明 plans 可作执行路线代理。
- ⇒ 结论须标 **证据等级 = plans（计划路线）**；⛔ 不得等同于「实际执行路线」。

### B 路线不变、时段内流量变化
- 需 events 的 link-entry 时刻。**SB-A5 无 events ⇒ BLOCKED**；仅能引用 E-SB-03 的时间窗敏感性（07-08 +6.17% / 08-09 +6.08% 同向；09-10 及以后无实测）。
- 检查 cycle-mean LinkStats 与单次迭代事件是否存在不可比之处。
- ⛔ 不得把无 LTA 实测的 09:00 后变化当成已验证真实流量。

### C 观测断面映射与平行道路替代
- 对 E-SB-03 发现的同走廊内正负变化，区分：真正的有向路线变化 / 同一走廊内不同路段之间转移 / **对向或平行近重复 link** / **LTA section→MATSim 1:K 映射**的聚合效应。
- 对向 link 定义：`e{a}_{b}` ↔ `e{b}_{a}`；平行/近重复：同 `RoadName` 且共享节点。
- ⛔ 必须与已 `CLOSED` 的 **O3-R1「承载对象替代」分列**，不得把相邻 link 的流量转移直接认定为车辆路径重分配。

---

## 3. 阶段 3：验证 E-SB-03 的主要增量

固定 E-SB-03 的断面集合（576）／聚合（`median(匹配有向边 HRS8-9avg)`）／`SCALE=2.29897`，逐断面计算

$$\Delta Q_g = Q^{sim,SB\text{-}A5}_g - Q^{sim,v1.0}_g$$

报告：正/负/零断面数与流量贡献；Top-2/Top-10 走廊占净增比例；各等级**路径长度占比变化**与**路段流量变化**；路线变化指标与 ΔQ 的对应关系；同走廊内正负抵消与对向/平行 link 替代分布。**三层级并报**：全网 / 观测匹配边 / LTA 断面。

---

## 4. 预注册判决（五选一或并列）

| 判决 | 含义 |
|---|---|
| `PATH_REDISTRIBUTION_SUPPORTED` | 实际路线或道路等级路径占比存在明确变化，并与快速路流量增量空间对应 |
| `TEMPORAL_REALIZATION_SUPPORTED` | 路径结构基本不变，但 link-entry 时刻变化能解释观测窗内流量增量 |
| `OBSERVATION_MAPPING_EFFECT_SUPPORTED` | 增量主要来自断面—路网映射、平行道路或对向 link 的替代 |
| `MIXED_MECHANISM` | 两类或以上机制获得独立支持 |
| `INCONCLUSIVE` | 缺匹配事件输出、person/vehicle 关联不可靠，或证据不足以区分机制 |

所有判决须给出**支持与反例证据**。**若只能分析 plans，不得裁为已证实的实际路径重分配。**

---

## 5. 交付物（`reports/path_redistribution_audit_E_SB_04/`）

`input_manifest.json` · `gate_checks.csv` · `route_change_summary.csv` · `roadclass_route_share.csv` · `section_delta_decomposition.csv` · `corridor_delta_decomposition.csv` · `mechanism_scorecard.csv` · `VERDICT_E-SB-04.md`

（另附：`config_diff_vs_base.csv`、`network_freespeed_diff.csv`、`edge_level_delta.csv`、`three_level_summary.csv`、`corridor_linkage_route_vs_flow.csv`、`roadclass_route_vs_flow.csv`）

---

## 6. 决策红线

审计结束前，**不**调整 `SCALE`/容量/`freespeed`/`lambda`/其他校准参数；**不**启动信号灯/交叉口机制实验；**不**晋升 v1.1。

---

## 7. 门禁清单

| ID | 判据 |
|---|---|
| `G01` | 三臂 plans 与 network 均存在 |
| `G02` | v1.0 events 存在（重跑） |
| `G03` | SB-A5/SB-A5ind events 均缺失（⇒ 证据降级） |
| `G04` | events 重跑 = v1.0 冻结配置（仅差 `writeEventsInterval` 等外观项） |
| `G05.*` | `flowCapacityFactor`/`storageCapacityFactor`/`randomSeed`/`disableInnovation` 三臂一致 |
| `G06.*` | 每臂每 person 恰 1 个 `selected` plan |
| `G07.*` | 各臂与 v1.0 person 集合逐位相同 |
| `G08.*` | 各臂与 v1.0 网络 link id 集合相同 |
| `G09` | SB-A5 仅 `freespeed` 变化（拓扑 from/to/length/cap/lanes 零差异） |
| `G10` | network→highway 源表覆盖 ≥ 99% |
| `G11` | 时段分支对 SB-A5 判 `BLOCKED` |
| `G12` | v1.0 plans↔events 路线一致率 ≥ 99% |
| `H01–H05`（阶段3） | crosswalk 3193/576、ΔQ 闭合、对向边可检验、全网 vs 匹配边方向相反 |
