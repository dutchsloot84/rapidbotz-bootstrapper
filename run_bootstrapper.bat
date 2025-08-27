@echo off
setlocal
set "SCRIPT_DIR=%~dp0"
cd /d "%SCRIPT_DIR%"

rem ===== Friendly, minimal banner =====
echo Rapidbotz Bootstrapper
echo.

rem ===== timestamped log (support) =====
for /f %%i in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMdd-HHmmss"') do set "RBZ_TS=%%i"
if not exist "logs" mkdir "logs" >nul 2>&1
set "RBZ_LOG=logs\launcher-%RBZ_TS%.log"
> "%RBZ_LOG%" echo Rapidbotz bootstrapper log %RBZ_TS%

set "PY_DIR=python"
set "PY_EXE=%PY_DIR%\python.exe"
set "PY_ZIP=python-3.13.2-embed-amd64.zip"
set "PTH_FILE=%PY_DIR%\python313._pth"
set "WHEELS_DIR=wheels"
set "REQS=requirements.txt"

echo - Preparing Python...
if not exist "%PY_EXE%" (
  mkdir "%PY_DIR%" >nul 2>&1
  powershell -NoProfile -Command "Expand-Archive -Path '%PY_ZIP%' -DestinationPath '%PY_DIR%' -Force" >>"%RBZ_LOG%" 2>&1
  if errorlevel 1 (
    echo ERROR: Failed to extract embedded Python. See %RBZ_LOG%
    exit /b 1
  )
)

rem ---- Ensure stdlib zip (python3*.zip), '.' and '..', and 'import site' in _pth
call :fix_pth >>"%RBZ_LOG%" 2>&1
if errorlevel 1 (
  echo ERROR: Unable to configure python313._pth. See %RBZ_LOG%
  exit /b 1
)

echo - Ensuring pip...
call :clean_broken_pip >>"%RBZ_LOG%" 2>&1
call :ensure_pip >>"%RBZ_LOG%" 2>&1
if errorlevel 1 (
  echo ERROR: pip is not available. See %RBZ_LOG%
  exit /b 1
)

echo - Installing dependencies...
call :install_deps_offline_first >>"%RBZ_LOG%" 2>&1
if errorlevel 1 (
  echo ERROR: Failed to install dependencies. See %RBZ_LOG%
  exit /b 1
)

echo - Running setup...
rem make repo root importable (so rbz/ resolves)
set "PYTHONPATH=%CD%;%PYTHONPATH%"
"%PY_EXE%" rapidbotz_bootstrapper.py >>"%RBZ_LOG%" 2>&1
if errorlevel 1 (
  echo ERROR: Setup failed. See %RBZ_LOG%
  exit /b 1
)

echo Success.
echo Log: %RBZ_LOG%
exit /b 0


:: =========================
:: Helpers
:: =========================
:fix_pth
setlocal ENABLEDELAYEDEXPANSION
if not exist "%PTH_FILE%" (
  echo [%date% %time%] creating %PTH_FILE%
  set "ZIP_FOUND="
  for %%Z in ("%PY_DIR%\python3*.zip") do ( set "ZIP_FOUND=%%~nxZ" & goto :zip_found )
  :zip_found
  if not defined ZIP_FOUND (
    echo [%date% %time%] ERROR: stdlib zip not found in %PY_DIR%
    endlocal & exit /b 1
  )
  (
    echo !ZIP_FOUND!
    echo .
    echo ..
    echo import site
  ) > "%PTH_FILE%"
  endlocal & exit /b 0
)

set "HAS_ZIP=0" & set "HAS_DOT=0" & set "HAS_DOTDOT=0" & set "HAS_SITE=0"
for /f "usebackq tokens=* delims=" %%L in ("%PTH_FILE%") do (
  set "line=%%L"
  if /i "!line!"=="." set "HAS_DOT=1"
  if /i "!line!"==".." set "HAS_DOTDOT=1"
  if /i "!line!"=="import site" set "HAS_SITE=1"
  echo !line!| findstr /i /r "^python3[0-9][0-9]*\.zip$" >nul && set "HAS_ZIP=1"
)
if not "!HAS_ZIP!"=="1" (
  set "ZIP_FOUND="
  for %%Z in ("%PY_DIR%\python3*.zip") do ( set "ZIP_FOUND=%%~nxZ" & goto :zip2 )
  :zip2
  if not defined ZIP_FOUND (
    echo [%date% %time%] ERROR: stdlib zip not found in %PY_DIR%
    endlocal & exit /b 1
  )
  >>"%PTH_FILE%" echo !ZIP_FOUND!
)
if not "!HAS_DOT!"=="1"    >>"%PTH_FILE%" echo .
if not "!HAS_DOTDOT!"=="1" >>"%PTH_FILE%" echo ..
if not "!HAS_SITE!"=="1"   >>"%PTH_FILE%" echo import site
endlocal & exit /b 0

:clean_broken_pip
if exist "%PY_DIR%\Lib\site-packages\pip" rmdir /s /q "%PY_DIR%\Lib\site-packages\pip"
for /d %%D in ("%PY_DIR%\Lib\site-packages\pip-*.dist-info") do rmdir /s /q "%%~fD"
del /q "%PY_DIR%\Scripts\pip*.exe" >nul 2>&1
exit /b 0

:ensure_pip
"%PY_EXE%" -m pip --version >nul 2>&1 && exit /b 0
if not exist get-pip.py (
  echo [%date% %time%] ERROR: get-pip.py not found in %CD%
  exit /b 1
)
"%PY_EXE%" get-pip.py --no-warn-script-location
if errorlevel 1 (
  "%PY_EXE%" -m pip install --force-reinstall --no-deps pip==25.0.1 --no-warn-script-location
)
"%PY_EXE%" -m pip --version >nul 2>&1 || exit /b 1
exit /b 0

:install_deps_offline_first
setlocal ENABLEDELAYEDEXPANSION
set "DO_OFFLINE=0"
if exist "%WHEELS_DIR%" dir /b "%WHEELS_DIR%\*.whl" >nul 2>&1 && set "DO_OFFLINE=1"

if "%DO_OFFLINE%"=="1" (
  echo Looking in links: %WHEELS_DIR%
  "%PY_EXE%" -m pip install --no-index --find-links="%WHEELS_DIR%" --upgrade pip --no-warn-script-location || (endlocal & exit /b 1)
  if exist "%REQS%" (
    "%PY_EXE%" -m pip install --no-index --find-links="%WHEELS_DIR%" -r "%REQS%" --no-warn-script-location || (endlocal & exit /b 1)
  ) else (
    set "PKGS="
    for %%F in ("%WHEELS_DIR%\*.whl") do set "PKGS=!PKGS! "%%~fF""
    if not defined PKGS (
      echo [%date% %time%] ERROR: No .whl files in "%WHEELS_DIR%"
      endlocal & exit /b 1
    )
    "%PY_EXE%" -m pip install --no-index --find-links="%WHEELS_DIR%" !PKGS! --no-warn-script-location || (endlocal & exit /b 1)
  )
  endlocal & exit /b 0
)

if exist "%REQS%" (
  "%PY_EXE%" -m pip install -r "%REQS%" --no-warn-script-location || (endlocal & exit /b 1)
) else (
  "%PY_EXE%" -m pip install requests --no-warn-script-location || (endlocal & exit /b 1)
)
endlocal & exit /b 0
