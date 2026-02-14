@echo off
REM WenShape Backend Startup Script for Windows

REM Ensure working directory is this script's directory (robust for "backend\\run.bat" called from repo root)
cd /d %~dp0

set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8

echo ========================================
echo   WenShape Backend Server
echo ========================================
echo.

REM Check Python installation
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed or not in PATH.
    echo.
    echo Please install Python 3.10+ from:
    echo   https://www.python.org/downloads/
    echo.
    echo IMPORTANT: During installation, check "Add python.exe to PATH"
    echo.
    pause
    exit /b 1
)

echo [1/3] Checking dependencies...
python -m pip install -r requirements.txt -q
if errorlevel 1 (
    echo.
    echo ERROR: Dependency installation failed.
    echo Try running: python -m pip install -r requirements.txt
    echo to see detailed error messages.
    pause
    exit /b 1
)

REM Check if .env exists
if not exist ".env" (
    echo.
    echo [!] .env file not found. Copying from .env.example...
    if not exist ".env.example" (
        echo [!] .env.example not found in: %CD%
        echo [!] Please ensure you are running this script from the backend directory.
        echo.
        pause
        exit /b 1
    )
    copy ".env.example" ".env" >nul
    if errorlevel 1 (
        echo [!] Failed to create .env in: %CD%
        echo.
        pause
        exit /b 1
    )
    echo [!] Created: %CD%\.env
    echo [!] Please edit .env file and add your API keys!
    echo     Or use WENSHAPE_LLM_PROVIDER=mock for demo mode.
    echo.
    pause
)

REM Start server
echo.
echo [2/3] Starting server...
echo.
if "%PORT%"=="" set "PORT=%WENSHAPE_BACKEND_PORT%"
if "%PORT%"=="" set "PORT=8000"
if "%VITE_DEV_PORT%"=="" set "VITE_DEV_PORT=%WENSHAPE_FRONTEND_PORT%"
if "%VITE_DEV_PORT%"=="" set "VITE_DEV_PORT=3000"
echo   Frontend: http://localhost:%VITE_DEV_PORT%
echo   Backend:  http://localhost:%PORT%
echo   API Docs: http://localhost:%PORT%/docs
echo.

echo [3/3] Server running...
if "%WENSHAPE_AUTO_PORT%"=="" set "WENSHAPE_AUTO_PORT=1"
python -m app.main

pause
