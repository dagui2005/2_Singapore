# Step 7.3.2B — Route Structure / Path-choice Diagnosis 报告

**日期**：2026-09-12
**状态**：✅ PASS（诊断层；**不改 OD / λ / population / departure / network / capacity / crosswalk**）
**数据源**：6.3.3B λ=0.05 `it.0` 的 `output_plans.xml.gz`（route type=links 完整 link 序列）+ `output_trips.csv.gz`（200,000 行）+ 冻结 `network_links_source_copy.csv`（等级/长度）。**events 不需要**——plans 已含完整路径。

## 1. 运行前修复的脚本缺陷

1. **`network_links_source_copy.csv` 没有 `matsim_link_id` 列**（只有 `from_node/to_node`）→ 原脚本必抛"缺字段"。已按 6.1 建网约定构造 `matsim_link_id = "e" + from_node + "_" + to_node`（Step 4 审计确认 0 重复有向边 → 构造 id 唯一）。
2. **性能**：原稿每条 route 调 `classify_route` **两次**且逐 link 用 `df.loc`（数千万次索引查询）→ 改为**单次遍历** + `highway/length` 字典视图，200k routes 分钟级完成。
3. 运行时显式传参：实际文件名为 `step6_3_3b_lambda_0p050.0.{trips.csv.gz,plans.xml.gz}`（非默认 `output_*`）。

## 2. 核心结果

| 指标 | 值 |
|---|---|
| trips / routes / 成功对接 | **200,000 / 200,000 / 200,000**（plans route 单行可解析，`person` 一致） |
| route 中未知 link 数 | **0**（`e{from}_{to}` 构造后全覆盖） |
| **使用 motorway 的路线** | **122,110 = 61.06%** |
| 使用 motorway_link 的路线 | 122,774 = 61.39% |
| 含 `motorway→motorway_link→motorway` 精确三元组 | **0 条**（匝道在路径中呈**链状**：`ml→ml` 转移高达 5.12M 次，无"单匝道即出即进"） |
| **OD 对数 / 多路径 OD 对** | **196,447 / 0（0.0000%）**——当前 λ=0.05、it.0 下**完全确定性单一路径**（与 SpeedyALT + 单迭代一致） |
| 总路线长度 | 2,807,035 km（均值 ≈14.0 km/路线，与 MATSim avg trip distance 14,309 m 一致） |

**路线长度按等级占比**（`route_class_summary.csv`）：

| highway | 长度 (km) | 占比 | 使用路线数 | 使用率 |
|---|---|---|---|---|
| **motorway** | 1,164,270 | **41.48%** | 122,110 | 61.1% |
| primary | 779,263 | 27.76% | 192,253 | 96.1% |
| trunk | 275,033 | 9.80% | 84,820 | 42.4% |
| **motorway_link** | 163,148 | **5.81%** | 122,774 | 61.4% |
| secondary | 159,917 | 5.70% | 138,395 | 69.2% |
| 其余（residential/tertiary/service/link 等） | 235,405 | 8.4% | — | — |

**等级间转移**（`route_transition_matrix.csv`，前几位）：`motorway→motorway` 16.01M、`motorway_link→motorway_link` **5.12M**、`motorway→motorway_link` 160,979、`motorway_link→motorway` 162,400、`primary→motorway_link` 84,887、`motorway_link→primary` 76,502。用 ramp 的路线平均穿越 ~42 个 `motorway_link` 微段（平均单段仅 ~30 m——**路网碎片化表达**，非异常长匝道）。

## 3. A / B / C 三分判定（对照预注册问题）

> **A. 高速实际上很少被选择？** → **否定。** 61.1% 路线、41.5% 路线长度使用 motorway；motorway 是路线长度第一大等级。结合 7.1 靶场（CATA sim/obs **0.584/0.739** 低于总体 **0.744/0.889**）：高速**被大量使用但相对仍不足/错位**，不是"绕开高速"。
>
> **B. 高速被选择，但流量被分散到大量 MATSim 边？** → **部分成立，且机制已定位。** 同一 OD **完全单一路径**（0/196,447 多路径），分散只可能来自 **OD 级空间差异**（不同 OD 各走各的高速段），而非同 OD 多路径摊薄。SLIP_ROAD 高估（1.594/2.033）与 **ramp 链**现象一致：匝道以长链（~42 个微段/路线）进入最短路，被当作正常通行路径使用。
>
> **C. 高速使用正常，但 LTA 观测与 MATSim 路段表达存在系统差异？** → **保留，待断面级验证。** 需把本步 route 分类与 7.1 冻结靶场做**断面级对应**（route link 集合 × crosswalk 断面归属），才能区分"CATA 断面附近确实少走"还是"走了但 LTA 观测点位与 MATSim 边表达错位"。

**判定：A 已排除；B/C 的最终分辨需下一步做 route×crosswalk 断面级对照（7.3.3 候选）。**

## 4. 对下一步（7.3.3）的指向

1. **route×crosswalk 断面级对照**（零仿真成本）：对 1,278 个 LTA 断面，统计其对应 MATSim 边上"是否被 route 使用 + 使用量 vs 靶场 sim/obs"，直接定位 CATA 低估是空间错位还是表达差异；
2. route-choice 参数实验（ReRoute fraction / plan memory）**优先级进一步下降**——路径已是确定性最短路且高速使用率高，参数微调不改变"哪条高速段被走"的结构；
3. ramp 链/碎片化提示：若后续修网络，`motorway_link` 过碎（~30 m/段）值得合并审视，但**本轮不改网络**。

## 5. 冻结关系

- 冻结不动：3B.1/4/5B/5C.1/6.1/6.2/6.2B/6.3.2/6.3.3A/6.3.3B/7.1/7.2.1/7.2.2/7.3.1/**7.3.2A**；
- **λ 暂不冻结**（0.05 诊断基准）；`frozen_parameters_unchanged=true`。

## 6. 产物清单

```
reports/od_route_diagnosis_7_3_2b/
├─ route_agent_summary.csv           # 逐 agent 路线诊断（长度占比、模式标记）
├─ route_class_summary.csv           # 等级长度占比 + 使用率
├─ route_transition_matrix.csv       # 等级间转移计数
├─ route_od_consistency.csv          # 196,447 OD × (agents, unique_routes)
├─ route_diagnosis_summary.json      # 汇总（status=PASS, frozen_parameters_unchanged=true）
└─ STEP7_3_2B_REPORT.md              # 本报告
```

脚本：`scripts/od/diagnose_route_structure_7_3_2b.py`（运行前修复：`e{from}_{to}` id 构造 + 单遍历/字典查询提速 + 显式文件名传参）。

```bat
python scripts\od\diagnose_route_structure_7_3_2b.py ^
  --trips  reports\matsim_assignment_6_3_3b\lambda_0p050\ITERS\it.0\step6_3_3b_lambda_0p050.0.trips.csv.gz ^
  --plans  reports\matsim_assignment_6_3_3b\lambda_0p050\ITERS\it.0\step6_3_3b_lambda_0p050.0.plans.xml.gz
```
