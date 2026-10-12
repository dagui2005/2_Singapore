# VERDICT — E-SB-05：SB-A5 执行级 events 验证

> 实验：`E-SB-05_exec_level_events` ｜ runId：`SB-A5_EVT19_CHECK`
> 性质：**EXPERIMENT ONLY / NOT v1.1** ｜ 建立：2026-10-12T07:07:04
> 上游：`E-SB-04`（plans 级路径重分配）、`E-SB-04B`（plans 级速度↔改道耦合）、`E-SB-03`（1.0601 归因）
> 运行：heap 24g ｜ rc=0 ｜ 用时 125.7 min

---

## 0. 判决

### **`EXECUTION_LEVEL_CONFIRMED`**（核心执行级判据 D1–D4 + A/B/C） ｜ 证据等级：**`EXECUTION_LEVEL`**

SB-A5 的 **执行级路线**已由 events 直接重建，并在 `drop_start_link` 语义下与 selected plan **逐人 100% 对账**（236,039/236,039）；在与 v1.0 的同 population、同迭代配对比较中，执行路线的快速路里程份额 **50.9497% → 54.5310%**（+3.5813 pp），与计划级 +3.5742 pp 同号同量级（差 +0.0070 pp）。

> ⚠️ **协议合规披露**：原始预注册判据 **D5 FAIL**（执行级里程份额 Δ Top-2 = **['PIE', 'MCE']**，非 PIE/TPE）；有效门禁 **16/17**。**⛔ 不得表述为「原协议 17/17 PASS」**，详见 §3.3。

| 读法 | 覆盖范围 | 结果 |
|---|---|---|
| **实体结论**（核心执行级配对） | A1–A3 · B1–B5 · C1–C3 · **D1–D4** | **全 PASS** ⇒ `EXECUTION_LEVEL_CONFIRMED` |
| **原始预注册协议**（含 D5 硬门禁） | 上列 + **D5** | **16/17 PASS**（**D5 FAIL**）⇒ 严格读法 `EXECUTION_LEVEL_PARTIAL` |
| **协议真空** | `D1–D4 PASS` 且 `D5 FAIL` | 判决 1 要求 D1–D5 全 PASS；判决 2 仅覆盖 D1–D4 部分 FAIL ⇒ **两分支均未覆盖** |

> ⛔ **本轮撤回「原协议 17/17 PASS」表述**。正确说法：**核心执行级判据（D1–D4）全 PASS；原始预注册判据 D5 FAIL；协议对「D1–D4 PASS + D5 FAIL」组合无定义**（`protocol_uncovered_case=True`）。

| 块 | 判据 | 通过 |
|---|---|---|
| A 运行一致性 | A1–A3 | **3/3** |
| B events 完整性 | B1–B5 | **6/6** |
| C 路线对账 | C1–C3 | **3/3** |
| D 执行级配对 | D1–D4（+ 原始 D5） | **4/5** |
| | **合计有效门禁** | **16/17** |

---

## 1. 运行一致性：开 events 没有改变仿真动力学

- **it.19 逐链 LinkStats sha256 逐位相同**：`True`
  - 参照 `ddc879a07dfedb429367e90b8f880afc6ee63088…`
  - 新 run `ddc879a07dfedb429367e90b8f880afc6ee63088…`
- 确定性产物 sha256 相同：**79/79**
- 观测域复算（it.10–19 cycle-mean → 576 断面 → median×SCALE=2.29897）：

| 量 | v1.0 | 原 SB-A5 | 新 run |
|---|---|---|---|
| 08-09 `Sim/Obs` | 0.9993348 | 1.0600691 | **1.0600691** |
| 匹配边 ΣQ(raw) | 2,741,071.9000 | 2,944,517.8000 | **2,944,517.8000** |
| 断面 ΣQ(scaled) | 1,513,214.5844 | 1,605,179.8215 | **1,605,179.8215** |

⇒ **结论**：`writeEventsInterval=19` 只挂了一个输出 handler，**未改变仿真动力学**；新 events 可安全用于推断原 SB-A5 的执行路径。

| ID | 判据 | 结果 | 实测 |
|---|---|---|---|
| A1 | 总判决 = CONSISTENT_* | **PASS** | verdict=CONSISTENT_STRICT |
| A2 | it.19 linkstats.gz 逐位相同 | **PASS** | identical=True |
| A3 | 观测域 Sim/Obs(08-09) == 原 SB-A5 1.0600691（±1e-6） | **PASS** | new=1.0600691 ref=1.0600691 |

---

## 2. events 完整性与路线对账

- 事件类型集合：`['PersonEntersVehicle', 'PersonLeavesVehicle', 'actend', 'actstart', 'arrival', 'departure', 'entered link', 'left link', 'vehicle enters traffic', 'vehicle leaves traffic']`
- 事件计数（新 run it.19）：`{'actend': 236044, 'departure': 236044, 'PersonEntersVehicle': 236044, 'vehicle enters traffic': 236044, 'left link': 80286900, 'entered link': 80286900, 'vehicle leaves traffic': 236044, 'PersonLeavesVehicle': 236044, 'arrival': 236044, 'actstart': 236044}`
- 关联 person 数：**236,044**
- 重建执行路线的 person 数：**236,039**
- 未完成（截尾排除）：0

**对账语义（实测）**：`entered link` 只带 `vehicle` ⇒ 经 `PersonEntersVehicle` 关联到 person；
selected plan 的 `<route type="links">` 内容以 `start_link` 为首元素，车辆被置于 start_link ⇒
events 不记其 `entered link` ⇒ `obs == plan[1:]`。

| 侧 | 匹配率 | direct | drop_start_link | drop_last_link | mismatch |
|---|---|---|---|---|---|
| **SB-A5_EVT19_CHECK** | **100.0000%** | 0 | 236039 | 0 | 0 |
| v1.0（独立复核） | 100.0000% | 0 | 236039 | 0 | 0 |

⇒ `drop_start_link` 语义两侧一致，且与 E-SB-04 对 v1.0 的独立抽样（8,000/8,000 = 100%）一致。

| ID | 判据 | 结果 | 实测 |
|---|---|---|---|
| C1 | obs == plan[1:]（drop_start_link 语义）占比 ≥ 99% | **PASS** | rate=100.0000% (236,039/236,039)；direct=0 drop_start=236039 drop_last=0 mismatch=0 |
| C2 | drop_start_link 是优势语义（严格高于 direct 与 drop_last_link） | **PASS** | drop_start=236039 direct=0 drop_last=0 |
| C3 | 该语义在 v1.0 侧亦成立（与 E-SB-04 抽样 8,000/8,000 独立一致） | **PASS** | v1.0 rate=100.0000% (236,039/236,039) |

---

## 3. 执行级配对比较（v1.0 vs SB-A5_EVT19_CHECK）

同 population（`population_lambda_0p075.xml.gz`）、同 `lastIteration=19`、同 seed；
**只有网络 `freespeed` 不同** ⇒ 差异可干净归因到「网络改速 ⇒ 路线重分配」。

- 共享 person：**236,039**
- **执行路线改变率**：**66.0603%**（155,928 人）
  ｜ 计划级参照（E-SB-04）：66.0589%
- 执行 VKT：v1.0 3,315,013.5 km → SB-A5 3,366,229.6 km
  ｜ 人均里程 14.0443 → 14.2613 km
- 人均 link 数 341.930 → 340.143

### 3.1 快速路（motorway + motorway_link）里程份额

| 口径 | v1.0 | SB-A5 | Δ |
|---|---|---|---|
| **执行级**（总量加权） | 50.9497% | **54.5310%** | **+3.5813 pp** |
| **计划级**（E-SB-04 参照） | 50.8234% | 54.3976% | **+3.5742 pp** |
| 执行级（逐人均值，稳健性） | 38.5344% | 42.3216% | +3.7872 pp |

⇒ **执行级 Δ 与计划级 Δ 同号同量级（差 +0.0070 pp）** ⇒ E-SB-04 的「计划路线向快速路倾斜」
不是计划层伪影，**在执行中真实发生**。

### 3.1b 方法学校验：执行级里程与计划级里程之差恰为 `start_link`

`obs == plan[1:]` 意味着执行级里程**天然不含 `start_link` 的长度**。若该语义被正确实现，
则「计划级人均里程 − 执行级人均里程」应在两侧**都等于人均 `start_link` 长度**：

| 侧 | 计划级人均里程 | 执行级人均里程 | 差（= 人均 `start_link`） |
|---|---|---|---|
| v1.0 | 14.0798 km | 14.0443 km | **35.4 m** |
| SB-A5 | 14.2967 km | 14.2613 km | **35.4 m** |

⇒ 两侧差值一致（差 0.00 m），验证了执行路线重建的**唯一系统性缺口**
就是 `start_link`，不是遗漏 link 或截断 ⇒ 执行级份额与计划级份额可直接比较。

### 3.2 逐道路等级份额（执行级 vs 计划级）

| 等级 | v1.0 执行 | SB-A5 执行 | 执行 Δ | v1.0 计划 | SB-A5 计划 | 计划 Δ |
|---|---|---|---|---|---|---|
| motorway | 44.6683% | 47.3704% | +2.7021 | 44.5552% | 47.2523% | +2.6970 |
| motorway_link | 6.2814% | 7.1606% | +0.8792 | 6.2681% | 7.1453% | +0.8772 |
| trunk | 9.2661% | 7.9045% | -1.3616 | 9.2432% | 7.8853% | -1.3579 |
| trunk_link | 0.7402% | 0.7393% | -0.0009 | 0.7386% | 0.7378% | -0.0009 |
| primary | 25.1960% | 23.6301% | -1.5659 | 25.1442% | 23.5830% | -1.5612 |
| primary_link | 0.5688% | 0.7138% | +0.1450 | 0.5679% | 0.7125% | +0.1446 |
| secondary | 5.5875% | 5.2624% | -0.3251 | 5.5793% | 5.2551% | -0.3242 |
| secondary_link | 0.1211% | 0.1479% | +0.0268 | 0.1212% | 0.1480% | +0.0268 |
| tertiary | 2.5386% | 2.3936% | -0.1451 | 2.5389% | 2.3942% | -0.1447 |
| tertiary_link | 0.0242% | 0.0298% | +0.0056 | 0.0242% | 0.0298% | +0.0056 |
| service | 1.6498% | 1.6290% | -0.0208 | 1.8081% | 1.7849% | -0.0232 |
| unclassified | 0.3240% | 0.2628% | -0.0612 | 0.3244% | 0.2633% | -0.0610 |
| residential | 3.0338% | 2.7557% | -0.2781 | 3.0866% | 2.8085% | -0.2782 |
| **快速路合计** | 50.9497% | 54.5310% | +3.5813 | 50.8234% | 54.3976% | +3.5742 |

### 3.3 执行级走廊（里程份额 + person 使用率）

| 走廊 | v1.0 里程份额 | SB-A5 里程份额 | Δ 里程 | v1.0 使用率 | SB-A5 使用率 | Δ 使用率 |
|---|---|---|---|---|---|---|
| PIE | 15.0956% | 15.9430% | +0.8474 pp | 27.3277% | 30.3848% | +3.0571 pp |
| MCE | 0.6827% | 1.1799% | +0.4972 pp | 2.0691% | 3.6977% | +1.6285 pp |
| CTE | 8.1178% | 8.4391% | +0.3213 pp | 19.2286% | 20.9978% | +1.7692 pp |
| TPE | 3.4402% | 3.6624% | +0.2222 pp | 9.6946% | 10.8613% | +1.1668 pp |
| AYE | 6.1900% | 6.4105% | +0.2205 pp | 11.0566% | 12.7818% | +1.7251 pp |
| KPE | 2.2069% | 2.4073% | +0.2004 pp | 6.2257% | 7.2073% | +0.9816 pp |
| BKE | 2.9016% | 3.0780% | +0.1764 pp | 10.1326% | 10.6063% | +0.4737 pp |
| ECP | 1.2431% | 1.3974% | +0.1543 pp | 3.2554% | 3.8417% | +0.5863 pp |
| KJE | 1.4288% | 1.5495% | +0.1208 pp | 4.2607% | 5.0030% | +0.7423 pp |
| SLE | 3.9413% | 3.9693% | +0.0279 pp | 10.6279% | 10.6275% | -0.0004 pp |

⇒ 执行级里程份额 Δ Top-2 走廊 = **['PIE', 'MCE']**（合计 +1.3446 pp）。

#### ★★原始预注册判据 D5 的处置（逐条披露）

- **原始预注册判据 D5**（`PROTOCOL_E-SB-05.md` 初稿）：执行级里程份额 Δ Top-2 走廊 **恰为** PIE/TPE。
- **本轮实测排序**（里程份额 Δ 降序，前 5）：`PIE > MCE > CTE > TPE > AYE`
  ｜ person 使用率 Δ 排序（前 5）：`PIE > CTE > AYE > MCE > TPE`
- ⇒ 实测 Top-2 = **['PIE', 'MCE']**，**不是 PIE/TPE**
  ⇒ **原始 D5 = FAIL**（TPE 里程份额口径第 **4** 位、使用率口径第 **5** 位）。
- **处置**：原 D5 判定**保留为 FAIL（硬门禁）**；「PIE 与 TPE 的里程份额 Δ 均为正」**降为补充分析 `A5`**
  （`status=supplementary`，**不进判决**）。
- **协议真空**：原判决 1 要求 `D1–D5 全 PASS`、判决 2 仅覆盖 `D1–D4 部分 FAIL`；本轮为
  `D1–D4 全 PASS + D5 FAIL` ⇒ **两个预注册分支均未覆盖**（`protocol_uncovered_case=True`）。
- **双读法（并列，⛔ 不静默择一）**：
  - **核心执行级判据 D1–D4 全 PASS** ⇒ E-SB-04/04B 的路径结论**升级为执行级**（实体结论）；
  - **严格按原始协议合取条件** ⇒ 有效门禁 **16/17**，严格读法为 `EXECUTION_LEVEL_PARTIAL`。

#### ★ D5 修订时间线核实（客观证据，⛔ 不采信自述）

| 通道 | 可用性 | 说明 |
|---|---|---|
| Git 历史 | **不可用** | `esb05_*` 脚本与协议**从未被 git 跟踪**（`tracked=False`）⇒ 无历史可回放 |
| 协议 mtime | 可用 | `2026-10-11 23:06:25` 早于 SB-A5 执行级数据 `2026-10-12 01:20:38` |
| 脚本 mtime | **已被本轮覆盖** | 为恢复原始 D5 而编辑脚本 ⇒ 原 `23:11:42` 已丢失（现 `2026-10-12 07:06:48`）⇒ 观察者破坏性 |

- **审计判决**：`EVIDENCE_CHANNELS_EXHAUSTED__REVISION_TIMING_UNVERIFIABLE`。
- ⇒ **本报告不主张「修订先于数据」，也不主张「原协议 17/17 PASS」**；
  证据不足时按**最保守口径**处理：原始 D5 保留 FAIL、修订版降为补充分析。
- E-SB-03 原命题是「PIE+TPE **合计贡献 63.4% 的观测域净流量增量**」（**贡献份额**，非排序第一名）。
  本轮**补充分析**的等价检验为符号同向：里程份额 Δ PIE = +0.8474 pp、TPE = +0.2222 pp
  （使用率 Δ +3.0571 / +1.1668 pp）⇒ 均 > 0。
  但 TPE 增量**量级远小于 PIE**，在本轮执行级口径下**非贡献前二**；E-SB-03 的「63.4%」是
  **观测域断面流量**口径、与本轮**执行级里程份额**口径**不同源**，⛔ 不得互换。

| ID | 判据 | 结果 | 实测 |
|---|---|---|---|
| D3 | 共享 person 集合 ≥ 236,000（可比性） | **PASS** | ∩=236,039  NEW=236,039  v1.0=236,039 |
| D1 | 执行路线改变率 > 0（且与计划级 66.06% 同量级） | **PASS** | exec_change=66.0603%  plans_change=66.0589% |
| D2 | 执行路线快速路里程份额：SB-A5 > v1.0（Δ > 0） | **PASS** | v1.0=50.9497%  SB-A5=54.5310%  Δ=+3.5813 pp |
| D4 | 执行级 Δ 与计划级 Δ 同号且 \|Δ_exec − Δ_plans\| ≤ 2 pp | **PASS** | Δexec=+3.5813 pp  Δplans=+3.5742 pp  差=+0.0070 pp |
| D5 | ★【原始预注册判据】执行级里程份额 Δ Top-2 走廊 恰为 PIE/TPE | **FAIL** | 实测 Top-2 = ['PIE', 'MCE']；排序 PIE > MCE > CTE > TPE > AYE ⇒ 不满足 |

**参考项（不进判决）**

| ID | 类型 | 判据 | 实测 |
|---|---|---|---|
| A5 | supplementary | （补充分析）执行级 PIE 与 TPE 的里程份额 Δ 均为正（与 E-SB-03 观测域净增同向） | PIE:+0.8474 pp \| TPE:+0.2222 pp |
| I1 | informative | （参考）执行级里程份额 Δ Top-2 走廊 合计 | top2=['PIE', 'MCE'] 合计 +1.3446 pp |

---

## 4. 与 E-SB-04 / E-SB-04B 的衔接

| 环节 | E-SB-04（plans） | E-SB-05（execution） | 一致？ |
|---|---|---|---|
| 路线改变率 | 66.0589% | 66.0603% | 同量级 |
| 快速路份额 Δ | +3.5742 pp | +3.5813 pp | 同号 PASS |
| PIE 里程份额 Δ | （E-SB-04 未单列） | +0.8474 | 与 E-SB-03 观测域同向（**补充分析 `A5`**，⛔ 非门禁） |
| TPE 里程份额 Δ | （E-SB-04 未单列） | +0.2222 | 符号同向（**补充分析**）；但**量级远小、非 Top-2** ⇒ **原始 D5 FAIL**（见 §3.3） |

E-SB-04B 的 `FREESPEED_ROUTE_COUPLING_SUPPORTED` 结论基于同一 population、仅 `freespeed` 差 90,643 链；
本轮执行级证据表明该「改道补偿」**在执行层同样成立**。

---

## 5. 边界（不得越过）

- 本轮**只**补执行级证据；⛔ 未调 `SCALE`；⛔ 未改容量 / `freespeed` / λ / 阈值；
  ⛔ 未启动信号灯、交叉口实验；⛔ 未晋升 `v1.1`；⛔ 未覆盖原 SB-A5 输出；⛔ 未重跑 `SB-A5ind`。
- `v1.0` 与原 SB-A5 均保持不动（只读）。
- 执行级 `Sim/Obs` 口径未变：**不得**用本轮结果去把 `Sim/Obs` 调向 1。
- 「执行路线改变」是**网络改速的后果**，不代表校准结论升级；口径（car-only 通勤 vs 全机动车+全目的）差异仍在。

---

## 6. 产物清单

```
experiments/E-SB-05_exec_level_events/
  PROTOCOL_E-SB-05.md  README.md
  configs/config_SB-A5_EVT19_CHECK.xml
  outputs/SB-A5_EVT19_CHECK/            (ITERS/it.0, it.19 含 events + 根产物)
  logs/SB-A5_EVT19_CHECK_run.log
  audit/  esb05_preflight.csv, run_config_manifest.json, input_manifest.json,
          SB-A5_EVT19_CHECK_run_stamp.json,
          esb05_consistency_files.csv / _numeric.csv / _gates.csv / _summary.json,
          SB-A5_EVT19_CHECK_allhours_conv.linkstats.txt.gz,
          esb05_events_integrity.json, esb05_exec_route_compare.csv,
          esb05_exec_corridor_use.csv, esb05_exec_route_gates.csv,
          esb05_exec_route_summary.json, _exec_cache/
reports/exec_level_events_E_SB_05/
  VERDICT_E-SB-05.md  exec_level_scorecard.csv
```
