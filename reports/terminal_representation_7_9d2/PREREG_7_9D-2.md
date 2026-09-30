# PREREG — Step 7.9D-2  Terminal Representation Audit

> **冻结时刻**：2026-09-20（在读取任何 7.9D-2 输出之前）
> **上游裁定**：7.9D-0 结论 `DELAY_TRAP_OFF_MAINLINE_BY_CONSTRUCTION__BASE_RATE_DOMINATED`；`service` 固定为 **400 veh/h/车道 / 自由流 20 km/h / 薄储存**；236,044 出行中 **90.26% 至少一端落在 `service`**。
> **本步性质**：**零仿真只读结构 + 自由流时间审计**。⛔ 不改 network、⛔ 不改 capacity、⛔ 不跑 MATSim、⛔ 不先改容量、⛔ 不产生 v1.1。
> **本步只回答一个问题**：大量需求是否在**进入真正的主干路网之前**，就已经被 **terminal-access representation** 消耗掉了大量自由流时间？

---

## 0. 与上游的边界（不可越界）

- 7.9D-0 已证明：端点暴露（O 落 `service` 70.68% / D 66.85% / 至少一端 90.26%）是**描述性**结论，**无裁决权**。
- 本步**不得**改 `service` 容量（400）、⛔ 不改端点吸附方式；**只审计表示机制**。
- 本步**不得**重答 D-0 / D-1 的问题；**不得**修改任何冻结件。
- **沿用 R-DIST-1 / R-MULTI-1**（见 `PREREG_7_9D-1.md` §1）：距离一律物理口径；接口判据一律多跳。

## 1. 数据源（只读）

| 用途 | 路径 |
|---|---|
| 网络（v1.0 冻结） | `scripts/od/_cache_network_7_9c0.npz` |
| **冻结输入需求（端点来源）** | `matsim_final_7_6h/populations/pop_W01/population_lambda_0p075.xml.gz` |
| v1.0 linkstats（**仅用于 volume 权与交叉核对**） | `matsim_final_7_6h/outputs/W01_rc_min/ITERS/it.19/W01_rc_min.19.linkstats.txt.gz` |
| KW linkstats（交叉核对） | `matsim_kw_7_9b1/outputs/W01_kw/ITERS/it.19/W01_kw.19.linkstats.txt.gz` |
| 冻结件快照（changed 门） | `matsim_final_7_6h`、`matsim_viz_7_8`、`matsim_kw_7_9b1` |

⛔ 不读 `output_plans` / `output_allVehicles`（本步不用仿真路由；`TT_terminal/TT_trip` 用**网络级自由流分解**给出，见 §3-D）。

## 2. 定义（冻结）

- **class** 严格沿用 7.9B-1（同 D-1）。
- **raw highway 分组（本步新增，用于端点分布）**：
  - `mainline` = `{motorway, trunk}`
  - `ramp` = `{motorway_link, trunk_link}`
  - `arterial` = `{primary, secondary, tertiary, primary_link, secondary_link, tertiary_link}`
  - `local` = `{residential, living_street, unclassified, service, road}`
  - `other` = 其余
- **端点**：每人的**选中 plan** 的首个 `<act link>`（origin）与末个 `<act link>`（destination）。
- **自由流接入时间**（**主口径**）：
  - `t_to_mw[i]` = 从 link `i` **沿行驶方向**到最近 mainline 的最短**免费流时间（秒）**（Dijkstra，权 = `len_m/fs_mps`，种子 = 全部 mainline，向**上游**展开）。
  - `t_from_mw[i]` = 从最近 mainline **沿行驶方向**到达 link `i` 的最短免费流时间（秒）（种子 = mainline，向**下游**展开）。
  - 逐出行：`T_acc = t_to_mw[o]`（到主线的时间）、`T_egr = t_from_mw[d]`（从主线到目的地的时间）、`T_terminal_lb = T_acc + T_egr`。
- **全网自由流时间分解（回答 `TT_terminal/TT_trip` 的网络级形式）**：
  - `VH_ff[i] = HRS8-9avg[i] × (len_m[i]/fs_mps[i]) / 3600`（车·小时，免费流）。
  - `share_offmain = Σ_{cls≠motorway} VH_ff / Σ_all VH_ff` ⇒ **即在进入/离开主干路网前后所消耗的自由流时间占全部自由流时间的比例**。

## 3. 冻结常数

| 常数 | 值 | 用途 |
|---|---|---|
| `OFFMAIN_HI` | 0.70 | off-mainline 占比「主导」阈值 |
| `OFFMAIN_LO` | 0.50 | off-mainline 占比「次要」阈值 |
| `ACC_MED_HI_S` | 180 | 接入时间中位「偏高」阈值（秒） |
| `EXPECT_TRIPS` | 236044 | 端点复现（冻结复现） |
| `EXPECT_V1_DELAY_H` | 4778.8 | 与 7.9D-0 一致（±0.5 h） |
| `CTE_NAME` / `CTE_EXPECT_N` | `Central Expressway` / 603 | 正名口径 |
| `BANNED_MASK` | `CTE` | `"CTE" in name.upper()` **命中必须为 0** |

## 4. 门控（T2.01–T2.13，全部硬门）

| ID | 描述 | 通过条件 |
|---|---|---|
| T2.01 | 网络来自 v1.0 冻结缓存 | `links==693575` 且 `km≈15126.5(±5)` |
| T2.02 | 端点解析复现 | `n_trip_mapped == 236044` |
| T2.03 | 端点 class 分布已算（O/D/either） | 三者均产出 |
| T2.04 | 端点 raw-highway 分组分布已算 | 5 组均产出、非退化 |
| T2.05 | `t_to_mw` 完整 | `finite≥0.99` |
| T2.06 | `t_from_mw` 完整 | `finite≥0.99` |
| T2.07 | 逐出行 `T_acc`/`T_egr` 分布已算 | 产出非空 |
| T2.08 | 全网自由流分解已算 | `Σ VH_ff > 0` |
| T2.09 | `share_offmain` 已算 | 有限且 ∈[0,1] |
| T2.10 | v1.0 延误份额（off-mainline）已算 | `total_delay ≈ 4778.8 h (±0.5)` |
| T2.11 | KW 交叉核对已算 | KW `share_offmain` 已产出 |
| T2.12 | verdict 判定 | 落在 §5 允许集合内 |
| T2.13 | 冻结件未被触碰 | `changed == 0` |

## 5. Verdict 分支（**冻结顺序**，自上而下首个命中）

```
if t_to_mw finite < 0.99 or t_from_mw finite < 0.99:
    v = 'TERMINAL_ACCESS_UNMEASURABLE'
elif share_offmain >= OFFMAIN_HI and median_T_acc >= ACC_MED_HI_S:
    v = 'TERMINAL_ACCESS_CONSUMES_DOMINANT_FREE_FLOW_TIME'
elif share_offmain >= OFFMAIN_HI:
    v = 'TERMINAL_NETWORK_DOMINATES_FREE_FLOW_TIME__ACCESS_SHORT'
elif share_offmain >= OFFMAIN_LO:
    v = 'MIXED__TERMINAL_AND_MAINLINE_COMPARABLE'
else:
    v = 'MAINLINE_DOMINATES_FREE_FLOW_TIME__TERMINAL_NOT_THE_BOTTLENECK'
```

`median_T_acc` = 逐出行 `T_acc` 的中位（秒）。

## 6. 独立旗标（记录，不改 verdict）

`ENDPOINT_SERVICE_DOMINANT`（O 或 D 落 `service` ≥0.50）｜`TERMINAL_IS_SERVICE_90`（至少一端 `service` ≥0.90）｜`OFFMAIN_MAJORITY`（`share_offmain≥0.50`）｜`SERVICE_CAP_FIXED`（`service` 的 `cap/lane` 唯一 = 400）｜`SERVICE_SPEED_FIXED`（`service` 自由流唯一 = 20 km/h）。

## 7. 反模式（禁止）

1. ⛔ **不得**把「至少一端 `service` 90%」当作延误因果（7.9D-0 已判其 base-rate 性质）。
2. ⛔ **不得**只用绝对时间份额；必须给出**分布（中位 / p90）**与 **km 对照**。
3. ⛔ **不得**用 hop count 作距离结论（R-DIST-1）。
4. ⛔ **不得**修改 `service` 容量或端点吸附；本步**只证明不修改**。
5. ⛔ **不得**在预注册后追加裁决性判据；补充只能并列并标注「不改 verdict」。
6. ⛔ `CTE` 必须用正名；`banned_mask_hits` 必须为 0。

## 8. 输出

目录 `reports/terminal_representation_7_9d2/`：
`t2_audit_summary.json`、`t2_checks.csv`、`t2_gates.json`、`t2_endpoint_class.csv`、`t2_endpoint_highway.csv`、`t2_access_time.csv`、`t2_ff_decomposition.csv`、`t2_kw_cross.csv`、`_run_t2.log`。

## 9. 成功判据

13/13 硬门通过 + `changed=0` + verdict 落在 §5 集合内。**不改动任何冻结件；不产生 v1.1。**
