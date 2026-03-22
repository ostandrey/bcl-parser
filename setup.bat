@echo off
echo === BCL Parser Setup ===

python -m venv .venv
if errorlevel 1 (
    echo ERROR: Python not found. Install Python 3.11+ from https://python.org
    pause
    exit /b 1
)

call .venv\Scripts\activate.bat
pip install --upgrade pip
pip install -r requirements.txt

echo.
echo === Installing Playwright browsers ===
playwright install chromium

echo.
echo === Done! ===
echo To activate the environment: .venv\Scripts\activate.bat
echo To run the app:              python src/main.py
pause
