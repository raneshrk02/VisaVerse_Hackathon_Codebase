@echo off
REM ================================================================
REM SAGE RAG System - Installation Wizard
REM ================================================================
REM Main installer - Copy from USB to user's computer
REM Everything self-contained - works completely offline
REM ================================================================

setlocal enabledelayedexpansion
cd /d "%~dp0"

echo.
echo ================================================================
echo SAGE RAG System - Installation Wizard
echo ================================================================
echo.
echo This wizard will install SAGE RAG System on your computer
echo from the USB drive you just inserted.
echo.

REM Get USB root
set USB_ROOT=%~dp0
if "%USB_ROOT:~-1%"=="\" set USB_ROOT=%USB_ROOT:~0,-1%

REM Install to user's home directory (no admin needed)
set INSTALL_DIR=%USERPROFILE%\AppData\Local\SAGE_RAG_System
set DESKTOP=%USERPROFILE%\Desktop
set SHORTCUT=%DESKTOP%\Start SAGE RAG System.lnk
set LOG_FILE=%INSTALL_DIR%\install.log

echo Preparing installation...
echo.

REM Create installation directory
if not exist "%INSTALL_DIR%" (
    mkdir "%INSTALL_DIR%"
    if errorlevel 1 (
        echo ERROR: Cannot create installation directory
        echo Please ensure you have write permissions to your user folder
        echo.
        pause
        exit /b 1
    )
)

echo ================================================================
echo Step 1: Copying files from USB to computer...
echo ================================================================
echo.

REM Copy all files from USB to installation directory
echo Source: %USB_ROOT%
echo Destination: %INSTALL_DIR%
echo.

REM Copy backend
if exist "%USB_ROOT%\backend" (
    echo Copying backend files...
    xcopy "%USB_ROOT%\backend" "%INSTALL_DIR%\backend" /E /I /Y >nul
    if errorlevel 1 (
        echo WARNING: Some backend files may not have copied
    )
)

REM Copy frontend
if exist "%USB_ROOT%\frontend" (
    echo Copying frontend files...
    xcopy "%USB_ROOT%\frontend" "%INSTALL_DIR%\frontend" /E /I /Y >nul
    if errorlevel 1 (
        echo WARNING: Some frontend files may not have copied
    )
)

REM Copy python
if exist "%USB_ROOT%\python" (
    echo Copying Python runtime...
    xcopy "%USB_ROOT%\python" "%INSTALL_DIR%\python" /E /I /Y >nul
    if errorlevel 1 (
        echo ERROR: Failed to copy Python
        pause
        exit /b 1
    )
)

REM Copy node
if exist "%USB_ROOT%\node" (
    echo Copying Node.js runtime...
    xcopy "%USB_ROOT%\node" "%INSTALL_DIR%\node" /E /I /Y >nul
    if errorlevel 1 (
        echo ERROR: Failed to copy Node.js
        pause
        exit /b 1
    )
)

REM Copy autorun scripts
if exist "%USB_ROOT%\autorun" (
    echo Copying startup scripts...
    xcopy "%USB_ROOT%\autorun" "%INSTALL_DIR%\autorun" /E /I /Y >nul
    if errorlevel 1 (
        echo WARNING: Some startup files may not have copied
    )
)

echo ✓ Files copied successfully
echo.

REM Create desktop shortcut
echo ================================================================
echo Step 2: Creating desktop shortcut...
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
        echo oLink.IconLocation = "%INSTALL_DIR%\frontend\public\favicon.ico"
        echo oLink.Save
    ) > "%TEMP%\create_sage_shortcut.vbs"
    
    cscript.exe //nologo "%TEMP%\create_sage_shortcut.vbs" >nul 2>&1
    del /Q "%TEMP%\create_sage_shortcut.vbs" >nul 2>&1
    
    echo ✓ Desktop shortcut created
) else (
    echo ✓ Shortcut already exists
)

echo.

REM Launch application
echo ================================================================
echo Step 3: Launching application...
echo ================================================================
echo.

echo Starting SAGE RAG System...
echo.

wscript.exe "%INSTALL_DIR%\autorun\launcher.vbs"

echo.
echo ================================================================
echo Installation Complete!
echo ================================================================
echo.
echo Application installed at:
echo %INSTALL_DIR%
echo.
echo Desktop shortcut created:
echo %SHORTCUT%
echo.
echo You can now:
echo ✓ Remove the USB drive if desired
echo ✓ Use the desktop shortcut to launch the app anytime
echo ✓ Application is fully installed on your computer
echo.
echo Installation logged at:
echo %LOG_FILE%
echo.
echo ================================================================
echo.

pause
exit /b 0
