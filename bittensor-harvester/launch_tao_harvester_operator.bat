@echo off
setlocal
set "ROOT=%~dp0"
set "PYTHONW=%ROOT%.venv\Scripts\pythonw.exe"
set "PYTHON=%ROOT%.venv\Scripts\python.exe"

if exist "%PYTHONW%" (
    start "TAO Harvester Operator" "%PYTHONW%" -m v2.tao_harvester.operator_gui
    exit /b 0
)

if exist "%PYTHON%" (
    start "TAO Harvester Operator" "%PYTHON%" -m v2.tao_harvester.operator_gui
    exit /b 0
)

echo Could not find local virtual environment Python at:
echo   %PYTHONW%
echo or
echo   %PYTHON%
pause
exit /b 1
