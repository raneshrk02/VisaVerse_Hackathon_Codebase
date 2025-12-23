@echo off
REM Start both frontend and backend in separate terminals for USB deployment
REM Frontend (static server): D:\frontend - uses Python 3.11 from D:\python
REM Backend: D:\backend (expects a venv at D:\backend\venv) - uses Python 3.11 from D:\python

echo ==================================================================
echo Starting frontend and backend servers
echo Python 3.11 from D:\python
echo ==================================================================

REM Check if D:\python\python.exe exists
if not exist D:\python\python.exe (
  echo ERROR: D:\python\python.exe not found. Please ensure Python 3.11 is at D:\python\python.exe
  pause
  exit /b 1
)

REM Check if frontend directory exists
if not exist D:\frontend (
  echo WARNING: D:\frontend not found. Frontend server may fail to start.
)

REM Check if backend directory exists
if not exist D:\backend (
  echo WARNING: D:\backend not found. Backend server may fail to start.
)

REM --- Start Frontend ---
echo Starting frontend server on port 8080...
start "Frontend Server" cmd /k "cd /d D:\frontend && echo Serving frontend from D:\frontend on port 8080 && D:\node\npm run dev"

REM --- Start Backend ---
echo Starting backend server on port 8001...
start "Backend Server" cmd /k "cd /d D:\backend && call D:\backend\venv\Scripts\activate.bat && echo Using venv from D:\backend\venv && echo Starting backend server... && uvicorn main:app --host 0.0.0.0 --port 8001 --reload"

echo.
echo Launched Frontend and Backend windows.
echo Frontend: http://localhost:8080
echo Backend: http://localhost:8001
echo Check the new terminal windows for logs and errors.
pause