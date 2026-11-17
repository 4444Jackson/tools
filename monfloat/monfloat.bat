@echo off
rem MonFloat launcher: pinned to the working WorkBuddy pythonw.
rem The first pythonw on PATH is a broken 3.13.12.old copy (missing encodings), so PATH lookup is skipped.
rem Needs admin (PawnIO reads sensors); self-elevates via UAC when needed.
setlocal
set "SCRIPT=%~dp0monfloat.py"
set "PY=C:\Users\%USERNAME%\.workbuddy\binaries\python\versions\3.13.12\pythonw.exe"
if not exist "%PY%" (
  echo [error] pythonw not found: %PY%
  pause
  exit /b 1
)
net session >nul 2>&1
if %errorlevel% neq 0 (
    powershell -NoProfile -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
    exit /b
)
start "" "%PY%" "%SCRIPT%"
