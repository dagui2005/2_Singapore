# 执行报告 — Tier C + Tier F 清理（2026-09-21）

> 承 2026-09-21 重扫报告（`RESCAN_2026_09_21.md`）。本报告只记录**实际执行**的动作与**机器校验原始结论**。
> **结论：`ALL_CHECKS_PASS`（failures=0）。D 盘 66 GB → 72 GB 可用。**

---

## 1. 执行范围（用户裁定：**C+F，继续清**）

| 分级 | 内容 | 条目 | 规模 |
|---|---|---:|---:|
| **C** | T2+T3 剩余（`reports/**/*plans*.xml.gz` 非 `lambda_0p050` 层 17 件 + F05/F15/F25/L05/L10/L75 的 `outputs` 可弃部分 120 件） | 137 | 5.185 GB |
| **F1** | `reports/od_route_diagnosis_7_3_2b/route_agent_summary.csv`（PRODUCER-ONLY，零读者） | 1 | 1.352 GB |
| **F2** | `_smoke*` 目录 ×8 | 8 目录 / 199 文件 | 0.631 GB |
| **F3** | `_ABORTED_*` 目录 ×2 | 2 目录 / 30 文件 | 0.147 GB |
| | **合计** | **148 项** | **7.315 GB** |

> ⚠️ **勘误**：初版重扫报告把 F2/F3 记作 0.221 GB，系扫描脚本**只累加目录顶层文件、漏算子目录**所致；递归正确值 **0.778 GB**。Tier F 由 1.573 → **2.003 GB**，C+F 小计由 6.758 → **7.188 GB**（清单字节口径 7.315 GB 含目录重复计数，以 MANIFEST 去重后 7.188 GB 为准）。

**执行方式**：全部 **移到 K 盘**（`K:\_sg_matsim_cleanup_2026-09-21\`），保留原相对路径结构与 MANIFEST，**可原路还原**。⛔ 未触碰任何冻结目录（`matsim_final_7_6h` / `matsim_viz_7_8` / `matsim_kw_7_9b1` / `matsim_routechoice_7_6d`）。

---

## 2. 分批执行过程（安全门约束）

环境安全门 `SAFE_DELETE_BULK_CONFIRM_REQUIRED` 阈值 = 50 次删除/轮，**后台任务无法弹确认、只能硬拦**。故采用**分批 ≤45**：

| 批次 | 脚本 | 删除 | 复制 | 失败 | 剩余 |
|---|---|---:|---:|---:|---:|
| T2/T3 batch1 | `_move_t2t3_to_K_2026_09_21.py --max 45` | 45 | 44 | 0 | 92 |
| T2/T3 batch2 | 同上 | 45 | 44 | 0 | 45 |
| T2/T3 batch3 | 同上 | 45 | 44 | 0 | **0** |
| F 单批 | `_move_F_to_K_2026_09_21.py --max 45` | 11 目录 | 10 | 0 | **0** |

> batch1 的 `deleted=45 / copied=44` 差 1：`cf_it5.output_plans.xml.gz` 在上一轮中断时**已复制到 K、仅差 D 侧 unlink**，本批只做删除。
> 补记：上一轮中断留下的 **11 项 manifest 记账缺口**（capf_1p25×4 / capf_1p50×4 / smoke_cf_it3 / F15 modestats / F15 allVehicles）已由实际 K 树**重建补齐**，`MANIFEST_moved_2.csv` 现 **186 行 / 186 MOVED**。

---

## 3. 机器校验原始结论 —— `ALL_CHECKS_PASS`

| 编号 | 检查项 | 结果 |
|---|---|---|
| **T2T3.K** | 186/186 项在 K 且 `bytes + n_files` 全等 | **PASS** |
| **T2T3.D** | 186/186 项已从 D 移除 | **PASS** |
| **F.K** | 11/11 项在 K 且 `bytes + n_files` 全等 | **PASS** |
| **F.D** | 11/11 项已从 D 移除 | **PASS** |
| **A5** | 保护项体检 | **PASS** |
| A5-a | T2 排序冠军层 `lambda_0p050` plans（8 件）在场 | PASS |
| A5-b | `edge_route_loading.csv`（7.3.2c 数据源）在场 | PASS |
| A5-c | `matsim/step6_3/config_E06_lam0p075_cap1p00.xml`（6 个 prepare 的 BASELINE_CFG）在场 | PASS |
| A5-d | `viz` + `kw` **run 级** `output_events.xml.gz`（7.7E / analyze_kw 读）在场 | PASS |
| A5-e | `R01_rc_min.output_plans.xml.gz`（7.6C/7.6C-1 数据源）在场 | PASS |
| A5-f | **T3 六 run：20/20 迭代 `linkstats.txt.gz` + root `output_network.xml.gz` + root `output_config.xml`** | PASS |
| **A6** | **19 件冻结资产**（14 `evidence_manifest` + 5 `products`）存在且 `bytes` 与 `FINAL_MODEL_MANIFEST.json` **完全一致** | **PASS** |
| **B** | **gzip 全流解压 CRC：210 文件 / 9.388 GB / invalid = 0**（20 进程并行，224 s） | **PASS** |

```
RESULT: ALL_CHECKS_PASS   (failures=0 [])
```

**校验脚本自纠**：首版 A5 把 `linkstats` 判在 run 根目录（实际在 `ITERS/it.N/` 下）而误报 FAIL；首版 B 段缺 `if __name__ == "__main__"` 保护，Windows 下多进程重入导致 `BrokenProcessPool`。两者均为**校验器缺陷、非数据问题**，已修正后重跑全绿。

---

## 4. 空间与结构变化

| 项 | 清理前 | 清理后 | Δ |
|---|---:|---:|---:|
| **D 盘可用** | 66 GB | **72 GB** | **+6 GB** |
| `reports/` | 15.01 GB | **9.03 GB** | −5.98 GB |
| `reports/od_route_diagnosis_7_3_2b/` | 1.327 GB | **0.007 GB** | −1.320 GB |
| `reports/**/events.xml.gz` 残留 | 0 | **0** | — |
| `_smoke*` / `_ABORTED_*` 残留 | 10 | **0** | −10 |
| K 盘可用 | 317 GB | 311 GB | −6 GB |

---

## 5. 归档产物（K 盘，可还原）

```
K:\_sg_matsim_cleanup_2026-09-21\
├── sg_move_2026-09-21\        T0+T1（116 文件 / 30.773 GB）  + MANIFEST_before/moved.csv
├── sg_move2_2026-09-21\       T2+T3（186 文件 / 8.711 GB）  + MANIFEST_before_2.csv / MANIFEST_moved_2.csv
├── sg_move3_2026-09-21\       Tier F（11 项 / 2.003 GB）    + MANIFEST_before_3.csv / MANIFEST_moved_3.csv
├── _move_t2t3_to_K_2026_09_21.py     ├── _move_F_to_K_2026_09_21.py
├── _verify_CF_2026_09_21.py          └── _probe_winner.txt
├── EXECUTION_REPORT.md（T0+T1） / VERIFY_REPORT.md / CLEANUP_SCAN.md
```

**还原方式**：把对应 `sg_move*/` 目录按原相对路径复制回 `D:\Luan\2026-05\2_Singapore\` 即可。

---

## 6. 冻结影响 = 无

- 零仿真；未改 7.1 / 7.3.6A / OD / network / capacity / route-choice 任何冻结件。
- **19 件冻结资产 `bytes` 全等**（A6 PASS）；`FINAL_MODEL_MANIFEST.json` 的 `evidence_manifest` 中 **0 件涉及任何 events / linkstats / plans / outputs**。
- **v1.0 仍是唯一冻结模型，不产生 v1.1。**
- `_probe_winner.txt` 排序探针运行前后 **`SAME = True`** —— `diagnose_route_structure_7_3_2b` / `diagnose_motorway_loading_7_3_2c` 的 `find_existing()` 输入解析结果未改变。

---

## 7. 仍未执行（**需显式授权**）

| 分级 | 内容 | 规模 | 备注 |
|---|---|---:|---|
| **D1** | `viz` / `kw` 的 `ITERS/it.19/*.events.xml.gz`（与 run 级 MD5 逐位相同） | 3.234 GB | 分析侧零消费者；但 producer 默认校验（`B1.43–B1.46` / `V44–V47`）会读它 |
| **D2** | `matsim_viz_7_8` 非 events 主体（与 `final` 逐位相同） | 0.649 GB | viz 自身 linkstats 被 7.7E / 7.8-diagnose 读 ⇒ **只能硬链接、不能删** |
| 旁支 | `osm/*.dbf` ↔ `Singapore_OD_MATSim_FinalData/07_RoadNetwork/*.dbf`（6 个 `.dbf` size+partial-md5 全等） | ≈8.14 GB 重复 | ⛔ 非 MATSim 产物，且属 OSM 源数据 |

**D1+D2 的零损失正解 = NTFS 硬链接**（实测 `os.link` 可用）：占用归零、`exists()/getsize()/open()` 全照常、引用零破坏。
**代价**：会改写冻结目录 `matsim_viz_7_8/`、`matsim_kw_7_9b1/` 的目录项，与 `audit_sampling_capacity_7_9a0.py:682`「⛔ 不得改 `matsim_viz_7_8/` 任何文件」的纪律直接冲突 ⇒ **需你明确破例授权**。
