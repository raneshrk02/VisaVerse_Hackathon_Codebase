' USB Monitor for USB Mode Shortcut
' Monitors USB connection and removes shortcut if USB is removed
' Runs silently in background

Option Explicit
On Error Resume Next

Dim objShell, objFSO, strUSBPath, strShortcutPath
Dim bUSBConnected, bLastState, objFolder

Set objShell = CreateObject("WScript.Shell")
Set objFSO = CreateObject("Scripting.FileSystemObject")

' Get USB path from command line argument
' Usage: usb_monitor.vbs "D:\"
If WScript.Arguments.Count > 0 Then
    strUSBPath = WScript.Arguments(0)
Else
    ' Fallback - try common USB paths
    strUSBPath = "D:\"
End If

strShortcutPath = objShell.SpecialFolders("Desktop") & "\Start SAGE RAG System.lnk"

' Monitor loop
bLastState = True

Do While True
    bUSBConnected = objFSO.FolderExists(strUSBPath & "autorun")
    
    ' If USB was connected and now disconnected
    If bLastState And Not bUSBConnected Then
        ' Remove shortcut
        If objFSO.FileExists(strShortcutPath) Then
            objFSO.DeleteFile strShortcutPath, True
        End If
        ' Exit since USB is removed
        Exit Do
    End If
    
    bLastState = bUSBConnected
    
    ' Check every 5 seconds
    WScript.Sleep 5000
Loop
