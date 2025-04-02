@echo off
setlocal

:: ==== Friendly Header ====
echo --------------------------------------------
echo   Rapidbotz Bootstrapper Launcher
echo   Version 1.0
echo --------------------------------------------

:: ==== Optionally set env vars ====
:: Uncomment and fill these out if you're running in a restricted environment (e.g., VDI)
:: These override system environment variables for this session only

:: set GITHUB_PAT=your_github_pat_here
:: set GITHUB_EMAIL=your_email@yourdomain.com
:: set RAPIDBOTZ_SECRET=BZ::firstname.lastname::xxxxxxxxxxxxxxxxxxxx

:: ==== Check for Python ====
echo Checking for Python...
where python >nul 2>&1
IF %ERRORLEVEL% NEQ 0 (
    echo ERROR: Python not found! Install from python.org and add to PATH.
    pause
    exit /b 1
)

:: ==== Check for Git ====
echo Checking for Git...
where git >nul 2>&1
IF %ERRORLEVEL% NEQ 0 (
    echo ERROR: Git not found! Install from git-scm.com.
    pause
    exit /b 1
)

:: ==== Check for Java ====
echo Checking for Java...
java -version >nul 2>&1
IF %ERRORLEVEL% NEQ 0 (
    echo ERROR: Java not found! Install from java.com.
    pause
    exit /b 1
)

:: ==== Install Python dependencies from requirements.txt ====
echo Installing required Python packages...
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
IF %ERRORLEVEL% NEQ 0 (
    echo WARNING: Could not install keyring automatically. You may need to run 'pip install keyring' manually.
)

:: ==== Run the Script ====
echo.
echo Starting Rapidbotz setup...
python rapidbotz_bootstrapper.py

:: ==== Finish ====
echo.
echo Setup complete! Check above for any errors.
echo Press any key to exit.
pause