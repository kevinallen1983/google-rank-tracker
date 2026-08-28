@echo off
setlocal
cd /d "%~dp0"

REM 优先用本目录的 venv；否则回退到 WorkBuddy 自带 Python；最后回退系统 python
if exist "venv\Scripts\python.exe" (
  "venv\Scripts\python.exe" check_rank.py
  goto :eof
)

if exist "C:\Users\Administrator\.workbuddy\binaries\python\versions\3.13.12\python.exe" (
  "C:\Users\Administrator\.workbuddy\binaries\python\versions\3.13.12\python.exe" check_rank.py
  goto :eof
)

python check_rank.py
endlocal
