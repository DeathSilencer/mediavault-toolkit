# ⚡ Gofile Ultra Batch Downloader & Remuxer

Herramienta de descarga masiva multihilo de alto rendimiento para **Gofile.io** con bypass automático de tokens mediante Chromium headless, auto-conversión sin pérdidas a `.mp4` y soporte para cualquier álbum o carpeta.

---

## ✨ Características Principales

- **Conexiones Paralelas Optimizadas:** Gofile limita las descargas individuales a ~3.5 MB/s. Este bot descarga múltiples archivos en paralelo saturando por completo tu ancho de banda (alcanza más de **17 MB/s** estables).
- **Auto-Bypass de Tokens con Playwright:** Obtiene los tokens de sesión de Gofile automáticamente en segundo plano sin intervención del usuario.
- **Auto-Detección y Modo Universal:** Pega cualquier URL o ID (`https://gofile.io/d/XXXXXX`) y el bot detecta el nombre del álbum, crea la carpeta en tu disco de destino y organiza los archivos.
- **Descarga Ordenada por Tamaño:** Ordena los archivos de mayor a menor tamaño para priorizar los contenidos más pesados.
- **Reanudación por Byte (.part):** Si se interrumpe la conexión o cierras la consola, el bot reanuda cada descarga exactamente en el byte donde se quedó.
- **Auto-Conversión sin Pérdidas (FFmpeg Remuxing):** Convierte automáticamente archivos `.MOV`, `.m4v` o contenedores de Apple a formato `.MP4` estándar mediante copia de flujo (*Stream Copy*, sin recodificar y en menos de 1 segundo por archivo).
- **Auto-Instalador Integrado:** Si faltan librerías de Python (`requests`, `rich`, `playwright`) o binarios del sistema (`ffmpeg`), el script los descarga e instala automáticamente.

---

## 🚀 Uso Rápido

### Opción 1: Lanzador Directo (.bat)
Haz doble clic en:
```cmd
iniciar_descarga.bat
```

### Opción 2: Desde Consola
```bash
python gofile_downloader.py
```

### Parámetros Opcionales (CLI):
```bash
# Descargar un álbum directamente por URL o ID
python gofile_downloader.py --url https://gofile.io/d/cWUx4ngb

# Especificar carpeta de destino personalizada
python gofile_downloader.py --url cWUx4ngb --output "D:\MisVideos\Album1"

# Cambiar el número de descargas simultáneas (por defecto: 3)
python gofile_downloader.py --workers 4

# Aceptar confirmaciones automáticamente
python gofile_downloader.py --yes
```

---

## 🛠️ Requisitos
- **Python 3.10+**
- **FFmpeg** (Instalado en el sistema o auto-descargado en `bin/`)
- Conexión a Internet
