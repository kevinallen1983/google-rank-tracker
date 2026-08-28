@echo off
chcp 936 >nul
cd /d "%~dp0"

REM 自动请求管理员权限（定时任务需要）
fltmc >nul 2>&1 || (
  echo 正在请求管理员权限以注册定时任务...
  PowerShell -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
  exit /b
)

REM 创建每日 09:00 定时任务，调用 run_check.bat
schtasks /create /tn "GoogleRankTrackerDaily" ^
  /tr "\"%~dp0run_check.bat\"" ^
  /sc daily /st 09:00 /f

if %errorlevel%==0 (
  echo.
  echo 已创建定时任务：GoogleRankTrackerDaily（每天 09:00 自动检查）
  echo 可在「任务计划程序」中查看 / 修改触发时间。
) else (
  echo.
  echo 创建失败，请检查是否以管理员身份运行。
)
echo.
pause
