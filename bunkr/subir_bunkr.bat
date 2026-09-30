@echo off
chcp 65001 > nul
title Bot Subidor a Bunkr (Reintentos Infinitos - SoyMafe)

echo ========================================================
echo        BOT SUBIDOR AUTOMATICO A BUNKR.CR
echo   - Album: SoyMafe By:@DeathSilencer
echo   - Orden: Del mas grande al mas chico (uno por uno)
echo   - Reintentos continuos si se traba en 0%% o falla
echo   - Deteccion de videos ya subidos para no duplicar
echo ========================================================
echo.

python "%~dp0bunkr_uploader.py" %*
pause
