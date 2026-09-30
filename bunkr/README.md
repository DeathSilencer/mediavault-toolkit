# ☁️ Bunkr Ultra Uploader Bot

Bot automatizado de subida masiva a **Bunkr.cr** con control de chunks (95 MB), reintentos infinitos anti-congelamiento, rotación automática de nodos de servidor y memoria anti-duplicados por álbum.

---

## ✨ Características Principales

- **Orden Descendente (Mayor a Menor):** Escanea tu carpeta local y prioriza los archivos más pesados primero, subiéndolos uno por uno.
- **Protocolo de Chunks Oficial (95 MB):** Utiliza la misma arquitectura de Dropzone/Chibisafe que la web oficial de Bunkr, segmentando videos en bloques de 95 MB.
- **Reintentos Infinitos Anti-Error (Cero Atascos en 0%):** Si un bloque se traba, se corta la conexión o el servidor devuelve error (500, 502, timeout), el bot reintenta de forma automática el mismo bloque hasta completarlo.
- **Rotación de Servidor en Caliente:** Si un nodo de subida (`n49`, `n50`, `n51`) presenta fallas persistentes, el bot consulta la API de Bunkr y cambia dinámicamente a otro nodo activo sin cancelar el archivo.
- **Detección Anti-Duplicados:**
  - Consulta en vivo tu álbum objetivo (ej. `SoyMafe By:@DeathSilencer`) para omitir los videos que ya existen.
  - Guarda un registro local atómico (`.bunkr_upload_history.json`).
- **Pausa y Reanudación Segura:** Puedes presionar `Ctrl+C` para pausar en cualquier momento; al volver a abrir, continuará exactamente con los videos faltantes.

---

## 🚀 Uso Rápido

### Opción 1: Lanzador Directo (.bat)
Haz doble clic en:
```cmd
subir_bunkr.bat
```

### Opción 2: Desde Consola
```bash
python bunkr_uploader.py
```

---

## 🛠️ Requisitos
- **Python 3.10+**
- Librerías: `requests`, `rich` (se auto-instalan al ejecutar)
- Conexión a Internet
