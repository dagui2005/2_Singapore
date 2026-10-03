@echo off
REM ============================================================
REM  E-CAP-01  抽样需求-道路供给尺度统一试验  (EXPERIMENT ONLY)
REM  独立点火器：由 Windows 任务计划程序托管，脱离 agent shell 进程树
REM  唯一模型改动 = qsim.flowCapacityFactor / storageCapacityFactor -> 0.434977
REM ============================================================
cd /d D:\Luan\2026-05\2_Singapore
set LOG=D:\Luan\2026-05\2_Singapore\experiments\E-CAP-01_scale_capacity\logs\ecap01_task.log
echo [%DATE% %TIME%] TASK START > "%LOG%"
"C:\Users\LQP\miniconda3\python.exe" scripts\experiments\ecap01_build_config.py --run --heap 24g >> "%LOG%" 2>&1
set RC=%ERRORLEVEL%
echo [%DATE% %TIME%] TASK END rc=%RC% >> "%LOG%"
