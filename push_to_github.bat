@echo off
setlocal
rem Prefer the PowerShell 7 bundled with Codex (same as D:\Personal Plan\push_to_github.bat), else Windows PowerShell
set "BLING_PS=%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe"
if exist "%USERPROFILE%\.cache\codex-runtimes\codex-primary-runtime\dependencies\native\powershell\pwsh.exe" set "BLING_PS=%USERPROFILE%\.cache\codex-runtimes\codex-primary-runtime\dependencies\native\powershell\pwsh.exe"
"%BLING_PS%" -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0push_to_github.ps1" %*
set "BLING_RESULT=%ERRORLEVEL%"
pause
exit /b %BLING_RESULT%
