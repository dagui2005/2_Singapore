# Step 7.4.2 Phase 2 — λ 灵敏度实验设计（capacity 固定 1.00）

**本文件为 Phase 2 的单一事实源**（由 `prepare_calibration_phase2_7_4_2.py` 生成）。**从不启动 MATSim。**

## 1. 固定项

- `capacity_factor` = 1.0
- `storage_capacity_factor` = 1.0
- `last_iteration` = 19
- `iterations` = 20
- `routing_algorithm` = SpeedyALT
- `random_seed` = 4711
- `population_agents` = 200000
- `car_trip_expansion` = 2.29897
- `crosswalk` = 7.3.6A Final Calibration Crosswalk
- `departure_profile` = 6.3.3A
- `network` = network_cleaned.xml.gz

## 2. λ 扫描矩阵

| 规范 ID | 用户标签 | λ | capacity | 迭代 | population | 状态 |
|---|---|---:|---:|---:|---|---|
| **E10** | E04 | 0.025 | 1.00 | 20 | ❌ 缺失 | DEFERRED_BY_USER_DECISION |
| **E03** | E05 | 0.050 | 1.00 | 20 | ✅ | REUSE_PHASE1_E03 |
| **E06** | E06 | 0.075 | 1.00 | 20 | ✅ | RUN |
| **E09** | E07 | 0.100 | 1.00 | 20 | ✅ | RUN |

## 3. ⚠️ 编号映射（与 7.4.1 冻结矩阵对齐）

用户口述的 E04/E05/E06/E07 与 **7.4.1 冻结矩阵** 编号不一致，本阶段采用**规范 ID**：

- λ=0.025 → **E10（新增，用户决定先跳过）**；7.4.1 矩阵无此 λ。
- λ=0.050 → **E03**（7.4.1 矩阵既有；**Phase 1 已完成，直接复用**）。
- λ=0.075 → **E06**（7.4.1 矩阵既有，恰好一致）。
- λ=0.100 → **E09**（7.4.1 矩阵既有；矩阵 E07 = λ0.100/**f0.50** 属 f<1.00，已退役）。
- 7.4.1 矩阵所有 **f<1.00** 的行（E01/E02/E04/E05/E07/E08）在 Phase 1 后**退役**。

## 4. λ=0.025：现状 + 用户决策

`reports/matsim_departure_6_3_3a/` 仅存在 λ ∈ {0.050, 0.075, 0.100} 的 population。运行 λ=0.025 前需补齐上游冻结链（**新增 λ，不改既有产物**）：

1. `build_prior_od.py --lambdas 0.025`
1. `build_prior_od_5b.py --lambdas 0.025`
1. `build_prior_od_5c1.py --lambdas 0.025`
1. `build_matsim_population_6_2b.py --lambdas 0.025`
1. `prepare_connected_scenario.py (connected population)`
1. `build_departure_profile_6_3_3a.py --lambdas 0.025`

**★用户决策（2026-09-14）：先跳过 λ=0.025。** 用户决定**先跳过 λ=0.025**，用现有三点 λ∈{0.050,0.075,0.100}（E03/E06/E09）的正式趋势判断 λ 的辨识力；若三点趋势显示确需拓展低端，再补齐上游冻结链新增 λ=0.025（E10）。

## 5. 预注册判据

- **不自行选 λ**：由 E03/E06/E09 的正式趋势决定候选区间。
- 若 λ 只改变总流量、`CATA/SLIP` 与 WMAPE/GEH 不随之改善 → λ 非结构杠杆 → 转 OD 总量/departure profile。
- 若 λ 同时改善量级与结构 → 进入 **Phase 3 λ 精细搜索**。
