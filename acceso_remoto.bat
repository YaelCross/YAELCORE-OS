@echo off
chcp 65001 >nul
title YAELCORE-OS - Acceso de respaldo
cd /d "%~dp0"
set PUERTO=8765
for /f "tokens=2 delims==" %%a in ('findstr /b "CENTRO_PUERTO=" .env 2^>nul') do set PUERTO=%%a
where cloudflared >nul 2>nul
if errorlevel 1 (
  echo  Falta instalar Cloudflare. Ejecuta una sola vez en PowerShell:
  echo    winget install --id Cloudflare.cloudflared
  echo  Luego cierra y vuelve a abrir este archivo.
  pause
  exit /b 1
)
echo.
echo  ACCESO DE RESPALDO - usalo si la red de la oficina falla o alguien esta fuera.
echo  El Centro de Mando debe estar encendido en otra ventana.
echo  Copia la liga https://....trycloudflare.com que aparece abajo y compartela.
echo  La liga funciona mientras esta ventana siga abierta. Cambia cada vez.
echo.
cloudflared tunnel --url http://localhost:%PUERTO%
pause
