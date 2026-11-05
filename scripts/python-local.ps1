$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot -Parent
$envFile = Join-Path $root '.env'
if (-not (Test-Path $envFile)) { throw 'Run scripts/init-local.ps1 first.' }
$settings = @{}
foreach ($line in [System.IO.File]::ReadAllLines($envFile)) {
    if ($line -match '^(RADAR_DB_PASSWORD|RADAR_JWT_SECRET|RADAR_DB_NAME)=(.+)$') {
        $settings[$Matches[1]] = $Matches[2]
    }
}
$databaseName = if ($settings.RADAR_DB_NAME) { $settings.RADAR_DB_NAME } else { 'cashflow_radar' }
$values = @{
    RADAR_DATABASE_URL = "postgresql+asyncpg://radar:$($settings.RADAR_DB_PASSWORD)@localhost:55432/$databaseName"
    RADAR_JWT_SECRET = $settings.RADAR_JWT_SECRET
    RADAR_ALLOWED_ORIGINS = 'http://localhost:3000'
    FORECAST_GRPC_TARGET = 'localhost:50052'
    PYTHONPATH = "$root;$root\backend"
}
$previous = @{}
foreach ($key in $values.Keys) {
    $previous[$key] = [Environment]::GetEnvironmentVariable($key, 'Process')
    [Environment]::SetEnvironmentVariable($key, $values[$key], 'Process')
}
Push-Location $root
try {
    & (Join-Path $root '.venv\Scripts\python.exe') @args
    $result = $LASTEXITCODE
} finally {
    Pop-Location
    foreach ($key in $previous.Keys) { [Environment]::SetEnvironmentVariable($key, $previous[$key], 'Process') }
}
exit $result
