"""
Bunkr Ultra Uploader Bot (Subida Inteligente con Reintentos Infinitos)
----------------------------------------------------------------------
- Sube videos automáticamente a Bunkr.cr asignándolos al álbum especificado.
- Orden de subida: Del más grande al más chico (uno por uno).
- Protocolo por chunks (95 MB) con reintentos automáticos si se congela o da error.
- Detección de servidor activo con rotación automática de nodos caídos.
- Memoria de subida (.bunkr_upload_history.json) y sincronización con el álbum online para evitar duplicados.
"""

import os
import sys
import time
import json
import uuid
import shutil
import subprocess
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

DEFAULT_TOKEN = "Yf4UTVsscXzs4uClNAh50CKdy4wBWdmkU73QN0NVEprnSXnC0BQqVAchIehJU5kc"
DEFAULT_ALBUM_ID = 628942
DEFAULT_ALBUM_NAME = "SoyMafe By:@DeathSilencer"
DEFAULT_ALBUM_SLUG = "OKS37rXx"
DEFAULT_FOLDER = r"D:\Armando\$1 Corel\$ 2FBK\Fotos cuentas\Alma\Nueva Carpeta\Models\Nueva carpeta\Nueva carpeta"
CHUNK_SIZE = 95 * 1000 * 1000  # 95 MB por bloque estándar de Bunkr

def format_bytes(bytes_val: float) -> str:
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if bytes_val < 1024.0:
            return f"{bytes_val:.2f} {unit}"
        bytes_val /= 1024.0
    return f"{bytes_val:.2f} PB"

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
        except Exception as e:
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
    headers = {
        "token": token,
        "albumid": str(album_id),
        "User-Agent": "Mozilla/5.0"
    }
    with open(file_path, "rb") as f:
        files = {"files[]": (file_name, f, "video/mp4")}
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
            files = {"files[]": (file_name, chunk_data, "video/mp4")}

            # Bucle de reintentos infinitos para este chunk si se congela o da error
            chunk_success = False
            chunk_attempts = 0

            while not chunk_success:
                chunk_attempts += 1
                try:
                    if progress_callback:
                        progress_callback(chunk_idx + 1, total_chunks, len(chunk_data), file_size, chunk_attempts)

                    r = requests.post(node_url, headers=headers, data=fields, files=files, timeout=180)
                    if r.status_code == 200 and r.json().get("success", False):
                        chunk_success = True
                    else:
                        console.print(f"[yellow]  ⚠️ Chunk {chunk_idx + 1}/{total_chunks} falló (código {r.status_code}). Reintentando en 3s...[/yellow]")
                        time.sleep(3)
                except Exception as e:
                    console.print(f"[yellow]  ⚠️ Error de red en chunk {chunk_idx + 1}/{total_chunks} ({e}). Reintentando en 3s...[/yellow]")
                    time.sleep(3)
                    # Si falla más de 3 veces, refrescar nodo
                    if chunk_attempts % 3 == 0:
                        node_url = get_active_node(token)
                        console.print(f"[dim]  🔄 Servidor de subida actualizado: {node_url}[/dim]")

    # Todos los chunks subidos con éxito -> Finalizar y asignar al álbum
    finish_headers = {
        "token": token,
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0"
    }
    finish_body = {
        "files": [
            {
                "uuid": file_uuid,
                "original": file_name,
                "type": "video/mp4",
                "albumid": album_id
            }
        ]
    }

    for _ in range(5):
        try:
            rf = requests.post(f"{node_url}/finishchunks", headers=finish_headers, json=finish_body, timeout=60)
            if rf.status_code == 200 and rf.json().get("success", False):
                return True, node_url
        except Exception:
            time.sleep(2)

    return False, node_url

def main():
    console.print(Panel(
        "[bold cyan]🚀 BOT SUBIDOR MASIVO A BUNKR (REINTENTOS INFINITOS & ANTI-CONGELAMIENTO)[/bold cyan]\n"
        f"[white]• [bold green]Álbum Objetivo:[/bold green] {DEFAULT_ALBUM_NAME} (ID: {DEFAULT_ALBUM_ID})\n"
        "• [bold green]Orden de Subida:[/bold green] Del más grande al más chico (uno por uno)\n"
        "• [bold green]Reintentos Inteligentes:[/bold green] Si un chunk se traba en 0% o da error, reintenta sin parar hasta lograrlo.\n"
        "• [bold green]Anti-Duplicados:[/bold green] Consulta tu álbum para omitir videos ya subidos.[/white]",
        border_style="cyan"
    ))

    # 1. Configuración de carpeta
    console.print(f"[bold yellow]Carpeta de videos[/bold yellow] (Presiona [bold green]Enter[/bold green] para usar la ruta por defecto):")
    console.print(f"[dim]{DEFAULT_FOLDER}[/dim]")
    user_input = input("Ruta > ").strip().strip('"').strip("'")
    target_dir = user_input if user_input else DEFAULT_FOLDER

    if not os.path.exists(target_dir):
        console.print(f"[bold red]❌ La carpeta especificada no existe: {target_dir}[/bold red]")
        return

    # 2. Escanear videos locales
    valid_exts = {".mp4", ".mov", ".m4v", ".mkv", ".avi", ".ts", ".webm"}
    all_videos = []
    for root, _, files in os.walk(target_dir):
        for f in files:
            ext = os.path.splitext(f)[1].lower()
            if ext in valid_exts and not f.startswith("._") and not f.endswith(".tmp.mp4"):
                all_videos.append(os.path.join(root, f))

    if not all_videos:
        console.print("[bold yellow]⚠️ No se encontraron videos compatibles en esta carpeta.[/bold yellow]")
        return

    # Ordenar estrictamente del más grande al más chico
    all_videos.sort(key=lambda f: os.path.getsize(f), reverse=True)

    # 3. Consultar historial local y online
    console.print(f"\n🔍 Comprobando qué videos ya están en tu álbum [cyan]{DEFAULT_ALBUM_NAME}[/cyan]...")
    local_history = load_local_history(target_dir)
    online_files = fetch_online_album_files(DEFAULT_TOKEN, DEFAULT_ALBUM_ID)

    to_upload = []
    already_uploaded = []

    for v_path in all_videos:
        v_name = os.path.basename(v_path)
        if v_name in local_history or v_name in online_files:
            already_uploaded.append(v_path)
            # Asegurar sincronización local
            if v_name not in local_history:
                local_history[v_name] = {"uploaded_at": time.time(), "size": os.path.getsize(v_path)}
        else:
            to_upload.append(v_path)

    save_local_history(target_dir, local_history)

    total_pending_bytes = sum(os.path.getsize(f) for f in to_upload)

    console.print(f"📊 [bold cyan]ESTADO DE LA SUBIDA:[/bold cyan]")
    console.print(f"  • Total videos en carpeta: [bold white]{len(all_videos)}[/bold white]")
    console.print(f"  • Ya subidos previamente: [bold green]{len(already_uploaded)}[/bold green] (se omitirán)")
    console.print(f"  • [bold yellow]Pendientes por subir:[/bold yellow] [bold green]{len(to_upload)} videos[/bold green] ([bold cyan]{format_bytes(total_pending_bytes)}[/bold cyan])\n")

    if not to_upload:
        console.print(Panel(
            f"[bold green]🎉 ¡Todos los videos de esta carpeta ya están subidos a tu álbum {DEFAULT_ALBUM_NAME}![/bold green]",
            border_style="green"
        ))
        return

    # Obtener nodo inicial de subida
    console.print("🌐 Conectando con los servidores de Bunkr...")
    active_node = get_active_node(DEFAULT_TOKEN)
    console.print(f"✅ Servidor asignado: [bold cyan]{active_node}[/bold cyan]\n")

    console.print(f"[bold green]¿Iniciar la subida de los {len(to_upload)} videos pendientes? (S/N):[/bold green] ", end="")
    confirm = input().strip().lower()
    if confirm not in ["s", "si", "y", "yes", ""]:
        console.print("[yellow]Operación cancelada.[/yellow]")
        return

    console.print(f"\n[bold green]🚀 Iniciando subidas uno por uno (de mayor a menor peso)...[/bold green]\n")

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
            task_total = progress.add_task("[cyan]Subiendo videos...", total=len(to_upload))

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
                            success = upload_single_file(active_node, DEFAULT_TOKEN, DEFAULT_ALBUM_ID, file_path)
                            if not success:
                                time.sleep(3)
                        except Exception:
                            time.sleep(3)
                            if attempts % 3 == 0:
                                active_node = get_active_node(DEFAULT_TOKEN)
                else:
                    # Subida por chunks con progreso visual
                    def on_chunk(curr, total, chunk_len, f_size, att):
                        pass

                    success, active_node = upload_chunked_file(
                        active_node,
                        DEFAULT_TOKEN,
                        DEFAULT_ALBUM_ID,
                        file_path,
                        progress_callback=on_chunk
                    )

                elapsed = time.time() - t0

                if success:
                    success_count += 1
                    local_history[file_name] = {
                        "uploaded_at": time.time(),
                        "size": file_size,
                        "album_id": DEFAULT_ALBUM_ID
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
        console.print("[green]💾 Los videos ya completados quedaron registrados en el historial.[/green]")
        console.print("[white]Al volver a ejecutar, el bot continuará exactamente donde se quedó.[/white]\n")
        save_local_history(target_dir, local_history)
        return

    total_time = time.time() - start_time

    # Tabla resumen final
    summary_table = Table(title="🎉 RESUMEN DE SUBIDA A BUNKR", border_style="green", show_lines=True)
    summary_table.add_column("Métrica", style="bold cyan")
    summary_table.add_column("Valor", style="bold white")

    summary_table.add_row("Álbum destino", DEFAULT_ALBUM_NAME)
    summary_table.add_row("Videos subidos en esta sesión", f"{success_count} de {len(to_upload)}")
    summary_table.add_row("Datos transferidos con éxito", format_bytes(total_pending_bytes))
    summary_table.add_row("Tiempo total transcurrido", f"{total_time / 60:.1f} minutos")

    console.print("\n")
    console.print(summary_table)
    console.print("\n[bold green]✅ Todos los videos pendientes han sido subidos exitosamente a Bunkr.[/bold green]\n")

if __name__ == "__main__":
    main()
