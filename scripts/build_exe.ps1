$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $projectRoot

python -m pip install pyinstaller
python -m PyInstaller --noconfirm --clean BossInsightAssistant.spec

Write-Host ""
Write-Host "Build finished:"
Write-Host "  $projectRoot\dist\BossInsightAssistant\BossInsightAssistant.exe"
