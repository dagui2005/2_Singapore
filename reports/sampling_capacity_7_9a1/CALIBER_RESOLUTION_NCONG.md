# 口径决议备忘 — `N_cong` 的 `excess` 阈值

> **性质：评价器侧消歧说明（evaluator-side disambiguation note）。**
> ⛔ **不是**对 `PREREG_7_9A1.md` 的修订。预注册文件**一字未改**，其 SHA256 仍为
> `de15361a09e764de626c68fa71d931c5ad073422419a05f940a5118e44a110f7`（15,631 B，冻结于 2026-09-29 09:09:12）。
> 本备忘由评价器 `scripts/od/audit_sampling_capacity_7_9a1.py` 在**读产物之前**写出并登记自己的 SHA256。

---

## 1. 发现的矛盾（冻结文本内部不一致）

`PREREG_7_9A1.md §4.1` 对指标①的定义为：

```text
N_cong(cut) = # { HRS8-9avg > 0  ∧  excess_s >= 1.0 s  ∧  LENGTH >= cut }      cut ∈ {0, 50, 100, 200} m
```

而同一节给出的 **v1.0 登记基线**为：

```text
v1.0 基线（cut = 0，实测）：N_cong = 7,985、loaded = 224,432（3.56 %）
```

二者**不能同时成立**。对 v1.0 冻结 `linkstats`（`matsim_final_7_6h/outputs/W01_rc_min/ITERS/it.19/`，
693,575 行）逐行实测：

| # | 口径 | 条数 | 占 `loaded`(224,432) |
|---|---|---:|---:|
| A | `h89 > 0` ∧ `tt89 − ff_s >= 1.0` | 2,808 | 1.2512 % |
| B | `h89 > 0` ∧ `tt89 − ceil(ff_s) >= 1.0` | **1,308** | 0.5828 % |
| **C** | **`h89 > 0` ∧ `tt89 − ceil(ff_s) > 0`** | **7,985** | **3.5579 %** ✅ |
| D | 全体 ∧ `tt89 − ceil(ff_s) >= 1.0` | 1,308 | — |
| E | 全体 ∧ `tt89 − ff_s > 0` | 190,836 | — |

- 只有 **C** 复现登记值 `7,985`，且 `7,985 / 224,432 = 3.5579 % ≈ 3.56 %` **逐位吻合**。
- ⇒ 预注册**登记基线**对应 `excess_s > 0`（"任何真实超额"），
  **正文的 `excess_s >= 1.0 s` 是文本缺陷**（写成了绝对秒阈）。
- 附注：正判据要求 `HRS8-9avg > 0`（"载流链"），A–C 均已含该过滤；
  `loaded` 定义（`h89 > 0`）与 §4.1 的 `loaded = 224,432` 一致，无歧义。

---

## 2. 决议（确定性，不择一）

**双口径并报，主判据取预注册登记基线；A-1 与 v1.0 同口径计算。**

| 输出名 | 定义 | 角色 |
|---|---|---|
| `N_cong(cut)` | `h89 > 0 ∧ excess_s > 0 ∧ LENGTH ≥ cut` | **主**（= 登记基线 7,985） |
| `N_cong_ge1s(cut)` | `h89 > 0 ∧ excess_s ≥ 1.0 ∧ LENGTH ≥ cut` | 辅（= 1,308，正文阈值） |
| `N_slow(cut)` | `h89 > 0 ∧ ff_s/tt89 < 0.80 ∧ LENGTH ≥ cut` | 与容量/超额**无关**的独立指标（**不依赖本决议**） |

**为什么不需要另立 R2：**

1. §4.0 已冻结"**统一仪器原则**"——全部判据都是 **A-1 vs v1.0 的相对量**（倍率、新增/消失口径）。
   两个候选阈值**都**同时在两侧计算，任何相对结论都由**同一阈值**得出 ⇒ 相对判据对本歧义**不变**。
2. 本决议**不新增、不删除、不修改**任何判据、阈值、产物清单或红线；只把一个**已有**的文本歧义
   显式化为"同时报出 + 指定主判据（登记基线）"。
3. 与 §11（`v/c` 分母歧义）**同一处置精神**：预注册对已知歧义预置**消解规则**，
   本备忘即 §4.1 的消解规则，且**在读取任何 A-1 产物之前**写盘登记。
4. 若后续需要"单一口径"的正式结论，可另立 `7.9A-1-R2` 并同时作废本备忘；
   **在 R2 出现之前，本备忘为唯一的 `N_cong` 口径权威。**

---

## 3. 连带影响（已在评价器中处理）

- `a1_face_metrics.csv`：`n_cong_cut{0,50,100,200}` 与 `n_cong_ge1s` **两套并列**。
- `a1_summary.json : ratios`：`n_cong_cut0` 的倍率用**主口径**。
- 情形判定（§7 A/B/C/D）只用 `sat_km` 倍率与 `Sim/Obs` 倍率，**不含** `N_cong` ⇒ 判决天然免疫。
- `N_slow`（`speed_ratio < 0.80`）**完全不涉及容量与超额** ⇒ 与 §11、本备忘**双重无关**，
  是本步最强的"口径无关"证据。

---

## 4. 复现

```bash
# 直接复现本备忘表 A–E（只读 v1.0 linkstats）
python - <<'PY'
import gzip, csv, math
P = r"D:\Luan\2026-05\2_Singapore\matsim_final_7_6h\outputs\W01_rc_min\ITERS\it.19\W01_rc_min.19.linkstats.txt.gz"
C_LEN, C_FS, C_H89, C_TT89 = 4, 5, 32, 107
A=B=C=D=E=0; load=0
with gzip.open(P, "rt", encoding="utf-8", errors="replace") as fh:
    rd = csv.reader(fh, delimiter="\t"); next(rd, None)
    for r in rd:
        if len(r) <= C_TT89: continue
        try: L, fs, h, tt = float(r[C_LEN]), float(r[C_FS]), float(r[C_H89]), float(r[C_TT89])
        except ValueError: continue
        ff = L/fs if fs > 0 else 0.0; ffc = math.ceil(ff - 1e-9)
        exf, exc = tt - ff, tt - ffc
        if h > 0:
            load += 1
            if exf >= 1.0: A += 1
            if exc >= 1.0: B += 1
            if exc > 0:    C += 1
        if exc >= 1.0: D += 1
        if exf > 0:    E += 1
print("A",A,"B",B,"C(主)",C,"D",D,"E",E,"loaded",load)
PY
```

期望：`A 2808  B 1308  C(主) 7985  D 1308  E 190836  loaded 224432`。
