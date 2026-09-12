# Step 3B.1 — Attraction v2.1 构建与 v1/v2/v2.1 三方对比

> 状态：**PASS**（PA 逐区守恒达机器精度）
> 产出目录：`reports/od_attraction_v21/`（不覆盖 `od_attraction/` = v1、`od_attraction_v2/` = v2）
> 脚本：`scripts/od/build_attraction_v21.py`、`scripts/od/attraction_diagnostics_v21.py`
> 原则：**未对任何 Subzone 的就业量做人工调整**；所有变化均来自 Census 控制量 + ACRA + Building + LandUse + POI。

---

## 0. 本步实际改动（A / B / C + 新发现并修复的 D）

| 项 | v2 做法 | v2.1 做法 |
|---|---|---|
| **A 归一化** | PA 内 **min-max** `(x-min)/(max-min)+0.05` —— 抹掉绝对量级，且 0.05 floor 让零活动区仍分到份额 | **`x' = log(1+x)`，再 PA 内求和归一化** `s = x'/Σx'`；**无 min-max、无 0.05 floor** |
| **B 建筑层数** | 有 `building:levels` 用之，否则**一律按 1 层** → 79.4% 建筑退化为 footprint | 有实测（`building:levels` / `height÷3.2`）用之；缺失按**建筑类型先验层数**填入，先验由「有实测层数的同类型建筑中位数」推导（n≥20 采信，否则回退全局中位数 3） |
| **C 土地利用** | 代码内 `LU_FACTOR` 字典，键名与实际 `LU_DESC` 错位，**仅命中 23/33 类**，`PORT / AIRPORT` 等误落 0.20 | 改用 `landuse_class_mapping.csv` 的 `employment_factor`，**33/33 类全覆盖**，`WATERBODY`/`ROAD` = 0 |
| **D 建筑图层（本步新发现的 bug）** | 对 `osm-polygon` **全量 155,074 个多边形**求面积，未过滤非建筑；且用 `intersects` 做空间连接 | 只保留 `building` 标签非空的**真建筑 125,632 个**；改用**代表点质心归属唯一 Subzone** |

### D 的影响有多大（必须记录）

`osm-polygon` 图层里 **29,433 个多边形没有 `building` 标签**，总面积 5,961 km² —— 全部是行政边界/水域/陆地轮廓类大面（最大单个 **652.87 km²**）。v2 把这些都当成了"建筑面积"：

| | v2 / v2.1-前缀（未过滤） | v2.1（修复后） | 合理值参照 |
|---|---|---|---|
| 全岛建筑 footprint | 6,055 km² | **93.7 km²** | 新加坡国土 734 km²，建筑覆盖率 ~12% |
| 全岛 GFA | 31.1 亿 m²（前缀口径 1.90 万亿 m²） | **4.90 亿 m²** | 新加坡总 GFA 量级约 4–5 亿 m² |
| 建筑 footprint 中位数 | — | **223 m²** | 单栋建筑量级合理 |

修复后 shares 与修复前 Spearman = **0.975**，即该 bug 主要污染的是**量级**而非排序；但它让 v2 的 GFA 组件在物理上不可解释，必须在进入 Gravity 前修掉。

---

## 1. 运行结果

- **守恒**：逐 PA `Σ A_z ≡ E_PA`，最大绝对误差 `7.28e-12`、最大相对误差 **`1.89e-16`**（机器精度）
- **控制总量**：物理 44 PA = **1,935,235** = `attraction_total`（恒等）
- **零 attraction Subzone**：**25 个**（v1/v2/v2.1 完全一致，全部来自 11 个「仅居住端」PA，属预期设计）
- **建筑**：125,632 个建筑多边形；实测层数覆盖 25.1%（31,539），类型先验 74.9%（94,093）；mean levels **4.44**（v2 约 1.x）
- **LandUse 类别命中**：**33 / 33**

---

## 2. 核心指标：v1 → v2 → v2.1

| 指标 | v1 | v2 | **v2.1** | 判定 |
|---|---|---|---|---|
| 单 Zone 占 PA > 50% 数量 | 9 | 7 | **3** | ✅ 明显改善 |
| 单 Zone 占 PA > 60% 数量 | 7 | 6 | **2** | ✅ 明显改善 |
| 最大单 Zone 占比 | 95.5% | 95.5% | **81.9%** | ✅ 改善 |
| PA 平均 top-1 占比 | 32.6% | 29.3% | **19.4%** | ✅ 大幅改善 |
| ACRA=0 但 A>0 数量 | 17 | 17 | 17 | ➖ 未变（见 §5） |
| 零 attraction 数量 | 25 | 25 | 25 | ✅ 守住 |
| Spearman（对 v1 的份额） | — | 0.853 | **0.719** | v2.1 结构性差异最大 |
| Σ\|ΔA\|（对前一版，人） | — | 497,969 | 759,869 | 重分配量 ≈ 控制总量 39% |

> 统计口径说明：>50%/>60% **只在「有就业控制量的 PA」内统计**。若把 11 个无就业的居住端 PA 也算进去，会得到无意义的 11/10（这是 v2.1 首次运行时发现的统计口径问题，已修正）。

---

## 3. 之前被点名的异常集中区

| Subzone | PA | v1 | v2 | **v2.1** | 说明 |
|---|---|---|---|---|---|
| JURONG ISLAND AND BUKOM | WESTERN ISLANDS | 90.7% | 91.1% | **76.8%** | ✅ −14pp |
| MURAI | WESTERN WATER CATCHMENT | 78.9% | 79.7% | **54.3%** | ✅ −25pp |
| CHANGI AIRPORT | CHANGI | 76.4% | 68.2% | **42.2%** | ✅ −26pp |
| UPPER THOMSON | BISHAN | 79.9% | 63.0% | **36.5%** | ✅ −27pp |
| DHOBY GHAUT | MUSEUM | 62.9% | 61.0% | **38.9%** | ✅ −22pp |

**关键判断**：Jurong Island 仍有 76.8%，但这已**不是 min-max "凑"出来的**——Western Islands PA 只有 3 个 zone（Jurong Island & Bukom / Semakau 填埋岛 / Sudong 岛），Jurong Island 是其中唯一真实就业载体（1.35 km² 建筑 footprint、5.2 百万 m² GFA、1,354 栋建筑）。其份额由 `ACRA log 权重 + GFA + LandUse` 真实信号驱动，**属于结构性合理**，不建议再人为压低。

---

## 4. 空间量级核验（v2.1）

| 项 | 数值 | 参照 | 判定 |
|---|---|---|---|
| Σ 建筑 footprint | 93.7 km² | 国土 734 km² → 覆盖率 12.8% | ✅ 合理 |
| Σ GFA | 490 百万 m² | 新加坡总 GFA 约 4–5 亿 m² | ✅ 合理 |
| Σ LandUse 面积 | 784.8 km² | 与 Step 1 zone_dictionary 784.8 km² 一致 | ✅ 闭环 |
| 建筑 footprint / LandUse | 11.9% | 城市建筑覆盖率典型 10–20% | ✅ 合理 |

GFA Top 10：CHANGI AIRPORT 9.09M、TAMPINES EAST 8.10M、TAMPINES WEST 6.74M、TUAS VIEW EXTENSION 6.43M、KEMBANGAN 6.36M、MURAI 6.31M、JURONG ISLAND 5.22M …（均落在机场/工业区/高密度组屋区，符合常识）

---

## 5. 残留问题 1：17 个 `ACRA = 0 但 A > 0` 的 Subzone

**数量 v1/v2/v2.1 均为 17，未变化。** 分类后并不都是错的：

**(a) 真实"有作业活动但无注册办公地"—— 合理保留**

| Subzone | PA | 性质 | 份额 |
|---|---|---|---|
| SHIPYARD | BOON LAY | 船厂作业区 | 10.8% |
| GUL BASIN | PIONEER | 工业填土/作业区 | 7.8% |
| TENGEH | TUAS | 工业作业区 | 5.6% |
| SAFTI | JURONG WEST | 军事学院 | 4.5% |
| PLAB | PAYA LEBAR | 巴耶利峇空军基地 | 11.2% |
| AIRPORT ROAD | PAYA LEBAR | 机场附属 | 7.8% |

**(b) 非就业承载用地（应≈0，但拿到正份额）—— 待决策**

| Subzone | PA | 性质 | GFA | 份额 |
|---|---|---|---|---|
| LORONG HALUS | HOUGANG | 原填埋场 | **0** | 1.1%（纯 LandUse 兜底） |
| BAHAR | WESTERN WATER CATCHMENT | 实弹射击区 | 1,533 m² | 9.2% |
| SEMAKAU | WESTERN ISLANDS | 填埋岛 | 1.07e5 | 12.7% |
| SUDONG | WESTERN ISLANDS | 离岛 | 1.13e4 | 10.5% |
| SOUTHERN GROUP | SOUTHERN ISLANDS | 南部离岛群 | 8.67e4 | 18.1% |
| CONEY ISLAND | PUNGGOL | 离岛公园 | 4.70e4 | 4.7% |
| PULAU PUNGGOL TIMOR | SELETAR | 离岛 | 1.64e5 | 9.6% |
| MARINA EAST (MP) | MARINE PARADE | 填海未开发 | 1.21e5 | 7.3% |

> 这些 zone 的份额被 `LandUse`/`GFA` 从"次小"抬到 5–18%。**注意：它们所在 PA 的其余 zone 往往更小**，所以份额看似不低。绝对量不大，但进入 Gravity 会产生"住户 → 填埋场/离岛"的伪 OD。

**3B.2 建议（等你定，本轮未动）**：对 `allow_employment = False` 用地占绝对主导、且 `ACRA = 0` 的 zone，加一条**显式硬约束**把 `allow_employment` 纳入 `W_z`（例如 LU 组件的 `employment_factor` 改为按 `allow_employment` 门控），并在 `attraction_*_suspicious.csv` 中单独标记。

---

## 6. 残留问题 2：3 个单区 > 50% 的 PA

| Subzone | PA | 份额 | PA zone 数 | 判断 |
|---|---|---|---|---|
| SENTOSA | SOUTHERN ISLANDS | 81.9% | 2 | 结构性必然（PA 只有 2 区，Sentosa 是唯一就业载体） |
| JURONG ISLAND AND BUKOM | WESTERN ISLANDS | 76.8% | 3 | 结构性合理（见 §3） |
| MURAI | WESTERN WATER CATCHMENT | 54.3% | 3 | 结构性合理（其余为 Bahar 射击区等） |

**结论：3 个 >50% 全部可由 PA 的 zone 数与真实就业载体解释，无一是权重凑出来的。**

---

## 7. 组件相关性变化

| 组件 | v2 相关系数 | v2.1 相关系数 |
|---|---|---|
| ACRA | 0.761 | **0.622** |
| GFA | 0.184 | **0.303** |
| LandUse | 0.171 | **0.193** |
| POI | 0.551 | **0.462** |

含义：`log1p` 压缩了 ACRA 的绝对量级优势（ACRA 仍是第一信号，但不再"一票独大"）；**GFA 相关性从 0.184 升到 0.303 —— 说明修复建筑图层后 GFA 组件终于携带真实信息**，不再退化为"又一次面积权重"。

---

## 8. 待你决策

1. **是否冻结 `attraction_v2.1.csv` 进入 Step 4？**
   — 支持冻结：守恒达机器精度、量级全部合理、异常集中区明显缓解、>50%/>60% 降至 3/2 且均可解释。
2. **是否先做 3B.2（`allow_employment` 硬约束）再进 Step 4？**
   — 若担心 §5(b) 的伪 OD。

无论选哪条，**Step 4 的输入都已就绪**：`P_i`（Step 2）+ `A_j`（v2.1，332 行，逐 PA 守恒）。

---

## 9. 产物清单

```
reports/od_attraction_v21/
├─ attraction_v21.csv                     # 332 行，主表（含各组件与份额）
├─ attraction_v21_pa_validation.csv       # 逐 PA 守恒校验
├─ attraction_v21_suspicious.csv          # 单区>50% / ACRA=0&A>0 候选
├─ attraction_v1_v2_v21_comparison.csv    # 332 行 × 三版本 A 与份额
├─ attraction_v21_diagnostics.csv         # 诊断字段（组件、flag）
├─ attraction_v21_diagnostics.json        # 汇总指标
├─ attraction_v21_buildingfilter_impact.csv # 建筑过滤 bug 前后对比
├─ pa_employment_concentration.csv        # 逐 PA 的 top1 份额与 HHI（三版本）
├─ building_level_prior.csv               # 建筑类型先验层数（103 类，可人工标定）
├─ special_workplace_destinations.csv     # 3 个特殊虚拟目的地保留
└─ _prefix_buildingfilter_off/            # 建筑过滤修复前的快照（留档）
```

---

*执行模型：DeepSeek-V4.1-Flash（本会话）。本轮为脚本运行 + 数据分析，无人工权重调整。*
