# STEP 7.9E-0 — Arterial-Layer Delay Attribution Audit

**Step**: 7.9E-0 `Arterial-Layer Delay Attribution Audit`
**Scope**: zero-simulation, read-only structural attribution（不启动 MATSim、不改网络/容量/OD/QSim）
**Frozen prereg**: `PREREG_7_9E0.md`, `sha256 = 4fa98a96fd05893fb21670304fc0fc007d85f8c83b878cbe181fe11212ea08f1`（运行时重算 **MATCH**，哈希门先于一切）
**Verdict**: **`ARTERIAL_LAYER_AUDIT_BLOCKED`**（硬门 **11/12 PASS**；唯一失败项 = E0.09，见 §6）
**Runtime**: 22.1 s

---

## 0. 一句话结论

> **干道 arterial 层是 off-mainline「时间」的主承载层（车时加权 63.71%），但它不是「延误」的主承载层（延误份额 29.78%，`service` 仍以 57.10% 居首）。**
> 而且,**"arterial 是不是空间残差的主场"在本步无法判定**——冻结的 576 断面靶场中只有 **12 个** 以干道为主导（<30 门槛），E3 腿按预注册 **BLOCKED**，不做静默替代。

---

## 1. 冻结边界（未越界）

- 只读：`network_links_source_copy.csv`、W01 `it.19` linkstats、7.7C-0 `c0_section_table.csv`、7.9C-0 网络缓存、`PREREG_7_9E0.md`。
- **零仿真**：脚本内不含任何 Java/MATSim 调用 API（静态自审门 E0.02 ✓）；未写回任何冻结输入。
- 冻结件（`matsim_final_7_6h` / `matsim_viz_7_8` / `matsim_kw_7_9b1` / `spatial_residual_7_7c0`）跑前跑后 **`changed=0`**（E0.07 ✓）。
- **不产生 v1.1**；不选新的 `f_cap / SCALE / λ / service capacity / endpoint snapping`。

---

## 2. 固定分组（PREREG §3）

| 组 | 定义 | links | km |
|---|---|---|---|
| `arterial_core` | `primary ∪ secondary ∪ tertiary` | 68,882 | **2,050.7** |
| `mainline` | `motorway ∪ motorway_link` | 13,770 | 622.5 |
| `off_mainline` | `highway ∉ mainline` | 679,805 | **14,504.0** |
| 全网 | — | 693,575 | 15,126.5 |

> **⚠️ 定义提示**：本步 `mainline` **仅含 `motorway ∪ motorway_link`**（PREREG §3.2 冻结）；`trunk` 归入 `off_mainline`。这与 7.9D-0/D-2 的 `mainline = {motorway, trunk}` **不同**，故本步 `off_mainline` 数值**不与 D-2 的 `share_offmain=0.5680` 直接可比**。

---

## 3. E1 — 时间归属（PREREG §4 E1）

`ff_time_share(class) = Σ FFTT(class) / Σ FFTT(off_mainline)`，其中 `FFTT = free_flow_time_s / 3600`。

| bucket | links | km | **结构份额** `ff_time_share` | **车时加权份额** `wff_share` |
|---|---|---|---|---|
| **primary** | 25,798 | 865.0 | 0.0256 | **0.4649** |
| secondary | 19,806 | 568.6 | 0.0192 | 0.1148 |
| tertiary | 23,278 | 617.1 | 0.0228 | 0.0575 |
| **arterial_core** | **68,882** | **2,050.7** | **0.0676** | **0.6371** |
| trunk | 5,091 | 193.6 | 0.0053 | 0.1586 |
| trunk_link | 2,714 | 56.3 | 0.0020 | 0.0158 |
| primary_link | 8,077 | 102.0 | 0.0037 | 0.0129 |
| secondary_link | 3,481 | 37.8 | 0.0014 | 0.0028 |
| tertiary_link | 2,157 | 21.5 | 0.0009 | 0.0006 |
| residential | 120,396 | 2,595.4 | 0.1033 | 0.0757 |
| **service** | **450,486** | **8,865.5** | **0.7924** | **0.0889** |
| unclassified | 18,521 | 581.3 | 0.0234 | 0.0077 |
| other | 0 | 0.0 | 0.0 | 0.0 |

**★★ E1 关键**：
- **按车时（真实出行时间）加权**：`arterial_core` 承载 off-mainline **63.71%** 的自由流车时 ⇒ **干道是 off-mainline 时间的绝对主场**。
- **按结构（link-小时）加权**：`service` 因 link 数（45 万）与里程（8,865 km）巨大而占 79.24%，arterial 仅 6.76%。
- ⇒ **同一个"时间归属"问题，两个基数给出完全相反的图景**——这正是 7.9D-0「base-rate 决定偏差方向」教训在 E1 层的复现。**必须并报两个基数**。

---

## 4. E2 — 延误归属（PREREG §4 E2）

`delay_h = HRS8-9avg × max(TRAVELTIME8-9avg − free_flow_time_s, 0) / 3600`
`delay_share(class) = Σdelay_h(class) / Σdelay_h(off_mainline)`；`delay_ratio = delay_share / ff_time_share`

| bucket | delay_h | **`delay_share`** | `delay_ratio`（vs 结构） | `delay_ratio_weighted`（vs 车时） |
|---|---|---|---|---|
| **service** | **4,736.9** | **0.5710** | 0.7206 | **6.4257** |
| **primary** | 1,782.4 | **0.2149** | 8.4033 | 0.4622 |
| trunk | 550.3 | 0.0663 | **12.4805** | 0.4183 |
| secondary | 446.4 | 0.0538 | 2.8051 | 0.4687 |
| residential | 355.1 | 0.0428 | 0.4145 | 0.5656 |
| **arterial_core** | **2,470.6** | **0.2978** | **4.4075** | **0.4674** |
| tertiary | 241.8 | 0.0291 | 1.2772 | 0.5072 |
| primary_link | 73.3 | 0.0088 | 2.3811 | 0.6849 |
| trunk_link | 60.3 | 0.0073 | 3.6090 | 0.4609 |
| unclassified | 25.7 | 0.0031 | 0.1323 | 0.4049 |
| secondary_link | 18.0 | 0.0022 | 1.5404 | 0.7665 |
| tertiary_link | 5.7 | 0.0007 | 0.7937 | 1.1731 |

（分母：off-mainline 延误 = 8,295.8 h；全网延误 = 10,319.1 h）

**★★ E2 关键（两条腿结论相反）**：
1. **延误份额最大者仍是 `service`（0.5710）**，`arterial_core` 仅 **0.2978** ⇒ **干道不是延误的主承载层**。
2. **`delay_ratio` 随基数反转**：
   - vs **结构**基数：`primary 8.40`、`trunk 12.48`、`arterial_core 4.41` **≫1**，`service 0.72 <1` ⇒ 干道"异常富集"。
   - vs **车时**基数：`service 6.43 ≫1`，`arterial_core 0.47 <1` ⇒ service"异常富集"、干道反而**欠**表达。
   - ⇒ **单一 `delay_ratio` 会随基数翻转结论**；PREREG §5.1 明令必须 `ff_time_share + delay_share + delay_ratio` 三者同报，**不得**用单一"delay share 最大"或单一 ratio 判定主场。

---

## 5. E4 — 多跳 + 物理距离拓扑（PREREG §4 E4）

对每条 link 沿**有向网络反向多源 Dijkstra**（种子 = `mainline`）求其到最近 mainline 的**物理距离**（m，主指标），搜索上限 3,000 m；跳数仅辅助。

| bucket | links | finite | **中位距离 m** | p90 m | ≤300 m | ≤1000 m | ≤2000 m | `hop_median`（辅） | 延误加权距离 m |
|---|---|---|---|---|---|---|---|---|---|
| **arterial_core** | 68,882 | 0.8437 | **1,309.9** | 2,324.5 | 0.0532 | 0.3260 | 0.8198 | **52** | 1,297.1 |
| primary | 25,798 | 0.8413 | 1,288.3 | 2,344.1 | 0.0776 | 0.3563 | 0.8063 | 50 | 1,329.9 |
| secondary | 19,806 | 0.8610 | 1,287.9 | 2,336.0 | 0.0463 | 0.3152 | 0.8215 | 51 | 1,155.2 |
| tertiary | 23,278 | 0.8316 | 1,342.0 | 2,286.9 | 0.0318 | 0.3015 | 0.8334 | 56 | 1,325.1 |
| service | 450,486 | 0.7822 | 1,504.3 | 2,485.9 | 0.0130 | 0.2248 | 0.7539 | 67 | **1,831.8** |
| residential | 120,396 | 0.8626 | 1,507.0 | 2,503.3 | 0.0119 | 0.2166 | 0.7422 | 62 | 1,407.5 |
| trunk | 5,091 | 0.9083 | 1,299.2 | 2,581.7 | 0.1174 | 0.3979 | 0.7240 | 43 | 1,456.9 |
| unclassified | 18,521 | 0.5511 | 1,718.4 | 2,744.5 | 0.0207 | 0.1694 | 0.6380 | 77 | 1,563.6 |

**空间一致性（可选附加）**：抽样 12,242 条 arterial link，`中位(拓扑/直线) = 2.007`（碎化网络下拓扑约为直线 2 倍，合理），拓扑 < 直线 的违规仅 **2.12%**（几何伪影，非指标错误）。

**★★ E4 关键**：
- arterial 到 mainline 的典型距离约 **1.31 km**、中位 **52 跳**，`≤300 m` 仅 **5.32%** ⇒ **arterial 深居 off-mainline 内部，不是"贴着主线的接口/膜层"**。
- 与既有膜层对比：**ramp 478 m**（D-1）、**service 1.50 km**（延误加权 1.83 km）。arterial 的耦合距离与 service 同量级、远大于 ramp。
- ⇒ 用户假设的"**时间占比高 + 延误占比高 + 与主线具有传播关系**"三合一组合，**在 arterial 层不成立**：时间高 ✓，但延误不高 ✗（E2 份额 0.2978 < service 0.5710），与主线耦合也很弱（1.31 km / 52 跳）✗。

---

## 6. E3 — 空间残差耦合（PREREG §4 E3）→ **BLOCKED**

**断面构成（`dominant_highway`）**：

| dominant_highway | 断面数 |
|---|---|
| motorway | **449** |
| motorway_link | **92** |
| service | 16 |
| **primary** | 9 |
| unclassified | 3 |
| **primary_link** | 2 |
| **secondary** | 2 |
| residential | 1 |
| trunk | 1 |
| **tertiary** | 1 |

⇒ `arterial_core` 断面合计 **12（< 30）** ⇒ 硬门 **E0.09 FAIL** ⇒ **E3 腿 BLOCKED**（预注册 §7 第 9 条明确"不足则 BLOCKED，不静默替代"）。

**即便在欠功率样本上，也未观察到 arterial 残差耦合信号**（仅作参考，**不作判据**）：

| group | n | mean residual | median | p10 | p90 |
|---|---|---|---|---|---|
| arterial_core | 12 | **+0.0776** | −0.3717 | −0.9945 | +1.8338 |
| non_arterial | 564 | +0.1434 | −0.0336 | −0.9729 | +1.3065 |
| ALL | 576 | +0.1420 | −0.0410 | −0.9758 | +1.3324 |

- 分层置换（统计量 = arterial 均值 − 非 arterial 均值）：`obs = −0.0658`，`p(region) = 0.8534`、`p(pa) = 0.8256` ⇒ **不显著**（甚至符号为负）。
- `Spearman(residual ~ is_arterial) = −0.0213` ⇒ **≈ 0**。
- 按 `radial × reciprocal` 交叉分组亦未见一致梯度（节段级 n 极小）。

**★ 由此得到一个关于靶场本身的重要结构性发现**：
> 冻结的 576 断面靶场 **77.8% 是 motorway / motorway_link 断面**（449+92/576）——**靶场是快速路中心化的**。因此它不仅无法支撑"arterial 是否为残差主场"的检验，也**系统性地对干道层的残差不可分辨**。这是一个**靶场设计层面**的事实，不是 arterial 无罪或有罪的证据。

---

## 7. 硬门（PREREG §7，12 项）

| id | 门 | 结果 |
|---|---|---|
| E0.01 | PREREG 哈希 == 冻结值 | ✅ `4fa98a96…12ea08f1` |
| E0.02 | zero-simulation（脚本无 Java/MATSim 调用 API） | ✅ 静态自审 `forbidden_tokens=[]` |
| E0.03 | 网络字段齐全 + `matsim_link_id` 唯一 | ✅ 693,575 / id_unique=True |
| E0.04 | linkstats 字段齐全 + `LINK` 唯一 | ✅ matched=693,575, unique=True |
| E0.05 | 自由流时间有效率 ≥ 99% | ✅ 1.00000 |
| E0.06 | 三固定集合非空 | ✅ art=68,882 / main=13,770 / off=679,805 |
| E0.07 | 无输出反写冻结输入 | ✅ changed=0 |
| E0.08 | 7.7C-0 断面表可读且 ≥576 | ✅ 576 |
| **E0.09** | **`ratio_8_9` 有效样本足以做 E3** | ❌ **art=12 < 30**（non=564） |
| E0.10 | E4 用多跳（非单跳）为主结果 | ✅ hop_median=52 |
| E0.11 | 类别份额闭合（容差 1e-6） | ✅ Σff=1.000000000 / Σdelay=1.000000000 |
| E0.12 | provenance 含 路径/sha256/bytes/mtime + 脚本版本 | ✅ n_inputs=5 |

---

## 8. 预注册偏差与处理（如实上报，非静默替代）

1. **网络表来源**：PREREG §2.1 首选 `network_links_source_copy.csv`，但同文件**无 `matsim_link_id`、无 `capacity`**，而 §7 门 3 又**要求 `matsim_link_id` 唯一**。二者在源文件上不可同时满足。
   **处理**：以 **7.9C-0 缓存**为 link 表——该缓存**正是由 W01 输出网络构建**（提供 `matsim_link_id`、`capacity`、拓扑 `from/to`），并把 **source copy 的 `highway`/`name` 桥接进来**。这样门 3 成立，且 source copy 的内容被完整采用。
2. **自由流时间**：按 §2.1 优先取 source copy 的 `travel_time_s`（join 覆盖 **100.00%**，706,554 行 → 693,575 命中）；与 W01 `freespeed` 交叉校核 `med_rel = 1.62e-05`，`|rel|≤1e-4` 占 89.83%（差异源于两处 free-speed 的舍入/取整，数量级一致）。缺项时回退 `len/fs`。
3. **残差长度字段**：`c0_section_table` 无 `length_m`，仅有 **`section_length_m`**；已按此映射，`residual = ratio_8_9 − 1`。
4. **E1 基数二义性**：§4 E1 公式为**结构（未加权）**份额；用户指引关心的 `0.379` 为**车时加权**。**两者并报**（§3 两列），不加权者作 PREREG 主口径、加权者作对照。

---

## 9. 判读（PREREG §5 纪律）

- **§5.1** 已同报 `ff_time_share + delay_share + delay_ratio`，未用单一"delay share 最大"定主场。✅
- **§5.2** 已同报相关性与分层置换；样本不足按 **BLOCKED** 上报，未静默替代。✅
- **§5.3 未把 arterial 归因自动解释成容量错误**：本步至多得"arterial 承载了 63.71% 的 off-mainline 时间"这一**归因结果**；**不得**推出 "`primary/secondary/tertiary` 的容量赋值错误"——后者需**独立的容量合理性审计**（与 D-0 对 `service=400` 的处理一致）。✅
- **§5.4** 未修改模型、未产生 v1.1。✅

---

## 10. 对用户假设的回应

> 用户假设：**"真正剩下来的高价值对象，已经明显指向干道 arterial 层。"**

**部分成立，需要修正**：

| 问题 | 答案 | 证据 |
|---|---|---|
| arterial 是 off-mainline **时间**主场？ | ✅ **是** | 车时加权份额 **0.6371**（E1） |
| arterial 是 **延误**主场？ | ❌ **不是** | 延误份额 **0.2978** < `service` **0.5710**（E2） |
| arterial 是 **空间残差**主场？ | ⛔ **不可判定** | 靶场仅 12 个 arterial 断面 ⇒ E3 **BLOCKED** |
| arterial 与主线有强传播耦合？ | ❌ **弱** | 中位 **1,309.9 m / 52 跳**、`≤300 m` 仅 5.32%（E4） |

⇒ **"时间在干道、延误在 service、残差不可分辨"** 是当前最贴合证据的三分格局。**下一步不应把 arterial 当作唯一继承嫌疑；`service` 在车时基数下仍是延误第一承载层，而靶场的快速路中心化本身已成为新的约束条件。**

---

## 11. 产物清单

```
reports/arterial_delay_attribution_7_9e0/
├─ PREREG_7_9E0.md                (冻结, sha256=4fa98a96…12ea08f1)
├─ e0_checks.csv                  (12 项硬门)
├─ e0_class_summary.csv           (E1/E2 全部类别)
├─ e0_residual_coupling.csv       (E3 分组统计)
├─ e0_residual_permutation.csv    (E3 分层置换 + Spearman + radial×reciprocal)
├─ e0_topology_summary.csv        (E4 多跳物理距离)
├─ e0_input_manifest.json         (输入 path/sha256/mtime/bytes)
├─ e0_summary.json                (全量结构化结果 + verdict + flags)
├─ _run_e0.log                    (运行日志)
└─ STEP7_9E0_REPORT.md            (本报告)
scripts/od/audit_arterial_delay_7_9e0.py
```
