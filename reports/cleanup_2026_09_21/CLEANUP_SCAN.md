# MATSim 仿真结果清理 · 只读盘点报告

- 生成时间：2026-09-21
- 扫描根：`D:\Luan\2026-05\2_Singapore`
- **本报告为扫描件：未删除、未移动、未改名任何文件**
- 归档/暂存根（本次新建）：`K:\_sg_matsim_cleanup_2026-09-21\`

> ⚠️ **触发背景：D 盘 477 GB 已 100% 占满、可用 0 字节**（连 5 KB 的报告都写不进 D，故本报告落在 K 盘）。
> 因此本任务的真实约束不是"要不要清"，而是"清哪些才不破坏冻结链"。

---

## 0. 安全前提

| 事实 | 含义 |
|---|---|
| `.gitignore` 第 200–212 行忽略 `/matsim_*_*/outputs/`、`populations/`、`audit/`、`/reports/**/*.gz` | **这些仿真产物不在 git 内 ⇒ 删除不可恢复** |
| D 盘与 K 同机但异卷，K 余 351 GB | 可用「**移到 K 盘**」代替删除 ⇒ 既释放 D 又完全可逆 |
| 回收站位于同卷 | ⚠️ 走回收站**不会释放 D 盘空间**（只是 move），对本次目标无效 |

---

## 1. 空间分布（一层）

| 目录 | 体量 | 说明 |
|---|---:|---|
| **`reports/`** | **49.14 GB** | ★ 真正的大头 |
| `Singapore_OD_MATSim_FinalData` | 8.88 GB | 数据集仓库 |
| `osm` | 8.16 GB | 底图 |
| `Dynamic_2026_03_16` | 7.68 GB | LTA 动态源 |
| `matsim_kw_7_9b1` ★ | 4.06 GB | 冻结链 |
| `matsim_viz_7_8` ★ | 3.81 GB | 冻结链 |
| `Static_ 2026_03` | 2.26 GB | LTA 原始源 |
| `matsim_lambda_7_6g` | 1.99 GB | |
| `matsim_demand_7_6f_1` | 1.98 GB | |
| `matsim_routechoice_7_6d` | 1.34 GB | |
| `matsim_final_7_6h` ★ | 0.67 GB | **v1.0 唯一冻结模型** |
| `matsim`（step6_3 遗留） | 0.02 GB | git 已跟踪 |
| **项目合计** | **91.18 GB** | |

★ = 出现在脚本的 `FROZEN` / `FROZEN_DIRS` 列表内。

---

## 2. 引用面审计方法

对 **172 个 `scripts/**/*.py`** + `reports/**`（md/json/csv/txt）逐一做路径与文件名正则扫描，判定每个产物的"活引用"。

### 2.1 冻结链的活引用（**必须保留**）

| 产物 | 消费者 |
|---|---|
| `matsim_final_7_6h/outputs/W01_rc_min/ITERS/it.19/*.linkstats.txt.gz` | 7.9A-0/C-0/C-1/D-0/D-1/E-0/E-2、7.6H 等 10+ |
| `matsim_final_7_6h/populations/pop_W01/*.xml.gz` | 7.9A-0、7.9D-0 |
| `matsim_final_7_6h/audit/*` | 7.7C-1/D、7.7A |
| `matsim_viz_7_8/.../W01_events.output_events.xml.gz` | **7.7E**、**7.9B-1** |
| `matsim_viz_7_8/.../it.19/*.linkstats.txt.gz` + `configs` + `audit/` | 7.9A-0、7.8 参数演化 |
| `matsim_kw_7_9b1/.../W01_kw.output_events.xml.gz` | 7.9B-1 评价 |
| `matsim_kw_7_9b1/.../it.19/*.linkstats.txt.gz` | 7.9C-1、D-0、D-1、E-0 |
| `matsim_routechoice_7_6d/outputs/R01_rc_min/R01_rc_min.output_plans.xml.gz` | **7.6C、7.6C-1** |

### 2.2 reports/ 下早期 run 的活引用

| 读取方 | 需要什么 | 硬约束 |
|---|---|---|
| `audit_assignment_stability_7_6b.py`（**7.6B**） | `od_calibration_7_4_2/E06`、`od_calibration_7_4_3/D02·D03·D04` 的 **全部 20 迭代** linkstats | ⛔ 不可减迭代 |
| `audit_routechoice_stability_7_6d.py`（**7.6D**） | 同上 + `od_sample_7_5a/S100c`，另读 `ITERS/it.N/legHistogram.txt` | ⛔ 不可减迭代 |
| `evaluate_demand_scale_7_6f_0.py`（**7.6F-0**） | 同上 5 个 run | **硬门 `P5 = 20/20 linkstats`** |
| `audit_parameter_evolution_7_8.py`（**7.8**） | `7_2_2/capacity_factor_1p00`、`7_4_2/E03`、`7_4_3/D02` 的 `*.output_config.xml` | 仅 config |
| `audit_matsim_calibration_7_2.py`（**7.2**） | `matsim_assignment*` 的 `*output_config*` | 仅 config |
| `compare_step6_3.py`（6.3） | `matsim_assignment/lambda_*/ITERS/it.0/*.0.linkstats.txt.gz` | 仅 it.0 |
| `compare_capacity_sweep_7_2_2.py`（7.2.2） | `capacity_factor_*/` 下 **it.0** linkstats | 仅 it.0 |
| `diagnose_route_structure_7_3_2b.py`（7.3.2b） | `matsim_assignment/lambda_0p050/ITERS/it.0/*plans*.xml.gz` | 1 个 plans |
| `diagnose_motorway_loading_7_3_2c.py`（7.3.2c） | `matsim_assignment_6_3_3b/lambda_0p050/ITERS/it.0/*plans*.xml.gz` | 1 个 plans |

---

## 3. ★ 核心发现：`events.xml.gz` 在 `reports/` 下是**零引用**

全量 172 脚本扫描结果：读取 `*.output_events.xml.gz` 的脚本只有 4 个 ——
`analyze_kw_7_9b1.py`、`audit_congestion_plausibility_7_7e.py`（均指向 **kw / viz**）、以及两个 runner 自身。
**没有任何脚本读取 `reports/**/events.xml.gz`。**

| 位置 | 文件数 | 体量 |
|---|---:|---:|
| `reports/**/events.xml.gz` | **28** | **30.61 GB** |
| `reports/**/*plans.xml.gz` | 74 | 8.28 GB |
| 小计 | 102 | 38.89 GB |

### 3.1 附带发现：run 级 events 与 `ITERS/it.0` events **互为副本**

| 例 | run 级 | it.0 级 |
|---|---|---|
| `od_calibration_7_2_2/capacity_factor_0p50` | `cap_f_0p50.output_events.xml.gz` 1.44 GB | `ITERS/it.0/cap_f_0p50.0.events.xml.gz` 1.44 GB |
| `matsim_assignment_6_3_3b/lambda_0p050` | 1.40 GB | 1.40 GB |

⇒ 这两类文件在 6.3 / 7.2.2 / 6.3.3b 三组里都是**同一份内容写两遍**，占 30.61 GB 的一半以上。

### 3.2 `matsim_viz_7_8` 与 `matsim_final_7_6h` 的重复（另一发现）

- 20/20 迭代的 `linkstats.txt.gz` **MD5 逐位相同** ⇒ 430.2 MB 纯冗余
- run 级 14 个根文件中 13 个逐位相同（`output_plans.xml.gz` 205.8 MB 等）⇒ 234.3 MB
- run 级 `output_events.xml.gz` 与 `ITERS/it.19/*.events.xml.gz` **MD5 逐位相同** ⇒ 1.58 GB
- `matsim_kw_7_9b1` 的 run 级 events 与 it.19 events 亦 **MD5 逐位相同** ⇒ 1.66 GB

⚠️ 但这些路径全部位于 `FROZEN` 目录内；用硬链接折叠会**改变 mtime**（sha256 不变），可能触发对已落盘 manifest 的复核告警 ⇒ 列为"需你单独授权"。

---

## 4. 分级处置建议

### T0 — 零风险，纯垃圾（170 MB）

| 路径 | 体量 |
|---|---:|
| `matsim_routechoice_7_6d/outputs/_smoke_R01_rc_min/` | 84.8 MB |
| `matsim_routechoice_7_6d/outputs/_smoke_S100k_rc_min/` | 85.2 MB |

冒烟测试残留（3 迭代），零引用。

### T1 — ★ 强烈推荐：`reports/**/events.xml.gz`（**30.61 GB**）

- **零脚本引用**（172 脚本全扫确认）
- 全部属早期阶段（6.3 / 6.3.3b / 7.2.2），已被 v1.0（7.8）取代
- 其中过半是 run 级与 it.0 的互相重复
- **不触碰任何** linkstats / config / plans / 冻结目录

### T2 — 需你确认：早期 run 的 `*plans.xml.gz`（**≈ 7.9 GB**）

`reports/**/*plans.xml.gz` 共 8.28 GB，须**保护 2 个例外**（下表），其余可弃：

| 必须保留的 plans | 消费者 |
|---|---|
| `matsim_assignment/lambda_0p050/ITERS/it.0/step6_3_lambda_0p050.0.plans.xml.gz` | 7.3.2b |
| `matsim_assignment_6_3_3b/lambda_0p050/ITERS/it.0/step6_3_3b_lambda_0p050.0.plans.xml.gz` | 7.3.2c |

### T3 — 需你确认：`matsim*` 中零引用的 outputs（**3.98 GB**）

| 路径 | 体量 | 引用 |
|---|---:|---|
| `matsim_demand_7_6f_1/outputs/`（F05/F15/F25） | 1,985.6 MB | **0** |
| `matsim_lambda_7_6g/outputs/`（L05/L75/L10） | 1,997.8 MB | **0** |

两实验结论已固化；`audit/`（17 MB/个，7.7D 闭环门读）**保留不动**。

### T4 — 不建议：冻结证据链（**8.72 GB**）

`matsim_final_7_6h/outputs` 665.7 MB、`matsim_viz_7_8/outputs` 3,896.8 MB、`matsim_kw_7_9b1/outputs` 4,156.8 MB。动了会破坏 v1.0 可复现性与 5 个以上的 `FROZEN` 门。

### T5 — 需单独授权：副本去重（3.98 GB，改 mtime）

见 §3.2。

---

## 5. 汇总

| 方案 | 回收 | 风险 |
|---|---:|---|
| T0 | 0.17 GB | 无 |
| **T0 + T1** | **30.78 GB** | **低（零引用，不动任何被读文件）** |
| T0 + T1 + T2 + T3 | 42.66 GB | 中（2 个 plans 例外须精确保护） |
| + T4 | 51.4 GB | 高（破坏 v1.0 可复现） |
| + T5 | 55.4 GB | 中高（冻结目录 mtime 变动） |

### 推荐路线

**T0 + T1，以「移到 K 盘」方式执行** ——
D 盘立即释放 **≈ 30.8 GB**，K 盘保留完整副本，随时可原路还原，且不动任何被脚本读取的文件。

---

## 6. 执行纪律（若获批）

1. **先建清单**：逐文件记录 `相对路径 + size + mtime`，落盘为 `MANIFEST_before.csv`
2. **移到 K 盘**（`K:\_sg_matsim_cleanup_2026-09-21\reports_events\<原相对路径>`），不用永久删除
3. **小批量**：每批 ≤ 10 个文件，逐批校验大小一致后继续
4. **全程不碰**：`matsim_final_7_6h/`、`matsim_viz_7_8/`、`matsim_kw_7_9b1/`、任何 `linkstats.txt.gz`、任何 `output_config*.xml`
5. **清理后复核**：重跑 `_apply_*` 之外不受影响的只读门（抽查 7.6B / 7.6F-0 的输入定位函数），确认 20/20 linkstats 与 config 定位仍 OK
