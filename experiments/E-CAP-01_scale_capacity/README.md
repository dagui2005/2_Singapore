# E-CAP-01 —— 抽样需求—道路供给尺度统一试验

```
EXPERIMENT ONLY / NOT v1.1 / NOT FORMAL BASELINE / NOT CALIBRATED MODEL
```

**给领导看的旁路演示**：把 QSim 流量容量与储车容量按抽样比例同步缩到 `1/SCALE = 0.434977`，
观察「当前模型过于通畅」有多少来自**需求抽样与道路供给不同尺度**。

## 30 秒速览

| 项 | 值 |
|---|---|
| 唯一模型改动 | `qsim.flowCapacityFactor` / `qsim.storageCapacityFactor`：`1.0 → 0.434977` |
| 依据 | $f_{cap}=200{,}000/459{,}794=0.4349774\ldots=1/SCALE$（现场可算） |
| 需求 / 网络 / 种子 | **完全继承 v1.0**（200k · 同网络 · seed 4711） |
| 输出 | 独立目录 `outputs/E-CAP-01/`，**v1.0 一字不改** |
| 配置 diff | 恰 **5 项**（2 模型 + 3 输出层），机器校验 |
| 运行前硬门 | **22 / 22 PASS** |
| **运行状态** | **✅ 已跑完**（20 迭代 · `rc=0` · 219.8 min）· **运行后硬门 11/11 PASS** |

## ★ 必读：本试验与 `7.9A-1` 物理等价（✅ 已实测证实）

派生后实测：E-CAP-01 与已跑的 `matsim_sampling_capacity_7_9a1/configs/config_A1_capf0p435.xml`
**模型层 0 差异**（只差 `outputDirectory` 与 `runId`）。

⇒ 实测结果：**逐位复现** 7.9A-1（`Sim/Obs` 差 `Δ=+0.000e+00`）。两条路**数值完全一致**：

| 方式 | 成本 | 说明 |
|---|---|---|
| ① 复用 A-1 | **0** | `matsim_sampling_capacity_7_9a1/outputs/A1_capf0p435/`；直接做展示包 |
| **② 新建独立运行（已执行）** | ≈ 2–3.5 h | 干净的演示目录，**数值等同**（本目录即此产物） |

**实测结果**：`Sim/Obs 0.9993 → 0.7665`（⚠️ 恶化）· `n(v/c≥1) 82 → 501`（×6.11）·
饱和里程 `1.15 → 7.34 km`（×6.37）· 全网 `ΣHRS8-9avg −4.7%` ·
`stuck = 0`、未到达 `0%`（**网络未崩解**）。
判决 **`SAMPLING_CAPACITY_NETWORK_BREAKDOWN`**（流量层护栏），消歧落 **情形 D**。
详见 `PROTOCOL_E-CAP-01.md §15/§17` 与 **`DEMO_ONE_PAGER.md`**。

## 用法

```
python scripts/experiments/ecap01_build_config.py                   # 派生配置 + 22 项硬门（零仿真）
python scripts/experiments/ecap01_build_config.py --verify          # 只复核
python scripts/experiments/ecap01_build_config.py --run --heap 24g  # 点火（≈2–3.5 h）【已跑完】
python scripts/experiments/ecap01_postrun.py                        # ★运行后验收门 + 冻结口径复算（只读）
python scripts/experiments/ecap01_demo_figs.py                      # ★生成领导展示 3 图（fig1–fig3）
python scripts/experiments/ecap01_static_figs.py                    # ★生成结果静态图集 6 图（fig4–fig9，只读）
```

## 文件

| 路径 | 说明 |
|---|---|
| `PROTOCOL_E-CAP-01.md` | **完整规程**（§0 披露 / 目的 / 独立性 / 参数 / 运行 / 解释 / 展示 / 判读 / 硬门 / §17 运行后结果） |
| **`DEMO_ONE_PAGER.md`** | **★领导判读一页纸**（三图怎么看 + 关键数字 + 诚实结论 + 红线） |
| `configs/config_E-CAP-01.xml` | 由冻结 v1.0 配置机器派生 |
| `audit/ecap01_config_diff_whitelist.csv` | 全展开 diff 白名单（5 项） |
| `audit/ecap01_checks.csv` | 22 项运行前硬门结果 |
| `audit/ecap01_postrun_gates.csv` | **11 项运行后硬门结果** |
| `audit/ecap01_postrun_metrics.json` | **全量实测 + 护栏 + 门禁** |
| `audit/ecap01_postrun_comparison.csv` | v1.0 vs E-CAP-01 对照 |
| `audit/ecap01_v10_mtime_before.json` | v1.0 冻结件 mtime 快照 |
| `audit/probe_background_survival_50min.*` | 后台托管存活上限探针（实测 ≥50 min） |

### 展示图（figures/）

**第一组：对照与参照（`ecap01_demo_figs.py`）**

| 文件 | 说明 |
|---|---|
| `fig1_load_grid_v10_vs_ecap.png` | **主图**：1 km 网格负荷（Σ流量/Σ容量），两版同色标 |
| `fig2_lta_observed_map.png` | 现实参照：LTA 实测断面流量 |
| `fig3_metrics_ratio_bars.png` | 倍率柱（E-CAP-01 ÷ v1.0） |

**第二组：E-CAP-01 结果绝对态（`ecap01_static_figs.py`，只读）**

> **先看 `fig10`**（单张自包含的早高峰拥堵态势图）；其余为分维度细图。

| 文件 | 说明 |
|---|---|
| `fig4_vc_map_ecap.png` | 早高峰 08–09 链路 v/c：**(a)** 全网绝对态 + **(b)** v/c ≥ 0.85 明细（灰底图 + 放大色标，看拥堵集中在哪） |
| `fig5_flow_map_ecap.png` | 链路流量地图（veh/h，对数色标；最大 3,982，p99 = 1,902） |
| `fig6_delay_map_ecap.png` | 链路延误地图（延误 = TT − ceil(自由流时间)；仅 ≥ 3 s；**对数色标**，因重尾 p50=9.5 s / p95=171 s / max=13,470 s） |
| `fig7_vc_distribution_v10_vs_ecap.png` | v/c 分布对照：直方 + 累计曲线（饱和链 82 → 501，×6.11） |
| `fig8_network_timeseries_ecap.png` | 全网逐小时负荷曲线（v1.0 vs E-CAP-01）+ 出行时间线（Σ出发=Σ到达=236,044，峰值在途 69,357，滞留 0） |
| `fig9_top_corridors_ecap.png` | Top 15 拥堵走廊（具名道路 ≥ 1 km，按 车·小时延误；榜首 PIE 862 veh·h） |
| **`fig10_congestion_status_map_ecap.png`** | **★早高峰拥堵态势图（单张自包含）**：主图按 v/c 五级着色 + Top 8 走廊标注；右侧分级里程构成 + 分级图例。超饱和 501 链/7.3 km、饱和及以上 2,201 链/87.0 km、Σ流量/Σ容量 = 0.198 |

> 图 4–9 的**口径与冻结评价器一致**：`v/c = HRS8-9avg / (CAPACITY × cap_mul)`（`cap_mul`：v1.0 = 1.0，E-CAP-01 = 0.434977）；
> 延误已消量化伪影（`TT − ceil(FF)`）；⛔ 不用 `speed_ratio` 红绿图作主图；⛔ TT/速度/延误不乘 SCALE。
> 图集**只读** E-CAP-01 与 v1.0 产物，不写回任何冻结件。


## ⛔ 红线

不改 v1.0 / crosswalk / `TrafficFlow` 原始值 / 评价器阈值 / `signals`·`trafficDynamics`·`speedFactor`；
不加迭代；不为展示效果调参；不写入 v1.1；展示主图**不用 `speed_ratio` 红绿图**（短链量化伪影）。
