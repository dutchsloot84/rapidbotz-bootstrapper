@echo off
setlocal

:: ==== Friendly Header ====
echo --------------------------------------------
echo   Rapidbotz Bootstrapper Launcher
echo   Version 1.0
echo --------------------------------------------

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

:: ==== Install keyring if not present ====
echo Ensuring keyring library is installed...
python -m pip install keyring --quiet
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