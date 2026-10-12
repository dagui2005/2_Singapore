# E-SB-05 — SB-A5 执行级 events 验证（`writeEventsInterval=19`）

> **一句话**：把 E-SB-04 / E-SB-04B 的「路径重分配」结论从 `PLANS_LEVEL` 补到 **执行级**——
> 在原 SB-A5 完全不变的模型设置下**只**开事件输出（`writeEventsInterval=19`），
> 用新目录 / 新 `runId` 重跑一轮，先证明「开 events 没有改变仿真动力学」，
> 再用 events 重建实际执行路线并与 selected plan 对账、与 v1.0 做执行级配对比较。

- **性质**：`EXPERIMENT ONLY / NOT v1.1`
- **runId**：`SB-A5_EVT19_CHECK`
- **上游**：`E-SB-04`（`PATH_REDISTRIBUTION_SUPPORTED`，plans）｜`E-SB-04B`（`FREESPEED_ROUTE_COUPLING_SUPPORTED`，plans）｜`E-SB-03`（1.0601 归因）
- **协议**：`PROTOCOL_E-SB-05.md`

## 只改了 3 项（其余与原 SB-A5 逐字节相同）

| 配置项 | 值 |
|---|---|
| `controller.outputDirectory` | `…\E-SB-05_exec_level_events\outputs\SB-A5_EVT19_CHECK` |
| `controller.runId` | `SB-A5_EVT19_CHECK` |
| `controller.writeEventsInterval` | `19`（原 `0`） |

由 `esb05_build_config.py` 的「回填 3 项后与源配置逐字节相同」断言保证无其它改动。

## 运行前硬门（16/16 PASS）

源配置哈希未变 · 网络 `sha256=7978681b…` · 人口 `sha256=e96ed83f…`（236,044 未改）·
核心模型指纹逐项相同（seed 4711 / 8 线程 / `flowCapacityFactor=1.0` / `storageCapacityFactor=1.0` /
评课 / routing / qsim / replanning）· 输出目录全新 · 磁盘 ≥ 预估 ×2 · **含负例门禁 G02b**。

## MATSim 语义（源码实证）

`writeEventsInterval=19` 会写 **it.0**（`earlyIteration`）与 **it.19**（`regularWriteEvents`）
两份 events，`dumpDataAtEnd` 再把 it.19 复制成 `<runId>.output_events.xml.gz`（第三份）。
⇒ 预计磁盘 ≈ 3 × 1.72 GB。

## 一致性判据（任务书 §2.1）

- **首要**：it.19 逐链 LinkStats `sha256` 与原 SB-A5 **逐位相同**（含 `HRS8-9avg` 全 154 列）
- 确定性产物 sha256 逐位比较（`legHistogram` / `legdurations` / `output_links` / `output_plans` /
  `output_network` / `vehicles` / `counts` / `scorestats`）
- 观测域复算：it.10–19 cycle-mean → 576 断面 median×`SCALE=2.29897` 的 `Sim/Obs`(08-09) 必须 == **1.0600691**
- 负例：新 run 的 `Sim/Obs` 必须 **≠** v1.0 的 0.9993348

## events 语义（实测）

- `entered link` 事件**带 `vehicle` 不带 `person`** ⇒ 经 `PersonEntersVehicle` 建 person 关联
- selected plan 的 `<route type="links" start_link="X" …>` 内容**以 `start_link` 为首元素**；
  车辆被置于 start_link ⇒ events 不记其 `entered link` ⇒ **`obs == plan[1:]`**
- 尾部未完成车辆**排除**，不进入聚合与对账（否则系统性低估里程）

## 执行级升级判据（任务书 §3）

| ID | 判据 |
|---|---|
| D1 | 执行路线改变率 > 0（并与计划级 66.06% 同量级比较） |
| D2 | 执行级快速路里程份额 SB-A5 > v1.0 |
| D3 | 共享 person ≥ 236,000 |
| D4 | 执行级 Δ 与计划级 Δ **同号且 \|差\| ≤ 2 pp** |
| **D5** | ★**【原始预注册判据·硬门禁】**执行级里程份额 Δ **Top-2 走廊恰为 PIE/TPE** |
| A5 | （**补充分析**，⛔ 非门禁）执行级 PIE 与 TPE 的里程份额 Δ 均为正 |

> **★★§6 更正说明（2026-10-12）**：初稿 `D5` 写为「Top-2 变化走廊**恰为** PIE/TPE」。
> 首轮判定曾把 D5 改写为「PIE 与 TPE 的 Δ 均为正」，并据此报告 **17/17 PASS**。
> **该表述与处置已被撤回**：
> - **无独立通道可核实修订时刻**（Git 未跟踪；`mtime` 只记写入时刻、不记决策时刻；且本轮修正
>   已覆盖脚本 `mtime`）⇒ **不主张「修订先于数据」**，**⛔ 不得表述为「原协议 17/17 PASS」**。
> - `D5` **恢复为原始预注册判据并作为硬门禁**：实测里程份额 Δ 排序 `PIE > MCE > CTE > TPE > AYE`
>   ⇒ Top-2 = `PIE + MCE` ⇒ **D5 = FAIL**，有效门禁 **16/17**。
> - 「PIE 与 TPE 的 Δ 均为正」**降为补充分析 `A5`**（符号同向，成立）。
> - **协议真空**：原判决 1 要求 `D1–D5 全 PASS`、判决 2 仅覆盖 `D1–D4` 部分 FAIL ⇒
>   本轮 `D1–D4 全 PASS + D5 FAIL` **两个分支均未覆盖** ⇒ 并列双读法（见下）。

判决枚举：`EXECUTION_LEVEL_CONFIRMED` / `EXECUTION_LEVEL_PARTIAL` /
`CONSISTENCY_FAILED__PLANS_LEVEL_RETAINED` / `EVENTS_INTEGRITY_FAILED__PLANS_LEVEL_RETAINED` /
`PLAN_EXEC_MISMATCH__PLANS_LEVEL_RETAINED`。

> **★本轮并列双读法**（⛔ 不得只报前者）：
> `verdict = EXECUTION_LEVEL_CONFIRMED`（核心 D1–D4）｜
> `verdict_if_strict_protocol = EXECUTION_LEVEL_PARTIAL`（含原始 D5）。

## 结果（已跑完）

| 项 | 值 |
|---|---|
| 运行 | rc=0 ｜ heap 24g ｜ **125.7 min** ｜ events 3 份（it.0 1.72 GB / it.19 1.68 GB / 根副本 1.68 GB） |
| 运行一致性 | **`CONSISTENT_STRICT`** ｜ it.19 linkstats 容器+内容 sha256 **双逐位相同** ｜ 确定性产物 **79/79** |
| 观测域 | `Sim/Obs(08-09)` 新 run **1.0600691** == 原 SB-A5（±1e-6）｜断面 ΣQ=1,605,179.8215 == 原值 |
| events 完整性 | 10 类事件｜`PersonEntersVehicle`=236,044｜重建执行路线 **236,039**｜未完成排除 **0** |
| 路线对账 | `drop_start_link` **236,039/236,039 = 100%**（两侧一致，与 E-SB-04 抽样 8,000/8,000 独立吻合） |
| **判决** | **`EXECUTION_LEVEL_CONFIRMED`（核心 D1–D4 + A/B/C 全 PASS）** ｜ 协议原始合规 **16/17**（**D5 FAIL**）⇒ 严格读法 `EXECUTION_LEVEL_PARTIAL` |
| 执行路线改变率 | **66.0603%**（vs 计划级 **66.0589%**，几乎逐位吻合） |
| 执行级快速路份额 | **50.9497% → 54.5310%（+3.5813 pp）** ｜ 计划级 +3.5742 pp ｜ 差 **+0.0070 pp** |
| 方法学校验 | 「计划级−执行级」人均里程两侧**同为 35.4 m**（= 人均 `start_link`）⇒ 唯一系统性缺口已定位 |
| 走廊 | PIE +0.8474 pp（使用率 +3.06 pp）｜ TPE +0.2222 pp ｜ **Top-2 = PIE+MCE** ⇒ **原始 D5 FAIL**（TPE 第 4）；PIE/TPE 同向为正仅列为**补充分析 `A5`** |

**产物**：`reports/exec_level_events_E_SB_05/VERDICT_E-SB-05.md`、`exec_level_scorecard.csv`

## 目录

```
E-SB-05_exec_level_events/
  PROTOCOL_E-SB-05.md  README.md
  configs/config_SB-A5_EVT19_CHECK.xml
  outputs/SB-A5_EVT19_CHECK/          ITERS/it.0, it.19（含 events）+ 根产物
  logs/SB-A5_EVT19_CHECK_run.log
  audit/                              门禁 / 清单 / 一致性 / 对账 / _exec_cache
```

## 复现命令

```bash
python scripts/experiments/esb05_build_config.py        # 派生配置 + 白名单断言
python scripts/experiments/esb05_preflight.py           # 运行前硬门
python scripts/experiments/esb05_run.py --run --heap 24g
python scripts/experiments/esb05_consistency_check.py   # 运行一致性
python scripts/experiments/esb05_events_exec_route.py --tag NEW
python scripts/experiments/esb05_events_exec_route.py --tag V10   # 执行级基线
python scripts/experiments/esb05_exec_compare.py        # 对账 + 判决
python scripts/experiments/esb05_verdict_render.py      # 渲染判决书
```

## 红线

⛔ 不调 `SCALE` / 容量 / `freespeed` / λ / 阈值；⛔ 不启动信号灯、交叉口实验；⛔ 不晋升 `v1.1`；
⛔ 不覆盖原 SB-A5 输出；⛔ 不重跑 `SB-A5ind`；`v1.0` 与原 SB-A5 保持不动（只读）。
