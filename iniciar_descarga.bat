@echo off
chcp 65001 > nul
title Descargador Gofile - Modo Universal

:: 1. Verificar si Python está instalado
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ========================================================
    echo  [!] Python no detectado en el sistema.
    echo  [!] Intentando instalar Python automaticamente...
    echo ========================================================
    winget install --id Python.Python.3.11 -e --accept-source-agreements --accept-package-agreements
    if %errorlevel% neq 0 (
        echo [X] No se pudo instalar Python de forma automatica.
        echo Descargalo manualmente desde: https://www.python.org/
        pause
        exit /b
    )
)

echo ========================================================
echo        BOT DESCARGADOR DE GOFILE (MODO UNIVERSAL)
echo   - Auto-instalacion de dependencias y herramientas
echo   - Pega cualquier enlace o ID de Gofile
echo   - Auto-deteccion de nombre y creacion de carpeta
echo   - Descargas paralelas de alta velocidad y auto-MP4
echo ========================================================
echo.

python "%~dp0gofile_downloader.py" %*
pause
