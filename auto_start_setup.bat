@echo off
:: ─────────────────────────────────────────────────────────────
::  PinSave – Windows Startup mein Add karo
::  Computer start hote hi server automatically chalega
::  IMPORTANT: Pehli baar ADMINISTRATOR ki tarah run karo
:: ─────────────────────────────────────────────────────────────

set STARTUP_FOLDER=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup
set SCRIPT_PATH=%~dp0start_server.bat

:: Startup folder mein shortcut copy karo
copy "%SCRIPT_PATH%" "%STARTUP_FOLDER%\PinSave_Server.bat" /Y

if %errorlevel% == 0 (
    echo.
    echo  ✅ Setup complete!
    echo  🔄 Ab Windows start hote hi server automatically chalega
    echo  📁 Startup folder: %STARTUP_FOLDER%
    echo.
    echo  Ab start_server.bat chalao server abhi shuru karne ke liye.
    echo.
) else (
    echo.
    echo  ❌ Error! Kripya is file ko Right-Click karke
    echo     "Run as Administrator" se chalao.
    echo.
)

timeout /t 5 /nobreak >nul
