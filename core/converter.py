"""FFmpeg-based video → audio conversion."""

from __future__ import annotations

import os
import re
import subprocess
import tempfile
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from core.formats import (
    PROFILES,
    EncodeProfile,
    normalize_format,
    resolve_audio_bitrate,
    resolve_audio_sample_rate,
)
from core.utils import (
    default_output_for,
    ensure_ffmpeg,
    probe_audio_streams,
    probe_duration_seconds,
    unique_output_path,
)

ProgressCallback = Callable[[float, str], None]


@dataclass
class ConvertOptions:
    format: str = "mp3"
    quality: str | None = "medium"  # MP3: high/medium/low (高/中/低)
    bitrate: str | None = None
    sample_rate: int | None = None
    channels: int | None = None
    start: str | None = None
    end: str | None = None
    duration: str | None = None
    audio_stream: int | None = None
    copy_audio: bool = False
    overwrite: bool = False
    output_dir: Path | None = None


@dataclass
class MergeOptions:
    format: str = "mp3"
    quality: str | None = "medium"
    bitrate: str | None = None
    sample_rate: int | None = None
    channels: int | None = None
    overwrite: bool = False
    output_dir: Path | None = None


@dataclass
class ConvertResult:
    input_path: Path
    output_path: Path | None
    ok: bool
    message: str
    returncode: int = 0


@dataclass
class BatchReport:
    results: list[ConvertResult] = field(default_factory=list)

    @property
    def succeeded(self) -> list[ConvertResult]:
        return [r for r in self.results if r.ok]

    @property
    def failed(self) -> list[ConvertResult]:
        return [r for r in self.results if not r.ok]


_TIME_RE = re.compile(
    r"^\d+(?:\.\d+)?$|"  # seconds
    r"^(?:\d+:)?\d{1,2}:\d{2}(?:\.\d+)?$"  # HH:MM:SS or MM:SS
)


def _validate_time(label: str, value: str | None) -> None:
    if value is None:
        return
    if not _TIME_RE.match(value.strip()):
        raise ValueError(
            f"Invalid {label} '{value}'. Use seconds (e.g. 12.5) or HH:MM:SS / MM:SS."
        )


def _resolve_profile(fmt: str) -> EncodeProfile:
    return PROFILES[normalize_format(fmt)]


def build_ffmpeg_command(
    ffmpeg: str,
    input_path: Path,
    output_path: Path,
    options: ConvertOptions,
) -> list[str]:
    profile = _resolve_profile(options.format)
    _validate_time("start", options.start)
    _validate_time("end", options.end)
    _validate_time("duration", options.duration)

    if options.end and options.duration:
        raise ValueError("Use either end (-to) or duration (-t), not both.")

    cmd: list[str] = [ffmpeg, "-hide_banner", "-y" if options.overwrite else "-n"]

    # Seek after -i so -ss / -to are absolute timeline points (accurate trim)
    cmd.extend(["-i", str(input_path)])

    if options.start:
        cmd.extend(["-ss", options.start])
    if options.end:
        cmd.extend(["-to", options.end])
    if options.duration:
        cmd.extend(["-t", options.duration])

    cmd.append("-vn")

    if options.audio_stream is not None:
        cmd.extend(["-map", f"0:a:{options.audio_stream}"])

    if options.copy_audio:
        # Stream copy only works when container matches; we still try and let FFmpeg error clearly.
        cmd.extend(["-acodec", "copy"])
    else:
        cmd.extend(["-acodec", profile.codec])
        if profile.needs_bitrate:
            bitrate = resolve_audio_bitrate(
                options.format,
                bitrate=options.bitrate,
                quality=options.quality,
            )
            if bitrate:
                cmd.extend(["-b:a", bitrate])
        rate = resolve_audio_sample_rate(
            options.format,
            sample_rate=options.sample_rate,
            quality=options.quality if options.format == "mp3" else None,
        )
        if rate:
            cmd.extend(["-ar", str(rate)])
        if options.channels:
            cmd.extend(["-ac", str(options.channels)])
        if profile.extra_args:
            cmd.extend(profile.extra_args)

    cmd.append(str(output_path))
    return cmd


def build_merge_command(
    ffmpeg: str,
    inputs: list[Path],
    output_path: Path,
    options: MergeOptions,
) -> list[str]:
    if len(inputs) < 2:
        raise ValueError("Merge requires at least 2 audio files.")

    profile = _resolve_profile(options.format)
    cmd: list[str] = [ffmpeg, "-hide_banner", "-y" if options.overwrite else "-n"]
    for path in inputs:
        cmd.extend(["-i", str(path)])

    n = len(inputs)
    filter_complex = "".join(f"[{i}:a:0]" for i in range(n)) + f"concat=n={n}:v=0:a=1[outa]"
    cmd.extend(["-filter_complex", filter_complex, "-map", "[outa]"])
    cmd.extend(["-acodec", profile.codec])

    if profile.needs_bitrate:
        bitrate = resolve_audio_bitrate(
            options.format,
            bitrate=options.bitrate,
            quality=options.quality,
        )
        if bitrate:
            cmd.extend(["-b:a", bitrate])
    rate = resolve_audio_sample_rate(
        options.format,
        sample_rate=options.sample_rate,
        quality=options.quality if options.format == "mp3" else None,
    )
    if rate:
        cmd.extend(["-ar", str(rate)])
    if options.channels:
        cmd.extend(["-ac", str(options.channels)])
    if profile.extra_args:
        cmd.extend(profile.extra_args)

    cmd.append(str(output_path))
    return cmd


def merge_files(
    inputs: list[Path],
    *,
    output_path: Path | None = None,
    options: MergeOptions | None = None,
    on_progress: ProgressCallback | None = None,
) -> ConvertResult:
    """Concatenate multiple audio files into one (order preserved)."""
    options = options or MergeOptions()
    resolved = [p.resolve() for p in inputs]

    if len(resolved) < 2:
        return ConvertResult(
            resolved[0] if resolved else Path("."),
            None,
            False,
            "Merge requires at least 2 audio files.",
        )

    missing = [p for p in resolved if not p.is_file()]
    if missing:
        return ConvertResult(
            resolved[0],
            None,
            False,
            f"File not found: {missing[0]}",
        )

    try:
        profile = _resolve_profile(options.format)
    except ValueError as exc:
        return ConvertResult(resolved[0], None, False, str(exc))

    try:
        ffmpeg, _ = ensure_ffmpeg()
    except Exception as exc:  # noqa: BLE001
        return ConvertResult(resolved[0], None, False, str(exc))

    if output_path is None:
        stem = f"merged_{resolved[0].stem}"
        target_dir = options.output_dir if options.output_dir is not None else resolved[0].parent
        target_dir.mkdir(parents=True, exist_ok=True)
        output_path = unique_output_path(target_dir / f"{stem}{profile.extension}")
    else:
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        if not options.overwrite:
            output_path = unique_output_path(output_path)

    try:
        cmd = build_merge_command(ffmpeg, resolved, output_path, options)
    except ValueError as exc:
        return ConvertResult(resolved[0], None, False, str(exc))

    if on_progress:
        on_progress(0.0, f"Merging {len(resolved)} files")

    proc = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        check=False,
        encoding="utf-8",
        errors="replace",
    )

    label = Path(" + ".join(p.name for p in resolved[:3]) + ("…" if len(resolved) > 3 else ""))

    if proc.returncode != 0:
        err = (proc.stderr or proc.stdout or "ffmpeg failed").strip()
        tail = "\n".join(err.splitlines()[-12:])
        if on_progress:
            on_progress(1.0, "Failed")
        if output_path.exists() and output_path.stat().st_size == 0:
            output_path.unlink(missing_ok=True)
        return ConvertResult(label, output_path, False, tail, proc.returncode)

    if on_progress:
        on_progress(1.0, f"Done → {output_path.name}")

    return ConvertResult(label, output_path, True, "OK", 0)


def convert_file(
    input_path: Path,
    *,
    output_path: Path | None = None,
    options: ConvertOptions | None = None,
    on_progress: ProgressCallback | None = None,
) -> ConvertResult:
    options = options or ConvertOptions()
    input_path = input_path.resolve()

    if not input_path.is_file():
        return ConvertResult(input_path, None, False, f"File not found: {input_path}")

    try:
        profile = _resolve_profile(options.format)
    except ValueError as exc:
        return ConvertResult(input_path, None, False, str(exc))

    try:
        ffmpeg, ffprobe = ensure_ffmpeg()
    except Exception as exc:  # noqa: BLE001 — surface as result
        return ConvertResult(input_path, None, False, str(exc))

    if options.audio_stream is not None:
        streams = probe_audio_streams(input_path, ffprobe)
        if streams and options.audio_stream >= len(streams):
            return ConvertResult(
                input_path,
                None,
                False,
                f"Audio stream index {options.audio_stream} out of range "
                f"(found {len(streams)} stream(s)).",
            )

    if output_path is None:
        output_path = default_output_for(input_path, profile.extension, options.output_dir)
    else:
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        if not options.overwrite:
            output_path = unique_output_path(output_path)

    try:
        cmd = build_ffmpeg_command(ffmpeg, input_path, output_path, options)
    except ValueError as exc:
        return ConvertResult(input_path, None, False, str(exc))

    if on_progress:
        on_progress(0.0, f"Starting {input_path.name}")

    duration_hint = probe_duration_seconds(input_path, ffprobe)
    # Trimmed output length for accurate % (out_time is relative to output)
    if options.duration:
        trimmed = _parse_hhmmss(options.duration)
        if trimmed and trimmed > 0:
            duration_hint = trimmed
    elif duration_hint and (options.start or options.end):
        start_s = _parse_hhmmss(options.start) if options.start else 0.0
        end_s = _parse_hhmmss(options.end) if options.end else duration_hint
        if start_s is not None and end_s is not None and end_s > (start_s or 0):
            duration_hint = float(end_s) - float(start_s or 0)

    code, err_text = _run_ffmpeg(
        cmd,
        duration_hint,
        on_progress,
        output_path=output_path,
        expected_bytes=_estimate_output_bytes(options, duration_hint),
    )

    if code != 0:
        err = (err_text or "ffmpeg failed").strip()
        tail = "\n".join(err.splitlines()[-12:])
        if on_progress:
            on_progress(1.0, "Failed")
        if output_path.exists() and output_path.stat().st_size == 0:
            output_path.unlink(missing_ok=True)
        return ConvertResult(input_path, output_path, False, tail, code)

    if on_progress:
        on_progress(1.0, f"Done → {output_path.name}")

    return ConvertResult(input_path, output_path, True, "OK", 0)


def _parse_hhmmss(value: str) -> float | None:
    parts = value.strip().split(":")
    try:
        if len(parts) == 3:
            h, m, s = parts
            return int(h) * 3600 + int(m) * 60 + float(s)
        if len(parts) == 2:
            m, s = parts
            return int(m) * 60 + float(s)
        return float(parts[0])
    except ValueError:
        return None


def _read_progress_seconds(progress_path: Path) -> float | None:
    """Read latest out_time from an FFmpeg -progress file."""
    try:
        text = progress_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    seconds: float | None = None
    for line in text.splitlines():
        if line.startswith("out_time_ms="):
            raw = line.split("=", 1)[1].strip()
            if raw.isdigit():
                # FFmpeg names this *_ms but the value is microseconds
                seconds = int(raw) / 1_000_000.0
        elif line.startswith("out_time_us="):
            raw = line.split("=", 1)[1].strip()
            if raw.isdigit():
                seconds = int(raw) / 1_000_000.0
        elif line.startswith("out_time="):
            raw = line.split("=", 1)[1].strip()
            if raw and raw != "N/A":
                parsed = _parse_hhmmss(raw)
                if parsed is not None:
                    seconds = parsed
    return seconds


def _bitrate_kbps(bitrate: str | None) -> float | None:
    if not bitrate:
        return None
    raw = bitrate.strip().lower()
    try:
        if raw.endswith("k"):
            return float(raw[:-1])
        if raw.endswith("m"):
            return float(raw[:-1]) * 1000.0
        return float(raw) / 1000.0
    except ValueError:
        return None


def _estimate_output_bytes(options: ConvertOptions, duration_s: float | None) -> int | None:
    """Rough expected output size for size-based progress (audio extract is often too fast for time=)."""
    if duration_s is None or duration_s <= 0 or options.copy_audio:
        return None
    fmt = normalize_format(options.format)
    if fmt == "wav":
        rate = options.sample_rate or 44100
        ch = options.channels or 2
        return max(1, int(duration_s * rate * ch * 2))
    if fmt == "flac":
        rate = options.sample_rate or 44100
        ch = options.channels or 2
        return max(1, int(duration_s * rate * ch * 2 * 0.55))
    br = resolve_audio_bitrate(
        options.format,
        bitrate=options.bitrate,
        quality=options.quality,
    )
    kbps = _bitrate_kbps(br) or (192.0 if fmt == "mp3" else 160.0)
    return max(1, int(duration_s * kbps * 1000.0 / 8.0))


def _run_ffmpeg(
    cmd: list[str],
    duration_s: float | None,
    on_progress: ProgressCallback | None,
    *,
    output_path: Path | None = None,
    expected_bytes: int | None = None,
) -> tuple[int, str]:
    """
    Run FFmpeg with real progress via a progress file (Windows-safe).

    Pipe-based progress is buffered until exit on Windows; writing -progress to a
    temp file and polling it gives smooth updates. Output file size is a backup.
    """
    if on_progress is None:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=False,
            encoding="utf-8",
            errors="replace",
        )
        return proc.returncode, (proc.stderr or proc.stdout or "")

    fd, prog_name = tempfile.mkstemp(prefix="me_ff_", suffix=".prog")
    os.close(fd)
    progress_path = Path(prog_name)
    try:
        progress_path.write_text("", encoding="utf-8")
    except OSError:
        pass

    run_cmd = list(cmd)
    # Insert before output path (last argument)
    run_cmd[-1:-1] = ["-nostats", "-progress", str(progress_path)]

    # Remove existing target so size-based progress does not start at ~100%
    if output_path is not None and output_path.exists():
        try:
            output_path.unlink()
        except OSError:
            pass

    proc = subprocess.Popen(
        run_cmd,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1,
    )
    assert proc.stderr is not None

    stderr_chunks: list[str] = []
    duration_box: list[float | None] = [duration_s if duration_s and duration_s > 0 else None]
    dur_re = re.compile(r"Duration:\s*(\d{1,2}):(\d{2}):(\d{2}(?:\.\d+)?)")

    def _drain_stderr() -> None:
        assert proc.stderr is not None
        for line in proc.stderr:
            stderr_chunks.append(line)
            if duration_box[0] is None:
                dm = dur_re.search(line)
                if dm:
                    h, m, s = dm.groups()
                    duration_box[0] = int(h) * 3600 + int(m) * 60 + float(s)

    reader = threading.Thread(target=_drain_stderr, daemon=True)
    reader.start()

    last_emit = -1.0
    on_progress(0.0, "0%")
    stall = 0
    while True:
        done = proc.poll() is not None
        fracs: list[float] = [0.0]

        played = _read_progress_seconds(progress_path)
        total = duration_box[0]
        if played is not None and total and total > 0:
            fracs.append(min(0.99, max(0.0, played / total)))

        if output_path is not None and expected_bytes and expected_bytes > 0:
            try:
                size = output_path.stat().st_size if output_path.exists() else 0
            except OSError:
                size = 0
            fracs.append(min(0.99, size / float(expected_bytes)))

        frac = max(fracs)
        if frac - last_emit >= 0.005 or (done and frac > last_emit):
            last_emit = frac
            on_progress(frac, f"{int(frac * 100)}%")
            stall = 0
        else:
            stall += 1
            # Still heartbeat so UI does not look frozen while ffmpeg starts
            if stall == 1 and last_emit < 0.01:
                on_progress(0.0, "0%")

        if done:
            break
        time.sleep(0.12)

    reader.join(timeout=8)
    code = proc.wait()
    try:
        progress_path.unlink(missing_ok=True)
    except OSError:
        pass
    return code, "".join(stderr_chunks)


def convert_many(
    inputs: list[Path],
    *,
    options: ConvertOptions | None = None,
    on_item: Callable[[int, int, ConvertResult], None] | None = None,
) -> BatchReport:
    options = options or ConvertOptions()
    report = BatchReport()
    total = len(inputs)
    for index, path in enumerate(inputs, start=1):
        result = convert_file(path, options=options)
        report.results.append(result)
        if on_item:
            on_item(index, total, result)
    return report


def write_failure_log(report: BatchReport, log_path: Path) -> Path | None:
    failed = report.failed
    if not failed:
        return None
    log_path.parent.mkdir(parents=True, exist_ok=True)
    lines = ["# video-to-audio failure log", ""]
    for item in failed:
        lines.append(f"## {item.input_path}")
        lines.append(item.message)
        lines.append("")
    log_path.write_text("\n".join(lines), encoding="utf-8")
    return log_path
