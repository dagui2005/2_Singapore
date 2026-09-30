# PREREG — Step 7.9G-0：`service` 延误机制 · R0 结构审计（零仿真／只读）

> **节点链**：`7.9F-0/1/2 → F-2 v2.1-R2（Q2）→ Q4-R1-R1（READY，线关闭）→ 7.9G-0（本节点）`
> **本预注册在脚本运行之前冻结。任何结论若未在此声明，不得写入正式产物。**
> 生成日期：2026-09-28

---

## 1. 冻结边界（Frozen boundary）

本节点**只读、零仿真**。明确禁止：

- ⛔ 不修改 `…_Final_v1.0`（7.8 冻结模型）任何参数；
- ⛔ 不修改 `reports/secondary_tertiary_residual_7_9f2_Q4_R1_R1/` 任何产物（其 SHA 已冻结在该节点 `closure_check.csv`）；
- ⛔ 不修改 `service` 的 `capacity` / `freespeed` / `permlanes`，**不跑任何 MATSim**；
- ⛔ 不改动 `reports/matsim_network/`、`reports/congestion_plausibility_audit_7_7e/` 下任何文件；
- ⛔ **不新增/删除**任何 7.9 系列既有节点的产物文件。

本节点**只**在 `reports/service_delay_mechanism_7_9g0/` 内写入。

**范围声明**：R0 回答的是「**`service` 延误的归属结构是什么**」，**不是**「如何修它」。任何"改 `service` 参数"的动作都属后续节点（7.9G-1+），且须另行预注册。

---

## 2. 冻结输入（Frozen inputs，只读）

| 逻辑名 | 路径（相对 `D:\Luan\2026-05\2_Singapore`） | size (B) | SHA256 |
|---|---|---|---|
| `ls_final` | `matsim_final_7_6h/outputs/W01_rc_min/ITERS/it.19/W01_rc_min.19.linkstats.txt.gz` | 22,629,291 | `b842b93a92f41c81248922078ebc68fdbe5ddc88f70086ccfd32bf955f0c1949` |
| `ls_viz_ref` | `matsim_viz_7_8/outputs/W01_events/ITERS/it.19/W01_events.19.linkstats.txt.gz` | 22,629,291 | `b842b93a92f41c81248922078ebc68fdbe5ddc88f70086ccfd32bf955f0c1949` |
| `net_links_runtime` | `matsim_viz_7_8/outputs/W01_events/W01_events.output_links.csv.gz` | 14,753,288 | `b65edfd5a59f233bb2e8d83384dbe07650dadbdae929ed6a378c0e3af0a6c5c9` |
| `src_copy` | `reports/matsim_network/network_links_source_copy.csv` | 52,670,157 | `b5265e5978608e7337712922b67f455b8c86c42c204ccc32a742da48180de9c6` |
| `cfg` | `matsim_final_7_6h/configs/config_W01_rc_min.xml` | 22,098 | `8f44fb349bff9cf1b2bfd497b914b291f9d79482936689a2f2b6a8ffcfc1206e` |

**★关键事实（已实测）**：`ls_final` 与 `ls_viz_ref` **逐字节相同**（同 SHA）⇒ 7.7E 所用 run 与 7.6h 冻结 run 的 `it.19` linkstats 是同一份，**口径可直接继承**。

## 3. 对照产物（Reference artifacts，只读、**不写入、不改动**）

| 逻辑名 | 路径 | size (B) | SHA256 |
|---|---|---|---|
| `e7e_audit_summary` | `reports/congestion_plausibility_audit_7_7e/audit_summary.json` | 13,098 | `e8bb8f7c02599ce9d49beaf0038b774397ad5965f159b6eafad242273573a4ee` |
| `e7e_roadtype_quant` | `reports/congestion_plausibility_audit_7_7e/e2b_roadtype_quantization.csv` | 2,182 | `5cc30ce1003a8894492884febb50d72a11185991db8b5e5c220997483d586105` |
| `e7e_sat_links` | `reports/congestion_plausibility_audit_7_7e/e2_saturated_links_0809.csv` | 7,828 | `723f11a840617de826bebbc91b29c23fcbdebb14487e34f6dd2931d62b262770` |

对照物仅用于**一致性断言**（gate 10 / 25），**不是**本节点结论的来源；本节点的一切数字均从 §2 冻结输入**独立重算**。

---

## 4. 对象与口径定义（冻结）

### 4.1 道路等级 `service`

取自 `src_copy.highway` 列（join 键 `link = "e" + from_node + "_" + to_node`）。**不**从 linkstats 推断。`net_links_runtime` 表**不含**道路等级列，故必须两表 join。

### 4.2 自由流与量化校正（**继承 7.7E，不得改动**）

```text
ff_s        = LENGTH / FREESPEED                (s)
ff_ceil_s   = ceil(ff_s - 1e-9)                 (s)   # 1 s 步长的向上取整
q_ratio     = ff_ceil_s / ff_s                  (无量纲)
has         = (HRS{h}avg > 0) & isfinite(TRAVELTIME{h}avg / ff_s) & (ff_s > 0)
```

**延误两种口径（必须并报）**：

```text
delay_raw_h  = Σ_has  v · max(0, TT − ff_s)     / 3600     (车时)   # 未扣量化
delay_corr_h = Σ_has  v · max(0, TT − ff_ceil_s)/ 3600     (车时)   # ★ canonical
```

其中 `v = HRS{h}avg`，`TT = TRAVELTIME{h}avg`。**主窗 h = 8-9**。

### 4.3 暴露面（★「占比必须声明暴露/里程/时间面」，四面并报）

| face | 分子 / 分母 |
|---|---|
| `time` | `delay_corr_h(service)` / `delay_corr_h(all)` |
| `count` | `n_loaded(service)` / `n_loaded(all)` |
| `distance` | `length_km(service)` / `length_km(all)` |
| `volume` | `vol(service)` / `vol(all)` |

**⛔ 任何情况下不得单独引用某一面的比例而不标注面名。**

### 4.4 `service` 参数溯源

```text
unit_cap = {motorway:1900, motorway_link:1700, trunk:1800, trunk_link:1600,
            primary:1500, primary_link:1300, secondary:1200, secondary_link:1100,
            tertiary:900, tertiary_link:900, residential:700, unclassified:600,
            service:400}
cap == unit_cap[highway] × permlanes   ?     # 逐链路精确比较（容差 1e-6）
```

`qsim` 覆盖：读 `cfg` 的 `flowCapacityFactor` / `storageCapacityFactor`。

---

## 5. 三个核心问题 → 可证伪构造

### Q1 `service` 延误是否集中在容量约束？

三个子构造，全部需报数：

1. **绑定度**：已载流 `service` 链路的 `v/c = v / CAPACITY` 分布（p50/p90/max）；饱和率 `v/c ≥ 0.9999` 的链路数与占比。
2. **★归属反转检验**：`sat_delay_share = delay_corr_h(v/c≥1 的 service 链路) / delay_corr_h(全部 service)`。
3. **集中度**：按链路 `delay_corr_h` 降序的 top-10 / top-100 / top-1% 份额；`service` 延误的 Gini。
4. **反事实（长度控制）**：`service` 按长度分桶（`≤5 / 5-8.9 / 8.9-15 / 15-30 / 30-60 / >60` m）报 `n / vol / delay_h / delay_share_pct / ff_med / vc_med / per_veh_s`。

### Q2 94.36% 在严格可比口径下是否稳定？

**口径矩阵**（每格都必须算出，不得留空）：维度 = `quantization ∈ {raw, corr}` × `hour ∈ {7-8, 8-9, 9-10, 10-11}`，外加 `inclusion ∈ {loaded, all}` 与 `exposure ∈ {time, count, distance, volume}` 四面。输出扁平表 `g0_caliber_matrix.csv`（列：`caliber_id, quantization, hour, inclusion, exposure, service_value, total_value, share, note`）。

### Q3 `service` 的 capacity/speed/lane 是"实现参数"还是"机制旋钮"？

1. **溯源精确度**：`cap == unit_cap × permlanes` 在 service 的精确匹配率（要求 ≥ 0.999999）。
2. **异质性**：service 的 `permlanes` 取值集合、`capacity` 取值集合、`freespeed` 取值集合（证明"service = 单车道 400"是否为过度概括）。
3. **qsim 覆盖**：两因子是否 = 1.0。
4. **分类**：按 §7 规则输出**单值**闭集判决。

---

## 6. 硬门（25）

门禁**必须携带实测值**；`checks.csv` 只在全部产物写盘后计算一次。

| # | gate_id | 判据 |
|---|---|---|
| 01 | `PREREG_FROZEN_AND_EMBEDDED` | 脚本内嵌 prereg SHA == 磁盘 prereg SHA |
| 02 | `SCRIPT_AST_COMPILE` | `ast.parse` + `compile` 均通过 |
| 03 | `ZERO_SIMULATION` | 无 `matsim`/`java` 导入、无 java 子进程 |
| 04 | `INPUT_MANIFEST_COMPLETE` | 5 件冻结输入存在且 SHA/尺寸与 §2 一致 |
| 05 | `LINKSTATS_154_COLUMNS` | linkstats 列数 == 154，必需字段全在 |
| 06 | `NETWORK_JOIN_COMPLETE` | `net_links_runtime` 全部行 join 到 `src_copy.road_type`（missing == 0） |
| 07 | `LINKSTATS_JOIN_COMPLETE` | `net_links_runtime` 全部行 join 到 linkstats（missing == 0） |
| 08 | `TRIPLE_FIELD_IDENTITY` | `length/freespeed/capacity` 三字段 net↔linkstats 逐位一致（`max|Δ| < 1e-9`） |
| 09 | `REF_LINKSTATS_BYTE_IDENTICAL` | `ls_final` SHA == `ls_viz_ref` SHA |
| 10 | `CANONICAL_RECOMPUTE_MATCHES_7E7E` | 重算 `service` `delay_corr_h` 份额 vs 7.7E `94.35657888849315`，`|Δ| ≤ 1e-6`（相对） |
| 11 | `Q1_CAPACITY_BINDING_REPORTED` | 绑定度表非空且含 p50/p90/max、饱和 n 与占比 |
| 12 | `Q1_CONCENTRATION_REPORTED` | top-10/100/1% 份额均存在且满足 `top10 ≤ top100 ≤ top1% ≤ 1`（量级序） |
| 13 | `Q1_LENGTH_CONTROL_REPORTED` | 长度分桶 6 桶齐全、非空 |
| 14 | `Q2_CALIBER_MATRIX_COMPLETE` | 口径矩阵行数 == 声明行数，无 NaN-by-omission |
| 15 | `Q2_RAW_VS_CORR_DECLARED` | `time` 面 raw 与 corr 份额**同时存在且有限**，且二者不相等（`|corr − raw| > 0`）—— 这是**口径敏感性存在性**的执行门，**不**断言 gap 的大小 |
| 16 | `Q2_STABILITY_BAND_CONSISTENT` | 跨时段带宽**已计算**（hour ∈ {7-8, 8-9, 9-10} 三值均有限）**且** `verdict_Q2` 与该带宽**内部一致**（`CALIBER_STABLE` ⟺ 三值 ∈ `[0.85,0.99]` 且极差 ≤ 0.05）—— **判决值本身不受门禁约束** |
| 17 | `Q3_CAPACITY_PROVENANCE_EXACT` | service `cap == unit_cap × permlanes` 精确率 ≥ 0.999999 |
| 18 | `Q3_QSIM_OVERRIDE_NONE` | `flowCapacityFactor == 1.0` 且 `storageCapacityFactor == 1.0` |
| 19 | `Q3_KNOB_CLASSIFICATION_SINGLE` | Q3 判决为闭集单值（见 §7） |
| 20 | `TRACEABILITY_FIELDS_COMPLETE` | 每张输出 CSV 的必需列齐全（见 §9） |
| 21 | `NO_WINDOW_MIXING` | 仿真/观测一律用 `HRS8-9avg` 族；仿真路径中**不出现** `HRS0-24avg` |
| 22 | `WRITEBACK_VERIFICATION` | `declared → exists → non-empty → recorded size == actual → recorded SHA == actual`；manifest↔磁盘↔closure **三方一致**；逐字节比对覆盖除 `checks.csv`/`input_manifest.json`/`closure_check.csv` 之外的产物 |
| 23 | `STRAY_ISOLATION` | 节点目录之外无新增文件（`_isolation_stray`） |
| 24 | `TERMINAL_STATE_THREE_WAY` | `checks`/`summary`/`report` 三处状态字符串一致 |
| 25 | `NON_7_9G_ARTIFACTS_UNCHANGED` | §2 五件输入 + §3 三件对照物在运行后 SHA 未变（8/8） |

**不动点要求**：`checks → report → summary → manifest → closure` 迭代至字节不变；**不收敛本身即失败**。`closure_check.csv` **不为自己写 artifact 行**（记 artifact 行数），以避免自引用破坏不动点。

---

## 7. 判决闭集（Decision boundary，**运行前冻结**）

**节点总状态**：`SERVICE_DELAY_R0_READY`（25/25、EXIT=0）｜`SERVICE_DELAY_R0_BLOCKED`（preflight 失败）。

| 问题 | 判决 | 规则（运行前设定） |
|---|---|---|
| Q1 | `CAPACITY_CONSTRAINT_DOMINANT` / `CAPACITY_CONSTRAINT_NOT_DOMINANT` | `sat_delay_share ≥ 0.50` ⇒ DOMINANT；否则 NOT_DOMINANT |
| Q2 | `CALIBER_STABLE` / `CALIBER_FRAGILE` | `time` 面 corr 份额在 hour ∈ {7-8, 8-9, 9-10} 上全部 ∈ `[0.85, 0.99]` 且极差 ≤ 0.05 ⇒ `STABLE`，否则 `FRAGILE`。**★`FRAGILE` 是合法结果，不使节点 BLOCKED**——门 16 只校验"带宽已算 + 判决与之自洽" |
| Q3 | `SERVICE_PARAMS_DERIVED` / `SERVICE_PARAMS_FREE_KNOB` | `cap==unit_cap×permlanes` 精确率 ≥ 0.999999 **且** qsim 无覆盖 ⇒ DERIVED；否则 FREE_KNOB |

**任一判决为"非预期侧"不构成节点失败**——R0 的价值在于给出可证伪的事实，而非取得某个期望答案。

---

## 8. 负例（Negative tests，可证伪反例）

每个负例必须**使对应门 FAIL 且 EXIT=1**；不做负例的门视为空门。

| # | 注入 | 期望失败门 |
|---|---|---|
| N1 | 从 linkstats 读取字段集中移除 `TRAVELTIME8-9avg` | 05 |
| N2 | 向 `net_links_runtime` 注入一条 `src_copy` 中不存在的 link | 06 |
| N3 | `net.length` 全体 +1 m | 08 |
| N4 | 延误改用 `delay_raw_h` 冒充 canonical | 10 |
| N5 | 集中度改为"全链路份额"（使 top10 == 1.0） | 12 |
| N6 | 把 `verdict_Q2` 硬编码为 `CALIBER_STABLE`（而带宽违反） | 16 |
| N7 | `unit_cap[service]` 由 400 改为 800 | 17 |
| N8 | 向某产物追加 1 字节 | 22 |
| N9 | 主窗改用 `HRS0-24avg` 族 | 21 |
| N10 | 触碰 §3 对照物（追加 1 字节） | 25 |
| N11 | 强制 `share_raw == share_corr` | 15 |

负例在**独立沙盒根** `reports/_r1r1_neg_r2` 之外新开 `reports/_g0_neg_root` 内执行；**不使用 `shutil.rmtree`**（本环境 >50 文件/轮会触发 `SAFE_DELETE_BULK_CONFIRM_REQUIRED`）。

---

## 9. 必需输出（Required outputs）

`reports/service_delay_mechanism_7_9g0/`：

| 文件 | 内容 | 必需列 |
|---|---|---|
| `g0_roadtype_delay_decomposition.csv` | 全等级延误分解 | `road_type,n_links,n_loaded,length_km,vol,ratio_vw,qratio_vw,delay_raw_h,delay_corr_h,share_corr_pct,share_raw_pct,sat_links` |
| `g0_caliber_matrix.csv` | 口径矩阵 | `caliber_id,quantization,hour,inclusion,exposure,service_value,total_value,share,note` |
| `g0_exposure_faces.csv` | 四面并报 | `face,service_value,total_value,share_pct` |
| `g0_service_capacity_binding.csv` | Q1 绑定度 | `metric,value,note` |
| `g0_service_length_buckets.csv` | Q1 长度控制 | `bucket,n,vol,delay_h,delay_share_pct,ff_med_s,vc_med,per_veh_s` |
| `g0_service_concentration.csv` | 集中度 | `rank_scope,share_pct,cum_delay_h` |
| `g0_parameter_provenance.csv` | Q3 溯源（按等级） | `road_type,n,cap_eq_unit_lanes_share,lanes_set,capacity_set,freespeed_set` |
| `g0_qsim_override.csv` | qsim 因子 | `param,value` |
| `g0_verdicts.csv` | 三判决 | `question,verdict,rule,evidence` |
| `g0_input_manifest.json` | 输入清单 + SHA | — |
| `g0_checks.csv` | 25 门 | `gate_id,pass,detail` |
| `g0_closure_check.csv` | 终局闭环 | — |
| `g0_summary.json` | 状态汇总 | — |
| `STEP7_9G0_REPORT.md` | 报告 | — |

---

## 10. BLOCKED 条件

`preflight` 失败（输入缺失／SHA 不符／linkstats 列数 ≠ 154／join 覆盖率 < 1）⇒ **必须是完整可审计节点**：

```text
坏输入 → preflight FAIL → 对应门 FAIL → 完整 25 行 checks.csv → summary.json
       → input_manifest.json → closure_check.csv → report.md → EXIT=1
```

后续门写 `"NOT_EVALUATED: preflight blocked"`。**⛔ 不得是"异常退出的半成品"。**

---

## 11. 版本边界

`7.9G-0` = service 线**第一个**节点，R0 结构审计 + 本 prereg。任何修改 §2/§3 输入、§4 口径、§6 门禁、§7 判决规则的动作 ⇒ `7.9G-0` 作废，升级为 `7.9G-0 v2`。

**本节点不产出**"如何修 `service`"的任何建议或参数改动——那属 `7.9G-1+`。
