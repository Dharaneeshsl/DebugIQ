param(
  [string]$BaseUrl = "http://localhost:8000",
  [string]$Username = "admin",
  [string]$Password = "admin123",
  [string]$LogPath = "$PSScriptRoot\..\backend\sample_logs\test.log"
)

$ErrorActionPreference = "Stop"

Write-Host "== DebugIQ smoke test =="

if (!(Test-Path $LogPath)) {
  throw "Log file not found: $LogPath"
}

Write-Host "1) Get token..."
try {
  $tokenResp = Invoke-RestMethod -Method Post -Uri "$BaseUrl/token" -ContentType "application/x-www-form-urlencoded" -Body "username=$Username&password=$Password"
  $token = $tokenResp.access_token
} catch {
  $token = $null
}

if (!$token) {
  Write-Host "   Admin login failed; creating a temporary user..."
  $tmpUser = ("smoke_" + [DateTime]::UtcNow.ToString("yyyyMMddHHmmss") + "@debugiq.local")
  $tmpPass = "smoke_test_pw_123!"
  Invoke-RestMethod -Method Post -Uri "$BaseUrl/signup" -ContentType "application/json" -Body (@{ username = $tmpUser; password = $tmpPass; role = "user" } | ConvertTo-Json) | Out-Null
  $tokenResp = Invoke-RestMethod -Method Post -Uri "$BaseUrl/token" -ContentType "application/x-www-form-urlencoded" -Body "username=$tmpUser&password=$tmpPass"
  $token = $tokenResp.access_token
}

if (!$token) { throw "Token missing" }

$headers = @{ Authorization = "Bearer $token" }

Write-Host "2) Upload log..."
$uploadJson = & curl.exe -sS -X POST "$BaseUrl/upload" -H "Authorization: Bearer $token" -F "file=@$LogPath"
if (!$uploadJson) { throw "Upload returned empty response" }
$uploadResp = $uploadJson | ConvertFrom-Json
$runId = $uploadResp.run_id
if (!$runId) { throw "run_id missing" }
Write-Host "Uploaded. run_id=$runId"

Write-Host "3) Dashboard..."
$dash = Invoke-RestMethod -Method Get -Uri "$BaseUrl/dashboard/$runId" -Headers $headers
Write-Host ("total_failures=" + $dash.total_failures + " unique_failures=" + $dash.unique_failures)

Write-Host "4) Failures..."
$fails = Invoke-RestMethod -Method Get -Uri "$BaseUrl/failures/$runId" -Headers $headers
if ($fails.Count -lt 1) { throw "No failures returned" }
$first = $fails[0]
Write-Host ("first_failure_id=" + $first.id)

Write-Host "5) Explain..."
$exp = Invoke-RestMethod -Method Get -Uri "$BaseUrl/explain/$runId/$($first.id)" -Headers $headers
$preview = $exp.llm_explanation
if (!$preview) { throw "llm_explanation missing" }
$preview = $preview.Substring(0, [Math]::Min(120, $preview.Length))
$preview = ($preview -replace "`r`n", " ") -replace "`n", " "
Write-Host ("Explanation received. preview=" + $preview)

Write-Host "OK: DebugIQ is submission-ready."

