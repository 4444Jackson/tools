@echo off
setlocal EnableExtensions
title 联想电池充电档位

set "EC=%~dp0EnergyControl.exe"
set "CLI=0"
if not "%~1"=="" set "CLI=1"

if not exist "%EC%" (
  echo [错误] 找不到 EnergyControl.exe
  echo 期望位置: %EC%
  if "%CLI%"=="0" pause
  exit /b 1
)

if /i "%~1"=="status"   goto STATUS
if /i "%~1"=="storage" (set "M=storage" & goto SET)
if /i "%~1"=="normal"  (set "M=normal"  & goto SET)
if /i "%~1"=="express" (set "M=express" & goto SET)
if /i "%~1"=="quick"   (set "M=express" & goto SET)
if not "%~1"=="" goto USAGE

:MENU
cls
echo.
echo   联想电池充电档位  ^|  EnergyControl 直写 EC 固件
echo   --------------------------------------------------------------
echo   当前状态:
call :SHOW
echo.
echo    [1] Storage   养护档   上限约 55-60%%，长期插电推荐
echo    [2] Normal    标准档   充到 100%%，出门前用
echo    [3] Express   快充档
echo    [4] 刷新状态
echo    [0] 退出
echo.
set "CH="
set /p "CH=请选择: "
if "%CH%"=="1" (set "M=storage" & goto SET)
if "%CH%"=="2" (set "M=normal"  & goto SET)
if "%CH%"=="3" (set "M=express" & goto SET)
if "%CH%"=="4" goto MENU
if "%CH%"=="0" exit /b 0
echo   输入无效，请按 0-4。
timeout /t 2 >nul
goto MENU

:SET
echo.
echo   正在切换到 %M% ...
"%EC%" charge direct set %M% --apply
if errorlevel 1 (
  echo.
  echo   [切换失败] 若提示权限不足，请右键本文件选「以管理员身份运行」。
  if "%CLI%"=="0" pause
  exit /b 1
)
echo.
echo   切换后状态:
call :SHOW
echo.
if "%CLI%"=="1" exit /b 0
pause
goto MENU

:STATUS
call :SHOW
if "%CLI%"=="1" exit /b 0
echo.
pause
goto MENU

:USAGE
echo 用法: %~nx0 [storage^|normal^|express^|quick^|status]
echo   不带参数 = 交互菜单；带参数 = 直接执行，不暂停。
echo   例: %~nx0 normal   （出门前恢复充满）
echo       %~nx0 storage  （回家插电后开养护）
echo       %~nx0 status   （只查当前档位）
exit /b 1

:SHOW
"%EC%" charge direct get | findstr /i "backend protocol mode supportedModes storageEnabled quickEnabled rawFlags"
exit /b 0
