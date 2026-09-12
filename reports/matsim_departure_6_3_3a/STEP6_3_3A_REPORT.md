# Step 6.3.3A —— TrafficFlow 驱动的 AM 出发时刻剖面（Departure-Time Profile）

> 状态：**PASS** ｜ 日期：2026-09-12 ｜ 脚本：`scripts/od/build_departure_profile_6_3_3a.py`
> 门控定位：**只改"什么时候走"，不改 OD 总量、OD 空间结构、Home/Work link 与 λ**

---

## 1. 这一步解决什么问题

Step 6.3 / 6.3.2 暴露的结构性缺口：**6.2B population 中全部 200,000 个 agent 都在 `08:00:00` 同时出发**。

```text
07:00–08:00       0        ← HRS7-8 恒为 0
08:00–09:00   200,000     ← 全部需求挤在一个小时里
```

这构成一个**人为的瞬时脉冲**，导致单迭代 QSim 出现：

- 平均通勤时间 **61.8 min**
- 网络均速 **~19 km/h**

这两个数**不能**当作真实 AM 拥堵水平来解释。而 LTA 观测按小时统计（07–08、08–09），当前口径等于把**两个观测小时与一个 08:00 脉冲硬拼**，因此 `q^sim vs q^obs` 的逐小时比较在 6.3 中不成立。

**6.3.3A 的唯一目标**：把单脉冲替换为 **TrafficFlow 驱动的 07–08 / 08–09 两小时 departure profile**，使逐小时比较第一次有意义。

---

## 2. 方法（为什么不是"拍脑袋平均分配"）

### 2.1 为什么不能从 Census 直接得到出发时刻

现有 Census 2020 数据**不含出发时刻维度**：

| 来源 | 维度 | 用途 |
|---|---|---|
| `outputFile (3).xlsx` T10 / Table 117 | **PA × 上班行程时间** | ❌ 不含出发时刻 |
| `outputFile (5).xlsx` T15 / Table 133 | **全国就业居民 × 交通方式 × 上班行程时间** | ❌ 不含出发时刻 |
| Table 118 | Residence Region × Workplace PA × Mode | ❌ 不含 departime time |

Census 只有 7 个行程时间分箱：`Below 15 / 15–29 / 30–44 / 45–59 / 60–89 / 90–119 / 120 & Over`。用"假设 9 点上班 → 倒推出发时刻"会同时踩到**宽泛分箱 + 开放尾箱 + 到岗时刻不齐**三个坑，**不采用**。

> **长期口径**：真正的 departure-time 数据应优先找 LTA **Household Travel Survey（HTS）**——它是全国代表性调查，明确采集 "how, when and where Singaporeans travel"，并用于更新 LTA 交通模型。HTS 数据未纳入本项目数据源，故本轮不依赖它。

### 2.2 采用的方案：观测驱动的网络时间形状先验

用项目已有的、真实的 **`TrafficFlow_Data.json`**（LTA 官方定义为 **hourly average traffic flow**）估计 AM 需求的时间形状。

**稳健代表值**：先按 `LinkID × Date × Hour` 取均值，再对每个 `LinkID × Hour` 取**工作日逐日中位数**（不把所有日期原始记录简单相加），得到每链路的小时代表流量 $\tilde q_{l,h}$。

**全网时间比例**：

$$
s_7=\frac{\sum_l \tilde q_{l,7}}{\sum_l\left(\tilde q_{l,7}+\tilde q_{l,8}\right)},
\qquad s_8=1-s_7
$$

**分配到 agent**：

$$
N_7=\mathrm{round}(s_7 N),\qquad N_8=N-N_7,\qquad N=200{,}000
$$

**小时内随机微扰**：每个 bin 内均匀随机到**秒级**，避免整点同时出发：

```text
07:00:00 – 07:59:59
08:00:00 – 08:59:59
```

> ⚠️ 口径声明：这是 **network-observed temporal shape prior（观测驱动的网络时间形状先验）**，**不是**居民 departure-time 观测，也**不独立于 TrafficFlow**。论文中据此表述。

### 2.3 结果（实测）

| 时段 | 网络流量指数（Σ 链路中位） | 时间占比 |
|---|---:|---:|
| 07:00–08:00 | 2,301,067.5 | **48.7103 %** |
| 08:00–09:00 | 2,422,915.9 | **51.2897 %** |

工作日样本：2025-11-03 起共 **20 个工作日**，可用链路 **1,311** 条/小时。

---

## 3. 写回 MATSim 的方式（严格保持冻结量）

脚本**只修改** `home` 活动的 `end_time`：

```xml
<!-- 修改前 -->
<activity type="home" link="e410217_410218" end_time="08:00:00" />
<!-- 修改后（示例） -->
<activity type="home" link="e410217_410218" end_time="07:12:03" />
```

- **不是**修改 `<leg>`，**不是**新增计划时间字段，**不是**重写 `<person>` 的 attributes。
- 采用**流式逐行**替换（gzip 读 → gzip 写），不反序列化整棵树。
- **基线 population 用 `reports/matsim_population_6_2b_connected/`**（6.3a 连通性修复版），而非原始 6.2B——因为 6.3.4 重跑 MATSim 时 car 连通性检查会 abort 未修复版本。这是**必要**选择。

**严格保持不变**（validation 中列为 `frozen_quantities`）：

```text
OD trips  ·  expansion_factor  ·  home_link  ·  work_link  ·  lambda
```

---

## 4. 校验结果（`departure_profile_validation.json`）

**STATUS = PASS**。三个 λ 完全一致（λ 不影响时间剖面）：

| 项 | λ=0.05 | λ=0.075 | λ=0.10 |
|---|---:|---:|---:|
| agents | 200,000 | 200,000 | 200,000 |
| **ΣEF（真实出行量）** | **459,794.0** | **459,794.0** | **459,794.0** |
| 目标时间占比 s7 / s8 | 0.4871 / 0.5129 | 同 | 同 |
| **EF 加权实现占比（07–08 / 08–09）** | 0.4868 / 0.5132 | 0.4877 / 0.5123 | 0.4873 / 0.5127 |
| agent 数 07–08 / 08–09 | 97,421 / 102,579 | 同 | 同 |
| 出发时间范围 | 07:00:00 – 08:59:59 | 同 | 同 |
| missing_times / duplicate_agents | 0 / 0 | 0 / 0 | 0 / 0 |
| XML 改写 persons / home activities | 200,000 / 200,000 | 同 | 同 |

**独立反查（直接从输出 XML 统计，非读 CSV）**：

```text
home end_time 计数      = 200,000
小时分布 {7: 97421, 8: 102579}
实测占比 h7=0.4871  h8=0.5129
残留 "08:00:00"         = 35   （=随机击中整点的期望数，可忽略）
work 活动含 end_time    = 0    （未被误改 ✓）
```

**EF 加权占比 ≈ 网络时间占比**（0.4868–0.4877 ≈ 0.4871）——直接证明时间剖面**只改变出发时刻、不改变 OD 总量**。

---

## 5. 结论与边界

1. **单脉冲已消除**：`HRS7-8 = 0` 的问题在 6.3.4 重跑后应消失，07–08 与 08–09 都将有真实流量。
2. **OD / λ 未动**：ΣEF 严格 = 459,794，home/work link、OD 空间结构、λ 全部冻结不变。
3. **仍待做**：
   - **6.3.3B**：检查时间分布对 MATSim link flow 是否真正生效，并重跑 3 个 λ 的 AM assignment（逐小时 `q^sim_{a,7-8} vs q^obs_{a,7-8}`、`q^sim_{a,8-9} vs q^obs_{a,8-9}`）。
   - **Census T10 / T15 行程时间分布**：作为**独立合理性检验**（检查生成的 MATSim travel time 是否落在合理区间），**不用于反推出发时刻**。
4. **不使用**：`TrafficSpeedBands`（适合构建 AM 速度层，非出发时刻）；Census "Travelling Time"（非 departure time）。

---

## 6. 产物清单（`reports/matsim_departure_6_3_3a/`）

| 文件 | 内容 |
|---|---|
| `departure_profile.csv` | 07/08 两小时的全网时间占比与网络流量指数 |
| `trafficflow_link_hour_basis.csv` | 每 LinkID×Hour 的工作日稳健代表流量（1,311×2 行） |
| `agent_departure_assignment_lambda_0p{050,075,100}.csv` | 各 λ 的 agent 级出发时刻（原字段全保留 + `departure_time_s` / `departure_time`） |
| `population_lambda_0p{050,075,100}.xml.gz` | **6.3.4 输入**：改好 `home end_time` 的 MATSim population |
| `departure_assignment_summary.csv` | 三 λ 汇总（占比、计数、EF、XML 更新数） |
| `departure_profile_validation.json` | 校验（STATUS=PASS，profile + summary + frozen_quantities + 口径声明） |

---

## 7. 冻结关系

| 阶段 | 状态 |
|---|---|
| 3B.1 Attraction / 4 网络 / 5B / 5C.1 / 6.1 / 6.2 / 6.2B | **冻结** |
| 6.3.2 断面 crosswalk 校验 | **PASS（疑点已排除）** |
| **6.3.3A 出发时刻剖面** | **本轮 PASS** |
| 6.3.3B 重跑 + 逐小时对照 | 待做 |
| 6.3.4 → 7 λ/OD/capacity 校准 | 未开始 |
| **λ** | **仍未冻结** |
