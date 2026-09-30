# Step 7.9C-1 预注册判据（冻结）— Structural Spillback Validation

> **冻结时间**：2026-09-20（7.9B-1 正式收口之后、7.9C-1 执行之前）
> **冻结依据**：7.9C-0 冻结结构 `c0_junction_clusters.csv`（22,722 单元）+ v1.0 冻结网络 `_cache_network_7_9c0.npz`（693,575 link / 421,406 node）
> **只读声明**：本步**零仿真**。候选集**不读取任何 W01/KW 流量**。仿真延误**仅作对账**（test, not definition），与 7.9C-0「先验与流量解耦」同一纪律。
> **上游收口**：`7.9B-1 ✓ 实验性未采纳` ⇒ v1.0 仍为冻结模型，C-1 **不回灌、不产生 v1.1**。

---

## 0. 唯一问题（单一命题，禁止扩散）

> **为什么真实拥堵结构应出现在 CTE / 主干快速路及其回溢链上，而当前 MATSim 却把大量延误吸收到 service/connector 等短段？**

C-1 **不再回答**「kinematicWaves 是否有效」——该问题已由 7.9B-1 回答（机制变、位置未改善）。
C-1 **只回答**：

> **网络表达方式本身，是否阻断了拥堵从瓶颈向上游传播的结构通道？**

---

## 1. 三条证据链（冻结）

```
真实候选瓶颈  →  上游传播路径  →  下游储存/阻塞能力
 E1              E2                E3
```

| 链 | 冻结定义 | 来源 |
|---|---|---|
| **E1 真实候选瓶颈** | `is_candidate==1` 的 7.9C-0 结构单元（prior ≥ p80 = 0.41667）；其**类别/走廊/是否含主线 link** | C-0 冻结 |
| **E2 上游传播路径** | `up_chain_m`：沿**同名物理道路**反向的连续链长（含本 link） | 静态网络 |
| **E3 下游储存/阻塞能力** | `down_storage_veh = Σ_{out} lanes×len/CELL`（下游可存车数）；`inflow_rate = Σ_{in} cap/3600`（辆/s）；`fill_time_s = down_storage_veh / inflow_rate`（下游灌满耗时）；对照 `up_storage_veh`（上游通道可存车数）；`return_competent = 下游节点存在 ≥1 条 motorway 出边` | 静态网络 |

---

## 2. 统一拓扑框架（一个坐标系放五类对象）

所有 693,575 link 归入 **class × corridor(name) × junction-cluster(unit)**：

- **class**（严格沿用 7.9B-1 定义，保证与 B-1 延误分解可对账）：
  `ramp` = {motorway_link, trunk_link}；`connector` = 其余 `*_link`；`service` = `service`；`motorway` = {motorway, trunk}（**= 主线**）；`other` = 其余。
- **corridor**：按 `name` 直配的命名走廊（Central / Tampines / Pan-Island / Ayer Rajah / Kallang-Paya Lebar / East Coast Pkwy / Seletar / Bukit Timah / Marina Coastal / Kranji Expressway）。
- **junction-cluster**：7.9C-0 L1 单元（`link2unit`，22,722 个）。

> ⚠️ **B-1 用词更正（本步附带修正）**：`name` 中**不含**字面 "CTE"（0 条 link）。B-1 的 `"CTE" in name.upper()` 掩码实际只命中 `CHANGI ∪ TAMPINES EXP`。C-1 一律以 **`Central Expressway`（603 link / 34.55 km）** 为 CTE 正名，并单列 B-1 旧掩码以保持可比。

---

## 3. 四条拓扑检查 + 预登记阈值

| ID | 检查（用户口径） | 预登记量 | 阈值（冻结） |
|---|---|---|---|
| **K1** | 主线 → merge/diverge → 上游 link 是否存在**连续可传播路径** | 主线(motorway) link 的 `up_main_m`（同名且同为主线类的反向连续链长） | `CHAIN_MIN_M = 300` m；敏感度另报 500/1000 m |
| **K2** | **downstream storage 是否足以产生反向回溢** | 候选瓶颈节点的 `down_storage_veh`、`fill_time_s`、对照 `up_storage_veh` | `FILL_BLOCK_S = 10` s（`fill_time_s < 10` ⇒ 下游即被灌满 ⇒ 阻塞/回溢倾向） |
| **K3** | **service/connector 是否存在「先堵自己、无法把压力传回主线」的拓扑断点** | `return_incompetent` = 下游节点**无** motorway 出边的 link 占比，按 class | 断点占比 ≥ 90% 判为「结构上无法回压主线」 |
| **K4** | 同一物理道路是否被切成**过多超短 link**，导致拥堵被局部吸收 | 按 class/name：`links/km`、`median_len`、`%≤SHORT_M` | `SHORT_M = 20` m；碎化重判 = `links/km > 40` |

**四道硬门**：K1–K4 各自必须产出有限、可复算的量；K1 的静态量须能复现（两次运行逐位一致）。

---

## 4. 决定性对账（test, not definition）

1. **延误去向**：v1.0 与 KW 的 `delay_h` 按 class / 按 `return_competent` / 按命名走廊分解。
2. **通道—延误对齐**：以 `delay_h` 为权，计算延误所在 link 的**加权 `up_chain_m`**。
   - 若延误坐落在**短通道**结构 ⇒ **拥堵被结构性地困住** ⇒ 支持「表达阻断传播」。
   - 若延误坐落在**长通道**结构 ⇒ 传播在结构上可能，阻断在别处 ⇒ 不支持。
3. **候选集位置**：E1 候选单元中，含主线 link 的比例（预期检验用户前提「真实瓶颈在快速路」是否成立）。

---

## 5. Verdict 规则（冻结，先于结果）

- **`SPILLBACK_CHANNEL_BLOCKED_BY_NETWORK_REPRESENTATION`** —— 当且仅当 **K1 断裂**（主线 `up_main_m ≥ 300 m` 的长度占比 < 50%）**或 K4 主轴碎化**（存在 `links/km > 40` 的快速路物理道路）。
- **`SPILLBACK_CHANNEL_INTACT__DELAY_TRAPPED_OFF_MAINLINE`** —— 当且仅当 **K1 通道完整**（≥300 m 占比 ≥ 80%）**且 K3 断点成立**（service∪connector 断点 ≥ 90%）**且 延误集中在断点子网络**。
- 否则 **`INDETERMINATE`**。

**红线（同 7.9B-1）**：**「结构上能传播」与「实际传播了」必须分开**。前者由静态拓扑证明；后者须有延误对账证据。⛔ **不得**用「延误更大」代替「通道判断」；⛔ **不得**为了得到某个 verdict 更换通道定义。

---

## 6. 反模式（禁止）

1. ⛔ 不做参数实验（C-1 **不**重跑仿真、**不**改 `f_cap`/`SCALE`/route-choice）。
2. ⛔ 不因 B-1「更堵」就采纳 KW；⛔ 不因 C-1 结论好看就调整 C-0 候选阈值。
3. ⛔ 不挑选让结论成立的通道定义；所有定义**对称施加**于五类对象。
4. ⛔ 不碰冻结件（`matsim_final_7_6h` / `matsim_viz_7_8` / `matsim_kw_7_9b1` 只读）。
5. ⛔ 不以「全网聚合量」（≈总车公里）作为空间判据。

---

## 7. 数据来源（全部只读）

| 用途 | 文件 |
|---|---|
| 网络拓扑 | `scripts/od/_cache_network_7_9c0.npz` |
| 单元映射 + 先验 | `scripts/od/_cache_link_unit_7_9b1.npz` |
| 候选/先验（E1） | `reports/structural_junction_cluster_audit_7_9c0/c0_junction_clusters.csv` |
| v1.0 延误 | `matsim_final_7_6h/.../W01_rc_min.19.linkstats.txt.gz` |
| KW 延误 | `matsim_kw_7_9b1/outputs/W01_kw/ITERS/it.19/W01_kw.19.linkstats.txt.gz` |
| 主窗 | `HRS8-9avg`（08–09，冻结主窗） |

---

*本判据在读取任何 7.9C-1 结果之前冻结；C-1 主判据为静态结构量，仿真延误仅用于第 4 节对账。*
