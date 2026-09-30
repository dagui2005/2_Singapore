# PREREG_7_9F2_v2 — Secondary/Tertiary Residual Mechanism Audit（正式节点）

**Step**: 7.9F-2 v2
**Scope**: zero-simulation, read-only, diagnostic-only
**身份**: 本文件定义 **F-2 正式证据节点**。`audit_secondary_tertiary_residual_7_9f2.py` 的 as-provided 运行
（输出目录 `reports/secondary_tertiary_residual_7_9f2/`）为 **R0 = 侦察运行**，保持原样、不再改写。
本 v2 与其**物理隔离**（独立目录、独立预注册哈希）。

---

## 0. 预注册前的只读探索（**披露**）

为把 D7 的容差**在下笔前定死**（而非事后调），本次在**不运行审计脚本**的前提下做了两项只读探针：

1. `TrafficFlow_Data.json` 顶层为 `{"LastUpdatedDate": "2026-03-18", "Value": [75,899 行]}`；
   字段 `LinkID, Date, HourOfDate, Volume, StartLon, StartLat, EndLon, EndLat, RoadName, RoadCat`。
   - `Date` 必须 `dayfirst=True`（否则仅 **40.7%** 可解析；`dayfirst=True` ⇒ 100%，覆盖 2025-11-01…2025-11-30 共 30 天）。
   - `HourOfDate` **仅含 `7` 与 `8`**（与 7.4.3-R「可观测窗 ≤ 07-09」一致）。
   - `RoadCat` 含 `CATA/B/C/D/E`、`SLIP_ROAD`、**`#N/A`**（与 F-1 的 `#N/A` 占位发现一致；本步骤目标域来自
     E2 `diagnostic_highway`，不来自 `RoadCat`，故 `#N/A` 不进入分析域）。
2. 按本 prereg §2 的 reduction 规则重建 `obs_8_9`，与 E2 `obs_8_9` 逐 LinkID 比对，**实测**：
   - 全部 1,311 条：逐位相等 **1,311/1,311**，`max|Δ| = 4.547473508864641e-13`
   - 109 条 target：逐位相等 **109/109**，`max|Δ| = 0.0`

**容差的定法（原则，非拟合）**：两侧是**同一冻结文件的同一定义 reduction**，因此**期望精确相等**；
`1e-9`（音量绝对）仅用于容忍浮点求和尾差。**该阈值在本次正式运行前已固定，运行后不得调整。**

---

## 1. Frozen boundary

本步骤不得修改 TrafficFlow、E1/E2、MATSim network/capacity/lanes/speed、route-choice/scoring/QSim、7.3.6A、7.6H、F-0/F-1、v1.0/v1.1。

本步骤不启动 MATSim、不调用 Java、不修改模型、不重新估计 SCALE、不重新设计 E1 candidate search。

**输出只写入 `reports/secondary_tertiary_residual_7_9f2_v2/`；R0 目录 `reports/secondary_tertiary_residual_7_9f2/` 只读、不得新增或改写任何文件。**

## 2. Fixed inputs

### TrafficFlow
`Singapore_OD_MATSim_FinalData/08_TrafficCount/TrafficFlow_Data.json`

工作日、`HourOfDate=8`；同一 `LinkID × Date` 先取日代表值（mean），再按 LinkID 取工作日 median，得到 `obs_8_9`。
`Date` 以 `dayfirst=True` 解析。

### TrafficFlow geometry
`Singapore_OD_MATSim_FinalData/08_TrafficCount/TrafficFlow_Links.shp`

字段：`LinkID, RoadName, RoadCat, StartLon, StartLat, EndLon, EndLat, geometry`。`.prj` = `GCS_WGS_1984`；
几何投影到 **EPSG:3414** 后计算 LTA directed heading。

### E1
`reports/arterial_observability_7_9e1/e1_crosswalk_candidates.csv`

严格复刻 F-1/E2 A+B main：有 A 用全部 A，否则全部 B；**C 不进入主诊断**；selected tier 内按 `matsim_link_id` 去重，保留全部 selected directed links。

### E2
`reports/arterial_expanded_residual_7_9e2/e2_section_residual_main.csv`

只读取 `LinkID, obs_8_9, diagnostic_residual_8_9, diagnostic_highway, valid_residual`，作为 frozen diagnostic target；F-2 **不重算 residual**。

### MATSim network
`reports/matsim_network/network_links_source_copy.csv`，必需 `from_node,to_node,length_m,highway,name`。

### MATSim nodes
`reports/matsim_network/network_nodes_source_copy.csv`，`node_id` / `x_svy21_m` / `y_svy21_m`（米，EPSG:3414）。

### W01
真实冻结运行结果：`matsim_final_7_6h/outputs/W01_rc_min/ITERS/it.19/`，使用 `LINK,HRS8-9avg`。

## 3. Frozen analysis domain

只分析：`diagnostic_highway ∈ {secondary, tertiary}`、`valid_residual=True`、`obs_8_9>0`。
预期 secondary=89、tertiary=20、合计 109；不足则 BLOCKED。

## 4. Matching-structure diagnostics

每个目标 LinkID 固定报告 `selected_total_n`、`selected_A_n`、`selected_B_n`、`selected_highway_n`、
`selected_distance_min_m`、`selected_distance_median_m`、`selected_direction_min/median/max_deg`、
`selected_direction_good_share`（`<=30°`）、`selected_direction_twin_share`（`>=150°`）、`same_highway_share`、
`matched_flow_raw_sum` / `matched_flow_scaled_sum` / `matched_ratio_sum`。

## 5. Directionality diagnostics

由 `TrafficFlow_Links.shp` 独立计算 LTA heading；由 network node 坐标计算 MATSim directed heading；
报告重算后的 direction difference，并与 E1 `direction_diff_deg` 做一致性记录。阈值固定 30° / 150°，**不得按 residual 调整**。

## 6. Parallel / twin diagnostics

**真实物理米制距离**（midpoint-to-midpoint，EPSG:3414），不用 hop count。固定半径：**20 m / 50 m / 100 m**。

- parallel：heading difference **<= 30°**；
- twin/opposite：heading difference **>= 150°**；
- 排除自身及 selected matched-link set；
- same-name / same-highway 仅作 **diagnostic subclass**，不是主定义。

## 7. Local-flow-envelope diagnostic

本步骤核心概念为 **local flow envelope diagnostic**，**不是** observed network flow conservation，**也不是** OD-level conservation。

- `matched_flow_raw = Σ HRS8-9avg(selected matched directed links)`；`matched_flow_scaled = matched_flow_raw × SCALE`，`SCALE = 459794/200000 = 2.29897`。
- 分别计算 20/50/100 m 下 parallel / twin / same-name parallel / same-name twin 的 added W01 flow；**不得重新运行 MATSim**。
- `envelope_ratio = (matched_flow_scaled + nearby_added_flow_scaled) / obs_8_9`。
- 固定报告 added share、envelope ratio、以及 `|envelope_ratio-1| - |matched_ratio-1|`。

⚠️ **口径披露（不得据此改动）**：`matched_flow_raw` 是**同一批链路的 Σ**，而 E2 的 `diagnostic_residual_8_9` 基于同一批链路的 **median**。
每断面选中链路数 min/median/max = 2/5/11，故 Σ 口径 ≈ median 口径的 4–5 倍；`Σ×SCALE/obs` 中位为 1.93（secondary）/1.65（tertiary）。
**因此 `envelope_ratio` 与 1 不可比，`|envelope_ratio-1| - |matched_ratio-1|` 属结构性为正。**
该问题**在本版本中原样冻结、仅作描述性报告，不进入机制结论**（见 §9 R-F2-12）。

## 8. Prespecified mechanism questions

- **Q1**：residual 是否与 selected candidate count、distance、direction quality、highway heterogeneity 存在单调关系？使用 Spearman。
- **Q2**：residual 是否与 median direction difference、direction-good share、reverse-candidate share 存在单调关系？使用 Spearman。
- **Q3**：20/50/100 m 内是否存在有非零 W01 flow 的 parallel/twin/same-name neighbors？报告 prevalence 与 observed-flow-weighted added share。
- **Q4**：20/50/100 m 的 matched baseline、parallel envelope、twin envelope、all-direction envelope 是否呈系统性不同？报告 mean/median/paired change；**不选择"最佳半径"**。

⚠️ **Q2 的可答性披露（不得据此改动）**：Tier A（`A_STRICT_SEMANTIC_DIRECTION`）与 Tier B（`B_DIRECTION_GEOMETRY`）
**以方向合格为选择前提**，故 A+B 域内 `direction_good_share` 恒为常数（实测 109/109 断面 = 1.0、
593 条候选重算方向差 max = 29.818° < 30°），相关统计量为**未定义（NaN）**。
**Q2 在本步骤内结构性不可答**，其结果原样保留、**不进入机制结论**（见 §9 R-F2-11）。

## 9. Non-circularity / permanent rules

- **R-F2-1**：E2 frozen residual 永久不被 F-2 包络重定义。
- **R-F2-2**：20/50/100 m、30°、150° 运行前固定。
- **R-F2-3**：neighbor search 不使用 residual sign、magnitude 或 rank 筛选。
- **R-F2-4**：只使用冻结 W01 `HRS8-9avg`；不重跑 MATSim。
- **R-F2-5**：matched baseline 使用 selected A+B directed links 的 W01 flow sum，仅为 F-2 diagnostic；F-1 canonical median 不改写。
- **R-F2-6**：same-name / same-highway 只是 diagnostic subclass。
- **R-F2-7**：主空间尺度永远是 physical meters；hop count 只能辅助记录。
- **R-F2-8**：secondary 与 tertiary 分开报告。
- **R-F2-9**：local flow envelope 数值改善不能表述为真实 network flow conservation 证明。
- **R-F2-10**：不得据 F-2 结果直接修改 capacity/speed/route-choice/demand/crosswalk。
- **R-F2-11**：**Q2 为结构性不可答**（选择规则以方向合格为前提）⇒ 其输出**只作描述，不进入机制结论**；
  **不得**在 v2 中替换 Q2 的提问域或补入新量来"救活"它。
- **R-F2-12**：**`matched_flow_raw` 的 Σ 口径与 obs 不同量纲可比性**（§7）**原样冻结**；
  `envelope_ratio` 及其导出量**只作描述，不进入机制结论**；**不得**在 v2 中改为 median 口径、方向折叠或引入第二口径。
- **R-F2-13**：§4–§8 的分析判据、公式与阈值在本版本中**一字未改**；v2 的改动**仅限** §13 所列的执行与契约缺陷。
- **R-F2-14**：Q2 / Q4 的**重新设计**（换域、补量、改口径）属**独立立项**（`PREREG_7_9F2_v2.1`），
  **不得**夹带在本次 v2 修补中。

## 10. Hard gates

1. `F2.01_PREREG_HASH`：prereg SHA256 MATCH；
2. `F2.02_ZERO_SIMULATION`：AST zero-simulation PASS；
3. `F2.03_TRAFFIC_INPUTS`：TrafficFlow JSON 与 geometry 输入完整（各 >= 1278 唯一 LinkID）；
4. `F2.04_E1_CANDIDATES`：candidate 完整，**并披露 `raw_rows` / `dropped_tier_C` / `dropped_missing_distance` / `kept_rows`**；
5. `F2.05_E2_TARGET_FIELDS`：E2 frozen residual 字段完整；
6. `F2.06_NETWORK_FIELDS_AND_COORDS`：network link/node 完整；
7. `F2.07_W01_LINKSTATS`：W01 `LINK`/`HRS8-9avg` 完整且 `LINK` 唯一；
8. `F2.08_TARGET_TOTAL_GE100`：target valid total >= 100；
9. `F2.09_SECONDARY_GE80`：secondary >= 80；
10. `F2.10_TERTIARY_GE15`：tertiary >= 15；
11. `F2.11_SELECTED_COVERAGE_GE95`：selected A+B coverage >= 95% of target；
12. `F2.12_SELECTED_NETWORK_COORD_GE99`：selected network coordinate coverage >= 99%；
13. `F2.13_DIRECTION_RECOMPUTED_GE95`：direction recomputed coverage >= 95%；
14. `F2.14_NEIGHBOR_DIAGNOSTICS_GE95`：20/50/100 m neighborhood diagnostics >= 95%；
15. `F2.15_OUTPUT_PROVENANCE`：**§12 声明的 12 项产物全部实际存在且非空**；输出目录名 == `secondary_tertiary_residual_7_9f2_v2`；
    无未声明杂散文件（已知外部同步瞬时文件模式除外，并在 detail 中列出）；R0 目录零污染；
16. `F2.16_OBS_CROSSWALK_REPRODUCED`：**由冻结 TrafficFlow JSON 实际重建的 `obs_8_9` 与 E2 的 `obs_8_9` 逐 LinkID 一致**
    —— 覆盖 `e2_rows == matched_rows`、`max|Δ| <= 1e-9`、`count(|Δ| > 1e-9) == 0`。

**阈值与判据与 R0（as-provided）完全一致**，仅新增 `F2.16`（D7 授权范围内）与 `F2.04` 的 detail 披露。

### §10.5 执行顺序契约（v2 新增，仅涉执行）

```
B1  写 8 件分析产物（不含任何判决字段）
B2  写 f2_summary.json      （status = PENDING_GATE_EVALUATION）
B3  写 STEP7_9F2_REPORT.md  （status = PENDING_GATE_EVALUATION）
B4  写 f2_checks.csv        （单行 F2.00_GATE_EVALUATION = PENDING）
B5  写 f2_input_manifest.json（v1：仅输入 provenance + protocol）
D   【唯一一次】终局门禁求值 → checks_rows, status
E  物化终局判决：重写 f2_checks.csv / f2_summary.json / STEP7_9F2_REPORT.md
F  重写 f2_input_manifest.json（终版：输入 provenance + 11 件已声明产物的 sha256/size）— **最后写**
G  写后闭合断言 A1–A9（非门禁行；任一失败即抛异常，退出码非 0）
```

**D 之前不写任何含判决内容的产物** ⇒ 磁盘上**永不出现**与终局判决不同的状态（对比 R0 会先落盘 FAIL/BLOCKED 再覆盖）。
`generated_artifacts` 由**显式声明清单**生成，**不再用 `iterdir()` 扫描**。

## 11. Decision boundary

`MECHANISM_AUDIT_READY`：全部 hard gates PASS，表示诊断链可用于后续 mechanism interpretation，**不代表某个机制已被证明**。

`MECHANISM_AUDIT_BLOCKED`：任一 gate FAIL，只能报告输入/contract 问题。

## 12. Output

固定目录：`reports/secondary_tertiary_residual_7_9f2_v2/`（**与 R0 目录物理隔离**）

声明产物 **12 项**：

1. `f2_target_sections.csv`
2. `f2_selected_candidates.csv`
3. `f2_candidate_structure.csv`
4. `f2_direction_diagnostics.csv`
5. `f2_direction_candidate_long.csv`
6. `f2_local_neighbors.csv`
7. `f2_mechanism_summary.csv`
8. `f2_group_summary.csv`
9. `f2_checks.csv`
10. `f2_input_manifest.json`
11. `f2_summary.json`
12. `STEP7_9F2_REPORT.md`

**允许的非声明辅助件（白名单，非杂散）**：

| 名称 | 性质 | 说明 |
|---|---|---|
| `PREREG_7_9F2_v2.md` | **协议输入（本目录常驻）** | 本预注册文件必须位于输出目录内，`F2.01` 才能对其取哈希；它是**输入**而非产物，故不列入 §12 的 12 项，但 **必须**列入 `F2.15` 无杂散检查的白名单 |
| `_run_v2.log` | 运行日志 | 由外部重定向产生 |
| `_f2v2_obs_crosswalk.csv` | D7 逐 LinkID 证据 | `F2.16` 的原始证据 |

⚠️ **实测记录**：v2 首次正式运行时，`F2.15` 的无杂散检查（断言 `A4`）**命中** `PREREG_7_9F2_v2.md` 并中止运行
（`AssertionError: A4 stray files in secondary_tertiary_residual_7_9f2_v2: ['PREREG_7_9F2_v2.md']`）。
按协议在此把该文件显式列入白名单后重跑。**这是本轮新增检查有效工作的第一手证据**（R0 版本无此检查、永远不会发现）。

**自指说明**：`f2_input_manifest.json` 无法自证其自身哈希 ⇒ 由写后断言 `A2`/`A3` 覆盖。
故 **`F2.15` 判定 12 项中的 11 项存在性 + 无杂散 + R0 隔离，`A2`/`A3` 判定 manifest 覆盖与哈希保真 ⇒ 合起来完整覆盖 §12。**

**已知外部同步瞬时文件模式（在 `F2.15` detail 中列出、不计为杂散）**：
包含 `baiduyun` 或 `uploading.cfg`、`*.tmp`、`Thumbs.db`、`desktop.ini`、`.DS_Store`、`~$*`。
（依据：R0 运行实测捕获到百度网盘同步的 `_run.asprovided.log.baiduyun.uploading.cfg`。）

## 13. v2 变更日志（**仅执行与契约；分析判据/阈值/口径一字未改**）

| 编号 | R0 缺陷 | v2 处置 |
|---|---|---|
| **D1** | manifest 早于 checks/summary/report 最终重写，4 条哈希陈旧；`iterdir()` 捕获外部瞬时文件；无写后断言 | manifest **最后写**；`generated_artifacts` 由**显式清单**生成；新增写后断言 **A2/A3**（双向哈希保真）；`F2.15` 增加无杂散检查与外部瞬时文件白名单 |
| **D2** | prereg §12 声明 12 项、gate 只列 11 项（缺 `f2_direction_candidate_long.csv`） | `DECLARED_ARTIFACTS` 与 §12 **完全一致（12 项）**；`F2.15` 逐项判定 |
| **D3** | `build_checks` 求值两次；干净目录首跑第一次求值 = BLOCKED（`F2.15` FAIL），先落盘 FAIL/BLOCKED 再覆盖 | **单次终局求值**（§10.5）；B 阶段仅写 `PENDING` 占位；**磁盘永不出现与终局判决不同的状态** |
| **D4** | —— | **不改**。Q2 结构性不可答（§8 披露）+ **R-F2-11** 明确其不进机制结论 |
| **D5** | —— | **不改**。Σ 口径与 obs 不可比（§7 披露）+ **R-F2-12** 明确其不进机制结论 |
| **D6** | `F2.04` 仅 `len(cand)>0`，detail 无原始行数/剔除量 | `F2.04` detail 披露 `raw_rows` / `dropped_tier_C` / `dropped_missing_distance` / `kept_rows` |
| **D7** | prereg §2 的 obs 推导规则未被使用（分析直接取 E2；仅契约声明） | **代码实际由冻结 JSON 重建 `obs_8_9`**，与 E2 逐 LinkID 比对：新增门 **`F2.16`** + 逐 LinkID 证据 `_f2v2_obs_crosswalk.csv` |

**未授权事项（本版本禁止）**：修改 Q2/Q4 提问方式、替换方向域、引入方向折叠口径、改动 §4–§8 任一公式或阈值、
回写 E2、改动 R0 目录。上述须另立 `PREREG_7_9F2_v2.1`。
