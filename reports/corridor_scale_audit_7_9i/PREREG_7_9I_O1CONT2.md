# PREREG · Step 7.9I-O1-续② —— 死管链「接入（access）审计」

> **状态**：`RUN_PRE_REGISTERED_FROZEN`（运行前冻结，2026-09-30）
> **阶段**：`7.9I_FROZEN_CLOSED → O1 ✓ → O1-续 ✓ → READY(O1-续②)`
> **范围（用户 2026-09-30 裁定收紧）**：**只正式推进 `ISO_DEAD_TUBE` 18 节**；`ISO_TWIN_EXISTS` 18 节**仅做证据整理**，只保留 `TWIN_GEOMETRIC_SUBSTITUTE` 标签，⛔ **不做「同一物理车行道」裁定**。
> **底线（冻结，不得触碰）**：⛔ 不改 v1.0 ⛔ 不跑 MATSim ⛔ 不碰 `signals` ⛔ 不碰 `trafficDynamics` ⛔ 不碰 `speedFactor`；全链**零仿真 / 只读**；`changed = 0`；**不产生 v1.1**。

---

## 1. 正式问题（三分支 + 细化）

```text
LTA B2 zero-flow section (18 节 ISO_DEAD_TUBE)
        ↓
MATSim 已建本侧有向链（O1-续已证：本侧 38/38 已建）
        ↓
沿零流链向上游/下游追踪（本步）
        ↓
寻找「应当存在但没有」的接入
        ↓
┌─────────────────────────────────────────────┐
│ A 源头无接入        （OSM 侧就没有接入对象）   │
│ B OSM 有接入但转换丢失（OSM link way → 无边） │
│ C MATSim 无入口边    （头部节点无任何入边）    │
└─────────────────────────────────────────────┘
＋ 若上述三类皆不成立 ⇒ 必须给出**可证伪的细分**，
   否则违反 `readme §4`「冻结判据命中 100% = 判据缺陷」纪律。
```

**★B 是本刀最值得验证的分支**（用户原话）：OSM 是否存在 `motorway_link / trunk_link` 入口对象，但经 `build_impedance` 的 `(u,v)` 去重、`ROUND_M=0.1 m` 网格合并或其他清洗后，**没有形成实际可进入这条零流链的 MATSim 接入**。

---

## 2. 口径（全部冻结，运行前）

### 2.1 常量

| 常量 | 值 | 含义 |
|---|---|---|
| `R_ACC` | **60.0 m** | 链头节点 → OSM way 的邻域半径（与 O1-续 `R_OSM` 同值） |
| `R_MS2` | **50.0 m** | 邻域判定点的 MATSim 同向边搜索半径 |
| `R_SNAP` | **30.0 m** | OSM 端点「终止于」链头节点的吸附半径（**仅披露量**） |
| `DIR_OK` | **30.0°** | 同向容差（与 O1-续同值） |
| `COV_MIN` | **0.50** | OSM link way **转换成功**的最小顶点覆盖率 |
| `SAMPLE_M` | **10.0 m** | OSM way 顶点重采样步长（覆盖率用） |
| `MAX_STEPS` | **2000** | 零流链扩展上限 |
| `CAP_BFS` | **4000** | 活流可达 BFS 上限 |

### 2.2 ★死管链（同向零流单链）

从 matched 边出发双向扩展：**上游** `v=f(e)`，若 `incoming[v]` 中「`flow==0` 的边恰有 1 条」则并入并继续；**下游** `v=t(e)`，若 `outgoing[v]` 中「`flow==0` 的边恰有 1 条」则并入并继续。
- `dead_chain_len` = 链内边数（含 matched 边，去重）
- `upstream_zero_depth` = 上游扩展步数

> ⛔ **本步不追求「物理同向整条走廊」**；`in-deg==1 / out-deg==1` 是无启发式的确定性规则（与 O1-续 `upstream_end` 同源语义）。

### 2.3 三个「接入」对象（★唯一关键区分）

| 对象 | 定义 |
|---|---|
| **链头节点** `head` | matched 边（取集合首条）的 `from` 节点 |
| **OSM 接入对象** | `R_ACC` 内、与链**同向**（`circ_diff(bear_way, bear_section) < 30°`）的 OSM way 数 |
| **MATSim 接入对象** | `head` 的 **MATSim 入边数**（拓扑入口） |

### 2.4 ★B 类判据（转换丢失，严格版）

对每条「OSM 接入对象中的 link way」`L`（`highway ∈ LINK_TYPES`）：
1. 沿 `L` 几何每 `SAMPLE_M=10 m` 重采样顶点；
2. 对每个采样点，在 `R_MS2=50 m` 内找**同向**（`circ_diff(bear_e, bear_section) < 30°`）的 MATSim 边；
3. `cov_frac(L)` = 命中采样点 / 总采样点；
4. `L` **已转换** ⇔ `cov_frac(L) ≥ COV_MIN`。

`conversion_loss` = `OSM_link_n > 0 ∧ 已转换数 == 0`。
`unconverted_link_n` = 未达 `COV_MIN` 的接入 link way 数。

> **★R1（探路后、正式跑前登记）**：单点口径（只看 `L` 离 head 最近的一点）**会把端点落在路口空档的 way 误判为未转换**（实测 49054 的 `479127292` 单点判定=未转换，覆盖率=**0.89** ⇒ 实为已转换）。故正式口径改为**顶点覆盖率**。阈值 `COV_MIN=0.5` 冻结。

### 2.5 判别量 `ms_same_live`（D/E 细分）

`ms_same_live` = `head` 的 `R_MS2=50 m` 内、与链**同向**、且 `flow > 0` 的 MATSim 边数。
> 语义：头部**本地**是否存在同向活流边。`== 0` ⇒ 本方向在本地无活流；`> 0` ⇒ 有同向活流近在 50 m 内却仍零流。

### 2.6 `route_accessible`（★已披露为「不区分量」）

`route_accessible` = `∃ flow>0 的边 e`，使 `t(e) ⇝ head`（有向路径，含 0 跳）。
> **★预注册即披露**：探路显示 18/18 均 `True`（活流上游 1–13 跳可及），**故该字段不构成区分量**；它作为**契约/反例量**保留（N3 应使其变 `False`）。

### 2.7 分类（互斥，优先级自上而下）

| 类 | 规则 | 语义 |
|---|---|---|
| **A** `A_NO_OSM_FEEDER` | `OSM_access_n == 0` | 源头就没有接入对象 |
| **B** `B_LINK_UNCONVERTED` | `OSM_link_n > 0 ∧ 已转换数 == 0` | OSM 有接入、MATSim 转换丢失 ★ |
| **C** `C_NO_MATSIM_IN_EDGE` | `MATSim_access_n == 0` | MATSim 头部无入口边 |
| **D** `D_NO_LOCAL_LIVE_SAME_DIR` | `ms_same_live == 0` | 接入完备、出入口皆通，但**本地同向无活流** |
| **E** `E_LOCAL_LIVE_SAME_DIR_EXISTS` | `ms_same_live > 0` | 接入完备、**本地同向有活流**却仍零流 |

> **★预注册即披露**：探路显示 **A/B/C 预期为空**。为避免「命中 100% 判据缺陷」，**D/E 作为已经过探路的细化轴，一并预注册**（不是后验补丁）。

### 2.8 其余卡片字段

`first_nonzero_dist` = `head` → 最近「关联某条 `flow>0` 边」节点的**欧氏距离（m）**。
`confidence`：A/B/C → `high`；D/E → `medium`（`dead_chain_len ≥ 3`）否则 `low`。

---

## 3. 硬门（全部携带实测值；判据=契约/非退化/复现/负例/确定性，⛔ 不含实质性类计数）

| 门 | 判据 |
|---|---|
| `G-O1C2-1` | 坐标同源：`SEC_GEO_7_6C.mid_x` 落在 SVY21 量级（`0 < mid_x < 1e6`） |
| `G-O1C2-2` | 上游复现：18 节 matched 边总数 = **74**（= O1-续卡片 18 节 `n_match` 之和） |
| `G-O1C2-3` | 冻结对账：18 节 `sim_median_xS` 全为 `0`（`max|·| = 0`） |
| `G-O1C2-4` | OSM 源自检：MAJOR way = **6,694**；`oneway=yes` 占比 = **0.9283**（与 O1-续一致） |
| `G-O1C2-5` | ★**判别量非退化**：`OSM_access_n`、`MATSim_access_n`、`ms_same_live` **三者各至少出现 2 个取值** |
| `G-O1C2-6` | ★**覆盖率口径非退化**：存在 `cov_frac ∈ (0,1)` 的 link way，且 `min cov_frac < 1` |
| `G-O1C2-7` | **死管链非退化**：`dead_chain_len` 取值 ≥ 3 类；`upstream_zero_depth` 有 `0` 与非 `0` |
| `G-O1C2-8` | **卡片完备**：18 行 × 11 必填字段，无缺失；`final_class` 全落在 {A,B,C,D,E} |
| `G-O1C2-N` | **负例 5/5 fired**（且扰动**非同构**、须真改变可观测结果） |
| `G-O1C2-9` | **确定性**：AST 无随机源；卡片 18 行 |

**负例（预注册）**：
- `N1` `R_ACC 60→5 m`（取消 OSM 邻域）⇒ `OSM_access_n` 应骤降
- `N2` `R_MS2 50→2000 m` ⇒ `ms_same_live` 应变大
- `N3` **OSM 几何不投影（保持 `EPSG:4326`）**，与 SVY21 锚点**非同源**（单位由 m 变 degree）⇒ 几何量应崩
  > **★R2（首跑后登记，`n_fail=1` BLOCKED）**：`N3` 原设计为「断面坐标改用 `lta_section_geometry().mx/my`」，但扰动函数以**链头节点**为 OSM 邻域锚点 ⇒ `mx/my` 从未被使用 ⇒ **空扰动**（`fired=False`）⇒ **仪器实现缺陷**（非科学结论）。已改为上句的「不投影」构造；**主路径判据/阈值未改**。
- `N4` `COV_MIN 0.5→1.01`（**空判据**）⇒ `unconverted_link_n` 应 = `OSM_link_n`（证明 B 判据**可证伪**）
- `N5` 方位整体 +180°（same/opp 互换）⇒ `OSM_access_n` / `ms_same_live` 应改变

---

## 4. `ISO_TWIN_EXISTS` 18 节（★仅证据整理）

⛔ **不做「同一物理车行道」裁定**。登记：
- **`TWIN_GEOMETRIC_SUBSTITUTE`**：存在近距离同向高流对象。
- 披露量：`twin_dist_min` 分位（沿用 O1-续卡片），⛔ 不得升级为「同一物理车行道」。

---

## 5. 交付物

- `scripts/od/audit_access_dead_tube_7_9io1c2.py`（引擎）
- `reports/corridor_scale_audit_7_9i/o1c2_access_cards_7_9io1c2.csv`（18 行 Access Card）
- `reports/corridor_scale_audit_7_9i/o1c2_access_summary_7_9io1c2.json`（判决 + 门 + 汇总 + 负例）
- `reports/corridor_scale_audit_7_9i/STEP7_9I_O1CONT2_REPORT.md`

## 6. 结论判读纪律（预注册）

- ⛔ 若 **B = 0/18** ⇒ 明确写「**路网构建链未丢接入**」；**不得**倒过来论证「OSM 有入口但 MATSim 丢了」。
- ⛔ 若 **A/B/C 全为 0** ⇒ 必须显式披露该退化，并以 **D/E** 承担细分；**不得**只报「原因分类占比」。
- ⛔ **观测断面 ≠ 仿真对象**的推论（`U_UNIT_MISMATCH` 同源）**不得**在本步重复消费（O1-续③已单独裁定）。
- ⛔ 所有比例必须声明**暴露面**（本节：18 节 / Σobs = 36,150.5）。
