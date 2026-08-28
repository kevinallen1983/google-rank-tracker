@echo off
chcp 936 >nul
cd /d "%~dp0"

REM 自动请求管理员权限
fltmc >nul 2>&1 || (
  echo 正在请求管理员权限以删除定时任务...
  PowerShell -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
  exit /b
)

schtasks /delete /tn "GoogleRankTrackerDaily" /f

if %errorlevel%==0 (
  echo.
  echo 已删除定时任务：GoogleRankTrackerDaily
) else (
  echo.
  echo 未找到该任务，或删除失败。
)
echo.
pause
