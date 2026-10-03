# STEP 7.9I-O3-DATA-RECOVERY — 恢复审计正式报告

> **状态机**：`D2-review ✓ → O3 ✓ → O3-METADATA ✓ → READY(O3-DATA-RECOVERY) →` **`O3_RECOVERY_AWAITING_INPUT`**
> **判决**：`status = BLOCKED` · `verdict = O3_RECOVERY_AWAITING_INPUT` · 硬门 **12/12** · 负例 **6/6** · `EXIT = 0`
> **性质**：**零仿真** · 不改模型 / 不改评价器 / 不跑 MATSim · ⛔ 不产生 v1.1
> **冻结件**：`PREREG_7_9I_O3RECOVERY.md`（运行前冻结）· `scripts/od/audit_o3_recovery_7_9io3r.py`（引擎）· `scripts/od/check_o3_recovery_inputs_7_9io3r.py`（自检）
> **日期**：2026-10-01

---

## 1. 本步唯一目标

恢复 `TrafficFlow → Detector / 道路设施` 的**可连接身份链**。

⛔ **旧链已被 O3-METADATA 正式证伪**，不得再提：

```text
DetectorLoop → DETECTOR_ID → TrafficFlow        # ⛔ 证伪
```

✅ **本步采用的纠正后五跳链**（逐跳独立判定，**不得跳级**）：

```text
① TrafficFlow LinkID ──(RoadName / RoadCat)──▶ ② RD_CD
                                                  │
                                                  ▼
                                        ③ RoadSectionLine（RD_CD / RD_NAM）
                                                  │
                                                  ▼
                                        ④ DetectorLoop（RD_CD / JOB_NUM / 几何）
                                                  │
                                                  ▼
                                  ⑤ Junction / Detector ID  ← 仅 On-Request 有
```

---

## 2. ★§0 正式自查更正（对 O3-METADATA 的一处更正）

O3-METADATA 把 `REMARKS`（`DetectorLoop` 1 处、`RoadSectionLine` 1 处）登记为**臆造**。本轮在**源库变更日志**里找到了反证。

### 2.1 方法学更正（可复用）

**官方 schema 自证源不止一种写法**：

| 写法 | 位置 | 本轮 29 图层命中 |
|---|---|---|
| **FGDC 字段映射串** | `<attr><attrlabl Sync="TRUE">NAME</attrlabl>…` 旁的 `NAME 'text' true true true N Text` | **6 / 29** |
| **`AddField` 语句** | 源库变更日志（同 `*.shp.xml` 内） | **22 / 29** |

**⇒ 权威 schema = FGDC 映射串 ∪ `AddField`**；**仅用 FGDC 正则会漏字段**。

**源库身份**（本轮新增证据）：
`Database Connections\gdm@pdn4.sde\GDM.LTALayers\GDM.<Layer>` ·
ArcSDE / Oracle `gispprod` · `User=GDM` · `Version=SDE.DEFAULT` · `en` · ArcCatalog `9.3.1.3000`

### 2.2 更正结果

| 图层 | `AddField` 记录 | 更正后判定 |
|---|---|---|
| **`RoadSectionLine`** | ✅ `AddField D:\Data\GDMPDN4.sde\GDM.LTALayers\GDM.RoadSectionLine REMARKS TEXT # # 200 Remarks NULLABLE NON_REQUIRED`（**Date=20140801**） | `REMARKS` = **真实源字段** ⇒ 从「臆造」**移出**，改入 **`SOURCE_ONLY_STRIPPED`**；官方并集 **11 → 12** |
| `DetectorLoop` | ⛔ **无 `AddField` 记录** | 维持「FGDC 未声明」，**降级**为 **`UNCONFIRMED_IN_SOURCE`** ⇒ ⛔ **不得再称「臆造」** |

**未受影响**：`DETECTOR_ID` / `LANE_NUM` **仍是文档独有** —— `DetectorLoop` 官方 = FGDC 12 ∪ `AddField` ∅ = **12**，确实**不含**此二者。

### 2.3 已同步的下游 4 处

| 文件 | 位置 |
|---|---|
| `reports/corridor_scale_audit_7_9i/CLOSURE_7_9I.md` | 新增 **§14.0**；§14.2 表按更正后口径重列 |
| `docs/readme_technical_v1.md` | §2.73 三方对账表重列；新增 **§2.74**；变更记录新增行 + O3-METADATA 行加更正标记 |
| `reports/corridor_scale_audit_7_9i/PREREG_7_9I_O3.md` | §2.1 表下新增更正块 |
| `reports/corridor_scale_audit_7_9i/PREREG_7_9I_O3METADATA.md` | `G-M1` / `G-M4` 口径修正；新增 **§3.3 更正**；判读纪律第 4 条改写 |

---

## 3. 运行前否定性先验（P1 / P2 / P3，必须写进结论）

| # | 事实（实测） | 结论 |
|---|---|---|
| **P1** | `RD_CD` 在**三个独立图层**近全空：`RoadSectionLine` **0/15,329** · `CyclingPath` **0/4,830** · `LampPost` **61/126,916 = 0.048%** | 「保文本（`RD_CD_DESC` 100%）/ 清代码（`RD_CD` ≈0%）」是**跨图层重复出现的模式** ⇒ 可能**不是交付剥离，而是源库本身未赋值** |
| **P2** | `LampPost` 61 条非空 `RD_CD` **全部 6 字符**，去重后仅 **6 个** | 与官方 `RD_CD (Road Code, 6)` 声明**吻合** ⇒ **`RD_CD` 确实存在于源数据**；但取值形如**内部占位/临时码** ⇒ **很可能不是可用的道路码体系** |
| **P3** | 剥空**逐图层差异化、非统一**：29 层 = **A 完全剥空 14**（含 `DetectorLoop`）· **B 保文本清代码 3**（`RoadSectionLine` / `LampPost` / `CyclingPath`）· **C 字段完整 12**（含真 ID 如 `BUS_STOP_N` / `GNTRY_NUM` / `STN_NAM`） | 存在**可获取的完整版图层**；但**不保证** `DetectorLoop` / `RoadSectionLine` 在完整版中 `RD_CD` 有值 |

**`LampPost` 的 6 个去重值（逐字）**

| 值 | 出现次数 |
|---|---:|
| `ZZ190A` | 46 |
| `ZZ202A` | 11 |
| `ZZ161A` | 7 |
| `ZZZ43A` | 4 |
| `ZZ203A` | 3 |
| `PUP06M` | 4 |
| **合计** | **61 / 126,916 = 0.048%** |

**⇒ 硬性顺序要求**：**先实测 `RD_CD` 填充率，再谈连接**。
⛔ 不得因「拿到了官方 schema 声明的字段」就宣布「连接链已恢复」。

---

## 4. ★P3 测量更正（预注册 §2 的一处部分计数）

预注册 §2 的 P3 记「**14 层完全剥空 · 3 层保文本清代码 · 7 层字段完整**」—— 三者之和 **24 ≠ 29**（侦察期**部分计数**）。

**本轮 29 层全量普查（可复现）**：

| 模式 | 层数 | 图例 |
|---|---:|---|
| **A 完全剥空**（仅 `OBJECTID`） | **14** | `DetectorLoop` · `ControlBox` · `Bollard` · `Footpath` · `GuardRail` · `KerbLine` · `Railing` · `RetainingWall` · `RoadCrossing` · `RoadHump` · `SpeedRegulatingStrip` · `StreetPaint` · `PassengerPickupBay` · `CoveredLinkWay` |
| **B 保文本清代码** | **3** | `RoadSectionLine` · `LampPost` · `CyclingPath` |
| **C 字段完整** | **12** | 其余 12 层 |

**性质**：**测量更正**（scope 从 24 层扩到 29 层全量），**非判据变更** —— 硬门 `G-O3R-4` 仍只断言「普查非退化且可复现」。
明细见 `o3r_local_inventory.csv`。

---

## 5. 本步执行结果

### 5.1 输入解析（`G-O3R-1`）

| 逻辑输入 | 声明路径（优先） | `declared_exists` | `resolved_path` |
|---|---|---|---|
| `DetectorLoop` | `recovery_7_9io3r/DetectorLoop/DetectorLoop.dbf` | **False** | ⛔ `null` ⇒ 回退到基线 |
| `RoadSectionLine` | `recovery_7_9io3r/RoadSectionLine/RoadSectionLine.dbf` | **False** | ⛔ `null` ⇒ 回退到基线 |
| `OnRequestJunctionLoopCounts` | `recovery_7_9io3r/junction_loop_counts/*.{csv,json}` | — | ⛔ `null` |

**⇒ 用户尚未放入恢复件** ⇒ 引擎按设计**受控收口**（`G-O3R-7`）。
全部候选与尝试痕迹：`o3r_input_resolution.json`。
本次盘点已预建投放目录 `recovery_7_9io3r/`（含 `README_DROP_HERE.md`）。

### 5.2 官方 schema 自证可复现（`G-O3R-2`）

| 图层 | FGDC | `AddField` | **并集** |
|---|---:|---:|---:|
| `DetectorLoop` | **12** | **0** | **12** |
| `RoadSectionLine` | **11** | **1**（`REMARKS`） | **12** |

`official_n`（两侧并集之和）= **24**。
（`N4` 负例把 schema 源退化为 `FGDC only` ⇒ `official_n = 23`，差值恰好 = `REMARKS` 一处，**证明 `AddField` 分支真实生效**。）

### 5.3 五个能力门（`G-O3R-6`）

常量（运行前冻结）：`MIN_FILL = 0.01` · `M4_CLOSE_MIN = 0.50`

| 门 | 判据 | 实测 | 取值 | 理由 |
|---|---|---|---|---|
| `M1a` | `RoadSectionLine` 侧 `RD_CD` 存在 ∧ 填充率 ≥ `MIN_FILL` | `RD_CD` 字段**存在**但填充率 **0.0000 / 15,329** | **`ABSENT`** | 字段在、值全空 |
| `M1b` | 检测器标识字段存在 ∧ 填充率 > 0 | `DetectorLoop.DETECTOR_ID` **不存在**；On-Request **未到手** | **`ABSENT`** | 两个来源都缺 |
| **`M2`** ★ | `RD_CD` **双侧可用** ∧ `intersection ≠ ∅` | 交付侧 `DetectorLoop` **仅 `{OBJECTID}`** | **`BLOCKED`** | 上游依赖未满足 |
| `M3` | `LANE_NUM` 存在，或检测器侧方向可恢复 | `LANE_NUM`（官方本无）缺失；检测器侧无方向字段 | **`ABSENT`** | — |
| `M4` | `F_LOW 9` 节设施级闭环比例 ≥ 0.50 | **`m4_closed = 0/9`**（`m4_ratio = 0.0`） | **`BLOCKED`** | 受 `M2` 阻塞 |

**⛔ 读法纪律（逐字沿用 O3-METADATA）**
- `BLOCKED` **只读「上游依赖未满足」**，⛔ **不读「不可连接」**；
- `ABSENT` **只读「本批无此字段」**，⛔ **不读「LTA 无检测器身份」**；
- `M2 = BLOCKED` **只读「本批无法建立该跳」**，⛔ **不读「LTA 数据体系无此关系」**。

### 5.4 逐跳连接统计（`G-O3R-*`；`o3r_recovery_layers.csv`）

> 用户点名要求：**1:1 / 1:N / N:1 / N:M + 覆盖率 + `K_pooled`**。口径见 PREREG §4：按「左键 → 右键集合势 `k`」× 「右键 → 左键集合势 `m`」双向计数。

| 跳 | 左 / 右 | `n_left` | `n_right` | `n_matched_L` | `n_matched_R` | `c_1_1` | `c_1_N` | `c_N_1` | `c_N_M` | 状态 |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| `①→②` `TF LinkID ─(RoadName)→ RD_CD` | TF links / RSL 道路码记录 | **1,278** | **0** | 0 | 0 | 0 | 0 | 0 | 0 | **`BLOCKED_EMPTY_SIDE`** |
| `②→③` / `③→④` `RoadSectionLine ─(RD_CD)→ DetectorLoop` | RSL / DET | **0** | **0** | 0 | 0 | 0 | 0 | 0 | 0 | **`BLOCKED_EMPTY_SIDE`** |
| `④→⑤` `DetectorLoop ─(Detector ID)→ On-Request` | DET / On-Request | **0** | **0** | 0 | 0 | 0 | 0 | 0 | 0 | **`BLOCKED_EMPTY_SIDE`** |

**逐跳判读**：

- **`①→②`**：`n_left = 1,278`（`TrafficFlow_Links` 全量 `LinkID` 都有 `RoadName`），但**右侧为空** —— 因为 `RoadSectionLine` 交付版**没有 `RD_NAM`**（且 `RD_CD` 填充率 0%）⇒ **该跳在没有恢复件时不可建立**。既不是 1:1 也不是 1:N，而是 **`BLOCKED`**。
- **`②→③` / `③→④`**：**两侧都空**（`DetectorLoop` 仅 `{OBJECTID}`、`RoadSectionLine.RD_CD` 全空）⇒ 连「候选」都不存在。
- **`④→⑤`**：`DetectorLoop` 无 `DETECTOR_ID`、On-Request 未到手 ⇒ **两侧都空**。
- **`K_pooled`**：三跳均**不可计算**（`n_matched_left = 0`）⇒ ⛔ **不报比值**（承读法纪律：只报计数）。

**方向 / 车道可恢复性**：

| 量 | 值 | 说明 |
|---|---|---|
| `lane_recoverable` | **False** | `LANE_NUM` 在官方 schema 里**本就不存在** |
| `direction_recoverable` | **False** | 检测器侧无方向字段，且无链路可继承 |
| `geom.rsl_shp` / `geom.det_shp` | `True` / `True` | 几何文件存在 ⇒ **仅作支撑证据**，⛔ **不单独构成 M3**（承 §10.2：不得以几何邻近替代设施身份） |

### 5.5 `F_LOW 9` 节逐节闭环（`o3r_floow_closure.csv`）

**闭合定义（每节独立，4 条件全真）**：
① `LinkID → 路` ② `路 → 检测器` ③ 检测器有**唯一**设施身份 ④ **方向可归属**

| `section_id` | `road_name` | `obs_8_9` | ① | ② | ③ | ④ | `closed` |
|---|---|---:|:-:|:-:|:-:|:-:|:-:|
| 48461 | AYER RAJAH EXPRESSWAY | 4,118.0 | ✗ | ✗ | ✗ | ✗ | **False** |
| 49054 | AYER RAJAH EXPRESSWAY | 3,481.5 | ✗ | ✗ | ✗ | ✗ | **False** |
| 49104 | AYER RAJAH EXPRESSWAY | 2,896.0 | ✗ | ✗ | ✗ | ✗ | **False** |
| 48586 | AYER RAJAH EXPRESSWAY | 2,532.0 | ✗ | ✗ | ✗ | ✗ | **False** |
| 48708 | AYER RAJAH EXPRESSWAY | 2,393.5 | ✗ | ✗ | ✗ | ✗ | **False** |
| 48337 | AYER RAJAH EXPRESSWAY | 2,052.5 | ✗ | ✗ | ✗ | ✗ | **False** |
| 47163 | AYER RAJAH EXPRESSWAY | 1,967.0 | ✗ | ✗ | ✗ | ✗ | **False** |
| 49027 | AYER RAJAH EXPRESSWAY | 581.5 | ✗ | ✗ | ✗ | ✗ | **False** |
| 172382 | EAST COAST PARK SERVICE ROAD | 119.0 | ✗ | ✗ | ✗ | ✗ | **False** |

**`m4_closed = 0 / 9`（`m4_ratio = 0.0`）** ⇒ `M4 = BLOCKED`（受 `M2` 阻塞，非独立阴性结论）。
`Σobs = 20,141.0 veh/h`（本刀要回答的对象）。

### 5.6 `B` 类升级判据

**`B_SET = [48461, 49054, 47189]`（3 节，`B_BINDING_UNDECIDABLE`）**

- 升级条件（严格）：`M1a ∧ M1b ∧ M2` 三者同时成立 **且** 该节 §5.5 四条件全真；
- 本轮 `M1a = M1b = ABSENT`、`M2 = BLOCKED` ⇒ **`B` 保持 `UNRESOLVED` / `BINDING_UNDECIDABLE`，不升级**；
- ⛔ **不得**用几何邻近替代（同 `TWIN_GEOMETRIC_SUBSTITUTE` 纪律）。

---

## 6. 判决

```
无恢复件        -> status=BLOCKED, verdict=O3_RECOVERY_AWAITING_INPUT   (全部产物齐备, EXIT=0)
有恢复件:
   M1a ABSENT 或 M1b ABSENT -> RECOVERY_INCOMPLETE_FIELD_MISSING
   M2 BLOCKED               -> RECOVERY_FIELDS_PRESENT_LINKAGE_BLOCKED
   M2 EVALUABLE: M4>=0.50   -> RECOVERY_STAGE_1_CLOSED ; 否则 RECOVERY_PARTIAL_CLOSURE
```

**⇒ 本轮：`status = BLOCKED` · `verdict = O3_RECOVERY_AWAITING_INPUT`**

**★受控收口已满足（`G-O3R-7`）**：`status = BLOCKED`，但**全部 11 项产物齐备**、`EXIT = 0`、**⛔ 无 Traceback**。
`o3r_closure.csv` 已把终局态物化（`gates_verdict = O3_RECOVERY_GATES_PASS` · `n_gates_pass = 12/12`）。

**★状态推进**

| | |
|---|---|
| `state_in` | `D2-review ✓ → O3 ✓ → O3-METADATA ✓ → READY(O3-DATA-RECOVERY)` |
| `state_out` | **`O3_RECOVERY_AWAITING_INPUT`**（引擎就绪、门禁 12/12、等用户放入恢复件） |
| 下一步触发条件 | `recovery_7_9io3r/DetectorLoop/DetectorLoop.dbf` **∧** `recovery_7_9io3r/RoadSectionLine/RoadSectionLine.dbf` 同时就位 ⇒ 重跑引擎自动切换到有恢复件分支 |

---

## 7. 硬门 `G-O3R-1` – `G-O3R-12`（**12 / 12 PASS**）

| 门 | 内容 | 实测 | 判定 |
|---|---|---|---|
| `G-O3R-1` | 输入解析：每逻辑输入报 `declared_path` / `declared_exists` / `resolved_path`；全部候选落盘 | 3 逻辑输入 · 全部候选已落盘 | **PASS** |
| `G-O3R-2` | 官方 schema 自证可复现（FGDC ∪ `AddField`，含 `REMARKS` 归类） | `DetectorLoop` 12 ∪ 0 = **12**；`RoadSectionLine` **11 ∪ {`REMARKS`} = 12** | **PASS** |
| `G-O3R-3` | `REMARKS` 更正已落盘（§0） | 4 文档 `has_old = False ∧ has_new = True` | **PASS** |
| `G-O3R-4` | 本地图层普查非退化 | 29 层 · **A 14 / B 3 / C 12**（和 = 29） | **PASS** |
| `G-O3R-5` | `RD_CD` 格式证据 | `LampPost` **61** 条非空 · **全 6 字符** · 去重 **6** | **PASS** |
| `G-O3R-6` | 能力门判定完备（5 门各有取值与理由） | 5/5 有值 + 有理由 | **PASS** |
| `G-O3R-7` | `AWAITING_INPUT` 受控收口 | `status=BLOCKED` · 产物齐备 · `EXIT=0` | **PASS** |
| `G-O3R-8` | 负例可证伪（`N1–N6`） | **6/6** `fired ∧ hit`，标注 `REHEARSAL_ON_BASELINE` | **PASS** |
| `G-O3R-9` | 零仿真 AST 自检 | `banned = []`（无 `subprocess`/`os`/`java`/`shlex`/`pty`） | **PASS** |
| `G-O3R-10` | 冻结件未改 | v1.0 快照 **84 文件** · `changed = []` | **PASS** |
| `G-O3R-11` | 不产生 v1.1 | `parameters_changed=False` · `matsim_rerun=False` · `crosswalk_changed=False` | **PASS** |
| `G-O3R-12` | manifest 最后生成、不自哈希；闭环物化 | `generated_last=True` · `self_hashed=False` · `o3r_closure.csv` 有 **14** 行 | **PASS** |

### 7.1 负例 `N1–N6`（全部共用同一 `compute(p)`）

> **恢复件缺席 ⇒ 标注 `REHEARSAL_ON_BASELINE = True`**：每个负例取「使其设计方向成立」的**最小锚点**（`N1/N2/N4/N5` 锚点 = 真实基线；`N3/N6` 锚点 = 基线 ⊕ `inject_rd_cd`，使 `M1a` 先 `PRESENT`），再叠加**单点扰动**。

| 负例 | 扰动 | 设计可观测量 | 锚点 → 扰动 | `fired` | `hit` |
|---|---|---|---|---|---|
| `N1` | 注入伪造 `DETECTOR_ID` | `M1b` | `ABSENT → PRESENT` | ✅ | ✅ |
| `N2` | 双侧注入相交 `RD_CD` | `M2` | `BLOCKED → EVALUABLE` | ✅ | ✅ |
| `N3` | 删除 `RD_CD` 列 | `M1a` | `PRESENT → ABSENT` | ✅ | ✅ |
| `N4` | schema 源退化为 `FGDC only` | `official_n` | `24 → 23` | ✅ | ✅ |
| `N5` | 注入伪造 `LANE_NUM` | `M3` | `ABSENT → PRESENT` | ✅ | ✅ |
| `N6` | `RD_CD` 填充率压 0 | `M1a` | `PRESENT → ABSENT` | ✅ | ✅ |

**⇒ 6/6 全部 `fired ∧ hit`：五门与官方 schema 解析**均可被单点扰动翻转 ⇒ **判定可证伪、非退化**。

### 7.2 可复现性

两次连续运行，10 项核心产物 **SHA256 逐位一致**：

```text
bf943e21731f1395  o3r_local_inventory.csv
04b7f19522b92681  o3r_official_schema.csv
6af0caafe02d9c57  o3r_rdcd_format_evidence.csv
ffb125e099c6b386  o3r_input_resolution.json
090232ae6f687d3a  o3r_recovery_layers.csv
7219413735fc8aea  o3r_floow_closure.csv
f62019c5d43906f8  o3r_m_gates.json
69ee201c789b8f94  o3r_checks.csv
b57b140fbdfc0939  o3r_summary.json
51499254f26cffd3  o3r_closure.csv
```

---

## 8. ★缺陷登记

| 编号 | 类别 | 内容 | 处置 |
|---|---|---|---|
| **R1** | **仪器实现缺陷（门禁判定分辨率）** | `G-O3R-3` 原用**全文件级** token 共现（同一文件出现 `REMARKS` 即视为未更正）⇒ **无法区分**「`REMARKS` 被列为臆造」与「`REMARKS` 已被更正说明」（本步 §2.74 正文自身即触发误报） | 改为**行级**判定（**同一行**同时出现 `REMARKS` 与该臆造登记表名才判为未更正）。**门禁语义 / 阈值 / 判决空间一律未改** ⇒ 属**仪器层修正**，非判据变更 |
| **D1** | 测量更正 | 预注册 §2 的 P3「7 层字段完整」为侦察期**部分计数**（14+3+7=24≠29） | 29 层全量普查更正为 **12**；**判据未变**（`G-O3R-4` 仍只断言「非退化且可复现」） |
| **D2** | 已知风险（未触发） | `lta_dynamic_data_downloader.py` 具 `if os.path.exists(save_path): skip` ⇒ **直接重跑不刷新** | 已写入 `ACQUISITION_MANIFEST` §2 与 `recovery_7_9io3r/README_DROP_HERE.md` |
| **D3** | 结构性阻塞 | 三跳 `BLOCKED_EMPTY_SIDE` 且 `M4` 受 `M2` 阻塞 ⇒ **本批不可能产生独立阳性结论** | ⛔ 属**预期**；读法纪律已禁止把 `BLOCKED` 读作阴性 |
| **D4** | S3 链接时效 | `GeospatialWholeIsland_Links.json` 中的预签名链接**已过期** | 清单已注明必须**用自己的凭据重新请求 API** |
| **D5** | 覆盖边界 | `TrafficFlow_Links`（本步 `①→②` 左端）**无 `*.shp.xml`** ⇒ 无官方 schema 自证源 | 已在 O3-METADATA 登记，本步沿用 |

---

## 9. 判读纪律（承 PREREG §10，8 条硬约束）

1. ⛔ **不得**把「拿到官方 schema 声明的字段」等同于「连接链已恢复」—— **必须先实测填充率**。
2. ⛔ **不得**用几何邻近替代设施身份（同 `TWIN_GEOMETRIC_SUBSTITUTE` 纪律）。
3. ⛔ **不得**预设 `Junction ID ↔ LinkID` 可连接；必须实测。
4. ⛔ `BLOCKED` / `ABSENT` 的读法严格按 §5.3。
5. ⛔ **不得**因本步结果改动 v1.0 / `trafficDynamics` / `signals` / `speedFactor`。
6. ⛔ **不得**把 `F_LOW` 的现状读作「需求不足」（承 7.7D 收口）。
7. ⛔ **只补元数据**：不改模型、不改评价器、不跑仿真。
8. ⛔ **`REMARKS` 更正必须在报告与 readme 同步**，不得只改一处 —— 已在 §2.3 落定 4 处。

---

## 10. 交付物

| 类别 | 文件 |
|---|---|
| 预注册 | `PREREG_7_9I_O3RECOVERY.md` |
| 本报告 | `STEP7_9I_O3RECOVERY_REPORT.md` |
| **采集清单** | **`ACQUISITION_MANIFEST_7_9I_O3RECOVERY.md`** |
| 引擎 | `scripts/od/audit_o3_recovery_7_9io3r.py` |
| 自检 | `scripts/od/check_o3_recovery_inputs_7_9io3r.py` |
| 投放目录 | `recovery_7_9io3r/`（含 `README_DROP_HERE.md`） |
| 产物 | `o3r_local_inventory.csv` · `o3r_official_schema.csv` · `o3r_rdcd_format_evidence.csv` · `o3r_input_resolution.json` · `o3r_m_gates.json` · `o3r_recovery_layers.csv` · `o3r_floow_closure.csv` · `o3r_checks.csv` · `o3r_summary.json` · `o3r_closure.csv` · `o3r_manifest.json` |
| 运行日志 | `_run_7_9io3r.log` |
| 文档同步 | `CLOSURE_7_9I.md` §14.0/§14.2/§15 · `docs/readme_technical_v1.md` §2.73/§2.74 + 变更记录 · `PREREG_7_9I_O3.md` · `PREREG_7_9I_O3METADATA.md` |

---

## 11. 下一步（⛔ 本节点不擅自启动）

| 优先级 | 动作 | 关键约束 |
|---|---|---|
| **P1** | 本地取回**属性完整版** `DetectorLoop` **+** `RoadSectionLine`（**两个都要**） | ⚠ 重跑下载脚本前**先删/改名旧 zip**，否则 `⊘ 文件已存在，跳过`；⛔ **不要在聊天里发 `AccountKey`** |
| **P1** | 放到 `recovery_7_9io3r/<图层名>/<图层名>.dbf` ⇒ 跑 `check_o3_recovery_inputs_7_9io3r.py` 自检 ⇒ 再跑主引擎 | 仍然 **不跑 MATSim**；先做逐层统计 |
| **P2** | 申请 On-Request `Indicative Traffic Counts at Junctions by Loop Detectors` | **`Detector ID` 的唯一来源**；⛔ **不得预设一定能连上**；是**独立交叉验证**，非 Geospatial 的替代 |

**最终目标**：回答 **那 `20,141 veh/h` 的「异常」对应的是哪个现实检测对象** ——
这才是下一轮**决定是否修改 MATSim 路网或动力学**的真正入口。

---

**边界（全程未动）**
`B = BINDING_UNDECIDABLE` **不升级** · ⛔ 不改 v1.0 · ⛔ 不改 `TrafficFlow` 原始值 · ⛔ 不改 crosswalk ·
⛔ 不改评价器阈值 · ⛔ 不跑 MATSim · ⛔ 不碰 `signals` / `trafficDynamics` / `speedFactor` · ⛔ 不产生 v1.1。
