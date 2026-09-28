# 🛡️ Pixeldrain Smart Quota Downloader & Manager

Bot automatizado para descargar álbumes completos de **Pixeldrain** con control en tiempo real de la cuota diaria gratuita de 6 GB, detección de límites por WebSocket, cambio de VPN/IP en caliente y auto-conversión sin pérdidas a `.mp4`.

---

## ✨ Características Principales

- **Gestor Inteligente de Cuota (6 GB/día):** Pixeldrain impone un límite de 6 GB de descarga diaria por IP pública. El bot consulta en vivo a través de WebSockets (`wss://pixeldrain.com/api/file_stats`) los bytes exactos disponibles.
- **Protección Preventiva:** Antes de iniciar cualquier descarga pesada, el bot calcula si el archivo cabe en la cuota restante. Si se fuera a exceder, **se pausa automáticamente** para no dejar descargas incompletas ni desperdiciar tu cuota.
- **Cambio de VPN en Caliente (Bypass de Límite sin Esperar 24h):**
  - Dado que el límite de Pixeldrain está ligado a la **dirección IP**, cuando la cuota se agota el bot entra en pausa interactiva.
  - Al activar o cambiar de servidor en tu VPN (Cloudflare WARP, ProtonVPN, etc.) y pulsar `[Enter]`, el bot verifica la nueva IP al instante y continúa descargando con otros 6 GB frescos. ¡Permite descargar álbumes de 50+ GB el mismo día!
- **Modo Universal:** Acepta cualquier enlace o ID de álbum (`https://pixeldrain.com/l/XXXXXX`).
- **Auto-Conversión sin Pérdidas:** Convierte archivos `.m4v` o contenedores QuickTime a `.MP4` estándar mediante copia de flujo en FFmpeg.
- **Auto-Instalador:** Comprueba e instala automáticamente librerías faltantes (`requests`, `rich`, `websockets`, `ffmpeg`).

---

## 🚀 Uso Rápido

### Opción 1: Lanzador Directo (.bat)
Haz doble clic en:
```cmd
iniciar_pixeldrain.bat
```

### Opción 2: Desde Consola
```bash
python pixeldrain_downloader.py
```

### Parámetros Opcionales (CLI):
```bash
# Descargar un álbum específico
python pixeldrain_downloader.py --url https://pixeldrain.com/l/2U1rM5UC

# Especificar carpeta de salida personalizada
python pixeldrain_downloader.py --url 2U1rM5UC --output "D:\MisVideos\PixeldrainAlbum"
```

---

## 🛠️ Requisitos
- **Python 3.10+**
- **FFmpeg** (Instalado o auto-descargado)
- Cliente VPN opcional para rotación de cuota (Cloudflare WARP, etc.)
