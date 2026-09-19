"""FFmpeg 检测与文件工具（优先使用内置二进制）。"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

from core.formats import is_audio_file, is_video_file
from core.paths import resolve_binary


class FFmpegNotFoundError(RuntimeError):
    """Raised when ffmpeg / ffprobe cannot be found (bundled or PATH)."""


def _win_no_window_kwargs() -> dict[str, Any]:
    """Avoid console flash when spawning ffmpeg/ffprobe from a GUI process."""
    if sys.platform != "win32":
        return {}
    # CREATE_NO_WINDOW = 0x08000000
    return {"creationflags": getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)}


def run_hidden(cmd: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
    """subprocess.run with Windows console hidden."""
    merged = {
        "capture_output": True,
        "text": True,
        "check": False,
        "encoding": "utf-8",
        "errors": "replace",
        **_win_no_window_kwargs(),
        **kwargs,
    }
    return subprocess.run(cmd, **merged)


def popen_hidden(cmd: list[str], **kwargs: Any) -> subprocess.Popen[str]:
    """subprocess.Popen with Windows console hidden."""
    merged = {**_win_no_window_kwargs(), **kwargs}
    return subprocess.Popen(cmd, **merged)


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
    result = run_hidden([binary, "-version"])
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


def parse_optional_positive_int(
    raw: str,
    label: str,
    *,
    maximum: int | None = None,
) -> int | None:
    """Parse a blank-or-positive-integer field. Raises ValueError with a user-facing message."""
    text = raw.strip()
    if not text:
        return None
    if not text.isdigit():
        raise ValueError(f"{label}请填写正整数，或留空。")
    value = int(text)
    if value <= 0:
        raise ValueError(f"{label}须为正整数。")
    if maximum is not None and value > maximum:
        raise ValueError(f"{label}不能大于 {maximum}。")
    return value


def move_selected(items: list, selected: list[int], delta: int) -> list[int] | None:
    """Shift selected indexes by -1 or +1, keeping gaps. Mutates items. None if nothing moved."""
    if delta not in (-1, 1) or not selected:
        return None
    count = len(items)
    moving = set(selected)
    order = sorted(moving) if delta < 0 else sorted(moving, reverse=True)
    changed = False
    for index in order:
        target = index + delta
        if target < 0 or target >= count or target in moving:
            continue
        items[index], items[target] = items[target], items[index]
        moving.remove(index)
        moving.add(target)
        changed = True
    if not changed:
        return None
    return sorted(moving)


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
        proc = run_hidden(cmd)
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
    result = run_hidden(cmd)
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
