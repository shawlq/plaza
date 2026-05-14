@echo off
setlocal
cd /d "%~dp0"
python -m pip install PySide6 opencv-python numpy fastapi "uvicorn[standard]"
python winapp.py
