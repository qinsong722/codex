param(
    [switch]$Clean
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ProjectRoot

if ($Clean) {
    Remove-Item -Recurse -Force "$ProjectRoot\build","$ProjectRoot\dist" -ErrorAction SilentlyContinue
}

python -m pip install -r requirements.txt

pyinstaller `
    --noconfirm `
    --clean `
    --onefile `
    --name oa-auto-approve `
    --add-binary "drivers\chromedriver-unpacked-146\chromedriver-win64\chromedriver.exe;drivers/chromedriver-146" `
    --hidden-import selenium.webdriver.chrome.webdriver `
    oa_auto_approve.py
