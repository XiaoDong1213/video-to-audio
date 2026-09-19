"""Config persistence tests."""

from __future__ import annotations

from pathlib import Path

from core.config import AppConfig, existing_dir, load_config, save_config


def test_save_load_roundtrip(tmp_path: Path) -> None:
    path = tmp_path / "config.json"
    cfg = AppConfig(
        last_video_dir=str(tmp_path / "videos"),
        last_audio_dir=str(tmp_path / "audio"),
        last_output_dir=str(tmp_path / "out"),
        last_format="wav",
        last_quality="high",
        overwrite=True,
        auto_open_output=True,
    )
    (tmp_path / "videos").mkdir()
    save_config(cfg, path)
    loaded = load_config(path)
    assert loaded.warning == ""
    assert loaded.config.last_format == "wav"
    assert loaded.config.last_quality == "high"
    assert loaded.config.overwrite is True
    assert loaded.config.auto_open_output is True
    assert existing_dir(loaded.config.last_video_dir) == str(tmp_path / "videos")
    assert existing_dir(loaded.config.last_audio_dir) == ""


def test_corrupt_config(tmp_path: Path) -> None:
    path = tmp_path / "config.json"
    path.write_text("{not json", encoding="utf-8")
    loaded = load_config(path)
    assert loaded.warning
    assert loaded.config.last_format == "mp3"
