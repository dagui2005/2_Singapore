# PROTOCOL — E-SB-06：信号灯/交叉口实验**可行性审查**（阶段1）

> 建立：2026-10-12 ｜ 性质：**零仿真、零改模型**（纯静态审计）
> 上游：7.9D0 `SIGNAL_MECHANISM_ABSENT`（2026-09-29）｜ E-SB-05 执行级证据（2026-10-12）
> 一句话：**在启动任何信号灯/交叉口仿真之前，先核验「有没有可信数据、模型是否真的用它、
> 能否复现、能否做独立对照」——四项全不满足，则不得启动实验。**

---

## §0 为什么先做可行性审查（而不是直接跑实验）

1. `E-CAP-01` 已表明：**粗粒度的全网容量缩放会压低流量、却让拥堵指标恶化**。
   不能因为 SB-A5 的 `Sim/Obs=1.0601`，就用信号灯/容量「修正」它。
2. `E-SB-04B` + `E-SB-05` 表明：`freespeed` 改变会**影响选路**并把流量重分配到观测路段。
   剩余偏差是否来自**路口延误/信号控制/交叉口连接建模**，需要**先判断**，不能默认归因于容量。
3. **信号灯与交叉口不得在同一实验内同时改**——否则无法分辨是哪一项起作用。

---

## §1 四点核验（任务书 §三）

| # | 问题 | 判据 |
|---|---|---|
| **Q1** | 项目当前网络是否已有**可靠的信号灯及交叉口资料**？ | 需同时具备：位置 + **配时** + **node/link 关联** + 官方自证元数据 |
| **Q2** | MATSim 配置是否**真正使用**这些设施？ | 网络含 `<signalSystems>` 且配置含 `signals` 模块 |
| **Q3** | 现有数据是否足以支撑**可复现的改变**？ | 缺任一项即不可复现 |
| **Q4** | 是否能设计**独立对照实验**？ | 只有在 Q1–Q3 满足后才有意义 |

---

## §2 门禁设计（★每条必携实测值；另设正/负例对照）

**语义**：本组为**可行性条件**门禁，`PASS` = **具备该条件**（不是"当前状态断言"）。

### A 组 · LTA 信号灯资料可用性
| ID | 判据 |
|---|---|
| A1 | LTA 信号灯资料存在且可解析（`shp` + `dbf`） |
| A2 | 字段非空且记录数 > 0 |
| **A3** | ★资料含**信号配时**字段（cycle / green / phase / split / offset…） |
| **A4** | ★资料含**节点/链路关联 ID**（可与网络对接） |
| **A5** | ★官方自证元数据（`*.shp.xml`）**完备**（非模板占位） |

### B 组 · MATSim 网络 / 配置就绪度
| ID | 判据 |
|---|---|
| **B1** | ★网络节点含 `type` 属性（可标记 signal/priority 交叉口） |
| **B2** | ★网络含信号定义（`<signalSystems>` / `SignalGroup`） |
| **B3** | ★配置含信号模块（`signals` / `trafficSignals`） |
| B4 | 配置启用车道级模型（`useLanes`） |

### C 组 · 发行版实现层（独立复核 7.9D0）
| ID | 判据 |
|---|---|
| **C1** | ★核心 jar 含**可经 config 启用**的信号实现类（ConfigGroup / Module / Plan） |
| C1b | （对照，informative）核心 jar 仅存**接口/桩/DTD 骨架**（存在 ≠ 可用） |
| **C2** | classpath（`libs/`）含 signals contrib |

### N 组 · 正/负例对照（防空门禁）
| ID | 判据 |
|---|---|
| N1 | （负例）类名检测器对**已知存在**的核心类应命中 ⇒ C1 有分辨力 |
| N2 | （负例）配时检测器对**构造的配时字段**应命中 ⇒ A3 有分辨力 |
| N3 | （负例）**朴素子串检 `Signalize`** 会命中接口/桩 ⇒ 证明必须区分「实现 vs 骨架」 |

> **★判据纪律（承接项目教训）**：
> - 门禁判据必须精确到「**可启用**」，而非类名**子串**。C1 初版即因朴素子串命中
>   `SignalizeableItem`（接口）/`DefaultSignalizeableItem`（桩）/`lightSignalSystems*.xsd`（DTD）
>   而**误判为「有实现」**（同项目**第 10 次假门禁**）。
> - ⛔ **不得以几何邻近替代缺失元数据**：LTA 信号灯点若无 node/link 关联 ID，
>   不得靠「最近的 MATSim 节点」硬接。

---

## §3 判决枚举

| 判决 | 触发 |
|---|---|
| `SIGNAL_CONTROL_FEASIBLE__READY_FOR_DESIGN` | A3∧A4∧A5 ∧ B1∧B2∧B3 ∧ C1∧C2 全满足 |
| `SIGNAL_CONTROL_NOT_FEASIBLE__DATA_AND_IMPLEMENTATION_GAP` | 数据侧与实现侧**双双**不足 |
| `SIGNAL_CONTROL_NOT_FEASIBLE__DATA_GAP` | 仅数据侧不足 |
| `SIGNAL_CONTROL_NOT_FEASIBLE__IMPLEMENTATION_GAP` | 仅实现侧不足 |
| `SIGNAL_CONTROL_NOT_FEASIBLE__NETWORK_UNPREPARED` | 数据/实现够、网络未准备 |

---

## §4 `DATA_ACQUISITION_GAP`（若要推进，缺什么）

| 缺口 | 需求 | 现状 |
|---|---|---|
| **D1 配时方案** | 交叉口级 cycle / phase / green split / offset | **缺失**（LTA 资料仅位置 + 方位角） |
| **D2 拓扑关联** | 信号灯组 ↔ MATSim node/link 的**权威映射** | **缺失**（资料无 ID） |
| **D3 官方自证** | 字段语义官方元数据 | `*.shp.xml` 为**模板占位** |
| **D4 实现支持** | 发行版含信号实现类且可由 config 启用 | **`SIGNAL_IMPL_NOT_ON_CLASSPATH`** |
| **D5 车道级** | `useLanes=true` + 转向/通行能力建模 | `useLanes=false` |

---

## §5 红线

⛔ 不启动信号灯/交叉口仿真；⛔ 不改任何模型参数（`SCALE`/容量/`freespeed`/λ/阈值）；
⛔ 不以几何邻近替代缺失元数据；⛔ 不因 `Sim/Obs=1.0601` 而用信号控制「调指标」；
⛔ 信号灯与交叉口不得同实验同改；`v1.0` / 原 SB-A5 / SB-A5_EVT19_CHECK 保持只读。

---

## §6 交付物

```
experiments/E-SB-06_signal_feasibility/
  PROTOCOL_E-SB-06.md  README.md
  audit/esb06_probe.json  audit/esb06_feasibility_gates.csv
reports/esb06_signal_feasibility/FEASIBILITY_E-SB-06.md
scripts/experiments/esb06_signal_feasibility_probe.py   （可复现）
```

## §7 复现命令

```bash
python scripts/experiments/esb06_signal_feasibility_probe.py
```
