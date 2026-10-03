# ⤵ 恢复件投放目录（Step 7.9I-O3-DATA-RECOVERY）

把**本地重新下载**的「属性完整版」shapefile 放在这里，然后跑自检：

```bash
C:/Users/LQP/miniconda3/python.exe scripts/od/check_o3_recovery_inputs_7_9io3r.py
```

## 放什么 / 放哪里

| 优先级 | 文件 | 放到 |
|---|---|---|
| **P1** | `DetectorLoop.dbf`（+ `.shx/.prj/.shp/.shp.xml` 同目录） | `recovery_7_9io3r/DetectorLoop/` |
| **P1** | `RoadSectionLine.dbf`（同上） | `recovery_7_9io3r/RoadSectionLine/` |
| P2 | On-Request `Indicative Traffic Counts at Junctions by Loop Detectors` | `recovery_7_9io3r/junction_loop_counts/`（`.csv` 或 `.json`） |

**★ 两个 P1 都要**（只给 `DetectorLoop` 连不上）。
**★ 也可直接放 zip**：`recovery_7_9io3r/DetectorLoop.dbf` / `recovery_7_9io3r/RoadSectionLine.dbf` 亦可被识别。

## 完整清单与坑

见 `reports/corridor_scale_audit_7_9i/ACQUISITION_MANIFEST_7_9I_O3RECOVERY.md`
（含：端点与参数、**`if exists: skip` 陷阱**、期望字段、合格线、边界禁令）。

## 一句话

端点 = `GET .../GeospatialWholeIsland?ID=DetectorLoop` 与 `ID=RoadSectionLine`；
⚠️ **重跑下载脚本前必须先删/改名旧 zip，否则会被 `⊘ 文件已存在，跳过` 静默跳过**；
⛔ **不要在聊天里发 `AccountKey`**。
