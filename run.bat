@echo off
title Lemiex Order Manager
cd /d "%~dp0"

echo ========================================
echo   Lemiex Order Manager
echo ========================================
echo.
echo   1. Auto (desktop app)
echo   2. Web browser
echo   3. Server only
echo.
set /p choice="Chọn (1/2/3): "

if "%choice%"=="1" (
    python app_eel.py --app
) else if "%choice%"=="2" (
    python app_eel.py --web
) else if "%choice%"=="3" (
    python app_eel.py --server
) else (
    python app_eel.py
)

pause
