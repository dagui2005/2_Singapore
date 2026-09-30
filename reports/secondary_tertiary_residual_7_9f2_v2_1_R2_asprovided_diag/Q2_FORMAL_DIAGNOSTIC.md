# Q2 正式诊断记录（negative diagnostic）

**节点**：`F-2 v2.1-R2` — `LOCAL_CAPTURE_DIAGNOSTIC_READY`
**状态**：R2 已正式收口（18/18 PASS / EXIT=0 / CLOSURE=OK），Q2 因此**由 `probe / exploratory evidence` 提升为正式 diagnostic**。
**生效日**：2026-09-27
**本记录所在目录**：`reports/secondary_tertiary_residual_7_9f2_v2_1_R2_asprovided_diag/`（**节点目录之外的伴随记录**，见 §7 说明）

---

## 1. 正式表述（已获裁定确认，逐字采用）

> 在冻结的 E2 secondary/tertiary residual target 上，基于 E1 保存的完整 A/B/C candidate evidence，候选方向结构中的 forward/reverse share、方向差中位数及其相关性均未显示出能够解释 secondary/tertiary 系统性低估的明显统计关联。

### 1.1 边界（必须与上一句同时出现）

> 这是 **negative diagnostic**，**不是「方向机制不存在」的物理证明**。

具体地：
- 它排除的是「**以 E1 已存证的候选方向结构（forward/reverse share、方向差中位数、及其与 frozen residual 的秩相关）作为解释变量**」这一条路径；
- 它**不**排除：方向机制在别的观测口径下存在、几何方向定义并非真实行驶方向、E1 candidate universe 本身对 sec/ter 存在系统性覆盖偏差、或残差由 E2 之外的机制（如延误/车型/出发时刻）主导。
- 未做的三件事（P2-8 / P2-10 / P2-11）意味着：**本诊断的解释力上限受这三处未修缺陷约束**，见 §6。

---

## 2. 提升条件达成证据

| 条件 | 要求 | 实测 | 结论 |
|---|---|---|---|
| ① 正式节点自身可重复 | 18/18 PASS | `hard_pass_count=18 / hard_total=18`，`status=LOCAL_CAPTURE_DIAGNOSTIC_READY`，`EXIT=0`，`CLOSURE_OK=True` | ✅ |
| ② Q2 数值与先前 probe 逐项复现 | 逐项一致 | **更强**：`R2 ↔ R1 probe` 10/10 分析产物 **SHA256 逐位相同** | ✅ |

> 条件 ① 是 R2 存在的全部意义：R1 的 as-provided 因 `checks()` 引用 `e1_load` 未返回的键而 `KeyError`、产物全 `PENDING`，**节点自身不可重复**，故那时 Q2 只能记 `probe`。
> 条件 ② 说明 R2 的三处执行层修复（R2-1 契约、R2-2 preflight 权威化、R2-3 闭环物化）**确实分析中性**。

---

## 3. 支撑数值（第一手，取自 R2 节点产物）

### 3.1 组级主量 — 源：`f2v21r2_group_summary.csv`

| diagnostic_highway | n | median_reverse_share | median_forward_share | median_direction_diff_deg | reverse_any_prevalence |
|---|---|---|---|---|---|
| secondary | 89 | 0.220779 | 0.237500 | 89.932874 | 1.0 |
| tertiary | 20 | 0.240372 | 0.233036 | 90.014366 | 1.0 |

> `median_direction_diff_deg` 由 `direction_candidate_summary.csv` 的 per-断面 `median_direction_diff_deg` 再取组内中位数得到，与上表逐位一致（89.932874 / 90.014366）。

**读数**：两组的方向差中位数都落在 **≈90°**（正交），forward 与 reverse share 几乎对称（0.233–0.240），亦即候选方向**没有可支配的净方向偏好**。

### 3.2 与 frozen residual 的秩相关 — 源：`f2v21r2_q2_correlations.csv`

| metric | n | Spearman with frozen residual |
|---|---|---|
| `reverse_share` | 109 | 0.055790 |
| `forward_share` | 109 | 0.050897 |
| `median_direction_diff_deg` | 109 | −0.048191 |
| `reverse_any` | 109 | **（NaN，见 §4.2）** |
| `C_GEOMETRY_ONLY_reverse_share` | 109 | **0.115600** ← max\|ρ\| |
| `C_GEOMETRY_ONLY_forward_share` | 109 | 0.000650 |

**读数**：**max\|ρ\| = 0.1156**（`n=109`）。即便取全部 6 个 metric 的最大值，也远低于任何可用于解释 sec/ter 系统性低估的强度。

### 3.3 样本与冻结量（`f2v21r2_summary.json`）

```
target_n = 109 (secondary 89 / tertiary 20)
e1_candidate_rows = 67,471
selected_anchor_rows = 593
network_links = 706,554
w01_links = 693,575
obs_rebuild_max_abs_delta = 0.0
protocol.scale = 2.29897
```

---

## 4. 口径声明（**报数必须带口径**）

### 4.1 `neutral` 有四版口径 —— 数值不同，选哪个都必须明示

| 口径 | 定义 | secondary | tertiary | 全 109 |
|---|---|---|---|---|
| **(A) 混合 median** | 109 个断面 `neutral_share` 直接取中位数 | — | — | **0.542857** |
| **(B) per-hw median** | 组内取中位数 | **0.550000** | **0.539020** | — |
| **(C) 混合 mean** | 109 个断面 `neutral_share` 取均值 | — | — | 0.509430 |
| **(D) per-hw mean** | 组内取均值 | 0.509746 | 0.508022 | — |
| **(E) pooled 行级** | 7,277 条候选行按 `direction_class` 汇总 | **0.527568** | **0.509924** | — |

> ⚠️ 此前口头引用的「**54.3%**」= 口径 **(A)**；组级表里若写 `neutral` 中位数，用的是 **(B)**（0.5500 / 0.5390）。
> **本记录的正式主量采用 (B) + (E) 并报**：(B) 是「典型断面的中性占比」，(E) 是「候选行总体的中性占比」。
> 行级计数：secondary `FORWARD 1456 / NEUTRAL 3148 / REVERSE 1363`；tertiary `324 / 668 / 318`。

### 4.2 `reverse_any` 是常量，Spearman 恒为 NaN

```
direction_candidate_summary.reverse_any 唯一值 = [True]，109/109
group_summary.reverse_any_prevalence = [1.0, 1.0]
```

⇒ 方差为 0 ⇒ **秩相关未定义**，落盘保持空白（**不是 0**）。
**正确处理 = 保留 NaN + 标记 `DEGENERATE_CONSTANT`**，不得强行制造相关系数。
此项**不在 R2 修复范围**，属后续 **Q2 reporting refinement**（见 §6 P2-8）。

### 4.3 方向分类标签

`direction_candidate_long.csv`：`{NEUTRAL: 3816, FORWARD: 1780, REVERSE: 1681}`，`UNKNOWN` **不出现**；3,816 与 `30° < d < 150°` 精确吻合。此项在 R1 已修（P2-7），R2 继承不变。

---

## 5. 不变量（本记录生效期间不得更改）

```
Q2 domain          = all E1 stored A/B/C candidates
FORWARD            <= 30°
REVERSE            >= 150°
NEUTRAL            30° ~ 150°
UNKNOWN            = missing
SCALE              = 2.29897
E2 frozen residual = 原样（未回写）
target = 109 / E1 = 67,471 / anchors = 593 / network = 706,554 / W01 = 693,575
```

冻结输入对账：**`FROZEN_INPUTS_UNCHANGED = True`**（manifest 声明的 8 个输入逐一与磁盘重算一致）。

---

## 6. 本诊断的**非目标**与已知解释力上限

| 编号 | 内容 | 归属 | 对本诊断的影响 |
|---|---|---|---|
| **P2-8** | `reverse_any` 109/109 退化 ⇒ 相关系数 NaN | **Q2 reporting refinement**（不属 R2） | 6 个 metric 里 1 个不可估；其余 5 个 \|ρ\| ≤ 0.1156 |
| **P2-10** | `best_single_link = max over N(r)` 是**阶统计量** ⇒ 跨半径/跨类型不可比 | **另立 `F-2 Q4-R1`** | 约束 **Q4**，不影响 Q2 |
| **P2-11** | 未记录被选中的 neighbor link ⇒ 无可追溯锚点 | **另立 `F-2 Q4-R1`** | 约束 **Q4**，不影响 Q2 |

> 一句话：**Q2 的负结果是「方向候选结构不能解释 sec/ter 系统性低估」；Q4 的指标本身可能构造性偏置 —— 二者不混。**
> `ρ(N, improved) = 0.9429`（阶统计量偏倚）在 R2 中**原样保留、未作任何校正**，故不能据此对 Q4 做机制结论。

---

## 7. 为什么本记录写在节点目录**之外**

R2 节点 `reports/secondary_tertiary_residual_7_9f2_v2_1_R2/` 的 15 件产物已被 `f2v21r2_closure_check.csv` 逐件 `size + sha256` 对账，并声明 `declared_set_vs_disk: missing=[]; extra=[]`。
**任何向该目录新增文件都会使门禁 15 `OUTPUT_PROVENANCE` 的 `unknown` 集合非空**，从而破坏「R2 已正式收口」的冻结状态。
故本记录放在伴随诊断目录，节点目录保持 **零写入**。

---

## 8. R2 节点冻结留痕（15 件，2026-09-27 20:29:43 / 20:29:58）

| sha256(前16) | bytes | 文件 |
|---|---|---|
| `e7bd590fb0b49581` | 18,767 | `f2v21r2_target_sections.csv` |
| `89a83b2907469039` | 929,020 | `f2v21r2_all_e1_candidates.csv` |
| `159581fd953ead61` | 86,519 | `f2v21r2_selected_ab_candidates.csv` |
| `cff9fcd1113895ee` | 21,550 | `f2v21r2_direction_candidate_summary.csv` |
| `e69df9864237522f` | 933,721 | `f2v21r2_direction_candidate_long.csv` |
| `fd4a8d084daf1d91` | 303 | `f2v21r2_q2_correlations.csv` |
| `d384f1148abdc7b2` | 424 | `f2v21r2_group_summary.csv` |
| `96042abe4c7c3684` | 209,367 | `f2v21r2_single_link_capture.csv` |
| `9272b4d64b90b5e0` | 3,243 | `f2v21r2_q4_summary.csv` |
| `5db00d70a035c8b6` | 2,659 | `f2v21r2_obs_rebuild_check.csv` |
| `5c561e3529f0cf4d` | 2,220 | `f2v21r2_checks.csv` |
| `b8c155a36504c423` | 568 | `f2v21r2_summary.json` |
| `14eba915aa28d086` | 4,732 | `f2v21r2_input_manifest.json` |
| `86e2d42670ac6bde` | 6,292 | `f2v21r2_closure_check.csv` |
| `5ca719ba27ee5a14` | 5,397 | `STEP7_9F2_v2_1_R2_REPORT.md` |

**TOTAL_BYTES = 2,224,782**

### 8.1 交付件身份

| 件 | SHA256 | bytes |
|---|---|---|
| `PREREG_7_9F2_v2_1_R2.md` | `0a0c61336056a66d5ea1506215b1680d3920aef2cb804a221571812e9de18a19` | 4,617 |
| `audit_secondary_tertiary_residual_7_9f2_v2_1_R2.py` | `1d12aa799dc4e707ed6531621e61c4da00130d4c9d7058645f8ff1bd83fd35fb` | 43,759 |
| `.py.bak_asprovided` | 同上（**正本 == bak，逐位一致**） | 43,759 |

### 8.2 污染核对（本轮及累计均为零）

| 目录 | files | mtime |
|---|---|---|
| `secondary_tertiary_residual_7_9f2` | 13 | 09-23 12:26–12:27 |
| `secondary_tertiary_residual_7_9f2_v2` | 15 | 09-23 20:34–20:35 |
| `secondary_tertiary_residual_7_9f2_v2_1` | 1 | 09-24 07:50 |
| `secondary_tertiary_residual_7_9f2_v2_1_R1` | 14 | 09-26 20:52 |
| `secondary_tertiary_residual_7_9f2_v2_1_R1_PREREG` | 1 | 09-26 20:49 |
| `secondary_tertiary_residual_7_9f2_v2_1_R2` | 15 | 09-27 20:29 |

MATSim / Java：**未调用（NO）**。网络 / OD / v1.0：**未改**。

---

## 9. 复现命令

```bash
python scripts/od/audit_secondary_tertiary_residual_7_9f2_v2_1_R2.py \
  > reports/secondary_tertiary_residual_7_9f2_v2_1_R2_asprovided_diag/_run_asprovided_R2.log 2>&1
# 期望：hard_pass_count=18 / hard_total=18, status=LOCAL_CAPTURE_DIAGNOSTIC_READY, EXIT=0
```

⚠️ 重跑前须确认输出目录为空（R2 在非空目录上会因门禁 15 `unknown` 非空而 FAIL —— 这是设计意图，非缺陷）。

---

## 10. 版本树与工作面

```text
F-2 v2
  ↓
F-2 v2.1-R0            BLOCKED
  ↓
F-2 v2.1-R1            BLOCKED  (+ probe READY，非正式)
  ↓
F-2 v2.1-R2            LOCAL_CAPTURE_DIAGNOSTIC_READY  ← 正式节点（本次）
  ↓    Q2 ⇒ 正式 negative diagnostic（本记录）
  ↓
F-2 Q4-R1              另立 prereg：single-link capture 重定义 + traceability
  ↓
SKILL.md 7.9A–F 统一重构（待 Q4-R1 之后）
```

工作面锁定：`✅ R2 关闭 / ✅ Q2 进入正式结论 / ⏸ Q4 另开 Q4-R1 / ⏸ SKILL 重构延后`

---

*本文档为 Q2 的正式诊断记录，只陈述 R2 节点产物所支持的量；不引入新计算、不改任何冻结量。*
