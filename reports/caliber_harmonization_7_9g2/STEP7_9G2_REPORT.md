# STEP 7.9G-2 — 「时间 / 数量 / 距离 / 体积」四面口径统一 · R0（零仿真 / 只读）

**STATUS: CALIBER_HARMONIZATION_R0_READY**
**CLOSURE: OK**

- 门禁：**25/25**
- prereg：`6df55c428f1de8bc75d0e76267ccbe8f37ea0fe0c44c6d50dc9a5377f6d96260`（22238 B）
- 判决：Q1 `DENOMINATOR_SPLIT` / Q2 `EXPOSURE_IMPACT_DECOUPLED` / Q3 `CONCENTRATION_ATTENUATED`（SVC：`CONCENTRATION_ATTENUATED`）/ Q4 `FOUR_FACE_PARALLEL_REPORTING`
- 无操作自检：`noop_selfcheck_passed=True`（noop_identity_holds=True; contradictory_mutation_fires=True）

## 一、统一规则（本节点交付物）

```text
D0 = ALL_LOADED ⊃ D1 = SERVICE_LOADED ⊃ D2 = ENDPOINT_SERVICE_LOADED   （默认宇宙 U_loaded）
time -> IMPACT ; count / distance / volume -> EXPOSURE                 （角色固定，不互替）
任何份额写作 share[face, scope | Dk] @ universe                         （四要素缺一不可）
禁止合成总分；禁止用 Gini 或常数 top-k 作集中度判据
集中度主仪器 = 覆盖率分数 f_t = k_t / n_scope , t ∈ {50,90,99}
```

> **`service` 端点链对仿真延误具有显著的时间暴露特征，但其影响并不与交通流量占比同步增长；
> 因此应分别从时间、数量、距离和交通量四个维度表征，而不能以单一 `delay share`
> 作为系统性拥堵归因依据。**

## 二、四面实测（EP_SVC ｜ D0）

| Face | Role | U_loaded | U_any | 撕裂 (pp) |
|---|---|---:|---:|---:|
| count | EXPOSURE | 3.155967% | 1.464297% | 1.691670 |
| distance | EXPOSURE | 3.922029% | 1.959488% | 1.962541 |
| volume | EXPOSURE | 0.421506% | 0.421506% | 0.000000 |
| time | IMPACT | 71.368133% | 71.368133% | 0.000000 |

- 四面极差 `RANGE_ep` = **70.946627 pp**（band = 5.00 pp）
- 宇宙撕裂 `SPREAD_U` = **1.962541 pp**（tol = 0.50 pp）
- 非法混合宇宙比 `SVC_any_km / ALL_loaded_km` = **1.709605**（>1 ⇒ 门 10 显式标注 ILLEGAL）

## 三、锚点复算（逐位，atol = 0）

| Scope | n | km | vol | delay_h |
|---|---:|---:|---:|---:|
| D0 ALL_LOADED | 224432 | 5185.704197 | 40008184.000000 | 4778.773666 |
| D1 SVC_LOADED | 62407 | 962.715006 | 1725544.000000 | 4509.087344 |
| D2 EP_SVC_LOADED | 7083 | 203.384816 | 168637.000000 | 3410.521558 |
| U_any EP_SVC | 10156 | 296.402279 | 168637.000000 | 3410.521558 |
| U_any SVC | 450486 | 8865.505964 | nan | 4509.087344 |

## 四、门禁明细

| Gate | Pass | Detail |
|---|---|---|
| `7.9G2.01_PREREG_FROZEN_AND_EMBEDDED` | PASS | bytes=22238 (declared 22238); sha=6df55c428f1de8bc… match=True |
| `7.9G2.02_SCRIPT_AST_COMPILE` | PASS | ast_parse=OK compile=OK n_lines=1408 |
| `7.9G2.03_ZERO_SIMULATION` | PASS | banned_hits=[] |
| `7.9G2.04_INPUT_MANIFEST_COMPLETE` | PASS | manifest_items=5 mismatched=[] |
| `7.9G2.05_LINKSTATS_154_COLUMNS` | PASS | n_cols=154 (expected 154); required_missing=[] |
| `7.9G2.06_NETWORK_JOIN_COMPLETE` | PASS | net_links=693575; ls_links=693575; net∩ls=693575; len(U_any)=src_copy∩runtime=693575; ls_not_in_net=0; unmatched=0 |
| `7.9G2.07_LINKSTATS_JOIN_COMPLETE` | PASS | sha(I2)==sha(I3):True; ls_rows=693575 covered=693575 |
| `7.9G2.08_UNIVERSE_DECLARED_PER_ROW` | PASS | tagged_checked=10 exempt=['g2_checks.csv', 'g2_closure_check.csv', 'g2_input_manifest.json', 'g2_summary.json', 'g2_reporting_template.md', 'STEP7_9G2_REPORT.md'] problems=[] |
| `7.9G2.09_UNIVERSE_SINGLE_PER_COMPARISON` | PASS | combos_with_multiple_universes=[] (scope names are universe-specific) |
| `7.9G2.10_NO_IMPOSSIBLE_SHARE` | PASS | max_legal_share=1.000000000; impossible_rows=0; illegal_mixed_universe_ratio=1.709605027 (>1 => captured & labelled ILLEGAL_MIXED_UNIVERSE, excluded); n_legal=32 |
| `7.9G2.11_NESTED_DENOMINATOR_MONOTONIC` | PASS | monotonic_violations=[] |
| `7.9G2.12_DENOMINATOR_DECLARED_PER_ROW` | PASS | problems=[] allowed=['D0', 'D1', 'D2'] |
| `7.9G2.13_FACE_ROLE_DECLARED` | PASS | face_role_map={'count': 'EXPOSURE', 'distance': 'EXPOSURE', 'volume': 'EXPOSURE', 'time': 'IMPACT'} |
| `7.9G2.14_FOUR_FACE_MATRIX_COMPLETE` | PASS | rows=12 combos=12/12 nans=0 |
| `7.9G2.15_FACE_RECOMPUTE_MATCHES_G0` | PASS | bit_exact(atol=0,rtol=0) failures=[]; compared_rows=4 |
| `7.9G2.16_EP_SVC_RECOMPUTE_MATCHES_G1` | PASS | vol=168637.0 match=True; delay_h match=True; length_km U_any=296.40227899999996==file(296.40227899999996) True; U_loaded=203.384816 explicitly labelled |
| `7.9G2.17_IMPACT_ONLY_FROM_TIME_FACE` | PASS | forbidden_impact_columns=[] |
| `7.9G2.18_INTENSITY_REPORTED` | PASS | rows=9 combos=9/9 nans=0 |
| `7.9G2.19_NO_COMPOSITE_INDEX` | PASS | bad_columns=[]; banned_identifiers=[] |
| `7.9G2.20_CONCENTRATION_INSTRUMENT_DECLARED` | PASS | instrument=['coverage_fraction']; targets=[50, 90, 99]; constant_k_hits=[]; k_rule=minimum k such that cumsum(sort(delay_corr_h desc)) … |
| `7.9G2.21_CONCENTRATION_BASELINE_PAIRED` | PASS | unpaired_cells=[] (n=0); rows=15 |
| `7.9G2.22_CONCENTRATION_VERDICT_SINGLE` | PASS | closed_set_values=['CONCENTRATION_ATTENUATED'] primary=CONCENTRATION_ATTENUATED Q3=CONCENTRATION_ATTENUATED recomputed=CONCENTRATION_ATTENUATED R_t=[1.0, 3.1467, 19.8038, 1.0, 2.1462, 6.6438, 1.0, 1.1519, 1.0321] |
| `7.9G2.23_GINI_FORBIDDEN_AS_CRITERION` | PASS | artifacts_with_gini_column=['denominator_audit']; gini_in_decision_columns=[]; gini_in_comparisons=[]; descriptive_only=True |
| `7.9G2.24_TERMINAL_STATE_THREE_WAY` | PASS | writeback_set_ok=True byte_bad=[] stray=[] checks=CALIBER_HARMONIZATION_R0_READY summary=CALIBER_HARMONIZATION_R0_READY report=CALIBER_HARMONIZATION_R0_READY summary_time_share=71.36813325066313 expected=71.36813325066313 |
| `7.9G2.25_NON_7_9G_ARTIFACTS_UNCHANGED` | PASS | guard_dirs=2 guard_files=32 drift=[] out_inside_guard=False |

## 五、边界

- 本节点**只**统一口径与表达，不重判 G-1 的 `A1–A6`，不新增机制假说。
- 未改 `Singapore_OD_MATSim_Final_v1.0`；未回写 G-0/G-1 任何冻结产物；未重跑 MATSim。

