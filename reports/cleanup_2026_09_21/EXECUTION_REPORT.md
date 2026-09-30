# MATSim 仿真结果清理 · 执行报告（2026-09-21）

> 承接只读盘点报告 `CLEANUP_SCAN.md`。本报告记录**已执行**的 T0+T1 搬运、校验结果、以及**未执行**的候选。
> 执行方式：**MOVE 到 K 盘**（可逆）；**K 盘副本暂不删除**（按你的裁定）。

---

## 1. 批准范围与执行结果

| 分级 | 内容 | 规模 | 结果 |
|---|---|---:|---|
| **T1** | `reports/**/events.xml.gz` | **28 文件 / 30.607 GB** | ✅ 全部搬运 + 校验 |
| **T0** | `matsim_routechoice_7_6d/outputs/_smoke_R01_rc_min` | 53 文件 / 84.84 MB | ✅ 整目录搬运 |
| **T0** | `matsim_routechoice_7_6d/outputs/_smoke_S100k_rc_min` | 33 文件 / 85.22 MB | ✅ 整目录搬运 |
| | **合计** | **30.77 GB** | ✅ |

**搬运后 D 盘可用空间：0 B → 32.91 GB**（`reports/` 由 49.14 GB → **18.53 GB**）。

---

## 2. ⚠️ 过程中出现的一个真实阻断（已解决，需你知晓）

**现象**：第一轮搬运以**后台任务**运行，T1 的 28 个文件全部成功，但 **T0 被硬拦**：

```
[safe-delete][SAFE_DELETE_BULK_CONFIRM_REQUIRED]
{"count":81,"threshold":50,"scope":"turn",
 "targets":["...\\matsim_routechoice_7_6d\\outputs\\_smoke_R01_rc_min"]}
```

**根因**：环境的**批量删除确认门**（阈值 50 个文件 / 单轮）在**后台任务里无法弹出确认交互**，只能直接阻断 `rmtree`。于是脚本在复制完成、但源目录尚未删除时中断，D 盘残留 4 个文件、K 盘留下一个半成品副本。

**处置**：
1. 改到**前台**重跑 T0 完成脚本 → 确认门可正常交互，S100k 一次通过。
2. R01 因为 K 侧副本已完整（53 文件），D 侧只剩 4 个漏删文件 → 逐个 **md5 与 K 侧比对通过后**再删除，空目录自底向上剪除。
3. `_smoke_R01_rc_min` 在 D 盘已彻底消失（`dir still exists: False`）。

---

## 3. 校验结果：`ALL_CHECKS_PASS`

| 编号 | 校验项 | 期望 | 实测 | 结论 |
|---|---|---|---|---|
| A1 | `reports/**/events.xml.gz` 残留 | 0 | **0** | ✅ PASS |
| A2 | 两个 smoke 目录已从 D 移除 | gone | **gone / gone** | ✅ PASS |
| A3 | 需 20/20 迭代的 5 个 run（7.6B/7.6D/7.6F-0 硬门） | 20 | **E06 20/20、D02 20/20、D03 20/20、D04 20/20、S100c 20/20** | ✅ PASS |
| A4 | 受保护 `plans.xml.gz`（7.3.2b/7.3.2c 数据源） | 存在 | **两者均存在** | ✅ PASS |
| A5 | 冻结目录未被触碰 | 不变 | `final` 0.667 GB/107f、`viz` 3.806 GB/94f、`kw` 4.060 GB/94f | ✅ PASS |
| A6 | `MANIFEST_before` vs K 副本（**字节数 + 文件数**逐项） | 30/30 | **OK=30 / MISSING=0 / DIFF=0** | ✅ PASS |
| A7 | 磁盘 | — | D 32.91 GB 可用（93.1%）；K 319.98 GB 可用（27.3%） | — |
| **B** | **gzip 全流解压 + CRC 校验**（K 侧全部 `.gz`） | 0 损坏 | **50 文件 / 30.77 GB / invalid=0**（墙钟 570 s，28 进程并行） | ✅ PASS |

**关于 B 的必要性**：D 侧源文件已被解除链接，所以「字节数相同」只能证明长度一致、不能证明内容一致。
B 对 K 侧 **每一个 `.gz` 做完整解压并校验 gzip 块 CRC + 尾部 CRC32/ISIZE** ⇒ 这是当前可获得的**最强完整性证明**。

---

## 4. 安全性论证（为什么这些文件可动）

1. **T1 的 28 个 `events.xml.gz` 在 `reports/` 下零引用**：172 个脚本全扫，确认 `reports/**` 的 events **没有任何脚本读取**；仅冻结链（`final`/`viz`/`kw`）与 `routechoice` 的 events 被 7.7E / 7.9B-1 读取，**全部未动**。
2. **T0 两个 smoke 目录零引用**：逐文件反查，命中 5 处，**全部是生产者侧配置**（`config_R01_rc_min_smoke.xml`、`config_S100k_rc_min_smoke.xml`）与历史笔记，**无任何下游消费者**。
3. **附带冗余证据**：6.3 / 7.2.2 / 6.3.3b 各组内，run 级 `*.output_events.xml.gz` 与其 `ITERS/it.0/*.events.xml.gz` **互为副本**（MOVED 明细中成对出现、体积逐位相同）⇒ 本批搬运中**至少半数属纯重复**。
4. **`.gitignore` 第 200–212 行**：`/matsim_*_*/outputs/`、`populations/`、`audit/` 全部被忽略 ⇒ **不在 git 内，删除不可恢复**（这也是坚持「移到 K」而非直删的原因）。
5. **T0 以整目录搬运**（连带其内部 `linkstats.txt.gz` / `output_config*.xml` / `plans.xml.gz`）—— 这些**属于零引用 smoke run 自身产物**，非冻结链资产；搬运脚本对**目标路径**做了保护断言，冻结目录 `matsim_final_7_6h` / `matsim_viz_7_8` / `matsim_kw_7_9b1` 全程未进入工作集。

---

## 5. 可复现性资产（K 盘归档）

```
K:\_sg_matsim_cleanup_2026-09-21\
├─ CLEANUP_SCAN.md              只读盘点报告（分级建议）
├─ EXECUTION_REPORT.md          本报告
├─ VERIFY_REPORT.md             机器生成的原始校验输出
├─ _move_sim_results_to_K_2026_09_21.py   主搬运脚本
├─ _complete_t0.py              T0 补完（前台）
├─ _purge_leftovers.py          D 侧漏删文件清理（md5 比对后删）
├─ _verify_final.py             最终校验（A1–A7 + gzip 全量 CRC）
└─ sg_move_2026-09-21\          搬运目标（保留原相对路径）
   ├─ MANIFEST_before.csv       搬运前权威快照（30 项：字节数 + 文件数 + mtime）
   ├─ MANIFEST_moved.csv        搬运后状态（30/30）
   ├─ reports\...               T1 的 28 个 events
   └─ matsim_routechoice_7_6d\outputs\_smoke_*_rc_min\   T0 两个 smoke run
```

**还原方式**：把 `sg_move_2026-09-21\` 下的目录树按原相对路径复制回 `D:\Luan\2026-05\2_Singapore\` 即可（`MANIFEST_before.csv` 可用于逐项核对）。

---

## 6. 未执行的候选（等你裁定）

| 分级 | 内容 | 规模 | 备注 |
|---|---|---:|---|
| **T2** | 早期 run 的 `*plans.xml.gz` | ≈ 7.9 GB | 须精确保护 7.3.2b / 7.3.2c 各读的那 1 个 plans（已在本报告 A4 中列为受保护项） |
| **T3** | `matsim_demand_7_6f_1` + `matsim_lambda_7_6g` 的 `outputs` | 3.98 GB | 零引用 |
| **T4** | 冻结证据链（`final`/`viz`/`kw`） | 8.72 GB | ⛔ 不建议（可复现性锚点） |
| **T5** | `matsim_viz_7_8` 与 `final` 的副本去重 | 3.98 GB | 需单独授权；会改变 mtime |

**当前 D 盘 32.91 GB 可用**；若仍紧张，建议按 **T2 → T3** 顺序追加（合计约 11.9 GB → 可达 ~45 GB 可用）。

---

## 7. 冻结影响 = 无

- 未改 7.1 / 7.3.6A / OD / network / capacity / route-choice 任何一项。
- v1.0 仍是唯一冻结模型，**不产生 v1.1**。
- 本操作**不涉及仿真运行**，纯文件搬运 + 校验。
