"""应用配置：路径记忆等（写入 data_dir/config.json）。"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, fields
from pathlib import Path

from core.paths import data_dir

DEFAULT_CONFIG_NAME = "config.json"


@dataclass
class AppConfig:
    last_video_dir: str = ""
    last_audio_dir: str = ""
    last_output_dir: str = ""
    last_format: str = "mp3"
    last_quality: str = "medium"  # high / medium / low
    window_geometry: str = ""  # base64 from QByteArray or hex
    overwrite: bool = False

    @classmethod
    def default(cls) -> AppConfig:
        return cls()

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> AppConfig:
        known = {f.name for f in fields(cls)}
        kwargs = {k: v for k, v in data.items() if k in known}
        return cls(**kwargs)


@dataclass
class ConfigLoadResult:
    config: AppConfig
    warning: str = ""


def default_config_path() -> Path:
    return data_dir() / DEFAULT_CONFIG_NAME


def load_config(path: Path | None = None) -> ConfigLoadResult:
    cfg_path = path or default_config_path()
    if not cfg_path.is_file():
        return ConfigLoadResult(AppConfig.default())
    try:
        raw = json.loads(cfg_path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            return ConfigLoadResult(AppConfig.default(), "配置格式无效，已使用默认值。")
        return ConfigLoadResult(AppConfig.from_dict(raw))
    except (OSError, json.JSONDecodeError, TypeError, ValueError) as exc:
        return ConfigLoadResult(AppConfig.default(), f"配置读取失败，已使用默认值：{exc}")


def save_config(config: AppConfig, path: Path | None = None) -> None:
    cfg_path = path or default_config_path()
    cfg_path.parent.mkdir(parents=True, exist_ok=True)
    cfg_path.write_text(
        json.dumps(config.to_dict(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def existing_dir(path_str: str) -> str:
    """Return path if it exists as a directory, else empty string."""
    if not path_str:
        return ""
    p = Path(path_str)
    return str(p) if p.is_dir() else ""
