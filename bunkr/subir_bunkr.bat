@echo off
title Bot Subidor a Bunkr (Universal - Videos y RAR)

:: Verificacion e instalacion automatica de Python si no existe
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ========================================================
    echo  [!] Python no detectado en el sistema.
    echo  [*] Instalando Python 3.11 automaticamente via Winget...
    echo ========================================================
    winget install --id Python.Python.3.11 -e --accept-source-agreements --accept-package-agreements
    if %errorlevel% neq 0 (
        echo [X] No se pudo instalar Python automaticamente.
        echo Por favor instalalo desde: https://www.python.org/
        pause
        exit /b 1
    )
)

echo ========================================================
echo        BOT SUBIDOR AUTOMATICO A BUNKR.CR (UNIVERSAL)
echo   - Soporte: Videos (.MP4, .MKV) y Archivos (.RAR, .ZIP, .7Z)
echo   - Personalizable: Token, Album y Carpetas dinamicos
echo   - Deteccion automatica de volumenes divididos (part01...part99)
echo   - Reintentos continuos si se traba en 0%% o falla
echo   - Deteccion de archivos ya subidos para no duplicar
echo ========================================================
echo.

python "%~dp0bunkr_uploader.py" %*
pause
