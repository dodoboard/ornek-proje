# Start the backend API, the job worker (auto-restarted on crash) and the frontend dev server.
# Ctrl+C stops everything.
$ErrorActionPreference = "Stop"
$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$Backend = Join-Path $Root "backend"
$Venv = Join-Path $Backend ".venv\Scripts"
$env:NEXT_TELEMETRY_DISABLED = "1"

if (-not (Test-Path (Join-Path $Venv "uvicorn.exe"))) { throw "Backend venv not found. See README: Setup." }

Push-Location $Backend
try { & (Join-Path $Venv "alembic.exe") upgrade head; if ($LASTEXITCODE -ne 0) { throw "Migration failed." } }
finally { Pop-Location }

$Api = Start-Process -FilePath (Join-Path $Venv "uvicorn.exe") -WorkingDirectory $Backend -PassThru -NoNewWindow `
    -ArgumentList @("app.main:create_app", "--factory", "--host", "127.0.0.1", "--port", "8000",
                    "--reload", "--reload-dir", "app")
$Worker = Start-Process -FilePath (Join-Path $Venv "python.exe") -WorkingDirectory $Backend -PassThru -NoNewWindow `
    -ArgumentList @("-m", "app.workers.supervisor")
try {
    Set-Location (Join-Path $Root "frontend")
    npm run dev
}
finally {
    foreach ($p in @($Api, $Worker)) {
        if ($p -and -not $p.HasExited) { Stop-Process -Id $p.Id -Force }
    }
}
