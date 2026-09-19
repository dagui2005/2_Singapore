# Step 7.4.1 — Joint Calibration Experiment Design

## Status
**PLANNED / DESIGN ONLY**

本步骤只固化实验矩阵，不启动 MATSim，不修改冻结输入。

## 1. 核心矩阵

λ ∈ {0.050, 0.075, 0.100}

flowCapacityFactor ∈ {0.50, 0.75, 1.00}

storageCapacityFactor 与 flowCapacityFactor 同步。

route choice 固定为 20 iterations（lastIteration=19）。

共 **9 组**核心实验。

## 2. 冻结输入

Final Calibration Crosswalk = 7.3.6A  
Departure Profile = 6.3.3A  
Network = network_cleaned.xml.gz  
OD / population = 6.2B  
randomSeed = 4711  ← 见下方一致性说明  
mode = car

> **randomSeed 一致性说明**：外部草案把 randomSeed 写成 `20260912`（疑似设计日期误写）。
> 项目**实测冻结值 = 4711**（`make_config_6_3.py` 硬编码，6.3.3B / capf_* / cf_it20 三份
> config 实测均为 4711）。为保持与 6.3.3B linkstats 及整条 7.x 评价链**可比**，本步骤
> 以 **4711** 为准。

## 3. 评价

窗口：07-08、08-09、AM。

指标：Pearson r、Spearman rho、MAE、RMSE、WMAPE、Bias、Sim/Obs、GEH<5、GEH<10。

重点道路类别：CATA、SLIP_ROAD、CATB、CATC、CATD、CATE。

结构指标：

    CATA Sim/Obs
    ----------------
    SLIP_ROAD Sim/Obs

## 4. 执行策略

第一阶段只运行 E01-E03（λ=0.050）。

只有第一阶段无法判别容量作用时，才继续 E04-E09。

不一次性启动完整九组，以避免在缺乏信息增益的情况下消耗大量 MATSim 计算资源。

## 5. 预注册判据

不能只因为总体 Sim/Obs 更接近 1 就认定模型更好。

候选方案需要同时改善总体误差，并保持或改善 CATA/SLIP 结构。

λ 只有在不同 capacity factor 下表现持续占优、且多个时间窗一致时才可以冻结。

## 6. 当前状态

parameters_changed = false  
lambda_selected = false  
matsim_runs_started = false
