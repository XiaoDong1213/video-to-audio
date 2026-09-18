"""Unit tests (no real media file required)."""

from __future__ import annotations

from pathlib import Path

import pytest

from core.converter import (
    ConvertOptions,
    MergeOptions,
    _estimate_output_bytes,
    _parse_hhmmss,
    _read_progress_seconds,
    build_ffmpeg_command,
    build_merge_command,
)
from core.formats import (
    normalize_format,
    normalize_mp3_quality,
    resolve_audio_bitrate,
    resolve_audio_sample_rate,
)
from core.paths import bundled_ffmpeg_dir, resolve_binary
from core.utils import unique_output_path


def test_normalize_format() -> None:
    assert normalize_format("MP3") == "mp3"
    assert normalize_format(".flac") == "flac"
    with pytest.raises(ValueError):
        normalize_format("wma")


def test_mp3_quality_presets() -> None:
    assert normalize_mp3_quality("高") == "high"
    assert normalize_mp3_quality("中") == "medium"
    assert normalize_mp3_quality("低") == "low"
    assert normalize_mp3_quality("HIGH") == "high"
    # UVS-style: 高=默认, 中=128k/44100, 低=32k/22050
    assert resolve_audio_bitrate("mp3", quality="high") is None
    assert resolve_audio_bitrate("mp3", quality="medium") == "128k"
    assert resolve_audio_bitrate("mp3", quality="low") == "32k"
    assert resolve_audio_sample_rate("mp3", quality="high") is None
    assert resolve_audio_sample_rate("mp3", quality="medium") == 44100
    assert resolve_audio_sample_rate("mp3", quality="low") == 22050
    assert resolve_audio_bitrate("mp3", bitrate="256k", quality="low") == "256k"
    with pytest.raises(ValueError):
        resolve_audio_bitrate("aac", quality="high")


def test_unique_output_path(tmp_path: Path) -> None:
    target = tmp_path / "song.mp3"
    target.write_text("x", encoding="utf-8")
    assert unique_output_path(target).name == "song_1.mp3"
    (tmp_path / "song_1.mp3").write_text("x", encoding="utf-8")
    assert unique_output_path(target).name == "song_2.mp3"


def test_build_ffmpeg_command_mp3_high_default() -> None:
    opts = ConvertOptions(format="mp3", quality="high")
    cmd = build_ffmpeg_command("ffmpeg", Path("in.mp4"), Path("out.mp3"), opts)
    assert "libmp3lame" in cmd
    assert "-b:a" not in cmd
    assert "-ar" not in cmd


def test_build_ffmpeg_command_mp3_medium() -> None:
    opts = ConvertOptions(format="mp3", quality="medium")
    cmd = build_ffmpeg_command("ffmpeg", Path("in.mp4"), Path("out.mp3"), opts)
    assert "128k" in cmd
    assert "44100" in cmd


def test_build_ffmpeg_command_mp3_low() -> None:
    opts = ConvertOptions(format="mp3", quality="low")
    cmd = build_ffmpeg_command("ffmpeg", Path("in.mp4"), Path("out.mp3"), opts)
    assert "32k" in cmd
    assert "22050" in cmd


def test_build_ffmpeg_command_explicit_rate_wins() -> None:
    opts = ConvertOptions(format="mp3", quality="low", sample_rate=48000, channels=2)
    cmd = build_ffmpeg_command("ffmpeg", Path("in.mp4"), Path("out.mp3"), opts)
    assert "48000" in cmd
    assert "22050" not in cmd


def test_build_ffmpeg_command_copy_and_stream() -> None:
    opts = ConvertOptions(
        format="m4a",
        copy_audio=True,
        audio_stream=1,
        start="0:00:10",
        end="0:01:00",
        quality=None,
    )
    cmd = build_ffmpeg_command("ffmpeg", Path("in.mkv"), Path("out.m4a"), opts)
    assert "-ss" in cmd and "0:00:10" in cmd
    assert cmd.index("-i") < cmd.index("-ss")
    assert "-to" in cmd and "0:01:00" in cmd
    assert "-map" in cmd and "0:a:1" in cmd
    assert "copy" in cmd


def test_reject_end_and_duration() -> None:
    opts = ConvertOptions(format="wav", end="30", duration="10", quality=None)
    with pytest.raises(ValueError):
        build_ffmpeg_command("ffmpeg", Path("a.mp4"), Path("a.wav"), opts)


def test_build_merge_command() -> None:
    opts = MergeOptions(format="mp3", quality="low")
    cmd = build_merge_command(
        "ffmpeg",
        [Path("a.mp3"), Path("b.wav"), Path("c.m4a")],
        Path("out.mp3"),
        opts,
    )
    assert cmd.count("-i") == 3
    assert "concat=n=3:v=0:a=1[outa]" in " ".join(cmd)
    assert "32k" in cmd
    assert "22050" in cmd
    with pytest.raises(ValueError):
        build_merge_command("ffmpeg", [Path("a.mp3")], Path("o.mp3"), opts)


def test_progress_file_parsing(tmp_path: Path) -> None:
    assert _parse_hhmmss("01:05.500") == pytest.approx(65.5)
    assert _parse_hhmmss("1.500") == pytest.approx(1.5)
    prog = tmp_path / "p.ffprog"
    prog.write_text(
        "out_time_ms=12500000\nprogress=continue\n",
        encoding="utf-8",
    )
    assert _read_progress_seconds(prog) == pytest.approx(12.5)


def test_estimate_output_bytes() -> None:
    low = ConvertOptions(format="mp3", quality="low")
    mid = ConvertOptions(format="mp3", quality="medium")
    assert _estimate_output_bytes(low, 10.0) == 40000
    assert _estimate_output_bytes(mid, 10.0) == 160000


def test_read_progress_seconds(tmp_path: Path) -> None:
    from core.converter import _read_progress_seconds

    p = tmp_path / "p.prog"
    p.write_text("out_time_ms=6500000\nprogress=continue\n", encoding="utf-8")
    assert _read_progress_seconds(p) == pytest.approx(6.5)


def test_bundled_ffmpeg_preferred() -> None:
    bundled = bundled_ffmpeg_dir() / "ffmpeg.exe"
    if not bundled.is_file():
        pytest.skip("bundled ffmpeg not present")
    resolved = resolve_binary("ffmpeg")
    assert resolved is not None
    assert resolved.resolve() == bundled.resolve()
