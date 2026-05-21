' Lance l'interface de configuration des profils YAML (schema_ui.yaml).
Option Explicit

Dim shell, fso, scriptDir, venvPythonw, pythonExe, cmd, errMsg

Set shell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")

scriptDir = fso.GetParentFolderName(WScript.ScriptFullName)
venvPythonw = scriptDir & "\.venv\Scripts\pythonw.exe"

If fso.FileExists(venvPythonw) Then
    pythonExe = """" & venvPythonw & """"
Else
    pythonExe = "pythonw"
    If Not fso.FileExists(scriptDir & "\tools\config_profils.py") Then
        errMsg = "Fichier introuvable : tools\config_profils.py"
        MsgBox errMsg, vbCritical, "Configurer les profils"
        WScript.Quit 1
    End If
End If

' Fenêtre visible si Python manque ; sinon lancement silencieux de l'interface Tk.
cmd = "cmd /c cd /d """ & scriptDir & """ && " & pythonExe & " ""tools\config_profils.py"""
Dim exitCode
exitCode = shell.Run(cmd, 0, True)

If exitCode <> 0 Then
    errMsg = "L'interface n'a pas pu démarrer (code " & exitCode & ")." & vbCrLf & vbCrLf
    errMsg = errMsg & "Vérifiez que le projet est installé :" & vbCrLf
    errMsg = errMsg & "  .venv\Scripts\pythonw.exe" & vbCrLf
    errMsg = errMsg & "  pip install pyyaml" & vbCrLf & vbCrLf
    errMsg = errMsg & "Relance en mode diagnostic (fenêtre visible) ?"
    If MsgBox(errMsg, vbYesNo + vbExclamation, "Configurer les profils") = vbYes Then
        cmd = "cmd /k cd /d """ & scriptDir & """ && python ""tools\config_profils.py"""
        shell.Run cmd, 1, False
    End If
End If
