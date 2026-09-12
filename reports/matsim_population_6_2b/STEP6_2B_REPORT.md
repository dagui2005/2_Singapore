# Step 6.2B — OD-cell 保底采样 + 住宅/就业空间下分

> 目标：把 Step 6.2 的「第一版网络可运行人口」升级为**100% OD-cell 可回溯**、
> Home/Work 落在**真实空间点所吸附的 MATSim link** 上的 population。
> 不改动任何上游冻结量：`A_j` / `C_ij^AM,v2` / `λ` / `network.xml.gz` 原封不动。

---

## 1. 结论（PASS）

| λ | agents | 非零 OD cell | cell 覆盖 | Σ expansion | car OD 总量 | 单 cell 最大误差 | 缺 cell | status |
|---|---|---|---|---|---|---|---|---|
| 0.050 | 200,000 | 71,136 | **100%** | **459,794.000** | 459,794 | 1.42e-14 | 0 | **PASS** |
| 0.075 | 200,000 | 71,136 | **100%** | **459,794.000** | 459,794 | 1.42e-14 | 0 | **PASS** |
| 0.100 | 200,000 | 71,136 | **100%** | **459,794.000** | 459,794 | 1.42e-14 | 0 | **PASS** |

独立复核（`validate_matsim_population_6_2b.py`，重新解析 `population_lambda_*.xml.gz`，不信任自报告）：

```
lambda 0.050: persons=200000 cells=71136/71136 coverage=1.0000 exp_sum=459794.000
              max_cell_err=6.82e-13 node_mismatch=0 link_missing=0 -> PASS
lambda 0.075: persons=200000 cells=71136/71136 coverage=1.0000 exp_sum=459794.000
              max_cell_err=3.98e-13 node_mismatch=0 link_missing=0 -> PASS
lambda 0.100: persons=200000 cells=71136/71136 coverage=1.0000 exp_sum=459794.000
              max_cell_err=9.09e-13 node_mismatch=0 link_missing=0 -> PASS
ALL_CHECKS_PASS: True
```

三条目标全部达成：

- `V(i,j): T_ij>0 ⇒ N_ij ≥ 1` —— **cell 覆盖 = 100%**（71,136 / 71,136）；
- `Σ_ij N_ij · EF_ij = 459,794` —— **总量精确守恒**（误差 < 1e-3，单 cell < 1e-12）；
- `EF_ij = T_ij / N_ij` —— 每个 cell 都能被 agent 的 expansion 精确重建，**任意 cell 均可回溯**。

---

## 2. 运行前修复的 3 处致命缺陷

脚本第一版无法产出正确结果。以下三处是**致命/静默错误**，均在运行前修复：

### 2.1 POI 列名不识别 + 未重投影（POI 池静默为空）

`poi.csv` 的坐标列是 **`lng` / `lat`**（WGS84 度，`lat 1.21–1.47, lng 103.6–104.0`）。
原脚本检索 `x | lon | longitude | wgs84_lon` —— **`lng` 不匹配任何一项** → 返回空表 →
**整条 POI→Work 空间下分链路从未生效**（Work 端全部退回 building）。

修复：识别 `lng/lon/long/longitude`，并**把 WGS84 经纬度重投影到 EPSG:3414**再吸附
（网络坐标是 SVY21 米制，`x 2.7k–55.6k, y 20.5k–50.2k`）。若不重投影，经纬度将被当作米去吸附
→ 所有 POI 塌缩到同一条 link。修复后 `poi_points = 8,670`、覆盖 **304 个 Subzone**。

### 2.2 MATSim activity 元素名写错（`<act>` → `<activity>`）

MATSim `population_v6.dtd` 声明 `<!ELEMENT plan (attributes?, (activity|leg)*)>`，
`PopulationReaderMatsimV6` 的 `startTag` switch 中 `case ACT` 且 `ACT = "activity"`，
任何其它标签都会 `throw new RuntimeException("[tag=... not known or not supported]")`。
第一版发出 `<act>` → **MATSim 会直接拒绝该文件**。已改为 `<activity>`（与已冻结的 6.2 一致）。

### 2.3 home/work node 与 link 不一致

第一版写 `homeNode = zone node`，但 `home_link = 空间点吸附到的 link`，二者互不隶属。
修复：**activity 的 node 取该 link 的 `from_node`**（即空间节点），与「不再落在 Zone centroid 节点」的设计意图一致；
zone node 另存为 CSV 的 `*_zone_node` 参考列。复核 `node_link_mismatch = 0`。

---

## 3. 方法

```
car Prior OD(λ)
  └─ allocate_cells: 每个正 cell 保底 1 agent；余量按 trips 做 largest-remainder 分配
       → N_ij ;  EF_ij = T_ij / N_ij
  Home 候选：URANoofDwellingUnits（按 DU 加权）→ Building（均匀）→ zone-node 关联 link
  Work 候选：POI（均匀）→ Building（均匀）→ zone-node 关联 link
  候选点 → 吸附到最近 MATSim link（cKDTree，对 link 中点；每 zone 只吸附一次）
  → activity(home, link=home_link) + leg(car) + activity(work, link=work_link)
```

- **Home 端按 DU 加权**：`URANoofDwellingUnits` 的 `DU`（套数）中位 1、最大 774，按套数抽样使
  home 落点与住宅容量成比例，而非均匀铺开。
- **不凭空造 ACRA 坐标**：ACRA 空间定位率约 82%，Work 端用 POI + 建筑，**不拿未确认邮编硬凑空间点**。
- **特殊就业质量不外挂**：`Works from Home` / `No Fixed Location` / `Other PA or Outside SG`
  继续单独保留，**不塞进 332×332**。

---

## 4. 空间来源比例（源侧）

| 项 | URANOF | Building | zone-node fallback |
|---|---|---|---|
| Home（λ=0.05，agent 数） | **174,711 (87.4%)** | 24,681 (12.3%) | 608 (0.3%) |
| Work（λ=0.05，agent 数） | — | 1,141 (0.6%) | 4,049 (2.0%) |
| Work（POI） | **194,810 (97.4%)** | | |

- Home 空间池：URANOF 覆盖 206 Subzone，Building 补 46 个，80 个 zone 无住宅候选 → 回退 zone-node 关联 link。
- Work 空间池：POI 覆盖 304 Subzone，Building 补 2 个，26 个 zone 回退（多为工业/离岸/无 POI 区）。

---

## 5. 空间离散度（相对 6.2 的关键升级）

| 指标 | Step 6.2 | **Step 6.2B** |
|---|---|---|
| 使用的 home link 数 | ≤ 332（每 zone 一条） | **17,052** |
| 使用的 work link 数 | ≤ 332 | **5,782** |
| 每 origin zone 的 home link 数（中位 / 最大） | 1 / 1 | **40 / 651** |
| 每 dest zone 的 work link 数（中位 / 最大） | 1 / 1 | **13 / 156** |

agent 不再共用 zone 质心节点，而是分布在真实住宅/就业建筑周边的 1.7 万条 home link 上 ——
这是后续做 **链路级 TrafficFlow 校准**的空间基础。

其他分布 QC（λ=0.05）：

- agents/cell：min 1、median 2、max 109（λ=0.10 时 max 121）。
- expansion factor：min **0.00066**、median 2.614、max 3.539。
  > 注意：保底 1 agent 后，**小 cell 的 EF 可以 < 1**（1 个 agent 代表不足 1 次出行），
  > 这是「每 cell 可回溯」的必然结果；EF 不再是统一的"放大倍数"，而是**逐 cell 系数**。

---

## 6. 产物

`reports/matsim_population_6_2b/`

| 文件 | 内容 |
|---|---|
| `population_lambda_0p050/0p075/0p100.xml.gz` | MATSim population（每套 20 万 agents，`<activity>` 元素） |
| `agent_spatial_assignment_lambda_*.csv` | 每 agent：origin/dest zone、home/work node+link、home/work source、od_trips、expansion_factor |
| `od_cell_conservation_lambda_*.csv` | 每 cell：trips / agent_count / realized / abs_error（全 0） |
| `population_6_2b_summary.csv` | 3 λ 汇总（覆盖/守恒/来源分解/status） |
| `population_6_2b_validation.json` | 自报告（PASS） |
| `population_6_2b_independent_check.json` | 独立复核（`ALL_CHECKS_PASS: true`） |
| `spatial_source_summary.json` | 空间源点数/覆盖 zone 数/抽样规则 |

脚本：`scripts/od/build_matsim_population_6_2b.py`、`scripts/od/validate_matsim_population_6_2b.py`。
性能：整套 3×200k **53 s**（空间源加载约 8 s，逐 λ 约 15 s）。

---

## 7. 限制与下一步

- **仍为 2 活动日计划**：`home(end 08:00) → car → work`，**尚无出发时刻分布 / 时间属性 / rerouting**。
  真实的 AM peak 出发时间分散、活动时长、方案重选属 **Step 6.2C / 6.3** 范畴。
- **Home 落点用建筑/住宅单元点，非单元级入户**：DU 加权是容量比例，级别仍是「建筑」。
- **未含非汽车方式与特殊就业质量**（设计如此）。
- **λ 仍未冻结**。Step 6.3 先用 λ = 0.05 / 0.075 / 0.10 三档跑 assignment。

**下一步 Step 6.3**：MATSim AM simulation → `q_a^sim`，再进 Step 7 用 TrafficFlow
`q_a^obs` 做链路级校准，由 `argmin_λ Error(q_sim, q_obs)` 决定最终 `λ*`。
