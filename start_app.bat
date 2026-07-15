@echo off
setlocal EnableExtensions EnableDelayedExpansion

set "SCRIPT_DIR=%~dp0"
cd /d "%SCRIPT_DIR%"

set "VENV_DIR=%SCRIPT_DIR%.venv"

where py >nul 2>nul
if %ERRORLEVEL% EQU 0 (
    set "PYTHON_CMD=py"
) else (
    where python >nul 2>nul
    if %ERRORLEVEL% EQU 0 (
        set "PYTHON_CMD=python"
    ) else (
        echo Python was not found.
        echo Please install Python 3.10+ from https://www.python.org/downloads/ and try again.
        pause
        exit /b 1
    )
)

if not exist "%VENV_DIR%\Scripts\python.exe" (
    echo Creating virtual environment...
    %PYTHON_CMD% -m venv "%VENV_DIR%"
)

set "PYTHON_EXE=%VENV_DIR%\Scripts\python.exe"

echo Installing requirements...
"%PYTHON_EXE%" -m pip install --upgrade pip
"%PYTHON_EXE%" -m pip install -r requirements.txt

echo.
echo Starting Parcel Label Extractor...
echo Open your browser at: http://localhost:3000
echo Press Ctrl+C in this window to stop the app.
echo.
start "" http://localhost:3000
"%PYTHON_EXE%" -m uvicorn main:app --host 0.0.0.0 --port 3000
