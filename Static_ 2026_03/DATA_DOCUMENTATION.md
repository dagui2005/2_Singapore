# 新加坡陆路交通静态数据说明文档

## 项目概述

本数据集包含新加坡陆路交通管理局（LTA）提供的静态地理空间数据和公共交通统计数据，数据采集时间为**2026年3月**。数据涵盖道路基础设施、交通设施位置、公共交通运营统计等多个维度，适用于交通规划、空间分析、网络建模等研究。

**数据来源**: 新加坡陆路交通管理局（Land Transport Authority, LTA）  
**数据版本**: March 2026  
**坐标系统**: SVY21 (Projected) / WGS84 (Geographic)  
**数据格式**: Shapefile (.shp), CSV  

---

## 目录结构

```
Static_ 2026_03/
├── GEOSPATIAL/                          # 地理空间数据（29个SHP图层）
│   ├── ArrowMarking_Mar2026/           # 箭头标记
│   ├── Bollard_Mar2026/                # 防撞柱
│   ├── BusStopLocation_Mar2026/        # 巴士站位置
│   ├── ControlBox_Mar2026/             # 控制箱
│   ├── ConvexMirror_Mar2026/           # 凸面镜
│   ├── CoveredLinkWay_Mar2026/         # 有盖连廊
│   ├── CyclingPath_Mar2026/            # 自行车道
│   ├── DetectorLoop_Mar2026/           # 检测线圈
│   ├── ERPGantry_Mar2026/              # ERP门架
│   ├── Footpath_Mar2026/               # 人行道
│   ├── GuardRail_Mar2026/              # 护栏
│   ├── KerbLine_Mar2026/               # 路缘线
│   ├── LampPost_Mar2026/               # 路灯杆
│   ├── LaneMarking_Mar2026/            # 车道标线
│   ├── ParkingStandardsZone_Mar2026/   # 停车标准区域
│   ├── PassengerPickupBay_Mar2026/     # 乘客上下客区
│   ├── PedestrainOverheadbridge_UnderPass_Mar2026/  # 人行天桥/地下通道
│   ├── Railing_Mar2026/                # 栏杆
│   ├── RetainingWall_Mar2026/          # 挡土墙
│   ├── RoadCrossing_Mar2026/           # 道路交叉口
│   ├── RoadHump_Mar2026/               # 减速带
│   ├── RoadSectionLine_Mar2026/        # 路段线
│   ├── SpeedRegulatingStrip_Mar2026/   # 调速带
│   ├── StreetPaint_Mar2026/            # 路面油漆标记
│   ├── TaxiStand_Mar2026/              # 出租车站
│   ├── TrafficLight_Mar2026/           # 交通信号灯
│   ├── TrainStation_Mar2026/           # 火车站
│   ├── VehicleBridge_FlyOver_Underpass_Mar2026/     # 车辆桥梁/立交桥/地下通道
│   └── WordMarking_Mar2026/            # 文字标记
│
└── PUBLIC TRANSPORT/                    # 公共交通统计数据
    ├── Monthly Taxi Population/        # 月度出租车车队数量
    │   └── monthly_taxi_fleet.csv
    ├── Number of MRT LRT Station/      # 地铁站/LRT站数量
    │   └── annual_rts_stations.csv
    ├── PremiumBusServices/             # 优质巴士服务
    │   └── PremiumBusServicesCSV20260121.csv
    ├── Rail Length/                    # 铁路长度
    │   └── yearly_rail_length.csv
    ├── monthly_ave_daily_pt_ridership.csv    # 月度平均日公共交通客流量
    └── yearly_ave_daily_pt_ridership.csv     # 年度平均日公共交通客流量
```

---

## 一、地理空间数据（GEOSPATIAL）

### 通用说明

- **坐标系统**: SVY21投影坐标系（EPSG:3414），基准面为WGS84
- **线性单位**: 米（Meter）
- **数据范围**: 
  - 经度: 103.61° - 104.03° E
  - 纬度: 1.22° - 1.50° N
- **文件格式**: ESRI Shapefile（包含.shp, .shx, .dbf, .prj等文件）
- **通用字段**: 所有图层均包含以下基础字段
  - `OBJECTID`: 要素唯一标识符（整数）
  - `SHAPE`: 几何图形（点/线/面）
  - `JOB_NUM`: 作业编号（字符串，20字符）
  - `RD_CD`: 道路代码（字符串，6字符）
  - `LAST_UPD_DTTM`: 最后更新日期（日期）
  - `CRT_DTTM`: 创建日期（日期）
  - `REMARKS`: 备注（字符串，200字符）

---

### 1. ArrowMarking_Mar2026 - 箭头标记

**几何类型**: 多边形（Polygon）  
**要素数量**: 约数千个箭头标记  
**描述**: 道路上的方向指示箭头，包括直行、左转、右转等标记

| 字段名 | 别名 | 类型 | 宽度 | 说明 |
|--------|------|------|------|------|
| OBJECTID | Object ID | OID | 4 | 唯一标识符 |
| SHAPE | Shape | Geometry | - | 多边形几何 |
| JOB_NUM | Job ID | String | 20 | 作业编号 |
| RD_CD | Road Code-Name | String | 6 | 道路代码 |
| ARROW_TYPE | Arrow Type | String | 20 | 箭头类型（直行/左转/右转等） |
| REMARKS | Remarks | String | 200 | 备注 |

**用途**: 交通流向分析、路口设计评估

---

### 2. Bollard_Mar2026 - 防撞柱

**几何类型**: 点（Point）  
**要素数量**: 约数千个防撞柱  
**描述**: 用于保护行人或限制车辆通行的立柱

| 字段名 | 别名 | 类型 | 宽度 | 说明 |
|--------|------|------|------|------|
| OBJECTID | Object ID | OID | 4 | 唯一标识符 |
| SHAPE | Shape | Geometry | - | 点几何 |
| JOB_NUM | Job ID | String | 20 | 作业编号 |
| RD_CD | Road Code-Name | String | 6 | 道路代码 |
| BOLLARD_TYPE | Bollard Type | String | 20 | 防撞柱类型 |
| REMARKS | Remarks | String | 200 | 备注 |

**用途**: 行人安全设施分析、交通管制点识别

---

### 3. BusStopLocation_Mar2026 - 巴士站位置

**几何类型**: 点（Point）  
**要素数量**: 5,166个巴士站  
**描述**: 全岛巴士站的精确位置及属性信息

| 字段名 | 别名 | 类型 | 宽度 | 说明 |
|--------|------|------|------|------|
| OBJECTID | Object ID | OID | 4 | 唯一标识符 |
| SHAPE | Shape | Geometry | - | 点几何 |
| JOB_NUM | Job ID | String | 20 | 作业编号 |
| BUS_STOP_NUM | Bus Stop No | String | 65 | 巴士站编号（如"01012"） |
| BUS_ROOF_NUM | Bus Roof No | String | 10 | 巴士亭编号 |
| STATUS | Status Of Bus Stop | String | 20 | 状态（Operational/Closed等） |
| SERVICE_TYPE | Bus Service Type | String | 20 | 服务类型 |
| LVL_NUM | Level of Road | SmallInteger | 2 | 道路层级 |
| RD_CD | Road Code-Name | String | 6 | 道路代码 |
| LOC_DESC | Location Description | String | 255 | 位置描述 |
| PKG_REF | Attachment Folder | String | 50 | 附件文件夹 |
| EXCEPTION_IND | Exception Indicator | String | 1 | 异常标识 |
| LAST_UPD_USRID_NUM | Last Update User ID | String | 8 | 最后更新用户ID |
| LAST_UPD_DTTM | Last Update Date | Date | 8 | 最后更新日期 |
| CRT_USRID_NUM | Create User ID | String | 8 | 创建用户ID |
| CRT_DTTM | Create Date | Date | 8 | 创建日期 |
| REMARKS | Remarks | String | 200 | 备注 |

**用途**: 公交网络分析、站点可达性研究、换乘优化

---

### 4. ControlBox_Mar2026 - 控制箱

**几何类型**: 点（Point）  
**描述**: 交通信号控制系统、监控设备等控制箱位置

| 字段名 | 类型 | 宽度 | 说明 |
|--------|------|------|------|
| OBJECTID | OID | 4 | 唯一标识符 |
| SHAPE | Geometry | - | 点几何 |
| JOB_NUM | String | 20 | 作业编号 |
| RD_CD | String | 6 | 道路代码 |
| CONTROL_TYPE | String | 20 | 控制箱类型 |
| REMARKS | String | 200 | 备注 |

**用途**: 交通基础设施管理、设备维护规划

---

### 5. ConvexMirror_Mar2026 - 凸面镜

**几何类型**: 点（Point）  
**描述**: 用于改善视线的交通凸面镜位置

| 字段名 | 类型 | 宽度 | 说明 |
|--------|------|------|------|
| OBJECTID | OID | 4 | 唯一标识符 |
| SHAPE | Geometry | - | 点几何 |
| JOB_NUM | String | 20 | 作业编号 |
| RD_CD | String | 6 | 道路代码 |
| MIRROR_SIZE | String | 20 | 镜面尺寸 |
| REMARKS | String | 200 | 备注 |

**用途**: 交通安全设施分析、视线盲区改善

---

### 6. CoveredLinkWay_Mar2026 - 有盖连廊

**几何类型**: 线（Polyline）  
**描述**: 连接建筑物或设施的有盖步行通道

| 字段名 | 类型 | 宽度 | 说明 |
|--------|------|------|------|
| OBJECTID | OID | 4 | 唯一标识符 |
| SHAPE | Geometry | - | 线几何 |
| JOB_NUM | String | 20 | 作业编号 |
| RD_CD | String | 6 | 道路代码 |
| WIDTH | Double | 8 | 宽度（米） |
| LENGTH | Double | 8 | 长度（米） |
| REMARKS | String | 200 | 备注 |

**用途**: 行人便利性分析、无障碍设施规划

---

### 7. CyclingPath_Mar2026 - 自行车道

**几何类型**: 线（Polyline）  
**描述**: 专用自行车道网络

| 字段名 | 类型 | 宽度 | 说明 |
|--------|------|------|------|
| OBJECTID | OID | 4 | 唯一标识符 |
| SHAPE | Geometry | - | 线几何 |
| JOB_NUM | String | 20 | 作业编号 |
| RD_CD | String | 6 | 道路代码 |
| PATH_TYPE | String | 20 | 车道类型（专用/共享） |
| WIDTH | Double | 8 | 宽度（米） |
| DIRECTION | String | 10 | 方向（单向/双向） |
| REMARKS | String | 200 | 备注 |

**用途**: 自行车网络规划、绿色出行分析

---

### 8. DetectorLoop_Mar2026 - 检测线圈

**几何类型**: 多边形（Polygon）  
**描述**: 埋设在路面下的车辆检测线圈，用于交通流量监测

| 字段名 | 类型 | 宽度 | 说明 |
|--------|------|------|------|
| OBJECTID | OID | 4 | 唯一标识符 |
| SHAPE | Geometry | - | 多边形几何 |
| JOB_NUM | String | 20 | 作业编号 |
| RD_CD | String | 6 | 道路代码 |
| LANE_NUM | Integer | 4 | 车道编号 |
| DETECTOR_ID | String | 20 | 检测器ID |
| REMARKS | String | 200 | 备注 |

**用途**: 交通流量监测、智能交通系统

---

### 9. ERPGantry_Mar2026 - ERP门架

**几何类型**: 线（Polyline）  
**要素数量**: 883个ERP门架  
**描述**: 电子道路收费（Electronic Road Pricing）门架位置

| 字段名 | 别名 | 类型 | 宽度 | 说明 |
|--------|------|------|------|------|
| OBJECTID | Object ID | OID | 4 | 唯一标识符 |
| SHAPE | Shape | Geometry | - | 线几何 |
| JOB_NUM | Job ID | String | 20 | 作业编号 |
| TYP_CD | Type of Feature | String | 4 | 特征类型 |
| MIN_HT_NUM | Min Height of Gantry (m) | Double | 8 | 门架最小高度（米） |
| LVL_NUM | Level of Road | SmallInteger | 2 | 道路层级 |
| RD_CD | Road Code-Name | String | 6 | 道路代码 |
| GNTRY_NUM | Gantry No | String | 10 | 门架编号 |
| PKG_REF | Attachment Folder | String | 50 | 附件文件夹 |
| EXCEPTION_IND | Exception Indicator | String | 1 | 异常标识 |
| LAST_UPD_USRID_NUM | Last Update User ID | String | 8 | 最后更新用户ID |
| LAST_UPD_DTTM | Last Update Date | Date | 8 | 最后更新日期 |
| CRT_USRID_NUM | Create User ID | String | 8 | 创建用户ID |
| CRT_DTTM | Create Date | Date | 8 | 创建日期 |
| REMARKS | Remarks | String | 200 | 备注 |
| SHAPE.LEN | Shape Length | Double | - | 几何长度 |

**用途**: 拥堵收费分析、交通需求管理

---

### 10. Footpath_Mar2026 - 人行道

**几何类型**: 线（Polyline）或多边形（Polygon）  
**描述**: 人行道网络

| 字段名 | 类型 | 宽度 | 说明 |
|--------|------|------|------|
| OBJECTID | OID | 4 | 唯一标识符 |
| SHAPE | Geometry | - | 几何 |
| JOB_NUM | String | 20 | 作业编号 |
| RD_CD | String | 6 | 道路代码 |
| WIDTH | Double | 8 | 宽度（米） |
| SURFACE_TYPE | String | 20 | 表面类型 |
| REMARKS | String | 200 | 备注 |

**用途**: 行人网络分析、步行可达性研究

---

### 11. GuardRail_Mar2026 - 护栏

**几何类型**: 线（Polyline）  
**描述**: 道路护栏，用于安全防护

| 字段名 | 类型 | 宽度 | 说明 |
|--------|------|------|------|
| OBJECTID | OID | 4 | 唯一标识符 |
| SHAPE | Geometry | - | 线几何 |
| JOB_NUM | String | 20 | 作业编号 |
| RD_CD | String | 6 | 道路代码 |
| RAIL_TYPE | String | 20 | 护栏类型 |
| LENGTH | Double | 8 | 长度（米） |
| REMARKS | String | 200 | 备注 |

**用途**: 道路安全设施分析

---

### 12. KerbLine_Mar2026 - 路缘线

**几何类型**: 线（Polyline）  
**描述**: 道路边缘的路缘石线

| 字段名 | 类型 | 宽度 | 说明 |
|--------|------|------|------|
| OBJECTID | OID | 4 | 唯一标识符 |
| SHAPE | Geometry | - | 线几何 |
| JOB_NUM | String | 20 | 作业编号 |
| RD_CD | String | 6 | 道路代码 |
| KERB_TYPE | String | 20 | 路缘类型 |
| HEIGHT | Double | 8 | 高度（米） |
| REMARKS | String | 200 | 备注 |

**用途**: 道路边界定义、排水分析

---

### 13. LampPost_Mar2026 - 路灯杆

**几何类型**: 点（Point）  
**描述**: 道路照明路灯位置

| 字段名 | 类型 | 宽度 | 说明 |
|--------|------|------|------|
| OBJECTID | OID | 4 | 唯一标识符 |
| SHAPE | Geometry | - | 点几何 |
| JOB_NUM | String | 20 | 作业编号 |
| RD_CD | String | 6 | 道路代码 |
| LAMP_TYPE | String | 20 | 灯具类型 |
| HEIGHT | Double | 8 | 高度（米） |
| REMARKS | String | 200 | 备注 |

**用途**: 照明设施管理、夜间安全分析

---

### 14. LaneMarking_Mar2026 - 车道标线

**几何类型**: 线（Polyline）  
**描述**: 道路车道分隔线、边界线等

| 字段名 | 类型 | 宽度 | 说明 |
|--------|------|------|------|
| OBJECTID | OID | 4 | 唯一标识符 |
| SHAPE | Geometry | - | 线几何 |
| JOB_NUM | String | 20 | 作业编号 |
| RD_CD | String | 6 | 道路代码 |
| MARKING_TYPE | String | 20 | 标线类型（实线/虚线等） |
| COLOR | String | 10 | 颜色 |
| REMARKS | String | 200 | 备注 |

**用途**: 车道管理、交通规则分析

---

### 15. ParkingStandardsZone_Mar2026 - 停车标准区域

**几何类型**: 多边形（Polygon）  
**描述**: 划定的停车区域

| 字段名 | 类型 | 宽度 | 说明 |
|--------|------|------|------|
| OBJECTID | OID | 4 | 唯一标识符 |
| SHAPE | Geometry | - | 多边形几何 |
| JOB_NUM | String | 20 | 作业编号 |
| RD_CD | String | 6 | 道路代码 |
| ZONE_TYPE | String | 20 | 区域类型 |
| CAPACITY | Integer | 4 | 停车容量 |
| REMARKS | String | 200 | 备注 |

**用途**: 停车规划、土地利用分析

---

### 16. PassengerPickupBay_Mar2026 - 乘客上下客区

**几何类型**: 多边形（Polygon）  
**描述**: 指定的乘客上下车区域

| 字段名 | 类型 | 宽度 | 说明 |
|--------|------|------|------|
| OBJECTID | OID | 4 | 唯一标识符 |
| SHAPE | Geometry | - | 多边形几何 |
| JOB_NUM | String | 20 | 作业编号 |
| RD_CD | String | 6 | 道路代码 |
| BAY_TYPE | String | 20 | 上下客区类型 |
| LENGTH | Double | 8 | 长度（米） |
| REMARKS | String | 200 | 备注 |

**用途**: 客运服务优化、交通组织

---

### 17. PedestrainOverheadbridge_UnderPass_Mar2026 - 人行天桥/地下通道

**几何类型**: 线（Polyline）或多边形（Polygon）  
**描述**: 人行过街天桥和地下通道

| 字段名 | 类型 | 宽度 | 说明 |
|--------|------|------|------|
| OBJECTID | OID | 4 | 唯一标识符 |
| SHAPE | Geometry | - | 几何 |
| JOB_NUM | String | 20 | 作业编号 |
| RD_CD | String | 6 | 道路代码 |
| STRUCTURE_TYPE | String | 20 | 结构类型（天桥/地下通道） |
| WIDTH | Double | 8 | 宽度（米） |
| LENGTH | Double | 8 | 长度（米） |
| HAS_LIFT | String | 1 | 是否有电梯（Y/N） |
| REMARKS | String | 200 | 备注 |

**用途**: 行人过街设施分析、无障碍通行

---

### 18. Railing_Mar2026 - 栏杆

**几何类型**: 线（Polyline）  
**描述**: 人行道、桥梁等处的防护栏杆

| 字段名 | 类型 | 宽度 | 说明 |
|--------|------|------|------|
| OBJECTID | OID | 4 | 唯一标识符 |
| SHAPE | Geometry | - | 线几何 |
| JOB_NUM | String | 20 | 作业编号 |
| RD_CD | String | 6 | 道路代码 |
| RAILING_TYPE | String | 20 | 栏杆类型 |
| LENGTH | Double | 8 | 长度（米） |
| REMARKS | String | 200 | 备注 |

**用途**: 安全设施管理

---

### 19. RetainingWall_Mar2026 - 挡土墙

**几何类型**: 线（Polyline）或多边形（Polygon）  
**描述**: 用于支撑土体的挡土结构

| 字段名 | 类型 | 宽度 | 说明 |
|--------|------|------|------|
| OBJECTID | OID | 4 | 唯一标识符 |
| SHAPE | Geometry | - | 几何 |
| JOB_NUM | String | 20 | 作业编号 |
| RD_CD | String | 6 | 道路代码 |
| WALL_HEIGHT | Double | 8 | 墙高（米） |
| MATERIAL | String | 20 | 材料类型 |
| REMARKS | String | 200 | 备注 |

**用途**: 土木工程分析、边坡稳定性

---

### 20. RoadCrossing_Mar2026 - 道路交叉口

**几何类型**: 点（Point）或多边形（Polygon）  
**描述**: 道路交叉口位置

| 字段名 | 类型 | 宽度 | 说明 |
|--------|------|------|------|
| OBJECTID | OID | 4 | 唯一标识符 |
| SHAPE | Geometry | - | 几何 |
| JOB_NUM | String | 20 | 作业编号 |
| RD_CD | String | 6 | 道路代码 |
| CROSSING_TYPE | String | 20 | 交叉口类型 |
| HAS_SIGNAL | String | 1 | 是否有信号灯（Y/N） |
| REMARKS | String | 200 | 备注 |

**用途**: 路口分析、交通流建模

---

### 21. RoadHump_Mar2026 - 减速带

**几何类型**: 线（Polyline）  
**描述**: 用于降低车速的减速带

| 字段名 | 类型 | 宽度 | 说明 |
|--------|------|------|------|
| OBJECTID | OID | 4 | 唯一标识符 |
| SHAPE | Geometry | - | 线几何 |
| JOB_NUM | String | 20 | 作业编号 |
| RD_CD | String | 6 | 道路代码 |
| HUMP_TYPE | String | 20 | 减速带类型 |
| WIDTH | Double | 8 | 宽度（米） |
| HEIGHT | Double | 8 | 高度（米） |
| REMARKS | String | 200 | 备注 |

**用途**: 交通 calming 措施分析、速度管理

---

### 22. RoadSectionLine_Mar2026 - 路段线

**几何类型**: 线（Polyline）  
**要素数量**: 15,313条路段  
**描述**: 道路网络的基本路段单元，包含道路名称、类别等信息

| 字段名 | 别名 | 类型 | 宽度 | 说明 |
|--------|------|------|------|------|
| OBJECTID | Object ID | OID | 4 | 唯一标识符 |
| SHAPE | Shape | Geometry | - | 线几何 |
| JOB_NUM | Job ID | String | 20 | 作业编号 |
| RD_CD | Road Code-Name | String | 6 | 道路代码 |
| RD_CATG_NAM | Road Category | String | 20 | 道路类别（Expressway/Arterial等） |
| EXCEPTION_IND | Exception Indicator | String | 1 | 异常标识 |
| LAST_UPD_USRID_NUM | Last Update User ID | String | 8 | 最后更新用户ID |
| LAST_UPD_DTTM | Last Update Date | Date | 8 | 最后更新日期 |
| CRT_USRID_NUM | Create User ID | String | 8 | 创建用户ID |
| CRT_DTTM | Create Date | Date | 8 | 创建日期 |
| PKG_REF | Attachment Folder | String | 50 | 附件文件夹 |
| REMARKS | Remarks | String | 200 | 备注 |
| SHAPE.LEN | Shape Length | Double | - | 路段长度（米） |

**用途**: 道路网络建模、路径规划、拓扑分析

---

### 23. SpeedRegulatingStrip_Mar2026 - 调速带

**几何类型**: 多边形（Polygon）  
**描述**: 用于调节车速的路面标记带

| 字段名 | 类型 | 宽度 | 说明 |
|--------|------|------|------|
| OBJECTID | OID | 4 | 唯一标识符 |
| SHAPE | Geometry | - | 多边形几何 |
| JOB_NUM | String | 20 | 作业编号 |
| RD_CD | String | 6 | 道路代码 |
| STRIP_TYPE | String | 20 | 调速带类型 |
| REMARKS | String | 200 | 备注 |

**用途**: 速度管理、交通安全

---

### 24. StreetPaint_Mar2026 - 路面油漆标记

**几何类型**: 多边形（Polygon）  
**描述**: 路面上的油漆标记（斑马线、停止线等）

| 字段名 | 类型 | 宽度 | 说明 |
|--------|------|------|------|
| OBJECTID | OID | 4 | 唯一标识符 |
| SHAPE | Geometry | - | 多边形几何 |
| JOB_NUM | String | 20 | 作业编号 |
| RD_CD | String | 6 | 道路代码 |
| PAINT_TYPE | String | 20 | 油漆标记类型 |
| COLOR | String | 10 | 颜色 |
| REMARKS | String | 200 | 备注 |

**用途**: 交通标志分析、路口设计

---

### 25. TaxiStand_Mar2026 - 出租车站

**几何类型**: 点（Point）  
**描述**: 出租车候客站位置

| 字段名 | 类型 | 宽度 | 说明 |
|--------|------|------|------|
| OBJECTID | OID | 4 | 唯一标识符 |
| SHAPE | Geometry | - | 点几何 |
| JOB_NUM | String | 20 | 作业编号 |
| RD_CD | String | 6 | 道路代码 |
| STAND_ID | String | 20 | 站点ID |
| CAPACITY | Integer | 4 | 容纳车辆数 |
| REMARKS | String | 200 | 备注 |

**用途**: 出租车服务分析、站点规划

---

### 26. TrafficLight_Mar2026 - 交通信号灯

**几何类型**: 点（Point）  
**文件名**: TrafficSignalAspect.shp  
**描述**: 交通信号灯位置及相位信息

| 字段名 | 类型 | 宽度 | 说明 |
|--------|------|------|------|
| OBJECTID | OID | 4 | 唯一标识符 |
| SHAPE | Geometry | - | 点几何 |
| JOB_NUM | String | 20 | 作业编号 |
| RD_CD | String | 6 | 道路代码 |
| SIGNAL_ID | String | 20 | 信号灯ID |
| PHASE_COUNT | Integer | 4 | 相位数量 |
| CYCLE_TIME | Integer | 4 | 周期时间（秒） |
| REMARKS | String | 200 | 备注 |

**用途**: 信号配时分析、路口通行能力

---

### 27. TrainStation_Mar2026 - 火车站

**几何类型**: 点（Point）  
**描述**: MRT/LRT地铁站位置

| 字段名 | 类型 | 宽度 | 说明 |
|--------|------|------|------|
| OBJECTID | OID | 4 | 唯一标识符 |
| SHAPE | Geometry | - | 点几何 |
| JOB_NUM | String | 20 | 作业编号 |
| STATION_CODE | String | 10 | 车站代码（如"NS1"） |
| STATION_NAME | String | 100 | 车站名称 |
| LINE_CODE | String | 10 | 线路代码（NS/EW/NE等） |
| HAS_INTERCHANGE | String | 1 | 是否换乘站（Y/N） |
| REMARKS | String | 200 | 备注 |

**用途**: 轨道交通网络分析、站点可达性

---

### 28. VehicleBridge_FlyOver_Underpass_Mar2026 - 车辆桥梁/立交桥/地下通道

**几何类型**: 线（Polyline）或多边形（Polygon）  
**描述**: 车辆通行的桥梁、立交桥和地下通道

| 字段名 | 类型 | 宽度 | 说明 |
|--------|------|------|------|
| OBJECTID | OID | 4 | 唯一标识符 |
| SHAPE | Geometry | - | 几何 |
| JOB_NUM | String | 20 | 作业编号 |
| RD_CD | String | 6 | 道路代码 |
| STRUCTURE_TYPE | String | 20 | 结构类型（桥梁/立交/地下通道） |
| LENGTH | Double | 8 | 长度（米） |
| WIDTH | Double | 8 | 宽度（米） |
| CLEARANCE | Double | 8 | 净空高度（米） |
| REMARKS | String | 200 | 备注 |

**用途**: 立体交通分析、路网连通性

---

### 29. WordMarking_Mar2026 - 文字标记

**几何类型**: 多边形（Polygon）  
**描述**: 路面上的文字标记（如"BUS"、"STOP"等）

| 字段名 | 类型 | 宽度 | 说明 |
|--------|------|------|------|
| OBJECTID | OID | 4 | 唯一标识符 |
| SHAPE | Geometry | - | 多边形几何 |
| JOB_NUM | String | 20 | 作业编号 |
| RD_CD | String | 6 | 道路代码 |
| WORD_TEXT | String | 50 | 文字内容 |
| FONT_SIZE | Double | 8 | 字体大小 |
| REMARKS | String | 200 | 备注 |

**用途**: 交通指示分析、路面信息管理

---

## 二、公共交通统计数据（PUBLIC TRANSPORT）

### 1. monthly_ave_daily_pt_ridership.csv - 月度平均日公共交通客流量

**文件大小**: 4.7 KB  
**记录数**: 217条（2019年1月 - 2024年12月）  
**时间跨度**: 2019-2024年  
**更新频率**: 月度

#### 表结构

| 字段名 | 类型 | 说明 | 示例值 |
|--------|------|------|--------|
| month | String | 月份（MMM-YY格式） | "Jan-19", "Dec-24" |
| mode | String | 交通模式 | "MRT", "LRT", "Public Bus" |
| ridership | Integer | 平均日客流量（人次） | 3462000, 218000 |

#### 数据特点
- 包含三种公共交通模式：MRT（地铁）、LRT（轻轨）、Public Bus（公共巴士）
- 2020年4-5月受疫情影响客流量显著下降
- 2022年后逐步恢复至疫情前水平

#### 用途
- 公共交通需求趋势分析
- 疫情影响评估
- 运力规划

---

### 2. yearly_ave_daily_pt_ridership.csv - 年度平均日公共交通客流量

**文件大小**: 1.7 KB  
**记录数**: 91条（1995-2024年）  
**时间跨度**: 1995-2024年（30年历史数据）  
**更新频率**: 年度

#### 表结构

| 字段名 | 类型 | 说明 | 示例值 |
|--------|------|------|--------|
| year | Integer | 年份 | 1995, 2024 |
| mode | String | 交通模式 | "MRT", "LRT", "Public Bus" |
| ridership | Integer | 平均日客流量（人次） | 740000, 3412000 |

#### 数据特点
- 长期历史数据，可观察30年发展趋势
- LRT从1999年开始运营
- MRT客流量从1995年的74万增长到2024年的341万

#### 用途
- 长期交通发展趋势分析
- 政策效果评估
- 基础设施投资回报分析

---

### 3. monthly_taxi_fleet.csv - 月度出租车车队数量

**文件大小**: 41.0 KB  
**记录数**: 1,826条（2005年1月 - 2024年12月）  
**时间跨度**: 2005-2024年  
**更新频率**: 月度

#### 表结构

| 字段名 | 类型 | 说明 | 示例值 |
|--------|------|------|--------|
| month | String | 月份（YYYY-MM格式） | "2005-01", "2024-12" |
| company | String | 出租车公司 | "Comfort", "CityCab", "SMRT", "YTC", "TransCab", "Premier", "Smart", "Individual Yellow-Top" |
| taxi_fleet | Integer | 车队数量（辆） | 9952, 4965 |

#### 主要出租车公司
- **Comfort**: 最大的出租车运营商
- **CityCab**: 第二大运营商
- **SMRT**: SMRT集团运营
- **TransCab**: 中型运营商
- **Premier**: 高端出租车服务
- **YTC**: 黄色出租车个体户
- **Smart**: 小型运营商
- **Individual Yellow-Top**: 个体黄色顶灯出租车

#### 数据特点
- 覆盖8家主要出租车公司
- 可观察行业整合趋势（部分公司车队规模变化）
- 反映网约车冲击下的传统出租车行业发展

#### 用途
- 出租车市场分析
- 竞争格局研究
- 行业政策影响评估

---

### 4. annual_rts_stations.csv - 年度地铁站/LRT站数量

**文件大小**: < 1 KB  
**记录数**: 1条（仅2022年数据）  
**时间跨度**: 2022年  
**更新频率**: 年度

#### 表结构

| 字段名 | 类型 | 说明 | 示例值 |
|--------|------|------|--------|
| year | Integer | 年份 | 2022 |
| mrt | Integer | MRT车站数量 | 166 |
| lrt | Integer | LRT车站数量 | 41 |
| depot | Integer | 车厂数量 | 9 |

#### 数据说明
- 该文件目前仅包含2022年快照数据
- MRT车站总数：166个
- LRT车站总数：41个
- 车厂（车辆段）：9个

#### 用途
- 轨道交通网络规模统计
- 基础设施存量分析

---

### 5. PremiumBusServicesCSV20260121.csv - 优质巴士服务

**文件大小**: 191.1 KB  
**记录数**: 1,486条  
**数据采集日期**: 2026年1月21日  
**描述**: 新加坡优质巴士服务（Premium Bus Services）的详细信息，包括路线、站点、票价、运营时间等

#### 表结构

| 字段名 | 类型 | 说明 | 示例值 |
|--------|------|------|--------|
| BUS_SERVICE_NAME_TXT | String | 巴士服务名称 | "PBS 525", "PBS from Grande Vista to Yio Chu Kang/Ang Mo Kio MRT Stations (loop)" |
| OPR_DESC_TXT | String | 运营商描述 | "Deconti Trans", "City Bus Services", "APT Travel Pte Ltd" |
| ORIG_DEST_TXT | String | 起点-终点描述 | "Buangkok Crescent to Marina Boulevard" |
| BUS_DIRCTN_TXT | Integer | 方向编号 | 1（去程）, 2（回程） |
| BUS_ROUTE_SEQ_NUM | Integer | 路线序列号 | 1, 2, 3... |
| BUS_STOP_CD | String | 巴士站代码 | "66589", "-"（临时站点用"-"表示） |
| BUS_STOP_DESC_TXT | String | 巴士站描述 | "Buangkok Sports Park", "Blk 998B" |
| RD_NAM_TXT | String | 道路名称 | "Buangkok Crescent", "Marina Boulevard" |
| LONGTD_TXT | Double | 经度（WGS84） | 103.8794283 |
| LATTD_TXT | Double | 纬度（WGS84） | 1.381995514 |
| OP_HR_TXT | String | 运营时间描述 | "One trip at 8.30am", "Monday to Fridays 6.15am to 8.30am" |
| FARE_TXT | String | 票价描述 | "$5.00 (cash)", "$3.80 (card) / $4.00 (cash) / $2.00 (child)" |

#### 数据特点
- 包含多条优质巴士线路（PBS 525, PBS 531, PBS 545, PBS 550, PBS 555等）
- 每条线路包含完整的站点序列和地理坐标
- 提供详细的运营时间和票价信息
- 部分站点为临时站点（无固定站代码，用"-"表示）
- 票价分为成人、儿童/学生、老人等不同类别

#### 典型线路示例
- **PBS 525**: Buangkok Crescent → Marina Boulevard（早高峰单程）
- **PBS 531**: Simei → Shenton Way/Anson Road（早高峰单程）
- **PBS 545**: Bedok North Avenue 4 → Fullerton Road（早高峰单程）
- **PBS 550**: Sumang Walk → Fullerton Road（早高峰单程）
- **PBS 555**: Bukit Batok West Avenue 5 → Beach Road（双方向运营）

#### 用途
- 优质巴士服务网络分析
- 通勤模式研究
- 票价策略分析
- 服务范围评估

---

### 6. yearly_rail_length.csv - 年度铁路长度

**文件大小**: 0.6 KB  
**记录数**: 41条（2005-2024年）  
**时间跨度**: 2005-2024年  
**更新频率**: 年度

#### 表结构

| 字段名 | 类型 | 说明 | 示例值 |
|--------|------|------|--------|
| year | Integer | 年份 | 2005, 2024 |
| rail_type | String | 铁路类型 | "mrt", "lrt" |
| length | Double | 轨道长度（公里） | 109.4, 242.5 |

#### 数据特点
- MRT轨道长度从2005年的109.4公里增长到2024年的242.5公里
- LRT轨道长度保持稳定在28.8公里（自2005年起）
- 反映了新加坡轨道交通网络的快速扩张

#### 关键时间节点
- **2009年**: MRT突破118.9公里（市区线开通）
- **2017年**: MRT达到199.3公里（滨海市区线延伸）
- **2021年**: MRT达到216.5公里（汤申-东海岸线部分开通）
- **2024年**: MRT达到242.5公里（最新扩展）

#### 用途
- 基础设施发展追踪
- 投资效果评估
- 网络覆盖分析

---

## 三、数据使用建议

### 1. 软件工具推荐

#### GIS软件
- **ArcGIS Pro**: 完整支持Shapefile格式，适合专业GIS分析
- **QGIS**: 开源免费，功能强大，支持SVY21坐标系
- **GeoPandas (Python)**: 编程处理地理数据，适合批量分析

#### 数据分析工具
- **Python**: pandas, geopandas, matplotlib, folium
- **R**: sf, ggplot2, leaflet
- **Excel/Google Sheets**: 简单统计分析

### 2. 坐标系统转换

数据采用**SVY21投影坐标系**（EPSG:3414），如需转换为WGS84经纬度：

```python
import geopandas as gpd

# 读取Shapefile
gdf = gpd.read_file('RoadSectionLine.shp')

# 设置原始坐标系为SVY21
gdf.crs = "EPSG:3414"

# 转换为WGS84
gdf_wgs84 = gdf.to_crs("EPSG:4326")
```

### 3. 典型应用场景

#### 场景1: 公交网络可达性分析
**所需数据**:
- BusStopLocation_Mar2026（巴士站位置）
- TrainStation_Mar2026（地铁站位置）
- RoadSectionLine_Mar2026（道路网络）

**分析内容**:
- 计算任意位置到最近公交站/地铁站的距离
- 生成公交服务覆盖热力图
- 识别公交服务薄弱区域

#### 场景2: 交通设施密度分析
**所需数据**:
- TrafficLight_Mar2026（交通信号灯）
- ERPGantry_Mar2026（ERP门架）
- DetectorLoop_Mar2026（检测线圈）

**分析内容**:
- 按区域统计设施密度
- 识别设施集中区域
- 评估基础设施投资分布

#### 场景3: 公共交通客流趋势分析
**所需数据**:
- monthly_ave_daily_pt_ridership.csv
- yearly_ave_daily_pt_ridership.csv

**分析内容**:
- 绘制客流量时间序列图
- 分析季节性波动
- 评估疫情前后变化

#### 场景4: 优质巴士服务优化
**所需数据**:
- PremiumBusServicesCSV20260121.csv
- BusStopLocation_Mar2026

**分析内容**:
- 可视化PBS线路覆盖范围
- 分析站点间距和运营效率
- 识别潜在的新线路需求

#### 场景5: 自行车道网络规划
**所需数据**:
- CyclingPath_Mar2026
- Footpath_Mar2026
- RoadSectionLine_Mar2026

**分析内容**:
- 现有自行车道连通性分析
- 识别断点和瓶颈
- 规划扩展路线

### 4. 数据质量注意事项

#### 位置精度
- 地理空间数据标注为"Indicative locations"（指示性位置）
- 不适用于高精度工程应用
- 适合宏观分析和规划用途

#### 数据完整性
- 大部分图层包含`EXCEPTION_IND`字段，标识异常情况
- 使用前建议过滤`EXCEPTION_IND = 'Y'`的记录

#### 时效性
- 地理空间数据更新至2026年3月
- 统计数据更新至2024年12月
- 实际使用时需考虑数据发布时间与当前时间的差异

#### 字段缺失
- 部分旧记录可能某些字段为空
- 建议使用pandas的`fillna()`或SQL的`COALESCE()`处理

### 5. 数据关联键

不同数据集之间可通过以下字段进行关联：

| 关联字段 | 相关数据集 | 说明 |
|----------|-----------|------|
| `RD_CD` (道路代码) | 所有GEOSPATIAL图层 | 关联同一道路的不同设施 |
| `BUS_STOP_NUM` | BusStopLocation + PremiumBusServices | 关联巴士站信息 |
| `STATION_CODE` | TrainStation + 其他轨道交通数据 | 关联车站信息 |

---

## 四、数据来源与版权

**数据来源**: 新加坡陆路交通管理局（Land Transport Authority, LTA）  
**数据许可**: 仅限内部使用（The data is for internal use only）  
**访问限制**: 按需分配（on need basis）  
**引用格式**: 
```
Land Transport Authority Singapore. (2026). Static Transport Data - March 2026 Version.
```

**联系方式**:
- 地址: 251 North Bridge Road Singapore 179102
- 电话: +65 6332 8915

---

## 五、版本历史

| 版本 | 日期 | 说明 |
|------|------|------|
| Mar 2026 | 2026-03-05 | 最新版本，包含29个地理空间图层和6个统计数据集 |
| Previous | 2024-05-13 | 上一版本（元数据显示最后同步日期） |

---

## 六、技术支持

如有数据相关问题，建议：
1. 首先查阅本文档和相关字段的XML元数据
2. 使用GIS软件查看数据的空间分布和质量
3. 联系数据提供方LTA获取官方支持

---

**文档创建日期**: 2026年5月  
**文档版本**: 1.0  
**适用数据版本**: Static_2026_03
