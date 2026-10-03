# PREREG · Step 7.9I-O3 —— 「LTA 观测对象语义审计」（OBS-DOMAIN）预注册（运行前冻结）

> 冻结时间：2026-09-30（用户裁定 `7.9I_FROZEN_CLOSED → O1 ✓ → O1-续 ✓ → O1-续② ✓ → D-path ✓ → D2-review ✓ → READY(O3-OBS-DOMAIN)`）
> 冻结件版本：`PREREG_7_9I_O3.md` v1（**本文件在任何计算执行前写完**）
> 范围：主集 = **9 个 `F_LOW` 断面**（D-path 第二轴 `carry_scaled < 0.50`，Σobs **20,141.0 / 71.02%**）；参照集 = **5 个 `F_ADQ` 断面**；基线 = **全域观测域**（1,311 obs LinkID / 1,278 有几何）
> 底线：⛔ 不改 v1.0 ⛔ 不跑 MATSim ⛔ 不碰 `signals` ⛔ 不碰 `trafficDynamics` ⛔ 不碰 `speedFactor` ⛔ 不产生 v1.1

---

## 1. 正式问题（用户 2026-09-30 裁定）

⛔ **本刀不再问**「哪条 MATSim edge 应该承接这些车？」（该问法已被 D-path / D2-review 收敛为阴性结果）
✅ **本刀改问**：
> **LTA 的这个数，到底在现实世界中测量了什么？**

**官方依据（用户引用，且本地 `docs/LTA_DataMall_API_User_Guide.md` L1029 逐字确证）**：
> TrafficFlow —— *"Returns **hourly average traffic flow**, taken from a **representative month of every quarter** during **0700-0900 hours**."*（Update Freq: Quarterly）

⇒ 必须把三个概念**彻底分开**：
```text
Traffic Flow  ≠  Detector Loop  ≠  Traffic Count / Turning Movement
```
⇒ 官方资料**并未**证明：「一个 LinkID / Traffic Flow section = MATSim 中的一条物理车行道」。

### 1.1 O3 第一阶段只查 9 个 `F_LOW` 断面

这 9 节当前状态：**找得到同向候选，但没有任何候选达到 `carry_scaled ≥ 0.50`**（D2-review `F_ADQ = 0/6` 诸节口径一致）。
⇒ 再问「车在哪条 MATSim edge 上」已非最佳问题；先问「**观测值是什么对象的计数**」。

`F_LOW` 9 节（`o1e_d2rev_cards_7_9id2.csv` ∩ D-path `carry_class == F_LOW`）：

| # | section_id | RoadName | RoadCat | obs_8_9 | K（primary MATSim 边） |
|---|---|---|---|---|---|
| 1 | 48461 | AYER RAJAH EXPRESSWAY | CATA | 4,118.0 | 1 |
| 2 | 49054 | AYER RAJAH EXPRESSWAY | CATA | 3,481.5 | 1 |
| 3 | 49104 | AYER RAJAH EXPRESSWAY | CATA | 2,896.0 | 2 |
| 4 | 48586 | AYER RAJAH EXPRESSWAY | CATA | 2,532.0 | 4 |
| 5 | 48708 | AYER RAJAH EXPRESSWAY | CATA | 2,393.5 | 3 |
| 6 | 48337 | AYER RAJAH EXPRESSWAY | CATA | 2,052.5 | 3 |
| 7 | 47163 | AYER RAJAH EXPRESSWAY | SLIP_ROAD | 1,967.0 | 5 |
| 8 | 49027 | AYER RAJAH EXPRESSWAY | SLIP_ROAD | 581.5 | 5 |
| 9 | 172382 | EAST COAST PARK SERVICE ROAD | SLIP_ROAD | 119.0 | 14 |
| | **Σ** | | | **20,141.0** | |

> ★结构信号（运行前登记，**不预设结论**）：9 节中 **8 节在 AYER RAJAH EXPRESSWAY（AYE）**，1 节在 ECP 服务道路。

### 1.2 O3 要查的四个事实（用户指定）

| # | 问题 | 关键检索项 |
|---|---|---|
| **①** | 观测对象到底是「单车行道」还是「道路断面/设施」 | detector ID / junction ID / link-road section ID / detector loop↔turning count 对应 / 单方向 / 双方向设施 |
| **②** | 是否存在「一个观测对象覆盖多个实际承载对象」 | LTA section → 1 detector? 多 detector? 一方向? 双向? 多 lane? junction movement? |
| **③** | `Volume` 是「通过该对象的流量」还是某种道路级统计量 | Volume → physical counting object → direction → road facility |
| **④** | **最后**才回到 MATSim（本刀**不做** ④） | — |

### 1.3 正式输出：逐断面 **Observation Object Card**（用户指定，**不要只给占比**）

```text
section_id / road_name / road_cat / obs_8_9
n_vertices / len_m / bearing
opp_obs_id / opp_perp_m / opp_obs89 / opp_same_road
sib_n / sib_obs_nunique / sib_uniq_frac
det_min_m / det_n_100
K_primary / highway / direction_ok_frac
n_h8_wd / vol_int_frac / vol_cv / obs_h7
facility_binding / final_class / confidence
```

### 1.4 `OBS_OBJECT_UNRESOLVED` 规则（用户指定，**硬约束**）

> 「这一步如果没有官方元数据，就只能标成：**`OBS_OBJECT_UNRESOLVED`**，不能继续猜。」

⇒ 凡涉及「观测对象 ↔ 物理设施对象」的绑定，**缺元数据时一律标 `OBS_OBJECT_UNRESOLVED`**；
⛔ **不得以几何邻近替代**（与 `TWIN_GEOMETRIC_SUBSTITUTE` **同一纪律**）。

---

## 2. 口径（运行前冻结，⛔ 不得改）

### 2.1 数据资产实况（★首次在正式产物中登记「文档 ≠ 数据」）

全部为 **LTA 官方随数据发布的本地文档**（`docs/LTA_DataMall_API_User_Guide.md` / `Static_ 2026_03/DATA_DOCUMENTATION.md` / `Dynamic_2026_03_16/DATA_README.md` / `DATA_DICTIONARY.md`）与**实际下载文件**对照：

| 表 | 实际字段（本刀实测） | 本地文档声称 | 差异 |
|---|---|---|---|
| `TrafficFlow_Links.dbf`（WGS84） | `LinkID, RoadName, RoadCat, StartLon, StartLat, EndLon, EndLat`（7） | — | — |
| `TrafficFlow_Data.json` | `LinkID, Date, HourOfDate, Volume, StartLon, StartLat, EndLon, EndLat, RoadName, RoadCat`（10） | `LinkID, **VehicleType**, Volume, **Timestamp**` | ⚠ **`VehicleType` / `Timestamp` 不存在**；实际为 `Date/HourOfDate/RoadCat` |
| `DetectorLoop.dbf`（SVY21） | **`OBJECTID`（1）** | `OBJECTID, SHAPE, JOB_NUM, RD_CD, **LANE_NUM**, **DETECTOR_ID**, REMARKS` | ⚠ **`DETECTOR_ID` / `RD_CD` / `LANE_NUM` 全部缺失**；★`REMARKS` 条目见下方更正 |
| `RoadSectionLine.dbf`（SVY21） | `RD_CD, RD_CATG_NA, RD_CATG__1, RD_CD_DESC`（4） | `OBJECTID, SHAPE, JOB_NUM, RD_CD, RD_CATG_NAM, …, SHAPE.LEN` | ⚠ **无 `LinkID`**；`RD_CD`/`RD_CATG_NA` **100% 空**；实际另有 `RD_CATG__1`（Category 1–5）/`RD_CD_DESC`（路名） |

> **★更正（2026-10-01，由 7.9I-O3-DATA-RECOVERY §0 正式更正）**：`REMARKS` **不是**文档臆造字段。
> `RoadSectionLine.shp.xml` 含源库变更日志 `AddField … REMARKS TEXT # # 200 …`（**Date=20140801**）⇒ 判定改为 **`SOURCE_ONLY_STRIPPED`**（真实但在交付中被剥）。
> `DetectorLoop` 侧 `REMARKS` 无 `AddField` 记录 ⇒ 降级 **`UNCONFIRMED_IN_SOURCE`**（⛔ 不得再称「臆造」）。
> **未受影响**：`DETECTOR_ID` / `LANE_NUM` **仍是文档独有**（`DetectorLoop` 官方 FGDC 12 ∪ `AddField` ∅ = 12）。

⇒ **本批下载缺少「观测对象 ↔ 物理设施」所需的全部标识字段**。这是本刀**最关键的可操作发现**，须在报告中**逐项登记**。

### 2.2 观测值口径（承接 7.3.6A / 7.9E-2，⛔ 不变）

```text
obs_8_9(section) = median{ Volume(LinkID=s, Date=d, HourOfDate=8) : d 为工作日 }
```
- `Volume` **须先去千分位逗号**（原始 JSON 为字符串，如 `"1,069"`）；⛔ 直接 `to_numeric` 会把约 0.4% 记录变 NaN。
- `HourOfDate` 全域仅 **{7, 8}**（承接 7.4.3-R「可观测窗 ≤07-09」）。
- `SCALE = 2.29897` 仅登记，**本刀不使用**。

### 2.3 坐标口径（承接 `readme §4`「坐标必须同源」）

| 层 | CRS | 用途 |
|---|---|---|
| `TrafficFlow_Links` / `TrafficFlow_Data` | **EPSG:4326（WGS84）** | 观测对象几何 |
| `DetectorLoop` / `RoadSectionLine` / `SEC_GEO_7_6C.mid_x/mid_y` | **SVY21 (EPSG:3414)** | 设施几何 / 项目断面锚点 |

⇒ 距离计算**统一投影到 SVY21**（`pyproj Transformer("EPSG:4326","EPSG:3414")`）；⛔ 不得跨系直算。
**自洽门**：`48461` 的 lon/lat → SVY21 中点须与 `section_geography.csv` 的 `mid_x/mid_y` 相距 **≤ 250 m**（实测约 60 m）。

### 2.4 三轴结构判据（★本刀新增，均为**结构判定**，须预注册）

| 轴 | 判据（实测式） | 含义 |
|---|---|---|
| **粒度** | `nv = 顶点数`；`len_m` | LTA 观测几何是否为「短有向段」 |
| **方向性** | `opp_perp_m = ` 断面**中点**到「**反向**（`|Δbearing| ≥ OPP_MIN`）观测对象**线**」的**垂距**最小值 | 是否存在独立对向观测对象 |
| **聚合性** | `sib_uniq_frac = unique(obs_8_9 within same RoadName) / n_sib`（仅当 `n_sib ≥ SIB_MIN_N`） | 观测值是否在**路级重复**（⇒ 聚合设施） |
| **设施绑定** | `det_min_m`、`det_n_100`，**以及字段实况** | 能否把观测对象绑到物理线圈 |

### 2.5 A–E 分类（★用户指定，五类**并列可证伪**）

| 类 | 常量名 | 判据（本刀**可本地执行**的版本） |
|---|---|---|
| **A** | `A_OBS_NOT_SINGLE_SEGMENT` | `nv > 2` ∨ `len_m > LEN_MAX` ⇒ 观测对象**不是**短单段 |
| **C** | `C_OBS_AGGREGATE_FACILITY` | `sib_n ≥ SIB_MIN_N` ∧ `sib_uniq_frac < AGG_MAX` ⇒ 观测值在路级重复（聚合） |
| **D** | `D_LEVEL_CARDINALITY_MISMATCH` | `K_primary > 1` ⇒ **1 观测对象 ↔ K>1 网络对象**（跨层基数不同） |
| **B** | `B_BINDING_UNDECIDABLE` | `facility_binding == UNRESOLVED` ∧ ¬A ∧ ¬C ⇒ 「是否 = 一条物理车行道」**本地不可判定** |
| **E** | `E_UNEXPLAINED` | ¬(A ∨ C ∨ D ∨ B) |

**主类优先级**：`A > C > D > B > E`（并列披露全部命中项）。
`facility_binding` 取值域：`{UNRESOLVED, RESOLVED}`；**本批预期恒为 `UNRESOLVED`**（字段缺失）⇒ 须**披露该退化**。

> ★**可证伪性来源**：`B` 的「不可判定」由负例 `N5`（**注入伪造 `DETECTOR_ID` 列并允许绑定**）反证——
> 若注入后 `facility_binding` **能**翻为 `RESOLVED`，则 `UNRESOLVED` 是**数据缺失**而非**判据无法工作**。

### 2.6 常量表（★新增者已标注）

| 常量 | 值 | 沿自 / 理由 |
|---|---|---|
| `OPP_MIN` | 150.0° | D-path（对向判据，⛔ 复用不新造） |
| `DIR_OK` | 30.0° | O1-续② / D-path（同向判据） |
| `LEN_MAX` | **500.0 m** | **本刀新增**：短段的宽松上界（实测 p50 129 m / max 201 m ⇒ 非临界） |
| `AGG_MAX` | **0.50** | **本刀新增**：路级重复判据（沿用 `CARRY_MIN=0.50` 的量纲习惯；实测值 0.98–1.00 ⇒ 非临界） |
| `SIB_MIN_N` | **3** | **本刀新增**：聚合统计最小同胞数（低于此数不判 C） |
| `DET_R` | **100.0 m** | **本刀新增**：detector 共址披露半径（另报 25/50/200 m） |
| `PERP_R` | **250.0 m** | **本刀新增**：`opp_perp_m` 搜索上界（超出记 `inf`，须披露） |
| `HOUR` | **8** | 承接 7.3.6A |
| `K_pooled` | 5.5434 | 1 断面 ↔ K 边（**必须同报**） |

> ★**新增阈值非临界声明**：`LEN_MAX / AGG_MAX / SIB_MIN_N / DET_R / PERP_R` 的实测值距离阈值均有 ≥ 2× 余量（见报告 §4），
> 因此结论**不是阈值敏感性产物**；负例 `N2/N3` 仍会**显式扰动** `AGG_MAX / DET_R` 以证明其有效。

---

## 3. 硬门与负例（运行前冻结）

### 3.1 硬门（10 项，全 PASS 才 `OBS_DOMAIN_AUDIT_READY`）

| 门 | 断言 |
|---|---|
| `G-O3-1` | **坐标同源自洽**：9 主节 lon/lat → SVY21 中点 vs `SEC_GEO_7_6C.mid_x/mid_y` 距离 ≤ **250 m**（9/9） |
| `G-O3-2` | **obs 复现**：重算 `obs_8_9` 与 `o1e_d2rev_cards_7_9id2.csv` 逐值一致（`atol=0.5`，9/9） |
| `G-O3-3` | **字段实况自检**：4 张表实际字段数与 §2.1 表**逐位一致**（7/10/1/4） |
| `G-O3-4` | **全域基线非退化**：LinkID 数、2–顶点率、`sib_uniq_frac` p50、`det` 共址率**各有 ≥2 取值** |
| `G-O3-5` | **判别量非退化**：`opp_perp_m` / `sib_uniq_frac` / `K_primary` / `len_m` **各 ≥2 取值** |
| `G-O3-6` | **卡片完备**：11+ 字段齐、无 NaN 缺失（`inf` 允许，须另列计数） |
| `G-O3-7` | **`UNRESOLVED` 可证伪**：负例 `N5`（注入伪造 `DETECTOR_ID`）须把 `facility_binding` 翻为 `RESOLVED` |
| `G-O3-8` | **A/C 可证伪**：负例 `N2`（`AGG_MAX 0.5→1.01`）与 `N6`（`nv` 口径扰动）须各改变 A 或 C 的命中数 |
| `G-O3-N` | **负例 6/6 fired**（非同构扰动、与主路径**共用同一 `compute(params)`**） |
| `G-O3-9` | **AST 自检**：无 `random` / 无网络 / 无写盘副作用（只读） |

### 3.2 负例（6 项，★全部与主路径共用 `compute`）

| # | 扰动 | 期望 |
|---|---|---|
| `N1` | `OPP_MIN 150 → 30.1`（把对向阈值降入同向带） | `opp_perp_m` 分布改变（对向对象被并入同向） |
| `N2` | `AGG_MAX 0.50 → 1.01`（聚合判据失效） | `C` 命中数改变 |
| `N3` | `project_det=False`（DetectorLoop 用 lon/lat 原值，**不投影**） | `det_min_m` 全体放大 ⇒ 证明投影是杠杆 |
| `N4` | `hour 8 → 7` | `obs_8_9` 变化（`G-O3-2` 必 FAIL） |
| `N5` | `fake_detector_id=True`（注入伪造 `DETECTOR_ID` 且允许绑定） | `facility_binding` 由 `UNRESOLVED` → `RESOLVED` |
| `N6` | `vertex_mode="bbox"`（把 2 顶点段扩成 bbox ⇒ `nv` 判据被扰动） | `A` 命中数改变 |

**签名** `sig = (Σ len_m, Σ opp_perp_m[finite], Σ det_n100, Σ K_primary, nA, nC, nD, nB, nE, n_bound)`。

---

## 4. 判读纪律（★用户指定 + 承接 `readme §4`）

1. ⛔ **不得以几何邻近替代物理对应**：`det_min_m` 小 ⇒ 只能说「附近有线圈设施」，**不得**说「该观测对象由该线圈测量」。
2. ✅ **`A/C` 若不成立，只能写「不成立」**，不得写「因此 = 单车行道」。
3. ✅ **`B` 只能写「本地不可判定」**（`OBS_OBJECT_UNRESOLVED`），不得写「MATSim 承载错误」。
4. ✅ **`D` 成立时只写「跨层基数 ≠ 1」**，不得写「观测对象方向错」。
5. ⛔ **尺度纪律**：`F_LOW`（71.02% Σobs）**仍不与 ④ 混解**；本刀**不产生** ④ 的结论。
6. ✅ **`K_pooled = 5.5434` 基数不可比** ⇒ `K` 仅报计数，**不作**流量比较。
7. ✅ **退化必披露**：`facility_binding` 单值、`E` 不可达、`opp_perp_m` 含 `inf`，均须**显式列出**。
8. ⛔ **不改** network / v1.0 / 靶场定义 / 阈值族（D-path、D2-review 冻结值全部不动）。

---

## 5. 交付物

| 文件 | 内容 |
|---|---|
| `PREREG_7_9I_O3.md` | 本文件（运行前冻结） |
| `scripts/od/audit_obs_domain_7_9io3.py` | 引擎（零仿真、只读） |
| `reports/corridor_scale_audit_7_9i/o1f_obs_cards_7_9io3.csv` | 逐断面 Observation Object Card（14 行 = 9 主 + 5 参照） |
| `reports/corridor_scale_audit_7_9i/o1f_obs_summary_7_9io3.json` | 汇总（门禁 / 负例 / 全域基线 / 字段实况 / 元数据矩阵） |
| `reports/corridor_scale_audit_7_9i/_run_7_9io3.log` | 运行日志 |
| `reports/corridor_scale_audit_7_9i/STEP7_9I_O3_REPORT.md` | 正式报告 |

**判决串**：`OBS_DOMAIN_AUDIT_READY`（10/10 门 + 负例 6/6）→ 阶段链更新为 `… → D2-review ✓ → O3 ✓`
