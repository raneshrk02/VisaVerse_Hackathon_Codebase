' SAGE RAG System - Professional Installer
' Completely silent - no command prompt or terminal windows visible

Option Explicit
On Error Resume Next

Dim objShell, objFSO, strUSBRoot, strInstallDir, strDesktop
Dim strChoice

Set objShell = CreateObject("WScript.Shell")
Set objFSO = CreateObject("Scripting.FileSystemObject")

' Get USB root
strUSBRoot = objFSO.GetParentFolderName(WScript.ScriptFullName)
strDesktop = objShell.SpecialFolders("Desktop")

' Show landing page first
ShowLandingPageAndInstall()

WScript.Quit 0

' ============================================
' FUNCTION: Show Landing Page And Install
' ============================================
Sub ShowLandingPageAndInstall()
    On Error Resume Next
    
    Dim strHTAPath, objWshShell, intReturnValue
    Dim strChoice
    
    Set objWshShell = CreateObject("WScript.Shell")
    
    ' Create HTA file for landing page
    strHTAPath = objShell.ExpandEnvironmentStrings("%TEMP%") & "\SAGE_RAG_Installer.hta"
    CreateLandingPageHTA strHTAPath
    
    ' Run the HTA file
    intReturnValue = objWshShell.Run("mshta.exe """ & strHTAPath & """", 1, True)
    
    ' Give the HTA time to write the indicator file before checking
    WScript.Sleep 1000
    
    ' Check if user clicked Start Installation (HTA will create a file if they did)
    Dim strIndicatorFile
    strIndicatorFile = objShell.ExpandEnvironmentStrings("%TEMP%") & "\SAGE_RAG_START.txt"
    
    If objFSO.FileExists(strIndicatorFile) Then
        objFSO.DeleteFile strIndicatorFile, True
        
        ' Show installation choice
        strChoice = ShowInstallationChoiceWindow()
        
        If strChoice = "LOCAL" Then
            ' Install locally
            strInstallDir = objShell.ExpandEnvironmentStrings("%USERPROFILE%") & "\AppData\Local\SAGE_RAG_System"
            If Not InstallLocally(strUSBRoot, strInstallDir) Then
                MsgBox "Installation failed. Please try again.", vbCritical, "Error"
                WScript.Quit 1
            End If
        ElseIf strChoice = "USB" Then
            ' Run from USB
            If Not SetupUSBMode(strUSBRoot) Then
                MsgBox "USB setup failed. Please try again.", vbCritical, "Error"
                WScript.Quit 1
            End If
        End If
    End If
    
    ' Clean up HTA file
    On Error Resume Next
    If objFSO.FileExists(strHTAPath) Then
        objFSO.DeleteFile strHTAPath, True
    End If
End Sub

' ============================================
' FUNCTION: Create Landing Page HTA
' ============================================
Sub CreateLandingPageHTA(strFilePath)
    On Error Resume Next
    
    Dim objFile, htaContent
    
    htaContent = "<!DOCTYPE html>" & _
    "<html>" & _
    "<head>" & _
    "<meta charset='utf-8'>" & _
    "<title>SAGE RAG - Installer</title>" & _
    "<HTA:APPLICATION ID='SAGE_RAG_Installer' APPLICATIONNAME='SAGE RAG Installer' VERSION='1.0' " & _
    "BORDER='THIN' BORDERSTYLE='STATIC' CAPTION='YES' SHOWINTASKBAR='YES' " & _
    "SINGLETHREADED='NO' THREADINGMODEL='APARTMENT' WINDOWSTATE='NORMAL' " & _
    "INNERBORDER='NO' SCROLL='NO' MAXIMIZEBUTTON='NO' MINIMIZEBUTTON='NO' SYSMENU='YES' />" & _
    "<style>" & _
    "* { margin: 0; padding: 0; }" & _
    "body { font-family: Segoe UI, Arial, sans-serif; background: #f0f4f8; overflow: hidden; }" & _
    "table { border-collapse: collapse; }" & _
    ".outer-container { width: 100%; height: 100%; }" & _
    ".container { background: white; border-radius: 20px; padding: 50px; box-shadow: 0 20px 60px -12px rgba(59, 130, 246, 0.25); width: 900px; margin: 40px auto; border: 1px solid rgba(219, 234, 254, 0.5); }" & _
    ".layout-table { width: 100%; }" & _
    ".left-section { width: 50%; padding-right: 25px; border-right: 2px solid #e2e8f0; vertical-align: middle; }" & _
    ".right-section { width: 50%; padding-left: 25px; vertical-align: middle; }" & _
    ".logo-box { width: 75px; height: 75px; background: #3b82f6; border-radius: 16px; text-align: center; line-height: 75px; font-size: 42px; font-weight: 700; color: white; margin-bottom: 24px; }" & _
    ".title { font-size: 42px; font-weight: 800; color: #0f172a; margin-bottom: 10px; }" & _
    ".subtitle { font-size: 13px; color: #64748b; margin-bottom: 24px; font-weight: 600; letter-spacing: 1.2px; text-transform: uppercase; }" & _
    ".description { font-size: 15px; color: #475569; line-height: 1.6; margin-bottom: 35px; }" & _
    ".start-button { background: #10b981; color: white; border: none; padding: 16px 0; font-size: 16px; font-weight: 700; border-radius: 12px; cursor: pointer; width: 100%; }" & _
    ".start-button:hover { background: #059669; }" & _
    ".features { }" & _
    ".feature-item { padding: 16px 18px; background: #f0f9ff; border-radius: 12px; border-left: 4px solid #3b82f6; margin-bottom: 16px; }" & _
    ".feature-icon { font-size: 24px; display: inline-block; width: 30px; }" & _
    ".feature-title { font-size: 14px; font-weight: 700; color: #0f172a; display: inline-block; }" & _
    "</style>" & _
    "</head>" & _
    "<body>" & _
    "<div class='container'>" & _
    "<table class='layout-table'>" & _
    "<tr>" & _
    "<td class='left-section'>" & _
    "<div class='logo-box'>S</div>" & _
    "<h1 class='title'>SAGE RAG</h1>" & _
    "<p class='subtitle'>OFFLINE-FIRST AI ASSISTANT</p>" & _
    "<p class='description'>A powerful, privacy-first RAG system that works completely offline on your machine</p>" & _
    "<button class='start-button' onclick='startInstall()'>Start Installation</button>" & _
    "</td>" & _
    "<td class='right-section'>" & _
    "<div class='features'>" & _
    "<div class='feature-item'><span class='feature-icon'>⚡</span><span class='feature-title'>Fast & Responsive</span></div>" & _
    "<div class='feature-item'><span class='feature-icon'>🔒</span><span class='feature-title'>Privacy First</span></div>" & _
    "<div class='feature-item'><span class='feature-icon'>📚</span><span class='feature-title'>Knowledge Base</span></div>" & _
    "<div class='feature-item'><span class='feature-icon'>🔧</span><span class='feature-title'>Easy Setup</span></div>" & _
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
    "} catch(e) {} " & _
    "}; " & _
    "function startInstall() { " & _
    "try { " & _
    "var objFSO = new ActiveXObject('Scripting.FileSystemObject'); " & _
    "var objWshShell = new ActiveXObject('WScript.Shell'); " & _
    "var strTempPath = objWshShell.ExpandEnvironmentStrings('%TEMP%'); " & _
    "var strIndicatorFile = strTempPath + '\\SAGE_RAG_START.txt'; " & _
    "var objFile = objFSO.CreateTextFile(strIndicatorFile, true); " & _
    "objFile.WriteLine('START'); " & _
    "objFile.Close(); " & _
    "window.setTimeout(function() { window.close(); }, 500); " & _
    "} catch(e) { alert('Error: ' + e.message); } " & _
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
' FUNCTION: Show Installation Choice Window
' ============================================
Function ShowInstallationChoiceWindow()
    On Error Resume Next
    
    Dim strHTAPath, objWshShell
    Dim strChoiceIndicator
    
    Set objWshShell = CreateObject("WScript.Shell")
    
    ' Create HTA file for choice
    strHTAPath = objShell.ExpandEnvironmentStrings("%TEMP%") & "\SAGE_RAG_Choice.hta"
    CreateChoiceHTA strHTAPath
    
    ' Run the HTA file and activate it
    objWshShell.Run "mshta.exe """ & strHTAPath & """", 1, False
    WScript.Sleep 500
    
    ' Try to activate the window
    On Error Resume Next
    objWshShell.AppActivate "SAGE RAG - Choose Installation Type"
    On Error GoTo 0
    
    ' Wait for window to close
    Do While objFSO.FileExists(strHTAPath) And Not objFSO.FileExists(objShell.ExpandEnvironmentStrings("%TEMP%") & "\SAGE_RAG_CHOICE.txt")
        WScript.Sleep 200
    Loop
    
    ' Give time for file to be written
    WScript.Sleep 500
    
    ' Check which choice was made
    strChoiceIndicator = objShell.ExpandEnvironmentStrings("%TEMP%") & "\SAGE_RAG_CHOICE.txt"
    
    If objFSO.FileExists(strChoiceIndicator) Then
        Dim objFile, strChoice
        Set objFile = objFSO.OpenTextFile(strChoiceIndicator, 1)
        strChoice = objFile.ReadLine
        objFile.Close
        objFSO.DeleteFile strChoiceIndicator, True
        
        ShowInstallationChoiceWindow = strChoice
    Else
        ShowInstallationChoiceWindow = ""
    End If
    
    ' Cleanup
    On Error Resume Next
    If objFSO.FileExists(strHTAPath) Then
        objFSO.DeleteFile strHTAPath, True
    End If
End Function

' ============================================
' FUNCTION: Create Choice HTA
' ============================================
Sub CreateChoiceHTA(strFilePath)
    On Error Resume Next
    
    Dim objFile, htaContent
    
    htaContent = "<!DOCTYPE html>" & _
    "<html>" & _
    "<head>" & _
    "<meta charset='utf-8'>" & _
    "<title>SAGE RAG - Choose Installation Type</title>" & _
    "<HTA:APPLICATION ID='SAGE_RAG_Choice' APPLICATIONNAME='SAGE RAG Installer' VERSION='1.0' " & _
    "BORDER='THIN' BORDERSTYLE='STATIC' CAPTION='YES' SHOWINTASKBAR='YES' " & _
    "SINGLETHREADED='NO' THREADINGMODEL='APARTMENT' WINDOWSTATE='NORMAL' " & _
    "INNERBORDER='NO' SCROLL='NO' MAXIMIZEBUTTON='NO' MINIMIZEBUTTON='NO' SYSMENU='YES' />" & _
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
    ".option-card { padding: 20px; background: #f0f9ff; border-radius: 12px; border-left: 4px solid #3b82f6; margin-bottom: 16px; cursor: pointer; }" & _
    ".option-card:hover { background: #dbeafe; }" & _
    ".option-icon { font-size: 32px; margin-bottom: 12px; }" & _
    ".option-title { font-size: 16px; font-weight: 700; color: #0f172a; margin-bottom: 6px; }" & _
    ".option-desc { font-size: 13px; color: #64748b; }" & _
    "</style>" & _
    "</head>" & _
    "<body>" & _
    "<div class='container'>" & _
    "<table class='layout-table'>" & _
    "<tr>" & _
    "<td class='left-section'>" & _
    "<div class='logo-box'>S</div>" & _
    "<h1 class='title'>SAGE RAG</h1>" & _
    "<p class='subtitle'>CHOOSE INSTALLATION TYPE</p>" & _
    "<p class='description'>Select how you would like to install and run SAGE RAG on your system</p>" & _
    "</td>" & _
    "<td class='right-section'>" & _
    "<div class='option-card' onclick='selectLocal()'>" & _
    "<div class='option-icon'>💻</div>" & _
    "<div class='option-title'>Install Locally</div>" & _
    "<div class='option-desc'>Install on your computer for faster performance</div>" & _
    "</div>" & _
    "<div class='option-card' onclick='selectUSB()'>" & _
    "<div class='option-icon'>💾</div>" & _
    "<div class='option-title'>Run from USB</div>" & _
    "<div class='option-desc'>Portable installation. Run directly from USB</div>" & _
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
    "setTimeout(function() { window.focus(); self.focus(); }, 100); " & _
    "setTimeout(function() { window.focus(); self.focus(); }, 500); " & _
    "} catch(e) {} " & _
    "}; " & _
    "function selectLocal() { " & _
    "try { " & _
    "var objFSO = new ActiveXObject('Scripting.FileSystemObject'); " & _
    "var objWshShell = new ActiveXObject('WScript.Shell'); " & _
    "var strTempPath = objWshShell.ExpandEnvironmentStrings('%TEMP%'); " & _
    "var strFile = strTempPath + '\\SAGE_RAG_CHOICE.txt'; " & _
    "var objFile = objFSO.CreateTextFile(strFile, true); " & _
    "objFile.WriteLine('LOCAL'); " & _
    "objFile.Close(); " & _
    "window.setTimeout(function() { window.close(); }, 300); " & _
    "} catch(e) { } " & _
    "} " & _
    "function selectUSB() { " & _
    "try { " & _
    "var objFSO = new ActiveXObject('Scripting.FileSystemObject'); " & _
    "var objWshShell = new ActiveXObject('WScript.Shell'); " & _
    "var strTempPath = objWshShell.ExpandEnvironmentStrings('%TEMP%'); " & _
    "var strFile = strTempPath + '\\SAGE_RAG_CHOICE.txt'; " & _
    "var objFile = objFSO.CreateTextFile(strFile, true); " & _
    "objFile.WriteLine('USB'); " & _
    "objFile.Close(); " & _
    "window.setTimeout(function() { window.close(); }, 300); " & _
    "} catch(e) { } " & _
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
' FUNCTION: Install Locally
' ============================================
Function InstallLocally(fromPath, toPath)
    On Error Resume Next
    
    Dim objFolder, strShortcut, bResult
    Dim objProgressWnd
    
    ' Create install directory
    If Not objFSO.FolderExists(toPath) Then
        Set objFolder = objFSO.CreateFolder(toPath)
        If Err.Number <> 0 Then
            InstallLocally = False
            Exit Function
        End If
    End If
    
    ' Create and show progress window
    Set objProgressWnd = CreateProgressWindow()
    
    ' Copy files with progress
    bResult = CopyFilesWithProgress(fromPath, toPath, objProgressWnd)
    If Not bResult Then
        CloseProgressWindow objProgressWnd
        InstallLocally = False
        Exit Function
    End If
    
    ' Update progress - creating shortcut
    UpdateProgressDisplay objProgressWnd, 85, "Creating desktop shortcut..."
    
    ' Create desktop shortcut
    strShortcut = strDesktop & "\Start SAGE RAG System.lnk"
    If Not CreateLocalShortcut(strShortcut, toPath) Then
        CloseProgressWindow objProgressWnd
        InstallLocally = False
        Exit Function
    End If
    
    ' Update progress - complete (WITHOUT launching)
    UpdateProgressDisplay objProgressWnd, 100, "Installation complete!"
    
    ' Show finish page instead of in-window button
    ShowFinishPage toPath, "local"
    
    CloseProgressWindow objProgressWnd
    
    InstallLocally = True
End Function

' ============================================
' FUNCTION: Setup USB Mode
' ============================================
Function SetupUSBMode(usbPath)
    On Error Resume Next
    
    Dim strShortcut, bResult
    
    ' Create shortcut directly (no launcher batch needed)
    strShortcut = strDesktop & "\Start SAGE RAG System.lnk"
    bResult = CreateUSBModeShortcut(strShortcut, usbPath)
    If Not bResult Then
        SetupUSBMode = False
        Exit Function
    End If
    
    ' Show finish page directly
    ShowFinishPage usbPath, "usb"
    
    SetupUSBMode = True
End Function

' ============================================
' FUNCTION: Copy Files With Progress
' ============================================
Function CopyFilesWithProgress(fromPath, toPath, objProgressWnd)
    On Error Resume Next
    
    Dim foldersToCopy, i, srcFolder, destFolder
    Dim intProgress, intProgressPerStep
    
    foldersToCopy = Array("backend", "frontend", "python", "node", "autorun")
    intProgressPerStep = 60 / (UBound(foldersToCopy) + 1)
    intProgress = 10
    
    For i = LBound(foldersToCopy) To UBound(foldersToCopy)
        srcFolder = fromPath & "\" & foldersToCopy(i)
        destFolder = toPath & "\" & foldersToCopy(i)
        
        If objFSO.FolderExists(srcFolder) Then
            UpdateProgressDisplay objProgressWnd, intProgress, "Copying " & foldersToCopy(i) & "..."
            
            If objFSO.FolderExists(destFolder) Then
                objFSO.DeleteFolder destFolder, True
            End If
            
            objFSO.CopyFolder srcFolder, destFolder
            
            If Err.Number <> 0 Then
                CopyFilesWithProgress = False
                Exit Function
            End If
            
            intProgress = intProgress + intProgressPerStep
            UpdateProgressDisplay objProgressWnd, intProgress, "Copied " & foldersToCopy(i) & " ✓"
        End If
    Next
    
    CopyFilesWithProgress = True
End Function

' ============================================
' FUNCTION: Create Progress Window
' ============================================
' FUNCTION: Create Progress Window (HTA-based)
' ============================================
Function CreateProgressWindow()
    On Error Resume Next
    
    Dim strHTAPath, objProgressWnd, intRetries
    
    strHTAPath = objShell.ExpandEnvironmentStrings("%TEMP%") & "\SAGE_RAG_Progress.hta"
    CreateProgressHTA strHTAPath
    
    ' Launch HTA and return handle
    Set objProgressWnd = CreateObject("WScript.Shell")
    objProgressWnd.Run "mshta.exe """ & strHTAPath & """", 1, False
    
    ' Store HTA path for later cleanup
    objProgressWnd.HTAPath = strHTAPath
    
    ' Give HTA time to open
    WScript.Sleep 2000
    
    ' Return a special object that represents the HTA
    Dim objProgressObj
    Set objProgressObj = CreateObject("Scripting.Dictionary")
    objProgressObj.Add "HTAPath", strHTAPath
    objProgressObj.Add "Shell", objProgressWnd
    
    Set CreateProgressWindow = objProgressObj
End Function

' ============================================
' FUNCTION: Create Progress HTA
' ============================================
Sub CreateProgressHTA(strFilePath)
    On Error Resume Next
    
    Dim objFile, htaContent
    
    htaContent = "<!DOCTYPE html>" & _
    "<html>" & _
    "<head>" & _
    "<meta charset='utf-8'>" & _
    "<title>SAGE RAG - Installing</title>" & _
    "<HTA:APPLICATION ID='SAGE_RAG_Progress' APPLICATIONNAME='SAGE RAG Installer' VERSION='1.0' " & _
    "BORDER='THIN' BORDERSTYLE='STATIC' CAPTION='YES' SHOWINTASKBAR='YES' " & _
    "SINGLETHREADED='NO' THREADINGMODEL='APARTMENT' WINDOWSTATE='NORMAL' " & _
    "INNERBORDER='NO' SCROLL='NO' MAXIMIZEBUTTON='NO' MINIMIZEBUTTON='NO' SYSMENU='YES' />" & _
    "<style>" & _
    "* { margin: 0; padding: 0; }" & _
    "body { font-family: Segoe UI, Arial, sans-serif; background: #f0f4f8; overflow: hidden; }" & _
    "table { border-collapse: collapse; }" & _
    ".container { background: white; border-radius: 20px; padding: 50px; box-shadow: 0 20px 60px -12px rgba(59, 130, 246, 0.25); width: 900px; margin: 40px auto; border: 1px solid rgba(219, 234, 254, 0.5); }" & _
    ".layout-table { width: 100%; }" & _
    ".left-section { width: 50%; padding-right: 25px; border-right: 2px solid #e2e8f0; vertical-align: middle; }" & _
    ".right-section { width: 50%; padding-left: 25px; vertical-align: middle; }" & _
    ".logo-box { width: 75px; height: 75px; background: #3b82f6; border-radius: 16px; text-align: center; line-height: 75px; font-size: 42px; font-weight: 700; color: white; margin-bottom: 24px; }" & _
    ".spinner { display: inline-block; width: 20px; height: 20px; border: 3px solid #e2e8f0; border-top: 3px solid #3b82f6; border-radius: 50%; animation: spin 0.8s linear infinite; }" & _
    "@keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }" & _
    ".title { font-size: 42px; font-weight: 800; color: #0f172a; margin-bottom: 10px; }" & _
    ".subtitle { font-size: 13px; color: #64748b; margin-bottom: 24px; font-weight: 600; letter-spacing: 1.2px; text-transform: uppercase; }" & _
    ".description { font-size: 15px; color: #475569; line-height: 1.6; margin-bottom: 35px; }" & _
    ".progress-item { padding: 16px 18px; background: #f0f9ff; border-radius: 12px; border-left: 4px solid #3b82f6; margin-bottom: 16px; }" & _
    ".progress-icon { font-size: 20px; display: inline-block; width: 30px; vertical-align: middle; }" & _
    ".progress-text { font-size: 14px; color: #0f172a; display: inline-block; vertical-align: middle; }" & _
    ".progress-label { font-weight: 700; }" & _
    ".progress-value { color: #64748b; font-size: 13px; }" & _
    ".progress-bar { background: #e2e8f0; border-radius: 8px; overflow: hidden; height: 8px; margin-top: 8px; }" & _
    ".progress-fill { background: #3b82f6; height: 100%; width: 0%; transition: width 0.3s ease; }" & _
    ".status-active { border-left-color: #10b981; background: #f0fdf4; }" & _
    "</style>" & _
    "</head>" & _
    "<body>" & _
    "<div class='container'>" & _
    "<table class='layout-table'>" & _
    "<tr>" & _
    "<td class='left-section'>" & _
    "<div class='logo-box'>S</div>" & _
    "<h1 class='title'>SAGE RAG</h1>" & _
    "<p class='subtitle'>INSTALLING SYSTEM</p>" & _
    "<p class='description'>Please wait while we set up SAGE RAG on your system. This may take a few minutes.</p>" & _
    "</td>" & _
    "<td class='right-section'>" & _
    "<div class='progress-item status-active' id='step1'>" & _
    "<span class='progress-icon'><span class='spinner'></span></span>" & _
    "<span class='progress-text'>" & _
    "<span class='progress-label'>Preparing Installation</span><br>" & _
    "<span class='progress-value' id='status1'>Initializing...</span>" & _
    "</span>" & _
    "<div class='progress-bar'><div class='progress-fill' id='progress1' style='width: 0%;'></div></div>" & _
    "</div>" & _
    "<div class='progress-item' id='step2'>" & _
    "<span class='progress-icon'>📦</span>" & _
    "<span class='progress-text'>" & _
    "<span class='progress-label'>Copying Files</span><br>" & _
    "<span class='progress-value' id='status2'>Waiting...</span>" & _
    "</span>" & _
    "<div class='progress-bar'><div class='progress-fill' id='progress2' style='width: 0%;'></div></div>" & _
    "</div>" & _
    "<div class='progress-item' id='step3'>" & _
    "<span class='progress-icon'>🔗</span>" & _
    "<span class='progress-text'>" & _
    "<span class='progress-label'>Creating Shortcuts</span><br>" & _
    "<span class='progress-value' id='status3'>Waiting...</span>" & _
    "</span>" & _
    "<div class='progress-bar'><div class='progress-fill' id='progress3' style='width: 0%;'></div></div>" & _
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
    "} catch(e) {} " & _
    "}; " & _
    "</script>" & _
    "</body>" & _
    "</html>"
    
    ' Write HTA file
    Set objFile = objFSO.CreateTextFile(strFilePath, True)
    objFile.Write htaContent
    objFile.Close
End Sub


' ============================================
' FUNCTION: Update Progress Display (HTA version)
' ============================================
Sub UpdateProgressDisplay(objProgressWnd, intPercent, strStatus)
    On Error Resume Next
    
    ' Write progress to a temp file that we'll check exists as a signal
    Dim strProgressFile, objFile
    strProgressFile = objShell.ExpandEnvironmentStrings("%TEMP%") & "\SAGE_RAG_Progress_Signal.txt"
    
    Set objFile = objFSO.CreateTextFile(strProgressFile, True)
    objFile.WriteLine intPercent & "|" & strStatus
    objFile.Close
    
    ' Small delay to allow file system to sync
    WScript.Sleep 100
End Sub

' ============================================
' FUNCTION: Close Progress Window (HTA version)
' ============================================
Sub CloseProgressWindow(objProgressWnd)
    On Error Resume Next
    
    ' Give a moment for final updates
    WScript.Sleep 500
    
    If Not (objProgressWnd Is Nothing) Then
        ' Close the HTA window via taskkill
        objShell.Run "taskkill /F /FI ""WINDOWTITLE eq SAGE RAG - Installing*"" /T", 0, True
        WScript.Sleep 300
        
        ' Delete the temporary HTA file
        If objProgressWnd.Exists("HTAPath") Then
            Dim strHTAPath
            strHTAPath = objProgressWnd.Item("HTAPath")
            If objFSO.FileExists(strHTAPath) Then
                objFSO.DeleteFile strHTAPath, True
            End If
        End If
        
        ' Clean up progress signal file
        Dim strProgressFile
        strProgressFile = objShell.ExpandEnvironmentStrings("%TEMP%") & "\SAGE_RAG_Progress_Signal.txt"
        If objFSO.FileExists(strProgressFile) Then
            objFSO.DeleteFile strProgressFile, True
        End If
    End If
End Sub


' ============================================
' FUNCTION: Create Local Shortcut
' ============================================
Function CreateLocalShortcut(shortcutPath, installDir)
    On Error Resume Next
    
    Dim oLink, iconPath
    
    ' Always recreate the shortcut to ensure icon and settings are updated
    If objFSO.FileExists(shortcutPath) Then
        objFSO.DeleteFile shortcutPath, True
    End If
    
    Set oLink = objShell.CreateShortcut(shortcutPath)
    oLink.TargetPath = "wscript.exe"
    ' Pass the launcher path as a quoted argument to wscript.exe
    oLink.Arguments = """" & installDir & "\autorun\launcher.vbs" & """"
    oLink.WorkingDirectory = installDir
    oLink.Description = "Start SAGE RAG System"
    oLink.WindowStyle = 0
    
    ' Try to set icon from frontend assets if available
    iconPath = installDir & "\frontend\public\sage-icon.ico"
    If objFSO.FileExists(iconPath) Then
        ' Explicitly set index to 0 for .ico files to ensure Windows picks it up
        oLink.IconLocation = iconPath & ",0"
    End If
    
    oLink.Save
    
    CreateLocalShortcut = (Err.Number = 0)
End Function

' ============================================
' FUNCTION: Create USB Mode Shortcut
' ============================================
Function CreateUSBModeShortcut(shortcutPath, usbPath)
    On Error Resume Next
    
    Dim oLink, iconPath
    
    ' Always recreate shortcut to ensure icon is set
    If objFSO.FileExists(shortcutPath) Then
        objFSO.DeleteFile shortcutPath, True
    End If
    
    Set oLink = objShell.CreateShortcut(shortcutPath)
    oLink.TargetPath = "wscript.exe"
    ' Pass the launcher path as a quoted argument to wscript.exe
    oLink.Arguments = """" & usbPath & "\autorun\launcher.vbs" & """"
    oLink.WorkingDirectory = usbPath
    oLink.Description = "Start SAGE RAG System (USB Mode)"
    oLink.WindowStyle = 0
    
    ' Set icon from USB assets
    iconPath = usbPath & "\frontend\public\sage-icon.ico"
    If objFSO.FileExists(iconPath) Then
        oLink.IconLocation = iconPath & ",0"
    End If
    
    oLink.Save
    
    CreateUSBModeShortcut = (Err.Number = 0)
End Function

' ============================================
' FUNCTION: Show Finish Page HTA
' ============================================
Sub ShowFinishPage(appPath, installMode)
    On Error Resume Next
    
    Dim strHTAPath, objWshShell, strDesktopShortcut
    
    Set objWshShell = CreateObject("WScript.Shell")
    
    ' Determine shortcut location and message
    strDesktopShortcut = strDesktop & "\Start SAGE RAG System.lnk"
    
    ' Create HTA file for finish page
    strHTAPath = objShell.ExpandEnvironmentStrings("%TEMP%") & "\SAGE_RAG_Finish.hta"
    CreateFinishPageHTA strHTAPath, installMode, strDesktopShortcut
    
    ' Run the HTA file
    objWshShell.Run "mshta.exe """ & strHTAPath & """", 1, True
    
    ' Cleanup
    On Error Resume Next
    If objFSO.FileExists(strHTAPath) Then
        objFSO.DeleteFile strHTAPath, True
    End If
End Sub

' ============================================
' FUNCTION: Create Finish Page HTA
' ============================================
Sub CreateFinishPageHTA(strFilePath, installMode, shortcutPath)
    On Error Resume Next
    
    Dim objFile, htaContent, strModeInfo
    
    ' Set mode-specific text
    If installMode = "usb" Then
        strModeInfo = "USB Mode installation"
    Else
        strModeInfo = "Local installation"
    End If
    
    htaContent = "<!DOCTYPE html>" & _
    "<html>" & _
    "<head>" & _
    "<meta charset='utf-8'>" & _
    "<title>SAGE RAG - Installation Complete</title>" & _
    "<HTA:APPLICATION ID='SAGE_RAG_Finish' APPLICATIONNAME='SAGE RAG Installer' VERSION='1.0' " & _
    "BORDER='THIN' BORDERSTYLE='STATIC' CAPTION='YES' SHOWINTASKBAR='YES' " & _
    "SINGLETHREADED='NO' THREADINGMODEL='APARTMENT' WINDOWSTATE='NORMAL' " & _
    "INNERBORDER='NO' SCROLL='NO' MAXIMIZEBUTTON='NO' MINIMIZEBUTTON='NO' SYSMENU='YES' />" & _
    "<style>" & _
    "* { margin: 0; padding: 0; }" & _
    "body { font-family: Segoe UI, Arial, sans-serif; background: #f0f4f8; overflow: hidden; }" & _
    "table { border-collapse: collapse; }" & _
    ".container { background: white; border-radius: 20px; padding: 50px; box-shadow: 0 20px 60px -12px rgba(59, 130, 246, 0.25); width: 900px; margin: 40px auto; border: 1px solid rgba(219, 234, 254, 0.5); }" & _
    ".layout-table { width: 100%; }" & _
    ".left-section { width: 50%; padding-right: 25px; border-right: 2px solid #e2e8f0; vertical-align: middle; }" & _
    ".right-section { width: 50%; padding-left: 25px; vertical-align: middle; }" & _
    ".logo-box { width: 75px; height: 75px; background: #10b981; border-radius: 16px; text-align: center; line-height: 75px; font-size: 42px; font-weight: 700; color: white; margin-bottom: 24px; }" & _
    ".title { font-size: 42px; font-weight: 800; color: #0f172a; margin-bottom: 10px; }" & _
    ".subtitle { font-size: 13px; color: #64748b; margin-bottom: 24px; font-weight: 600; letter-spacing: 1.2px; text-transform: uppercase; }" & _
    ".description { font-size: 15px; color: #475569; line-height: 1.6; margin-bottom: 35px; }" & _
    ".finish-button { background: #10b981; color: white; border: none; padding: 16px 0; font-size: 16px; font-weight: 700; border-radius: 12px; cursor: pointer; width: 100%; }" & _
    ".finish-button:hover { background: #059669; }" & _
    ".info-item { padding: 16px 18px; background: #f0f9ff; border-radius: 12px; border-left: 4px solid #3b82f6; margin-bottom: 16px; }" & _
    ".info-icon { font-size: 20px; display: inline-block; width: 25px; }" & _
    ".info-text { font-size: 14px; color: #0f172a; display: inline-block; }" & _
    ".info-label { font-weight: 700; }" & _
    ".info-value { color: #64748b; font-size: 13px; }" & _
    "</style>" & _
    "</head>" & _
    "<body>" & _
    "<div class='container'>" & _
    "<table class='layout-table'>" & _
    "<tr>" & _
    "<td class='left-section'>" & _
    "<div class='logo-box'>✓</div>" & _
    "<h1 class='title'>Success!</h1>" & _
    "<p class='subtitle'>INSTALLATION COMPLETE</p>" & _
    "<p class='description'>" & strModeInfo & " completed successfully. Your system is ready to use!</p>" & _
    "<button class='finish-button' onclick='window.close()'>Close Window</button>" & _
    "</td>" & _
    "<td class='right-section'>" & _
    "<div class='info-item'><span class='info-icon'>📦</span><span class='info-text'><span class='info-label'>Status:</span> <span class='info-value'>Ready to use</span></span></div>" & _
    "<div class='info-item'><span class='info-icon'>🔗</span><span class='info-text'><span class='info-label'>Frontend:</span> <span class='info-value'>http://172.31.16.1:8080</span></span></div>" & _
    "<div class='info-item'><span class='info-icon'>⚙️</span><span class='info-text'><span class='info-label'>Backend:</span> <span class='info-value'>http://172.31.16.1:8001</span></span></div>" & _
    "<div class='info-item'><span class='info-icon'>🚀</span><span class='info-text'><span class='info-label'>Next:</span> <span class='info-value'>Use desktop shortcut to launch</span></span></div>" & _
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
    "} catch(e) {} " & _
    "}; " & _
    "</script>" & _
    "</body>" & _
    "</html>"
    
    ' Write HTA file
    Set objFile = objFSO.CreateTextFile(strFilePath, True)
    objFile.Write htaContent
    objFile.Close
End Sub

' ============================================
' FUNCTION: Show Finish Button (Legacy)
' ============================================
Sub ShowFinishButton(objProgressWnd)
    On Error Resume Next
    
    If Not (objProgressWnd Is Nothing) Then
        ' Hide spinner
        objProgressWnd.Document.getElementById("spinner").Style.Display = "none"
        
        ' Update title and message
        objProgressWnd.Document.getElementById("mainTitle").InnerText = "Installation Complete!"
        objProgressWnd.Document.getElementById("logo").InnerText = "✓"
        objProgressWnd.Document.getElementById("successMsg").Style.Display = "block"
        objProgressWnd.Document.getElementById("footerText").InnerText = "Click 'Finish' to close this window"
        
        ' Show button container
        objProgressWnd.Document.getElementById("buttonContainer").Style.Display = "block"
    End If
End Sub

' ============================================
' FUNCTION: Wait For Finish Button
' ============================================
Sub WaitForFinishButton(objProgressWnd)
    On Error Resume Next
    
    Dim bFinishClicked
    bFinishClicked = False
    
    ' Create external object for button callback
    Set objProgressWnd.External = CreateObject("Shell.Application")
    
    ' Add click event handler
    objProgressWnd.Document.getElementById("finishBtn").onclick = GetRef("FinishButtonClick")
    
    ' Wait for button click (poll every 100ms)
    Do
        WScript.Sleep 100
        
        ' Check if page still exists
        On Error Resume Next
        If objProgressWnd.Document Is Nothing Then
            Exit Do
        End If
        On Error GoTo 0
    Loop
End Sub

' Global variable for finish button
Dim bFinishClicked

' ============================================
' FUNCTION: Finish Button Click Handler
' ============================================
Function FinishButtonClick()
    On Error Resume Next
    bFinishClicked = True
End Function

' ============================================
' FUNCTION: Launch Application Silently
' ============================================
Sub LaunchApplicationSilent(appPath)
    On Error Resume Next
    
    Dim strLauncher
    
    strLauncher = appPath & "\autorun\launcher.vbs"
    
    If objFSO.FileExists(strLauncher) Then
        objShell.Run "wscript.exe """ & strLauncher & """", 0, False
    End If
End Sub