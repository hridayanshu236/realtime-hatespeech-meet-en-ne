@echo off
echo ==========================================
echo   Real-Time Hate Speech Detector Backend
echo ==========================================
echo.

:: Check if Python is installed
python --version >nul 2>&1
IF %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Python is not installed or not in your PATH. 
    echo Please install Python 3.10+ from python.org and try again.
    pause
    exit /b
)

:: Create Virtual Environment if it doesn't exist
IF NOT EXIST ".venv\" (
    echo [INFO] Creating Python Virtual Environment...
    python -m venv .venv
)

:: Activate Virtual Environment
call .venv\Scripts\activate

:: Install Requirements
echo [INFO] Checking dependencies...
python -m pip install --upgrade pip >nul
pip install -r requirements.txt

:: Check if model exists, download if it doesn't
IF NOT EXIST "models\xlmroberta_finetuned\pytorch_model.bin" (
    echo [INFO] Hate speech model not found locally. Starting download...
    python download_model.py
) ELSE (
    echo [INFO] Model found locally. Skipping download.
)

:: Start the server
echo.
echo [SUCCESS] Everything is ready! Starting the FastAPI server...
echo.
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000

pause
