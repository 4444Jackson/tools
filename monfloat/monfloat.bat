@echo off
rem MonFloat launcher: auto-detect pythonw on PATH, fall back to WorkBuddy python.
rem Needs admin (PawnIO reads sensors); self-elevates via UAC when needed.
setlocal
set "SCRIPT=%~dp0monfloat.py"
set "PY="
for /f "delims=" %%i in ('where pythonw 2^>nul') do if not defined PY set "PY=%%i"
if not defined PY set "PY=C:\Users\%USERNAME%\.workbuddy\binaries\python\versions\3.13.12\pythonw.exe"
net session >nul 2>&1
if %errorlevel% neq 0 (
    powershell -NoProfile -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
    exit /b
)
start "" "%PY%" "%SCRIPT%"
