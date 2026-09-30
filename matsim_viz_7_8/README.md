# matsim_viz_7_8 — 为 VIA 可视化重跑 W01（仅开 events 输出）

> ⚠️ **这不是新的模型版本。** 这是 `Singapore_OD_MATSim_Final_v1.0` 的
> **输出层重执行**：模型参数（f / λ / SCALE / f_cap / route-choice / 人口 / 路网）
> **逐位继承**冻结配置，只改了 3 个输出参数。判据：
> **it.19 linkstats 693,575/693,575 行重放 `BITEXACT`（max|Δ| = 0.0）**。

## ★ 两个目录怎么选

| 目录 | 是什么 | 有 events？ | VIA 里能看什么 |
|---|---|---|---|
| `matsim_final_7_6h/outputs/W01_rc_min/` | **v1.0 冻结最终运行**（定版基准，只读） | ⛔ **无**（`writeEventsInterval=0`） | 静态路网 + 按仿真流量着色（`output_links.csv.gz` 含 `vol_car` + WKT 几何）；**无车流动画** |
| `matsim_viz_7_8/outputs/W01_events/` | **同一模型的输出层重执行**（字节级等价） | ✅ **有**（1.69 GB） | ⭐ **车流动画**（Vehicles 层）+ 全部静态层 |

**要看车流动态 → 开 `matsim_viz_7_8/outputs/W01_events/`。**
**要看定版基准 / 引用标定结果 → 用 `matsim_final_7_6h/outputs/W01_rc_min/`。**

## 为什么重跑

7.8 定版的 W01 配置里 `writeEventsInterval = 0` ⇒ **没有 events 文件**，
而 VIA 的车辆层（唯一能做车流动画的层）只能靠 events。
原目录**保持只读**：新配置 / 新输出全部落在本目录，`matsim_final_7_6h/` 一字未动
（14 件冻结输入跑前后 mtime + sha256 逐位未变，见 `audit/frozen_inputs_*.csv`）。

## 与冻结配置的差异（白名单，共 3 项）

| 参数 | 冻结值 | 本目录值 | 性质 |
|---|---|---|---|
| `controller.outputDirectory` | `...\matsim_final_7_6h\outputs\W01_rc_min` | `...\matsim_viz_7_8\outputs\W01_events` | 输出层 |
| `controller.runId` | `W01_rc_min` | `W01_events` | 输出层（仅文件名） |
| `controller.writeEventsInterval` | `0`（不写） | `19` | **输出层（本次唯一目的）** |

其余 214 个参数（含 `<parameterset>` 全展开）取值逐位相同，见
`audit/config_diff_whitelist.csv`。

## ★ 运行结果（已验证 · 2026-09-19 20:21）

| 项 | 值 |
|---|---|
| 判决 | **`VIA_EVENTS_REPRODUCTION_CONFIRMED_BITEXACT`** |
| 过程门 | **40/40 PASS** |
| 运行耗时 | **117.67 min**（20 迭代，heap 24g，退出码 0） |
| **重放一致性** | **`BITEXACT`** — it.19 linkstats **693,575 / 693,575** 行，**max\|Δ\| = 0.0**，relΣ = 0.00e+00 |
| 14 件冻结输入 | 跑前后 sha256 + mtime **逐位未变**（V30/V31） |
| 冻结 W01 目录 | 仍 `writeEventsInterval=0`、仍 **0 个 events**（V32/V33，未被污染） |
| events 总量 | **163,305,988** 条记录 · 1.69 GB |
| departure / arrival | **236,044 / 236,044**（== 冻结 `N_sim`，**零滞留**） |
| entered link / left link | **80,708,818 / 80,708,818** |
| 车辆 / 人 | `PersonEntersVehicle` = `vehicle enters traffic` = 236,044 |
| it.0 events | 已删除（未收敛路线，释放 1.76 GB） |
| 本目录占用 | **3.9 GB** |

> ⚠️ 根目录 `W01_events.output_events.xml.gz` 与 `ITERS/it.19/W01_events.19.events.xml.gz`
> **字节完全相同**（sha256 `c9b61fba06d8a9b0…`），各 1.69 GB ⇒ **目录内 1.69 GB 冗余**。
> 给 VIA 任选其一即可（默认用根目录那份）。

## 产物

```
outputs/W01_events/
├── W01_events.output_network.xml.gz        ← VIA：Network 层（CRS EPSG:3414）
│                                              13.8 MB
├── W01_events.output_events.xml.gz         ← ★ VIA：事件/车辆层（最后一次写入 = it.19）
│                                              1.69 GB
├── W01_events.output_plans.xml.gz          ← VIA：Plans 层（215.8 MB，解析慢）
├── W01_events.output_links.csv.gz          ← vol_car + WKT geometry，可作 link 附加属性
│                                              14.8 MB
├── W01_events.output_vehicles.xml.gz       ← 车辆数据源（静态）635 KB
├── W01_events.output_config.xml            ← 实际生效配置（复核用）
├── ITERS/it.19/W01_events.19.events.xml.gz            ← 与根目录 events 同哈希
└── ITERS/it.19/W01_events.19.linkstats.txt.gz         ← 与冻结件对账（BITEXACT）
```

## 在 VIA 里怎么开

1. `File > Add Data...` 选 **`W01_events.output_network.xml.gz`**
   （网络自带 `coordinateReferenceSystem = EPSG:3414 / SVY21`）；
2. `File > Add Data...` 选 **`W01_events.output_events.xml.gz`**；
3. `File > Add Layer...` → **Network**；
4. `File > Add Layer...` → **Agents > Vehicles**，再点该层的 **Load Data**
   （events 不会被自动解析，需手动点一次；gz 约 1.7 GB，解析要几分钟）；
5. 底部时间轴拖到 **08:00–09:00**（本项目标定窗）即可看早高峰车流。

> 若底图错位：EPSG:3414 是新加坡 SVY21，别把它当 WGS84（EPSG:4326）。

### ⚠️ 只加 Network 层**不会**显示拥堵

Network 层的 *Link Coloring* 下拉里只有 `freespeed / capacity / lanes / length`
这些**静态**字段 —— `freespeed` 是设计速度，与拥堵无关；而 `output_links.csv.gz`
本身也**没有**行程时间 / 速度 / 延误字段（只有 10 列，见上）。

要出流量/速度必须**另加 `Dynamic Link Attributes` 层**（VIA 手册 §3.2.5），
再把 **aggregation window 设成 08:00–09:00**、颜色属性改成 **`speed`**。

诊断与"校准级"链路属性文件见
[`../reports/via_congestion_diagnosis_7_8/`](../reports/via_congestion_diagnosis_7_8/VIA_CONGESTION_DIAGNOSIS.md)
（含 `via_link_attributes_HRS8-9.tsv`，可在 Attributes Manager 里直接加载）。

## 纪律

- ⛔ 不改 `matsim_final_7_6h/` 下任何文件；⛔ 不改 f / λ / SCALE / f_cap / route-choice；
- ⛔ 本目录产物**不得**被引用为新的标定证据（`Sim/Obs` 仍以冻结的 `0.9993347697` 为准）；
- it.0 的 events 是**未收敛路线**的流量、非最终模型，跑完即删。

## 复现

```bash
cd D:/Luan/2026-05/2_Singapore
"C:/Users/LQP/miniconda3/python.exe" scripts/od/run_via_events_7_8_viz.py            # 准备步（29/29）
"C:/Users/LQP/miniconda3/python.exe" scripts/od/run_via_events_7_8_viz.py --run --heap 24g
"C:/Users/LQP/miniconda3/python.exe" scripts/od/run_via_events_7_8_viz.py --verify   # 重放分级 + events 盘点
```
