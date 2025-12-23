@echo off
setlocal enabledelayedexpansion
REM ==================================================================
REM Create a venv in D:\backend and install dependencies from requirements.txt
REM All Python commands use D:\python\python.exe (Python 3.11)
REM ==================================================================
echo ==================================================================
echo Create venv and install requirements (for USB deployment)
echo Python 3.11 from D:\python
echo ==================================================================

REM Check Python existence
if not exist "D:\python\python.exe" (
  echo ERROR: D:\python\python.exe not found. Please ensure Python 3.11 is installed there.
  pause
  exit /b 1
)

REM Ensure backend folder exists
cd /d "D:\backend" 2>nul || (
  echo ERROR: D:\backend not found. Please copy backend to D:\backend
  pause
  exit /b 1
)

REM Create venv if missing
if exist "venv\Scripts\python.exe" (
  echo Virtual environment already exists at D:\backend\venv
) else (
  echo Creating venv using Python 3.11...
  "D:\python\python.exe" -m venv venv
  if errorlevel 1 (
    echo Failed to create virtual environment.
    pause
    exit /b 1
  )
)

set "VENV_PY=D:\backend\venv\Scripts\python.exe"

if not exist "%VENV_PY%" (
  echo ERROR: venv Python not found at %VENV_PY%
  pause
  exit /b 1
)

echo.
echo Upgrading pip, setuptools, and wheel in the venv...
"%VENV_PY%" -m pip install --upgrade pip setuptools wheel

REM Locate requirements file
set REQ=
if exist "requirements.txt" (
  set REQ=requirements.txt
)
if exist "D:\requirements.txt" (
  set REQ=D:\requirements.txt
)

if not defined REQ (
  echo requirements.txt not found in D:\backend or D:\
  pause
  exit /b 1
)

REM Install dependencies
echo.
if exist "D:\backend\wheelhouse" (
  echo Installing from local wheelhouse: D:\backend\wheelhouse
  "%VENV_PY%" -m pip install --no-index --find-links "%CD%\wheelhouse" -r "%REQ%"
  goto :installation_done
)

if exist "D:\wheelhouse" (
  echo Installing from local wheelhouse: D:\wheelhouse
  "%VENV_PY%" -m pip install --no-index --find-links "D:\wheelhouse" -r "%REQ%"
  goto :installation_done
)

echo Installing from PyPI (online). This may take a while...
"%VENV_PY%" -m pip install -r "%REQ%"

:installation_done
echo.
echo ==================================================================
echo Installation complete.
echo To start the backend:
echo     D:\backend\venv\Scripts\activate.bat
echo     python -m uvicorn main:app --port 8000 --reload
echo ==================================================================
pause