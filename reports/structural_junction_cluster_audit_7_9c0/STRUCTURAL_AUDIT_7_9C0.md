# Step 7.9C-0 — 结构性瓶颈审计：junction-cluster / short-chain（零仿真 · 只读）

> 定性：**7.9 第一阶段结构审查**。目的 = 用**网络结构 + 既有观测映射**（⛔ 不用 W01 拥堵结果）
> 先把「哪里**应该**堵」定义出来，再把 W01 残差**投影**上去检验。
> 判决：**`STRUCTURAL_BOTTLENECK_PRIOR_ESTABLISHED`**，门 **25/25 PASS**。
> 零仿真：`matsim_rerun=False`；冻结件 `changed=0`（201 件 mtime+size 快照）。

> **边界（用户裁定）**：7.9C **不试图证明「KW 就是瓶颈机制」**。要验证的是两件独立的事：
> **(A)** 网络本身是否存在足够明显的结构性瓶颈与回溢通道；**(B)** 若存在，`queue` 与 `kinematicWaves`
> 是否对这些结构产生**不同的传播行为**。

## 三层空间尺度

| 层 | 定义 | 规模 |
|---|---|---|
| **L1 junction-cluster**（主判据） | 同一自由流层级内、由短链（≤ p90 = 52 m）连成的连通分量，且含 ≥1 结构种子节点；超 200 link 的分量按「移除最长 link」二分拆解 | 22722 单元 / 460001 link（66.3%）/ 6277 km |
| **L2 short-chain** | ramp（`motorway_link`/`trunk_link`）、connector（`primary/secondary/tertiary_link`）、service（`service`）按拓扑合并成链 | ramp 500 链 / connector 2428 链 / service 11638 链 |
| **L3 corridor**（仅宏观诊断） | 按 OSM `name` 分组的主干/快速路线（**不作第一判据**，因 7.9B-0 已证 median corridor 退化为单 link） | 30 条（列前 30） |

**结构种子节点**：度 ≥ 3 且满足任一结构跃变 —— ≥2 个自由流层级 / 自由流落差 ≥20 km/h / 车道数变化 ≥1 / 容量比 ≥1.25。
实测种子 = **50617** 个（占节点 12.01%）；单元规模中位 **10** link、p90 **51**、max **200**。

## C1 — 结构瓶颈先验（**不使用任何仿真流量**）

**节点分数** = 该节点在其**关联 link** 上算出的 4 个分量的未加权均值：

| 分量 | 定义 | 全单元均值 |
|---|---|---|
| `merge_deficit` | 节点处 max(0, (Σ入向容量 − Σ出向容量)/Σ出向容量) —— 经典汇入瓶颈 | 0.0208 |
| `lane_narrowing` | 节点处 max(0, (最大入向车道 − 最小出向车道)/最大入向车道) | 0.1030 |
| `class_transition` | 单元节点处是否出现 ≥2 个自由流层级（道路等级边界） | 0.2348 |
| `ramp_mainline` | 单元节点处是否同时出现 (`*_link` 匝道/接驳) 与 (motorway/trunk/primary 主线) | 0.0124 |

**节点分数 = 4 分量未加权均值**；**单元先验 = 单元内节点分数的最大值**（严重度语义：
「该单元是否含结构瓶颈、有多严重」）。⛔ 不调权。⇒ 均值 **0.3486**、中位 **0.3750**、p80 **0.4167**、max **0.9375**（单元内均值的平均 = 0.0927，作次要列）。

**存储短缺 proxy（`storage_shortage_proxy`）仅作诊断、⛔ 不进分数**：全单元均值 **0.0058** —— 在本路网上它**近乎恒为 0**（碎片路网中「储存容量 / 单步流入」普遍 ≫ 1）⇒ **判别力为零**，故剔除。

**尺寸偏差自查**：`Spearman(prior, log 单元规模) = 0.0251`；单元规模已限制 ≤ 200 link（超限按「移除最长 link」递归拆解，被排除的长 link 归为 background、不计入任何单元，故覆盖率由 77.6% 降至 **66.3%**）。

> ⚠️ 先验采用 **max** 聚合 ⇒ 与单元规模存在天然相关。为**消除此混淆**，C2/C3 均另做
> **单元规模十等分分层控制**（每层内部重新取 p80 阈值），见下。这与 7.9B-0 B4 的「同类别对照」同一纪律。

| 主导自由流层级 | 单元数 | link 数 | 里程 km | 均值先验 | 候选占比 | 均值 v/c | 均值饱和占比 |
|---|---|---|---|---|---|---|---|
| local <30 | 15190 | 318553 | 3912.59 | 0.3319 | 17.50% | 0.0081 | 0.02% |
| collector 30-50 | 1949 | 34162 | 532.78 | 0.3856 | 34.48% | 0.0245 | 0.00% |
| arterial 50-70 | 5304 | 106014 | 1796.64 | 0.3712 | 35.99% | 0.0523 | 0.00% |
| fast 70-90 | 104 | 733 | 18.71 | 0.5482 | 81.73% | 0.3105 | 0.00% |
| expressway >=90 | 175 | 539 | 16.34 | 0.5780 | 94.86% | 0.3416 | 0.00% |

> ⚠️ **层级耦合（重要）**：`fast` 单元 **81.7%**、`expressway` 单元 **94.9%** 都落入候选集（因道路等级边界本身就是种子条件）——这就是 C3 中 `lift` 被「容量/层级」共同因子污染的来源，也是为何 C3 必须附「共同因子证伪」一节。
## C2 — 既有残差的结构投影（**检验，不是定义**）

口径：576 断面（`c0_section_table.csv`）经 7.3.6A crosswalk 落到 L1 单元（断面自身 link 未入单元时，退回其 link 端点的所属单元）；`rel_dev = ratio_8_9 / 池化比 − 1`；单元值 = 观测加权均值。池化 `Sim/Obs = 0.999335`。
映射覆盖：**574 / 576（99.7%）**（link 直连 304、端点兜底 108、空间最近邻 162）。
空间最近邻兜底距离（m）：中位 **56.8**、p90 **172.8**、max **376.4**（门 C0.23）。

| prior 四分位 | 单元数 | 均值先验 | 均值 rel_dev | 负残差单元占比 |
|---|---|---|---|---|
| Q1 lowest | 102 | 0.2842 | -0.0236 | 54.90% |
| Q2 | 113 | 0.4945 | 0.1619 | 46.90% |
| Q3 | 92 | 0.6214 | 0.2707 | 45.65% |
| Q4 highest | 124 | 0.6934 | 0.1546 | 48.39% |

**Spearman(单元先验, 单元 rel_dev) = 0.0355**；**置换零分布**（同区域打乱断面，n=400）：mean=-0.0079、sd=0.0480，**p(rho ≤ 观测) = 0.8125**。
**规模分层后**（十等分，层内重算）：median rho = **0.0359**，负相关层 **4/9**。

⇒ **未发现显著同向**：W01 残差**未**明显向结构瓶颈单元聚集 —— 说明当前 `queue` 模型产生的
   （缺失的）拥堵位置与**结构应有位置**不一致。这正是 7.9B-1 要检验的『堵得对不对』。

> ⚠️ 纪律：候选单元**先**由结构 + 观测映射定义（⛔ 与 W01 流量无关，见门 **C0.22** 自检）；
> 残差只作**事后检验**。⇒ C2 是**探索性的**，确认性检验在 7.9B-1。

## C3 — 「堵得对不对」判据（预登记 + v1.0 基线）

```
HitRate  = |模型高拥堵单元 ∩ 结构候选单元| / |模型高拥堵单元|
Coverage = |结构候选单元 ∩ 模型高拥堵单元| / |结构候选单元|
随机基线 = |结构候选单元| / |全部单元|    ⇒ lift = HitRate / 随机基线   （>1 才是有位置信息）
```
阈值**现在冻结**：候选 = 先验 ≥ p80（=0.4167）；模型高拥堵 = 单元长度加权 `v/c` ≥ p80（=0.0220）。

| 量 | v1.0（queue）基线 | 规模分层后（十等分 macro） |
|---|---|---|
| 候选单元数 | 5490（24.16%） | — |
| 模型高拥堵单元数 | 4545（20.00%） | — |
| 交集 | 2034 | — |
| **HitRate** | **0.4475** | **0.4218** |
| **Coverage** | **0.3705** | **0.3829** |
| 随机基线 | 0.2416 | 0.2226 |
| **lift** | **1.852x** | **1.895x** |

**v1.0 拥堵基线（`HRS8-9avg`/容量）**：`v/c ≥ 1` 的 link **82**（0.0118%），饱和里程 **1.151 km（0.0076%）**；拥堵连通分量 **16** 个，中位长度 **37.9 m**、最长 **0.403 km**。⚠️ **与 7.9A-0 冻结流量投影的 82 link / 1.151 km 逐位一致 ⇒ 本条流水线自检通过（门 C0.17）。**

⇒ **`lift` 就是 B-1 必须超过的基线**。若 B-1 后 `lift` 不升（甚至降），则「地图变红」不构成成功。

### ⚠️ 对 v1.0 基线 `lift` 的**证伪性警告**（先证伪，再断言）

- **值域问题**：v1.0 几乎无拥堵（饱和 link **82** 个 = 全网 0.0118%，饱和里程 1.151 km），单元 `v/c` 的 p80 阈值仅 **0.0220** ⇒ 「模型高拥堵单元」在 v1.0 下**近似任意排名**。
- **共同因子**：`Spearman(prior, 单元单车道容量) = 0.2479`、`Spearman(单元 v/c, 单元单车道容量) = 0.4491` ⇒ 先验与 `v/c` 共享一个**容量因子**，故 `lift` 有一部分**不是位置信息**。
- ⇒ 因此 `lift = **1.852x**` **不得**读作「当前模型已经把拥堵放在对的位置」。它是**弱且被容量污染的**基线。B-1 的价值在于**改变拥堵机制与空间连续性**，而不是把这个数刷高。

## C4 — B-1 最小观察集（**提前冻结**）

| 层面 | 指标 |
|---|---|
| 稳定性 | `A_10:19`、parity gap、`never_arrived`、`max_stuck_car`、stuck 命中 |
| 总量 | `Sim/Obs`（**仅崩解护栏 ≥ 0.85**，⛔ 不再作目标） |
| 链级 | `excess delay_h = TT/FF − ceil(FF)/FF`、link/单元 `v/c` |
| 结构 | junction-cluster 拥堵（长度加权 `v/c`、饱和占比） |
| 空间 | **HitRate / Coverage / lift** |
| 连续性 | 拥堵连通分量长度（km）与分量数 |
| 时段 | 07–09 in-network vehicles（15 min 分箱） |
| 重点对象 | **CTE / service 短链 / ramp 链 / connector 链** |

**成功判据**：B-1 的成功**不是**「地图变红」，而是能证明 `queue → kinematicWaves` 是否改变了**拥堵传播机制与空间连续性**（连续性↑ + lift↑，且总量未崩塌）。
**决断规则**：若拥堵状态指标无实质变化且 `Sim/Obs` 未崩塌 ⇒ 判 **`TIMEDYNAMICS_NOT_PRIMARY`** ⇒ 转 7.9C-1。

## 门

| id | 判据 | 结果 | 细节 |
|---|---|---|---|
| C0.01 | network parsed from frozen v1.0 W01 output | PASS | links=693575 km=15126.51 |
| C0.02 | structural seed nodes identified | PASS | seeds=50617 (12.01%) |
| C0.03 | L1 units built with coverage | PASS | units=22722 links=460001 (66.3%) |
| C0.04 | oversize units resolved (max <= 200 links) | PASS | max_unit_links=200 splits=213 |
| C0.17 | v1.0 baseline reproduces the 7.9A-0 frozen-flow projection (82 links / 1.151 km) | PASS | links=82 km=1.151 (7.9A-0 reported 82 / 1.151) |
| C0.05 | C1 prior computed, all components finite | PASS | units=22722 mean_prior=0.3486 |
| C0.06 | prior size-bias quantified | PASS | spearman_prior_vs_logsize=0.0251 |
| C0.15 | storage-shortage proxy computed (diagnostic, NOT in score) | PASS | mean_storage_proxy=0.0058 (kept out of prior: low discrimination) |
| C0.07 | L2 short chains built (ramp/connector/service) | PASS | ramp=500 connector=2428 service=11638 |
| C0.08 | L3 corridor macro diagnostic built | PASS | corridors=30 |
| C0.09 | sections mapped to L1 units (coverage >= 95%) | PASS | mapped=574/576 (99.7%) direct=304 endpoint=108 spatial=162 |
| C0.23 | spatial fallback assignment distance within 200 m (p90) | PASS | spatial_n=162 p90=172.8 m max=376.4 m |
| C0.10 | C2 residual projection correlation computed | PASS | spearman=0.0355 n_units=431 |
| C0.11 | C2 permutation null computed | PASS | null_n=400 p=0.8125 |
| C0.12 | C3 HitRate/Coverage computed (v1.0 baseline) | PASS | HitRate=0.4475 Coverage=0.3705 |
| C0.13 | C3 lift vs random baseline computed | PASS | lift=1.852x base=0.2416 |
| C0.18 | C3 size-stratified control computed (unit-size confound removed) | PASS | HitRate_strat=0.4218 lift_strat=1.895 n_deciles=9 |
| C0.24 | common-factor falsification: prior vs capacity confounding quantified | PASS | rho(prior,lanecap)=0.248 rho(vc,lanecap)=0.449 |
| C0.25 | v1.0 congestion dynamic range documented (lift read as weak/confounded baseline) | PASS | saturated_links=82 ; unit_vc_p80=0.0220 ; rank-based lift is capacity-confounded, NOT positional evidence |
| C0.19 | C2 size-stratified control computed | PASS | median_rho=0.0359 n_deciles=9 |
| C0.16 | congestion continuity (v1.0 baseline) computed | PASS | components=16 max_km=0.4035 |
| C0.14 | C4 B-1 observation set frozen | PASS | layers=8 file written |
| C0.20 | zero simulation: MATSim not re-run | PASS | matsim_rerun=False |
| C0.21 | frozen artifacts untouched (mtime+size) | PASS | files=201 changed=0 |
| C0.22 | C1 prior uses NO W01 flow input (candidate set is flow-free) | PASS | prior body references flow: False |

## 主线（用户冻结）

`7.9A-0 ✓ → **7.9A-1：sample-consistent capacity** → 7.9B-0 ✓ → **7.9C-0 ✓ 结构审计** → 7.9B-1：queue → kinematicWaves 单变量实验 → （据 B-1）是否进入 7.9C-1：结构性回溢验证`

⛔ **7.9A-1 与 7.9B-1 绝对不合并** —— 否则无法判断拥堵究竟来自 sampling-capacity 一致性还是 traffic dynamics。