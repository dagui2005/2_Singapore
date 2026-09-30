# PREREG · Step 7.9I-O1 —— B2 车行道对（carriageway pair）层

- **步骤**：7.9I-O1（O1 恢复入口第一步；**零仿真 / 只读**）
- **上游**：`7.9I_FROZEN_CLOSED → READY(O1)`（`CLOSURE_7_9I.md`）
- **引擎（待写）**：`scripts/od/audit_carriageway_pair_7_9io1.py`
- **本文件在运行前冻结**；运行后判据/阈值**不得改动**，如需修订须另立后验脚本并标 `EXPLORATORY_POST_HOC`
- **日期**：2026-09-30

---

## 1. 要回答的问题

> **LTA 所观测的「一个方向断面」，与 MATSim 中由独立节点串表达的另一方向车行道，到底是什么对应关系？**

拆成三个可判定的子问题：

| 编号 | 子问题 | 判定量 |
|---|---|---|
| Q-a | 该断面的**对向对象**在网络里存在吗？以什么形式存在？ | `Q0_TWIN_PAIR` / `Q1_SEPARATE_CARRIAGEWAY` / `Q2_NO_OPPOSITE_OBJECT` |
| Q-b | 若把对向对象**当作该断面的物理对应物**重新计流，载流比是多少？ | `r_pair(s) = SCALE × Σ_C rep(C) / obs_s` |
| Q-c | 这能否解释掉 `B2` 的一大块？ | `PAIR_CONSISTENT` 覆盖的 Σobs 份额（`B2` 与全靶场分别报） |

## 2. 输入（全部冻结产物，只读）

| 输入 | 来源 |
|---|---|
| 全网图（421,406 节点 / 693,575 边） | `scripts/od/_cache_network_7_9c0.npz`（经 `Graph` 载入） |
| 边流量 `HRS8-9avg` | `read_edge_full(V10_LS)`（v1.0，冻结） |
| 断面中点 `mid_x/mid_y`（**SVY21**）与 `bear` | `SEC_GEO_7_6C`（位置）/ `lta_section_geometry()`（`bear`/`len_m`，与 CRS 无关） |
| `B(b)` 目标集（38 节） | `bb_zero_flow_ledger_7_9ibb.csv` |
| `B(b)-P` 对账量 | `bbp_direction_probe_7_9ibbp.csv` |
| 靶场断面全集（576）与匹配链（3,015） | `load_frozen()`（`obs` / `cw`） |

**★坐标纪律（沿用 `CLOSURE §3-R2`）**：断面位置**一律**取 `SEC_GEO_7_6C.mid_x/mid_y`（SVY21）；
⛔ **不得**取 `lta_section_geometry().mx/my`（局部等距平面米 ≈1.15e7，与全网图不同源）。

## 3. 操作定义

### 3.1 对向边池 `E_opp(s)`（**不要求有流**）

```
E_opp(s) = { e : ‖mid_e − mid_s‖ ≤ R
               ∧ highway(e) ∈ MAJOR = {motorway, motorway_link, trunk, trunk_link}
               ∧ circ_diff(bear_e, (bear_s + 180°) mod 360) < DIR_OK
               ∧ e ∉ matched(s) }
```

- `mid_e = (G.ex[e], G.ey[e])`（边中点，SVY21）；`bear_e` 由 `G.nx/G.ny` 计算。
- `circ_diff(a, b) = |((a − b + 180) mod 360) − 180|`。
- **与 `7.9I-B(b)` 的唯一差别**：此处**去掉 `flow > 0`**。
  **理由**：`B(b)` 问「流量去了哪」（必须是有流对象）；O1 问「**对象对应关系**」，
  必须允许「对向对象存在但无流」这一情形，否则无法区分
  「没有对向对象」与「有对向对象但没流量」。⇒ 这是**刻意的口径扩展**，不是放松。

### 3.2 对向有向链分量

在 `E_opp(s)` 诱导的无向子图上取**弱连通分量** `C_1…C_m`。对每个 `C`，按 `7.9I-A1` 同一规则取代表值：

| 条件 | `rep(C)` |
|---|---|
| `C` 为**有向路径**（`|E|=|V|−1` 且 `max(outdeg) ≤ 1`、`max(indeg) ≤ 1`，且**恰有 1 个 `indeg=0` 起点、恰有 1 个 `outdeg=0` 终点**） | `median_{e∈C} flow_e` |
| 否则（**无向**路径但存在折返 / 分支 / 交叉 / 多起点多终点） | `Σ_{e∈C} flow_e` |

> **★为何「有向路径」而非「每步方位一致」**：`E_opp` 内每条边**已按方位筛过**
> （`circ_diff(bear_e, bear_s+180°) < DIR_OK`），故「链内每步方位一致」**恒真**——
> 拿它当判据就是**命中 100% 的退化判据**（违反 `readme §4` 纪律）。
> 真正有区分度的是**拓扑方向性**：一组方位都对的边，仍可能在拓扑上**折返**
> （`A→B→C` 与 `C→B→A` 混装）⇒ 不是同一股车流 ⇒ 只能 `sum`。
> 判据由此变为 `is_directed_path`，实测必同时出现两类 ⇒ 非退化。

```
sim_pair(s) = SCALE × Σ_{C} rep(C)
r_pair(s)   = sim_pair(s) / obs_s
```

**链内不重复计数、跨链可加**（与 `7.9I-A1` 一致）。

### 3.3 对层分类（对断面 `s`）

| 类 | 判据 | 含义 |
|---|---|---|
| **`Q0_TWIN_PAIR`** | `∃ e ∈ E_opp(s)` 使 `(t_e, f_e) ∈ E`（同节点对反向孪生存在） | 该设施被建模为**双向 way** |
| **`Q1_SEPARATE_CARRIAGEWAY`** | `E_opp(s) ≠ ∅` 且无任何孪生 | 对向车行道以**独立节点串**另建 |
| **`Q2_NO_OPPOSITE_OBJECT`** | `E_opp(s) = ∅` | 邻近**根本没有**对向承载对象 |

优先级：`Q0` > `Q1` > `Q2`（存在任一孪生即记 `Q0`）。

### 3.4 对层一致性判据

`r_pair(s) ∈ [0.5, 2.0]` ⇒ 记 **`PAIR_CONSISTENT`**（对层口径下与观测同量级）。
报告 `Σobs(PAIR_CONSISTENT) / Σobs(全体)`，**`B2` 与全靶场分别报**。

## 4. 硬门（8 项，全部携带实测值）

| 编号 | 门 | 阈值 |
|---|---|---|
| `G-O1-1` | 坐标同源 | 样例 `0 < mid_x < 1.0e6`（SVY21 量级） |
| `G-O1-2` | 与冻结引擎逐位对账 `n_par_opp_100` | **逐位全等**（Σ = **139**） |
| `G-O1-3` | 匹配边方向一致 | `Σ n_matc_opp = 0`、`Σ n_matched = 152` |
| `G-O1-4` | `Q0` 覆盖 `B(b)-P` 的孪生节 | `Q0 ⊇ {s : twin_exist > 0}`（**7 节**，`E_opp` 放宽 ⇒ 只多不少）；并报差集 |
| `G-O1-5` | 拓扑方向判据**非退化** | 判为 `is_directed_path`（⇒`median`）与降级为 `sum` 的 `C` **两类都出现**（`0 < n_directed < n_comp`）；并报 `n_comp` / `n_directed` |
| `G-O1-6` | 非退化 | `Q0 / Q1 / Q2` 三类**均非空** |
| `G-O1-7` | 口径嵌套自洽 | `E_opp`（无流过滤）**严格包含**其「有流子集」，且差集 = 「对向 MAJOR 但无流」的边；报三者计数 |
| `G-O1-8` | 确定性自检（AST） | 源码**无随机源**（`random` / `np.random` / `shuffle` 命中 0）；产物卡片行数 = **38** |

## 5. 负例（4 项，须 `fired = True`，且**非同构扰动**）

| 编号 | 扰动 | 期望 |
|---|---|---|
| `N1` | `DIR_OK`: `30° → 180°`（取消方向约束） | `E_opp` 规模与 `Q0/Q1/Q2` 构成**必变** |
| `N2` | `R`: `100 m → 3000 m` | `r_pair` 与分类**必变** |
| `N3` | 断面坐标改用 `lta_section_geometry().mx/my` | `E_opp` **必空**（距离恒 ≈1.15e7 m）⇒ `Q2 = 100%` |
| `N4` | 代表值规则退化为「全部 `sum`」（取消路径 `median`） | `sim_pair` **必变**（路径分量被重复计数放大） |

## 6. 范围与限制（预先声明）

1. **`E_opp` 是「几何+拓扑」构造，不是「真值对应表」**。它只回答「邻近存在哪种形式的对向对象」，
   ⛔ **不得**读作「LTA 的这个断面就是 MATSim 的这条链」——那需要 LTA detector 元数据，本步不具备。
2. `r_pair` 若落在 `[0.5, 2.0]`，仅说明**量级相容**，**不等于**「对层映射正确」。
3. 对向链的**上游/下游延伸范围**由 `R` 决定（本步 `R = 100 m`）；`R` 是**暴露面**，必须同报。
4. 本步**不触碰** v1.0 任何参数；`changed = 0`；不产生 v1.1。

## 7. 产物

| 文件 | 内容 |
|---|---|
| `o1_pair_cards_7_9io1.csv` | 38 节逐断面卡片（分类 / `E_opp` 规模 / 孪生 / `r_pair` / 链分量明细） |
| `o1_pair_census_7_9io1.csv` | 靶场全集（576）对层分类普查 |
| `o1_pair_summary_7_9io1.json` | 判决 + 门 + 汇总（self-audit） |
| `_run_7_9io1.log` | 运行日志 |
