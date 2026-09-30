# STEP 7.9G-0 — `service` 延误机制 · R0 结构审计（零仿真 / 只读）

**STATUS: SERVICE_DELAY_R0_READY**
**CLOSURE: OK**

- 门禁：**25/25**
- prereg：`2db351c89afffa93e8ccf007e28ced9b1127ad41d992e48631db98a006f49b51`（14221 B）
- Q1 判决：`CAPACITY_CONSTRAINT_NOT_DOMINANT`
- Q2 判决：`CALIBER_FRAGILE`
- Q3 判决：`SERVICE_PARAMS_DERIVED`

## 关键数字（第一手复算）

- 全网 `delay_corr_h`（08-09）= **4778.773666**
- `service` 份额（量化校正 / canonical）= **94.356579%**
- `service` 份额（未校正 raw）= **45.903769%**
- 饱和链路承载的 service 延误份额 = **13.9452%**

## 口径矩阵（time 面，8-9）

| quantization | 份额 % |
|---|---|
| corr | 94.3566 |
| raw | 45.9038 |

## 门禁明细

| gate | pass | detail |
|---|---|---|
| `7.9G0.01_PREREG_FROZEN_AND_EMBEDDED` | ✅ | disk=2db351c89afffa93(14221B) embedded=2db351c89afffa93(14221B) |
| `7.9G0.02_SCRIPT_AST_COMPILE` | ✅ | AST_PARSE_PASS; COMPILE_PASS |
| `7.9G0.03_ZERO_SIMULATION` | ✅ | banned_imports=[]; subprocess_calls=[] |
| `7.9G0.04_INPUT_MANIFEST_COMPLETE` | ✅ | ls_final:ok;ls_viz_ref:ok;net_links_runtime:ok;src_copy:ok;cfg:ok |
| `7.9G0.05_LINKSTATS_154_COLUMNS` | ✅ | n_cols=154; missing=[] |
| `7.9G0.06_NETWORK_JOIN_COMPLETE` | ✅ | missing=0 |
| `7.9G0.07_LINKSTATS_JOIN_COMPLETE` | ✅ | missing=0 |
| `7.9G0.08_TRIPLE_FIELD_IDENTITY` | ✅ | max|d|=0 |
| `7.9G0.09_REF_LINKSTATS_BYTE_IDENTICAL` | ✅ | final=b842b93a92f41c81 viz=b842b93a92f41c81 |
| `7.9G0.10_CANONICAL_RECOMPUTE_MATCHES_7E7E` | ✅ | recomputed=94.3565788885 ref=94.3565788885 rel=0 |
| `7.9G0.11_Q1_CAPACITY_BINDING_REPORTED` | ✅ | vc p50=0.0225 p90=0.1325 max=1.0000 sat_n=74 |
| `7.9G0.12_Q1_CONCENTRATION_REPORTED` | ✅ | top10=62.1734% top100=96.0073% gini=0.9999 |
| `7.9G0.13_Q1_LENGTH_CONTROL_REPORTED` | ✅ | buckets=6 merged_n=62407 |
| `7.9G0.14_Q2_CALIBER_MATRIX_COMPLETE` | ✅ | rows=64 expected=64 nan=0 |
| `7.9G0.15_Q2_RAW_VS_CORR_DECLARED` | ✅ | corr=0.9436 raw=0.4590 |gap|=0.4845 (口径敏感性存在性) |
| `7.9G0.16_Q2_STABILITY_BAND_CONSISTENT` | ✅ | hours=['7-8', '8-9', '9-10'] shares=[0.9279, 0.9436, 0.9852] range=0.0573 band_ok=False verdict=CALIBER_FRAGILE |
| `7.9G0.17_Q3_CAPACITY_PROVENANCE_EXACT` | ✅ | service cap==unit_cap*permlanes share=1.00000000 |
| `7.9G0.18_Q3_QSIM_OVERRIDE_NONE` | ✅ | flowCap=1.0 storageCap=1.0 |
| `7.9G0.19_Q3_KNOB_CLASSIFICATION_SINGLE` | ✅ | Q1=CAPACITY_CONSTRAINT_NOT_DOMINANT Q2=CALIBER_FRAGILE Q3=SERVICE_PARAMS_DERIVED |
| `7.9G0.20_TRACEABILITY_FIELDS_COMPLETE` | ✅ | {} |
| `7.9G0.21_NO_WINDOW_MIXING` | ✅ | read_hours=['7-8', '8-9', '9-10', '10-11'] sim_window=8-9 bad=[] aggregate_cols_in_read_set=[] |
| `7.9G0.22_WRITEBACK_VERIFICATION` | ✅ | manifest_set_ok=True closure_set_ok=True disk_set_ok=True byte_mismatch=[] n_byte_compared=12 |
| `7.9G0.23_STRAY_ISOLATION` | ✅ | stray=[] |
| `7.9G0.24_TERMINAL_STATE_THREE_WAY` | ✅ | checks=SERVICE_DELAY_R0_READY summary=SERVICE_DELAY_R0_READY report=SERVICE_DELAY_R0_READY summary_share=94.35657888849315 expected=94.35657888849315 |
| `7.9G0.25_NON_7_9G_ARTIFACTS_UNCHANGED` | ✅ | checked=8 drift=[] |
