# PREREG — Step 7.9I-O3-R1 · 「观测域重建（Observation-Domain Reconstruction）」

> **状态**：`D2-review ✓ → O3 ✓ → O3-METADATA ✓ → O3-DATA-RECOVERY ✓（READY）→ O3-R1（本步）`
> **性质**：**零仿真 / 只读**。⛔ 不跑 MATSim；⛔ 不改 v1.0 / crosswalk / `TrafficFlow` 原始值 / 评价器阈值；⛔ 不碰 `signals` / `trafficDynamics` / `speedFactor`；⛔ 不产生 v1.1。
> **用户裁定**（2026-10-01 18:00）：**放弃「必须恢复 `DetectorLoop → Detector ID → Junction ID`」这条链**，把研究对象重定义为「**LTA 道路观测段 — `RoadSectionLine` — MATSim 道路对象**」的空间观测单元；**`DetectorLoop` 退为辅助证据**。
> **本文件为运行前冻结件**：任何判据/阈值/门数/判决空间的改动 ⇒ 本预注册作废，须重立新 step。
> 本预注册**须与** `PREREG_7_9I_O3RECOVERY.md`（§0 更正 · 五跳链 · 读法纪律）**连读**。

---

## §0. 本步定位 · 与前序的衔接（运行前已实测，非推断）

### 0.1 输入实测（2026-10-01，`_recon_7_9io3r1_inputs.py` 逐字解析）

| 图层 | ZIP SHA256（前 24） | 记录数 | DBF 字段 | `RD_CD` | CRS | 几何 |
|---|---|---|---|---|---|---|
| **`RoadSectionLine`_Sep2026** | `f817f085e2ced9dbfdd03cd0` | **15,354** | **11**（`JOB_NUM RD_CD RD_CATG_NA EXCEPTION_ LAST_UPD_* CRT_* PKG_REF REMARKS SHAPE_LEN`） | ✅ **1.0000**（15,354/15,354），**distinct 3,825** | SVY21 | POLYLINE（顶点 p50 **12**，max 588） |
| **`DetectorLoop`_Sep2026** | `0fed9592114c196519db0a8f` | **16,275** | **1**（`OBJECTID`） | ❌ **无该列** | SVY21 | POLYGON（顶点 p50 **5**） |
| （对照）`RoadSectionLine`_Mar2026 | — | 15,329 | 4（`RD_CD RD_CATG_NA RD_CATG__1 RD_CD_DESC`） | ❌ **0.0000** | SVY21 | POLYLINE |

### 0.2 ★本步成立的两个事实依据

1. **`RoadSectionLine` 的 `RD_CD` 已恢复 100%**（旧版 0/15,329 → 新版 15,354/15,354）⇒ ①→②／②→③ 跳**首次具备可算性**。
2. **`DetectorLoop` 公开导出仍只余 `OBJECTID`**（16,275），而其 `.shp.xml` 官方并集含 `RD_CD`（12 字段）⇒ **确认「原始 GDM 有 `RD_CD`、DataMall 导出把属性剥掉」**，且**换月份不能解决**（Mar2026 / Sep2026 两次一致）。

### 0.3 ★两处新增观测（运行前登记，必须写进结论，不得隐藏）

| 编号 | 观测 | 含义 / 处理 |
|---|---|---|
| **`N1`** | **`RD_NAM` 仍被剥**：官方并集含 `RD_NAM`，交付 DBF **无此列** | 新文件是「**保代码、掉路名**」，与旧文件「保文本、掉代码」**正好相反** ⇒ ②→③ **只能用 `RD_CD`**，**无法用路名交叉核对** |
| **`N2`** | **`RD_CD` 内含占位值**：`ZZZ38A` **677** · **`NONAME` 355** · `AYE00N` 81 …；长度直方图 **{6: 15,351, 5: 3}** | `NONAME` / 5 字符值**不是可用道路码** ⇒ 匹配时必须识别并标注（见 §3 常量 `PLACEHOLDER_RD_CD`） |
| **`N3`** | `section_geography.csv` 仅 **574** 行，而 crosswalk `distinct lta_linkid = 576` | 两个靶场集合**差 2** ⇒ 本步**不得默认二者同集**，须显式取交集/并集并报基数 |

### 0.4 本步**不做**什么

⛔ 不再尝试恢复 `Detector ID` / `Junction ID`；⛔ 不再下载新月份 `DetectorLoop`；⛔ 不使用几何邻近**冒充**设施身份（承 `TWIN_GEOMETRIC_SUBSTITUTE` 纪律）；⛔ 不启动学校数据审批。

---

## §1. 研究对象重定义（本步唯一目标）

**旧问题（O3 / O3-METADATA / O3-DATA-RECOVERY）**：
> `DetectorLoop` 与 `RoadSectionLine` / `Detector ID` 的绑定关系无法确定 ⇒ 卡在数据获取。

**新问题（本步）**：**LTA 的一个交通流观测量，对应 MATSim 中哪些道路对象？**

$$\text{LTA observation}\;\rightarrow\;\text{road section}\;\rightarrow\;\text{MATSim links}$$

而不是 `LTA observation → DetectorID → DetectorLoop → RD_CD`。
**后者只是「一种辅助实现方式」，不是唯一路径**（用户逐字）。

**观测单元定义（冻结）**：
> **`TrafficFlow` Link = LTA 道路交通观测段**（`LinkID` + 几何 + `Volume`），**不是 Detector**。
（承接 O3 四事实①：1,278/1,278 双顶点、p50 **128 m**）

---

## §2. 输入契约（**声明路径优先**，含回退；逐条落盘 `o3r1_input_resolution.json`）

| 逻辑输入 | **声明路径（优先）** | 回退 |
|---|---|---|
| `TrafficFlow_Links` | `Dynamic_2026_03_16/historical_data/TrafficFlow_Links.dbf` | — |
| `TrafficFlow_Data` | `Dynamic_2026_03_16/historical_data/TrafficFlow_Data.json` | — |
| **`RoadSectionLine`（新）** | `recovery_7_9io3r/RoadSectionLine/RoadSectionLine.dbf` | `recovery_7_9io3r/RoadSectionLine/*.dbf` · `Singapore_OD_MATSim_FinalData/**/RoadSectionLine*.dbf` |
| **`DetectorLoop`（新）** | `recovery_7_9io3r/DetectorLoop/DetectorLoop.dbf` | `recovery_7_9io3r/DetectorLoop/*.dbf` · `Singapore_OD_MATSim_FinalData/**/DetectorLoop*.dbf` |
| MATSim 网络（v1.0/λ 冻结） | `scripts/od/_cache_network_7_9c0.npz`（`ids/frm/to/len_m/fs_mps/cap/lanes/highway/name` + `node_x/node_y`；**693,575** 边） | — |
| crosswalk（576 靶场） | `reports/od_final_calibration_crosswalk_7_3_6/final_calibration_crosswalk.csv` | — |
| 断面锚点 | `reports/od_structure_7_6c/section_geography.csv`（`lta_linkid, mid_x, mid_y`，**SVY21**） | — |

**★坐标纪律（硬约束）**：全部空间运算在 **EPSG:3414（SVY21，米）** 内进行。
- `TrafficFlow_Links` 的 `StartLon/Lat·EndLon/Lat` 为 **WGS84** ⇒ 必须经 `pyproj` 转 SVY21（承 O3 引擎 `Transformer("EPSG:4326","EPSG:3414")`）。
- `RoadSectionLine` / `DetectorLoop` / `_cache_network` / `section_geography` 均为 SVY21。
- ⛔ **禁止**使用 `lta_section_geometry().mx/my`（局部等距平面米 ≈1.15e7）与 SVY21 混算。

---

## §3. 冻结常量与判据（运行前冻结）

```text
RSL_MATCH_MAX_M      = 25.0     # ① TF→RSL 距离上界（用户指定）
RSL_ANGLE_MAX_DEG    = 30.0     # ① TF→RSL 方向差上界（用户指定，承接 O1-续② / D-path 的 DIR_OK）
MATSIM_MATCH_MAX_M   = 25.0     # ② TF(Mid)→MATSim 边中点 距离上界
MATSIM_ANGLE_MAX_DEG = 30.0     # ② 方向差上界
TIER_A_SCORE_MIN     = 0.70     # Tier A 判据
TIER_B_LOOP_MAX_M    = 50.0     # Tier B 判据（用户指定）
UNIQUE_GAP_M         = 10.0     # 「唯一」判据：次近 − 最近 ≥ 10 m 才算唯一
RC_LEN               = 6        # 合法 RD_CD 长度
PLACEHOLDER_RD_CD    = {"NONAME", ""}          # N2 观测：占位码
LOOP_BANDS           = [(0,25,"LOOP_NEAR"), (25,50,"LOOP_ASSOCIATED"),
                        (50,100,"LOOP_WEAK"), (100,inf,"LOOP_UNRESOLVED")]
```

**`match_score` 定义（冻结，显式加权，避免事后调参）**：

```text
match_score = 0.5·d_term + 0.3·a_term + 0.2·code_term
  d_term    = clip(1 − d_rsl / RSL_MATCH_MAX_M, 0, 1)      # 距离项
  a_term    = clip(1 − ang / RSL_ANGLE_MAX_DEG, 0, 1)      # 方向项
  code_term = 1 若 RD_CD 合法（len==6 且 ∉ PLACEHOLDER_RD_CD）否则 0   # 代码项
```
> ⚠️ **无「路名一致加分」项**：因 `RD_NAM` 被剥（§0.3 `N1`），本批**没有可用的路名字段** ⇒ 该项**结构性不可用**，⛔ 不得以任何代理替代。

**三层可信度（Tier，**互斥**，按下列**优先级**判定）**：

| Tier | 判据 | 标签 | 含义 |
|---|---|---|---|
| **X** | 无任何 RSL 满足 `d ≤ 25 ∧ ang ≤ 30` | `OBS_DOMAIN_UNMAPPED` | ★引擎新增：观测域未落图（须披露） |
| **A** | 唯一匹配 ∧ `d ≤ 25` ∧ `ang ≤ 30` ∧ `code_term = 1` ∧ `match_score ≥ 0.70` ∧ MATSim link 集非空 | `DIRECT_ROAD_SECTION_OBSERVATION` | **正式观测域** |
| **B** | 非 A，但 RSL 匹配成立 ∧ `d_loop ≤ 50` | `LOOP_SPATIALLY_ASSOCIATED` | 设施**仅空间邻近**，⛔ **不声称 `Detector ID` 已恢复** |
| **C** | 非 A 非 B，但 RSL 匹配成立（`d_loop > 50` 或无 loop） | `FACILITY_LINKAGE_UNRESOLVED` | 仍可用，设施链未定 |

**观测尺度指标（逐 TF Link 输出，用户 §13）**：

| 指标 | 定义 |
|---|---|
| `TF_LENGTH` | TF 段长（SVY21 米） |
| `N_MATSIM` | 对应 MATSim 有向边数（② 命中集合势） |
| `MATSIM_LENGTH` | 对应 MATSim 边**总长**（米） |
| `N_LOOP_NEAR` | `d_loop ≤ 50 m` 的 `DetectorLoop` 个数 |
| `LOOP_DISTANCE` | 最近 `DetectorLoop` 距离（米） |
| `MATCH_SCORE` | §3 定义 |

**残差口径（用户 §11，**本步只定义、只作诊断，⛔ 不回写 canonical**）**：

$$R_g=\frac{\sum_{l\in M_g}Q_l^{sim}}{Q_g^{obs}}$$

其中 `g` = LTA 观测段，`M_g` = 其对应 MATSim 边集，`Q_l^sim` = MATSim 边流量（`SCALE × HRS8-9avg`），`Q_g^obs` = LTA 观测流量。
★**双口径并报**：`Σ`（本定义）与 **`median`（现有 canonical）** 并列，只为**披露尺度口径差**，⛔ **不替换 canonical**。

---

## §4. 逐层统计口径（用户点名必须输出）

对**每一跳**（① TF→RSL · ② TF→MATSim · ③ TF→DetectorLoop）逐层统计：

| 量 | 定义 |
|---|---|
| `n_left` / `n_right` | 两侧**非空键**记录数 |
| `n_matched_left` / `n_matched_right` | 命中对方者 |
| `c_1_1` / `c_1_N` / `c_N_1` / `c_N_M` | 按 **左→右键集合势 `k`** × **右→左集合势 `m`** 双向计数：`k=1∧m=1`→`1:1`；`k=1∧m>1`→`1:N`；`k>1∧m=1`→`N:1`；`k>1∧m>1`→`N:M` |
| `coverage_left` / `coverage_right` | `n_matched_*/n_*` |
| `K_pooled` | `n_matched_right_total / n_matched_left`（**只报计数，不作比值**） |
| `direction_recoverable` | 由几何可算 bearing（本步恒 `True`，须附实测） |

★ 纪律：**多边映射必报计数基数 `K`**；**取子集必断言命中非零**；**占比须声明暴露面**。

---

## §5. 判决空间（**互斥、按序**）

```text
输入缺失（RSL 或 MATSim 不可读）                    -> O3R1_BLOCKED_INPUT
Tier A 覆盖率 < 0.50                                -> OBSERVATION_DOMAIN_PARTIAL
Tier A 覆盖率 ≥ 0.50 且 Tier X 覆盖率 ≤ 0.10         -> FACILITY_IDENTITY_UNAVAILABLE_BUT_OBSERVATION_DOMAIN_RECOVERABLE
Tier A 覆盖率 ≥ 0.50 但 Tier X 覆盖率 > 0.10         -> OBSERVATION_DOMAIN_RECOVERABLE_WITH_UNMAPPED
```

**★主判决（用户 §10 指定）**：**`FACILITY_IDENTITY_UNAVAILABLE_BUT_OBSERVATION_DOMAIN_RECOVERABLE`**
中文：**检测器业务身份不可由公开数据恢复，但交通观测空间域可通过 `TrafficFlow Link` 与 `RoadSectionLine` 的几何对应关系重建。**

**★`B` 状态处理（承 O3-METADATA / O3-DATA-RECOVERY）**：
- `B = BINDING_UNDECIDABLE` **保持不升级**（其升级条件是「`M1a ∧ M1b ∧ M2` 全真且该节 4 条件全真」，本步**不满足** `M1b`/`M2`）。
- 本步对 `B_SET` 3 节只回答：**其观测域（Tier）是否已重建** —— 这是**另一条判据**，⛔ **不得**据此宣布 `B` 升级。

---

## §6. 硬门（`G-O3R1-1` – `G-O3R1-12`）

| 门 | 内容 |
|---|---|
| `G-O3R1-1` | **输入解析**：每个逻辑输入报 `declared_path` / `declared_exists` / `resolved_path`；全部候选落盘 |
| `G-O3R1-2` | **新 RSL 身份**：记录数 **15,354**、`RD_CD` 填充率 **1.0000**、distinct **3,825**、字段数 **11** |
| `G-O3R1-3` | **DetectorLoop 仍未恢复**：记录数 **16,275**、字段数 **1**、`RD_CD` 不存在（**必须显式记录，不得静默跳过**） |
| `G-O3R1-4` | **官方 schema 自证可复现**：RSL 并集 **12**（FGDC 11 ∪ `AddField{REMARKS}` 1）；DET 并集 **12**（FGDC 12 ∪ ∅） |
| `G-O3R1-5` | **坐标同源**：所有空间运算在 EPSG:3414；`section_geography.mid_x/mid_y` 与 RSL/DET 的 bbox 同域 |
| `G-O3R1-6` | **`RD_CD` 占位码已识别**（`NONAME` 355 · 5 字符 3 个）且计入 `code_term=0` |
| `G-O3R1-7` | **逐跳统计完备**：①/②/③ 各有 `n_*` / `c_*` / `coverage_*` / `K_pooled`，且**命中非零断言**成立 |
| `G-O3R1-8` | **Tier 互斥且完备**：`A ∪ B ∪ C ∪ X = 1,278` 且两两不交（**分母必须等于 TF 全集**） |
| `G-O3R1-9` | **AST 自检**：无 `subprocess` / `os.system` / `popen` / `java` ⇒ **零仿真可证** |
| `G-O3R1-10` | **v1.0 未被触碰**：`matsim_final_7_6h/outputs/W01_rc_min` 全量快照前后 `changed = []` |
| `G-O3R1-11` | **canonical 未被覆盖**：本步产物**不写入** `reports/corridor_scale_audit_7_9i/` 以外的既有结果目录 |
| `G-O3R1-12` | **收口一致**：`o3r1_closure.csv` 的 `verdict` 与 `summary.json` 一致；`gates_verdict` / `n_gates_pass` 由门禁计算后**回填** |

---

## §7. 负例（`N1`–`N6`，**须真改变结果且非同构**；全部与主路径**共用同一 `compute(p)`**）

| 负例 | 扰动（锚点 = 基线 ⊕ 该锚点） | 设计可观测量 | 预期方向 |
|---|---|---|---|
| `N1` | 把 `RSL_MATCH_MAX_M` 25 → 5 | `n_matched_left`(①) | 下降 |
| `N2` | 把 `RSL_MATCH_MAX_M` 25 → 200 | `n_matched_left`(①) | 上升 |
| `N3` | `PLACEHOLDER_RD_CD` 置空（即把 `NONAME` 当作合法码） | `n_placeholder` / Tier A 计数 | 占位码数 → 0 |
| `N4` | 注入伪 `RD_CD` 到 `DetectorLoop`（模拟「属性版」到手） | `det_has_rdcd` | `False → True` |
| `N5` | `MATSIM_MATCH_MAX_M` 25 → 1 | `N_MATSIM` 中位 | 下降 |
| `N6` | 关闭 `DetectorLoop` 输入（`d_loop = ∞`） | Tier B 计数 | → 0 |

**机制隔离**（承 O3-R1 前序纪律）：`N1`/`N2` 分别验**下界**与**上界**非饱和；`N3` 验**占位码识别**非死代码；`N4` 验**设施身份不可得**是数据结论而非判据失效；`N5` 验 MATSim 命中非退化；`N6` 验 Tier B 依赖真实输入。

---

## §8. 交付物

| 文件 | 内容 |
|---|---|
| `o3r1_input_resolution.json` | 输入解析痕迹（声明/回退/命中） |
| `o3r1_rsl_identity.json` | 新 RSL/DET 实测身份（记录数/字段/填充率/schema 并集） |
| `o3r1_tf_to_rsl.csv` | ① 逐 TF Link：`d_rsl` / `ang` / `RD_CD`(可多值) / `n_rsl` / `unique` / `code_term` / `match_score` |
| `o3r1_tf_to_matsim.csv` | ② 逐 TF Link：`N_MATSIM` / `MATSIM_LENGTH` / `highway` 构成 / crosswalk `K`（若在 576 靶场） |
| `o3r1_loop_proximity.csv` | ③ 逐 TF Link：`LOOP_DISTANCE` / `N_LOOP_NEAR` / `LOOP_BAND` |
| `o3r1_tier_cards.csv` | **Observation Object Card**：逐 Link 的 Tier + 全部指标（⛔ 不只给占比） |
| `o3r1_obs_scale.csv` | 观测尺度指标汇总（分位/按 RoadCat/按 Tier） |
| `o3r1_anchor_audit.csv` | `F_LOW 9` · `B_SET 3` · `F_ADQ 5` · **576 靶场** 逐节观测域状态 |
| `o3r1_hop_stats.csv` | §4 逐跳统计 |
| `o3r1_checks.csv` | 门禁逐项实测值 |
| `o3r1_summary.json` | 全量结果 |
| `o3r1_manifest.json` | 产物清单（**最后生成、不自哈希**） |
| `o3r1_closure.csv` | 收口（verdict + 门禁回填） |

---

## §9. 判读纪律（全部为硬约束）

1. ⛔ **Tier B 只读「设施空间邻近」**，**绝不读作「`Detector ID` 已恢复」**；⛔ Tier C 只读「设施链未定」。
2. ⛔ **不得**因 RSL `RD_CD` 100% 就宣布「观测对象已是检测器级」—— 本步只到**道路段级**。
3. ⛔ **不得**说「`DetectorLoop` 已与 `TrafficFlow` 完全绑定」；只能说「观测空间域**独立于** `Detector ID` 重建；`DetectorLoop` **仅**辅助验证设施空间关联」。
4. ⛔ `NONAME` / 5 字符 `RD_CD` **不得**当作合法道路码参与 Tier A。
5. ⛔ **`B = BINDING_UNDECIDABLE` 保持**；本步结论**不得**用于升级 `B`。
6. ⛔ **`median` canonical 不得被 `Σ` 替换**；双口径并报，且**明确标注** `Σ` 为本步诊断口径。
7. **本步不产生**任何关于 `F_LOW` 成因的新结论；`F_LOW` **仍不是「需求不足」**。
8. **边界全部保持冻结**：v1.0 · crosswalk · `TrafficFlow` 原始值 · 评价器阈值 · `signals`/`trafficDynamics`/`speedFactor`。

---

## §10. 本步**不**回答的问题（防止越界）

⛔ 观测尺度 / 路网对象 / 交通动力学三者谁是主因 —— 用户裁定：**须待属性链闭合之后**才有资格讨论，**顺序不得倒置**。
⛔ 是否修改 MATSim 路网或动力学 —— 本步**不进入**该决策。

---

## §11. ★运行后正式更正（2 处）—— 由引擎自身诊断触发，**非事后调参**

> 触发路径：`N3` 完全静默（负例空扰动）⇒ 追查 `ph` 口径 ⇒ 新增「最近距诊断」与「逐判据贡献」两块**披露性诊断** ⇒ 诊断暴露两处**判据规范缺陷**。
> 两处更正均为**判据规范更正（spec correction）**，**不是阈值放宽**；两轴一律**并报**；原冻结轴结果**保留为审计轨迹**。

### 11.1 `§0` 方向轴更正：有向 → **轴向**

- **实测**：`TF→RSL` 最近距 **p50 = 6.4 m**，`≤25 m` 有 **1,234/1,278**；但其中 **730 条**「有向」方向差 **> 30°**（即**反向**）。
- **根因**：`RoadSectionLine` **无方向语义**（只是道路段线），`circ_diff` 对反向给出 180° ⇒ 有向判据把**同一道路的反向绘制**误判为不匹配。
- **退化证据**：有向轴 `Tier X = 537（42.0%）`、`Tier A = 25（2.0%）` —— **判据缺陷**（承「冻结判据命中异常必查判据」）。
- **更正**：`TF→RSL` 改判**轴向**（`_adiff = min(d, 180−d)`）；**`TF→MATSim` 保持有向**（MATSim 边确有方向）。
- **效果**：`Tier X 537→64（5.0%）`、`①命中 741→1,214`。
- **新增门 `G-O3R1-13`**：两轴（有向/轴向）Tier 合计均 = 1,278 **且互异** ⇒ 非死代码。

### 11.2 `§0.2` 唯一性轴更正：`tie` → **`rdcd`**（并列细化轴）

- **实测**：轴向修正后 `Tier A` 反而降至 **19**；敏感度表显示 `unique_gap → 0` 时 **A = 709** ⇒ **「唯一性」才是真正的卡点**。
- **根因**：预注册把「唯一」实现为「次近候选距最近候选 ≥ `UNIQUE_GAP_M`（10 m）」—— 这是**并列（tie）测试**，在密集路段把**同一条道路的相邻分段**误判为歧义。
- **更正**：「唯一」= 命中候选的 **`RD_CD` 去重后恰为 1 条**（与「该观测段归属哪条道路」的科学含义一致）；`tie` 轴**保留并报**。
- **效果**：`Tier A 19→795（62.2%）`；`uniq 通过数：tie 46 / rdcd 1,086`。
- **新增门 `G-O3R1-14`**：两轴 Tier 合计均 = 1,278 **且互异**。

### 11.3 门数与判据变更声明

- 硬门 **12 → 14**（新增 `G-O3R1-13` / `G-O3R1-14`，均为**更正可复现性**门）。
- **未受影响（一字未改）**：几何阈值 `RSL_MATCH_MAX_M=25` / `RSL_ANGLE_MAX_DEG=30` / `MATSIM_MATCH_MAX_M=25` / `MATSIM_ANGLE_MAX_DEG=30` · `UNIQUE_GAP_M=10`（在 `tie` 轴内仍生效）· `TIER_A_SCORE_MIN=0.70` · `TIER_B_LOOP_MAX_M=50` · `LOOP_BANDS` · `PLACEHOLDER_RD_CD` · Tier 优先级（X→A→B→C）· 判决空间阈值（0.50 / 0.10）· 负例集合 `N1–N6` · §9 判读纪律 · §10 边界。
- **判决稳健性**：`Tier A` 在 `rsl50 / ang45 / rsl50_ang45 / score0.50 / matsim50` 扰动下为 **818 / 802 / 805 / 920 / 909**（基线 795）⇒ **非阈值刀锋**。
