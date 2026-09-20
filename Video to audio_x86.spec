# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec — Video to audio x86（PyQt5 + 32-bit FFmpeg）。"""

from pathlib import Path

from PyInstaller.utils.hooks import collect_submodules

project_root = Path(SPECPATH).resolve()
resources = project_root / "resources"
ffmpeg_dir = resources / "ffmpeg_x86"

APP_NAME = "Video to audio_x86"

datas = []
binaries = []

for exe in ("ffmpeg.exe", "ffprobe.exe"):
    src = ffmpeg_dir / exe
    if src.is_file():
        binaries.append((str(src), "ffmpeg"))

styles = resources / "styles"
if styles.is_dir():
    datas.append((str(styles), "styles"))

icons = resources / "icons"
if icons.is_dir():
    datas.append((str(icons), "icons"))

icon_file = resources / "icon.ico"
if icon_file.is_file():
    datas.append((str(icon_file), "."))

hiddenimports = [
    "PyQt5",
    "PyQt5.QtCore",
    "PyQt5.QtGui",
    "PyQt5.QtWidgets",
    "PyQt5.QtMultimedia",
    "PyQt5.QtMultimediaWidgets",
    *collect_submodules("app"),
    *collect_submodules("core"),
    *collect_submodules("ui"),
    "typer",
    "rich",
]

a = Analysis(
    [str(project_root / "main.py")],
    pathex=[str(project_root)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["PyQt6", "tkinter", "customtkinter", "_tkinter"],
    noarchive=False,
)

# Do not ship this PC's Windows 10/11 UCRT. Those copies import
# api-ms-win-core-sysinfo-l1-2-0.dll, which Windows 7 does not have.
# The target OS provides its own Universal CRT (Win7: KB2999226).
def _win7_runtime(name: str) -> bool:
    base = Path(name).name.lower()
    return base == "ucrtbase.dll" or base.startswith("api-ms-win-")


a.binaries = TOC([item for item in a.binaries if not _win7_runtime(item[0])])

pyz = PYZ(a.pure)

exe_kwargs = dict(
    exclude_binaries=True,
    name=APP_NAME,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    version=str(project_root / "file_version_info.txt"),
)
if icon_file.is_file():
    exe_kwargs["icon"] = str(icon_file)

exe = EXE(pyz, a.scripts, [], **exe_kwargs)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name=APP_NAME,
)
