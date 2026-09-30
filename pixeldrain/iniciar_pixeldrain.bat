@echo off
title Descargador Pixeldrain - Modo Universal

:: 1. Verificar si Python esta instalado
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ========================================================
    echo  [!] Python no detectado en el sistema.
    echo  [*] Intentando instalar Python automaticamente...
    echo ========================================================
    winget install --id Python.Python.3.11 -e --accept-source-agreements --accept-package-agreements
    if %errorlevel% neq 0 (
        echo [X] No se pudo instalar Python de forma automatica.
        echo Descargalo manualmente desde: https://www.python.org/
        pause
        exit /b 1
    )
)

echo ========================================================
echo       BOT DESCARGADOR DE PIXELDRAIN (MODO UNIVERSAL)
echo   - Auto-instalacion de dependencias y herramientas
echo   - Pega cualquier enlace o ID de album de Pixeldrain
echo   - Proteccion activa de limite diario de 6 GB
echo   - Cambio de VPN / Cloudflare en caliente
echo   - Auto-deteccion de nombre y creacion de carpeta
echo ========================================================
echo.

python "%~dp0pixeldrain_downloader.py" %*
pause
