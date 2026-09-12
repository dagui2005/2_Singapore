# Step 3 — Workplace Attraction 运行审查报告

- 生成时间：2026-09-11
- 脚本：`scripts/od/build_attraction.py`
- 状态：**PASS**
- 输出目录：`reports/od_attraction/`

---

## 1. 运行结果（真实输出）

| 指标 | 数值 |
|---|---|
| Subzone 数 | 332 |
| 物理工作地 PA 控制数 | 44 |
| 特殊节点数 | 3 |
| ACRA 记录数 | 1,049,322 |
| ACRA 有效邮编（6 位） | 1,046,847 |
| ACRA 成功定位到 Subzone | 858,741 |
| ACRA 邮编定位率 | **82.03%** |
| Census 物理控制总量 | 1,935,235 |
| Subzone Attraction 合计 | 1,935,235 |
| PA 守恒最大绝对误差 | 1.46e-11 |
| PA 守恒最大相对误差 | 1.89e-16 |
| 零 Attraction Subzone | 25 |
| 正值 Attraction Subzone | 307 |

**逐 PA 守恒达机器精度**：`Σ_{z∈PA} A_z ≡ E_PA`，最大相对误差 1.9e-16。

---

## 2. 预期设计行为（已确认，非缺陷）

### 2.1 特殊节点保留
全国合计 2,208,358 被拆为：

| 类别 | 数值 |
|---|---|
| 44 个物理 PA 控制量 | 1,935,235 |
| Other Planning Areas or Outside Singapore | 24,736 |
| No Fixed Location for Work | 177,588 |
| Works from Home | 70,800 |
| 3 个特殊节点小计 | 273,124 |
| 物理 + 特殊 | 2,208,359 |
| 全国合计（源表） | 2,208,358 |
| **残差** | **+1** |

> ⚠️ 残差 ±1 属源表取整残差（与 Step 2 的 Table 88 取整问题同源），按既定口径记为显式参数，不修正。

### 2.2 11 个"仅居住端"PA → 0 工作吸引量
55 个 zone PA 中有 11 个不在工作端 44 PA 内，这些 PA 下 25 个 Subzone 得到 0：

TENGAH(6)、RIVER VALLEY(5)、SIMPANG(4)、MANDAI(3)、LIM CHU KANG(1)、CENTRAL WATER CATCHMENT(1)、CHANGI BAY(1)、NORTH-EASTERN ISLANDS(1)、MARINA SOUTH(1)、MARINA EAST(1)、STRAITS VIEW(1)。

> 符合"44 ⊂ 55 + 3 特殊节点"的既定设计。**但需注意**：River Valley、Marina East/South、Straits View 在现实中位于滨海湾 CBD 延伸带，其就业被 Census 折叠进相邻 PA，Step 4 之前可考虑作显式口径说明。

---

## 3. 合理性验证（正信号）

- **工作端就业空间梯度正确**：Downtown Core 284,004 居首，Queenstown 131,782、Geylang 116,481、Bukit Merah 103,575 次之。
- **Top Subzone 全部落在 CBD**：CECIL(49,394)、CITY HALL(40,526)、RAFFLES PLACE(37,410)、MARINA CENTRE、TANJONG PAGAR、CENTRAL SUBZONE 均属 Downtown Core。
- **区域份额**：Central 53.6% / West 17.7% / East 12.7% / North-East 8.4% / North 7.6%（直接来自 Census 控制量，非算法产物）。
- **ACRA 空间信号强度**：`corr(acra_activity_weight, attraction) = 0.766`；`corr(landuse_activity_weight, attraction) = 0.135`。ACRA 权重（0.65）主导，符合设计意图。
- **未定位企业未删除**：17.97% 未定位 ACRA 不被丢弃，通过 Census PA 归一化间接体现。

---

## 4. 需要关注的信号（Step 4 前建议处理）

### 4.1 面积型 LandUse 权重在"大面积低强度用地"上被放大 ⚠️

单个 Subzone 吸收 PA 内 >60% 岗位：

| Subzone | PA | PA 岗位 | 占比 | ACRA 企业 | landuse 权重(m²) |
|---|---|---|---|---|---|
| JURONG ISLAND AND BUKOM | WESTERN ISLANDS | 13,152 | **90.7%** | 5 | 8.36e7 |
| UPPER THOMSON | BISHAN | 28,932 | 79.9% | 12,921 | 1.53e6 |
| MURAI | WESTERN WATER CATCHMENT | 28,079 | **78.9%** | 198 | 1.21e7 |
| CHANGI AIRPORT | CHANGI | 63,747 | 76.4% | 583 | 7.47e6 |
| DHOBY GHAUT | MUSEUM | 12,672 | 62.9% | 1,729 | 2.29e5 |

JURONG ISLAND AND BUKOM 仅 5 家企业却吸收 90.7% —— 典型"面积权重放大"。该 Subzone 3,660 公顷，绝大多数为港口/工业/填海地，落入默认权重 0.2。**建议引入 GPR 建筑面积/楼层承载权重**以抑制此效应。

### 4.2 LU_DESC 权重字典覆盖不足（18/33 类落默认 0.2） ⚠️

`LANDUSE_WEIGHT` 未覆盖的真实类别（按多边形数）：UTILITY(1067)、WATERBODY(1015)、RESIDENTIAL / INSTITUTION(960)、COMMERCIAL & RESIDENTIAL(905)、RESERVE SITE(665)、PLACE OF WORSHIP(645)、COMMERCIAL / INSTITUTION(533)、TRANSPORT FACILITIES(349)、AGRICULTURE(239)、SPECIAL USE/MRT/PORT-AIRPORT/B1-WHITE/BEACH/CEMETERY/LRT/B2-WHITE/BUSINESS PARK-WHITE(共 292)。

合计约 6,675 个多边形（占 5.9%）落入默认 0.2，其中：
- **PORT / AIRPORT → 0.2 明显偏低**（机场/港口是高就业用地，却仅得 0.2）
- **WATERBODY → 0.2 明显偏高**（应为 0，否则水域被赋予就业承载）
- **COMMERCIAL & RESIDENTIAL / RESIDENTIAL / INSTITUTION / COMMERCIAL / INSTITUTION → 0.2 偏低**

### 4.3 13 个 Subzone 无任何 ACRA 企业但 Attraction>0（纯 landuse 兜底）⚠️

YIO CHU KANG NORTH、LORONG HALUS、MARINA EAST (MP)、CONEY ISLAND、AIRPORT ROAD、GUL BASIN、LORONG HALUS NORTH、SOUTHERN GROUP、PULAU PUNGGOL TIMOR、TENGEH、BAHAR、SEMAKAU、SUDONG。

多为填埋场/离岛/军事/机场附属地，现实就业极少 —— 属面积权重的假信号。

### 4.4 3 个 PA 完全无定位 ACRA（landuse-only 兜底）
CHANGI BAY、MARINA EAST、SIMPANG。三者的 Census 控制量为 0，故 attraction 仍为 0，**无实际影响**。

### 4.5 输出字段与规划口径的差异（信息项）
- 脚本产出 `subzone_landuse_weights.csv`，规划命名为 `subzone_activity_weights.csv`。
- `attraction.csv` 尚未包含分类用地面积列（office/commercial/industrial/institution/education/health）与 `poi_activity_weight`；`poi.csv` 已定义但未接入。
- `attraction_weight` 目前以中间量 `activity_weight_raw` / `attraction_share_within_pa` 体现。

---

## 5. 结论与 Step 4 前建议

1. **Step 3 v1 可判 PASS**：逐 PA 守恒达机器精度，控制量口径清晰，ACRA 主导空间信号，CBD 梯度正确。
2. **不建议大改结构**，建议做三项"权重精细化"再进 Step 4：
   - 补全 `LANDUSE_WEIGHT` 覆盖（至少 PORT/AIRPORT、COMMERCIAL & RESIDENTIAL、*/INSTITUTION、WATERBODY=0、UTILITY/GPR 处理）；
   - 引入 **GPR 建筑面积权重**（`FloorArea ≈ area × GPR`），替代/加权裸面积，抑制 Jurong Island / Murai / Changi Airport 类放大；
   - 可选：接入 POI 强度，补充分类用地面积列以对齐规划字段。
3. Step 4 输入已就绪：`A_j`（332 行，逐 PA 守恒）+ Step 2 的 `P_i`（332 行）。
