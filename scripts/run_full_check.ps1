# Backend and build verification, plus smoke tests when the local API is running.
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$python = Join-Path $root ".venv\Scripts\python.exe"
if (!(Test-Path $python)) { $python = "python" }

Write-Host "== DebugIQ full check =="

Write-Host "`n[1/3] Backend unit + pipeline tests (pytest)..."
Push-Location (Join-Path $root "backend")
try {
  & $python -m pytest tests -v --tb=short
  if ($LASTEXITCODE -ne 0) { throw "pytest failed" }
} finally {
  Pop-Location
}

Write-Host "`n[2/3] Frontend production build..."
Push-Location (Join-Path $root "frontend")
try {
  if (!(Test-Path "node_modules")) {
    npm ci
    if ($LASTEXITCODE -ne 0) { throw "Frontend dependency install failed" }
  }
  npm run build
  if ($LASTEXITCODE -ne 0) { throw "npm run build failed" }
} finally {
  Pop-Location
}

Write-Host "`n[3/3] Optional live smoke (backend on $env:DEBUGIQ_SMOKE_URL or http://localhost:8000)..."
$smokeUrl = $env:DEBUGIQ_SMOKE_URL
if ([string]::IsNullOrWhiteSpace($smokeUrl)) { $smokeUrl = "http://localhost:8000" }
$liveAvailable = $false
try {
  $r = Invoke-WebRequest -Uri "$smokeUrl/health" -UseBasicParsing -TimeoutSec 3
  if ($r.StatusCode -eq 200) {
    $liveAvailable = $true
  }
} catch {
  Write-Host "Skipping live smoke (start scripts/start_local.ps1, then scripts/smoke_test.ps1)"
}
if ($liveAvailable) {
  Write-Host "Backend health OK - running smoke_test.ps1 ..."
  & "$PSScriptRoot\smoke_test.ps1" -BaseUrl $smokeUrl
}

Write-Host "`nDone."
