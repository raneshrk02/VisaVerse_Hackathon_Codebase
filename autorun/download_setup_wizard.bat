@echo off
REM ================================================================
REM SAGE RAG System - Download & Setup Wizard
REM ================================================================
REM Downloads latest version and sets up on user's computer
REM ================================================================

setlocal enabledelayedexpansion
cd /d "%~dp0"

echo.
echo ================================================================
echo SAGE RAG System - Download & Setup Wizard
echo ================================================================
echo.

REM Get USB root
for %%A in (%~dp0..) do set USB_ROOT=%%~dpA
set USB_ROOT=%USB_ROOT:~0,-1%

set DOWNLOAD_DIR=%TEMP%\SAGE_RAG_Setup
set INSTALL_DIR=%ProgramFiles%\SAGE_RAG_System
set DESKTOP=%USERPROFILE%\Desktop
set SHORTCUT=%DESKTOP%\Start SAGE RAG System.lnk

REM Check internet connectivity
echo Checking internet connectivity...
ping google.com -n 1 >nul 2>&1
if errorlevel 1 (
    echo WARNING: No internet connection detected
    echo Using local USB version instead
    echo.
    call "%USB_ROOT%\autorun\auto_run.bat"
    exit /b 0
)

echo ✓ Internet connected
echo.

REM Create download directory
if not exist "%DOWNLOAD_DIR%" mkdir "%DOWNLOAD_DIR%"

echo.
echo ================================================================
echo Step 1: Downloading SAGE RAG System
echo ================================================================
echo.

REM Download latest version (replace with your actual download URL)
set DOWNLOAD_URL=https://your-server.com/sage-rag-latest.zip

echo Downloading from: %DOWNLOAD_URL%
echo Destination: %DOWNLOAD_DIR%\sage-rag.zip
echo.

REM Using PowerShell for better download experience
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
    "try { ^
        $url = '%DOWNLOAD_URL%'; ^
        $outPath = '%DOWNLOAD_DIR%\sage-rag.zip'; ^
        $webClient = New-Object System.Net.WebClient; ^
        $webClient.DownloadFile($url, $outPath); ^
        Write-Host 'Download complete!'; ^
        exit 0 ^
    } catch { ^
        Write-Host 'Download failed: $_'; ^
        exit 1 ^
    }"

if errorlevel 1 (
    echo ERROR: Download failed!
    echo.
    echo Using local USB version instead...
    echo.
    call "%USB_ROOT%\autorun\auto_run.bat"
    exit /b 0
)

echo.
echo ================================================================
echo Step 2: Extracting Files
echo ================================================================
echo.

REM Extract using PowerShell
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
    "Expand-Archive -Path '%DOWNLOAD_DIR%\sage-rag.zip' -DestinationPath '%INSTALL_DIR%' -Force; exit $?"

if errorlevel 1 (
    echo ERROR: Extraction failed!
    echo Using local USB version instead...
    echo.
    call "%USB_ROOT%\autorun\auto_run.bat"
    exit /b 0
)

echo ✓ Files extracted successfully
echo.

REM Create desktop shortcut
echo ================================================================
echo Step 3: Creating Desktop Shortcut
echo ================================================================
echo.

if not exist "%SHORTCUT%" (
    (
        echo Set oWS = WScript.CreateObject("WScript.Shell"^)
        echo sLinkFile = "%SHORTCUT%"
        echo Set oLink = oWS.CreateShortcut(sLinkFile^)
        echo oLink.TargetPath = "wscript.exe"
        echo oLink.Arguments = """%INSTALL_DIR%\autorun\launcher.vbs"""
        echo oLink.WorkingDirectory = "%INSTALL_DIR%"
        echo oLink.Description = "Start SAGE RAG System"
        echo oLink.Save
    ) > "%TEMP%\create_shortcut.vbs"
    
    cscript.exe //nologo "%TEMP%\create_shortcut.vbs" >nul 2>&1
    del /Q "%TEMP%\create_shortcut.vbs" >nul 2>&1
    
    echo ✓ Desktop shortcut created
) else (
    echo ✓ Shortcut already exists
)

echo.
echo ================================================================
echo Step 4: Launching Application
echo ================================================================
echo.

REM Launch the application
wscript.exe "%INSTALL_DIR%\autorun\launcher.vbs"

echo.
echo ================================================================
echo Setup Complete!
echo ================================================================
echo.
echo Application installed at: %INSTALL_DIR%
echo Desktop shortcut: %SHORTCUT%
echo.
echo You can now:
echo - Click the desktop shortcut to start the app
echo - Remove the USB drive if needed
echo - Application is now installed on your computer
echo.
echo ================================================================
echo.

pause
exit /b 0
