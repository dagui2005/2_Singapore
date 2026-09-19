# Step 7.6G — λ 敏感度 screening（三档 λ × 单一 demand level）

**隔离工作区**：不修改 7.1 / 7.3.6A / OD / network / capacity / 200k 源人口 / route-choice 任何冻结件。

| 项 | 值 |
|---|---|
| 被扫变量 | λ ∈ {0.05, 0.075, 0.10} |
| demand level | f = 1.18（N_sim = 236,000） |
| λ 参考 | 0.075 |
| SCALE | 2.29897（全档统一，禁按 ΣEF 重算） |
| f_cap | 1.0 |
| route-choice | R01_rc_min（7.6E 冻结） |
| 靶场 | 7.3.6A Frozen crosswalk（576 池化） |
| 主口径 | MATCHED Sim/Obs(08-09) |
| Primary / Reference | `Q̄_10:19` / `Q_19` |

## 目录
```text
matsim_lambda_7_6g/
├─ README.md                              ← 本文件
├─ STEP7_6G_PREREGISTRATION.md            ← 预注册（判据/判决空间/阈值依据）
├─ lambda_sensitivity_7_6g_matrix.csv
├─ lambda_sensitivity_7_6g_lambda_invariance.csv
├─ lambda_sensitivity_7_6g_config_provenance.csv
├─ lambda_sensitivity_7_6g_config_validation.json
├─ populations/pop_L05|L75|L10/population_lambda_<TAG>.xml.gz
├─ configs/config_L05|L75|L10_rc_min.xml
├─ outputs/                               ← run 后产生
├─ logs/                                  ← run 后产生
└─ audit/                                 ← 评价后产生
```

## 状态

- 配置/人口校验：**72/72 PASS**
- 正式 run：**未启动**（需用户明确启动指令）
- 串行执行：本机 63.7 GB RAM，24g/run ⇒ 并行必 OOM；预计 ≈85 min/档，合计 ≈4.3 h
