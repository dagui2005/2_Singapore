# 快速使用指南

## 🚀 3步开始使用

### 第1步：运行工具
```bash
python lta_dynamic_data_downloader.py
```

### 第2步：选择模式
输入 `1`、`2` 或 `3`：
- **1** = 下载历史数据（推荐首次使用）
- **2** = 启动实时监控
- **3** = 两者都执行

### 第3步：等待完成
工具会自动下载所有数据到 `Dynamic_2026_03_16/` 目录

---

## 📋 常用场景

### 场景1：快速获取样例数据
```bash
python lta_dynamic_data_downloader.py
# 选择 1
# 等待约10-20分钟
```

### 场景2：监控一天交通状况
```bash
python lta_dynamic_data_downloader.py
# 选择 2
# 监控时长: 24
# 采集间隔: 5
```

### 场景3：完整数据采集
```bash
python lta_dynamic_data_downloader.py
# 选择 3
# 先下载历史数据
# 然后监控24小时
```

---

## 📊 数据说明

### 最重要的文件

| 文件名 | 大小 | 内容 |
|--------|------|------|
| TrafficSpeedBands_v4.json | 55 MB | 143,787条路段速度（最核心） |
| TrafficFlow_Data.json | 16 MB | 交通流量数据 |
| BusRoutes.json | 8.4 MB | 巴士路线信息 |
| EVChargingPoints_Batch_Data.json | 3 MB | EV充电点数据 |

### 实时监控文件

每5分钟生成一组文件，包含：
- TrafficIncidents - 交通事故
- TrafficSpeedBands - 路段速度 ⭐
- CarparkAvailability - 停车场空位
- 等17种数据类型

---

## ⚠️ 注意事项

1. **存储空间**：确保至少有20 GB可用空间
2. **网络稳定**：下载过程需要稳定的网络连接
3. **API限制**：遵守LTA API的使用条款和频率限制
4. **时间戳**：部分文件会自动添加采集时间

---

## 🔍 验证数据

下载完成后检查：

```bash
# 查看文件数量
ls Dynamic_2026_03_16/historical_data/*.json | wc -l
# 应该看到 25+ 个文件

# 查看实时监控
ls Dynamic_2026_03_16/realtime_monitoring/ | head
# 应该看到按时间戳命名的文件

# 查看日志
tail Dynamic_2026_03_16/download.log
# 应该看到 "✓ 所有历史数据下载完成！"
```

---

## 💡 提示

- 首次使用建议先运行模式1测试
- 实时监控会产生大量数据，注意存储空间
- 可以随时按 Ctrl+C 停止下载
- 查看详细日志：`cat Dynamic_2026_03_16/download.log`
