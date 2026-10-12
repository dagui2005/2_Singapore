# PROTOCOL — E-SB-05：SB-A5 执行级 events 验证（writeEventsInterval=19）

> 实验 ID：`E-SB-05_exec_level_events`
> runId：`SB-A5_EVT19_CHECK`
> 性质：**EXPERIMENT ONLY / NOT v1.1**。只读冻结件，不改任何模型设置（除白名单 3 项）。
> 上游：`E-SB-04`（`PATH_REDISTRIBUTION_SUPPORTED`，plans 级）、`E-SB-04B`（`FREESPEED_ROUTE_COUPLING_SUPPORTED`，plans 级）、`E-SB-03`（1.0601 归因）
> 建立：2026-10-11

---

## §0 问题与证据边界

**问题**：E-SB-04 / E-SB-04B 已证明「改 `freespeed` ⇒ 计划路线向快速路倾斜，且与观测域流量增量在走廊层面同序」，
但**证据等级只有 `PLANS_LEVEL`**：SB-A5 无 events，**没有直接证明其执行路线也发生了同样变化**。
本轮唯一目标：**补执行级证据**，不是调参。

**证据边界（不得越过）**
| 项 | 本轮是否可得 |
|---|---|
| v1.0 的 plans↔events 保真（E-SB-04 抽样 8,000 人 = 100%，`drop_start_link` 语义） | 已有，作参考 |
| SB-A5 的**计划**路线变化率 66.06% / motorway 份额 44.56%→47.25% | 已有（E-SB-04），plans 级 |
| SB-A5 的**执行**路线（events 重建） | **本轮首次获得** |
| v1.0 的**执行**路线（`W01_events` events，同 lastIteration=19、同 population） | 已有，本轮同时解析作配对基线 |

⛔ 与 `O3-R1`（对象重定义）分列；⛔ 不重解释 E-SB-03 的 1.0601 归因；⛔ 不产生 v1.1。

---

## §1 输入前提与运行约束

### §1.1 白名单（只允许改这 3 项）
| 配置项 | 值 |
|---|---|
| `controller.outputDirectory` | `…\experiments\E-SB-05_exec_level_events\outputs\SB-A5_EVT19_CHECK` |
| `controller.runId` | `SB-A5_EVT19_CHECK` |
| `controller.writeEventsInterval` | `19` |

其余**全部**与原 SB-A5 逐字节相同（由 `esb05_build_config.py` 的「回填 3 项后与源配置逐字节相同」断言保证）。

### §1.2 冻结输入
| 输入 | sha256 |
|---|---|
| 原 SB-A5 配置 `config_SB-A5.xml` | `d560bd89c27068c12b5ebbe82255f3e90a99c1b9a314a5f9861f5885e2a2c088` |
| 网络 `network_SB-A5.xml.gz` | `7978681b2a4ab54d1c14890943bf37012d51a003dd14c10dcfd447776eca6dab` |
| 人口 `population_lambda_0p075.xml.gz` | `e96ed83ff59c0f5ecb50c9d9ff2d42a4b4bdbebf2bbfe81a1e0604fb94921fbd` |
| 原 SB-A5 it.19 linkstats.gz（一致性基准） | `ddc879a07dfedb429367e90b8f880afc6ee630886d1d0bfc1129297bd43f9d3e` |

### §1.3 MATSim `writeEventsInterval` 语义（**源码实证，非推断**）
`ControllerConfigGroup`：`"iterationNumber % writeEventsInterval == 0 defines in which iterations events are written"`。
`EventsHandlingImpl.notifyBeforeMobsim`：
```java
final boolean writingEventsAtAll = this.writeEventsInterval > 0;
final boolean regularWriteEvents = writingEventsAtAll && (iteration > 0 && iteration % writeEventsInterval == 0);
final boolean earlyIteration   = iteration <= writeMoreUntilIteration;   // 默认 0
final boolean lastIteration    = event.isLastIteration();
if (writingEventsAtAll && (regularWriteEvents || earlyIteration || lastIteration)) { …写 events… }
```
⇒ `writeEventsInterval=19` 会写 **it.0（earlyIteration）与 it.19（regular+last）两份**；
`DumpDataAtEndImpl` 再把 it.19 的 events `copyFile` 成 `<runId>.output_events.xml.gz`（第三份副本）。
⇒ **预计磁盘占用 ≈ 3 × 1.95 GB = 5.85 GB**。

### §1.4 事件记录语义（**实测，非推断**）
`entered link` 事件**带 `vehicle` 不带 `person`** ⇒ 必须经 `PersonEntersVehicle` 建 `(person, vehicle)` 关联。
selected plan 的 `<route type="links" start_link="X" …>` 内容**以 `start_link` 为首元素**；
车辆被置于 start_link ⇒ events **不记其 `entered link`** ⇒ `obs == plan_route[1:]`。

---

## §2 运行前硬门（`esb05_preflight.py`）

| ID | 判据 |
|---|---|
| G00 | 源配置 / 派生配置 / 源输出目录均存在 |
| G01 | 原 SB-A5 配置 sha256 == 冻结值（未被改动） |
| G02 | 派生配置参数 diff == 白名单 3 项 |
| **G02b** | **负例：`writeEventsInterval` 未改时该门禁必须 FAIL（非恒真）** |
| G03 | `writeEventsInterval == 19` |
| G04 | `runId == SB-A5_EVT19_CHECK` 且 ≠ 原 SB-A5 |
| G05 | `outputDirectory` 在 E-SB-05 内、不与原 SB-A5 / v1.0 输出重叠 |
| G06 | 输出目录尚不存在或为空（绝不覆盖原 SB-A5 输出） |
| G07/G07b | 网络 sha256 / 内容 sha16 == 原 SB-A5 所用 |
| G08 | 人口 sha256 == 原 SB-A5 所用（236,044 未改） |
| G09 | 核心模型指纹逐项相同（seed / 线程 / `flowCapacityFactor` / `storageCapacityFactor` / 评课 / routing / qsim / replanning） |
| G10 | 磁盘余量 ≥ 预估需求 × 2 安全系数 |
| G11 | `eventsFileFormat==xml` 且 `compressionType==gzip` |
| G12 | MATSim 运行时（本地 JDK25 + `matsim-2026.0.jar` + libs）可用 |
| G13 | 原 SB-A5 it.19 linkstats sha256 == 冻结参照（一致性基准在册） |

---

## §3 运行一致性判据与容差（`esb05_consistency_check.py`）

**原则**：写 events 只是「挂一个输出 handler」，不应改变仿真动力学。
若出现超出容差的差异，**先查原因，不得直接用新 events 推断原 SB-A5 的执行路径**。

| 层 | 判据 | 容差 |
|---|---|---|
| L1 | 全部确定性产物（linkstats / legHistogram / legdurations / output_links / output_plans / output_network / vehicles / counts / scorestats）sha256 逐位相同 | **严格**（首要为 it.19 linkstats） |
| L2 | 若 L1 不同：逐链 154 列数值差 `max|Δ|` | `T3` `max|Δ|==0` → `PASS_EQUIVALENT`；`T4` `max 相对差 < 1e-9` → `PASS_TOLERATED`；否则 `FAIL` |
| L3 | it.10–19 cycle-mean 复算：576 断面 median×`SCALE` 的 `Sim/Obs`(08-09) == 1.0600691 | ±1e-6 |
| L3 | 观测域总量：匹配边 ΣQ(raw) / 断面 ΣQ(scaled) == 原 SB-A5 | ±1e-9 相对 |

排除项（外观，不判一致性）：`*.output_config*.xml`（含 runId/路径）、`*.logfile*.log`、`*.stopwatch.csv`（墙钟）、`tmp/`。

**负例（分辨力）**：新 run 的 `Sim/Obs` 必须 **≠** v1.0 的 0.9993348（证明检查能区分臂）。

**总判决**：
- `CONSISTENT_STRICT`：L1 全同（含 it.19 linkstats sha256 相同）
- `CONSISTENT_PASS_EQUIVALENT` / `CONSISTENT_PASS_TOLERATED`
- `INCONSISTENT`：⇒ **保留 `PLANS_LEVEL`**，追因后再议。

---

## §4 events 完整性判据（`esb05_events_exec_route.py`）

| ID | 判据 |
|---|---|
| E01 | events 文件可完整解压 + 行数为正 + 首行 `<?xml` / 第二行 `<events version="1.0">` / 末行 `</events>` |
| E02 | 事件类型集合与 v1.0 同构（`entered link` / `left link` / `actend` / `departure` / `PersonEntersVehicle` / `vehicle enters traffic` / `arrival` / `actstart` / `PersonLeavesVehicle` / `vehicle leaves traffic`） |
| E03 | `PersonEntersVehicle` 能建立 `(person, vehicle)` 关联；关联到的 person 数 == 236,044（±0） |
| E04 | 每人（selected plan）恰好 1 条 car leg；`n_legs` 与 `departure` 事件数一致 |
| E05 | 重建出的执行有向 link 序列非空；`n_links ≥ 1` |
| E06 | 所有 `entered link` 的 link 均能在权威网络中找到（未映射数 == 0） |

## §5 路线对账判据

| ID | 判据 |
|---|---|
| R01 | 逐人实际执行序列 vs selected plan：`obs == plan[1:]`（`drop_start_link`）占比 ≥ 99% |
| R02 | `drop_start_link` 是**优势语义**（其占比严格高于 `direct` 与 `drop_last_link`） |
| R03 | 该语义与 E-SB-04 对 v1.0 的独立抽样结果一致（8,000/8,000 = 100%） |

## §6 执行级升级判据（**任务书 §3 的核心**）

在同一 population（236,044）、同一迭代（it.19）下，配对比较
`v1.0（W01_events）` 与 `SB-A5_EVT19_CHECK` 的**实际执行路线**：

| ID | 判据 | 门槛 |
|---|---|---|
| D1 | **执行路线改变率**（逐人 `exec_hash` 不等占比）> 0 | 严格 > 0，并与计划级 66.06% 同量级比较 |
| D2 | **执行路线快速路里程份额**（`motorway + motorway_link`）在 SB-A5 侧 **高于** v1.0 侧 | Δ > 0 |
| D3 | 共享人集合（两 run 都有执行路线的 person）≥ 236,000 | ≥ 236,000 |
| D4 | **执行级 Δ 与计划级 Δ 同号同量级**（Δ 快速路份额），判定升级 | 同号且 \|执行级 − 计划级\| ≤ 2 pp |
| **D5** | ★**【原始预注册判据·硬门禁】**执行级里程份额 Δ **Top-2 走廊恰为 PIE/TPE** | Top-2 == {PIE, TPE} |
| A5 | （**补充分析**，⛔ 非门禁、不进判决）执行级 PIE 与 TPE 的里程份额 Δ 均为正 | 两者均 > 0 |
| I1 | （参考，不进判决）执行级里程份额 Δ Top-2 走廊 合计 | 只报告 |

> **§6 修订与处置说明（★2026-10-12 更正；撤回原「执行前登记」表述）**
>
> E-SB-05 初稿的 `D5` 写作「Top-2 变化走廊 **恰为** PIE/TPE」。首轮判定曾把 D5 改写为
> 「PIE 与 TPE 的里程份额 Δ 均为正」，并据此报告 **17/17 PASS**。
>
> **该表述与处置已被撤回**，理由：
> 1. **无独立通道可核实修订时刻**。Git 历史不可用（`esb05_*` 从未被跟踪）；文件 `mtime` 只记录
>    **写入时刻**、不记录**决策时刻**；且本轮为恢复 D5 而编辑脚本后，脚本层 `mtime` **已被覆盖**
>    （观察者破坏性）。详见 `audit/esb05_d5_timeline_audit.json`。
> 2. 预注册判据的意义在于**不可事后改写**。在无法证明修订先于数据时，**按最保守口径处置**。
>
> **正式处置**：
> - `D5` **恢复为原始预注册判据**（`Top-2 == {PIE,TPE}`）并作为**硬门禁**；本轮实测
>   `Top-2 = [PIE, MCE]` ⇒ **D5 = FAIL**。
> - 「PIE 与 TPE 的 Δ 均为正」**降为补充分析 `A5`**（`status=supplementary`，⛔ 不进判决）。
> - **⛔ 不得表述为「原协议 17/17 PASS」**；正确说法：有效门禁 **16/17**。
>
> **协议真空（必须披露）**：原判决 1 要求 `D1–D5 全 PASS`；判决 2 仅覆盖「`D1–D4` 部分 FAIL」。
> 本轮为 `D1–D4 全 PASS + D5 FAIL` ⇒ **两个预注册分支均未覆盖**，协议对该组合**无定义**
> （`protocol_uncovered_case=true`）。故报告**并列双读法**：实体结论（D1–D4 核心）为
> `EXECUTION_LEVEL_CONFIRMED`；严格按原始协议合取条件读法为 `EXECUTION_LEVEL_PARTIAL`。

**五选一判决**
1. `CONSISTENT_*` 且 E01–E06 全 PASS 且 D1–D5 全 PASS ⇒ **`EXECUTION_LEVEL_CONFIRMED`**（E-SB-04 结论升级为执行级）
2. 一致性 PASS 但 D1–D4 部分 FAIL ⇒ **`EXECUTION_LEVEL_PARTIAL`**（逐条披露哪一项不支持）
3. 一致性 `INCONSISTENT` ⇒ **`CONSISTENCY_FAILED__PLANS_LEVEL_RETAINED`**
4. E01–E06 有 FAIL（events 不可靠） ⇒ **`EVENTS_INTEGRITY_FAILED__PLANS_LEVEL_RETAINED`**
5. R01 < 99% ⇒ **`PLAN_EXEC_MISMATCH__PLANS_LEVEL_RETAINED`**

> **★本轮落点（协议真空）**：`D1–D4` 全 PASS、`D5` FAIL ⇒ **判决 1 与判决 2 均不精确适用**。
> 报告**并列**：`verdict = EXECUTION_LEVEL_CONFIRMED`（D1–D4 核心）、
> `verdict_if_strict_protocol = EXECUTION_LEVEL_PARTIAL`。⛔ 不得只报前者。

**判决后动作**
- 判决 1：把 E-SB-04/04B 的路径结论从 `PLANS_LEVEL` 升级为**执行级**；更新 `MEMORY.md` 阶段链与证据等级。
- 判决 2–5：**维持 `PLANS_LEVEL`**；⛔ 不调 `SCALE`/容量/`freespeed`/λ/阈值；⛔ 不启动信号灯/交叉口实验；⛔ 不晋升 v1.1。

---

## §7 红线（本轮不变）

⛔ 不调 `SCALE`；⛔ 不改容量 / `freespeed` / λ / 阈值；⛔ 不启动信号灯、交叉口实验；
⛔ 不晋升 `v1.1`；⛔ 不覆盖原 SB-A5 输出；⛔ 不重跑 `SB-A5ind`；
⛔ v1.0 与原 SB-A5 均保持不动（只读）。

## §8 交付物

```
experiments/E-SB-05_exec_level_events/
  configs/config_SB-A5_EVT19_CHECK.xml
  outputs/SB-A5_EVT19_CHECK/                 ITERS/it.0, it.19（含 events）+ 根产物
  logs/SB-A5_EVT19_CHECK_run.log
  audit/  esb05_preflight.csv
          run_config_manifest.json
          input_manifest.json
          SB-A5_EVT19_CHECK_run_stamp.json
          esb05_consistency_files.csv / _numeric.csv / _gates.csv / _summary.json
          SB-A5_EVT19_CHECK_allhours_conv.linkstats.txt.gz
          esb05_events_integrity.json
          esb05_exec_route_compare.csv
          esb05_exec_route_gates.csv
          esb05_exec_route_summary.json
          _exec_cache/                       （大件中间缓存，不入 reports）
  PROTOCOL_E-SB-05.md
  README.md
reports/exec_level_events_E_SB_05/
  VERDICT_E-SB-05.md
  exec_level_scorecard.csv
```

## §9 渲染纪律

- 凡「判据 + 实测」同行必**动态渲染**（⛔ 硬编码符号）。
- 证据等级必须逐处显式标注（`PLANS_LEVEL` / `EXECUTION_LEVEL`）。
- 覆盖率必同报（多少 person 进入比较、多少被排除及原因）。
- 门禁须携带**实测值**；负例门禁须证明识别假门禁的假门禁（G02b / C13）。
- 判决只用 `status=effective` 的门禁；撤回/阻塞项保留实录。
