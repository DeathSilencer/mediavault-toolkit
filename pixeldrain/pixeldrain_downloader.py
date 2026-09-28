"""
Pixeldrain Album Downloader & Quota Manager (Autoinstalable y Dinámico)
-----------------------------------------------------------------------
- Comprueba e instala automáticamente cualquier paquete o herramienta faltante (pip, FFmpeg).
- Acepta cualquier enlace o ID de álbum de Pixeldrain sin nada hardcodeado.
- Pregunta la carpeta de destino o crea una con el nombre del álbum en el Disco D:.
- Monitoreo en tiempo real de la cuota diaria de 6 GB con cambio de VPN en caliente.
- Reanudación por byte (.part) y auto-conversión de .m4v a .MP4 estándar vía FFmpeg.
- Permite descargar múltiples álbumes consecutivos en una sola sesión.
"""

import os
import sys
import shutil
import subprocess
import urllib.request
import zipfile

# 1. AUTO-INSTALACIÓN DE DEPENDENCIAS Y HERRAMIENTAS
def ensure_dependencies():
    """
    Verifica e instala automáticamente:
    1. Paquetes pip: requests, rich, websockets
    2. Binarios de FFmpeg / FFprobe para conversión de video
    """
    required = ["requests", "rich", "websockets"]
    missing = []
    for pkg in required:
        try:
            __import__(pkg)
        except ImportError:
            missing.append(pkg)

    if missing:
        print(f"📦 Instalando dependencias de Python faltantes: {', '.join(missing)}...")
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", "--upgrade"] + missing)
            print("✅ Dependencias instaladas con éxito.")
        except Exception as e:
            print(f"❌ Error al instalar paquetes con pip: {e}")

    # Verificar FFmpeg
    if not shutil.which("ffmpeg"):
        script_dir = os.path.dirname(os.path.abspath(__file__))
        local_bin = os.path.join(script_dir, "bin")
        local_ffmpeg = os.path.join(local_bin, "ffmpeg.exe")

        if os.path.exists(local_ffmpeg):
            os.environ["PATH"] = local_bin + os.pathsep + os.environ.get("PATH", "")
        else:
            print("🎬 FFmpeg no detectado en el sistema. Intentando instalación automática...")
            installed_via_winget = False
            if shutil.which("winget"):
                try:
                    res = subprocess.run(
                        ["winget", "install", "--id", "Gyan.FFmpeg", "-e", "--accept-source-agreements", "--accept-package-agreements"],
                        capture_output=True, text=True
                    )
                    if res.returncode == 0:
                        installed_via_winget = True
                        print("✅ FFmpeg instalado vía Winget.")
                except Exception:
                    pass

            if not installed_via_winget and not shutil.which("ffmpeg"):
                try:
                    print("⬇️ Descargando versión portable de FFmpeg...")
                    os.makedirs(local_bin, exist_ok=True)
                    zip_url = "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip"
                    zip_path = os.path.join(local_bin, "ffmpeg.zip")
                    urllib.request.urlretrieve(zip_url, zip_path)
                    with zipfile.ZipFile(zip_path, 'r') as zf:
                        for member in zf.namelist():
                            if member.endswith("ffmpeg.exe") or member.endswith("ffprobe.exe"):
                                filename = os.path.basename(member)
                                with zf.open(member) as source, open(os.path.join(local_bin, filename), "wb") as target:
                                    shutil.copyfileobj(source, target)
                    os.remove(zip_path)
                    os.environ["PATH"] = local_bin + os.pathsep + os.environ.get("PATH", "")
                    print("✅ FFmpeg portable configurado en carpeta local bin/.")
                except Exception as e:
                    print(f"⚠️ No se pudo descargar FFmpeg automáticamente: {e}")


# Ejecutar comprobación antes de importar librerías externas
ensure_dependencies()

# Forzar codificación UTF-8 en consolas Windows
if sys.platform.startswith("win"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

import time
import json
import argparse
import asyncio
import re
import requests
import websockets

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.progress import (
    Progress,
    BarColumn,
    TextColumn,
    TransferSpeedColumn,
    TimeRemainingColumn,
    DownloadColumn,
    TaskID
)

console = Console(force_terminal=True)

BASE_DEFAULT_DIR = r"D:\Armando\$1 Corel\$ 2FBK\Fotos cuentas\Alma\Nueva Carpeta\Models"


def find_ffmpeg():
    return shutil.which("ffmpeg")


def sanitize_folder_name(name: str) -> str:
    return re.sub(r'[\\/*?:"<>|]', "", name).strip() or "Pixeldrain_Album"


def extract_pixeldrain_id(url_or_id: str) -> str:
    url_or_id = url_or_id.strip()
    if "/l/" in url_or_id:
        return url_or_id.split("/l/")[-1].split("?")[0].strip("/")
    if "/u/" in url_or_id:
        return url_or_id.split("/u/")[-1].split("?")[0].strip("/")
    if "/" in url_or_id:
        return url_or_id.split("/")[-1].split("?")[0].strip()
    return url_or_id


def convert_to_mp4(source_file: str) -> str:
    ffmpeg_exe = find_ffmpeg()
    if not ffmpeg_exe:
        return source_file

    base, ext = os.path.splitext(source_file)
    if ext.lower() == ".mp4":
        return source_file

    target_mp4 = base + ".mp4"
    if os.path.exists(target_mp4) and os.path.getsize(target_mp4) > 0:
        try:
            os.remove(source_file)
        except Exception:
            pass
        return target_mp4

    cmd = [ffmpeg_exe, "-y", "-hide_banner", "-loglevel", "error", "-i", source_file, "-c", "copy", target_mp4]
    res = subprocess.run(cmd, capture_output=True, text=True)

    if res.returncode != 0 or not os.path.exists(target_mp4) or os.path.getsize(target_mp4) == 0:
        cmd_fallback = [ffmpeg_exe, "-y", "-hide_banner", "-loglevel", "error", "-i", source_file, "-c:v", "copy", "-c:a", "aac", target_mp4]
        res = subprocess.run(cmd_fallback, capture_output=True, text=True)

    if res.returncode == 0 and os.path.exists(target_mp4) and os.path.getsize(target_mp4) > 0:
        try:
            os.remove(source_file)
        except Exception:
            pass
        return target_mp4

    return source_file


def get_live_pixeldrain_limits(timeout: float = 4.0):
    async def _fetch():
        uri = "wss://pixeldrain.com/api/file_stats"
        headers = [
            ("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"),
            ("Origin", "https://pixeldrain.com")
        ]
        async with websockets.connect(uri, additional_headers=headers) as ws:
            await ws.send(json.dumps({"type": "limits"}))
            msg = await asyncio.wait_for(ws.recv(), timeout=timeout)
            data = json.loads(msg)
            return data.get("limits", {})

    try:
        return asyncio.run(_fetch())
    except Exception:
        return None


def get_album_info(list_id: str):
    url = f"https://pixeldrain.com/api/list/{list_id}"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req) as resp:
        data = json.loads(resp.read().decode())
    return data


def download_pixeldrain_file(file_id: str, filename: str, file_size: int, output_dir: str, progress: Progress, total_task: TaskID, max_retries: int = 5):
    dest_path = os.path.join(output_dir, filename)
    base_name, _ = os.path.splitext(filename)
    mp4_dest_path = os.path.join(output_dir, base_name + ".mp4")
    part_path = dest_path + ".part"

    if os.path.exists(mp4_dest_path) and os.path.getsize(mp4_dest_path) > 0:
        progress.update(total_task, advance=file_size)
        return True, 0, f"[dim]Saltado (ya existe): {os.path.basename(mp4_dest_path)}[/dim]"

    if os.path.exists(dest_path) and os.path.getsize(dest_path) == file_size:
        final_file = convert_to_mp4(dest_path)
        progress.update(total_task, advance=file_size)
        return True, 0, f"[dim]Saltado (ya descargado): {os.path.basename(final_file)}[/dim]"

    download_url = f"https://pixeldrain.com/api/file/{file_id}?download"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko)",
        "Referer": "https://pixeldrain.com/",
    }

    retries = 0
    actual_bytes_downloaded = 0

    while retries < max_retries:
        try:
            downloaded = 0
            mode = "wb"
            req_headers = dict(headers)

            if os.path.exists(part_path):
                downloaded = os.path.getsize(part_path)
                if downloaded < file_size:
                    req_headers["Range"] = f"bytes={downloaded}-"
                    mode = "ab"
                elif downloaded >= file_size:
                    shutil.move(part_path, dest_path)
                    final_path = convert_to_mp4(dest_path)
                    progress.update(total_task, advance=file_size)
                    return True, 0, f"[green]Listo: {os.path.basename(final_path)}[/green]"

            file_task = progress.add_task(f"[cyan]{filename[:30]}[/cyan]", total=file_size, completed=downloaded)

            with requests.get(download_url, headers=req_headers, stream=True, timeout=30) as r:
                if r.status_code == 429:
                    progress.remove_task(file_task)
                    return False, actual_bytes_downloaded, "RATELIMIT"

                if r.status_code not in (200, 206):
                    progress.remove_task(file_task)
                    raise Exception(f"HTTP {r.status_code}")

                with open(part_path, mode) as f:
                    for chunk in r.iter_content(chunk_size=512 * 1024):
                        if chunk:
                            f.write(chunk)
                            actual_bytes_downloaded += len(chunk)
                            progress.update(file_task, advance=len(chunk))
                            progress.update(total_task, advance=len(chunk))

            progress.remove_task(file_task)

            if os.path.getsize(part_path) >= file_size:
                shutil.move(part_path, dest_path)
                final_path = convert_to_mp4(dest_path)
                return True, actual_bytes_downloaded, f"[green]Descargado: {os.path.basename(final_path)}[/green]"
            else:
                retries += 1
                time.sleep(2)

        except Exception:
            retries += 1
            if 'file_task' in locals():
                try:
                    progress.remove_task(file_task)
                except Exception:
                    pass
            time.sleep(3)

    return False, actual_bytes_downloaded, f"[red]Error tras varios intentos: {filename}[/red]"


def process_pixeldrain_download(raw_url: str, custom_output: str = None, sort_mode: str = "desc", limit_gb: float = 5.85, auto_yes: bool = False):
    list_id = extract_pixeldrain_id(raw_url)
    if not list_id:
        console.print("[bold red]❌ Enlace o ID no válido.[/bold red]")
        return

    try:
        album_data = get_album_info(list_id)
    except Exception as e:
        console.print(f"[bold red]❌ Error al obtener álbum de Pixeldrain: {e}[/bold red]")
        return

    files = album_data.get("files", [])
    album_title = sanitize_folder_name(album_data.get("title", list_id))

    if not files:
        console.print("[bold red]❌ El álbum no contiene archivos o no es accesible.[/bold red]")
        return

    if not custom_output:
        suggested_dir = os.path.join(BASE_DEFAULT_DIR, album_title)
        console.print(f"\n[bold green]📁 Carpeta de destino:[/bold green] [yellow]{suggested_dir}[/yellow]")
        user_dest = console.input("[bold white]Presiona ENTER para usar esa carpeta, o escribe otra ruta: [/bold white]").strip()
        output_dir = os.path.abspath(user_dest) if user_dest else os.path.abspath(suggested_dir)
    else:
        output_dir = os.path.abspath(custom_output)

    os.makedirs(output_dir, exist_ok=True)

    if sort_mode == "desc":
        files.sort(key=lambda x: x["size"], reverse=True)
    elif sort_mode == "asc":
        files.sort(key=lambda x: x["size"])

    total_bytes = sum(f["size"] for f in files)
    total_gb = total_bytes / (1024**3)

    disk_total, disk_used, disk_free = shutil.disk_usage(output_dir)
    disk_free_gb = disk_free / (1024**3)
    drive_letter = os.path.splitdrive(output_dir)[0] or output_dir

    live_limits = get_live_pixeldrain_limits()
    if live_limits:
        server_limit_gb = live_limits.get("transfer_limit", 6000000000) / (1024**3)
        server_used_gb = live_limits.get("transfer_limit_used", 0) / (1024**3)
        server_remaining_gb = max(0, server_limit_gb - server_used_gb)
        quota_display = f"{server_used_gb:.2f} GB usados de {server_limit_gb:.2f} GB (Restan: {server_remaining_gb:.2f} GB)"
    else:
        quota_display = f"Tope seguro configurado: {limit_gb:.2f} GB"

    table = Table(title="📊 Resumen del Álbum Pixeldrain")
    table.add_column("Propiedad", style="cyan")
    table.add_column("Detalle", style="magenta")

    table.add_row("Nombre del álbum", album_data.get("title", list_id))
    table.add_row("Total de archivos", str(len(files)))
    table.add_row("Tamaño total del álbum", f"{total_gb:.2f} GB ({total_bytes / (1024**2):.1f} MB)")
    table.add_row(f"Espacio libre en {drive_letter}", f"{disk_free_gb:.2f} GB")
    table.add_row("Cuota actual de tu IP", quota_display)
    table.add_row("Orden de descarga", "⬇️ Más pesados primero" if sort_mode == "desc" else ("⬆️ Más ligeros primero" if sort_mode == "asc" else "Orden original"))
    table.add_row("Carpeta destino", output_dir)
    console.print(table)

    if not auto_yes:
        resp = console.input("\n[bold green]¿Deseas iniciar la descarga? (s/n): [/bold green]").strip().lower()
        if resp not in ('s', 'si', 'y', 'yes', ''):
            console.print("[yellow]Descarga omitida por el usuario.[/yellow]")
            return

    console.print(f"\n[bold green]🚀 Iniciando descargas en:[/bold green] [yellow]{output_dir}[/yellow]\n")

    session_bytes_downloaded = 0
    max_session_bytes = limit_gb * (1024**3)

    progress = Progress(
        TextColumn("[bold blue]{task.description}"),
        BarColumn(),
        DownloadColumn(),
        TransferSpeedColumn(),
        TimeRemainingColumn(),
        console=console,
    )

    with progress:
        total_task = progress.add_task(f"[bold magenta]Progreso Total ({len(files)} archivos)[/bold magenta]", total=total_bytes)

        for idx, file_item in enumerate(files, 1):
            fid = file_item["id"]
            fname = file_item["name"]
            fsize = file_item["size"]

            base_name, _ = os.path.splitext(fname)
            mp4_path = os.path.join(output_dir, base_name + ".mp4")
            orig_path = os.path.join(output_dir, fname)
            if (os.path.exists(mp4_path) and os.path.getsize(mp4_path) > 0) or (os.path.exists(orig_path) and os.path.getsize(orig_path) == fsize):
                progress.update(total_task, advance=fsize)
                continue

            if (session_bytes_downloaded + fsize) > max_session_bytes:
                console.print("\n" + "="*70)
                console.print(f"[bold yellow]⚠️ LÍMITE DIARIO DE CUOTA ALCANZADO ({session_bytes_downloaded / (1024**3):.2f} GB descargados en esta sesión)[/bold yellow]")
                console.print(f"[cyan]El siguiente archivo '{fname}' ({fsize / (1024**2):.1f} MB) excedería el tope de seguridad de {limit_gb:.2f} GB.[/cyan]")
                console.print("[green]👉 OPCIÓN 1:[/green] Si tienes [bold cyan]VPN / Cloudflare[/bold cyan], cambia de servidor (o dale a 'Restablecer claves') y presiona [bold green]ENTER[/bold green] para continuar descargando de inmediato.")
                console.print("[yellow]👉 OPCIÓN 2:[/yellow] Escribe [bold red]'q'[/bold red] para salir y continuar mañana sin gastar cuota extra.")
                console.print("="*70)

                user_choice = console.input("\n[bold white]Presiona ENTER tras cambiar de VPN, o 'q' para salir: [/bold white]").strip().lower()
                if user_choice == 'q':
                    console.print("[yellow]Descargas pausadas por hoy. ¡Todos los videos descargados están a salvo en tu disco![/yellow]")
                    break
                else:
                    console.print("[bold green]🔄 Detectando nueva conexión... Reiniciando contador de cuota y continuando.[/bold green]")
                    session_bytes_downloaded = 0
                    time.sleep(2)

            console.print(f"[bold green]▶ [{idx}/{len(files)}][/bold green] Descargando [yellow]{fname}[/yellow] ({fsize / (1024**2):.1f} MB)...")
            success, downloaded_now, msg = download_pixeldrain_file(fid, fname, fsize, output_dir, progress, total_task)

            session_bytes_downloaded += downloaded_now

            if not success:
                if msg == "RATELIMIT":
                    console.print("\n[bold red]⚠️ El servidor de Pixeldrain indica que se ha agotado el límite de 6 GB para tu IP actual.[/bold red]")
                    console.print("[cyan]Cambia de servidor en tu VPN / Cloudflare y presiona ENTER, o 'q' para salir.[/cyan]")
                    ans = console.input("ENTER para reanudar con nueva IP, o 'q' para salir: ").strip().lower()
                    if ans == 'q':
                        break
                    else:
                        session_bytes_downloaded = 0
                else:
                    console.print(msg)

    console.print(f"\n[bold green]✨ Sesión finalizada. Archivos descargados en:[/bold green] [yellow]{output_dir}[/yellow]\n")


def main():
    parser = argparse.ArgumentParser(description="Bot Descargador interactivo de Pixeldrain")
    parser.add_argument("url", nargs="?", default=None, help="URL o ID del álbum de Pixeldrain")
    parser.add_argument("--output", "-o", default=None, help="Carpeta destino")
    parser.add_argument("--sort", choices=["desc", "asc", "none"], default="desc", help="Orden de descarga")
    parser.add_argument("--limit-gb", type=float, default=5.85, help="Tope de cuota por sesión en GB (default: 5.85)")
    parser.add_argument("--yes", "-y", action="store_true", help="Iniciar sin confirmación previa")
    args = parser.parse_args()

    console.print(Panel.fit(
        "[bold cyan]🤖 Bot Descargador de Pixeldrain (Modo Universal)[/bold cyan]\n"
        "[yellow]• Acepta cualquier enlace o ID de álbum de Pixeldrain[/yellow]\n"
        "[yellow]• Auto-instalación de herramientas y dependencias[/yellow]\n"
        "[yellow]• Control y protección de cuota de 6 GB con cambio de VPN en caliente[/yellow]\n"
        "[yellow]• Auto-conversión a formato .MP4 estándar[/yellow]",
        border_style="cyan"
    ))

    if args.url:
        process_pixeldrain_download(args.url, args.output, args.sort, args.limit_gb, args.yes)
        return

    while True:
        console.print("\n" + "─"*70)
        user_url = console.input("[bold green]🔗 Pega el enlace o ID del álbum de Pixeldrain[/bold green] (o escribe [bold red]'q'[/bold red] para salir): ").strip()
        if not user_url or user_url.lower() == 'q':
            console.print("[yellow]Saliendo del descargador de Pixeldrain.[/yellow]")
            break

        process_pixeldrain_download(user_url, args.output, args.sort, args.limit_gb, args.yes)


if __name__ == "__main__":
    main()
