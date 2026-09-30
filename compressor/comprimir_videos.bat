@echo off
title Compresor de Videos Masivo por GPU (NVIDIA RTX / HEVC)

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
echo       COMPRESOR MASIVO DE VIDEO POR HARDWARE (GPU NVENC)
echo   - Reduce 50%% - 65%% del tamano sin perdida visible
echo   - Audio 100%% original bit a bit (Stream Copy)
echo   - Acelerado por hardware con GPU NVIDIA RTX
echo ========================================================
echo.

python "%~dp0video_compressor.py" %*
pause
