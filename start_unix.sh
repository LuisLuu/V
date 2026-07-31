#!/bin/bash

echo "==================================================="
echo "  Starting V - The AI Assistant (Initialization)"
echo "==================================================="

# 1. Check Python
if ! command -v python3 &> /dev/null; then
    echo "[ERROR] Python3 is not installed."
    exit 1
fi

# 2. Check & Auto-Install Ollama
if ! command -v ollama &> /dev/null; then
    echo "[WARNING] Ollama is not installed."
    echo "[INFO] Automatically fetching the Ollama installation script..."
    curl -fsSL https://ollama.com/install.sh | sh
fi

# 3. Ensure Server is Running
echo "[INFO] Waking up the Ollama server..."
if ! curl -s http://localhost:11434/api/tags > /dev/null; then
    ollama serve &
    sleep 3 # Give the server a few seconds to breathe
fi

# 4. Pull the Required Model (Change 'llama3' to your specific model)
echo "[INFO] Pre-fetching required AI model..."
ollama pull llama3

# 5. Setup Environment & Run
if [ ! -d "venv" ]; then
    echo "[INFO] Creating Python virtual environment..."
    python3 -m venv venv
fi
source venv/bin/activate
pip install -q -r requirements.txt

echo "[INFO] Booting up V Backend and Frontend..."
uvicorn v_backend.main:app --host 127.0.0.1 --port 8000 --reload