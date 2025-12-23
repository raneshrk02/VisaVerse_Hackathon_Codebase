' SAGE RAG System - Universal USB Launcher
' This VBScript works regardless of AutoPlay settings
' Run this file to start the SAGE RAG System
' Also creates a desktop shortcut on first run

Option Explicit

Dim objShell, objFSO, strUSBRoot, strPythonExe, strLogFile
Dim strOutput, intReturnCode, strDesktopShortcut, objLink, objLoadingWnd

Set objShell = CreateObject("WScript.Shell")
Set objFSO = CreateObject("Scripting.FileSystemObject")

' Get the USB root directory (where this script is located)
strUSBRoot = objFSO.GetParentFolderName(WScript.ScriptFullName)
strUSBRoot = objFSO.GetParentFolderName(strUSBRoot)

strLogFile = strUSBRoot & "\autorun\launcher.log"

' Log function
Sub LogMessage(msg)
    Dim objFile
    On Error Resume Next
    Set objFile = objFSO.OpenTextFile(strLogFile, 8, True)
    objFile.WriteLine Now & " - " & msg
    objFile.Close
    On Error GoTo 0
End Sub

LogMessage "Launcher started from: " & WScript.ScriptFullName

' Show loading dialog
Set objLoadingWnd = CreateLoadingDialog()

' Create desktop shortcut on first run
Call CreateDesktopShortcut()

' Check if Python exists
strPythonExe = strUSBRoot & "\python\python.exe"
If Not objFSO.FileExists(strPythonExe) Then
    CloseLoadingDialog objLoadingWnd
    LogMessage "ERROR: Python not found at " & strPythonExe
    MsgBox "ERROR: Python not found!" & vbCrLf & vbCrLf & _
           "Expected location: " & strPythonExe & vbCrLf & vbCrLf & _
           "Please ensure Python is extracted to the USB drive.", _
           vbCritical, "SAGE RAG System - Error"
    WScript.Quit 1
End If

LogMessage "Python found: " & strPythonExe
UpdateLoadingDialog objLoadingWnd, "Checking system requirements..."

' Run OS detection
LogMessage "Running OS detection..."
UpdateLoadingDialog objLoadingWnd, "Detecting system configuration..."
intReturnCode = objShell.Run("""" & strPythonExe & """ """ & strUSBRoot & "\autorun\detect_os.py""", 0, True)

If intReturnCode <> 0 Then
    CloseLoadingDialog objLoadingWnd
    LogMessage "ERROR: OS detection failed with code " & intReturnCode
    MsgBox "ERROR: OS detection failed!" & vbCrLf & vbCrLf & _
           "Please check the logs or run manually from: " & strUSBRoot & "\autorun\autorun.bat", _
           vbCritical, "SAGE RAG System - Error"
    WScript.Quit 1
End If

LogMessage "OS detection passed"

' Kill any processes using required ports BEFORE starting anything
LogMessage "Cleaning up any existing processes on ports..."
UpdateLoadingDialog objLoadingWnd, "Closing any running services..."
KillProcessOnPort "8001"  ' Backend port
KillProcessOnPort "8080"  ' Frontend port
KillProcessOnPort "50051" ' gRPC port
WScript.Sleep 2000  ' Wait for processes to fully terminate

' Start servers directly (completely hidden - no batch file)
LogMessage "Starting servers in background..."
UpdateLoadingDialog objLoadingWnd, "Starting backend server..."

' Start Frontend (completely hidden using VBScript wrapper)
StartServerHidden strUSBRoot & "\frontend", strUSBRoot & "\node\npm run dev"

' Start Backend (completely hidden using VBScript wrapper)
StartServerHidden strUSBRoot & "\backend", strUSBRoot & "\backend\venv\Scripts\python.exe -m uvicorn main:app --host 0.0.0.0 --port 8001 --reload"

LogMessage "Servers started in background"

' Wait for backend to be ready with better progress messages
LogMessage "Waiting for backend to start..."
UpdateLoadingDialog objLoadingWnd, "Loading AI model (this may take 2-3 minutes)..."
WScript.Sleep 5000

UpdateLoadingDialog objLoadingWnd, "AI model loading... Please wait..."
WScript.Sleep 10000

UpdateLoadingDialog objLoadingWnd, "Almost ready... Loading knowledge base..."

If Not WaitForBackendReady(strUSBRoot) Then
    LogMessage "ERROR: Backend did not start within timeout"
    
    ' Make sure to close the loading dialog before showing error
    WScript.Sleep 500
    CloseLoadingDialog objLoadingWnd
    WScript.Sleep 500
    
    MsgBox "ERROR: Backend server failed to start!" & vbCrLf & vbCrLf & _
           "Please check the system logs.", _
           vbCritical, "SAGE RAG System - Error"
    WScript.Quit 1
End If

LogMessage "Backend is ready"

' Check if user closed the loading dialog before opening browser
If IsLoadingDialogOpen() Then
    ' Open browser to frontend
    LogMessage "Opening browser to http://127.0.0.1:8080"
    UpdateLoadingDialog objLoadingWnd, "Opening application..."
    WScript.Sleep 500
    objShell.Run "http://127.0.0.1:8080", 0, False
    
    ' Close loading dialog
    CloseLoadingDialog objLoadingWnd
    
    LogMessage "Launcher completed successfully"
Else
    ' User closed the dialog, exit without opening browser
    LogMessage "Loading dialog was closed by user, exiting without opening browser"
End If

WScript.Quit 0

' ============================================
' FUNCTION: Wait For Backend Ready
' ============================================
Function WaitForBackendReady(basePath)
    On Error Resume Next
    
    Dim strPythonExe, strWaitScript, intReturnCode
    
    strPythonExe = "D:\python\python.exe"
    strWaitScript = basePath & "\autorun\wait_for_backend.py"
    
    LogMessage "Checking for Python: " & strPythonExe
    LogMessage "Checking for script: " & strWaitScript
    
    If objFSO.FileExists(strPythonExe) And objFSO.FileExists(strWaitScript) Then
        ' Use Python script to wait for backend
        LogMessage "Running wait_for_backend.py..."
        intReturnCode = objShell.Run("""" & strPythonExe & """ """ & strWaitScript & """", 0, True)
        
        LogMessage "wait_for_backend.py returned: " & intReturnCode
        
        If intReturnCode = 0 Then
            WaitForBackendReady = True
        Else
            WaitForBackendReady = False
        End If
    Else
        ' Fallback: just wait a fixed amount of time
        LogMessage "Python or script not found, using fallback wait"
        WScript.Sleep 10000
        WaitForBackendReady = True
    End If
End Function

' ============================================
' FUNCTION: Create Loading Dialog
' ============================================
Function CreateLoadingDialog()
    On Error Resume Next
    
    Dim strHTAPath
    
    strHTAPath = objShell.ExpandEnvironmentStrings("%TEMP%") & "\SAGE_RAG_Loading.hta"
    CreateLoadingHTA strHTAPath
    
    ' Launch HTA in background
    objShell.Run "mshta.exe """ & strHTAPath & """", 1, False
    
    ' Give HTA time to open
    WScript.Sleep 1000
    
    ' Return HTA path for later reference
    Dim objLoadingObj
    Set objLoadingObj = CreateObject("Scripting.Dictionary")
    objLoadingObj.Add "HTAPath", strHTAPath
    
    Set CreateLoadingDialog = objLoadingObj
End Function

' ============================================
' FUNCTION: Create Loading HTA
' ============================================
Sub CreateLoadingHTA(strFilePath)
    On Error Resume Next
    
    Dim objFile, htaContent
    
    htaContent = "<!DOCTYPE html>" & _
    "<html>" & _
    "<head>" & _
    "<meta charset='utf-8'>" & _
    "<title>SAGE RAG - Starting</title>" & _
    "<HTA:APPLICATION ID='SAGE_RAG_Loading' APPLICATIONNAME='SAGE RAG' VERSION='1.0' " & _
    "BORDER='THIN' BORDERSTYLE='STATIC' CAPTION='YES' SHOWINTASKBAR='YES' " & _
    "SINGLETHREADED='NO' THREADINGMODEL='APARTMENT' WINDOWSTATE='NORMAL' " & _
    "INNERBORDER='NO' SCROLL='NO' MAXIMIZEBUTTON='NO' MINIMIZEBUTTON='NO' SYSMENU='NO' />" & _
    "<style>" & _
    "* { margin: 0; padding: 0; }" & _
    "body { font-family: Segoe UI, Arial, sans-serif; background: #f0f4f8; overflow: hidden; }" & _
    "table { border-collapse: collapse; }" & _
    ".container { background: white; border-radius: 20px; padding: 50px; box-shadow: 0 20px 60px -12px rgba(59, 130, 246, 0.25); width: 900px; margin: 40px auto; border: 1px solid rgba(219, 234, 254, 0.5); }" & _
    ".layout-table { width: 100%; }" & _
    ".left-section { width: 50%; padding-right: 25px; border-right: 2px solid #e2e8f0; vertical-align: middle; }" & _
    ".right-section { width: 50%; padding-left: 25px; vertical-align: middle; }" & _
    ".logo-box { width: 75px; height: 75px; background: #3b82f6; border-radius: 16px; text-align: center; line-height: 75px; font-size: 42px; font-weight: 700; color: white; margin-bottom: 24px; }" & _
    ".title { font-size: 42px; font-weight: 800; color: #0f172a; margin-bottom: 10px; }" & _
    ".subtitle { font-size: 13px; color: #64748b; margin-bottom: 24px; font-weight: 600; letter-spacing: 1.2px; text-transform: uppercase; }" & _
    ".description { font-size: 15px; color: #475569; line-height: 1.6; margin-bottom: 35px; }" & _
    ".status-box { padding: 20px; background: #f0f9ff; border-radius: 12px; border-left: 4px solid #10b981; margin-bottom: 20px; min-height: 120px; }" & _
    ".status-icon { font-size: 48px; text-align: center; margin-bottom: 16px; }" & _
    ".status-text { font-size: 16px; color: #0f172a; text-align: center; font-weight: 600; margin-bottom: 12px; }" & _
    ".status-detail { font-size: 13px; color: #64748b; text-align: center; }" & _
    ".spinner { display: inline-block; width: 40px; height: 40px; border: 4px solid #e2e8f0; border-top: 4px solid #3b82f6; border-radius: 50%; animation: spin 0.8s linear infinite; margin: 20px auto; display: block; }" & _
    "@keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }" & _
    ".info-grid { display: block; }" & _
    ".info-item { padding: 16px 18px; background: #f0f9ff; border-radius: 12px; border-left: 4px solid #3b82f6; margin-bottom: 12px; }" & _
    ".info-label { font-size: 13px; font-weight: 700; color: #0f172a; display: block; margin-bottom: 4px; }" & _
    ".info-value { font-size: 12px; color: #64748b; }" & _
    "</style>" & _
    "</head>" & _
    "<body>" & _
    "<div class='container'>" & _
    "<table class='layout-table'>" & _
    "<tr>" & _
    "<td class='left-section'>" & _
    "<div class='logo-box'>S</div>" & _
    "<h1 class='title'>SAGE RAG</h1>" & _
    "<p class='subtitle'>STARTING APPLICATION</p>" & _
    "<p class='description'>Please wait while we prepare your AI assistant. This will only take a moment.</p>" & _
    "</td>" & _
    "<td class='right-section'>" & _
    "<div class='status-box'>" & _
    "<div class='status-icon'>🚀</div>" & _
    "<div class='status-text' id='statusText'>Starting application...</div>" & _
    "<div class='spinner'></div>" & _
    "<div class='status-detail'>First launch may take 2-3 minutes</div>" & _
    "</div>" & _
    "<div class='info-grid'>" & _
    "<div class='info-item'>" & _
    "<span class='info-label'>Frontend</span>" & _
    "<span class='info-value'>http://127.0.0.1:8080</span>" & _
    "</div>" & _
    "<div class='info-item'>" & _
    "<span class='info-label'>Backend API</span>" & _
    "<span class='info-value'>http://127.0.0.1:8001</span>" & _
    "</div>" & _
    "</div>" & _
    "</td>" & _
    "</tr>" & _
    "</table>" & _
    "</div>" & _
    "<script>" & _
    "window.onload = function() { " & _
    "try { " & _
    "window.resizeTo(980, 580); " & _
    "window.moveTo((screen.availWidth - 980) / 2, (screen.availHeight - 580) / 2); " & _
    "window.focus(); " & _
    "checkForStatusUpdate(); " & _
    "} catch(e) {} " & _
    "}; " & _
    "function checkForStatusUpdate() { " & _
    "try { " & _
    "var fso = new ActiveXObject('Scripting.FileSystemObject'); " & _
    "var shell = new ActiveXObject('WScript.Shell'); " & _
    "var tempPath = shell.ExpandEnvironmentStrings('%TEMP%'); " & _
    "var statusFile = tempPath + '\\\\SAGE_RAG_Loading_Status.txt'; " & _
    "if (fso.FileExists(statusFile)) { " & _
    "var file = fso.OpenTextFile(statusFile, 1); " & _
    "var status = file.ReadLine(); " & _
    "file.Close(); " & _
    "document.getElementById('statusText').innerText = status; " & _
    "} " & _
    "} catch(e) {} " & _
    "setTimeout(checkForStatusUpdate, 300); " & _
    "} " & _
    "</script>" & _
    "</body>" & _
    "</html>"
    
    ' Write HTA file
    Set objFile = objFSO.CreateTextFile(strFilePath, True)
    objFile.Write htaContent
    objFile.Close
End Sub

' ============================================
' FUNCTION: Update Loading Dialog
' ============================================
Sub UpdateLoadingDialog(objLoadingWnd, strStatus)
    On Error Resume Next
    
    If Not (objLoadingWnd Is Nothing) Then
        ' Write status to temp file
        Dim strStatusFile, objFile
        strStatusFile = objShell.ExpandEnvironmentStrings("%TEMP%") & "\SAGE_RAG_Loading_Status.txt"
        
        Set objFile = objFSO.CreateTextFile(strStatusFile, True)
        objFile.WriteLine strStatus
        objFile.Close
        
        WScript.Sleep 100
    End If
End Sub

' ============================================
' FUNCTION: Close Loading Dialog
' ============================================
Sub CloseLoadingDialog(objLoadingWnd)
    On Error Resume Next
    
    If Not (objLoadingWnd Is Nothing) Then
        ' Small delay before closing
        WScript.Sleep 300
        
        ' Try multiple methods to close the HTA window
        ' Method 1: Kill by window title
        objShell.Run "taskkill /F /FI ""WINDOWTITLE eq SAGE RAG - Starting*"" /T", 0, True
        WScript.Sleep 200
        
        ' Method 2: Kill all mshta processes if still running
        objShell.Run "taskkill /F /IM mshta.exe /T", 0, True
        WScript.Sleep 200
        
        ' Clean up temp files
        If objLoadingWnd.Exists("HTAPath") Then
            Dim strHTAPath
            strHTAPath = objLoadingWnd.Item("HTAPath")
            If objFSO.FileExists(strHTAPath) Then
                objFSO.DeleteFile strHTAPath, True
            End If
        End If
        
        ' Clean up status file
        Dim strStatusFile
        strStatusFile = objShell.ExpandEnvironmentStrings("%TEMP%") & "\SAGE_RAG_Loading_Status.txt"
        If objFSO.FileExists(strStatusFile) Then
            objFSO.DeleteFile strStatusFile, True
        End If
    End If
End Sub

' ============================================
' FUNCTION: Create Desktop Shortcut
' ============================================
Sub CreateDesktopShortcut()
    Dim strDesktopPath, strShortcutPath, objLink, bShortcutExists
    On Error Resume Next
    
    ' Get Desktop path
    strDesktopPath = objShell.SpecialFolders("Desktop")
    strShortcutPath = strDesktopPath & "\Start SAGE RAG System.lnk"
    
    ' Check if shortcut already exists
    bShortcutExists = objFSO.FileExists(strShortcutPath)
    
    If Not bShortcutExists Then
        LogMessage "Creating desktop shortcut at: " & strShortcutPath
        
        Set objLink = objShell.CreateShortcut(strShortcutPath)
        ' Point to the hidden launcher wrapper
        objLink.TargetPath = strUSBRoot & "\autorun\launcher_hidden.vbs"
        objLink.WorkingDirectory = strUSBRoot
        objLink.Description = "Start SAGE RAG System"
        
        ' Set icon from frontend assets
        Dim strIconPath
        strIconPath = strUSBRoot & "\frontend\public\sage-icon.ico"
        If objFSO.FileExists(strIconPath) Then
            objLink.IconLocation = strIconPath
            LogMessage "Icon set to: " & strIconPath
        End If
        
        objLink.Save
        
        LogMessage "Desktop shortcut created successfully"
    Else
        LogMessage "Desktop shortcut already exists"
    End If
    
    On Error GoTo 0
End Sub

' ============================================
' FUNCTION: Kill Process On Port
' ============================================
Sub KillProcessOnPort(portNumber)
    On Error Resume Next
    
    Dim strTempFile, strOutput, objFile, strLine, arrLines, i
    Dim strPID
    
    LogMessage "Checking port " & portNumber & "..."
    
    ' Use temporary file to capture output without showing window
    strTempFile = objShell.ExpandEnvironmentStrings("%TEMP%") & "\sage_port_check.txt"
    
    ' Run netstat and save output to file (completely hidden)
    objShell.Run "cmd /c netstat -ano | findstr :" & portNumber & " > """ & strTempFile & """", 0, True
    
    ' Read the output file
    If objFSO.FileExists(strTempFile) Then
        Set objFile = objFSO.OpenTextFile(strTempFile, 1)
        If Not objFile.AtEndOfStream Then
            strOutput = objFile.ReadAll()
        End If
        objFile.Close
        objFSO.DeleteFile strTempFile, True
        
        If Len(strOutput) > 0 Then
            ' Parse output to find PIDs
            arrLines = Split(strOutput, vbCrLf)
            For i = 0 To UBound(arrLines)
                strLine = Trim(arrLines(i))
                If Len(strLine) > 0 And InStr(strLine, "LISTENING") > 0 Then
                    ' Extract PID (last column)
                    Dim arrParts, j
                    arrParts = Split(strLine, " ")
                    For j = UBound(arrParts) To 0 Step -1
                        If Len(Trim(arrParts(j))) > 0 Then
                            strPID = Trim(arrParts(j))
                            Exit For
                        End If
                    Next
                    
                    If Len(strPID) > 0 And IsNumeric(strPID) Then
                        LogMessage "Killing process " & strPID & " on port " & portNumber
                        objShell.Run "taskkill /F /PID " & strPID & " /T", 0, True
                        WScript.Sleep 500
                    End If
                End If
            Next
        End If
    End If
    
    On Error GoTo 0
End Sub

' ============================================
' FUNCTION: Start Server Hidden
' ============================================
Sub StartServerHidden(workingDir, commandLine)
    On Error Resume Next
    
    Dim tempVBS, objFile
    
    ' Create a temporary VBS file to launch the server
    tempVBS = objShell.ExpandEnvironmentStrings("%TEMP%") & "\sage_start_" & Int(Rnd() * 10000) & ".vbs"
    
    Set objFile = objFSO.CreateTextFile(tempVBS, True)
    objFile.WriteLine "Set objShell = CreateObject(""WScript.Shell"")"
    objFile.WriteLine "objShell.CurrentDirectory = """ & workingDir & """"
    objFile.WriteLine "objShell.Run """ & Replace(commandLine, """", """""") & """, 0, False"
    objFile.Close
    
    ' Execute the VBS file hidden
    objShell.Run "wscript.exe //nologo """ & tempVBS & """", 0, False
    
    ' Clean up after a short delay (in background)
    WScript.Sleep 1000
    On Error Resume Next
    objFSO.DeleteFile tempVBS, True
    On Error GoTo 0
End Sub

' ============================================
' FUNCTION: Is Loading Dialog Open
' ============================================
Function IsLoadingDialogOpen()
    On Error Resume Next
    
    Dim strTempFile, strOutput, objFile
    
    ' Use temporary file to capture output without showing window
    strTempFile = objShell.ExpandEnvironmentStrings("%TEMP%") & "\sage_dialog_check.txt"
    
    ' Check if mshta.exe is running (completely hidden)
    objShell.Run "cmd /c tasklist /FI ""IMAGENAME eq mshta.exe"" /FO CSV /NH > """ & strTempFile & """", 0, True
    
    ' Read the output file
    If objFSO.FileExists(strTempFile) Then
        Set objFile = objFSO.OpenTextFile(strTempFile, 1)
        If Not objFile.AtEndOfStream Then
            strOutput = objFile.ReadAll()
        End If
        objFile.Close
        objFSO.DeleteFile strTempFile, True
    End If
    
    ' If mshta.exe is running, the dialog is likely open
    If InStr(strOutput, "mshta.exe") > 0 Then
        IsLoadingDialogOpen = True
    Else
        IsLoadingDialogOpen = False
    End If
    
    On Error GoTo 0
End Function

' ============================================
' FUNCTION: Is Port In Use
' ============================================
Function IsPortInUse(portNumber)
    On Error Resume Next
    
    Dim strTempFile, strOutput, objFile
    
    ' Use temporary file to capture output without showing window
    strTempFile = objShell.ExpandEnvironmentStrings("%TEMP%") & "\sage_port_check_" & portNumber & ".txt"
    
    ' Run netstat and save output to file (completely hidden)
    objShell.Run "cmd /c netstat -ano | findstr :" & portNumber & " | findstr LISTENING > """ & strTempFile & """", 0, True
    
    ' Read the output file
    If objFSO.FileExists(strTempFile) Then
        Set objFile = objFSO.OpenTextFile(strTempFile, 1)
        If Not objFile.AtEndOfStream Then
            strOutput = objFile.ReadAll()
        End If
        objFile.Close
        objFSO.DeleteFile strTempFile, True
    End If
    
    ' If output contains port and LISTENING, port is in use
    If Len(strOutput) > 0 Then
        IsPortInUse = True
    Else
        IsPortInUse = False
    End If
    
    On Error GoTo 0
End Function
