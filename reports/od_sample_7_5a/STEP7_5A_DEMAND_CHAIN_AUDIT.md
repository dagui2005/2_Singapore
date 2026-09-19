# Step 7.5A（一）— 需求权重链条核查

**零仿真**。目的只有一个：确定 `MATSim` 的 linkstats 到底由哪个字段、以什么方式形成**有效需求权重**。

## 0. 结论（一句话）

> MATSim 的 link flow（linkstats 原始口径）由**进入 QSim 的 person/vehicle 数**决定；`expansionFactor` 与 `odTrips` 仅作为 population 的自定义属性存在，**不被任何 MATSim 代码消费**，因此『代表多少现实出行』的扩样系数必须在**评价层**显式施加（现行 SCALE = 459794 / N_sample）。

**判定：`NOT_CONSUMED`**

`expansionFactor` 与 `odTrips` 在 **MATSim 自身 class（`matsim-2026.0.jar` / `org/matsim/**`）中零命中**（阳性对照 `flowCapacityFactor` 等有命中，证明扫描有效）→ **没有任何 MATSim 代码按名读取这两个属性**，它们不可能进入 QSim。 需注意：`expansionFactor` 仅在 commons-math3-3.6.1.jar（第三方库）里出现同名标识符，属与该属性无关的同名字段（已逐条目核对）。 有效需求权重 = 进入 QSim 的 person/vehicle 数。

## 1. 链条全景

```text
OD 矩阵 T_ij
   |  6.2B allocate_cells: 每个正 cell >=1 agent，其余按 trips 最大余数分配
   v
agent 数 N_ij  +  expansionFactor EF_ij = T_ij / N_ij   (ΣEF = ΣT = 459,794)
   |  odTrips(每 cell 同值写 T_ij) 也写进 XML
   v
MATSim population XML  ──  QSim 只加载 N_ij 个 person/vehicle
   v
linkstats 原始口径 = 每小时通过该边的车辆数（未扩样）
   v
评价层 × SCALE = ΣT / ΣN  = 459,794 / N_sample   ← 有效需求权重在此形成
```

## 2. 证据 A — 项目自定义 Java

- `*.java` 文件数 = **2**；其中引用 `expansionFactor`/`odTrips` = **0** 处。
- 文件清单：
  - `matsim/step6_3/_CalcLinkStats.java`（MATSim 官方源码，非项目模块）
  - `matsim/step6_3/_GlobalConfigGroup_src.java`（MATSim 官方源码，非项目模块）
- 全部位于 `matsim/` 下（官方发行源码副本）= **True**；**项目自定义 Java 模块 = 0 个**。

## 3. 证据 B — Python 侧出现点（分类）

- `*.py` 扫描 3243 个；`expansionFactor` 13 处 / `odTrips` 12 处（已剔除审计脚本自身自指 37 处）。
- 分类计数：{"WRITE": 2, "READ_AUDIT": 23}
- 定位（前 12 条）：

| 文件 | 行 | 代码 |
|---|---:|---|
| `scripts/matsim/prepare_connected_scenario.py` | 170 | `"expansionFactor", "odTrips", "homeSource", "workSource"]` |
| `scripts/od/build_matsim_population.py` | 213 | `for name,value,cls in [("originZone",r.origin_zone,"java.lang.Integer"),("destinationZone",r.destination_zone,` |
| `scripts/od/build_matsim_population_6_2b.py` | 272 | `("expansionFactor", r.expansion_factor, "java.lang.Double"),` |
| `scripts/od/compare_step6_3_3b.py` | 231 | `ef = pers.set_index("person")["expansionFactor"].astype(float)` |
| `scripts/od/evaluate_demand_scale_7_4_3.py` | 106 | `m = re.search(r'name="expansionFactor" class="java.lang.Double">([0-9eE\.\-\+]+)<', line)` |
| `scripts/od/prepare_demand_scale_7_4_3.py` | 110 | `"question": "缩放的到底是什么：expansionFactor / odTrips / agents？",` |
| `scripts/od/prepare_demand_scale_7_4_3.py` | 134 | `"expansionFactor / odTrips scaling alone is a no-op for the simulation.",` |
| `scripts/od/prepare_demand_scale_7_4_3.py` | 269 | `md.append("- 每 agent 的 `expansionFactor` / `home_link` / `work_link` / departure `end_time` "` |
| `scripts/od/run_demand_scale_7_4_3.py` | 12 | `* 每 agent 的 expansionFactor / home_link / work_link / departure end_time 逐字节不变；` |
| `scripts/od/run_demand_scale_7_4_3.py` | 150 | `m = re.search(r'name="expansionFactor" class="java.lang.Double">([0-9eE\.\-\+]+)<', line)` |
| `scripts/od/validate_matsim_population.py` | 71 | `ef = attrs.get("expansionFactor")` |
| `scripts/od/validate_matsim_population_6_2b.py` | 16 | `6. expansionFactor finite and > 0.` |

> 关键：Python 侧只做两件事——（i）**写**人口属性（6.2B `write_population`）；（ii）**审计/守恒复核**（`ΣEF` 是否等于 `ΣT`）。**没有任何一处把 EF/odTrips 传回 MATSim 去放大流量**。

## 4. 证据 C — 配置 XML

- 全项目 `*.xml` 扫描 122 个；属性名命中 = **0** 处（`expansionFactor` / `odTrips`）。
- 其中 `matsim/` 下扫描 28 个 config，命中 = **0** 处。
- 官方认可的缩放旋钮（E06/D01 实测值）：

| 旋钮 | 位置 | E06/D01 取值 | 作用 |
|---|---|---:|---|
| `flowCapacityFactor` | qsim | 1.00 | sample-rate companion: 采样率一致时应 = N_sample/N_full |
| `storageCapacityFactor` | qsim | 1.00 | 同上（GlobalConfigGroup.checkConsistency 要求二者相等） |
| `countsScaleFactor` | counts | 1.0 | 仅用于 counts 比较，且必须等于 flowCapacityFactor |
| `writeLinkStatsInterval` | linkStats | 1 | writeLinkStatsInterval / averageLinkStatsOverIterations（不缩放 volume） |

> 官方无任何『按 person 属性扩样』机制；扩样必须由评价层完成。

## 5. 证据 D — MATSim jar 字节级常量池扫描（决定性）

- 扫描对象：`matsim-2026.0.jar` + `libs/*.jar`，共 **165** 个 jar、**38,647** 个 zip 条目。
- 原理：Java 通过反射按**属性名字面量**读取 person attribute，因此相关代码必然在常量池中留下该字面量；字符串常量在 class 文件中以 UTF-8 原样存放，可直接字节搜索。
- 判定口径：只有命中**落在 MATSim 自身 class**（`matsim-2026.0.jar` 或 `org/matsim/**`）才算「被消费」；第三方库（如数值库 commons-math3）里的同名私有字段属无关命中。

| 字面量 | 命中 jar 数 | 命中 jar | 是否命中 MATSim 自身 class | 性质 |
|---|---:|---|---|---|
| `expansionFactor` | **1** | commons-math3-3.6.1.jar | **否** | 被核查属性 |
| `odTrips` | **0** | — | **否** | 被核查属性 |
| `flowCapacityFactor` | **1** | matsim-2026.0.jar | **是** | 阳性对照（必须命中） |
| `storageCapacityFactor` | **1** | matsim-2026.0.jar | **是** | 阳性对照（必须命中） |
| `countsScaleFactor` | **1** | matsim-2026.0.jar | **是** | 阳性对照（必须命中） |

被核查属性的**逐条目命中明细**（透明、可复核）：

| 字面量 | zip 条目 |
|---|---|
| `expansionFactor` | `commons-math3-3.6.1.jar!org/apache/commons/math3/util/ResizableDoubleArray.class` |

> **MATSim 自身 class 零命中 + 阳性对照命中** = 扫描有效 且 官方代码里不存在按名读取这两个属性的代码。这是本核查最强的一条证据。

## 6. 对下游三个直接后果

1. **降低 agent 数会使 linkstats 原始口径近似线性下降**：因为它只数车，不认扩样权重。因此 100k 的 raw 大约是 200k 的一半，**必须**在评价层把 `SCALE` 从 2.29897 提到 4.59794 才可比。
2. **`capacity_factor` 不能当性能旋钮**：它直接改变每车饱和度，即改变拥堵/路由/断面分配（Phase 1 已证其在结构通道有显著影响）。反过来说，若要让『降低采样率』保持**同一物理交通场景**，`flowCapacityFactor` 就必须**随采样率同比缩放**——这不是调参，而是采样一致性的数学要求。
3. **`odTrips` 不是需求杠杆**：`od_trips / expansion_factor = N_ij`，Σ`odTrips` 随 λ 变化只是『每 cell agent 数分布』的影子。

---

口径：观测 7.1 冻结；仿真 `median(edges HRSx-yavg) × SCALE`；crosswalk = 7.3.6A Final；randomSeed=4711。
