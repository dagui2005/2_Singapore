# Step 7.9I · 阶段冻结收口档案（CLOSURE）

- **阶段**：7.9I —— 观测域尺度审计 + M1 可达性审计 + 「观测对象 ↔ MATSim 对象」三刀闭环
- **判决**：**`7.9I_FROZEN_CLOSED` → `READY(O1)` → `O1 ✓`**（2026-09-30 更新；O1 执行报告见 `STEP7_9I_O1_REPORT.md`）
- **冻结日期**：2026-09-29
- **冻结依据**：用户裁定「**暂停推进，先冻结收口**」（承接上一轮正式裁定）
- **性质**：全链 **零仿真 / 只读**；**未触碰** v1.0 任何交通动力学参数、靶场、交叉表、OD、network、capacity、prereg、阈值
- **总门数**：**70/70**（6 个引擎，`n_fail=0`）；负例 **4/4 fired × 4 个正式引擎**
- **产物根**：`D:\Luan\2026-05\2_Singapore\reports\corridor_scale_audit_7_9i\`

---

## 0. 冻结声明（可直接引用的阶段结论）

> **当前主要问题不能继续归因于采样容量折减，也不能直接归因于 MATSim 全网需求不足。现有证据表明，评价域存在显著的 1:K 映射尺度错配；在消除该尺度效应后，仍存在少数高影响快速路断面的真实低载问题，其主要表现为映射链断裂、平行替代路径及特殊道路设施对象不一致。**
>
> —— 用户 2026-09-29 正式裁定（本档案即为该裁定的**证据交付**）

**7.9I 对该结论的贡献**：把上述三段话**逐段量化**，并**逐段指明机制**：
① 「1:K 尺度错配」= `ratio_simobs 5.2818` vs `K_pooled 5.5434` ⇒ 归一 **0.953**（「sim 大 5 倍」是**计数基数错配**，不是需求）；
② 「少数真实低载」= 去尺度残差 `norm < 0.5` 的走廊中，**前 3 条担 22.42% 的 obs**（KPE 隧道 / ECP / KPE）；
③ 「映射链断裂 / 平行替代 / 特殊设施」= M1 五分类与 B(b) 三分类**一一落地到断面卡片**。

---

## 1. 交付清单（全链 7 脚本 · 6 判决 · 70 门）

| # | 脚本 | 判决 | 门 | 耗时 | 性质 |
|---|---|---|---|---|---|
| 0 | `audit_corridor_scale_7_9ia.py` | `CORRIDOR_SCALE_AUDIT_READY` | **20/20** | 38.4 s | 7.9I-A 主引擎 |
| 1 | `audit_m1_accessibility_7_9ib.py` | `M1_ACCESSIBILITY_AUDIT_READY` | **12/12** | 46.3 s | 7.9I-B 主引擎 |
| 2 | `audit_kpe_ecp_object_7_9ia2.py` | `KPE_ECP_OBJECT_AUDIT_READY` | **18/18** | 41.6 s 冷 / 31.3 s 热 | 第二刀·第一步（A2） |
| 3 | `audit_chain_reaggregation_7_9ia1.py` | `CHAIN_REAGGREGATION_READY` | **8/8** | 20.3 s | 第二刀·第二步（A1） |
| 4 | `audit_zero_flow_ledger_7_9ibb.py` | `ZERO_FLOW_PARALLEL_LEDGER_READY` | **6/6** | 19.7 s | 第三刀（B(b)） |
| 5 | `audit_bb_direction_probe_7_9ibbp.py` | `BB_DIRECTION_PROBE_READY` | **6/6** | 25.5 s 冷 / 11.0 s 热 | **后验探针**（`EXPLORATORY_POST_HOC`） |
| — | `build_figs_7_9i.py` | — | — | — | 出图 `fig_7_9i_corridor_scale_and_m1.png` |

**合计门数**：20 + 12 + 18 + 8 + 6 + 6 = **70**；`n_fail = 0`（全链）。

### 报告（预注册 + 结果）

| 文件 | 字节 | 说明 |
|---|---|---|
| `PREREG_7_9I.md` | 9,670 | 阶段预注册 |
| `PREREG_7_9I_A2.md` | 7,314 | 第二刀·第一步预注册（运行前冻结） |
| `PREREG_7_9I_A1.md` | 5,218 | 第二刀·第二步预注册 |
| `PREREG_7_9I_Bb.md` | 4,243 | 第三刀预注册 |
| `STEP7_9I_REPORT.md` | 15,577 | 7.9I-A + 7.9I-B 主报告 |
| `STEP7_9I_A2_REPORT.md` | 11,541 | A2 实体核验报告 |
| `STEP7_9I_A1_REPORT.md` | 7,363 | A1 链重聚合报告 |
| `STEP7_9I_Bb_REPORT.md` | 12,536 | B(b) 平行边记账报告（**含方向性后验核验**） |

### 数据产物

| 引擎 | 卡片 / 表 | 汇总 / 判决 | 运行日志 |
|---|---|---|---|
| 7.9I-A | `section_scale_v10.csv`(85,452) · `section_scale_A1.csv`(88,688) · `corridor_scale_v10.csv`(24,774) · `corridor_scale_A1.csv`(25,585) | `corridor_scale_summary.json`(10,425) · `_corridor_audit_7_9ia.json`(11,802) | `_run_7_9ia.log`(2,943) |
| 7.9I-B | `m1_cards_7_9ib.csv`(38,704) | `m1_class_summary.json`(4,024) · `_m1_audit_7_9ib.json`(5,370) | `_run_7_9ib.log`(1,529) |
| 7.9I-A2 | `kpe_ecp_entity_cards_7_9ia2.csv`(25,734) | `kpe_ecp_object_summary_7_9ia2.json`(7,095) · `_kpe_ecp_audit_7_9ia2.json`(7,095) | `_run_7_9ia2.log`(2,238) |
| 7.9I-A1 | `a1_chain_cards_7_9ia1.csv`(12,647) | `a1_chain_summary_7_9ia1.json`(6,281) · `_chain_audit_7_9ia1.json`(6,281) | `_run_7_9ia1.log`(1,194) |
| 7.9I-B(b) | `bb_zero_flow_ledger_7_9ibb.csv`(7,695) | `bb_ledger_summary_7_9ibb.json`(4,257) · `_bb_audit_7_9ibb.json`(4,257) | `_run_7_9ibb.log`(1,089) |
| 7.9I-B(b)-P | `bbp_direction_probe_7_9ibbp.csv`(3,481) | `bbp_direction_probe_summary_7_9ibbp.json`(1,951) | `_run_7_9ibbp.log` |
| 图 | `fig_7_9i_corridor_scale_and_m1.png`(206,785) | — | — |

**★已知良性重复（登记，不修改）**：A2 / A1 / Bb 三者的 `*_summary_*.json` 与 `_*_audit_*.json` **md5 全等**
（`6f357f49…` / `6b65888e…` / `86e21605…`）——同一 dict 按两种命名约定落盘，**内容为判决记录的权威副本**。⛔ 收口阶段不重命名、不去重。

---

## 2. 冻结结论清单（C1–C9）

| 编号 | 结论 | 关键数 | 证据 |
|---|---|---|---|
| **C1** | 「sim 是 obs 的 5 倍」**不成立**，是计数基数错配 | `ratio_simobs` **5.2818** / `K_pooled` **5.5434** ⇒ 归一 **0.953** | `corridor_scale_summary.json` |
| **C2** | 修正覆盖率的**不得外推** | 靶场匹配边 3,037 条 / 159.7 km，仅担全网高峰 **6.64%**（v1.0）/ 5.29%（A-1）；严格 1:1 仅 **10.42%** | `flow_share_matched` |
| **C3** | 真缺载**收敛到 3 条走廊** | `norm<0.5` 共 **19 条** / obs **23.08%**；**前 3 = KPE 隧道 0.1172 / ECP 0.1320 / KPE 0.1190，担 22.42%** | `genuine_shortfall_corridors` |
| **C4** | **A2：KPE/ECP 的「8 倍缺载」不成立**；按对象选口径后收敛到 **2.2–2.6×** | `r_mixed` = KPE隧道 **0.385** / ECP **0.388** / KPE **0.465**（vs `norm` 0.117/0.132/0.119） | `STEP7_9I_A2_REPORT §0` |
| **C5** | **A2 决定性判据 `U_UNIT_MISMATCH`**：观测单元 ≠ 仿真单元 | KPE 隧道 **16/19 断面** `vc_max = obs / max_e cap_eff > 1`，最高 **20,342/5,700 = 3.569×**；KPE 隧道剩余偏差 **92.6%（Σobs 加权）** 归此项 | 同上 |
| **C6** | **A1：杠杆是「候选对象选取」不是「统计量」** | `r_med` **0.1187** → `r_sum` 0.2871 → `r_chain(P0)` **0.1881**（冻结匹配集内**几乎无效**，60/60 仍 `C_LOW`）→ **`r_chain(P1)` 0.5556**（重建候选池，缺载倍数 **8.4× → 1.8×**，`C_OK+C_HIGH` 担 Σobs **27.8%**） | `STEP7_9I_A1_REPORT §0` |
| **C7** | **M1 主因 = 映射链缺陷** | 133 节：`X1_CHAIN_DEFECT` **60 节 / obs 69.16%**、`X2_RAMP_OR_STRUCTURE` 40 / 11.37%、`X3_PARALLEL_BYPASS` 22 / 12.40%、`X4_ISOLATED` 9 / 6.22%、**`X0_UNEXPLAINED` 2 / 0.86%** | `m1_class_summary.json` |
| **C8** | **B(b)：38 个零流量断面的主项不是「平行边抢流量」** | `B2_OPPOSITE_ONLY` **22 节 / Σobs 61.72%**（同向有流边仅 **7 条**、反向 **83 条**）；`B1_SAME_DIR_PARALLEL` 10 / 20.73%（`r_par_sum_same` 中位 **1.628**，真平行接住）；`B3_NO_PARALLEL_FLOW` 6 / 17.55% | `STEP7_9I_Bb_REPORT §0` |
| **C9** | **B(b)-P：「映射选错方向」假设被否定** | 38 节共 **152 条匹配边方向一致性 = 152/152 同向、0 反向**（`d_match` 中位 1.8°/5.1°/2.9°）；`B2` 同节点对反向孪生仅 **1/22 节** ⇒ 该设施在 MATSim 中为**单向 way**（对向车行道以**独立节点串**另建） | `bbp_direction_probe_summary_7_9ibbp.json` |

---

## 3. 口径修正与陷阱登记（R1–R5）

| 编号 | 登记项 | 内容 | 处置 |
|---|---|---|---|
| **R1** | **`norm = ratio / K_c` 的隐含前提** | 该式成立**隐含**「一个断面对应的 K 条边承载**同一股车流**（连续有向链）」。A2 已证伪 KPE 隧道前提 ⇒ 除以 K **人为制造并不存在的缺载** | ⇒ 改用 `r_mixed`（链→median / 非链→sum）；A2 报告 §0 |
| **R2** | **★坐标陷阱** | `lta_section_geometry()` 的 `mx/my` 是**局部等距平面米**（`lon×111320·cos(lat0)`，原点 (0,0) ⇒ x≈1.155e7、y≈1.41e5），**与全网图 SVY21（EPSG:3414，x≈2.7e4）不同源**。⛔ 绝不能与 `Graph.ex/ey` 或 `SEC_GEO_7_6C.mid_x/mid_y` 做半径/距离运算；其 `bear`/`len_m` 与 CRS 无关可照用 | 已加**防御性 docstring**；新探针加 `G-P0` 坐标同源门（样例 48525 `mid_x=28742.8`）；已 grep 核实 **A2/A1/Bb 三引擎均正确使用 `SEC_GEO_7_6C`**，未受影响 |
| **R3** | **判据退化（不静默改阈值）** | `G-A1-7` 实测 median rel diff = **0.0056**（冻结匹配集内路径分量代表值 ≡ canonical `median`，**构造性恒等**）。**不静默改阈值**，记入 `rec["degenerate_criteria"]`，有效对比改用 `G-A1-7'`（P1 口径，实测 **1.070**），标签 `EXPLORATORY_POST_HOC` | `PREREG_7_9I §4` 纪律 |
| **R4** | **退化诊断披露** | `all_endpoints_in_giant` 恒 True（全网**单一**弱连通分量 421,406/421,406）、`dangling` 恒 0 | 已写入 `degraded_diagnostics`，不得当作证据 |
| **R5** | **冻结判据命中 100% = 判据缺陷** | `M1-E_SPECIAL_FACILITY` 命中 **133/133**（无区分度）⇒ 标 `EXPLORATORY_POST_HOC`，须后验修订 | `m1_class_summary.json` |

---

## 4. 未解项与移交（OPEN）

| 编号 | 未解项 | 归属 | 处置 |
|---|---|---|---|
| **O1** | **`B2` 需要「车行道对（carriageway pair）」层**：区分「同节点对双向 way」与「独立节点串单向 way」 | 零仿真域 | **待裁定**归属下一阶段 |
| **O2** | `SIGNAL_MECHANISM_ABSENT`：config 与网络 **0 信号令牌**、`contrib.signals` 不在 classpath ⇒ 与 `0.434977` **独立且未处理** | 仿真域 | **本轮不碰**（触底线） |
| **O3** | `CALIBER_FRAGILE`（raw 45.90 vs corr 94.36）；`CALIBER_GAP_DOMINATES`（`cov(V1/V3)=0.6502`） | 数据侧 | 需 LTA 分车型 / HTS 观测口径核验 |
| **O4** | `B3_NO_PARALLEL_FLOW` 6 节（Σobs 17.55%）：邻近**既无同向也无反向**承载对象 | 连通性 / 需求 | 留待后续 |
| **O5** | `X0_UNEXPLAINED` **2 节 / 0.86%** | — | 量级可接受，登记 |

---

## 5. 复现方法（一键顺序）

```bash
PY="C:/Users/LQP/miniconda3/python.exe"        # ⚠️ 裸 python 无 pandas
R="reports/corridor_scale_audit_7_9i"
cd "D:/Luan/2026-05/2_Singapore"

$PY scripts/od/audit_corridor_scale_7_9ia.py      # 20/20
$PY scripts/od/audit_m1_accessibility_7_9ib.py    # 12/12
$PY scripts/od/audit_kpe_ecp_object_7_9ia2.py     # 18/18
$PY scripts/od/audit_chain_reaggregation_7_9ia1.py # 8/8
$PY scripts/od/audit_zero_flow_ledger_7_9ibb.py   # 6/6
$PY scripts/od/audit_bb_direction_probe_7_9ibbp.py # 6/6
$PY scripts/od/build_figs_7_9i.py
```

**复现性已验（2026-09-29 收口时）**：`audit_bb_direction_probe_7_9ibbp.py` 重跑一次，
`bbp_direction_probe_summary_7_9ibbp.json` 除 `elapsed_s` 外**逐位相同（True）**、
`bbp_direction_probe_7_9ibbp.csv` **逐位相同**。

---

## 6. 恢复入口（下次从哪续）

> **★底线（用户明示，跨阶段生效）**：
> **在 7.9I-A1/A2/B 没有把观测对象与 MATSim 对象的尺度关系理清之前，不再调整 v1.0 的交通动力学参数。**

尺度关系**已理清**（C1–C9）。恢复时的**唯一合法入口**是 `OPEN` 表中的 O1–O5，**优先序建议**：

1. **O1**（`B2` 车行道对层）—— 仍属零仿真域，直接承接本轮主结论，是**唯一不需要突破底线**的续接点；
2. O3（LTA 分车型 / HTS 口径）—— 数据侧，同为**零仿真**；
3. O2 / 动力学参数 —— **必须由用户显式裁定解除底线**后方可进入。

⛔ 恢复时**不得**：改 7.1 / 7.3.6A / OD / network / capacity / prereg / 阈值；不得按 `ΣEF/N_sim` 重算 `SCALE`；
不得用 `demand↑` 造堵、不砍容量造红；不得把 expanded residual 回写 target；不得用 `Sim/Obs` 外推为「全网只有观测的 X%」。

---

## 7. ★后续必须遵守的锚点（用户 2026-09-30 裁定，逐条照录）

> 以下 7 条为**跨阶段生效**的锚点，任何后续步骤的判读与 DOC 均**不得**与之冲突。

| # | 锚点 | 落点 |
|---|---|---|
| **A1** | **采样容量折减已排除为主因**：`0.434977` **不进入 v1.1** | `§2-C1` / `7.9A-1` |
| **A2** | **`Sim/Obs ≈ 0.766` 不再解释为全网需求不足**，只能放在**靶场观测域内**解释 | `§2-C2`（覆盖率 6.64% / 严格 1:1 10.42%） |
| **A3** | **1:K 映射尺度错配已被实证确认**，不能再用简单 `sum / median / K` 偷换物理测量单元 | `§3-R1`（⇒ `r_mixed`） |
| **A4** | **真正剩余的低载问题已收敛**：主要是**映射链、对象定义、平行/对层结构**，而不是单纯「没车」 | `§2-C6/C7/C8` |
| **A5** | **KPE/ECP 的极端缺载数字已大幅回收**，`r_mixed` 才是当前更合理的**设施对象比较依据** | `§2-C4`（`r_mixed` 0.385/0.388/0.465） |
| **A6** | **38 个零流量断面中，方向映射错误已被 152/152 同向证据排除**；`B2` 更值得从「**对层建模**」继续查 | `§2-C9` + `STEP7_9I_O1_REPORT.md` |
| **A7** | **v1.0 全程保持冻结**，截至 7.9I **没有产生 v1.1** | `changed = 0` |

---

## 8. 收口后状态（2026-09-30）

**`7.9I_FROZEN_CLOSED → READY(O1) → O1 ✓`**

| 项 | 结果 |
|---|---|
| O1 主引擎 | `CARRIAGEWAY_PAIR_AUDIT_READY`（**9/9**；负例 4/4；20.7 s） |
| 后验 ①「候选对象选取」 | `PAIR_CANDIDATE_PROBE_READY`（**5/5**；14.1 s） |
| 后验 ②「对向标签对照」 | `OPPOSITE_LABEL_CONTROL_READY`（**8/8**；13.2 s） |
| 合计 | **22 项门 / `n_fail = 0`**；`changed = 0` |
| **★`B2` 归因** | **对象层面 15 节 / 75.51% Σobs**（对向断面 canonical 正常、本侧全零）；**需求/路径 6 节 / 24.27%**；LTA 覆盖 1 节 / 0.22% |
| **★对层口径** | `r_pair` 中位：R-sum 2.1512 / **R-max **1.8677**（带内 [0.5,2]）** / R-med 1.2183 |
| 暴露面 | `L1` 的 51.86% 依赖 **300 m** 搜索半径；**保守读法 30.77%**（`R ≤ 100 m`） |

**下一步（建议，待裁定）**：**`O1-续`** —— 对 `L1` 的 15 节做「车行道对账卡」（单侧 way 数量与标签 / OSM `oneway` / 与 `U_UNIT_MISMATCH` 求交），**仍零仿真**。
O2 / 动力学参数**须用户显式裁定解除底线**。
