@echo off
title Traffix - Flask Server
cd /d "%~dp0"

echo Installing dependencies if needed...
pip install -q -r requirements.txt

echo.
echo Starting Traffix at http://127.0.0.1:5000
echo Open that address in your browser. Keep this window open.
echo Press Ctrl+C to stop the server.
echo.

python app.py

pause
