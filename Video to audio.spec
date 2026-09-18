# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec — Video to audio x64（PyQt6 + 内置 FFmpeg）。"""

from pathlib import Path

from PyInstaller.utils.hooks import collect_submodules

project_root = Path(SPECPATH).resolve()
resources = project_root / "resources"
ffmpeg_dir = resources / "ffmpeg"

APP_NAME = "Video to audio"

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

translations = resources / "translations"
if translations.is_dir():
    datas.append((str(translations), "translations"))

hiddenimports = [
    "PyQt6",
    "PyQt6.QtCore",
    "PyQt6.QtGui",
    "PyQt6.QtWidgets",
    "PyQt6.QtMultimedia",
    "PyQt6.QtMultimediaWidgets",
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
    excludes=["tkinter", "customtkinter", "_tkinter", "PyQt5"],
    noarchive=False,
)

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
