$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot -Parent
$target = Join-Path $root '.env'
if (Test-Path $target) {
    Write-Host '.env already exists; left unchanged.'
    return
}
function New-LocalSecret {
    $bytes = New-Object byte[] 32
    $rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
    try { $rng.GetBytes($bytes) } finally { $rng.Dispose() }
    return -join ($bytes | ForEach-Object { $_.ToString('x2') })
}
$lines = @(
    "RADAR_DB_PASSWORD=$(New-LocalSecret)"
    "RADAR_JWT_SECRET=$(New-LocalSecret)"
)
[System.IO.File]::WriteAllLines($target, $lines, [System.Text.UTF8Encoding]::new($false))
Write-Host 'Created .env with new local-only secrets. Existing database is untouched.'
