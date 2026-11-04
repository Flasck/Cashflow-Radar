$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot -Parent
Push-Location $root
try {
    docker compose stop
    if ($LASTEXITCODE -ne 0) { throw 'Compose stop failed.' }
    Write-Host 'CashFlow Radar stopped. Database volume and secrets retained for the next start.'
} finally { Pop-Location }
