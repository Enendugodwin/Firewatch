@echo off
rem Start FIREWATCH X: PostgreSQL, API and web.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\start_stack.ps1" %*
if errorlevel 1 pause
