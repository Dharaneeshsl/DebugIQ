$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
if (!(Test-Path (Join-Path $root "frontend\dist\index.html"))) { throw "Build the frontend before packaging the release." }
$outputs = Join-Path $root "outputs"
$staging = Join-Path $outputs ("release-" + [guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Path $staging -Force | Out-Null
$files = @("README.md", "PRODUCTION.md", "RELEASE_STATUS.md", "backend/.env.example", "frontend/.env.example", "frontend/package.json", "frontend/package-lock.json", "frontend/index.html", "frontend/vite.config.js", "frontend/tailwind.config.cjs", "frontend/postcss.config.cjs", "data/demo.txt")
foreach ($folder in @("backend", "frontend/src", "frontend/public", "frontend/dist", "scripts")) {
    foreach ($file in Get-ChildItem -LiteralPath (Join-Path $root $folder) -Recurse -File) {
        $relative = $file.FullName.Substring($root.Length + 1)
        if ($relative -match '(^|\\)(__pycache__|data|node_modules|\.venv)(\\|$)') { continue }
        if ($file.Extension -in @(".py", ".jsx", ".js", ".css", ".html", ".png", ".svg", ".ps1") -or $file.Name -like "requirements*.txt") { $files += $relative }
    }
}
foreach ($relative in ($files | Select-Object -Unique)) {
    $destination = Join-Path $staging $relative
    New-Item -ItemType Directory -Path (Split-Path -Parent $destination) -Force | Out-Null
    Copy-Item -LiteralPath (Join-Path $root $relative) -Destination $destination
}
$manifest = Get-ChildItem -LiteralPath $staging -Recurse -File | ForEach-Object {
    @{ path = $_.FullName.Substring($staging.Length + 1); sha256 = (Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash }
}
$manifest | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $staging "manifest.json")
$archive = Join-Path $outputs ("DebugIQ-release-" + [DateTime]::UtcNow.ToString("yyyyMMdd-HHmmss") + ".zip")
Compress-Archive -Path (Join-Path $staging "*") -DestinationPath $archive
(Get-FileHash -LiteralPath $archive -Algorithm SHA256).Hash | Set-Content -LiteralPath ($archive + ".sha256")
Write-Output $archive
