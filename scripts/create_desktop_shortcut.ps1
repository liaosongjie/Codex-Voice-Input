$ErrorActionPreference = "Stop"

$shortcutName = -join ("Codex", [char]0x4e2d, [char]0x6587, [char]0x8bed, [char]0x97f3, [char]0x8f93, [char]0x5165, ".lnk")
$repoRoot = Split-Path -Parent $PSScriptRoot
$launcher = Join-Path $repoRoot "start_voice_input.vbs"
$desktop = [Environment]::GetFolderPath("Desktop")
$shortcutPath = Join-Path $desktop $shortcutName

$shell = New-Object -ComObject WScript.Shell
$shortcut = $shell.CreateShortcut($shortcutPath)
$shortcut.TargetPath = Join-Path $env:WINDIR "System32\wscript.exe"
$shortcut.Arguments = '"' + $launcher + '"'
$shortcut.WorkingDirectory = $repoRoot
$shortcut.WindowStyle = 1
$shortcut.Description = "Start Codex voice input"
$shortcut.Save()

Write-Host "已创建桌面快捷方式：$shortcutPath"
