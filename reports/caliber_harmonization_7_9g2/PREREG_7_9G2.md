# PREREG — Step 7.9G-2 「时间 / 数量 / 距离 / 体积」四面口径统一

- **节点**：`7.9G-2 CALIBER_HARMONIZATION`
- **状态**：`OPEN`（用户裁定 2026-09-28）
- **性质**：**零仿真 / 只读**（read-only，zero-simulation）。不跑 MATSim，不产生新 agent，不修改任何冻结件。
- **本文件一旦冻结，其判据、阈值、闭集、门编号、负例、输出清单**在分析阶段**不得更改**；如需更改，必须新建 `PREREG_7_9G2_R2.md` 并把本文件标为 `SUPERSEDED`。

---

## §1 冻结边界（用户裁定，逐条不可推导）

### 1.1 本轮**只**解决「怎么统计、怎么表达」

> **不再重新争论 G-1 的机制结论，只解决"怎么统计、怎么表达"这个问题。**

因此：

- ⛔ **不得**在 `7.9G-2` 中对 `A1–A6`（G-1 六项判决）作任何重新判定、重新解释或反证；
- ⛔ **不得**提出新的拥堵机制假说；
- ⛔ **不得**以 `7.9G-2` 的统计结果去"确认"或"削弱" `A6 = ENDPOINT_ABSORPTION_DOMINANT`；
- ✅ **只**输出「四面的统一统计定义 + 统一表达规则 + 可长期复用的报告模板」。

### 1.2 `7.9G-0` 的两条边界继续有效

```text
不得把"94.36%"作为 service 延误归因的单一证据；
不得把 service capacity = 400 veh/h/lane 直接作为后续敏感性旋钮。
```

### 1.3 冻结影响 = 无

- 不改 `Singapore_OD_MATSim_Final_v1.0`；
- 不回写、不覆盖、不"修正" `reports/service_delay_mechanism_7_9g0/` 与
  `reports/endpoint_access_absorption_7_9g1/` 的**任何**已冻结产物；
- 不重跑 MATSim；不新增 `qsim.*` 覆写；不动 `service` 容量与端点吸附行为。

### 1.4 阶段目标（用户给定）

```text
输入冻结 → prereg → 零仿真 / 只读 → 四面统一 → 负例 + BLOCKED → 独立复核 → READY / CLOSED
```

### 1.5 主线位置

```text
7.9F-0 容量编码审计 → 7.9F-1 聚合统计审计 → 7.9F-2 道路匹配机制
→ Q2 方向关系（未发现解释信号）→ Q4-R1-R1 最近邻捕获 READY
→ 7.9G-0 service 延误总审计 READY → 7.9G-1 端点/接入吸收 READY
→ ★ 7.9G-2 时间/数量/距离/体积四面口径统一
→ LTA 分车型 / HTS 出发时刻
```

---

## §2 冻结输入（**5 件**，SHA-256 逐字节核验；任一变更即 BLOCKED）

| # | 键 | 相对 `ROOT = D:\Luan\2026-05\2_Singapore` 的路径 | 字节数 | SHA-256 |
|---|---|---|---|---|
| I1 | `pop` | `matsim_final_7_6h/populations/pop_W01/population_lambda_0p075.xml.gz` | 8,930,574 | `e96ed83ff59c0f5ecb50c9d9ff2d42a4b4bdbebf2bbfe81a1e0604fb94921fbd` |
| I2 | `ls_final` | `matsim_final_7_6h/outputs/W01_rc_min/ITERS/it.19/W01_rc_min.19.linkstats.txt.gz` | 22,629,291 | `b842b93a92f41c81248922078ebc68fdbe5ddc88f70086ccfd32bf955f0c1949` |
| I3 | `ls_viz_ref` | `matsim_viz_7_8/outputs/W01_events/ITERS/it.19/W01_events.19.linkstats.txt.gz` | 22,629,291 | `b842b93a92f41c81248922078ebc68fdbe5ddc88f70086ccfd32bf955f0c1949` |
| I4 | `net_links_runtime` | `matsim_viz_7_8/outputs/W01_events/W01_events.output_links.csv.gz` | 14,753,288 | `b65edfd5a59f233bb2e8d83384dbe07650dadbdae929ed6a378c0e3af0a6c5c9` |
| I5 | `src_copy` | `reports/matsim_network/network_links_source_copy.csv` | 52,670,157 | `b5265e5978608e7337712922b67f455b8c86c42c204ccc32a742da48180de9c6` |

**`I2 ≡ I3`**（sha 相同）是**设计约束**（G-0/G-1 同款），本节点必须在门 07 显式断言。

### 2.1 为什么本节点**不含** `plans` / `events`

`7.9G-2` **不触及**路由遍历与事件级证据。端点对象 `EP_SVC` 的定义逐位继承 G-1 的
`home_p ∪ work_p`（= population activity `link`），而该定义与「选中计划路由首/末 link」的
一致性已由 **G-1 门 10** 以 `contract = 236044/236044/236044`（== 1.000000）过门。
故本节点**不再**引入 `plans`/`events`，以把运行成本压到「net + linkstats」。

> ⚠️ 该"输入缩减"是**显式声明**，不是遗漏：门 04 会断言 manifest 恰为 5 件。

---

## §3 只读对照物（**8 件**，仅读，SHA 核验；**禁止写入**）

### 3.1 G-0（`reports/service_delay_mechanism_7_9g0/`）

| 键 | 文件 | 字节 | SHA-256 |
|---|---|---|---|
| `g0_summary.json` | `g0_summary.json` | 522 | `d8c0b2f0c139005731de63b04ffee19be8265d7853e3839d2c5ec0ce9ab1166a` |
| `g0_service_concentration.csv` | `g0_service_concentration.csv` | 194 | `4898adcf77f90e95b107afab8d251026bd4aed12df990071de9268e0bd81bfed` |
| `g0_exposure_faces.csv` | `g0_exposure_faces.csv` | 252 | `61bb9eef77004e49732472d3b8e54891b7c597e1ec7dcf7e508cafd75b3abba8` |
| `g0_verdicts.csv` | `g0_verdicts.csv` | 1,207 | `38c898f500a7219e60ca0b56aafd74d7fc5181b082a4aad5c037710c78211b8f` |

### 3.2 G-1（`reports/endpoint_access_absorption_7_9g1/`）

| 键 | 文件 | 字节 | SHA-256 |
|---|---|---|---|
| `g1_exposure_faces.csv` | `g1_exposure_faces.csv` | 293 | `c4043a67abb1f8da054dd16848d5a55e90ba3add2ef948db677d68885ae7933b` |
| `g1_endpoint_service_split.csv` | `g1_endpoint_service_split.csv` | 355 | `8a8119d1049ef0e3bd7bcfd8100b3073f0524b8d9ab460d8c4aec732acbe9914` |
| `g1_summary.json` | `g1_summary.json` | 1,031 | `87e1b36fe7abc348c433c0c47aefdd397e0819f34bc7e33c3ae6d50dbdc8333d` |
| `g1_verdicts.csv` | `g1_verdicts.csv` | 864 | `948b974b35e49fcc4c6d2e7df3d8ab5dfd06c664e9c8d3600028fd1d9f053401` |

> 门 25 断言这 8 件与整个 7.9G-0 / 7.9G-1 目录在本节点运行前后**字节不变**。

---

## §4 对象与口径定义（O1–O12，**全部分析必须且只能使用这些定义**）

### O1 — 宇宙 `U`（UNIVERSE）

```text
U_loaded  := { link : vol(link) > 0 }               vol := linkstats 列 "HRS8-9avg"
U_any     := 网络 (net_links_runtime ∩ src_copy) 的全部 link
```

- **默认宇宙 = `U_loaded`**（记 `UNIVERSE_DEFAULT`）。
- 任何在 `U_any` 上计算的量，其**列名/字段名必须带后缀 `_any`**；缺后缀即视为违约（门 08）。
- ⛔ **一次比较内宇宙必须唯一**（门 09）；⛔ 分子、分母不得跨宇宙（门 10）。
- **理由（可证伪）**：`U_any` 含大量零流边，与 `U_loaded` 混用会产生 >100% 的份额，或产生
  「子集占全网 1.71 倍」这类不可能结果。该现象**必须**被门 10 捕获。

### O2 — 分母栈 `D`（DENOMINATOR STACK，嵌套，均在同一宇宙内取）

```text
D0 = ALL      := U_default
D1 = SVC      := U_default ∩ (road_type == "service")
D2 = EP_SVC   := U_default ∩ (road_type == "service") ∩ (link ∈ home_link ∪ work_link)
```

- 任何份额必须写成 `share[face, scope | Dk]`，三要素**缺一不可**（门 12）。
- ⛔ 禁止把 `D1` 或 `D2` 分母的份额标为 `D0`（或反之）——这正是 G-1 中
  `w_ep = 75.6366%`（`|D1`）与 `s_end = 71.3681%`（`|D0`）并存时的**误用风险点**。
- 嵌套单调性：`|D2| ≤ |D1| ≤ |D0|`（逐面量单调，门 11）。

### O3 — 四面 `FACE`（角色固定，不可重标）

| 面 | 角色 | 定义（**逐位继承 G-0 / G-1 canonical**） |
|---|---|---|
| `time` | **IMPACT（影响）** | `delay_corr_h = Σ_{v>0} v · max(0, TT8-9avg − ff_ceil_s) / 3600`，`ff_ceil_s = ceil(length/freespeed − 1e-9)` |
| `count` | **EXPOSURE（暴露）** | 宇宙内 link 条数 |
| `distance` | **EXPOSURE（暴露）** | `Σ length / 1000`（km） |
| `volume` | **EXPOSURE（暴露）** | `Σ HRS8-9avg`（veh） |

```text
IMPACT   := {time}
EXPOSURE := {count, distance, volume}
```

### O4 — 强度面 `INTENSITY`（影响 / 暴露，**三档必报**）

```text
s/link := 3600 · time / count
s/km   := 3600 · time / distance
s/veh  := 3600 · time / volume
```

- 强度面**必须**与份额面**并列**输出（门 18）。份额可比但会掩盖强度差异；二者不可互替。

### O5 — 集中度仪器（`CONCENTRATION`）

**主仪器 = 覆盖率分数**

```text
f_t(scope) := k_t / n_scope
  k_t := 按 delay_corr_h 降序累加至 ≥ t% 的 scope 总延误 所需的最小 link 数
  t ∈ COVER_TARGETS = {50, 90, 99}
```

**判据 = 与基线 `D0` 的倍率**

```text
R_t := f_t(scope) / f_t(D0)
RATIO_CONC_MIN = 3.0

∃ t : R_t ≥ RATIO_CONC_MIN        ⇒ CONCENTRATION_ATTENUATED
∃ t : R_t ≤ 1 / RATIO_CONC_MIN    ⇒ CONCENTRATION_AMPLIFIED
否则                               ⇒ CONCENTRATION_COMPARABLE
```

- 语义：`f_t` 越大 ⇒ 覆盖同样延误份额需要 **更大比例** 的 link ⇒ **相对更分散**。
- ⛔ **Gini 禁用**：在拥堵延误分布下 Gini-over-links 无区分度（`Δ` 量级 `1e-3`）且符号反直觉，
  **不得**作为集中度判据（门 23）。Gini 可作**描述性**字段，但一旦出现在判据表达式中即违约。
- ⛔ **固定 `k` 禁用**：不得以 `top-k`（`k` 为常数，如 `k=10/100`）作为集中度判据。
  `k` 必须声明为 scope 规模的函数（即覆盖分数 `f_t`）。

### O6 — 暴露 / 影响 分离规则

- `IMPACT`（`time`）**不得**由 `EXPOSURE` 任一面替代或推断（门 17）。
- 任何「某类占 X%」的断言**必须**同时给出四元组：`face` + `scope` + `Dk` + `universe`。
- 报告次序固定：先 `EXPOSURE` 三档（`count` → `distance` → `volume`），再 `IMPACT`（`time`），
  最后 `INTENSITY` 三档。

### O7 — 不可合成性

- ⛔ 禁止跨面加权总分 / 归一化总分（`composite index`）。四个面回答**不同问题**，不对等、不互换（门 19）。
- ⛔ 禁止跨面求和（如 `count% + km% + vol% + time%`）。

### O8 — HEADLINE 规则

```text
AGREEMENT_BAND_PP = 5.0
RANGE := max over {time,count,distance,volume} of share[face, scope | D0] − 同理取 min
RANGE ≤ 5.0 pp ⇒ SINGLE_HEADLINE_ADMISSIBLE
RANGE > 5.0 pp ⇒ FOUR_FACE_PARALLEL_REPORTING（⛔ 禁止以任一单面份额作该对象的头部结论）
```

### O9 — 报告模板（句式由用户给定，本节点须**物化**为产物）

> **`service` 端点链对仿真延误具有显著的时间暴露特征，但其影响并不与交通流量占比同步增长；
> 因此应分别从时间、数量、距离和交通量四个维度表征，而不能以单一 `delay share`
> 作为系统性拥堵归因依据。**

模板**必须**含：4 个面标签 + 12 个数值（3 scope × 4 face）+ 3 档强度；**不得**含任何
"某类占 X%，因此……"形式的单面归因句。

### O10 — 冻结继承（不重验）

- `EP_SVC` 定义逐位继承 G-1（`home_p ∪ work_p` = population activity `link`）；
- `canonical delay_corr_h` 口径逐位继承 G-0 / G-1；
- `contract == 1.000000` 由 **G-1 门 10** 负责，本节点不重验（不引入 `plans`）。

### O11 — 只读

零仿真；不改 v1.0；不回写 G-0/G-1；不重跑 MATSim。本节点**只写** `reports/caliber_harmonization_7_9g2/`。

### O12 — 不重开机制

见 §1.1。本节点所有产物**不得**出现 `A1–A6` 的重新判定列。

---

## §5 可证伪问题（Q1–Q4，**全部为闭集判决**）

### Q1 `DENOMINATOR_UNIFORMITY` — 既有口径（G-0/G-1）在四面上是否自洽？

**判据**（两项**同时**满足才算统一）：

```text
(a) 对 G-0/G-1 产物中所有可直接读出或可派生的 share：
    不存在 > 100% + IMPOSSIBLE_SHARE_TOL(=1e-9) 的份额
(b) SPREAD_U := max over faces | share_{U_any}(EP_SVC) − share_{U_loaded}(EP_SVC) |
    SPREAD_U ≤ UNIVERSE_SPREAD_TOL_PP = 0.5
```

```text
(a) ∧ (b) ⇒ DENOMINATOR_UNIFIED
否则       ⇒ DENOMINATOR_SPLIT
```

> ⚠️ 阈值 `0.5 pp` 与 `1e-9` 为**预先约定**（`0.5 pp` 小于任何有统计意义的差异），
> **不得**在看到实测值后回调。

### Q2 `EXPOSURE_IMPACT_SEPARATION` — 暴露面与影响面是否同向？

```text
RANGE_ep := max − min of share[face, EP_SVC | D0] for face ∈ {time, count, distance, volume}
RANGE_ep > AGREEMENT_BAND_PP(=5.0) ⇒ EXPOSURE_IMPACT_DECOUPLED
否则                                ⇒ EXPOSURE_IMPACT_COUPLED
```

辅助证据（**不参与判决**，仅描述）：`s/veh(EP_SVC) / s/veh(D0)` 与 `share_vol / share_time` 的互反性。

### Q3 `CONCENTRATION_VERDICT` — 在预锁定判据下，端点 service 链的延误分布如何？

按 O5：

```text
{CONCENTRATION_AMPLIFIED, CONCENTRATION_ATTENUATED, CONCENTRATION_COMPARABLE}
```

对 `scope ∈ {SVC, EP_SVC}` 各给一次；主判决取 `scope = EP_SVC`。

### Q4 `HEADLINE_POLICY` — 是否可以给单一 headline？

按 O8：

```text
{RANGE_ep ≤ 5.0 pp ⇒ SINGLE_HEADLINE_ADMISSIBLE , 否则 FOUR_FACE_PARALLEL_REPORTING}
```

---

## §6 硬门（**25 条**，编号即门 ID，**顺序即求值顺序**）

| # | 门 ID | 判据（**必须携带实测值**） |
|---|---|---|
| 01 | `7.9G2.01_PREREG_FROZEN_AND_EMBEDDED` | 本文件字节数 == 声明值 且 sha256 == 脚本内嵌 `PREREG_SHA` |
| 02 | `7.9G2.02_SCRIPT_AST_COMPILE` | `ast.parse` 通过 且 `compile` 通过 |
| 03 | `7.9G2.03_ZERO_SIMULATION` | AST 区间检查：模块级无 `matsim*.jar`/`subprocess`/`os.system`/网络写；白名单导入集 |
| 04 | `7.9G2.04_INPUT_MANIFEST_COMPLETE` | manifest 恰 5 件、逐件 sha+bytes 与 §2 一致 |
| 05 | `7.9G2.05_LINKSTATS_154_COLUMNS` | linkstats 列数 == 154，且必需字段全在 |
| 06 | `7.9G2.06_NETWORK_JOIN_COMPLETE` | net ∩ ls 的 link 覆盖数 == `len(U_any)`，未匹配 == 0 |
| 07 | `7.9G2.07_LINKSTATS_JOIN_COMPLETE` | `sha(I2) == sha(I3)` 且 ls 行数 == 覆盖数 |
| 08 | `7.9G2.08_UNIVERSE_DECLARED_PER_ROW` | 每个产物行带 `universe` 列且 ∈ `{U_loaded, U_any}`；`U_any` 量字段名带 `_any` 后缀 |
| 09 | `7.9G2.09_UNIVERSE_SINGLE_PER_COMPARISON` | 同一 `(face, scope, Dk)` 组合下 universe 唯一 |
| 10 | `7.9G2.10_NO_IMPOSSIBLE_SHARE` | 所有 share ≤ 100% + 1e-9；且**显式断言**「分子宇宙 == 分母宇宙」（捕捉 170.96% 类失效） |
| 11 | `7.9G2.11_NESTED_DENOMINATOR_MONOTONIC` | 逐面：`val(D2) ≤ val(D1) ≤ val(D0)` |
| 12 | `7.9G2.12_DENOMINATOR_DECLARED_PER_ROW` | 每个 share 行带 `denom_scope ∈ {D0, D1, D2}`，非空 |
| 13 | `7.9G2.13_FACE_ROLE_DECLARED` | 每行带 `face_role ∈ {IMPACT, EXPOSURE}`，且与 O3 表一致 |
| 14 | `7.9G2.14_FOUR_FACE_MATRIX_COMPLETE` | 3 scope × 4 face = 12 行全填，无 NaN |
| 15 | `7.9G2.15_FACE_RECOMPUTE_MATCHES_G0` | SVC 的四面值与 `g0_exposure_faces.csv` **逐位**一致（`rtol 0`，`atol 0`） |
| 16 | `7.9G2.16_EP_SVC_RECOMPUTE_MATCHES_G1` | EP_SVC 的 `vol`/`delay_h` 与 `g1_endpoint_service_split.csv` 逐位一致；`length_km` 差异必须**显式标注宇宙**（`U_any` vs `U_loaded`），不得静默取一个 |
| 17 | `7.9G2.17_IMPACT_ONLY_FROM_TIME_FACE` | 所有 `face_role == IMPACT` 的行其 `face == time`；产物内不得出现「用 count/km/vol 表述影响」的字段名 |
| 18 | `7.9G2.18_INTENSITY_REPORTED` | `s/link`、`s/km`、`s/veh` 三档 × 3 scope 全非空 |
| 19 | `7.9G2.19_NO_COMPOSITE_INDEX` | 产物列名/字段名不含 `composite|index|score|weighted_sum|total_share` 等；AST 无跨面求和 |
| 20 | `7.9G2.20_CONCENTRATION_INSTRUMENT_DECLARED` | 集中度产物声明 `instrument == "coverage_fraction"`、`t ∈ {50,90,99}`、`k` 为 scope 规模函数；⛔ 出现常数 `k`（如 `top10`）即 FAIL |
| 21 | `7.9G2.21_CONCENTRATION_BASELINE_PAIRED` | 每个 scope 的 `f_t` 必同报 `f_t(D0)` 与倍率 `R_t` |
| 22 | `7.9G2.22_CONCENTRATION_VERDICT_SINGLE` | Q3 闭集唯一取值，且与 `R_t` 数值自洽 |
| 23 | `7.9G2.23_GINI_FORBIDDEN_AS_CRITERION` | 判据表达式/AST 中不含 `gini`；Gini 若出现仅可作描述性字段且**不得**参与任何比较 |
| 24 | `7.9G2.24_TERMINAL_STATE_THREE_WAY` | 写盘回查（显式清单集合 + 逐字节 + 无游离文件）∧ 三方状态一致（`checks` / `summary` / `report`）∧ summary 数字与产物同源 |
| 25 | `7.9G2.25_NON_7_9G_ARTIFACTS_UNCHANGED` | 7.9G-0 / 7.9G-1 两目录在本节点运行前后**逐文件 sha 不变**；且本节点输出不落在两目录内 |

---

## §7 判决闭集

```text
Q1 DENOMINATOR_UNIFORMITY : {DENOMINATOR_UNIFIED, DENOMINATOR_SPLIT}
Q2 EXPOSURE_IMPACT_SEPARATION : {EXPOSURE_IMPACT_DECOUPLED, EXPOSURE_IMPACT_COUPLED}
Q3 CONCENTRATION_VERDICT  : {CONCENTRATION_AMPLIFIED, CONCENTRATION_ATTENUATED, CONCENTRATION_COMPARABLE}
Q4 HEADLINE_POLICY        : {FOUR_FACE_PARALLEL_REPORTING, SINGLE_HEADLINE_ADMISSIBLE}
```

- 四问**各自独立**，不得互相推导。
- ⛔ 不得出现闭集外的取值，也不得新增第五问。
- **状态串**：`CALIBER_HARMONIZATION_R0_READY` / `CALIBER_HARMONIZATION_R0_BLOCKED`。

---

## §8 负例（**11 真负例** + **1 空负例自检** + **3 BLOCKED**）

手法：对分析脚本做**文本级补丁**（每处 `assert src.count(old) == 1`），在**新沙盒根**
`reports/_g2_neg_root/` 下独立运行，读 `g2_checks.csv`，断言期望门以 `pass=False` 出现。

| # | 名称 | 注入 | 期望触发门 |
|---|---|---|---|
| N1 | **改分母** | time 面的 `share｜D0` 改用 `D1` 作分母 | 12 / 09 |
| N2 | **time 当 volume** | 把 `time` 值写进 `volume` 面 | 15 |
| N3 | **link 数当 delay** | 把 `count` 值写进 `time` 面 | 15 / 17 |
| N4 | **混用内部/全网占比** | 把 `w_ep`（`｜D1` 分母）标为 `D0` | 12 / 10 |
| N5 | **固定 k 判据** | 以常数 `top-10` 作集中度判据 | 20 |
| N6 | **合成总分** | 追加列 `composite = 0.25*t + 0.25*c + 0.25*d + 0.25*v` | 19 |
| N7 | **分母声明缺失** | 某行 `denom_scope` 置空 | 12 |
| N8 | **宇宙混用** | 分子 `U_any`、分母 `U_loaded`（可产生 >100%） | 10 |
| N9 | **Gini 作判据** | 集中度判据改 `gini >= 0.8` | 23 |
| N10 | **单面 headline** | 把单一 `time` share 写成头部结论字段 | 17 |
| N11 | **冻结件被动** | 运行后改写 `g1_exposure_faces.csv` 一个字节 | 25 |

**空负例自检 `S1`（纪律 ⑧ 的强制执行）**

```text
S1 := 把某字段写死为「其真值」（no-op，不改变任何可观测结果）
断言：套件对其判 fired = False
若套件报 fired = True ⇒ 套件失效（失败）
```

> 即：**负例必须真改变可观测结果**。写死为真值只证明"没抓到"，不证明"能抓到"。
> 该自检本身**必须**在 `g2_summary.json` 中以 `noop_selfcheck_passed: true` 物化。

### 8.1 BLOCKED 三件（**必须完整物化**）

| # | 名称 | 构造 | 断言 |
|---|---|---|---|
| P1 | `empty_ref_dir` | `--ref-dir` 指向空目录 | 终态 = `CALIBER_HARMONIZATION_R0_BLOCKED`，25 行 checks 齐全，6 件终态产物齐全，EXIT=1 |
| P2 | `tamper_pop_sha` | 篡改 `pop` 的声明 sha | 同上（`preflight FAIL`） |
| P3 | `wrong_cols` | `LINKSTATS_EXPECTED_COLS = 153` | 同上 |

---

## §9 必需输出（**16 件**，全部落在 `reports/caliber_harmonization_7_9g2/`）

| # | 文件 | 内容 |
|---|---|---|
| 1 | `g2_face_matrix.csv` | 3 scope × 4 face 的**值** + `universe` + `face_role` |
| 2 | `g2_share_matrix.csv` | `share[face, scope ｜ Dk]`，含 `universe` + `denom_scope` |
| 3 | `g2_intensity_matrix.csv` | `s/link`、`s/km`、`s/veh` × 3 scope |
| 4 | `g2_universe_contrast.csv` | `U_any` vs `U_loaded` 逐面撕裂 + `>100%` 标记 |
| 5 | `g2_denominator_audit.csv` | 逐字段审计 G-0/G-1 既有 share 的 universe / denom / 可派生性 |
| 6 | `g2_concentration_curve.csv` | `f_t (t∈{50,90,99})` × 5 scope + `f_t(D0)` + 倍率 `R_t` |
| 7 | `g2_concentration_verdict.csv` | O5 判决 + 仪器声明（`instrument`、`k` 函数形式） |
| 8 | `g2_exposure_impact_gap.csv` | 四面份额极差 + 三档强度比 |
| 9 | `g2_reporting_template.md` | **物化模板句**（O9）+ 四面数值表 + 强度表 |
| 10 | `g2_caliber_crosswalk.csv` | 字段 → `face` / `universe` / `denom` / 继承来源（G-0/G-1/canonical）的映射 |
| 11 | `g2_verdicts.csv` | Q1–Q4（`question, verdict, rule, evidence`） |
| 12 | `g2_checks.csv` | 25 门（`gate_id, pass, detail`） |
| 13 | `g2_closure_check.csv` | 闭包表（**不得哈希自身**，记行数 + 逐件 sha） |
| 14 | `g2_input_manifest.json` | 5 件冻结输入 + 8 件对照物 + prereg 的 sha/bytes |
| 15 | `g2_summary.json` | `status` / `closure` / `gates_*` / 4 判决 / 关键实测值 / `noop_selfcheck_passed` / `prereg_sha256` |
| 16 | `STEP7_9G2_REPORT.md` | 人读报告（判决 + 实测 + 统一规则 + 模板） |

---

## §10 BLOCKED 触发条件（任一即 BLOCKED，且**必须完整物化终态**）

1. 任一冻结输入（§2）sha/bytes 不符；
2. 本文件（prereg）sha/bytes 与内嵌值不符；
3. linkstats 列数 ≠ 154 或必需字段缺失；
4. 任一对照物（§3）缺失或 sha 不符；
5. `U_any` 或 `U_loaded` 为空；
6. 出现 > 100% 的 share（门 10）；
7. 同一次比较内宇宙不唯一（门 09）；
8. 检出 `composite index` 或跨面求和（门 19）；
9. 集中度判据使用 Gini 或常数 `k`（门 20/23）；
10. 终局写盘回查或三方状态不一致（门 24）。

**BLOCKED 物化顺序（不得省略、不得用裸 `assert`）**：

```text
preflight FAIL → 门 FAIL → g2_checks.csv → g2_summary.json → g2_input_manifest.json
→ g2_closure_check.csv → STEP7_9G2_REPORT.md → EXIT = 1
```

---

## §11 版本与不变量

- **不变量**：`ROOT`、`SERVICE = "service"`、主窗 `8-9`、`canonical delay_corr_h`、
  宇宙/分母栈定义（O1/O2）、四面角色（O3）、阈值（§5 三阈值 + §4 三仪器常数）。
- 任一不变量变更 ⇒ **新版本** `PREREG_7_9G2_R2.md`，本文件标 `SUPERSEDED`。
- 本节点**不产生** `v1.1`：`Singapore_OD_MATSim_Final_v1.0` 及其判据均未被触及。
- **完成后**：`7.9G-2 = READY / CLOSED` ⇒ 再进入 **LTA 分车型 / HTS 出发时刻**。

---

## §12 本轮**不做**什么（显式负面清单）

- ⛔ 不重新判定 `A1–A6`、不新增机制假说；
- ⛔ 不修改、不"修正"、不回写 G-0 / G-1 的任何冻结产物；
- ⛔ 不重跑 MATSim、不改 `qsim.*`、不动 `service` 容量与端点吸附；
- ⛔ 不用 Gini 或常数 `k` 作集中度判据；
- ⛔ 不构造跨面总分、不给单一 headline（除非 §5 Q4 判为可采纳）；
- ⛔ 不做 `LTA` 分车型 / `HTS` 出发时刻（属下一节点）。
