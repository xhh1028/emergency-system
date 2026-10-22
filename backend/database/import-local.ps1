param(
    [string]$SqlPath = (Join-Path $PSScriptRoot 'All.sql'),
    [switch]$CheckOnly
)

$ErrorActionPreference = 'Stop'
$backendDir = Split-Path $PSScriptRoot -Parent
$config = @{}
foreach ($file in @('.env', '.env.local')) {
    $path = Join-Path $backendDir $file
    if (Test-Path -LiteralPath $path) {
        foreach ($line in Get-Content -LiteralPath $path -Encoding UTF8) {
            if ($line -match '^\s*(DB_[A-Z_]+)=(.*)$') {
                $config[$matches[1]] = $matches[2]
            }
        }
    }
}
foreach ($key in @('DB_HOST', 'DB_PORT', 'DB_NAME', 'DB_USERNAME', 'DB_PASSWORD')) {
    if (-not $config.ContainsKey($key)) { throw "Missing setting: $key" }
}
if ($config.DB_HOST -notin @('localhost', '127.0.0.1', '::1')) {
    throw 'This tool imports into local MySQL only.'
}
if ($config.DB_PASSWORD -eq 'REPLACE_WITH_LOCAL_MYSQL_PASSWORD') {
    throw 'Fill in DB_PASSWORD in backend/.env.local, save it, then retry.'
}
if ($config.DB_NAME -notmatch '^[A-Za-z0-9_]+$') { throw 'Invalid DB_NAME.' }
$mysql = (Get-Command mysql.exe -ErrorAction Stop).Source
$mysqlArgs = @('--protocol=TCP', "--host=$($config.DB_HOST)", "--port=$($config.DB_PORT)",
    "--user=$($config.DB_USERNAME)", '--default-character-set=utf8mb4', '--connect-timeout=8',
    '--batch', '--skip-column-names')
$previousPassword = $env:MYSQL_PWD
$previousEncoding = $OutputEncoding
$previousConsoleEncoding = [Console]::OutputEncoding
try {
    $env:MYSQL_PWD = $config.DB_PASSWORD
    $OutputEncoding = New-Object System.Text.UTF8Encoding($false)
    [Console]::OutputEncoding = $OutputEncoding
    function Invoke-LocalQuery([string]$Query) {
        $result = & $mysql @mysqlArgs "--execute=$Query"
        if ($LASTEXITCODE -ne 0) { throw 'MySQL command failed. Check the error above.' }
        return $result
    }
    Invoke-LocalQuery 'SELECT VERSION(), CURRENT_USER();'
    $database = $config.DB_NAME
    $tables = Invoke-LocalQuery "SELECT TABLE_NAME FROM information_schema.TABLES WHERE TABLE_SCHEMA='$database' ORDER BY TABLE_NAME;"
    if ($CheckOnly) {
        Write-Host "Database: $database"
        $tables
        if ($tables -contains 'sys_user') {
            Invoke-LocalQuery "SELECT 'sys_user',COUNT(*) FROM $database.sys_user UNION ALL SELECT 'station',COUNT(*) FROM $database.station UNION ALL SELECT 'pre_plan',COUNT(*) FROM $database.pre_plan UNION ALL SELECT 'event',COUNT(*) FROM $database.event;"
        }
        return
    }
    if ($tables) { throw "Database $database already contains tables. Import stopped to preserve existing data. Use -CheckOnly, or set a new DB_NAME in .env.local." }
    $resolvedSql = (Resolve-Path -LiteralPath $SqlPath).Path
    $sql = [System.IO.File]::ReadAllText($resolvedSql, [System.Text.Encoding]::UTF8)
    Invoke-LocalQuery "CREATE DATABASE IF NOT EXISTS $database CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;"
    # One MySQL session; preserve Chinese text and stop on SQL errors.
    $sql + "`nSET FOREIGN_KEY_CHECKS=1;`n" | & $mysql @mysqlArgs "--database=$database"
    if ($LASTEXITCODE -ne 0) { throw 'Import failed. Some tables may have been created. Inspect the database before retrying; this tool never drops tables.' }
    Invoke-LocalQuery "SELECT TABLE_NAME FROM information_schema.TABLES WHERE TABLE_SCHEMA='$database' ORDER BY TABLE_NAME;"
    Invoke-LocalQuery "SELECT 'sys_user',COUNT(*) FROM $database.sys_user UNION ALL SELECT 'station',COUNT(*) FROM $database.station UNION ALL SELECT 'pre_plan',COUNT(*) FROM $database.pre_plan UNION ALL SELECT 'event',COUNT(*) FROM $database.event;"
    Write-Host "Import complete: $database"
} finally {
    $env:MYSQL_PWD = $previousPassword
    $OutputEncoding = $previousEncoding
    [Console]::OutputEncoding = $previousConsoleEncoding
}
