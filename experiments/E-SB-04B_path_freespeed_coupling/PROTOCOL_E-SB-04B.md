# PROTOCOL_E-SB-04B —— 自由流速度变更与路径重分配的空间耦合审计

> 预注册（**先于任何计算落盘**）｜ 日期：**2026-10-11**
> 性质：**零仿真 · 只读**。⛔ 不启动 MATSim；⛔ 不改 network / population / capacity /
> `freespeed` / `SCALE` / lambda / 阈值 / 任何冻结配置；⛔ 不生成 v1.1。
> 上游：`E-SB-04 = PATH_REDISTRIBUTION_SUPPORTED（证据等级 = plans，路线变化 66.06%）`
> 主比较：**v1.0 vs SB-A5**（同 population、仅 `freespeed` 差）；`SB-A5ind` 仅作参照。

---

## §0 问题与证据边界

**唯一要回答的问题**

> 究竟是**哪些 `freespeed` 变更**，与**哪些路线变化**、**哪些断面流量增量**在空间上对应起来？
> 这种对应是否只是「快速路本身流量大」造成的伪关联？

**必须保留的证据边界（⛔ 全程不得越界）**

- E-SB-04 的 **66.06% 是计划路线变化率**，**不是** SB-A5 的实际执行路径变化率。
- v1.0 的 plans↔events 保真率 100.000%（n=8,000）只增强**计划路线的可信度**；
  **SB-A5 无 events** ⇒ 其执行路线**未被直接观测**。
- 本研究结论的证据等级一律标 **`PLANS_LEVEL`**；⛔ 不得写作「已证实的执行级路径重分配」。

**与已关闭工作的分列（⛔ 不合并）**

| 项 | 主题 | 状态 |
|---|---|---|
| `O3-R1` | 观测对象（link）替代 / 承载对象替代 | ✅ CLOSED |
| `E-SB-03` | 断面增量的时间窗/路径/聚合归因 | ✅ 已完成（B = 路径重分配为主因） |
| `E-SB-04` | 计划路线变化率与走廊同序 | ✅ 已完成（`PATH_REDISTRIBUTION_SUPPORTED`，plans） |
| `E-SB-04B`（本） | `freespeed` 变更 ↔ 路线变化 ↔ 断面增量的**空间耦合** | 进行中 |

---

## §1 输入前提（只读，冻结）

| 项 | 路径 | 说明 |
|---|---|---|
| v1.0 network | `matsim_final_7_6h/outputs/W01_rc_min/W01_rc_min.output_network.xml.gz` | 长度/自由流速度权威源（单位 = **m / m·s⁻¹**） |
| SB-A5 network | `experiments/E-SB-02_night_freeflow/outputs/SB-A5/SB-A5.output_network.xml.gz` | 同上 |
| v1.0 plans | `…/W01_rc_min.output_plans.xml.gz` | selected plan 路线 |
| SB-A5 plans | `…/SB-A5.output_plans.xml.gz` | 同 population |
| 路线缓存 | `experiments/E-SB-04_path_redistribution_audit/_cache/routes_{arm}.pkl` | E-SB-04 已解析（person + links），**只读复用** |
| 等级/路名源 | `reports/matsim_network/network_links_source_copy.csv` | `highway` / `name`（E-SB-04 同源） |
| crosswalk | `reports/od_final_calibration_crosswalk_7_3_6/final_calibration_crosswalk.csv` | 3,193 匹配边 / 576 断面 |
| 逐边 ΔQ | `reports/path_redistribution_audit_E_SB_04/edge_level_delta.csv` | E-SB-04 阶段3，冻结口径 |
| 逐断面 ΔQ | `experiments/E-SB-03_flow_shift_audit/audit/esb03_section_delta.csv` | 576 行 |
| 走廊路线使用率 | `reports/path_redistribution_audit_E_SB_04/corridor_route_use.csv` | E-SB-04 阶段2 |

**单位声明（★防漂移）**：MATSim `output_network.xml` 的 `freespeed` 单位为 **m/s**；
报告渲染时**同时给出 m/s 与换算 km/h**（×3.6），⛔ 不得混用。

---

## §2 阶段 1：门禁（输入存在性 / 可比性 / 变更链非空）

| 门禁 | 判据 |
|---|---|
| `G01` | 三臂 network 与 plans 均存在 |
| `G02` | v1.0 与 SB-A5 网络 link id 集合**逐位相同**（693,575） |
| `G03` | SB-A5 相对 v1.0：**拓扑（from/to/length/capacity/permlanes）零差异** |
| `G04` | v1.0 与 SB-A5 使用**同一 `inputPlansFile`**（需求可比 ⇒ 可干净归因） |
| `G05` | 路线缓存可用：每臂 person 集合 = **236,044**，且与 E-SB-04 一致 |
| `G06` | crosswalk = 3,193 边 / 576 断面；`edge_level_delta.csv` = 3,193 行 |
| `G07` | 走廊正则（10 条快速路）在匹配边上**命中非零**（PIE、TPE 必须 > 0） |
| `G08` | `freespeed` 变更链数 **> 0**，且**升/降两侧均非空** |
| `G09` | 每条匹配边均可取到 `freespeed`（无缺失），覆盖率 = 100% |

---

## §3 阶段 2：检查 1 —— 自由流速度变更的空间特征

**做法**：逐链 `Δfree = fs_SB-A5 − fs_v1.0`；按 `highway`、走廊、Δ 幅度分桶聚合。

**输出**：`freespeed_change_summary.csv`、`freespeed_change_by_corridor.csv`、`freespeed_change_distribution.csv`

**预注册判据 A**

- `A1` 变更链总数在 **(0, N_link)** 区间内；变更**净降速**（`Σ length·Δfree < 0`）。
- `A2` **相对速度判据**：路面干道（`primary/trunk/secondary`）的**里程加权 Δfree** <
  快速路（`motorway/motorway_link`）的里程加权 Δfree。即「**快速路相对变快**」。
- `A3` 变更**覆盖长度**（受影响的里程）≥ 全网里程的 1%（排除「几链噪声」）。

---

## §4 阶段 3：检查 2 —— 路线变化 ↔ 速度变更（逐人）

**定义（逐 person，两臂同一 population）**

- `fs_mean`：路线**里程加权**平均自由流速度，`Σ len·fs / Σ len`。
- 四元组：`fs_net_route` = 网络 × 路线：
  `fsV10_onR10`、`fsA5_onR10`、`fsV10_onR5`、`fsA5_onR5`
  （`R10` = v1.0 计划路线，`R5` = SB-A5 计划路线）。
- **分解**（★核心）：
  `Δfs = fsA5_onR5 − fsV10_onR10`
       = `[fsA5_onR5 − fsA5_onR10]`（**route-effect**：路线改变引起的速度变化）
       + `[fsA5_onR10 − fsV10_onR10]`（**network-effect**：网络改速引起的速度变化）
- 暴露度：`slow_len = Σ len·1[Δfree<0]`、`fast_len = Σ len·1[Δfree>0]`、`chg_len = slow+fast`。

**输出**：`route_freespeed_coupling.csv`（分组）、`route_delta_exposure.csv`（逐人，精简列）

**预注册判据 B**

- `B1` **placebo**：路线**未变化**者，`Δfs` == 0（数值容差 1e-9）。
- `B2` 路线**变化**者，`Δfs > 0`（改后路线**更快**）。
- `B3` 变化者的 `Δfs` **显著大于**未变化者（0）。
- `B4` 变化者在 **v1.0 路线**上对「被降速链」的里程暴露占比 **高于**未变化者
  （⇒ 路线变化确实由「速度变更的空间位置」驱动，而非随机）。
- `B5` 分解：**route-effect** 与 **network-effect** 同号且 `|route-effect| > 0`
  （⇒ 存在真实的路线重选，而非仅网络改速）。

---

## §5 阶段 4：检查 3 —— 观测域断面增量 ↔ 速度变更（逐边）

**做法**：把 `edge_level_delta.csv`（3,193 匹配边、`dQ_edge_raw`）与逐链 `Δfree` 合并，
按 `Δfree` 是否变更分组，统计 `ΣΔQ`、pos/neg、net/gross、单位边净增；并在走廊级与
E-SB-04 的 route-use Δ 并联。

**输出**：`section_delta_coupling.csv`、`corridor_coupling_decomposition.csv`

**预注册判据 C**

- `C1` **本地速度效应不足以解释**：`freespeed`-**未变更**匹配边承担的**净增占比 > 50%**。
- `C2` `freespeed`-变更边的**单位边净增**（net/link）与未变更边**同一量级**（比值 ∈ [0.25, 4]），
  ⇒ 不构成「本地提速 ⇒ 局部流量暴增」的模式。
- `C3` 走廊级同序：走廊 route-use Δ 与 ΔQ 净额 Spearman **> 0**（沿用 E-SB-04，本次复算）。

---

## §6 阶段 5：检查 4 —— 负例对照（★防「快速路本身流量大」伪关联）

- `N1` **路线级 placebo**：未变化路线的 `Δ暴露度 = 0`（构造性）。
- `N2` **空间 shuffle 置换检验**：把逐链 `Δfree` 的**多重集随机置换**到链上（保持分布、破坏空间位置），
  重算「路线↔速度耦合」统计量（`mean Δfs among changed routes` 与 `B4 暴露差`），
  重复 **≥ 200 次**，报告实测值的**经验百分位**与 z 值。判据 `D1`：实测值 **≥ 95 百分位**。
- `N3` **base-rate 同等级对照**：仅在 **motorway + motorway_link** 内，
  比较 `Δfree≠0` 边与 `Δfree=0` 边的 **ΔQ 率**（净增 / v1.0 流量）；
  判据 `D2`：两者差异**不足以**解释总增量（即未变更边仍贡献主要净增）。

---

## §7 预注册判决（五选一）

| 判决 | 触发条件 |
|---|---|
| `FREESPEED_ROUTE_COUPLING_SUPPORTED` | A 全过 ∧ B1–B5 全过 ∧ C1 ∧ D1 ⇒ **空间耦合成立** |
| `COUPLING_PARTIAL_SECTION_LINKAGE_UNCLEAR` | A+B 过，但 C1 不过（ΔQ 主要落在 fs-变更边）⇒ **局部速度效应混入** |
| `COUPLING_ABSENT` | B 不过（路线变化与速度变更不对应）⇒ **停止「改道」解释，转向映射/聚合** |
| `CONFOUNDED_BY_CORRIDOR_SIZE` | D1 不过（实测值落在置换分布内）⇒ **关联可由走廊规模解释** |
| `INCONCLUSIVE` | 输入不足 / 关键门禁 FAIL |

**判决后的动作（预注册）**

- 若 `FREESPEED_ROUTE_COUPLING_SUPPORTED` ⇒ **建议**对 SB-A5 以 `writeEventsInterval=19`
  重跑一轮（**需用户裁定**；本轮 ⛔ 不启动），并比较新旧 LinkStats 是否被事件记录改变。
- 若 `COUPLING_ABSENT` / `PARTIAL` ⇒ **先查路线映射与断面聚合**，⛔ 不急重跑、
  ⛔ 不转向容量/信号灯参数。

---

## §8 交付物（→ `reports/path_redistribution_audit_E_SB_04B/`）

`input_manifest.json`、`gate_checks.csv`、`freespeed_change_summary.csv`、
`freespeed_change_by_corridor.csv`、`freespeed_change_distribution.csv`、
`route_freespeed_coupling.csv`、`route_delta_exposure.csv`、
`section_delta_coupling.csv`、`corridor_coupling_decomposition.csv`、
`negative_control_shuffle.csv`、`coupling_scorecard.csv`、`esb04b_summary.json`、
`VERDICT_E-SB-04B.md`。

---

## §9 决策红线

审计结束前：⛔ 不调 `SCALE`、容量、`freespeed`、lambda 或任何校准参数；
⛔ 不启动容量/信号灯/交叉口机制实验；⛔ 不晋升 v1.1；⛔ 不启动 MATSim（本轮）。

## §10 渲染纪律（沿用项目教训）

- 判据行**由实测自动渲染**，⛔ 不硬编码符号；凡「判据 + 实测」同行**必动态渲染**。
- 分组叙述**须整组求和后再写**（避免把净减误读为净增）。
- **覆盖率必同报**（匹配边仅占全网高峰 ~6.6% ⇒ ⛔ 不得外推）。
- 退化诊断必披露；冻结判据命中 100% 即视为判据缺陷，须复核。

---

## §11 修订记录（★先于二次执行登记；保留实录 + 显式撤回）

**修订 1（2026-10-11，首跑后）—— 撤回判据 `B1` / `B2` / `B5`，改用 `B1c` / `B2c` / `B5c`。**

- **触发原因是先验的逻辑矛盾，而非结果好坏**：
  1. §4 定义的 `Δfs = fsA5_onR5 − fsV10_onR10` **同时包含**路线改变与网络改速两种效应，
     即 `Δfs = route-effect + network-effect`。
  2. `B1` 要求「未变化路线 `Δfs ≡ 0`」——但未变化路线 `R5 ≡ R10`，其 `Δfs` **恰等于
     `network-effect`**（网络改速在固定路线上的效应），**逻辑上不可能为 0**。
  3. `B2` 要求「变化路线 `Δfs > 0`」——与 `A1`（全网**净降速**，`Σ len·Δfree < 0`）**互相矛盾**：
     当网络整体降速时，`Δfs` 必被 `network-effect` 拉负。
  4. `B5` 要求两项「同号」——亦为误述；路由器对网络降速的**正确响应是反号补偿**。
- **修正定义**（作用在分解项上，语义更锐利）：
  - `B1c` placebo：未变化路线 `route-effect ≡ 0`（容差 1e-9）。
  - `B2c`：变化者 `route-effect > 0`（改道方向 = 走向新网络下更快的路线）。
  - `B5c`：变化者 `route-effect > 0` **且** `network-effect < 0`（**补偿性改道**）。
- **保留**：`B1/B2/B5` 的原始实测结果在 `gate_checks.csv` 中**以 `status=retracted_misspecified` 实录**，
  ⛔ 不删除；判决**只使用** `status=effective` 的判据。
- **不变**：`A1–A3`、`B3`、`B4`、`C1–C3`、`D1`、`D2` 与 §7 判决规则（B 组改为按修正判据判）均不变。
- **证据边界不变**：仍为 `PLANS_LEVEL`；⛔ 不启动 MATSim；⛔ 不调任何冻结参数。
