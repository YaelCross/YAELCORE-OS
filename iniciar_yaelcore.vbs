' Inicia YAELCORE-OS en segundo plano (sin ventana de consola).
' Lo usa el inicio automatico de Windows, pero tambien puedes
' darle doble clic para abrir el sistema.
'
' Con el argumento /inicio espera unos segundos antes de arrancar,
' para que Windows termine de cargar el escritorio, el audio y la red.
'
' Cada arranque queda anotado en logs\lanzador.log y los errores de
' Python en logs\yaelcore.log.

Set fso = CreateObject("Scripting.FileSystemObject")
Set shell = CreateObject("WScript.Shell")

carpeta = fso.GetParentFolderName(WScript.ScriptFullName)
shell.CurrentDirectory = carpeta

carpetaLogs = carpeta & "\logs"
If Not fso.FolderExists(carpetaLogs) Then fso.CreateFolder carpetaLogs

Sub Anotar(texto)
    Set archivoLog = fso.OpenTextFile(carpetaLogs & "\lanzador.log", 8, True)
    archivoLog.WriteLine Now & "  " & texto
    archivoLog.Close
End Sub

esInicio = False
For Each arg In WScript.Arguments
    If LCase(arg) = "/inicio" Then esInicio = True
Next

If esInicio Then
    Anotar "Inicio automatico de Windows: esperando 20 segundos..."
    WScript.Sleep 20000
End If

python = carpeta & "\.venv\Scripts\pythonw.exe"

If Not fso.FileExists(python) Then
    Anotar "ERROR: no se encontro " & python
    MsgBox "No se encontro el entorno virtual:" & vbCrLf & python & vbCrLf & vbCrLf & _
        "Crea el entorno .venv e instala las dependencias antes de iniciar YAELCORE-OS.", _
        vbCritical, "YAELCORE-OS"
    WScript.Quit 1
End If

Anotar "Arrancando YAELCORE-OS"
shell.Run """" & python & """ """ & carpeta & "\main.py""", 0, False
