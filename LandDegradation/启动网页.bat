@echo off
cd /d "%~dp0\.."
start "LandDegradation Web" python ".\LandDegradation\web_app.py"
timeout /t 2 >nul
start "" "http://127.0.0.1:8765/"
