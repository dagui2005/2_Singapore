# MATSim 仿真结果清理 —— 扫描报告（**只读，未删任何文件**）

> 生成时间：2026-10-01 21:12 · 扫描脚本：只读遍历（`os.walk` + `getsize`）
> **状态：`SCAN_ONLY`** —— 本报告**不移动、不重命名、不删除**任何文件。
> 待用户逐类确认后才执行。

## 0. 磁盘现状

| 盘 | 总量 | 已用 | 可用 | 使用率 |
|---|---|---|---|---|
| `D:` | 477 GB | 437 GB | **41 GB** | **92%** |
| `K:` | 440 GB | 130 GB | **311 GB** | 30% |

既有归档约定：`K:\_sg_matsim_cleanup_2026-09-21\{sg_move,sg_move2,sg_move3}_2026-09-21\`（共 **41.9 GB**）。
⇒ **K: 是既定归档目标，空间充足。**

## 1. 项目顶层占用（Top 15）

| 目录 | 占用 |
|---|---|
| `reports/` | **9.7 G** |
| `Singapore_OD_MATSim_FinalData/` | 8.9 G |
| `osm/` | 8.2 G |
| `Dynamic_2026_03_16/` | 7.8 G |
| `matsim_sampling_capacity_7_9a1/` | **4.5 G** |
| `matsim_kw_7_9b1/` | **4.1 G** |
| `matsim_viz_7_8/` | **3.9 G** |
| `Static_ 2026_03/` | 2.3 G |
| `matsim_lambda_7_6g/` | **1.4 G** |
| `matsim_demand_7_6f_1/` | **1.4 G** |
| `matsim_routechoice_7_6d/` | **1.2 G** |
| `matsim_final_7_6h/` | 684 M（**冻结，勿动**） |
| `tools/` | 658 M |
| `scripts/` | 38 M |
| `matsim/` | 21 M |

## 2. 各运行目录的内部结构（关键分解）

| 运行目录 | 总计 | `it.19` | `it.0–it.18`（19 个） | 根层 |
|---|---|---|---|---|
| `matsim_sampling_capacity_7_9a1`（A1） | 4.47 G | **1.82 G** | 0.42 G | **2.23 G** |
| `matsim_kw_7_9b1`（KW） | 4.06 G | **1.68 G** | 0.42 G | **1.97 G** |
| `matsim_viz_7_8`（VIA） | 3.81 G | **1.60 G** | 0.41 G | **1.81 G** |
| `matsim_demand_7_6f_1`（F05/F15/F25） | 1.34 G | 0.06 G | **1.23 G** | 0.08 G |
| `matsim_lambda_7_6g`（L05/L10/L75） | 1.34 G | 0.06 G | **1.23 G** | 0.08 G |
| `matsim_routechoice_7_6d`（R01/S100k） | 1.17 G | 0.04 G | **0.81 G** | 0.34 G |
| `matsim_final_7_6h`（W01 = **v1.0 冻结**） | 0.67 G | 0.02 G | **0.40 G** | 0.24 G |

### 2.1 ★ 已核验：`根层 events` 与 `ITERS/it.19/events` 是**同一份字节**

| 运行 | 根层 events | it.19 events | 大小相同 | 头/尾 8 MB 哈希相同 |
|---|---|---|---|---|
| KW | 1.656 GB | 1.656 GB | ✅ | ✅ `1778049358:6ed69d48…` |
| A1 | 1.800 GB | 1.800 GB | ✅ | ✅ `1932894470:28a4e9fe…` |
| VIA | 1.578 GB | 1.578 GB | ✅ | ✅ `1694011331:69b4ecd8…` |

> ⚠️ 说明：MATSim 语义为「根目录 = 最后一次写入（= it.19）+ `ITERS/it.19/` 各一份」，
> 故**每份运行目录内恒定冗余 1 份 events**。VIA 的 `README.md` 亦已记载该冗余 1.69 GB。

## 3. 可清理清单（分级，**均未执行**）

### 【A 类】字节重复的 events —— **最高性价比、零信息损失**

| # | 路径（**拟删除**） | 释放 |
|---|---|---|
| A1 | `matsim_kw_7_9b1\outputs\W01_kw\ITERS\it.19\W01_kw.19.events.xml.gz` | 1.656 G |
| A2 | `matsim_sampling_capacity_7_9a1\outputs\A1_capf0p435\ITERS\it.19\A1_capf0p435.19.events.xml.gz` | 1.800 G |
| A3 | `matsim_viz_7_8\outputs\W01_events\ITERS\it.19\W01_events.19.events.xml.gz` | 1.578 G |
| | **小计** | **≈ 5.03 G** |

保留根层那份（VIA `README.md` 明确「默认用根目录那份」）。若整目录要归档，则整目录移走即可，不必先删。

### 【B 类】中间迭代 `ITERS/it.0–it.18`（未收敛路线的中间态）

| # | 路径 | 释放 |
|---|---|---|
| B1 | `matsim_demand_7_6f_1\outputs\*\ITERS\it.{0..18}\` | ≈ 1.23 G |
| B2 | `matsim_lambda_7_6g\outputs\*\ITERS\it.{0..18}\` | ≈ 1.23 G |
| B3 | `matsim_routechoice_7_6d\outputs\*\ITERS\it.{0..18}\` | ≈ 0.81 G |
| B4 | `matsim_kw_7_9b1\outputs\W01_kw\ITERS\it.{0..18}\` | ≈ 0.42 G |
| B5 | `matsim_sampling_capacity_7_9a1\outputs\A1_capf0p435\ITERS\it.{0..18}\` | ≈ 0.42 G |
| B6 | `matsim_viz_7_8\outputs\W01_events\ITERS\it.{0..18}\` | ≈ 0.41 G |
| | **小计** | **≈ 4.52 G** |

> ⚠️ 依据：本项目**全部评价口径只取 `it.19`**（canonical `section_scale_v10.csv`、`Sim/Obs`、7.9 各轮）⇒ `it.0–18` 是中间态，**不承载判决**。
> ⛔ **但 `matsim_final_7_6h\outputs\W01_rc_min\ITERS\it.{0..18}\`（0.40 G）属 v1.0 冻结运行目录，本报告不建议动**，需你单独裁定。

### 【C 类】`reports/` 下实验目录内的 `ITERS/`（同样的中间态）

| 目录 | 占用 | 大头 |
|---|---|---|
| `reports/od_calibration_7_4_2/` | 2.3 G | 各 `E0x_*/ITERS/`（单个 451 M / 480 M） |
| `reports/od_calibration_7_4_3/` | 1.4 G | 各 `D0x_*/ITERS/` |
| `reports/od_sample_7_5a/` | 904 M | `S100*/ITERS/` |
| `reports/matsim_assignment_6_3_3b/` | 693 M | 迭代 dump |
| `reports/od_calibration_7_3_1/` | 599 M | `iterations_20/` 459 M + `iterations_05/` 135 M |
| `reports/od_sample_7_5b/` | 461 M | `S100r*/ITERS/` |
| `reports/_r1r1_preflight_neg{,_r2}/` | 154 M | 负例运行 |
| `reports/_r1r1_neg{,_r2}/` | 90 M | 负例运行 |
| | **≈ 6.5–7 G** | |

> ⚠️ 本类**判决性产物在小文件里**（`.md`/`.json`/`.csv`），`ITERS/` 是过程 dump。
> ⛔ **但 `reports/corridor_scale_audit_7_9i/`、`reports/final_model_7_8/`、`reports/via_congestion_diagnosis_7_8/`、`reports/sampling_capacity_7_9a1/` 等当前主线/冻结相关目录必须整目录保留。**

## 4. ⛔ 必须保留（MUST KEEP）

| 路径 | 理由 |
|---|---|
| `matsim_final_7_6h/`（含 `outputs/W01_rc_min/`） | **v1.0 冻结运行**，`FINAL_MODEL_MANIFEST.json` 14 件只读输入 |
| `matsim_viz_7_8/outputs/W01_events/`（网络 + **一份** events） | **你正在 VIA 里看的最终效果** |
| `reports/final_model_7_8/` | 冻结 manifest |
| `reports/corridor_scale_audit_7_9i/` | O3-R1 canonical（`section_scale_v10.csv` 等） |
| `reports/via_congestion_diagnosis_7_8/` | VIA 诊断 + `via_link_attributes_HRS8-9.tsv` |
| `reports/sampling_capacity_7_9a1/` | 7.9A-1 正式报告与产物 |
| `reports/matsim_assignment/*.csv`（3×76 M） | λ 三档 sim linkstats，**小体积高价值** |
| `Singapore_OD_MATSim_FinalData/`、`osm/`、`Static_ 2026_03/`、`Dynamic_2026_03_16/` | 原始数据，**不在本轮范围** |
| `matsim/*`（21 M） | step6_3 |

## 5. 汇总

| 类 | 释放 | 风险 | 可否回滚 |
|---|---|---|---|
| **A** 重复 events | ≈ **5.03 G** | 极低（字节相同，另存一份） | 可重跑生成 |
| **B** 中间迭代（非冻结目录） | ≈ **4.52 G** | 低（评价口径只取 it.19） | 不可（需重跑） |
| **C** `reports/*/ITERS` | ≈ **6.5–7 G** | 中（需逐目录确认判决产物已在小文件中） | 不可 |
| | **合计 ≈ 16 G** | | |

> 执行后 `D:` 可用空间预计从 **41 GB → ≈ 57 GB**。

## 6. 执行方式（待你选定）

- **方案 1（推荐）**：**先 A 类**（零风险，5.03 G），验证后再议 B/C。
- **方案 2**：A + B（≈ 9.5 G），全在 `matsim_*` 目录内，不碰 `reports/`。
- **方案 3**：A + B + C 全做（≈ 16 G），需逐目录白名单确认。
- **痕迹保留**：删除前对每项生成 `sha256 + size` 清单并落盘
  `reports/_cleanup_2026-10-01/CLEANUP_MANIFEST.csv`，可追溯"删了什么"。
- **归档 vs 删除**：C 类建议**移动到** `K:\_sg_matsim_cleanup_2026-10-01\`（沿用既定约定），A/B 类可直接删除。

## 7. ⚠️ 风险声明

- 本报告**未执行任何写操作**。
- ⛔ 清理属**仓库卫生**，与已 `CLOSED` 的 O3-R1 科学闭环**严格隔离**（与 `#327` 同一纪律）。
- ⛔ 不得因清理而修改/删除任何**冻结件**（v1.0 / crosswalk / `TrafficFlow` 原始值 / 评价器阈值 / canonical CSV）。
- ⛔ 删除不可回滚（A 类可由重跑再生，B/C 类需重跑仿真）。
- 建议：**B/C 类优先"移动归档"而非"删除"**，K: 尚有 311 GB。
