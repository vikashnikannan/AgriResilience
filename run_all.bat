@echo off
rem Runs the whole project (creates .venv on first use). Extra options are passed on, e.g.  run_all.bat --ee
cd /d "%~dp0"
where py >nul 2>nul && (set PYCMD=py -3) || (set PYCMD=python)
%PYCMD% run_all.py %*
if errorlevel 1 pause
