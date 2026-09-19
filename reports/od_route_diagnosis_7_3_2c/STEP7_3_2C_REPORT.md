# Step 7.3.2C — Motorway Flow Spatial Loading Audit

## 状态

**✅ PASS / 🔒 可冻结**

本步骤只做 **route-structure / spatial-loading** 诊断，**不修改任何模型**：
OD / λ / population / departure profile / network topology / capacity / route-choice / crosswalk 全部保持冻结。

λ 仍为 **0.05（诊断基准）**，**未选定最终 λ**。

---

## 0. 本轮口径与降本设计

- **输入**：`lambda_0p050/ITERS/it.0/step6_3_3b_lambda_0p050.0.plans.xml.gz`（200,000 条 `route type="links"`）+ `reports/matsim_network/network_links_source_copy.csv`。
- **方法**：**逐行流式**解析 `plans.xml.gz`（二进制正则提取 route links，**不构造完整 XML 树、不建 20 万 route 对象**），只累计 motorway / motorway_link 的 edge 使用计数。此前全量对象化解析连续超时，本轻量版一次跑通（`unknown_link_uses=0`）。
- **注意**：本步骤的 edge 使用计数是 **route-structure 指标（多少条 route 经过该 edge）**，**不是小时交通流量**。不要与 LTA 小时点计数直接等量比较；与观测的连接统一走 7.1 靶场的 `sim/obs` 口径。

---

## 1. 产物

```
reports/od_route_diagnosis_7_3_2c/
├─ step7_3_2c_summary.json              # 7.3.2C-1 总览
├─ edge_route_loading.csv               # 693,575 全边 + motorway/motorway_link route 使用计数
├─ top_motorway_edges.csv               # TOP200 motorway（按 route 使用数）
├─ top_motorway_link_edges.csv          # TOP200 motorway_link
├─ route_class_spatial_loading.csv      # 各道路等级 route 长度占比 + route 使用率
├─ route_transition_matrix.csv          # 相邻等级转移矩阵
├─ cata_section_spatial_correspondence.csv    # 7.3.2C-2 逐 CATA 断面装载对应
├─ cata_loading_index_by_roadcat.csv          # 7.3.2C-2 按 RoadCat 汇总
├─ cata_spatial_correspondence_summary.json   # 7.3.2C-2 总览
└─ STEP7_3_2C_REPORT.md
```

脚本：
- `scripts/od/diagnose_motorway_loading_7_3_2c.py`（7.3.2C-1，流式装载计数）
- `scripts/od/analyze_cata_spatial_correspondence_7_3_2c.py`（7.3.2C-2，CATA 断面空间对应）

---

## 2. 7.3.2C-1：route 使用与空间装载

### 2.1 route 层使用（回答“车有没有走高速”）

| 指标 | 值 |
|---|---:|
| route 总数 | **200,000** |
| 使用 motorway 的 route | **122,110（61.06%）** |
| 使用 motorway_link 的 route | **122,774（61.39%）** |
| 未识别 link | **0** |

- **motorway route-length share = 41.48%**；**motorway_link = 5.81%**；**motorway + ramp = 47.29%**。
- 与 7.3.2B 完全一致（61.06% / 61.39%）——两条独立管线互证。

### 2.2 motorway edge 空间装载（回答“流量落在哪些边”）

| 指标 | 值 |
|---|---:|
| motorway edges（CSV 口径） | **4,780** |
| 实际被 route 使用 | **4,044（84.60%）** |
| Top 10 edge 占 motorway 使用量 | **1.196%** |
| Top 50 | **5.46%** |
| Top 100 | **9.57%** |

- **装载极度分散**：4,044 条被使用的 motorway 边里，**装载最高的 100 条合计仅占 9.57%**（即平均每条仅 ≈ 均匀分布的 4 倍）。**不存在“少数 motorway 边吸走大部分流量”的集中结构。**
- **TOP 边全部是 Central Expressway（CTE）**，且每条使用率仅 ≈ **9.67%**（19,335/200,000）——即 CTE 这条最繁忙快速路被切成**数百条 20–100 m 微段**，任何单条边的使用率都被碎片化稀释到 ~10% 量级。
- motorway_link：9,086 条中 **7,598 条（83.62%）** 被使用；Top10 占 **1.388%**、Top50 占 **5.09%** —— 同样极度分散。

### 2.3 等级转移结构

| 转移 | 次数 |
|---|---:|
| motorway → motorway | 16,011,673 |
| motorway_link → motorway_link | 5,122,638 |
| motorway → motorway_link | **160,979** |
| motorway_link → motorway | **162,400** |
| primary → motorway_link | 84,887 |
| motorway_link → primary | 76,502 |

- **主线↔匝道接口被大量使用**（m→ml 160,979 / ml→m 162,400）——与 7.3.2A 的拓扑 `m→ml 240 / ml→m 240`（edge 级）互为印证。
- `ml→ml` 转移 **5.12M** 说明**匝道被切成大量微段串联**（7.3.2B 已测：用 ramp 的 route 平均经 ~42 个 ramp 微段、~30 m/段）。
- **7.3.2B 中 `motorway→motorway_link→motorway` 精确三元组 = 0，不是“没进出高速”**，而是因为匝道被拆成多段（`m→ml→ml→…→m`）或出入口处衔接 primary。**该三元组指标不具验收意义。**

### 2.4 各等级长度占比（route 加权）

| highway | route_length_share | route_use_rate |
|---|---:|---:|
| motorway | 41.48% | 61.06% |
| primary | 27.76% | 96.13% |
| trunk | 9.80% | 42.41% |
| motorway_link | 5.81% | 61.39% |
| secondary | 5.70% | 69.20% |
| residential | 3.16% | 84.87% |

---

## 3. 7.3.2C-2：CATA 断面空间对应

把 6.3.2 tight crosswalk（断面→MATSim 边）与 7.3.2C-1 的 edge 装载计数连接，逐 CATA 断面求其**匹配 motorway 边的平均装载**，再与全网 motorway 均值比较。

- 全网 motorway 平均装载 = **3,383.9 次/边**（4,780 边，含未使用边）；仅被使用边均值 = 3,999.7。
- 339 个 CATA 断面中 **332 个**有匹配到的 motorway 边。

| 指标 | CATA | SLIP_ROAD | CATB |
|---|---:|---:|---:|
| 断面数（有 motorway 匹配） | 332 | 212 | 8 |
| **装载指数 mean**（÷ 全网均值） | **0.846** | **0.852** | 0.921 |
| 装载指数 median | **0.780** | **0.767** | 1.026 |
| **sim/obs mean** | **0.685** | **2.046** | 0.617 |
| sim/obs median | 0.552 | 0.763 | 0.429 |

- **CATA 断面装载指数 mean 0.846 / median 0.780**：CATA 观测点整体落在**低于全网均值约 15–22%** 的 motorway 走廊上；**64.5%** 的 CATA 断面（214/332）低于全网均值。
- **r(装载指数, sim/obs)**：CATA 内 **+0.19（n=332）**、全断面 **+0.25（n=553）**——**弱正相关**，装载仅能解释 CATA sim/obs 约 **3.6%** 的方差。

### ★ 决定性对照

**CATA 与 SLIP_ROAD 的装载指数几乎完全相同（0.846 vs 0.852；median 0.780 vs 0.767），但二者的 sim/obs 方向相反（0.685 vs 2.046）。**

- 也就是说：**“断面落在多繁忙的 motorway 走廊上”这一个变量，无法区分被低估的快速路主线断面与被高估的匝道断面。**
- 结构错配**不是**“CATA 落在空走廊、SLIP_ROAD 落在忙走廊”这么简单——二者处在同一装载区间。

---

## 4. 核心判读（对应预注册三问）

**问 1：车辆是否集中在少数 motorway 边？**
→ **否。** Top100 仅占 9.57%，4,044 条边被使用、分布近乎扁平；最繁忙的 CTE 也因微段切分每条仅 ≈ 10%。

**问 2：是否大量使用 motorway 但绕过 LTA CATA 观测断面？**
→ **部分成立（B-弱）。** CATA 断面确实整体落在低于均值 15–22% 的走廊上（64.5% 低于均值），存在**轻度空间欠装载**；但相关性仅 +0.19，装载远不足以解释 CATA 的系统性低估。

**问 3：是否存在大量平行 motorway / motorway_link 边把流量分散？**
→ **是（结构性主因嫌疑）。** motorway 被切成 **4,780 条微段**、匝道 9,086 条且 `ml→ml` 5.12M 串联——**观测点对位的是碎片化微边，单条微边天然只能承载走廊总流量的一小部分**。这直接对应 CATA 断面 r≈0（空间排序被打散）。

### A / B / C 判定更新

| 假设 | 判定 | 依据 |
|---|---|---|
| **A 高速很少被选择** | **已否定**（7.3.2B 已定，本轮再证） | 61.06% route 使用 motorway、41.5% 路径长度 |
| **B 高速被选但空间分散** | **弱-部分成立** | CATA 断面装载指数 0.78–0.85（低于均值），但 r 仅 +0.19 |
| **C 观测↔网络表达存在系统性差异** | **强支持（主因嫌疑）** | **CATA 与 SLIP_ROAD 装载指数相同、sim/obs 相反**；微段碎片化 |

---

## 5. 与既有证据链的一致性

| 步骤 | 结论 | 与本步关系 |
|---|---|---|
| 6.3.2 Crosswalk | 断面映射粒度非主因 | 本步沿用其 tight crosswalk |
| 6.3.3A/B Departure | 脉冲消除，结构问题仍在 | — |
| 7.2.2 Capacity-only | capacity 非结构杠杆 | 与本步“装载分散”一致：capacity 只动通量水平 |
| 7.3.1 Congestion feedback | ReRoute 非结构杠杆 | 同上：路径已完全重优化，仍分散 |
| 7.3.2A 连通性 | 拓扑无规模性断裂 | 本步 m↔ml 转移 16 万级互证 |
| **7.3.2B 路径结构** | 61% 用高速、单一路径 | 本步逐位复现 61.06%/61.39% |
| **7.3.2C 空间装载** | **装载极分散、CATA 略低载、CATA≈SLIP 装载但 sim/obs 相反** | **指向 C 类（观测/表达）** |

---

## 6. 结论与下一步

1. **“高速没人走”彻底排除**（A 死）；**capacity / 拥堵反馈 / 网络连通性**三大杠杆此前均已排除。
2. **motorway 装载极度分散**：“集中/分散”问题里答案是**极端分散**——由**微段碎片化**驱动。
3. **最关键的新证据**：**CATA 与 SLIP_ROAD 处在同一 motorway 装载水平（≈0.85）却 sim/obs 相反**（0.69 vs 2.05）⇒ **edge 级装载不是判别变量**。
4. 因此剩余误差高度指向 **C 类：LTA 点计数断面 ↔ MATSim 微段路网表达的系统性差异**（断面分级语义、点计数 vs 微边流、走廊碎片化下的空间对位），**而非 route-choice 效用**。

> **建议下一步 → Step 7.3.3：Observation–Representation Diagnosis（观测-表达专项）**
> 不跑仿真，聚焦三件事：(a) SLIP_ROAD 断面为何系统性高估（是否被“断面点计数 vs 匝道多微边口径”放大）；(b) CATA 断面 r≈0 是否源于**微段-断面多对一空间对位**的排序损失；(c) 检验“把 CATA 观测聚合到走廊级（而非微边级）”后 sim/obs 是否回升到 1 附近——若回升，则坐实 C 类。
> **route-choice 参数扫描（原 7.3.2C 后半）优先级进一步下调**：路径结构已确定性、完全重优化，改效用难以移动已成型的空间装载。

**冻结关系**：全部上游 + 7.1 + 7.2.1 + 7.2.2 + 7.3.1 + 7.3.2A + 7.3.2B + **7.3.2C = 🔒**；**λ 仍未冻结**（0.05 仅诊断基准）。

---

## 7. 数据质量与口径说明

- **unknown route links = 0**（`e{from}_{to}` 唯一构造正确，无重复有向边）。
- **edge 计数口径差异**：本步 motorway edges = **4,780**、motorway_link = **9,086**（源自 `network_links_source_copy.csv`，清洗前源表）；7.3.2A 基于 `network_cleaned.xml.gz` 记 motorway **4,744** / motorway_link **9,026**。差异量级 <1%，属**源表 vs 清洗后 XML** 的边集口径差，**不影响任何结论**。
- `sim/obs` 沿用 6.3.2 `section_flow_comparison_lambda_0p050.csv`（`sim_median_scaled / obs_am`）；RoadCat 为断面级 LTA 口径。
- 本步所有产物 `frozen_inputs_unchanged=true`、`lambda_selected=false`。
