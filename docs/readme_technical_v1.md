# Singapore OD → MATSim 流水线 · `scripts/od` README

> 新加坡 **LTA / Census / ACRA / OSM** 开放数据驱动的 **OD 矩阵 → MATSim** 分步构建流水线。
> 空间体系：**332 Subzone → 55 Planning Area → 5 Region**，统一坐标 **EPSG:3414 (SVY21)**。
> 数据冻结目录：`Singapore_OD_MATSim_FinalData/`；动态数据：`Dynamic_2026_03_16/`。

---

## 导读：5 分钟读懂本项目（更新至 2026-09-30）

> 给"刚接触项目的人"看的速读版。下面 §0～§8 是完整技术参考。

### 一句话总结

把新加坡全岛人口、住房、企业、车辆出行数据接进来，喂给交通仿真软件（MATSim），在电脑里"重演"早高峰车流，再用真实摄像头数据对账——校准出一个能代表真实交通的仿真模型 `Singapore_OD_MATSim_Final_v1.0`。

### 用了哪些数据？（大白话版）

| 数据来源 | 是什么 | 用来做什么 |
|---|---|---|
| 建屋发展局 2025 住房与人口 | 全岛组屋户数与人口 | 每户有几口人、几辆车（出行起点） |
| 2020 年全国普查出行调查 | 新加坡人真实出行记录 | 验证仿真出来的出行结构是否合理 |
| 企业注册地址 | 全岛公司注册地址 | 哪里是工作地（出行终点） |
| OpenStreetMap / 政府规划路网 | 全岛道路几何与车道数 | 路在哪里、几车道、限速多少 |
| 政府规划 2019 道路等级 | 道路分级（motorway / arterial / slip） | 哪些是高速、哪些是主干路、哪些是匝道 |
| 陆路交通局 17 类实时接口 | 早高峰实测车流量 | 校准的"标尺"——仿真要追这个目标 |
| 陆路交通局历史车速分布 | 早高峰典型车速 | 速度参照（决定仿真是否"该堵"） |

### 方法：4 阶段 14 步

**第一阶段：算出"有多少出行需求"**（用真实人口数据）

1. 数据接入与对齐（八类数据源）
2. 把全岛划成 332 个小区（5 个大区 → 55 个规划区 → 332 个子区）
3. 每个小区早高峰出发多少人（按人口 + 户数推算）
4. 每个小区早高峰去多少人（按就业推算）
5. 用"双约束重力模型"算小区到小区的出行量
6. 算每条出行走高速 vs 走普通路要多久

**第二阶段：搭建仿真路网 + 生成 23 万"虚拟人"**

7. 把真实路网转成仿真格式（清理断头路、补齐连通性）
8. 按真实人口/出行比例，生成 236,044 辆虚拟车
9. 把每个虚拟人的出发地/目的地接到最近的路网上（"端点吸附"）

**第三阶段：让虚拟车跑早高峰 + 对账**

10. 第一次仿真（让 23 万虚拟车按各自计划跑 20 轮迭代）
11. 把仿真结果按 576 个真实摄像头断面映射、对齐（"三方回测"）
12. 比对仿真 vs 实测：哪些断面有差距？哪些已经吻合？

**第四阶段：排查差距根因（v1.0 已冻结）**

13. 逐轮排查：拥堵反馈系数？道路容量？路径选择？路网表达？匝道建模？
14. 调整参数 + 重跑 + 验证 → 直到"全局总流量"和"实测"完全对齐

### 关键里程碑（按时间顺序）

| 时间 | 进展 |
|---|---|
| 14 步全过 | 第一版"端到端"流水线跑通 |
| 7.3.6B | 最终路段映射表通过三方回测：仿真/实测 ≈ 0.96 |
| 7.4.2 Phase 1 | 联合校准三组实验（容量因子 0.5/0.75/1.0）跑完 |
| **7.6H** | **正式冻结 `Singapore_OD_MATSim_Final_v1.0`**（仿真/实测 = 0.999） |
| 7.7A | 外部数据审计：LTA 无分车型交通量 → 决定不追求消除空间残差 |
| **7.8** | **最终模型正式定版**（含 6 件正式产品与版本号） |
| 7.9G-2 | 四面口径统一（时间 / 数量 / 距离 / 体积） |
| **7.9I** | 观测域尺度 + 局部可达性诊断（**已冻结收口**） |

### 现在做到哪里了？

**模型身份（v1.0 已冻结，2026-09-16 定版）**：

- **全局量级**：仿真总流量 / 实测总流量 = **0.9993**（仿真与实测总流量一致到小数点后 3 位）
- **空间分布**：东部仿真流量比实测少约 32%、东北部多约 34%（结构性问题，不在 v1.0 修）
- **仿真规模**：236,044 辆虚拟车 × 早高峰 20 轮迭代
- **校准基准**：576 个真实摄像头断面（其中 574 条用于正式评价）

**当前阶段（7.9I 已收口）**：

- 不再调整交通动力学参数
- 已确证审计中心：评价靶场的"1:K 计数错配"是空间残差主因（不是"车没跑"，是"评价口径"问题）
- 三个未解项：
  - ① 车行道对层建模（评价对象的精细化）
  - ② LTA 分车型交通量（验证"车型构成能否解释空间偏差"）
  - ③ HTS 出发时刻（验证"早高峰时刻分布是否需要调整"）

**下一步**：

- LTA 分车型交通量到位后，先验证"车型构成能否解释空间残差"
- HTS 出发时刻数据到位后，验证"早高峰时刻分布是否需要调整"
- **路线方针**：从归因入手，不从调参入手——等外部数据，而非再调 v1.0

### 这么多参数我看不懂？

完整参数清单在 §2（约 67 个 step），每个 step 都有：

- **做了什么**（输入 / 输出 / 判据）
- **结论是什么**（判决标签，如 `PASS` / `BLOCKED` / `READY`）
- **为什么这样选**（机制解释）

如果只想看"现在哪些参数被冻结、哪些没定"，翻 **§6「冻结 / 待定」**。

如果想看"最近做了什么改动"，翻 **§7「变更记录」**。

如果想看"历史裁决有哪些没推翻"，翻 **§8「历史归档结论」**。

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
Step 7.3.2B Route-structure / Path-choice 诊断（plans 路径序列 × 等级分类）  ✅ PASS：**A"不走高速"被否定（61% 路线用 motorway、41.5% 长度）；0/196,447 OD 多路径**
  ↓
Step 7.3.2C Motorway Flow Spatial Loading（流式 edge 装载计数 + CATA 断面空间对应）  ✅ PASS：**装载极分散（Top100 仅 9.57%）；CATA≈SLIP 装载指数（0.85）但 sim/obs 相反 → 指向 C 类（观测/表达）**
  ↓
Step 7.3.3 LTA 断面语义 ↔ MATSim Link 表达审计（零仿真）  ← 本轮 PASS：**CATA↔motorway 干净（99.2%）/ SLIP_ROAD 被"主线化"（dominant 主线 55.8%）；对向车道混入（72.1% 断面含反向边、仅 8.5% 可串单链）→ C 类（观测-表达）直接证实**
  ↓
Step 7.3.4 LTA 断面语义对齐重构 + Sim/Obs 收敛判别（零仿真）  ✅ PASS：**边/断面 10.30→4.70、CATA 纯度 97.64%；★仅语义过滤即把 SLIP sim/obs 1.88→0.81、CATA/SLIP 0.41→0.97；strict 下 0.363→0.914（收敛成立）；但 46.6% SLIP 断面在基座候选中无 motorway_link（覆盖缺口）**
  ↓
Step 7.3.5 SLIP_ROAD 候选几何补全（LTA TrafficSpeedBands_Links 独立几何，零仿真）  ← 本轮 PASS：**判定 A（大量补回）——核心 251 SLIP 断面中旧缺口 113 个补回 112 个（99.1%）；93.5% 断面与同向 motorway_link 距离 ≤5 m；50 m 半径即 98.2%（半径非瓶颈）；仅 1 个断面（48170）真实缺口 → 根因是旧 crosswalk 的"路名锚"排除了匝道**
  ↓
Step 7.3.6A Final Calibration Crosswalk 构建（合并 6.3.2 + 7.3.4 + 7.3.5，零仿真）  ← 本轮 PASS：**CATA→motorway / SLIP_ROAD→motorway_link 硬规则；覆盖 CATA 326/339（96.2%）、SLIP 250/251（99.6%）；纯度 100%、对向残差 1.10%；Tier 分层 + UNMATCHED 不强行匹配 + N 超限 REVIEW**
  ↓
Step 7.3.6B Final Crosswalk 三方回测（final vs 7.3.4-strict vs 7.1，用 6.3.3B linkstats 复算 Sim/Obs，零仿真）  ← 本轮 PASS：**★核心链条 0.3633 → 0.9135 → 1.0984（CATA/SLIP Σsim/Σobs，08-09）**；final 下 CATA 0.7797 / SLIP 0.7098；**当仅保留 fallback 的 7.3.4-full 作参照时仍为 0.4100（SLIP 1.8796）→ 覆盖广 ≠ 语义对齐** → **断面语义错配（C 类）正式从主要模型误差中剔除**；残差转为"整体量级不足（CATA 0.78 / SLIP 0.71 均 <1）"
  ↓
Step 7.4.1 Joint Calibration Experiment Matrix（设计 9 组，不跑 MATSim）  ← 本轮 PASS：**θ={λ, f_cap, route-choice}；λ∈{0.050,0.075,0.100}、f_cap∈{0.50,0.75,1.00}（storage=flow）、route-choice 固定 20 it；★randomSeed 校正为项目实测冻结值 4711（草案 20260912 系误写）；Phase1 只跑 E01–E03（λ=0.050）**
  ↓
Step 7.4.2 Phase 1（E01–E03：λ=0.050 × f_cap 0.50/0.75/1.00 × 20 it）  ← 本轮 PASS：**★capacity 是强总量杠杆（Sim/Obs(all) 0.399→0.570→0.810），且随 capacity 单调影响 CATA/SLIP（极差 0.2371 = 基线偏离 |1.0984−1| 的 2.41×）**；但结构变化是**两类道路拥堵弹性差**（CATA ×2.11 vs SLIP ×1.64），**非语义级重分配**；**f=1.00 全面占优（GEH<5 0.1163、Sim/Obs 0.8105 最接近 1）→ 不存在更优 f<1.00**；**迭代效应（同 f=1.00，1it→20it）：Sim/Obs 0.7690→0.8105、CATA/SLIP 1.0984→1.0698**
  ↓
Step 7.4.2 Phase 2（λ 灵敏度：capacity 固定 1.00 × 20 it，只扫 λ）  ← 本轮完成：E06/E09 跑完（各 20 it，`exit=0`）；**规范 ID E03(λ0.050,复用 Phase1) / E06(λ0.075) / E09(λ0.100)**；⚠️**用户口述 E04/E05/E06/E07 与 7.4.1 矩阵编号不一致 → 采用规范 ID**（映射见 §2.21）；**λ=0.025 全链 population 缺失 → 暂缓（E10=DEFERRED）**；**★结论：λ 既非结构杠杆（CATA/SLIP 极差 0.0146 ≪ capacity 0.2371）也非量级杠杆（Sim/Obs 非单调，最优仍仅 0.81）；λ 对截面拟合有真实但有限正效应（E06 λ=0.075 三窗口一致最优）→ 存在「量级最优 0.050 vs 拟合最优 0.075」权衡**
  ↓
Step 7.4.3 OD 总量 / 机动车出行量标定（**demand scale**：λ 固定 0.075、f_cap 固定 1.00、20 it，**只缩放 agent 车辆数**）  ← 本轮启动：**设计 + 运行器 + 评价器 PASS**；D01 f=1.00（复用 E06）/ D02 f=1.10 / D03 f=1.20 / D04 f=1.25；**★双系列并列：D 系列（真实加车、跑仿真）vs A 系列（算术参照、零仿真，把 D01 的 sim 直接 ×f）→ A−D = 拥堵弹性阻尼**；**★需求承载机制核查（本步核心）：MATSim 只消费 agents（车辆数）= 唯一物理需求杠杆；`expansionFactor`（Σ=459,794 = 真实 car OD 总量）MATSim **不消费**、`odTrips`（Σ 随 λ 变 4.215M→4.327M→4.485M）只是每 cell agent 数分布影子 → 二者均**不作**缩放对象**；**★结果（2026-09-15）PASS：08-09 Sim/Obs(all) 0.7070→0.7095→0.8601（峰@f1.20）→0.7599 非单调，最强仍 <1（差 0.1399）→ 加车补不满量级缺口；CATA/SLIP 极差 0.1738（=λ 的 12×）且穿越 1 → 结构不中性、SLIP 弹性 ×1.249 > CATA ×1.045；A−D 阻尼 +0.0682/−0.0116/+0.1239**
  ↓
Step 7.5A 需求权重链条核查 + 固定样本量采样架构（**100k 标定 / 200k 终验**；λ 仍固定 0.075、capacity 冻结 1.00）  ← **本轮启动**：**★审计（零仿真，决定性）**：`expansionFactor` / `odTrips` 在 **MATSim 自身 class 零命中**（`matsim-2026.0.jar` 字节级常量池扫描；阳性对照 `flowCapacityFactor`/`storageCapacityFactor`/`countsScaleFactor` 命中 `QSimConfigGroup`）→ **MATSim 不消费二者，有效需求权重 = 进入 QSim 的 person/vehicle 数** → 扩样必须在评价层施加 `SCALE = ΣT / N_sample`（200k→2.29897、100k→4.59794）；**★硬约束**：λ=0.075 正 OD cell = **71,136** → `N_sample ≥ 71,136`（**50k 不可行**）；**★采样—扩样解耦**：S100（100k, f_cap=1.00 字面设计）vs S200（=D01/E06 复用, 200k, f_cap=1.00）等需求对照；**并列 S100c（f_cap=0.50 = N_sample/N_ref，采样一致对照）** 以分离「采样效应」与「供给/需求比效应」  ← **★结果（2026-09-15）：S100 跑完（100k × 20 it，143.80 min，`exit=0`），判决 `NOT_SUBSTITUTABLE`**：**raw 线性比中位 0.6174（≠0.5 → 减样本后单位 agent 流量 +23.5%，车密度减半、拥堵减轻的直接证据）**、**scaled 比值中位 1.2308（≈2×0.6174 自洽）**、**±10% 内 17.9% / ±20% 内 32.6%**（但 **Pearson 0.9006 / Spearman 0.9567** 截面形态强一致、仅整体偏高）；三窗口同向偏高（0.7595/0.9784/0.8699）→ **f_cap=1.00 对照不干净**（混杂「采样效应」与「拥堵物理改变」），**须跑 S100c（f_cap=0.50）干净对照方能判定 100k 是否可替代**（**已授权**）；S200 = E06 复用；**★S100c 预注册判据 C1–C7 已「跑前固定」落盘**（`preregistered_criteria.json` + `STEP7_5A_S100C_PREREGISTRATION.md`；`f_cap=0.50` 仅作**采样一致性校正**，非供给标定参数）  ← **★S100c 结果（2026-09-15）：跑完（100k × 20 it，164.59 min，`exit=0`），预注册硬门槛 1/6（仅 C6 PASS）→ `NOT_SUBSTITUTABLE`**：**raw 线性比 0.6174→0.5799**（采样非线性 +23.5%→**+16.0%，f_cap 校正部分有效**）、**CATA/SLIP 漂移 0.0480→0.0233（C6 PASS → 结构畸变主因是「车密度/容量」，同比缩放可基本修复）**、但 **scaled 比值中位仍 1.1537、±20% 仅 0.2648、Pearson 0.8557（空间相关性反降）** → **残余 16% 非线性不可由标量 f_cap 消除（样本量本身改变网络动力学）** → **100k 不可替代 200k；「固定样本+可变权重」在拥堵型网络不成立；100k 方案不冻结、λ 仍不冻结**
  ↓
Step 7.5B Sampling Rule Sensitivity（**采样规则敏感性**；唯一变量 = 采样规则，其余全冻结）  ← **本轮完成**：**★动机**：S100c 同时给出两条信号 —— (a) `f_cap=0.50` 把 CATA/SLIP 漂移 0.0480→**0.0233**（C6 PASS）→「供需密度」机制可被容量同比缩放吸收；(b) 但 raw ratio 仍 **0.5799**（≠0.50）、Pearson 由 0.9006 **降到 0.8557** → 仍存在**第二层「样本空间分布偏差」**；**★假设**：6.2B `allocate_cells` 的「**每正 OD cell ≥1 agent**」保底规则让小 cell 获得**相对过多**代表个体，且畸变随 N 减小急剧放大（保底 agent 占比 **200k 35.6% → 100k 71.1%**）；**★单变量设计**：`S100c`（现有保底规则，复用）vs `S100r`（**纯 trips-proportional，无保底**）—— `N=100k` / `λ=0.075` / `f_cap=storage=0.50`（=N/N_ref 采样一致校正）/ 20 it / `seed=4711` / `routingRandomness=0` / 同 network·OD·departure·crosswalk·靶场 **全部冻结**；**★已验证 S100c 与 S100r 的 config 除 outputDirectory/runId/inputPlansFile 外逐字节完全相同**（单变量成立）；**★人口侧诊断（零仿真）**：100k 纯比例 → sampled cells **38,350** / zero-sampled **32,786（46.09%）** / OD coverage **0.5391** / 丢弃 trips **21,528（4.68%）** / ΣEF **438,266.0**（`f_realized` **0.95318**，被采样 cell 逐 cell 守恒误差 5.7e-14）；**★S100r 全量跑通（100k × 20 it，171.20 min，exit=0，20 it 全落盘）**；**★判据「跑前固定」落盘**（D1–D7 绝对 + M1–M4 机制，`preregistered_criteria_7_5b.json`）；**判决规则**：D 全 PASS → `SAMPLING_RULE_WAS_THE_CAUSE`（保留 100k 但改采样算法）/ M ≥3 改善 → `PARTIAL_IMPROVEMENT` / M <3 → `SAMPLE_SIZE_DEPENDENT`（**此时 knee 扫描才有意义**）；**★判决：`PARTIAL_IMPROVEMENT`（D 0/6、M 3/4）—— 纯比例把 raw 比由 0.5799 拉到 0.4325（0.5 被夹在中间）、±20% 覆盖 0.2648→0.4305（M2 PASS）、Pearson 0.8557→0.9162（M3 PASS），但 CATA÷SLIP 漂移 0.0233→0.1037（M4 FAIL，恶化 4.4×）、Sim/Obs 0.8389→0.5984（欠冲）⇒ 采样规则与样本量共同作用，任一单独都不够**
  ↓
Step 7.4.3-Diag demand scale 非单调回落机制诊断（零仿真只读）  ← **本轮完成：判决 `TIME_WINDOW_ARTIFACT_CONFIRMED`**：08-09 单小时 f1.25/f1.20 **0.9584（下降）** → 非单调；**窗口加宽 07-11 = 1.0404 ≈ 纯比例 1.0417、0-24 = 1.2547 ≈ 1.2500（达成率 100.4%）** → **需求被完整投递、只是在时间上被摊开**；平均行程时长 33.24→**38.99 min**（×1.173）、8-9 加权拥堵倍率 2.314→**2.796**（×1.208）、09:00 前到达占比 73.26%→**68.35%**、09-10/10-11 到达 +12%/+68%；**出发占比跨档极差仅 0.035 pp** → 机制全在**行进入端**；**f=1.20 的 0.8601 不可读作「最优需求规模」**
  ↓
Step 7.4.3-R 宽时间窗重新评价（零仿真只读）  ← **完成：★阻断发现 = 可观测窗上限 07-09**（LTA `HourOfDate` **只有 7/8**，`TrafficSpeedBands_v4` / `EstimatedTravelTimes` 均为**单时刻快照**）；7 窗口中 **6 个仍非单调**；`ALL` 缺口 0.0799 → **0.0006（00-24 完全收敛）**，`MATCHED` 缺口 0.1507 → **0.9333（只解释 55.7%）**，**残留 6.7% 与窗口无关** ⇒ 残差指向 **ReRoute 路径替代 / 分配重分布**
  ↓
Step 7.4.3′ 回到 **200k 正式标定基准**（🔒 `N_sample=200,000` / `f_cap=1.00` / capacity = 1.00；100k **暂不替代**；`λ` / demand scale / sampling rule **均不冻结**）
  ↓
**【路线重构（用户裁定）】不继续「一个参数一个参数地扫」→ 先把剩余误差归因，再决定哪些值得消耗算力**
  ↓
Step 7.6A Official Car-Demand Accounting（零仿真只读）  ← **完成：判决 `CALIBER_GAP_DOMINATES`**：`ΣEF = 459,794` ≈ Census 2020 `Car Only` 名义锚（459,796）；物理 / 非物理 **1,935,235 / 273,124**（守恒 Δ=1）；**观测无车型字段 ⇒ 车型构成不可分解** ⇒ **`f ∈ [1.0504, 1.4641]`（总量证据只能给区间）**；**需求口径保持 V1（Car Only）—— 用户裁定**
  ↓
Step 7.6B Assignment / Route Stability Audit（零仿真只读）  ← **本轮完成：判决 `UNCONVERGED_PERIOD2_LIMIT_CYCLE__CROSS_F_SIGNAL_BELOW_PHASE_NOISE`**：D01–D04 全部呈 **周期-2 极限环**（MATCHED 振幅 1.59% / 3.77% / **20.75%** / 16.22%，ALL 仅 0.39–1.40% ⇒ **放大 14.8×**）；**it.19 是极限环的一个相位样本**（f=1.20 偏置 **+12.47%**）；**同相位检验：偶相位单调下降 vs 奇相位峰在 D03 ⇒ 响应符号由采样相位决定 ⇒ 该实验无法识别 demand scale**
  ↓
Step 7.6B′ 【**本轮已裁定 → 拆为 7.6D / 7.6E**】(a) 评价口径 = **双口径并报**（Primary `Q̄_10:19` 周期均值 / Reference `Q_19` 单点，不丢弃可追溯）—— **已采纳**；(b) **route-choice 机制修复** → 独立为 **7.6D**（最小修复）+ **7.6E**（新配置稳定性验证）
  ↓
Step 7.6D Route-choice Stabilization（**本步**；独立工作区 `matsim_routechoice_7_6d/`）  ← **完成配置验证 19/19 PASS + 冒烟预检 PASS + 预注册判据跑前冻结**：最小修复 = `fractionOfIterationsToDisableInnovation` `Infinity→0.8` + 策略集 `[ReRoute 1.00]→[ReRoute 0.15, ChangeExpBeta 0.85]` + `learningRate` `1.0→0.5`；**★修复前 `A_10:19(MATCHED)` = 8.48% / 11.10% / 23.25% / 20.32%（f=1.00/1.10/1.20/1.25，无一 STABLE）⇒ 不是 demand 选得不好，而是机制问题**；**200k 正式 run 已由 7.6E 执行完成并判 `STABILITY_PASS`（6/6）**
  ↓
Step 7.6E route-choice 正式冻结门（200k × 20 it）  ← **✅ 完成，判 `STABILITY_PASS`（G1–G6 6/6）**：MATCHED `A_10:19` **8.48% → 1.00%**、`parity_gap_rel` **1.59% → 0.13%**、`Q19/Q̄` **+0.19%**、`sign_consistency` **1.000**、`never_arrived`=`max_stuck`=**0**、跨规模比 **1.40**；逐迭代形态由**周期-2 极限环 → 单调指数收敛**，且 100k/200k 归一路径几乎重合 ⇒ **机制签名**；**route-choice 层正式冻结，成为后续所有实验的分配底座**
Step 7.6F-0 新稳定底座 demand=1.00 基准重算（零仿真）  ← **✅ 完成，判 `PASS` 20/20**：新基准点 **Sim/Obs(08-09) Primary = 0.8590**（Reference 0.8603 / AM 0.7665）；**机制分解**（固定 demand=1.00，仅 route-choice 变）200k **0.7506 → 0.8590（+14.43%）**、100k **0.8169 → 0.9639（+18.00%）** ⇒ 机制签名；而 `Σ(HRS0-24avg|MATCHED)` 仅 **+3.11%** ⇒ **禁止 ×(1+δ) 平移旧曲线**；**旧 D01–D04 谱判 `LEGACY_CURVE_UNINFORMATIVE`**（信噪比 0.372 < 1）⇒ **7.6F-1（在新底座补跑 D02–D04 重建响应曲线）待用户裁定**
Step 7.6F-1 粗档 demand-response（f = 1.05/1.15/1.25，**物理加车**）    ← **✅ 完成，判 `RESPONSE_STABLE_CROSSES`（评价 21/21 PASS；三档全 PASS：F05 69.73 / F15 80.40 / F25 75.74 min，累计 3.76 h）**：**Sim/Obs `FROZEN`（MATCHED，08-09）单调上升 0.8589732 → 0.8994456 → 0.9767361 → 1.0535647 ⇒ 曲线在网格内跨越 1.0**；**★跨越点（Sim/Obs = 1 线性插值）：`FROZEN` f\* = 1.1803 / `BEST_DIRECTION` 1.1320 / `POSITIVE_ONLY` 1.0748** ⇒ **与 7.6C-2 静态预测区间 [1.06945, 1.16418] 自洽**（主靶场仅高出上界 1.4%）。**★稳定性承继**：`A_10:19`(MATCHED) **1.0009% → 0.7833%**（加车使收敛更好）⇒ G1 PASS。**★拥堵阻尼比 ρ(f)** = 1.000 / 0.997255 / 0.988780 / **0.981232** ⇒ 200k→250k **几乎无阻尼**（仅 1.88%）。**★★空间残差不随 f 变化**（EAST −32.20%→−31.38%、`radial_in` −28.80%→−30.96%，极差仅 1.05/2.16 pp）⇒ **demand 缩放无法压平空间结构缺口 —— 全局量级与空间结构是正交问题**，正面确认 7.6C-1；**★对账**：7.6C-2 3/3 + 7.6D 4/4 全中（口径未漂移）。**未选 demand scale / 未评价 λ**
  ↓
  ↓
Step 7.6C OD 空间结构 / 距离带 / 空间集中诊断（零仿真只读）  ← **✅ 完成，判 `OD_STRUCTURE_PARTIAL`（28 校验 23 过）**：S5 Table118（物理格中位残差 **0.0026**）/ S6 无异常吸收区（0 个 |z|>5）/ S7 detour **1.068–1.111**（plan 与 linkstats 独立互证）全过 ⇒ **OD 形状大体可信**；但 **S4 不过**（Region 最大相对偏差 **0.348**；**EAST 0.582 vs NORTH-EAST 1.158**；**radial_in 0.612 vs radial_out 0.976**；**54 断面 sim=0 却占 8.14% 观测**，剔除后全局 0.8590→**0.9351** 但区域偏差仅降到 0.333）⇒ **缺口是空间结构性的**，绝对 demand 规模仍不可干净识别 ⇒ **7.6F-1 已由用户裁定进入（见下方 7.6F-1 节点；性质降级为「粗档响应」）**
  ↓
Step 7.6C-1 异常归因追踪（零仿真只读）  ← **✅ 完成，判 `MIXED_COVERAGE_AND_RESIDUAL_STRUCTURE`（5/5 判据、6/6 校验；78.3 s；plans 缓存后 14.4 s）**：专查 7.6C 暴露的两个高集中异常 —— **(a) R5/radial_in 的 13/13 零流断面全部位于 WEST（TUAS/PIONEER）**，其 **47 条匹配边在 `HRS7-8avg`/`HRS8-9avg`/`HRS0-24avg` 三窗口 × 正反向全部为 0**，**43/47 是有向拓扑孤儿、0/47 连通**（正常有流链路参照 0.987/0.991）⇒ 不是时间窗伪影、不是方向伪影，而是**有向可达性「孤儿边」**；但 400 m 邻域内有 **1,559–39,762 veh/h** 仿真流量（常与断面同名）⇒ 走廊是活的。**(b) 54 个零流断面（8.14% 观测）100% 在 100 m 内、96.3% 在 60 m 内有有流平行链**，机制四类：`CROSSWALK_TWIN_ORPHAN` 31 / `DIRECTION_MISMATCH` 13 / `WINDOW_ARTIFACT` 8 / `GENUINE_UNROUTED` **仅 2**（0.38% 观测）⇒ **硬零流可正式判为测量伪影**，`0.8590 → 0.9351` 的跳升由此解释。**但 graded 缺口对修正稳健**（EAST 0.582→0.622、`radial_in` 0.612→0.634，仍远低于 NORTH-EAST 1.158 / `radial_out` 1.022）⇒ **真实结构信号**。**Layer 2 三假设全部否证**：吸引量错（Table118 中位 0.0026/P95 0.0095）、OD 方向错（EC 不对称 **0.2112 ∈ [0.1044, 0.3089]** 同类区间）、路径改道（**EC 实走路径 64.25% 为 `radial_in`、99.2 链次/出行落在 EAST 入城走廊**；CE 以 `radial_out` 58.85% 为主）⇒ EAST 低估来自**细粒度链路归属 + 断面中位统计口径**，不是 OD/吸引/改道
  ↓
Step 7.6C-2 Calibration Target Integrity Gate（零仿真只读）  ← **✅ 完成，判 `TARGET_MARGINAL_COARSE_ONLY`（判据 7/10；16.7 s）**：问「当前 7.3.6A frozen crosswalk 是否仍足以支持 demand scale 的**绝对**识别」。**★核心量 `Delta_target` = Q_POSITIVE_ONLY − Q_FROZEN = 0.9350621 − 0.8589732 = **7.609 pp**；f\* 识别区间 **[1.06945, 1.16418]**，宽度 `Delta_f_target` = **0.09473**。**★信噪比：粗档 1.10→1.20 SNR = 1.056 ✓；细档 1.20→1.25 SNR = 0.528 < 1 ✗**（需 ε ≥ 1.895 才可识别，而 8-9 过饱和份额恒 0% ⇒ ε ≈ 1）⇒ **靶场不确定性与粗档 demand 增量同量级**。**★网格诊断：f = 1.10 落在 f\* 区间内部（口径分歧），1.20/1.25 均在区间之上且三口径一致** ⇒ 3 次跑只买 2 个区制；建议网格 **`1.00/1.10/1.20`** 或 **`1.05/1.15/1.25`**（间距 0.10 ≥ `Delta_f_target`）。**★结构可分性**：Region 跨度 0.5576 / `Delta_target` 0.0761 = **7.33×** ⇒ 7.6C/7.6C-1 结构结论**不受污染**；**★断面集口径澄清**：7.3.6A = 576 断面/574 primary/3,015 primary 匹配链（全家 3,037），7.6C 地理只有 574 ⇒ 7.6C-1 repair bounds 按 574 算（差 4.06e-4）。**不得把 `0.9351` 升格为新靶场；不得用 `0.8590` 或 `1.1642` 反推 demand scale。**
  ↓
Step 7.6F-1 稳定底座上的**粗档** demand-response 曲线（**入场准备 → 已跑完 → 已出判决；见本文件 §2.36/§2.37/§2.38**）  ← **入场准备判 `PREPARED`（67/67 校验 PASS）；三档仿真与评价已完成 → 最终判决 `RESPONSE_STABLE_CROSSES`（21/21）**。原入场准备要点：用户裁定修正网格 **`f = 1.05/1.15/1.25`**（落在 7.6C-2 `f*` 区间 `[1.069,1.164]` 的**下方/内部附近/上方**）
  ↓
Step 7.6F λ 辨识 / 灵敏度（分配收敛后才进入）→ 最终 demand calibration → **Final 200k validation**
  ↓
（原）Step 7.4.4 λ 辨识 / Phase 3 λ 精细搜索 / route-choice 参数扫描 —— **已由 7.6 系列取代：λ 只有在分配收敛问题解决后才进入**
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
| 7.3.2B | `diagnose_route_structure_7_3_2b.py` | **路径结构诊断**：解析 6.3.3B it.0 `plans.xml.gz`（route type=links 单行正则）+ `trips.csv.gz` 对接 200k agents，构造 `e{from}_{to}` 接 `network_links_source_copy.csv` 等级/长度（**单次遍历 + 字典视图**），输出逐 agent 诊断 + 等级长度占比 + 等级间转移矩阵 + OD 路径一致性 + A/B/C 三分判定；**只诊断不改模型** | 6.3.3B it.0 plans/trips、`network_links_source_copy.csv` | `reports/od_route_diagnosis_7_3_2b/`（5 产物 + STEP7_3_2B_REPORT.md） | ✅ **PASS** |
| 7.3.2C-1 | `diagnose_motorway_loading_7_3_2c.py` | **motorway 空间装载（流式）**：**逐行二进制正则**解析 `plans.xml.gz` 的 route links（**不构造 XML 树、不建 20 万 route 对象**），只累计 motorway/motorway_link 的 edge 使用计数 + 等级长度占比 + 等级转移矩阵 + Top10/50/100 集中度；**只诊断不改模型** | 6.3.3B it.0 `plans.xml.gz`、`network_links_source_copy.csv` | `reports/od_route_diagnosis_7_3_2c/`（summary/edge_route_loading/top_*_edges/route_class_spatial_loading/route_transition_matrix + STEP7_3_2C_REPORT.md） | ✅ **PASS（本轮）** |
| 7.3.2C-2 | `analyze_cata_spatial_correspondence_7_3_2c.py` | **CATA 断面空间对应**：把 6.3.2 tight crosswalk（断面→MATSim 边）与 edge 装载计数连接，逐 CATA 断面算其匹配 motorway 边的**平均装载指数**（÷ 全网 motorway 均值）→ 与 6.3.2 `sim/obs` 相关，并按 RoadCat 汇总；回答「CATA 观测点落在高/低装载走廊」 | 6.3.2 crosswalk + `section_flow_comparison_lambda_0p050.csv`、7.3.2C-1 `edge_route_loading.csv` | `reports/od_route_diagnosis_7_3_2c/`（cata_section_spatial_correspondence/cata_loading_index_by_roadcat/cata_spatial_correspondence_summary.json） | ✅ **PASS（本轮）** |
| 7.3.3 | `audit_section_semantics_7_3_3.py` | **LTA 断面语义 ↔ MATSim link 表达专项审计（零仿真）**：① TrafficFlow 长表→断面级；② 6.3.2 tight crosswalk（断面→MATSim 边）+ network 等级/名称 + nodes 坐标；③ 检查 CATA↔motorway、SLIP_ROAD↔motorway_link 语义对应、一断面→多边 & 一边→多断面重叠、RoadName/等级/方向一致率、上下游道路等级组合、**对向车道混入**（断面内自含反向边 + 精确互反配对 + 可串链率）；**只审计不改任何冻结模型** | 6.3.2 tight crosswalk、`TrafficFlow_Data.json`、`network_links_source_copy.csv`、`network_nodes_source_copy.csv` | `reports/od_network_semantic_audit_7_3_3/`（section_semantic_audit/cata_semantic_audit/sliproad_semantic_audit/section_upstream_downstream/section_class_transition/section_duplicate_overlap/roadcat_highway_correspondence + semantic_audit_summary.json + STEP7_3_3_REPORT.md） | ✅ **PASS（本轮）** |
| 7.3.4 | `audit_section_rebuild_7_3_4.py` | **语义对齐后的断面重构（零仿真）**：以 6.3.2 tight crosswalk 为起点**不重新自由匹配**，只重新筛选——`同向(|Δθ|≤30°)` + `RoadCat 语义允许集（CATA→{motorway}、SLIP_ROAD→{motorway_link}）` + 分级 fallback（strict→direction_name→name_fallback→original）；逐断面输出边集/tier/纯度。**不改 OD/λ/population/departure/network/capacity/route choice** | 6.3.2 tight crosswalk、`TrafficFlow_Data.json`、`network_links_source_copy.csv`、`network_nodes_source_copy.csv`、6.3.3B it.0 linkstats | `reports/od_section_semantic_rebuild_7_3_4/`（rebuilt_crosswalk/section_semantic_rebuild_summary/cata_rebuild/sliproad_rebuild/rebuilt_section_flow + step7_3_4_summary.json） | ✅ **PASS（本轮）** |
| 7.3.4-C | `analyze_section_rebuild_flow_7_3_4.py` | **重构后 Sim/Obs 收敛判别（零仿真，伴随分析）**：按 7.1 冻结口径 `sim=median(匹配边 HRSx-yavg)×2.29897`、`obs_am=obs_7_8+obs_8_9`，对 **old vs rebuilt(full) vs rebuilt(strict-only)** 用**同一条代码路径**算 Σsim/Σobs 与 mean-of-ratio；含**过滤归因**（full/dir_only/sem_only/strict）与**strict 覆盖偏差检查**（保留断面数 + obs 权重）；产出权威 `STEP7_3_4_REPORT.md` | `rebuilt_crosswalk.csv`、7.1 `calibration_target_lambda_0p050.csv`（old 基线 + obs）、6.3.3B it.0 linkstats | `reports/od_section_semantic_rebuild_7_3_4/`（rebuilt_vs_old_by_roadcat/filter_attribution_by_roadcat/strict_filter_coverage_by_roadcat/rebuilt_direction_audit/rebuilt_section_flow_detail + section_rebuild_convergence_summary.json + STEP7_3_4_REPORT.md） | ✅ **PASS（本轮）** |

| 7.3.5 | `build_slip_candidate_completion_7_3_5.py` | **SLIP_ROAD 候选几何补全（零仿真）**：用独立 LTA 几何 `TrafficSpeedBands_Links.shp`（RoadCat=6 slip）与 MATSim `motorway_link`（真实 LineString，非中点）做 **line-to-line** 空间搜索（buffer + 真实距离）；对每个 slip 断面给出 **同向（±30°）/ 同名 / strict** 分级候选，并区分 **CORE（251 检测器断面）** 与 **FULL（5,207 全网 slip）** 两口径；含 **半径敏感性（50/80/120/200 m）** 与 **最近同向匝道距离分布**；旧覆盖按"**旧 crosswalk ∩ 网络 = motorway_link**"定义（=7.3.4 的真实缺口）。**不改 OD/λ/population/departure/network/capacity/route choice** | `TrafficSpeedBands_Links.shp`、`network_links_source_copy.csv`、`network_nodes_source_copy.csv`、6.3.2 tight crosswalk | `reports/od_slip_candidate_completion_7_3_5/`（slip_candidates_all/slip_candidates_strict/slip_section_summary/slip_section_coverage/old_vs_new_slip_coverage/slip_core_missing_recovery/slip_core_radius_sensitivity/slip_core_nearest_samedir_distance + step7_3_5_summary.json + STEP7_3_5_REPORT.md） | ✅ **PASS** |
| 7.3.6A | `build_final_calibration_crosswalk_7_3_6a.py` | **Final Calibration Crosswalk 构建（零仿真）**：把 **6.3.2（几何基座 + 逐边 distance_m）+ 7.3.4（方向 + 语义）+ 7.3.5（独立几何补全）** 合成为唯一评价映射。**硬规则**：`CATA→motorway`、`SLIP_ROAD→motorway_link`；SLIP **RoadName 不作硬约束**（仅辅助/质量分层）。**Tier 分层**：CATA_T1；SLIP_T1(方向+名)→T2(方向+几何)→T3(几何 fallback，带 flag)；无候选 → **UNMATCHED（不强行匹配）**。**N 上限**：CATA≤10 / SLIP≤8（CLI 可调），超限 → `REVIEW`（保留但标记）。**1:N** 保留完整同向匝道链。**不改 MATSim 网络/任何冻结参数，不覆盖 7.1 靶场** | 6.3.2 tight crosswalk、7.3.4 `rebuilt_crosswalk.csv`、7.3.5 `slip_candidates_all.csv`、`network_links_source_copy.csv`、`TrafficFlow_Data.json` | `reports/od_final_calibration_crosswalk_7_3_6/`（final_calibration_crosswalk/final_section_summary/final_cata_summary/final_slip_summary/crosswalk_edge_overlap/crosswalk_quality_summary + step7_3_6a_summary.json + STEP7_3_6A_REPORT.md） | ✅ **PASS（本轮）** |
| 7.3.6B | `compare_final_crosswalk_7_3_6b.py` | **Final Crosswalk 三方回测（零仿真）**：仅读已有 6.3.3B `it.0` linkstats，按 **7.1 冻结口径**（`sim=median(匹配边 HRSx-yavg)×2.29897`；obs=工作日日内均值→`LinkID×hour` 日中位；`obs_am=obs_7_8+obs_8_9`）复算 **`7.1_old` / `7.3.4_semantic(strict)` / `7.3.6A_final`**（+ 参照 **`7.3.4_full`**）三窗口（07-08/08-09/AM）的 CATA/SLIP Σsim/Σobs 与全指标（Pearson/Spearman/MAE/RMSE/MAPE/**WMAPE**/Bias/GEH<5/GEH<10）。**不重跑 MATSim、不改任何参数、不动 7.1 靶场** | `TrafficFlow_Data.json`、6.3.3B `it.0` linkstats、6.3.2 crosswalk、7.3.4 `rebuilt_crosswalk.csv`、7.3.6A `final_calibration_crosswalk.csv` | `reports/od_final_crosswalk_backtest_7_3_6/`（final_crosswalk_backtest/roadcat_summary/method_comparison/coverage/metric_matrix + step7_3_6b_summary.json + STEP7_3_6B_REPORT.md） | ✅ **PASS（本轮）** |

| 7.4.1 | `prepare_calibration_experiments_7_4_1.py` | **联合校准实验矩阵设计（零仿真，从不启动 MATSim）**：固化 θ={λ, f_cap, route-choice}，产出 9 组核心矩阵（λ×{0.050,0.075,0.100} × f_cap×{0.50,0.75,1.00}，route-choice 固定 20 it）；冻结 Final Crosswalk 7.3.6A / Departure 6.3.3A / OD 6.2B / network_cleaned；**Phase1=E01–E03**、Phase2=E04–E09（按需）；含预注册判据与淘汰规则。**★把 `randomSeed` 校正为项目实测冻结值 4711**（外部草案 20260912 系设计日期误写，已在 JSON/报告中披露） | 无（纯设计） | `reports/od_calibration_7_4_1/`（calibration_experiment_matrix.csv + calibration_parameter_definition.json + STEP7_4_1_EXPERIMENT_DESIGN.md） | ✅ **PASS（本轮）** |
| 7.4.2-R | `run_calibration_phase1_7_4_2.py` | **Phase 1 联合校准运行器**：读 7.4.1 矩阵，逐实验 `make_config_6_3.build_one` 生成同源 config 后最小 patch —— **唯一变量 = `qsim.flowCapacityFactor`（= storageCapacityFactor，MATSim 2026 硬约束）** + `controller.lastIteration=19`（20 it 拥堵反馈）；磁盘控制（`writeEvents/Plans/Trips/SnapshotsInterval=0`，只留每迭代 linkstats）；`verify_patch` 读回断言 seed=4711 / ReRoute / routingRandomness=0；**可断点续跑**（it.19 linkstats 存在即跳过）。**不改 OD/λ（λ 由实验档决定）/population/departure/network/crosswalk/route-choice** | 7.4.1 矩阵、6.3.3A population、`network_cleaned.xml.gz`、`fullConfig_2026_0.xml` | `reports/od_calibration_7_4_2/<EID>_lam*_cap*/`（每实验 20 迭代 linkstats）+ `matsim/step6_3/config_E0*_lam*.xml` + `matsim/step6_3/logs/<EID>_run.log` + `phase1_run_manifest.json` | ✅ **PASS（本轮跑完 E01–E03，~10.6 h）** |
| 7.4.2-E | `evaluate_calibration_7_4_2.py` | **Phase 1 评价（零仿真）**：**import 已冻结的 7.3.6B 模块**保证口径逐字节同源；评价接口 = **7.3.6A Final Crosswalk** + 7.1 冻结观测口径；对每实验 linkstats（默认取最末迭代 it.19，另附 it.0 / 6.3.3B 单迭代基线）复算 07-08/08-09/AM 的 **ALL + CATA + SLIP_ROAD + CATB** 的 Σsim/Σobs 与全指标（Pearson/Spearman/MAE/RMSE/WMAPE/Bias/GEH<5/GEH<10），直接产出 **`f × {Sim/Obs, WMAPE, GEH<5, CATA, SLIP, CATA/SLIP}`** 对比表 | 7.4.2 各实验 linkstats、`TrafficFlow_Data.json`、7.3.6A `final_calibration_crosswalk.csv`、6.3.3B `it.0` linkstats | `reports/od_calibration_7_4_2/`（phase1_backtest.csv + phase1_roadcat_summary.csv + **phase1_capacity_comparison.csv** + step7_4_2_phase1_summary.json + STEP7_4_2_PHASE1_REPORT.md） | ✅ **PASS（上一轮正式结果）**（★`capacity` 强总量杠杆 + 结构极差 0.2371；**f=1.00 全面占优**；修复 §报告生成 1 处 `float` 缺陷） |
| 7.4.2-P2 设计 | `prepare_calibration_phase2_7_4_2.py` | **Phase 2 λ 灵敏度设计（零仿真，从不启动 MATSim）**：capacity 固定 1.00、20 it，只扫 λ；**规范 ID E10(λ0.025)/E03(λ0.050)/E06(λ0.075)/E09(λ0.100)**；⚠️**显式披露用户口述 E04/E05/E06/E07 与 7.4.1 矩阵编号不一致 + 映射**；**探测 population 存在性** → 标 BLOCKED_NO_POPULATION | `reports/matsim_departure_6_3_3a/`（population 存在性探测） | `reports/od_calibration_7_4_2/`（**phase2_lambda_matrix.csv** + phase2_parameter_definition.json + **STEP7_4_2_PHASE2_DESIGN.md**） | ✅ **PASS（本轮）**（runnable=E06/E09；blocked=E10） |
| 7.4.2-P2 评价 | `evaluate_calibration_phase2_7_4_2.py` | **Phase 2 评价（零仿真）**：import 冻结的 7.3.6B + Phase 1 评价函数，口径逐字节同源；λ × RoadCat × 窗口复算 Σsim/Σobs 与全指标，产出 **λ × {Sim/Obs, WMAPE, GEH<5/10, Pearson, CATA, SLIP, CATA/SLIP}** 对比表 + **逐指标趋势（单调/非单调判定）** + **跨窗口一致性** + **三类响应（结构/量级/拟合）** | 7.4.2 各实验 linkstats、7.3.6A crosswalk、6.3.3B 基线 | `reports/od_calibration_7_4_2/`（**phase2_lambda_comparison.csv** + phase2_backtest.csv + phase2_roadcat_summary.csv + step7_4_2_phase2_summary.json + STEP7_4_2_PHASE2_REPORT.md） | ✅ **PASS（本轮正式结果）**（★λ 非结构杠杆/非量级杠杆；E06 三窗口拟合最优） |
| 7.4.3 设计 | `prepare_demand_scale_7_4_3.py` | **OD 总量 / 机动车出行量标定设计（零仿真，从不启动 MATSim）**：固定 λ=0.075 / f_cap=1.00 / 20 it，只做 demand scale；产出 **D01–D04** 实验矩阵；**★内含 MECHANISM 块（完整论证"缩放对象"）**——`expansionFactor`=`T_ij/N_ij`（MATSim **不消费**）、`odTrips`=cell 总量 T_ij（Σ 随 λ 变，**非需求量**，`od_trips/expansion_factor=N_ij`）、**agents（车辆数）= 唯一被 QSim 消费的物理需求杠杆**；含决策规则 + 双系列（D 物理 / A 算术参照） | 无（纯设计） | `reports/od_calibration_7_4_3/`（demand_scale_matrix.csv + demand_parameter_definition.json + STEP7_4_3_DESIGN.md） | ✅ **PASS（本轮）** |
| 7.4.3-R | `run_demand_scale_7_4_3.py` | **demand scale 运行器**：读 7.4.3 矩阵 → **嵌套随机子集复制** 按 permutation 前缀（`seed=20260912`）把 D01 冻结人口复制到 220k/240k/250k（每 agent 的 EF/home_link/work_link/departure end_time **逐字节不变**、复制概率对每个 agent 相同 → 增量空间**无偏**）→ `make_config_6_3.build_one`（`pop_dir=` 指新人口）+ 最小 patch（`flowCapacityFactor=storageCapacityFactor=1.00`、`lastIteration=19`、`write*Interval=0`）+ `verify_patch` 读回断言（f==1.0 / lastIter==19 / seed==4711 / ReRoute / routingRandomness==0 / plans 含 `pop_<EID>`）；支持 `--gen-only` / `--smoke N` / `--experiments` / `--force`；**可断点续跑**（it.19 linkstats 存在即跳过） | 7.4.3 矩阵、6.3.3A 冻结人口、`network_cleaned.xml.gz`、`fullConfig_2026_0.xml` | `reports/matsim_demand_7_4_3/pop_<EID>/`（复制人口）+ `reports/od_calibration_7_4_3/<EID>_lam0p075/`（每实验 20 it linkstats）+ `matsim/step6_3/config_D0*_lam0p075_dem1p*.xml` + `demand_run_manifest.json` | ✅ **PASS（人口/config 已生成 + 冒烟 2000×3it；★全量完成（D02–D04）+ 评价已出）** |
| 7.4.3-E | `evaluate_demand_scale_7_4_3.py` | **demand scale 评价（零仿真，仅读已有 linkstats）**：**import 冻结的 7.3.6B + 7.4.2 评价函数**（口径逐字节同源）；评价接口 = 7.3.6A Final Crosswalk、观测 = 7.1 冻结；**D01 复用 `E06_lam0p075_cap1p00`**；产出 **D 系列（物理加车、跑仿真）** 与 **A 系列（算术参照 = 把 D01 的 sim 直接 ×f，零仿真，代表"若仅总量偏小、空间形态正确"的上界）** 并列 → **A−D = 拥堵弹性阻尼**；含**需求量核查**（`pop_stats` 复核每档 ΣEF → `f_realized`）+ 四曲线（Sim/Obs **all / CATA / SLIP**、**CATA÷SLIP**）+ WMAPE/GEH<5/GEH<10/Pearson/Spearman；报告结构 = §0 方法学（双系列）/§1 对比表/§2 四曲线/§3 阻尼/§4 判读 | 各实验 linkstats、7.3.6A crosswalk、6.3.3B 基线、7.4.2 `E06_lam0p075_cap1p00` | `reports/od_calibration_7_4_3/`（demand_scale_backtest.csv + demand_scale_roadcat_summary.csv + **demand_scale_comparison.csv** + step7_4_3_summary.json + STEP7_4_3_REPORT.md） | ✅ **PASS（D01 自检逐位复现 E06；D02–D04 已跑完并出正式结果；**★补做非单调回落机制诊断见 `7.4.3-Diag` 行**）** |
| 7.5A-A 审计 | `audit_demand_chain_7_5a.py` | **需求权重链条核查（纯审计，零仿真）**：回答「MATSim 的 linkstats 由哪个字段、以什么方式形成有效需求权重」。**手段 = 4 条可复现证据**：(A) 枚举全项目 `*.java`；(B) 枚举 `*.py` 出现点并分类 **WRITE（写人口属性）/ READ_AUDIT（守恒复核、事后 EF 加权诊断）**；(C) 枚举全项目 `*.xml` 检查是否有 param 绑定这两个属性名；(D) **★决定性证据 = 对 `matsim-2026.0.jar` + `libs/*.jar` 做字节级常量池扫描**（Java 反射按属性名字面量读取 → 字面量必留常量池），并区分**命中是否落在 MATSim 自身 class**（`matsim-2026.0.jar` / `org/matsim/**`）；含**阳性对照**（`flowCapacityFactor` 等必须命中）以排除"扫描失效导致的假阴性"。**结论：`expansionFactor` 仅在 `commons-math3` 的 `ResizableDoubleArray.class` 出现（无关同名字段）、`odTrips` 零命中 → NOT_CONSUMED** | 无（纯审计：项目源码 + `tools/matsim-2026.0/**`） | `reports/od_sample_7_5a/`（demand_chain_audit.json + **STEP7_5A_DEMAND_CHAIN_AUDIT.md**） | ✅ **PASS（本轮，verdict = NOT_CONSUMED）** |
| 7.5A-P 设计+采样管线 | `prepare_sample_7_5a.py` | **固定样本量架构设计 + 100k 人口管线（零仿真，从不启动 MATSim）**：产出 **S200（REUSE_E06）/ S100（100k, f_cap=1.00）/ S100c（100k, f_cap=0.50 采样一致对照）** 矩阵；**三层需求**（真实需求 ΣT=459,794 / 采样率 N_sample / 有效权重 SCALE=ΣT/N_sample）；**★硬约束披露**：正 OD cell=71,136 → N_sample 下限；**★容量—采样耦合论证**（改采样率时 f_cap 必须同比缩放才保持同一物理场景）。**人口管线三阶段**：6.2B `--target-agents 100000` → 连通性修复（复用冻结 `network_cleaned.xml.gz`）→ 6.3.3A 出发剖面，**一律写入新目录**（`*_s100k`），**绝不覆盖冻结 200k 产物**；以 **monkeypatch 目录常量**方式复用三个冻结构建脚本（构建逻辑与守恒校验逐字节同源） | `car_prior_od_lambda_0p075.parquet`、`network_cleaned.xml.gz`、`TrafficFlow_Data.json` | `reports/od_sample_7_5a/`（sample_matrix.csv + **STEP7_5A_DESIGN.md** + sample_build_summary.json）+ `reports/matsim_population_6_2b_s100k/` + `reports/matsim_population_6_2b_connected_s100k/` + `reports/matsim_departure_6_3_3a_s100k/` | ✅ **PASS（本轮；persons=100,000、ΣEF=459,794.0、mean_ef=4.59794、出发剖面 count_07_08=48,710 / count_08_09=51,290）** |
| 7.5A-R | `run_sample_7_5a.py` | **固定样本量运行器**：读 7.5A 矩阵 → `make_config_6_3.build_one(ltg, pop_dir=<样本人口目录>)` 生成同源 config + 最小 patch（**唯一变量 = 采样率 / its capacity companion**：`flowCapacityFactor=storageCapacityFactor=<矩阵 f_cap>`、`lastIteration=19`、`write*Interval=0`）+ `verify_patch` 读回断言（f_cap / lastIter==19 / seed==4711 / ReRoute / routingRandomness==0 / plans 含 `matsim_departure_6_3_3a_s100k`）；**复用 7.4.3 运行器的 patch/verify 口径**；支持 `--gen-only` / `--smoke N` / `--experiments` / `--force`；**可断点续跑** | 7.5A 矩阵、`reports/matsim_departure_6_3_3a_s100k/`、`network_cleaned.xml.gz`、`fullConfig_2026_0.xml` | `reports/od_sample_7_5a/<EID>_lam0p075_cap*/`（20 it linkstats）+ `matsim/step6_3/config_S1*_lam0p075_cap*.xml` + `sample_run_manifest.json` | ✅ **PASS（config 已生成 + `verify_patch` PASS + 冒烟 2000×3it PASS；★S100 全量完成：143.80 min、exit=0）** |
| 7.5A-E 评价 | `evaluate_sample_7_5a.py` | **固定样本量评价（零仿真，仅读已有 linkstats）**：**import 冻结的 7.3.6B + 7.4.2 评价函数**（口径逐字节同源）；**★按实验注入不同 `SCALE`**（`bt.SCALE = ΣT/N_sample`，评价后还原）——S200=2.29897 / S100=4.59794；**★线性度检验**（`raw_sim_am(100k)/raw_sim_am(200k)` 应≈0.5）；**★等价性检验**（逐断面 `scaled sim_am` 的 S100 vs S200：比值中位/均值、±10%/±20% 内占比、Pearson/Spearman、总体 Σsim/Σobs）；数据驱动判决 `SUBSTITUTABLE` / `SUBSTITUTABLE_WITH_NONLINEARITY` / `NOT_SUBSTITUTABLE`；**★预注册判据（S100c，本轮新增）**：`PREREG` 常量（判据单一事实源）+ **`--prereg-only`**（跑前落盘 `preregistered_criteria.json` + `STEP7_5A_S100C_PREREGISTRATION.md`）+ **`check_preregistered()`** 逐条 PASS/FAIL **C1–C7**（报告新增 **§5 判定表** / **§6 三问判读**） | 各实验 linkstats、7.3.6A crosswalk、7.1 观测、7.4.2 `E06_lam0p075_cap1p00` | `reports/od_sample_7_5a/`（sample_backtest.csv + sample_roadcat_summary.csv + **sample_comparison.csv** + step7_5a_summary.json + STEP7_5A_REPORT.md + **preregistered_criteria.json** + **STEP7_5A_S100C_PREREGISTRATION.md**） | ✅ **S100 正式结果已出**（判 `NOT_SUBSTITUTABLE`）；**S100c 已完成**（判 `NOT_SUBSTITUTABLE`） |
| 7.5B-P 设计+采样管线 | `prepare_sample_7_5b.py` | **采样规则敏感性设计与 S100r 人口管线（零仿真）**：产出 **S200（REUSE_E06）/ S100c（现行保底规则，REUSE）/ S100r（**纯 trips-proportional，无保底**，RUN）** 矩阵；**★采样规则诊断（零仿真，不依赖 MATSim）**：把 6.2B 的 `allocate_cells`（保底 +1 + largest-remainder）与**纯比例**（`raw = target·T_ij/ΣT`，floor 后按小数部分补余，**无保底**）并列算出 → `sampled / zero-sampled OD cells`、`OD coverage`、`dropped trips`、`ΣEF`、`f_realized`、保底 agent 占比、agent 数分位、**逐 cell 重构误差**；**★S100r 人口管线**：**monkeypatch 6.2B 的 `allocate_cells` 为纯比例**（空间实现逻辑/XML 写出/守恒校验**逐字节复用**，只替换抽样函数）→ 连通性修复（复用冻结 `network_cleaned.xml.gz`）→ 6.3.3A 出发剖面，**全部写入新目录** `*_s100r`，**绝不覆盖任何冻结件** | `car_prior_od_lambda_0p075.parquet`、`network_cleaned.xml.gz` | `reports/od_sample_7_5b/`（`sample_matrix_7_5b.csv` + **`STEP7_5B_DESIGN.md`** + `sampling_rule_diagnostics.json` + `sampling_rule_summary.csv` + **`od_cell_sampling_rules.csv`** + `s100r_build_summary.json`）+ `reports/matsim_population_6_2b_s100r/` + `..._connected_s100r/` + `reports/matsim_departure_6_3_3a_s100r/` | ✅ **PASS（本轮；persons=100,000、ΣEF=438,266.0、OD coverage=0.5391、zero-sampled=32,786、被采样 cell 逐 cell 守恒误差 5.7e-14）** |
| 7.5B-R | `run_sample_7_5b.py` | **采样规则敏感性运行器**：读 7.5B 矩阵 → 复用 7.5A 的 `gen_experiment`/`run_matsim`（**config 与 S100c 除 `outputDirectory`/`runId`/`inputPlansFile` 外逐字节相同** → 单变量成立）+ `verify_patch` 读回断言（f_cap=0.50 / lastIter==19 / seed==4711 / ReRoute / routingRandomness==0 / plans 含 `matsim_departure_6_3_3a_s100r`）；支持 `--gen-only` / `--smoke N` / `--experiments` / `--force`；**可断点续跑** | 7.5B 矩阵、`reports/matsim_departure_6_3_3a_s100r/`、`network_cleaned.xml.gz` | `reports/od_sample_7_5b/S100r_lam0p075_cap0p50/`（20 it linkstats）+ `matsim/step6_3/config_S100r_lam0p075_cap0p50.xml` + `sample_run_manifest_7_5b.json` | ✅ **PASS（config `verify_patch` PASS + 冒烟 2000×3it PASS；★S100r 全量跑通：171.20 min、exit=0、20 it 全落盘）** |
| 7.5B-E 评价 | `evaluate_sample_7_5b.py` | **采样规则敏感性评价（零仿真，仅读已有 linkstats）**：**import 冻结的 7.3.6B + 7.4.2 评价函数**（口径逐字节同源）；**三方**（S200 / S100c 复用 / S100r）同 `SCALE` 口径（**名义需求相同 → 隔离采样规则效应**）+ 线性度 + 逐断面等价性；**★预注册判据（跑前固定）**：`PREREG_B` 常量 → **`--prereg-only`** 落盘 `preregistered_criteria_7_5b.json` + `STEP7_5B_PREREGISTRATION.md`；**D1–D7 绝对判据**（与 7.5A 的 C1–C7 同阈值）+ **M1–M4 机制判据**（差分：S100r 相对 S100c 是否改善）；**判决** `SAMPLING_RULE_WAS_THE_CAUSE` / `PARTIAL_IMPROVEMENT` / `SAMPLE_SIZE_DEPENDENT`；**★raw-EF 敏感性口径**解析给出（`SCALE_raw = ΣEF_sampled/N = 4.38266`，整体 ×0.95318） | 三方 linkstats、7.3.6A crosswalk、7.1 观测、`E06_lam0p075_cap1p00`、`od_sample_7_5a/S100c_lam0p075_cap0p50` | `reports/od_sample_7_5b/`（sample_backtest_7_5b.csv + sample_roadcat_summary_7_5b.csv + **sample_comparison_7_5b.csv** + step7_5b_summary.json + STEP7_5B_REPORT.md + **preregistered_criteria_7_5b.json** + **STEP7_5B_PREREGISTRATION.md**） | ✅ **正式结果已出：判 `PARTIAL_IMPROVEMENT`（D 0/6、M 3/4）** |

| 7.4.3-Diag | `diagnose_demand_scale_nonmonotonic_7_4_3.py` | **demand scale 非单调回落机制诊断（零仿真，只读）**：回答「08-09 单小时 `Sim/Obs` 在 f=1.20 达 0.8601 后、为何 f=1.25 回落 0.7599 —— 是 OD 需求参数效应，还是时间分配/拥堵饱和的**测量窗口伪影**」。**四层证据**：(A) **窗口加宽单调性检验**（linkstats 逐小时 `Σ_links HRSx-yavg`，窗口 08-09 → 07-09 → 07-10 → 07-11 → 07-12 → 0-24）；(B) **时间剖面**（`legHistogram` it.19 逐 5 min 出发/到达/滞留/在途 + 逐小时归因）；(C) **拥堵状态量**（`TRAVELTIME8-9avg` ÷ 自由流通过时间、按流加权拥堵倍率、>2×/>3× 拥堵链路数与流量占比、平均行程时长/距离）；(D) **估计量稳定性**（`demand_scale_backtest.csv` 逐断面 `D(b)/D(a)` 的**超额系数**与分位）。**判据跑前固定**：T1 日总量随 f 单调且≈等比 / T2 **窗口加宽恢复单调（决定性）** / T3 出发剖面跨档稳定 ≤0.10 pp / T4 无 agent 丢失与 stuck / T5 拥堵倍率与行程时长在 f1.20→f1.25 跳升。| 四档 `linkstats` / `legHistogram` / `legdurations` / `traveldistancestats`、`demand_scale_backtest.csv` | `reports/od_calibration_7_4_3/`（**STEP7_4_3_NONMONOTONIC_DIAGNOSIS.md** + demand_scale_window_widening.csv + demand_scale_timing_profile.csv + demand_scale_congestion_state.csv + demand_scale_section_step_ratio.csv + demand_scale_nonmonotonic_diag.json） | ✅ **PASS（判决 `TIME_WINDOW_ARTIFACT_CONFIRMED`，T1–T5 全过）** |
| 7.4.3-R | `reevaluate_demand_scale_windows_7_4_3r.py` | **宽时间窗重新评价（零仿真，只读 D01–D04 的 it.19 linkstats）**：回答「7.4.3 的非单调在更宽时间窗下是否消失、宽窗能否作水平判据」。**★前置阻断（决定窗口集合）**：LTA `TrafficFlow_Data.json` 的 `HourOfDate` **只有 7 与 8**（75,899 行 / 1,311 LinkID / 30 天，非脚本过滤），项目内 `TrafficSpeedBands_v4` 与 `EstimatedTravelTimes` **各只含 1 个 Timestamp** → **可观测窗上限 = 07-09**，`07-10/07-11/07-12/00-24` **无观测对象、Sim/Obs 无定义**。**Class O（可观测）**= 07-08 / 08-09 / 07-09(=冻结 `AM`)，出全指标（Sim/Obs、Bias、WMAPE、GEH、Pearson、CATA、SLIP、CATA/SLIP）；**Class S（无观测）**= 07-10 / 07-11 / 07-12 / 00-24，只出模拟侧量级。**★双聚合拆分**：`ALL`=全网 693,575 链路（≈总车公里，对空间重分配**不敏感**）× `MATCHED`=crosswalk 命中的 **3,037** 条标定链路（**敏感**）。**★口径同源断言 PASS**：与 `demand_scale_backtest.csv` 逐值一致（n=5,184，max\|Δ\|=3.6e-12）。 | it.19 linkstats（24 小时箱）+ 7.1 冻结观测 + 7.3.6A Final Crosswalk | `reports/od_calibration_7_4_3r/`（8 件） | ✅ **PASS（zero simulation）** |
| 7.6A-A | `account_official_car_demand_7_6a.py` | **官方汽车通勤需求会计（零仿真，只读；从不启动 MATSim）**：回答「`ΣEF = 459,794` 占官方机动车通勤需求多少、基准『总量不足』是 demand 还是口径差」。**★前置发现**：`TrafficFlow_Data.json` **无车型字段** ⇒ 观测的车型构成**不可分解**（模态缺口只能用 Census 作外部参照界定）。链条：居住/工作地就业锚 → **物理 vs 非物理**（No Fixed 177,588 / WFH 70,800 / Other-or-Outside 24,736 **单列，不进道路 OD**）→ 11 方式 → **口径变体 V1 459,796 / V2 526,477 / V3 707,116** → 占位率敏感性（occ 1.00/1.15/1.30）→ 目的覆盖 → **量级一致性检验**（`cov(V1/V3)=0.6502` vs MATCHED 07-09 `SimObs 0.6830`，比 **0.9520**）⇒ **`f ∈ [1.0504, 1.4641]`**，判决 **`CALIBER_GAP_DOMINATES`**；12/12 校验 PASS | Census 2020 T4/T9/T10/T11/T7/T15、GHS2025 T8、LTA `TrafficFlow_Data.json`、7.4.3-R、03B.1 控制 | `reports/od_calibration_7_6a/` | ✅ PASS |
| 7.6B-A | `audit_assignment_stability_7_6b.py` | **分配 / 路径稳定性审计（零仿真，只读复用 D01–D04 的 linkstats；从不启动 MATSim）**：回答「分配本身收敛了吗、标定断面的 VKT 份额 `R_cal` 是否随 demand 变、f=1.20→1.25 的落差里路径替代占多少」。**★先验事实（决定判读）**：D01–D04 config 全部为 `fractionOfIterationsToDisableInnovation = Infinity` + 唯一策略 `ReRoute`(weight 1.0) + `planCalcScore.learningRate = 1.0` + `routingRandomness = 0.0` ⇒ **100% agent 每代全部重新选路**，是**周期-2 极限环**的标准配置。**★决定性发现 = 周期-2 极限环**：奇/偶迭代从 it.0 起完全分离；MATCHED 周期振幅 **1.59% / 3.77% / 20.75% / 16.22%**（D01–D04），ALL 仅 0.39–1.40% ⇒ **放大 14.8×**；**08-09 冻结指标相位振幅 2.05% / 5.98% / 22.33% / 16.82%**；**周期均值（it.10–19 奇偶均衡）把跨 f 极差由 it.19 的 15.30% 压缩到 5.87%**（it.19 在 f=1.20 偏置 **+12.47%**）；**★同相位检验：偶相位 attainment 单调下降（1.0/0.9637/0.9065/0.8841）vs 奇相位峰在 D03（1.0/0.9849/1.0987/1.0238）⇒ 响应符号由采样相位决定 ⇒ 该实验在方法上无法识别 demand scale**；`R_cal` 归一（周期）1.0000/0.9483/0.9753/**0.9220**（f=1.25 时 −7.8%，轻微而方向正确的绕开标定断面）；相位翻转 MATCHED 与 NON-MATCHED 互相对冲（抵消比 0.53/0.40，全网总量仅动 1–2% ⇒ 纯路径替代）；**top50 最高流链路相邻两代 ρ = 0.986/−0.546/−0.209/0.465**；标定链路承担 |Δq| 的 4.8–5.7%（链路占比 0.4379%）；判决 **`UNCONVERGED_PERIOD2_LIMIT_CYCLE__CROSS_F_SIGNAL_BELOW_PHASE_NOISE`**；**20/20 校验 PASS** | D01–D04 it.0–19 linkstats、7.3.6A Final Crosswalk、7.1 冻结观测、7.4.3-R 已发布表（同源断言 max|d|=4.8e-7）、`config_E06/D02/D03/D04*.xml` | `reports/od_calibration_7_6b/` | ✅ PASS |
| 7.6D-A | `prepare_routechoice_7_6d.py` | **最小 route-choice 修复配置生成 + 零仿真配置验证（从不启动正式 run）**：以官方 `fullConfig` 为基线生成合法 config，再施加最小 patch（`fractionOfIterationsToDisableInnovation` `Infinity→0.8`、策略集 `[ReRoute 1.00]→[ReRoute 0.15, ChangeExpBeta 0.85]`、`scoring.learningRate` `1.0→0.5`、`routingRandomness` 保留 `0.0`），并做 **V1–V6 共 19 项断言**（策略集 / 修复标量 / 与基线 diff 仅 4 处 / `MUST_MATCH_BASELINE` 16 项逐值相同 / 显式冻结夹具 / DOCTYPE）；销出 `configs/` + `routechoice_7_6d_config_provenance.csv` + `routechoice_7_6d_config_validation.json` + `README.md`；`--smoke N` 截断人口跑冒烟，`--run` 正式 20 迭代；**新增** | 7.4.2 / 7.4.3 D01–D04 基线 config | `matsim_routechoice_7_6d/` |
| 7.6D-B | `audit_routechoice_stability_7_6d.py` | **稳定性评价（零仿真、只读；从不启动 MATSim）**：对 `ALL / MATCHED / CATA / SLIP` 四口径计算 **`A_W(X) = (max−min)/mean`**（预注册判据），并并报**双口径**（Primary `Q̄_10:19` / Reference `Q_19`）与 `parity_gap_rel`（7.6B 口径，仅供连续性对照）；`--include-ref` 同时评价 D02/D03/D04 修复前参照档；销出 `audit/routechoice_stability_{by_iter,amplitude,dual_caliber}.csv` + `summary.json` | 已跐 linkstats + 7.3.6A Final Crosswalk | `matsim_routechoice_7_6d/audit/` | **新增** |
| 7.6F-0 | `evaluate_demand_scale_7_6f_0.py` | **新稳定底座 demand=1.00 基准重算（零仿真、只读；从不启动 MATSim）**：**import 冻结的 `compare_final_crosswalk_7_3_6b` + `evaluate_calibration_7_4_2`**（口径逐字节同源）；把**双口径**（Primary = 收敛窗 it.10–19 **逐链路周期均值**后再算 Sim/Obs；Reference = it.19 单点）**统一施加到全部对照 run**（含旧配置），使「极限环中心」与「稳定收敛解」可比；每 run 注入自身 `SCALE = ΣT/N_sample`（200k→2.29897 / 100k→4.59794）；产出 **新基准点** + **旧分配层 vs 新分配层机制分解表** + **旧 demand 响应谱可辨识性判决**；**20/20 校验 PASS**（C1/C2 逐位重现 7.4.3；C3 七个 run 的 `Σ(cycle-mean HRS0-24avg|MATCHED)` 与 7.6D/7.6E 审计逐位一致）；收敛窗周期均值 linkstats 落盘 `_cycle_linkstats/` 可复用 |
| **7.6F-1-R** | **`run_demand_response_7_6f_1.py`** | **粗档 demand-response 点火器（★本项目唯一会启动 MATSim 的 7.6F-1 脚本）**：点火前对 config 做 **sha256 钉扎**、运行后再哈希断言**逐字节未变**（被执行的 = 被验证的）；点火前逐档**重跑 `prepare.validate()`（18/18）**（与 R01 逐参数 diff 白名单 + 7.6E route-choice 继承 + `f_cap`/seed/lastIter/λ + 人口指针）；**★`SCALE_FROZEN = 2.29897` 全档统一注入**，并把「若按 `ΣEF/N_sim` 重算」的偏离（F05 −397.69 / F15 −56.03 / F25 −56.32 ppm）**仅作披露**；**断点续跑**（`it.19` linkstats 存在即跳过）；写 `demand_response_7_6f_1_run_manifest.json`（exit code / wall min / iters / sha256 前后 / heap / 运行时描述）。**★串行执行**（本机 63.7 GB RAM、24g/run ⇒ 三档并行必 OOM） | 三档 config + 复制人口、R01 config、`it.19` linkstats | `matsim_demand_7_6f_1/{outputs,logs,audit}/` + `demand_response_7_6f_1_run_manifest.json` | ✅ **三档全 `PASS`（F05 69.73 / F15 80.40 / F25 75.74 min；累计 3.76 h）** |
| 7.6F-1-P | `prepare_demand_response_7_6f_1.py` | **粗档 demand-response 曲线入场准备（零仿真；从不启动 MATSim）**：按用户裁定网格 **`f = 1.05 / 1.15 / 1.25`** 生成三档**复制人口**（`f̲×̲200,000` = 210k/230k/250k，`seed=20260912` permutation 前缀**嵌套随机子集复制**，复用 `run_demand_scale_7_4_3.build_population` → F05⊂F15⊂F25，**F25 与 7.4.3 D04 人口解压后逐字节一致**）+ 三份 config（`make_config_6_3.build_one` + 复用 `prepare_routechoice_7_6d.apply_min_patch` 继承 7.6E 冻结 route-choice）+ **P1–P9 + W1–W6 共 67 项校验**（与 R01 config 差异**仅限** `plans.inputPlansFile` + `controller.{outputDirectory,runId}`；route-choice 4 项 / `f_cap=1.00` / seed 4711 / λ 0.075 / 冻结件 mtime 未变逐项断言）+ **预注册落盘**（`STEP7_6F_1_PREREGISTRATION.md`：§0 机制推论、§2 网格理由、§5 G1–G7 + 判决空间、§6 三口径、§7 明确不做、**§11 启动许可与追加硬约束**）。**★§0 机制门**：`f_demand` 必须缩放**被仿真 agent 数**（复制机制下 `SCALE=2.29897` 恒定）—— **已由用户于 2026-09-17 20:17 确认为「物理加车」并解除** | R01 config（diff 基线）、6.3.3A 冻结 200k 人口、冻结件 mtime 快照 | `matsim_demand_7_6f_1/`（`configs/`×3 + `populations/`×3 + `demand_response_7_6f_1_{matrix,config_provenance,strategy_provenance}.csv` + `..._config_validation.json` + `STEP7_6F_1_PREREGISTRATION.md`） | ✅ **PASS（67/67；★机制门已解除、已点火，见 `7.6F-1-R`）** |
| 7.6F-1-E | `evaluate_demand_response_7_6f_1.py` | **粗档 demand-response 曲线评价（零仿真、只读；从不启动 MATSim）**：**import 冻结模块** `compare_final_crosswalk_7_3_6b` / `evaluate_calibration_7_4_2` / `diagnose_od_spatial_structure_7_6c` / `audit_anomaly_trace_7_6c_1` / `evaluate_demand_scale_7_6f_0`（**不复制公式**）；构造各 run 收敛窗周期均值 linkstats（`_cycle_linkstats/` 缓存）→ 三口径（`FROZEN`/`POSITIVE_ONLY`/`BEST_DIRECTION`）+ 双口径（`Q̄_10:19` / `Q_19`）+ **稳定性承继**（`A_10:19` 四口径）+ **算术参照与拥堵阻尼比 ρ(f)= 实测/(R01×f)** + **空间残差（region/radial，只报告不压平）**；**★P1b/P1c SCALE 冻结审计**（全档统一 2.29897，`ΣEF/N_sim` 仅作披露并落盘 `demand_response_7_6f_1_scale_audit.csv`）；**预注册判据 G1–G7 + 判决空间**（`AWAITING_RUNS` / `RESPONSE_UNSTABLE` / `RESPONSE_NON_MONOTONIC` / `RESPONSE_STABLE_PARTIAL` / `RESPONSE_STABLE_CROSSES`）；**★与 7.6C-2 / 7.6D 审计缓存逐位对账**（R01 三口径 0.8589732 / 0.9350621 / 0.8909674；`Q̄_10:19` MATCHED/ALL/CATA/SLIP 四项**逐位相等**）以证明口径未漂移；网格未齐时输出 `AWAITING_RUNS` 并仍复算 R01 锚点 | 三档 linkstats、R01 linkstats/plans、7.3.6A crosswalk、7.1 观测、7.6C `section_geography`、7.6D 审计缓存、7.6F-1 矩阵/manifest | `matsim_demand_7_6f_1/audit/`（`demand_response_curve.csv` + `demand_response_arithmetic_reference.csv` + `demand_response_spatial_residuals.csv` + `demand_response_crossvalidation.csv` + **`demand_response_7_6f_1_scale_audit.csv`** + `od_demand_response_7_6f_1_summary.json` + `STEP7_6F_1_REPORT.md`） | ✅ **`RESPONSE_STABLE_CROSSES`（21/21 PASS；7.6C-2 对账 3/3 + 7.6D 对账 4/4 全中）** |
| **7.6G-P** | `prepare_lambda_sensitivity_7_6g.py` | **λ 敏感度 screening 入场准备（零仿真；从不启动 MATSim）**：`SPEC = [(L05,0.050,236000),(L75,0.075,236000),(L10,0.100,236000)]`；**只复制 agent 到 N_sim = 236,000**（`f_realized` ≈ 1.18），**λ 由 6.3.3A 的 λ 冻结人口承载**；**单点重绑定**复用 7.6F-1 的 `validate()`（W1–W6）＋ 新增 λ 专项门 **L1–L5**（λ 由人口承载 / 源人口 = 6.3.3A 冻结人口 / **λ 不变性 ΣEF=459,794** / `persons == N_sim` / SCALE 不重算）⇒ **72/72 PASS、`PREPARED`**；产出 `STEP7_6G_PREREGISTRATION.md`（§0–§8）、`lambda_sensitivity_7_6g_matrix.csv`、`_lambda_invariance.csv`、`_config_provenance.csv`、`_config_validation.json` |
| **7.6G-R** | **`run_lambda_sensitivity_7_6g.py`** | **λ 敏感度点火器（★本项目唯一会启动 7.6G MATSim 的脚本）**：`R.prep = P` **单点重绑定**（零逻辑复制）复用 7.6F-1 的 `preflight` / `iters_present` / `sha256_file`；点火前 config **sha256 钉扎**、运行后断言**逐字节未变**；**串行**（本机 63.7 GB RAM、24g/run ⇒ 并行必 OOM）；**断点续跑**（`it.19` linkstats 存在即跳过）；失败即**中止后续档**；写 `lambda_sensitivity_7_6g_run_manifest.json`（append 合并语义） |
| **7.6G-E** | `evaluate_lambda_sensitivity_7_6g.py` | **λ 敏感度评价（零仿真只读；从不启动 MATSim）**：`E.OUT` / `E.CYCLE_DIR` / `E.MATRIX_CSV` **重绑定** ⇒ 复用 7.6F-1 的 `eval_run` / `pooled` / `scale_audit`（**零公式复制**）；**import 冻结模块**保证逐位可复现；产出 `lambda_sensitivity_{curve,delta,spatial_residuals,spatial_spread,scale_audit,crossvalidation}.csv` + `od_lambda_sensitivity_7_6g_summary.json` + **`STEP7_6G_REPORT.md`**；判决 = `LAMBDA_{WEAK\|DETECTABLE_NOT_IDENTIFIABLE\|IDENTIFIABLE}` × `SPATIAL_{INERT\|ACTIVE}` |
| **7.6H-P** | `prepare_final_workingpoint_7_6h.py` | **最终工作点确定与独立验证入场准备 + 点火（准备段零仿真；`--run` 才启动 MATSim）**：`NEW_ROOT = matsim_final_7_6h`；`N_SIM = int(round(F_REF*N_BASE)) = 236,044`、`N_SIM_ROUNDED_F = int(round(1.1802*200000)) = 236,040`（**算术披露**）；**单点重绑**复用 7.6G 机器（`stage_population` / `build_config` / `validate` / `run_matsim`）⇒ **零逻辑复制**；**24/24 校验**（含 L1–L5 + W1：λ 不变性 / SCALE 冻结 / config 与 R01 恰差 **3 项白名单**） |
| **7.6H-E** | `evaluate_final_workingpoint_7_6h.py` | **最终工作点评价（零仿真只读；从不启动 MATSim）**：`E.OUT` / `E.CYCLE_DIR` / `E.MATRIX_CSV` **重绑定** ⇒ 复用 7.6F-1 `eval_run` / `pooled` / `scale_audit`；**H1** 可复现（4）/ **H2** 稳定（6，含 `never_arrived` / `max_stuck_car`，复用 7.6D `read_leg_hist`）/ **H3** 空间格局（2 + 关键 PA 表）/ **H4** 三层带（2）/ **P1** SCALE 审计 / **V1–V2** 判决；产物 `final_workingpoint_7_6h_{h1_reproducibility,h2_stability,h3_spatial,h3_key_pa,h4_bands,scale_audit,crossvalidation}.csv` + `od_final_workingpoint_7_6h_summary.json` + **`STEP7_6H_REPORT.md`**；判决 = `WORKING_POINT_{FROZEN_AND_REPRODUCIBLE\|NOT_REPRODUCIBLE\|FROZEN_BUT_UNSTABLE}` × `SPATIAL_{RESIDUAL_PERSISTS\|SHIFTED}` |
| 7.6C | `diagnose_od_spatial_structure_7_6c.py` | **OD 空间结构诊断（零仿真、只读；从不启动 MATSim）**：三轴 —— **P1 OD 距离结构**（分布/分带/长短尾/带内集中度，归一化不含总量）、**P2 空间集中与分散 + `0.8590` 缺口的空间结构**（Subzone/PA 集中度、异常吸收区、Table118 残差、按 Region/PA/RoadCat/环×径向 的缺口分解、**覆盖 vs 真实缺口**分离）、**P3 路由前 OD ↔ 路由后断面**（`ΣEF`/`N×SCALE` 守恒链、per-agent 实走距离 vs 阻抗距离 detour、it.0→it.19 空间重分配定位）。**import 冻结模块 `compare_final_crosswalk_7_3_6b`（口径逐位同源）**；窗口纪律：Sim/Obs 用 `HRS8-9avg`、稳定性用 `ΣHRS0-24avg`，**两者永不混用**；空间归属用 **link MIDPOINT → 最近 zone 质心（cKDTree）**，不用 `from_node`。预注册判据 S1–S7；**判 `OD_STRUCTURE_PARTIAL`**（S5/S6/S7 过、S4 不过）；**23/28 校验**；运行 **79.5 s**（200k plans 解析 53.2 s，缓存 `_agent_realized.parquet`）；`--skip-plans` / `--force-plans` | 冻结 OD + 阻抗 + 7.3.6A Crosswalk + Table118/T10 + R01 linkstats/plans | `reports/od_structure_7_6c/` | **新增** |
| 7.6C-2 | `audit_target_integrity_7_6c_2.py` | **校准靶场完整性门控（零仿真、只读；从不启动 MATSim）**：把 7.6C-1 发现的三类问题拆成 **`FROZEN`（主口径）/ `POSITIVE_ONLY`（敏感性）/ `BEST_DIRECTION`（误差边界）** 三口径（+ 最近有流 / 同名有流外包络），计算 **`Delta_target` = Q_POS − Q_FROZEN**，并把它换算到 **demand factor 单位**`Delta_f_target`（f\* = Q^(-1/ε)），再与 7.6F-1 的阶跃做**信噪比判定**（复用项目自己的“SNR < 1 ⇒ 不可用于推断”）；另做**口径越过一致性**、**7.6F-1 网格位置诊断 + 重排建议**、**`Delta_target` 空间分布**、**结构可分性**。**import 冻结模块** `compare_final_crosswalk_7_3_6b` / `diagnose_od_spatial_structure_7_6c` / `audit_anomaly_trace_7_6c_1`（**不复制公式**；交叉校验 7/7 全中） | 冻结件：7.6F-0 backtest + 7.6C `section_geography` + 7.6C-1 repair bounds + 7.3.6A crosswalk | `reports/od_target_integrity_7_6c_2/` | **新增** |
| 7.6C-1 | `audit_anomaly_trace_7_6c_1.py` | **异常归因追踪（零仿真、只读；从不启动 MATSim）**：**Layer 1** LTA 断面 → final crosswalk → matched MATSim links → R01 实走路径 全链路追踪，对全部 54 个零流断面做**四类机制归因**（`CROSSWALK_TWIN_ORPHAN` / `DIRECTION_MISMATCH` / `WINDOW_ARTIFACT` / `GENUINE_UNROUTED`），含**三窗口 × 正反向**流量、**有向拓扑可达性**（孤儿边判定）、**平行孪生链路**邻近度与**覆盖修正反事实区间**；**Layer 2** EAST↔CENTRAL 流向拆解（区域 OD 块矩阵 + 定向对称性 + 5 距离带；并流式解析 200k 条 R01 实走路径，按 起点区 × 终点区 × 距离带 聚合，对**全网 706,554 链**做 region/radial 分类）。**import 冻结模块** `compare_final_crosswalk_7_3_6b`（`SCALE`）与 `diagnose_od_spatial_structure_7_6c`（bands/聚合/口径，**不得复制公式**）；CLI `--force-routes` | 冻结件：7.6F-0 backtest + 7.6C `section_geography` + 7.3.6A crosswalk + `_cycle_linkstats` + `network_{nodes,links}.csv` + R01 `output_plans.xml.gz` + OD 先验 + Table118 残差 | `reports/od_anomaly_trace_7_6c_1/` | **新增** |
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

### 2.14 Step 7.3.2C Motorway Flow Spatial Loading 结果（流式 edge 装载 + CATA 空间对应，PASS）

新增 `scripts/od/diagnose_motorway_loading_7_3_2c.py`（7.3.2C-1）与 `scripts/od/analyze_cata_spatial_correspondence_7_3_2c.py`（7.3.2C-2）；输出 `reports/od_route_diagnosis_7_3_2c/`。

**降本设计（关键）**：此前对 `plans.xml.gz` 做**全量对象化解析**连续超时 → 改为**逐行二进制正则流式**（只提取 route links、只累计 motorway/motorway_link edge 计数，**不建 XML 树、不建 route 对象**），一次跑通（`unknown_link_uses=0`）。**events 不需要**。

**7.3.2C-1 核心结果**：
- **route 使用**：122,110/200,000 = **61.06%** route 用 motorway、**61.39%** 用 motorway_link（与 7.3.2B 逐位一致，双管线互证）；motorway 长度占比 **41.48%**、+ramp = **47.29%**。
- **edge 装载极度分散**：motorway 4,780 边（CSV 口径）/ 4,044 被用（**84.60%**）；**Top10 = 1.196%、Top50 = 5.46%、Top100 = 9.57%** → **不存在「少数边吸走大部分流量」**。TOP 边全是 **Central Expressway** 的微段（每条使用率仅 ≈9.67% = 15,335 的碎片化稀释）。
- **转移结构**：`m→m` 16.01M、`ml→ml` 5.12M、**`m→ml` 160,979 / `ml→m` 162,400**（与 7.3.2A 拓扑 240/240 互证）、`primary→ml` 84,887 / `ml→primary` 76,502。

**7.3.2C-2 核心结果（★决定性对照）**：
- 全网 motorway 平均装载 3,383.9 次/边；339 个 CATA 断面中 332 个有 motorway 匹配。
- **CATA 装载指数 mean 0.846 / median 0.780**（落在**低于均值 15–22%** 的走廊上，**64.5%** 低于均值）；`r(装载指数, sim/obs)` = **+0.19（n=332）** → 装载仅解释 ~3.6% 方差。
- **★ CATA vs SLIP_ROAD 装载指数几乎相同（0.846 vs 0.852；median 0.780 vs 0.767），但 sim/obs 相反（0.685 vs 2.046）** ⇒ **edge 级装载无法区分被低估的快速路主线与被高估的匝道**。
- **A/B/C 判定**：A 彻底否定；**B 弱-部分成立**（CATA 轻度低载但 r 弱）；**C 强支持（主因嫌疑）**——观测↔微段路网表达的系统性差异（碎片化下断面空间对位、点计数 vs 微边口径）。

**结论**：`motorway` 被大量使用、装载极度分散、CATA 略低载但非判别变量 → 剩余误差高度指向 **C 类（观测/表达）**，**route-choice 参数扫描优先级进一步下调**。

**下一步（建议）**：**Step 7.3.3 Observation–Representation Diagnosis（观测-表达专项，零仿真）**——(a) SLIP_ROAD 为何系统性高估；(b) CATA `r≈0` 是否源于微段-断面多对一的排序损失；(c) 把 CATA 聚合到**走廊级**后 sim/obs 是否回升。

---

### 2.15 Step 7.3.3 断面语义 ↔ MATSim Link 表达专项审计结果（零仿真，PASS）

用户交付 `scripts/od/audit_section_semantics_7_3_3.py`；**运行前修复 4 处 + 补 2 类验收产物**，输出 `reports/od_network_semantic_audit_7_3_3/`。输入 = 6.3.2 **tight crosswalk**（`reports/matsim_assignment_6_3_2/lta_section_matsim_crosswalk.csv`，**13,163 行 / 1,278 断面**；**该文件自带 `highway`/`RoadCat` 列**）+ `TrafficFlow_Data.json` + `network_links_source_copy.csv` + `network_nodes_source_copy.csv`。

**运行前修复（坑 44/45）**：① `TrafficFlow_Data.json` 是**长表**（75,899 行 = **1,311 断面 × 日期 × 小时 7/8**），原脚本按"一断面一行"直接 merge → `MergeError: not a many-to-one merge`；断面属性（RoadName/RoadCat）经核验**唯一** → 加载后按 `LinkID` 去重到断面级；② tight crosswalk 自带 `highway`/`RoadCat` 列，再合并 network/traffic 会生成 `_x/_y` 重名列并 `KeyError` → 合并前丢弃 crosswalk 内这两列，改由 network（`highway`）/ traffic（`RoadCat`）权威提供；③ docstring 转义告警（`\L`）→ raw string；④ 报告 f-string 缺 `**`。**补产物**：用户验收清单内的 `section_upstream_downstream.csv`（原脚本缺失）+ `roadcat_highway_correspondence.csv` + **方向/对向车道指标**（原脚本只算了与 LTA 方向夹角）。

**核心结果（★ = 决定性）**：

- **覆盖**：1,278/1,311 = **97.48%**（未覆盖 33 个恰为 `RoadCat=#N/A`）；平均 **10.30** 边/断面（中位 **8**）；路名一致率 **90.37%**。
- **★ CATA↔motorway 语义干净**：CATA 断面 **339** 个，等级语义一致率 **99.23%**、dominant 落 motorway 家族 **99.12%**（纯 motorway **92.92%**）、含 motorway 边 **97.94%**、混合语义仅 **16.81%**、路名一致 **91.45%** → **CATA 断面主体语义未错配**。
- **★ SLIP_ROAD↔motorway_link 语义严重不干净**：SLIP_ROAD 断面 **251** 个，等级语义一致率仅 **31.63%**、dominant 为纯 motorway_link 仅 **30.68%**（`*_link` 家族 31.47%）、而 dominant = **motorway 主线 55.8%**、混合语义 **47.81%**、路名一致仅 **70.12%**、平均 **11.69** 边/断面（**比 CATA 还多**）→ **匝道断面被"主线化"：系统性主线/匝道错配成立，且方向不对称（SLIP 侧成立、CATA 侧不成立）**。
- **一断面↔多边 & 一边↔多断面**：**28.10%** 匹配边被 ≥2 断面共享；**73.32%** 断面与其它断面共享 ≥1 条边 → 断面级流量存在重复计数。
- **★ 对向车道混入（不依赖 LTA 方向约定）**：**32.43%** 匹配边与自身断面模态方向相反；**72.07%** 断面含 ≥1 条对向边；**15.49%** 断面含**精确互反配对**（同两节点正反微段同时被匹配）；仅 **8.53%** 断面的匹配边可串成**单一有向链**（CATA 仅 **4.42%**）。实例：CATA 断面 `45094`（CENTRAL EXPRESSWAY）同时匹配 `e20232_20225`(2.5°) 与 `e20225_20232`(177.5°) → **一个"单方向断面观测"被表达为"双向微段集合"**。
- **上下游组合**：CATA 边界道路近 **37%** 为 motorway_link（立交口）；SLIP_ROAD 下游 **33%** 为 motorway_link、上游 20% motorway_link + 2.8% motorway。

**A/B/C 判定**：**C（观测-路网微段表达系统差异）由"嫌疑"升级为"直接证实"**，机制三条：(C1) SLIP_ROAD 匝道断面被主线化（dominant 55.8% = motorway）；(C2) 一断面→多边 & 一边→多断面多对多重叠（73.3% 断面共享边）；(C3) 方向语义未对齐（对向车道一并匹配、91.5% 断面无法串链）。**这与 7.3.2C 的反常信号自洽**：SLIP_ROAD 匹配边更多且混入大量主线 motorway 边 → 断面 sim 流量被推高（sim/obs=**2.046**）；CATA 断面匹配到双向 motorway 微段、被拆成碎片 → 断面 sim 口径与 LTA 断面口径不可比（sim/obs=**0.685**）。

**结论**：CATA 语义层对齐良好却被低估、SLIP_ROAD 语义层错配而被高估 ⇒ **误差主因在"观测断面语义 ↔ MATSim 微段表达"的对齐，而非 route preference**。**route-choice 参数扫描继续后置**；后续若要动，优先动 **network representation / crosswalk 语义对齐**（方向约束、匝道-主线分离、一对多聚合口径）。

**网络版本口径**：本步用 `network_links_source_copy.csv`（motorway **4,780** / motorway_link **9,086**）；7.3.2A 的 `network_cleaned.xml.gz` 为 **4,744 / 9,026**，差异 <1%（清洗前/后口径），正式报告需明确区分。

---

### 2.16 Step 7.3.4 断面语义对齐重构 + Sim/Obs 收敛判别结果（零仿真，PASS）

用户交付 `scripts/od/audit_section_rebuild_7_3_4.py`（重构）；AI **运行前修复 3 处阻塞缺陷 + 补伴随分析** `analyze_section_rebuild_flow_7_3_4.py`（收敛判别），输出 `reports/od_section_semantic_rebuild_7_3_4/`（14 产物）。

**运行前修复（坑 47）**：① 脚本 `NODES_DEFAULT` 指向不存在的 `network_nodes.csv`，实际为 `network_nodes_source_copy.csv` 且坐标为 `x_svy21_m/y_svy21_m/lon/lat`（非 `x/y`）→ 改路径 + 坐标列自适应（**优先 lon/lat，与 LTA 断面 heading 同口径**）；② `load_traffic` 返回列名为 `LinkID`，而 `build_candidates` 按 `lta_linkid` 合并 → `KeyError` → 合并前 `rename(LinkID→lta_linkid)`；③ docstring `\L` 转义告警 → raw string。

**重构结果（Part A）**：

| 指标 | old（6.3.2 tight） | rebuilt |
|---|---:|---:|
| 断面数 | 1,278 | 1,278 |
| 每断面平均边 / 中位 | 10.30 / 8 | **4.70 / 4** |
| 平均方向一致率 | — | **97.51%** |
| 平均语义一致率 | — | 88.48% |
| mixed-highway 断面 | — | **1.56%** |
| CATA dominant=motorway | 92.92% | **97.64%** |
| SLIP dominant=motorway_link | 30.68% | **52.99%** |
| SLIP dominant=motorway 主线 | 55.8% | **41.43%** |
| strict / fallback 边占比 | — | 87.47% / 12.53% |

**★ Sim/Obs 收敛判别（Part B，口径 = 7.1 冻结：`sim=median(匹配边 HRSx-yavg)×2.29897`；08-09 时段）**：

| crosswalk 变体 | CATA Σsim/Σobs | SLIP Σsim/Σobs | **CATA/SLIP** |
|---|---:|---:|---:|
| old（7.1 冻结） | 0.7388 | **2.0333** | **0.3633** |
| rebuilt（full，含 fallback） | 0.7707 | 1.8796 | 0.4100 |
| **rebuilt（strict-only）** | **0.7797** | **0.8535** | **0.9135** |

**★★ 过滤归因（决定性）**——08-09 Σsim/Σobs：

| 过滤 | CATA | SLIP_ROAD | CATA/SLIP |
|---|---:|---:|---:|
| full | 0.7707 | 1.8796 | 0.4100 |
| **dir_only（仅方向 ±30°）** | 0.7773 | 1.8513 | **0.4199** |
| **sem_only（仅语义）** | 0.7779 | **0.8055** | **0.9658** |
| strict（方向∩语义） | 0.7797 | 0.8535 | 0.9135 |

→ **仅加方向过滤几乎不动（0.41→0.42）；仅加语义过滤即让 SLIP 从 1.88→0.81、CATA/SLIP 从 0.41→0.97**。**误差主因是"SLIP 观测断面被匹配到 motorway 主线而非 motorway_link 匝道"（语义错配），既非方向、更非 route choice。**

**★ strict 覆盖偏差检查**：CATA 保留 **326/339（96.2%，obs 权重 97.4%）**；但 **SLIP 仅保留 129/251（51.4%，obs 权重 49.7%）**。进一步量化：**117/251（46.6%）SLIP 断面在基座 crosswalk 中根本没有 `motorway_link` 候选**（其中 **104 个 dominant = motorway 主线**、7 primary）；CATA 仅 **8/339（2.4%）** 缺 `motorway` 候选。

**结论**：(1) **收敛成立且归因明确**——CATA/SLIP 结构倒挂是"过向 + 主线/匝道语义错配"的产物，**纯语义对齐即可消除**（0.96）；(2) **残差 = 覆盖缺口**——近半 SLIP 断面无匝道候选，过滤无法凭空生成几何，SLIP 纯度存在由**基座 crosswalk 决定的上界**；(3) **CATA 稳定 ≈0.78**（各过滤不动，old 0.739）→ 其 ~22% 系统性低估与 crosswalk 无关，属**需求量级/全局尺度**问题；(4) **技术路线判决：停止 route-choice 参数扫描**，下一步 = **network representation / crosswalk 覆盖修正**（对 ~47% 无匝道候选的 SLIP 断面重新推导断面语义），随后再议 λ / 需求尺度。

**验收对照**：CATA 纯度 >95% ✅（97.64%）；对向边混入 <10% ✅（CATA 5.07% / SLIP 9.52%）；断面中位边数 << 8–12 ✅（4）；SLIP 纯度 >90% ❌（52.99%，受候选集上界约束）；CATA/SLIP 相对比 0.363→0.914 ✅✅。

---

### 2.17 Step 7.3.5 SLIP_ROAD 候选几何补全结果（零仿真，PASS）

> 目标：回答 7.3.4 遗留的**覆盖缺口**——117/251（46.6%）SLIP 断面为何在基座 crosswalk 中无 `motorway_link`：是**旧 crosswalk 候选机制不足**，还是**路网本身缺匝道几何**？
> 输入：`TrafficSpeedBands_Links.shp`（LTA 独立几何，WGS84，**143,787 LineString**，`RoadCat=6` slip = **5,207** 条）+ `network_links_source_copy.csv` + `network_nodes_source_copy.csv` + 6.3.2 tight crosswalk。**零仿真、不改任何冻结数据/参数。**

**运行前修复（坑 49）**：用户脚本 3 处阻塞——① `read_network` 用 **int64** 的 `from_node` join **字符串**节点索引 → `ValueError: merge on int64 and str`；② `read_nodes` 的 `usecols=["node_id","x","y"]` 与 `network_nodes_source_copy.csv`（列 `node_id,x_svy21_m,y_svy21_m,lon,lat`）不符 → 坐标列**自适应**；③ `old_had_candidate` 语义错误（计"任何边"而非"`motorway_link` 边"）。AI 重写并保留用户原件备份 `_build_slip_candidate_completion_7_3_5.py.user_orig_backup`。

**两个口径（关键，坑 50）**：`TrafficSpeedBands_Links.shp` 是 LTA **全网精细几何**（143,787 条，其中 slip 5,207），而校准相关的是 **1,311 个检测器断面**中的 251 个 SLIP → 必须区分 **CORE（251，=slip∩6.3.2 crosswalk）** 与 **FULL（5,207）**：FULL 中其余 4,956 条是**不参与流量校准**的匝道。**恢复率以 CORE 为准**。

**CORE 覆盖（主判据）**：

| 阶段 | 有 candidate | 覆盖 |
|---|---:|---:|
| 旧 6.3.2 crosswalk 含 `motorway_link` | **138** | 54.98% |
| 新几何（≤80 m）含 `motorway_link` | **250** | **99.60%** |
| 新几何 · 仅同向（±30°） | 248 | 98.80% |
| 新几何 · 仅同名 | 73 | 29.08% |
| 新几何 · 同向 + 同名（strict） | 62 | 24.70% |

- 旧缺口（无 `motorway_link`）：**113 / 251（45.02%）**
- **几何补回：112（占旧缺口 99.12%）**；仍缺失 **1**

**关键证据（最近「同向」匝道距离，line-to-line 真实距离）**：中位 **0.00 m**、均值 **1.64 m**；**≤5 m：232/248（93.5%）**、≤10 m 95.6%、**≤20 m 98.4%**、≤80 m 100% → 匝道几何**几乎逐条重合**（大量距离 = 0 m）。

**半径敏感性（CORE）**：50 m → 249 断面 / 补回 111（98.2%）；80 m → 250 / 112（99.1%）；120 m、200 m **不再增加** → **半径不是瓶颈**。

**FULL 覆盖（背景）**：2,498/5,207（47.97%）——因 FULL 含普通道路匝道（其附近本无 motorway_link），属正常背景、非反证。

**仍缺失断面**：唯一 **48170**（TAMPINES EXPRESSWAY）——最近 `motorway_link` 在 **~227 m** 外，近邻是 **`motorway` 主线**（距离 0 m）→ **单点真实几何缺口（0.4%）**。

**★与 7.3.4 的对账（113 vs 117）**：7.3.4 的 117 是在其 **已约简的 `rebuilt_crosswalk.csv`（6,008 行 / SLIP 1,103 行）** 上统计；本步以**冻结的 6.3.2 tight crosswalk（13,163 行 / SLIP 2,933 行）** 为基座得 **138 有 / 113 缺**，差异 4 个断面（45102/47200/48993/49474）源于 rebuild 边集缩减。两套 `highway` 标签与网络**完全一致（0 处不符）** → **113 为权威缺口**。

**★★判定：A（大量补回）** —— 理由：① 旧缺口 113 个中 **112 个（99.1%）** 被独立几何补回；② **93.5%** 断面与同向匝道距离 **≤5 m**；③ 半径 50 m 即达 98.2%、扩大无增益；④ 仅 **1** 个断面（0.4%）属真实几何缺口。
**根因**：6.3.2 crosswalk 以"**沿线采样 + 路名一致**"为锚，而 LTA slip 的 `RoadName` 是**所属高速名**（PAN ISLAND EXPRESSWAY / TAMPINES EXPRESSWAY …），OSM `motorway_link` 的 `name` 却**异构**（连接路 / 立交名 / 高速名混杂）——**精确同名仅覆盖 29.1%**，于是路名锚把匝道排除、断面被迫落到同名的高速**主线**（正是 7.3.3/7.3.4 观察到的"**匝道被主线化**"）。
**方法学含义**：SLIP→匝道指派应改用 **"几何重合 + 同向"**（≤5 m 覆盖 93.5%），**而非路名**；路名仅作辅助。

**产出**：`reports/od_slip_candidate_completion_7_3_5/`（10 产物：`STEP7_3_5_REPORT.md`、`step7_3_5_summary.json`、`slip_candidates_all.csv`、`slip_candidates_strict.csv`、`slip_section_summary.csv`、`slip_section_coverage.csv`、`old_vs_new_slip_coverage.csv`、`slip_core_missing_recovery.csv`、`slip_core_radius_sensitivity.csv`、`slip_core_nearest_samedir_distance.csv`）。

**结论/下一步**：(1) **覆盖缺口不是路网缺几何，而是旧 crosswalk 候选机制（路名锚）** → 7.3.4 的 "SLIP 纯度上界" 可被解除；(2) 下一步 = **Step 7.4 Network Representation / Crosswalk 覆盖修正**（按"几何重合 + 同向"重建 SLIP→`motorway_link` 指派），再用 6.3.3B linkstats 复算 Sim/Obs；(3) route-choice 参数扫描继续后置；λ 仍不冻结。

---

### 2.18 Step 7.3.6A Final Calibration Crosswalk 构建结果（零仿真，PASS）

> 目标：把 **6.3.2（几何基座 + 逐边 `distance_m`）+ 7.3.4（方向 + 语义）+ 7.3.5（独立几何补全）** 正式合成为**唯一、语义正确的评价映射**，供 7.3.6B 与 7.4 使用；**不覆盖 7.1 冻结靶场**。
> 输入：`lta_section_matsim_crosswalk.csv`、`rebuilt_crosswalk.csv`、`slip_candidates_all.csv`、`network_links_source_copy.csv`、`TrafficFlow_Data.json`。**零仿真、不改任何冻结数据/参数。**

**运行前修复（坑 51）**：用户脚本 3 处阻塞——① `load_traffic` 未把 `LinkID`→`lta_linkid`，`main()` 首行 `AttributeError`；② `semantic.merge(obs, on="lta_linkid")` 时 **`RoadName`/`RoadCat` 两边同名** → 生成 `_x/_y` → `cata[["RoadName","RoadCat"]]` **KeyError**；③ `slip.merge(slip_obs)` 同样 `RoadName` 冲突 → `slip_final[["RoadName"]]` **KeyError**。AI 重写并保留用户原件 `_build_final_calibration_crosswalk_7_3_6a.py.user_orig_backup`。**另补**：覆盖分母（CATA 339 / SLIP 251）、`selection_status`、`shared_section_count`、`is_primary_candidate`、`geometry_fallback`、N 超限 `REVIEW`、`UNMATCHED`、Gates 判定。

**分组陷阱（坑 52）**：修好列冲突后 SLIP 仍全为 0 —— 根因是 **`groupby` 默认 `dropna=True`**，而 SLIP 行曾因列冲突把 `RoadName` 填成 NaN → **整组被静默丢弃**，在 `sec` 里表现为"全部 UNMATCHED"。修法：`load_slip` 丢弃文件自带 `RoadName`（由 obs 权威提供）+ `groupby(..., dropna=False)` 兜底。

**硬规则**：`CATA → motorway`（direction ≤30°，name 仅辅助）；`SLIP_ROAD → motorway_link`（direction + geometry，**RoadName 不作硬约束**）。

**Tier 分层（断面级）**：CATA `CATA_T1_DIRECTION_SEMANTIC`；SLIP `SLIP_T1_DIRECTION_NAME` → `SLIP_T2_DIRECTION_GEOMETRY` → `SLIP_T3_GEOMETRY_ONLY`（geometry fallback，带 flag）；无可靠候选 → **UNMATCHED**。**1:N** 保留完整同向匝道链；N 超限（CATA>10 / SLIP>8，CLI `--cata-n-max/--slip-n-max` 可调）→ `REVIEW`（保留但标记）。

**核心结果**：

| 指标 | CATA | SLIP_ROAD |
|---|---:|---:|
| 观测断面数 | 339 | 251 |
| 匹配断面数 | **326** | **250** |
| 覆盖率 | **96.17%** | **99.60%** |
| 纯度（全部边=期望等级） | **100%** | **100%** |
| UNMATCHED | 13 | **1（48170）** |
| 平均/中位/最大边数 | 3.21 / 3 / 17 | 8.59 / 8 / 31 |
| REVIEW（N 超限） | 4 | 105 |

- Final crosswalk rows：**3,193**；断面 **590**；全局 mean/median 边数 **5.54 / 4**；p90 **11**、max **31**。
- Tier 边数：CATA_T1 **1,046**；SLIP_T2 **1,515** / SLIP_T1 **597** / SLIP_T3 **35**。
- **共享 MATSim 边率 4.87%**（远低于 7.3.3 的 73.3%，因基座已大幅去重）；**对向残差 1.10%**（仅来自 35 条 T3 几何回退边）。
- CATA 边数 100% 携带 6.3.2 几何 `distance_m`；SLIP T3（几何回退）仅 **35 条边 / 2 断面**，`direction_ok=False` 已显式 flag。

**Gates（全部通过）**：G1 CATA 语义 >95% ✅（100%）；G1 SLIP 语义 >90% ✅（100%）；G2 对向边 <10% ✅（1.10%）；G3 CATA 覆盖 >95% ✅（96.17%）；G3 SLIP 覆盖 >95% ✅（99.60%）。
> 纯度由构造保证，G1 的判别力主要在**覆盖率 / 未匹配断面**；真正的差异在 **7.3.6B** 的 Sim/Obs 回测体现。

**⚠ 需注意的张力（未擅自改阈值）**：SLIP 中位边数 **≈8**，恰好压在 `--slip-n-max=8` 上限 → **105/251（41.8%）SLIP 断面被标 REVIEW**。这是 OSM 匝道微段化的正常结果（单条 LTA slip 观测对应多条 ramp 微段）；因 7.1 断面聚合口径为 **median**，长链本身不引入系统性偏差，故 REVIEW 仅为"待复核"标记、**不剔除**。若需收紧，可 `--slip-n-max 12` 重跑。

**Scope（重要）**：本表仅覆盖 7.3 诊断锁定的 **CATA + SLIP_ROAD 两类**（590/1,311）；**CATB/CATC/CATD/CATE 不在表内**，其评价仍沿用 6.3.2/7.3.4 基底。若 7.4 需全网分等级校准，须按同一规则另行扩展。

**产出**：`reports/od_final_calibration_crosswalk_7_3_6/`（8 产物：`STEP7_3_6A_REPORT.md`、`step7_3_6a_summary.json`、`final_calibration_crosswalk.csv`、`final_section_summary.csv`、`final_cata_summary.csv`、`final_slip_summary.csv`、`crosswalk_edge_overlap.csv`、`crosswalk_quality_summary.csv`）。

**结论/下一步**：(1) Final Calibration Crosswalk 建立完成、语义/方向/覆盖三门全过；(2) **7.1 冻结靶场保持不变**（历史基准 / 可复现性），本表用于改进后的 calibration experiment，两者在报告里须明确区分；(3) 下一步 = **Step 7.3.6B 三方回测**（final vs 7.3.4 vs 7.1，用 6.3.3B linkstats 零仿真复算 CATA/SLIP 的 Sim/Obs），直接回答是否收敛到 1；(4) λ 仍不冻结。

---

### 2.19 Step 7.3.6B Final Crosswalk 三方回测结果（零仿真，PASS）

> 目标：用**已存在的 6.3.3B linkstats**（λ=0.05、`it.0`），按 **7.1 冻结口径**零仿真复算 `7.1 old → 7.3.4 semantic → 7.3.6A final` 的 **CATA / SLIP_ROAD Sim/Obs**，直接回答 `0.3633 → 0.9135 → ?` 是否收敛到 1。**不重跑 MATSim、不改任何模型参数、不动 7.1 冻结靶场、λ 仍不冻结。**
> 输入：`TrafficFlow_Data.json`、`lta_section_matsim_crosswalk.csv`（7.1）、`rebuilt_crosswalk.csv`（7.3.4）、`final_calibration_crosswalk.csv`（7.3.6A）、`step6_3_3b_lambda_0p050.0.linkstats.txt.gz`。

**运行前修复（坑 53/54）**：用户脚本 4 处缺陷——① `normalize_crosswalk` 保留 crosswalk 自带 `RoadCat` → 与观测表合并产生 `RoadCat_x/_y` → `groupby(["lta_linkid","RoadName","RoadCat"])` **KeyError（直接崩溃）**；② `load_traffic` **未按工作日过滤**、且**未先"日内均值再跨日中位数"** → 复现不出 7.1 的冻结观测（必须严格复刻 7.1 冻结口径）；③ 语义 crosswalk 喂入的是 **full（覆盖全 251 SLIP）**，而非用户引用的 **strict（129 SLIP）** → 中间值会变成 1.88 而不是 0.8535；④ `summarize` 缺 **WMAPE**、无 AM 窗口。AI 重写脚本并保留用户原件 `_compare_final_crosswalk_7_3_6b.py.user_orig_backup`。**新增**：`7.3.4_full` 作为**参照方法**（诚实披露"覆盖广 ≠ 语义对齐"）、AM/07-08/08-09 三窗口、CATA/SLIP 全指标矩阵（Pearson/Spearman/MAE/RMSE/MAPE/WMAPE/Bias/GEH<5/GEH<10）。

**口径（与 7.1 冻结一致）**：观测 = 工作日 TrafficFlow Volume → 日内均值 → `LinkID × hour` 日中位数（hour 7,8）；仿真 = `median(匹配 MATSim 有向边 HRSx-yavg) × 459794/200000`（=2.29897）；`obs_am = obs_7_8 + obs_8_9`；**主判据窗口 08-09**。

**★核心链条（08-09，Σsim/Σobs）**：

| Crosswalk | n(CATA/SLIP) | CATA | SLIP_ROAD | **CATA/SLIP_ROAD** |
|---|---|---|---:|---:|---:|
| 7.1 old | 339 / 251 | 0.7388 | 2.0333 | **0.3633** |
| 7.3.4 semantic (strict) | 326 / 129 | 0.7797 | 0.8535 | **0.9135** |
| **7.3.6A final** | 326 / 250 | **0.7797** | **0.7098** | **1.0984** |
| 7.3.4 full（参照） | 339 / 251 | 0.7707 | 1.8796 | 0.4100 |

> 链条：`0.3633` → `0.9135` → **`1.0984`**（越过 1，偏差 +9.8%）。AM 窗口同向：`0.3650 → 0.8982 → 1.0922`；07-08：`0.3663 → 0.8765 → 1.0816`。

**关键读数**：
- **final 的 CATA 映射与 7.3.4-strict 完全一致**（n=326、Σsim/Σobs 均 0.7797）→ 证实 7.3.6A 未额外补回 CATA 断面，**13 个 CATA UNMATCHED 仍缺**。
- **SLIP 由 2.0333（旧）→ 0.7098（final，n=250）**：几何补全（7.3.5）把覆盖从 129 → 250 断面，且新纳入的 121 个断面 sim/obs 更低 → **比值进一步下移、越过 1**。
- **7.3.4 full 参照（SLIP 1.8796）**：说明"保留 fallback 匹配、覆盖全 251 SLIP"只会把旧式错配重新引入 → **高覆盖 ≠ 语义对齐**（这是 7.3.4 覆盖率与纯度不可兼得的直接量化证据）。
- **残差性质转变**：修好结构后 **CATA 0.78 / SLIP 0.71 均 <1** → 剩余问题是**整体量级（全局少分配 ~25–30%）**，而非 CATA↔SLIP 的**相对**错配。

**评价指标矩阵（08-09，摘）**：

| RoadCat | method | n | Pearson | Spearman | WMAPE | GEH<5 | GEH<10 |
|---|---|---:|---:|---:|---:|---:|---:|
| CATA | 7.1_old | 339 | −0.057 | 0.256 | 0.619 | 7.1% | 15.3% |
| CATA | 7.3.4_semantic | 326 | −0.043 | 0.292 | 0.609 | 10.4% | 21.2% |
| CATA | 7.3.6A_final | 326 | −0.043 | 0.292 | 0.609 | 10.4% | 21.2% |
| SLIP_ROAD | 7.1_old | 251 | 0.213 | 0.208 | **1.750** | 4.0% | 11.2% |
| SLIP_ROAD | 7.3.4_semantic | 129 | 0.274 | 0.412 | 0.773 | 10.1% | 17.8% |
| SLIP_ROAD | **7.3.6A_final** | 250 | 0.272 | 0.348 | **0.715** | 9.6% | **22.4%** |

> SLIP 的 **WMAPE 1.750 → 0.715**（相对误差减半以上）、GEH<10 **11.2% → 22.4%** 翻倍；CATA 的 GEH<5 **7.1% → 10.4%** 亦改善。相关（Pearson）仍然弱——属**断面级排序**问题，与结构比值是两回事。

**产出**：`reports/od_final_crosswalk_backtest_7_3_6/`（7 产物：`STEP7_3_6B_REPORT.md`、`step7_3_6b_summary.json`、`final_crosswalk_backtest.csv`、`final_crosswalk_roadcat_summary.csv`、`final_crosswalk_method_comparison.csv`、`final_crosswalk_coverage.csv`、`final_crosswalk_metric_matrix.csv`）。

**结论/下一步**：(1) **7.3 的结构性问题（断面语义错配，C 类）已通过 7.3.4+7.3.5+7.3.6A 解决**——CATA/SLIP 由 0.3633 收敛到 **1.0984**，可正式把 **TrafficFlow 评价语义错配从主要模型误差中剔除**；(2) 残差转为**整体量级**（两类均 <1）；(3) 下一步 = **Step 7.4 联合校准**（在语义正确的 final crosswalk 上再议 λ / 需求尺度 / capacity 语义），**λ 仍不冻结**。

### 2.20 Step 7.4.1 联合校准实验矩阵 + Step 7.4.2 Phase 1 运行/评价（本轮）

> 目标：7.3.6B 已把**断面语义错配**从主要误差中剔除，残差转为**整体量级不足**（CATA 0.78 / SLIP 0.71 均 <1）。据此进入**受控联合校准** θ={λ, f_cap, route-choice}，但**先固化实验设计、再分批跑**，避免盲目全组合消耗算力。

**7.4.1（设计，零仿真）** —— `prepare_calibration_experiments_7_4_1.py`（**从不启动 MATSim**）：

- **冻结输入**：Final Calibration Crosswalk 7.3.6A、Departure 6.3.3A、OD/population 6.2B、`network_cleaned.xml.gz`、mode=car。
- **开放参数**：λ∈{0.050, 0.075, 0.100}；`flowCapacityFactor`∈{0.50, 0.75, 1.00}（**storage=flow 同值**，MATSim 2026 硬约束）；**route-choice 固定 20 iterations**（7.3.1 已证迭代次数非主要校准变量）。
- **9 组矩阵**：E01–E09；**执行策略 Phase1=E01–E03（λ=0.050），Phase2=E04–E09 按需**，不一次性启动。
- **★randomSeed 一致性修正（坑 56）**：外部草案把 seed 写成 `20260912`（疑为设计日期误写），项目**实测冻结值 = 4711**（`make_config_6_3.py` 硬编码；6.3.3B / capf_* / cf_it20 三份 config 均为 4711）。**为保持与 6.3.3B linkstats 及整条 7.x 评价链可比，采用 4711**，并在 JSON `random_seed_note` + 设计 MD 中披露。
- **预注册淘汰规则**：① 仅总体 Sim/Obs 改善而 CATA/SLIP 结构未改善 → 淘汰（只是调总量）；② 结构改善但 WMAPE/RMSE 明显恶化 → 淘汰；③ 三档 λ 的 J 差异落在实验误差内 → λ 继续不辨识；④ **λ 只有在不同 capacity 下持续占优**才算有辨识力。

**7.4.2 Phase 1（运行，本轮启动）** —— `run_calibration_phase1_7_4_2.py`：

- 三组：**E01 λ=0.050 f=0.50** / **E02 f=0.75** / **E03 f=1.00**，均 **20 it**。
- **唯一实验变量 = `qsim.flowCapacityFactor`**（+ storage 同值）；`lastIteration=19` 让基线 config 里已配好的 ReRoute(weight=1.0)/TTC 多迭代**自动启用拥堵反馈**。
- **磁盘控制**：`writeEvents/Plans/Trips/SnapshotsInterval=0`，只保留每迭代 linkstats（本实验唯一测量需求）；否则 20 it × 200k agents 会写出数十 GB events。
- **`verify_patch` 读回断言**：`flowCapacityFactor==storageCapacityFactor==f`、`lastIteration==19`、`randomSeed==4711`、`ReRoute` 存在、`routingRandomness==0`。
- **冒烟（2000 agents × 3 it，0.94 min）PASS**：逐迭代 linkstats 3 份齐全、**数值逐迭代变化**（HRS8-9avg sum 322k→314k→325k）→ 拥堵反馈确实生效。日志中收尾的 `DumpDataAtEndImpl` ERROR 为**良性**（因关掉中间迭代 plans 写出而无文件可拷贝，shutdown 正常完成、exit=0）。
- 每档约 **3 h 50 min**，三档约 **11.5 h**；**可断点续跑**（目标 it.19 linkstats 已存在即跳过）。

**7.4.2 评价（零仿真）** —— `evaluate_calibration_7_4_2.py`：

- **import 已冻结的 7.3.6B 模块**（`load_traffic`/`normalize_crosswalk`/`load_linkstats`/`calc_method`/`_metrics`）→ 口径**逐字节同源**，不做复制粘贴。
- **评价接口 = 7.3.6A Final Crosswalk**；**观测口径 = 7.1 冻结**；默认取最末迭代 it.19，另附 it.0 与 **6.3.3B 单迭代基线**，用于分离「迭代效应」与「capacity 效应」。
- **管线自检（本轮）**：对 6.3.3B 基线逐位复现 7.3.6B 头条 —— CATA **0.779683**、SLIP **0.709812**、**CATA/SLIP 1.098435**（7.3.6B 记 0.7797 / 0.7098 / 1.0984）✅。
- **★`HRSx-yavg` 语义确认（坑 57）**：经验判定 `HRSx-yavg` = **车辆数（volume）**（取值 1/2/5/6/… 整数计数），**不是速度**——`TRAVELTIME{x-y}avg` 才是行程时间（s，≈LENGTH/FREESPEED）。这印证 7.1 冻结口径 `sim=median(HRSx-yavg)×2.29897` 是「仿真流量 × 抽样扩样」而非「速度比流量」。
- **★Scope 披露**：7.3.6A Final Crosswalk **仅覆盖 CATA + SLIP_ROAD 两类**，故 `CATB/CATC/CATD/CATE` 的 Σsim/Σobs 在本评价中为 **null**（无匹配断面）——需全网分等级校准时须按同一规则另行扩展。

**结论/下一步**（Phase 1 已完成）：
- **★核心表（08-09，Σsim/Σobs）**：`6.3.3B(1it,f=1.00)` Sim/Obs 0.7690 / CATA **0.7797** / SLIP **0.7098** / CATA÷SLIP **1.0984**；`E01(f=0.50)` 0.3994 / **0.3874** / 0.4652 / **0.8328**；`E02(f=0.75)` 0.5698 / **0.5611** / 0.6181 / **0.9078**；`E03(f=1.00,20it)` 0.8105 / **0.8187** / 0.7652 / **1.0698**。
- **capacity 不是"只改总量"**：三档 `CATA/SLIP` **极差 0.2371** = 基线偏离 |1.0984−1| 的 **2.41×** → capacity 已进入结构通道；但**分解显示是两类道路拥堵弹性差**（f=0.50→1.00：CATA ×**2.11**、SLIP ×**1.64**，主线对容量更敏感），**不是 capacity 把车改派到哪类道路的语义级重分配**（区别要点：结构差来自"饱和度差异"，非"路径重分配"）。
- **★f=1.00 全面占优 → 不存在更优 f<1.00**：GEH<5 0.0642→0.0851→**0.1163**、GEH<10 0.1181→0.1719→**0.2170** 随 f 单调改善，Sim/Obs(all) **0.8105** 最接近 1 → **capacity 固定 f=1.00 作基线，不再作为待辨识变量**（f<1.00 只牺牲总体水平）。
- **迭代效应（同 f=1.00）**：1 it→20 it 使 Sim/Obs(all) **0.7690→0.8105（+0.0415）**、CATA/SLIP **1.0984→1.0698**、Pearson 0.2909→0.3309 → **固定 20 it 必要，迭代本身非主要结构误差来源**。
- **剩余误差 = 整体量级不足**：即使 f=1.00 + 20 it，Sim/Obs 仍只有 **0.81**、CATA 0.82 / SLIP 0.77 均 <1（全局少分配 ~19–23%）→ 下一步应聚焦 **λ 辨识（f=1.00 固定）** 与需求尺度，**Phase 2 精简为 λ=0.075/0.100 @ f=1.00（即 E06/E09），不必跑 E04/E05/E07/E08 的 f<1.00 组合**。
- (4) **λ 仍不冻结**。

---

### 2.21 Step 7.4.2 Phase 2 λ 灵敏度设计 + 运行（capacity 固定 1.00，本轮启动）

**目的**：Phase 1 已证 capacity 是"总量杠杆 + 拥堵弹性的从属结构响应"、且 **f=1.00 全面占优** → Phase 2 **固定 f_cap=1.00、20 it，只扫 λ**，检验 λ 是否**同时**改善「总体量级 + CATA/SLIP 结构 + 断面误差」，而不只是移动总流量。

**设计（零仿真）** —— `prepare_calibration_phase2_7_4_2.py`（**从不启动 MATSim**）→ `reports/od_calibration_7_4_2/`（`phase2_lambda_matrix.csv` + `phase2_parameter_definition.json` + `STEP7_4_2_PHASE2_DESIGN.md`）。

**⚠️ 编号映射（本步最需注意，已显式披露）**：用户口述的 Phase 2 编号 `E04/E05/E06/E07` 与 **7.4.1 冻结矩阵**编号**不一致**，故采用**规范 ID**：

| 用户 Phase 2 标签 | λ | 规范 ID | 说明 |
|---|---:|---|---|
| E04 | 0.025 | **E10（新增）** | 7.4.1 矩阵无此 λ；**全链 population 缺失 → BLOCKED** |
| E05 | 0.050 | **E03** | 7.4.1 矩阵 E03 = λ0.050/f1.00；**Phase 1 已完成，直接复用** |
| E06 | 0.075 | **E06** | 恰好一致：矩阵 E06 = λ0.075/f1.00 |
| E07 | 0.100 | **E09** | 矩阵 E09 = λ0.100/f1.00（矩阵 E07 = λ0.100/**f0.50**，f<1.00 已退役） |

> 7.4.1 矩阵所有 **f<1.00** 的行（E01/E02/E04/E05/E07/E08）在 Phase 1 后**退役**，不再运行。

**★λ=0.025 阻塞**：`reports/matsim_departure_6_3_3a/` 仅存在 λ ∈ {0.050,0.075,0.100} 的 population。要跑 λ=0.025 必须先补齐上游冻结链（**新增 λ，不改既有产物**）：`5A build_prior_od.py` → `5B build_prior_od_5b.py` → `5C1 build_prior_od_5c1.py` → `6.2B build_matsim_population_6_2b.py` → `prepare_connected_scenario.py` → `6.3.3A build_departure_profile_6_3_3a.py`（均 `--lambdas 0.025`）。**★用户决策（2026-09-14）：先跳过 λ=0.025**（E10 = `DEFERRED_BY_USER_DECISION`）——先用现有三点 λ∈{0.050,0.075,0.100}（E03/E06/E09）的正式趋势判断 λ 辨识力；若趋势显示确需拓展低端，再补齐上游冻结链新增 λ=0.025。

**运行（本轮完成）** —— `run_calibration_phase1_7_4_2.py --experiments E06 E09 --phase 2`（**复用同一运行器**，新增 `--phase`/`--manifest` 两个可选参数，默认行为不变）：E06(λ0.075)→E09(λ0.100)，各 20 it，`exit=0`（E09 墙钟 212.59 min）；可断点续跑；唯一变量 = λ（population 文件），capacity/seed/network/route-choice 全部冻结。**⚠️ 本轮修正**：`--manifest` 默认名按 `--phase` 生成（`phase<phase>_run_manifest.json`），避免覆盖 Phase 1 manifest（曾误覆盖，已恢复）。

**三组人口核对（关键）**：E03/E06/E09 的 config 分别指向 `population_lambda_0p050/0p075/0p100.xml.gz`；三者均为 **200,000 agents**、`Σ expansionFactor = 459,794` **恒定** → **模拟出行量在三个 λ 下相同**，差异纯来自 λ 的空间重分配（非总量）。旁证：`Σ odTrips` 随 λ 上升 4.215M→4.327M→4.485M。

**★结果（08-09，Σsim/Σobs）**：

| 实验 | λ | Sim/Obs(all) | WMAPE | GEH<5 | GEH<10 | Pearson | CATA | SLIP | CATA/SLIP |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 6.3.3B (1 it) | 0.050 | 0.7690 | 0.6257 | 0.1007 | 0.2170 | 0.2909 | 0.7797 | 0.7098 | 1.0984 |
| E03 (20 it) | 0.050 | **0.8105** | 0.6296 | 0.1163 | 0.2170 | 0.3309 | 0.8187 | 0.7652 | 1.0698 |
| E06 (20 it) | 0.075 | 0.7070 | **0.5660** | **0.1389** | **0.2413** | **0.3800** | 0.7137 | 0.6706 | 1.0642 |
| E09 (20 it) | 0.100 | 0.7646 | 0.5933 | 0.1163 | 0.2361 | 0.3388 | 0.7707 | 0.7304 | **1.0552** |

**结论（三类响应）**：
1. **λ 不是结构杠杆**：`CATA/SLIP` 跨 λ 极差 **0.0146**（1.0698→1.0642→1.0552，唯一单调项），仅为 Phase 1 capacity 极差 **0.2371** 的 **1/16** → 断面语义结构问题已由 7.3.6A 解决，λ 无须再动结构。
2. **λ 不是量级杠杆**：Sim/Obs(all) 随 λ **非单调**（峰@λ0.050、谷@λ0.075），极差 0.1034，且最优仍仅 **0.8105 < 1** → 补不上 19–25% 的整体量级缺口。
3. **λ 对截面拟合有真实但有限的正效应**：**E06 (λ=0.075) 在 WMAPE / GEH<5 / GEH<10 / Pearson / Spearman 上三窗口（07-08/08-09/AM）一致最优**；而量级最优是 E03(λ=0.050) → **存在「量级最优 0.050 vs 拟合最优 0.075」权衡**。
4. **λ=0.025 暂缓**（E10 = `DEFERRED_BY_USER_DECISION`），未纳入本轮趋势。

**结论/下一步**：**λ 仍不冻结**、**不自行按单一指标选 λ**（由用户判定）。候选：(a) **Phase 3 λ∈[0.06,0.09] 精细搜索**（改善截面拟合）；(b) 转 **OD 总量 / car-trip 扩样因子 (2.29897) / departure profile / mode coverage** 补量级缺口。

---

### 2.22 Step 7.4.3 OD 总量 / 机动车出行量标定（demand scale，本轮启动）

**背景（用户的纠正性判断，必须保留）**：Phase 2 **并未证明"λ≈0.075 即最终最优 λ"**——它只证明在**当前三档 {0.050,0.075,0.100}** 内 λ=0.075 对**截面拟合指标**（WMAPE/GEH<5/GEH<10/Pearson/Spearman）三窗口一致最优；且 λ 对**总量非单调**、三档均**明显总体低估**（最优仅 0.81）。→ **λ 暂不冻结**；本轮**固定 λ=0.075**（仅作控制变量），只研究一个问题：**当前全网约 0.71–0.81 的 Sim/Obs，是否主要由机动车 OD 总需求规模不足造成**。

**冻结项**：7.1 观测靶场、7.3.6A Final Crosswalk、network、capacity factor=**1.00**、simulation iterations=**20**、seed/routing randomness（4711 / SpeedyALT / `routingRandomness=0`）；**λ 暂不冻结**（本轮固定 0.075 仅为控制变量，**不代表 λ 已选定**）。

**实验矩阵（D01–D04，唯一变量 = demand scale 因子 `f_demand`）**：

| EID | f_demand | agents | 方式 | 说明 |
|---|---:|---:|---|---|
| D01 | 1.00 | 200,000 | **REUSE_E06** | **直接复用 Phase 2 的 E06，不重跑**（λ=0.075、f_cap=1.00、20 it） |
| D02 | 1.10 | 220,000 | RUN | 嵌套随机子集复制（D01 ⊂ D02） |
| D03 | 1.20 | 240,000 | RUN | 嵌套随机子集复制 |
| D04 | 1.25 | 250,000 | RUN | 嵌套随机子集复制 |

**★需求量承载机制（本步方法学基石，回答用户"到底该缩放什么"）**：

| 属性 | 定义 | Σ（三档 λ 原始均为 200k agents） | MATSim 是否消费 | 是否需求杠杆 |
|---|---|---|---:|---|
| `agents`（车辆数 / plans） | 出行个体数 | 200,000（**复制后 220k/240k/250k**） | ✅ **QSim 唯一消费** | ✅ **唯一物理需求杠杆** |
| `expansionFactor` | `EF_ij = T_ij / N_ij`（每 agent 代表的**真实车次**） | **459,794**（恒定）= 真实 car OD 总量 | ❌ **不消费** | ❌ 单独缩放只是算术重标定，**不改仿真** |
| `odTrips` | `T_ij`（该 cell 的 car OD 总量，**同 cell 每个 agent 写同一个值**） | 4.215M→4.327M→4.485M（**随 λ 变**） | ❌ **不消费** | ❌ `od_trips/expansion_factor = N_ij`（cell 内 agent 数，中位 4、max 114）→ ΣodTrips 只是每 cell agent 数分布的**影子** |

> **结论**：**只能缩放 agents（真实加车）**。缩放 `expansionFactor` 或 `odTrips` 都**不会改变 QSim 里的车辆数** → 不构成需求标定。**★这正是用户所担心的"把实现层权重差异误当真实需求"的关键排除**（就是 `odTrips`；`expansionFactor` 的 459,794 恒定但被 MATSim 忽略）。

**★双系列并列（本步方法学核心）**：
- **D 系列**：**真实加车 + 跑仿真**（D02–D04 各 20 it）→ 含**拥堵反馈**的真实响应。
- **A 系列（算术参照，零仿真）**：把 **D01 的 sim 直接 ×f** → `Sim/Obs` **精确 ×f**、`CATA/SLIP` **恒 = D01 的 1.064180**（结构对算术缩放**零响应**）→ 代表"若**仅总量偏小、空间形态正确**"的**上界**。
- **A − D = 拥堵弹性阻尼**：真实加车会因拥堵使车辆速度下降 / 绕行，使 Sim/Obs 增长**慢于** f → 该差值是**拥堵弹性**的直接度量（零仿真算术参照对真实仿真的偏离）。

**四曲线 + 指标**：Sim/Obs(**all**) / Sim/Obs(**CATA**) / Sim/Obs(**SLIP**) / **CATA÷SLIP**；并配 WMAPE / GEH<5 / GEH<10 / Pearson / Spearman → 判定 demand scale 是**纯量级杠杆**还是**同时进入结构通道**。

**判据（预注册）**：若 **Sim/Obs(all) 随 f 近线性升到 ≈1** 且 **CATA÷SLIP 基本不动** ⇒ **总需求不足是主因、需求尺度可冻结**；若 **CATA/SLIP 显著移动** ⇒ demand scale 亦进入结构通道（须与 capacity 的结构效应区分：**拥堵弹性差** vs **语义重分配**）。

**嵌套复制设计（保证增量无偏）**：D02/D03/D04 的 population 由 D01 冻结人口按 **permutation 前缀**（`seed=20260912`）复制——每 agent 的 `EF/home_link/work_link/departure end_time` **逐字节不变**、**复制概率对每个 agent 相同** → D02 ⊂ D03 ⊂ D04 的**增量空间无偏**（不是"重新抽一批人"，而是"在原人口上等比加车"）。

**产物**：见 §2 脚本清单 7.4.3 三行（`reports/od_calibration_7_4_3/` + `reports/matsim_demand_7_4_3/`）。

**★★结果（正式，2026-09-15）** —— `evaluate_demand_scale_7_4_3.py`；窗口 **08-09**；Σsim/Σobs；评价迭代 = it.19：

| 实验 | 系列 | f_demand | agents | Sim/Obs(all) | WMAPE | GEH<5 | GEH<10 | Pearson | CATA | SLIP_ROAD | CATA/SLIP |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 6.3.3B (1 it, λ=0.050) 参照 | baseline | — | — | 0.7690 | 0.6257 | 0.1007 | 0.2170 | 0.2909 | 0.7797 | 0.7098 | 1.0984 |
| D01 (=E06) | physical | 1.00 | 200k | 0.7070 | 0.5660 | 0.1389 | 0.2413 | **0.3800** | 0.7137 | 0.6706 | 1.0642 |
| D02 | physical | 1.10 | 220k | 0.7095 | 0.6103 | 0.1233 | 0.2448 | 0.3401 | 0.6980 | 0.7729 | 0.9031 |
| **D03** | physical | 1.20 | 240k | **0.8601** | 0.6957 | 0.0868 | 0.1979 | 0.3154 | **0.8512** | 0.9091 | 0.9363 |
| D04 | physical | 1.25 | 250k | 0.7599 | 0.6581 | 0.0885 | 0.2066 | 0.2464 | 0.7458 | 0.8376 | 0.8904 |
| A_f1.10（算术参照） | arithmetic | 1.10 | — | 0.7777 | 0.5923 | 0.1146 | 0.2257 | 0.3800 | 0.7850 | 0.7377 | 1.0642 |
| A_f1.20（算术参照） | arithmetic | 1.20 | — | 0.8484 | 0.6299 | 0.0920 | 0.1927 | 0.3800 | 0.8564 | 0.8047 | 1.0642 |
| A_f1.25（算术参照） | arithmetic | 1.25 | — | 0.8838 | 0.6512 | 0.0799 | 0.1753 | 0.3800 | 0.8921 | 0.8383 | 1.0642 |

**拥堵弹性阻尼（A − D，08-09）**：f=1.10 → **+0.0682**、f=1.20 → **−0.0116**、f=1.25 → **+0.1239**（**非单调**；f=1.20 为负 → 物理在该档甚至略高于等比外推）。

**★四条判读**：
1. **量级：非单调，峰 @f=1.20（0.8601），f=1.25 回落至 0.7599** → 跨 f 极差 **0.1530**；**最强档仍 0.8601 < 1（距 1 差 0.1399）→ 加车不能单独补齐量级缺口**（与 λ 同样"补不满"）。
2. **结构：不中性（显著移动）** —— `CATA/SLIP` 极差 **0.1738**（= λ 极差 0.0146 的 **12×**、= capacity 极差 0.2371 的 **73%**），且 **穿越 1**（1.0642 → 0.8904，CATA↔SLIP 相对高低反转）；**需求弹性 SLIP ×1.249 > CATA ×1.045** → **加车把结构推向 SLIP**（匝道侧对需求更敏感）。**修正**：评价器原报告 §5 硬编码"需求缩放对结构基本中性"与本次数字矛盾，已改为**数据驱动判决**。
3. **阻尼非单调且 f=1.20 为负** → `A − D` **同时**含「拥堵饱和」与「断面重分配」两种效应（算术参照冻结了 D01 的空间形态），**不能**单独解释为拥堵。
4. **窗口一致性**：07-08 **单调上升**（0.6585→0.6734→0.7586→0.7665）、08-09 与 AM **峰 @1.20**（AM 0.8098）→ 需求响应存在 **knee≈f1.20**，且 08-09 在最高档回落最明显（疑与饱和下 8–9 时窗计数被推迟/抑制有关，待查）。

**结论/下一步**：**demand scale 不能单独冻结为"补量级"的手段**（既补不满、又动结构）；**λ 仍不冻结**、**不自行选定 f_demand**。候选：(a) 在 **f≈1.15–1.20** 细扫并同时核 07/08/AM 三窗；(b) 转 **OD 空间结构标定**（结构对需求敏感、SLIP 弹性 > CATA）；(c) 复核饱和下 8–9 时窗的计数口径（非单调峰的成因）。

---

### 2.23 Step 7.5A 需求权重链条核查 + 固定样本量采样架构（本轮启动）

**为什么做**：7.4.3 证明 demand scale 补不满量级缺口（峰 @f=1.20 仅 0.8601）且动结构；而 D02–D04 用「200k→250k agents」实现需求放大，**运行时间随 agent 数暴涨**（D04 单次 **492.94 min**）。若后续还要做 λ 细搜 / OD attraction / departure profile / route choice / 最终验证，按 200k~250k/次跑十几次不可接受。

#### 2.23.1 ★审计（零仿真，决定性证据）：到底谁决定 link flow

链条：`OD trips T_ij → 6.2B 采样 → agent 数 N_ij → expansionFactor → odTrips → QSim → linkstats`

| 字面量 | 命中 jar | 是否命中 MATSim 自身 class | 判定 |
|---|---|---:|---|
| `expansionFactor` | `commons-math3-3.6.1.jar`（`org/apache/commons/math3/util/ResizableDoubleArray.class`） | **否** | 无关同名字段 |
| `odTrips` | — | **否** | 零命中 |
| `flowCapacityFactor`（阳性对照） | `matsim-2026.0.jar` | **是**（`QSimConfigGroup` / `HermesConfigGroup`） | 扫描有效 |
| `storageCapacityFactor`（阳性对照） | `matsim-2026.0.jar` | **是** | 扫描有效 |
| `countsScaleFactor`（阳性对照） | `matsim-2026.0.jar` | **是**（`CountsComparisonAlgorithm` / `GlobalConfigGroup`） | 扫描有效 |

扫描范围：**165 个 jar / 38,647 个 zip 条目**（`matsim-2026.0.jar` + `libs/*.jar`）；原理 = Java 反射按**属性名字面量**读取 person attribute → 字面量必留常量池 → 可直接字节搜索；**命中是否落在 MATSim 自身 class** 是判定口径（第三方库同名字段不算）。

- 项目自定义 Java = **0 个**（仓内两个 `*.java` 均为 MATSim 官方源码副本）；全项目 `*.xml` 对这两个属性名命中 = **0**。
- Python 侧对二者只有三种用法：**写**（6.2B）、**守恒/有限性校验**（`validate_matsim_population*.py`）、**事后 EF 加权诊断**（`compare_step6_3_3b.py` 读的是 MATSim **输出** persons）。**没有任何一处回流仿真**。
- **★一句话结论：MATSim 的 link flow 由进入 QSim 的 person/vehicle 数决定；`expansionFactor`/`odTrips` 不被消费 → 扩样必须在评价层施加 `SCALE = ΣT / N_sample`。**

#### 2.23.2 三层需求（论文口径）与硬约束

| 层 | 量 | 符号 | λ=0.075 值 |
|---|---|---|---|
| 1 | 真实需求 | `ΣT` | **459,794**（与 N 无关） |
| 2 | 采样率 | `N_sample` | 200,000 / **100,000** |
| 3 | 有效需求权重 | `SCALE = ΣT/N_sample` | 2.29897 / **4.59794** |

- **★硬约束**：`allocate_cells` 要求 `N_sample ≥` **正 OD cell 数 = 71,136**（λ=0.075）→ **50k 不可行（ValueError）**，100k 是可行且推荐的最低标定档。
- 三阶段 100k 管线实测：persons=**100,000**、ΣEF=**459,794.000**、mean_ef=**4.59794**、coverage=1.0、max_od_cell_error=1.4e-14；连通性修复 home 1,270 / work 1,182（中位位移 3.3 m）；出发剖面 count_07_08=**48,710** / count_08_09=**51,290**、零缺失/零重复。**冻结 200k 产物 mtime 未变（零覆盖）。**

#### 2.23.3 ★容量与采样率的耦合（本步最需要裁定的一点）

若 `N_sample` 200k→100k 而 **f_cap 固定 1.00**，车密度减半 → **每车经历的供给饱和度被改变** → 差异混杂「采样效应」与「供给/需求比效应」，无法判定 100k 是否可替代。要保持**同一物理交通场景**，`flowCapacityFactor` 必须**随采样率同比缩放**：

| 实验 | N_sample | f_cap | SCALE | 物理含义 |
|---|---:|---:|---:|---|
| **S200**（=D01/E06，复用） | 200,000 | 1.00 | 2.29897 | 参考场景 |
| **S100** | 100,000 | **1.00** | 4.59794 | 用户字面设计：同容量减样本 |
| **S100c** | 100,000 | **0.50** | 4.59794 | 采样一致：`f_cap = N/200k`，保持同一物理场景 |

> 判定逻辑：若 `S100c×SCALE ≈ S200×SCALE` 而 `S100×SCALE` 明显偏离，则同时得到两个结论——(a) 100k 是可替代样本；(b) **一旦改变采样率，capacity 就不能再独立冻结 1.00**（这是采样一致性的数学要求，不是把 capacity 当性能旋钮）。

#### 2.23.4 判据与产物

- 评价器按实验注入 `bt.SCALE`；**线性度检验** `raw_sim_am(100k)/raw_sim_am(200k) ≈ 0.5`；**等价性检验**逐断面比值中位/±10%/±20% 占比/Pearson/Spearman；数据驱动判决 `SUBSTITUTABLE` / `SUBSTITUTABLE_WITH_NONLINEARITY` / `NOT_SUBSTITUTABLE`。
- **明确不做**：不进 route-choice、不继续 7.4.3 细扫、不动 capacity（除 S100c 的采样一致对照）；**λ 仍不冻结**。
- 产物：`reports/od_sample_7_5a/`（审计 + 设计 + 评价 5 文件 + manifest 与日志）+ `reports/matsim_population_6_2b_s100k/` + `..._connected_s100k/` + `reports/matsim_departure_6_3_3a_s100k/`。

#### 2.23.5 ★结果（正式，2026-09-15）：S100 不能替代 S200（f_cap=1.00 下）

S100 全量跑完（**100k × 20 it，`exit=0`，墙钟 143.80 min**；it.19 linkstats 就绪），`evaluate_sample_7_5a.py` 按 **7.3.6A Final Crosswalk + 7.1 冻结口径**、**按样本注入 `SCALE`** 复算（S200 复用 E06，不重跑）。

| 实验 | N_sample | f_cap | SCALE | Sim/Obs(all) | WMAPE | GEH<5 | GEH<10 | Pearson | Spearman | CATA | SLIP | CATA/SLIP |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| **S200**（=E06） | 200,000 | 1.00 | 2.29897 | **0.7070** | 0.5660 | 0.1389 | 0.2413 | 0.3800 | 0.5801 | 0.7137 | 0.6706 | **1.0642** |
| **S100** | 100,000 | 1.00 | 4.59794 | **0.9784** | 0.7177 | 0.0938 | 0.1892 | 0.3198 | 0.5943 | 0.9938 | 0.8935 | **1.1122** |

**判读①线性度不达标（本步最关键的物理信号）**：`raw S100/200` 比值**中位 0.6174**、均值 0.6551（期望 **0.5000**）→ 减样本后**单位 agent 的实际流量上升 ~23.5%** → **车密度减半、拥堵减轻**的直接证据（QSim 只数车，raw 却**非线性**于 agent 数）。评价层再乘 2× SCALE 把这个非线性放大：`scaled 比值中位 1.2308 ≈ 2 × 0.6174 = 1.2348`（实测自洽）。

**判读②等价性差**：逐断面（n=525）`scaled 比值`中位 **1.2308** / 均值 1.3051；**±10% 内仅 17.9%、±20% 内仅 32.6%**；但 **Pearson 0.9006 / Spearman 0.9567**（截面**形态**强一致，只是**整体偏高**）→ 说明误差来自**水平/非线性**，非断面排序。

**判读③三窗口一致偏高**：S100 = 07-08 **0.7595** / 08-09 **0.9784** / AM **0.8699**（S200 对应 0.6585 / 0.7070 / 0.6830）→ 同比偏高，非单窗伪影。

**△判决 `NOT_SUBSTITUTABLE`**（判据：scaled 比值中位 |r−1|≤0.10 **且** ±20% 内 ≥0.80 **且** raw 线性比 |0.5−中位|≤0.05）。

**★物理结论（不是「100k 没用」，而是「f_cap=1.00 对照不干净」）**：本对照把 `N_sample` 200k→100k 而把 `f_cap` 固定 1.00 → **车密度减半、供给/需求比被改变**，S100 与 S200 的差异**混杂「采样效应」与「拥堵物理改变」两种成分**。要判定 100k 是否为可替代样本，须跑 **S100c（100k, f_cap=0.50 = N_sample/N_ref）** 这一**采样一致的干净对照**——**已备好、未运行（待用户裁定）**。

**产物**：`reports/od_sample_7_5a/`（`STEP7_5A_REPORT.md`（正式版）+ `step7_5a_summary.json` + `sample_comparison.csv` + `sample_backtest.csv` + `sample_roadcat_summary.csv` + `sample_run_manifest.json`）。

#### 2.23.6 ★S100c 采样一致对照：预注册判据（跑前固定）→ 已完成（判 `NOT_SUBSTITUTABLE`，预注册硬门槛 1/6）

**用户裁定（2026-09-15）**：授权跑 S100c，并要求**先把判据固定下来**（避免「看到结果再决定标准」）。定义更严格：**S100c 不是「继续调容量」，而是验证 100k 样本在等效供需比下能否复现 200k 的交通状态** —— 决定后续计算规模的关键实验。

| 项 | 设定 |
|---|---|
| S200 | N=200,000, f_cap=1.00 |
| **S100c** | **N=100,000, f_cap=0.50** |
| 其余全固定 | λ=0.075 / 20 iterations / seed=4711 / routingRandomness=0 / same network / same OD / same departure profile / same Final Crosswalk / same 评价靶场 |

**★预注册判据**（`preregistered_criteria.json` + `STEP7_5A_S100C_PREREGISTRATION.md`，**均在 S100c 运行之前生成**）

| ID | 判据 | 目标 | 门槛 |
|---|---|---|---|
| C1 | 动力学等价性：raw flow ratio 中位 | 接近 0.50（\|中位−0.50\|≤0.05） | **硬** |
| C2 | 扩样后等价性：scaled S100c/S200 中位 | 接近 1.00（\|中位−1\|≤0.10） | **硬** |
| C3 | scaled ratio ±10% 内占比 | 尽可能高 | 仅报告 |
| C4 | scaled ratio ±20% 内占比 | ≥ 0.80（较强证据） | **硬** |
| C5 | Pearson / Spearman（scaled 逐断面 vs S200） | ≥0.90 / ≥0.95 | **硬** |
| C6 | CATA/SLIP 漂移（主窗口 08-09） | ≤0.05 | **硬** |
| C7 | 三窗口方向一致 | 每窗 \|Δ\|≤0.05 且同号 | **硬** |

**通过规则**：C1/C2/C4/C5/C6/C7 全 PASS → 判定 **100k 在等效供需比下可替代 200k**（此后 **100k 用于全部参数标定 / 敏感性分析 / 迭代搜索，200k 只保留一次最终验证**）。

**★容量语义（严格区分）**：S100c 的 `f_cap=0.50 = N_sample/N_ref` 是**采样一致性校正**（保持同一物理供需比），**不是**交通供给标定参数——与 Phase 1 的 `capacity_factor` **不能混为一谈**。

**跑完要回答的三个问题**：① **动力学等价性**（raw ratio 是否回到 ≈0.50，而非 S100 的 0.6174）；② **扩样后等价性**（scaled 比值 / WMAPE / GEH / Pearson/Spearman）；③ **结构是否保持**（`CATA/SLIP` + 三窗口 07–08 / 08–09 / AM）。

**状态**：S100c config 已 `verify_patch` PASS（qsim `f_cap=0.50`、`lastIter=19`、`seed=4711`、`routingRandomness=0`、plans→`matsim_departure_6_3_3a_s100k`）；**全量完成（100k × 20 it，`exit=0`，墙钟 164.59 min，20 迭代全落盘，`STATUS: PASS`）**。

**评价器增强（本轮）**：`evaluate_sample_7_5a.py` 新增 **`PREREG` 常量**（判据单一事实源）+ **`--prereg-only`**（跑前落盘判据）+ **`check_preregistered()`**（C1–C7 逐条 PASS/FAIL）+ 报告新增 **§5 预注册判定表** / **§6 三问判读**。

#### 2.23.7 ★S100c 正式结果（2026-09-15）：**预注册判据未通过 → 100k 不可替代 200k**

**总判定 `NOT_SUBSTITUTABLE`**（S100 与 S100c 均未过线）。三方正式评价表（窗口 08-09，Σsim/Σobs，it.19）：

| 实验 | N_sample | f_cap | SCALE | Sim/Obs(all) | WMAPE | GEH<5 | GEH<10 | Pearson | Spearman | CATA | SLIP | CATA/SLIP |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| **S200** | 200,000 | 1.00 | 2.29897 | **0.7070** | 0.5660 | 0.1389 | 0.2413 | 0.3800 | 0.5801 | 0.7137 | 0.6706 | **1.0642** |
| **S100** | 100,000 | 1.00 | 4.59794 | 0.9784 | 0.7177 | 0.0938 | 0.1892 | 0.3198 | 0.5943 | 0.9938 | 0.8935 | 1.1122 |
| **S100c** | 100,000 | **0.50** | 4.59794 | **0.8389** | 0.7090 | 0.1076 | 0.1875 | 0.3057 | 0.5376 | 0.8440 | 0.8108 | **1.0409** |

**线性度 / 等价性**（逐断面，n=525）：

| 对比 | raw 比值中位 | raw 比值均值 | scaled 比值中位 | ±10% | ±20% | Pearson | Spearman |
|---|---:|---:|---:|---:|---:|---:|---:|
| S100 / S200 | 0.6174 | 0.6551 | 1.2308 | 0.1790 | 0.3257 | 0.9006 | 0.9567 |
| S100c / S200 | **0.5799** | 0.6588 | **1.1537** | 0.1105 | 0.2648 | 0.8557 | 0.9344 |
| 期望 | 0.5000 | 0.5000 | 1.0000 | — | ≥0.80 | ≥0.90 | ≥0.95 |

**预注册判据逐条判定**（S100c：硬门槛 **1/6**，仅 C6 PASS；S100 为 3/6）：

| ID | 判据 | S100c 实测 | 判定 |
|---|---|---|---|
| C1 | 动力学等价性（raw ratio 中位） | **0.5799** vs 0.5000 | FAIL（\|Δ\|=0.0799>0.05） |
| C2 | 扩样后等价性（scaled 比值中位） | **1.1537** vs 1.0000 | FAIL（\|Δ\|=0.1537>0.10） |
| C3 | ±10% 内占比（仅报告） | 0.1105 | — |
| C4 | ±20% 内占比 ≥ 0.80 | 0.2648 | FAIL |
| C5 | Pearson≥0.90 且 Spearman≥0.95 | 0.8557 / 0.9344 | FAIL |
| C6 | CATA/SLIP 漂移（08-09）≤0.05 | **0.0233** | **PASS** |
| C7 | 三窗口方向一致（\|Δ\|≤0.05 且同号） | 07-08:0.0277 / 08-09:**−0.0233** / AM:0.0005 | FAIL（仅符号不一致；三窗 \|Δ\| 均 ≤0.0277） |

**★三条判读（f_cap 校正部分有效，但不足以替代）**：
1. **f_cap 校正确实有效（部分）**：`f_cap=0.50` 把 raw 比值中位从 **0.6174 拉回 0.5799**（采样非线性 +23.5% → **+16.0%**）；**CATA/SLIP 漂移减半**（0.0480 → **0.0233**，C6 PASS）→ 证实 **S100 的结构畸变主要是「车密度/容量」效应**，同比缩放容量可基本修复。
2. **但残余非线性仍在（16%）**：样本量本身改变网络动力学（拥堵节流非线性 + 代理样本空间分布差异），**标量 f_cap 无法消除** → `scaled` 比值仍偏高中位 **1.1537**、±20% 仅 0.2648。
3. **存在权衡**：`f_cap=0.50` 改善了水平（Sim/Obs 0.9784→**0.8389**）与结构（C6 PASS），但**空间相关性略降**（Pearson 0.9006→**0.8557**）——因 100k 样本的 volume 分布≠200k，标量 f_cap 是粗糙校正，拥堵位置错配使逐断面形态稍离 S200。

**★候选机制（待查，非定论）**：6.2B 采样规则「**每个正 OD cell ≥1 agent**」在 100k 下使 **71.1% 的 agent 是「保底 agent」**（71,136/100,000），而 200k 下仅 35.6% → **样本空间分布随 N 系统性变平**（小 cell 被相对高估）。这可能是残余非线性的一部分（属**采样规则伪影**，非纯网络物理）——若要干净 100k，需改采样规则（如按 trips 无保底抽样）。

**结论**：**100k 在 f_cap=1.00 与 f_cap=0.50 下都不能替代 200k**；「固定样本 + 可变权重」在 **MATSim 拥堵型网络**中**不成立**（采样非线性不可忽略）。**100k 方案不冻结**；**λ 仍不冻结**。

**产物**：`reports/od_sample_7_5a/`（`STEP7_5A_REPORT.md` 三方正式版 + `step7_5a_summary.json` + `sample_comparison.csv` + `sample_backtest.csv` + `sample_roadcat_summary.csv` + `sample_run_manifest.json`）。

---

### 2.24 Step 7.5B Sampling Rule Sensitivity 采样规则敏感性（**本轮完成**；判决 `PARTIAL_IMPROVEMENT` D 0/6、M 3/4）

#### 2.24.1 ★动机：S100c 同时给出两条方向不同的信号

7.5A 的 S100c（100k, f_cap=0.50，采样一致对照）说明「100k 不可替代 200k」，但它同时留下**两条方向不同的信号**：

| 信号 | 数值 | 含义 |
|---|---|---|
| (a) 结构畸变可被容量修复 | `CATA/SLIP` 漂移 0.0480（S100）→ **0.0233**（S100c），C6 PASS | 「采样导致的**供需密度**变化」是重要机制，**容量同比缩放可基本吸收** |
| (b) 残余非线性仍在 | `raw ratio` **0.5799**（≠0.50）；Pearson 0.9006 → **0.8557** | 还有**第二层：样本空间分布偏差**（且空间相关性反而下降） |

**假设**：6.2B `allocate_cells` 的「**每个正 OD cell 至少 1 个 agent**」保底规则，让小 trips 的 cell 获得**相对过多**的代表个体；该畸变**随 N 减小急剧放大**：

| N_sample | 保底 agent 数 | 占全部 agent 比例 |
|---:|---:|---:|
| 200,000 | 71,136 | **35.568%** |
| 100,000 | 71,136 | **71.136%** |

→ 因此在做任何样本量（125k/150k/175k）扫描**之前**，必须先回答：**保底采样到底是不是残余非线性的主因？** 两者后续处理完全不同：

- 若 S100r 改善 → **保留 100k，改采样算法**；
- 若 S100r 仍偏离 → 才可认定存在 **sample-size dependence**，此时 knee 扫描才有意义。

#### 2.24.2 单变量设计（唯一变量 = 采样规则）

```text
S100c（现行规则）  每正 OD cell >= 1 agent  + largest-remainder      已完成，复用
S100r（纯比例）    不设保底；raw = target * T_ij/SigmaT，floor 后按小数部分
                   补余（允许 cell 被抽到 0 个 agent）                ← 本步唯一新实验
```

**完全冻结**：`N_sample=100,000` / `λ=0.075` / `flowCapacityFactor=storageCapacityFactor=0.50`（= N/N_ref，**采样一致性校正**）/ 20 iterations / `randomGenerationSeed=4711` / `routingRandomness=0` / `routingAlgorithm=SpeedyALT` / 同一 `network_cleaned.xml.gz` / 同一 OD / 同一 departure profile / 同一 7.3.6A Final Crosswalk / 同一 7.1 观测靶场。

> **★单变量的机器验证**：`config_S100c_lam0p075_cap0p50.xml` 与 `config_S100r_lam0p075_cap0p50.xml` 在忽略 `outputDirectory` / `runId` / `inputPlansFile` 后**逐字节完全相同**（diff = 0）→ 唯一差异只有人口的空间分配规则。

#### 2.24.3 采样规则诊断（零仿真，人口侧）

λ=0.075 正 OD cell 数 = **71,136**，ΣT = **459,794**（`reports/od_sample_7_5b/sampling_rule_summary.csv`）：

| N_sample | 采样规则 | sampled cells | **zero-sampled** | **OD coverage** | 丢弃 trips | ΣEF | `f_realized` | 保底占比 | agent 数 min/中位/max |
|---:|---|---:|---:|---:|---:|---:|---:|---:|---|
| 100,000 | `FLOOR_PLUS_1` | 71,136 | 0 | 1.0000 | 0 | 459,794.0 | 1.00000 | 71.14% | 1 / 1 / 26 |
| 100,000 | **`PURE_TRIPS_PROP`** | **38,350** | **32,786（46.09%）** | **0.5391** | **21,528（4.68%）** | **438,266.0** | **0.95318** | **0** | 0 / 1 / **87** |
| 200,000 | `FLOOR_PLUS_1` | 71,136 | 0 | 1.0000 | 0 | 459,794.0 | 1.00000 | 35.57% | 1 / 2 / 114 |
| 200,000 | `PURE_TRIPS_PROP` | 46,843 | 24,293（34.15%） | 0.6585 | 8,644（1.88%） | 451,149.7 | 0.98120 | 0 | 0 / 1 / 175 |

**读法**：保底规则下**零 cell 被遗漏**（coverage = 1.0），但 100k 时**中位 agent 数 = 1**（即一半 cell 只拿到一个保底 agent）；纯比例下这些 cell **直接归零**（46.09%），agent 集中到高 trips 的 cell（max 26 → **87**）。

**7.5B 要求输出的 6 项（S100r 实测，`s100r_build_summary.json`）**：

| 量 | 值 |
|---|---:|
| positive OD cells | 71,136 |
| sampled OD cells | 38,350 |
| **zero-sampled OD cells** | **32,786** |
| **OD coverage** | **0.539108** |
| **Σ expansion_factor** | **438,266.002**（`f_realized` = **0.953179**） |
| 逐 cell 重构误差 max（全体 / 被采样 cell） | **2.0468**（最大被丢弃 cell 的 trips）/ **5.68e-14**（精确） |

> **守恒口径说明（必读）**：`EF_ij = T_ij/N_ij`（沿用 6.2B 冻结定义）→ 被抽到 0 的 cell **没有代表个体、其 trips 不被承载**，故 `ΣEF = ΣT × OD coverage（trips 加权） = 438,266 < 459,794`。由于 7.5A 审计已证 **EF 不被 MATSim 消费**，`ΣEF` 只影响账面、**不影响仿真**；评价层主口径仍用与 S100c **相同**的 `SCALE = ΣT/N = 4.59794`（**名义需求相同 → 隔离采样规则效应**），并解析给出 raw-EF 敏感性口径 `SCALE_raw = ΣEF_sampled/N = 4.38266`（整体 ×0.95318）。

#### 2.24.4 ★预注册判据（跑前固定）

| 组 | ID | 判据 | 门槛 |
|---|---|---|---|
| 绝对（与 7.5A 的 C1–C7 同阈值） | **D1** | raw flow ratio 中位 ≈0.50 | \|Δ\|≤0.05 |
| | **D2** | scaled S100r/S200 比值中位 ≈1.00 | \|Δ\|≤0.10 |
| | D3 | scaled ±10% 内占比 | 仅报告 |
| | **D4** | scaled ±20% 内占比 ≥0.80 | 硬 |
| | **D5** | Pearson≥0.90 且 Spearman≥0.95 | 硬 |
| | **D6** | \|Δ(CATA÷SLIP) vs S200\| ≤0.05（08-09） | 硬 |
| | **D7** | 三窗口 \|Δ\|≤0.05 且同号 | 硬 |
| 机制（差分 vs S100c） | **M1** | raw ratio 比 S100c 更接近 0.50 | 硬 |
| | **M2** | scaled ±20% 内占比 ≥ S100c | 硬 |
| | **M3** | Pearson ≥ S100c | 硬 |
| | **M4** | \|Δ(CATA÷SLIP)\| ≤ S100c | 硬 |

**判决规则**：D 全 PASS → **`SAMPLING_RULE_WAS_THE_CAUSE`**（保留 100k，改用纯比例采样）；M ≥3 改善但 D 未全过 → **`PARTIAL_IMPROVEMENT`**；M <3 → **`SAMPLE_SIZE_DEPENDENT`**（此时 knee 扫描才有意义）。判据在 S100r 评价**之前**落盘：`preregistered_criteria_7_5b.json` + `STEP7_5B_PREREGISTRATION.md`。

#### 2.24.5 状态与产物

**状态**：✅ **全部完成**——设计 + 采样规则诊断 + S100r 人口管线（三阶段，新目录 `*_s100r`，冻结件零覆盖）+ config `verify_patch` PASS + 冒烟 2000×3it PASS + **S100r 全量跑通（100k × 20 it，171.20 min，exit=0，20 it 全落盘）** + 三方正式评价（判决 `PARTIAL_IMPROVEMENT`，D 0/6、M 3/4）；详见 **§2.24.6**。

**产物**：`reports/od_sample_7_5b/`（`STEP7_5B_DESIGN.md` + `sample_matrix_7_5b.csv` + `sampling_rule_diagnostics.json` + `sampling_rule_summary.csv` + `od_cell_sampling_rules.csv` + `s100r_build_summary.json` + `STEP7_5B_PREREGISTRATION.md` + `preregistered_criteria_7_5b.json`）+ `reports/matsim_population_6_2b_s100r/` + `..._connected_s100r/` + `reports/matsim_departure_6_3_3a_s100r/` + `reports/od_sample_7_5b/S100r_lam0p075_cap0p50/`。

#### 2.24.6 ★正式结果（S100r 跑通；判决 `PARTIAL_IMPROVEMENT`）

**S100r 全量**：100k × 20 it，`exit=0`，墙钟 **171.20 min**，20 迭代全落盘，`STATUS: PASS`。

> ⚠️ **运行期踩坑**：`--heap 12g` **不足**，进程在 it.2 / it.5 被**外部硬杀**两次（Java `exit=4294967295`、无 `hs_err`、无 stack trace、无 shutdown hook；物理内存 63.7 GB / 空闲 43.8 GB ⇒ 非内存争用）；**改 `--heap 24g` 后一次通过**（未生成 `hs_err`、GC 日志仅 71 KB）。**堆上限非模型参数，不改口径与可比性。**

**三方正式表（窗口 08-09，Σsim/Σobs，it.19）**

| 实验 | 采样规则 | N | f_cap | SCALE | Sim/Obs | WMAPE | GEH<5 | GEH<10 | Pearson | Spearman | CATA | SLIP | CATA/SLIP |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| S200 | `FLOOR_PLUS_1` | 200k | 1.00 | 2.29897 | 0.7070 | 0.5660 | 0.1389 | 0.2413 | 0.3800 | 0.5801 | 0.7137 | 0.6706 | 1.0642 |
| S100c | `FLOOR_PLUS_1` | 100k | 0.50 | 4.59794 | 0.8389 | 0.7090 | 0.1076 | 0.1875 | 0.3057 | 0.5376 | 0.8440 | 0.8108 | 1.0409 |
| **S100r** | **`PURE_TRIPS_PROP`** | 100k | 0.50 | 4.59794 | **0.5984** | 0.5837 | 0.1181 | 0.2101 | 0.3647 | 0.5351 | 0.5947 | 0.6191 | **0.9605** |

**预注册判据逐条**：D1 FAIL（raw 比中位 **0.4325** vs 0.50）、D2 FAIL（scaled 比中位 **0.8571**）、D3 —（±10% 内 **0.2533**，仅报告）、D4 FAIL（±20% 内 **0.4305**）、D5 FAIL（Pearson **0.9162** / Spearman **0.9410**）、D6 FAIL（|Δ(CATA÷SLIP)| **0.1037**）、D7 FAIL（三窗 −0.0799 / −0.1037 / −0.0921，同号但超阈）；**M1 PASS**（|Δ0.5| 0.0675 < 0.0799）、**M2 PASS**（0.4305 > 0.2648）、**M3 PASS**（0.9162 > 0.8557）、**M4 FAIL**（0.1037 vs 0.0233，**恶化 4.4×**）。
⇒ **D 0/6、M 3/4 ⇒ 判决 `PARTIAL_IMPROVEMENT`**：保底规则是残余偏差的**贡献来源之一**，但**不足以让 100k 达标**；采样规则与样本量**共同**作用，任一单独都不够。

**★两个机制发现（已由评价器 §8 固化，可复现）**

| # | 发现 | 证据 |
|---|---|---|
| 1 | 缺口是**全断面比例性收缩**，**不是断面归零** | S100c 与 S100r 的 raw 零流量断面数**同为 62 / 576（10.8%）**；S100c→S100r 的 raw 缺口 79,196 中，归零断面仅贡献 **794（1.00%）**，**99.00% 来自其余断面的等比收缩** ⇒ 「去掉保底会丢网络覆盖」**不成立** |
| 2 | 纯比例**系统性剔除长距离 OD 对** | 平均行程距离 it.0 / it.19：S200 **13,873.9 / 14,213.2 m**、S100c **14,521.0 / 14,922.7 m**、S100r **13,179.3 / 13,396.6 m**（**短 10.2%**）。重力模型下 `T_ij` 最小 ⇔ `c_ij` 最大 ⇒ 纯比例先删掉的正是**最长的 OD 对**，每条留存 trip 覆盖链路更少 ⇒ 断面流量 **−28.7%**，而需求质量（ΣEF）仅 **−4.7%**，**放大约 6 倍** |

**★待证假设（解释性，勿当结论）**：Sim/Obs 与「保底 agent 占比」**完全单调**——S100r **0%** → 0.5984；S200 **35.6%** → 0.7070；S100c **71.1%** → 0.8389。机制猜想：**MATSim 只 1:1 消费 agents，评价层只乘一个全局 `SCALE`** ⇒ 保底让大量小 `T_ij` cell 各得 ≥1 agent、**抬高 raw 链路流量**，单一 `SCALE` 无法校正这种**构成偏差**（只能校水平）。若成立，则 7.5A 的 raw 比 **0.5799 ≠ 0.5** 本身就是「保底占比随 N 变化」的症状（100k 71.1% vs 200k 35.6%），且 **0.50 恰夹在 S100c 0.5799 与 S100r 0.4325 之间** ⇒ 100k 的「非线性」**大部分可归因于采样规则而非样本量**。
⚠️ **但三点同时变动 N 与 f_cap，单调性不能单独证明该假设** → **唯一干净的判别实验 = 纯比例 @200k 对称参照**（7.5B 遗留的最大方法论缺口，**待用户裁定是否补跑**）。

**产物**：`STEP7_5B_REPORT.md`（8 节，含 §8 机制补充诊断）+ `sample_comparison_7_5b.csv` + `sample_roadcat_summary_7_5b.csv` + `sample_backtest_7_5b.csv` + `step7_5b_summary.json`（新增 `mechanism_diagnostics_section8`）；失败现场归档于 `_ABORTED_S100r_it2_20260916/`、`_ABORTED_S100r_it5_20260916/`。

---

### 2.25 Step 7.4.3 补充诊断 —— demand scale 在 08-09 的非单调回落机制（**本轮完成**；判决 `TIME_WINDOW_ARTIFACT_CONFIRMED`）

#### 2.25.1 ★要回答的唯一问题（用户裁定）

7.4.3 扫描里 08-09 单小时 `Sim/Obs(all)` 呈 **非单调**：f=1.00 → **0.7070**、f=1.10 → 0.7095、f=1.20 → **0.8601（峰）**、f=1.25 → **0.7599（回落）**；而算术参照 A 系列单调升到 0.8838。

用户要求：**先把「为什么 f=1.20 在 08–09 达到 0.8601 后 f=1.25 反而回落到 0.7599」解释清楚，再继续做 OD 空间结构和 λ 标定，避免把时间分配/拥堵饱和效应误判成 OD 参数效应。**

#### 2.25.2 判决

**`TIME_WINDOW_ARTIFACT_CONFIRMED`（判据 T1–T5 全部成立）**

> **f=1.20→f=1.25 的回落不是 OD 总量/需求参数效应，而是拥堵导致的时间重分配（AM 峰值被推出 08-09 测量窗）的窗口伪影。需求被完整投递，只是在时间上被摊开：单小时窗口看得见的部分变少了。**

| 判据 | 内容 | 结果 |
|---|---|---|
| T1 | 日总量 `ΣHRS0-24avg` 随 f 单调且 ≈ 正比于需求 | PASS |
| T2 | **窗口加宽到 07-11 后恢复单调且 ≈ 等比（决定性）** | PASS |
| T3 | 出发剖面跨档稳定（极差 ≤ 0.10 pp） | PASS |
| T4 | 无 agent 丢失 / 无 stuck（排除口径丢失） | PASS |
| T5 | 拥堵倍率与平均行程时长在 f=1.20→1.25 跳升 | PASS |

#### 2.25.3 ★决定性证据：窗口加宽（`Σ_links HRSx-yavg`，it.19）

| 窗口 | f=1.00 | f=1.10 | f=1.20 | f=1.25 | f1.25/f1.20 | 单调↑ |
|---|---:|---:|---:|---:|---:|:--:|
| **08-09** | 31,966,212 | 33,954,661 | 36,274,085 | 34,765,233 | **0.9584** | **否** |
| **07-09** | 59,414,995 | 63,855,728 | 68,332,693 | 67,014,597 | 0.9807 | **否** |
| **07-10** | 68,794,269 | 74,827,817 | 80,274,341 | 81,065,391 | 1.0099 | 是 |
| **07-11** | 71,434,513 | 77,470,751 | 84,073,924 | 87,469,205 | **1.0404** | 是 |
| **07-12** | 71,498,189 | 78,897,281 | 85,752,994 | 89,539,250 | 1.0442 | 是 |
| **0-24** | 71,498,189 | 79,776,857 | 86,176,094 | 89,708,946 | **1.0410** | 是 |

> 纯比例期望：`f1.25/f1.20 = 1.0417`、`f1.25/f1.00 = 1.2500`。
> **08-09 单小时** `f1.25/f1.20 = 0.9584`（**反而下降**）→ 非单调；**07-11 四小时窗 = 1.0404**（≈ 纯比例）→ 单调；**0-24 全日 `f1.25/f1.00 = 1.2547`（纯比例 1.2500，达成率 100.4%）** ⇒ **需求几乎 100% 被投递，无系统性吸收，只是峰值被摊到 09–12 时**。

#### 2.25.4 拥堵与时间分配的直读状态量（it.19）

| 场景 | f | agents | 未到达 | max stuck | 平均行程时长 | 平均行程距离 | 8-9 加权拥堵倍率 | 8-9 流量在 >3× 拥堵链路占比 | 09:00 前到达占比 | ΣHRS0-24 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| f1.00 | 1.00 | 200,000 | 0 | 0 | 25.76 min | 14,213 m | 2.007 | 7.3% | 77.21% | 71,498,189 |
| f1.10 | 1.10 | 220,000 | 0 | 0 | 32.26 min | 14,269 m | 2.314 | 8.1% | 74.33% | 79,776,857 |
| f1.20 | 1.20 | 240,000 | 0 | 0 | 33.24 min | 14,429 m | 2.314 | 8.6% | 73.26% | 86,176,094 |
| f1.25 | 1.25 | 250,000 | 0 | 0 | **38.99 min** | 14,549 m | **2.796** | 9.6% | **68.35%** | 89,708,946 |

#### 2.25.5 出发 vs 到达：机制完全在下游行进端

逐小时**出发**（car，括号为占该场景总出发的百分比）：

| 小时 | f1.00 | f1.10 | f1.20 | f1.25 |
|---|---:|---:|---:|---:|
| 07-08 | 97,421 (48.71%) | 107,194 (48.72%) | 116,897 (48.71%) | 121,863 (48.75%) |
| 08-09 | 102,579 (51.29%) | 112,806 (51.28%) | 123,103 (51.29%) | 128,137 (51.25%) |

逐小时**到达**（car）：

| 小时 | f1.00 | f1.10 | f1.20 | f1.25 |
|---|---:|---:|---:|---:|
| 07-08 | 68,529 | 73,794 | 79,313 | 79,131 |
| 08-09 | 85,898 | 89,732 | **96,501** | **91,743** |
| 09-10 | 34,567 | 39,654 | 43,208 | **48,466** |
| 10-11 | 10,663 | 9,552 | 13,233 | **22,228** |
| 11-12 | 343 | 4,117 | 5,965 | 7,651 |

> **出发占比跨档极稳（极差仅 0.035 pp = 3.5 bp）** → 出发时刻基本不漂移；而 **09:00 前到达占比在 f=1.20→1.25 移动 −4.91 pp（约 141× 于出发端）**，04/10/11 三个后续小时到达分别 **+12% / +68% / +28%** ⇒ **全部机制来自行进入端（行程时间变长）**，与出发时刻无关。
> 同时四档均为 `never_arrived = 0`、`max_stuck = 0` ⇒ **不存在 agent 丢失或滞留口径问题**。

#### 2.25.6 次要发现：08-09 单小时估计量本身不稳定

逐断面 `D(b)/D(a)` 的 `Σ比值 ÷ 需求比` = **超额系数**（1.0 = 正好等比）：

| 窗口 | 档位步 | 需求比 | Σ比值 | 超额系数 | 中位比值 | q05 | q95 | 落在[0.9,1.1]占比 |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| 08-09 | D01→D02 | 1.1000 | 1.0035 | **0.9123** | 1.0403 | 0.0597 | 2.9167 | 32.2% |
| 08-09 | D02→D03 | 1.0909 | 1.1953 | **1.0957** | 1.0639 | 0.2739 | 3.1425 | 34.4% |
| 08-09 | D03→D04 | 1.0417 | 0.8835 | **0.8482** | 0.9539 | 0.4288 | 1.4866 | 35.5% |
| 07-08 | D01→D02 | 1.1000 | 1.0227 | 0.9297 | 1.0848 | 0.7079 | 1.2849 | 44.4% |
| 07-08 | D02→D03 | 1.0909 | 1.1264 | 1.0326 | 1.0795 | 0.8621 | 1.5233 | 55.3% |
| 07-08 | D03→D04 | 1.0417 | 1.0105 | 0.9701 | 1.0230 | 0.7907 | 1.4021 | 65.3% |

> `07-08` 窗超额系数稳定在 **0.930–1.033**（近线性）；`08-09` 窗在 **0.848–1.096** 大幅摆动。
> 判决量 `sim = median(断面内匹配边 HRS8-9avg) × 2.29897` 是**单小时**统计量，强拥堵下边流量分布畸变会使中位数非线性移动 ⇒ **08-09 不宜作 demand scale 的水平判据**。

#### 2.25.7 ★阶段门控决定（用户裁定，2026-09-16）

1. **不补跑「纯比例 @200k」作为主线**；把 **200k 保留为正式标定样本** → 冻结 `N_sample = 200,000`、`f_cap = 1.00`。
2. **`λ` 不冻结；demand scale 不冻结；sampling rule 不重构**（维持 6.2B 保底规则）；**capacity 保持 1.00**（不作性能旋钮）。
3. **100k 暂不作为替代样本**（S100 / S100c / S100r 均已判不可替代）。
4. **下一阶段只追一个问题**：本步的非单调机制 —— **已澄清为时间窗伪影**；随后继续 OD 总量 / OD 空间结构 / λ，**先固定「水平口径」再动 OD 参数**，以免把时间分配/拥堵饱和效应误判成 OD 参数效应。
5. **顺序**：`7.5A 样本量初测 → 7.5B 采样规则诊断 → 【此处暂停】 → 回到 200k 正式标定 → OD 总量/demand → OD 空间结构 → λ → route choice / impedance（仅当前面仍解释不了时） → 最终 200k 验证`。
6. `PURE_TRIPS_PROP @ 200k`（`f_cap=1.00`）作为**方法论验证实验保留后置**（可真正解耦 N 效应与 sampling-rule 效应），**非当前主线必要条件**。

#### 2.25.8 产物与复现

```
python scripts/od/diagnose_demand_scale_nonmonotonic_7_4_3.py --iteration 19
```

产物：`reports/od_calibration_7_4_3/`（`STEP7_4_3_NONMONOTONIC_DIAGNOSIS.md` + `demand_scale_window_widening.csv` + `demand_scale_timing_profile.csv` + `demand_scale_congestion_state.csv` + `demand_scale_section_step_ratio.csv` + `demand_scale_nonmonotonic_diag.json` + `nonmonotonic_console.log`）。

> 口径：读 it.19 `linkstats` / `legHistogram` / `legdurations` / `traveldistancestats`；观测与断面对照沿用 7.3.6A Final Crosswalk；**零仿真、只读**；`λ` 固定 0.075（不冻结）、capacity 固定 1.00、`randomSeed=4711`。

---

### 2.26 Step 7.4.3-R 宽时间窗重新评价（**本轮完成**；zero simulation；★阻断发现：可观测窗上限 = 07-09）

回答的问题：7.4.3 的非单调（f=1.20 峰 → f=1.25 回落）在**更宽时间窗**下是否消失？宽窗能否作为 demand scale 的水平判据？

**★前置事实（决定窗口集合）**：LTA 原始 `TrafficFlow_Data.json` 的 `HourOfDate` **只有 7 与 8**
（38,083 + 37,816 = 75,899 行；1,311 LinkID；2025-11-01..11-30 共 30 天）。**不是脚本过滤** ——
7.1 冻结口径 `load_traffic()` 里的 `isin([7,8])` 与数据本身一致。
项目内其它动态源：`TrafficSpeedBands_v4.json`（143,787 行 / 56 MB）与 `EstimatedTravelTimes.json`（192 行）
**各只含 1 个 Timestamp → 单时刻快照，无时间序列**。
⇒ **可观测窗上限 = 07-09**；`07-10 / 07-11 / 07-12 / 00-24` **没有观测对象**，
其 Sim/Obs、WMAPE、GEH **无定义**（不是「缺失」）。本步骤按 Class O / Class S 分开处理，**不伪造 Sim/Obs**。

**窗口集合**

| 类 | 窗口 | hours | 观测列 |
|---|---|---|---|
| Class O（可观测） | `07-08` / `08-09` / `07-09`(= 冻结 `AM`) | [7] / [8] / [7,8] | `obs_7_8` / `obs_8_9` / `obs_am` |
| Class S（无观测） | `07-10` / `07-11` / `07-12` / `00-24` | [7..9] / [7..10] / [7..11] / [0..23] | 无 |

**估计量**：断面 `med_h = median(匹配 MATSim 有向边 HRS{h}-{h+1}avg)`；`scaled_h = med_h × SCALE(2.29897)`；
窗口 `sim_W = Σ_{h∈W} scaled_h`。与冻结 `calc_method` 完全一致 →
**断言 PASS：与 `demand_scale_backtest.csv` 逐值一致（n = 5,184，max|Δ| = 3.6e-12 < 1e-6）**。

**★两种聚合（用于拆分「时间迁移」与「空间重分配」）**

| 聚合 | 含义 | 对空间重分配 |
|---|---|---|
| `ALL` = 全网 **693,575** 条链路求和 | 近似「总车公里」 | **不敏感**（由构造近似随需求线性） |
| `MATCHED` = crosswalk 命中的 **3,037** 条标定链路求和 | **标定靶场自身的量级响应** | **敏感** |
| `section` = 断面中位数估计量（标定实际使用） | 与 `MATCHED` 忠实对应（比值 0.999–1.013） | 敏感 |

**★单调性判决（f=1.25 / f=1.20；纯比例期望 = 1.0417）**

| 窗口 | 可观测 | 形态 | 峰 f | ALL/期望 | MATCHED/期望 | section/期望 |
|---|---|---:|---|---:|---:|---:|
| `07-08` | 是 | **monotonic_up** | 1.25 | 0.9657 | 0.9644 | 0.9701 |
| `08-09` | 是 | non_monotonic | 1.20 | 0.9201 | **0.8493** | 0.8482 |
| `07-09` | 是 | non_monotonic | 1.20 | 0.9415 | 0.9026 | 0.9048 |
| `07-10` | 否 | non_monotonic | 1.20 | 0.9695 | 0.9250 | 0.9276 |
| `07-11` | 否 | non_monotonic | 1.20 | **0.9988** | 0.9478 | 0.9533 |
| `07-12` | 否 | non_monotonic | 1.20 | 1.0024 | 0.9394 | 0.9510 |
| `00-24` | 否 | non_monotonic | 1.20 | **0.9994** | **0.9333** | 0.9456 |

**缺口分解**：`ALL` 缺口 **0.0799（08-09）→ 0.0006（00-24）完全收敛**；
`MATCHED` 缺口 0.1507 → 0.0667，**只解释掉 55.7%**，残留约 **6.7% 与窗口无关**。

**★对 7.4.3-Diag 的修正（重要）**：7.4.3-Diag 的「需求近 100% 被投递」**只在全网总量口径成立**；
该量近似「总车公里」，由构造近似随需求线性，**对空间重分配不敏感**。
在**标定真正使用的 3,037 条主干链路**上，全日窗仍保留约 **6.7%** 缺口 ⇒ **时间窗伪影只解释约六成**。

**残差机制（候选，不判决）**：标定靶场在 f=1.20 **过量加载** —— 归一化到 f=1.00 后 `MATCHED` 在 00-24 窗
= D02 1.0806 / D03 **1.3332** / D04 1.2961，峰位 **D03 = 1.3332 远超名义 1.20**；
即「回落」主要是 **f=1.20 在标定断面上的一次超标冲高**，而非 f=1.25 的塌陷。
相符的行进端证据（7.4.3-Diag 已测）：f=1.20→1.25 平均行程时长 ×1.173、8-9 加权拥堵倍率 ×1.208、
平均行程距离 14,429→14,549 m（**绕行变长**）而标定子集流量 −2.8%
→ 指向 **ReRoute 下的路径替代 / 分配重分布**，而非单纯的时段推移。

**结论 / 动作项**
1. **换窗口不能消除非单调**：08-09 → 00-24 只解释约六成；
2. **07-11 不可作水平判据**：它**既无观测**（LTA 只有 h7/h8），**也不能**让标定靶场恢复单调；
3. 当前可用水平口径 = **最宽可观测窗 `07-09`**（= 冻结命名 `AM`），并**同时披露 08-09**；
   `08-09` 保留给**空间断面拟合**与 `CATA/SLIP` **结构比较**；
4. **数据动作项**：若要真正用宽窗做水平判据，需向 LTA 获取 **09:00 之后**的流量观测；
5. **优先级动作项**：`route choice` 应**提前**（OD 总量与空间结构均已不能解释该残差）
   → 建议下一步做**分配稳定性审计**（零仿真即可先做：比较 D01–D04 在标定断面上的流量构成/路径份额随 demand 的变化）；
6. 在完成 4/5 之前，**不要**依据 08-09 的 f=1.20 → 0.8601 选定 demand scale。

**复现**

```
python scripts/od/reevaluate_demand_scale_windows_7_4_3r.py --iteration 19
```

产物：`reports/od_calibration_7_4_3r/`（`STEP7_4_3R_REPORT.md` + `window_reevaluation_comparison.csv` +
`window_reevaluation_roadcat.csv` + `window_reevaluation_backtest.csv` + `sim_only_window_levels.csv` +
`window_monotonicity_verdict.csv` + `observation_window_availability.csv` + `step7_4_3r_summary.json` + `reeval_console.log`）

> 口径：读 it.19 `linkstats`（24 小时箱）；观测 7.1 冻结（**仅 h7/h8**）；crosswalk = 7.3.6A Final；
> **零仿真、只读**；未重跑 MATSim；`λ` = 0.075（不冻结）、capacity = 1.00、randomSeed = 4711。

---

### 2.27 Step 7.6A Official Car-Demand Accounting 官方汽车通勤需求会计（**本轮完成**；zero simulation；★判决 `CALIBER_GAP_DOMINATES`）

**目的**：回答「`ΣEF = 459,794`（MATSim car-trip equivalent）究竟占官方机动车通勤需求的多少」，并据此判断
「基准 `f=1.00` 宽窗总量仍不足」应归因于 **demand scale** 还是 **统计口径差**。**零仿真、只读**，从不启动 MATSim。

**★前置发现（决定全案）**：`TrafficFlow_Data.json` **没有车型字段**
（字段仅 `LinkID / Date / HourOfDate / Volume / StartLon / StartLat / EndLon / EndLat / RoadName / RoadCat`）
⇒ **「观测流量中有多少是小汽车」在本地数据上不可分解**。模态覆盖缺口只能用 Census 作 **外部参照** 界定，
不能从观测侧测量。这是本步最重要的数据结论。

**会计链条（逐层对账 L0–L5）**

```
Employed residents 15+ (居住侧)                2,177,456   ← Census 2020 T104/T133
Employed residents 15+ (工作地侧)              2,208,358   ← T4   （口径差 30,902 = 1.42%）
  ├─ 物理工作地 (03B.1 控制)                   1,935,235   87.63%   ← 实测一致 Δ = 1
  └─ 非物理承载（单列，不进道路 OD）              273,124   12.37%
       ├─ No Fixed Location for Work           177,588
       ├─ Works from Home                       70,800
       └─ Other Planning Areas/Outside SG        24,736
Usual mode of transport to work（11 方式）       2,177,456  →  Car Only 459,796
  ├─ Combinations of Public Transport          1,257,434   57.75%
  ├─ Car or Taxi/PHC（官方 T11 自带分组）          526,477   24.18%
  ├─ Other Modes（PCV / 货车 / 摩托 / 其他）        180,639    8.30%
  └─ No Transport Required                      212,907    9.78%
道路口径变体   V1 459,796 / V2 526,477 / V3 707,116   （占就业居民 21.12% / 24.18% / 32.47%）
MATSim car-trip equivalent（ΣEF，6.2B 实现）     459,794    （名义锚 459,796；Δ = 2 = 取整）
```

**★核心结论：口径差支配**

| 量 | 值 | 来源 |
|---|---:|---|
| 模态覆盖率 `V1/V3` | **0.6502** | 本步 L3 |
| 断面水平 `Sim/Obs`（MATCHED 07-09，f=1.00） | **0.6830** | 7.4.3-R（D01） |
| 二者之比 | **0.9520** | 推导 |

⇒ 两个量分属 **国家人-口径** 与 **断面流-口径**，是不同测度，但 **量级高度一致**：
**观测里「非小汽车」的那一部分，几乎正好填满模型断面流量的缺口。**
⇒ 隐含 demand scale **`f ∈ [1.0504, 1.4641]`**：下端 = V3 口径差解释全部缺口（**不需要加车**，模型已略高于可比口径）；
上端 = 0 口径差、缺口全算需求不足。**总量证据只能给出区间，不能识别单点。**

**★判决规则**：`f_lower = cov(V1/V3) ÷ SimObs(07-09, f=1.00)`；`< 1.10` ⇒ 口径差支配；
`1.10–1.30` ⇒ 混合；`> 1.30` ⇒ 需求缺口支配。实测 **1.0504 → `CALIBER_GAP_DOMINATES`**。

**★三项本地不可定量（必须外部数据，不给猜测值）**

| 项 | 状态 | 所需源 |
|---|---|---|
| 观测车型构成（小汽车占多少） | **不可分解**（观测无车型字段） | LTA 分车型交通量计数 |
| AM 峰占日通勤比重 | **不可标定**（Census 无 departure-time；6.3.3A 剖面由 TrafficFlow 自推 → 与靶场 **循环**） | LTA Household Travel Survey (HTS) |
| 平均载客率（人 → 车辆） | 无观测（现行隐含 `occ = 1.00`） | LTA 统计 / HTS |

**附带发现**

- `Works from Home`（工作地表 **70,800**）≠ 方式表 `No Transport Required`（**212,907**）：后者 **包含** 前者，
  差额 **142,107** 为其他不需出行者，两者不可互替。
- **载客率与模态覆盖方向相反**：若 `occ = 1.30`，V1 只对应 **353,689** 辆车 → 模型 **高估** 车辆 **23.08%**。
  二者必须同时处理，不能只挑一个有利的方向。
- **2025 稳健性**：GHS 2025 `Car Only` 占比 **21.18%** vs Census 2020 **21.12%** ⇒ 用 2020 锚 **不构成系统偏差**；
  但总量 2,356,000 vs 2,177,456（**+8.20%**），若以 2025 为标定年应做年际放大。

**★对后续路线的含义**

- 「总量不足」必须拆成三段：① 模态/载客率 **口径差**（≤ 34.98% / 反向 23.08%，靠 **数据口径对齐** 解决，**不是仿真**）；
  ② AM 峰 **时间分配**（不可定量）；③ 标定断面 **窗口无关残差 6.7%**（属 **空间结构 / 路径分配** → 7.6B / 7.6C）。
- ❌ **不要在口径未固定前再跑 demand scale 批量实验** —— 每档 `Sim/Obs` 同时混着口径差、载客率、时间分配
  三个未知量，扫出的曲线 **不可识别**。
- ❌ **不要把 `V3/V1 = 1.5379` 直接当 demand scale** —— 那等于让 **小汽车吸收出租车 / 摩托 / 货车 / 包车** 的流量，
  会人为制造拥堵；`f_cap = 1.00` 与 capacity = 1.00 保持。
- 下一步：**7.6B Assignment / Route Stability Audit（零仿真，复用 D01–D04 既有 linkstats）**，
  算 `R_cal = ΣQ_matched / ΣQ_all` 随 demand 的变化；并行做 **口径数据获取（动作项，非仿真）**。

复现：
```
python scripts/od/account_official_car_demand_7_6a.py
```
产物：`reports/od_calibration_7_6a/`（`STEP7_6A_REPORT.md` + `car_demand_accounting_layers.csv` +
`mode_split_official.csv` + `mode_split_crosscheck.csv` + `pa_car_share_official.csv` +
`workplace_pa_car_share_official.csv` + `special_workplace_buckets.csv` + `coverage_gap_decomposition.csv` +
`observation_coverage_audit.csv` + `step7_6a_summary.json` + `account_console.log`）

> 口径：Census of Population 2020 / GHS 2025 / LTA TrafficFlow（`08_TrafficCount`）；**零仿真、只读**；
> 未重跑 MATSim；`λ` = 0.075（不冻结）、capacity = 1.00、`N_sample` = 200,000（冻结）、`f_cap` = 1.00（冻结）。

---

### 2.28 Step 7.6B Assignment / Route Stability Audit 分配 / 路径稳定性审计（**本轮完成**；zero simulation；★判决 `UNCONVERGED_PERIOD2_LIMIT_CYCLE__CROSS_F_SIGNAL_BELOW_PHASE_NOISE`）

**问题**：7.4.3-R 把 demand scale 非单调的残差指向「ReRoute 下的路径替代 / 分配重分布」，
但**从未检验分配本身是否收敛**。本步骤零仿真回答三问：① 分配收敛了吗？
② 标定断面在全网车公里（VKT）中的份额 `R_cal` 是否随 demand 系统性变化？
③ f=1.20 → 1.25 的落差里，路径替代占多少？

**★先验事实（决定整个判读）**：D01–D04 的 config 全部为
`fractionOfIterationsToDisableInnovation = Infinity` + 唯一策略 `ReRoute`(weight 1.0) +
`planCalcScore.learningRate = 1.0` + `routingRandomness = 0.0`
⇒ **100% 的 agent 在 100% 的迭代里重新选路，且计划得分无指数平滑** ——
这是 **周期-2 极限环（route flip-flop）** 的标准配置组合。
故本步骤**不默认 it.19 已收敛**，而是把「迭代」当成一个显式维度审计。

**★一、周期-2 极限环（直接证据；窗口 00-24，收敛窗 it.10–19，单位 = 车公里）**

| 实验 | f | MATCHED 偶相位 | MATCHED 奇相位 | 周期均值 | **MATCHED 振幅** | ALL 振幅 | 放大 | it.19 相对周期均值 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| D01 | 1.00 | 4,394,944 | 4,465,272 | 4,430,108 | **1.59%** | 0.39% | 4.0× | −1.04% |
| D02 | 1.10 | 4,658,772 | 4,837,584 | 4,748,178 | **3.77%** | 1.34% | 2.8× | −0.22% |
| D03 | 1.20 | 4,780,698 | 5,887,389 | 5,334,043 | **20.75%** | 1.13% | **18.3×** | **+9.58%** |
| D04 | 1.25 | 4,856,980 | 5,714,396 | 5,285,688 | **16.22%** | 1.40% | 11.6× | **+7.50%** |

奇偶两列**从 it.0 起完全分离**（D03 奇 ≈5.7–5.96 M / 偶 ≈4.72–5.03 M），
**这不是噪声**。三点关键读法：
① **振荡在标定子集上被放大 14.8 倍**（全网总量只振荡 0.39–1.40%）⇒ 振荡是
**标定断面 ↔ 其余路网之间的路径替代**，不是总量波动；
② **振幅随 demand 单调放大**（1.59% → 3.77% → 20.75%），**峰值恰好与 Sim/Obs 峰值同址（f=1.20）**；
③ **it.19 在 f≥1.20 时落在其振荡高端**（+9.58% / +7.50%），而在 f≤1.10 时几乎居中（−1.04% / −0.22%）
⇒ **跨 f 比较被差分相位采样污染**。

**★二、冻结指标的周期均值重估计（08-09，主窗口）**

| 实验 | f | SimObs it.19 | SimObs 周期均值 | 偶相位 | 奇相位 | 相位振幅 | it.19 偏置 | 补齐到 1（it.19） | 补齐到 1（周期） |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| D01 | 1.00 | 0.7070 | **0.7505** | 0.7429 | 0.7582 | 2.05% | −5.80% | 1.4143 | 1.3324 |
| D02 | 1.10 | 0.7095 | **0.7127** | 0.6914 | 0.7340 | 5.98% | −0.45% | 1.4094 | 1.4030 |
| D03 | 1.20 | **0.8601** | **0.7647** | 0.6794 | 0.8501 | **22.33%** | **+12.47%** | 1.1627 | 1.3076 |
| D04 | 1.25 | 0.7599 | **0.7061** | 0.6467 | 0.7655 | 16.82% | +7.62% | 1.3160 | 1.4163 |

- **f=1.20 的 0.8601 峰值大幅回落**（0.8601 → 0.7647）；跨 f 极差由 it.19 的 **15.30%** 压缩到周期均值的 **5.87%**。
- 而 f≥1.20 的**相位振幅单独就有 16.8–22.3%** ⇒ **跨 f 信号 < 相位噪声**，
  **单迭代水平不可用于 demand scale 判决**。

**★★三、决定性检验：同相位（奇 / 偶）分别比较 —— 响应符号随采样相位改变**

| 指标 | 相位 | D01 (f=1.00) | D02 (f=1.10) | D03 (f=1.20) | D04 (f=1.25) |
|---|---|---:|---:|---:|---:|
| MATCHED 00-24 attainment | 偶 | 1.0000 | 0.9637 | 0.9065 | 0.8841 |
| MATCHED 00-24 attainment | 奇 | 1.0000 | 0.9849 | **1.0987** | 1.0238 |
| SimObs 08-09 attainment | 偶 | 1.0000 | 0.8462 | 0.7621 | 0.6964 |
| SimObs 08-09 attainment | 奇 | 1.0000 | 0.8801 | **0.9343** | 0.8076 |

**偶数相位里看到「越加车越差」（单调下降，峰在 D01），奇数相位里看到「f=1.20 最优」（峰在 D03）——
两者来自同一次仿真的样本。** 响应**符号**由采样相位决定，
这本身就证明：**该实验在方法上无法识别 demand scale。**

**★四、`R_cal`：标定断面承载的全网 VKT 份额**

| 实验 | f | R_cal(00-24) it.19 | 归一 | R_cal(00-24) 周期均值 | 归一 |
|---|---:|---:|---:|---:|---:|
| D01 | 1.00 | 0.06132 | 1.0000 | 0.06312 | 1.0000 |
| D02 | 1.10 | 0.05939 | 0.9685 | 0.05986 | 0.9483 |
| D03 | 1.20 | 0.06783 | 1.1061 | 0.06156 | 0.9753 |
| D04 | 1.25 | 0.06334 | 1.0330 | 0.05820 | **0.9220** |

- 标定链路只占全网链路的 **0.4379%**，却承载约 **6%** 的 VKT。
- 单迭代 R_cal 归一后非单调（峰值 f=1.20 → 1.1061）；**周期均值口径下变为接近单调的轻微下降**
  （1.0000 / 0.9483 / 0.9753 / 0.9220）⇒ 存在**方向正确的「流量离开标定断面」**（f=1.25 时 −7.8%），
  但**量级远小于相位振幅**，不足以单独解释任何东西。

**★五、重分布分解：MATCHED 与 NON-MATCHED 的增量对冲（相位翻转，窗口 00-24）**

| 实验 | f | ΔMATCHED（偶→奇） | ΔNON-MATCHED | 抵消比 |
|---|---:|---:|---:|---:|
| D01 | 1.00 | +70,327 | −346,859 | 0.20 |
| D02 | 1.10 | +178,811 | +881,040 | −0.20 |
| D03 | 1.20 | **+1,106,691** | **−2,088,348** | **0.53** |
| D04 | 1.25 | **+857,416** | **−2,132,046** | **0.40** |

⇒ 相位翻转时 **MATCHED 的增量被 NON-MATCHED 的等量减量对冲**，而**全网总量只动 1–2%**
⇒ **纯路径替代**，不涉及总量或时段迁移。这正是 7.4.3-R 的机制候选，**现被直接量化证实**。

**★六、逐链路秩稳定性与替代类别（it.18 ↔ it.19）**

| 实验 | f | 有流链路 | ρ(it18,it19) 全体 | ρ 标定子集 | **ρ top50 最高流** | MATCHED 承担 \|Δq\| 份额 |
|---|---:|---:|---:|---:|---:|---:|
| D01 | 1.00 | 237,247 | 0.8400 | 0.8972 | **0.9858** | 4.9% |
| D02 | 1.10 | 239,261 | 0.8274 | 0.8068 | **−0.5459** | 4.8% |
| D03 | 1.20 | 239,552 | 0.8139 | 0.7813 | **−0.2085** | 5.7% |
| D04 | 1.25 | 240,713 | 0.8092 | 0.7487 | 0.4651 | 5.1% |

- **D02/D03 里最繁忙的 50 条链路在相邻两代之间流量排序为负相关** —— 直接翻转，非缓慢漂移。
- 标定链路承担 \|Δq\| 的 **4.8–5.7%**（其链路占比 0.4379% ⇒ **12–13 倍超载**）。
- 替代类别：`matched` **5.7%** / `nonmatched_adjacent` 3.4% / `nonmatched_other` **90.9%**
  ⇒ 翻转**弥散在全网**，**不是**单一平行走廊的故事。
- 相邻迭代 ρ 全体仅 0.81–0.84（距收敛所需 ≫0.99 甚远）⇒ **分配未收敛**。

**★七、绕行与拥堵响应（周期均值口径）**

| 实验 | f | 绕行指数 | 拥堵倍率 ALL | MATCHED | NON-MATCHED | 8-9 过饱和份额(ALL) |
|---|---:|---:|---:|---:|---:|---:|
| D01 | 1.00 | 1.0000 | 1.631 | 1.273 | 1.664 | 0.00% |
| D02 | 1.10 | 1.0274 | 1.958 | 1.470 | 2.001 | 0.00% |
| D03 | 1.20 | 1.0288 | 2.145 | 1.546 | 2.197 | 0.00% |
| D04 | 1.25 | **1.0352** | 2.421 | **1.531** | 2.495 | 0.00% |

- 绕行指数单调上升（+3.5%）⇒ 单位需求走的链路变多（路径变长），与 7.4.3-Diag 一致但量级很小。
- **标定主干道（快速路）反而比全网其余部分畅通**（MATCHED 1.531 vs NON-MATCHED 2.495 @ f=1.25）。
- **8-9 过饱和份额恒为 0.00%**（无链路 `HRS8-9avg > CAPACITY`）⇒ 拥堵以**排队/存储**形式出现，而非流量越限；
  这也说明 `capacity` 在 f_cap=1.00 下**不是**当前拥堵的控制变量。

**★★判决：`UNCONVERGED_PERIOD2_LIMIT_CYCLE__CROSS_F_SIGNAL_BELOW_PHASE_NOISE`**（**20/20 校验 PASS**）

**对既有结论的修正**

| 既有结论 | 本步骤修正 |
|---|---|
| 7.4.3「f=1.20 峰 0.8601 → f=1.25 回落 0.7599」 | **部分为相位伪影**：周期均值把跨 f 极差由 15.30% 压缩到 5.87%；f=1.20 的 it.19 恰落在其振荡高端（**+12.47%**），被系统性抬高 |
| 7.4.3-R「残差指向 ReRoute 路径替代」 | **被直接证实**（相位翻转时 MATCHED 增量被 NON-MATCHED 等量对冲，全网总量仅动 1–2%） |
| 7.4.3-R「约 6.7% 与窗口无关的标定靶场缺口」 | **在周期均值口径下仍存活**，但其置信区间必须先由相位振幅给出；**单迭代无法把它与振荡区分开** |
| 「it.19 是收敛解」 | **不成立**。it.19 是周期-2 极限环的一个相位样本，在 f≥1.20 时位于高端 |

**动作项（按优先级）**

1. **★最高优先级（配置层，需重跑但代价明确）**：`fractionOfIterationsToDisableInnovation = 0.5 ~ 0.9`；
   把 `ReRoute` 权重降到 **0.10–0.20** 并引入 `ChangeExpBeta` / `BestScore`；
   给 `planCalcScore` 设 **`learningRate < 1`**。目标：把标定子集的周期振幅压到 **3% 以下**，
   使 Sim/Obs 的单迭代水平具备可辨识性。
2. **零仿真即可立即采用**：评价口径由「it.19 单点」改为
   **收敛窗（it.10–19）的奇偶相位均衡周期均值**（本步骤已证：跨 f 极差 **15.30% → 5.87%**）。
3. **不要**在收敛问题解决前再增加 demand scale 的 MATSim 跑次 —— 新增跑次只会扩大同一个相位带。
4. **可并行的数据动作项**（7.6A 已列）：LTA 分车型交通量计数 + HTS 出发时刻 ——
   这是把需求口径 `f` 从区间收敛到单点的唯一途径。
5. **7.6C（OD 空间结构 / 距离带）必须建立在周期均值口径上**，否则会被同一相位噪声污染。

复现：
```
python scripts/od/audit_assignment_stability_7_6b.py            # 全量（约 7 min，80 个 linkstats 只读）
python scripts/od/audit_assignment_stability_7_6b.py --reuse    # 复用缓存轨迹（约 1 min）
```
产物：`reports/od_calibration_7_6b/`（`STEP7_6B_REPORT.md` +
`assignment_iter_trajectory.csv` + `assignment_parity_decomposition.csv` +
`assignment_frozen_metric_by_iter.csv` + `assignment_cycle_mean_reevaluation.csv` +
`assignment_cycle_mean_frozen_metric.csv` + `assignment_rcal_share.csv` +
`assignment_reallocation_decomposition.csv` + `assignment_phase_reallocation.csv` +
`assignment_link_flip_profile.csv` + `assignment_substitution_classes.csv` +
`assignment_link_rank_stability.csv` + `assignment_same_parity_attainment.csv` +
`assignment_detour_congestion.csv` + `assignment_config_provenance.csv` +
`assignment_stability_summary.json` + `stability_console.log`）

> 口径：观测 7.1 冻结（仅 h7/h8）；仿真 `median(edges HRSx-yavg) × 2.29897`；
> crosswalk = 7.3.6A Final；randomSeed = 4711；`λ` = 0.075（不冻结）；capacity = 1.00；
> `N_sample` = 200,000（冻结）、`f_cap` = 1.00（冻结）；**零仿真、只读、未改任何参数**。

---

### 2.29 Step 7.6D Route-choice Stabilization 分配机制稳定化（**本轮：配置验证 PASS + 预注册完成；零仿真；正式 run 待批**）

**为何需要这一步**：7.6B 证明 D01–D04 的分配**从未收敛**，而是处于**周期-2 极限环（route flip-flop）**；
根因是**配置组合**而非任何数据问题。在此机制下继续判断 `λ` / demand scale / OD 空间结构，统计上都不干净。

#### 用户裁定（2026-09-16）

| 项 | 裁定 |
|---|---|
| ① 评价口径 | **采纳周期均值，但不简单「替代」 it.19** → **双口径并报**：Primary `Q̄_10:19`，Reference `Q_19` |
| ② route-choice | **执行，但先做「最小修复 + 稳定性预检」**，不一次改三个参数然后直接跑；先配置验证、再决定是否正式重跑 |
| ③ 7.6C OD 空间结构 | **暂缓**：分配还在震荡时研究距离带 / λ 会把 phase noise 误认为 OD 空间效应 |

**新排序**：`7.6A ✓ → 7.6B ✓ → 7.6D Route-choice stabilization ✓ → 7.6D-S 低样本稳定性筛查 ✓（判 `SCREENING_PASS`）→ `**`7.6E route-choice 正式冻结门（200k × 20 it，本步）`**` → 7.6F demand scale 重新评价 → 7.6C OD 空间结构 / 距离带 → λ / impedance → 最终 200k 验证`。

#### 最小修复（唯一变量，针对「学习过猛 + 持续创新」两机制）

| # | 参数 | 基线 | 修复后 | 针对机制 |
|---|---|---|---|---|
| 1 | `replanning.fractionOfIterationsToDisableInnovation` | `Infinity` | **`0.8`** | 持续创新（无收尾沉降阶段） |
| 2 | `replanning` 策略集 | `[ReRoute 1.00]` | **`[ReRoute 0.15, ChangeExpBeta 0.85]`** | 持续创新 + 无计划选择算子 |
| 3 | `scoring.learningRate` | `1.0` | **`0.5`** | 学习过猛（得分无指数平滑） |
| 4 | `routing.routingRandomness` | `0.0` | `0.0`（**保留**） | 确定性最短路（显式冻结） |

> **为何加 `ChangeExpBeta`**：`fractionOfIterationsToDisableInnovation = 0.8` 意味着**迭代 16 起禁用创新策略**；
> 若策略集里没有 plan-selection 算子，禁用创新后网络无法沉降。
> **为何不一次改三个参数直接跑**：否则知道「新配置更稳」却不知道是哪一项起作用（同 7.5A/7.5B 已暴露的可识别性问题）。

#### 配置验证（零仿真，**19/19 PASS**）

`scripts/od/prepare_routechoice_7_6d.py` 以官方 `fullConfig` 为基线生成，再施加最小 patch，并逐项断言：

| 校验组 | 内容 |
|---|---|
| V1（4 项） | 新策略集 == `[ReRoute 0.15, ChangeExpBeta 0.85]`、权重和 == 1.0、ReRoute 由 1.0 降至 0.15、**基线无任何 plan-selection 策略（复现 7.6B 根因）** |
| V2（3 项） | 三个修复标量逐一命中目标值 |
| V3（1 项） | 与基线 diff **仅 4 处**、越白名单零项（数值感知比较：`"1"` vs `"1.0"` 不计为差异） |
| V4（1 项） | `MUST_MATCH_BASELINE` **16 项逐值相同**（network / plans / seed / coordSystem / threads / qsim capacity / SpeedyALT / TTC / linkStats / networkRouteType / hermes capacity） |
| V5（9 项） | routingRandomness=0.0 / seed=4711 / qsim flow=storage=1.0 / lastIteration=19 / network 未换 / population 指向 6.3.3A / 中间迭代不写产物 / writeLinkStatsInterval=1 / DOCTYPE 存在 |
| V6（1 项） | XML 可解析且模块数 = 25 |

**冒烟预检 PASS**：2000 agents × 3 迭代，MATSim `using config_v2-reader` 解析通过、
`MultimodalNetworkCleaner` 零删除、`SpeedyALT` 构建成功、it.0 完成，
**无策略解析错误** ⇒ `ChangeExpBeta` 与 `fractionOfIterationsToDisableInnovation = 0.8` 均被正确接受。

#### ★ 预注册稳定性判据

```
A_W(X) = ( max_k X_k − min_k X_k ) / mean_k X_k            X ∈ {ALL, MATCHED, CATA, SLIP}
主判据（窗口 it.10–19，MATCHED）:  < 3% STABLE | 3–10% PARTIAL | ≥10% UNSTABLE
双口径并报：Primary Q̄_10:19（周期均值）、Reference Q_19（单点）
```

**★★ 统计量口径警示**：7.6B 报的「周期振幅」= `|even−odd|/mean`（仅相位分离），
而本步骤 `A` = `(max−min)/mean`（相位分离 **+ 窗内非交替漂移**）——**两者不是同一个量**。
D01 MATCHED：**`parity_gap_rel` 1.59% vs `A_10:19` 8.48%（5.3×）**，说明当前「周期-2」并不干净，
是**弱交替叠加在大幅非交替漂移之上**（偶相位内部极差 ≈ 5.0%、奇相位 ≈ 8.3%）。
⇒ 结论比 7.6B **更严峻**；后续引用「20.75%」必须说明那是 D03 的 `parity_gap_rel`。

#### 修复前基线（before，零仿真复用，不新增仿真）

| run | f_demand | `A` ALL | **`A` MATCHED** | `A` CATA | `A` SLIP | 判决 |
|---|---:|---:|---:|---:|---:|---|
| BASELINE_D01（= 7.4.2 E06） | 1.00 | 3.96% | **8.48%** | 10.14% | 8.93% | `PARTIAL` |
| REF_D02（7.4.3） | 1.10 | 2.71% | **11.10%** | 8.97% | 18.05% | `UNSTABLE` |
| REF_D03（7.4.3） | 1.20 | 1.51% | **23.25%** | 18.15% | 35.51% | `UNSTABLE` |
| REF_D04（7.4.3） | 1.25 | 2.32% | **20.32%** | 15.43% | 33.94% | `UNSTABLE` |

**四条读数**：① `ALL` 在所有 demand 档只有 1.51–3.96%，而 `MATCHED` 达 8.48–23.25% ⇒ **振荡集中在标定断面上**；
② `MATCHED` 振幅随 demand 放大且**峰在 f=1.20**（与 7.6B 「峰值与 Sim/Obs 峰值同址」交叉印证）；
③ `SLIP`（匣道）最不稳（最高 **35.51%**，约 `CATA` 的 2 倍）；
④ **即使最温和的 f=1.00 也只是 `PARTIAL`** ⇒ **当前机制下不存在任何稳定的 demand 档 ⇒ 不是 demand 选得不好，而是机制问题**。

#### 隔离与产物

**用户工程决定**：不修改任何现有 7.1 / 7.3.6A / OD / network / capacity 产物，
新配置与新输出全部落在**独立目录 `matsim_routechoice_7_6d/`**，旧结果完全保留。

| 路径 | 内容 |
|---|---|
| `matsim_routechoice_7_6d/STEP7_6D_PREREGISTRATION.md` | **预注册判据（跑前冻结）** |
| `matsim_routechoice_7_6d/README.md` | 机制 + 修复规格 + 运行方式 |
| `configs/config_R01_rc_min.xml` | 修复后正式 config（20 迭代） |
| `configs/config_R01_rc_min_smoke.xml` | 冒烟 config（3 迭代） |
| `routechoice_7_6d_config_provenance.csv` | 与基线逐参数 diff（**唯一权威差异表**） |
| `routechoice_7_6d_strategy_provenance.csv` | 策略集前后对照 |
| `routechoice_7_6d_config_validation.json` | 配置验证（19 项，机器可读） |
| `logs/` × `outputs/` | MATSim 日志与输出 |
| `audit/routechoice_stability_by_iter.csv` | 逐迭代 4 口径数值（缓存） |
| `audit/routechoice_stability_amplitude.csv` | 各 run × 各口径 × 各窗口的 `A` |
| `audit/routechoice_stability_dual_caliber.csv` | **双口径**（`Q̄_10:19` 主 / `Q_19` 参考） |
| `audit/routechoice_stability_summary.json` | 机器可读汇总 |

#### 运行计划

```
python scripts/od/prepare_routechoice_7_6d.py                 # 生成 + 验证（已完成，19/19 PASS）
python scripts/od/prepare_routechoice_7_6d.py --smoke 2000 --heap 8g   # 冒烟预检（已 PASS）
python scripts/od/prepare_routechoice_7_6d.py --run --heap 24g          # 正式 20 迭代（待批准；200k 必需 24g）
python scripts/od/audit_routechoice_stability_7_6d.py                    # 稳定性评价（零仿真）
```

**本步骤未修改任何模型参数**（配置验证阶段）；
`N_sample` = 200,000 / `f_cap` = 1.00 / capacity = 1.00 **冻结未变**；`λ` / demand scale **仍不冻结**。
> ⚠️ §2.29 的「正式 run 待批」已被用户裁定**改为先行低样本筛查** ⇒ 见 **§2.30 Step 7.6D-S**。

---

### 2.30 Step 7.6D-S 低样本(100k)稳定性筛查（**本轮完成；判 `SCREENING_PASS`**）—— route-choice 修复是否把 assignment 从不稳定压到稳定？

**用户裁定（2026-09-16 22:16）**：**不**直接跑 200k（~8–9 h），先做**更便宜且更有辨识力**的机制筛查。
本轮**不评价** demand scale / λ / OD 空间结构，只回答**唯一一个问题**：

> 新 route-choice 配置有没有让 assignment 从「不稳定」变成「稳定」？

#### 样本量：50k 不可行 → 改 100k（用户裁定）

| 项 | 值 | 说明 |
|---|---|---|
| 原定 | 50,000 | 用户初案 |
| **硬约束** | `ValueError: agents 50000 < positive OD cells 71136` | 6.2B `FLOOR_PLUS_1` 语义 = **每个正 OD cell ≥ 1 agent**；λ=0.075 正 OD cell **恒为 71,136** ⇒ **N < 71,136 在设计上不可行**（与目标值无关，不是慢） |
| **改选** | **100,000 @ `f_cap = 0.50`** | 用户裁定；**复用 `S100c_lam0p075_cap0p50` 冻结人口**（0 重建） |

**各样本量分配形态实测**（零仿真，同一 OD）：

| N | f_cap | 每 cell 最大 agent | 保底 cell 占比 |
|---:|---:|---:|---:|
| 71,136 | 0.35568 | **1**（完全退化） | 100.0% |
| 80,000 | 0.40000 | 9 | 88.5% |
| **100,000** | **0.50000** | 26 | 70.5% |
| 200,000 | 1.00000 | 114 | 41.5% |

（复现的 100k 形态 max=26 / 保底 70.5% 与 7.5B 实测一致 ⇒ 表可信。）

#### ★同 N 严格对照（边际成本为零）

`S100c` 已有**完整 20 迭代 linkstats**，且其 100k 人口与 config 均在盘 ⇒ 得到
「**同 N、同 f_cap、同采样规则、同 seed，仅 route-choice 不同**」的 before/after 对照，
辨识力高于 50k 的「绝对门槛判决」，且**无需重建人口**。

#### 最小修复（与 7.6D 完全一致，唯一变量 = route-choice 4 项）

`fractionOfIterationsToDisableInnovation` `Infinity`→**0.8**；策略集 `[ReRoute 1.00]`→**`[ReRoute 0.15, ChangeExpBeta 0.85]`**；
`learningRate` `1.0`→**0.5**；`routingRandomness` 保留 **0.0**。采样规则 `FLOOR_PLUS_1` **未重构**；`hermes` capacity **不缩放**（与 S100c 同构）。

#### 配置验证（零仿真，**25/25 PASS**）

`scripts/od/prepare_routechoice_7_6d_s.py`：含 **P0 显式断言 N ≥ 71,136**（下界守卫）、**P3 冻结件 mtime 9/9 未变**；
与基线**仅 7 处白名单差异**：`outputDirectory` / `runId` / `inputPlansFile`(→100k 剖面) / `qsim` flow+storage `1→0.5` /
`fractionOfIterationsToDisableInnovation` `∞→0.8` / `learningRate` `1.0→0.5`（`routingRandomness` 不变）。

#### 预注册判据（**任何运行之前冻结**）

| 口径 | 门槛 | 性质 |
|---|---|---|
| MATCHED | `A_10:19 < 3%` | 正式判据 |
| CATA | `A_10:19 < 3%` | 正式判据 |
| SLIP | `A_10:19 < 5%` | 正式判据 |
| `parity_gap_rel` | 无门槛 | **辅助诊断**（周期结构，**不**与 `A_10:19` 混称「周期振幅」） |

> 这是**稳定性筛查门槛，不是拟合优劣门槛**。`A_10:19` 是唯一正式判据。

#### 运行结果

```
run_id = S100k_rc_min | 100,000 × 20 it | f_cap=0.50 | --heap 24g
exit=0 | 33.20 min | linkstats 20/20 | RUN STATUS: PASS
```

#### ★判决：`SCREENING_PASS`（3/3 门槛全过）

| 口径 | S100c（100k，**修复前**） | S100k_rc_min（100k，**修复后**） | 相对 | 门槛 | 结果 |
|---|---:|---:|---:|---:|---|
| **MATCHED** | 5.84% | **0.71%** | **×0.12** | <3% | ✅ PASS |
| **CATA** | 4.31% | **0.76%** | ×0.18 | <3% | ✅ PASS |
| **SLIP** | 10.86% | **0.60%** | **×0.06** | <5% | ✅ PASS |
| ALL | 1.38% | 0.44% | ×0.32 | 仅报告 | — |
| `parity_gap_rel`(MATCHED) | 4.07% | **0.09%** | ×0.02 | 辅助 | — |

（对照参考：`BASELINE_D01` 200k 旧配置 MATCHED = **8.48%** → 修复后 100k 档 **0.71%**。）

#### ★★机制层证据：振荡不是「变小」而是**被消除**

逐迭代 `MATCHED` 流量（归一化到各自 `Q̄_10:19`）：

```
BASELINE_D01 (200k, 旧)  0.945 1.068 0.960 1.050 0.991 1.069 0.958 1.050 1.005 1.039
                         0.993 1.051 0.972 1.009 1.016 1.020 0.966 0.970 1.013 0.990  ← 永不衰减
REF_S100c    (100k, 旧)  0.938 1.083 0.995 1.022 0.978 1.026 0.990 1.010 1.001 1.006
                         0.969 1.015 0.988 1.021 0.971 1.016 0.999 1.022 0.972 1.027  ← 同上
S100k_rc_min (100k, 新)  0.911 0.932 0.948 0.958 0.966 0.974 0.980 0.985 0.989 0.992
                         0.995 0.998 0.999 1.000 1.001 1.002 1.002 1.001 1.001 1.001  ← 单调指数收敛
```

两个旧配置是**标准周期-2 极限环**（奇偶交替、无衰减趋势）；新配置是**教科书式单调收敛**，
it.13 起即稳定在 `1.000 ± 0.002`，**从 it.0 起就不存在奇偶交替**。

> ⚠️ **`A_full_00_19`(MATCHED) = 9.25% 不是振荡**：它是 **burn-in 瞬态**（it.0 = 0.911 ≈ 收敛值 −9%，
> 属从初始计划出发的正常沉降），与极限环的**本质区别**在于**是否单调**。基线 `A_full` = 12.30% **且**含持续交替。
> 判据只用 `A_10:19` 正是为了剔除这段瞬态。

#### 双口径并报（用户裁定 ①）

| 口径 | 修复前 S100c | 修复后 S100k_rc_min | 说明 |
|---|---:|---:|---|
| Primary `Q̄_10:19`(MATCHED) | 2,443,276 | **2,514,748** | it.10–19 周期均值 |
| Reference `Q_19`(MATCHED) | 2,510,011 | **2,517,251** | 单点 |
| `Q_19 vs 周期均值` | **+2.73%** | **+0.10%** | 修复后单点代表性大幅提高 |

#### 产物

| 文件 | 说明 |
|---|---|
| `scripts/od/prepare_routechoice_7_6d_s.py` | 7.6D-S 专用：下界断言 + 人口复用 + 25 项配置校验 + 预注册落盘 |
| `scripts/od/audit_routechoice_stability_7_6d.py --screening` | 按口径门槛判决 + S100c 同 N 对照 + 返回码 0/2/3 |
| `matsim_routechoice_7_6d/configs/config_S100k_rc_min.xml` | 正式 config（+`_smoke` 版） |
| `matsim_routechoice_7_6d/STEP7_6D_S_PREREGISTRATION.md` | 预注册判据（**运行前冻结**） |
| `matsim_routechoice_7_6d/routechoice_7_6d_s_config_validation.json` | 25/25 PASS 记录 |
| `matsim_routechoice_7_6d/audit/routechoice_stability_screening_7_6d_s.csv` | 按口径判决表 |
| `matsim_routechoice_7_6d/outputs/S100k_rc_min/ITERS/it.0..19` | 20 迭代 linkstats |

#### 结论与下一步

**机制修复确证有效** ⇒ 依用户裁定「**PASS → 再做 200k × 20 it 正式稳定化**」，
下一步已启动 ⇒ 见 **§2.31 Step 7.6E**。
**未进入 7.6C**；`λ` / demand scale 判决**仍不成立**（本轮不评价）。
**未修改** 7.1 / 7.3.6A / OD / network / capacity / S100c / S100r 任何冻结件。

---

### 2.31 Step 7.6E 200k 正式稳定化（**本轮完成；判 `STABILITY_PASS` 6/6 ⇒ route-choice 层正式冻结**）—— 200k × 20 it

**用户裁定（2026-09-17）**：基于 7.6D-S 的 `SCREENING_PASS`，**直接进入 7.6E**，不再做新的低样本试验，也暂不进 7.6C。理由三条：

1. **修复已有强证据**：同 N=100k、同 `f_cap=0.50`、同采样规则的严格对照下，MATCHED 振幅 5.84% → 0.71%，SLIP 10.86% → 0.60%，远低于预注册门槛；
2. **修复已改变机制性质**：从周期-2 极限环变为单调收敛（it.13 后 `1.000±0.002`）⇒ 继续纠结旧配置下 D01–D04 的非单调 demand 响应已无意义；
3. **200k 是最终冻结样本规模**：100k 只能证明「修复有效」，不能作为最终模型规模。

> **★7.6E 的分工**：本步骤**不**同时承担「找参数」与「找机制」。route-choice 已由 100k 筛查通过；
> **200k 只负责确认「规模提升后机制仍然成立」**。

#### 冻结不动（逐项，不得修改）

| 项 | 值 | 冻结依据 |
|---|---|---|
| 人口 `N` | **200,000** | 正式标定基准；已核 6.3.3A 冻结件 persons = **200,000** |
| 采样规则 | **`FLOOR_PLUS_1`** | 不重构（6.2B 原生；下界 = 正 OD cell 71,136） |
| `qsim.flowCapacityFactor` / `storageCapacityFactor` | **`1.00`** / **`1.00`** | 正式档冻结 |
| `λ` | **0.075** | 不冻结但本轮**不变动** |
| 7.3.6A crosswalk | `reports/od_final_calibration_crosswalk_7_3_6/final_calibration_crosswalk.csv` | 靶场冻结（MATCHED **3,037** / CATA **1,020** / SLIP **2,017**） |
| network | `reports/matsim_network/network_cleaned.xml.gz` | 冻结 |
| departure profile | `reports/matsim_departure_6_3_3a/population_lambda_0p075.xml.gz` | 冻结 |
| OD matrix | 6.2B `FLOOR_PLUS_1` 采样产物 | 冻结 |
| demand scale | **暂不调整** | 属 7.6F |

#### 唯一改变：route-choice 最小修复（与 7.6D / 7.6D-S 完全一致）

| 参数 | 基线（D01 / E06） | **7.6E（= 7.6D-S）** |
|---|---|---|
| `replanning.fractionOfIterationsToDisableInnovation` | `Infinity` | **`0.8`** |
| `replanning` 策略集 | `[ReRoute 1.00]` | **`[ReRoute 0.15, ChangeExpBeta 0.85]`** |
| `scoring.learningRate` | `1.0` | **`0.5`** |
| `routing.routingRandomness` | `0.0` | `0.0`（保留） |

其余一切逐参数不变 ⇒ 与基线 diff 仅 4 处（`outputDirectory` / `runId` + 2 个标量）。

#### ★★本步骤自带两组严格对照（零额外成本）

**（a）200k 同 N 单变量对照**（本步骤最大信息增益）：

| run | N | f_cap | 人口/网络/seed | route-choice | 角色 |
|---|---:|---:|---|---|---|
| **BASELINE_D01**（E06, 7.4.2） | 200,000 | 1.00 | 同 | 旧 | **200k 修复前** |
| **R01_rc_min**（7.6E） | 200,000 | 1.00 | 同 | 新 | **200k 修复后** |

⇒ D01 与 R01 **除 route-choice 4 项外完全一致**（同人口文件、同网络、同 seed 4711、同窗 08-09、同 crosswalk）
⇒ **200k 档的单变量 before/after**，对照边际成本为零。

**（b）跨规模一致性对照**：`S100k_rc_min`（100k, f_cap=0.50, 新）vs `R01_rc_min`（200k, f_cap=1.00, 新）
⇒ 若**都稳定**，则机制对样本量稳健。

#### 统计量定义（严格区分，不得混称）

```
A_10:19(X)        = ( max_{k∈10..19} X_k − min_{k∈10..19} X_k ) / mean
A_full_00_19(X)   = 同上但 k∈0..19        ← 含 burn-in 瞬态，仅报告，绝不作判据
parity_gap_rel(X) = | even_mean − odd_mean | / mean      （周期结构诊断，非判据）
Q̄_10:19(X)        = mean_{k∈10..19} X_k                  （Primary，用户裁定 ①）
Q_19(X)           = 单点                                  （Reference，用户裁定 ①）
Q19_over_Qbar(X)  = Q_19 / Q̄_10:19
sign_consistency  = #{k∈0..12 : Q_{k+1} ≥ Q_k − 0.002·Q̄}/13   （单调性，0.2% 容差）
```

口径：`ALL`(693,575) / `MATCHED`(3,037) / `CATA`(1,020) / `SLIP`(2,017)。
`never_arrived = Σdepartures_car − Σarrivals_car`、`max_stuck_car = max(stuck_car)`，
源 = `ITERS/it.19/R01_rc_min.19.legHistogram.txt`（与 7.4.3 同源同口径）。

> **★统计量纪律**：`A_10:19` = 正式判据；`parity_gap_rel` = 周期结构诊断；**两者不得统称「周期振幅」**。
> 7.6B 报的「20.75%」是 D03 的 `parity_gap_rel`（同档 `A_10:19` = 23.25%）；D01 二者为 **1.59% vs 8.48%（5.3×）**。
> **`A_full_00_19` 不可作判据**：100k 新配置的 `A_full` = 9.25% 纯属 burn-in 瞬态（**单调**）；
> 与极限环的本质区别是**是否单调**，不是振幅大小。

#### 预注册判据（**运行前冻结**，第一关 = 稳定性，不是拟合）

| # | 判据 | 阈值 |
|---|---|---|
| **G1** | 单调收敛 | `sign_consistency(MATCHED, it.0→13) ≥ 0.85` |
| **G2** | 收敛窗振幅（正式） | MATCHED `< 3%` **且** CATA `< 3%` **且** SLIP `< 5%` |
| **G3** | 无周期结构 | `parity_gap_rel < 1%`（MATCHED / CATA / SLIP） |
| **G4** | 单点代表性 | `\|Q19_over_Qbar − 1\| < 2%`（MATCHED） |
| **G5** | 无 agent 丢失 | `never_arrived = 0` **且** `max_stuck_car = 0`（it.19） |
| **G6** | 跨规模不恶化 | `A_10:19(200k) < 3%` 且 `A_10:19(200k) / A_10:19(100k) < 5` |

**6 项全部通过**才判 `STABILITY_PASS` ⇒ **route-choice 层正式冻结**；否则 `STABILITY_FAIL` ⇒ 暂停，
**不进入 7.6F / 7.6C**。`ALL` 与 `A_full_00_19` **仅报告**。
**不论 PASS / FAIL**：均**不选 demand scale**、**不评价 λ**、**不评价 OD 空间结构**。

#### 后续主线（用户裁定 2026-09-17）

```
7.6E  route-choice 正式冻结          ← 本步
  ↓
7.6F  重新评价 demand scale
  ↓
7.6C  OD 空间结构 / 距离带
  ↓
λ / impedance
  ↓
最终 200k 验证
```

#### 运行

```
run_id = R01_rc_min | 200,000 × 20 it | f_cap = 1.00 | --heap 24g
python scripts/od/prepare_routechoice_7_6d.py --run --heap 24g
python scripts/od/audit_routechoice_stability_7_6d.py --stability-7_6e --reuse
```

墙钟预估：参考 100k 实测 **33.20 min** ⇒ 约 **1–1.5 h**（★原估 8–9 h 已被 100k 实测推翻）。
评价器返回码：`0` = STABILITY_PASS ／ `2` = STABILITY_FAIL ／ `3` = NO_RUN。

#### 产物

| 路径 | 说明 |
|---|---|
| `matsim_routechoice_7_6d/STEP7_6E_PREREGISTRATION.md` | 预注册判据（**运行前冻结**） |
| `matsim_routechoice_7_6d/configs/config_R01_rc_min.xml` | 正式 config（200k × 20 it） |
| `matsim_routechoice_7_6d/routechoice_7_6d_config_validation.json` | 配置验证 19/19 PASS |
| `matsim_routechoice_7_6d/audit/routechoice_stability_7_6e.csv` | 逐口径判决表 |
| `matsim_routechoice_7_6d/audit/routechoice_stability_7_6e_by_iter.csv` | 逐迭代轨迹 |
| `matsim_routechoice_7_6d/audit/routechoice_stability_7_6e_summary.json` | 机器可读汇总 + 判决 |
| `matsim_routechoice_7_6d/outputs/R01_rc_min/ITERS/it.0..19` | 20 迭代 linkstats |

**本步骤未修改任何模型参数**（仅施加 route-choice 最小修复，与 7.6D-S 逐参数一致）；
**未触碰** 7.1 / 7.3.6A / OD / network / capacity / S100c / S100r 任何冻结件；
**未进入 7.6C**；`λ` / demand scale 判决**仍不成立**。

---


#### ★7.6E 结果（run 完成：`exit=0`，**84.41 min**，linkstats **20/20**，≈4.2 min/it）

**判决 `STABILITY_PASS` —— G1–G6 6/6 全过 ⇒ route-choice 层正式冻结。**

| # | 判据 | 阈值 | 实测 | 结果 |
|---|---|---|---|---|
| **G1** | 单调收敛 `sign_consistency(MATCHED, it.0→13)` | ≥ 0.85 | **1.000** | ✅ |
| **G2** | `A_10:19` | MATCHED `<3%`、CATA `<3%`、SLIP `<5%` | **1.00% / 1.01% / 0.97%** | ✅ |
| **G3** | `parity_gap_rel` | `<1%`（三口径） | **0.13% / 0.14% / 0.13%** | ✅ |
| **G4** | `\|Q19/Q̄_10:19 − 1\|` | `<2%` | **+0.19%** | ✅ |
| **G5** | 无 agent 丢失 | `never_arrived=0` 且 `max_stuck_car=0` | **0 / 0**（departures 200,000 = arrivals 200,000） | ✅ |
| **G6** | 跨规模不恶化 | `A(200k)/A(100k) < 5` | **1.40** | ✅ |

**四口径 `A_10:19`（修复前 200k D01 → 修复后 200k R01）**：

| 口径 | 修复前 | 修复后 | 相对 | `parity_gap_rel` 前→后 |
|---|---:|---:|---:|---|
| **MATCHED** | 8.48% | **1.00%** | ×0.12 | 1.59% → **0.13%** |
| **CATA** | 10.14% | **1.01%** | ×0.10 | 2.63% → **0.14%** |
| **SLIP** | 8.93% | **0.97%** | ×0.11 | 0.78% → **0.13%** |
| ALL | 3.96% | **0.51%** | ×0.13 | 0.39% → **0.06%** |

**双口径（用户裁定 ①）**：`Q̄_10:19`(MATCHED) = **4,567,962**；`Q_19` = **4,576,724**；`Q19/Q̄` = **1.0019**。
`A_full_00_19`(MATCHED) = **8.79%（仅报告；含 burn-in 瞬态，不是振荡）** —— 这正是判据只能用收敛窗 `A_10:19` 的原因（瞬态与极限环的区别是**是否单调**）。

**★★逐迭代 MATCHED 轨迹（归一化到各自 `Q̄_10:19`）—— 收敛形态已改变性质**：

```
BASELINE_D01 (200k 旧)  0.9454 1.0679 0.9605 1.0495 0.9907 1.0692 0.9581 1.0502 1.0053 1.0388 ... 0.9896  ← 奇偶交替、永不衰减
S100k_rc_min (100k 新)  0.9112 0.9320 0.9479 0.9580 0.9659 0.9745 0.9797 0.9851 0.9890 0.9921 ... 1.0010  ← 单调指数收敛
R01_rc_min   (200k 新)  0.9169 0.9345 0.9457 0.9564 0.9648 0.9716 0.9772 0.9816 0.9859 0.9900 ... 1.0019  ← 单调指数收敛
```

**★跨规模可复现性极强**：新配置在 100k 与 200k 上的归一路径几乎重合（it.0 = 0.9112 vs 0.9169；it.19 = 1.0010 vs 1.0019）
⇒ 该收敛形态是**机制签名**，不是规模效应或噪声。

**★一个必须报告的结构性副产物（仅记录，不作 demand 判决）**：收敛过程**单调地把流量搬到标定断面** ——
MATCHED 从 it.0 的 `0.9169·Q̄` 升到 it.19 的 `1.0019·Q̄`（**+9.28%**），同时 ALL 从 `1.0374·Q̄_ALL` 降到 `0.9990·Q̄_ALL`（**−3.70%**），两者**反单调**；100k 上完全同形（**+9.85% / −3.78%**）。
⇒ 新配置的收敛解在标定断面上比 D01 极限环中心**高约 +3.1%**（`Q̄` 4,430,108 → 4,567,962）。
**这会改变 Sim/Obs 的水平，但本步按裁定不评价拟合**（7.6E 只回答稳定性；Sim/Obs 属 7.6F）。

**产物**：`audit/routechoice_stability_7_6e.csv`（汇总一行）、`routechoice_stability_7_6e_by_iter.csv`（逐迭代四口径绝对值）、
`routechoice_stability_amplitude.csv`（三档 × 四口径 + `A_pre_05_09`/`A_conv_10_19`/`A_full_00_19` + `parity_gap_rel` + 双口径 + `slope`）、
`routechoice_stability_dual_caliber.csv`。评价器零仿真、只读，`--stability-7_6e` 返回码 `0 = STABILITY_PASS` / `2 = STABILITY_FAIL` / `3 = NO_RUN`；本轮内部校验 **5/5 PASS**。

**`λ` / demand scale 判决仍不成立**（本轮明确未评价）；**未进入 7.6C**。下一步 = **7.6F 重新评价 demand scale**（分配底座已冻结）。

### 2.32 Step 7.6F-0 新稳定分配底座上的 demand = 1.00 基准重算（**本轮完成；零仿真只读；校验 20/20 PASS**）—— 第一次有资格讨论 demand scale

**授权与纪律**：7.6E 判 `STABILITY_PASS`（G1–G6 6/6）⇒ **route-choice 层正式冻结** ⇒ 7.6B 时代的禁令
「route-choice 未稳定 ⇒ demand scale 不可评价」**正式解除**。但**不能**把旧 D01–D04 的 Sim/Obs
简单乘一个修正因子：7.6E 改的是 **assignment dynamics（分配动力学）**，不是需求本身。
用户裁定把 7.6F 拆两层：**7.6F-0 零仿真基准重算（本轮）** / **7.6F-1 仅在必要时补跑 D02–D04**（3 × ~85 min）。

**设计（只回答一个问题）**：demand = 1.00 时，R01 稳定分配解对应什么**新的 MATCHED Sim/Obs 水平**？
`N=200,000` / `f_cap=1.00` / `λ=0.075` / 7.3.6A crosswalk / cleaned network / OD / departure **全部冻结**；
**唯一变量 = route-choice（已在 7.6E 冻结）**。**不选 demand scale、不评价 λ、不评价 OD 空间结构。**

#### 1) ★ 新基准点（R01，demand = 1.00）

| 口径 | 值 |
|---|---:|
| **Sim/Obs(08-09, MATCHED)** — Primary `Q̄_10:19` | **0.8590** |
| Sim/Obs(08-09) — Reference `Q_19` | 0.8603 |
| Sim/Obs(AM 07-09) — Primary | 0.7665 |
| CATA / SLIP_ROAD / CATA/SLIP | 0.8717 / 0.7889 / **1.1050** |
| WMAPE / GEH<5 / GEH<10 | 0.6310 / 0.1163 / 0.2257 |
| Pearson / Spearman | 0.3365 / 0.5836 |
| `Q̄_10:19`(MATCHED, ΣHRS0-24avg) / `Q_19` | 4,567,961 / 4,576,724 |
| 隐含 demand 倍率（`1/Sim/Obs`，**仅指示，非判决**） | **1.1642** |

#### 2) ★★ 机制分解：旧分配层 vs 新分配层（固定 demand = 1.00）

**(a) 200k 同 N 单变量**（同人口 / 同网络 / 同 seed / 同 crosswalk，**仅 route-choice 不同**）

| 量 | 旧配置 D01 | 新配置 R01 | 变化 |
|---|---:|---:|---:|
| Sim/Obs(08-09) — Primary `Q̄_10:19` | 0.7506 | **0.8590** | **+14.43%** |
| Sim/Obs(08-09) — Reference `Q_19` | 0.7070 | 0.8603 | +21.68% |
| `Q̄_10:19`(MATCHED, ΣHRS0-24avg) | 4,430,108 | 4,567,961 | **+3.11%** |

**(b) 100k 同 N 单变量**（跨规模复核）

| 量 | 旧配置 S100c | 新配置 S100k | 变化 |
|---|---:|---:|---:|
| Sim/Obs(08-09) — Primary | 0.8169 | **0.9639** | **+18.00%** |
| Sim/Obs(08-09) — Reference | 0.8389 | 0.9652 | +15.05% |
| `Q̄_10:19`(MATCHED, ΣHRS0-24avg) | 2,443,276 | 2,514,747 | **+2.93%** |

⇒ 两规模**同向（均大幅上移）、量级接近（+14.4% vs +18.0%）** ⇒ **机制签名**（非规模偶然）。

#### 3) ★★ 为什么不能用「×(1+δ) 修正因子」平移旧曲线 —— 本步给出定量反证

- 「断面流量位移」(`Q̄_10:19`(MATCHED), ΣHRS0-24avg) = **+3.11%**
- 「Sim/Obs 位移」(08-09, Primary) = **+14.43%**
- **两者相差 4.6×** ⇒ 断面流量位移与 Sim/Obs 位移**不是同一个数**。机制是**空间重分配**而非等比缩放
  （MATCHED it.0→it.19 **+9.28%** 而 ALL **−3.70%**，两者**反单调**）。把后者当可乘因子施加到 D02–D04，
  会把**分配层效应**混进**需求响应**。

#### 4) ★★ 旧 demand 响应谱（D01–D04，统一 Primary 口径重算）：**不可辨识**

| f_demand | Sim/Obs Primary | Reference(it.19) | 相位偏移(it19/均值−1) | CATA | SLIP | CATA/SLIP | `A_10:19`(MATCHED) |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 1.00 | 0.7506 | 0.7070 | −5.81% | 0.7559 | 0.7216 | 1.0475 | 8.48% |
| 1.10 | 0.7129 | 0.7095 | −0.47% | 0.7098 | 0.7295 | 0.9730 | 11.10% |
| 1.20 | 0.7655 | 0.8601 | **+12.35%** | 0.7631 | 0.7790 | 0.9795 | **23.25%** |
| 1.25 | 0.7068 | 0.7599 | +7.51% | 0.6962 | 0.7651 | 0.9099 | 20.32% |

- 旧曲线**非单调**、内部极差仅 **0.0587**，而四点极限环振幅均值 **0.1579** ⇒ **信噪比 0.372 < 1**
  ⇒ 判决 **`LEGACY_CURVE_UNINFORMATIVE`**。
- **新基准点 0.8590 高于旧谱全部四点（最高 0.7655）** ⇒ 旧 demand 扫描（f=1.00→1.25）**从未达到
  新底座在 f=1.00 单独达到的水平**，整条扫描被机制伪影吞没。
- `it.19` 相位偏移最高达 **+12.35%（D03）**，与 7.6B 记录的「+12.47%」一致 ⇒ 旧「demand 非单调」
  确认是**相位伪影**。

#### 5) 结论与下一步

- **本步产出 = 新底座上 demand = 1.00 的正式基准点 `0.8590`**，**取代旧 D01** 作为后续
  demand-scale 分析的参照（旧 D01 的 0.7070 是极限环相位样本，不可再用）。
- **「结合既有 D01–D04 给出约束区间」这条路径已封闭**（旧曲线不可辨识）⇒ 若确需 demand 响应信息，
  只能**在新底座上重建** = **7.6F-1**（D02/D03/D04 × 新 route-choice，各 ~85 min，合计 ~4.25 h）。**本轮未启动。**
- **本步不选 demand scale**：`1.1642` 仅为**指示量**。7.6A 的「三项本地不可定量」
  （观测车型构成 / AM 峰占比 / 载客率）**仍未解决**，其中载客率方向相反。
- **未改动** 7.1 / 7.3.6A / OD / network / capacity / population / route-choice 任何冻结件；**未进入 7.6C**。

**产物**：`reports/od_calibration_7_6f/` 下 `demand_scale_7_6f_0_backtest.csv`（逐断面 14 = 7 run × 2 口径）、
`demand_scale_7_6f_0_roadcat_summary.csv`、`demand_scale_7_6f_0_comparison.csv`（run × caliber × window）、
`demand_scale_7_6f_0_decomposition.csv`（★机制分解）、`step7_6f_0_summary.json`、`STEP7_6F_0_REPORT.md`；
另有 `_cycle_linkstats/`（7 个 run 的收敛窗周期均值 linkstats，可复用）。
**校验 20/20 PASS**：含 **C1/C2 逐位重现 7.4.3 的 D01 `it.19` Sim/Obs = 0.707041（08-09）/ 0.682991（AM）**，
以及 **C3 七个 run 的 `Σ(cycle-mean HRS0-24avg | MATCHED)` 与 7.6D/7.6E 审计逐位一致**
（R01 4,567,962 / D01 4,430,108 / D02 4,748,178 / D03 5,334,043 / D04 5,285,688 / S100c 2,443,276 / S100k 2,514,748）。

**★口径辨析（易错）**：稳定性审计的 `Q̄_10:19` / `Q_19` 用 **ΣHRS0-24avg**；Sim/Obs 用 **HRS8-9avg** —— **不混用**。
**


### 2.33 Step 7.6C OD 空间结构诊断（**本轮完成；零仿真只读；判 `OD_STRUCTURE_PARTIAL`，校验 23/28**）—— 冻结 OD 的「形状」是否可信

**授权与纪律（用户裁定 2026-09-17）**：**先 7.6C（零仿真、不改模型、不选 demand scale、不选 λ），再决定是否投入 7.6F-1 的 3 次正式仿真**。前置 = 7.6E `STABILITY_PASS` 6/6（route-choice 层冻结）+ 7.6F-0 新基准 `Sim/Obs(08-09)` Primary **0.8590**。**保留原则**：**不得把 demand 倍率解释成 `1/0.8590 = 1.1642`**（仅指示量，非结论）。**未启动 MATSim、未改任何参数、未触碰** 7.1 / 7.3.6A / OD / network / capacity / 6.2B 人口。

**本步只回答一个问题**：冻结 OD 的**形状（shape）**是否可信？—— 与**绝对规模（scale）**问题**刻意解耦**。

#### 1) Part 1 — OD 距离结构（归一化，不做总量判断）

| 口径 | mean | p10 | p25 | **p50** | p75 | p90 | p95 | p99 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 自由流网络距离 (km) | 12.64 | 4.08 | 7.10 | **11.67** | 16.97 | 22.03 | 25.89 | 34.75 |
| AM 行程时间 (min) | 18.21 | 7.94 | 12.14 | **17.49** | 23.42 | 29.22 | 32.93 | 41.53 |

| 分带 (km) | 0–2 | 2–5 | 5–10 | 10–15 | 15–20 | 20–30 | 30–40 | 40+ |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 需求份额 | **2.34%** | 11.94% | **26.34%** | 25.86% | 18.70% | 12.31% | 2.24% | **0.26%** |
| 带内集中比 (d/p) | 1.698 | 1.506 | 1.252 | 1.056 | 0.808 | 0.635 | 0.941 | 1.011 |

- **短/中/长**：≤5 km **14.28%** / 5–15 km **52.20%** / >15 km **33.52%**；域内 0.98%；>30 km 2.51%；>40 km 0.26%。
- **距离衰减单调**（B6 12.31% ≥ B7 2.24% ≥ B8 0.26%，且 B8<2%）⇒ **S2 PASS**。
- **★采样偏差 = 0.00 pp**（八个分带 realized agents 与 OD 矩阵**逐带一致**，最大偏差 1.1e-14 pp）⇒ **6.2B 的 OD→agent 实施无距离选择性偏差** —— 结构性排除「保底采样剔除长距离 OD」这一 7.5B 疑点。
- **AM 时间分带 vs Census T10**：模型 0–15min 份额 38.04% vs 普查 14.15%（比 2.69）、60+ min 0.006% vs 9.34% —— **跨口径（T10 = 全方式 + 全天 + 含公交等待），仅记录形状方向，不可作模型错误证据**。

#### 2) Part 2 — 空间集中 / 分散 + ★★ 缺口的空间结构（**本步核心**）

| 层级 | 量 | Gini | top1 | top10 | top20% |
|---|---|---:|---:|---:|---:|
| Subzone | `P_i` 生产 | **0.677** | 2.90% | 17.75% | 67.27% |
| Subzone | `A_j` 吸引 | 0.438 | 1.39% | 13.09% | 48.45% |
| PA | `P_i` | 0.621 | 7.57% | 53.82% | 58.04% |
| PA | `A_j` | 0.553 | 14.68% | 52.87% | 55.36% |

- OD cell：**密度 0.6454**（71,136/110,224）、Gini **0.680**、**top-10% cell = 50.56%**、max cell 401.69、中位 2.47。
- **生产端比吸引端更集中**（`P_i` 0.677 vs `A_j` 0.438）⇒ 符合「居住聚居 + 就业多中心」的**预期方向**。
- **0 个 `|z|>5` 异常吸收区** ⇒ **S6 PASS**。
- **Table118（剔 15 个非物理格，220 物理格）：中位 |份额残差| 0.0026 / P95 0.0095** ⇒ **S5 PASS**（门槛 0.02 / 0.10）。

**★★ 缺口（0.8590）不是处处均匀偏短**：

| Region | 断面 | obs | 池化比 | **正流比** | sim=0 | 零流 obs 占比 | 相对偏差 |
|---|---:|---:|---:|---:|---:|---:|---:|
| **EAST** | 133 | 282,363 | **0.582** | 0.624 | 15 | 6.70% | **−0.322** ❌ |
| CENTRAL | 112 | 438,057 | 0.790 | 0.882 | 6 | 10.38% | −0.080 |
| WEST | 180 | 411,015 | 0.880 | 1.003 | 27 | 12.30% | +0.024 |
| NORTH | 72 | 161,125 | 1.067 | 1.093 | 4 | 2.38% | +0.243 |
| **NORTH-EAST** | 77 | 219,192 | **1.158** | 1.182 | 2 | 2.02% | **+0.348** ❌ |

| 径向 | 断面 | 池化比 | 正流比 | sim=0 | 相对偏差（全/正流） |
|---|---:|---:|---:|---:|---:|
| **radial_in**（进中心） | 164 | **0.612** | 0.783 | **39** | **−0.288 / −0.162** |
| circumferential（环向） | 154 | 0.936 | 0.962 | 8 | +0.090 / +0.029 |
| radial_out（出中心） | 256 | 0.976 | 0.999 | 7 | +0.136 / +0.068 |

- **区域最大相对偏差 0.348 > 0.25 ⇒ S4 FAIL**；**剔除零流断面后 0.3325 ⇒ 仍 > 0.25（S4b FAIL）** ⇒ **区域不均不是零流断面造成的，是真实空间结构成分**。
- **定向系统性偏差**：**指向中心方向被系统性低估**（radial_in −29% 全 / −16% 正流），离开中心方向不偏；CATA 0.872 / SLIP 0.789（同向）。
- **局部最差**：R2 5–10 km radial_in **0.277**；R4 15–20 km radial_in 0.611（15 个零流）；**R5 20 km+ radial_in 13/13 断面全部零仿真流量**。
- **PA 级**：低估集中在**东部走廊**（HOUGANG 0.110 / TUAS 0.115 / KALLANG 0.228 / PIONEER 0.417），高估集中在**中心商业/中区**（ORCHARD 2.409 / OUTRAM 2.157 / BUKIT TIMAH 2.001）⇒ 与 Region 级**互为独立证据**。
- **★覆盖 vs 真实缺口必须分开**：**54 个断面 `sim=0` 但 `obs>0`，承载 8.14% 观测**；若算进池化比会把**未被路网覆盖的观测**误算成**模型低估**。全局 0.8590 → 剔零流 **0.9351**（约 7.6 pp 属覆盖缺口）。

#### 3) Part 3 — 路由前 OD ↔ 路由后断面 一致性

| 阶段 | 值 | 相对冻结 OD |
|---|---:|---:|
| 冻结 OD Σ`T_ij` | 459,794.0 | 0.0 |
| MATSim 人口（样本） | 200,000 agents | −56.50% |
| 经 `expansion_factor` 还原 | 459,793.999993 | **−1.5e-11** ✅ |
| 尺度恒等 `N × SCALE` | 459,794.0000000001 | **+2.2e-16** ✅ |
| ⚠️ 守卫：`Σ(agent.od_trips)` 原始值 | 4,326,638.56 | +8.41 ❌ **绝不可与 OD 总量比较** |

- **S1 PASS**。**唯一正确的守恒检验是 `Σexpansion_factor == 459,794` 与 `N×SCALE == 459,794`**（agent 文件按 agent 重复 cell 值，`Σod_trips` **不是**人口总量）。
- **detour**：planned 12,642.4 m；per-agent 实走 it.0→it.19 13,873.9 → **14,045.8 m** ⇒ **detour 1.111**（**S7 PASS**，区间 1.00–1.35）；per-agent plans 加权 1.0683；收敛前后仅 +1.24%。
- **VKT 独立互证**：planned 5,812,919 km；linkstats 全天代理 **6,456,072 km** ⇒ 比 **1.1106 ≈ detour 1.111**（两条独立链路同一结论）。分出发 Region detour：EAST **1.101** > NORTH 1.092 > NE 1.065 > CENTRAL 1.053 > WEST 1.051。
- **重分配定位（it.0→it.19）**：全天箱 ALL **−3.70%** / MATCHED **+9.23%**；08-09 ALL −0.48% / MATCHED **+12.82%** ⇒ **独立重现 7.6E 机制签名**（空间重分配而非缩放）。

#### 4) 预注册判据与判决

| 判据 | 内容 | 实测 | 结果 |
|---|---|---|---|
| S1 | 质量守恒 `|ΣEF−459,794|<1e-4` 且 agents==200,000 | 7e-6 / 200,000 | ✅ |
| S2 | 距离衰减 B6≥B7≥B8 且 B8<0.02 | 12.31/2.24/0.26% | ✅ |
| S3 | 短带主导 `share(B1..B3)>0.55` | **0.4062** | ❌（**门槛为通用先验**，不进判决集合） |
| **S4** | 各 Region 相对偏差 max < 0.25 | **0.348**（正流 0.3325） | ❌ |
| **S5** | Table118 物理格 中位<0.02 且 P95<0.10 | 0.0026 / 0.0095 | ✅ |
| **S6** | `|z|>5` 异常吸收区 == 0 | 0 | ✅ |
| **S7** | 加权 detour ∈ [1.00, 1.35] | 1.068（1.111 另一口径） | ✅ |

**判决（脚本内置，仅用 S4–S7）= `OD_STRUCTURE_PARTIAL`**（3/4 通过）。

> **关于 S3**：门槛 0.55 来自通用先验（假定短途主导）。实测「0–10 km 40.6% / ≤15 km 66.5% / 均值 12.6 km」对一个 **50 km 尺度的岛国 + car-only 通勤**并不异常（汽车通勤本就比全方式更长）。S3 **不进入判决集合**，仅登记为**门槛标定问题**，**不得据此判结构异常**。

#### 5) 结论与下一步

- **结构可信三条**：**OD 形状与普查一致**（Table118 中位残差 0.0026）；**无异常吸收区**；**路由可信**（detour 1.068–1.111 且 plan 与 linkstats **独立互证**，质量守恒到浮点精度）。
- **必须直视一条**：**`0.8590` 缺口不均匀且含真实空间结构成分** —— EAST −32% / NE +35%、**radial_in −29% vs radial_out +14%**、**R5 radial_in 13/13 零流**、东部走廊低估 / 中心商业高估；剔零流后全局升到 0.9351 但区域偏差仅降到 0.333。
- ⇒ **`0.8590` 不能当作一个"干净的规模因子"**；在补掉结构项之前直接做 demand-scale 扫描，会把**空间结构缺口修正**误读成**需求规模响应**。
- **下一步（对应决策树，须用户裁定）**：(i) 视结构"基本合理" → 进 **7.6F-1**（冻结 R01 底座补跑 f=1.10/1.20/1.25，~4.25 h）；(ii) **先消化 7.6C 标记的结构项**（零流断面覆盖 / radial_in 系统性低估 / 东部走廊 vs 中心）再谈规模；(iii) 其他。
- **禁止**：盲目补跑 D02–D04（旧谱 `LEGACY_CURVE_UNINFORMATIVE`）；把 `1/0.8590 = 1.1642` 当 demand scale 结论。

#### 6) 产物与复现

- 脚本：`scripts/od/diagnose_od_spatial_structure_7_6c.py`（`--out` / `--skip-plans` / `--force-plans`）；**运行 79.5 s**；**200k plans 解析 53.2 s**，缓存 `_agent_realized.parquet` 后复跑数秒。
- 产物目录：`reports/od_structure_7_6c/`（summary.json + 距离统计/分带/短中长 + T10 对照 + 采样偏差 + 集中度 + 边际/吸收异常 + Table118 残差 + 六张缺口分解表 + 断面地理归属 + 守恒链/逐带实走/分区域 detour + 重分配 + plans 缓存 + `STEP7_6C_REPORT.md`）。

### 2.34 Step 7.6C-1 异常归因追踪（**本轮完成；零仿真只读；判 `MIXED_COVERAGE_AND_RESIDUAL_STRUCTURE`，判据 5/5、校验 6/6**）—— 覆盖/归属伪影 vs 真实结构

**授权与纪律（用户裁定 2026-09-17）**：`7.6C-1 → 7.6F-1`（**不是** `7.6C → 7.6F-1`）。专查 7.6C 暴露的两个高集中异常：**(a) R5/radial_in 的 13/13 零流断面**；**(b) EAST-CENTRAL vs NORTH-NORTH-EAST 区域反向**。**零仿真；不改 7.1 / 7.3.6A crosswalk / OD / network / capacity / `attraction_v2`；不选 demand scale、不评价 λ；判据跑前冻结。** 特别纪律：**不要因为 R01 已得 0.8590 就把 demand 倍率解释成 `1/0.8590 = 1.1642`**（仅指示量）。

**Layer 1 — 零流断面全链路归因**

| 机制 | 断面数 | 观测 veh/h | 判读 |
|---|---|---|---|
| `CROSSWALK_TWIN_ORPHAN` | **31** | 46,049.5 | 匹配边三窗口全零 + 多为有向孤儿；60 m 内有**同名/同走廊的有流平行链**（平均 28.6 m） |
| `DIRECTION_MISMATCH` | **13** | 59,144.0 | 匹配边**跨双车道方向混合**；断面统计量取中位 ⇒ 被未使用方向拉塌为 0（反向边常载 700–3,900 veh/h） |
| `WINDOW_ARTIFACT` | **8** | 12,207.5 | 部分匹配边在 `HRS7-8avg` / `HRS0-24avg` 有流、`HRS8-9avg` 为 0 ⇒ 中位塌陷 |
| `GENUINE_UNROUTED` | **2** | 5,816.0 | 全零 + 有向孤儿 + 最近有流链 **≥60 m**（最接近"真缺"） |
| **合计** | **54** | **123,217.0** | = **8.1373%** 观测 |

**★13 个 R5/radial_in 断面（聚焦集）**：**全部位于 WEST REGION（TUAS / PIONEER）**，道路为 AYE ×8 / PIE ×3 / JALAN AHMAD IBRAHIM / UPPER JURONG ROAD，`d_cbd` 20.1–24.3 km，观测合计 **28,604.5 veh/h**。⇒ 这不是普遍的"外环入城"问题，而是**高度局域化于最西端工业区的路网表征问题**。

- 匹配边 **47 条**（`motorway` 15 / `motorway_link` 32）：**正向 `HRS7-8avg`/`HRS8-9avg`/`HRS0-24avg` 有流数全为 0**；**反向 `HRS8-9avg`/`HRS0-24avg` 有流数亦全为 0** ⇒ **47/47 三窗口 × 正反向全零**。
- **拓扑**：**43/47 为有向拓扑孤儿**（from-node 无人到达 且 to-node 无人离开），**0/47 两端均连通**；对照 20,000 条**全天有流**链路：in-reachable **0.987** / out-departable **0.991**，而聚焦集仅 **0.021 / 0.064**。⇒ **链路存在于仿真网络中（47/47 在 linkstats 内），但整整一天无人使用** —— **既非时间窗伪影、亦非方向伪影**。
- **但走廊是活的**：每个断面 **400 m 邻域**内有 **1,559 – 39,762 veh/h**（`HRS8-9avg` 合计，`HRS0-24avg` 最高 80,808），高流链常与断面**同名**（AYE / PIE / JALAN AHMAD IBRAHIM / Tuas Road）⇒ **交通存在，只是落在相邻平行链上**。

**★泛化（54 个零流断面）**：最近有流链 **≤30 m 36/54（66.7%）**、**≤60 m 52/54（96.3%）**、**≤100 m 54/54（100%）**；**同路名**有流链存在 **50/54**。

**★覆盖修正的反事实区间（仅指示量，非修正）**

| 变体 | 全局 `Sim/Obs` | 偏置 |
|---|---|---|
| matched（7.6F-0 实际） | **0.8586** | 基准 |
| repair: nearest flowing link（60/100/150 m） | 0.8152 / 0.8168 / 0.8205 | **下偏**（横街） |
| **repair: best-direction median（POST-HOC）** | **0.8906** | 保守 |
| 7.6C 正流口径（剔 54 断面） | **0.9351** | 覆盖上限读数 |
| repair: same-name flowing max（150/400 m） | 1.0430 / **1.0646** | **上偏**（取 max） |

⇒ 修正后全局落在 **≈ [0.89, 1.06]**，7.6C 的 **0.9351 正落区间内** ⇒ **"0.8590 → 0.9351 的跳升可被正式解释为测量/覆盖伪影"**。⚠️ 这些替代值**不是修正量**，**不得**当作"真实 Sim/Obs"。

**★但 graded 缺口对修正稳健（本步最重要否证）** —— 两种变体下排序均不变：

| 分组 | matched | same-name-max（上界） | best-direction（保守） |
|---|---|---|---|
| CENTRAL REGION | 0.790 | 0.931 | 0.876 |
| **EAST REGION** | **0.582** | 0.720 | **0.622** |
| WEST REGION | 0.880 | 1.094 | 0.880 |
| NORTH REGION | 1.067 | 1.284 | 1.067 |
| **NORTH-EAST REGION** | **1.158** | 1.560 | 1.158 |
| `radial_in` | **0.612** | 0.865 | **0.634** |
| `circumferential` | 0.936 | 1.130 | 0.956 |
| `radial_out` | 0.976 | 1.158 | 1.022 |

⇒ **硬零流是覆盖伪影，但"EAST/CENTRAL 偏低 + radial_in 偏低"是真实的、稳健的结构信号。**

**Layer 2 — EAST ↔ CENTRAL 流向拆解**

- **OD 侧**：EAST→CENTRAL **45,228.9**（占全 OD 9.84%）vs CENTRAL→EAST **9,550.5**（2.08%）。**定向不对称 0.2112 落在其余居住→CBD 块的 [0.1044（NE）, 0.3089（WEST）] 区间内** ⇒ 早高峰郊区→CBD 远大于反向是**结构性预期**，**无证据支持"OD 方向错误"**。距离带剖面平滑单调（EC 峰在 10-15 km 占 38.9%；CE 长尾更厚，20+ 占 21.7%）。
- **吸引量侧**：Table 118（剔 15 个非物理桶，220 个物理格）**中位 |share 残差| 0.0026 / P95 0.0095**，7.6C 异常吸收区 **0 个** ⇒ **无证据支持"吸引量错误"**，**不改 `attraction_v2`**。
- **路径侧（200k 实走路径，全网 706,554 链分类）**：EAST→CENTRAL 实走路径 **`radial_in` 占比 0.6425**、`radial_out` 0.1619、`circ` 0.1956，**EAST 入城走廊链次/出行 = 99.20**；CENTRAL→EAST 则以 **`radial_out` 0.5885** 为主（入城走廊仅 10.60）⇒ **路径层方向完全正确，没有"把本该进入东部的 OD 导向其他走廊"**。分带看 EC 的 `radial_in` 占比随距离单调下降（0.71→0.46），符合几何直觉。

⇒ **EAST 低估的成因 = ④（本步新增）细粒度链路归属 + 断面中位统计口径**，**不是** ①吸引量、②OD 方向、③路径改道。

**★可复用方法（本步新增两条）**

1. **零流断面必须做"有向拓扑可达性"检验**：判定 `sim=0` 是"真无车"还是"匹配到无人使用的孤儿边"，只需两步 —— ① 用**全网有流链路**构建 `arrive-node` / `depart-node` 集合，检验匹配边两端是否落入；② 找**最近的有流平行链**（分"任意"与"同路名"两档）。正常链路 in/out 可达率 ≈ 0.99，孤儿边 ≈ 0.02–0.06，**分离度极大、判据极硬**。
2. **断面统计量的口径脆弱性（中位数陷阱）**：本项目断面 `sim = median(匹配边 HRS8-9avg)` ⇒ 一旦 **≥50% 匹配边落在 router 未使用方向**（`DIRECTION_MISMATCH`）或落在无流窗口，**中位即塌为 0**，与真实需求无关。任何"断面级比值"结论都必须先做**匹配边级的方向/窗口构成审计**。

**预注册判据（运行前冻结）**：T1（47/47 三窗口 × 正反向全零）✅ / T1b（可达性 ≪ 参照）✅ / T2（≥90% 零流断面 60 m 内有平行有流链，实测 **96.3%**）✅ / T3（EC 不对称 ∈ 同类区间）✅ / T4（Table118 中位<0.02 且 P95<0.10）✅ / T5（修正后 `radial_in` 仍 < `circ` 且 < `radial_out`）✅ ⇒ **6/6**。

**Key docs**
- 报告：`reports/od_anomaly_trace_7_6c_1/STEP7_6C_1_REPORT.md`
- 汇总：`.../od_anomaly_trace_7_6c_1_summary.json`
- 脚本：`scripts/od/audit_anomaly_trace_7_6c_1.py`（`--force-routes`）

---

### 2.35 Step 7.6C-2 Calibration Target Integrity Gate 校准靶场完整性门控（**本轮完成；零仿真只读；判 `TARGET_MARGINAL_COARSE_ONLY`，判据 7/10**）—— 当前 7.3.6A frozen crosswalk 是否仍有资格做 demand scale 的绝对识别？

**授权与纪律（用户裁定 2026-09-17）**：**不启动 7.6F-1**，先做本门。原因：7.6C-1 发现的不是普通模型残差，而是**校准靶场本身存在可识别的链路归属问题**，会直接污染 demand scale 的绝对标定。**零仿真；不改 crosswalk、不改 OD、不改 λ、不改 network/capacity/7.1/7.3.6A；不选 demand scale、不选 λ、不启动 MATSim。**

**门控问题**：在已知 **8.14% 观测量**受 crosswalk/归属伪影影响的情况下，当前 frozen target 是否还有资格做 **demand scale 的绝对识别**？

**三口径（按用户规定）**

| 口径 | 定义 | 用途 |
|---|---|---|
| `FROZEN` | 全部 576 断面池化 `Sum(sim)/Sum(obs)` | **主口径，不能擅改** |
| `POSITIVE_ONLY` | 仅 `sim>0` 断面池化 | **敏感性口径** |
| `BEST_DIRECTION` | `max(median(正向 f89), median(反向 f89)) × SCALE` | **误差边界，不作正式靶场** |
| `MATCH_NEAREST_LOWER` / `MATCH_SAMENAME_UPPER` | 最近有流链 / 同名有流最大（@400 m） | 外包络（探究，不作靶场） |

为保证 `Delta_target` 只反映**断面排除效应**而非定义变化，`FROZEN` 与 `POSITIVE_ONLY` 采用**同一函数形式**（池化比）；`FROZEN` 的另一种定义（逐断面比的 obs 加权均值）与之**逐位相同**（0.8589732）。

**★断面集口径澄清（本轮新发现）**：7.3.6A crosswalk = **576 断面／574 primary candidate／3,015 条 primary 去重匹配链（全 crosswalk 3,037）**；而 7.6C 的 `section_geography.csv` **只覆盖 574 个 primary 断面**（缺 `190339 YIO CHU KANG ROAD`、`195768 PAN ISLAND EXPRESSWAY`，两者 obs/sim 均 > 0），因此 **7.6C-1 的 repair-bounds CSV 内部 `dropna` 后按 574 计算**，与其自身“anchor”行（576）相差 **4.06e-4**（0.8585675 vs 0.8589732）。本步**主口径统一取 576 全口径**，并**分开复现 574 子集**（交叉校验 **7/7 全中**）。

**★核心量**

```
Delta_target = Q_POSITIVE_ONLY - Q_FROZEN = 0.9350621 - 0.8589732 = 0.076089 = 7.609 pp
```

| 口径 | Q | f\* = 1/Q |
|---|---|---|
| `FROZEN` | 0.8589732 | 1.16418 |
| `POSITIVE_ONLY` | 0.9350621 | 1.06945 |
| `BEST_DIRECTION` | 0.8909674 | 1.12238 |

⇒ **f\* 识别区间 = [1.06945, 1.16418]**，宽度 **`Delta_f_target` = 0.09473**。外包络 `0.8205206 .. 1.0645964`（24.41 pp 宽，探究性）。

**★信噪比判定（复用项目自己的正式判据：SNR < 1 ⇒ 不可用于推断）**

| 7.6F-1 阶跃 | Δf | SNR = Δf / Delta_f_target | 判定 | 需要的 ε |
|---|---|---|---|---|
| 粗档 1.10→1.20 | 0.10 | **1.056** | 可用（勉强） | ≥ 0.947 |
| 细档 1.20→1.25 | 0.05 | **0.528** | **不可用** | ≥ 1.895 |

⇒ **靶场不确定性与粗档 demand 增量同量级**。在 8-9 过饱和份额恒 0%（无容量反馈）下 ε ≈ 1 是物理预期，故**细档不可识别**。

**★网格位置诊断（对 7.6F-1 的直接后果）**

`Sim/Obs(f, caliber) = Q_caliber × f^ε`（ε = 1 参考）：

| f | FROZEN | POSITIVE_ONLY | BEST_DIRECTION | 口径一致 | 越 1.0 的口径数 |
|---|---|---|---|---|---|
| 1.00 | 0.8590 | 0.9351 | 0.8910 | 是 | 0/3 |
| 1.05 | 0.9019 | 0.9818 | 0.9355 | 是 | 0/3 |
| **1.10** | 0.9449 | 1.0286 | 0.9801 | **否** | **1/3** |
| 1.15 | 0.9878 | 1.0753 | 1.0246 | **否** | 1/3 |
| 1.20 | 1.0308 | 1.1221 | 1.0670 | 是 | 3/3 |
| 1.25 | 1.0737 | 1.1688 | 1.1115 | 是 | 3/3 |
| 1.30 | 1.1167 | 1.2156 | 1.1559 | 是 | 3/3 |

- 建议网格 `[1.10, 1.20, 1.25]` **未跨越** f\* 区间（下界 1.06945 低于 1.10）；
- **f = 1.10 落在区间内部 ⇒ 结论随口径而变（口径分歧）**；
- `1.20` 与 `1.25` 均在区间之上且口径一致（全部越 1.0）⇒ **3 次跑只买 2 个不同区制**。

**★网格重排建议**（判据：最小间距 ≥ `Delta_f_target` = 0.09473，且必须跨越 f\* 区间）

| 候选网格 | 跑数 | 最小间距 | 间距 ≥ Delta_f_target | 跨越区间 | 可接受 |
|---|---|---|---|---|---|
| `1.00 / 1.10 / 1.20` | 3 | 0.10 | 是 | 是 | **是** |
| `1.05 / 1.15 / 1.25` | 3 | 0.10 | 是 | 是 | **是** |
| `1.10 / 1.20 / 1.30` | 3 | 0.10 | 是 | 否 | 否 |
| `1.00 / 1.05 / 1.10 / 1.15 / 1.20 / 1.25` | 6 | 0.05 | 否 | 是 | 否 |

**★Delta_target 的空间分布（池化）**：WEST **+0.1234**（Q 0.8796→**1.0030**，剔零后已过平衡）、CENTRAL **+0.0916**（0.7903→0.8819）、EAST **+0.0418**（0.5824→0.6242）、NORTH +0.0260、NORTH-EAST **+0.0238**（1.1579→1.1817）；径向：`radial_in` **+0.1717**（0.6116→0.7834）、`circ` +0.0257、`radial_out` +0.0229。**靶场不确定性主要来自 WEST/CENTRAL 与 `radial_in`，而 EAST 的亏损并非由其造成**。

**★结构可分性（决定 7.6C/7.6C-1 结构结论是否被污染）**：Planning Region 跨度（`POSITIVE_ONLY`）**0.5576** / `Delta_target` **0.0761** = **7.33×**（门槛 ≥ 5）⇒ **结构结论不受靶场不确定性污染**；EAST 相对亏损 −0.3220 是 `Delta_target` 的 **4.23×**。

**★稳健性**：改用 **574 子集**，`Delta_target` = **7.619 pp**、`Delta_f_target` = 0.09493、SNR 粗 **1.053** / 细 **0.527** ⇒ **全部结论不变**。

**判决 `TARGET_MARGINAL_COARSE_ONLY`**：**不是** `TARGET_ADEQUATE_FOR_ABSOLUTE_SCALE`（细档 SNR 0.528 < 1、f = 1.10 口径分歧、网格未跨越区间）；**也不是** `TARGET_INADEQUATE`（粗档 SNR 1.056 ≥ 1，且三口径**方向一致**：f\* > 1，需上调）。⇒ **7.6F-1 可进入，但性质必须降级**：读出的是「**带靶场不确定性的粗档 demand 响应关系**」，**不是**「绝对 demand scale」。

**★硬约束（逻辑链完整性）**：「发现校准靶场存在可修正伪影」**≠**「已允许修改冻结靶场」；后者必须**另立版本（如 7.3.6A-b）、另留证据链**。本步**不得**把 `0.9351` 升格为新主靶场，**不得**用 `0.8590` 或其倒数 `1.1642` 反推 demand scale。

**分支**：`7.3.6A Frozen Target` → `7.6C-1` 发现 comparator artifact → **`7.6C-2` 本步 = `TARGET_MARGINAL_COARSE_ONLY`** → （粗档可读）`7.6F-1` 降级为粗档响应 + 网格重排；若不可接受则 → 新建 crosswalk 修复实验（7.3.6A-b）。

**产物**：`reports/od_target_integrity_7_6c_2/STEP7_6C_2_REPORT.md`；汇总 `.../od_target_integrity_7_6c_2_summary.json`；表 `target_integrity_crossvalidation.csv` / `target_step_snr.csv` / `target_response_grid.csv` / `target_grid_placement.csv` / `target_grid_recommendation.csv` / `target_uncertainty_localisation.csv`；脚本 `scripts/od/audit_target_integrity_7_6c_2.py`（import 冻结模块 `bt` / `d76` / `a761`，**不复制公式**）。

---

### 2.36 Step 7.6F-1 入场准备 — 稳定底座上的**粗档** demand-response 曲线（**入场准备完成：67/67 PASS；★机制门已解除、2026-09-17 20:19 正式点火 → 见 §2.37**）

> **用户裁定（2026-09-17，逐字要点）**：正式进入 **7.6F-1**，但采用修正后三档
> `f = 1.05 / 1.15 / 1.25`（理由：分别落在 7.6C-2 的粗略识别区间 `[1.069, 1.164]`
> 的**下方 / 内部附近 / 上方**，信息利用率高于原 `1.10/1.20/1.25`）。
> 执行时继续严格冻结：route-choice = `R01_rc_min`、`N = 200,000`、`f_cap = 1.00`、
> λ = 0.075（**本轮仅保持不变，不作评价**）、7.3.6A frozen crosswalk 仍为**正式主靶场**、
> MATCHED 为主口径、`Q̄_10:19` 为主 / `Q19` 为参考、EAST / `radial_in` 作为**已知空间残差**
> **不通过调 demand 主动压平**、**不把 `POSITIVE_ONLY` / `BEST_DIRECTION` 升格为正式标定靶场**。
> 最终输出核心**不是**「哪个 factor 最好」，而是建立
> `f_demand → Q_MATCHED → Sim/Obs` 的**稳定响应关系**，并同时报告 frozen target 不确定性。
> **★在没有明确启动指令前，不启动新的 MATSim 仿真。**
> —— **该启动指令已于 2026-09-17 20:17 给出（「物理加车」路径，见 §2.37）。**

#### 1) ★★ 机制门（**已在启动前确认并解除**，否则设计自相矛盾）

用户冻结清单同时给出 `N = 200,000` 与 `f_demand = 1.05/1.15/1.25`，**二者不是同一个量**：

| 量 | 值 | 性质 |
|---|---:|---|
| 采样基准 `N`（= `SCALE` 锚） | **200,000** | 冻结，**不改** |
| 被仿真的 agent 数 | **210,000 / 230,000 / 250,000** | = `f × 200,000` |
| `SCALE = ΣT / N` | **2.29897**（恒定） | 复制机制下平均 EF 不变 |

**三条闭合论证**：
1. **7.4.3 已证**：只缩放 `expansion_factor` / `od_trips` 而**不动 agent 数**是对仿真的 **no-op**
   —— `HRSx-yavg` 一个数都不变，Sim/Obs 只是被算术地乘 f（那样的「三档实验」会得到三份
   **完全相同**的 linkstats，跑 MATSim 毫无信息）。
2. **`f_cap = 1.00` 冻结**（而非 `N/200,000`）**排除**了 7.6D-S 的「采样一致性」约定，
   锁定 7.4.3 的「**物理加车**」约定。
3. **`SCALE` 恒定**：复制 agent 会连同其 `expansion_factor` 一并复制 ⇒ 平均 EF 不变
   ⇒ `SCALE = 459794/200000 = 2.29897` 对三档**全部适用**。此点已由 7.6F-0
   `demand_scale_7_6f_0_decomposition.csv` 实证：**D01–D04 的 SCALE 列全为 2.29897**
   （而非 `459794/220000` 等）。

⇒ 本预注册按「`f_demand` 缩放**被仿真 agent 数**」冻结。
**若用户意图是「agent 数恒为 200,000、仅改算术倍数」，则本步骤应完全不跑 MATSim**，
改为在 R01 上做零仿真算术重标定（Sim/Obs 精确 × f）。

> **✅ 门控解除（2026-09-17 20:17）**：用户正式确认采用 **「物理加车」** 路径 ——
> `N_base = 200,000`（SCALE 锚）、`N_sim = f × 200,000`（QSim 真实分配车辆数），
> **不采用**「agent 数恒为 200,000、仅做算术倍乘」；并追加硬约束
> **「不得根据 `ΣEF` 重算 SCALE，三档统一 2.29897」**（详见 §2.37）。

#### 2) 设计：唯一变量 = `f_demand`

| 项 | 取值 | 性质 |
|---|---|---|
| **`f_demand`** | **1.05, 1.15, 1.25** | ★ 唯一被扫的量 |
| route-choice | `R01_rc_min`（innovation 0.8 / `[ReRoute 0.15, ChangeExpBeta 0.85]` / lr 0.5 / randomness 0.0） | 7.6E 冻结 |
| 采样基准 `N` / `f_cap` | 200,000 / **1.00** | 冻结（**不随 N 缩放**） |
| `SCALE` | **2.29897** | 恒定（复制机制） |
| λ / capacity / 迭代 / seed | 0.075 / 1.00 / 20 it（评估窗 it.10–19）/ 4711（MATSim）· 20260912（复制） | 冻结 |
| network / 人口源 / 观测靶场 | `network_cleaned.xml.gz` / 6.3.3A 冻结 200k / 7.1 + 7.3.6A（576 断面） | 冻结，**不得擅改** |

**人口机制**：以 6.3.3A 冻结 200k 人口为源，按 `seed=20260912` 的 **permutation 前缀**做
**嵌套随机子集复制**（F05 ⊂ F15 ⊂ F25 = 7.4.3 D04）；每 agent 的 `expansionFactor` /
`home_link` / `work_link` / departure `end_time` **逐字节不变** ⇒ 唯一变化 = 车辆数；
复制概率对每个 agent 相同 ⇒ 增量空间**无偏**。

| Exp | f_demand | agents | persons（实测） | ΣEF（实测） | `f_realized` |
|---|---:|---:|---:|---:|---:|
| **F05** | 1.05 | 210,000 | 210,000 | 482,591.7 | 1.0495824 |
| **F15** | 1.15 | 230,000 | 230,000 | 528,733.5 | 1.1499356 |
| **F25** | 1.25 | 250,000 | 250,000 | 574,710.1 | 1.2499296 |

**★机制可复现硬证据**：`F25` 人口与 7.4.3 `D04` 人口**解压内容逐字节一致**（sha256 前缀 `49ff7ccbe622770`）⇒ 复制管线未漂移。

#### 3) 预注册判据 G1–G7（**运行前冻结**）与判决空间

| # | 判据 | 门槛 | 性质 |
|---|---|---|---|
| **G1** | 稳定性承继：三档 `A_10:19`(MATCHED/CATA/SLIP) | MATCHED<3% 且 CATA<3% 且 SLIP<5% | **硬门槛** |
| **G2** | 单调性：Sim/Obs(08-09, MATCHED, FROZEN) 在 f∈{1.00,1.05,1.15,1.25} 单调递增 | 容差 ±0.5% | **硬门槛** |
| **G3** | `rho(f) = Sim/Obs_run(f) / (Sim/Obs_R01 × f)` | 仅报告 | 诊断 |
| **G4** | 曲线相对 `FROZEN` 靶场的位置、是否**跨越 1.000** | 仅报告 | 诊断 |
| **G5** | 三口径并报（`POSITIVE_ONLY` / `BEST_DIRECTION` 不得升格） | 必须同时输出 | **纪律** |
| **G6** | 空间残差 EAST / `radial_in` 逐档报告、不得压平 | 必须同时输出 | **纪律** |
| **G7** | 双口径 `Q̄_10:19`(Primary) + `Q_19`(Reference) | 必须同时输出 | **纪律** |

```
G1 不过                               -> RESPONSE_UNSTABLE（暂停，回 route-choice / OD 结构，不消耗 7.6F-2 算力）
G1 过 + G2 不过                        -> RESPONSE_NON_MONOTONIC（只记录形态，不得解释为需求响应）
G1 过 + G2 过 + 曲线未跨越 1.000        -> RESPONSE_STABLE_PARTIAL
G1 过 + G2 过 + 曲线跨越 1.000          -> RESPONSE_STABLE_CROSSES（f 方向可解释量级缺口，可进 λ / impedance）
```
网格未齐时输出 **`AWAITING_RUNS`**。

**★属性（7.6C-2 门后含义，当前生效）**：靶场不确定性 **7.609 pp** ≈ 粗档增量 ⇒ 本步骤**只能**
给出「带靶场不确定性的**粗档**响应关系」，**不能**给出「**绝对** demand scale」；
`0.9351` / `1.1642` **不得**用于反推 demand scale；`0.8590` 仍是唯一正式 demand=1.00 参照。

#### 4) 配置验证（零仿真，**67/67 PASS**）

由 `prepare_demand_response_7_6f_1.py` 的 **P1–P9 + W1–W6 共 67 项校验**保证：
与 **R01 config** 的差异**仅限** `plans.inputPlansFile` + `controller.{outputDirectory,runId}`；
route-choice 4 项、`f_cap`、seed、network、threads、travelTimeCalculator、linkStats 间隔、
`networkRouteType`、hermes capacity 与 R01 **逐值相同**（`MUST_MATCH_R01` 19 项）；P9 断言
**8 个冻结件 mtime 全部未变**；P8 断言 F25 与 D04 人口**解压逐字节一致**。

#### 5) 评价器自检（零仿真；网格未齐 → `AWAITING_RUNS`）

`evaluate_demand_response_7_6f_1.py` 在网格档 linkstats 未齐时仍**照常复算 R01 锚点并做同源对账**，
作为「口径未漂移」的硬证据（**7/7 全中**）：

| 对账 | 本脚本 | 基准 | 结果 |
|---|---:|---:|---|
| `FROZEN`（R01） | 0.8589732 | 7.6C-2 | ✅ 逐位 |
| `POSITIVE_ONLY`（R01） | 0.9350621 | 7.6C-2 | ✅ 逐位 |
| `BEST_DIRECTION`（R01） | 0.8909674 | 7.6C-2 | ✅ 逐位 |
| `Q̄_10:19`(MATCHED) | 4,567,961.5 | 7.6D 审计缓存 | ✅ 逐位 |
| `Q̄_10:19`(CATA) | 3,210,503.5 | 7.6D 审计缓存 | ✅ 逐位 |
| `Q̄_10:19`(SLIP) | 1,357,458.0 | 7.6D 审计缓存 | ✅ 逐位 |
| `Q̄_10:19`(ALL) | 68,252,699.5 | 7.6D 审计缓存 | ✅ 逐位 |

**R01 锚点（f=1.00）复述**：三口径 **0.8589732 / 0.9350621 / 0.8909674**；`Q̄_10:19`(MATCHED)
= 4,567,961.5；`A_10:19`(MATCHED) = **1.0009%**（<3% ✓，与 7.6E 一致）；空间残差
EAST **−32.2025%** / `radial_in` **−28.7967%** / NORTH-EAST **+34.7982%**（与 7.6C-1 逐值一致）。

#### 6) 明确不做（清单）

```text
x 不选 demand scale（本步只建立响应关系）      x 不评价 lambda（本轮仅保持 0.075）
x 不评价 OD 空间结构 / 距离带                  x 不把 POSITIVE_ONLY / BEST_DIRECTION 升格为正式靶场
x 不修改 7.3.6A crosswalk（若确需修，必须另立 7.3.6A-b + 另留证据链）
x 不用 0.9351 / 1.1642 反推 demand scale       x 不用调 demand 去压平 EAST / radial_in 的已知空间残差
x 不用 (1+delta) 修正因子平移旧 D01-D04        x 不加 1.00 以外的第五档；不改网格
x 不用 F05/F15/F25 各自的 ΣEF / N_sim 重算 SCALE（★全档统一 2.29897，见 §2.37）
```

#### 7) 产物与复现

- 入场准备：`scripts/od/prepare_demand_response_7_6f_1.py`
- **点火器（新增）**：`scripts/od/run_demand_response_7_6f_1.py`
- 预注册分析：`scripts/od/evaluate_demand_response_7_6f_1.py`
- 工作区：`matsim_demand_7_6f_1/`（`configs/config_F05|F15|F25_rc_min.xml` + `populations/pop_F05|F15|F25/` + `STEP7_6F_1_PREREGISTRATION.md` + 4 件 provenance/validation + `outputs/` + `logs/` + `audit/`）
- 状态：**三档人口与 config 已就位（67/67 PASS）→ 2026-09-17 20:19 正式点火（见 §2.37）。**

```bash
python scripts/od/prepare_demand_response_7_6f_1.py                  # 生成 + 67 项校验（已完成）
python scripts/od/run_demand_response_7_6f_1.py --dry-run            # 前置核验（18/18 ×3）
python scripts/od/run_demand_response_7_6f_1.py --experiments F05    # ★点火单档（--heap 24g）
python scripts/od/run_demand_response_7_6f_1.py --status             # 只看状态
python scripts/od/evaluate_demand_response_7_6f_1.py                 # 网格未齐 → AWAITING_RUNS
```

**冻结不动**：7.1 / 7.3.6A / OD / network / capacity / population / route-choice 任何冻结件；
**未改任何模型参数（只改被仿真 agent 数）；未选 demand scale / 未评价 λ**。

---

### 2.37 Step 7.6F-1 正式点火（**RUNNING**）— 「物理加车」路径确认 + 三档串行点火

#### 1) 用户裁定（2026-09-17 20:17）：正式采用「**物理加车**」解释

不再采用「200k agents 不变、只做算术倍乘」的方案。三个量**必须区分**：

```text
200,000            = 冻结的采样基准 / SCALE 分母（不改）
210k / 230k / 250k = QSim 中**真正参与交通分配的车辆数**（= f × 200,000）
2.29897            = 每个模拟 agent 对应的 OD 扩展权重
```

`ΣEF` 随复制 agent 增加而增加，而**平均 EF 基本不变** ⇒ `SCALE = ΣOD/200,000 = 2.29897` 全档适用。
这与 6.2B 人口实现逻辑一致：`expansion_factor` 用于**在统计上恢复冻结 OD**，
而**不是**代替 QSim 中真实车辆数。

| run | `f_demand` | simulated agents | SCALE | route-choice |
|---|---:|---:|---:|---|
| F05 | 1.05 | 210,000 | 2.29897 | R01_rc_min |
| F15 | 1.15 | 230,000 | 2.29897 | R01_rc_min |
| F25 | 1.25 | 250,000 | 2.29897 | R01_rc_min |

#### 2) ★追加硬约束：SCALE 全档统一，**不得**按 `ΣEF` 重算

> 不得根据 F05/F15/F25 的 `ΣEF` 重新计算 SCALE；三档统一使用冻结基准 `SCALE = 2.29897`。
> 否则就会把「增加真实车辆数」和「改变扩展权重」混成两个不同的 demand 操作。

**已实装为机器校验 + 审计产物**（`demand_response_7_6f_1_scale_audit.csv`）：
「若按 `ΣEF/N_sim` 重算」的偏离**仅作披露、一律 NOT USED**：

| run | ΣEF | N_sim | SCALE 采用 | 若按 ΣEF/N 重算 | 偏离 |
|---|---:|---:|---:|---:|---:|
| R01 | 459,794.0 | 200,000 | **2.29897** | 2.298970 | 0.00 ppm |
| F05 | 482,591.7001 | 210,000 | **2.29897** | 2.298056 | **−397.69 ppm** |
| F15 | 528,733.4723 | 230,000 | **2.29897** | 2.298841 | **−56.03 ppm** |
| F25 | 574,710.1279 | 250,000 | **2.29897** | 2.298841 | **−56.32 ppm** |

偏离全部来自 6.2B `FLOOR_PLUS_1`（每正 OD cell ≥1 agent）的取整效应，量级 1e-4 相对值，
**不改变任何结论**；评价器 `P1b`/`P1c` 对此设硬断言。

#### 3) 点火器 `run_demand_response_7_6f_1.py`（新增，本项目唯一会启动 MATSim 的 7.6F-1 脚本）

- **只运行已通过 67/67 校验的那份 config**：点火前对 config 做 **sha256 钉扎**，
  运行后再哈希断言**逐字节未变**（被执行的 = 被验证的）；
- 点火前逐档**重跑 `prepare` 的 `validate()`**（18/18：与 R01 逐参数 diff 白名单
  + 7.6E route-choice 4 项继承 + `f_cap`/seed/lastIter/λ + 人口指针）；
- 逐档落盘 `scale_if_recomputed_sumEF_over_N` 与 `scale_recompute_delta_ppm`（仅披露）；
- **断点续跑**：`outputs/<RUN_ID>/ITERS/it.19/<RUN_ID>.*.linkstats.txt.gz` 存在即跳过；
- 写 `demand_response_7_6f_1_run_manifest.json`（append-合并语义：exit code / wall min /
  iters 列表 / sha256 前后 / heap / MATSim 运行时描述）。

#### 4) 为什么**串行**而不是并行（RAM 硬约束，本轮实测）

本机 **63.7 GB RAM（点火时可用 ≈38.1 GB）**、28 逻辑核；而 100k+ 档需 `--heap 24g`
（12g 在 it.2/it.5 `PlanRouter` 被硬杀）。三档并行需 ≥72 GB ⇒ **必 OOM**。
故三档**串行**：预计 ≈ 88 / 94 / 100 min（200k 实测 84.41 min 外推），合计 **≈ 4.7 h**。
每档独立可中断、可续跑，已完成档不会被重跑。

#### 5) `f_realized` **如实报告，不四舍五入**

| run | 目标 `f` | `f_realized`（复制后实际 `ΣEF` 实现值） |
|---|---:|---:|
| F05 | 1.05 | **1.0495824** |
| F15 | 1.15 | **1.1499356** |
| F25 | 1.25 | **1.2499296** |

#### 6) 启动后**未变**的纪律

Primary = **MATCHED `Q̄_10:19`**；Reference = **MATCHED `Q_19`**；
三口径并报但 `POSITIVE_ONLY` / `BEST_DIRECTION` **不得升格**；crosswalk = **7.3.6A Frozen**；
`f_cap = 1.00`；λ = 0.075（仅保持，不评价）；EAST / `radial_in` 作为已知空间残差不压平；
**`0.8590` / `0.9351` 或任何倒数值均不得预先用于选择 demand scale**。

#### 7) 点火记录

- **2026-09-17 20:19** 前置核验 **18/18 × 3 档 PASS**，config sha256 钉扎完成；
- **2026-09-17 20:19** **F05 点火**（210k agents / 24g heap / 20 it）→ `outputs/F05_rc_min/`；
- **2026-09-17 21:29** **F05 完成：`PASS`** —— `exit=0`，**wall 69.73 min**（快于外推 88 min），
  **iters 20/20**，`it.19/*.linkstats.txt.gz` 22.5 MB 存在，**config sha256 运行后未变**（`cfg_unchanged=True`）；
  前置核验 **18/18 PASS**；manifest 已写 `demand_response_7_6f_1_run_manifest.json`。
  （收尾仅一条**良性**告警：`DumpDataAtEndImpl` 找不到 `it.19.*.experienced_plans_scores.txt.gz`
  —— 因中间迭代不写 plans 属预期，**不影响 linkstats**。）
- **2026-09-17 21:29** **F15 点火**（230k agents / 24g heap / 20 it）→ `outputs/F15_rc_min/`；
- **2026-09-17 22:50** **F15 完成：`PASS`** —— `exit=0`，**wall 80.40 min**，**iters 20/20**，
  `it.19/F15_rc_min.19.linkstats.txt.gz` 存在，**config sha256 运行后未变**（`cfg_unchanged=True`）；
  前置核验 **18/18 PASS**。`persons=230,000` / `ΣEF=528,733.4723` / `f_realized=1.1499356`。
- **2026-09-17 22:50** **F25 点火**（250k agents / 24g heap / 20 it）→ `outputs/F25_rc_min/`；
  至此累计 F05 **69.73 min** + F15 **80.40 min** = **150.13 min**，F25 预计 ≈75–85 min。

### 2.38 Step 7.6F-1 结果 — **`RESPONSE_STABLE_CROSSES`**（零仿真只读；校验 **21/21**；516.3 s）

> **三档仿真已跑完**：F05 `PASS` 69.73 min / F15 `PASS` 80.40 min / F25 `PASS` 75.74 min（累计 **3.76 h**，串行），
> 三档均 `exit=0`、**20/20 迭代**、`it.19` linkstats 齐备、**config sha256 运行前后逐字节一致**。
> 本步为**零仿真**评价：只读既有 linkstats，**未启动 MATSim、未改任何参数**。

#### 1) ★响应曲线 `f_demand → Sim/Obs`（MATCHED，08-09；Primary = 收敛窗 it.10–19 逐链路周期均值）

| run | `f_demand` | N_sim | **Sim/Obs `FROZEN`（主靶场）** | `POSITIVE_ONLY` | `BEST_DIRECTION` | Reference `Q_19` | `Q̄_10:19`(MATCHED) | `A_10:19`(MATCHED) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| R01 | 1.00 | 200,000 | **0.8589732** | 0.9350621 | 0.8909674 | 0.860338 | 4,567,961.5 | 1.0009% |
| F05 | 1.05 | 210,000 | **0.8994456** | 0.9791197 | 0.9333491 | 0.901418 | 4,791,355.7 | 1.0132% |
| F15 | 1.15 | 230,000 | **0.9767361** | 1.0632567 | 1.0146563 | 0.978187 | 5,236,533.2 | 0.9157% |
| F25 | 1.25 | 250,000 | **1.0535647** | 1.1463563 | 1.0956645 | 1.055759 | 5,678,900.9 | 0.7833% |

- **单调不减**（增量 +0.04047 / +0.07729 / +0.07683，均 > 容差 ±0.5% 的绝对量级）⇒ **G2 PASS**；
- **曲线跨越 1.000**（min 0.858973 → max 1.053565）⇒ **G4 PASS**；
- **★跨越点（线性插值，Sim/Obs = 1）**：`FROZEN` **f\* = 1.1803**（区间 1.15–1.25）／
  `BEST_DIRECTION` **1.1320**／`POSITIVE_ONLY` **1.0748**（后两者区间 1.05–1.15）。
- **★与 7.6C-2 的静态预测比对**：7.6C-2 由 `Delta_target` = 7.609 pp 推出的 `f*` 区间 = **[1.06945, 1.16418]**。
  实测三口径跨越点 **1.0748 / 1.1320 / 1.1803** ⇒ **`POSITIVE_ONLY` 与 `BEST_DIRECTION` 落在预测区间内**，
  **主靶场 `FROZEN` 的 1.1803 仅高出预测上界 1.4%** ⇒ **几何预测与动态仿真结果自洽**（粗档分辨率内的闭合）。

#### 2) 稳定性承继（`Σ HRS0-24avg`，与 7.6B/7.6D/7.6E 同口径；**不得与 Sim/Obs 的 `HRS8-9avg` 混用**）

| run | `A_10:19` MATCHED | CATA | SLIP | ALL | `parity_gap_rel`(MATCHED) | 门槛 |
|---|---:|---:|---:|---:|---:|---|
| R01 | 1.0009% | 1.0143% | 0.9691% | 0.5127% | 0.1349% | MATCHED/CATA < 3% / SLIP < 5% |
| F05 | 1.0132% | 1.0452% | 0.9374% | 0.5135% | 0.1251% | 同上 |
| F15 | 0.9157% | 0.9564% | 0.8194% | 0.5454% | 0.0483% | 同上 |
| F25 | 0.7833% | 0.8605% | 0.7636% | 0.5717% | 0.0455% | 同上 |

- **★加车不破坏收敛**：`A_10:19`(MATCHED) 由 1.0009% **降到 0.7833%**（agent 越多、采样越密 ⇒ 振荡越小）；
  `parity_gap_rel` 由 0.1349% 降到 0.0455% ⇒ **G1 PASS**（7.6E 的 `STABILITY_PASS` 机制在加车后**继续保持**）。

#### 3) 算术参照（零仿真上界）与拥堵阻尼比 `ρ(f) = 实测 / (R01×f)`

| run | `f_demand` | 实测 `FROZEN` | 算术 `R01×f` | **ρ** |
|---|---:|---:|---:|---:|
| R01 | 1.00 | 0.8589732 | 0.8589732 | **1.000000** |
| F05 | 1.05 | 0.8994456 | 0.9019219 | **0.997255** |
| F15 | 1.15 | 0.9767361 | 0.9878192 | **0.988780** |
| F25 | 1.25 | 1.0535647 | 1.0737165 | **0.981232** |

- **ρ ≈ 1（1.25 档仅 1.88% 阻尼）** ⇒ 在 200k→250k 范围内，加车Almost 未被拥堵吞掉，
  **全局量级缺口基本可由「加车」补齐**；`ρ` 单调下降但仍远未饱和 ⇒ 与 8-9 过饱和份额恒 0% 一致。
- **不设阈值**（7.6C-2 已判只能粗档识别）。

#### 4) ★★空间残差**不随 demand 变化**（决定性证据，与 7.6C-1 结论一致）

| run | EAST `rel_dev` | `radial_in` `rel_dev` | CENTRAL | NORTH | NORTH-EAST | WEST | `radial_out` |
|---|---:|---:|---:|---:|---:|---:|---:|
| R01 | **−32.20%** | **−28.80%** | −7.99% | +24.25% | +34.80% | +2.40% | +13.65% |
| F05 | −32.43% | −29.38% | −8.13% | +23.62% | +34.85% | +2.92% | +13.81% |
| F15 | −31.97% | −30.34% | −8.01% | +23.84% | +34.12% | +2.76% | +14.27% |
| F25 | −31.38% | −30.96% | −8.03% | +23.09% | +32.99% | +3.29% | +14.69% |

- **四档之间区域/径向相对偏差几乎不动**（EAST 极差仅 1.05 pp、`radial_in` 极差仅 2.16 pp）
  ⇒ **demand 缩放无法压平空间结构缺口**：**全局量级**与**空间结构**是两个正交问题。
- 这**正面确认** 7.6C-1 的判决（EAST/`radial_in` 残余低估 = **真实结构 + 细粒度链路归属 + 断面中位口径**），
  且**证明**「用调 `f_demand` 去压平区域偏差」是**错误路径**（G6 仅要求报告、**不得**优化）。

#### 5) 判据与判决

| # | 判据 | 结果 |
|---|---|---|
| G1 | 稳定性承继（三档 `A_10:19` 达标） | **PASS** |
| G2 | 单调性（容差 ±0.5%） | **PASS** |
| G4 | 曲线跨越 `Sim/Obs = 1.000` | **PASS（是）** |
| G5 | 三口径并报（`POSITIVE_ONLY`/`BEST_DIRECTION` 不得升格） | **PASS** |
| G6 | 空间残差已报告（EAST / `radial_in`） | **PASS**（32 行） |
| G7 | 双口径并报（`Q̄_10:19` + `Q_19`） | **PASS** |

**判决：`RESPONSE_STABLE_CROSSES`** —— `f_demand → Q_MATCHED → Sim/Obs` 的**稳定响应关系**成立，
曲线**单调**且在网格内**跨越 1.0**；**靶场不确定性（`Delta_target` = 7.609 pp）与粗档增量同量级**，
故**只识别粗档响应关系，不识别绝对 demand scale**（承 7.6C-2 的 `TARGET_MARGINAL_COARSE_ONLY`）。

#### 6) 口径未漂移的硬证据（对账）

- **7.6C-2 对账 3/3 全中**（tol 1e-6）：`FROZEN` 0.8589732 / `POSITIVE_ONLY` 0.9350621 / `BEST_DIRECTION` 0.8909674；
- **7.6D 审计缓存对账 4/4 全中**：R01 `Q̄_10:19`(MATCHED/ALL/CATA/SLIP) = 4,567,961.5 / 68,252,699.5 / 3,210,503.5 / 1,357,458.0 **逐位相等**；
- **`SCALE` 冻结审计**：全档统一 **2.29897**，`ΣEF/N_sim` 重算值**仅披露 NOT USED**（F05 −397.69 / F15 −56.03 / F25 −56.32 ppm）；
- **P1–P6 + G1–G7 + G4 共 21/21 PASS**。

#### 7) 产物与复现

- 点火器：`scripts/od/run_demand_response_7_6f_1.py`（**本项目唯一**会启动 MATSim 的 7.6F-1 脚本）
- 评价器：`scripts/od/evaluate_demand_response_7_6f_1.py`（零仿真只读）
- 工作区：`matsim_demand_7_6f_1/`（`outputs/F05|F15|F25_rc_min/` 各 20 迭代 + `logs/` + `audit/`）
- 审计产物：`audit/{STEP7_6F_1_REPORT.md, od_demand_response_7_6f_1_summary.json, demand_response_curve.csv,
  demand_response_arithmetic_reference.csv, demand_response_spatial_residuals.csv,
  demand_response_crossvalidation.csv, demand_response_7_6f_1_scale_audit.csv, _cycle_linkstats/,
  run_console_F05|F15|F25.log}`

```bash
python scripts/od/run_demand_response_7_6f_1.py --experiments F05 --heap 24g   # 已跑 PASS 69.73 min
python scripts/od/run_demand_response_7_6f_1.py --experiments F15 --heap 24g   # 已跑 PASS 80.40 min
python scripts/od/run_demand_response_7_6f_1.py --experiments F25 --heap 24g   # 已跑 PASS 75.74 min
python scripts/od/evaluate_demand_response_7_6f_1.py                            # 已跑 → RESPONSE_STABLE_CROSSES
```

**冻结不动**：7.1 / 7.3.6A / OD / network / capacity / population / route-choice 任何冻结件；
**未选 demand scale（`demand_scale_selected=False`）/ 未评价 λ（`lambda_selected=False`）**。

---

### 2.39 Step 7.6G λ 敏感度 screening — **`LAMBDA_DETECTABLE_NOT_IDENTIFIABLE` / `SPATIAL_INERT`**（零仿真只读；校验 **21/21**；823.1 s）

> **三档仿真已跑完**：L05 `PASS` 77.36 min / L75 `PASS` 81.63 min / L10 `PASS` 77.01 min（累计 **3.93 h**，串行），
> 三档均 `exit=0`、**20/20 迭代**、`it.19` linkstats 齐备、**config sha256 运行前后逐字节一致**。
> 本步为**零仿真**评价：只读既有 linkstats，**未启动 MATSim、未改任何参数**。

#### 0) ★机制前提：λ 作用在 **OD 构造层**，不是 MATSim 运行时参数

- 链条：`5C1 build_prior_od_5c1.py`（`LAMBDAS=[.05,.075,.10,.125,.15]`）→ `6.2B build_matsim_population_6_2b.py`（`DEFAULT_LAMBDAS=[0.05,0.075,0.10]`）→ `6.3.3A build_departure_profile_6_3_3a.py` → **人口文件**；**config 内无 λ 形参** ⇒ **换 λ = 换 `inputPlansFile`**。
- **★λ 不变性（经验证）**：`ΣT`(5C1) = **1,935,235**；`car_od_total`(6.2B) = **459,794**；`ΣEF`(6.3.3A) = **459,794.0000** —— **三档逐位相同**
  ⇒ **`SCALE = 459,794 / 200,000 = 2.29897` 天然 λ 不变**，用户「不得按 ΣEF 重算 SCALE」硬约束在 λ 维度**自动满足**（总-空间无混淆）。
- **成本后果**：三份 **200k λ 冻结人口已存在**于 `reports/matsim_departure_6_3_3a/`（`population_lambda_0p050|0p075|0p100.xml.gz`）
  ⇒ 7.6G **无需任何上游重建**，只需**复制 agent 到 236,000** + 换 config + 跑 20 it ⇒ 用户担心的「3×4 = 12 跑网格」**塌缩为 3 跑**。

#### 1) λ 响应曲线（MATCHED，08-09；Primary = 收敛窗 it.10–19 逐链路周期均值；**f ≡ 1.18，N_sim = 236,000**）

| run | λ | `f_demand` | N_sim | **Sim/Obs `FROZEN`（主靶场）** | `POSITIVE_ONLY` | `BEST_DIRECTION` | `Q̄_10:19`(MATCHED) | `Q_19`(MATCHED) | `A_10:19`(MATCHED) | 隐含 f\*(FROZEN) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| L05 | 0.050 | 1.18 | 236,000 | **1.0125538** | 1.0812354 | 1.0520222 | 5,431,058.8 | 5,441,685.0 | 0.8461% | **1.163660** |
| L75 | 0.075 | 1.18 | 236,000 | **0.9998291** | 1.0878873 | 1.0387486 | 5,374,462.6 | 5,386,490.0 | 0.9971% | **1.180222** |
| L10 | 0.100 | 1.18 | 236,000 | **0.9893922** | 1.0569860 | 1.0278950 | 5,320,598.4 | 5,332,539.0 | 0.9724% | **1.193808** |
| R01 | 0.075 | 1.00 | 200,000 | 0.8589732 | 0.9350621 | 0.8909674 | 4,567,961.5 | 4,576,724.0 | 1.0009% | （7.6E/7.6F-0 锚点，**仅作 f 轴参照**） |

**★中心问题「λ 是否改变 f\*?」的回答：**

- **† 口径护栏：R01 的隐含 f\* = 1.363560 是「参照值」，不参与任何判断。** 该值由 **f=1.18 附近局部割线向低需求侧外推**得到；响应曲线存在**非线性 / 凹性**，故**不作为需求尺度估计**，也**不参与 λ 敏感度比较**。正式需求工作点以**曲线插值 1.1803**（7.6F-1）与**实测 1.180222**（7.6G `L75`）为准；⛔ **不得由该列反推 demand scale**。

- **★直跑复核 7.6F-1 的插值点**：`L75 = λ0.075 @ f=1.18` 实测 **0.9998291** ⇒ 隐含 f\* = **1.180222**，
  与 7.6F-1 线性插值 **1.1803** 相差 **0.007%** ⇒ **插值可信度被直跑证实**（同时纠正用户表中「λ=0.075 @ f=1.18 已有」的事实错误 —— 7.6F-1 只跑过 **1.00 / 1.05 / 1.15 / 1.25**）。
- **λ 0.05 → 0.10 的全跨度效应**：Δ Sim/Obs `FROZEN` = **−2.3162 pp**（`POSITIVE_ONLY` −2.4249 / `BEST_DIRECTION` −2.4127；三口径极差仅 **0.1087 pp**）
  ⇒ 对应 **Δf\* = +0.03015**，即 λ 全跨度只把 demand scale 移动 **±0.0151**（≈ f\* 的 **1.3%**）。
- **单调**（G9，虽不要求）：1.0125538 → 0.9998291 → 0.9893922 ⇒ **λ↑（出行更局部化）需略多车**才能匹配观测。

#### 2) ★判决与阈值定位

| 阈值 | 值 | 本步实测 | 落点 |
|---|---:|---:|---|
| 全局**弱**（噪声底） | < 1.0 pp | **2.3162 pp** | 超过 ⇒ **可检出** |
| 全局**可辨识**（= 7.6C-2 `Delta_target`） | ≥ 7.609 pp | **2.3162 pp** | 未达 ⇒ **不可辨识** |

**判决：`LAMBDA_DETECTABLE_NOT_IDENTIFIABLE / SPATIAL_INERT`**
⇒ 按预注册 **Case A**：**λ = 0.075 保持为「敏感度中心 / 基准」取值，不得声明为数据最优 λ**；
**7.6H 的 demand scale 应给两层结果**：点估计（λ=0.075）＋ 由 λ 带来的**不确定带 [1.1637, 1.1938]**。

#### 3) ★★空间残差**几乎不随 λ 变化**（与 7.6F-1 的 demand 结论同构）

| group_by | group | `rel_dev`(λ=0.05) | `rel_dev`(λ=0.10) | 极差 (pp) |
|---|---|---:|---:|---:|
| region | NORTH-EAST | +0.3157 | +0.3336 | **1.7904** |
| region | NORTH | +0.2192 | +0.2341 | **1.4885** |
| region | WEST | +0.0349 | +0.0258 | **0.9174** |
| region | **EAST** | **−0.3082** | **−0.3173** | **0.9051** |
| radial | circumferential | +0.0880 | +0.0951 | 0.7098 |
| radial | radial_out | +0.1497 | +0.1428 | 0.6973 |
| radial | **radial_in** | **−0.3064** | **−0.3024** | **0.3960** |
| region | CENTRAL | −0.0744 | −0.0745 | **0.0034** |

- **EAST 极差仅 0.91 pp / `radial_in` 仅 0.40 pp**，而 EAST 的残余缺口是 **−31 pp 量级** ⇒ **λ 完全无法压平空间结构**。
- 对照 7.6F-1 demand 方向（EAST **1.05 pp** / `radial_in` **2.16 pp**）⇒ **λ 与 demand 的移动力同量级，且都远小于缺口本身**
  ⇒ **「全局量级」与「空间结构」是两个正交问题**（7.6C-1 / 7.6F-1 结论在 **λ 维度再次成立**）。
- λ 敏感度最大的两处 —— **NORTH-EAST 1.79 pp / NORTH 1.49 pp** —— 都是**远离中心**的区域，与「λ 惩罚长距离出行 ⇒ 主要影响远端 OD」的机制一致。

#### 4) 稳定性承继（`Σ HRS0-24avg`，与 7.6B/7.6D/7.6E 同口径；**不得与 Sim/Obs 的 `HRS8-9avg` 混用**）

| run | λ | `A_10:19` MATCHED | CATA | SLIP | ALL | `parity_gap_rel`(MATCHED) | 门槛 |
|---|---:|---:|---:|---:|---:|---:|---|
| L05 | 0.050 | 0.8461% | 0.9150% | 0.6827% | 0.5602% | 0.0918% | MATCHED/CATA < 3% / SLIP < 5% |
| L75 | 0.075 | 0.9971% | 1.0810% | 0.7987% | 0.5405% | 0.1496% | 同上 |
| L10 | 0.100 | 0.9724% | 1.0155% | 0.8708% | 0.5514% | 0.1337% | 同上 |

- 三档 `A_10:19`(MATCHED) 均 **< 1.0%**、`parity_gap_rel` 均 **≤ 0.15%** ⇒ **7.6E 的 `STABILITY_PASS` 在 λ 维度继续保持**（G5/G6 PASS）。

#### 5) 口径未漂移的硬证据（对账）

- **7.6C-2 对账 3/3 全中**（tol 1e-6）：`FROZEN` 0.8589732 / `POSITIVE_ONLY` 0.9350621 / `BEST_DIRECTION` 0.8909674；
- **7.6D 审计缓存对账 4/4 全中**（tol 1e-9，**逐位相等 Δ = 0.00e+00**）：R01 `Q̄_10:19` MATCHED/ALL/CATA/SLIP = 4,567,961.5 / 68,252,699.5 / 3,210,503.5 / 1,357,458.0；
  ★ 本步**修掉一个自检缺陷**：原 7.6G 评估器把 `routechoice_stability_by_iter.csv`（**逐迭代原始表，无 `metric` 列**）误当聚合表读
  ⇒ `KeyError: 'metric'` **静默跳过**对账；修法 = 复用 7.6F-1 的 **C2** 写法（读原始表 → 取收敛窗 `[10,19]` 列均值），并补 `encoding="utf-8-sig"`。
- **`SCALE` 冻结审计**：全档统一 **2.29897**；`ΣEF/N_sim` 重算值**仅披露 NOT USED**（L05 **+4.30** / L75 **−66.16** / **L10 −517.93** ppm）⇒ 冻结值**不可被 ΣEF 反推**。

#### 6) 判据与产物

| # | 判据 | 结果 |
|---|---|---|
| G1 | λ 网格齐备（3/3 档 × 20/20 迭代） | **PASS** |
| G5 | `A_10:19`(MATCHED) < 3.0%（全档） | **PASS** |
| G6 | 收敛窗 `parity_gap_rel`(MATCHED) < 5.0%（全档） | **PASS** |
| G7 | 全局标签 = `LAMBDA_DETECTABLE_NOT_IDENTIFIABLE` | **PASS**（\|Δ\| = 2.3162 pp） |
| G8 | 空间标签 = `SPATIAL_INERT` | **PASS**（max spread = 1.7904 pp） |
| G9 | λ 响应单调（不要求，仅登记） | **PASS** |

**P1–P7 + X1(3) + X2(4) + G1/G5/G6/G7/G8/G9 + P1b = 21/21 PASS。**

- 点火器：`scripts/od/run_lambda_sensitivity_7_6g.py`（**本项目唯一**会启动 7.6G MATSim 的脚本）
- 评价器：`scripts/od/evaluate_lambda_sensitivity_7_6g.py`（零仿真只读）
- 工作区：`matsim_lambda_7_6g/`（`outputs/L05|L75|L10_rc_min/` 各 20 迭代 + `logs/` + `audit/`）
- 审计产物：`audit/{STEP7_6G_REPORT.md, od_lambda_sensitivity_7_6g_summary.json, lambda_sensitivity_curve.csv,
  lambda_sensitivity_delta.csv, lambda_sensitivity_spatial_residuals.csv, lambda_sensitivity_spatial_spread.csv,
  lambda_sensitivity_scale_audit.csv, lambda_sensitivity_crossvalidation.csv, _cycle_linkstats/,
  _console_run_lambda_sensitivity_7_6g_chain.log}`

```bash
python scripts/od/prepare_lambda_sensitivity_7_6g.py                      # 生成 + 72 项校验（已完成）
python scripts/od/run_lambda_sensitivity_7_6g.py --dry-run                # 前置核验（24/24 ×3）
python scripts/od/run_lambda_sensitivity_7_6g.py --experiments L05 L75 L10 --heap 24g  # 已跑，累计 3.93 h
python scripts/od/evaluate_lambda_sensitivity_7_6g.py                     # 已跑 → LAMBDA_DETECTABLE_NOT_IDENTIFIABLE / SPATIAL_INERT
```

**冻结不动**：7.1 / 7.3.6A / OD / network / capacity / population / route-choice 任何冻结件；
**未选 λ（`lambda_selected=False`）/ 未选 demand scale（`demand_scale_selected=False`）/ `parameters_changed=False`（只改被仿真 agent 数）。**

---
### 2.40 Step 7.6H — 最终工作点确定与独立验证（`WORKING_POINT_FROZEN_AND_REPRODUCIBLE / SPATIAL_RESIDUAL_PERSISTS`）

> **定位**：7.6H **不是**「最终标定」，也**不是**新一轮参数搜索，而是 **「最终工作点 + 独立验证」**：
> 第一层**冻结**既有口径（只读引用），第二层跑**一次**独立验证，回答 **H1–H5 五个问题**。
> **零仿真评价** + 本步**只跑过 1 次 MATSim**（`W01`），此后只读 linkstats。

**★第一层（冻结，只读引用）**

| 项 | 冻结值 | 来源 |
|---|---|---|
| `λ_ref` | **0.075** | 7.6G 敏感度中心（⛔ **非**数据最优 λ） |
| `f_demand,ref` | **1.180222** | 7.6G `L75 @ f=1.18` **实测**（非插值） |
| `SCALE` | **2.29897** | 7.3.6A 冻结（**⛔ 不按 ΣEF/N_sim 重算**） |
| `f_cap` | **1.00** | 7.6E 冻结 |
| route-choice | **`R01_rc_min`** | 7.6E 冻结 |
| 靶场 | **7.3.6A crosswalk** | 7.1 冻结观测 + 7.3.6A Final Crosswalk |
| sampling base | **`N_base = 200,000`** | 7.6D-S / 7.6E 冻结 |

**★第二层（唯一一次独立验证 `W01`）**

`N_sim = round(1.180222 × 200,000) = 236,044`；**`SCALE` 仍 2.29897（⛔ 不是 `459,794/236,044`）**。

> ⚠️ **算术披露**：`1.1802 × 200,000 = 236,040`，而 `1.180222 × 200,000 = 236,044.4 → 236,044`。
> 本步取 **236,044**（由**实测** f\* 推出），二者差 **4 agent（0.0017%）** ⇒ 已写进预注册与 `frozen_parameters` 表。

| run | λ | N_sim | ΣEF | f_realized | exit | wall | iters |
|---|---:|---:|---:|---:|---:|---:|---:|
| `W01` | 0.075 | **236,044** | 542,628.837 | **1.1801564** | 0 | **102.22 min** | 20/20 |

**★H1–H5 判决（26/26 PASS）**

| 组 | 问题 | 结果 |
|---|---|---|
| **H1** | 可复现性 | `Sim/Obs FROZEN` = **0.999335**（Δ **0.0665 pp**）；隐含 `f*` = **1.180866**（Δ 6.44e-4 vs 1.180222）；`f_realized` = 1.1801564（Δ 6.6e-5）；vs 7.6G `L75` Δ = **0.0494 pp** ⇒ **独立实例化可复现** |
| **H2** | 稳定性 | `A_10:19`(MATCHED / CATA / SLIP) = **0.8899% / 0.9038% / 0.8568%**；`parity_gap_rel` **0.0964%**；`Q_19/Q̄_10:19` = **1.001972**（Δ 0.1972%）；**`never_arrived = 0`、`max_stuck_car = 0`**（dep 236,044 / arr 236,044）⇒ 未见 agent 量级引发的新失稳 |
| **H3** | 空间残差 | **格局保持**（8 组 max \|Δ vs `L75`\| = **0.7599 pp** ≤ 2.0 pp）；残差**仍在**：EAST **−31.75%**、`radial_in` **−30.67%**、NE **+33.88%**、CENTRAL −7.82%、NORTH +23.09% ⇒ **不追求消除** |
| **H4** | 边界 | 三层**独立成列、未合并**：工作点 `f* = 1.180222` / λ 敏感带 **[1.1637, 1.1938]** / 静态靶场带 **[1.06945, 1.16418]** |
| **H5** | 未解决 | 总体量级达标；EAST / NE / radial 残差**仍在**且对 demand / λ **低敏感** ⇒ **不宜强行消除**；另三项本地不可定量（车型构成 / AM 峰占日通勤比重 / 平均载客率） |

**★关键 PA（`W01` 相对全局偏差）**：ORCHARD **+142.00%**、BUKIT TIMAH **+138.61%**、OUTRAM **+131.69%**、MUSEUM +97.10%；TUAS **−86.99%**、HOUGANG **−86.98%**、KALLANG −72.91%。

**★判决**

```
WORKING_POINT_FROZEN_AND_REPRODUCIBLE / SPATIAL_RESIDUAL_PERSISTS
```

**★口径未漂移硬证据**：**X1** R01 三口径 vs 7.6C-2（Δ ≤ 4.9e-8）＋ **X2** `Q̄_10:19` 四口径 vs 7.6D 缓存（**Δ = 0.00e+00**）；
**SCALE 审计**：R01 **0.00 ppm** / W01 **−53.88 ppm**（仅披露，**NOT USED**）。

**★明确未做**：未再细搜 λ、未细化 demand grid（无 1.17–1.20 细扫、无 3×4 网格）、未做 crosswalk-b、
未改 7.1 / 7.3.6A / OD / network / capacity / route-choice 任一冻结件、未把 `POSITIVE_ONLY` / `BEST_DIRECTION` 升格靶场、**未把三层带压成单点**。

```bash
python scripts/od/prepare_final_workingpoint_7_6h.py --run --heap 24g   # 准备（24/24）+ 点火 W01（236,044 agents）
python scripts/od/evaluate_final_workingpoint_7_6h.py                    # 零仿真评价 → H1–H5（26/26）
```

---

### 2.41 Step 7.7A 入场审计 —— LTA 分车型交通量可得性（零仿真只读）

**目的**：7.6 收口后进入 **7.7（外部观测验证与空间残差归因）**。7.7A 的目标是回答
「EAST / `radial_in` / NE 的空间残差是否由**车型结构**造成」。

**判决（6/6 PASS）**：`local = VEHICLE_TYPE_VOLUME_UNAVAILABLE` /
`composition = COMPOSITION_EXPLAINS_GLOBAL_LEVEL_NOT_SPATIAL_PATTERN`

**★Q1 本地可得性 = 无**（字段级复核）：

- 核心观测 `08_TrafficCount/TrafficFlow_Data.json`（75,899 条）**字段全集仅 10 个**：
  `LinkID / Date / HourOfDate / Volume / StartLon / StartLat / EndLon / EndLat / RoadName / RoadCat`
  ⇒ `Volume` = **全部机动车合计**（字符串型，含千分位逗号，如 `"1,069"`）；`RoadCat` = **道路等级**（**不是**车型）
- LTA DataMall 端点清单（本项目 `lta_dynamic_data_downloader.py`）**无任何车型/分类计数端点**
- `data.gov.sg` 仅有**全国年度车队构成**（`Annual Motor Vehicle Population by Vehicle Type`）⇒ **非路段流量**
- 其余本地源（`Static_ 2026_03/GEOSPATIAL|PUBLIC TRANSPORT|OTHER`、`Dynamic_2026_03_16/historical_data` 55 项）
  均无分车型流量；`TrafficSpeedBands` 仅速度、`PassengerVolume_*` 仅 PT 人次
- 唯一本地车型线索 = **90 台 LTA 交通摄像机 × 8,552 帧**（`Dynamic_2026_03_16`）⇒ 仅能得**点位级构成**

**★Q2 零成本构成归因先验**（Census 2020 Table 104，居住端 PA × 11 方式；
口径 `PMV = Car Only + Taxi/PHC + Motorcycle/Scooter + Lorry/Pickup + Private Chartered Bus/Van`）：

| 层 | n | Pearson r(残差, car_share) | R² | 残差极差 | 构成极差 | 比 |
|---|---:|---:|---:|---:|---:|---:|
| region（7.6H `W01`） | 5 | **−0.3600**（**符号相反**） | 0.130 | 65.6 pp | 17.1 pp | **3.83×** |
| PA（`n_sections≥5`） | 21 | **+0.2533** | **0.0641** | 206.4 pp | 36.5 pp | **5.66×** |

- **反例最刺眼**：**NORTH 是 car 份额最低（56.9%）的区域，却是 sim 超额最高（+23.1%）的区域** ⇒ 直接推翻「低 car 份额 ⇒ 低估」的朴素假设
- 仅 **EAST** 一例巧合对齐（构成 68.4% ↔ 区域 `Sim/Obs` 0.682）
- **★全域自洽**：`car_share_pmv = 0.682452`（`PMV = 673,741`），与 7.6A 的 D01 断面 `Sim/Obs = 0.6830` 相差 **0.07%**；
  `1/0.682452 = 1.4653` vs `1/D01 = 1.4641`。机制自洽：**`f=1.00` 时 car-only 模型正好复现「私人机动车中 car 的份额」**，
  与 7.6A 判决 `CALIBER_GAP_DOMINATES`（非小汽车正好填满缺口）互相印证。
  ⚠️ **口径护栏**：`1.4653`（Census 构成比）与 `1.4641`（`=1/D01`）**概念不同**，属**两条独立证据链的巧合吻合**，
  ⛔ **不得**据此宣称等价，也**不得**由任一者反推 demand scale。
- **局限**：区域加权用 `section_geography` 的 PA 词表（与 Census 词表不同，12 个 PA 回退 `Others`）；人-次≠车-次（无 `occ` 观测）；含 7.6C-1 已识别的 **8.14% 硬零流伪影**；n=5 / n=21 ⇒ **只作方向性先验，不作定论**

**★方法学意义**：空间残差现已在 **demand（7.6F-1）/ λ（7.6G）/ 车型构成（7.7A）三个方向**同时被证明**不敏感**
⇒ 残差被定位到残余候选：**OD 空间结构 / 观测口径语义 / 网络表征 / 时段实现（temporal）**。

**★三条路径**：

| 路径 | 内容 | 外部数据 | 状态 |
|---|---|:--:|---|
| **A1** | Census 方式构成（PA 级）归因 | 否 | **本轮完成（audit-level prior）** |
| **B** | LTA 摄像机图像 CV 车型构成 | 否 | 待定：**覆盖与残差错位**（NE 仅 **7** 台、EAST **14** 台，vs CENTRAL **35** 台）；需 CV 依赖；时序错配（2026-05 vs 2025-11） |
| **C** | 断面级分车型计数（向 LTA 申请） | **是** | **`BLOCKED_ON_EXTERNAL_DATA`**，见 `STEP7_7A_EXTERNAL_DATA_REQUEST.md` |

**★下一步建议**：7.7A 严格版挂起 → **先推 7.7C（空间残差归因，零外部依赖）**，同步准备 7.7B（HTS 出发时刻）。

**★明确未做**：未启动 MATSim；未获取外部数据；未装 CV 依赖；未改 7.1 / 7.3.6A / OD / network / capacity / population / route-choice 任一冻结件；未把构成先验当作结论。

```bash
python scripts/od/audit_external_data_7_7a.py   # 零仿真审计（6/6 PASS）→ reports/external_validation_7_7/
```

---

### 2.42 Step 7.7C-0 空间残差归因基线审计（零仿真只读）

**目的**：7.7A 已排除「车型/方式构成」对空间残差的解释；本步把「EAST / `radial_in` / NE 残差存在」
进一步定位到 **6 层**（OD 空间供需 / 方向性 / 道路等级 / section 几何·twin·拓扑 / 长度归一化 / PA·Region 空间梯度）。
**用户裁定**：**先做 7.7C，并拆为「零仿真空间残差归因（7.7C-0）」与「时段敏感性（7.7C-1）」两层**，
**不直接进 7.7B / HTS**（理由：7.7A 已排除构成，继续等 HTS 非最高收益动作）。

**方法**：**零仿真、只读**。逐断面 Sim/Obs **直接复用** `evaluate_demand_response_7_6f_1.eval_run()`
（只重绑 `E.OUT / E.CYCLE_DIR / E.MATRIX_CSV` 到 7.6H 工作区），**不复制任何公式**。
`MUST_MATCH_BASELINE`：逐组 `rel_dev` 与 7.6H `h3_spatial` **逐位一致（max|Δ|=8.674e-17）**、
`Sim/Obs FROZEN=0.9993348`（=7.6H 汇总）；EAST / `radial_in` / NE = **−31.7524% / −30.6727% / +33.8833%**。

**判决（14/14 PASS；173.8 s）**：`RESIDUAL_LOCALIZED_TO_PA_LOCATION`

- 机制层：`pa_location` · `network_topology_twin` · `distance_impedance` · `region_location` · `directionality`
- **排除层**：`road_class` · `section_crosswalk` · `observation_semantics` · `network_representation`

**★核心发现**

1. **`radial × reciprocal` 交叉表（两机制独立可加）**：
   - `radial_in | recip=False`（n=130，**18.6% obs**）→ **ratio = 0.9915 ≈ 1.000**（干净子组几乎无偏）
   - `radial_in | recip=True`（n=34）→ **0.1738（−82.61%）** ⇒ **twin/对偶链路表征是强退化项**
   - 同 `recip` 类内 `in < circum < out` 排序保持（`recip=False` 跨度 **36 pp**）⇒ 方向性**独立**存在
2. **`has_reciprocal_pair`**：仅 **2 组**即达 `η²_excess = 0.1423`（全表最高效单因子）。
3. **方向性跨 f/λ 全 8 档稳定**（`radial_in < radial_out`）：f∈{1.00,1.05,1.15,1.25} × λ∈{0.05,0.075,0.10}
   ⇒ **非 demand/λ 伪影**（与 7.6F-1 / 7.6G 一致）。
4. **道路等级**：`motorway` 449 断面（136.7 万 obs）ratio **0.9922**（几乎无偏）；偏离大的类断面数 ≤16
   ⇒ **η²_excess = −0.0069（低于随机，无解释力）**。
5. **长度归一化失败**：区域残差极差 **33.88% → 42.49%（反而扩大 8.61 pp）** ⇒ 非 section 聚合尺度问题。
6. **PA 位置轴**：`η²_excess=0.2476`（最高）；与 `od_outflow` ρ=−0.3955 / `d_cbd` ρ=−0.3077 弱相关。

**对 7.7C-1 / 7.7B 的判据**：残差主控轴是 **网络表征（twin）与方向性**（结构/表征性质，且对 f、λ 均不敏感）
⇒ HTS 出发时刻很可能只影响 **时段总量/峰值形状** 而非空间格局。**建议 7.7C-1 先做零仿真解析上界**，
仅在显示「时段分散会系统性改变空间格局」时才进入 7.7B 做真实 temporal realization。

**产物**：`reports/spatial_residual_7_7c0/`（**19 文件** — 17 张 `c0_*` 表 + `step7_7c0_summary.json` + 报告；含 `c0_section_table.csv` 逐断面底表、
`c0_4_radial_x_reciprocal.csv` 核心交叉表、`c0_rank_eta2.csv` 归因排序、`STEP7_7C0_REPORT.md`）。
**脚本**：`scripts/od/audit_spatial_residual_7_7c0.py`

---

### 2.43 Step 7.7C-1 时段实现敏感性（零仿真解析上界）

**判决：`TEMPORAL_SPATIAL_SENSITIVITY_FAIL_DEFER_HTS`（ratio = 0.1104）。**

**★★方法学修正（本轮关键，务必保留）**：初版脚本以「**全局标量**」`share_8_9` 作乘子
⇒ 所有断面同乘一个系数 ⇒ `rel_dev_g` 在数学上**恒等不变**
（`P1_UNIFORM` 的 Δ 逐组恒为 **0.0000**），属**退化 / tautological** 设计，**无法回答空间敏感性**。
**已改为断面级 temporal shape**：`sim_8_9(s|P) = sim_8_9_scaled(s) × share_8_9(s|P)`，
`share_8_9(s)` 取自 6.3.3A 冻结底表 `trafficflow_link_hour_basis.csv`（1311 link × h7/h8）。

**★效应分离**：
- (a) **总体水平效应** `rho_glob = Σ(sim·share)/Σobs`：全局 Sim/Obs 由 **0.9993 → 0.4972**（P2）⇒ 时段分配本身所致；
- (b) **空间结构效应** `rel_dev_g = rho_g/rho_glob − 1`：**判据只看这一个**。

**★断面级异质性**：`share_8_9(s)` CV = **0.0909**，范围 [0.2783, 0.7931]，全网 **0.512897**；
按 region：WEST 0.4922 → CENTRAL 0.5217；**按 radial 几乎无差异**（in 0.5014 / out 0.5038）。

**★7 个 profile**：`P0_CONCENTRATED`（W01 基线）/ `P1_UNIFORM_50`（**退化参照**）/ `P2_TF_SECTION`（断面级 6.3.3A）/
`P3_TF_AMP2`（异质性外推 ×2）/ `P4_TF_MIRROR`（**结构镜像，对抗性**）/ `P5_BAND_P10` / `P6_BAND_P90`（逐链路日级 p10/p90 可行带）。

**★MUST_MATCH 7.6H**：P0 逐位复现 —— global Sim/Obs **0.9993348**；EAST **−0.317524** / NE **+0.338833** / `radial_in` **−0.306727**。

**★判据焦点（三条命名残差组）**：

| 组 | n | rel_dev(P0) | envelope [min, max] | max\|Δ\| | Δ/残差 |
|---|---:|---:|---|---:|---:|
| EAST | 133 | **−0.3175** | [−0.3549, −0.2992] | 0.0374 | **0.118** |
| NE | 77 | **+0.3388** | [+0.3285, +0.3417] | 0.0103 | 0.030 |
| `radial_in` | 164 | **−0.3067** | [−0.3283, −0.2983] | 0.0216 | **0.070** |

**★HTS gate**：`S_spatial`（命名组）= **0.3388**，`A_temporal`（命名组）= **0.0374** ⇒ **ratio = 0.1104 < 0.20 ⇒ FAIL**；
全组口径 ratio = **0.0924**。**★排序保持**：**region 与 radial 的组间排序在全部 7 个 profile 下严格保持**
（EAST 恒为最低区域 / NE 恒为最高 / `radial_in` 恒为最低 radial）；仅 `ring` 维 P4/P6 出现 R2↔R4 交换（基线仅差 0.006，**噪声级**）。

**★radial × reciprocal**：`radial_in | recip=False` 基线 rel_dev **−0.0078** ⇒ pooled ratio ≈ **0.9915**
（与 7.7C-0 **逐位一致**），全部 profile 下位移 ≤ 0.04 ⇒ **「近无偏子组」不随时段分配改变**。

**★局限（须随结论引用）**：temporal-only separable null **无法**表征 route-choice 重选 / 拥堵溢出 / spillback 动态耦合；
结论严格限于「**时段分配本身**不足以解释现有空间残差」。若需检验 `departure-time × route-choice × congestion` 耦合，
或 HTS 能提供独立行为证据，仍可进 7.7B。

产物：`reports/spatial_temporal_sensitivity_7_7c1/`（**8 文件** = 报告 + 7 CSV/JSON；含 `c1_section_share.csv` 逐断面底表、
`c1_group_envelope.csv`、`c1_radial_reciprocal.csv`、`c1_rank_preservation.csv`、`c1_summary.json`）。
脚本 `scripts/od/audit_temporal_sensitivity_7_7c1.py`。**零仿真；未改冻结参数；未选 λ / demand scale。**

### 2.44 Step 7.7D 空间残差归因收口（零仿真收口审计）

**定位**：**收口审计**，不创造新解释变量；只把 7.6H / 7.7A / 7.7C-0 / 7.7C-1 的证据串成可正式关闭的归因链。
**原则**：缺证据 ⇒ `BLOCKED`；有证据但不满足 ⇒ `FAIL`；**不猜**。

**判决：`SPATIAL_RESIDUAL_ATTRIBUTION_CLOSED_WITH_UNRESOLVED_STRUCTURAL_LAYER`（硬门 7/7 + 软门 2/2 PASS；零仿真）**

| 门 | 名称 | 类型 | 结果 |
|---|---|---|---|
| G1 | W01 独立验证锚点复核 | 硬 | PASS（SimObs `0.9993347696792919`；EAST `-0.3175244561953319` / radial_in `-0.3067274364274516` / NE `0.3388326175136829` 逐位） |
| G2 | 7.7C-0 ↔ W01 口径一致性 | 硬 | PASS（对 7.6H **实测真值**逐位，tol `1e-12`；`14/14`） |
| G3 | f 变化下空间残差稳定性 | 软 | PASS（R01/F05/F15/F25；EAST 恒最低、NE 恒最高；max span **1.851 pp**） |
| G4 | λ 变化下空间残差稳定性 | 软 | PASS（R01/L05/L75/L10；排序保持；max span **3.227 pp**） |
| G5 | `radial × reciprocal` 结构闭环 | 硬 | PASS（in\|False **0.9915**、out\|False **1.3546** > in\|False、in\|True **0.1738** < in\|False；f/λ **8/8** 且 C1 **7/7 profile** 结构保持） |
| G6 | temporal 上界闭环 | 硬 | PASS（ratio **0.1104**；`TEMPORAL_SPATIAL_SENSITIVITY_FAIL_DEFER_HTS`） |
| G7 | 车型/方式构成空间排除 | 硬 | PASS（`6/6`；`COMPOSITION_EXPLAINS_GLOBAL_LEVEL_NOT_SPATIAL_PATTERN`） |
| G8 | 已排除层明确化 | 硬 | PASS（**机会校正** `eta2_excess` ≤ .001：road_class −0.0069 / section_crosswalk −0.0021 / observation_semantics −0.0004 / network_representation −0.0017） |
| G9 | 剩余结构层明确化 | 硬 | PASS（机制层与排除层**不相交**） |
| G10 | 收口判决 | 硬 | PASS（全部硬门 PASS） |

**归因三类**：
- **已解释**：全局水平 `f_work=1.180222`；阻抗 `λ_ref=0.075`（可检测不可识别）；车型构成 `car_share_pmv=0.682452`（**仅总量级**）。
- **已排除**：`road_class` / `section aggregation` / `observation semantics` / `temporal realization` / `scalar demand·λ tuning`。
- **未解释（收缩到结构层）**：`PA/OD spatial allocation`、`reciprocal-twin network representation`、`directionality`、`section-to-network correspondence`。

**★结论边界（必须随结论引用）**：本步**不**证明 twin/directionality 已构成**因果机制**，仅证明**其他已检验层不足以解释剩余空间残差** ⇒ 问题被**收缩到结构性层**。

产物：`reports/spatial_residual_closure_7_7d/`（`d_checks.csv` / `d_closure_summary.json` / `STEP7_7D_REPORT.md`，含证据 manifest sha256）。
脚本 `scripts/od/audit_spatial_residual_closure_7_7d.py`（**适配器版**；预置占位路径版存 `.user_orig_backup`）。
**零仿真；未跑 MATSim；未改 7.3.6A / f / λ / R01 route-choice。⛔ 不再为追 HRS8-9 聚合拟合跑 demand/λ grid 或 HTS MATSim 标定。**

---

### 2.45 Step 7.8 Final Model Freeze & Validation Package 最终模型冻结（**本轮完成；零仿真定版；判 `FINAL_MODEL_FROZEN_AND_REPRODUCIBLE`，硬门 23/23**）

**定位**：7.7D 收口后，**从「研究」切换到「定版」** —— 不再产生新分析结论，只把 7.3→7.7D 的已验证链条整理成**不可歧义 / 可复现 / 可引用 / 可交付**的最终版本。⛔ **不跑 3×4 网格、不再细搜 f/λ、不再调 demand**。

**脚本** `scripts/od/freeze_final_model_7_8.py`（零仿真；只读 14 件冻结输入；仅写入新目录 `reports/final_model_7_8/`）。

#### 1) 7.8A 参数冻结

| 项目 | 最终值 | 来源 |
|---|---:|---|
| `f_work` | **1.180222** | 7.6G `L75` direct（7.6H 冻结） |
| `λ_ref` | **0.075** | 7.6G sensitivity center（⛔ **非最优 λ**） |
| `SCALE` | **2.29897** | 7.4 / 全流程冻结（★ΣT/N_base，⛔ 不按 ΣEF/N_sim 重算） |
| `f_cap` | **1.00** | 7.4 capacity freeze |
| Route Choice | **`R01_rc_min`** | 7.6E |
| Sim agents | **236,044** | `W01` = round(f_work × N_base) |
| Crosswalk | **7.3.6A** | frozen（只读） |
| Calibration target | **0.8589732** | 7.6C-2 `FROZEN`（主口径） |

**★措辞纪律（强制，须随结论引用）**：
> λ=0.075 作为经过灵敏度分析后的**工作中心参数**；7.6G 表明 λ 对**总体水平**具有**可检测**影响，但在**现有观测与误差边界下不足以实现可靠参数识别**。⛔ **不得写作「最优 λ / 数据最优 λ」**。

> `f_work=1.180222` 是**最终工作点**，**不意味着需求规模参数具有唯一真实值**（总量证据只能给区间，见 7.6A/7.6G）。

三层带**独立成列、⛔ 不得合并**：工作点 `f*=1.180222` / λ 敏感带 **[1.1637, 1.1938]** / 静态靶场带 **[1.06945, 1.16418]**。

#### 2) 7.8B 输入与算法冻结（版本锁）

| 层 | 冻结条目 |
|---|---|
| Input | Census 2020；ACRA / building / landuse / POI；OSM network；LTA TrafficFlow；existing network / zone mappings |
| OD | 332 Subzones；gravity；λ=0.075；IPF；Census workplace controls；attraction disaggregation |
| Sampling | `FLOOR_PLUS_1`；`N_base=200,000`；`SCALE=2.29897` |
| Network | frozen MATSim network；`f_cap=1.00`；frozen zone→node/link realization |
| Route Choice | `R01_rc_min` |
| Crosswalk | 7.3.6A |

> **版本语义**：7.8 之后**任何**修改上述条目，**都不属于「最终模型参数调整」，而属于新模型版本**（v1.1 Structural Repair）。

#### 3) 7.8C 最终验证包（`W01`）

`N_sim` **236,044** / `f_realized` **1.1801564** / `f_work` **1.180222** / `Sim/Obs FROZEN` **0.9993347697** / implied `f*` **1.180866**。
稳定性：`A_10:19`(M/C/S) **0.8899 / 0.9038 / 0.8568 %**、`parity gap` **0.0964%**、`Q19/Q̄` **1.001972**、`never_arrived=0` / `max_stuck_car=0`、departure = arrival = **236,044**。
跨步对账（口径未漂移）：X1 三口径 Δ ≤ **4.9e-8**、X2 四口径 **Δ = 0.00e+00**（逐位）。

#### 4) 7.8D 空间残差边界（★保留，不藏）

**Final Model — Known Spatial Residual Boundary**（55 行：region 5 / radial 3 / PA 37 / 关键 PA 10）。这不是「失败项」，而是最终模型**显式披露的已知边界**：

| 层级 | 组 | ratio | rel_dev vs global |
|---|---|---:|---:|
| region | EAST | 0.6820 | **−31.75%** |
| radial | `radial_in` | 0.6928 | **−30.67%** |
| region | NORTH-EAST | 1.3379 | **+33.88%** |
| pa | ORCHARD | 2.4184 | **+142.00%** |
| pa | BUKIT TIMAH | 2.3845 | **+138.61%** |
| pa | TUAS | 0.1300 | **−86.99%** |
| pa | HOUGANG | 0.1301 | **−86.98%** |

归因三类（7.7D 继承）：**已解释** f / λ / 构成·总量级；**已排除** road_class·section aggregation·observation semantics·temporal realization·scalar demand·λ；**未解释** ⇒ `PA/OD spatial allocation` · `reciprocal-twin network representation` · `directionality` · `section-to-network correspondence` ⇒ **`UNRESOLVED_STRUCTURAL_LAYER`**。**★这比强行把所有 section ratio 拉到 1 更有研究价值。**

#### 5) 7.8E 最终模型 Manifest + #168 完整性门

`FINAL_MODEL_MANIFEST.json` 固定模型身份：`model_version = Singapore_OD_MATSim_Final_v1.0`、`f_work=1.180222`、`lambda_ref=0.075`、`scale=2.29897`、`f_cap=1.0`、`route_choice=R01_rc_min`、`sim_agents=236044`、`crosswalk=7.3.6A`、`calibration_target=0.8589732`、`validation=W01`、`spatial_residual_status=UNRESOLVED_STRUCTURAL_LAYER`；并含 14 件冻结输入 sha256 证据 manifest + config 指纹。

**★#168 完整性门（23 条，全 PASS）**：冻结真值逐位一致（G1–G7）/ config 继承 7.6E 四项（G8）/ 运行控制（G9）/ 冻结输入存在（G10–G11）/ OD 结构未变 71,136 正 cell（G12）/ `car_od_total` 459,794（G13）/ 三层带未合并（G14）/ 空间残差仍在（G15）/ 上游判决一致（G16–G19）/ 纪律（G20）/ 6 件产品落盘（G21）/ **跑前后冻结件 mtime+sha256 逐位未变（G22，read-only 硬证据）** / `W01` it.19 产物存在（G23）。

#### 6) 产物

`reports/final_model_7_8/`（9 件）：**6 件正式产品** = `FINAL_MODEL_SPECIFICATION.md` / `FINAL_VALIDATION_REPORT.md` / `FINAL_PARAMETER_FREEZE.json` / `FINAL_VALIDATION_METRICS.csv` / `FINAL_SPATIAL_RESIDUAL_BOUNDARY.csv` / `FINAL_MODEL_MANIFEST.json`；+ `STEP7_8_REPORT.md` / `f_integrity_checks.csv` / `step7_8_summary.json`。

#### 7) ★停止规则（本项目节奏控制）

**7.8 完成后 STOP。** 后续若继续研究，属**新研究问题** `7.9 Structural Repair / Model v1.1`，**而非**「继续把 v1.0 的 `Sim/Obs` 从 0.9993 调到 1.00」——两者性质完全不同。

**纪律**：`zero_simulation=True` / `matsim_rerun=False` / `parameters_changed=False` / `lambda_selected=False` / `demand_scale_selected=False` / `frozen_artifacts_touched=False`。

**★本步自查 2 处脚本缺陷（均为自身核对逻辑、非数据问题）**：① G6 曾以**发布用四舍五入常量**（0.8589732）配逐位比较 ⇒ 改为按 7.6C-2 自声明 `tol=1e-6` 核对并保留全精度真值（Δ=4.331e-08）；② G21 曾在 manifest 自身写入**前**扫描产品 ⇒ 改为落盘后**两遍写 + 全量重扫**（manifest 内 `products` 仅列非自身 5 件，避免自 hash 循环声明）。

#### 8) ★7.8-VIZ 可视化看板 + **已录产物缺陷勘误**（附加件，非冻结产品）

**新增 2 件附加件**（`reports/final_model_7_8/`，⛔ 不属于 6 件冻结产品）：

| 文件 | 内容 |
|---|---|
| `FINAL_MODEL_DASHBOARD.html` | **自包含单文件看板**（219 KB；零 CDN / 零依赖 / 离线可开；浅深主题自适应）。12 面板：① 总体水平表盘 ② 收敛稳定性 ③ 三层区间数轴 ④ 归因 η²_excess 排序 ⑤ 已解释/已排除/未解释 ⑥ 空间残差边界（4 级 + 排序）⑦ **口径校验** ⑧ 断面 Sim-Obs log-log 散点 ⑨ SVY21 空间残差图 ⑩ 断面明细表（可排序）⑪ #168 门 23/23 ⑫ 版本线 + 停止规则 |
| `ERRATUM_spatial_residual_boundary_pa_all.csv` | 勘误：`pa_all` 37 行的 frozen / true / Δ / 两种 rel_dev |

生成器 `scripts/od/make_final_model_dashboard_7_8.py`（零仿真、只读；0.5 s）。

**★★发现并定位 1 处冻结产物缺陷（仅限展示表，模型身份与 #168 全部 23 门不受影响）**

- **症状**：`FINAL_SPATIAL_RESIDUAL_BOUNDARY.csv` 的 `pa_all` 层 ratio 出现**负值**（BEDOK −0.357807、HOUGANG −0.869825…）。
- **根因**：源文件 `7.7C-0 / c0_6_pa_gradient.csv` 的列 **`R_PA` 实际语义是「Q−1（相对偏离）」**（核对：ANG MO KIO `R_PA`=0.681533 ⇒ 真值 ratio=Σsim/Σobs=**1.680415**；ORCHARD 1.419980 ⇒ **2.418370**）。而 `freeze_final_model_7_8.py` L366–367 把它当 ratio ⇒ **双重变换**：`ratio_FROZEN = R_PA`（偏 **−1.0**）、`rel_dev_vs_global = R_PA − 1`（再偏 **−1.0**）；该层 **37/37 行全部受影响**（max |Δ| = 0.9999）。
- **其余三层正确**（从 576 断面表重算核对，|Δ| ≤ 4.6e-7 = 发布四舍五入精度）：`region` 5/5、`radial` 3/3、`pa_key` 10/10。
- **处置**：⛔ **未就地改冻结件**（守 7.8 纪律：改锁 = v1.1）⇒ 看板按**真值**呈现 + 挂「口径校验」面板显式标注 + 另出 `ERRATUM_*.csv`。**是否升 `v1.0.1`（勘误版）待用户裁定。**

**★本步自查 3 处口径陷阱（第 3 次出现同族错误，已固化为纪律）**

1. **「逐位一致」不能随口说**：冻结 CSV 的 ratio 按**发布精度**四舍五入存储（region/radial 6 dp、pa_key 5 dp）⇒ 逐位比对必然 FAIL；判定容差须取 **1e-6**，并把精度事实写进产物文案。（与 7.7D G2 / 7.8 G6 同族。）
2. **聚合样本必须与冻结口径同源**：按「有坐标」筛掉 2 个断面 ⇒ 全局 ratio 变化 ⇒ **所有 rel_dev 整体偏移 0.07 pp**（NE 33.95% vs 冻结 33.88%）。⇒ **分组聚合用全 576 行；坐标只决定「能否进图」**。
3. **`rel_dev_vs_global` 定义 = `ratio / 全局ratio − 1`**，**不是** `ratio − 1`（EAST 上差 ~1e-3，足以让对账误判）。

**★渲染验证链（自建，可复用）**：`node --check` 内联 JS → **jsdom 无头 DOM 执行**（`jsdom@22.1.0`；Node 20 需 CJS 版，装托管工作区 + `NODE_PATH`）断言 14 面板非空 + 表格 574 行 → **Chrome headless 截图**（`--blink-settings=preferredColorScheme=1/2` 双主题 + `--force-device-scale-factor=2` 局部放大）+ PIL 分片目检。L2 抓出 1 处对账 bug；L3 抓出 4 处视觉缺陷（`**` 未渲染 / 零流断面被画成最显眼点 / 灰条不可见 / 网格列宽为负）。

---


### 2.46 Step 7.8-VIZ-RUN 为 VIA 可视化重跑 W01 并开启 events（**输出层重执行；判 `VIA_EVENTS_REPRODUCTION_CONFIRMED_BITEXACT`，40/40**）

**起因**：用户追问「用 VIA 看哪个 MATSim 文件夹是最终成果」。核查发现 **7.8 定版 W01 无 events**——`config_W01_rc_min.xml` 里 `writeEventsInterval = 0`；而 VIA 官方支持的输入 = network / events / plans / facilities / transit schedule，**车辆层（唯一能做车流动画的层）只能靠 events**。核对 **7.6 全家族**（`matsim_final_7_6h` / `matsim_demand_7_6f_1` / `matsim_lambda_7_6g`）**一律无 events**（当时为省 ~1.5 GB/次 × 9 次关掉）。

**做法 = 输出层重执行（⛔ 非新模型版本）**：新目录 `matsim_viz_7_8/`，`matsim_final_7_6h/` **一字未动**。**白名单差异仅 3 项**：`controller.outputDirectory`、`controller.runId`（`W01_rc_min` → `W01_events`）、`controller.writeEventsInterval`（`0` → `19`）；**214 个参数全展开（含 `<parameterset>`）逐位比对，非白名单差异 = 0**。准备步 **29/29 PASS**（判 `PREPARED_AWAITING_RUN`），含 V0/V31「14 件冻结输入 sha256 == 7.8 登记值」、V1「源配置 sha256 == `8f44fb349bff9cf1`」、V5–V15c「7.6E route-choice 五项 + R01 + f_cap + 人口/路网引用逐项继承」。

**MATSim 2026.0 注释实证 events 语义**：`iterationNumber % writeEventsInterval == 0` 写该迭代；`dumpDataAtEnd=true` 且 `lastIteration=19` 为间隔整数倍 ⇒ **在输出根目录再写一份** ⇒ it.0 + it.19 + 根目录 ≈ 4.5 GB；**it.0 是未收敛路线的流量、非最终模型 ⇒ 跑完即删（V48，释放 1.76 GB）**。

**结果**（**117.67 min**，heap 24g，exit 0；过程门 **40/40 PASS**）：

- **★重放 `BITEXACT`**：it.19 linkstats **693,575 / 693,575** 行 **max|Δ| = 0.0**、`relΣ = 0.00e+00` ⇒ **本轮与新模型无关，是同一模型的字节级等价重放**。
- events **163,305,988** 条 / **1.69 GB**；`departure = arrival = **236,044**`（== 冻结 `N_sim`，**零滞留**）；`entered_link = left_link = **80,708,818**`；`PersonEntersVehicle = vehicle enters traffic = 236,044`。
- **14 件冻结输入跑前后 sha256 + mtime 逐位未变**（V30/V31）；冻结 W01 配置仍 `writeEventsInterval=0`、其输出目录仍 **0 个 events**（V32/V33，未被污染）；`freeze_final_model_7_8.py` 复跑 **G22 `changed=[]`** ⇒ **v1.0 身份不变**。
- **★两个 events 文件字节完全相同**（sha256 `c9b61fba06d8a9b0…`，各 1.69 GB，**非硬链接**）⇒ 目录内 **1.69 GB 冗余**，给 VIA 任选其一即可。新目录总占用 **3.9 GB**。

**★VIA 食用方式**：要**车流动画** → 开 `matsim_viz_7_8/outputs/W01_events/`（network + events + plans + links.csv + vehicles）；要**定版基准** → `matsim_final_7_6h/outputs/W01_rc_min/`（静态层 + `output_links.csv.gz` 的 `vol_car` / WKT 几何，**无动画**）。完整步骤见 `matsim_viz_7_8/README.md`。

**★本步自查 4 处缺陷（同族第 4 次，已固化为纪律）**

1. **配置 diff 解析器漏 `<parameterset>`** —— 而 **route-choice 恰藏在 `<parameterset type="strategysettings">`** 里 ⇒ 原先的 diff 是「**假安全**」（覆盖不完整）。已改为**全展开 214 键**。
2. **★键名必须从产物读、不能猜**：route-choice 真实键名不是 `strategy.ReRoute` / `planCalcScore.learningRate`，而是 `replanning[?].weight`（`strategyName=ReRoute` / `ChangeExpBeta`）、`replanning.fractionOfIterationsToDisableInnovation`、`scoring.learningRate`、`routing.routingRandomness`。
3. **★重放判定不能写死「必须逐位」**：配置是 `qsim.numberOfThreads = 8` / `global.numberOfThreads = 8`，多线程跨次运行不保证逐位 ⇒ 改**分级** `BITEXACT` / `NUMERIC_EQUIVALENT`（max|Δ|≤1e-9 且 Σ 相对差≤1e-12）/ `APPROXIMATE`（≤0.5 且 ≤1e-6，**通过但带警告**）/ `DIVERGED`（FAIL）。
4. **Edit 工具连中 3 次「报告成功但未落盘」**（`write_readme` 签名、`verify` 签名、`count_events`）⇒ 最终**整文件 Write 重写**才落地。再次印证既有教训。

---


### 2.47 Step 7.8-VIA-DIAG「VIA 早高峰不拥堵」三层诊断（**零仿真只读派生；非新版本**）

**起因**：用户追问「为什么我用 VIA 看仿真结果，新加坡全市早高峰一点儿都不拥堵？」

**结论：三层叠加**（⛔ 不是模型跑错）：

| 层 | 原因 | 关键证据 |
|---|---|---|
| **① 可视化层（主因）** | VIA 的 **Network 层本身不带任何交通属性**；供 VIA 的 `output_links.csv.gz` 只有 **10 列**（`link, from_node, to_node, length, freespeed, capacity, lanes, modes, vol_car, geometry`），**无任何行程时间/速度/延误字段** ⇒ Link Coloring 只有静态字段，`freespeed` 是**设计速度**。 | VIA 手册 §3.2.5 **`Dynamic Link Attributes`**：*"Displays traffic volumes or average link speeds ... **Requires a loaded network file and an events file.**"* ⇒ **必须另加该层**，再把 **aggregation window 设 08:00–09:00**、颜色属性改 **`speed`**。按 volume 着色也不显堵（v/c 中位数 **0.0236**） |
| **② 路网表征层** | **693,575 条有向碎段**，长度中位数 **11.0 m** / 均值 21.8 m（总长 15,126.5 km）；**>200 m 仅 3,463 / >500 m 167 / >1 km 仅 23**；单车道 51.1%。全市尺度下单段 < 1 像素；且 MATSim 行程时间**取整秒** ⇒ 几米路段倍率失真。 | 倍率 × 长度：**0–20 m 1.757** → 20–50 m 1.311 → 100–200 m 1.096 → **>500 m 1.018** |
| **③ 模型层（真实）** | **v/c 恒 ≤1**（max **1.000000**，>1.0 的 **0 条**；>0.5 仅 **1.22% 路段 / 17.79% 车流**）⇒ 容量相对需求严重富余，仿真不会出现「堵死」红链。 | 全网拥堵指数 **1.4143**（全部）→ 剔 ≤20 m **1.2671** → 剔 ≤50 m **1.2091** → 剔 ≤100 m **1.1082**；需求 **236,044 辆全在 07–09 出发**，峰值在途 **36,799 辆** ≈ **2.4 辆/km** |

**★「堵的很多」≠「看得见」**（同一批载流路段换口径结论相反）：

| 倍率 | 按**条数** | 按**长度**（≈视觉面积） |
|---|---|---|
| ≤1.2 | 42.6% | **66.3%** |
| 1.5–2.0 | 17.6% | 8.6% |
| >2.0 | **16.1%** | 3.0% |

⇒ 长路段（视觉占主导）恰好自由流，高倍率全是几米短段 ⇒ 地图「偏绿」是**面积权重**的必然结果。

**★本步自查 2 处**：

1. **按位置贴两表 ⇒ 整体错配**：首版把 linkstats 的值**按行号**贴到 network CSV 上，而**两表行序不同** ⇒ 地图配色与属性文件整体错位（地图仍「偏绿」，肉眼不易察觉）。改为 **按 `link id` 显式 `merge`** + 内建自检 `np.allclose(LENGTH, network.length)`；交叉校验链路 `e157170_157176`（期望 speed 86.09 / ratio 1.045 / load 0.9509）**逐位一致**。
2. `pd.Categorical == label` 返回 **ndarray**（非 Series）⇒ `.to_numpy()` 报 `AttributeError`，用 `np.asarray(...)`；matplotlib 中文须 `addfont(msyh.ttc)` + `rcParams['font.sans-serif']`。

**产物**（`reports/via_congestion_diagnosis_7_8/`，⛔ 非 7.8 冻结产品）：
`VIA_CONGESTION_DIAGNOSIS.md`、`via_link_attributes_HRS8-9.tsv`（**693,575 行**，首列 `link`，含 `vol / speed_kmh / cong_ratio / load_vc / delay_s_per_km` × 0708/0809 ⇒ VIA **Attributes Manager** 可直接加载）、`congestion_map_and_diagnostics_HRS8-9.png`（A/B 地图 + C 倍率×长度 + D 条数vs长度 + E 出发时刻 + F v/c + G 指数塌缩）、`diagnosis_summary.json`。
脚本 `scripts/od/diagnose_via_congestion_7_8.py`（零仿真，<2 min）。`matsim_viz_7_8/README.md` 已加「只加 Network 层不会显示拥堵」小节。

---


### 2.48 Step 7.7E 拥堵状态合理性审计（**零仿真只读事后审计；判 `CONGESTION_STATE_PLAUSIBILITY_AUDIT_COMPLETE`，硬门 20/20**）

**起因**：用户在 7.8-VIA-DIAG 之后追加裁定 —— 「VIA 看不出拥堵」不能只归给可视化；必须回答
**「当前模型匹配了断面*流量*，是否产生了*合理的拥堵状态*？」**，并**明令禁止为提高 demand 让动画变堵**。

**性质**：⛔ **只读事后审计** —— 零 MATSim 重跑、未改任何冻结输入/参数/产物；模型仍是
`Singapore_OD_MATSim_Final_v1.0`（23/23 门不受影响）。数据源仅 `matsim_viz_7_8/outputs/W01_events/`
（输出层重执行、已判 `BITEXACT`）+ `reports/matsim_network/network_links_source_copy.csv`（含 OSM `highway`/`name`）。
产物全在 `reports/congestion_plausibility_audit_7_7e/`（⛔ **非 7.8 冻结产品**）。

**★0 两条必须先纠正的口径**（本轮推翻既有读法）：

1. **`v/c ≤ 1` 是结构性质，不是「容量富余」**：MATSim 链路流出被容量截断，需求超额表现为**上游排队**而非该链路 `v/c > 1`
   ⇒ `v/c = HRS8-9avg / CAPACITY` **恒 ≤ 1**；`v/c = 1.000000` = **已饱和 + 正在排队**。
   （7.8-VIA-DIAG 曾把 `max v/c = 1.000000` 读成「容量富余」，此处**更正**。）
2. **★★`qsim.timeStepSize = 1 s` ⇒ 既有「拥堵倍率」口径被量化污染**：本网络链路自由流时间
   **中位 1.37 s / 均值 2.93 s**（>500 m 仅 29 条），多数链路不足一个时间步；1 s 步长下链路行程时间被
   **向上取整**（`TT_recorded = ceil(FF)`）⇒ **即使零延误**，`TT/FF = ceil(FF)/FF ≫ 1`。

**★E1 容量来源**：`capacity = lanes × capacityPerLane(road_type)`，每车道容量是 `road_type` 的**确定性函数**；
限速与源副本**逐位一致**；源副本 `lanes` 有 27 万余条缺失（不参与比较），可比区间内车道数完全一致。
快速路/高速（motorway 1900 / trunk 1800 / motorway_link 1700）**在 HCM 参考带内**、并未被抬高；
**超出上沿的是干道与地方道路**（primary 1500>1200、secondary 1200>1000、residential 700>600）
⇒ **H1「容量被设得离谱地大」不成立**。容量利用率：全部 **7.9%** / 已载流 **12.8%** / 快速路走廊 **28.5%** / 干道 7.8% / 地方 0.9%。

**★E2/E2b 走廊与量化审计**（10 条快速路：PIE/AYE/CTE/ECP/TPE/SLE/BKE/KPE/KJE/MCE）：

| 口径 | 结果 |
|---|---|
| 原始 `TT/FF` | 1.20–1.44，看起来「每条都在堵」 |
| **`ceil(FF)/FF` 量化基准** | 1.20–1.40（**只由路网几何决定**） |
| **扣量化后真实超额** | **9/10 条 ≈ 0（−0.002 ~ +0.008）；只有 CTE +0.085（105 车时）** |

**跨时段对照（决定性）**：量化基准在所有时段恒定 **1.567–1.596**；实测倍率随需求 1.552–4.705；
**几乎空网的 12–13 时（仅 18,694 车·链路）倍率仍有 1.552 ≈ 基准 1.596** ⇒ **该口径测的是量化、不是拥堵**。
**82.56% 载流链路零延误**（`|TT/FF − ceil(FF)/FF| < 0.05`）。单车级样本：链路 `e138309_138310`
（15.924 m，FF = 0.955 s）07:00 有 23 辆车，`sum_tt` **恰为 23.0 s** = 每车恰好 1 s = `ceil(0.955)`。

**★按道路类型分解真实延误（本步最关键的新证据；08–09 全网 4,779 车时）**：

| road_type | 载流链路 | **真实超额** | **扣量化延误 车时** | **占比** |
|---|---:|---:|---:|---:|
| **`service`** | 62,407 | **+5.580** | **4,509** | **94.4%** |
| `motorway` | 4,025 | +0.017 | **105** | **2.2%** |
| `motorway_link` | 8,113 | +0.052 | 68 | 1.4% |
| `residential` | 71,237 | +0.027 | 25 | 0.5% |
| `primary` | 23,979 | +0.005 | 20 | 0.4% |
| `secondary` / `trunk` / `tertiary` | 17,722 / 4,302 / 17,756 | +0.006 ~ +0.032 | 16 / 14 / 13 | 0.3% 各 |

⇒ **「真实拥堵延误」的主体是大量 20 km/h 单车道 `service` 接入短段（每车道容量仅 400 辆/h）的局部瓶颈**，
**不是城市快速路的排队拥堵**；`motorway` 仅 **105 车时**且**全部落在 CTE**。
**饱和链路 82 条 / 总长 1.15 km**：**74 条是 6 m 左右 `service` 短段**；**8 条是 CTE motorway**
（4 车道 / 90 km/h / 容量 7600，节点 `7214→7215→…→7221→20261` 首尾相接，SVY21 x≈29.4–29.7k、y≈33.0–33.3k
= CTE 中段 Jalan Toa Payoh / Kampong Java 一带），构成 **≈0.40 km 排队链**。

**★E3 拥堵是否形成连续空间结构**（宇宙 = 载流且长度 ≥20 m，n = 82,167；按 `to_node == next.from_node` 串链；**200 次随机置换**）：

| 判据 | 候选链路 | 最长连续链 | 随机均值 | p | z |
|---|---:|---:|---:|---:|---:|
| 原始 `TT/FF > 1.2` | 27,690 | 0.601 km | 1.402 km | 1.000 | −2.54 |
| 原始 `TT/FF > 1.5` | 2,728 | 0.420 km | 0.623 km | 0.870 | −0.78 |
| **★扣量化 真实超额 > 0.1** | 638 | **0.499 km** | 0.417 km | **0.165** | **+0.46** |

两套**原始**口径的 z 为负 ⇒ 被量化伪影标记的链路**比随机散布更分散**（正符合伪影特征：`ceil(FF)/FF`
只取决于该链路 FF 的小数部分，与地理/上下游无关）。**扣量化后的真实口径与随机散布不可区分（p = 0.165，不显著）**，
最长仅 0.499 km ⇒ **模型没有形成任何「连续几公里的拥堵走廊」**。

**★E4 07:00–09:00 峰值演化**：峰值在途 **36,799 辆 @ 08:55**（= `N_sim` 236,044 的 **15.6%**）、峰值/中位 **8.27**；
15 min 网络 `Σ流量/Σ容量` 峰值仅 **0.102**；真实超额全程 **+0.083 ~ +0.221** ⇒ **无拥堵波**；
events↔linkstats 交叉校验最大相对差 **0.0000%**。
（⚠️ 09:15 后需求崩塌、仅 `service` 短段载流 ⇒ 倍率被动放大，属**伪影放大而非拥堵波**，图中已显式标注。）

**裁决**：

| 假设 | 证据 | 裁决 |
|---|---|---|
| H1 容量过大 | 快速路每车道容量在参考带内；已载流利用率 12.8% | **不成立** |
| H2 OD 时空实现不足 | 峰值在途仅占 agents 的 15.6%；快速路走廊利用率 28.5% | **主因** |
| H3 路网表征稀释 | 693,575 条中 65% 是 `service`；FF 中位 1.37 s | **成立（放大视觉错觉）** |
| **H4 度量伪影（本步最重要）** | `timeStepSize = 1 s` ⇒ `TT/FF ≥ ceil(FF)/FF`；空网时段仍报 1.55；82.56% 链路零延误 | **决定性，推翻既有「拥堵倍率」口径** |

**一句话**：不是「有点堵但 VIA 没显示」，而是**扣掉 1 秒量化伪影后全网基本不堵**；全网 4,779 车时真实延误中
**94.4% 落在 `service` 接入短段**、**`motorway` 仅 105 车时（全在 CTE）**；
**快速路走廊层面唯一成形的真实拥堵 = CTE 约 0.40 km 排队链**。

**★★「交通流量校准成功 ≠ 拥堵状态校准成功」得到数据支持**：576 断面 `Sim/Obs = 0.9993348`（总量级匹配）
vs 已载流利用率 12.8% / `Σ流量/Σ容量` 峰值 0.102 / 无拥堵波 / 快速路走廊真实超额 ≈ 0（9/10）
⇒ **交通状态形成机制未被校准**。两者不矛盾。

**★纪律（用户硬约束）**：⛔ **不得为「让动画堵起来」而放大 demand**（`f_work = 1.180222` / `Sim/Obs = 0.9993348` 是已冻结结果）；
正确路径 = **7.9 Structural Repair / v1.1**（容量/车道/瓶颈/出发剖面结构修复 + **调小 `qsim.timeStepSize` 或改用逐车行程时间评价**），须另立版本 + 独立验证链。

**产物**（`reports/congestion_plausibility_audit_7_7e/`，⛔ 非冻结产品）：
`CONGESTION_PLAUSIBILITY_AUDIT_7_7E.md`（报告）、`congestion_plausibility_audit_7_7e.png`（6 面板）、
`e1_capacity_provenance_by_roadtype.csv` / `e1_capacity_anomalies.csv` / `e1_network_supply_vs_demand.csv`、
`e2_corridor_congestion_0809.csv` / `e2_roadclass_congestion_0809.csv` / `e2_saturated_links_0809.csv`、
`e2b_hour_control.csv` / `e2b_length_bucket.csv` / `e2b_corridor_quantization.csv` / **`e2b_roadtype_quantization.csv`**、
`e3_components_*.csv` ×3 / `e3_continuity_null_test.json`、
`e4_events_15min_by_link.csv.gz`（缓存 2.03 M 行）/ `e4_network_temporal_15min.csv` / `e4_corridor_temporal_15min.csv` /
`e4_leg_histogram_5min.csv` / `e4_crosscheck_linkstats.csv`、`audit_summary.json`。
脚本 `scripts/od/audit_congestion_plausibility_7_7e.py`（零仿真；首次 events 扫描 ~19 min，之后走缓存 ~1 min）。

**★本步自查 4 处**：① 把 `v/c = 1.000000` 读成「容量富余」（实为**饱和 + 排队**）；② 误用被 1 秒量化污染的
`TT/FF` 口径作拥堵评价（**7.6/7.7 标定用的是断面*流量*（Sim/Obs），未受影响**）；③ 「CTE 是全网唯一真实拥堵」
**过度概括** ⇒ 修正为「唯一真实拥堵的**快速路走廊**」，并补道路类型分解（`service` 才是延误主体）；④ E3 三判据中
`真实超额 > 0.1` 的 z 为 **正** ⇒ **不得写「z 全为负」**。★**Edit 工具连 5 次静默丢改动** ⇒ 一律改走
**Python 锚点补丁 + `assert count == 1`**（本步 14 处锚点全部一次命中）；★matplotlib 缺字形字符（`⛔`/`⇒`）
须从图内文本剔除（仅影响 PNG，不影响 md）。

---

### 2.49 Step 7.9A-0 采样—容量一致性审计（**v1.0 冻结后的只读结构审查 = 7.9 第一阶段；判 `SAMPLING_CAPACITY_CONSISTENCY_AUDIT_COMPLETE`，硬门 22/22**）

**定位（用户 2026-09-20 裁定）**：`7.8 v1.0 冻结 → 7.7E 事后只读诊断 → 发现状态形成机制结构性不足 → 7.9 Structural Repair / v1.1`。
本步**不是** 7.8 的前置校准步骤，**不**把结果回灌 v1.0 的参数选择。零仿真、零参数改动、零冻结件触碰。
**新增** `scripts/od/audit_sampling_capacity_7_9a0.py`（~10 s）⇒ 新目录 `reports/sampling_capacity_audit_7_9a0/`（8 件）。

**一、四个实际生效值（用户指定核实）**

| module | param | v1.0 | 生效? |
|---|---|---|---|
| `qsim` | `flowCapacityFactor` | **1.0** | ✅ 生效 |
| `qsim` | `storageCapacityFactor` | **1.0** | ✅ 生效 |
| `qsim` | `trafficDynamics` | **`queue`** | ✅ 生效 |
| `qsim` | `timeStepSize` | **`00:00:01`** | ✅ 生效 |
| `hermes` | `flow/storageCapacityFactor` | 1.0 | ⛔ 惰性 |
| `dsim` | `trafficDynamics` | **`kinematicWaves`** | ⛔ **惰性诱饵** |
| `controller` | `mobsim` | **`qsim`** | 决定谁生效 |

★ **两个口径陷阱**：① 全配置里 `trafficDynamics` 出现 **两次**（`dsim` = `kinematicWaves`、`qsim` = `queue`）⇒ **`mobsim=qsim` 故只有后者生效**，前者是惰性诱饵 —— **只看 key 名会得出完全相反的结论**；② `hermes.*CapacityFactor` 同为 1.0 但**惰性** ⇒ **A-1 的唯一容量旋钮是 `qsim.*`**（保持 `hermes` 不动，与 S100c 同构）。四个值在 **权威 cfg / viz cfg / 两次 MATSim 运行期 dump** 四源逐位一致。

**二、采样比例：一个必须排除的分母歧义（本步最重要发现）**

| 口径 | 值 | 判定 |
|---|---|---|
| `s = N_sim / ΣEF` = 236,044 / 459,794 | **0.513369** | ⛔ **误用**（与需求锚混用） |
| `s = N_sim / (SCALE·N_sim) = 1/SCALE` | **0.434977** | ✅ **capacity 一致性因子** |
| 两者之比 | **1.180220** | 恒等于 `f_work` ⇒ 已定位为**分母选错** |

**量纲证明（与 `ΣEF` 定义无关）**：`Sim/Obs = 1`（冻结 **0.9993347697**）断言 `F_real = SCALE × F_sim`；要保持 `v/c_sim = v/c_real` 即 `F_sim/C_sim = F_real/C_real` ⇒ **`C_sim = C_real / SCALE` ⇒ `f_cap = 1/SCALE = 0.434977`**。
`ΣEF = 459,794` 是 **Census 2020 Table 104 `Car Only` 的需求锚**，而模型实际在路网上表示的是 `SCALE × N_sim = 542,658` 辆（= **1.180222 倍**需求锚，用于弥合 7.6A 的 `CALIBER_GAP`：观测含非小汽车、全目的）；拿需求锚当流量分母会把一致性因子算成 0.513369（**偏高 18%，等于容量少砍 18%**）。★ **稳健性**：`1/SCALE = N_base/ΣEF` **与工作点缩放无关** ⇒ A-1 的数值不依赖 `f_work`。

**三、当前模型的物理含义（= 7.7E 结果的机制解释）**：236,044 辆车 = 真实 **43.4977%** 的样本，却跑在 **100% 的容量**上 ⇒ **`v/c_sim ≈ 0.43498 × v/c_real`** —— 这正是「流量可以对上（总量级），但容量竞争不足（状态）」的成因。

**四、零仿真预注册预测（冻结流量一阶上界；高估饱和）**

| 指标 | v1.0 实测 | A-1 预测（上界） | 倍数 |
|---|---|---|---|
| `n(v/c≥0.5)` | 2,813 | 16,049 | ×5.71 |
| `n(v/c≥0.9)` | 220 | 5,413 | ×24.60 |
| `n(v/c≥1.0)` | **82** | **4,187** | ×51.06 |
| 饱和里程 | 1.151 km | **178.114 km** | ×154.69 |
| 饱和里程占全网（15,126.5 km） | 0.008% | **1.177%** | — |
| 全时段 `Σ流量/Σ容量` | 0.052792 | 0.121368 | ×2.30 |
| 峰 `aggV/C`（7.7E E4，15 min） | 0.102447 | **0.235522** | ×2.30 |

★ **空间尺度结论（预注册）**：即使按 sample-consistent 容量，饱和里程也**只占全网 1.18%**、峰 `aggV/C` 仅 **0.236** ⇒ **仍不预期出现全网级拥堵波**，改变集中在**局部瓶颈**。
方向性预测：在途峰值 ↑（车辆滞留更久）、通过量 ↓、**`Sim/Obs` 预计下移** ⇒ ⛔ **`Sim/Obs = 0.9993` 是 v1.0 的流量校准成果，不得作为 A-1 的目标**；A-1 的流量门只是**崩解护栏**（`Sim/Obs >= 0.85`）。⇒ 若实测与投影一致，主因更可能落 **情形 C** ⇒ 第二刀转 **7.9B `trafficDynamics`**（A 容量 / B 动力学 / C 瓶颈结构 **三刀必须串行**）。

**五、7.9A-1 计划（待批准；本步不执行）**：唯一结构变化 = `qsim.flowCapacityFactor` / `qsim.storageCapacityFactor` `1.0 → 0.434977`（**单点派生值，不做 0.35/0.40/0.45/0.50 扫描** —— 那是参数拟合）；新版本 **v1.1**、新目录、新 runId；⛔ 不动 OD / `f_work` / λ / `SCALE` / population 236,044 / R01 / 7.3.6A / network / W01 / `randomSeed=4711`。**四项预注册读法**：A 拥堵显著增强且流量保持 ⇒ 表示尺度统一（非调参）；B 拥堵增强但 stuck/崩溃 ⇒ 转 **7.9B 瓶颈与存储结构**（⛔ 不把容量调回）；C 增强很少 ⇒ 转 **`trafficDynamics`**；D 流量严重恶化 ⇒ 查 flow scale × capacity × departure 耦合。

**★纪律**：⛔ 不为了让 VIA 变红而提高 demand；⛔ 不为制造拥堵降低容量/修改 λ/修改 route-choice；⛔ 不为视觉效果重定义 congestion index。**正确表述** = 「由于模型 population 按 **43.4977%** 样本表示完整交通需求，而 QSim 的流量与存储容量采用**未经 sample adjustment** 的 1.0 倍容量，因此首先检验 sample-consistent capacity representation；该因子由 population representation 独立推导，**不由交通观测误差反演**。」

### 2.50 Step 7.9B-0 交通动力学机制审计（**零仿真只读结构审查 = 7.9 第二阶段；判 `TRAFFIC_DYNAMICS_MECHANISM_AUDIT_COMPLETE`，硬门 16/16**）

**脚本**：`scripts/od/audit_traffic_dynamics_7_9b0.py`（读 v1.0 冻结网络 `matsim_final_7_6h/outputs/W01_rc_min/W01_rc_min.output_network.xml.gz` = 693,575 links / 421,406 nodes，加冻结 cfg；**源码证据 15 条逐条从 `tools/matsim-2026.0/matsim-2026.0-sources.jar` 现场重新核对，非凭记忆**）
**产物**：`reports/traffic_dynamics_audit_7_9b0/`（7 件：`TRAFFIC_DYNAMICS_AUDIT_7_9B0.md`、`traffic_dynamics_audit_7_9b0.png`（4 面板）、`b0_audit_summary.json`、`b0_fdiag_by_class.csv`、`b0_merge_diverge_enrichment.csv`、`b0_source_evidence.csv`、`_run_b0.log`）

**回答的五问（B1–B5）**

- **B1 当前真正生效的交通动力学**：`qsim.trafficDynamics = queue`；`dsim.trafficDynamics = kinematicWaves` **惰性**（`controller.mobsim = qsim`）；`qsim.inflowCapacitySetting` **未在 cfg 中设置 ⇒ 取 MATSim 默认 `INFLOW_FROM_FDIAG`**。
- **B2 `queue` 是否带 inflow 约束 —— 没有（源码级证明）**：`QueueWithBuffer.initializeQSim` 内 `switch (trafficDynamics) { case queue: case withHoles: break; ... }`（**L393–396**）⇒ 不改动 `maxInflowUsedInQsim`，其初值 = `flowCapacityPerTimeStep`（**L391** = 路网容量 × `flowCapFactor`）。**`queue` 的入口约束就是路网自带容量，没有额外的基本图入口限制。**
- **B3 换成 `kinematicWaves` 会有多少道路被新增入口约束卡住**：`q_fdiag(link) = (permlanes / 7.5) / (1/(15/3.6) + 1/freespeed)`（**L414**；`HOLE_SPEED_KM_H = 15.0`，L175），判据 **`r_fdiag = q_fdiag / network_capacity < 1`**。**被卡 = 21,670 links（3.1244%）= 869.589 km（全网 5.7488%）**。分速度级：local<30 132 条 / 2.4 km；collector 30–50 1,005 / 23.8 km；**arterial 50–70 15,526 / 492.4 km（最大贡献）**；fast 70–90 2,386 / **138.1 km（该类 100%）**；expressway ≥90 2,621 / **212.9 km（97.98%）**。★被移除入口容量合计 **8,784,415 veh/h**。
- **B4 ★★预登记假设被证伪**：问题「被卡 link 是否集中在 merge / diverge」——**三个独立口径一致给出负富集**：全样本 **0.268×**（merge 占比 71.61% → 19.20%）、同类别 0.18–0.65×、严格 junction（in-degree≥3）**0.090×**；被卡 link 的 from-node 平均入度 **1.207 vs 全样本 1.882**。**机制含义**：KW 的入口上限**不是节点级瓶颈机制**，而是对**高容量 / 高速度路段**的**整体性 ~10–11% 入口削流**（expressway 中位 r = 0.90、fast 0.89）。⚠️ **风险与红线同构：KW 可能让地图「变堵」却不提升结构性保真度**（均匀削流 ≠ 复现瓶颈）⇒ B-1 判据**必须同时**看 (i) 拥堵是否形成、(ii) 拥堵**位置**是否落在 7.7E 的 CTE / `service` 短段。
- **B5 碎片化网络里瓶颈的有效空间尺度**：link 中位 **11.0 m**、p90 52.0 m；**24.34% 里程在 < 20 m 的 link**；节点间距均值 **35.9 m**（27.9 nodes/km）；度 ≥3 节点 **242,388（16.0 个/km，即每 ~62 m 一个）**；度-2 直通节点 42.5%。★**不存在长「度-2 链」可供聚合**（中位 corridor = 1 条 link）⇒ **7.9C 应做 junction cluster 聚合，而非 corridor 聚合**。KW 储存最低值使 **20,922 links（3.02%）** 储存被放大（`queue` 下为 0）。

**★★A × B 非可加性（直接决定实验设计）**：`flowCapFactor` 缩放 `flowCapacityPerTimeStep`（L386）与 `storageCapacity`（L487），但 **`maxFlowFromFdiag` 刻意不缩放**（源码注释 **L407–412**「leave the inflow capacity (unscaled)」）。⇒ **`f_cap = 1/SCALE ≈ 0.435` 时 FD 入口约束在 0 条 link 上生效**（`f_cap = 1.0` 时 21,670 条）。而 **KW 的储存 / 空洞机制是 `f_cap` 不变**的（`minStorCapForHoles` 与几何储存同比缩放、判据为比值，L547）⇒ 0.435 下 KW 与 `queue` 的差别**只剩储存侧**。⇒ **从机制上支持「B1 用 `f_cap=1.0` 先测 `queue → kinematicWaves`；B2 才叠加 0.435」的串行设计**（⛔ 不要一次改两个机制）。

**7.9B-1 预登记（待批准）**：`f_cap=1.0` / `storage_cap=1.0`，**仅** `qsim.trafficDynamics: queue → kinematicWaves`；其余继承 v1.0（含 route-choice 锁、`stuckTime=10`、`removeStuckVehicles=false`）。观测：`Sim/Obs` 仅作**崩解护栏**（≥0.85），⛔ 不再作目标；主看**拥堵状态**指标（`v/c` 分布、饱和里程、峰 `aggV/C`、真实超额 `TT/FF − ceil(FF)/FF`、回溢链长度）。**决断规则**：若无实质变化且 `Sim/Obs` 未崩 ⇒ 判 **`TIMEDYNAMICS_NOT_PRIMARY`** ⇒ 转 7.9C（瓶颈 / 回溢结构）。

**纪律**：零仿真、未跑 MATSim、未改任何冻结件（`matsim_final_7_6h` + `matsim_viz_7_8` 跑前后 mtime+size 快照 **`changed=0`**、201 件）；`stuckTime=10` / `removeStuckVehicles=false` **保留观察、不作 7.9 第一变量**（W01 `never_arrived=0` 已健康）。


### 2.51 Step 7.9C-0 结构性瓶颈审计 junction-cluster / short-chain（**零仿真只读结构审查 = 7.9 第三阶段；判 `STRUCTURAL_BOTTLENECK_PRIOR_ESTABLISHED`，硬门 25/25**）

**目的（用户裁定）**：用**网络结构 + 既有观测映射**（⛔ **不用 W01 拥堵结果**）先把「哪里**应该**堵」定义出来，再把 W01 残差**投影**上去检验。**7.9C 不试图证明「KW 就是瓶颈机制」**；要验证的是两件独立的事：**(A)** 网络本身是否存在足够明显的结构性瓶颈与回溢通道；**(B)** 若存在，`queue` 与 `kinematicWaves` 是否对这些结构产生**不同的传播行为**。

**脚本**：`scripts/od/audit_structural_junction_cluster_7_9c0.py`（门 C0.01–C0.25 共 **25** 门）+ 输入预处理 `scripts/od/_build_network_cache_7_9c0.py` ⇒ `_cache_network_7_9c0.npz`（693,575 link 属性 + 421,406 节点坐标 + 574 断面 crosswalk 索引）。
**产物**：`reports/structural_junction_cluster_audit_7_9c0/`（10 件：报告 / 6 面板图 / summary JSON / 单元表 / L2 链表 / L3 走廊表 / C2 投影表 / C3 JSON / C4 冻结 JSON / 分层表 / run log）。

**三层空间尺度**

| 层 | 定义 | 规模 |
|---|---|---|
| **L1 junction-cluster**（主判据） | 同一自由流层级内、由短链（≤ p90 = **52 m**）连成的连通分量，且含 ≥1 结构种子节点；超 **200** link 的分量按「移除最长 link」**递归**拆解 | **22,722 单元 / 460,001 link（66.3%）/ 6,277 km**；单元规模中位 **10** link、p90 **51**、max **200** |
| **L2 short-chain** | ramp（`motorway_link`/`trunk_link`）/ connector（`primary/secondary/tertiary_link`）/ service（`service`）按拓扑合并成链 | ramp **500** 链 / connector **2,428** 链 / service **11,638** 链 |
| **L3 corridor**（**仅宏观诊断**） | 按 OSM `name` 分组的主干/快速路线 | 30 条（7.9B-0 已证 median corridor 退化为单 link ⇒ ⛔ **不作第一判据**） |

**结构种子节点** = 度 ≥ 3 且满足任一结构跃变（≥2 个自由流层级 / 自由流落差 ≥20 km/h / 车道数变化 ≥1 / 容量比 ≥1.25）⇒ 实测 **50,617 个（12.01% 节点）**。

**C1 结构瓶颈先验（⛔ 不含任何仿真流量；门 C0.22 源码自检）**：**节点分数 = `mean(merge_deficit, lane_narrowing, class_transition, ramp_mainline)`**；**单元先验 = 单元内节点分数的最大值**（严重度语义：「该单元是否含结构瓶颈、有多严重」）。分量均值：`merge_deficit` **0.0208** / `lane_narrowing` **0.1030** / `class_transition` **0.2348** / `ramp_mainline` **0.0124**。先验 均值 **0.349** / 中位 **0.375** / p80 **0.417** / max **0.938**。
★`storage_shortage_proxy` 均值仅 **0.0058** ⇒ 在本路网上**近乎恒 0、判别力为零**，**剔除出分数**（仅作诊断列）。**尺寸偏差** `Spearman(prior, log 单元规模) = 0.0251`（可忽略；因已限制单元 ≤200 link）。

**C2 既有残差的结构投影（检验，⛔ 不是定义）**：576 断面（`c0_section_table.csv`）经 **7.3.6A crosswalk** 落到 L1 单元 —— **映射覆盖 574/576 = 99.7%**（link 直连 **304** / 端点兜底 **108** / **空间最近邻 162**；兜底距离 中位 **56.8 m**、p90 **172.8 m**、max **376.4 m**，门 C0.23）。`rel_dev = ratio_8_9 / 池化比 − 1`（池化 `Sim/Obs = **0.999335**`）。
⇒ **Spearman(单元先验, 单元 rel_dev) = 0.0355**；**置换零分布**（同区域打乱断面，n=400；mean −0.0079 / sd 0.0480）**p(rho ≤ 观测) = 0.8125** ⇒ **无显著同向**。**规模分层后**（十等分、层内重算）median ρ = **0.0359**、负相关层 **4/9**，同样无信号。
四分位均值：Q1 **−0.0236** / Q2 **0.1619** / Q3 **0.2707** / Q4 **0.1546** ⇒ **无单调趋势**，甚至**最低先验层残差最负**。
⇒ **结论**：网络**确实存在**可量化的结构性瓶颈（C1 成立），但 W01 的流量残差**并不向这些单元聚集** ⇒ 当前 `queue` 模型「缺失的拥堵」**位置与结构应有位置不一致**，正是 **7.9B-1 要检验的「堵得对不对」**。

**C3「堵得对不对」判据（阈值预先冻结 + v1.0 基线）**
```
HitRate  = |模型高拥堵单元 ∩ 结构候选单元| / |模型高拥堵单元|
Coverage = |结构候选单元 ∩ 模型高拥堵单元| / |结构候选单元|
随机基线  = |结构候选单元| / |全部单元|    ⇒ lift = HitRate / 随机基线
```
阈值：候选 = 先验 ≥ **p80 = 0.4167**；模型高拥堵 = 单元长度加权 `v/c` ≥ **p80 = 0.0220**。
⇒ v1.0 基线 **HitRate 0.4475 / Coverage 0.3705 / lift 1.852×**（规模分层 macro：0.4218 / 0.3829 / **1.895×**）。
⚠️ **证伪性警告（两条，先证伪再断言）**：① **值域**：v1.0 几乎无拥堵（饱和 link **82** 个 = 全网 **0.0118%**、饱和里程 **1.151 km**），单元 `v/c` 的 p80 阈值仅 **0.0220** ⇒ 「模型高拥堵单元」在 v1.0 下**近似任意排名**；② **共同因子**：`ρ(prior, 单元单车道容量) = **0.2479**`、`ρ(单元 v/c, 单元单车道容量) = **0.4491**`，且 `fast`/`expressway` 单元 **81.7% / 94.9%** 天然落入候选 ⇒ `lift` 有一部分**不是位置信息**。⇒ **`lift = 1.852×` 不得读作「当前模型已把拥堵放对」**，它是**弱且被容量污染的**基线。

**C4 B-1 最小观察集（提前冻结）**：稳定性（`A_10:19` / parity gap / `never_arrived` / `max_stuck_car` / stuck 命中）、总量（`Sim/Obs`，**仅崩解护栏 ≥0.85**）、链级（`excess delay_h = TT/FF − ceil(FF)/FF`、link/单元 `v/c`）、结构（junction-cluster 拥堵：长度加权 `v/c`、饱和占比）、空间（**HitRate / Coverage / lift**）、连续性（拥堵连通分量长度 km 与个数）、时段（07–09 in-network vehicles，15 min 分箱）、重点对象（**CTE / service 短链 / ramp 链 / connector 链**）⇒ `c0_C4_b1_observation_set.json`。**成功判据 = 能证明 `queue → kinematicWaves` 是否改变拥堵传播机制与空间连续性，而不是「地图变红」。**

**v1.0 拥堵基线与自检**：`v/c ≥ 1` 的 link **82**（0.0118%）、饱和里程 **1.151 km（0.0076%）**、拥堵连通分量 **16** 个（中位 **37.9 m**、最长 **0.403 km** ≈ 7.7E 的 CTE 排队链）——**与 7.9A-0 冻结流量投影的 82 link / 1.151 km 逐位一致（门 C0.17）**。

**纪律**：零仿真、未跑 MATSim、未改任何冻结件（`matsim_final_7_6h` + `matsim_viz_7_8` 跑前后 mtime+size 快照 **`changed=0`**、201 件）；**门 C0.22 源码自检**要求 C1 先验函数体内**不出现** `vc[` / `vol[` / `ratio_8_9` / `sat[`（保证候选集与 W01 流量无关）。

**主线（用户冻结，2026-09-20 更新）**：`7.9A-0 ✓ → 7.9B-0 ✓ → 7.9C-0 ✓ → 7.9B-1 ✓（实验性，未采纳）→ **7.9C-1 ✓（因果解释已被 D-0 修正）** → **7.9D-0 ✓** → **7.9D-1 Ramp Interface Audit ✓** → **7.9D-2 Terminal Representation Audit ✓** → **7.9E-0 Arterial-Layer Delay Attribution ✓（判 `ARTERIAL_LAYER_AUDIT_BLOCKED`）**`；**7.9A-1（sample-consistent capacity）继续不动**；⛔ **7.9A-1 与 7.9B-1 绝不合并**；⛔ **暂不改 `service` 容量 400、暂不改端点吸附**——D-0/D-2 只发现“高度可疑的表示机制”，尚未证明它是主线观测残差的第一原因。**7.9E-0 补充：arterial 承载 off-mainline 车时 63.71%（时间主场），但延误仍以 `service` 居首（57.10%）；冻结靶场 77.8% 为 motorway/motorway_link，arterial 空间残差不可判定（E3 BLOCKED）。** **7.9E-1 补充（根因推进）：E0.09 的「arterial 不可观测」**根因不是匹配质量、也不是 arterial 样本少，而是**冻结靶场的定义域只覆盖 `CATA`(326)+`SLIP_ROAD`(250)——arterial 断面在 576 断面中恒为 0**。独立 diagnostic crosswalk 在全量 1,278 条有几何链路中可标出 **542** 条 arterial（A+B 覆盖 **97.48%**、中位匹配 **0.57 m**、p90 **2.92 m**）⇒ 判 `OBSERVABILITY_BLOCKED`；要检验 arterial 是否残差主场，**必须扩大断面域（新版本）而非放宽匹配**。 **7.9E-2 补充（本步）：** 用 E-1 独立 diagnostic crosswalk + 冻结 SCALE 口径把**诊断**断面域扩到全部 **1,278** 条链路 ⇒ **arterial 残差 n 12 → 542**，A+B 覆盖 **97.48%**、与正式 576 断面 bridge **Spearman 0.9662**；判 **`NO_ARTERIAL_COUPLING_SIGNAL`（12/12）**，但 **RoadCat 分层 `p = 0.05247` 临界**、且分层统计量 **69.3% 来自 CATA 单条误映射链路** ⇒ **arterial 是否残差主场仍不可判**；**★★真正结构 = 道路等级单调梯度**（`primary` +7.6% → `tertiary` −41.7%，flow-weighted），`arterial_core` 三类**符号相反 ⇒ 聚合均值是抵消伪影**。

### 2.52 Step 7.9B-1 `qsim.trafficDynamics: queue → kinematicWaves` 单变量机制实验（**7.9 第四阶段；仿真侧 49/49 + 分析侧 14/14**；判 `KW_CHANGES_CONGESTION_MECHANISM__KW_POSITION_NOT_IMPROVED__STABILITY_OK`）

**目的（用户裁定）**：v1.0 冻结后的**真·单变量机制实验**（⛔ **不是调参实验**）。只切换 **`qsim.trafficDynamics: queue → kinematicWaves`**，其余 v1.0 条件**全部继承**；结果落**独立目录**，⛔ 不碰冻结件。**成功标准不是「比 queue 更堵」，而是「在稳定性不过关的前提下，既产生动力学差异、该差异又具有可解释的空间结构」**。

**脚本**：`scripts/od/run_kw_single_variable_7_9b1.py`（配置派生 + 49 门硬门 + 点火）+ `scripts/od/analyze_kw_7_9b1.py`（零仿真只读三层分析，14 门）+ 输入预处理 `scripts/od/_build_link_unit_map_7_9b1.py` ⇒ `_cache_link_unit_7_9b1.npz`（**溯源执行 7.9C-0 冻结源码切片**重建 link→unit 映射，自校 **22,722 单元逐位一致**）。
**产物**：仿真 `matsim_kw_7_9b1/`（配置 + `audit/` + `outputs/W01_kw/`）；分析 `reports/kw_single_variable_7_9b1/`（**13 件**，含 `REPORT_7_9B1.md`）。

**diff 裁决（★单变量的核心门）**：模型层 **恰好 1 项** = `qsim.trafficDynamics: queue→kinematicWaves`（门 B1.07）；输出层 **恰好 3 项** = `outputDirectory` / `runId` / `writeEventsInterval`（门 B1.08，**不进入动力学**）；越界改动 **0**（门 B1.09）。
**惰性诱饵排除**：`dsim.trafficDynamics` 早已是 `kinematicWaves` 且本步**未触碰**（B1.04/B1.12）；生效分支 `controller.mobsim = qsim` 未变（B1.10）；`qsim.inflowCapacitySetting` **未显式覆盖** ⇒ 取 MATSim 默认 **`INFLOW_FROM_FDIAG`**（B1.13，即开启 FD 入口容量约束）。
**继承性硬门**：`f_cap=1.0`（B1.14）、`stuckTime=10`/`removeStuckVehicles=false`（B1.15）、R01 route-choice（B1.21–B1.24）、`pop_W01`/`network_cleaned`（B1.19/B1.20）。
**运行期实证机制生效**：控制台出现 `max flow from fdiag < flow cap in network file` / `The flow capacity will be reduced … 'maxInflowUsedInQsim'` / `storage capacity not sufficient for holes` 告警 ⇒ **KW 约束确在起作用，非空转**。
**仿真侧**：耗时 **177.5 min**（exit=0）；`it.19` linkstats **23.1 MB / 693,575 link**；events **出发 = 到达 = 236,044**（**零滞留**）；14 件冻结输入跑前后 sha256+mtime **`changed=0`**；冻结 W01 配置**未被改写**。

**三层解释（用户冻结框架）**

| 层 | 问题 | 结果 |
|---|---|---|
| **L1 动力学** | 有没有产生动力学变化 | ✅ **有，且很大**：`Sim/Obs` **0.9993348 → 0.8506114（−14.9%，险过 0.85 崩解护栏）**；真实超额 >0.1 链路 **4,705 → 18,860（4.0×）**、里程 **58.19 → 200.87 km**；**总延误 4,778.8 → 12,482.1 h（+7,703 h / +161.2%）**；`A_10:19` **0.8899% → 3.5200%** |
| **L2 连续性** | 有没有形成真正的连续拥堵 | ❌ **没有**：超额连通分量 **3,603 → 8,223（2.3× 更碎）**、最长分量 **0.857 → 0.954 km（仅 +11%）**；**命中 junction-cluster 单元 2,283 → 3,788**（集合大 4×，命中只大 1.7×）；**★超额链路落在候选结构单元内比例 32.54% → 29.45%，富集 1.718× → 1.555×（下降）** |
| **L3 位置** | 堵的位置有没有改善 | ❌ **没有，略变差**：C3 预登记 **lift 1.852× → 1.835×（Δ −0.017×）**；`ABS_unit_vc_0.5` **3.548× → 3.204×**；C2 式 ρ **+0.0267（p 0.200）→ −0.0078（p 0.485）**；辅助（真实超额）口径 lift **1.679× → 1.601×**（同 v1.0 阈值下 **1.527×**） |

**★关键判读（防误读）**：`v/c ≥ 1` 饱和链路 **82 → 10**、饱和里程 **1.151 → 0.271 km** **不是「拥堵减轻」**，而是 **KW 削流 15% 后贴容量链路整体跌破 1.0**；真正反映拥堵的**延误型指标反向暴涨** ⇒ 「**流量掉了、时间长了**」= KW 典型签名。
**次级观察（附警示）**：08–09 小时均值恰落在 FD 入口天花板的链路数 **KW = 0 vs v1.0 = 32**。⚠️ 该指标是**巧合级**（`q_fdiag` 为「速率上限」，小时均值天然低于它），**不得**据此说 KW 无效（告警已证生效）；正确读法 = **KW 的入口约束表现为「排队等待」而非「把小时流量压在天花板上」**。

**延误去向（分类别）**：**`service` 4,509.1 → 10,985.1 h（占 KW 总延误 88.0%、占 Δ 84.1%）**；other 74.9→744.8；motorway 119.6→492.8（`mean_v/c` 反降 0.256→0.231）；ramp 69.9→220.7；connector 5.3→38.7；**CTE 走廊 1.76 → 24.22 h（仅占总延误 0.19%）** ⇒ **KW 未复现唯一真实的快速路排队链**（7.7E 的 CTE ≈0.40 km），主体仍是 20 km/h 单车道接入短段。

**红线遵循（★机制变化 vs 位置改善 严格分离）**：①「KW 改变了拥堵传播机制」= **成立**（**仿真结果即可验证**：Δ延误 +7,703 h、Δ超额里程 +142.7 km、Δ分量 +4,620）；②「KW 让位置更接近真实结构瓶颈」= **不成立**（**必须** C3/C4 空间证据，而 C3 lift 微降、C2 ρ 转负且 p 更高、超额落候选单元比例下降、辅助口径同向）。⇒ 满足前者、不满足后者 ⇒ `KW_POSITION_NOT_IMPROVED`。**「变堵了 ≠ 堵得对了」**。

**对冻结状态的影响 = 无**：7.9B-1 是**实验、未被采纳** ⇒ **v1.0 仍为冻结模型，不产生 v1.1**；冻结输入 sha256+mtime `changed=0`（B1.31/B1.32、L9.01）。⚠️ `Sim/Obs` 的 15% 损失源于 **`SCALE` 未在 KW 下重标定**；按 **7.6F-1 纪律禁止用 `ΣEF/N_sim` 重算 `SCALE`**，故如实报告、不做补偿。
**口径自校验（门 L0.01）**：用冻结模块复算 v1.0 `Sim/Obs` = **0.9993347697**，与冻结值**逐位一致** ⇒ 分析口径与 v1.0 同源。

**★收口结论（用户裁定，2026-09-20）**

> **7.9B 已排除「仅因 QSim `queue` 缺少基础图入口约束而导致城市拥堵缺失」这一单一机制解释。**

三条证据闭环：**① 机制真生效**（唯一模型层改动 + `maxInflowUsedInQsim` 实弹告警）⇒ 不是「改了配置但没走到代码分支」；**② 拥堵形态确实改变**（超额链路 4,705→**18,860**、总延误 4,778.8→**12,482.1 h**、连通分量 3,603→**8,223**）⇒ **不能再把「没有拥堵」简单归因于 `queue` 缺 FD 入口约束**；**③ 决定性一条 = 位置未改善**（落候选比例 **32.54%→29.45%**、lift **1.718×→1.555×**；`CTE` 仅 **24.22 h / 0.19%**、`service` 吃 **88%**）⇒ **很难支持「KW 恢复了正确的快速路回溢机制」**。

**★不得采纳为 v1.1（预登记护栏）**：`Sim/Obs = 0.8506114` **已逼近 0.85 崩解护栏** ⇒ B-1 **只能作为机制诊断实验**，⛔ 不得写入任何参数配置版本。

**★用词更正（C-1 附带）**：B-1 的走廊掩码 `"CTE" in name.upper()` 实际**未命中**字面 "CTE"（v1.0 网络 `name` 中 0 条），其命中集 = `CHANGI ∪ TAMPINES EXP`；`Central Expressway` 正名 = **603 link / 34.55 km**。**7.9C-1 起改用正名**。

### 2.53 Step 7.9C-1 结构性回溢验证 Structural Spillback Validation（**7.9 第五阶段；零仿真只读；硬门 11/11**；判 `SPILLBACK_CHANNEL_INTACT__DELAY_TRAPPED_OFF_MAINLINE`）

**唯一问题（用户冻结）**：为什么真实拥堵结构应出现在 CTE / 主干快速路及其回溢链上，而当前 MATSim 却把大量延误吸收到 `service/connector` 等短段？——C-1 **不**再回答「KW 是否有效」（7.9B-1 已回答）。

**冻结三条证据链**：**真实候选瓶颈 → 上游传播路径 → 下游储存/阻塞能力**；**统一拓扑框架**：`class(motorway/ramp/connector/service/other) × corridor(name) × junction-cluster(unit)`。

**脚本/产物**：`scripts/od/audit_structural_spillback_7_9c1.py`（零仿真只读；11 门）⇒ `reports/structural_spillback_7_9c1/`（**`PREREG_7_9C1.md` 预注册 + `REPORT_7_9C1.md` + 7 件数据产物**）。运行 **23.7 s**。**预注册在读取任何结果前冻结**；主判据为**静态结构量**，仿真延误**仅作对账**（test, not definition）。

**四条检查（预登记阈值 → 结果）**

| ID | 检查 | 阈值 | 结果 |
|---|---|---|---|
| **K1** | 主线→merge/diverge→上游连续可传播路径 | `CHAIN_MIN_M=300 m` | ✅ **完整**：按里程覆盖 **91.52%**；中位链 **1,957 m**（p25 550 / p90 15,537） |
| **K2** | downstream storage 是否足以反向回溢 | `FILL_BLOCK_S=10 s` | ⚠️ **51.02%** 候选 `fill_time<10 s`（中位 9.80 s）；`down_storage` 中位 13.47 辆 |
| **K3** | service/connector 回压死端 | 断点 ≥90% | ✅ **成立 99.95%**（motorway 仅 0.17%） |
| **K4** | 同一物理道路超短 link 碎化 | `SHORT_M=20 m`；重 = `>40 links/km` | ✗ **快速路不碎**（motorway 17.43 links/km、中位 37.8 m、**0** 条 `>40`）；✅ **服务网极碎**（connector **85.01**、service **50.81** links/km） |

**决定性对账（以 `delay_h` 为权）**：v1.0 总延误 **4,778.8 h**，按 class：motorway **2.50%** / ramp 1.46% / connector 0.11% / **service 94.36%** / other 1.57%；KW 总延误 **12,482.1 h**，motorway **3.95%** / **service 88.01%**。
**★延误坐落在 334 m 通道上**（V1 加权 `up_chain_m`；service 内仅 **107 m**、motorway 内 7,921 m）；**v1.0 有 97.34% 的延误落在「无法回压主线」的 link 上**（KW 95.97%）。

**裁决与对假设的回应（诚实报告）**：用户预设的「**网络表达阻断快速路回溢通道**」**未被支持**——主线通道**完整**（K1）、快速路**未碎化**（K4）；被表达方式伤害的是**非主线的接入/服务子系统**（K3+K4 服务网）。⇒ 结论应从「queue / KW 参数不对」改写为 **「拥堵的生成与吸收都被结构性地困在离主线的、拓扑终端的接入子系统里」**。
**★附带发现**：冻结结构先验（C-0）**本身不偏向快速路**——5,490 候选单元中**仅 7.05% 含主线 link**；与 7.9C-0 的 C2（残差不向结构单元富集）叠加 ⇒ **「结构先验」与「实际延误」都不落在快速路上**。

**★对 7.9B-1 的更正（C-1 检出）**：B-1 的「CTE 走廊 1.76 → 24.22 h」**不是 CTE**（`name` 无字面 "CTE"，掩码命中 **Changi ∪ Tampines**）。**正名 CTE**：v1.0 **104.57 h（2.19%）**、KW **56.68 h（0.45%）** ⇒ B-1 三层 verdict 不变，但「KW 未复现唯一真实快速路排队链」的**数值须更正**为 **KW 削弱/转移**了它。已在 `REPORT_7_9B1.md` 追加更正附录。

**对冻结状态影响 = 无**：未重跑仿真、未改参数、冻结件 `changed=0`；**v1.0 仍为唯一冻结模型，不产生 v1.1**。

### 2.54 Step 7.9D-0 接入系统延误滞留审计 Access-System Delay-Trapping Audit（**7.9 第六阶段；零仿真只读；硬门 15/15 + 补充 2/2**；判 `DELAY_TRAP_OFF_MAINLINE_BY_CONSTRUCTION__BASE_RATE_DOMINATED`）

**唯一问题（用户收窄后冻结）**：为什么这些回溢无能的 `service/connector` 短链能持续吸收大量延误，却不能把压力反馈到主线？三接口：`主线容量 ↔ 接入拓扑 ↔ 局部储存`。
**纪律**：先写 `PREREG_7_9D-0.md`（sha256 **`564310dee…6ee85`**，运行期重算 **MATCH=True**）再读任何仿真输出；零仿真结构审计优先，**不改 network、不跑 MATSim**。

**脚本/产物**：`scripts/od/audit_access_delay_trapping_7_9d0.py`（15 硬门 + 2 补充门）⇒ `reports/access_delay_trapping_7_9d0/`（`PREREG_7_9D-0.md` + `REPORT_7_9D0.md` + 8 件数据产物）。运行 **33.0 s**，冻结件 `changed=0`。

**★★决定性发现：base-rate 控制让结论反转**

| class | 全网 km% | 全网 delay% | **全网 ratio** | 邻域 km% | 邻域 delay% | **邻域 ratio** |
|---|---|---|---|---|---|---|
| motorway | 3.73% | 2.50% | 0.671 | 80.15% | **78.42%** | 0.978 |
| ramp | 2.04% | 1.46% | 0.719 | 11.23% | **17.93%** | **1.597** |
| connector | 1.07% | 0.11% | 0.104 | 0.02% | 0.00% | 0.000 |
| **service** | **58.61%** | **94.36%** | **1.610** | 3.10% | **0.53%** | **0.171** |
| other | 34.56% | 1.57% | 0.045 | 5.50% | 3.12% | 0.566 |

`ratio = delay_share / km_share`；邻域 = `d_up ≤ 3`（向上游 ≤3 跳可触达主线）∪ `d_down ≤ 3`，**15,319 links（2.209%）/ 13,125 nodes**。
⇒ **全网 `service` ratio 仅 1.610（<2.50，不构成富集）；限定主线邻域后掉到 0.171（欠表达 8.5×）** ⇒ 主线上**没有**可供下沉的压力；C-1 的 94.36% 是**网络构成假象**。邻域延误的 **96.35%** 落在 `motorway + ramp` 上。

**三条接口审计（预注册 → 结果）**

| ID | 接口 | 判据 | 结果 |
|---|---|---|---|
| **D1** | ① 拓扑单向阀（`mw_in ∧ acc_out ∧ ¬mw_out`） | `VALVE_THR=0.10` | ✗ **证伪**：全岛 sink-valve **仅 13 个**节点（邻域占比 **0.00099**）⇒ `VALVE_PRESENT=False`；旁证 mainline-in 节点 **8,567** vs out **8,566**（8,550 重合）= 主线**几乎完全可逆** |
| **D2** | ② 局部储存深度（`fill_time = down_storage / inflow`） | `REQ_FILL_S=30 s`；`THIN_THR=0.60` | ✅ **成立**：邻域中位 **9.18 s**、**89.81% < 30 s**（全网中位 10.43 s、82.56%）；`service` 单 link 储存中位 **1.55 veh**。**但它是"查表赋值"**：`cap/lanes` 按 `(highway×lanes)` **单值确定**（**13/13** 类型，组内 `min=max`）⇒ `service`=**400**、`residential`=700、`tertiary`=900、`secondary`=1200、`primary`=1500、`motorway`=1900（veh/h/lane）；`cap_ratio_ref`：`service` **0.222**、`connector` 0.722、`ramp` 0.944 |
| **D3** | ③ 排队耦合（延误加权 `d_up`/`d_down`） | `share_off ≥ 0.90` | ✅ **构造性缺失**：延误加权 `d_up` = **72.33 hops**；`share(d_up≤3)` = **0.0278**、`share(d_up>3)` = **0.9722** ⇒ `COUPLING_ABSENT=True`；敏感度稳定（D=1/3/5 → 0.0278/0.0278/**0.0280**） |
| **D4** | 终端暴露（**描述性，无裁决权**；读**冻结输入人口**，⛔ 不用 `output_plans`/`linkstats`） | — | **236,044** 出行：起点在 `service` **0.7068**、终点 **0.6685**、**至少一端 0.9026**（对照 km 占比 0.5861）⇒ **出行的两端都挂在 400 veh/h、20 km/h、≈1.55 车储存的"车道"上** |

**补充分析（非预注册，不改变判决）**：① **hop → 米翻译**（link 中位仅 ~11 m，跳数被碎片化放大）：延误加权**上游距主线 = 1,952 m**；`share(≤300 m)` **0.0315**、`share(>1000 m)` **0.7354** ⇒ **跳数确实夸大，但结论不变**；② 细分辨率容量确定性 **13/13 单值**（预注册的**类别级** `CAP_DETERMINISTIC=False` 因 `other` 合并 5 种 highway，**如实上报**，两者并列记录）。

**判决与旗标**：`VERDICT_RULE = branch2: share_off=0.9722 ≥ 0.90`；
`VALVE_PRESENT=False` / `THIN_STORAGE=True` / `CAP_DETERMINISTIC=False（类别级；细分辨率 True）` / `COUPLING_ABSENT=True` / `BASE_RATE_ARTIFACT=True`。

**对 C-1 的更正（本步提供，已追加到 `REPORT_7_9C1.md` 更正附录）**：C-1 的 K3「回溢无能 99.95%」是**单跳口径的近重言式**（全网仅 **0.049%** 的 `service` link 有主线 feeder）⇒ 升维后 `share(d_up≤3)` 仅 **2.78%**；「延误被吸收到 service/connector」**因果解释被取代**（主线上本无压力可沉）；研究对象**收窄为 `ramp`**（唯一邻域富集类，ratio 1.597，邻域延误 17.93%，延误加权 25.3 跳）。C-1 **verdict 字符串字面不变**。

**CTE 口径（D0.13 断言）**：`name == "Central Expressway"` → **603 links**、v1.0 **104.57 h（2.19%）**、KW **56.68 h（0.45%）**；`"CTE" in name.upper()` **命中 0**（门内断言 `banned_mask_hits==0`）。

**对冻结状态影响 = 无**：零仿真、未改参数、未改 network、冻结件 `changed=0`；**v1.0 仍为唯一冻结模型，不产生 v1.1**。**本步只"证明"，不"修"。**

### 2.55 Step 7.9D-1 Ramp Interface Audit 主线↔ramp↔地方路 接口审计（**7.9 第七阶段；零仿真只读；硬门 11/13 + 补充 3/3**；判 `RAMP_INTERFACE_CONTINUOUS__RAMP_NOT_A_DELAY_HOST`）

**唯一问题（用户收窄后冻结）**：`mainline ↔ ramp ↔ local` 接口在**拓扑与容量上是否连续**，以及 **ramp 延误是否真能传到 motorway**？
**纪律**：先写 `PREREG_7_9D-1.md`（sha256 **`5c8fd9c1…8983`**，运行期重算 **MATCH=True**）再读任何输出；**新增两条永久规则**：**R-DIST-1**（接口距离一律 **meter/km** 为主口径，hop 仅辅助）、**R-MULTI-1**（接口判据**必须多跳**）。零仿真、⛔ 不改 network/capacity、⛔ 不跑 MATSim。
**脚本/产物**：`scripts/od/audit_ramp_interface_7_9d1.py` ⇒ `reports/ramp_interface_7_9d1/`（预注册 + 报告 + 8 件产物）。运行 **19.7 s**，冻结件 `changed=0`。

**★ 单跳口径是近重言式（先排除）**：`motorway_link/trunk_link` **11,740 条（308.15 km）**，单跳邻接分类 **`neither` = 10,886（92.73%）**、`on_ramp` 428 / `off_ramp` 422 / `both` 4 ⇒ **`SINGLE_HOP_TAUTOLOGY=True`**（与 D-0 的 K3 同型，**必须升维多跳**）。

**★ 多跳物理接口 = 连续**：`acc_m`（到主线最短免费流弧长）**有限率 100.00%**；ramp 中位 **478 m** / p90 **1,467 m**；`≤300 m` **30.49%**、`>1000 m` **20.92%**；`egr_m` 中位 **419 m**。⇒ **任意 ramp 片段 100% 可达主线**，无断裂。ramp 链长（到主线残余）中位 **500 m** / p90 1,491 m，单片段中位 **16.6 m**、**58.29% ≤20 m**（碎片化）。

**★ 车道/容量连续**：`on_ramp`（合流侧）**432** 条，`Δlanes`（下游 motorway 车道 − ramp 车道）中位 **+2**、min **−2**、max **+6**；**车道下降仅 8 条（1.85%）**（阈值 0.20 未触发 ⇒ `LANE_DROP=False`）；`Δcap/lane` 中位 **+200 veh/h/车道** ⇒ 合流处是**扩容**而非收窄。ramp 的 `cap/lane` 在**每类 highway 内唯一** ⇒ `CAP_DETERMINISTIC=True`。

**★★ ramp 不是一个延误宿主（本步结论）**：ramp **里程 2.04%**、**车流 9.22%**，但延误仅 **69.9 h（share 1.46%）**、`ratio = 1.46%/2.04% = 0.719`（**<1 ⇒ 欠表达**）、按车流归一 **0.158**（比全网低 **6.3×**）；KW 下 220.7 h（1.77%）。ramp 延误**在物理上确实靠近主线**（延误加权 `acc_m` **647 m**，`≤300 m` 26.75%、`>1000 m` 23.25%；有延误片段 **228** 条）⇒ **耦合方向通、但量太小**。下游节点 `fill_time` 中位 **4.96 s**。

**判决**：`branch3: ramp_share=0.0146 < 0.05 且 delay_weighted_acc_m=647 m ≤ 1000 m`。
**旗标**：`SINGLE_HOP_TAUTOLOGY=True` / `LANE_DROP=False` / `RAMP_IS_DELAY_HOST=False` / `RAMP_NEAR_MAINLINE=False` / `CAP_DETERMINISTIC=True`。

**⚠️ 预注册缺陷（如实上报）**：`R1.05/R1.06` **FAIL**，**与数据无关**——冻结门文写「`finite≥0.999` **且 `min>0`**」，而距离场**种子 = 全部主线 link，按构造距离恒为 0** ⇒ `min>0` **逻辑不可能**（观测 `finite=100%`、`min=0.0`，场本身良构）。**不改预注册**，改列**补充门** `S1.01/S1.02`（良构形式：`finite=100%` ∧ 种子`==0` ∧ 非种子`>0`，**均 PASS**）与 `S1.03`（`cap/lane` 每类 highway 确定，**PASS**）；判决分支只用 `finite<0.99`（False），**verdict 不受影响**。

**对冻结状态影响 = 无**：零仿真、冻结件 `changed=0`；**不产生 v1.1**。**只证明、不修改**。

### 2.56 Step 7.9D-2 Terminal Representation Audit 端点表征审计（**7.9 第八阶段；零仿真只读 + 自由流时间；硬门 13/13**；判 `MIXED__TERMINAL_AND_MAINLINE_COMPARABLE`）

**唯一问题（用户收窄后冻结）**：大量需求是否在**进入主干路网之前**就被 **terminal-access representation** 消耗掉大量**自由流时间**？
**纪律**：先写 `PREREG_7_9D-2.md`（sha256 **`03f24243…3369`**，运行期重算 **MATCH=True**）；⛔ 不改 `service` 容量、⛔ 不改端点吸附、⛔ 不读 `output_plans`（`TT_terminal/TT_trip` 用**全网自由流分解**给出）。
**脚本/产物**：`scripts/od/audit_terminal_representation_7_9d2.py` ⇒ `reports/terminal_representation_7_9d2/`。运行 **27.5 s**，冻结件 `changed=0`。

**★ 端点分布**（236,044 出行，冻结输入人口）：O 落 `service` **0.7068**、D **0.6685**、至少一端 **0.9026**（`expansionFactor` 加权 O 0.7170 / D 0.6687）；按**道路组**：O `local` **0.9011** / `arterial` 0.0859 / `ramp` 0.0107 / `mainline` 0.0023，D `local` 0.8131 / `arterial` 0.1592。

**★ 自由流接入时间**：`T_acc`（起点→主线）中位 **124.8 s**（p90 219.2，加权均值 137.6）；`T_egr` 中位 **103.6 s**；`T_terminal_lb` 中位 **234.3 s**（≈3.9 min）、p90 **417.8 s**。

**★★ 全网自由流时间分解（主口径）**：总 **24,905.2 车·h**，off-mainline **14,146.7** ⇒ **`share_offmain = 0.5680`**（实际时间口径 **0.6364**；KW 交叉 **0.6049**）⇒ 落在 `[0.50,0.70)` ⇒ 判 `MIXED`。

**★★ 最重要发现：非主线时间由干道主导，不是 `service`**：ff 时间份额 **mainline 0.4320 / arterial 0.3787 / local 0.0998 / ramp 0.0895**；其中 **`service` 仅 0.0515**。⇒ **端点暴露面（90% 在地方路）≠ 时间面（地方路仅 10%、`service` 仅 5.15%）**——`service` link 太短（中位 8.9 m），**把矛头指向 `service` 的 400 veh/h 会指错对象**。

**★ `service` 表征精度修正**：`cap/lane` **严格唯一 = 400**（`SERVICE_CAP_FIXED=True`）；但自由流速度**不是严格恒定**——**10 个不同值 {5,10,15,20,25,30,40,50,60,70} km/h**，其中 **20 km/h 占 96.80%**（中位 20.00、均值 20.58）⇒ `SERVICE_SPEED_FIXED=False`。D-0「自由流被硬编码为 20 km/h（p10=p90）」**仅在 p10=p90 意义上成立**，本步以 `False` **如实上报**。

**判决**：`branch4: share_offmain=0.5680 ∈ [0.50,0.70)`。
**旗标**：`ENDPOINT_SERVICE_DOMINANT=True` / `TERMINAL_IS_SERVICE_90=True` / `OFFMAIN_MAJORITY=True` / `SERVICE_CAP_FIXED=True` / `SERVICE_SPEED_FIXED=False`。

**对冻结状态影响 = 无**：零仿真、未改容量/吸附、冻结件 `changed=0`；**不产生 v1.1**。**只证明、不修改**。

### 2.57 Step 7.9E-0 Arterial-Layer Delay Attribution Audit 干道层延误归因审计（**7.9 第九阶段；零仿真只读；硬门 11/12**；判 `ARTERIAL_LAYER_AUDIT_BLOCKED`）

**唯一问题（用户冻结）**：`primary / secondary / tertiary` 干道是否才是当前模型 off-mainline 时间与空间残差的主要承载层？
**纪律**：先写 `PREREG_7_9E0.md`（sha256 **`4fa98a96…12ea08f1`**，运行期重算 **MATCH=True**，哈希门置于一切之前）；零仿真、不改网络/容量；E4 用**一次多源反向 Dijkstra**（非每条 link 各搜一次）。
**脚本/产物**：`scripts/od/audit_arterial_delay_7_9e0.py` ⇒ `reports/arterial_delay_attribution_7_9e0/`（含 `e0_checks/class_summary/residual_coupling/residual_permutation/topology_summary/input_manifest/summary` + `STEP7_9E0_REPORT.md`）。运行 **22.1 s**，冻结件 `changed=0`。

**★ 固定分组**：`arterial_core = primary∪secondary∪tertiary`（68,882 links / 2,050.7 km）；`mainline = motorway∪motorway_link`（13,770 / 622.5 km）—— ⚠️ **本步 `mainline` 不含 `trunk`**，与 D-0/D-2 不同 ⇒ `off_mainline`（679,805 / 14,504.0 km）**不与 D-2 的 `share_offmain=0.5680` 直接可比**。

**★★ E1 时间归属（两基数结论相反）**：`ff_time_share`（结构）`service` **0.7924** vs arterial 0.0676；`wff_share`（**车时加权**）**arterial_core 0.6371**、primary 0.4649、trunk 0.1586、service 0.0889 ⇒ **干道是 off-mainline 时间的绝对主场**。

**★★ E2 延误归属（干道不是延误主场）**：`delay_share` `service` **0.5710** > arterial_core **0.2978**（primary 0.2149）；`delay_ratio`（vs 结构）primary **8.40** / trunk **12.48** / arterial **4.41** vs service 0.72（干道"富集"）；但 `delay_ratio_weighted`（vs 车时）service **6.43** vs arterial **0.47**（service"富集"）⇒ **单一 ratio 随基数翻转**，§5.1 要求三者同报。

**★ E3 空间残差 → BLOCKED（硬门 E0.09 FAIL）**：576 断面 `dominant_highway` = motorway **449** + motorway_link **92** + service 16 + primary 9 + … ⇒ **arterial 断面仅 12（<30）**。欠功率参考（**不作判据**）：arterial mean residual **+0.0776** vs non +0.1434、置换 `p(region)=0.8534` / `p(pa)=0.8256`、`Spearman=−0.0213` ⇒ 无耦合信号。**★新事实：冻结靶场 77.8% 为 motorway/motorway_link ⇒ 靶场快速路中心化，天生不可分辨干道残差。**

**★ E4 拓扑（一次多源反向 Dijkstra，物理距离为主）**：arterial_core 到 mainline 中位 **1,309.9 m**、p90 2,324.5 m、`≤300 m` 仅 **5.32%**、`hop_median 52`（辅）、回搜上限 3,000 m 内可达 **84.37%**；延误加权 **1,297.1 m**。对照 ramp **478 m**（D-1）⇒ **arterial 深居 off-mainline 内部，不是接口/膜层**。空间一致性：抽样 12,242，中位(拓扑/直线) **2.007**、违规 **2.12%**。

**判决**：`ARTERIAL_LAYER_AUDIT_BLOCKED`（硬门 **11/12**，唯一 FAIL = E0.09）。**旗标**：`ARTERIAL_OVER_REPRESENTED_IN_DELAY=True` / `ARTERIAL_IS_MAX_DELAY_SHARE_OFFMAIN=False` / `ARTERIAL_RESIDUAL_COUPLED=False` / `DOMINANT_OFFMAIN_DELAY_BUCKET='service'`。
**★ §5.3 纪律**：本步至多得「arterial 承载 63.71% off-mainline 时间」；**不得**推出「干道容量赋值错误」——需**独立容量审计**（同 D-0 对 `service=400` 的处理）。
**对冻结状态影响 = 无**：零仿真、未改容量/吸附、`changed=0`；**不产生 v1.1**。**只证明、不修改**。

### 2.58 Step 7.9E-1 Arterial Observability Expansion 干道可观测性扩展（**7.9 第十阶段；零仿真只读 + 独立 diagnostic crosswalk；硬门 10/12**；判 `OBSERVABILITY_BLOCKED`）

**目的（用户裁定）**：7.9E-0 的 E0.09（arterial 断面 **12 < 30** ⇒ BLOCKED）只是「靶场对 arterial 欠功率」的**表象**。本步用**全部 1,278 条有几何的 LTA TrafficFlow 链路**（1,311 unique LinkID 中）建立一张**独立 diagnostic crosswalk**，回答：arterial 不可观测是**匹配质量问题**还是**靶场定义域问题**。⛔ 不替换、不回写 7.3.6A 正式 crosswalk；⛔ 不改冻结 target；⛔ 不跑 MATSim/Java。

**脚本**：`scripts/od/audit_arterial_observability_7_9e1.py`（内嵌 PREREG sha256 门；E1.02 用 **AST 静态自审**）。**预注册**：`reports/arterial_observability_7_9e1/PREREG_7_9E1.md`（sha256 `4d5ee3e1…6751d`，运行期重算 **MATCH=True**）⇒ **12 件产物**。

**方法**：SVY21 中沿 LTA 折线 **50 m** 采样（5–25 点）→ MATSim directed-link midpoint KD-tree（半径 **80 m**）→ 逐候选算几何距离 / 方向差 / 名称相似度 / `RoadCat↔highway` 语义兼容 ⇒ **A 严格（≤25 m ∧ ≤30° ∧ 语义兼容）/ B 方向几何（≤50 m ∧ ≤30°）/ C 仅几何（≤80 m）** 三档置信；主分析 **A+B**（优先 A），C 仅 sensitivity。

**★可观测性——匹配质量不是瓶颈**：A+B 覆盖 **97.48%**（1,278/1,311，**已达上界**——33 条无任何几何的链路天生不可匹配）、匹配距离中位 **0.57 m** / p90 **2.92 m**、方向差中位 **1.38°**。**LTA 功能类 → OSM**：`CATA`→motorway **97.35%**；`CATB`→primary **65.93%** / trunk **21.29%** / secondary **11.04%**；`CATC`→secondary **41.30%** / primary **28.26%** / tertiary **28.26%**；`CATD`→tertiary **71.43%**；`CATE`→service；`SLIP_ROAD`→motorway_link **97.61%**。**全量 1,278 条可标出 542 条 `arterial_core`**（CATB 490 + CATC 45 + CATD 6 + CATA 1）。

**★★根因：冻结靶场的定义域不含 arterial**。576 个残差断面的 `RoadCat` **只有 `CATA` 326 + `SLIP_ROAD` 250**；其 A+B 代表链路为 `motorway` **328** / `motorway_link` **247** / `primary_link` **1** ⇒ **arterial residual n = 0（A / A+B / A+B+C 三档全为 0）**。⇒ E0.09 的 12 个「arterial 断面」实为按 `dominant_highway` 标记的 **CATA/SLIP_ROAD** 断面，独立几何匹配后全部落在 ramp/主线。

**判决**：`OBSERVABILITY_BLOCKED`（硬门 **10/12**，**24 s**）。唯二 FAIL = **E1.09**（`valid_residual=576; arterial=0`）/ **E1.10**（`AB_arterial_residual_n=0 < 30`）——**均为真实结构结论，非执行错误**。敏感度三档：`A_STRICT` 95.19% / `A+B_MAIN` 97.48% / `A+B+C_RELAXED` 97.48%（**C 档未增加任何匹配**）。

**因果链修正**：E-1 把「arterial 不可判」的归因从「靶场欠功率（表象）」推进到「**靶场定义域 = 高速+匝道，arterial 断面数恒为 0（结构）**」。⇒ 想检验 arterial 是否残差主场，**必须把断面域从 `CATA+SLIP_ROAD` 扩到 `CATB/CATC/CATD/CATE`**（= 新版本 / 新诊断域），**不是**放宽匹配阈值。

**新永久规则**：`R-OBS-1`~`R-OBS-5` —— ① 正式 calibration crosswalk 与 diagnostic observability crosswalk **永久分离**；② `RoadCat → highway` 语义映射**只作诊断**、不得事后制造动脉样本；③ 主分析用 **A+B**、C 仅敏感度；④ **任何「某类别是否残差主场」的判断必须先证明该类别具备足够观测性**；⑤ 匹配质量须**同时报 coverage / distance / direction**。

**对冻结状态影响 = 无**：零仿真、未改网络/容量/需求/route-choice、未新建在线文档；**不产生 v1.1**。**只证明、不修改**。


### 2.59 Step 7.9E-2 Expanded Diagnostic Residual Domain 扩展诊断残差域（**7.9 第十一阶段；零仿真只读 + 复用 E-1 独立 diagnostic crosswalk + 冻结 SCALE 口径**；**硬门 12/12**；判 `NO_ARTERIAL_COUPLING_SIGNAL`）

**目的（用户裁定）**：E-1 已证「arterial 不可观测」的根因是**冻结靶场定义域只覆盖 `CATA` + `SLIP_ROAD`**。本步在**不替换 7.3.6A** 的前提下，把**诊断**断面域扩到全部可观测 TrafficFlow LinkID（1,311 unique），用与 7.7C-0 / 7.3.6B **完全相同的 `Sim/Obs/SCALE` 口径**（`sim_section = median(matched directed links HRS8-9avg) × SCALE`，`SCALE = 459794/200000 = 2.29897`；`obs = 工作日 HourOfDate=8 的 median Volume`）构造 `diagnostic_residual = Sim/Obs − 1`，首次让 arterial 空间残差**可检验**。⛔ 不重新匹配（直接复用 E-1 `e1_crosswalk_candidates.csv`）、⛔ 不改 7.3.6A / 网络 / 容量 / demand / route-choice、⛔ 不跑 MATSim/Java。

**脚本**：`scripts/od/audit_expanded_residual_7_9e2.py`（内嵌 PREREG sha256 门 + **AST 零仿真自审门**）。**预注册**：`reports/arterial_expanded_residual_7_9e2/PREREG_7_9E2.md`（sha256 `c9e68272…e6cc`，运行期重算 **MATCH=True**）⇒ **12 件预注册产物 + 3 件事后补充产物**。

**★可观测性问题已解决**：A+B 覆盖 **97.48%**（1,278/1,311 **上界**）、有效残差 **1,278**、**arterial 残差 n = 542**（E-0 仅 12），匹配中位 **0.57 m** / p90 **2.92 m**。三档敏感度 `A_ONLY` 1,248（art 538）/ `A+B_MAIN` 1,278（art 542）/ `A+B+C_RELAXED` 1,278（art 542）⇒ **C 档仍不增加任何匹配**，结论不依赖 crosswalk 严格程度。

**★formal bridge（方法一致性，`R-RES-1`）**：与冻结 7.7C-0 的 576 断面 overlap **576/576**、Spearman **0.9662** / Pearson **0.9398**、mean bias **+0.0229**、MAE **0.0722**、RMSE **0.4655** ⇒ 诊断残差与正式残差**高度一致**（RMSE≫MAE ⇒ 重尾，少数断面差异大）。

**判决**：`NO_ARTERIAL_COUPLING_SIGNAL`（**硬门 12/12**，**60–73 s**）。pooled：arterial 均值 **+0.0027** vs 非 arterial **+0.0904**；Spearman **−0.0216**、η² **0.0013**；非分层置换 `p = 0.1969`（不显著）；**RoadCat 分层置换 `p = 0.05247`（≥0.05 ⇒ 按冻结规则判「无信号」，但仅高于阈值 5%）**。

**⚠️ 必须同时报告的事后稳健性（明确标注、不改变冻结判决）**：分层统计量被**退化层**主导——CATA 层内唯一「arterial」是 LinkID **26827**（AYER RAJAH EXPRESSWAY，被诊断映射成 `primary`、`sim=0.0` ⇒ 残差 **−1.000**），**单独贡献分层统计量的 69.3%**。⇒ ① 限定有效混合层（`n≥30 ∧ 双臂≥5` ⇒ 仅 **CATB**：490 art vs 144 non）`p = 0.0080`；② 去掉 CATA 后 `p = 0.0400`；③ 去掉 CATB（唯一有效层）则 `p = 0.1679`。⇒ **分层 p 的显著性完全取决于如何处理退化层**。

**★★ 真正的结构发现：残差不是「arterial vs 非 arterial」，而是按道路等级的单调梯度**（A+B，flow-weighted）：`motorway` **+2.0%** / `primary` **+7.6%**（高估）；`motorway_link` **−6.3%** / `trunk` **−20.2%** / `secondary` **−34.6%** / `tertiary` **−41.7%**（**低估且随等级下降单调加深**）。⇒ **`arterial_core = primary ∪ secondary ∪ tertiary` 三类残差符号相反（primary 正、sec/ter 负）⇒ 该聚合量存在符号抵消，聚合均值（+0.0027 ≈ 0）是抵消伪影，不可用作「arterial 是否残差主场」的依据。** 同理 CATB 层内「arterial 好、非 arterial 差」实为 **arterial vs `trunk`** 的对比（CATB 的 144 条非 arterial 中 `trunk` 占 135）。

**新永久规则**：`R-RES-1`~`R-RES-6` —— ① 正式 calibration residual 与 expanded diagnostic residual **永久分离**；② expanded residual **只作结构归因、⛔ 不得进入 v1.0 target**；③ section 级模拟流量**必须用 matched directed links 的 median 再乘冻结 SCALE**（⛔ 不可先求和再比单条 LTA 断面）；④ arterial coupling **必须同时控制 / 报告 LTA RoadCat 组成**；⑤ **LTA 功能类（CATA–E / SLIP_ROAD）与 OSM 结构类（motorway/primary/…）永久分开表述**，⛔ 不得声称 `CATB/CATC/CATD/CATE == primary/secondary/tertiary`；⑥ **只有通过 observability gate 的道路层才允许进入 mechanism attribution**。

**决策树（用户冻结）**：`7.9E-2 ✓ → ├─ arterial residual coupling 明显且稳定 → 7.9E-3 arterial mechanism audit；├─ 无耦合 / 仍不稳定 → service / endpoint mechanism；└─ 仍 BLOCKED → 外部 LTA 数据申请`。本步落 **「无耦合 / 仍不稳定」** 分支（`p = 0.0525` 临界 + 梯度结构未决）⇒ **下一候选须重新裁定**。

**对冻结状态影响 = 无**：零仿真、未改网络/容量/需求/route-choice、冻结件 `changed=0`；**v1.0 仍为唯一冻结模型、不产生 v1.1**。

### 2.60 Step 7.9G-0 `service` 延误机制 R0 结构审计（**7.9 第十二阶段；零仿真只读；硬门 25/25；EXIT=0；`CLOSURE=OK`；`converged=True; it=4`**；判 Q1 `CAPACITY_CONSTRAINT_NOT_DOMINANT` / Q2 `CALIBER_FRAGILE` / Q3 `SERVICE_PARAMS_DERIVED`）

**定位（用户裁定 2026-09-28）**：`Q4-R1-R1` READY 后关闭 `Q4-R1` 线，进入 **`service` 延误机制**（与已收口的几何匹配线属**不同层面**的残差解释）。**边界 = 只审计、不改模型**：⛔ 不碰 v1.0 与 Q4-R1-R1 产物、⛔ 不改 `service` 400 / 端点吸附 / 网络 / 容量 / demand / route-choice。

**预注册**：`reports/service_delay_mechanism_7_9g0/PREREG_7_9G0.md`（14,221 B，sha256 `2db351c8…f49b51`），运行期重算 **MATCH=True**；锁定对象定义、三核心问题、指标、排除规则、**硬门 25**、判决闭集、**负例 N1–N11**、必需输出 14 件、BLOCKED 条件。**脚本**：`scripts/od/audit_service_delay_mechanism_7_9g0.py`（48,460 B，sha256 `61cfe26a…569dfd`）。

**冻结输入（5 件，跑前后 sha256+mtime 逐位未变）**：`W01_rc_min/ITERS/it.19` linkstats（22,629,291 B）/ `W01_events` linkstats（与之逐字节相同）/ `W01_events.output_links.csv.gz` / `network_links_source_copy.csv` / `config_W01_rc_min.xml`。**只读对照（3 件）**：7.7E 审计 summary / roadtype_quant / sat_links。

**口径（继承 7.7E，不可改）**：`ff_s = LENGTH/FREESPEED`；`ff_ceil_s = ceil(ff_s − 1e-9)`；**`delay_corr_h = Σ_{v>0} v·max(0, TT8-9avg − ff_ceil)/3600`**（canonical）；`delay_raw_h` 用 `ff_s`（未扣量化）。饱和定义 `v ≥ CAPACITY×0.9999`。

**★Q1 = `CAPACITY_CONSTRAINT_NOT_DOMINANT`（容量不是主因）**：已载流 `service` link **62,407** 条，`v/c` 中位 **0.0225** / p90 **0.1325**；饱和仅 **74 条 = 0.1186%**，**这 74 条只承担 `service` 延误的 13.95%**（判据 `sat_delay_share ≥ 0.50` ⇒ 未达）⇒ **延误主要由大量未饱和短段的时间量级产生**，而非容量约束。集中度 **top-10 = 62.17% / top-100 = 96.01%**（少数 link 吃掉大部分延误，但与被饱和无关）。长度分桶：`>60 m` 占 **29.02%**（per-veh 58.8 s）、`≤5 m` 占 24.68%。

**★Q2 = `CALIBER_FRAGILE`（口径脆弱，须四面并报）**：`raw` **45.903769%** vs `corr` **94.356579%**（≈ 7.7E 的 94.4%）；**暴露面四面** time **94.36%** / count **27.81%** / distance **18.56%** / volume **4.31%** ⇒ **同一数据相差 20 倍以上**。跨时段 corr：07-08 **92.79%** / 08-09 **94.36%** / 09-10 **98.52%** / 10-11 **99.999%** ⇒ 极差 **0.0573 > 0.05** ⇒ **判 `FRAGILE`（不判 STABLE）**。⛔ 门 16 为**「已计算 + 判决自洽」执行门**，`FRAGILE` 是**合法结论、不使节点 BLOCKED**（此即首跑 E1 修正）。

**★Q3 = `SERVICE_PARAMS_DERIVED`（参数是派生的实现量，不是机制旋钮）**：`cap = 400 × permlanes` 对 `service` **100.000%（450,486 条，对角 crosstab）**；全网络 `cap = unit_cap[highway] × lanes` **99.689%**；`qsim` 两因子 = 1.0、`linkDynamics=FIFO` ⇒ **qsim 无覆盖 ⇒ 容量是派生量**。真正输入只有 `permlanes`（1–6；1 车道占 296,513 = 65.8%）、`unit_cap[service]=400`、`freespeed`（10 个取值）⇒ **`service` 参数不能直接当旋钮；后续敏感性须在「网络表征 / 端点吸收」层设计**。

**★工程验证（全第一手）**：基线 **25/25、EXIT=0、`converged=True; it=4`、`CLOSURE=OK`**；**负例 11/11 全部按预期门触发**（N1→05、N2→06+07、N3→08+10、N4→10、N5→12、N6→16、N7→17+19、N8→22、N9→21、N10→25、N11→15）；**BLOCKED 3/3 完整节点**（25 行 checks + 6 文件 + EXIT=1）；**独立复核** `scripts/od/_verify_g0.py`（不复用被测脚本、独立重算）⇒ **`VERIFY_OK=True`**（share Δ=2.84e-14、sat_share / Q3 / 三方一致、manifest 字节一致、8 件冻结件未变）。**★本轮自查 5 处**：E1 门 16 把合法 `FRAGILE` 判成 BLOCKED（改「已计算+自洽」）、E2 门 24 与写入状态自引用振荡、E3 `manifest↔closure` 互引用 2-循环、E4 `summary` 头条数字漏赋值写成 0.0、E5 复核脚本自身少乘 `service` 掩码（82 vs 74）。

**新永久规则 `R-G0-1…5`**：① **「发现门」≠「执行门」**——门禁不得编码期望科学结论，否则合法负结果会把节点误判 BLOCKED；② **manifest 不得自哈希且不得含 closure**（防 2-循环）；③ **写入终局状态的判据必须排除决定该状态的门自身**；④ **汇总件数字必须与分解件同源**（漏赋值 ⇒ 0.0 静默失真）且有门禁约束；⑤ **占比必须并报暴露面**（time/count/distance/volume 可差 20 倍）。

**对冻结状态影响 = 无**：零仿真、未跑 MATSim、未改网络 / 容量 / demand / route-choice、冻结件 `changed=0`；**v1.0 仍为唯一冻结模型、不产生 v1.1**。产物 `reports/service_delay_mechanism_7_9g0/`（15 件）。

### 2.61 Step 7.9G-1 端点/接入子系统「就地吸收」机制审计（**7.9 第十三阶段；零仿真只读；硬门 25/25；EXIT=0；`CLOSURE=OK`；`converged=True; it=3`**；判 A1 `PROPORTIONAL_TO_MILEAGE` / A2 `ENDPOINT_LOCALIZED` / A3 `NOT_MAINLINE_QUEUE` / A4 `NEITHER_BOUND` / A5 `NEGLIGIBLE` / A6 `ENDPOINT_ABSORPTION_DOMINANT`）

**唯一可证伪机制命题（用户裁定原文）**：`service` 延误是否主要表现为**端点接入 / 局部循环 / 短链时间表达**形成的**「就地吸收」**，而非道路容量约束产生的**排队**延误。
**审计链（冻结）**：`service link → population/OD endpoint → connector/access → mainline interface → short-link accumulation → terminal/local circulation`。
**边界（继承 G-0，作为前置约束）**：⛔ 不得把 `94.36%` 当单一证据；⛔ 不得把 `cap=400` 当敏感性旋钮；⛔ 不改 `Singapore_OD_MATSim_Final_v1.0`；先 `prereg` 再零仿真。

**脚本 / 产物**：`scripts/od/audit_endpoint_access_absorption_7_9g1.py` + 冻结 `reports/endpoint_access_absorption_7_9g1/PREREG_7_9G1.md`（**17,536 B**，sha256 `4e7ffa3c…`）⇒ **16 件产物**（含 `g1_checks.csv` / `g1_summary.json` / `g1_closure_check.csv` / `g1_input_manifest.json` / `STEP7_9G1_REPORT.md`）。**运行 340.8 s**（events 14.75 GB / 331.8 s）。冻结输入 **7 件**（pop / plans / events / ls_final / ls_viz_ref / net_links_runtime / src_copy）+ 只读对照 **4 件**（G-0 产物）。

**六个答案（第一手复算）**

| 问 | 判决 | 证据 |
|---|---|---|
| A1 端点是否被"吸附"到 `service` | `PROPORTIONAL_TO_MILEAGE` | `p_end_svc` **0.692865** vs 里程基线 **0.586090**、计数基线 0.649513 ⇒ enrich **1.1822× < 1.5** ⇒ 仅**轻度富集**，**不是**"吸附伪影" |
| A2 就地吸收：端点 vs 遍历位置 | `ENDPOINT_LOCALIZED` | `f_pos`（service 遍历首/末位占比）**0.088818**；`w_ep`（端点链延误份额／`service`）**0.756366**；`v_ep`（端点链流量份额／`service`）**0.097730** ⇒ **75.6% 的 `service` 延误落在只占 9.8% 流量的端点链上** |
| A3 干道接口排除 | `NOT_MAINLINE_QUEUE` | 邻接干道的 `service` 仅担**全网 1.8736%** vs 内部 `service` **92.4830%** ⇒ **不是主线回溢** |
| A4 绑定约束：流量容量 vs 储存微胞 | `NEITHER_BOUND` | `D` 集 422 条（端点 `service` 且有延误）：`sat_share_D`（`v/c_flow≥0.9999`）**0.1394**、`cell_share_D`（`storage_veh<2`）**0.4961** ⇒ 两者均 **< 0.50** |
| A5 局部循环 | `NEGLIGIBLE` | `f_local`（全 local 路由占比）**0.001296**（306/236,044）⇒ **可忽略** |
| A6 机制汇总 | `ENDPOINT_ABSORPTION_DOMINANT` | `s_end` **71.3681%** / `s_mid` **22.9884%** / `s_main` **1.8736%** ⇒ **端点就地吸收主导** |

**★核心量（端点 service 切分）**：`endpoint_service` **10,156** 条（296.4 km）担延误 **3,410.52 h = 全网 71.37% ／ `service` 内 75.64%**，却只占 `service` 流量 **9.77%** ⇒ **逐车延误 72.81 s/veh vs 非端点 2.54 s/veh（28.7×）**。集中度：端点 `service` 的 **top-10 = 全网延误 58.66%**、top-100 = **71.27%**（端点 service 内 `top10_ep` = **82.20%**）。
**★暴露四面（与 G-0 完全一致，重申 `CALIBER_FRAGILE`）**：time **94.36%** / count **27.81%** / distance **18.56%** / volume **4.31%**。
**★路由位置剖面（决定性对照）**：`service` 遍历 first 166,835 / last 157,791 / mid 3,330,324 ⇒ 首末位仅 **8.88%**；**全 local 路由 0.13%** ⇒ **"位置效应"与"局部循环"两条支路被证伪**，但**端点链归属**（A2）成立。
**★events 逐车轨迹（A7 仪器，命中 24,293 事件）**：12 条 target 链 `n_enter ≥ 1` 全齐；**`dwell_p50` 高达 280–6,423 s**，而链长仅 **1.9–140.8 m**、自由流 `ff_s` **0.62–25.3 s** ⇒ 车辆"停"在几米到百米级的 `service` 链上**数十分钟** ⇒ 与**「就地吸收／储存微胞耗尽」一致**，与**「道路容量排队」不一致**。

**核心结论**：G-0 把"容量瓶颈"排到次要位置后，G-1 给出替代机制 —— `service` 延误**不是**道路容量排队、**不是**主线回溢、**不是**全局部循环；它**几乎全部落在直接承载人口/OD 端点的 10,156 条微短链上**（`service` 总延误的 75.6%；按逐车计 28.7×）。⇒ **站点/接入子系统的「就地吸收」** 是残差的机制归属。

**验证**：负例 **11/11** 全触发、BLOCKED **3/3** 完整节点、独立复核 `VERIFY_OK=True`（7 件冻结件未变 / prereg 恒等 / 独立 canonical 重算 / 独立端点抽样 40k / 独立契约抽样 40k / 25 门有序 / manifest 字节一致且不自含 / closure OK / 6 判决 ∈ 闭集）。
**本轮自查 4 处（E1–E4，均在交付前修复）**：**E1** `CONTRACT` 键错——被赋成 `link→权重`（`home_w`）而 `scan_plans` 按 **person id** 查 ⇒ 契约恒 `0/0/236044`，**门 10 自抓**；修：`load_population` 增 `home_p/work_p`（person→link）。**E2（同源）** `data.split(b"<person ")` **吃掉前缀** ⇒ `re.compile(rb'<person id="…"')` 永不命中 ⇒ `pid` 恒空；修：改 `rb'\A\s*id="([^"]+)"'`（抽样 5000/5000 = 1.000000 验证）。**E3** `events_trace` 性能（`gzip` 模块仅 **33 MB/s**，14.75 GB 需 447 s+）⇒ 改 **`zlib.decompressobj(31)`**（**348 MB/s**，纯解压 42.4 s）＋正则由「全事件 1.63e8 迭代」改「仅命中目标链」⇒ 事件段 **666 s → 331.8 s**。**E4（负例设计缺陷）** N9 首跑把 `a4` 写死为 **`NEITHER_BOUND`**——而**真值恰为 `NEITHER_BOUND`** ⇒ **空负例（no-op）**，不产生任何可观测变化、门 17 自然不触发 ⇒ 被负例套件自抓（`fired=False`）。修：改为**与规则相矛盾**的 `FLOW_CAPACITY_BOUND`（重跑 ⇒ `A4=FLOW_CAPACITY_BOUND`、门 17 FAIL、24/25、BLOCKED、`fired=True`）。
**★R-G1-1…8（新增纪律）**：①**大 `.gz` 一律 `zlib.decompressobj(31)`**；②**`bytes.split(b"<tag ")` 吃掉前缀 ⇒ 后续 regex 不得再含该前缀**；③**缓存仅用于不绕过被测函数的负例**（打 `scan_plans`/`events` 的负例必须关 `--cache`）；④**A 类判决须同报四面暴露**（time/count/km/vol）；⑤**机制判决须"位置面 vs 延误面"分列**（`f_pos` vs `w_ep`），不可只报一个；⑥**"就地吸收"须逐车口径复核**（`s/veh`），不能只看份额；⑦**机制闭集必须含否定分支**（`NEITHER_BOUND`/`NEGLIGIBLE`），不得只用单一 `share` 阈值；⑧**负例必须"改变可观测结果"**——把变量写死为**真值**是 no-op 空负例，只证明"没抓到"而非"能抓到"；**必须取与规则相矛盾的取值**，并在套件里对 `fired=False` 视为失败（不得静默通过）。
**对冻结状态影响 = 无**：零仿真、冻结件 `changed=0`；**v1.0 仍为唯一冻结模型，不产生 v1.1**。

### 2.62 Step 7.9G-2 「时间 / 数量 / 距离 / 体积」四面口径统一（**7.9 第十四阶段；✅ `CALIBER_HARMONIZATION_R0_READY`；零仿真只读；硬门 25/25、EXIT=0、`CLOSURE=OK`、`converged=True; it=3`、47.8 s；prereg `6df55c42…`、22,238 B**）

**用户裁定（2026-09-28）**：`7.9G-2 = OPEN`。**本轮只解决「怎么统计、怎么表达」，不重新争论 G-1 的机制结论** —— ⛔ 不重判 `A1–A6`、⛔ 不提新机制假说、⛔ 不以 G-2 结果确认或削弱 `A6`。

**为什么必须做这一步**：G-0 已证 `94.36%` 对口径极其敏感（raw `45.90%` vs corr `94.36%`），故不得再以单一 `delay share` 作系统性归因。G-2 的目标**不是**再得到一个"更大的百分比"，而是建立一套**四面一致的 reporting rule**，并物化一句可长期复用的表述。

**锁定的 5 件事**：
1. **分母统一** —— 三档嵌套分母栈 `D0 = ALL ⊃ D1 = SVC ⊃ D2 = EP_SVC`；任何份额必须写成 `share[face, scope | Dk]`，三要素缺一不可。
2. **宇宙必须声明** —— 默认 `U_loaded`（`vol = HRS8-9avg > 0`）；在 `U_any` 上计算的量**必须带 `_any` 后缀**；⛔ 分子/分母不得跨宇宙。
3. **暴露 ≠ 影响** —— `IMPACT = {time}`（`delay_corr_h`）、`EXPOSURE = {count, distance, volume}`；三档强度面 `s/link`、`s/km`、`s/veh` **必须与份额面并列**。
4. **不合成总分** —— ⛔ 禁止跨面加权/归一总分、禁止跨面求和；四面回答的是不同问题。
5. **集中度判据预先锁定** —— 仪器 = **覆盖率分数** `f_t = k_t / n_scope`（`t ∈ {50, 90, 99}`）；判据 = 与 `D0` 的倍率 `R_t`，阈值 `RATIO_CONC_MIN = 3.0`；⛔ **Gini 禁用**、⛔ **常数 `k`（`top-10` 类）禁用**。

**零仿真侦察（第一手，已用于锚定 prereg 判据）**：
- **★(a) 宇宙撕裂可产生 >100% 的份额** —— `SVC_any` 的 km = `ALL_loaded` km 的 **170.96%**（分子含零流边、分母只含 loaded）⇒ 硬失效，须由门 10 捕获。
- **★(b) 同一对象 / 两种宇宙 / 两个 distance share** —— `g1_endpoint_service_split.csv` 的 `length_km = 296.402`（`U_any`，10,156 链）vs `U_loaded` 下 EP_SVC 重算 **203.385 km**（7,083 链）⇒ share **5.716%** vs **3.922%**，差 **1.79 pp** > `UNIVERSE_SPREAD_TOL_PP = 0.5`。
- **★(c) Gini 在本分布下失效** —— `ΔGini(EP_SVC − ALL) = −0.0014`（`ALL` 0.999541 / `EP_SVC` 0.998174），**无区分度且符号反直觉**（会推出"端点链更不集中"）⇒ 不得作判据。
- **★(d) 覆盖率分数有区分度且尺度无关** —— `f50`：ALL **0.000036** → SVC **0.000112** → EP_SVC **0.000706**（倍率 **19.6×**）；`f90` 倍率 **6.65×** ⇒ 在子集内部延误**相对更分散**，恰好回应「不能因为 top-10 link 占 62% 就直接宣布高度集中」。
- **★(e) 强度面** —— `s/veh`：ALL **0.4300** / SVC **9.4073** / EP_SVC **72.8065**（EP_SVC/ALL = **169.3×**），与 `vol 0.42%` vs `time 71.37%` 的份额反差同向。

**四面侦察实测（EP_SVC ｜ D0，`U_loaded`）**：time **71.3681%** / count **3.1560%** / distance **3.9220%** / volume **0.4215%** ⇒ 极差 **70.95 pp**。

**25 门**：01 冻结嵌入 / 02 AST / 03 零仿真 / 04 manifest 5 件 / 05 154 列 / 06–07 join / **08 宇宙逐行声明** / **09 比较内宇宙唯一** / **10 无不可能份额（含"分子宇宙 == 分母宇宙"显式断言）** / 11 嵌套分母单调 / **12 分母逐行声明** / 13 面角色声明 / 14 四面矩阵完整 / **15 SVC 四面逐位复现 G-0** / **16 EP_SVC 复现 G-1 且差异须显式标注宇宙** / **17 影响只出自 `time` 面** / **18 强度三档全非空** / **19 无合成总分** / **20 集中度仪器声明（禁常数 `k`）** / **21 基线配对** / 22 判决闭集唯一 / **23 Gini 禁作判据** / 24 终局三方一致 / 25 非 7.9G 产物未变。

**判决闭集**：`Q1 {DENOMINATOR_UNIFIED, DENOMINATOR_SPLIT}`；`Q2 {EXPOSURE_IMPACT_DECOUPLED, EXPOSURE_IMPACT_COUPLED}`；`Q3 {CONCENTRATION_AMPLIFIED, CONCENTRATION_ATTENUATED, CONCENTRATION_COMPARABLE}`；`Q4 {FOUR_FACE_PARALLEL_REPORTING, SINGLE_HEADLINE_ADMISSIBLE}`。**阈值 `UNIVERSE_SPREAD_TOL_PP = 0.5` / `AGREEMENT_BAND_PP = 5.0` / `RATIO_CONC_MIN = 3.0` 均为预先约定，不得在看到实测值后回调。**

**负例**：**11 真负例**（N1 改分母 / N2 time 当 volume / N3 link 数当 delay / N4 混用内部与全网占比 / N5 固定 `k` / N6 合成总分 / N7 分母声明缺失 / N8 宇宙混用 / N9 Gini 判据 / N10 单面 headline / N11 冻结件被动）+ **1 个 no-op 空负例自检 `S1`**（把字段写死为**真值**，套件**必须**判 `fired=False`，否则套件失效）+ **3 BLOCKED**（空 ref 目录 / 篡改 `pop` sha / 列数 153）。

**必需输出 16 件**：`g2_face_matrix.csv` / `g2_share_matrix.csv` / `g2_intensity_matrix.csv` / `g2_universe_contrast.csv` / `g2_denominator_audit.csv` / `g2_concentration_curve.csv` / `g2_concentration_verdict.csv` / `g2_exposure_impact_gap.csv` / **`g2_reporting_template.md`（物化模板句）** / `g2_caliber_crosswalk.csv` / `g2_verdicts.csv` / `g2_checks.csv` / `g2_closure_check.csv` / `g2_input_manifest.json` / `g2_summary.json` / `STEP7_9G2_REPORT.md`。

**冻结输入 5 件**（`pop` / `ls_final` / `ls_viz_ref` / `net_links_runtime` / `src_copy`，SHA 见 prereg §2）；**只读对照物 8 件**（G-0 4 件 + G-1 4 件）。**★本节点不含 `plans`/`events`**：`EP_SVC` 定义逐位继承 G-1，其与"选中计划路由首/末 link"的一致性已由 **G-1 门 10** 以 `contract = 1.000000` 过门 ⇒ 不再重验，本节点运行成本压到"net + linkstats"。

**实现与验收（2026-09-29 完成）**：
- **脚本** `scripts/od/audit_caliber_harmonization_7_9g2.py`（**73,426 B**，1,396 行，零仿真 / 只读）；**产物 16+1 件**落 `reports/caliber_harmonization_7_9g2/`。**跑批** `25/25`、EXIT=0、`CLOSURE=OK`、`converged=True; it=3`、**47.8 s**。
- **★四面实测（EP_SVC ｜ D0，`U_loaded`）**：time **71.368133%** / count **3.155967%** / distance **3.922029%** / volume **0.421506%**；极差 **RANGE_ep = 70.946627 pp**。
- **★判决**：`Q1 = DENOMINATOR_SPLIT`（`max_legal_share_pct = 71.368133`、`universe_spread_pp = 1.962541 > 0.5`）；`Q2 = EXPOSURE_IMPACT_DECOUPLED`（RANGE **70.95 pp** ≫ 5.0）；`Q3 = CONCENTRATION_ATTENUATED`（`R_50 = 19.803755` / `R_90 = 6.643841` / `R_99 = 1.032118`）；`Q4 = FOUR_FACE_PARALLEL_REPORTING`。`noop_selfcheck_passed = true`。
- **★宇宙撕裂（门 10 捕获并标注）**：`illegal_mixed_universe_ratio = SVC_any km / ALL_loaded km = 1.709605`（**170.9605%**）。`U_any` 面：`EP_SVC_any` n **10,156** / km **296.402279** / delay **3,410.521558 h**；`SVC_any` n **450,486** / km **8,865.505964**。
- **★三档强度（s/veh）**：ALL **0.430002** → SVC **9.407303** → EP_SVC **72.806547**（EP_SVC/ALL = **169.32×**）。
- **★★口径级技术发现（本轮 7 项，均已固化进脚本）**：
  1. **时间面逐位一致必须用 `math.fsum`** —— pandas / numpy 的**顺序求和**与 G-0/G-1 存储值差 **1 ulp**（D0 `9.095e-13`、D2 `4.547e-13`）；`fsum` 是正确舍入的精确求和，D0/D1/D2 三档全部 `atol=0` 命中 ⇒ **门 15/16 的「逐位」要求真实可达**，但**只有 `fsum` 路径**可达。
  2. **pandas 默认快速浮点解析会丢 1 ulp** —— `296.40227899999996` 被读成 `296.402279`；**产物回读同样中招**（`962.7150059999999` → `962.715006`）⇒ 一切对照物 / 产物回读**必须 `float_precision="round_trip"`**，否则门 15/16 出现**假失败**。
  3. **`D2 = (home ∪ work) ∩ service`，不是 home∪work 全集** —— 全集 22,359 条会得到 km **775.33** / vol **1,148,087**（错）；`∩ service` 才得 n_any **10,156** / n_loaded **7,083** / km_any **296.402279** / vol **168,637**，与 G-1 逐位一致。
  4. **G-0 与 G-1 的面名不同** —— `g0_exposure_faces.csv` 用裸名 `time/count/distance/volume`，`g1_exposure_faces.csv` 用 `time_delay_corr_h/...` ⇒ `FACE_G0_KEY` 必须**双向映射**，否则门 15 直接 `IndexError`。
  5. **空串经 `to_csv`/`read_csv` 往返变成 NaN** ⇒ 门 12 的「**非空**」必须显式 `isna()` 判定（只做 `dropna()` 后的集合差会**漏检** `denom_scope` 置空）。
  6. **pandas 3.0 `df.loc[len(df)] = {...}` 静默丢弃新列** ⇒ 负例 N10 首跑**空转**（`face_role` 列从未生成）。**列注入必须走 `g_rows.append(dict)` 或直接列赋值**。
  7. **门 09 / 12 需覆盖「全部 share 行载体」**（含 `denominator_audit`）才与 §6 原文「**每个** share 行」一致；覆盖后 N4 的「跨宇宙同键」才被门 09 捕获。
- **★独立复核** `scripts/od/_verify_g2.py`（**不导入被测脚本**，从 5 件原始输入重算全部头条量）：**90/90 PASS**、判 `INDEPENDENT_REPRODUCTION_OK`；含 12 组四面逐位、24 组份额逐位、15 组集中度 `f_t`/`R_t` 逐位、9 组强度、13 组 G-0/G-1 锚点、closure/manifest 逐件 sha。
- **★负例套件** `scripts/od/_g2_negatives.py`（严格按 §8）：**11 真负例 11/11 全 `fired=True`**、**空负例 `S1` 正确 `fired=False`**（`q3_for` 写死真值 = no-op）、**3 BLOCKED 3/3 `complete=True`**（各 25 行 checks + 6 件终态产物 + EXIT=1 + 状态 `…_BLOCKED`）。沙盒根 `reports/_g2_neg_root2/`。
- **★§8「期望触发门」预测偏差（实测 vs 预测，逐条留痕）**：**N1** 期望 12/09 → 实测 **10**（`share_loaded(ALL_LOADED, time) = 1.059809514` = **105.98% > 100%**，被门 10 以**更强**的失效信号捕获）；**N4** 期望 12/10 → 实测 **09**（`denominator_audit:2` 组合同键跨宇宙）；**N3** 期望 15/17 → 实测 **15**（+16）；**N2** 期望 15 → 实测 15（+16，附带 `vol` 失配）；**N9** 期望 23 → 实测 23（+22，附带判决串自洽性）。**逐条命中 7 例**（N5→20 / N6→19 / N7→12 / N8→10 / N10→17 / N11→25）。**★留痕结论**：§8 的「期望门」列是**设计期预测**，与冻结**判据**无关；其中 **门 17 的判据是「`face_role` 归属 + 影响类字段名」，结构上无法检测「把 `count` 值塞进 `time` 面」这类**值替换**攻击**——该类攻击由**门 15** 正确捕获。此偏差**已留痕、未改任何判据**（改判据须立 R2）。
- **★冻结影响 = 无**：零仿真、未改网络/容量/需求/route-choice；G-0/G-1 两目录 `changed=0`（门 25 逐文件 sha）；**不回写** G-0/G-1 任何产物；**v1.0 仍为唯一冻结模型、不产生 v1.1**。**下一步** = **LTA 分车型 / HTS 出发时刻**。

### 2.63 Step 7.9A-1 采样一致性容量单因子动态实验（**Dynamic Realism Audit ①；1 次 20 迭代仿真 226.99 min；零仿真评价 104 s；硬门 0 失败 / 记录项 6**；判 `SAMPLING_CAPACITY_NETWORK_BREAKDOWN` × §7 情形 **D**）

**起因（领导者反馈）**：MATSim 动态交通状态“不像真实城市交通”、VIA 画面无拥堵。用户提出两条嫌疑（①抽样率与容量不一致 ②所有人 08:00 整点出发）并要求 2×2 实验。

**★第一手核实（推翻了用户的第二嫌疑）**：冻结 population（`populations/pop_W01/population_lambda_0p075.xml.gz`，236,044 persons）的 `home end_time` **早已分散** —— 范围 07:00:00–08:59:59、07 时 114,970（**48.71%**）/ 08 时 121,074（**51.29%**）、**7,200 个秒级不同取值**、中位 **08:01:27**、恰为 `08:00:00` 者仅 **44** 个 ⇒ **`6.3.3A` 早已固化**，用户描述的“08:00 单脉冲”是 **6.2B 时代**状态 ⇒ **2×2 退化为单因子（C≡A、D≡B）**。用户据此裁定：**只跑 `7.9A-1` 单因子**（另裁定判据 = 四指标 + 空间位置，锚 7.3.6A 靶场）。

**唯一结构变化**：`qsim.flowCapacityFactor` / `qsim.storageCapacityFactor` `1.0 → 0.434977`（= `1/SCALE`，由 `N_base/ΣEF = 200,000/459,794` **独立推导**，⛔ 不由交通观测反演）；其余全部继承 v1.0（`queue` / FIFO / `timeStepSize 1 s` / λ=0.075 / route-choice 冻结 / `randomSeed 4711` / 236,044 agents）。config 全展开 diff **恒 5 项**且全白名单。

**运行**：`matsim_sampling_capacity_7_9a1/`。20 迭代 **226.99 min**、heap 24 g、`A1_RUN_COMPLETE` **41/42**（1 项 `WARN` 非失败、`failed == []`）、`dep = arr = 236,044`、`stuckAndAbort = 0`、it.19 events **1.93 GB**；冻结 3 目录（`matsim_final_7_6h` / `matsim_viz_7_8` / `reports/final_model_7_8`）**0 漂移**。

**★四指标实测（A-1 vs v1.0，同口径）**：

| 指标 | v1.0 | A-1 | 倍率 |
|---|---:|---:|---:|
| ① `N_cong`（`excess_s>0`，**主判据** = 登记基线） | 7,985 | **15,083** | **×1.889** |
| ① `N_cong`（cut 50 / 100 / 200 m） | 721 / 144 / 9 | 1,805 / 435 / 58 | ×2.503 / ×3.021 / ×6.444 |
| ① `N_slow`（cut 0，**含量化伪影**，见下） | 117,168 | 124,736 | ×1.065 |
| ② `n(v/c ≥ 1)` | 82 | **501** | **×6.110** |
| ② `sat_km` | 1.1514 | **7.3379** | **×6.373** |
| ② `max v/c` | 1.000000 | **1.001695** | **首次越过 1.0** |
| ② 饱和链流量占比 | 0.2260% | 0.3892% | ×1.722 |
| ② 峰 `aggV/C`(15 min) | 0.102603 @08:30 | 0.216183 **@08:45** | ×2.107 |
| ③ 峰在途（events / legHistogram） | 36,176 / 36,799 | **63,706 / 69,357** | ×1.761 / **×1.885** |
| ③ 峰排队（`enters traffic` 未进链） | 57 | 73 | ×1.281 |
| ③ 峰 `n_slow_links` / 峰时刻 | 30,706 @08:25 | 37,917 **@08:55** | ×1.235（**峰后移 30 min**） |
| ③ `stuck` / 全天未到达 | 0 / 0 | **0 / 0** | 满分（**非网络崩解**） |
| ③ 06:00–12:00 窗内未到达 | 104 | **5,241** | ×50.4（**拥堵外溢到午后**） |
| ④ `overlap_len_share` | 0.03547 | 0.04140 | ×1.17 |
| ④ `concentration_ratio`（全网上限分母 / 载流链分母） | 3.377 / 1.158 | **3.942 / 1.412** | 拥堵**向靶场聚集** |

**★★§5 ① 流量质量（本轮首次真正产出，门 `A09b`）**：Pearson r **0.3452 → 0.4278**、WMAPE **0.7176 → 0.4774**、GEH 中位 **26.088 → 15.887**、GEH<5 **49 → 88**（占比 8.51% → 15.28%）⇒ **四项分布面全部改善**。

**★崩解护栏（门 `A09`）**：`Sim/Obs` `0.9993348 → 0.7664761`（**< 0.85 ⇒ 触发**）；`POSITIVE_ONLY 1.0873 → 0.8161`、`BEST_DIRECTION 1.0383 → 0.7997`（**三口径全跌破** ⇒ 非零流伪影所致）。`it.19` 单点 `0.7725`。

**★判决**：**`SAMPLING_CAPACITY_NETWORK_BREAKDOWN`**（预注册 §10），§7 情形自动分类 = **D**（`sat_km ×6.37 ≥ 2.0` 且 `Sim/Obs ×0.767 < 0.95`）。

**★★机制分解（`scripts/od/decompose_simobs_7_9a1.py`，519 s，逐断面 576/576 全内连接）**：
- `Σsim` 1,513,214.6 → **1,160,614.9（−23.30%）**；`Σobs` 冻结不变（1,514,221.9）。
- **★不是均匀缩放**：**`L1/L0 = Σ|Δ| / |ΣΔ| = 1.4226`**（345 断面降 / 186 升 / 45 持平；按 obs 加权：降的担 62.44%、升的担 31.45%）⇒ **正负抵消的空间重分配**，非整体变稀。
- **★`|Δ|` top-20 全为高速**（CTE / PIE / SLE），且这些断面 **v1.0 严重高估 2.0–4.9×**：CTE `44900` obs 5,131.5 / v1.0 11,911.5（**×2.32**）/ A-1 4,094.6（×0.80）；SLE `47376` obs 3,432.0 / v1.0 6,843.8（×1.99）/ A-1 2,845.4（×0.83）；PIE `46623` obs 2,797.2 / v1.0 13,800.4（**×4.93**）/ A-1 8,917.2（×3.19）。
- **★A-1 把逐断面 `sim/obs` 分布向 1 压缩**：P25 0.287→0.341、P50 0.959→**0.816**、P75 1.539→**1.185**、P95 2.991→**2.245** ⇒ 这正是 r/WMAPE/GEH **四项改善**的来源。
- **⇒ 对 §7 情形 D 的直接证实**：v1.0 的 `Sim/Obs = 0.9993` 是**大额正负抵消**的产物（高速高估 ≈ 其余低估）；A-1 削掉的正是高速上**物理上不可能**的那部分高估（`0.434977 × C_real` 下链路根本载不动 12,000 veh/h）⇒ 总量因此不再平衡。§7 情形 D 原文「既有断面流量校准可能依赖了错误的容量尺度补偿」**由实测直接坐实**。
- 产 `reports/sampling_capacity_7_9a1/_decompose_simobs_a1.json`（含 `L1/L0`、分位、按 `RoadCat`、top-20）。

**★口径与实现留痕（本轮 4 项，⛔ 均未改预注册 sha `de15361a…`、⛔ 未改任何阈值）**：
1. **`A03` 假门禁（第 7 次同类复现）**：判据写死 `vd.startswith("PREPARED")`，而 runner 跑完后**合法地**把 verdict 由 `PREPARED_AWAITING_RUN` 改写为 `A1_RUN_COMPLETE`（该 json 内**没有** `ok` 键）⇒ `A03` 必判 FAIL ⇒ 因 `hard_fail` 非空把总判决压成 `FAILED`，**整轮结论被误毁**。已修为「跑前 `PREPARED*` **或** 跑后完成态且 `failed == []`（允许 `WARN`）」。全脚本仅 `A03` 引用 `PREPARED` ⇒ 单点修复。
2. **★`A09` 的判决分支是死代码**：原 `hard_fail = [c for c in CHECKS if c["pass"] is False]` 收录**全部** False 门（含 `A09`）⇒ 只要 `Sim/Obs < 0.85` 就必然走首分支 `FAILED`，预注册 §10 的 `SAMPLING_CAPACITY_NETWORK_BREAKDOWN` **永远不可达**。已按 §10 分离 `BREAKDOWN_GATES = ("A09", "A10b")`。
3. **报告 §8 渲染硬编码**：原文本恒定写「`Sim/Obs(A-1) = …` **≥ 0.85**」，实测 0.7665 时照写“≥”，会把读者带到错误结论 ⇒ 已按**实测比较结果**动态渲染符号与 PASS/FAIL 判定，并在触发时附加子义说明。
4. **`onset` 判据（§4.3）口径警告**：`t_onset` = A-1 `n_slow_links(t)` 首次 ≥ **v1.0 同一 bin 值的 3 倍**；v1.0 的该曲线在 07:00–08:55 **平台化**（≈2.9–3.07 万，短链量化伪影所致）⇒ A-1（峰 3.79 万）在 07:00–09:00 内**根本达不到** 3 倍 ⇒ 实测 `t_onset = 09:20` **不代表拥堵自 09:20 才出现**，只是「v1.0 09:00 后回落、A-1 仍高」的**交叉时刻**；⛔ `duration = 155 min` **不得**读作「拥堵总时长」。同时报 1.5× 次级判据（`t_onset_1p5x = 09:10` / 165 min）。

**★§11 `CAPACITY` 语义（运行前 1.5 h 提前解出，运行后由门 `A04` 证实）**：`MODE = BASE_CAPACITY`（`identical = 693575/693575` 逐位相同、`ratio_match = 0`）⇒ linkstats 的 `CAPACITY` 列**不随 `flowCapacityFactor` 缩放**，评价器「自己 ×0.434977」的口径**正确**；`max v/c = 1.0017` 证明**容量天花板在 A-1 下首次成为实际约束**（v1.0 恒 `1.000000`）。交叉验证 `n_over = 501/235,612`（`WARN_RULE_SUSPECT`，§11 第 2 条要求两版数字同时报出）。

**★第三份口径备忘**：`CALIBER_RESOLUTION_BREAKDOWN.md`（**§10 判决子义消歧** —— 本次触发的是**流量层崩解**（`Sim/Obs < 0.85`），**不是** `stuck` / `never_arrived` 的**网络崩解**（实测 `max stuck_car = 0`、全天未到达 `0.0000%`、`dep = arr = 236,044`）⇒ 判决取 `NETWORK_BREAKDOWN` 但**读法按 §7 情形 D**；⛔ 两种子义都**不**允许“把容量调回去”），并加门 `A09d` 断言其存在。

**★产物**：运行侧 8 件（`configs/config_A1_capf0p435.xml`、`audit/*`、`logs/*`、`ITERS/it.0…19`、`output_events/output_plans`）；评价侧 **21 件**（`PREREG_7_9A1.md`（`sha de15361a…`，15,631 B）、`a1_face_metrics.csv`、`a1_time_series.csv`、`a1_spatial_top500.csv`、`a1_target_overlap.csv`、`a1_guardrails.csv`、`via_link_attributes_HRS8-9_A1.tsv`（87.96 MB）、`congestion_map_A1_HRS8-9.png`、`STEP7_9A1_REPORT.md`、`a1_summary.json`、3 份 `CALIBER_RESOLUTION_*.md`、`_decompose_simobs_a1.json` 等）。

**★独立复核与预热**：`scripts/od/xcheck_flow_quality_7_9a1.py`（§5 ① 三项独立重导 **12/12**）；`scripts/od/prewarm_events_7_9a1.py`（events 缓存往返无损 **`PREWARM_OK`**，15 项基线逐位 + 7 项结构不变量）；`scripts/od/audit_signal_mechanism_7_9d0.py`（信号机制零仿真审计，判 **`SIGNAL_MECHANISM_ABSENT`**）。

**★冻结影响 = 无**：零仿真评价、未改网络 / 容量 / 需求 / route-choice / 出发时刻；**v1.0 仍是唯一冻结模型、不产生 v1.1**；⛔ **`0.434977` 不得被宣布为最终 / 最优容量**（它只是「目前唯一有数学来源、最该先验证」的参数）。

**★判决含义（一句话）**：**按抽样比例收紧容量是“方向正确、但单独使用会过冲”的一刀** —— 它同时（a）造出了 v1.0 从未有过的**真实拥堵波**（峰在途 ×1.885、饱和里程 ×6.37、拥堵外溢到午后、峰后移 30 min），(b) 把断面流量校准从 0.9993 打到 0.7665，而 **0.7665 的成因已查明是「削掉了高速上物理不可能的高估」**（见机制分解）⇒ **`Sim/Obs` 的“崩解”不是模型坏了，而是 v1.0 的“水平对上”本来就是靠大额抵消买来的**。

### 2.64 Step 7.9H 动态真实性诊断（**Dynamic Realism Audit ②；零仿真 / 只读 / 47 s + 81 s；⛔ 不改 v1.0、不重跑 MATSim**；判 `SIGNAL_MECHANISM_ABSENT` + 缺口成因锁定为「评价靶场尺度错配」而非需求/容量）

**★起因与一处关键更正**：用户提议的「单因素容量一致性实验」（`flowCapacityFactor`/`storageCapacityFactor` `1.0 → 0.434977`，其余冻结）**已由 §2.63 `7.9A-1` 跑完并出判决**。**基线须更正**：`Sim/Obs` v1.0 = **0.9993347697**（不是 0.766）；**0.7664760994 就是 A-1 的结果**。即：容量按抽样率折减后 `Sim/Obs` **不是回升，而是从 0.9993 掉到 0.7665**。

**★用户 4 条验收标准逐条实测**：

| # | 标准 | 实测 | 结论 |
|---|---|---|---|
| ① | `Sim/Obs` 明显回升 | 0.9993348 → **0.7664761**（↓0.2329） | **✗ 反向** |
| ② | 形成连续拥堵走廊 | 严格档 `vc≥0.85 且 sr<0.70`：0 条 → **2 条 / 1.141 km** | △ 极弱 |
| ③ | 空间残差方向改善 | 高估桶 154 → **65 节**（担 obs 25.16% → **5.69%**）；低估桶 210 → 179（38.58% → **35.17%**） | △ 半改善 |
| ④ | 无全网锁死 | `stuck = 0`、dep = arr = 236,044、真实拥堵只担全网 **0.423%** 流量 | **✓** |

**★H1 缺口去向（it.19 `HRS8-9avg`）**：全网 40,008,184 → 38,130,232（**−4.69%**）；**被 crosswalk 映射的 3,037 条边 2,655,572 → 2,016,818（−24.05%）**；未映射 690,538 条边 37,352,612 → 36,113,414（**−3.32%**）⇒ **缺口主要是「车改道离开被观测边」**（匹配边相对跌幅是其余网络 **7.2 倍**）。走廊间重分配实证：**ECP +83.2%**、**KPE 隧道 +17.7%** 而 **PIE −34.5%**、**CTE −37.0%**、**SLE −26.7%**。

**★H1 断面分桶（576 节，cycle 均值）**：低 `sim/obs<0.5` **210 节担 38.58% obs** → A-1 **179 节担 35.17%**；≈ `0.5–1.5` 212 → **332**；高 `>1.5` **154 节担 25.16%** → **65 节担 5.69%** ⇒ **v1.0 的 `0.9993` 是「154 节高估 ↔ 210 节低估」大额正负抵消**；A-1 压掉了高估侧，**低估侧几乎未动**。

**★「sim 低 obs 高」几乎全是快速路**：**KPE 隧道 19 节 `Σobs 230,268` / `Σsim×S 22,239`（0.097）**、ECP 41 节 0.227、PIE 38 节 0.124、**AYE 26 节 0.092**、TPE 17 节 0.201、KJE 15 节 0.298、BKE 8 节 0.118。`RoadCat` = `CATA 106 / SLIP_ROAD 104`。**成因二分**：**M1 真·低载 133 节**（连 `sum` 口径也 < obs，中位 `sum/obs = 0.538`）／**M2 median 塌陷 77 节**（`sum ≥ obs` 但 median = 0）。`sim_median ≡ 0` 共 **53 节** ⇒ 其中 **`sum` 亦精确为 0 者 37 节**（MATSim 完全不用这些边）、`sum>0 且 sum/obs≥1` **9 节**（纯 M2）、其余 **7 节**（叠加）。**★容量不是约束**：210 节中仅 **4 节** `cap_eff_sum < obs`，中位 `cap_eff_sum = 15,200 veh/h` ⇒ 物理上装得下，MATSim 不放车。极端例：AYE `48525` `obs 4,535`、`n_edges 1`、`cap_eff_sum 7,600`、`sum×S = 0`。

**★H2「快速路被 crosswalk 低估」假设的实测（三部分）**：
1. **「1:1 最近边」被证否**：576 断面 → **3,037 条唯一匹配边**（primary 行 3,015），每断面 min 1 / **max 31** / 中位 **4** / 均值 **5.54**；**严格 1:1 仅 60 节（10.42%）**。
2. **聚合口径敏感性**（只换 `<agg>`）：`median` **0.9993 / 0.7665**、`mean` 1.0074 / 0.7725、**`sum` 4.1616 / 3.1384**、`max` 1.1113 / 0.8589 ⇒ **"聚合函数选错"不成立**（median 恰在 1.0 附近）；但要 `median` 口径在 A-1 达到 1.0 需 **`SCALE × 1.3047`**，在 v1.0 只需 ×1.0007。
3. **覆盖率成立且严重**：匹配边 **159.7 km**（全网 15,126.5 km）却只担 **全网高峰流量 6.64%（v1.0）/ 5.29%（A-1）** ⇒ **靶场只覆盖 6.6% 流量** ⇒ `Sim/Obs` **不可**读作"全网只有观测的 76.6%"。
4. **但快速路整体在 MATSim 里并不低载（关键反证）**：PIE 689 边 / 33.4 km 担 **991,784 veh/h**、SLE 276 边 357,471、TPE 412 边 331,340、CTE 191 边 229,368、BKE 165 边 177,116、**AYE 176 边 136,381**、KJE 150 边 123,249 ⇒ ⇒ **真问题是"LTA 断面观测值 vs 4 条匹配边的中位数"跨尺度比较 + MATSim 在走廊内跨边重分配**，而非"少走快速路"。

**★H3 真正拥堵在哪**：严格口径（`len≥50 m` 且 `vol>0` 且 `vc≥0.85` 且 `sr<0.70`）v1.0 **13 条 / 0.96 km / 担全网 0.124% 流量** → A-1 **91 条 / 8.74 km / 0.423%**，中位 `speed_ratio` 0.630 → **0.253**。走廊（连续相邻按最小转角合并、≥0.30 km）：严格档 0 → **2 条 / 1.141 km**（PIE 0.796 km `14,442 veh/h, vc 0.923, sr 0.150, 3 h`）；宽松档 0 → **10 条 / 4.236 km**。

**★H4 可视化重建（5 张图，v1.0 / A-1 双版）**：旧 `speed_ratio` 污染实测与正式口径**逐位吻合** —— v1.0 载流 224,432 中 `speed_ratio<0.80` **117,168（52.21%）**、其中 **99% 是 `LENGTH<50 m`**；过滤 `len≥50 且 vol>0` 后仅 **1,174（4.70%）**（≡ `n_slow_cut0` / `n_slow_cut50`）。新图：`fig_why_speedratio_fails_v10_A1.png`（2×2 对照，直接证明"全红"是仪器问题）、`congestion_map_vc_5bin_v10_A1.png`（方案 A，`0.85–1.00` 档 79 → **530**、`>1.00` 5 → **33**）、`congestion_map_delay_v10_A1.png`（主图 `delay = TT − FF`，过滤后只画 `delay≥1 s`：**249 条 / 20.8 km / 1,497 veh·h → 998 条 / 88.4 km / 6,073 veh·h**）、`congestion_map_ttratio_major_v10_A1.png`（辅助图，仅干道）、`congestion_corridors_v10_A1.png`（方案 C 双层走廊）。

**★判决与下一步**：`0.434977` **不是**最终答案，**v1.0 仍唯一冻结、不产生 v1.1**。容量一致性修正**确有效果**（高估侧伪影 25.2% → 5.7%）但**未修好 `Sim/Obs`**（判据①反向），暴露更根本的结构障碍 = **评价靶场尺度错配**（覆盖 6.6% 流量 + median 取代表 + 53 节塌陷）。**正交未决两事**：① **`SIGNAL_MECHANISM_ABSENT`**（config 0 命中 / 网络 0 令牌 / `org.matsim.contrib.signals` **不在 classpath** / 恒绿桩 / `NodeTransition` 无 `@StringSetter` 故 XML 改不动）；② M1 真·低载（容量充足却不放车 ⇒ 指向路由分配 / 路网连通性 / OD 空间分布）。**下一刀候选**：(a) 靶场重标定（走廊级 Σ / 容量加权，**零仿真**）；(b) M1 连通性归因（**零仿真**）；(c) `matsim-signals` 或绿信比折减容量；(d) `7.9B trafficDynamics` 复评。

**★脚本**：`scripts/od/diagnose_gap_7_9h.py`（H1/H2/H3，47 s）、`scripts/od/build_congestion_maps_7_9h.py`（5 图，81 s）、`scripts/od/audit_signal_mechanism_7_9d0.py`（信号零仿真审计，20.5 s）。
**★产物**：`reports/dynamic_realism_audit_7_9/` —— `STEP7_9H_REPORT.md`、`_gap_diagnostic_7_9h.json`、`_congestion_maps_7_9h.json`、`_signal_mechanism_audit.{json,md}`、`h2_mapping_cardinality.csv`、`gap_low_ratio_sections_{v10,A1}.csv`、`h3_congested_links_{v10,A1}.csv`、`congestion_corridors_{v10,A1}.csv` + 5 张 PNG。

**★新纪律**：**可视化指标必须报"被谁污染"** —— 本步实测旧图 52% "慢"链路中 99% 来自 `LENGTH<50 m` 的 1 s 量化 ⇒ **凡按比率着色的图，必须先报过滤前后的条数与里程**；**「覆盖率」必须先算**（靶场只担 6.6% 流量 ⇒ 任何断面级比率的对外表述都必须带覆盖率限定）；**比值指标必须同报聚合函数**（median/mean/sum/max 可得 0.77 / 0.77 / 3.14 / 0.86）。

---

### 2.65 Step 7.9I 观测域尺度与局部可达性诊断（**Dynamic Realism Audit ③④；零仿真 / 只读 / 38.4 s + 46.3 s；⛔ 不改 v1.0、不重跑 MATSim**；判 `CORRIDOR_SCALE_AUDIT_READY` + `M1_ACCESSIBILITY_AUDIT_READY`）

> 用户裁定：**暂停 G-3/G-4 与 C（信号）/D（动力学）**，只做 (a) 靶场比较口径修正 + (b) M1 可达性归因，**两者均零仿真**。判据运行前冻结于 `reports/corridor_scale_audit_7_9i/PREREG_7_9I.md`。
> 脚本：`scripts/od/audit_corridor_scale_7_9ia.py`（38.4 s）、`scripts/od/audit_m1_accessibility_7_9ib.py`（46.3 s）、`scripts/od/build_figs_7_9i.py`。

#### 7.9I-A 走廊级容量加权比较（73 条非空 `RoadName` 走廊）

**三口径并报**（1:many 会造成口径不对称，必须同报）：`sim_flow^sec`（断面级累加，主）/ `sim_flow^edge`（边级去重）/ `sim_flow^med`（代表值 = canonical median）；分母 `cap_c = Σ CAPACITY×cap_mul`（边级去重）。

**★★核心发现 = 1:K 计数机制**。1 个 LTA 断面典型对应 **K = 5.5434** 条 MATSim 有向边（走廊级 `K_c` ∈ 3.0–14.4）。实测池化 `ratio_simobs` = **5.2818** ⇒ **`5.2818 / 5.5434 = 0.953`**，量级自洽 ⇒ **"sim 比 obs 大 5 倍"主要是计数基数错配，不是交通现象**。

**容量加权残差（⚠ 口径局限必须同报）**：

| 版本 | `Sim/Cap`(Σ) | `Obs/Cap`(Σ) | 残差 | 代表值口径残差 |
|---|---:|---:|---:|---:|
| v1.0 | 0.5194 | 0.1248 | **+39.46 pp** | −0.0083 pp |
| A-1 | 0.9004 | 0.2869 | **+61.35 pp** | −6.6998 pp |

⚠ Σ 口径的 `+39.46 pp` **主要是 1:K 计数所致**（sim 计 K 次 / obs 计 1 次 / 容量分母也 K 折 ⇒ `Obs/Cap` 被结构性压低 ≈K 倍）；⚠ 代表值口径与 canonical `median` 比 **代数同源**（`=(0.9993348−1)×100×Σobs/Σcap`）**不构成独立证据**。⇒ **容量加权本身给不出独立答案**。

**★★真正的独立证据 = 去尺度残差** `ratio_simobs_norm = ratio_simobs / K_c`（≈1 ⇒ 可被 1:K 完全解释；≪1 ⇒ 真实缺载）：

| 走廊 | 断面 | `K_c` | `ratio_simobs` | **norm** | `obs_flow` |
|---|---:|---:|---:|---:|---:|
| KALLANG PAYA LEBAR EXPRESSWAY **TUNNEL** | 19 | 3.53 | 0.413 | **0.117** | **230,268** |
| **EAST COAST PARKWAY** | 47 | 6.15 | 0.810 | **0.132** | **93,818** |
| KALLANG PAYA LEBAR EXPRESSWAY | 3 | 5.33 | 0.635 | **0.119** | 15,362 |
| （其余 16 条，`norm<0.5`） | — | — | — | <0.5 | 9,816 |

`norm<0.5` 共 **19 条走廊 / 担 `Σobs` 23.08%**，其中**前 3 条担 22.42%**、其余 16 条仅 0.65%。**PIE / SLE / CTE / BKE 的 norm = 1.129 / 1.104 / 1.132 / 0.953** ⇒ **完全可由 1:K 解释，不是真低流量**。分组：EXPRESSWAY norm **0.8232**（obs 89.5%）/ OTHER **0.5504**（obs 10.5%）（⚠ 该池化 K 为 obs 加权混合，仅作量级对照）。

**⇒ 回答「快速路是否被低估」= 分裂成两半**：**大部分快速路 = 计数基数错配**；**只有 KPE 隧道 / ECP / KPE 存在真实缺载（缺 7.6–8.5 倍）**。

#### 7.9I-B 133 个 M1 断面的可达性归因

M1 = `median 口径 sim/obs<0.50` 且 `sim_sum×SCALE < obs` ⇒ **133 节**（M2 = 77 节，复现无损）。图：421,406 节点 / 693,575 边；`hot` 边（`HRS8-9avg≥500`）20,258 条；端点距离用 `dijkstra(unweighted=True, min_only=True)` 一次多源 BFS。

**⚠ 冻结判据缺陷披露（本步最重要的方法论事件）**：冻结分类实测 `M1-C 60 节（obs 69.2%）` / `M1-E 73 节（30.8%）` / `M1-A = M1-B = M1-D = 0`。**`M1-E` 无区分度** —— 133 个 M1 **全部**落在 `motorway`(89)/`motorway_link`(44)，`is_major_highway` 恒 True，把 A/B 挤成**结构性不可达**。**另三项退化诊断**：`all_endpoints_in_giant` 恒 True（**全网单一弱连通分量 421,406/421,406**）、`n_dangling_endpoints` 恒 0、`dir_diff_median` 最大 23.8°（阈值 30° ⇒ `M1-D` 恒 0，**不是"方向正确"**）。以上均已写入 `degraded_diagnostics`。

**后验修订分类（标签 `EXPLORATORY_POST_HOC`，仅假设生成）**：只把"特殊设施"从"任何快速路"收窄为**结构性设施**（`SLIP_ROAD` / 全 `*_link` / 名称含 `TUNNEL·VIADUCT·FLYOVER·BRIDGE·UNDERPASS`），**阈值一律未改**。

| 后验类 | 节数 | `Σobs` 占比 |
|---|---:|---:|
| `X1_CHAIN_DEFECT`（链断裂/多分量） | **60** | **69.2%** |
| `X2_RAMP_OR_STRUCTURE` | 40 | 11.4% |
| `X3_PARALLEL_BYPASS`（旁路 ≥0.5×obs） | 22 | 12.4% |
| `X4_ISOLATED_FROM_MAIN_FLOW`（≥5 跳） | 9 | 6.2% |
| `X0_UNEXPLAINED` | **2** | **0.9%** |

**非互斥标志位**：`f_chain_defect` **60** ／ `f_bypass_ge_half_obs` **105（78.9%）** ／ `f_hop_ge5` 59 ／ `f_slip_roadcat` = `f_all_link_edges` 44 ／ `f_name_structure` 18 ／ **`f_no_flow_in_matched` 38**（匹配边流量**精确为 0**，`Σobs` 62,051 = **13.2%**）／ `f_zero_matched_edges` **0**（映射本身没断）。

**走廊集中度**：KPE 隧道 18 节 `Σobs` 220,473（**17 节多分量、0 节零流量** ⇒ **车在跑但映射对象错**）；ECP 27 节 74,583（13 节 ≥5 跳）；PIE 28 节 63,523；**AYE 21 节 47,734（16 节零流量）**。

#### 交叉印证与判决

| 证据 | 7.9I-A（走廊级） | 7.9I-B（断面级） |
|---|---|---|
| KPE 隧道 | `norm = 0.117` 真实缺载 | 17/18 多分量、**0 零流量** ⇒ 映射对象错 |
| ECP | `norm = 0.132` | 13/27 ≥5 跳、12 链缺陷 |
| PIE/SLE/CTE/BKE | `norm` 0.95–1.13 ⇒ 无真实缺载 | 仍有 28/1/0/6 个 M1 节 ⇒ **走廊内部被高估断面抵消**（均值抵消） |
| 「车改道」 | 匹配边 −24.05% vs 其余 −3.32% | **105/133 节** 300 m 内存在高流量平行边 |

**门/负例**：I-A `6/6` 负例 fired（permute-corridor / constant-capacity / zero-corridor / swap-capmul / zero-all-sim / swap-obs-window）；I-B `4/4` fired（no-hot-edges / A-1-section-set / random-rewire / broken-ids）。**两脚本 `n_fail = 0`**。

**★新纪律（本步新增）**：
1. **多边映射必报计数基数 K** —— 任何「Σ sim 边 vs 单次 obs」的比值必须同报 `K_c`，并给 `ratio/K`；否则会把 **1:K 计数错配**误读为物理缺口。
2. **「口径修正」不得充当独立证据** —— 若修正量与 canonical 指标**代数同源**，必须显式声明（如本文 `residual_pp_rep`）。
3. **退化诊断必须披露** —— 网络是单一弱连通分量时，`in_giant` / `dangling` 类字段**恒真/恒 0**，必须写入 `degraded_diagnostics`，⛔ 不得当作"通过"。
4. **冻结判据无区分度 = 判据缺陷** —— 某类命中率 100% ⇒ 该判据失效，须**后验修订并加 `EXPLORATORY_POST_HOC` 标签**，⛔ 不得静默改阈值。
5. **负例必须是"非同构扰动"** —— 索引整体位移、整体反向都是**同构**，不会改变拓扑量 ⇒ 必然 `fired=False`；负例必须真正改变可观测结果（本步两次踩坑已修）。

**★产物**：`reports/corridor_scale_audit_7_9i/` —— `PREREG_7_9I.md`、`STEP7_9I_REPORT.md`、`corridor_scale_{v10,A1}.csv`（26 列）、`section_scale_{v10,A1}.csv`、`m1_cards_7_9ib.csv`（133 卡）、`m1_class_summary.json`、`corridor_scale_summary.json`、`_corridor_audit_7_9ia.json`、`_m1_audit_7_9ib.json`、`fig_7_9i_corridor_scale_and_m1.png`、`_run_7_9i{a,b}.log`。

**★下一刀候选（均零仿真）**：**(a1)** 对 60 个链缺陷 M1 断面把 crosswalk 从"最近若干条边"改为**沿走廊拓扑取连续有向链**（`from→to` 相邻闭包）；**(a2)** KPE 隧道 / ECP 的"结构设施"实体核验；**(b)** 38 个零流量断面的"平行边承接"一对一记账。**(a1)(a2) 完成后**才重谈 **7.9J / signals**。

---

### 2.66 Step 7.9I-A2 / A1 / B(b) 三刀闭环（**零仿真 / 只读 / 41.6 s + 20.3 s + 19.7 s + 25.5 s；⛔ 不改 v1.0、不重跑 MATSim**；判 `KPE_ECP_OBJECT_AUDIT_READY` + `CHAIN_REAGGREGATION_READY` + `ZERO_FLOW_PARALLEL_LEDGER_READY` + `BB_DIRECTION_PROBE_READY`）

> 用户裁定：**把「模型不堵」与「评价不对」拆开**，并按 **(1) KPE/ECP 实体核验 → (2) 60 节链重聚合 → (3) 38 节零流量平行边记账** 三刀顺序在**零仿真域**收干净证据链；**★底线：在 A1/A2/B 没有把「观测对象 ↔ MATSim 对象」的尺度关系理清之前，不再调整 v1.0 的交通动力学参数**（否则又会"跑四小时 → Sim/Obs 变了 → 却不知道为何变"）。
> 预注册（运行前冻结）：`PREREG_7_9I_A2.md` / `PREREG_7_9I_A1.md` / `PREREG_7_9I_Bb.md`。
> 脚本：`audit_kpe_ecp_object_7_9ia2.py` / `audit_chain_reaggregation_7_9ia1.py` / `audit_zero_flow_ledger_7_9ibb.py` / `audit_bb_direction_probe_7_9ibbp.py`。**全部 `n_fail = 0`**。

#### 7.9I-A2 KPE / ECP 实体定义核验（69 张实体卡；18/18 门；4/4 负例）

**★`norm` 的隐含前提被证伪**：`norm = ratio_simobs / K_c` 成立**隐含**「一个断面对应的 K 条边承载**同一股车流**（连续有向链）」。若实为**平行对象**，「除以 K」会**人为制造并不存在的缺载**。

**核心判据 `vc_max = obs_8_9 / max_e cap_eff(e)`**（观测单元 vs 仿真单元）：

| 走廊 | 断面 | Σobs | **`norm`** | `vc_mean` 中位 | `vc_max` 最大 | 匹配链落 `*_link` 占比 | 主导分类（按 Σobs） |
|---|---:|---:|---:|---:|---:|---:|---|
| KPE 隧道 | 19 | 230,267.5 | 0.117223 | 1.718 | **3.569** | — | **`U_UNIT_MISMATCH` 92.64%** |
| ECP | 47 | 93,818.0 | 0.131760 | — | 0.724 | **78%** | `C_CHAIN` 49.88% / `P_PARALLEL` 38.37% / `S_SLIP_GEOM` 11.74%（**无** `U_UNIT_MISMATCH`） |
| KPE | 3 | 15,362.0 | 0.119084 | — | — | — | **`U_UNIT_MISMATCH` 58.91%** |

**★决定性**：KPE 隧道 **16/19 断面 `vc_max > 1`**（`obs_8_9` 中位 **12,119** > 最大单边容量 **9,500**；最高 `20,342 / 5,700 = 3.569×`）⇒ **拿容量最大的匹配边也装不下 obs** ⇒ **观测单元 ≠ 仿真单元**。

**半径设施重建**（`F_R = SCALE × Σ` 半径内 MAJOR 边 `HRS8-9avg`）：KPE 隧道 matched-only **0.417** → 50 m **0.657** → 100 m **1.439** → 150 m **2.897**（相对 Σobs）⇒ **crosswalk 只选中了低流量子集**。

**★对 7.9I-A 的修正（必须同步）**：`norm` 与设施级口径差 **253% / 500% / 434%**（远超 `PREREG §4-2` 的 15% 门槛）⇒ **7.9I-A 的缺载倍数须修正**：KPE 隧道 / ECP / KPE 从 8.5× / 7.6× / 8.4× 收敛到 **`r_mixed` 2.6× / 2.6× / 2.2×**。

> **★口径记法披露（首跑单门 FAIL 的真因）**：`matched_edges` 有**两个都正确**的计数 —— `n_edge_sec`（逐断面求和，ECP **289**）与 `n_edge_dedup`（去重，ECP **283**，15 行为 `shared_section_count=2`）。`PREREG §1` 给的是 dedup 值。**修法 = 门同时断言两者并携带实测值**（阈值未改），非"改阈值放行"。

#### 7.9I-A1 60 个链缺陷断面连续有向链重聚合（60 张链卡；8/8 门；4/4 负例）

**口径**：候选边集 `E` 的每个**弱连通分量** `C`，有向**路径**（每节点 in/out 度 ≤1 且 边数 = 节点数−1）⇒ `rep(C) = median_e flow_e`、容量 `min_e cap_e`；**非路径** ⇒ `rep(C) = Σ_e flow_e`、容量 `Σ_e cap_e`。`sim_chain = SCALE × Σ_C rep(C)` ⇒ **链内不重复计数、跨链可加**。两级候选池：**P0** = 冻结匹配集；**P1** = `E_s ∪ {100 m 内同向 MAJOR 边}`（重建池）。

| 口径 | pooled `sim/obs` | 缺载倍数 | 说明 |
|---|---:|---:|---|
| `r_med`（canonical） | **0.1187** | 8.4× | 零流边多时塌为 0 |
| `r_sum`（断面级累加） | **0.2871** | 3.5× | 1:K 重复计数 |
| **`r_chain(P0)`** | **0.1881** | 5.3× | 正确口径，但**受限于匹配集** |
| **`r_chain(P1)`** | **0.5556** | **1.8×** | 尺度修复后的真实量级 |

分类（按 Σobs）：P0 **`C_LOW` 100%**；P1 **`C_OK` 17.82% + `C_HIGH` 10.00% + `C_LOW` 72.18%**。
**★结论：链重聚合本身价值有限（0.119→0.188）——真正的杠杆是「候选对象选取」，不是统计量**（P1 推到 0.556 即缺载 1.8×），但仍剩 **72.18% 的 Σobs 判 `C_LOW`**。
走廊：KPE 隧道 17 节 / 200,410（61.8%）；**AYE 10 节 `r_chain` 中位 = 0.000（匹配集全零流）**；**TPE 3 节 `r_chain_p1` 中位 = 5.305 ⇒ P1 是上界、非无偏估计**。

> **★判据退化披露**：原 `G-A1-7`（`r_chain(P0)` vs `r_med`）实测 median rel diff = **0.0056** —— 冻结匹配集内**路径分量的代表值 ≡ canonical `median`（构造性恒等）**，该对比**无信息量**。按 `PREREG_7_9I §4` 纪律：**不静默改阈值**，记入 `degenerate_criteria`，有效对比改为 **`G-A1-7'`（P1 口径，实测 1.070，标签 `EXPLORATORY_POST_HOC`）**。与 7.9I-B 的 `M1-E`（命中 133/133）同类。

#### 7.9I-B(b) 38 个零流量断面平行边记账（38 张记账卡 + 38 张方向卡；6/6 + 6/6 门；4/4 负例）

目标集：`M1` 判为「匹配边流量精确为 0」的 **38 节**（Σobs **62,050.5**；`RoadCat` = **`CATA` 22 / `SLIP_ROAD` 16**；`n_matched` min 1 / 中位 3 / max 16）⇒ **全部匹配成功，但匹配到的边在 v1.0 中一条都没有流量**。

| 分类 | 节数 | Σobs 占比 | 「流量去了哪」 |
|---|---:|---:|---|
| **`B2_OPPOSITE_ONLY`** | **22** | **61.72%** | **同向没有承接对象**（同向有流边 100 m 内 **19/22 节 = 0**、200 m 内 **17/22 节 = 0**）⇒ 流量在**反向车行道**上 |
| `B1_SAME_DIR_PARALLEL` | 10 | 20.73% | **同向平行对象确实接住了**（`r_par_sum_same` 中位 **1.628**，6/10 落在 [0.5, 2]）⇒ 真「平行对象抢流量」 |
| `B3_NO_PARALLEL_FLOW` | 6 | 17.55% | 邻近**既无同向也无反向**承载对象 ⇒ 回到**连通性 / 需求** |

同向平行合计 `Σ×S` = **47,745.0 @100 m**（`r = 0.7695`）／**87,535.6 @200 m**（`r = 1.4107`）。

**★★后验探针 `-P`（标签 `EXPLORATORY_POST_HOC`；预注册与主引擎判据/阈值未改）** 分开了两种互斥解释：

| 分类 | 匹配边 | 其中同向 | 其中**反向** | `d_match_max` 中位 | 同向有流边 | 反向有流边 | 有**对向孪生**的节 |
|---|---:|---:|---:|---:|---:|---:|---:|
| `B1` | 31 | **31** | **0** | 1.8° | 41 | 53 | 6/10 |
| **`B2`** | 91 | **91** | **0** | 5.1° | **7** | **83** | **1/22** |
| `B3` | 30 | **30** | **0** | 2.9° | 0 | 3 | 0/6 |
| **合计** | **152** | **152（100%）** | **0** | — | 48 | 139 | 7/38 |

⇒ **「映射选错方向」的假设被否定**（152/152 匹配边方位一致，0 条反向）⇒ **`B2` 的「同向无对象」是真结论**。`B2` 反向有流边**仅 1/22 节存在同节点对反向孪生** ⇒ 该设施在 MATSim 中建模为**单向 way**（对向车行道以**独立节点串**另建）⇒ **流量确实在「对向车行道」上，但那是网络的另一个对象、另一条节点串** ⇒ **观测对象与仿真对象在「方向」维度上不一致**，不是需求不足、也不是平行边抢流量。

**走廊集中度**：**AYE 16 节 / 37,520.0 + PIE 7 节 / 15,014.5 = 23 节 / 52,534.5（84.7% 的 Σobs）**，两走廊 `r_par_same` 中位均为 **0.000** ⇒ 与 `B2` 完全吻合。

> **★口径陷阱（新纪律）**：`lta_section_geometry()` 的 `mx/my` 是**局部等距平面米**（`lon×111320·cos(lat0)`，原点 (0,0) ⇒ ≈1.15e7），**与全网图 SVY21 不同源**；⛔ **绝不能**与 `Graph.ex/ey` 或 `SEC_GEO_7_6C.mid_x/mid_y` 做半径/距离运算（首版探针混用 ⇒ 距离恒 ≈1.15e7 m ⇒ `n_same = n_opp = 0` **全零伪影**）。其 `bear` / `len_m` 与 CRS 无关，可照用。A2 / A1 / Bb 三引擎**均正确使用 `SEC_GEO_7_6C`**，不受影响；已加防御性文档字符串 + 新增 `G-P0` 坐标同源门。

#### 阶段判决（本轮冻结）

> **当前主要问题不能继续归因于采样容量折减（7.9A-1 已否定为主因），也不能直接归因于 MATSim 全网需求不足（7.9H：缺口是「改道」非「少跑」，`Σflow` 全网 −4.69% vs 匹配边 −24.05%，差 7.2×）。现有证据表明，评价域存在显著的 1:K 映射尺度错配；在消除该尺度效应后，仍存在少数高影响快速路断面的真实低载问题，其主要表现为映射链断裂、平行替代路径及特殊道路设施对象不一致。**

**★产物**：`reports/corridor_scale_audit_7_9i/` —— `PREREG_7_9I_{A2,A1,Bb}.md`、`STEP7_9I_{A2,A1,Bb}_REPORT.md`、`kpe_ecp_entity_cards_7_9ia2.csv`（69 卡）、`a1_chain_cards_7_9ia1.csv`（60 卡）、`bb_zero_flow_ledger_7_9ibb.csv`（38 卡）、`bbp_direction_probe_7_9ibbp.csv`（38 卡）、4 份 `*_summary*.json`、4 份 `_*_audit_*.json`、4 份 `_run_*.log`。

**★下一步（待裁定）**：三刀已闭环 ⇒ 候选 = `B2` 需要「**车行道对（carriageway pair）**」层（区分「同节点对双向 way」与「独立节点串单向 way」），**仍属零仿真域**；其后才重谈 **7.9J / signals / trafficDynamics**。

#### ★阶段冻结收口（判决 `7.9I_FROZEN_CLOSED`，2026-09-29）

用户裁定「**暂停推进，先冻结收口**」⇒ 阶段档案 **`CLOSURE_7_9I.md`**（6 节：冻结声明 / 交付清单 / 冻结结论 C1–C9 / 口径修正与陷阱 R1–R5 / 未解项移交 O1–O5 / 复现与恢复入口）。

- **全链完整性审计**：7 脚本（含出图）× 6 判决 × **70/70 门 / `n_fail = 0`**（`CORRIDOR_SCALE` 20 + `M1_ACCESSIBILITY` 12 + `KPE_ECP_OBJECT` 18 + `CHAIN_REAGGREGATION` 8 + `ZERO_FLOW_PARALLEL_LEDGER` 6 + `BB_DIRECTION_PROBE` 6）。
- **补齐缺失 run log**：`_run_7_9ibbp.log`（原 **5/6** ⇒ 现 **6/6**，全链日志完整）。
- **★复现性校验**：重跑 `audit_bb_direction_probe_7_9ibbp.py` ⇒ ① summary JSON 除 `elapsed_s`（25.5 s→11.0 s，热缓存）外**逐位相同 = True**；② CSV **逐位相同 OK**。
- **良性重复登记（不修改）**：A2 / A1 / Bb 的 `*_summary_*.json` 与 `_*_audit_*.json` **md5 全等**（`6f357f49…` / `6b65888e…` / `86e21605…`）⇒ 同一 dict 按两种命名约定落盘，为判决记录的权威副本；⛔ 收口阶段**不重命名、不去重**。
- **★恢复入口**：尺度关系**已理清**（C1–C9）⇒ 唯一合法入口为 **O1–O5**，优先序 **① O1（`B2` 车行道对层，零仿真，唯一不需突破底线者）→ ② O3（LTA 分车型 / HTS 口径，零仿真）→ ③ O2 / 动力学参数（必须用户显式裁定解除底线）**。

### 2.67 Step 7.9I-O1 —— B2 车行道对层（**零仿真 / 只读 / 20.7 s + 14.1 s + 13.2 s；⛔ 不改 v1.0**；判 `CARRIAGEWAY_PAIR_AUDIT_READY` + `PAIR_CANDIDATE_PROBE_READY` + `OPPOSITE_LABEL_CONTROL_READY`）

**状态链**：`7.9I_FROZEN_CLOSED → READY(O1) → O1 ✓`（用户 2026-09-30 裁定「暂停推进，先冻结收口」后给出 O1 恢复入口，并列出 **7 条锚点 A1–A7**，已录入 `CLOSURE_7_9I.md §7`）。

**要回答的问题**：**LTA 所观测的「一个方向断面」，与 MATSim 中由独立节点串表达的另一方向车行道，到底是什么对应关系？**

**预注册** `PREREG_7_9I_O1.md`（运行前冻结）。**★`G-O1-5` 运行前修订**：原表述「链内每步方位一致」因 `E_opp` 已按方位筛过而**恒真** ⇒ **命中 100% 的退化判据**，改为**拓扑有向路径**判据（`is_directed_path`：`|E|=|V|−1` 且 `max(out/intdeg)≤1` 且恰 1 起点 1 终点）⇒ 实测 `directed_path` **46** / `sum` **11**，非退化。

**方法**：`E_opp(s)` = 半径 100 m 内、`MAJOR`、方位差 `~(bear_s+180°) < 30°`、排除匹配边 —— **与 B(b) 的唯一差别是去掉 `flow > 0`**（刻意口径扩展：要区分「无对向对象」与「有对向对象但无流」）。链分量按 `7.9I-A1` 同规则取代表值（有向路径 `median` / 否则 `sum`），`sim_pair = SCALE × Σ_C rep(C)`。

**★主引擎结果**：`Q0_TWIN_PAIR` **10 节 / Σobs 18,531.5**、**`Q1_SEPARATE_CARRIAGEWAY` **26 节 / 43,303.5****、`Q2_NO_OPPOSITE_OBJECT` 2 节 / 215.5；**`B2` 22 节 → Q1 **19** / Q0 3 / Q2 0 ⇒ 86.4% 对向对象是「独立节点串」**（`B(b)-P` 的机制判断被**拓扑证实**）；靶场 576 普查 `PAIR_CONSISTENT` 32.03%。
**硬门 9/9**（`G-O1-2` 与冻结引擎逐位全等 **Σ139=139**；`G-O1-7` `Σ|E_opp|=159` = 有流 **139** + 无流 **20**；负例 **4/4** fired：取消方向约束 / R→3000 m / 非同源坐标 / 代表值退化）。

**★后验 ①（候选对象选取，`EXPLORATORY_POST_HOC`）**：按「候选对象选取 > 统计量」与「多边映射必报 K」把 `Σ_C` 拆三规则 —— `r_pair` 中位 **R-sum 2.1512 / R-max **1.8677（落在 [0.5,2] 带内）** / R-med 1.2183**；带内 Σobs 占比 0.3353 / **0.3963** / 0.3494；**`Σ K_pair = 57`**（`{1:23, 2:8, 3:4, 0:2, 6:1}`）；`Σflow_same **47,745.0**` vs `Σflow_opp **254,771.9**`（**5.34×**）；**`corr(log obs, log r_pair) = 0.0535`** ⇒ 高 `r` 尾部**不是**低 obs 分母伪影。⇒ **按「单一最强对向链」读，`B2` 的零流量不再是缺载，而是 ≈1.9× obs 的同量级**。

**★★后验 ②（对向标签对照，决定性）**：对每个 `B2` 断面 `s`，在 LTA 侧找**方位相反、几何邻近**的断面 `s'`（同一物理段另一方向，`R ∈ {100,200,300} m` 由近到远取首个），读其**冻结 canonical** `ratio_median` ——
**`L1_OPP_LOADED_OK`（`s'` 正常而 `s` 全零）18 节 / Σobs 32,181 / **51.86%****（严格 `R≤100` 仅 **10 节 / 30.77%**，宽 `R>100` 8 节 / 21.09%）；`L2_OPP_ALSO_LOW` 15 节 / 24,979 / 40.26%；`L3_NO_LTA_OPP` 5 节 / 4,890.5 / 7.88%（`L3a` 4 + `L3b` 1）；`L5_OPP_HIGH` **0 节**。
**★`B2` 内部（Σobs 38,299.5）：`L1` **15 节 / 28,918.5 / **75.51%****、`L2` 6 节 / 9,297.0 / 24.27%、`L3` 1 节 / 84.0 / 0.22%**。典型：**46894（PIE，obs 2,914）→ 对向断面 46009 距 **26.4 m**、obs 4,533、`sim_median_xS` **5,969.3**、`ratio_median` **1.3168**，而本侧 `sim_median_xS` **精确为 0**** ⇒ **同一物理段、几十米之隔：一侧标定正常、一侧全零**。
**硬门 8/8**（`G-O1Q-4` 对向断面匹配边落在 `s` 的 `E_opp` 池内 **25/33** 命中；`G-O1Q-5` LTA 双向观测对称 `obs_{s'}/obs_s` 中位 **1.371**；`G-O1Q-7` `{n_E_opp=0} ≡ Q2` **对称差 ∅**）。

**★裁定**：**`B2` 的问题 75.51%（Σobs）属「路网建模对象层面」（一侧被加载、另一侧对象全零），24.27% 才回到需求 / 路径域**；方向映射错误已被 `152/152 同向` 排除。**与 `7.9F` 系逐层排除、`7.9H`「改道非少跑」、`B(b)-P`「方向排除」完全一致，不构成新矛盾。**

**★暴露面（不得省略）**：`L1` 的 **51.86% 依赖 300 m 搜索半径**，**保守读法 30.77%**（`R≤100`）；`E_opp` 是「几何+拓扑」构造而非**真值对应表**，⛔ 不得读作「LTA 断面 = MATSim 某链」。

**★缺陷登记**：`D1` `G-O1-5` 运行前修订（退化判据）；**`D2` `G-O1Q-4` v1 实现与判据文字不符（实测 `0/19`）⇒ 属实现缺陷非科学结论，v2 修正后 `25/33`**；`D3` `G-O1Q-7` 首版量词过强 ⇒ 换为与主引擎的构造性恒等核验；`D4` 半径暴露面；`D5` `r_pair` 与 `r_par_sum_opp` 口径不同源，⛔ 不得直接相减。

**★产物**：`o1_pair_cards_7_9io1.csv`（38 卡）、`o1_pair_census_7_9io1.csv`（576 普查）、`o1p_pair_candidate_cards_7_9io1p.csv`、`o1q_opposite_label_cards_7_9io1q.csv`、3 份 summary JSON、3 份 `_run_*.log`。

**★下一步（建议，待裁定）**：**`O1-续`** —— 对 `L1` 的 15 节做「车行道对账卡」（该物理段**是否只建了一条单向 way** / OSM `oneway` 标签 / 与 `7.9I-A2` `U_UNIT_MISMATCH` 求交），**仍零仿真**。O2 / 动力学参数**须用户显式裁定解除底线**。

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
| 7.3.2B Route-structure 诊断 | ✅ **PASS** | plans 路径 × 等级分类（200,000/200,000 对接、0 未知 link）；**A"不走高速"否定**（**61.1% 路线 / 41.5% 长度用 motorway**）；**0/196,447 OD 多路径**（完全确定性）；ramp 链 5.12M 次 ml→ml（~42 微段/路线、~30 m/段碎片化） |
| 7.3.2C Motorway Spatial Loading | ✅ **本轮 PASS** | 流式解析（不建 XML 树/ route 对象）；**装载极分散**（motorway 4,780 边 84.6% 被用、**Top100 仅 9.57%**、TOP=CTE 微段）；`m→ml` 160,979 / `ml→m` 162,400；**CATA 装载指数 0.846（64.5% 低于均值）**、`r(装载,sim/obs)`=+0.19；**★CATA≈SLIP 装载（0.85）但 sim/obs 相反（0.69 vs 2.05）→ 装载非判别变量、指向 C 类** |
| 7.3.3 断面语义 ↔ MATSim Link 表达审计 | ✅ **PASS** | 零仿真；覆盖 **1,278/1,311=97.48%**、**10.30 边/断面**（中位 8）；**★CATA↔motorway 干净（等级一致 99.23%、dominant motorway 92.9%）**；**★SLIP_ROAD↔motorway_link 脏（等级一致仅 31.6%、dominant motorway_link 仅 30.7%、dominant 主线 motorway 55.8%、混合 47.8%）→ 匝道被"主线化"**；一边被 ≥2 断面共享 **28.1%**、断面共享边 **73.3%**；**对向车道混入：32.4% 边反向、72.1% 断面含反向边、15.5% 含精确互反配对、仅 8.5% 可串单链** → **C 类（观测-表达系统差异）直接证实**，route-choice 后置 |
| 7.3.4 语义对齐重构 + 收敛判别 | ✅ **本轮 PASS** | 零仿真；**边/断面 10.30→4.70（中位 4）、CATA 纯度 92.9%→97.64%、SLIP motorway_link 纯度 30.7%→52.99%**；**★仅语义过滤即把 SLIP sim/obs 1.88→0.81、CATA/SLIP 0.41→0.97；strict 下 CATA/SLIP 0.363→0.914、SLIP 2.033→0.854** → **收敛成立、主因=语义非方向**；但 **117/251（46.6%）SLIP 断面基座候选无 motorway_link（覆盖缺口）**、CATA 稳定 ≈0.78 → **停止 route-choice，转 7.4 crosswalk 覆盖修正** |
| 7.3.5 SLIP_ROAD 候选几何补全 | ✅ **本轮 PASS** | 零仿真；独立 LTA 几何（5,207 slip）→ **CORE 251 断面：旧有 motorway_link 138（54.98%）→ 新 250（99.60%）**；**★旧缺口 113 个补回 112 个（99.12%）**；**最近同向匝道 ≤5 m 覆盖 93.5%、≤20 m 98.4%**；**半径敏感性：50 m 即 98.2%、200 m 无增益（半径非瓶颈）**；**唯一仍缺失 48170（TAMPINES EXPRESSWAY，最近 ramp 227 m）**；**判定 A（大量补回）** → 根因＝旧 crosswalk 的"**路名锚**"（LTA slip 名为所属高速名，与 OSM ramp 名异构，精确同名仅 **29.1%**）排除了匝道；**方法学：SLIP→匝道应用"几何重合+同向"而非路名** |
| 7.3.6A Final Calibration Crosswalk | ✅ **本轮 PASS** | 零仿真；合并 6.3.2 + 7.3.4 + 7.3.5。**硬规则 CATA→motorway / SLIP→motorway_link（SLIP 不以 RoadName 为硬约束）**；覆盖 **CATA 326/339（96.17%）、SLIP 250/251（99.60%）**；**纯度 100%/100%**；Tier 边数 CATA_T1 1,046 / SLIP_T2 1,515 + T1 597 + **T3 几何回退 35**；**对向残差仅 1.10%**；**共享边率 4.87%**（7.3.3 为 73.3%）；rows 3,193 / 断面 590；**UNMATCHED 14（13 CATA + 48170）不强行匹配**；**N 超限 REVIEW 109（SLIP 中位边数 8 恰压上限）**；5 门全过 ✅；**覆盖仅 CATA+SLIP 两类**；7.1 靶场不动 |
| 7.3.6B Final Crosswalk 三方回测 | ✅ **本轮 PASS** | 零仿真；仅复用 6.3.3B `it.0` linkstats（λ=0.05），按 7.1 冻结口径复算。**★核心链条（08-09, Σsim/Σobs）：CATA/SLIP `0.3633 → 0.9135 → 1.0984`**；CATA `0.7388→0.7797→0.7797`、SLIP `2.0333→0.8535→0.7098`；**参照 7.3.4-full = 0.4100（SLIP 1.8796）→ 覆盖广 ≠ 语义对齐**；SLIP **WMAPE 1.750→0.715**、GEH<10 **11.2%→22.4%**；final CATA 映射 = 7.3.4-strict（n=326，13 UNMATCHED 仍缺）；AM 链条 `0.3650→0.8982→1.0922`；**残差转为整体量级（两类均 <1）** → **断面语义错配（C 类）正式从主要误差剔除**；7 产物全出 |
| **7.4.1 联合校准实验矩阵设计** | ✅ **本轮 PASS** | 零仿真（**从不启动 MATSim**）；θ={λ, f_cap, route-choice}；λ∈{0.050,0.075,0.100}、f_cap∈{0.50,0.75,1.00}（storage=flow）、route-choice 固定 20 it；**9 组矩阵 E01–E09**；**Phase1=E01–E03 / Phase2 按需**；**★randomSeed 校正为 4711**（草案 20260912 系设计日期误写，已披露）；预注册淘汰规则 + `parameters_changed=false` / `lambda_selected=false` / `matsim_runs_started=false` |
| **7.4.2 Phase 1 运行（E01–E03）** | ✅ **本轮 PASS** | E01 λ=0.050 f=0.50 / E02 f=0.75 / E03 f=1.00，均 20 it，全部 `exit=0`（E01 19:08 / E02 22:30 / E03 01:24，墙钟 ~10.6 h）；**唯一变量=`qsim.flowCapacityFactor`（+storage 同值）**，`lastIteration=19` 启用 ReRoute/TTC；磁盘控制 `write*Interval=0`；组合 patch 冒烟 2000×3it PASS；`verify_patch` 断言 seed=4711/ReRoute/routingRandomness=0；可断点续跑 |
| **7.4.2 评价器（零仿真）** | ✅ **上一轮 PASS（正式结果）** | import 冻结的 7.3.6B 模块保证口径同源；评价接口=7.3.6A Final Crosswalk、观测=7.1 冻结；**逐位复现 7.3.6B 头条 CATA 0.779683 / SLIP 0.709812 / CATA÷SLIP 1.098435** ✅；**★Phase 1 结果（08-09）：capacity 强总量杠杆（Sim/Obs 0.399→0.570→0.810）+ 结构极差 0.2371（=2.41× 基线偏离）；CATA/SLIP 0.8328→0.9078→1.0698；f=1.00 全面占优 → 不存在更优 f<1.00**；**★修复报告生成 1 处缺陷**（`struct_scan` 的 `capacity_factor` 取自 CSV 为字符串 → `f4()` `ValueError` → 强制 `float`）；**Scope：仅 CATA+SLIP 两类**（CATB/C/D/E 为 null） |
| **7.4.2 Phase 2 λ 灵敏度（设计 + 运行 + 评价）** | ✅ **PASS（本轮跑完）** | capacity 固定 **1.00**、20 it，只扫 λ；**规范 ID E10(λ0.025)/E03(λ0.050)/E06(λ0.075)/E09(λ0.100)**；⚠️**披露用户口述 E04/E05/E06/E07 与 7.4.1 矩阵编号不一致 + 映射**；**λ=0.025 全链 population 缺失 → DEFERRED（E10）**；**★结论：λ 非结构杠杆（`CATA/SLIP` 极差 0.0146 = capacity 0.2371 的 1/16）也非量级杠杆（Sim/Obs 非单调，峰@0.050=0.8105、谷@0.075=0.7070，最优仍 <1）；λ 对截面拟合有真实但有限正效应（E06 λ=0.075 三窗口 WMAPE/GEH/Pearson/Spearman 一致最优）→ 「量级最优 0.050 vs 拟合最优 0.075」权衡；λ 仍不冻结** |
| **7.4.3 demand scale 设计** | ✅ **本轮 PASS** | 零仿真（**从不启动 MATSim**）；固定 **λ=0.075 / f_cap=1.00 / 20 it**，只做 demand scale；**★MECHANISM 块论证"只缩放 agents"**：`expansionFactor`（Σ=**459,794** = 真实 car OD 总量）MATSim **不消费**、`odTrips`（Σ 随 λ 变 4.215M→4.327M→4.485M）只是每 cell agent 数分布**影子** → **agents（车辆数）= 唯一物理需求杠杆**；矩阵 **D01（REUSE_E06）/ D02 f=1.10 / D03 f=1.20 / D04 f=1.25** |
| **7.4.3 运行器（人口 + config 生成）** | ✅ **本轮 PASS（全量跑完）** | **嵌套随机子集复制**（permutation 前缀 `seed=20260912`，D01⊂D02⊂D03⊂D04 → 增量无偏）：D02 **220k**（ΣEF=505,695.8，`f_realized`=1.09983）/ D03 **240k**（551,684.9 / 1.19985）/ D04 **250k**（574,710.1 / 1.24993）；config 全部 `patch + verify_patch` PASS（f==1.0 / lastIter==19 / seed==4711 / ReRoute / routingRandomness==0 / plans 含 `pop_<EID>`）；**冒烟 2000 agents × 3 it PASS**（2.11 min，逐迭代 linkstats 变化 → 拥堵反馈生效）；**全量 D02→D03→D04 全部 `exit=0`**（各 20 it，D04 墙钟 **492.94 min**），it.19 linkstats 全就绪 |
| **7.4.3 评价（零仿真，正式结果）** | ✅ **本轮 PASS** | **import 冻结的 7.3.6B + 7.4.2 评价函数**（口径逐字节同源）；评价接口 = 7.3.6A Final Crosswalk、观测 = 7.1 冻结；**D01 自检逐位复现 E06（0.7070 / 0.7137 / 0.6706 / 1.0642）** ✅；**★08-09（Σsim/Σobs）：D01 0.7070（CATA 0.7137 / SLIP 0.6706 / 比值 1.0642）→ D02 0.7095（0.6980 / 0.7729 / 0.9031）→ D03 0.8601（0.8512 / 0.9091 / 0.9363）→ D04 0.7599（0.7458 / 0.8376 / 0.8904）**；**★量级非单调（峰@f=1.20），最强 0.8601 仍 <1（差 0.1399）→ 加车补不满量级缺口**；**★结构不中性：CATA/SLIP 极差 0.1738（=λ 的 12×、capacity 的 73%）且穿越 1；SLIP 需求弹性 ×1.249 > CATA ×1.045**；**A−D 阻尼 +0.0682 / −0.0116 / +0.1239（非单调）**；**★已修正**：报告 §5 原硬编码"结构基本中性"与数字矛盾 → 改**数据驱动判决**，summary 增 `level_shape`/`level_peak_f_demand`/`structure_verdict`/`structure_crosses_one`/`demand_elasticity_CATA_vs_SLIP` |
| **7.5A 需求权重链条核查（审计）** | ✅ **本轮 PASS** | 零仿真；**★决定性证据 = jar 字节级常量池扫描（165 jars / 38,647 entries）**：`expansionFactor` 仅出现在 `commons-math3` 的 `ResizableDoubleArray.class`（无关同名字段）、`odTrips` **零命中**；阳性对照 `flowCapacityFactor`/`storageCapacityFactor`/`countsScaleFactor` 全部命中 **MATSim 自身 class**（`QSimConfigGroup` / `HermesConfigGroup` / `CountsComparisonAlgorithm` / `GlobalConfigGroup`）→ 扫描有效；项目自定义 Java = **0**；全项目 `*.xml` 命中 = **0**；**判定 `NOT_CONSUMED`**：MATSim 不消费这两个属性，**有效需求权重 = 进入 QSim 的 person/vehicle 数** → 扩样必须在评价层 `SCALE = ΣT/N_sample` |
| **7.5A 采样管线（100k 人口）** | ✅ **本轮 PASS** | 零仿真；**★硬约束**：λ=0.075 正 OD cell=**71,136** → `N_sample ≥ 71,136`（**50k 不可行**）；三阶段（6.2B `--target-agents 100000` → 连通性修复[复用冻结 `network_cleaned.xml.gz`] → 6.3.3A 出发剖面）**全部写入新目录** `*_s100k`；实测 persons=**100,000**、ΣEF=**459,794.000**、mean_ef=**4.59794**、coverage=1.0、max_od_cell_error=1.4e-14；修复 home 1,270 / work 1,182（中位 3.3 m）；出发剖面 count_07_08=**48,710** / count_08_09=**51,290**、零缺失/零重复；**★冻结 200k 产物 mtime 未变（零覆盖）**；以 monkeypatch 目录常量复用冻结构建脚本 |
| **7.5A 运行器（config 生成）** | ✅ **本轮 PASS（config + 冒烟）** | 复用 7.4.3 运行器 `patch_config`/`verify_patch` 口径；`S100`（f_cap=**1.00**）/`S100c`（f_cap=**0.50** = 采样一致对照）两 config 生成且 `verify_patch` PASS（f_cap / lastIter==19 / seed==4711 / ReRoute / routingRandomness==0 / plans 指向 `matsim_departure_6_3_3a_s100k`）；**冒烟 2000 agents × 3 it PASS**（2000 载入、逐迭代 linkstats 3 份；`DumpDataAtEndImpl` 良性）；**★S100 全量完成（100k × 20 it，`exit=0`，墙钟 143.80 min，it.19 linkstats 就绪）**；**★S100c（f_cap=0.50，采样一致对照）全量完成（100k × 20 it，`exit=0`，墙钟 164.59 min，20 迭代全落盘，`STATUS: PASS`）**；**预注册判据 C1–C7 已跑前落盘**） |
| **7.5A 评价（零仿真，正式结果）** | ✅ **S100c 已评（判 `NOT_SUBSTITUTABLE`，预注册硬门槛 1/6）** | import 冻结 7.3.6B + 7.4.2 评价函数（口径逐字节同源）；**按实验注入不同 `bt.SCALE`**（S200=2.29897 / S100=S100c=4.59794）；**★08-09（Σsim/Σobs）：S200 0.7070（CATA 0.7137 / SLIP 0.6706 / 比值 1.0642）→ S100 0.9784（0.9938 / 0.8935 / 1.1122）→ S100c 0.8389（0.8440 / 0.8108 / 1.0409）**；**★线性度**：`raw S100c/200` 中位 **0.5799**（vs S100 0.6174，期望 0.5）→ **f_cap=0.50 把采样非线性 +23.5% 压到 +16.0%（部分有效）**；**★等价性**：scaled 比值中位 **1.1537**、±10% **11.1%** / ±20% **26.5%**、**Pearson 0.8557 / Spearman 0.9344**（空间相关性反降）；**★结构**：`CATA/SLIP` 漂移 **0.0233（C6 PASS，约为 S100 之半）** → **S100 结构畸变主因是「车密度/容量」**；**△判决 `NOT_SUBSTITUTABLE` —— 残余 16% 非线性不可由标量 f_cap 消除（样本量本身改变网络动力学，含「每正 cell ≥1 agent」保底规则使 100k 下 71.1% agent 为保底 agent）→ 100k 不可替代 200k，100k 方案不冻结**；**λ 仍不冻结** |
| **7.5B 采样规则诊断（零仿真）** | ✅ **本轮 PASS** | 把 6.2B 的保底规则（`每正 cell >=1 agent` + largest-remainder）与**纯 trips-proportional（无保底）** 并列算出 → **★100k 纯比例：sampled cells 38,350 / zero-sampled 32,786（46.09%）/ OD coverage 0.5391 / 丢弃 trips 21,528（4.68%）/ ΣEF 438,266.0 / `f_realized` 0.95318**；对照保底规则 100k：zero 0 / coverage 1.0 / 保底占比 **71.14%** / agent 中位 **1**、max 26（纯比例 max **87**）→ **坐实「保底规则把小 cell 相对高估、且畸变随 N 减小放大」**；200k 纯比例参照：zero 24,293（34.15%）/ coverage 0.6585 / 丢弃 1.88% | 无（纯人口侧计算） | `reports/od_sample_7_5b/sampling_rule_summary.csv` + `sampling_rule_diagnostics.json` + `od_cell_sampling_rules.csv` | ✅ **PASS** |
| **7.5B 采样管线（S100r 100k 人口）** | ✅ **本轮 PASS** | **monkeypatch 6.2B `allocate_cells` 为纯比例**（空间实现/XML 写出/守恒校验逐字节复用）；三阶段全部写入新目录 `*_s100r`（**冻结件 mtime 未变**）；实测 persons=**100,000**、ΣEF=**438,266.002**、OD coverage=**0.5391**、zero-sampled=**32,786**、**被采样 cell 逐 cell 守恒误差 5.68e-14**、max 全体重构误差 2.0468（最大被丢弃 cell）；出发剖面 count_07_08=48,710 / count_08_09=51,290、零缺失 | `car_prior_od_lambda_0p075.parquet`、`network_cleaned.xml.gz` | `reports/od_sample_7_5b/`（`STEP7_5B_DESIGN.md` + `sample_matrix_7_5b.csv` + `s100r_build_summary.json`）+ `reports/matsim_population_6_2b_s100r/` + `..._connected_s100r/` + `reports/matsim_departure_6_3_3a_s100r/` | ✅ **PASS** |
| **7.5B 运行器 + 评价器** | ✅ **全量跑通（171.20 min，exit=0）；判据跑前预注册；判决 `PARTIAL_IMPROVEMENT`（D 0/6、M 3/4）** | 运行器复用 7.5A `gen_experiment`；**★机器验证单变量：S100c 与 S100r 的 config 除 `outputDirectory`/`runId`/`inputPlansFile` 外逐字节相同（diff=0）**；`verify_patch` PASS（f_cap=0.50 / lastIter==19 / seed==4711 / ReRoute / routingRandomness==0 / plans 含 `..._s100r`）；冒烟 2000×3it PASS；评价器 `evaluate_sample_7_5b.py` 三方（S200/S100c/S100r）+ **D1–D7 绝对 / M1–M4 机制**判据 + raw-EF 敏感性（`SCALE_raw`=4.38266）；判决 `SAMPLING_RULE_WAS_THE_CAUSE` / `PARTIAL_IMPROVEMENT` / `SAMPLE_SIZE_DEPENDENT` | 7.5B 矩阵、三方 linkstats、7.3.6A crosswalk、7.1 观测 | `reports/od_sample_7_5b/S100r_lam0p075_cap0p50/` + `matsim/step6_3/config_S100r_lam0p075_cap0p50.xml` + `STEP7_5B_PREREGISTRATION.md` + `preregistered_criteria_7_5b.json` | ✅ **正式结果已出：`PARTIAL_IMPROVEMENT`（D 0/6、M 3/4）** |

| **7.4.3 补充诊断（非单调回落机制，零仿真只读）** | ✅ **本轮 PASS（判决 `TIME_WINDOW_ARTIFACT_CONFIRMED`，T1–T5 全过）** | **★决定性证据（窗口加宽，`Σ_links HRSx-yavg`）**：08-09 单小时 `f1.25/f1.20 = 0.9584`（**下降 → 非单调**）、07-09 仍非单调（0.9807）、**07-11 = 1.0404 ≈ 纯比例 1.0417**、**0-24 = 1.2547 ≈ 纯比例 1.2500（达成率 100.4%）** ⇒ **需求完整投递、仅时间摊开**；**★时间分配直读**：平均行程时长 33.24→**38.99 min（×1.173）**、8-9 加权拥堵倍率 2.314→**2.796（×1.208）**、09:00 前到达占比 73.26%→**68.35%（−4.91 pp）**、到达端后移（08-09 **96,501→91,743**；09-10 **43,208→48,466**；10-11 **13,233→22,228**）；**★出发端稳定**：出发占比跨档极差仅 **0.035 pp（3.5 bp）** ⇒ 机制全在**行进入端**；**★无口径丢失**：四档 `never_arrived=0`、`max_stuck=0`；**★次要发现**：08-09 单小时判决量的超额系数在 **0.848–1.096** 摆动，而 07-08 稳定在 **0.930–1.033** ⇒ `median(匹配边 HRS8-9avg)` 单小时估计量在强拥堵下不稳定 → **水平口径建议改「07-11 累计」，08-09 保留给空间结构比较**；**结论：f=1.20 的 0.8601 不可读作「最优需求规模」**；**未改动任何模型产物**；**λ 仍不冻结；未动 capacity** |
| **7.4.3-R 宽时间窗重新评价（zero simulation）** | ✅ **本轮 PASS（未重跑 MATSim）** | **★阻断发现**：LTA 原始流量 `HourOfDate` **只有 7/8**（75,899 行 / 1,311 LinkID / 30 天，非脚本过滤），`TrafficSpeedBands_v4` 与 `EstimatedTravelTimes` **各只 1 个 Timestamp** ⇒ **可观测窗上限 = 07-09**，`07-10/07-11/07-12/00-24` 的 Sim/Obs **无定义**。**Class O** = 07-08 / 08-09 / 07-09；**Class S** = 07-10 / 07-11 / 07-12 / 00-24（只出模拟侧量级）。**★双聚合**：`ALL`（全网 693,575 链路，≈总车公里，对空间重分配不敏感）vs `MATCHED`（crosswalk 命中 **3,037** 条标定链路，敏感）。**★判决**（f=1.25/f=1.20，期望 1.0417）：`ALL/期望` 0.9201(08-09) → **0.9994(00-24) 完全收敛**；`MATCHED/期望` 0.8493 → **0.9333，仅解释 55.7%**，残留 **6.7% 与窗口无关**；**7 个窗口中 6 个仍 non_monotonic（峰恒在 f=1.20）**，唯一 monotonic 的是 `07-08`。**★对 7.4.3-Diag 的修正**：「需求近 100% 被投递」只在**全网口径**成立，标定靶场全日窗仍留 6.7% 缺口 ⇒ **换窗口不能消除非单调，07-11 也不可作水平判据**（既无观测、也不恢复单调）。**残差指向 ReRoute 路径替代/分配重分布**（MATCHED 在 00-24 归一后 D03=**1.3332** 远超名义 1.20 → 「回落」实为 f=1.20 的超标冲高）。**口径同源断言 PASS**（vs `demand_scale_backtest.csv`，n=5,184，max|Δ|=3.6e-12）。脚本 `scripts/od/reevaluate_demand_scale_windows_7_4_3r.py`；产物 `reports/od_calibration_7_4_3r/`（8 件） |
| **7.6A 官方汽车通勤需求会计（zero simulation）** | ✅ **本轮 PASS（未重跑 MATSim；12/12 校验 PASS）** | **★判决 `CALIBER_GAP_DOMINATES`**。**链条**：居住侧 **2,177,456** / 工作地侧 **2,208,358**（口径差 30,902 = 1.42%）；**物理工作地 1,935,235（87.63%）** + **非物理承载 273,124（12.37%）** —— No Fixed 177,588 / WFH 70,800 / Other-or-Outside 24,736，**单列不进道路 OD，也不丢弃（守恒 Δ = 1）**；11 方式 → **Car Only 459,796 / Car or Taxi-PHC 526,477 / 全部私人道路机动车 707,116**（占就业居民 **21.12% / 24.18% / 32.47%**）。**★量级一致性**：`cov(V1/V3)` = **0.6502** vs 7.4.3-R MATCHED 07-09 `Sim/Obs` = **0.6830**（比 **0.9520**）⇒ **`f ∈ [1.0504, 1.4641]`**；判据 `f_lower = cov/SimObs`，实测 **1.0504 < 1.10**。**★三项不可定量**：观测 **无车型字段**（车型构成不可分解）、Census 无 departure-time（AM 峰因子不可标定；6.3.3A 剖面由 TrafficFlow 自推 = **与靶场循环**）、无 occ 观测（现行隐含 1.00；`occ=1.30` → 模型 **高估** 车辆 23.08%，与模态覆盖 **方向相反**）。**2025 稳健性**：GHS2025 Car Only **21.18%** ≈ Census2020 **21.12%**，但总量 **+8.20%** |
| **7.6B 分配 / 路径稳定性审计（zero simulation）** | ✅ **本轮 PASS（未重跑 MATSim；20/20 校验 PASS）** | **★判决 `UNCONVERGED_PERIOD2_LIMIT_CYCLE__CROSS_F_SIGNAL_BELOW_PHASE_NOISE`**。**★先验事实**：D01–D04 config 全部为 `fractionOfIterationsToDisableInnovation=Infinity` + 唯一 `ReRoute`(w=1.0) + `learningRate=1.0` + `routingRandomness=0.0` ⇒ 100% agent 每代全部重选路。**★周期-2 极限环**：MATCHED 振幅 **1.59% / 3.77% / 20.75% / 16.22%**（ALL 仅 0.39–1.40% ⇒ **放大 14.8×**），奇偶从 it.0 起完全分离；**08-09 冻结指标相位振幅 2.05% / 5.98% / 22.33% / 16.82%**。**★周期均值重估**：08-09 SimObs = 0.7505 / 0.7127 / **0.7647** / 0.7061（it.19 分别为 0.7070 / 0.7095 / **0.8601** / 0.7599，f=1.20 偏置 **+12.47%**）；跨 f 极差 **15.30% → 5.87%**。**★★同相位检验**：偶相位 attainment 单调下降 **1.0 / 0.9637 / 0.9065 / 0.8841**，奇相位峰在 D03 **1.0 / 0.9849 / 1.0987 / 1.0238** ⇒ **响应符号由采样相位决定**。**★R_cal 归一（周期）**：1.0000 / 0.9483 / 0.9753 / **0.9220**（f=1.25 −7.8%）。**★互补证据**：相位翻转 MATCHED 与 NON-MATCHED 对冲（抵消比 0.53 / 0.40，全网仅动 1–2%）⇒ 纯路径替代；top50 最高流 ρ **0.986 / −0.546 / −0.209 / 0.465**；标定链路承担 \|Δq\| 的 4.8–5.7%（链路占比 0.4379%）；绕行指数 1.0000 / 1.0274 / 1.0288 / 1.0352；MATCHED 拥堵倍率 **低于** NON-MATCHED（1.531 vs 2.495 @ f=1.25）。**★动作项**：① 修 replanning 收尾机制（`fractionOfIterationsToDisableInnovation` 0.5–0.9、`ReRoute` 降至 0.10–0.20、`learningRate<1`）；② 评价口径改**周期均值**；③ 在收敛解决前**不再加 demand scale 跑次** |

| **7.6D** Route-choice Stabilization | ✅ **配置验证 PASS + 预注册完成（本轮，零仿真）**：`matsim_routechoice_7_6d/` 独立工作区；最小修复 4 项（`fractionOfIterationsToDisableInnovation` → 0.8、策略集 → `[ReRoute 0.15, ChangeExpBeta 0.85]`、`learningRate` → 0.5、`routingRandomness` 保留 0.0）；**19/19 校验 PASS**，与基线差异仅 4 处；冒烟预检 PASS；**★修复前 `A_10:19(MATCHED)` = 8.48% / 11.10% / 23.25% / 20.32%**（f=1.00/1.10/1.20/1.25，均非 STABLE）；**正式 200k run 经用户裁定改为「先低样本筛查、PASS 后再上」⇒ 见下行 7.6D-S** |
| **7.6D-S** 低样本(100k)稳定性筛查 | ✅ **本轮完成，判 `SCREENING_PASS`（exit=0；33.20 min；linkstats 20/20）** | **★结论：route-choice 最小修复彻底消除周期-2 极限环**。样本量：**50k 因 `FLOOR_PLUS_1` 下界 71,136 不可行 → 用户改选 100k @ `f_cap=0.50`，复用 S100c 人口**；配置 **25/25 PASS**（含 P0 下界断言 / P3 冻结件 mtime 9/9）；预注册门槛**运行前冻结**（MATCHED <3% / CATA <3% / SLIP <5%）。**`A_10:19`：MATCHED 5.84%→`0.71%`(×0.12) / CATA 4.31%→`0.76%` / SLIP 10.86%→`0.60%`(×0.06) / ALL 1.38%→0.44%**；`parity_gap_rel`(MATCHED) 4.07%→**0.09%**。**★★逐迭代轨迹由「奇偶交替、永不衰减」变为「单调指数收敛」（it.13 起 1.000±0.002）** ⇒ 振荡被**消除**而非减小。双口径：`Q̄_10:19`(MATCHED) 2,443,276→**2,514,748**、`Q_19` 2,510,011→**2,517,251**（`Q_19` 相对偏差 +2.73%→**+0.10%**） |
| **7.6E** 200k 正式稳定化 | ✅ **本轮完成，判 `STABILITY_PASS`（6/6）⇒ route-choice 层正式冻结**（`exit=0`；**84.41 min**；linkstats 20/20；≈4.2 min/it） | 200k × 20 it、`f_cap=1.00`，仅改 route-choice 4 项（与 7.6D-S 逐参数一致）。**★四口径 `A_10:19`（200k 修复前 D01 → 修复后 R01）**：MATCHED **8.48% → 1.00%**（×0.12）/ CATA **10.14% → 1.01%**（×0.10）/ SLIP **8.93% → 0.97%**（×0.11）/ ALL 3.96% → **0.51%**；**`parity_gap_rel` 1.59%→0.13%（MATCHED）**。**G1–G6 全过**：`sign_consistency`=**1.000**、`A_10:19` 三口径 `<3%`/`<5%`、`parity_gap_rel<1%`、`Q19/Q̄`=**+0.19%**、`never_arrived=0` & `max_stuck_car=0`（200,000 departures = 200,000 arrivals）、`A(200k)/A(100k)`=**1.40**。**双口径**：`Q̄_10:19`=**4,567,962** / `Q_19`=**4,576,724**。**★逐迭代形态由周期-2 极限环变为单调指数收敛**（旧 D01 `0.9454 1.0679 0.9605 1.0495 …` 不衰减；新 R01 `0.9169 0.9345 0.9457 … 1.0019`），且 **100k/200k 归一路径几乎重合 ⇒ 机制签名**。**★结构性副产物（仅记录）**：收敛单调把流量搬到标定断面，MATCHED `it.0→it.19` **+9.28%**、ALL **−3.70%**（反单调；100k 同形 +9.85%/−3.78%）⇒ 收敛解 MATCHED `Q̄` 比 D01 极限环中心 **+3.1%**；**本步不评价 Sim/Obs**。**未进入 7.6C**；`λ`/demand scale 判决仍不成立 |
| **7.6F-0** 新稳定底座 demand=1.00 基准重算 | ✅ **本轮完成，判 `PASS`（零仿真只读；20/20 校验）** | 7.6E `STABILITY_PASS` ⇒ 禁令解除 ⇒ **第一次有资格讨论 demand scale**。**★新基准点（R01, demand=1.00, 200k, f_cap=1.00）**：Sim/Obs(08-09) Primary **0.8590** / Reference 0.8603 / AM 0.7665；CATA 0.8717 / SLIP 0.7889 / **CATA/SLIP 1.1050**；WMAPE 0.6310 / GEH<5 0.1163 / Pearson 0.3365。**★机制分解（固定 demand=1.00，仅 route-choice 变）**：200k **0.7506 → 0.8590（+14.43%）**、100k **0.8169 → 0.9639（+18.00%）** ⇒ 两规模同向、量级接近 ⇒ **机制签名**；而 `Q̄_10:19`(MATCHED, ΣHRS0-24avg) 仅 **+3.11%** ⇒ **断面流量位移 ≠ Sim/Obs 位移（差 4.6×）**，**禁止用 ×(1+δ) 修正因子平移旧曲线**。**★旧 D01–D04 响应谱判 `LEGACY_CURVE_UNINFORMATIVE`**（PRIMARY 口径内部极差 0.0587 vs 四点振幅均值 0.1579 ⇒ 信噪比 0.372 < 1；新基准点 0.8590 **高于旧谱全部四点**）；`it.19` 相位偏移最高 **+12.35%（D03）**（与 7.6B 的 +12.47% 一致）。**隐含 demand 倍率 1.1642 仅为指示量；本步不选 demand scale / 不评价 λ**；未进入 7.6C |
| **7.6C** OD 空间结构诊断（距离带 / 空间集中 / 路由前后一致性） | ✅ **本轮完成，判 `OD_STRUCTURE_PARTIAL`（零仿真只读；23/28 校验；79.5 s）** | 三轴：**P1 距离结构**（需求加权均值 **12.64 km** / 中位 11.67 km；short/med/long = 14.28%/52.20%/33.52%；衰减单调；**采样偏差 0.00 pp** ⇒ 验证 6.2B 无距离选择性偏差）；**P2 空间集中**（Subzone `P_i` Gini 0.677 / `A_j` 0.438；OD-cell Gini 0.680、top-10% cell 50.56%；**0 个 |z|>5 异常吸收区**；**Table118 物理格中位残差 0.0026 / P95 0.0095**）；**P3 一致性**（`ΣEF=459,794` 与 `N×SCALE` 守恒到浮点精度；**detour 1.068–1.111**，plan 与 linkstats **独立互证**；重分配重现 7.6E 签名）。**★缺口不均匀（S4 FAIL）**：EAST **0.582** / CENTRAL 0.790（亏）vs NORTH 1.067 / **NORTH-EAST 1.158**（盈）；**radial_in 0.612 vs radial_out 0.976**；**54 断面 sim=0 却占 8.14% 观测**（剔除后全局 0.8590→**0.9351**，但区域最大偏差仅 0.348→**0.333**）⇒ **缺口含真实空间结构成分**。**未选 demand scale / 未评价 λ**；**7.6F-1 待用户裁定** |
| **7.6C-2** 校准靶场完整性门控（三口径 + 信噪比 + 网格位置） | ✅ **本轮完成，判 `TARGET_MARGINAL_COARSE_ONLY`（零仿真只读；判据 **7/10**；16.7 s）** | **三口径**：`FROZEN` **0.8589732**（主）/ `POSITIVE_ONLY` **0.9350621**（敏感）/ `BEST_DIRECTION` **0.8909674**（误差边界）；外包络 0.8205206..1.0645964。**`Delta_target` = 0.076089 = 7.609 pp**；**f\* 区间 [1.06945, 1.16418]**，`Delta_f_target` = **0.09473**。**SNR：粗档 (0.10) 1.056 ✓ / 细档 (0.05) 0.528 ✗**（需 ε ≥ 0.947 / 1.895）。**网格：1.10 落在区间内（口径分歧）、1.20/1.25 均在上方且一致** ⇒ 3 跑只买 2 区制；**建议 `1.00/1.10/1.20` 或 `1.05/1.15/1.25`**。**结构可分性 7.33× ✓**；**断面集口径澄清**：7.3.6A 576 断面／574 primary／3,015 primary 匹配链（全家 3,037），7.6C 地理覆盖 574 ⇒ 7.6C-1 repair bounds 按 574（差 4.06e-4），574 子集稳健（**7.619 pp / SNR 1.053 / 0.527**）。**未改 crosswalk / OD / λ；未选 demand scale；未启动 MATSim**；**7.6F-1 可进入但性质必须降级为「粗档响应」，待用户裁定网格** |
| **7.6F-1** 粗档 demand-response 曲线（`f = 1.05 / 1.15 / 1.25`，**物理加车**） | ✅ **完成，判 `RESPONSE_STABLE_CROSSES`（三档全 PASS：69.73/80.40/75.74 min，累计 3.76 h；评价 21/21）** | **路径确认（用户 20:17 裁定）**：`N_base = 200,000`（SCALE 锚）／`N_sim = f × 200,000`（QSim 真实车辆数：**210k / 230k / 250k**）／`SCALE = 2.29897` **全档统一**。**★追加硬约束**：**不得按各档 `ΣEF/N_sim` 重算 SCALE**（披露审计：F05 **−397.69 ppm** / F15 **−56.03** / F25 **−56.32**，全部来自 `FLOOR_PLUS_1` 保底取整，**一律 NOT USED**）。`f_realized` **如实报告**：**1.0495824 / 1.1499356 / 1.2499296**。前置核验 **18/18 × 3 档 PASS**（config **sha256 前后钉扎**；与 R01 差异**仅 3 项**且全在白名单；route-choice 4 项 + `f_cap=1.00` + seed 4711 + λ 0.075 逐值继承/相同）。**串行原因**：本机 **63.7 GB RAM** / `24g` per run ⇒ 三档并行必 OOM；预计 ≈88/94/100 min，合计 **≈4.7 h**。**只改被仿真 agent 数，未改任何模型参数；未选 demand scale / 未评价 λ** |
| **7.6C-1** 异常归因追踪（零流断面全链路 + 东部/中心流向拆解） | ✅ **本轮完成，判 `MIXED_COVERAGE_AND_RESIDUAL_STRUCTURE`（零仿真只读；5/5 判据、6/6 校验；78.3 s）** | **L1**：13 个 R5/radial_in 零流断面**全部在 WEST（TUAS/PIONEER）**，47 条匹配边**三窗口 × 正反向全 0**、**43/47 有向拓扑孤儿**（参照 0.987/0.991）、**0/47 连通**；但 400 m 邻域有 **1,559–39,762 veh/h** ⇒ 走廊是活的；**54/54 在 100 m 内有有流平行链、52/54 在 60 m 内、50/54 有同路名有流链**；机制 31/13/8/**2**。**L2**：EAST→CENTRAL **45,229** vs CENTRAL→EAST **9,550**，不对称 **0.2112 ∈ [0.1044,0.3089]**（正常）；EC 实走路径 **64.25% 为 radial_in、99.2 东走廊链次/出行**；Table118 中位 0.0026/P95 0.0095。⇒ **硬零流 = 测量伪影（0.8590→0.9351 可解释）；graded 区域/径向缺口 = 真实**（修正后 EAST 0.622、radial_in 0.634 仍最低）**；吸引量 / OD 方向 / 路径改道三假设全否证**。**未选 demand scale / 未评价 λ**；**7.6F-1 可进入（须双口径并报且必须用 MATCHED）** |
| **7.6F-1** 粗档 demand-response 曲线 | ✅ **本轮完成入场准备，判 `PREPARED`（零仿真；**67/67 校验 PASS**）；★正式 run 未启动 —— 等用户明确启动指令** | 用户裁定网格 **`f = 1.05/1.15/1.25`**（落在 7.6C-2 `f*` 区间 `[1.069,1.164]` 的**下方/内部附近/上方**）。**★机制门（§0）**：`f_demand` 缩放**被仿真 agent 数**（= `f×200,000` → **210k/230k/250k**），`SCALE = 2.29897` **恒定**（复制 agent 连 EF 一起复制；7.6F-0 分解表已证 D01–D04 SCALE 恒 2.29897）；`f_cap=1.00` 冻结排除「采样一致」约定、锁定「物理加车」约定；**若用户意图为「agent 数恒 200,000、仅改算术倍数」则应改走零仿真算术重标定 —— 预注册 §0 已请用户启动前确认**。**三档人口实测** ΣEF = 482,591.7 / 528,733.5 / 574,710.1（`f_realized` 1.0496/1.1499/1.2499）；**★F25 与 7.4.3 `D04` 人口解压逐字节一致**（sha256 `49ff7ccbe622770`）⇒ 复制管线未漂移。**配置验证 67/67 PASS**：与 R01 差异**仅限** `plans.inputPlansFile` + `controller.{outputDirectory,runId}`；route-choice 4 项 / `f_cap=1.00` / seed 4711 / λ 0.075 / `MUST_MATCH_R01` 19 项逐值相同；P9 断言 **8 个冻结件 mtime 未变**。**★预注册落盘** G1–G7 + 判决空间（`AWAITING_RUNS`/`RESPONSE_UNSTABLE`/`NON_MONOTONIC`/`STABLE_PARTIAL`/`STABLE_CROSSES`）。**评价器零仿真自检（`AWAITING_RUNS`）与 7.6C-2 / 7.6D 审计缓存对账 7/7 全中**（R01 三口径 **0.8589732 / 0.9350621 / 0.8909674**；`Q̄_10:19` MATCHED/ALL/CATA/SLIP **逐位相等**）；R01 锚点 `A_10:19`(MATCHED)=**1.0009%**、空间残差 EAST −32.20% / `radial_in` −28.80%（与 7.6C-1 逐值一致）。**未启动任何 MATSim 仿真；未选 demand scale / 未评价 λ**；**`outputs/` 与 `logs/` 为空** |
| **7.6G** λ 敏感度 screening（`λ = 0.05 / 0.075 / 0.10` × **统一 f = 1.18**，N_sim = 236,000） | ✅ **完成，判 `LAMBDA_DETECTABLE_NOT_IDENTIFIABLE / SPATIAL_INERT`（三档全 PASS：77.36/81.63/77.01 min，累计 3.93 h；评价 21/21）** | **★机制前提**：λ 由**人口文件**承载（config 无 λ 形参）；**λ 不变性**（`ΣT` 1,935,235 / `car_od_total` 459,794 / `ΣEF` 459,794 **三档逐位相同**）⇒ SCALE **2.29897 天然 λ 不变** ⇒ **无需上游重建（3 跑，非 12 跑）**。**★λ 响应（MATCHED, 08-09）**：`Sim/Obs FROZEN` **1.0125538（λ=.05）→ 0.9998291（.075）→ 0.9893922（.10）**，**单调**；Δ(0.05→0.10) = **−2.3162 pp** ⇒ 隐含 **Δf\* = +0.03015**（λ 全跨度仅把 f\* 移动 **±0.0151**）。**★直跑复核 7.6F-1 插值**：`L75 @ f=1.18` 实测 0.9998291 ⇒ 隐含 f\* = **1.180222** vs 插值 **1.1803**（差 **0.007%**）⇒ 插值可信。**★判决定位**：2.3162 pp **> 噪声底 1.0 pp**（可检出）但 **< 靶场辨识下界 7.609 pp**（不可辨识）⇒ **λ=0.075 保持为「敏感度中心」，不得声明为数据最优**；**7.6H 出两层结果**（点估计 ＋ λ 不确定带 **[1.1637, 1.1938]**）。**★空间**：EAST 极差仅 **0.91 pp** / `radial_in` **0.40 pp**（缺口 **−31 pp** 量级）⇒ **`SPATIAL_INERT`**；λ 最强处＝远端 **NORTH-EAST 1.79 pp / NORTH 1.49 pp**。**★稳定性承继**：`A_10:19`(MATCHED) 0.85–1.00%、`parity_gap_rel` ≤ 0.15% ⇒ `STABILITY_PASS` 继续保持。**★修复**：评估器 7.6D 对账原误读逐迭代表（`KeyError: 'metric'`）⇒ 改用 7.6F-1 的 **C2** 写法，对账 **4/4 逐位相等**；并补上缺失的 `STEP7_6G_REPORT.md` 渲染 |
| **7.6H** 最终工作点确定与独立验证（`W01`，λ=0.075，**N_sim=236,044**） | ✅ **完成，判 `WORKING_POINT_FROZEN_AND_REPRODUCIBLE / SPATIAL_RESIDUAL_PERSISTS`（`W01` 单跑 `exit=0`，**102.22 min**，iters 20/20；零仿真评价 **26/26 校验 PASS**）** | **★第一层冻结**：`λ_ref=0.075` / `f_demand,ref=1.180222` / `SCALE=2.29897`（⛔ **不按 ΣEF/N_sim 重算**）/ `f_cap=1.00` / `R01_rc_min` / 7.3.6A crosswalk / `N_base=200,000`。**★第二层**：`N_sim = round(1.180222×200,000) = 236,044`（ΣEF 542,628.837，`f_realized` 1.1801564）（★算术披露：`1.1802×200k = 236,040`，差 4 agent / 0.0017%）。**★H1 可复现**：`Sim/Obs FROZEN` **0.999335**（Δ **0.0665 pp**）、隐含 `f*` **1.180866**（Δ 6.44e-4）、`f_realized` 1.1801564（Δ 6.6e-5）、vs 7.6G `L75` Δ **0.0494 pp**。**★H2 稳定**：`A_10:19`(M/C/S) **0.8899/0.9038/0.8568%**、`parity_gap_rel` **0.0964%**、`Q19/Q̄` **1.001972**（Δ 0.1972%）、**`never_arrived=0` / `max_stuck_car=0`**。**★H3 空间残差仍在**：8 组 max \|Δ vs `L75`\| = **0.7599 pp**（格局保持，≤2.0 pp）；EAST **−31.75%** / `radial_in` **−30.67%** / NE **+33.88%** / CENTRAL −7.82% / NORTH +23.09% ⇒ **不追求消除**。**★H4 三层带独立、未合并**：工作点 `f*` **1.180222** / λ 敏感带 **[1.1637,1.1938]** / 静态靶场带 **[1.06945,1.16418]**。**★H5 未解决**：量级达标，空间残差对 demand/λ 低敏感 ⇒ 不宜强行消除；三项本地不可定量。**★对账**：X1 3/3（Δ ≤ 4.9e-8）+ X2 4/4（**Δ = 0.00e+00**）；SCALE 审计 R01 **0.00 ppm** / W01 **−53.88 ppm**（仅披露） |
| **7.7A** 入场审计（LTA 分车型交通量可得性 + 构成归因先验） | ✅ **完成，判 `VEHICLE_TYPE_VOLUME_UNAVAILABLE` / `COMPOSITION_EXPLAINS_GLOBAL_LEVEL_NOT_SPATIAL_PATTERN`（零仿真只读；6/6 校验）** | 本地**无分车型交通量**（`TrafficFlow_Data.json` 字段全集 **10 个**、`Volume`=全部机动车合计；DataMall 无分类计数端点；`data.gov.sg` 仅全国年度车队构成）。构成归因：region r=**−0.3600**（符号相反）/ PA r=**+0.2533**（R²=**0.0641**）；残差极差 **65.6 / 206.4 pp** vs 构成极差 **17.1 / 36.5 pp**（**3.83× / 5.66×**）。**全域 `car_share_pmv = 0.682452` ↔ 7.6A D01 `Sim/Obs = 0.6830`（差 0.07%）** ⇒ 车型构成只解释**总体量级**、不解释**空间分布**。唯一本地车型线索 = 90 台摄像机 × 8,552 帧。**严格版 `BLOCKED_ON_EXTERNAL_DATA`** |
| **7.7C-0** 空间残差归因基线审计（6 维：OD 供需 / 方向性 / 道路等级 / 几何拓扑 / 长度 / PA 梯度） | ✅ **完成，判 `RESIDUAL_LOCALIZED_TO_PA_LOCATION`（零仿真只读；14/14 校验；173.8 s）** | 机制层 = `pa_location`/`network_topology_twin`/`distance_impedance`/`region_location`/`directionality`；**排除** `road_class`/`section_crosswalk`/`observation_semantics`/`network_representation`。★`radial_in\|recip=False` 子组 ratio **0.9915≈1**；`has_reciprocal_pair` 2 组 η²_excess **0.1423**。MUST_MATCH 逐位复现 7.6H（8.674e-17）。产物 `reports/spatial_residual_7_7c0/` |
| **7.7C-1** 时段实现敏感性（零仿真解析上界，断面级 temporal shape） | ✅ **完成，判 `TEMPORAL_SPATIAL_SENSITIVITY_FAIL_DEFER_HTS`（零仿真；7/7 校验；**ratio = 0.1104**）** | ★**方法学修正**：全局标量乘子 ⇒ `rel_dev` 恒等不变（退化）⇒ 改**断面级** `share_8_9(s)`（6.3.3A 底表，CV **0.0909**）。**效应分离**：水平（Sim/Obs **0.9993→0.4972**）vs 结构（`rel_dev_g`）。**★命名组 envelope**：EAST [−0.3549,−0.2992] / NE [+0.3285,+0.3417] / `radial_in` [−0.3283,−0.2983] ⇒ max\|Δ\| **0.0374** vs 残差 **0.3388** = **11.0%**。**region/radial 排序 7/7 profile 保持**。P0 MUST_MATCH 7.6H 逐位。⛔ HTS 暂不接入 |
| **7.7D** 空间残差归因收口（零仿真收口审计，10 门） | ✅ **完成，判 `SPATIAL_RESIDUAL_ATTRIBUTION_CLOSED_WITH_UNRESOLVED_STRUCTURAL_LAYER`（硬门 7/7 + 软门 2/2；零仿真）** | 归因三类闭环：已解释（f / λ / 构成·总量级）/ 已排除（road_class·section aggregation·observation semantics·temporal realization·scalar demand·λ）/ 未解释（PA/OD allocation、twin、directionality）。★适配器：预置版**占位路径**致 6/8 门**假 BLOCKED**，修正为真实产物路径（**判定阈值未改**） |
| **7.8** Final Model Freeze & Validation Package（最终模型冻结） | ✅ **完成，判 `FINAL_MODEL_FROZEN_AND_REPRODUCIBLE`（零仿真定版；硬门 **23/23**）** | **从「研究」切到「定版」**。**7.8A 参数冻结**：`f_work=1.180222` / `λ_ref=0.075`（⛔ **非最优 λ**）/ `SCALE=2.29897` / `f_cap=1.00` / `R01_rc_min` / `N_sim=236,044` / 7.3.6A / target **0.8589732**；三层带**不合并**。**7.8B 输入与算法版本锁**（Input/OD/Sampling/Network/RouteChoice/Crosswalk）⇒ 后续任何修改 = **新版本 v1.1**。**7.8C 验证包**：`Sim/Obs FROZEN` **0.9993347697** / implied `f*` **1.180866** / `f_realized` **1.1801564**；`A_10:19`(M/C/S) **0.8899/0.9038/0.8568%**、`parity gap` **0.0964%**、`Q19/Q̄` **1.001972**、`never_arrived=0`/`max_stuck=0`、dep=arr=**236,044**；X1 Δ≤**4.9e-8** / X2 **Δ=0.00e+00**。**7.8D 空间残差边界（保留不藏）**：EAST **−31.75%** / `radial_in` **−30.67%** / NE **+33.88%** / ORCHARD **+142.00%** / BUKIT TIMAH **+138.61%** / TUAS **−86.99%** / HOUGANG **−86.98%** ⇒ **Final Model — Known Spatial Residual Boundary**（55 行），状态 `UNRESOLVED_STRUCTURAL_LAYER`。**7.8E Manifest**：`Singapore_OD_MATSim_Final_v1.0` + 14 件冻结输入 sha256。**#168 门 23/23**（含 G22 跑前后冻结件 mtime+sha256 逐位未变 = read-only 硬证据）。**★停止规则**：7.8 完成 STOP；后续 = **7.9 Structural Repair / v1.1**（新研究问题），⛔ 非「把 0.9993 调到 1.00」。产物 `reports/final_model_7_8/`（9 件，含 6 件正式产品）。**★本步自查 2 处脚本缺陷**（G6 四舍五入常量配逐位比较 / G21 manifest 自身写入前扫描）已修 |
| **7.8-VIZ-RUN** VIA events 重跑（输出层重执行，**非新版本**） | ✅ **完成，判 `VIA_EVENTS_REPRODUCTION_CONFIRMED_BITEXACT`（过程门 **40/40**；117.67 min）** | 7.8 定版 W01 **无 events**（`writeEventsInterval=0`）⇒ VIA 车辆层无法工作。新目录 `matsim_viz_7_8/`，白名单差异**仅 3 项**（outputDirectory / runId / writeEventsInterval `0`→`19`），**214 参数全展开逐位比对、非白名单差异 = 0**。**重放 `BITEXACT`**：it.19 linkstats **693,575/693,575 max\|Δ\|=0.0**；events **163,305,988** 条 / 1.69 GB；`dep=arr=**236,044**`（零滞留）/ `entered_link=left_link=80,708,818`；**14 件冻结输入跑前后 sha256+mtime 逐位未变**；冻结 W01 仍 0 events（未污染）；7.8 复跑 **G22 `changed=[]`** ⇒ **v1.0 身份不变**。★两 events 文件**字节相同**（1.69 GB 冗余）。⛔ 本产物**不得**作新标定证据。**★自查 4 处**（漏 `<parameterset>` 致假安全 diff / 键名靠猜 / 重放判定写死逐位 / Edit 静默丢改动 ×3） |
| **7.8-VIA-DIAG** VIA 早高峰「不拥堵」诊断（零仿真只读派生，**非新版本**） | ✅ **完成，判 `VIA_UNCONGESTED_IS_THREE_LAYER_ARTEFACT`（只读；<2 min）** | 三层：① **VIA Network 层无交通属性** ⇒ 须另加 `Dynamic Link Attributes` 层（手册 §3.2.5）、窗口设 08–09、按 `speed` 着色；② 路网 **693,575 碎段 / 中位 11 m**（>1 km 仅 **23** 条）+ 行程时间取整秒 ⇒ 短段倍率失真；③ **v/c 恒 ≤1**（max 1.000000）、拥堵指数 **1.4143**（剔 ≤50 m 后 **1.2091**）。★「按条数 57% 超 1.2，按长度仅 34%」= 地图偏绿成因。产物 `reports/via_congestion_diagnosis_7_8/`。⛔ 不作标定证据 |
| **7.7E** 拥堵状态合理性审计（E1 容量来源 / E2 走廊聚合 / E3 空间连续性 / E4 峰值演化） | ✅ **完成，判 `CONGESTION_STATE_PLAUSIBILITY_AUDIT_COMPLETE`（零仿真只读；硬门 **20/20**）** | **★两条口径更正**：① `v/c ≤ 1` 是**结构性质**（流出被容量截断 ⇒ 超额走上游排队），`v/c = 1.000000` = **饱和 + 排队**、**不是**容量富余（更正 7.8-VIA-DIAG）；② **★★`qsim.timeStepSize = 1 s` ⇒ `TT = ceil(FF)`**，链路 FF 中位 **1.37 s** ⇒ 既有「拥堵倍率」口径被**量化污染**（空网 12–13 时仍报 **1.552 ≈ 基准 1.596**）。**E1**：`capacity = lanes × capacityPerLane(road_type)`；快速路 **1900/1800/1700 在参考带内**，超上沿的是干道/地方道路 ⇒ **H1 不成立**；已载流利用率 **12.8%**、快速路走廊 **28.5%**。**E2b**：10 条快速路原始 `TT/FF` **1.20–1.44** → **扣量化后 9/10 ≈ 0**（**仅 CTE +0.085 / 105 车时**）。**★按道路类型分解 4,779 车时真实延误**：**`service` 占 94.4%（4,509 h）**、`motorway` 仅 **105 h（全在 CTE）** ⇒ 真实延误主体是 **20 km/h 单车道接入短段（400 辆/h）局部瓶颈**、**不是快速路排队**。**饱和链路 82 条 / 1.15 km**（74 条 `service` 6 m 段 + **8 条 CTE motorway 组成 ≈0.40 km 排队链**）。**E3**：200 次置换 —— 原始口径最长连续链 **0.601 / 0.420 km** 均**短于**随机（z 负 ⇒ 比随机更分散 = 伪影特征）；**扣量化后 0.499 km、p = 0.165、z = +0.46（不显著）** ⇒ **无连续拥堵走廊**。**E4**：峰值在途 **36,799 @ 08:55**（agents 的 **15.6%**）、`Σ流量/Σ容量` 峰值 **0.102**、真实超额 **+0.083~+0.221** ⇒ **无拥堵波**；events↔linkstats Δ **0.0000%**。**判决**：H1 不成立 / H2 主因 / H3 成立（放大错觉）/ **H4 度量伪影（决定性）**。★**「流量校准成功 ≠ 拥堵状态校准成功」**（0.9993348 vs 利用率 12.8%）。⛔ **不得为让动画变堵而放大 demand**；正解 = **7.9 Structural Repair / v1.1**（含调小 `timeStepSize` 或改用逐车行程时间评价）。产物 `reports/congestion_plausibility_audit_7_7e/`（22 件） |
| **7.9A-0** 采样—容量一致性审计（四值核实 + 采样比例对账 + 零仿真投影） | ✅ **完成，判 `SAMPLING_CAPACITY_CONSISTENCY_AUDIT_COMPLETE` / `SAMPLING_CAPACITY_INCONSISTENCY_CONFIRMED`（v1.0 冻结后只读；硬门 **22/22**；~10 s）** | **7.9 第一阶段（结构审查），⛔ 非 7.8 前置步骤、结果不回灌 v1.0**。**四值**：`qsim.flowCapacityFactor=1.0` / `storageCapacityFactor=1.0` / `trafficDynamics=queue` / `timeStepSize=00:00:01`（四源逐位一致）。**★惰性诱饵（新坑）**：`dsim.trafficDynamics=kinematicWaves` 与 `hermes.*CapacityFactor=1.0` 均因 `mobsim=qsim` **不生效** ⇒ A-1 唯一旋钮 = `qsim.*`。**★★分母歧义（最重要）**：`N_sim/ΣEF` = **0.513369**（⛔ 误用）vs `1/SCALE` = **0.434977**（✅ capacity 一致性因子），比值恒 = `f_work` **1.180220**。**量纲证明**：`Sim/Obs=1` ⇒ `F_real = SCALE·F_sim`，要 `v/c_sim = v/c_real` ⇒ `C_sim = C_real/SCALE`；`ΣEF` 是需求锚、不参与流量扩样分母。**物理含义**：236,044 辆 = 真实 **43.4977%** 样本跑在 **100% 容量** ⇒ **`v/c_sim ≈ 0.43498 × v/c_real`**。**★零仿真投影（冻结流量上界）**：`n(v/c≥1)` **82 → 4,187**、饱和里程 **1.151 → 178.114 km**（占全网 15,126.5 km 的 **0.008% → 1.177%**）、峰 `aggV/C` **0.102447 → 0.235522** ⇒ **仍不预期全网级拥堵波**（→ 情形 C 优先）；方向 = 在途峰 ↑ / 通过量 ↓ / **`Sim/Obs` 下移**（⛔ 0.9993 **不得**作 A-1 目标，仅崩解护栏 ≥0.85）。**A-1 计划**：`qsim` 两因子 `1.0 → 0.434977`（单点派生、**不扫描**）、v1.1 新版本。★自查 3 处：① `E4.entries` 是**累计链路进入数**、非在途量（首版 A0.21 误读，改用 legHistogram `enr_car` 后复现 **36,799 @08:55**）；② `SCALE×N_sim` 是**车辆数**非流量率；③ md 表格含 `|` 会拆列 ⇒ 统一转义。⛔ 未跑 MATSim、冻结件跑前后 mtime 快照 **`changed=0`**、**7.8 门 23/23 不受影响**。产物 `reports/sampling_capacity_audit_7_9a0/`（8 件） |
| **7.9B-0** 交通动力学机制审计（B1 生效动力学 / B2 `queue` 有无 inflow 约束 / B3 `r_fdiag` 被卡集合 / B4 merge–diverge 富集 / B5 碎片化有效尺度） | ✅ **完成，判 `TRAFFIC_DYNAMICS_MECHANISM_AUDIT_COMPLETE`（v1.0 冻结后只读；硬门 **16/16**；~8 s）** | **7.9 第二阶段（结构审查），⛔ 非 7.8 前置、不回灌 v1.0**。**B2（源码级）**：`QueueWithBuffer` 中 `case queue: case withHoles: break`（L393–396）⇒ `maxInflowUsedInQsim` 恒 = `flowCapacityPerTimeStep`（L391）⇒ **`queue` 无额外入口约束**；`inflowCapacitySetting` 未设 ⇒ MATSim 默认 **`INFLOW_FROM_FDIAG`**。**B3**：`r_fdiag < 1` 的 link = **21,670（3.1244%）/ 869.589 km（5.7488%）** ⇒ **KW 的作用集合比 A-1 的 1.18% 饱和里程大约 5×**；贡献最大 = arterial 50–70（492.4 km），其次 expressway ≥90（212.9 km, 97.98%）、fast 70–90（138.1 km, 100%）；★被移除入口容量 **8,784,415 veh/h**；★`MAX_CAP_FOR_ONE_LANE` 与 `INFLOW_FROM_FDIAG` 的 r<1 集合**代数恒等**。**★B4 预登记假设被证伪**：「被卡 link 集中 merge/diverge」**不成立** —— 全样本 **0.268×**、同类别 0.18–0.65×、严格 in-degree≥3 **0.090×**，from-node 平均入度 **1.207 vs 1.882** ⇒ KW 入口上限是**对高速/高容量路段的整体 ~10–11% 削流**，**非**节点级瓶颈机制 ⇒ ⚠️ **可能让地图变堵却不提升结构保真度**（与红线同构）⇒ B-1 必判「拥堵**位置**」是否落在 7.7E 的 CTE/`service` 短段。**B5**：link 中位 **11.0 m**、24.34% 里程 < 20 m；节点间距 **35.9 m**、度 ≥3 节点 **16.0 个/km**（每 ~62 m 一个）⇒ **无长「度-2 链」**（中位 corridor = 1 条 link）⇒ **7.9C 用 junction cluster 聚合**；KW 储存放大 **20,922 links（3.02%）**、`queue` 下 0。**★★A×B 非可加**：`maxFlowFromFdiag` **不被 `flowCapFactor` 缩放**（源码 L407–412）⇒ `f_cap=0.435` 时 FD 入口约束在 **0** 条 link 生效、KW 与 `queue` 只差**储存侧** ⇒ 支持 **B1(`f_cap=1.0`) → B2(叠加 0.435)** 串行。**B-1 预登记**：仅 `queue→kinematicWaves`、`Sim/Obs` 仅护栏 ≥0.85、无实质变化即判 `TIMEDYNAMICS_NOT_PRIMARY`。⛔ 未跑 MATSim、冻结件 `changed=0`（201 件）。产物 `reports/traffic_dynamics_audit_7_9b0/`（7 件） |
| **7.9C-0** 结构性瓶颈审计 junction-cluster / short-chain（L1/L2/L3 三层 + C1 结构先验 / C2 残差投影 / C3 HitRate-Coverage / C4 B-1 观察集） | ✅ **完成，判 `STRUCTURAL_BOTTLENECK_PRIOR_ESTABLISHED`（v1.0 冻结后只读；硬门 **25/25**；~35 s）** | **7.9 第三阶段（空间结构层）**。★**网络侧**：结构种子 **50,617** 节点（12.01%）⇒ L1 **22,722 单元 / 460,001 link（66.3%）**（中位 10 link、max 200）；L2 ramp **500** / connector **2,428** / service **11,638** 链；L3 30 corridor（仅宏观、⛔ 非第一判据）。★**C1 先验（零流量；C0.22 源码自检）**：`mean(merge_deficit, lane_narrowing, class_transition, ramp_mainline)` 取单元内**最大值**；均值 0.349 / p80 0.417 / max 0.938；`storage_shortage_proxy` 均值 **0.0058 ⇒ 判别力为零、剔除**。★**C2（检验）**：映射覆盖 **99.7%**（空间兜底 p90 173 m）⇒ **ρ = 0.0355、置换 p = 0.8125 ⇒ 残差未向结构瓶颈聚集**（规模分层后同结论）。★**C3**：v1.0 基线 `HitRate 0.4475 / Coverage 0.3705 / lift 1.852×`，但附**证伪性警告**：饱和 link 仅 **82**（p80 阈值 0.022）+ `ρ(prior,单车道容量)=0.248`、`ρ(v/c,单车道容量)=0.449` ⇒ **lift 被容量污染、非位置证据**。★**C4 B-1 观察集已冻结**（8 层，`c0_C4_b1_observation_set.json`）。★**自检**：v1.0 拥堵基线 **82 link / 1.151 km 与 7.9A-0 逐位一致（C0.17）**；`changed=0` |
| **7.9B-1** `qsim.trafficDynamics: queue → kinematicWaves` 单变量机制实验（L1 动力学 / L2 连续性 / L3 位置） | ✅ **完成，判 `KW_CHANGES_CONGESTION_MECHANISM__KW_POSITION_NOT_IMPROVED__STABILITY_OK`（仿真侧 **49/49** + 分析侧 **14/14**；仿真 177.5 min）** | **7.9 第四阶段（机制实验）。★单变量门**：模型层 diff **恰好 1 项**（`qsim.trafficDynamics`）、输出层 **恰好 3 项**、`VIOLATION=0`；`dsim` 同名诱饵**未触碰**、`inflowCapacitySetting` 未覆盖 ⇒ 默认 `INFLOW_FROM_FDIAG`。**★L1 机制变化 = 有**：`Sim/Obs` **0.9993348 → 0.8506114（−14.9%，险过 0.85 护栏）**、超额链路 **4,705 → 18,860**、延误 **4,778.8 → 12,482.1 h（+161%）**、`A_10:19` **0.8899% → 3.5200%**。**★L2 = 没有长链**：分量 **3,603 → 8,223（更碎）**、最长 **0.857 → 0.954 km**、**超额落候选结构单元比例 32.54% → 29.45%（富集 1.718× → 1.555×）**。**★L3 = 位置未改善**：C3 预登记 lift **1.852× → 1.835×**、`ABS 0.5` **3.548× → 3.204×**、C2 ρ **+0.0267（p .200）→ −0.0078（p .485）**、辅助（真实超额、非预登记）**1.679× → 1.601×**。**★延误去向**：`service` **88.0%**（+6,476 h）、**CTE 仅 24.2 h（0.19%）⇒ 未复现真实快速路排队链**。**★红线**：机制变化成立（仿真可判）／位置改善**不成立**（须空间证据）⇒ **更堵 ≠ 更对**。**★冻结影响 = 无**（实验未采纳 ⇒ v1.0 不变、不产生 v1.1；冻结输入 `changed=0`） |
| **7.9C-1** 结构性回溢验证 Structural Spillback Validation（K1 主线可传播通道 / K2 下游储存 / K3 回压死端 / K4 超短 link 碎化） | ✅ **完成，判 `SPILLBACK_CHANNEL_INTACT__DELAY_TRAPPED_OFF_MAINLINE`（零仿真只读；硬门 **11/11**；**23.7 s**）** | **7.9 第五阶段（拓扑通道层）**。**预注册** `PREREG_7_9C1.md` 于读结果前冻结；主判据为**静态结构量**、仿真延误**仅对账**（test, not definition）。**★K1**：主线 `up_main_m` 中位 **1,957 m**、`≥300 m` 覆盖 **91.52%** 里程 ⇒ **通道完整**（✗ 不支持「被切断」）。**★K3**：`service∪connector` 回压死端 **99.95%**（motorway 0.17%）⇒ **断点成立**。**★K4**：motorway **17.43 links/km**（中位 37.8 m、**0** 条 `>40`）⇒ **快速路不碎**；connector **85.01** / service **50.81 links/km**（中位 8.9–9.3 m、72–89% ≤20 m）⇒ **服务网极碎**。**★K2**：候选 **5,490** 中**仅 7.05% 含主线 link**；**51.02%** 候选 `fill_time<10 s`。**★决定性对账**：v1.0 延误 **4,778.8 h** → motorway **2.50%** / **service 94.36%**；**延误加权通道仅 334 m**（service 内 107 m vs motorway 内 7,921 m）；**97.34% 延误落在回压死端 link 上**（KW 95.97%）⇒ **就地生成、就地吸收**。**★裁决**：用户预设「表达阻断快速路回溢」**未被支持**，改写为**「拥堵被结构性困在离主线的、拓扑终端的接入子系统里」**。**★更正 B-1**：CTE 正名 **104.57 h（2.19%）→ 56.68 h（0.45%）**（旧掩码 1.76→24.22 h 实为 Changi∪Tampines）。**★冻结影响 = 无**（未跑仿真、`changed=0`、不产生 v1.1） |
| **7.9D-0** 接入系统延误滞留审计 Access-System Delay-Trapping Audit（D0 base-rate 控制 / D1 单向阀 / D2 浅储存 / D3 排队耦合 / D4 终端暴露） | ✅ **完成，判 `DELAY_TRAP_OFF_MAINLINE_BY_CONSTRUCTION__BASE_RATE_DOMINATED`（零仿真只读；硬门 **15/15** + 补充 **2/2**；**33.0 s**）** | **7.9 第六阶段（接入结构层）**。**预注册** `PREREG_7_9D-0.md`（sha256 `564310dee…6ee85`，运行期重算 **MATCH=True**）于读任何仿真输出前冻结。**★★base-rate 反转**：全网 `service` delay/km ratio 仅 **1.610**，**限定主线邻域（`d_up≤3`，15,319 links / 2.209%）后 ratio = 0.171（欠表达 8.5×）** ⇒ 主线上**本无压力可沉**；邻域延误 **96.35%** 落在 `motorway+ramp`。**①单向阀证伪**：全岛 sink-valve **仅 13** 节点（`VALVE_PRESENT=False`），mainline-in **8,567** vs out **8,566** ⇒ 主线几乎完全可逆。**②薄储存成立但是查表**：邻域 `fill_time` 中位 **9.18 s**、**89.81%<30 s**；`cap/lanes` 按 `(highway×lanes)` **单值确定（13/13）**，`service`=**400 veh/h/lane**（参考值 **22.2%**）、20 km/h。**③耦合构造性缺失**：延误加权 `d_up`=**72.33 hops**、`share(d_up>3)`=**0.9722**（D=1/3/5 → 0.0278/0.0278/0.0280 稳定）⇒ `COUPLING_ABSENT=True`。**④终端暴露**：236,044 出行中 **90.26%** 至少一端落 `service`（起点 70.68% / 终点 66.85%，对照 km 0.5861）。**补充**：物理上游距主线 **1,952 m**、`≤300 m` 仅 **3.15%**（跳数被碎片化夸大，结论不变）。**★更正 C-1**：K3「99.95%」是**单跳近重言式**（仅 0.049% service 有主线 feeder）；研究对象**收窄为 `ramp`**（唯一邻域富集 ratio 1.597）。**CTE 门断言**：正名 **603 links / 104.57 h(2.19%) → 56.68 h(0.45%)**、旧掩码命中 **0**。**★冻结影响 = 无**（零仿真、未改 network、`changed=0`、不产生 v1.1；**只证明不修改**） |
| **7.9D-1** Ramp Interface Audit 主线↔ramp↔地方路 接口审计（R1 单跳 vs 多跳接口 / R2 车道·容量不连续 / R3 ramp 链长 / R4 局部储存 / R5 延误传播） | ✅ **完成，判 `RAMP_INTERFACE_CONTINUOUS__RAMP_NOT_A_DELAY_HOST`（零仿真只读；硬门 **11/13** + 补充 **3/3**；**19.7 s**）** | **7.9 第七阶段（主线接口层）**。**预注册** `PREREG_7_9D-1.md`（sha256 `5c8fd9c1…8983`，运行期重算 **MATCH=True**）于读任何输出前冻结；**新增永久规则 R-DIST-1**（接口距离一律 **meter/km**，hop 仅辅助）+ **R-MULTI-1**（接口判据必须多跳）。**★单跳近重言式**：`ramp` **11,740 条/308.15 km**，单跳 `neither` **10,886（92.73%）** ⇒ `SINGLE_HOP_TAUTOLOGY=True`。**★多跳接口连续**：`acc_m` 有限率 **100.00%**，ramp 中位 **478 m**/p90 1,467 m，`≤300 m` 30.49%；`egr_m` 中位 419 m；ramp 链长中位 **500 m**、单片段中位 **16.6 m**（58.29% ≤20 m）。**★车道/容量连续**：`on_ramp` 432 条，`Δlanes` 中位 **+2**、车道下降仅 **8 条（1.85%）** ⇒ `LANE_DROP=False`；`Δcap/lane` 中位 **+200**。**★★ramp 非延误宿主**：里程 2.04% / 车流 **9.22%** ⇒ 延误仅 **69.9 h（1.46%）**、`ratio=0.719`、按车流归一 **0.158**（低于全网 6.3×）；延误加权 `acc_m` **647 m** ⇒ **方向通、量太小**。**⚠️ 预注册缺陷**：`R1.05/R1.06` FAIL 系「`min>0`」**逻辑不可能**（主线种子距离恒 0），非数据问题；改列补充门 `S1.01–S1.03` **3/3 PASS**，verdict 不受影响。**★冻结影响 = 无**（零仿真、`changed=0`、不产生 v1.1；**只证明不修改**） |
| **7.9D-2** Terminal Representation Audit 端点表征审计（T2 端点分布 / 自由流接入时间 / 全网 Σvol×ff 分解 / KW 交叉） | ✅ **完成，判 `MIXED__TERMINAL_AND_MAINLINE_COMPARABLE`（零仿真只读 + 自由流时间；硬门 **13/13**；**27.5 s**）** | **7.9 第八阶段（端点表示层）**。**预注册** `PREREG_7_9D-2.md`（sha256 `03f24243…3369`，运行期重算 **MATCH=True**）；⛔ 不改 `service` 400、⛔ 不改端点吸附、⛔ 不读 `output_plans`。**★端点**：O `service` **0.7068** / D **0.6685** / 至少一端 **0.9026**；按组 O `local` **0.9011**。**★自由流接入时间**：`T_acc` 中位 **124.8 s**、`T_egr` **103.6 s**、`T_terminal_lb` 中位 **234.3 s**。**★★全网自由流分解**：总 **24,905.2 车·h**、off-mainline 14,146.7 ⇒ **`share_offmain = 0.5680`**（实际 0.6364；KW 0.6049）⇒ `MIXED`。**★★最重要发现**：off-mainline 由**干道主导（arterial 0.3787）**，`local` 仅 0.0998、**`service` 仅 0.0515** ⇒ **端点暴露面（90%）≠ 时间面（5%）**；`service` link 中位 8.9 m 太短。**★精度修正**：`service` `cap/lane` **严格 = 400**（`SERVICE_CAP_FIXED=True`），但自由流速度**非严格恒定**（10 个值 5–70 km/h，**20 km/h 占 96.80%**）⇒ `SERVICE_SPEED_FIXED=False`；D-0「恒 20 km/h」**仅 p10=p90 意义成立**。**★冻结影响 = 无**（零仿真、`changed=0`、不产生 v1.1；**只证明不修改**） |
| **7.9E-0** Arterial-Layer Delay Attribution Audit 干道层延误归因审计（E1 时间归属 / E2 延误归属+delay_ratio / E3 空间残差耦合+分层置换 / E4 多跳物理距离拓扑） | ✅ **完成，判 `ARTERIAL_LAYER_AUDIT_BLOCKED`（零仿真只读；硬门 **11/12**；**22.1 s**）** | **7.9 第九阶段（干道层）**。**预注册** `PREREG_7_9E0.md`（sha256 `4fa98a96…12ea08f1`，运行期 **MATCH=True**）。**★E1**：`arterial_core` 车时份额 **0.6371**（时间主场），结构份额 0.0676（`service` 0.7924）。**★E2**：`delay_share` `service` **0.5710** > arterial **0.2978**；`delay_ratio` 结构基数 **4.41** vs 车时基数 **0.47**（`service` 0.72 vs **6.43**）⇒ 随基数翻转。**★E3 = BLOCKED**：576 断面中 **77.8% 为 motorway/motorway_link**、arterial 仅 **12**（<30）；欠功率参考 mean +0.0776、置换 p≈0.83、Spearman −0.0213。**★E4**：arterial→mainline 中位 **1,309.9 m**、p90 2,324.5、`≤300 m` 5.32%、hop 52（辅）。**★冻结影响 = 无**（零仿真、`changed=0`、不产生 v1.1；**只证明不修改**） |
| **7.9E-1** Arterial Observability Expansion 干道可观测性扩展（独立 diagnostic crosswalk / A·B·C 三档置信 / RoadCat×highway 矩阵 / 残差耦合） | ✅ **完成，判 `OBSERVABILITY_BLOCKED`（零仿真只读；硬门 **10/12**；**24 s**）** | **7.9 第十阶段（可观测性层）**。**预注册** `PREREG_7_9E1.md`（sha256 `4d5ee3e1…6751d`，运行期 **MATCH=True**）。**★匹配质量**：A+B 覆盖 **97.48%**（1,278/1,311，**上界**）、中位 **0.57 m**、p90 **2.92 m**、方向差中位 **1.38°** ⇒ 非瓶颈。**★全量可标出 542 条 `arterial_core`**。**★★根因**：576 残差断面 `RoadCat` 仅 `CATA` 326 + `SLIP_ROAD` 250，A+B 代表链路 `motorway` 328 / `motorway_link` 247 / `primary_link` 1 ⇒ **arterial residual n = 0**（三档全 0）⇒ **冻结靶场定义域不含 arterial**，非匹配质量、非 arterial 样本少。**★判决** FAIL = E1.09/E1.10（真实结构结论）。**★R-OBS-1~5**：正式与诊断 crosswalk 永久分离、先证可观测再判归因。**★冻结影响 = 无**（⛔ 不回灌 v1.0、不产生 v1.1） |
| **7.9E-2** Expanded Diagnostic Residual Domain 扩展诊断残差域（复用 E-1 独立 diagnostic crosswalk / 冻结 SCALE 口径 / RoadCat 分层置换 / formal bridge / 事后稳健性） | ✅ **完成，判 `NO_ARTERIAL_COUPLING_SIGNAL`（零仿真只读；硬门 **12/12**；**60–73 s**）** | **7.9 第十一阶段（扩展诊断残差域）**。**预注册** `PREREG_7_9E2.md`（sha256 `c9e68272…e6cc`，运行期 **MATCH=True**）。**★可观测性解决**：A+B 覆盖 **97.48%**、有效残差 **1,278**、**arterial n 12 → 542**。**★formal bridge**：overlap **576/576**、Spearman **0.9662** / Pearson **0.9398**、MAE **0.0722**、RMSE **0.4655**。**★耦合**：arterial 均值 **+0.0027** vs 非 arterial **+0.0904**，Spearman **−0.0216**、η² **0.0013**、非分层 **p=0.1969**、**RoadCat 分层 `p=0.05247`（临界，≥0.05 ⇒ 无信号）**。**★事后稳健性（不改判决）**：分层统计量 **69.3% 来自 CATA 单条误映射 `primary`（残差 −1.000）**；仅 CATB（490 vs 144）`p=0.0080`、去 CATA `p=0.0400`、去 CATB `p=0.1679`。**★★真实结构**：残差按等级**单调梯度**（motorway +2.0% / primary +7.6% vs trunk −20.2% / secondary −34.6% / tertiary −41.7%，flow-weighted）⇒ **`arterial_core` 三类符号相反、聚合均值是抵消伪影**。**★R-RES-1~6**。**★冻结影响 = 无**（⛔ 不回灌 v1.0、不产生 v1.1） |
| **7.9F-0 v2** Highway Grade × Capacity/Speed 结构审计（零仿真只读） | ✅ 完成，判 `GRADE_CAPACITY_AUDIT_READY`（正式硬门 **12/12** + 补充 **3/3**） | 目标域 = E2 secondary/tertiary residual（有效 join **1,278**）；runtime XML links **706,554**；E2 A/B main rows **1,311**。**★容量 = 纯查表**（`cap = lanes × cap_per_lane[highway]`，组内 min=max）⇒ 无 link 级信息 ⇒ **分层相关恒 NaN、容量非绑定**；`service` = **400 veh/h/lane**（参考值 22.2%）。prereg `31d61dc8…`。产物 `reports/highway_grade_capacity_7_9f0_v2/` |
| **7.9F-1 v2** Section Aggregation Sensitivity Audit（零仿真只读 diagnostic-only） | ✅ 完成，判 `AGGREGATION_AUDIT_READY`（正式门 **12/12**；check rows 18 / 通过 15） | 轨迹 **1,311**；**CANONICAL_MEDIAN 零断面 83 = 68 真零 + 15 median 塌陷**（zero obs-flow share **6.36%**）；**obs 加权残差 −0.0139 → +0.0110**、sim 加权 0.8127 → 0.8239（对照 POSITIVE_MEDIAN）。candidate rows **15,783** / selected **6,773**；W01 links **693,575**、corridor **124**；E2 canonical max abs delta **0.0**。⛔ **不替换 canonical**、替代聚合仅 diagnostic。prereg `75bab7e2…` |
| **7.9F-2 v2** secondary/tertiary 单链路捕获机制审计（零仿真只读） | ✅ 完成，判 `MECHANISM_AUDIT_READY`（硬门 **16/16**） | target **109**（secondary 89 / tertiary 20）、selected anchors **593**；E1 raw **67,471** → kept **15,783**（丢 tier C 51,688、缺 distance 0）；network **706,554** / W01 **693,575**；radii **20/50/100 m**、parallel ≤30°、twin ≥150°；obs crosswalk max abs delta **4.5e-13**、mismatch **0**。**⛔ D4/Q2 结构性不可答**（`STRUCTURALLY_UNANSWERABLE__DESCRIPTIVE_ONLY`）、**⛔ D5 不可比** ⇒ 只作描述。prereg `018d1562…` |
| **F-2 v2.1-R2** 局部捕获诊断执行契约闭环（零仿真只读） | ✅ 完成，判 `LOCAL_CAPTURE_DIAGNOSTIC_READY`（硬门 **18/18**、EXIT=0、`contract_pass=true`） | target **109**、E1 candidates **67,471**、selected anchors **593**、network **706,554** / W01 **693,575**；`preflight_passed=true`、obs rebuild max abs delta **0.0**。**★AST 双向契约自检 = 18 号门（loader 前求值）**；**preflight = 05/06 唯一权威**；**manifest 最后生成且不自哈希 + `closure_check.csv` 物化**。**★Q2 由 probe 升为正式 negative diagnostic**（`…_R2_asprovided_diag/Q2_FORMAL_DIAGNOSTIC.md`，2026-09-27）：候选方向结构（forward/reverse share、方向差中位、相关性）**不能解释** secondary/tertiary residual；方向差中位 **≈90°**、neutral 中位 **0.54**、abs ρ **≤0.116**；⛔ **negative diagnostic，非「方向机制不存在」的物理证明**。prereg `0a0c6133…` |
| **★Q4-R1-R1** nearest-single-link 局部捕获（4 类邻域 × 3 半径；零仿真只读） | ✅ **正式 READY 节点（用户裁定 2026-09-28）**，判 `Q4_LOCAL_CAPTURE_READY`（硬门 **25/25**、EXIT=0、`CLOSURE=OK`、`converged=True; it=4`） | prereg `82a03eb8…`（16,772 B）/ 脚本 `1cbeb201…`（98,312 B）。**★4 类 × 109 × 3 半径 = 1,308 格**（各 327）：`parallel` / `twin` / `same_name_parallel` / `same_name_twin`。**★选择规则（不可改）**：`min distance → min direction diff → min link_id`；W01 flow/residual/ratio **禁参与选链**。**门 20 真独立重导**（从 `candidate_pool` 重算 → **1308/1308**、`max abs Δ = 0`）；**门 22 独立重导 `SELF(sid)`**（self/anchor/pool/radius/type violations **全 0**）；**门 23 = AST 语句区间**（`banned_hits=[]; flow_after_selection=True`）；**门 16 = WRITEBACK**（三方一致、`byte_mismatch=[]`、`n_byte_compared=12`）；**门 25 = 非 Q4 产物 vs R2**（`identical=8/8` + 本地重算 `2/2`）。**负例 10/10**（N1→19、N2→19、N3→20+21、N4→20+21+23、N5→20+21、N6/N7→22、N8→24、N9→15、N10→25）；**BLOCKED 路径 3/3 完整节点**。**★同层对照（R2 max-flow → R1-R1 nearest）median ratio 20→100 m**：sec/parallel **+0.365 → +0.020**、ter/parallel **+0.499 → +0.007**、sec/twin +0.0915 → −0.0033、ter/twin +0.0042 → −0.0879 ⇒ **nearest 规则去掉 max-over-N 单调膨胀**。**★R-Q4R1R1-1…7**。产物 `reports/secondary_tertiary_residual_7_9f2_Q4_R1_R1/`（15 件 + `inherited_r2/` 8 件） |
| **7.9G-0** `service` 延误机制 R0 结构审计（三问：容量是否为延误主因 / 94.36% 口径是否稳定 / `service` 参数是解释量还是机制旋钮） | ✅ **完成**，Q1 `CAPACITY_CONSTRAINT_NOT_DOMINANT` / Q2 `CALIBER_FRAGILE` / Q3 `SERVICE_PARAMS_DERIVED`（零仿真只读；硬门 **25/25**、EXIT=0、`CLOSURE=OK`、`converged=True; it=4`） | 口径继承 7.7E：`delay_corr_h = Σ_{v>0} v·max(0, TT8-9avg − ceil(ff_s−1e-9))/3600`。**★Q1**：`service` 已载流 **62,407** 条、`v/c` 中位 **0.0225**；饱和仅 **74（0.1186%）**、只担 **13.95%** `service` 延误；集中度 top-10 **62.17%** / top-100 **96.01%**；长度桶 `>60 m` 29.02% / `≤5 m` 24.68%。**★Q2**：`raw` **45.904%** vs `corr` **94.357%**；暴露面 time **94.36** / count 27.81 / distance 18.56 / volume **4.31**（%）；跨时段 92.79/94.36/98.52/99.999 ⇒ 极差 **0.0573 > 0.05** ⇒ **FRAGILE**。**★Q3**：`service` `cap = 400×permlanes` **100.000%**、全网 `unit_cap×lanes` **99.689%**、`qsim` 两因子 1.0 **无覆盖**；输入仅 `permlanes` / `unit_cap[service]=400` / `freespeed`。**★验证**：负例 **11/11**、BLOCKED **3/3**、独立复核 `VERIFY_OK=True`。prereg `2db351c8…` / 脚本 `61cfe26a…`。**★R-G0-1…5**。产物 `reports/service_delay_mechanism_7_9g0/`（15 件） |
| **7.9G-1** 端点/接入子系统「就地吸收」机制审计（可证伪命题：`service` 延误是否主要表现为端点接入/局部循环/短链时间表达的「就地吸收」，而非道路容量约束产生的排队延误） | ✅ **完成**，A1 `PROPORTIONAL_TO_MILEAGE` / A2 `ENDPOINT_LOCALIZED` / A3 `NOT_MAINLINE_QUEUE` / A4 `NEITHER_BOUND` / A5 `NEGLIGIBLE` / A6 `ENDPOINT_ABSORPTION_DOMINANT`（零仿真只读；硬门 **25/25**、EXIT=0、`CLOSURE=OK`、`converged=True; it=3`；契约 **236,044³**） | **★A2 决定性**：端点 `service` **10,156** 条（296.4 km）担延误 **3,410.52 h = 全网 71.37% / `service` 内 75.64%**，只占 `service` 流量 **9.77%** ⇒ 逐车 **72.81 s/veh vs 2.54 s/veh（28.7×）**；`f_pos` **0.088818** vs `w_ep` **0.756366** ⇒ **位置面被证伪、端点归属成立**。**★A3**：邻干道 `service` 仅 **1.8736%** vs 内部 **92.4830%** ⇒ 非主线回溢。**★A4**：`sat_share_D` **0.1394** / `cell_share_D` **0.4961**（均 <0.50）⇒ `NEITHER_BOUND`。**★A5**：`f_local` **0.001296**（306/236,044）⇒ `NEGLIGIBLE`（**局部循环支路被证伪**）。**★A6**：`s_end` **71.3681%** / `s_mid` **22.9884%** / `s_main` **1.8736%**。**★暴露四面**：time **94.36** / count 27.81 / distance 18.56 / volume **4.31**（%）。**★events**：12 链 `n_enter≥1` 全齐，`dwell_p50` **280–6,423 s** 而链长 **1.9–140.8 m**。**★验证**：负例 **11/11**、BLOCKED **3/3**、独立复核 `VERIFY_OK=True`。prereg `4e7ffa3c…` / 脚本 `audit_endpoint_access_absorption_7_9g1.py`。**★R-G1-1…8**。产物 `reports/endpoint_access_absorption_7_9g1/`（16 件） |
| **7.9G-2** 「时间 / 数量 / 距离 / 体积」四面口径统一（可证伪命题：**既有四面统计口径是否自洽？统一后的 reporting rule 应如何表述？**；⛔ 不重开 G-1 机制结论） | ✅ **完成（2026-09-29）**，`Q1 = DENOMINATOR_SPLIT` / `Q2 = EXPOSURE_IMPACT_DECOUPLED` / `Q3 = CONCENTRATION_ATTENUATED` / `Q4 = FOUR_FACE_PARALLEL_REPORTING`（零仿真只读；硬门 **25/25**、EXIT=0、`CLOSURE=OK`、`converged=True; it=3`、**47.8 s**；`noop_selfcheck_passed=True`；脚本 `scripts/od/audit_caliber_harmonization_7_9g2.py` **73,426 B**） | **★锁 5 事**：①统一分母栈 `D0 = ALL ⊃ D1 = SVC ⊃ D2 = EP_SVC`；②**宇宙必须声明**（默认 `U_loaded`，`U_any` 须带 `_any` 后缀）；③**暴露（count/km/vol）≠ 影响（time）**，不互替；④**不合成总分**；⑤集中度用**覆盖率分数 `f_t`**，⛔ Gini / 常数 `k` 禁用。**★阈值（预先约定）**：`0.5 pp` / `5.0 pp` / `3.0×`。**★侦察（第一手）**：宇宙撕裂可致 **>100%** 份额（`SVC_any` km = `ALL_loaded` 的 **170.96%**）；同对象两个 distance share（**5.716%** vs **3.922%**，差 **1.79 pp**）；Gini **失效**（`ΔGini = −0.0014`、符号反直觉）；`f50` **19.6×** ⇒ 子集内部**相对更分散**；`s/veh` **169.3×**。**★四面实测（EP_SVC｜D0）**：time **71.3681%** / count **3.1560%** / distance **3.9220%** / volume **0.4215%**（极差 **70.95 pp**）。**★实现验收（2026-09-29）**：16+1 件产物；`RANGE_ep = 70.946627 pp`、`universe_spread_pp = 1.962541`、`illegal_mixed_universe_ratio = 1.709605`（170.96%）、`R_50 = 19.803755` / `R_90 = 6.643841` / `R_99 = 1.032118`、`s/veh` ALL 0.430002 → SVC 9.407303 → EP_SVC 72.806547（**169.32×**）；`EP_SVC_any` n **10,156** / km **296.402279**。**★独立复核** `scripts/od/_verify_g2.py` **90/90** `INDEPENDENT_REPRODUCTION_OK`；**★负例** `scripts/od/_g2_negatives.py` **11/11 fired** + `S1 fired=False` + **3/3 BLOCKED complete**。**★口径发现（7 项）**：① 时间面逐位一致**必须 `math.fsum`**（pandas/numpy 顺序求和差 1 ulp = 9.095e-13）；② **pandas 默认解析丢 1 ulp**（`296.40227899999996`→`296.402279`、产物回读 `962.7150059999999`→`962.715006`）⇒ 对照物与产物回读**必须 `float_precision="round_trip"`**；③ **`D2 = (home∪work) ∩ service`**（非全集）；④ G-0 用裸面名、G-1 用带后缀名 ⇒ `FACE_G0_KEY` 双向映射；⑤ **空串经 CSV 往返变 NaN** ⇒ 门 12「非空」须显式 `isna()`；⑥ **pandas 3.0 `df.loc[len(df)]={...}` 静默丢新列**；⑦ 门 09/12 须覆盖全部 share 行载体（含 `denominator_audit`）。**★§8 期望门偏差留痕**：N1 期望 12/09→实测 **10**（`share(ALL_LOADED,time)=105.98%`）、N4 期望 12/10→实测 **09**、N3 期望 15/17→实测 **15**（门 17 判据为 face_role/字段名，**不能**检测值替换）；其余 8 例命中或其超集。prereg `reports/caliber_harmonization_7_9g2/PREREG_7_9G2.md` |

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
42. **200k route 的装载统计必须「流式、只计数」**：对 `plans.xml.gz` 全量对象化解析（建 XML 树 / 建 20 万 route 对象 / 建完整 DataFrame）会**连续超时**。正解 = **逐行二进制正则**（`rb'<route\b[^>]*\btype="links"[^>]*>(.*?)</route>'`，`gzip.open(...,'rb')` 逐行）+ 只累计 `Counter`（不保留 route 结构）→ 分钟级跑完（7.3.2C）。**events 不需要**：`plans` 的 `route type="links"` 已含完整 link 序列。
43. **edge 级流量"集中度"会被微段碎片化稀释，不能当结论**：OSM/MATSim 把快速路切成 4,780 条 20–100 m 微段，即便最繁忙走廊（CTE）单边也只承载 ~10%；本项目 motorway **Top100 边合计仅 9.57%**。凡涉及"某走廊流量高/低"的判断，应**聚合到走廊/断面级**再比较，勿用单条 micro-edge 的计数。**CATA 与 SLIP_ROAD 装载指数几乎相同（≈0.85）却 sim/obs 相反（0.69 vs 2.05）** ⇒ edge 级装载不是判别变量，指向观测-表达口径（C 类）。
44. **`TrafficFlow_Data.json` 是长表，不是"一断面一行"**：75,899 行 = **1,311 LinkID × 日期 × 小时（仅 7/8）**，每断面 14–120 条；断面属性（RoadName / RoadCat / 坐标）在断面内**唯一**（坐标偶有 51 个断面跨日期微变，取首行即可）。直接按 LinkID 与"断面级"表 merge 会 `MergeError: not a many-to-one merge`（7.3.3 运行前抓到）。正解 = 加载后 `drop_duplicates("LinkID")` 去重到断面级。断面级 `RoadCat` 分布：CATB 634 / CATA 339 / SLIP_ROAD 251 / CATC 46 / **#N/A 33** / CATD 7 / CATE 1；**33 个 `#N/A` 恰为 crosswalk 未覆盖断面**。
45. **6.3.2 tight crosswalk 自带 `highway`/`RoadCat` 列，再合并会 `_x/_y` 冲突**：`reports/matsim_assignment_6_3_2/lta_section_matsim_crosswalk.csv` 列 = `LinkID, osm_edge_index, matsim_link_id, distance_m, name_match, highway, RoadCat`。若把它当"纯映射"再 join network（含 `highway`）/ traffic（含 `RoadCat`）→ pandas 生成 `highway_x/highway_y`、`RoadCat_x/RoadCat_y`，后续 `df["highway"]` 直接 `KeyError`。正解 = 合并前 **drop 掉 crosswalk 内这两列**，由 network（`highway`）/ traffic（`RoadCat`）权威提供。
46. **"观测断面→MATSim 边"默认不含方向约束（对向车道会被一并匹配）**：6.3.2 tight crosswalk（沿线采样 + 路名一致）**未做方向过滤**——双 carriageway 的两侧 micro-link 同名同走廊，会被同时选入。诊断既不能只看"与 LTA Start→End 夹角"（LTA 方向约定未必是行驶方向），也**不能只看精确互反配对**（对向车道常走**不同节点**，互反率仅 15.5%，会低估）。稳健口径 = **断面内自身模态方向 vs 各边夹角**：本项目 **32.4% 匹配边反向、72.1% 断面含反向边、仅 8.5% 断面可串成单一有向链**（CATA 更低 4.4%）。凡"点流量 vs 微段集合"对照，**须先分离方向**。
47. **交付脚本的默认路径/列名可能与本机实际不符，务必运行前核对（勿让脚本静默 fallback）**：7.3.4 里三处阻塞——① `NODES_DEFAULT` 指 `network_nodes.csv`（**不存在**，实际 `network_nodes_source_copy.csv`）且坐标列为 `x_svy21_m/y_svy21_m/lon/lat` 而非 `x/y`；② `load_traffic` 产出列名 `LinkID`，却在 `build_candidates` 里按 `lta_linkid` 合并 → `KeyError`；③ linkstats 的 `LINK` = `e{from}_{to}`，与 6.1 建网 id 约定一致（可 join）。**正解**：坐标列**自适应并优先 lon/lat**（与 LTA 断面 heading 同口径），合并前统一改名，运行前先 `head` 核对每张输入表的表头。
48. **收敛判别必须做"选择偏差检查"**：语义/方向过滤会**丢弃断面**——只报"过滤后 ratio 好看"是误导。7.3.4 中 strict 过滤保留 CATA 326/339（obs 权重 97.4%）但 SLIP 仅 129/251（**obs 权重 49.7%**），且 **117/251 SLIP 断面在基座候选中无 `motorway_link`**（dominant 主线 104 个）→ SLIP 纯度存在**由基座 crosswalk 决定的上界**，过滤无法凭空生成匝道几何。报告须同时给出**保留断面数 + obs 权重 + 不可映射断面数**。
49. **同名字段 join 前必须显式统一 dtype（int64 vs str）**：MATSim `network_links_source_copy.csv` 的 `from_node/to_node` 读进来是 **int64**，而节点表 `node_id` 被 `astype(str)` → 直接 join 触发 `ValueError: You are trying to merge on int64 and str columns`。7.3.5 修法：`net[["from_node","to_node"]].astype(str).str.strip()` 后再 join。另：**交付脚本的 `usecols` 常写死理想列名**（如 `x/y`），必须改为**候选列自适应**（本例实为 `x_svy21_m/y_svy21_m/lon/lat`），并**优先 lon/lat** 以与 LTA heading 同口径。
50. **分清"全网几何"与"检测器断面"两个口径，勿混用分母**：`TrafficSpeedBands_Links.shp` 是 LTA **全网精细切片**（**143,787** 条 LineString；`RoadCat` 为**数字**：1=Expressway / 6=Slip / 8=Short Tunnel；slip=**5,207**），而校准相关的是 **1,311 个检测器断面**（TrafficFlow，`RoadCat` 为**文本** CATA/CATB/…/SLIP_ROAD）中的 **251** 个 SLIP。二者 **LinkID 同一空间**（251 个检测器 slip **100%** 落在 5,207 全网 slip 内），但**分母含义完全不同**：用 5,207 算覆盖率会得到 48% 的假象、并把 4,956 条"非检测器"slip 误算成"新补回"。**正解**：定义 **CORE = slip ∩ 6.3.2 crosswalk** 作主口径，FULL 仅作背景。另注意 **`rebuilt_crosswalk.csv` 是约简边集**（6,008 行 vs 6.3.2 的 13,163 行），在其上统计"无 motorway_link"会得到 **117**，而冻结基座上权威值为 **113** —— 凡涉及"缺口/覆盖率"一律以冻结基座为准。
51. **多表 join 前必须清理"同名但不同来源"的列，否则列被静默改名 + 报错/丢组**：7.3.6A 中 `rebuilt_crosswalk`（含 `RoadName`/`RoadCat`）与观测表 `obs`（也含 `RoadName`/`RoadCat`）合并 → 生成 `RoadName_x/_y`、`RoadCat_x/_y` → 后续按原名取列直接 `KeyError`；`slip_candidates_all`（自带 `RoadName`）与 `obs` 合并同理。**修法**：合并前**显式 drop 掉"非权威来源"的同名列**（本例：观测 RoadName 权威、候选表的同名一律丢弃），或统一改后缀后再取用。**交付脚本务必先核对输入 CSV 的真实列名**（`head -1` 一行即可），不要假设。
52. **`pandas.groupby` 默认 `dropna=True` 会静默丢弃"键含 NaN 的整组"** —— 这是最隐蔽的"数据凭空消失"来源。7.3.6A 中 SLIP 行因上述列冲突把 `RoadName` 变成 NaN，`groupby(["lta_linkid","RoadName","RoadCat"])` 于是把它们**整组丢掉**，结果"2,147 行 SLIP 在 final 里存在、却在 section summary 里全部显示为 UNMATCHED"。**排查套路**：① 对 `final` 直接 `value_counts()` 看行是否真在；② 检查分组键是否有 NaN（`df[keys].isna().any()`）；③ 需要保留 NaN 键时显式 `groupby(..., dropna=False)`。**凡"上游有、下游没"都先怀疑 dropna/列名漂移。**
53. **crosswalk 的"诊断列"（`highway`/`RoadCat`/`RoadName`）不要在回测脚本里保留**：7.3.6B 直接把三张 crosswalk（`LinkID`/`lta_linkid`/`matsim_link_id`）与观测表合并做回测时，若 `normalize_crosswalk` 保留了 crosswalk 自带的 `RoadCat`，与观测表（也含 `RoadCat`）merge 生成 `RoadCat_x/_y` → `groupby(["lta_linkid","RoadName","RoadCat"])` 直接 **KeyError 崩溃**（此为 7.3.3/7.3.6A 的坑 45/51 在"回测"环节的复现）。**正解**：回测只需 `lta_linkid + matsim_link_id`（+ 可选诊断列）；**断面 `RoadCat`/`RoadName` 一律由观测表（TrafficFlow）权威提供**，crosswalk 侧同名一律丢弃。凡"多表 join 回测"先把**只在观测表出现的属性列**列一遍，其余同名列 drop。
54. **复现冻结靶场必须逐条复刻其"观测statistic"，差一步数值就对不上**：7.1 冻结靶场的观测口径是 **`weekday daily volume` → 先按 `(LinkID, Date, Hour)` 求日内均值 → 再按 `(LinkID, Hour)` 取**跨日中位数**（`Date.dt.weekday < 5` 过滤 + 两段 groupby）**。若回测脚本图省事直接 `groupby(LinkID, Hour).median()`（不滤工作日、不做日内均值），得到的 CATA/SLIP 旧值不会等于 **0.7388/2.0333**，整条 `0.3633→…` 链条随即失真。**凡要"衔接/复现"某个已冻结结果，先把其构造脚本（本例 `build_calibration_target_7_1.py::obs_load`）逐行读一遍，再对齐日历过滤 + 聚合层级 + 中位/均值选择。**
55. **同一份"语义重构表"有 full / strict 两个子集，回测选哪一个会直接改结论**：`rebuilt_crosswalk.csv`（7.3.4）是**全量 1,278 断面**（含 fallback 匹配），其 **strict 子集**（`selection_tier=='strict'`）才对应"同向+同类+同名"的干净匹配（CATA 326 / SLIP 129）。用户引用的 `0.9135` 来自 **strict**；若误喂 full 会得到 **0.4100**（SLIP 1.8796）——两者结论相反。**正解**：回测"语义对齐"效果用 strict；同时**把 full 作为参照方法一并输出**，用于诚实披露"覆盖广 ≠ 对齐好"。**凡 B/A 两口径并存的数据集，报告中须同时给出两者并注明取用口径。**
56. **设计文档里的"冻结输入"要逐一与项目实测值对账，别照抄外部草案**：7.4.1 外部草案把 `randomSeed` 写成 `20260912`（= 设计日期，**误当种子**），而项目实测冻结值是 **4711**（`make_config_6_3.py` 硬编码；6.3.3B / `config_capf_*` / `config_cf_it20` 三份 config 全为 4711）。**改种子会让所有 linkstats 失去与 6.3.3B 及 7.x 评价链的可比性**。**正解**：落盘设计时把 `randomSeed` 校正为实测值，并在 JSON `random_seed_note` + 设计 MD 中**显式披露被覆盖的草案值**（不静默改）。**凡接手外部草案，先把它列的每个"冻结输入"到项目里 grep 一遍真值。**
57. **MATSim `linkstats.txt.gz` 的 `HRSx-y{min,avg,max}` 是"小时流量"，`TRAVELTIME{x-y}{min,avg,max}` 才是"行程时间"——不要混淆**：文件 154 列分两块；`HRS8-9avg` 取值为 **1/2/5/6/… 整数（车辆数）**，`TRAVELTIME8-9avg` ≈ `LENGTH/FREESPEED`（秒）。7.1 冻结口径 `sim = median(匹配边 HRSx-yavg) × 2.29897` 因此是**仿真流量 × 抽样扩样**（200k → 459,794），**不是"速度 ÷ 流量"**。**改 capacity / 迭代的联合校准时，被比较的量始终是 `HRSx-yavg`（volume），不要误取 `TRAVELTIME` 列。**（另一坑：`flowCapacityFactor` 同时存在于 `hermes` 与 `qsim` 两个 module，但只有 `qsim` 生效——7.2.2 实测只 patch `qsim` 即可产生容量差异，`hermes` 为惰性模块。）
58. **从 CSV 读入的"数值列"默认是字符串，直接喂 `f"{v:.4f}"` 会崩**：7.4.2 评价器把实验矩阵 `capacity_factor`（CSV 里是 `"0.50"` 字符串）原样放进 `struct_scan`，报告 f-string 调 `f4()` 时触发 `ValueError: Unknown format code 'f' for object of type 'str'`（`clean()` 只处理了 float/NaN，没处理 str）。**正解**：凡参与格式化/比较的 CSV 数值列，读入后显式 `float()`/`pd.to_numeric()`；或让 `clean()` 对 `str` 也尝试转 float。**同类风险**：pandas `read_csv` 不带 `dtype` 时，`"1.00"` 这种会被推断为 str（含非数字行时整列 str），别假设它一定是数值。

---

59. **★改文件：Edit 偶发「报告成功但未落盘」**：关键改动一律用 **Write 整文件重写**，或用 **Python 补丁 + `assert` 校验锚点唯一性**（`t.count(anchor)==1`）；改完必须**再读回校验**。同理 `bash -c` **不能**传含反引号/反斜杠的 Windows 路径或代码（反引号会被 shell 当命令替换）⇒ 一律落地为脚本文件再跑。**Write/注入时 `\n` 可能被当字面两字符** ⇒ Python 源码写双反斜杠或改 raw 字符串；跨文件注入后必须 grep 校验转义层级。
60. **★日志/CSV 会被外部进程短暂占用**：写出函数带**重试 + 备用文件名降级**；补丁脚本的「已存在」守卫用**代码特征串**而非文件名。
61. **★★跨参数档比较前必先做同档内逐迭代收敛审计**（奇偶相位分解 + 相位均衡周期均值，奇/偶各判一次看符号）。审计脚本**先读 config 再读结果** ⇒ 落 `*_config_provenance.csv` 并写进 verdict。**「是否仍振荡」必须看逐迭代轨迹单调性**：新配置 `A_full_00_19`=8.79% 看似很大，实为 **burn-in 瞬态**；旧配置含**持续奇偶交替** ⇒ 只用收敛窗 `A_10:19` + `sign_consistency`，**`A_full` 不可作判据**。
62. **★零仿真重算必须 `import` 冻结模块，不得复制公式**（7.6F-0 / 7.6C / 7.6C-1 / 7.6C-2 均 import `compare_final_crosswalk_7_3_6b`）⇒ 能**逐位重现**既有数值（D01 `it.19`=0.707041 / AM=0.682991），这是「口径未漂移」的**唯一硬证据**。
63. **★空间归属要用 link MIDPOINT → 最近 zone 质心（`cKDTree`）**，不要用 `from_node`（CBD 邻近 `from_node` 会误判给 CENTRAL）。
64. **★「覆盖率缺口」必须与「真实缺口」分开**：先统计 `sim=0 但 obs>0` 断面，再报 `ratio_pos_only` 作稳健性；否则把**未被覆盖的观测**误算成**模型低估**。
65. **★★「信噪比 < 1」是「曲线不可用于推断」的正式判据**（`极差/自身噪声 < 1` ⇒ `UNINFORMATIVE`）。
66. **★★「零流断面」先查有向拓扑可达性，再谈需求**：用**全网有流链**建 `arrive-node`/`depart-node` 集合，检验匹配边两端是否落入（孤儿边 ≈0.02–0.06 vs 正常 ≈0.99），再找**最近有流平行链**（分「任意」与「同路名」）。**平行孪生（OSM 重复几何）= 同路名、相距 <60 m、一条有流一条全零**。
67. **★断面 `median` 口径脆弱**：`sim = median(匹配边 HRS8-9avg)` ⇒ **≥50% 匹配边落在未使用方向（双向混合匹配）或无流窗口时中位塌 0**，与需求无关 ⇒ 任何断面级比值结论前**必须做匹配边级方向/窗口构成审计**。
68. **★helper 内部 `dropna` 会静默改变样本集**：7.6C-1 `link_attribution_bounds` 内 `dropna(subset=[mid_x,mid_y])` 把 **576** 断面静默降到 **574**，与其自身 anchor 行（576）差 **4.06e-4**（0.8585675 vs 0.8589732）。⇒ **任何跨脚本对齐前必须显式声明并核对断面集基数**（7.6C-2 主口径固定 576、另复现 574，交叉校验 7/7 全中）。
69. **★三口径拆分必须同函数形式**：主口径（`FROZEN`，全断面池化）与敏感口径（`POSITIVE_ONLY`，`sim>0` 池化）**必须同用池化比**，否则两者之差**不只是**「断面排除效应」。**靶场不确定性要换算成参数单位**：`f* = Q^(-1/ε)`，其跨度 `Delta_f_target` = demand 因子的识别区间宽度 ⇒ 再用 `SNR = ε·step/Delta_f_target` 判「靶场是否有资格做绝对标定」。
70. **★配置变更必须落「逐参数 provenance + diff 白名单 + MUST_MATCH_BASELINE」三重验证**；**数值比较要类型感知**（`"1"` vs `"1.0"` 用 `same_value()`）。
71. **★运行成本用实测值**：100k 实测 **33.20 min**（事前外推 4.5–5 h，**高估 8 倍**）；200k 实测 **84.41 min**。**★Windows 文件锁**：同位置连续两次失败**不能**直接判配置缺陷 ⇒ 必须「**换 run 重跑**」对照；评价前先确认 run `exit=0`。
72. **★低样本/降规模实验前先算采样下界**；某档不可行时**先找「同 N 对照」**而非立刻降 N。
73. **★文档交付**：版本化用 V2/V4/V6 后缀；保留原完整内容并按原风格撰写；**要求同步 `scripts/od/readme.md` 与技能 `singapore-od-matsim-pipeline/SKILL.md`**。
74. **★★零仿真拼接多源产物前先统一键的 dtype**：`section_geography.csv` 的 `lta_linkid` 落盘为 **int64**，而 `backtest_one` 断面统计为 **str** ⇒ `merge` 抛 `ValueError: merge on str and int64`；更隐蔽的是 **`directional_repair` 返回的键是 `int`**（`out[int(lid)]`），若用 str 值 `.map()` 会**静默全 NaN**（不报错、但结果全错）⇒ 拼接两侧一律 `astype(str).str.strip()`、映射前 `{str(k): v ...}`。**「没报错」≠「口径对」**。

75. **★★`qsim.timeStepSize` 的量化会污染任何以 `TRAVELTIME` 为基础的评价**：1 s 步长下链路行程时间被**向上取整**（`TT_recorded = ceil(FF)`），而本网络链路 FF **中位 1.37 s / 均值 2.93 s**（>500 m 仅 29 条）⇒ **即使零延误**也会得到 `TT/FF = ceil(FF)/FF ≫ 1`。**三重自检**：① **跨时段对照**（几乎空网时段倍率 ≈ `ceil(FF)/FF` 基准 ⇒ 该口径不含拥堵信号 —— 实测 12–13 时仍 1.552 vs 基准 1.596）；② 逐链路 `|TT/FF − ceil(FF)/FF|` 分布（实测 **82.56% 载流链路零延误**）；③ **单车级**核对 `sum_tt` 是否恰为 `n × ceil(FF)`（实测 23 辆车 / 0.955 s ⇒ 23.0 s）。**评价一律先扣基准**：`真实超额 = TT/FF − ceil(FF)/FF`。⚠️ **断面*流量*（Sim/Obs）不受影响** ⇒ 7.6/7.7 标定结论不变。
76. **★★`v/c ≤ 1` 是结构性质，不是「容量富余」**：MATSim 链路流出被容量截断，需求超额表现为**上游排队** ⇒ `v/c = HRS8-9avg / CAPACITY` **恒 ≤ 1**、`>1` 恒 **0** 条；`v/c = 1.000000` 的正确读法是 **「已饱和 + 正在排队」**。**不要把 `max v/c = 1.0` 读成「容量富余 / 不会堵」**（7.8-VIA-DIAG 曾如此误读，7.7E 更正）。
77. **★「全网聚合量」不能用来定位拥堵** —— 要看延迟的**空间分布**而不是总量：`service` 接入短段占链路数 **65%**、却承载 **94.4%** 的真实延误，而 `motorway` 仅 **2.2%** ⇒ 任何「网络级」拥堵标量都会被碎段主导。**必做步**：按 `road_type` / 走廊 / 长度桶**分解**后再下结论。
78. **★图内文本要过「字体字形」检查**：matplotlib + `msyh.ttc` 渲染缺字形字符（如 `⛔` U+26D4、`⇒` U+21D2）**只发 `UserWarning: Glyph ... missing from font`、不报错**，图上静默缺字 ⇒ 生成图后**必须 grep 日志的 `missing from font`**，并把图内文本限制在 CJK 常用字符 + ASCII（md 正文不受限）。

79. **★★判断某个 MATSim 参数是否生效，必须看 `mobsim`，不能只看「这个 key 存在」**：同一配置里 `trafficDynamics` 可以出现**两次**（`dsim` = `kinematicWaves`、`qsim` = `queue`，值还不同），`flowCapacityFactor` 也同时存在于 `hermes` 与 `qsim`。`controller.mobsim = qsim` ⇒ **只有 `qsim` 的那份生效**，其余是 mobsim 专属/惰性配置（`hermes` 在 `mobsim=hermes` 时才生效）。**只看 key 名会得出完全相反的结论**（"当前动力学已经是 kinematicWaves"）。落地做法：任何容量/动力学/时间步审计，**先把 module 归属与 `mobsim` 一起打印出来**，再谈值。
80. **★★「采样比例」的分母必须由「流量扩样因子」决定，不能用需求锚**：`s = N_sim/ΣEF` 与正确的 `s = 1/SCALE` 可以差整整一个 `f_work`（实测 0.513369 vs 0.434977，**差 18%**）。判据是**量纲**：`Sim/Obs = 1` 断言 `F_real = SCALE × F_sim`，要保持 `v/c` 一致就必须 `C_sim = C_real/SCALE` ⇒ `f_cap = 1/SCALE`，**与 `ΣEF` 如何定义无关**（`ΣEF` 只是需求锚，且工作点可能故意相对它超采样以弥合口径差）。**任何「比值型」因子落地前，先写一行量纲等式。**
81. **★「冻结流量投影」不能替代仿真，且必须显式标注为上界**：把 `CAPACITY × (1/SCALE)` 后重算 `v/c` 只给出**一阶上界**（不含排队导致的流量回落与重分配），可用作**预注册预测**与判据前置，但**不得**据此下结论、**更不得**写进校准结果。其价值在于提前暴露方向：本例即显示「即使样本一致，饱和里程也只占全网 1.18%」，从而把下一刀指向机制（`trafficDynamics`）而非继续压容量。

> 以上 59–74 于 2026-09-17 按精简需要自 `MEMORY.md §6` 原样转存（`MEMORY §6` 保留指针）；**75–78 于 2026-09-19 追加（Step 7.7E）**；**79–81 于 2026-09-20 追加（Step 7.9A-0）**；**82–84 于 2026-09-20 追加（Step 7.9B-0）**；**85–89 于 2026-09-20 追加（Step 7.9C-0）**。`MEMORY.md` 有**注入长度上限**，超限会被**静默截断**，故把长清单落在本文件。

82. **★★「某机制会不会改善结果」应先在零仿真下量化它的「作用集合」与「作用位置」，再决定是否跑仿真**：7.9B-0 用 `r_fdiag = FD 天花板 / 路网容量 < 1` 把「换成 `kinematicWaves`」从定性猜想变成 **21,670 条 link / 869.6 km（5.75%）** 的定量集合，再用节点度检验**位置**，从而在**不跑 2 小时仿真**的前提下先否决了「集中在 merge」的假设。**顺序 = 先量化集合 → 再量化位置 → 最后才花钱跑。**
83. **★★「会变堵」≠「堵得对」——均匀削流是伪改善**：7.9B-0 显示 KW 的 FD 入口上限是**对高容量/高速度路段的整体性 ~10–11% 削流**（expressway 中位 r = 0.90），而非复现真实瓶颈 ⇒ 它**可能让地图变红却不提升结构性保真度**。凡遇「某参数能让结果看起来更合理」，必追问**它作用在哪里**；位置不对的增强 = 与「为让动画变堵而放大 demand」同构的红线违规。
84. **★比值/约束类判据必须查「缩放是否对称」**：`flowCapFactor` 缩放路网容量但**不**缩放 `maxFlowFromFdiag`（源码注释 L407–412 明确「leave unscaled」）⇒ 两个约束的**相对**强弱随 `f_cap` 漂移，导致 A、B 两刀**不可加**（`f_cap=0.435` 时 FD 入口约束在 **0** 条 link 生效）。**改多参数前先列「各自被谁缩放」。**
85. **★★结构单元的规模定义必须先量「作用集合」再定，且要防「链式合并出巨块」**：7.9C-0 先做三轮零成本探针——种子节点 **50,617**（deg≥3 且含结构跃变）、短链阈值 **p90 = 52 m**、K-hop 邻域中位 4/10/18 link；再用 union-find 实测发现 **K=2 邻域合并 max 达 3,351 link、短链连通分量 max 38,241** ⇒ 若直接合并会退化成「一个巨块」。最终定稿 = **同层短链连通分量 + ≥1 种子 + 超 200 link 递归拆分** ⇒ 22,722 单元、中位 10、max 200。**先看规模，再选容器**。
86. **★★聚合方式决定偏差方向，必须先报偏差再做分层控制**：同一套节点分数，用**均值**聚合 ⇒ 大单元被稀释（`ρ(prior, log 规模) = −0.686`）；用**极值**聚合 ⇒ 大单元被偏爱。7.9C-0 取极值（严重度语义）后偏差降到 `+0.025`，**但仍另做「单元规模十等分分层控制」**（C2 层内重算 ρ、C3 层内重算 p80 阈值）——与 7.9B-0 B4 的「同类别对照」同一纪律。**报了偏差 ≠ 控制了偏差**。
87. **★★位置一致性指标（HitRate/lift 之类）必须先做「共同因子证伪」**：7.9C-0 的 v1.0 基线 `lift = 1.852×` 看起来不错，但两个证伪刀口立刻刺穿它：① **值域**——v1.0 饱和 link 仅 **82** 个（全网 0.0118%），单元 `v/c` 的 p80 阈值只有 **0.022** ⇒ 「模型高拥堵单元」近似**任意排名**；② **共同因子**——`ρ(prior, 单车道容量) = 0.248`、`ρ(v/c, 单车道容量) = 0.449`，且快速路单元 **94.9%** 天然入选候选 ⇒ `lift` 里混着**容量因子**。⇒ 凡「某指标变好了」，先问**它是不是同一个物理量在两边同时出现**。
88. **★★零仿真残差投影的判据是「置换零分布」，不是相关系数的绝对值**：C2 的 `ρ = 0.0355` 单看无意义；建**同区域内打乱断面**的 400 次置换零分布（mean −0.0079 / sd 0.0480）后得 **p = 0.8125** ⇒ 可**明确断言无关联**。同时必须随附**映射质量**：截面覆盖 **99.7%**、三种映射路径（link 直连/端点/空间最近邻）与兜底距离 p90 **173 m**——否则「无关联」可能只是**映射丢失**造成的假阴性。
89. **★★numpy 字符串标量当 dict 键会慢 ~100×，脚本会从 35 s 变成跑不完**：7.9C-0 初版用 `{z['ids'][i]: i for i in range(n)}`（693k 个 `np.str_` 键）+ `inc[a].append(i)`（2.8M 次）⇒ 实测 **7 分 25 秒仍未跑完**；改成 `[str(x) for x in arr]` 一次性转 **Python str** 后**全流程 33–43 s**。**凡「数组元素要当键/要做集合成员」，先转原生类型**；先测「作用集合」的规模，再决定容器与类型。
90. **★★单变量实验的「diff 显式化」门必须把模型层与输出层分开计**：7.9B-1 若只报「共 4 处 diff」会掩盖「模型只改了 1 处」。做法 = 展开 `<parameterset>` 后按 **`module.param`** 归一，断言 **模型层恰好 1 项且 == 目标参数**、**输出层恰好 3 项且 ∈ 白名单**、**`VIOLATION = 0`**。⚠️ 且必须**同名校验 module**：`dsim.trafficDynamics` 与 `qsim.trafficDynamics` **同名**，`dsim` 早已是 `kinematicWaves`（**惰性诱饵**）⇒ **只按 key 名 grep 会得出「已经改过了」的反向结论**。输出层 3 项（`outputDirectory`/`runId`/`writeEventsInterval`）**不进动力学**，必须单列声明。
91. **★★「作用集合」与「作用强度」要分开量：命中集合 = 0 ≠ 机制未生效**：7.9B-1 的「08–09 小时均值恰落在 FD 入口天花板上」链路数 **KW = 0 vs v1.0 = 32**，但运行期明明有 `maxInflowUsedInQsim` 告警。原因是 **`q_fdiag` 是速率上限（veh/h 瞬时能力），小时均值天然低于它** ⇒ 该指标是**巧合级**。同理 **`v/c≥1` 从 82 降到 10 是「削流后贴容量链路跌破 1.0」，不是拥堵减轻**。⇒ 判「约束是否生效」用**运行期告警 / 逐时步流量是否被削**；**比值型指标在缩放改变后必须换另一族指标（延误型）交叉验证**。
92. **★★「变堵」与「堵得对」必须两套独立证据链，⛔ 禁止用拥堵量代替位置质量**：7.9B-1 总延误 **+161%**（机制确实变了），但「新增延误落在候选结构单元内的比例」**32.5% → 29.5%**、富集 **1.718× → 1.555×**、最长连通分量仅 **0.857 → 0.954 km**、分量数 **3,603 → 8,223（更碎）** ⇒ **更堵 ≠ 更对**。**量化口径**：机制侧 = Δ延误 / Δ超额里程 / Δ分量 / Δ稳定性（**仿真结果即可判**）；位置侧 = **C3 lift、C2 ρ + 置换 p、落候选单元比例（含 base 与富集）**（**必须空间证据**）。**两者都过才算成功**。
93. **★★换拥堵定义时要「对称施加 + 明确标注非预登记」**：KW 经 FD 入口上限压低 `v/c` ⇒ 用 `v/c` 判「堵在哪」会系统性低估。故另按**真实超额**（`TT/FF − ceil(FF)/FF`）长度加权复算同一 C3 判据，**对称跑 V1 与 KW**，并**标注为非预登记**（结果同向：own-p80 `1.679× → 1.601×`、同 v1.0 阈值 `1.527×`）。⇒ **允许做「口径稳健性检查」，⛔ 但不允许挑一个让结论变好看的口径充当主判据**；**预登记阈值仍是唯一主判据**。
94. **★★复用上游「冻结单元定义」的正确姿势 = 溯源执行源码切片 + 位级自校，而不是重抄算法**：7.9B-1 需要 7.9C-0 的 link→unit 映射；重抄 ~300 行单元算法**必漂移**。做法 = `exec` 冻结脚本的**源码切片**（`head 1–102` + L1/C1 块 L115–338，去缩进、去图/输出副作用），再对 `c0_junction_clusters.csv` 做**位级自校**（**22,722 单元**的 `unit_id`/`n_links`/`km`/`prior` 全同，并复现 82 link / 1.151 km 基线）⇒ **既零漂移又免维护**。⇒ **凡「下游要复用上游的冻结中间结构」，优先复用其代码而非其产物，并强制自校**。

95. **★★「结构完整 / 损坏」必须按「瓶颈侧 vs 吸收侧」分列判——同一张图里两类道路的结论可以完全相反**：7.9C-1 检验「网络表达是否阻断回溢」，K1/K4 显示**主线侧完整**（`up_main_m` 中位 **1,957 m**、`≥300 m` 覆盖 **91.5%** 里程；motorway **17.4 links/km**、**0** 条 `>40 links/km`）⇒ **用户预设立场被证伪**；而 K3/K4 又显示**吸收侧（service/connector）99.95% 为回压死端、且被切到 8.9–9.3 m / 50.8–85.0 links/km** ⇒ 结论方向**只在吸收侧成立**。⇒ **凡「网络表达 / 拓扑」类判据，必按「瓶颈侧 vs 吸收侧」分列，⛔ 不可用一个全局结论概括两者**。
96. **★★「延误落在多长的结构通道上」是检验「拥堵被结构困住」的直接物理量，优于再堆一个相关系数**：C-1 以 `delay_h` 为权计算 `up_chain_m` ⇒ v1.0 加权通道仅 **334 m**（service 内 **107 m** vs motorway 内 **7,921 m**）、**97.34% 的延误落在「无法回压主线」的 link 上**，一句话即证「就地生成、就地吸收」。⇒ **位置/机制类问题优先构造「延误 × 结构」的物理量**（可解释、可复算）。
97. **★★冻结文件里的「简称掩码」是最隐蔽的静默错误源——必须用「正名 + 计数断言」兜底**：7.9B-1 用 `"CTE" in name.upper()` 识别 CTE，但 v1.0 网络 `name` 中**根本没有**字面 "CTE"（**0 条 link**），掩码**静默退化**为 `Changi ∪ Tampines`（3,647 link），使 CTE 真实延误（**104.57 h / 2.19%**）被漏掉、只报了 **1.76 h**，且方向被读反（KW 实为**削弱** CTE）。⇒ **凡按名称/类别取子集，必须打印「命中 link 数」并断言非零**；`in`/`grep` 类匹配**靠「什么都不匹配」制造假阴性而不报错**。
98. **★★「份额 / 占比」类结论必须先做 base-rate 归一（`份额 ÷ 里程份额`），否则结论会随分析域反转**：7.9C-1 报「`service` 吃掉 **94.36%** 延误」，7.9D-0 一算 `ratio = delay_share / km_share` 只有 **1.610**（`service` 本就占 58.61% km、64.95% link）⇒ **不构成富集**；而**限定主线邻域后 ratio 反转为 0.171（欠表达 8.5×）**，邻域延误 **96.35%** 落在 `motorway+ramp`。⇒ 凡「某类吃了 X%」的句式，**必须同时报 km 份额与 ratio，并给出「全域 vs 限定域」两套数**。
99. **★★「拓扑跳数」在碎片化路网里会系统性夸大距离，接口类判据必须同时给物理量**：`d_up = 72 hops` 听起来像「极远」，但 link 中位只有 **~11 m**，换成物理距离只有 **1,952 m**；反之「仅 3.15% 延误在主线 300 m 内」才是可直接采信的表述。⇒ 凡用 hop/hop-count 下结论，**必须附 `dist_*_m` 并报分布**（本步做法：多源 Dijkstra 以 `len` 为权）。
100. **★★「单跳不可逆」是重言式，不是证据——回溢/耦合类判据必须升维到多跳**：C-1 的 K3「99.95% 回压无能」在「全网只有 **0.049%** 的 `service` link 有主线 feeder」的前提下**必然接近 100%**，不含信息量；7.9D-0 改成多跳 `d_up` 分布后才有判别力（`share(d_up≤3) = 2.78%`，且对阈值 D=1/3/5 稳定）。⇒ **任何「A 无法影响 B」的判据，先算 A、B 的基础接触率**，再决定用单跳还是多跳。
101. **★★「参数是不是涌现结果」要用「确定性与细分辨率」两刀捅穿**：单看 `cap = 400 veh/h` 无法判断它是建模设定还是涌现。7.9D-0 用 `ndistinct(cap/lanes)` 检验——**类别级**因 `other` 合并 5 种 highway 而报 `False`（如实上报），**细分辨率**（`highway × lanes`）显示 **13/13 类型组内 `min = max`** ⇒ 容量是**纯查表赋值**。⇒ 归因「薄储存 / 低容量」时，**必须做确定性检验，并按最细可分辨粒度报**；预注册粒度不足时应并列补充、而非改预注册。
102. **★★「接口距离 / 耦合距离」必须用物理口径，跳数只是碎片化伪影**（**R-DIST-1**）：7.9D-1 里 ramp 到主线「92.73% 单跳不接触」，看似全线断裂，但**多跳物理距离中位仅 478 m、100% 可达**；link 中位仅 11–16.6 m 时，跳数被碎片化放大一个数量级。⇒ 今后 `coupling distance` / `spillback reach` / `interface proximity` **一律以 m/km 为主**，hop 仅作辅助并附换算。
103. **★★「接口 / 相邻」类判据必须多跳（R-MULTI-1），单跳在碎片化路网上是近重言式**：7.9D-1 的单跳分类 `neither` 占 **92.73%**（`motorway_link` 中间片段两侧都不是主线），与 7.9C-1 的 K3、7.9D-0 的 D3 同型 ⇒ 单跳判据**靠“什么都不匹配”制造假阳性**。
104. **★★「暴露面」≠「时间面」——占比必须用与目标一致的分母**：`service` 占 **90.26%** 的出行端点（暴露面），却只占 **5.15%** 的自由流时间（时间面）；真正吃掉 off-mainline 时间的是**干道（37.87%）**。⇒ 报告「某类很重要」时**必须声明是暴露面、里程面还是时间面**，三者常指向不同对象。
105. **★★「恒等于 X」类口径断言必须用「唯一值」而不是「p10=p90」**：7.9D-0 写「`service` 自由流被硬编码为 20 km/h（p10=p90）」，7.9D-2 细查发现**有 10 个不同值（5–70 km/h）**、20 km/h 仅占 **96.80%** ⇒ `SERVICE_SPEED_FIXED=False`；真正严格唯一的只有**容量 400**。⇒ 「恒定」类结论一律用 `ndistinct` 断言，并**同时给出例外比例**。

106. **★★「时间归属」与「延误归属」可以是不同层——必须分别报，且各自声明基数**（7.9E-0）：干道承载 off-mainline **车时 63.71%**（时间主场），但延误份额仅 **29.78%**、`service` 仍以 **57.10%** 居首 ⇒ 「谁占时间」≠「谁占延误」。⇒ 归因结论**必须写清是时间面还是延误面**，并给对应基数。
107. **★★「某项是否富集」会随基数翻转——`delay_ratio` 必须与所用基数绑定声明**（7.9E-0）：`arterial_core` 的 `delay_ratio` 在**结构基数**下 **4.41（富集）**、在**车时基数**下 **0.47（欠表达）**；`service` 恰相反（0.72 vs 6.43）。⇒ 单报一个 ratio 必然误导，须**双基数并报**（承接 §4-98 的 base-rate 纪律）。
108. **★★「靶场不可分辨」本身就是结论——目标断面表的道路构成必须先行体检**（7.9E-0）：冻结 576 断面中 **motorway 449 + motorway_link 92 = 77.8%**，arterial 仅 **12** ⇒ 任何「arterial 是否为残差主场」的检验在此靶场上**先天欠功率**（按预注册 BLOCKED，不静默替代）。⇒ 涉及某道路层的残差检验前，**先报靶场该层断面数**；不足则 BLOCKED。
109. **★★「不可观测」的根因要先分清是「匹配质量」还是「断面域定义」**（7.9E-1）：E-0 的 `12 < 30` 曾被读成「arterial 样本少」；E-1 用独立 crosswalk（A+B 覆盖 **97.48%**、中位匹配 **0.57 m**、p90 **2.92 m**）在全量 1,278 链路里标出 **542** 条 arterial ⇒ **不是匹配不准、也不是 arterial 少**，而是**冻结靶场的 576 个断面 `RoadCat` 只有 `CATA`+`SLIP_ROAD`、arterial 断面恒为 0**。⇒ 「某层不可判」必须分三问且**按下述顺序**：**① 断面域里有这个类吗？② 匹配得上吗？③ 样本够吗？**

110. **★★诊断 crosswalk 必须与正式 calibration crosswalk 永久分离且禁止回流**（7.9E-1；`R-OBS-1`）：E-1 的 1,278 链路映射**只作诊断**，⛔ 不回写 7.3.6A、⛔ 不替换冻结 target、⛔ 不用于调 demand/λ/capacity。⇒ 任何「为了让某层可观测」而**放宽匹配阈值**的做法都等价于**制造样本**，须以「**A+B 主分析 + C 仅敏感度**」（`R-OBS-3`）隔离。

111. **★「三档置信 + 只报主档」是几何匹配的标准姿势**（7.9E-1）：A 严格（≤25 m ∧ ≤30° ∧ 语义兼容）/ B 方向几何（≤50 m ∧ ≤30°）/ C 仅几何（≤80 m），主分析用 **A+B**（优先 A）。E-1 实测 **C 档未增加任何匹配**（A+B 已达上界 97.48%，缺口全在 33 条无几何链路）⇒ 放宽到 C 只会**制造样本而不增加信息**。

112. **★★零仿真「自审门」绝不能扫自己的源码文本**（7.9E-0 → 7.9E-1，**同类坑第二次**）：E-0 用 `'subprocess' not in sys.modules`（pandas 惰性导入 `subprocess` ⇒ 误报）；E-1 初版用 `token not in source`，而**检查函数自身的字面量就含 `subprocess.run` / `java -`** ⇒ **自指误报**（`E1.02` 假 FAIL）。⇒ 一律改成 **AST 门**（解析 `Import` / `ImportFrom` / `Attribute` 调用，检查 `banned_modules` 与 `spawn_attr_calls`），**不扫原始文本**。

113. **★★「聚合类别的各组成部分符号相反」时，聚合均值是抵消伪影、不可作归因依据**（7.9E-2）：`arterial_core = primary ∪ secondary ∪ tertiary` 的 flow-weighted 残差分别是 **+7.6% / −34.6% / −41.7%** ⇒ 三类**符号相反**，加权聚合后 **+0.0027 ≈ 0** 纯属抵消 —— 于是 `NO_ARTERIAL_COUPLING_SIGNAL` 是**类别构造伪影**，不是物理结论。⇒ 凡「某聚合类是否残差主场」，**必须先报其内部各子类的残差符号与量级**；符号不一致时**禁止在该聚合层下结论**，须下沉到子类。

114. **★★分层置换统计量必须先做「退化层」体检**（7.9E-2）：RoadCat 分层 `p = 0.05247` 看似「临界无信号」，但 **69.3% 的统计量来自 CATA 层里唯一一条被误映射成 `primary` 的链路（残差 −1.000）** —— 该层 `arterial:n=1 / non:338` 属**退化层**。⇒ 分层检验须同时输出 ① 每层 `n_art / n_non`、② 每层 `|Δmean| × n` 的贡献占比、③ **限定有效层（`n≥30 ∧ 双臂≥5`）** 与 **leave-one-stratum-out** 两套 p。本例三值 = **0.0525（全层）/ 0.0080（仅 CATB）/ 0.0400（去 CATA）** ⇒ **结论完全取决于退化层处理方式**。

115. **★★「诊断域扩容」时，与正式域 overlap 的双相关 + 误差分解是必报项**（7.9E-2；`R-RES-1`）：E-2 的 1,278 诊断残差与 7.7C-0 的 576 正式残差 overlap **576/576**、Spearman **0.9662** / Pearson **0.9398** / mean bias **+0.0229** / MAE **0.0722** / RMSE **0.4655** ⇒ 证明扩容域**口径一致**（RMSE≫MAE 表明重尾）。⇒ 任何「换域重算」必须报这四个量，否则无法排除**人为制造尺度误差**；且 ⛔ expanded residual **永久不得回写为正式 target**。


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

  【7.3.2C 已执行，命令如下】：

```bat
REM 7.3.2C-1 motorway 空间装载（逐行流式，不建 XML 树/route 对象，一次跑通）
python scripts\od\diagnose_motorway_loading_7_3_2c.py ^
  --plans reports\matsim_assignment_6_3_3b\lambda_0p050\ITERS\it.0\step6_3_3b_lambda_0p050.0.plans.xml.gz
REM 7.3.2C-2 CATA 断面空间对应（crosswalk + edge 装载 + sim/obs）
python scripts\od\analyze_cata_spatial_correspondence_7_3_2c.py
REM → reports/od_route_diagnosis_7_3_2c/（step7_3_2c_summary.json + edge_route_loading.csv
REM   + top_motorway_edges + top_motorway_link_edges + route_class_spatial_loading + route_transition_matrix
REM   + cata_section_spatial_correspondence + cata_loading_index_by_roadcat
REM   + cata_spatial_correspondence_summary.json + STEP7_3_2C_REPORT.md）
```

  【7.3.3 已执行，命令如下】：

```bat
REM 零仿真断面语义审计（自动定位 tight crosswalk / network / nodes / TrafficFlow）
python scripts\od\audit_section_semantics_7_3_3.py
REM 可选显式指定（默认项目根 D:\Luan\2026-05\2_Singapore）
python scripts\od\audit_section_semantics_7_3_3.py ^
  --crosswalk reports\matsim_assignment_6_3_2\lta_section_matsim_crosswalk.csv ^
  --network   reports\matsim_network\network_links_source_copy.csv ^
  --nodes     reports\matsim_network\network_nodes_source_copy.csv ^
  --out-dir   reports\od_network_semantic_audit_7_3_3
REM → reports/od_network_semantic_audit_7_3_3/（section_semantic_audit.csv + cata_/sliproad_semantic_audit.csv
REM   + section_upstream_downstream.csv + section_class_transition.csv + section_duplicate_overlap.csv
REM   + roadcat_highway_correspondence.csv + semantic_audit_summary.json + STEP7_3_3_REPORT.md）
REM 无 crosswalk 时脚本明确 FAIL 并列缺失输入（不猜测式匹配）
```

  【7.3.4 已执行，命令如下】（**先重构、后复算**，顺序不可颠倒）：

```bat
REM 7.3.4-A 语义对齐重构（同向 |Δθ|≤30° + RoadCat 语义允许集 + 分级 fallback）
python scripts\od\audit_section_rebuild_7_3_4.py
REM 可选显式指定：--nodes reports\matsim_network\network_nodes_source_copy.csv（默认已指向该文件，坐标列自适应）
REM → reports/od_section_semantic_rebuild_7_3_4/（rebuilt_crosswalk.csv + section_semantic_rebuild_summary.csv
REM   + cata_rebuild.csv + sliproad_rebuild.csv + rebuilt_section_flow.csv + step7_3_4_summary.json）
REM 7.3.4-C 收敛判别 + 过滤归因 + 覆盖偏差（伴随分析；产出权威 STEP7_3_4_REPORT.md）
python scripts\od\analyze_section_rebuild_flow_7_3_4.py
REM → reports/od_section_semantic_rebuild_7_3_4/（rebuilt_vs_old_by_roadcat.csv
REM   + filter_attribution_by_roadcat.csv + strict_filter_coverage_by_roadcat.csv
REM   + rebuilt_direction_audit.csv + rebuilt_section_flow_detail.csv
REM   + section_rebuild_convergence_summary.json + SECTION_REBUILD_FLOW_REPORT.md + STEP7_3_4_REPORT.md）
```

  【7.3.5 已执行，命令如下】（零仿真；需 **geopandas**，用 conda python）：

```bat
REM 7.3.5 SLIP_ROAD 候选几何补全（LTA TrafficSpeedBands_Links 独立几何）
C:\Users\LQP\miniconda3\python.exe scripts\od\build_slip_candidate_completion_7_3_5.py
REM 可选：--search-m 80 --direction-deg 30 --speedbands <path> --out-dir <path>
REM → reports/od_slip_candidate_completion_7_3_5/（slip_candidates_all.csv + slip_candidates_strict.csv
REM   + slip_section_summary.csv + slip_section_coverage.csv + old_vs_new_slip_coverage.csv
REM   + slip_core_missing_recovery.csv + slip_core_radius_sensitivity.csv
REM   + slip_core_nearest_samedir_distance.csv + step7_3_5_summary.json + STEP7_3_5_REPORT.md）
```

  【7.3.6A 已执行，命令如下】（零仿真；无 geo 依赖，conda python 即可）：

```bat
REM 7.3.6A Final Calibration Crosswalk（合并 6.3.2 + 7.3.4 + 7.3.5）
C:\Users\LQP\miniconda3\python.exe scripts\od\build_final_calibration_crosswalk_7_3_6a.py
REM 可选：--cata-n-max 10 --slip-n-max 8 --out-dir <path>
REM   （把 --slip-n-max 调到 12 可显著降低 SLIP 的 REVIEW 比例；聚合口径仍为 median）
REM → reports/od_final_calibration_crosswalk_7_3_6/（final_calibration_crosswalk.csv
REM   + final_section_summary.csv + final_cata_summary.csv + final_slip_summary.csv
REM   + crosswalk_edge_overlap.csv + crosswalk_quality_summary.csv
REM   + step7_3_6a_summary.json + STEP7_3_6A_REPORT.md）
REM 注意：本表不覆盖 7.1 冻结靶场；仅 CATA/SLIP 两类。
```

  【7.3.6B 已执行，命令如下】（零仿真；只读已有 6.3.3B linkstats，无 geo 依赖，conda python 即可）：

```bat
REM 7.3.6B Final Crosswalk 三方回测（7.1 old vs 7.3.4 semantic(strict) vs 7.3.6A final）
C:\Users\LQP\miniconda3\python.exe scripts\od\compare_final_crosswalk_7_3_6b.py
REM 可选：--traffic <json> --linkstats-root <dir> --old <csv> --semantic <csv> --final <csv> --out-dir <path>
REM → reports/od_final_crosswalk_backtest_7_3_6/（final_crosswalk_backtest.csv
REM   + final_crosswalk_roadcat_summary.csv + final_crosswalk_method_comparison.csv
REM   + final_crosswalk_coverage.csv + final_crosswalk_metric_matrix.csv
REM   + step7_3_6b_summary.json + STEP7_3_6B_REPORT.md）
REM 注意：不改 λ / OD / population / network / route-choice；不重跑 MATSim；不动 7.1 冻结靶场。
REM 口径：sim = median(匹配边 HRSx-yavg) × 2.29897；obs = 工作日日内均值→年中位数；主判据窗口 08-09。
```

  【7.4.1 已执行，命令如下】（设计；**从不启动 MATSim**，无 geo 依赖，conda python 即可）：

```bat
REM 7.4.1 联合校准实验矩阵（可复现的单一事实源；randomSeed 校正为 4711）
C:\Users\LQP\miniconda3\python.exe scripts\od\prepare_calibration_experiments_7_4_1.py
REM → reports/od_calibration_7_4_1/（calibration_experiment_matrix.csv
REM   + calibration_parameter_definition.json + STEP7_4_1_EXPERIMENT_DESIGN.md）
REM 9 组：E01–E09；Phase1 = E01–E03（λ=0.050）；不启动 MATSim。
```

  【7.4.2 Phase 1 运行命令】（**会跑 MATSim，约 11.5 h**；需项目本地 JDK25 + matsim-2026.0）：

```bat
REM 7.4.2 Phase 1（E01 λ=0.050 f=0.50 / E02 f=0.75 / E03 f=1.00，均 20 it）
C:\Users\LQP\miniconda3\python.exe scripts\od\run_calibration_phase1_7_4_2.py --gen-only   REM 先只生成+校验 config
C:\Users\LQP\miniconda3\python.exe scripts\od\run_calibration_phase1_7_4_2.py --smoke 2000  REM 冒烟（2000×3it）
C:\Users\LQP\miniconda3\python.exe scripts\od\run_calibration_phase1_7_4_2.py             REM 全量（可断点续跑）
REM 可选：--experiments E01 E02 E03  --heap 12g  --force（忽略续跑检查）
REM → reports/od_calibration_7_4_2/<EID>_lam*_cap*/(ITERS/it.19/*.linkstats.txt.gz)
REM   + matsim/step6_3/config_E0*_lam*.xml + matsim/step6_3/logs/<EID>_run.log
REM   + reports/od_calibration_7_4_2/phase1_run_manifest.json
REM 注意：唯一实验变量 = qsim.flowCapacityFactor(+storage 同值)；seed=4711；不动 OD/departure/network/crosswalk。
```

  【7.4.2 Phase 1 评价命令】（零仿真；跑完 3 组后执行）：

```bat
REM 7.4.2 评价（Final Crosswalk 7.3.6A + 7.1 冻结口径；默认取最末迭代 it.19）
C:\Users\LQP\miniconda3\python.exe scripts\od\evaluate_calibration_7_4_2.py
REM 可选：--iteration 0（看首迭代）--allow-baseline-only（实验未跑完时只出基线自检）
REM → reports/od_calibration_7_4_2/（phase1_backtest.csv + phase1_roadcat_summary.csv
REM   + phase1_capacity_comparison.csv + step7_4_2_phase1_summary.json + STEP7_4_2_PHASE1_REPORT.md）
REM 核心输出：f × {Sim/Obs, WMAPE, GEH<5, CATA, SLIP_ROAD, CATA/SLIP}（窗口 08-09）。
REM 注意：不改 λ / crosswalk；不重跑 MATSim；7.3.6A Final Crosswalk 仅覆盖 CATA+SLIP 两类。
```

> ⚠️ 环境：本机 `python`（PATH）可能缺 numpy → 用 `C:\Users\LQP\miniconda3\python.exe`（pandas 3.0.1 / numpy 2.3.2）。

---

## 6. 冻结 / 待定

| 项 | 状态 |
|---|---|
| Step 3B.1 Attraction | 🔒 冻结 |
| Step 4 `C^FF` | 🔒 冻结 |
| Step 5B Census-constrained Prior OD 基线 | 🔒 冻结 |
| Step 5C.1 `C^AM,v2` | 🔒 冻结（**38.35% 长度覆盖，不再继续追求覆盖**） |
| Step 5C.1 Prior OD `T^5C.1` | ✅ PASS（5 组 λ，守恒到机器精度） |
| Step 5C/5C.1 最终 λ* | ⏳ **仍暂不冻结 —— 7.6G 已证 λ 在本靶场 `DETECTABLE_NOT_IDENTIFIABLE`（Δ = 2.3162 pp，介于噪声底 1.0 pp 与辨识下界 7.609 pp 之间）⇒ 不能由数据选出 λ**；**λ = 0.075 保留为「敏感度中心」取值**；最终 λ 须待**外部数据**（LTA 分车型交通量 / HTS 出发时刻），与 demand scale 同路径 |
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
| Step 7.3.2B Route-structure Diagnosis | ✅ **PASS**（**A"不走高速"否定：61.1% 路线 / 41.5% 长度用 motorway；0/196,447 OD 多路径**；ramp 链 5.12M 次 ml→ml） |
| Step 7.3.2C Motorway Flow Spatial Loading | ✅ **本轮 PASS**（流式边装载 + CATA 空间对应；**motorway 4,780 边 84.6% 被用、Top100 仅 9.57% → 装载极分散**、TOP=CTE 微段；**CATA 装载指数 0.846（64.5% 低于均值）**、`r(装载,sim/obs)`=+0.19；**★CATA≈SLIP 装载（0.85）但 sim/obs 相反（0.69 vs 2.05）→ 装载非判别变量、指向 C 类（观测/表达）**） |
| Step 7.3.3 断面语义 ↔ MATSim Link 表达审计 | ✅ **本轮 PASS**（零仿真；覆盖 97.48%、10.30 边/断面；**★CATA↔motorway 干净（等级一致 99.23%）/ SLIP_ROAD↔motorway_link 脏（等级一致 31.6%、dominant 主线 55.8%）→ 匝道被主线化**；一边共享 28.1%、断面共享边 73.3%；**对向车道混入：32.4% 边反向 / 72.1% 断面含反向边 / 仅 8.5% 可串单链** → **C 类直接证实**，route-choice 后置） |
| Step 7.3.4 语义对齐重构 + Sim/Obs 收敛判别 | ✅ **本轮 PASS**（零仿真；断裂面 1,278；**边/断面 10.30→4.70、CATA 纯度 92.9%→97.64%、SLIP motorway_link 纯度 30.7%→52.99%**；**★过滤归因：dir_only 不动（0.42）/ sem_only 即达 0.966 → 主因=语义错配非方向**；**strict 下 CATA/SLIP 0.363→0.914、SLIP 2.033→0.854**；**覆盖缺口：117/251（46.6%）SLIP 断面基座无 motorway_link 候选**、CATA 稳定 ≈0.78 → **停止 route-choice，转 7.4 crosswalk 覆盖修正**） |
| Step 7.3.5 SLIP_ROAD 候选几何补全 | ✅ **本轮 PASS**（零仿真；独立 LTA 几何 5,207 slip；**CORE 251：旧有 motorway_link 138（54.98%）→ 新 250（99.60%）**；**★旧缺口 113 补回 112（99.12%）**；**最近同向匝道 ≤5 m 93.5% / ≤20 m 98.4%**；**半径 50 m 即 98.2%、200 m 无增益**；唯一仍缺失 **48170**（最近 ramp 227 m）；**判定 A（大量补回）** → 根因＝旧 crosswalk 的"路名锚"（精确同名仅 29.1%）→ **SLIP→匝道改用"几何重合+同向"，路名仅作辅助**） |
| Step 7.3.6A Final Calibration Crosswalk | ✅ **本轮 PASS**（零仿真；合并 6.3.2+7.3.4+7.3.5；**硬规则 CATA→motorway / SLIP→motorway_link，SLIP 不以 RoadName 为硬约束**；**覆盖 CATA 326/339（96.17%）/ SLIP 250/251（99.60%）**；**纯度 100%/100%**；**对向残差 1.10%**；**共享边率 4.87%**；rows 3,193 / 断面 590；Tier CATA_T1 1,046 / SLIP_T2 1,515 + T1 597 + **T3 几何回退 35**；**UNMATCHED 14 不强行匹配**；**REVIEW 109（SLIP 中位边数 8 恰压上限）**；5 门全过；**仅覆盖 CATA+SLIP**；**7.1 靶场不动**） |
| **Step 7.3.6B Final Crosswalk 三方回测** | 🔒 冻结（零仿真；**★CATA/SLIP `0.3633 → 0.9135 → 1.0984`**，08-09；SLIP `2.0333→0.8535→0.7098`、CATA 恒 0.7797；参照 7.3.4-full = 0.4100；**断面语义错配（C 类）正式剔除**；残差转为整体量级 <1） |
| Step 7.4.1 联合校准实验矩阵 | 🔒 冻结（**设计，从不启动 MATSim**；θ={λ, f_cap, route-choice}；9 组 E01–E09；**Phase1=E01–E03** / Phase2 按需；**★randomSeed 校正为 4711**（草案 20260912 系误写，已披露）；`parameters_changed=false` / `lambda_selected=false` / `matsim_runs_started=false`） |
| **Step 7.4.2 Phase 1（E01–E03）** | ✅ **PASS（上一轮跑完）**（λ=0.050 × f_cap 0.50/0.75/1.00 × **20 it**，全部 `exit=0`，~10.6 h；**★capacity 强总量杠杆 Sim/Obs(all) 0.399→0.570→0.810 + 结构极差 0.2371（=2.41× 基线偏离）**；`CATA/SLIP` **0.8328→0.9078→1.0698**；**CATA 对 capacity 弹性 ×2.11 > SLIP ×1.64 → 结构差源于拥堵弹性而非语义重分配**；**f=1.00 全面占优 → 不存在更优 f<1.00**；同 f=1.00 迭代效应 Sim/Obs `0.7690→0.8105`、`CATA/SLIP 1.0984→1.0698`） |
| **Step 7.4.2 Phase 2（λ 灵敏度）** | ✅ **PASS（本轮跑完）**（capacity 固定 **1.00**、20 it，只扫 λ，E06/E09 全部 `exit=0`；**E03(λ0.050,复用 Phase1)/E06(λ0.075)/E09(λ0.100)**；**E10(λ0.025)=DEFERRED**；⚠️**用户口述 E04/E05/E06/E07 与 7.4.1 矩阵编号不一致，已披露映射**；**★λ 非结构杠杆（CATA/SLIP 极差 0.0146 = capacity 0.2371 的 1/16）；λ 非量级杠杆（Sim/Obs 非单调，峰@0.050=0.8105 / 谷@0.075=0.7070，最优仍 <1）；λ 对截面拟合有真实但有限正效应（E06 λ=0.075 三窗口 WMAPE/GEH/Pearson/Spearman 一致最优）→ 「量级最优 0.050 vs 拟合最优 0.075」权衡**；**λ 仍不冻结**） |
| **Step 7.4.3 demand scale（设计 + 运行器）** | ✅ **本轮 PASS（全量跑完，D02→D03→D04 各 20 it、全部 `exit=0`，D04 墙钟 492.94 min）**（固定 **λ=0.075 / f_cap=1.00 / 20 it**，唯一变量 = demand scale 因子 `f_demand`；**D01 = REUSE_E06（不重跑）/ D02 f=1.10（220k）/ D03 f=1.20（240k）/ D04 f=1.25（250k）**；**嵌套随机子集复制 `seed=20260912` → D01⊂D02⊂D03⊂D04 增量无偏**；**★MECHANISM：MATSim 只消费 agents（车辆数）= 唯一物理需求杠杆；`expansionFactor`（Σ=459,794 恒定但被 MATSim 忽略）与 `odTrips`（Σ 随 λ 变 = cell 内 agent 数分布的影子）均**不作**缩放对象**；**λ 仍不冻结**） |
| **Step 7.4.3 评价（零仿真，正式结果）** | ✅ **本轮 PASS**（import 冻结 7.3.6B + 7.4.2 评价函数，口径逐字节同源；评价接口 = 7.3.6A Final Crosswalk、观测 = 7.1 冻结；**D01 自检逐位复现 E06（0.7070 / 0.7137 / 0.6706 / 1.0642）** ✅；**★双系列：D 系列（物理加车、跑仿真）vs A 系列（算术参照 = D01 sim ×f，零仿真）→ A−D = 拥堵弹性阻尼**；**★08-09（Σsim/Σobs）：0.7070 → 0.7095 → 0.8601（峰@f1.20）→ 0.7599，非单调；最强 0.8601 仍 <1（差 0.1399）→ 加车补不满量级缺口；CATA/SLIP 极差 0.1738（=λ 的 12×、capacity 的 73%）且穿越 1 → 结构不中性，SLIP 弹性 ×1.249 > CATA ×1.045；A−D 阻尼 +0.0682 / −0.0116 / +0.1239 非单调**；**★已修正报告 §5 硬编码"结构基本中性"→ 数据驱动判决**；**λ 仍不冻结、f_demand 未选定**） |
| **Step 7.5A 需求权重链条核查（审计）** | ✅ **PASS（本轮，零仿真）**（**★决定性证据 = `matsim-2026.0.jar` + `libs/*.jar` 字节级常量池扫描（165 jars / 38,647 entries）**：`expansionFactor` **仅**在 `commons-math3` 的 `ResizableDoubleArray.class`（无关同名字段）、`odTrips` **零命中**；阳性对照 `flowCapacityFactor`/`storageCapacityFactor`/`countsScaleFactor` 全部命中 **MATSim 自身 class**；项目自定义 Java = 0、全项目 `*.xml` 命中 = 0；**判决 `NOT_CONSUMED`：MATSim 不消费 `expansionFactor`/`odTrips`，有效需求权重 = 进入 QSim 的 person/vehicle 数 → 扩样必须在评价层 `SCALE = ΣT/N_sample`**） |
| **Step 7.5A 固定样本量采样架构（100k）** | ✅ **本轮：设计 PASS + 人口管线 PASS + config PASS + 冒烟 PASS + S100 全量完成 + 评价 PASS（判 `NOT_SUBSTITUTABLE`）；S100c 全量完成（100k × 20 it，164.59 min，exit=0；判 `NOT_SUBSTITUTABLE`）**（**★三层需求**：真实需求 ΣT=459,794 / 采样率 `N_sample` / 有效权重 `SCALE=ΣT/N_sample`；**★硬约束**：λ=0.075 正 OD cell=**71,136** → `N_sample ≥ 71,136`，**50k 不可行**；**实验矩阵 S200（=D01/E06 复用, 200k, f_cap=1.00, SCALE=2.29897）/ S100（100k, f_cap=1.00, SCALE=4.59794）/ S100c（100k, f_cap=0.50 采样一致对照）**；**★容量—采样耦合**：改变采样率时 `flowCapacityFactor` 必须同比缩放才保持同一物理场景——这是采样一致性的数学要求，非性能旋钮；100k 人口实测 persons=100,000、ΣEF=459,794.0、mean_ef=4.59794；**★不覆盖冻结 200k 产物**（新目录 `*_s100k`，mtime 未变）；**★结果（2026-09-15）**：S100 全量完成（100k × 20 it，`exit=0`，**143.80 min**），**08-09（Σsim/Σobs）：S200 0.7070 → S100 0.9784**；**线性度不达标**（`raw S100/200` 中位 **0.6174** ≠0.5 → 减样本后单位 agent 流量 **+23.5%** = 车密度减半拥堵减轻）；**等价性差**（scaled 比值中位 **1.2308**、±10% 内 17.9% / ±20% 内 32.6%，但 Pearson 0.9006 / Spearman 0.9567 → 形态强一致、仅整体偏高）；**△判决 `NOT_SUBSTITUTABLE`，物理结论 = f_cap=1.00 对照不干净**（混杂「采样效应」+「拥堵改变」）→ 须 **S100c（100k, f_cap=0.50）** 干净对照方能否定/确认 100k 可替代性；**★S100c 全量完成（100k × 20 it，`exit=0`，164.59 min，20 迭代全落盘，`STATUS: PASS`）**；**★S100c 预注册判据 C1–C7 在运行前已落盘**（`preregistered_criteria.json` + `STEP7_5A_S100C_PREREGISTRATION.md`：C1 raw ratio≈0.50 / C2 scaled 中位≈1.00 / C4 ±20%≥0.80 / C5 Pearson≥0.90 & Spearman≥0.95 / C6 CATA÷SLIP 漂移≤0.05 / C7 三窗口一致；C3 仅报告）；**★S100c 结果（2026-09-15）**：预注册硬门槛 **1/6 PASS（仅 C6）→ `NOT_SUBSTITUTABLE`**；**f_cap=0.50 部分有效**：raw 线性比 **0.6174→0.5799**（采样非线性 +23.5%→**+16.0%**）、**CATA/SLIP 漂移 0.0480→0.0233（C6 PASS，结构畸变主因是车密度/容量）**；**但残余 16% 非线性不可由标量 f_cap 消除**（scaled 比值中位 **1.1537**、±20% **0.2648**、Pearson 反降至 **0.8557**；候选机制：6.2B「每正 OD cell ≥1 agent」使 100k 下 **71.1% agent 为保底 agent** → 样本空间分布随 N 变平）→ **100k 不可替代 200k；「固定样本+可变权重」在拥堵型网络不成立；100k 方案不冻结**；**`f_cap=0.50` 仅作采样一致性校正、非供给标定参数**；**λ 仍不冻结**） |
| **Step 7.5B Sampling Rule Sensitivity（采样规则敏感性）** | ✅ **本轮完成：设计 PASS + 采样规则诊断 PASS + S100r 人口管线 PASS + config PASS + 冒烟 PASS + 判据跑前预注册 + ★S100r 全量跑通（171.20 min，exit=0）+ 三方正式评价 → 判决 `PARTIAL_IMPROVEMENT`（D 0/6、M 3/4）**（**唯一变量 = 采样规则**：`S100c` 现行「每正 cell ≥1 agent」保底规则（复用）vs **`S100r` 纯 trips-proportional（无保底）**；其余全冻结：`N=100k` / `λ=0.075` / `f_cap=storage=0.50`（=N/N_ref **采样一致性校正**）/ 20 it / `seed=4711` / `routingRandomness=0` / 同 network·OD·departure·crosswalk·靶场；**★单变量机器验证：两 config 除 outputDirectory/runId/inputPlansFile 外逐字节相同**；**★诊断（零仿真）**：100k 纯比例 → sampled **38,350** / **zero-sampled 32,786（46.09%）** / **OD coverage 0.5391** / 丢弃 trips **21,528（4.68%）** / **ΣEF 438,266.0**（`f_realized` 0.95318）/ 被采样 cell 逐 cell 守恒误差 **5.68e-14**；对照保底规则 100k：zero 0 / coverage 1.0 / 保底占比 **71.14%** / agent 中位 **1**（纯比例 max 26→**87**））；**★判据 D1–D7（绝对，与 7.5A C1–C7 同阈值）+ M1–M4（机制，差分 vs S100c）已跑前固定落盘**；**判决规则**：D 全 PASS → `SAMPLING_RULE_WAS_THE_CAUSE` / M ≥3 → `PARTIAL_IMPROVEMENT` / M <3 → `SAMPLE_SIZE_DEPENDENT`（knee 扫描的前置条件）；**λ 仍不冻结；未动 capacity（0.50 仅采样一致性校正）**） |

| **Step 7.4.3 补充诊断（非单调回落机制）** | ✅ **PASS（本轮，零仿真只读）**（判决 **`TIME_WINDOW_ARTIFACT_CONFIRMED`**，T1–T5 全过；**★决定性证据 = 窗口加宽**：08-09 单小时 f1.25/f1.20 **0.9584**（下降，非单调）vs **07-11 = 1.0404**、**0-24 = 1.2547**（≈ 纯比例 1.0417 / 1.2500，达成率 100.4%）→ 需求完整投递、仅时间摊开；**★机制在下游行进端**：出发占比跨档极差仅 **0.035 pp**，而平均行程时长 33.24→**38.99 min**、8-9 拥堵倍率 2.314→**2.796**、09:00 前到达 73.26%→**68.35%**、09-10/10-11 到达 +12%/+68%；**★次要**：08-09 单小时估计量超额系数在 0.848–1.096 摆动（07-08 稳定 0.930–1.033）→ 水平口径建议改 **07-11 累计**；**λ 仍不冻结；未动 capacity**） |
| **当前正式标定基准（用户裁定，2026-09-16）** | 🔒 **冻结 `N_sample = 200,000` / `f_cap = 1.00`**；**100k 暂不作为替代样本**（S100 / S100c / S100r 均判不可替代）；**`λ` 不冻结**、**demand scale 不冻结**、**sampling rule 不重构**（维持 6.2B 保底规则）；**capacity 保持 1.00**（不作性能旋钮） |
| **Step 7.6A Official Car-Demand Accounting** | ✅ **PASS（本轮，零仿真只读；12/12 校验）**（判决 **`CALIBER_GAP_DOMINATES`**；`ΣEF` 459,794 = Car Only 459,796 名义锚（Δ = 2 取整）；物理 / 非物理 **1,935,235 / 273,124 守恒 Δ = 1**；**观测无车型字段 ⇒ 车型构成不可分解**；**`f ∈ [1.0504, 1.4641]` —— 总量证据不能识别单点**；**未改动任何模型产物**）|
| **需求口径裁定** | 🔒 **已裁定（2026-09-16）：保持 V1（`Car Only` = 459,796）**。V1 与 MATSim car-only 通勤语义**严格对齐**；改 V2（`Car or Taxi/PHC`，隐含 f = 1.1450）属**口径对齐**，须先取分车型观测，且**载客率方向相反**，两项必须同时处理；在二者分离前 `f_cap = 1.00` / capacity = 1.00 / demand scale 均 **维持现状** |
| **Step 7.6B Assignment / Route Stability Audit** | ✅ **PASS（本轮，零仿真只读；20/20 校验）**（判决 **`UNCONVERGED_PERIOD2_LIMIT_CYCLE__CROSS_F_SIGNAL_BELOW_PHASE_NOISE`**；**D01–D04 全部呈周期-2 极限环**；MATCHED 振幅 1.59% / 3.77% / **20.75%** / 16.22%，ALL 仅 0.39–1.40%（**放大 14.8×**）；**周期均值把 08-09 跨 f 极差 15.30% → 5.87%**；**同相位检验：偶相位单调下降 vs 奇相位峰在 D03 ⇒ 响应符号由采样相位决定**；**未改动任何模型产物**）|
| **Step 7.6D Route-choice Stabilization（最小修复 + 配置验证）** | ✅ **配置验证 PASS（本轮，零仿真；19/19 校验）**：`matsim_routechoice_7_6d/` 独立工作区；最小修复 = `fractionOfIterationsToDisableInnovation` `Infinity→0.8` + 策略集 `[ReRoute 1.00]→[ReRoute 0.15, ChangeExpBeta 0.85]` + `learningRate` `1.0→0.5`；**与基线差异仅 4 处**；冒烟预检 PASS；**200k 正式 run 已由 7.6E 执行完成并判 `STABILITY_PASS`（6/6）** |
| **Step 7.6D 稳定性预注册判据** | 🔒 **已跑前冻结**（`STEP7_6D_PREREGISTRATION.md`）：`A_W(X) = (max−min)/mean`；主判据 **`A_10:19(MATCHED) < 3%` = STABLE** / 3–10% PARTIAL / ≥10% UNSTABLE；四口径 **ALL / MATCHED / CATA / SLIP**；**★修复前基线：**MATCHED `A_10:19` = **8.48%**（f=1.00）/ 11.10% / **23.25%** / 20.32%（f=1.10/1.20/1.25）、ALL 仅 1.51–3.96%、SLIP 最差 **35.51%** |
| **★统计量口径警示（与 7.6B 不可混用）** | ⚠️ 7.6B 的「周期振幅」= `|even−odd|/mean`（仅相位分离）；本步骤 `A` = `(max−min)/mean`（相位分离 + 窗内非交替漂移）。D01 MATCHED：**1.59% vs 8.48（5.3×）**。今后引用「20.75%」必须说明那是 **D03 的 `parity_gap_rel`** 而非 `A_10:19` |
| **Step 7.6D-S 低样本(100k)稳定性筛查** | ✅ **完成，判 `SCREENING_PASS`**（`exit=0`，**33.20 min**，linkstats 20/20）：N=**100k**、`f_cap=0.50`（原定 50k 因 `FLOOR_PLUS_1` 下界 **71,136** 不可行）；**同 N 严格对照**（复用 S100c 人口与 20 迭代 linkstats，边际成本为零）；配置 **25/25 PASS**；**预注册门槛** MATCHED `<3%` / CATA `<3%` / SLIP `<5%`（`parity_gap_rel` 仅辅助诊断）；**`A_10:19` MATCHED 5.84%→0.71% / CATA 4.31%→0.76% / SLIP 10.86%→0.60% / ALL 1.38%→0.44%** ⇒ **3/3 全过**；逐迭代由周期-2 极限环变为**单调指数收敛** |
| **Step 7.6E 200k 正式稳定化（route-choice 正式冻结门）** | ✅ **完成，判 `STABILITY_PASS`（G1–G6 6/6）⇒ ★route-choice 层正式冻结，成为后续所有实验的分配底座**（`exit=0`，**84.41 min**，linkstats 20/20，≈4.2 min/it）：`R01_rc_min` = **200k × 20 it**、`f_cap=1.00`，**唯一变量 = route-choice 4 项**（与 7.6D-S 逐参数一致）。**四口径 `A_10:19`（200k D01 前 → R01 后）**：MATCHED **8.48%→1.00%**（×0.12）/ CATA **10.14%→1.01%**（×0.10）/ SLIP **8.93%→0.97%**（×0.11）/ ALL 3.96%→**0.51%**；`parity_gap_rel`(MATCHED) **1.59%→0.13%**。**双口径**：`Q̄_10:19`=**4,567,962** / `Q_19`=**4,576,724** / `Q19/Q̄`=**+0.19%**；`sign_consistency`=**1.000**；`never_arrived=0` & `max_stuck_car=0`（200,000 departures = 200,000 arrivals）；`A(200k)/A(100k)`=**1.40**；`A_full_00_19`=8.79% **仅报告**（burn-in 瞬态）。**★跨规模可复现**：100k/200k 归一路径几乎重合（it.0 0.9112 vs 0.9169；it.19 1.0010 vs 1.0019）⇒ **机制签名**。**★结构性副产物（仅记录）**：收敛单调把流量搬到标定断面，MATCHED `it.0→it.19` **+9.28%**、ALL **−3.70%**（反单调，100k 同形 +9.85%/−3.78%）⇒ 收敛解 MATCHED `Q̄` 比 D01 极限环中心 **+3.1%**；**本步不评价 Sim/Obs**（属 7.6F） |
| **Step 7.6F-0 新稳定底座 demand=1.00 基准重算** | ✅ **完成，判 `PASS`（零仿真只读；20/20 校验）**：`reports/od_calibration_7_6f/`。**★新基准点（R01, demand=1.00, 200k, f_cap=1.00）Sim/Obs(08-09) Primary = `0.8590`**（Reference `Q_19` = 0.8603；AM = 0.7665）**⇒ 取代旧 D01（0.7070）成为后续 demand-scale 分析的参照**；**★机制分解（固定 demand=1.00、同 N、同 f_cap，仅 route-choice 变）**：200k `0.7506 → 0.8590`（**+14.43%**）、100k `0.8169 → 0.9639`（**+18.00%**）⇒ **机制签名**；而 `Σ(cycle-mean HRS0-24avg|MATCHED)` 仅 **+3.11%** ⇒ **断面流量位移 ≠ Sim/Obs 位移（差 4.6×）**。**未改动任何冻结件** |
| **Step 7.6F-0 旧 demand 响应谱可辨识性判决** | ⛔ **`LEGACY_CURVE_UNINFORMATIVE`**：D01–D04 统一 Primary 口径后 **非单调**、内部极差仅 **0.0587**，而四点极限环振幅均值 **0.1579** ⇒ **信噪比 0.372 < 1**；**新基准点 0.8590 高于旧谱全部四点（最高 0.7655）** ⇒ 旧 demand 扫描（f=1.00→1.25）被机制伪影吞没。**⇒「结合既有 D01–D04 给出约束区间」路径封闭**；若需 demand 响应信息只能在新底座重建（**7.6F-1**，3 × ~85 min，**本轮未启动**）|
| **★Step 7.6C OD 空间结构诊断** | ✅ **完成，判 `OD_STRUCTURE_PARTIAL`（零仿真只读；23/28 校验）**：`reports/od_structure_7_6c/`。**★结构可信三条**：Table118 物理格 中位 |残差| **0.0026 / P95 0.0095**（S5）；**0 个 `|z|>5` 异常吸收区**（S6）；**detour 1.068–1.111**（S7，per-agent plans 与 linkstats 全天/planned **1.1106** 独立互证）。**★必须直视一条（S4 FAIL）**：`0.8590` 缺口**不均匀** —— **EAST 0.582 / CENTRAL 0.790（亏）vs NORTH 1.067 / NORTH-EAST 1.158（盈）**，区域最大相对偏差 **0.348 > 0.25**；**radial_in 0.612 vs radial_out 0.976**（进中心方向系统性低估）；**R5 20km+ radial_in 13/13 断面零仿真流**；**54 断面 sim=0 却占 8.14% 观测** ⇒ 剔除后全局 0.8590→**0.9351**，但区域偏差仅 0.348→**0.333** ⇒ **不是零流断面造成的，是真实空间结构成分**。**★口径**：OD 距离结构合理（需求加权均值 12.64 km / 中位 11.67 km；short/med/long 14.28%/52.20%/33.52%；**采样偏差 0.00 pp** ⇒ 验证 6.2B）；质量守恒到浮点精度（`ΣEF` 与 `N×SCALE` 均 == 459,794）。⇒ **`0.8590` 不能当作一个干净的规模因子**。**未选 demand scale / 未评价 λ**；**7.6F-1 是否补跑待用户裁定** |
| **★Step 7.6C-2 靶场完整性门控** | ✅ **完成，判 `TARGET_MARGINAL_COARSE_ONLY`（零仿真只读；判据 7/10；16.7 s）**：`reports/od_target_integrity_7_6c_2/`。**★核心量 `Delta_target` = Q_POSITIVE_ONLY − Q_FROZEN = 0.9350621 − 0.8589732 = 7.609 pp**。**★信噪比**：粗档 0.10 → **SNR 1.056**（✓，需 ε ≥ 0.947）；细档 0.05 → **SNR 0.528**（✗，需 ε ≥ 1.895 才可识别；而 8-9 过饱和份额恒 0% ⇒ ε ≈ 1）⇒ **靶场不确定性与粗档 demand 增量同量级**。**★f\* 识别区间 [1.06945, 1.16418]**（宽度 0.09473），三口径方向一致（f\* > 1）。**★网格位置：`1.10/1.20/1.25` 未跨越区间；f = 1.10 落在区间内部（口径分歧），1.20/1.25 三口径一致越 1.0** ⇒ 3 跑只买 2 区制；**建议 `1.00/1.10/1.20` 或 `1.05/1.15/1.25`**（间距 0.10 ≥ `Delta_f_target`）。**★结构可分性 0.5576 / 0.0761 = 7.33× ✓** ⇒ 7.6C/7.6C-1 结构结论不受污染；EAST 相对亏损 −0.3220 = `Delta_target` 的 4.23×。**★断面集口径澄清**：7.3.6A = **576 断面 / 574 primary candidate / 3,015 primary 去重匹配链**（全 crosswalk 3,037），但 7.6C `section_geography` 只有 574（缺 190339 YIO CHU KANG ROAD、195768 PAN ISLAND EXPRESSWAY）⇒ 7.6C-1 repair bounds 内部 `dropna` 后按 574 算（与其 anchor 行差 **4.06e-4**）；574 子集稳健（**7.619 pp / SNR 1.053 / 0.527**）。**★硬约束**：「发现可修正伪影」≠「已允许修改冻结靶场」；修改须另立版本（7.3.6A-b）；**不得把 0.9351 升格为新靶场，不得用 0.8590 / 1.1642 反推 demand scale**。**不启动 7.6F-1**（等用户裁定） |
| **★Step 7.6C-1 异常归因追踪** | ✅ **完成，判 `MIXED_COVERAGE_AND_RESIDUAL_STRUCTURE`（零仿真只读；5/5 判据、6/6 校验）**：`reports/od_anomaly_trace_7_6c_1/`。**★硬零流 = 覆盖/归属/方向/统计口径伪影**：13 个 R5/radial_in 零流断面（全部 WEST/TUAS+PIONEER）的 **47 条匹配边在三窗口 × 正反向全为 0**、**43/47 有向拓扑孤儿**（正常链路 0.987/0.991）、**0/47 连通**；**54/54 零流断面 100 m 内有有流平行链、52/54 在 60 m 内、50/54 同路名有流链**（1,559–39,762 veh/h 就在邻域）；机制四类 `CROSSWALK_TWIN_ORPHAN` 31 / `DIRECTION_MISMATCH` 13（匹配边跨双向混合 ⇒ 中位塌 0）/`WINDOW_ARTIFACT` 8 / `GENUINE_UNROUTED` **仅 2（0.38% 观测）** ⇒ **8.14% 硬零流可正式判为测量伪影**，`0.8590 → 0.9351` 由此解释。**★graded 缺口 = 真实（对任何修正稳健）**：保守 `best-direction` 修正后 EAST 0.582→**0.622**、`radial_in` 0.612→**0.634**，仍远低于 NORTH-EAST 1.158 / `radial_out` 1.022、`circ` 0.956。**★Layer 2 三假设全否证**：① 吸引量（Table118 物理格 220 个，中位 0.0026 / P95 0.0095）；② OD 方向（EC 不对称 0.2112 ∈ [0.1044,0.3089]）；③ 路径改道（EC 实走路径 **64.25% `radial_in`**、**99.2 东走廊链次/出行**；CE 以 `radial_out` 58.85% 为主）⇒ **EAST 低估 = 细粒度链路归属 + 断面中位口径**。⇒ **不得**用 `0.8590`（或其倒数 `1.1642`）反推 demand scale。**未选 demand scale / 未评价 λ**；**7.6F-1 可进入** |


| **★评价口径修订（**已采纳，2026-09-16**）** | ✅ **双口径并报（不以周期均值「替代」 it.19）**：**Primary = `Q̄_10:19`**（收敛窗 it.10–19 奇偶相位均衡周期均值，跨 f 极差 15.30% → 5.87%）；**Reference = `Q_19`**（单点，**不丢弃、保留可追溯性**）。两者同时输出（`audit/routechoice_stability_dual_caliber.csv` 的 `Q_conv_mean` / `Q_19`）。**分配稳定性已于 7.6E 解决（`STABILITY_PASS` 6/6）⇒ 该冻结解除**：route-choice 层正式冻结，`demand scale` / `λ` 的重新评价进入 **7.6F**（`Q19/Q̄` = **1.0019**，单点已具备代表性，但仍按双口径并报）。`N_sample` = 200,000 / `f_cap` = 1.00 / capacity = 1.00 **维持冻结**；`λ` / demand scale **仍不冻结** |
| **待补机制闭环实验（已裁定后置，非主线）** | ⏳ **`PURE_TRIPS_PROP @ 200k`（`f_cap = 1.00`）** —— 现有三组 `S100r = 100k + PURE` / `S200 = 200k + FLOOR` / `S100c = 100k + FLOOR` **缺少 `200k + PURE`**，故 **N 效应与 sampling-rule 效应尚不能完全解耦**；该实验属**方法论验证**，**不是当前主模型推进的必要条件**，用户已裁定**暂不跑** |
| **★Step 7.6G λ 敏感度 screening** | ✅ **完成，判 `LAMBDA_DETECTABLE_NOT_IDENTIFIABLE / SPATIAL_INERT`（零仿真只读；21/21 校验；823.1 s）**：`matsim_lambda_7_6g/`。**★判决口径**：λ 全跨度（0.05→0.10）使 Sim/Obs 变 **−2.3162 pp** ⇒ **> 噪声底 1.0 pp（可检出）但 < 7.609 pp 靶场辨识下界（不可辨识）** ⇒ **λ = 0.075 是「敏感度中心」，不是数据最优 λ**；**Δf\* = +0.03015** ⇒ 7.6H 的 f\* 带 = **[1.1637, 1.1938]**（λ 0.05–0.10）。**★直跑复核**：`L75 @ f=1.18` = 0.9998291 ⇒ f\* = **1.180222** vs 7.6F-1 插值 **1.1803**（差 0.007%）。**★空间 `SPATIAL_INERT`**：EAST 极差 **0.9051 pp**、`radial_in` **0.3960 pp**（缺口 **−31 pp** 量级）⇒ **λ 亦不能修空间结构**，与 7.6F-1「全局量级 ⊥ 空间结构」一致 |
| **★Step 7.6H 最终工作点确定与独立验证** | ✅ **完成，判 `WORKING_POINT_FROZEN_AND_REPRODUCIBLE / SPATIAL_RESIDUAL_PERSISTS`（`W01` 单跑 102.22 min；零仿真评价 26/26）**：`matsim_final_7_6h/`。**★设计**：**第一层冻结 + 第二层一次独立验证**，**不是最终标定、不是参数搜索**。**第一层**：`λ_ref=0.075`（7.6G 敏感度中心）/ `f_demand,ref=1.180222`（7.6G `L75` 实测）/ `SCALE=2.29897`（⛔ 不按 ΣEF/N 重算）/ `f_cap=1.00` / `R01_rc_min` / 7.3.6A crosswalk / `N_base=200,000`。**第二层**：`N_sim = round(1.180222×200,000) = 236,044`（⛔ **不是** `459,794/236,044`）。**★H1 可复现**：`Sim/Obs FROZEN` **0.999335**（Δ **0.0665 pp**）；隐含 `f*` **1.180866**（Δ 6.44e-4）；`f_realized` 1.1801564（Δ 6.6e-5）；vs 7.6G `L75` Δ **0.0494 pp**。**★H2 稳定**：`A_10:19`(M/C/S) **0.8899/0.9038/0.8568%**、`parity_gap_rel` **0.0964%**、`Q19/Q̄` **1.001972**、`never_arrived=0` / `max_stuck_car=0`。**★H3 空间残差仍在**：8 组 max \|Δ vs `L75`\| = **0.7599 pp**（格局保持）；EAST **−31.75%**、`radial_in` **−30.67%**、NE **+33.88%** ⇒ **不追求消除**。**★H4 三层带不合并**：工作点 `f*=1.180222` / λ 敏感带 **[1.1637,1.1938]** / 静态靶场带 **[1.06945,1.16418]**。**★H5 未解决**：量级达标但空间残差对 demand/λ 低敏感，不宜强行消除；三项本地不可定量。**对账**：X1 3/3（Δ ≤ 4.9e-8）+ X2 4/4（**Δ = 0.00e+00**）；SCALE 审计 R01 **0.00 ppm** / W01 **−53.88 ppm**（仅披露 NOT USED） |
| **★Step 7.7A LTA 分车型交通量（入场审计）** | ✅ **完成审计，判 `VEHICLE_TYPE_VOLUME_UNAVAILABLE` / `COMPOSITION_EXPLAINS_GLOBAL_LEVEL_NOT_SPATIAL_PATTERN`（零仿真；6/6 校验）**：`reports/external_validation_7_7/`（8 文件）。**★Q1**：本地与开放数据**均无**断面级分车型交通量（`TrafficFlow_Data.json` 仅总量 10 字段；DataMall 无分类计数端点；`data.gov.sg` 仅全国年度车队构成）。**★Q2 零成本先验**：Census T104 方式构成 vs 7.6C/H 空间残差 ⇒ region r=**−0.3600** / PA r=**+0.2533**（R²=**0.0641**），构成极差仅为残差极差的 **1/3.83 ~ 1/5.66** ⇒ **车型构成解释总体量级（0.6825 ↔ 0.6830，差 0.07%）但不解释空间分布**。**★三方向一致**：`dR/df≈0`（7.6F-1）、`dR/dλ≈0`（7.6G）、`dR/d构成≈0`（7.7A）。**★下一步**：严格版挂起（须 LTA 申请，见 `STEP7_7A_EXTERNAL_DATA_REQUEST.md`）；建议先推 **7.7C（空间残差归因，零外部依赖）**，同步准备 **7.7B（HTS 出发时刻）**。 |
| **★Step 7.7C-0 空间残差归因基线审计** | ✅ **完成，判 `RESIDUAL_LOCALIZED_TO_PA_LOCATION`（零仿真只读；14/14 校验；173.8 s）**：`reports/spatial_residual_7_7c0/`（19 文件）。**★六维**：OD 供需（ρ(A/P)=−0.70，**EAST 反例**）/ 方向性（跨 f/λ **8/8 稳定**）/ 道路等级（**排除**，motorway 0.9922）/ twin 拓扑（`has_reciprocal_pair` η²_excess **0.1423**）/ 长度归一化（**反而扩大 8.61 pp**）/ PA 梯度（outflow ρ=−0.40）。**★核心**：`radial×reciprocal` 交叉表 ⇒ `radial_in\|recip=False` **0.9915≈1.000**，twin 与方向性两机制**独立可加** |
| **★Step 7.7C-1 时段实现敏感性（零仿真解析上界）** | ✅ **完成，判 `TEMPORAL_SPATIAL_SENSITIVITY_FAIL_DEFER_HTS`（零仿真；7/7 校验；ratio 0.1104）**：`reports/spatial_temporal_sensitivity_7_7c1/`（8 文件）。**★关键修正**：初版全局标量乘子 ⇒ 结构恒不变（退化）⇒ 改**断面级** `share_8_9(s)`。**★7 profile**（含 P4 结构镜像 / P5–P6 日级 p10/p90 可行带）。**★命名组**：EAST/NE/`radial_in` 位移上界 **1–4 pp** vs 残差 **30–34 pp** ⇒ ratio ≤ **0.118**。**region/radial 排序全 profile 保持**；`radial_in`\|`recip=False` **0.9915** 不变。⛔ 详见 §2.43 |
| **★Step 7.7D 空间残差归因收口（零仿真收口审计）** | ✅ **完成，判 `SPATIAL_RESIDUAL_ATTRIBUTION_CLOSED_WITH_UNRESOLVED_STRUCTURAL_LAYER`（硬门 7/7 + 软门 2/2 PASS）**：`reports/spatial_residual_closure_7_7d/`（3 文件 + 证据 manifest）。**★G1–G9 十门**：W01 锚点 / C0↔W01（tol 1e-12）/ f·λ 稳定性（span 1.85 / 3.23 pp）/ `radial×reciprocal` 闭环（in|False 0.9915）/ temporal 上界 0.1104 / 构成排除 6/6 / 排除层 `eta2_excess` ≤ .001 / 剩余结构层明文。**★收口三类**：已解释 f·λ·构成；已排除 road_class·section aggregation·observation semantics·temporal realization·scalar demand·λ；未解释 PA/OD allocation·twin·directionality（§2.44）。**⛔ 不再为追 HRS8-9 聚合拟合跑 demand/λ grid 或 HTS MATSim 标定。** |
| **★Step 7.8 Final Model Freeze（最终模型冻结）** | ✅ **完成，判 `FINAL_MODEL_FROZEN_AND_REPRODUCIBLE`（零仿真定版；硬门 23/23）：`reports/final_model_7_8/`（9 件，含 6 件正式产品 + `STEP7_8_REPORT.md`/`f_integrity_checks.csv`/`step7_8_summary.json`）。**★版本线正式定格**：`7.3 crosswalk → 7.4 capacity/sampling → 7.6E route-choice → 7.6F demand → 7.6G λ 边界 → 7.6H 独立验证 → 7.7A 车型排除 → 7.7C-0/1 → 7.7D 收口 → **`Singapore_OD_MATSim_Final_v1.0`** → **STOP**`。**★模型身份**（`FINAL_MODEL_MANIFEST.json`）：`f_work=1.180222` / `lambda_ref=0.075`（⛔ 非最优）/ `scale=2.29897` / `f_cap=1.0` / `route_choice=R01_rc_min` / `sim_agents=236044` / `crosswalk=7.3.6A` / `calibration_target=0.8589732` / `validation=W01` / `spatial_residual_status=UNRESOLVED_STRUCTURAL_LAYER`。**★7.8D 空间残差边界保留不藏**（`FINAL_SPATIAL_RESIDUAL_BOUNDARY.csv`，55 行）。**★#168 门 23/23 全过**，含 **G22 = 全部 14 件冻结输入跑前后 mtime+sha256 逐位未变**（read-only 硬证据）与 **G21 = 6 件产品落盘**。**★新硬约束**：7.8 之后任何修改 `输入与算法锁` 条目 ⇒ **新版本 v1.1**，⛔ 不得就地改 v1.0；**后续 = 7.9 Structural Repair（新研究问题）**，⛔ 非「把 0.9993 调到 1.00」。 |
| **★`F-2 Q4-R1-R1`（nearest-single-link 局部捕获）** | 🔒 **正式 READY 冻结验收节点（用户裁定 2026-09-28）：`25/25` / `EXIT=0` / `CLOSURE=OK` / `converged=True; it=4`**；prereg `82a03eb8…` / 脚本 `1cbeb201…`；**4 类 × 109 × 3 半径 = 1,308 格**；**⛔ `nearest-single-link` 选择规则本身不得再改**；`Q4-R1` 线**已关闭** |
| **★技术链（更新，2026-09-28）** | `F2 v2 → v2.1-R2（Q2）→ Q4-R1-R1（Q4 nearest capture）→ 7.9G-0（`service` 延误 R0）→ 7.9G-1（端点/接入就地吸收）→ ★7.9G-2（四面口径统一，**OPEN / prereg 已冻结**）`；**下一步 = 分析脚本 → 25 门 → 负例 → 独立复核 → READY/CLOSED → LTA 分车型 / HTS 出发时刻**。⛔ 不修改 `Singapore_OD_MATSim_Final_v1.0` |
| **★`7.9G-0`（service 延误机制 R0）** | ✅ **完成（2026-09-28）**：判 Q1 `CAPACITY_CONSTRAINT_NOT_DOMINANT` / Q2 `CALIBER_FRAGILE` / Q3 `SERVICE_PARAMS_DERIVED`；**硬门 25/25 / EXIT=0 / `CLOSURE=OK` / `converged=True; it=4`**；prereg `2db351c8…` / 脚本 `61cfe26a…`。**只审计、不改模型**（⛔ 未碰 v1.0 与 Q4-R1-R1 产物、⛔ 未改 `service` 400 / 端点吸附）；**v1.0 仍为唯一冻结模型、不产生 v1.1** |
| **★`7.9G-1`（端点/接入就地吸收 R0）** | ✅ **完成（2026-09-28）**：判 A1 `PROPORTIONAL_TO_MILEAGE` / A2 `ENDPOINT_LOCALIZED` / A3 `NOT_MAINLINE_QUEUE` / A4 `NEITHER_BOUND` / A5 `NEGLIGIBLE` / A6 `ENDPOINT_ABSORPTION_DOMINANT`；**硬门 25/25 / EXIT=0 / `CLOSURE=OK` / `converged=True; it=3`**；prereg `4e7ffa3c…`。**机制 = `service` 延误集中在承载 OD 端点的 10,156 条微短链上（`service` 内 75.6%、逐车 28.7×）**；**只审计、不改模型**（⛔ 未碰 v1.0 与 Q4-R1-R1 产物、⛔ 未改 `service` 400 / 端点吸附）；**v1.0 仍为唯一冻结模型、不产生 v1.1** |
| **★`7.9G-2`（四面口径统一）** | ✅ **READY（2026-09-29）**：prereg `reports/caliber_harmonization_7_9g2/PREREG_7_9G2.md`（**22,238 B** / sha `6df55c42…`）；脚本 `scripts/od/audit_caliber_harmonization_7_9g2.py`（**73,426 B**）。**判 Q1 `DENOMINATOR_SPLIT` / Q2 `EXPOSURE_IMPACT_DECOUPLED` / Q3 `CONCENTRATION_ATTENUATED` / Q4 `FOUR_FACE_PARALLEL_REPORTING`**（硬门 **25/25**、EXIT=0、`CLOSURE=OK`、`it=3`；独立复核 **90/90**；负例 **11/11** + `S1 fired=False` + **3/3 BLOCKED**）。**✅ 只解决"怎么统计、怎么表达"**，⛔ 未重开 G-1 机制结论（未重判 `A1–A6`、未提新假说）。**锁 5 事**：统一分母栈 `D0 = ALL ⊃ D1 = SVC ⊃ D2 = EP_SVC`／宇宙必须声明（默认 `U_loaded`，`U_any` 带 `_any` 后缀）／暴露（count/km/vol）≠ 影响（time）／不合成总分／集中度用覆盖率分数 `f_t`（⛔ **Gini 禁用**、⛔ 常数 `k` 禁用）。**★实测**：四面 EP_SVC｜D0 = time **71.3681%** / count **3.1560%** / distance **3.9220%** / volume **0.4215%**（极差 **70.95 pp**）；`SVC_any/ALL_loaded km = 1.709605`（170.96%）；`R_50 = 19.803755`。输入 **5 件**（不含 `plans`/`events`）+ 对照 **8 件**；**25 门** / **11 负例 + 1 no-op 自检** / **3 BLOCKED** / **16 产物**。⛔ 未改 v1.0、未回写 G-0/G-1。 |

---

## 7. 变更记录

| 日期 | 变更 |
|---|---|
| 2026-09-30 | **★Step 7.9I-O1 —— B2 车行道对（carriageway pair）层（恢复入口 O1；零仿真只读；20.7 s + 14.1 s + 13.2 s）→ 判 `CARRIAGEWAY_PAIR_AUDIT_READY` + `PAIR_CANDIDATE_PROBE_READY` + `OPPOSITE_LABEL_CONTROL_READY`（三脚本 `n_fail = 0`；9/9 + 5/5 + 8/8 = **22 门**；负例 4/4）** —— 用户裁定「**暂停推进，先冻结收口**」并把阶段标记为 **`7.9I_FROZEN_CLOSED → READY(O1)`**，同时给出 **7 条跨阶段锚点 A1–A7**（已录入 `CLOSURE_7_9I.md §7`；核心 = ① `0.434977` **不进 v1.1**；② `Sim/Obs≈0.766` **只在靶场观测域解释**，不再读作全网需求不足；③ **1:K 尺度错配已实证**，⛔ 不得用 `sum/median/K` 偷换物理测量单元；④ 剩余低载 = **映射链 + 对象定义 + 平行/对层结构**，非单纯「没车」；⑤ KPE/ECP 极端数字已回收，**`r_mixed` 才是设施对象比较依据**；⑥ **方向映射错误已被 `152/152 同向` 排除**，`B2` 改从「对层建模」查；⑦ **v1.0 全程冻结，未产生 v1.1**）。**问题**：**LTA 观测的「一个方向断面」与 MATSim 中由独立节点串表达的另一方向车行道，是什么对应关系？** 预注册 `PREREG_7_9I_O1.md`（运行前冻结；**`G-O1-5` 运行前修订**：原「链内每步方位一致」因 `E_opp` 已筛方位而**恒真** ⇒ 退化判据，改为**拓扑有向路径**判据，实测 `directed_path` **46** / `sum` **11**）。**方法**：`E_opp(s)` = 100 m 内 `MAJOR` + 方位差 `~(bear_s+180°) < 30°` + 排除匹配边，**与 B(b) 的唯一差别 = 去掉 `flow > 0`**（刻意口径扩展）；链分量按 A1 规则取代表值（有向路径 `median` / 否则 `sum`）。**★主引擎**：`Q0_TWIN_PAIR` **10 节/Σobs 18,531.5**、**`Q1_SEPARATE_CARRIAGEWAY` **26 节/43,303.5****、`Q2_NO_OPPOSITE_OBJECT` 2 节/215.5 ⇒ **`B2` 22 节 = Q1 **19** / Q0 3 / Q2 0 = **86.4% 对向车行道为「独立节点串」****（`B(b)-P` 机制被**拓扑证实**）；靶场 576 普查 `PAIR_CONSISTENT` **32.03%**；门 9/9（`G-O1-2` 逐位全等 **Σ139=139**；`G-O1-7` `Σ|E_opp|=159` = 有流 139 + 无流 20）。**★后验 ①**：`r_pair` 中位 **R-sum 2.1512 / R-max **1.8677（带内 [0.5,2]）** / R-med 1.2183**；带内 Σobs 占比 0.3353 / **0.3963** / 0.3494；**`ΣK_pair=57`**；`Σflow_same **47,745.0**` vs `Σflow_opp **254,771.9**`（**5.34×**）；`corr(log obs, log r_pair)=0.0535` ⇒ 尾部**非**低 obs 分母伪影。**★★后验 ②（决定性）**：`B2` 中 **`L1_OPP_LOADED_OK` 15 节 / Σobs 28,918.5 / **75.51%**** —— **对向断面在冻结 canonical 下令 `ratio_median ∈ [0.5,2]`，本侧 `sim_median_xS` 精确为 0**（典型 **46894 → 对向 46009 距 26.4 m、`ratio_median` 1.3168、本侧 0**）；`L2_OPP_ALSO_LOW` 6 节/9,297.0/**24.27%**；`L3` 1 节/84.0/0.22%；全 38 节 `L1` 18/32,181/**51.86%**（严格 `R≤100` 仅 **10 节/30.77%**）；`G-O1Q-5` 双向观测对称中位 **1.371**。**★裁定：`B2` 的 75.51% 属「路网建模对象层面」（一侧被加载、另一侧对象全零），24.27% 才回到需求/路径域。** **★暴露面**：`L1` 的 51.86% 依赖 **300 m** 搜索半径，保守读法 **30.77%**；`E_opp` 非真值对应表。**★缺陷登记**：`G-O1-5` 运行前修订；**`G-O1Q-4` v1 实现与判据文字不符（`0/19`）⇒ 实现缺陷非科学结论，v2 `25/33`**；`G-O1Q-7` 量词过强 ⇒ 改构造性恒等核验；`r_pair` 与 `r_par_sum_opp` 口径不同源。**★下一步（待裁定）**：**`O1-续`** 对 `L1` 15 节做「车行道对账卡」（单侧 way 数量与标签 / OSM `oneway` / 与 `U_UNIT_MISMATCH` 求交），**仍零仿真**；O2 须用户显式裁定解除底线。⛔ 不改 v1.0、不重跑 MATSim、不产生 v1.1；`changed = 0`。 |
| 2026-09-29 | **★Step 7.9I 阶段冻结收口（CLOSURE）→ 判 `7.9I_FROZEN_CLOSED`** —— 用户裁定「**暂停推进，先冻结收口**」；新建档案 `reports/corridor_scale_audit_7_9i/CLOSURE_7_9I.md`（6 节：冻结声明 / 交付清单 / C1–C9 / R1–R5 / O1–O5 / 复现与恢复入口）。**全链完整性审计：7 脚本 × 6 判决 × 70/70 门 / `n_fail=0`**（20+12+18+8+6+6）。**补齐 `_run_7_9ibbp.log`（原 5/6 → 6/6，全链日志完整）**。**★复现性校验**：重跑 `audit_bb_direction_probe_7_9ibbp.py` ⇒ summary JSON 除 `elapsed_s`（25.5 s→11.0 s 热缓存）外**逐位相同 = True**、CSV **逐位相同 OK**。**良性重复登记（不修改）**：A2/A1/Bb 的 `*_summary_*.json` 与 `_*_audit_*.json` **md5 全等**（`6f357f49…`/`6b65888e…`/`86e21605…`）⇒ 同一 dict 双命名落盘。**★冻结结论 C1–C9**：①「sim 大 5 倍」= 计数基数错配（`ratio_simobs` **5.2818** / `K_pooled` **5.5434** ⇒ 归一 **0.953**）；②覆盖率不得外推（匹配边担全网高峰 **6.64%**、严格 1:1 **10.42%**）；③真缺载收敛 **3 条走廊**（`norm<0.5` 19 条 / obs **23.08%**，前 3 担 **22.42%**）；④A2：KPE/ECP「8 倍缺载」**不成立** ⇒ `r_mixed` **0.385/0.388/0.465**；⑤`U_UNIT_MISMATCH`：KPE 隧道 **16/19 节 `vc_max>1`**（最高 **3.569×**，剩余偏差 **92.6%** 归此项）；⑥A1 杠杆 = **候选对象选取**（`r_chain(P1)` **0.5556**，8.4×→**1.8×**）；⑦M1 主因 = **链缺陷**（`X1` **60 节 / obs 69.16%**）；⑧B(b) 主项 = `B2` **22 节 / 61.72%**，**非**平行边竞争；⑨B(b)-P **152/152 同向、0 反向** ⇒ **方向性对象不一致**。**未解项 O1–O5**（O1 `B2` 车行道对层 / O2 `SIGNAL_MECHANISM_ABSENT` / O3 LTA 分车型·HTS / O4 `B3` 6 节 / O5 `X0` 2 节）。**★恢复入口**：尺度已理清 ⇒ 优先序 **O1 → O3 → O2**（O2 须用户显式裁定解除底线）。⛔ 不改 v1.0、不重跑 MATSim、不产生 v1.1；`changed = 0`。 |
| 2026-09-29 | **★Step 7.9I-A2 / A1 / B(b) 「观测对象 ↔ MATSim 对象」三刀闭环（Dynamic Realism Audit ⑤⑥⑦；零仿真只读；41.6 s + 20.3 s + 19.7 s + 25.5 s；⛔ 不改 v1.0、不重跑 MATSim、不产生 v1.1）→ 判 `KPE_ECP_OBJECT_AUDIT_READY` + `CHAIN_REAGGREGATION_READY` + `ZERO_FLOW_PARALLEL_LEDGER_READY` + `BB_DIRECTION_PROBE_READY`（四脚本 `n_fail = 0`；18/18 + 8/8 + 6/6 + 6/6 门；负例 4/4 × 4）** —— 用户裁定**把「模型不堵」与「评价不对」拆开**，按 **(1) KPE/ECP 实体核验 → (2) 60 节链重聚合 → (3) 38 节零流量平行边记账** 顺序在**零仿真域**收干净证据链；**★底线：A1/A2/B 未把「观测对象 ↔ MATSim 对象」尺度关系理清前，⛔ 不再调整 v1.0 交通动力学参数**。预注册运行前冻结（`PREREG_7_9I_{A2,A1,Bb}.md`）；脚本 `audit_kpe_ecp_object_7_9ia2.py` / `audit_chain_reaggregation_7_9ia1.py` / `audit_zero_flow_ledger_7_9ibb.py` / `audit_bb_direction_probe_7_9ibbp.py`。**★A2（69 张实体卡）**：`norm = ratio_simobs/K_c` 的**隐含前提「K 条边承载同一股车流」被证伪**；**核心判据 `vc_max = obs_8_9 / max_e cap_eff(e)`** ⇒ **KPE 隧道 16/19 节 `vc_max > 1`**（obs 中位 **12,119** > 最大单边容量 **9,500**；最高 `20,342/5,700 = 3.569×`）⇒ **观测单元 ≠ 仿真单元**；**半径设施重建** matched-only **0.417** → 50 m **0.657** → 100 m **1.439** → 150 m **2.897** ⇒ **crosswalk 只选中低流量子集**；分类（按 Σobs）：KPE 隧道 `U_UNIT_MISMATCH` **92.64%** / ECP `C_CHAIN` **49.88%** + `P_PARALLEL` 38.37% + `S_SLIP_GEOM` 11.74%（**无** `U_UNIT_MISMATCH`，78% 匹配链落 `motorway_link`）/ KPE `U_UNIT_MISMATCH` 58.91% ⇒ **★7.9I-A 缺载倍数必须修正**：`norm` 与设施级口径差 **253%/500%/434%**（远超 15% 门槛）⇒ KPE隧道/ECP/KPE 从 8.5×/7.6×/8.4× 收敛到 **`r_mixed` 2.6×/2.6×/2.2×**；**★口径记法披露**：`n_edge_sec`（逐断面求和，ECP **289**）vs `n_edge_dedup`（去重，ECP **283**，15 行 `shared_section_count=2`）两者都正确 ⇒ 门**同时断言两者并携带实测值**（阈值未改）。**★A1（60 张链卡）**：口径 = 候选集内**弱连通分量划分**，有向**路径** ⇒ `median`/`min(cap)`，**非路径** ⇒ `sum`/`sum(cap)`，`sim_chain = SCALE × Σ_C rep(C)`（链内不重复计数、跨链可加）；四口径 pooled `r_med` **0.1187**（8.4×）/ `r_sum` **0.2871**（3.5×）/ **`r_chain(P0)` 0.1881**（5.3×）/ **`r_chain(P1)` 0.5556**（**1.8×**，重建候选池）；分类 P0 `C_LOW` **100%** → P1 `C_OK` **17.82%** + `C_HIGH` 10.00% + `C_LOW` **72.18%**；**★结论 = 链重聚合本身价值有限，真正的杠杆是「候选对象选取」不是统计量**；走廊：KPE 隧道 17 节/200,410（61.8%）、**AYE 10 节 `r_chain` 中位 0.000**、**TPE 3 节 `r_chain_p1` 中位 5.305 ⇒ P1 是上界非无偏估计**；**★判据退化披露**：原 `G-A1-7` 实测 median rel diff **0.0056**（冻结匹配集内路径分量代表值 ≡ canonical `median`，**构造性恒等** ⇒ 无信息量）⇒ ⛔ 不静默改阈值，记入 `degenerate_criteria`，有效对比改为 **`G-A1-7'`（P1 口径，实测 1.070，标签 `EXPLORATORY_POST_HOC`）**。**★B(b)（38 张记账卡 + 38 张方向卡）**：目标 38 节 / Σobs **62,050.5**（`RoadCat` = `CATA` 22 / **`SLIP_ROAD` 16 = 42%**；`n_matched` min 1 / 中位 3 / max 16 ⇒ **全部匹配成功但匹配边流量精确为 0**）；分类 **`B2_OPPOSITE_ONLY` 22 节 / Σobs 61.72%**、`B1_SAME_DIR_PARALLEL` 10 / 20.73%、`B3_NO_PARALLEL_FLOW` 6 / 17.55%；**★★38 节共 152 条匹配边方向一致性 = 152/152 同向、0 反向**（`d_match_max` 中位 1.8°/5.1°/2.9°）⇒ **「映射选错方向」假设被否定**；**`B2` 同向有流边合计仅 7 条**（`B1` 41 条）而**反向 83 条** ⇒ **`B2` 不是「同向平行边抢流量」**；**`B2` 反向有流边仅 1/22 节存在同节点对反向孪生** ⇒ 该设施被建模为**单向 way**（对向车行道以**独立节点串**另建）⇒ **流量确在「对向车行道」上，但那是网络的另一个对象** ⇒ **观测对象与仿真对象在「方向」维度上不一致**；走廊集中度 **AYE 16 节/37,520.0 + PIE 7 节/15,014.5 = 23 节/52,534.5（84.7% Σobs）**，两走廊 `r_par_same` 中位 **0.000**；**★口径陷阱（新纪律）**：`lta_section_geometry()` 的 `mx/my` 是**局部等距平面米**（`lon×111320·cos(lat0)`，≈1.15e7），**与全网图 SVY21 不同源** ⇒ ⛔ 绝不能与 `Graph.ex/ey` 或 `SEC_GEO_7_6C.mid_x/mid_y` 做距离运算（首版探针混用 ⇒ 距离恒 ≈1.15e7 m ⇒ `n_same = n_opp = 0` **全零伪影**）；A2/A1/Bb 三引擎**均正确使用 `SEC_GEO_7_6C`**，已加防御性文档字符串 + 新增 `G-P0` 坐标同源门。**★阶段判决（本轮冻结）**：**当前主要问题不能继续归因于采样容量折减（7.9A-1 已否定为主因），也不能直接归因于 MATSim 全网需求不足（7.9H：缺口是「改道」非「少跑」，全网 `Σflow` −4.69% vs 匹配边 −24.05%，差 7.2×）。现有证据表明，评价域存在显著的 1:K 映射尺度错配；在消除该尺度效应后，仍存在少数高影响快速路断面的真实低载问题，其主要表现为映射链断裂、平行替代路径及特殊道路设施对象不一致。** **★下一步（待裁定）**：`B2` 需「**车行道对（carriageway pair）**」层（区分「同节点对双向 way」与「独立节点串单向 way」），**仍属零仿真域**；其后才重谈 **7.9J / signals / trafficDynamics**。 |
| 2026-09-29 | **★Step 7.9I 观测域尺度 + 局部可达性诊断完成（Dynamic Realism Audit ③④）→ 判 `CORRIDOR_SCALE_AUDIT_READY` + `M1_ACCESSIBILITY_AUDIT_READY`（零仿真只读；38.4 s + 46.3 s；⛔ 不改 v1.0、不重跑 MATSim、不产生 v1.1）** —— 用户裁定**暂停 G-3/G-4 与 C（信号）/D（动力学）**，只做 **(a) 靶场比较口径修正** + **(b) M1 可达性归因**，两者均零仿真；判据运行前冻结于 `reports/corridor_scale_audit_7_9i/PREREG_7_9I.md`。**★7.9I-A（73 条走廊）**：三口径并报；**★★核心 = 1:K 计数机制** —— 1 个 LTA 断面典型对应 **K = 5.5434** 条 MATSim 有向边（走廊 `K_c` ∈ 3.0–14.4），池化 `ratio_simobs` **5.2818** ⇒ `5.2818/5.5434 = 0.953` 量级自洽 ⇒ **「sim 比 obs 大 5 倍」主要是计数基数错配**；容量加权 Σ 口径残差 v1.0 **+39.46 pp** / A-1 **+61.35 pp**，⚠ 但该值**主要是 1:K 所致**（sim 计 K 次 / obs 计 1 次 / 容量分母也 K 折），且代表值口径 `−0.0083 pp` **与 canonical `median` 代数同源 ⇒ 不构成独立证据**；**★★独立证据 = 去尺度残差 `ratio_simobs/K_c`**：`norm<0.5` 共 **19 条走廊 / 担 `Σobs` 23.08%**，**前 3 条(KPE 隧道 0.117 / ECP 0.132 / KPE 0.119)担 22.42%**，而 **PIE 1.129 / SLE 1.104 / CTE 1.132 / BKE 0.953** ⇒ 完全可由 1:K 解释 ⇒ **「快速路被低估」分裂成两半：多数 = 计数基数错配；只有 KPE 隧道/ECP/KPE = 真实缺载（缺 7.6–8.5×）**。**★7.9I-B（133 个 M1）**：图 421,406 节点 / 693,575 边；**⚠ 冻结判据缺陷披露** —— 实测 `M1-C 60 节(obs 69.2%)` / `M1-E 73 节` / `M1-A=M1-B=M1-D=0`，因 **133 个 M1 全部落在 `motorway`/`motorway_link`** ⇒ `M1-E` 命中 133/133、**A/B 结构性不可达**；**另三项退化诊断**：全网**单一弱连通分量**（421,406/421,406）⇒ `in_giant` 恒真、`dangling` 恒 0、`dir_diff_median` 最大 23.8°（阈值 30°）⇒ `M1-D` 恒 0；**后验修订分类（`EXPLORATORY_POST_HOC`，阈值一律未改）**：`X1 链缺陷 60 节 / 69.2%`、`X2 匝道或结构 40 / 11.4%`、`X3 平行旁路 22 / 12.4%`、`X4 孤立 9 / 6.2%`、**`X0 未解释 2 / 0.9%`**；**标志位**：`f_chain_defect` 60、**`f_bypass_ge_half_obs` 105(78.9%)**、`f_hop_ge5` 59、**`f_no_flow_in_matched` 38（`Σobs` 62,051 = 13.2%）**；**走廊集中度**：KPE 隧道 18 节 `Σobs` 220,473（**17 多分量 / 0 零流量 ⇒ 车在跑但映射对象错**）、ECP 27/74,583（13 节 ≥5 跳）、PIE 28/63,523、**AYE 21/47,734（16 零流量）**。**★交叉印证**：两个尺度独立指向同一机制 —— **观测值没被映射到"同一股车流"上，而非"车没跑"**。**门/负例**：I-A **6/6 fired**、I-B **4/4 fired**，两脚本 `n_fail = 0`。**★新纪律**：①多边映射**必报计数基数 `K_c`**（否则 1:K 计数错配被误读为物理缺口）；②**「口径修正」不得充当独立证据**（与 canonical 代数同源须显式声明）；③**退化诊断必须披露**（单一连通分量下 `in_giant`/`dangling` 恒真恒 0，⛔ 不得当作"通过"）；④**冻结判据无区分度 = 判据缺陷**（须后验修订并加 `EXPLORATORY_POST_HOC` 标签，⛔ 不得静默改阈值）；⑤**负例必须是非同构扰动**（索引整体位移/整体反向都是同构 ⇒ 必 `fired=False`；本步两次踩坑已修）。**★下一刀（均零仿真）**：(a1) 60 个链缺陷断面改为**沿走廊拓扑取连续有向链**；(a2) KPE 隧道/ECP 结构设施实体核验；(b) 38 个零流量断面的平行边一对一记账；(a1)(a2) 完成后才重谈 7.9J/signals。 |
| 2026-09-29 | **★Step 7.9H 动态真实性诊断完成（Dynamic Realism Audit ②）→ 判 `SIGNAL_MECHANISM_ABSENT` + 缺口成因锁定为「评价靶场尺度错配」而非需求/容量（零仿真只读；47 s + 81 s + 20.5 s；⛔ 不改 v1.0、不重跑 MATSim、不产生 v1.1）** —— **★起因含一处关键更正**：用户提议的「单因素容量一致性实验」（`flowCapacityFactor`/`storageCapacityFactor` `1.0 → 0.434977`，其余冻结）**已由 7.9A-1 跑完并出判决**；**基线须更正**：`Sim/Obs` v1.0 = **0.9993347697**（不是 0.766），**0.7664760994 就是 A-1 的结果**。**★用户 4 条验收标准逐条实测**：① `Sim/Obs` 回升 → **0.9993348 → 0.7664761（↓0.2329，方向相反）✗**；② 连续拥堵走廊 → 严格档 `vc≥0.85 且 sr<0.70` 0 → **2 条 / 1.141 km** △；③ 空间残差方向 → 高估桶 154 → **65 节**（担 obs 25.16% → **5.69%**）、低估桶 210 → 179（38.58% → **35.17%**）△半改善；④ 无全网锁死 → `stuck=0`、dep=arr=236,044、真实拥堵只担全网 **0.423%** 流量 **✓**。**★H1 缺口去向**：全网 40,008,184 → 38,130,232（**−4.69%**）vs **被 crosswalk 映射的 3,037 条边 2,655,572 → 2,016,818（−24.05%）**、未映射 690,538 边 **−3.32%** ⇒ **缺口主要是「车改道离开被观测边」**（匹配边相对跌幅 = 其余网络的 **7.2 倍**）；走廊间重分配实证 **ECP +83.2% / KPE 隧道 +17.7%** vs **PIE −34.5% / CTE −37.0% / SLE −26.7%**。**★断面分桶（576 节）**：低 `sim/obs<0.5` **210 节担 38.58% obs → 179 节担 35.17%**、≈ `0.5–1.5` 212 → **332**、高 `>1.5` **154 节担 25.16% → 65 节担 5.69%** ⇒ **v1.0 的 0.9993 = 「154 节高估 ↔ 210 节低估」大额正负抵消**。**★「sim 低 obs 高」几乎全是快速路**：**KPE 隧道 19 节 `Σobs 230,268` / `Σsim×S 22,239`（0.097）**、ECP 0.227、PIE 0.124、**AYE 0.092**、TPE 0.201、KJE 0.298、BKE 0.118；成因二分 **M1 真·低载 133 节**（中位 `sum/obs = 0.538`）/ **M2 median 塌陷 77 节**；`sim_median ≡ 0` **53 节**（`sum` 亦 0 者 **37 节** / 纯 M2 **9 节** / 叠加 **7 节**）；**★容量不是约束**（210 节中仅 **4 节** `cap_eff_sum < obs`，中位 `cap_eff_sum = 15,200 veh/h`）。**★H2 假设实测**：**(1)「1:1 最近边」被证否**（576 断面 → **3,037 条唯一匹配边**，min 1 / **max 31** / 中位 **4** / 均值 **5.54**，**严格 1:1 仅 60 节 = 10.42%**）；**(2) 聚合口径敏感性**（`median` **0.9993/0.7665**、`mean` 1.0074/0.7725、**`sum` 4.1616/3.1384**、`max` 1.1113/0.8589 ⇒ **"聚合函数选错"不成立**）；**(3) 覆盖率成立且严重**（匹配边 **159.7 km** / 全网 15,126.5 km 却只担 **6.64% / 5.29%** 高峰流量 ⇒ **靶场只覆盖 6.6%**）；**(4) 关键反证** —— 快速路整体**并不低载**（PIE 689 边担 **991,784 veh/h**、SLE 357,471、TPE 331,340、CTE 229,368、BKE 177,116、**AYE 136,381**）⇒ 真问题 = **「LTA 断面观测值 vs 4 条匹配边中位数」跨尺度比较 + MATSim 走廊内跨边重分配**。**★H3**：严格口径 v1.0 **13 条 / 0.96 km / 0.124%** → A-1 **91 条 / 8.74 km / 0.423%**，中位 `sr` 0.630 → **0.253**；走廊严格档 0 → **2 条 / 1.141 km**、宽松档 0 → **10 条 / 4.236 km**。**★H4 可视化重建（5 图，v1.0/A-1 双版）**：旧 `speed_ratio` 污染与正式口径**逐位吻合**（v1.0 载流 224,432 中 `<0.80` **117,168 = 52.21%**、其中 **99% 是 `LENGTH<50 m`**；过滤后仅 **1,174 = 4.70%**，≡ `n_slow_cut0`/`n_slow_cut50`）；新图 `fig_why_speedratio_fails_v10_A1`（2×2 证明"全红"是仪器问题）、`congestion_map_vc_5bin_v10_A1`（`0.85–1.00` 79 → **530**、`>1.00` 5 → **33**）、`congestion_map_delay_v10_A1`（**249 条 / 20.8 km / 1,497 veh·h → 998 条 / 88.4 km / 6,073 veh·h**）、`congestion_map_ttratio_major_v10_A1`、`congestion_corridors_v10_A1`（双层走廊）。**★正交未决两事**：① **`SIGNAL_MECHANISM_ABSENT`**（config 25 模块 0 命中 / 421,770 节点 694,226 链信号令牌全 0 / `org.matsim.contrib.signals` **不在 classpath**（`libs/` 164 jar 无）/ 恒绿桩 / `DefaultTurnAcceptanceLogic` 只判拓扑 / `NodeTransition` 无 `@StringSetter` 故 **XML 改不动**）⇒ 信号化类链路担 **94.23% 里程 / 56.32% 高峰流量**，真实进口道有效能力 ≈ 饱和流 × 绿信比(0.45–0.55) ⇒ **系统性高估约 2×，与 0.434977 独立且完全未处理**；② M1 真·低载（容量充足却不放车 ⇒ 指向路由分配/路网连通性/OD 空间分布）。**★下一刀候选**：(a) 靶场重标定（走廊级 Σ / 容量加权，**零仿真**）；(b) M1 连通性/可达性归因（**零仿真**）；(c) `matsim-signals` 或绿信比折减容量；(d) `7.9B trafficDynamics` 复评。**★新纪律**：**可视化指标必须报"被谁污染"**（按比率着色前必报过滤前后条数与里程）；**覆盖率必须先算**；**比值指标必须同报聚合函数**。**★新增脚本** `scripts/od/diagnose_gap_7_9h.py`（47 s）/ `build_congestion_maps_7_9h.py`（81 s）/ `audit_signal_mechanism_7_9d0.py`（20.5 s）**+ 产物** `reports/dynamic_realism_audit_7_9/`（`STEP7_9H_REPORT.md` 等 11 件 + 5 张 PNG）。**★冻结影响 = 无**（零仿真、v1.0 仍唯一冻结）。 |
| 2026-09-29 | **★Step 7.9A-1 采样一致性容量单因子动态实验完成（Dynamic Realism Audit ①）→ 判 `SAMPLING_CAPACITY_NETWORK_BREAKDOWN` × §7 情形 D（20 迭代仿真 226.99 min；零仿真评价 104 s；硬门 0 失败 / 记录项 6）** —— **起因**：领导者反馈「MATSim 动态状态不像真实城市交通、VIA 无拥堵」。**★第一手核实推翻第二嫌疑**：冻结 population 的 `home end_time` **早已分散**（07:00–08:59:59、07 时 **48.71%** / 08 时 **51.29%**、**7,200 个秒级取值**、中位 **08:01:27**、恰 08:00 仅 **44**）⇒ `6.3.3A` 早已固化、**2×2 退化为单因子**（C≡A、D≡B）⇒ 用户裁定只跑 A-1。**唯一变化** `flowCapacityFactor`/`storageCapacityFactor` `1.0 → **0.434977**`（= `1/SCALE`，由 `200,000/459,794` **独立推导**，⛔ 不由观测反演）。**★四指标**：① `N_cong`(`excess>0`) 7,985 → **15,083**（×1.889）；② `n(v/c≥1)` 82 → **501**（×6.110）、`sat_km` 1.1514 → **7.3379**（×6.373）、`max v/c` **首次越过 1**（1.001695）；③ 峰在途 36,176 → **63,706**（legHistogram 36,799 → **69,357**，×1.885）、峰时刻**后移 30 min**、06–12 窗内未到达 104 → **5,241**、`stuck`/全天未到达 **均 0**；④ `concentration_ratio` 3.377 → **3.942**（拥堵**向 7.3.6A 靶场聚集**）。**★★机制分解**（`scripts/od/decompose_simobs_7_9a1.py`，576/576 断面内连接）：`Σsim` **−23.30%**、**非均匀缩放**（**`L1/L0 = Σ\|Δ\|/\|ΣΔ\| = 1.4226`**；345 降 / 186 升 / 45 持平），`\|Δ\|` top-20 **全为高速且 v1.0 高估 2.0–4.9×**（CTE `44900` 2.32 → 0.80、SLE `47376` 1.99 → 0.83、PIE `46623` **4.93** → 3.19），逐断面 `sim/obs` 分布**向 1 压缩**（P75 1.539 → 1.185、P95 2.991 → 2.245）⇒ **§5 ① 四项全改善**（r 0.3452 → **0.4278**、WMAPE 0.7176 → **0.4774**、GEH 中位 26.09 → **15.89**、GEH<5 49 → 88）**而 `Sim/Obs` 跌破护栏**（0.9993 → **0.7665**，`POSITIVE_ONLY 0.8161` / `BEST_DIRECTION 0.7997` **三口径全跌破**）⇒ **§7 情形 D 原文「既有断面流量校准可能依赖了错误的容量尺度补偿」由实测直接坐实**。**★4 项实现/口径留痕（⛔ 未改预注册 `de15361a…`、⛔ 未改任何阈值）**：**`A03` 假门禁**（第 7 次同类复现；runner 跑完后**合法地**把 verdict 改写为 `A1_RUN_COMPLETE` ⇒ 原写死 `PREPARED*` 的判据必 FAIL 并把总判决误压成 `FAILED`）、**`A09` 判决分支是死代码**（`hard_fail` 收录全部 False 门 ⇒ 预注册 §10 的 `NETWORK_BREAKDOWN` **永不可达**；已按 §10 分离 `BREAKDOWN_GATES = (A09, A10b)`）、报告 §8 硬编码「≥ 0.85」（实测 0.7665 也照写"≥"⇒ 已改**按实测动态渲染**）、`onset` 3× 判据**交叉时刻陷阱**（v1.0 曲线平台化 ⇒ `t_onset = 09:20` ≠ 拥堵起点；⛔ `155 min` ≠ 拥堵总时长）。**★§11 提前解出**：`MODE = BASE_CAPACITY`（693,575/693,575 逐位相同）⇒ linkstats 的 `CAPACITY` **不随 `flowCapacityFactor` 缩放**。**★第三份备忘** `CALIBER_RESOLUTION_BREAKDOWN.md`（§10 判决**子义消歧**：本次触发**流量层崩解**（`Sim/Obs<0.85`），**非** `stuck`/`never_arrived` 的**网络崩解** ⇒ 读法按 §7 情形 D）+ 门 `A09d`。**★结论**：**容量按抽样比例收紧是「方向正确、但单独使用会过冲」的一刀** —— 它造出了 v1.0 从未有过的**真实拥堵波**，代价是把断面流量校准从 0.9993 打到 0.7665，而 **0.7665 的成因已查明是「削掉了高速上物理不可能的高估」**；**`0.434977` ⛔ 不得宣布为最终 / 最优容量**；**v1.0 仍为唯一冻结模型、不产生 v1.1**；⛔ 未改网络 / 容量 / 需求 / route-choice / 出发时刻。**下一步 = 待用户裁定**（容量扫描刻画 trade-off vs 信号绿信比**结构性折减**（信号机制零仿真审计判 `SIGNAL_MECHANISM_ABSENT`，不在 classpath）vs 7.9B `trafficDynamics` vs 高速高估归因）。 |
| 2026-09-29 | **Step 7.9G-2 「时间 / 数量 / 距离 / 体积」四面口径统一 READY → 判 Q1 `DENOMINATOR_SPLIT` / Q2 `EXPOSURE_IMPACT_DECOUPLED` / Q3 `CONCENTRATION_ATTENUATED` / Q4 `FOUR_FACE_PARALLEL_REPORTING`（零仿真只读；硬门 **25/25**、EXIT=0、`CLOSURE=OK`、`converged=True; it=3`、**47.8 s**；`noop_selfcheck_passed=True`）—— 7.9 第十四阶段，⛔ 只解决"怎么统计、怎么表达"，不重开 G-1 机制结论、不回灌 v1.0** —— **新增** `scripts/od/audit_caliber_harmonization_7_9g2.py`（**73,426 B**，1,396 行）+ **16+1 件产物**落 `reports/caliber_harmonization_7_9g2/`（prereg `6df55c42…` / 22,238 B、`STEP7_9G2_REPORT.md`、`g2_*` 14 件）。**★四面实测（EP_SVC ｜ D0，`U_loaded`）**：time **71.368133%** / count **3.155967%** / distance **3.922029%** / volume **0.421506%** ⇒ 极差 **RANGE_ep = 70.946627 pp** ≫ `AGREEMENT_BAND_PP = 5.0` ⇒ **四面不可合并为单一 headline**。**★宇宙撕裂**：`SVC_any km / ALL_loaded km = 1.709605`（**170.9605%**，被门 10 捕获并标注 `ILLEGAL_MIXED_UNIVERSE`）；`universe_spread_pp = 1.962541 > 0.5` ⇒ Q1 `SPLIT`。**★集中度（覆盖率分数）**：`R_50 = 19.803755` / `R_90 = 6.643841` / `R_99 = 1.032118` ⇒ 子集内部延误**相对更分散** ⇒ Q3 `ATTENUATED`（⛔ Gini 仅作描述：ALL 0.999541 / EP_SVC 0.998174）。**★三档强度 `s/veh`**：ALL **0.430002** → SVC **9.407303** → EP_SVC **72.806547**（**169.32×**）。**★★口径级技术发现（7 项，全部为实测驱动）**：**(1) 时间面「逐位一致」只有 `math.fsum` 路径可达** —— pandas/numpy 的**顺序求和**与 G-0/G-1 存储值差 **1 ulp**（D0 `9.095e-13` / D2 `4.547e-13`）；换 `fsum` 后 D0/D1/D2 三档全部 `atol=0` 命中。**(2) pandas 默认快速浮点解析丢 1 ulp** —— 对照物 `296.40227899999996` 被读成 `296.402279`；**产物回读同样中招**（`962.7150059999999` → `962.715006`，使门 15 出现**假失败**）⇒ 对照物与产物回读一律 `float_precision="round_trip"`。**(3) `D2 = (home ∪ work) ∩ service`，不是 home∪work 全集** —— 全集（22,359 条）会得 km `775.332372` / vol `1,148,087`（错）；`∩ service` 才逐位复现 G-1（n_any **10,156** / n_loaded **7,083** / km_any **296.402279** / vol **168,637** / delay **3,410.521558 h**）。**(4) G-0 与 G-1 面名不同**（裸名 `time` vs `time_delay_corr_h`）⇒ `FACE_G0_KEY` 必须双向映射，否则门 15 直接 `IndexError`。**(5) 空串经 `to_csv`/`read_csv` 往返变成 NaN** ⇒ 门 12 原文的「**非空**」必须显式 `isna()`，只做 `dropna()` 后的集合差会**漏检** `denom_scope` 置空（实测漏检 12 行）。**(6) pandas 3.0 `df.loc[len(df)] = {...}` 静默丢弃新列** ⇒ 负例 N10 首跑**空转**；列注入必须走 `list.append(dict)` 或直接列赋值。**(7) 门 09/12 须覆盖「全部 share 行载体」**（含 `denominator_audit`）才与 §6 原文「**每个** share 行」一致。**★独立复核** `scripts/od/_verify_g2.py`（**13,631 B**，**不导入被测脚本**，从 5 件原始输入重算）：**90/90 PASS**、`INDEPENDENT_REPRODUCTION_OK`（12 组四面逐位 / 24 组份额逐位 / 15 组 `f_t`·`R_t` 逐位 / 9 组强度 / 13 组 G-0·G-1 锚点 / closure·manifest 逐件 sha / 不自哈希 / 25 门）。**★负例套件** `scripts/od/_g2_negatives.py`（**12,712 B**，严格按 §8）：**11 真负例 11/11 `fired=True`**、**空负例 `S1` 正确 `fired=False`**（`q3_for` 写死真值 = no-op；套件把 `fired=False` 判失败）、**3 BLOCKED 3/3 `complete=True`**（各 25 行 checks + 6 件终态产物 + EXIT=1 + 状态 `…_BLOCKED`）；沙盒根 `reports/_g2_neg_root2/`。**★§8「期望触发门」预测偏差（实测 vs 预测，逐条留痕、未改任何判据）**：**N1** 期望 12/09 → 实测 **10**（`share_loaded(ALL_LOADED, time) = 1.059809514` = **105.98% > 100%**，被门 10 以**更强**失效信号捕获）；**N4** 期望 12/10 → 实测 **09**（`denominator_audit:2` 组合同键跨宇宙）；**N3** 期望 15/17 → 实测 **15**（+16）；**N2** 期望 15 → 实测 15（+16）；**N9** 期望 23 → 实测 23（+22）；**N5→20 / N6→19 / N7→12 / N8→10 / N10→17 / N11→25 逐条命中**。**★留痕结论**：§8 的「期望门」列是**设计期预测**，与冻结**判据**无关；其中 **门 17 的判据为「`face_role` 归属 + 影响类字段名」，结构上无法检测「把 `count` 值塞进 `time` 面」这类**值替换**攻击**（该类攻击由**门 15** 正确捕获）。**★冻结影响 = 无**（零仿真、冻结件 `changed=0`、G-0/G-1 两目录 `drift=[]`、不回写任何 G-0/G-1 产物、不产生 v1.1）；**下一节点 = LTA 分车型 / HTS 出发时刻**。 |
| 2026-09-28 | **Step 7.9G-2 「时间 / 数量 / 距离 / 体积」四面口径统一 OPEN → prereg 冻结**（**7.9 第十四阶段**；零仿真只读；⛔ 只解决"怎么统计、怎么表达"，不重开 G-1 机制结论）—— **新增** `reports/caliber_harmonization_7_9g2/PREREG_7_9G2.md`（**22,238 B**，sha256 `6df55c42…`，§1–§12；**冻结输入 5 件**（`pop`/`ls_final`/`ls_viz_ref`/`net_links_runtime`/`src_copy`，**不含 `plans`/`events`**，因 `EP_SVC` 定义已由 G-1 门 10 以 `contract = 1.000000` 过门）+ **只读对照 8 件**（G-0 4 + G-1 4）；**硬门 25**；**判决闭集 Q1–Q4**；**11 真负例 + 1 no-op 空负例自检 `S1` + 3 BLOCKED**；**必需输出 16 件**）。**★锁定 5 事**：①统一分母栈 `D0 = ALL ⊃ D1 = SVC ⊃ D2 = EP_SVC`；②**宇宙必须声明**（默认 `U_loaded`；`U_any` 须带 `_any` 后缀）；③**暴露 ≠ 影响**（`IMPACT = {time}`、`EXPOSURE = {count, distance, volume}`，配三档强度 `s/link`/`s/km`/`s/veh`）；④**不合成总分**（禁跨面加权/归一/求和）；⑤集中度用**覆盖率分数 `f_t = k_t / n_scope`**（`t ∈ {50,90,99}`）+ 与 `D0` 的倍率 `R_t`，`RATIO_CONC_MIN = 3.0`。**★阈值（预先约定，不得事后回调）**：`UNIVERSE_SPREAD_TOL_PP = 0.5` / `AGREEMENT_BAND_PP = 5.0` / `RATIO_CONC_MIN = 3.0`。**★零仿真侦察（第一手）**：**(a)** 宇宙撕裂可致 **>100%** 份额 —— `SVC_any` km = `ALL_loaded` km 的 **170.96%**；**(b)** 同一对象两个 distance share —— `g1_endpoint_service_split.csv` 的 `length_km = 296.402`（`U_any`，10,156 链）vs `U_loaded` 下 EP_SVC **203.385 km**（7,083 链）⇒ **5.716%** vs **3.922%**，差 **1.79 pp** > `0.5 pp`；**(c)** Gini **失效** —— `ΔGini(EP_SVC − ALL) = −0.0014`（0.998174 vs 0.999541），无区分度且符号反直觉 ⇒ 禁作判据；**(d)** 覆盖率分数有区分度且尺度无关 —— `f50` ALL **0.000036** → SVC **0.000112** → EP_SVC **0.000706**（**19.6×**）、`f90` 倍率 **6.65×** ⇒ 子集内部延误**相对更分散**；**(e)** 强度面 `s/veh` ALL **0.4300** / SVC **9.4073** / EP_SVC **72.8065**（**169.3×**）。**★四面实测（EP_SVC ｜ D0，`U_loaded`）**：time **71.3681%** / count **3.1560%** / distance **3.9220%** / volume **0.4215%**（极差 **70.95 pp**）。**★冻结影响 = 无**（零仿真、冻结件 `changed=0`、不回写 G-0/G-1、不产生 v1.1）；**下一节点 = 分析脚本 → 25 门 → 负例 → 独立复核 → READY/CLOSED，随后 LTA 分车型 / HTS 出发时刻**。 |
| 2026-09-28 | **Step 7.9G-1 端点/接入子系统「就地吸收」机制审计完成 → 判 A1 `PROPORTIONAL_TO_MILEAGE` / A2 `ENDPOINT_LOCALIZED` / A3 `NOT_MAINLINE_QUEUE` / A4 `NEITHER_BOUND` / A5 `NEGLIGIBLE` / A6 `ENDPOINT_ABSORPTION_DOMINANT`（零仿真只读；硬门 **25/25**、EXIT=0、`CLOSURE=OK`、`converged=True; it=3`）—— 7.9 第十三阶段，⛔ 只审计不改模型、不回灌 v1.0** —— **新增** `scripts/od/audit_endpoint_access_absorption_7_9g1.py` + 冻结 `reports/endpoint_access_absorption_7_9g1/PREREG_7_9G1.md`（**17,536 B**，sha256 `4e7ffa3c…`）⇒ **16 件产物**；运行 **340.8 s**。**★可证伪命题（用户裁定）**：`service` 延误是否主要表现为端点接入 / 局部循环 / 短链时间表达的**「就地吸收」**，而非道路容量约束产生的**排队**延误。**★A2 决定性**：端点 `service` **10,156** 条（296.4 km）担延误 **3,410.52 h = 全网 71.37% / `service` 内 75.64%**，却只占 `service` 流量 **9.77%** ⇒ 逐车 **72.81 s/veh vs 非端点 2.54 s/veh（28.7×）**；`f_pos` **0.088818** vs `w_ep` **0.756366** ⇒ **遍历位置效应被证伪、端点链归属成立**。**★A3**：邻接干道 `service` 仅担 **1.8736%** vs 内部 **92.4830%** ⇒ **非主线回溢**。**★A4**：`D` 集 422 条，`sat_share_D` **0.1394**、`cell_share_D` **0.4961** ⇒ 两者均 <0.50 ⇒ `NEITHER_BOUND`（**容量与储存微胞都不是单一绑定约束**）。**★A5**：`f_local` **0.001296**（306/236,044）⇒ `NEGLIGIBLE`（**局部循环支路被证伪**）。**★A6**：`s_end` **71.3681%** / `s_mid` **22.9884%** / `s_main` **1.8736%** ⇒ **端点就地吸收主导**。**★暴露四面（重申 `CALIBER_FRAGILE`）**：time **94.36** / count **27.81** / distance **18.56** / volume **4.31**（%）。**★events 逐车轨迹**：12 条 target 链 `n_enter≥1` 全齐（命中 24,293 事件）；`dwell_p50` **280–6,423 s** 而链长仅 **1.9–140.8 m**、`ff_s` **0.62–25.3 s** ⇒ 与「就地吸收／储存微胞耗尽」一致、与「道路容量排队」不一致。**★验证**：负例 **11/11** 全触发、BLOCKED **3/3** 完整节点、独立复核 `VERIFY_OK=True`（7 件冻结件未变 / prereg 恒等 / 独立 canonical 重算 / 独立端点抽样 40k / 独立契约抽样 40k / 25 门有序 / manifest 字节一致且不自含 / closure OK / 判决 ∈ 闭集）。**★新纪律 `R-G1-1…8`**：大 `.gz` 一律 `zlib.decompressobj(31)`（`gzip` 33 MB/s vs **348 MB/s**）／`bytes.split(b"<tag ")` 吃掉前缀 ⇒ 后续 regex 不得再含该前缀／缓存仅用于**不绕过被测函数**的负例（打 `scan_plans`/`events` 的必须关 `--cache`）／A 类判决须同报四面暴露／机制判决须「位置面 vs 延误面」分列／「就地吸收」须逐车口径复核／机制闭集必须含否定分支／⑧**负例必须"改变可观测结果"**——把变量写死为**真值**是 no-op 空负例，只证明"没抓到"而非"能抓到"；必须取**与规则相矛盾**的取值，且套件须把 `fired=False` 判为失败、不得静默通过。**本轮自查 4 处**（E1 `CONTRACT` 键错存成 link→权重致契约恒 `0/0/236044`，**门 10 自抓**；E2 同源 `split` 吃掉 `<person ` 前缀致 `pid` 恒空，改 `\A\s*id="…"` 后抽样 5000/5000=1.000000；E3 `events_trace` 性能 `gzip`→`zlib` + 仅命中目标链正则，666 s→331.8 s；**E4 负例设计缺陷**——N9 首跑把 `a4` 写死为**真值** `NEITHER_BOUND` ⇒ **空负例（no-op）**、不产生任何可观测变化、门 17 自然不触发 ⇒ 被套件自抓（`fired=False`）；改取**与规则相矛盾**的 `FLOW_CAPACITY_BOUND` 后门 17 FAIL、24/25、BLOCKED）。**★负例全套复跑（E4 修复后）落新沙盒根 `reports/_g1_neg_root_r2/`**——旧根单用例 >50 文件/轮 ⇒ `build()` 的 `rmtree` 撞 `SAFE_DELETE_BULK_CONFIRM_REQUIRED` 使全套用例**静默夭折**；修：`G1_NEG_ROOT` 参数化 + 对非新鲜目录**硬失败**（不静默）⇒ **复跑结果 N1–N11 全 `fired=True`（11/11，含 N9 现已真触发：`A4=FLOW_CAPACITY_BOUND`、门 17 FAIL、24/25、BLOCKED）、P1–P3 `complete=True`（3/3，各 25 行 / 6 件终态产物 / EXIT=1）、`ALL_EXPECTED_GATES_FIRED=True`、`PREFLIGHT_BLOCKED_NODE_COMPLETE=True`、EXIT=0**（7 min 45 s / 3 并发；N5 391 s、N11 290 s 为关缓存重算）。**★冻结影响 = 无**（零仿真、冻结件 `changed=0`、不产生 v1.1）。 |
| 2026-09-28 | **Step 7.9G-0 `service` 延误机制 R0 结构审计完成 → 判 Q1 `CAPACITY_CONSTRAINT_NOT_DOMINANT` / Q2 `CALIBER_FRAGILE` / Q3 `SERVICE_PARAMS_DERIVED`（零仿真只读；硬门 **25/25**、EXIT=0、`CLOSURE=OK`、`converged=True; it=4`）—— 7.9 第十二阶段，⛔ 只审计不改模型、不回灌 v1.0** —— **新增** `scripts/od/audit_service_delay_mechanism_7_9g0.py`（48,460 B，sha256 `61cfe26a…`）+ 冻结 `reports/service_delay_mechanism_7_9g0/PREREG_7_9G0.md`（14,221 B，sha256 `2db351c8…`）⇒ **15 件产物**。**★Q1**：已载流 `service` 62,407 条中 `v/c` 中位 **0.0225**、饱和仅 **74（0.1186%）**且只担 **13.95%** 延误 ⇒ **容量约束非主因**（判据 `sat_delay_share < 0.50`）；集中度 top-10 **62.17%** / top-100 **96.01%**。**★Q2**：`raw` **45.904%** vs `corr` **94.357%**；**暴露面四面** time **94.36** / count 27.81 / distance 18.56 / volume **4.31**（%）；跨时段极差 **0.0573 > 0.05** ⇒ **`CALIBER_FRAGILE`**（须四面并报，⛔ 不得单报 94.36%）。**★Q3**：`service` `cap = 400×permlanes` **100.000%**、全网 **99.689%**、`qsim` 无覆盖 ⇒ **参数是派生实现量，不是机制旋钮**。**★验证**：负例 **11/11** 全触发、BLOCKED **3/3** 完整节点、独立复核 `VERIFY_OK=True`。**★新纪律 `R-G0-1…5`**：发现门≠执行门（门禁不得编码期望结论，否则合法负结果被误判 BLOCKED）／manifest 不自哈希且不含 closure／写入终局状态的判据须排除该门自身／汇总件数字须与分解件同源／占比必须并报暴露面。**本轮自查 5 处**（E1 门 16 误判 `FRAGILE`、E2 门 24 自引用振荡、E3 manifest↔closure 2-循环、E4 summary 头条漏赋值 0.0、E5 复核脚本自身少乘 service 掩码 82 vs 74）。**★冻结影响 = 无**（零仿真、冻结件 `changed=0`、不产生 v1.1）。 |
| 2026-09-28 | **★`F-2 Q4-R1-R1` 正式记为 READY 节点，`Q4-R1` 线关闭（用户裁定）** —— **冻结验收 = `25/25` / `EXIT=0` / `CLOSURE=OK`**；prereg `82a03eb8aac0dc5d7ba610f8f0e3ba53e1cc1e0bd92ca00f60dbc8fdcd7c5f7f`（16,772 B）/ 脚本 `1cbeb2014fb6e2303099d7bbcbae58725e5b84518942f1e2bfc548a268227679`（98,312 B）。**技术链正式记为 `F2 v2 → v2.1-R2（Q2）→ Q4-R1-R1（Q4 nearest capture）→ service delay mechanism`**，下一步 = **`service` 延误机制**（避免继续在已基本收口的几何匹配线上迭代）。**本轮 9 项修复全落地**：① 恢复 4 类邻域 ② grid = 1,308 ③ 真独立 selection re-derivation（1308/1308、max abs Δ=0）④ 真独立 SELF exclusion audit（violations 全 0）⑤ selection flow-blind 改 **AST 语句区间**结构化检查 ⑥ Q4 traceability 保持 23 字段 ⑦ 门 16 升级为 `WRITEBACK_VERIFICATION`（manifest↔磁盘↔closure 三方一致）⑧ 门 25 修正为真实 `…_v2_1_R2` 路径 + 8 件非 Q4 产物 SHA 对照（8/8 identical + 本地重算 2/2）⑨ BLOCKED 路径完整物化 + 最终三方状态闭环（坏输入 ×3 均产出 25 行 checks + 5 件产物 + EXIT=1）。**负例矩阵 10/10 全部按预期门触发**（此前 5 个空门 16/20/22/24/25 现均有可证伪反例）。**★同层对照 R2(max-flow) → R1-R1(nearest) median ratio 20→100 m**：sec/parallel **+0.365 → +0.020**、ter/parallel **+0.499 → +0.007**、sec/twin +0.0915 → −0.0033、ter/twin +0.0042 → −0.0879 ⇒ **nearest 规则去掉此前明显的 max-over-N 单调膨胀**（用户要求：先记住、待 R1-R1 自身过 25 门后落定 —— 已过门）。**★新纪律 `R-Q4R1R1-1…7`**：闭包表不得含自身（自引用破坏不动点）／独立重导必须从原始候选池重算／BLOCKED 必须是完整可审计节点／词窗式静态检查改 AST 语句区间／环境：`rmtree` 触发批量删除门、`tasklist` 输出须 GBK 解码／R2 节点本就含 4 类邻域。**本轮自查 5 处**（E1 闭包自引用致不收敛、E2 漏导出 `distance_same`、E3 `rmtree` 触发 SAFE_DELETE 门改新沙盒根、E4 `tasklist` GBK、E5 prereg 计数 16→15 并重算哈希）。 |
| 2026-09-28 | **台账补记：`7.9F-0/1/2` + `F-2 v2.1-R2` + `Q2` 正式诊断**（此前仅存于各自 `reports/` 目录与项目记忆，本轮统一补入 §3.1 与 §6）—— `7.9F-0 v2` 判 `GRADE_CAPACITY_AUDIT_READY`（12/12 + 补充 3/3；**容量纯查表 ⇒ 无 link 级信息**）；`7.9F-1 v2` 判 `AGGREGATION_AUDIT_READY`（12/12；**83 零断面 = 68 真零 + 15 median 塌陷**；obs 加权 −0.0139→+0.0110）；`7.9F-2 v2` 判 `MECHANISM_AUDIT_READY`（16/16；**D4/D5 只作描述**）；`F-2 v2.1-R2` 判 `LOCAL_CAPTURE_DIAGNOSTIC_READY`（18/18；**Q2 升为正式 negative diagnostic**）。 |
| 2026-09-20 | **Step 7.9E-0 Arterial-Layer Delay Attribution Audit 完成 → 判 `ARTERIAL_LAYER_AUDIT_BLOCKED`（零仿真只读；硬门 **11/12**；**22.1 s**）—— 7.9 第九阶段（干道层），⛔ 不回灌 v1.0** —— **新增** `scripts/od/audit_arterial_delay_7_9e0.py` + 冻结 `reports/arterial_delay_attribution_7_9e0/PREREG_7_9E0.md`（sha256 `4fa98a96…12ea08f1`）⇒ 8 件产物。**E1**：arterial_core 车时份额 **0.6371**（时间主场）/ 结构份额 0.0676；**E2**：`delay_share` `service` **0.5710** > arterial **0.2978**，`delay_ratio` 结构 4.41 vs 车时 0.47 **翻转**；**E3 BLOCKED**（576 断面中 motorway/motorway_link **77.8%**、arterial 仅 **12** <30）；**E4**：arterial→mainline 中位 **1,309.9 m**、`≤300 m` 5.32%、hop 52（辅）⇒ 深居离主线。**新规则**：时间面≠延误面须分别报基数；靶场构成须先行体检。⛔ 暂不改 service 400 / 端点吸附；**不产生 v1.1** |
| 2026-09-20 | **Step 7.9E-1 Arterial Observability Expansion 完成 → 判 `OBSERVABILITY_BLOCKED`（零仿真只读；独立 diagnostic crosswalk；硬门 **10/12**；**24 s**）—— 7.9 第十阶段（可观测性层），⛔ 不回灌 v1.0** —— **新增** `scripts/od/audit_arterial_observability_7_9e1.py` + 冻结 `reports/arterial_observability_7_9e1/PREREG_7_9E1.md`（sha256 `4d5ee3e1…6751d`）⇒ **12 件产物**。**匹配质量**：A+B 覆盖 **97.48%**（1,278/1,311 上界）、中位 **0.57 m**、p90 **2.92 m**、方向差中位 **1.38°**；全量标出 **542** 条 `arterial_core`。**★★根因**：576 残差断面 `RoadCat` 仅 `CATA` 326 + `SLIP_ROAD` 250，A+B 代表链路 motorway 328 / motorway_link 247 / primary_link 1 ⇒ **arterial residual n = 0（三档全 0）** ⇒ **冻结靶场定义域不含 arterial**，既非匹配质量亦非 arterial 少。**新规则 `R-OBS-1~5`**（正式/诊断 crosswalk 永久分离；先证可观测再判归因）。**两个坑**：① 零仿真自审门**自指误报**（检查函数字面量含 `subprocess.run`/`java -`）⇒ 改 **AST 门**；② `section_length_m` → `length_m` **别名回退**。⛔ 暂不改 service 400 / 端点吸附；**不产生 v1.1** |
| 2026-09-20 | **Step 7.9E-2 Expanded Diagnostic Residual Domain 完成 → 判 `NO_ARTERIAL_COUPLING_SIGNAL`（零仿真只读；复用 E-1 独立 diagnostic crosswalk + 冻结 SCALE；硬门 **12/12**；**60–73 s**）—— 7.9 第十一阶段（扩展诊断残差域），⛔ 不回灌 v1.0** —— **新增** `scripts/od/audit_expanded_residual_7_9e2.py` + 冻结 `reports/arterial_expanded_residual_7_9e2/PREREG_7_9E2.md`（sha256 `c9e68272…e6cc`）⇒ **12 件预注册产物 + 3 件事后补充**。**★可观测性解决**：A+B 覆盖 **97.48%**、有效残差 **1,278**、**arterial 12 → 542**。**★formal bridge**：overlap **576/576**、Spearman **0.9662** / Pearson **0.9398** / MAE **0.0722** / RMSE **0.4655**。**★耦合**：arterial 均值 **+0.0027** vs 非 **+0.0904**、Spearman **−0.0216**、η² **0.0013**、非分层 p **0.1969**、**分层 p **0.05247**（临界 ≥0.05 ⇒ 无信号）**。**⚠️ 事后稳健性（不改判决）**：分层统计量 **69.3% 来自 CATA 单条误映射 `primary`（残差 −1.000）**；仅 CATB `p=0.0080`、去 CATA `p=0.0400`、去 CATB `p=0.1679`。**★★真实结构 = 等级单调梯度**（motorway +2.0% / primary +7.6% vs trunk −20.2% / secondary −34.6% / tertiary −41.7%，flow-weighted）⇒ **`arterial_core` 符号抵消、聚合均值是伪影**。**新规则 `R-RES-1~6`**。**运行前修 1 处**：`W01_DIR_CANDIDATES` 路径笔误（缺 `W01_rc_min`）⇒ 修正为 `matsim_final_7_6h/outputs/W01_rc_min/ITERS/it.19`。⛔ 暂不改 service 400 / 端点吸附；**不产生 v1.1** |
| 2026-09-20 | **Step 7.9D-1 Ramp Interface Audit 完成 → 判 `RAMP_INTERFACE_CONTINUOUS__RAMP_NOT_A_DELAY_HOST`（零仿真只读；硬门 **11/13** + 补充 **3/3**；**19.7 s**）—— 7.9 第七阶段（主线接口层），⛔ 不回灌 v1.0** —— **新增** `scripts/od/audit_ramp_interface_7_9d1.py` ⇒ 新目录 `reports/ramp_interface_7_9d1/`（**预注册 `PREREG_7_9D-1.md`（sha256 `5c8fd9c1…8983`）+ 报告 `REPORT_7_9D1.md` + 8 件产物**）。**用户裁定**：研究对象由 `service+connector` **收窄**为 `mainline ↔ ramp ↔ local-access`。**★新增两条永久规则**：**R-DIST-1**（接口距离一律 meter/km，hop 仅辅助）、**R-MULTI-1**（接口判据必须多跳）。**★单跳近重言式**：`neither` **92.73%**。**★接口连续**：多跳 `acc_m` 有限率 **100%**、ramp 中位 **478 m**；`egr_m` 中位 419 m；链长中位 500 m、片段中位 16.6 m。**★车道/容量连续**：车道下降仅 **1.85%**、`Δcap/lane` 中位 **+200**。**★★ramp 非延误宿主**：车流 9.22% vs 延误 **1.46%**、`ratio 0.719`、按车流归一 0.158；延误加权 `acc_m` 647 m ⇒ 耦合方向通、量太小 ⇒ **与 C-1/D-0 连续一致：问题不在主线接口层**。**⚠️ 预注册缺陷如实上报**：`R1.05/R1.06` FAIL 系「`min>0`」逻辑不可能（主线种子恒 0），**不改预注册**、改列补充门 `S1.01–S1.03` 3/3 PASS。**★冻结影响 = 无**：未跑仿真、未改参数、冻结件 `changed=0`；**v1.0 仍为唯一冻结模型、不产生 v1.1**。■**教训 §102–104**：接口距离必须物理口径；接口判据必须多跳；暴露面 ≠ 时间面 |
| 2026-09-20 | **Step 7.9D-2 Terminal Representation Audit 完成 → 判 `MIXED__TERMINAL_AND_MAINLINE_COMPARABLE`（零仿真只读 + 自由流时间；硬门 **13/13**；**27.5 s**）—— 7.9 第八阶段（端点表示层），⛔ 不回灌 v1.0** —— **新增** `scripts/od/audit_terminal_representation_7_9d2.py` ⇒ 新目录 `reports/terminal_representation_7_9d2/`（**预注册 `PREREG_7_9D-2.md`（sha256 `03f24243…3369`）+ 报告 `REPORT_7_9D2.md` + 6 件产物**）。**★端点**：O `service` **0.7068** / D 0.6685 / 至少一端 **0.9026**（`expansionFactor` 加权 O 0.7170）；按组 O `local` **0.9011**。**★自由流接入时间**：`T_acc` 中位 **124.8 s**、`T_egr` 103.6 s、`T_terminal_lb` 中位 **234.3 s**（p90 417.8）。**★★全网自由流时间分解**：总 **24,905.2 车·h**、off-mainline 14,146.7 ⇒ **`share_offmain = 0.5680`**（实际 0.6364；KW 0.6049）⇒ 判 `MIXED`。**★★最重要发现**：off-mainline 由**干道主导**（mainline 0.4320 / arterial **0.3787** / local 0.0998 / ramp 0.0895），**`service` 仅 0.0515** ⇒ **端点暴露面（90%）≠ 时间面（5%）**，把矛头指向 `service` 的 400 veh/h **会指错对象**。**★精度修正**：`cap/lane` 严格 = **400**；自由流速度**非严格恒定**（10 值 5–70 km/h、20 km/h 占 **96.80%**）⇒ `SERVICE_SPEED_FIXED=False`；D-0「恒 20 km/h」仅 p10=p90 意义成立。**★冻结影响 = 无**：未跑仿真、未改容量/吸附、冻结件 `changed=0`；**v1.0 仍为唯一冻结模型、不产生 v1.1**。■**教训 §102–105**：接口距离物理口径；接口判据多跳；暴露面≠时间面；「恒定」类断言须用 `ndistinct` + 例外比例 |
| 2026-09-20 | **Step 7.9D-0 Access-System Delay-Trapping Audit 完成 → 判 `DELAY_TRAP_OFF_MAINLINE_BY_CONSTRUCTION__BASE_RATE_DOMINATED`（零仿真只读；硬门 **15/15** + 补充 **2/2**；**33.0 s**）—— 7.9 第六阶段（接入结构层），⛔ 不回灌 v1.0** —— **新增** `scripts/od/audit_access_delay_trapping_7_9d0.py` ⇒ 新目录 `reports/access_delay_trapping_7_9d0/`（**预注册 `PREREG_7_9D-0.md`（sha256 `564310dee…6ee85`，运行期重算 **MATCH=True**）+ 报告 `REPORT_7_9D0.md` + 8 件数据产物**）。**用户裁定**：问题收窄为「**为什么回溢无能的 `service/connector` 短链能持续吸收大量延误，却不能把压力反馈到主线**」；三接口 = `主线容量 ↔ 接入拓扑 ↔ 局部储存`；**零仿真结构审计优先**（⛔ 不改 network、⛔ 不跑 MATSim），**先写预注册再读任何仿真输出**。**★★决定性发现 = base-rate 控制让结论反转**：`ratio = delay_share / km_share` ⇒ 全网 `service` **1.610**（不构成富集；本就占 58.61% km / 64.95% link），**限定主线邻域（`d_up≤3`，**15,319 links / 2.209%** / 13,125 nodes）后 ratio = 0.171（欠表达 8.5×）**，邻域延误 **96.35%** 落在 `motorway+ramp`（78.42% / 17.93%）⇒ **主线上本无压力可沉**。**①单向阀 = 证伪**：全岛 sink-valve（`mw_in ∧ acc_out ∧ ¬mw_out`）**仅 13 个**节点（邻域占比 **0.00099**，`VALVE_PRESENT=False`）；mainline-in 节点 **8,567** vs out **8,566**（8,550 重合）⇒ 主线**几乎完全可逆**。**②薄储存 = 成立但是"查表赋值"**：邻域 `fill_time` p25/中位/p75 = 4.53/**9.18**/17.28 s、**89.81% < 30 s**（全网中位 10.43 s、82.56%）；`cap/lanes` 按 `(highway × lanes)` **单值确定（13/13 类型，组内 `min=max`）** ⇒ `service`=**400**、`residential`=700、`tertiary`=900、`secondary`=1200、`primary`=1500、`motorway`=1900（veh/h/lane）；`cap_ratio_ref`：`service` **0.222**、`connector` 0.722、`ramp` 0.944。**③排队耦合 = 构造性缺失**：延误加权 `d_up` = **72.33 hops**、`share(d_up≤3)` = **0.0278**、`share(d_up>3)` = **0.9722**（`COUPLING_ABSENT=True`；敏感度 D=1/3/5 → 0.0278/0.0278/**0.0280** 稳定）。**④终端暴露（描述性、无裁决权；读冻结输入人口 `pop_W01`，⛔ 不用 `output_plans`/`linkstats`）**：**236,044** 出行，起点落 `service` **0.7068**、终点 **0.6685**、**至少一端 0.9026**（对照 km 0.5861）⇒ **出行两端都挂在 400 veh/h、20 km/h、≈1.55 车储存的"车道"上**。**★补充（非预注册，不改变判决）**：hop → 米翻译（延误加权上游距主线 **1,952 m**；`≤300 m` **0.0315**、`>1000 m` **0.7354**）⇒ 跳数被碎片化夸大但结论不变；细分辨率容量确定性 **13/13 单值**（预注册类别级 `CAP_DETERMINISTIC=False` 因 `other` 合并 5 种 highway，**两者并列如实上报**）。**★更正 C-1（已追加到 `REPORT_7_9C1.md` 更正附录）**：K3「回溢无能 99.95%」是**单跳口径近重言式**（仅 **0.049%** 的 `service` link 有主线 feeder）⇒ 升维多跳后 `share(d_up≤3)` 仅 **2.78%**；「延误被吸收到 service/connector」的**因果解释被取代**；研究对象**收窄为 `ramp`**（唯一邻域富集类，ratio **1.597**，邻域延误 17.93%）；C-1 **verdict 字符串字面不变**。**★CTE 门（D0.13 断言）**：正名 `Central Expressway` **603 links**、v1.0 **104.57 h（2.19%）**、KW **56.68 h（0.45%）**；旧掩码 `"CTE" in name.upper()` **命中 0**（`banned_mask_hits==0` 已断言）。**★冻结影响 = 无**：零仿真、未改参数/network、冻结件 `changed=0`；**v1.0 仍为唯一冻结模型、不产生 v1.1**；**本步只"证明"，不"修"**。■**教训 §98–101**：「份额类」结论必须先做 `份额 ÷ 里程份额` 归一（否则随分析域反转）；拓扑跳数在碎片化路网里须附物理距离；「单跳不可逆」是重言式、耦合判据必须升维多跳；「参数是否涌现」要用「确定性 + 最细可分辨粒度」两刀捅穿 |
| 2026-09-20 | **Step 7.9C-1 Structural Spillback Validation 完成 → 判 `SPILLBACK_CHANNEL_INTACT__DELAY_TRAPPED_OFF_MAINLINE`（零仿真只读；硬门 **11/11**；**23.7 s**）—— 7.9 第五阶段（拓扑通道层），⛔ 不回灌 v1.0** —— **新增** `scripts/od/audit_structural_spillback_7_9c1.py` ⇒ 新目录 `reports/structural_spillback_7_9c1/`（**预注册 `PREREG_7_9C1.md` + 报告 `REPORT_7_9C1.md` + 7 件数据产物**）。**用户裁定**：C-1 **不**再回答「KW 是否有效」（B-1 已回答），只回答「**网络表达方式是否阻断拥堵从瓶颈向上游传播的结构通道**」；冻结**三条证据链**（真实候选瓶颈→上游传播路径→下游储存/阻塞能力）与**四条检查**（K1 主线可传播通道 / K2 下游储存回溢 / K3 service-connector 回压死端 / K4 超短 link 碎化）；**统一拓扑框架** = `class × corridor(name) × junction-cluster(unit)`。**★K1 = 通道完整**（`up_main_m` 中位 **1,957 m**、p90 15,537 m；`≥300 m` 按里程 **91.52%**、`≥1000 m` **75.84%**）⇒ **✗ 不支持「被切断」**。**★K3 = 断点成立**（`service∪connector` 回压死端 **99.95%**、motorway 仅 **0.17%**）。**★K4 = 快速路不碎、服务网极碎**（motorway **17.43 links/km**、中位 37.8 m、**0** 条 `>40`；connector **85.01**、service **50.81** links/km，中位 8.9–9.3 m、72–89% ≤20 m）。**★K2**：候选 **5,490** 中**仅 387（7.05%）含主线 link**；`fill_time` 中位 **9.80 s**、**51.02% < 10 s**。**★决定性对账**：v1.0 延误 **4,778.8 h** → motorway **2.50%** / **service 94.36%**；KW **12,482.1 h** → motorway 3.95% / service 88.01%；**延误加权通道 v1.0 = 334 m**（service 内 **107 m** vs motorway 内 7,921 m）、**97.34% 延误落在回压死端 link 上**（KW 95.97%）⇒ **「就地生成、就地吸收」**。**★裁决（对用户假设的诚实回应）**：预设「网络表达阻断快速路回溢通道」**未被支持**（主线通道完整 + 快速路未碎化）；被表达方式伤害的是**非主线接入/服务子系统** ⇒ 应将结论从「queue / KW 参数不对」改写为 **「拥堵的生成与吸收都被结构性地困在离主线的、拓扑终端的接入子系统里」**。**★附带发现**：冻结结构先验**本身不偏向快速路**（候选单元仅 7.05% 含主线 link）；与 7.9C-0 的 C2（残差不向结构单元富集）叠加 ⇒ **「结构先验」与「实际延误」都不落在快速路上**。**★更正 7.9B-1**：B-1 的「CTE 走廊 1.76→24.22 h」系**旧掩码**（`name` 无字面 "CTE"，实际命中 **Changi ∪ Tampines**）；**CTE 正名 104.57 h（2.19%，v1.0）→ 56.68 h（0.45%，KW）** ⇒ B-1 三层 verdict 不变，但「KW 未复现唯一真实快速路排队链」的数值须更正为 **KW 削弱/转移**；已在 `REPORT_7_9B1.md` 追加更正附录。**★冻结影响 = 无**：未跑仿真、未改参数、冻结件 `changed=0`；**v1.0 仍为唯一冻结模型、不产生 v1.1**。■**教训 §95–97**：「结构完整/损坏」须按**瓶颈侧 vs 吸收侧**分列；「延误×结构通道」是检验「被困住」的直接物理量；**冻结文件里的简称掩码**须用「正名 + 计数断言」兜底 |
| 2026-09-20 | **Step 7.9B-1 `qsim.trafficDynamics: queue → kinematicWaves` 单变量机制实验完成 → 判 `KW_CHANGES_CONGESTION_MECHANISM__KW_POSITION_NOT_IMPROVED__STABILITY_OK`（仿真侧 **49/49** + 分析侧 **14/14**；仿真 **177.5 min**；分析 **400.6 s**）—— 7.9 第四阶段，★**真·单变量实验（非调参）**，结果落**独立目录**、⛔ 不回灌 v1.0** —— 用户裁定：7.9C-0 冻结后进入 B-1，**唯一改动 = `qsim.trafficDynamics`**，其余 v1.0 条件（`f_cap=1.0`/`SCALE=2.29897`/`λ=0.075`/`f_work=1.180222`/`N_sim=236,044`/R01 rc_min/`stuckTime=10`/`removeStuckVehicles=false`/network/OD/crosswalk/seed/departure）**全部继承**；**红线 = 「机制变化」与「位置改善」严格分离**。**新增** `scripts/od/run_kw_single_variable_7_9b1.py`（配置派生 + **49 门** + 点火；模型层 diff **恰好 1 项**、输出层 **恰好 3 项**、`VIOLATION=0`；`dsim.trafficDynamics` 同名诱饵未触碰；`inflowCapacitySetting` 未覆盖 ⇒ 默认 `INFLOW_FROM_FDIAG`）／`scripts/od/analyze_kw_7_9b1.py`（零仿真三层分析，**14 门**）／`scripts/od/_build_link_unit_map_7_9b1.py`（**溯源执行 7.9C-0 冻结源码切片** 重建 link→unit 映射，**22,722 单元位级自校**）⇒ 产物 `matsim_kw_7_9b1/`（配置+audit+`outputs/W01_kw/`）与 `reports/kw_single_variable_7_9b1/`（**13 件**，含 `REPORT_7_9B1.md`）。★**结果**：L1 机制变化**成立**（`Sim/Obs` 0.9993→**0.8506**、超额 4,705→**18,860**、延误 4,779→**12,482 h（+161%）**、`A_10:19` 0.89%→**3.52%**）；L2 **无长链**（分量 3,603→**8,223** 更碎、最长仅 0.857→**0.954 km**、**超额落候选单元比例 32.54%→29.45%**、富集 1.718×→**1.555×**）；L3 **位置未改善**（C3 lift 1.852×→**1.835×**、C2 ρ +0.0267(p .200)→**−0.0078(p .485)**、辅助超额口径 1.679×→**1.601×**）。★**延误去向**：`service` **88.0%**、**CTE 仅 0.19%**（未复现 7.7E 认定的 CTE 排队链）。★**结论**：**「变堵了 ≠ 堵得对了」**——满足「机制变化」、不满足「位置改善」。★**冻结影响 = 无**：实验**未被采纳** ⇒ **v1.0 仍为冻结模型、不产生 v1.1**；14 件冻结输入 sha256+mtime `changed=0`。■**教训 §90–94**：diff 门须模型/输出分层且**校验 module 同名**；「作用集合=0」≠ 机制未生效（`q_fdiag` 是速率上限）；「变堵」与「堵得对」须两套独立证据链；换拥堵定义须**对称施加 + 标注非预登记**；复用冻结中间结构应**执行其源码切片 + 位级自校** |
| 2026-09-20 | **Step 7.9C-0 结构性瓶颈审计完成 → 判 `STRUCTURAL_BOTTLENECK_PRIOR_ESTABLISHED`（零仿真只读结构审查；硬门 **25/25**；~35 s）—— 7.9 第三阶段（空间结构层），⛔ 非 7.8 前置、不回灌 v1.0** —— **新增** `scripts/od/audit_structural_junction_cluster_7_9c0.py` + 输入预处理 `_build_network_cache_7_9c0.py`（⇒ `_cache_network_7_9c0.npz`：link 属性 + 421,406 节点坐标 + 断面 crosswalk）；**新目录** `reports/structural_junction_cluster_audit_7_9c0/`（10 件）。★**三层尺度**：L1 junction-cluster（同层短链 ≤52 m 连通分量 + 结构种子；**22,722 单元 / 460,001 link / 66.3%**，单元 ≤200 link）、L2 short-chain（ramp/connector/service 链）、L3 corridor（仅宏观，⛔ 非第一判据）。★**C1 结构瓶颈先验（零流量；门 C0.22 源码自检）**：`mean(merge_deficit, lane_narrowing, class_transition, ramp_mainline)` 取单元内**最大值**；`storage_shortage_proxy` 均值 **0.0058** ⇒ 判别力为零、剔除。★**C2 残差投影**：映射覆盖 **99.7%**（空间最近邻兜底 p90 173 m）⇒ **ρ = 0.0355 / 置换 p = 0.8125 ⇒ W01 残差未向结构瓶颈单元聚集**（规模分层后同结论）。★**C3 HitRate/Coverage 预登记 + v1.0 基线**：0.4475 / 0.3705 / **lift 1.852×**，附**共同因子证伪**（`ρ(prior,单车道容量)=0.248`、`ρ(v/c,单车道容量)=0.449`；饱和 link 仅 82、p80 阈值 0.022）⇒ **lift 不得读作位置成功**。★**C4 B-1 最小观察集冻结**（8 层）。★**自检**：v1.0 拥堵基线 **82 link / 1.151 km 与 7.9A-0 逐位一致（C0.17）**；`changed=0` |
| 2026-09-20 | **Step 7.9B-0 交通动力学机制审计完成 → 判 `TRAFFIC_DYNAMICS_MECHANISM_AUDIT_COMPLETE`（零仿真只读结构审查；硬门 **16/16**；~8 s）—— 7.9 第二阶段（结构审查），⛔ 非 7.8 前置、不回灌 v1.0** —— **新增** `scripts/od/audit_traffic_dynamics_7_9b0.py` ⇒ 新目录 `reports/traffic_dynamics_audit_7_9b0/`（7 件）。**源码证据 15 条全部从 `tools/matsim-2026.0/matsim-2026.0-sources.jar` 现场重新核对**（非凭记忆）：`HOLE_SPEED_KM_H = 15.0`(L175)、`maxFlowFromFdiag`(L414)、`INFLOW_FROM_FDIAG` 分支(L447/460)、`case queue: ... break`(L394)、`maxInflowUsedInQsim` 初值(L391)、储存公式(L487/L509/L547)、`inflowCapacitySetting` 默认(L73)、**`maxFlowFromFdiag` 不乘 `flowCapFactor`** 的源码注释(L407–412)、`DEFAULT_EFFECTIVE_CELL_SIZE = 7.5`(NetworkImpl L59)、`stuckTime=10`/`removeStuckVehicles=false`(QSimConfigGroup L95/L96)。**B1**：生效 = `qsim = queue`；`dsim = kinematicWaves` 惰性；`inflowCapacitySetting` 未设 ⇒ 默认 `INFLOW_FROM_FDIAG`。**B2**：`queue` **无**额外入口约束（源码级）。**B3**：被卡 link **21,670（3.1244%）/ 869.589 km（5.7488%）**（local 132 / collector 1,005 / **arterial 15,526（492.4 km）** / **fast 2,386（138.1 km, 100%）** / **expressway 2,621（212.9 km, 97.98%）**）；★被移除入口容量 **8,784,415 veh/h**；★`MAX_CAP_FOR_ONE_LANE` 与 `INFLOW_FROM_FDIAG` 的 r<1 集合**代数恒等**（`fd_lane×lanes/cap ≡ fd_link/cap`）。**★B4 预登记假设被证伪**：被卡 link **不**集中于 junction —— 全样本 **0.268×**、同类别 0.18–0.65×、严格 in-degree≥3 **0.090×**、from-node 平均入度 **1.207 vs 1.882** ⇒ KW 入口上限 = 对高速/高容量路段的**整体 ~10–11% 削流**（expressway 中位 r 0.90、fast 0.89），**非**节点级瓶颈机制 ⇒ ⚠️ **可能让地图变堵却不提升结构保真度**（与「为让动画变堵而放大 demand」同构的红线风险）⇒ B-1 必判**拥堵位置**。**B5**：link 中位 **11.0 m** / p90 52.0 m、**24.34% 里程 < 20 m**、节点间距 **35.9 m**、度 ≥3 节点 **242,388（16.0/km）**、度-2 直通 42.5% ⇒ **无长「度-2 链」**（中位 corridor **1** 条 link）⇒ **7.9C 改做 junction cluster 聚合**；KW 储存放大 **20,922 links（3.02%）**、`queue` 0。**★★A×B 非可加**：`flowCapFactor` 缩放 `flowCapacityPerTimeStep`/`storageCapacity` 但**不**缩放 `maxFlowFromFdiag` ⇒ `f_cap=0.435` 时 FD 入口约束在 **0** 条 link 生效（1.0 时 21,670）；KW 储存机制 **`f_cap` 不变**（比值判据）⇒ 0.435 下两模型只差储存侧 ⇒ **支持 B1(`f_cap=1.0`) → B2(叠加 0.435) 串行**（⛔ 不一次改两个机制）。**B-1 预登记**：仅 `queue→kinematicWaves`、其余继承 v1.0；`Sim/Obs` 仅崩解护栏 ≥0.85；主看 `v/c` 分布 / 饱和里程 / 峰 `aggV/C` / 真实超额 / 回溢链；无实质变化且未崩 ⇒ **`TIMEDYNAMICS_NOT_PRIMARY`** ⇒ 转 7.9C。**`stuckTime=10` / `removeStuckVehicles=false` 保留观察、非第一变量**。⛔ 未跑 MATSim、冻结件跑前后快照 `changed=0`（201 件）。 |
| 2026-09-20 | **Step 7.9A-0 采样—容量一致性审计完成 → 判 `SAMPLING_CAPACITY_CONSISTENCY_AUDIT_COMPLETE` / `SAMPLING_CAPACITY_INCONSISTENCY_CONFIRMED`（v1.0 冻结后只读结构审查；硬门 **22/22**；~10 s）—— 7.9 第一阶段（结构审查），⛔ 非 7.8 前置步骤** —— **新增** `scripts/od/audit_sampling_capacity_7_9a0.py` ⇒ 新目录 `reports/sampling_capacity_audit_7_9a0/`（8 件）。**定位（用户 2026-09-20）**：`7.8 v1.0 冻结 → 7.7E 事后只读诊断 → 状态形成机制结构性不足 → 7.9 Structural Repair / v1.1`；⛔ 结果不回灌 v1.0。**① 四个实际生效值**（四源逐位一致）：`qsim.flowCapacityFactor` **1.0** / `qsim.storageCapacityFactor` **1.0** / `qsim.trafficDynamics` **`queue`** / `qsim.timeStepSize` **`00:00:01`**。**★惰性诱饵（新坑）**：全配置 `trafficDynamics` 出现**两次** —— `dsim` = **`kinematicWaves`**、`qsim` = **`queue`**；因 `controller.mobsim = qsim`，**只有后者生效**（`hermes.*CapacityFactor = 1.0` 同理惰性）⇒ A-1 的**唯一容量旋钮是 `qsim.*`**；**只看 key 名会得出「当前已是 kinematicWaves」的相反结论**。**② ★★分母歧义（本步最重要）**：`s = N_sim/ΣEF = 236044/459794 = **0.513369**`（⛔ 误用）vs `s = N_sim/(SCALE·N_sim) = 1/SCALE = **0.434977**`（✅ capacity 一致性因子），两者之比恒 **1.180220 = f_work** ⇒ 不是误差而是**分母选错**。**量纲证明**：`Sim/Obs = 1`（冻结 **0.9993347697**）断言 `F_real = SCALE × F_sim`；要 `v/c_sim = v/c_real` ⇒ `C_sim = C_real/SCALE` ⇒ **`f_cap = 1/SCALE`**（与 `ΣEF` 定义无关）。`ΣEF = 459,794` 是 **Census Car Only 需求锚**，模型实际表示 `SCALE×N_sim = **542,658**` 辆（= **1.180222 倍**需求锚，弥合 7.6A `CALIBER_GAP`）⇒ 拿需求锚当流量分母会把因子**算高 18%**。★ **稳健性**：`1/SCALE = N_base/ΣEF` **与工作点缩放无关**。**③ 模型物理含义**：236,044 辆 = 真实 **43.4977%** 样本，却用 **100% 容量** ⇒ **`v/c_sim ≈ 0.43498 × v/c_real`** = 7.7E「流量对上、状态不足」的机制解释。**④ ★零仿真预注册预测（冻结流量一阶上界、高估饱和）**：`n(v/c≥0.5)` 2,813→**16,049**（×5.71）/ `n(v/c≥0.9)` 220→**5,413**（×24.60）/ `n(v/c≥1.0)` **82→4,187**（×51.06）/ 饱和里程 **1.151→178.114 km**（×154.69；占全网 15,126.5 km 的 **0.008%→1.177%**）/ 全时段 `Σ流量/Σ容量` 0.052792→**0.121368** / 峰 `aggV/C`（7.7E E4）0.102447→**0.235522** ⇒ ★**即使 sample-consistent，饱和里程也仅 1.18%、峰 aggV/C 仅 0.236 ⇒ 仍不预期全网级拥堵波**，改变集中在**局部瓶颈** ⇒ **情形 C 优先**；方向性 = 在途峰 ↑ / 通过量 ↓ / **`Sim/Obs` 下移**（⛔ `0.9993` **不得**作 A-1 目标，仅**崩解护栏 ≥0.85**）。**⑤ A-1 计划（待批准，本步不执行）**：唯一变化 `qsim.flowCapacityFactor` / `storageCapacityFactor` `1.0 → **0.434977**`（**单点派生值，不做 0.35/0.40/0.45/0.50 扫描** —— 那是参数拟合）；新版本 **v1.1** 新目录；⛔ 不动 OD / `f_work` / λ / `SCALE` / population 236,044 / R01 / 7.3.6A / network / W01 / `randomSeed=4711`。**四项预注册读法**：A 拥堵显著增强且流量保持 ⇒ 表示尺度统一（非调参）；B 拥堵增强但 stuck/崩溃 ⇒ 转 **7.9B 瓶颈与存储结构**（⛔ 不把容量调回）；C 增强很少 ⇒ 转 **`trafficDynamics`**；D 流量严重恶化 ⇒ 查 flow scale × capacity × departure 耦合。★ **A/B/C 三刀必须串行**。**⑥ 纪律**：⛔ 不为了让 VIA 变红加 demand；⛔ 不为制造拥堵降容量/改 λ/改 route-choice；⛔ 不重定义 congestion index。**★本步自查 3 处**：① `E4.entries` 是**累计链路进入数**、非在途量（首版 A0.21 误读，改用 legHistogram `enr_car` 后复现 **36,799 @08:55**）；② `SCALE×N_sim` 是**车辆数**而非流量率；③ md 表格单元格含 `|` 会**拆列** ⇒ `md_table` 统一转义 + 数值去尾零。⛔ 未跑 MATSim、未改任何冻结件（三个冻结目录跑前后 mtime 快照 **`changed=0`**、n_files=212）、**7.8 门 23/23 不受影响**。 |
| 2026-09-19 | **Step 7.7E 拥堵状态合理性审计完成 → 判 `CONGESTION_STATE_PLAUSIBILITY_AUDIT_COMPLETE`（零仿真只读事后审计；硬门 **20/20**）—— ★直接回应 7.8-VIA-DIAG，**推翻既有读法**，并承接用户硬约束「不得为让动画变堵而放大 demand」** —— **新增** `scripts/od/audit_congestion_plausibility_7_7e.py` ⇒ 新目录 `reports/congestion_plausibility_audit_7_7e/`（22 件）。**★两条口径先纠正**：① **`v/c ≤ 1` 是结构性质**（MATSim 流出被容量截断 ⇒ 超额表现为**上游排队**），故 `v/c = HRS8-9avg/CAPACITY` **恒 ≤ 1**、`v/c = 1.000000` 意为**饱和 + 排队**；**7.8-VIA-DIAG 把它读成「容量富余」是错的**；② **★★`qsim.timeStepSize = 1 s`**（config 第 222 行）⇒ 链路行程时间**向上取整** `TT = ceil(FF)`，而本网络链路 FF **中位 1.37 s / 均值 2.93 s**（>500 m 仅 **29** 条）⇒ **即使零延误** `TT/FF = ceil(FF)/FF ≫ 1`。**★E1 容量来源**：`capacity = lanes × capacityPerLane(road_type)` 确定性函数；限速与源副本**逐位一致**、可比区间车道数完全一致（源副本 `lanes` 27 万条缺失，不参与比较）；快速路 **motorway 1900 / trunk 1800 / motorway_link 1700 在参考带内**，**超出上沿的是干道与地方道路**（primary 1500>1200 等）⇒ **H1「容量被设得离谱地大」不成立**；利用率 全部 **7.9%** / 已载流 **12.8%** / 快速路走廊 **28.5%** / 干道 7.8% / 地方 0.9%。**★E2/E2b（决定性）**：10 条快速路原始 `TT/FF` **1.20–1.44**「看起来每条都在堵」→ 扣 **`ceil(FF)/FF` 基准**（**只由几何决定、跨时段恒定 1.567–1.596**）后 **9/10 ≈ 0（−0.002~+0.008）**，**仅 CTE +0.085**。**★跨时段对照**：几乎空网的 **12–13 时（仅 18,694 车·链路）倍率仍 1.552 ≈ 基准 1.596** ⇒ **该口径测的是量化不是拥堵**；**82.56% 载流链路零延误**；单车级：`e138309_138310`（15.924 m / FF 0.955 s）07:00 23 辆车 `sum_tt` **恰为 23.0 s**。**★★按道路类型分解（本步最重要新证据；08–09 全网 4,779 车时真实延误）**：**`service` 占 94.4%（4,509 h，超额 +5.580）** / `motorway` **105 h（2.2%，全在 CTE）** / `motorway_link` 68 h / `residential` 25 h / `primary` 20 h / `trunk` 14 h / `tertiary` 13 h ⇒ **真实延误主体 = 大量 20 km/h 单车道 `service` 接入短段（容量 400 辆/h）的局部瓶颈，不是快速路排队拥堵**。**饱和链路 82 条 / 总长 1.15 km**：**74 条为 6 m `service` 短段** + **8 条 CTE motorway**（4 车道 / 90 km/h / 容量 7600，节点 `7214→…→20261`，SVY21 x≈29.4–29.7k、y≈33.0–33.3k = **CTE 中段 Jalan Toa Payoh / Kampong Java**），构成 **≈0.40 km 排队链**。**★E3 空间连续性**（宇宙 82,167 条载流 ≥20 m；**200 次随机置换**）：原始 `TT/FF>1.2` 最长链 **0.601 km**（随机 1.402，p=1.000，z=−2.54）、`>1.5` **0.420 km**（随机 0.623，p=0.870，z=−0.78）⇒ **比随机更分散**（`ceil(FF)/FF` 只取决于 FF 小数部分、与地理/上下游无关 = 伪影签名）；**扣量化后 真实超额>0.1**（638 条）最长 **0.499 km**、随机 0.417、**p = 0.165、z = +0.46 不显著** ⇒ **与随机不可区分、无连续拥堵走廊**。**★E4 峰值演化**：峰值在途 **36,799 @ 08:55**（`N_sim` 236,044 的 **15.6%**）、peak/median **8.27**；15 min `Σ流量/Σ容量` 峰值 **0.102**、真实超额全程 **+0.083~+0.221** ⇒ **无 AM 拥堵波**；events↔linkstats 最大相对差 **0.0000%**（另：09:15 后需求崩塌、仅 `service` 载流 ⇒ 倍率被动放大 = **伪影放大非拥堵波**，图中已标注）。**★裁决**：H1 **不成立** / H2 **主因** / H3 **成立（放大视觉错觉）** / **H4 度量伪影（决定性）**。**★★「交通流量校准成功 ≠ 拥堵状态校准成功」**：576 断面 `Sim/Obs = 0.9993348`（总量级匹配）vs 利用率 12.8% / 走廊真实超额 ≈0 / 无波 ⇒ **状态形成机制未被校准**。**★纪律**：⛔ **不得为「让动画堵起来」放大 demand**；正解 = **7.9 Structural Repair / v1.1**（结构修复 + 调小 `timeStepSize` 或改逐车行程时间评价），须另立版本 + 独立验证链。**★本步自查 4 处**：① `v/c = 1.000000` 误读；② 被量化污染的 `TT/FF` 口径（**7.6/7.7 标定用断面*流量*，未受影响**）；③ 「CTE 是全网唯一真实拥堵」过度概括（改为「唯一真实拥堵的**快速路走廊**」）；④ E3 第三判据 z **为正** ⇒ 不得写「z 全为负」。**★工具教训**：Edit 连 5 次静默丢改动 ⇒ 一律 **Python 锚点补丁 + `assert count == 1`**（14 处锚点一次命中）；matplotlib 缺字形字符须从图内文本剔除。⛔ 未跑 MATSim、未改任何冻结件（`reports/final_model_7_8/` 全件 mtime 仍 **2026-09-19 21:44**）、**7.8 门 23/23 不受影响** |
| 2026-09-19 | **Step 7.8-VIA-DIAG「VIA 早高峰不拥堵」三层诊断（零仿真只读派生，非新版本）** —— 用户追问「为什么我用 VIA 看…一点儿都不拥堵」。**新增** `scripts/od/diagnose_via_congestion_7_8.py` ⇒ 新目录 `reports/via_congestion_diagnosis_7_8/`（4 件）。**★三层归因**：① **VIA Network 层不带交通属性**、`output_links.csv.gz` 仅 10 列无行程时间字段 ⇒ 须另加 **`Dynamic Link Attributes`** 层（手册 §3.2.5）+ 窗口设 08–09 + 按 `speed` 着色；② 路网 **693,575 条碎段、中位 11.0 m**（>1 km 仅 **23** 条），且 MATSim 行程时间取整秒 ⇒ 短段倍率失真；③ **v/c 恒 ≤1**（max 1.000000、>1.0 零条），拥堵指数 **1.4143**（剔 ≤50 m 后 **1.2091**）。**★新证据**「按条数 57% 超 1.2 vs 按长度仅 34%」解释了地图为何偏绿。**★自查**：首版按位置贴两表 ⇒ **行序不同致整体错配**，改按 `link id` 显式 merge + `LENGTH` 一致性断言。`matsim_viz_7_8/README.md` 同步。⛔ 未跑 MATSim、未改冻结件、不作标定证据 |
| 2026-09-19 | **Step 7.8-VIZ-RUN 为 VIA 重跑 W01 开启 events** —— 用户追问「VIA 看哪个文件夹」。**发现** 7.8 定版 `writeEventsInterval=0` ⇒ 无 events，VIA 车辆层不可用（7.6 全家族同此）。**新增** `scripts/od/run_via_events_7_8_viz.py` + 新目录 `matsim_viz_7_8/`（`matsim_final_7_6h/` 一字未动）。准备步 **29/29**；白名单差异**仅 3 项**、214 参数全展开逐位比对；运行 **117.67 min**、过程门 **40/40**、判 **`VIA_EVENTS_REPRODUCTION_CONFIRMED_BITEXACT`**（it.19 linkstats 693,575/693,575 max|Δ|=0.0）；events 163,305,988 条 / 1.69 GB、dep=arr=236,044。**readme §2.46 + §3.1 + `matsim_viz_7_8/README.md`**。⛔ 输出层重执行、**非新版本**；⛔ 不得作新标定证据 |
| 2026-09-19 | **Step 7.8-VIZ 可视化看板 + ★冻结产物勘误** —— 用户诉求「我想可视化一下效果」。**新增** `scripts/od/make_final_model_dashboard_7_8.py`（**零仿真**、只读冻结件）⇒ `reports/final_model_7_8/` 增 **2 件附加件**（⛔ 非 6 件冻结产品）：`FINAL_MODEL_DASHBOARD.html`（**自包含单文件**、219 KB、零依赖、浅深主题自适应、12 面板）、`ERRATUM_spatial_residual_boundary_pa_all.csv`。**★★发现并定位 1 处冻结产物缺陷**：`FINAL_SPATIAL_RESIDUAL_BOUNDARY.csv` 的 `pa_all` 层 ratio 出现**负值** ⇒ 根因是源列 `7.7C-0 / c0_6_pa_gradient.csv → R_PA` **实际语义为「Q−1」**（核对 ANG MO KIO `R_PA`=0.681533 ↔ 真值 ratio **1.680415**），而 `freeze_final_model_7_8.py` L366–367 当 ratio 处理 ⇒ **双重变换**（`ratio_FROZEN` 偏 **−1.0**、`rel_dev` 再偏 −1.0；**37/37 行**；max |Δ| **0.9999**）。**影响边界**：仅此展示表——模型身份（f / λ / SCALE / f_cap / R01 / population / network）与 **#168 全部 23 门不受影响**。**其余三层正确**（576 断面表重算核对，|Δ| ≤ **4.6e-7** = 发布精度）：`region` 5/5（CENTRAL −7.82% / EAST **−31.75%** / NORTH +23.09% / NE **+33.88%** / WEST +2.84%）、`radial` 3/3（`radial_in` **−30.67%** / `radial_out` +14.50% / circumf +9.61%）、`pa_key` 10/10（ORCHARD **+142.00%** / BUKIT TIMAH **+138.61%** / TUAS **−86.99%** / HOUGANG **−86.98%** …）。**处置**：⛔ **未就地改冻结件**（改锁 = v1.1）⇒ 看板按真值呈现 + 「口径校验」面板显式标注 + 另出勘误 CSV；**是否升 `v1.0.1` 待用户裁定**。**★本步自查 3 处口径陷阱**：① 「逐位一致」误用（冻结 CSV 按**发布精度**存储 ⇒ 容差须 **1e-6**；与 7.7D G2 / 7.8 G6 **同族第 3 次**）；② 按「有坐标」筛掉 2 断面 ⇒ 全局 ratio 变化 ⇒ 所有 rel_dev 偏移 **0.07 pp**（NE 33.95% vs 33.88%）⇒ **分组聚合须用全 576 行**；③ `rel_dev_vs_global` = **`ratio/全局−1`**（非 `ratio−1`）。**★渲染验证链**：`node --check` → **jsdom 无头 DOM 断言**（`jsdom@22.1.0`，Node 20 须 CJS 版）→ **Chrome headless 截图**（浅/深双主题 + 2× 局部放大）+ PIL 分片目检；L2 抓出 1 处对账 bug、L3 抓出 4 处视觉缺陷。**#168 门 23/23 仍成立（本步未触碰任何冻结件）** |
| 2026-09-19 | **Step 7.8 Final Model Freeze & Validation Package 完成 → 判 `FINAL_MODEL_FROZEN_AND_REPRODUCIBLE`（零仿真定版；硬门 23/23；0.1 s）—— ★项目从「研究」切换为「定版」** —— 用户裁定：**不再做「7.8A 继续分析」，直接进入 7.8 最终模型冻结**（继续调参已无足够证据收益，反易把「模型诊断」退回「参数追拟合」）。**新增** `scripts/od/freeze_final_model_7_8.py`（**零仿真**；只读 14 件冻结输入；仅写入新目录 `reports/final_model_7_8/`）。**★7.8A 参数冻结**：`f_work=1.180222`（7.6G `L75` direct）/ `λ_ref=0.075`（7.6G 敏感度中心，⛔ **非最优 λ**）/ `SCALE=2.29897` / `f_cap=1.00` / `R01_rc_min` / `N_sim=236,044` / 7.3.6A crosswalk / `calibration_target=0.8589732`；**三层带独立不合并**（工作点 `f*=1.180222` / λ 带 `[1.1637,1.1938]` / 静态靶场带 `[1.06945,1.16418]`）。**★措辞纪律落入产物**：λ 只写「工作中心参数，可检测但不可靠识别」；`f_work` 只写「最终工作点，非唯一真实值」。**★7.8B 输入与算法版本锁**（Input / OD / Sampling / Network / Route Choice / Crosswalk）+ config 指纹（`seed=4711` / `SpeedyALT` / `qsim` / `lastIteration=19` / `fractionOfIterationsToDisableInnovation=0.8` / `[ReRoute .15, ChangeExpBeta .85]` / `learningRate=0.5` / `routingRandomness=0.0` / `flow+storageCapacityFactor=1.0`）+ 7.6H 相对 R01 的**3 项白名单差异**。**★版本语义**：任何修改均 = **新版本 v1.1 Structural Repair**，⛔ 不得就地改 v1.0。**★7.8C 验证包（W01）**：`Sim/Obs FROZEN` **0.9993347697** / implied `f*` **1.180866** / `f_realized` **1.1801564**；`A_10:19`(M/C/S) **0.8899 / 0.9038 / 0.8568 %**、`parity_gap_rel` **0.0964%**、`Q19/Q̄` **1.001972**、`never_arrived=0` / `max_stuck_car=0`、departure = arrival = **236,044**；跨步对账 X1 三口径 **Δ≤4.9e-8** / X2 四口径 **Δ=0.00e+00**（逐位）。**★7.8D 空间残差边界（保留不藏）**：`FINAL_SPATIAL_RESIDUAL_BOUNDARY.csv` **55 行**（region 5 / radial 3 / PA 37 / 关键 PA 10）；EAST **−31.75%**、`radial_in` **−30.67%**、NE **+33.88%**、ORCHARD **+142.00%**、BUKIT TIMAH **+138.61%**、TUAS **−86.99%**、HOUGANG **−86.98%** ⇒ **不使用「失败项」措辞**，而是 **Final Model — Known Spatial Residual Boundary**，状态 `UNRESOLVED_STRUCTURAL_LAYER`；归因三类继承 7.7D。**★7.8E Manifest**：`model_version=Singapore_OD_MATSim_Final_v1.0` + 14 件冻结输入 sha256 证据 manifest（`manifest_self` 说明自身 hash 不含以免循环）。**★#168 完整性门 23 条全 PASS**：G1–G7 冻结真值逐位/容差一致、G8 config 继承 7.6E 四项、G9 运行控制、G10–G11 输入存在、G12 正 cell **71,136**、G13 `car_od_total` **459,794**、G14 三层带未合并、G15 空间残差仍在、G16–G19 上游判决一致、G20 纪律、G21 六件产品落盘、**G22 全部 14 件冻结输入跑前后 mtime+sha256 逐位未变（read-only 硬证据）**、G23 `W01` it.19 产物存在。**★停止规则**：7.8 完成 **STOP**；后续若继续研究 = **7.9 Structural Repair / Model v1.1**（新研究问题），⛔ **非**「继续把 v1.0 的 `Sim/Obs` 从 0.9993 调到 1.00」。**★本步自查 2 处脚本缺陷**：① G6 曾以**发布用四舍五入常量**（0.8589732）配逐位比较 ⇒ 改为按 7.6C-2 自声明 `tol=1e-6` 并保留全精度真值（Δ **4.331e-08**）；② G21 曾在 manifest 自身写入**前**扫描产品 ⇒ 改为落盘后**两遍写 + 全量重扫**（`products` 仅列非自身 5 件）。**新增产物** `reports/final_model_7_8/`（9 件） |
| 2026-09-19 | **Step 7.7D 空间残差归因收口完成 → 判 `SPATIAL_RESIDUAL_ATTRIBUTION_CLOSED_WITH_UNRESOLVED_STRUCTURAL_LAYER`（硬门 7/7 + 软门 2/2；零仿真）** —— **★收口审计（非新模型、不造新变量）**：把 7.6H/7.7A/7.7C-0/7.7C-1 串成可关闭归因链。10 门全 PASS（W01 锚点逐位 / C0↔W01 tol 1e-12 / f span 1.85 pp / λ span 3.23 pp / `radial×reciprocal` 闭环 / temporal ratio 0.1104 / 构成排除 6/6 / 排除层 η²_excess ≤ .001）。**★适配器修正**：预置版用**占位路径**致 6/8 门**假 BLOCKED**（证据其实都在）⇒ 仅改数据接入（路径/列/机会校正指标），**判定阈值与判决串一律未改**；原版存 `.user_orig_backup`。**★两条 bug 自查**：① G2 曾用四舍五入常量配 `1e-12` 容差（改为对 7.6H 实测真值逐位）；② G5 补充证据曾因 `pd.read_csv` 把 `True/False` 解析为 **bool** 而误判 C1 全部 profile 不稳定（`astype(str)` 修正后 **7/7 稳定**）。**结论边界**：不证明 twin/directionality 为因果机制，仅证明其余层不足 ⇒ 问题收缩到结构层 |
| 2026-09-19 | **Step 7.7C-1 时段实现敏感性完成 → 判 `TEMPORAL_SPATIAL_SENSITIVITY_FAIL_DEFER_HTS`（零仿真；7/7 校验）** —— **★方法学修正**：初版脚本以「**全局标量**」`share_8_9` 作乘子 ⇒ 所有断面同乘一系数 ⇒ `rel_dev_g` 数学**恒等不变**（`P1_UNIFORM` Δ 逐组 = **0.0000**），属退化设计、**无法回答空间敏感性**；**改为断面级 temporal shape**（`sim_8_9(s|P)=sim_8_9_scaled(s)×share_8_9(s|P)`，取 6.3.3A 冻结底表 `trafficflow_link_hour_basis.csv`，CV **0.0909**）。**★效应分离**：水平效应（全局 Sim/Obs **0.9993→0.4972**）vs 结构效应（`rel_dev_g`）。**★7 profile**：P0 / P1(退化参照) / P2(断面级) / P3(外推×2) / P4(结构镜像) / P5,P6(日级 p10/p90 可行带)。**★P0 MUST_MATCH 7.6H 逐位**（0.9993348；EAST −0.317524 / NE +0.338833 / `radial_in` −0.306727）。**★gate**：`S_spatial`=0.3388 vs `A_temporal`=0.0374 ⇒ **ratio 0.1104 < 0.20 ⇒ FAIL**（全组 0.0924）；**region/radial 排序在 7/7 profile 下严格保持**。⛔ **HTS 暂不接入 MATSim**（除非需检验 departure×route-choice×congestion 耦合）。详见 §2.43 |
| 2026-09-19 | **Step 7.7C-0 空间残差归因基线审计完成 → 判 `RESIDUAL_LOCALIZED_TO_PA_LOCATION`（零仿真只读；14/14 校验；173.8 s）** —— **7.7C 拆两层**（用户裁定：先 7.7C-0 再 7.7C-1，**不直接进 7.7B/HTS**）。**★六维归因**：① OD 空间供需（`A/P` vs 残差 ρ=−0.70，但 **EAST 反例**）② 方向性（`radial_in −30.67%` vs `radial_out +14.50%`，跨 f/λ **8/8 稳定**）③ 道路等级（`motorway` 0.9922，**η²_excess=−0.0069 排除**）④ **`has_reciprocal_pair`**（True 0.3711 / False 1.2035，2 组 η²_excess **0.1423**）⑤ 长度归一化（极差 33.88%→42.49%，**反而扩大**）⑥ PA 梯度（`od_outflow` ρ=−0.40）。**★核心交叉表**：`radial_in\|recip=False`（130 断面, 18.6% obs）= **0.9915 ≈ 1.000**；`radial_in\|recip=True` = 0.1738（−82.6%）⇒ **twin 表征 + 方向性两机制独立可加**。`MUST_MATCH_BASELINE` 逐位复现 7.6H（8.674e-17）。产物 `reports/spatial_residual_7_7c0/` |
| 2026-09-19 | **Step 7.7A 入场审计完成 → 判 `VEHICLE_TYPE_VOLUME_UNAVAILABLE` / `COMPOSITION_EXPLAINS_GLOBAL_LEVEL_NOT_SPATIAL_PATTERN`（零仿真只读；6/6 校验）** —— **7.6 正式收口**（`W01`=236,044 为正式独立验证基准；**取消同口径 200k 复跑**）。**Q1**：`TrafficFlow_Data.json` **字段全集 10 个**、`Volume` = 全部机动车合计（无车型字段）⇒ 车型不可分解；LTA DataMall 端点清单**无**分类计数端点；`data.gov.sg` 仅**全国年度车队构成**。**Q2 零成本先验**：Census 2020 Table 104 方式构成 vs 7.6C/H 区域与 PA 空间残差 ⇒ region r=**−0.3600**、PA r=**+0.2533**（R²=**0.0641**），构成极差（17.1 / 36.5 pp）仅为残差极差（65.6 / 206.4 pp）的 **1/3.83 ~ 1/5.66**。**全域 `car_share_pmv = 0.682452` 与 7.6A D01 断面 `Sim/Obs = 0.6830` 差 0.07%** ⇒ **车型构成解释总体量级、不解释空间分布**。⇒ 空间残差在 **f / λ / 车型构成三方向同时不敏感**，定位到 OD 空间结构 / 观测口径 / 网络表征 / 时段实现。产物 `reports/external_validation_7_7/`。**未启动 MATSim、未取外部数据、未改冻结件**。 |
| 2026-09-18 | **Step 7.6H 完成 → 判 `WORKING_POINT_FROZEN_AND_REPRODUCIBLE / SPATIAL_RESIDUAL_PERSISTS`（`W01` 单跑 `exit=0`，**102.22 min**，iters 20/20；零仿真评价 **26/26 校验 PASS**）** —— **第一层冻结**：`λ_ref=0.075` / `f_demand,ref=1.180222` / `SCALE=2.29897` / `f_cap=1.00` / `R01_rc_min` / 7.3.6A crosswalk / `N_base=200,000`；**第二层一次独立验证**：`W01`（λ=0.075，**N_sim=236,044**，ΣEF 542,628.837，`f_realized` 1.1801564）。**★H1 可复现**：`Sim/Obs FROZEN` **0.999335**（Δ **0.0665 pp**），隐含 `f*` **1.180866** vs 1.180222（Δ 6.44e-4），vs 7.6G `L75` Δ **0.0494 pp**。**★H2 稳定**：`A_10:19`(M/C/S) **0.8899/0.9038/0.8568%**、`parity_gap_rel` **0.0964%**、`Q19/Q̄` **1.001972**（Δ 0.1972%）、**`never_arrived=0` / `max_stuck_car=0`**。**★H3 空间残差仍在**：8 组 max \|Δ vs `L75`\| = **0.7599 pp**（格局保持，≤2.0 pp）；EAST **−31.75%** / `radial_in` **−30.67%** / NE **+33.88%** / CENTRAL −7.82% / NORTH +23.09% ⇒ **不追求消除**。**★H4 三层带独立、未合并**：工作点 `f*` **1.180222** / λ 敏感带 **[1.1637,1.1938]** / 静态靶场带 **[1.06945,1.16418]**。**★H5 未解决**：量级达标、空间残差对 demand/λ 低敏感 ⇒ 不宜强行消除；三项本地不可定量。**★对账**：X1 R01 三口径 vs 7.6C-2（Δ ≤ 4.9e-8）+ X2 `Q̄_10:19` 四口径 vs 7.6D 缓存（**Δ = 0.00e+00**）；SCALE 审计 R01 **0.00 ppm** / W01 **−53.88 ppm**（仅披露 **NOT USED**）。**★本步修 2 个自身缺陷**：① `stab` 子字典键名笔误 `A_10:19`→`A_10_19`（致 `KeyError` 中止）；② `runtime_sec` 字段声明却恒为 `None` ⇒ 计时移入 `main()` 后落盘 |
| 2026-09-18 | **Step 7.6G 完成 → 判 `LAMBDA_DETECTABLE_NOT_IDENTIFIABLE / SPATIAL_INERT`（评价零仿真只读；**21/21 校验 PASS**；823.1 s）** —— 三档仿真全部 `PASS`：**L05 77.36 min / L75 81.63 min / L10 77.01 min**（累计 **3.93 h**，串行），各 `exit=0`、**20/20 迭代**、`it.19` linkstats 齐备、**config sha256 运行前后逐字节一致**。**★机制前提**：λ 作用在 **OD 构造层**（5C1→6.2B→6.3.3A→人口文件），**config 内无 λ 形参**；**λ 不变性**（`ΣT`(5C1) **1,935,235** / `car_od_total`(6.2B) **459,794** / `ΣEF`(6.3.3A) **459,794.0000** 三档**逐位相同**）⇒ **`SCALE = 2.29897` 天然 λ 不变**，用户「不得按 ΣEF 重算 SCALE」**自动满足**；三份 200k λ 冻结人口已存在 ⇒ **无需上游重建**（用户担心的 3×4=12 跑网格**塌缩为 3 跑**）。**★λ 响应（MATCHED, 08-09, f≡1.18, N_sim=236,000）**：`Sim/Obs FROZEN` **1.0125538（λ=0.05）→ 0.9998291（0.075）→ 0.9893922（0.10）**，**单调**（G9 登记）；**Δ(0.05→0.10) = −2.3162 pp**（`POSITIVE_ONLY` −2.4249 / `BEST_DIRECTION` −2.4127，三口径极差 **0.1087 pp**）⇒ **隐含 Δf\* = +0.03015**（λ 全跨度仅把 demand scale 移动 **±0.0151** ≈ f\* 的 **1.3%**）。**★★直跑复核 7.6F-1 插值点**：**`L75 = λ0.075 @ f=1.18` 实测 0.9998291 ⇒ 隐含 f\* = 1.180222**，与 7.6F-1 线性插值 **1.1803 相差 0.007%** ⇒ **插值可信度被直跑证实**（并纠正用户表中「λ=0.075 @ f=1.18 已有」的事实错误：7.6F-1 只跑过 **1.00/1.05/1.15/1.25**）。**★判决定位**：\|Δ\| = **2.3162 pp** **> 噪声底 1.0 pp**（**可检出**）但 **< 靶场自身辨识下界 7.609 pp = 7.6C-2 `Delta_target`**（**不可辨识**）⇒ 按预注册 **Case A**：**λ = 0.075 保持为「敏感度中心 / 基准」取值，不得声明为数据最优 λ**；**7.6H 出两层结果**（点估计 @ λ=0.075 ＋ λ 不确定带 **[1.1637, 1.1938]**）。**★★空间残差几乎不随 λ 变化**：EAST 极差 **0.9051 pp** / `radial_in` **0.3960 pp** / CENTRAL **0.0034 pp**（而 EAST 缺口为 **−31 pp 量级**）⇒ **`SPATIAL_INERT`**；λ 最强处＝**远端**（NORTH-EAST **1.7904 pp** / NORTH **1.4885 pp**），与「λ 惩罚长距离 ⇒ 主要动远端 OD」机制一致；对照 7.6F-1 demand 方向（EAST 1.05 / `radial_in` 2.16 pp）⇒ **λ 与 demand 移动力同量级且都远小于缺口** ⇒ **「全局量级 ⊥ 空间结构」在 λ 维度再次成立**。**★稳定性承继**：`A_10:19`(MATCHED) **0.8461% / 0.9971% / 0.9724%**（均 < 1%）、`parity_gap_rel` ≤ **0.1496%** ⇒ **7.6E `STABILITY_PASS` 在 λ 维度继续保持**（G5/G6 PASS）。**★口径未漂移硬证据**：**7.6C-2 对账 3/3 全中**（tol 1e-6）＋ **7.6D 缓存对账 4/4 全中**（tol 1e-9，**Δ = 0.00e+00 逐位相等**：4,567,961.5 / 68,252,699.5 / 3,210,503.5 / 1,357,458.0）；**`SCALE` 审计**：全档统一 **2.29897**，`ΣEF/N_sim` 重算值**仅披露 NOT USED**（L05 **+4.30** / L75 **−66.16** / **L10 −517.93** ppm）。**★本步修复两个缺陷**：①7.6G 评估器把**逐迭代原始表** `routechoice_stability_by_iter.csv`（**无 `metric` 列**）误当聚合表读 ⇒ 静默 `KeyError: 'metric'` 跳过对账；改为复用 7.6F-1 的 **C2** 写法（取收敛窗 **[10,19]** 列均值）＋ 补 `encoding="utf-8-sig"` ⇒ 对账恢复并 **4/4 逐位相等**；②评估器 `artifacts` 声明了 `STEP7_6G_REPORT.md` 但**从未渲染** ⇒ 新增 `write_report()` 并由冻结 `summary.json` 渲染成文。**★判据 P1–P7 + X1(3) + X2(4) + G1/G5/G6/G7/G8/G9 + P1b 全 PASS（21/21）**。**新增** `scripts/od/{prepare,run,evaluate}_lambda_sensitivity_7_6g.py`；**新增** `matsim_lambda_7_6g/{configs, populations, outputs, logs, audit}`。**★未选 λ（`lambda_selected=False`）/ 未选 demand scale（`demand_scale_selected=False`）/ `parameters_changed=False`（只改被仿真 agent 数）** |
| 2026-09-18 | **Step 7.6G 正式点火 → 状态 `RUNNING`（用户裁定启动：实验主线改为 7.6F-1 → 7.6G → 7.6H）** —— 用户裁定：demand scale 由「不可辨识」→「**条件可辨识**」，**不直接进最终 200k 验证**；7.6G 只跑 **λ ∈ {0.05, 0.075, 0.10} × 单一 demand level f = 1.18**（**不做** 3×4 网格 / **不做** crosswalk-b / **不做** demand 细扫），中心问题 = **λ 是否改变 f\***；**7.6F-1 的 f\* = 1.1803 只是 λ=0.075 下的条件估计，不得冻结为最终 demand scale**。点火器 `run_lambda_sensitivity_7_6g.py --experiments L05 L75 L10 --heap 24g`（**串行**，约 4.3 h）。★用户表中把「λ=0.075 @ f=1.18」标为「已有/基准」**与事实不符**（7.6F-1 只跑过 1.00/1.05/1.15/1.25）⇒ 采用**方案 A：真跑 L75 @ f=1.18**，兼作**响应曲线可复现性 + 插值可信度对照** |
| 2026-09-18 | **Step 7.6G 入场准备完成 → 判 `PREPARED`（零仿真；**72/72 校验 PASS**）** —— 侦察确认 **λ 是 OD 构造层参数、不是 MATSim 运行参数**（config 内无 λ 形参），且**三份 200k λ 冻结人口已在 `reports/matsim_departure_6_3_3a/`** ⇒ 7.6G **无需上游重建**，只需复制 agent 到 236,000 + 换 config ⇒ 把「3×4 = 12 跑」**塌缩为 3 跑**。**λ 不变性经验证**：`ΣT` 1,935,235 / `car_od_total` 459,794 / `ΣEF` 459,794.0000 三档逐位相同 ⇒ SCALE **天然 λ 不变**（用户「不得按 ΣEF 重算」自动满足）。**零成本先验（legacy `matsim_assignment/lambda_0p*/` it.0 旧配置，仅作效应量先验、非 7.6G 口径）**：pooled Sim/Obs Δ(λ 0.05→0.10) 仅 **+0.5291 pp**、Σ(HRS8-9avg) **−0.0786%**（非单调）⇒ **先验预期 `LAMBDA_WEAK`**；**实测证明先验连方向都错了**（实测 **−2.3162 pp**、单调）⇒ **再次验证「必须实测、不得据先验下判」**。**新增** `scripts/od/prepare_lambda_sensitivity_7_6g.py` + `matsim_lambda_7_6g/{configs, populations, STEP7_6G_PREREGISTRATION.md}`（三档 config 与 R01 差异**恰 3 项白名单**：`outputDirectory` / `runId` / `inputPlansFile`） |
| 2026-09-17 | **Step 7.6F-1 完成 → 判 `RESPONSE_STABLE_CROSSES`（评价零仿真只读；**21/21 校验 PASS**；516.3 s）** —— 三档**物理加车**仿真全部 `PASS`：**F05 69.73 min / F15 80.40 min / F25 75.74 min**（累计 **3.76 h**，串行；本机 63.7 GB RAM、24g/run ⇒ 并行必 OOM），各 `exit=0`、**20/20 迭代**、`it.19` linkstats 齐备、**config sha256 运行前后逐字节一致**。**★响应曲线（MATCHED，08-09；Primary = 收敛窗 it.10–19 周期均值）**：`Sim/Obs FROZEN` **0.8589732（f=1.00）→ 0.8994456（1.05）→ 0.9767361（1.15）→ 1.0535647（1.25）**，**单调不减**（增量 +0.04047/+0.07729/+0.07683）且**跨越 1.000** ⇒ `RESPONSE_STABLE_CROSSES`。**★三口径跨越点（Sim/Obs=1 线性插值）**：`FROZEN` **f\* = 1.1803** / `BEST_DIRECTION` **1.1320** / `POSITIVE_ONLY` **1.0748** ⇒ **与 7.6C-2 由 `Delta_target` = 7.609 pp 推出的 `f*` 区间 [1.06945, 1.16418] 自洽**（后两者在区间内、主靶场仅高出上界 **1.4%**）⇒ **几何预测与动态仿真闭合**。**★稳定性承继**：`A_10:19`(MATCHED) **1.0009% → 1.0132% → 0.9157% → 0.7833%**、`parity_gap_rel` **0.1349% → 0.0455%** ⇒ **加车使收敛更好**，G1 PASS。**★算术参照与拥堵阻尼比**：`ρ(f)` = **1.000000 / 0.997255 / 0.988780 / 0.981232** ⇒ 200k→250k **几乎无阻尼**（f=1.25 仅 1.88%）⇒ 全局量级缺口**基本可由加车补齐**（与 8-9 过饱和份额恒 0% 一致）。**★★空间残差不随 demand 变化（决定性证据）**：EAST `rel_dev` **−32.20% → −32.43% → −31.97% → −31.38%**、`radial_in` **−28.80% → −29.38% → −30.34% → −30.96%**，四档极差仅 **1.05 / 2.16 pp** ⇒ **demand 缩放无法压平空间结构缺口：全局量级与空间结构是正交问题**，**正面确认 7.6C-1**「EAST/`radial_in` 残余低估 = 真实结构 + 细粒度链路归属」，并**证明**「用调 `f_demand` 压平区域偏差」是错误路径（G6 仅要求报告、不得优化）。**★口径未漂移硬证据**：**7.6C-2 对账 3/3 全中**（0.8589732 / 0.9350621 / 0.8909674，tol 1e-6）+ **7.6D 缓存对账 4/4 全中**（R01 `Q̄_10:19` MATCHED/ALL/CATA/SLIP = 4,567,961.5 / 68,252,699.5 / 3,210,503.5 / 1,357,458.0 **逐位相等**）；**★`SCALE` 冻结审计**：全档统一 **2.29897**（`ΣEF/N_sim` 重算值仅披露 **NOT USED**：F05 −397.69 / F15 −56.03 / F25 −56.32 ppm）。**★判据 G1/G2/G4/G5/G6/G7 全 PASS**。**新增** `scripts/od/run_demand_response_7_6f_1.py`（**本项目唯一**会启动 MATSim 的 7.6F-1 脚本：sha256 前后钉扎 + 断点续跑 + manifest）；**新增** `matsim_demand_7_6f_1/{outputs/F05|F15|F25_rc_min, logs, audit}`（含正式报告 `STEP7_6F_1_REPORT.md`）。**★未选 demand scale（`demand_scale_selected=False`）/ 未评价 λ（`lambda_selected=False`）/ `parameters_changed=False`（只改被仿真 agent 数）** |
| 2026-09-17 | **Step 7.6F-1 正式点火 → 状态 `RUNNING`（用户 20:17 作出启动许可 + 追加硬约束）** —— 用户**确认采用「物理加车」解释**，不再采用「200k agents 不变、只做算术倍乘」。**三个量正式区分**：`200,000` = **冻结的采样基准 / SCALE 分母**（不改）／`210k / 230k / 250k` = **QSim 中真正参与交通分配的车辆数**（`= f × 200,000`）／`2.29897` = **每个模拟 agent 对应的 OD 扩展权重**。与 6.2B 人口实现逻辑一致：`expansion_factor` 用于**在统计上恢复冻结 OD**，而**不是**代替 QSim 中真实车辆数；`ΣEF` 随复制 agent 增加而增加，而**平均 EF 基本不变**。**★追加硬约束（用户原话）**：「**不得根据 F05/F15/F25 的 `ΣEF` 重新计算 SCALE；三档统一使用冻结基准 `SCALE = 2.29897`**」—— 否则会把「增加真实车辆数」与「改变扩展权重」混成两个不同的 demand 操作。**已实装为机器校验 + 审计产物**：点火器全档注入 `SCALE_FROZEN = 2.29897`；评价器新增 **P1b/P1c** 硬断言并落盘 **`demand_response_7_6f_1_scale_audit.csv`**，「若按 `ΣEF/N_sim` 重算」的偏离**仅作披露、一律 NOT USED**：R01 **0.00** / F05 **−397.69 ppm** / F15 **−56.03 ppm** / F25 **−56.32 ppm**（全部源于 6.2B `FLOOR_PLUS_1` 保底取整，量级 1e-4 相对值，**不改变任何结论**）。**★`f_realized` 如实报告，不四舍五入**：`1.0495824 / 1.1499356 / 1.2499296`。**★新增点火器** `scripts/od/run_demand_response_7_6f_1.py`（本项目**唯一**会启动 MATSim 的 7.6F-1 脚本）：点火前对 config 做 **sha256 钉扎**、运行后再哈希断言**逐字节未变**（被执行的 = 被验证的）；点火前逐档**重跑 `prepare.validate()`（18/18 × 3 档 PASS）**；**断点续跑**（`it.19` linkstats 存在即跳过）；写 `demand_response_7_6f_1_run_manifest.json`（exit code / wall min / iters / sha256 前后 / heap / MATSim 运行时描述）。**★串行而非并行（RAM 硬约束，本轮实测）**：本机 **63.7 GB RAM**（点火时可用 **38.1 GB**）、28 逻辑核，而 100k+ 档需 `--heap 24g`（12g 曾在 it.2/it.5 `PlanRouter` 被硬杀）⇒ 三档并行需 ≥72 GB **必 OOM**；故串行，预计 ≈**88 / 94 / 100 min**（200k 实测 84.41 min 外推），合计 **≈4.7 h**。**★点火记录**：**2026-09-17 20:19** 前置核验 **18/18 × 3 档 PASS**、config sha256 钉扎完成；**20:19 F05 点火**（210k agents / 24g heap / 20 it → `outputs/F05_rc_min/`）；F15 / F25 待 F05 完成后依次点火。**预注册同步更新**（`STEP7_6F_1_PREREGISTRATION.md`）：§0 机制门标记**已解除**、§7 增加「不用各档 `ΣEF/N_sim` 重算 SCALE」、**新增 §11 启动许可与追加硬约束**。**未改任何模型参数（只改被仿真 agent 数）；未选 demand scale / 未评价 λ；`f_cap=1.00` / λ 0.075 / crosswalk 7.3.6A Frozen / route-choice `R01_rc_min` 逐项保持**。readme 新增 **§2.37**、脚本清单 +1 行（`7.6F-1-R`）、§3.1 +1 行、路线图 +1 节点 |
| 2026-09-17 | **Step 7.6F-1 入场准备完成 → 判 `PREPARED`（零仿真；**67/67 校验 PASS**）；★正式 run 未启动，等用户明确启动指令** —— 按用户裁定正式进入 7.6F-1，采用修正网格 **`f = 1.05 / 1.15 / 1.25`**（落在 7.6C-2 的 `f*` 区间 `[1.06945, 1.16418]` 的**下方 / 内部附近 / 上方**，信息利用率高于原 `1.10/1.20/1.25`）。**★机制门（预注册 §0，需用户在启动前确认）**：用户冻结清单同时给出 `N=200,000` 与 `f_demand`，**二者不是同一个量** —— `N` 是**采样基准 / `SCALE` 锚**（冻结，不改），被仿真的 agent 数 = `f×200,000` = **210k/230k/250k**。三条闭合论证：① 7.4.3 已证只缩放 `expansion_factor`/`od_trips` 而**不动 agent 数**是对仿真的 **no-op**（三份 linkstats 完全相同，跑 MATSim 无信息）；② `f_cap=1.00` 冻结（而非 `N/200,000`）**排除** 7.6D-S 的「采样一致」约定、**锁定** 7.4.3 的「**物理加车**」约定；③ 复制 agent 会连 `expansion_factor` 一并复制 ⇒ 平均 EF 不变 ⇒ `SCALE = 459794/200000 = 2.29897` 对三档**全部适用**（7.6F-0 分解表实证 D01–D04 SCALE 恒 2.29897）。**若用户意图是「agent 数恒 200,000、仅改算术倍数」，则本步应完全不跑 MATSim，改在 R01 上做零仿真算术重标定（Sim/Obs 精确 × f）—— 已在预注册 §0 显式请用户启动前确认**。**★三档人口（`seed=20260912` permutation 前缀嵌套随机子集复制，F05⊂F15⊂F25）**：实测 persons = 210,000 / 230,000 / 250,000、ΣEF = **482,591.7 / 528,733.5 / 574,710.1**、`f_realized` = **1.0495824 / 1.1499356 / 1.2499296**；**★F25 与 7.4.3 `D04` 人口解压后逐字节一致**（sha256 前缀 `49ff7ccbe622770`）⇒ 复制管线可复现。**★配置验证 67/67 PASS**（P1–P9 + W1–W6）：与 **R01 config** 差异**仅限** `plans.inputPlansFile` + `controller.{outputDirectory,runId}`，零白名单外 diff；route-choice 4 项（innovation 0.8 / `[ReRoute 0.15, ChangeExpBeta 0.85]` / lr 0.5 / randomness 0.0）继承 7.6E；`f_cap=1.00` / seed 4711 / λ 0.075 / `MUST_MATCH_R01` 19 项逐值相同；**P9 断言 8 个冻结件 mtime 全部未变**。**★预注册落盘** `STEP7_6F_1_PREREGISTRATION.md`：G1–G7 判据（G1 稳定性承继 / G2 单调性为**硬门槛**；G3–G4 诊断；G5–G7 纪律）+ 判决空间 `AWAITING_RUNS` / `RESPONSE_UNSTABLE` / `RESPONSE_NON_MONOTONIC` / `RESPONSE_STABLE_PARTIAL` / `RESPONSE_STABLE_CROSSES`。**★评价器零仿真自检**（`evaluate_demand_response_7_6f_1.py`，网格未齐 → `AWAITING_RUNS`）**与 7.6C-2 / 7.6D 审计缓存对账 7/7 全中**：R01 三口径 **0.8589732 / 0.9350621 / 0.8909674**（逐位复现 7.6C-2）、`Q̄_10:19`(MATCHED/ALL/CATA/SLIP) = 4,567,961.5 / 68,252,699.5 / 3,210,503.5 / 1,357,458.0（**逐位等于 7.6D 缓存**）；R01 锚点 `A_10:19`(MATCHED) = **1.0009%**（<3% ✓）、空间残差 EAST **−32.20%** / `radial_in` **−28.80%** / NORTH-EAST **+34.80%**（与 7.6C-1 逐值一致）。**新增** `scripts/od/prepare_demand_response_7_6f_1.py`（980 行，零仿真入场准备 + 67 项校验 + 预注册落盘）与 `scripts/od/evaluate_demand_response_7_6f_1.py`（预注册分析）；**新增** `matsim_demand_7_6f_1/`（3 config + 3 人口 + 4 件 provenance/validation + 预注册 + `audit/`）。**未启动任何 MATSim 仿真**（`outputs/` 与 `logs/` 为空）；**未选 demand scale / 未评价 λ / 未改 grid 以外的任何冻结件**。readme 新增 **§2.36**、脚本清单 +2 行、§3.1 +1 行 |
| 2026-09-17 | **Step 7.6C-2 Calibration Target Integrity Gate 完成 → 判 `TARGET_MARGINAL_COARSE_ONLY`（零仿真只读；判据 7/10；16.7 s）** —— 按用户裁定**不启动 7.6F-1**，先判「当前 7.3.6A frozen crosswalk 是否仍有资格做 demand scale 的**绝对**识别」。**三口径**`FROZEN` 0.8589732 / `POSITIVE_ONLY` 0.9350621 / `BEST_DIRECTION` 0.8909674（+ 最近有流 0.8205206 与 同名有流 1.0645964 外包络）。**`Delta_target` = 0.9350621 − 0.8589732 = **7.609 pp**；**f\* 识别区间 [1.06945, 1.16418]**（`Delta_f_target` = **0.09473**）。**★信噪比（复用项目自己的“SNR < 1 ⇒ 不可用于推断”）：粗档 1.10→1.20 **SNR 1.056 ✓**（需 ε ≥ 0.947）；细档 1.20→1.25 **SNR 0.528 ✗**（需 ε ≥ 1.895；而 8-9 过饱和份额恒 0% ⇒ ε ≈ 1 是物理预期）**⇒ **靶场不确定性与粗档 demand 增量同量级**。**★对 7.6F-1 的直接后果**：`1.10/1.20/1.25` **未跨越** f\* 区间；**f = 1.10 落在区间内部 ⇒ 结论随口径而变**；1.20 与 1.25 均在区间之上且三口径一致越 1.0 ⇒ **3 次跑只买 2 个区制**；**建议网格 `1.00/1.10/1.20` 或 `1.05/1.15/1.25`**（间距 0.10 ≥ `Delta_f_target`）。**★结构可分性 7.33×（≥ 5）** ⇒ 7.6C/7.6C-1 结构结论**不受靶场不确定性污染**；EAST 相对亏损 −0.3220 是 `Delta_target` 的 4.23×。**★断面集口径澄清（本轮新发现）**：7.3.6A crosswalk = **576 断面 / 574 primary candidate / 3,015 条 primary 去重匹配链**（全 crosswalk **3,037**）；而 7.6C `section_geography.csv` 只覆盖 **574**（缺 `190339 YIO CHU KANG ROAD`、`195768 PAN ISLAND EXPRESSWAY`，两者 obs/sim 均 > 0）⇒ **7.6C-1 的 repair-bounds CSV 内部 `dropna` 后实际按 574 计算**，与其自身 “anchor” 行（576）相差 **4.06e-4**；本步主口径统一取 **576** 并分开复现 **574**（**交叉校验 7/7 全中**）；574 子集稳健（`Delta_target` **7.619 pp**、SNR **1.053 / 0.527**）⇒ **结论不变**。**★硬约束**：「发现校准靶场存在可修正伪影」**≠**「已允许修改冻结靶场」；后者必须**另立版本（7.3.6A-b）、另留证据链**。**新增** `scripts/od/audit_target_integrity_7_6c_2.py`；**新增** `reports/od_target_integrity_7_6c_2/`（8 产物 + 正式报告）。**未启动任何 MATSim 仿真；未改 crosswalk / OD / λ；未选 demand scale / 未评价 λ** |
| 2026-09-17 | **Step 7.6C-1 异常归因追踪完成 → 判 `MIXED_COVERAGE_AND_RESIDUAL_STRUCTURE`（零仿真只读；判据 5/5；校验 6/6；78.3 s）—— 把 7.6C 的「覆盖缺口 vs 真实缺口」追问到**链路级**，首次证明 8.14% 的硬零流是测量伪影、而 graded 区域/径向缺口是真实结构**。按用户裁定走 **`7.6C-1 → 7.6F-1`**（不是 `7.6C → 7.6F-1`）。**Layer 1**：13 个 R5/radial_in 零流断面**全部在 WEST（TUAS/PIONEER）**，47 条匹配边**三窗口 × 正反向全 0**、**43/47 有向拓扑孤儿**（参照 0.987/0.991）、**0/47 连通**，而 400 m 邻域有 **1,559–39,762 veh/h**；**54/54 零流断面 100 m 内有有流平行链、52/54 在 60 m 内**；机制 `CROSSWALK_TWIN_ORPHAN` 31 / `DIRECTION_MISMATCH` 13 / `WINDOW_ARTIFACT` 8 / `GENUINE_UNROUTED` **仅 2**。**Layer 2**：EC 不对称 **0.2112** 正常、Table118 中位 **0.0026**、EC 实走路径 **64.25% `radial_in`**（99.2 东走廊链次/出行）⇒ **吸引量 / OD 方向 / 路径改道三假设全否证**。**新增** `scripts/od/audit_anomaly_trace_7_6c_1.py`；**新增** `reports/od_anomaly_trace_7_6c_1/`（13 个产物 + 正式报告）。**未启动任何 MATSim 仿真；未选 demand scale / 未评价 λ** |
| 2026-09-17 | **Step 7.6C OD 空间结构诊断完成 → 判 `OD_STRUCTURE_PARTIAL`（零仿真只读；23/28 校验；79.5 s）—— 冻结 OD 的「形状」首次被独立检验，与「绝对规模」问题刻意解耦**。用户裁定**先 7.6C、再决定 7.6F-1**（避免把 phase noise / 空间结构缺口误读成 demand 响应）。**新增** `scripts/od/diagnose_od_spatial_structure_7_6c.py`（三轴：距离结构 / 空间集中 + 缺口空间结构 / 路由前后一致性；import 冻结模块保证口径同源；**窗口纪律 `HRS8-9avg` vs `ΣHRS0-24avg` 永不混用**；空间归属用 link MIDPOINT → 最近 zone 质心）。**★结构可信**：Table118 物理格 中位残差 **0.0026**；**0 个 `|z|>5` 异常吸收区**；**detour 1.068–1.111**（plan 与 linkstats 独立互证）；**采样偏差 0.00 pp**；质量守恒到浮点精度。**★S4 不通过**：缺口**不均匀且具方向性** —— **EAST 0.582 / NORTH-EAST 1.158**（区域偏差 **0.348 > 0.25**）、**radial_in 0.612 vs radial_out 0.976**、**R5 radial_in 13/13 断面零仿真流**、**54 断面 sim=0 却占 8.14% 观测**（剔除后全局 0.8590→**0.9351**，但区域偏差仅降到 **0.333** ⇒ 结构性成分真实存在）。⇒ **`0.8590` 不是干净的规模因子**；**未选 demand scale / 未评价 λ / 未启动任何 MATSim 仿真**；**未改动** 7.1 / 7.3.6A / OD / network / capacity / 6.2B 人口 |
| 2026-09-17 | **Step 7.6F-0 新稳定分配底座上的 demand = 1.00 基准重算完成 → 判 `PASS`（零仿真只读；20/20 校验）—— ★route-choice 层冻结后「demand scale 不可评价」的禁令正式解除，demand-scale 讨论第一次有资格开始**。用户裁定把 7.6F 拆两层：**先零仿真复核（本轮）再决定是否补跑 D02–D04**，避免再一次 3 × 85 min 的盲目实验。**新增** `scripts/od/evaluate_demand_scale_7_6f_0.py`（import 冻结模块保证口径同源；把**双口径**统一施加到全部对照 run；构造 7 个 run 的收敛窗周期均值 linkstats 并复用）。**★新基准点**：R01（demand=1.00，200k，f_cap=1.00）Sim/Obs(08-09) Primary **0.8590** / Reference 0.8603 / AM 0.7665；CATA 0.8717 / SLIP 0.7889 / CATA/SLIP **1.1050**；WMAPE 0.6310 / GEH<5 0.1163 / Pearson 0.3365。**★★机制分解（固定 demand=1.00、同 N、同 f_cap，仅 route-choice 变）**：200k **0.7506 → 0.8590（+14.43%）**、100k **0.8169 → 0.9639（+18.00%）** ⇒ **同向、量级接近 ⇒ 机制签名**；而 `Σ(cycle-mean HRS0-24avg|MATCHED)` 仅 **+3.11%** ⇒ **断面流量位移 ≠ Sim/Obs 位移（4.6×）** ⇒ **「×(1+δ) 修正因子平移旧曲线」被定量否证**（分配层是**空间重分配**：MATCHED +9.28% vs ALL −3.70%，反单调）。**★旧 D01–D04 响应谱判 `LEGACY_CURVE_UNINFORMATIVE`**：统一 Primary 口径后非单调、内部极差 0.0587 vs 四点振幅均值 0.1579 ⇒ **信噪比 0.372 < 1**；新基准点 0.8590 **高于旧谱全部四点**（最高 0.7655）；`it.19` 相位偏移最高 **+12.35%（D03）**（与 7.6B 的 +12.47% 一致）⇒ 旧「非单调」确认是相位伪影。**未选 demand scale / 未评价 λ / 未进入 7.6C**；**未改动** 7.1 / 7.3.6A / OD / network / capacity / population / route-choice 任何冻结件 |
| 2026-09-17 | **Step 7.6E 200k 正式稳定化完成 → 判决 `STABILITY_PASS`（G1–G6 6/6 全过）⇒ ★route-choice 层正式冻结**（`exit=0`，**84.41 min**，linkstats 20/20，≈4.2 min/it）。`R01_rc_min` = 200k × 20 it、`f_cap=1.00`，**唯一变量 = route-choice 4 项**（`fractionOfIterationsToDisableInnovation` 0.8 / 策略 `[ReRoute 0.15, ChangeExpBeta 0.85]` / `learningRate` 0.5 / `routingRandomness` 0.0 保留）。**★四口径 `A_10:19`（200k 修复前 D01 → 修复后 R01）**：MATCHED **8.48% → 1.00%**（×0.12）、CATA **10.14% → 1.01%**（×0.10）、SLIP **8.93% → 0.97%**（×0.11）、ALL 3.96% → **0.51%**（×0.13）；`parity_gap_rel`(MATCHED) 1.59% → **0.13%**（×0.08）。**G1–G6**：`sign_consistency`=**1.000** ≥ 0.85；`A_10:19` MATCHED/CATA `<3%`、SLIP `<5%`；`parity_gap_rel<1%`；`\|Q19/Q̄−1\|`=**+0.19%** < 2%；`never_arrived=0` & `max_stuck_car=0`（200,000 departures = 200,000 arrivals）；`A(200k)/A(100k)`=**1.40** < 5。**双口径（用户裁定①）**：Primary `Q̄_10:19`(MATCHED)=**4,567,962**、Reference `Q_19`=**4,576,724**、`Q19/Q̄`=1.0019；`A_full_00_19`=8.79% **仅报告**（burn-in 瞬态，非振荡）。**★机制性质改变**：逐迭代 MATCHED 由旧配置的**周期-2 极限环**（`0.9454 1.0679 0.9605 1.0495 0.9907 1.0692 …` 永不衰减）变为**单调指数收敛**（`0.9169 0.9345 0.9457 … 1.0019`）；**100k 与 200k 归一路径几乎重合**（it.0 0.9112 vs 0.9169、it.19 1.0010 vs 1.0019）⇒ **机制签名，非规模效应**。**★结构性副产物（仅记录，不作 demand 判决）**：收敛**单调地把流量搬到标定断面** —— MATCHED `it.0→it.19` **+9.28%**，同时 ALL **−3.70%**（反单调；100k 同形 **+9.85% / −3.78%**）⇒ 收敛解 MATCHED `Q̄` 比 D01 极限环中心 **+3.1%**（4,430,108 → 4,567,962）；**这会影响 Sim/Obs 水平，但 7.6E 按裁定不评价拟合**。新产物：`audit/routechoice_stability_7_6e.csv`、`routechoice_stability_7_6e_by_iter.csv`；评价器新增 `--stability-7_6e`（含 `sign_consistency` 单调性判据 + `legHistogram` 无损失检查）。**冻结件（7.1 / 7.3.6A / OD / network / capacity / S100c / S100r）全部未触碰**；**未进入 7.6C**；`λ` / demand scale 判决仍不成立。下一步 = **7.6F demand scale 重新评价** |
| 2026-09-17 | **Step 7.6E 200k 正式稳定化启动（预注册运行前冻结）—— 用户裁定：基于 7.6D-S 的 `SCREENING_PASS` 直接进 7.6E，不再做低样本试验、暂不进 7.6C**。冻结不动：`N=200,000` / `FLOOR_PLUS_1` / `f_cap=1.00` / `λ=0.075` / 7.3.6A crosswalk / cleaned network / departure profile / OD matrix / demand scale；**唯一改变 = route-choice 最小修复**（`fractionOfIterationsToDisableInnovation` 0.8 / 策略 `[ReRoute 0.15, ChangeExpBeta 0.85]` / `learningRate` 0.5 / `routingRandomness` 0）。**★7.6E 分工**：不承担「找参数」，200k 只确认「规模提升后机制仍成立」。**预注册 G1–G6（运行前冻结）**：单调性 / 四口径 `A_10:19` / `parity_gap_rel` / `Q19/Q̄` / `never_arrived & max_stuck` / 跨规模比；6/6 通过 ⇒ route-choice 层正式冻结。评价器新增 `--stability-7_6e`（含 `sign_consistency` 单调性判据与 `legHistogram` 无损失检查，与 7.4.3 同源）。**未触碰** 7.1 / 7.3.6A / OD / network / capacity / S100c / S100r 任何冻结件；**未进入 7.6C**。 |
| 2026-09-16 | **Step 7.6D-S 低样本(100k)稳定性筛查完成 → 判决 `SCREENING_PASS`（exit=0，33.20 min，linkstats 20/20）—— ★route-choice 最小修复彻底消除周期-2 极限环（非减小，而是消除）**。用户裁定：**不直接跑 200k（~8–9 h），先做便宜且有辨识力的机制筛查**，只回答「新配置是否把 assignment 从不稳定变稳定」，**不评价** demand scale / λ / OD 空间结构。**★50k 不可行**（`FLOOR_PLUS_1` 要求每正 OD cell ≥1 agent，正 cell 恒 71,136 ⇒ `ValueError: agents 50000 < positive OD cells 71136`）→ 用户改选 **100k @ f_cap=0.50，复用 S100c 冻结人口**，由此得到「**同 N、同 f_cap、同采样规则、同 seed，仅 route-choice 不同**」的零边际成本严格对照。**结果：`A_10:19` MATCHED 5.84%→0.71%（×0.12）/ CATA 4.31%→0.76% / SLIP 10.86%→0.60%（×0.06，改善最大）/ ALL 1.38%→0.44%；`parity_gap_rel`(MATCHED) 4.07%→0.09%（×0.02）**。**★★机制证据**：逐迭代 MATCHED 轨迹由旧配置的「奇偶交替、永不衰减」（0.945/1.068/0.960/1.050…）变为「**单调指数收敛**」（0.911→0.932→…→1.001），it.13 起稳定于 1.000±0.002 —— 振荡被**消除**。**★区分「收敛瞬态」与「极限环」**：新配置 `A_full_00_19`(MATCHED)=9.25% 是 burn-in 瞬态（it.0≈收敛值−9%，**单调**），非振荡；判据只用 `A_10:19` 以剔除瞬态。配置 **25/25 PASS** + 冒烟 PASS + 预注册**运行前冻结**。**未进入 7.6C**；**未修改** 7.1/7.3.6A/OD/network/capacity/S100c/S100r 任何冻结件。产物 `scripts/od/prepare_routechoice_7_6d_s.py`、`scripts/od/audit_routechoice_stability_7_6d.py --screening`、`matsim_routechoice_7_6d/{STEP7_6D_S_PREREGISTRATION.md, configs/config_S100k_rc_min.xml, audit/routechoice_stability_screening_7_6d_s.csv}` |
| 2026-09-16 | **Step 7.6D Route-choice Stabilization 完成配置验证 + 预注册（零仿真；正式 run 待批）—— ★用户裁定：采纳①（评价口径改双口径并报）、执行②（最小 route-choice 修复，先配置验证再决定是否正式重跑）、暂缓③（7.6C OD 空间结构）。****新建隔离工作区 `matsim_routechoice_7_6d/`**（用户工程决定：不修改任何现有 7.1 / 7.3.6A / OD / network / capacity 产物，旧结果完全保留）；**新增** `scripts/od/prepare_routechoice_7_6d.py`（配置生成 + 零仿真验证，**19/19 校验 PASS**）与 `scripts/od/audit_routechoice_stability_7_6d.py`（稳定性评价，零仿真只读）。**★最小修复（唯一变量，针对「学习过猛 + 持续创新」两机制）**：`replanning.fractionOfIterationsToDisableInnovation` `Infinity → 0.8`；`replanning` 策略集 `[ReRoute 1.00] → [ReRoute 0.15, ChangeExpBeta 0.85]`；`scoring.learningRate` `1.0 → 0.5`；`routing.routingRandomness` 保留 `0.0`。**★配置差异仅 4 处**（controller.outputDirectory / controller.runId + 上述2 个标量；策略集在 `<parameterset>` 内由 V1 校验），network / population（f = 1.00 不加车）/ capacity 1.00 / seed 4711 / SpeedyALT / TTC / linkStats 逐值相同；**冒烟预检 PASS**（2000 agents × 3 it，MATSim 接受 `ChangeExpBeta` 与 `fractionOfIterationsToDisableInnovation = 0.8`，无策略解析错误）。**★★统计量口径警示（重要）**：7.6B 报的「周期振幅」= `|even−odd|/mean`（**仅相位分离**），而用户预注册的 `A_10:19 = (max−min)/mean`（**相位分离 + 窗内非交替漂移**）——两者**不是同一个量**：D01 MATCHED 上 **1.59% vs 8.48%（5.3×）**，即当前「周期-2」并不干净，是**弱交替叠加在大幅非交替漂移之上**。**★修复前（before，零仿真复用）四档 demand 的 `A_10:19(MATCHED)`**：f=1.00 **8.48%** `PARTIAL` / f=1.10 **11.10%** / f=1.20 **23.25%** / f=1.25 **20.32%** `UNSTABLE`；同期 `ALL` 仅 1.51–3.96% ⇒ **振荡集中在标定断面**；`SLIP` 最差（最高 **35.51%**，约 `CATA` 的 2 倍）；**即使最温和的 f=1.00 也只是 `PARTIAL`** ⇒ **当前机制下不存在任何稳定的 demand 档 ⇒ 不是 demand 选得不好，而是机制问题**。**①评价口径已采纳（双口径并报）**：Primary = `Q̄_10:19`（奇偶相位均衡周期均值）、Reference = `Q_19`（不丢弃可追溯）。**判据已跑前冻结**（`STEP7_6D_PREREGISTRATION.md：`A_W(X)=(max−min)/mean；`A_10:19(MATCHED) < 3%` = STABLE / 3–10% PARTIAL / ≥10% UNSTABLE；四口径 ALL/MATCHED/CATA/SLIP）。**正式 20 迭代 run（200k×20 it，预计 ~8–9 h）待用户批准**；`N_sample` / `f_cap` / capacity 冻结未变，`λ` / demand scale 仍不冻结，**7.6C 暂缓** |
| 2026-09-16 | **Step 7.6B Assignment / Route Stability Audit 完成（zero simulation，未重跑 MATSim）—— ★判决 `UNCONVERGED_PERIOD2_LIMIT_CYCLE__CROSS_F_SIGNAL_BELOW_PHASE_NOISE`：D01–D04 的分配从未收敛，『it.19 单点』是一个周期-2 极限环的相位样本，因此 7.4.3 的 demand scale 非单调有相当部分是相位伪影。**用户裁定「口径保持 V1（Car Only）」并「启动 7.6B」。**新增** `scripts/od/audit_assignment_stability_7_6b.py`（零仿真只读，复用 D01–D04 it.0–19 共 80 个 linkstats；**20/20 校验 PASS**，其中 **it.19 与 7.4.3-R 已发布表同源 max\|d\| = 4.8e-7**、与 `sim_only_window_levels.csv` 的 ALL/MATCHED 全窗 **max\|d\| = 0**）。**★先验事实（决定判读）**：四份 config 全为 `fractionOfIterationsToDisableInnovation = Infinity` + 唯一策略 `ReRoute`(weight 1.0) + `planCalcScore.learningRate = 1.0` + `routingRandomness = 0.0` ⇒ **100% 的 agent 在 100% 的迭代里重新选路且得分无平滑** = 产生 route flip-flop 的标准配置。**★一、周期-2 极限环（窗口 00-24，收敛窗 it.10–19）**：MATCHED 偶/奇相位均值 4,394,944/4,465,272（D01）、4,658,772/4,837,584（D02）、4,780,698/5,887,389（D03）、4,856,980/5,714,396（D04）⇒ **振幅 1.59% / 3.77% / 20.75% / 16.22%**，而 ALL 仅 0.39% / 1.34% / 1.13% / 1.40% ⇒ **放大 14.8×**、**振幅随 demand 单调放大且峰值与 Sim/Obs 峰值同址（f=1.20）**；奇偶从 it.0 起完全分离。**★二、冻结指标周期均值重估（08-09）**：SimObs it.19 = 0.7070 / 0.7095 / **0.8601** / 0.7599，周期均值 = **0.7505 / 0.7127 / 0.7647 / 0.7061**（it.19 偏置 −5.80% / −0.45% / **+12.47%** / +7.62%），相位振幅 2.05% / 5.98% / **22.33%** / 16.82% ⇒ **跨 f 极差由 15.30% 压缩到 5.87%，而 f≥1.20 的相位振幅单独就有 16.8–22.3% ⇒ 跨 f 信号 < 相位噪声**。**★★三、决定性检验（同相位分别比较）**：MATCHED 00-24 attainment 偶相位 **1.0000/0.9637/0.9065/0.8841（单调下降、峰在 D01）** vs 奇相位 **1.0000/0.9849/1.0987/1.0238（峰在 D03）**；SimObs 08-09 attainment 偶 1.0000/0.8462/0.7621/0.6964 vs 奇 1.0000/0.8801/0.9343/0.8076 ⇒ **响应符号由采样相位决定，该实验在方法上无法识别 demand scale**。**★四、R_cal（标定断面 VKT 份额）**：归一后 it.19 非单调（峰 f=1.20 = 1.1061），**周期均值口径变为接近单调的轻微下降 1.0000 / 0.9483 / 0.9753 / 0.9220**（f=1.25 时 −7.8%）⇒ 存在方向正确的「流量离开标定断面」，但量级远小于相位振幅。**★五、重分布分解**：相位翻转时 ΔMATCHED 与 ΔNON-MATCHED **互相对冲**（D03 +1,106,691 vs −2,088,348，抵消比 **0.53**；D04 +857,416 vs −2,132,046，**0.40**），而全网总量只动 1–2% ⇒ **纯路径替代**，7.4.3-R 的机制候选**被直接量化证实**。**★六、逐链路**：ρ(it18,it19) 全体仅 0.81–0.84（未收敛），**top50 最高流链路 ρ = 0.986 / −0.546 / −0.209 / 0.465**（D02/D03 为**负相关** = 直接翻转）；标定链路承担 \|Δq\| 的 **4.8–5.7%**（链路占比 0.4379% ⇒ **12–13×** 超载）；替代类别 `matched` 5.7% / `nonmatched_adjacent` 3.4% / `nonmatched_other` **90.9%** ⇒ **弥散全网，非单一平行走廊**。**★七、绕行与拥堵**：绕行指数 1.0000 / 1.0274 / 1.0288 / **1.0352**（单调 +3.5%）；8-9 拥堵倍率 ALL 1.631→2.421、**MATCHED 1.273→1.531**、NON-MATCHED 1.664→**2.495** ⇒ **标定主干道反而比全网更畅通**。**★动作项**：① **配置层修复（最高优先）** —— `fractionOfIterationsToDisableInnovation = 0.5–0.9`、`ReRoute` 权重降至 0.10–0.20 并引入 `ChangeExpBeta`/`BestScore`、`planCalcScore.learningRate < 1`，目标把周期振幅压到 3% 以下；② **零仿真立即可用** —— 评价口径改为收敛窗周期均值（15.30% → 5.87%）；③ **停止**在收敛解决前增加 demand scale 跑次；④ 并行取 LTA 分车型计数 + HTS 出发时刻；⑤ **7.6C 必须建立在周期均值口径上**。产物 `reports/od_calibration_7_6b/`（报告 + 15 CSV/JSON + 控制台日志）；readme 同步（§2.28 + 脚本清单行 + §3.1 行 + §6 两行）。**`N_sample` / `f_cap` / capacity 冻结状态未变；`λ` / demand scale 仍不冻结** |
| 2026-09-16 | **Step 7.6A Official Car-Demand Accounting 完成（zero simulation，未重跑 MATSim）—— ★判决 `CALIBER_GAP_DOMINATES`：『总量不足』主要是口径差，不是 demand scale**。用户裁定「下一阶段不继续一个参数一个参数地扫，先把误差归因，再决定哪些值得用 MATSim 消耗算力」，并把路线正式定成 **7.6A（本文，零仿真）→ 7.6B Assignment / Route Stability Audit（零仿真）→ 7.6C OD 距离带 / 空间结构 → 7.6D/7.6E 小规模 λ 与 λ×demand 联合验证 → Final 200k 验证**；**λ 由「下一步直接扫」降级为前面机制确认后才进入**。**新增** `scripts/od/account_official_car_demand_7_6a.py`（零仿真只读，**12/12 校验 PASS**）：**★前置发现 = `TrafficFlow_Data.json` 无车型字段** ⇒ 观测的车型构成 **不可分解**，模态缺口只能用 Census 外部参照界定；逐层对账 居住 2,177,456 / 工作地 2,208,358（差 30,902）→ **物理 1,935,235（87.63%）+ 非物理 273,124（12.37%）**（守恒 Δ = 1，三条特殊类别单列不进道路 OD）→ 11 方式 → **V1 459,796 / V2 526,477 / V3 707,116**（21.12% / 24.18% / 32.47%）；**★量级一致性检验**：`cov(V1/V3) = 0.6502` vs MATCHED 07-09 `Sim/Obs = 0.6830`（比 **0.9520**）⇒ **`f ∈ [1.0504, 1.4641]`，总量证据只能给区间**；判据 `f_lower = cov(V1/V3) ÷ SimObs`，实测 **1.0504 < 1.10** ⇒ 口径差支配。**★三项本地不可定量**：观测车型构成、AM 峰因子（Census 无 departure-time，6.3.3A 剖面由 TrafficFlow 自推 = 循环）、平均载客率（现行隐含 occ = 1.00；occ = 1.30 → 模型高估车辆 23.08%，与模态覆盖 **方向相反**）。**★结论**：不要在口径未固定前再跑 demand scale 批量实验（曲线不可识别），也不要把 `V3/V1 = 1.5379` 当 demand scale（等于让小汽车吸收出租车/摩托/货车流量）。产物 `reports/od_calibration_7_6a/`（报告 + 9 件 CSV/JSON + 控制台日志）；`λ` / demand scale / capacity / `f_cap` **冻结状态未变** |
| 2026-09-16 | **Step 7.4.3-R 宽时间窗重新评价完成（zero simulation，未重跑 MATSim）—— ★阻断发现 + ★对 7.4.3-Diag 的修正**。用户裁定「先重新评价已有结果、不重新仿真」，并建议把水平口径改为 07–11 累计。**新增 `scripts/od/reevaluate_demand_scale_windows_7_4_3r.py`**：复用冻结 `bt.load_traffic` / `normalize_crosswalk` / `_metrics` / `SCALE`，把断面聚合推广到 24 个小时箱。**★阻断事实**：LTA 原始 `TrafficFlow_Data.json` 的 `HourOfDate` **只有 7 与 8**（38,083 + 37,816 行 / 1,311 LinkID / 2025-11-01..30 共 30 天），**与 7.1 冻结口径一致、非脚本过滤**；项目内 `TrafficSpeedBands_v4.json`（143,787 行）与 `EstimatedTravelTimes.json`（192 行）**各只含 1 个 Timestamp**（单时刻快照）⇒ **可观测窗上限 = 07-09**，`07-10/07-11/07-12/00-24` **无观测对象，Sim/Obs 无定义**。**窗口分两类**：Class O（可观测，全指标）= 07-08 / 08-09 / 07-09(=冻结 `AM`)；Class S（无观测，只出模拟侧量级）= 07-10 / 07-11 / 07-12 / 00-24。**★双聚合拆分**：`ALL`=全网 693,575 链路（≈总车公里，**对空间重分配不敏感**）× `MATCHED`=crosswalk 命中 **3,037** 条标定链路（**敏感**）× `section`=断面中位数估计量。**★口径同源断言 PASS**（vs `demand_scale_backtest.csv`，n=5,184，max\|Δ\| = 3.6e-12 < 1e-6）。**★判决**（f=1.25/f=1.20，期望 1.0417）：7 窗口中 **6 个仍 non_monotonic**（峰恒在 f=1.20），唯一 monotonic 的是 `07-08`；`ALL/期望` 0.9201(08-09) → **0.9994(00-24) 完全收敛**，`MATCHED/期望` 0.8493 → **0.9333（只解释 55.7%）**，残留 **6.7% 与窗口无关**。**★对 7.4.3-Diag 的修正**：其「需求近 100% 被投递」**只在全网总量口径成立**（该量近似总车公里，由构造近似随需求线性、对空间重分配不敏感）；**标定靶场全日窗仍留 6.7% 缺口** ⇒ **时间窗伪影只解释约六成，换窗口不能消除非单调，07-11 也不可作水平判据**（既无观测、也不恢复单调）。**残差机制候选**：MATCHED 在 00-24 归一后 D02 1.0806 / D03 **1.3332** / D04 1.2961，峰位 D03 远超名义 1.20 ⇒ 「回落」实为 **f=1.20 在标定断面上的一次超标冲高**；配合行进端证据（行程时长 ×1.173、拥堵倍率 ×1.208、平均行程距离 14,429→14,549 m 绕行变长而标定子集流量 −2.8%）指向 **ReRoute 路径替代/分配重分布**。**动作项**：① 水平口径采用**最宽可观测窗 07-09**（= `AM`）并同时披露 08-09，08-09 保留给空间拟合与 CATA/SLIP 结构比较；② 需向 LTA 获取 **09:00 之后**的流量观测；③ **`route choice` 优先级提前**（OD 总量与空间结构均已不能解释残差）→ 下一步建议做**分配稳定性审计**（零仿真可先做）；④ 在此之前**不要**依据 08-09 的 f=1.20 → 0.8601 选定 demand scale。产物 `reports/od_calibration_7_4_3r/`（`STEP7_4_3R_REPORT.md` + 6 CSV/JSON + `reeval_console.log`）；同步 `scripts/od/readme.md`（§2.26 + 脚本清单行 + §3.1 行）。 |
| 2026-09-16 | **Step 7.4.3 补充诊断完成 —— demand scale 在 08-09 的非单调回落 = 时间窗伪影（判决 `TIME_WINDOW_ARTIFACT_CONFIRMED`）**。用户裁定：**不补跑「纯比例 @200k」作为主线**；**把 200k 保留为正式标定样本（冻结 `N_sample = 200,000` / `f_cap = 1.00`）**，`λ` / demand scale / sampling rule **均不冻结**，**capacity 保持 1.00**；下一阶段**只追一个问题**——7.4.3 的 demand scale 为什么在 08-09 出现 `1.20 → 1.25` 的回落，**避免把时间分配/拥堵饱和效应误判成 OD 参数效应**。**新增** `scripts/od/diagnose_demand_scale_nonmonotonic_7_4_3.py`（零仿真只读；四层证据 + T1–T5 跑前判据）。**★决定性证据（窗口加宽，`Σ_links HRSx-yavg`，it.19）**：**08-09 单小时 31.97M / 33.95M / 36.27M / 34.77M（f1.25/f1.20 = 0.9584 下降 → 非单调）**；**07-09 仍非单调（0.9807）**；**07-10 = 1.0099（单调但仅达比例的约 97%）**；**07-11 = 1.0404 ≈ 纯比例 1.0417**；**07-12 = 1.0442**；**0-24 = 1.2547 ≈ 纯比例 1.2500（达成率 100.4%）** ⇒ **需求几乎 100% 被投递，不存在系统性吸收，只是峰值被摊到 09–12 时**。**★时间分配直读**：平均行程时长 25.76 / 32.26 / 33.24 / **38.99 min**（f1.20→f1.25 ×**1.173**）；8-9 加权拥堵倍率 2.007 / 2.314 / 2.314 / **2.796**（×1.208）；>3× 拥堵链路承载流量占比 7.3%→**9.6%**；09:00 前到达占比 77.21% / 74.33% / 73.26% / **68.35%（−4.91 pp）**；**到达端后移**：08-09 **96,501→91,743**，而 09-10 **43,208→48,466**、10-11 **13,233→22,228**、11-12 5,965→7,651。**★出发端稳定（排除出发延迟）**：出发占比跨档极差仅 **0.035 pp（3.5 bp）**，且四档**逐档 `never_arrived = 0`、`max_stuck = 0`** ⇒ 机制完全在**行进入端（行程时间变长）**。**★次要发现（估计量稳定性）**：逐断面「超额系数」= `Σ比值 ÷ 需求比` —— `08-09` 窗 **0.9123 / 1.0957 / 0.8482**（大幅摆动），`07-08` 窗 **0.9297 / 1.0326 / 0.9701**（近线性稳定）⇒ `sim = median(断面内匹配边 HRS8-9avg) × 2.29897` 是**单小时**统计量，强拥堵下中位数非线性移动 → **08-09 不宜作 demand scale 的水平判据；建议水平口径改用 07-11 累计，08-09 保留给空间结构（CATA/SLIP）比较**。**★结论**：**f=1.20 的 0.8601 不可读作「最优需求规模」**；下一阶段先固定「水平口径」再动 λ / OD 空间结构。**未改动任何模型产物**（零仿真只读）；**λ 仍不冻结；未动 capacity（1.00）**。readme 新增 **§2.25**、流程图新增 7.4.3-Diag 与 200k 基准节点、脚本清单 +1 行、§3.1 +1 行、冻结表 +3 行。 |
| 2026-09-16 | **Step 7.5B Sampling Rule Sensitivity 完成 → 判决 `PARTIAL_IMPROVEMENT`（D 0/6、M 3/4）**。S100r 全量跑通（**100k × 20 it，`exit=0`，墙钟 171.20 min**；★**`--heap 12g` 不足 → 进程被外部硬杀 2 次，改 `--heap 24g` 后一次通过**，堆上限非模型参数）。三方正式结果（08-09，it.19）：Sim/Obs S200 **0.7070** / S100c **0.8389** / **S100r 0.5984**；raw 比 **0.5799 → 0.4325**（**0.50 被夹在中间**）；Pearson **0.8557 → 0.9162（M3 PASS）**；±20% **0.2648 → 0.4305（M2 PASS）**；但 **CATA÷SLIP 漂移 0.0233 → 0.1037（M4 FAIL，恶化 4.4×）**。**★两个机制发现**：① 缺口是**全断面比例性收缩**（99.00%）而非断面归零（S100c/S100r 零流量断面同为 62/576）；② 纯比例**系统性剔除长距离 OD 对**（平均行程距离 14,922.7 → **13,396.6 m**，短 10.2%；ΣEF 仅 −4.7% 却造成断面流量 **−28.7%**，放大 6 倍）。**★待证假设**：Sim/Obs 与「保底 agent 占比」完全单调（0%→0.5984、35.6%→0.7070、71.1%→0.8389）⇒ 单一全局 `SCALE` 无法校正保底规则造成的**构成偏差**；**唯一干净判别实验 = 纯比例 @200k 对称参照（待用户裁定）**。评价器新增 **§8 `mechanism_diagnostics()`**（零流量断面 / 缺口分解 / 平均行程距离，不参与判据）。**λ 仍不冻结；未动 capacity**。 |
| 2026-09-16 | **Step 7.5B Sampling Rule Sensitivity 启动（唯一变量 = 采样规则）**。用户裁定：**不做 125k/150k/175k knee 扫描，先查「每个正 OD cell 至少 1 个 agent」保底采样规则**——理由是 S100c 同时出现两件事：(a) `f_cap=0.50` 把 `CATA/SLIP` 漂移 0.0480→**0.0233**（C6 PASS）→「供需密度」机制可被容量同比缩放吸收；(b) raw ratio 仍 **0.5799**、Pearson 由 0.9006 **降到 0.8557** → 还有第二层「样本空间分布偏差」。**假设**：保底规则让小 cell 获得相对过多代表个体，且畸变随 N 减小放大（保底 agent 占比 200k 35.6% → 100k **71.1%**）。**设计**：`S100r = 纯 trips-proportional（无保底，允许 cell 被抽到 0 个 agent）`，`S100c` 复用；`N=100k`/`λ=0.075`/`f_cap=storage=0.50`/20 it/`seed=4711`/`routingRandomness=0`/同 network·OD·departure·crosswalk·靶场全部冻结。**实现**：`prepare_sample_7_5b.py`（设计 + 采样规则诊断 + S100r 三阶段人口管线，**monkeypatch 6.2B `allocate_cells` 为纯比例**、只改目录常量 → 冻结件零覆盖）、`run_sample_7_5b.py`、`evaluate_sample_7_5b.py`（三方 + D1–D7 绝对 / M1–M4 机制判据 + raw-EF 敏感性）。**★机器验证单变量**：S100c 与 S100r 的 config 除 `outputDirectory`/`runId`/`inputPlansFile` 外**逐字节相同（diff=0）**。**★诊断（零仿真）**：100k 纯比例 → sampled **38,350** / zero-sampled **32,786（46.09%）** / OD coverage **0.5391** / 丢弃 trips **21,528（4.68%）** / ΣEF **438,266.0**（`f_realized` **0.95318**）/ 被采样 cell 逐 cell 守恒误差 **5.68e-14**；对照保底规则 100k：zero 0 / coverage 1.0 / 保底占比 **71.14%** / agent 中位 **1**、max 26（纯比例 max **87**）。**★判据「跑前固定」落盘**（`preregistered_criteria_7_5b.json` + `STEP7_5B_PREREGISTRATION.md`，早于 S100r 启动）；判决 `SAMPLING_RULE_WAS_THE_CAUSE` / `PARTIAL_IMPROVEMENT` / `SAMPLE_SIZE_DEPENDENT`。config `verify_patch` PASS + 冒烟 2000×3it PASS；**S100r 全量启动（100k × 20 it）**（当晚完成 → 见上方完成行）。readme 新增 **§2.24**、脚本清单 +3 行、§3.1 +3 行、冻结表 +1 行、流程图新增 7.5B 节点。**λ 仍不冻结；未动 capacity**。 |
| 2026-09-15 | **Step 7.5A 正式结果（S100c 采样一致对照，零仿真）—— 等效供需比下 100k 能替代 200k 吗？答案：不能**。S100c 全量跑完（**100k × 20 it，`exit=0`，墙钟 164.59 min**，20 迭代全落盘，`STATUS: PASS`）。**★预注册判据（跑前固定）硬门槛 1/6，仅 C6 PASS → `NOT_SUBSTITUTABLE`**：C1 raw ratio 中位 **0.5799**（\|Δ\|=0.0799>0.05 FAIL）、C2 scaled 比值中位 **1.1537**（\|Δ\|=0.1537>0.10 FAIL）、C4 ±20% 内 **0.2648**（<0.80 FAIL）、C5 Pearson/Spearman **0.8557/0.9344**（FAIL）、C6 CATA/SLIP 漂移 **0.0233**（≤0.05 **PASS**）、C7 三窗口（07-08 +0.0277 / 08-09 −0.0233 / AM +0.0005，仅符号不一致 FAIL、三窗 \|Δ\| 均≤0.0277）。**★三条判读**：① **f_cap 校正部分有效**——raw 线性比 **0.6174→0.5799**（采样非线性 +23.5%→**+16.0%**）、CATA/SLIP 漂移 **0.0480→0.0233 减半（C6 PASS）** → **S100 的结构畸变主因是「车密度/容量」，同比缩放容量可基本修复**；② **残余 16% 非线性不可由标量 f_cap 消除**（scaled 比值仍偏高中位 1.1537、±20% 仅 0.2648）→ **样本量本身改变网络动力学**；③ **存在权衡**——f_cap=0.50 改善水平（Sim/Obs 0.9784→**0.8389**）与结构（C6 PASS），但**空间相关性反降**（Pearson 0.9006→**0.8557**）。**★候选机制（待查）**：6.2B「**每个正 OD cell ≥1 agent**」保底规则使 100k 下 **71.1% agent 为保底 agent**（200k 仅 35.6%）→ **样本空间分布随 N 系统性变平**（小 cell 相对高估），可能是残余非线性的一部分（采样规则伪影，非纯网络物理）。**结论：100k 在 f_cap=1.00 与 0.50 下都不能替代 200k；「固定样本+可变权重」在 MATSim 拥堵型网络中不成立；100k 方案不冻结、λ 仍不冻结**。产物：`reports/od_sample_7_5a/`（三方正式报告 + summary + comparison + backtest + roadcat）。 |
| 2026-09-15 | **Step 7.5A：S100c 采样一致对照启动（预注册判据先行）**。用户裁定：**授权跑 S100c，并先把判据固定下来**（避免「看到结果再定标准」）；定义更严格 —— S100c **不是「继续调容量」，而是验证 100k 在等效供需比下能否复现 200k 的交通状态**（决定后续计算规模的关键实验）。**实验设定**：S200（N=200,000, f_cap=1.00）vs **S100c（N=100,000, f_cap=0.50）**，其余全固定（λ=0.075 / 20 iterations / seed=4711 / routingRandomness=0 / same network / same OD / same departure profile / same Final Crosswalk / same 评价靶场）。**★预注册判据（跑前落盘，早于任何 S100c 结果）**：`evaluate_sample_7_5a.py` 新增 `PREREG` 常量（判据单一事实源）+ `--prereg-only` → 生成 `preregistered_criteria.json` + `STEP7_5A_S100C_PREREGISTRATION.md`；**C1** raw flow ratio 中位≈0.50（\|中位−0.50\|≤0.05）/ **C2** scaled S100c÷S200 中位≈1.00（\|中位−1\|≤0.10）/ **C3** ±10% 内占比（仅报告）/ **C4** ±20% 内占比≥0.80 / **C5** Pearson≥0.90 且 Spearman≥0.95 / **C6** CATA÷SLIP 漂移≤0.05 / **C7** 三窗口 \|Δ\|≤0.05 且同号；**全部硬门槛 PASS → 判定 100k 在等效供需比下可替代 200k**（此后 100k 用于全部参数标定/敏感性/迭代搜索，200k 保留一次最终验证）。**★容量语义严格区分**：`f_cap=0.50 = N_sample/N_ref` 是**采样一致性校正**（保持同一物理供需比），**不是**交通供给标定参数 —— 与 Phase 1 的 `capacity_factor` 不能混为一谈。**config 自检 PASS**（qsim `flowCapacityStorage=0.50`/`lastIteration=19`/`seed=4711`/`routingRandomness=0`/`ReRoute`/plans→`matsim_departure_6_3_3a_s100k`）；**S100c 全量完成（100k × 20 it，164.59 min，exit=0）**。**评价器增强**：`check_preregistered()` 逐条 PASS/FAIL + 报告新增 **§5 预注册判定表** / **§6 三问判读**（① 动力学等价性 ② 扩样后等价性 ③ 结构保持）。**冻结不变**：capacity 语义、network、7.3.6A crosswalk、7.1 观测靶场、seed=4711、ReRoute、20 it；**λ 仍不冻结**。 |
| 2026-09-15 | **Step 7.5A 正式结果（S100 评价，零仿真）—— 100k 能替代 200k 吗？**。S100 全量跑完（**100k × 20 it，`exit=0`，墙钟 143.80 min**，it.19 linkstats 就绪），`evaluate_sample_7_5a.py` 按 **7.3.6A Final Crosswalk + 7.1 冻结口径**、**按样本注入 `SCALE`（S200=2.29897 / S100=4.59794）** 复算（S200 复用 E06，不重跑）。**★核心表（08-09，Σsim/Σobs）**：`S200` **0.7070** / WMAPE 0.5660 / GEH<5 0.1389 / GEH<10 0.2413 / Pearson 0.3800 / Spearman 0.5801 / CATA 0.7137 / SLIP 0.6706 / **CATA÷SLIP 1.0642**；`S100` **0.9784** / 0.7177 / 0.0938 / 0.1892 / 0.3198 / 0.5943 / 0.9938 / 0.8935 / **1.1122**。**★判读①线性度不达标（最关键的物理信号）**：`raw S100/200` 比值**中位 0.6174** / 均值 0.6551（期望 **0.5000**）→ **减样本后单位 agent 的实际流量上升 ~23.5%** = **车密度减半、拥堵减轻**的直接证据（QSim 只数车，raw 却**非线性**于 agent 数）；评价层再乘 2× SCALE 放大非线性：`scaled 比值中位 1.2308 ≈ 2×0.6174=1.2348`（实测自洽）。**★判读②等价性差**：逐断面（n=525）scaled 比值中位 **1.2308** / 均值 1.3051、**±10% 内仅 17.9% / ±20% 内仅 32.6%**，但 **Pearson 0.9006 / Spearman 0.9567**（截面**形态**强一致、仅**整体偏高**）→ 误差来自水平/非线性，非断面排序。**★判读③三窗口一致偏高**：S100 = 07-08 **0.7595** / 08-09 **0.9784** / AM **0.8699**（S200 对应 0.6585 / 0.7070 / 0.6830）。**△判决 `NOT_SUBSTITUTABLE`**（判据：scaled 比值中位 |r−1|≤0.10 **且** ±20% 内 ≥0.80 **且** raw 线性比 |0.5−中位|≤0.05）。**★物理结论（不是「100k 没用」，而是「f_cap=1.00 对照不干净」）**：`N_sample` 200k→100k 而 `f_cap` 固定 1.00 → 车密度减半、供给/需求比被改变，S100 与 S200 的差异**混杂「采样效应」与「拥堵物理改变」**；要判定 100k 可替代性，须跑 **S100c（100k, f_cap=0.50 = N_sample/N_ref，采样一致的干净对照）**——**已备好、未运行（待用户裁定）**。**产物**：`reports/od_sample_7_5a/`（**STEP7_5A_REPORT.md**（正式版）+ step7_5a_summary.json + sample_comparison.csv + sample_backtest.csv + sample_roadcat_summary.csv + sample_run_manifest.json）。**冻结不变**：capacity=1.00（除 S100c 对照）、network、crosswalk、观测靶场、seed=4711、ReRoute、20 it；**λ 仍不冻结**。 |
| 2026-09-15 | **Step 7.5A：需求权重链条核查 + 固定样本量采样架构（本轮）**。① **审计（零仿真，决定性）** `audit_demand_chain_7_5a.py`：对 `matsim-2026.0.jar` + `libs/*.jar`（**165 jars / 38,647 entries**）做**字节级常量池扫描**并区分是否命中 MATSim 自身 class —— `expansionFactor` **仅**出现在 `commons-math3` 的 `ResizableDoubleArray.class`（无关同名字段）、`odTrips` **零命中**；**阳性对照** `flowCapacityFactor`/`storageCapacityFactor`/`countsScaleFactor` 全部命中 **MATSim 自身 class**（`QSimConfigGroup`/`HermesConfigGroup`/`CountsComparisonAlgorithm`/`GlobalConfigGroup`）证明扫描有效；项目自定义 Java = **0**、全项目 `*.xml` 属性名命中 = **0**；Python 侧只有「写 / 守恒校验 / 事后 EF 加权诊断」三种用法，**无一处回流仿真** → **判决 `NOT_CONSUMED`：MATSim 的 link flow 由进入 QSim 的 person/vehicle 数决定，扩样必须在评价层 `SCALE = ΣT/N_sample`**。② **设计 + 100k 人口管线** `prepare_sample_7_5a.py`：**三层需求**（真实需求/采样率/有效权重）；**★硬约束** λ=0.075 正 OD cell=**71,136** → `N_sample ≥ 71,136`（**50k 不可行**）；**★容量—采样耦合**论证（改采样率须同比缩放 `flowCapacityFactor` 才保持同一物理场景，非性能旋钮）；三阶段（6.2B `--target-agents 100000` → 连通性修复[复用冻结网络] → 6.3.3A 出发剖面）**全部写入新目录 `*_s100k`，零覆盖冻结 200k 产物**（monkeypatch 目录常量复用冻结构建脚本）→ persons=**100,000**、ΣEF=**459,794.000**、mean_ef=**4.59794**、出发剖面 48,710/51,290。③ **运行器** `run_sample_7_5a.py`：S100（f_cap=1.00）/S100c（f_cap=0.50 采样一致对照）config 生成 + `verify_patch` PASS + **冒烟 2000×3it PASS**；**S100 全量完成（100k × 20 it，143.80 min，exit=0）**。④ **评价器** `evaluate_sample_7_5a.py`：按实验注入 `bt.SCALE` + **线性度检验**（raw 100k/200k ≈0.5）+ **等价性检验**（逐断面比值/±10%/±20%/Pearson/Spearman）→ 数据驱动判决 `SUBSTITUTABLE`/`SUBSTITUTABLE_WITH_NONLINEARITY`/`NOT_SUBSTITUTABLE`。**冻结不变**：capacity=1.00（除 S100c 对照）、network、crosswalk、观测靶场、seed=4711、ReRoute、20 it；**λ 仍不冻结**。**指出**：若要继续 7.4.3 细扫，现在应改为「固定 100k 样本 + 可变扩样权重」架构以控制计算规模 |
| 2026-09-15 | **Step 7.4.3 OD 总量 / 机动车出行量标定（demand scale）正式结果（PASS，零仿真评价）—— 加车能补上量级缺口吗？**。D02–D04 全量跑完（**各 20 it，全部 `exit=0`**；D04 墙钟 **492.94 min**；it.19 linkstats 全就绪），`evaluate_demand_scale_7_4_3.py` 按 **7.3.6A Final Crosswalk + 7.1 冻结口径**复算，**D01 复用 E06**。**★核心表（08-09，Σsim/Σobs）**：`D01(f=1.00)` 0.7070 / WMAPE 0.5660 / GEH<5 0.1389 / GEH<10 0.2413 / Pearson 0.3800 / CATA 0.7137 / SLIP 0.6706 / **CATA÷SLIP 1.0642**；`D02(f=1.10,220k)` 0.7095 / 0.6103 / 0.1233 / 0.2448 / 0.3401 / 0.6980 / 0.7729 / **0.9031**；`D03(f=1.20,240k)` **0.8601** / 0.6957 / 0.0868 / 0.1979 / 0.3154 / **0.8512** / **0.9091** / **0.9363**；`D04(f=1.25,250k)` 0.7599 / 0.6581 / 0.0885 / 0.2066 / 0.2464 / 0.7458 / 0.8376 / **0.8904**。**★A 系列（算术参照，零仿真，= D01 sim ×f）**：f1.10→0.7777 / f1.20→0.8484 / f1.25→0.8838（Sim/Obs 精确 ×f、CATA/SLIP 恒 1.0642 → 证实算术缩放对结构零影响）。**★判读①量级非单调、补不满**：Sim/Obs(all) 峰 @**f=1.20 = 0.8601**、f=1.25 回落 0.7599，跨 f 极差 **0.1530**；**最强档距 1 仍差 0.1399** → **加车不能单独补齐量级缺口**。**★判读②结构不中性（重要）**：`CATA/SLIP` 极差 **0.1738**（= λ 极差 0.0146 的 **12×**、= capacity 极差 0.2371 的 **73%**），且 **穿越 1**（1.0642→0.8904，CATA↔SLIP 反转）；**需求弹性 SLIP ×1.249 > CATA ×1.045 → 加车把结构推向 SLIP**。**★判读③阻尼非单调**：`A−D` = **+0.0682（f1.10）/ −0.0116（f1.20）/ +0.1239（f1.25）**，且同时含「拥堵饱和」与「断面重分配」（算术参照冻结 D01 空间形态）→ **不能单独解释为拥堵**。**★判读④窗口**：07-08 单调上升（0.6585→0.6734→0.7586→0.7665）、08-09 与 AM 峰 @1.20（AM 0.8098）→ knee≈f1.20。**★修正评价器缺陷**：报告 §5 原**硬编码**"需求缩放对结构基本中性"，与本次数字（0.1738、穿越 1）**直接矛盾** → 改为**数据驱动判读**（单调性 / 峰位 / 穿越 1 / 需求弹性 / 阻尼解读 4 条），并在 `step7_4_3_summary.json` 增 `level_scan_08_09` / `level_shape=non_monotonic` / `level_peak_f_demand=1.2` / `level_gap_to_1_at_peak=0.1399` / `structure_verdict=not_neutral` / `structure_crosses_one=true` / `demand_elasticity_CATA_vs_SLIP`。**产物**：`reports/od_calibration_7_4_3/`（demand_scale_backtest.csv / demand_scale_roadcat_summary.csv / **demand_scale_comparison.csv** / step7_4_3_summary.json / **STEP7_4_3_REPORT.md**（正式版））。**结论/下一步**：**demand scale 不能单独冻结为"补量级"手段**（补不满且动结构）；**λ 仍不冻结、f_demand 未选定**。候选：(a) **f∈[1.15,1.20] 细扫 + 三窗核**；(b) 转 **OD 空间结构标定**（结构对需求敏感、SLIP 弹性 > CATA）；(c) 复核饱和下 8–9 时窗计数口径（非单调峰成因）。 |
| 2026-09-14 | **Step 7.4.3 OD 总量 / 机动车出行量标定（demand scale）：设计 + 运行器 + 评价器三件套落地，**全量完成 + 评价已出**。「Phase 2 证明 λ≈0.075 是最优 λ」**被用户纠正并保留**：Phase 2 只证明在**当前三档**内 λ=0.075 对**截面拟合指标**最优，λ 对总量**非单调**且三档均**明显总体低估**（最优仅 0.81）→ **λ 暂不冻结**。本轮**固定 λ=0.075（仅作控制变量）、f_cap=1.00、20 it**，只做 **demand scale**。**★需求承载机制核查（回应"到底该缩放什么"）**：`expansionFactor`=`T_ij/N_ij`（Σ=**459,794** = 真实 car OD 总量，**MATSim 不消费**）、`odTrips`=`T_ij`（Σ 随 λ **4.215M→4.327M→4.485M** 变，**= cell 内 agent 数分布的影子**）、**agents（车辆数）= 唯一被 QSim 消费的物理需求杠杆** → **只缩放 agents**；**排除缩放 `expansionFactor`/`odTrips`**（后者正是用户担心的"实现层权重差异被误当真实需求"）。**实验矩阵**：**D01 f=1.00（直接复用 E06，不重跑）/ D02 f=1.10（220k）/ D03 f=1.20（240k）/ D04 f=1.25（250k）**。**三件套**：`prepare_demand_scale_7_4_3.py`（设计单一事实源，零仿真，含 MECHANISM 块 + 决策规则）/ `run_demand_scale_7_4_3.py`（**嵌套随机子集复制** permutation 前缀 `seed=20260912` 把 D01 冻结人口复制到 220k/240k/250k，**每 agent 的 EF/home_link/work_link/departure end_time 逐字节不变、复制概率均等 → 增量空间无偏**；`build_one(pop_dir=)` + 最小 patch + `verify_patch` 读回断言；`--gen-only/--smoke/--experiments/--force`；**断点续跑**）/ `evaluate_demand_scale_7_4_3.py`（零仿真，import 冻结 7.3.6B + 7.4.2 评价函数；**★双系列：D 物理加车 vs A 算术参照 = D01 sim ×f → A−D = 拥堵弹性阻尼**；含 `f_realized` 复核 + 四曲线）。**已验证**：设计脚本产出 `demand_scale_matrix.csv`（levels=[1.0,1.1,1.2,1.25]、run=[D02,D03,D04]、reuse=[D01]）；人口实测 **ΣEF = 505,695.8 / 551,684.9 / 574,710.1 → `f_realized` = 1.09983 / 1.19985 / 1.24993**（复制正确）；三份 config 全部 PASS；**冒烟 2000×3it PASS**（2.11 min，逐迭代 linkstats 变化 → 拥堵反馈生效）；**D02 已载入 220,000 agents 进入 QSim**；评价器**自检逐位复现 E06（0.7070 / 0.7137 / 0.6706 / 1.0642）**、**A 系列锚定正确**（`CATA/SLIP` 恒 1.064180、Sim/Obs 精确 ×f）。**★坑（本轮）**：运行器 `verify_patch` 初版断言 `plans.endswith("pop_D02")` 失败（config 的 `inputPlansFile` 是完整路径 `...\pop_D02\population_lambda_0p075.xml.gz`）→ 改为 `expect_plans_contains in plans`（并连带修 `NameError`）；评价器报告生成曾用中文弯引号破坏字符串、另有 2 处死代码，均已修。**产物**：`reports/od_calibration_7_4_3/`（demand_scale_matrix.csv + demand_parameter_definition.json + **STEP7_4_3_DESIGN.md** + demand_scale_backtest.csv + demand_scale_roadcat_summary.csv + **demand_scale_comparison.csv** + step7_4_3_summary.json + **STEP7_4_3_REPORT.md**（当前 = D01 自检版）+ demand_run_manifest.json + demand_console.log）+ `reports/matsim_demand_7_4_3/pop_D0{2,3,4}/`（复制人口）+ `matsim/step6_3/config_D0*_lam0p075_dem1p*.xml`。**冻结不动**：全部上游 + 7.1/7.2.1/7.2.2/7.3.1/7.3.2A/7.3.2B/7.3.2C/7.3.3/7.3.4/7.3.5/7.3.6A/7.3.6B/7.4.1 + **7.4.2 Phase 1/Phase 2 = 🔒**；**λ 仍不冻结**。下一步 = D02–D04 跑完 → `evaluate_demand_scale_7_4_3.py` 出正式评价表 + summary → 判能否**冻结 demand scale**，再决定进 **OD 空间结构标定** 还是 **继续总量细化**。 |
| 2026-09-14 | **Step 7.4.2 Phase 2 λ 灵敏度结果（PASS，零仿真评价）—— λ 能同时改善量级 + 结构 + 断面误差吗？**。E06(λ0.075)→E09(λ0.100) 跑完（各 20 it，`exit=0`，E09 墙钟 212.59 min），用 `evaluate_calibration_phase2_7_4_2.py` 按 7.3.6A Final Crosswalk + 7.1 冻结口径复算，**E03(λ0.050) 复用 Phase 1**。**★三组人口核对**：config 分别指向 `population_lambda_0p050/0p075/0p100.xml.gz`；三者均 **200,000 agents**、**Σ expansionFactor = 459,794 恒定** → **模拟出行量三档相同**，λ 差异纯来自空间重分配（旁证 `Σ odTrips` 4.215M→4.327M→4.485M）。**★核心表（08-09，Σsim/Σobs）**：`6.3.3B(1it,λ0.050)` 0.7690 / WMAPE 0.6257 / GEH<5 0.1007 / GEH<10 0.2170 / Pearson 0.2909 / CATA 0.7797 / SLIP 0.7098 / **CATA÷SLIP 1.0984**；`E03(20it,λ0.050)` **0.8105** / 0.6296 / 0.1163 / 0.2170 / 0.3309 / **0.8187** / 0.7652 / **1.0698**；`E06(20it,λ0.075)` 0.7070 / **0.5660** / **0.1389** / **0.2413** / **0.3800** / 0.7137 / 0.6706 / 1.0642；`E09(20it,λ0.100)` 0.7646 / 0.5933 / 0.1163 / 0.2361 / 0.3388 / 0.7707 / 0.7304 / **1.0552**。**★判读①λ 不是结构杠杆**：`CATA/SLIP` 跨 λ 极差 **0.0146**（唯一单调项，1.0698→1.0642→1.0552）= Phase 1 capacity 极差 **0.2371** 的 **1/16** → 断面语义结构已由 7.3.6A 解决，λ 无须再动结构。**★判读②λ 不是量级杠杆**：Sim/Obs(all) 随 λ **非单调**（峰@λ0.050=0.8105、谷@λ0.075=0.7070，极差 0.1034），最优仍 <1 → 补不上 19–25% 的整体量级缺口；应由 **OD 总量 / car-trip 扩样因子 (2.29897) / departure profile / mode coverage** 方向排查。**★判读③λ 对截面拟合有真实但有限的正效应**：**E06(λ=0.075) 在 WMAPE / GEH<5 / GEH<10 / Pearson / Spearman 上三窗口（07-08/08-09/AM）一致最优**；而量级最优是 E03(λ=0.050) → **存在「量级最优 0.050 vs 拟合最优 0.075」权衡**；SLIP Sim/Obs 与 CATA/SLIP 的跨窗口最优 λ **不一致**（其余 7 项一致）。**★判读④λ=0.025 暂缓**（`population_lambda_0p025.xml.gz` 缺失，E10 = `DEFERRED_BY_USER_DECISION`），未纳入趋势。**评价器增强**：新增 §2.1 逐指标趋势（单调/非单调判定）、§2.2 跨窗口一致性（各窗口独立取最优 λ）、§2.3 三类响应（结构/量级/拟合）+ 权衡；summary JSON 固化 `lambda_trend_08_09` / `lambda_window_consistency` / `lambda_0p025_status` / `level_spread_across_lambda_08_09`。**产物**：`reports/od_calibration_7_4_2/`（phase2_backtest.csv / phase2_roadcat_summary.csv / **phase2_lambda_comparison.csv** / step7_4_2_phase2_summary.json / **STEP7_4_2_PHASE2_REPORT.md** / phase2_run_manifest.json）。**冻结不动**：全部上游 + 7.1/7.2.1/7.2.2/7.3.1/7.3.2A/7.3.2B/7.3.2C/7.3.3/7.3.4/7.3.5/7.3.6A/7.3.6B/7.4.1/7.4.2 Phase 1 + **7.4.2 Phase 2 = 🔒（结果冻结）**；**λ 仍不冻结**、**不自行按单一指标选 λ**（由用户判定）。下一步候选：(a) **Phase 3 λ∈[0.06,0.09] 精细搜索**（改善截面拟合）；(b) 转 **OD 总量 / car-trip 扩样因子 / departure profile** 补量级缺口。 |
| 2026-09-14 | **Step 7.4.2 Phase 2 λ 灵敏度：设计 PASS + E06/E09 启动（capacity 固定 1.00）**。Phase 1 已证 capacity 是"总量杠杆 + 拥堵弹性从属结构响应"且 **f=1.00 全面占优** → Phase 2 **固定 f_cap=1.00、20 it，只扫 λ**。**⚠️ 编号冲突（本步重点，已显式披露）**：用户口述 Phase 2 编号 `E04/E05/E06/E07` 与 **7.4.1 冻结矩阵**不一致 → 采用**规范 ID**：λ0.025→**E10**（新增）、λ0.050→**E03**（Phase 1 已完成，复用）、λ0.075→**E06**、λ0.100→**E09**（矩阵 E07=λ0.100/**f0.50**；7.4.1 全部 **f<1.00** 行 E01/E02/E04/E05/E07/E08 在 Phase 1 后**退役**）。**★λ=0.025 阻塞**：`reports/matsim_departure_6_3_3a/` 仅存 λ∈{0.050,0.075,0.100} 的 population；跑 λ=0.025 需先补齐上游冻结链（`5A build_prior_od.py`→`5B build_prior_od_5b.py`→`5C1 build_prior_od_5c1.py`→`6.2B build_matsim_population_6_2b.py`→`prepare_connected_scenario.py`→`6.3.3A build_departure_profile_6_3_3a.py`，均 `--lambdas 0.025`）——**新增 λ、不改既有产物**，**本步不自动执行，待用户决策**。**新增脚本**：`prepare_calibration_phase2_7_4_2.py`（设计单一事实源，零仿真，探测 population 存在性 + 输出 ID 映射 + blocker）+ `evaluate_calibration_phase2_7_4_2.py`（零仿真评价，import 冻结 7.3.6B + Phase 1 评价函数，产出 λ×指标对比表 + λ 趋势）。**运行器增强**：`run_calibration_phase1_7_4_2.py` 加 `--phase`/`--manifest` 两可选参数（默认行为不变）；**manifest 默认名按 phase 生成**（`phase<phase>_run_manifest.json`）——**曾因默认名固定为 phase1 而误覆盖 Phase 1 manifest，已恢复**。**已启动**：`--experiments E06 E09 --phase 2`（E06 λ0.075 → E09 λ0.100，各 20 it，~4 h/档 → **~8 h**），可断点续跑，唯一变量 = λ。**产物**：`reports/od_calibration_7_4_2/`（phase2_lambda_matrix.csv + phase2_parameter_definition.json + **STEP7_4_2_PHASE2_DESIGN.md** + phase2_console.log + phase2_run_manifest.json），待跑完出 phase2_lambda_comparison.csv 等 5 件套。**冻结不动**：全部上游 + 7.1/7.2.1/7.2.2/7.3.1/7.3.2A/7.3.2B/7.3.2C/7.3.3/7.3.4/7.3.5/7.3.6A/7.3.6B/7.4.1 + **7.4.2 Phase 1 = 🔒（结果冻结）**；**λ 仍不冻结**。下一步 = E06/E09 跑完 → `evaluate_calibration_phase2_7_4_2.py` 出 λ 对比表 → 判 λ 是否具结构辨识力 → Phase 3 精细搜索或转 OD 总量/departure profile。 |
| 2026-09-13 | **Step 7.4.2 Phase 1 联合校准结果（PASS，零仿真评价）—— capacity 只改总量还是也改结构？**。E01–E03 全部跑完（E01 f=0.50 19:08 / E02 f=0.75 22:30 / E03 f=1.00 次日01:24，`exit=0`，墙钟 ~10.6 h），用 `evaluate_calibration_7_4_2.py` 按 7.3.6A Final Crosswalk + 7.1 冻结口径复算。**运行前修复评价器 1 处缺陷**：`struct_scan[...]["capacity_factor"]` 取自矩阵 CSV（字符串）→ `f4()` 触发 `ValueError: Unknown format code 'f' for object of type 'str'` → 强制 `float()`（坑 58）。**★核心表（08-09，Σsim/Σobs）**：`6.3.3B(1it,f=1.00)` Sim/Obs 0.7690 / CATA **0.7797** / SLIP **0.7098** / CATA÷SLIP **1.0984**；`E01(20it,f=0.50)` 0.3994 / **0.3874** / 0.4652 / **0.8328**；`E02(f=0.75)` 0.5698 / **0.5611** / 0.6181 / **0.9078**；`E03(f=1.00)` 0.8105 / **0.8187** / 0.7652 / **1.0698**。**★判读①capacity 是强总量杠杆**：Sim/Obs(all) 随 f 单调 0.399→0.570→0.810（f 0.50→0.75 增 0.170、0.75→1.00 增 0.241，近似线性）。**★判读②capacity 同时进入结构通道**：三档 `CATA/SLIP` **极差 0.2371 = 基线偏离 |1.0984−1|（0.0984）的 2.41×** → 不是"只改总量"。**★判读③但结构变化是拥堵弹性差、非语义重分配**：分解 f=0.50→1.00 时 CATA ×**2.11**（0.3874→0.8187）> SLIP ×**1.64**（0.4652→0.7652）→ 主线（容量大、饱和度对总需求更敏感）被放大更多 → `CATA/SLIP` 单调上升；**这是两类道路对饱和度的响应弹性差异，不是"capacity 把车改派到哪类道路"**。**★判读④f=1.00 全面占优 → 不存在更优 f<1.00**：GEH<5 0.0642→0.0851→**0.1163**、GEH<10 0.1181→0.1719→**0.2170** 随 f 单调改善，Sim/Obs(all) **0.8105** 最接近 1 → **capacity 固定 f=1.00 作基线，不再作为待辨识变量**（降低 capacity 只牺牲总体水平；WMAPE 非单调，E02 0.6245 略优于 E03 0.6296）。**★判读⑤迭代效应（同 f=1.00，1it→20it）**：Sim/Obs(all) **0.7690→0.8105（+0.0415）**、CATA 0.7797→0.8187、SLIP 0.7098→0.7652、`CATA/SLIP` **1.0984→1.0698**、Pearson 0.2909→0.3309 → **固定 20 it 必要；迭代本身非主要结构误差来源**。**★判读⑥剩余误差=整体量级不足**：f=1.00+20it 下 Sim/Obs 仍仅 **0.81**、CATA 0.82 / SLIP 0.77 均 <1（全局少分配 ~19–23%）→ 下一步聚焦 **λ 辨识**与需求尺度。**★下一步建议**：**Phase 2 精简为 λ=0.075/0.100 @ f=1.00（矩阵中即 E06/E09）**，**不必跑 E04/E05/E07/E08（f<1.00 组合）**，因 f=1.00 已全面占优；λ 仍未辨识→不冻结。**产物**：`reports/od_calibration_7_4_2/`（phase1_backtest.csv / phase1_roadcat_summary.csv / **phase1_capacity_comparison.csv** / step7_4_2_phase1_summary.json / **STEP7_4_2_PHASE1_REPORT.md**（含 §2.1 结构分解 + §2.2 迭代效应）/ phase1_run_manifest.json）。**冻结不动**：全部上游 + 7.1/7.2.1/7.2.2/7.3.1/7.3.2A/7.3.2B/7.3.2C/7.3.3/7.3.4/7.3.5/7.3.6A/7.3.6B/7.4.1 + **7.4.2 Phase 1 = 🔒（结果冻结）**；**λ 仍不冻结**。 |
| 2026-09-13 | **Step 7.4.1 联合校准实验矩阵设计（PASS，零仿真）+ Step 7.4.2 Phase 1 运行/评价管线（上一轮启动）**。用户交付 7.4.1 三件套（`calibration_experiment_matrix.csv` / `calibration_parameter_definition.json` / `STEP7_4_1_EXPERIMENT_DESIGN.md`）→ AI 落地进项目 `reports/od_calibration_7_4_1/` 并新增 `scripts/od/prepare_calibration_experiments_7_4_1.py`（**可复现的单一事实源**，从不启动 MATSim）。**★关键修正（坑 56）**：草案 `randomSeed=20260912`（= 设计日期，误当种子）→ 项目**实测冻结值 4711**（`make_config_6_3.py` 硬编码；6.3.3B / `config_capf_*` / `config_cf_it20` 三份 config 一致）；**为保持与 6.3.3B linkstats 及整条 7.x 评价链可比，采用 4711**，并在 JSON `random_seed_note` + 设计 MD 中**披露被覆盖的草案值**（不静默改）。**θ={λ, f_cap, route-choice}**：λ∈{0.050,0.075,0.100}、f_cap∈{0.50,0.75,1.00}（**storage=flow**，MATSim 2026 硬约束）、**route-choice 固定 20 it**（7.3.1 已证迭代次数非主要校准变量）；**9 组 E01–E09，Phase1 = E01–E03（λ=0.050）**、Phase2 按需；含预注册淘汰规则（仅总量改善而结构不动 → 淘汰；结构改善但 WMAPE/RMSE 恶化 → 淘汰；λ 只有在不同 capacity 下持续占优才可辨识）。**7.4.2 运行器** `run_calibration_phase1_7_4_2.py`：`make_config_6_3.build_one` 同源 config + 最小 patch —— **唯一实验变量 = `qsim.flowCapacityFactor`（+ `storageCapacityFactor` 同值）** + `controller.lastIteration=19`（20 it 启用基线已配的 ReRoute/TTC 拥堵反馈）+ 磁盘控制（`writeEvents/Plans/Trips/SnapshotsInterval=0`，只留每迭代 linkstats）；`verify_patch` 读回断言（`f==storage`、`lastIteration==19`、`randomSeed==4711`、`ReRoute` 存在、`routingRandomness==0`）；**冒烟 2000 agents × 3 it PASS（0.94 min，逐迭代 linkstats 3 份、数值 322k→314k→325k 变化 → 拥堵反馈生效；收尾 `DumpDataAtEndImpl` ERROR 为良性）**；**可断点续跑**（it.19 linkstats 存在即跳过）。**7.4.2 评价器** `evaluate_calibration_7_4_2.py`：**import 已冻结的 7.3.6B 模块**保证口径逐字节同源（不做复制粘贴），评价接口 = **7.3.6A Final Crosswalk** + 观测 = **7.1 冻结口径**，默认取最末迭代 it.19（另附 it.0 / 6.3.3B 基线）；**管线自检逐位复现 7.3.6B 头条 —— CATA 0.779683 / SLIP 0.709812 / CATA÷SLIP 1.098435 ✅**；产出 **`f × {Sim/Obs, WMAPE, GEH<5, CATA, SLIP_ROAD, CATA/SLIP}`** 对比表。**★语义确认（坑 57）**：`linkstats` 154 列中 `HRSx-y{min,avg,max}` = **小时流量（车辆数，整数计数）**，`TRAVELTIME{x-y}{...}` 才是**行程时间**（≈LENGTH/FREESPEED）→ 佐证 7.1 口径 `sim=median(HRSx-yavg)×2.29897` 是"仿真流量 × 抽样扩样"而非"速度÷流量"；另 `flowCapacityFactor` 同时存在于 `hermes` 与 `qsim` 两 module，但**只有 `qsim` 生效**（7.2.2 实测），`hermes` 为惰性模块。**★Scope 披露**：7.3.6A Final Crosswalk **仅覆盖 CATA+SLIP_ROAD 两类**，故 `CATB/CATC/CATD/CATE` 的 Σsim/Σobs 在本评价中为 **null**。**本轮启动 Phase 1 全量（E01–E03，3 组 × ~3h50m ≈ 11.5 h，后台完成）**。**冻结不动**：全部上游 + 7.1 / 7.2.1 / 7.2.2 / 7.3.1 / 7.3.2A / 7.3.2B / 7.3.2C / 7.3.3 / 7.3.4 / 7.3.5 / 7.3.6A / 7.3.6B + **7.4.1**；**λ 仍不冻结**。下一步 = 跑完用 `evaluate_calibration_7_4_2.py` 出 `f × 指标` 表 → 判 capacity 是否只改总量 → 决定 Phase 2（E04–E09）或转 λ × route-choice 联合辨识。 |
| 2026-09-13 | **Step 7.3.6B Final Crosswalk 三方回测（PASS，零仿真）**。用户交付 `scripts/od/compare_final_crosswalk_7_3_6b.py`；AI **运行前修复 4 处缺陷**：① `normalize_crosswalk` 保留 crosswalk 自带 `RoadCat` → 与观测表合并生成 `RoadCat_x/_y` → `groupby(["lta_linkid","RoadName","RoadCat"])` **KeyError 崩溃**（坑 53）；② `load_traffic` **未按工作日过滤 + 未先日内均值再跨日中位数** → 复现不出 7.1 冻结观测（改为严格复刻 `build_calibration_target_7_1.py::obs_load`，坑 54）；③ 语义 crosswalk 误喂 **full（251 SLIP）** 而非用户引用的 **strict（129 SLIP）** → 中间值会成 1.88 而非 0.8535（坑 55）；④ `summarize` 缺 **WMAPE**、无 AM 窗口。AI 重写脚本并保留用户原件 `_compare_final_crosswalk_7_3_6b.py.user_orig_backup`。**新增**：`7.3.4_full` 参照法、三窗口（07-08/08-09/AM）、CATA/SLIP 全指标矩阵（Pearson/Spearman/MAE/RMSE/MAPE/WMAPE/Bias/GEH<5/GEH<10）。**口径（严格 = 7.1 冻结）**：观测 = 工作日 TrafficFlow Volume → 日内均值 → `LinkID×hour` 日中位；仿真 = `median(匹配边 HRSx-yavg) × 2.29897`；主判据窗口 **08-09**。**★核心链条（08-09，Σsim/Σobs）**：`7.1_old 0.7388 / 2.0333 / CATA÷SLIP 0.3633` → `7.3.4_semantic(strict) 0.7797 / 0.8535 / 0.9135` → **`7.3.6A_final 0.7797 / 0.7098 / 1.0984`**（越过 1，+9.8%）。**AM 窗口同向**：`0.3650 → 0.8982 → 1.0922`；07-08：`0.3663 → 0.8765 → 1.0816`。**★参照 7.3.4_full = 0.4100（SLIP 1.8796）** → 量化证明"**保留 fallback、覆盖全 251 SLIP**"会把旧式错配重新引入，即 **覆盖广 ≠ 语义对齐**。**关键读数**：(a) final 的 CATA 映射 ≡ 7.3.4-strict（n=326、0.7797 逐位一致）→ 13 CATA UNMATCHED 仍缺；(b) SLIP 覆盖 129→250，比值 2.0333→0.7098；(c) SLIP **WMAPE 1.750→0.715**、GEH<10 **11.2%→22.4%**，CATA GEH<5 **7.1%→10.4%**；(d) Pearson 仍弱（断面级排序问题）。**★★判读**：**7.3 的结构性问题（断面语义错配，C 类）已由 7.3.4+7.3.5+7.3.6A 解决**——`CATA/SLIP` 由 0.3633 收敛到 **1.0984**，可正式把 **TrafficFlow 评价语义错配从主要模型误差中剔除**；**残差转为整体量级**（CATA 0.78 / SLIP 0.71 均 <1，全局少分配 ~25–30%）。**产出**：`reports/od_final_crosswalk_backtest_7_3_6/`（7 产物）。**冻结不动**：全部上游 + 7.1/7.2.1/7.2.2/7.3.1/7.3.2A/7.3.2B/7.3.2C/7.3.3/7.3.4/7.3.5/7.3.6A/**7.3.6B**；**λ 仍不冻结**。下一步 = **Step 7.4 联合校准**（在语义正确的 final crosswalk 上再议 λ / 需求尺度 / capacity 语义）。 |
| 2026-09-13 | **Step 7.3.6A Final Calibration Crosswalk 构建（PASS，零仿真）**。用户交付 `scripts/od/build_final_calibration_crosswalk_7_3_6a.py`；AI **运行前修复 3 处阻塞缺陷**：① `load_traffic` 未把 `LinkID`→`lta_linkid`，`main()` 首行即 `AttributeError: 'DataFrame' object has no attribute 'lta_linkid'`；② `semantic.merge(obs, on="lta_linkid")` 时 **`RoadName`/`RoadCat` 两边同名** → 生成 `RoadName_x/_y`、`RoadCat_x/_y` → `cata[["RoadName","RoadCat"]]` **KeyError**；③ `slip.merge(slip_obs)` 同样 `RoadName` 冲突 → `slip_final[["RoadName"]]` **KeyError**（坑 51）。**★第 4 处（最隐蔽）**：修好列冲突后 **SLIP 仍全部为 0/UNMATCHED** —— 根因是 **`pandas.groupby` 默认 `dropna=True`**，SLIP 行曾因列冲突把 `RoadName` 填成 NaN → **整组被静默丢弃**（坑 52）；修法：`load_slip` 丢弃文件自带 `RoadName`（由观测表权威提供）+ `groupby(..., dropna=False)` 兜底。**并按用户验收清单补全**：覆盖分母（CATA 339 / SLIP 251）、`selection_status`、`shared_section_count`、`is_primary_candidate`、`geometry_fallback`、N 超限 `REVIEW`、`UNMATCHED`、Gates 判定、`--cata-n-max/--slip-n-max`（可调）。AI 重写脚本并保留用户原件 `_build_final_calibration_crosswalk_7_3_6a.py.user_orig_backup`。**硬规则**：`CATA→motorway`（direction ≤30°，name 仅辅助）、`SLIP_ROAD→motorway_link`（direction + geometry，**RoadName 不作硬约束** —— 依 7.3.5 证据）。**Tier 分层（断面级）**：CATA_T1_DIRECTION_SEMANTIC；SLIP_T1_DIRECTION_NAME → T2_DIRECTION_GEOMETRY → T3_GEOMETRY_ONLY（带 flag）；无候选 → **UNMATCHED（不强行匹配）**。**1:N** 保留完整同向匝道链；N 超限（CATA>10 / SLIP>8）→ `REVIEW`（保留但标记）。**★核心结果**：断面 **590**、rows **3,193**；**覆盖 CATA 326/339（96.17%）、SLIP 250/251（99.60%）**；**纯度均 100%**；Tier 边数 CATA_T1 **1,046** / SLIP_T2 **1,515** + T1 **597** + **T3 35**；**共享 MATSim 边率 4.87%**（较 7.3.3 的 73.3% 大幅下降）；**对向残差仅 1.10%**（全部来自 35 条 T3 几何回退边，已 flag）；CATA 边 100% 携带 6.3.2 几何 `distance_m`；mean/median 边数 5.54/4（CATA 3.21/3、SLIP 8.59/8）。**Gates 全过**：G1 CATA>95% ✅ / G1 SLIP>90% ✅ / G2 对向<10% ✅（1.10%）/ G3 CATA>95% ✅（96.17%）/ G3 SLIP>95% ✅（99.60%）。**★UNMATCHED 14**（13 CATA + 48170 SLIP）→ 语义+方向不一致者**宁缺勿滥**。**⚠ 诚实披露**：SLIP 中位边数 **≈8** 恰压 `--slip-n-max=8` → **105/251（41.8%）SLIP 断面标 REVIEW**（OSM 匝道微段化正常结果；因聚合口径为 median，长链不引入系统偏差，REVIEW 仅"待复核"、不剔除；可用 `--slip-n-max 12` 重跑）。**Scope**：本表**仅覆盖 CATA+SLIP 两类**（590/1,311），CATB/CATC/CATD/CATE 仍用 6.3.2/7.3.4 基底。**关键原则**：**不覆盖 7.1 冻结靶场**（历史基准保留），本表用于改进后的 calibration experiment。readme 已同步（流程图、脚本清单 +1、§2.18、状态表、坑 51/52、复用命令 7.3.6A、冻结表、变更记录）。**冻结不动**：全部上游 + 7.1/7.2.1/7.2.2/7.3.1/7.3.2A/7.3.2B/7.3.2C/7.3.3/7.3.4/7.3.5；**λ 暂不冻结**。 |
| 2026-09-13 | **Step 7.3.5 SLIP_ROAD 候选几何补全（PASS，零仿真）**。用上传的 LTA 独立几何 `TrafficSpeedBands_Links.shp`（**143,787 LineString**，WGS84；`RoadCat` 为数字，**6=Slip Roads → 5,207 条**）补全 7.3.4 遗留的覆盖缺口。**运行前修复 3 处阻塞缺陷**：① `read_network` 用 **int64** 的 `from_node` join **字符串**节点索引 → `ValueError: merge on int64 and str` → `astype(str).str.strip()`；② `usecols=["node_id","x","y"]` 与实际 `network_nodes_source_copy.csv`（`x_svy21_m/y_svy21_m/lon/lat`）不符 → **坐标列自适应**；③ `old_had_candidate` 语义错误（计"任何边"而非"`motorway_link` 边"）→ 改为"**旧 crosswalk ∩ 网络 = motorway_link**"。AI 重写脚本并保留用户原件 `_build_slip_candidate_completion_7_3_5.py.user_orig_backup`。**新增**：ramp 用**真实 LineString**（非中点）做 line-to-line 距离；**CORE(251) vs FULL(5,207)** 双口径；**半径敏感性**；**最近同向匝道距离分布**；**113 vs 117 对账**。**★核心结果**：CORE 251 断面中，旧 crosswalk 含 `motorway_link` 仅 **138（54.98%）**、新几何 ≤80 m 达 **250（99.60%）**、仅同向 **248（98.80%）**、strict（同向+同名）**62（24.70%）**；**旧缺口 113 个补回 112 个（99.12%）**；**最近同向匝道距离中位 0.00 m / ≤5 m 覆盖 93.5% / ≤20 m 98.4%**；**半径 50 m 已 98.2%、200 m 无增益 → 半径非瓶颈**；唯一仍缺失 **48170（TAMPINES EXPRESSWAY，最近 ramp 227 m，近邻为主线）**。**★★判定：A（大量补回）** → 旧 crosswalk 的"**沿线采样 + 路名一致**"锚是瓶颈：LTA slip 的 `RoadName` 是**所属高速名**，OSM `motorway_link` 的 `name` 异构（**精确同名仅 29.1%**）→ 路名锚把匝道排除、断面被迫落到同名高速**主线**（= 7.3.3/7.3.4 的"匝道被主线化"）。**方法学含义**：SLIP→匝道指派改用 **"几何重合 + 同向"**，路名仅作辅助；7.3.4 的"SLIP 纯度上界"可被解除。**★113 vs 117 对账**：7.3.4 的 117 在其**约简的 `rebuilt_crosswalk.csv`（6,008 行 vs 13,163 行）**上统计；冻结基座权威缺口 = **113**。**结论/下一步**：(1) 覆盖缺口不是路网缺几何；(2) 下一步 = **Step 7.4 Network Representation / Crosswalk 覆盖修正**（按"几何重合+同向"重建 SLIP→`motorway_link` 指派，再用 6.3.3B linkstats 复算 Sim/Obs）；(3) route-choice 继续后置、λ 仍不冻结。readme 已同步（流程图、脚本清单 +1、§2.17、状态表、坑 49/50、复用命令 7.3.5、冻结表、变更记录）。**冻结不动**：全部上游 + 7.1/7.2.1/7.2.2/7.3.1/7.3.2A/7.3.2B/7.3.2C/7.3.3/**7.3.4**；**λ 暂不冻结**。 |
| 2026-09-13 | **Step 7.3.4 LTA 断面语义对齐重构 + Sim/Obs 收敛判别（PASS，零仿真）**。用户交付 `scripts/od/audit_section_rebuild_7_3_4.py`；AI **运行前修复 3 处阻塞缺陷**：① `NODES_DEFAULT` 指向**不存在**的 `network_nodes.csv`（实际 `network_nodes_source_copy.csv`，坐标列 `x_svy21_m/y_svy21_m/lon/lat`）→ 改路径 + **坐标列自适应（优先 lon/lat，与 LTA 断面 heading 同口径）**；② `load_traffic` 产出列名 `LinkID` 但 `build_candidates` 按 `lta_linkid` 合并 → `KeyError` → 合并前 `rename`；③ docstring `\L` 转义告警 → raw string（坑 47）。并**新增伴随分析** `analyze_section_rebuild_flow_7_3_4.py`（收敛判别 + 过滤归因 + 覆盖偏差），产出权威 `STEP7_3_4_REPORT.md`。**重构规则**：`同向 |Δθ|≤30°` + `RoadCat 语义允许集（CATA→{motorway}、SLIP_ROAD→{motorway_link}）` + 分级 fallback（strict→direction_name→name_fallback→original）。**重构结果**：边/断面 **10.30→4.70**（中位 8→**4**）、平均方向一致率 **97.51%**、混合 highway 断面 **1.56%**、strict 边占比 **87.47%**；**CATA 纯度 92.92%→97.64%**（达标）、**SLIP motorway_link 纯度 30.68%→52.99%**（改善未达标）。**★Sim/Obs 收敛（口径=7.1 冻结：`sim=median(匹配边 HRSx-yavg)×2.29897`，08-09）**：old CATA **0.7388** / SLIP **2.0333** / CATA÷SLIP **0.3633** → rebuilt(full) 0.7707 / 1.8796 / 0.4100 → **rebuilt(strict-only) 0.7797 / 0.8535 / 0.9135**。**★★过滤归因（决定性）**：`dir_only` CATA/SLIP **0.4199**（几乎不动）、**`sem_only` 即达 0.9658**（SLIP 1.8796→**0.8055**）→ **误差主因是"SLIP 观测断面被匹配到 motorway 主线而非 motorway_link 匝道"（语义错配），非方向、非 route choice**。**★覆盖偏差（诚实披露）**：strict 保留 CATA **326/339（obs 权重 97.4%）** 但 SLIP 仅 **129/251（obs 权重 49.7%）**；**117/251（46.6%）SLIP 断面在基座 crosswalk 中根本没有 `motorway_link` 候选**（其中 **104 个 dominant=motorway 主线**），CATA 仅 8/339（2.4%）缺 motorway 候选 → **SLIP 纯度存在由基座 crosswalk 决定的上界**（过滤无法凭空生成匝道几何，坑 48）。**结论**：(1) 结构倒挂**收敛成立且纯由语义错配造成**；(2) 残差 = **覆盖缺口**；(3) **CATA 各过滤下恒 ≈0.78**（old 0.739）→ 其 ~22% 系统性低估属**需求量级/全局尺度**、与 crosswalk 无关；(4) **停止 route-choice 参数扫描**，下一步 = **Step 7.4 network representation / crosswalk 覆盖修正**（对 ~47% 无匝道候选的 SLIP 断面重新推导断面语义），随后再议 λ / 需求尺度。**验收对照**：CATA 纯度 >95% ✅ / 对向边 <10% ✅（CATA 5.07%、SLIP 9.52%）/ 中位边数 ≪8–12 ✅（4）/ SLIP 纯度 >90% ❌（52.99%，候选集上界）/ CATA/SLIP 0.363→0.914 ✅✅。readme 已同步（流程图、脚本清单 +2 行、§2.16、状态表、坑 47/48、复用命令 7.3.4、冻结表、变更记录）。**冻结不动**：全部上游 + 7.1/7.2.1/7.2.2/7.3.1/7.3.2A/7.3.2B/7.3.2C/7.3.3/7.3.4；**λ 暂不冻结**。 |
| 2026-09-13 | **Step 7.3.3 LTA 断面语义 ↔ MATSim Link 表达专项审计（PASS，零仿真、纯诊断）**。用户交付 `scripts/od/audit_section_semantics_7_3_3.py`；**运行前修复 4 处缺陷 + 补 2 类验收产物**，输出 `reports/od_network_semantic_audit_7_3_3/`（9 产物）。**修复**：① `TrafficFlow_Data.json` 实为**长表**（75,899 行 = 1,311 断面 × 日期 × 小时 7/8；断面属性唯一）→ 原脚本按"一断面一行"merge 触发 `MergeError: not a many-to-one merge` → 加载后按 `LinkID` 去重到断面级（坑 44）；② 6.3.2 tight crosswalk **自带 `highway`/`RoadCat` 列** → 再合并 network/traffic 生成 `_x/_y` 并 `KeyError` → 合并前丢弃（坑 45）；③ docstring `\L` 转义告警；④ 报告 f-string 缺 `**`。**补产物**：验收清单内缺失的 `section_upstream_downstream.csv` + `roadcat_highway_correspondence.csv` + **对向车道指标**。**核心结果**：覆盖 **1,278/1,311=97.48%**（未覆盖 33 个恰为 `RoadCat=#N/A`）、**10.30 边/断面**（中位 8）、路名一致 **90.37%**；**★CATA↔motorway 语义干净**（CATA 339 断面：等级语义一致率 **99.23%**、dominant motorway 家族 **99.12%**（纯 motorway 92.92%）、含 motorway 边 97.94%、混合仅 16.81%）；**★SLIP_ROAD↔motorway_link 语义脏**（SLIP 251 断面：等级一致仅 **31.63%**、dominant 纯 motorway_link 仅 **30.68%**、而 **dominant=motorway 主线 55.8%**、混合 **47.81%**、路名一致仅 70.12%、平均 **11.69 边/断面 > CATA 7.13**）→ **匝道断面被"主线化"，系统性主线/匝道错配成立且方向不对称**；**一断面↔多边 & 一边↔多断面**：**28.10%** 匹配边被 ≥2 断面共享、**73.32%** 断面共享 ≥1 边；**★对向车道混入（不依赖 LTA 方向约定）**：**32.43%** 匹配边与自身断面模态方向相反、**72.07%** 断面含 ≥1 对向边、**15.49%** 含**精确互反配对**、仅 **8.53%** 断面可串**单一有向链**（CATA 仅 4.42%）；实例 CATA `45094`（CENTRAL EXPRESSWAY）同时匹配 `e20232_20225`(2.5°) 与 `e20225_20232`(177.5°) → **单方向断面观测被表达为双向微段集合**。**A/B/C 判定**：**C（观测-路网微段表达系统差异）由"嫌疑"升级为"直接证实"**，机制 (C1) SLIP 匝道被主线化 / (C2) 多对多重叠 / (C3) 方向语义未对齐；与 7.3.2C 反常信号自洽（SLIP 匹配边更多且混入主线 → sim/obs **2.046** 高估；CATA 双向碎片化 → sim/obs **0.685** 低估）。**结论**：误差主因在"观测断面语义 ↔ MATSim 微段表达"的对齐，**非 route preference**；route-choice 参数扫描继续后置，优先动 **network representation / crosswalk 语义对齐**（方向约束、匝道-主线分离、一对多聚合口径）。**网络版本**：本步 `network_links_source_copy.csv`（motorway 4,780 / motorway_link 9,086）vs 7.3.2A `network_cleaned.xml.gz`（4,744 / 9,026），差异 <1%，属清洗前/后口径。readme 已同步（脚本清单 +1 行、§2.15、状态表、坑 44/45/46、复用命令 7.3.3、冻结表、变更记录）。**冻结不动**：全部上游 + 7.1/7.2.1/7.2.2/7.3.1/7.3.2A/7.3.2B/7.3.2C；**λ 暂不冻结**。 |
| 2026-09-13 | **Step 7.3.2C Motorway Flow Spatial Loading Audit（PASS，零仿真、纯诊断）**。新增 `diagnose_motorway_loading_7_3_2c.py`（7.3.2C-1）+ `analyze_cata_spatial_correspondence_7_3_2c.py`（7.3.2C-2），输出 `reports/od_route_diagnosis_7_3_2c/`。**降本设计（关键）**：此前对 `plans.xml.gz` 全量对象化解析连续超时（每 route 建对象/建树）→ 改为**逐行二进制正则流式**（只提取 route links 并累计 motorway/motorway_link edge 计数，不建 XML 树、不建 route 对象），一次跑通（`unknown_link_uses=0`）；**events 不需要**。**7.3.2C-1**：122,110/200,000=**61.06%** route 用 motorway、**61.39%** 用 motorway_link（与 7.3.2B 逐位一致）；motorway 长度占比 **41.48%**（+ramp **47.29%**）；**edge 装载极度分散**——motorway 4,780 边/4,044 被用（**84.60%**）、**Top10=1.196%/Top50=5.46%/Top100=9.57%**（TOP 边全为 **Central Expressway 微段**、单边使用率仅 ≈9.67%，OTM 微段碎片化稀释）；转移 `m→m` 16.01M、`ml→ml` 5.12M、**`m→ml` 160,979 / `ml→m` 162,400**、`primary→ml` 84,887 / `ml→primary` 76,502。**7.3.2C-2**：全网 motorway 均值 3,383.9 次/边；339 CATA 断面中 332 有 motorway 匹配；**CATA 装载指数 mean 0.846 / median 0.780**（**64.5% 低于全网均值**）、`r(装载指数,sim/obs)=+0.19（n=332）`（装载仅解释 ~3.6% 方差）；**★决定性对照：CATA vs SLIP_ROAD 装载指数几乎相同（0.846/0.852；median 0.780/0.767）但 sim/obs 相反（0.685/2.046）⇒ edge 级装载无法区分被低估的快速路主线与被高估的匝道**。**A/B/C 判定**：A 彻底否定；**B 弱-部分成立**（CATA 轻度低载但 r 弱）；**C 强支持（主因嫌疑）**——观测↔微段路网表达的系统性差异（碎片化下断面空间对位、点计数 vs 微边口径）。**结论**：motorway 被大量使用、装载极分散、CATA 略低载但非判别变量 → 剩余误差高度指向 **C 类**，**route-choice 参数扫描优先级进一步下调**。**下一步（建议）**：**Step 7.3.3 Observation–Representation Diagnosis（观测-表达专项，零仿真）**——(a) SLIP_ROAD 为何系统性高估；(b) CATA `r≈0` 的微段-断面多对一排序损失；(c) CATA 聚到**走廊级**后 sim/obs 是否回升。readme 已同步（流程图、脚本清单 +2 行、§2.14、状态表、坑 42、复用命令 7.3.2C、冻结表、变更记录）。**冻结不动**：全部上游 + 7.1/7.2.1/7.2.2/7.3.1/7.3.2A/7.3.2B；**λ 暂不冻结**。 |
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

---

## 8. 历史归档结论（自 `MEMORY.md` 转存）

> 2026-09-17 按用户批准，从 `Static_ 2026_03/.workbuddy/memory/MEMORY.md` 的「已固化结论」中
> **移出以下历史条目、原样转存于此**，使长期记忆只保留**当前仍生效的冻结口径 / 判决 / 硬约束**。
> 内容未作任何实质修改，仅位置变更。

- **2025 稳健性**：GHS 2025 `Car Only` **21.18%** ≈ Census 2020 **21.12%** ⇒ 2020 锚**无系统偏差**，总量 **+8.20%**。
- **Step 7.5B `PARTIAL_IMPROVEMENT`**（D 0/6、M 3/4）：纯比例采样系统性剔除长距离 OD 对
  （平均行程距离 −10.2% → 断面流量 −28.7%，放大 ≈6×）；缺口是**全断面等比收缩**而非归零。
  （实验设计与结果详见 §2.24。）
- **★两种「振幅」不可混用**：`parity_gap_rel = |even−odd|/mean`（只含奇偶分离）
  vs `A_W = (Q_max−Q_min)/Q̄`（含奇偶分离 + 窗内漂移）。D01 MATCHED 二者 = **1.59% vs 8.48%（5.3×）**。
  引「20.75%」须注明是 D03 的 `parity_gap_rel`。
