@echo off
setlocal
set SCRIPT_DIR=%~dp0
set SCRIPT_PATH=%SCRIPT_DIR%bridge_bot.py

echo Registering ReadEra Telegram Bridge Bot as a Windows Task Scheduler service (runs hidden at logon)...
schtasks /create /tn "ReadEraBridgeBot" /tr "pythonw.exe \"%SCRIPT_PATH%\"" /sc onlogon /rl HIGHEST /f

if %ERRORLEVEL% EQU 0 (
    echo [SUCCESS] Task "ReadEraBridgeBot" created successfully!
    echo It will automatically start silently in the background when you log on.
) else (
    echo [ERROR] Failed to register task. Make sure you run this script as Administrator.
)
pause
