@echo off
setlocal enabledelayedexpansion

REM A/H Alpha System Windows launcher
REM Usage:
REM   run_alpha_windows.bat demo
REM   run_alpha_windows.bat live
REM   run_alpha_windows.bat etf
REM   run_alpha_windows.bat csv your_ah_data.csv

set MODE=%1
if "%MODE%"=="" set MODE=live

set PYTHON_BIN=python
set SCRIPT=quant_alpha_system.py
set OUT_DIR=outputs
if not exist "%OUT_DIR%" mkdir "%OUT_DIR%"

for /f %%i in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMdd_HHmmss"') do set TS=%%i
set OUT_FILE=%OUT_DIR%\portfolio_%TS%.csv
set PREV_FILE=%OUT_DIR%\latest_portfolio.csv

if /I "%MODE%"=="demo" (
  echo [INFO] Running DEMO mode...
  %PYTHON_BIN% %SCRIPT% --demo --topn 10 --save-weights "%OUT_FILE%"
  goto END
)

if /I "%MODE%"=="live" (
  echo [INFO] Running LIVE mode (online refresh default) with mainland-first providers...
  if exist "%PREV_FILE%" (
    %PYTHON_BIN% %SCRIPT% --no-db-only --providers eastmoney,tencent,yahoo,stooq --request-timeout 8 --request-retries 1 --benchmark 000300.SS --topn 20 --max-weight 0.20 --risk-aversion 0.20 --cost-penalty 0.10 --prev-weights "%PREV_FILE%" --save-weights "%OUT_FILE%"
  ) else (
    %PYTHON_BIN% %SCRIPT% --no-db-only --providers eastmoney,tencent,yahoo,stooq --request-timeout 8 --request-retries 1 --benchmark 000300.SS --topn 20 --max-weight 0.20 --risk-aversion 0.20 --cost-penalty 0.10 --save-weights "%OUT_FILE%"
  )
  goto END
)

if /I "%MODE%"=="etf" (
  echo [INFO] Running CN ETF rotation mode...
  if exist "%PREV_FILE%" (
    %PYTHON_BIN% %SCRIPT% --no-db-only --cn-etf-rotation --providers eastmoney,tencent,yahoo,stooq --request-timeout 8 --request-retries 1 --cn-etf-limit 200 --etf-live-limit 120 --benchmark 510300.SS --topn 20 --max-weight 0.20 --risk-aversion 0.20 --cost-penalty 0.12 --auto-tune-horizon-weights --prev-weights "%PREV_FILE%" --save-weights "%OUT_FILE%"
  ) else (
    %PYTHON_BIN% %SCRIPT% --no-db-only --cn-etf-rotation --providers eastmoney,tencent,yahoo,stooq --request-timeout 8 --request-retries 1 --cn-etf-limit 200 --etf-live-limit 120 --benchmark 510300.SS --topn 20 --max-weight 0.20 --risk-aversion 0.20 --cost-penalty 0.12 --auto-tune-horizon-weights --save-weights "%OUT_FILE%"
  )
  goto END
)

if /I "%MODE%"=="csv" (
  set CSV_PATH=%2
  if "%CSV_PATH%"=="" (
    echo [ERROR] Missing CSV path.
    echo Usage: run_alpha_windows.bat csv your_ah_data.csv
    exit /b 1
  )
  echo [INFO] Running CSV mode with: %CSV_PATH%
  if exist "%PREV_FILE%" (
    %PYTHON_BIN% %SCRIPT% --input-csv "%CSV_PATH%" --topn 20 --max-weight 0.20 --risk-aversion 0.20 --cost-penalty 0.10 --prev-weights "%PREV_FILE%" --save-weights "%OUT_FILE%"
  ) else (
    %PYTHON_BIN% %SCRIPT% --input-csv "%CSV_PATH%" --topn 20 --max-weight 0.20 --risk-aversion 0.20 --cost-penalty 0.10 --save-weights "%OUT_FILE%"
  )
  goto END
)

echo [ERROR] Unknown mode: %MODE%
echo Usage:
echo   run_alpha_windows.bat demo
echo   run_alpha_windows.bat live
echo   run_alpha_windows.bat etf
echo   run_alpha_windows.bat csv your_ah_data.csv
exit /b 1

:END
if errorlevel 1 (
  echo [ERROR] Strategy run failed.
  exit /b 1
)

copy /Y "%OUT_FILE%" "%PREV_FILE%" >nul
echo [INFO] Done. Portfolio saved to: %OUT_FILE%
echo [INFO] Latest portfolio updated: %PREV_FILE%
exit /b 0
