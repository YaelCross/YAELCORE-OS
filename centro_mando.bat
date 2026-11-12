@echo off
cd /d "%~dp0"
title YAELCORE-OS - Centro de Mando

rem Usa el entorno .venv si existe; si no, el Python instalado en Windows.
set "PY=%~dp0.venv\Scripts\python.exe"
if not exist "%PY%" (
    where py >NUL 2>NUL && (set "PY=py") || (set "PY=python")
)

echo Iniciando Centro de Mando con: %PY%
echo NO cierres esta ventana: si la cierras, la pagina deja de funcionar.
echo.
"%PY%" "%~dp0centro_mando.py"

echo.
echo El Centro de Mando se detuvo. Si ves un error arriba, mandale una captura a Claude.
pause
