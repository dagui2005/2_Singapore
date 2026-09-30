# STEP 7.9G-1 — 端点/接入子系统「就地吸收」机制审计 · R0（零仿真 / 只读）

**STATUS: ENDPOINT_ACCESS_R0_READY**
**CLOSURE: OK**

- 门禁：**25/25**
- prereg：`4e7ffa3c90d47eaceff07c0f4a3af45dd039a0ccd2f49f8a9f751ceb73aad2ea`（17536 B）
- A1 判决：`PROPORTIONAL_TO_MILEAGE`
- A2 判决：`ENDPOINT_LOCALIZED`
- A3 判决：`NOT_MAINLINE_QUEUE`
- A4 判决：`NEITHER_BOUND`
- A5 判决：`NEGLIGIBLE`
- A6 判决：`ENDPOINT_ABSORPTION_DOMINANT`

## 关键数字（第一手复算）

- 全网 `delay_corr_h`（08-09）= **4778.773666**（G-0 = 4778.77366611111）
- `service` 份额 canonical = **94.356579%** / raw = **45.903769%**
- 端点吸附：`p_end_svc` = **0.692865** vs 里程基线 **0.586090**（enrich **1.1822×**）
- 位置面 vs 延误面：`f_pos` = **0.088818** ; `w_ep` = **0.756366** ; `v_ep` = **0.097730**
- 干道接口：`s_main` = **1.8736%** vs 内部 `s_int` = **92.4830%**
- 绑定诊断：`sat_share_D` = **0.1394** ; `cell_share_D` = **0.4961** ; nD = 422
- 集中度：端点 service 的 top-10 占**全网**延误 **58.6647%**、top-100 **71.2746%**
- 局部循环：`f_local` = **0.001296**

## 门禁明细

| gate | pass | detail |
|---|---|---|
| `7.9G1.01_PREREG_FROZEN_AND_EMBEDDED` | ✅ | disk=4e7ffa3c90d47eac(17536B) embedded=4e7ffa3c90d47eac(17536B) |
| `7.9G1.02_SCRIPT_AST_COMPILE` | ✅ | AST_PARSE_PASS; COMPILE_PASS |
| `7.9G1.03_ZERO_SIMULATION` | ✅ | banned_imports=[]; subprocess_calls=[] |
| `7.9G1.04_INPUT_MANIFEST_COMPLETE` | ✅ | pop:ok;plans:ok;events:ok;ls_final:ok;ls_viz_ref:ok;net_links_runtime:ok;src_copy:ok |
| `7.9G1.05_LINKSTATS_154_COLUMNS` | ✅ | n_cols=154; missing=[] |
| `7.9G1.06_NETWORK_JOIN_COMPLETE` | ✅ | missing=0 |
| `7.9G1.07_LINKSTATS_JOIN_COMPLETE` | ✅ | missing=0 |
| `7.9G1.08_TRIPLE_FIELD_IDENTITY` | ✅ | max|d|=0 |
| `7.9G1.09_REF_LINKSTATS_BYTE_IDENTICAL` | ✅ | final=b842b93a92f41c81 viz=b842b93a92f41c81 |
| `7.9G1.10_ENDPOINT_LINK_EQ_ROUTE_ENDPOINT` | ✅ | compared=236044 home=1.000000 work=1.000000 expected=236044 |
| `7.9G1.11_CANONICAL_RECOMPUTE_MATCHES_G0` | ✅ | share=94.3565788885(rel=1.51e-16) total=4778.77366611111(rel=1.9e-16) |
| `7.9G1.12_A1_ENDPOINT_SHARE_REPORTED` | ✅ | p_end_svc=0.692865 mileage=0.586090 count=0.649513 enrich=1.1822 verdict=PROPORTIONAL_TO_MILEAGE |
| `7.9G1.13_A2_POSITION_VS_DELAY_DECLARED` | ✅ | f_pos=0.088818 w_ep=0.756366 v_ep=0.097730 rule=ENDPOINT_LOCALIZED verdict=ENDPOINT_LOCALIZED |
| `7.9G1.14_A2_CONCENTRATION_REPORTED` | ✅ | top10=58.6647% top100=71.2746% (of total) top10_ep=82.2001% |
| `7.9G1.15_A3_MAINLINE_ADJACENCY_REPORTED` | ✅ | s_main=1.8736% s_int=92.4830% rule=NOT_MAINLINE_QUEUE verdict=NOT_MAINLINE_QUEUE |
| `7.9G1.16_A4_STORAGE_BUCKETS_COMPLETE` | ✅ | buckets=7 n_sum=693575 nan=0 |
| `7.9G1.17_A4_VC_TENSION_DECLARED` | ✅ | sat=0.1394 cell=0.4961 vc_flow_p50=0.185 vc_storage_p50=26.02005896830059 rule=NEITHER_BOUND verdict=NEITHER_BOUND |
| `7.9G1.18_A5_LOCAL_ROUTE_SHARE_REPORTED` | ✅ | f_local=0.001296 rule=NEGLIGIBLE verdict=NEGLIGIBLE |
| `7.9G1.19_A6_MECHANISM_VERDICT_SINGLE` | ✅ | A1=PROPORTIONAL_TO_MILEAGE A2=ENDPOINT_LOCALIZED A3=NOT_MAINLINE_QUEUE A4=NEITHER_BOUND A5=NEGLIGIBLE A6=ENDPOINT_ABSORPTION_DOMINANT rule=ENDPOINT_ABSORPTION_DOMINANT |
| `7.9G1.20_EXPOSURE_FACES_COMPLETE` | ✅ | faces=['time_delay_corr_h', 'count_links_loaded', 'distance_km_loaded', 'volume_veh'] |
| `7.9G1.21_NO_WINDOW_MIXING` | ✅ | read_hours=['7-8', '8-9', '9-10', '10-11'] sim_window=8-9 bad=[] aggregate_cols=[] |
| `7.9G1.22_EVENTS_TRACE_COMPLETE` | ✅ | targets=12 with_enter=12 nan_dwell=0 |
| `7.9G1.23_TRACEABILITY_FIELDS_COMPLETE` | ✅ | {} |
| `7.9G1.24_TERMINAL_STATE_THREE_WAY` | ✅ | writeback_set_ok=True byte_bad=[] stray=[] checks=ENDPOINT_ACCESS_R0_READY summary=ENDPOINT_ACCESS_R0_READY report=ENDPOINT_ACCESS_R0_READY summary_share=94.35657888849313 expected=94.35657888849313 |
| `7.9G1.25_NON_7_9G_ARTIFACTS_UNCHANGED` | ✅ | checked=11 drift=[] |
