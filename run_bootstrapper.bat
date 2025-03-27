@echo off
setlocal

:: ==== Friendly Header ====
echo -------------------------------------------
echo   Rapidbotz Bootstrapper Launcher
echo -------------------------------------------

:: ==== Check for Python ====
where python >nul 2>&1
IF %ERRORLEVEL% NEQ 0 (
    echo ERROR: Python is not installed or not in PATH.
    pause
    exit /b 1
)

:: ==== Optionally set env vars ====
:: Uncomment the lines below to predefine access keys (optional for advanced users)
:: set GITHUB_PAT=your_token_here
:: set GITHUB_EMAIL=your_email@example.com

:: ==== Run the script ====
echo Running bootstrapper script...
python rapidbotz_bootstrapper.py

:: ==== Finish ====
echo.
echo Script execution finished.
pause
