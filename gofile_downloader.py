"""
Gofile Batch Downloader & MP4 Auto-Converter (Autoinstalable y Dinámico)
-------------------------------------------------------------------------
- Comprueba e instala automáticamente cualquier paquete o herramienta faltante (pip, Playwright, FFmpeg).
- Permite ingresar cualquier enlace o ID de Gofile en tiempo real sin nada hardcodeado.
- Pregunta la carpeta de destino o usa la carpeta base con el nombre del álbum.
- Descarga de más pesados a más ligeros con conexiones simultáneas optimizadas.
- Convierte automáticamente videos .MOV (y otros) a .MP4 usando FFmpeg sin pérdida de calidad.
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
    1. Paquetes pip: requests, rich, playwright
    2. Navegador Chromium para Playwright
    3. Binarios de FFmpeg / FFprobe para conversión de video
    """
    required = ["requests", "rich", "playwright"]
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

    # Verificar navegador Playwright
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            exe = p.chromium.executable_path
            if not exe or not os.path.exists(exe):
                raise Exception("Chromium no encontrado")
    except Exception:
        print("🌐 Descargando e instalando navegador Chromium de Playwright...")
        try:
            subprocess.check_call([sys.executable, "-m", "playwright", "install", "chromium"])
            print("✅ Navegador Chromium instalado con éxito.")
        except Exception as e:
            print(f"⚠️ Error al instalar Chromium: {e}")

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
import argparse
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
import requests
from playwright.sync_api import sync_playwright

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
    return re.sub(r'[\\/*?:"<>|]', "", name).strip() or "Gofile_Download"


def extract_gofile_id(url_or_id: str) -> str:
    url_or_id = url_or_id.strip()
    if "/d/" in url_or_id:
        return url_or_id.split("/d/")[-1].split("?")[0].strip("/")
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


def convert_existing_movs(output_dir: str):
    if not os.path.exists(output_dir):
        return
    movs = [f for f in os.listdir(output_dir) if f.lower().endswith(".mov")]
    if movs:
        console.print(f"[bold cyan]🎬 Convirtiendo {len(movs)} archivo(s) .MOV previos a .MP4...[/bold cyan]")
        for m in movs:
            full_p = os.path.join(output_dir, m)
            converted = convert_to_mp4(full_p)
            console.print(f"[dim] - Convertido: {os.path.basename(converted)}[/dim]")


class GofileManager:
    def __init__(self, content_id: str):
        self.content_id = content_id
        self.cookies = {}
        self.user_agent = ""
        self.folder_name = content_id
        self.items = []

    def fetch_folder(self):
        console.print(f"[bold cyan]🔍 Conectando con Gofile para obtener la carpeta [yellow]{self.content_id}[/yellow]...[/bold cyan]")
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()

            page.goto(f"https://gofile.io/d/{self.content_id}", wait_until="networkidle")

            self.cookies = {c['name']: c['value'] for c in page.context.cookies()}
            self.user_agent = page.evaluate("() => navigator.userAgent")

            eval_script = f"""async () => {{
                const match = document.cookie.match(/accountToken=([^;]+)/);
                const token = match ? match[1] : null;
                const {{ getFolder }} = await import('/js/services/contents.js');

                let allFiles = [];
                let pageNum = 1;
                let folderName = '{self.content_id}';

                while (true) {{
                    const res = await getFolder(token, '{self.content_id}', {{ page: pageNum, pageSize: 100 }});
                    if (res.data && res.data.name) {{
                        folderName = res.data.name;
                    }}
                    const children = res.data.children || {{}};
                    const items = Object.values(children);
                    allFiles.push(...items);

                    const total = res.metadata?.totalCount || res.data.totalChildrenCount || items.length;
                    if (items.length === 0 || allFiles.length >= total) {{
                        break;
                    }}
                    pageNum++;
                }}

                return {{
                    folderName: folderName,
                    totalFiles: allFiles.length,
                    items: allFiles.map(f => ({{
                        id: f.id,
                        name: f.name,
                        size: f.size || 0,
                        link: f.link,
                        mimetype: f.mimetype || ''
                    }}))
                }};
            }}"""

            result = page.evaluate(eval_script)
            browser.close()

        self.folder_name = result.get("folder_name", self.content_id)
        self.items = result.get("items", [])
        return self.items

    def refresh_links(self):
        console.print("\n[yellow]🔄 Renovando sesión y enlaces de descarga en Gofile...[/yellow]")
        old_items = {i["id"]: i for i in self.items}
        new_items = self.fetch_folder()
        for item in new_items:
            if item["id"] in old_items:
                old_items[item["id"]]["link"] = item["link"]
        console.print("[green]✅ Enlaces actualizados con éxito.[/green]\n")


def is_already_downloaded(item: dict, output_dir: str) -> bool:
    orig_name = item["name"]
    base, _ = os.path.splitext(orig_name)
    mp4_name = base + ".mp4"

    orig_path = os.path.join(output_dir, orig_name)
    mp4_path = os.path.join(output_dir, mp4_name)

    if os.path.exists(mp4_path) and os.path.getsize(mp4_path) > 0:
        return True
    if os.path.exists(orig_path) and os.path.getsize(orig_path) == item["size"]:
        if orig_name.lower().endswith(".mov"):
            convert_to_mp4(orig_path)
        return True

    return False


def download_file(item: dict, output_dir: str, manager: GofileManager, progress: Progress, total_task: TaskID, max_retries: int = 5):
    filename = item["name"]
    file_size = item["size"]
    dest_path = os.path.join(output_dir, filename)
    part_path = dest_path + ".part"

    if is_already_downloaded(item, output_dir):
        progress.update(total_task, advance=file_size)
        return True, f"[dim]Saltado (ya existe): {filename}[/dim]"

    retries = 0
    while retries < max_retries:
        try:
            downloaded = 0
            mode = "wb"
            headers = {
                "User-Agent": manager.user_agent,
                "Referer": "https://gofile.io/",
                "Accept": "*/*",
            }

            if os.path.exists(part_path):
                downloaded = os.path.getsize(part_path)
                if downloaded < file_size:
                    headers["Range"] = f"bytes={downloaded}-"
                    mode = "ab"
                elif downloaded >= file_size:
                    shutil.move(part_path, dest_path)
                    final_path = convert_to_mp4(dest_path)
                    progress.update(total_task, advance=file_size)
                    return True, f"[green]Listo: {os.path.basename(final_path)}[/green]"

            file_task = progress.add_task(f"[cyan]{filename[:28]}[/cyan]", total=file_size, completed=downloaded)

            with requests.get(item["link"], headers=headers, cookies=manager.cookies, stream=True, timeout=30) as r:
                if r.status_code in (401, 403, 410):
                    progress.remove_task(file_task)
                    manager.refresh_links()
                    retries += 1
                    continue

                if r.status_code not in (200, 206):
                    progress.remove_task(file_task)
                    raise Exception(f"HTTP {r.status_code}")

                with open(part_path, mode) as f:
                    for chunk in r.iter_content(chunk_size=512 * 1024):
                        if chunk:
                            f.write(chunk)
                            progress.update(file_task, advance=len(chunk))
                            progress.update(total_task, advance=len(chunk))

            progress.remove_task(file_task)

            if os.path.getsize(part_path) >= file_size:
                shutil.move(part_path, dest_path)
                final_path = convert_to_mp4(dest_path)
                return True, f"[green]Descargado y en MP4: {os.path.basename(final_path)}[/green]"
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
            time.sleep(2 * retries)

    return False, f"[red]Error tras varios intentos: {filename}[/red]"


def process_gofile_download(raw_url: str, custom_output: str = None, workers: int = 3, auto_yes: bool = False):
    content_id = extract_gofile_id(raw_url)
    if not content_id:
        console.print("[bold red]❌ Enlace o ID no válido.[/bold red]")
        return

    manager = GofileManager(content_id)
    items = manager.fetch_folder()

    if not items:
        console.print("[bold red]❌ No se encontraron archivos en la carpeta de Gofile o el enlace es privado.[/bold red]")
        return

    folder_title = sanitize_folder_name(manager.folder_name)

    if not custom_output:
        suggested_dir = os.path.join(BASE_DEFAULT_DIR, folder_title)
        console.print(f"\n[bold green]📁 Carpeta de destino:[/bold green] [yellow]{suggested_dir}[/yellow]")
        user_dest = console.input("[bold white]Presiona ENTER para usar esa carpeta, o escribe otra ruta: [/bold white]").strip()
        output_dir = os.path.abspath(user_dest) if user_dest else os.path.abspath(suggested_dir)
    else:
        output_dir = os.path.abspath(custom_output)

    os.makedirs(output_dir, exist_ok=True)
    convert_existing_movs(output_dir)

    items.sort(key=lambda x: x["size"], reverse=True)

    total_bytes = sum(i["size"] for i in items)
    total_gb = total_bytes / (1024**3)

    disk_total, disk_used, disk_free = shutil.disk_usage(output_dir)
    disk_free_gb = disk_free / (1024**3)
    drive_letter = os.path.splitdrive(output_dir)[0] or output_dir

    table = Table(title="📊 Resumen de la Descarga")
    table.add_column("Propiedad", style="cyan")
    table.add_column("Detalle", style="magenta")

    table.add_row("Nombre de carpeta Gofile", manager.folder_name)
    table.add_row("Total de archivos", str(len(items)))
    table.add_row("Tamaño total de videos", f"{total_gb:.2f} GB ({total_bytes / (1024**2):.1f} MB)")
    table.add_row(f"Espacio libre en {drive_letter}", f"{disk_free_gb:.2f} GB")
    table.add_row("Orden de descarga", "⬇️ Más pesados primero")
    table.add_row("Formato final", "🎬 Todo en .MP4 (FFmpeg copy)")
    table.add_row("Descargas simultáneas", f"{workers} en paralelo")
    table.add_row("Carpeta destino", output_dir)
    console.print(table)

    if disk_free_gb < total_gb:
        console.print(f"\n[bold red]⚠️ Espacio insuficiente en {drive_letter}: Se requieren {total_gb:.2f} GB y tienes {disk_free_gb:.2f} GB disponibles.[/bold red]")
        return

    if not auto_yes:
        resp = console.input("\n[bold green]¿Deseas iniciar la descarga de los videos ahora? (s/n): [/bold green]").strip().lower()
        if resp not in ('s', 'si', 'y', 'yes', ''):
            console.print("[yellow]Descarga omitida.[/yellow]")
            return

    console.print(f"\n[bold green]🚀 Iniciando descarga ({workers} en paralelo) en:[/bold green] [yellow]{output_dir}[/yellow]\n")

    progress = Progress(
        TextColumn("[bold blue]{task.description}"),
        BarColumn(),
        DownloadColumn(),
        TransferSpeedColumn(),
        TimeRemainingColumn(),
        console=console,
    )

    with progress:
        total_task = progress.add_task(f"[bold magenta]Progreso Total ({len(items)} videos)[/bold magenta]", total=total_bytes)

        if workers <= 1:
            for idx, item in enumerate(items, 1):
                console.print(f"[bold green]▶ [{idx}/{len(items)}][/bold green] Descargando [yellow]{item['name']}[/yellow] ({item['size'] / (1024**2):.1f} MB)...")
                success, msg = download_file(item, output_dir, manager, progress, total_task)
                if not success:
                    console.print(msg)
        else:
            with ThreadPoolExecutor(max_workers=workers) as executor:
                futures = {
                    executor.submit(download_file, item, output_dir, manager, progress, total_task): item
                    for item in items
                }
                for future in as_completed(futures):
                    success, msg = future.result()
                    if not success:
                        console.print(msg)

    console.print(f"\n[bold green]🎉 ¡Todos los {len(items)} videos se han descargado y convertido a .MP4 en:[/bold green]")
    console.print(f"[bold yellow]{output_dir}[/bold yellow]\n")


def main():
    parser = argparse.ArgumentParser(description="Bot descargador interactivo de Gofile")
    parser.add_argument("url", nargs="?", default=None, help="URL o ID de la carpeta Gofile")
    parser.add_argument("--output", "-o", default=None, help="Carpeta destino")
    parser.add_argument("--workers", "-w", type=int, default=3, help="Descargas simultáneas (default: 3)")
    parser.add_argument("--yes", "-y", action="store_true", help="Iniciar sin confirmación interactiva")
    args = parser.parse_args()

    console.print(Panel.fit(
        "[bold cyan]🤖 Bot Descargador de Gofile.io (Modo Universal)[/bold cyan]\n"
        "[yellow]• Acepta cualquier enlace o ID de Gofile[/yellow]\n"
        "[yellow]• Auto-instalación de herramientas y dependencias[/yellow]\n"
        "[yellow]• Auto-conversión a .MP4 sin pérdida de calidad[/yellow]\n"
        "[yellow]• Descargas paralelas optimizadas a máxima velocidad[/yellow]",
        border_style="cyan"
    ))

    if args.url:
        process_gofile_download(args.url, args.output, args.workers, args.yes)
        return

    while True:
        console.print("\n" + "─"*70)
        user_url = console.input("[bold green]🔗 Pega el enlace o ID de Gofile[/bold green] (o escribe [bold red]'q'[/bold red] para salir): ").strip()
        if not user_url or user_url.lower() == 'q':
            console.print("[yellow]Saliendo del descargador de Gofile.[/yellow]")
            break

        process_gofile_download(user_url, args.output, args.workers, args.yes)


if __name__ == "__main__":
    main()
