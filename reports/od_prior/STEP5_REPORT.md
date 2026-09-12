# Step 5 报告 — 双约束 Gravity Prior OD（Physical Workplace）

- 脚本：`scripts/od/build_prior_od.py`
- 运行：`python scripts/od/build_prior_od.py`（`C:/Users/LQP/miniconda3/python.exe`）
- 用时：约 2 s（IPF 10–25 次迭代收敛）
- 输出目录：`reports/od_prior/`
- 结论：**程序 PASS（行列守恒达 1e-9 量级、IPF 全部收敛）**，但**平均通勤时间偏低是继承自 Step 4 的 free-flow 阻抗，不是 Step 5 的 bug** → 是否进入 Step 5B 前需先决定是否引入 AM peak 拥堵因子。

---

## 一、输入与冻结口径（本轮未改动任何上游）

| 输入 | 来源 | 关键总量 |
|---|---|---|
| `P_i` 工作出行产生 | `reports/od_production/production.csv`（列 `work_trip_production`） | **2,208,356** |
| `A_j` 就业吸引 | `reports/od_attraction_v21/attraction_v21.csv`（列 `workplace_attraction`） | **1,935,235** |
| `C_ij` 静态最短旅行时间 | `reports/od_impedance/impedance_matrix.parquet` | 110,224 行，全部可达 |

- 物理工作地口径：`r = A_total / P_total = 1,935,235 / 2,208,356 = 87.6324%`
- `P_i^phys = r · P_i`，再进行双约束 IPF。
- **特殊工作地口径 273,124**（No Fixed Location 177,588 / Works From Home 70,800 / Other PA or Outside SG 24,736）**不进入 332×332 物理 OD**，单独落盘，不隐藏。

---

## 二、本轮修复的 1 处接线问题（非模型改动）

`get_special_workplace_totals()` 原查找 `pa_workplace_control_v21.csv`，而 v21 实际产出的是 **`special_workplace_destinations.csv`**（列 `planning_area_norm` / `is_special_destination` / `workplace_employment` 完全匹配）。若不接线，脚本会静默回退成"单行 SPECIAL_TOTAL"，**三个特殊目的地分类明细会丢失**。

修复：① 把该文件名加入候选并置顶；② 布尔解析改为稳健版（防止 `"False"` 字符串被 `astype(bool)` 误判为 True）。**未触碰任何权重 / 口径 / λ。**

修复后 `special_destination_mass.csv` 正确输出 3 行分类：

| 特殊目的地 | national_employment |
|---|---|
| NO FIXED LOCATION FOR WORK | 177,588 |
| OTHER PLANNING AREAS OR OUTSIDE SINGAPORE | 24,736 |
| WORKS FROM HOME | 70,800 |
| **合计** | **273,124** |

---

## 三、`prior_od_accounting.json`（逐字）

```json
{
  "production_total": 2208355.9999989998,
  "physical_attraction_total": 1935235.0,
  "special_workplace_total": 273124.0,
  "production_minus_physical_attraction": 273120.99999899976,
  "physical_workplace_share_assumed": 0.8763238354689536,
  "special_workplace_share_assumed": 0.12367616453104635,
  "assumption": "Special workplace destination mass is proportionally distributed across residence Subzones because current data do not provide Subzone-level residence distributions for those categories."
}
```

- `physical + special = 1,935,235 + 273,124 = 2,208,359` vs `P_total 2,208,356` → **残差 +3**（源表取整，与 Step 2/3 同源）。
- `production_minus_physical = 273,121` vs `special_workplace_total = 273,124` → 差 3，同上。

---

## 四、`prior_od_summary.csv`（逐字）

| lambda_per_min | od_total | production_physical_target | attraction_total | production_physical_share | row_max_abs_err | col_max_abs_err | mean_weighted_travel_time_min | nonzero_od_cells | matrix_density | ipf_iter | ipf_converged |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 0.050 | 1,935,235 | 1,935,235 | 1,935,235 | 0.876324 | 6.62e-10 | 2.55e-11 | 13.740 | 71,838 | 0.651746 | 10 | True |
| 0.075 | 1,935,235 | 1,935,235 | 1,935,235 | 0.876324 | 1.49e-09 | 2.55e-11 | 13.073 | 71,838 | 0.651746 | 13 | True |
| 0.100 | 1,935,235 | 1,935,235 | 1,935,235 | 0.876324 | 5.64e-09 | 2.18e-11 | 12.425 | 71,838 | 0.651746 | 16 | True |
| 0.125 | 1,935,235 | 1,935,235 | 1,935,235 | 0.876324 | 6.53e-09 | 3.64e-11 | 11.816 | 71,838 | 0.651746 | 20 | True |
| 0.150 | 1,935,235 | 1,935,235 | 1,935,235 | 0.876324 | 4.31e-09 | 1.82e-11 | 11.259 | 71,838 | 0.651746 | 25 | True |

**守恒判定**：所有 λ 的 `row/col_max_abs_error` 均 ≤ 6.6e-9 ≪ IPF_TOL(1e-8)，`ipf_converged=True`。**行和 ≡ P_i^phys、列和 ≡ A_j 严格成立。**

---

## 五、四个判据的核验结果

### 1. 行列守恒 ✅
逐行 = `P_i^phys`、逐列 = `A_j`，误差 1e-9 量级；`od_total ≡ 1,935,235`（= 物理吸引总量）。

### 2. OD 稀疏度 ⚠️（口径需修正说明）
- **`nonzero_od_cells` 恒为 71,838 = 234 × 307**，与 λ 无关。
  - 原因：有效支撑 = (P>0 的 234 个 origin) × (A>0 的 307 个 destination)。引力种子在此支撑上**恒正**，IPF 的乘法缩放**不会制造/消灭零**，故支撑与 λ 无关。
  - **结论：`matrix_density` 在本模型类中不是有效的 λ 诊断量**（它对 5 个 λ 给出同一个数）。
- **有意义的稀疏度是"阈值稀疏度"**，它随 λ 单调且方向正确：

| λ | cells ≥1 | cells ≥10 | cells ≥100 | top1% 单元承载 trip 份额 | 区内(自环)份额 |
|---|---|---|---|---|---|
| 0.050 | 61,314 | 38,196 | 3,560 | 12.71% | 0.63% |
| 0.075 | 60,771 | 37,055 | 3,661 | 13.57% | 0.84% |
| 0.100 | 60,059 | 35,911 | 3,788 | 14.62% | 1.11% |
| 0.125 | 59,119 | 34,519 | 3,934 | 15.78% | 1.42% |
| 0.150 | 57,874 | 32,909 | 4,034 | 17.04% | 1.78% |

→ λ 越大：小流量单元被压到阈值以下、大流量单元更集中（集中度上升）。符合距离衰减直觉。

### 3. 平均通勤时间 ⚠️（偏低，继承自 Step 4）
均值随 λ 单调递减：**13.74 → 13.07 → 12.43 → 11.82 → 11.26 min**。

按 trip 加权的行程时间分布：

| λ | <15 min | 15–30 min | 30–45 min | 45–60 min | ≥60 min |
|---|---|---|---|---|---|
| 0.050 | 59.52% | 39.16% | 1.30% | 0.02% | 0.00% |
| 0.075 | 63.76% | 35.19% | 1.03% | 0.01% | 0.00% |
| 0.100 | 67.80% | 31.39% | 0.80% | 0.01% | 0.00% |
| 0.125 | 71.50% | 27.88% | 0.62% | 0.01% | 0.00% |
| 0.150 | 74.78% | 24.74% | 0.47% | 0.00% | 0.00% |

### 4. 长距离 OD 比例 ⚠️（几乎为零 — 这是本轮最重要的信号）
**所有 5 个 λ 下，>45 min 的出行占比 ≤ 0.02%，>60 min ≈ 0。** 即便最弱的 λ=0.05，也有 98.7% 的出行 <30 min。

---

## 六、根因诊断：不是 Step 5 的问题，是 Step 4 的 free-flow 天花板

Step 4 阻抗是**自由流**：中位 14.88 min、mean 61.0 km/h、**0% 超 90 km/h**。在一个自由流路网里，几乎没有 OD 对本身是"长"的；再加上指数衰减，出行自然压在 10–15 min。

对照现实：新加坡早高峰汽车通勤平均约 **25–30 min**（公交约 40+ min）。当前 11–14 min **约偏低一半** —— 这与"自由流比早高峰畅通约一倍"的量级一致。

> **结论：`λ` 无法修复这个偏低，因为它来自 `C_ij` 本身。** 需要引入早高峰速度折减（peak factor）或 LTA 实测速度，才能在 Step 5B/6 得到现实量级的通勤时间。

---

## 七、空间结构验证（强正信号 ✅）

按 Planning Region 的 P / A：

| Region | P 份额 | A 份额 | A/P |
|---|---|---|---|
| **CENTRAL** | 21.69% | **53.65%** | **2.17** |
| WEST | 23.44% | 17.70% | 0.66 |
| EAST | 16.99% | 12.66% | 0.65 |
| NORTH-EAST | 23.29% | 8.41% | **0.32** |
| NORTH | 14.58% | 7.58% | 0.46 |

→ Central（CBD）以 21.7% 的居住就业人口承载 53.7% 的岗位（净输入 2.17×）；North-East（盛港/榜鹅/后港）为典型卧城（A/P=0.32）。**这正是新加坡真实的空间结构**，是 Prior OD 合理性的正面证据。

- 最大产生区：TAMPINES EAST 73,517（3.33%）、WOODLANDS EAST 52,937、TAMPINES WEST 43,960 — 均为大 HDB 新镇，合理。
- 最大吸引区：CHANGI AIRPORT 26,898（1.39%）居首，其后为 CBD 的 CECIL / RAFFLES PLACE / CITY HALL（各约 1.3%）— 机场作为单一最大就业极合理（CBD 总量大但分散在多个小 Subzone）。

---

## 八、带入 Step 5B 的 3 个待处理项

1. **⚠️ 无路网 5 区仍有 4,506 吸引量（占全国 A 的 0.2329%）**：SEMAKAU 1,672 / SUDONG 1,384 / SOUTHERN GROUP 1,450，其到发时间靠 1.8–6.3 km 几何外推。这些是填埋场/离岛，**建议在 Step 5B 将其 A 置 0**（产生量已为 0，无问题）。
2. **⚠️ `c_ii = 0` 导致自环被过度加权**：区内份额随 λ 从 0.63% 升到 1.78%；λ=0.10 下第 2 大流即 TAMPINES EAST→TAMPINES EAST（2,140）。建议给对角一个小的区内阻抗下限。
3. **⚠️ 平均通勤偏低（见六）**：需在进入 MATSim 前决定是否引入早高峰速度折减。

---

## 九、产物清单

```
reports/od_prior/
├─ physical_production.csv              332 行：P_i 与 P_i^phys
├─ special_destination_mass.csv          3 行：三个特殊目的地分类
├─ prior_od_accounting.json              口径记账（含显式假设）
├─ prior_od_summary.csv                  5 个 λ 的汇总（本文第四节）
├─ prior_od_diagnostics.csv              332×5 行的 origin/destination 侧诊断
├─ prior_od_lambda_0p050.parquet / .csv  长表 OD
├─ prior_od_lambda_0p075.parquet / .csv
├─ prior_od_lambda_0p100.parquet / .csv
├─ prior_od_lambda_0p125.parquet / .csv
├─ prior_od_lambda_0p150.parquet / .csv
├─ prior_od_validation_lambda_*.json     每个 λ 的校验 JSON
└─ network_access_mass.json              无路网区记账（P 质量 = 0）
```

## 十、模型边界（本步未做）

- ❌ Census Table 118 的 Region→Workplace PA 约束
- ❌ Car-only OD（本步为全体就业者的物理工作地 OD，非汽车专用）
- ❌ MATSim assignment / `network.xml.gz`
- ❌ TrafficFlow 校准（Zone 07，属 Step 7）

> 本步只产出 `T_ij^prior`，为下一步（Table 118 约束 / 车辆分配）提供输入。
