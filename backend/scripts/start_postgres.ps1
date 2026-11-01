# Starts the local PostgreSQL instance used by FIREWATCH X (Windows, no service).
#
# The binaries are the EDB "binaries" zip unpacked to C:\Users\<you>\pgsql\pgsql
# and initialised into C:\Users\<you>\pgsql\data on port 5433 with a trust
# authentication rule bound to 127.0.0.1 only. Nothing here needs admin rights.
#
#   powershell -ExecutionPolicy Bypass -File scripts\start_postgres.ps1
param(
    [string]$PgHome = "$env:USERPROFILE\pgsql\pgsql",
    [string]$DataDir = "$env:USERPROFILE\pgsql\data",
    [int]$Port = 5433
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path "$PgHome\bin\pg_ctl.exe")) {
    throw "PostgreSQL binaries not found at $PgHome. Unzip the EDB binaries zip there first."
}

if (-not (Test-Path "$DataDir\PG_VERSION")) {
    Write-Host "Initialising a new cluster in $DataDir"
    & "$PgHome\bin\initdb.exe" -D $DataDir -U firewatch -A trust -E UTF8 --locale=C
}

$log = Join-Path $DataDir "..\server.log"

# Start postgres.exe directly, not through pg_ctl. On this Windows host pg_ctl
# yielded a postmaster whose child processes died with 0xC0000142
# (STATUS_DLL_INIT_FAILED) under load; the same server started this way runs for
# hours. Keep the launcher in sync with how the cluster is actually run.
$arguments = @("-D", $DataDir, "-p", "$Port")
$process = Start-Process -FilePath "$PgHome\bin\postgres.exe" -ArgumentList $arguments `
    -RedirectStandardOutput $log -RedirectStandardError "$DataDir\..\server.err" `
    -WindowStyle Hidden -PassThru

Start-Sleep -Seconds 5
if ($process.HasExited) {
    throw "PostgreSQL exited immediately (code $($process.ExitCode)); see $log"
}
& "$PgHome\bin\psql.exe" -h 127.0.0.1 -p $Port -U firewatch -d postgres -tAc "select 'postgres ' || version();"
