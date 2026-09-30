# 口径决议备忘 — `enroute(t)` 的定义不自洽

> **性质：评价器侧消歧说明（evaluator-side disambiguation note）。**
> ⛔ **不是**对 `PREREG_7_9A1.md` 的修订。预注册文件**一字未改**，其 SHA256 仍为
> `de15361a09e764de626c68fa71d931c5ad073422419a05f940a5118e44a110f7`（15,631 B，冻结于 2026-09-29 09:09:12）。
> 本备忘为 **`CALIBER_RESOLUTION_NCONG.md` 的姊妹件**（后者处置 §4.1 的 `excess` 阈值歧义）。

---

## 1. 发现的矛盾（冻结文本**结构性**不自洽）

`PREREG_7_9A1.md §4.3` 对指标③的第三个序列定义为：

```text
enroute(t) = 在途车辆数（已 `entered link` 未 `left link`）
```

该定义**按字面实现会得到物理上不可能的曲线**。对 v1.0 的冻结 events
（`matsim_viz_7_8/outputs/W01_events/ITERS/it.19/W01_events.19.events.xml.gz`，1,694,011,331 B）
按字面配对实测（5-min bin，06:00–12:00）：

| # | 口径 | 峰值 | 峰时 |
|---|---|---:|---|
| a | **字面**「`entered link` 未 `left link`」 | **236,039** | 09:50 |
| **b** | **在网车辆**（本备忘决议） | **36,176** | **08:55** |
| c | 独立来源：`legHistogram.txt` `en-route_all` / `en-route_car` | **36,799** | **08:55** |

- 口径 **a** 的峰值 **236,039 ≈ 全部车辆数 236,044**，且**随出发数单调同步增长**
  （实测 `n_pair_miss = 236,039`、`n_pair_net = 236,039`；事件流时间序完好，`n_back = 0`）。
- **根因**：MATSim **不为每趟行程的最后一条 link 发 `left link`** ⇒ 每辆车**约**有 1 个未配对的
  `entered link`（窗口内实测 `n_pair_miss = 236,039`，车辆数 `236,044`，差 **5 条 = 0.002 %**，
  系 `06:00–12:00` 窗口边界效应）⇒ 字面口径实际度量的是「**在网车辆 + 已完成车辆**」，
  随模拟推进必然趋于车辆总数。
- ⇒ 这不是"另一种口径"，而是**结构上不自洽的仪器**：它**不可能**呈现"形成—消散"形态，
  而"形成—消散"正是指标③的全部意义。

---

## 2. 决议（确定性，不择一；在读取任何 A-1 产物之前生效）

```text
enroute(t) = n_on(t) − |pending(t)|
    n_on(t)    = #`vehicle enters traffic`(≤ t) − #`vehicle leaves traffic`(≤ t)    # 系统内车辆
    pending(t) = 已 `vehicle enters traffic` 但**尚未** `entered link`（等待插入）的车辆集合
```

- `n_on` 减 `pending` = **真正在网（已进 link 未出网）的车辆数**；两者皆由**配对无关**的计数器得出，
  不需要 `entered link` / `left link` 配对 ⇒ **对末链缺失天然免疫**。
- 字面口径（a）**保留留痕**为 `enroute_pair(t)`，随 `a1_time_series.csv` 一并落盘，便于审计对账。
- ⛔ 本决议**不新增、不删除、不修改**任何判据、阈值、产物清单或红线。相对判据（§4.0 统一仪器原则）
  在本决议下**不变**：A-1 与 v1.0 用**同一段代码**算 `enroute`。

---

## 3. 交叉验证（同一仪器 vs 独立来源）

`legHistogram.txt` 是 **MATSim 自己**（`LegHistogramListener`）写出的 5-min bin 统计，
与本评价器的 events 流式解析**完全独立**。二者对 v1.0 的一致性是本决议的**外部证据**：

| 量 | 本评价器（events 逐条配对） | `legHistogram`（MATSim 内部） | 差 |
|---|---:|---:|---:|
| 峰值在途 | **36,176** | **36,799** | **−1.69 %** |
| 峰时 | **08:55** | **08:55**（`t = 32,100 s`） | 完全一致 |

- 门 `B02` 判据为 **±3 %**（在途量与 `legHistogram` 一致）⇒ **PASS**。
- 残差 −1.69 % 的成因：`legHistogram` 按 **bin 右端**记账、本评价器按**事件时刻**记账，
  且 `en-route` 在 bin 内是**瞬时量**、二者取样时刻不同 ⇒ 属**口径级采样差**，非缺陷。
- 对 `acc_n`（该链路上车辆级样本数）的影响 **≈0.29 %**，且**两侧同源** ⇒ 全部相对判据免疫。

---

## 4. 与 `n_queued(t)` 的关系（无歧义）

§4.3 的 `n_queued(t)` 定义为「该时刻**已 `vehicle enters traffic` 但尚未 `entered link`** 的车辆数（等待插入）」，
与实现中的 `pending` **逐字一致**，**不涉及** `left link` ⇒ **无歧义，按字面实现**。
实测 v1.0 `max queued = 57 @08:15`（≈0 排队，与 v1.0 几乎不堵一致）。

---

## 5. 复现

```bash
# 直接复现本备忘表 a/b/c（只读 v1.0 events，约 12 min；或读已落盘缓存）
python scripts/od/prewarm_events_7_9a1.py --check
```

缓存文件：`reports/sampling_capacity_7_9a1/_events_cache/v1.0_W01_events.19.events.xml.gz_<sha16>_cm1_fp<fp>.json`
（`payload.bins[*].enroute_end` = 口径 b、`payload.bins[*].enroute_pair_end` = 口径 a、
`payload.n_pair_miss` = 未配对 `entered link` 数）。

期望：`n_pair_miss = 236039`、`enroute_pair_end` 峰 **236,039 @09:50**、`enroute_end` 峰 **36,176 @08:55**。

---

## 6. 连带影响（已在评价器中处理）

- `a1_time_series.csv`：`enroute` 列（口径 b）与 `n_queued` 列并列；口径 a 不进入该 CSV，仅存于 events 缓存留痕。
- `a1_summary.json : time_profile`：`enroute_max` / `enroute_peak_hms` 用口径 b。
- 情形判定（§7 A/B/C/D）只用 `sat_km` 倍率与 `Sim/Obs` 倍率，**不含** `enroute` ⇒ 判决天然免疫。
