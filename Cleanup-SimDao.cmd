@echo off
chcp 65001 >nul
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0Cleanup-SimDao.ps1" %*
pause
