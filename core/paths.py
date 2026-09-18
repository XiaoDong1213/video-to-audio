"""统一资源与数据目录解析（与同目录其它项目一致）。"""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path


def project_root() -> Path:
    """源码包根目录（video-to-audio）。"""
    return Path(__file__).resolve().parents[1]


def resource_dir() -> Path:
    """只读资源：内置 FFmpeg、图标等。"""
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS)
    return project_root() / "resources"


def app_dir() -> Path:
    """程序目录：exe 旁或源码根。"""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return project_root()


def data_dir() -> Path:
    """可写目录：安装版走 APPDATA，源码跑走项目根。"""
    if getattr(sys, "frozen", False):
        if sys.platform == "win32":
            base = Path(os.environ.get("APPDATA", str(Path.home())))
        else:
            base = Path.home()
        path = base / "video_to_audio"
        path.mkdir(parents=True, exist_ok=True)
        return path
    return project_root()


def resource_path(*parts: str) -> Path:
    return resource_dir().joinpath(*parts)


def is_64bit_process() -> bool:
    return sys.maxsize > 2**32


def bundled_ffmpeg_dir() -> Path:
    """
    内置 FFmpeg 目录。
    - 64 位：resources/ffmpeg（打包后 _MEIPASS/ffmpeg）
    - 32 位：resources/ffmpeg_x86（打包后 _MEIPASS/ffmpeg）
    打包时两种架构都会把对应文件放到 _MEIPASS/ffmpeg，因此 frozen 时统一用 ffmpeg。
    """
    if getattr(sys, "frozen", False):
        return resource_dir() / "ffmpeg"
    if is_64bit_process():
        return resource_dir() / "ffmpeg"
    return resource_dir() / "ffmpeg_x86"


def resolve_binary(name: str) -> Path | None:
    """按优先级查找：内置 → exe 旁 → PATH。"""
    exe_name = f"{name}.exe" if sys.platform == "win32" else name
    candidates = [
        bundled_ffmpeg_dir() / exe_name,
        # 开发时：32 位进程也可回退到 64 位目录（仅本机调试，勿用于发布）
        resource_dir() / "ffmpeg" / exe_name,
        resource_dir() / "ffmpeg_x86" / exe_name,
        app_dir() / "ffmpeg" / exe_name,
        app_dir() / exe_name,
    ]
    seen: set[Path] = set()
    for path in candidates:
        try:
            resolved = path.resolve()
        except OSError:
            continue
        if resolved in seen:
            continue
        seen.add(resolved)
        if path.is_file() and path.stat().st_size > 0:
            return resolved

    found = shutil.which(name)
    if found:
        return Path(found).resolve()
    return None


def app_icon_path() -> Path:
    for path in (resource_dir() / "icon.ico", app_dir() / "icon.ico"):
        if path.is_file():
            return path
    return resource_dir() / "icon.ico"


def load_app_stylesheet() -> str:
    """Load QSS and inject absolute icon URLs (Qt needs real file paths)."""
    path = resource_path("styles", "app.qss")
    if not path.is_file():
        return ""
    text = path.read_text(encoding="utf-8")
    arrow = resource_path("icons", "arrow-down.svg")
    if arrow.is_file():
        text = text.replace("{{ARROW_DOWN}}", f'"{arrow.resolve().as_posix()}"')
    return text
