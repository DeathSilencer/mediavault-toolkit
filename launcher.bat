@echo off
chcp 65001 > nul
title MediaVault Toolkit - Panel Principal

:MENU
cls
echo ========================================================
echo        🎬 MEDIAVAULT TOOLKIT - PANEL PRINCIPAL
echo ========================================================
echo.
echo   [1] ⚡ Descargador de Gofile (Multi-conexiones y Auto-MP4)
echo   [2] 🛡️ Descargador de Pixeldrain (Cuota 6GB y VPN Hot-Swap)
echo   [3] 🚀 Compresor Masivo de Video por GPU (NVIDIA RTX / NVENC)
echo   [4] 🚪 Salir
echo.
echo ========================================================
set /p OPCION="Selecciona una opción [1-4]: "

if "%OPCION%"=="1" (
    call "%~dp0iniciar_descarga.bat"
    goto MENU
)
if "%OPCION%"=="2" (
    call "%~dp0pixeldrain\iniciar_pixeldrain.bat"
    goto MENU
)
if "%OPCION%"=="3" (
    call "%~dp0comprimir_videos.bat"
    goto MENU
)
if "%OPCION%"=="4" (
    exit /b
)

echo [!] Opción no válida.
timeout /t 2 > nul
goto MENU
