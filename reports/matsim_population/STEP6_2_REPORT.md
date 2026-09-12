# Step 6.2 — Prior OD → MATSim Population / Plans

**状态：PASS**（独立结构复核通过）
**日期：** 2026-09-12
**脚本：** `scripts/od/build_matsim_population.py`
**独立校验：** `scripts/od/validate_matsim_population.py`
**输出：** `reports/matsim_population/`

---

## 1. 这一步做了什么

把 **car-only Prior OD** 转成可被 MATSim 直接读取的 agent population，链路为：

```text
5C.1 all-mode Prior OD T_ij^5C.1
        │  ①按 Step-2 car production P_car 与 Table 118 car-only
        │    (ResidenceRegion × WorkplacePA) 结构重投影
        ▼
car-only Prior OD T_ij^car      （总量 = 459,794，与 P_car 逐位一致）
        │  ② 多测度抽样：每 cell 按 trips 体积采样 agent，记录 expansion factor
        ▼
agents（λ 各 200,000）          （home activity → car leg → work activity）
        │  ③ 用冻结的 zone_matsim_node_map.csv + network link 挂载
        ▼
population_lambda_*.xml.gz      （activity 使用 MATSim **link id**，非 node id）
```

**严格没有做**（留给 Step 6.2B）：住宅/就业空间点下分（URA/HDB/建筑）、agent 出发时刻分布、MATSim rerouting 准备。
**没有塞进网络**：`Works from Home`、`No Fixed Location for Work`、`Other Planning Areas or Outside Singapore` 三类特殊就业质量继续单独保留，仍不属于 332×332 physical OD。

---

## 2. 运行前修复的两个脚本缺陷

「已整理好」的脚本第一版**跑不起来 / 结果不可用**，运行前修复两处致命缺陷：

| # | 缺陷 | 现象 | 修复 |
|---|---|---|---|
| 1 | 列名不匹配 | 搜索 `car_work_production`/`P_car`/… ，但 `production.csv` 实际列名是 **`car_work_trip_production`** → `ValueError: production.csv lacks car-only production field`，脚本直接崩溃 | 候选列加入 `car_work_trip_production` |
| 2 | **吸引口径错** | 目的地列边际用了 **raw** `workplace_attraction`（307 个非零），而冻结先验 OD 用的是 **cleaned** `workplace_attraction_clean`（304 个非零，无路网离岛已置 0）。多出的 3 个目标列（zone 258/322/323）**永远无法被 seed 填充** → IPF 10,000 次迭代不收敛（行误差 31.1、列误差 397.2） | 改用**冻结的** cleaned 吸引（`attraction_clean_5c1.csv`，回退 `attraction_carbon.csv`，再回退按 5B 规则就地重算），使 seed 支撑与列边际支撑完全一致 |

**修复后：** IPF 13–14 次迭代收敛，行误差 ≤8.6e-9、列误差 ≤1.0e-11，`car_od_total = 459,794` 与 car production 逐位一致。

> 缺陷 2 的根因：脚本作者自己的注释写的是「proportional to **frozen** workplace attraction v2.1」——冻结量正是 cleaned 版本。属 bug，不是设计改动。

---

## 3. 产物清单

| 文件 | 内容 |
|---|---|
| `population_lambda_0p050.xml.gz` | λ=0.05，200,000 agents，2.44 MB |
| `population_lambda_0p075.xml.gz` | λ=0.075，200,000 agents，2.43 MB |
| `population_lambda_0p100.xml.gz` | λ=0.10，200,000 agents，2.41 MB |
| `agent_zone_assignment_lambda_*.csv` | 逐 agent：`agent_id, origin_zone, destination_zone, home_node, work_node, home_link, work_link, expansion_factor` |
| `car_prior_od_lambda_*.parquet/.csv` | car-only Prior OD（`origin_zone, destination_zone, trips`），71,136 非零 cell |
| `population_summary.csv` | 5 项守恒/收敛指标 × 3 个 λ |
| `population_validation.json` | 自报告 PASS/WARN + 口径说明 |
| `population_independent_check.json` | **独立结构复核**（重新解析 XML） |

---

## 4. 验收结果

### 4.1 守恒与收敛（`population_summary.csv`）

| λ | car_od_total | 行最大误差 | 列最大误差 | IPF 收敛 | 迭代 | agents | expansion 中位 |
|---|---|---|---|---|---|---|---|
| 0.050 | 459,794.0 | 7.95e-9 | 8.19e-12 | ✅ True | 13 | 200,000 | 2.031 |
| 0.075 | 459,794.0 | 2.46e-9 | 6.37e-12 | ✅ True | 14 | 200,000 | 2.044 |
| 0.100 | 459,794.0 | 8.56e-9 | 1.00e-11 | ✅ True | 14 | 200,000 | 2.044 |

car-only OD 总量 **459,794** = Step-2 `car_work_trip_production` 合计，逐位一致。

### 4.2 独立结构复核（`population_independent_check.json`）

重新解析三个 `population_*.xml.gz`（429,032 节点 / 706,554 link 的 frozen network），逐 agent 校验：

| 检查项 | λ=0.05 | λ=0.075 | λ=0.10 |
|---|---|---|---|
| persons | 200,000 | 200,000 | 200,000 |
| plan 结构异常（非 home→car→work） | 0 | 0 | 0 |
| activity link **不存在于 network** | 0 | 0 | 0 |
| link 与声明 node **不邻接** | 0 | 0 | 0 |
| link 与 zone_matsim_node_map **不一致** | 0 | 0 | 0 |
| zone 越界（非 332 物理 Subzone） | 0 | 0 | 0 |
| expansion factor 非有限/非正 | 0 | 0 | 0 |
| **ALL_CHECKS_PASS** | ✅ | ✅ | ✅ |

- 每个 activity 的 `link` 都是**真实 MATSim link id**（`e{from}_{to}`），**不是 node id** —— 已明确排除「表面上合法、MATSim 无法解释」的 `activity link=node_id` 错误。
- `home_link`/`work_link` 均与该 zone 经 `zone_matsim_node_map.csv` 映射到的 node 邻接。

### 4.3 抽样代表性（需要你注意）

| λ | 非零 OD cell | 有 ≥1 agent 的 cell | agents/cell 中位 | expansion Σ（真实等价出行） | 占 459,794 |
|---|---|---|---|---|---|
| 0.050 | 71,136 | 41,940（**59.0%**） | 3 | 431,462 | **93.84%** |
| 0.075 | 71,136 | 41,410（58.2%） | 3 | 431,647 | 93.88% |
| 0.100 | 71,136 | 40,969（57.6%） | 3 | 431,706 | 93.89% |

> ⚠️ **200,000 agents 下，约 59% 的 OD cell 被采样覆盖，代表的出行量约 93.8%**。剩余 ~6.2% 的出行量集中在 **trips 极小（最低 0.001）的 OD cell** —— 按 `trips` 体积做多项抽样时，小 cell 期望 agent 数 <1，被自然漏掉。
>
> 这不是 bug，是「按体积抽样」的固有特性。**影响**：MATSim link 流量层面只损失 ~6% 质量（可用全局 expansion 标定解释）；但**OD 回溯**层面，约 41% 的 cell 在网络里没有 agent 可追踪。
>
> **建议在 Step 6.2B 处理**：改为「**每非零 cell 保底 1 个 agent** + 剩余名额按体积分配」（200k > 71,136，完全可行），可让 cell 覆盖 100%、expansion Σ 精确等于 459,794。

### 4.4 car-only vs all-mode 的差异（context）

| λ | car-only 加权平均 AM 时长 | all-mode 5C.1 | 比值 |
|---|---|---|---|
| 0.050 | 18.478 min | 18.082 min | 1.022 |
| 0.075 | 18.211 min | 17.811 min | 1.022 |
| 0.100 | 17.946 min | 17.533 min | 1.024 |

car-only OD 的平均通勤时长比 all-mode **长 ~2.2%**：Table 118 的 car 结构使跨区（长距离）通勤占比略升，符合预期。car-only intrazonal 份额 0.83%–1.15%，随 λ 上升（重罚跨区 → 略偏本地）。

---

## 5. 冻结关系（本轮不变）

```text
Step 3B.1  Attraction v2.1              ✅ 冻结
Step 4     Free-flow impedance C^FF      ✅ 冻结
Step 5B    Census-constrained Prior OD   ✅ 基线
Step 5C.1  AM-v2 Prior OD T_ij^5C.1      ✅ 当前候选
Step 6.1   MATSim network.xml.gz         ✅ 冻结（本轮确认）
Step 6.2   car-only population           ✅ 本轮产物（第一版「网络可运行人口」）
λ = 0.05 / 0.075 / 0.10                  ⏳ 仍未冻结
Step 6.2B  住宅/就业空间下分 + 时间属性   → 下一步
Step 7     TrafficFlow calibration       → 最终 λ*
```

---

## 6. 复现命令

```bat
cd /d D:\Luan\2026-05\2_Singapore
python scripts\od\build_matsim_population.py
python scripts\od\build_matsim_population.py --target-agents 300000
python scripts\od\validate_matsim_population.py
```
