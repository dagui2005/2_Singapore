# STEP 7.9F-2 v2 — 正式节点收口证据

**日期**：2026-09-23
**授权范围（用户裁定）**：仅修 **D1/D2/D3/D6/D7** 的执行与契约缺陷；**判据、阈值及已有分析口径不变**；
D4/D5 原样冻结并标注为"结构性不可解释/仅描述、不进入机制结论"；**不得借 v2 修改 Q2/Q4**。

---

## 一、节点身份

| 项 | 值 |
|---|---|
| v2 预注册 | `reports/secondary_tertiary_residual_7_9f2_v2/PREREG_7_9F2_v2.md`（16,041 B） |
| **v2 prereg SHA256** | `018d1562bb452948befce23ed925065f4a3da855f1724476c7ccb55c109146d6` |
| v2 脚本 | `scripts/od/audit_secondary_tertiary_residual_7_9f2_v2.py`（52,130 B） |
| v2 脚本 SHA256 | `7e8e45c13aa657c3…`（与 manifest 内记录**一致**） |
| R0（侦察运行） | `reports/secondary_tertiary_residual_7_9f2/`（13 件，mtime 12:26–12:27，**未被触碰**） |
| R0 as-provided 备份 | `scripts/od/audit_secondary_tertiary_residual_7_9f2.py.bak_asprovided_20260923` |
| 补丁脚本 | `scripts/od/_patch_7_9f2_v2.py`（16 处锚点，全部 `assert` 命中） |

## 二、正式运行结果

```
[1/6] target valid sections = 109        [5/6] hard gates           = 16/16
[2/6] selected candidates  = 593         [6/6] STATUS               = MECHANISM_AUDIT_READY
[3/6] network links        = 706,554           R0 (read-only)      = …\secondary_tertiary_residual_7_9f2
[4/6] W01 links            = 693,575           CLOSURE A1..A8      = A1..A8 PASS (declared=12, manifest=11, fails=0)
EXIT=0
```

## 三、D1/D2/D3/D6/D7 逐项落实与实测证据

| 编号 | 落实现状 | 实测证据 |
|---|---|---|
| **D1** | manifest **最后写**；`generated_artifacts` 由**显式声明清单**生成（不再 `iterdir()`）；新增写后断言 **A2/A3** 双向哈希保真；`F2.15` 增加无杂散 + R0 隔离 + 外部瞬时文件白名单 | manifest **11 条 / 0 条陈旧 / 0 条 declared-but-absent**（R0 为 4 条陈旧 + 1 条缺失）；`iterdir()` 用量 R0=1 → v2=4（仅用于杂散检查与 R0 隔离，**不用于生成 manifest**） |
| **D2** | `DECLARED_ARTIFACTS` 与 prereg §12 **完全一致（12 项）** | 磁盘 12 项声明产物 **全部存在**；`f2_direction_candidate_long.csv`（R0 无门禁覆盖）纳入 `F2.15`；`declared present = True` |
| **D3** | **单次终局求值** + 执行顺序契约（prereg §10.5） | `build_checks()` 调用点 **R0=2 → v2=1**；`write_report()` R0=3 → v2=2（PENDING + 终局）；磁盘 `f2_checks.csv` **16 行、无 PENDING 残留**；**D 之前不写任何含判决的产物** |
| **D6** | `F2.04` detail 披露原始行数与全部剔除量 | `raw_rows=67,471; dropped_tier_C=51,688; dropped_missing_distance=0; kept_rows=15,783` |
| **D7** | **代码实际由冻结 JSON 重建 `obs_8_9`**，与 E2 逐 LinkID 校验；新增门 `F2.16` + 证据 `_f2v2_obs_crosswalk.csv` | `F2.16`：`e2_rows=1,311; matched=1,311; max_abs_delta=4.54747e-13; mismatch_gt_1e-09=0`；109 条 target 上 `max|Δ| = 0.0` |

### 3.1 两处第一手命中（新增检查**有效工作**的直接证据）

1. **`A4` 首次拦截自指脚手架**
   v2 首次正式运行在 `assert_closure` 的 `A4`（无杂散）中止：
   `AssertionError: A4 stray files in secondary_tertiary_residual_7_9f2_v2: ['PREREG_7_9F2_v2.md']`
   —— 预注册文件必须常驻输出目录（`F2.01` 需取其哈希），但未被声明为产物。已按协议在 prereg §12
   把它显式列入白名单并重算哈希后重跑。**R0 版本无此检查，永远不会发现。**
2. **外部同步瞬时文件被识别并披露，而不是污染 manifest**
   `F2.15` 终局 detail：
   `ignored_transient=['_run_v2.log.baiduyun.uploading.cfg']`
   —— **同一现象在 R0 中把该文件写进了 `generated_artifacts`，留下一条 declared-but-absent 且无人发现**；
   v2 将其识别为外部瞬时文件、**排除出 manifest 并在门禁 detail 中公开**。

## 四、v2 ↔ R0 对账（**分析口径未变的证明**）

### 4.1 函数级
`scripts/od/_f2v2_function_diff.py`：R0 28 个函数 / v2 31 个（新增 `is_transient`、`obs_crosswalk`、`assert_closure`）。
**24 个分析关键函数逐字节相同**（含 `load_traffic_json`、`load_traffic_geometry`、`select_links`、`load_e2`、
`load_network`、`load_w01`、`candidate_structure`、`direction_diagnostics`、`local_neighbors`、`build_summary`、
`mechanism_summary`、`provenance` 及全部工具函数）；仅 4 个按授权改动
（`load_candidates`、`build_checks`、`write_report`、`main`）。

### 4.2 产物级：**8 件分析产物逐字节相同**

| 产物 | sha256 前 12 位 | 与 R0 相同 |
|---|---|---|
| `f2_target_sections.csv` | `e7bd590fb0b4` | ✅ |
| `f2_selected_candidates.csv` | `159581fd953e` | ✅ |
| `f2_candidate_structure.csv` | `f28d98461e16` | ✅ |
| `f2_direction_diagnostics.csv` | `d93bc71de856` | ✅ |
| `f2_direction_candidate_long.csv` | `348d902ac77f` | ✅ |
| `f2_local_neighbors.csv` | `b1411a6122b4` | ✅ |
| `f2_mechanism_summary.csv` | `c4ad0dffb04e` | ✅ |
| `f2_group_summary.csv` | `d459f60c9cd5` | ✅ |

⇒ **`ALL ANALYTIC ARTIFACTS BIT-IDENTICAL: True`**。即 v2 **没有触碰任何一个分析数值**。

### 4.3 与 F-1 的上游复现保持
| 等级 | v2 mean / median | F-1 `CANONICAL_MEDIAN` | 相等 |
|---|---|---|---|
| secondary | `−0.395459768956448 / −0.560550867256637` | 同 | ✅（<1e-15） |
| tertiary | `−0.560180563688507 / −0.665904770393877` | 同 | ✅（<1e-15） |

### 4.4 静默丢弃
`selected 593 = structure Σselected_total_n 593 = direction_long 593`；`dir_n ≠ sel_n` 的断面 **0**；
E1 与重算方向差 `max|Δ| = 7.105e-15`（浮点尾差）。

## 五、D4 / D5 冻结与披露（**未改一字**）

`f2_summary.json` 新增两个**披露字段**（非判据）：

```
d4_q2_status       = STRUCTURALLY_UNANSWERABLE__DESCRIPTIVE_ONLY
d5_envelope_status = SUM_CALIBER_NOT_COMPARABLE_TO_OBS__DESCRIPTIVE_ONLY
```

- **D4（Q2）**：Tier A/B 以方向合格为选择前提 ⇒ 109/109 断面 `direction_good_share = 1.0`、
  593 条候选重算方向差 `max = 29.818° < 30°` ⇒ 该组相关统计量**未定义（NaN）**。
  prereg §8 与 **R-F2-11** 明示：**只作描述，不进入机制结论**；不得在 v2 内换域或补量"救活"它。
- **D5（Q4 包络）**：`matched_flow_raw` 是**同一批链路的 Σ**，E2 residual 是**同一批链路的 median**；
  每断面选中链路 2/5/11 条 ⇒ `Σ×SCALE/obs` 中位 **1.93（sec）/1.65（ter）**，
  `|envelope_ratio−1|−|matched_ratio−1|` 中位 **+1.94/+4.58/+9.19**（20/50/100 m），"改善"占比仅 **3.7%–6.4%**。
  prereg §7 与 **R-F2-12** 明示：**原样冻结、只作描述、不进入机制结论**；
  不得在 v2 内改为 median 口径、方向折叠或引入第二口径。

⇒ **`f2_mechanism_summary.csv` 中 `DIRECTIONALITY` 四行为 NaN、`LOCAL_FLOW_ENVELOPE` 各行在 D5 解决前不得作机制解释。**
（`parallel_added_share` 的 +0.62/+0.70 等看似最强信号，建立在与 obs 不可比的 `added_share` 上。）

## 六、独立核验（脚本之外）

| 项 | 结果 |
|---|---|
| prereg SHA256 | `018d1562…46d6` = 脚本内嵌值 = 运行时实测值 ✅ |
| 12 件声明产物 | 全部存在且非空 ✅ |
| manifest 覆盖 | 键集 == 声明集 − manifest 自身（11）✅ |
| manifest 哈希保真 | **0 条陈旧**、**0 条 declared-but-absent** ✅ |
| 杂散文件 | **0**（`ignored_transient` 仅 1 条外部同步文件，已披露）✅ |
| R0 隔离 | R0 目录 13 件、mtime 12:26–12:27 未变、无 `_v2`/`f2v2*` 命中 ✅ |
| 门禁 | **16/16 全 PASS**，磁盘无 PENDING 残留 ✅ |
| 脚本身份 | manifest 内 `script.sha256` == 磁盘实测 ✅ |

## 七、纪律核对

| 项 | 状态 |
|---|---|
| 启动 MATSim / 调用 Java | ❌ 未发生（`F2.02` AST 门 + `ZERO_SIM_IMPORT_VIOLATIONS=0`） |
| 修改 network / capacity / lanes / speed | ❌ 未发生 |
| 修改 route-choice / scoring / QSim | ❌ 未发生 |
| 修改 7.3.6A / 7.6H / F-0 / F-1 / E1 / E2 / TrafficFlow | ❌ 未发生（全部只读；E2 frozen residual `F2.16` 仅比对、未回写） |
| 重算 SCALE | ❌ 未发生（`SCALE = 459794/200000`） |
| 产生 v1.1 | ❌ 未发生 |
| 回写 E2 frozen residual | ❌ 未发生（R-F2-1 遵守） |
| 改写 R0 目录 | ❌ 未发生（`A8` 断言 + 独立核验） |
| 改动 Q2/Q4 提问方式 | ❌ 未发生（R-F2-11 / R-F2-13 / R-F2-14） |

## 八、下一步（**待用户裁定**）

F-2 v2 收口后，证据链为：**"工程执行问题修好了；科学问题没有趁机改定义。"**

若仍需处理 D4/D5，须**独立立项** `PREREG_7_9F2_v2.1`，例如：
- Q2 换域（C 档 / 反向候选 / 未匹配候选）并补实现 `reverse-candidate share`；
- Q4 增加方向折叠后的第二口径（或显式声明"不与 1 可比"并把 Q4 限定为半径间/类型间对比）。

**在上述裁定之前，F-2 的机制解释暂停在"已知 D4 不可答、D5 不可比"的边界内。**

---

## 7. 终局复核时的补充观察（收口后一次性回查，不改动任何冻结产物）

### 7.1 `declared=12` 与 `manifest=11` 不是缺口，而是**设计**且被 A2 显式断言

```
A2: want = set(DECLARED_ARTIFACTS) - {"f2_input_manifest.json"}
    got  = set(manifest["generated_artifacts"])
    assert got == want
```

`f2_input_manifest.json` 本身在 §12 声明集内（故 declared=12），但它**最后写**，无法包含自身哈希 ⇒
`generated_artifacts` 恒为 11 条。A2 用 **排除自身的显式集合** 双向断言，而非放宽容差。
⇒ **"12 vs 11" 是可复算的构造性差额，不是漏写产物。**

### 7.2 命名观察（低风险，仅提示，不构成缺陷、不触发 v2 变更）

`provenance()`（L632，与 R0 **逐字节相同**，被调用 1 次 @L909）实际构建的是
**输入侧清单**（traffic_json / e1 / e2 / network / nodes / w01 / prereg / script 的 sha256+size+mtime ⇒ `f2_input_manifest.json`）；
而**输出侧 provenance 门禁**是 `build_checks()` 内被修补的 `F2.15` 段（L771，`prov_pass` / `prov_detail`）。

⇒ 同名不同物：**函数名 `provenance` 指输入清单，门禁 `F2.15_OUTPUT_PROVENANCE` 指输出自证。**
二者无冲突、无死代码（`provenance` 确实被调用），但**后续若有人按函数名找"输出 provenance 实现"会找错位置**。
建议在 v2.1 或下一节点顺手改名（如 `input_manifest`），**本轮不动**。

### 7.3 终局一致性双重确认（本次回查实测）

| 项 | 实测 |
|---|---|
| `prereg_v2` SHA256 | `018d1562bb452948befce23ed925065f4a3da855f1724476c7ccb55c109146d6` ✓ 与 `f2_checks.csv`/`f2_summary.json`/manifest 三处一致 |
| `script_v2` SHA256 | `7e8e45c13aa657c3c827f39533cc8e9d5cd9b49f23141cc31f700d74c70190c4` ✓ 与 manifest `script.sha256` 一致 |
| 分析产物逐字节同 R0 | **8/8 BIT-IDENTICAL**（candidate_structure / direction_candidate_long / direction_diagnostics / group_summary / local_neighbors / mechanism_summary / selected_candidates / target_sections） |
| 契约层产物按授权改动 | **4/4 应改**（`f2_checks.csv`、`f2_summary.json`、`f2_input_manifest.json`、`STEP7_9F2_REPORT.md`） |
| v2 新增件 | 3 件（`PREREG_7_9F2_v2.md`、`_f2v2_obs_crosswalk.csv`、`_run_v2.log`） |
| R0 目录 | 13 件、mtime 12:26–12:27、零 `_v2` 命中、零外部瞬时文件 ⇒ **未被触碰** |
| D7 target 子集 | 109/109 匹配、`max|Δ| = 0.0`、非零 **0** |
| D7 全库 | 1,311/1,311 匹配、3 处浮点尾差 `4.547473508864641e-13`（LinkID 44880 / 46623 / 49264），**均 < tol 1e-9** |
