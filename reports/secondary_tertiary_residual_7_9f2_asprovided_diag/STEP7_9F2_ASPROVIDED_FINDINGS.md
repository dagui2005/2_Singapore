# STEP 7.9F-2 — as-provided 审计发现（未修补，待裁定）

**日期**：2026-09-23
**对象**：`PREREG_7_9F2.md`（SHA256 `5c361b2d…f968bec`）+ `audit_secondary_tertiary_residual_7_9f2.py`（as-provided 42,883 bytes，备份 `scripts/od/audit_secondary_tertiary_residual_7_9f2.py.bak_asprovided_20260923`）
**执行方式**：零仿真、只读、`MECHANISM_AUDIT_READY` 判定未改动一字
**as-provided 运行结果**：`15/15 MECHANISM_AUDIT_READY`，EXIT=0

> ⚠️ 与 F-1 不同：F-2 as-provided **首跑即 15/15 全绿**。**全绿 ≠ 无缺陷**——本轮全部缺陷均**不被任何门禁捕获**。

---

## 一、静态核验（as-provided）

| 项 | 结果 |
|---|---|
| `HASH_EMBEDDED_MATCH` | ✅ True（`5c361b2de1731d6b4325bbcb3b739e85ce5fcc4fb02640e03a14239d5f968bec`） |
| `PY_COMPILE_PASS` / `AST_PARSE_PASS` / `IN_MEMORY_COMPILE_PASS` | ✅ True / True / True |
| `ZERO_SIM_IMPORT_VIOLATIONS` | ✅ 0（无 `subprocess` / `jpype` / `py4j`） |
| `HARD_CODED_GATE_CONSTANTS` | ✅ 0（AST 扫 `{"check":…,"pass":<常量>}` 字典） |
| `SELF_COMPARISON_PATTERNS` | ✅ 0（无 `x == x` / `e2` vs `e2.copy()` 类空门） |
| `MAIN_GUARD_PRESENT` | ✅ True |
| `MANIFEST_POST_WRITE_ASSERT` | ❌ **False**（无写后回查断言 → 见 F2-D1） |

**输入契约预检（全部通过）**：

| 输入 | 状态 | 关键 |
|---|---|---|
| `TrafficFlow_Data.json` | ✅ 16.3 MB | 1,311 唯一 LinkID（=E2 行数） |
| `TrafficFlow_Links.shp`（+`.prj`） | ✅ | `.prj`=**GCS_WGS_1984**，geopandas 读出 `EPSG:4326` → `to_crs(3414)` 米制有效；1,278 行 / 1,278 唯一 LinkID；全 `LineString` |
| `e1_crosswalk_candidates.csv` | ✅ 67,471 行 / 1,278 唯一 lta | tier：`A=6,455`、`B=9,328`、`C=51,688`（C 按 §2 剔除 → A+B = **15,783**） |
| `e2_section_residual_main.csv` | ✅ 1,311 行 | `valid_residual=True` 1,278 |
| `network_links_source_copy.csv` | ✅ 706,554 行 | `matsim_link_id = "e"+from+"_"+to` **零重复** |
| `network_nodes_source_copy.csv` | ✅ 429,032 行 | `x_svy21_m`/`y_svy21_m` = **米**（EPSG:3414 一致） |
| W01 `…/ITERS/it.19/…linkstats.txt.gz` | ✅ 22.6 MB / 154 列 | `LINK` + `HRS8-9avg` 齐备，693,575 唯一 |

**ID 契约**：`E1 matsim_link_id ⊂ network`（44,463/44,463）、`W01 ⊂ network`（693,575/693,575）。E1 有 128 个 matsim id 不在 W01，但**均未落入 sec/ter 选中集**（见下）。

---

## 二、复现验证（对照 R0 / F-1）—— 全部精确

| 检查 | 结果 |
|---|---|
| target 唯一性与集合 | `109` = E2 中 `diagnostic_highway∈{secondary,tertiary}` ∧ `valid_residual` ∧ `obs_8_9>0` 的**精确子集**（LinkID 集合相等 = True） |
| secondary / tertiary 计数 | `89 / 20`（= F-1 等级表 89 / 20） |
| **frozen residual 复现 F-1** | secondary `mean = −0.395459768956448`、`median = −0.560550867256637`；tertiary `mean = −0.560180563688507`、`median = −0.665904770393877` ⇒ **与 F-1 `CANONICAL_MEDIAN` 逐位相同（差 < 1e-15）** |
| **方向重算 vs E1** | F-2 由 shp 几何独立算的 LTA heading 与 network 节点算的 MATSim heading ⇒ `direction_diff_recomputed` 与 E1 `direction_diff_deg` 的 `max|Δ| = 0.000000`（109/109 断面） |
| 静默丢弃 | `593 selected` = `structure Σselected_total_n 593` = `direction_candidate_long 593`；选中链路 **0 条**缺 W01、**0 条**缺 network；`direction_n_recomputed ≠ selected_total_n` 的断面 = **0** |
| 邻居行数 | `1,635 = 109 × 3 半径 × 5 类`，section coverage = 1.000000 |
| 门禁 coverage | `F2.11 / F2.12 / F2.13 / F2.14` = 1.000000 / 1.000000 / 1.000000 / 1.000000 |

⇒ **F-2 的输入链、匹配选择、方向重算、frozen target 全部可信。**

---

## 三、缺陷清单（按严重度排序；全部未被门禁捕获）

### F2-D3 「首跑门禁求值早于产物写出」——**已第一手实证，最高优先**

`build_checks` 在 `main()` 中被调用**两次**（第 802 行、第 832 行）。第一次发生在 `f2_checks.csv` 写出（第 808 行）**之前**，而 gate 15 的 `declared` 列表包含 `f2_checks.csv` 本身。

**实证**（instrument 一份**副本**、输出到临时目录，未触碰 as-provided 脚本）：

```
[PROBE-FIRST-GATE] f2_checks.csv exists = False
[PROBE-FIRST-GATE] STEP7_9F2_REPORT.md exists = True
[PROBE-FIRST-PASS-STATUS] BLOCKED
[PROBE-FIRST-PASS-FAILS] ['F2.15_OUTPUT_PROVENANCE']
```

后果：**干净目录首跑时，第 808/820/821 行会先后落盘 `f2_checks.csv`（gate15=FAIL）、`f2_summary.json`（status=BLOCKED）、`STEP7_9F2_REPORT.md`（BLOCKED）**；靠第 832–841 行的第二次求值覆盖回 `READY`。本次之所以最终是 READY，只因第二次写覆盖了第一次。**若脚本在 808–832 之间中断，交付物将永久停留在 `MECHANISM_AUDIT_BLOCKED`。**

而且：第二次求值时全部声明产物都已写出 ⇒ **gate 15 在生效的那一次求值里恒为真（同义反复）**。

### F2-D1 「manifest 哈希陈旧 + 目录扫描未过滤 + 无写后断言」

`f2_input_manifest.json` 的 `generated_artifacts` 在第 829 行写出，**早于**第 836/840/841 行对 `f2_checks.csv` / `f2_summary.json` / `STEP7_9F2_REPORT.md` 的最终重写，且**没有任何写后回查断言**。

实测 14 条 manifest 条目中 **4 条陈旧**：

| 文件 | manifest 记录 | 磁盘实况 |
|---|---|---|
| `f2_checks.csv` | `12b19c90ccdd`, 968 B | `fd9601809175`, 966 B |
| `f2_summary.json` | `ad85bd621414`, 576 B | `001eed4f3cab`, 574 B |
| `STEP7_9F2_REPORT.md` | `f6c4c8ac1159`, 3903 B | `b74c2c4bb813`, 3900 B |
| `_run_asprovided.log` | `e195c1722a6c`, 388 B | `24ec24d48b58`, 2105 B |

**附加发现（环境）**：manifest 里有一条 **declared-but-absent**：`_run_asprovided.log.baiduyun.uploading.cfg`。即第 824 行 `out.iterdir()` 在运行时**捕获到了一个百度网盘同步进程的瞬时临时文件**，该文件现已不存在。⇒ `iterdir()` 未做名字/后缀过滤，任何外部瞬时文件都会污染 manifest，而**没有任何断言会发现它**。

> 注：`_run_asprovided.log` 是我自己用 shell 重定向写进官方目录的，因此被 manifest 捕获；已移至 `…_asprovided_diag/`。这是我的污染，非交付稿缺陷。

### F2-D2 「provenance 门覆盖面 < prereg §12 声明集」

`PREREG_7_9F2.md` §12 声明 **12** 个产物；脚本 gate 15 的 `declared` 列表只有 **11**，**缺 `f2_direction_candidate_long.csv`**。该文件确实写盘且进了 manifest，但**不被任何门禁覆盖**。

且 gate 15 仅断言"存在"，**不回查 sha256/size、不检查杂散文件、不比对 prereg §12 集合**。它的 detail 只有一句 `declared_outputs_exist=True`。

### F2-D4 「Q2（方向性）结构性退化 —— 静默 NaN + 一项未实现」【prereg 级，需裁定】

| 量 | 唯一值 | min | max |
|---|---|---|---|
| `selected_direction_good_share` | **1** | 1.0 | 1.0 |
| `selected_direction_twin_share` | **1** | 0.0 | 0.0 |
| `direction_good_share_recomputed` | **1** | 1.0 | 1.0 |
| `direction_twin_share_recomputed` | **1** | 0.0 | 0.0 |

全部 593 条选中候选的**重算方向差最大值 = 29.818094° < 30°**；**109/109 断面的候选全部"方向合格"**。

⇒ 这是**构造性的**：Tier A = `STRICT_SEMANTIC_DIRECTION`、Tier B = `DIRECTION_GEOMETRY`，**选择规则本身就以方向合格为前提**，因此无法用 A+B 集合回答"residual 是否随方向质量变化"。结果是 `f2_mechanism_summary.csv` 中 **3 行相关性为空白 NaN**（`selected_direction_good_share`、`selected_direction_twin_share`、`direction_good_share_recomputed`、`direction_twin_share_recomputed` 中的 4 个 → 实为 4 行空白），且 pandas 抛 `ConstantInputWarning`。

**另**：prereg §8 Q2 明文要求报告 **`reverse-candidate share`**，但脚本**全篇未实现**该项（无任何以 reverse 为名的变量或输出）。

⇒ **Q2 在本协议下不可答**；且"不可答"这一事实**不被任何门禁记录**。

### F2-D5 「matched baseline 口径：Σ 多链路 vs obs 单向计数 ⇒ Q4 指标构造性为正」【prereg 级，需裁定】

prereg §7 定义 `matched_flow_raw = Σ HRS8-9avg(selected matched directed links)`；而 E2 的 `diagnostic_residual_8_9` 基于**同一批链路的 median**。

实测同一批链路的两种口径：

| 断面 | 每断面选中链路数（min/median/max） | `Σ×SCALE/obs` 中位（= `matched_ratio_sum`） | E2 canonical `ratio` 中位 |
|---|---|---|---|
| secondary | 2 / 5 / 11 | **2.0281** | 1 − 0.5606 = **0.4394** |
| tertiary | — | **1.6541** | 1 − 0.6659 = **0.3341** |

⇒ **Σ 口径 ≈ median 口径的 4–5 倍**（≈ 每断面选中链路条数），并非"双向"两倍。因此：

| 半径 | `matched_ratio` 中位 | `added_share` 中位 | `envelope_ratio` 中位 | `\|env−1\|−\|match−1\|` 中位 | **改善(<0)占比** |
|---|---|---|---|---|---|
| 20 m | 1.928 | 2.105 | 4.527 | **+1.943** | **6.42%** |
| 50 m | 1.928 | 4.885 | 7.663 | **+4.584** | **3.67%** |
| 100 m | 1.928 | 9.401 | 12.120 | **+9.189** | **3.67%** |

⇒ `envelope_abs_residual_change` **在 93.6%–96.3% 的断面上为正**，是**构造性结果**：baseline 已是 1.93（Σ 口径），与"相对于 1（=obs）"的比较前提不成立；叠加邻域只会单调远离 1。**该指标当前不能回答"局部包络是否改善"**。

**同时暴露一个真实的量级问题**：100 m 半径时 `ALL_DIRECTION_ENVELOPE` 的 `added_share` 中位 = **9.40**（max 53.09），邻居条数中位 twin 26 / parallel 23 条。⇒ 100 m 在本地路网密度下**已吞入约 50 条链路**，更接近"走廊总量"而非"局地落点"。

> 注：prereg R-F2-5 已声明 sum 仅作 F-2 diagnostic、不改写 F-1 canonical median ⇒ **这不是"违规"，而是"§7 的定义与 §7·Q4 的比较前提之间不自洽"**。

### F2-D6 「`F2.04_E1_CANDIDATES` 门过弱」

`pass = len(cand) > 0`，detail 写 `candidate_rows=15,783`，但读入原始 67,471 行 ⇒ **detail 无法区分"C 档 51,688 条被剔除"这一事实**，"15,783"看似一个独立数字实则由过滤产生。

### F2-D7 「prereg §2 的 obs 推导规则实际未被使用」

§2 规定 TrafficFlow JSON 按"工作日、`HourOfDate=8`、先日代表值再 LinkID 取 median"得到 `obs_8_9`；脚本确实实现了（`load_traffic_json`），但**该 DataFrame 仅被 gate 03 用于计数**，全部分析直接取 E2 的 `obs_8_9`。⇒ 16.3 MB 的解析结果被丢弃，且**契约声明与实现口径不一致**（应显式声明"obs 以 E2 为准，JSON 仅作输入完整性校验"）。

---

## 四、建议处置

| 缺陷 | 类别 | 建议 |
|---|---|---|
| F2-D3 | 实现/顺序 | ✅ **v2 必修**：将 checks 收敛为**全部产物写盘后的单次终局求值** |
| F2-D1 | provenance | ✅ **v2 必修**：`iterdir()` 加后缀/名字过滤；manifest 移到**最后**并加**写后逐文件回查断言** |
| F2-D2 | provenance | ✅ **v2 必修**：`declared` 对齐 prereg §12 的 **12 项**；门 15 增加 sha256/size 回查 + 杂散文件检查 |
| F2-D6 | 门禁措辞 | ✅ **v2 必修**：detail 补 `raw_rows` 与 `dropped_C_rows` |
| F2-D7 | 契约披露 | ✅ **v2 必修**：manifest/报告显式声明 obs 来源为 E2 |
| **F2-D4** | **prereg 级** | ⚠️ **需裁定**：Q2 在 A+B 域内**不可答**。选项：① 如实登记为"结构性不可答 + reverse-candidate share 未实现"；② 发 `PREREG_7_9F2_v2.1` 把 Q2 改为"对 C 档/反向候选做方向性对照"（属**新增分析**，非修补） |
| **F2-D5** | **prereg 级** | ⚠️ **需裁定**：`Σ` 与 `obs` 不可比 ⇒ Q4 指标构造性为正。选项：① 保留 `Σ`（符合 §7/R-F2-5 原文）但**把 `envelope_ratio` 明标为"不与 1 可比"**，并把 Q4 改为**半径间/类型间对比**（prereg §8 Q4 原文其实只要求"呈系统性不同…不选最佳半径"）；② 增补**方向折叠后的 sum** 作第二口径（新增量，须另立 v2.1） |

**建议**：按 F-1 先例走 **`v2`**——只修 D1/D2/D3/D6/D7（实现与 provenance，**不动判据、阈值、口径数值**），对 **D4/D5 如实披露**并在报告边界中写明，**不擅自改变 prereg 定义**。若您要动 Q2/Q4 的提问方式，那属于 **v2.1（prereg 修订）**，需您明确授权。

---

## 五、附录：as-provided 原始输出

```
[1/6] target valid sections = 109
[2/6] selected candidates  = 593
[3/6] network links        = 706,554
[4/6] W01 links            = 693,575
[5/6] hard gates           = 15/15
[6/6] STATUS               = MECHANISM_AUDIT_READY
      NOTE                 = no MATSim/Java call
EXIT=0
```

`f2_mechanism_summary.csv`（as-provided 全文）：

| family | metric | spearman |
|---|---|---|
| MATCHING_STRUCTURE | selected_total_n | +0.0064 |
| MATCHING_STRUCTURE | selected_distance_median_m | +0.1443 |
| MATCHING_STRUCTURE | selected_direction_median_deg | +0.1986 |
| MATCHING_STRUCTURE | selected_direction_good_share | *(空/NaN)* |
| MATCHING_STRUCTURE | selected_direction_twin_share | *(空/NaN)* |
| MATCHING_STRUCTURE | same_highway_share | +0.1807 |
| DIRECTIONALITY | direction_median_recomputed_deg | +0.1986 |
| DIRECTIONALITY | direction_good_share_recomputed | *(空/NaN)* |
| DIRECTIONALITY | direction_twin_share_recomputed | *(空/NaN)* |
| LOCAL_FLOW_ENVELOPE | parallel_added_share@20m | +0.1361 |
| LOCAL_FLOW_ENVELOPE | twin_added_share@20m | −0.0330 |
| LOCAL_FLOW_ENVELOPE | same_name_parallel_added_share@20m | +0.0546 |
| LOCAL_FLOW_ENVELOPE | same_name_twin_added_share@20m | −0.0579 |
| LOCAL_FLOW_ENVELOPE | all_direction_envelope_abs_residual_change@20m | +0.1754 |
| LOCAL_FLOW_ENVELOPE | parallel_added_share@50m | **+0.6190** |
| LOCAL_FLOW_ENVELOPE | twin_added_share@50m | +0.0263 |
| LOCAL_FLOW_ENVELOPE | same_name_parallel_added_share@50m | **+0.5907** |
| LOCAL_FLOW_ENVELOPE | same_name_twin_added_share@50m | +0.0229 |
| LOCAL_FLOW_ENVELOPE | all_direction_envelope_abs_residual_change@50m | +0.2899 |
| LOCAL_FLOW_ENVELOPE | parallel_added_share@100m | **+0.6980** |
| LOCAL_FLOW_ENVELOPE | twin_added_share@100m | −0.0220 |
| LOCAL_FLOW_ENVELOPE | same_name_parallel_added_share@100m | **+0.7637** |
| LOCAL_FLOW_ENVELOPE | same_name_twin_added_share@100m | −0.0231 |
| LOCAL_FLOW_ENVELOPE | all_direction_envelope_abs_residual_change@100m | +0.3012 |

> ⚠️ **在 D5 口径问题解决前，上表 `LOCAL_FLOW_ENVELOPE` 各行不得作机制解释。**（`parallel/same_name_parallel` 的 +0.62/+0.70/+0.59/+0.76 看似是最强信号，但它建立在 `added_share` 这一与 obs 不可比的量上，且 D4 已表明 DIRECTIONALITY 家族为空 —— 先修口径，再谈机制。）

---

## 六、纪律核对

| 项 | 状态 |
|---|---|
| 启动 MATSim / 调用 Java | ❌ 未发生（AST 门 + 脚本无 subprocess） |
| 修改 network / capacity / lanes / speed | ❌ 未发生 |
| 修改 route-choice / scoring / QSim | ❌ 未发生 |
| 修改 7.3.6A / 7.6H / F-0 / F-1 / E1 / E2 / TrafficFlow | ❌ 未发生（均为只读） |
| 重算 SCALE | ❌ 未发生（`SCALE = 459794/200000`，与 v1.0 一致） |
| 产生 v1.1 | ❌ 未发生 |
| 输出隔离 | ✅ 仅写 `reports/secondary_tertiary_residual_7_9f2/`；诊断件入 `…_asprovided_diag/` |
| 回写 E2 frozen residual | ❌ 未发生（R-F2-1 遵守） |
