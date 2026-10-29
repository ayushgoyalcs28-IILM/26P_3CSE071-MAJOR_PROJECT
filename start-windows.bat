@echo off
setlocal
title VaultChain Frontend Demo
cd /d "%~dp0"
where node >nul 2>nul
if errorlevel 1 (
  echo [VaultChain] Node.js is not installed.
  echo Download a current LTS version from https://nodejs.org/
  pause
  exit /b 1
)
if not exist node_modules\ (
  echo [VaultChain] Installing dependencies. Internet connection required on first run.
  call npm.cmd install
  if errorlevel 1 (
    echo [VaultChain] Dependency installation failed. Check your internet connection.
    pause
    exit /b 1
  )
)
echo [VaultChain] Starting the demo server...
call npm.cmd run dev
pause
