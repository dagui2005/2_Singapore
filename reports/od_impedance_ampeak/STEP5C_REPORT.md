# Step 5C — AM Peak Travel-Time Impedance（LTA TrafficSpeedBands → C_ij^AM）

状态：**PASS**（reachable 1.000；5 组 λ 全部收敛；质量守恒 1,935,235）
脚本：`scripts/od/build_am_peak_impedance.py`（+ `build_impedance.py` 补节点表）
输出：`reports/od_impedance_ampeak/`、`reports/od_prior_5c/`
上游：Step 4 free-flow 阻抗 `reports/od_impedance/`（口径不变，仅新增 `network_nodes.csv`）

---

## 1. 数据实况勘查：AM 数据到底在哪

| 事实 | 结论 |
|---|---|
| `TrafficSpeedBands_v4.json`（56 MB, 143,787 条） | **是 2026-05-05 18:53（周二傍晚）的单次快照**，不是 AM 历史聚合 → 按 07:00–10:00 过滤会得到 0 条 |
| 带时间戳的 `TrafficSpeedBands_YYYYMMDD_HHMMSS.json` | 全部在 **`realtime_monitoring/`**（不在 `historical_data/`），共 **144 个 / 7.4 GB** |
| 其中工作日 07:00–09:59 | **仅 12 个**：2026-05-06（周三）6 个 + 2026-05-07（周四）6 个，各 07:00/07:30/08:00/08:30/09:00/09:30 |
| 每个 AM 快照 | **143,787 条 = 全 Link 覆盖**，合计 1,653,657 条观测 |
| 快照 JSON 字段 | `LinkID / RoadName / RoadCategory / SpeedBand / MinimumSpeed / MaximumSpeed / StartLon/Lat / EndLon/Lat` —— **无 Timestamp 字段**，时间只能由文件名解析 |
| `TrafficSpeedBands_Links.shp` | **143,787 条 LinkID，与 SpeedBand JSON 完全一一对应**（正确几何源） |
| `08_TrafficCount/TrafficFlow_Links.shp` | 只有 **1,278** 条 Link（仅交通量调查断面），**不能**用作 SpeedBand 几何源 |

---

## 2. 复现过程中修复的 5 处（3 个阻塞 + 1 个数据质量 bug + 1 个性能问题）

| # | 位置 | 问题 | 处理 |
|---|---|---|---|
| 1 | Step 4 `build_impedance.py` | 缺 `reports/od_impedance/network_nodes.csv`（Step 4 只存边、未存节点坐标），5C 无法把 LTA 速度落到 OSM 有向边 | Step 4 增加节点表导出（`node_id, x_svy21_m, y_svy21_m, lon, lat`，429,032 行、id 稠密、端点全覆盖），重跑 **1m25s**，Step 4 全部指标与之前**逐位一致**（reachable 1.0 / median 14.878 min / max 64.066） |
| 2 | 5C `LTA_LINKS` | 指向 `TrafficFlow_Links.shp`（**1,278 条**）→ 匹配率上限 0.9% | 改用 `TrafficSpeedBands_Links.shp`（**143,787 条**） |
| 3 | 5C `SPEED_DIR` | 只扫 `historical_data/`，AM 快照在 `realtime_monitoring/` → 回退到傍晚快照并被时间过滤挡掉，Step 1 直接报错 | 多目录扫描 + **按文件名时间戳预筛**（否则要解析 7.4 GB 全部 144 个文件） |
| 4 | **⚠️ `speed_from_record`（关键数据质量 bug）** | LTA 对 `SpeedBand=8`（≥70 km/h 开放档）用 `MinimumSpeed=70, MaximumSpeed=999`，**999 是哨兵值不是 999 km/h**。原护栏写 `if vmax >= 1000` → 999 漏过 → `(70+999)/2 = 534.5 km/h` 被赋给所有高速 | 哨兵（`vmax ≥ 999`）或 Band 8 一律回退到可配置代理值 75 km/h；代理值单列记录 |
| 5 | 5C 性能 | 原实现每条记录 `pd.to_numeric(pd.Series([x]))`（≈700 万次 Series 创建）+ 匹配阶段 14 万×8 次 pandas `.iloc`/shapely 标量访问 → **>17 min 仍未跑完 Step 1** | 记录解析改为标量 `tofloat` + 每文件解析一次列名；LTA→OSM 匹配**整体向量化**（KDTree + 广播端点误差 + argmin）→ **2m12s** |
| 附 | `recompute_332_impedance` | snap 表列名是 `nearest_node`，脚本要求 `nearest_network_node` | 兼容两种列名 |

### 哨兵 bug 的影响（修正前 vs 修正后）

| 指标 | v1（含 bug） | **v2（修正）** |
|---|---|---|
| AM 最大速度 | **534.5 km/h** | 90.0 km/h |
| 匹配边上 >130 km/h | 1,790 条（其中 motorway 814） | **0 条** |
| motorway AM 中位速 | **283.25 km/h** | **64.5 km/h** |
| OD 中位时长 | 16.77 min（×1.146） | **18.13 min（×1.222）** |
| OD 对变慢比例 | 92.05% | **99.67%** |

v1 输出已留档于 `reports/od_impedance_ampeak/_v1_band8_sentinel_bug/`。

---

## 3. LTA → OSM 匹配与 AM 速度

| 指标 | 值 |
|---|---|
| AM 观测（工作日 07–09 点，12 快照） | 1,653,065 条 |
| 唯一 LTA Link | 143,735 |
| 成功匹配的 LTA Link | **143,478（99.82%）** |
| 获得 AM 速度的 OSM 有向边 | **92,149（13.0% 边数 / 18.1% 长度）** |
| 未匹配边 | 保留 Step 4 free-flow 速度 |

### 各等级 AM vs free-flow（匹配边上中位速度）

| highway | n | free-flow | AM | AM/FF |
|---|---|---|---|---|
| residential | 35,067 | 50.0 | 19.5 | **0.39** |
| service | 15,051 | 20.0 | 14.5 | 0.73 |
| primary | 11,244 | 60.0 | 44.5 | 0.74 |
| tertiary | 8,704 | 50.0 | 29.5 | 0.59 |
| secondary | 7,926 | 50.0 | 34.5 | 0.69 |
| unclassified | 4,395 | 50.0 | 24.5 | 0.49 |
| motorway_link | 2,260 | 50.0 | 54.5 | 1.09 |
| primary_link | 2,063 | 50.0 | 24.5 | 0.49 |
| trunk | 1,771 | 70.0 | 44.5 | 0.64 |
| **motorway** | 1,570 | 90.0 | **64.5** | 0.72 |
| secondary_link / trunk_link / tertiary_link | 2,098 | 50.0 | 19.5–34.5 | 0.39–0.69 |

- 匹配边上 **89.6% 变慢**；长度加权 AM 速度 **19.9 km/h**。
- 全网络（含未匹配）边速度中位 20.0 km/h（因 service 类占边数过半、默认 20）。
- 按各档中值加权的全网 AM 平均速 ≈ **25.5 km/h**，与新加坡早高峰全网实际量级一致。

### OD 层面：AM vs free-flow（332×332）

| 指标 | free-flow (Step 4) | **AM peak (Step 5C)** | 变化 |
|---|---|---|---|
| 旅行时间中位 | 14.878 min | **18.131 min** | +3.18 min（×1.222）|
| 旅行时间均值 | 15.197 min | 18.481 min | +3.28 min |
| 旅行时间最大 | 64.066 min | 78.953 min | +14.89 min |
| 不可达 | 0 | 0 | — |
| 变慢的 OD 对 | — | **99.67%** | — |

➜ **回答"是否明显高于 14.88 min"：是。中位 18.13 min（+22.2%），均值 18.48 min。** 现实新加坡汽车早高峰约 25–30 min，5C 已从 5A/5B 的 11–12 min 显著逼近，但仍有约 7–11 min 的差距（见 §5 局限性）。

---

## 4. Step 5C 的 Prior OD（同一约束框架 + AM 阻抗）

在**完全相同的约束框架**（无路网区 A 清理 + c_ii 修正 + Table 118 + IPF）下，仅把 C_ij 换成 AM 阻抗，重跑 5 组 λ（`reports/od_prior_5c/`）：

| λ (/min) | od_total | row_err | col_err | Region→PA 最大残差 | **平均通勤 (min)** | 非零 OD | Gravity IPF | Final IPF | 收敛 |
|---|---|---|---|---|---|---|---|---|---|
| 0.050 | 1,935,235 | 4.4e-9 | 3.3e-11 | 2.32% | **15.312** | 71,136 | 11 | 15 | ✓ |
| 0.075 | 1,935,235 | 6.4e-9 | 2.2e-11 | 2.31% | **15.119** | 71,136 | 14 | 15 | ✓ |
| 0.100 | 1,935,235 | 5.4e-9 | 2.2e-11 | 2.40% | **14.922** | 71,136 | 19 | 15 | ✓ |
| 0.125 | 1,935,235 | 5.2e-9 | 2.9e-11 | 2.82% | **14.720** | 71,136 | 24 | 16 | ✓ |
| 0.150 | 1,935,235 | 3.0e-9 | 2.2e-11 | **4.01%** | **14.514** | 71,136 | 30 | 18 | ✓ |

### 三步对照（平均通勤，min）

| λ | 5A free-flow | 5B free-flow+约束 | **5C AM peak+约束** | 5C/5B |
|---|---|---|---|---|
| 0.050 | 13.740 | 12.344 | **15.312** | 1.240 |
| 0.075 | 13.073 | 12.218 | **15.119** | 1.237 |
| 0.100 | 12.425 | 12.089 | **14.922** | 1.234 |
| 0.125 | 11.816 | 11.958 | **14.720** | 1.231 |
| 0.150 | 11.259 | 11.825 | **14.514** | 1.227 |

- **AM 阻抗使平均通勤整体上移约 22–24%**（λ=0.10 时 12.089 → 14.922 min）。
- c_ii 代理值随阻抗重估：**free-flow 中位 1.594 min → AM 中位 2.079 min**（max 15.448）。
- 非零 OD 格仍恒为 **71,136**（支撑集不变，与 λ、与阻抗都无关）。
- ⚠️ Region→PA 残差随 λ 增大而升高（2.3% → 4.0%@λ=0.15）：距离衰减越强，越难同时满足 Census 区块结构与吸引量边际。λ=0.10 及以下仍在 2.4% 以内，接近 5B 的 2.2% 地板。

---

## 5. 局限性（下结论前需知）

1. **匹配覆盖率只有 13% 边 / 18.1% 长度**：87% 的边仍用 free-flow 速度，AM 拥堵效应被**稀释**。因此 §3 的 ×1.222 是**下界**性质。若要把 AM 结构做全，候选方案（5C.2）：
   - 把 LTA 速度按**路名**传播到同名 OSM 边 —— 需要 Step 4 在 `network_links.csv` 里**额外保留 road name**（当前只有 6 列，无 name），然后在 5C 做「同名 + 邻近」传播；
   - 或放宽 80 m 匹配半径（当前 `--max-match-distance`）并允许一条 LTA 链路命中多条最近边；
   - 不建议用 TrafficFlow 的 Volume ÷ 拍脑袋通行能力反推速度。
2. **AM 样本只有 2 个工作日**（2026-05-06 周三、05-07 周四，各 6 次快照）。是**真实观测**但样本薄；扩样需继续抓取或补充历史档。
3. **Band 8 用 75 km/h 代理**（开放档 ≥70 km/h 无上界）。该假设已单列在 `ampeak_network_validation.json:band8_speed_proxy_kmh`，未伪装成观测值。
4. **λ 仍未冻结**：5 组全部保留。λ* 应由 Step 7 的 TrafficFlow 校准目标决定：
   `λ* = argmin_λ Error(q_a^sim(λ), q_a^obs)`，即 `min_T [Σ w_a (q_a^sim − q_a^obs)² + λD(T, T_prior)]`。
5. 5C 只改**网络阻抗**，未做任何 OD 校准、未做 car-only、未做 mode share。

---

## 6. 结论与下一步

- Step 5C **PASS**：AM 阻抗已由 LTA 实测 SpeedBand 构建（**非** TrafficFlow 反推），332×332 全可达，5 组 λ 收敛、守恒 ≤6.4e-9。
- AM 峰值中位时长 **18.13 min（×1.222 vs free-flow）**，OD 平均通勤 12.1 → 14.9 min（λ=0.10）。
- 关键修复：**Band 8 的 `999` 哨兵值**（否则高速被赋 534.5 km/h，严重低估拥堵）——这一条是 5C 能否成立的前提。
- **建议**：先确认匹配覆盖率是否接受（13%/18.1%）。若接受，直接进 **Step 6 MATSim**；若要把覆盖率做上去，先做 **5C.2 路名/半径传播**（需 Step 4 增存 road name），再重跑一次 5C 的 Gravity/IPF。最后 λ* 交 **Step 7 TrafficFlow** 校准。
