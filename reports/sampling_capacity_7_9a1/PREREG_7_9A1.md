# PREREG — Step 7.9A-1 采样一致性容量（sample-consistent capacity）· 单因子动态实验

> **状态：运行前冻结（零仿真）。** 本文件在**任何 MATSim 点火之前**写盘并登记 SHA256。
> 点火后**任何判据、阈值、口径、产物清单不得修改**；确需修改 ⇒ 作废本文件、另立 R2。
>
> - 上游：`reports/sampling_capacity_audit_7_9a0/SAMPLING_CAPACITY_AUDIT_7_9A0.md`（2026-09-20，**22/22 PASS**，
>   判决 `SAMPLING_CAPACITY_INCONSISTENCY_CONFIRMED`）。本步是 A-0 §五 执行计划的**点火**版本。
> - 身份：**v1.1 结构修复的第一刀**（7.8 `version_semantics`：改动 `f/λ/SCALE/f_cap/route-choice` 任一 ⇒ 新模型版本）。
>   ⛔ 本步**不修改 v1.0 的任何冻结件**；`v1.0` 仍是唯一冻结模型。
> - 触发背景：领导反馈「VIA 画面不真实、没有拥堵」；2026-09-29 第一手核实确认
>   ①出发时刻已由 6.3.3A 分散（07 时 48.71 % / 08 时 51.29 %，逐秒随机）⇒ 「全员 08:00 出发」前提在 v1.0 **不成立**；
>   ②容量嫌疑成立且已被 A-0 量化，但 `7.9A-1` **从未点火**。故本步只做**单因子**（容量），不重建脉冲对照臂。

---

## §0 本步回答 / 不回答什么

**回答**（三问 + 一护栏）：
1. 把 QSim 的流量与存储容量按 population 表示比例 `1/SCALE = 0.434977` 缩放后，全网拥堵是否出现**量级**变化？
2. 拥堵是否出现在**正确的空间位置**（相对 7.3.6A 冻结靶场）？
3. 拥堵是否呈现**正常的形成—消散时间过程**（onset / peak / clear / duration），而非静态贴色？
4. **护栏**：是否出现网络崩解（stuck、滞留在途、流量护栏失守）？

**不回答**：
- 不重定 `λ / f_work / OD / 路网 / route-choice / 出发时刻`；
- 不回答「0.434977 是不是真实容量」——本步只检验**表示口径一致性**，`0.434977` 由 population representation 独立推导，
  **不由交通观测误差反演**；
- **不**把本步结果写成「最优容量」。

---

## §1 唯一结构变化（单因子、单点、不扫描）

| # | 参数 | v1.0 冻结值 | **A-1 值** | 模块 | 性质 |
|---|---|---|---|---|---|
| 1 | `qsim.flowCapacityFactor` | `1.0` | **`0.434977`** | qsim（**生效**） | 模型 |
| 2 | `qsim.storageCapacityFactor` | `1.0` | **`0.434977`** | qsim（**生效**） | 模型 |
| 3 | `controller.outputDirectory` | `…\matsim_final_7_6h\outputs\W01_rc_min` | `…\matsim_sampling_capacity_7_9a1\outputs\A1_capf0p435` | controller | 输出层 |
| 4 | `controller.runId` | `W01_rc_min` | `A1_capf0p435` | controller | 输出层 |
| 5 | `controller.writeEventsInterval` | `0` | `19` | controller | 输出层 |

- **判据**：与冻结 config 的**全展开参数 diff 必须恰为 5 项**（含 `<parameterset>` 子节点展开）；出现第 6 项 ⇒ **FAIL 中止**。
- **不做扫描**：`0.35 / 0.40 / 0.45 / 0.50` 属参数拟合，A-0 已预注册排除。
- **不采取**：⛔ 不改 `hermes.*CapacityFactor`（`mobsim=qsim` ⇒ **惰性**）；⛔ 不改 `dsim.trafficDynamics=kinematicWaves`（**惰性诱饵**）。
- 数值精度：`0.434977` 由 `1/SCALE = 1/2.29897` 计算；配置写入 **6 位小数**（`0.434977`），
  并在产物中报出 `1/SCALE` 的 15 位值与二者之差（预期 `|Δ| ≤ 5e-7`）。

---

## §2 完全不动（逐位继承，跑前已断言）

`λ = 0.075` · `f_work = 1.180222` · `SCALE = 2.29897` · `N_sim = 236,044` ·
route-choice **R01**（`fractionOfIterationsToDisableInnovation = 0.8` / `ReRoute 0.15` + `ChangeExpBeta 0.85` /
`learningRate 0.5` / `routingRandomness 0.0` / `maxAgentPlanMemorySize 5` / `WorstPlanSelector`）·
人口 `matsim_final_7_6h/populations/pop_W01/population_lambda_0p075.xml.gz` ·
路网 `reports/matsim_network/network_cleaned.xml.gz` · `randomSeed = 4711` · `lastIteration = 19`（20 迭代）·
`qsim.trafficDynamics = queue` · `qsim.linkDynamics = FIFO` · `qsim.timeStepSize = 00:00:01` ·
出发时刻实现（**6.3.3A 分散**，已冻结）· crosswalk **7.3.6A**。

---

## §3 输入契约与只读守卫

| 项 | 要求 |
|---|---|
| 源配置 sha256_16 | 必须 `== 8f44fb349bff9cf1` |
| 人口 sha256_16 | 必须 `== e96ed83ff59c0f5e` |
| 14 件冻结输入（`FINAL_MODEL_MANIFEST.json : evidence_manifest`） | 跑前/跑后 `sha256_16` + `mtime` 快照比对，**0 变化** |
| 冻结目录 `matsim_final_7_6h/` · `matsim_viz_7_8/` · `reports/final_model_7_8/` | 跑前后递归 sha 快照，**0 漂移**；`out_inside_guard == False` |
| 新产物落点 | 仅 `matsim_sampling_capacity_7_9a1/` 与 `reports/sampling_capacity_7_9a1/` |

---

## §4 ★四动态指标（操作定义 + 相对判据）

### §4.0 统一仪器原则（★本步的关键设计）

A-1 的**全部**动态指标，与 **v1.0 的 events**（`matsim_viz_7_8/outputs/W01_events/`，已判 `BITEXACT`，
`163,305,988` 条 / `departure = arrival = 236,044`）**用同一段代码、同一口径、同一时间窗**计算。

⇒ 因此**全部判据都是相对的**（A-1 vs v1.0），不依赖任何事后挑选的绝对阈值。

**linkstats 列索引**（154 列，已实测）：`LENGTH = 4`、`FREESPEED = 5`、`CAPACITY = 6`、
`HRS8-9avg = 32`（**流量**，veh/h）、`TRAVELTIME8-9avg = 107`（**行程时间**，s）。

```text
ff_s        = LENGTH / FREESPEED
ff_ceil_s   = ceil(ff_s - 1e-9)                       # ★量化消除（7.7E：TT=ceil(FF)）
excess_s    = TRAVELTIME8-9avg - ff_ceil_s            # 真实超额秒（>= 0）
speed_ratio = ff_s / TRAVELTIME8-9avg
```

### §4.1 指标① 拥堵链路数 `N_cong`

```text
N_cong(cut) = # { HRS8-9avg > 0  ∧  excess_s >= 1.0 s  ∧  LENGTH >= cut }      cut ∈ {0, 50, 100, 200} m
N_slow(cut) = # { HRS8-9avg > 0  ∧  speed_ratio < 0.80 ∧  LENGTH >= cut }      # ★不依赖容量口径
```

- v1.0 基线（`cut = 0`，实测）：`N_cong = 7,985`、`loaded = 224,432`（3.56 %）。
- 报告：A-1 与 v1.0 的绝对数、**倍率**、新增/消失链路的**条数与里程**。

### §4.2 指标② `v/c >= 1` 链路数

```text
v/c = HRS8-9avg / CAPACITY_eff          # CAPACITY_eff 按 §11 消解规则确定
```

- 报告：`n(v/c >= 0.5 / 0.9 / 1.0 / 1.5 / 2.0)`、饱和里程 `sat_km`、
  `share_len_saturated = sat_km / 15,126.5 km`、`share_flow_on_saturated`。
- v1.0 基线（实测）：`n(>=0.5)=2,813`、`n(>=0.9)=220`、`n(>=1.0)=82`、`sat_km = 1.1514`、`max v/c = 1.000000`。

### §4.3 指标③ 拥堵持续时间 / 排队形成—消散

**仪器**：events 逐条流式解析（`A1_capf0p435.19.events.xml.gz`，≈1.7 GB），**5 分钟 bin**，窗口 `06:00–12:00`。

| 序列 | 定义 |
|---|---|
| `n_slow_links(t)` | 该 bin 内在该链路上**车辆级平均行程速度比 < 0.6** 的链路数（由 `entered link` / `left link` 的车辆级配对计算） |
| `n_queued(t)` | 该时刻**已 `vehicle enters traffic` 但尚未 `entered link`** 的车辆数（等待插入） |
| `enroute(t)` | 在途车辆数（已 `entered link` 未 `left link`） |

- 输出：`t_onset`（`n_slow_links(t)` **首次 ≥ v1.0 同 bin 值的 3 倍**）、`t_peak`、`t_clear`、`duration = t_clear − t_onset`。
- 判据：A-1 的 `max_t n_slow_links` 与 `duration` **相对 v1.0** 的倍率；**必须同时给出 v1.0 同口径曲线**。

### §4.4 指标④ 拥堵空间位置

1. 输出 A-1 与 v1.0 的**按 `excess_s` 降序 top-500** 拥堵链路清单（含 `LINK`、`ORIG_ID`、`RoadName`、`RoadCat`、
   `highway`、`LENGTH`、`excess_s`、`speed_ratio`、`v/c`）。
2. **锚 7.3.6A 靶场**：`reports/od_final_calibration_crosswalk_7_3_6/final_calibration_crosswalk.csv`
   （文件内 590 断面 / 3,193 行；取 `is_primary_candidate == True` 的主候选集，并与 7.1 靶场**显式对账**，
   预期 ≈ **576 断面 / ≈ 3,015 匹配链**；对账差额**必须报出并解释**）。
3. 判据（★**双基数并报，防 base-rate 反转**——7.9D-0 的教训）：

```text
overlap_len_share = (拥堵链路 ∩ 靶场链) 里程 / 拥堵链总里程
base_rate_len_share = 靶场链总里程 / 全网载流链总里程        # 同一 15,126.5 km 口径
concentration_ratio = overlap_len_share / base_rate_len_share
```

| `concentration_ratio` | 读法 |
|---|---|
| `> 1.5` | 拥堵**向靶场聚集**（位置可能对） |
| `0.67 – 1.5` | comparable（无证据） |
| `< 0.67` | 拥堵**避开靶场**（= **堵错地方**） |

4. 走廊分组（`RoadCat ∈ {CATA, CATB, CATC, SLIP_ROAD}`，另按 `highway` 分组）分别报 excess 汇总与倍率。
5. 输出：拥堵空间位置图（EPSG:3414）+ **VIA 可加载属性层**（`link` / `speed_kmh_0809` / `vol_0809` /
   `cong_ratio_0809` / `delay_s_per_km_0809`），格式与 `reports/via_congestion_diagnosis_7_8/via_link_attributes_HRS8-9.tsv` **同构**。

---

## §5 三层判据（A-0 §五 预注册，逐条继承）

| 层 | 内容 |
|---|---|
| **① 流量（崩解护栏）** | `Sim/Obs >= 0.85`（⛔ `0.9993` **不是**本步目标）；`CATA / CATB / SLIP_ROAD` 分组 ratio；Pearson r、WMAPE、GEH 分布；`Σsim × SCALE vs Σobs` |
| **② 拥堵形成** | 真实 excess（扣 `ceil(ff)`）、`N_cong`、`sat_km`、走廊 excess、排队连通链长、峰 `aggV/C`、峰在途量 |
| **③ 数值稳定性** | `A_10:19`（收敛诊断）、parity gap、`never_arrived`、`max_stuck_car`、departure/arrival 完整率（`arrival == departure == 236,044` 为满分） |

---

## §6 零仿真先验（A-0 已算，作为**预期**，**不是**判据）

| 指标 | v1.0 实测 | A-1 上界投影 | 倍数 |
|---|---:|---:|---:|
| `n(v/c >= 1.0)` | 82 | 4,187 | 51.06 |
| `saturated_km` | 1.1514 | 178.114 | 154.69 |
| `share_len_saturated` | 0.0076 % | 1.1775 % | 154.69 |
| 峰 `aggV/C` | 0.102447 | 0.235522 | 2.29897 |
| `share_flow_on_saturated` | 0.226 % | 23.329 % | 103.25 |
| `n(v/c >= 0.5)` | 2,813 | 16,049 | 5.705 |
| `n(v/c >= 0.9)` | 220 | 5,413 | 24.60 |

★ 该投影假设「**冻结流量不变**」、**未计排队回落** ⇒ 实测**预期低于**上界。
★ A-0 预先提示：即使按 sample-consistent 容量，峰 `aggV/C` 也只到 **0.236**、饱和里程只占 **1.18 %**
⇒ **仍不预期出现全网级拥堵波**；若实测与之相符 ⇒ 主因更可能落在**情形 C**（sample inconsistency 非主因）。

---

## §7 四种结果读法（冻结，A-0 §五）

| 情形 | 判据 | 读法 | 动作 |
|---|---|---|---|
| **A** | 拥堵显著增强且流量基本保持 | v1.0 轻拥堵主因 = **sample-capacity inconsistency** | v1.1 = 表示尺度统一（**非调参**） |
| **B** | 拥堵增强但大量 stuck / 网络崩解 | 方向对，但超细碎路网 storage/bottleneck 表达承受不了 | 转 **7.9B Network Bottleneck / Storage Structure**（⛔ **不把容量调回去**） |
| **C** | 拥堵增强很少 | sample inconsistency **不是**主因 | 第二刀 = **7.9B `trafficDynamics`** |
| **D** | 流量指标严重恶化而拥堵才变合理 | 既有断面流量校准可能依赖了错误的容量尺度补偿 | 检查 OD assignment / flow scale / capacity / departure concentration 耦合 |

---

## §8 红线（用户指定，逐条继承 A-0）

- ⛔ 不为了让 VIA 变红而提高 `demand`；
- ⛔ 不为制造拥堵而降低容量 / 修改 `λ` / 修改 route-choice；
- ⛔ 不为视觉效果重定义 congestion index；
- ⛔ **不把 `0.434977` 表述为「为了让新加坡堵起来把容量砍到 43.5 %」**。

★ 正确表述：**「由于模型 population 按 43.4977 % 样本表示完整交通需求，而 QSim 的流量与存储容量采用未经
sample adjustment 的 1.0 倍容量，因此首先检验 sample-consistent capacity representation；
该因子由 population representation 独立推导，不由交通观测误差反演。」**

---

## §9 必需产物（本步交付）

**运行侧**（`matsim_sampling_capacity_7_9a1/`）
1. `configs/config_A1_capf0p435.xml`
2. `audit/config_diff_whitelist.csv`（全展开 diff，含 `whitelisted` 列）
3. `audit/frozen_inputs_before.csv` / `audit/frozen_inputs_after.csv`
4. `audit/a1_run_integrity.json`（运行门 + 契约门 + 冻结只读证据）
5. `logs/A1_capf0p435_run.log`
6. `outputs/A1_capf0p435/A1_capf0p435.output_config.xml`（**实际生效配置**，含 `flowCapacityFactor`）
7. `outputs/A1_capf0p435/ITERS/it.19/A1_capf0p435.19.linkstats.txt.gz`
8. `outputs/A1_capf0p435/A1_capf0p435.output_events.xml.gz`（VIA 用）

**评价侧**（`reports/sampling_capacity_7_9a1/`）
9. `PREREG_7_9A1.md`（本文件）
10. `a1_prereg_sha.json`（本文件 SHA256 + 冻结时刻）
11. `a1_face_metrics.csv`（① ② 指标，A-1 vs v1.0）
12. `a1_time_series.csv`（③ 的 5-min 曲线，A-1 与 v1.0 并列）
13. `a1_spatial_top500.csv`（④ 的 top-500 拥堵链路，A-1 与 v1.0）
14. `a1_target_overlap.csv`（④ 的靶场锚定 + 双基数）
15. `a1_guardrails.csv`（① 流量层 + ③ 数值稳定性层）
16. `via_link_attributes_HRS8-9_A1.tsv`（VIA 属性层）
17. `congestion_map_A1_HRS8-9.png`（空间位置图）
18. `STEP7_9A1_REPORT.md`（正式报告）
19. `a1_summary.json`（判决 + 全部头条量，**含实测值**）

---

## §10 判定文本（闭集）

| 判决 | 条件 |
|---|---|
| `SAMPLING_CAPACITY_R0_READY` | 全部硬门 PASS，且 `arrival == departure == 236,044`，且 `Sim/Obs >= 0.85` |
| `SAMPLING_CAPACITY_NETWORK_BREAKDOWN` | 触发情形 B 的崩解护栏（`never_arrived` 或 `max_stuck_car` 超阈，或 `Sim/Obs < 0.85`）⇒ 按 §7 情形 B 处置，⛔ **不把容量调回** |
| `FAILED` | 契约门 / 冻结只读门失败，或运行非 0 退出 |

---

## §11 ★`v/c` 分母歧义的预注册消解规则（本步新增，运行前冻结）

**问题**：MATSim 的 `linkstats.CAPACITY` 列在 `f_cap = 1.0` 时**无法判别**它属于**基础容量**（网络属性）还是
**有效容量**（已乘 `flowCapacityFactor`）。这直接决定 A-1 的 `v/c` 分母用 `CAPACITY` 还是 `CAPACITY × 0.434977`。

**消解规则（确定性，点火后不允许择一）**：

1. 按 `LINK` 键对齐 A-1 与 v1.0 的 `CAPACITY` 列（`n = 693,575`）：
   - 若 **693,575 / 693,575 逐位相同** ⇒ `CAPACITY` = **基础容量** ⇒ `CAPACITY_eff = CAPACITY × 0.434977`；
   - 若 **A-1 ≈ v1.0 × 0.434977**（逐条相对差 `≤ 1e-6`，且逐位相同的条数为 0）⇒ `CAPACITY` = **有效容量** ⇒ `CAPACITY_eff = CAPACITY`；
   - 其他情况 ⇒ 判 **`CAPACITY_SEMANTICS_UNRESOLVED`**：本步**不报 `v/c`**，只报 `excess_s` / `speed_ratio`（**容量口径无关**），并在报告中显式声明。
2. **交叉验证**（必须记录）：A-1 中 `max(HRS8-9avg)` 应 `≤` 量级相符的 `CAPACITY_eff`；
   若出现**大量** `HRS8-9avg > CAPACITY_eff`（> 100 条）⇒ 判规则选错 ⇒ 回到第 1 条并把两版数字**同时**报出。
3. `n(v/c >= 1.0)` 的**主判据**统一采用消解后的 `CAPACITY_eff`；若走第 1 条第三分支，则该指标记为 `NA` 并注明原因。

---

## §12 与本步无关（明确排除）

- ⛔ 本步**不**重建「08:00 单脉冲」对照臂（2026-09-29 核实：v1.0 已含 6.3.3A 分散，07 时 48.71 % / 08 时 51.29 %，
  逐秒随机 7,200 个不同值）——若日后需要「时间形状贡献」，须**另立** 7.9A-2 并单独预注册。
- ⛔ 本步**不**改 `trafficDynamics`（留待 7.9B）。
- ⛔ 本步产物**不得**被引用为对 v1.0 的标定证据；`Sim/Obs = 0.9993347697` 仍以 v1.0 为唯一权威。
