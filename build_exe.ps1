Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

Write-Host "Installing runtime dependencies..."
python -m pip install -r requirements.txt

Write-Host "Installing build dependencies..."
python -m pip install -r requirements-build.txt

Write-Host "Building FocusForensics.exe..."
pyinstaller --noconfirm --clean FocusForensics.spec

Write-Host "Build complete."
Write-Host "Executable: dist\\FocusForensics.exe"
