@echo off
setlocal
cd /d "%~dp0"

if "%AUTOMATION_CONTROL_TOKEN%"=="" (
  for /f "usebackq tokens=*" %%A in (`powershell -NoProfile -Command "[Environment]::GetEnvironmentVariable('AUTOMATION_CONTROL_TOKEN','User')"`) do set "AUTOMATION_CONTROL_TOKEN=%%A"
)
if "%AUTOMATION_CONTROL_TOKEN%"=="" (
  for /f "usebackq tokens=*" %%A in (`powershell -NoProfile -Command "[Environment]::GetEnvironmentVariable('AUTOMATION_CONTROL_TOKEN','Machine')"`) do set "AUTOMATION_CONTROL_TOKEN=%%A"
)
if "%AUTOMATION_CONTROL_TOKEN%"=="" (
  for /f "usebackq tokens=*" %%A in (`powershell -NoProfile -Command "[Environment]::GetEnvironmentVariable('AUTOMATION_STATUS_TOKEN','User')"`) do set "AUTOMATION_CONTROL_TOKEN=%%A"
)
if "%AUTOMATION_CONTROL_TOKEN%"=="" (
  for /f "usebackq tokens=*" %%A in (`powershell -NoProfile -Command "[Environment]::GetEnvironmentVariable('AUTOMATION_STATUS_TOKEN','Machine')"`) do set "AUTOMATION_CONTROL_TOKEN=%%A"
)

if "%AUTOMATION_CONTROL_TOKEN%"=="" (
  echo ERROR: Set AUTOMATION_CONTROL_TOKEN or AUTOMATION_STATUS_TOKEN before starting the control agent.
  exit /b 1
)

set "CONTROL_AGENT_DEPS=%LOCALAPPDATA%\ACTAutomationControlAgent\deps"
if not exist "%CONTROL_AGENT_DEPS%\flask\__init__.py" (
  echo Installing control agent dependencies...
  python -m pip install --target "%CONTROL_AGENT_DEPS%" -r requirements.txt
  if errorlevel 1 exit /b 1
)
set "PYTHONPATH=%CONTROL_AGENT_DEPS%;%PYTHONPATH%"

python automation_control_agent.py
