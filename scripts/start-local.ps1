$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot -Parent
& (Join-Path $PSScriptRoot 'init-local.ps1')
Push-Location $root
try {
    docker compose up --build -d --wait --wait-timeout 120
    if ($LASTEXITCODE -ne 0) { throw 'Compose startup failed. Existing containers/data were not deleted.' }
    Write-Host 'CashFlow Radar: http://localhost:3000; API: http://localhost:8000/docs'
} finally { Pop-Location }
