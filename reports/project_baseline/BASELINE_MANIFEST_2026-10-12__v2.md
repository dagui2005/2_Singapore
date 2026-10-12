# 基线 SHA-256 清单 — 2026-10-12

> **判决**：`BASELINE_MANIFEST_SEALED` ｜ 门禁 **16/16 PASS** ｜ 条目 **92** ｜ 总计 **9.33 GiB** ｜ 缺失 **0**

> 生成器 `scripts/experiments/baseline_manifest.py`（自登记，可检出日后改动）｜ 生成于 2026-10-12T07:38:20 ｜ 用时 288.9 s

> **目的**：回答「今天用来支撑这些结论的文件，是否就是当时真正生成和复核过的那一批文件」。

## 哈希口径（★勿混用）

| 字段 | 含义 | 用途 |
|---|---|---|
| `sha256_container` | 文件字节本身 | 同一性 / 防篡改（容器相同 ⟺ 文件完全相同） |
| `sha256_content` | gz **解压内容** | 跨运行**可比性**（同内容可能容器字节不同） |

> 超过 286 MB 的 gz 只登记容器哈希并显式标注（事件文件 ~1.7 GB/个，解压约 14.7 GB）。

## 门禁

| ID | 判据 | 结果 | 实测 |
|---|---|---|---|
| `M00` | 登记条目数 ≥ 40（防空表假门禁） | **PASS** | n=92 |
| `M01` | 全部登记文件存在 | **PASS** | missing=0 |
| `M02` | 7 个组均非空（覆盖用户点名的全部对象类） | **PASS** | A/B/C/D/E/F/G 各 ≥1 |
| `M03` | 无零字节文件 | **PASS** | zero=0 |
| `M04` | （负例）改 1 字节 ⇒ sha256 必变（登记有分辨力） | **PASS** | orig=2dbe942d2995f7ce… alt=d757f0fb24a00436… |
| `M05` | 锚点：SB-A5/EVT19 输入网络 sha256 == 运行前硬门登记值 | **PASS** | got=7978681b2a4ab54d1c148909… exp=7978681b2a4ab54d1c148909… |
| `M06` | 锚点：共用人口 sha256 == 运行前硬门登记值 | **PASS** | got=e96ed83ff59c0f5ecb50c9d9… exp=e96ed83ff59c0f5ecb50c9d9… |
| `M07` | 锚点：EVT19 it.19 linkstats 容器 + 内容 sha256 双双 == 冻结值 | **PASS** | ct=ddc879a07dfedb429367… content=fdc6ff5cd7e40000ad67… |
| `M08` | ★关系式 R1：EVT19 it.19 linkstats ≡ SB-A5 it.19（容器+内容）⇒ 开 events 未改动力学 | **PASS** | ct_eq=True content_eq=True |
| `M09` | ★关系式 R2：v1.0 侧 W01_events it.19 ≡ W01_rc_min it.19（容器+内容）⇒ 配对**双侧对称** | **PASS** | ct_eq=True content_eq=True |
| `M10` | ★关系式 R3：EVT19 vs SB-A5 配置差异 == 白名单 3 项 | **PASS** | diff=['outputDirectory', 'runId', 'writeEventsInterval'](3) |
| `M11` | ★关系式 R4：v1.0 侧 events 重跑 vs 冻结配置差异 == 白名单 3 项 | **PASS** | diff=['outputDirectory', 'runId', 'writeEventsInterval'](3) |
| `M12` | （负例）目标版本目录已存在 ⇒ next_free 取 `__v2` 且既有目录**内容未变**（只增不改） | **PASS** | got=S__v2 keep_intact=True |
| `M13` | 外部副本逐文件容器 sha256 == 源（源→副本 忠实性） | **PASS** | copied=92 mismatch=0 |
| `M14` | 外部副本未覆盖既有版本（本次版本目录在写入前不存在） | **PASS** | 既有=['2026-10-12'] 本次=2026-10-12__v2 |
| `M15` | 外部副本含零依赖独立核验器 | **PASS** | verifier=VERIFY_BASELINE_MANIFEST.py |

## 登记条目（按组）

### A 冻结声明 / 协议 / 判决书（可读证据链主干）

| 相对路径 | 字节 | sha256(容器) | sha256(内容) | 证据角色 |
|---|---|---|---|---|
| `reports/project_baseline/BASELINE_FREEZE_2026-10-12.md` | 16,391 | `52087bebf450b077…` | `—` | 基线冻结声明（含本清单保护节） |
| `experiments/E-SB-05_exec_level_events/PROTOCOL_E-SB-05.md` | 13,029 | `76549b88afac942c…` | `—` | E-SB-05 预注册协议（含原 D5 保留 FAIL 与协议真空披露） |
| `experiments/E-SB-05_exec_level_events/README.md` | 7,414 | `2ebb878914313642…` | `—` | E-SB-05 实验说明 |
| `reports/exec_level_events_E_SB_05/VERDICT_E-SB-05.md` | 15,165 | `226f797798002bbc…` | `—` | E-SB-05 判决书（并列双读法） |
| `reports/exec_level_events_E_SB_05/exec_level_scorecard.csv` | 349 | `f8084ee9bdcac051…` | `—` | E-SB-05 评分卡（门禁逐项） |
| `experiments/E-SB-06_signal_feasibility/PROTOCOL_E-SB-06.md` | 5,782 | `50007bd6d30dba46…` | `—` | E-SB-06 可行性审查协议 |
| `experiments/E-SB-06_signal_feasibility/README.md` | 3,286 | `02ed6fb916ff8d39…` | `—` | E-SB-06 实验说明 |
| `reports/esb06_signal_feasibility/FEASIBILITY_E-SB-06.md` | 8,274 | `72a3714ae50b377f…` | `—` | E-SB-06 可行性审查报告 |

### B 复核与判定脚本（可复算入口）

| 相对路径 | 字节 | sha256(容器) | sha256(内容) | 证据角色 |
|---|---|---|---|---|
| `scripts/experiments/esb05_independent_recheck.py` | 18,204 | `32dc6dd01f755f24…` | `—` | ★独立复核脚本（37/37，绕过自产 summary 直算原始层） |
| `scripts/experiments/esb05_exec_compare.py` | 20,139 | `66a34b76a8f22ca7…` | `—` | E-SB-05 判决合成（D5 已恢复原始预注册判据） |
| `scripts/experiments/esb05_verdict_render.py` | 19,356 | `47d5c47733e0f173…` | `—` | E-SB-05 判决书渲染（全动态） |
| `scripts/experiments/esb05_events_exec_route.py` | 16,224 | `69cb18b791c7a60f…` | `—` | 执行路线重建（events → 逐人链路序列） |
| `scripts/experiments/esb05_consistency_check.py` | 18,971 | `0adcdcefd2d15f3b…` | `—` | 运行一致性检查（A/B/C 判定） |
| `scripts/experiments/esb05_preflight.py` | 13,966 | `4504f1ff154768b1…` | `—` | 运行前硬门 G00–G13（含负例门禁） |
| `scripts/experiments/esb05_build_config.py` | 4,923 | `8e71891b8f7fd15d…` | `—` | 配置派生（白名单 3 项 + 逐字节回填断言） |
| `scripts/experiments/esb05_run.py` | 3,017 | `9cb379f4380dc61b…` | `—` | 仿真驱动（heap 24g） |
| `scripts/experiments/esb05_d5_timeline_audit.py` | 7,799 | `e4f7bc3c23ee7501…` | `—` | D5 修订时间线核实（含观察者破坏性） |
| `scripts/experiments/esb06_signal_feasibility_probe.py` | 22,293 | `0f9ac29474adb77c…` | `—` | 信号可行性探针（零仿真静态审计） |
| `scripts/experiments/baseline_manifest.py` | 39,289 | `a5615b5408839745…` | `—` | ★本清单生成器（自登记：日后被改动可检出） |
| `scripts/matsim/matsim_env.py` | 5,213 | `a0973fbc075160b1…` | `—` | MATSim 运行环境封装（两侧共用） |

### C 原始门禁 / 逐文件哈希 / 独立复核原始结果

| 相对路径 | 字节 | sha256(容器) | sha256(内容) | 证据角色 |
|---|---|---|---|---|
| `experiments/E-SB-05_exec_level_events/audit/esb05_preflight.csv` | 1,963 | `fd2aae06588a0774…` | `—` | 运行前 16 项硬门明细（实测值） |
| `experiments/E-SB-05_exec_level_events/audit/input_manifest.json` | 1,625 | `4caa69cc3204ba62…` | `—` | 输入哈希登记（网络/人口） |
| `experiments/E-SB-05_exec_level_events/audit/run_config_manifest.json` | 6,930 | `24c9971feb73021b…` | `—` | 配置清单（白名单 diff 与逐字节回填） |
| `experiments/E-SB-05_exec_level_events/audit/SB-A5_EVT19_CHECK_run_stamp.json` | 294 | `824a1eba1e5d0964…` | `—` | 运行时刻 / 耗时 / heap |
| `experiments/E-SB-05_exec_level_events/audit/esb05_consistency_gates.csv` | 1,478 | `53ac676397d8f59f…` | `—` | 运行一致性门禁 A/B/C 明细 |
| `experiments/E-SB-05_exec_level_events/audit/esb05_consistency_files.csv` | 6,390 | `4317e2eb970f0c9e…` | `—` | ★79/79 逐文件双侧哈希（确定性产物） |
| `experiments/E-SB-05_exec_level_events/audit/esb05_consistency_summary.json` | 3,818 | `27d505f956313ea6…` | `—` | 运行一致性判决 CONSISTENT_STRICT |
| `experiments/E-SB-05_exec_level_events/audit/esb05_events_integrity.json` | 2,612 | `62d5cf4e88c26181…` | `—` | events 完整性（10 类 / 236,044） |
| `experiments/E-SB-05_exec_level_events/audit/esb05_exec_route_gates.csv` | 2,395 | `2dbe942d2995f7ce…` | `—` | ★执行级门禁 16/17（含原 D5 FAIL） |
| `experiments/E-SB-05_exec_level_events/audit/esb05_exec_route_compare.csv` | 1,876 | `9d789899c550eb54…` | `—` | 执行路线逐人配对（改变率 66.060270%） |
| `experiments/E-SB-05_exec_level_events/audit/esb05_exec_corridor_use.csv` | 1,315 | `d1e2d9c819dd1fb9…` | `—` | 走廊里程份额 / 使用率 Δ（PIE/TPE 等） |
| `experiments/E-SB-05_exec_level_events/audit/esb05_exec_route_summary.json` | 6,184 | `b3390448581c0010…` | `—` | 执行级配对汇总 + 双读法判定 + 协议真空标记 |
| `experiments/E-SB-05_exec_level_events/audit/esb05_independent_recheck.json` | 8,669 | `fbe162217cceb2d1…` | `—` | ★独立复核原始结果（37/37，0 MISMATCH） |
| `experiments/E-SB-05_exec_level_events/audit/esb05_d5_timeline_audit.json` | 3,094 | `e5c523ca8d330bb4…` | `—` | ★D5 修订时间线核实（证据通道穷尽） |
| `experiments/E-SB-05_exec_level_events/audit/SB-A5_EVT19_CHECK_allhours_conv.linkstats.txt.gz` | 4,998,543 | `dde1dddfce208d00…` | `8aa242c4f2893a8d…` | 全时段 cycle-mean linkstats（08-09 口径复核用） |
| `experiments/E-SB-06_signal_feasibility/audit/esb06_probe.json` | 9,825 | `ebe47d109c813034…` | `—` | E-SB-06 探针原始结果（网络/配置/jar/LTA 数据） |
| `experiments/E-SB-06_signal_feasibility/audit/esb06_feasibility_gates.csv` | 2,414 | `b7b676232f8ef462…` | `—` | E-SB-06 可行性门禁明细（有效 5/14） |
| `experiments/E-SB-05_exec_level_events/audit/_revision_history/v1_17of17/esb05_exec_corridor_use.csv` | 1,315 | `d1e2d9c819dd1fb9…` | `—` | 版本留痕：已撤回的「17/17」版产物（只增不改） |
| `experiments/E-SB-05_exec_level_events/audit/_revision_history/v1_17of17/esb05_exec_route_compare.csv` | 1,876 | `9d789899c550eb54…` | `—` | 版本留痕：已撤回的「17/17」版产物（只增不改） |
| `experiments/E-SB-05_exec_level_events/audit/_revision_history/v1_17of17/esb05_exec_route_gates.csv` | 2,206 | `d8166ec0166f6bc6…` | `—` | 版本留痕：已撤回的「17/17」版产物（只增不改） |
| `experiments/E-SB-05_exec_level_events/audit/_revision_history/v1_17of17/esb05_exec_route_summary.json` | 5,191 | `cb77668018c61845…` | `—` | 版本留痕：已撤回的「17/17」版产物（只增不改） |
| `experiments/E-SB-05_exec_level_events/audit/_revision_history/v1_17of17/exec_level_scorecard.csv` | 348 | `8088c2d3df61a834…` | `—` | 版本留痕：已撤回的「17/17」版产物（只增不改） |
| `experiments/E-SB-05_exec_level_events/audit/_revision_history/v1_17of17/VERDICT_E-SB-05.md` | 12,576 | `33171be5e4a2c8b1…` | `—` | 版本留痕：已撤回的「17/17」版产物（只增不改） |

### D 逐人配对缓存（执行级重建产物）

| 相对路径 | 字节 | sha256(容器) | sha256(内容) | 证据角色 |
|---|---|---|---|---|
| `experiments/E-SB-05_exec_level_events/audit/_exec_cache/exec_V10.pkl` | 97,165,103 | `f80fa852f358c58e…` | `—` | ★v1.0 逐人执行路线（236,039 人） |
| `experiments/E-SB-05_exec_level_events/audit/_exec_cache/exec_V10.meta.json` | 1,087 | `00086e076c9e0fda…` | `—` | v1.0 执行路线扫描元数据（单侧 events 来源） |
| `experiments/E-SB-05_exec_level_events/audit/_exec_cache/exec_NEW.pkl` | 97,165,282 | `36f7ce6986897efd…` | `—` | ★EVT19 逐人执行路线（236,039 人） |
| `experiments/E-SB-05_exec_level_events/audit/_exec_cache/exec_NEW.meta.json` | 1,182 | `830422092788aad7…` | `—` | EVT19 执行路线扫描元数据 |

### E 配置与输入（三侧：v1.0 / SB-A5 / EVT19）

| 相对路径 | 字节 | sha256(容器) | sha256(内容) | 证据角色 |
|---|---|---|---|---|
| `experiments/E-SB-05_exec_level_events/configs/config_SB-A5_EVT19_CHECK.xml` | 22,152 | `43d45072a6985027…` | `—` | EVT19 配置（与 SB-A5 仅差白名单 3 项） |
| `experiments/E-SB-02_night_freeflow/configs/config_SB-A5.xml` | 22,124 | `d560bd89c27068c1…` | `—` | SB-A5 配置（原方案） |
| `matsim_final_7_6h/configs/config_W01_rc_min.xml` | 22,098 | `8f44fb349bff9cf1…` | `—` | v1.0 冻结配置（W01 工作点） |
| `matsim_viz_7_8/configs/config_W01_events.xml` | 22,096 | `38e9d402b108be48…` | `—` | v1.0 侧 events 重跑配置（配对**双侧对称**的证据） |
| `experiments/E-SB-02_night_freeflow/networks/network_SB-A5.xml.gz` | 14,061,792 | `7978681b2a4ab54d…` | `7a2a81f925c5c560…` | 关键网络：SB-A5 / EVT19 输入 |
| `reports/matsim_network/network_cleaned.xml.gz` | 13,816,419 | `f55795995b87d330…` | `40cdffc340fee130…` | 关键网络：v1.0 输入 |
| `matsim_final_7_6h/populations/pop_W01/population_lambda_0p075.xml.gz` | 8,930,574 | `e96ed83ff59c0f5e…` | `01d50a6432f78ebb…` | 共用人口（三侧同源，236,044 人） |
| `matsim_final_7_6h/final_workingpoint_7_6h_frozen_parameters.csv` | 1,308 | `82e86a6e7194c381…` | `—` | 7.6H 冻结参数表 |
| `matsim_final_7_6h/final_workingpoint_7_6h_config_validation.json` | 1,731 | `0293ba05b66dfda7…` | `—` | 7.6H 配置校验 |
| `matsim_final_7_6h/final_workingpoint_7_6h_config_provenance.csv` | 505 | `7149b95f24db79ae…` | `—` | 7.6H 配置来源链 |
| `matsim_final_7_6h/final_workingpoint_7_6h_source_invariance.csv` | 247 | `e3f9a13b9d876e3e…` | `—` | 7.6H 来源不变性 |
| `matsim_final_7_6h/final_workingpoint_7_6h_matrix.csv` | 561 | `e7d8e0edc5585bf3…` | `—` | 7.6H 工作点矩阵 |

### F 运行产物与锚点（events / linkstats / 日志）

| 相对路径 | 字节 | sha256(容器) | sha256(内容) | 证据角色 |
|---|---|---|---|---|
| `experiments/E-SB-05_exec_level_events/outputs/SB-A5_EVT19_CHECK/ITERS/it.0/SB-A5_EVT19_CHECK.0.events.xml.gz` | 1,716,906,925 | `1a4f85fecc3ac2fc…` | `（>阈值，仅容器）` | EVT19 it.0 events（earlyIteration 语义产物） |
| `experiments/E-SB-05_exec_level_events/outputs/SB-A5_EVT19_CHECK/ITERS/it.19/SB-A5_EVT19_CHECK.19.events.xml.gz` | 1,679,363,373 | `52cbaf8ab78198b4…` | `（>阈值，仅容器）` | ★EVT19 it.19 events（执行级重建的原始输入） |
| `experiments/E-SB-05_exec_level_events/outputs/SB-A5_EVT19_CHECK/SB-A5_EVT19_CHECK.output_events.xml.gz` | 1,679,363,373 | `52cbaf8ab78198b4…` | `（>阈值，仅容器）` | EVT19 收尾事件副本（DumpDataAtEnd 同源） |
| `experiments/E-SB-05_exec_level_events/outputs/SB-A5_EVT19_CHECK/SB-A5_EVT19_CHECK.output_plans.xml.gz` | 222,868,451 | `3d89ee66324a6c93…` | `fc6050cef209399b…` | EVT19 输出计划（路线对账的另一侧） |
| `experiments/E-SB-05_exec_level_events/outputs/SB-A5_EVT19_CHECK/SB-A5_EVT19_CHECK.output_network.xml.gz` | 14,225,463 | `7384c3ff06591b5f…` | `2106d34a0ae8bbe9…` | EVT19 运行期网络（证明网络未被改动） |
| `experiments/E-SB-05_exec_level_events/outputs/SB-A5_EVT19_CHECK/ITERS/it.19/SB-A5_EVT19_CHECK.19.linkstats.txt.gz` | 23,055,353 | `ddc879a07dfedb42…` | `fdc6ff5cd7e40000…` | ★锚点：EVT19 it.19 linkstats（容器+内容双双逐位同） |
| `experiments/E-SB-05_exec_level_events/outputs/SB-A5_EVT19_CHECK/ITERS/it.19/SB-A5_EVT19_CHECK.19.legHistogram.txt` | 12,144 | `1d95561988149804…` | `—` | 确定性产物（79/79 成员） |
| `experiments/E-SB-05_exec_level_events/outputs/SB-A5_EVT19_CHECK/ITERS/it.19/SB-A5_EVT19_CHECK.19.legdurations.txt` | 198 | `9b6e2adc17daba79…` | `—` | 确定性产物（79/79 成员） |
| `experiments/E-SB-05_exec_level_events/outputs/SB-A5_EVT19_CHECK/SB-A5_EVT19_CHECK.scorestats.csv` | 1,595 | `866321615eb1e42c…` | `—` | 评分轨迹（逐迭代） |
| `experiments/E-SB-05_exec_level_events/outputs/SB-A5_EVT19_CHECK/SB-A5_EVT19_CHECK.stopwatch.csv` | 5,439 | `6b46f95aa06a4e25…` | `—` | 阶段耗时 |
| `experiments/E-SB-05_exec_level_events/outputs/SB-A5_EVT19_CHECK/SB-A5_EVT19_CHECK.logfileWarningsErrors.log` | 8,202 | `e54ad8f49f018469…` | `—` | 收尾 5 类可选 dump ERROR（与 SB-A5 逐项相同） |
| `experiments/E-SB-02_night_freeflow/outputs/SB-A5/SB-A5.logfileWarningsErrors.log` | 8,148 | `e514205817a82f79…` | `—` | SB-A5 侧同项日志（对照） |
| `experiments/E-SB-02_night_freeflow/outputs/SB-A5/ITERS/it.19/SB-A5.19.linkstats.txt.gz` | 23,055,353 | `ddc879a07dfedb42…` | `fdc6ff5cd7e40000…` | ★参照锚点：SB-A5 it.19 linkstats |
| `experiments/E-SB-02_night_freeflow/outputs/SB-A5/ITERS/it.19/SB-A5.19.legHistogram.txt` | 12,144 | `1d95561988149804…` | `—` | 参照：SB-A5 确定性产物 |
| `experiments/E-SB-02_night_freeflow/outputs/SB-A5/ITERS/it.19/SB-A5.19.legdurations.txt` | 198 | `9b6e2adc17daba79…` | `—` | 参照：SB-A5 确定性产物 |
| `matsim_final_7_6h/outputs/W01_rc_min/ITERS/it.19/W01_rc_min.19.linkstats.txt.gz` | 22,629,291 | `b842b93a92f41c81…` | `de9424731106221b…` | ★锚点：v1.0 冻结模型 it.19 linkstats |
| `matsim_viz_7_8/outputs/W01_events/ITERS/it.19/W01_events.19.linkstats.txt.gz` | 22,629,291 | `b842b93a92f41c81…` | `de9424731106221b…` | ★锚点：v1.0 侧 events 重跑 it.19 linkstats（≡ 冻结模型） |
| `matsim_viz_7_8/outputs/W01_events/W01_events.output_events.xml.gz` | 1,694,011,331 | `c9b61fba06d8a9b0…` | `（>阈值，仅容器）` | ★v1.0 执行级重建的原始输入（exec_V10 来源） |
| `matsim_viz_7_8/outputs/W01_events/W01_events.output_plans.xml.gz` | 215,827,261 | `2aee1ba25a8416c9…` | `17799e2c1dddac91…` | v1.0 输出计划（对账另一侧） |
| `experiments/E-SB-05_exec_level_events/logs/SB-A5_EVT19_CHECK_run.log` | 411,707 | `d46fca943df2687d…` | `—` | EVT19 运行日志（rc=0 / 125.7 min） |
| `experiments/E-SB-05_exec_level_events/logs/esb05_scan_NEW.log` | 4,371 | `89262b6588bef4aa…` | `—` | EVT19 执行路线扫描日志 |
| `experiments/E-SB-05_exec_level_events/logs/esb05_compare_v2.log` | 3,974 | `6089907b9ab712be…` | `—` | ★恢复原始 D5 后的判决合成日志（现行版本） |
| `experiments/E-SB-05_exec_level_events/logs/esb05_compare.log` | 3,610 | `30d3742a3882acb6…` | `—` | 首轮（已撤回）判决合成日志（留痕） |

### G 上游计划级参照（E-SB-04 / 04B）

| 相对路径 | 字节 | sha256(容器) | sha256(内容) | 证据角色 |
|---|---|---|---|---|
| `experiments/E-SB-04_path_redistribution_audit/_cache/routes_v1.0.pkl` | 1,157,302,794 | `c1e795f35c156ad8…` | `—` | v1.0 逐人计划路线（计划级） |
| `experiments/E-SB-04_path_redistribution_audit/_cache/routes_SB-A5.pkl` | 1,150,074,176 | `52bd2ef6b44af871…` | `—` | SB-A5 逐人计划路线（计划级） |
| `experiments/E-SB-04_path_redistribution_audit/_cache/cls_v1.0.pkl` | 80,646,450 | `15961a633a4fd984…` | `—` | v1.0 逐人等级里程分类 |
| `experiments/E-SB-04_path_redistribution_audit/_cache/cls_SB-A5.pkl` | 80,646,450 | `06328f5f6292acd8…` | `—` | SB-A5 逐人等级里程分类 |
| `experiments/E-SB-04_path_redistribution_audit/_cache/fidelity.json` | 332 | `142ec6d0c37cef54…` | `—` | plans↔events 保真抽样（8,000/8,000） |
| `experiments/E-SB-04_path_redistribution_audit/_cache/info_v1.0.json` | 67 | `83557e985d9a714c…` | `—` | v1.0 计划结构信息 |
| `experiments/E-SB-04_path_redistribution_audit/_cache/info_SB-A5.json` | 67 | `11c3c0c07b02e89e…` | `—` | SB-A5 计划结构信息 |
| `reports/path_redistribution_audit_E_SB_04/route_change_summary.csv` | 628 | `a28f2bba277af485…` | `—` | 计划级改变率 66.058870% |
| `reports/path_redistribution_audit_E_SB_04/roadclass_route_share_pivot.csv` | 1,196 | `9fc1a0ef9f78809a…` | `—` | 计划级等级份额（+3.5742 pp） |
| `reports/path_redistribution_audit_E_SB_04/VERDICT_E-SB-04.md` | 14,806 | `c3c4e69167fdde4e…` | `—` | E-SB-04 判决书（计划级） |

## 显式排除（避免「清单像全量」的错觉）

| 对象 | 理由 |
|---|---|
| `experiments/E-SB-02_night_freeflow/outputs/SB-A5ind/**` | SB-A5ind 全链（population 异于 SB-A5 ⇒ 不可与 SB-A5 路线差配对；不支撑冻结结论） |
| `experiments/E-SB-04_path_redistribution_audit/_cache/routes_SB-A5ind.pkl 等 SB-A5ind 缓存` | 同上（仅参照，未被任何冻结结论引用） |
| `tools/matsim-2026.0/matsim-2026.0.jar 与 libs/**.jar` | 发行版二进制（可重新获取；E-SB-06 已记录版本与类清单结论） |
| `experiments/E-SB-05_exec_level_events/outputs/SB-A5_EVT19_CHECK/ITERS/it.1–it.18` | 中间迭代产物（结论仅依赖 it.0 / it.19 与确定性产物哈希表） |

## 外部副本（项目工作目录之外，只增不改）

| 项 | 值 |
|---|---|
| 版本目录 | `K:\_sg_matsim_baseline_freeze\2026-10-12__v2` |
| 文件数 / 体积 | 92 / 9.33 GiB |
| 源→副本 哈希不一致 | **0** |
| 本次之前已存在的版本（未被覆盖） | ['2026-10-12'] |
| 清单副本 / 校验和边车 | `manifest/` + `manifest/SHA256SUMS.txt` |
| 独立核验器 | `VERIFY_BASELINE_MANIFEST.py`（零依赖） |

核验命令：

```bash
python "K:\_sg_matsim_baseline_freeze\2026-10-12__v2\VERIFY_BASELINE_MANIFEST.py"            # 核验外部副本
python "K:\_sg_matsim_baseline_freeze\2026-10-12__v2\VERIFY_BASELINE_MANIFEST.py" --root "D:\Luan\2026-05\2_Singapore"  # 核验项目内原件
```

## 只增不改规则

- 项目内清单：目标文件已存在 ⇒ 自动落为 `…__v2/__v3/…`，⛔ 不覆盖。

- 外部副本：`K:\_sg_matsim_baseline_freeze/<戳记>` 已存在 ⇒ 自动落为 `<戳记>__v2/…`，⛔ 不覆盖。

- 任何后续变更**新增版本**；已冻结副本**原样保留**，作为「当时那一批文件」的锚。
