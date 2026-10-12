# 判决书 —— E-SB-04：路径重分配与观测域流量增量审计

> 日期：**2026-10-11** ｜ 性质：**零仿真 · 只读**（未启动 MATSim，未改 network/population/capacity/freespeed/SCALE/lambda/阈值）
> 主比较：**v1.0 vs SB-A5**；`SB-A5ind` 作独立 OD 稳健性参照
> 上游：`E-SB-03 = A❌ / B✅(路径重分配) / C❌ / D❌`
> 阶段1+2 门禁：**24/24 PASS** ｜ 阶段3 门禁：**5/5 PASS**

## 0. 一句话

**支持** `PATH_REDISTRIBUTION_SUPPORTED`（证据等级 = **plans**，并由 v1.0 侧 plans↔events 一致率 **100.0%** 佐证）。改 `freespeed` 后，**66.1%** 的 agent 计划路线发生改变，且改变方向一致地**向快速路倾斜**（motorway 路径里程占比 **+2.70 pp**），与 E-SB-03 观测域流量增量在**走廊层面高度同序**。

⚠️ **但不得据此裁决为「已证实的实际路径重分配」**：SB-A5/SB-A5ind **无 events**，执行路线未被直接观测；本书结论的**证据等级 = plans（计划路线）**。

## 1. 阶段 1：输入存在性与可比性（门禁）

| 门禁 | 判据 | 结果 | 实测 |
|---|---|---|---|
| `G01` | v1.0/SB-A5/SB-A5ind 的 plans 与 network 均存在 | ✅ PASS | — |
| `G02` | v1.0 events 存在（writeEventsInterval 重跑） | ✅ PASS | — |
| `G03` | SB-A5/SB-A5ind events 均缺失（⇒ 证据降级） | ✅ PASS | SB-A5/SB-A5ind writeEventsInterval=0 |
| `G04` | events 重跑 = v1.0 冻结配置（仅差 outputDirectory/runId/writeEventsInterval） | ✅ PASS | 实质差异=['controller.writeEventsInterval', 'writeEventsInterval']（外观差异=['controller.outputDirectory', 'controller.runId', 'outputDirectory', 'runId']） |
| `G05.flowCapacityFactor` | flowCapacityFactor 三臂一致 = 1.0 | ✅ PASS | — |
| `G05.qsim.flowCapacityFactor` | qsim.flowCapacityFactor 三臂一致 = 1.0 | ✅ PASS | — |
| `G05.storageCapacityFactor` | storageCapacityFactor 三臂一致 = 1.0 | ✅ PASS | — |
| `G05.qsim.storageCapacityFactor` | qsim.storageCapacityFactor 三臂一致 = 1.0 | ✅ PASS | — |
| `G05.randomSeed` | randomSeed 三臂一致 = 4711 | ✅ PASS | — |
| `G05.global.randomSeed` | global.randomSeed 三臂一致 = 4711 | ✅ PASS | — |
| `G05.replanning.fractionOfIterationsToDisableInnovation` | replanning.fractionOfIterationsToDisableInnovation 三臂一致 = 0.8 | ✅ PASS | — |
| `G05.routingRandomness` | routingRandomness 三臂一致 = 0.0 | ✅ PASS | — |
| `G13` | v1.0 与 SB-A5 使用同一 inputPlansFile（主比较需求可比） | ✅ PASS | v1.0=同 | SB-A5=同 | SB-A5ind=异 |
| `G08.SB-A5` | SB-A5 与 v1.0 网络 link id 集合相同 | ✅ PASS | ∩=693,575 A=693,575 B=693,575 |
| `G08.SB-A5ind` | SB-A5ind 与 v1.0 网络 link id 集合相同 | ✅ PASS | ∩=693,575 A=693,575 B=693,575 |
| `G09` | SB-A5 仅 freespeed 变化（拓扑 from/to/length/cap/lanes 零差异） | ✅ PASS | SB-A5:topo=0 | SB-A5ind:topo=0 |
| `G10` | network→highway 源表覆盖 ≥ 99% | ✅ PASS | 693575/693575 |
| `G06.v1.0` | v1.0 每个 person 恰 1 个 selected plan | ✅ PASS | selected=236044 persons=236044 |
| `G06.SB-A5` | SB-A5 每个 person 恰 1 个 selected plan | ✅ PASS | selected=236044 persons=236044 |
| `G06.SB-A5ind` | SB-A5ind 每个 person 恰 1 个 selected plan | ✅ PASS | selected=236044 persons=236044 |
| `G07.SB-A5` | SB-A5 与 v1.0 person 集合逐位相同 | ✅ PASS | ∩=236,044 | A=236,044 B=236,044 |
| `G07.SB-A5ind` | SB-A5ind 与 v1.0 person 集合逐位相同 | ✅ PASS | ∩=236,044 | A=236,044 B=236,044 |
| `G11` | 时段分支对 SB-A5 判定为 BLOCKED（无 events） | ✅ PASS | BLOCKED（证据不足，不裁） |
| `G12` | v1.0 plans↔events 路线一致率 ≥ 99%（plans 可作执行代理） | ✅ PASS | matched=8000 rate=100.000% |

**输入清单**（`input_manifest.json`，含 sha256）：
- `v1.0.plans`：exists=True，size=215,827,261，sha256=`2aee1ba25a8416c9…`
- `v1.0.network`：exists=True，size=13,816,517，sha256=`0967a059cf37e139…`
- `v1.0.config`：exists=True，size=8,832，sha256=`36e61f2f7f41841a…`
- `v1.0.config_full`：exists=True，size=46,218，sha256=`1d95ad6a70cac581…`
- `SB-A5.plans`：exists=True，size=222,868,451，sha256=`3d89ee66324a6c93…`
- `SB-A5.network`：exists=True，size=14,225,463，sha256=`7384c3ff06591b5f…`
- `SB-A5.config`：exists=True，size=8,858，sha256=`a68dc1514ce5835c…`
- `SB-A5.config_full`：exists=True，size=46,244，sha256=`308200a44c8a79b5…`
- `SB-A5ind.plans`：exists=True，size=224,621,700，sha256=`f2a9b4d966c0c2f5…`
- `SB-A5ind.network`：exists=True，size=14,225,463，sha256=`7384c3ff06591b5f…`
- `SB-A5ind.config`：exists=True，size=8,882，sha256=`2d86d7f3d3766346…`
- `SB-A5ind.config_full`：exists=True，size=46,268，sha256=`3ebdb4c4768fc7cd…`
- `v1.0.events`：exists=True，size=1,694,011,331，sha256=`c9b61fba06d8a9b0…`
- `v1.0.events_config`：exists=True，size=8,830，sha256=`83d1c4c69f96f4f2…`
- `net_src_copy`：exists=True，size=52,670,157，sha256=`b5265e5978608e73…`
- `esb03_section_delta`：exists=True，size=147,079，sha256=`5da9c2ffd5c4ab0f…`
- `esb03_total_decomposition`：exists=True，size=1,242，sha256=`8180bddb19b1bbab…`
- `esb03_summary`：exists=True，size=70,441，sha256=`ad2cfa06d4d504b7…`

**可比性**：三臂 person 集合逐位相同（**236,044**）、每 person 恰 1 个 `selected` plan、网络 link id 集合相同（**693,575**）；**SB-A5 仅 `freespeed` 变化（90,643 链）**，拓扑（from/to/length/capacity/permlanes）**零差异**。

## 2. 阶段 2A：路线结构变化（selected plans）

| 比较 | N | 路线变化数 | 变化率 | 快速路段数(均值) |
|---|---:|---:|---:|---|
| SB-A5 vs v1.0 | 236,044 | 155,928 | **66.06%** | 0.873 → 0.979 |
| SB-A5ind vs v1.0 | 236,044 | 235,893 | **99.94%** | 0.873 → 0.984 |
| SB-A5ind vs SB-A5 | 236,044 | 235,728 | **99.87%** | 0.979 → 0.984 |

### 道路等级路径里程占比（v1.0 → SB-A5）

| highway | v1.0 | SB-A5 | Δ(pp) |
|---|---:|---:|---:|
| motorway | 44.56% | 47.25% | +2.697 |
| motorway_link | 6.27% | 7.15% | +0.877 |
| primary_link | 0.57% | 0.71% | +0.145 |
| secondary_link | 0.12% | 0.15% | +0.027 |
| tertiary_link | 0.02% | 0.03% | +0.006 |
| trunk_link | 0.74% | 0.74% | -0.001 |
| service | 1.81% | 1.78% | -0.023 |
| unclassified | 0.32% | 0.26% | -0.061 |
| tertiary | 2.54% | 2.39% | -0.145 |
| residential | 3.09% | 2.81% | -0.278 |
| secondary | 5.58% | 5.26% | -0.324 |
| trunk | 9.24% | 7.89% | -1.358 |
| primary | 25.14% | 23.58% | -1.561 |

⇒ **motorway ↑、motorway_link ↑；primary ↓、trunk ↓、secondary/residential ↓** ⇒ 计划路线由**干道转向快速路**。

### 需求可比性（关键）

- **v1.0 与 SB-A5 使用同一 `inputPlansFile`**（`population_lambda_0p075.xml.gz`），且网络拓扑逐位相同、仅 `freespeed` 差 90,643 链 ⇒ **v1.0↔SB-A5 的路线变化可干净归因于 `freespeed`**。
- ⚠️ **SB-A5ind 使用不同 population**（`population_SB-A5ind_lambda_0p075.xml.gz`）⇒ 其「路线变化 99.94% / 99.87%」**含需求变更**，只作独立参照，**不并入** freespeed 归因。

## 3. 阶段 2B：时段（证据受限）

- SB-A5/SB-A5ind writeEventsInterval=0 ⇒ 无实际执行事件；时段分支仅 v1.0 侧可校验，SB-A5 侧 BLOCKED（降级为 plans）
- ⇒ 时段分支对 SB-A5 **BLOCKED**；⛔ 不得把无实测的 09:00 后变化当作已验证真实流量。

## 4. 阶段 2C：v1.0 plans↔events 保真（plans 代理合法性）

- 抽样：由 events 重建执行 link 序列，与 selected plan 比对 **一致率 = 100.000%**（n=8,000）。
- 分解：**原样一致** 0；**因 start_link 语义少首链** 8000（MATSim 把车辆置于 `start_link`，故只记其 `left link`、不记 `entered link`）；少末链 0。
- ⇒ 本模型**无日内重路由**，selected plan 的路线 **= 实际执行路线**；该等价对同配置的 SB-A5 亦成立 ⇒ plans 级路线变化**可视作执行级**，但 SB-A5 侧仍**缺 events 直接佐证**。

## 5. 阶段 3：观测域增量 ΔQ 分解

### 5.1 三层级（08-09, cycle it.10-19）

| 层级 | v1.0 | SB-A5 | Δ |
|---|---:|---:|---:|
| lta_section_scaled | 1,513,214.6 | 1,605,179.8 | **+6.08%** |
| matched_edges_raw | 2,650,736.1 | 2,841,195.7 | **+7.19%** |
| network_all_links_raw | 40,055,233.0 | 39,844,516.5 | **-0.53%** |

⇒ **匹配边 +7.19% vs 全网 -0.53%** ⇒ 增量是**观测域选择性**，非全网增车。

### 5.2 走廊 ΔQ × 路线变化（同序检验）

| 走廊 | 路线使用率 v1.0 | SB-A5 | Δ(pp) | 增/减用户 | 断面数 | ΔQ 净额 | 净/毛 | 占净增 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| PIE | 27.33% | 30.38% | +3.06 | +10013/−2797 | 133 | +35,877 | 0.87 | 39.0% |
| TPE | 9.69% | 10.86% | +1.17 | +3788/−1034 | 76 | +22,392 | 0.83 | 24.3% |
| KJE | 4.38% | 5.05% | +0.67 | +1930/−345 | 32 | +8,295 | 0.97 | 9.0% |
| AYE | 11.06% | 12.78% | +1.73 | +5068/−996 | 49 | +6,238 | 0.64 | 6.8% |
| CTE | 19.23% | 21.00% | +1.77 | +9136/−4960 | 29 | +4,937 | 0.22 | 5.4% |
| SLE | 10.63% | 10.63% | -0.00 | +2344/−2345 | 59 | +4,452 | 0.25 | 4.8% |
| （非识别走廊） | - | - | - | +-/−- | 93 | +3,900 | 0.26 | 4.2% |
| KPE | 6.23% | 7.21% | +0.98 | +4818/−2501 | 22 | +2,472 | 0.19 | 2.7% |
| BKE | 10.13% | 10.61% | +0.47 | +2385/−1267 | 36 | +1,747 | 0.35 | 1.9% |
| ECP | 3.26% | 3.84% | +0.59 | +1805/−421 | 47 | +1,655 | 0.33 | 1.8% |
| MCE | 2.07% | 3.70% | +1.63 | +4255/−411 | - | - | - | - |

⇒ 走廊**路线使用率变化**与**ΔQ 净额** 相关：**Pearson=0.74，Spearman=0.67**（PIE 在两者均居首）。

### 5.3 逐匹配边 ΔQ 与对向/平行/聚合

- 逐边 ΔQ：n+=2,118，n−=759，净=203,445.9（净/毛=0.552）
- 对向边亦在匹配集者 **57**，其中**对向且同断面 = 0** ⇒ 方向性替代**不构成**本节增量的主导
- K>1（1 断面↔多边）的匹配边 **3,133** ⇒ 聚合确实存在，但不改变符号/量级
- **Top-2 道路占净增 63.4%，Top-10 占 97.4%**

## 6. 机制判决（预注册五选）

| 机制 | 是否成立 | 证据等级 | 支持证据 | 反例/反证 |
|---|---|---|---|---|
| `PATH_REDISTRIBUTION_SUPPORTED` | ✅ 支持 | PLANS + v1.0 events 代理 | 路线 hash 变化 66.06%（155,928/236,044）；motorway 路径占比 +2.70 pp、motorway_link +0.88 pp；干道 primary -1.56 pp / trunk -1.36 pp；走廊 route-use 变化 vs ΔQ 净额 Spearman=0.67 | SB-A5 侧无 events ⇒ 严格意义上执行路线未被直接观测；但 v1.0 抽样 plans↔events 一致率 100.000%（n=8,000）表明本模型无日内重路由 |
| `TEMPORAL_REALIZATION_SUPPORTED` | ❌ 不支持 | BLOCKED | 需两臂 events 的 link-entry 时刻；SB-A5/SB-A5ind 无 events | E-SB-03 已示 07-08(+6.17%) 与 08-09(+6.08%) 同向，非同小时此消彼长；09:00 后无 LTA 实测 |
| `OBSERVATION_MAPPING_EFFECT_SUPPORTED` | ❌ 不支持 | — | 对向边同属同一 LTA 断面者 = 0（不可能主导）；匹配边 +7.19% 与断面 +6.08% 同向；E-SB-03 已证 R(A5/v1.0) 对 median/mean/max 稳定 [1.0367,1.0681] | K>1（1 断面↔多边）的边 3,133，聚合确实存在，但其不改变符号与量级 |

### 总体判决：**`PATH_REDISTRIBUTION_SUPPORTED`**

- ⛔ **不得**裁为「已证实的实际路径重分配」：SB-A5 无 events；但 v1.0 plans↔events 一致率 100%（n=8,000）说明本模型 plans≡执行路线，故本条**证据等级 = plans（＋v1.0 事件代理）**。
- `TEMPORAL_REALIZATION_SUPPORTED`：**BLOCKED**（缺两臂 events）。
- `OBSERVATION_MAPPING_EFFECT_SUPPORTED`：**不支持**（对向同断面 = 0；匹配边与断面同向；E-SB-03 已证 R(A5/v1.0) 对聚合稳定）。
- 与已 `CLOSED` 的 **O3-R1「承载对象替代」分列**：O3-R1 讲的是**观测对象（link）替代**，本节讲的是**车辆路径重分配**，二者层级不同，⛔ 不合并。

## 7. 下一步（建议，待裁定）

- **补执行级证据**：若需把本条从 plans 级提升为执行级，须对 SB-A5 以 `writeEventsInterval=19` **重跑一次**（需 1 轮 MATSim 全量）——本轮 ⛔ 不启动。
- **路由机制**：可核查 SB-A5 的 `freespeed` 变更集合与 PIE/TPE/CTE/KPE 的空间对应（纯几何，零仿真）。
- ⛔ 在该问题厘清前，不启动容量/信号灯/交叉口实验；⛔ 不调 `SCALE`/容量/阈值；⛔ 不晋升 v1.1。

## 8. 产物

- `D:\Luan\2026-05\2_Singapore\reports\path_redistribution_audit_E_SB_04\config_diff_vs_base.csv`
- `D:\Luan\2026-05\2_Singapore\reports\path_redistribution_audit_E_SB_04\corridor_delta_decomposition.csv`
- `D:\Luan\2026-05\2_Singapore\reports\path_redistribution_audit_E_SB_04\corridor_linkage_route_vs_flow.csv`
- `D:\Luan\2026-05\2_Singapore\reports\path_redistribution_audit_E_SB_04\corridor_route_use.csv`
- `D:\Luan\2026-05\2_Singapore\reports\path_redistribution_audit_E_SB_04\edge_level_delta.csv`
- `D:\Luan\2026-05\2_Singapore\reports\path_redistribution_audit_E_SB_04\esb04_stage12_summary.json`
- `D:\Luan\2026-05\2_Singapore\reports\path_redistribution_audit_E_SB_04\esb04_stage3_summary.json`
- `D:\Luan\2026-05\2_Singapore\reports\path_redistribution_audit_E_SB_04\gate_checks.csv`
- `D:\Luan\2026-05\2_Singapore\reports\path_redistribution_audit_E_SB_04\gate_checks_stage3.csv`
- `D:\Luan\2026-05\2_Singapore\reports\path_redistribution_audit_E_SB_04\input_manifest.json`
- `D:\Luan\2026-05\2_Singapore\reports\path_redistribution_audit_E_SB_04\mechanism_scorecard.csv`
- `D:\Luan\2026-05\2_Singapore\reports\path_redistribution_audit_E_SB_04\network_freespeed_diff.csv`
- `D:\Luan\2026-05\2_Singapore\reports\path_redistribution_audit_E_SB_04\roadclass_route_share.csv`
- `D:\Luan\2026-05\2_Singapore\reports\path_redistribution_audit_E_SB_04\roadclass_route_share_pivot.csv`
- `D:\Luan\2026-05\2_Singapore\reports\path_redistribution_audit_E_SB_04\roadclass_route_vs_flow.csv`
- `D:\Luan\2026-05\2_Singapore\reports\path_redistribution_audit_E_SB_04\route_change_summary.csv`
- `D:\Luan\2026-05\2_Singapore\reports\path_redistribution_audit_E_SB_04\section_delta_by_roadcat.csv`
- `D:\Luan\2026-05\2_Singapore\reports\path_redistribution_audit_E_SB_04\section_delta_by_roadname.csv`
- `D:\Luan\2026-05\2_Singapore\reports\path_redistribution_audit_E_SB_04\section_delta_decomposition.csv`
- `D:\Luan\2026-05\2_Singapore\reports\path_redistribution_audit_E_SB_04\three_level_summary.csv`
- `D:\Luan\2026-05\2_Singapore\reports\path_redistribution_audit_E_SB_04\VERDICT_E-SB-04.md`
