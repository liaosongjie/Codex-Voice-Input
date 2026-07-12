Set shell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")

scriptDir = fso.GetParentFolderName(WScript.ScriptFullName)
setupComplete = fso.FileExists(scriptDir & "\.venv\.deps-stamp")

If setupComplete Then
    windowStyle = 0
    powershellStyle = "Hidden"
Else
    windowStyle = 1
    powershellStyle = "Normal"
    MsgBox "首次启动需要安装 Python 依赖。请保持网络连接，安装窗口完成后会自动关闭。", 64, "Codex Voice Input"
End If

command = "powershell.exe -NoProfile -ExecutionPolicy Bypass -WindowStyle " & powershellStyle & " -File " & Chr(34) & scriptDir & "\run.ps1" & Chr(34)

shell.Run command, windowStyle, False
