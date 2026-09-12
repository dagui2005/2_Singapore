# Singapore_OD_MATSim_FinalData/

> **本仓库不包含此目录的实际数据文件**
> 仅保留目录结构与 `.gitkeep` 占位。完整数据集约 **9 GB**，请按 [`docs/DATASETS.md`](../../docs/DATASETS.md) 下载后解压到当前位置。

## 子目录

| 子目录 | 主题 | 估算大小 | 数据源 |
| --- | --- | --- | --- |
| `01_Boundary_TAZ/` | TAZ/Subzone/PlanningArea 边界 | ~10 MB | URA MasterPlan 2019 |
| `02_Population_Residence/` | 按 TAZ 居住人口分布 | ~200 MB | SingStat / Census 2020 |
| `03_Workplace_Employment/` | 按 TAZ 工作岗位 | ~150 MB | URA / Census 2020 |
| `04_LandUse_Building/` | 土地利用 + 建筑层 (MasterPlan 2019 Land Use + Building) | ~750 MB | URA |
| `05_POI_Enterprise/` | POI、企业注册 (ACRA 全字母表) | ~700 MB | ACRA / OneMap |
| `06_Census_TravelBehavior/` | 出行行为调查 | ~30 MB | SingStat Census 2020 |
| `07_RoadNetwork/` | 道路网络 + 路段 shapefile | ~3 GB | OneMap / LTA |
| `08_TrafficCount/` | 路段交通量观测 | ~50 MB | LTA |
| `09_Auxiliary/` | 公交站点、地铁站、POI 背景 | ~100 MB | LTA / MyTransport.sg |
| `10_Documentation/` | 数据字典与处理说明 | <1 MB | — |

## 同步方式

```bash
# 第一次：参考 docs/DATASETS.md 获取数据集链接
# 解压或下载到本目录位置，保持子目录名一致

# 后续若启用 DVC：
dvc pull Singapore_OD_MATSim_FinalData
```

## 用法

MATSim 网络生成、OD 矩阵构建脚本会从此目录读取：
- `scripts/matsim/network/reader.py`
- `scripts/od/build_od_matrix.py`

一旦目录按 [`docs/DATASETS.md`](../../docs/DATASETS.md) 重新创建，可直接运行。
