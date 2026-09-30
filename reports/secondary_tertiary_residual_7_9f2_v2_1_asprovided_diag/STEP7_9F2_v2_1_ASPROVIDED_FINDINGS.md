# STEP 7.9F-2 v2.1 — as-provided 审计发现

**节点**：`F-2 v2.1`（R0 = as-provided）
**协议**：zero-simulation / read-only / diagnostic-only
**审计日期**：2026-09-24
**审计方式**：身份核验 → 静态审计 → 输入 schema 预检 → as-provided 实跑 → 最小 probe 打通下游 → 独立复算

---

## 0. 结论摘要（一句话）

**v2.1 as-provided 不可运行**：在两处硬崩（P0-1 W01 路径、P0-2 `name_norm`）修掉后可达 **16/16 READY**，但该 16/16 **不能等同于"数据链有效"**——其中 **1 条在默认布局下必 FAIL（P1-3）**、**1 条是检查错目录的空门（P1-4）**、**3 条判据项恒真（P1-5）**，且 **Q4 的核心量存在构造性偏倚（P2-10）与不可追溯性（P2-11）**。

⇒ **不建议把 as-provided 结果当作 v2.1 正式节点。**

---

## 1. 身份与静态核验（全部通过）

| 项 | 结果 |
|---|---|
| `PREREG_7_9F2_v2_1.md` SHA256 | `b495e2750b3cdae9ab5be51bd11dee8c4d7743ef0ba3e485cc1c5fe9d45ecf71` ✓ **= 你声明值** |
| `audit_..._v2_1.py` SHA256 | `c02ca038e1f7687a4e83b5fac7e165ee1eca388eabb6945812ccdc2953070a59` ✓ **= 你声明值** |
| 下载件 ↔ 工程件 | 三处（`scripts/od/` 正本 + `.bak_asprovided_20260924` + `reports/..._v2_1/PREREG…`）**逐位一致** |
| 代码内嵌 `EXPECTED_PREREG_SHA256` | **命中** |
| AST 解析 / 内存编译 / 零仿真 import | 通过（与你的自检一致） |

**输入 schema 预检（全部匹配，无一处声明错误）**

| 输入 | 实测 |
|---|---|
| E1 `e1_crosswalk_candidates.csv` | 12 列，含 `semantic_compatible` / `name_similarity` / `tier` / `direction_diff_deg` ⇒ `select_ab` 的排序键与 `e1_load` 的映射**无冲突、无缺列** |
| E2 | 17 列，所需 6 字段齐备 |
| network links | `from_node,to_node,travel_time_s,length_m,speed_kmh,highway,lanes,name` ✓ |
| network nodes | `node_id,x_svy21_m,y_svy21_m,lon,lat` ⇒ 三选一识别器命中 ✓ |
| W01 | 154 列，`LINK` / `HRS8-9avg` 均在 ✓ |
| scipy | 1.17.1 可用（`cKDTree` 依赖满足） |

⇒ **prereg 的路径与字段声明这一版是对的**（F-0/F-1 各错 ≥1 处的规律这次没有复现）。

---

## 2. as-provided 实跑结果：**两次崩溃，均未到达任何门禁**

### Run 1 — 按代码默认布局（`python scripts/od/audit_..._v2_1.py`）

```
PermissionError: [Errno 13] Permission denied:
  'D:\Luan\2026-05\2_Singapore\matsim_final_7_6h\outputs\W01_rc_min\ITERS\it.19'
```
```
File "...v2_1.py", line 118, in w01_load
    with op(p,"rt",encoding="utf-8",errors="replace") as f: ...
EXIT=1
```
正式目录最终**只剩 `PREREG_7_9F2_v2_1.md`**，零产物。

### Run 2 — 显式传 `--w01-linkstats <file>`

```
UserWarning: Pandas doesn't allow columns to be created via a new attribute name
AttributeError: 'DataFrame' object has no attribute 'name_norm'
  File "...v2_1.py", line 157, in q4
    names={x for x in focal.name_norm if x}
EXIT=1
```

### 最小 probe（仅改 1 处）后才能打通

`scripts/od/_probe_v21_run.py` = as-provided 的副本，**唯一改动**：
```python
# 原： g.name=g.name.map(nt); g.name_norm=g.name.map(nn);
# 改： g.name=g.name.map(nt); g["name_norm"]=g.name.map(nn);
```
并令输出目录 basename 保持 `secondary_tertiary_residual_7_9f2_v2_1`，以使 `out.name==OUT_REL.name` 门禁可判。

| probe | 输入 | 结果 |
|---|---|---|
| **A** | prereg 外置（指向正式目录） | `16/16` · `LOCAL_CAPTURE_DIAGNOSTIC_READY` · **EXIT=0** |
| **B** | prereg 与产物**同目录** | `15/16` · `BLOCKED` · `F2V21.15 FAIL` · EXIT=1 |

---

## 3. 缺陷清单（按严重度）

### 🔴 P0-1｜W01 路径未定位到文件 —— BLOCKER

- `L18: W01_REL=Path("matsim_final_7_6h/outputs/W01_rc_min/ITERS/it.19")` ⇒ **是目录**（prereg §2.5 自己末尾也带 `/`）。
- 目录内容实测：`W01_rc_min.19.linkstats.txt.gz` + 2 个 txt。
- F-2 v2 里处理这一点的 `locate_w01()`（`is_file()` → 否则 `glob("*.linkstats.txt.gz")`）在 v2.1 **被整体删除**（函数级 diff：v2 33 个函数、v2.1 25 个，仅 `main`/`sha256_file` 同名）。
- ⇒ **按 prereg 与代码共同声明的默认布局，as-provided 一行分析都跑不出。**

**处置建议**：恢复 `locate_w01()` 语义（`--w01-linkstats` 允许目录或文件）。

---

### 🔴 P0-2｜`name_norm` 新建列用了属性赋值 —— BLOCKER

- `L112: ... g.name_norm=g.name.map(nn); ...`
- pandas 3 对该写法**只发 `UserWarning`，不建列**（同一行的 `g.from_node=` / `g.name=` 因列已存在而正常）。
- 于是 `q4()` 的 `L157 focal.name_norm` 直接 `AttributeError`。
- ⇒ 与 v2 的教训同族（「**pandas 3 静默 no-op**」），但这次是 **新建列** 场景。

**处置建议**：一律 `g["name_norm"]=...`；并把该 `UserWarning` 升级为**致命**（见 P1-6 的闭环断言）。

---

### 🟠 P1-3｜`F2V21.15` 在默认布局下**必 FAIL**

probe B 实测：
```
F2V21.15_OUTPUT_PROVENANCE,False,
  declared=15; all_declared_exist=True;
  unknown_stray=['PREREG_7_9F2_v2_1.md']; ignored_transient=[]
→ STATUS=LOCAL_CAPTURE_DIAGNOSTIC_BLOCKED, EXIT=1
```
- 成因：`L195` 的 `existing = {p.name for p in out.iterdir()}` 与 `names` 白名单比对，而 `L20 PREREG_REL=OUT_REL/"PREREG_7_9F2_v2_1.md"` ⇒ **prereg 被代码自己的默认值放进输出目录**，随即被判为 stray。
- ⇒ 这不是"用户放错位置"，是 **代码自相矛盾**：默认输入位置 = 默认输出目录。
- F-2 v2 用 `AUX_ALLOW` 白名单（含 `PREREG_7_9F2_v2.md`）解决了同一问题，**v2.1 没有白名单机制**。

**处置建议**：加 `AUX_ALLOW`（至少含 prereg），并在 prereg §8 明确"prereg 常驻输出目录，不计入 stray"。

---

### 🟠 P1-4｜`F2V21.16` 是**空门**，且**检查错目录**

原文（精确）：
```python
{"check":"F2V21.16_V2_1_ISOLATION",
 "pass":not list((out.parent/"secondary_tertiary_residual_7_9f2").glob("f2v21_*")),
 "detail":"isolated from F-2 v2 directory"}
```
- prereg §6 gate 16 写的是「v2.1 outputs 与 **F-2 v2 目录** 隔离」，代码 glob 的却是 **R0 目录** `..._7_9f2`（少 `_v2`）。
- 实测 R0 目录 13 件、**零 `f2v21_*`** ⇒ glob 恒空 ⇒ `pass` **恒 True**。
- ⇒ **判据与声明不符 + 空门 + detail 文案是假陈述**（它声称"isolated from F-2 v2 directory"，但从未看过那个目录）。
- 双向隔离本身**实际成立**（我独立核验：v2 目录 15 件、R0 目录 13 件，均无 `f2v21_*`）——**但那是事实，不是这条门禁证明的。**

**处置建议**：改为对 `..._7_9f2_v2` **与** `..._7_9f2` **两个**目录各做一次 `f2v21_*` 断言。

---

### 🟠 P1-5｜三条门禁判据项**恒真**（后验恒 True）

实测（用 as-provided 模块本体，喂入构造的坏输入）：

| 门禁 | 判据项 | 实测 |
|---|---|---|
| `F2V21.05` | `not net.matsim_link_id.duplicated().any()` | `network_load` 对重复 id **抛 ValueError**（"重复 matsim_link_id"）⇒ 到达门禁前已拦截 ⇒ 恒真 |
| `F2V21.06` | `not stats.LINK.duplicated().any()` | `w01_load` 对重复 LINK **抛 ValueError**（"W01 LINK 重复"）⇒ 恒真 |
| `F2V21.03` | `c.tier.isin(TIERS).all()` | `e1_load` 已 `x[x.tier.isin(TIERS)]` 过滤 ⇒ 喂入 `Z_BOGUS` 后被丢弃，表达式返回 `True` ⇒ 恒真 |

- 后果：这三条被当作"内容门禁"计入 `Hard gates 16/16`，**实际零信息量**。
- prereg §6 gate 6 还要求「W01 `LINK/HRS8-9avg` **complete** and unique」——**`HRS8-9avg` 的完备性根本没有检查**（只查了非空与唯一）。

**处置建议**：判据移到 loader **内部**（先测后丢），或改成对**已载入表的实测统计**（如 `HRS8-9avg` 非空率、NaN 率），使门禁携带实测值。

---

### 🟠 P1-6｜**无终局闭环断言**（F-2 v2 的 A1–A8 未继承）

- 实测：脚本**不存在**任何 `assert_closure` / `assert*` 函数（AST 扫得 `False`）。
- `manifest` 在 `L226` **最后写**（这点做对了），但**写完之后没有任何回查**：既不验"manifest 每条仍在磁盘且哈希一致"，也不验"磁盘产物都在 manifest"。
- 对比 F-2 v2：正是靠 `A1..A8` 抓到了 stale manifest / 自指脚手架 / 瞬时文件。
- 现实风险已存在：v2 目录同级就有外部同步瞬时文件（`.baiduyun.uploading.cfg`）先例。

**处置建议**：补 `assert_closure()` ≥6 条（声明集存在、manifest↔磁盘双向、无 stray、checks 唯一求值、status 与 FAIL 数一致、隔离双向）。

---

### 🟡 P2-7｜`direction_class` 把 **NEUTRAL 全标成 UNKNOWN**（3,816 行）

prereg §3 定义三类：`FORWARD ≤30°`、`REVERSE ≥150°`、`NEUTRAL 30°~150°`。

实测 `f2v21_direction_candidate_long.csv`（7,277 行）：

| direction_class | 行数 |
|---|---|
| FORWARD | 1,780 |
| REVERSE | 1,681 |
| **UNKNOWN** | **3,816** |
| `direction_diff_deg` 缺失数 | **0** |
| `30 < d < 150` 的条数 | **3,816** |

- 代码用 `np.select([...],["FORWARD","REVERSE"], default="UNKNOWN")`，**`NEUTRAL` 这个标签从未产出**。
- 由于方向缺失数为 **0**，这 3,816 行**全部是真的 NEUTRAL**，却被标为「UNKNOWN」⇒ **标签与语义完全相反**，且与同批产出的 `f2v21_direction_candidate_summary.csv`（`neutral_n` 合计 = 3,816 ✓ 计算正确）**自相矛盾**。
- 讽刺的是：你特意修掉了"缺失方向被标成 NEUTRAL"，现在变成了"NEUTRAL 被标成 UNKNOWN"。

**处置建议**：`default` 分支拆成 `NEUTRAL`（有值且 30<d<150）与 `MISSING`（无值）两类。

---

### 🟡 P2-8｜`reverse_any` 恒 True ⇒ `q2_correlations` **静默 NaN**

实测 `f2v21_q2_correlations.csv`：
```
reverse_share,109,0.05579
forward_share,109,0.05090
median_direction_diff_deg,109,-0.04819
reverse_any,109,            ← 空（NaN）
C_GEOMETRY_ONLY_reverse_share,109,0.11560
C_GEOMETRY_ONLY_forward_share,109,0.00065
```
- 成因：`reverse_any` 对 **109/109** 全部为 `True`（`f2v21_direction_candidate_summary.csv` 实测 `{True: 109}`）⇒ `spr()` 的 `nunique()<2` 判据触发 ⇒ `NaN`。
- 这是 prereg §3 明列的 5 项固定 Spearman 之一，却在**没有任何披露**的情况下退化为空值。
- 与 F-2 v2 的 D4 属**同一失效模式**（恒定量 ⇒ 静默 NaN），只是这次成因是**结构性真实**（每个目标断面都至少有 1 条反向候选），而非循环论证。

**处置建议**：把该项改写为"**该量结构性不可变（109/109 为 True）**"的显式披露；或改用 `reverse_n / reverse_share` 的变异（它们有变异）。

---

### 🟡 P2-9｜`capture_improved` 把 NaN **强转 False** ⇒ `improved_share` 被"邻接可得性"稀释

`L176`：`"capture_improved": bool(ch<0) if np.isfinite(ch) else False` ⇒ 无邻接（或邻接全无 W01 覆盖）的断面一律记 **False**。

独立复算（`neighbor_type=parallel`，全 109 断面）：

| radius | 有正流邻接 | 无正流邻接 | `improved_share`（全样本） | `improved_share`（**仅**有正流） |
|---|---:|---:|---:|---:|
| 20 m | 51 | 58 | **0.1284** | **0.2549** |
| 50 m | 100 | 9 | 0.4679 | 0.5100 |
| 100 m | 105 | 4 | 0.5872 | 0.6095 |

- 20 m 处**腰斩**（0.1284 vs 0.2549）：一半的"未改善"根本不是"没改善"，而是**没有可比的邻接**。
- ⇒ `capture_improved_share` 混合了「capture 改善」与「邻接覆盖率」两个概念，**未加披露**。

**处置建议**：分母限定为 `neighbor_positive_flow_n > 0`，并**同时**报告覆盖率。

---

### 🟠 P2-10｜Q4 的 `best_single_link_ratio` 是 **N(r) 阶统计量** ⇒ **半径间 / 类型间不可比**

- 定义：`best = max(W01 flow of neighbors)` ⇒ 对 N 条候选取最大 ⇒ **均值向上偏、方差随 N 收缩**。
- 实测（`parallel`，`f2v21_q4_summary.csv`）：

| 半径 | `median_neighbor_n` | `capture_improved_share` |
|---|---:|---:|
| 20 m | 1.0（secondary）/ 0.0（tertiary） | 0.135 / 0.100 |
| 50 m | 9.0 / 8.0 | 0.472 / 0.450 |
| 100 m | 23.0 / 24.0 | 0.596 / 0.550 |

- **Spearman(`median_neighbor_n`, `capture_improved_share`) = 0.9429**（跨 6 个 radius×highway 单元）。
- 即：**"改善"基本由"邻域里有多少条路"驱动**，而不是由"流量是否真的落在邻近替代道路上"驱动。
- `neighbor_type` 之间同理（twin 的 N 系统性大于 parallel ⇒ twin 的 improved_share 系统性更高）。
- ⇒ 你想避免的"**指标构造性为正**"问题（原 D5 的 Σ 口径），在 v2.1 里**换了一个形式重新出现**。`R-F2V21-5`（不按 residual 选邻居）**挡不住**这一类偏倚，因为它是**样本量**造成的，不是**选择变量**造成的。

**这不是"执行缺陷"，是"诊断量定义"问题**，性质与 D5 同类。三条可选路线，请你裁定：
1. **加空模型基准**：在同一邻域内对 W01 流量做置换，报告 `best` 的零分布 ⇒ 给出 `capture_gain` 的显著性/期望值（最有力，但要新增分析）。
2. **限定为"与 canonical anchor 等 N 可比"**：例如只取最近邻 1 条，或按 N 分层的第 k 阶统计量。
3. **只作描述、显式声明不可比**：在报告里写死"**`capture_gain(r)` 不可跨半径比较**"，与 D5 同处理。

---

### 🟠 P2-11｜Q4 未记录"被选中的是哪条 link" ⇒ 核心量**不可追溯**

- `f2v21_single_link_capture.csv` 的 15 列中**没有**被选中 neighbor 的 link id（精确复核：唯一含 `LinkID` 的是 section 自己的 id；我最初的锚点扫描把 `diagnostic_residual_8_9` 里的 "id" 误判为命中，已纠正）。
- 后果：
  1. 无法验证 `best_single_link_flow_raw` 取自哪条路 ⇒ **审计不可复核**；
  2. 无法检查**同一条高流量 link 被反复复用**（若是，则"当地截获"其实是"全网最大流"的别名）；
  3. 无法判断 P2-10 的偏倚方向（若被选 link 集中在少数几条，N 的差异会被进一步压缩/放大）。

**处置建议**：加 `best_single_link_id`（可再加 `best_single_link_flow_scaled`）。

---

### 🟢 P3-12｜「排除自身及 selected anchors」歧义（实测影响面 4–17%）

- prereg §4 原文「排除自身及 selected anchors」；代码只排**本 section 自己的** anchors（`if nid in mids`），未排**全局 593 条**。
- 独立复算每 section 邻接条数中位数：

| 半径 | 仅排自身 | 再排全局 593 | 与全局 anchor 重叠 |
|---|---:|---:|---:|
| 20 m | 12 | 10 | **2**（≈17%） |
| 50 m | 47 | 43 | 4 |
| 100 m | 121 | 116 | 5 |

- 重叠条次合计 **1,146 / 20,594**。
- 影响不大但**非零**，且由于选的是 max-flow 那条、而 anchor 恰是高流量主干 ⇒ **可能翻转个别 `capture_improved` 判定**。

**处置建议**：在 prereg 里把"selected anchors"明确为「本 section 的」或「全局的」，二者只留一个说法。

---

### 🟢 P3-13｜`f2v21_all_e1_candidates.csv` 名不副实

- 文件名含 `all`，实为 **target 子集**：7,277 行 / 109 个 `lta_linkid`（全量 E1 = 67,471 行）。
- 同时 `f2v21_summary.json` 的 `candidate_raw_rows = candidate_kept_rows = 67,471`（C 档保留，与 F-2 v2 的 15,783 不同口径——**正确**，但两处数字容易被误比）。

**处置建议**：改名 `f2v21_target_e1_candidates.csv`，或在摘要里并列"全量 / target 子集"两个计数。

---

### 🟢 P3-14｜obs 重建**未设门**

- 实测 `f2v21_obs_rebuild_check.csv`：109/109、`max|Δ| = 0.0`、非零 0、`obs_8_9_rebuilt` 无 NaN ⇒ **D7 的成果完美继承**。
- 但该值只进 `f2v21_summary.json`，**prereg §6 的 16 条门禁里没有任何一条检查它** ⇒ 一旦重建规则漂移，无人报警。

**处置建议**：加 `F2V21.17_OBS_REBUILD_REPRODUCED`（`max|Δ| ≤ 1e-9`）。

---

### 🟢 P3-15｜卫生问题（不致命，但会被后来者踩）

| 位置 | 问题 |
|---|---|
| `q4()` L163 | `nid=nr.matsim_link_id` **局部遮蔽了模块级函数 `nid()`** ⇒ 后续若在该函数内调用 `nid()` 会炸 |
| `checks()` L193 | `cc=safe_cov=...` ⇒ `safe_cov` 是死变量 |
| `w01_load()` L118/L121 | 文件被**读两次**（先 `readline` 取表头，再 `pd.read_csv`）⇒ 22 MB gz 解压两遍 |
| `q4()` | `focal.iterrows()` 在邻居循环内被反复调用（O(|idx|×|focal|)）⇒ 可向量化，当前 109 断面尚可 |
| `report()` L224/L225 | 被调用 **2 次**（先 `PENDING` 占位、再真实）⇒ 中间态文件可被误读 |

---

## 4. 正面确认（v2.1 做对且应当保留的部分）

| 项 | 实测 |
|---|---|
| **`select_ab` 精确复刻 F-1/E2 主选择** | `f2v21_selected_ab_candidates.csv` = **593 行**、**A 577 + B 16**、`matsim_link_id` **全局唯一 593**、覆盖 **109** section ⇒ 与 F-2 v2 的 `selected=593` **逐项相同** |
| 域规模 | target **109**、E1 载入 **67,471**、network **706,554**、W01 **693,575** ⇒ 与 F-2 v2 **全同** |
| **obs 重建** | `max|Δ| = 0.0`（109/109，非零 0，无 NaN）⇒ D7 结论在 v2.1 独立复现 |
| **manifest** | 14 条 `generated_artifacts`、**0 陈旧**、显式清单（非 `iterdir`）、**最后写** ⇒ F-2 的 D1 教训已吸收 |
| **`checks()` 单次求值** | 调用点 **1 处**（L225）⇒ F-2 的 D3（双求值）已修 |
| **`transient()`** | 覆盖 `.uploading.cfg` / `.tmp` / `~$` / `.~lock.` ⇒ 外部同步瞬时文件可识别 |
| **冻结输入** | E1 / E2 / network / nodes / W01 / TrafficFlow **哈希逐项未变** |
| **双向隔离** | v2 目录 15 件、R0 目录 13 件，**均无 `f2v21_*`**；F-2 v2 的 `f2_summary.json`(`a7b53d95…`) / `f2_checks.csv`(`87bb75bf…`) 哈希与昨日收口**一致** |
| **零仿真** | AST 审计通过，无 MATSim/Java 调用 |

---

## 5. 科学层面的实质信号（即便工程有问题，这两条结论已可用）

### Q2：**方向候选结构不解释 secondary/tertiary 的残差梯度**

以 **E1 stored A/B/C 全量**（7,277 行，非 A/B selected 域）计算：

| 量 | secondary（n=89） | tertiary（n=20） |
|---|---:|---:|
| `median_direction_diff_deg` | **89.93°** | **90.01°** |
| `median_forward_share` | 0.2375 | 0.2330 |
| `median_reverse_share` | 0.2208 | 0.2404 |
| `median_neutral_share` | 0.5429 | — |
| `reverse_any_prevalence` | **1.000** | **1.000** |

与 frozen residual 的 Spearman（n=109 全部）：

| metric | ρ |
|---|---:|
| `reverse_share` | +0.0558 |
| `forward_share` | +0.0509 |
| `median_direction_diff_deg` | −0.0482 |
| `C_GEOMETRY_ONLY_reverse_share` | +0.1156 |
| `C_GEOMETRY_ONLY_forward_share` | +0.0006 |
| `reverse_any` | **NaN**（恒 True） |

⇒ **E1 存储候选的方向分布近似对称（中位 90°）、neutral 占多数（54%）、forward≈reverse（0.23 vs 0.22），且与残差无关联（|ρ| ≤ 0.116）。**
⇒ **Q2 的答案：方向候选本身（含反向候选）不是 secondary/tertiary 系统性低估的解释。** —— 这是**干净的负结果**，且**避开了循环论证**（域是 A/B/C 全量，不是被方向阈值筛过的 selected 集）。

### Q4：**单链路截获的"改善"目前不可作为机制证据**

`capture_improved_share` 随 N(r) 单调上升（ρ=0.943），且被邻接覆盖度稀释（P2-9）；`capture_gain` **跨半径不可比**（P2-10）；被选 link **不可追溯**（P2-11）。
⇒ **暂不下结论。** 待 P2-9/P2-10/P2-11 处置后重报。

---

## 6. 建议处置（请你裁定）

| 方案 | 内容 | 评价 |
|---|---|---|
| **A（推荐）** | 开 **`F-2 v2.1` 的 v2 修订**，只修 **P0-1 / P0-2 / P1-3 / P1-4 / P1-5 / P1-6 / P2-7 / P2-9**（纯执行与契约层，判据/阈值/Q2-Q4 提问方式**不动**）；**P2-10 / P2-11 单独立项**（属"诊断量定义"，与 D5 同性质） | 与 F-2 的 D1/D2/D3/D6/D7 vs D4/D5 划分同构，证据链最干净 |
| **B** | 把 P2-10 / P2-11 也纳入 v2.1-v2（理由是 v2.1 的任务本就是"重新定义可比诊断量"） | 可行，但会把"执行修复"与"定义重设"混在一个节点里，与你上一轮对 D5 的裁定精神冲突 |
| **C** | 不修，直接把 as-provided 记成 `BLOCKED` 并封存 | 浪费已完成的 Q2 负结果（它其实已可用） |

**无论选哪个**：as-provided 的运行**只能记为 R0**，且 `F-2 v2.1` 目前**没有**一个可称为"正式节点"的产物集。

---

## 7. 纪律核对

| 项 | 状态 |
|---|---|
| MATSim rerun / Java | **NO** |
| network / capacity / lanes / speed 修改 | **NO** |
| E1 / E2 / F-1 / F-2 v2 / 7.3.6A / v1.0 回写 | **NO** |
| SCALE 重估 | **NO** |
| v2 目录 / R0 目录 写入 | **NO**（实测 mtime 与文件数未变，哈希一致） |
| 新增写入位置 | `reports/secondary_tertiary_residual_7_9f2_v2_1/`（仅 prereg，as-provided 崩溃留痕）、`reports/secondary_tertiary_residual_7_9f2_v2_1_asprovided_diag/`、`reports/_f2v21_probe_run{,_B}/`（探针，**非正式**）、`scripts/od/`（脚本 + `.bak_asprovided_20260924` + 只读探针） |
| 对 prereg / 脚本的修改 | **无**（`.bak_asprovided_20260924` 与下载件逐位一致） |

---

## 附录 A：运行日志

- `_run_asprovided.log` —— Run 1（默认布局，PermissionError）
- `_run_asprovided_w01supplied.log` —— Run 2（显式 W01，AttributeError）
- `_probe_A_prereg_external.log` —— probe A（16/16 READY）
- `_probe_B_prereg_colocated.log` —— probe B（15/16 BLOCKED，F2V21.15 FAIL）

## 附录 B：探针产物位置（非正式，仅供复核）

- probe A：`reports/_f2v21_probe_run/secondary_tertiary_residual_7_9f2_v2_1/`
- probe B：`reports/_f2v21_probe_run_B/secondary_tertiary_residual_7_9f2_v2_1/`
