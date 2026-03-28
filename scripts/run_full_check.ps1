# Full offline + build verification. Live API smoke: run smoke_test.ps1 with backend + Mongo up.
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot

Write-Host "== DebugIQ full check =="

Write-Host "`n[1/3] Backend unit + pipeline tests (pytest)..."
Push-Location (Join-Path $root "backend")
try {
  python -m pytest tests -v --tb=short
  if ($LASTEXITCODE -ne 0) { throw "pytest failed" }
} finally {
  Pop-Location
}

Write-Host "`n[2/3] Frontend production build..."
Push-Location (Join-Path $root "frontend")
try {
  if (!(Test-Path "node_modules")) {
    npm install
  }
  npm run build
  if ($LASTEXITCODE -ne 0) { throw "npm run build failed" }
} finally {
  Pop-Location
}

Write-Host "`n[3/3] Optional live smoke (backend on $env:DEBUGIQ_SMOKE_URL or http://localhost:8000)..."
$smokeUrl = $env:DEBUGIQ_SMOKE_URL
if ([string]::IsNullOrWhiteSpace($smokeUrl)) { $smokeUrl = "http://localhost:8000" }
try {
  $r = Invoke-WebRequest -Uri "$smokeUrl/health" -UseBasicParsing -TimeoutSec 3
  if ($r.StatusCode -eq 200) {
    Write-Host "Backend health OK - running smoke_test.ps1 -SkipExplain ..."
    & "$PSScriptRoot\smoke_test.ps1" -BaseUrl $smokeUrl -SkipExplain
  }
} catch {
  Write-Host "Skipping live smoke (start uvicorn + Mongo, then: .\scripts\smoke_test.ps1)"
}

Write-Host "`nDone."
