@echo off
setlocal
rem Use the local PowerShell 7 bundled with Codex; fall back to Windows PowerShell only if it is missing.
set "BLING_PS=C:\Users\sbing\.cache\codex-runtimes\codex-primary-runtime\dependencies\native\powershell\pwsh.exe"
if not exist "%BLING_PS%" set "BLING_PS=%USERPROFILE%\.cache\codex-runtimes\codex-primary-runtime\dependencies\native\powershell\pwsh.exe"
if not exist "%BLING_PS%" set "BLING_PS=%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe"
"%BLING_PS%" -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0push_to_github.ps1" %*
set "BLING_RESULT=%ERRORLEVEL%"
pause
exit /b %BLING_RESULT%
