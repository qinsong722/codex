@echo off
setlocal

set "NODE_HOME=C:\Users\qinso\AppData\Roaming\fnm\node-versions\v24.14.0\installation"
set "PATH=%NODE_HOME%;%PATH%"

cd /d "%~dp0"

call npm.cmd run build
if errorlevel 1 (
  echo Build failed.
  pause
  exit /b 1
)

call npm.cmd run electron

endlocal
