@echo off
echo ===================================================
echo   Starting V - The AI Assistant (Initialization)
echo ===================================================

REM 1. Check Python
python --version >nul 2>&1
IF %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Python is not installed or not in your system PATH.
    pause
    exit /b
)

REM 2. Check Ollama Installation
ollama -v >nul 2>&1
IF %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Ollama is not detected on this system.
    echo V requires Ollama to run local models securely.
    echo Please download and install it from: https://ollama.com/download
    pause
    exit /b
)

REM 3. Ensure Ollama Server is Running
echo [INFO] Ensuring Ollama backend is active...
start /B ollama serve >nul 2>&1

REM 4. Pull the Required Model (Change 'llama3' to your specific model)
echo [INFO] Verifying local AI models. This may take a moment on first run...
ollama pull llama3

REM 5. Setup Environment & Run
IF NOT EXIST "venv\" (
    echo [INFO] Creating Python virtual environment...
    python -m venv venv
)
call venv\Scripts\activate
pip install -q -r requirements.txt

echo [INFO] Booting up V Backend and Frontend...
uvicorn v_backend.main:app --host 127.0.0.1 --port 8000 --reload
pause