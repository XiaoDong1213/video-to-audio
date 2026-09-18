"""FFmpeg 检测与文件工具（优先使用内置二进制）。"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from core.formats import is_audio_file, is_video_file
from core.paths import resolve_binary


class FFmpegNotFoundError(RuntimeError):
    """Raised when ffmpeg / ffprobe cannot be found (bundled or PATH)."""


def which_ffmpeg() -> str:
    path = resolve_binary("ffmpeg")
    if not path:
        raise FFmpegNotFoundError(
            "未找到 ffmpeg。\n"
            "请将 ffmpeg.exe / ffprobe.exe 放到 resources/ffmpeg/，\n"
            "或安装系统 FFmpeg 并加入 PATH。\n"
            "  Windows: winget install Gyan.FFmpeg"
        )
    return str(path)


def which_ffprobe() -> str:
    path = resolve_binary("ffprobe")
    if not path:
        raise FFmpegNotFoundError(
            "未找到 ffprobe。请将 ffprobe.exe 与 ffmpeg.exe 一并放入 resources/ffmpeg/。"
        )
    return str(path)


def ensure_ffmpeg() -> tuple[str, str | None]:
    """Return (ffmpeg_path, ffprobe_path_or_None)."""
    ffmpeg = which_ffmpeg()
    try:
        ffprobe = which_ffprobe()
    except FFmpegNotFoundError:
        ffprobe = None
    return ffmpeg, ffprobe


def ffmpeg_version(ffmpeg: str | None = None) -> str:
    binary = ffmpeg or which_ffmpeg()
    result = subprocess.run(
        [binary, "-version"],
        capture_output=True,
        text=True,
        check=False,
        encoding="utf-8",
        errors="replace",
    )
    first = (result.stdout or result.stderr or "").splitlines()
    return first[0] if first else "unknown"


def unique_output_path(path: Path) -> Path:
    """If path exists, append _1, _2, ... before the suffix."""
    if not path.exists():
        return path
    stem, suffix, parent = path.stem, path.suffix, path.parent
    index = 1
    while True:
        candidate = parent / f"{stem}_{index}{suffix}"
        if not candidate.exists():
            return candidate
        index += 1


def collect_video_files(source: Path, *, recursive: bool = False) -> list[Path]:
    if source.is_file():
        if is_video_file(source.suffix):
            return [source.resolve()]
        raise ValueError(f"不支持的视频文件: {source}")

    if not source.is_dir():
        raise FileNotFoundError(f"路径不存在: {source}")

    pattern_iter = source.rglob("*") if recursive else source.glob("*")
    files = [
        item.resolve()
        for item in pattern_iter
        if item.is_file() and is_video_file(item.suffix)
    ]
    return sorted(files)


def collect_audio_files(sources: list[Path], *, recursive: bool = False) -> list[Path]:
    """Collect audio files from paths, preserving order for explicit file lists."""
    files: list[Path] = []
    seen: set[Path] = set()

    for source in sources:
        source = source.resolve()
        if source.is_file():
            if not is_audio_file(source.suffix):
                raise ValueError(f"不支持的音频文件: {source}")
            if source not in seen:
                files.append(source)
                seen.add(source)
            continue

        if not source.is_dir():
            raise FileNotFoundError(f"路径不存在: {source}")

        pattern_iter = source.rglob("*") if recursive else source.glob("*")
        dir_files = sorted(
            item.resolve()
            for item in pattern_iter
            if item.is_file() and is_audio_file(item.suffix)
        )
        for item in dir_files:
            if item not in seen:
                files.append(item)
                seen.add(item)

    return files


def default_output_for(input_path: Path, fmt_extension: str, output_dir: Path | None) -> Path:
    target_dir = output_dir if output_dir is not None else input_path.parent
    target_dir.mkdir(parents=True, exist_ok=True)
    return unique_output_path(target_dir / f"{input_path.stem}{fmt_extension}")


def probe_duration_seconds(input_path: Path, ffprobe: str | None = None) -> float | None:
    """Return media duration in seconds, or None if unavailable."""
    try:
        probe = ffprobe or which_ffprobe()
    except FFmpegNotFoundError:
        return None
    cmd = [
        probe,
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "default=noprint_wrappers=1:nokey=1",
        str(input_path),
    ]
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=False,
            encoding="utf-8",
            errors="replace",
        )
    except OSError:
        return None
    raw = (proc.stdout or "").strip()
    if not raw:
        return None
    try:
        value = float(raw)
    except ValueError:
        return None
    return value if value > 0 else None


def probe_audio_streams(input_path: Path, ffprobe: str | None = None) -> list[dict]:
    """Return audio stream metadata via ffprobe, or empty list if unavailable."""
    try:
        probe = ffprobe or which_ffprobe()
    except FFmpegNotFoundError:
        return []

    cmd = [
        probe,
        "-v",
        "quiet",
        "-print_format",
        "json",
        "-show_streams",
        "-select_streams",
        "a",
        str(input_path),
    ]
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        check=False,
        encoding="utf-8",
        errors="replace",
    )
    if result.returncode != 0:
        return []
    try:
        data = json.loads(result.stdout or "{}")
    except json.JSONDecodeError:
        return []
    return list(data.get("streams") or [])


def format_stream_summary(streams: list[dict]) -> str:
    if not streams:
        return "(未检测到音轨 / ffprobe 不可用)"
    lines: list[str] = []
    for idx, stream in enumerate(streams):
        codec = stream.get("codec_name", "?")
        channels = stream.get("channels", "?")
        rate = stream.get("sample_rate", "?")
        lang = (stream.get("tags") or {}).get("language", "")
        lang_part = f", lang={lang}" if lang else ""
        lines.append(f"  [{idx}] {codec}, {channels}ch, {rate}Hz{lang_part}")
    return "\n".join(lines)
