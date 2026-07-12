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
    MsgBox "First launch will install Python dependencies. Keep this window open until setup finishes.", 64, "Codex Voice Input"
End If

command = "powershell.exe -NoProfile -ExecutionPolicy Bypass -WindowStyle " & powershellStyle & " -File " & Chr(34) & scriptDir & "\run.ps1" & Chr(34)

shell.Run command, windowStyle, False
