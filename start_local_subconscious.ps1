$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root

$venvPython = Join-Path $root "venv\Scripts\python.exe"
if (-not (Test-Path $venvPython)) {
    throw "Missing venv Python at $venvPython. Activate or recreate the project venv first."
}

$logsDir = Join-Path $root "logs"
New-Item -ItemType Directory -Force -Path $logsDir | Out-Null

$mainStdoutLog = Join-Path $logsDir "main.stdout.log"
$mainStderrLog = Join-Path $logsDir "main.stderr.log"
$apiStdoutLog = Join-Path $logsDir "uvicorn.stdout.log"
$apiStderrLog = Join-Path $logsDir "uvicorn.stderr.log"

# Avoid stale listener conflict when re-running locally while testing changed code.
$existing = Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue
if ($existing) {
    foreach ($conn in $existing) {
        try {
            Stop-Process -Id $conn.OwningProcess -Force -ErrorAction Stop
        } catch {
            Write-Warning "Could not stop process $($conn.OwningProcess) on port 8000."
        }
    }
}

# Launch the Tkinter UI in the current repo state.
Start-Process -FilePath $venvPython -ArgumentList @("main.py") -WorkingDirectory $root -RedirectStandardOutput $mainStdoutLog -RedirectStandardError $mainStderrLog

# Launch the FastAPI app without source reload. ChromaDB writes inside the project
# directory, and a reload during a write interrupts browser refresh requests.
Start-Process -FilePath $venvPython -ArgumentList @("-m", "uvicorn", "explorer:app", "--host", "127.0.0.1", "--port", "8000") -WorkingDirectory $root -RedirectStandardOutput $apiStdoutLog -RedirectStandardError $apiStderrLog

Write-Host "Started Local Subconscious"
Write-Host "UI: python main.py"
Write-Host "API: http://127.0.0.1:8000"
Write-Host "Logs:"
Write-Host "  - $mainStdoutLog"
Write-Host "  - $mainStderrLog"
Write-Host "  - $apiStdoutLog"
Write-Host "  - $apiStderrLog"
