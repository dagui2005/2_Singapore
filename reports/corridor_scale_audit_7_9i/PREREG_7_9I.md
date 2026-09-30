# PREREG · Step 7.9I —— 观测域尺度与局部可达性诊断（零仿真）

> 冻结时间：2026-09-29（**运行任何分析脚本之前**）
> 冻结人：建模方
> 范围：**只读诊断**。⛔ 不改 v1.0、⛔ 不改 7.1/7.3.6A/OD/network/capacity、⛔ 不重跑 MATSim、⛔ 不新增/修改任何既有 prereg。
> 本 prereg 覆盖两个子阶段：
> * **7.9I-A** 走廊级容量加权比较（观测域尺度修正）
> * **7.9I-B** 133 个 M1 断面的可达性归因（局部可达性）

---

## 0. 立论来源（本阶段只做这两件事，不做第三件事）

上一轮 `7.9H` 已固化的两条事实，构成本阶段的唯一出发点：

1. **`0.434977` 不是答案**。7.9A-1 实测：容量按抽样率折减后 `Sim/Obs` 由 `0.9993348` → `0.7664761`（**方向相反**）。⇒ 这一条**从后续推理链中正式移除**，不得再作为"不堵"的解释。
2. **`0.766` 不能升级为"全网只有观测的 76.6%"**。靶场匹配边仅覆盖全网高峰流量的 **6.64%**（v1.0），且典型是 **1:many**（576 断面 → 3,037 条有向边；严格 1:1 仅 10.42%）。⇒ `Sim/Obs` 只能读作**靶场子集上的比较结果**。

因此本阶段回答两个**互相独立**的问题：

| 子阶段 | 问题 | 性质 |
|---|---|---|
| **7.9I-A** | 把比较搬到"流量占容量多少"的尺度上，sim 与 obs 之间**是否仍存在系统性偏差**？ | 比较口径问题 |
| **7.9I-B** | 那 133 个"真·低载"断面，为什么在 MATSim 中**真的没有形成对应流量**？ | 局部可达性问题 |

**⛔ 明确不做**：C（信号机制 / 绿信比折减）与 D（`trafficDynamics`）。理由：C 属**动力学机制问题**、D 已有 7.9B 实验基础且未形成干净证据链；现在做会把"比较尺度问题"与"动力学问题"混在一起。**只有 I-A + I-B 收敛后，才重谈是否进入 7.9J / signals。**

---

## 1. 冻结输入（逐位只读）

| 用途 | 路径 |
|---|---|
| LTA 观测（7.1 冻结） | `Singapore_OD_MATSim_FinalData/08_TrafficCount/TrafficFlow_Data.json`（经 `bt.load_traffic`） |
| crosswalk（7.3.6A 冻结） | `reports/od_final_calibration_crosswalk_7_3_6/final_calibration_crosswalk.csv`（经 `bt.normalize_crosswalk(..., "final")`） |
| 断面地理（7.6C 冻结） | `reports/od_structure_7_6c/section_geography.csv` |
| v1.0 linkstats | `matsim_final_7_6h/outputs/W01_rc_min/ITERS/it.19/W01_rc_min.19.linkstats.txt.gz` |
| A-1 linkstats | `matsim_sampling_capacity_7_9a1/outputs/A1_capf0p435/ITERS/it.19/A1_capf0p435.19.linkstats.txt.gz` |
| 网络拓扑/容量缓存 | `scripts/od/_cache_network_7_9c0.npz` |

**冻结常量**（回读断言，不得近似）：
* `SCALE = bt.SCALE = 2.298970`；`F_CAP = 0.434977`
* 断面数 **576**；crosswalk 行 **3,193**；匹配有向边 **3,037**
* canonical 池化比（**median 口径**）：v1.0 **`0.9993348`**、A-1 **`0.7664761`**
* canonical 池化比（**sum 口径**）：v1.0 **`4.1616`**、A-1 **`3.1384`**（7.9H `H2b`）
* 低比断面（v1.0，`median 口径 sim/obs < 0.50`）：**210**；其中 **M1 = 133**、**M2 = 77**

---

## 2. 口径定义（冻结）

### 2.1 指数与聚合

* `ff_s = LENGTH / FREESPEED`（**原始**；⛔ 不用 `ceil(ff)`）
* 有效容量 `cap_eff(e) = CAPACITY(e) × cap_mul`，`cap_mul = 1.0 (v1.0)｜0.434977 (A-1)`
  —— linkstats 的 `CAPACITY` 是**基础容量**，由 `_precheck_capacity_semantics.json` 实测（两版逐位相同）
* 断面级（canonical，不得替换）：`sim_sec = median{ HRS8-9avg(e) : e ∈ 匹配边(断面) } × SCALE`

### 2.2 走廊定义（7.9I-A）

* **走廊 = LTA 原始道路名 `RoadName`**（`obs` 侧字段；去首尾空白、大写归一后作为键）
* 走廊边集 `E_c` = 该走廊下**所有断面**的 `matsim_link_id` **并集（去重）**
* 三种分子口径**并报**（这是本阶段的核心，因为 1:many 会造成口径不对称）：
  * **`sim_flow_c^edge`** = `SCALE × Σ_{e∈E_c} HRS8-9avg(e)` —— **边级去重**（共享边只算一次）
  * **`sim_flow_c^sec`** = `SCALE × Σ_{断面 s∈c} Σ_{e∈E_s} HRS8-9avg(e)` —— **断面级累加**（与 obs 的"每断面各计一次"对称）
  * **`obs_flow_c`** = `Σ_{断面 s∈c} obs_8_9(s)`
* 分母（走廊级唯一）：**`cap_c = Σ_{e∈E_c} cap_eff(e)`**（边级去重），并同报 `cap_c^sec`（断面级累加）
* 派生量：
  * `Sim/Cap = sim_flow_c^sec / cap_c^sec`，`Obs/Cap = obs_flow_c / cap_c^sec`（**用同一分母**，保证可比）
  * `Residual_pp = 100 × (Sim/Cap − Obs/Cap)`
  * `ratio_simobs = sim_flow_c^sec / obs_flow_c`
  * `mapped_link_count = |E_c|`，`mapped_length_m = Σ_{e∈E_c} LENGTH(e)`

> **为什么主口径用 `^sec`**：`obs_flow_c` 是"断面各计一次"的累加，若分子用边级去重会引入系统性低估；故主口径两端都取"断面级累加"，边级去重作为**对照**并报。

### 2.3 M1 定义与分类（7.9I-B）

* `low` = 断面 `median 口径 sim/obs < 0.50`（v1.0）⇒ 210 节
* **`M1` = `low` 且 `sim_sum×SCALE < obs`**（"连 sum 口径也载不动"）⇒ **133 节**
* **`M2` = `low` 且 `sim_sum×SCALE ≥ obs`**（"median 塌陷"）⇒ **77 节**
* M1 逐断面**可达性诊断卡**字段（全部实测，不设默认值）：
  1. `n_edges` 匹配边数；`n_edges_flow_gt0`
  2. `sum_flow_xS`、`obs_8_9`、`sum_over_obs`
  3. `matched_components` 匹配边诱导子图的弱连通分量数
  4. `directed_breaks` 匹配边有向链断裂数（无后继且无前驱的边数）
  5. `n_dangling_endpoints` 端点中度数 = 1 的个数
  6. `all_endpoints_in_giant` 端点是否全部落在**网络最大弱连通分量**
  7. `min_hop_to_hot` 从匹配边端点到"高流量边端点"的**最小无向跳数**（`hot` = `HRS8-9avg ≥ 500`；一次多源 BFS）
  8. `bypass_flow_within_300m` 断面中点 300 m 内、**同 `RoadCat` 大类**、**非匹配边**、`HRS8-9avg ≥ 500` 的边流量合计
  9. `dir_diff_median` 匹配边的 crosswalk `direction_diff_deg` 中位
  10. `highway_set` / `name_has_special`（`TUNNEL/EXPRESSWAY/FLYOVER/HIGHWAY/VIADUCT/PIE/CTE/KPE` 等）
* **分类（固定优先级，先命中先归类；全部分类必须可被 1–10 号原始字段复算）**：
  * `M1-C_TOPOLOGY_DISCONTINUOUS`：`matched_components > 1` **或** `directed_breaks > 0`
  * `M1-D_DIRECTION_ERROR`：`dir_diff_median > 30`
  * `M1-E_SPECIAL_FACILITY`：`name_has_special` **或** `highway ∈ {motorway, motorway_link, trunk, trunk_link}`
  * `M1-B_PARALLEL_BYPASS`：`bypass_flow_within_300m ≥ 0.5 × obs_8_9`
  * `M1-A_REAL_LOW_DEMAND`：以上皆不命中
* **判读纪律**：分类是**诊断标签**，不是"结论"。必须同报每一类的**节数 / `Σobs` / `Σsim×SCALE` / 占比**，且**任一类的 `Σobs` 占比 < 5% 时该类的均值不得单独解释**（防"子类符号相反 ⇒ 均值抵消伪影"）。

---

## 3. 硬门（全部在**产物写盘后**算一次；任一门失败 ⇒ 整体 BLOCKED）

| 门 | 判据 | 期望 |
|---|---|---|
| `G-A1` | `SCALE` / `F_CAP` 回读逐位 | `2.29897` / `0.434977` |
| `G-A2` | 断面数 / crosswalk 行 / 匹配边数 | `576 / 3193 / 3037` |
| `G-A3` | **canonical 池化比复现**（median 口径） | v1.0 `0.9993348`、A-1 `0.7664761`（±1e-6） |
| `G-A4` | **聚合敏感性复现**（sum 口径） | v1.0 `4.1616`、A-1 `3.1384`（±5e-4） |
| `G-A5` | obs 分配守恒：`Σ_c obs_flow_c == Σ_sections obs_8_9` | 逐位相等；未被任何非空 `RoadName` 收走的断面数 = **0** |
| `G-A6` | 走廊边集去重自洽：`Σ_c |E_c| ≥ 3037` 且 `|∪_c E_c| == 3037` | 成立 |
| `G-A7` | 覆盖率复现：匹配边高峰流量占比 | v1.0 `0.0664`、A-1 `0.0529`（±1e-4） |
| `G-B1` | M1 / M2 计数复现 | `133 / 77` |
| `G-B2` | 分类覆盖：五类计数之和 == 133；**无未分类** | 成立 |
| `G-B3` | 拓扑基础量自洽：最大弱连通分量规模、`Σ` 度数 == 2×边数 | 成立 |
| `G-N` | **负例门**（每个脚本 ≥3 个）：故意篡改输入，**必须**产生可观测的不同结果；若某负例与真值**逐位相同** ⇒ 该门 FAIL | 全部 `fired=True` |

**产物**（全部落 `reports/corridor_scale_audit_7_9i/`）：
`corridor_scale_{v10,A1}.csv`、`corridor_scale_summary.json`、`m1_cards_7_9ib.csv`、`m1_class_summary.json`、`_corridor_audit_7_9ia.json`、`_m1_audit_7_9ib.json`、`STEP7_9I_REPORT.md`

---

## 4. 可证伪条件（本阶段**可能被推翻**的表述）

* 若 `Obs/Cap` 与 `Sim/Cap` 在走廊级**几乎重合**（池化 `|Residual_pp| < 2 pp` 且走廊符号随机）⇒ 则先前所有"快速路被低估"的读数**全部是尺度错配伪影**，须整体改写。
* 若 M1 中 `M1-A_REAL_LOW_DEMAND` 合计 `Σobs` 占比 **< 5%** ⇒ 则"真·低载"这一命名**不成立**，须改称"结构性映射失配"。
* 若 M1 中 `M1-C + M1-D` 合计节数 **> 60%** ⇒ 则主因是**映射拓扑缺陷**，与需求/容量无关，后续应优先修 crosswalk 而非动力学。

---

## 5. 纪律留痕

* 本 prereg **运行前冻结**；运行后**不得**修改判据、阈值、分类优先级。
* ⛔ 不改 `PREREG_7_9A1.md`；⛔ 不新立与既有 prereg 冲突的判据。
* 所有"汇总数字"必须由**逐条记录**可复算；⛔ 不得硬编码符号（凡"判据+实测"同行必动态渲染）。
* `pandas 3.0`：`groupby.apply` 口径有歧义 ⇒ 一律**显式循环**；`astype(str)` 会把 NaN 存成 `"nan"` ⇒ 先 `fillna` 或用 `pd.Series(...).astype(str)` 后 `.str.strip()`。
* 产物/对照物回读一律 `float_precision="round_trip"`（默认会丢 1 ulp）。
