@echo off
echo Starting Arcco AI Backend...
cd /d "%~dp0"

:: Check if python is available
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo Python not found! Please install Python 3.10+
    pause
    exit /b
)

:: Install requirements if needed
if not exist "venv" (
    echo Creating virtual environment...
    python -m venv venv
)

call venv\Scripts\activate

:: Install dependencies
echo Installing dependencies...
pip install -r backend/requirements.txt

:: Start Server
echo.
echo Starting FastAPI Server on Port 8001...
echo API Docs available at http://localhost:8001/docs
echo.
uvicorn backend.main:app --host 0.0.0.0 --port 8001 --reload

pause
