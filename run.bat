@echo off
chcp 65001 >nul
echo ================================================================================
echo LTA DataMall 动态交通数据下载工具
echo ================================================================================
echo.
echo 请选择运行模式:
echo 1. 快速下载所有历史数据（推荐）
echo 2. 交互式下载（可选择模式）
echo 3. 启动实时监控
echo 4. 运行数据分析示例
echo 5. 安装依赖
echo.

set /p choice="请输入选择 (1-5): "

if "%choice%"=="1" (
    echo.
    echo 开始快速下载...
    python quick_download.py
) else if "%choice%"=="2" (
    echo.
    echo 启动交互式下载...
    python lta_dynamic_data_downloader.py
) else if "%choice%"=="3" (
    echo.
    set /p duration="请输入监控时长（小时，默认24）: "
    set /p interval="请输入采集间隔（分钟，默认5）: "
    
    if "%duration%"=="" set duration=24
    if "%interval%"=="" set interval=5
    
    echo.
    echo 启动实时监控...
    python start_monitoring.py %duration% %interval%
) else if "%choice%"=="4" (
    echo.
    echo 运行数据分析示例...
    python example_data_analysis.py
) else if "%choice%"=="5" (
    echo.
    echo 安装依赖包...
    pip install -r requirements.txt
) else (
    echo.
    echo 无效选择
)

echo.
pause
