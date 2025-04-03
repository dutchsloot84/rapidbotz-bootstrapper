@echo off
setlocal

:: ==== Friendly Header ====
echo --------------------------------------------
echo   Rapidbotz Bootstrapper Launcher
echo   Version 1.0 (Embedded Python Mode)
echo --------------------------------------------

:: ==== Optionally set env vars ====
:: Uncomment and fill these out if you're running in a restricted environment (e.g., VDI)
:: These override system environment variables for this session only

:: set GITHUB_PAT=your_github_pat_here
:: set GITHUB_EMAIL=your_email@yourdomain.com
:: set RAPIDBOTZ_SECRET=BZ::firstname.lastname::xxxxxxxxxxxxxxxxxxxx

:: ==== Extract Embedded Python (if needed) ====
IF NOT EXIST python\python.exe (
    echo Extracting embedded Python...
    mkdir python >nul 2>&1
    tar -xf python-3.13.2-embed-amd64.zip -C python
)

:: ==== Install pip (if needed) ====
IF NOT EXIST python\Scripts\pip.exe (
    echo Installing pip into embedded Python...
    if EXIST get-pip.py (
        python\python.exe get-pip.py
    ) else (
        echo ERROR: get-pip.py is missing! Please make sure it's in this folder.
        pause
        exit /b 1
    )
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

:: ==== Install Python dependencies ====
echo Installing required Python packages...
python\python.exe -m pip install --upgrade pip
python\python.exe -m pip install -r requirements.txt
IF %ERRORLEVEL% NEQ 0 (
    echo WARNING: Could not install packages automatically. You may need to check requirements.txt manually.
)

:: ==== Run the Script ====
echo.
echo Starting Rapidbotz setup...
python\python.exe rapidbotz_bootstrapper.py

:: ==== Finish ====
echo.
echo Setup complete! Check above for any errors.
echo Press any key to exit.
pause
