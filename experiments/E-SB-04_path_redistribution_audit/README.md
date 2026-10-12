# E-SB-04 —— 路径重分配与观测域流量增量审计

> 状态：**已完成**（2026-10-11）· 性质：**零仿真 · 只读**
> 协议：`PROTOCOL_E-SB-04.md` ｜ 判决：`reports/path_redistribution_audit_E_SB_04/VERDICT_E-SB-04.md`
> 门禁：阶段1+2 **24/24 PASS** ｜ 阶段3 **5/5 PASS**
> 上游：`E-SB-03 = A❌ / B✅(路径重分配) / C❌ / D❌`

## 一句话
**支持** `PATH_REDISTRIBUTION_SUPPORTED`（证据等级 = **plans**，由 v1.0 侧 plans↔events 一致率 **100%** 佐证）：
改 `freespeed` 后 **66.06%** 的 agent 计划路线改变，且一致地**向快速路倾斜**（motorway 路径里程占比 **+2.70 pp**），
与 E-SB-03 观测域流量增量在**走廊层面同序**（PIE 于两者均居首）。

⛔ **不得**裁为「已证实的实际路径重分配」——SB-A5/SB-A5ind **无 events**，执行路线未被直接观测。

## 关键实测
| 维度 | 值 |
|---|---|
| 路线变化率（SB-A5 vs v1.0） | **155,928 / 236,044 = 66.06%** |
| 道路等级路径里程占比 | motorway 44.56% → **47.25%（+2.70 pp）**；primary −1.56 pp、trunk −1.36 pp |
| 走廊路线使用率 | PIE +3.06 pp、CTE +1.77、AYE +1.73、MCE +1.63、TPE +1.17、KPE +0.98 |
| 三层级（08-09） | 断面 **+6.08%** / 匹配边 **+7.19%** / 全网 **−0.53%** |
| 走廊 ΔQ × 路线变化 | Pearson **0.74**，Spearman **0.67**（PIE 两者皆首） |
| plans↔events 保真 | **100.000%**（n=8,000，全部为 MATSim start_link 语义少首链） |
| 对向边同断面 | **0** ⇒ 方向性替代非主导 |

## 结论与证据等级
- **v1.0 与 SB-A5 需求同一**（共用 `population_lambda_0p075.xml.gz`）、网络拓扑逐位相同、**仅 `freespeed` 差 90,643 链**
  ⇒ 路线变化**可干净归因于 freespeed**。
- `SB-A5ind` 使用**不同 population** ⇒ 其 99.94% 路线变化含**需求变更**，只作独立参照。

| 机制 | 判决 |
|---|---|
| `PATH_REDISTRIBUTION_SUPPORTED` | ✅ 支持（plans 级） |
| `TEMPORAL_REALIZATION_SUPPORTED` | ⛔ BLOCKED（无两臂 events） |
| `OBSERVATION_MAPPING_EFFECT_SUPPORTED` | ❌ 不支持 |
| 与 `O3-R1 承载对象替代` | **分列**（观测对象替代 ≠ 车辆路径重分配） |

## 目录
```
PROTOCOL_E-SB-04.md                 预注册协议
VERDICT_E-SB-04.md -> reports/path_redistribution_audit_E_SB_04/
scripts/experiments/
  esb04_route_audit.py              阶段1 门禁 + 阶段2 路线结构（+ plans↔events 保真）
  esb04_section_decomp.py           阶段3 断面增量分解 / 对向·平行 link / 三层级
  esb04_verdict_render.py           阶段4 渲染判决书 + 机制评分卡
_cache/                             中间缓存（cls_*.pkl ~80MB/臂；routes_*.pkl ~1.15GB/臂）★不入 reports
```

## 复现
```bash
python scripts/experiments/esb04_route_audit.py       # 首跑 ~12 min；有 _cache 后 ~1 min
python scripts/experiments/esb04_section_decomp.py    # ~30 s
python scripts/experiments/esb04_verdict_render.py    # 秒级
```

## 口径
- 每 person 取 **`selected="yes"`** 的 plan；路线 = 该 plan 各 car leg 的有向 link 序列拼接。
- 道路等级/路名来自 `reports/matsim_network/network_links_source_copy.csv`；长度来自 `output_network.xml` 的 `length`（米，权威）。
- ΔQ 固定 E-SB-03 断面集合（576）/ 聚合（`median(匹配有向边 HRS8-9avg)`）/ `SCALE=2.29897`。
- ⛔ 未改 v1.0 / 网络 / population / OD / `freespeed` / `SCALE` / 阈值；未启动 MATSim。
