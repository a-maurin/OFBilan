Set shell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")

' Dossier Bilans_production
scriptDir = WScript.ScriptFullName
scriptDir = Left(scriptDir, InStrRev(scriptDir, "\") - 1)

' Priorité au pythonw du .venv local si présent.
venvPythonw = scriptDir & "\.venv\Scripts\pythonw.exe"
If fso.FileExists(venvPythonw) Then
    pythonExe = """" & venvPythonw & """"
Else
    pythonExe = "pythonw"
End If

' Commande à exécuter : interface GUI tools\config_profils.py
cmd = "cmd /c cd /d """ & scriptDir & """ && " & pythonExe & " ""tools\config_profils.py"""

' 0 = fenêtre cachée, False = ne pas attendre la fin
shell.Run cmd, 0, False