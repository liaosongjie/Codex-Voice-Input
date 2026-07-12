$ErrorActionPreference = "Stop"

$venv = Join-Path $PSScriptRoot ".venv"
$python = Join-Path $venv "Scripts\python.exe"
$pythonw = Join-Path $venv "Scripts\pythonw.exe"
$requirements = Join-Path $PSScriptRoot "requirements.txt"
$stamp = Join-Path $venv ".deps-stamp"
$log = Join-Path $PSScriptRoot "启动错误.log"

try {
    $escapedRoot = [Regex]::Escape($PSScriptRoot)
    $existing = Get-CimInstance Win32_Process | Where-Object {
        $_.Name -eq "pythonw.exe" -and
        $_.CommandLine -match $escapedRoot -and
        $_.CommandLine -match "voice_input\.py"
    } | Select-Object -First 1
    if ($existing) {
        exit 0
    }

    if (-not (Test-Path $python)) {
        if (-not (Get-Command py -ErrorAction SilentlyContinue)) {
            throw "未找到 Python。请先安装 Python 3.10 或更高版本，并勾选 Add Python to PATH。"
        }
        & py -3 -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)"
        if ($LASTEXITCODE -ne 0) {
            throw "Python 版本过低。需要 Python 3.10 或更高版本。"
        }
        py -3 -m venv $venv
        if ($LASTEXITCODE -ne 0) {
            throw "创建 Python 虚拟环境失败。"
        }
    }

    if ((-not (Test-Path $stamp)) -or ((Get-Item $requirements).LastWriteTime -gt (Get-Item $stamp).LastWriteTime)) {
        & $python -m pip install -r $requirements
        if ($LASTEXITCODE -ne 0) {
            throw "依赖安装失败。请检查网络或启动错误日志。"
        }
        Set-Content -Path $stamp -Value (Get-Date).ToString("o")
    }

    & $pythonw (Join-Path $PSScriptRoot "voice_input.py")
}
catch {
    $_ | Out-File -FilePath $log -Encoding utf8
    Add-Type -AssemblyName System.Windows.Forms
    [System.Windows.Forms.MessageBox]::Show("启动失败，详情见：$log", "Codex 中文语音输入") | Out-Null
    exit 1
}
