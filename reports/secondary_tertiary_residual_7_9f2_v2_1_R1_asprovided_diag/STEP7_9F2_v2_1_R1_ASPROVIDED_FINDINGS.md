# Step 7.9F-2 v2.1-R1 — as-provided 审计发现报告

**口径：ZERO SIMULATION / READ-ONLY / DIAGNOSTIC ONLY。未运行 MATSim / Java；未回写任何冻结节点。**

**一句话结论：R1 的 8 项修补中 6 项实测有效、2 项只落实一半；同时引入 1 处新的硬契约缺陷，导致 as-provided 在门禁构造时即崩溃 ⇒ R1 as-provided = `BLOCKED`，不能作为正式节点收口。**

---

## 1. 身份核验（全部相符）

| 对象 | SHA256 | 声明值 | 判定 |
|---|---|---|---|
| `PREREG_7_9F2_v2_1_R1.md` | `13401c3f7c9542c8f5a4d28197c5ade7e56294286f620a160a73d5de517fcadf` | 同左 | ✓ MATCH（1,970 B） |
| `audit_secondary_tertiary_residual_7_9f2_v2_1_R1.py` | `d4100dbd0b091753f89a8baa9d93e963d3fcd929612f994f6d052e8adb19af25` | 同左 | ✓ MATCH（28,895 B） |

静态自检复现：`AST_PARSE_PASS=True` / `IN_MEMORY_COMPILE_PASS=True` / `HASH_EMBEDDED_MATCH=True` / `ZERO_SIM_IMPORT=True`（imports 仅 `argparse, ast, gzip, hashlib, json, math, re, pathlib, numpy, pandas, scipy`）。

落盘：脚本 → `scripts/od/`（正本 + `.bak_asprovided_20260926`，与下载件**逐位一致**）；prereg → `reports/secondary_tertiary_residual_7_9f2_v2_1_R1_PREREG/`。

> ⚠️ **门禁条数：17 条**，不是 16 条。prereg §Hard gates 逐项列举 = 代码 `checks()` 返回列表 = **17**（v2.1 是 16）。你提到的「16/16 PASS」应为 **17/17**。

---

## 2. as-provided 实测：**崩在门禁之前**

```
STEP 7.9F-2 v2.1-R1 | EXECUTION / CONTRACT REPAIR
PREREG SHA=13401c3f7c9542c8f5a4d28197c5ade7e56294286f620a160a73d5de517fcadf
W01=...\ITERS\it.19\W01_rc_min.19.linkstats.txt.gz          <-- P0-1 修补生效
OUTPUT=...\reports\secondary_tertiary_residual_7_9f2_v2_1_R1
Traceback (most recent call last):
  File "..._R1.py", line 275, in main
    cks=checks(...)
  File "..._R1.py", line 225, in checks
    raw_ok=cand_detail["raw_rows"]>0 and cand_detail["raw_id_missing"]==0 and cand_detail["raw_bad_tier"]==0
KeyError: 'raw_id_missing'
EXIT=1
```

**已越过的关卡**：`locate_w01()` 正确把目录解析为唯一 `W01_rc_min.19.linkstats.txt.gz`（P0-1 ✓）；`q4()` 正常执行（P0-2 ✓，`name_norm` 未再触发 AttributeError）。崩溃点在 **产物写完之后的门禁构造**。

**留痕**：`reports/secondary_tertiary_residual_7_9f2_v2_1_R1/` 共 **14 件**，其中 `f2v21r1_checks.csv` = `PENDING`、`f2v21r1_input_manifest.json` = `PENDING`、`f2v21r1_summary.json` = `{"status":"PENDING"}`、报告 `**STATUS: PENDING**`。**10 个分析 CSV 是完整写出的**（值可用，但节点身份无效）。

---

## 3. 缺陷清单（按严重度）

### 🔴 R1-N1（P0，**新增**）门禁引用了 loader 从未产出的键 ⇒ `KeyError`

| 项 | 实测 |
|---|---|
| 引用侧 | `checks()` L225：`cand_detail["raw_id_missing"]`、`cand_detail["raw_bad_tier"]` |
| 产出侧 | `e1_load()` L100：`return x,{"raw_rows","kept_rows","dropped_rows","tier_counts"}` —— **仅 4 键** |
| 后果 | `KeyError` ⇒ EXIT=1 ⇒ **无 checks、无 status、无终局闭环**；输出目录停在 PENDING |
| 根因（函数级 diff 证据） | `e1_load` 在 **F-2 v2.1 与 R1 之间逐字节相同**（`identical=True`）⇒ **P1-5「真实 preflight」只改了 `checks()` 一侧，忘了扩 loader 的返回字典** |
| 覆盖面 | 静态未定义名扫描：脚本内**仅此一处**契约错配（另有 `__file__` 为运行时内建，属误报） |

### 🟠 R1-N2（P1）P1-5 只落实一半：`F2V21R1.05` / `F2V21R1.06` 的 **FAIL 分支不可达**

`preflight_network` / `preflight_w01` 在 L266 求值，而 `network_load` / `w01_load` 在 L267 —— **同名条件的 loader 一律先 `raise`**：

| loader 内 raise | 位置 |
|---|---|
| `重复 node_id` | L120 |
| `重复 matsim_link_id` | L121 |
| `W01 缺字段` | L128 |
| `W01 LINK 重复` | L131 |
| `network nodes 无法识别 node/x/y` | L117 |

⇒ 坏输入 → 进程**崩在 L267** → 连 `f2v21r1_checks.csv` 都不存在 ⇒ **这两条门禁只能是 PASS，或根本不存在**。你要求的「让坏输入真的能够触发 FAIL」，在这一条上**未达成**。

> ✅ 但 `F2V21R1.03_E1_RAW_QUALITY` **是真的可 FAIL**（见 §5 的 N5/N6：16/17 `BLOCKED` 并持久化 BLOCKED 节点）——该条已落实。**P1-5 属于「部分落实」而非「未落实」。**

### 🟠 R1-N3（P2）P1-6 只落实一半：`F2V21R1.17` 是**构造性恒真**，真正的终局闭环没进产物

- `f2v21r1_summary.json` 与报告在 **L274 无条件写出**，`checks()` 在 **L275 求值** ⇒ `.is_file()` 恒为 True。实测：N8 中 15 号门已 FAIL，17 号门**仍为 True**。
- 真正的终局一致性是 **L280–284 的裸 `assert`**（`checks` 无 FAIL / summary status 一致 / 报告 status 一致 / prereg hash 未变）——**全部没有落盘为任何产物**，且脚本内**不存在** `assert_closure` 式函数（AST 扫描：`无`）。
- **manifest 写后未回读**：L278 的 `generated_artifacts` 用 `is_file()` 过滤 ⇒ **缺件会被静默略过**，且 `set(generated_artifacts) == set(names) - {manifest}` 未被断言（正常路径靠 15 号门兜住，故本次未暴露）。
- 结论：**闭环逻辑存在，但不可审计**（无产物、无双向回查）。

### 🟡 R1-N4（P2，操作约束）R1 **没有 `AUX_ALLOW` 白名单**

实测 N8：输出目录放入 `_run_note.txt` ⇒ `F2V21R1.15 = False, unknown=['_run_note.txt']` ⇒ 16/17 BLOCKED。
⇒ **判别力是真的**（好），但代价是：**运行日志绝不能放在输出目录**；`transient()` 只认 `.uploading.cfg` / `.tmp` / `~$` / `.~lock.`，而外部同步客户端会不断产生别名的瞬时文件。
（对比 F-2 v2 做法：显式 `AUX_ALLOW = {"_run_v2.log", "_f2v2_obs_crosswalk.csv", "PREREG_7_9F2_v2.md"}`。）
**建议**：把 `_run_*.log` 显式列入白名单。

### 🟢 R1-N5（P3，卫生，无功能影响）

| 项 | 实测 |
|---|---|
| `nid` 局部遮蔽 | `q4()` 内 `nid=nr.matsim_link_id` 遮蔽模块级 `nid()`；AST 确认 `q4` 内**未调用** `nid` ⇒ 无功能影响 |
| 重复读取 | nodes 读两遍（`preflight_network` + `network_load`）、W01 读两遍（`preflight_w01` + `w01_load`） |
| 重复写出 | `report()` 调 2 次（L274 PENDING / L277 终局）——为满足 15/17 号门的存在性判据，属**有意**但可更清晰 |
| 未使用字段 | `traffic_obs` 的 `req` 含 `RoadName` / `RoadCat`，全文未使用 |
| 崩溃留痕 | as-provided 崩溃后输出目录留下 14 个 PENDING 产物，无崩前清理 |

---

## 4. 8 项授权修补逐条验收

| 编号 | 修补内容 | 判定 | 第一手证据 |
|---|---|---|---|
| **P0-1** | W01 目录 → 唯一 frozen linkstats 解析 | ✅ **有效** | 运行输出 `W01=...\W01_rc_min.19.linkstats.txt.gz`；`locate_w01` 对目录 `glob("*.linkstats.txt.gz")` 且要求命中恰好 1 个 |
| **P0-2** | `g.name_norm=...` → `g["name_norm"]=...` | ✅ **有效** | 已越 `q4()`（L271）；`network_load` L120 全部改用显式列赋值（`name_norm / matsim_link_id / mid_x / mid_y / heading_deg`） |
| **P1-3** | prereg 与 output 分离 | ✅ **有效** | `PREREG_REL` 在 `..._R1_PREREG/`、`OUT_REL` 在 `..._R1/`；probe A 15 号门 `declared=14; all_exist=True; unknown=[]` |
| **P1-4** | isolation 检查真实旧目录 | ✅ **有效且真实** | N7 在旧目录植入 `LEAK_R1_payload.csv` ⇒ `F2V21R1.16=False, ['...\\secondary_tertiary_residual_7_9f2\\LEAK_R1_payload.csv']` ⇒ **BLOCKED** |
| **P1-5** | 后验恒真门 → 真实 preflight | ⚠️ **部分** | 03 号门**真可 FAIL**（N5 `raw_bad_tier=1`、N6 `raw_id_missing=1` → 16/17 BLOCKED）；**05/06 号门 FAIL 不可达**（见 R1-N2） |
| **P1-6** | 终局闭环 / 最终 assertion | ⚠️ **部分** | `checks()` **单次求值**（调用点仅 L275，v2.1 为 2 次）✅；但 17 号门恒真、闭环为裸 assert 未物化、manifest 未回读（见 R1-N3） |
| **P2-7** | NEUTRAL 与 UNKNOWN 正确区分 | ✅ **有效** | `direction_class` = `{NEUTRAL: 3816, FORWARD: 1780, REVERSE: 1681}`，`UNKNOWN` **不出现**，且与 `30<d<150` 的 **3816 精确吻合**（v2.1 把这 3816 行错标为 UNKNOWN） |
| **P2-9** | NaN 保持缺失 + 正确分母 | ✅ **有效** | `capture_improved` 取值 `{False: 630, True: 516, NaN: 162}`（pd.NA 未被强转）；`q4_summary` 新增 `n_valid_single_link_ratio / n_valid_capture_change / positive_flow_prevalence_valid_ratio / capture_improved_share_valid / capture_missing_share`；**24 个 strata 独立复算全部一致** |

### 4.1 P2-9 的量化效果（消除「覆盖率稀释」）

| strata（20 m） | n_all | 旧口径（缺失→False） | 新口径（valid 分母） | missing_share | 稀释量 |
|---|---:|---:|---:|---:|---:|
| secondary / parallel | 89 | 0.1348 | **0.2308** | 0.4157 | +0.0960 |
| secondary / same_name_parallel | 89 | 0.0899 | **0.2500** | 0.6404 | +0.1601 |
| tertiary / same_name_parallel | 20 | 0.1000 | **0.3333** | 0.7000 | +0.2333 |

全 24 strata：稀释量 **max 0.2333 / 均值 0.0384 / 有 10 个 strata 不受影响**（100 m 处基本为 0，因为正流覆盖饱和）。

### 4.2 明确「没有修」的三项（**与你的裁定一致，属正确行为**）

| 项 | 实测：原样保留 |
|---|---|
| **P2-8** `reverse_any` 退化 | `reverse_any` 取值 `{True: 109}`（恒真）⇒ `q2_correlations` 该行 Spearman = **NaN**（未掩盖） |
| **P2-10** `max over N(r)` 阶统计量偏倚 | `Spearman(median_neighbor_n, capture_improved_share_valid)`：parallel = **0.9429**（**与 v2.1 逐位相同**）、twin = 0.7714、全 24 strata = 0.5910 |
| **P2-11** 未记录被选 neighbor link | `single_link_capture` 列 = `LinkID, diagnostic_highway, diagnostic_residual_8_9, obs_8_9, canonical_ratio_e2, canonical_abs_error_e2, radius_m, neighbor_type, neighbor_n, neighbor_positive_flow_n, best_single_link_flow_raw, best_single_link_ratio, best_single_link_abs_error, capture_error_change, capture_improved` ⇒ **仍无 `selected_neighbor_link_id` / 距离 / 方向** |

---

## 5. 负向测试矩阵（N1–N8，全部第一手实测）

| 编号 | 构造的坏条件 | 结果 | 说明 |
|---|---|---|---|
| **N1** | network 重复 `matsim_link_id` | `ValueError: 重复 matsim_link_id`（L121）**崩于 L267** | **无 checks 文件** ⇒ 05 号门 FAIL 不可达 |
| **N2** | nodes 重复 `node_id` | `ValueError: 重复 node_id`（L120）**崩于 L267** | **无 checks 文件** ⇒ 05 号门 FAIL 不可达 |
| **N3** | W01 重复 `LINK` | `ValueError: W01 LINK 重复`（L131）**崩于 L267** | **无 checks 文件** ⇒ 06 号门 FAIL 不可达 |
| **N5** | E1 追加 1 行非法 `tier` | **16/17 `LOCAL_CAPTURE_DIAGNOSTIC_BLOCKED`**，EXIT=1 | ✅ `F2V21R1.03=False, raw_bad_tier=1` ⇒ **真实 FAIL 路径成立** |
| **N6** | E1 追加 1 行空 `lta_linkid` | **16/17 BLOCKED**，EXIT=1 | ✅ `F2V21R1.03=False, raw_id_missing=1` ⇒ **真实 FAIL 路径成立** |
| **N7** | 旧目录植入 `LEAK_R1_payload.csv` | **16/17 BLOCKED**，EXIT=1 | ✅ `F2V21R1.16=False`（精确路径）⇒ 隔离门**真实** |
| **N8** | 输出目录放入 `_run_note.txt` | **16/17 BLOCKED**，EXIT=1 | ✅ `F2V21R1.15=False, unknown=['_run_note.txt']` ⇒ 来源门**真实**，且 **17 号门在此情形下仍为 True**（构造性恒真的直接证据） |
| **probe A** | 正常输入 | **17/17 `LOCAL_CAPTURE_DIAGNOSTIC_READY`**，EXIT=0 | 见 §6 |

---

## 6. 对照：R1 vs R0(as-provided) vs F-2 v2.1 probe A

### 6.1 规模量（三源逐项相同）

| 量 | R1 | F-2 v2 | F-2 v2.1 |
|---|---:|---:|---:|
| target valid sections | **109** | 109 | 109 |
| E1 candidate rows | **67,471** | 67,471 | 67,471 |
| selected A+B anchors | **593** | 593 | 593 |
| network links | **706,554** | 706,554 | 706,554 |
| W01 links | **693,575** | 693,575 | 693,575 |
| obs 重建 `max|Δ|` | **0.0** | 0.0 | 0.0 |

### 6.2 **R0(as-provided) 与 probe 的 10/10 分析产物逐字节相同**

```
BIT-IDENTICAL  f2v21r1_target_sections.csv
BIT-IDENTICAL  f2v21r1_selected_ab_candidates.csv
BIT-IDENTICAL  f2v21r1_all_e1_candidates.csv
BIT-IDENTICAL  f2v21r1_direction_candidate_summary.csv
BIT-IDENTICAL  f2v21r1_direction_candidate_long.csv
BIT-IDENTICAL  f2v21r1_q2_correlations.csv
BIT-IDENTICAL  f2v21r1_group_summary.csv
BIT-IDENTICAL  f2v21r1_single_link_capture.csv
BIT-IDENTICAL  f2v21r1_q4_summary.csv
BIT-IDENTICAL  f2v21r1_obs_rebuild_check.csv
==> 10/10 分析产物逐字节相同
```

⇒ probe 的「补 2 个键」改动是 **分析中性**的：它**只影响门禁能否求值**，不改变任何一个分析数字。

### 6.3 Q2 与 F-2 v2.1 **逐项 0 差异**

| metric | Spearman (R1) | Spearman (v2.1) | Δ |
|---|---:|---:|---:|
| `reverse_share` | 0.055790 | 0.055790 | **0.0** |
| `forward_share` | 0.050897 | 0.050897 | **0.0** |
| `median_direction_diff_deg` | −0.048191 | −0.048191 | **0.0** |
| `reverse_any` | NaN | NaN | — |
| `C_GEOMETRY_ONLY_reverse_share` | 0.115600 | 0.115600 | **0.0** |
| `C_GEOMETRY_ONLY_forward_share` | 0.000650 | 0.000650 | **0.0** |

`direction_candidate_summary`：**22 个数值列 × 109 个 LinkID，逐项 `max|Δ| = 0.0`**。
`group_summary`：两行（secondary / tertiary）**完全相同**。
`direction_candidate_long`：7,277 行，**唯一差异 = 3,816 行 `UNKNOWN → NEUTRAL`**，其余数值列 `max|Δ| = 0.0`。

### 6.4 Q2 主量（R1 正式值，供后续报告中引用）

| Highway | n | median forward | median reverse | median neutral | median direction |
|---|---:|---:|---:|---:|---:|
| secondary | 89 | 0.2375 | 0.2208 | **0.5500** | **89.93°** |
| tertiary | 20 | 0.2330 | 0.2404 | **0.5390** | **90.01°** |

> ⚠️ **口径澄清（建议后续统一）**：你上轮引用的「neutral 54.3%」= **109 个 section 混合的 `median(neutral_share)` = 0.5429**。另有三个不同口径：per-highway 中位 = 0.5500 / 0.5390；全 109 混合 **mean** = 0.5094；**pooled 行级占比 = 3816/7277 = 0.5244**。**正式报告里必须写明用的是哪一个**，否则会出现「同一现象四个数」。

pooled（行级）：FORWARD **0.2446** / REVERSE **0.2310** / NEUTRAL **0.5244**。
⇒ 结论方向不变：**方向差中位 ≈ 90°，forward 与 reverse 近似对称，与 frozen residual 的 |ρ| ≤ 0.116。**

### 6.5 Q4：R1 只验执行链，机制强度**不下结论**

- `median_neighbor_n`、`median_best_single_link_ratio` 与 v2.1 **逐 strata `max|Δ| = 0.0`**。
- 新增 `n_all_target / n_valid_single_link_ratio / n_valid_capture_change / positive_flow_prevalence_all / positive_flow_prevalence_valid_ratio / capture_improved_share_valid / capture_missing_share`，删除旧列 `n / positive_flow_prevalence / capture_improved_share`。
- ⛔ **阶统计量偏倚原样保留**（ρ = 0.9429，与 v2.1 相同）⇒ **跨半径/跨类型仍不可比**，不得据 R1 做机制结论。

---

## 7. `R-F2V21-R1-1` 冻结量核对（全部保持）

| 冻结量 | 实测 |
|---|---|
| target domain | **109**（secondary 89 / tertiary 20），与 F-2 v2 完全一致 |
| E1 candidate universe | **67,471** 行；tier = C 51,688 / B 9,328 / A 6,455 |
| A/B selection hierarchy | `select_ab` **函数逐字节相同**；选中 **593** = A **577** + B **16**；`matsim_link_id` **全局唯一 593**；覆盖 **109** 个 section |
| forward ≤ 30° / reverse ≥ 150° | 代码常量 `FWD=30.0` / `REV=150.0` 未变 |
| 20 / 50 / 100 m | `RADII=[20.0,50.0,100.0]` 未变 |
| parallel / twin 定义 | `hd<=FWD` / `hd>=REV`，`same_name_*` 子集定义未变 |
| SCALE | `459794.0/200000.0` = **2.29897**，且在 manifest `protocol.scale` 明确落盘 |
| E2 frozen residual | R1 target 表 vs v2.1 `max|Δ| = 0.0`；**vs E2 源文件 `max|Δ| = 0.0`** |

**函数级 diff（F-2 v2.1 → R1）**：
- **逐字节相同 18 个**：`adiff, bearing, e1_load, e2_load, group_sum, nid, nn, nt, num, q2corr, ratio, select_ab, sha256_file, spr, traffic_obs, transient, w01_load, zero_sim`
- **有改动 7 个**：`checks, main, network_load, q2, q4, q4sum, report`
- **新增 3 个**：`locate_w01, preflight_network, preflight_w01`

---

## 8. 纪律核对

| 项 | 结果 |
|---|---|
| MATSim / Java 调用 | **NO**（`F2V21R1.02` 通过；AST 无 subprocess/jpype/py4j） |
| 冻结输入是否被改 | **NO**——manifest 记录 8 个输入的 sha256 **全部复核 OK**（TrafficFlow_JSON / E1 / E2 / network / nodes / W01 / prereg / script） |
| as-provided 正本是否被改 | **NO**——下载件 == 工程正本 == `.bak_asprovided_20260926`，三者逐位一致 |
| 双向隔离 | R0(13 件, 09-23 12:26–12:27) / F-2 v2(15 件, 09-23 20:34–20:35) / v2.1(1 件, 09-24 07:50) 目录**零 `r1` 命中、零写入** |
| E2 / 7.3.6A / v1.0 回写 | **NO**；未产生 v1.1 |
| SCALE 重估 | **NO** |

**本次新增写入位置**：
```
reports/secondary_tertiary_residual_7_9f2_v2_1_R1/                    14 件  ← R1 as-provided 崩溃留痕（BLOCKED，非正式节点）
reports/secondary_tertiary_residual_7_9f2_v2_1_R1_PREREG/              1 件  ← prereg
reports/secondary_tertiary_residual_7_9f2_v2_1_R1_asprovided_diag/     9 件  ← 日志 + 本报告
reports/_f2v21r1_probe_run/…_R1/                                      14 件  ← probe A（17/17，非正式）
reports/_f2v21r1_negative_probe/                                       5 件  ← 反例输入
reports/_f2v21r1_neg_iso/                                             15 件  ← N7
reports/_f2v21r1_neg_out_N5|N6|N8/…                                   各 14 件 ← 负向测试输出
scripts/od/_probe_v21r1_run.py                                              ← 单处补齐副本
```

---

## 9. Q2 当前的身份：**probe / exploratory evidence**（不得提升）

按你上轮设定的提升规则 ——「R1 正式重跑后，如果 **17/17 PASS** 且 Q2 数值逐项复现，才提升为 **F-2 v2.1 正式 Q2 negative diagnostic**」：

- **条件 1（正式跑通过）**：❌ **不满足** —— R1 **as-provided 崩溃**（R1-N1），未产生任何 READY 节点。
- **条件 2（数值逐项复现）**：✅ **满足** —— probe 与 v2.1/R0 逐项 0 差异。

⇒ **两者未同时满足，故 Q2 只能记为 probe / exploratory evidence**。它现在比上轮更硬（标签错误已修、缺失值语义已修、分析产物可证中性），但**身份仍是执行副本**。

---

## 10. 处置方案（请裁定）

| 方案 | 内容 | 代价 | 我的建议 |
|---|---|---|---|
| **A（推荐）** | 开 **`F-2 v2.1-R2`**，仅补 3 项**执行层**修复：① `e1_load` 补 `raw_id_missing` / `raw_bad_tier`，并加一条「loader 返回键集合 ⊇ `checks()` 引用键集合」的自检；② 把 preflight 立为**唯一权威**（loader 不再对已被门禁覆盖的条件硬 raise，或捕获后仍走 `checks()`），使 05/06 号门**真的能 FAIL**；③ 终局闭环**物化**为产物（`closure` 表）+ manifest **写后双向回查**，并把 17 号门改为「manifest ↔ 磁盘数量与哈希对账」。**不动** Q2/Q4 定义、阈值、样本域、SCALE、E2 residual；**不动** P2-8/10/11。 | 小：3 处定点修补 + 1 次重跑 | ✅ 与你「执行修复 vs 指标重定义必须分离」的裁定精神完全一致 |
| **B** | 不开 R2，把 `_probe_v21r1_run.py`（单行补齐）当作 R1 的**执行副本**，把 17/17 与 Q2 记为 probe，R1 记 `BLOCKED` 封存。 | 无额外工作，但**正式性不足**：probe 未经预注册，不能作为节点身份 | ⚠️ 仅在你不想再走一轮时采用 |
| **C** | 接受「崩在门禁之前 = BLOCKED」为 R1 终态，不再修。 | R1 永远产不出正式节点；Q2 永远停在 exploratory | ❌ 浪费已到手的 Q2 负结果 |

无论选哪个：**R1 as-provided 只能记为 `BLOCKED`**，且 `reports/secondary_tertiary_residual_7_9f2_v2_1_R1/` 当前存放的是**崩溃留痕**，不是正式节点产物集；若开 R2，**必须改用新的输出目录名**。

---

## 附录 A：probe A 的 17 条门禁原始输出

```
F2V21R1.01_PREREG_HASH                  True  13401c3f7c9542c8f5a4d28197c5ade7e56294286f620a160a73d5de517fcadf
F2V21R1.02_ZERO_SIMULATION              True  AST no subprocess/Java
F2V21R1.03_E1_RAW_QUALITY               True  {'raw_rows': 67471, 'kept_rows': 67471, 'dropped_rows': 0, 'raw_id_missing': 0, 'raw_bad_tier': 0, 'tier_counts': {...}}
F2V21R1.04_E2_TARGET_UNIQUE             True  target_n=109
F2V21R1.05_NETWORK_PREFLIGHT            True  {"network_duplicate_link_id": 0, "node_duplicate_id": 0, "node_required_missing": []}
F2V21R1.06_W01_PREFLIGHT                True  {"missing": [], "duplicate_link": 0}
F2V21R1.07_TARGET_TOTAL_GE100           True  target_n=109
F2V21R1.08_SECONDARY_GE80               True  secondary=89
F2V21R1.09_TERTIARY_GE15                True  tertiary=20
F2V21R1.10_E1_COVERAGE_GE95             True  coverage=1.000000
F2V21R1.11_DIRECTION_COVERAGE_GE95      True  coverage=1.000000
F2V21R1.12_AB_ANCHOR_COVERAGE_GE95      True  coverage=1.000000
F2V21R1.13_ANCHOR_COORD_GE99            True  coverage=1.000000
F2V21R1.14_NEIGHBOR_GE95_EACH_RADIUS    True  {"20.0": 1.0, "50.0": 1.0, "100.0": 1.0}
F2V21R1.15_OUTPUT_PROVENANCE            True  declared=14; all_exist=True; unknown=[]
F2V21R1.16_ISOLATION                    True  []
F2V21R1.17_FINAL_CLOSURE_FILES          True  summary/report present
```

manifest 一致性：`generated_artifacts` **13 条**（= 14 声明 − manifest 自身）、**0 陈旧**、磁盘 14 件、无未入账、无账面缺件；`protocol` = `{scale: 2.29897, radii_m: [20,50,100], forward_max_deg: 30, reverse_min_deg: 150, q2_domain: "all E1 stored A/B/C candidates", q4_anchor_domain: "F-1/E2 A+B selected", revision: "F-2 v2.1-R1"}`。

## 附录 B：本次未做（边界声明）

⛔ 未改 Q2/Q4 的提问方式、阈值、样本域、核心公式；⛔ 未修 P2-8 / P2-10 / P2-11；⛔ 未回写 E1/E2/F-1/F-2 v2/v2.1/7.3.6A/v1.0；⛔ 未产生 v1.1；⛔ 未运行 MATSim；⛔ 未修改 as-provided 脚本一字。
