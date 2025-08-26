@echo off
setlocal
echo Rapidbotz Bootstrapper

:: timestamped log
for /f %%i in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMdd-HHmmss"') do set TIMESTAMP=%%i
set "LOGFILE=bootstrapper-%TIMESTAMP%.log"
echo Logging to %LOGFILE%
> "%LOGFILE%" echo Rapidbotz bootstrapper log %TIMESTAMP%

set "PY=python\python.exe"

:: extract embedded Python if missing
if not exist "%PY%" (
  echo Extracting embedded Python...
  mkdir python >nul 2>&1
  powershell -NoProfile -Command "Expand-Archive -Path 'python-3.13.2-embed-amd64.zip' -DestinationPath 'python' -Force" >>"%LOGFILE%" 2>&1
  if errorlevel 1 (
    echo Failed to extract Python. See %LOGFILE%
    exit /b 1
  )
)

:: ensure python._pth enables site and stdlib zip
set "PYZIP=python313.zip"
(
  echo %PYZIP%
  echo .
  echo import site
)>python\python._pth

:: ensure pip is available
%PY% -m pip --version >>"%LOGFILE%" 2>&1
if errorlevel 1 (
  call :clean_broken_pip
  echo Installing pip...
  %PY% get-pip.py >>"%LOGFILE%" 2>&1
  if errorlevel 1 (
    echo Failed to install pip. See %LOGFILE%
    exit /b 1
  )
)

:: install dependencies (prefer wheels\*.whl)
echo Installing dependencies...
set HAS_WHEELS=
for %%F in (wheels\*.whl) do set HAS_WHEELS=1
if defined HAS_WHEELS (
  echo Using local wheels >>"%LOGFILE%"
  %PY% -m pip install --no-index --find-links=wheels wheels\*.whl >>"%LOGFILE%" 2>&1
) else (
  echo Using requirements.txt >>"%LOGFILE%"
  %PY% -m pip install -r requirements.txt >>"%LOGFILE%" 2>&1
)
if errorlevel 1 (
  echo Failed to install dependencies. See %LOGFILE%
  exit /b 1
)

:: run bootstrapper
echo Running bootstrapper...
%PY% rapidbotz_bootstrapper.py >>"%LOGFILE%" 2>&1
if errorlevel 1 (
  echo Bootstrapper failed. See %LOGFILE%
  exit /b 1
)

echo Done. See %LOGFILE% for details.
exit /b 0

:clean_broken_pip
for /d %%D in ("python\Lib\site-packages\pip*") do (
  rmdir /s /q "%%~fD" >>"%LOGFILE%" 2>&1
)
del /q python\Scripts\pip*.exe >nul 2>&1
exit /b 0
