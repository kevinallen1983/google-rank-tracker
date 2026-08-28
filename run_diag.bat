@echo off
setlocal
cd /d "%~dp0"

set "PY="
where py >nul 2>nul && set "PY=py"
if not defined PY (where python >nul 2>nul && set "PY=python")
if not defined PY (if exist "C:\Python311\python.exe" set "PY=C:\Python311\python.exe")
if not defined PY (if exist "C:\Python312\python.exe" set "PY=C:\Python312\python.exe")
if not defined PY (if exist "C:\Python313\python.exe" set "PY=C:\Python313\python.exe")
if not defined PY (if exist "C:\Users\Administrator\.workbuddy\binaries\python\versions\3.13.12\python.exe" set "PY=C:\Users\Administrator\.workbuddy\binaries\python\versions\3.13.12\python.exe")

if not defined PY (
  echo ERROR: Python not found. Cannot run diagnosis.
  pause
  exit /b 1
)

echo Running SERP diagnosis...
echo Result will be saved to result.txt
echo.
"%PY%" test_serp.py > result.txt 2>&1
if errorlevel 1 (
  echo Diagnosis script failed. See result.txt for details.
) else (
  echo Diagnosis done. Result saved to result.txt
)
echo.
echo Please open result.txt with Notepad and send the content.
pause
