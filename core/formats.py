"""Supported formats and default encode settings."""

from __future__ import annotations

from dataclasses import dataclass

VIDEO_EXTENSIONS: frozenset[str] = frozenset(
    {
        ".mp4",
        ".mkv",
        ".avi",
        ".mov",
        ".webm",
        ".flv",
        ".wmv",
        ".m4v",
        ".mpeg",
        ".mpg",
        ".ts",
        ".m2ts",
        ".3gp",
        ".ogv",
    }
)

AUDIO_EXTENSIONS: frozenset[str] = frozenset(
    {".mp3", ".wav", ".aac", ".m4a", ".flac", ".ogg", ".opus", ".wma"}
)

OUTPUT_FORMATS: tuple[str, ...] = ("mp3", "wav", "aac", "m4a", "flac")

# MP3 quality presets — aligned with legacy UVS-style low / mid / high
# 低: 22050 Hz + 32k | 中: 44100 Hz + 128k | 高: 编码器默认（不强制 -ar / -b:a）
MP3_QUALITY_LEVELS: tuple[str, ...] = ("high", "medium", "low")
MP3_QUALITY_BITRATES: dict[str, str | None] = {
    "high": None,
    "medium": "128k",
    "low": "32k",
}
MP3_QUALITY_SAMPLE_RATES: dict[str, int | None] = {
    "high": None,
    "medium": 44100,
    "low": 22050,
}
MP3_QUALITY_LABELS: dict[str, str] = {
    "high": "高品质 (默认)",
    "medium": "中品质 (128k / 44.1kHz)",
    "low": "低品质 (32k / 22.05kHz)",
}

MP3_QUALITY_ALIASES: dict[str, str] = {
    "high": "high",
    "h": "high",
    "hi": "high",
    "高": "high",
    "medium": "medium",
    "med": "medium",
    "mid": "medium",
    "m": "medium",
    "中": "medium",
    "low": "low",
    "l": "low",
    "lo": "low",
    "低": "low",
}

DEFAULT_BITRATES: dict[str, str] = {
    "mp3": "128k",
    "aac": "192k",
    "m4a": "192k",
}


def normalize_mp3_quality(quality: str | None) -> str | None:
    """Map quality label to high/medium/low, or None if empty."""
    if quality is None:
        return None
    key = quality.strip().lower()
    if not key:
        return None
    raw = quality.strip()
    if raw in MP3_QUALITY_ALIASES:
        return MP3_QUALITY_ALIASES[raw]
    if key in MP3_QUALITY_ALIASES:
        return MP3_QUALITY_ALIASES[key]
    raise ValueError(
        f"Unsupported MP3 quality '{quality}'. "
        f"Use: high/medium/low (or 高/中/低)."
    )


def describe_mp3_quality(quality: str | None) -> str:
    level = normalize_mp3_quality(quality)
    if level is None:
        return "默认"
    return MP3_QUALITY_LABELS.get(level, level)


def resolve_audio_bitrate(
    fmt: str,
    *,
    bitrate: str | None = None,
    quality: str | None = None,
) -> str | None:
    """
    Resolve bitrate for lossy formats.
    Explicit --bitrate wins; else MP3 --quality; else format default.
    High quality returns None (encoder default, no -b:a).
    """
    fmt_key = normalize_format(fmt)
    profile = PROFILES[fmt_key]
    if not profile.needs_bitrate:
        return None
    if bitrate:
        return bitrate
    if quality is not None:
        level = normalize_mp3_quality(quality)
        if level is None:
            return DEFAULT_BITRATES.get(fmt_key)
        if fmt_key != "mp3":
            raise ValueError("Quality presets (high/medium/low) only apply to MP3.")
        return MP3_QUALITY_BITRATES[level]
    return DEFAULT_BITRATES.get(fmt_key, "128k")


def resolve_audio_sample_rate(
    fmt: str,
    *,
    sample_rate: int | None = None,
    quality: str | None = None,
) -> int | None:
    """Explicit sample_rate wins; else MP3 quality preset; high → None (default)."""
    if sample_rate is not None:
        return sample_rate
    if quality is None:
        return None
    level = normalize_mp3_quality(quality)
    if level is None:
        return None
    if normalize_format(fmt) != "mp3":
        return None
    return MP3_QUALITY_SAMPLE_RATES[level]


@dataclass(frozen=True)
class EncodeProfile:
    """FFmpeg codec / container profile for one output format."""

    extension: str
    codec: str
    needs_bitrate: bool = True
    extra_args: tuple[str, ...] = ()


PROFILES: dict[str, EncodeProfile] = {
    "mp3": EncodeProfile(extension=".mp3", codec="libmp3lame"),
    "wav": EncodeProfile(
        extension=".wav",
        codec="pcm_s16le",
        needs_bitrate=False,
    ),
    "aac": EncodeProfile(extension=".aac", codec="aac"),
    "m4a": EncodeProfile(
        extension=".m4a",
        codec="aac",
        extra_args=("-f", "ipod"),
    ),
    "flac": EncodeProfile(
        extension=".flac",
        codec="flac",
        needs_bitrate=False,
    ),
}


def normalize_format(fmt: str) -> str:
    key = fmt.lower().lstrip(".")
    if key not in PROFILES:
        raise ValueError(
            f"Unsupported format '{fmt}'. Choose one of: {', '.join(OUTPUT_FORMATS)}"
        )
    return key


def is_video_file(path_suffix: str) -> bool:
    return path_suffix.lower() in VIDEO_EXTENSIONS


def is_audio_file(path_suffix: str) -> bool:
    return path_suffix.lower() in AUDIO_EXTENSIONS
