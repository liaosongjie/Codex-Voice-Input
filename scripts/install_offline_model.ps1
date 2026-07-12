$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$modelName = "sherpa-onnx-x-asr-480ms-streaming-zipformer-transducer-zh-en-punct-int8-2026-06-05"
$url = "https://github.com/k2-fsa/sherpa-onnx/releases/download/asr-models/$modelName.tar.bz2"
$modelsDir = Join-Path $repoRoot "models"
$archive = Join-Path $modelsDir "$modelName.tar.bz2"
$partialArchive = "$archive.download"
$modelDir = Join-Path $modelsDir $modelName
$requiredFiles = @("tokens.txt", "encoder.int8.onnx", "decoder.onnx", "joiner.int8.onnx", "bpe.model")

function Test-ModelReady {
    foreach ($name in $requiredFiles) {
        if (-not (Test-Path (Join-Path $modelDir $name))) {
            return $false
        }
    }
    return $true
}

$resolvedModelsDir = [System.IO.Path]::GetFullPath($modelsDir).TrimEnd('\') + '\'
$resolvedModelDir = [System.IO.Path]::GetFullPath($modelDir)
if (-not $resolvedModelDir.StartsWith($resolvedModelsDir, [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "Model directory escaped the project models directory."
}

New-Item -ItemType Directory -Force -Path $modelsDir | Out-Null

try {
    if (Test-ModelReady) {
        Write-Host "离线模型已经安装，无需重复下载。" -ForegroundColor Green
        exit 0
    }

    if (-not (Test-Path $archive)) {
        Remove-Item -LiteralPath $partialArchive -Force -ErrorAction SilentlyContinue
        Write-Host "正在下载离线模型（约 128 MB）..." -ForegroundColor Cyan
        Invoke-WebRequest -Uri $url -OutFile $partialArchive -Headers @{ "User-Agent" = "CodexVoiceInput" }
        Move-Item -LiteralPath $partialArchive -Destination $archive -Force
    }

    if (Test-Path $modelDir) {
        Remove-Item -LiteralPath $modelDir -Recurse -Force
    }

    Write-Host "下载完成，正在安装模型..." -ForegroundColor Cyan
    tar -xjf $archive -C $modelsDir
    if ($LASTEXITCODE -ne 0 -or -not (Test-ModelReady)) {
        throw "模型文件不完整，请重新运行安装脚本。"
    }

    Remove-Item -LiteralPath $archive -Force -ErrorAction SilentlyContinue
    Write-Host "离线模型安装完成：$modelDir" -ForegroundColor Green
}
catch {
    Remove-Item -LiteralPath $partialArchive -Force -ErrorAction SilentlyContinue
    if (-not (Test-ModelReady)) {
        Remove-Item -LiteralPath $archive -Force -ErrorAction SilentlyContinue
    }
    throw
}
