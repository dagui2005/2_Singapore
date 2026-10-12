# 基线封存 · 独立信任锚记录 — 2026-10-12

> 锚点版本 **`2026-10-12__v3`** ｜ 发布状态：**已发布** ｜ 生成器门禁 **17/17** ｜ 生成于 2026-10-12T21:27:20

> 对应第 2 层保护：**给「封存清单自身」加独立锚**。第 1 层（文件 ≡ 清单）见 `BASELINE_MANIFEST_2026-10-12__v3.json`。

> 本文件**不在** 92 项封存集内（锚点必须位于被它证明的对象之外）⇒ 改动它不会触发封存漂移。

## ★点信任值（Point of Trust）

```
6d80c8b3f6ec86c30049e6511bd486184f1fadb76a8d447f9b74f4e051e7d7bd
```

该值 = `sha256(ANCHOR_ROOT.txt)`。请**离线/异地**留存（手抄、自寄邮件、另一台机器）。

> 单机环境下此值无法自证；**离线记录是不可再约简的人工步骤**。


> 本文件描述锚点版本 **`2026-10-12__v3`**。


### 前序锚点版本（原样保留，只增不改）

| 版本 | 前序 PT |
|---|---|
| `2026-10-12` | `ce824bc6c8ec38249e7b23ecca5bd532e59665c60b0972c04d4b72c437729d96` |
| `2026-10-12__v2` | `9404a1fca78c7ce687ba32b304fa6b16ac3f790f723470d259cc4bbe728e217b` |

> 若前序 PT 与当前 PT 不同，属**重新生成**所致，非篡改；差异原因见项目日志 `2026-10-12.md`。

## 锚点位置

| 位置 | 路径 | 介质 | 介质独立于封存副本 |
|---|---|---|---|
| 主锚点 | `C:\Users\LQP\sg_baseline_trust_anchor\2026-10-12__v3` | disk 1（NVMe 内置） | ✔ |
| 次锚点 | `L:\_sg_matsim_trust_anchor\2026-10-12__v3` | disk 2（USB，**同 K:**） | ✘ 仅可用性/交叉核验 |

## 关键值

| 项 | 值 |
|---|---|
| 封存版本目录 | `K:\_sg_matsim_baseline_freeze\2026-10-12__v3` |
| 封存清单 | `BASELINE_MANIFEST_2026-10-12__v3.json` |
| 清单判决 / 门禁 | **BASELINE_MANIFEST_SEALED** / 16-16 |
| 条目 / 体积 | 92 / 9.332 GiB |
| **payload_root** | `56cb75712303b92061aa1a8006b761b866fd7a839159eaf248051532f1b5b110` |

### 清单自身 SHA-256（项目侧 == 锚点副本侧）

| 文件 | sha256 |
|---|---|
| `BASELINE_MANIFEST_2026-10-12__v3.csv` | `7d66c0ba12b297a5eda7508798c3f35798b98ba35178f3326a77a7690691f468` |
| `BASELINE_MANIFEST_2026-10-12__v3.json` | `c2d047ec371dba40e350303366397231e54808f73a5dc2493bc39cc2afe41579` |
| `BASELINE_MANIFEST_2026-10-12__v3.md` | `d0d3c4ac6e0f13c77d33b53ca36a2c128c26ccb59073817765f38f2e3fa56109` |

## 已认可判决（连同失败项一起锚定）

| 项 | 值 |
|---|---|
| `sealed_set` | BASELINE_MANIFEST_SEALED |
| `strict_protocol_verdict` | EXECUTION_LEVEL_PARTIAL |
| `core_exec_evidence` | D1-D4 成立（执行级路线证据） |
| `original_d5` | FAIL（原预注册判据：Top-2 应为 PIE+TPE，实际为 PIE+MCE） |
| `a5` | 补充分析（独立报告，⛔ 不替代 D5） |
| `v1_1_promotion` | 不晋升（Sim/Obs = 1.0600691 > 1.05） |
| `esb06` | 不启动（SIGNAL_CONTROL_NOT_FEASIBLE__DATA_AND_IMPLEMENTATION_GAP） |

## 核验方式

```bash
python "C:\Users\LQP\sg_baseline_trust_anchor\2026-10-12__v3\VERIFY_TRUST_ANCHOR.py"                                  # 锚点包自洽（秒级）
python "C:\Users\LQP\sg_baseline_trust_anchor\2026-10-12__v3\VERIFY_TRUST_ANCHOR.py" --expect <PT>   # 再比对离线记录
python "C:\Users\LQP\sg_baseline_trust_anchor\2026-10-12__v3\VERIFY_TRUST_ANCHOR.py" --payload "K:\_sg_matsim_baseline_freeze\2026-10-12__v3\files"   # 用锚内清单核验封存副本
```

## 边界

- 本锚只回答「**文件是不是那一批、清单是不是那一份**」，**不回答「结论对不对」**。

- ⛔ 不提升、不降低任何门禁判定：**原始 D5 仍为 FAIL**，`A5` 仍仅为补充分析。

- ⛔ 本轮未改 SCALE / 容量 / freespeed / λ / 阈值；未跑仿真；未晋升 v1.1。

---

## 附记（人工追加 · 2026-10-12）

### A. 锚点版本序列 —— 两次判据缺陷及其修复

本锚首次落地经历三次生成。**两次失败都发生在生成器自身的判据上，而不是证据文件上**；失败版本已按「只增不改」原样保留，但**其 PT 不得用作对外记录值**。

| 版本 | 结构 | 门禁 | 状态 | 判据缺陷 |
|---|---|---|---|---|
| `2026-10-12` | 写盘→门禁 | 16/17 | ⛔ 作废 | **P14**：写成 `len(rec_root) >= 10`，而实际被覆盖锚件为 **8 件 + payload_root = 9 条** ⇒ 结构性「漏列」检查缺位，靠阈值兜底 |
| `2026-10-12__v2` | 写盘→门禁 | 16/17 | ⛔ 作废 | **P11**：写作「主/次锚点均**未**覆盖既有版本」，而**重跑时前序版本必然存在** ⇒ 判据与语义不符（且 `chosen_existed_before` 在 `next_free` **之后**捕获 ⇒ 恒 `False` ⇒ 假门禁） |
| `2026-10-12__v3` | **暂存→门禁→发布** | **17/17** | ✅ **当前建立** | — |

**修复后的性质**：

- **P14** 改为**结构性判据**——「每一个被覆盖锚件都必须在 `ANCHOR_ROOT.txt` 中被列出，且哈希与实测一致」（⛔ 不写死条目阈值）。
- **P11** 改为正确语义——「前序版本**原样保留**（`sha256(ANCHOR_ROOT.txt)` 逐位不变）、本次不覆盖既有版本、次锚点逐件字节一致」。
- 生成流程改为 **暂存 → 全部门禁 → 发布** ⇒ 自本版起 **版本目录存在 ⟺ 该次门禁全通过**，失败尝试不再留下看似有效的版本目录。

> ⚠️ 两条纪律由此再次确认：**（1）判据必须结构性、⛔ 不写死阈值；（2）判据必须与语义自洽**（「只增不改」的判据是「既有**未被改动**」，而非「既有**不存在**」）。

### B. 独立位置复核结果（本次实测）

| 核验项 | 命令位置 | 结果 |
|---|---|---|
| 主锚点包自洽 + 比对离线 PT | cwd = `C:\Users\LQP`（项目与封存目录之外） | `TRUST_ANCHOR_INTACT`（bad=0） |
| 次锚点包自洽 + 比对离线 PT | 同上 | `TRUST_ANCHOR_INTACT`（bad=0） |
| 由独立位置核验封存副本 `files/` | 锚点目录（生成时 P09） | **VERIFIED=92 / MISMATCH=0 / MISSING=0** |
| 封存清单 vs 项目原件（未被本次扰动） | 锚点包核验器 | **92/92 `ALL_FILES_MATCH_THE_SEALED_SET`** |

### C. 作废版本的「自洽陷阱」

作废版本**内部是自洽的**：对它们运行 `VERIFY_TRUST_ANCHOR.py` 同样报 `TRUST_ANCHOR_INTACT`。因为它们并未被篡改，只是**生成器判据有缺陷**。
⇒ **不得以「核验通过」推断某版本有效**；版本有效性以锚点根目录的 `_ANCHOR_INDEX.md` 为准。
