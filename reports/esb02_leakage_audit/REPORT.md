# E-SB-02B —— AM SpeedBand → OD 信息泄漏审计（只读）

> 生成：2026-10-09 ｜ 脚本：`scripts/experiments/esb02_leakage_audit.py` ｜ 产物：`reports/esb02_leakage_audit/`
> 性质：**只读**。零仿真、零冻结件改动、未产生 v1.1。
> 判决：**`LEAKAGE_QUANTIFIED`（门禁 7/7 PASS）**
> 回答的问题：把 SB-A4 的 AM 观测速度换成夜间速度，**能不能算"独立拟合"**——取决于 AM SpeedBand 是否已经把观测信息带进了需求。

---

## 0. 一句话结论

**AM SpeedBand 确实进了 OD，但只在"目的地选择权重"这一层，且量级很小、可精确量化。**
- 通道：`TrafficSpeedBands(AM) → C^AM(332×332) → 重力项 exp(−λ·C^AM) → IPF → Prior OD → 200k car-only 人口`。
- **P_i / A_j / Table118 是硬约束，完全不受阻抗选择影响** ⇒ 泄漏**不**影响出行总量、也不影响 Census 的 Region×PA 结构。
- 量级：`TV(T^5B, T^5C.1) = 3.49%`（λ=0.075，**本脚本重算与既有产物逐位一致，max|Δ|=8.33e-17**）。
- 方向上，AM 阻抗让 OD **略微更本地化**（区内份额 +20.5% 相对），单块最大变化仅 **0.013 pp**。

⇒ **E-SB-02B 是可解的，且并非"必须推倒重来"**：只需一个"无 SpeedBand 需求"对照臂（**Step 5B 自由流阻抗 OD，已存在**），即可把"真实供给速度校准"与"AM 先影响车辆去哪走"彻底分开。

---

## 1. 泄漏通道（唯一）

```
Dynamic_2026_03_16/realtime_monitoring/TrafficSpeedBands_*.json   (weekday 07:00-09:59, 12 快照)
        │  Step 5C  build_am_peak_impedance.py
        ▼
reports/od_impedance_ampeak/ampeak_impedance_matrix.parquet
        │  Step 5C.1  enhance_ampeak_network.py  (三级置信度 geom / name+hw / name 传播)
        ▼
reports/od_impedance_ampeak_v2/ampeak_impedance_v2.parquet   (332×332, 中位 21.361 min)
        │  build_prior_od_5c1.py
        │      seed_ij = P_i · A_j · exp(−λ · C_ij^AM)      ← ★泄漏点：仅此一项
        │      IPF(seed; P_i, A_j)  +  Table118 Region×PA 块约束
        ▼
reports/od_prior_5c1/prior_od_5c1_lambda_0p075.parquet        (λ=0.075 冻结)
        │  build_matsim_population.py  (car-only, 200,000 agents)
        ▼
matsim_final_7_6h/populations/pop_W01/population_lambda_0p075.xml.gz   ← v1.0 需求
```

| 层 | 是否受 SpeedBand 影响 | 实测 |
|---|---|---|
| `C_ij`（逐对旅行时间） | ✅ **是** | 中位 14.878 → **21.361 min（+43.6%）** |
| 重力项 `exp(−λ·C_ij)` | ✅ **是** | 唯一通道 |
| `P_i`（生产边际） | ❌ 否（IPF 硬约束） | Σ=1,935,235 不变 |
| `A_j`（吸引边际） | ❌ 否（IPF 硬约束） | Σ=1,935,235 不变 |
| Table118 `Region×PA` 块 | ❌ 否（块约束） | — |
| 出行总量 / 支撑集 | ❌ 否 | 非零格恒 71,136；ΣT=1,935,235 |

> **含义**：AM SpeedBand 的泄漏**只能**通过"把出行质量在同距离/跨距离之间重新分配"起作用，**不能**改变总量或 Census 结构。

---

## 2. 泄漏量级：`TV(T^5B, T^5C.1)`

**对照臂 = Step 5B**：`reports/od_prior_5b/`，用 **自由流阻抗 `C^FF`**（`reports/od_impedance/impedance_matrix.parquet`，中位 14.878 min）构建，**不含任何 SpeedBand 输入**；其余约束框架（P/A/Table118/`c_ii` 代理）与 5C.1 **完全相同**。
⇒ `T^5B` 是天然的「零泄漏需求」；`T^5B` 与 `T^5C.1` 的**总变差距离 = 泄漏的空间杠杆**。

| λ | TV(5B vs 5C.1) | 区内份额 5B → 5C.1 | 区内相对变化 |
|---|---:|---|---:|
| 0.050 | 2.34% | 0.94% → 1.07% | +13.7% |
| **0.075** | **3.49%** | **1.04% → 1.26%** | **+20.5%** |
| 0.100 | 4.61% | 1.15% → 1.47% | +27.1% |
| 0.125 | 5.69% | 1.28% → 1.70% | +33.5% |
| 0.150 | 6.73% | 1.41% → 1.96% | +39.6% |

- **λ=0.075（冻结值）泄漏量级 = 3.49%**，本脚本重算与 `compare_5b_vs_5c1_summary.csv` **逐位一致**。
- 泄漏随 λ **单调增大**（越大＝距离衰减越强＝AM 阻抗的"惩罚长距离"效应被放大）。
- **方向**：AM 阻抗更重地惩罚长距离，把质量**压回近距离对** ⇒ OD 略更本地化；跨区份额几乎不动（60.52%）。

---

## 3. 泄漏的空间模式（275 个 Region×WorkplacePA 块）

| residence_region | workplace_pa | trips_5B | trips_5C1 | Δ(pp) |
|---|---|---:|---:|---:|
| CENTRAL REGION | QUEENSTOWN | 35,703.5 | 35,758.2 | **+0.0130** |
| CENTRAL REGION | GEYLANG | 28,980.4 | 28,943.5 | −0.0088 |
| EAST REGION | BEDOK | 26,834.5 | 26,808.2 | −0.0080 |
| CENTRAL REGION | BUKIT MERAH | 32,219.2 | 32,250.1 | +0.0074 |
| EAST REGION | CHANGI | 26,173.8 | 26,188.2 | +0.0044 |
| CENTRAL REGION | KALLANG | 18,431.5 | 18,416.4 | −0.0036 |
| WEST REGION | TUAS | 23,698.3 | 23,714.1 | +0.0035 |
| WEST REGION | PIONEER | 20,870.4 | 20,885.3 | +0.0033 |

- **单块最大变化 = 0.0130 pp**；块份额 L1/2 = 0.0004。⇒ **泄漏在空间上高度分散，无"某一块被系统性搬走"的集中伪影。**

---

## 4. 独立 OD 的两个选项

| 选项 | 状态 | 速度带输入 | 说明 |
|---|---|---|---|
| **① 自由流阻抗 OD（Step 5B）** | **✅ READY** | **无** | `reports/od_prior_5b/prior_od_5b_lambda_*.parquet` 已存在；输入为 `C^FF`；**只需参数化 `build_matsim_population.py` 的 `PRIOR_DIR`** 即可生成对应 car-only 人口 |
| ② AM 留出（hold-out） | ⚪ NOT_BUILT | 部分 | 只用一部分 AM 快照建阻抗/OD、余下作验证；需重建 AM 阻抗+OD 两轮，成本高、验证集仅 1 天 |

> ⚠️ **代码层面唯一障碍**：`scripts/od/build_matsim_population.py` 把 `PRIOR_DIR = Path("reports/od_prior_5c1")` **写死**（第 16 行）。做独立需求臂需要给它加一个 `--prior-dir` 参数，或建一个只改该常量的变体脚本——**注意这属于"需求侧变更"，不是"网络变更"**。

---

## 5. 对 E-SB-02 的含义（★设计要点）

1. **E-SB-02C（夜间自由流臂）不必因泄漏而推翻**：泄漏仅 3.49%，且不改变总量与 Census 结构。SB-A5 用"夜间→设 freespeed、AM→评价"，**在参数估计层已摆脱 A4 的 AM→AM 循环**；残余的"OD 层 AM 影响"量级已知（3.49%）。
2. **要把"独立拟合"这句话坐实**，只需**一个对照臂**：把需求换成 **Step 5B（无 SpeedBand）**，网络用同一套夜间 freespeed，再对 AM SpeedBand + TrafficFlow 评价。此时**从需求到供给都无 AM 观测输入**，AM 速度拟合才是真正样本外。
3. **两个臂的差 = 泄漏的"下游影响"**：
   - 臂 α：`v1.0 需求(5C.1) + 夜间网络`
   - 臂 β：`5B 需求(无 SpeedBand) + 夜间网络`
   - `Δ(α, β)` 就是"AM 先影响车辆去哪走"对最终指标的实际影响。若 `Δ` 很小，则 E-SB-02C 的结论对泄漏稳健；若很大，则必须用 β 口径报告。
4. **不得把 3.49% 说成"无泄漏"**：它是**可测的**；正确表述是"**已量化、可隔离、可用独立 OD 对照消除**"。

---

## 6. 限制与红线

- 本审计**只读**：未改 v1.0 / 5C / 5C.1 / 5B / crosswalk / TrafficFlow / SpeedBand 原始值。
- **Level 2 未解**：`TrafficFlow`=2025-11 与 `SpeedBand`=2026-05 **不同期**；且 λ、`SCALE` 曾用 TrafficFlow 选定 ⇒ 即便换成 5B 需求，流量拟合仍是**样本内**。要称"正式联合校准"，需**同期** TrafficFlow+SpeedBand 数据 + 留出未参与构建的日期。
- ⛔ 不因"泄漏小"就跳过对照臂；⛔ 不把"独立 OD 对照"当成"数据同期"的替代。

---

## 7. 门禁汇总

| 门 | 内容 | 结果 |
|---|---|---|
| L1 | AM 阻抗确由 SpeedBand 构建（332×332、可达、覆盖>0） | ✅ cov_len=0.383 |
| L2 | 最终 v1.0 需求来自 5C.1（携带 AM） | ✅ `population_lambda_0p075.xml.gz` |
| L3 | 本脚本重算 TV 与既有产物逐位一致 | ✅ max\|Δ\|=8.33e-17 |
| L4 | 泄漏存在且可测（TV>0） | ✅ 3.49% |
| L5 | 泄漏量级为"小"（TV<10%） | ✅ 3.49% < 10% |
| L6 | 泄漏空间分散（单块<0.5 pp） | ✅ max=0.0130 pp |
| L7 | Step5B（无 SpeedBand）OD 已存在 | ✅ ΣT=1,935,235 |

**⇒ `verdict = LEAKAGE_QUANTIFIED`。**

---

## 8. 产物清单

| 文件 | 内容 |
|---|---|
| `leakage_summary.json` | 通道/量级/空间/选项/门禁（机器可读） |
| `leakage_by_lambda.csv` | 5 组 λ 的 TV（重算 vs 既有）+ 区内份额变化 |
| `leakage_top_blocks.csv` | λ=0.075 的 Top12 变化块 |

---
*⛔ 本轮：零仿真、零冻结件改动；未产生 v1.1。*
