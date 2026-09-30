# PREREG · Step 7.9I-B(b) —— 38 个零流量断面的平行边记账（零仿真）

> 运行前冻结。若事后发现判据缺陷，必须**披露 + 加后验修订分类**（`EXPLORATORY_POST_HOC`），
> **阈值一律不改**。

---

## 0. 立论与范围

7.9I-B 实测：**38 个 M1 断面的匹配边流量精确为 0**（担 M1 `Σobs` 的 13.24%）。
问题**不是**「这条边为什么没车」，而是：

> **LTA 所认为的这个交通对象，MATSim 实际把流量放到了哪个平行对象上？**

本步为 38 个断面逐个做**平行边记账**，输出 `matched / parallel A / parallel B` 三方流量对账。

⛔ 零仿真、只读；不改 v1.0 / 交叉表 / 靶场；本步结论**不得**用于调动力学参数。

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

**回读常量**：目标集 = **38**；目标 `Σobs` = **62,050.5**；`SCALE = 2.29897`。

---

## 2. 方法

### 2.1 目标集

`m1_cards_7_9ib.csv` 中 `n_edges_flow_gt0 == 0` 的断面（构造性断言：对 linkstats v1.0 逐边复核流量 == 0）。

### 2.2 平行对象池

半径 `R ∈ {100, 200} m`，边满足 `highway ∈ MAJOR = {motorway, motorway_link, trunk, trunk_link}`
且 `HRS8-9avg > 0`，按与断面方位的关系分组：

- **同向** `|Δbear| < DIR_OK(30°)`
- **反向** `|Δbear − 180°| < DIR_OK`
- 其余（横穿/斜交）计入 `other`，不参与判定但记账。

### 2.3 记账量（逐断面）

| 量 | 定义 |
|---|---|
| `matched_flow_xS` | `SCALE × Σ_{matched} HRS8-9avg`（= 0，构造性） |
| `par_sum_same_xS` / `par_sum_opp_xS` | 同向 / 反向平行边流量和 × SCALE |
| `par_max_same_xS` | 同向平行边**最大**流量 × SCALE |
| `par_top1..3` | 同向平行边按流量排序前 3（id, flow, dist） |
| `r_par_sum_same` / `r_par_max_same` | 除以 `obs_8_9` |

### 2.4 分类（单标签，固定优先级）

| 标签 | 条件 |
|---|---|
| `B1_SAME_DIR_PARALLEL` | `par_sum_same_xS ≥ 0.5 · obs`（MATSim 把流量放在**同向平行对象**上） |
| `B2_OPPOSITE_ONLY` | 否则 `par_sum_opp_xS ≥ 0.5 · obs`（只**反向**对象有流量） |
| `B3_NO_PARALLEL_FLOW` | 其余（无足够平行流量 ⇒ 真零流/网络不通） |

---

## 3. 硬门

| 门 | 断言 |
|---|---|
| `G-B1` 目标集 = **38** | |
| `G-B2` `Σobs` = **62,050.5** | |
| `G-B3` 构造性：匹配边流量**全部为 0**（对 linkstats 逐边复核） | |
| `G-B4` 分类全覆盖（无 NaN / 无未覆盖标签） | |
| `G-B5` 半径单调：`n_edges(100) ≤ n_edges(200)` 且 `Σflow(100) ≤ Σflow(200)` 逐断面 | |
| `G-N` 负例 4 个有效门全 `fired` | |

---

## 4. 可证伪条件

1. 若 `B1` 的 **Σobs 占比 = 0**，则「MATSim 把流量放在同向平行对象上」**不成立** ⇒
   38 个零流量断面应按「真实零流/网络不通」处理。
2. 若 `B1 + B2` 占比 ≥ 90%，则零流量断面**基本可由对象映射错误解释**。
3. 若 `B3` 占比 ≥ 50%，则**必须**回到网络连通性/需求层面。

---

## 5. 负例（非同构扰动）

| 编号 | 扰动 | 期望 |
|---|---|---|
| `N1_shuffle_parallel_flow` | 随机重排平行边流量 | `fired` |
| `N2_zero_parallel` | 令全部平行边流量 = 0 | `fired` |
| `N3_shift_mid` | 断面中点整体 `+300 m` | `fired` |
| `N4_drop_dir_filter` | 关闭方向过滤（同向 = 全部） | `fired` |
| `N5_reverse_all` | 整体反向：同向/反向**互换**但分类结构不变（同构） | **记录项** |

---

## 6. 纪律留痕

- 门禁**必携带实测值**；`checks` 只在全部产物写盘后算一次。
- 构造性断言（匹配边零流、半径单调）必须在代码里 `assert`。
- 本步结论**不得**用于调整 v1.0 的交通动力学参数。
