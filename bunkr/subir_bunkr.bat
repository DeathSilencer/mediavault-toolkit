@echo off
chcp 65001 > nul
title Bot Subidor a Bunkr (Modo Universal y Personalizable)

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
