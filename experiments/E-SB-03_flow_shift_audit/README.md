# E-SB-03 —— 自由流速度变化后的观测域流量偏移审计

> 状态：**已完成**（2026-10-11）· 性质：**零仿真·只读**
> 协议：`PROTOCOL_E-SB-03.md` ｜ 报告：`reports/esb03_flow_shift_audit/REPORT.md`
> 门禁：**11/11 PASS**

## 一句话
**不是**「怎样把 `Sim/Obs` 从 1.0601 调回 1.0」，**而是**「1.0601 到底反映了什么」。

## 判决（实测驱动）
| 分支 | 是否成立 | 实测依据 |
|---|---|---|
| A 时间窗转移 | ❌ | 07–08 +6.17% / 08–09 +6.08%（同向） |
| **B 路径重分配** | **✅ 主因** | 匹配边 **+7.19%** vs 全网 **−0.53%**；Top-2 快速路（PIE+TPE）占净增 **63.4%** |
| C 聚合/匹配口径 | ❌ | `R(A5/v1.0)` 稳定 `[1.0367, 1.0681]` |
| D 需求扩展系数 `SCALE` | ❌ | 固定 `SCALE` 恒等式（门禁 E03 `1.0607747494`）已证不能产生该差 |

**⇒ 上升是「负荷向被观测的快速路走廊集中」，不是「车变多」，也不是口径问题。**
**⇒ 按预注册决策规则：下一步查路径重分配与观测域覆盖，⛔ 不调全网容量、⛔ 不反调 `SCALE`。**

## 目录
```
PROTOCOL_E-SB-03.md               预注册协议
audit/
  esb03_total_decomposition.csv     表 1 总量分解
  esb03_section_delta.csv           表 2 逐断面差异（576 行）
  esb03_concentration_by_group.csv  表 2b 分组集中度
  esb03_network_vs_matched.csv      全网 vs 匹配子集
  esb03_window_sensitivity.csv      表 3a 时间窗（24 小时）
  esb03_aggregation_sensitivity.csv 表 3b 聚合 / 匹配集敏感性
  esb03_gates.csv                   门禁 11/11
  esb03_summary.json                汇总（报告的唯一数据源）
  *_allhours_conv.linkstats.txt.gz  自建全时段 cycle-mean（it.10–19）
```

## 复现
```bash
python scripts/experiments/esb03_flow_shift_audit.py     # 审计（~9 min；有缓存，二次秒级）
python scripts/experiments/esb03_render_report.py        # 由 summary.json 渲染 REPORT.md
```

## 口径（与冻结评分器逐位同源）
- 断面 sim = `median(匹配有向边 HRSx-yavg) × SCALE`，`SCALE = 2.29897`，**576 断面**
- 主窗 08-09（`HRS8-9avg`）· 周期均值 = it.10–19 逐列均值
- ⛔ 未改 v1.0 / 网络 / OD / crosswalk / `TrafficFlow` / `SpeedBand` / 阈值 / `SCALE`；未启动 MATSim
