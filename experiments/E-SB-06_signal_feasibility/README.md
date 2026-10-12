# E-SB-06 — 信号灯/交叉口实验可行性审查（阶段1）

> **一句话**：在启动任何信号灯/交叉口仿真**之前**，先核验「有没有可信数据 / 模型是否真的用它 /
> 能否复现 / 能否做独立对照」——四项**全不满足** ⇒ **不启动实验**。

- **性质**：`FEASIBILITY_REVIEW_ONLY / NOT_AN_EXPERIMENT / NOT v1.1`
- **零仿真**：本轮**未启动**任何 MATSim 运行，**未改**任何模型参数
- **上游**：7.9D0 `SIGNAL_MECHANISM_ABSENT`（2026-09-29）｜`E-CAP-01`｜`E-SB-04B`｜`E-SB-05`
- **协议**：`PROTOCOL_E-SB-06.md`

## 判决

### **`SIGNAL_CONTROL_NOT_FEASIBLE__DATA_AND_IMPLEMENTATION_GAP`**

| 侧 | 结论 | 关键实测 |
|---|---|---|
| 数据侧 | **不可用** | LTA `TrafficSignalAspect` 45,076 条**只有位置/方位角/层号**；**无配时、无 node/link ID**；`*.shp.xml` 为**模板占位**（23 个 `REQUIRED:`） |
| 网络侧 | **未就绪** | 网络 **421,407 节点无 `type`**；**无 `<signalSystems>`**；配置 **25 个模块无 signals**；`useLanes=false` |
| 实现侧 | **不可用** | 核心 jar **无可用信号实现类**（`SignalSystemsConfigGroup`/`Module`/`SignalPlan` = 0）；`libs/` 164 jar 无 contrib ⇒ **`SIGNAL_IMPL_NOT_ON_CLASSPATH`** |

⇒ **有效门禁 5/14 PASS**（A1/A2 + N1/N2/N3；N 为对照项）。

## 四点核验

| # | 问题 | 回答 |
|---|---|---|
| Q1 | 是否有可靠信号灯/交叉口资料？ | **不充分**（有位置、无配时、无关联、无自证） |
| Q2 | MATSim 是否真正使用？ | **否**（网络/配置均无信号设施） |
| Q3 | 数据是否足以支撑可复现改变？ | **否** |
| Q4 | 能否设计独立对照实验？ | **否（当前不可设计）** |

## ★ 自查修正：第 10 次「假门禁」

`C1` 初版用**朴素子串**（`SignalSystem`/`Signalize`）检「实现类」，命中
`SignalizeableItem`（**接口**）、`DefaultSignalizeableItem`（**桩**）、`SignalGroupState`（**状态**）、
`lightSignalSystems*.xsd`（**DTD**）⇒ **误判为「核心 jar 有信号实现」**。
修正为**区分「可用实现类 vs 骨架」**后 `C1 = FAIL`，与 7.9D0 一致；
`N3` 负例专门复现该误判机制。⇒ **门禁判据必须精确到「可启用」，而非类名子串**。

## 若要推进：`DATA_ACQUISITION_GAP`

D1 配时方案（缺）· D2 信号↔node/link 权威映射（缺）· D3 官方字段自证（模板占位）·
D4 发行版信号实现 + config 启用（`SIGNAL_IMPL_NOT_ON_CLASSPATH`）· D5 车道级 `useLanes`（false）。

⇒ 建议：**不启动** E-SB-06 完整实验；若推进，先做**数据获取（D1–D3）**与**实现路线裁定（D4–D5）**，
且**信号灯与交叉口拆为独立对照臂**。

## 目录

```
E-SB-06_signal_feasibility/
  PROTOCOL_E-SB-06.md  README.md
  audit/esb06_probe.json  audit/esb06_feasibility_gates.csv
reports/esb06_signal_feasibility/FEASIBILITY_E-SB-06.md
```

## 复现

```bash
python scripts/experiments/esb06_signal_feasibility_probe.py
```

## 红线

⛔ 不启动信号灯/交叉口仿真；⛔ 不改任何模型参数；⛔ 不以几何邻近替代缺失元数据；
⛔ 不因 `Sim/Obs=1.0601` 而「调指标」；`v1.0` / 原 SB-A5 / `SB-A5_EVT19_CHECK` 保持只读。
