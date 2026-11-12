@echo off
REM Revisa por que YAELCORE-OS no arranca al encender la computadora.
REM Muestra el estado del acceso directo y los ultimos registros.

cd /d "%~dp0"

set "DESTINO=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\YAELCORE-OS.lnk"

echo ==================================================
echo   DIAGNOSTICO DE INICIO AUTOMATICO - YAELCORE-OS
echo ==================================================
echo.

echo [1] Acceso directo en la carpeta Inicio:
if exist "%DESTINO%" (
    echo     OK - existe
) else (
    echo     FALTA - ejecuta instalar_inicio_automatico.bat
)
echo.

echo [2] Python del entorno virtual:
if exist "%~dp0.venv\Scripts\pythonw.exe" (
    echo     OK - .venv\Scripts\pythonw.exe existe
) else (
    echo     FALTA - no existe .venv\Scripts\pythonw.exe
)
echo.

echo [3] Esta desactivado en el Administrador de tareas?
reg query "HKCU\Software\Microsoft\Windows\CurrentVersion\Explorer\StartupApproved\StartupFolder" /v "YAELCORE-OS.lnk" 2>nul | findstr /i "REG_BINARY" | findstr /r "REG_BINARY *0[13]" >nul
if errorlevel 1 (
    echo     OK - no aparece como desactivado
) else (
    echo     DESACTIVADO - abre el Administrador de tareas, pestana
    echo     "Aplicaciones de arranque", y activa YAELCORE-OS
)
echo.

echo [4] Ultimos arranques del lanzador (logs\lanzador.log):
if exist "logs\lanzador.log" (
    powershell -NoProfile -Command "Get-Content -Tail 10 'logs\lanzador.log'"
) else (
    echo     Sin registros: el lanzador nunca se ha ejecutado.
)
echo.

echo [5] Ultimos mensajes de YAELCORE-OS (logs\yaelcore.log):
if exist "logs\yaelcore.log" (
    powershell -NoProfile -Command "Get-Content -Tail 30 'logs\yaelcore.log'"
) else (
    echo     Sin registros todavia.
)
echo.

pause
