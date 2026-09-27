# Start the backend API and the frontend dev server. Ctrl+C stops both.
$ErrorActionPreference = "Stop"
$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$env:NEXT_TELEMETRY_DISABLED = "1"

$Uvicorn = Join-Path $Root "backend\.venv\Scripts\uvicorn.exe"
if (-not (Test-Path $Uvicorn)) { throw "Backend venv not found. See README: Backend setup." }

$Api = Start-Process -FilePath $Uvicorn -PassThru -NoNewWindow -ArgumentList @(
    "app.main:create_app", "--factory",
    "--app-dir", "`"$(Join-Path $Root 'backend')`"",
    "--host", "127.0.0.1", "--port", "8000",
    "--reload", "--reload-dir", "`"$(Join-Path $Root 'backend\app')`""
)
try {
    Set-Location (Join-Path $Root "frontend")
    npm run dev
}
finally {
    if (-not $Api.HasExited) { Stop-Process -Id $Api.Id -Force }
}
