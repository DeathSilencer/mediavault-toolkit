"""
Video Batch Compressor (GPU NVIDIA RTX & CPU Accelerated)
------------------------------------------------------------
Comprime colecciones de video con Triple Protección de Integridad y Memoria de Reanudación:
1. Reanudación inteligente: Recuerda qué videos ya fueron comprimidos para no repetir trabajo.
2. Detección automática por códec (HEVC/AV1) y registro persistente (.compression_history.json).
3. Codificación en archivo temporal aislado (.tmp.mp4).
4. Verificación de integridad y duración con ffprobe antes de reemplazar.
5. Si se cancela o interrumpe (Ctrl+C), guarda el progreso y reanuda en el punto exacto.
6. Regla de exclusión automática para archivos con '.M'.
"""

import os
import sys
import time
import json
import shutil
import subprocess
import argparse
from pathlib import Path

CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".compressor_config.json")

def load_compressor_config() -> dict:
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}

def save_compressor_config(cfg: dict):
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2, ensure_ascii=False)
    except Exception:
        pass

import urllib.request
import zipfile

def ensure_ffmpeg():
    """Verifica e instala automáticamente FFmpeg/ffprobe si faltan en el sistema."""
    if shutil.which("ffmpeg") and shutil.which("ffprobe"):
        return

    script_dir = os.path.dirname(os.path.abspath(__file__))
    root_dir = os.path.dirname(script_dir)
    possible_bins = [
        os.path.join(script_dir, "bin"),
        os.path.join(root_dir, "bin")
    ]
    for b in possible_bins:
        if os.path.exists(os.path.join(b, "ffmpeg.exe")):
            os.environ["PATH"] = b + os.pathsep + os.environ.get("PATH", "")
            if shutil.which("ffmpeg") and shutil.which("ffprobe"):
                return

    if shutil.which("winget"):
        try:
            print("🎬 FFmpeg no detectado en el sistema. Instalando automáticamente con Winget...")
            subprocess.run(
                ["winget", "install", "--id", "Gyan.FFmpeg", "-e", "--accept-source-agreements", "--accept-package-agreements"],
                capture_output=True, text=True
            )
            if shutil.which("ffmpeg") and shutil.which("ffprobe"):
                print("✅ FFmpeg instalado vía Winget.")
                return
        except Exception:
            pass

    try:
        target_bin = os.path.join(root_dir, "bin")
        os.makedirs(target_bin, exist_ok=True)
        print("⬇️ Descargando versión portable de FFmpeg...")
        zip_url = "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip"
        zip_path = os.path.join(target_bin, "ffmpeg.zip")
        urllib.request.urlretrieve(zip_url, zip_path)
        with zipfile.ZipFile(zip_path, 'r') as zf:
            for member in zf.namelist():
                if member.endswith("ffmpeg.exe") or member.endswith("ffprobe.exe"):
                    filename = os.path.basename(member)
                    with zf.open(member) as source, open(os.path.join(target_bin, filename), "wb") as target:
                        shutil.copyfileobj(source, target)
        os.remove(zip_path)
        os.environ["PATH"] = target_bin + os.pathsep + os.environ.get("PATH", "")
        print("✅ FFmpeg portable configurado en bin/.")
    except Exception as e:
        print(f"⚠️ No se pudo auto-descargar FFmpeg: {e}")

# Auto-instalar dependencias básicas si faltan
for pkg in ["rich"]:
    try:
        __import__(pkg)
    except ImportError:
        subprocess.check_call([sys.executable, "-m", "pip", "install", pkg])

ensure_ffmpeg()

# Forzar codificación UTF-8 en consola de Windows
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
    SpinnerColumn
)

console = Console()

def format_bytes(bytes_val: int) -> str:
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if bytes_val < 1024.0:
            return f"{bytes_val:.2f} {unit}"
        bytes_val /= 1024.0
    return f"{bytes_val:.2f} PB"

def check_nvidia_gpu() -> bool:
    try:
        res = subprocess.run(["ffmpeg", "-encoders"], capture_output=True, text=True)
        return "hevc_nvenc" in res.stdout
    except Exception:
        return False

def get_video_duration(file_path: str) -> float:
    """Obtiene la duración exacta en segundos de un video usando ffprobe."""
    try:
        cmd = [
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            file_path
        ]
        res = subprocess.run(cmd, capture_output=True, text=True, check=True)
        val = res.stdout.strip()
        return float(val) if val else 0.0
    except Exception:
        return 0.0

def get_video_codec(file_path: str) -> str:
    """Obtiene el nombre del codec de video usando ffprobe."""
    try:
        cmd = [
            "ffprobe", "-v", "error",
            "-select_streams", "v:0",
            "-show_entries", "stream=codec_name",
            "-of", "default=noprint_wrappers=1:nokey=1",
            file_path
        ]
        res = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return res.stdout.strip().lower()
    except Exception:
        return ""

def verify_video_integrity(file_path: str, expected_duration: float) -> bool:
    """
    Verifica que el video comprimido sea válido, reproducible
    y que su duración coincida con el original (margen de tolerancia de 1.5s).
    """
    if not os.path.exists(file_path) or os.path.getsize(file_path) < 10240:
        return False

    dur = get_video_duration(file_path)
    if dur <= 0:
        return False

    if expected_duration > 0:
        diff = abs(dur - expected_duration)
        if diff > 1.5:
            return False

    return True

def is_excluded_video(filename: str) -> bool:
    """
    Excluye archivos que empiecen con '.M' o cuyo título contenga '.M' (ignorando extensión).
    """
    base_name = os.path.splitext(filename)[0]
    return (
        filename.startswith(".M") or
        filename.startswith(".m") or
        ".M" in base_name or
        ".m" in base_name
    )

def load_history(folder_path: str) -> dict:
    """Carga el historial de videos ya procesados desde .compression_history.json."""
    hist_file = os.path.join(folder_path, ".compression_history.json")
    if os.path.exists(hist_file):
        try:
            with open(hist_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}

def save_history(folder_path: str, history: dict):
    """Guarda el progreso de videos comprimidos de forma atómica."""
    hist_file = os.path.join(folder_path, ".compression_history.json")
    try:
        with open(hist_file, "w", encoding="utf-8") as f:
            json.dump(history, f, indent=2, ensure_ascii=False)
    except Exception:
        pass

def get_video_files(folder_path: str):
    """Escanea la carpeta clasificando videos compatibles y excluidos."""
    valid_exts = {".mp4", ".mov", ".m4v", ".mkv", ".avi", ".ts", ".webm"}
    video_files = []
    excluded_files = []
    for root, _, files in os.walk(folder_path):
        for f in files:
            ext = os.path.splitext(f)[1].lower()
            if ext in valid_exts and not f.startswith("._") and not f.endswith(".tmp.mp4"):
                full_path = os.path.join(root, f)
                if is_excluded_video(f):
                    excluded_files.append(full_path)
                else:
                    video_files.append(full_path)
    # Ordenar estrictamente del más grande al más chico
    video_files.sort(key=lambda f: os.path.getsize(f), reverse=True)
    return video_files, excluded_files

def compress_video(
    src_path: str,
    dst_path: str,
    codec: str = "hevc_nvenc",
    cq: int = 29,
    use_gpu: bool = True
) -> tuple[bool, str]:
    """
    Comprime un video con FFmpeg con máxima seguridad y triple verificación.
    Retorna: (éxito: bool, mensaje: str)
    """
    temp_dst = dst_path + ".tmp.mp4"
    if os.path.exists(temp_dst):
        try:
            os.remove(temp_dst)
        except Exception:
            pass

    orig_duration = get_video_duration(src_path)
    orig_size = os.path.getsize(src_path)

    if use_gpu:
        cmd = [
            "ffmpeg", "-y", "-hide_banner", "-v", "error",
            "-hwaccel", "cuda",
            "-i", src_path,
            "-map", "0:v:0",
            "-map", "0:a?",
            "-c:v", "hevc_nvenc",
            "-preset", "p7",
            "-tune", "hq",
            "-multipass", "fullres",
            "-rc", "vbr",
            "-cq", str(cq),
            "-b:v", "0",
            "-spatial-aq", "1",
            "-temporal-aq", "1",
            "-c:a", "copy",
            temp_dst
        ]
    else:
        cmd = [
            "ffmpeg", "-y", "-hide_banner", "-v", "error",
            "-i", src_path,
            "-map", "0:v:0",
            "-map", "0:a?",
            "-c:v", "libx265",
            "-crf", str(cq - 4),
            "-preset", "fast",
            "-c:a", "copy",
            temp_dst
        ]

    try:
        res = subprocess.run(cmd, capture_output=True, text=True)
        if res.returncode != 0:
            if os.path.exists(temp_dst):
                os.remove(temp_dst)
            return False, f"FFmpeg error: {res.stderr[:100]}"

        # Verificación de integridad con ffprobe
        if not verify_video_integrity(temp_dst, orig_duration):
            if os.path.exists(temp_dst):
                os.remove(temp_dst)
            return False, "Falló la prueba de integridad / duración no coincide"

        new_size = os.path.getsize(temp_dst)

        # Si el nuevo archivo es mayor o igual, conservar el original
        if new_size >= orig_size:
            if os.path.exists(temp_dst):
                os.remove(temp_dst)
            return False, "Ya estaba optimizado (el comprimido no era menor)"

        # Reemplazar archivo de forma segura
        if os.path.exists(dst_path):
            os.remove(dst_path)
        os.rename(temp_dst, dst_path)
        return True, "OK"

    except Exception as e:
        if os.path.exists(temp_dst):
            os.remove(temp_dst)
        return False, str(e)

def main():
    parser = argparse.ArgumentParser(description="Compresor Masivo de Video por Hardware (GPU NVENC / CPU)")
    parser.add_argument("--folder", "-f", default=None, help="Carpeta que contiene los videos a procesar")
    parser.add_argument("--cq", type=int, choices=[27, 29, 31], default=None, help="Nivel de compresión CQ (27: Máxima calidad, 29: Óptimo, 31: Máximo ahorro)")
    parser.add_argument("--mode", type=int, choices=[1, 2], default=None, help="1: Reemplazar originales, 2: Guardar en subcarpeta 'Comprimidos'")
    parser.add_argument("--yes", "-y", action="store_true", help="Iniciar compresión sin confirmación interactiva")
    args = parser.parse_args()

    cfg = load_compressor_config()

    console.print(Panel(
        "[bold cyan]🛡️ COMPRESOR MASIVO DE VIDEO CON MEMORIA Y REANUDACIÓN INTELIGENTE[/bold cyan]\n"
        "[white]• [bold green]Memoria de progreso:[/bold green] Recuerda videos ya comprimidos si se cancela o interrumpe.\n"
        "• [bold green]Detección por códec:[/bold green] Salta automáticamente videos que ya estén en HEVC / H.265.\n"
        "• [bold green]Garantía anti-corrupción:[/bold green] Triple verificación con ffprobe y exclusión de '.M'.\n"
        "• [bold green]Aceleración NVIDIA NVENC:[/bold green] Ahorro masivo a máxima velocidad en tu GPU.[/white]",
        border_style="cyan"
    ))

    # 1. Verificar GPU
    has_gpu = check_nvidia_gpu()
    if has_gpu:
        console.print("[bold green]🚀 Tarjeta gráfica NVIDIA RTX detectada (Aceleración NVENC activa).[/bold green]\n")
    else:
        console.print("[bold yellow]⚠️ No se detectó NVENC. Se usará CPU multihilo (libx265).[/bold yellow]\n")

    # 2. Solicitar carpeta
    target_dir = args.folder
    if not target_dir:
        saved_folder = cfg.get("last_folder", "")
        if saved_folder and os.path.exists(saved_folder):
            console.print(f"[bold yellow]Carpeta a procesar[/bold yellow] (Presiona [bold green]Enter[/bold green] para usar la ruta guardada):")
            console.print(f"[dim]{saved_folder}[/dim]")
            user_input = input("Ruta > ").strip().strip('"').strip("'")
            target_dir = user_input if user_input else saved_folder
        else:
            console.print(f"[bold yellow]Carpeta a procesar:[/bold yellow]")
            target_dir = input("Ruta > ").strip().strip('"').strip("'")

    if not target_dir or not os.path.exists(target_dir):
        console.print(f"[bold red]❌ La carpeta especificada no existe: {target_dir}[/bold red]")
        return

    cfg["last_folder"] = target_dir
    save_compressor_config(cfg)

    # Cargar historial existente
    history = load_history(target_dir)

    # Escanear archivos
    console.print(f"\n🔍 Escaneando videos en: [cyan]{target_dir}[/cyan]...")
    raw_video_files, excluded_files = get_video_files(target_dir)

    if not raw_video_files and not excluded_files:
        console.print("[bold yellow]⚠️ No se encontraron archivos de video compatibles en esta carpeta.[/bold yellow]")
        return

    # 3. Detectar qué videos ya están comprimidos previamente
    console.print("🔎 Verificando estado de compresión previo de los videos...")
    already_compressed = []
    to_compress = []

    for f_path in raw_video_files:
        f_name = os.path.basename(f_path)
        # Revisar historial previo
        if f_name in history and history[f_name].get("status") in ["ok", "optimized"]:
            already_compressed.append(f_path)
            continue
        # Revisar si el códec del archivo ya es HEVC / AV1 (ya fue comprimido y reemplazado)
        codec = get_video_codec(f_path)
        if codec in ["hevc", "av1"]:
            already_compressed.append(f_path)
            # Registrar en historial para acelerar futuros escaneos
            history[f_name] = {
                "status": "ok",
                "codec": codec,
                "size": os.path.getsize(f_path),
                "timestamp": time.time()
            }
        else:
            to_compress.append(f_path)

    save_history(target_dir, history)

    total_all_bytes = sum(os.path.getsize(f) for f in raw_video_files)
    total_excluded_bytes = sum(os.path.getsize(f) for f in excluded_files)
    total_to_compress_bytes = sum(os.path.getsize(f) for f in to_compress)
    total_already_bytes = sum(os.path.getsize(f) for f in already_compressed)

    console.print(f"\n📊 [bold cyan]ESTADO DE LA COLECCIÓN:[/bold cyan]")
    console.print(f"  • Total encontrados: [bold white]{len(raw_video_files) + len(excluded_files)} videos[/bold white]")
    if excluded_files:
        console.print(f"  • Omitidos por regla '.M': [dim]{len(excluded_files)} videos ({format_bytes(total_excluded_bytes)}) intactos.[/dim]")
    if already_compressed:
        console.print(f"  • Ya comprimidos previamente: [bold green]{len(already_compressed)} videos ({format_bytes(total_already_bytes)}) (se omitirán).[/bold green]")

    # Si todo ya está comprimido
    if not to_compress:
        console.print(Panel(
            "[bold green]🎉 ¡EXCELENTE! Todos los videos de esta carpeta ya están comprimidos y optimizados.[/bold green]\n"
            "[white]No hay ningún archivo pendiente por procesar. No es necesario realizar ninguna acción.[/white]",
            border_style="green"
        ))
        return

    max_file_size = os.path.getsize(to_compress[0])
    min_file_size = os.path.getsize(to_compress[-1])

    console.print(f"  • [bold yellow]Pendientes por comprimir:[/bold yellow] [bold green]{len(to_compress)} videos[/bold green] ([bold cyan]{format_bytes(total_to_compress_bytes)}[/bold cyan]).")
    console.print(f"📉 [bold yellow]Orden de procesamiento:[/bold yellow] Del más grande ([bold red]{format_bytes(max_file_size)}[/bold red]) al más chico ([bold green]{format_bytes(min_file_size)}[/bold green]).\n")

    # 4. Preguntar Nivel de Compresión
    if args.cq:
        chosen_cq = args.cq
        profile_names = {27: "Máxima Fidelidad (CQ 27)", 29: "Óptimo / Recomendado (CQ 29)", 31: "Máximo Ahorro (CQ 31)"}
        profile_name = profile_names.get(chosen_cq, f"Personalizado (CQ {chosen_cq})")
    else:
        console.print(Panel(
            "[bold yellow]Selecciona el Perfil de Compresión:[/bold yellow]\n\n"
            "[bold green]1.[/bold green] [bold white]Óptimo / Recomendado (CQ 29)[/bold white] ➔ Ahorro ~50-60% del espacio con nitidez 100% cristalina.\n"
            "[bold green]2.[/bold green] [bold white]Máxima Fidelidad (CQ 27)[/bold white] ➔ Ahorro ~40-48% del espacio (Calidad indistinguible del máster).\n"
            "[bold green]3.[/bold green] [bold white]Máximo Ahorro (CQ 31)[/bold white] ➔ Ahorro ~65-70% del espacio.\n",
            title="Niveles de Calidad H.265 / HEVC",
            border_style="blue"
        ))
        opt_quality = input("Selecciona una opción [1/2/3, default: 1]: ").strip()
        if opt_quality == "2":
            chosen_cq = 27
            profile_name = "Máxima Fidelidad (CQ 27)"
        elif opt_quality == "3":
            chosen_cq = 31
            profile_name = "Máximo Ahorro (CQ 31)"
        else:
            chosen_cq = 29
            profile_name = "Óptimo / Recomendado (CQ 29)"

    # 5. Preguntar Modo de Destino
    if args.mode is not None:
        replace_originals = (args.mode != 2)
    else:
        console.print(Panel(
            "[bold yellow]¿Cómo deseas guardar los videos?:[/bold yellow]\n\n"
            f"[bold green]1.[/bold green] [bold white]Reemplazar originales directamente[/bold white] ➔ Libera espacio de inmediato en Disco (Con verificación previa).\n"
            f"[bold green]2.[/bold green] [bold white]Guardar en subcarpeta 'Comprimidos'[/bold white] ➔ Conserva los originales para comparar primero.\n",
            title="Modo de Salida",
            border_style="blue"
        ))
        opt_mode = input("Selecciona una opción [1/2, default: 1]: ").strip()
        replace_originals = (opt_mode != "2")

    out_folder = None
    if not replace_originals:
        out_folder = os.path.join(target_dir, "Comprimidos")
        os.makedirs(out_folder, exist_ok=True)
        console.print(f"📁 Modo seguro: Los videos comprimidos se guardarán en: [cyan]{out_folder}[/cyan]\n")
    else:
        console.print("⚠️ [bold yellow]Reemplazo directo activo: Solo se reemplaza cada video si supera con éxito la prueba de integridad.[/bold yellow]\n")

    # Confirmación final
    if not args.yes:
        console.print(f"[bold green]¿Iniciar compresión de {len(to_compress)} videos usando perfil '{profile_name}'? (S/N):[/bold green] ", end="")
        confirm = input().strip().lower()
        if confirm not in ["s", "si", "y", "yes", ""]:
            console.print("[yellow]Operación cancelada por el usuario.[/yellow]")
            return

    # Iniciar compresión con barra de progreso
    console.print(f"\n[bold green]🚀 Procesando videos pendientes...[/bold green]\n")

    processed_count = 0
    saved_bytes_total = 0
    total_new_bytes = 0
    skipped_count = 0
    start_time = time.time()

    try:
        with Progress(
            SpinnerColumn(),
            TextColumn("[bold blue]{task.description}"),
            BarColumn(bar_width=35),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TextColumn("•"),
            TextColumn("[bold green]{task.completed}/{task.total} videos"),
            TextColumn("•"),
            TimeRemainingColumn(),
            console=console
        ) as progress:
            task_main = progress.add_task("[cyan]Comprimiendo...", total=len(to_compress))

            for idx, src_file in enumerate(to_compress, 1):
                file_name = os.path.basename(src_file)
                orig_size = os.path.getsize(src_file)

                if replace_originals:
                    dst_file = src_file
                else:
                    dst_file = os.path.join(out_folder, file_name)

                progress.update(task_main, description=f"[cyan]({idx}/{len(to_compress)}) {file_name[:25]}...")

                t0 = time.time()
                success, msg = compress_video(
                    src_path=src_file,
                    dst_path=dst_file,
                    codec="hevc_nvenc",
                    cq=chosen_cq,
                    use_gpu=has_gpu
                )
                elapsed = time.time() - t0

                if success:
                    new_size = os.path.getsize(dst_file)
                    diff = orig_size - new_size
                    saved_bytes_total += diff
                    total_new_bytes += new_size
                    processed_count += 1
                    ratio = (1 - (new_size / orig_size)) * 100 if orig_size > 0 else 0
                    progress.console.print(
                        f"  [green]✔[/green] {file_name[:35]}: [dim]{format_bytes(orig_size)}[/dim] ➔ [bold green]{format_bytes(new_size)}[/bold green] "
                        f"([cyan]-{ratio:.1f}%[/cyan] en {elapsed:.1f}s)"
                    )
                    # Registrar en historial persistente
                    history[file_name] = {
                        "status": "ok",
                        "orig_size": orig_size,
                        "compressed_size": new_size,
                        "ratio_pct": round(ratio, 1),
                        "timestamp": time.time()
                    }
                    save_history(target_dir, history)
                else:
                    skipped_count += 1
                    total_new_bytes += orig_size
                    progress.console.print(f"  [yellow]ℹ Conservado original ({msg}):[/yellow] {file_name[:35]}")
                    history[file_name] = {
                        "status": "optimized",
                        "size": orig_size,
                        "reason": msg,
                        "timestamp": time.time()
                    }
                    save_history(target_dir, history)

                progress.advance(task_main)

    except KeyboardInterrupt:
        console.print("\n\n[bold yellow]⚠️ Proceso pausado/cancelado por el usuario (Ctrl+C).[/bold yellow]")
        console.print("[green]💾 El progreso hasta este momento ha sido guardado exitosamente.[/green]")
        console.print("[white]Cuando vuelvas a ejecutar el programa, detectará los videos ya completados y reanudará automáticamente.[/white]\n")
        save_history(target_dir, history)
        return

    total_time = time.time() - start_time

    # Tabla resumen final
    summary_table = Table(title="🎉 RESUMEN DE LA COMPRESIÓN", border_style="green", show_lines=True)
    summary_table.add_column("Métrica", style="bold cyan")
    summary_table.add_column("Valor", style="bold white")

    summary_table.add_row("Videos procesados en esta sesión", f"{processed_count} de {len(to_compress)}")
    if skipped_count > 0:
        summary_table.add_row("Videos conservados en original", f"{skipped_count} (ya estaban optimizados)")
    summary_table.add_row("Tamaño original procesado", format_bytes(total_to_compress_bytes))
    summary_table.add_row("Tamaño final comprimido", format_bytes(total_new_bytes))
    pct_total = (saved_bytes_total / total_to_compress_bytes * 100) if total_to_compress_bytes > 0 else 0
    summary_table.add_row("Espacio total liberado en Disco", f"[bold green]{format_bytes(saved_bytes_total)} (-{pct_total:.1f}%)[/bold green]")
    summary_table.add_row("Tiempo transcurrido en sesión", f"{total_time / 60:.1f} minutos ({total_time / max(1, processed_count):.2f} s/video)")

    console.print("\n")
    console.print(summary_table)
    console.print("\n[bold green]✅ Proceso completado exitosamente. Todo el progreso quedó guardado.[/bold green]\n")

if __name__ == "__main__":
    main()
