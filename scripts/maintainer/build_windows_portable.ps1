$ErrorActionPreference = "Stop"

$repoRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot "..\.."))
$python = Join-Path $repoRoot ".venv\Scripts\python.exe"
$source = Join-Path $repoRoot "voice_input.py"
$icon = Join-Path $repoRoot "assets\app.ico"
$buildRoot = Join-Path $repoRoot ".pet-build\pyinstaller"
$pyinstallerDist = Join-Path $buildRoot "dist"
$pyinstallerWork = Join-Path $buildRoot "work"
$specDir = Join-Path $buildRoot "spec"
$distRoot = Join-Path $repoRoot "dist"

if (-not (Test-Path $python)) {
    throw "Project virtual environment was not found."
}

$versionMatch = Select-String -LiteralPath $source -Pattern '^APP_VERSION = "([^"]+)"$'
if (-not $versionMatch) {
    throw "APP_VERSION was not found in voice_input.py."
}
$version = $versionMatch.Matches[0].Groups[1].Value
$packageName = "CodexVoiceInput-$version-win64"
$packageDir = Join-Path $distRoot $packageName
$archive = Join-Path $distRoot "$packageName.zip"

$safeRoots = @(
    [System.IO.Path]::GetFullPath((Join-Path $repoRoot ".pet-build")).TrimEnd('\'),
    [System.IO.Path]::GetFullPath($distRoot).TrimEnd('\')
)
foreach ($target in @($buildRoot, $packageDir, $archive)) {
    $resolved = [System.IO.Path]::GetFullPath($target)
    $isSafe = $safeRoots | Where-Object {
        $resolved.Equals($_, [System.StringComparison]::OrdinalIgnoreCase) -or
        $resolved.StartsWith($_ + '\', [System.StringComparison]::OrdinalIgnoreCase)
    }
    if (-not $isSafe) {
        throw "Build target escaped the project build directories: $resolved"
    }
}

foreach ($target in @($buildRoot, $packageDir, $archive)) {
    if (Test-Path $target) {
        Remove-Item -LiteralPath $target -Recurse -Force
    }
}
New-Item -ItemType Directory -Force -Path $pyinstallerDist, $pyinstallerWork, $specDir, $distRoot | Out-Null

$arguments = @(
    "-m", "PyInstaller",
    "--noconfirm",
    "--clean",
    "--onedir",
    "--windowed",
    "--name", "CodexVoiceInput",
    "--icon", $icon,
    "--add-data", "$(Join-Path $repoRoot 'assets');assets",
    "--collect-all", "sherpa_onnx",
    "--collect-all", "sounddevice",
    "--hidden-import", "pynput.keyboard._win32",
    "--hidden-import", "pynput.mouse._win32",
    "--distpath", $pyinstallerDist,
    "--workpath", $pyinstallerWork,
    "--specpath", $specDir,
    $source
)

& $python @arguments
if ($LASTEXITCODE -ne 0) {
    throw "PyInstaller build failed."
}

$builtApp = Join-Path $pyinstallerDist "CodexVoiceInput"
if (-not (Test-Path (Join-Path $builtApp "CodexVoiceInput.exe"))) {
    throw "Portable executable was not created."
}

Copy-Item -LiteralPath $builtApp -Destination $packageDir -Recurse
Copy-Item -LiteralPath (Join-Path $repoRoot "README.md") -Destination $packageDir
Copy-Item -LiteralPath (Join-Path $repoRoot "CHANGELOG.md") -Destination $packageDir
Copy-Item -LiteralPath (Join-Path $repoRoot "LICENSE") -Destination $packageDir
Copy-Item -LiteralPath (Join-Path $repoRoot "scripts\portable_create_shortcut.ps1") -Destination (Join-Path $packageDir "CreateDesktopShortcut.ps1")

Add-Type -AssemblyName System.IO.Compression.FileSystem
$archiveCreated = $false
Start-Sleep -Seconds 15
for ($attempt = 1; $attempt -le 12; $attempt++) {
    try {
        if (Test-Path $archive) {
            Remove-Item -LiteralPath $archive -Force
        }
        [System.IO.Compression.ZipFile]::CreateFromDirectory(
            $packageDir,
            $archive,
            [System.IO.Compression.CompressionLevel]::Optimal,
            $true
        )
        $archiveCreated = $true
        break
    }
    catch {
        Write-Warning "Archive attempt $attempt failed: $($_.Exception.Message)"
        if ($attempt -eq 12) {
            throw
        }
        Start-Sleep -Seconds 5
    }
}

if (-not $archiveCreated) {
    throw "Portable package archive was not created."
}

$check = [System.IO.Compression.ZipFile]::OpenRead($archive)
try {
    if (-not ($check.Entries | Where-Object FullName -like '*\CodexVoiceInput.exe')) {
        throw "Portable package archive is missing CodexVoiceInput.exe."
    }
}
finally {
    $check.Dispose()
}

Write-Host "Windows portable package created: $archive"
