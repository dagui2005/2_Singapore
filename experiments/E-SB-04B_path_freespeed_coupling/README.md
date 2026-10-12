# E-SB-04B —— 自由流速度变更与路径重分配的空间耦合审计

> **零仿真 · 只读**（未启动 MATSim；未改 network / population / capacity / `freespeed` /
> `SCALE` / lambda / 阈值 / 任何冻结件；未生成 v1.1）
> 日期：**2026-10-11** ｜ 预注册协议：`PROTOCOL_E-SB-04B.md`（含 §11 判据修订记录）
> 上游：`E-SB-04 = PATH_REDISTRIBUTION_SUPPORTED`（plans 级，路线变化 66.06%）

## 一句话

**判决 = `FREESPEED_ROUTE_COUPLING_SUPPORTED`（证据等级 = `PLANS_LEVEL`）。**
SB-A5 的 `freespeed` 变更**主要落在路面/地方道路（普遍降速）**，而**快速路相对变快**；
计划路线的改变**朝着新网络下更快的方向**（route-effect **+0.438 m/s**，约**补偿 49%** 的网络降速），
并在**走廊层面**与观测域流量增量同序；负例对照（空间 shuffle，z≈+43 / +20）支持该关联
**不是**「快速路本身流量大」的伪关联。

## 关键实测

### 检查 1 —— `freespeed` 变更的空间特征（阶段 2）

| 项 | 实测 |
|---|---|
| 变更链 / 方向 | **90,643**（升 19,635 / **降 71,008**），占全网 693,575 的 13.1% |
| 变更里程 | **2,695 km** / 全网 15,127 km（**17.82%**） |
| 净降速 | `Σ len·Δfree` = **−7,984,712 m²/s**（< 0） |
| 里程加权 Δfree | **路面干道 −1.0837 m/s ｜ 快速路 +0.2388 m/s** ⇒ **快速路相对变快** |
| 变更集中处 | residential −2.12 m/s（35,046 链）；primary −1.16（11,234）；trunk −0.79；motorway 仅 280 链（5.9%） |
| 唯一升速类 | `motorway_link` **+1.25 m/s**（2,228 链） |

### 检查 2 —— 路线变化 ↔ 速度变更（阶段 3，逐 person）

| 组 | n | Δfs (m/s) | **route-effect** | **network-effect** | 降速链暴露(v1.0) |
|---|---:|---:|---:|---:|---:|
| 未变化 | 80,116 | −0.7287 | **+0.0000** | −0.7287 | 0.2361 |
| 变化 | 155,928 | −0.4522 | **+0.4382** | −0.8904 | 0.2598 |

- 分解恒等式 `Δfs = route-effect + network-effect`；改道**补偿约 49.2%** 的网络降速。
- `route-effect` 在未变化者上**严格为 0**（`R5≡R10`）⇒ placebo 成立。

### 检查 3 —— 观测域 ΔQ ↔ `freespeed` 变更（阶段 4，逐匹配边）

| fs 是否变更 | n_edges | ΣΔQ 净 | 占净增 | 单位边净增 | ΔQ 率 |
|---|---:|---:|---:|---:|---:|
| **未变更** | 2,498 | **+168,167.8** | **82.7%** | +67.32 | +6.971% |
| 变更 | 695 | +35,278.1 | 17.3% | +50.76 | +10.729% |

⇒ 观测域流量增量的 **82.7% 落在 `freespeed` 未变更的匹配边上** ⇒ **本地速度效应不足以解释**，
必须是**路径重分配**（与 E-SB-04 一致）。走廊 route-use Δ vs ΔQ 净额 **Spearman = 0.667**。

### 检查 4 —— 负例对照（阶段 5）

| 统计量 | 置换 | 观测 | 置换均值 | **z** | 经验百分位 |
|---|---|---:|---:|---:|---:|
| route-effect 均值 | global | +0.43819 | +0.15656 | **+43.19** | 100.0% |
| route-effect 均值 | within_highway | +0.43819 | +0.21427 | **+29.88** | 100.0% |
| 降速暴露差 | global | +0.02374 | −0.00001 | **+19.92** | 100.0% |
| 降速暴露差 | within_highway | +0.02374 | +0.00824 | **+11.49** | 100.0% |

⇒ 全部远超 95 百分位（`n_perm = 500`）⇒ **非随机空间指派**。

## 证据等级与边界

- **`PLANS_LEVEL`**：SB-A5 **无 events**，其**执行路线未被直接观测**。v1.0 侧 plans↔events
  一致率 **100.000%**（n=8,000）只增强**计划路线**的可信度。
  ⛔ 不得写作「已证实的执行级路径重分配」。
- ⛔ 与已 `CLOSED` 的 **O3-R1「承载对象替代」分列**（层级不同，不合并）。
- ⛔ 匹配边仅占全网高峰 ~6.6% ⇒ 结论**不得外推**到全网。

## 判据修订（★先于二次执行登记，见协议 §11）

预注册的 `B1/B2/B5` 经复核为**协议内部自相矛盾**（`Δfs` 含 `network-effect`，与 `A1` 净降速冲突），
**保留实录（`status=retracted_misspecified`）但不参与判决**；判决改用作用在**分解项**上的
`B1c/B2c/B5c`。修订由**先验逻辑矛盾**触发，非由结果好坏触发。

## 目录

```
experiments/E-SB-04B_path_freespeed_coupling/
  PROTOCOL_E-SB-04B.md     预注册协议（§11 修订记录）
  README.md                本文件
  _cache/                  perm_inputs.npz（置换聚合向量 A/B/C/DFREE/FS10）等中间件
reports/path_redistribution_audit_E_SB_04B/
  VERDICT_E-SB-04B.md      判决书
  coupling_scorecard.csv   四区块判据记分卡
  freespeed_change_summary.csv / _by_corridor.csv / _distribution.csv
  route_freespeed_coupling.csv / route_delta_exposure.csv（逐人，236,044 行）
  section_delta_coupling.csv / _by_changed.csv / corridor_coupling_decomposition.csv
  negative_control_shuffle.csv
  gate_checks.csv / input_manifest.json / esb04b_summary.json
```

## 复现

```bash
python scripts/experiments/esb04b_coupling_audit.py        # 阶段 1–4（约 1.5 min）
python scripts/experiments/esb04b_negcontrol_verdict.py    # 阶段 5 + 渲染
```

## 下一步（★预注册动作，需用户裁定）

- **若采纳**：对 SB-A5 开启 `writeEventsInterval=19` **重跑一轮**（新 `outputDirectory`/`runId`，
  其余模型设置不变），比较新旧 LinkStats 检查开启事件记录是否改变原有结果 ⇒ 把结论
  从 `PLANS_LEVEL` 提升到**执行级**。
- ⛔ 本轮未启动任何 MATSim；⛔ 不调 `SCALE`/容量/`freespeed`/lambda/阈值；
  ⛔ 不启动信号灯/交叉口实验；⛔ 不晋升 v1.1。
