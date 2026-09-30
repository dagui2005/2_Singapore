# PREREG_7_9D-0 — Access-System Delay-Trapping Audit（预注册，读取任何仿真输出之前冻结）

> **步骤**：7.9D-0（零仿真 · 只读 · 不改 network · 不跑 MATSim · 不产生 v1.1）
> **上游**：7.9C-1 `SPILLBACK_CHANNEL_INTACT__DELAY_TRAPPED_OFF_MAINLINE`
> **冻结时间**：2026-09-20（本文档 sha256 见 §11，写入后不得再改数值口径）
> **纪律**：本文件冻结后，才允许读取 `linkstats` / `output_plans`。若冻结后被修改，全部 D-0 结果作废。

---

## 0. 非目标（Non-goals）

1. ⛔ 不回答泛问「接入子系统为什么堵」。只回答 §1 的窄问。
2. ⛔ 不修改 `network` / `capacity` / `OD` / 靶场 / `SCALE`。
3. ⛔ 不重新运行 MATSim，不产生 `v1.1`。
4. ⛔ 不以 `demand↑` 或「砍容量」制造拥堵（沿用 §工程纪律）。
5. ⛔ 任何 CTE 分析**禁止**使用 `"CTE" in name.upper()` 掩码（该掩码在 v1.0 网络命中 **0** 条，会静默退化）。

---

## 1. 冻结问题（窄化后）

> **为什么这些回溢无能的 `service` / `connector` 短链能够持续吸收大量延误，却不能把交通压力反馈到主线？**

拆成三个接口，逐一定量：

$$
\text{主线容量}\;\leftrightarrow\;\text{接入拓扑}\;\leftrightarrow\;\text{局部储存}
$$

- **① 接入口是否存在拓扑「单向阀」**：`service → mainline` 只有单一出口 / lane transition / 方向限制，使压力无法反向传播。
- **② `service`/`connector` 局部储存是否过浅**：是**合理的短接入段**，还是**网络表达 / 容量设定导致的异常薄储存**。
- **③ 主线—接入之间是否缺少真实排队耦合**：`service` link 堵死后，QSim 是否只能在该局部 link/节点消化，无法对上游 `mainline` 形成 backward propagation。

---

## 2. 必须先做的 Base-rate 控制（D0，关键前置）

C-1 报告的「`service` 吃掉 **94.36%** 延误」是在**全网口径**下得到的，而 `service` 本身占 **64.95%** 的 link、**58.6%** 的 km。**位置/份额类指标必须先做共同因子证伪**（§6 教训 95–97），否则会把「网里本来就 65% 是 service」误读成「service 异常吸延误」。

因此 D-0 **必须**先给出：

| 量 | 定义 |
|---|---|
| `km_share[c]` | 类别 `c` 的公里占比 |
| `link_share[c]` | 类别 `c` 的 link 数占比 |
| `delay_share[c]` | 类别 `c` 的延误占比（V1 = v1.0） |
| **`ratio[c]`** | **`delay_share[c] / km_share[c]`**（>1 = 相对 km 富集） |
| `ratio_if[c]` | 同上，但**限定在主线邻域**（§3.1 的 `IF_UP` ∪ `IF_DOWN`） |

判读基线（预先固定）：
- `ratio ≤ RATIO_BASE(1.50)` ⇒ **base-rate 可解释**，不得宣称「强烈富集」。
- `ratio ≥ RATIO_CONC(2.50)` ⇒ 真实富集。

---

## 3. 三条审计链（预先冻结定义）

### 3.0 拓扑原语（BFS，多源，非递归 —— v1 递归已证实会栈溢出）

以 link 为单位。`feeders(i) = inb(frm[i])`，`succ(i) = outb(to[i])`。

- **`d_up[i]`** = 从 link `i` **向上游**走，到达任一 `mainline` link 所需的最小 link 跳数。
  `d_up = 0` 若 `i` 本身是 mainline；`d_up = 1` 若 `feeders(i)` 中含 mainline。
  BFS：源 = mainline links（0）；当 `k` 定型，对 `i ∈ succ(k)` 取 `d_up[i] = d_up[k]+1`。
  → 语义：**`i` 上的排队要往上游传播多少跳才能压到主线**。
- **`d_down[i]`** = 从 link `i` **向下游**走，到达任一 `mainline` link 所需的最小 link 跳数。
  BFS：源 = mainline links（0）；当 `k` 定型，对 `j ∈ feeders(k)` 取 `d_down[j] = d_down[k]+1`。
  → 语义：**`i` 上的车要往下游走多少跳才能回到主线**。

**邻域定义**：
- `IF_UP` = `{ i : 0 ≤ d_up[i] ≤ D_IF }`（压力**能**在 D_IF 跳内触达主线的 link 集合）
- `IF_DOWN` = `{ i : 0 ≤ d_down[i] ≤ D_IF }`
- `INTERFACE` = `IF_UP ∪ IF_DOWN`（主线邻域，D-0 的主分析域）
- `OFF_MAINLINE` = 补集

### 3.1 D1 — 单向阀审计（拓扑）

1. **节点级 sink-valve**：节点 `x` 满足 `(∃ mainline in-edge) ∧ (∃ access out-edge) ∧ (∄ mainline out-edge)`
   → 主线可以把车倒进 `x`，`x` 却**无法**把车送回主线。
   - `sink_valve_share_interface` = `INTERFACE` 内节点中 sink-valve 占比。
2. **单出口**：上述 valve 节点出度 == 1 的占比。
3. **Lane transition**：valve 节点 `max(lanes_in) > min(lanes_out)` 的占比。
4. **方向限制**：v1.0 网络无 `oneway`/`access` 字段 ⇒ 以 `d_up` / `d_down` **不对称性**作为代理：
   `asym_share` = `INTERFACE` 内 `|d_up − d_down| ≥ 2` 的 link 占比。

### 3.2 D2 — 局部储存深度审计（容量 / 几何）

对节点 `x`：`storage_veh(x) = Σ_{o ∈ outb(x)} len[o] · lanes[o] / CELL`；
`inflow_veh_s(x) = Σ_{i ∈ inb(x)} cap[i] / 3600`；`fill_time_s(x) = storage / inflow`。

1. `fill_time_s` 分布（`INTERFACE` 节点 vs 全网节点）：p10/p25/**median**/p75/p90。
2. `share_fill_lt_REQ` = `fill_time < REQ_FILL_S(30 s)` 的节点占比 → 判「薄储存」。
3. **容量赋值确定性检验（判「是否网络表达伪影」的决定性检验）**：
   `ndistinct_cap_per_lane[c]` = 类别 `c` 内 `cap/lanes` 的**不同取值个数**。
   若 == 1 ⇒ 该类别容量是**按 (highway, lanes) 查表赋值**，**不随地理/几何变化**
   ⇒ **薄储存是建模设定，不是涌现结果**。
4. `cap_ratio_ref[c] = median(cap/lanes)[c] / LANE_CAP_REF(1800)`：`service` 若 ≈0.22 ⇒ 容量被压到参考值的 22%。
5. `link_storage_veh` 中位（按类别）。

### 3.3 D3 — 排队耦合审计（backward propagation 可达性）

1. **延误加权 `d_up` 分布**：`share_up_le_DIF`、`share_up_gt_DIF`。
   → 决定量：**延误到底落在「能碰到主线」的域里，还是落在构造上就碰不到的域里**。
2. **延误加权 `d_down` 分布**（同上）。
3. `delay_weighted_d_up`（延误加权的平均上游跳数）按类别。
4. `d_up` = ∞（上游完全无 mainline 可达）的 link 占比 —— 应为 0，作为 sanity gate。

### 3.4 D4 — 终端暴露（描述性，**无裁决权**）

从**冻结的输入人口** `matsim_final_7_6h/populations/pop_W01/population_lambda_0p075.xml.gz`
统计每条 agent 的起/终 link（不使用 `output_plans`，不使用 `linkstats`），给出：

- `start_link_class_share` / `end_link_class_share`
- `terminal_is_service_share` = 起或终为 `service` 的 trip 占比
- 与 `km_share` / `link_share` 对照

> **规则**：D4 仅作**支持性证据**，**不得改变 §4 的主判据**。若人口文件不可读，D4 报 `UNAVAILABLE`，不影响 verdict。

---

## 4. 冻结常量与阈值（冻结后不得改）

```
CELL          = 7.5      # m / veh of storage（沿用 C-1）
D_IF          = 3        # 主线邻域 = link 跳数 ≤ 3
D_IF_SENS     = (1, 5)   # 敏感度
REQ_FILL_S    = 30.0     # 储存须能容纳 ≥30 s 的到达流，否则判「薄」
LANE_CAP_REF  = 1800.0   # veh/h/lane 参考容量
SHORT_M       = 20.0     # 超短 link
VALVE_THR     = 0.10     # sink-valve 在 INTERFACE 节点中的占比阈值
THIN_THR      = 0.60     # fill_time < REQ 的 INTERFACE 节点占比阈值
RATIO_BASE    = 1.50     # delay_share / km_share ≤ 1.5 ⇒ base-rate 可解释
RATIO_CONC    = 2.50     # ≥ 2.5 ⇒ 真实富集
PRIOR_CAND    = 80.0
CLASSES       = (motorway, ramp, connector, service, other)
```

`class` 定义**严格沿用 B-1**：
`ramp = {motorway_link, trunk_link}`；`connector = 其余 *_link`；`service = service`；
`motorway = {motorway, trunk}`；`other = 其余`。

---

## 5. 门控清单（D0.01–D0.15）

| id | 内容 | 通过条件 |
|---|---|---|
| D0.01 | 网络来自冻结 v1.0 缓存 | `links=693575` 且 `km≈15126.5` |
| D0.02 | 类别掩码非退化 | 5 类命中数全 > 0 且打印 |
| D0.03 | `d_up` BFS 完成 | 有限值覆盖 100%，`min=0` |
| D0.04 | `d_down` BFS 完成 | 有限值覆盖 100%，`min=0` |
| D0.05 | Base-rate 表产出 | `km_share` / `link_share` / `delay_share` / `ratio` 齐全 |
| D0.06 | D1 sink-valve 产出 | 命中数打印；**允许为 0**，但必须显式记录 |
| D0.07 | D1 单出口 / lane drop 产出 | 数值有限 |
| D0.08 | D2 fill_time 产出 | `INTERFACE` 节点数 > 0 |
| D0.09 | D2 容量确定性检验产出 | `ndistinct_cap_per_lane` 全类别有值 |
| D0.10 | D3 延误加权 `d_up` 分布产出 | 权重和 > 0 |
| D0.11 | D3 延误加权 `d_down` 分布产出 | 权重和 > 0 |
| D0.12 | 候选单元先验复现 | `candidates == 5490` |
| D0.13 | CTE 名称口径正确 | `Central Expressway` 命中 **603** links（≠0，且非掩码旧值） |
| D0.14 | D4 终端暴露（或 UNAVAILABLE） | 读取成功或显式 UNAVAILABLE |
| D0.15 | 冻结产物未变 | `changed == 0` |

---

## 6. Verdict 规则（主判据，分支互斥、按序判定）

```
share_if   = delay_share(d_up <= D_IF)          # 延误落在主线邻域的比例
share_off  = delay_share(d_up >  D_IF)          # 落在构造上碰不到主线的域
thin_share = fill_time < REQ_FILL_S 的 INTERFACE 节点占比

if share_if >= 0.50 and thin_share >= THIN_THR:
        v = 'ACCESS_INTERFACE_DELAY_DOMINANT__THIN_STORAGE'
elif share_off >= 0.90:
        v = 'DELAY_TRAP_OFF_MAINLINE_BY_CONSTRUCTION__BASE_RATE_DOMINATED'
elif share_if >= 0.50 and thin_share < THIN_THR:
        v = 'ACCESS_INTERFACE_DELAY_DOMINANT__STORAGE_NOT_THIN__LOOK_ELSEWHERE'
else:
        v = 'INDETERMINATE'
```

**独立旗标（无论主判据为何，都必须报告）**：

| 旗标 | 条件 | 含义 |
|---|---|---|
| `VALVE_PRESENT` | `sink_valve_share_interface ≥ VALVE_THR` | ① 单向阀成立 |
| `THIN_STORAGE` | `thin_share ≥ THIN_THR` | ② 薄储存成立 |
| `CAP_DETERMINISTIC` | 所有类别 `ndistinct_cap_per_lane == 1` | ② 薄储存 = **查表设定**，非涌现 |
| `COUPLING_ABSENT` | `share_off ≥ 0.90` | ③ 排队耦合缺失（构造性） |
| `BASE_RATE_ARTIFACT` | `ratio[service] ≤ RATIO_BASE` 或 `ratio_if[service] ≤ RATIO_BASE` | 富集为口径假象 |

---

## 7. 反模式（Anti-patterns，命中即视为结论不可用）

1. ⛔ 用**全网** `delay_share` 直接宣称「service 异常吸延误」而不报 `ratio`（§2）。
2. ⛔ 用**单跳** `ret_comp` 当「回溢无能」的充分证据而不给 `d_up` 多跳分布（C-1 的 K3 是单跳口径，D-0 必须升维）。
3. ⛔ 把 `cap=400 veh/h/lane` 当**涌现**结果；必须先跑 `ndistinct_cap_per_lane` 检验。
4. ⛔ 子集取用后不打印命中数（§97 静默不匹配）。
5. ⛔ 让 D4（终端暴露）影响主判据。
6. ⛔ 以「薄储存」为理由直接提议改 network —— D-0 只**证明**，不**修**。
7. ⛔ 沿用 `"CTE" in name.upper()`。

---

## 8. 数据来源与读取顺序纪律

| 顺序 | 文件 | 性质 | 何时可读 |
|---|---|---|---|
| 1 | `scripts/od/_cache_network_7_9c0.npz` | 结构（v1.0 网络） | 预检已读 |
| 2 | `scripts/od/_cache_link_unit_7_9b1.npz` | 结构 | 预检已读 |
| 3 | `reports/structural_junction_cluster_audit_7_9c0/c0_junction_clusters.csv` | 结构（C-0 先验） | 预检已读 |
| 4 | `matsim_final_7_6h/populations/pop_W01/population_lambda_0p075.xml.gz` | **输入人口** | **本文件冻结后** |
| 5 | `matsim_final_7_6h/.../W01_rc_min.19.linkstats.txt.gz` | **仿真输出** | **本文件冻结后** |
| 6 | `matsim_kw_7_9b1/.../W01_kw.19.linkstats.txt.gz` | 仿真输出（B-1） | **本文件冻结后** |

**预检已确认的结构事实（不构成结论，仅供设计）**：
- 节点级 sink-valve 全网仅 **13** 个；mainline-in 节点 8,567 vs mainline-out 8,566 ⇒ 主线**几乎完全可逆**。
- 直接由 mainline 喂养的 link：`service` **0.049%**、`connector` **0.007%**、`ramp` 3.629%。
- `cap` 按 `(highway, lanes)` **确定赋值**：`service`=400、`residential`=700、`tertiary`=900、`secondary`=1200、`primary`=1500、`motorway`=1800（veh/h/lane），组内 `min=max`。
- `service` 自由流 **20 km/h**（p10=p90），中位长 **8.9 m**、中位车道 1、中位储存 **1.55 veh**。

---

## 9. 交付物

| 文件 | 内容 |
|---|---|
| `PREREG_7_9D-0.md` | 本文件（冻结） |
| `scripts/od/audit_access_delay_trapping_7_9d0.py` | 审计引擎 |
| `d0_audit_summary.json` | 全量结果 |
| `d0_checks.csv` | 门控清单 |
| `d0_gates.json` | 门控 + verdict |
| `d0_base_rate.csv` | §2 base-rate 表 |
| `d0_d1_valve.csv` | D1 |
| `d0_d2_storage.csv` | D2 |
| `d0_d3_coupling.csv` | D3 |
| `d0_d4_terminal.csv` | D4 |
| `REPORT_7_9D0.md` | 报告 |

---

## 10. 与冻结态的关系

- `v1.0` 仍是唯一冻结模型；D-0 **不回灌**、不产生 v1.1。
- 上游 C-1 verdict `SPILLBACK_CHANNEL_INTACT__DELAY_TRAPPED_OFF_MAINLINE` 保持。
- **CTE 更正口径（强制）**：`Central Expressway` = **603 links / 104.57 h (2.19%)**（v1.0）→ **56.68 h (0.45%)**（KW）。B-1 曾报告的 24.22 h 实为 Changi∪Tampines，作废。
- 主线序列：`… → 7.9C-1 ✓ → 7.9D-0（本步）→ 7.9D（待定）`；`7.9A-1` 继续降级。

---

## 11. 冻结凭证

- 冻结时刻：2026-09-20
- `PREREG_7_9D-0.md` sha256：写入后由引擎在门控 D0.13 前置校验中重新计算并记录（见 `d0_gates.json.prereg_sha256`）。
- 若实际计算值与报告记录不一致 ⇒ verdict 视为 `PREREG_TAMPERED`，全部 D-0 结果作废。
