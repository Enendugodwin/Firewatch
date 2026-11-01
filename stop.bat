@echo off
rem Stop FIREWATCH X. Use "stop.bat -KeepDatabase" to leave PostgreSQL running.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\stop_stack.ps1" %*
if errorlevel 1 pause
