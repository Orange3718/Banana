@echo off
cd /d "%~dp0"
start "Upbit Dashboard" ".venv\Scripts\python.exe" -m streamlit run app.py --server.address 127.0.0.1 --server.port 8501 --server.headless true
start "Upbit Trading Worker" ".venv\Scripts\python.exe" main.py
start "Upbit Telegram Control" ".venv\Scripts\python.exe" telegram_bot.py
timeout /t 3 /nobreak > nul
start "" "http://127.0.0.1:8501"
