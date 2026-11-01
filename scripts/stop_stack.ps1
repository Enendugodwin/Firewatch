# Stops the API and web server started by start_stack.ps1, then PostgreSQL.
#
#   stop.bat                    (stops web + API + database)
#   stop.bat -KeepDatabase      (leaves PostgreSQL running)
param(
    [int]$ApiPort = 8200,
    [int]$WebPort = 5273,
    [int]$DbPort = 5433,
    [switch]$KeepDatabase
)

$ErrorActionPreference = "Continue"
$root = Split-Path -Parent $PSScriptRoot
$logs = Join-Path $root "logs"

function Stop-FromPidFile([string]$name, [int]$port) {
    $file = Join-Path $logs "$name.pid"
    if (Test-Path $file) {
        $processId = (Get-Content $file -Raw).Trim()
        if ($processId) {
            & taskkill.exe /PID $processId /T /F *> $null
        }
        Remove-Item $file -Force -ErrorAction SilentlyContinue
    }
    # Always verify the port: the recorded pid may be a launcher that already exited.
    $connection = Get-NetTCPConnection -State Listen -LocalPort $port -ErrorAction SilentlyContinue
    if ($connection) { return $false }
    return $true
}

function Stop-ByPort([int]$port, [string]$label) {
    $connection = Get-NetTCPConnection -State Listen -LocalPort $port -ErrorAction SilentlyContinue
    if (-not $connection) { return }
    $ownerPid = $connection.OwningProcess
    & taskkill.exe /PID $ownerPid /T /F *> $null
    Write-Host "$label stopped (port $port, pid $ownerPid)."
}

# Web first: it is the least important process.
if (-not (Stop-FromPidFile "web" $WebPort)) { Stop-ByPort $WebPort "Web" } else { Write-Host "Web stopped." }
if (-not (Stop-FromPidFile "api" $ApiPort)) { Stop-ByPort $ApiPort "API" } else { Write-Host "API stopped." }

if ($KeepDatabase) {
    Write-Host "PostgreSQL left running on $DbPort."
} else {
    $pgHome = Join-Path $env:USERPROFILE "pgsql\pgsql"
    $dataDir = Join-Path $env:USERPROFILE "pgsql\data"
    if (Test-Path (Join-Path $pgHome "bin\pg_ctl.exe")) {
        & (Join-Path $pgHome "bin\pg_ctl.exe") -D $dataDir -m fast stop *> $null
        Write-Host "PostgreSQL stopped."
    } else {
        Write-Host "PostgreSQL binaries not found; nothing to stop."
    }
}
