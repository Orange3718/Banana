@echo off
cd /d "%~dp0"
start "Upbit Telegram Control" ".venv\Scripts\python.exe" telegram_bot.py
