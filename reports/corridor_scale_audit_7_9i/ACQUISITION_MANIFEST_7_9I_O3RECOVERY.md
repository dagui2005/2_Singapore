# 采集清单 — Step 7.9I-O3-DATA-RECOVERY

> **状态**：`D2-review ✓ → O3 ✓ → O3-METADATA ✓ → READY(O3-DATA-RECOVERY)`
> **当前判决**：`status = BLOCKED` · `verdict = O3_RECOVERY_AWAITING_INPUT`（硬门 **12/12**、负例 **6/6**、`EXIT = 0`）
> **本清单用途**：告诉你在**本地**取回哪两个文件、放到哪里、如何自检；**Agent 不需要知道你的 `AccountKey`**。
> **时效提醒**：S3 预签名链接**有有效期**（本批 `GeospatialWholeIsland_Links.json` 里的链接已失效），必须**用你自己的凭据重新请求 API**。

---

## 0. 一句话任务

**取回「属性完整版」的 `DetectorLoop` 与 `RoadSectionLine` 两个 shapefile**（**两个都要**），放到
`D:\Luan\2026-05\2_Singapore\recovery_7_9io3r\`，然后跑一次自检脚本。

---

## 1. 为什么是这两个（而不是别的）

O3-METADATA 已证明：**问题不是 LTA 没有观测设施语义，而是当前交付文件把关键连接属性剥掉了**。

- 交付的 `DetectorLoop.dbf` **只剩 `OBJECTID` 一列**（16,275 条记录全是空壳）；
- 交付的 `RoadSectionLine.dbf` **`RD_CD` 填充率 0% / 15,329**；
- ⇒ **链路 `Risk` 断在「② `RD_CD`」这一跳**，与几何无关。

要恢复的是这条**五跳链**（逐跳独立判定、不得跳级）：

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

⛔ **注意（这是 O3-METADATA 的正式结论，不要走回头路）**：
旧链 `DetectorLoop → DETECTOR_ID → TrafficFlow` **已被证伪** —— `DETECTOR_ID` / `LANE_NUM` **从来不在 LTA 公开 geospatial schema 里**（本地文档臆造）。
所以**不要期待**属性完整版 `DetectorLoop` 里会有 `DETECTOR_ID`；它最多带你到 **`RD_CD` 道路码级**。
**检测器身份（`Detector ID`）只能来自 On-Request 数据**（见 §4）。

---

## 2. 主要采集目标（第一优先）

| # | 图层 | 端点 | 参数 |
|---|---|---|---|
| 1 | **`RoadSectionLine`** | `GET https://datamall2.mytransport.sg/ltaodataservice/GeospatialWholeIsland` | `ID=RoadSectionLine` |
| 2 | **`DetectorLoop`** | `GET https://datamall2.mytransport.sg/ltaodataservice/GeospatialWholeIsland` | `ID=DetectorLoop` |

**请求头**：`AccountKey: <你的 DataMall 凭据>` · `accept: application/json`

**返回**：`{"value":[{"Link":"https://dmgeospatial.s3.../xxx.zip?X-Amz-..."}]}` ⇒ 下载该 `Link` 指向的 zip（内含 `*.shp/.shx/.dbf/.prj/.shp.xml`）。

### ⚠️⚠️ 最容易踩的坑（务必先看）

本项目自带的下载脚本 `scripts/lta_dynamic_data_downloader.py` 在 `download_geospatial_layers()` 里有这段逻辑：

```python
save_path = os.path.join(geospatial_dir, f"{layer_id}.zip")
if os.path.exists(save_path):
    logger.info("    ⊘ 文件已存在，跳过")     # ← 直接重跑不会刷新！
    continue
```

**⇒ 直接重跑脚本，会拿到旧的那份空壳 zip。**
**⇒ 必须先删除或改名**下面这些旧文件，再去请求：

```text
Dynamic_2026_03_16/historical_data/geospatial/DetectorLoop.zip
Dynamic_2026_03_16/historical_data/geospatial/RoadSectionLine.zip
Static_ 2026_03/GEOSPATIAL/DetectorLoop_Mar2026/        (整个目录改名，如加后缀 _old)
Static_ 2026_03/GEOSPATIAL/RoadSectionLine_Mar2026/     (同上)
```

> ⛔ **但不要删除/覆盖交付原件的备份**：本步只需要「新取一份」，旧件保持不动即可（引擎对基线只读）。

---

## 3. 放哪里（声明路径，优先命中）

把解压后的文件按下表放置（**放 zip 也行，脚本会找 `*.dbf`**）：

| 逻辑输入 | **声明路径（优先）** | 可接受的回退位置 |
|---|---|---|
| `DetectorLoop` | `recovery_7_9io3r/DetectorLoop/DetectorLoop.dbf` | `recovery_7_9io3r/DetectorLoop.dbf` · `recovery_7_9io3r/DetectorLoop/*.dbf` · `uploads/**/DetectorLoop*.dbf` |
| `RoadSectionLine` | `recovery_7_9io3r/RoadSectionLine/RoadSectionLine.dbf` | `recovery_7_9io3r/RoadSectionLine.dbf` · `recovery_7_9io3r/RoadSectionLine/*.dbf` · `uploads/**/RoadSectionLine*.dbf` |

即：**只需保证 `recovery_7_9io3r/<图层名>/<图层名>.dbf` 存在**（`.shx/.prj/.shp/.shp.xml` 同目录更好，可一并保留）。
所有候选的尝试痕迹会写入 `reports/corridor_scale_audit_7_9i/o3r_input_resolution.json`。

---

## 4. 第二优先（On-Request，**独立交叉验证**，非替代 Geospatial）

> 用户原话：**「这一层不能预设一定能连上」**。

| 项 | 内容 |
|---|---|
| 数据集 | **`Indicative Traffic Counts at Junctions by Loop Detectors`** |
| 官方描述 | *"…captured by each loop detector installed at **signalised intersections**, **without vehicle classification counts**"* |
| 目标字段 | `Junction ID` · `Detector ID` · `Date and time for each collection period` · `Indicative traffic counts` |
| 频率 | **Daily** |
| 格式 | `XLS / CSV / TXT` |
| 放置位置 | `recovery_7_9io3r/junction_loop_counts/*.csv`（或 `.json`） |

**拿到后要检验的**：`Detector ID → Junction → Road/Direction → TrafficFlow LinkID` **是否真的存在稳定的连接关系**。
⛔ **不得预设一定能连上**；⛔ 这一层是**独立交叉验证**，不是 Geospatial 的替代品。
⛔ **`Detector ID` 的唯一来源就是这里**，公开 geospatial 层里没有。

---

## 5. 期望字段（官方 GDM schema = FGDC 映射串 ∪ `AddField` 语句）

> 方法学更正（本步 §0）：官方 schema 自证源**不止 FGDC 映射串一种写法**，还有源库变更日志里的 **`AddField` 语句** ⇒ **权威 schema = 两者并集**。

### `DetectorLoop` — 期望 **12** 字段

`OBJECTID` · `SHAPE` · `JOB_NUM` · `TYP_CD` · `LVL_NUM` · `EXCEPTION_IND` ·
`LAST_UPD_USRID_NUM` · `LAST_UPD_DTTM` · `CRT_USRID_NUM` · `CRT_DTTM` · **`RD_CD`** · `PKG_REF` ·
`SHAPE_Length` · `SHAPE_Area`

> ⛔ **不会有** `DETECTOR_ID` / `LANE_NUM` —— 这两个字段**不在** LTA 官方 schema 里。

### `RoadSectionLine` — 期望 **12** 字段（FGDC 11 ∪ `AddField{REMARKS}`）

`OBJECTID` · `SHAPE` · `JOB_NUM` · **`RD_CD`**（Road Code, 6） · **`RD_NAM`**（Road Name, 150） ·
`RD_CATG_NAM`（20） · `EXCEPTION_IND` · `LAST_UPD_USRID_NUM` · `LAST_UPD_DTTM` ·
`CRT_USRID_NUM` · `CRT_DTTM` · `PKG_REF` · `SHAPE_LEN` · **`REMARKS`**（Date=20140801）

> ★`REMARKS` 是本步新确认的**真实源字段**（此前被误登记为「臆造」，已更正为 `SOURCE_ONLY_STRIPPED`）。

---

## 6. 拿到后怎么自检（**先自检，再交给主引擎**）

```bash
C:/Users/LQP/miniconda3/python.exe scripts/od/check_o3_recovery_inputs_7_9io3r.py
```

它会打印：**记录数 / 字段清单 / 关键字段填充率 / 与官方 schema 的差集 / 能力门预判**。

**关键看点**（⛔ 不达标的字段会直接决定判决，别跳过）：

| 看点 | 合格线 | 若不达标 |
|---|---|---|
| `RoadSectionLine.RD_CD` **填充率** | ≥ `MIN_FILL = 1%` | `M1a = ABSENT` ⇒ `RECOVERY_INCOMPLETE_FIELD_MISSING` |
| `DetectorLoop.RD_CD` **填充率** | > 0 | ⇒ `M2 = BLOCKED` ⇒ `RECOVERY_FIELDS_PRESENT_LINKAGE_BLOCKED` |
| 双侧 `RD_CD` **交集 ≠ ∅** | 非空 | 同上 |

**★运行前已掌握的否定性先验（请作好心理准备，这不代表失败）**：

- `RD_CD` 在 **3 个独立图层**近全空（`RoadSectionLine` 0/15,329 · `CyclingPath` 0/4,830 · `LampPost` **61/126,916 = 0.048%**）
  ⇒ 存在一种可能：**不是交付剥离，而是源库本身未赋值**。
- `LampPost` 那 61 条非空 `RD_CD` **全部 6 字符**、去重只有 **6 个**（`ZZ190A` `ZZ202A` `ZZ161A` `ZZZ43A` `ZZ203A` `PUP06M`）
  ⇒ 格式与官方 `RD_CD(Road Code,6)` 吻合，但形如**内部占位码** ⇒ **可能不是可用的道路码体系**。

⇒ **所以：先实测填充率，再谈连接。** ⛔ 不得因「拿到了官方 schema 声明的字段」就宣布「连接链已恢复」。

---

## 7. 自检通过后，交给主引擎

```bash
C:/Users/LQP/miniconda3/python.exe scripts/od/audit_o3_recovery_7_9io3r.py
```

**主引擎会自动完成（全部零仿真、不跑 MATSim）**：

1. 逐层统计 `①→② / ②→③ / ③→④ / ④→⑤` 的 **1:1 / 1:N / N:1 / N:M** + 覆盖率 + `K_pooled`；
2. 判定**方向是否可恢复**（`direction_recoverable`）与**车道是否可恢复**（`lane_recoverable`）；
3. `F_LOW 9` 节逐节闭环（4 条件：`LinkID→路` / `路→检测器` / `唯一设施身份` / `方向可归属`）；
4. `B = BINDING_UNDECIDABLE` 能否升级为 `EVALUABLE`（**仅当 `M1a ∧ M1b ∧ M2` 且该节 4 条件全真**）；
5. 门禁 `G-O3R-1`–`G-O3R-12` + 负例 `N1–N6`。

判决空间：

```text
M1a/M1b 缺失         -> RECOVERY_INCOMPLETE_FIELD_MISSING
M2 = BLOCKED         -> RECOVERY_FIELDS_PRESENT_LINKAGE_BLOCKED
M2 = EVALUABLE 且 M4 >= 0.50 -> RECOVERY_STAGE_1_CLOSED
M2 = EVALUABLE 且 M4 <  0.50 -> RECOVERY_PARTIAL_CLOSURE
```

---

## 8. 绝对不要做的事

| ⛔ | 说明 |
|---|---|
| **不要在聊天里发 `AccountKey`** | 你在本地自取即可；Agent 拿到**文件**就能继续，**不需要知道凭据本身** |
| ⛔ 不要改 v1.0 | `SCALE=2.29897` / `N_sim=236,044` / `target=0.8589732` 全部冻结 |
| ⛔ 不要改 `TrafficFlow` 原始值 | 含 `Volume` 千分位字符串 |
| ⛔ 不要改 crosswalk | |
| ⛔ 不要改评价器阈值 | |
| ⛔ 不要跑 MATSim | 本步**零仿真**；拿到文件后也**先不跑仿真** |
| ⛔ 不要碰 `signals` / `trafficDynamics` / `speedFactor` | |
| ⛔ 不要用几何邻近替代设施身份 | 承 `TWIN_GEOMETRIC_SUBSTITUTE` 纪律 |
| ⛔ 不要预设 `Junction ID ↔ LinkID` 可连接 | 必须实测 |

**读法纪律**：`BLOCKED` 只读「**上游依赖未满足**」，⛔ **不读「不可连接」**；`ABSENT` 只读「**本批无此字段**」，⛔ **不读「LTA 无检测器身份」**。

---

## 9. 最终目标（这一刀是为了回答什么）

**那 `20,141 veh/h` 的「异常」**（`F_LOW` 9 节之和，占靶场匹配承载里程 `6.64%`），
**到底对应的是哪个现实检测对象**。

这才是下一轮**决定是否修改 MATSim 路网或动力学**的真正入口。

---

**关联文件**
- 预注册：`reports/corridor_scale_audit_7_9i/PREREG_7_9I_O3RECOVERY.md`
- 引擎：`scripts/od/audit_o3_recovery_7_9io3r.py` · 自检：`scripts/od/check_o3_recovery_inputs_7_9io3r.py`
- 报告：`reports/corridor_scale_audit_7_9i/STEP7_9I_O3RECOVERY_REPORT.md`
- 输入解析痕迹：`reports/corridor_scale_audit_7_9i/o3r_input_resolution.json`
