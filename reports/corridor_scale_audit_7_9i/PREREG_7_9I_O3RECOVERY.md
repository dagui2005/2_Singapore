# PREREG — Step 7.9I-O3-DATA-RECOVERY（运行前冻结）

> **状态**：`D2-review ✓ → O3 ✓ → O3-METADATA ✓ → READY(O3-DATA-RECOVERY)`
> **用户裁定（2026-10-01）**：继续 `O3-METADATA`，优先走「本地重新获取完整属性数据」路线，同时申请 On-Request 数据作为**第二证据层**。
> **本步性质**：**零仿真**、**不改模型 / 不改评价器 / 不跑 MATSim**；**恢复 `TrafficFlow → Detector / 道路设施` 的可连接身份链**。
> **冻结边界**：⛔ 不改 v1.0 · ⛔ 不改 TrafficFlow 原始值 · ⛔ 不改 crosswalk · ⛔ 不改评价器阈值 · ⛔ 不跑 MATSim · ⛔ 不碰 `signals` / `trafficDynamics` / `speedFactor`。
> **`B = BINDING_UNDECIDABLE` 继续保持**，直到真正拿到属性连接链才允许升级为 `EVALUABLE / CONFIRMED / REJECTED`。

---

## §0. 本预注册对 O3-METADATA 的一处**正式自查更正**（必须先读）

O3-METADATA 把 `REMARKS`×2 登记为 `DOC_FABRICATED_FIELDS`（臆造）。本轮在**源库变更日志**里找到了反证：

| 图层 | `AddField` 记录（源库 `GDM@PDN4` / ArcSDE Oracle `gispprod`） | 更正后判定 |
|---|---|---|
| **`RoadSectionLine`** | ✅ `AddField D:\Data\GDMPDN4.sde\GDM.LTALayers\GDM.RoadSectionLine REMARKS TEXT # # 200 Remarks NULLABLE NON_REQUIRED`（**Date=20140801**） | **`REMARKS` 是真实源字段** ⇒ 从 `DOC_FABRICATED_FIELDS` **移出**，改入 `SOURCE_ONLY_STRIPPED`（真实但在交付中被剥） |
| `DetectorLoop` | ⛔ **无 `AddField` 记录** | 维持「官方 FGDC schema 未声明」，但**降级**为 `UNCONFIRMED_IN_SOURCE`，⛔ **不得再称「臆造」** |

**方法学更正（可复用）**：`*.shp.xml` 的**官方 schema 自证源不止一种写法** —— 除 FGDC 字段映射串外，还有 **`AddField` 语句**（源库变更日志）。**权威 schema = FGDC 映射 ∪ `AddField`**。仅用 FGDC 正则会**漏字段**（本轮实测：29 图层中仅 **6** 个含 FGDC 映射串，但 **24** 个含 `AddField`）。

`DETECTOR_ID` / `LANE_NUM` 的判定**不变**（`DetectorLoop` 官方 = FGDC 12 字段 ∪ `AddField` ∅ = 12，确实**不含**此二者）。

---

## §1. 本步唯一目标与**纠正后的**恢复链

**唯一目标**：恢复 `TrafficFlow → Detector / 道路设施` 的**可连接身份链**。

⛔ O3-METADATA **已正式证伪**的旧链（不得再提）：
```text
DetectorLoop → DETECTOR_ID → TrafficFlow        # ⛔ 已被证伪
```

✅ **本步正式采用的恢复链**（逐跳独立判定，**不得跳级**）：
```text
① TrafficFlow LinkID  ──(RoadName / RoadCat)──▶  ② RD_CD
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
- **①→②**：`TrafficFlow_*` 只有 `RoadName`/`RoadCat`，**无 `RD_CD`** ⇒ 这一跳**需要一个 road-name↔RD_CD 字典**（来自 ③ 或 ④ 的完整属性版）。
- **②→③**：靠 `RD_CD` 连接。⚠️ 但见 §2 的**否定性先验**。
- **③→④**：靠 `RD_CD` 连接。
- **④→⑤**：**只有 On-Request**（`Junction ID` + `Detector ID`）。
- **⑤→①**：⛔ **不得预设可连接**（用户原话：「这一层不能预设一定能连上」）。

---

## §2. 运行前已掌握的**否定性先验**（必须写进结论，不得隐藏）

本轮零仿真侦察（全 29 图层字段普查）发现三条**指向「②/③ 可能失效」的先验**：

| # | 事实 | 结论 |
|---|---|---|
| **P1** | **`RD_CD` 在三个独立图层里 100% 为空**：`RoadSectionLine` 0/15,329 · `CyclingPath` 0/4,830 · `LampPost` 61/126,916（**0.048%**） | 「保文本（`RD_CD_DESC` 100%）/ 清代码（`RD_CD` ~0%）」是**跨图层重复出现的模式** ⇒ 可能**不是交付剥离，而是源库本身未赋值** |
| **P2** | `LampPost` 的 61 条非空 `RD_CD` **全部是 6 字符字母数字**：`ZZ190A` `ZZ202A` `ZZ161A` `ZZ203A` `ZZZ43A` `PUP06M`（去重后仅 **6 个**） | 与官方 `RD_CD (Road Code, 6)` 声明**吻合** ⇒ **`RD_CD` 确实存在于源数据**；但取值形如**内部占位/临时码**（`ZZ`/`ZZZ` 前缀）⇒ **很可能不是可用的道路码体系** |
| **P3** | **剥空是逐图层差异化的，不是统一的**：14 层**仅 `OBJECTID`**（含 `DetectorLoop`）· 3 层「保文本清代码」· 7 层**字段完整**（含真 ID 如 `BUS_STOP_N`/`GNTRY_NUM`/`STN_NAM`） | 说明存在**可获取的完整版图层**；但**不保证 `DetectorLoop`/`RoadSectionLine` 在完整版中 `RD_CD` 有值** |

**⇒ 硬性顺序要求**：**先实测 `RD_CD` 填充率，再谈连接**。⛔ 不得因「拿到了官方 schema 声明的字段」就宣布「连接链已恢复」。

---

## §3. 输入契约（**声明路径优先**，含备用回退）

本步**不接触任何凭据**（用户本地自行下载，无需告知 AccountKey）。输入落盘候选（**按序尝试，命中即用，全部候选写入 `o3r_input_resolution.json`**）：

| 逻辑输入 | 声明路径（优先） | 备用回退 |
|---|---|---|
| `DetectorLoop`（属性完整版） | `recovery_7_9io3r/DetectorLoop/DetectorLoop.dbf` | `recovery_7_9io3r/DetectorLoop.dbf` · `recovery_7_9io3r/DetectorLoop/*.dbf` · `uploads/**` |
| `RoadSectionLine`（属性完整版） | `recovery_7_9io3r/RoadSectionLine/RoadSectionLine.dbf` | `recovery_7_9io3r/RoadSectionLine.dbf` · `recovery_7_9io3r/RoadSectionLine/*.dbf` · `uploads/**` |
| On-Request Junction Loop Counts | `recovery_7_9io3r/junction_loop_counts/*.{csv,json}` | `recovery_7_9io3r/JunctionLoopCounts*` · `uploads/**` |
| 基线（**已有**，非恢复件） | `Static_ 2026_03/GEOSPATIAL/{DetectorLoop,RoadSectionLine}_Mar2026/...` | `Dynamic_2026_03_16/historical_data/geospatial/...` |

★ 纪律（承 7.9F-1）：**声明路径必须排第一**（保留「尝试过但不存在」的痕迹）；真实路径排后。

---

## §4. 逐层统计口径（用户点名必须输出）

对**每一跳**（①→② · ②→③ · ③→④ · ④→⑤）逐层统计：

| 量 | 定义 |
|---|---|
| `n_left` / `n_right` | 两侧 **非空键** 的记录数 |
| `n_matched_left` / `n_matched_right` | 命中对方的记录数 |
| `c_1_1` / `c_1_N` / `c_N_1` / `c_N_M` | 按**左键 → 右键集合的势**（`k`）+ **右键 → 左键集合的势**（`m`）双向计数：`k=1∧m=1`→`1:1`；`k=1∧m>1`→`1:N`；`k>1∧m=1`→`N:1`；`k>1∧m>1`→`N:M` |
| `coverage_left` / `coverage_right` | `n_matched_*/n_*` |
| `K_pooled` | `n_matched_right_total / n_matched_left`（**只报计数，不作比值**） |
| `direction_recoverable` | 仅当存在几何（`*.shp`）+ 顶点可算 bearing 时 = `True`；另有方向字段则 `True` |
| `lane_recoverable` | 存在 `LANE_NUM`/`LANES`/`Lanes` 字段且非全空 |

★ 纪律：**多边映射必报计数基数 `K`**（承 readme §4）；**取子集必断言命中非零**。

---

## §5. 五个能力门（`M1a · M1b · M2 · M3 · M4`）

> 用户原话：**「拿到新数据以后，先不要跑 MATSim，只做四个零仿真门」**；本预注册把 `M1` 拆为 `M1a`/`M1b`（承 O3-METADATA），共 5 门。

| 门 | 判据（**可证伪**） | 取值 |
|---|---|---|
| **`M1a`** | `RoadSectionLine` 侧 `RD_CD` **字段存在** ∧ 填充率 ≥ `MIN_FILL` | `PRESENT` / `ABSENT` |
| **`M1b`** | 检测器标识字段**存在**（`DetectorLoop` 的 `DETECTOR_ID` **或** On-Request 的 `Detector ID`）∧ 填充率 > 0 | `PRESENT` / `ABSENT` |
| **`M2`** ★最重要 | `RD_CD` **双侧可用** ∧ `intersection(RSL.RD_CD, DET.RD_CD) ≠ ∅` | `EVALUABLE` / `BLOCKED` |
| **`M3`** | `LANE_NUM` 存在**或**可从几何恢复方向；否则 `ABSENT` | `PRESENT` / `ABSENT` |
| **`M4`** | `F_LOW 9` 节中达到**设施级对象闭合**的比例 ≥ `M4_CLOSE_MIN` | 比例（含逐节明细） |

**常量（运行前冻结）**：`MIN_FILL = 0.01`（1%）；`M4_CLOSE_MIN = 0.50`。
⚠️ `MIN_FILL = 0.01` 的标定依据：`LampPost` 的 `RD_CD` 填充率 = **0.048%**，若阈值取 1% 则**明确判否**；若取 0.01% 则**误判为可用**。取 1% 是为了**排除占位码级别的极稀疏填充**。

⚠️ **读法纪律（承 O3-METADATA，逐字沿用以防越界）**：
- `BLOCKED` **只读「上游依赖未满足」，⛔ 绝不读作「不可连接」**；
- `ABSENT` **只读「本批文件中无此字段」，⛔ 不读「LTA 无检测器身份」**；
- `M2 = BLOCKED` **只读「本批无法建立该跳」，⛔ 不读「LTA 数据体系无此关系」**。

---

## §6. `F_LOW 9` 节闭合判据 + `B` 类升级判据

**集合（冻结）**：
- `F_LOW = [48461, 49054, 49104, 48586, 48708, 48337, 47163, 49027, 172382]`（9 节；`Σobs = 20,141`）
- `B_SET = [48461, 49054, 47189]`（3 节；`B_BINDING_UNDECIDABLE`）
- `REFERENCE / F_ADQ = [45956, 47189, 45927, 48983, 129352]`（5 节）

**闭合定义（每节独立，四条件全真）**：
1. 该节 `LinkID` 能经 `RoadName`（或 `RD_CD`）连到 ≥1 条 `RoadSectionLine`；
2. 该 `RoadSectionLine` 能经 `RD_CD` 连到 ≥1 个 `DetectorLoop`；
3. 该 `DetectorLoop` 有**唯一**的设施身份（`Detector ID` 或可归一到 `Junction ID`）；
4. 该身份**方向可归属**（单方向 / 明确双向）。

**`B` 类升级判据（严格）**：
- `B: UNRESOLVED → EVALUABLE`：仅当 `M1a ∧ M1b ∧ M2` 三者同时成立，**且**该节上文 4 条全真；
- 否则保持 `UNRESOLVED`（⛔ **不得**用几何邻近替代 —— 与 `TWIN_GEOMETRIC_SUBSTITUTE` 同纪律）。

---

## §7. 硬门（`G-O3R-*`）与负例（`N1–N6`）

| 门 | 内容 |
|---|---|
| `G-O3R-1` | **输入解析**：每个逻辑输入报 `declared_path` / `declared_exists` / `resolved_path`；全部候选落盘 |
| `G-O3R-2` | **官方 schema 自证**：`DetectorLoop` 与 `RoadSectionLine` 的 `FGDC ∪ AddField` 可复现（含 `REMARKS` 归类） |
| `G-O3R-3` | **`REMARKS` 更正已落盘**（§0） |
| `G-O3R-4` | **本地图层普查非退化**：29 图层 · 三种剥空模式计数可复现 |
| `G-O3R-5` | **`RD_CD` 格式证据**：`LampPost` 61 条非空值全部 6 字符、去重 6 |
| `G-O3R-6` | **能力门判定完备**：`M1a/M1b/M2/M3/M4` 各有取值与理由 |
| `G-O3R-7` | **`AWAITING_INPUT` 受控收口**：无恢复件时 `status = BLOCKED`，**但全部产物齐备**、`EXIT = 0`（⛔ 不 Traceback） |
| `G-O3R-8` | **负例可证伪**（`N1–N6`，见下）；**无恢复件时在基线上做「门禁可翻转预演」并显式标注 `REHEARSAL_ON_BASELINE`** |
| `G-O3R-9` | **零仿真**：AST 自检（无 `subprocess` / `java` / `matsim` 调用）|
| `G-O3R-10` | **冻结件未改**：跑前后对 v1.0 目录做 mtime+size 快照，`changed = []` |
| `G-O3R-11` | **不产生 v1.1**：`parameters_changed=False` / `matsim_rerun=False` / `crosswalk_changed=False` |
| `G-O3R-12` | **manifest 最后生成**且**不自哈希**；终局闭环物化为 `o3r_closure.csv` |

**负例（主路径与全部负例共用同一 `compute(p)`；签名必须含可观测量）**：
- `N1` 注入伪造 `DETECTOR_ID` 列 ⇒ `M1b ABSENT→PRESENT`；
- `N2` 给 `RoadSectionLine.RD_CD` 注入与 `DetectorLoop` 相交的值 ⇒ `M2 BLOCKED→EVALUABLE`；
- `N3` 删除 `RD_CD` 列 ⇒ `M1a PRESENT→ABSENT`；
- `N4` 官方 schema 源退化为 `FGDC only` ⇒ `official_n` 变小（`AddField` 分支失效）；
- `N5` 注入伪造 `LANE_NUM` ⇒ `M3 ABSENT→PRESENT`；
- `N6` 把 `RD_CD` 填充率压到 0 ⇒ `M1a → ABSENT`（填充率门可证伪）。

---

## §8. 状态机与判决空间

```text
无恢复件        -> status=BLOCKED, verdict=O3_RECOVERY_AWAITING_INPUT      (全部产物齐备, EXIT=0)
有恢复件:
   M1a ABSENT 或 M1b ABSENT -> verdict=RECOVERY_INCOMPLETE_FIELD_MISSING
   M2 BLOCKED               -> verdict=RECOVERY_FIELDS_PRESENT_LINKAGE_BLOCKED
   M2 EVALUABLE:
        M4 >= 0.50           -> verdict=RECOVERY_STAGE_1_CLOSED
        M4 <  0.50           -> verdict=RECOVERY_PARTIAL_CLOSURE
```

## §9. 交付物清单

`reports/corridor_scale_audit_7_9i/`：`STEP7_9I_O3RECOVERY_REPORT.md` · `ACQUISITION_MANIFEST_7_9I_O3RECOVERY.md` ·
`o3r_local_inventory.csv` · `o3r_official_schema.csv` · `o3r_rdcd_format_evidence.csv` ·
`o3r_input_resolution.json` · `o3r_m_gates.json` · `o3r_recovery_layers.csv` · `o3r_floow_closure.csv` ·
`o3r_checks.csv` · `o3r_summary.json` · `o3r_manifest.json` · `o3r_closure.csv` · `_run_7_9io3r.log`；
脚本 `scripts/od/audit_o3_recovery_7_9io3r.py`。

## §10. 判读纪律（8 条，全部为硬约束）

1. ⛔ **不得**把「拿到官方 schema 声明的字段」等同于「连接链已恢复」——**必须先实测填充率**。
2. ⛔ **不得**用几何邻近替代设施身份（同 `TWIN_GEOMETRIC_SUBSTITUTE` 纪律）。
3. ⛔ **不得**预设 `Junction ID ↔ LinkID` 可连接；必须实测。
4. ⛔ `BLOCKED` / `ABSENT` 的读法严格按 §5。
5. ⛔ **不得**因本步结果改动 v1.0 / trafficDynamics / signals / speedFactor。
6. ⛔ **不得**把 `F_LOW` 的现状读作「需求不足」（承 7.7D 收口）。
7. ⛔ **只补元数据**：不改模型、不改评价器、不跑仿真。
8. ⛔ **`REMARKS` 更正必须在报告与 readme 同步**，不得只改一处。

---

**冻结时间**：2026-10-01（运行前）
**性质**：零仿真 · 不改模型 · 不跑 MATSim · 不构成 v1.1
