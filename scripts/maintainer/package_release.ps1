$ErrorActionPreference = "Stop"

$version = "0.3.1"
$repoRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot "..\.."))
$packageName = "CodexVoiceInput-$version"
$distDir = Join-Path $repoRoot "dist"
$packageDir = Join-Path $distDir $packageName
$archive = Join-Path $distDir "$packageName.zip"
$resolvedDist = [System.IO.Path]::GetFullPath($distDir).TrimEnd('\') + '\'
$resolvedPackage = [System.IO.Path]::GetFullPath($packageDir)

if (-not $resolvedPackage.StartsWith($resolvedDist, [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "Package directory escaped the project dist directory."
}

if (Test-Path $packageDir) {
    Remove-Item -LiteralPath $packageDir -Recurse -Force
}
if (Test-Path $archive) {
    Remove-Item -LiteralPath $archive -Force
}

New-Item -ItemType Directory -Path $packageDir -Force | Out-Null

$rootFiles = @(
    "README.md",
    "CHANGELOG.md",
    "LICENSE",
    "requirements.txt",
    "run.ps1",
    "start_voice_input.vbs",
    "voice_input.py"
)

foreach ($name in $rootFiles) {
    Copy-Item -LiteralPath (Join-Path $repoRoot $name) -Destination $packageDir
}

Copy-Item -LiteralPath (Join-Path $repoRoot "assets") -Destination $packageDir -Recurse
Copy-Item -LiteralPath (Join-Path $repoRoot "config") -Destination $packageDir -Recurse

$packageScripts = Join-Path $packageDir "scripts"
New-Item -ItemType Directory -Path $packageScripts -Force | Out-Null
Copy-Item -LiteralPath (Join-Path $repoRoot "scripts\create_desktop_shortcut.ps1") -Destination $packageScripts
Copy-Item -LiteralPath (Join-Path $repoRoot "scripts\install_offline_model.ps1") -Destination $packageScripts

Compress-Archive -LiteralPath $packageDir -DestinationPath $archive -CompressionLevel Optimal

Write-Host "Release package created: $archive"
