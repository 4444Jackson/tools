@echo off
setlocal
set "SCRIPT=%~dp0FnLockEC.py"
set "PY="
for /f "delims=" %%i in ('where python 2^>nul') do if not defined PY set "PY=%%i"
if not defined PY set "PY=C:\Users\%USERNAME%\.workbuddy\binaries\python\versions\3.13.12\python.exe"
if not "%~1"=="" (
    "%PY%" "%SCRIPT%" %~1
    goto :eof
)
:menu
set "ST1="
set "ST2="
for /f "usebackq delims=" %%a in (`%PY% %SCRIPT% batstatus`) do (
  if not defined ST1 (set "ST1=%%a") else set "ST2=%%a"
)
echo.
echo === Lenovo Fn Lock ==========================
echo   当前 %ST1%
echo   快捷键 %ST2%
echo ---------------------------------------------
echo  [1] Fn Lock 切换
echo  [2] 快捷键监听 开/关
echo  [3] 重设快捷键    (现场按下想要的组合键)
echo  [0] exit
choice /c 1230 /n /m "请选择: "
if errorlevel 4 goto :eof
if errorlevel 3 ("%PY%" "%SCRIPT%" hotkey-set)
if errorlevel 2 ("%PY%" "%SCRIPT%" hotkey-toggle)
if errorlevel 1 ("%PY%" "%SCRIPT%" toggle)
echo.
pause
goto :menu
