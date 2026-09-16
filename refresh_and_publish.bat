@echo off
setlocal
cd /d "%~dp0"

echo ============================================
echo  Step 1/5: TDM EU coffee trade flow refresh
echo ============================================
echo.

python "Automator\tdm_eu_ingest.py" %*
if errorlevel 1 (
    echo.
    echo  REFRESH FAILED - see error above.
    echo  The existing parquet was left untouched. Nothing was pushed.
    pause
    exit /b 1
)

echo.
echo ============================================
echo  Step 2/5: Arabica/Robusta type-split refresh
echo  (rebuilds Brazil's ratio from Cecafe Monthly)
echo ============================================
echo.

python "Automator\build_type_split.py"
if errorlevel 1 (
    echo.
    echo  TYPE-SPLIT REFRESH FAILED - see error above.
    echo  The TDM parquet above still refreshed OK, but nothing was pushed.
    pause
    exit /b 1
)

echo.
echo ============================================
echo  Step 3/5: Validating Coffee Stocks.xlsx
echo ============================================
echo.

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
echo ============================================
echo  Step 4/5: Checking for changes
echo ============================================
echo.

git diff --quiet -- "Database\Coffee Stocks.xlsx" "Database\tdm_coffee_eu.parquet" "Database\origin_type_split.parquet"
if not errorlevel 1 (
    echo No changes detected - nothing to push.
    pause
    exit /b 0
)

echo.
echo ============================================
echo  Step 5/5: Committing and pushing to GitHub
echo ============================================
echo.

git add "Database\Coffee Stocks.xlsx" "Database\tdm_coffee_eu.parquet" "Database\origin_type_split.parquet"
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
