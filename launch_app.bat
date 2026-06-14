@echo off
title Green Wall Recommender
echo Starting Green Wall Recommender...

REM Kill any previous instance on port 8501
for /f "tokens=5" %%a in ('netstat -aon ^| findstr :8501 ^| findstr LISTENING') do taskkill /PID %%a /F >nul 2>&1

REM Start Streamlit in background
start "" /B "C:\Users\ECO9\anaconda3\Scripts\streamlit.exe" run "%~dp0app\streamlit_app.py" --server.port 8501 --server.headless true

REM Wait for server to be ready
echo Waiting for server...
timeout /t 5 /nobreak >nul

REM Open in Chrome
start "" "C:\Program Files\Google\Chrome\Application\chrome.exe" http://localhost:8501

echo App is running. Close this window to STOP the server.
pause
