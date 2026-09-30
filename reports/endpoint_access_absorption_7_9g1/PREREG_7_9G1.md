# PREREG — Step 7.9G-1 · 端点/接入子系统「就地吸收」机制审计（R0）

> **零仿真 / 只读 / 可证伪结构审计。**
> 本文件在脚本运行前冻结；脚本内嵌本文件 sha256 与字节数，门 01 校验二者逐位一致。
> 上游：`7.9G-0 = SERVICE_DELAY_R0_READY`（Q1 `CAPACITY_CONSTRAINT_NOT_DOMINANT` / Q2 `CALIBER_FRAGILE` / Q3 `SERVICE_PARAMS_DERIVED`）。
> 用户裁定（2026-09-28）：`7.9G-0` 正式 READY；service 线进入 **方案 (a) 端点/接入子系统审计**。

---

## 1. 冻结边界（不可越界）

1. **零仿真**：不启动 MATSim / Java，不生成任何新仿真产物；只读既有输出。
2. **只读**：⛔ 不修改 `Singapore_OD_MATSim_Final_v1.0`；⛔ 不修改 `7.9G-0`、`Q4-R1-R1`、`7.9F-*`、`7.7E` 任何产物；⛔ 不修改 `7.1` / `7.3.6A` / OD / network / capacity。
3. **不改 service 参数**：⛔ 不改 `unit_cap[service]=400`、`permlanes`、`freespeed`；⛔ 不改端点吸附规则；⛔ 不做任何敏感性试验。
4. **继承 G-0 两条冻结边界（作为本节点前置约束）**：
   - ⛔ **不得把「94.36%」作为 service 延误归因的单一证据**（G-0 Q2 = `CALIBER_FRAGILE`；四面相差 20 倍以上）；
   - ⛔ **不得把 `service capacity = 400 veh/h/lane` 直接作为后续敏感性旋钮**（G-0 Q3 = `SERVICE_PARAMS_DERIVED`）。
5. **本节点新增边界**：
   - ⛔ **「端点」不得偷换概念**：必须在 **①人口/OD 端点面**（活动点吸附）、**②路由位置面**（首/末链）、**③地理面**（长度/储存）三个面**分别定义并分别报告**；禁止用任一面的结论代替另一面。
   - ⛔ **不得用「流量面份额」代替「时间面份额」**：G-0 已证四面可差 20 倍以上。
   - ⛔ 本节点只做**机制刻画**，不改模型；产出的机制判决**不得**直接转成参数改动建议。

---

## 2. 冻结输入（7 件，含 sha256 / 字节数；跑前跑后逐位校验）

| key | 相对路径 | 字节 | sha256 |
|---|---|---|---|
| `pop` | `matsim_final_7_6h/populations/pop_W01/population_lambda_0p075.xml.gz` | 8,930,574 | `e96ed83ff59c0f5ecb50c9d9ff2d42a4b4bdbebf2bbfe81a1e0604fb94921fbd` |
| `plans` | `matsim_final_7_6h/outputs/W01_rc_min/W01_rc_min.output_plans.xml.gz` | 215,827,261 | `2aee1ba25a8416c986d09a8fb8f502de0dc6ace18e6863119c9959c45bbf1210` |
| `events` | `matsim_viz_7_8/outputs/W01_events/W01_events.output_events.xml.gz` | 1,694,011,331 | `c9b61fba06d8a9b07b5ff27d6ccb92e996f0d74833e8bb0233b8ed942a5a3b98` |
| `ls_final` | `matsim_final_7_6h/outputs/W01_rc_min/ITERS/it.19/W01_rc_min.19.linkstats.txt.gz` | 22,629,291 | `b842b93a92f41c81248922078ebc68fdbe5ddc88f70086ccfd32bf955f0c1949` |
| `ls_viz_ref` | `matsim_viz_7_8/outputs/W01_events/ITERS/it.19/W01_events.19.linkstats.txt.gz` | 22,629,291 | `b842b93a92f41c81248922078ebc68fdbe5ddc88f70086ccfd32bf955f0c1949` |
| `net_links_runtime` | `matsim_viz_7_8/outputs/W01_events/W01_events.output_links.csv.gz` | 14,753,288 | `b65edfd5a59f233bb2e8d83384dbe07650dadbdae929ed6a378c0e3af0a6c5c9` |
| `src_copy` | `reports/matsim_network/network_links_source_copy.csv` | 52,670,157 | `b5265e5978608e7337712922b67f455b8c86c42c204ccc32a742da48180de9c6` |

**说明**：
- `ls_final` 与 `ls_viz_ref` **逐字节相同**（门 09 断言）⇒ 允许用 `W01_events` 的 events 作为 `W01_rc_min` 的同一次运行的逐车轨迹代理。
- `cfg`（`config_W01_rc_min.xml`, 22,098 B, `8f44fb349bff9cf1b2bfd497b914b291f9d79482936689a2f2b6a8ffcfc1206e`）作为只读参照，用于 `accessEgressType` / `storageCapacityFactor` 的读值复核。
- ⛔ **`pop` / `plans` / `events` 是本节点新增冻结输入**，一旦进入本 prereg 即不可替换；替换即 v1.1。

---

## 3. 只读对照物（相对 REF_DIR = `reports/service_delay_mechanism_7_9g0/`）

| key | 文件 | 用途 |
|---|---|---|
| `g0_summary` | `g0_summary.json` | 核对 canonical 总量与 service 份额（`4778.77366611111` / `94.35657888849315`） |
| `g0_concentration` | `g0_service_concentration.csv` | 核对 top-N 集中度 |
| `g0_faces` | `g0_exposure_faces.csv` | 核对四面口径 |
| `g0_verdicts` | `g0_verdicts.csv` | 核对 Q1/Q2/Q3 判决串 |

上述 4 件只读、不写回（门 25 校验 sha 未变）。

---

## 4. 对象与口径定义（判定前冻结）

- **O1 端点集合（人口面）**：对每个人取 `home` / `work` 活动的 `link` 属性为端点链；权重 = 其 `expansionFactor`（EF）。端点强度 `E(ℓ) = Σ_{home=ℓ} EF + Σ_{work=ℓ} EF`。
- **O2 端点链路契约**：⛔ 端点链必须逐位等于该人**选中计划**（`selected="yes"`）首腿路由的 `start_link`（home）与末腿路由的 `end_link`（work）。门 10 断言全量匹配率 **== 1.0**。
- **O3 link 层**：`road_type`（`src_copy.highway`）；`length` / `permlanes` / `capacity`（`net_links_runtime`）。
  - `cap_flow(ℓ) = capacity(ℓ)`（读值）；校验 `capacity ≈ UNIT_CAP[road_type] × permlanes`。
  - **`storage_veh(ℓ) = length(ℓ) × permlanes(ℓ) / 7.5`**（MATSim 队列储存约定；`storageCapacityFactor=1.0`）。⚠️ 这是**派生诊断量**，非配置读值。
- **O4 干道接口（D-ADJ）**：`service` 链 ℓ 若其 `from` 或 `to` 节点上存在 `road_type ∈ {motorway, motorway_link, trunk, trunk_link, primary, primary_link, secondary, secondary_link}` 的边，则 ℓ 为「邻干道」；否则为「内部」。
- **O5 canonical 延误（与 G-0 逐位一致，不可改）**：
  - `ff_s = LENGTH / FREESPEED`；`ff_ceil_s = ceil(ff_s − 1e-9)`；
  - `delay_corr_h = Σ_{v>0} v · max(0, TT8-9avg − ff_ceil_s) / 3600`（canonical）；
  - `delay_raw_h` 用 `ff_s`（未扣量化）。
- **O6 暴露面（四面并报，继承 G-0）**：`time`（车时）/ `count`（链数）/ `distance`（长度）/ `volume`（流量）。
- **O7 路由位置（plans 面）**：仅取 **选中计划**；对每条路由的链序列，位置 ∈ {`first`, `last`, `mid`}（`first`/`last` 定义相对于**该路由**）。
- **O8 全 local 路由**：路由的全部链 `road_type ∈ {service, residential}`。
- **O9 窗口**：读 4 个小时 `7-8 / 8-9 / 9-10 / 10-11`；**主窗 = `8-9`**；⛔ 不读任何 `0-24` 聚合列。

---

## 5. 可证伪问题（A1–A6）与证伪构造

> 核心命题（用户裁定原文）：
> **service 延误是否主要表现为端点接入、局部循环和短链时间表达所形成的「就地吸收」，而非道路容量约束产生的排队延误。**

### A1 端点吸附量级 — `ENDPOINT_SNAPPING`
- 量：`p_end_svc` = service 端点强度 / 全部端点强度（加权 EF）。
- 基线：`mileage_share_svc` = service 里程 / 全网里程；`count_share_svc` = service 链数 / 全网链数。
- **证伪构造**：若 `p_end_svc / mileage_share_svc < 1.5`，则「端点系统性吸附到 service」**不成立**（因为网络本就以 service 为主）。
- 判决：`ENRICHED_ON_SERVICE`（比值 ≥ 1.5）/ `PROPORTIONAL_TO_MILEAGE`（< 1.5）。

### A2 就地吸收：端点 vs 遍历位置 — `ENDPOINT_ABSORPTION`
- `f_pos` = service 遍历中位于路由首/末位的份额（**体积面**，plans）。
- `w_ep` = 端点∩service 延误 / **service 延误**（**时间面**，linkstats）。
- `v_ep` = 端点∩service 流量 / **service 流量**（**体积面**）。
- **证伪构造**：若 `w_ep ≈ f_pos`（同量级），则「吸收」可由**遍历数量**解释（位置效应）；若 `w_ep ≥ 2×f_pos` 且 `w_ep ≥ 2×v_ep`，则「吸收」是**端点链的单位延误放大**（放大效应）。
- 判决：`ENDPOINT_LOCALIZED`（放大成立）/ `POSITION_PROPORTIONAL`（不成立）。

### A3 干道接口排除 — `MAINLINE_INTERFACE`
- 量：`s_main` = 邻干道 service 延误 / 全网延误；`s_int` = 内部 service 延误 / 全网延误。
- **证伪构造**：若 `s_main ≥ s_int`，则延误可能仍是**干道排队外溢**，不可排除。
- 判决：`NOT_MAINLINE_QUEUE`（`s_main < s_int`）/ `MAINLINE_QUEUE_SUSPECTED`（否）。

### A4 绑定约束：流量容量 vs 储存微胞 — `BINDING_CONSTRAINT`
- 样本 `D` = 端点∩service 且 `delay_corr_h > 0` 的链。
- 量：`sat_share_D` = `{v/c_flow ≥ 0.9999}` 在这些链延误中的份额；`cell_share_D` = `{storage_veh < 2}` 在这些链延误中的份额；
- 并报 `v/c_flow` 与 **`v/c_storage = vol / storage_veh`** 的分位（张力诊断）。
- **证伪构造**：若 `sat_share_D ≥ 0.50`，则**流量容量绑定**成立（容量排队解释）；否则若 `cell_share_D ≥ 0.50`，则**储存微胞绑定**成立；否则两者皆非。
- 判决：`FLOW_CAPACITY_BOUND` / `STORAGE_CELL_BOUND` / `NEITHER_BOUND`。

### A5 局部循环 — `LOCAL_CIRCULATION`
- 量：`f_local` = 全 local 路由 / 全部路由。
- **证伪构造**：`f_local ≥ 0.05` ⇒ 成立。
- 判决：`LOCAL_CIRCULATION_PRESENT` / `NEGLIGIBLE`。

### A6 机制汇总判决 — `MECHANISM`
- 记 `s_end` = 端点∩service 延误 / **全网延误**，`s_mid` = 非端点 service 延误 / 全网延误，`s_main` 同 A3。
- 规则（**先判后取，顺序不可变**）：
  1. `s_main ≥ 0.50` → `MAINLINE_QUEUE_DOMINANT`
  2. 否则 `s_mid ≥ 0.50` → `MIDROUTE_THROUGH_DOMINANT`
  3. 否则 `s_end ≥ 0.50` 且 `A4 判决 == STORAGE_CELL_BOUND` → `SUBCELL_STORAGE_DOMINANT`
  4. 否则 `s_end ≥ 0.50` → `ENDPOINT_ABSORPTION_DOMINANT`
  5. 否则 → `MIXED_NO_SINGLE_DOMINANT`

### A7 逐车轨迹校验（events 面）— 仪器 `E-TRACE`
- 目标集 `T` = 端点∩service 中 canonical 延误 **top-12** 的链。
- 单遍流式扫描 `events`，对 `link ∈ T` 的 `entered link` / `left link` 事件记录 `(t, vehicle, type)`；并记录 `departure` 事件的 `(t, vehicle, link)`。
- 派生（每链）：`n_enter` / `n_leave` / `dwell = t_left − t_enter` 的 p50/p90/max / `headway`（相邻 enter 间隔）p50 / `n_first_link`（enter 紧跟同车 `departure`）/ `cap_headway_s = 3600/cap_flow`。
- **用途**：区分「入口排队（headway ≈ cap_headway）」与「链路内滞留（dwell ≫ ff）」。**只作描述性交叉校验，不改变 A1–A6 的判决规则**。

---

## 6. 硬门（25 条；⛔ 门禁只断言「已计算 + 判决自洽」，不编码期望科学结论）

| # | gate | 判据 |
|---|---|---|
| 01 | `PREREG_FROZEN_AND_EMBEDDED` | 盘上 prereg 的 sha256/字节 == 脚本内嵌常量 |
| 02 | `SCRIPT_AST_COMPILE` | 脚本 AST 解析 + compile 通过 |
| 03 | `ZERO_SIMULATION` | AST 内无 `matsim/java/jpype` import、无 subprocess 调用 |
| 04 | `INPUT_MANIFEST_COMPLETE` | 7 件冻结输入全部存在且 size/sha 逐位一致 |
| 05 | `LINKSTATS_154_COLUMNS` | linkstats 列数 == 154 且必需字段齐全 |
| 06 | `NETWORK_JOIN_COMPLETE` | `road_type` 缺失数 == 0 |
| 07 | `LINKSTATS_JOIN_COMPLETE` | `HRS8-9avg` 缺失数 == 0 |
| 08 | `TRIPLE_FIELD_IDENTITY` | runtime net 与 linkstats 的 length/freespeed/capacity 逐位一致（max|Δ| < 1e-9） |
| 09 | `REF_LINKSTATS_BYTE_IDENTICAL` | `ls_final` 与 `ls_viz_ref` sha256 相等 |
| 10 | `ENDPOINT_LINK_EQ_ROUTE_ENDPOINT` | 全量（236,044）home/work 端点链 == 选中计划首/末链，匹配率 **== 1.0** |
| 11 | `CANONICAL_RECOMPUTE_MATCHES_G0` | 复算 `delay_corr_h` 与 service 份额对 G-0 相对误差 ≤ 1e-6 |
| 12 | `A1_ENDPOINT_SHARE_REPORTED` | `p_end_svc` / `mileage_share_svc` / `count_share_svc` 均有限且 ∈[0,1] |
| 13 | `A2_POSITION_VS_DELAY_DECLARED` | `f_pos` / `w_ep` / `v_ep` 均算出且有限；判决 == 规则结果 |
| 14 | `A2_CONCENTRATION_REPORTED` | top10 ≤ top100 ≤ 100 且 top10 < 100 |
| 15 | `A3_MAINLINE_ADJACENCY_REPORTED` | `s_main` / `s_int` / `s_main_links` 有限；判决 == 规则结果 |
| 16 | `A4_STORAGE_BUCKETS_COMPLETE` | 7 个储存桶齐全、桶内链数合计 > 0、无 NaN |
| 17 | `A4_VC_TENSION_DECLARED` | `sat_share_D` / `cell_share_D` / `v_c_flow` 与 `v_c_storage` 分位均算出；判决 == 规则结果 |
| 18 | `A5_LOCAL_ROUTE_SHARE_REPORTED` | `f_local` 有限且 ∈[0,1]；判决 == 规则结果 |
| 19 | `A6_MECHANISM_VERDICT_SINGLE` | A6 判决 ∈ 闭集，且 A1–A5 判决各自 ∈ 其闭集 |
| 20 | `EXPOSURE_FACES_COMPLETE` | 四面（time/count/distance/volume）齐备且 service/total 均有限 |
| 21 | `NO_WINDOW_MIXING` | 读取窗 ⊆ {7-8,8-9,9-10,10-11}；主窗 ∈ 读取集；读取列中无 `0-24` |
| 22 | `EVENTS_TRACE_COMPLETE` | 目标集 12 链**全部**有 `n_enter ≥ 1` 且 dwell/headway 字段完整 |
| 23 | `TRACEABILITY_FIELDS_COMPLETE` | 每件分析产物含 prereg 声明的必需列 |
| 24 | `TERMINAL_STATE_THREE_WAY` | checks/summary/report 三方状态串一致；**判据含门 01..23 与 25，不含自身** |
| 25 | `NON_7_9G_ARTIFACTS_UNCHANGED` | 7 件冻结输入 + 4 件只读对照物 sha256 跑后未变 |

---

## 7. 判决闭集（穷举；写在产物中，不得出现集合外取值）

```
A1_ENDPOINT_SNAPPING : {ENRICHED_ON_SERVICE, PROPORTIONAL_TO_MILEAGE}
A2_ENDPOINT_ABSORPTION: {ENDPOINT_LOCALIZED, POSITION_PROPORTIONAL}
A3_MAINLINE_INTERFACE : {NOT_MAINLINE_QUEUE, MAINLINE_QUEUE_SUSPECTED}
A4_BINDING_CONSTRAINT : {FLOW_CAPACITY_BOUND, STORAGE_CELL_BOUND, NEITHER_BOUND}
A5_LOCAL_CIRCULATION  : {LOCAL_CIRCULATION_PRESENT, NEGLIGIBLE}
A6_MECHANISM          : {MAINLINE_QUEUE_DOMINANT, MIDROUTE_THROUGH_DOMINANT,
                         SUBCELL_STORAGE_DOMINANT, ENDPOINT_ABSORPTION_DOMINANT,
                         MIXED_NO_SINGLE_DOMINANT}
```

---

## 8. 负例（必须全部触发对应门；未触发即门禁失效）

| id | 注入的破坏 | 期望触发门 |
|---|---|---|
| N1 | 从必需 linkstats 字段列表删除一个真实字段 | 05 |
| N2 | 在 `src_copy` 中把某类 `highway` 置空以制造 join 缺失 | 06 与 07 |
| N3 | 篡改 runtime net 的 `length`（单链 +1.0） | 08 |
| N4 | 让 `ls_viz_ref` 指向一个不同的 linkstats | 09 |
| N5 | 篡改 population 中一个人的 `home` 端点链 | 10 |
| N6 | 把 canonical 的 `ff_ceil` 改回 `ff`（未扣量化） | 11 |
| N7 | 在读取列表注入 `HRS0-24avg`（聚合列） | 21 |
| N8 | 让 A2 判决与实测规则结果不一致（写死相反值） | 13 |
| N9 | 让 A4 判决与实测规则结果不一致 | 17 |
| N10 | 让 A6 判决取闭集外的值 | 19 |
| N11 | 让 `events` 目标集为空（top-K=0） | 22 |

**BLOCKED 负例（须物化完整 BLOCKED 节点：25 行 checks + 6 文件 + EXIT=1）**：
- P1 空 ref 目录（对照物缺失）
- P2 篡改 `cfg` 的 sha（冻结输入漂移）
- P3 `LINKSTATS_EXPECTED_COLS` 改为 153

---

## 9. 必需输出（16 件；`<out>` = `reports/endpoint_access_absorption_7_9g1/`）

| 文件 | 内容 |
|---|---|
| `g1_endpoint_snapping.csv` | A1：端点类别分布（加权/计数）+ 里程/链数基线 |
| `g1_route_position_profile.csv` | A2：按 `road_type × position` 的遍历计数与份额 |
| `g1_endpoint_service_split.csv` | A2：端点/非端点 × service 的延误、流量、长度、份额 |
| `g1_mainline_adjacency.csv` | A3：邻干道/内部 service 的延误与流量 |
| `g1_storage_buckets.csv` | A4：7 桶 × n / vol / delay / delay_share / storage 中位 |
| `g1_binding_diagnostics.csv` | A4：`v/c_flow` 与 `v/c_storage` 分位、sat_share_D、cell_share_D |
| `g1_local_circulation.csv` | A5：全 local 路由份额、路由长度分布 |
| `g1_concentration_detail.csv` | top-30 端点 service 链全画像（长度/储存/cap/vol/TT/delay/位置剖面） |
| `g1_events_trace.csv` | A7：12 条目标链的 n_enter/n_leave/dwell/headway/n_first_link |
| `g1_exposure_faces.csv` | 四面：service 与全网各面值 + 份额 |
| `g1_verdicts.csv` | A1–A6 判决 + 规则 + 证据 |
| `g1_checks.csv` | 25 行门禁 |
| `g1_closure_check.csv` | 闭包表（16 artifact 行 + self_exclusion + 状态行） |
| `g1_input_manifest.json` | 清单（**最后生成、不自哈希、不含 closure**） |
| `g1_summary.json` | 头条数字 + 状态 + 判决 |
| `STEP7_9G1_REPORT.md` | 报告（`**STATUS: <...>**` 行必须存在） |

---

## 10. BLOCKED 条件（满足任一即 `ENDPOINT_ACCESS_R0_BLOCKED`，且必须完整物化节点）

1. 任一冻结输入缺失 / size 或 sha 不符；
2. 任一对照物缺失或 sha 不符；
3. linkstats 列数 ≠ 154 或必需字段缺失；
4. 网络/ linkstats join 出现缺失；
5. 端点契约匹配率 < 1.0；
6. canonical 复算对 G-0 相对误差 > 1e-6；
7. 任一分析产物缺必需列；
8. `events` 目标集无法物化（n_enter 全 0）；
9. 不动点 8 轮未收敛；
10. 出现沙箱外多余文件（stray）。

**终态要求**：`preflight FAIL → 对应门 FAIL → 25 行 checks → summary → manifest → closure → report → EXIT=1`，**不得用裸 assert 代替物化**。

---

## 11. 版本边界与不变量

- 本 prereg 冻结后，**任何**常量（输入 sha / 判决阈值 `1.5`、`2×`、`0.50`、`0.05`、储存除数 `7.5`、主窗 `8-9`、top-K `12`）改动 ⇒ 本 prereg 作废，须重出 prereg 并升版（v1.1）。
- 目标集 `T` 由 **canonical 延误** 决定；⛔ 不得改为按 `raw` 或按 `v/c` 选链。
- 储存 `storage_veh` 是**派生诊断量**；⛔ 不得写入任何冻结产物、不得回写 target。
- 本节点**不改任何模型参数**，其结论**不得**直接转成参数改动建议。

---

*冻结时间：2026-09-28 · 上游 `7.9G-0` READY · 本节点 R0（零仿真 / 只读）*
