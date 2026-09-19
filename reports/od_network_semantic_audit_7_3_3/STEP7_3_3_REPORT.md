# Step 7.3.3 — LTA 断面语义 ↔ MATSim Link 表达专项审计

> 脚本：`scripts/od/audit_section_semantics_7_3_3.py`（零仿真）
> 网络版本：`network_links_source_copy.csv`（清洗后，motorway 4,780 / motorway_link 9,086）
> 冻结：OD / λ / Population / Departure / Network / Capacity / Route-choice 全部未动
> λ 仍未选择。

## 0. STATUS

**PASS** — 断面语义审计完成，未改任何冻结模型。

## 1. 口径与覆盖

| 项 | 值 |
|---|---:|
| LTA TrafficFlow 断面（JSON 去重后） | 1,311 |
| tight crosswalk 覆盖断面 | 1,278 |
| 覆盖率 | 97.48% |
| 平均 MATSim 边 / 断面 | 10.30 |
| 中位 MATSim 边 / 断面 | 8 |
| 路名一致率（断面均值） | 90.37% |
| 道路等级语义一致率（断面均值） | 83.86% |
| 方向一致率（断面均值） | 56.33% |
| 含混合 highway 语义的断面 | 22.38% |
| 被 ≥2 个断面共享的 MATSim 边 | 28.10% |
| 至少共享 1 条边的断面 | 73.32% |

> 未覆盖的 33 个断面恰为 `RoadCat = #N/A`（无有效等级），不参与 CATA/SLIP 判读。

> **网络版本口径说明**：本审计使用 `network_links_source_copy.csv`（清洗后源拷贝），
> motorway 4,780 / motorway_link 9,086；7.3.2A 的 `network_cleaned.xml.gz`
> 为 motorway 4,744 / motorway_link 9,026，差异 <1%，属**清洗前/后网络口径差异**，
> 不推翻任何结论。正式报告需明确区分这两个网络版本。

## 2. 一个 LTA 断面 → 多少 MATSim 边

断面级匹配边数分布见 `section_semantic_audit.csv`；
平均 10.30、中位 8。
→ 单个 LTA "点流量" 断面被 MATSim 用**多条 link** 重新表达，属一→多关系。

## 3. CATA ↔ highway 语义

- 断面数：**339**
- 平均匹配边：**7.13**（中位 6）
- dominant 落在 motorway 家族（motorway/motorway_link）：
  **99.12%**
- dominant 为纯 `motorway`：**92.92%**
- 含 motorway 边的断面：**97.94%**
- 混合 highway 语义：**16.81%**
- 路名一致率：**91.45%**
- 等级语义一致率：**99.23%**
- 方向一致率：**52.33%**

CATA 断面 dominant highway 分布：

| 值 | 断面数 | 占比 |
|---|---:|---:|
| `motorway` | 315 | 92.9% |
| `motorway_link` | 21 | 6.2% |
| `service` | 3 | 0.9% |

## 4. SLIP_ROAD ↔ highway 语义

- 断面数：**251**
- 平均匹配边：**11.69**（中位 7）
- dominant 为纯 `motorway_link`：**30.68%**
- dominant 落在 `*_link` 家族：**31.47%**
- 含 motorway_link 边的断面：**54.98%**
- 混合 highway 语义：**47.81%**
- 路名一致率：**70.12%**
- 等级语义一致率：**31.63%**
- 方向一致率：**65.51%**

SLIP_ROAD 断面 dominant highway 分布：

| 值 | 断面数 | 占比 |
|---|---:|---:|
| `motorway` | 140 | 55.8% |
| `motorway_link` | 77 | 30.7% |
| `service` | 15 | 6.0% |
| `primary` | 9 | 3.6% |
| `unclassified` | 3 | 1.2% |
| `primary_link` | 2 | 0.8% |
| `secondary` | 2 | 0.8% |
| `residential` | 1 | 0.4% |

## 5. 方向语义与"对向车道混入"

> 该节指标**不依赖 LTA Start→End 的方向约定**，因此比单纯的"方向一致率"更稳健。

| 指标 | 全部 | CATA | SLIP_ROAD |
|---|---:|---:|---:|
| 与 LTA 方向一致率（边加权，断面均值） | 56.33% | 52.33% | 65.51% |
| 断面内自身对向边占比（边加权） | 32.43% | 27.81% | 21.39% |
| 含 ≥1 条对向边的断面 | 72.07% | 65.78% | 69.32% |
| 含精确互反配对（e_a_b + e_b_a）的断面 | 15.49% | 15.93% | 18.73% |
| 匹配边可串成**单一有向链**的断面 | 8.53% | 4.42% | 13.15% |

→ 若一个断面同时匹配到**同一条路的正反两个行驶方向微段**，则断面"点流量"
语义与 MATSim"双向微段集合"表达不对齐，是"对向车道混入"的直接证据。
"可串成单一有向链"比例越低，说明断面被拆成越多方向不一致的碎片。

## 6. 上下游道路等级组合

### CATA 上游等级分布

| 组合 | 断面数 | 占比 |
|---|---:|---:|
| `(无)` | 193 | 56.9% |
| `motorway_link` | 127 | 37.5% |
| `service` | 10 | 2.9% |
| `primary` | 5 | 1.5% |
| `motorway_link|primary` | 2 | 0.6% |
| `secondary` | 1 | 0.3% |
| `motorway` | 1 | 0.3% |

### CATA 下游等级分布

| 组合 | 断面数 | 占比 |
|---|---:|---:|
| `(无)` | 196 | 57.8% |
| `motorway_link` | 123 | 36.3% |
| `service` | 11 | 3.2% |
| `primary` | 4 | 1.2% |
| `motorway_link|primary` | 2 | 0.6% |
| `motorway` | 2 | 0.6% |
| `trunk` | 1 | 0.3% |

### SLIP_ROAD 上游等级分布

| 组合 | 断面数 | 占比 |
|---|---:|---:|
| `(无)` | 179 | 71.3% |
| `motorway_link` | 50 | 19.9% |
| `motorway` | 7 | 2.8% |
| `primary` | 3 | 1.2% |
| `unclassified` | 3 | 1.2% |
| `service` | 3 | 1.2% |
| `tertiary` | 2 | 0.8% |
| `residential|service` | 1 | 0.4% |
| `motorway_link|residential|service` | 1 | 0.4% |
| `residential` | 1 | 0.4% |

### SLIP_ROAD 下游等级分布

| 组合 | 断面数 | 占比 |
|---|---:|---:|
| `(无)` | 145 | 57.8% |
| `motorway_link` | 83 | 33.1% |
| `motorway` | 8 | 3.2% |
| `unclassified` | 3 | 1.2% |
| `primary` | 3 | 1.2% |
| `residential` | 2 | 0.8% |
| `motorway_link|service` | 2 | 0.8% |
| `motorway_link|residential|service` | 1 | 0.4% |
| `tertiary` | 1 | 0.4% |
| `service|tertiary` | 1 | 0.4% |

## 7. 产出文件

| 文件 | 说明 |
|---|---|
| `section_semantic_audit.csv` | 断面级语义审计（边数/一致率/dominant highway） |
| `cata_semantic_audit.csv` | CATA 断面子集 |
| `sliproad_semantic_audit.csv` | SLIP_ROAD 断面子集 |
| `section_upstream_downstream.csv` | 断面链首/链尾 + 上下游道路等级组合 |
| `section_class_transition.csv` | 断面内相邻匹配边等级变化 |
| `section_duplicate_overlap.csv` | 一条 MATSim 边被多少 LTA 断面共享 |
| `roadcat_highway_correspondence.csv` | RoadCat × dominant highway 对应矩阵 |
| `semantic_audit_summary.json` | 汇总指标 |
| `STEP7_3_3_REPORT.md` | 本报告 |

## 8. 判读原则

LTA `RoadCat` 与 OSM/MATSim `highway` 不是同一分类体系，本审计不要求
二者严格一一相等，而是检查：

1. CATA 是否主要落到 motorway 家族；
2. SLIP_ROAD 是否主要落到 `*_link`（尤指 motorway_link）；
3. 一个 LTA 断面是否被映射到过多/过杂的 MATSim links；
4. 一条 MATSim link 是否被多个 LTA 断面共享；
5. CATA / SLIP 的上游-下游道路等级组合是否符合"主线↔匝道"结构。

本步骤不修改任何冻结模型。
