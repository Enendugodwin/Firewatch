# Stops the local PostgreSQL instance started by start_postgres.ps1.
param(
    [string]$PgHome = "$env:USERPROFILE\pgsql\pgsql",
    [string]$DataDir = "$env:USERPROFILE\pgsql\data"
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path "$PgHome\bin\pg_ctl.exe")) {
    throw "PostgreSQL binaries not found at $PgHome."
}

& "$PgHome\bin\pg_ctl.exe" -D $DataDir -m fast stop
