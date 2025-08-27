@echo off
setlocal
set "SCRIPT_DIR=%~dp0"
cd /d "%SCRIPT_DIR%"
echo Rapidbotz Bootstrapper

:: timestamped log
for /f %%i in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMdd-HHmmss"') do set TIMESTAMP=%%i
set "LOGFILE=bootstrapper-%TIMESTAMP%.log"
echo Logging to %LOGFILE%
> "%LOGFILE%" echo Rapidbotz bootstrapper log %TIMESTAMP%

set "PY_DIR=python"
set "PY_EXE=%PY_DIR%\python.exe"
set "WHEELS_DIR=wheels"
set "REQS=requirements.txt"

:: extract embedded Python if missing
if not exist "%PY_EXE%" (
  echo Extracting embedded Python...
  mkdir "%PY_DIR%" >nul 2>&1
  powershell -NoProfile -Command "Expand-Archive -Path 'python-3.13.2-embed-amd64.zip' -DestinationPath '%PY_DIR%' -Force" >>"%LOGFILE%" 2>&1
  if errorlevel 1 (
    echo Failed to extract Python. See log: %LOGFILE%
    exit /b 1
  )
)

:: ensure python._pth enables site and stdlib zip
set "PYZIP=python313.zip"
(
  echo %PYZIP%
  echo %SCRIPT_DIR%
  echo .
  echo import site
)>"%PY_DIR%\python._pth"

:: ensure pip is available
"%PY_EXE%" -m pip --version >>"%LOGFILE%" 2>&1
if errorlevel 1 (
  call :clean_broken_pip
  echo Installing pip...
  "%PY_EXE%" get-pip.py >>"%LOGFILE%" 2>&1
  if errorlevel 1 (
    echo Failed to install pip. See log: %LOGFILE%
    exit /b 1
  )
)

:: install dependencies (prefer local wheels)
echo Installing dependencies...
call :install_deps_offline_first
if errorlevel 1 (
  echo Failed to install dependencies. See log: %LOGFILE%
  exit /b 1
)

:: run bootstrapper
echo Running bootstrapper...
set "PYTHONPATH=%SCRIPT_DIR%;%PYTHONPATH%"
"%PY_EXE%" rapidbotz_bootstrapper.py >>"%LOGFILE%" 2>&1
if errorlevel 1 (
  echo Bootstrapper failed. See log: %LOGFILE%
  exit /b 1
)

echo Done. See %LOGFILE% for details.
exit /b 0

:install_deps_offline_first
setlocal ENABLEDELAYEDEXPANSION
set "DO_OFFLINE=0"
if exist "%WHEELS_DIR%" (
  dir /b "%WHEELS_DIR%\*.whl" >nul 2>&1 && set "DO_OFFLINE=1"
)
if "!DO_OFFLINE!"=="1" (
  echo Using local wheels
  if exist "%REQS%" (
    "%PY_EXE%" -m pip install --no-index --find-links="%WHEELS_DIR%" -r "%REQS%" --no-warn-script-location >>"%LOGFILE%" 2>&1
    if errorlevel 1 (endlocal & exit /b 1)
  ) else (
    rem Expand the wheel list ourselves (pip does not expand *.whl in .bat)
    set "PKGS="
    for %%F in ("%WHEELS_DIR%\*.whl") do (
      set "PKGS=!PKGS! \"%%~fF\""
    )
    if not defined PKGS (
      echo ERROR: No .whl files found in "%WHEELS_DIR%".
      endlocal & exit /b 1
    )
    "%PY_EXE%" -m pip install --no-index --find-links="%WHEELS_DIR%" !PKGS! --no-warn-script-location >>"%LOGFILE%" 2>&1
    if errorlevel 1 (endlocal & exit /b 1)
  )
) else if exist "%REQS%" (
  "%PY_EXE%" -m pip install -r "%REQS%" --no-warn-script-location >>"%LOGFILE%" 2>&1
  if errorlevel 1 (endlocal & exit /b 1)
) else (
  echo No requirements.txt found; skipping dependency install >>"%LOGFILE%"
)
endlocal & exit /b 0

:clean_broken_pip
for /d %%D in ("%PY_DIR%\Lib\site-packages\pip-*.dist-info") do rmdir /s /q "%%~fD" >>"%LOGFILE%" 2>&1
del /q "%PY_DIR%\Scripts\pip*.exe" >nul 2>&1
exit /b 0
