@echo off
title Bot Subidor a Bunkr (Modo Universal y Personalizable)

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
echo   - Personalizable: Token, Album y Carpetas dinamicos
echo   - Orden: Del mas grande al mas chico (uno por uno)
echo   - Reintentos continuos si se traba en 0%% o falla
echo   - Deteccion de videos ya subidos para no duplicar
echo ========================================================
echo.

python "%~dp0bunkr_uploader.py" %*
pause
