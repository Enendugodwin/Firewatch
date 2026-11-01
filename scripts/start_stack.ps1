# Starts FIREWATCH X: PostgreSQL (if needed), the API and the web dev server.
#
#   start.bat                (from the repository root)
#   powershell -ExecutionPolicy Bypass -File scripts\start_stack.ps1
#
# Logs and pid files live in <repo>\logs. Stop everything with stop.bat.
param(
    [int]$ApiPort = 8200,
    [int]$WebPort = 5273,
    [int]$DbPort = 5433
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$logs = Join-Path $root "logs"
New-Item -ItemType Directory -Force -Path $logs | Out-Null

function Test-Port([int]$port) {
    return [bool](Get-NetTCPConnection -State Listen -LocalPort $port -ErrorAction SilentlyContinue)
}

function Wait-Http([string]$url, [int]$seconds = 60) {
    $deadline = (Get-Date).AddSeconds($seconds)
    while ((Get-Date) -lt $deadline) {
        try {
            $response = Invoke-WebRequest -Uri $url -UseBasicParsing -TimeoutSec 5
            if ($response.StatusCode -eq 200) { return $true }
        } catch {
            Start-Sleep -Milliseconds 750
        }
    }
    return $false
}

# --- database -------------------------------------------------------------
if (-not (Test-Port $DbPort)) {
    Write-Host "Starting PostgreSQL on port $DbPort ..."
    & (Join-Path $PSScriptRoot "start_postgres.ps1") -Port $DbPort
} else {
    Write-Host "PostgreSQL already listening on $DbPort."
}

# --- API ------------------------------------------------------------------
if (-not (Test-Port $ApiPort)) {
    $python = Join-Path $root "backend\.venv\Scripts\python.exe"
    if (-not (Test-Path $python)) { throw "Python venv missing at $python. Create it first." }

    Write-Host "Starting API on port $ApiPort ..."
    # WMI keeps the server detached from this shell: a console child would keep
    # cmd.exe (and the .bat that called us) waiting until the server exits.
    $command = "cmd.exe /c cd /d `"$root\backend`" && `"$python`" -m uvicorn app.main:app --host 127.0.0.1 --port $ApiPort > `"$logs\api.log`" 2> `"$logs\api.err`""
    $created = Invoke-CimMethod -ClassName Win32_Process -MethodName Create -Arguments @{ CommandLine = $command }
    if ($created.ReturnValue -ne 0) { throw "Could not start the API (Win32_Process.Create returned $($created.ReturnValue))." }
    $created.ProcessId | Set-Content (Join-Path $logs "api.pid")
} else {
    Write-Host "API already listening on $ApiPort."
}

# --- web ------------------------------------------------------------------
if (-not (Test-Port $WebPort)) {
    Write-Host "Starting web dev server on port $WebPort ..."
    $command = "cmd.exe /c cd /d `"$root\frontend`" && npx vite --host 127.0.0.1 --port $WebPort --strictPort > `"$logs\web.log`" 2> `"$logs\web.err`""
    $created = Invoke-CimMethod -ClassName Win32_Process -MethodName Create -Arguments @{ CommandLine = $command }
    if ($created.ReturnValue -ne 0) { throw "Could not start the web server (Win32_Process.Create returned $($created.ReturnValue))." }
    $created.ProcessId | Set-Content (Join-Path $logs "web.pid")
} else {
    Write-Host "Web already listening on $WebPort."
}

# --- readiness ------------------------------------------------------------
$apiReady = Wait-Http "http://127.0.0.1:$ApiPort/ready" 90
$webReady = Wait-Http "http://127.0.0.1:$WebPort/" 90

# Record the listening processes: the launcher pids above can exit once the
# server is up (python and npx both spawn a child), so stop.bat needs the real ones.
foreach ($pair in @(@("api", $ApiPort), @("web", $WebPort))) {
    $name, $port = $pair
    $connection = Get-NetTCPConnection -State Listen -LocalPort $port -ErrorAction SilentlyContinue |
        Select-Object -First 1
    if ($connection) { $connection.OwningProcess | Set-Content (Join-Path $logs "$name.pid") }
}

Write-Host ""
if ($apiReady) { Write-Host "API   ready  -> http://127.0.0.1:$ApiPort/docs" }
else { Write-Host "API   NOT ready - see logs\api.err" -ForegroundColor Yellow }

if ($webReady) { Write-Host "Web   ready  -> http://127.0.0.1:$WebPort" }
else { Write-Host "Web   NOT ready - see logs\web.log" -ForegroundColor Yellow }

Write-Host "Database     -> postgresql://127.0.0.1:$DbPort/firewatch"
Write-Host ""
Write-Host "Stop everything with stop.bat"
