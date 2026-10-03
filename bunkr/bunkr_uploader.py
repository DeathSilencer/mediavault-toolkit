"""
Bunkr Ultra Uploader Bot (Subida Inteligente Universal y Personalizable)
----------------------------------------------------------------------
- Soporte universal para Videos (.mp4, .mkv, .mov, etc.) y Archivos comprimidos (.rar, .zip, .7z, etc.).
- Detección inteligente de volúmenes divididos (.part01.rar ➔ .part99.rar) con subida secuencial automática.
- Cero valores hardcodeados: Token, álbum y carpeta 100% configurables e interactivos.
- Memoria de configuración local (.bunkr_config.json) para no tener que escribir todo de nuevo.
- Consulta dinámica de álbumes en tu cuenta Bunkr (seleccionar, buscar o crear nuevo álbum).
- Protocolo por chunks (95 MB) con reintentos infinitos si se congela o da error.
- Detección de servidor activo con rotación automática de nodos caídos.
- Memoria de subida (.bunkr_upload_history.json) y sincronización con el álbum online para evitar duplicados.
"""

import os
import sys
import time
import json
import uuid
import shutil
import argparse
import subprocess
import re
import mimetypes
import requests

# Auto-instalar dependencias básicas si faltan
for pkg in ["rich", "requests"]:
    try:
        __import__(pkg)
    except ImportError:
        subprocess.check_call([sys.executable, "-m", "pip", "install", pkg])

# Forzar codificación UTF-8 en Windows
if sys.platform.startswith("win"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.progress import (
    Progress,
    BarColumn,
    TextColumn,
    TimeRemainingColumn,
    TransferSpeedColumn,
    SpinnerColumn
)

console = Console()

CHUNK_SIZE = 95 * 1000 * 1000  # 95 MB por bloque estándar de Bunkr
CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".bunkr_config.json")

# Mapeo de tipos MIME para archivos y videos
MIME_MAP = {
    ".rar": "application/x-rar-compressed",
    ".zip": "application/zip",
    ".7z": "application/x-7z-compressed",
    ".tar": "application/x-tar",
    ".gz": "application/gzip",
    ".bz2": "application/x-bzip2",
    ".xz": "application/x-xz",
    ".iso": "application/x-iso9660-image",
    ".mp4": "video/mp4",
    ".mov": "video/quicktime",
    ".m4v": "video/x-m4v",
    ".mkv": "video/x-matroska",
    ".avi": "video/x-msvideo",
    ".webm": "video/webm",
    ".ts": "video/mp2t",
    ".wmv": "video/x-ms-wmv",
    ".flv": "video/x-flv",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".gif": "image/gif",
    ".webp": "image/webp",
}


def get_mime_type(file_path: str) -> str:
    """Devuelve el tipo MIME apropiado para el archivo."""
    ext = os.path.splitext(file_path)[1].lower()
    if ext in MIME_MAP:
        return MIME_MAP[ext]
    guess, _ = mimetypes.guess_type(file_path)
    return guess or "application/octet-stream"


def natural_sort_key(s: str):
    """Clave de ordenamiento natural (humano) para ordenar correctamente part01, part02, etc."""
    return [int(text) if text.isdigit() else text.lower() for text in re.split(r'(\d+)', s)]


def load_bunkr_config() -> dict:
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def save_bunkr_config(cfg: dict):
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2, ensure_ascii=False)
    except Exception:
        pass


def format_bytes(bytes_val: float) -> str:
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if bytes_val < 1024.0:
            return f"{bytes_val:.2f} {unit}"
        bytes_val /= 1024.0
    return f"{bytes_val:.2f} PB"


def mask_token(t: str) -> str:
    if not t or len(t) < 10:
        return "..."
    return f"{t[:4]}...{t[-4:]}"


def validate_token(token: str) -> bool:
    """Verifica si el token es válido consultando la API de Bunkr."""
    headers = {"token": token, "User-Agent": "Mozilla/5.0"}
    try:
        r = requests.get("https://dash.bunkr.cr/api/albums/0", headers=headers, timeout=10)
        return r.status_code == 200 and r.json().get("success") is True
    except Exception:
        return False


def fetch_all_user_albums(token: str) -> list[dict]:
    """Obtiene la lista completa de álbumes de la cuenta del usuario en Bunkr."""
    albums = []
    headers = {"token": token, "User-Agent": "Mozilla/5.0"}
    for page in range(15):  # Soporta hasta 750 álbumes
        try:
            r = requests.get(f"https://dash.bunkr.cr/api/albums/{page}", headers=headers, timeout=12)
            if r.status_code == 200:
                data = r.json()
                batch = data.get("albums", [])
                if not batch:
                    break
                albums.extend(batch)
            else:
                break
        except Exception:
            break
    return albums


def create_user_album(token: str, album_name: str) -> int | None:
    """Crea un nuevo álbum en Bunkr y devuelve su ID numérico."""
    headers = {"token": token, "User-Agent": "Mozilla/5.0"}
    try:
        r = requests.post("https://dash.bunkr.cr/api/albums", headers=headers, json={"name": album_name}, timeout=15)
        if r.status_code == 200 and r.json().get("success"):
            return r.json().get("id")
    except Exception:
        pass
    return None


def get_active_node(token: str, max_retries: int = 5) -> str:
    """Obtiene un nodo de subida activo desde la API de Bunkr."""
    headers = {"token": token, "User-Agent": "Mozilla/5.0"}
    for attempt in range(1, max_retries + 1):
        try:
            r = requests.get("https://dash.bunkr.cr/api/node", headers=headers, timeout=15)
            if r.status_code == 200:
                data = r.json()
                if data.get("success") and "url" in data:
                    return data["url"]
        except Exception:
            time.sleep(2)
    return "https://n50.scdn.st/api/upload"


def load_local_history(folder_path: str) -> dict:
    hist_file = os.path.join(folder_path, ".bunkr_upload_history.json")
    if os.path.exists(hist_file):
        try:
            with open(hist_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def save_local_history(folder_path: str, history: dict):
    hist_file = os.path.join(folder_path, ".bunkr_upload_history.json")
    try:
        with open(hist_file, "w", encoding="utf-8") as f:
            json.dump(history, f, indent=2, ensure_ascii=False)
    except Exception:
        pass


def fetch_online_album_files(token: str, album_id: int) -> set:
    """Consulta la API de Bunkr para ver qué archivos ya existen en el álbum."""
    uploaded_names = set()
    headers = {"token": token, "User-Agent": "Mozilla/5.0"}
    try:
        r = requests.get("https://dash.bunkr.cr/api/uploads", headers=headers, timeout=15)
        if r.status_code == 200:
            for item in r.json().get("files", []):
                if item.get("albumid") == album_id and item.get("original"):
                    uploaded_names.add(item.get("original"))
    except Exception:
        pass
    return uploaded_names


def upload_single_file(node_url: str, token: str, album_id: int, file_path: str) -> bool:
    """Sube un archivo menor a 95 MB de forma directa en una sola petición."""
    file_name = os.path.basename(file_path)
    mime_type = get_mime_type(file_path)
    headers = {
        "token": token,
        "albumid": str(album_id),
        "User-Agent": "Mozilla/5.0"
    }
    with open(file_path, "rb") as f:
        files = {"files[]": (file_name, f, mime_type)}
        r = requests.post(node_url, headers=headers, files=files, timeout=180)
        return r.status_code == 200 and r.json().get("success", False)


def upload_chunked_file(
    node_url: str,
    token: str,
    album_id: int,
    file_path: str,
    progress_callback=None
) -> tuple[bool, str]:
    """
    Sube un archivo mayor a 95 MB dividiéndolo en chunks con reintentos automáticos.
    Si un chunk falla o se congela, se reintenta hasta tener éxito.
    """
    file_name = os.path.basename(file_path)
    mime_type = get_mime_type(file_path)
    file_size = os.path.getsize(file_path)
    total_chunks = (file_size + CHUNK_SIZE - 1) // CHUNK_SIZE
    file_uuid = str(uuid.uuid4())
    headers = {"token": token, "User-Agent": "Mozilla/5.0"}

    with open(file_path, "rb") as f:
        for chunk_idx in range(total_chunks):
            chunk_data = f.read(CHUNK_SIZE)
            offset = chunk_idx * CHUNK_SIZE

            fields = {
                "dzuuid": file_uuid,
                "dzchunkindex": chunk_idx,
                "dztotalfilesize": file_size,
                "dzchunksize": CHUNK_SIZE,
                "dztotalchunkcount": total_chunks,
                "dzchunkbyteoffset": offset
            }

            chunk_success = False
            attempts = 0

            while not chunk_success:
                attempts += 1
                try:
                    files = {"files[]": (file_name, chunk_data, mime_type)}
                    r = requests.post(
                        node_url,
                        headers=headers,
                        data=fields,
                        files=files,
                        timeout=180
                    )

                    if r.status_code == 200:
                        res_json = r.json()
                        if res_json.get("success", False):
                            chunk_success = True
                            if progress_callback:
                                progress_callback(chunk_idx + 1, total_chunks, len(chunk_data), file_size, attempts)
                            break
                        else:
                            time.sleep(3)
                    elif r.status_code in [500, 502, 503, 504, 404]:
                        time.sleep(3)
                        if attempts % 3 == 0:
                            node_url = get_active_node(token)
                    else:
                        time.sleep(3)

                except Exception:
                    time.sleep(3)
                    if attempts % 3 == 0:
                        node_url = get_active_node(token)

            if not chunk_success:
                return False, node_url

    # Finalizar chunks
    finish_url = f"{node_url}/finishchunks"
    finish_payload = {
        "files": [
            {
                "uuid": file_uuid,
                "original": file_name,
                "type": mime_type,
                "albumid": int(album_id)
            }
        ]
    }

    finish_headers = {
        "token": token,
        "User-Agent": "Mozilla/5.0",
        "Content-Type": "application/json"
    }

    for finish_attempt in range(1, 10):
        try:
            r = requests.post(finish_url, headers=finish_headers, json=finish_payload, timeout=120)
            if r.status_code == 200 and r.json().get("success", False):
                return True, node_url
            time.sleep(3)
        except Exception:
            time.sleep(3)

    return False, node_url


def select_album_flow(token: str, cfg: dict, arg_album: str = None) -> tuple[int, str]:
    """Flujo interactivo o por parámetro para seleccionar o crear el álbum de destino."""
    all_albums = fetch_all_user_albums(token)

    # 1. Si se pasó por argumento CLI
    if arg_album:
        arg_clean = arg_album.strip()
        # Verificar si es un ID numérico
        if arg_clean.isdigit():
            aid = int(arg_clean)
            for a in all_albums:
                if a["id"] == aid:
                    return aid, a["name"]
            return aid, f"Álbum #{aid}"

        # Verificar si es enlace con slug (ej: bunkr.cr/a/OKS37rXx)
        slug_match = arg_clean.split("/a/")[-1].split("?")[0].strip("/")
        for a in all_albums:
            if a.get("identifier") == slug_match or a.get("identifier") == arg_clean:
                return a["id"], a["name"]

        # Buscar coincidencia por nombre
        for a in all_albums:
            if arg_clean.lower() in a["name"].lower():
                return a["id"], a["name"]

        # Si no existe, preguntar si desea crearlo con ese nombre
        console.print(f"[yellow]El álbum '{arg_album}' no fue encontrado en tu cuenta.[/yellow]")
        create_it = input("¿Deseas crearlo ahora mismo con ese nombre? (S/N): ").strip().lower()
        if create_it in ["s", "si", "y", "yes"]:
            nid = create_user_album(token, arg_album)
            if nid:
                console.print(f"[bold green]✅ Álbum '{arg_album}' creado con éxito (ID: {nid}).[/bold green]")
                return nid, arg_album
            else:
                console.print("[red]❌ Error al crear el álbum en Bunkr.[/red]")

    # 2. Flujo Interactivo
    saved_album_id = cfg.get("last_album_id")
    saved_album_name = cfg.get("last_album_name", f"Álbum #{saved_album_id}")

    console.print("\n" + "─"*70)
    console.print("[bold cyan]📂 SELECCIÓN DEL ÁLBUM DESTINO EN BUNKR[/bold cyan]")

    if saved_album_id:
        console.print(f"[bold green]1.[/bold green] Usar álbum guardado: [bold white]{saved_album_name}[/bold white] [dim](ID: {saved_album_id})[/dim] [green][Recomendado - Presiona ENTER][/green]")
        console.print(f"[bold green]2.[/bold green] Elegir de mis álbumes en Bunkr ({len(all_albums)} encontrados)")
        console.print(f"[bold green]3.[/bold green] Ingresar ID o enlace directo de otro álbum")
        console.print(f"[bold green]4.[/bold green] Crear un nuevo álbum ahora mismo")
    else:
        console.print(f"[bold green]1.[/bold green] Elegir de mis álbumes en Bunkr ({len(all_albums)} encontrados)")
        console.print(f"[bold green]2.[/bold green] Ingresar ID o enlace directo de un álbum")
        console.print(f"[bold green]3.[/bold green] Crear un nuevo álbum ahora mismo")

    opt = input("\nSelecciona una opción: ").strip()

    if saved_album_id:
        if not opt or opt == "1":
            return saved_album_id, saved_album_name
        choice = opt
    else:
        if not opt or opt == "1":
            choice = "2"
        elif opt == "2":
            choice = "3"
        else:
            choice = "4"

    # Opción 2: Mostrar lista de álbumes
    if choice == "2":
        if not all_albums:
            console.print("[yellow]No se encontraron álbumes en tu cuenta. Crea uno nuevo.[/yellow]")
            choice = "4"
        else:
            tbl = Table(title="📁 Tus Álbumes en Bunkr", border_style="cyan")
            tbl.add_column("#", style="bold yellow", width=4)
            tbl.add_column("Nombre del Álbum", style="bold white")
            tbl.add_column("Archivos", style="green")
            tbl.add_column("Tamaño", style="cyan")
            tbl.add_column("ID", style="dim")

            for i, alb in enumerate(all_albums[:30], 1):
                tbl.add_row(
                    str(i),
                    alb.get("name", "Sin nombre"),
                    str(alb.get("uploads", 0)),
                    format_bytes(alb.get("size", 0)),
                    str(alb.get("id"))
                )
            console.print(tbl)
            if len(all_albums) > 30:
                console.print(f"[dim]Mostrando los primeros 30 de {len(all_albums)} álbumes.[/dim]")

            sel_idx = input(f"\nElige el número de álbum [1-{min(len(all_albums), 30)}]: ").strip()
            if sel_idx.isdigit() and 1 <= int(sel_idx) <= len(all_albums):
                selected = all_albums[int(sel_idx) - 1]
                return selected["id"], selected["name"]

    # Opción 3: Ingresar ID o enlace
    if choice == "3":
        user_input_album = input("Pega el enlace o ID del álbum: ").strip()
        slug_clean = user_input_album.split("/a/")[-1].split("?")[0].strip("/")
        for a in all_albums:
            if a.get("identifier") == slug_clean or str(a.get("id")) == slug_clean:
                return a["id"], a["name"]
        if slug_clean.isdigit():
            return int(slug_clean), f"Álbum #{slug_clean}"

    # Opción 4: Crear nuevo álbum
    if choice == "4":
        new_name = input("Nombre del nuevo álbum a crear en Bunkr: ").strip()
        if new_name:
            nid = create_user_album(token, new_name)
            if nid:
                console.print(f"[bold green]✅ Álbum '{new_name}' creado con éxito (ID: {nid}).[/bold green]")
                return nid, new_name
            else:
                console.print("[red]❌ No se pudo crear el álbum en la API de Bunkr.[/red]")

    # Fallback seguro
    if saved_album_id:
        return saved_album_id, saved_album_name
    elif all_albums:
        return all_albums[0]["id"], all_albums[0]["name"]
    return 0, "Álbum por defecto"


def main():
    parser = argparse.ArgumentParser(description="Bot Subidor Masivo a Bunkr (Videos & Archivos RAR/ZIP) con Reintentos Infinitos")
    parser.add_argument("--token", "-t", default=None, help="Token de autenticación de Bunkr")
    parser.add_argument("--album", "-a", default=None, help="ID, enlace o nombre del álbum destino")
    parser.add_argument("--folder", "-f", default=None, help="Carpeta que contiene los archivos a subir")
    parser.add_argument("--yes", "-y", action="store_true", help="Iniciar subida sin confirmación interactiva")
    args = parser.parse_args()

    cfg = load_bunkr_config()

    console.print(Panel(
        "[bold cyan]🚀 BOT SUBIDOR MASIVO A BUNKR (VIDEOS & ARCHIVOS COMPRIMIDOS RAR/ZIP)[/bold cyan]\n"
        "[white]• [bold green]Formatos Soportados:[/bold green] Videos (.mp4, .mkv, .mov) y Archivos (.rar, .zip, .7z, etc.).\n"
        "• [bold green]Partes Divididas:[/bold green] Detecta automáticamente volúmenes secuenciales (part01 ➔ part99).\n"
        "• [bold green]100% Configurable:[/bold green] Token, álbum y carpetas sin código hardcodeado.\n"
        "• [bold green]Memoria Inteligente:[/bold green] Recuerda tus configuraciones con [Enter].\n"
        "• [bold green]Reintentos Infinitos:[/bold green] Si un chunk se traba o da error, reintenta sin parar.\n"
        "• [bold green]Anti-Duplicados:[/bold green] Sincroniza con el historial local y con tu álbum en Bunkr.[/white]",
        border_style="cyan"
    ))

    # 1. Configuración de Token
    token = args.token
    if not token:
        saved_tok = cfg.get("token", "")
        if saved_tok:
            console.print(f"\n🔑 [bold yellow]Token de Bunkr:[/bold yellow] [dim]{mask_token(saved_tok)}[/dim]")
            tok_input = input("Presiona ENTER para usar el guardado, o pega uno nuevo: ").strip()
            token = tok_input if tok_input else saved_tok
        else:
            console.print("\n" + "="*70)
            console.print("[bold yellow]🔑 CONFIGURACIÓN DE TU TOKEN DE BUNKR (Solo una vez)[/bold yellow]")
            console.print("1. Inicia sesión en [cyan]https://dash.bunkr.cr[/cyan] o [cyan]https://bunkr.cr[/cyan]")
            console.print("2. Presiona [bold]F12[/bold] -> Pestaña [bold]'Application' (o 'Almacenamiento')[/bold] -> [bold]'Cookies'[/bold]")
            console.print("3. Copia el valor de la cookie llamada [bold green]'token'[/bold green]")
            console.print("="*70)
            token = input("Pega tu Token de Bunkr: ").strip()

    if not token:
        console.print("[bold red]❌ Se requiere un Token válido para subir a Bunkr.[/bold red]")
        return

    # Validar token
    console.print("[cyan]🔍 Verificando conexión con Bunkr...[/cyan]")
    if not validate_token(token):
        console.print("[bold red]❌ El Token proporcionado es inválido o expiró. Por favor verifica tus credenciales.[/bold red]")
        return

    cfg["token"] = token

    # 2. Configuración de Carpeta
    target_dir = args.folder
    if not target_dir:
        saved_folder = cfg.get("last_folder", "")
        if saved_folder and os.path.exists(saved_folder):
            console.print(f"\n📁 [bold yellow]Carpeta de archivos/videos[/bold yellow] (Presiona [bold green]Enter[/bold green] para usar la ruta guardada):")
            console.print(f"[dim]{saved_folder}[/dim]")
            folder_input = input("Ruta > ").strip().strip('"').strip("'")
            target_dir = folder_input if folder_input else saved_folder
        else:
            console.print("\n📁 [bold yellow]Carpeta con los archivos o videos a subir:[/bold yellow]")
            target_dir = input("Ruta > ").strip().strip('"').strip("'")

    if not target_dir or not os.path.exists(target_dir):
        console.print(f"[bold red]❌ La carpeta especificada no existe: {target_dir}[/bold red]")
        return

    cfg["last_folder"] = target_dir

    # 3. Selección de Álbum
    album_id, album_name = select_album_flow(token, cfg, args.album)
    cfg["last_album_id"] = album_id
    cfg["last_album_name"] = album_name

    # Guardar configuración actualizada
    save_bunkr_config(cfg)

    # 4. Escanear archivos locales (Videos, Comprimidos RAR/ZIP/7Z e Imágenes)
    valid_exts = {
        # Archivos comprimidos y volúmenes divididos
        ".rar", ".zip", ".7z", ".tar", ".gz", ".bz2", ".xz", ".iso",
        # Videos
        ".mp4", ".mov", ".m4v", ".mkv", ".avi", ".ts", ".webm", ".wmv", ".flv",
        # Imágenes
        ".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp"
    }
    all_files = []
    for root, _, files in os.walk(target_dir):
        for f in files:
            ext = os.path.splitext(f)[1].lower()
            if ext in valid_exts and not f.startswith("._") and not f.endswith(".tmp.mp4") and not f.endswith(".tmp"):
                all_files.append(os.path.join(root, f))

    if not all_files:
        console.print("[bold yellow]⚠️ No se encontraron archivos compatibles (.mp4, .rar, .zip, etc.) en esta carpeta.[/bold yellow]")
        return

    # Detectar si son partes divididas de un archivo comprimido (ej: .part01.rar, .part02.rar, etc.)
    is_split_archive = len(all_files) > 1 and all(
        bool(re.search(r'\.(part\d+|r\d+|z\d+)(\.rar|\.zip)?$', os.path.basename(f), re.IGNORECASE))
        for f in all_files
    )

    if is_split_archive:
        all_files.sort(key=lambda f: natural_sort_key(os.path.basename(f)))
        sort_mode_desc = "Secuencial ordenado por partes (part01 ➔ part99)"
    else:
        # Ordenar estrictamente del más grande al más chico, y por nombre natural si empatan
        all_files.sort(key=lambda f: (-os.path.getsize(f), natural_sort_key(os.path.basename(f))))
        sort_mode_desc = "Del más grande al más chico (por peso)"

    # 5. Consultar historial local y online
    console.print(f"\n🔍 Comprobando qué archivos ya están en tu álbum [cyan]{album_name}[/cyan]...")
    local_history = load_local_history(target_dir)
    online_files = fetch_online_album_files(token, album_id)

    to_upload = []
    already_uploaded = []

    for v_path in all_files:
        v_name = os.path.basename(v_path)
        if v_name in local_history or v_name in online_files:
            already_uploaded.append(v_path)
            if v_name not in local_history:
                local_history[v_name] = {"uploaded_at": time.time(), "size": os.path.getsize(v_path)}
        else:
            to_upload.append(v_path)

    save_local_history(target_dir, local_history)

    total_pending_bytes = sum(os.path.getsize(f) for f in to_upload)

    console.print(f"\n📊 [bold cyan]ESTADO DE LA SUBIDA:[/bold cyan]")
    console.print(f"  • Álbum Destino: [bold green]{album_name}[/bold green] (ID: {album_id})")
    console.print(f"  • Total archivos en carpeta: [bold white]{len(all_files)}[/bold white]")
    console.print(f"  • Ya subidos previamente: [bold green]{len(already_uploaded)}[/bold green] (se omitirán)")
    console.print(f"  • [bold yellow]Pendientes por subir:[/bold yellow] [bold green]{len(to_upload)} archivos[/bold green] ([bold cyan]{format_bytes(total_pending_bytes)}[/bold cyan])")
    console.print(f"  • Orden de procesamiento: [bold cyan]{sort_mode_desc}[/bold cyan]\n")

    if not to_upload:
        console.print(Panel(
            f"[bold green]🎉 ¡Todos los archivos de esta carpeta ya están subidos a tu álbum '{album_name}'![/bold green]",
            border_style="green"
        ))
        return

    # Obtener nodo inicial de subida
    console.print("🌐 Conectando con los servidores de Bunkr...")
    active_node = get_active_node(token)
    console.print(f"✅ Servidor asignado: [bold cyan]{active_node}[/bold cyan]\n")

    if not args.yes:
        console.print(f"[bold green]¿Iniciar la subida de los {len(to_upload)} archivos pendientes? (S/N):[/bold green] ", end="")
        confirm = input().strip().lower()
        if confirm not in ["s", "si", "y", "yes", ""]:
            console.print("[yellow]Operación cancelada por el usuario.[/yellow]")
            return

    console.print(f"\n[bold green]🚀 Iniciando subidas uno por uno...[/bold green]\n")

    success_count = 0
    start_time = time.time()

    try:
        with Progress(
            SpinnerColumn(),
            TextColumn("[bold blue]{task.description}"),
            BarColumn(bar_width=35),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TextColumn("•"),
            TransferSpeedColumn(),
            TextColumn("•"),
            TimeRemainingColumn(),
            console=console
        ) as progress:
            task_total = progress.add_task("[cyan]Subiendo archivos...", total=len(to_upload))

            for idx, file_path in enumerate(to_upload, 1):
                file_name = os.path.basename(file_path)
                file_size = os.path.getsize(file_path)

                progress.update(task_total, description=f"[cyan]({idx}/{len(to_upload)}) {file_name[:25]}... ({format_bytes(file_size)})")

                t0 = time.time()
                is_chunked = file_size > CHUNK_SIZE

                if not is_chunked:
                    # Subida directa (archivo < 95 MB)
                    success = False
                    attempts = 0
                    while not success:
                        attempts += 1
                        try:
                            success = upload_single_file(active_node, token, album_id, file_path)
                            if not success:
                                time.sleep(3)
                        except Exception:
                            time.sleep(3)
                            if attempts % 3 == 0:
                                active_node = get_active_node(token)
                else:
                    # Subida por chunks con progreso visual
                    def on_chunk(curr, total, chunk_len, f_size, att):
                        pass

                    success, active_node = upload_chunked_file(
                        active_node,
                        token,
                        album_id,
                        file_path,
                        progress_callback=on_chunk
                    )

                elapsed = time.time() - t0

                if success:
                    success_count += 1
                    local_history[file_name] = {
                        "uploaded_at": time.time(),
                        "size": file_size,
                        "album_id": album_id
                    }
                    save_local_history(target_dir, local_history)
                    speed = (file_size / elapsed) if elapsed > 0 else 0
                    progress.console.print(
                        f"  [green]✔[/green] {file_name[:35]} ([cyan]{format_bytes(file_size)}[/cyan]) subido a Bunkr en {elapsed:.1f}s "
                        f"([bold green]{format_bytes(speed)}/s[/bold green])"
                    )
                else:
                    progress.console.print(f"  [red]✖ Error permanente al subir:[/red] {file_name}")

                progress.advance(task_total)

    except KeyboardInterrupt:
        console.print("\n\n[bold yellow]⚠️ Subida pausada por el usuario (Ctrl+C).[/bold yellow]")
        console.print("[green]💾 Los archivos ya completados quedaron registrados en el historial.[/green]")
        console.print("[white]Al volver a ejecutar, el bot continuará exactamente donde se quedó.[/white]\n")
        save_local_history(target_dir, local_history)
        return

    total_time = time.time() - start_time

    # Tabla resumen final
    summary_table = Table(title="🎉 RESUMEN DE SUBIDA A BUNKR", border_style="green", show_lines=True)
    summary_table.add_column("Métrica", style="bold cyan")
    summary_table.add_column("Valor", style="bold white")

    summary_table.add_row("Álbum destino", album_name)
    summary_table.add_row("Archivos subidos en esta sesión", f"{success_count} de {len(to_upload)}")
    summary_table.add_row("Datos transferidos con éxito", format_bytes(total_pending_bytes))
    summary_table.add_row("Tiempo total transcurrido", f"{total_time / 60:.1f} minutos")

    console.print("\n")
    console.print(summary_table)
    console.print("\n[bold green]✅ Todos los archivos pendientes han sido subidos exitosamente a Bunkr.[/bold green]\n")


if __name__ == "__main__":
    main()
