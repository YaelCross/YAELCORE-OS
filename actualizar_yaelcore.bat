@echo off
REM Descarga la ultima version de YAELCORE-OS desde GitHub
REM e instala las dependencias nuevas.

cd /d "%~dp0"

where git >nul 2>nul
if errorlevel 1 (
    echo [!] Falta instalar Git: https://git-scm.com/download/win
    pause
    exit /b 1
)

git pull origin main
if errorlevel 1 (
    echo [!] No se pudo descargar la actualizacion. Revisa el mensaje de arriba.
    pause
    exit /b 1
)

if exist "%~dp0.venv\Scripts\python.exe" (
    "%~dp0.venv\Scripts\python.exe" -m pip install -r requirements.txt
) else (
    echo [!] No existe .venv. Crea el entorno virtual e instala las dependencias.
)

echo.
echo [OK] YAELCORE-OS actualizado. Abrelo de nuevo con jarvis.bat
pause
