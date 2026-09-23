@echo off
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0Compare-StoryModels.ps1"
if errorlevel 1 pause
