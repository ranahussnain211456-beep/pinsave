@echo off
:: ─────────────────────────────────────────────────────────────
::  PinSave – Server Stop
::  Background mein chalne wale server ko band karta hai
:: ─────────────────────────────────────────────────────────────

taskkill /f /im pythonw.exe >nul 2>&1

echo.
echo  🛑 PinSave server band ho gaya.
echo.
timeout /t 2 /nobreak >nul
