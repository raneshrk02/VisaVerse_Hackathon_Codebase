' Hidden launcher wrapper - ensures no terminal appears
' This script launches the main launcher completely hidden

CreateObject("WScript.Shell").Run "wscript.exe //nologo """ & CreateObject("Scripting.FileSystemObject").GetParentFolderName(WScript.ScriptFullName) & "\launcher.vbs""", 0, False
