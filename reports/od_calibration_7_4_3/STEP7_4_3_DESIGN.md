# Step 7.4.3 — OD 总量 / car-trip demand scale 标定（设计）

> 本文件由 `scripts/od/prepare_demand_scale_7_4_3.py` 生成，是本步骤的**单一事实源**。本步骤只做**设计 + 人口变体生成 + 仿真 + 评价**；不修改任何已冻结产物。

## 1. 要回答的唯一问题

E06（λ=0.075, f_cap=1.00, 20 it）下 `Sim/Obs(all)=0.7070`、`CATA=0.7137`、`SLIP_ROAD=0.6706` 全面 <1。这 19–30% 的量级缺口，**是否主要来自机动车 OD 总需求规模不足？**

## 2. ★ 前置结论：缩放的到底是什么（本步骤的方法论基石）

| 量 | 定义 | Σ | MATSim 消费 | 能否作为需求缩放对象 |
|---|---|---:|---|---|
| `expansion_factor` | `EF_ij = T_ij / N_ij`（每 agent 代表的真实车次） | **459,794 = 真实 car OD 总量** | ❌ 否 | 仅**算术**，不改仿真 |
| `od_trips` | `T_ij`（cell 车 OD 总量，复制给该 cell 每个 agent） | 约 4.2–4.5M（**随 λ 变，非需求量**） | ❌ 否 | ❌ **不能** |
| **agents（车辆）** | `<person>`/`<plan>`（每人 1 条 car leg） | **200,000** | ✅ **是** | ✅ **唯一物理杠杆** |

**推论**：

1. 只缩放 `expansion_factor` / `od_trips` → 仿真的 `HRSx-yavg` 完全不变，只是把标定倍数换成 f×2.29897 → `Sim/Obs` **精确 ×f**、`CATA/SLIP` **完全不变**。这是**算术重标定**，不是需求实验 → 本步骤作为 **A 系列参照（零仿真）**输出。
2. 需求要**物理地**增加，必须**增加被仿真的车辆数（agent 数）** → 本步骤主实验 = **D 系列（真实加车、跑 MATSim）**。
3. **A 系列 − D 系列 = 拥堵弹性阻尼**（网络饱和导致流量不按比例上升的部分）。

**ΣodTrips 随 λ 变化不是异常**：`od_trips / expansion_factor = N_ij`（cell 内 agent 数，中位 4、最大 114）→ ΣodTrips 只反映**每 cell agent 数分布**，真实需求量恒为 `Σ EF = 459,794`（6.2B 逐 cell 守恒误差 < 1e-12）。

## 3. 冻结项（本步骤一律不动）

```text
7.1 观测靶场             不变
7.3.6A Final Crosswalk   不变
network_cleaned.xml.gz   不变
capacity factor          1.00
simulation iterations    20
departure profile        6.3.3A
randomSeed / routingRand 4711 / 0.0
λ                        固定 0.075（不冻结，但本轮不扫）
```

## 4. 实验矩阵

| Exp | f_demand | agents | 新增 | λ | f_cap | it | 状态 |
|---|---:|---:|---:|---:|---:|---:|---|
| **D01** | 1.00 | 200,000 | 0 | 0.075 | 1.00 | 20 | REUSE_E06 |
| **D02** | 1.10 | 220,000 | 20,000 | 0.075 | 1.00 | 20 | RUN |
| **D03** | 1.20 | 240,000 | 40,000 | 0.075 | 1.00 | 20 | RUN |
| **D04** | 1.25 | 250,000 | 50,000 | 0.075 | 1.00 | 20 | RUN |

> `D01` ≡ `E06`，**直接复用 Phase 2 结果，不重新仿真**。

## 5. 人口变体怎么造（受控性）

以 6.3.3A 冻结人口为源，按 **seed=20260912 的 permutation 前缀**做**嵌套随机子集复制**（D02 ⊂ D03 ⊂ D04）：

- 每 agent 的 `expansionFactor` / `home_link` / `work_link` / departure `end_time` **逐字节不变** → 唯一变化 = 车辆数；
- 复制概率对**每个 agent 相同** → 增量在空间上**无偏**（不会被「每 cell 保底 1 agent」扭曲，这是逐 cell 按比例复制做不到的）；
- 目标 `Σ EF = f × 459,794`，**实测值由评价器复核并披露**。

## 6. 预注册判据

1. 若 D 系列 Sim/Obs(all) 随 f 上升并趋近 1，且 CATA/SLIP 仍接近 1、WMAPE/GEH 不恶化 → 量级缺口主要是 OD 总量问题，可冻结 demand scale。
2. 若 D 系列接近 A 系列（算术上界）→ 网络未饱和，需求标定是纯量级问题。
3. 若 D 系列显著低于 A 系列 → 存在拥堵弹性阻尼：加车被饱和吸收，量级缺口不能只靠需求补齐。
4. 若仅总量改善而 CATA/SLIP 恶化 → 出现'总量对、空间错'，须回到 OD 空间结构 / λ / attraction。
5. λ 继续不冻结；本步骤不自行选定 λ 或 f_demand。

## 7. 产物

```text
reports/od_calibration_7_4_3/
├── demand_scale_matrix.csv
├── demand_parameter_definition.json
├── STEP7_4_3_DESIGN.md
├── demand_run_manifest.json                  （运行后）
├── demand_scale_backtest.csv                 （评价后）
├── demand_scale_roadcat_summary.csv
├── demand_scale_comparison.csv               ★ f × 指标
├── step7_4_3_summary.json
└── STEP7_4_3_REPORT.md
```
