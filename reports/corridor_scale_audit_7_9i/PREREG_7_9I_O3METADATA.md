# PREREG_7_9I_O3METADATA.md — Step 7.9I-O3-METADATA「恢复 TrafficFlow → Detector / 道路设施 可连接身份链」预注册

> **本文件在引擎运行前冻结。** 运行后只允许追加"执行结果"章节，判据/阈值/门数/负例不得改。
> 上一节点状态：`7.9I_FROZEN_CLOSED → … → D2-review ✓ → O3 ✓`
> 本节点状态：**`O3 ✓ → READY(O3-METADATA)`**
> 冻结时间：2026-10-01 · 用户裁定原文："先补元数据，不改模型、不改评价器、不跑仿真。"

---

## 1. 正式问题

> **恢复 LTA `TrafficFlow` → `Detector` / 道路设施 的可连接身份链。**

O3 已确证（不重复验证，直接引用为输入事实）：

| 事实 | O3 实测值 |
|---|---|
| 观测对象结构层 | `TrafficFlow_Links` 1,278/1,278 **全 2 顶点**、长度 p50 **128 m**、有向 `LinkID`、同路名 obs 唯一率 p50 **1.0000** |
| 设施归属层 | ⛔ `OBS_OBJECT_UNRESOLVED` |
| 跨层基数 | `1 LTA LinkID ↔ K MATSim primary 边`，`K` 1–14（`K_pooled` 5.5434） |
| 缺口性质 | `DATA_ACQUISITION_GAP`：**不是「LTA 没有元数据」，而是「本批未取得」** |

**⇒ 本节点只做一件事：把"缺什么、缺到哪一层、哪条来源可能补上"钉死，并冻结验收门。**
**⛔ 不改模型、不改评价器、不跑 MATSim、不做任何几何替代。**

---

## 2. 本节点新增的权威证据（运行前已确证，作为判据输入）

### 2.1 官方 GDM schema（来源 = 交付包内 FGDC 元数据 `*.shp.xml`，LTA 侧自证）

`DetectorLoop.shp.xml` 逐字载明源库导出字段映射（`GDM.LTALayers\GDM.DetectorLoop`）：

```
JOB_NUM 'Job No' 20 Text | TYP_CD 'Type of Feature' 4 Text | LVL_NUM 'Level of Road' 2 Short
EXCEPTION_IND 'Exception Indicator' 1 Text | LAST_UPD_USRID_NUM 8 Text | LAST_UPD_DTTM Date
CRT_USRID_NUM 8 Text | CRT_DTTM Date | RD_CD 'RD_CD' 6 Text | PKG_REF 50 Text
SHAPE_Length Double | SHAPE_Area Double
```

要素定义（官方英文原文）：
> *"A symbolic polygon representation of an electronic loop on the road surface at **signalised junctions**, to detect **traffic movements** for **traffic control** purpose"*

`RoadSectionLine.shp.xml` 逐字载明源库 schema（`GDM.RoadSectionLine` / `GDM.ROADSECTIONLINETEMP`）：

```
JOB_NUM 'Job No' 20 Text | RD_CD 'Road Code' 6 Text | RD_NAM 'Road Name' 150 Text
RD_CATG_NAM 'Road Category' 20 Text | EXCEPTION_IND 1 Text | LAST_UPD_USRID_NUM 8 Text
LAST_UPD_DTTM Date | CRT_USRID_NUM 8 Text | CRT_DTTM Date | PKG_REF 50 Text | SHAPE.LEN Double
```

**★关键**：`DetectorLoop` 官方 schema **不含 `DETECTOR_ID`，也不含 `LANE_NUM`**；唯一道路关联键 = **`RD_CD`（Road Code）**，且被 domain 绑定到 `roadname`。

### 2.2 LTA On-Request 官方口径（来源 = `on-request_datasets.html`，本次联网逐字抓取）

**`Indicative Traffic Counts at Junctions by Loop Detectors`**
> *"Indicative traffic counts captured by each loop detector installed at **signalised intersections**, **without vehicle classification counts**"*

字段：`Junction ID` · `Detector ID` · `Date and time for each collection period` · `Indicative traffic counts`
频率：**Daily** ｜ 格式：`XLS/CSV/TXT`

**★与 2.1 的要素定义完全同域**（同是 *signalised junction* 上的 *loop detector*，同服务于 *traffic control*）⇒ 两者是**同一套设施的两个视角**：`DetectorLoop` = 几何（polygon），On-Request = 计数（`Detector ID` + `Junction ID` + count）。
**⇒ `Detector ID` 的唯一可能来源是 On-Request，不是 geospatial 层。**

（旁证，冻结不动）On-Request 另有 `Traffic Lights Traffic Plans`（`Junction ID` + `traffic signal phase timing`），与已登记的 `SIGNAL_MECHANISM_ABSENT` 同域，本节点**不取用**。

### 2.3 LTA 官方 API 文档（本地 `docs/LTA_DataMall_API_User_Guide.md`）

- L1029：`Traffic Flow` → *"Returns hourly average traffic flow, taken from a representative month of every quarter during 0700-0900 hours."*
- L1394：Geospatial Whole Island 第 8 层 = `Detector Loop` → `DetectorLoop`

---

## 3. 冻结的四条零仿真门（用户裁定原文）

```text
M1  DetectorID 是否恢复
M2  Detector → RoadSection / LinkID 是否可连接   ← 最重要
M3  Direction / Lane 是否可恢复
M4  F_LOW 9节是否能完成设施级对象闭合
```

**★精化（运行前冻结，理由见 §2.1）**：M1 必须拆为两支，因为两支的**数据来源不同、代价完全不同**：

| 门 | 判据 | 可判定来源 |
|---|---|---|
| **M1a** | `RD_CD`（Road Code）在 `DetectorLoop` 侧是否恢复（字段存在 ∧ 填充率 > 0） | LTA 公开 geospatial（属性完整版） |
| **M1b** | `DETECTOR_ID` 是否可取得 | **仅** On-Request Junction Loop Counts |
| **M2** | `Detector → RoadSection / LinkID` 是否能建立（道路码级 / 路段级 / 链路级 三档分列） | 依赖 M1a |
| **M3** | `Direction` / `Lane` 是否可恢复 | 依赖是否存在 lane / direction 字段来源 |
| **M4** | `F_LOW` 9 节（`Σobs` 20,141 / 占 D 类 71.02%）能否完成设施级对象闭合 | 依赖 M1a+M1b+M3 |

**状态取值域**：`PRESENT` / `ABSENT` / `BLOCKED`（上游依赖未过）/ `UNRESOLVED`（有字段但语义不可判）
**⛔ 严禁第四种取值**：不得以几何邻近把 `ABSENT` 改写成 `PRESENT`（与 `TWIN_GEOMETRIC_SUBSTITUTE` 同纪律）。

### 3.1 硬门（引擎必须全部通过）

| 门 | 判据（实测值必须随门输出） |
|---|---|
| `G-M1` | 官方 schema 解析成功：`DetectorLoop` = **12** 字段、`RoadSectionLine` = **11** 字段（逐字来自 `*.shp.xml` 的 FGDC 映射串；★并集口径见 §3.3 更正，`RoadSectionLine` = **12**） |
| `G-M2` | 交付字段枚举成功：`DetectorLoop` = `{OBJECTID}`、`RoadSectionLine` = `{RD_CD, RD_CATG_NA, RD_CATG__1, RD_CD_DESC}` |
| `G-M3` | 填充率：`RD_CD` = **0.0000**、`RD_CATG_NA` = **0.0000**、`RD_CATG__1` = **1.0000**、`RD_CD_DESC` = **1.0000**（`atol=1e-4`） |
| `G-M4` | 文档 ≠ 官方：`DetectorLoop` 文档独有 = **`{LANE_NUM, DETECTOR_ID}`**（**2 个，官方 schema 中不存在**）、官方独有 = **10** 个非几何字段（★`REMARKS` 已移出，见 §3.3 更正） |
| `G-M5` | 连接键可用性：`RD_CD` **两侧均不可用**；`RD_NAM ↔ RD_CD_DESC` **道路名级可用** |
| `G-M6` | 双获取路径一致：`Static` 原件 与 `Dynamic` 重下 zip 的 `DetectorLoop` 字段集**全等** = `{OBJECTID}` |
| `G-M7` | M 门状态机：`M1a=ABSENT · M1b=ABSENT · M2=BLOCKED · M3=BLOCKED · M4=BLOCKED` |
| `G-M8` | 负例 **N1–N5** 全部 `fired=True` |
| `G-M9` | AST 自检：无随机源、无时间依赖 |

### 3.2 负例契约（必须真改变结果、非同构、签名含可观测量）

| 负例 | 扰动 | 必须翻转的可观测量 |
|---|---|---|
| `N1` | 向 `DetectorLoop` 交付字段注入伪造 `DETECTOR_ID` 列 | `M1b`: `ABSENT → PRESENT` |
| `N2` | 向 `RoadSectionLine` 注入非空 `RD_CD`（填充率 1.0） | `M2`: `BLOCKED → EVALUABLE`、`M1a`: `ABSENT → PRESENT` |
| `N3` | 键选择切到 `RD_CATG__1`（100% 填充） | 连接键可用性 `FALSE → TRUE`（证明键选择有区分度） |
| `N4` | 官方 schema 源从 `*.shp.xml` 切到 `*.dbf` | 官方字段数 `12 → 1`（证明 schema 源选择有区分度） |
| `N5` | 注入伪造 `LANE_NUM`（`F_LOW` 侧） | `M3`: `BLOCKED → PRESENT` |

**负例签名 `sig` 必含**：`Σ官方字段数` · `Σ交付字段数` · `Σ填充率` · `M1a/M1b/M2/M3/M4` 状态码之和 · 连接键布尔。**⛔ 签名不含可观测量者 = 空扰动假阴性，门必挂。**

---

## 4. 采集目标（两层，优先级冻结）

### 第一优先：属性完整版 `DetectorLoop`（LTA 公开 geospatial）
- 目标：恢复 `JOB_NUM / TYP_CD / LVL_NUM / EXCEPTION_IND / LAST_UPD_* / CRT_* / RD_CD / PKG_REF / SHAPE_Length / SHAPE_Area`
- **★须事先声明期望**：**即使成功，本层也不含 `DETECTOR_ID`**（官方 schema 无此字段）⇒ 只能把链接提升到 **`RD_CD`（道路码）级**，不是检测器级、更不是链路级。

### 第二优先：On-Request `Indicative Traffic Counts at Junctions by Loop Detectors`
- 目标字段：`Junction ID` · `Detector ID` · `Date and time` · `Indicative traffic counts`（Daily）
- **★这是 `Detector ID` 的唯一可能来源**，也是把"几何线圈"提升到"真实检测器 + 真实 Junction + 真实采集时间 + 真实计数"的唯一路径。
- **⛔ 不得先假定它能与 `TrafficFlow.LinkID` 一一连接**：`Junction ID ↔ LinkID` 的可连接性**必须等字段到手后实测**（本节点不预设）。

---

## 5. 冻结边界（用户裁定原文，本节点及后续节点不得越界）

1. **`B = BINDING_UNDECIDABLE`**：metadata 拿到以前**不升级**（O3 的 3 节 `B` 保持原状）。
2. **`TWIN_GEOMETRIC_SUBSTITUTE` 继续只是几何证据**，不构成身份证据。
3. **`F_LOW` 继续不是"需求不足"**（9 节 / `Σobs` 20,141 / 71.02% 的缺口性质未被本节点重新裁定）。
4. **v1.0 继续冻结**；`SCALE=2.29897` / `N_sim=236,044` / `target=0.8589732` 不动。
5. **`signals` / `trafficDynamics` / `speedFactor` 不碰。**
6. **不改模型、不改评价器、不跑 MATSim。**
7. **⛔ 缺元数据不得以几何邻近替代**；拿到前一律 `UNRESOLVED` / `ABSENT` / `BLOCKED`。

---

## 6. 交付物

| 文件 | 内容 |
|---|---|
| `PREREG_7_9I_O3METADATA.md` | 本文件（运行前冻结） |
| `scripts/od/audit_o3_metadata_7_9io3m.py` | 零仿真审计引擎 |
| `reports/corridor_scale_audit_7_9i/o3m_schema_reconciliation.csv` | 三方对账（官方 GDM / 实际交付 / 本地文档）逐字段 |
| `reports/corridor_scale_audit_7_9i/o3m_field_fill.csv` | 每图层每字段填充率 |
| `reports/corridor_scale_audit_7_9i/o3m_m_gates.json` | M1–M4 状态 + 硬门 + 负例 + 采集目标 |
| `reports/corridor_scale_audit_7_9i/STEP7_9I_O3METADATA_REPORT.md` | 正式报告 |

---

## 7. 判读纪律

1. `M1b = ABSENT` 只读「**本批公开层无此字段**」，⛔ **不读「LTA 无检测器身份」**。
2. `M1a = ABSENT` 只读「**本批 `RD_CD` 被剥空**」，⛔ **不读「道路码不可得」**。
3. `M2/M3/M4 = BLOCKED` 只读「**上游依赖未满足**」，⛔ **不读「不可连接」**（= 把 BLOCKED 误读为阴性结论，违反「假门禁」纪律）。
4. 文档声明与官方 schema 冲突时，**以官方 schema 为准**；**仅当 FGDC 映射串 ∪ `AddField` 语句两处均无**才可登记为 `DOC_FABRICATED_FIELDS`，⛔ 不得作为采集目标。
5. 本节点**不产生**任何关于 `F_LOW` 成因的新结论；只更新「缺什么、从哪补」。
6. 覆盖率/基数必同报：`DetectorLoop` 16,275 要素 · `RoadSectionLine` 15,329 要素（交付）vs 15,313（文档声称）。

### 3.3 ★更正（2026-10-01，由 7.9I-O3-DATA-RECOVERY §0 正式更正）

**原判定**：`REMARKS`（`DetectorLoop` 1 处、`RoadSectionLine` 1 处）登记为臆造。

**更正**：官方 schema 自证源**不止 FGDC 映射串一种写法** —— 还有源库变更日志里的 **`AddField` 语句**；**权威 schema = FGDC ∪ `AddField`**。

| 图层 | `AddField` | 更正后 |
|---|---|---|
| `RoadSectionLine` | ✅ `AddField … REMARKS TEXT # # 200 …`（Date=20140801） | **真实源字段** ⇒ 改入 **`SOURCE_ONLY_STRIPPED`**；官方并集 **11 → 12** |
| `DetectorLoop` | ⛔ 无 | 降级 **`UNCONFIRMED_IN_SOURCE`**（⛔ 不得再称「臆造」） |

**未受影响**：`DETECTOR_ID` / `LANE_NUM` **仍是文档独有**。
**连带修正**：`G-M1` 并集口径、`G-M4` 文档独有由 3 个改为 **2** 个。

---

**冻结完成。以下为引擎执行结果（运行后追加，不改上文）。**
