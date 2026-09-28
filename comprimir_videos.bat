@echo off
chcp 65001 > nul
title Compresor de Videos Masivo por GPU (NVIDIA RTX 5070 / HEVC)

echo ========================================================
echo       COMPRESOR MASIVO DE VIDEO POR HARDWARE (GPU NVENC)
echo   - Reduce 50%% - 65%% del tamano sin perdida visible
echo   - Audio 100%% original bit a bit (Stream Copy)
echo   - Acelerado por hardware con NVIDIA RTX 5070
echo ========================================================
echo.

python "%~dp0video_compressor.py" %*
pause
