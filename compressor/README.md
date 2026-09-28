# 🚀 Hardware-Accelerated Video Batch Compressor (NVIDIA RTX & CPU)

Compresor masivo de video de alto rendimiento diseñado para reducir el tamaño de bibliotecas y colecciones de video entre un **45% y 65%** manteniendo una calidad visual idéntica (*visually lossless*) y el audio original intacto bit a bit.

---

## ✨ Características Principales

- **Aceleración por Hardware NVENC (NVIDIA RTX):** Aprovecha los codificadores NVENC dedicados de tarjetas gráficas modernas (GeForce RTX 30/40/50 Series), procesando videos 1080p a más de 300-500 FPS (~2.5 segundos por video).
- **Fallback Automático a CPU:** Si no se detecta una GPU NVIDIA compatible, cambia de forma transparente al codificador multihilo de alta eficiencia `libx265`.
- **Audio Intacto (Stream Copy):** Copia directamente el flujo de audio original (`-c:a copy` / `-map 0:a?`) sin recodificar ni degradar la calidad sonora, ahorrando tiempo de procesamiento.
- **Triple Blindaje de Seguridad e Integridad:**
  1. **Archivo Temporal Aislado (`.tmp.mp4`):** El archivo original jamás se modifica durante la codificación.
  2. **Validación Exhaustiva con `ffprobe`:** Comprueba la integridad del contenedor y valida que la duración del video coincida con el original con un margen de tolerancia estricto (±1.5s).
  3. **Protección de Tamaño:** Si un video ya estaba muy optimizado y el archivo comprimido resulta de mayor tamaño, se conserva el original.
- **Regla de Exclusión Inteligente (`.M`):** Omite automáticamente archivos cuyo título contenga o empiece con `.M` para proteger colecciones maestras o videos previamente procesados.
- **Orden de Procesamiento Descendente:** Ordena la cola del video más grande al más chico para liberar la mayor cantidad de gigabytes en los primeros minutos.
- **Modos de Salida Seguros:**
  - *Modo Seguro:* Guarda en subcarpeta `Comprimidos/` manteniendo los archivos originales intactos.
  - *Reemplazo Verificado:* Reemplaza el original únicamente tras verificar con éxito la prueba de integridad.

---

## 📊 Perfiles de Compresión

| Perfil | Parámetro NVENC | Ahorro Estimado | Uso Recomendado |
| :--- | :--- | :--- | :--- |
| **Óptimo (Recomendado)** | `CQ 29` (Preset P7 Multipass) | **~50% - 60%** | Mejor balance entre ahorro masivo y fidelidad visual indistinguible. |
| **Máxima Fidelidad** | `CQ 27` (Preset P7 Multipass) | **~40% - 48%** | Calidad idéntica al máster de cámara. |
| **Máximo Ahorro** | `CQ 31` (Preset P7 Multipass) | **~65% - 70%** | Para bibliotecas gigantes donde prima el espacio en disco. |

---

## 🚀 Uso Rápido

### Lanzador Directo (.bat)
```cmd
comprimir_videos.bat
```

### Desde Consola (Python)
```bash
python video_compressor.py
```

---

## 🛠️ Requisitos
- **Python 3.10+**
- **FFmpeg & FFprobe** con soporte NVENC habilitado
- Tarjeta Gráfica NVIDIA con drivers actualizados (o procesador con soporte SSE/AVX)
