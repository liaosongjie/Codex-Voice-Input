$ErrorActionPreference = "Stop"

$version = "0.3.0"
$packageName = "CodexVoiceInput-$version"
$distDir = Join-Path $PSScriptRoot "dist"
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

$sourceFiles = Get-ChildItem -LiteralPath $PSScriptRoot -File | Where-Object {
    $_.Extension -in @(".py", ".ps1", ".vbs", ".cmd", ".md") -or
    $_.Name -in @("requirements.txt", "LICENSE", ".gitignore") -or
    $_.Name.EndsWith(".example.json", [System.StringComparison]::OrdinalIgnoreCase)
}

foreach ($file in $sourceFiles) {
    Copy-Item -LiteralPath $file.FullName -Destination $packageDir
}

Copy-Item -LiteralPath (Join-Path $PSScriptRoot "assets") -Destination $packageDir -Recurse
Copy-Item -LiteralPath (Join-Path $PSScriptRoot "tools") -Destination $packageDir -Recurse
Compress-Archive -LiteralPath $packageDir -DestinationPath $archive -CompressionLevel Optimal

Write-Host "Release package created: $archive"
