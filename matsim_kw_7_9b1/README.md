# matsim_kw_7_9b1 — Step 7.9B-1：唯一变量 `queue -> kinematicWaves`

> **这是 7.9 结构性修复链的第一刀实验**：在 `f_cap=1.0` 下**只切换交通动力学机制**，
> 其余全部逐位继承 `Singapore_OD_MATSim_Final_v1.0`。⛔ **不是**新标定、⛔ 不回灌 v1.0。
> ⛔ **不与 7.9A-1（sample-consistent capacity）合并**。

## 唯一模型改动（1 项）

| 参数 | v1.0 冻结值 | 本目录值 | 性质 |
|---|---|---|---|
| `qsim.trafficDynamics` | `queue` | **`kinematicWaves`** | ★**模型层（本步唯一意图）** |

`dsim.trafficDynamics` 本来就是 `kinematicWaves`，但 `controller.mobsim=qsim` ⇒ **dsim 惰性**，
本步**未触碰** dsim（它是同名不同 module 的经典诱饵）。

## 输出层改动（3 项，不进入动力学）

| 参数 | v1.0 冻结值 | 本目录值 | 性质 |
|---|---|---|---|
| `controller.outputDirectory` | `...\matsim_final_7_6h\outputs\W01_rc_min` | `...\matsim_kw_7_9b1\outputs\W01_kw` | 输出层 |
| `controller.runId` | `W01_rc_min` | `W01_kw` | 输出层（仅文件名） |
| `controller.writeEventsInterval` | `0` | `19` | 输出层（复现 7.7E 的 07–09 时段指标） |

其余 214 个参数（含 `<parameterset>` 全展开）取值逐位相同，见 `audit/b1_config_diff.csv`。

## 继承的 v1.0 条件（冻结）

`flowCapacityFactor=1.0` / `storageCapacityFactor=1.0` / `SCALE=2.29897` /
`lambda=0.075` / `f_work=1.180222` / `N_sim=236,044` /
route-choice `R01_rc_min` / `stuckTime=10` / `removeStuckVehicles=false` /
network / OD / crosswalk / seed / departure = 冻结。
`qsim.inflowCapacitySetting` **未显式覆盖** ⇒ MATSim 默认 **`INFLOW_FROM_FDIAG`**（KW 的入口上限由此生效）。

## 判读纪律（用户冻结口径）

本步必须**分开**判定两件事：
1. **`kinematicWaves` 改变了拥堵传播机制** —— 有仿真结果即可验证；
2. **`kinematicWaves` 让拥堵位置更接近真实结构瓶颈** —— 必须同时得到 **7.9C-0 的 C3/C4 空间证据**支持。

⇒ **成功 ≠ 「比 queue 更堵」**；成功 = 「在稳定性不过关的前提下，不仅产生动力学差异，
而且这种差异具有**可解释的空间结构**」。其余三层解释见 `reports/structural_.../` 与
`audit/` 下的分析产物。

## 纪律

- ⛔ 不改 `matsim_final_7_6h/` 下任何文件（14 件冻结输入跑前后 mtime + sha256 逐位未变）；
- ⛔ 不改 f / λ / SCALE / f_cap / route-choice / 人口 / 路网；
- it.0 的 events 是**未收敛路线**的流量、非最终模型，跑完即删；
- ⛔ 本目录产物**不得**回灌 v1.0（`Sim/Obs` 冻结值仍为 `0.9993347697`）。
