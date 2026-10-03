# STEP7_9I_O3METADATA_REPORT.md — Step 7.9I-O3-METADATA「恢复 TrafficFlow → Detector / 道路设施 可连接身份链」

> 节点：`O3 ✓ → READY(O3-METADATA)`
> 裁定：用户 **①补齐 LTA 设施级标识字段**，不走②，不把 TrafficFlow 从硬校准域剔除
> 纪律：**零仿真** · 不改模型 · 不改评价器 · 不跑 MATSim · ⛔ 缺元数据不得以几何邻近替代
> 预注册（运行前冻结）：`PREREG_7_9I_O3METADATA.md`
> 引擎：`scripts/od/audit_o3_metadata_7_9io3m.py` · 判决：**`O3_METADATA_AUDIT_CLOSED`（9/9 门 + 负例 5/5）**

---

## §0 结论摘要

| # | 结论 | 证据 |
|---|---|---|
| **C1** | **官方 GDM schema 已逐字恢复**（来源 = 交付包内 FGDC 元数据 `*.shp.xml`，LTA 侧自证，非第三方推断） | `DetectorLoop` **12** 字段 / `RoadSectionLine` **11** 字段 |
| **C2** | **`DetectorLoop` 官方 schema 中不存在 `DETECTOR_ID`、也不存在 `LANE_NUM`** ⇒ 本地文档的这两个字段是**臆造** | `G-M4`：文档独有 = `{DETECTOR_ID, LANE_NUM, REMARKS}`（**3 个**） |
| **C3** | **`DetectorLoop` 官方 schema 唯一道路关联键 = `RD_CD`（Road Code, 6）**，且被 domain 绑定到 `roadname` | `DetectorLoop.shp.xml`：`AssignDomainToField ... GDM.DetectorLoop RD_CD roadname` |
| **C4** | **交付的 `DetectorLoop` 仅剩 `OBJECTID`**；官方应有的 **10 个非几何字段一个未到** | 交付 = `{OBJECTID}`；官方独有 = **10** |
| **C5** | **`RD_CD` 在交付包内「字段在、值全空」**：`RoadSectionLine.RD_CD` 填充率 = **0.0000 / 15,329**；`RD_CATG_NA` 同为 0.0000 | `G-M3` |
| **C6** | **⇒ 整条 road-code 连接层在交付包中被剥空**（`DetectorLoop` 侧字段删、`RoadSectionLine` 侧值空） | `G-M5`：`RD_CD` 双侧可用 = **False** |
| **C7** | 交付包**保留了文本类**（`RD_CD_DESC` 路名 100%、`RD_CATG__1` 类别 100%），**清空了代码类**（`RD_CD`/`RD_CATG_NA` 0%） | `o3m_field_fill.csv` |
| **C8** | **双获取路径结论一致**：`Static` 原件与 `Dynamic` 重下 zip **字段集全等 = `{OBJECTID}`** ⇒ 缺口**不是单次下载失误** | `G-M6` |
| **C9** | **`Detector ID` 的唯一可能来源 = On-Request `Indicative Traffic Counts at Junctions by Loop Detectors`**；且它与 `DetectorLoop` **同要素域**（同为 signalised junction 上的 loop detector） | 官方 On-Request 页逐字：（略，见 §4.6） |
| **C10** | **四门状态（用户裁定的 M1–M4）**：`M1a=ABSENT · M1b=ABSENT · M2=BLOCKED · M3=BLOCKED · M4=BLOCKED` —— ⛔ **BLOCKED 只读「上游依赖未满足」，不读「不可连接」** | `G-M7` |

**一句话**：**TrafficFlow 的道路段语义清楚（O3 已证），但把它绑到"设施/车道/方向"的那一层属性，在本批交付里被整层剥掉了；而"检测器身份"这一层，LTA 公开 geospatial 层在设计上就不提供。**

---

## §1 立论与范围

O3 已经把问题钉到：**观测对象结构层清楚、设施归属层 `OBS_OBJECT_UNRESOLVED`、缺口性质 = `DATA_ACQUISITION_GAP`（不是「LTA 没有」，是「本批未取得」）**。

本节点**只做一件事**：把"**缺什么、缺到哪一层、哪条来源可能补上**"钉死，并冻结验收门。
**⛔ 不做**：不产生任何关于 `F_LOW` 成因的新结论；不做几何替代；不做任何连接尝试；不跑仿真。

---

## §2 方法

### 2.1 数据资产（只读）

| 资产 | 路径 | 规模 |
|---|---|---|
| `DetectorLoop` 交付（Static 原件） | `Static_ 2026_03/GEOSPATIAL/DetectorLoop_Mar2026/…/DetectorLoop.dbf` | **16,275** 要素 |
| `DetectorLoop` 第二路径（Dynamic 重下 zip） | `Dynamic_2026_03_16/historical_data/geospatial/DetectorLoop.zip` | **16,275**（同） |
| `RoadSectionLine` 交付 | `Static_ 2026_03/GEOSPATIAL/RoadSectionLine_Mar2026/…/RoadSectionLine.dbf` | **15,329** 要素 |
| **官方 schema 源（★关键）** | 同目录 `DetectorLoop.shp.xml` / `RoadSectionLine.shp.xml`（FGDC 元数据，含源库导出字段映射） | 17,112 / 17,109 B |
| 文档声称源 | `Static_ 2026_03/DATA_DOCUMENTATION.md`、`Dynamic_2026_03_16/DATA_README.md` | — |
| 观测数据 | `TrafficFlow_Links.dbf` / `TrafficFlow_Data.json` | 1,278 / 75,899 条 |

**★方法学要点**：LTA 交付的 shapefile **自带 `*.shp.xml` FGDC 元数据**，其中 `CopyFeatures` / `Append` / `FeatureClassToFeatureClass` 的**字段映射串逐字记录了源库（`GDM.LTALayers`）的完整字段表**。
⇒ **这是本批数据内部唯一可用的"官方 schema 自证"来源**，⛔ 不是第三方推断、不是模型知识。

### 2.2 三方对账口径

对每个图层做三集对账：
- **官方** = `*.shp.xml` 字段映射并集（字段名规范化 `.`→`_`）
- **交付** = `*.dbf` 字节级表头解析 + 逐记录非空扫描（填充率）
- **文档** = 本地 `.md` 表格 / bullet 清单

差集命名：`OFFICIAL_ONLY`（官方有、交付无）· `DELIVERED_ONLY`（交付有、官方无）· `DOC_ONLY`（文档有、官方无 = **`DOC_FABRICATED_FIELDS`**）· `IMPLICIT`（`OBJECTID`/`SHAPE`，shapefile 隐式字段，不计入差集）

### 2.3 四门定义（用户裁定 + 运行前精化）

| 门 | 判据 | 状态取值域 |
|---|---|---|
| **M1a** | `RD_CD`（Road Code）在 `DetectorLoop` 侧是否恢复（字段存在 ∧ 填充率 > 0） | `PRESENT`/`ABSENT` |
| **M1b** | `DETECTOR_ID` 是否可取得 | `PRESENT`/`ABSENT` |
| **M2** | `Detector → RoadSection / LinkID` 是否能建立 | `EVALUABLE`/`BLOCKED` |
| **M3** | `Direction` / `Lane` 是否可恢复 | `PRESENT`/`BLOCKED` |
| **M4** | `F_LOW` 9 节（`Σobs` 20,141 / 占 D 类 71.02%）能否完成设施级对象闭合 | `EVALUABLE`/`BLOCKED` |

**★运行前精化的理由**（已写入冻结 prereg §3）：用户给的 `M1 = "DetectorID 是否恢复"` 必须**拆两支**，因为 `RD_CD` 与 `DETECTOR_ID` 的**来源、代价完全不同**（前者来自公开 geospatial，后者只能来自 On-Request）。
**⛔ 状态取值域严禁出现第四种**：不得以几何邻近把 `ABSENT` 改写成 `PRESENT`。

### 2.4 硬门与负例

- 硬门 **9 项**（`G-M1`…`G-M9`，含 AST 无随机源自检）
- 负例 **5 项**（`N1`…`N5`），**与主路径共用同一 `compute(p)` 入口**；签名 `sig` 必含可观测量：
  `(Σ官方字段数, Σ交付字段数, Σ填充率, ΣM状态码, 连接键布尔)`

---

## §3 硬门与负例结果

```
G-M1 官方 schema: DetectorLoop=12 RoadSectionLine=11                     PASS
G-M2 交付字段: DetectorLoop=['OBJECTID']
     RoadSectionLine=['RD_CATG_NA','RD_CATG__1','RD_CD','RD_CD_DESC']     PASS
G-M3 填充率: {RD_CD:0.0, RD_CATG_NA:0.0, RD_CATG__1:1.0, RD_CD_DESC:1.0} PASS
G-M4 文档臆造(DetectorLoop)=['DETECTOR_ID','LANE_NUM','REMARKS']; 官方独有=10;
     RSL 文档独有=['REMARKS']                                            PASS
G-M5 连接键: RD_CD 双侧可用=False ; 道路名级可用=True                     PASS
G-M6 双获取路径: zip=['OBJECTID'] static=['OBJECTID']                    PASS
G-M7 M 门: {M1a:ABSENT, M1b:ABSENT, M2:BLOCKED, M3:BLOCKED, M4:BLOCKED}  PASS
G-M8 负例 N1–N5 全部 fired=True ∧ hit_designed_observable=True           PASS
G-M9 AST 无随机源: OK                                                    PASS

verdict = O3_METADATA_AUDIT_CLOSED   gates = 9/9
sig_base = (23, 5, 3.0, 3, 0)
```

| 负例 | 扰动 | 设计可观测量 | 实测 |
|---|---|---|---|
| `N1` | 向 `DetectorLoop` 交付字段注入伪造 `DETECTOR_ID` | `M1b` | `ABSENT → PRESENT` ✓ |
| `N2` | 模拟「属性完整版 DetectorLoop 到手」（双侧 `RD_CD` 填充率 1.0） | `M2` | `BLOCKED → EVALUABLE` ✓ |
| `N3` | 键「层级」切到道路名级（`RD_CD_DESC ↔ RD_NAM`） | `key_available` | `0 → 1` ✓ |
| `N4` | 官方 schema 源从 `*.shp.xml` 退化到 `*.dbf` | `official_n` | `23 → 5` ✓ |
| `N5` | 注入伪造 `LANE_NUM` | `M3` | `BLOCKED → PRESENT` ✓ |

**⇒ 5 个负例全部真改变结果、非同构、且命中各自设计的可观测量** ⇒ `ABSENT`/`BLOCKED` **是数据状态的结论，不是判据失效的伪影**。

---

## §4 结果

### 4.1 官方 GDM schema（逐字恢复）

**`DetectorLoop`（12）**：`JOB_NUM`(Job No,20) · `TYP_CD`(Type of Feature,4) · `LVL_NUM`(Level of Road,2) · `EXCEPTION_IND`(1) · `LAST_UPD_USRID_NUM`(8) · `LAST_UPD_DTTM`(Date) · `CRT_USRID_NUM`(8) · `CRT_DTTM`(Date) · **`RD_CD`(6)** · `PKG_REF`(50) · `SHAPE_Length` · `SHAPE_Area`

要素定义（官方英文原文）：
> *"A symbolic polygon representation of an electronic loop on the road surface at **signalised junctions**, to detect **traffic movements** for **traffic control** purpose"*

**`RoadSectionLine`（11）**：`JOB_NUM`(20) · **`RD_CD`(Road Code,6)** · **`RD_NAM`(Road Name,150)** · `RD_CATG_NAM`(Road Category,20) · `EXCEPTION_IND`(1) · `LAST_UPD_USRID_NUM`(8) · `LAST_UPD_DTTM`(Date) · `CRT_USRID_NUM`(8) · `CRT_DTTM`(Date) · `PKG_REF`(50) · `SHAPE_LEN`

> ⚠️ 注：`RoadSectionLine.shp.xml` 含两处映射，分别写作 `SHAPE.LEN` 与 `SHAPE_LEN`（同字段两种拼法）⇒ 规范化后唯一计数 = **11**。

### 4.2 交付 vs 官方 vs 文档 —— 三方对账

**`DetectorLoop`**（16,275 要素）

| 状态 | 字段 |
|---|---|
| `OFFICIAL_ONLY`（官方有、交付无）**10** | `JOB_NUM` `TYP_CD` `LVL_NUM` `EXCEPTION_IND` `LAST_UPD_USRID_NUM` `LAST_UPD_DTTM` `CRT_USRID_NUM` `CRT_DTTM` `RD_CD` `PKG_REF` `SHAPE_Length` `SHAPE_Area`（其中 `JOB_NUM`/`RD_CD` 文档有声明） |
| `DELIVERED_ONLY` | `OBJECTID`（隐式） |
| `DOC_ONLY`（**臆造**）**3** | **`DETECTOR_ID`** · **`LANE_NUM`** · `REMARKS` |

**`RoadSectionLine`**（15,329 要素）

| 状态 | 字段 |
|---|---|
| `BOTH` | `RD_CD`（★**但填充率 0.0000**） |
| `OFFICIAL_ONLY` | `JOB_NUM` `RD_NAM` `RD_CATG_NAM` `EXCEPTION_IND` `LAST_UPD_*` `CRT_*` `PKG_REF` `SHAPE_LEN` |
| `DELIVERED_ONLY` | `RD_CATG_NA`（0.0000） · `RD_CATG__1`（1.0000） · `RD_CD_DESC`（1.0000） |
| `DOC_ONLY`（**臆造**） | `REMARKS` |

**`TrafficFlow_Data`**（75,899 条）

| 状态 | 字段 |
|---|---|
| 实际（10） | `LinkID` `Date` `HourOfDate` `Volume` `StartLon` `StartLat` `EndLon` `EndLat` `RoadName` `RoadCat` |
| `DOC_ONLY` | **`VehicleType`** · **`Timestamp`**（实际以 `Date` + `HourOfDate` 表达时间） |

### 4.3 ★文档臆造字段（`DOC_FABRICATED_FIELDS`）

本地 `DATA_DOCUMENTATION.md` 为 `DetectorLoop` 声明了 `LANE_NUM` / `DETECTOR_ID` / `REMARKS`，为 `RoadSectionLine` 声明了 `REMARKS` —— **这 4 个字段在 LTA 官方 GDM schema 中均不存在**。

**⇒ O3 的 `DATA_ACQUISITION_GAP` 需要精确化**：

| 原表述（O3） | 精确化（本节点） |
|---|---|
| "文档称有 `DETECTOR_ID`/`LANE_NUM`，实际无" | **`DETECTOR_ID`/`LANE_NUM` 从来不在 LTA 公开 geospatial schema 里** ⇒ 它们不该出现在"待恢复"清单 |
| — | **真正被剥掉的是 10 个非几何字段**（`JOB_NUM`/`TYP_CD`/`LVL_NUM`/`EXCEPTION_IND`/`LAST_UPD_*`/`CRT_*`/`RD_CD`/`PKG_REF`/`SHAPE_*`） |

### 4.4 连接键可用性

| 键层级 | 候选 | 双侧可用 | 判据 |
|---|---|---|---|
| **代码级** | `RD_CD`（Road Code） | **False** | `DetectorLoop` 侧字段被删；`RoadSectionLine` 侧填充率 **0.0000** |
| **道路名级** | `RD_CD_DESC`(交付,100%) ↔ `RD_NAM`(官方,150) | **True**（结构性可用） | 文本类字段被完整保留 |

**⇒ 即便拿到属性完整版 `DetectorLoop`，本套连接也最多到「道路名 / 道路码」级 —— 不是检测器级，更不是链路级。**

### 4.5 ★剥空模式（可复核）

| 图层 | 文本/名称类 | 代码/ID 类 | 几何派生量 |
|---|---|---|---|
| `RoadSectionLine` | **保留**（`RD_CD_DESC` 100%、`RD_CATG__1` 100%） | **清空**（`RD_CD` 0%、`RD_CATG_NA` 0%） | `SHAPE_LEN` **缺失** |
| `DetectorLoop` | — | 全缺 | `SHAPE_Length`/`SHAPE_Area` 亦**缺失** |

⚠️ **两图层的剥离强度不同**（`RoadSectionLine` 保文本、清代码；`DetectorLoop` 全清）⇒ **不是同一条规则**。本节点**只陈述观测，不推断 LTA 发布管线动机**。

### 4.6 On-Request 官方口径（逐字抓取，2026-10-01）

**`Indicative Traffic Counts at Junctions by Loop Detectors`**
> *"Indicative traffic counts captured by each loop detector installed at **signalised intersections**, **without vehicle classification counts**"*

- 字段：`Junction ID` · `Detector ID` · `Date and time for each collection period` · `Indicative traffic counts`
- 频率：**Daily** ｜ 格式：`XLS/CSV/TXT`

**★与 §4.1 的要素定义同域**（同是 signalised junction 上的 loop detector，同服务于 traffic control）⇒ 两者是**同一套设施的两个视角**：
`DetectorLoop` = **几何**（polygon，无身份字段） ｜ On-Request = **计数**（`Detector ID` + `Junction ID` + count）

（旁证，**冻结不取用**）On-Request 另有 `Traffic Lights Traffic Plans`（`Junction ID` + signal phase timing），与已登记的 `SIGNAL_MECHANISM_ABSENT` 同域。

### 4.7 M1–M4 状态机

| 门 | 状态 | 依据 |
|---|---|---|
| `M1a` `RD_CD` 是否恢复 | **ABSENT** | 交付字段集无 `RD_CD`（`DetectorLoop` 侧） |
| `M1b` `DETECTOR_ID` 是否可取得 | **ABSENT** | 官方 schema 无此字段；两条下载路径均无 |
| `M2` `Detector → RoadSection/LinkID` | **BLOCKED** | 依赖 `M1a` 未过 |
| `M3` `Direction` / `Lane` | **BLOCKED** | 无 lane / direction 字段来源 |
| `M4` `F_LOW` 9 节设施级闭合 | **BLOCKED** | 依赖 `M1a + M1b + M3` |

**⚠️ 判读纪律（必须遵守）**：`BLOCKED` **只读「上游依赖未满足」**；⛔ **不得读作「不可连接」**——那会把"数据未到"误判为"阴性结论"，属「假门禁」纪律违规。

---

## §5 判读

1. **本节点是"仪器校准"，不是"结论"**：它把 O3 的 `DATA_ACQUISITION_GAP` 从"若干字段缺失"**精确到"哪一层被剥、剥到什么程度、哪条来源能补"**。
2. **★不可越界的三条读法**：
   - `M1b = ABSENT` ⇒ 只读「**本批公开层无此字段**」，⛔ **不读「LTA 无检测器身份」**（检测器身份存在于 On-Request）。
   - `M1a = ABSENT` ⇒ 只读「**本批 `RD_CD` 被剥空**」，⛔ **不读「道路码不可得」**。
   - `M2/M3/M4 = BLOCKED` ⇒ 只读「**上游依赖未满足**」，⛔ **不读「不可连接」**。
3. **文档 vs 官方冲突时以官方为准**；`DOC_FABRICATED_FIELDS`（4 个）**已从采集目标中剔除**。
4. **本节点不产生**任何关于 `F_LOW` 成因的新结论；`F_LOW` **仍不是"需求不足"**。
5. **边界全部保持冻结**：`B = BINDING_UNDECIDABLE`（3 节，**不升级**）· `TWIN_GEOMETRIC_SUBSTITUTE` **仅几何证据** · v1.0 冻结（`SCALE=2.29897` / `N_sim=236,044` / `target=0.8589732`）· `signals`/`trafficDynamics`/`speedFactor` **不碰**。

---

## §6 复现

```
引擎：C:/Users/LQP/miniconda3/python.exe scripts/od/audit_o3_metadata_7_9io3m.py
两次运行产物 SHA256 前 16 位逐位一致：
  o3m_schema_reconciliation.csv  e50738292de820ee   (2,203 B)
  o3m_field_fill.csv             ac7eb1743ca870e2   (238 B)
  o3m_m_gates.json               533846204afc3623   (12,375 B)
G-M9 AST 自检：无 random / time / datetime / np 引用 ⇒ 无随机源
```

---

## §7 产物清单

| 文件 | 大小 | 内容 |
|---|---|---|
| `reports/corridor_scale_audit_7_9i/PREREG_7_9I_O3METADATA.md` | 10,826 B | 运行前冻结预注册 |
| `scripts/od/audit_o3_metadata_7_9io3m.py` | 21,517 B | 零仿真审计引擎（唯一入口 `compute(p)`） |
| `reports/corridor_scale_audit_7_9i/o3m_schema_reconciliation.csv` | 2,203 B | 三方逐字段对账 |
| `reports/corridor_scale_audit_7_9i/o3m_field_fill.csv` | 238 B | 逐图层逐字段填充率 |
| `reports/corridor_scale_audit_7_9i/o3m_m_gates.json` | 12,375 B | M 门 + 9 硬门 + 5 负例 + 采集目标 + 冻结边界 |
| `reports/corridor_scale_audit_7_9i/_run_7_9io3m.log` | — | 运行日志 |
| `reports/corridor_scale_audit_7_9i/STEP7_9I_O3METADATA_REPORT.md` | 19,446 B | 本文件 |

---

## §8 缺陷登记

### `R1` — 仪器实现缺陷（负例契约可实施性），**已披露**

| 项 | 内容 |
|---|---|
| **现象** | 首跑 `N3` `fired=False`、`N2` `hit=False` |
| **根因** | `N3` 原设计的字段名（冻结 prereg §3.2 记的 `RD_CATG__1`）**在 `DetectorLoop` 侧不存在** ⇒ 无法构成"双侧键" ⇒ **空扰动**（判据不可实施）；`N2` 仅注入了 `RoadSectionLine` 侧 `RD_CD`，`M1a` 仍 `ABSENT` ⇒ `M2` 不翻转 |
| **修订** | `N3` → **键「层级」切换**（代码级 `RD_CD` vs 道路名级 `RD_CD_DESC↔RD_NAM`），语义等价且**可实施**；`N2` → 改为**双侧注入**（忠实模拟"属性完整版到手"） |
| **影响面** | **仅负例实现**。主路径判据 / 阈值（`filled>0` / `atol=1e-4`）/ M 门定义 / 采集目标 / 门数（9）/ 冻结边界**全部未改** |
| **性质** | **仪器层缺陷，不是科学结论**；已按项目纪律披露 |

### `N1`–`N5` 复核

5 个负例**全部** `fired=True` ∧ `hit_designed_observable=True`（见 §3 表）⇒ 判定**可证伪**。

### 未登记风险（保持）

- `TrafficFlow_Links` **无 `*.shp.xml`** ⇒ 该图层**无官方 schema 自证源**，其 schema 只能取自 API 文档 + 实际字段（本节点未对其做三方对账）。
- 本节点**未**验证 `Junction ID ↔ TrafficFlow.LinkID` 的可连接性（**前置：On-Request 数据到手**）。

---

## §9 下一步（**待用户裁定，本节点不擅自启动**）

### 采集目标（两层，优先级冻结）

**第一优先 —— 属性完整版 `DetectorLoop`（LTA 公开 geospatial）**
- 恢复目标：官方 10 个非几何字段（`JOB_NUM` / `TYP_CD` / `LVL_NUM` / `EXCEPTION_IND` / `LAST_UPD_*` / `CRT_*` / `RD_CD` / `PKG_REF` / `SHAPE_*`）
- ⛔ **须事先声明期望**：**即使成功也不含 `DETECTOR_ID`** ⇒ 只能把链接提升到 **`RD_CD` 道路码级**。

**第二优先 —— On-Request `Indicative Traffic Counts at Junctions by Loop Detectors`**
- 目标字段：`Junction ID` · `Detector ID` · `Date and time` · `Indicative traffic counts`（Daily）
- **★这是 `Detector ID` 的唯一可能来源**
- ⛔ **不得先假定它能与 `TrafficFlow.LinkID` 一一连接**：可连接性**必须等字段到手后实测**

### 建议的 M 门重评顺序（数据到手后，仍零仿真）

```
① M1a  RD_CD 是否恢复（DetectorLoop 属性版）
② M1b  DETECTOR_ID 是否可取得（On-Request）
③ M2   Detector → RoadSection/LinkID 是否可连接   ← 最关键
④ M3   Direction / Lane 是否可恢复
⑤ M4   F_LOW 9 节设施级对象闭合
     F_LOW → 观测设施是什么？→ 观测方向是什么？→ 观测覆盖几条 lane？
           → 对应 MATSim 哪个对象？→ Sim/Obs 是否仍异常？
```

**⇒ 只有 ①–④ 全通，O3 才算真正闭合；在此之前 `B` 保持 `BINDING_UNDECIDABLE`，`F_LOW` 保持"未解释"。**

---

**状态更新**：`O3 ✓ → READY(O3-METADATA) → METADATA_GAP_QUANTIFIED`（9/9 门 + 5/5 负例）
**如需推进**：请提供 LTA DataMall **AccountKey**（用于 geospatial 属性版重取），或授权申请 On-Request 数据集。
