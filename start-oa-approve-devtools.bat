@echo off
setlocal
pushd "%~dp0"

set "CHROME_EXE=C:\Program Files\Google\Chrome\Application\chrome.exe"
if not exist "%CHROME_EXE%" set "CHROME_EXE=C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"
set "CHROME_PROFILE=%~dp0browser-profile\chrome-devtools"
set "LOGIN_URL=http://oa.hq.cmcc/portal-new/login"
set "APP_EXE=%~dp0dist\oa-auto-approve.exe"

if not exist "%CHROME_EXE%" (
  echo [ERROR] Chrome was not found.
  pause
  popd
  exit /b 1
)

if not exist "%APP_EXE%" (
  echo [ERROR] dist\oa-auto-approve.exe was not found.
  pause
  popd
  exit /b 1
)

if not exist "%CHROME_PROFILE%" mkdir "%CHROME_PROFILE%"

echo [1/4] Closing existing Chrome...
taskkill /IM chrome.exe /F >nul 2>nul
timeout /t 2 /nobreak >nul

echo [2/4] Starting Chrome with remote debugging...
start "" "%CHROME_EXE%" --remote-debugging-address=127.0.0.1 --remote-debugging-port=9222 --user-data-dir="%CHROME_PROFILE%" --profile-directory=Default --no-first-run --no-default-browser-check "%LOGIN_URL%"
timeout /t 5 /nobreak >nul

echo [3/4] Starting OA approver...
"%APP_EXE%" --browser chrome --attach-debugger 127.0.0.1:9222
set "EXIT_CODE=%ERRORLEVEL%"

if not "%EXIT_CODE%"=="0" (
  echo [ERROR] oa-auto-approve.exe exited with code %EXIT_CODE%.
  pause
)

echo [4/4] Finished.
popd
endlocal & exit /b %EXIT_CODE%
