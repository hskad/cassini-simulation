@echo off
setlocal
python "%~dp0cassini.py" %*
exit /b %errorlevel%
