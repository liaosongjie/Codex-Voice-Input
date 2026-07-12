$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"

$repoRoot = Split-Path -Parent $PSScriptRoot
$modelName = "sherpa-onnx-x-asr-480ms-streaming-zipformer-transducer-zh-en-punct-int8-2026-06-05"
$url = "https://github.com/k2-fsa/sherpa-onnx/releases/download/asr-models/$modelName.tar.bz2"
$modelsDir = Join-Path $repoRoot "models"
$archive = Join-Path $modelsDir "$modelName.tar.bz2"
$modelDir = Join-Path $modelsDir $modelName

New-Item -ItemType Directory -Force -Path $modelsDir | Out-Null

if (-not (Test-Path $archive)) {
    Write-Host "Downloading offline model..."
    Invoke-WebRequest -Uri $url -OutFile $archive -Headers @{ "User-Agent" = "CodexVoiceInput" }
}

if (-not (Test-Path $modelDir)) {
    Write-Host "Extracting offline model..."
    tar -xjf $archive -C $modelsDir
}

Write-Host "Offline model ready: $modelDir"
