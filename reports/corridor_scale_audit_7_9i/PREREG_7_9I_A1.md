# PREREG · Step 7.9I-A1 —— 60 个链缺陷断面的连续有向链重聚合（零仿真）

> 运行前冻结。若事后发现判据缺陷，必须**披露 + 加后验修订分类**（`EXPLORATORY_POST_HOC`），
> **阈值一律不改**（`PREREG_7_9I §4` 纪律）。

---

## 0. 立论与范围

7.9I-A2 已证明 `norm = r_sum / K_c` **在链不成立时非法**，且 `r_med`（canonical）
在**零流边占多数**时塌为 0（如 KPE 隧道 49684：9 边中 6 条零流 ⇒ median=0）。

本步**不换更漂亮的统计量**，而是先**恢复「一个 LTA 断面对应的物理交通链」**：

```
LTA section → candidate MATSim links → 按拓扑连续性筛选
            → 连续、有方向的 chain → chain flow / chain capacity → 与 LTA section 比较
```

**目标集**：7.9I-B 判为 `X1_CHAIN_DEFECT` / `M1-C_TOPOLOGY_DISCONTINUOUS` 的 **60 个断面**。

⛔ 零仿真、只读；不改 v1.0 / 交叉表 / 靶场；**不得**用本步结论调动力学参数。

---

## 1. 冻结输入

| 角色 | 路径 |
|---|---|
| 冻结 crosswalk | `reports/od_final_calibration_crosswalk_7_3_6/final_calibration_crosswalk.csv` |
| LTA 观测与几何 | `Singapore_OD_MATSim_FinalData/08_TrafficCount/TrafficFlow_Data.json` |
| 断面地理 | `reports/od_structure_7_6c/section_geography.csv` |
| 网络缓存 | `scripts/od/_cache_network_7_9c0.npz` |
| linkstats v1.0 | `matsim_final_7_6h/…/it.19/W01_rc_min.19.linkstats.txt.gz` |
| 7.9I-B 诊断卡 | `reports/corridor_scale_audit_7_9i/m1_cards_7_9ib.csv` |

**回读常量**：目标集 = 60；`SCALE = 2.29897`；网络 421,406 节点 / 693,575 有向边。

---

## 2. 方法

### 2.1 候选池（两级，并报）

- **P0（crosswalk）**：该断面的匹配边集 `E_s`。
- **P1（拓扑扩展）**：`E_s ∪ { e : d(mid_e, mid_s) < 100 m 且 highway ∈ MAJOR }`。

### 2.2 方向过滤

`bear_e = atan2(Δy, Δx)`（SVY21 节点坐标）；`bear_s` 由 LTA `Start/EndLon/Lat` 计算。
保留 `|Δbear| < DIR_BAD = 30°`（环形差）。

### 2.3 连续有向链构建

在候选子图上（边 `u→v` 与 `v→w` 相接）：

1. **起点集** = 无「候选入边」的节点 ∪ 所有候选边起点。
2. 从每个起点**沿出边唯一延续**（若有多条出边，取 `HRS8-9avg` 最大者）；
   遇到已访问边、无出边或链长 >40 即停。
3. 对称地向后延伸（无「候选入边」以外不再回溯）。
4. 链去重（`frozenset(edge_ids)`）；**打分**：`(含匹配边, −|mid_chain − mid_section|, chain_len_m)` 取最优。

### 2.4 链级比较量

| 量 | 定义 |
|---|---|
| `chain_flow_xS` | `SCALE × median_{e∈chain} HRS8-9avg(e)` |
| `chain_cap` | `median_{e∈chain} CAPACITY(e)`（**基础容量、不缩放**，与 canonical 一致） |
| `chain_len_m` | `Σ_e LENGTH(e)` |
| `r_chain` | `chain_flow_xS / obs_8_9` |
| `vc_chain` | `median_{e∈chain} HRS8-9avg(e) / chain_cap` |
| `r_med`（基线） | `sim_median_xS / obs_8_9` |

### 2.5 判据

- **`C_OK`**：`|r_chain − 1| < 0.25` ⇒ 链口径下**该断面已被解释**（不构成缺载）。
- **`C_LOW`**：`r_chain < 0.75` ⇒ 链口径下**仍缺载**。
- **`C_HIGH`**：`r_chain > 1.25` ⇒ 链口径下**高估**。

---

## 3. 硬门

| 门 | 断言 |
|---|---|
| `G-A1-1` | 目标集 = **60**（`class_exploratory == X1_CHAIN_DEFECT`） |
| `G-A1-2` | 60 断面 `Σobs` 复现 7.9I-B 的 `Σobs`（obs 加权 69.2% 口径） |
| `G-A1-3` | 每断面均找到链（`chain_edges ≥ 1`），无 NaN |
| `G-A1-4` | 链内**所有**边的方向与断面差 `< DIR_BAD`（构造性断言） |
| `G-A1-5` | 链**拓扑连续**：`e_i.to == e_{i+1}.frm` 逐对成立（构造性断言） |
| `G-A1-6` | P1 候选池 ≥ P0 候选池（逐断面，单调） |
| `G-A1-7` | 链口径与 canonical 口径**不同源**：`|r_chain − r_med|` 中位 > 5%（非退化） |
| `G-N` | 负例 4 个有效门全 `fired` |

---

## 4. 可证伪条件

1. 若 **`r_chain` 与 `r_med` 差异中位 < 5%**，则链重建**不改变结论** ⇒ A1 无信息量，
   应回到 A2 的 `r_mixed`。
2. 若 `C_OK` 占比 **≥ 90%**，则 60 个链缺陷断面**基本可被链口径解释** ⇒ 支持
   「缺载主要是尺度/对象问题」。
3. 若 `C_LOW` 占比 **≥ 50%**，则链口径下**仍大面积缺载** ⇒ 必须回到需求/网络层面，
   且**不得**再归因于尺度。

---

## 5. 负例（非同构扰动）

| 编号 | 扰动 | 期望 |
|---|---|---|
| `N1_shuffle_chain_flow` | 随机重排每断面的 `chain_flow_xS` | `fired` |
| `N2_zero_cap` | 令 `chain_cap = 1.0` | `fired` |
| `N3_shift_mid` | 断面中点整体 `+400 m`（改变候选池） | `fired` |
| `N4_drop_direction_filter` | 关闭方向过滤（DIR_BAD = 180°） | `fired` |
| `N5_reverse_all` | 整体反向：链连续性断言不变（同构） | **记录项** |

---

## 6. 纪律留痕

- 门禁**必携带实测值**；`checks` 只在全部产物写盘后算一次。
- 负例必须**非同构**；同构扰动不作为有效门。
- 构造性断言（连续性、方向）必须**在代码里 assert**，不得只写进报告。
- 本步结论**不得**用于调整 v1.0 的交通动力学参数。
