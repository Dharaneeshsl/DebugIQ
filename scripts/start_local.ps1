param([switch]$Install)
$ErrorActionPreference = "Stop"
$env:OPENBLAS_NUM_THREADS = "1"
$env:OMP_NUM_THREADS = "1"
$root = Split-Path -Parent $PSScriptRoot
$python = Join-Path $root ".venv\Scripts\python.exe"
if (!(Test-Path $python)) {
    python -m venv (Join-Path $root ".venv")
    if ($LASTEXITCODE -ne 0) { throw "Python environment setup failed" }
    $Install = $true
}
if ($Install) {
    & $python -m pip install -r (Join-Path $root "backend\requirements.txt")
    if ($LASTEXITCODE -ne 0) { throw "Backend dependency setup failed" }
    Push-Location (Join-Path $root "frontend")
    try {
        npm ci --no-audit --no-fund
        if ($LASTEXITCODE -ne 0) { throw "Frontend dependency setup failed" }
    } finally { Pop-Location }
}
if (!(Test-Path (Join-Path $root "frontend\node_modules"))) {
    throw "Run this script with -Install for first-time setup."
}
$backend = $null
Push-Location (Join-Path $root "frontend")
try {
    $backend = Start-Process -FilePath $python -ArgumentList @("-m", "uvicorn", "main:app", "--host", "127.0.0.1", "--port", "8000") -WorkingDirectory (Join-Path $root "backend") -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $root "backend\local-api.log") -RedirectStandardError (Join-Path $root "backend\local-api-error.log")
    $ready = $false
    for ($attempt = 0; $attempt -lt 40; $attempt++) {
        if ($backend.HasExited) { throw "API startup failed. Check backend/local-api-error.log." }
        try {
            $health = Invoke-RestMethod -Uri "http://127.0.0.1:8000/health" -TimeoutSec 1
            if ($health.status -eq "ok") { $ready = $true; break }
        } catch { Start-Sleep -Milliseconds 250 }
    }
    if (!$ready) { throw "API did not become ready. Check backend/local-api-error.log." }
    Write-Host "DebugIQ: http://localhost:5173 | API: http://localhost:8000/docs"
    Write-Host "Local admin: admin / admin123 (unless changed in backend/.env). Ctrl+C stops the app."
    npm run dev -- --host 127.0.0.1
} finally {
    if ($backend -and !$backend.HasExited) { Stop-Process -Id $backend.Id }
    Pop-Location
}
