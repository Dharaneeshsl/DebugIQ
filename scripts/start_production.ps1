$ErrorActionPreference = "Stop"
$env:OPENBLAS_NUM_THREADS = "1"
$env:OMP_NUM_THREADS = "1"
$root = Split-Path -Parent $PSScriptRoot
$python = Join-Path $root ".venv\Scripts\python.exe"
$configuration = Join-Path $root "backend\.env.production"
if (!(Test-Path $python)) { throw "Install dependencies with scripts/start_local.ps1 -Install first." }
if (!(Test-Path $configuration)) { throw "Run .venv/Scripts/python.exe backend/provision_production.py first." }
Push-Location $root
try {
    & $python -m uvicorn main:app --app-dir backend --env-file $configuration --host 127.0.0.1 --port 8000 --workers 1 --no-proxy-headers
    if ($LASTEXITCODE -ne 0) { throw "Production API exited with an error" }
} finally { Pop-Location }
