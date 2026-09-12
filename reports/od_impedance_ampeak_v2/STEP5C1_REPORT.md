# Step 5C.1 报告 · AM-peak 速度覆盖增强（三轮传播）

> 脚本：`scripts/od/enhance_ampeak_network.py`
> 输出：`reports/od_impedance_ampeak_v2/`
> 结论：**PASS**。AM 速度覆盖由 v1 的 **18.1% 长度**提升到 **38.35% 长度**；`C^AM,v2` 中位旅行时间 **21.361 min**。
> 本步**不覆盖** `reports/od_impedance_ampeak/`（v1）与 `reports/od_prior_5c/`；**未重跑 5C Gravity**（按约定）。

---

## 一、目标与判定

用户既定目标：本轮先解决 **LTA SpeedBand → OSM edge 的传播机制**（而非简单放宽匹配半径、更非用 Volume 反推速度），
把 AM 速度覆盖从 ~18.1% 提速级地扩大，并核查 AM 旅行时间是否更合理。**确认网络层改善有效后**，下一步再把它接回 Step 5B 的 Census 约束框架生成 5C.1 Prior OD。

判定：**PASS**（矩阵 332×332 全可达、无 >130 km/h 异常边、速度分层合理）。

---

## 二、运行前发现并修复的 4 处问题

| # | 位置 | 问题 | 处理 |
|---|---|---|---|
| 1 | `enhance_ampeak_network.py` `main()` | `global BAND8_SPEED,GEOM_MAX_M` 声明晚于其作为 `add_argument(default=...)` 的使用 → **SyntaxError**，脚本从未跑起来 | 将 `global` 合并到 `main()` 首行 |
| 2 | 同脚本 `LTA_LINKS` | 指向 `08_TrafficCount/TrafficSpeedBands_Links.shp`（**不存在**）；真实位置在 `Dynamic_2026_03_16/historical_data/` | 改为**候选路径列表**并自动择优 |
| 3 | Step 4 `build_impedance.py` | `READ_COLS` / `build_graph` 从未读取 OSM `name`；`network_links.csv` **只有 6 列、无 `name`** → 5C.1 的 `name_norm` 恒空、同名传播**实际不生效** | `READ_COLS` 增加 `name`；`build_graph` 贯通 `name`；`network_links.csv` 扩为 `…,highway,lanes,name` |
| 4 | 同脚本 匹配/解析循环 | 逐记录 key 扫描（≈700 万次）+ 逐行 `.iloc` → 会拖到 >15 min | 改为定长字段取值 + numpy 数组访问 → 全程 **45 s** |

> 说明：Step 4 重跑（**1m13s**）后，`C^FF` 指标**逐位一致**（可达率 1.0 / 中位 14.877969777832641 / 最大 64.06551699576448）——改动纯属“增列元数据”，未触及阻抗口径。
> 另：对同一源文件**并行**发起多个编辑会相互覆盖（读-改-写竞争），改为**串行**后 6 处改造全部落盘。

---

## 三、三级传播设计

| tier | 规则 | 置信度 |
|---|---|---|
| `geom` | LTA Link 质心 → 最近 OSM 边（≤100 m），道路名一致优先；速度取该边匹配 LTA 速度中位数 | 最高 |
| `name+hw` | 未被几何命中的边：路名命中「有 ≥3 条 LTA 证据的路名」，且其 highway 组与该路名已几何命中的 highway 组一致 | 高 |
| `name` | 同上但 highway 组不一致 | 较低 |
| `none` | 未传播，保留 Step 4 free-flow 速度 | — |

- **路名归一化**：大写 + 标点/连字符→空格 + 常见后缀缩写（AVENUE→AVE…），两侧一致。实测 **95.7% 的 LTA 路名可在 OSM 命中**（4,040 / 4,221）。
- **软护栏**：AM ≤ free-flow × 1.5 且 ≥ 5 km/h（触发 1,800 边）。
- **SpeedBand=8** 的 `MaximumSpeed=999` 哨兵 → 75 km/h 代理（显式拦截，不再产生 534.5 km/h）。

---

## 四、结果

### 4.1 AM 速度覆盖（对 `ampeak_v2_validation.json`）

| 指标 | v1（5C） | **v2（5C.1）** |
|---|---|---|
| AM 覆盖（**长度占比**） | 18.1% | **38.35%** |
| AM 覆盖（边占比） | 13.0% | **32.17%** |
| 几何匹配 LTA Link | 143,478 | 143,562 |
| 几何匹配 OSM 边 | 92,149 | 87,195 |
| 路名命中率（几何） | — | 91.93% |
| 参与传播的路名数 | — | 4,221 |

tier 分解：

| tier | 边数 | 长度 (km) | 长度占比 |
|---|---|---|---|
| `geom` | 87,195 | 2,894.9 | 18.65% |
| `name+hw` | 139,776 | 3,052.0 | 19.66% |
| `name` | 340 | 6.2 | 0.04% |
| `none` | 479,243 | 9,571.5 | 61.65% |

> 覆盖率天花板：OSM 机动车边**有名字者占 34.4% 边 / 41.1% 长度**，其中名字命中 LTA 的占 **37.4% 长度**。5C.1 的 38.35% 已基本触及该上限；剩余 `none` 多为**无名的 local / service 路**。

### 4.2 AM 旅行时间与速度合理性

| 指标 | `C^FF` | `C^AM,v1` | **`C^AM,v2`** |
|---|---|---|---|
| 中位 (min) | 14.878 | 18.131 | **21.361** |
| 均值 (min) | 15.197 | 18.481 | **21.724** |
| 最大 (min) | 64.066 | 78.953 | **89.301** |
| 相对 FF | 1.000 | 1.232 | **1.461** |
| >130 km/h 边 | 0 | 0 | **0** |
| 可达率 | 1.0 | 1.0 | **1.0** |

按道路组（已覆盖边）AM/FF 中位速比：**expressway 0.78、arterial 0.58、local 0.49** —— 高速降幅最小、地面道路降幅最大，符合早高峰实际。

**AMv2 vs AMv1**：`AMv2/AMv1 = 1.185`；**100% 的 OD 单元** AMv2 ≥ AMv1（95.5% 涨 >1 min，55.6% 涨 >3 min）。

### 4.3 λ 敏感性（Prior OD 加权平均通勤时长, min）

| λ (per min) | 5B（FF） | 5C（AM-v1） | 5C.1（AM-v2，**估算**） |
|---|---|---|---|
| 0.050 | 12.344 | 15.312 | ≈ 17.7（未跑） |
| 0.100 | 12.089 | 14.922 | ≈ 17.7（未跑） |
| 0.150 | 11.825 | 14.514 | ≈ 17.2（未跑） |

> 依据 `AMv2/AMv1 = 1.185` 粗估；**实际需运行脚本确认**（命令见 §6）。

---

## 五、判定与建议

1. **网络层改善有效**：覆盖率翻倍（18.1%→38.35% 长度），AM 中位时长 18.13→21.36 min，方向正确。
2. **仍低于现实早高峰（25–30 min）**：剩余 61.65% 长度的边（多为无名 local/service）仍用 free-flow；因此 21.36 min 仍是**下界**。
   进一步压缩空间有限（路名天花板 ~37.4%），**不建议**为此继续放宽几何半径（会引入错配）。
3. **λ 仍不冻结**：λ* 交 Step 7 TrafficFlow 目标函数决定。
4. **下一步**：把 `C^AM,v2` 接回 Step 5B 的 Census 约束框架，生成 **5C.1 Prior OD**（不覆盖 5B / 5C）。

---

## 六、复现

```bat
cd /d D:\Luan\2026-05\2_Singapore

rem 1) Step 4（若 network_links.csv 缺 name/lanes 才需重跑）
python scripts\od\build_impedance.py

rem 2) Step 5C.1 网络层
python scripts\od\enhance_ampeak_network.py

rem 3) 5C.1 Prior OD（接 5B 约束框架，本轮未执行）
python scripts\od\build_prior_od_5b.py ^
  --out reports/od_prior_5c1 --prefix prior_od_5c1 ^
  --impedance reports/od_impedance_ampeak_v2/ampeak_impedance_v2.parquet ^
  --label "Step 5C.1"
```

`reports/od_impedance_ampeak_v2/` 产物：
`lta_speedbands_ampeak.csv`、`lta_name_speed_v2.csv`、`lta_osm_match_v2.csv`、`osm_link_ampeak_speed_v2.csv`、
`ampeak_v2_speed_by_tier.csv`、`ampeak_impedance_v2.parquet`、`ampeak_impedance_v2.csv`、`ampeak_v2_validation.json`。
