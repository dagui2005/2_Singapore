# Step 4 — 道路网络与 332×332 最短旅行时间矩阵

**状态：PASS** ｜ 运行耗时 **1m39s** ｜ 生成时间 2026-09-11
脚本：`scripts/od/build_impedance.py` ｜ 输出：`reports/od_impedance/`

---

## 1. 建模链路（与冻结口径一致）

```
OSM Road (osm-lines_expanded.shp)
  → 机动车网络过滤 (13 类 highway)
  → 速度赋值 (OSM maxspeed → highway 默认)
  → 有向化 (oneway yes/-1/no)
  → 429,032 节点 / 706,554 有向边
  → Subzone 质心吸附到 giant SCC 内最近节点
  → scipy.sparse.csgraph.dijkstra (332 源)
  → C(332×332)
```

- **空间参考**：EPSG:3414 (SVY21)，节点按 0.1 m 网格合并
- **速度规则**：可解析的 OSM `maxspeed`（支持 km/h 与 mph）优先，缺失回退 highway 等级默认
- **方向规则**：`yes`→正向，`-1`→反向，`no`/空→双向；**未做强制作对称化**
- **离散化**：AM peak **静态 free-flow** 阻抗（无拥堵反馈；拥堵由后续 TrafficFlow 校准引入）

---

## 2. 本次为使其可运行/正确所做的 3 处修改

| # | 问题 | 处理 |
|---|---|---|
| 1 | 脚本 `import networkx`，但当前 conda 环境**未安装 networkx**；且纯 Python 实现在 42.9 万节点网络上不可行 | 改用 `scipy.sparse.csgraph.dijkstra`（C 实现，已装 1.17.1）；输出 schema 不变 |
| 2 | `oneway` 分支逻辑用 `edges[-1]` 回写判断，脆弱且 `-1` 方向处理含 IndexError 风险 | 改为显式三元分支：`yes→(u,v)`、`-1→(v,u)`、其他→双向 |
| 3 | 质心吸附到**弱连通分量**内最近节点：弱连通≠有向可达，实测 2 个 Zone 恰好吸附到单向死胡同节点，造成 **661 个不可达 OD** | 改为吸附到**最大强连通分量（giant SCC）**内最近节点 |

**验证列未错位**：`oneway`/`maxspeed` 两列与原始 `other_tags` 逐条比对，**168,580 条 0 处不符**，故 `oneway=yes` 占 46% 系真实 OSM 数据（新加坡大量干道为"上下行分离的单向车道"成对建图），非解析错误。

---

## 3. 路网审计（`network_audit.csv`）

| highway | features | 有向段 | 长度 km | oneway 占比 | maxspeed 覆盖 | 默认速度占比 | lanes 覆盖 |
|---|---:|---:|---:|---:|---:|---:|---:|
| motorway | 1,664 | 4,780 | 323.25 | 90.4% | 99.0% | 1.0% | 99.6% |
| trunk | 2,310 | 6,208 | 178.40 | 87.7% | 84.6% | 15.4% | 87.4% |
| primary | 12,910 | 25,821 | 847.87 | 97.9% | 99.2% | 0.8% | 97.8% |
| secondary | 9,216 | 19,806 | 547.66 | 96.3% | 97.8% | 2.2% | 95.8% |
| tertiary | 9,272 | 23,642 | 534.09 | 79.1% | 96.8% | 3.2% | 94.2% |
| residential | 32,340 | 121,521 | 1,590.76 | 40.0% | 96.3% | 3.7% | 91.9% |
| **service** | **89,906** | **460,548** | **5,158.36** | 27.1% | **3.6%** | **96.4%** | 48.9% |
| unclassified | 5,150 | 18,650 | 356.08 | 37.6% | 91.2% | 8.8% | 89.4% |
| motorway_link | 1,956 | 9,086 | 250.21 | 99.0% | 95.3% | 4.7% | 95.1% |
| trunk_link | 764 | 2,714 | 54.93 | 97.9% | 94.1% | 5.9% | 95.4% |
| primary_link | 1,803 | 8,087 | 102.03 | 99.7% | 92.8% | 7.2% | 92.2% |
| secondary_link | 769 | 3,492 | 37.76 | 99.4% | 86.0% | 14.0% | 83.8% |
| tertiary_link | 520 | 2,205 | 22.12 | 97.3% | 84.0% | 16.0% | 86.7% |
| **__TOTAL__** | **168,580** | **706,560** | **10,003.52** | **45.9%** | **46.8%** | **53.2%** | **69.7%** |

> ⚠️ **`service` 道路的 maxspeed 覆盖率仅 3.6%**：89,906 条 service 道（占要素 53%、占长度 51.6%）中 96.4% 使用默认 20 km/h。这是当前路网最大的速度不确定性来源，但它主要影响"最后一公里"接入（shortest path 主体走干道）。

---

## 4. 阻抗矩阵校验（`impedance_validation.json`）

| 指标 | 数值 |
|---|---|
| 网络节点 / 有向边 | 429,032 / 706,554 |
| 弱连通分量 / 强连通分量 | 84 / 2,507 |
| giant 弱分量占比 | 98.94% |
| giant 强分量占比 | **98.22%** |
| 有向边总长（含双向重复） | 15,524.6 km |
| Subzone 吸附中位 / p90 / 最大 | 26.2 m / 154.1 m / 6,339.5 m |
| **不可达 OD 对** | **0 / 110,224（reachable_rate = 1.000）** |
| 旅行时间 min / median / mean / max | 0.0 / **14.88** / 15.20 / **64.07** min |
| 距离 median / max | 15.22 km / 70.65 km |
| 隐含速度 median | **61.0 km/h** |
| 有向非对称比例 | 99.998% |

---

## 5. 合理性核验

**① 时间/距离/速度分位（非对角、可达）**

| 变量 | p1 | p5 | p25 | p50 | p75 | p95 | p99 |
|---|---:|---:|---:|---:|---:|---:|---:|
| travel_time_min | 2.63 | 4.75 | 10.14 | **14.90** | 19.54 | 27.15 | 35.35 |
| distance_km | 2.07 | 4.01 | — | 15.25 | — | 30.02 | 39.23 |
| implied_speed_kmh | 39.4 | 47.8 | — | **61.0** | — | 71.4 | 75.7 |

隐含速度全域落在 **20–83.5 km/h**，**0% 超过 90 km/h**，符合 free-flow 物理上限（网络最高限速 90）。

**② 非对称性** — 非对角对中 99.998% 满足 `c_ij ≠ c_ji`；差值中位 **28.1 s**、p90 82.2 s、最大 394.2 s。幅度不大但普遍存在，正是单行道网络的预期特征。对角 `c_ii = 0` ✓。

**③ 极值检查**

| 关系 | 耗时 / 距离 | 隐含速度 |
|---|---|---|
| CHANGI BAY ↔ TUAS VIEW EXTENSION（最长） | 64.07 min / 70.3 km | 65.8 km/h |
| SUDONG → CHANGI BAY | 62.39 min / 66.8 km | 64.3 km/h |
| PUNGGOL CANAL → CONEY ISLAND（最短非零） | 0.46 s / 6.4 m | 50.0 km/h |
| BOAT QUAY → CHINA SQUARE（CBD 内部） | 0.40 min / 0.33 km | 50.0 km/h |

横穿全岛 ~64 min / 70 km（free-flow）合理；CBD 内部短途 ~0.4 min 合理。

**④ SCC 修正的副作用 = 极小且可控**

| Zone | 名称 | v1(weak) 吸附 | v2(SCC) 吸附 | 变化 |
|---|---|---:|---:|---:|
| 141 | TANJONG RHU | 12.21 m | 13.67 m | +1.46 m |
| 204 | GHIM MOH | 43.60 m | 45.89 m | +2.29 m |

仅 **2 个 Zone** 换了吸附节点，**无一变化超过 20 m**，全局吸附中位数不变（26.2 m）。修正后 332 个吸附节点的入度/出度**均 > 0**。

---

## 6. 需要带入 Step 5 的 3 个已知限制

1. **free-flow ≠ AM peak**：本矩阵是无拥堵最短路。median 61 km/h 偏高是 free-flow 的固有结果。真正 AM peak 阻抗需在后续用 TrafficFlow（Zone 07，75,899 条 / 07:00–10:00 有 49,754 条）做拥堵反馈校准。Gravity 的 `λ` 应在该阶段一并标定。
2. **5 个"无机动车道路接入"Zone**：`NORTH-EASTERN ISLANDS`、`SOUTHERN GROUP`、`PULAU SELETAR`、`SEMAKAU`、`SUDONG` 为离岛，吸附到对岸最近道路节点（1.75–6.34 km），其 **3,295 个 OD 对** 的行程时间是几何外推的伪值。已在 `zone_network_snap.csv` 打 `no_road_access=True` 标记；Step 5 应将其与主岛 OD 分离处理（这些区多为零生产/零吸引）。
3. **service 道速度高度依赖默认值**：96.4% 的 service 道按 20 km/h 处理，对短途 OD 的末端时间有影响；如需精细，可在后续用 LTA `RoadSectionLine` 的 `RD_CATG__1` 修正。

---

## 7. 产物清单

| 文件 | 说明 |
|---|---|
| `network_links.csv` | 706,554 条有向边（from/to/travel_time/length/speed/highway） |
| `network_audit.csv` / `.json` | 分 highway 等级的路网审计（覆盖率） |
| `zone_network_snap.csv` | 332 Zone 吸附节点、吸附距离、节点入/出度、无道路接入标记 |
| `impedance_matrix.parquet` | **110,224 行** OD 阻抗（主交付物，7 列） |
| `impedance_matrix.csv` | 同上 CSV 版 |
| `impedance_validation.json` | 校验汇总 |
| `_v1_weakcomp/` | 修正前的弱分量版留档（用于量化 SCC 修正影响） |
| `STEP4_REPORT.md` | 本报告 |

---

## 8. 结论

$$
\boxed{P_i,\quad A_j,\quad C_{ij}\ \text{（AM peak 静态 free-flow）}\ \text{已全部就绪}}
$$

- `P_i` ← `reports/od_production/production.csv`（Step 2，Σ = 2,208,358）
- `A_j` ← `reports/od_attraction_v21/attraction_v21.csv`（Step 3B.1，逐 PA 守恒 1.89e-16）
- `C_{ij}` ← `reports/od_impedance/impedance_matrix.parquet`（**110,224 / 110,224 可达**）

**具备进入 Step 5：双约束 Gravity Prior OD 的全部数学输入。**

$$
T_{ij}^{prior}=\alpha_i\beta_j P_i A_j e^{-\lambda C_{ij}},\qquad
\sum_j T_{ij}=P_i,\quad \sum_i T_{ij}=A_j
$$
