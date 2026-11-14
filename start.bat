@echo off
set "ROOT=%~dp0"
start "RECURSION backend" /D "%ROOT%backend" cmd /k ".venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000"
start "RECURSION frontend" /D "%ROOT%frontend" cmd /k "npm run dev"
ping -n 4 127.0.0.1 >nul
start "" http://localhost:5173
