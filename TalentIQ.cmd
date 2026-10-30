@echo off
cd /d "%~dp0"
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0Start-TalentIQ.ps1" -OpenBrowser
if errorlevel 1 pause
