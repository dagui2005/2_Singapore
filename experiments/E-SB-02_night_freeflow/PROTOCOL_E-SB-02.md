# 预注册协议 —— E-SB-02：夜间自由流速度代理 × 独立 OD 口径

> 状态：**预注册草案（待用户裁定 4 个分支后冻结）**
> 目录：`experiments/E-SB-02_night_freeflow/`
> 上游门禁：**E-SB-02A 数据门禁 = `AVAILABLE`（6/6 PASS）** · **E-SB-02B 泄漏审计 = `LEAKAGE_QUANTIFIED`（7/7 PASS）**
> 红线：不改 v1.0 / OD 冻结件 / crosswalk / TrafficFlow / SpeedBand 原始值 / 评价器阈值；不产生 v1.1；只建新目录与新网络。

---

## 0. 为什么要这个实验

E-SB-01 把可变杠杆逐一试过，结论是：**速度侧的高杠杆在「供给侧自由流速度」，不在容量、不在排队机制**。

| 臂 | 改动 | 联合结果 | 裁定 |
|---|---|---|---|
| SB-A1 | `qsim.trafficDynamics: queue→kinematicWaves` | 速度无改善、流量变差（Sim/Obs 0.85） | **暂停** |
| SB-A3 | 定向容量 `capacity←c·m(l)`（4,838 链/236.5 km） | bias 压到 +3.24 但 **RMSE 反升**、流量崩到 0.50 | **暂停** |
| SB-A3n | 同 A3、空间打乱（负例） | 比 A3 更差（RMSE 20.80 vs 19.22） | **保留为负例证据**（证明 A3 是空间定向而非全域拉慢） |
| SB-A4 | 网络 `freespeed←AM 观测速度` | RMSE 18.24→**8.38**、r 0.40→**0.91**、band 21.7%→**61.9%**；但 **AM→AM 循环** | **保留为诊断性上界** |
| SB-A2 | `storageCapacityFactor 1.0→0.434977` | 点火即崩（框架阻断，源码级+jshell 实证） | **暂停，不绕过框架校验** |

**没有任何一臂可直接晋升 v1.1。** SB-A4 证明速度侧空间很大，但它是循环的（写 AM 观测、评 AM 观测）。

E-SB-02 的目标：用**夜间**速度（≠AM）估计自由流速度，并在**已隔离 AM 泄漏**的口径下，检验能否**同时**通过速度与流量两类检验。

---

## 1. E-SB-02A —— 夜间 SpeedBand 数据门禁（✅ 已完成）

**判决 `AVAILABLE`（6/6 PASS）**，报告见 `reports/esb02_night_audit/REPORT.md`。四项必答：

| 必答 | 结论 |
|---|---|
| 夜间有哪些时间戳 | 46 个夜间快照，内部权威时间戳 `lastUpdatedTime` 落 **23:00–06:59**；覆盖 **4 个夜晚**：2026-05-06(15) / 05-07(16) / 06-19(7，仅1.33h部分夜) / **10-07(8)** |
| 每条路有几次观测 | 6,033,595 条记录；每链中位 **42** 次，**≥6 次占比 100%**；`N_adjacent{05-06,05-07}` 中位 **29**，`N_distant{10-07}` 恰好 **8** |
| 覆盖多少公里/哪些等级 | AM 靶场 **92,149 边 / 2,816.2 km 全覆盖 100%**；residential 1,016 km、service 281 km、primary 438 km、motorway 143 km… 分等级均 100% |
| 哪些路段够估计自由流 | **全部 92,149 链均 ≥6 观测**（`N_distant` 单夜也 100% 过门槛） |

**关键数据身份事实**：`historical_data/TrafficSpeedBands_v4.json` = **单次 2026-05-05 18:53:30 快照**，**已排除**（非夜间样本）。12 处"文件名≠内部时间戳"为整点命名下载，滞后 ≤11 min，无害。

**一致性**（反量化口径）：逐链 Δ(p75−AM) 均值 **+6.94 km/h**，夜>AM 占 57.5% ⇒ 夜间确实更畅通。**但 residential 提升最小**（Δp75 仅 +5.58；夜中位 24.5 与 AM 同档），而 residential 恰是最大偏差来源。

---

## 2. E-SB-02B —— AM SpeedBand → OD 泄漏的隔离（✅ 已量化）

报告：`reports/esb02_leakage_audit/REPORT.md`（判决 `LEAKAGE_QUANTIFIED`，7/7 PASS）。

- **通道**：`TrafficSpeedBands(AM) → C^AM(332×332, 中位 21.361 min) → 重力 exp(−λ·C^AM) → IPF → Prior OD → 200k 人口`。**唯一泄漏点**。
- **作用面**：只改"目的地选择权重"；**P_i / A_j / Table118 是硬约束，不受影响**（总量 ΣT=1,935,235 与支撑格 71,136 恒定）。
- **量级**：`TV(T^5B, T^5C.1) = **3.49%**`（λ=0.075，重算与既有产物逐位一致）；随 λ 单调（2.34%→6.73%）；单块最大变化 **0.0130 pp**（分散，无集中伪影）。
- **方向**：AM 阻抗使 OD **略更本地化**（区内份额 +20.5% 相对）。
- **独立 OD 选项**：**Step 5B 自由流阻抗 OD（`reports/od_prior_5b/`）已存在，零 SpeedBand 输入**，约束框架与 5C.1 相同。

⛔ 不得写成"无泄漏"；正确表述 = "**已量化、可隔离、可用独立 OD 对照消除**"。

---

## 3. E-SB-02C —— 夜间自由流候选臂（待点火）

### 3.1 供给层规则（三个显式旋钮）

| 旋钮 | 预注册建议默认 | 备选 |
|---|---|---|
| **夜晚选择** | `N_adjacent{05-06, 05-07}`（29 次/链；与 AM 靶场同属那两天，物理解释力最强） | `N_distant{10-07}`（时间独立，仅 8 次）；`N_all4`（42 次，含部分夜/截断） |
| **分位数** | **p75**（自由流中位 34.5 km/h；比 A4 的 24.5 温和） | p50（24.5，=A4 水平）；p90（34.5） |
| **SB8 规则** | `freespeed_new = max(75, 该链 v1.0 自由流)`，**仅对 SB8 来源生效** | — |

> 只读预览（E-SB-02A §6）：`SB5_p75` 改动 **98.58%** 链；自由流中位 `v1.0(50.0) > SB5_p75(34.5) > SB5_p50(24.5)=A4(24.5)`；motorway 三分位都保留 90.0（SB8 规则生效）。

### 3.2 只改一件事

- 派生 **新网络**（新目录，不碰 `reports/matsim_network/network_cleaned.xml.gz`）：仅替换匹配链的 `freespeed`。
- **不动**：OD/需求、`SCALE`、`capacity`、`storageCapacityFactor`、`flowCapacityFactor`、动态机制、`seed`、迭代数（20）、route-choice 冻结参数。
- **不同时**引入容量缩放 / 信号灯 / scoring 调整。

### 3.3 臂结构（★需裁定）

| 臂 | 需求 | 网络 freespeed | 目的 |
|---|---|---|---|
| **SB-A5**（主臂） | v1.0 `5C.1`（含 AM 泄漏 3.49%） | 夜间 p75 | 单因子：夜间自由流是否同时改善速度+流量 |
| **SB-A5ind**（独立性对照） | **Step 5B（无 SpeedBand）** | 同 SB-A5 网络 | 让"AM 速度拟合"真正样本外 |

- `Δ(SB-A5, SB-A5ind)` = 「AM 先影响车辆去哪走」的下游影响。
- 若 `Δ` 小 ⇒ 结论对泄漏稳健；若大 ⇒ 必须以 `SB-A5ind` 口径报告。

---

## 4. 判定门槛（★三组共同判断，不能只看一项）

| 目标 | 主要指标 | 判定原则 |
|---|---|---|
| **速度区间** | 速度区间损失、RMSE、精确 band 命中、±1 band 命中、分等级符号 | 相对 v1.0 **明确且可重复**改善（RMSE 显著降、band 命中升，且**不得出现符号相反的分等级亚类被均值掩盖**） |
| **流量** | 总量 `Sim/Obs`、MAE、RMSE、空间相关、区域/等级/走廊残差、低估-高估分布 | 总量落 `Sim/Obs∈[0.95,1.05]`（**必要条件，非充分**），且**空间误差无明显恶化** |
| **拥堵机制** | 低速档仿真速度分布、拥堵链、延误、`stuck`/`never_arrived` | **不能只靠压低自由流制造漂亮 band 命中**；按观测档看仿真速度的**分辨率必须真实提升** |
| **独立验证** | 未用于 OD 构建/参数估计的数据 | 样本外仍改善（`SB-A5ind` 或 `N_distant`） |

**参考基线（E-SB-01 冻结口径 08–09 / cycle it.10–19）**：

| 臂 | Sim/Obs | bias | RMSE | r | band 精确 |
|---|---:|---:|---:|---:|---:|
| v1.0 | 0.9993 | +8.58 | 18.24 | 0.401 | 21.7% |
| SB-A4（上界） | 1.0524 | −5.35 | 8.38 | 0.910 | 61.9% |

> ⚠️ A4 的 `1.0524` 已略超 1.05 上限 ⇒ **即便速度 RMSE 大降，也不能不加限定判为通过**。SB-A5 必须在**速度改善**与 **`Sim/Obs∈[0.95,1.05]`** 之间同时成立。

---

## 5. 跑后决策树

| 若 | 则 |
|---|---|
| 速度与流量都改善 | 保留夜间自由流候选网络 → 独立日期/独立路段验证 → 再谈 v1.1 |
| 速度改善、流量空间分布不改善 | 查 **OD 空间分配、路径选择、断面—路网映射**；⛔ 不用 capacity 强行压速度 |
| 夜间自由流合理、AM 低速档仍拟合不好 | **才**评估信号灯/交叉口延误/排队传播/交通动力学（需下一轮实验验证，⛔ 不得仅凭当前诊断认定某机制必为主因） |

---

## 6. 必须随结果声明的限制

- **Level 1（本实验可做）**：SB-A5 用**夜间**设 `freespeed`、用 **AM** 评价 ⇒ 参数估计层已摆脱 A4 的 AM→AM 循环；`SB-A5ind` 进一步消除需求层的 3.49% 泄漏 ⇒ 可称"**样本外速度拟合**"。但 **λ 与 `SCALE` 曾由 TrafficFlow 选定** ⇒ 流量拟合仍是**样本内**。
- **Level 2（须补数据）**：`TrafficFlow`=2025-11 vs `SpeedBand`=2026-05 **不同期** ⇒ 不得称"通过真实流量与速度观测联合校准"。转正式需**同期**数据 + 留出未参与构建的日期。
- **物理限制**：夜间速度（尤其 residential 24.5 km/h）**不是零流自由流**，仍含信号与路口延误；把 `freespeed` 设为它 = **把信号延误折进自由流**（与 A4 同性质，只是数据源换成非 AM）。

---

## 7. ⛔ 红线

- 不改 v1.0 / `network_cleaned.xml.gz` / OD 冻结件 / crosswalk / `TrafficFlow` / `SpeedBand` 原始值 / 评价器阈值。
- 不产生 v1.1；新配置单独建目录。
- 不绕过 MATSim 框架校验（SB-A2 教训）。
- 不因结果显著就把"尺度相关"解释成"交通动力学机制"。
- ⛔ 与已 `CLOSED` 的 O3-R1 严格隔离。

---

## 8. ★已裁定（2026-10-09 冻结）

| 项 | 裁定 |
|---|---|
| **夜晚** | `N_adjacent{2026-05-06, 2026-05-07}`（29 次观测/链） |
| **分位数** | **p75** |
| **SB8 规则** | `freespeed_new = max(75, 该链 v1.0 自由流)`，**仅对 SB8 来源生效** |
| **臂结构** | **`SB-A5` + `SB-A5ind`**（含独立性对照） |

---

## 9. ★已派生并过门（零仿真）

| 阶段 | 产物 | 门禁 |
|---|---|---|
| 网络 | `networks/network_SB-A5.xml.gz` | **8/8 PASS**；改动 **91,532** 链；逐行差异集合**精确等于**目标集合；`freespeed∈[5,90]`；内容 sha16 `7a2a81f925c5c560`（**两次重建一致 = 可复现**） |
| 配置 | `configs/config_SB-A5.xml` / `config_SB-A5ind.xml` | 配置 diff **恰为白名单**（3 / 4 项，含 `controller.runId`） |
| 独立需求 | `populations/population_SB-A5ind_lambda_0p075.xml.gz` | **15/15 PASS**（v2 全链，见 §11）；来源 = `reports/od_prior_5b`（**零 SpeedBand**）；车行 OD 层 `TV(5C.1,5B)=0.0346`；**persons=236,044**（与 v1.0 `pop_W01` 同 N）；**真解析门通过** |
| 运行前硬门 | — | 两臂各 **11/11 PASS**（含新增 `R-09` 真解析门） |

> ⚠️ **§9 原记的「独立需求 5/5 PASS」已作废** —— 那是 v1（200,000 / 非原生格式，MATSim 无法解析）。见 **§11**。

- 分母链接：目标 92,149 具名链 → **在网 91,956**（另 **193 不在仿真网络内**，与既有已证事实相符，非映射错误）。
- **分等级改动**：residential 99.94%、service 99.34%、primary 99.91%、tertiary/secondary/unclassified 100%、motorway_link 99.51%、trunk 97.35%、**motorway 73.12%（418 链保留 90，SB8 规则生效）**。
- 源网络内容 sha16 `40cdffc340fee130`、源配置 `8f44fb349bff9cf1`（冻结未动）。

### 复现命令
```bash
python scripts/experiments/esb02_build_arms.py        # 网络 + 配置（可复现）
python scripts/experiments/esb02_build_ind_demand.py  # SB-A5ind 独立需求
python scripts/experiments/esb02_run_arm.py --arm SB-A5       # 运行前硬门
python scripts/experiments/esb02_run_chain.py --arms SB-A5 SB-A5ind --heap 24g  # 点火（断点续跑）
python scripts/experiments/esb02_objective.py         # 联合评分卡
```

---

## 10. 两个修掉的真问题（教训）

1. **`controller.runId` 继承 v1.0**：配置派生时若不动 `runId`，输出文件会命名为 `W01_rc_min.19.linkstats.*`，与 v1.0 混淆。⇒ 已显式设 `controller.runId = 臂名`，并加门禁 `R-04b`。
2. **`gzip.open` 头写入 mtime ⇒ 派生网络 sha16 不可复现**（同一内容两次构建得到不同哈希）。⇒ 改为**确定性写出**（`GzipFile(mtime=0, filename="")`）+ **内容哈希**（解压后再 sha），并让运行前门禁**从派生记录读期望值**而非硬编码。

---
*⛔ 本轮：零仿真、零冻结件改动；未产生 v1.1。下一动作 = 用户裁定后点火两臂。*

---

## 11. ★SB-A5ind 需求链修正（v1 → v2，真缺陷披露）

**首跑结果**：`SB-A5` **rc=0**（104.7 min，`it.19.linkstats.txt.gz` 已落盘）· `SB-A5ind` **rc=4 / 0.2 min**
⇒ **SB-A5ind 从未真正启动**。两臂不可比，**不得据此出联合结论**。

### 11.1 三处缺陷（全在「独立需求的构建」上，与 SB-A5 无关）

| # | 缺陷 | 证据 |
|---|---|---|
| 1 | **格式非法**：Step 6.2 用 `xml.etree` 直写，**缺 `<!DOCTYPE ...population_v6.dtd>`**，且属性写成 `<attribute ... value="…"/>` 自闭合形式 | 运行日志 `XML-FATAL … line 2, column 1 … "this.delegate" is null`；根因 = `MatsimXmlParser` 靠 DOCTYPE 选 delegate；DTD 要求属性值写在**元素正文**里 |
| 2 | **跳步**：v1.0 需求链为 `先验OD → 6.2 → **6.2B** → **连通性修复** → **6.3.3A** → **7.4.3 复制**`，v1 只做了 **6.2** | 6.2 产物 desc = `Singapore Step 6.2 car-only sampled population`；v1.0 为 `Step 6.2B … (connectivity-repaired)` |
| 3 | **样本量错配**：SB-A5 用 v1.0 `pop_W01` = **236,044** agent；v1 需求仅 **200,000** ⇒ 两臂样本量不同 = **混杂** | `pop_W01` persons=236,044 = `round(1.180222 × 200,000)`；v1 产物 persons=200,000 |

> ⚠️ 第 3 条即使修好前两条也**不能比**：agent 数不同会让 linkstats 总量口径整体平移。

### 11.2 修复（v2 = 复用**同一条冻结链**，只换先验 OD 目录）

```
reports/od_prior_5b            （自由流阻抗，零 SpeedBand）
  → Step 6.2   build_matsim_population.py        → car_prior_od_lambda_0p075.parquet
  → Step 6.2B  build_matsim_population_6_2b.py   → 200,000 原生格式人口
  → 连通性修复  prepare_connected_scenario.repair_population()   （★只调函数，不跑 main()，
                 以免覆写冻结件 reports/matsim_network/connectivity_repair.json）
  → Step 6.3.3A build_departure_profile_6_3_3a.py → 出发时刻
  → Step 7.4.3  run_demand_scale_7_4_3.build_population → 236,044
= populations/population_SB-A5ind_lambda_0p075.xml.gz
```
全程 **不改任何脚本、不改冻结件**，仅 monkeypatch `PRIOR_DIR / OD_DIR / POP_IN / POP_OUT / OUT`。

### 11.3 冻结链复现证据

对 **5C.1** 的 6.3.3A 人口做同样的 236,044 复制，逐位比对：

| 对象 | 解压内容 sha256 |
|---|---|
| 复现产物 | `01d50a6432f78ebb8408abeeac79e29e33f31dba1977647aedd7b64860e2885b` |
| `pop_W01` 冻结件 | `01d50a6432f78ebb8408abeeac79e29e33f31dba1977647aedd7b64860e2885b` |

⇒ **逐位一致**，链理解与复制机制无误。（`ΣEF` 236,044 复制后 = 542,628.84，非 459,794 —— 与既有「⛔ 不得按 `ΣEF/N_sim` 重算 `SCALE`」一致。）

### 11.4 门禁升级（★第 8 次「假门禁」修正）

- **旧 `R-06`**：只查「文件存在 + 文件名」⇒ 放行了一个从根节点就 FATAL 的文件。
- **新 `R-09`（真解析门）**：新增 `scripts/experiments/matsim_pop_probe.py`，**直接调用 MATSim 失败时的同一个类** `org.matsim.core.population.io.PopulationReader` 实际解析；并校验 `persons / withEF / missingEF`。
- **正负例对照（已验证探针具判别力）**：

| 文件 | 探针 |
|---|---|
| `pop_W01`（v1.0） | ✅ OK persons=236,044 |
| `reports/matsim_population_6_2b/…` | ✅ OK persons=200,000 |
| **坏文件（旧 v1 产物）** | ❌ FAIL，且报**与灭火日志逐字相同**的 `line 2, column 1 … delegate is null` |

### 11.5 影响范围

- **SB-A5 的 rc=0 结果不受影响**（它用 `pop_W01`，与 SB-A5ind 相互独立）。
- 需**重跑 SB-A5ind**（断点续跑会自动跳过 SB-A5）；其后再出联合评分卡与 `VERDICT_E-SB-02.md`。
- ⛔ 修复前**不得**将 SB-A5 与旧 SB-A5ind 并置比较。

---

## 12. ★结果记录（2026-10-10 跑完）

**点火**：`SB-A5` 跳过（`it.19` 已在）· `SB-A5ind` **rc=0 / 73.1 min**（首跑 rc=4 见 §11，修复后重跑成功）。
**裁定书**：`VERDICT_E-SB-02.md` —— 判决 **`SPEED_GAIN_INDEPENDENT_CONFIRMED__FLOW_GATE_FAILED`**。
**评分卡**：`audit/esb02_joint_scorecard.csv`（8 行 = v1.0 / E-CAP-01 / SB-A1 / SB-A3 / SB-A3n / SB-A4 / SB-A5 / SB-A5ind）。

| 判据（§4） | 裁定 | 关键实测 |
|---|---|---|
| 速度区间 | ✅ PASS | RMSE 18.235→**10.527**（−42.3%）· band 21.68→**40.58%**（+18.9 pp）· r 0.401→**0.771** |
| 流量（必要条件 `[0.95,1.05]`） | ❌ **FAIL** | cycle **1.0601** · it.19 1.0618 · POSITIVE_ONLY 1.1273 · BEST_DIR 1.1075（SB-A5ind cycle **1.0751**） |
| 拥堵机制分辨率 | ✅ PASS | 按观测档 spread 25.7→**53.2**（obs 54.5）· `r(band,sim)=0.9995` · 残差 = **均匀 +5 km/h 偏置**（非形变） |
| 独立验证 | ✅ PASS | `SB-A5ind`（零 SpeedBand）仍 −42.2% RMSE、+18.8 pp band；**≈ SB-A5**（ΔRMSE 0.007 km/h） |

**泄漏下游影响**：速度侧可忽略（ΔRMSE +0.06%）· 流量侧可见（1.060→1.075 = +1.42% 相对）。
**总判决**：判据 1/3/4 过、**判据 2（必要条件）不过 ⇒ 无一臂晋升 v1.1**；`SB-A5` 保留为候选网络，`SB-A4` 保持诊断性上界（循环）。
**下一轮唯一建议**：只读+预注册审计「低自由流制度下的 `Sim/Obs` 总量平移」（SCALE 制度平移 / 路径重分配 / 窗内滞留 三选一）；⛔ 裁定前不动 `SCALE`/容量/阈值。
