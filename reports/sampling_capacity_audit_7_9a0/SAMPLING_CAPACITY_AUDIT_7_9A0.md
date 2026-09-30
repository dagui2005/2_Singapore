# Step 7.9A-0 采样—容量一致性审计（v1.0 冻结后，只读）

- 模型版本：**Singapore_OD_MATSim_Final_v1.0（未改动）**
- 定性：**7.9 第一阶段（结构审查）**，不是 7.8 的前置校准步骤
- 零仿真：**是**（未启动 MATSim）；参数改动：**否**；冻结件触碰：**否**
- 门控：**22/22 PASS**
- 判决：`SAMPLING_CAPACITY_CONSISTENCY_AUDIT_COMPLETE` → `SAMPLING_CAPACITY_INCONSISTENCY_CONFIRMED`

> 本步不解释「模型为什么不堵」，只回答两个更前置的问题：**当前容量的实际取值是什么**，
> 以及**对当前 population 而言它是否自洽**。结论只作为 `7.9A-1` 的准入证据。

## 一、四个实际生效值（用户指定核实）

| module | param | 值（v1.0） | 值（viz） | 生效? | 说明 |
|---|---|---|---|---|---|
| qsim | flowCapacityFactor | 1.0 | 1.0 | 生效 | 容量旋钮（生效） |
| qsim | storageCapacityFactor | 1.0 | 1.0 | 生效 | 容量旋钮（生效） |
| qsim | trafficDynamics | queue | queue | 生效 | 流出释放机制（生效） |
| qsim | timeStepSize | 00:00:01 | 00:00:01 | 生效 | 时间离散（生效） |
| hermes | flowCapacityFactor | 1.0 | 1.0 | 惰性 | 惰性（mobsim=qsim） |
| hermes | storageCapacityFactor | 1.0 | 1.0 | 惰性 | 惰性（mobsim=qsim） |
| dsim | trafficDynamics | kinematicWaves | kinematicWaves | 惰性 | 惰性诱饵（mobsim=qsim） |
| controller | mobsim | qsim | qsim | 生效 | 决定谁生效 |

- **f_flow = `1.0`**、**f_storage = `1.0`**（module = `qsim`，生效）
- **trafficDynamics = `queue`**（module = `qsim`，生效）
- **timeStepSize = `00:00:01`**（module = `qsim`，生效；7.7E 量化伪影的根因）

### ★ 两个必须记录的口径陷阱（否则本步数字会算错）

1. **`dsim.trafficDynamics = kinematicWaves` 是惰性诱饵。** 该参数位于 `dsim` 模块，而 `controller.mobsim = qsim`，
   因此 MATSim 根本不会读它。全配置里出现两次同名参数 ≠ 冲突；**判断生效性必须看 `mobsim`**。
2. **`hermes.*CapacityFactor` 也是惰性的**（同样因为 `mobsim=qsim`）。
   ⇒ 7.9A-1 的**唯一容量旋钮是 `qsim.flowCapacityFactor` / `qsim.storageCapacityFactor`**，
   不要动 `hermes`（保持 1.0，与 S100c 同构）。

四个值在 **权威 config / viz config / 两次 MATSim 运行期 dump** 四源逐位一致（A0.07）。

## 二、采样比例：一个必须排除的分母歧义

用户的推导式 `s = N_sim / SigmaEF` 会给出 **0.513369**，而目标值 `1/SCALE` 是 **0.434977**。
两者之比恒为 **1.180220 = f_work**，所以这不是误差，而是**分母选错**。

| 量 | 值 | 说明 |
|---|---|---|
| N_sim (agents) | 236044 | pop 文件 person 数 = 冻结 sim_agents |
| N_base | 200000 | 7.8 冻结采样基准 |
| f_work | 1.180222 | 工作点 = N_sim/N_base |
| SCALE (frozen) | 2.29897 | SigmaEF/N_base，作为扩样因子冻结 |
| SigmaEF (Census car-only anchor) | 459793.999993 | 需求锚，非流量扩样基准 |
| Q_repr = SCALE * N_sim | 542658.07468 | 被表示的等效真实车辆数 |
| s = N_sim / SigmaEF | 0.513369 | WRONG for capacity：与需求锚混用 |
| s = 1/SCALE | 0.434977 | CORRECT：capacity-consistent factor |
| ratio (naive/correct) | 1.18022 | 恒等于 f_work |
| Sim/Obs (frozen) | 0.999335 | 断言 F_real = SCALE*F_sim |

### 裁定：capacity 一致性因子 = `1/SCALE` = **0.434977**

量纲证明（与 `SigmaEF` 的定义**无关**）：

- `Sim/Obs = 1` 断言：`F_real = SCALE x F_sim`，即 `2.298970 x 236044 = 542658` 辆（需求总量口径）
- 要保持 `v/c_sim = v/c_real`，即 `F_sim / C_sim = F_real / C_real`
- 代入得 `C_sim = C_real / SCALE` ⇒ **`f_cap = 1/SCALE = 0.434977`**

**为什么 `N_sim/SigmaEF` 是错的**：`SigmaEF = 459,794` 是 **Census 2020 Table 104 `Car Only` 的需求锚**，
而模型实际在路网上表示的是 `SCALE × N_sim = 542658.1` 辆（= 1.180222 倍需求锚）。
工作点故意让 population 相对需求锚超采样 18.0222%，以弥合 7.6A 的 `CALIBER_GAP`（观测含非小汽车、全目的）。
拿需求锚当流量分母，会把一致性因子算成 0.513369（**偏高 18%，等于把容量少砍了 18%**）。

★ **稳健性**：`1/SCALE = N_base/SigmaEF`，**与工作点缩放无关** —— 即使 f_work 变化，
只要 SCALE 冻结，该因子不变。所以 A-1 的数值不依赖 f_work 的取值。

## 三、当前模型的物理含义（这是 7.7E 结果的机制解释）

- 236,044 辆仿真车 = 真实 **43.4977%** 的样本；
- 但 QSim 给它们的是 **100% 的真实容量**（`f_cap=1.0`）⇒
- 于是 **`v/c_sim ≈ 0.4350 × v/c_real`**：模型里的容量利用率被系统性压到真实值的 **43.5%**。

这正好解释了 7.7E 的观感：**流量可以对上（总量级），但容量竞争不足（状态）**。

## 四、零仿真预注册预测（A-1 的前置判据）

方法：把 it.19 冻结流量保持不变，只把 `CAPACITY` 乘 `1/SCALE`，重算 v/c。
⚠️ **这是「冻结流量一阶上界」**：不考虑排队导致的流量回落，因此**高估**饱和程度。

| 指标 | v1.0 实测 | A-1 预测（上界） | 倍数 |
|---|---|---|---|
| n_links_total | 693575 | 693575 | 1 |
| n_loaded_links | 224432 | 224432 | 1 |
| n_vc_ge_0p5 | 2813 | 16049 | 5.705297 |
| n_vc_ge_0p9 | 220 | 5413 | 24.604545 |
| n_vc_ge_1p0 | 82 | 4187 | 51.060976 |
| saturated_km | 1.15142 | 178.114371 | 154.691052 |
| agg_util_hourly | 0.052792 | 0.121368 | 2.29897 |
| peak_agg_vc_15min | 0.102447 | 0.235522 | 2.29897 |
| network_length_km | 15126.514665 | 15126.514665 | 1 |
| share_len_saturated | 0.000076 | 0.011775 | 154.691052 |
| share_flow_on_saturated_links | 0.00226 | 0.23329 | 103.246582 |

- 饱和里程占全网 **0.008% → 1.177%**（全网链路总长 15126.5 km）；
  处于饱和链路上的链路级流量占比 **0.226% → 23.329%**。
- 链路级容量超额求和 `Sum max(0, q - cap*f)` = **2401343 辆/h**。
  ⚠️ 该量沿路径**重复计数**，只用于相对比较，**不代表「无法出行的车辆数」**。
- ★ **空间尺度结论（预注册）**：即使按 sample-consistent 容量，饱和里程也只占全网 **1.18%**，
  峰 `aggV/C` 仅 **0.236** ⇒ **仍不预期出现全网级拥堵波**；预期改变集中在**局部瓶颈**。
- **方向性预测**：在途峰值 ↑（车辆滞留更久）、通过量 ↓、**`Sim/Obs` 预计下移**。
- ⛔ **关键预注册**：`Sim/Obs = 0.9993` 是 v1.0 的流量校准成果，**不得作为 A-1 的目标**；
  A-1 的流量门只是**崩解护栏**（`Sim/Obs >= 0.85`）。
- ★ **本投影即已提示**：峰 `aggV/C` 仅从 0.1024 → **0.2355**（仍远小于 1）
  ⇒ 若 A-1 实测与之一致，则主因更可能落在 **情形 C**（sample inconsistency 非主因）
  ⇒ 第二刀应转向 **7.9B `trafficDynamics`**，而不是回头继续压容量。

## 五、7.9A-1 执行计划（待批准；本步不执行）

- **唯一结构变化**：`qsim.flowCapacityFactor` `1.0` → **0.434977**；`qsim.storageCapacityFactor` `1.0` → **0.434977**
- **单点派生值，不做扫描**（0.35/0.40/0.45/0.50 扫描 = 参数拟合，已预注册排除）
- **完全不动**：OD、`f_work`、`lambda=0.075`、`SCALE`、population 236,044、route-choice R01、
  crosswalk 7.3.6A、network v1.0、departure realization W01、`randomSeed=4711`
- **新版本 v1.1**：新目录、新 runId；⛔ 不得改 `matsim_final_7_6h/`、`matsim_viz_7_8/`、`reports/final_model_7_8/` 任何文件
- **三层判据**：① 流量（崩解护栏 + CATA/SLIP/Pearson/WMAPE/GEH）② 拥堵形成（★扣量化后的真实 excess、
  饱和链路数与里程、走廊 excess、排队连通链长、峰 aggV/C、峰在途量）③ 数值稳定性（`A_10:19`、parity gap、
  `never_arrived`、`max_stuck_car`、departure/arrival 完整率）

### 四种结果的预注册读法

| 情形 | 判据 | 读法 | 动作 |
|---|---|---|---|
| A | 拥堵显著增强且流量基本保持 | v1.0 轻拥堵主因 = sample-capacity inconsistency | v1.1 = 表示尺度统一（非调参） |
| B | 拥堵增强但大量 stuck / 网络崩溃 | 方向对，但超细碎路网 storage/bottleneck 表达承受不了 | 转入 7.9B Network Bottleneck / Storage Structure（⛔ 不把 capacity 调回去） |
| C | 拥堵增强很少 | sample inconsistency 不是主因 | 第二刀 = trafficDynamics |
| D | 流量指标严重恶化而拥堵才变合理 | 既有断面流量校准可能依赖了错误的容量尺度补偿 | 检查 OD assignment / flow scale / capacity / departure concentration 耦合 |

### 红线（用户指定，逐条预注册）

- ⛔ 不为了让 VIA 变红而提高 demand
- ⛔ 不为制造拥堵而降低容量/修改 lambda/修改 route-choice
- ⛔ 不为视觉效果重定义 congestion index
- ⛔ 不把 0.434977 表述为『为了让新加坡堵起来把容量砍到 43.5%』

★ 正确表述：**「由于模型 population 按 43.4977% 样本表示完整交通需求，而 QSim 的流量与存储容量采用未经
sample adjustment 的 1.0 倍容量，因此首先检验 sample-consistent capacity representation；
该因子由 population representation 独立推导，不由交通观测误差反演。」**

## 六、本步自查

1. **分母歧义**：`N_sim/SigmaEF` 会给出 0.513369，与目标 0.4350 差 18.0222% —— 已定位为 f_work，已排除。
2. **惰性诱饵**：`dsim.trafficDynamics=kinematicWaves` 与 `hermes.*CapacityFactor=1.0` 均不生效；
   若不先看 `mobsim`，极易误判「当前动力学已是 kinematicWaves」。
3. **投影不是仿真**：第四节的数是**上界**，不能替代 A-1 实测；不得据此下结论。
4. **未触碰冻结件**：A0.22 对三个冻结目录做运行前后 mtime 快照比对，`changed=0`。

## 七、门控明细

| id | 判据 | 结果 | 细节 |
|---|---|---|---|
| A0.01 | 输入文件齐备 | PASS | missing=none \| n=14 |
| A0.02 | 有效 mobsim = qsim | PASS | controller.mobsim=qsim (n_modules=25) |
| A0.03 | qsim.flowCapacityFactor = 1.0（权威 v1.0 配置） | PASS | value=1.0 |
| A0.04 | qsim.storageCapacityFactor = 1.0（权威 v1.0 配置） | PASS | value=1.0 |
| A0.05 | qsim.trafficDynamics=queue 生效；dsim 同名参数为惰性诱饵 | PASS | qsim=queue (EFFECTIVE) \| dsim=kinematicWaves (INERT: mobsim=qsim) => 不得把后者当成当前动力学 |
| A0.06 | qsim.timeStepSize = 00:00:01 | PASS | value=00:00:01（7.7E 量化伪影 TT=ceil(FF) 的根因） |
| A0.07 | 四源一致：四个实际值在 权威cfg / viz cfg / 两次运行 dump 中逐位相同 | PASS | f_flow=['1.0', '1.0', '1.0', '1.0'] f_storage=['1.0', '1.0', '1.0', '1.0'] dyn=['queue', 'queue', 'queue', 'queue'] ts=['00:00:01', '00:00:01', '00:00:01', '00:00:01'] |
| A0.08 | hermes.*CapacityFactor 同为 1.0 但模块惰性 => 容量旋钮只在 qsim | PASS | hermes.flow=1.0 hermes.storage=1.0 ; mobsim=qsim 故 hermes 惰性（7.2.2 实测） |
| A0.09 | 人口文件 person 数 = 冻结 sim_agents = 236,044 | PASS | pop file=236044 \| FINAL_PARAMETER_FREEZE=236044 |
| A0.10 | SCALE = SigmaEF / N_base（逐位复现） | PASS | 459793.999993 / 200000 = 2.298970 ; 冻结 SCALE = 2.29897 |
| A0.11 | 需求锚 SigmaEF = 459,794 = Census 2020 Table 104 Car Only | PASS | sum_expansion_factor = 459793.999993 |
| A0.12 | s_sample(flow-consistent) = 1/SCALE = 0.434977 | PASS | 1/2.29897=0.434977 \| N_sim/(SCALE*N_sim)=0.434977（恒等） \| Q_repr=542658.1 |
| A0.13 | 分母歧义已定位：N_sim/SigmaEF 与 1/SCALE 之比恒为 f_work | PASS | N_sim/SigmaEF=0.513369 \| 1/SCALE=0.434977 \| 比值=1.180220 (f_work=1.180222, f_realized=1.180156) |
| A0.14 | 裁定：capacity-consistent 因子 = 1/SCALE = 0.434977（排除 0.513369） | PASS | 量纲证明：F_real=SCALE*F_sim 且 Sim/Obs=1 => C_sim=C_real/SCALE；SigmaEF 是需求锚，不是流量扩样基准 |
| A0.15 | 冻结 Sim/Obs 逐位复现（证明 SCALE 即实际生效的扩样因子） | PASS | SimObs_FROZEN = 0.9993347696792920 |
| A0.16 | f_cap=1.0 属 7.8 冻结参数 => A-1 必须升版 v1.1 | PASS | kind=capacity value=1.0 source=7.4 capacity freeze |
| A0.17 | 7.8 冻结门 23/23 且 verdict 记录（只读引用） | PASS | FINAL_MODEL_FROZEN_AND_REPRODUCIBLE ; 23/23 |
| A0.18 | v1.0 -> viz 配置 diff 仅 3 项白名单（只读引用） | PASS | diff=3 keys=['controller.outputDirectory', 'controller.runId', 'controller.writeEventsInterval'] |
| A0.19 | it.19 linkstats：7.6H 与 VIZ-RUN 逐位相同（扩样口径输入未漂移） | PASS | n_links=693575 bit_identical=True |
| A0.20 | 复现 7.7E 饱和链路数（82 条 / 1.15 km） | PASS | linkstats n(v/c>=1)=82 sat_km=1.151 \| 7.7E csv rows=82 |
| A0.21 | 复现 7.7E E4 峰值（agg_vc=0.102447 / 在途峰 36,799 @08:55） | PASS | peak agg_vc=0.102447 \| peak enr_car=36799 @08:55（note: E4 的 entries 是累计链路进入数，不是在途量 —— 首个版本曾误读） |
| A0.22 | 红线段：冻结目录零改动（零仿真 / 零写入） | PASS | changed=0 removed=0 n_files=212 |