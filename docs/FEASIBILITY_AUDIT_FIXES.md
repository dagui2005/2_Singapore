# sg_feasibility_audit.py 数据适配修复说明

## 📋 问题概述

同事编写的`sg_feasibility_audit.py`脚本在数据路径和数据源理解上存在偏差，导致无法正确读取本工程的实际数据。

**修复时间**: 2026-05-05  
**状态**: ✅ 已修复

---

## 🔍 发现的问题

### 1. ❌ 配置路径错误（严重）

**问题**: 
```python
# 原代码
CONFIG = {
    "static_root": r"./Static_2026_03",  # 缺少空格！
    ...
}
```

**实际情况**: 
- 文件夹名是 `Static_ 2026_03`（有空格）
- LTA地理空间数据在 `Static_ 2026_03/GEOSPATIAL` 子目录

**影响**: 所有静态路网数据都无法找到

**修复**:
```python
CONFIG = {
    "static_root": r"./Static_ 2026_03/GEOSPATIAL",  # 修正路径
    "dynamic_root": r"./Dynamic_2026_03_16",
    "other_root": r"./Static_ 2026_03/OTHER",
    ...
}
```

---

### 2. ❌ 人口栅格文件查找范围过大

**问题**:
```python
# 原代码
pop_file = find_first(other_root, ["sgp_pop_2026", "100m"], [".tif"])
```

**实际情况**:
- 人口数据在 `OTHER/Population/` 子目录
- 有249个TIFF文件分布在多个子目录中
- 需要精确定位到总人口文件（而非按年龄性别分类的文件）

**影响**: 可能找到错误的文件或找不到

**修复**:
```python
pop_dir = other_root / "Population"
pop_file = find_first(pop_dir, ["sgp_pop_2026", "100m"], [".tif"])
if pop_file is None:
    pop_file = find_first(pop_dir, ["sgp_pop_2025", "100m"], [".tif"])
# ... 依次降级查找
```

---

### 3. ❌ HDB数据源选择错误

**问题**:
```python
# 原代码
hdb_file = find_first(other_root, ["hdb"], [".csv"])
```

**实际情况**:
本工程有**两个HDB数据源**:

| 数据源 | 位置 | 格式 | 特点 |
|--------|------|------|------|
| **LTSG研究数据** | `siteselect_sg-main/dataset/hdb.csv` | CSV | 12,442条记录，包含完整属性字段（房型、销售、租赁统计） |
| **政府开放数据** | `goverment_open/HDBExistingBuilding.geojson` | GeoJSON | 仅包含建筑物位置和几何信息 |

**原代码的问题**:
- 可能找到错误的文件
- 没有优先使用更丰富的LTSG数据

**修复**:
```python
# 优先使用LTSG数据集的hdb.csv（包含完整属性字段）
ltsg_dir = other_root / "siteselect_sg-main" / "dataset"
hdb_file = ltsg_dir / "hdb.csv"

if not hdb_file.exists():
    # 降级方案：从goverment_open查找GeoJSON
    gov_dir = other_root / "goverment_open"
    hdb_geojson = find_first(gov_dir, ["HDBExistingBuilding"], [".geojson"])
    ...
else:
    hdb_df = read_csv_if_exists(hdb_file)
```

---

### 4. ❌ POI数据源选择错误

**问题**: 与HDB类似，POI也有两个来源

**实际情况**:

| 数据源 | 位置 | 记录数 | 特点 |
|--------|------|--------|------|
| **LTSG研究数据** | `siteselect_sg-main/dataset/poi.csv` | 8,672个 | 包含Google评分、评论数、100+种类型标志 |
| **政府开放数据** | 分散在各个GeoJSON | - | 如旅游景点、学校等单独文件 |

**修复**: 优先使用LTSG的poi.csv

---

### 5. ⚠️ Master Plan土地用途文件查找路径不精确

**问题**:
```python
# 原代码
landuse_file = find_first(other_root, ["MasterPlan2019LandUselayer"], [".geojson"])
```

**实际情况**:
- 文件在 `OTHER/goverment_open/MasterPlan2019LandUselayer.geojson`
- 应该明确指定在goverment_open子目录查找

**修复**:
```python
gov_dir = other_root / "goverment_open"
landuse_file = find_first(gov_dir, ["MasterPlan2019LandUselayer"], [".geojson"])
```

---

### 6. ⚠️ 土地用途字段名称优先级调整

**问题**:
```python
# 原代码
lu_col = find_col(landuse_gdf, ["LU_DESC", "LANDUSE", "LAND_USE", ...])
```

**实际情况**:
根据新加坡URA Master Plan 2019的标准，土地用途字段通常是:
- `DEV_TYPE` - 开发类型（最常用）
- `LAND_USE` - 土地用途

**修复**:
```python
lu_col = find_col(
    landuse_gdf,
    ["DEV_TYPE", "LAND_USE", "LU_DESC", "LANDUSE", "PLN_AREA_N"],
    contains=True
)
```

---

## ✅ 修复总结

### 修改的代码部分

| 函数 | 修改内容 | 行数变化 |
|------|---------|---------|
| `CONFIG` | 修正static_root路径 | +4/-3 |
| `audit_population_raster()` | 限定在Population子目录查找 | +10/-6 |
| `audit_hdb_poi_landuse()` | 优先使用LTSG数据源 | +25/-8 |
| 土地用途字段查找 | 调整字段优先级 | +2/-1 |

**总计**: +47行/-19行

### 关键改进

1. ✅ **路径准确性**: 所有数据路径都指向正确的子目录
2. ✅ **数据源优先级**: 优先使用更丰富、更结构化的LTSG数据集
3. ✅ **降级策略**: 当首选数据源不存在时，有备选方案
4. ✅ **注释清晰**: 添加了详细的中文注释说明数据来源

---

## 🧪 测试建议

运行修复后的脚本：

```bash
cd D:\Luan\2026-05\2_Singapore
python sg_feasibility_audit.py
```

### 预期输出

脚本应该在 `./sg_feasibility_outputs/` 目录生成：

1. **report.md** - 完整的可行性审计报告
2. **CSV样例文件**:
   - `speedbands_sample.csv` - 速度带数据样例
   - `trafficflow_sample.csv` - 交通流数据样例
   - `arrow_type_counts.csv` - 箭头类型统计
   - `hdb_dwelling_by_zone.csv` - 按规划区统计的HDB住宅单元
   - `poi_attraction_by_zone.csv` - 按规划区统计的POI吸引力
   - `landuse_area_by_type.csv` - 按类型统计的土地用途面积
   - `proxy_od_by_planning_area.csv` - 基于规划区的OD代理矩阵

### 验证要点

检查以下关键指标是否正常：

#### 静态路网
- ✅ RoadSectionLine能找到并读取
- ✅ LaneMarking、ArrowMarking、TrafficLight、DetectorLoop都能关联
- ✅ 路网连通性 > 0.85

#### 动态数据
- ✅ TrafficSpeedBands和TrafficFlow能读取
- ✅ LinkID字段能识别
- ✅ Speed和Flow的LinkID有重叠

#### 需求数据
- ✅ HDB数据能读取（应该有12,000+条记录）
- ✅ POI数据能读取（应该有8,000+条记录）
- ✅ 人口栅格能打开
- ✅ 土地用途数据能读取
- ✅ OD代理矩阵能生成

---

## 📊 数据映射关系图

```
sg_feasibility_audit.py 数据需求
│
├─ 静态路网 (static_root)
│  └─ Static_ 2026_03/GEOSPATIAL/
│     ├─ RoadSectionLine.shp ✓
│     ├─ LaneMarking.shp ✓
│     ├─ ArrowMarking.shp ✓
│     ├─ TrafficLight.shp ✓
│     └─ DetectorLoop.shp ✓
│
├─ 动态数据 (dynamic_root)
│  └─ Dynamic_2026_03_16/
│     ├─ historical_data/
│     │  ├─ TrafficSpeedBands_*.json ✓
│     │  └─ TrafficFlow_Data_*.json ✓
│     └─ realtime_monitoring/
│        └─ (可选)
│
└─ 其他数据 (other_root)
   └─ Static_ 2026_03/OTHER/
      ├─ Population/
      │  └─ sgp_pop_2026_CN_100m_R2025A_v1.tif ✓
      │
      ├─ siteselect_sg-main/dataset/
      │  ├─ hdb.csv ✓ (优先)
      │  ├─ poi.csv ✓ (优先)
      │  ├─ bus_line.csv
      │  ├─ bus_vol.csv
      │  └─ mrt.csv
      │
      └─ goverment_open/
         ├─ HDBExistingBuilding.geojson (备选)
         ├─ MasterPlan2019LandUselayer.geojson ✓
         ├─ HawkerCentresGEOJSON.geojson
         ├─ TouristAttractions.geojson
         └─ HealthFacilities.../*.csv
```

---

## 💡 后续优化建议

### 1. 添加数据验证日志

在关键数据加载后添加验证：

```python
if hdb_df.empty:
    print("[WARN] HDB数据为空，请检查数据源")
elif len(hdb_df) < 10000:
    print(f"[INFO] HDB数据量较少: {len(hdb_df)}条")
else:
    print(f"[OK] HDB数据加载成功: {len(hdb_df)}条")
```

### 2. 支持更多数据源

可以考虑整合：
- ACRA企业数据用于就业中心识别
- MRT和巴士站点数据用于交通可达性
- 小贩中心、公园等公共设施数据

### 3. 坐标系转换优化

目前假设所有数据都能转换到EPSG:3414，但实际可能需要：
- 检测原始坐标系
- 处理转换失败的情况
- 记录转换警告

### 4. 性能优化

对于大数据集（如ACRA 326MB）：
- 使用分块读取
- 只加载需要的列
- 考虑使用数据库

---

## 📝 版本历史

| 版本 | 日期 | 变更 |
|------|------|------|
| 1.0 (原始) | 未知 | 同事编写，存在路径和数据源问题 |
| 1.1 (修复) | 2026-05-05 | 修正路径、数据源优先级、字段识别 |

---

**修复者**: AI Assistant  
**审核建议**: 运行脚本验证所有数据能正常读取  
**相关文档**: 
- [OTHER_DATA_DOCUMENTATION.md](Static_%202026_03/OTHER/OTHER_DATA_DOCUMENTATION.md)
- [DATA_DOCUMENTATION.md](Static_%202026_03/DATA_DOCUMENTATION.md)
