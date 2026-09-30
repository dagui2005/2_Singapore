# 口径决议备忘：预注册 §10 判决「子义消歧」+ 两处实现缺陷修复

**适用步骤**：`7.9A-1`（sample-consistent capacity，单因子）
**冻结预注册**：`PREREG_7_9A1.md`，`sha256 = de15361a09e764de626c68fa71d931c5ad073422419a05f940a5118e44a110f7`
**本备忘立场**：⛔ **不修改预注册**（sha 不变）、⛔ 不修改任何阈值、⛔ 不修改任何判据。
本文只做两件事：**(A) 判决子义消歧**、**(B) 实现偏离冻结文本的缺陷留痕**。

---

## A. `SAMPLING_CAPACITY_NETWORK_BREAKDOWN` 的两类子义（必须分开读）

预注册 §10 把三类触发合并进同一个判决名：

| 触发源 | 门 | 语义 |
|---|---|---|
| `Sim/Obs < 0.85` | `A09` | **流量层崩解护栏**（断面级流量校准被破坏） |
| `never_arrived` 超阈 | `A10b` | **网络崩解**（车辆无法完成出行） |
| `max_stuck_car` 超阈 | `A02` / `A06` | **网络崩解**（同义） |

★ 这两种子义在物理上**完全不同**：前者是「流量水平对不上」，后者是「网络被堵死」。

### 本次实测（A-1，`f_cap = 0.434977`）

| 触发源 | 是否触发 | 实测值 |
|---|---|---|
| `A09` `Sim/Obs < 0.85` | ★**触发** | **0.7664761**（v1.0 = 0.9993348） |
| `A10b` `never_arrived` 超阈 | **未触发** | 全天未到达 **0**（dep = arr = 236,044） |
| `A02/A06` `max_stuck_car` 超阈 | **未触发** | max `stuck_car` = **0** |

⇒ **判决 = `SAMPLING_CAPACITY_NETWORK_BREAKDOWN`（因 `A09`），但其读法应按 §7 情形 D，不是字面「网络崩解」。**

### §7 情形自动分类（评价器实测）

`sat_km ×6.3729 ≥ 2.0` 且 `Sim/Obs ×0.7670 < 0.95` ⇒ **情形 D**
（原文：「流量指标严重恶化而拥堵才变合理 ⇒ 检查 OD assignment / flow scale / capacity /
departure concentration 耦合」）。

⛔ 无论取哪一种子义，预注册 §7 情形 B 与 §8 红线的处置**一致**：**不把容量调回去**。

---

## B. 两处实现缺陷（本轮修复，属「判决/门禁实现偏离冻结文本」类）

### B.1 `A03` 假门禁（第 7 次同类复现）

- **原判据**：`vd.startswith("PREPARED") or integ.get("ok") is True`
- **缺陷**：`runner` 在**跑完后合法地**把 `a1_run_integrity.json` 的 `verdict` 由
  `PREPARED_AWAITING_RUN` 改写为 `A1_RUN_COMPLETE`，而该 json 内**没有 `ok` 键**。
  实测 `verdict = A1_RUN_COMPLETE  n_checks = 42  n_pass = 41  failed = []`
  （41/42 = 1 项 `WARN`，**非失败**；`failed` 为空）。
  ⇒ `A03` **必判 FAIL** ⇒ 因 `hard_fail` 非空把总判决压成 `FAILED` ⇒ **整轮结论被误毁**。
- **修复**：跑前 / 跑后**两个合法态都算通过**：
  `verdict` 以 `PREPARED` 开头 **或** `verdict ∈ {A1_RUN_COMPLETE, RUN_COMPLETE, COMPLETE}`
  且 `failed == []`（允许 `WARN`，不允许失败项）。
- **影响面**：全脚本仅 `A03` 引用 `PREPARED`（已 `grep` 确认）⇒ 单点修复。

### B.2 `A09` 判决分支是死代码

- **原实现**：
  `hard_fail = [c["check"] for c in CHECKS if c["pass"] is False]` → 命中即 `FAILED`。
- **缺陷**：`A09`（`Sim/Obs >= 0.85`）本身是 `CHECKS` 里的一个门 ⇒ 只要 `Sim/Obs < 0.85`，
  `A09` 即 `False` ⇒ `hard_fail` 非空 ⇒ **必然**走首分支 `FAILED`；
  于是紧随其后的 `elif sim_obs_a1 < GUARDRAIL_SIM_OBS: NETWORK_BREAKDOWN`
  **永远不可达（死代码）**，与预注册 §10 直接冲突。
- **修复**：按 §10 分离崩解护栏门
  `BREAKDOWN_GATES = ("A09", "A10b")`；
  `hard_fail` 只收**契约门 / 冻结只读门**的失败，
  崩解护栏失败改判 `SAMPLING_CAPACITY_NETWORK_BREAKDOWN`。
- **未改**：阈值（`GUARDRAIL_SIM_OBS = 0.85`）、判据、预注册 sha、产物口径。

### B.3 `onset` 判据（§4.3）口径警告（非缺陷，但必须声明）

`t_onset` = A-1 `n_slow_links(t)` **首次 ≥ v1.0 同一 bin 值的 3 倍**。
v1.0 的 `n_slow_links` 在 07:00–08:55 基本**平台化**（≈2.9–3.07 万，为 `timeStepSize = 1 s` +
`TT = ceil(FF)` 对中位 11 m 短链的**量化伪影**）⇒ A-1（峰值 3.79 万）在 07:00–09:00 内
**根本达不到** 3 倍 ⇒ 实测 `t_onset = 09:20` **不代表拥堵自 09:20 才出现**，
而是「v1.0 曲线 09:00 后回落、A-1 仍高」的**交叉时刻**。
⇒ 同时报 1.5× 次级判据（`t_onset_1p5x = 09:10`、165 min）；
⛔ `duration = 155 min` **不得**读作「拥堵总时长」。

---

## C. 复现方式

```bash
# 评价器（零仿真、只读）
"C:/Users/LQP/miniconda3/python.exe" -u scripts/od/audit_sampling_capacity_7_9a1.py --guardrail
# 门禁表 / 判决 / 头条量
reports/sampling_capacity_7_9a1/_a1_checks_partial.csv
reports/sampling_capacity_7_9a1/a1_summary.json      # 键：verdict / case_7_7 / hard_fail / breakdown
```

**生成时刻**：2026-09-29（A-1 正式评价完成后）
