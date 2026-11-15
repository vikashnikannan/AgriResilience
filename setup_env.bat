@echo off
rem Creates the project-only environment (.venv inside this folder) and installs everything.
cd /d "%~dp0"
where py >nul 2>nul && (set PYCMD=py -3) || (set PYCMD=python)
if exist .venv\Scripts\python.exe (echo .venv already exists. Use run_all.bat to run.& goto :eof)
%PYCMD% -m venv .venv || (echo Could not create the environment. Install Python 3.10+ from python.org and tick "Add Python to PATH".& pause & exit /b 1)
.venv\Scripts\python.exe -m pip install --upgrade pip
.venv\Scripts\python.exe -m pip install -r requirements.txt
echo.
echo Environment ready. Now double-click run_all.bat
pause
