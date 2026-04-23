@echo off
:: ─────────────────────────────────────────────────────────────
::  PinSave – Background Server Launcher
::  Yeh file server.py ko silently background mein chalata hai
::  Terminal band hone ke baad bhi server chalta rehta hai
:: ─────────────────────────────────────────────────────────────

:: Server pehle se chal raha hai toh band karo (fresh restart)
taskkill /f /im pythonw.exe >nul 2>&1

:: 1 second wait
timeout /t 1 /nobreak >nul

:: server.py ko pythonw se chalao (koi window nahi khulegi)
:: IMPORTANT: Yahan apna sahi path likho
start "" /B pythonw "%~dp0server.py"

:: Confirm message
echo.
echo  ✅ PinSave server background mein start ho gaya!
echo  🌐 URL: http://localhost:5000
echo  ❌ Band karna ho toh: stop_server.bat chalao
echo.
timeout /t 3 /nobreak >nul
