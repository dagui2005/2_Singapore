# PREREG · Step 7.9I-D-path —— D 类零流链「上游有向路径追踪」预注册（运行前冻结）

> 冻结时间：2026-09-30（用户裁定 `7.9I_FROZEN_CLOSED → O1 ✓ → O1-续 ✓ → O1-续② ✓ → READY(D-path)`）
> 冻结件版本：`PREREG_7_9I_DPATH.md` v1（**本文件在任何计算执行前写完**）
> 范围：**只追 D 类 14 节**（`o1c2_access_cards_7_9io1c2.csv` 中 `final_class == D_NO_LOCAL_LIVE_SAME_DIR`）
> 底线：⛔ 不改 v1.0 ⛔ 不跑 MATSim ⛔ 不碰 `signals` ⛔ 不碰 `trafficDynamics` ⛔ 不碰 `speedFactor` ⛔ 本刀不产生 v1.1

---

## 1. 正式问题（用户 2026-09-30 裁定）

```text
B2 本侧零流链
↓
沿有向拓扑向上游展开
↓
最近 active edge
↓
它究竟属于哪一种
```

| 类别 | 判定含义 |
|---|---|
| **D1** | 活流进入**同向平行链** |
| **D2** | 活流来自**对向车行道 / 对层** |
| **D3** | 活流仍在**同一走廊**，但更远处才重新汇入 |
| **D4** | 活流已经进入**拓扑替代路线** |
| **D5** | 在预定追踪深度内找不到合理承载对象 |

**★核心证据（用户指定）**：流量守恒
```text
zero-flow chain → branch / merge → first active chain → upstream inflow ≈ downstream outflow
```
目的是区分：
> **车根本没进入这条路**  vs  **车进入了这个道路走廊，但被另一条平行/替代有向链承载**

**★纪律（用户指定，本刀不可越界）**：
> **D1–D4 只能叫「承载对象替代 / 路径重分配」，不能直接叫「映射错误」**。
> 除非能与 OSM way / LTA detector / 物理设施对象建立可靠对应，否则不得把「MATSim 流到了旁边」升级成「MATSim 建错了」。（与 A2、B(b) 已建立纪律一致）

---

## 2. 口径（运行前冻结，⛔ 不得改）

### 2.1 常量表

| 常量 | 值 | 含义 |
|---|---|---|
| `HOP_MAX` | 120 | 反向零流 BFS 最大跳数 |
| `CAP_DOM` | 60000 | 反向零流域节点上限（触顶必须披露） |
| `MAX_STEPS` | 2000 | 单度链扩展上限 |
| `DIR_OK` | 30.0° | 「同向」阈值（承接 O1-续②，未改） |
| `OPP_MIN` | 150.0° | 「对向/对层」阈值（本刀新增，对称于 `DIR_OK`） |
| `D_PAR` | 60.0 m | 「紧邻平行」阈值（承接 O1-续② `R_ACC=60 m`，未改） |
| `CARRY_MIN` | 0.50 | 承载充分性阈值（作用于 `carry_scaled`） |
| `SCALE` | 2.29897 | 冻结采样倍率（v1.0） |
| `K_pooled` | 5.5434 | 1 断面 ↔ K 边的池化计数基数（**必须同报**） |
| `R_EUC` | — | 欧氏最近活性边**仅作诊断披露**，不参与分类 |

### 2.2 上游零流域 `hr(·)`（有向）

从链头节点 `head` 出发，**只允许经 `flow == 0` 的边反向行走**：
`hr(head) = 0`；`hr(u) = hr(v) + 1` 当且仅当存在边 `e: u → v` 且 `flow(e) == 0`；BFS 逐层 ⇒ **`hop ≤ 26` 层完整**（见 §3 `G-DP-6`）。
域记 `dom(hr)`；`hr_max = max hr`；`capped` = 是否触 `CAP_DOM`。

> ★为什么只用零流边：本刀问的是「**活性流为什么没有到达本链**」。若允许经活边反向行走，则等于假设流已到达，与 `head_in_flow == 0` 矛盾。

### 2.3 「最近 upstream active edge」`e_near`

**候选集** `C_in = { e : flow(e) > 0  ∧  to(e) ∈ dom(hr)  ∧  hr(to(e)) ≥ 1 }`
（`hr ≥ 1` 用于排除「从 `head` 本身驶出」的下游边；`C_in = ∅` ⇒ **D5**）

**选边规则（字典序，确定性）**：`e_near = argmin ( hr(to(e)), −flow(e), e )`
即：**先最小跳数 → 再最大流量 → 再最小边序**。⛔ 不按欧氏距离选边（见 §2.9 披露）。

### 2.4 承载链 `A*`（单度活链）

从 `e_near` 出发，沿 `flow > 0` 的边**双向**扩展：
- 向后：当尾节点 `v` 满足 `n_in_live(v) == 1` 时前置该唯一活入边；
- 向前：当头节点 `v` 满足 `n_out_live(v) == 1` 时追加该唯一活出边；
- `MAX_STEPS` 上限 + **visited 节点集合防环**。

记 `A_tail = frm(A*[0])`、`A_head = to(A*[-1])`、`A_n = |A*|`、`A_len_m = Σ LENGTH`（★`LENGTH` 单位实测为 **m**，见 §3 `G-DP-1`）。

### 2.5 ★流量守恒证据（核心）

| 量 | 定义 |
|---|---|
| `flA_in` | `flow(A*[0])` |
| `flA_out` | `flow(A*[-1])` |
| `fl_in_ext` | `Σ flow(live in-edges of A_tail)` |
| `fl_out_ext` | `Σ flow(live out-edges of A_head)` |
| `R_cons` | `flA_out / flA_in` — **链内守恒**（应 ≈1；<1 表示沿链衰减，>1 表示沿链生成） |
| `Rn` | `flA_in / fl_in_ext` — **上游分流比**（`fl_in_ext > 0` 时可得） |
| `Rd` | `fl_out_ext / flA_out` — **下游续行比**（`flA_out > 0` 时可得；`= 0` 表示流量在 `A_head` 终止） |
| `cons_testable` | `fl_in_ext > 0` ∧ `flA_in > 0` |

### 2.6 ★承载充分性（**第二轴**，与 D1–D5 并列报告）

| 量 | 定义 |
|---|---|
| `carry_raw` | `flA_in / obs_8_9` |
| `carry_scaled` | `flA_in × SCALE / obs_8_9` |
| `carry_class` | `F_ADQ` if `carry_scaled ≥ CARRY_MIN` else `F_LOW` |

⛔ **基数披露（强制）**：`carry_*` 是「单条 MATSim 边流量」与「LTA 单断面观测量」之比，`K_pooled = 5.5434` ⇒ **仅作量级参照，不作独立判据**；`carry_class` 只用于**细化**，不得替代 D1–D5。

### 2.7 分类表（互斥，**优先级 D5 > D3 > D2 > D1 > D4**）

| 顺序 | 类别 | 判据 |
|---|---|---|
| 1 | **D5** | `C_in == ∅`（`HOP_MAX` 内无任何 active edge 可经零流路径到达） |
| 2 | **D3** | `dn_live > 0`：**本链自身下游**存在活流（matched 边尾节点或上游死链末端的活出边计数 > 0）⇒ 同一走廊更远处才有流 |
| 3 | **D2** | `e_near_dbear ≥ OPP_MIN (150°)` ⇒ 对向/对层 |
| 4 | **D1** | `e_near_dbear ≤ DIR_OK (30°)` ∧ `e_near_d_own ≤ D_PAR (60 m)` ⇒ 同向紧邻平行链 |
| 5 | **D4** | 其余（同向但远 / 斜交 30°–150°）⇒ 拓扑替代 / 远距离重分配 |

**★退化预警（预注册即披露）**：
- **D1 预期 = 0**：D 类的定义即为「链头 50 m 内无同向活流」⇒ 同向且 `d_own ≤ 60 m` 的活对象**被上游定义结构性排除**。
  ⇒ **D1 = 0 不得读作「平行承载不存在」**，只能读作「**在本层判据下不可检出**」。
- **D5 预期 = 0**（探路显示 `C_in ≠ ∅`）⇒ `G-DP-N` 的 `N1` 必须能把 `C_in` 逼空，以证明 D5 判据可证伪而非死代码。

### 2.8 诊断列（强制披露，**不参与分类**）

| 量 | 含义 |
|---|---|
| `near_euc_db` | **欧氏最近**活边（不限定 `C_in`）相对本链的方位差 |
| `near_euc_in_Cin` | 该欧氏最近活边是否落在 `C_in` 内（True/False） |
| `ms_same` / `ms_same_live` | 复现 O1-续②：链头 50 m 内**同向** MATSim 边数（任意流量 / 活流量） |

> ★披露目的：若「拓扑最近」与「欧氏最近」长期不一致，说明零流团惰性遍历（`dom` 达 4k–6k 节点、跳数 ≤26）可能把 `e_near` 拉到物理上并不相邻的对象上 ⇒ **必须在报告中同报**，不得只报其一。

### 2.9 Card 字段（逐断面，14 行）

`section_id / RoadName / obs_8_9 / dead_chain_len / head_node / chain_bear / hr_dom_n / hr_hop_max / hr_capped / n_Cin / e_near_id / e_near_hw / e_near_fl / e_near_hop / e_near_dbear / e_near_d_own / A_star_n / A_star_len_m / flA_in / flA_out / R_cons / fl_in_ext / fl_out_ext / Rn / Rd / cons_testable / carry_raw / carry_scaled / carry_class / ms_same / ms_same_live / dn_live / near_euc_db / near_euc_in_Cin / final_class / confidence`

`confidence`：`high`（`cons_testable=True` 且 `n_Cin ≥ 20`）/ `medium`（`cons_testable=True`）/ `low`（其余）。

---

## 3. 硬门（10 项，全部须 PASS）

| 门 | 内容 |
|---|---|
| `G-DP-1` | 坐标同源（`SEC_GEO_7_6C.mid_x` ∈ SVY21 量级 <1e6）＋ **`LENGTH` 单位自检**（`LENGTH / 欧氏长度` 长边 p50 ∈ [0.99, 1.01] ⇒ m） |
| `G-DP-2` | 上游复现（D 类 **14 节**，Σobs = **28,361.0**，与 O1-续② 卡片逐位一致） |
| `G-DP-3` | 冻结对账（14 节 `sim_median_xS` 全为 0） |
| `G-DP-4` | 前提复核（14 节 `ms_same_live == 0` ∧ `MATSim_access_n ≥ 1` ∧ `head_in_flow == 0`） |
| `G-DP-5` | ★判别量非退化（`e_near_dbear` ≥2 取值 ∧ 极差 > 60°；`e_near_d_own` ≥2 取值；`e_near_hop` ≥2 取值；`R_cons` ≥2 取值） |
| `G-DP-6` | ★追踪完整性（`max(e_near_hop) ≤ HOP_MAX/4` ∧ `capped == False`（全节）） |
| `G-DP-7` | Card 完备（14 行 × §2.9 必填字段；`final_class ⊆ {D1..D5}`；`carry_class ⊆ {F_ADQ,F_LOW}`） |
| `G-DP-8` | ★支配类不得 100%（`nunique(final_class) ≥ 2` ∧ 最大类占比 < 100%）＋ 同报 `D1 == 0` 退化披露 |
| `G-DP-9` | 确定性自检（AST 无随机源 ∧ 14 行 ∧ **负例走与主路径同一函数**（`compute(params)`），保证扰动非空操作） |
| `G-DP-N` | 负例 **5/5 fired**（见 §4） |

## 4. 负例（5，须**非同构**扰动且**真改变可观测结果**）

| ID | 扰动 | 预期作用 |
|---|---|---|
| `N1` | `HOP_MAX 120 → 2` | 上游域被压到 2 层 ⇒ 部分节 `C_in = ∅` ⇒ **D5 出现**（证明 D5 非死代码） |
| `N2` | `OPP_MIN 150 → 30.1` | 斜交并入同向 ⇒ 类别重排 |
| `N3` | `D_PAR 60 → 5000` | 远距离同向并入 D1 ⇒ 类别重排 |
| `N4` | 参考方位整体 `+180°` | 同向 ↔ 对向互换 ⇒ `D2` 与同向类互换 |
| `N5` | 上游域放宽为**全边**反向 BFS（`zero_only=False`） | 域与 `e_near` 同时改变 ⇒ 类别/字段变 |

**签名** `sig = (n_D1, n_D2, n_D3, n_D4, n_D5, Σe_near_hop, Σ round(carry_scaled×1000), Σ round(R_cons×100), Σ flA_in)`

> ⚠️ 承接 O1-续② 教训 `R2`（负例空扰动 = 假阴性）：本刀**负例与主路径共用同一 `compute(params)`**，从实现层面消除「扰动未生效」这一类缺陷。

## 5. 交付物

| 文件 | 说明 |
|---|---|
| `scripts/od/audit_dpath_7_9id1.py` | 引擎（10 门 + 负例 5） |
| `reports/corridor_scale_audit_7_9i/o1d_trace_cards_7_9id1.csv` | 14 行 × 35 列逐断面 Card |
| `reports/corridor_scale_audit_7_9i/o1d_trace_summary_7_9id1.json` | 门禁 / 负例 / 汇总 |
| `reports/corridor_scale_audit_7_9i/STEP7_9I_DPATH_REPORT.md` | 报告 |

## 6. 判读纪律（⛔ 全部不可越界）

1. ⛔ D1–D4 **只能**表述为「**承载对象替代 / 路径重分配**」，**不得**升级为「映射错误 / 建错」。
2. ⛔ 不得把 `carry_*` 与 `obs` 的差异读作 demand scale 证据（`K_pooled` 基数不同）。
3. ⛔ 不得以本刀结论**回写 target**、**改 SCALE**、**改 v1.0**、**产生 v1.1**。
4. ⛔ 不得因「D2 占比最高」而断言「对向车行道在承载」—— `e_near` 为对向 ⇒ 其流向与本链相反 ⇒ 只能读作「**本方向未检出同向供流对象**」。
5. ⛔ `ISO_TWIN_EXISTS` 仍只保留 `TWIN_GEOMETRIC_SUBSTITUTE`，本刀不动它。
6. ✅ 必须同报退化诊断：`D1 == 0`（结构性）、`G-DP-6`/`hr_capped`、拓扑最近 vs 欧氏最近一致率。

## 7. 预注册修正登记（运行后如需改判据，必须登记于此并说明属「设计缺陷 / 实现缺陷」）

> （运行时若发生，于此处追加 `R1…`；**非科学结论**。）

---

*本文件于引擎任何一次执行前冻结。* 
