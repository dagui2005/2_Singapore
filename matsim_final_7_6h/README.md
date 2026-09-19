# matsim_final_7_6h — Step 7.6H **最终工作点确定与独立验证**

> 建立：2026-09-18T21:09:24   状态：**PREPARED**（24/24 零仿真校验）
> 上游：7.6G 判 `LAMBDA_DETECTABLE_NOT_IDENTIFIABLE / SPATIAL_INERT`，**结论已按现口径冻结**。

## 冻结工作点
| 项 | 值 |
|---|---|
| `λ_ref` | **0.075**（敏感度中心；⛔ 非数据最优 λ） |
| `f_demand,ref` | **1.180222**（7.6G `L75` 直跑实测隐含 f\*；插值对照 1.1803） |
| `N_base` | **200,000** |
| `N_sim` | **236,044** = round(f_ref × 200,000) |
| `SCALE` | **2.29897** ★⛔ 不得改为 459,794/N_sim |
| `f_cap` | **1.00** |
| route-choice | **R01_rc_min**（7.6E 冻结 4 项） |
| 靶场 | **7.3.6A Frozen Final Crosswalk**（只读） |

## 唯一实验臂
`W01`（λ=0.075，N_sim=236,044，20 it）→ `outputs/W01_rc_min/`

## 本步只回答 5 个问题
- **H1 可复现性**：`Sim/Obs ≈ 1.000`，且与 7.6G `L75` = 0.9998291 一致
- **H2 稳定性**：`A_10:19` / `parity_gap_rel` / `Q19/Q̄` / `never_arrived` / `max_stuck`
- **H3 空间残差仍存在**（**不追求消除**；只报告格局是否保持）
- **H4 λ 敏感性边界**：基准工作点 + λ 敏感带 `[1.1637, 1.1938]` + 静态靶场带 `[1.06945, 1.16418]`（**三层不合并**）
- **H5 未解决问题**：总体量级达标，但 EAST/NE/radial 空间残差仍在，**不宜**由 demand/λ 强行消除

## 明确不做
不再细搜 λ / 不再细化 demand grid / 不做 crosswalk-b / 不改任何冻结件 / 不把三层带压成单点。

## 运行
```
python scripts/od/prepare_final_workingpoint_7_6h.py            # 准备（零仿真）
python scripts/od/prepare_final_workingpoint_7_6h.py --run --heap 24g   # 点火（1 跑）
python scripts/od/evaluate_final_workingpoint_7_6h.py          # 评价出 H1–H5（run 后）
```
