# Step 7.9I-O3 —— 「LTA 观测对象语义审计」（OBS-DOMAIN）正式报告

> 阶段串：`7.9I_FROZEN_CLOSED → O1 ✓ → O1-续 ✓ → O1-续② ✓ → D-path ✓ → D2-review ✓ → **O3 ✓**`
> 判决：**`OBS_DOMAIN_AUDIT_READY`**（硬门 **10/10**、负例 **6/6 fired**、`n_fail=0`、35.0 s、**零仿真**）
> 预注册：`PREREG_7_9I_O3.md`（运行前冻结）；卡片 SHA256 `32daf852192a0c1d`（两次跑逐位一致）
> 底线执行情况：✅ 未改 v1.0 ✅ 未跑 MATSim ✅ 未碰 `signals` / `trafficDynamics` / `speedFactor` ✅ 未产生 v1.1

---

## 0. 结论摘要

| # | 结论 | 证据 |
|---|---|---|
| **C1** | **观测对象 = LTA 有向「路段」（directed link segment）** | `TrafficFlow_Links` **1,278/1,278 全为 2 顶点**；长度 p50 **128 m**（41–201 m）；**同路名 obs 唯一率 p50 = 1.0000**（96 组 ≥3 条） |
| **C2** | **「单车行道 vs 设施」：结构层支持「有向路段」；设施归属层 `OBS_OBJECT_UNRESOLVED`** | 结构证据见 C1；但 `DETECTOR_ID`/`RD_CD`/`LANE_NUM` **本地不存在**，且 DetectorLoop **与断面不共址**（见 C6） |
| **C3** | **事实②（一对象覆盖多承载对象）：LTA 侧\*\*非聚合\*\*；跨层基数为 1:K** | `sib_uniq_frac` **0.9706–1.0000** ⇒ 逐段独立；`K_primary` **1–14**（`K_pooled = 5.5434`） |
| **C4** | **事实③（Volume 语义）= 「通过该有向路段的（代表月工作日 08 时）小时机动车流量」** | `vol_int_frac = 1.0`（**原始整数计数**）；日间 CV p50 **0.075**；`obs_h7/obs_h8` p50 **0.988**；`n_h8_wd = 20`（工作日天数） |
| **C5** | **★本地文档 ≠ 实际数据（3 处）⇒ `DATA_ACQUISITION_GAP`** | 见 §4.1：`VehicleType`/`Timestamp` 不存在；`DetectorLoop` 仅 `OBJECTID`；`RoadSectionLine` 无 `LinkID` |
| **C6** | **DetectorLoop 在本地不可连接** | 共址率 **25 m 3.5% / 50 m 8.2% / 100 m 19.9% / 200 m 43.9%**；`det_min` p50 **222 m**；本批 14 节 `det_min` **113.6–673.8 m** |
| **C7** | **A–E：`A=0 · C=0 · D=11 · B=3 · E=0`** | 主集 `F_LOW`：**`D` 7 / `B` 2**；参照集 `F_ADQ`：`D` 4 / `B` 1 |
| **C8** | **结构性集中：`F_LOW` 9 节中 8 节在 `AYER RAJAH EXPRESSWAY`** | 8×(CATA 6 + SLIP_ROAD 2) + 1× ECP 服务道路 |
| **C9** | **运行健康** | 门 **10/10**、负例 **6/6**、`SHA 32daf852192a0c1d` 两次一致、AST 无随机源 |

> **★一句话结论**：本地元数据**可以**确立「观测对象是 LTA **有向、逐段、非聚合**的路段级流量」；
> 但**无法**确立「它是否等于 MATSim 的一条**物理车行道**」——**因为所需标识字段在本批下载中不存在**。
> ⇒ 该轴标 **`OBS_OBJECT_UNRESOLVED`**（⛔ **不以几何邻近替代**，与 `TWIN_GEOMETRIC_SUBSTITUTE` 同纪律）。

---

## 1. 立论与范围

### 1.1 问题转向（用户 2026-09-30 裁定）

⛔ 不再问「哪条 MATSim edge 应该承接这些车？」（D-path / D2-review 已把该问法收敛为**阴性结果**）
✅ 改问：**「LTA 的这个数，到底在现实世界中测量了什么？」**

**官方依据**（用户引用；本地 `docs/LTA_DataMall_API_User_Guide.md` L1029 **逐字确证**）：

> `TrafficFlow` — *"Returns **hourly average traffic flow**, taken from a **representative month of every quarter** during **0700-0900 hours**."*（Update Freq: **Quarterly**）

⇒ 三概念必须分开：`Traffic Flow` ≠ `Detector Loop` ≠ `Traffic Count / Turning Movement`。
⇒ 官方资料**并未**证明「一个 LinkID / TrafficFlow section = MATSim 中的一条物理车行道」。

### 1.2 范围

| 集 | 内容 | Σobs |
|---|---|---|
| **主集** | `F_LOW` 9 节（D-path `carry_scaled < 0.50`） | **20,141.0**（= 用户给定 71.02%） |
| **参照集** | `F_ADQ` 5 节（D-path `carry_scaled ≥ 0.50`） | 9,219.0 |
| **基线** | 全域观测域：**1,311 obs LinkID / 1,278 有几何** | — |

`F_LOW` 组成：`AYE` 8 节（`48461/49054/49104/48586/48708/48337` 为 CATA；`47163/49027` 为 SLIP_ROAD）+ `EAST COAST PARK SERVICE ROAD 172382`（SLIP_ROAD）。

---

## 2. 方法

### 2.1 数据资产（全部本地、只读）

| 文件 | CRS | 角色 |
|---|---|---|
| `Dynamic_2026_03_16/historical_data/TrafficFlow_Links.dbf` | WGS84 | **观测对象几何**（LinkID ↔ 2 顶点有向段） |
| `Dynamic_2026_03_16/historical_data/TrafficFlow_Data.json` | WGS84 | **观测值**（`LinkID × Date × HourOfDate → Volume`） |
| `Dynamic_2026_03_16/historical_data/geospatial/DetectorLoop.zip` | **SVY21** | 检测线圈**设施几何**（16,275 线 / 111,544 顶点） |
| `Dynamic_2026_03_16/historical_data/geospatial/RoadSectionLine/` | **SVY21** | **道路分级线**（15,329 条） |
| `reports/od_structure_7_6c/section_geography.csv`（SEC_GEO_7_6C） | SVY21 | 项目断面锚点（574） |
| `reports/od_final_calibration_crosswalk_7_3_6/final_calibration_crosswalk.csv` | — | `K = is_primary_candidate` 计数 |

### 2.2 观测值口径（承接 7.3.6A / 7.9E-2，⛔ 不变）

```text
obs_8_9(s) = median{ Volume(LinkID=s, Date=d, HourOfDate=8) : d 为工作日 }
```
- ⚠️ **`Volume` 是带千分位逗号的字符串**（如 `"1,069"`）；⛔ 直接 `to_numeric` 会把约 0.4% 记录变 NaN ⇒ 必须 `str.replace(",","")`。
- `HourOfDate` 全域仅 **{7, 8}**（承接 7.4.3-R「可观测窗 ≤07-09」）。
- ✅ **复现**：14 节 `obs_8_9` 与 `o1e_d2rev_cards_7_9id2.csv` **逐值一致（max|Δ| = 0.00）**。

### 2.3 坐标口径（承接 `readme §4`「坐标必须同源」）

`TrafficFlow_*` 为 WGS84；`DetectorLoop` / `RoadSectionLine` / `SEC_GEO_7_6C` 为 SVY21 ⇒ **距离计算统一投影到 SVY21**（`EPSG:4326 → EPSG:3414`）。
**自洽门 `G-O3-1`**：9 主节 lon/lat → SVY21 中点 vs `SEC_GEO_7_6C.mid_x/mid_y`，**max 57 m / p50 25 m**（阈值 250 m）。

### 2.4 四轴结构判据（本刀新增，已在预注册冻结）

| 轴 | 判据 |
|---|---|
| 粒度 | `nv`（顶点数）、`len_m` |
| 方向性 | `opp_perp_m` = 断面中点到最近**反向**（`|Δbearing| ≥ OPP_MIN = 150°`）观测对象**线**的**垂距** |
| 聚合性 | `sib_uniq_frac` = 同 `RoadName` 内 `obs_8_9` 唯一值数 / 同胞数（仅当 `sib_n ≥ 3`） |
| 设施绑定 | `det_min_m`、`det_n_100`，**以及字段实况** |

### 2.5 A–E 分类（用户指定，五类并列可证伪）

| 类 | 判据（本地可执行版） | 主类优先级 |
|---|---|---|
| **A** `A_OBS_NOT_SINGLE_SEGMENT` | `nv > 2` ∨ `len_m > 500 m` | 1 |
| **C** `C_OBS_AGGREGATE_FACILITY` | `sib_n ≥ 3` ∧ `sib_uniq_frac < 0.50` | 2 |
| **D** `D_LEVEL_CARDINALITY_MISMATCH` | `K_primary > 1` | 3 |
| **B** `B_BINDING_UNDECIDABLE` | `facility_binding == UNRESOLVED` ∧ ¬A ∧ ¬C | 4 |
| **E** `E_UNEXPLAINED` | ¬(A ∨ C ∨ D ∨ B) | 5 |

### 2.6 常量（新增者已登记；实测距阈值 ≥2× 余量 ⇒ 结论非阈值敏感性产物）

`OPP_MIN 150°` · `DIR_OK 30°` · **`LEN_MAX 500 m`**（实测 max 187 m）· **`AGG_MAX 0.50`**（实测 0.97–1.00）· **`SIB_MIN_N 3`** · **`DET_R 100 m`** · **`PERP_R 250 m`** · `HOUR 8` · `K_pooled 5.5434`。

---

## 3. 硬门与负例

### 3.1 硬门（10/10 PASS）

| 门 | 结果 | 实测 |
|---|---|---|
| `G-O3-1` 坐标同源 | ✅ PASS | max 57 m / p50 25 m |
| `G-O3-2` obs 复现 | ✅ PASS | max\|Δ\| **0.00**（9/9） |
| `G-O3-3` 字段实况 | ✅ PASS | Links=7 / Obs=10 / DetLoop=1 / RSL=4 |
| `G-O3-4` 全域基线非退化 | ✅ PASS | geo=1278、2-顶点率 1.000、uniq p50 1.000、det100 0.199 |
| `G-O3-5` 判别量非退化 | ✅ PASS | `len_m` 14 取值、`opp_perp_m` 14、`sib_uniq_frac` 3、`K_primary` 8、`det_min_m` 14 |
| `G-O3-6` 卡片完备 | ✅ PASS | 19 字段齐、非 inf 字段无 NaN |
| `G-O3-N` 负例 6/6 | ✅ PASS | N1✓ N2✓ N3✓ N4✓ N5✓ N6✓ |
| `G-O3-7` `UNRESOLVED` 可证伪 | ✅ PASS | N5 注入伪造 `DETECTOR_ID` ⇒ `RESOLVED` |
| `G-O3-8` A/C 可证伪 | ✅ PASS | ΔnC=+14、ΔnA=+14 |
| `G-O3-9` AST 自检 | ✅ PASS | hits=0（无 random / 无网络） |

### 3.2 负例（6/6 fired，**与主路径共用同一 `compute(params)`**）

基线签名 `(1810.5, 1417.4, 28361.0, 6141.6, 65, 0, 0, 11, 3, 0, 0)`

| # | 扰动 | fired | 作用 |
|---|---|---|---|
| `N1` | `OPP_MIN 150 → 30.1` | ✓ | 对向阈值降入同向带 ⇒ `Σopp_perp_m` 改变 |
| `N2` | `AGG_MAX 0.50 → 1.01` | ✓ | **ΔnC = +14** ⇒ 聚合判据有效 |
| `N3` | `project_det = False`（不投影） | ✓ | `Σdet_min_m` 剧变 ⇒ **证明坐标投影是杠杆** |
| `N4` | `hour 8 → 7` | ✓ | `Σobs_8_9` 改变 ⇒ **证明 obs 口径是杠杆** |
| `N5` | `fake_detector_id = True` | ✓ | `UNRESOLVED → RESOLVED` ⇒ **证明 UNRESOLVED 是数据缺失而非判据失效** |
| `N6` | `vertex_mode = bbox` | ✓ | **ΔnA = +14** ⇒ 粒度判据有效 |

---

## 4. 结果

### 4.1 ★本地文档 ≠ 实际数据（`DATA_ACQUISITION_GAP`）

| 表 | **实际字段（本刀实测）** | 本地文档声称 | 差异 |
|---|---|---|---|
| `TrafficFlow_Links.dbf` | `LinkID, RoadName, RoadCat, StartLon, StartLat, EndLon, EndLat`（7） | — | — |
| `TrafficFlow_Data.json` | `LinkID, Date, HourOfDate, Volume, StartLon, StartLat, EndLon, EndLat, RoadName, RoadCat`（10） | `LinkID, **VehicleType**, Volume, **Timestamp**`（`Dynamic_2026_03_16/DATA_README.md` L160–168） | ⚠ **`VehicleType` / `Timestamp` 不存在** |
| `DetectorLoop.dbf` | **`OBJECTID`（1）** | `OBJECTID, SHAPE, JOB_NUM, RD_CD, **LANE_NUM**, **DETECTOR_ID**, REMARKS`（`Static_ 2026_03/DATA_DOCUMENTATION.md` L233–241） | ⚠ **`DETECTOR_ID` / `RD_CD` / `LANE_NUM` 全部缺失** |
| `RoadSectionLine.dbf` | `RD_CD, RD_CATG_NA, RD_CATG__1, RD_CD_DESC`（4） | `OBJECTID, SHAPE, JOB_NUM, RD_CD, RD_CATG_NAM, …, SHAPE.LEN`（同文件 L513–527） | ⚠ **两版本皆无 `LinkID`**；本地 `RD_CD`/`RD_CATG_NA` **100% 空** |

> ⇒ **关键**：`DetectorLoop` 的**属性字段在下载时被剥离**（只剩几何 + `OBJECTID`）。
> 官方文档**明确列出了这些字段**（`DETECTOR_ID` / `RD_CD` / `LANE_NUM`）⇒ **不是「元数据不存在」，而是「本批未取得」**。

### 4.2 全域基线（1,278 有几何 LinkID）

| 指标 | 实测 |
|---|---|
| 顶点数分布 | `{2: 1278}` ⇒ **100% 2 顶点** |
| 长度 | p10 53 / **p50 128** / p90 187 / max 201 m |
| 同路名 `obs` 唯一率（96 组 ≥3 条） | p10 0.99 / **p50 1.0000** / p90 1.0000 |
| 到最近**对向**观测对象垂距 | p10 15 / **p50 40** / p90 669 m；**≤60 m 占比 0.504**；`PERP_R=250 m` 内无对向对象 **249 条** |
| DetectorLoop 共址率 | 25 m **3.5%** / 50 m 8.2% / 100 m **19.9%** / 200 m 43.9% |
| `det_min` | p10 59 / **p50 222** / p90 569 m |
| `RoadCat` 分布 | `CATB 634 · CATA 339 · SLIP_ROAD 251 · CATC 46 · CATD 7 · CATE 1` |

### 4.3 逐断面 Observation Object Card（14 行 = 9 主 + 5 参照）

| section_id | 集 | RoadName | Cat | obs_8_9 | nv | len_m | opp_id | opp_perp_m | opp_obs | 同路 | sib_n | uniq | det_min | K | highway | final_class |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 48461 | F_LOW | AYER RAJAH EXPRESSWAY | CATA | 4,118.0 | 2 | 167.3 | 26572 | 66.1 | 1,423.0 | ✓ | 52 | 0.9808 | 380.7 | 1 | motorway | **B** |
| 49054 | F_LOW | AYER RAJAH EXPRESSWAY | CATA | 3,481.5 | 2 | 105.8 | 25066 | 160.3 | 1,556.5 | ✓ | 52 | 0.9808 | 472.6 | 1 | motorway | **B** |
| 49104 | F_LOW | AYER RAJAH EXPRESSWAY | CATA | 2,896.0 | 2 | 102.8 | 25169 | **22.9** | 565.0 | ✗ | 52 | 0.9808 | 387.6 | 2 | motorway | **D** |
| 48586 | F_LOW | AYER RAJAH EXPRESSWAY | CATA | 2,532.0 | 2 | 173.4 | 48556 | 196.9 | 3,096.5 | ✓ | 52 | 0.9808 | 612.4 | 4 | motorway | **D** |
| 48708 | F_LOW | AYER RAJAH EXPRESSWAY | CATA | 2,393.5 | 2 | 40.9 | 48414 | 238.7 | 1,941.0 | ✓ | 52 | 0.9808 | 397.1 | 3 | motorway | **D** |
| 48337 | F_LOW | AYER RAJAH EXPRESSWAY | CATA | 2,052.5 | 2 | 187.1 | 48527 | 95.2 | 3,161.0 | ✓ | 52 | 0.9808 | 528.3 | 3 | motorway | **D** |
| 47163 | F_LOW | AYER RAJAH EXPRESSWAY | SLIP_ROAD | 1,967.0 | 2 | 128.4 | 26159 | 130.5 | 469.0 | ✗ | 52 | 0.9808 | 533.7 | 5 | motorway_link | **D** |
| 49027 | F_LOW | AYER RAJAH EXPRESSWAY | SLIP_ROAD | 581.5 | 2 | 139.1 | 48524 | **24.5** | 2,532.5 | ✓ | 52 | 0.9808 | 397.7 | 5 | motorway_link | **D** |
| 172382 | F_LOW | EAST COAST PARK SERVICE ROAD | SLIP_ROAD | 119.0 | 2 | 60.0 | — | **inf** | — | — | 3 | 1.0000 | 673.8 | 14 | motorway_link | **D** |
| 45956 | F_ADQ | PAN ISLAND EXPRESSWAY | CATA | 3,029.0 | 2 | 161.3 | 189161 | 126.9 | 4,237.5 | ✓ | 136 | 1.0000 | 209.6 | 3 | motorway | D |
| 47189 | F_ADQ | PAN ISLAND EXPRESSWAY | CATA | 2,334.5 | 2 | 127.5 | 46851 | 65.6 | 2,878.0 | ✓ | 136 | 1.0000 | 359.9 | 1 | motorway | **B** |
| 45927 | F_ADQ | JALAN AHMAD IBRAHIM | SLIP_ROAD | 1,780.5 | 2 | 143.9 | 46851 | 34.1 | 2,878.0 | ✗ | 34 | 0.9706 | 476.0 | 7 | motorway_link | D |
| 48983 | F_ADQ | AYER RAJAH EXPRESSWAY | SLIP_ROAD | 669.5 | 2 | 185.7 | 48527 | 205.8 | 3,161.0 | ✓ | 52 | 0.9808 | 598.6 | 5 | motorway_link | D |
| 129352 | F_ADQ | UPPER JURONG ROAD | SLIP_ROAD | 406.5 | 2 | 87.3 | 189161 | 49.9 | 4,237.5 | ✗ | 10 | 1.0000 | **113.6** | 11 | motorway_link | D |

- `facility_binding` **14/14 = `UNRESOLVED`**；`direction_ok_frac` **14/14 = 1.0**；`n_h8_wd` **14/14 = 20**；`vol_int_frac` **14/14 = 1.0**。
- `vol_cv`：p50 0.075 / max 0.241；`obs_h7 / obs_8_9` p50 **0.988**。

### 4.4 A–E 分类合计

| 类 | 全 14 节 | 主集 `F_LOW`(9) | 参照 `F_ADQ`(5) |
|---|---|---|---|
| **A** `A_OBS_NOT_SINGLE_SEGMENT` | **0** | 0 | 0 |
| **C** `C_OBS_AGGREGATE_FACILITY` | **0** | 0 | 0 |
| **D** `D_LEVEL_CARDINALITY_MISMATCH` | **11** | **7** | 4 |
| **B** `B_BINDING_UNDECIDABLE` | **3** | **2** | 1 |
| **E** `E_UNEXPLAINED` | **0** | 0 | 0 |

### 4.5 四事实逐项回答

| # | 问题 | 本刀实测回答 |
|---|---|---|
| **①** | 观测对象是「单车行道」还是「道路断面/设施」？ | **结构层**：**有向路段**（2 顶点、p50 128 m、逐段 Volume 唯一）。<br>**设施归属层**：⛔ **`OBS_OBJECT_UNRESOLVED`** —— `DETECTOR_ID` / `junction ID` / `RD_CD` / `LANE_NUM` **本地均不存在**，DetectorLoop 与断面亦**不共址**（p50 222 m）。 |
| **②** | 是否存在「一个观测对象覆盖多个实际承载对象」？ | **LTA 侧：否**（`sib_uniq_frac` 0.9706–1.0000 ⇒ 逐段独立，非聚合）。<br>**跨层：是**（`1 LTA LinkID ↔ K MATSim primary 边`，`K` **1–14**）。 |
| **③** | `Volume` 是「通过该对象的流量」还是道路级统计量？ | **通过该有向路段的流量**：原始**整数**计数（`vol_int_frac = 1.0`）、工作日 08 时中位、日间 CV p50 0.075。<br>⛔ **无车型字段**（`VehicleType` 不存在）⇒ 是**全机动车**口径；⛔ **无 detector 绑定** ⇒ 「通过哪个物理检测器」不可知。 |
| **④** | 回到 MATSim | **本刀不做**（用户明确「最后才回到 MATSim」）。 |

---

## 5. 判读

### 5.1 对用户四事实的裁定

- ✅ **事实①**：**结构层可判** ⇒ 观测对象 = 有向路段；**设施层不可判** ⇒ `OBS_OBJECT_UNRESOLVED`。
- ✅ **事实②**：**LTA 侧无聚合**（阴性）+ **跨层基数 1:K**（阳性）。
- ✅ **事实③**：Volume = 该有向路段的工作日 08 时中位机动车流量（**非道路级统计量**）。
- ⛔ **事实④**：未执行。

### 5.2 A–E 裁定（严格按预注册判据）

| 类 | 裁定 | 允许的表述 | ⛔ 禁止的表述 |
|---|---|---|---|
| **A** | **不成立（0/14）** | 「在本地可测维度上，观测几何不是多段/长段」 | 「因此 = 单车行道」 |
| **C** | **不成立（0/14）** | 「Volume 在路级**未**重复」 | 「因此 = 单车行道」 |
| **D** | **成立（11/14）** | 「**1 观测对象 ↔ K>1 网络对象**，跨层基数 ≠ 1」 | 「观测对象方向错」 |
| **B** | **命中（3/14）** | 「**本地不可判定**（缺设施绑定元数据）」 | 「MATSim 承载错误」 |
| **E** | **0（结构性不可达）** | 须**披露**：`B` 恒真 ⇒ `E` 在本批不可达 | — |

### 5.3 ★可操作发现（本刀最有价值的一条）

> **观测对象语义在本批**无法**闭合，原因不是「LTA 没有元数据」，而是：**
> **① `DetectorLoop` 下载时属性字段被剥离**（`DETECTOR_ID` / `RD_CD` / `LANE_NUM` 官方文档明确列出，本地只剩 `OBJECTID`）；
> **② `RoadSectionLine` 本地版本无 `LinkID`**；
> **③ 本地无 Junction / Turning-Count 数据集。**

⇒ **闭合路径（须用户裁定，本刀不执行）**：
```text
(a) 重新获取 LTA DataMall 「Geospatial」→ DetectorLoop（含属性字段）
(b) 申请 On-Request「Indicative Traffic Counts at Junctions by Loop Detectors」（JunctionID / DetectorID / 15-min counts）
(c) 取得后，方可把「观测对象 ↔ 物理设施对象」绑定 ⇒ 才能判 B（MATSim 是否承载错误）
```

### 5.4 与既有结论的一致性

- 与 **D-path / D2-review** 不冲突：本刀**未**改任何 D 类判据，**未**重解释 `D1 = 0`，**未**把 `F_LOW` 与 ④ 混解。
- 与 **O1-续②** 一致：本刀同样拒绝了「以几何邻近替代物理对应」。
- ⛔ `K_pooled = 5.5434` 基数不可比 ⇒ `K` 仅**计数**披露，**未**用于流量比较。

---

## 6. 复现

```bash
C:/Users/LQP/miniconda3/python.exe scripts/od/audit_obs_domain_7_9io3.py
# → OBS_DOMAIN_AUDIT_READY   gates=10/10   n_fail=0   elapsed=35.0 s   sha=32daf852192a0c1d
```
- **复现性**：连续两次运行 `o1f_obs_cards_7_9io3.csv` **SHA256 前 16 位逐位一致**（`32daf852192a0c1d`）。
- **AST 自检**：无 `random` / 无网络 / 只读（`G-O3-9`）。
- `elapsed_s` 为**单次墙钟量**，⛔ 不得用于文档↔产物对账。

---

## 7. 产物清单

| 文件 | 说明 |
|---|---|
| `PREREG_7_9I_O3.md` | 预注册冻结件（13,960 B） |
| `scripts/od/audit_obs_domain_7_9io3.py` | 引擎（零仿真、只读） |
| `o1f_obs_cards_7_9io3.csv` | 逐断面 Observation Object Card（14 行，3,160 B） |
| `o1f_obs_summary_7_9io3.json` | 汇总（门禁 / 负例 / 基线 / 字段实况 / 元数据矩阵，18,049 B） |
| `_run_7_9io3.log` | 运行日志（6,113 B） |
| `STEP7_9I_O3_REPORT.md` | 本报告 |

---

## 8. 缺陷登记

### 8.1 `criteria_revision`

| ID | 类型 | 内容 | 处置 |
|---|---|---|---|
| **`R1`** | **仪器实现缺陷（签名设计）** | 首版 `sig` 含 `Σdet_n_100`（基线**恒 0**：最小 `det_min` = 113.6 m > `DET_R` = 100 m ⇒ **无判别量**）且**未含** `Σobs_8_9` ⇒ 负例 `N3`（不投影）/`N4`（hour 7）**空扰动假阴性**（`fired=False`） | `sig` 改为含 `Σobs_8_9` 与 `Σdet_min_m`；**主路径判据 / 阈值 / 分类 / 卡片字段全部未改**。属**负例设计缺陷**，非科学结论 |

### 8.2 其他披露（`D` 系列，均为**结构/边界**而非缺陷）

| ID | 内容 |
|---|---|
| `D1` | **`facility_binding` 单值退化**：本批 14/14 = `UNRESOLVED`（由 `G-O3-7` 的 `N5` 反证其为**数据缺失**而非判据失效） |
| `D2` | **`E` 类不可达**：因 `B` 恒真 ⇒ `E_UNEXPLAINED` 在本批**结构性为 0**，须显式披露（类比 `D1 = 0`） |
| `D3` | **`opp_perp_m` 含 `inf`**：全域 249 条、本批 1 条（`172382`）在 `PERP_R = 250 m` 内无对向对象 ⇒ 已单列计数 |
| `D4` | **`A/C` 的否定不是「单车行道」的证据**：`LEN_MAX` / `AGG_MAX` 的实测距阈值有 ≥2× 余量，但 `A=0/C=0` 只能读作「**未检出**」 |
| `D5` | **文档 ≠ 数据**：`VehicleType`/`Timestamp`/`DETECTOR_ID`/`RD_CD`/`LANE_NUM`/`LinkID` 六项**在本地文档与本地数据间不一致** ⇒ 使用本地文档做口径推导时**必须实测校验**（本刀 `G-O3-3` 已固化） |
| `D6` | **`direction_ok_frac = 1.0`（14/14）** ⇒ 项目匹配层的方向判据在此批**不区分量**，不得据此声称「方向匹配正确」 |

---

## 9. 下一步（待用户裁定；⛔ 本刀不启动）

1. **（本刀直接指向）补齐观测对象语义元数据** —— `DetectorLoop` 含属性重新获取 + On-Request Junction Loop Counts ⇒ 方可判 **B**。
2. **事实④（回到 MATSim）** —— 须待 ① 闭合后，才能判 `F_LOW → B/C/D/E` 的最终归属。
3. ⛔ `signals` / `trafficDynamics` / `speedFactor` **须用户显式裁定解除底线**；**不产生 v1.1**。
