$ErrorActionPreference = "Stop"

$exe = Join-Path $PSScriptRoot "CodexVoiceInput.exe"
if (-not (Test-Path $exe)) {
    throw "CodexVoiceInput.exe was not found next to this script."
}

$desktop = [Environment]::GetFolderPath("Desktop")
$shortcutPath = Join-Path $desktop "Codex Voice Input.lnk"
$shell = New-Object -ComObject WScript.Shell
$shortcut = $shell.CreateShortcut($shortcutPath)
$shortcut.TargetPath = $exe
$shortcut.WorkingDirectory = $PSScriptRoot
$shortcut.IconLocation = "$exe,0"
$shortcut.Description = "Start Codex Voice Input"
$shortcut.Save()

Write-Host "Desktop shortcut created: $shortcutPath"
