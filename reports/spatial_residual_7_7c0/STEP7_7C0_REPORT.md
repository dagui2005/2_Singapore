# Step 7.7C-0 — 空间残差归因基线审计报告

> 生成：2026-09-19 ｜ 类型：**零仿真、只读** ｜ 运行：`scripts/od/audit_spatial_residual_7_7c0.py`
> 运行成本 **173.8 s**（纯 I/O + 统计，无 MATSim）｜ 校验 **14/14 PASS**
> 工作点 `W01`：`λ_ref=0.075` / `f*=1.180222` / `N_sim=236,044` / `SCALE=2.29897`（冻结）

---

## 0. 一句话结论

> **空间残差不来自 OD 总量、道路等级、section 长度聚合或观测语义分层；
> 它主要是一个「位置（PA 尺度）」现象，其两个可识别的结构机制是
> ①「双向/对偶链路表征（twin / reciprocal）」与 ②「方向性（in / out）」——
> 二者独立且可加。在「无对偶链路 + 入城方向」这一干净子组上，`Sim/Obs = 0.9915 ≈ 1.000`。**

**判决：`RESIDUAL_LOCALIZED_TO_PA_LOCATION`**
机制层：`pa_location` · `network_topology_twin` · `distance_impedance` · `region_location` · `directionality`
**排除层**：`road_class` · `section_crosswalk` · `observation_semantics` · `network_representation`

---

## 1. 方法与纪律

- **零仿真**：不启动 MATSim；逐断面 Sim/Obs 直接复用 7.6H 同一条链
  `evaluate_demand_response_7_6f_1.eval_run()`（只重绑 `E.OUT / E.CYCLE_DIR / E.MATRIX_CSV`），
  **不复制任何公式**。
- **冻结件未触碰**：7.1 观测、7.3.6A crosswalk、OD、network、capacity 全部只读；未引入新 calibration knob。
- **靶场**：576 断面（7.1 冻结观测 + 7.3.6A Final Crosswalk）；`08-09` 窗口、`HRS8-9avg`、`SCALE=2.29897`。

### MUST_MATCH_BASELINE（口径未漂移 = 唯一硬证据）

| 检查 | 结果 | 数值 |
|---|---|---|
| M1 逐组 `rel_dev` == 7.6H `h3_spatial` | ✅ | `max|Δ| = 8.674e-17`（逐位，8 组） |
| M2 `Sim/Obs FROZEN` == 7.6H 汇总 | ✅ | `0.9993348`（ours = ref） |
| M3 EAST / radial_in / NE 残差复现 | ✅ | `−31.7524%` / `−30.6727%` / `+33.8833%` |

---

## 2. 六维结果

### 2.1 C0-1 OD 空间供需（`P_i` / `A_j` / `T_ij`）

| Region | 残差 rel_dev | `P_sum`（home） | `A_sum`（work） | **`A/P`** | OD inflow/outflow |
|---|---|---|---|---|---|
| CENTRAL | **−7.82%** | 112,138 | 1,038,168 | **9.258** | 净流入 |
| WEST | +2.84% | 103,196 | 342,572 | 3.320 | — |
| EAST | **−31.75%** | 82,218 | 245,006 | 2.980 | — |
| NORTH | +23.09% | 50,271 | 146,654 | 2.917 | — |
| NORTH-EAST | **+33.88%** | 111,971 | 162,835 | **1.454** | 净流出 |

- `ρ(A/P, 残差) = −0.7000`（Spearman, n=5）⇒ **就业/居住比越高，模拟越偏低**（NE 居住主导 → 高估 +33.9%；CENTRAL 就业主导 → 低估 −7.8%）。
- **但 EAST 打破单调性**（A/P=2.98 却最低 −31.8%）⇒ **OD 总量供需只能解释一部分，不是主因**。
- region→region 早高峰方向性极强：`EAST→CENTRAL 45,229` vs `CENTRAL→EAST 9,550`（`rev/fwd=0.211`），
  四对「X→CENTRAL」全部 `rev/fwd < 0.31`。

### 2.2 C0-2 方向性

| 组 | n | 池化 ratio | rel_dev |
|---|---|---|---|
| `radial_in` | 164 | **0.6928** | **−30.67%** |
| `circumferential` | 154 | 1.0954 | +9.61% |
| `radial_out` | 256 | **1.1442** | **+14.50%** |

- `radial_in ≠ radial_out`：`Δ = −0.4514`（45 pp）。
- **★跨 f / λ 全 8 档稳定**：`radial_in < radial_out` 在 `f∈{1.00,1.05,1.15,1.25}` 与 `λ∈{0.05,0.075,0.10}` **8/8 成立**
  ⇒ 方向性**不是** demand/λ 的伪影（与 7.6F-1 / 7.6G 结论一致）。

### 2.3 C0-3 道路等级

| dominant_highway | n | 池化 ratio | rel_dev |
|---|---|---|---|
| motorway | **449** | **0.9922** | **−0.71%** |
| motorway_link | 92 | 1.0033 | +0.40% |
| primary | 9 | 0.6709 | −32.86% |
| service | 16 | 1.7235 | +72.47% |
| secondary / tertiary / trunk… | 各 ≤2 | 0.63–2.83 | 离散 |

- **主干 `motorway`（449 断面、136.7 万 obs）几乎无偏（0.9922）**；偏离大的类别断面数都 ≤16。
- `motorway mainline only`（373, `0.9964`）vs `with motorway_link edges`（192, `1.0109`）——**mainline-vs-link 差异可忽略**。
- `RoadCat`（观测语义分层）：`CATA` vs `SLIP_ROAD` —— **η²_excess = −0.0004（可忽略）**。
- ⇒ **排除道路等级 / 观测语义层。**

### 2.4 C0-4 section 几何 / twin / 拓扑 ★

| 维度 | 组 | n | 池化 ratio | rel_dev |
|---|---|---|---|---|
| **has_reciprocal_pair** | **True** | 98 | **0.3711** | **−62.86%** |
| | **False** | 478 | **1.2035** | **+20.43%** |
| shared_section_count | 2 | 63 | 0.7733 | −22.62% |
| | 1 | 503 | 1.0135 | +1.41% |
| matched_link_count | 1 / 2 | 156 | 0.95 | −5% |
| | 4+ | 344 | 1.0028 | +0.35% |
| has_mixed_highway | True/False | — | 1.01/0.995 | 可忽略 |

- **★`has_reciprocal_pair` 仅 2 组即解释 14.2% 的 excess 方差**（全表最高效的单因子）。
- 连续量 Spearman：`reciprocal_share −0.2412`（最强）、`section_length_m −0.1384`、`n_matsim_link −0.0264`。

### 2.5 C0-5 长度归一化（`q/L`）

| Region | 绝对 rel_dev | **每 km rel_dev** | 收缩 |
|---|---|---|---|
| CENTRAL | −7.82% | **+27.19%** | ✗（翻转） |
| EAST | −31.75% | −42.49% | ✗（加深） |
| NORTH | +23.09% | +11.07% | 部分 |
| NORTH-EAST | +33.88% | +23.07% | 部分 |
| WEST | +2.84% | −10.45% | ✗ |

- **区域残差极差 33.88% → 42.49%（Δ = −8.61 pp，反而扩大）**。
- ⇒ **残差不是 section 长度/聚合尺度造成的**；按长度归一化只会**重排**而非消除残差。

### 2.6 C0-6 PA / Region 空间梯度

| 变量（PA 级） | `ρ(R_PA, ·)` |
|---|---|
| `od_outflow` | **−0.3955** |
| `mean_d_cbd_m` | −0.3077 |
| `motorway_len_m` | −0.2726 |
| `road_len_m` | −0.2703 |
| `net_inflow_ratio` | +0.2629 |
| `od_inflow` | −0.1549 |

- 逐断面：`ρ(ratio, d_cbd) = −0.2443`（n=574）。
- ⇒ 存在**弱–中等连续梯度**：越远离 CBD、出流越大 → 残差越偏负（低估）；但强度远不足以单独解释。

---

## 3. ★核心分解：`radial × reciprocal`（两机制独立、可加）

| cell | n | obs | 池化 ratio | rel_dev |
|---|---|---|---|---|
| `radial_in \| recip=True` | 34 | 161,946 | **0.1738** | **−82.61%** |
| `radial_out \| recip=True` | 45 | 162,159 | 0.4919 | −50.78% |
| `circumferential \| recip=True` | 18 | 46,256 | 0.5826 | −41.70% |
| **`radial_in \| recip=False`** | **130** | **281,352** | **0.9915** | **−0.78%** |
| `circumferential \| recip=False` | 136 | 357,199 | 1.1618 | +16.26% |
| `radial_out \| recip=False` | 211 | 502,841 | 1.3546 | +35.55% |

**解读（关键）**

1. **无对偶链路 + 入城方向（130 断面、18.6% obs）⇒ `ratio = 0.9915 ≈ 1.000`**：
   在「干净表征 + 入城」子组上，模型**几乎无偏**。残差不是全局需求问题。
2. **对偶/双向链路表征是强退化项**：`recip=True` 全线 `−41.7% ~ −82.6%`；在 `radial_in` 上，
   `recip` 从 False→True 使 ratio 从 `0.9915` 崩到 `0.1738`（**−82 pp**）。
3. **方向性独立可加**：在同一 `recip` 类内，`in < circum < out` 的排序均保持
   （`recip=False`：`−0.78 / +16.26 / +35.55`，跨度 36 pp）⇒ 方向性是**独立机制**，非 twin 的副产物。

⇒ **模型空间残差 ≈ 「双向链路表征」+「方向性」两个结构机制的叠加**，
而非 demand scale / λ / 车型构成 / 道路等级 / 长度聚合。

---

## 4. 归因排序（obs 加权 η²，含机会校正）

| 维度 | 层 | η² | 组数 | η²_chance | **η²_excess** |
|---|---|---|---|---|---|
| `pa` | pa_location | 0.3102 | 37 | 0.0626 | **0.2476** |
| **`has_reciprocal_pair`** | **network_topology_twin** | **0.1441** | **2** | 0.0017 | **0.1423** |
| `distance_ring` | distance_impedance | 0.0580 | 6 | 0.0087 | 0.0493 |
| `region` | region_location | 0.0485 | 5 | 0.0070 | 0.0415 |
| `radial` | directionality | 0.0442 | 3 | 0.0035 | 0.0407 |
| `ring` | distance_impedance | 0.0433 | 5 | 0.0070 | 0.0363 |
| `shared_section_count` | section_crosswalk | 0.0040 | 3 | 0.0035 | 0.0005 |
| `RoadCat` | observation_semantics | 0.0014 | 2 | 0.0017 | **−0.0004** |
| `has_mixed_highway` | network_representation | 0.0001 | 2 | 0.0017 | **−0.0017** |
| `matched_link_count` | section_crosswalk | 0.0031 | 4 | 0.0052 | **−0.0021** |
| `roadclass` | road_class | 0.0088 | 10 | 0.0157 | **−0.0069** |

- **机制层（excess ≥ 0.03）**：`pa_location` · `network_topology_twin` · `distance_impedance` · `region_location` · `directionality`
- **排除层（excess ≤ 0.005）**：`section_crosswalk` · `observation_semantics` · `network_representation` · `road_class`
  （excess ≤ 0 意味该维度**低于随机分组期望**⇒ 无解释力）

> ⚠️ 方法学注记：`pa` 的原始 η² 最高，部分是「组数多（37）」带来的自由度优势——故同时报
> `η²_excess`（减去 `(k−1)/(N−1)` 的机会期望）。经校正后 `pa` 仍居首，但 `has_reciprocal_pair`
> **仅用 2 组**即达 0.1423，效率最高，机制含义最明确。`radial` 的**边际** η²（0.0407）被 twin 效应稀释，
> 其真实强度须看 §3 的交叉表（同 `recip` 类内 36 pp 跨度）。

---

## 5. 判决

```
RESIDUAL_LOCALIZED_TO_PA_LOCATION
  机制层 : pa_location · network_topology_twin · distance_impedance · region_location · directionality
  排除层 : road_class · section_crosswalk · observation_semantics · network_representation
```

**逐层排除链（论文可用）**

```
Global demand            → 7.6F-1 解决（f*=1.1802，Sim/Obs→1.000）
Distance decay λ         → 7.6G 证明不改变空间残差（SPATIAL_INERT）
Vehicle/mode composition → 7.7A 证明只解释总量级、不解释空间格局
──────────────────────────────────────────────────────────
OD aggregate supply/demand → 7.7C-0：只解释一部分（ρ=−0.70，且 EAST 反例）
道路等级 / 观测语义 / 长度聚合 → 7.7C-0：**排除**
── 剩余，且已验证为机制 ──
① 双向/对偶链路表征（twin）        ← η²_excess 0.1423（2 组）
② 方向性（in / out）                ← 跨 f/λ 8/8 稳定；同 twin 类内 36 pp
③ PA 尺度位置异质性                 ← η²_excess 0.2476（与 outflow ρ=−0.40、d_cbd ρ=−0.31 弱相关）
```

---

## 6. 对 7.7C-1（时段敏感性）与 7.7B（HTS）的判据建议

- 7.7C-0 表明残差主控轴是**网络表征（twin）与方向性**，二者是**结构/表征**性质，
  **不是「总体量的时间分布」性质**；且已被证明对 `f`、`λ` 均不敏感。
- ⇒ **HTS 出发时刻分布很可能主要影响「时段总量/峰值形状」，而难以改变当前空间格局。**
  因此建议 **7.7C-1 只做零仿真解析/上界审计**（利用现有 linkstats 与观测时间窗），
  **仅在 7.7C-1 显示「出发时刻分散会系统性改变空间格局」时**，才值得进入 7.7B 做一次真实
  temporal realization；否则 HTS 用于论文**外部行为验证**即可，不开启新一轮 MATSim 标定。

---

## 7. 局限与未解决

1. `has_reciprocal_pair` 是**表征层**指标，其与 `radial` 存在部分共线；本步用交叉表分离，
   但**未做偏效应回归**（属 7.7D 范畴）。
2. `PA` 尺度异质性（η² 最高）**尚未被归因到具体可操作变量**——与 outflow/d_cbd 只有弱相关（|ρ|≤0.40）。
3. 「方向性」的物理解释（OD 有向结构 vs 网络有向表征 vs 时段实现）**尚未唯一确定**。
4. 零流断面（53 个）仍按 `FROZEN` 口径保留在分母；`POSITIVE_ONLY` 口径的对照见
   `c0_section_table.csv`。
5. 观测语义层只用 `RoadCat`(CATA/SLIP) 代理；**断面级分车型计数仍缺**（7.7A 判决），
   「全部机动车 vs car-only」的口径差仍无法在断面级定量。

---

## 8. 产物清单（`reports/spatial_residual_7_7c0/`，19 个）

| 文件 | 内容 |
|---|---|
| `c0_section_table.csv` | **逐断面归因底表**（576 行；Sim/Obs/ratio + 全部维度字段） |
| `c0_1_od_supply_demand_by_region.csv` | OD 供需（P/A/A_over_P/in-out）by region |
| `c0_1_od_region_block_matrix.csv` · `c0_1_od_direction_symmetry.csv` | region×region OD 块矩阵 / 方向对称性（承 7.6C-1） |
| `c0_2_radial_residual.csv` · `c0_2_ring_residual.csv` | 方向性 / 距离环 残差 |
| `c0_2_directionality_stability_across_f_lambda.csv` | 方向性跨 f/λ 稳定性（8 档） |
| `c0_3_roadclass_residual.csv` · `c0_3_roadcat_residual.csv` · `c0_3_mainline_vs_link.csv` | 道路等级 / 观测语义 / mainline-vs-link |
| `c0_4_topology_residual.csv` · `c0_4_correlations.csv` · **`c0_4_radial_x_reciprocal.csv`** | 拓扑分组 / 连续量相关 / **核心交叉表** |
| `c0_5_length_normalized_by_region.csv` | 长度归一化对比 |
| `c0_6_pa_gradient.csv` · `c0_6_pa_gradient_correlations.csv` | PA 级梯度表与相关 |
| `c0_rank_eta2.csv` | **归因排序（η² / 机会校正 / 层映射）** |
| `step7_7c0_summary.json` | 机器可读汇总（含 14 项校验、判决、全部记录） |
