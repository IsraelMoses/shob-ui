@echo off
setlocal
cd /d "%~dp0"

if exist "%~dp0.venv\Scripts\pythonw.exe" (
    "%~dp0.venv\Scripts\pythonw.exe" "%~dp0run_shob_ui.pyw"
    exit /b %errorlevel%
)

if exist "%~dp0.venv\Scripts\python.exe" (
    "%~dp0.venv\Scripts\python.exe" "%~dp0main.py"
    exit /b %errorlevel%
)

where pyw.exe >nul 2>nul
if %errorlevel%==0 (
    pyw.exe -3 "%~dp0run_shob_ui.pyw"
    exit /b %errorlevel%
)

where pythonw.exe >nul 2>nul
if %errorlevel%==0 (
    pythonw.exe "%~dp0run_shob_ui.pyw"
    exit /b %errorlevel%
)

where py.exe >nul 2>nul
if %errorlevel%==0 (
    py.exe -3 "%~dp0main.py"
    pause
    exit /b %errorlevel%
)

python "%~dp0main.py"
pause
