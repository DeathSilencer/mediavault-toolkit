@echo off
setlocal
title MediaVault Toolkit - Panel Principal

:: 1. Verificacion e instalacion automatica de Python si no existe
where python >nul 2>&1
if errorlevel 1 goto INSTALL_PYTHON
python -V >nul 2>&1
if errorlevel 1 goto INSTALL_PYTHON
goto PYTHON_OK

:INSTALL_PYTHON
echo ========================================================
echo  [!] Python no detectado en el sistema.
echo  [*] Instalando Python 3.11 automaticamente via Winget...
echo ========================================================
winget install --id Python.Python.3.11 -e --accept-source-agreements --accept-package-agreements
if errorlevel 1 (
    echo.
    echo [X] No se pudo instalar Python automaticamente con Winget.
    echo Por favor descarga e instala Python manualmente desde:
    echo https://www.python.org/downloads/
    echo (Asegurate de marcar la casilla "Add python.exe to PATH")
    echo.
    pause
    exit /b 1
)
echo [*] Python instalado correctamente. Por favor vuelve a abrir launcher.bat.
pause
exit /b 0

:PYTHON_OK

:: 2. Auto-instalacion de dependencias si faltan
if exist "%~dp0requirements.txt" (
    python -c "import rich, requests, websockets, playwright" >nul 2>&1
    if errorlevel 1 (
        echo ========================================================
        echo  [*] Configurando librerias del toolkit por primera vez...
        echo ========================================================
        python -m pip install --upgrade pip >nul 2>&1
        python -m pip install -r "%~dp0requirements.txt"
        python -m playwright install chromium
        echo [*] Dependencias instaladas con exito.
        ping -n 2 127.0.0.1 >nul 2>&1
    )
)

:MENU
cls
echo ========================================================
echo        MEDIAVAULT TOOLKIT - PANEL PRINCIPAL
echo ========================================================
echo.
echo   [1] Descargador de Gofile (Multi-conexiones y Auto-MP4)
echo   [2] Descargador de Pixeldrain (Cuota 6GB y VPN Hot-Swap)
echo   [3] Compresor Masivo de Video por GPU (NVIDIA RTX / NVENC)
echo   [4] Subidor Automatico a Bunkr (Videos, RAR y Chunks 95MB)
echo   [5] Salir
echo.
echo ========================================================
choice /c 12345 /n /m "Selecciona una opcion [1-5]: "

if errorlevel 5 goto OP5
if errorlevel 4 goto OP4
if errorlevel 3 goto OP3
if errorlevel 2 goto OP2
if errorlevel 1 goto OP1
goto MENU

:OP1
call "%~dp0gofile\iniciar_descarga.bat"
goto MENU

:OP2
call "%~dp0pixeldrain\iniciar_pixeldrain.bat"
goto MENU

:OP3
call "%~dp0compressor\comprimir_videos.bat"
goto MENU

:OP4
call "%~dp0bunkr\subir_bunkr.bat"
goto MENU

:OP5
exit /b 0
