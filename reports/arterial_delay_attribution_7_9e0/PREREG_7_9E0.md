# PREREG_7_9E0 — Arterial-Layer Delay Attribution Audit

**Step**: 7.9E-0  
**Scope**: zero-simulation, read-only structural attribution  
**Target question**: 在不修改冻结模型、也不重新运行 MATSim 的条件下，判断 `primary / secondary / tertiary` 干道层是否是当前 W01 off-mainline 运行时间与延误的主要承载层，并检查其与既有空间残差及主线耦合的关系。

## 1. 冻结边界

本步骤只读取既有文件，不修改：

- OD / population / departure profile
- MATSim network / capacity / route-choice / scoring / QSim config
- 7.3.6A final calibration crosswalk
- 7.6H W01 仿真输出
- 7.7C-0 / 7.7D 已冻结空间残差表

本步骤**不启动 MATSim，不调用 Java，不写入任何冻结输入文件**。

## 2. 固定输入

### 2.1 路网

优先使用：

`reports/matsim_network/network_links_source_copy.csv`

必需字段：

`from_node, to_node, length_m, highway, lanes, capacity`

允许用 `speed_kmh` 或 `travel_time_s` 提供自由流阻抗；若二者同时存在，优先使用 `travel_time_s`，并以 `length_m / (speed_kmh/3.6)` 做数量级校核。

### 2.2 W01 linkstats

仅使用冻结的 **7.6H W01 / it.19** linkstats。

必需字段：

`LINK, HRS8-9avg, TRAVELTIME8-9avg`

### 2.3 已有空间残差表

优先使用：

`reports/spatial_residual_7_7c0/c0_section_table.csv`

备用候选仅限已知 W01/7.7C-0 产物。

要求至少存在：

`lta_linkid, ratio_8_9, dominant_highway, length_m`

以及可用于空间分组的既有 `pa / region / radial / reciprocal` 字段（缺失时相应子检验标记为 BLOCKED，不得静默替代）。

## 3. 事先冻结的道路分组

### 3.1 arterial_core

固定为：

`primary ∪ secondary ∪ tertiary`

### 3.2 mainline

固定为：

`motorway ∪ motorway_link`

### 3.3 off_mainline

固定为所有 `highway ∉ mainline` 的有效路网 link。

### 3.4 辅助类别

保留：

`trunk, trunk_link, primary_link, secondary_link, tertiary_link, residential, service, ramp-like / connector-like, unclassified`

不将任何辅助类别事后并入 `arterial_core`。

## 4. 指标定义

### E1 — 时间归属

对每条 link：

`fftt_h = free_flow_time_s / 3600`

并统计：

`ff_time_share = Σfftt_h(class) / Σfftt_h(off_mainline)`

其中 `off_mainline` 以 §3.3 固定定义。

### E2 — 延误归属

对每条 link：

`delay_h = HRS8-9avg × max(TRAVELTIME8-9avg - free_flow_time_s, 0) / 3600`

统计：

`delay_share = Σdelay_h(class) / Σdelay_h(off_mainline)`

`delay_ratio = delay_share / ff_time_share`

注意：延误归属只用于描述“时间由谁承载”，不作为需求缩放或容量反推依据。

### E3 — 空间残差耦合

直接复用冻结的 7.7C-0 断面残差：

`residual = ratio_8_9 - 1`

不使用 W01 linkstats 的流量结果重新定义候选道路类别。

对 `arterial_core` 与非 arterial_core 做：

- residual 的均值/中位数/分位数；
- Spearman 相关（可用时）；
- 分层置换检验，优先按既有 planning_region / PA 层级保持规模结构；
- 既有 radial / reciprocal 交叉分组，如字段存在。

**不预注册“arterial 一定是 residual 主场”的方向。** E3 的作用是检验，而不是证明既定假设。

### E4 — 多跳 + 物理距离拓扑

对 `arterial_core` 每条 link，沿有向网络反向搜索其最近 `mainline`：

- 使用 link 的 `from_node` 作为 upstream seed；
- 多跳反向 BFS / Dijkstra；
- 距离累加 `length_m`；
- 默认搜索上限 3000 m；
- 输出 ≤300 m、≤1000 m、≤2000 m 的覆盖率。

只允许将 hop count 作为辅助输出；主要耦合距离必须以 m/km 报告。

若存在 node 坐标，则额外输出空间一致性检查；不得用几何直线距离替代拓扑距离作为主指标。

## 5. 预注册判读规则

### 5.1 不以单一“delay share 最大”判定主场

由于道路类别 base-rate 差异很大，必须同时报告：

`ff_time_share + delay_share + delay_ratio`

不得把一个类别由于面积/里程基数大而产生的高 delay share 直接解释为“异常富集”。

### 5.2 不以单一 residual 均值判定空间耦合

必须同时检查相关性与分层置换结果；若样本结构不能支持分层检验，则明确标记为 BLOCKED。

### 5.3 不把 arterial attribution 自动解释成容量错误

即使发现 `delay_ratio > 1`，也只得到：

> arterial 层是延误承载层。

不得直接推出：

> primary / secondary / tertiary 的容量赋值错误。

后者需要独立的容量合理性审计。

### 5.4 不修改模型

本步骤永远不产生 v1.1，不选择新的 `f_cap / SCALE / λ / service capacity / endpoint snapping`。

## 6. 固定输出

输出目录：

`reports/arterial_delay_attribution_7_9e0/`

至少包含：

- `e0_checks.csv`
- `e0_class_summary.csv`
- `e0_residual_coupling.csv`
- `e0_residual_permutation.csv`
- `e0_topology_summary.csv`
- `e0_input_manifest.json`
- `e0_summary.json`
- `STEP7_9E0_REPORT.md`

## 7. 硬门

1. PREREG 文件哈希与运行时文件一致。
2. zero-simulation：脚本不调用 Java / MATSim。
3. network 必需字段齐全且 `matsim_link_id` 唯一。
4. W01 linkstats 必需字段齐全且 `LINK` 唯一。
5. free-flow time 有效值比例 ≥ 99%。
6. arterial_core / mainline / off_mainline 固定集合非空。
7. 无任何输出反写冻结输入。
8. 7.7C-0 section table 可读取且至少 576 个断面。
9. `ratio_8_9` 有效样本数足以进行 E3；不足则 BLOCKED，不静默替代。
10. E4 使用多跳拓扑距离，不以单 hop 作为主结果。
11. 所有类别份额总和与母集合核算闭合（数值容差 1e-6）。
12. 输出 provenance 含输入路径、sha256、mtime 与脚本版本。

## 8. 结果状态枚举

- `ARTERIAL_LAYER_SUPPORTS_DELAY_ATTRIBUTION`
- `ARTERIAL_LAYER_NOT_PRIMARY_DELAY_ATTRIBUTION`
- `ARTERIAL_LAYER_EVIDENCE_MIXED`
- `ARTERIAL_LAYER_AUDIT_BLOCKED`

最终状态只能由审计结果产生，不能在预注册阶段预填。

## 9. 明确排除

本步骤不做：

- demand scale 重估；
- lambda 选择；
- capacity factor 调参；
- queue / kinematicWaves 切换；
- service 400 veh/h/lane 修改；
- endpoint snapping 修改；
- LTA 分车型数据替代；
- HTS departure profile 重建。
