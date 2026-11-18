param(
    [ValidateRange(1, 65535)][int]$Port = 8000,
    [string]$ForwardedAllowIps
)
$ErrorActionPreference = "Stop"
$env:OPENBLAS_NUM_THREADS = "1"
$env:OMP_NUM_THREADS = "1"
$env:DEBUGIQ_ENV = "production"
$root = Split-Path -Parent $PSScriptRoot
$python = Join-Path $root ".venv\Scripts\python.exe"
$configuration = Join-Path $root "backend\.env.production"
if (!(Test-Path $python)) { throw "Create .venv and install backend/requirements-release.txt. See PRODUCTION.md." }
if (!(Test-Path $configuration)) { throw "Run .venv/Scripts/python.exe backend/provision_production.py first." }
$proxyOptions = @("--no-proxy-headers")
if ($ForwardedAllowIps) {
    if ($ForwardedAllowIps.Contains("*")) { throw "Specify the trusted proxy address instead of a wildcard." }
    $proxyOptions = @("--proxy-headers", "--forwarded-allow-ips", $ForwardedAllowIps)
}
Push-Location $root
try {
    & $python -m uvicorn main:app --app-dir backend --env-file $configuration --host 127.0.0.1 --port $Port --workers 1 --no-access-log @proxyOptions
    if ($LASTEXITCODE -ne 0) { throw "Production API exited with an error" }
} finally { Pop-Location }
