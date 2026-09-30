# STEP 7.9 F-2 Q4-R1 — as-provided 审计发现

**节点身份**：`reports/secondary_tertiary_residual_7_9f2_Q4_R1/`（as-provided）
**协议**：zero-simulation / read-only / diagnostic-only
**审计日期**：2026-09-27
**裁决预告**：**as-provided = `Q4_LOCAL_CAPTURE_BLOCKED`（崩在门禁之前）**；
单行修复探针可跑出 `25/25 PASS`，但**其中至少 5 门是空门或构造性恒真** ⇒ 该「全绿」不可采信。

---

## 0. 结论摘要

| 项 | 实测 | 判定 |
|---|---|---|
| 身份核验 | prereg `44d7f9c9…f7681`；script `df4da1a2…a65de` | ✅ 与声明逐位一致 |
| as-provided 实跑 | `EXIT=1`，崩于 `checks()` L1156 → L1073 | ⛔ **BLOCKED** |
| 崩溃原因 | `re.PatternError: unbalanced parenthesis at position 19` | 正则被双重转义 |
| 单行修复后 | `25/25 PASS / READY / CLOSURE=OK / EXIT=0` | ⚠️ **假绿** |
| 核心 nearest 规则 | 与我的独立实现 **593/593 逐位一致** | ✅ 规则本身实现正确 |
| 阶统计量偏倚 | 20→100 m 的 median ratio 增幅：R2 **+0.365/+0.499** → Q4-R1 **+0.020/+0.007** | ✅ 偏倚确已消除 |
| 邻域类型设计 | 冻结口径 **4 类（1308 格）**；实现 **2 类（654 格）** | ⛔ **偏离，需裁定** |
| 门禁语义 | 16 号恒真、25 号构造性恒真、20/22/24 号空门 | ⛔ **需重做** |
| 产物完整性 | manifest **2/11 陈旧**；closure 表 **3 行陈旧**；状态三处不一致 | ⛔ |

---

## 1. 身份核验

| 交付件 | 声明 SHA256 | 实测 | 结论 |
|---|---|---|---|
| `PREREG_7_9F2_Q4_R1.md` (7,132 B) | `44d7f9c995f49536cb1d3d141b237fd6bfbfaa6373ac6ef2c2001db48a2f7681` | 同 | ✅ |
| `audit_secondary_tertiary_residual_7_9f2_Q4_R1.py` (58,270 B) | `df4da1a2fda571899d2e68764e82f8354ce1d139ecfceee9e3c1ac0bdfaa65de` | 同 | ✅ |

- `AST_PARSE_PASS=True` / `COMPILE_PASS=True` / `ZERO_SIM_IMPORT=True`（imports 仅 `argparse, ast, gzip, hashlib, inspect, json, math, re, pathlib, numpy, pandas, scipy`）。
- `EMBEDDED_PREREG_SHA_MATCH=True`（脚本 L50 内嵌值与磁盘 prereg 一致）。
- 落盘：`scripts/od/audit_…_Q4_R1.py` == `.bak_asprovided` == 下载件（三者逐位一致）。
- 我的上一轮草案（`92d6c628…f84cf`，19,588 B）保留为
  `reports/…_Q4_R1_PREREG/PREREG_7_9F2_Q4_R1.md.bak_prior_draft_20260927`。

> ⚠️ 交付 prereg **不是**我草案的修订版，而是一份**重新撰写的精简版**（7,132 B vs 19,588 B）。因此必须逐条比对口径，不能假设继承。

**已确认纳入的两处改动**（用户本轮确认项）：
① `ratio_unavailable_reason ∈ {OK, NO_CANDIDATE, SELECTED_LINK_NOT_IN_W01}` 三态（prereg §6）✅；
② `selected_is_same_section_e1_candidate` 进入 schema，共 23 列（prereg §7）✅；
③ `Q4R1.21_RADIUS_MONOTONE_DISTANCE` 已采用软化措辞：「…does not prove all statistical bias has disappeared」✅。

---

## 2. as-provided = BLOCKED（第一手）

```
python scripts/od/audit_secondary_tertiary_residual_7_9f2_Q4_R1.py
→ File "..._Q4_R1.py", line 1975, in <module>   raise SystemExit(main())
→ File "..._Q4_R1.py", line 1757, in main       checks_rows = checks(...)
→ File "..._Q4_R1.py", line 1156, in checks     refs = referenced_check_keys(checks)
→ File "..._Q4_R1.py", line 1073, in referenced_check_keys
    re.findall(r'e1_detail\\["([^"]+)"\\]', src)
  re.PatternError: unbalanced parenthesis at position 19
→ EXIT=1
```

**根因（AST 抽取，非 shell 伪影）**：L1073 的字符串常量为
`e1_detail\\["([^"]+)"\\]`（字符序列含**两个** `0x5C`）。在正则里 `\\` 匹配一个字面反斜杠，随后 `[` **开启字符类**，把 `(` 吞进类内，于是索引 19 的 `)` 无对应 `(` ⇒ 编译失败。

正确写法应为 `e1_detail\["([^"]+)"\]`。

**这不是语法错误** —— `AST_PARSE_PASS` 与 `COMPILE_PASS` **一律抓不到**（与 7.9F-2 v2.1-R1 的 `KeyError` 属同一类：**语法全对、语义要命**）。

### 崩溃时的产物状态（13 件）

| 产物 | 状态 |
|---|---|
| 8 个分析 CSV（`target_sections` / `selected_ab_candidates` / `self_definition` / `candidate_grid` / `single_link_capture` / `summary.csv` / `group_summary` / `selection_audit`） | ✅ 完整（崩溃前已写） |
| `q4r1_checks.csv` | ⛔ 9 B `PENDING` |
| `q4r1_closure_check.csv` | ⛔ 9 B `PENDING` |
| `q4r1_summary.json` | ⛔ 76 B `PENDING` |
| `q4r1_input_manifest.json` | ⛔ 51 B `PENDING` |
| `STEP7_9F2_Q4_R1_REPORT.md` | ⛔ `STATUS: PENDING` |

⇒ **25 门一条都没有被求值**；`status` 从未计算。

---

## 3. 单行修复探针 ⇒ 假绿 25/25

按项目纪律生成了**只改那一行**的探针（`scripts/od/_probe_q4r1_regexfix.py`，58,268 B，`b6f74425…48548`）：

- 反向替换可**逐字节复原**原文件 ⇒ 改动面 = 恰好 1 行（byte delta = **−2**，即删掉两个多余反斜杠）；
- 正则只被**契约门**使用，从不参与任何分析计算 ⇒ **分析中性**。

**探针结果**：

```
target=109; E1=67,471; anchors=593; network=706,554; W01=693,575; grid=654
checks=25/25; STATUS=Q4_LOCAL_CAPTURE_READY; CLOSURE=OK   EXIT=0
```

⇒ **只要修正则，整份报告就是「全绿收口」。而其中有多门根本不具备失效能力。**
这正是我们反复固化的反模式：**as-provided 全绿 ≠ 无缺陷**。

---

## 4. 25 门逐门判定（有牙 / 空门 / 越界）

| # | gate | 判定 | 依据 |
|---|---|---|---|
| 01 | `PREREG_HASH` | ✅ 有牙 | 比对磁盘 prereg sha |
| 02 | `ZERO_SIMULATION` | ✅ 有牙 | AST 扫 subprocess/Java |
| 03 | `E1_RAW_QUALITY` | ✅ 有牙 | `raw_rows/raw_id_missing/raw_bad_tier`（**R2-1 契约修复已继承**） |
| 04 | `E2_TARGET_UNIQUE` | ⚠️ 弱 | 硬编码 `len(target)==109`（与 07 重复） |
| 05 | `NETWORK_PREFLIGHT` | ⚠️ **名不副实** | `checks()` 内判据仅 `len(network)>0`；**真正的 preflight 在 early-branch**（见 §5.4） |
| 06 | `W01_PREFLIGHT` | ⚠️ 同上 | `len(stats)>0 and not duplicated` |
| 07–11 | 样本量 / 覆盖率 | ✅ 有牙 | 阈值来自冻结量 |
| 12 | `E2_CANONICAL_COMPLETE` | ✅ | 新增，合理 |
| 13 | `W01_CAPTURE_COVERAGE` | ✅ | 新增，合理 |
| 14 | `OUTPUT_PROVENANCE` | ⚠️ 部分 | 显式**豁免 5 个终局产物**，故 checks/closure/summary/manifest/report 的存在性不受此门约束 |
| 15 | `ISOLATION` | ✅ 有牙 | T7 实测 FAIL；但 `old_dirs` 含**不存在的** `…_7_9f2_R2`，且漏检 R0/v2/R1/Q4_R1_PREREG |
| **16** | `FINAL_CLOSURE_FILES` | ⛔ **构造性恒真** | 判据仅 `closure_check.csv.is_file() and summary.json.is_file()`，而这两份在 `checks()` **之前**已由占位符写出 ⇒ **永不失败**；T6 实测 |
| 17 | `LOADER_CHECKS_CONTRACT` | ✅ 有牙（窄） | 正则仅捕获 `e1_detail["…"]` 字面形式 |
| 18 | `GRID_COMPLETE` | ⚠️ 有牙但**标定错** | `expected = len(target)*len(RADII_M)*2` —— **把「只有 2 类邻居」写死成期望值**（见 §5.1）；T9 实测可得 FAIL |
| 19 | `SCHEMA_AND_MISSINGNESS_ACCOUNTING` | ✅ 有牙 | T5 实测 FAIL |
| **20** | `SELECTION_REDERIVED` | ⛔ **空门** | 见 §5.2 |
| 21 | `RADIUS_MONOTONE_DISTANCE` | ✅ 有牙 | T1/T2/T4b 实测 FAIL |
| **22** | `EXCLUSION_AND_CONTAINMENT` | ⛔ **空门 + 名不副实** | 见 §5.3 |
| 23 | `SELECTION_FLOW_BLIND` | ⚠️ 有牙但**可绕过** | 见 §5.5 |
| **24** | `Q4_TRACEABILITY` | ⛔ **空门**（且不在冻结清单内） | T8 实测：全部 ID 改成 `BOGUS_*` 仍全绿 |
| **25** | `NON_Q4_ARTIFACTS_UNCHANGED_VS_R2` | ⛔ **构造性恒真 + 前提不成立** | 见 §5.6 |

---

## 5. 五处硬缺陷

### 5.1 邻域类型：冻结 4 类 → 实现 2 类

- 冻结口径：`neighbor_type ∈ {parallel, twin, same_name_parallel, same_name_twin}`（**109 × 3 × 4 = 1308**）。
- 实现（L711–714）：只有 `("parallel", …), ("twin", …)` ⇒ **654**。
- `expected_grid = len(target) * len(RADII_M) * 2`（L1161）—— **把 2 写死成期望值**，于是 18 门对 654 判 PASS。
- prereg §4 也只列 parallel/twin；但 **prereg §10 仍写「target grid = 1,308 section × radius × type cells」** ⇒ **prereg 自相矛盾**。
- 对照：我上一轮草案（含 4 类、1308 格）与 R2 节点（4 类、1308 行）**都是 4 类** ⇒ 本轮是相对 R2 的**功能缩减**。

### 5.2 第 20 门不是「独立重导」

`independent_selection_audit()`（L878–921）的全部逻辑：
```python
ok = (r["selection_rule"] == "<常量字符串>") and (r["reason"] in {闭集})
```
**它从不重新计算选择**，只把存下来的规则字符串与常量比对。
⇒ 只要代码继续写同一个字符串，此门**永远 PASS**，与"数据里是否真是 nearest"无关。

**实证（T2）**：把选链改成 `eligible[-1]`（取**最远**），而 `selection_rule` 字面量未动 ⇒ 选择已**明确违反规则**，但第 20 门**静默**（最终是第 21 门顺手抓到）。

> 用户本轮原话：「**Q4R1.21 独立重导尤其重要：它能把『代码恰好实现了 nearest』与『我们从数据重新得到 nearest』区分开。**」
> 交付实现**没有做到这一点**。

**我替它做了**：用冻结前独立编写的可行性探针（另一套实现）逐格对照交付版 ⇒
`selected_neighbor_link_id` **593/593 完全一致**（654 行中 61 行为双方同为 `NO_CANDIDATE`），
`nearest_single_link_ratio` / `capture_error_change` / `n_candidates` **max|Δ| = 0**，距离 max|Δ| = 3.6e-15。
⇒ **核心规则本身实现正确**，只是**没有门禁去证明它**。

### 5.3 第 22 门只查 SELF，且只查「自己算出来的 SELF」

判据仅 `not any(selected_is_self)`；而 `selected_is_self` 是 `build_grid` 内用**同一个** `self_id` 算出的派生列。
⇒ 一旦排除逻辑被破坏，**派生列与判据同时失真**，门禁失明。

**实证（T3）**：令 `self_id = ""`（等价于取消 SELF 排除）⇒
选中结果**改变 67 行**，其中 **6 行确实选中了该断面自身的 SELF 链路**（例：断面 `134926` → `e124434_4710`，3.92 m），
而 `selected_is_self` 报 **0**，第 22 门 **25/25 全绿**。

此外：门名含 `AND_CONTAINMENT`，但**既未独立校验 focal-anchor 排除，也未校验半径候选集的嵌套包含关系**。

### 5.4 05/06 号门与 preflight 的职责错位

真正的 `preflight_network()/preflight_w01()` 只在 `main()` 的 **early-branch**（L1565–1628）使用；
`checks()` 里的同名门只剩 `len(...)>0`。

**early-branch 实测有效**（复用 R1 反例输入）：

| 例 | 注入 | 结果 |
|---|---|---|
| N1 | network 重复 `link_id` | `05=False (duplicate_link_id:1)`，`status=BLOCKED`，`EXIT=1` ✅ |
| N2 | nodes 重复 `node_id` | `05=False (node_duplicate_id:1)`，同上 ✅ |
| N3 | W01 重复 `LINK` | `06=False (duplicate_link:1)`，同上 ✅ |

⇒ **坏输入确实走受控收口，不再崩溃**（相比 R1 的「0 产物崩溃」是实质进步）。

**但 BLOCKED 路径不完整**：只写 **3 件**（`checks.csv` / `summary.json` / `report`），
**没有 `closure_check.csv`、没有 `input_manifest.json`**；且 `checks.csv` **只有 2 行**（05/06），
不是 25 行 ⇒ 审计者无法从产物看出"共 25 门、其中 23 门未求值"。
（R2 的受控收口标准是 **5 件齐**。）

### 5.5 第 23 门可被绕过

判据是在源码里取 `eligible = sorted(` 与 `selected_id =` **之间的词窗**，看是否出现 `flow_map`。

**实证**：
- **T1b**（在词窗内插入 `flow_map` 引用）⇒ `23=False` ✅ **门有牙**；
- **T1**（把 `max(eligible, key=flow_map.get)` 写进 `selected_id = ( … )` 赋值表达式**之后**）⇒ 词窗只到 `selected_id =` 为止，**`flow_map` 落在窗外** ⇒ 第 23 门**未触发**（该例最终由第 21 门因单调性被破坏而抓到）。

⇒ 这是一门**依赖词法位置**的门，**不是语义门**。

### 5.6 第 25 门：构造性恒真 + 前提不成立

```python
inherited_r2 = output_dir.parent / ("secondary_tertiary_residual_7_9f2_R2")   # L1240
inherited_compare = not inherited_r2.exists()                                 # L1244
```
- 路径名**错**：真实冻结节点是 `secondary_tertiary_residual_7_9f2_**v2_1**_R2`（存在，15 件）。
  脚本指向的 `…_7_9f2_R2` **不存在** ⇒ `not exists()` 恒为 `True` ⇒ **此门永不失败**。
- 脚本自己在 detail 里承认：「*local gate only verifies no shadow R2 directory*」—— **根本没做字节比对**。
- **更根本**：prereg §12 的 required outputs 里 **没有任何「继承的非 Q4 产物」**（只有 `q4r1_*` + report）。
  Q4-R1 节点 13 件产物中，**不存在** `q2_correlations` / `direction_candidate_*` / `obs_rebuild_check` / `all_e1_candidates` 等。
  ⇒ **「与 R2 逐字节相同」在本节点内无法被验证**，该门写成这样**必然要么恒真、要么永假**。

---

## 6. 负向测试矩阵（全部第一手）

变体脚本：`scripts/od/_probe_q4r1_neg_<name>.py`（均由探针单点变异生成）。

| 测试 | 注入 | 门数 | FAIL | 触发门 | 判读 |
|---|---|---|---|---|---|
| **T1** | 选择改为 `max(flow)`，写在 `selected_id = (…)` 内 | 25 | 1 | `21_RADIUS_MONOTONE` | 第 23 门**被绕过** |
| **T1b** | 词窗内插入 `flow_map` 引用 | 25 | 1 | `23_SELECTION_FLOW_BLIND` | 词窗内**有牙** |
| **T2** | 选择改为 `eligible[-1]`（取最远），规则串不动 | 25 | 1 | `21_RADIUS_MONOTONE` | ⛔ **第 20 门静默** ⇒ 空门实证 |
| **T3** | 取消 SELF 排除（`self_id = ""`） | 25 | **0** | —（全绿） | ⛔ **第 22 门失明**；6 行真泄漏 SELF |
| **T4** | `d20 += 5` | 25 | 0 | — | ⚠️ **我方 harness 符号错误，非有效负例**（见下） |
| **T4b** | `d50 += 5`（真逆序） | 25 | 1 | `21_RADIUS_MONOTONE` | ✅ 第 21 门有牙（159/159 行逆序被抓） |
| **T5** | 非法 reason 词元 | 25 | 2 | `19_SCHEMA…`, `20_SELECTION_REDERIVED` | ✅（20 门只对 reason 敏感，非对选择） |
| **T6** | 终局占位符写成 0 字节 | 25 | **0** | —（全绿） | ⛔ **第 16 门恒真** + **状态三处不一致** |
| **T7** | 往 R2 目录放 `*Q4_R1*` 杂物 | 25 | 1 | `15_ISOLATION` | ✅ |
| **T8** | 所有选中 ID 改成 `BOGUS_*` | 25 | **0** | —（全绿） | ⛔ **第 24 门空门** |
| **T9** | 只保留 1 类邻居（→327 格） | 25 | 1 | `18_GRID_COMPLETE` | ✅（但期望值写死 654） |
| **N1** | network 重复 link | **2** | 1 | `05_NETWORK_PREFLIGHT` | ✅ 受控收口，EXIT=1 |
| **N2** | nodes 重复 id | **2** | 1 | `05_NETWORK_PREFLIGHT` | ✅ 同上 |
| **N3** | W01 重复 LINK | **2** | 1 | `06_W01_PREFLIGHT` | ✅ 同上 |

### 关于 T4 —— 必须澄清我自己的错误

T4 把 `d20` **加 5**，得到 `d20 > d50`，而门禁要求 `d20 ≥ d50` ⇒ **加大的方向恰是门禁期望的方向**
（因为 `Pool(20) ⊆ Pool(50) ⇒ min(Pool(20)) ≥ min(Pool(50))`）。
⇒ **T4 不是有效负例，不能用来指控第 21 门**；我随后补了 T4b（抬 d50 制造真逆序）才得到有效结果。
此条按项目纪律如实披露：**harness 出错时先怀疑 harness**。

### T6 的复合发现（状态三处不一致）

```
gates:  25/25 PASS（含 16_FINAL_CLOSURE_FILES）
summary.json: status = Q4_LOCAL_CAPTURE_BLOCKED_CLOSURE_FAILED, closure = CLOSURE_FAILED
report:       **STATUS: Q4_LOCAL_CAPTURE_READY**   ← 与 summary 冲突
EXIT=1
```
根因：`final_status` 改写后 **report 仍用旧 `status` 重写**（L1928–1932），且 `final_status` 硬编码 `…_BLOCKED_…` 前缀、
忽略 `status` 原本是 READY。⇒ **终局三处（checks / summary / report）不一致**。
（这正是 R2 中我修过的 N10 缺陷的**复发**。）

---

## 7. 分析层结论（这部分是好消息）

### 7.1 核心规则实现正确（我已独立复现）

见 §5.2。

### 7.2 阶统计量偏倚确实被消除

12 层口径完全对齐（**每层 `n` 与 R2 相同**，故为同分母对照）：

| hw | type | R2 median ratio<br>20 → 50 → 100 m | Q4-R1 median ratio<br>20 → 50 → 100 m |
|---|---|---|---|
| secondary | parallel | 0.1562 → 0.4563 → **0.5212**（+0.365） | 0.0324 → 0.0656 → **0.0525**（**+0.020**） |
| secondary | twin | 0.5045 → 0.5711 → 0.5960（+0.092） | 0.4431 → 0.4431 → 0.4398（−0.003） |
| tertiary | parallel | 0.1106 → 0.4631 → **0.6092**（+0.499） | 0.0972 → 0.1039 → **0.1039**（**+0.007**） |
| tertiary | twin | 0.3605 → 0.3018 → 0.3647（+0.004） | 0.3018 → 0.2140 → 0.2140（−0.088） |

**R2 的 `max over N(r)` 会让「候选变多 ⇒ 最大值机械升高」，parallel 层尤其明显；Q4-R1 的 nearest 平掉了它。**

全局：`median ratio` **0.4716 → 0.2351**；`capture_improved share` **0.4503 → 0.3103**；
`exact-zero change share` **0.1204 → 0.0776**。
⇒ R2 里「改善」有相当部分是**机械的**，换成最近链路后回落到更保守的水平。这是 **Q4-R1 最有价值的科学产出**。

### 7.3 冻结量全部保持

`target=109（sec 89 / ter 20）`、`E1=67,471`、`anchors=593`、`network=706,554`、`W01=693,575`、
`SCALE=2.29897`、30°/150°、20/50/100 m；七个冻结输入源 sha256 全部 OK；manifest 内 5 个输入回查 OK。

### 7.4 ★别名性（aliasing）比上一轮更严重，且**本轮已可逐条追溯**

`same_section_e1_share_parallel_100m` = **0.988764**（secondary）/ **1.0**（tertiary）；
twin 均为 **1.0**；`self_selected_share_100m` = 0.0。

即：**在 100 m 处，几乎 100% 的「邻居」其实就是目标断面自己的 E1 候选链路**（上一轮我测得 1121/1308 = 85.7%，本轮在 100 m 层更高）。
`exact_zero_change_share_100m` = **0.0618**（sec）/ **0.175**（ter）—— 这些"精确零"主要是
「选中链路与 E2 `sim_8_9_scaled` 来源边重合」造成的**同一性**，不是独立的平行道路巧合。

好消息：本轮 schema 已含 `selected_is_same_section_e1_candidate`，**可逐条追溯**（上一轮只能写在报告散文里）。

### 7.5 缺失结构

`ratio_unavailable_reason`：**OK 593 / NO_CANDIDATE 61 / SELECTED_LINK_NOT_IN_W01 0**。
即**流量盲选链未引入任何新的缺失类别**（与我冻结前探针的预期一致）。
20 m 处 parallel 层缺失最多（secondary 52/89 有效，tertiary 9/20 有效）。

---

## 8. 产物完整性缺陷

### 8.1 manifest 陈旧（2/11）

manifest 在 L1782–1828 生成，**早于** `summary.json` 定稿（L1849 起）与 report 重写（L1858/L1928）：

| 产物 | manifest 记录 | 磁盘实际 |
|---|---|---|
| `STEP7_9F2_Q4_R1_REPORT.md` | 1,989 B | **3,921 B** |
| `q4r1_summary.json` | 76 B | **405 B** |

⇒ 记录的是**占位符**哈希。而**没有任何门禁检查 manifest** ⇒ 错误静静出厂。

### 8.2 closure 表自身陈旧（3 行）

`closure_df` 在 L1866–1897 计算，**早于** `closure_check.csv` 落盘、`summary.json` 定稿、report 重写：

| 行 | closure 记录 | 磁盘实际 |
|---|---|---|
| `q4r1_closure_check.csv`（自身） | size 9 / sha `52b267e1…`（**占位符**） | 1,508 B / `352ed3e2…` |
| `q4r1_summary.json` | 410 B | 405 B |
| `STEP7_9F2_Q4_R1_REPORT.md` | 3,926 B | 3,921 B |

⇒ **终局闭环产物在描述自己未完成时的样子**。且 `closure_ok` 之后**不再回查**，也**没有 manifest ↔ 磁盘对账**。

---

## 9. 边界声明（本轮未越界）

- ⛔ 未改 `target` / `E1` / `E2` / `network` / `nodes` / `capacity` / `lanes` / `speed` / `SCALE` / `E2 frozen residual`；
- ⛔ 未回写 E2，未产生 v1.1，未改 7.3.6A / 7.6H / F-0 / F-1 / F-2 v2 / R2；
- ⛔ 未运行 MATSim / Java；
- ⛔ 未修改交付件（下载件、正本、`.bak_asprovided` 三者逐位一致）；
- ⛔ 未改 Q4-R1 的选择规则、阈值、样本域（探针与变体**只作用于脚本副本**）；
- ✅ 早期节点目录零污染：R0 13 件 / v2 15 件 / v2.1 1 件 / R1 14 件 / R1_PREREG 1 件 / R2 15 件 / R2_PREREG 1 件 —— `q4stray` 全部为 `[]`，mtime 未变。

---

## 10. 处置建议（需用户裁定）

**不可再走「方案 C（接受 BLOCKED）」**：本轮不是科学问题卡死，而是一处**精确到字符**的转义错误 + **5 门空门**，全部可纯执行层修复。

- **方案 A（推荐）：开 `F-2 Q4-R1-R1`，仍限定为「执行契约闭环修复」**
  1. **R1-1** 修正 L1073 正则（`\\[` → `\[`、`\\]` → `\]`）；
  2. **R1-2** **第 20 门改为真·独立重导**（第二套实现，向量化重算 nearest，逐行比对 ID + 距离），
     并保留我这次的 593/593 作为**预注册期望值**；
  3. **R1-3** **第 16 门**改为「写后回查」：物化 `closure_check.csv`，逐项 size/sha256 对账，
     并**回读** checks/summary/report 三处状态一致性；**manifest 最后生成、不自哈希**，且**加一门检查 manifest ⊆ 磁盘**；
  4. **R1-4** **第 22 门**改为**独立**校验：直接从候选池重算 `selected ∉ ANCHOR ∪ SELF`（不读派生列），并补上嵌套包含关系；
  5. **R1-5** **第 24 门**加 ID 一致性：`selected_neighbor_link_id` 必须 ∈ 该 (断面, 半径, 类型) 的 eligible 池，且其
     distance/direction/name/highway/flow 必须与 `candidate_grid` 中该 ID 的记录**逐字段一致**；
  6. **R1-6** **第 23 门**改为**语义/AST 门**（扫 `build_grid` 全函数体中是否存在 flow/residual 标识符参与排序或选择），不再依赖词窗；
  7. **R1-7** **第 25 门**：把 `…_7_9f2_R2` 改为 `…_v2_1_R2`；若坚持要求非 Q4 产物与 R2 逐字节相同，
     则**必须先把那 8 件产物纳入本节点 required outputs**，否则该门应**明确标为 `NOT_APPLICABLE_AS_DEFINED`** 并降级为报告项；
  8. **R1-8** **BLOCKED 路径补全**：受控收口也写 `closure_check.csv` + `input_manifest.json`，
     且 `checks.csv` 写**全 25 行**（未求值者标 `NOT_EVALUATED`）；
  9. **R1-9** **状态一致性**：`final_status` 必须由「最终产物 + 最终检查」共同决定，且 checks/summary/report 三处同步。

- **方案 B**：把「4 类→2 类」的设计缩减**正式接受**，并据此改写 prereg §4/§10（1308→654）、
  门编号对齐用户冻结清单（GRID 归位到 19）、`SELECTION_FLOW_BLIND_STATIC` 恢复原名、删除/并入 `Q4R1.24_Q4_TRACEABILITY`；
  然后只做 A 的 R1-1…R1-3、R1-5…R1-9。
  （**不推荐**：等于在 2 类设计上盖章，而 R2 已按 4 类交付过，会造成同层不可比。）

- **方案 C**：不接受（见上）。

### 需要你先定的两件事

1. **邻域类型到底 2 类还是 4 类？**
   - 若 4 类 ⇒ prereg 与代码都要补 `same_name_parallel` / `same_name_twin`（我的草案里有判定口径：与 focal anchor 的 `name_norm` 相同）；
   - 若 2 类 ⇒ 必须**明文**说明与 R2 的 4 类不可直接比较，并把 `<n>` 的对照表限定在同层。
2. **第 25 门的去留**：Q4-R1 是否应当**继承输出** R2 的 8 件非 Q4 产物（以便真的做字节对账），
   还是承认该门在 Q4-R1 内**不适用**？

---

## 11. 复现命令

```bash
cd "D:/Luan/2026-05/2_Singapore"

# 身份 + 静态 + 落盘
C:/Users/LQP/miniconda3/python.exe scripts/od/_q4r1_static_and_deploy.py

# as-provided（预期崩溃）
C:/Users/LQP/miniconda3/python.exe scripts/od/audit_secondary_tertiary_residual_7_9f2_Q4_R1.py

# 单行修复探针（预期 25/25 READY）
C:/Users/LQP/miniconda3/python.exe scripts/od/_probe_q4r1_regexfix.py \
  --out-dir reports/_q4r1_probe_run/secondary_tertiary_residual_7_9f2_Q4_R1

# 生成并运行负向变体
C:/Users/LQP/miniconda3/python.exe scripts/od/_make_q4r1_negatives.py
C:/Users/LQP/miniconda3/python.exe scripts/od/_probe_q4r1_neg_T2_union_reversed.py \
  --out-dir reports/_q4r1_neg_T2_union_reversed/secondary_tertiary_residual_7_9f2_Q4_R1
```

## 12. 本轮新增文件

| 路径 | 说明 |
|---|---|
| `reports/…_Q4_R1/`（13 件） | **as-provided 崩溃留痕**（5 件终局产物 `PENDING`） |
| `reports/…_Q4_R1_asprovided_diag/` | 本报告 + 16 个运行日志 |
| `reports/…_Q4_R1_PREREG/` | 交付 prereg（`44d7f9c9…`）+ `.bak_prior_draft_20260927`（`92d6c628…`） |
| `reports/_q4r1_probe_run/`（13 件） | 单行修复探针输出（25/25 READY） |
| `reports/_q4r1_neg_*/`（14 组） | 负向测试输出 |
| `scripts/od/audit_…_Q4_R1.py` (+`.bak_asprovided`) | 交付脚本正本 |
| `scripts/od/_probe_q4r1_regexfix.py` | 单行修复探针（分析中性） |
| `scripts/od/_probe_q4r1_neg_*.py`（10 个） | 负向变体 |
| `scripts/od/_q4r1_static_and_deploy.py` / `_make_probe_q4r1.py` / `_make_q4r1_negatives.py` | 工具 |
