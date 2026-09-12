# Step 7.3.2A — Motorway–Ramp Connectivity Audit
## 结论：PASS

本审计只检查 `network_cleaned.xml.gz` 对应的已冻结路网拓扑，不修改网络、OD、Population、lambda 或 MATSim 参数。

## 1. 网络规模
- 清洗后网络：**693,575 directed links**；节点按已知清洗结果 **421,406**。
- motorway：**4,744** 条；motorway_link：**9,026** 条。
- duplicate directed pairs：**0**。

## 2. 主线连续性
- motorway 主线没有相关上游 motorway/ramp 的边：**1 / 4744**。
- motorway 主线没有相关下游 motorway/ramp 的边：**0 / 4744**。
- 唯一异常主线端点为 **Airport Boulevard**，建议后续做一次人工/几何 spot check。

## 3. motorway ↔ ramp 连接
- motorway → motorway：**5,855** 条转移。
- motorway → motorway_link：**240**。
- motorway_link → motorway：**240**。
- motorway_link → motorway_link：**8,914**。
- 这一组对称连接说明快速路主线与匝道之间存在大规模、完整的有向接口，不支持“快速路主线整体断网”的假设。

- motorway+ramp 弱连通分量：**2**，最大分量占相关节点 **99.9691%**。
- 强连通分量：**6245**，最大强分量约占 **51.1%**；由于路网包含大量单向道路，强连通度不作为“全网应为一个 SCC”的验收条件。

## 4. Ramp terminal 结构
- motorway_link 共 **9,026**。
- 上游没有 motorway/ramp：**239（2.65%）**；主要直接连接 primary/trunk/secondary。
- 下游没有 motorway/ramp：**248（2.75%）**；主要直接连接 primary/secondary/trunk。
- 这类 terminal connector 是正常出入口形态，不应被自动判为错误。

## 5. 对 CATA/SLIP_ROAD 错配的判读

已有 7.2.2 与 7.3.1 实验表明 capacity-only 与拥堵反馈都不能显著改变 CATA/SLIP_ROAD 的相对结构。
本次拓扑审计又显示：

1. **motorway 主线连续性没有发现规模性断裂**；
2. **motorway↔motorway_link 接口大量存在且双向方向配对合理**；
3. ramp 与 primary/trunk/secondary 的端接主要呈现正常出入口结构；
4. 因而当前证据**不支持把 CATA 低估主要归因于“快速路/匝道网络断裂”**。

## 6. 下一步

不修改冻结网络。下一步应从“道路等级之间的路径使用”继续诊断：以实际 MATSim route/事件为依据，检查同一 O-D 是否过度使用 ramp、快速路是否因 route-choice generalized cost 被系统性排斥，以及 motorway_link 的速度/车道表达是否造成异常吸引。

## 7. 产物

- `motorway_ramp_transition_matrix.csv`
- `motorway_link_endpoint_diagnostics.csv`
- `motorway_endpoint_anomalies.csv`
- `motorway_ramp_class_summary.csv`
- `step7_3_2a_validation.json`