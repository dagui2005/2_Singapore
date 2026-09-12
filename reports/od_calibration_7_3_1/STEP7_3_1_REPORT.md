# Step 7.3.1 — Congestion-feedback Sensitivity 报告

**日期**：2026-09-12
**状态**：✅ PASS（实验执行完整 + 双重确定性验证 PASS + 结构判读闭合）
**口径**：λ=0.05（冻结实验基准）；capacity 固定 1.0（7.2.2 已证非结构杠杆）；OD / population（6.3.3A）/ departure profile / network topology / permlanes / crosswalk 全冻结。
**唯一打开的变量**：多迭代拥堵反馈（`controller.lastIteration`）——基线 config 中 `ReRoute` weight=1.0 与 `travelTimeCalculator`（car / binSize 900 / optimistic+average）在单迭代下被旁路，加迭代即自动生效；`routingRandomness=0.0`、无 timeAllocationMutator / mode choice ⇒ 出发时刻与方式不漂移。

---

## 1. 运行与验证

| 项目 | 结果 |
|---|---|
| 主运行 `cf_it20`（lastIteration=19） | 20 迭代 × 200,000 agents，`lost=0`，每迭代 linkstats 全保留（it.0–it.19），~3h50m |
| 嵌套验证 `cf_it5`（lastIteration=4） | 5 迭代，~48 min |
| **嵌套性验证** | **PASS**：it5 的 it.0–it.4 与 it20 的 it.0–it.4 **逐位一致**（5/5 identical，`nesting_check.json`）→ 同 seed + 确定性 ReRoute 下 lastIteration 确为截断，检查点 {1,5,10,20} 全部由主运行覆盖 |
| **it.0 一致性核对** | **PASS**：it.0 与冻结 6.3.3B **逐位复现**（ratio 0.7441/0.8893/0.8185、r 三窗全同，`it0_vs_frozen_633b_consistency.json`）→ 对照管线无泄漏 |
| 磁盘控制 | 中间迭代不写 events/plans/trips/snapshots（writeIntervals=0），只保留每迭代 linkstats |

## 2. 预注册检查点结果（1 / 5 / 10 / 20 迭代 ↔ it.0 / 4 / 9 / 19）

| 指标 | 1 迭代（=冻结 6.3.3B） | 5 迭代 | 10 迭代 | 20 迭代 |
|---|---|---|---|---|
| 总体 r（07-08 / 08-09） | 0.279 / 0.249 | 0.326 / 0.292 | 0.321 / 0.293 | 0.325 / 0.290 |
| 总体 Sim/Obs（07-08 / 08-09） | 0.744 / 0.889 | 0.770 / 0.852 | 0.774 / 0.854 | 0.773 / 0.863 |
| CATA Sim/Obs（07-08 / 08-09） | 0.584 / 0.739 | 0.649 / 0.743 | 0.653 / 0.767 | 0.651 / 0.780 |
| SLIP_ROAD Sim/Obs（07-08 / 08-09） | 1.594 / 2.033 | 1.754 / 1.993 | 1.737 / 2.032 | 1.718 / 2.075 |
| **CATA/SLIP 比值（07-08 / 08-09）** | **0.366 / 0.363** | 0.370 / 0.373 | 0.376 / 0.378 | **0.379 / 0.376** |
| r_CATA 断面内（07-08 / 08-09） | −0.012 / −0.057 | +0.017 / −0.018 | +0.014 / −0.030 | +0.014 / −0.030 |

逐迭代完整轨迹见 `congestion_feedback_structure_trajectory.csv`（20 迭代 × 3 窗）；轨迹在奇偶迭代间小幅振荡（±0.006 量级，ReRoute 交替使用上一轮 TT 所致），振荡带内 CATA/SLIP 比值全程 **0.363–0.389**。

## 3. 判读（对照预注册判据）

**判据「CATA/SLIP 比值显著偏离 0.366 且 r_CATA 改善」→ 不成立。**

1. **比值只从 0.366 微移到 ~0.377（+3%），远不足以闭合结构缺口**（需要 →1 才算修复快速路/匝道错配）；
2. **CATA 与 SLIP_ROAD 依旧同向移动**（CATA 0.584→0.651 ↑11%，SLIP 1.594→1.718 ↑8%）——拥堵反馈抬升的是**通量水平**，不是**相对分配结构**；
3. **r_CATA 在 20 迭代内始终 ≈0**（−0.06 ~ +0.02 振荡）——快速路断面内的空间排序从未被改善；
4. 总体 r 的小幅改善（0.28→0.32 / 0.25→0.29）属于**全网通量水平效应**，与 7.2.2 中 f 扫描的效应同性质。

**结论（与 7.2.2 并列的第二个否定性实验结论）**：

$$\boxed{\text{拥堵反馈 / 迭代式 ReRoute 也不能解释 CATA↔SLIP\_ROAD 结构错配}}$$

机理自洽：20 迭代 × 每轮全员 ReRoute + 拥堵感知 TT ⇒ 路径选择已**完全重优化**，若错配源于"单迭代自由流最短路"，比值理应显著移动——它没有。**单迭代不是结构性低估的原因**。

## 4. 对 Step 7.3.2 / 下一步的证据指向

已排除的结构杠杆：① capacity factor（7.2.2）；② 拥堵反馈 / 迭代次数（本步）。剩余候选：

- **7.3.2 route-choice 参数**（ReRoute fraction、learning/plan memory、travel-time scoring）：先验已弱——路径已在每轮完全重优化，调 ReRoute fraction / 评分不太可能改变 0.377 这个稳定比值；
- **网络表达审查**（证据更强）：快速路↔匝道**拓扑连通性**（CATA 断面 r≈0 而非单纯低比例，暗示"走错地方"而非"走少比例"）、匝道 speed/lanes 表达、转向限制缺失、`network_cleaned` 中 motorway 连接的入出口结构；
- **需求/对照侧**：crosswalk 已排除粒度疑点，但断面归属与 TrafficFlow 观测点位的**空间对位**仍可在网络审查后再复核一次。

**建议**：7.3.2 之前先做一次轻量的**快速路-匝道连通性专项审计**（零仿真成本，纯 network 拓扑统计），其结果将决定 7.3.2 是否还有必要、或直接转入网络结构修复。λ 继续保持不冻结（0.05 仍只是实验基准）。

## 5. 冻结关系

- 冻结不动：3B.1 / 4 / 5B / 5C.1 / 6.1 / 6.2 / 6.2B / 6.3.2 / 6.3.3A / 6.3.3B / 7.1 / 7.2.1 / 7.2.2；
- **λ 暂不冻结**；`parameters_changed=false`（相对 6.3.3B 基线仅 lastIteration 变化，属实验变量）；
- 下一步：快速路-匝道连通性专项审计（建议）→ 7.3.2 route-choice 参数（视审计结果取舍）。

## 6. 产物清单

```
reports/od_calibration_7_3_1/
├─ iterations_20/ITERS/it.0..19/cf_it20.k.linkstats.txt.gz   # 主运行逐迭代 linkstats
├─ iterations_05/ITERS/it.0..4/cf_it5.k.linkstats.txt.gz     # 嵌套验证运行
├─ congestion_feedback_iterations_summary.csv                # 逐迭代总体指标
├─ congestion_feedback_by_roadcat.csv                        # 逐迭代 RoadCat 分层
├─ congestion_feedback_sections_all_iterations.csv           # 断面 × 迭代明细
├─ congestion_feedback_structure_trajectory.csv              # 结构轨迹（CATA/SLIP 比值 + r_CATA × 3 窗 × 20 迭代）
├─ congestion_feedback_checkpoints.csv                       # 预注册检查点 {1,5,10,20}
├─ nesting_check.json                                        # 嵌套性验证 PASS（5/5 逐位一致）
├─ it0_vs_frozen_633b_consistency.json                       # it.0 与 6.3.3B 逐位一致 PASS
├─ congestion_feedback_definition.json                       # 实验定义（口径 + 判据预注册）
└─ STEP7_3_1_REPORT.md                                       # 本报告
```

脚本：`scripts/od/run_congestion_feedback_7_3_1.py`（`--smoke` / `--gen-only` / `--skip-nesting-check` / `--max-iter`）、`scripts/od/compare_congestion_feedback_7_3_1.py`（import 7.1 冻结靶场模块，口径零漂移）。
