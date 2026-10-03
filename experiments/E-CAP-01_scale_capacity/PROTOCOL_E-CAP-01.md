# E-CAP-01 —— 抽样需求—道路供给尺度统一试验（规程）

```
EXPERIMENT ONLY   /   NOT v1.1   /   NOT FORMAL BASELINE
NOT CALIBRATED MODEL   /   NOT SCIENTIFIC CONCLUSION
```

> **一句话定位**：不是修改 v1.0，不是新基线，不是校准结论，而是**给领导直观看**
> 「为什么当前模型会过于通畅，以及把需求与供给放到同一尺度后交通状态会发生什么」。
>
> **唯一任务**：检验「抽样需求—道路供给尺度一致性」是否能显著改变当前**过度通畅**的交通状态。

- 试验 ID：`E-CAP-01`
- 独立根：`experiments/E-CAP-01_scale_capacity/`
- 派生器 / 硬门：`scripts/experiments/ecap01_build_config.py`
- 冻结源：`matsim_final_7_6h/configs/config_W01_rc_min.xml`（sha16 `8f44fb349bff9cf1`）
- 生成配置：`experiments/E-CAP-01_scale_capacity/configs/config_E-CAP-01.xml`
- 状态：**✅ 已跑完（2026-10-01 22:21 → 2026-10-02 01:55，20 迭代，`rc=0`，用时 219.8 min）·
  运行前硬门 22/22 PASS · 运行后验收门 11/11 PASS · 逐位复现 `7.9A-1`（`Δ=+0.000e+00`）**

---

## §0 前置披露（★执行前必读）

### 0.1 本试验在物理上与 `7.9A-1 / A1_capf0p435` **完全等价**

本次派生完成后，实测对比结论：

| 对比 | 差异项 | 结论 |
|---|---|---|
| **E-CAP-01 vs `A1_capf0p435`** | **仅** `controller.outputDirectory` + `controller.runId`（均为输出层） | **模型层 0 差异** |
| E-CAP-01 vs v1.0 冻结配置 | 恰 **5 项**（2 模型 + 3 输出层） | 与规程声明一致 |

`A1_capf0p435` 是 **Step 7.9A-1**（`matsim_sampling_capacity_7_9a1`）在 **2026-09-29** 已实际跑完的 20 迭代运行，
`PREREG_7_9A1.md` 运行前冻结，唯一结构变化同样是：

```
qsim.flowCapacityFactor     1.0 -> 0.434977
qsim.storageCapacityFactor  1.0 -> 0.434977
```

⇒ **同网络（SHA16 `f55795995b87d330`）、同人口（`e96ed83ff59c0f5e`）、同种子（4711）、同线程（8）、同 20 迭代。**
⇒ 重新点火在数值上将**逐位复现** A-1，**不产生新信息**。

> **因此本规程有两种合法执行方式，请在 §15 结果已知的前提下选择：**
>
> | 方式 | 计算成本 | 产出 |
> |---|---|---|
> | **① 复用 A-1**（推荐） | **0**（结果已在盘上） | 直接进入 §8 领导展示包 |
> | **② 新建独立运行** | ≈ 2–3.5 h + ≈ 2 GB | 一个干净的 `experiments/…` 运行目录，**数值等同** |

### 0.2 A-1 的既有结论（已冻结，供对照）

判决 **`SAMPLING_CAPACITY_NETWORK_BREAKDOWN`**（§11 护栏 A09 触发），消歧后落 **情形 D**：
**拥堵才变合理，但流量指标恶化**。详见 §15。

### 0.3 本试验与项目封板状态的关系

- O3-R1 已 `CLOSED`；本试验**不重启 O3**，不改其任何结论，仅作**旁路演示**。
- ⛔ 本试验**不是**「观测尺度 × 残差」诊断的开启；§9.C 引用 576 残差对象是**读**，不是**重定义样本**。

---

## §1 试验目的

检验**单一尺度假设**：

> 当前 MATSim 使用约 **43.5%** 的抽样交通需求，但道路容量仍按 **100%** 完整尺度设置，
> 是否**系统性削弱拥堵形成**。

本试验**只回答**「需求抽样与道路供给是否需要保持同尺度」，**不用于**修改或替代正式 v1.0 模型。

---

## §2 独立性规则

**必须与正式 v1.0 完全旁路。** 试验目录单独建立：

```
experiments/E-CAP-01_scale_capacity/
├── PROTOCOL_E-CAP-01.md       ← 本规程
├── README.md                  ← 速览
├── configs/config_E-CAP-01.xml
├── outputs/E-CAP-01/          ← MATSim 输出（点火后生成）
├── logs/                      ← 运行日志
└── audit/                     ← 配置 diff 白名单 / 硬门结果 / mtime 快照
```

### 2.1 允许

- 复制 v1.0 配置与输入；
- 在副本中修改 QSim capacity 参数；
- 在独立输出目录运行 MATSim；
- 对实验结果单独做可视化与对比。

### 2.2 禁止（⛔ 任一违反 ⇒ `E-CAP-01 = INVALID`）

| # | 禁止项 |
|---|---|
| 1 | 覆盖 v1.0 输出 |
| 2 | 修改 v1.0 XML / 配置 |
| 3 | 修改原始 OD / plans |
| 4 | 修改 `TrafficFlow` 原始数据 |
| 5 | 修改道路等级 / Crosswalk / `signals` / `trafficDynamics` / `speedFactor` |
| 6 | 修改网络拓扑 |
| 7 | 修改路由规则 / 行为参数 / 评分函数 |
| 8 | 为了让结果「更像堵车」再次人工调容量 |
| 9 | 将本试验结果写入 v1.1 |
| 10 | 为展示效果增加额外迭代或改变行为模型 |

---

## §3 基准输入

除 §4 两项参数外，**全部继承 v1.0**。

### 3.1 需求

保持 `N_sim = 200,000`。不得重新抽样、不得更换随机种子、不得改变 OD 文件。

| 项 | 值 |
|---|---|
| plans 文件 | `matsim_final_7_6h/populations/pop_W01/population_lambda_0p075.xml.gz` |
| plans SHA16 | `e96ed83ff59c0f5e` |
| `f_work` / `λ` | `1.180222` / `0.0750` |
| `SCALE` | `2.29897` |
| 全量锚 `ΣEF` | `459,794` |
| 实际 agent 数 | `236,044` |

### 3.2 网络

| 项 | 值 |
|---|---|
| network 文件 | `reports/matsim_network/network_cleaned.xml.gz` |
| network SHA16 | `f55795995b87d330` |
| 坐标系 | `EPSG:3414` |

### 3.3 运行设置（全部保持 v1.0）

`randomSeed` `4711` · `numberOfThreads` `8` · `lastIteration` `19` ·
`replanning strategy` · `scoring` · `routing` · `qsim.timeStepSize` `00:00:01` ·
`qsim.trafficDynamics` `queue` · `qsim.linkDynamics` `FIFO` · `qsim.stuckTime` `10.0` ·
`linkStats.writeLinkStatsInterval` `1` · `travelTimeCalculator` · 其余 `controller` 参数。

---

## §4 唯一参数改动

### 4.1 Flow capacity

```
qsim.flowCapacityFactor = 0.434977
```

### 4.2 Storage capacity

```
qsim.storageCapacityFactor = 0.434977
```

理由：若只缩小流量容量而保留 100% 储车空间，**流量约束与排队储存空间仍不在同一抽样尺度**。

### 4.3 标定依据（现场可算给领导看）

$$
f_{cap}=\frac{N_{sim}}{N_{full}}=\frac{200{,}000}{459{,}794}=0.4349774\ldots
\;\Longrightarrow\;\text{写入 6 位小数 } \mathbf{0.434977}
$$

且 $f_{cap}=1/SCALE=1/2.29897$ —— **不是「看着合适」，而是尺度映射的直接结果**。

### 4.4 ⛔ 一个必须记录的细节：`hermes` 模块保持 1.0

配置中 `flowCapacityFactor / storageCapacityFactor` **各出现两次**：

| 模块 | 位置 | 本试验 | 理由 |
|---|---|---|---|
| `qsim` | 权威（`controller.mobsim = qsim`） | **`0.434977`** | 实际生效 |
| `hermes` | L133/L135 | **保持 `1.0`** | `mobsim=qsim` ⇒ hermes **不生效**（惰性），不得顺手改 |

⇒ 硬门 `M3` 专测此项。若未来有人 grep 到 `hermes` 里的 `1.0`，**这不是遗漏，是设计**。

---

## §5 参数变更表

| 参数 | v1.0 | E-CAP-01 |
|---|---:|---:|
| sampled trips | 200,000 | 200,000 |
| `SCALE` | 2.29897 | 2.29897 |
| **`qsim.flowCapacityFactor`** | **1.000000** | **0.434977** |
| **`qsim.storageCapacityFactor`** | **1.000000** | **0.434977** |
| `hermes.flowCapacityFactor` | 1.0 | 1.0（惰性，不动） |
| network | unchanged | unchanged |
| OD / plans | unchanged | unchanged |
| routing | unchanged | unchanged |
| scoring | unchanged | unchanged |
| trafficDynamics | unchanged | unchanged |
| signals | unchanged | unchanged |
| speedFactor | unchanged | unchanged |
| randomSeed / threads / lastIteration | 4711 / 8 / 19 | 4711 / 8 / 19 |

实验差异严格限制为：

$$
\boxed{\,f_{flow}=f_{storage}=1/SCALE=0.434977\,}
$$

---

## §6 运行规则

### 6.1 单次正式运行

只运行 `E-CAP-01 / seed = v1.0 seed`，**不做多随机种子平均**。
（第一目标是判断「尺度修正是否改变交通状态」，不是统计稳健性研究。）

### 6.2 禁止中途调参

运行过程中不得：修改 `capacityFactor` / `storageCapacityFactor` / network / OD / 迭代设置；
不得根据地图颜色提前停止；不得根据领导反馈再次调参。
**如果结果不好，原样保留。**

### 6.3 正式保留两套结果

`v1.0 baseline` 与 `E-CAP-01 experiment` **两套输出完整保存，不覆盖任何文件。**

---

## §7 输出解释规则

必须严格区分「**仿真运行量**」与「**展示量**」。

### 7.1 交通流量

MATSim 实际模拟的是 20 万抽样车辆。与完整观测量比较时：

$$
Q_{full}=Q_{sim}\times SCALE=Q_{sim}\times 2.29897
$$

**仅用于**：与 LTA 观测比较 · 流量专题图 · 道路流量统计。
⛔ **不得**用于重新计算仿真中的拥堵过程。

### 7.2 旅行时间 / 速度 / 排队 / 延误

⛔ **不得**乘 `SCALE`。这些是**交通运行状态**，不是车辆数量。

$$
TravelTime_{sim},\; Delay_{sim},\; Speed_{sim}\;\text{直接使用实验运行结果}
$$

### 7.3 观测段 ↔ 路网的比较口径（★强制）

LTA 观测段 ≈ **128 m** 与 MATSim 边 ≈ **67 m**（≈**1.9×**）**不是一对一**。任何与观测段比较：

$$
Q_{sim,g}=\sum_{l\in M_g}Q_l
$$

⛔ 禁止回退到「一条 LTA Link 对一条 MATSim link」的隐含假设。

---

## §8 领导展示建议

不展示几十个技术指标，只做「**同一场景、两版结果**」对照。

### 图 1 —— v1.0
**标题**：当前正式模型：抽样需求 + 完整道路容量
**表达**：> 只模拟了约 43.5% 的需求，但道路供给仍保持 100% 尺度，模型表现得偏通畅。

### 图 2 —— E-CAP-01
**标题**：尺度统一试验：抽样需求 + 同尺度道路容量
**表达**：> 需求抽取了 43.5%，道路承载能力同步按 43.5% 进入仿真，观察交通拥堵状态是否明显变化。

### 图 3 —— LTA 观测
独立参照图，展示真实观测流量空间格局。

⇒ 领导一眼看到：**现实 → v1.0 → 尺度统一试验**，而不是只看一张「漂亮地图」。

### ⛔ 展示用图的选择纪律

**主图不得使用 `speed_ratio` 红绿图。** 短链量化会把地图视觉上弄成「满屏红」，
**不能代表真实拥堵**。优先使用：

| 优先 | 指标 | 理由 |
|---|---|---|
| 1 | **按长度/流量聚合后的负荷**（`Σ流量/Σ容量`、饱和里程） | 与交通状态真正对应 |
| 2 | **旅行时间 / 延误**（`delay_s_per_km`） | 不依赖容量口径，抗伪影 |
| 3 | `v/c`（`load_vc`）按**长度加权**聚合 | 需声明长度切口 |
| ⛔ 避免 | 逐链 `speed_ratio` / `cong_ratio` 直接着色 | 短链量化伪影 |

---

## §9 判读标准

⛔ **不得以「地图看起来更堵」作为成功标准。** 至少观察四件事：

| # | 观察项 | 具体 |
|---|---|---|
| **A** | 拥堵是否从「全城过于通畅」中恢复 | 高流量主干路、高速、公路节点、典型拥堵走廊 |
| **B** | 高流量道路是否更易进入高负荷 | 高观测流量区域是否对应更高仿真负荷 |
| **C** | 区域残差是否系统性变化 | **仍用原来的 576 个正式残差对象**，⛔ 不得为试验效果重新挑样本 |
| **D** | 是否出现新的明显异常 | 大范围无意义拥堵 · 大量车辆无法到达 · 大量车辆卡死 · 异常高旅行时间 · 支路全面堵死 · 高速主线无负荷 |

---

## §10 「什么结果才算有意义」——三种合法结果

### 结果 A：交通状态明显改善
v1.0 过度通畅 · E-CAP-01 出现**集中而非全城式**拥堵 · 高流量走廊负荷增加 ·
区域残差同步改善 · 无运行异常。
⇒ 只能得出：**「需求—容量尺度不一致很可能是当前交通状态失真的重要原因之一。」**
⛔ **不能**直接宣布「模型正确」。

### 结果 B：拥堵出现了，但位置明显错误
⇒ **「容量尺度问题确实影响交通状态，但并不是唯一原因。」**
下一步回到 OD 分配 / 网络结构 / 其他机制层排查。

### 结果 C：即使尺度统一，结果仍明显失真
⇒ **「当前过度通畅不能仅由需求—容量尺度不一致解释。」**
停止继续调 capacity，转向其他机制层。

---

## §11 自动验收门（已实现，运行前 22/22 PASS）

派生器 `scripts/experiments/ecap01_build_config.py` 强制执行：

### 11.1 配置层（7 项）

| 门 | 内容 | 实测 |
|---|---|---|
| `A1` | 源配置 sha16 == 冻结值 | `8f44fb349bff9cf1` ✅ |
| `A2-*` | `qsim.*CapacityFactor` 命中唯一且旧值 1.0 | n=1 ✅ |
| `A3-*` | 3 项输出层参数全文件唯一 | n=1 ✅ |
| `A4` | `<param>` 标签总数不变 | 342 → 342 ✅ |
| `M1` | **全展开 diff 恰为 5 项白名单，非白名单 = 0** | diff=5 ✅ |
| `M2` | `qsim` 块内仅 2 个容量参数变化 | ✅ |
| `M3` | `hermes.*CapacityFactor` 保持 1.0 | ✅ |
| `M5` | seed/线程/迭代/network/plans/动力学/路由/评分逐位不变 | drift=NONE ✅ |

### 11.2 运行前硬门（§11，10 项全 PASS）

| 门 | 判据 | 实测 |
|---|---|---|
| `G-01` | 网络 SHA16 与 v1.0 相同 | `f55795995b87d330` ✅ |
| `G-02` | OD/plans SHA16 与 v1.0 相同 | `e96ed83ff59c0f5e` ✅ |
| `G-03/04` | 生效配置两个容量参数 == 0.434977 | ✅ |
| `G-05/06/07` | seed `4711` / threads `8` / `lastIteration 19` | ✅ |
| `G-08` | 输出目录为实验专属且不在 v1.0 内 | ✅ |
| `G-09` | **v1.0 目录 mtime 未变（冻结件 0 漂移）** | drift=NONE ✅ |
| `G-10` | 1/SCALE 与写入值自洽（< 5e-7） | `0.434977402924` ✅ |

### 11.3 运行后硬门（§11 剩余项，点火后核）

```
never_arrived == 0            # 不得有大量车辆无法到达
max stuck_car == 0            # 不得有大量车辆卡死
输出目录为实验专属目录
v1.0 文件 modification time 不变
```

⚠️ **注意**：`never_arrived` / `stuck` 为 0 **不代表试验成功** —— 7.9A-1 实测这两项均为 0，
但仍触发**流量层护栏**（`Sim/Obs < 0.85`）。二者是**不同子义**，不得混用。

**任一硬门失败 ⇒ `E-CAP-01 = INVALID`，不得解释交通效果。**

---

## §12 对领导的最终解释（建议表述）

> **「我们先没有改模型结构，也没有为了让结果看起来更像真实交通去人为调参数。
> 我们只是做了一个独立的尺度试验：现在实际只抽取了 43.5% 的车辆进入仿真，
> 所以把道路流量容量和储车容量也同步放到 43.5% 的尺度，看看交通拥堵是否恢复。
> 正式模型完全不动，这只是一个旁路试验，用来判断当前『过于通畅』
> 到底有多少是由抽样尺度造成的。」**

若结果改善，再补：

> **「这说明之前的结果偏通畅，至少有一部分可能来自需求和道路供给没有保持同一尺度；
> 我们还不会直接把这版认定为最终正确模型，还需要继续验证道路分布和交通状态。」**

---

## §13 版本定位

| 标记 | 值 |
|---|---|
| `E-CAP-01` | `EXPERIMENT ONLY` |
| | `NOT v1.1` |
| | `NOT FORMAL BASELINE` |
| | `NOT CALIBRATED MODEL` |
| | `NOT SCIENTIFIC CONCLUSION` |

唯一任务：**检验「抽样需求—道路供给尺度一致性」是否能显著改变当前过度通畅的交通状态。**

---

## §14 目录布局与运行命令

```
python scripts/experiments/ecap01_build_config.py                 # 派生 + 硬门（零仿真）
python scripts/experiments/ecap01_build_config.py --verify        # 只复核
python scripts/experiments/ecap01_build_config.py --run --heap 24g  # 点火
```

产物：`audit/ecap01_config_diff_whitelist.csv` · `ecap01_config_applied.json` ·
`ecap01_checks.csv` · `ecap01_v10_mtime_before.json` · `configs/config_E-CAP-01.xml`。

---

## §15 ★已知结果（来自 `7.9A-1 / A1_capf0p435`，已冻结）

因 §0.1 已证模型等价，**下表即为 E-CAP-01 若不改动任何输入时的预期结果**。

### 15.1 主判决

**`SAMPLING_CAPACITY_NETWORK_BREAKDOWN`** —— 触发护栏 **A09：流量层崩解 `Sim/Obs < 0.85`**（实测 **0.7664761**）。
消歧：**不是**「`stuck` / `never_arrived`」的网络崩解子义（`max stuck_car = 0`、全天未到达 `0.0000%`），
⇒ 分类落 **情形 D：拥堵才变合理，但流量指标恶化**。

### 15.2 关键对照

| 指标 | v1.0 | E-CAP-01（预期） | 倍率 |
|---|---:|---:|---:|
| `Sim/Obs`（08-09 FROZEN） | `0.9993347697` | **`0.7664761`** | ×0.767 ⚠️ |
| 拥堵链数 `n_cong`（cut0, `excess_s>0`） | 7,985 | **15,083** | ×1.889 |
| `n(v/c ≥ 0.9)` | 220 | 1,484 | ×6.745 |
| `n(v/c ≥ 1.0)` | 82 | **501** | ×6.110 |
| 饱和里程 (km) | 1.1514 | 7.3379 | ×6.373 |
| `max v/c` | 1.000000 | 1.001695 | — |
| `Σ流量/Σ容量` | 0.093323 | 0.197867 | ×2.120 |
| 峰在途车辆 | 36,176 | 63,706 | ×1.761 |
| 峰时刻 | `08:25` | `08:55` | — |
| 峰 `aggV/C`(15min) | 0.102603 | 0.216183 | ×2.107 |
| 拥堵∩靶场链数 | 123 | **307** | ×2.496 |
| 拥堵∩靶场里程 (km) | 5.8153 | 15.2676 | ×2.626 |
| `concentration_ratio`（载流链分母） | 1.1577 | **1.4123** | ↑ 向靶场聚集 |
| `t_onset` / `t_clear` / `duration` | — | `09:20` / `11:55` / **155.0 min** | — |
| `max stuck_car` / 未到达 | 0 | **0 / 0.0000%** | 网络未崩解 |

### 15.3 读法（⛔ 不得越界）

1. **拥堵确实出现了，而且不是全城式** —— 倍率集中在中高负荷段（`v/c≥1` ×6.11），
   且 `concentration_ratio` **升到 3.942**（全网上限分母）⇒ 拥堵**向观测靶场聚集**，**位置不像是错的**。
2. **但流量对账被破坏** —— `Sim/Obs` 从 `0.9993` 掉到 `0.7665`，全网 `Σsim −23.30%`。
   ⇒ **统一削容量会同时压低全网流量**，这不是可以直接采纳的修正。
3. ⇒ 对领导的诚实结论应是 **§10 结果 B/C 的混合**：
   **「尺度不一致确实系统性压低了拥堵水平（机制成立）；但它不是充分解释，均匀缩放会过校正。」**

### 15.4 ⛔ 从 7.9A-1 继承的判读红线

- **流量校准成功 ≠ 拥堵状态校准**（v1.0 `0.9993` 是「大额正负抵消」后的结果）。
- ⛔ **不得**写作「为堵砍容量」；**变堵 ≠ 堵得对**。
- ⛔ **不得**把 `1/SCALE` 的结果宣称为「最优容量」或「真实容量」。
- ⛔ **不得**把本试验结果写入 v1.1 或任何正式基线。

---

## §16 边界

- 本试验属**演示/旁路**，与已 `CLOSED` 的 O3-R1 科学闭环**严格隔离**。
- ⛔ 不改 v1.0 / crosswalk / `TrafficFlow` 原始值 / 评价器阈值 / `signals`·`trafficDynamics`·`speedFactor`。
- ⛔ 不产生 v1.1；不改 `MEMORY.md` 的封板结论。
- ⛔ 不因结果显著就把「尺度相关」解释成「交通动力学机制」。

---

## §17 ★运行后实际结果（2026-10-02 固化）

### 17.1 运行与验收

| 项 | 实测 |
|---|---|
| 点火 → 结束 | `2026-10-01 22:21:08` → `2026-10-02 02:00:51`（`rc=0`，**219.8 min**） |
| 运行前硬门 | **22/22 PASS** |
| **运行后硬门** | **11/11 PASS**（`P-01`…`P-08b`，见 `audit/ecap01_postrun_gates.csv`） |
| `never_arrived` / `max stuck_car` | **0 / 0**（legHistogram 全天口径） |
| CAPACITY 语义 | `BASE_CAPACITY` ⇒ `cap_mul = 1/SCALE = 0.434977` |
| 与 `7.9A-1` 对账 | `Sim/Obs(cycle)` `Δ = +0.000e+00`；`Sim/Obs(it.19)` `Δ = +0.000e+00` ⇒ **逐位复现** |
| 冻结件漂移 | `drift = NONE`（v1.0 目录 mtime 未变） |

> ⚠️ `DumpDataAtEndImpl` 在 shutdown 报 4 条 `ERROR`（trips/legs/activities/experienced_plans
> 未生成）——因 `writeExperiencedPlans` 类开关未开，**与 v1.0 同配置行为**，非致命。

### 17.2 实测结果（= §15.2 预期，逐项复现）

见 `audit/ecap01_postrun_metrics.json` 与 `DEMO_ONE_PAGER.md` §二。主判决仍为
**`SAMPLING_CAPACITY_NETWORK_BREAKDOWN`**（流量层护栏 `Sim/Obs < 0.85`，实测 `0.7664761`），
分类 **情形 D**；全文判读见 `DEMO_ONE_PAGER.md` §三，红线同 §15.4 不变。

### 17.3 产物

```
audit/ecap01_postrun_metrics.json      # 全量实测 + 门禁 + 护栏
audit/ecap01_postrun_gates.csv         # 11/11 门禁
audit/ecap01_postrun_comparison.csv    # v1.0 vs E-CAP-01 对照
audit/_cycle_linkstats/                # it.10–19 周期均值（护栏口径，实验专属）
audit/_guardrail_cache/                # 冻结模块护栏缓存（实验专属）
figures/fig1_load_grid_v10_vs_ecap.png # 主图：1 km 网格负荷（Σ流量/Σ容量）
figures/fig2_lta_observed_map.png      # 现实：LTA 观测
figures/fig3_metrics_ratio_bars.png    # 倍率柱
DEMO_ONE_PAGER.md                      # 领导判读一页纸
logs/ecap01_postrun.log · ecap01_demo_figs.log
```

> **执行方式说明**：本试验最初按 §0.1「方式②」点火；首跑被本环境长任务约束外部终止，
> 经 `run_in_background=true` 重跑**一次完成**（未改任何输入）。同时 §0.1「方式①复用 A-1」
> 仍是 0 成本等价路径，二者**数值逐位一致**。
