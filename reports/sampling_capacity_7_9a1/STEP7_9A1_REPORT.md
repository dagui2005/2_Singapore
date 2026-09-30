# Step 7.9A-1 报告 —— 采样一致性容量（sample-consistent capacity）单因子动态实验

> **判决：`SAMPLING_CAPACITY_NETWORK_BREAKDOWN`**
>
> 崩解护栏触发 ['A09']（§10） ⇒ 按 §7 情形 B 处置，⛔ **不把容量调回**。★子义消歧：本次触发的是 **流量层崩解护栏 `Sim/Obs < 0.85`**（实测 0.7664761），**不是**「`stuck` / `never_arrived`」的网络崩解子义（A-1 max `stuck_car` = 0、legHistogram 全天未到达 = 0.0000 %）⇒ §7 情形分类实为 **D**：情形 D：拥堵才变合理但流量指标恶化（sat_km ×6.37、N_cong ×1.89、Sim/Obs ×0.767） ⇒ 检查 OD assignment / flow scale / capacity / departure 耦合

> 本报告由 `scripts/od/audit_sampling_capacity_7_9a1.py` 从 `a1_summary.json` **自动渲染**，
> 所有数字均来自实测产物。**零仿真评价**；评价过程不改任何 MATSim 输入。

- 预注册：`PREREG_7_9A1.md` sha256 `de15361a09e764de626c68fa71d931c5ad073422419a05f940a5118e44a110f7`（运行前冻结，未修改）
- 评价器 sha256 `76243122b43400a3cd999a1432acf16329d31522ace67083af60eada0627dda4`
- 口径决议备忘：`CALIBER_RESOLUTION_NCONG.md`（`N_cong` 阈值歧义，双口径并报）

## 1. 本步回答了什么 / 没回答什么

**回答**：把 QSim 流量与存储容量按 population 表示比例 `1/SCALE` 缩放后，
① 全网拥堵是否出现**量级**变化；② 是否出现在**正确空间位置**（锚 7.3.6A 靶场）；
③ 是否呈现正常的**形成—消散**时间过程；④ 是否触发**崩解护栏**。

**不回答**：不重定 `λ / f_work / OD / 路网 / route-choice / 出发时刻`；
不回答「`0.434977` 是不是真实容量」；⛔ 不把本步结果写成「最优容量」。

## 2. 唯一结构变化（单因子、单点、不扫描）

| # | 参数 | v1.0 冻结 | A-1 | 性质 |
|---|---|---|---|---|
| 1 | `qsim.flowCapacityFactor` | `1.0` | **`0.434977`** | 模型 |
| 2 | `qsim.storageCapacityFactor` | `1.0` | **`0.434977`** | 模型 |
| 3–5 | `outputDirectory` / `runId` / `writeEventsInterval` | — | 输出层 | 非模型 |

`1/SCALE = 0.43497740292391807`；写入配置 6 位小数 `0.434977`。
全展开参数 diff **恒为 5 项**（含 `<parameterset>` 展开）。

## 3. §11 `CAPACITY` 语义消解

- 判定：**`BASE_CAPACITY`**（`identical=693575/693575`，
`ratio_match=0`）
- 有效容量乘子：v1.0 `×1.0`，A-1 `×0.434977`
- 交叉验证：`HRS8-9avg > CAPACITY_eff` 条数 = `501`（状态 `WARN_RULE_SUSPECT`）

## 4. 指标① 拥堵链路数（`N_cong` / `N_slow`，五口径 × 四长度 cut）

| 指标 | cut (m) | v1.0 | A-1 | 倍率 | 里程 A-1 (km) |
|---|---:|---:|---:|---:|---:|
| `n_cong` | 0 | 7,985 | 15,083 | ×1.889 | 368.801 |
| `n_cong` | 50 | 721 | 1,805 | ×2.503 | 158.513 |
| `n_cong` | 100 | 144 | 435 | ×3.021 | 65.345 |
| `n_cong` | 200 | 9 | 58 | ×6.444 | 15.516 |
| `n_slow` | 0 | 117,168 | 124,736 | ×1.065 | 1587.279 |
| `n_slow` | 50 | 1,174 | 1,839 | ×1.566 | 125.286 |
| `n_slow` | 100 | 17 | 163 | ×9.588 | 24.215 |
| `n_slow` | 200 | 2 | 23 | ×11.500 | 5.825 |

- **主判据口径**（`excess_s > 0`，= 预注册登记基线 7,985）：v1.0 `7,985` → A-1 `15,083`（×1.889）
- 辅口径（`excess_s ≥ 1.0`）：v1.0 `1,308` → A-1 `6,138`
- `N_slow`（`speed_ratio < 0.80`，**不依赖容量口径**）：cut0 ×1.065、cut50 ×1.566、cut100 ×9.588

## 5. 指标② `v/c` 与饱和

| 指标 | v1.0 | A-1 | 倍率 |
|---|---:|---:|---:|
| `n(v/c ≥ 0.5)` | 2,813 | 15,104 | ×5.369 |
| `n(v/c ≥ 0.9)` | 220 | 1,484 | ×6.745 |
| `n(v/c ≥ 1.0)` | 82 | 501 | ×6.110 |
| `n(v/c ≥ 1.5)` | 0 | 0 | ×inf |
| `n(v/c ≥ 2.0)` | 0 | 0 | ×inf |
| 饱和里程 (km) | 1.151420 | 7.337939 | ×6.373 |
| 饱和里程占比 | 0.000076 | 0.000485 | ×6.373 |
| 饱和链流量占比 | 0.002260 | 0.003892 | ×1.722 |
| `max v/c` | 1.000000 | 1.001695 | — |
| `Σ流量/Σ容量` | 0.093323 | 0.197867 | ×2.120 |

## 6. 指标③ 拥堵形成—消散（events，5-min bin，06:00–12:00）

| 量 | v1.0 | A-1 | 倍率 |
|---|---:|---:|---:|
| `max_t n_slow_links` | 30,706 | 37,917 | ×1.235 |
| 峰在途 | 36,176 | 63,706 | ×1.761 |
| 峰排队 | 57 | 73 | ×1.281 |
| 峰 stuck | 0 | 0 | ×nan |
| 峰 `aggV/C`(15min) | 0.102603 | 0.216183 | ×2.107 |
| 峰时刻 | `08:25` | `08:55` | — |

- 主判据（**3 倍**，PREREG §4.3 冻结）：`criterion = THREE_X`；`t_onset` = `09:20`，`t_clear` = `11:55`，`duration` = `155.0` min
- 次级敏感性（1.5 倍，⛔ 不替代主判据）：`t_onset` = `09:10`，`duration` = `165.0` min
- ★口径自校验：v1.0 峰 `aggV/C`(15min) = **0.102603** @`08:30` vs 7.7E E4 / A-0 §6 引用值 **0.102447**

[留痕] 原始配对差 `enroute_pair`（含 **+1/车** 结构性伪影）：v1.0 `236,039` / A-1 `236,039`；`enroute` 采用**在网车辆**口径，已与 legHistogram 交叉核对。

## 7. 指标④ 拥堵空间位置 + 7.3.6A 靶场锚定

靶场对账：crosswalk `3,193` 行 / 主候选 `3,158` 行 / 唯一断面 `574` / 唯一匹配链 `3,015`（预注册预期 ≈576 / ≈3,015）。

| 量 | v1.0 | A-1 |
|---|---:|---:|
| 拥堵链数 | 7985.0000 | 15083.0000 |
| 拥堵链里程 (km) | 163.9667 | 368.8005 |
| ∩靶场链数 | 123.0000 | 307.0000 |
| ∩靶场里程 (km) | 5.8153 | 15.2676 |
| `overlap_len_share` | 0.0355 | 0.0414 |
| `concentration_ratio`（全网上限分母） | 3.3770 | 3.9417 |
| `concentration_ratio`（载流链分母） | 1.1577 | 1.4123 |

- 读法（§4.4）：`3.942` ⇒ **拥堵**向靶场聚集**（位置可能对）**

### 分道路类别（A-1）

| RoadCat | 链数 | 里程 km | 流量 | 拥堵链 | 拥堵里程 km | 真实延误车时 | 饱和链 |
|---|---:|---:|---:|---:|---:|---:|---:|
| CATA | 1,020 | 85.3 | 1,371,398 | 81 | 5.997 | 162.7 | 0 |
| SLIP_ROAD | 1,995 | 73.6 | 639,095 | 226 | 9.271 | 245.2 | 0 |

## 8. 三层护栏

| run | 层 | 值 |
|---|---|---:|
| V1 | 08-09 FROZEN Sim/Obs | 0.9993347696792919 |
| V1 | POSITIVE_ONLY | 1.0873494259238392 |
| V1 | BEST_DIRECTION | 1.0383317484890895 |
| V1 | it.19 FROZEN | 1.0014525031000747 |
| V1 | 断面数 | 576 |
| V1 | 零流断面数 | 53 |
| V1 | §5① Pearson r | 0.3452 |
| V1 | §5① WMAPE | 0.7176 |
| V1 | §5① GEH 中位数 | 26.088 |
| V1 | §5① GEH<5 / 5-10 / ≥10（断面数） | 49 / 46 / 481 |
| V1 | §5① GEH<5 占比 | 0.0851 |
| V1 | §5① 口径断面数 | 576 |
| A1 | 08-09 FROZEN Sim/Obs | 0.7664760994478101 |
| A1 | POSITIVE_ONLY | 0.8161223869020577 |
| A1 | BEST_DIRECTION | 0.7996726734488973 |
| A1 | it.19 FROZEN | 0.7725115296237909 |
| A1 | 断面数 | 576 |
| A1 | 零流断面数 | 44 |
| A1 | §5① Pearson r | 0.4278 |
| A1 | §5① WMAPE | 0.4774 |
| A1 | §5① GEH 中位数 | 15.887 |
| A1 | §5① GEH<5 / 5-10 / ≥10（断面数） | 88 / 92 / 396 |
| A1 | §5① GEH<5 占比 | 0.1528 |
| A1 | §5① 口径断面数 | 576 |

★崩解护栏：`Sim/Obs(A-1) = 0.7664760994478101` **<** `0.85` ⇒ **★触发（FAIL）**；
★ 该护栏触发 ⇒ 判决取 `SAMPLING_CAPACITY_NETWORK_BREAKDOWN`（预注册 §10），但**读法按 §7 情形分类**（见 §1 判决行与 `CALIBER_RESOLUTION_BREAKDOWN.md` 的**子义消歧**）：本次是**流量层崩解**（断面级流量水平对不上），**不是** `stuck` / `never_arrived` 的**网络崩解**。
⛔ `Sim/Obs = 0.9993347697` **不是**本步目标；A-1 的 `Sim/Obs` **不得**被引用为对 v1.0 的标定证据。

★§5 ① 的 `Pearson r / WMAPE / GEH 分布` 由 `flow_quality()` 计算（全断面池化、含零流断面），门 `A09b` 断言其**确实产出**。
⚠ **留痕**：该三项在 2026-09-29 的**死代码审计前从未被任何代码计算过** —— `pearson()`/`geh()` 自写下起就一直未被调用，A-0 脚本第 683 行只是把这三个词写进了**前向描述字符串**。
  ⇒ 本轮将其**补齐**，⛔ 未改动 §5 ① 的任何阈值（硬门仍是 `Sim/Obs ≥ 0.85`）。

## 9. 与 A-0 §6 零仿真上界投影对照

| 指标 | v1.0 实测 | A-0 上界投影 | A-1 实测 | 投影倍数 |
|---|---:|---:|---:|---:|
| `n(v/c ≥ 1.0)` | 82 | 4,187 | 501 | ×51.06 |
| 饱和里程 km | 1.15142 | 178.114 | 7.337939000000003 | ×154.69 |
| `n(v/c ≥ 0.5)` | 2,813 | 16,049 | 15,104 | ×5.71 |
| `n(v/c ≥ 0.9)` | 220 | 5,413 | 1,484 | ×24.60 |

★ A-0 预先提示：即使按 sample-consistent 容量，峰 `aggV/C` 也只到 **0.236**、饱和里程只占 **1.18 %**
⇒ **仍不预期出现全网级拥堵波**。

## 10. 口径决议与留痕（⛔ 不改预注册）

1. **`N_cong` 阈值歧义**：预注册 §4.1 正文写 `excess_s ≥ 1.0`，但其登记基线 `7,985 / 3.56 %` 
   只能由 `excess_s > 0` 复现 ⇒ 双口径并报，主判据 = 登记基线。详见 `CALIBER_RESOLUTION_NCONG.md`。
2. **events 属性顺序**随事件类型而变（`entered link` 的 link 在 `tk[5]`，`departure` 的在 `tk[7]`）
   ⇒ 首版曾产出 `unknown_link = 161,380,248` 假值，已加硬门 `unknown_link == 0`。
3. **每辆车恰有 1 个未配对 `entered link`**（MATSim 末链不发 `left link`；实测 `n_pair_miss = 236,039`）
   ⇒ §4.3 对 `enroute(t)` 的**字面定义会产生物理上不可能的曲线**（峰 **236,039 @09:50** ≈ 全部车辆、
   随出发数单调增长）⇒ 改用**在网车辆**口径 `enroute = (#enters traffic − #leaves traffic) − |pending|`，
   字面口径保留为 `enroute_pair`。**交叉验证**：峰 **36,176 @08:55** vs 独立来源 `legHistogram.en-route`
   **36,799 @08:55** ⇒ **−1.69 %**（门 `B02` ±3 % 内，峰时完全一致）。影响 `acc_n` ≈0.29 %，两侧同源 ⇒ 相对判据免疫。
   ⇔ 详见 `CALIBER_RESOLUTION_ENROUTE.md`（本备忘为 `CALIBER_RESOLUTION_NCONG.md` 的姊妹件）。
4. **A-0 口径补齐**：`share_flow_on_saturated` 分母 = 全网总流量（v1.0 = 0.226 % 复现）；
   `peak_agg_vc_15min` = 7.7E E4 口径（`Σ rate / Σ capacity`，15 min bin）。
5. **出发/到达完整率（两口径，勿混用）**：**legHistogram 全天**口径下预注册 §10 字面要求
   `arrival == departure == 236,044` **成立**；但 **events 06:00–12:00 窗**口径会少 104 条
   `arrival`（落在窗外的迟到到达）⇒ 该窗口径不得用于完整性判据（见门禁 `A10/A10b/A11`）。
6. **★短链量化伪影 —— `N_slow` / `n_slow_links` 的绝对量不可直读**：指标① 的 `N_slow(cut)` 实测
   `cut=0 → 117,168`（占 `loaded` 224,432 的 **52.2 %**）→ `cut=50 → 1,174` → `cut=100 → 17` → `cut=200 → 2`
   ⇒ 绝对量的 **≈99 %** 来自 **`LENGTH < 50 m`** 的短链（全网中位段长 11.0 m、`service` 占 65 %）。
   机制：`timeStepSize = 1 s` + `TT = ceil(FF)` ⇒ 11 m / 13.9 m·s⁻¹ 的自由流链（`ff` 仅 **0.79 s**）
   一旦被记为 **2 s**，`speed_ratio` 立刻跌到 **0.40** ⇒ **短链上「多 1 秒」= 速度比腰斩**。
   ⇒ **`N_slow` 与 events 侧 `n_slow_links(t)` 只能读「A-1 相对 v1.0 的同口径倍率」，绝对条数**
   **⛔ 不得解释为拥堵规模**。这也解释了为何 v1.0 `N_slow(cut=0)` 高达 117,168 而饱和链路只有 82：
   `N_slow` **不度量拥堵**，只度量「未达自由流」。该危害由 §4.1 的 `cut ∈ {0,50,100,200}` 四档并列呈现。
7. **★死代码审计（本轮新增，两类真实缺陷）**：
   (a) `events_cached()` 曾**定义但从未被调用**（调用点于 2026-09-29 11:09 的缓存键重构中丢失）
   ⇒ 缓存与 `parser_fingerprint()` 双双失效、正式跑白付 ~20 min × 2；**已重接并用
   `scripts/od/prewarm_events_7_9a1.py` 逐位证明缓存往返无损**。
   (b) `pearson()` / `geh()` 曾**定义但从未被调用**，而预注册 §5 ① **明文要求** Pearson r / WMAPE /
   GEH 分布 ⇒ 该三项在 **A-0 与 A-1 均未实际产出**（A-0 脚本第 683 行只是把这几个词写进了**前向
   描述字符串**）⇒ 本轮以 `flow_quality()` **补齐**，门 `A09b` 断言其确实产出。⛔ 未改动任何阈值。
8. **`CATB` / `CATC` 不存在**：预注册 §4.4 第 4 条与 §5 ① 所列 `RoadCat ∈ {CATA, CATB, CATC, SLIP_ROAD}`，
   而冻结靶场 `RoadCat` 实测**仅** `CATA`/`SLIP_ROAD` ⇒ `CATB`/`CATC` 按**空集**处理（**非缺失门禁**）。
   与 `"CTE" in name` 命中 0 同类：**过度规定**，已在 `NOTES` 与本节显式声明。

## 11. 红线复述（逐条继承 A-0 / PREREG §8）

- ⛔ 不为了让 VIA 变红而提高 `demand`；
- ⛔ 不为制造拥堵而降低容量 / 修改 `λ` / 修改 route-choice；
- ⛔ 不为视觉效果重定义 congestion index；
- ⛔ **不把 `0.434977` 表述为「为了让新加坡堵起来把容量砍到 43.5 %」**。

★ 正确表述：**「由于模型 population 按 43.4977 % 样本表示完整交通需求，而 QSim 的流量与存储容量
采用未经 sample adjustment 的 1.0 倍容量，因此首先检验 sample-consistent capacity representation；
该因子由 population representation 独立推导，不由交通观测误差反演。」**

## 12. 复现

```bash
python scripts/od/run_sampling_capacity_7_9a1.py --run --heap 24g   # 点火（20 迭代）
python scripts/od/audit_sampling_capacity_7_9a1.py                 # 完整评价（本报告）
python scripts/od/audit_sampling_capacity_7_9a1.py --check-v10     # v1.0 侧口径自检
```

## 附录 A：口径与审计备注（NOTES，逐条来自实测）

1. 靶场对账：crosswalk rows=3193 / primary=3158 / 唯一断面=574 / 唯一链=3015；预注册预期 ≈576 断面 / ≈3,015 匹配链。
2. ★RoadCat 构成（primary）：{'SLIP_ROAD': 2112, 'CATA': 1046} ⇒ 预注册 §4.4 第 4 条与 §5 ① 原文所列 `CATB` / `CATC` 在**冻结靶场中均不存在**（`RoadCat` 仅 CATA/SLIP_ROAD）⇒ 按**空集**处理，**不是缺失门禁**；分组 ratio 按实际存在的 CATA/SLIP_ROAD 出。
3. ★死代码审计（本轮新增）：`events_cached()` 曾定义但从未被调用（调用点于 2026-09-29 11:09 的缓存键重构中丢失）⇒ 已重接；`pearson()`/`geh()` 曾定义但从未被调用 ⇒ 已由 `flow_quality()` 起用，以补齐预注册 §5 ① 的 Pearson r / WMAPE / GEH 分布。新增门 `A09b` 专防「预注册要求静默缺席」。
4. ★两份口径决议备忘（评价器侧，⛔ 预注册 sha `de15361a…` 一字未改）：① `CALIBER_RESOLUTION_NCONG.md` —— §4.1 `excess` 阈值文本缺陷（正文 `>=1.0` vs 登记基线 7,985 只能由 `>0` 复现）⇒ 双口径并报、主判据 = 登记基线；② `CALIBER_RESOLUTION_ENROUTE.md` —— §4.3 `enroute(t)` 字面定义结构性不自洽（末链不发 `left link` ⇒ 字面峰 236,039 @09:50 ≈ 全部车辆）⇒ 改用「在网车辆」口径，与独立来源 `legHistogram.en-route` 36,799 @08:55 相差 −1.69 %（门 `B02` ±3 %）。门 `A09c` 断言两份备忘均存在。
5. 护栏断面数（冻结模块返回）=576；本评价器 crosswalk 主候选唯一断面=574（差 -2），主候选唯一链=3015。
6. §5 ① 流量层质量（v1.0）：Pearson r=0.3452229341869945 / WMAPE=0.7175706050665775 / GEH 中位=26.0884178651379 / GEH<5=49、5-10=46、≥10=481（共 576 断面）。
7. 出发/到达完整率（两个口径，勿混用）：**legHistogram 全天** v1.0 未到达 = 0（0.0000 %）、A-1 未到达 = 0（0.0000 %）⇒ 预注册 §10 字面 `arrival == departure == 236,044` 在 legHistogram 口径下**成立**；而 **events 06:00–12:00 窗**会少 104 条 `arrival`（落在窗外的迟到到达）⇒ 该窗口径不得用于完整性判据。
8. ★判决口径消歧（预注册 §10 的子义分离；⛔ 未改预注册 sha `de15361a…`）：§10 的 `SAMPLING_CAPACITY_NETWORK_BREAKDOWN` 实际混装两类子义 —— (i) **流量层崩解护栏**（`Sim/Obs < 0.85`，门 `A09`）；(ii) **网络崩解**（`never_arrived` 或 `max_stuck_car` 超阈，门 `A10b`）。本次实测：(i) **触发**（A-1 = 0.7664761 < 0.85）；(ii) **未触发**（max `stuck_car` = 0、全天未到达 = 0.0000 %、dep = arr = 236,044）⇒ 判决取 `SAMPLING_CAPACITY_NETWORK_BREAKDOWN`，但其**读法应按 §7 情形 D**，而非字面「网络崩解」。⛔ 两种子义都**不**允许「把容量调回去」（§7 情形 B / §8 红线）。
9. ★实现缺陷修复（本轮；与 A03 同属「判决实现偏离冻结文本」类）：原 `hard_fail` 收录**全部** False 门 ⇒ 崩解护栏门 `A09` 失败时总判决恒为 `FAILED`，预注册 §10 的 `SAMPLING_CAPACITY_NETWORK_BREAKDOWN` 分支为**死代码**。现按 §10 分离 `BREAKDOWN_GATES = ('A09', 'A10b')`。⛔ 阈值未动（`GUARDRAIL_SIM_OBS` = 0.85）；⛔ 判据未动；⛔ 预注册未动。
10. ★`onset` 判据（预注册 §4.3）口径警告：`t_onset` = A-1 `n_slow_links(t)` **首次 ≥ v1.0 同一 bin 值的 3 倍**。v1.0 的 `n_slow_links` 在 07:00–08:55 基本**平台化**（≈2.9–3.07 万；短链量化伪影所致，见 §10 条目 6）⇒ A-1（峰值 3.79 万）在 07:00–09:00 内**根本达不到** 3 倍 ⇒ `t_onset = 09:20` **不代表拥堵自 09:20 才出现**，而代表「v1.0 曲线 09:00 后回落、A-1 仍高」的**交叉时刻**。⇒ 报告同时给出 1.5× 次级判据（`t_onset_1p5x`）；⛔ 不得把 `duration = 155 min` 读作『拥堵总时长』，它只是该交叉判据下的相对时长。

## 附录：门禁清单（含实测值）

| 门 | 名称 | 结果 | 实测 |
|---|---|---|---|
| `E01` | v1.0 it.19 linkstats 载入 | PASS | n_links=693575 |
| `E02` | v1.0 it.19 legHistogram 载入（5-min bin） | PASS | n_rows=362  span=0..108300 |
| `E03` | v1.0 复现 A-0 基线（82 / 1.151 km / 2,813 / 220） | PASS | n_ge1=82 sat_km=1.1514 n_ge0.5=2813 n_ge0.9=220 |
| `E04a` | v1.0 N_cong(cut=0, excess>0) == 预注册登记 7,985  ← 主判据 | PASS | 7985 |
| `E04b` | v1.0 N_cong_ge1s(cut=0, excess>=1.0) —— 预注册正文阈值（辅） | REC | 1308  （占比 0.5828%） |
| `E04c` | 口径决议：主判据 = excess>0（登记基线 7,985 / 3.56%），辅 = excess>=1.0（1,308） | REC | A-1 与 v1.0 同口径 ⇒ 相对判据不受影响；⛔ 不修改预注册（sha de15361a…） |
| `E05` | 观测 audit_trafficflow.csv 载入 | PASS | n_LinkID=1311 |
| `E06` | ★口径自校验：冻结模块复算 v1.0 Sim/Obs == 0.9993347697（±1e-6） | PASS | recomputed=0.9993347697  sections=576  零流=53 |
| `A01` | A-1 it.19 linkstats 载入且链路集与 v1.0 一致 | PASS | n_links=693575  ∩v1.0=693575 |
| `A02` | A-1 it.19 legHistogram 载入 | PASS | n_rows=362  max_stuck_car=0 |
| `A03` | A-1 运行契约门（verdict ∈ {PREPARED_AWAITING_RUN（跑前）, A1_RUN_COMPLETE 且 failed==[]（跑后）}） | PASS | verdict=A1_RUN_COMPLETE  n_checks=42  n_pass=41  failed=[] |
| `A03b` | A-1 预注册 sha 与 runner 登记一致 | PASS | de15361a09e764de626c68fa… |
| `A03c` | A-1 config diff 恰 5 项且全部白名单，qsim 两项 = 1.0→0.434977 | PASS | n_diff=5  n_qsim=2  keys=controller.outputDirectory,controller.runId,controller.writeEventsInterval,qsim.flowCapacityFactor,qsim.storageCapacityFactor |
| `A04` | §11 CAPACITY 语义已消解（三选一；空跑为 DRY_RUN_FORCED_EFFECTIVE） | PASS | mode=BASE_CAPACITY identical=693575/693575 ratio_match=0 |
| `A05` | §11 交叉验证：大量流量超有效容量 ⇒ 规则可疑（两版数字同时报出） | REC | n_over=501/235612 full_cap_over=0 |
| `C01a` | v1.0 events 链路 id 全部命中 linkstats（unknown == 0） | PASS | unknown=0 / lines=163,305,991 |
| `C01b` | v1.0 events 出发数 == 236,044 | PASS | dep=236,044  arr=235,940 |
| `C02a` | A-1 events 链路 id 全部命中 linkstats（unknown == 0） | PASS | unknown=0 / lines=178,131,265 |
| `C02b` | A-1 events 出发数 == 236,044 | PASS | dep=236,044  arr=230,803 |
| `B01` | ★口径自校验：v1.0 峰 aggV/C(15min) 复现 7.7E E4 = 0.102447（±2e-3） | PASS | recomputed=0.102603 @08:30 |
| `B02` | ★③ 在途曲线交叉核对：events 峰在途 ≈ legHistogram 峰 en-route_car（±3%） | PASS | events=36,176  legHistogram=36,799  Δ=-1.693% |
| `A06` | ③ 交叉核对 legHistogram：max stuck_car / max en-route_car | REC | v1.0 stuck=0 enroute=36,799 | A-1 stuck=0 enroute=69,357 |
| `A07` | VIA 属性层写出（行数 == 693,575） | PASS | rows=693575 |
| `A08` | 拥堵空间位置图写出（EPSG:3414） | PASS | 908478 bytes |
| `A09` | ★崩解护栏判据：Sim/Obs(A-1) >= 0.85 | FAIL | 实测 0.7664761 < 0.85  （v1.0=0.9993348） |
| `A09b` | ★预注册 §5 ① 三项（Pearson r / WMAPE / GEH 分布）已**实际产出**（非死代码） | PASS | missing=[]  rows=64  v1.0: r=0.3452229341869945 WMAPE=0.7175706050665775 GEH<5=0.08506944444444445  A-1: r=0.4277869591911868 WMAPE=0.4774346454164238 |
| `A09c` | ★报告引用的两份口径决议备忘均存在（§4.1 `excess` 阈值 / §4.3 `enroute`） | PASS | memos=['CALIBER_RESOLUTION_NCONG.md', 'CALIBER_RESOLUTION_ENROUTE.md']  missing=[] |
| `A09d` | ★§10 判决子义消歧备忘存在（BREAKDOWN 子义分离 + A03/A09 实现修复留痕） | PASS | memo=CALIBER_RESOLUTION_BREAKDOWN.md |
| `A10` | ③ 出发/到达完整率（legHistogram 全天合计） | REC | v1.0 dep=236,044 arr=236,044 未到达=0 (0.0000%) | A-1 dep=236,044 arr=236,044 未到达=0 (0.0000%) |
| `A10b` | ③ 崩解口径：A-1 未到达率 ≤ 1 % 且 ≤ 3×v1.0（legHistogram 全天口径） | PASS | A-1=0.0000%  v1.0=0.0000% |
| `A11` | ③ events 级完整率 | REC | dep=236,044 arr=230,803 leave_traffic=230,803 unknown_link=0 pair_net=236,039（结构性 +1/车 伪影） |
