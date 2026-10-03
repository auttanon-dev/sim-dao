@echo off
REM Render compiled shots with Blender headless. Pass absolute paths.
REM   cinema\render.cmd <shots.json> <out-dir> [shot_id] [--draft] [--engine=cycles]
setlocal
set BLENDER=C:\Program Files\Blender Foundation\Blender 5.2\blender.exe
set PY=C:\Users\user\AppData\Local\Programs\Python\Python312\python.exe

if "%~1"=="" (
  echo usage: cinema\render.cmd ^<shots.json^> ^<out-dir^> [shot_id] [--draft]
  exit /b 1
)

set SHOTS=%~f1
set OUTDIR=%~2
if "%OUTDIR%"=="" set OUTDIR=%~dp1renders
if not exist "%OUTDIR%" mkdir "%OUTDIR%"
set OUTDIR=%OUTDIR%

REM Any further args are passed through to render_shot.py.
shift
set EXTRA=
:collect
if not "%~1"=="" (
  set EXTRA=%EXTRA% %1
  shift
  goto collect
)

"%BLENDER%" -b --factory-startup -P "%~dp0render_shot.py" -- --shots "%SHOTS%" --out "%OUTDIR%"%EXTRA%
endlocal
