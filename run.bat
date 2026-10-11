@echo off
title OmniPost - Social Media Auto Publisher
echo ========================================================
echo        OmniPost - Multi-Platform Scheduler & AI
echo ========================================================
echo Starting server at http://127.0.0.1:8000 ...
start http://127.0.0.1:8000
.venv\Scripts\uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
pause
