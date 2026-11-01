# Starts the local PostgreSQL instance used by FIREWATCH X (Windows, no service).
#
# The binaries are the EDB "binaries" zip unpacked to C:\Users\<you>\pgsql\pgsql
# and initialised into C:\Users\<you>\pgsql\data on port 5433 with trust
# authentication bound to 127.0.0.1. Nothing here needs admin rights.
#
# postgres.exe is launched through WMI so it is not a child of the calling shell:
# a pg_ctl-started postmaster, and processes started in the caller's job object,
# were killed when the hosting session restarted (children died with 0xC0000142).
param(
    [string]$PgHome = "$env:USERPROFILE\pgsql\pgsql",
    [string]$DataDir = "$env:USERPROFILE\pgsql\data",
    [int]$Port = 5433
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path "$PgHome\bin\pg_ctl.exe")) {
    throw "PostgreSQL binaries not found at $PgHome. Unzip the EDB binaries zip there first."
}

if (Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue) {
    Write-Host "PostgreSQL already listening on $Port."
    return
}

if (-not (Test-Path "$DataDir\PG_VERSION")) {
    Write-Host "Initialising a new cluster in $DataDir"
    & "$PgHome\bin\initdb.exe" -D $DataDir -U firewatch -A trust -E UTF8 --locale=C
}

$command = "`"$PgHome\bin\postgres.exe`" -D `"$DataDir`" -p $Port -c listen_addresses=127.0.0.1"
$created = Invoke-CimMethod -ClassName Win32_Process -MethodName Create -Arguments @{ CommandLine = $command }
if ($created.ReturnValue -ne 0) {
    throw "Could not start postgres.exe (Win32_Process.Create returned $($created.ReturnValue))."
}

$deadline = (Get-Date).AddSeconds(30)
while ((Get-Date) -lt $deadline) {
    if (Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue) { break }
    Start-Sleep -Milliseconds 500
}

if (-not (Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue)) {
    throw "PostgreSQL did not start listening on $Port within 30s. See $DataDir\..\server.log."
}

Write-Host "PostgreSQL ready on 127.0.0.1:$Port (pid $($created.ProcessId))."
