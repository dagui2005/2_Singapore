# Step 6.3 第一次 MATSim AM Assignment 对照报告

> **单次迭代 QSim**（`firstIteration=lastIteration=0`）——纯 AM peak static assignment baseline。
> 网络 `reports/matsim_network/network_cleaned.xml.gz`（car 主连通分量，693,575 边）：
> car 连通性检查 **0 边被移除**（修复前会 abort）。
> 人口 `reports/matsim_population_6_2b_connected/population_lambda_*.xml.gz`（连通性修复后，
> 每 λ 200,000 agents，其中约 5,100 个端点在碎片里的 agent 重吸附，位移中位 3.3 m）。

## 1. 对照口径

```
LTA TrafficFlow LinkID --(lta_osm_match_v2.csv)--> osm_edge_index
    --(network_links_source_copy.csv 行号)--> (from_node,to_node)
    --> MATSim link id = e{from}_{to}
```
- 匹配 LTA 链路 **1,278** 条（TrafficFlow 全量 1,311 中 1,278 有几何匹配）
- 观测：`TrafficFlow_Data.json`（2025-11，30 天；Volume 千分位逗号已还原），hour ∈ {7,8}，
  每条 (LinkID,hour) 有效观测 n ≥ 5
- 交叉核验：本脚本重算中位数 vs `reports/od_audit/audit_trafficflow.csv` 最大偏差 **0.0000**

## 2. 两个必须说明的口径（否则会误读结果）

### 2.1 规模口径：仿真车数需 ×2.299

population 是 **200,000 agents 代表 459,794 次 car 出行**（`EF_ij = T_ij / N_ij`）。
QSim 的 linkstats 计的是实际车辆数（200k），所以与真实观测对照需乘
`scale = ΣEF / N_agents = 459,794 / 200,000 = 2.29897`。
本报告同时给出 **raw**（不乘）与 **scaled**（×2.299）两套；**scaled 为主口径**。

### 2.2 时窗口径：冻结 population 全部 08:00 出发

全部 200,000 个 agent 的 home `end_time` = **08:00:00**，work 无 `end_time`。
因此 QSim 在 08:00 一次性释放全部 AM 需求：
- `HRS7-8` **恒为 0**（结构性，不是模型误差）
- `HRS8-9` = 整个 AM 脉冲
- 主对照取：sim `HRS8-9` vs obs `(hour7+hour8)`（两者都代表「整个 AM 高峰」）

## 3. 汇总指标（三套 λ，scaled 主口径）

| λ | scale | 对照链路 | Σsim | Σobs | sim/obs | Pearson r | Spearman ρ | NRMSE | %GEH<5 | %GEH<10 | GEH中位 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 0p050 | 2.2990 | 1278 | 2,851,808 | 4,409,374 | 0.647 | 0.306 | 0.358 | 1.104 | 7.5 | 15.2 | 32.3 |
| 0p075 | 2.2990 | 1278 | 2,848,065 | 4,409,374 | 0.646 | 0.308 | 0.359 | 1.103 | 8.4 | 15.3 | 31.9 |
| 0p100 | 2.2990 | 1278 | 2,858,551 | 4,409,374 | 0.648 | 0.308 | 0.358 | 1.103 | 8.5 | 15.1 | 31.8 |

### 3.1 raw vs scaled（看规模口径的影响）

| λ | Σsim raw | sim/obs raw | Σsim scaled | sim/obs scaled |
|---|---:|---:|---:|---:|
| 0p050 | 1,240,472 | 0.281 | 2,851,808 | 0.647 |
| 0p075 | 1,238,844 | 0.281 | 2,848,065 | 0.646 |
| 0p100 | 1,243,405 | 0.282 | 2,858,551 | 0.648 |

### 3.2 逐时（说明时刻剖面）

| λ | H8 Σsim(scaled) | H8 Σobs(hour8) | H8 ratio | H8 r | H7 Σsim(raw) | H7 Σobs(hour7) |
|---|---:|---:|---:|---:|---:|---:|
| 0p050 | 2,851,808 | 2,285,817 | 1.248 | 0.290 | 0 | 2,123,557 |
| 0p075 | 2,848,065 | 2,285,817 | 1.246 | 0.291 | 0 | 2,123,557 |
| 0p100 | 2,858,551 | 2,285,817 | 1.251 | 0.292 | 0 | 2,123,557 |

### 3.3 按道路类别（λ=0.05，scaled）

| RoadCat | 链路数 | Σsim | Σobs | sim/obs | sim>0 占比 |
|---|---:|---:|---:|---:|---:|
| CATB | 634 | 906,774 | 1,385,602 | 0.654 | 89.9% |
| CATA | 339 | 1,273,875 | 2,498,903 | 0.510 | 86.1% |
| SLIP_ROAD | 251 | 604,749 | 443,956 | 1.362 | 89.2% |
| CATC | 46 | 54,348 | 65,786 | 0.826 | 93.5% |
| CATD | 7 | 12,024 | 14,600 | 0.824 | 100.0% |
| CATE | 1 | 39 | 527 | 0.074 | 100.0% |

> **CATA=expressway，CATB=arterial，SLIP_ROAD=匝道。** 仿真在**快速路（CATA）上系统性偏低**，
> 这是本轮到最重要的结构性信号，见 §5。

## 4. 各 λ 观测 vs 仿真 Top-20 链路（按 obs AM 降序，scaled）

### λ = 0p050

| LinkID | RoadName | Cat | sim | obs | sim/obs | GEH |
|---|---|---|---:|---:|---:|---:|
| 49839 | KALLANG PAYA LEBAR EXPRESS | CATA | 0 | 34,702 | 0.000 | 263.4 |
| 49662 | KALLANG PAYA LEBAR EXPRESS | CATA | 2 | 34,508 | 0.000 | 262.7 |
| 49685 | KALLANG PAYA LEBAR EXPRESS | CATA | 3,671 | 34,015 | 0.108 | 221.0 |
| 49651 | KALLANG PAYA LEBAR EXPRESS | CATA | 851 | 32,934 | 0.026 | 246.9 |
| 49649 | KALLANG PAYA LEBAR EXPRESS | CATA | 0 | 30,733 | 0.000 | 247.9 |
| 49844 | KALLANG PAYA LEBAR EXPRESS | CATA | 0 | 30,436 | 0.000 | 246.7 |
| 49684 | KALLANG PAYA LEBAR EXPRESS | CATA | 9 | 21,390 | 0.000 | 206.7 |
| 49716 | KALLANG PAYA LEBAR EXPRESS | CATA | 7 | 21,348 | 0.000 | 206.5 |
| 49699 | KALLANG PAYA LEBAR EXPRESS | CATA | 876 | 20,637 | 0.042 | 190.5 |
| 49687 | KALLANG PAYA LEBAR EXPRESS | CATA | 0 | 19,934 | 0.000 | 199.7 |
| 49934 | KALLANG PAYA LEBAR EXPRESS | CATA | 303 | 17,334 | 0.018 | 181.4 |
| 49771 | KALLANG PAYA LEBAR EXPRESS | CATA | 0 | 15,488 | 0.000 | 176.0 |
| 191208 | KALLANG PAYA LEBAR EXPRESS | CATA | 1,522 | 15,376 | 0.099 | 150.7 |
| 49909 | KALLANG PAYA LEBAR EXPRESS | CATA | 7 | 14,540 | 0.000 | 170.4 |
| 49702 | KALLANG PAYA LEBAR EXPRESS | CATA | 0 | 14,468 | 0.000 | 170.1 |
| 49912 | KALLANG PAYA LEBAR EXPRESS | CATA | 0 | 12,793 | 0.000 | 160.0 |
| 49895 | KALLANG PAYA LEBAR EXPRESS | CATA | 3,736 | 11,817 | 0.316 | 91.6 |
| 49892 | KALLANG PAYA LEBAR EXPRESS | CATA | 1,984 | 11,496 | 0.173 | 115.9 |
| 46008 | PAN ISLAND EXPRESSWAY | CATA | 0 | 10,221 | 0.000 | 143.0 |
| 47432 | SELETAR EXPRESSWAY | CATA | 7,069 | 10,064 | 0.702 | 32.4 |

### λ = 0p075

| LinkID | RoadName | Cat | sim | obs | sim/obs | GEH |
|---|---|---|---:|---:|---:|---:|
| 49839 | KALLANG PAYA LEBAR EXPRESS | CATA | 0 | 34,702 | 0.000 | 263.4 |
| 49662 | KALLANG PAYA LEBAR EXPRESS | CATA | 0 | 34,508 | 0.000 | 262.7 |
| 49685 | KALLANG PAYA LEBAR EXPRESS | CATA | 3,784 | 34,015 | 0.111 | 219.9 |
| 49651 | KALLANG PAYA LEBAR EXPRESS | CATA | 862 | 32,934 | 0.026 | 246.7 |
| 49649 | KALLANG PAYA LEBAR EXPRESS | CATA | 0 | 30,733 | 0.000 | 247.9 |
| 49844 | KALLANG PAYA LEBAR EXPRESS | CATA | 0 | 30,436 | 0.000 | 246.7 |
| 49684 | KALLANG PAYA LEBAR EXPRESS | CATA | 2 | 21,390 | 0.000 | 206.8 |
| 49716 | KALLANG PAYA LEBAR EXPRESS | CATA | 2 | 21,348 | 0.000 | 206.6 |
| 49699 | KALLANG PAYA LEBAR EXPRESS | CATA | 812 | 20,637 | 0.039 | 191.4 |
| 49687 | KALLANG PAYA LEBAR EXPRESS | CATA | 0 | 19,934 | 0.000 | 199.7 |
| 49934 | KALLANG PAYA LEBAR EXPRESS | CATA | 303 | 17,334 | 0.018 | 181.4 |
| 49771 | KALLANG PAYA LEBAR EXPRESS | CATA | 0 | 15,488 | 0.000 | 176.0 |
| 191208 | KALLANG PAYA LEBAR EXPRESS | CATA | 1,416 | 15,376 | 0.092 | 152.4 |
| 49909 | KALLANG PAYA LEBAR EXPRESS | CATA | 2 | 14,540 | 0.000 | 170.5 |
| 49702 | KALLANG PAYA LEBAR EXPRESS | CATA | 0 | 14,468 | 0.000 | 170.1 |
| 49912 | KALLANG PAYA LEBAR EXPRESS | CATA | 0 | 12,793 | 0.000 | 160.0 |
| 49895 | KALLANG PAYA LEBAR EXPRESS | CATA | 3,839 | 11,817 | 0.325 | 90.2 |
| 49892 | KALLANG PAYA LEBAR EXPRESS | CATA | 2,090 | 11,496 | 0.182 | 114.1 |
| 46008 | PAN ISLAND EXPRESSWAY | CATA | 0 | 10,221 | 0.000 | 143.0 |
| 47432 | SELETAR EXPRESSWAY | CATA | 7,154 | 10,064 | 0.711 | 31.4 |

### λ = 0p100

| LinkID | RoadName | Cat | sim | obs | sim/obs | GEH |
|---|---|---|---:|---:|---:|---:|
| 49839 | KALLANG PAYA LEBAR EXPRESS | CATA | 0 | 34,702 | 0.000 | 263.4 |
| 49662 | KALLANG PAYA LEBAR EXPRESS | CATA | 7 | 34,508 | 0.000 | 262.6 |
| 49685 | KALLANG PAYA LEBAR EXPRESS | CATA | 3,784 | 34,015 | 0.111 | 219.9 |
| 49651 | KALLANG PAYA LEBAR EXPRESS | CATA | 807 | 32,934 | 0.025 | 247.3 |
| 49649 | KALLANG PAYA LEBAR EXPRESS | CATA | 0 | 30,733 | 0.000 | 247.9 |
| 49844 | KALLANG PAYA LEBAR EXPRESS | CATA | 0 | 30,436 | 0.000 | 246.7 |
| 49684 | KALLANG PAYA LEBAR EXPRESS | CATA | 7 | 21,390 | 0.000 | 206.7 |
| 49716 | KALLANG PAYA LEBAR EXPRESS | CATA | 5 | 21,348 | 0.000 | 206.6 |
| 49699 | KALLANG PAYA LEBAR EXPRESS | CATA | 874 | 20,637 | 0.042 | 190.6 |
| 49687 | KALLANG PAYA LEBAR EXPRESS | CATA | 0 | 19,934 | 0.000 | 199.7 |
| 49934 | KALLANG PAYA LEBAR EXPRESS | CATA | 290 | 17,334 | 0.017 | 181.6 |
| 49771 | KALLANG PAYA LEBAR EXPRESS | CATA | 0 | 15,488 | 0.000 | 176.0 |
| 191208 | KALLANG PAYA LEBAR EXPRESS | CATA | 1,393 | 15,376 | 0.091 | 152.7 |
| 49909 | KALLANG PAYA LEBAR EXPRESS | CATA | 5 | 14,540 | 0.000 | 170.4 |
| 49702 | KALLANG PAYA LEBAR EXPRESS | CATA | 0 | 14,468 | 0.000 | 170.1 |
| 49912 | KALLANG PAYA LEBAR EXPRESS | CATA | 0 | 12,793 | 0.000 | 160.0 |
| 49895 | KALLANG PAYA LEBAR EXPRESS | CATA | 3,844 | 11,817 | 0.325 | 90.1 |
| 49892 | KALLANG PAYA LEBAR EXPRESS | CATA | 2,127 | 11,496 | 0.185 | 113.5 |
| 46008 | PAN ISLAND EXPRESSWAY | CATA | 0 | 10,221 | 0.000 | 143.0 |
| 47432 | SELETAR EXPRESSWAY | CATA | 7,065 | 10,064 | 0.702 | 32.4 |

## 5. 结论与下一步

**已打通**：Population → MATSim routing → QSim → 每 link 每小时 `q_a^sim` / `t_a^sim`
（`v_a^sim = LENGTH / t_a^sim`），并首次与 LTA AM 观测做了逐链路对照。

**结果**（scaled 主口径）：
- 总量：仿真约为观测的 **65%**（λ=0.05，Σsim/Σobs = 0.647）。
  缺口主要来自**口径差**：观测含全部交通（货运/非通勤/商务），而我们只建了**car 通勤**
  （Σ=459,794 次）。故「仿真偏低」在预期内，不能直接判模型错。
- 空间相关：Pearson r ≈ **0.31**、Spearman ρ ≈ **0.36** —— **偏弱**。
- GEH：GEH<5 仅 **7.5%–8.5%**，远低于交通工程常用的 85% 阈值 → 逐链路拟合差。
- **λ 几乎不可分辨**：λ=0.05/0.075/0.10 的 ratio 0.647/0.646/0.648、r 0.306/0.308/0.308、
  GEH<5 7.5%/8.4%/8.5% 几乎完全相同。说明**在当前对照精度下无法用 assignment 定 λ***，
  必须先修好对照口径（否则 Step 7 的 argmin_λ 只会拟合噪声）。
- **时刻剖面副产物**：因全部需求 08:00 一次性释放，车队到 **09:00 仍有 85,838 辆**在网、
  10:00 有 21,146、12:00 才降到 322；平均通勤耗时被抬到 **61.8 min**、全网均速仅 ~19 km/h。
  这是单时刻出发造成的**人为拥堵**，也再次说明需要出发时刻分布。

**结构性信号**：按道路类别（λ=0.05，scaled）：CATB 0.65、**CATA 0.51**、CATC 0.83、
**SLIP_ROAD 1.36**。即仿真**低估快速路、高估匝道**——与 §5 的 crosswalk 粒度问题方向一致。

**最需要修的不是 OD，而是对照用的 crosswalk 粒度**：
`lta_osm_match_v2.csv` 是 Step 5C.1 为**速度传播**建立的「每 LTA 链路取 1 条最近 OSM 边」。
但 LTA 监测链路是一整段（100–500 m），OSM 把它拆成多条 13–100 m 短边。
实测 KPE（Kallang–Paya Lebar Expressway）：网络上 KPE 全边 **432 条、仿真通过 188,481 次**，
而 crosswalk 只映射到 22 条、仅捕获 **6,156 次（3.3%）** → 快速路流量被系统性低估。
这是 r 偏低与 GEH 差的主因。

**建议的下一步（建议单独门控 6.3.2）**：
1. **升级对照 crosswalk**：对每条 LTA 监测链路，用其 `Start/End` 几何（WGS84→SVY21）+ 归一化路名
   + 方向一致，圈出全部走廊 OSM 边，在边上取**中位数**（同向顺序边流量应相近）作为该断面的
   `q_a^sim`；对快速路优先匹配 `motorway` 主车道而非匝道。
2. **时刻剖面**：给 population 加 AM 出发时刻分布（07:00–09:00），使逐时对照有物理意义。
3. **规模一致性**：把 200k 抽样与 459,794 的关系显式化——或设
   `qsim.flowCapacityFactor = 200000/459794 = 0.435` 让拥堵程度与全量一致，并统一用 scaled 口径。
4. 上述完成后，再进 Step 7 做 `argmin_λ Error(q_sim, q_obs)` 定 λ*，并分离
   「非通勤流量」的缩放（引入一个 AM 全交通/通勤倍率）。

