@echo off
chcp 936 >nul
cd /d "%~dp0"

REM ========== 1. 定位 Python ==========
set PY=

where python >nul 2>nul
if %errorlevel%==0 set PY=python

if "%PY%"=="" (
  where py >nul 2>nul
  if %errorlevel%==0 set PY=py
)

if "%PY%"=="" (
  if exist "C:\Users\Administrator\.workbuddy\binaries\python\versions\3.13.12\python.exe" (
    set PY=C:\Users\Administrator\.workbuddy\binaries\python\versions\3.13.12\python.exe
  )
)

if "%PY%"=="" (
  if exist "C:\Python313\python.exe" set PY=C:\Python313\python.exe
  if exist "C:\Python312\python.exe" set PY=C:\Python312\python.exe
  if exist "C:\Python311\python.exe" set PY=C:\Python311\python.exe
  if exist "C:\Python310\python.exe" set PY=C:\Python310\python.exe
)

if "%PY%"=="" (
  if exist "%LOCALAPPDATA%\Programs\Python\Python313\python.exe" set PY=%LOCALAPPDATA%\Programs\Python\Python313\python.exe
  if exist "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" set PY=%LOCALAPPDATA%\Programs\Python\Python312\python.exe
  if exist "%LOCALAPPDATA%\Programs\Python\Python311\python.exe" set PY=%LOCALAPPDATA%\Programs\Python\Python311\python.exe
)

if "%PY%"=="" (
  echo ============================================================
  echo   未检测到 Python，排名监控工具无法启动。
  echo ============================================================
  echo.
  echo   请先安装 Python 3.10 或以上版本：
  echo     1. 打开 https://www.python.org/downloads/windows/
  echo     2. 下载并运行安装包
  echo     3. 安装时务必勾选 "Add Python to PATH"
  echo     4. 安装完成后，重新双击本 start.bat
  echo.
  echo   若已装过 Python 但没勾选 PATH：重新运行安装包，选 Modify 勾上即可。
  echo.
  pause
  exit /b 1
)

echo 检测到 Python：%PY%

REM ========== 2. 创建虚拟环境并安装依赖 ==========
if not exist venv (
  echo 正在创建虚拟环境（首次稍慢，请耐心等待）...
  "%PY%" -m venv venv
  if errorlevel 1 (
    echo 创建虚拟环境失败。
    pause
    exit /b 1
  )
)

if not exist venv\Lib\site-packages\flask (
  echo 正在安装依赖（首次稍慢，请耐心等待）...
  venv\Scripts\python.exe -m pip install -r requirements.txt
  if errorlevel 1 (
    echo 安装依赖失败，请检查网络后重试。
    pause
    exit /b 1
  )
)

REM ========== 3. 启动服务，再开浏览器 ==========
echo 正在启动排名监控看板...
start "GoogleRankTracker" "%~dp0venv\Scripts\python.exe" app.py --no-browser
echo 等待服务就绪（约 4 秒）...
timeout /t 4 >nul
start "" http://127.0.0.1:5000
echo.
echo 看板已尝试在浏览器打开。若未自动打开，请手动访问： http://127.0.0.1:5000
echo 服务窗口（标题 GoogleRankTracker）已单独打开，关闭它即可停止服务。
echo 本窗口可安全关闭。
pause
