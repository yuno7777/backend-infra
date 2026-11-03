
# Backend Infra - local development PostgreSQL provisioner (Windows, no admin, no Docker).
# Idempotent: safe to re-run. Downloads portable EDB binaries once into local/postgres,
# creates a user-mode cluster in local/pgdata, starts it on 127.0.0.1:54329, creates the
# app + test databases, generates credentials into local/ and syncs .env.
# Nothing under local/ is ever committed (.gitignore).

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)   # repo root
$lib  = Join-Path $root "local"
$pgHome = Join-Path $lib "pgsql"
$pgData = Join-Path $lib "pgdata"
$pgSockets = Join-Path $lib "pgsockets"
$pgLog  = Join-Path $lib "pglog"
$pgPinne = Join-Path $lib "pg-password.txt"
$user = "backend_infra"
$port = 54329
$pgVersion = "17.8"
$dbName = "backend_infra"
$testDbName = "backend_infra_test"
$zipUrl = "https://get.enterprisedb.com/postgresql/postgresql-$pgVersion-1-windows-x64-binaries.zip"

function Test-ServerUp {
    param([int]$Port, [string]$User, [string]$Password)
    $eap = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        $env:PGPASSWORD = $Password
        $output = & (Join-Path $script:pgHome "bin\psql.exe") -h 127.0.0.1 -p $Port -U $User -d postgres -tAc "SELECT 1;" 2>$null
        return ($output -eq "1")
    } finally {
        $ErrorActionPreference = $eap
    }
}

New-Item -ItemType Directory -Force -Path $lib | Out-Null

# 1) Binaries
if (-not (Test-Path (Join-Path $pgHome "bin\postgres.exe"))) {
    $zip = Join-Path $env:TEMP "postgresql-$pgVersion-binaries.zip"
    if (-not (Test-Path $zip)) {
        Write-Host "Downloading portable PostgreSQL $pgVersion (one-time, ~334MB)..."
        & curl.exe -sSL -o $zip $zipUrl
        if ($LASTEXITCODE -ne 0) { throw "download failed" }
    }
    Write-Host "Extracting to $lib ..."
    New-Item -ItemType Directory -Force -Path $lib | Out-Null
    Expand-Archive -LiteralPath $zip -DestinationPath $lib -Force
    if (-not (Test-Path (Join-Path $pgHome "bin\postgres.exe"))) { throw "postgres binaries missing after extract" }
}

# 2) Credentials
if (-not (Test-Path $pgPinne)) {
    $bytes = New-Object byte[] 24
    [System.Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($bytes)
    [System.IO.File]::WriteAllText($pgPinne, [Convert]::ToBase64String($bytes))
}
$password = [System.IO.File]::ReadAllText($pgPinne).Trim()

# 3) Cluster init
$bin = Join-Path $pgHome "bin"
$srvReady = Test-ServerUp -Port $port -User $user -Password $password
if (-not $srvReady) {
    if (-not (Test-Path (Join-Path $pgData "PG_VERSION"))) {
        Write-Host "initdb -> $pgData"
        $tmpPw = Join-Path $env:TEMP "pg_initpw.txt"
        [System.IO.File]::WriteAllText($tmpPw, $password)
        & (Join-Path $bin "initdb.exe") -D $pgData -U $user --pwfile=$tmpPw -A scram-sha-256 -E UTF8 | Out-Null
        Remove-Item $tmpPw
    }
    $logDir = Join-Path $lib "pglog"
    $sockDir = Join-Path $lib "pgsockets"
    New-Item -ItemType Directory -Force -Path $logDir, $sockDir | Out-Null
    Write-Host "Configuring cluster (listen_addresses=127.0.0.1, port=$port, scram)"
    $conf = Join-Path $pgData "postgresql.conf"
    $marker = "# backend-infra-dev-config"
    if (-not ((Get-Content $conf -ErrorAction SilentlyContinue) -match [regex]::Escape($marker))) {
        $confLines = @(
            $marker,
            "listen_addresses = '127.0.0.1'",
            "port = $port",
            "unix_socket_directories = '$((($sockDir -replace '\\','/')))'",
            "password_encryption = 'scram-sha-256'"
        )
        Add-Content -LiteralPath $conf -Value ($confLines -join "`n")
    }
    Write-Host "Starting cluster on 127.0.0.1:$port"
    # Do NOT pipe this through PowerShell - the detached server inherits the stdout pipe and hangs it.
    # ArgumentList must be ONE pre-quoted string: PS 5.1 does not quote array items with spaces.
    $pgArgs = '-D "{0}" -l "{1}" start' -f $pgData, (Join-Path $logDir "postgres.log")
    Start-Process -FilePath (Join-Path $bin "pg_ctl.exe") -ArgumentList $pgArgs -Wait -NoNewWindow > $null 2>&1
    $deadline = (Get-Date).AddSeconds(60)
    do {
        Start-Sleep -Milliseconds 500
        $srvReady = Test-ServerUp -Port $port -User $user -Password $password
    } while (-not $srvReady -and (Get-Date) -lt $deadline)
    if (-not $srvReady) { throw "cluster did not become ready; see $logDir" }
}

# 4) Databases
foreach ($db in @($dbName, $testDbName)) {
    $exists = & (Join-Path $bin "psql.exe") -h 127.0.0.1 -p $port -U $user -d postgres -tAc "SELECT 1 FROM pg_database WHERE datname='$db';"
    if ($exists -ne "1") {
        & (Join-Path $bin "createdb.exe") -h 127.0.0.1 -p $port -U $user $db | Out-Null
        Write-Host "created database $db"
    }
}

# 5) Sync .env (only the keys this script owns; preserves everything else)
$envFile = Join-Path $root ".env"
$apiUrl = "postgresql+psycopg://${user}:$([uri]::EscapeDataString($password))@127.0.0.1:${port}/$dbName"
$testUrl = "postgresql+psycopg://${user}:$([uri]::EscapeDataString($password))@127.0.0.1:${port}/$testDbName"
$owned = @{
    "DATABASE_URL"     = $apiUrl
    "TEST_DATABASE_URL" = $testUrl
}
$envLines = @()
if (Test-Path $envFile) {
    $envLines = Get-Content $envFile | Where-Object { $_ -notmatch "^(DATABASE_URL|TEST_DATABASE_URL)=" }
}
$envLines = @($envLines) + @("DATABASE_URL=$apiUrl", "TEST_DATABASE_URL=$testUrl")
[System.IO.File]::WriteAllLines($envFile, $envLines)

Write-Host ""
Write-Host "Local PostgreSQL ready:"
Write-Host "  host: 127.0.0.1  port: $port  user: $user  databases: $dbName, $testDbName"
Write-Host "  .env synced with DATABASE_URL / TEST_DATABASE_URL"
Write-Host "Stop cluster:   & `"$bin\pg_ctl.exe`" -D `"$pgData`" stop"
Write-Host "Check status:   & `"$bin\pg_ctl.exe`" -D `"$pgData`" status"
