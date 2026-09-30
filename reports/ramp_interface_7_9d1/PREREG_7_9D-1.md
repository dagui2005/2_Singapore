# PREREG — Step 7.9D-1  Ramp Interface Audit

> **冻结时刻**：2026-09-20（在读取任何 7.9D-1 输出之前）
> **上游裁定**：7.9D-0 正式收口为 `DELAY_TRAP_OFF_MAINLINE_BY_CONSTRUCTION__BASE_RATE_DOMINATED`；研究对象由 `service + connector` **收窄**为 `mainline ↔ ramp ↔ local-access`。
> **本步性质**：**零仿真只读结构审计**。⛔ 不改 network、⛔ 不改 capacity、⛔ 不跑 MATSim、⛔ 不产生 v1.1。
> **本步只回答一个问题**：主线 ↔ ramp ↔ 地方路 的接口在**拓扑与容量上是否连续**，以及 **ramp 的延误是否真的能传到 motorway**。

---

## 0. 与上游的边界（不可越界）

- 7.9D-0 已证明：Sink-valve **证伪**（全岛 13 个）；主线在拓扑上**几乎完全可逆**（in 8,567 / out 8,566）；薄储存是**查表赋值**（`service` = 400 veh/h/车道、自由流恒 20 km/h），非涌现；延误向主线的有效耦合**很弱**（延误加权上游距主线 ≈ 1,952 m、`≤300 m` 仅 3.15%）。
- 7.9D-0 的**对象收窄裁定**：`ramp` 是主线接口邻域**唯一**相对富集类（邻域 `ratio` = **1.597**；motorway 0.978 / service 0.171 / connector ≈ 0）。
- **本步不得**重答 D-0 的问题（不重查阀、不重查薄储存的成因）；**不得**修改任何冻结靶场/OD/network/capacity。
- **本步不得**用「绝对延误份额」单独下结论——7.9D-0 已证明该统计会被全网基数放大；**必须同报 ratio（份额 / km 份额）**。

## 1. 判据规则（新增冻结，永久生效）

> **R-DIST-1（物理距离优先）**：`coupling distance` / `spillback reach` / `interface proximity` **一律以 meter / km 为主口径**；hop count **仅作拓扑辅助**，且必须同时给出其物理距离换算。
> 依据：7.9D-0 证明 link 中位 ≈ 11 m 时，72 hops 听起来很大，实际仅 ≈ 1.95 km。本步所有「接口距离」均以 **免费流加权弧长（m）** 计。

> **R-MULTI-1（多跳优先）**：任何「接口 / 相邻 / 耦合」判据**不得**只用单跳邻接。依据：本步预检发现 **`motorway_link` 中 92.7% 的 link 在单跳上既无 motorway 上游也无 motorway 下游**（hyper-fragmentation）⇒ 单跳口径是**近重言式**。

---

## 2. 数据源（只读）

| 用途 | 路径 |
|---|---|
| 网络（v1.0 冻结） | `scripts/od/_cache_network_7_9c0.npz`（693,575 link / 15,126.5 km） |
| v1.0 linkstats | `matsim_final_7_6h/outputs/W01_rc_min/ITERS/it.19/W01_rc_min.19.linkstats.txt.gz` |
| KW linkstats | `matsim_kw_7_9b1/outputs/W01_kw/ITERS/it.19/W01_kw.19.linkstats.txt.gz` |
| 冻结件快照（changed 门） | `matsim_final_7_6h`、`matsim_viz_7_8`、`matsim_kw_7_9b1` |

⛔ 不读 `output_plans` / `output_allVehicles`（本步不需要出行级路由）。

## 3. 定义（冻结）

- **class（**严格沿用 7.9B-1，不得改**）**：
  `ramp` = `{motorway_link, trunk_link}`；`connector` = 其余 `*_link`；`service` = `service`；`motorway` = `{motorway, trunk}`；`other` = 其余。
- **mainline** ≡ `motorway`（含 `trunk`）。
- **单跳接口类型**（仅作对照，不作裁决）：对 ramp link `i`，令
  `up(i)` = {`cls[j]` : `to[j]==frm[i]`}，`dn(i)` = {`cls[k]` : `frm[k]==to[i]`}。
  `on_ramp` = `motorway∈up(i)`；`off_ramp` = `motorway∈dn(i)`；`both`；`neither`。
- **多跳物理接口距离**（**主口径**）：
  - `dn_m[i]` = 从 `i` **沿行驶方向**到最近 mainline 的**最短免费流弧长（m）**（**接入距离**；Dijkstra，权 = `len_m`，种子 = 全部 mainline，向**上游**展开，即从主线回推其上游 feeder）。
  - `up_m[i]` = 从最近 mainline **沿行驶方向**到达 `i` 的最短免费流弧长（m）（**驶离距离**；种子 = mainline，向**下游**展开）。
  - 二者语义以本行**文字定义**为准；`delay_weighted_dn_m` 使用 `dn_m`（接入距离，即「ramp 能否把延误送到主线」的方向）。
  - `ramp_chain_len[i]` = `dn_m[i] + len_m[i]`（该 ramp 片段到主线的**残余链长**）。
- **时间版**：`t_to_mw[i]` = 同 `dn_m` 但权 = `len_m / fs_mps`（免费流秒）；`t_from_mw[i]` = 同 `up_m`。
- **车道 / 容量不连续**：对每个 `on_ramp` 片段 `i`（其 `to` 节点有 motorway 出边）：
  `Δlanes(i)` = `min{lanes[k] : k∈out(to[i]), cls[k]=='motorway'}` − `lanes[i]`。
  `Δlanes < 0` ⇒ **合流处车道下降（lane DROP）**。
  另记 `Δcap_per_lane(i)` = `cap/lane(motorway) − cap/lane(ramp)`。
- **延误**：`delay_h[i] = max(TT8-9avg − ceil(FF), 0) × HRS8-9avg / 3600`（与 7.9D-0 逐字一致；`FF = len_m/fs_mps`）。

## 4. 冻结常数

| 常数 | 值 | 用途 |
|---|---|---|
| `RAMP_NEAR_M` | 300 | 「贴近主线」阈值（物理，m） |
| `RAMP_FAR_M` | 1000 | 「远离主线」阈值（物理，m） |
| `DELAY_HOST_SHARE` | 0.05 | 某类成为「延误宿主」的绝对份额门槛 |
| `LANE_DROP_THR` | 0.20 | 合流车道下降的判定门槛（占 on-ramp 比例） |
| `EXPECT_RAMP_LINKS` | 11740 | 预检已观测（冻结复现） |
| `EXPECT_RAMP_KM` | 308.15 | 预检已观测（±0.5 km） |
| `EXPECT_V1_DELAY_H` | 4778.8 | 与 7.9D-0 一致（±0.5 h） |
| `CTE_NAME` / `CTE_EXPECT_N` | `Central Expressway` / 603 | 正名口径 |
| `BANNED_MASK` | `CTE` | `"CTE" in name.upper()` **命中必须为 0** |

## 5. 门控（R1.01–R1.13，全部硬门）

| ID | 描述 | 通过条件 |
|---|---|---|
| R1.01 | 网络来自 v1.0 冻结缓存 | `links==693575` 且 `km≈15126.5(±5)` |
| R1.02 | class 掩码非退化 | `ramp>0 且 motorway>0` |
| R1.03 | ramp 复现 | `ramp_links==11740` 且 `ramp_km≈308.15(±0.5)` |
| R1.04 | 单跳接口类型已算 | `on+off+both+neither == ramp_links` |
| R1.05 | 多跳 `dn_m` 完整 | `finite≥0.999` 且 `min>0` |
| R1.06 | 多跳 `up_m` 完整 | `finite≥0.999` 且 `min>0` |
| R1.07 | 车道不连续已算 | `on_ramp 样本 ≥ 100` |
| R1.08 | v1.0 延误复算一致 | `total_delay ≈ 4778.8 h (±0.5)` |
| R1.09 | ramp 延误份额已算 | `ramp_delay_share` 有限 |
| R1.10 | ramp 储存 / fill 已算 | 产出非空 |
| R1.11 | KW 交叉核对已算 | KW ramp 延误已产出 |
| R1.12 | verdict 判定 | 落在 §6 允许集合内 |
| R1.13 | 冻结件未被触碰 | `changed == 0` |

## 6. Verdict 分支（**冻结顺序**，自上而下首个命中）

```
if dn_m finite < 0.99 or up_m finite < 0.99:
    v = 'RAMP_INTERFACE_BROKEN__NO_PATH_TO_MAINLINE'
elif lane_drop_share >= LANE_DROP_THR:
    v = 'RAMP_INTERFACE_LANE_DISCONTINUITY_AT_MERGE'
elif ramp_delay_share < DELAY_HOST_SHARE and delay_weighted_dn_m <= RAMP_FAR_M:
    v = 'RAMP_INTERFACE_CONTINUOUS__RAMP_NOT_A_DELAY_HOST'
elif delay_weighted_dn_m > RAMP_FAR_M:
    v = 'RAMP_INTERFACE_CONTINUOUS_BUT_DISTANT__DELAY_DECOUPLED_FROM_MAINLINE'
else:
    v = 'INDETERMINATE'
```

其中 `delay_weighted_dn_m` = `Σ(delay_h[ramp] × dn_m[ramp]) / Σ(delay_h[ramp])`。

## 7. 独立旗标（记录，不改 verdict）

`SINGLE_HOP_TAUTOLOGY`（neither 占比 ≥0.80 ⇒ 单跳口径近重言式）｜`LANE_DROP` ｜`RAMP_IS_DELAY_HOST`（`ramp_delay_share≥0.05`）｜`RAMP_NEAR_MAINLINE`（`delay_weighted_dn_m ≤ 300 m`）｜`CAP_DETERMINISTIC`（`cap/lane` 在 `highway` 内唯一）。

## 8. 反模式（禁止）

1. ⛔ **不得**用单跳邻接作为「接口」的唯一判据（92.7% 为 `neither`，接近重言式）。
2. ⛔ **不得**只用绝对延误份额；必须同报 `ratio = delay_share / km_share`。
3. ⛔ **不得**用 hop count 作距离结论；必须给物理距离（R-DIST-1）。
4. ⛔ **不得**因本步结果修改 network / capacity / 靶场；本步**只证明不修改**。
5. ⛔ **不得**把 `CTE` 用简称掩码识别（`banned_mask_hits` 必须为 0）。
6. ⛔ **不得**在预注册后追加裁决性判据；如需补充，只能作为**并列 supplementary**并显式标注「不改 verdict」。

## 9. 输出

目录 `reports/ramp_interface_7_9d1/`：
`r1_audit_summary.json`、`r1_checks.csv`、`r1_gates.json`、`r1_interface_topology.csv`、`r1_lane_discontinuity.csv`、`r1_ramp_chain.csv`、`r1_ramp_delay.csv`、`r1_storage.csv`、`_run_r1.log`。

## 10. 成功判据

13/13 硬门通过 + `changed=0` + verdict 落在 §6 集合内。**不改动任何冻结件；不产生 v1.1。**
