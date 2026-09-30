# ☁️ Bunkr Ultra Uploader Bot (Universal y Personalizable)

Bot automatizado de subida masiva a **Bunkr.cr** con control de chunks (95 MB), reintentos infinitos anti-congelamiento, rotación automática de nodos de servidor, selección interactiva de álbumes y memoria anti-duplicados.

---

## ✨ Características Principales

- **100% Personalizable y Cero Hardcodeo:**
  - Token, álbum destino y carpeta de origen son dinámicos e interactivos.
  - Guarda tus preferencias en `.bunkr_config.json` (ignorado por Git para máxima privacidad) para no tener que escribirlos de nuevo: basta presionar `[Enter]`.
- **Gestión Inteligente de Álbumes:**
  - Consulta en tiempo real tus álbumes en Bunkr vía API.
  - Permite seleccionar de tu lista numerada, pegar un link directo (ej. `https://bunkr.cr/a/OKS37rXx`), ingresar un ID numérico o crear un álbum nuevo al instante.
- **Orden Descendente (Mayor a Menor):**
  - Escanea tu carpeta local y prioriza los archivos más pesados primero, subiéndolos uno por uno.
- **Protocolo de Chunks Oficial (95 MB):**
  - Utiliza la arquitectura por bloques multipart estándar de Bunkr, segmentando videos en bloques de 95 MB.
- **Reintentos Infinitos Anti-Error (Cero Atascos en 0%):**
  - Si un bloque se traba, se corta la conexión o el servidor devuelve error (500, 502, timeout), el bot reintenta de forma automática el mismo bloque hasta completarlo al 100%.
- **Rotación de Servidor en Caliente:**
  - Si un nodo de subida (`n49`, `n50`, `n51`, etc.) presenta fallas persistentes, el bot consulta la API de Bunkr y cambia dinámicamente a otro nodo activo sin perder el archivo.
- **Detección Anti-Duplicados:**
  - Consulta los archivos ya presentes en tu álbum para omitir los que ya existen.
  - Guarda un registro local atómico (`.bunkr_upload_history.json`).
- **Pausa y Reanudación Segura:**
  - Puedes presionar `Ctrl+C` para pausar en cualquier momento; al volver a abrir, continuará exactamente con los videos faltantes.

---

## 🚀 Modos de Uso

### 1. Modo Interactivo (Recomendado)
Doble clic en:
```cmd
subir_bunkr.bat
```
El bot te solicitará tu token (la primera vez), tu carpeta y tu álbum, recordando todo para las siguientes sesiones con solo pulsar `[Enter]`.

### 2. Modo Línea de Comandos (Automatización y Scripts)
```bash
# Uso interactivo estándar:
python bunkr_uploader.py

# Especificando parámetros directamente:
python bunkr_uploader.py --token "TU_TOKEN" --album "123456" --folder "D:\MisVideos" --yes
```

### Opciones CLI Disponibles:
| Opción | Descripción |
| :--- | :--- |
| `--token`, `-t` | Token de autenticación de Bunkr (desde cookies `token`) |
| `--album`, `-a` | ID numérico, identificador (slug), URL o nombre del álbum |
| `--folder`, `-f` | Carpeta de videos a procesar |
| `--yes`, `-y` | Inicia la subida sin confirmaciones previas |

---

## 🔑 ¿Cómo obtener tu Token de Bunkr?
1. Inicia sesión en [dash.bunkr.cr](https://dash.bunkr.cr) o [bunkr.cr](https://bunkr.cr).
2. Presiona `F12` en tu navegador para abrir las herramientas de desarrollador.
3. Ve a la pestaña **Application** (o **Almacenamiento**) ➔ **Cookies** ➔ `https://bunkr.cr`.
4. Copia el valor del campo llamado **`token`**.

---

## 🛠️ Requisitos
- **Python 3.10+**
- Librerías: `requests`, `rich` (se instalan solas al ejecutar)
- Conexión a Internet
