# STEP 7.9I-O3-R1 报告 —— 「观测域重建（Observation-Domain Reconstruction）」

> **状态**：`D2-review ✓ → O3 ✓ → O3-METADATA ✓ → O3-DATA-RECOVERY ✓ → O3-R1 ✓`
> **本步性质**：**零仿真 / 只读**。⛔ 未跑 MATSim；⛔ 未改 v1.0 / crosswalk / `TrafficFlow` 原始值 / 评价器阈值；⛔ 未碰 `signals`/`trafficDynamics`/`speedFactor`；⛔ 未产生 v1.1。
> **判决**：**`status = RECOVERED`** · **`verdict = FACILITY_IDENTITY_UNAVAILABLE_BUT_OBSERVATION_DOMAIN_RECOVERABLE`**
> 硬门 **14/14 `O3R1_GATES_PASS`** · 负例 **6/6 `fired ∧ hit`** · 15 项产物**两次重跑 SHA256 逐位一致** · `EXIT = 0`

---

## §0. 本步定位与两条**正式更正**（必须先读）

### 0.1 研究对象重定义（用户 2026-10-01 18:00 裁定）

**放弃**「必须恢复 `DetectorLoop → Detector ID → Junction ID`」这条链。
**重新定义**为：**LTA 道路观测段（`TrafficFlow` Link）— `RoadSectionLine` — MATSim 道路对象** 的空间观测单元；**`DetectorLoop` 退为辅助空间证据**。

$$\text{旧：}\;\text{observation}\to DetectorID \to DetectorLoop \to RD\_CD \qquad \text{新：}\;\text{observation}\to \text{road section}\to \text{MATSim links}$$

### 0.2 两条更正（**由引擎自身诊断触发**，非事后调参；两轴一律并报，原轴结果保留为审计轨迹）

| # | 缺陷 | 实测证据 | 更正 | 效果 |
|---|---|---|---|---|
| **§0** | **方向轴**：`RoadSectionLine` **无方向语义**，有向 `circ_diff` 把反向绘制误判为不匹配 | `≤25 m` 的 **1,234** 条中 **730** 条有向差 **>30°**；最近距 **p50 6.4 m** | `TF→RSL` 改**轴向**（`min(d,180−d)`）；`TF→MATSim` **保有向** | `TierX 537→64`；`①命中 741→1,214` |
| **§0.2** | **唯一性轴**：预注册把「唯一」实现为「次近候选 ≥10 m」= **并列测试**，把**同一道路的相邻分段**误判为歧义 | `unique_gap→0` 时 `TierA 19→709` | 「唯一」= 命中候选 **`RD_CD` 去重 = 1**；`tie` 轴并报 | `TierA 19→795` |

- **门数 12 → 14**（新增 `G-O3R1-13` / `G-O3R1-14`，均为**更正可复现性**门）。
- **未受影响（一字未改）**：几何阈值（25/30）· `TIER_A_SCORE_MIN=0.70` · `TIER_B_LOOP_MAX_M=50` · `LOOP_BANDS` · Tier 优先级 · 判决空间阈值（0.50/0.10）· 负例集合 · 判读纪律 · 边界。
- **判决稳健性**：`TierA` 在 `rsl50/ang45/rsl50_ang45/score0.50/matsim50` 下为 **818/802/805/920/909**（基线 795）⇒ **非阈值刀锋**。

---

## §1. 输入实测（2026-10-01，逐字解析，未采信任何转述）

| 图层 | ZIP SHA256（前 24） | 记录数 | DBF 字段 | `RD_CD` | 官方 schema（FGDC ∪ `AddField`） | CRS | 几何 |
|---|---|---|---|---|---|---|---|
| **`RoadSectionLine`_Sep2026** | `f817f085e2ced9dbfdd03cd0` | **15,354** | **11** | ✅ **1.0000**（distinct **3,825**） | **12**（11 ∪ 1） | SVY21 | POLYLINE（段 **236,677**） |
| **`DetectorLoop`_Sep2026** | `0fed9592114c196519db0a8f` | **16,275** | **1**（`OBJECTID`） | ❌ **无该列** | **12**（12 ∪ 0） | SVY21 | POLYGON |
| （对照）`RoadSectionLine`_Mar2026 | — | 15,329 | 4 | ❌ **0.0000** | — | SVY21 | — |

### ★三处运行前新观测（已入结论）

1. **`RD_NAM` 仍被剥**：官方并集含 `RD_NAM`，交付 DBF **无此列** ⇒ 新文件是「**保代码、掉路名**」，与旧文件「保文本、掉代码」**正好相反** ⇒ ②→③ **只能用 `RD_CD`**，**无法用路名交叉核对**。
2. **`RD_CD` 含占位值**：`NONAME` **355** 次；长度直方图 **{6: 15,351, 5: 3}** ⇒ 已在 `code_term` 中剔除（`n_placeholder` 命中 **90**）。
3. **`section_geography.csv` 574 行 vs crosswalk 576** ⇒ 两靶场集**差 2**，本步按 `crosswalk` ∪ 显式报基数处理。

**DetectorLoop 结论不变且已实测双月一致（Mar2026 / Sep2026）**：**换月份不能解决**公开导出属性被剥的问题；官方 schema 证明原始 `GDM.DetectorLoop` **确有 `RD_CD`**。

---

## §2. 观测域重建主结果

### 2.1 三层可信度（互斥、优先级 X→A→B→C；分母 = TF 全集 **1,278**）

| Tier | 标签 | 计数 | 占比 | 定义 |
|---|---|---|---|---|
| **A** | `DIRECT_ROAD_SECTION_OBSERVATION` | **795** | **62.21%** | 唯一 ∧ `d≤25` ∧ `ang(轴向)≤30` ∧ 合法 `RD_CD` ∧ `score≥0.70` ∧ MATSim 集非空 |
| **B** | `LOOP_SPATIALLY_ASSOCIATED` | **67** | 5.24% | 非 A，RSL 命中且 `d_loop ≤ 50`（**仅空间邻近**，⛔ 不声称 `Detector ID` 恢复） |
| **C** | `FACILITY_LINKAGE_UNRESOLVED` | **352** | 27.54% | 非 A 非 B，RSL 命中但 `d_loop > 50` 或无 loop |
| **X** | `OBS_DOMAIN_UNMAPPED`（★引擎新增，须披露） | **64** | 5.01% | 无 RSL 满足 `d≤25 ∧ ang≤30` |

> **对照（审计轨迹）**：预注册原文（有向 + tie 轴）= `A 25 / B 151 / C 565 / X 537`；`§0` 已生效 = `A 19 / B 246 / C 949 / X 64`。

### 2.2 逐跳统计（PREREG §4；右键覆盖率的**分母 = 右键全域基数**）

| 跳 | 左→右 | `n_matched_left` | `coverage_left` | `n_matched_right` | 右键全域 | `coverage_right` | `K_pooled` | `1:1` / `1:N` / `N:1` / `N:M` |
|---|---|---|---|---|---|---|---|---|
| **① TF→RSL** | LinkID → `RD_CD` | **1,214** | **0.9499** | **134** | 3,825 | 0.0350 | **1.0000** | 19 / **1,195** / 0 / 0 |
| **② TF→MATSim** | LinkID → 有向边 | **1,104** | **0.8639** | **1,931** | 693,575 | 0.0028 | **1.8687** | **515** / 47 / **427** / 115 |
| **③ TF→LOOP** | LinkID → 检测器（≤50 m） | **252** | **0.1972** | **1,680** | 16,275 | 0.1032 | **8.4444** | 8 / 4 / 132 / **108** |

**读法**：
- **①** `K_pooled = 1.0000` ⇒ **一个观测段 → 恰一个 `RD_CD`**；`c_1_N = 1,195` ⇒ 该 `RD_CD` 同时被多个观测段引用（**1 道路码 ↔ 多观测段**，属正常聚合，非错误）。
- **②** `1:1` 515 与 `N:1` 427 并存 ⇒ **LTA 观测段 ↔ MATSim 有向边既非纯 1:1 也非纯 1:N**；`K_pooled = 1.8687`（承「多边映射必报基数 `K`」）。⚠️ 覆盖率陷阱仍在：1,931/693,575 = **0.28%** ⇒ ⛔ **不得外推全网**。
- **③** `K_pooled = 8.44` 且 **`N:M = 108`** ⇒ 一个观测段附近平均 **8 个** loop；但**仅 19.72% 的观测段**在 50 m 内存在 loop。

---

## §3. 逐判据贡献与阈值敏感度（★披露，不为好看而调参）

**逐判据通过数**（轴向·生效轴）：

```text
距离 d≤25            : 1,214
  ∧ 方向 ang≤30      : 1,214   ← 轴向后不再是卡点
  ∧ 合法 RD_CD       : 1,207
  ∧ MATCH_SCORE≥0.70 : 1,044   ← 第二卡点
  ∧ MATSim 集非空    : 1,104
  ∧ 唯一性(rdcd)     : 1,086
  ⇒ Tier A           :   795
```

**阈值敏感度**（`TierA / TierX`）：

| 配置 | TierA | TierX | 说明 |
|---|---|---|---|
| **基线（轴向 + uniq_rdcd）** | **795** | **64** | §0 生效 |
| 预注册原文（有向 + tie） | 25 | 537 | **判据退化，见 §0** |
| 轴向 + tie | 19 | 64 | 唯一性轴是卡点 |
| `rsl_max=50` | 818 | 26 | 稳健 |
| `ang=45` | 802 | 55 | 稳健 |
| `rsl50 ∧ ang45` | 805 | 17 | 稳健 |
| `gap=0`（tie） | 709 | 64 | — |
| `gap=25`（tie） | 8 | 64 | — |
| `score≥0.50` | 920 | 64 | 稳健 |
| `msim_max=50` | 909 | 64 | 稳健 |

**最近距诊断**：`d_near` **p50 = 6.39 m** · p90 = 16.44 m · `≤25 m` **1,234** · `≤50 m` **1,271** · `≤100 m` **1,277** · `≤200 m` **1,278**。
⇒ **几何上是「几乎全覆盖」，TierX 64 节是真·远离 RSL 的少数派**（其余为 SLIP_ROAD / 服务道路）。

---

## §4. 观测尺度指标（用户 §13）

| Tier | n | `TF_LENGTH` 中位 | `N_MATSIM` 中位 | `MATSIM_LENGTH` 中位 | `LOOP_DISTANCE` 中位 |
|---|---|---|---|---|---|
| A | 795 | 121.77 m | 1.0 | 72.74 m | 139.95 m |
| B | 67 | 135.50 m | 1.0 | 54.41 m | **13.85 m** |
| C | 352 | 140.36 m | 1.0 | 43.55 m | 248.95 m |
| X | 64 | 136.32 m | 1.5 | 50.13 m | 346.92 m |
| **全域** | **1,278** | **128.20 m** | **1.0** | **66.66 m** | — |

**★结论**：`TF_LENGTH(128 m) / MATSIM_LENGTH(67 m)` 之比 ≈ **1.9×**，`N_MATSIM` 中位 **1** ⇒ **LTA 观测尺度 ≈ 2× MATSim 边尺度**，**不是一对一 link matching**。
**`DetectorLoop` 空间分档**（`LOOP_NEAR 174 · ASSOCIATED 78 · WEAK 163 · UNRESOLVED 863`）⇒ 仅 **19.7%** 的观测段处于 loop 50 m 邻域内。

---

## §5. 锚点审计（★回答「`F_LOW` 那批异常对应哪个现实观测对象」）

### 5.1 `F_LOW 9`（`Σobs = 20,141 veh/h`）

| LinkID | `RoadName` | RoadCat | `RD_CD` | Tier | `d_rsl` | `score` | `N_MATSIM` | `LOOP_DISTANCE` | `R_median` | `R_sum` |
|---|---|---|---|---|---|---|---|---|---|---|
| 48461 | AYER RAJAH EXPRESSWAY | CATA | **AYE00N** | C | 9.745 | 0.8050 | 0 | 331.13 | **0.0** | **0.0** |
| 49054 | AYER RAJAH EXPRESSWAY | CATA | **AYE00N** | **A** | 8.384 | 0.8246 | 1 | 419.70 | **0.0** | **0.0** |
| 49104 | AYER RAJAH EXPRESSWAY | CATA | **AHI00U** | C | 0.000 | 0.7228 | 1 | 336.35 | **0.0** | **0.0** |
| 48586 | AYER RAJAH EXPRESSWAY | CATA | **AYE00N** | C | 7.115 | 0.8568 | 2 | 560.37 | **0.0** | **0.0** |
| 48708 | AYER RAJAH EXPRESSWAY | CATA | **AYE00N** | C | 2.684 | 0.9207 | 1 | 397.01 | **0.0** | **0.0** |
| 48337 | AYER RAJAH EXPRESSWAY | CATA | **AYE00N** | C | 6.804 | 0.8634 | 1 | 527.80 | **0.0** | **0.0** |
| 47163 | AYER RAJAH EXPRESSWAY | SLIP_ROAD | **AHI00U** | **A** | 0.000 | 0.9872 | 1 | 481.73 | **0.0** | **0.0** |
| 49027 | AYER RAJAH EXPRESSWAY | SLIP_ROAD | **AHI00U** | C | 8.461 | 0.7703 | 2 | 328.34 | **0.0** | **0.0** |
| 172382 | EAST COAST PARK SERVICE ROAD | SLIP_ROAD | — | **X** | — | — | 14 | 644.34 | **0.0** | **0.0** |

**★★结论（本步最重要的一条）**：
> **`F_LOW 9` 中 8/9 节落在同一条走廊 —— `AYER RAJAH EXPRESSWAY`（AYE，亚逸拉惹高速公路）**，其 `RD_CD` 为 **`AYE00N`（5 节）** 与 **`AHI00U`（3 节）**（后者为 AYE 的 **SLIP_ROAD** 匝道段）；余下 1 节为 `EAST COAST PARK SERVICE ROAD`（服务道路，无 RSL 匹配）。
> ⇒ 那 `20,141 veh/h` 的「异常」**不是全岛弥散的统计效应，而是集中在单一高速走廊上的 8 个具体观测段**。

**同时实测**：`F_LOW 9` 的 `LOOP_DISTANCE` 全部为 **328–644 m**（全部 `LOOP_UNRESOLVED`，仅 `129352` 为 `LOOP_WEAK 69.9 m`）⇒ **这些观测段在空间上远离 loop detector**。
⛔ **不得**据此断言「它们不是 loop 观测」—— 只能说「**观测段与 loop 设施在空间上是分离的**」，这是一个**观测设施可见性指标**。

### 5.2 `B_SET 3`（`B = BINDING_UNDECIDABLE`）

`48461 → C / AYE00N`、`49054 → A / AYE00N`、`47189 → A / PAE02K`。⇒ 3 节**观测域已重建**，但 **`B` 状态保持 `UNCHANGED`**（其升级条件 `M1a ∧ M1b ∧ M2` 本步**未满足**；⛔ **不得**据本步结论升级 `B`）。

### 5.3 `F_ADQ 5`

`45956 → A/PAE02K` · `47189 → A/PAE02K` · `45927 → A/PAE02K` · `48983 → C/AHI00U` · `129352 → C/PAE02K`（唯一 `LOOP_WEAK`）。

---

## §6. ★576 靶场：`Σ` 与 `median` 口径差（用户 §11 的直接产出）

| 量 | `median`（**canonical，未被覆盖**） | `Σ`（本步**诊断口径**） |
|---|---|---|
| `R` 中位数 | **0.959004** | **3.462132** |
| `R < 1` 的节数 | **294** | **139** |

**★关键数**：**`n(R_sum ≥ 1 ∧ R_median < 1) = 155`** ⇒ **155/576（26.9%）节的残差符号在两种聚合口径下相反**。

**判读**：
> canonical 用 `median(匹配有向边 HRS8-9avg) × SCALE`，而匹配边 `P50 = 0` ⇒ **结构性偏保守**（承 7.9F-1 定案）；改用 `Σ` 后中位残差从 **0.96 → 3.46**。
> ⇒ **「`Sim/Obs` 系统性偏低」在相当程度上是聚合口径（median vs Σ）的产物，而非单纯需求不足。**

⛔ **`median` canonical 一字未改、未被覆盖**（`G-O3R1-11`）：`section_scale_v10/A1`、`corridor_scale_v10/A1` 四件产物运行前后 `mtime` **未变**。
⛔ 本条仅为**诊断披露**；⛔ **不得**据此替换 canonical；⛔ `F_LOW` **仍不是「需求不足」**。

---

## §7. 硬门（**14/14 PASS**）

| 门 | 内容 | 实测 |
|---|---|---|
| `G-O3R1-1` | 输入解析（8 个逻辑输入声明/回退/命中） | 全 `OK` |
| `G-O3R1-2` | 新 RSL 身份 | `n=15,354` · `fields=11` · `RD_CD=1.0000` · `distinct=3,825` |
| `G-O3R1-3` | `DetectorLoop` 仍未恢复（**显式记录，不静默跳过**） | `n=16,275` · `fields=1` · `has_rdcd=False` |
| `G-O3R1-4` | 官方 schema 自证可复现 | RSL `(11,1,12)` · DET `(12,0,12)` |
| `G-O3R1-5` | 坐标同源（EPSG:3414） | RSL bbox / DET bbox 相交 ∧ SECG x∈(1e3,6e4) |
| `G-O3R1-6` | `RD_CD` 占位码已识别 | `NONAME=355` · `len5=3` |
| `G-O3R1-7` | 逐跳统计完备且**命中非零** | `h1/h2/h3 = 1,214/1,104/252` |
| `G-O3R1-8` | Tier 互斥完备（合计 = 1,278） | `795+67+352+64 = 1,278` |
| `G-O3R1-9` | **AST 自检**（零仿真可证） | `banned_hits = []` |
| `G-O3R1-10` | v1.0 未被触碰 | `changed = []` |
| `G-O3R1-11` | **canonical 未被覆盖** | 4 件 `changed = []` |
| `G-O3R1-12` | 收口一致（verdict 与 summary 一致；门禁回填） | `14/14` · 负例全 `fired∧hit` |
| `G-O3R1-13` | **§0 方向轴更正**可复现（两轴完备且互异） | 有向 `A25/X537` vs 轴向 `A795/X64` |
| `G-O3R1-14` | **§0.2 唯一性轴更正**可复现（两轴完备且互异） | `rdcd A795` vs `tie A19` |

---

## §8. 负例（**6/6 `fired ∧ hit`**；全部与主路径共用同一 `compute(p)`）

| 负例 | 扰动（锚点 = 生效轴 ⊕ 该锚点） | 设计可观测量 | 实测 |
|---|---|---|---|
| `N1` | `rsl_max 25 → 5` | `①n_matched_left` | `1,214 → 405` ↓ |
| `N2` | `rsl_max 25 → 200` | `①n_matched_left` | `1,214 → 1,270` ↑ |
| `N3` | `PLACEHOLDER` 置空（把 `NONAME` 当合法码） | `n_placeholder` / `TierA` | `90 → 0`；`TierA 795 → 799` |
| `N4` | 向 `DetectorLoop` 注入伪 `RD_CD` | `det_has_rdcd` | `False → True` |
| `N5` | `msim_max 25 → 1` | `②n_matched_left` | `1,104 → 27` ↓；`TierA 795→23` |
| `N6` | 关闭 `DetectorLoop` 输入 | `Tier B` | `67 → 0`（全部转 C） |

⇒ `Tier A/B/C/X` 与 `ABSENT`-类结论**是数据状态的结论，不是判据失效的伪影**。

---

## §9. 可复现性

```bash
C:/Users/LQP/miniconda3/python.exe scripts/od/audit_o3_r1_odrecon.py
```

**15 项产物两次连跑 SHA256 逐位一致**（首 `70ccc44aa279430d` … 末 `dce84f974a4dc533`）。
`G-O3R1-9` AST 自检无 `subprocess`/`os.system`/`popen`/`java` ⇒ **零仿真可证**。
★ 计时量已移出 `summary.json`（确保逐位可复现）。

---

## §10. 缺陷登记

| 编号 | 项 | 内容 |
|---|---|---|
| **`R1`** | **判据规范缺陷（方向轴）** | 见 §0 —— `RoadSectionLine` 无方向语义，有向判据把反向绘制误判为不匹配（730/1,234）。已更正为轴向；**新增 `G-O3R1-13`**。属**判据缺陷，非科学结论** |
| **`R2`** | **判据规范缺陷（唯一性轴）** | 见 §0.2 —— 「唯一」误实现为并列测试（10 m），把同一道路相邻分段判为歧义。已细化为 `RD_CD` 去重 = 1；**新增 `G-O3R1-14`**；`tie` 轴并报 |
| **`R3`** | **负例空扰动** | `N3` 首版完全静默：`n_placeholder` 误用模块常量而非生效的 `ph`，且 `sig` 未纳入该观测量 ⇒ 改为随 `ph` 变化 + `sig` 纳入 `nph`。**判据/阈值/门定义未改** |
| **`R4`** | **产物非确定性** | `summary.json` 含 `elapsed_s` ⇒ 两次跑哈希不同；已移出（计时仅入日志） |
| **`D1`** | 靶场集计数不一致 | `section_geography.csv` **574** vs `crosswalk` distinct **576** ⇒ 本步以 `crosswalk` 为准并显式报基数；⛔ 不擅自补 2 节 |
| **`D2`** | `RD_NAM` 不可得 | 官方并集有、交付无 ⇒ `match_score` **结构性缺失路名项**（⛔ 不以任何代理替代） |

---

## §11. 判读纪律 / 边界 / 下一步

### 11.1 判读纪律（硬约束）

1. ⛔ **Tier B 只读「设施空间邻近」**，**绝不读作「`Detector ID` 已恢复」**。
2. ⛔ **不得**因 RSL `RD_CD` 100% 就宣布「观测对象已是检测器级」—— 本步只到**道路段级**。
3. ⛔ **不得**说「`DetectorLoop` 已与 `TrafficFlow` 完全绑定」；只能说「**观测空间域独立于 `Detector ID` 重建；`DetectorLoop` 仅辅助验证设施空间关联**」。
4. ⛔ `NONAME` / 5 字符 `RD_CD` **不得**当作合法道路码。
5. ⛔ **`B = BINDING_UNDECIDABLE` 保持**；本步结论**不得**用于升级 `B`。
6. ⛔ **`median` canonical 不得被 `Σ` 替换**；双口径并报且标注 `Σ` 为诊断口径。
7. **本步不产生** `F_LOW` 成因的新结论；`F_LOW` **仍不是「需求不足」**。
8. **边界全部保持冻结**：v1.0 · crosswalk · `TrafficFlow` 原始值 · 评价器阈值 · `signals`/`trafficDynamics`/`speedFactor`。

### 11.2 本步结论（正式）

> **检测器业务身份不可由公开数据恢复，但交通观测空间域可通过 `TrafficFlow Link` 与 `RoadSectionLine` 的几何对应关系重建。**
> —— `FACILITY_IDENTITY_UNAVAILABLE_BUT_OBSERVATION_DOMAIN_RECOVERABLE`

**方法学答辩口径（用户 §16 要求）**：**本研究不依赖 detector-level identity，而是以 LTA `TrafficFlow` Link 作为观测单元，通过其与 `RoadSectionLine` 的空间对应关系建立道路观测域；`DetectorLoop` 仅作为独立的设施空间证据，不将公开数据中无法获得的 `Detector ID` 作为必要关联键。**

### 11.3 下一步（⛔ 本节点不擅自启动）

1. **可选**：把本步 Tier A 观测域（795 节）与 576 靶场残差联结，做**观测尺度 × 残差**诊断（`Σ`/`median` 双口径）。
2. ⛔ **仍不**修改 MATSim 路网/动力学；⛔ 观测尺度 / 路网对象 / 交通动力学三者主因的讨论**须待用户裁定后**方可开启（顺序不得倒置）。
3. ⛔ **不再**下载新月份 `DetectorLoop`（双月实测一致，已定位为公开导出剥离，非月份问题）。

---

**关联文件**
- 预注册：`reports/corridor_scale_audit_7_9i/PREREG_7_9I_O3R1.md`（含 §11 运行后正式更正）
- 引擎：`scripts/od/audit_o3_r1_odrecon.py`
- 探路（保留，与既有 `_recon_7_9f0/f1_inputs.py` 同例）：`scripts/od/_recon_7_9io3r1_inputs.py` · `scripts/od/_recon_7_9io3r1_net.py` · 运行日志 `reports/corridor_scale_audit_7_9i/_run_7_9io3r1.log` · 输入落盘 `recovery_7_9io3r/{RoadSectionLine,DetectorLoop}/`
- **★文档同步（已完成，2026-10-01）**：`CLOSURE_7_9I.md` **§16**（16.1–16.11）· `docs/readme_technical_v1.md` **§2.75** + §7 变更记录行 · `scripts/od/readme.md` §6.2 / §6.3 / §7.2 / §7.3 · 当日日志 **§29** · `MEMORY.md` §3 新行 + §5 阶段链/`★当前` + 头部 `最后更新`
- 产物（15）：`o3r1_tier_cards.csv` · `o3r1_tf_to_rsl.csv` · `o3r1_tf_to_matsim.csv` · `o3r1_loop_proximity.csv` · `o3r1_obs_scale.csv` · `o3r1_anchor_audit.csv` · `o3r1_hop_stats.csv` · `o3r1_threshold_sensitivity.csv` · `o3r1_checks.csv` · `o3r1_input_resolution.json` · `o3r1_rsl_identity.json` · `o3r1_summary.json` · `o3r1_closure.csv` · `o3r1_manifest.json` · `o3r1_obs_scale.json`
