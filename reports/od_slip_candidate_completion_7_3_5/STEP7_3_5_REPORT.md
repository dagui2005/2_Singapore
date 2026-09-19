# Step 7.3.5 — SLIP_ROAD Candidate Geometry Completion

## Status

**PASS** — 零仿真；不修改 OD / λ / Population / Departure Profile /
MATSim Network / Capacity / Route Choice，也不改动 7.1 冻结靶场。

输入：`TrafficSpeedBands_Links.shp`（LTA 独立几何，5,207 条
RoadCat=6 SLIP link）+ `network_links_source_copy.csv` +
`network_nodes_source_copy.csv` + 6.3.2 tight crosswalk。

## 0. 两个口径（必须区分）

| 口径 | 含义 | 断面数 |
|---|---|---:|
| **FULL** | TrafficSpeedBands_Links 中全部 `RoadCat=6` slip link | **5,207** |
| **CORE** | 同时是 LTA 检测器断面（TrafficFlow / 6.3.2 crosswalk）的 slip | **251** |

> 7.3.4 的缺口只在 **CORE** 口径下有意义；FULL 中其余 4,956 条
> 是 LTA 全网几何里**不参与流量校准**的匝道，因此**恢复率以 CORE 为准**，
> FULL 仅作背景。

## 1. CORE 覆盖（主判据）

| 阶段 | 有 candidate | 覆盖 |
|---|---:|---:|
| 旧 6.3.2 crosswalk 含 motorway_link | 138 | 54.98% |
| 新几何（≤80 m）含 motorway_link | 250 | 99.60% |
| 新几何 · 仅同向（±30°） | 248 | 98.80% |
| 新几何 · 仅同名 | 73 | 29.08% |
| 新几何 · 同向 + 同名（strict） | 62 | 24.70% |

- 旧缺口（无 motorway_link）：**113** / 251（45.02%）
- 几何补回：**112**（**占旧缺口 99.12%**）
- 仍缺失：**1**

## 2. FULL 覆盖（背景）

- FULL slip：**5,207**
- 新几何含 motorway_link：**2,498**（47.97%）
- 说明：FULL 包含**非快速路的普通道路匝道**，其附近本就没有 motorway_link，
  故 48% 属正常背景，不构成反证。

## 3. 候选几何

- search radius：**80 m**（line-to-line 真实距离）
- direction threshold：**±30°**
- core candidate rows：**4,765**
- strict rows：**2,342**
- tier 分布（core）：{'geometry_only': 2438, 'direction_only': 1784, 'direction+name': 328, 'name_only': 215}
- 补回断面“任一 motorway_link”最近距离中位：**0.0 m**

## 4. 半径敏感性（CORE）

```
 radius_m  sections_with_candidate  coverage  recovered_of_missing  recovery_rate_of_missing  strict_sections
     50.0                      249  0.992032                   111                  0.982301               59
     80.0                      250  0.996016                   112                  0.991150               62
    120.0                      250  0.996016                   112                  0.991150               70
    200.0                      250  0.996016                   112                  0.991150               75
```

> 结论：**50 m 时已补回 98.2%**，放大到 200 m 不再增加 → **半径不是瓶颈**。

## 5. 关键证据：最近「同向」匝道距离

对每个 CORE 断面，取**方向一致**（±30°）的最近 motorway_link：

```
 radius_m  sections    share
      5.0       232 0.935484
     10.0       237 0.955645
     20.0       244 0.983871
     30.0       244 0.983871
     50.0       247 0.995968
     80.0       248 1.000000
```

- 最近同向匝道距离：中位 **0.00 m**，均值 **1.64 m**
- **≤5 m：232/248（93.55%）**
- ≤20 m：244/248（98.39%）

> 匝道几何**几乎逐条重合**（大量距离 = 0 m），说明 LTA SLIP 断面在
> OSM/MATSim 网络中**确有对应 `motorway_link`**，旧 crosswalk 只是没选到。

## 6. 仍缺失断面

```
LinkID            RoadName  old_ml_edges
 48170 TAMPINES EXPRESSWAY             0
```

- 唯一仍缺失：**['48170']**
- 说明：该断面最近 `motorway_link` 在 **~227 m** 之外，其近邻是 **`motorway` 主线**
  （TAMPINES EXPRESSWAY，距离 0 m）→ 属于**单点真实几何缺口**
  （0.40%），不影响整体判定。

## 7. 与 7.3.4 的对账（113 vs 117）

- 7.3.4 报“117/251 缺 motorway_link”，是在其 **`rebuilt_crosswalk.csv`
  （已约简边集，6,008 行 / SLIP 1,103 行）** 上统计的；
- 本步以**冻结的 6.3.2 tight crosswalk（13,163 行 / SLIP 2,933 行）** 为基座，
  得 **138 有 / 113 缺**；差异 4 个断面（45102/47200/48993/49474）
  因 rebuild 边集缩减而失真。
- 两套口径的 `highway` 标签与网络完全一致（0 处不符），故 **113 为权威缺口**。

## 8. 判读（A / B / C）

- **A. 大量补回** → 旧 crosswalk 候选搜索机制不足为主因。
- **B. 少量补回** → 部分是 crosswalk 机制、部分需动 network representation。
- **C. 基本补不回** → 路网本身缺乏匝道表达。

**判定：A（大量补回）**，理由：

1. CORE 旧缺口 113 个中 **112 个（99.1%）** 被独立几何补回；
2. **93.5%** 的断面与同向匝道距离 **≤5 m**；
3. 半径 50 m 即达 98.2%，扩大半径无增益；
4. 仅 **1** 个断面（0.4%）属真实几何缺口。

**根因**：6.3.2 crosswalk 以“**沿线采样 + 路名一致**”为锚，而 LTA slip 的
`RoadName` 是**所属高速名**（PAN ISLAND EXPRESSWAY 等），OSM `motorway_link`
的 `name` 却异构（连接路/立交名/高速名混杂）——**精确同名仅覆盖
29.1%**，导致路名锚把匝道排除、
断面被迫落到同名的高速**主线**（即 7.3.3/7.3.4 观察到的“匝道被主线化”）。

**方法学含义**：SLIP→匝道指派应改用 **“几何重合 + 同向”**（≤5 m 覆盖
93.5%），而非**路名**；路名仅作辅助。

> 新增 candidate 只证明“存在合理匝道几何候选”，**不直接改动 7.1 冻结靶场**；
> 需经独立重构验证后才能生成新 calibration crosswalk。
