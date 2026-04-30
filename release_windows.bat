@echo off
setlocal ENABLEDELAYEDEXPANSION

set SCRIPT_DIR=%~dp0
cd /d "%SCRIPT_DIR%"

set VERSION=%~1
if "%VERSION%"=="" (
    for /f %%i in ('git describe --tags --abbrev^=0 2^>nul') do set VERSION=%%i
)

if "%VERSION%"=="" (
    echo [ERROR] Version not provided and no git tag found.
    echo Usage: release_windows.bat v0.1.4
    exit /b 1
)

set VERSION=%VERSION:v=%

echo [1/4] Installing/updating dependencies...
if not exist ".venv\Scripts\python.exe" (
    echo [ERROR] .venv\Scripts\python.exe not found.
    exit /b 1
)

call .venv\Scripts\python.exe -m pip install -r requirements.txt || exit /b 1

echo [2/4] Building onedir app...
call .venv\Scripts\python.exe build.py --mode onedir || exit /b 1

echo [3/4] Creating portable ZIP...
call .venv\Scripts\python.exe release_portable.py || exit /b 1

echo [4/4] Creating installer EXE...
call .venv\Scripts\python.exe release_installer.py v%VERSION% || exit /b 1

echo.
echo Release artifacts created:
echo   dist\release\MountDock_Portable.zip
echo   dist\release\MountDock-Setup-v%VERSION%.exe
echo.
echo Done.
exit /b 0
