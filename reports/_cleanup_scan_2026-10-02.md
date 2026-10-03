# MATSim 仿真结果清理 — 只读扫描报告（2026-10-02）

> **本轮为只读扫描。未经确认不移动/删除任何文件。**
> 引擎：`scripts/_housekeeping/cleanup_whitelist_2026-10-02.py`（默认只建清单）
> 清单：`reports/_cleanup_2026-10-02/CLEANUP_MANIFEST.csv` · 统计：`CLEANUP_SUMMARY.json`

## 0. 磁盘现状

| 盘 | 容量 | 已用 | 可用 | 使用率 |
|---|---:|---:|---:|---:|
| C: | 476 G | 411 G | 66 G | 87% |
| **D:** | 477 G | 454 G | **23 G** | **96%** |
| K: | 440 G | 135 G | 306 G | 31% |

- 回收站 `D:\$RECYCLE.BIN` = **49 M**（近乎空）。
- ⚠️ 本环境删除会**先进回收站**，不清空则 D 盘可用空间**不会变**。

## 1. MATSim 产物分布（>50 M 文件）

| 文件 | 体积 | 归属 |
|---|---:|---|
| `matsim_sampling_capacity_7_9a1/…/A1_capf0p435.output_events.xml.gz` | 1.9 G | 7.9A-1 原始轨迹 |
| `experiments/E-CAP-01…/ITERS/it.19/E-CAP-01.19.events.xml.gz` | 1.8 G | **根层副本（逐位重复）** |
| `experiments/E-CAP-01…/E-CAP-01.output_events.xml.gz` | 1.8 G | E-CAP-01 根层轨迹（保留） |
| `matsim_kw_7_9b1/…/W01_kw.output_events.xml.gz` | 1.7 G | 7.9B1 原始轨迹 |
| `experiments/E-CAP-01…/ITERS/it.0/E-CAP-01.0.events.xml.gz` | 1.7 G | **中间迭代（非收敛窗）** |
| `matsim_viz_7_8/…/W01_events.output_events.xml.gz` | 1.6 G | **VIA 回放源（硬豁免）** |
| 各 run 的 `output_plans.xml.gz` | 0.10–0.43 G | 末迭代计划 |
| `reports/matsim_assignment*/…/*events|plans*.xml.gz` | 0.10–0.11 G | 6.3 分配（含重复对） |

## 2. 关键结构性发现

1. **`ITERS/it.19` 不含 events/plans**（只有 linkstats 22 M + legHistogram + legdurations）。
   ⇒ 根层 events/plans **不是** it.19 的副本（除 E-CAP-01 的 events 恰好重复）。
2. **E-CAP-01 根层 events ≡ `it.19` events**：同为 `1,925,806,193 B`，sha256 `4ee16aa3…` ⇒ 真重复。
3. **`reports/matsim_assignment*` 的 `experienced_plans`**：根层 ≡ `it.0` 副本（sha256 同）⇒ 真重复；
   但 `plans` 根层 ≠ `it.0`（迭代 0 vs 末迭代，内容不同）⇒ **非重复，跳过**。
4. **A1 events ≠ E-CAP-01 events**（`4fbf6869…` vs `4ee16aa3…`；events 头部内嵌 `runId`）
   ⇒ 即便模型等价也**非逐位重复**，只能按「已固化实验轨迹」处理。
5. `matsim_demand_7_6f_1` / `matsim_lambda_7_6g` 无 >50 M 文件（仅 links/network ≈ 14 M/run）。

## 3. ⛔ 硬约束（本轮清理不可逾越）

| 约束 | 依据 |
|---|---|
| **`matsim_final_7_6h/` 整树豁免** | v1.0 冻结运行（配置 mtime Sep 18 21:09） |
| **`matsim_viz_7_8/` 整树豁免** | VIA 回放源（用户在用） |
| **任何 `it.10`–`it.19` 的 `*.linkstats.txt.gz` 永不删** | 评价器主口径 = 收敛窗 it.10–19 逐链路周期均值；护栏缓存键含 `it.10–19 linkstats sha16` |
| **`*.legHistogram.txt` 永不删** | 同属评价器输入 |
| 报告目录 `final_model_7_8` / `corridor_scale_audit_7_9i` / `via_congestion_diagnosis_7_8` / `sampling_capacity_7_9a1` | 冻结证据，不进删除集 |

> 已核：`ecap01_postrun.py`、`ecap01_demo_figs.py`、`ecap01_static_figs.py` **均不读 events**；
> 护栏 `guardrail_key()` 只取 `it.10–19 linkstats` ⇒ 删除 events **不破坏**任何评价链。

## 4. 白名单（共 12 项 / 8.313 GB）

### A 类 — 逐位重复副本（sha256 全量一致，删一份）· 3 项 / 1.991 GB
| 删除 | 体积 | 保留孪生 |
|---|---:|---|
| `experiments/E-CAP-01…/ITERS/it.19/E-CAP-01.19.events.xml.gz` | 1.793 G | 根层 `E-CAP-01.output_events.xml.gz` |
| `reports/matsim_assignment/lambda_0p050/ITERS/it.0/….0.experienced_plans.xml.gz` | 0.099 G | 根层同名 |
| `reports/matsim_assignment_6_3_3b/lambda_0p050/ITERS/it.0/….0.experienced_plans.xml.gz` | 0.100 G | 根层同名 |

### B 类 — 中间迭代事件（非收敛窗）· 1 项 / 1.699 GB
| 删除 | 体积 | 说明 |
|---|---:|---|
| `experiments/E-CAP-01…/ITERS/it.0/E-CAP-01.0.events.xml.gz` | 1.699 G | 迭代 0 轨迹，评价/VIA 均不用 |

### C 类 — 已固化实验的原始轨迹（保留 linkstats 与 reports）· 8 项 / 4.623 GB
| 删除 | 体积 | 说明 |
|---|---:|---|
| `matsim_kw_7_9b1/…/W01_kw.output_events.xml.gz` | 1.656 G | 7.9B1（已出报告） |
| `matsim_kw_7_9b1/…/W01_kw.output_plans.xml.gz` | 0.287 G | 同上 |
| `matsim_sampling_capacity_7_9a1/…/A1_capf0p435.output_events.xml.gz` | 1.800 G | 7.9A-1（判决已冻结） |
| `matsim_sampling_capacity_7_9a1/…/A1_capf0p435.output_plans.xml.gz` | 0.403 G | 同上 |
| `matsim_routechoice_7_6d/…/R01_rc_min.output_plans.xml.gz` | 0.177 G | 7.6D（已出报告） |
| `matsim_routechoice_7_6d/…/S100k_rc_min.output_plans.xml.gz` | 0.106 G | 同上 |
| `reports/matsim_assignment/…/step6_3_lambda_0p050.output_plans.xml.gz` | 0.096 G | 6.3 分配（已出报告） |
| `reports/matsim_assignment_6_3_3b/…/step6_3_3b_lambda_0p050.output_plans.xml.gz` | 0.098 G | 同上 |

## 5. 处理方式选项

| 方案 | 内容 | D 盘即时释放 | 可恢复性 |
|---|---|---:|---|
| **A+B（零风险）** | 只删已证重复副本 + E-CAP-01 中间迭代事件 | ≈ 3.69 G | 重复项有孪生；中间事件无需 |
| **A+B+C 归档** | C 类 **移动**到 `K:\_sg_matsim_cleanup_2026-10-02\`（保相对路径） | ≈ 8.31 G | **完全可恢复**（K 盘） |
| **A+B+C 删除** | C 类直接删除（进 D 回收站） | ≈ 8.31 G（需清空回收站） | 不可恢复 |

> ⛔ 无论选哪项：**不动** v1.0 / VIA 源 / `it.10–19` linkstats / 任何报告表格；
> ⛔ 与已 `CLOSED` 的 O3-R1 及 E-CAP-01 展示包**严格隔离**。

## 6. 复核方式

```
python scripts/_housekeeping/cleanup_whitelist_2026-10-02.py            # 重建清单（只读）
python scripts/_housekeeping/cleanup_whitelist_2026-10-02.py --verify    # 冻结豁免自检
```
