@echo off
setlocal
cd /d "%~dp0"

echo ============================================
echo  Coffee Certs and Disappearance data publish
echo ============================================
echo.

echo Step 1/3: Validating Coffee Stocks.xlsx ...
python validate_xlsx.py
if errorlevel 1 (
    echo.
    echo ============================================
    echo  VALIDATION FAILED - nothing was pushed.
    echo  Fix the issues above in "Database\Coffee Stocks.xlsx", then run this again.
    echo ============================================
    pause
    exit /b 1
)

echo.
echo Step 2/3: Checking for changes ...
git diff --quiet -- "Database\Coffee Stocks.xlsx" "Database\tdm_coffee_eu.parquet"
if not errorlevel 1 (
    echo No changes detected - nothing to push.
    pause
    exit /b 0
)

echo.
echo Step 3/3: Committing and pushing to GitHub ...
git add "Database\Coffee Stocks.xlsx" "Database\tdm_coffee_eu.parquet"
for /f "delims=" %%i in ('powershell -NoProfile -Command "Get-Date -Format \"yyyy-MM-dd HH:mm\""') do set STAMP=%%i
git commit -m "Data update %STAMP%"
if errorlevel 1 (
    echo.
    echo Commit failed - see error above.
    pause
    exit /b 1
)

git push
if errorlevel 1 (
    echo.
    echo Push failed - see error above. Your commit is still saved locally;
    echo ask for help before trying again.
    pause
    exit /b 1
)

echo.
echo ============================================
echo  Done. Streamlit Cloud will redeploy within
echo  about a minute.
echo ============================================
pause
