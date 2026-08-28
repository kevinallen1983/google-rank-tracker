@echo off
setlocal
cd /d "%~dp0"

set "PY="
where py >nul 2>nul && set "PY=py"
if not defined PY (where python >nul 2>nul && set "PY=python")
if not defined PY (if exist "C:\\Python311\\python.exe" set "PY=C:\\Python311\\python.exe")
if not defined PY (if exist "C:\\Python312\\python.exe" set "PY=C:\\Python312\\python.exe")
if not defined PY (if exist "C:\\Python313\\python.exe" set "PY=C:\\Python313\\python.exe")
if not defined PY (if exist "C:\\Users\\Administrator\\.workbuddy\\binaries\\python\\versions\\3.13.12\\python.exe" set "PY=C:\\Users\\Administrator\\.workbuddy\\binaries\\python\\versions\\3.13.12\\python.exe")

if not defined PY (
  echo ERROR: Python not found. Cannot run diagnosis.
  pause
  exit /b 1
)

echo Running SerpBase diagnosis...
echo Result will be saved to serpbase_diag_result.txt
echo.
"%PY%" serpbase_diag.py > serpbase_diag_result.txt 2>&1
if errorlevel 1 (
  echo Diagnosis script failed. See serpbase_diag_result.txt for details.
) else (
  echo Diagnosis done. Result saved to serpbase_diag_result.txt
)
echo.
echo Please open serpbase_diag_result.txt with Notepad and send the content.
pause