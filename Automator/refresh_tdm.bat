@echo off
setlocal
cd /d "%~dp0"

echo ============================================
echo  TDM EU coffee trade flow refresh
echo ============================================
echo.

python tdm_eu_ingest.py %*
if errorlevel 1 (
    echo.
    echo  REFRESH FAILED - see error above.
    echo  The existing parquet was left untouched.
    pause
    exit /b 1
)

echo.
echo  Done. Review the numbers, then run publish_update.bat
echo  (one level up) to push Database\ to Streamlit Cloud.
pause
