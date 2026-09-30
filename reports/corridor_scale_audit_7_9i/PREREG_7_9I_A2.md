# PREREG · Step 7.9I-A2 —— KPE / ECP 实体定义核验（零仿真）

> 运行前冻结。判据与阈值一经写入不得运行后修改；若事后发现判据缺陷，
> 必须**披露 + 加后验修订分类**（标签 `EXPLORATORY_POST_HOC`），**阈值一律不改**（`PREREG_7_9I §4` 纪律）。

---

## 0. 立论与范围

7.9I-A 给出**去尺度残差** `norm = ratio_simobs / K_c`，并把 `norm<0.5` 的 19 条走廊判为
「真实缺载」，其中前 3 条（KPE 隧道 0.117 / ECP 0.132 / KPE 0.119）担 `Σobs` 的 **22.42%**。

但 `norm` 的成立**隐含一个前提**：
> 一个 LTA 断面对应的 K 条 MATSim 边**承载同一股车流**（连续有向链）⇒ 断面级累加放大 K 倍 ⇒ 须除以 K。

若这 K 条边实为**平行对象**（不同车流），则「除以 K」会**人为制造出并不存在的缺载**。

本步（A2）**零仿真**回答两个问题：

- **Q1**：KPE 隧道 / ECP / KPE 的 LTA 断面**代表什么物理对象**？其观测值与该对象的
  模型表征是否为**同一测量单元**？
- **Q2**：这三条走廊的「真实缺载」在**不除以 K** 的口径下还剩多少？即 `norm` 是
  **真实缺载**还是**除以 K 造成的伪缺载**？

⛔ 本步**不改** 7.1 / 7.3.6A / OD / network / capacity / prereg / 阈值；**不重跑 MATSim**；
⛔ **不改冻结靶场**（发现靶场伪影 ≠ 允许改靶场）；⛔ **不把 expanded residual 回写 target**。

---

## 1. 冻结输入（只读）

| 角色 | 路径 |
|---|---|
| 冻结 crosswalk（7.3.6A） | `reports/od_final_calibration_crosswalk_7_3_6/final_calibration_crosswalk.csv` |
| LTA 观测（含几何/方向） | `Singapore_OD_MATSim_FinalData/08_TrafficCount/TrafficFlow_Data.json` |
| 断面地理（7.6C） | `reports/od_structure_7_6c/section_geography.csv` |
| MATSim 网络缓存 | `scripts/od/_cache_network_7_9c0.npz` |
| linkstats v1.0 | `matsim_final_7_6h/outputs/W01_rc_min/ITERS/it.19/W01_rc_min.19.linkstats.txt.gz` |
| 7.9I-A 断面表 | `reports/corridor_scale_audit_7_9i/section_scale_v10.csv` |
| 7.9I-B 诊断卡 | `reports/corridor_scale_audit_7_9i/m1_cards_7_9ib.csv` |

**回读常量（逐位必须复现）**

| 量 | 值 |
|---|---|
| `SCALE` | 2.29897 |
| KPE 隧道 `Σobs` / `n_sections` / `matched_edges` | 230,267.5 / 19 / 67 |
| ECP `Σobs` / `n_sections` / `matched_edges` | 93,818.0 / 47 / 283 |
| KPE `Σobs` / `n_sections` / `matched_edges` | 15,362.0 / 3 / 16 |
| KPE 隧道 `norm` / ECP `norm` / KPE `norm` | 0.117223 / 0.131760 / 0.119084 |
| KPE 隧道 `ratio_simobs_med`（canonical） | 0.096581 |

---

## 2. 方法

### 2.1 观测单元核验（Q1）

对每个断面 `s`：

- `len_s`：由 LTA `Start/EndLon/Lat` 计算（等距圆柱近似，λ 按断面纬度取 `cosφ`）。
- `bear_s`：断面有向方位角。
- `opp_pair_s`：是否存在**反向成对断面**（中点距离 `< 60 m` 且方位差 `|Δbear−180°| < 30°`）⇒ 判定「双向 bore」。
- **容量可承受性**：
  - `cap_edge_mean = cap_eff_sum / n_edges`（匹配边平均容量）
  - `cap_edge_max  = max_e cap_eff(e)`（匹配边最大容量）
  - `vc_mean = obs_8_9 / cap_edge_mean`，`vc_max = obs_8_9 / cap_edge_max`

**判据 U（观测单元 ≠ 仿真单元）**：`vc_max > 1.0`
⇒ **即使拿容量最大的那条匹配边，也装不下观测值** ⇒ LTA 的「断面」不可能是
与一条有向 MATSim 边同量纲的单向断面流量。

### 2.2 半径设施重建（Q1 辅助）

对走廊 `c`，半径 `R ∈ {50, 100, 150} m`：
`F_R(c) = SCALE × Σ_{e ∈ M_R} HRS8-9avg(e)`，`M_R` = 与任一断面中点距离 `< R`
且 `highway ∈ {motorway, motorway_link, trunk, trunk_link}` 的边（去重）。
对照 `F_matched(c) = SCALE × Σ_{e ∈ matched}`（= `sim_flow_edge`）。

判据 **P（crosswalk 选中低流量子集）**：`F_matched < 0.5·Σobs` 且 `F_50m ≥ 1.5·F_matched`。

### 2.3 链 vs 平行（Q2，决定 `norm` 是否合法）

对断面的匹配边集 `E_s`（有向图 `G` = 全网 421,406 节点 / 693,575 有向边）：

- `n_comp_s`：`E_s` 的**弱连通分量数**
- `chain_break_s`：有向链断裂数（`v ∉ set(frm)` 且 `u ∉ set(to)`）
- **`is_chain_s` = `n_comp_s == 1` 且 `chain_break_s == 0` 且 `n_edges_s ≥ 2`**

**判据 C（链 ⇒ 除以 K 合法）**：`is_chain_s`
**判据 P2（平行/断裂 ⇒ 除以 K 非法）**：非 `is_chain_s`

三种比较口径并报：

| 口径 | 公式 | 适用 |
|---|---|---|
| `r_med`（canonical） | `SCALE·median_e flow_e / obs` | 链（同股车流取代表值） |
| `r_edge`（设施级） | `SCALE·Σ_{e∈E_c} flow_e / obs` | 平行（不同车流可加） |
| `r_norm`（7.9I-A） | `r_sec / K_c` | **仅当**链成立 |

### 2.4 分类（单标签，固定优先级）

| 标签 | 条件 |
|---|---|
| `U_UNIT_MISMATCH` | `vc_max > 1.0` |
| `S_SLIP_GEOM` | `RoadCat == SLIP_ROAD` 或全部匹配边 ∈ `*_link` |
| `C_CHAIN` | `is_chain_s` |
| `P_PARALLEL` | 非链 且 `n_comp_s > 1` 或 `chain_break_s > 0` |
| `N_PLAIN` | 其余 |

---

## 3. 硬门

| 门 | 断言 |
|---|---|
| `G-A2-1` | 三走廊 `Σobs` / `n_sections` / `n_matched_edges` 逐位复现 §1 常量 |
| `G-A2-2` | 三走廊 `norm` 复现 0.117223 / 0.131760 / 0.119084（`atol=1e-6`） |
| `G-A2-3` | KPE 隧道 `ratio_simobs_med` 复现 **0.096581** |
| `G-A2-4` | 每个断面均被分类且标签 ∈ 命名集（无 NaN / 无未覆盖） |
| `G-A2-5` | `Σ_e∈matched cap_eff` 与 `section_scale_v10.cap_eff_sum` 逐位一致 |
| `G-A2-6` | 反向成对检测非退化：三走廊成对断面数 ∈ [0, n_sections)（不是 0 也不是全部） |
| `G-A2-7` | 半径重建单调：`F_50 ≤ F_100 ≤ F_150`（逐走廊） |
| `G-N` | 负例套件全部 `fired=True`（见 §5） |

---

## 4. 可证伪条件

1. 若三走廊**没有任何**断面满足 `vc_max > 1`，则「观测单元 ≠ 仿真单元」**不成立**，
   本步必须改判为「KPE/ECP 的低 norm 是真实缺载」。
2. 若 `r_edge`（不除以 K）与 `r_norm` 差异 `< 15%`，则 `norm` 与设施级口径**同源**，
   「除以 K」不改变结论 ⇒ 7.9I-A 的缺载判定**不需要修正**。
3. 若 KPE 隧道匹配边**全部** `is_chain_s == True`，则「选错对象」不成立，
   `norm=0.117` 应被接受为真实缺载。

---

## 5. 负例（必须真改变可观测结果，且**非同构**）

| 编号 | 扰动 | 期望 |
|---|---|---|
| `N1_shuffle_obs` | 把容量可承受性分子（obs）随机重排到断面 | `fired` |
| `N2_cap_uniform` | 令所有匹配边 `cap_eff = 1.0` | `fired` |
| `N3_shift_section_mid` | 断面中点整体 `+500 m`（改变半径成员） | `fired` |
| `N4_permute_edge_to_section` | 把匹配边随机重接到别的断面（改变链/分量结构） | `fired` |
| `N5_reverse_all` | **记录项**：整体反向对无向分量/成对检测**不变**（同构）⇒ 不设门 | 记录 |

---

## 6. 纪律留痕

- 门禁**必携带实测值**；`checks` 只在全部产物写盘后算一次。
- 负例必须**非同构扰动**（整体位移 / 整体反向 = 同构 ⇒ 必 `fired=False`，不作为有效门）。
- 每个 Edit 后必 grep 断言；长段改写用 `.py` + `assert`。
- 本步结论**不得**用于调整 v1.0 的交通动力学参数。
