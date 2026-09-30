# Step 7.9F-2 v2.1-R2 — Execution / Contract Closure Repair — FINDINGS

**STATUS: `LOCAL_CAPTURE_DIAGNOSTIC_READY` · 18/18 · EXIT=0 · CLOSURE=OK**

ZERO SIMULATION / READ-ONLY / DIAGNOSTIC ONLY. No MATSim / Java invoked. No frozen input touched.

---

## 1. 身份核验

| 交付件 | SHA256 | 大小 | 结论 |
|---|---|---|---|
| `PREREG_7_9F2_v2_1_R2.md` | `0a0c61336056a66d5ea1506215b1680d3920aef2cb804a221571812e9de18a19` | 4,617 B | 与脚本内 `EXPECTED_PREREG_SHA256` 一致 |
| `audit_secondary_tertiary_residual_7_9f2_v2_1_R2.py` | `1d12aa799dc4e707ed6531621e61c4da00130d4c9d7058645f8ff1bd83fd35fb` | 43,759 B | 正本 == `.bak_asprovided`（逐位一致） |

- `AST_PARSE_PASS=True` / `COMPILE_PASS=True` / `ZERO_SIM_IMPORT=True`
  （imports：`__future__, argparse, ast, gzip, hashlib, json, math, numpy, pandas, pathlib, re, scipy`）
- ⚠️ **哈希披露**：脚本在首次实跑后因两处修正（占位符覆盖、升级态状态串）哈希变更，**最终值如上**；
  中间态哈希为 `7daad555…`（40,969 B）与 `05952366…`（43,248 B），两者均**未作为交付件保留**。
  `.bak_asprovided` 保存的是**最终版**。

### 函数级 diff（R1 → R2）

| 类别 | 数量 | 成员 |
|---|---|---|
| **逐字节相同** | **24** | `sha256_file, nid, nt, nn, num, ratio, spr, adiff, bearing, zero_sim, transient, locate_w01, traffic_obs, select_ab, e2_load, network_load, w01_load, q2, q2corr, q4, q4sum, group_sum, preflight_network, preflight_w01` |
| 改动 | 4 | `checks`、`e1_load`、`main`、`report` |
| 新增 | 9 | `pf_guard, pf_network_ok, pf_w01_ok, contract_check, dump_csv, writeback_rows, pass_col, closure_reconcile, final_assertions` |
| 删除 | 0 | — |

⇒ **全部分析函数（`q2 / q2corr / q4 / q4sum / group_sum / select_ab`）逐字节未变**，分析口径在源码层面可证未动。

---

## 2. 三项修复逐条验收

### R2-1 — `e1_load ↔ checks()` 契约修复 ✅

`e1_load` 返回键由 4 个扩到 6 个：`{raw_rows, kept_rows, dropped_rows, raw_id_missing, raw_bad_tier, tier_counts}`。
`diff` 证据显示改动**仅为**：docstring + 1 行计算（`_raw_id_missing` / `_raw_bad_tier`，在**过滤前**的原始行上计算）+ 返回字典加 2 键。**无其他改动。**

新增**静态契约自检** `contract_check()`（门禁 18），双向验证：

```
declared_keys      = ['raw_rows','kept_rows','dropped_rows','raw_id_missing','raw_bad_tier','tier_counts']
loader_return_keys = ['raw_rows','kept_rows','dropped_rows','raw_id_missing','raw_bad_tier','tier_counts']   ✅ 相等
checks_ref_keys    = ['raw_bad_tier','raw_id_missing','raw_rows']                                           ✅ ⊆
missing_from_loader = []        referenced_not_declared = []
CONTRACT_PASS = True
```

关键：**门禁 18 在任何 loader 运行之前求值**。契约被破坏时不再产生 `KeyError`，而是受控收口（见 N9）。
实跑前即在 AST 层抓住，而不是等到第 200 多行。

### R2-2 — preflight 成为 05/06 唯一权威 ✅

```
locate_w01 → contract_check + preflight_network + preflight_w01 + prereg + zero_sim
           → all PASS ? 严格 loader → 分析链
                        : 受控收口（BLOCKED 节点 + 5 件产物落盘 + EXIT=1）
```

- `pf_guard()` 包装使 preflight **永不抛异常**，只报告（`error` 字段进入门禁 detail）。
- loader **完全未做宽松化**，逐字节保留；只有在 preflight PASS 之后才会被执行。
- N1/N2/N3 实测：**不再是「崩在门禁之前」**（R1 时输出目录 **0 件**），现在是
  `05`（或 `06`）= FAIL、status `BLOCKED`、`checks.csv` + `summary.json` + `report.md` + `manifest` + `closure` 全部存在、`EXIT=1`。

### R2-3 — 终局闭环真正物化 ✅

四段式，全部**落盘可审计**，无裸 `assert`：

1. **写后回查（门禁 17）**：10 个分析产物逐项校验「存在 / 非空 / size == 写入时 / sha256 == 写入时 / 重读行数 == 内存行数」。
2. **manifest 最后生成**：`generated_artifacts` 13 条；manifest **不自哈希**；终局闭环产物显式声明 `terminal_closure_artifact = {hashed: false}`（写在 manifest 之后，故不入自哈希）。
3. **`f2v21r2_closure_check.csv`（终局闭环产物）**：逐产物 `exists / size / size_expected / size_match / nonempty / sha256_disk / sha256_expected / sha_match`；
   重读 `checks.csv` / `summary.json` / `report.md` 并断言**三处状态一致**；含 `declared_set_vs_disk` 数量对账行。
4. **final assertions 物化**：manifest ↔ 磁盘逐项 size/sha 对账（13 条）+ `status_three_way`。

> **★ 门禁 17 第一次实跑就抓到一个真实缺陷 —— 而且是 R2 自身的。**
> 我最初把占位符循环写成对**全部 15 个声明产物**写 `PENDING`，把刚写好的 10 个分析 CSV 覆盖成 9 字节。
> 实测输出：`f2v21r2_target_sections.csv:SIZE_MISMATCH; …(共 10 个)` ⇒ `17=False` ⇒ `BLOCKED`。
> 该缺陷已修复（占位符循环跳过已写入的分析产物），并**固化为可复现反例 N10**（见 §4），
> 不是口头描述。这直接证明新门禁不是装饰。

---

## 3. 门禁 18/18

| # | Check | Result |
|---|---|---|
| 01 | `PREREG_HASH` | PASS |
| 02 | `ZERO_SIMULATION` | PASS |
| 03 | `E1_RAW_QUALITY` | PASS（`raw_id_missing=0, raw_bad_tier=0, tier_counts C 51688 / B 9328 / A 6455`） |
| 04 | `E2_TARGET_UNIQUE` | PASS（target_n=109） |
| 05 | `NETWORK_PREFLIGHT` | PASS（dup_link=0, dup_node=0） |
| 06 | `W01_PREFLIGHT` | PASS（missing=[], dup_link=0） |
| 07 | `TARGET_TOTAL_GE100` | PASS（109） |
| 08 | `SECONDARY_GE80` | PASS（89） |
| 09 | `TERTIARY_GE15` | PASS（20） |
| 10 | `E1_COVERAGE_GE95` | PASS（1.000000） |
| 11 | `DIRECTION_COVERAGE_GE95` | PASS（1.000000） |
| 12 | `AB_ANCHOR_COVERAGE_GE95` | PASS（1.000000） |
| 13 | `ANCHOR_COORD_GE99` | PASS（1.000000） |
| 14 | `NEIGHBOR_GE95_EACH_RADIUS` | PASS（20/50/100 m 全 1.0） |
| 15 | `OUTPUT_PROVENANCE` | PASS（declared=15, all_exist=True, nonempty=True, unknown=[]） |
| 16 | `ISOLATION` | PASS（5 个早期节点内 `*R2*` 命中 = []） |
| 17 | `WRITEBACK_VERIFICATION` | PASS（10/10 OK） |
| 18 | `LOADER_CHECKS_CONTRACT` | PASS |

主量：`target=109；E1=67,471；anchors=593；network=706,554；W01=693,575；obs_rebuild_max_abs_delta=0.0`

---

## 4. 负向测试矩阵（全部第一手实测）

| 例 | 注入 | R1 旧行为 | **R2 新行为** |
|---|---|---|---|
| **N1** | network 重复 `link_id` | 💥 崩于 loader，**0 产物** | `05=False`（`duplicate_link_id:1`）→ BLOCKED，**5 件产物齐**，EXIT=1 |
| **N2** | nodes 重复 `node_id` | 💥 崩于 loader，**0 产物** | `05=False`（`node_duplicate_id:1`）→ BLOCKED，5 件齐，EXIT=1 |
| **N3** | W01 重复 `LINK` | 💥 崩于 loader，**0 产物** | `06=False`（`duplicate_link:1`）→ BLOCKED，5 件齐，EXIT=1 |
| **N9** | **契约破坏**：从 `e1_load` 返回字典删掉 `raw_id_missing` | 该类错误曾致 R1 `KeyError` 全链崩 | **`18=False`（`missing_from_loader=['raw_id_missing']`）→ BLOCKED，5 件齐，EXIT=1** |
| **N10** | **写后回查可证伪性**：占位符循环不跳过分析产物 | —（R1 无此门禁） | `17=False`（10×`SIZE_MISMATCH`）+ 闭环 `NOT_OK` ⇒ `BLOCKED_CLOSURE_FAILED`，EXIT=2 |

四例 BLOCKED 节点均满足你的验收式：
```
坏输入 → 05/06/18 = FAIL → status = BLOCKED → checks.csv 存在 → summary.json 存在
       → report 存在 → EXIT = 1
```
N10 额外满足：`17 = FAIL` + closure `CLOSURE_OK=False` + 三处状态一致（`…_CLOSURE_FAILED`）+ EXIT=2。

---

## 5. 四源对照

### 5.1 R2 ↔ R1（probe / as-provided）——**逐位相同**

```
R2 vs R1 probe       : 10/10 analytical artifacts bytewise identical
R2 vs R1 as-provided : 10/10 analytical artifacts bytewise identical
```
十个分析产物（`target_sections / all_e1_candidates / selected_ab_candidates / direction_candidate_summary /
direction_candidate_long / q2_correlations / group_summary / single_link_capture / q4_summary / obs_rebuild_check`）
SHA256 **完全相同**。

⇒ **R2 的执行层修复对分析结果零影响**，这是「R2 只是执行修复」的最强证据，也是
`R-F2V21-R1-1`（R1 与 R0 对照应逐项一致）在 R2 上的延续。

### 5.2 R2 ↔ F-2 v2.1 / F-2 v2

- 上一轮已证：R1 ≡ v2.1（Q2/Q4 逐项 0 差异；`direction_candidate_summary` 22 数值列 × 109 LinkID `max|Δ|=0`）。
- 本轮证：R2 ≡ R1（逐位）。⇒ **R2 ≡ v2.1 传递成立**。
- ⚠️ **R2 与 F-2 v2 不做数值比对**：v2 **不是**同一套 schema —— v2 的 `group_summary` 字段为
  `mean_frozen_residual / median_frozen_residual / median_matched_sum_ratio / median_direction_deg / median_direction_good_share …`，
  那是 v2.1 明确**重定义 Q2/Q4 之前**的对象。强行比对会得出伪结论。可比的只有冻结量与重叠字段：
  `positive_parallel_100m_share` 0.966292 / 0.950000、`positive_twin_100m_share` 0.977528 / 1.000000、
  `median_direction_good_share` 1.0 / 1.0 —— **R2 与 v2 在这三项上一致**。

### 5.3 冻结量（0 change）

```
SCALE = 2.29897   target = 109 (sec 89 / ter 20)   E1 = 67,471 (C 51,688 / B 9,328 / A 6,455)
anchors = 593 (A 577 + B 16)   network = 706,554   W01 = 693,575   RADII = 20/50/100 m   FWD ≤30°  REV ≥150°
```
manifest 声明的 **8 个冻结输入**（traffic_json / e1 / e2 / network / nodes / w01 / prereg / script）
逐一与磁盘重算 SHA256 对账：**`FROZEN_INPUTS_UNCHANGED = True`**。

### 5.4 污染检查（0）

| 节点 | files | mtime | `*R2*` 命中 |
|---|---|---|---|
| `secondary_tertiary_residual_7_9f2` (R0) | 13 | 09-23 12:26–12:27 | **[]** |
| `…_v2` | 15 | 09-23 20:34–20:35 | **[]** |
| `…_v2_1` | 1 | 09-24 07:50 | **[]** |
| `…_v2_1_R1` | 14 | 09-26 20:52 | **[]** |
| `…_v2_1_R1_PREREG` | 1 | 09-26 20:49 | **[]** |

MATSim / Java：**NO**（`02_ZERO_SIMULATION=True`，`matsim_rerun=false`）。

---

## 6. R2 节点产物（`reports/secondary_tertiary_residual_7_9f2_v2_1_R2/`，15 件）

```
   929,020  f2v21r2_all_e1_candidates.csv
     2,220  f2v21r2_checks.csv
     6,292  f2v21r2_closure_check.csv          ← 终局闭环（manifest 显式声明不自哈希）
   933,721  f2v21r2_direction_candidate_long.csv
    21,550  f2v21r2_direction_candidate_summary.csv
       424  f2v21r2_group_summary.csv
     4,732  f2v21r2_input_manifest.json         ← generated_artifacts 13 条
     2,659  f2v21r2_obs_rebuild_check.csv
       303  f2v21r2_q2_correlations.csv
     3,243  f2v21r2_q4_summary.csv
    86,519  f2v21r2_selected_ab_candidates.csv
   209,367  f2v21r2_single_link_capture.csv
       568  f2v21r2_summary.json
    18,767  f2v21r2_target_sections.csv
     5,397  STEP7_9F2_v2_1_R2_REPORT.md
```

---

## 7. 明确未做（写在 version boundary 内）

- **P2-8**（`reverse_any` 退化常量 ⇒ Spearman 未定义）：**未修**。`q2_correlations.csv` 中
  `reverse_any` 的 `spearman_with_frozen_residual` 仍为**空值（NaN 保留）**，`group_summary` 中
  `reverse_any_prevalence = 1.0`（109/109）。正确处理是保留 NaN 并标 `DEGENERATE_CONSTANT`，
  属 **Q2 reporting refinement**，不混入执行修补。
- **P2-10 / P2-11**（`max over N(r)` 阶统计量偏倚；无 `selected_neighbor_link_id` 可追溯锚点）：
  **未动**。`ρ(N, improved)=0.9429` 原样保留。
- **未改**：Q2/Q4 的定义、30°/150° 阈值、20/50/100 m、A+B 选择、SCALE、E2 frozen residual、target/E1/anchors/network/W01。
- **未做**：回写 E2、修改 R0/v2/v2.1/R1 目录、产生 v1.1。

---

## 8. 收口判定

### Q2 提升条件达成情况

| 条件 | 状态 |
|---|---|
| ① 正式节点 18/18 PASS | ✅（R2 `LOCAL_CAPTURE_DIAGNOSTIC_READY`，EXIT=0） |
| ② Q2 数值与 R1 probe 逐项复现 | ✅（10/10 分析产物**逐位相同**，强于「数值逐项」） |

⇒ **两项同时满足**，因此建议将

> **「方向候选结构基本不能解释 secondary/tertiary 系统性低估」**

提升为 **F-2 v2.1 正式 Q2 negative diagnostic**。

Q2 主量（R2 正式，与 R1 probe 逐位一致）：

| 组 | n | median reverse | median forward | median direction | reverse_any prevalence |
|---|---:|---:|---:|---:|---:|
| secondary | 89 | 0.220779 | 0.237500 | 89.932874° | 1.0 |
| tertiary | 20 | 0.240372 | 0.233036 | 90.014366° | 1.0 |

`|Spearman| ≤ 0.1156`（最高 `C_GEOMETRY_ONLY_reverse_share`）。
⚠️ 并报纪律：`neutral` 口径有四版（混合 median **0.5429** / per-hw median 0.5500、0.5390 / 混合 mean 0.5094 / pooled 行级 0.5244），**报哪个都要标口径**。

### Q4

R2 **仅验证执行链闭合**（`17` 号门 + 闭环 OK），**不解释 mechanism strength**。
阶统计量偏倚与可追溯锚点留待 `F-2 Q4-R1` 独立 prereg。

### 建议版本树（据此更新）

```
F-2 v2
   ↓
F-2 v2.1-R0   BLOCKED
   ↓
F-2 v2.1-R1   BLOCKED + probe READY (非正式)
   ↓
F-2 v2.1-R2   LOCAL_CAPTURE_DIAGNOSTIC_READY  ← 正式节点，本次
   ↓
F-2 Q4-R1     （另立 prereg：single-link capture / traceability 重设计）
```

---

## 附录 A — 复现命令

```bash
# baseline（正式节点）
python scripts/od/audit_secondary_tertiary_residual_7_9f2_v2_1_R2.py
# → 18/18 READY, EXIT=0, CLOSURE=OK

# N1 network / N2 nodes / N3 W01 受控收口
python scripts/od/audit_secondary_tertiary_residual_7_9f2_v2_1_R2.py --network <dup_link.csv>  --out-dir <dir>/secondary_tertiary_residual_7_9f2_v2_1_R2
python scripts/od/audit_secondary_tertiary_residual_7_9f2_v2_1_R2.py --nodes   <dup_id.csv>    --out-dir <dir>/secondary_tertiary_residual_7_9f2_v2_1_R2
python scripts/od/audit_secondary_tertiary_residual_7_9f2_v2_1_R2.py --w01-linkstats <dup.gz>  --out-dir <dir>/secondary_tertiary_residual_7_9f2_v2_1_R2
# → 各 EXIT=1, gate 05/06 FAIL, 5 件产物齐

# N9 契约破坏反例
python scripts/od/_probe_v21r2_contractbreak.py   --out-dir <dir>/secondary_tertiary_residual_7_9f2_v2_1_R2   # → gate 18 FAIL, EXIT=1
# N10 写后回查可证伪性反例
python scripts/od/_probe_v21r2_placeholderbug.py  --out-dir <dir>/secondary_tertiary_residual_7_9f2_v2_1_R2   # → gate 17 FAIL, EXIT=2
```

## 附录 B — 边界声明

R2 只做执行层 / 契约层 / 闭环物化修复。`LOCAL_CAPTURE_DIAGNOSTIC_READY` **只表示修复后的执行与契约链
闭合通过，不证明任何机制，也不授权修改模型**。Q2/Q4 的科学问题、阈值、样本域、核心计算定义在本版本中**未变**。
