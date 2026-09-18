"""Command-line interface for Video to audio."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.progress import BarColumn, Progress, TaskProgressColumn, TextColumn
from rich.table import Table

from app.identity import APP_VERSION as __version__
from core.converter import (
    BatchReport,
    ConvertOptions,
    MergeOptions,
    convert_file,
    convert_many,
    merge_files,
    write_failure_log,
)
from core.formats import OUTPUT_FORMATS
from core.utils import (
    FFmpegNotFoundError,
    collect_audio_files,
    collect_video_files,
    ensure_ffmpeg,
    ffmpeg_version,
    format_stream_summary,
    probe_audio_streams,
)

app = typer.Typer(
    name="video-to-audio",
    help="Extract / merge audio with FFmpeg.",
    add_completion=False,
    no_args_is_help=True,
)
console = Console()

_QUALITY_HELP = (
    "MP3 quality: high(默认)/medium(128k·44.1kHz)/low(32k·22.05kHz) or 高/中/低"
)


def _options_from_flags(
    *,
    format: str,
    quality: Optional[str],
    bitrate: Optional[str],
    sample_rate: Optional[int],
    channels: Optional[int],
    start: Optional[str],
    end: Optional[str],
    duration: Optional[str],
    audio_stream: Optional[int],
    copy: bool,
    overwrite: bool,
    output_dir: Optional[Path],
) -> ConvertOptions:
    return ConvertOptions(
        format=format,
        quality=quality,
        bitrate=bitrate,
        sample_rate=sample_rate,
        channels=channels,
        start=start,
        end=end,
        duration=duration,
        audio_stream=audio_stream,
        copy_audio=copy,
        overwrite=overwrite,
        output_dir=output_dir,
    )


@app.callback()
def main(
    version: bool = typer.Option(
        False,
        "--version",
        "-V",
        help="Show version and exit.",
        is_eager=True,
    ),
) -> None:
    if version:
        console.print(f"video-to-audio {__version__}")
        raise typer.Exit()


@app.command("check")
def check_cmd() -> None:
    """Verify that FFmpeg is installed and printable."""
    try:
        ffmpeg, ffprobe = ensure_ffmpeg()
    except FFmpegNotFoundError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1) from exc

    console.print(f"[green]ffmpeg[/green]: {ffmpeg}")
    console.print(f"  {ffmpeg_version(ffmpeg)}")
    if ffprobe:
        console.print(f"[green]ffprobe[/green]: {ffprobe}")
    else:
        console.print("[yellow]ffprobe[/yellow]: not found (stream listing limited)")


@app.command("streams")
def streams_cmd(
    path: Path = typer.Argument(..., exists=True, dir_okay=False, readable=True),
) -> None:
    """List audio streams in a media file."""
    try:
        ensure_ffmpeg()
    except FFmpegNotFoundError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1) from exc

    streams = probe_audio_streams(path)
    console.print(f"[bold]{path.name}[/bold] audio streams:")
    console.print(format_stream_summary(streams))


@app.command("convert")
def convert_cmd(
    source: Path = typer.Argument(..., help="Video file or directory"),
    output: Optional[Path] = typer.Option(
        None,
        "--output",
        "-o",
        help="Output file (single input only) or ignored for directories",
    ),
    output_dir: Optional[Path] = typer.Option(
        None,
        "--output-dir",
        "-d",
        help="Directory for output files",
    ),
    format: str = typer.Option(
        "mp3",
        "--format",
        "-f",
        help=f"Output format: {', '.join(OUTPUT_FORMATS)}",
    ),
    quality: Optional[str] = typer.Option(
        "medium",
        "--quality",
        "-q",
        help=_QUALITY_HELP,
    ),
    bitrate: Optional[str] = typer.Option(
        None,
        "--bitrate",
        "-b",
        help="Override bitrate (wins over --quality), e.g. 256k",
    ),
    sample_rate: Optional[int] = typer.Option(
        None,
        "--sample-rate",
        "-r",
        help="Sample rate in Hz, e.g. 44100",
    ),
    channels: Optional[int] = typer.Option(
        None,
        "--channels",
        "-c",
        help="Number of channels (1=mono, 2=stereo)",
    ),
    start: Optional[str] = typer.Option(
        None,
        "--start",
        "-ss",
        help="Start time (seconds or HH:MM:SS)",
    ),
    end: Optional[str] = typer.Option(
        None,
        "--end",
        "-to",
        help="End time (seconds or HH:MM:SS)",
    ),
    duration: Optional[str] = typer.Option(
        None,
        "--duration",
        "-t",
        help="Duration from start (seconds or HH:MM:SS)",
    ),
    audio_stream: Optional[int] = typer.Option(
        None,
        "--audio-stream",
        "-a",
        help="Audio stream index (0-based)",
    ),
    copy: bool = typer.Option(
        False,
        "--copy",
        help="Copy audio stream without re-encoding (container must match)",
    ),
    recursive: bool = typer.Option(
        False,
        "--recursive",
        "-R",
        help="Recurse into subdirectories when SOURCE is a folder",
    ),
    overwrite: bool = typer.Option(
        False,
        "--overwrite",
        "-y",
        help="Overwrite existing output files",
    ),
    log_file: Optional[Path] = typer.Option(
        None,
        "--log",
        help="Write failure details to this log file",
    ),
) -> None:
    """Convert one video or a folder of videos to audio."""
    try:
        ensure_ffmpeg()
    except FFmpegNotFoundError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1) from exc

    opts = _options_from_flags(
        format=format,
        quality=quality,
        bitrate=bitrate,
        sample_rate=sample_rate,
        channels=channels,
        start=start,
        end=end,
        duration=duration,
        audio_stream=audio_stream,
        copy=copy,
        overwrite=overwrite,
        output_dir=output_dir,
    )

    try:
        files = collect_video_files(source, recursive=recursive)
    except (ValueError, FileNotFoundError) as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1) from exc

    if not files:
        console.print("[yellow]No video files found.[/yellow]")
        raise typer.Exit(code=1)

    if output is not None and len(files) > 1:
        console.print("[red]--output/-o only works with a single input file.[/red]")
        raise typer.Exit(code=1)

    if len(files) == 1:
        result = convert_file(files[0], output_path=output, options=opts)
        if result.ok:
            console.print(f"[green]OK[/green] {result.input_path.name} → {result.output_path}")
            raise typer.Exit(code=0)
        console.print(f"[red]FAILED[/red] {result.input_path}")
        console.print(result.message)
        if log_file:
            report = BatchReport(results=[result])
            path = write_failure_log(report, log_file)
            if path:
                console.print(f"Log written: {path}")
        raise typer.Exit(code=1)

    with Progress(
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("Converting", total=len(files))

        def on_item(index: int, total: int, result) -> None:  # noqa: ANN001
            status = "OK" if result.ok else "FAIL"
            progress.update(
                task,
                advance=1,
                description=f"[{status}] {result.input_path.name} ({index}/{total})",
            )

        report = convert_many(files, options=opts, on_item=on_item)

    table = Table(title="Batch summary")
    table.add_column("Status")
    table.add_column("Count", justify="right")
    table.add_row("[green]Succeeded[/green]", str(len(report.succeeded)))
    table.add_row("[red]Failed[/red]", str(len(report.failed)))
    console.print(table)

    for item in report.failed:
        console.print(f"[red]• {item.input_path}[/red]")
        console.print(f"  {item.message.splitlines()[-1] if item.message else 'error'}")

    log_path = log_file or (Path.cwd() / "video-to-audio-failures.log")
    written = write_failure_log(report, log_path)
    if written:
        console.print(f"Failure log: {written}")

    raise typer.Exit(code=0 if not report.failed else 1)


@app.command("merge")
def merge_cmd(
    sources: list[Path] = typer.Argument(
        ...,
        help="Audio files and/or folders (order preserved for files)",
    ),
    output: Optional[Path] = typer.Option(
        None,
        "--output",
        "-o",
        help="Merged output file path",
    ),
    output_dir: Optional[Path] = typer.Option(
        None,
        "--output-dir",
        "-d",
        help="Directory for the merged file when -o is omitted",
    ),
    format: str = typer.Option(
        "mp3",
        "--format",
        "-f",
        help=f"Output format: {', '.join(OUTPUT_FORMATS)}",
    ),
    quality: Optional[str] = typer.Option(
        "medium",
        "--quality",
        "-q",
        help=_QUALITY_HELP,
    ),
    bitrate: Optional[str] = typer.Option(
        None,
        "--bitrate",
        "-b",
        help="Override bitrate (wins over --quality)",
    ),
    sample_rate: Optional[int] = typer.Option(
        None,
        "--sample-rate",
        "-r",
        help="Sample rate in Hz",
    ),
    channels: Optional[int] = typer.Option(
        None,
        "--channels",
        "-c",
        help="Number of channels",
    ),
    recursive: bool = typer.Option(
        False,
        "--recursive",
        "-R",
        help="Recurse into folders",
    ),
    overwrite: bool = typer.Option(
        False,
        "--overwrite",
        "-y",
        help="Overwrite existing output",
    ),
) -> None:
    """Merge multiple audio files into one (concat in given order)."""
    try:
        ensure_ffmpeg()
    except FFmpegNotFoundError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1) from exc

    try:
        files = collect_audio_files(sources, recursive=recursive)
    except (ValueError, FileNotFoundError) as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1) from exc

    if len(files) < 2:
        console.print("[red]Need at least 2 audio files to merge.[/red]")
        raise typer.Exit(code=1)

    console.print(f"Merging {len(files)} files → {format}" + (f" quality={quality}" if format == "mp3" else ""))
    for i, f in enumerate(files, 1):
        console.print(f"  {i}. {f.name}")

    opts = MergeOptions(
        format=format,
        quality=quality,
        bitrate=bitrate,
        sample_rate=sample_rate,
        channels=channels,
        overwrite=overwrite,
        output_dir=output_dir,
    )
    result = merge_files(files, output_path=output, options=opts)
    if result.ok:
        console.print(f"[green]OK[/green] → {result.output_path}")
        raise typer.Exit(code=0)

    console.print("[red]FAILED[/red]")
    console.print(result.message)
    raise typer.Exit(code=1)


@app.command("gui")
def gui_cmd() -> None:
    """Open the graphical interface."""
    try:
        ensure_ffmpeg()
    except FFmpegNotFoundError as exc:
        console.print(f"[red]{exc}[/red]")
        console.print("GUI can still open; sync_ffmpeg.bat if needed.")

    from app.main import _run_gui

    raise SystemExit(_run_gui())


def entry() -> None:
    app()


if __name__ == "__main__":
    entry()
