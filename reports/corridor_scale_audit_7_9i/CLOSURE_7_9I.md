# Step 7.9I · 阶段冻结收口档案（CLOSURE）

- **阶段**：7.9I —— 观测域尺度审计 + M1 可达性审计 + 「观测对象 ↔ MATSim 对象」三刀闭环
- **判决**：**`7.9I_FROZEN_CLOSED` → `READY(O1)` → `O1 ✓` → `O1-续 ✓` → `O1-续② ✓` → `D-path ✓` → `D2-review ✓` → `O3 ✓` → `O3-METADATA ✓`**（2026-10-01 更新；报告见 `STEP7_9I_O1_REPORT.md` / `STEP7_9I_O1CONT_REPORT.md` / `STEP7_9I_O1CONT2_REPORT.md` / `STEP7_9I_DPATH_REPORT.md` / `STEP7_9I_D2REVIEW_REPORT.md` / `STEP7_9I_O3_REPORT.md` / `STEP7_9I_O3METADATA_REPORT.md`）
- **冻结日期**：2026-09-29
- **冻结依据**：用户裁定「**暂停推进，先冻结收口**」（承接上一轮正式裁定）
- **性质**：全链 **零仿真 / 只读**；**未触碰** v1.0 任何交通动力学参数、靶场、交叉表、OD、network、capacity、prereg、阈值
- **总门数**：**110/110**（10 个引擎，`n_fail=0`）；负例 **4/4 fired × 4 个正式引擎 ＋ 5/5（O1-续②）＋ 6/6（D-path，附 1 项空扰动披露）＋ 6/6（D2-review）＋ 6/6（O3）＋ 5/5（O3-METADATA，附 1 项仪器缺陷披露）**
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

### 8.1 ★O1 正式裁定（用户 2026-09-30 给定，逐字照录）

> **B2 中 75.51%（按 Σobs 加权）的零流量异常具有对象层面证据：在本侧匹配边方向全部一致的前提下，
> 其对应物理段的对向 LTA 断面仍表现为正常仿真承载，说明异常主要涉及双向车行道对象的建模、
> 映射或对应关系，而非单纯交通需求不足。**

**因果链（冻结，不得拆散引用）**：

```text
B2 零流量 → 152/152 匹配边方向一致 → 19/22 为独立车行道节点串
→ 对向 LTA 断面同一物理段可找到正常承载对象
→ 75.51% Σobs 的本侧为 0、对向 ratio_median 落入 [0.5,2]
→ 不能解释为“这一段没有需求”
→ 应优先解释为 MATSim 车行道对象建模/映射问题
```

**★两个限制（与裁定同等效力，不得省略）**：

1. **75.51% 是「当前几何控制下的对象层支持比例」，不是最终真值归因比例** —— 其关键子类 `L1` 依赖 **300 m** 对向断面搜索半径；`R ≤ 100 m` 时仅 **30.77%**。⛔ 不得写成无条件「最终机制比例」。
2. **剩余 24.27% 不得称为「需求不足」** —— 其唯一合法名称是
   **`L2_OPP_ALSO_LOW`：对向断面同样低载，因而对象层证据不足，需要回到需求 / 路径层解释。**
   ⛔ 归因方向（需求 / 路径 / 其它）本步**未定**。

> 两句限制同时保留，O1 的证据强度反而更高 —— **没有把探索性空间对应关系包装成确定事实**。


---

## 9. O1-续 执行结果（2026-09-30，`O1 ✓ → O1-续 ✓`）

**状态**：**`7.9I_FROZEN_CLOSED → O1 ✓ → O1-续 ✓`** ｜ 全链 **零仿真 / 只读** ｜ `changed = 0`

| 项 | 结果 |
|---|---|
| 引擎 ①② | `audit_carriageway_build_7_9io1c.py` → **`CARRIAGEWAY_BUILD_AUDIT_READY`**（**12/12**；负例 4/4；23.2 s） |
| 引擎 ③ | `audit_uint_mismatch_intersect_7_9io1i.py` → **`UINT_MISMATCH_INTERSECT_READY`**（**7/7**；负例 3/3；26.3 s） |
| 合计 | **19 项门 / `n_fail = 0`**；两卡片重跑**逐位相同** |
| 报告 | `STEP7_9I_O1CONT_REPORT.md` |

### 9.1 冻结结论（D1–D6，接续 C1–C9）

| # | 一句话 | 关键数 |
|---|---|---|
| **D1** | **本侧车行道都已建**（无「少建本侧」） | matched 对象缺失 **0/38**；`build_class = S2_MS_SELF_BUILT_UNLOADED` **38/38** |
| **D2** | **对向也已建 36/38**，缺失 **2 节 ⇔ OSM `O_SELF_ONLY`**（集合恒等，对称差 ∅） | `{172382, 45187}`；均 `EAST COAST PARK SERVICE ROAD` |
| **D3** | **OSM 源头 = 每方向一条独立 `oneway=yes` way**（⛔ 非转换伪影） | MAJOR way **6,694**；`oneway=yes` **92.83%**；L1 同向 way 48 / 对向 way 40 |
| **D4** | **零流的两种形式**：死管（主导）vs 被平行对象替代 | `ISO_DEAD_TUBE` **18 节 / 58.26% Σobs**；`ISO_TWIN_EXISTS` **18 / 41.15%**（中位 **35.54 m**）；`ISO_BYPASS_NO_TWIN` 2 / 0.59% |
| **D5** | **与 `U_UNIT_MISMATCH` 完全不相交** | 38 节 `vc_max` p50 **0.339** / max **0.597** ⇒ **0/38 U**；对照 A2 范围 U = **17/69**（KPE 隧道 16/19，最高 `3.569×`） |
| **D6** | **★「少建一条车行道」在本数据集上不成立** | 唯一成立的分类 = **「两条都建了，本侧没有被路由使用」（38/38）** |

### 9.2 ★机制细化（对用户正式裁定的细化，非否证）

用户裁定「应优先解释为 MATSim 车行道对象建模/映射问题」⇒ 本步把「建模/映射/对应关系」收敛为：

> **不是「少建」，也不是「容量/单元错配」，而是「已建成的本侧车行道在拓扑上没有被接入
> （`ISO_DEAD_TUBE`，58.26% Σobs），或被更近的平行同向对象替代（`ISO_TWIN_EXISTS`，41.15% Σobs，中位 35.5 m）」。**

**零流链长**：p50 **6.5** / p90 **15.8** / **max 36 边**（沿 `入度=1` 上溯 36 步仍 Σflow = 0）。

### 9.3 缺陷登记（详见报告 §8）

| 编号 | 项 | 内容 |
|---|---|---|
| **D-1 / D-2** | 判据设计缺陷 ×2（同根因） | 用「几何同向池」代理「本侧对象」⇒ 纳入邻近其它道路同向有流边 ⇒ 首跑 FAIL 3 + v2 残留 FAIL 1。已改 **matched 边** 口径；阈值**未改** |
| **D-3** | 判据退化 | `G-O1I-3` 首版「U 与非 U 均出现」，实测 `U = 0/38` ⇒ 恒不可满足。已拆为「**交集 = ∅**」+「`vc_max` 非退化（`p90/p10 = 7.94`）」 |
| **D-4** | 口径暴露面 | `R_OSM/R_MS/R_TWIN/DIR_OK` 为预注册常量，**未做敏感性扫描**；⛔ 不得当绝对计数 |
| **D-5 / D-6** | 样本与推断边界 | 2 节来自**服务道**（不得与主线混算）；「双胞胎」⛔ **不等于**「同一物理车行道」 |

### 9.4 下一步（建议，待裁定）

**`O1-续②`：接入（access）审计** —— 对 `ISO_DEAD_TUBE` 的 18 节（58.26% Σobs）沿零流链找「本应有接入、实际没有」的节点，
比对 OSM 是否有连接 way ⇒ 区分 **转换丢边** vs **源头无接入**；对 `ISO_TWIN_EXISTS` 的 18 节（41.15%）核验「替代对象」是否同一物理车行道。**仍零仿真**。

⛔ `signals` / `trafficDynamics` / `speedFactor` **须用户显式裁定解除底线**后方可进入；**不产生 v1.1**。

**⇒ 已于同日执行完毕（用户裁定收紧口径后），见 §10。**

---

## 10. O1-续② 执行结果（2026-09-30，`O1-续 ✓ → O1-续② ✓`）

**状态**：**`… → O1 ✓ → O1-续 ✓ → O1-续② ✓`** ｜ 全链 **零仿真 / 只读** ｜ `changed = 0` ｜ 判决 **`DEAD_TUBE_ACCESS_AUDIT_READY`**（硬门 **10/10**、负例 **5/5**、`n_fail=0`；卡片重跑**逐位一致**）
**范围（用户收紧口径）**：**只正式推进 `ISO_DEAD_TUBE` 18 节（Σobs = 36,150.5）**；`ISO_TWIN_EXISTS` 18 节**仅证据整理**，标签 **`TWIN_GEOMETRIC_SUBSTITUTE`**，⛔ 不做「同一物理车行道」裁定。
**报告**：`STEP7_9I_O1CONT2_REPORT.md` ｜ **预注册**：`PREREG_7_9I_O1CONT2.md` ｜ **引擎**：`audit_access_dead_tube_7_9io1c2.py`

### 10.1 ★三支裁定（逐字结论）

| 支 | 判据 | 实测 | 裁定 |
|---|---|---|---|
| **A** 源头无接入 | `OSM_access_n == 0` | **0/18**（min 1 / max 10） | ⛔ 不成立 |
| **B** 转换丢失 | `OSM_link_n>0 ∧ 已转换==0` | **0/18**（**24/24 link way 全转换**；`cov_frac` min **0.654** / p50 **1.000**） | ⛔ **不成立** |
| **C** MATSim 无入口边 | `MATSim_access_n == 0` | **0/18**（1 条 13 节 / 2 条 5 节；5 节入边即 link 类） | ⛔ 不成立 |

> **★核心**：**「OSM 有入口 → MATSim 接入丢失」在本批不成立** ⇒ **问题不在路网构建链**，⛔ 不应据此改 `build_impedance.py` 的转换逻辑。

### 10.2 ★细化 D / E（A/B/C 全空后的可证伪细分，预注册并列）

| 类 | 规则 | 节数 | Σobs | 占比 |
|---|---|---|---|---|
| **D** `D_NO_LOCAL_LIVE_SAME_DIR` | `ms_same_live == 0` | **14** | **28,361.0** | **78.45%** |
| **E** `E_LOCAL_LIVE_SAME_DIR_EXISTS` | `ms_same_live > 0`（1 / 4 / 2 / 6） | **4** | **7,789.5** | **21.55%** |

`first_nonzero_dist`（链头 → 最近活流节点）p10 **17.4** / p50 **37.5** / p90 **61.3** / max **100.2 m**；`dead_chain_len` p50 **13** / max **36**；`route_accessible` **18/18 = True**（预注册即披露为**不区分量**）。

### 10.3 缺陷登记

| 编号 | 项 | 内容 |
|---|---|---|
| **R1** | B 判据「单点」→「覆盖率」 | 单点口径把**端点落在路口空档**的 way 误判为未转换（49054 `479127292` 覆盖率 **0.893**）⇒ 判据设计缺陷；`COV_MIN=0.5` 冻结 |
| **R2** | 负例 `N3` 原为**空扰动** | 原设计 `mx/my` 从未被使用 ⇒ 空操作 ⇒ `fired=False`（**仪器缺陷**）；已改「OSM 不投影」，**主路径判据未改** |
| **D1** | A/B/C 全空 = 判据退化 | 已在**预注册阶段**并列 D/E 细化轴（非后验补丁） |
| **D2** | `route_accessible` 不区分 | 18/18 True ⇒ 仅作契约/反例量 |
| **D3** | 口径暴露面 | `R_ACC/R_MS2/DIR_OK/COV_MIN/SAMPLE_M` 未做敏感性扫描；`ms_same_live` 依赖 `R_MS2` |
| **D4** | `ACCESS_TYPES` 是判定的一部分 | 已排除 footway/cycleway/service/residential 等 |
| **D5** | `ms_same_live` **含非 MAJOR** 边 | 与 O1-续 `ISO_TWIN_EXISTS` 的 **MAJOR** 口径**不同**；⛔ 两口径不得混用 |
| **D6** | 近旁活流 ≠ 同一车行道 | `first_nonzero_dist` 仅说明活流近旁；需 detector 元数据方可断言 |

### 10.4 下一步（建议，待裁定）

- **D（78.45% Σobs）**指向**方向/走廊层的路由行为** —— 本方向活流究竟走在何处（对向？更远平行走廊？）⇒ 需**有向路径级**追踪（仍零仿真）。
- **E（21.55% Σobs）**指向**对象对应关系**（4 节 50 m 内有同向活流边） —— ⛔ 与 `ISO_TWIN_EXISTS` 同样**缺 detector 元数据**，须谨慎。
- ⛔ `signals` / `trafficDynamics` / `speedFactor` **须用户显式裁定解除底线**；**不产生 v1.1**。

**⇒ 已于同日执行完毕（用户裁定推进 D-path 后），见 §11。**

---

## 11. D-path 执行结果（2026-09-30，`O1-续② ✓ → D-path ✓`）

**状态**：**`7.9I_FROZEN_CLOSED → O1 ✓ → O1-续 ✓ → O1-续② ✓ → D-path ✓`** ｜ 全链 **零仿真 / 只读** ｜ `changed = 0` ｜ 判决 **`DPATH_TRACE_READY`**（硬门 **10/10**、负例 **6/6**＋1 项空扰动披露、`n_fail = 0`；Card 重跑 **SHA256 逐位一致 `866023f85b504655`**，1.9 s）
**范围**：**只追 D 类 14 节**（`D_NO_LOCAL_LIVE_SAME_DIR`，Σobs = **28,361.0**）
**报告**：`STEP7_9I_DPATH_REPORT.md` ｜ **预注册**：`PREREG_7_9I_DPATH.md` ｜ **引擎**：`audit_dpath_7_9id1.py`

### 11.1 ★D1–D5 裁定

| 类 | 判据 | 节数 | Σobs | 占比 |
|---|---|---|---|---|
| **D1** 同向平行链 | `dbear ≤ 30° ∧ d_own ≤ 60 m` | **0** | 0.0 | 0.00%（**结构性退化**） |
| **D2** 对向/对层 | `dbear ≥ 150°` | **6** | 16,075.0 | **56.68%** |
| **D3** 同走廊更远处汇入 | `dn_live > 0`（本链下游同对象有活流） | **5** | 6,535.0 | **23.04%** |
| **D4** 拓扑替代 | 同向远 408 m / 斜交 114–137° | **3** | 5,751.0 | **20.28%** |
| **D5** 深度内无承载对象 | `C_in = ∅` | **0** | 0.0 | 0.00% |

### 11.2 ★第二轴：承载充分性（`carry_scaled = flA_in × SCALE / obs`）

| 轴 2 | 节数 | Σobs | 占比 | 范围 |
|---|---|---|---|---|
| `F_ADQ`（≥0.50） | **5** | 8,220.0 | **28.98%** | 1.246 – 11.894 |
| `F_LOW`（<0.50） | **9** | 20,141.0 | **71.02%** | **0.043 – 0.407** |

**★流量守恒**：`R_cons` **0.041 / p50 0.4375 / 13.364**（6 取值，14/14 可检验）；`Rn` 13/14 ≈ **1.000**、172382 = 0.524；**`Rd = 0` 3 节**（48586 / 48337 / 48983）⇒ 承载链流量在链头**全部终止**。
**★共享结构**：14 节只对应 **6 条**上游承载链（20–129 边，1.18–3.67 km）⇒ 残块在上游对象层面**高度集中**。
**★独立诊断**：欧氏最近活边 **13/14 节为对向**（0.929）；拓扑最近与欧氏最近**仅 2/14 一致**（必须同报）。

### 11.3 判读（严格执行用户纪律）

- ⛔ **D1–D4 一律表述为「承载对象替代 / 路径重分配」，不得写作「映射错误」**（未与 OSM way / LTA detector / 设施对象建立对应）。
- ⛔ **D1 = 0 只能读作「本层判据下不可检出」**（D 类定义即排除「链头 50 m 内同向活流」；实测 12/14 节近旁**有**同向对象但**全部零流**）。
- ⛔ **D2 不得读作「对向车行道在承载」**（对向对象流向相反，不可供流）⇒ 只能读作「**本方向未检出同向供流对象**」。
- ✅ 本刀证据**偏向**「**车没有进入这条路（本方向）**」，而**不是**「进入了走廊但被平行有向链承载」（后者仅弱支持，且限于 408–568 m 同向/斜交对象）。

### 11.4 缺陷登记

| 编号 | 项 | 内容 |
|---|---|---|
| **R1** | 负例 `N5` 原为**空扰动** | 「上游域放宽为全边」实测与基准**完全相同** ⇒ 负例设计缺陷；已改 `max_steps=1` + 新增 `N6`（`D3` 关闭），原扰动降级为**披露项**（**「零流-only」不是本刀选择杠杆**）；**主路径判据/阈值未改** |
| **R2** | 汇总层**顺序缺陷** | `cards_sha256_16` 原在 JSON 写盘后才赋值 ⇒ JSON 缺卡片哈希；改为 **先写 CSV → 算 SHA → 再写 JSON**；**CSV/判据未改**（`866023f85b504655`） |
| **D1** | `D1 = 0` 结构性退化 | 三处强制披露（`G-DP-8` / 报告 §5.2-① / `summary`） |
| **D2** | 拓扑最近 ≠ 欧氏最近（12/14） | 已在 §4.5 **同报两口径** |
| **D3** | 基数不可比 | `carry_*` vs `obs` 的 `K_pooled = 5.5434` ⇒ 仅量级参照 |
| **D5** | `hr_hop_max = 120` 饱和（13/14） | 不影响 `e_near`（BFS 逐层，`hop ≤ 26` 层完整，`G-DP-6` 门禁） |
| **D6** | ★单位口径更正 | `LENGTH` 实测为 **m**（比值 p50 = 1.0000；全网 **15,126.5 km**） |

### 11.5 下一步（建议，待裁定）

1. **D2（56.68% Σobs）对象级核验**：把 `C_in` 的方向性条件放松为「同向」并允许**跨 1 条活边**的上游扩展，检验是否只是被「零流-only + 1 跳」的域口径挡住（仍零仿真）。
2. **`F_LOW` 9 节（71.02% Σobs）量级缺口核验**：这些断面的 `obs` 是否**本就不应由本方向承接** ⇒ 属**观测域**问题，须先补 LTA detector / 设施元数据。
3. ⛔ `signals` / `trafficDynamics` / `speedFactor` **须用户显式裁定解除底线**；**不产生 v1.1**。

**⇒ 第 1 项已于同日执行完毕（用户裁定推进 D2-review），见 §12。**

---

## 12. D2-review 执行结果（2026-09-30，`D-path ✓ → D2-review ✓`）

**状态**：**`7.9I_FROZEN_CLOSED → O1 ✓ → O1-续 ✓ → O1-续② ✓ → D-path ✓ → D2-review ✓`** ｜ 全链 **零仿真 / 只读** ｜ `changed = 0` ｜ 判决 **`D2REVIEW_READY`**（硬门 **11/11**、负例 **6/6**、`n_fail = 0`；Card 重跑 **SHA256 逐位一致 `bc323212de2f4d5a`**，1.8 s）
**正式问题**：**是否因为当前候选域过窄，把「同向供流对象」人为排除掉了？**
**范围**：D 类 14 节；**重点裁定原 D2 六节**（Σobs **16,075.0 / 56.68%**）
**设计**：**R0**（冻结域，`MAX_ACTIVE=0`）与 **R1**（仅放宽候选域为「跨 ≤1 条活边」，`MAX_ACTIVE=1`）**并列**；⛔ `obs`/`SCALE`/`capacity`/链定义/`D1/D3/D4` 判据**全部不动** ⇒ R1 **不改变任何 `final_class`**
**报告**：`STEP7_9I_D2REVIEW_REPORT.md` ｜ **预注册**：`PREREG_7_9I_D2REVIEW.md` ｜ **引擎**：`audit_d2review_7_9id2.py`

### 12.1 ★原 D2 六节裁定（核心）

| `section_id` | `obs_8_9` | R0 `dbear` | R0 `carry` | R1 `same_dir_n` | R1 同向 `fl_max` | **`carry_scaled`（域上界）** | 裁定 |
|---|---|---|---|---|---|---|---|
| 48461 | 4,118.0 | 178.6° | 0.122 | 55 | 103 | **0.058** | `F_LOW` |
| 49054 | 3,481.5 | 179.3° | 0.234 | 31 | 103 | **0.068** | `F_LOW` |
| 48708 | 2,393.5 | 179.9° | 0.209 | 53 | 103 | **0.099** | `F_LOW` |
| 47189 | 2,334.5 | 163.4° | 2.071 | 43 | 109 | **0.107** | `F_LOW` |
| 47163 | 1,967.0 | 179.0° | 0.255 | 53 | 103 | **0.120** | `F_LOW` |
| 45927 | 1,780.5 | 166.6° | 2.715 | 39 | 109 | **0.141** | `F_LOW` |
| — | **Σ 16,075.0（56.68%）** | — | — | — | — | **`F_ADQ = 0/6`** | — |

⇒ **原 D2 六节中，放宽候选域后能找到「同向、量级合理」（`carry_scaled ≥ 0.50`）供流对象的节数 = `0 / 6`。**

### 12.2 ★三条防退化轴（因预期结果 = 判据命中 100%）

| 轴 | 实测 | 说明 |
|---|---|---|
| **A1 下界轴** | `same_dir_carry_max ∈ [0.058, **0.452**]`，**14/14 < 0.50** | 0/14 是**连续上界**结论，非二值退化 |
| **A2 对照轴** | R0 选中对象 `r0_carry_scaled` 最高 **11.894**，**5/14 节 ≥0.50** | 域内**确有**高承载对象，只是**方向不对** ⇒ 检索器正常 |
| **A3 反证轴** | 负例 `NF1`（方位 +180°）⇒ **`F_ADQ = 11/14`** | 判据**能**产出 `F_ADQ` ⇒ 主路径 0/14 是**真实空缺** |

### 12.3 ★R1 杠杆生效 + 「域过窄」被双重排除

| 口径 | 同向候选节数 | `carry_max` 范围 | `≥0.50` 节数 |
|---|---|---|---|
| **R0 冻结域**（零流-only） | **14/14**（每节 2–37 个） | [0.028, 0.407] | **0** |
| **R1 扩展域**（≤1 条活边） | **14/14** | [0.058, 0.452] | **0** |

域 **64,888 → 67,606** 节点（+2,718）；候选 **4,105 → 5,081**（+976）；**14/14 节**均新增（`G-D2R-5`）。
**★同向活跃对象在几何上亦够不着**：同向候选到本链最小距离**下界 407.9 m**（`same_dir_within_60m_of_chain = 0`）；`same_dir_fl_max ≤ 109 veh/h`。

### 12.4 判读（严格）

- ✅ **答**：**不是候选域过窄**。三条独立口径（对象存在性 / 量级合理性 / 几何距离）一致 ⇒ 偏向
  **「本方向交通没有沿该 MATSim 车行道进入，而是在更上游发生路径分配差异」**；
  ⛔ **不是**「零流链内部存在路径/连接断点」（该支要求同向合理供流对象**大量存在**，实测 `0/14`）。
- ⛔ `D1 = 0` **未重解释**；⛔ 全程只称「**承载对象替代 / 路径重分配**」，未升级为「映射错误」。
- ⛔ 不得把 `carry_*` 与 `obs` 之差读作 demand scale 证据（`K_pooled = 5.5434`）。
- ⛔ `F_LOW`（71.02% Σobs）**未与 D2 混解**（用户指定），仍独立待裁。

### 12.5 缺陷登记

| 编号 | 项 | 内容 |
|---|---|---|
| **R1** | **实现缺陷 + 门禁缺口** | `same_dir_euc_dist` 误把**候选数组序号**当**全局边索引**（`G.ex[i_e]`），首跑出现 1.5e4–2.4e4 m 的物理不可能值（新加坡南北向 < 25 km）⇒ 改为 `dd_sd.min()`；**并新增硬门 `G-D2R-10`**（由 card 内边 id 反算距离，`\|Δ\|<0.06 m` ∧ ≤ 全网坐标跨度 55,773 m），该门在缺陷版下必 FAIL，用于堵住「无门可拦」缺口。**主判据/阈值/`same_dir_first_*`/`carry_max`/`class` 全部未变** |
| **D1** | `D1 = 0` 结构性退化 | 三处强制披露（预注册 §2.5 / Card / 报告 §8） |
| **D2** | 拓扑最近 ≠ 欧氏最近（**9/14 一致，5 节不一致**） | 已在报告 §4.5 **同报两口径** |
| **D3** | 基数不可比 | `carry_*` vs `obs` 的 `K_pooled = 5.5434` ⇒ 仅量级参照 |
| **D4** | `same_dir_class` 单一取值（全 `F_LOW`） | 依纪律由 **A1 连续轴 + A3 反证门**承担「防 100% 判据缺陷」；`G-D2R-6` **不要求** class 多取值 |

### 12.6 下一步（建议，待裁定）

1. **D2 裁决已收敛**（不是检索域问题）⇒ 若继续，**只剩两条须先补外部语义的路线**：① LTA detector / 设施级元数据；② 观测域归属核验（`obs` 是否本就不应由本方向承接）。⛔ 缺元数据时**不得**以几何邻近替代。
2. **`F_LOW`（71.02% Σobs）** 仍独立待裁。
3. ⛔ `signals` / `trafficDynamics` / `speedFactor` **须用户显式裁定解除底线**；**不产生 v1.1**。

---

## 13. O3 执行结果（2026-09-30，`D2-review ✓ → O3 ✓`）

**状态**：**`7.9I_FROZEN_CLOSED → O1 ✓ → O1-续 ✓ → O1-续② ✓ → D-path ✓ → D2-review ✓ → O3 ✓`** ｜ 全链 **零仿真 / 只读** ｜ `changed = 0` ｜ 判决 **`OBS_DOMAIN_AUDIT_READY`**（硬门 **10/10**、负例 **6/6**、`n_fail = 0`；Card 重跑 **SHA256 逐位一致 `32daf852192a0c1d`**，35.0 s）
**正式问题（用户裁定，**换问题**）**：⛔ 不再问「哪条 MATSim edge 应该承接这些车」；✅ 改问 **「LTA 的这个数，到底在现实世界中测量了什么？」**
**范围**：主集 = **`F_LOW` 9 节**（Σobs **20,141.0**）；参照 = `F_ADQ` 5 节；基线 = 全域 **1,311 obs LinkID / 1,278 有几何**
**报告**：`STEP7_9I_O3_REPORT.md` ｜ **预注册**：`PREREG_7_9I_O3.md` ｜ **引擎**：`audit_obs_domain_7_9io3.py`

### 13.1 四事实逐项回答（核心）

| # | 问题 | 实测回答 |
|---|---|---|
| **①** | 观测对象是「单车行道」还是「道路断面/设施」 | **结构层 = 有向路段**（**1,278/1,278 全 2 顶点**、长度 p50 **128 m**、同路名 `obs` 唯一率 p50 **1.0000**）；**设施归属层 ⛔ `OBS_OBJECT_UNRESOLVED`** |
| **②** | 一观测对象覆盖多个承载对象？ | **LTA 侧：否**（`sib_uniq_frac` **0.9706–1.0000**）；**跨层：是**（`1 LTA LinkID ↔ K` MATSim 边，`K` **1–14**，`K_pooled 5.5434`） |
| **③** | `Volume` 语义 | **通过该有向路段的工作日 08 时中位机动车流量**（`vol_int_frac = 1.0` 整数计数；日间 CV p50 0.075；`obs_h7/obs_h8` p50 0.988；`n_h8_wd = 20`） |
| **④** | 回到 MATSim | **本刀不做**（用户明确「最后才回到 MATSim」） |

### 13.2 ★A–E 分类（用户指定五类）

| 类 | 全 14 节 | 主集 `F_LOW`(9) | 参照 `F_ADQ`(5) |
|---|---|---|---|
| **A** `A_OBS_NOT_SINGLE_SEGMENT` | **0** | 0 | 0 |
| **C** `C_OBS_AGGREGATE_FACILITY` | **0** | 0 | 0 |
| **D** `D_LEVEL_CARDINALITY_MISMATCH` | **11** | **7** | 4 |
| **B** `B_BINDING_UNDECIDABLE` | **3** | **2** | 1 |
| **E** `E_UNEXPLAINED` | **0**（结构性不可达） | 0 | 0 |

### 13.3 ★最关键可操作发现：`DATA_ACQUISITION_GAP`（本地文档 ≠ 实际数据）

| 表 | 实际字段 | 本地文档声称 | 差异 |
|---|---|---|---|
| `TrafficFlow_Data.json` | `LinkID,Date,HourOfDate,Volume,StartLon,StartLat,EndLon,EndLat,RoadName,RoadCat` | `LinkID, **VehicleType**, Volume, **Timestamp**` | ⚠ **`VehicleType`/`Timestamp` 不存在** |
| `DetectorLoop.dbf` | **`OBJECTID`（1）** | `…,RD_CD, **LANE_NUM**, **DETECTOR_ID**, REMARKS` | ⚠ **标识字段全部缺失**；★`REMARKS` 归类已更正，见 §14.7 |
| `RoadSectionLine.dbf` | `RD_CD,RD_CATG_NA,RD_CATG__1,RD_CD_DESC`（4） | `…, RD_CD, RD_CATG_NAM, …` | ⚠ **无 `LinkID`**；`RD_CD`/`RD_CATG_NA` **100% 空** |

⇒ **观测对象语义无法闭合，不是「LTA 没有元数据」，而是「本批未取得」**：
**① `DetectorLoop` 属性字段在下载时被剥离；② `RoadSectionLine` 本地版无 `LinkID`；③ 本地无 Junction/Turning-Count 数据集。**
`DetectorLoop` 与断面**亦不共址**（共址率 **25 m 3.5% / 100 m 19.9%**；`det_min` p50 **222 m**；本批 14 节 **113.6–673.8 m**）。

### 13.4 全域基线（1,278 LinkID）

`{2 顶点: 1278}` · 长度 p10 53 / **p50 128** / max 201 m · 同路名 `obs` 唯一率 p10 0.99 / **p50 1.0000** ·
到最近**对向**观测对象垂距 p10 15 / **p50 40** / p90 669 m（**≤60 m 占比 0.504**；`PERP_R` 内无对向对象 **249 条**） ·
`RoadCat`：`CATB 634 · CATA 339 · SLIP_ROAD 251 · CATC 46 · CATD 7 · CATE 1`

### 13.5 判读（严格按预注册）

- ⛔ `A = 0` / `C = 0` **只能读作「未检出」**，**不得**读作「因此 = 单车行道」。
- ⛔ `D` 成立**只能**读作「**跨层基数 ≠ 1**」，不得读作「观测对象方向错」。
- ⛔ `B` 命中**只能**读作「**本地不可判定**」，**不得**读作「MATSim 承载错误」。
- ⛔ `det_min_m` 小 ⇒ 只能说「附近有线圈设施」，**不得**说「该观测对象由该线圈测量」（**几何邻近 ≠ 物理对应**）。
- ✅ 与 **O1-续② / D-path / D2-review** 一致：全程未改 D 类判据、未重解释 `D1 = 0`、未把 `F_LOW` 与 ④ 混解。

### 13.6 缺陷登记

| 编号 | 项 | 内容 |
|---|---|---|
| **R1** | **仪器实现缺陷（签名设计）** | 首版 `sig` 含 `Σdet_n_100`（基线**恒 0**，最小 `det_min` 113.6 m > `DET_R` 100 m）且**未含** `Σobs_8_9` ⇒ 负例 `N3`/`N4` **空扰动假阴性**。改为含 `Σobs_8_9` 与 `Σdet_min_m`；**主路径判据/阈值/分类/卡片字段全部未改** |
| **D1** | `facility_binding` 单值退化 | 14/14 = `UNRESOLVED`；由 `N5`（注入伪造 `DETECTOR_ID`）反证其为**数据缺失**而非判据失效 |
| **D2** | `E` 类不可达 | 因 `B` 恒真 ⇒ 结构性为 0，须显式披露（类比 `D1 = 0`） |
| **D3** | `opp_perp_m` 含 `inf` | 全域 249 条、本批 1 条（`172382`）⇒ 已单列计数 |
| **D5** | **文档 ≠ 数据（6 项）** | `VehicleType`/`Timestamp`/`DETECTOR_ID`/`RD_CD`/`LANE_NUM`/`LinkID` ⇒ 已固化为硬门 `G-O3-3` |
| **D6** | `direction_ok_frac = 1.0`（14/14） | 匹配层方向判据在此批**不区分量**，不得据此声称「方向匹配正确」 |

### 13.7 下一步（建议，待裁定）

1. **（本刀直接指向）补齐观测对象语义元数据** —— 重新获取含属性的 DataMall Geospatial `DetectorLoop` + 申请 On-Request **Junction Loop Counts**（`JunctionID`/`DetectorID`/15-min counts）⇒ 方可判 **B**。
2. **事实④（回到 MATSim）** —— 须待 ① 闭合后才能执行。
3. ⛔ `signals` / `trafficDynamics` / `speedFactor` **须用户显式裁定解除底线**；**不产生 v1.1**。

---

## 14. O3-METADATA 执行结果（2026-10-01）

> 用户裁定：**①补齐 LTA 设施级标识字段**；不走②；**不把 TrafficFlow 从硬校准域剔除**。
> 目标：**恢复 `TrafficFlow` → `Detector` / 道路设施 的可连接身份链**（第一步 = 把「缺什么」钉死）。
> 纪律：**零仿真 / 只读**；不改模型、不改评价器、不跑 MATSim；⛔ 缺元数据不得以几何邻近替代。
> 预注册：`PREREG_7_9I_O3METADATA.md`（运行前冻结）· 引擎：`scripts/od/audit_o3_metadata_7_9io3m.py`
> 判决：**`O3_METADATA_AUDIT_CLOSED`（9/9 门 + 负例 5/5）**

### 14.0 ★自查更正（2026-10-01，由 7.9I-O3-DATA-RECOVERY §0 正式更正）

**被更正项**：§14.2 原把 `REMARKS` 列入 `DOC_ONLY`（**「臆造」**）。

**更正依据**：`*.shp.xml` 的**官方 schema 自证源不止一种写法** —— 除 **FGDC 字段映射串**外，还有 **`AddField` 语句**（源库 `GDM@PDN4` / ArcSDE Oracle `gispprod` 的变更日志）。
**权威 schema = FGDC 映射 ∪ `AddField`**；仅用 FGDC 正则会**漏字段**（实测：29 图层中仅 **6** 个含 FGDC 映射串，但 **22** 个含 `AddField`）。

| 图层 | `AddField` 记录 | 更正后判定 |
|---|---|---|
| **`RoadSectionLine`** | ✅ `AddField …\GDM.RoadSectionLine REMARKS TEXT # # 200 Remarks NULLABLE NON_REQUIRED`（**Date=20140801**） | `REMARKS` 是**真实源字段** ⇒ 从臆造清单**移出**，改入 **`SOURCE_ONLY_STRIPPED`**；官方并集 **11 → 12** |
| `DetectorLoop` | ⛔ **无 `AddField` 记录** | 维持「官方 FGDC schema 未声明」，**降级**为 **`UNCONFIRMED_IN_SOURCE`** —— ⛔ **不得再称「臆造」** |

**未受影响**：`DETECTOR_ID` / `LANE_NUM` 的判定**不变**（`DetectorLoop` 官方 = FGDC 12 ∪ `AddField` ∅ = 12，确实**不含**此二者 ⇒ 仍是文档独有）。
**⇒ 下游口径**：本文件 §14.2 表已按更正后口径重列；`readme_technical_v1.md` · `PREREG_7_9I_O3.md` · `PREREG_7_9I_O3METADATA.md` 同步更正。

### 14.1 官方 GDM schema 逐字恢复（★本节点方法学关键）

`*.shp.xml`（FGDC 元数据）中的 `CopyFeatures` / `Append` / `FeatureClassToFeatureClass` **字段映射串**逐字记录了 LTA 源库（`GDM.LTALayers`）schema：

- **`DetectorLoop`（12）**：`JOB_NUM`(Job No,20) · `TYP_CD`(Type of Feature,4) · `LVL_NUM`(Level of Road,2) · `EXCEPTION_IND`(1) · `LAST_UPD_USRID_NUM`(8) · `LAST_UPD_DTTM`(Date) · `CRT_USRID_NUM`(8) · `CRT_DTTM`(Date) · **`RD_CD`(6)** · `PKG_REF`(50) · `SHAPE_Length` · `SHAPE_Area`
  要素定义：*"…electronic loop on the road surface at **signalised junctions**, to detect **traffic movements** for **traffic control** purpose"*
- **`RoadSectionLine`（11）**：`JOB_NUM`(20) · **`RD_CD`(Road Code,6)** · **`RD_NAM`(Road Name,150)** · `RD_CATG_NAM`(20) · `EXCEPTION_IND`(1) · `LAST_UPD_*` · `CRT_*` · `PKG_REF`(50) · `SHAPE_LEN`
  （注：两处映射分别写作 `SHAPE.LEN` / `SHAPE_LEN`，规范化后唯一计数 11）

### 14.2 ★三方对账（官方 / 交付 / 文档）

| 图层 | 官方（FGDC 映射串） | 交付 | 官方 schema 中不存在者 | `OFFICIAL_ONLY` |
|---|---|---|---|---|
| `DetectorLoop`（16,275） | 12 | **`{OBJECTID}`** | **`DETECTOR_ID` · `LANE_NUM`**（2） | **10** |
| `RoadSectionLine`（15,329） | 11（★并集 12，见 §14.7） | `RD_CD`(0%) `RD_CATG_NA`(0%) `RD_CATG__1`(100%) `RD_CD_DESC`(100%) | **∅** | 9（含 `RD_NAM`） |
| `TrafficFlow_Data`（75,899） | — | `LinkID Date HourOfDate Volume StartLon StartLat EndLon EndLat RoadName RoadCat` | `VehicleType` · `Timestamp` | — |

**★精确化 O3 的 `DATA_ACQUISITION_GAP`**：`DETECTOR_ID` / `LANE_NUM` **从来不在 LTA 公开 geospatial schema 里**（本地文档臆造）⇒ 真正被剥掉的是 **10 个非几何字段**。
⚠ **本节含一处已被更正的判定**（原把 `REMARKS` 也列入「臆造」）——见 **§14.7 自查更正**；上表已按更正后口径列出。

### 14.3 连接键可用性

| 键层级 | 双侧可用 | 依据 |
|---|---|---|
| 代码级 `RD_CD`（Road Code） | **False** | `DetectorLoop` 侧字段被删；`RoadSectionLine` 侧填充率 **0.0000 / 15,329** |
| 道路名级 `RD_CD_DESC ↔ RD_NAM` | **True**（结构性） | 文本类字段完整保留 |

**⇒ 即便拿到属性完整版 `DetectorLoop`，本套连接最多到「道路名 / 道路码」级 —— 不是检测器级，更不是链路级。**

**剥空模式**：`RoadSectionLine` **保文本（100%）、清代码（0%）**；`DetectorLoop` **全清（含几何派生量 `SHAPE_Length`/`SHAPE_Area`）** ⇒ **两图层剥离强度不同，非同一规则**（只陈述观测，不推断动机）。

**双路径一致**：`Static` 原件与 `Dynamic` 重下 zip 字段集**全等 = `{OBJECTID}`** ⇒ 缺口**不是单次下载失误**。

### 14.4 On-Request 官方口径（逐字，2026-10-01）

**`Indicative Traffic Counts at Junctions by Loop Detectors`**
> *"…captured by each loop detector installed at **signalised intersections**, **without vehicle classification counts**"*

字段 `Junction ID` · `Detector ID` · `Date and time for each collection period` · `Indicative traffic counts`；频率 **Daily**；格式 `XLS/CSV/TXT`。
**★与 `DetectorLoop` 同要素域** ⇒ 同一套设施的两个视角（几何 vs 计数）。
**⇒ `Detector ID` 的唯一可能来源 = On-Request，不是公开 geospatial 层。**

### 14.5 四门状态（用户裁定的 M1–M4）

`M1a = ABSENT` · `M1b = ABSENT` · `M2 = BLOCKED` · `M3 = BLOCKED` · `M4 = BLOCKED`

- **M1 拆两支**（运行前精化，已冻结）：`M1a` = `RD_CD` 是否恢复（公开 geospatial 可补）；`M1b` = `DETECTOR_ID` 是否可取得（**仅** On-Request 可补）。
- ⛔ **`BLOCKED` 只读「上游依赖未满足」，不得读作「不可连接」**。
- ⛔ `M1b = ABSENT` 只读「本批公开层无此字段」，**不读「LTA 无检测器身份」**。

### 14.6 缺陷登记

| 编号 | 项 | 内容 |
|---|---|---|
| **R1** | **仪器实现缺陷（负例契约可实施性）** | 首跑 `N3 fired=False` / `N2 hit=False`：`N3` 原设计字段 `RD_CATG__1` **在 `DetectorLoop` 侧不存在** ⇒ 空扰动；`N2` 仅单侧注入。改为 **键「层级」切换**（code vs name）+ **双侧注入**。**主路径判据 / 阈值 / M 门定义 / 采集目标 / 门数 / 冻结边界全部未改**。属仪器层缺陷，非科学结论 |
| `N1`–`N5` | 负例 | **5/5** `fired=True` ∧ `hit_designed_observable=True` ⇒ 判定可证伪 |
| 未登记风险 | `TrafficFlow_Links` **无 `*.shp.xml`** | 该图层无官方 schema 自证源（本节点未对其做三方对账） |

### 14.7 下一步（待裁定，本节点不擅自启动）

1. **第一优先**：属性完整版 `DetectorLoop`（公开 geospatial）—— ⛔ **即使成功也不含 `DETECTOR_ID`**，只能到 `RD_CD` 道路码级。
2. **第二优先**：On-Request `Indicative Traffic Counts at Junctions by Loop Detectors` —— **`Detector ID` 的唯一来源**；⛔ **不得先假定能与 `TrafficFlow.LinkID` 一一连接**，可连接性须到手后实测。
3. 数据到手后按 `M1a → M1b → M2（最关键）→ M3 → M4` 重评（仍零仿真）。
4. **边界保持冻结**：`B = BINDING_UNDECIDABLE` **不升级** · `TWIN_GEOMETRIC_SUBSTITUTE` **仅几何** · `F_LOW` **不是"需求不足"** · v1.0 冻结 · `signals`/`trafficDynamics`/`speedFactor` **不碰**。

---

## 15. O3-DATA-RECOVERY 执行结果（2026-10-01）

> 用户裁定：**继续 O3-METADATA，优先走「本地重新获取完整属性数据」路线**，同时申请 On-Request 作为**第二证据层**。
> **⛔ 不要在对话里传 `AccountKey`** —— 用户本地自取，Agent 只等文件。
> 预注册 `PREREG_7_9I_O3RECOVERY.md`（运行前冻结）· 引擎 `scripts/od/audit_o3_recovery_7_9io3r.py` · 自检 `scripts/od/check_o3_recovery_inputs_7_9io3r.py` · 报告 `STEP7_9I_O3RECOVERY_REPORT.md` · 采集清单 `ACQUISITION_MANIFEST_7_9I_O3RECOVERY.md`
> 判决：**`status = BLOCKED` · `verdict = O3_RECOVERY_AWAITING_INPUT`**（硬门 **12/12** · 负例 **6/6** · `EXIT = 0` · ⛔ 不 Traceback）

### 15.1 ★§0 自查更正（`REMARKS`）—— 已同步 §14.0

**权威 schema = FGDC 映射串 ∪ `AddField` 语句**（后者来自源库变更日志；源库 `gdm@pdn4.sde\GDM.LTALayers` / ArcSDE Oracle `gispprod`）。
实测 29 图层：**仅 6 个含 FGDC 映射串、22 个含 `AddField`** ⇒ 仅用 FGDC 正则会**漏字段**。
`RoadSectionLine` 有 `AddField … REMARKS …`（Date=20140801）⇒ **真实源字段**、改入 `SOURCE_ONLY_STRIPPED`、官方并集 **11→12**；
`DetectorLoop` 无 ⇒ 降级 **`UNCONFIRMED_IN_SOURCE`**。**未受影响**：`DETECTOR_ID` / `LANE_NUM` 仍是文档独有。

### 15.2 纠正后的五跳恢复链（逐跳独立判定，不得跳级）

```text
① TrafficFlow LinkID ──(RoadName / RoadCat)──▶ ② RD_CD
                                                  │
                                                  ▼
                                        ③ RoadSectionLine（RD_CD / RD_NAM）
                                                  │
                                                  ▼
                                        ④ DetectorLoop（RD_CD / JOB_NUM / 几何）
                                                  │
                                                  ▼
                                  ⑤ Junction / Detector ID  ← 仅 On-Request 有
```
⛔ 旧链 `DetectorLoop → DETECTOR_ID → TrafficFlow` **已被 O3-METADATA 正式证伪**。

### 15.3 运行前否定性先验

| # | 事实 | 结论 |
|---|---|---|
| **P1** | `RD_CD` 在**三个独立图层**近全空：`RoadSectionLine` **0/15,329** · `CyclingPath` **0/4,830** · `LampPost` **61/126,916 = 0.048%** | 「保文本 / 清代码」跨图层重复 ⇒ 疑**源库未赋值**而非交付剥离 |
| **P2** | `LampPost` 61 条非空 **全部 6 字符**，去重仅 **6 个**（`ZZ190A` 46 / `ZZ202A` 11 / `ZZ161A` 7 / `ZZZ43A` 4 / `ZZ203A` 3 / `PUP06M` 4） | 格式吻合官方 `RD_CD(Road Code,6)`，但形如**内部占位码** |
| **P3** | 29 层全量普查 = **A 14 · B 3 · C 12**（★测量更正：预注册记「7 层」为侦察期部分计数 14+3+7=24≠29） | 存在可获取完整版图层，但**不保证**目标图层 `RD_CD` 有值 |

⇒ **先实测填充率，再谈连接**。

### 15.4 五门 + 逐跳 + `F_LOW` 闭环

| 门 | 实测 | 取值 |
|---|---|---|
| `M1a` | `RoadSectionLine.RD_CD` 字段存在、填充率 **0.0000 / 15,329** | **`ABSENT`** |
| `M1b` | `DetectorLoop.DETECTOR_ID` **不存在**、On-Request 未到手 | **`ABSENT`** |
| **`M2`** | 交付 `DetectorLoop` 仅 `{OBJECTID}` | **`BLOCKED`** |
| `M3` | `LANE_NUM`（官方本无）缺失、检测器侧无方向字段 | **`ABSENT`** |
| `M4` | `m4_closed = 0/9`（`m4_ratio = 0.0`） | **`BLOCKED`**（受 `M2` 阻塞） |

**逐跳统计**（`o3r_recovery_layers.csv`，用户点名 1:1/1:N/N:1/N:M + 覆盖率 + `K_pooled`）：
`①→②` `n_left = 1,278 / n_right = 0` · `②→③` 与 `④→⑤` **两侧皆空** ⇒ 三跳全部 **`BLOCKED_EMPTY_SIDE`**，`c_1_1 = c_1_N = c_N_1 = c_N_M = 0`，`K_pooled` **不可计算**（⛔ 不报比值）。
`lane_recoverable = False` · `direction_recoverable = False`（几何文件存在**仅作支撑证据**，⛔ 不单独构成 `M3`）。

**`F_LOW 9` 节闭环**（`o3r_floow_closure.csv`）：**9/9 四条件全 ✗** ⇒ `closed = 0/9`，`Σobs = 20,141.0 veh/h`。
**`B_SET = [48461, 49054, 47189]`**：`M1a/M1b = ABSENT`、`M2 = BLOCKED` ⇒ **`B` 保持 `UNRESOLVED`，不升级**。

### 15.5 硬门与负例

**`G-O3R-1`–`G-O3R-12` 全部 PASS**（含：官方 schema 自证 `12 / 11∪{REMARKS}=12` · 29 层普查 `A14/B3/C12` · `LampPost` `61/全6字符/去重6` · `AWAITING_INPUT` 受控收口 · **v1.0 快照 84 文件 `changed = []`** · manifest 最后生成不自哈希 · 闭环物化）。

**负例 `N1–N6`：6/6 `fired ∧ hit`**（全部共用同一 `compute(p)`；恢复件缺席 ⇒ 标 **`REHEARSAL_ON_BASELINE`**）：

| 负例 | 扰动 | 设计可观测量 | 锚点 → 扰动 |
|---|---|---|---|
| `N1` | 伪 `DETECTOR_ID` | `M1b` | `ABSENT → PRESENT` |
| `N2` | 双侧注入相交 `RD_CD` | `M2` | `BLOCKED → EVALUABLE` |
| `N3` | 删 `RD_CD` 列 | `M1a` | `PRESENT → ABSENT` |
| `N4` | schema 源退化 `FGDC only` | `official_n` | `24 → 23` |
| `N5` | 伪 `LANE_NUM` | `M3` | `ABSENT → PRESENT` |
| `N6` | 填充率压 0 | `M1a` | `PRESENT → ABSENT` |

**可复现性**：两次跑 10 项产物 SHA256 **逐位一致**（`bf943e21731f1395` / `04b7f19522b92681` / `6af0caafe02d9c57` / `ffb125e099c6b386` / `090232ae6f687d3a` / `7219413735fc8aea` / `f62019c5d43906f8` / `69ee201c789b8f94` / `b57b140fbdfc0939` / `51499254f26cffd3`）。

### 15.6 缺陷登记

| 编号 | 内容 |
|---|---|
| **R1** ★**仪器实现缺陷（门禁判定分辨率）** | `G-O3R-3` 原为**全文件级** token 共现 ⇒ 无法区分「`REMARKS` 被列为臆造」与「已被更正说明」（本步 readme §2.74 正文自身即误报）⇒ 改**行级**判定。**门禁语义/阈值/判决空间一律未改** |
| `D1` | P3 测量更正（24 层 → 29 层全量），**判据未变** |
| `D2` | `lta_dynamic_data_downloader.py` 有 `if os.path.exists: skip` ⇒ **重跑不刷新**；已写入采集清单 |
| `D3` | 三跳 `BLOCKED_EMPTY_SIDE`、`M4` 受 `M2` 阻塞 ⇒ **本批不可能产生独立阳性结论**（属预期；⛔ 不得读作阴性） |
| `D4` | `GeospatialWholeIsland_Links.json` 预签名链接**已过期** ⇒ 必须自行重新请求 API |
| `D5` | `TrafficFlow_Links` 无 `*.shp.xml` ⇒ 该图层无官方 schema 自证源（承 O3-METADATA） |

### 15.7 下一步（⛔ 本节点不擅自启动）

1. **P1** 本地取回**属性完整版** `DetectorLoop` **+** `RoadSectionLine`（**两个都要**，单取 `DetectorLoop` 连不上）；
   ⚠ 重跑前**先删/改名旧 zip**；⛔ **不要在聊天里发 `AccountKey`**。
   放到 `recovery_7_9io3r/<图层名>/<图层名>.dbf` ⇒ 跑 `check_o3_recovery_inputs_7_9io3r.py` 自检 ⇒ 再跑主引擎（**仍不跑 MATSim**）。
2. **P2** 申请 On-Request `Indicative Traffic Counts at Junctions by Loop Detectors`（`Detector ID` 的**唯一来源**）⇒ **独立交叉验证**，⛔ **不得预设一定能连上**。
3. **边界保持冻结**：`B = BINDING_UNDECIDABLE` **不升级** · `TWIN_GEOMETRIC_SUBSTITUTE` **仅几何** · `F_LOW` **≠ 需求不足** · v1.0 冻结 · `signals`/`trafficDynamics`/`speedFactor` **不碰** · **不产生 v1.1**。

**最终目标**：回答 **那 `20,141 veh/h` 的「异常」对应哪个现实检测对象** —— 这才是决定是否修改 MATSim 路网 / 动力学的真正入口。

---

## 16. O3-R1 执行结果（2026-10-01，`O3-DATA-RECOVERY ✓ → O3-R1 ✓`）

> 用户裁定：**放弃「必须恢复 `DetectorLoop → Detector ID → Junction ID`」这条链**；把 O3 研究对象重定义为「**LTA 道路观测段（`TrafficFlow` Link）— `RoadSectionLine` — MATSim 道路对象**」的**空间观测单元**；**`DetectorLoop` 退为辅助空间证据**（「我们刚才申请失败了，我们就当没有这份数据吧」「完全没必要为了 O3 这一个环节把学校的数据审批流程拖起来」）。
> 新节点名 **`O3-R1：Observation-Domain Reconstruction`**（对 **576 个 residual samples / 542 个 arterial diagnostic observations** 重做观测域审计）。
> **⛔ 不碰 v1.0 · ⛔ 不重跑仿真 · ⛔ 不改 `TrafficFlow` 原始值 / crosswalk / 评价器阈值 / `signals` / `trafficDynamics` / `speedFactor`** —— 纯**诊断 / 映射审计**。
> 预注册 `PREREG_7_9I_O3R1.md`（运行前冻结，含 **§11 运行后正式更正**）· 引擎 `scripts/od/audit_o3_r1_odrecon.py` · 报告 `STEP7_9I_O3R1_REPORT.md` · 产物 **15 项 `o3r1_*`**
> 判决：**`status = RECOVERED`** · **`verdict = FACILITY_IDENTITY_UNAVAILABLE_BUT_OBSERVATION_DOMAIN_RECOVERABLE`**（硬门 **14/14** · 负例 **6/6 `fired ∧ hit`** · 15 项产物两次重跑 SHA256 **逐位一致** · `EXIT = 0`）

### 16.1 ★研究对象重定义（用户逐字）

```text
旧：observation → DetectorID → DetectorLoop → RD_CD        （⛔ 公开数据无法闭合）
新：observation → road section → MATSim links               （O3-R1 生效）
```

⇒ **主键链降级为「可选辅助实现方式」**；本步证明**不需要设施身份即可重建观测域**。

### 16.2 ★两条正式更正（**由引擎自身诊断触发**，非事后调参；两轴并报，原轴保留为审计轨迹）

| # | 判据缺陷 | 实测证据 | 更正 | 生效后 |
|---|---|---|---|---|
| **§0 方向轴** | `RoadSectionLine` **无方向语义**，有向 `circ_diff` 把**反向绘制**误判为不匹配 | `≤25 m` 的 **1,234** 条中 **730** 条有向差 **>30°**；最近距 **p50 = 6.4 m** | `TF→RSL` 改**轴向**（`min(d, 180−d)`）；`TF→MATSim` **保有向** | `TierX 537→64`；`①命中 741→1,214` |
| **§0.2 唯一性轴** | 预注册把「唯一」实现为「次近候选 ≥10 m」= **并列测试**，把**同一道路的相邻分段**误判为歧义 | `unique_gap→0` 时 `TierA 19→709` | 「唯一」= 命中候选 **`RD_CD` 去重 = 1**；`tie` 轴并报 | `TierA 19→795` |

- **门数 12 → 14**（新增 `G-O3R1-13` / `G-O3R1-14`，均为**更正可复现性**门）。
- **未受影响（一字未改）**：几何阈值 `25 / 30` · `TIER_A_SCORE_MIN = 0.70` · `TIER_B_LOOP_MAX_M = 50` · `LOOP_BANDS` · Tier 优先级 `X→A→B→C` · 判决空间阈值 `0.50 / 0.10` · 负例集合 · 判读纪律 · 边界。
- **判决稳健性**（`TierA`）：`rsl50 / ang45 / rsl50∧ang45 / score0.50 / matsim50` = **818 / 802 / 805 / 920 / 909**（基线 795）⇒ **非阈值刀锋**。

### 16.3 输入实测（Sep2026 双件，逐字解析，未采信任何转述）

| 图层 | ZIP SHA256（前 24） | 记录数 | DBF 字段 | `RD_CD` | 官方 schema（FGDC ∪ `AddField`） | 几何 |
|---|---|---|---|---|---|---|
| **`RoadSectionLine`_Sep2026** | `f817f085e2ced9dbfdd03cd0` | **15,354** | **11** | ✅ **1.0000**（distinct **3,825**） | **12**（11 ∪ 1） | POLYLINE（段 **236,677**） |
| **`DetectorLoop`_Sep2026** | `0fed9592114c196519db0a8f` | **16,275** | **1**（`OBJECTID`） | ❌ **无该列** | **12**（12 ∪ 0） | POLYGON |
| （对照）`RoadSectionLine`_Mar2026 | — | 15,329 | 4 | ❌ **0.0000** | — | — |

**★三处运行前新观测**：① **`RD_NAM` 仍被剥**（新文件「**保代码、掉路名**」，与旧文件「保文本、掉代码」**正好相反**）⇒ ②→③ **只能用 `RD_CD`**；② **`RD_CD` 含占位值** —— `NONAME` **355** 次、长度直方图 `{6: 15,351, 5: 3}`（已在 `code_term` 剔除，`n_placeholder` 命中 **90**）；③ `section_geography.csv` **574** 行 vs `crosswalk` **576** ⇒ 差 **2**（本步以 `crosswalk` 为准并显式报基数）。
**`DetectorLoop` 结论不变且已双月实测一致**（Mar2026 / Sep2026）⇒ **换月份不能解决**公开导出属性被剥的问题。

### 16.4 三层可信度 Tier（互斥，优先级 `X→A→B→C`；分母 = TF 全集 **1,278**）

| Tier | 标签 | 计数 | 占比 | 定义 |
|---|---|---|---|---|
| **A** | `DIRECT_ROAD_SECTION_OBSERVATION` | **795** | **62.21%** | 唯一 ∧ `d≤25` ∧ `ang(轴向)≤30` ∧ 合法 `RD_CD` ∧ `score≥0.70` ∧ MATSim 集非空 |
| **B** | `LOOP_SPATIALLY_ASSOCIATED` | **67** | 5.24% | 非 A，RSL 命中且 `d_loop ≤ 50`（**仅空间邻近**，⛔ 不声称 `Detector ID` 恢复） |
| **C** | `FACILITY_LINKAGE_UNRESOLVED` | **352** | 27.54% | 非 A 非 B，RSL 命中但 `d_loop > 50` 或无 loop |
| **X** | `OBS_DOMAIN_UNMAPPED`（★引擎新增，须披露） | **64** | 5.01% | 无 RSL 满足 `d≤25 ∧ ang≤30` |

**对照（审计轨迹）**：预注册原文（有向 + `tie`）= `A 25 / B 151 / C 565 / X 537`；`§0` 已生效 = `A 19 / B 246 / C 949 / X 64`。
**`match_score = 0.5·d_term + 0.3·a_term + 0.2·code_term`**（`d_term=clip(1−d/25)`、`a_term=clip(1−ang/30)`、`code_term=1 若 len==6 ∧ ∉{"NONAME",""}`）；⛔ **无「路名一致加分」项**（`RD_NAM` 被剥，结构性不可用）。

### 16.5 逐跳统计（右键覆盖率**分母 = 右键全域基数**）

| 跳 | 左→右 | `n_matched_left` | `coverage_left` | `n_matched_right` | 右键全域 | `coverage_right` | `K_pooled` | `1:1` / `1:N` / `N:1` / `N:M` |
|---|---|---|---|---|---|---|---|---|
| **① TF→RSL** | LinkID → `RD_CD` | **1,214** | **0.9499** | **134** | 3,825 | 0.0350 | **1.0000** | 19 / **1,195** / 0 / 0 |
| **② TF→MATSim** | LinkID → 有向边 | **1,104** | **0.8639** | **1,931** | 693,575 | 0.0028 | **1.8687** | **515** / 47 / **427** / 115 |
| **③ TF→LOOP** | LinkID → 检测器（≤50 m） | **252** | **0.1972** | **1,680** | 16,275 | 0.1032 | **8.4444** | 8 / 4 / 132 / **108** |

⚠️ **覆盖率陷阱仍在**：`1,931 / 693,575 = 0.28%` ⇒ ⛔ **不得外推全网**。

### 16.6 观测尺度（用户 §13 指标表）

| Tier | n | `TF_LENGTH` 中位 | `N_MATSIM` 中位 | `MATSIM_LENGTH` 中位 | `LOOP_DISTANCE` 中位 |
|---|---|---|---|---|---|
| A | 795 | 121.77 m | 1.0 | 72.74 m | 139.95 m |
| B | 67 | 135.50 m | 1.0 | 54.41 m | **13.85 m** |
| C | 352 | 140.36 m | 1.0 | 43.55 m | 248.95 m |
| X | 64 | 136.32 m | 1.5 | 50.13 m | 346.92 m |
| **全域** | **1,278** | **128.20 m** | **1.0** | **66.66 m** | — |

**★**`TF_LENGTH / MATSIM_LENGTH` ≈ **1.9×**，`N_MATSIM` 中位 **1** ⇒ **LTA 观测尺度 ≈ 2× MATSim 边尺度，非一对一 link matching**。
`DetectorLoop` 空间分档 = `LOOP_NEAR 174 · ASSOCIATED 78 · WEAK 163 · UNRESOLVED 863` ⇒ 仅 **19.7%** 观测段在 loop 50 m 邻域内。

### 16.7 ★锚点审计（回答「`F_LOW` 那批异常对应哪个现实观测对象」）

> **`F_LOW 9` 中 8/9 节落在同一条走廊 —— `AYER RAJAH EXPRESSWAY`（AYE）**：`RD_CD` = **`AYE00N`（5 节：48461/49054/48586/48708/48337）** + **`AHI00U`（3 节：49104/47163/49027，AYE 的 SLIP_ROAD 匝道段）**；余 **1** 节 = `EAST COAST PARK SERVICE ROAD`（172382，服务道路，**无 RSL 匹配 ⇒ Tier X**）。
> ⇒ 那 **`20,141 veh/h`** 的「异常」**不是全岛弥散的统计效应，而是集中在单一高速走廊上的 8 个具体观测段**。
> **同时实测**：`F_LOW 9` 的 `LOOP_DISTANCE` 全为 **328–644 m**（全部 `LOOP_UNRESOLVED`）⇒ **这些观测段在空间上远离 loop detector**（⛔ 不得据此断言「它们不是 loop 观测」）。

**`B_SET 3`**：`48461 → C / AYE00N`、`49054 → A / AYE00N`、`47189 → A / PAE02K` ⇒ **`B` 状态保持 `UNCHANGED`**（升级条件 `M1a ∧ M1b ∧ M2` 本步**未满足**；⛔ 不得据本步结论升级）。
**`F_ADQ 5`**：`45956 → A/PAE02K` · `47189 → A/PAE02K` · `45927 → A/PAE02K` · `48983 → C/AHI00U` · `129352 → C/PAE02K`。

### 16.8 ★576 靶场：`Σ` 与 `median` 口径差（诊断口径，**不替换 canonical**）

| 量 | `median`（**canonical，未被覆盖**） | `Σ`（本步**诊断口径**） |
|---|---|---|
| `R` 中位数 | **0.959004** | **3.462132** |
| `R < 1` 的节数 | **294** | **139** |

**★关键数**：**`n(R_sum ≥ 1 ∧ R_median < 1) = 155`** ⇒ **155/576（26.9%）节的残差符号在两种聚合口径下相反**。
⇒ **「`Sim/Obs` 系统性偏低」在相当程度上是聚合口径（`median` vs `Σ`）的产物，而非单纯需求不足。**
⛔ `median` canonical **一字未改、未被覆盖**（`G-O3R1-11`：`section_scale_v10/A1`、`corridor_scale_v10/A1` 四件产物 `mtime` 运行前后**未变**）。

### 16.9 硬门与负例

**`G-O3R1-1`–`G-O3R1-14` 全部 PASS（14/14）**：输入解析（8 逻辑输入）· 新 RSL 身份（`15,354 / 11 / 1.0000 / 3,825`）· `DetectorLoop` **未恢复显式记录（不静默跳过）** · 官方 schema 自证可复现 · **坐标同源（EPSG:3414）** · `RD_CD` 占位码已识别（`NONAME=355`）· 逐跳统计完备且**命中非零**（`1,214/1,104/252`）· Tier 互斥完备（`795+67+352+64=1,278`）· **AST 自检零仿真可证**（`banned_hits=[]`）· v1.0 未被触碰（`changed=[]`）· canonical 未被覆盖 · 收口一致 · **双轴更正可复现（`-13`/`-14`，两轴完备且互异）**。

**负例 `N1–N6`：6/6 `fired ∧ hit`**（全部与主路径**共用同一 `compute(p)`**）：`N1 rsl_max 25→5`（`①1,214→405`）· `N2 rsl_max 25→200`（`①1,214→1,270`）· `N3 PLACEHOLDER 置空`（`n_placeholder 90→0`；`TierA 795→799`）· `N4` 向 `DetectorLoop` 注入伪 `RD_CD`（`det_has_rdcd False→True`）· `N5 msim_max 25→1`（`②1,104→27`；`TierA 795→23`）· `N6` 关闭 `DetectorLoop`（`Tier B 67→0`，全转 C）。
⇒ `Tier A/B/C/X` 是**数据状态的结论**，**不是判据失效的伪影**。

### 16.10 缺陷登记（接续 §3 `R1–R5`）

| 编号 | 项 | 内容 |
|---|---|---|
| **`R1`** | **判据规范缺陷（方向轴）** | 见 §16.2 —— `RoadSectionLine` 无方向语义，有向判据把反向绘制误判为不匹配（**730/1,234**）。已更正为轴向；**新增 `G-O3R1-13`**。属**判据缺陷，非科学结论** |
| **`R2`** | **判据规范缺陷（唯一性轴）** | 见 §16.2 —— 「唯一」误实现为并列测试（10 m），把同一道路相邻分段判为歧义。已细化为 `RD_CD` 去重 = 1；**新增 `G-O3R1-14`**；`tie` 轴并报 |
| **`R3`** | **负例空扰动** | `N3` 首版完全静默：`n_placeholder` 误用**模块常量**而非生效的 `ph`，且 `sig` 未纳入该观测量 ⇒ 改为随 `ph` 变化 + `sig` 纳入 `nph`。**判据/阈值/门定义未改** |
| **`R4`** | **产物非确定性** | `summary.json` 含 `elapsed_s` ⇒ 两次跑哈希不同；已移出（计时仅入日志） |
| **`D1`** | 靶场集计数不一致 | `section_geography.csv` **574** vs `crosswalk` distinct **576** ⇒ 本步以 `crosswalk` 为准并显式报基数；⛔ 不擅自补 2 节 |
| **`D2`** | `RD_NAM` 不可得 | 官方并集有、交付无 ⇒ `match_score` **结构性缺失路名项**（⛔ 不以任何代理替代） |

### 16.11 下一步（⛔ 本节点不擅自启动）

1. **可选**：把本步 Tier A 观测域（**795 节**）与 576 靶场残差联结，做**观测尺度 × 残差**诊断（`Σ` / `median` 双口径）。
2. ⛔ **仍不**修改 MATSim 路网 / 动力学；⛔ **观测尺度 / 路网对象 / 交通动力学三者主因的讨论须待用户裁定后**方可开启（**顺序不得倒置**）。
3. ⛔ **不再**下载新月份 `DetectorLoop`（**双月实测一致，已定位为公开导出剥离，非月份问题**）。
4. **边界保持冻结**：`B = BINDING_UNDECIDABLE` **保持 `UNCHANGED`** · v1.0 冻结 · crosswalk / `TrafficFlow` 原始值 / 评价器阈值不碰 · `signals`/`trafficDynamics`/`speedFactor` 不碰 · ⛔ 不产生 v1.1。

**★方法学答辩口径（用户 §16 要求，可直接引用）**：
> **本研究不依赖 detector-level identity，而是以 LTA `TrafficFlow` Link 作为观测单元，通过其与 `RoadSectionLine` 的空间对应关系建立道路观测域；`DetectorLoop` 仅作为独立的设施空间证据，不将公开数据中无法获得的 `Detector ID` 作为必要关联键。**

### 16.12 ★`O3-R1：CLOSED` —— 正式冻结裁定（用户 2026-10-01 18:33，逐字照录）

**用户裁定**：**「按你最后的边界停在这里，不启动下一轮实验。」** ⇒ 本节点**正式关闭**；**不再为补 `DetectorLoop` 业务身份继续消耗时间**。

**★正式冻结状态块（用户给定，可直接引用）**

```text
Observation domain      RECOVERED
Facility identity       UNDECIDABLE
Detector ID dependency  DROPPED
v1.0                    UNCHANGED
TrafficFlow             UNCHANGED
Crosswalk               UNCHANGED
Evaluator               UNCHANGED
New simulation          NONE
```

**★两条证据链并列、不矛盾**

1. `LTA TrafficFlow Link` → `RoadSectionLine` → `RD_CD` → `MATSim link set` → `Residual / Sim-Obs` ⇒ **已 `RECOVERED`**。
2. `DetectorLoop` → `Detector ID` → `Junction ID` ⇒ **保持 `BINDING_UNDECIDABLE`**（公开数据未提供业务身份字段）。

⇒ 二者合起来即本步核心结论：**`FACILITY_IDENTITY_UNAVAILABLE_BUT_OBSERVATION_DOMAIN_RECOVERABLE`**。

**★用户点名的三个「必须正式保留」的结果**

1. **Tier A = `795 / 1,278` = 62.21%** —— 观测域失败**不是因为几何距离**：`d_near` 中位 **6.4 m**、`≤25 m` 达 **1,234/1,278** ⇒ 早期 `TierX = 537` 确为**判据伪影**（§16.2 两条更正：反向道路的**轴向**问题 + 相邻道路分段的**唯一性**问题）。
2. **`F_LOW` 的 AYE 空间集中性** —— 9 节中 **8 节属 AYE 走廊**，`20,141 veh/h` **是一条高速走廊上的 8 个观测段，不是全岛均匀弥散** ⇒ ⛔ 后续**不得**把 `F_LOW` 当作「普通全岛低流量样本」。
3. **观测尺度 `LTA 128 m` ↔ `MATSim 67 m`（≈1.9×）** —— **`LTA observation segment ≠ MATSim single link`** ⇒ 后续一切残差解释**必须**以

$$Q_{sim,g}=\sum_{l\in M_g}Q_l$$

（观测段内匹配边的仿真流量求和 vs 该观测段）为**基础口径**，⛔ **不得**回退到一对一 link matching。

**★下一步 = 机制层裁定（不跑实验）** —— 唯一待裁定问题：

> **观测尺度问题，到底只是「比较口径问题」，还是可能成为残差形成机制的一部分？**

只有该问题裁定后，才决定是否开启 **Observation Scale × Residual**；⛔ **现阶段不得先跑「尺度 × 残差」**（易把**统计口径差异**误认为**真实交通机制** = 前几轮一直在避免的「先跑结果、后定义机制」）。

**★若开启 `Observation Scale × Residual`：六项前置约束（预注册，用户给定，须逐条并列、不得删减）**

| # | 约束 |
|---|---|
| 1 | `median` 与 `Σ` **双口径**同时固定 |
| 2 | **576 个残差断面的完整分母**（⛔ 不因缺测剔除） |
| 3 | **A/B/C/X 观测域等级**随报 |
| 4 | **`LTA 128 m` ↔ `MATSim 67 m` 尺度比**随报 |
| 5 | ⛔ **不允许用尺度指标反过来定义样本** |
| 6 | ⛔ **不允许因结果显著就把「尺度相关」解释成「交通动力学机制」** |

**★边界（继续冻结）**：`B = BINDING_UNDECIDABLE` **保持** · v1.0 冻结 · `TrafficFlow` 原始值 / crosswalk / 评价器阈值**不碰** · `signals` / `trafficDynamics` / `speedFactor` **不碰** · ⛔ **不再**下载新月份 `DetectorLoop` · ⛔ **不**为 O3 单跑校内数据审批 · ⛔ **不产生** v1.1。

**★本节点性质**：**零仿真、零新实验** —— 仅**状态冻结 + 文档 / 记忆同步**。
