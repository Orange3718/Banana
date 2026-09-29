@echo off
cd /d "%~dp0"
start "Upbit Trading Worker" ".venv\Scripts\python.exe" main.py
