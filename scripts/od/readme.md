# Singapore OD → MATSim 流水线 · `scripts/od` README

> 新加坡 **LTA / Census / ACRA / OSM** 开放数据驱动的 **OD 矩阵 → MATSim** 分步构建流水线。
> 空间体系：**332 Subzone → 55 Planning Area → 5 Region**，统一坐标 **EPSG:3414 (SVY21)**。
> 数据冻结目录：`Singapore_OD_MATSim_FinalData/`；动态数据：`Dynamic_2026_03_16/`。

---

## 0. 运行环境

| 项 | 值 |
|---|---|
| 工程根 | `D:\Luan\2026-05\2_Singapore` |
| Python | `C:/Users/LQP/miniconda3/python.exe`（pandas 3.0.1 / geopandas 1.1.3 / scipy 1.17.1 / shapely / numpy / pyarrow；**无 networkx**） |
| 运行方式 | `cd /d D:\Luan\2026-05\2_Singapore` → `python scripts\od\<script>.py` |
| Git-Bash 前置 | `export PATH="/usr/bin:/bin:/c/Windows/System32:/c/Windows:/c/Users/LQP/.workbuddy/binaries/PortableGit/versions/1.2.0/usr/bin:$PATH"` |
| **MATSim 运行时** | **`tools/matsim-2026.0/`**（官方 release：`matsim-2026.0.jar` + `libs/` 164 个依赖 jar，**无需 Maven/Gradle**） |
| **JDK** | **`tools/jdk-25.0.4.1+1/`**（Temurin 25，便携免管理员）。⚠️ MATSim 2026.0 用 **Java 25** 编译（class major 69），**Java 24 会 `UnsupportedClassVersionError`** |
| MATSim 入口 | `scripts/matsim/matsim_env.py`（定位 JDK + jar、拼 classpath、流式跑 Java）；`python scripts/matsim/matsim_env.py` 可打印完整环境 |

> ⚠️ **本机没有 networkx**：图论/最短路一律用 `scipy.sparse.csgraph`（C 实现）。
> ⚠️ **pandas 3.0 兼容**：`stack(dropna=False)` 已废弃；`to_numpy()` 返回只读数组，禁止 `arr *= x` 原地运算。
> ⚠️ MATSim 运行**不需要联网**，但 `MatsimXmlParser` 会先尝试下载 DTD（`SocketTimeoutException` 后自动回退 classpath 本地 DTD），属正常，可忽略。

---

## 1. 总流程设计

数据字典规定的完整链条：

```
Prior OD → Census constraint → MATSim → TrafficFlow calibration

Step 0  数据审计 / 接口体检
  ↓
Step 1  空间字典（332 Subzone 三级映射）
  ↓
Step 2  居住端产生量  P_i            （Table 88 / Table 97）
  ↓
Step 3  A 吸引量(初版) → B(v2) → B.1(v2.1)  就业吸引量 A_j（Table 118 控制）
  ↓
Step 4  有向机动车路网 + 332×332 最短旅行时间矩阵  C_ij^FF      ← 自由流
  ↓
Step 5A 双约束 Gravity + IPF（5 组 λ 敏感性）     Prior OD v1
  ↓
Step 5B  ① 无道路 Zone A=0  ② c_ii>0  ③ Table 118 Region×PA 约束   ← Census 约束基线（冻结）
  ↓
Step 5C  AM Peak 阻抗（LTA TrafficSpeedBands → OSM 边 → C_ij^AM,v1）
  ↓
Step 5C.1 AM 速度覆盖增强（几何 + 同名三级传播）→ C_ij^AM,v2
  ↓
Step 5C.1 Prior OD  AM-v2 阻抗 + 5B 约束框架 → T_ij^(5C.1)（5 组 λ）
  ↓
Step 6.1 OSM 有向路网 → MATSim `network.xml.gz` + Zone→node 映射
  ↓
Step 6.2 Prior OD → MATSim population/plans（car-only，200k agents × 3 λ）
  ↓
Step 6.2B OD-cell 保底采样 + 住宅/就业空间下分 → 100% 可回溯 population
  ↓
Step 6.3a 连通性修复：NetworkCleaner → network_cleaned.xml.gz + 端点重吸附 population  ← 本轮
  ↓
Step 6.3b 第一次 MATSim AM assignment（单迭代 QSim）→ q_a^sim / v_a^sim / t_a^sim     ← 本轮
  ↓
Step 6.3c 第一次 q_a^sim vs q_a^obs 对照（1,278 LTA 链路，AM）
  ↓
Step 6.3.2 LTA 观测 ↔ 断面 Crosswalk 重构（沿线采样+路名一致+逐断面中位）→ 排除 crosswalk 粒度疑点
  ↓
Step 6.3.3A TrafficFlow 驱动 AM 出发时刻剖面（07–08=48.71% / 08–09=51.29%）→ 消除 08:00 单点脉冲
  ↓
Step 6.3.3B 重跑 3λ AM assignment + 逐小时 q_sim(Link,Hour) vs q_obs(Link,Hour)
  ↓
Step 7.1 TrafficFlow Calibration Target 构建（q_obs↔q_sim 冻结靶场 + 统一指标 + RoadCat 分层）
  ↓
Step 7.2 参数审计（config/network 全量抽取 + capacity-only sweep 计划，不改任何模型）  ← 本轮
  ↓
Step 7.2.2 Capacity-only sensitivity 扫描（0.50/0.75/1.00/1.25/1.50）  ✅ PASS：**capacity 非结构杠杆（CATA/SLIP 比值恒 0.366）**
  ↓
Step 7.3.1 Congestion-feedback sensitivity（1/5/10/20 迭代拥堵反馈）  ✅ PASS：**拥堵反馈也非结构杠杆（比值 0.366→0.377、r_CATA 仍≈0）**
  ↓
Step 7.3.2A Motorway–Ramp 连通性审计（纯拓扑、零仿真）  ← 本轮 PASS：**主线连续、接口完整 → 不修网络**
  ↓
Step 7.3.2B Route-structure / Path-choice 诊断（plans 路径序列 × 等级分类）  ← 本轮 PASS：**A"不走高速"被否定（61% 路线用 motorway、41.5% 长度）；0/196,447 OD 多路径**
  ↓
Step 7.3.3 route×crosswalk 断面级对照（分辨 B 分散 vs C 表达差异）→ Step 7.4 λ 敏感性 → Step 7.5 联合校准
```

三层阻抗并存，供 MATSim 阶段做敏感性分析：

```
C^FF        reports/od_impedance/impedance_matrix.parquet
C^AM,v1     reports/od_impedance_ampeak/ampeak_impedance_matrix.parquet
C^AM,v2     reports/od_impedance_ampeak_v2/ampeak_impedance_v2.parquet
```

**核心模型（Step 5 系列）**：

```
T_ij = α_i · β_j · P_i^phys · A_j · exp(−λ · c_ij)        α/β 由 IPF 交替缩放求得
P_i^phys = r · P_i ,  r = 1,935,235 / 2,208,356 = 0.876324
```

---

## 2. 脚本清单与代码设计

| # | 脚本 | 作用 | 主要输入 | 主要输出 | 状态 |
|---|---|---|---|---|---|
| 0 | `audit_all.py` | 数据体检（不修改原始数据），覆盖空间一致性/字段质量/口径 | `Singapore_OD_MATSim_FinalData/` | `reports/od_audit/` | ✅ PASS |
| 1 | `build_zone_dictionary.py` | 构建 332 Subzone / 55 PA / 5 Region 统一空间字典 | `01_Boundary_TAZ/` | `reports/od_zone/zone_dictionary.csv` | ✅ PASS |
| 2 | `build_production.py` | 居住端产生量 `P_i^work` / `P_i^car` | T1（Table 88）、T8（Table 97） | `reports/od_production/production.csv` | ✅ PASS |
| 3A | `build_attraction.py` | 就业吸引量 v1（四组件用地强度） | ACRA / MasterPlan / Census | `reports/od_attraction(_v1)/` | 历史版本 |
| 3B | `build_attraction_v2.py` | 吸引量 v2（PA 内 min-max 归一） | 同上 | `reports/od_attraction_v2/` | 历史版本 |
| 3B.1 | `build_attraction_v21.py` | 吸引量 **v2.1**（log1p 归一 / 建筑层数先验 / 33 类 LandUse 映射） | 同上 | `reports/od_attraction_v21/attraction_v21.csv` | ✅ **冻结** |
| — | `attraction_diagnostics.py` | 只读诊断：v1 vs v2 | v1/v2 产物 | `reports/od_attraction_v2/*diagnostics*` | 诊断 |
| — | `attraction_diagnostics_v21.py` | 只读诊断：v1 / v2 / v2.1 三方对比 + 空间合理性 | v1/v2/v2.1 产物 | `reports/od_attraction_v21/*diagnostics*` | 诊断 |
| 4 | `build_impedance.py` | 有向机动车路网 + 332×332 `C_ij^FF`；导出 `network_links/nodes` | `07_RoadNetwork/osm-lines_expanded.shp` | `reports/od_impedance/` | ✅ **冻结** |
| 5A | `build_prior_od.py` | 双约束 Gravity + IPF，5 组 λ 扫描 | production / attraction / impedance | `reports/od_prior/` | ✅ PASS（保留） |
| 5B | `build_prior_od_5b.py` | **Census 约束基线**：无路网 A 清理 + c_ii 修正 + Table 118 + IPF | + T11（Table 118）、snap | `reports/od_prior_5b/` | ✅ **冻结基线** |
| 5C | `build_am_peak_impedance.py` | LTA SpeedBands → AM 速度 → `C_ij^AM,v1` | `Dynamic_2026_03_16/realtime_monitoring/`、`historical_data/TrafficSpeedBands_Links.shp` | `reports/od_impedance_ampeak/` | ✅ PASS（AM-v1，保留） |
| 5C.1a | `enhance_ampeak_network.py` | **AM 速度覆盖增强**：几何 + 同名三级传播 → `C_ij^AM,v2` | 同上 + Step 4 `network_links`(含 name) | `reports/od_impedance_ampeak_v2/` | ✅ PASS |
| 5C.1b | `build_prior_od_5c1.py` | **AM-v2 阻抗 + 5B 约束框架** → 5 组 λ 候选 Prior OD `T_ij^(5C.1)` | `ampeak_impedance_v2.parquet` + T11 + snap | `reports/od_prior_5c1/` | ✅ **PASS** |
| — | `compare_prior_od.py` | 只读对比：`T^5B` vs `T^5C.1`（时长/区内/跨区/长距离/块流量）+ 守恒校验 | 5B / 5C.1 产物 | `reports/od_prior_5c1/compare_*.csv` | 诊断 |
| 6.1 | `build_matsim_network.py` | **MATSim 网络底座**：Step 4 有向路网 → `network.xml.gz` + Zone→node 映射 | `od_impedance/network_links.csv`、`network_nodes.csv`、snap | `reports/matsim_network/` | ✅ **PASS（已冻结）** |
| — | `validate_matsim_network.py` | 独立复核 `network.xml.gz` 结构不变量 + Zone 映射（不信任自报告 JSON） | `network.xml.gz`、`zone_matsim_node_map.csv` | `network_independent_check.json` | 诊断 |
| 6.2 | `build_matsim_population.py` | **Prior OD → MATSim population/plans**：car-only OD + 多测度抽样 agent + home/work 挂 network link | `prior_od_5c1_lambda_*.parquet`、`production.csv`、T11、`zone_matsim_node_map.csv`、`network_links_source_copy.csv` | `reports/matsim_population/` | ✅ **PASS（第一版基线，已冻结）** |
| — | `validate_matsim_population.py` | 独立复核 `population_*.xml.gz`：activity link 存在且邻接、zone 映射一致、expansion 守恒 | `population_*.xml.gz`、`network.xml.gz`、`zone_matsim_node_map.csv` | `population_independent_check.json` | 诊断 |
| 6.2B | `build_matsim_population_6_2b.py` | **OD-cell 保底采样 + 住宅/就业空间下分**：每正 cell ≥1 agent + URANOF(DU 加权)/Building → home link、POI/Building → work link | `matsim_population/car_prior_od_*.parquet`、`04_LandUse_Building/*.geojson`、`05_POI_Enterprise/poi.csv`、`01_Boundary_TAZ/*.geojson`、network copy | `reports/matsim_population_6_2b/` | ✅ **PASS（本轮）** |
| — | `validate_matsim_population_6_2b.py` | 独立复核 6.2B：100% cell 覆盖、ΣEF=459,794、每 cell 精确重构、link 存在且与 node 一致、plan 结构与元素名 | `population_lambda_*.xml.gz`、`network.xml.gz`、6.2 car OD | `population_6_2b_independent_check.json` | 诊断（本轮） |
| 6.3.2 | `build_linkflow_crosswalk_6_3_2.py` | **LTA 观测 ↔ 断面 Crosswalk 重构**：沿线采样 + 路名一致收紧候选（中位 8 边/断面），逐断面取**中位数**为断面流量（median/mean/max/sum 四口径 + RoadCat 分解）；`--mode generous` 可复现原稿伪影 | `TrafficFlow_Links.shp`、`TrafficFlow_Data.json`、`network_links/nodes_source_copy.csv`、`reports/matsim_assignment/lambda_*` | `reports/matsim_assignment_6_3_2/`（STEP6_3_2_REPORT.md + section_flow_* + crosswalk） | ✅ **PASS** |
| 6.3.3A | `build_departure_profile_6_3_3a.py` | **TrafficFlow 驱动 AM 出发时刻剖面**：每 LinkID×Hour 工作日逐日中位数 → 全网 07/08 时间形状 → 3λ population 按 EF 守恒分配出发小时 + 小时内秒级随机微扰 → 流式改写 `home` 活动 `end_time`（不改 OD/λ/空间结构） | `TrafficFlow_Data.json`、`reports/matsim_population_6_2b_connected/`（agent csv + population xml） | `reports/matsim_departure_6_3_3a/`（STEP6_3_3A_REPORT.md + departure_profile.csv + 3×population xml.gz + assignment csv + validation.json） | ✅ **PASS** |
| 6.3.3B | `compare_step6_3_3b.py` | **逐小时对照**：用 6.3.2 tight crosswalk 把 3λ linkstats 汇总成 `q_sim(Link,Hour)`，与 `q_obs(7-8)/(8-9)` **逐小时**对照（`r_7/r_8/r_AM`、`GEH_7/GEH_8`、`ratio_7/ratio_8`、RoadCat 分解）；并从 `output_legs/persons` 算 **EF 加权通勤时间/距离** 与出发时刻分布 | `reports/matsim_assignment_6_3_3b/lambda_*/ITERS/it.0/*.linkstats.txt.gz`、6.3.2 crosswalk、`TrafficFlow_Data.json`、`TrafficFlow_Links.shp` | `reports/matsim_assignment_6_3_3b/`（STEP6_3_3B_REPORT.md + hourly_metrics + by_roadcat + section_hourly + departure_and_travel） | ✅ **PASS** |
| 7.1 | `build_calibration_target_7_1.py` | **TrafficFlow 校准靶场**：LTA `TrafficFlow`（工作日逐日中位 → LinkID×Hour 中位）× 6.3.3B linkstats（`HRS7-8avg`/`HRS8-9avg` × scale 2.29897）经 6.3.2 tight crosswalk（断面内取**中位**）对齐；输出总体 + **LTA `RoadCat` 分层**的 `r/ρ/MAE/RMSE/MAPE/WMAPE/Bias/Sim-Obs/GEH<5/GEH<10`；**不改任何模型参数** | 6.3.3B linkstats、6.3.2 crosswalk、`TrafficFlow_Data.json` | `reports/od_calibration_7_1/`（STEP7_1_REPORT.md + 3×calibration_target_lambda_*.csv + summary + by_roadcat + definition.json） | ✅ **PASS（本轮）** |
| 7.2 | `audit_matsim_calibration_7_2.py` | **MATSim 参数审计 + capacity sweep 计划**：解析全部 config XML（`<param name value/>` 属性 → 逐参数展开）+ 解析 `network_cleaned.xml.gz` 逐边 `capacity/permlanes/freespeed` 并按 `e{from}_{to}` 与 source copy 合并 + 复制 7.1 靶场基线 + 预置 capacity-only sweep 计划（0.50/0.75/1.00/1.25/1.50，**仅计划不执行**）；**不改任何模型** | `matsim/step6_3/*.xml`、`network_cleaned.xml.gz`、`network_links_source_copy.csv`、7.1 summary | `reports/od_calibration_7_2/`（parameter_audit/config_summary/network_capacity_audit/calibration_target_baseline/capacity_sweep_plan + step7_2_audit.json） | ✅ **PASS** |
| 7.2.2 | `run_capacity_sweep_7_2_2.py` | **Capacity-only sweep runner**：复用 `make_config_6_3.build_one` 同源重建 config 后仅 patch `flowCapacityFactor=storageCapacityFactor=f`（MATSim 2026.0 引擎强制同值）+ 输出目录/runId；`--smoke N`（f=0.75、N agents 验证 patch）+ `verify_patch` 读回断言 | 6.3.3A population、`network_cleaned.xml.gz`、6.3.3B config 语义 | `reports/od_calibration_7_2_2/capacity_factor_*/`（5 档 MATSim 输出）+ `matsim/step6_3/config_capf_*.xml` | ✅ **PASS（本轮）** |
| 7.2.2 | `compare_capacity_sweep_7_2_2.py` | **sweep 对照**：直接 import 7.1 的 `obs_load/cross_load/metric`（**完全复用冻结靶场口径**），对 5 档 linkstats × scale 2.29897 计算 summary/by_roadcat/sections/ratio_pivot 四表 + `f1p00_vs_frozen_633b_consistency.json`（f=1.00 与 6.3.3B 逐位核对） | 7.1 靶场模块、5 档 linkstats、6.3.2 crosswalk | `reports/od_calibration_7_2_2/`（4 CSV + 2 JSON + STEP7_2_2_REPORT.md） | ✅ **PASS（本轮）** |
| 7.3.1 | `run_congestion_feedback_7_3_1.py` | **拥堵反馈 runner（唯一变量 = lastIteration）**：复用 `build_one` 同源 + patch `lastIteration`（capacity 固定 1.0、ReRoute/TTC 基线不动）+ 磁盘控制（中间迭代不写 events/plans/trips/snapshots，linkstats 每迭代保留）+ **嵌套设计**（一次 20 迭代覆盖检查点 1/5/10/20 ↔ it.0/4/9/19 + 一次 5 迭代验证嵌套性）；`--smoke N`（N agents × 3 迭代验证 ReRoute 逐轮生效） | 6.3.3A population、`network_cleaned.xml.gz`、6.3.3B config 语义 | `reports/od_calibration_7_3_1/iterations_20/`（it.0–19 linkstats）、`iterations_05/`（嵌套验证）+ `config_cf_it*.xml` | ✅ **PASS（本轮）** |
| 7.3.1 | `compare_congestion_feedback_7_3_1.py` | **拥堵反馈对照**：import 7.1 冻结靶场口径，对 20 迭代逐迭代算 summary/by_roadcat/sections + **结构轨迹表**（CATA ratio、SLIP ratio、CATA/SLIP 比值、r_CATA × 3 窗 × 20 迭代）+ 检查点表 + `nesting_check.json`（it5↔it20 逐位）+ `it0_vs_frozen_633b_consistency.json`（与 6.3.3B 逐位） | 7.1 靶场模块、iterations_20/05 linkstats、6.3.2 crosswalk | `reports/od_calibration_7_3_1/`（5 CSV + 3 JSON + STEP7_3_1_REPORT.md） | ✅ **PASS（本轮）** |
| 7.3.2B | `diagnose_route_structure_7_3_2b.py` | **路径结构诊断**：解析 6.3.3B it.0 `plans.xml.gz`（route type=links 单行正则）+ `trips.csv.gz` 对接 200k agents，构造 `e{from}_{to}` 接 `network_links_source_copy.csv` 等级/长度（**单次遍历 + 字典视图**），输出逐 agent 诊断 + 等级长度占比 + 等级间转移矩阵 + OD 路径一致性 + A/B/C 三分判定；**只诊断不改模型** | 6.3.3B it.0 plans/trips、`network_links_source_copy.csv` | `reports/od_route_diagnosis_7_3_2b/`（5 产物 + STEP7_3_2B_REPORT.md） | ✅ **PASS（本轮）** |

> 7.3.2A Motorway–Ramp 连通性审计在用户外部环境执行，产物归档 `reports/od_calibration_7_3_2a/`（无项目内脚本）。

> `_backup/audit_all_baseline.py`：Step 0 基线留档；`__pycache__/`：解释器缓存。

### 2.0 `scripts/matsim/` — MATSim 运行与对照（Step 6.3 新增）

| # | 脚本 | 作用 | 主要输入 | 主要输出 | 状态 |
|---|---|---|---|---|---|
| — | `matsim_env.py` | 定位项目本地 **JDK25 + MATSim 2026.0**，拼 `classpath`（`matsim-2026.0.jar;libs/*`），流式启动 Java 主类 | `tools/jdk-25*/`、`tools/matsim-2026.0/` | 运行环境（`describe()`） | ✅ |
| 6.3a | `prepare_connected_scenario.py` | 连通性修复：跑官方 `org.matsim.run.NetworkCleaner` 产出 `network_cleaned.xml.gz`（car 主连通分量）；把端点落在碎片里的 agent 重吸附到最近主分量 link（KD-tree），并加 `homeRepairM`/`workRepairM` | `reports/matsim_network/network.xml.gz`、`reports/matsim_population_6_2b/population_*.xml.gz` | `reports/matsim_network/network_cleaned.xml.gz`、`connectivity_repair.json`、`reports/matsim_population_6_2b_connected/` | ✅ **PASS** |
| 6.3b | `make_config_6_3.py` | 以 `CreateFullConfig` dump 的 `fullConfig_2026_0.xml` 为基线，逐项覆盖生成 3 套 config（单迭代 QSim + linkStats） | `matsim/step6_3/fullConfig_2026_0.xml` | `matsim/step6_3/config_lambda_*.xml` | ✅ |
| 6.3b | `run_step6_3.py` | 极小 runner：生成 config → 用本地 JDK25 跑 `org.matsim.run.RunMatsim` → 日志落 `matsim/step6_3/logs/`（支持 `--smoke N`） | `config_lambda_*.xml` | `reports/matsim_assignment/lambda_*` | ✅ **PASS** |
| 6.3c | `compare_step6_3.py` | **第一次对照**：linkstats → 每 LTA 链路 `q_a^sim`；与 `TrafficFlow_Data.json`（LinkID×Hour，AM）对照；raw/scaled + GEH + RoadCat 分解 + Top-20 | `ITERS/it.0/*.linkstats.txt.gz`、`lta_osm_match_v2.csv`、`TrafficFlow_Data.json` | `reports/matsim_assignment/STEP6_3_COMPARISON.md` + `step6_3_*.csv` | ✅ **PASS** |

### 2.1 Step 4 的设计要点

- **机动车网络**：`motorway/trunk/primary/secondary/tertiary/residential/service/unclassified` 及 `*_link`；**排除** `footway/steps/cycleway/path/pedestrian`。
- **速度**：优先 OSM `maxspeed`（支持 km/h、mph），缺失回退 highway 默认速度。
- **方向**：`oneway=yes→正向`，`-1→反向`，`no/空→双向`；**不做对称化**（`c_ij ≠ c_ji` 属正常）。
- **节点**：按 0.1 m 网格合并；**Subzone 质心吸附到最大强连通分量 (giant SCC) 内最近节点**（弱分量曾命中单向死胡同，致 661 个不可达 OD）。
- **最短路**：`scipy.sparse.csgraph.dijkstra`（单源、有向）。
- **`network_links.csv` 列**：`from_node,to_node,travel_time_s,length_m,speed_kmh,highway,lanes,name`
  → `name`/`lanes` 是 Step 5C.1 同名传播的**必要输入**（本轮新增）。

### 2.2 Step 5B 的设计要点

- **无道路接入 Zone 清理**：5 个离岛/无路网 Subzone 的 `A_j = 0`，并在其 Workplace PA 内**重新归一化**，保持 PA 就业总量守恒：
  `A'_j = E_PA · A_j / Σ_{k∈PA, k∉R} A_k`
- **区内阻抗修正**：`c_ii = 0.5 × median(C_i,k1…k5)`（最近 5 个其他 Subzone 的旅行时间中位），消除 `c_ii=0` 造成的区内自环过度加权。
- **Table 118 约束**：四种方式合并为 `ResidenceRegion × WorkplacePA` 块约束，经 IPF 注入。
- **命名口径**：`physical_workplace_mass_share = 0.876324`（**不是**"87.63% 居民去实体 workplace"，而是对齐 332×332 物理 OD 与 Census PA 吸引的**质量分配系数**；缺 Subzone 级 Other/NoFixed/WFH 居住分布，按居住产生量比例分摊，**假设保留**）。
- **可复用参数**：`--out` / `--prefix` / `--impedance` / `--label`，因此同一脚本可跑 5B / 5C / 5C.1 的 OD。

### 2.3 Step 5C / 5C.1 的设计要点

- **数据源辨析（关键）**：`TrafficSpeedBands_v4.json` 是 **2026-05-05 18:53 的单次快照**，不是 AM 聚合；AM 数据在
  `realtime_monitoring/`（144 个 / 7.4 GB），其中**工作日 07:00–09:59 仅 12 个快照**（05-06 周三 + 05-07 周四，各 6 次），每档 **143,787 条**。按**文件名时间戳预筛**只读这 12 个，避免解析全部 7.4 GB。
- **几何源**：`TrafficSpeedBands_Links.shp`（**143,787** 条，与 JSON 一一对应），**不是** `TrafficFlow_Links.shp`（仅 1,278 条交通量断面）。
- **⚠️ SpeedBand=8 哨兵值**：LTA 对 `SpeedBand=8`(≥70 km/h 开放档) 把 `MaximumSpeed` 编码为 **999**（不是 999 km/h）。护栏必须显式处理，否则 `(70+999)/2 = 534.5 km/h` 会污染所有高速。
- **5C.1 三级传播**（逐边记录 `assignment_tier`）：
  | tier | 规则 | 说明 |
  |---|---|---|
  | `geom` | LTA Link 质心 → 最近 OSM 边（≤`geom_max_m`），路名一致优先 | 最高置信度 |
  | `name+hw` | 同名 且 highway 组与该路名已命中边一致 | 高置信度 |
  | `name` | 仅同名 | 较低置信度 |
  | `none` | 未传播 | 保留 Step 4 free-flow 速度 |
- **路名归一化**：大写、标点/连字符→空格、常见后缀缩写（AVENUE→AVE…），LTA / OSM 两侧一致（解决 `Pan-Island Expressway` ↔ `PAN ISLAND EXPRESSWAY`）。实测 **95.7% 的 LTA 路名能在 OSM 命中**。
- **软护栏**：AM 速度 ≤ free-flow × 1.5，且 ≥ 5 km/h（超限裁剪并计数 `am_over_ff_clipped`）。
- **不使用** `TrafficFlow` 的 Volume 反推速度（Volume 用于 Step 7 校准）。

### 2.4 Step 6.1 的设计要点（MATSim 网络底座）

- **纯转换、零掺入**：只把 Step 4 已验证的有向路网转成 MATSim XML，**不引入** 5C.1 Prior OD、TrafficFlow 或拥堵机制。
- **`network.xml.gz`**：根 `network(changeEvents=false)` → `nodes(format=matsim)` + `links(capperiod=01:00:00)`。
  - `freespeed = speed_kmh / 3.6`（m/s，源自 Step 4）；`length` 用 Step 4 的 `length_m`（米）；节点坐标为 **EPSG:3414 (SVY21)**。
  - `link id = e{from}_{to}`（有向边唯一，0 重复）；每条有向边单独成 link，`oneway=1`、`modes=car`。
- **`capacity` / `permlanes` = 假设值（非观测）**：`permlanes = OSM lanes（合理 1–20）否则按道路等级默认`；`capacity = permlanes × 等级默认 veh/h/lane`。
  - **所有假设参数落盘在 `network_validation.json`**，Step 7 校准时可单独校正，**不与 OD 校准混为一谈**。
- **Zone→MATSim node 映射**：直接用 Step 4 的 `zone_network_snap.nearest_node`（Subzone 质心在 giant SCC 内的最近节点），输出 `zone_matsim_node_map.csv`（332 行，含 `snap_distance_m`）。
  - 吸附中位 26 m / p90 154 m；仅 **5 个无道路离岛**（NORTH-EASTERN ISLANDS、SOUTHERN GROUP、PULAU SELETAR、SEMAKAU、SUDONG）>1000 m（最大 6.34 km）——它们 **P=0 且 A=0**，不产生/不吸引出行，该吸附值无实际影响。
- ⚠️ **性能**：原脚本对 706,554 条边做 `pd.Series(r._asdict())` 逐行构造（≈9 min）→ 已向量化（`lanes_vec` / `capacity_vec`），**9m00s → 38.5s（14×）**，XML 内容逐字节一致（已用固定 gzip mtime 复核，`sha256(uncompressed)=7b81b8e8…`）。
- ⚠️ **不要用 `network.xml.gz` 的文件哈希做内容比对**：gzip 头内嵌写入时间 MTIME，每次运行都变；要比内容请比对**解压后**字节。

### 2.5 Step 6.2 的设计要点（Prior OD → population/plans）

- **链路**：`T_ij^(5C.1)`（all-mode）→ 用 **Step-2 car production `car_work_trip_production`** + **Table 118 car-only `ResidenceRegion×WorkplacePA`** 重投影为 car-only OD（总量 459,794）→ 多测度抽样 agent → 挂 network link。
- **目的地列边际必须用冻结的 cleaned 吸引**（`workplace_attraction_clean`，无路网离岛已置 0，304 个非零），**不能用 raw `workplace_attraction`**（307 个非零）。否则多出的 3 个目标列（zone 258/322/323）无 seed 支撑 → IPF 不收敛。（见 §7 变更记录「修复」）
- **行边际** = `car_work_trip_production`（列名易错，**不是** `car_work_production`）。
- **不能 1 OD cell = 1 agent**：按 `trips` 体积做多项抽样（`target=200k`），每 cell 存 `expansion_factor = trips/cell_agent_count`。
  - ⚠️ **已知特性（6.2 第一版）**：按体积抽样下 ~59% 的 OD cell 被覆盖、代表 ~93.8% 出行量（小 cell 期望 agent<1 被漏掉）。
  - ✅ **Step 6.2B 已改为「每非零 cell 保底 1 个 agent + 剩余按 largest-remainder」** → cell 覆盖 100%、expansion Σ 精确 = 459,794、每 cell 可精确回溯。
- **activity 用 MATSim link id，不是 node id**：Zone→`matsim_node_id` 后，取该节点**关联 link**（`incident_link_map`，对每条边 `e{from}_{to}` 注册其两端节点，setdefault 取首个）作为 home/work link。避免生成 `activity link=<node_id>` 这种 MATSim 无法解释的写法。
- **特殊就业质量不外挂**：`Works from Home` / `No Fixed Location for Work` / `Other Planning Areas or Outside Singapore` 继续单独保留，**不塞进 332×332**。
- **XML 结构**：`population > person(id) > attributes(originZone/destinationZone/homeNode/workNode/expansionFactor) + plan(selected=yes)[ activity(home,link)+leg(car)+activity(work,link) ]`。
- ⚠️ **性能**：XML 生成用 `itertuples`（非 `iterrows`）；全套 3×200k 约 **1m49s**。

### 2.6 Step 6.2B 的设计要点（OD-cell 保底 + 空间下分）

- **保底采样**：`N_ij = 1 + floor(rem·w_ij)`，余量按 largest-remainder 分配 → `Σ N = target` 精确；
  `EF_ij = T_ij / N_ij` → `Σ_{a∈cell} EF = T_ij`，**每个 cell 都能被 agent 精确重建**。
  - 副作用（预期）：小 cell 的 **EF 可 < 1**（1 个 agent 代表不足 1 次出行）；EF 变为**逐 cell 系数**而非统一倍数。
- **⚠️ POI 列名与坐标系（致命）**：`poi.csv` 坐标列是 **`lng`/`lat`（WGS84 度）**，不是 `x/y`。
  第一版检索 `x|lon|longitude` → **`lng` 不匹配 → POI 池静默为空 → Work 空间下分从未生效**。
  且 WGS84 经纬度必须 **重投影 EPSG:3414** 后再吸附（网络是 SVY21 米制）。
- **⚠️ MATSim 元素名是 `<activity>`（致命）**：`population_v6.dtd` 为 `<!ELEMENT plan (attributes?, (activity|leg)*)>`，
  `PopulationReaderMatsimV6` 的 `case ACT` 且 `ACT="activity"`；`<act>` 会触发 `"[tag=... not known"` 异常。**不是 `<act>`。**
- **node ↔ link 一致性**：activity 的 node 取**该 link 的 `from_node`**（空间节点）；zone node 另存 `*_zone_node`。
- **Home 按 DU 加权**：`URANoofDwellingUnits.DU`（套数）为权，落点与住宅容量成比例；无住宅候选回退 Building。
- **Work 用 POI，不造 ACRA 坐标**：ACRA 空间定位率仅 ~82%，不拿未确认邮编硬凑空间点。
- **空间离散度**：home link **17,052** 条、work link **5,782** 条（6.2 各 ≤332）；每 origin zone 的 home link 中位 **40** / 最大 651。
- **性能**：候选点按 zone **只吸附一次**（cKDTree），逐 cell 向量化采样；3×200k **53 s**。

### 2.7 Step 6.3 的设计要点（连通性修复 + 第一次 AM assignment）

#### 2.7.1 为什么必须做连通性修复（6.3a）

- MATSim 的 `NetworkRoutingProvider.checkNetwork()` 会对 car 网络调 `NetworkUtils.cleanNetwork()`，
  **只要有 1 条 link/node 被移除就直接抛异常中止**：
  `"Network for mode 'car' has unreachable links and nodes ... Aborting."`
- 冻结的 OSM 有向路网天然有碎片（单向死胡同/未接回主干的支路）。实测：
  - `706,554` 有向边 → car 主连通分量 **`693,575`**（移除 **1.84%**）
  - `429,032` 节点 → **`421,406`**（移除 1.78%）
  - **332 个 Subzone 锚点节点全部保留（0 受影响）**
- **决策：修复而非绕过**。备选 `networkRouteConsistencyCheck=disable` 会让端点落在碎片里的 agent
  无路可走；直接删需求会损失真实 OD。故：
  1. `NetworkCleaner` 产出 `network_cleaned.xml.gz`（**原 `network.xml.gz` 保持冻结不动**）；
  2. 把 home/work link 不在主分量的 agent **重吸附**到最近主分量 link（cKDTree 最近邻），
     实测位移：中位 **3.3 m**、p90 41.5 m、p95 63.9 m、max 518 m；受影响 agent **5,066–5,156 / 200,000（≈2.55%）**；
  3. 被修复的 agent 在 XML 里新增 `homeRepairM`/`workRepairM`（未修复=0），可事后追溯。
- 结果：car 连通性检查 **0 边被移除**，QSim `lost=0`。

#### 2.7.2 第一次 AM assignment（6.3b）

- **单次迭代**（`firstIteration=lastIteration=0`）：人口（无 route）--ReRoute 权重 1.0--> 最短路 --QSim--> link volume/traveltime。
  这就是用户要的「纯 AM peak static assignment baseline」，**不掺任何复杂行为模型**。
- **config 以 `CreateFullConfig` 为基线**：MATSim 参数名逐版本会变（2026.0 是 `overwriteFiles`
  而**不是**老的 `overwriteFileSetting`），凭记忆手写最小 config 极易踩「参数不存在」。先用官方
  `org.matsim.run.CreateFullConfig` dump 当前版本完整默认配置，再逐项覆盖，保证合法。
- 关键覆盖项：
  - `global.coordinateSystem=EPSG:3414`（与网络一致）、`numberOfThreads=8`
  - `network.inputNetworkFile` = `network_cleaned.xml.gz`
  - `plans.inputPlansFile` = `reports/matsim_population_6_2b_connected/population_lambda_*.xml.gz`
  - `controller.mobsim=qsim`、`firstIteration=lastIteration=0`、`compressionType=gzip`
  - `qsim.mainMode=car`、`flowCapacityFactor=1.0`、`storageCapacityFactor=1.0`
  - `linkStats.writeLinkStatsInterval=1`（**必须设 1，否则迭代 0 不写 linkstats 文件**）
  - `replanning` 只留 ReRoute 权重 1.0；`scoring` 补 `home`/`work` 的 `activityParams`
- **`startTime/endTime` 保留 `undefined`** → `simStarttimeInterpretation=maxOfStarttimeAndEarliestActivityEnd`
  → 从最早活动结束时刻（08:00）开始跑到车队清空。
- **linkstats 输出格式**（`CalcLinkStats.writeFile`，154 列，tab 分隔）：
  `LINK, ORIG_ID, FROM, TO, LENGTH, FREESPEED, CAPACITY, HRS0-1{min,avg,max} … HRS23-24{…}, HRS0-24{…}, TRAVELTIME0-1{…} … TRAVELTIME23-24{…}`。
  单迭代下 `avg == sum` = 实际量。**`HRS7-8avg` = 第 29 列（0-based）**、`HRS8-9avg` = 第 32 列、`TRAVELTIME7-8avg` = 第 104 列。
- ⚠️ **`CalcLinkStats` 的 `volScaleFactor` 只在 `readFile` 生效，`writeFile` 不乘** → 规模放大必须在 Python 侧做。

#### 2.7.3 第一次对照口径（6.3c）

- **对照链路**：`LTA TrafficFlow LinkID` →(`lta_osm_match_v2.csv`)→ `osm_edge_index`
  →(`network_links_source_copy.csv` 行号)→ `(from_node,to_node)` → `MATSim link id = e{from}_{to}`。
  1,311 条 TrafficFlow 链路中 **1,278** 条有几何匹配。
- **规模口径（必读）**：population 是 **200,000 agents 代表 459,794 次 car 出行**
  （`EF_ij = T_ij/N_ij`）。linkstats 计的是实际车辆（200k），故与真实观测对照需乘
  `scale = ΣEF/N = 459,794/200,000 = 2.29897`。**scaled 为主口径**。
- **时窗口径（必读）**：冻结 population **全部 200,000 个 agent 的 home `end_time` = 08:00:00**、
  work 无 `end_time` → QSim 在 08:00 一次性释放全部 AM 需求 → **`HRS7-8` 恒为 0**，
  流量全在 `HRS8-9`。主对照取 sim `HRS8-9`（=整个 AM 脉冲）vs obs `(hour7+hour8)`（=整个 AM 窗口）。
- 指标：`sim/obs`、Pearson r、Spearman ρ、NRMSE、MAPE、**GEH**（=√(2(M−C)²/(M+C))，报 %GEH<5/<10）。

### 2.8 Step 6.3 第一次对照结果与诊断

- 结果（scaled 主口径，λ=0.05/0.075/0.10）：`Σsim/Σobs` = **0.647/0.646/0.648**；
  Pearson r = **0.306/0.308/0.308**；GEH<5 = **7.5%/8.4%/8.5%**。
- **λ 几乎不可分辨** → 当前对照精度**不足以定 λ***，Step 7 的 `argmin_λ` 会拟合噪声。
- **结构性信号**（按 RoadCat，λ=0.05 scaled）：CATB 0.65、**CATA 0.51**、CATC 0.83、**SLIP_ROAD 1.36**
  → 仿真**低估快速路、高估匝道**。
- **根因：对照 crosswalk 粒度**。`lta_osm_match_v2.csv` 是 5C.1 为**速度传播**建的「每 LTA 链路取
  1 条最近 OSM 边」；但 LTA 监测链路是 100–500 m 的**一整段**，OSM 把它拆成多条 13–100 m 短边。
  实测 **KPE（Kallang–Paya Lebar Expressway）**：网络上 KPE 全边 **432 条、仿真通过 188,481 次**，
  而 crosswalk 只映射到 **22 条、捕获 6,156 次（3.3%）** → 快速路被系统性低估。这是 r 偏低、GEH 差的主因。
- **时刻剖面副产物**：08:00 一次性放量导致人为拥堵——λ=0.10 时 **09:00 仍有 85,838 辆在网**、
  10:00 有 21,146、12:00 才降到 322；平均通勤 **61.8 min**、全网均速 **~19 km/h**、v/ff 中位 **0.70**。
- **下一步（已推进）**：① 走廊级 crosswalk → **6.3.2 已完成（已排除疑点）**；② population 加 AM 出发时刻分布
  → **6.3.3A 已完成（07–08=48.71% / 08–09=51.29%）**；③ 规模一致性（`flowCapacityFactor=200000/459794=0.435`
  或统一 scaled）**仍待做**；④ 之后再进 Step 7 定 λ*，并引入「AM 全交通/通勤倍率」分离非通勤流量。
  当前缺口：**6.3.3B 用 6.3.3A population 重跑 3λ + 逐小时对照**。

### 2.8.1 Step 6.3.2 断面 Crosswalk 重构结果（**排除 crosswalk 粒度疑点**）

脚本 `scripts/od/build_linkflow_crosswalk_6_3_2.py`；输出 `reports/matsim_assignment_6_3_2/`。

**运行前修复**：
1. **致命 bug**：`sim.merge(e, on="LINK")` 中 `e` 只有 `matsim_link_id`/`osm_edge_index`，**没有 `LINK` 列** → `KeyError`。改为把 `matsim_link_id` 重命名为 `LINK` 再 merge。
2. **方法学缺陷（两类，都会破坏结论）**：
   - **过度纳入**：原稿"质心 120m（全部边） + 250m（同名边）"→ **中位 77 边/断面**（max 264），把平行/对向/邻接边全拉进来。
   - **汇总口径错**：LTA `Volume` 是**点计数**；同一走廊**顺序** OSM 边稳态下流量相近 → **求和 = 流量 × 边数**（且跨断面求和重复计车）。正确估计量 = 断面内代表值（**中位数**）。修正：**沿线采样（每 25 m，半径 45 m）+ 路名一致**收紧候选（→ **中位 8 边/断面**），逐断面取中位。

**结果（λ=0.05，n=1,278，coverage 97.48%）**：

| 口径 | sim_obs_ratio | Pearson r | Spearman ρ |
|---|---:|---:|---:|
| 原稿 generous + **sum** | **16.90** ✗伪影 | 0.163 | 0.273 |
| **修正 tight + median（主）** | **0.618** | **0.293** | **0.398** |
| 修正 tight + max | 1.019 | 0.293 | 0.392 |
| **6.3 参照（旧 1:1 crosswalk）** | 0.647 | 0.306 | — |

**按 RoadCat（tight + median）**：CATA(快速路) **0.515**、CATB 0.556、CATC 0.557、SLIP_ROAD **1.398**；
三口径下 **CATA 相关 r ≈ 0（−0.05/−0.03/−0.02）**。

**结论**：修正 crosswalk 后 **总量比 0.618 ≈ 6.3 的 0.647、CATA 0.515 ≈ 6.3 的 0.510** —— **快速路低估原样保留、断面内零相关保留**。
→ **6.3 暴露的快速路问题不是观测 crosswalk 粒度造成的，而是分配侧（routing / OD / 网络 / 时刻脉冲）的真实信号**。
crosswalk 重构的价值在于**排除疑点**并给出可复用的断面级对照基线；**并未提升拟合质量**，也**不解决 08:00 时间脉冲**（留 6.3.3）。

**KPE 专项（"点计数 vs 求和"的直接证据）**：全网 KPE 483 边、仿真 scaled 求和 **451,757** ≈ 观测 22 断面之和 **450,748（比值 1.00）**；
但仿真**单条边最大仅 4,584/h** vs 观测断面中位 **17,969/h** → KPE **点流量偏低约 4–20×**。原稿"3.3% 捕获"是映射伪影，但 KPE 被**系统性少分配**是真的。

---

### 2.8.2 Step 6.3.3A 出发时刻剖面结果（**消除 08:00 单点脉冲**）

**问题**：6.2B population 全部 200,000 agent 的 home `end_time` = `08:00:00` → `HRS7-8 ≡ 0`，全部需求挤进 `HRS8-9`，形成人为脉冲（平均通勤 61.8 min、均速 ~19 km/h），使逐小时 `q_sim vs q_obs` 在 6.3 中**不成立**。

**方法**：只用项目已有的真实观测 `TrafficFlow_Data.json`（LTA 定义为 hourly average traffic flow）构造**网络观测驱动的时间形状先验**。

- 稳健代表流量 $\tilde q_{l,h}$：先按 `LinkID×Date×Hour` 取均值，再对 `LinkID×Hour` 取**工作日逐日中位数**（**不**把原始记录简单求和）。
- 全网时间比例 $s_7=\dfrac{\sum_l \tilde q_{l,7}}{\sum_l(\tilde q_{l,7}+\tilde q_{l,8})}$，$s_8=1-s_7$。
- 分配 $N_7=\mathrm{round}(s_7 N)$、$N_8=N-N_7$（$N=200{,}000$），每个 bin 内**秒级均匀随机**，避免整点同时出发。
- 只改写 `home` 活动的 `end_time`（流式逐行 gzip→gzip，不重写整棵 XML 树）；**不改** OD 总量 / OD 空间结构 / home_link / work_link / λ。

**结果**（`departure_profile_validation.json` = **PASS**）：

| 时段 | 网络流量指数 | 时间占比 | agent 数 |
|---|---:|---:|---:|
| 07:00–08:00 | 2,301,067.5 | **48.7103 %** | 97,421 |
| 08:00–09:00 | 2,422,915.9 | **51.2897 %** | 102,579 |

- 工作日样本 20 天、可用链路 1,311 条/小时；出发时间落 **07:00:00–08:59:59**。
- **ΣEF 严格 = 459,794**（3λ 不变）→ 时间剖面**只改"什么时候走"、不改 OD 总量**。
- **EF 加权实现占比** 0.4868–0.4877 ≈ 网络占比 0.4871（3λ）→ 守恒成立。
- **独立从输出 XML 反查**：`home end_time` 计数 200,000、小时分布 `{7: 97421, 8: 102579}`、`work` 活动 0 处被改。

**口径声明（写论文用）**：Census 2020 **不含出发时刻维度**（T10/Table 117 = PA×行程时间；T15/Table 133 = 全国就业×方式×行程时间；Table 118 = Region×PA×Mode）。故本轮用 LTA 实测小时交通流构建 **network-observed temporal shape prior**，**不声称**是居民 departure-time 观测；Census T10/T15 的 7 个行程时间分箱留作 **6.3.3B 的独立合理性检验**，**不用于反推出发时刻**。

**基线选择**：population 取 `reports/matsim_population_6_2b_connected/`（6.3a 连通性修复版），因 6.3.3B 重跑 MATSim 时 car 连通性检查会 abort 未修复的原始 6.2B。

**下一步（6.3.3B）**：用 `reports/matsim_departure_6_3_3a/population_lambda_*.xml.gz` 重跑 3λ AM assignment，做**逐小时**对照 `q^sim_{a,7-8} vs q^obs_{a,7-8}`、`q^sim_{a,8-9} vs q^obs_{a,8-9}`。→ **已完成，见 §2.8.3。**

### 2.8.3 Step 6.3.3B 逐小时对照结果（**时间脉冲确为人为拥堵主因；快速路仍低估 → 转 Step 7**）

**做法**：把 6.3.3A 的 3λ population（`reports/matsim_departure_6_3_3a/`）挂回**同一** `network_cleaned.xml.gz`，其余（crosswalk、OD、λ、Home-Work link）**全不变**；重跑单迭代 QSim → 3×200,000 agents、`lost=0`；对照口径为**逐小时 1↔1**（`q^sim_{7-8} ↔ q^obs_{7-8}`、`q^sim_{8-9} ↔ q^obs_{8-9}`），不再把两小时硬拼。断面 crosswalk 复用 **6.3.2 tight 版**（中位 8 边/断面、逐断面中位数）。

**逐小时指标**（λ=0.05；n=1,311 断面；crosswalk 覆盖 97.48%）：

| λ | r_7 | r_8 | r_AM | ρ_7 | ρ_8 | GEH7<5 | GEH8<5 | ratio_7 | ratio_8 | ratio_AM |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 0.05 | 0.284 | 0.252 | 0.271 | 0.385 | 0.389 | 9.76% | 8.39% | **0.734** | **0.876** | 0.806 |
| 0.075 | 0.285 | 0.256 | 0.273 | 0.384 | 0.392 | 9.84% | 8.92% | 0.734 | 0.865 | 0.801 |
| 0.10 | 0.286 | 0.256 | 0.274 | 0.384 | 0.392 | 10.37% | 9.46% | 0.727 | 0.858 | 0.794 |

**与 6.3（08:00 单脉冲）对照**：

| 指标 | 6.3（sim H8-9 vs obs h7+h8） | 6.3.3B（逐小时 7↔7 / 8↔8） | 判读 |
|---|---:|---:|---|
| Σsim/Σobs | 0.647 | **0.731 / 0.866** | 水平偏差**收窄** |
| CATA（快速路）ratio | 0.510 | **0.584 / 0.739** | 快速路**改善但未纠正** |
| Pearson r | 0.306 | 0.285 / 0.255 | **未提升**（逐小时更诚实） |
| EF 加权平均通勤 | 61.8 min（≈19 km/h） | **19.4 min（≈41 km/h）** | 人为拥堵**消除** |

**按 RoadCat 分解**（λ=0.05，ratio = Σsim/Σobs，pearson 为**断面内**相关）：

| RoadCat | n | 07-08 ratio | 07-08 r | 08-09 ratio | 08-09 r |
|---|---:|---:|---:|---:|---:|
| **CATA（快速路）** | 339 | **0.584** | **−0.012** | **0.739** | **−0.057** |
| CATB（主干道） | 634 | 0.757 | 0.311 | 0.808 | 0.314 |
| CATC | 46 | 0.741 | 0.660 | 0.750 | 0.602 |
| CATD | 7 | 0.368 | 0.766 | 0.475 | 0.779 |
| SLIP_ROAD（匝道） | 251 | 1.594 | 0.190 | 2.033 | 0.213 |

**判读（按门控决策逻辑）**：

1. **出发时刻剖面确为人为拥堵主因**：EF 加权平均通勤 **61.8 → 19.4 min**、网络均速 **≈19 → ≈41 km/h**；`ratio_7/ratio_8` 由 0.647 升至 **0.734 / 0.876**。6.3 的"拥堵水平"确为 08:00 单脉冲伪影。
2. **但快速路结构性低估仍在**：CATA ratio 仍 **< 1**（0.584 / 0.739），且**断面内相关 ≈0**（−0.01 / −0.06）——与 6.3.2 结论一致。
3. **相关未随剖面提升**（r 0.306 → 0.285/0.255）：逐小时口径更诚实，说明**空间分配结构**仍有系统偏差。
4. **结论**：**不再调 departure time**，正式转 **Step 7（network capacity / 车道表达 / route choice / OD assignment calibration）**。SLIP_ROAD 明显高估（1.59/2.03）与匝道—主线 crosswalk 重叠有关，留作 Step 7 一并处理。

**λ 判读**：λ=0.05/0.075/0.10 的 `ratio_7`（0.734/0.734/0.727）与 `r_7`（0.284/0.285/0.286）仍**几乎不可分辨** → **当前精度不足以定 λ\***，与 6.3 结论一致。

---

### 2.9 Step 7.1 TrafficFlow 校准靶场结果（**只建评价体系，不改模型**）

新增 `scripts/od/build_calibration_target_7_1.py`。**靶场定义**：观测 = `TrafficFlow_Data.json` 工作日逐日中位 → LinkID×Hour 中位；仿真 = 6.3.3B `it.0` linkstats `HRS7-8avg`/`HRS8-9avg` × scale **2.29897**；断面归属用 **6.3.2 tight crosswalk**（断面内取匹配边**中位数**）；分层用 **LTA `RoadCat`**。样本 **n=1,278**（观测 1,311 中有 MATSim 对应关系者，覆盖 97.48%；断面内匹配边中位 8、`name_match_rate` 均值 0.923）。

**总体指标（λ=0.05）**：

| 窗 | r | ρ | RMSE | MAE | WMAPE | Bias | Sim/Obs | GEH<5 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 07-08 | 0.279 | 0.378 | 2066.9 | 1227.7 | 0.692 | −454.2 | **0.744** | 10.02% |
| 08-09 | 0.249 | 0.383 | 2395.9 | 1389.9 | 0.745 | −206.7 | **0.889** | 8.61% |
| AM | 0.267 | 0.383 | 4416.5 | 2587.7 | 0.711 | −660.9 | 0.819 | 6.89% |

**按 LTA RoadCat（λ=0.05）**：

| RoadCat | n | r(h7-8) | Sim/Obs(h7-8) | r(h8-9) | Sim/Obs(h8-9) |
|---|---:|---:|---:|---:|---:|
| **CATA（快速路）** | 339 | **−0.012** | **0.584** | **−0.057** | **0.739** |
| CATB（主干道） | 634 | 0.311 | 0.757 | 0.314 | 0.808 |
| CATC | 46 | 0.660 | 0.741 | 0.602 | 0.750 |
| CATD | 7 | 0.766 | 0.368 | 0.779 | 0.475 |
| CATE | 1 | — | 0.000 | — | 0.000 |
| **SLIP_ROAD（匝道）** | 251 | 0.190 | **1.594** | 0.213 | **2.033** |

**结论（对 Step 7.2 的指向）**：
1. **CATA<1 且断面内 r≈0** + **SLIP_ROAD>1** → 问题在**快速路↔匝道的路径层面**，**不是**全局 scale（CATC 的 r≈0.6、水平≈1，说明网络/OD 基本框架可用）。
2. **λ 不可分辨**（3λ 的 r 极差 0.002、Sim/Obs 极差 <0.012）→ **不据某个 λ 的 r 选 λ\***；λ 待 Step 7 引入结构参数后再辨识。
3. Step 7.2 优先：**route choice 参数 → network `capacity`/`permlanes` → 规模一致 `flowCapacityFactor=0.435`**（三者都能改变快速路/匝道相对分配）。【7.2 审计后修正：实际 `flowCapacityFactor=1.0` 而非 0.435，见 §2.10——"规模一致性"问题实为"容量过剩"问题，一并纳入 7.2.2 扫描】
4. 目标函数：`J(θ)=w1·E_GEH+w2·E_RMSE+w3·E_MAE+w4·E_corr`，`θ={λ,capacity,lanes,route choice,…}`。

**运行前修复的口径缺陷**：脚本原用 crosswalk 的 **OSM `highway`**（primary/motorway/trunk…）分层，**不符合 LTA 口径**——核验发现 `highway` 是**逐边**属性（1,278 断面中 **286** 个多值），而 `RoadCat` 是**断面级** LTA 属性（**无一**多值）。已改用 `RoadCat`（并在 `cross_load` 加断面级一致性断言）；同时给 `metric()` 加 `n≥2` 防护消除 CATE(n=1) 的 numpy 警告。修正后逐类结果与 6.3.2/6.3.3B **完全一致**。

### 2.10 Step 7.2 MATSim 参数审计结果（**只审计，不改任何模型**）

新增 `scripts/od/audit_matsim_calibration_7_2.py`（用户交付，运行前修复 3 处缺陷）。输出 `reports/od_calibration_7_2/`：`parameter_audit.csv`（config 逐参数展开）、`config_summary.csv`（25 个 XML 概览）、`network_capacity_audit.csv`（逐 highway 等级容量）、`calibration_target_baseline.csv`（7.1 靶场基线复制）、`capacity_sweep_plan.csv`（**仅实验计划**：0.50/0.75/1.00/1.25/1.50）、`step7_2_audit.json`（`status=PASS`、`model_parameters_changed=false`）。

**运行前修复的 3 处缺陷**：
1. **config 参数全为 null**：MATSim config_v2 的参数是 `<param name="..." value="..."/>` **属性**而非元素文本，`flatten_xml` 只取叶子文本 → 扑空。已重写：module 名与 param 名嵌入 path（`module[qsim]/param[flowCapacityFactor]`）、`value` 作 text。
2. **baseline 选错文件**：原评分会选中 `*.output_config_reduced.xml`（MATSim 运行导出物）→ 已过滤所有 `output_config` 文件，正确选中 **`matsim/step6_3/config_lambda_0p050_6_3_3b.xml`**。
3. **capacity 列不存在**：`network_links_source_copy.csv` 根本没有 capacity 列（只有 from/to/travel_time/length/speed/highway/lanes/name）→ 原脚本会 KeyError。已改为解析 **`network_cleaned.xml.gz`** 逐边 `capacity`/`permlanes`/`freespeed`，按 `e{from}_{to}` 与 source copy 合并；`invalid_lanes`/失配判定以 XML `permlanes` 为准（CSV lanes 有 272,860 行缺失，均已被 6.1 建网默认值补齐，`lanes_mismatch_vs_xml=0`）。

**基线 config（6.3.3B，λ=0.05）关键参数**：

| 模块 | 参数 | 值 | 审计判读 |
|---|---|---|---|
| qsim | `flowCapacityFactor` | **1.0** | ⚠️ **重大发现**：不是预想的 0.435。抽样率 0.435 下网络容量相对需求被放大约 **2.3×** → QSim 内几乎不形成拥堵 |
| qsim | `storageCapacityFactor` | 1.0 | 同上 |
| qsim | `stuckTime` / `mainMode` | 10.0 / car | — |
| controller | `routingAlgorithmType` | **SpeedyALT** | 最短路路由；单迭代下无学习反馈 |
| controller | `firstIteration=lastIteration` | **0 / 0** | 单迭代：`ReRoute` 策略（`maxAgentPlanMemorySize=5`）**完全不起作用**，route choice = 一次性 freespeed 最短路 |
| travelTimeCalculator | `travelTimeBinSize` / `aggregator` / `getter` | 900 s / **optimistic** / average | 单迭代下 TT 估计 = freespeed，无拥堵反馈 |
| network | capacity 语义 | `permlanes × 等级默认 veh/h/lane` | 逐边审计：median 800 / p95 3,600 veh/h；CATA(motorway) 1,900 veh/h/lane；693,575 边 0 无效值 |

**逐 highway 等级**（`network_capacity_audit.csv`，边数前几名）：service 450,486（capacity/lane 400）、residential 120,396（700）、primary 25,798（1,500）、tertiary 23,278（900）、secondary 19,806（1,200）、**motorway 4,744（1,900）**、motorway_link 9,026（1,700）、trunk 5,091（1,800）。

**对 7.2.2 capacity-only sweep 的直接推论**：当前 `flowCapacityFactor=1.0` + 0.435 抽样 ⇒ **系统处于"容量严重过剩"区**。若扫描显示 CATA/SLIP_ROAD 对 capacity factor **不敏感**，则快速路低估几乎确定来自 **route choice 效用**（freespeed 最短路 + 无拥堵反馈 + 无 toll/偏好项）；若**敏感**（容量下调至拥堵形成后路径转移），则先校 capacity/`flowCapacityFactor`（理论一致性值 0.435）。**scan 判据**：CATA Sim/Obs 从 0.584/0.739 向 1 靠近且 SLIP_ROAD 从 1.59/2.03 回落 = capacity 主导；几乎不动 = route choice 主导。

**审计同时确认的冻结约束**：`inputNetwork=network_cleaned.xml.gz`、`inputPlans=matsim_departure_6_3_3a/population_lambda_0p050.xml.gz` —— 与 6.3.3B 冻结口径一致，审计未触碰任何输入。

### 2.11 Step 7.3.1 Congestion-feedback Sensitivity 结果（λ=0.05，唯一变量 = lastIteration）

新增 `run_congestion_feedback_7_3_1.py` + `compare_congestion_feedback_7_3_1.py`，输出 `reports/od_calibration_7_3_1/`。口径：capacity 固定 1.0（7.2.2 判定后不动）、OD/population(6.3.3A)/departure/topology/permlanes/crosswalk 全冻结；只打开多迭代拥堵反馈（ReRoute weight=1.0 + TTC 在单迭代下本被旁路，加迭代即自动生效；`routingRandomness=0.0` + 无 timeAllocationMutator/mode choice ⇒ 出发时刻与方式不漂移）。

**嵌套设计**：同 seed + 确定性 ReRoute ⇒ lastIteration 只是截断 → **一次 20 迭代运行**覆盖预注册检查点 {1,5,10,20}（↔ it.0/4/9/19）+ 一次 5 迭代运行验证嵌套性。**双重确定性验证 PASS**：① 嵌套 it.0–4 与主运行逐位一致（5/5）；② it.0 与冻结 6.3.3B 逐位复现。磁盘控制：中间迭代不写 events/plans/trips/snapshots，每迭代 linkstats 全保留。

**检查点结果**：

| 指标 | 1 迭代（=6.3.3B） | 5 迭代 | 10 迭代 | 20 迭代 |
|---|---|---|---|---|
| 总体 r（07-08 / 08-09） | 0.279 / 0.249 | 0.326 / 0.292 | 0.321 / 0.293 | 0.325 / 0.290 |
| CATA Sim/Obs（07-08 / 08-09） | 0.584 / 0.739 | 0.649 / 0.743 | 0.653 / 0.767 | 0.651 / 0.780 |
| SLIP_ROAD Sim/Obs（07-08 / 08-09） | 1.594 / 2.033 | 1.754 / 1.993 | 1.737 / 2.032 | 1.718 / 2.075 |
| **CATA/SLIP 比值** | **0.366 / 0.363** | 0.370 / 0.373 | 0.376 / 0.378 | **0.379 / 0.376** |
| r_CATA 断面内 | −0.012 / −0.057 | +0.017 / −0.018 | +0.014 / −0.030 | +0.014 / −0.030 |

**判读（预注册判据「比值显著偏离 0.366 且 r_CATA 改善」不成立）**：20 迭代全程比值仅在 **0.363–0.389** 带内振荡（均值 ~0.377，+3%），CATA 与 SLIP **依旧同向**上升（通量水平效应，非相对分配转移），**r_CATA 始终 ≈0**——快速路断面内空间排序从未被改善。**第二个否定性实验结论：拥堵反馈 / 迭代式 ReRoute 也不是 CATA↔SLIP_ROAD 结构错配的杠杆**——20 迭代 × 每轮全员 ReRoute + 拥堵 TT 下路径已完全重优化，比值仍不动 ⇒ **单迭代自由流最短路不是结构性低估的原因**。

**证据指向**：capacity（7.2.2）与拥堵反馈（本步）均已排除；7.3.2 route-choice 参数先验已弱（路径已完全重优化）。**建议下一步：快速路-匝道连通性专项审计**（零仿真成本，纯拓扑统计：CATA r≈0 暗示"走错地方"而非"走少比例"），其结果决定 7.3.2 取舍。λ 继续不冻结。

### 2.12 Step 7.3.2A Motorway–Ramp Connectivity Audit 结果（纯拓扑，零仿真，PASS）

用户在外部环境执行审计，产物已归档 `reports/od_calibration_7_3_2a/`（`STEP7_3_2A_REPORT.md` + `motorway_ramp_transition_matrix.csv` + `motorway_link_endpoint_diagnostics.csv` + `motorway_endpoint_anomalies.csv` + `step7_3_2a_validation.json`，`status=PASS`）。**审计对象为冻结 `network_cleaned.xml.gz`，不改任何输入**。

| 检查 | 结果 |
|---|---|
| motorway / motorway_link 边数 | 4,744 / 9,026（重复有向边 0） |
| motorway 无相关上游 / 下游 | **1 / 4,744**（Airport Boulevard，spot-check 级）/ **0 / 4,744** |
| motorway→motorway / →motorway_link | 5,855 / 240 |
| motorway_link→motorway / →motorway_link | 240 / 8,914 |
| motorway+ramp 最大弱连通分量 | **99.969%**（强分量不作验收条件——单向路网） |
| ramp 无 motorway/ramp 上游 / 下游 | 239（2.65%）/ 248（2.75%），均接 primary/trunk/secondary = 正常 terminal 出入口形态 |

**判读**：快速路主线连续、主线-匝道有向接口完整配对 → **不支持"快速路/匝道网络断裂"解释 CATA 低估；不修改冻结网络**。

### 2.13 Step 7.3.2B Route-structure / Path-choice Diagnosis 结果（plans 路径序列 × 等级分类，PASS）

新增 `scripts/od/diagnose_route_structure_7_3_2b.py`；输出 `reports/od_route_diagnosis_7_3_2b/`。数据源 = 6.3.3B λ=0.05 `it.0` 的 `step6_3_3b_lambda_0p050.0.plans.xml.gz`（route type=links 完整序列；**events 不需要**）+ `.trips.csv.gz` + 冻结 `network_links_source_copy.csv`。

**运行前修复 3 处**：① `network_links_source_copy.csv` **无 `matsim_link_id` 列** → 按 6.1 约定构造 `e{from}_{to}`（Step 4 审计 0 重复 ⇒ 唯一）；② 每条 route 分类两次 + 逐 link `df.loc` → **单次遍历 + 字典视图**（否则数千万次索引查询）；③ 显式传实际文件名（非默认 `output_*`）。

**核心结果**：
- **A（高速很少被选）→ 否定**：**61.06% 路线**用 motorway、**41.48% 路线长度**在 motorway 上（第一大道等级）；motorway_link 61.39%/5.81%。
- **确定性**：196,447 OD 对 **0 个多路径**——it.0 完全单一最短路（与 SpeedyALT+单迭代一致）；0 个未知 link（id 构造全覆盖）。
- **ramp 链现象**：`motorway_link→motorway_link` 转移 **5.12M**（用 ramp 路线平均 ~42 个微段、平均单段 ~30 m = 路网碎片化表达）；`motorway→motorway_link→motorway` 精确三元组 0（匝道呈链状，无单匝道即出即进）；`primary→motorway_link` 84,887 / `motorway_link→primary` 76,502。
- **A/B/C 判定**：A 排除；**B（被选但 OD 级空间分散）部分成立**（同 OD 单路径 ⇒ 分散只能跨 OD）；**C（观测 vs 表达系统差异）保留**——需 route×crosswalk 断面级对照分辨。SLIP_ROAD 高估与 ramp 链被当作正常最短路使用一致。
- **下一步 7.3.3 候选**：route×crosswalk 断面级对照（零仿真）；route-choice 参数实验优先级进一步下降。

---

## 3. 运行状态

### 3.1 步骤状态与关键指标

| Step | 状态 | 关键指标 |
|---|---|---|
| 0 审计 | ✅ | 接口/字段体检通过 |
| 1 空间字典 | ✅ | 332 Subzone / 55 PA / 5 Region，EPSG:3414 |
| 2 Production | ✅ | `work_trip_production` Σ = **2,208,356**；`car_work_trip_production` Σ = 459,794 |
| 3B.1 Attraction | ✅ 冻结 | `workplace_attraction` Σ = **1,935,235**，逐 PA 守恒 ~1e-16 |
| 4 Impedance | ✅ 冻结 | 429,032 节点 / 706,554 有向边；**可达率 1.0**；`C^FF` 中位 **14.878** / 均值 15.197 / 最大 64.066 min |
| 5A Gravity | ✅ 保留 | 5 λ 全收敛，守恒 ≤6.6e-9；均值 13.74→11.26 min |
| 5B Census 基线 | ✅ 冻结 | Σ T = 1,935,235；守恒 ≤6.4e-9；Region→PA 最大偏差 **2.29%**；非零格 71,136；均值 12.09–12.34 min |
| 5C AM-v1 | ✅ 保留 | 几何匹配 99.82% LTA Link；覆盖 **13.0% 边 / 18.1% 长度**；`C^AM,v1` 中位 **18.131** / 最大 78.953 min |
| **5C.1 AM-v2** | ✅ | 覆盖 **32.2% 边 / 38.35% 长度**；`C^AM,v2` 中位 **21.361** / 均值 21.724 / 最大 89.301 min；可达率 1.0 |
| **5C.1 Prior OD** | ✅ | AM-v2 阻抗 + 5B 约束框架；ΣT=**1,935,235**；守恒 ≤9.7e-9；Region×PA 最大残差 **2.25%–5.76%**；非零格 71,136；加权均值 **16.96–18.08** min（λ 0.05→0.15） |
| 6.1 MATSim 网络 | ✅ 冻结 | 429,032 节点 / 706,554 有向边；0 重复边 / 0 自环 / 0 孤立节点；`zone_matsim_node_map` 332/332 全覆盖；`network.xml.gz` 13.5 MB；独立复核 `ALL_CHECKS_PASS=true` |
| 6.2 Population/Plans | ✅ 冻结（第一版基线） | 3×200,000 agents（λ 0.05/0.075/0.10）；car-only OD Σ=**459,794**（= car production）；IPF 收敛 13–14 次，行误 ≤8.6e-9 / 列误 ≤1.0e-11；cell 覆盖 59%、expansion Σ 代表 93.8%；独立复核 `ALL_CHECKS_PASS=true` |
| **6.2B 保底采样 + 空间下分** | ✅ **本轮** | 3×200,000 agents；**cell 覆盖 100%**（71,136/71,136）；**ΣEF=459,794**（单 cell 误差 ≤1.4e-14）；home link **17,052** / work link **5,782**；home 源 uranof 87.4% / building 12.3% / fallback 0.3%，work 源 poi 97.4% / building 0.6% / fallback 2.0%；独立复核 `ALL_CHECKS_PASS=true` |
| 6.2C 时间属性 / rerouting | ◑ 部分 | 出发时刻分布已由 **6.3.3A** 覆盖；活动时长 / 方案重选（rerouting）仍待做 |
| **6.3a 连通性修复** | ✅ **本轮 PASS** | `NetworkCleaner` 706,554→**693,575** 边（−1.84%）；**332 锚点 0 受影响**；重吸附 agent **5,066–5,156/200,000（2.55%）**，位移中位 **3.3 m**/max 518 m；car 检查 **0 边被移除** |
| **6.3b 第一次 AM assignment** | ✅ **本轮 PASS** | 单迭代 QSim（`first=last=0`），3×200,000 agents；`lost=0`；车分担 100%；平均行程 13.7 km；**3λ 合计 ~41 min**（JDK25 + MATSim 2026.0） |
| **6.3c 第一次 q_sim vs q_obs 对照** | ✅ **本轮 PASS** | 1,278 条 LTA 链路；**Σsim/Σobs = 0.647**（scaled）、**r = 0.306**、**GEH<5 = 7.5%**；CATA 0.51 / SLIP_ROAD 1.36；**λ 不可分辨** |
| **6.3.2 断面 Crosswalk 重构** | ✅ **本轮 PASS** | 收紧候选 **中位 8 边/断面**（原稿 77）；tight+median：**sim/obs=0.618**、r=**0.293**、ρ=0.398；**CATA 0.515 / SLIP_ROAD 1.398**；原稿 `sum` 伪影 **16.90** 已复现并排除 → **crosswalk 粒度非主因** |
| 6.3.3 Departure-Time Profile | ✅ **本轮 PASS** | **6.3.3A**：TrafficFlow 驱动时间形状 → 07–08=**48.71%** / 08–09=**51.29%**（97,421 / 102,579 agents）；出发时间 07:00–08:59:59 秒级随机；**ΣEF=459,794 不变**、EF 加权占比≈网络占比；XML 200,000 persons/home 改写、`work` 未动；`validation.json=PASS` |
| 6.3.3B 重跑 + 逐小时对照 | ✅ **PASS** | 用 6.3.3A population 重跑 3λ（同网络 `network_cleaned.xml.gz`，`lost=0`）；**逐小时** `q_sim(Link,Hour) vs q_obs(Link,Hour)`：r_7=0.284 / r_8=0.252、ratio_7=**0.734** / ratio_8=**0.876**；**CATA 0.584/0.739**（6.3 为 0.510）；EF 加权通勤 **61.8 → 19.4 min**（均速 ≈19→≈41 km/h）→ **脉冲为人为拥堵主因**，但**快速路仍低估** |
| 7.1 TrafficFlow 校准靶场 | ✅ **PASS** | 冻结靶场 `q_obs↔q_sim`，**n=1,278**（覆盖 97.48%）；λ=0.05：r 0.279/0.249/0.267、Sim/Obs **0.744/0.889/0.819**；**RoadCat**：**CATA 0.584/0.739（r≈0）**、CATB 0.757/0.808、CATC 0.741/0.750、SLIP_ROAD **1.594/2.033**；**λ 不可分辨**；`parameters_changed=false` |
| 7.2.1 MATSim 参数审计 | ✅ **本轮 PASS** | 25 个 config XML 全解析（`<param name value/>` 属性口径修复）+ 693,575 边逐边 capacity/permlanes/freespeed 审计（0 无效值，`lanes_mismatch=0`）；**基线 `config_lambda_0p050_6_3_3b.xml`**：**`flowCapacityFactor=1.0`（⚠️ 非 0.435，容量过剩 ~2.3×）**、SpeedyALT、单迭代（ReRoute 无效）；sweep 计划 0.50/0.75/1.00/1.25/1.50 **仅计划**；`model_parameters_changed=false` |
| 7.2.2 Capacity-only sensitivity 扫描 | ✅ **本轮 PASS** | λ=0.05 × f∈{0.50,0.75,1.00,1.25,1.50}（storage=flow 引擎硬约束）；f=1.00 与 6.3.3B **逐位复现**；**r 对 f 不敏感（0.28–0.30 / 0.25–0.26）**；**CATA/SLIP_ROAD 比值恒 0.366（极差 ≤0.007）→ capacity 非结构杠杆**；CATA 内 r 全档 ≈0；**→ 转 Step 7.3 route choice** |
| 7.3.1 Congestion-feedback sensitivity | ✅ **本轮 PASS** | λ=0.05、capacity 1.0，唯一变量 lastIteration；**嵌套设计**（20 迭代一次覆盖 1/5/10/20 + 5 迭代验证，嵌套 **5/5 逐位一致**、it.0 与 6.3.3B 逐位复现）；**CATA/SLIP 比值 0.366→仅 0.377（+3%，带 0.363–0.389）、r_CATA 始终≈0、CATA/SLIP 同向移动 → 拥堵反馈非结构杠杆**；**→ 建议先做快速路-匝道连通性审计，再定 7.3.2 取舍** |
| 7.3.2A Motorway–Ramp 连通性审计 | ✅ **本轮 PASS** | 纯拓扑零仿真；主线连续（无上游仅 1/4,744 = Airport Boulevard spot-check 级）、接口完整（mw→ml 240 / ml→mw 240）、弱连通 99.969%、ramp terminal 2.65%/2.75% 属正常出入口形态 → **不支持网络断裂解释，不修冻结网络** |
| 7.3.2B Route-structure 诊断 | ✅ **本轮 PASS** | plans 路径 × 等级分类（200,000/200,000 对接、0 未知 link）；**A"不走高速"否定**（**61.1% 路线 / 41.5% 长度用 motorway**）；**0/196,447 OD 多路径**（完全确定性）；ramp 链 5.12M 次 ml→ml（~42 微段/路线、~30 m/段碎片化）；**→ 7.3.3 route×crosswalk 断面级对照分辨 B/C** |
| 7.3.3 route×crosswalk 断面级对照 | ⬜ **下一步** | 对 1,278 断面统计 route 使用 vs 靶场 sim/obs → 分辨 B（OD 级分散）vs C（观测-表达系统差异）；route-choice 参数实验优先级下降 |

### 3.2 三层阻抗对照（332×332）

| 层 | 中位 (min) | 均值 (min) | 最大 (min) | 覆盖（长度） | 相对 FF |
|---|---|---|---|---|---|
| `C^FF` | 14.878 | 15.197 | 64.066 | — | 1.000 |
| `C^AM,v1` | 18.131 | 18.481 | 78.953 | 18.1% | 1.232 |
| `C^AM,v2` | **21.361** | **21.724** | **89.301** | **38.35%** | **1.461** |

> AMv2/AMv1 = 1.185；**100% 的 OD 单元** AMv2 ≥ AMv1（95.5% 涨 >1 min，55.6% 涨 >3 min）。

### 3.3 Step 5C.1 tier 分解

| tier | 边数 | 长度 (km) | 长度占比 | AM/FF 中位比 |
|---|---|---|---|---|
| `geom` | 87,195 | 2,894.9 | 18.65% | 0.49 |
| `name+hw` | 139,776 | 3,052.0 | 19.66% | 0.49 |
| `name` | 340 | 6.2 | 0.04% | 0.59 |
| `none` | 479,243 | 9,571.5 | 61.65% | 1.00（保留 FF） |

按道路组（已覆盖边）：expressway 70→54.5 km/h（×0.78）、arterial 60→34.5（×0.58）、local 50→24.5（×0.49）；`edges_over_130_kmh = 0`；软护栏触发 1,800 边。

### 3.4 当前 λ 敏感性（Prior OD 加权平均通勤时长, min）

| λ (per min) | 5B（FF） | 5C（AM-v1） | **5C.1（AM-v2）** |
|---|---|---|---|
| 0.050 | 12.344 | 15.312 | **18.082** |
| 0.075 | 12.218 | 15.119 | **17.811** |
| 0.100 | 12.089 | 14.922 | **17.533** |
| 0.125 | 11.958 | 14.720 | **17.249** |
| 0.150 | 11.825 | 14.514 | **16.960** |

> **未冻结 λ**。λ 的选取应由 Step 7 的 `argmin_λ Error(q_sim, q_obs)` 决定，**不依据"平均通勤时长最像现实"**。
> ⚠️ **5C.1 的 Region×PA 残差随 λ 上升**（2.32%@0.05 → 5.76%@0.15；5B 恒 2.3%–2.7%）：AM-v2 对跨区出行惩罚更重，大 λ 下与 Census 跨区结构对抗更强。进 MATSim 建议先用 λ=0.05–0.10。

---

## 4. 常见坑与约定

1. **pandas 3.0**：`stack()`（勿带 `dropna=False`）；`to_numpy()` 只读 → 用非原地赋值；`get_special_workplace_totals` 找控制表要加候选与布尔稳健解析。
2. **LTA SpeedBand=8 的 999 哨兵**：务必显式拦截（见 §2.3）。
3. **LTA 几何源**：用 `TrafficSpeedBands_Links.shp`，不是 `TrafficFlow_Links.shp`。
4. **Table 118 的 2.21% 结构残差**：块约束与吸引量边际**无法同时精确满足**（PA 级 Census 隐含质量 vs 吸引量边际最大差 2.06%，绝对冲突仅 ~480/1,935,235 ≈ 0.025%）。**2.2% 是数据内在不一致的硬地板**，不必为追"0 误差"继续迭代。
5. **`matrix_density` 不是有效 λ 诊断量**：非零格恒为「P>0 × A>0」的支撑格数（71,136），IPF 乘法不造/灭零。
6. **平均通勤偏短的根因是阻抗**（free-flow 天花板），不是 λ；正确路径是 AM 阻抗 → MATSim → TrafficFlow 校准。
7. **同名传播的上限**：OSM 机动车边有名字的占 34.4% 边 / 41.1% 长度；其中名字命中 LTA 的占 37.4% 长度——这是 5C.1 覆盖率的天花板。剩余 `none` 多为**无名的 local/service 路**。
8. **production.csv 的 car 列名是 `car_work_trip_production`**（不是 `car_work_production`）。Step 6.2 脚本第一版按错名检索直接崩溃。
9. **car-only 目的地边际必须用冻结的 `workplace_attraction_clean`，不是 raw `workplace_attraction`**：raw 版本对 3 个无道路离岛（zone 258/322/323）仍保留正吸引，而先验 OD 支撑已把它们置 0 → 这 3 个目标列**永远无 seed 可填** → IPF 结构上不收敛。**凡是用先验 OD 支撑做 seed 的 IPF，列边际的零集必须与 seed 的零列集一致。**
10. **抽样代表性**：按 trips 体积做多项抽样时，小 cell（trips<1）会被自然漏掉 → 200k agents 下 cell 覆盖 ~59%、出行量代表 ~93.8%（不是 bug）。若要 100% cell 覆盖，用「保底 1 agent/cell + 剩余按体积」。
11. **POI 坐标列名 + 坐标系（致命）**：`poi.csv` 用 **`lng`/`lat`（WGS84 度）**；检索 `x|lon|longitude` 会漏掉 `lng` → **POI 池静默为空**。且 WGS84 经纬度必须**重投影 EPSG:3414** 后再吸附（网络坐标为 SVY21 米制）。
12. **MATSim 元素名是 `<activity>`（致命）**：`population_v6.dtd` 为 `(activity|leg)*`，reader `case ACT` 且 `ACT="activity"`；写 `<act>` 会触发 `"[tag=... not known or not supported]"` 异常。**不是 `<act>`。**
13. **保底采样后 EF 可 < 1**：`EF=T_ij/N_ij` 是**逐 cell 系数**；小 cell 的 1 个 agent 代表不足 1 次出行，属预期，`ΣEF` 仍精确 = 459,794。
14. **MATSim XML 必须有 DOCTYPE（致命）**：`MatsimXmlParser` 靠 DOCTYPE 的 system-id 识别文件版本，
    缺了会抛 `Missing DOCTYPE.` / 解析器 delegate 为 null 的 SAXParseException(NPE)。
    `config_v2.dtd` / `network_v2.dtd` / `population_v6.dtd` 三件套都必须在**手写序列化**时显式前置
    （ElementTree 不会写 DOCTYPE）。
15. **MATSim 会对 XML 做 DTD 校验**（`ValidationType.DTD_ONLY`）：写 DTD 未声明的属性会直接报错。已踩三例：
    ① `<network>` 只声明 `name`（**不能有 `changeEvents`**）；② `<nodes>` 无 ATTLIST（**不能有 `format="matsim"`**）；
    ③ `population_v6.dtd` 的 `<!ELEMENT attribute (#PCDATA)>` → 值必须放**元素文本**，**不是 `value=""` 属性**。
16. **Java 版本必须 25**：MATSim 2026.0 是 Java 25 编译（manifest `Java-Version: 25`，class major 69）。
    Java 24 → `UnsupportedClassVersionError`；日志里 `Unsupported class file major version 69`
    只是 Guice 的 ASM 读行号失败，**非致命**，可忽略。
17. **car 网络必须强连通**：见 §2.7.1。`networkRouteConsistencyCheck=disable` **不是**正确解法（会让碎片端点的 agent 无路可走）。
18. **linkstats 的规模口径**：`avg` 列在单迭代下 = 实际车辆数（=采样 agent 数），**不是** OD 的出行量。
    与真实观测对照必须乘 `ΣEF/N`（本项目 2.299）。且 `CalcLinkStats.volScaleFactor` **只在 readFile 生效**，
    `writeFile` 不乘，所以放缩只能在 Python 侧做。
19. **`linkStats.writeLinkStatsInterval` 必须 ≥1**：默认值不会在迭代 0 写出 `ITERS/it.0/<runId>.0.linkstats.txt.gz`。
20. **`tee`/管道会块缓冲 Java 日志**：在 Git-Bash 里 `python run.py | tee log` 时控制台日志会滞后；
    要看真实进度请读 MATSim 自己的 `reports/matsim_assignment/lambda_*/<runId>.logfile.log`。
21. **对照 crosswalk 的用途决定粒度**：`lta_osm_match_v2.csv`（5C.1）是**速度**用途的「1 链路→1 最近边」，
    直接拿来算**流量**会系统性低估（每 LTA 段对应多条短 OSM 边）。见 §2.8 / §2.8.1。
22. **流量断面口径：LTA `Volume` 是点计数，不能跨边/跨断面求和**：同一走廊**顺序** OSM 边稳态流量相近 →
    `sum = 断面流量 × 边数`；跨断面求和还会被同一辆车在每个断面重复计数。断面流量应取**断面内代表值（中位数）**，
    逐断面独立比较。实测：原稿「质心大半径 + sum」把 ratio 抬到 **16.90**（77 边/断面）；改「沿线采样 + 路名一致 + 中位」
    后回落到 **0.618**（8 边/断面）。见 §2.8.1。
23. **crosswalk 与 linkstats 的连接键必须对齐**：linkstats 边键是 `LINK`，网络边表键是 `matsim_link_id`；
    直接 `sim.merge(e, on="LINK")` 会 `KeyError`（`build_linkflow_crosswalk_6_3_2.py` 第一版即此 bug），merge 前先重命名。
24. **KPE（实时）判据**：快速路低估是**真实分配信号**，不是 crosswalk 伪影——修正断面 crosswalk 后 CATA 比值仍 **0.515**
    （=6.3 的 0.510），且断面内 **r≈0**。下一步应查分配侧（AM 阻抗/连通/OD 短途化），而非继续调观测映射。
25. **MATSim departure 只能改 `home` 活动 `end_time`**：时间剖面的正确落点是 `home` 的 `end_time`（6.2B writer 输出
    `<activity type="home" link="..." end_time="08:00:00" />`），**不是**改 `<leg>`、**不是**给 `<person>` 凭空加时间字段。
    流式正则替换时注意**属性顺序**：本项目的顺序是 `type` → `link` → `end_time`，正则需要 `type="home"` 出现在 `end_time="` 之前。
26. **出发时刻剖面基于连通性修复版 population**：6.3.3A 的输入取 `reports/matsim_population_6_2b_connected/`，因为重跑
    MATSim 时 car 连通性检查会 abort 未经 6.3a 修复的原始 6.2B。**不要**把原始 6.2B 直接喂给 QSim。
27. **不要用 Census 的 "Travelling Time" 冒充 departure time**：Census 2020 只有行程时间分箱（Below 15 / … / 120 & Over），
    **没有**出发时刻维度；Table 118 是 Region×PA×Mode。departure profile 只能来自 TrafficFlow 等真实时间观测（或未来 HTS）。
28. **时间分布不改变 OD 总量**：6.3.3A 只重排出发时刻，`ΣEF` 必须仍 = **459,794**；验证时应同时看 agent 数占比与
    **EF 加权占比**（后者略偏移是随机抽样所致，量级应 ≈ 网络时间占比）。
29. **逐小时对照必须 1↔1，不可再把两小时拼一起**：6.3 因单脉冲只能拿 `sim H8-9` 对 `obs(h7+h8)`；6.3.3B 起
    **严格** `sim(7-8)↔obs(7-8)`、`sim(8-9)↔obs(8-9)`（`linkstats` 的 `HRS7-8avg`/`HRS8-9avg` 列）。跨口径比值会系统性偏低。
30. **`run_step6_3.py --skip-config` 仍会启动仿真**：该开关只跳过"重新生成 config"，**不**跳过运行。生成配置请直接调用
    `make_config_6_3.build_one(...)`，**不要**误跑 runner（历史上曾因此清空 `reports/matsim_assignment/lambda_0p050/ITERS/`）。
31. **重跑 6.3.3B 必须换独立输出目录**：`make_config_6_3.build_one(out_root=..., cfg_path=..., run_prefix=...)` 已参数化；
    务必指向 `reports/matsim_assignment_6_3_3b/` 且 `runId=step6_3_3b_lambda_*`，否则会覆盖 6.3 既有 linkstats。
32. **RoadCat 分层必须用 LTA `RoadCat`，不是 OSM `highway`**：6.3.2 crosswalk 里两列并存，但 `highway` 是**逐边**属性
    （1,278 断面中 286 个多值），只有 `RoadCat` 是**断面级**常量（CATA/CATB/CATC/CATD/CATE/SLIP_ROAD）。用 `highway` 会把
    快速路拆成 `motorway`/`motorway_link`/`trunk` 等，**与 LTA 口径不一致、分层失真**。7.1 已加断面级一致性断言。
33. **相关类指标对 n<2 分组无定义**：CATE 仅 1 条断面，`np.corrcoef`/Spearman 会给 `nan` 并刷 numpy 警告
    （"Degrees of freedom <= 0"）。`metric()` 已加 `n≥2 且双方差>0` 防护，小类只出计数/误差类指标。
34. **校准期间不要因某个 λ 的 r 略高就选 λ\***：7.1 证 3λ 的 r 极差仅 **0.002**、Sim/Obs 极差 <**0.012**，
    全在噪声量级。λ 的辨识须待 Step 7 引入 capacity/route choice 等**能改变路径结构**的参数之后。
35. **MATSim config_v2 的参数在 `<param name= value=/>` 属性里，不是元素文本**：用 ElementTree 取
    `.text` 只会得到空串（7.2 审计脚本第一版全部参数为 null 的根因）。正确做法：module 名/param 名
    来自 `attrib["name"]`、值来自 `attrib["value"]`。同理 **`*.output_config*.xml` 是 MATSim 运行导出物**，
    做参数基线必须用 authored config（`matsim/step6_3/config_lambda_*.xml`），并过滤掉 output_config。
36. **`network_links_source_copy.csv` 没有 capacity 列**（只有 from/to/travel_time/length/speed/highway/lanes/name）：
    逐边 capacity/permlanes/freespeed 必须解析 MATSim 网络 XML（`network_cleaned.xml.gz`，link id
    `e{from}_{to}` 可反解合并）。且 CSV `lanes` 有 272,860 行缺失（service 类为主），6.1 建网时已用
    默认值补齐进 XML → **以 XML `permlanes` 为准**，不要拿 CSV lanes 判"无效"。
37. **`flowCapacityFactor` 的想当然值不可信**：审计前一直按"应该是 0.435"讨论，实测 = **1.0**。
    校准前先审计 config 实际值，任何"理论一致值"（0.435 = 200k/459,794）都必须与落盘 config 对照。
38. **MATSim 2026.0 强制 `storageCapacityFactor == flowCapacityFactor`**：`GlobalConfigGroup.checkConsistency`
    相对容差**硬编码 0.0**，且对应 `@StringSetter` 在源码中被注释——**无法经 XML 放宽**（冒烟 f=0.75 +
    storage=1.0 直接中止）。做 capacity 实验必须两 factor **同值** patch；这也是官方 sampled-population
    语义（两 factor 是同一语义单元），想"只压 flow 保 storage"在 2026.0 走不通。
39. **capacity factor 只动整体通量、不动相对分配**：7.2.2 实证 f 从 0.50 扫到 1.50，CATA/SLIP_ROAD
    Sim/Obs **比值恒 0.366**（同向近比例移动）。单迭代 + freespeed TT 下路径选择零拥堵反馈，capacity
    只决定"挤过去多少车"。凡结构错配（类别间 Sim/Obs 比例失衡），不要指望扫 capacity 解决——直接查
    route choice。
40. **拥堵反馈也救不了结构错配（7.3.1 补充坑 39）**：20 迭代 × 每轮全员 ReRoute + 拥堵 TT 下路径已
    完全重优化，CATA/SLIP 比值仍只在 0.363–0.389 带内振荡、r_CATA 始终 ≈0 → **单迭代自由流最短路
    不是结构性低估的原因**。逐迭代轨迹存在奇偶振荡（±0.006 量级，ReRoute 交替用上一轮 TT 所致），
    判读时看检查点/均值，勿把振荡当趋势。结构错配的剩余候选：网络拓扑表达（快速路-匝道连通性、
    转向限制）、crosswalk 空间对位。
41. **plans/网络对接的 id 口径**：`network_links_source_copy.csv` **没有 `matsim_link_id` 列**——plans
    route 里的 link id 是 `e{from}_{to}` 约定（6.1 建网），须由 `from_node/to_node` 构造后再 join
    （构造唯一性由 Step 4 审计 0 重复有向边保证）。plans 的 route 是**单行长文本**，逐行正则可解析；
    200k routes × 数十 link 的逐 link 查询必须用**字典视图**（`df.loc` 逐行查会慢两个数量级），
    且同一条 route 不要分类两次。

---

## 5. 复用与扩展

- **用 AM-v1 阻抗重跑 Census 约束的 Prior OD**（已产 `reports/od_prior_5c/`）：
  ```bat
  python scripts\od\build_prior_od_5b.py ^
    --out reports/od_prior_5c --prefix prior_od_5c ^
    --impedance reports/od_impedance_ampeak/ampeak_impedance_matrix.parquet ^
    --label "Step 5C"
  ```
- **用 AM-v2 阻抗生成 Step 5C.1 Prior OD（已执行）** —— 两种等价方式：
  ```bat
  :: (a) 独立脚本（推荐，产物名带 5c1 后缀）
  python scripts\od\build_prior_od_5c1.py

  :: (b) 复用参数化的 5B 脚本（产物名不同）
  python scripts\od\build_prior_od_5b.py ^
    --out reports/od_prior_5c1 --prefix prior_od_5c1 ^
    --impedance reports/od_impedance_ampeak_v2/ampeak_impedance_v2.parquet ^
    --label "Step 5C.1"
  ```
- **对比 T^5B vs T^5C.1（时长 / 区内 / 跨区 / 长距离 / Region×PA 块流量）+ 守恒校验**：
  ```bat
  python scripts\od\compare_prior_od.py
  ```
- **生成 MATSim 网络底座（Step 6.1）并独立复核**：
  ```bat
  python scripts\od\build_matsim_network.py
  python scripts\od\validate_matsim_network.py
  ```
- **生成 MATSim population/plans（Step 6.2）并独立复核**：
  ```bat
  python scripts\od\build_matsim_population.py                      REM 默认 λ=0.05/0.075/0.10，各 200k agents
  python scripts\od\build_matsim_population.py --target-agents 300000
  python scripts\od\validate_matsim_population.py
  ```
- **生成 6.2B 保底采样 + 空间下分 population 并独立复核**：
  ```bat
  python scripts\od\build_matsim_population_6_2b.py                 REM 默认 λ=0.05/0.075/0.10，各 200k agents
  python scripts\od\build_matsim_population_6_2b.py --target-agents 300000
  python scripts\od\validate_matsim_population_6_2b.py
  ```
- **调 5C.1 传播参数**：`--geom-max-m`（几何半径，默认 100）、`--name-min-links`（路名最小 LTA 证据，默认 3）、`--band8-speed`（默认 75）。
- **Step 6.3 连通性修复（6.3a）并生成 connected 场景**：
  ```bat
  python scripts\matsim\prepare_connected_scenario.py            REM NetworkCleaner + 端点重吸附
  python scripts\matsim\prepare_connected_scenario.py --force-clean   REM 强制重跑 NetworkCleaner
  ```
- **跑 MATSim AM assignment（6.3b）** —— 需要项目本地 JDK25（`tools/jdk-25*/`）：
  ```bat
  python scripts\matsim\matsim_env.py                 REM 打印 JDK / jar / classpath 环境自检
  python scripts\matsim\make_config_6_3.py            REM 只生成 3 套 config
  python scripts\matsim\run_step6_3.py --smoke 2000   REM 冒烟测试（2000 agents）
  python scripts\matsim\run_step6_3.py                REM 全量 3×200k agents（约 41 min）
  python scripts\matsim\run_step6_3.py --lambdas 0p050 --heap 16g
  ```
- **重跑 3λ + 逐小时对照（6.3.3B）** —— population 换成 6.3.3A 剖面版，网络仍 `network_cleaned.xml.gz`：
  ```bat
  REM 1) 生成 3 套 config（指向 departure population 与独立输出目录）
  python -c "import sys;sys.path.insert(0,'scripts/matsim');import make_config_6_3 as c;from pathlib import Path;p=c.PROJECT_ROOT;pop=p/'reports/matsim_departure_6_3_3a';out=p/'reports/matsim_assignment_6_3_3b';[c.build_one(l,pop_dir=pop,out_root=out,run_prefix='step6_3_3b_lambda_',cfg_path=c.CONFIG_DIR/f'config_lambda_{l}_6_3_3b.xml') for l in c.LAMBDAS]"
  REM 2) 跑 3λ（~55 min；⚠️ 勿用 --skip-config，它仍会启动仿真）
  python scripts\matsim\run_step6_3.py --lambdas 0p050 0p075 0p100 --skip-config ^
    --pop-dir reports/matsim_departure_6_3_3a --out-root reports/matsim_assignment_6_3_3b ^
    --run-prefix step6_3_3b_lambda_ --cfg-suffix _6_3_3b
  REM 3) 逐小时对照 → STEP6_3_3B_REPORT.md + step6_3_3b_*.csv
  python scripts\od\compare_step6_3_3b.py
  ```
  参数：`--assign-root`（默认 `reports/matsim_assignment_6_3_3b`）、`--out`、`--scale`（默认 2.29897）。
- **第一次对照 q_sim vs q_obs（6.3c）**：
  ```bat
  python scripts\matsim\compare_step6_3.py            REM → STEP6_3_COMPARISON.md + step6_3_*.csv
  ```
  ⚠️ 运行前需已装**项目本地 JDK25**（`tools/jdk-25.0.4.1+1/`）与 **MATSim 2026.0 release**
  （`tools/matsim-2026.0/`）。两者都是便携包，不污染系统环境；`MATSIM_JAVA` / `MATSIM_HOME`
  环境变量可覆盖自动定位。
- **断面级 crosswalk 对照（6.3.2）**：
  ```bat
  python scripts\od\build_linkflow_crosswalk_6_3_2.py                 REM 修正版（沿线采样+路名一致+逐断面中位）
  python scripts\od\build_linkflow_crosswalk_6_3_2.py --corridor-radius 60 --sample-step-m 20
  python scripts\od\build_linkflow_crosswalk_6_3_2.py --mode generous ^
    --out-dir reports/matsim_assignment_6_3_2/_generous_diagnostic    REM 复现原稿 sum 伪影（留档用）
  ```
  参数：`--mode tight|generous`（默认 tight）、`--corridor-radius`（默认 45 m）、`--sample-step-m`（默认 25 m）、
  `--scale`（默认 2.29897）、`--lambdas`、`--out-dir`。
- **AM 出发时刻剖面（6.3.3A）**：
  ```bat
  python scripts\od\build_departure_profile_6_3_3a.py                 REM TrafficFlow 驱动 07/08 时间形状 → 3λ population
  python scripts\od\build_departure_profile_6_3_3a.py --lambdas 0.05 0.075 0.10 --seed 20260912
  ```
  参数：`--project-root`（默认 `D:\Luan\2026-05\2_Singapore`）、`--lambdas`（默认 0.05/0.075/0.10）、`--seed`（默认 20260912）。
  输入取 `reports/matsim_population_6_2b_connected/`（连通性修复版）；输出到 `reports/matsim_departure_6_3_3a/`。
  **运行后看**：`departure_profile_validation.json`（`status=PASS`、`ΣEF=459,794`、`departure_ef_share_07_08≈0.487`）。
- **构建 TrafficFlow 校准靶场（7.1，只评价不改模型）**：
  ```bat
  python scripts\od\build_calibration_target_7_1.py      REM → reports/od_calibration_7_1/ + STEP7_1_REPORT.md
  ```
  参数：`--assign-root`（默认 `reports/matsim_assignment_6_3_3b`）、`--crosswalk`（默认 6.3.2 tight crosswalk）、
  `--scale`（默认 2.29897）、`--out`（默认 `reports/od_calibration_7_1`）。
  输出：`calibration_target_lambda_0p{050,075,100}.csv`（断面级）、`calibration_target_summary.csv`（3λ×3 窗总体）、
  `calibration_target_by_roadcat.csv`（LTA RoadCat 分层）、`calibration_target_definition.json`
  （`parameters_changed=false`、`lambda_selected=false`）。
- **MATSim 参数审计 + capacity sweep 计划（7.2.1，只审计不改模型）**：
  ```bat
  python scripts\od\audit_matsim_calibration_7_2.py      REM → reports/od_calibration_7_2/（6 个产物）
  ```
  输入：`matsim/step6_3/*.xml`（全部 config）、`reports/matsim_network/network_cleaned.xml.gz`
  （逐边 capacity/permlanes/freespeed）、`network_links_source_copy.csv`（highway 等级）、7.1 `calibration_target_summary.csv`。
  运行后看 `step7_2_audit.json`（`status=PASS`、基线 config 关键参数、网络容量分布）与
  `network_capacity_audit.csv`（逐 highway 等级 capacity/lane）。
  ⚠️ `capacity_sweep_plan.csv`（0.50/0.75/1.00/1.25/1.50）**只是实验计划，不会自动改参跑仿真**；
  7.2.2 扫描脚本必须等审计结论（`flowCapacityFactor=1.0` 容量过剩）确认执行方案后再写。
  【7.2.2 已执行，命令如下】：

```bat
REM 冒烟（2000 agents，f=0.75，验证 patch 真实生效，~2 min）
python scripts\od\run_capacity_sweep_7_2_2.py --smoke 2000
REM 全量 5 档（λ=0.05，每档 ~9 min，storage=flow 同值 patch）
python scripts\od\run_capacity_sweep_7_2_2.py
REM 对照（直接 import 7.1 冻结口径 obs_load/cross_load/metric）
python scripts\od\compare_capacity_sweep_7_2_2.py
REM → reports/od_calibration_7_2_2/（5×capacity_factor_*/ + summary + by_roadcat + sections + ratio_pivot
REM   + f1p00_vs_frozen_633b_consistency.json + capacity_sensitivity_definition.json + STEP7_2_2_REPORT.md）
```

  【7.3.1 已执行，命令如下】：

```bat
REM 冒烟（2000 agents × 3 迭代，验证 ReRoute 逐轮生效 + 每迭代 linkstats）
python scripts\od\run_congestion_feedback_7_3_1.py --smoke 2000
REM 全量（20 迭代主运行覆盖检查点 1/5/10/20 + 5 迭代嵌套验证，~4h）
python scripts\od\run_congestion_feedback_7_3_1.py
REM 对照（import 7.1 冻结口径；结构轨迹 + 检查点 + 嵌套/一致性双验证）
python scripts\od\compare_congestion_feedback_7_3_1.py
REM → reports/od_calibration_7_3_1/（iterations_20/ + iterations_05/ + 逐迭代 summary/by_roadcat/sections
REM   + structure_trajectory + checkpoints + nesting_check.json + it0_vs_frozen_633b_consistency.json
REM   + congestion_feedback_definition.json + STEP7_3_1_REPORT.md）
```

  【7.3.2B 已执行，命令如下】：

```bat
python scripts\od\diagnose_route_structure_7_3_2b.py ^
  --trips  reports\matsim_assignment_6_3_3b\lambda_0p050\ITERS\it.0\step6_3_3b_lambda_0p050.0.trips.csv.gz ^
  --plans  reports\matsim_assignment_6_3_3b\lambda_0p050\ITERS\it.0\step6_3_3b_lambda_0p050.0.plans.xml.gz
REM → reports/od_route_diagnosis_7_3_2b/（route_agent_summary + route_class_summary
REM   + route_transition_matrix + route_od_consistency + route_diagnosis_summary.json + STEP7_3_2B_REPORT.md）
REM 7.3.2A 审计产物在 reports/od_calibration_7_3_2a/（外部环境执行，无项目内脚本）
```

---

## 6. 冻结 / 待定

| 项 | 状态 |
|---|---|
| Step 3B.1 Attraction | 🔒 冻结 |
| Step 4 `C^FF` | 🔒 冻结 |
| Step 5B Census-constrained Prior OD 基线 | 🔒 冻结 |
| Step 5C.1 `C^AM,v2` | 🔒 冻结（**38.35% 长度覆盖，不再继续追求覆盖**） |
| Step 5C.1 Prior OD `T^5C.1` | ✅ PASS（5 组 λ，守恒到机器精度） |
| Step 5C/5C.1 最终 λ* | ⏳ **暂不冻结**（由 Step 6 MATSim assignment + Step 7 TrafficFlow 校准决定；Step 6 试验先用 0.05 / 0.075 / 0.10） |
| Step 6.1 MATSim 网络底座 | 🔒 冻结（独立 XML 结构复核 PASS，不再折腾网络层） |
| Step 6.2 car-only Population/Plans | 🔒 冻结（第一版基线；3×200k agents，cell 覆盖 59%） |
| Step 6.2B 保底采样 + 空间下分 Population | ✅ **PASS**（cell 覆盖 **100%**、ΣEF=**459,794**、独立复核 PASS） |
| Step 6.2C agent 时间属性 / rerouting | ◑ 部分（出发时刻剖面已由 6.3.3A 完成；活动时长 / rerouting 待做） |
| Step 6.3a MATSim 路由网络 `network_cleaned.xml.gz` | ✅ **PASS**（car 主连通分量；原 `network.xml.gz` 保持冻结） |
| Step 6.3a connected population（端点重吸附） | ✅ **PASS**（`reports/matsim_population_6_2b_connected/`；位移中位 3.3 m） |
| Step 6.3b 第一次 AM assignment（单迭代 QSim） | ✅ **PASS**（3λ × 200k，`lost=0`） |
| Step 6.3c 第一次 q_sim vs q_obs 对照 | ✅ **PASS**（Σsim/Σobs=0.647、r=0.306、GEH<5=7.5%；**λ 不可分辨**） |
| Step 6.3.2 断面 Crosswalk 重构 | ✅ **PASS**（收紧至中位 **8 边/断面**；tight+median sim/obs=**0.618**、r=**0.293**；**CATA 0.515 / 断面内 r≈0**；**排除 crosswalk 粒度疑点**） |
| Step 6.3.3A Departure-Time Profile（AM 出发时刻剖面） | ✅ **PASS**（TrafficFlow 驱动：07–08=**48.71%** / 08–09=**51.29%**；**ΣEF=459,794 不变**；消除 08:00 单点脉冲） |
| Step 6.3.3B 重跑 3λ + 逐小时对照 | ✅ **本轮 PASS**（ratio_7=**0.734** / ratio_8=**0.876**；**CATA 0.584/0.739**；EF 加权通勤 **61.8→19.4 min**；**相关未提升**） |
| Step 7.1 TrafficFlow 校准靶场 | ✅ **PASS**（冻结 `q_obs↔q_sim` 评价体系，**n=1,278** 覆盖 97.48%；`parameters_changed=false`、`lambda_selected=false`；**不改任何模型**） |
| Step 7.2.1 MATSim 参数审计 | ✅ **PASS**（25 个 config XML 全解析 + 693,575 边逐边 capacity/permlanes/freespeed 审计 0 无效值；**基线 `config_lambda_0p050_6_3_3b.xml`：`flowCapacityFactor=1.0`（⚠️ 非 0.435，容量过剩 ~2.3×）**、SpeedyALT、单迭代 ReRoute 无效；`model_parameters_changed=false`） |
| Step 7.2.2 Capacity-only sweep（0.50/0.75/1.00/1.25/1.50） | ✅ **PASS**（f=1.00 与 6.3.3B 逐位复现；**CATA/SLIP 比值全档恒 0.366 → capacity 非结构杠杆**；两 factor 同值 = MATSim 2026.0 引擎硬约束） |
| Step 7.3.1 Congestion-feedback sensitivity（1/5/10/20 迭代） | ✅ **本轮 PASS**（嵌套设计验证 5/5 逐位一致 + it.0 与 6.3.3B 逐位复现；**比值 0.366→仅 0.377、r_CATA 仍≈0 → 拥堵反馈亦非结构杠杆**；单迭代自由流最短路不是结构性低估原因） |
| Step 7.3.2A Motorway–Ramp Connectivity Audit | ✅ **PASS**（纯拓扑零仿真；主线连续 + 接口完整 → **不修冻结网络**；Airport Boulevard 1 处 spot-check 级） |
| Step 7.3.2B Route-structure Diagnosis | ✅ **本轮 PASS**（**A"不走高速"否定：61.1% 路线 / 41.5% 长度用 motorway；0/196,447 OD 多路径**；ramp 链 5.12M 次 ml→ml；→ 7.3.3 route×crosswalk 断面级对照分辨 B/C） |

---

## 7. 变更记录

| 日期 | 变更 |
|---|---|
| 2026-09-12 | **Step 7.3.2A Motorway–Ramp Connectivity Audit（PASS，纯拓扑零仿真）+ Step 7.3.2B Route-structure Diagnosis（PASS）**。7.3.2A：用户外部环境审计冻结 `network_cleaned.xml.gz`，产物归档 `reports/od_calibration_7_3_2a/`（`STEP7_3_2A_REPORT.md` + transition_matrix + endpoint_diagnostics + endpoint_anomalies + `step7_3_2a_validation.json` `status=PASS`）；**主线连续**（无相关上游仅 1/4,744 = Airport Boulevard，spot-check 级；无下游 0）、**主线-匝道接口完整配对**（mw→ml 240 / ml→mw 240、mw→mw 5,855）、motorway+ramp 最大弱连通分量 **99.969%**、ramp terminal 2.65%/2.75% 接 primary/trunk/secondary 属正常出入口形态 → **不支持网络断裂解释 CATA 低估，不修改冻结网络**。7.3.2B：新增 `scripts/od/diagnose_route_structure_7_3_2b.py`（运行前修复：① source copy CSV 无 `matsim_link_id` → 构造 `e{from}_{to}`；② 单次遍历 + 字典视图替代双重分类 + 逐 link `df.loc`；③ 显式传 it.0 实际文件名），解析 6.3.3B λ=0.05 it.0 `plans.xml.gz`（route type=links 单行）+ `trips.csv.gz` → **200,000/200,000 对接、0 未知 link**。**核心判定**：**A"高速很少被选"否定**（**61.06% 路线 / 41.48% 长度用 motorway**，第一大道等级；结合 CATA sim/obs 0.584/0.739 < 总体 0.744/0.889 ⇒ 被大量使用但相对仍不足/错位）；**确定性**：196,447 OD **0 多路径**（完全单一最短路）；**ramp 链**：`ml→ml` 转移 5.12M（用 ramp 路线平均 ~42 个微段、~30 m/段 = 碎片化表达）、`m→ml→m` 精确三元组 0、`primary→ml` 84,887 / `ml→primary` 76,502；**B（OD 级空间分散）部分成立、C（观测-表达系统差异）保留** → **下一步 7.3.3：route×crosswalk 断面级对照**（零仿真），route-choice 参数实验优先级进一步下降。readme 已同步（流程图、脚本清单 +1 行 + 7.3.2A 归档注记、§2.12/§2.13、状态表、坑 41、复用命令 7.3.2B、冻结表、变更记录）。**冻结不动**：全部上游 + 7.1/7.2.1/7.2.2/7.3.1/7.3.2A；**λ 暂不冻结**。 |
| 2026-09-12 | **Step 7.3.1 Congestion-feedback Sensitivity（λ=0.05，唯一变量 = lastIteration）**。新脚本 `run_congestion_feedback_7_3_1.py`（复用 `build_one` 同源 + 仅 patch lastIteration + 磁盘控制：中间迭代不写 events/plans/trips/snapshots、linkstats 每迭代保留）与 `compare_congestion_feedback_7_3_1.py`（import 7.1 冻结靶场口径）。**嵌套设计**：同 seed + 确定性 ReRoute（`routingRandomness=0.0`）⇒ lastIteration 只是截断 → **一次 20 迭代运行**覆盖预注册检查点 {1,5,10,20}（↔ it.0/4/9/19）+ 一次 5 迭代运行验证嵌套性；**双重确定性验证 PASS**（嵌套 it.0–4 与主运行逐位一致 5/5；it.0 与冻结 6.3.3B 逐位复现）。主运行 20 迭代 × 200k agents `lost=0`、~3h50m。**结果**：总体 r 0.279/0.249 → 0.325/0.290（小幅改善=通量水平效应）；CATA 0.584/0.739 → 0.651/0.780、SLIP 1.594/2.033 → 1.718/2.075 **同向上升**；**CATA/SLIP 比值 0.366 → 仅 ~0.377（+3%，全程带 0.363–0.389，奇偶振荡 ±0.006）**；**r_CATA 20 迭代始终 ≈0（−0.06~+0.02）**。**判读（预注册判据不成立）**：拥堵反馈改变通量水平、不改变相对分配结构 → **第二个否定性结论：拥堵反馈 / 迭代式 ReRoute 也不是 CATA↔SLIP_ROAD 结构错配的杠杆**；单迭代自由流最短路不是结构性低估原因。**证据指向**：capacity（7.2.2）+ 拥堵反馈（本步）均已排除，7.3.2 route-choice 参数先验已弱；**建议下一步：快速路-匝道连通性专项审计**（零仿真成本），视结果定 7.3.2 取舍。**冻结不动**：全部上游 + 7.1/7.2.1/7.2.2；**λ 暂不冻结**。 |
| 2026-09-12 | **Step 7.2.2 Capacity-only Sensitivity（λ=0.05 × f∈{0.50,0.75,1.00,1.25,1.50}，5 × 单迭代 QSim ~45 min）**。新脚本 `run_capacity_sweep_7_2_2.py`（复用 `make_config_6_3.build_one` 同源 + 仅 patch f + `--smoke`/`verify_patch` 防呆）与 `compare_capacity_sweep_7_2_2.py`（直接 import 7.1 的 `obs_load/cross_load/metric`，完全复用冻结靶场口径）。**引擎硬约束（坑 38）**：MATSim 2026.0 `GlobalConfigGroup.checkConsistency` 强制 `storageCapacityFactor == flowCapacityFactor`（相对容差硬编码 0.0、对应 setter 在源码中被注释，**无法经 XML 放宽**；从 `matsim-2026.0-sources.jar` 逐行确认）→ sweep 两 factor **同值**（官方 sampled-population 语义）；冒烟（f=0.75 + storage=1.0）直接抓到该中止。**结果**：f=1.00 与冻结 6.3.3B **逐位复现**（ratio/r 三窗全同，确定性核对 PASS）；总体 r 对 f 不敏感（07-08 稳定 0.28–0.30、08-09 稳定 0.25–0.26），Sim/Obs 单调随 f 上升但全程 <1（f=1.50 → 0.767/0.935）；**CATA 与 SLIP_ROAD 同向近比例移动，CATA/SLIP 比值全档恒 0.366（极差 ≤0.007），CATA 内 r 全档 ≈0 甚至轻微为负（−0.06~−0.01）** → **capacity 不是 CATA↔SLIP_ROAD 结构错配的杠杆**（单迭代 + SpeedyALT + freespeed TT ⇒ 路径选择零拥堵反馈，f 只动整体通量不动相对分配）；**不存在"正确的 f"修复快速路低估**，f 的选择回到规模一致性语义（0.435 候选）留待 7.4/7.5。**判读：转 Step 7.3 Route Choice**（多迭代 ReRoute / 拥堵反馈 TT；判据：CATA/SLIP 比值显著偏离 0.366 ⇒ route choice 主因）。**冻结不动**：全部上游 + 7.1 靶场 + 7.2.1 审计基线；**λ 仍冻结**。 |
| 2026-09-12 | **Step 7.2.1 MATSim 参数审计（只审计，不改任何模型）**。用户交付 `scripts/od/audit_matsim_calibration_7_2.py`，运行前审查修复 **3 处缺陷**：① config 参数全 null——MATSim config_v2 参数在 `<param name= value=/>` **属性**而非文本，重写 `flatten_xml`（module/param 名嵌入 path、value 作 text，坑 35）；② baseline 误选 `*.output_config_reduced.xml`（运行导出物）→ 过滤 output_config，正确选中 **`matsim/step6_3/config_lambda_0p050_6_3_3b.xml`**；③ `network_links_source_copy.csv` **无 capacity 列**（原脚本必 KeyError）→ 改为解析 `network_cleaned.xml.gz` 逐边 capacity/permlanes/freespeed、按 `e{from}_{to}` 合并，并以 XML `permlanes` 为权威（CSV lanes 272,860 行缺失已被 6.1 默认值补齐，`lanes_mismatch=0`，坑 36）。**产物** `reports/od_calibration_7_2/`：parameter_audit.csv（逐参数展开）、config_summary.csv（25 XML）、network_capacity_audit.csv（逐 highway 等级）、calibration_target_baseline.csv（7.1 基线复制）、capacity_sweep_plan.csv（0.50/0.75/1.00/1.25/1.50 **仅计划**）、step7_2_audit.json（**status=PASS**、`model_parameters_changed=false`、`lambda_selected=false`）。**审计核心发现**：⚠️ **`qsim.flowCapacityFactor=1.0`（非预想的 0.435，坑 37）** + `storageCapacityFactor=1.0` + 0.435 抽样率 ⇒ **网络容量相对需求过剩 ~2.3×，QSim 内几乎不形成拥堵**；`routingAlgorithmType=SpeedyALT`；`first=last=0` 单迭代 ⇒ **ReRoute 策略完全无效，route choice = 一次性 freespeed 最短路**；travelTimeCalculator binSize 900 s / optimistic aggregator（单迭代下 TT=freespeed）；网络 693,575 边 0 无效 capacity/permlanes，capacity=permlanes×等级默认（median 800、p95 3,600 veh/h；motorway 1,900/lane）。**对 7.2.2 sweep 的判据**：capacity factor 0.50–1.50 扫描中 CATA(0.584/0.739→1) 与 SLIP_ROAD(1.594/2.033→1) 若显著改善 = capacity 主导（先校 capacity/`flowCapacityFactor`，理论一致值 0.435）；若几乎不动 = **route choice 效用主导**（直接进 7.3）。**冻结不动**：全部上游 + 7.1 靶场；**λ 暂不冻结**；下一步 **7.2.2 capacity-only sweep（扫描脚本待写，勿提前写死）**。 |
| 2026-09-12 | **Step 7.1 TrafficFlow 校准靶场（正式收口 Step 6.3，只建评价体系不改模型）**。新增 `scripts/od/build_calibration_target_7_1.py`；产物 `reports/od_calibration_7_1/`（3λ 断面级靶场 CSV + summary + by_roadcat + `definition.json`，`parameters_changed=false`、`lambda_selected=false`）。**运行前修复两处口径缺陷**：① 分层由 OSM `highway` 改为 **LTA `RoadCat`**（`highway` 为逐边属性、1,278 断面中 286 个断面内多值；`RoadCat` 为断面级常量、无一多值），并在 `cross_load` 加断面级一致性断言；② `metric()` 加 `n≥2` 防护，消除 CATE（n=1）Spearman 的 numpy 警告 → 重跑 0 警告。**靶场口径（冻结）**：观测 = TrafficFlow 工作日逐日中位 → LinkID×Hour 中位；仿真 = 6.3.3B `it.0` linkstats × scale **2.29897**；断面归属 = 6.3.2 tight crosswalk（断面内匹配边**中位数**）；**n=1,278**（1,311 断面覆盖 97.48%）、匹配边中位 8、`name_match_rate` 均值 0.923。**总体**（λ=0.05）：r **0.279/0.249/0.267**、ρ≈0.38、Sim/Obs **0.744/0.889/0.819**、GEH<5 **6.9–10.0%**、Bias 全负 → 系统性少分配。**RoadCat 结构信号**（与 6.3.2/6.3.3B 一致）：**CATA 0.584/0.739 且断面内 r≈0（−0.01/−0.06）**、**SLIP_ROAD 1.594/2.033（WMAPE 1.4–1.8）**、**CATC 唯一装得好（r 0.60–0.66、Sim/Obs 0.74–0.75）** → 问题集中在**快速路↔匝道路径分配**，非全局 scale。**λ 不可分辨定量确认**：3λ r 极差仅 **0.002**、Sim/Obs 极差 <**0.012**、CATA 极差 **0.012** → λ 辨识必须等引入 route choice/capacity 等结构性机制后再做（坑 34）。**诊断指向 7.2**：① route choice 参数；② network `capacity`/`permlanes` 审查（当前为假设值）；③ `qsim.flowCapacityFactor=0.435`。目标函数 `J(θ)=w1·E_GEH+w2·E_RMSE+w3·E_MAE+w4·E_corr`。**冻结不动**：3B.1/4/5B/5C.1/6.1/6.2/6.2B/6.3.2/6.3.3A/6.3.3B；**λ 暂不冻结**；下一步 **7.2（route choice → capacity/lanes）**。 |
| 2026-09-12 | **Step 6.3.3B 多时段 MATSim Assignment + 逐小时对照**。新增 `scripts/od/compare_step6_3_3b.py`；参数化 `make_config_6_3.build_one(out_root/cfg_path/run_prefix)` 与 `run_step6_3.py --pop-dir/--out-root/--run-prefix/--cfg-suffix`，**未破坏 6.3 既有产出**。**唯一切换点**：`inputPlansFile` 由 `matsim_population_6_2b_connected/` → `matsim_departure_6_3_3a/`；网络仍 `network_cleaned.xml.gz`；OD / λ / Home-Work link / crosswalk **全不变**。**运行**：3×200,000 agents 单迭代 QSim，`lost=0`，仿真起点由 08:00 提前到 **07:00**，冒烟 `HRS7-8=269,600`（28,215 边）≠0、`HRS8-9=322,181` → **单点脉冲消除**。**逐小时对照**（n=1,311 断面、crosswalk 覆盖 97.48%、复用 6.3.2 tight crosswalk）：λ=0.05 **r_7=0.284 / r_8=0.252 / r_AM=0.271**、**ratio_7=0.734 / ratio_8=0.876 / ratio_AM=0.806**、GEH7<5=9.76% / GEH8<5=8.39%；λ 仍**几乎不可分辨**（ratio_7 0.734/0.734/0.727、r_7 0.284/0.285/0.286）。**RoadCat**（λ=0.05）：**CATA 0.584(h7)/0.739(h8)、断面内 r −0.012/−0.057**；CATB 0.757/0.808；SLIP_ROAD 1.594/2.033；CATC 0.741/0.750。**EF 加权通勤 61.8 → 19.4 min**（均速 ≈19 → ≈41 km/h）。**判读**：① 出发时刻脉冲**确为人为拥堵主因**（通勤时间减半、水平偏差由 0.647 收窄至 0.73/0.88）；② **快速路结构性低估仍在**（CATA<1、断面内 r≈0）→ **不再调 departure time，转 Step 7（network capacity / 车道表达 / route choice / OD assignment calibration）**；③ 相关未随剖面提升（0.306 → 0.285/0.255，口径更诚实）。**事故如实记录**：生成配置时误用 `--skip-config`（仍会启动仿真）导致一次非预期运行清空 `reports/matsim_assignment/lambda_0p050/ITERS/`；λ=0.05 仿真数据已由 `step6_3_sim_linkstats_lambda_0p050.csv` 保留、λ=0.075/0.100 未受影响，且已在同一后台任务中**重跑恢复** 6.3 λ=0.05 原始 linkstats。**冻结不动**：3B.1/4/5B/5C.1/6.1/6.2/6.2B；**λ 仍未冻结**；下一步 **Step 7**。 |
| 2026-09-12 | **Step 6.3.3A 出发时刻剖面（Departure-Time Profile）**。新增 `scripts/od/build_departure_profile_6_3_3a.py`。**运行前审查**：全契约核验（200,000 persons = 200,000 home 行 = 200,000 带 `end_time`；ΣEF=459,794；agent_id 唯一；home 属性顺序 `type→link→end_time`），**未发现致命缺陷**，仅做 2 处低风险增强：清理 `locate_population` 重复列表项 + 在 validation 中补 **EF 加权时间占比**。**方法**：`TrafficFlow_Data.json` → 每 `LinkID×Hour` **工作日逐日中位数** → 全网 07/08 时间形状 → 3λ population 分配出发小时（`round(s7·N)`）+ 小时内**秒级随机**微扰 → 流式改写 `home` 活动 `end_time`（不改 OD/λ/空间结构）。**结果**：07–08=**48.7103%**（97,421 agents）/ 08–09=**51.2897%**（102,579 agents）；出发时间落 07:00:00–08:59:59；**ΣEF 严格 = 459,794**（3λ）；EF 加权占比 0.4868–0.4877 ≈ 网络占比；XML 200,000 persons/home 改写、`work` 活动 0 处被改；`departure_profile_validation.json` = **PASS**。**基线**取 `reports/matsim_population_6_2b_connected/`（连通性修复版，QSim 必需）。**口径声明**：Census 2020 **无出发时刻维度**（T10/T15 仅行程时间分箱），本轮用 LTA 实测小时交通流构造 **network-observed temporal shape prior**，**不声称**居民 departure-time 观测；Census T10/T15 留作 6.3.3B 独立合理性检验。**冻结不动**：3B.1/4/5B/5C.1/6.1/6.2/6.2B；**λ 仍未冻结**；下一步 **6.3.3B 重跑 3λ + 逐小时对照**。 |
| 2026-09-12 | **Step 6.3.2 LTA 观测 ↔ 断面 Crosswalk 重构**。新增 `scripts/od/build_linkflow_crosswalk_6_3_2.py`（用户提供，**运行前修复 1 处致命 bug + 1 处方法学缺陷**）：①致命 bug `sim.merge(e,on="LINK")` 因 `e` 无 `LINK` 列而 `KeyError` → 先重命名 `matsim_link_id→LINK`；②方法学：原稿"质心 120m 全边 + 250m 同名边 + **求和**"→ **77 边/断面**、`sim_obs_ratio` 被抬到 **16.90**（伪影，已复现留档 `_generous_diagnostic/`）。③修正为"**沿线采样（25m/45m）+ 路名一致**"收紧候选（**中位 8 边/断面**），逐断面取**中位数**（另出 mean/max/sum 四口径 + RoadCat 分解）。**结果**：λ=0.05 下 sim/obs=**0.618**、r=**0.293**、ρ=0.398；**CATA(快速路) 0.515、SLIP_ROAD 1.398**，三口径下 **CATA 断面内 r≈0**。**判定**：修正 crosswalk 后总量比 0.618≈6.3 的 0.647、CATA 0.515≈6.3 的 0.510 → **crosswalk 粒度不是主因，快速路低估是分配侧真实信号**。KPE 专项：全网缩放求和 451,757≈观测 22 断面之和 450,748（比值 1.00），但仿真单边最大仅 4,584/h vs 观测断面中位 17,969/h → **点流量低 4–20×**。**冻结不动**：3B.1/4/5B/5C.1/6.1/6.2/6.2B；**λ 仍未冻结**；下一步 **6.3.3 出发时刻剖面** |
| 2026-09-12 | **Step 6.3 第一次 MATSim AM assignment（6.3a/6.3b/6.3c）**。① **6.3a 连通性修复**：新增 `scripts/matsim/prepare_connected_scenario.py`；官方 `NetworkCleaner` 706,554→**693,575** 边（−1.84%）、**332 锚点 0 受影响**；重吸附 5,066–5,156/200,000 agent（2.55%），位移中位 **3.3 m**；car 连通性检查由 **abort** 变为 **0 边被移除**。② **建立最小 MATSim runner**：新增 `matsim_env.py`（本地 **JDK25 Temurin + MATSim 2026.0 release**，无 Maven/Gradle、不污染系统）、`make_config_6_3.py`（以 `CreateFullConfig` 为基线）、`run_step6_3.py`；**运行前修复 6 处 MATSim XML/DTD 合规缺陷**（DOCTYPE 缺失 → "Missing DOCTYPE"；`<network changeEvents>`、`<nodes format>`、`<attribute value=>` 三处 DTD 违规；Java 24→25；subprocess UTF-8 解码）。③ **6.3b 全量运行**：3×200,000 agents 单迭代 QSim，`lost=0`，耗时 **41 min**。④ **6.3c 第一次对照**：1,278 条 LTA 链路，Σsim/Σobs=**0.647**（scaled 2.299）、Pearson r=**0.306**、GEH<5=**7.5%**；**λ=0.05/0.075/0.10 几乎不可分辨**（r 0.306/0.308/0.308）→ 当前精度不足以定 λ*。⑤ **结构性诊断**：快速路被系统性低估（KPE 432 条边的仿真 188,481 次通过中，crosswalk 只映射到 22 条、捕获 6,156 次=**3.3%**）→ 原判断主因是 5C.1 的 crosswalk 粒度（**6.3.2 已证伪**）。⑥ 时刻剖面：全部 08:00 出发 → `HRS7-8` 恒为 0、人为拥堵（平均通勤 61.8 min、均速 ~19 km/h）。**冻结保持不动**：3B.1 / 4 / 5B / 5C.1 / 6.1 / 6.2B；**λ 仍未冻结** |
| 2026-09-12 | **Step 6.2B OD-cell 保底采样 + 住宅/就业空间下分**：新增 `build_matsim_population_6_2b.py` 与 `validate_matsim_population_6_2b.py`。**运行前修复 3 处致命缺陷**：①`poi.csv` 坐标列是 `lng/lat`（原检索 `x|lon|longitude` 漏掉 → POI 池静默为空、Work 空间下分从未生效），且需**重投影 EPSG:3414**；②MATSim 元素名应为 `<activity>`（`<act>` 会被 reader 拒绝）；③activity node 改为吸附 link 的 `from_node`（原与 link 不一致）。结果：**cell 覆盖 100%**（71,136/71,136）、**ΣEF=459,794**（单 cell 误差 ≤1.4e-14）、home link **17,052** / work link **5,782**；独立复核 `ALL_CHECKS_PASS=true`；3×200k **53 s**。**λ 仍未冻结** |
| 2026-09-12 | **Step 6.2 Prior OD → MATSim population/plans**：新增 `build_matsim_population.py`（car-only OD + 多测度抽样 agent + home/work 挂 network link）与 `validate_matsim_population.py`（独立复核 XML）。**运行前修复 2 处缺陷**：①行边际列名 `car_work_production`→实际 `car_work_trip_production`（否则崩溃）；②目的地列边际误用 raw `workplace_attraction`（307 非零）→改用冻结的 `workplace_attraction_clean`（304 非零），否则多出 3 个无 seed 支撑的目标列导致 **IPF 10,000 次不收敛**；修复后收敛 13–14 次，行误 ≤8.6e-9。3×200,000 agents；car OD Σ=**459,794**；cell 覆盖 59%、expansion Σ 代表 93.8%；独立复核 `ALL_CHECKS_PASS=true`。**λ 仍未冻结** |
| 2026-09-11 | **Step 6.1 MATSim 网络底座**：新增 `build_matsim_network.py`（Step 4 有向路网 → `network.xml.gz` + Zone→node 映射）与 `validate_matsim_network.py`（独立复核）；429,032 节点 / 706,554 有向边 / 0 重复 / 0 自环 / 0 孤立；**性能 9m00s→38.5s（向量化，内容逐字节一致）** |
| 2026-09-11 | **Step 5C.1 Prior OD**：新增 `build_prior_od_5c1.py`（AM-v2 阻抗 + 5B 约束框架 → λ=0.05–0.15 共 5 套 `T^5C.1`）与 `compare_prior_od.py`（5B vs 5C.1 对比 + 守恒校验）；ΣT=**1,935,235**，守恒 ≤9.7e-9，Region×PA 残差 **2.25%–5.76%**；**λ 未冻结**，进 MATSim |
| 2026-09-11 | 新增 Step 5C.1：Step 4 `network_links.csv` 增加 `name`/`lanes`；新增 `enhance_ampeak_network.py`（三级速度传播）；AM 覆盖 18.1%→**38.35%** 长度；`C^AM,v2` 中位 21.361 min |
| 2026-09-11 | Step 5C：修复 SpeedBand=8 哨兵、几何源、目录扫描、性能；AM-v1 覆盖 18.1% 长度 |
| 2026-09-11 | Step 5B：无路网 A 清理 + c_ii 修正 + Table 118；Census 约束基线冻结 |
| 2026-09-11 | Step 5A：双约束 Gravity + IPF，5 组 λ 敏感性 |
| 2026-09-11 | Step 4：有向路网 + 332×332 `C^FF`（giant SCC 吸附） |
