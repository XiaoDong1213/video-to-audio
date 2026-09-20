"""In-app media file picker with on-demand thumbnails (avoids native dialog hangs)."""

from __future__ import annotations

import hashlib
import os
import string
from pathlib import Path

from core.formats import AUDIO_EXTENSIONS, VIDEO_EXTENSIONS
from core.paths import data_dir
from core.utils import resolve_binary, run_hidden
from ui.qtcompat import (
    QT_API,
    AlignVCenter,
    DialogAccepted,
    ExtendedSelection,
    PointingHandCursor,
    QComboBox,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QThread,
    QTimer,
    QVBoxLayout,
    QWidget,
    pyqtSignal,
)

if QT_API == "pyqt6":
    from PyQt6.QtCore import QPoint, QSize, Qt
    from PyQt6.QtGui import QColor, QIcon, QPainter, QPixmap
else:  # pragma: no cover
    from PyQt5.QtCore import QPoint, QSize, Qt  # type: ignore
    from PyQt5.QtGui import QColor, QIcon, QPainter, QPixmap  # type: ignore

_THUMB_W = 96
_THUMB_H = 54
_ROW_H = 64
_PLACEHOLDER: QIcon | None = None
_FOLDER_ICON: QIcon | None = None

# Newest first by default.
SORT_MTIME_DESC = "mtime_desc"
SORT_MTIME_ASC = "mtime_asc"
SORT_NAME_ASC = "name_asc"
SORT_NAME_DESC = "name_desc"
SORT_SIZE_DESC = "size_desc"
SORT_SIZE_ASC = "size_asc"

_SORT_CHOICES: list[tuple[str, str]] = [
    ("修改时间（新→旧）", SORT_MTIME_DESC),
    ("修改时间（旧→新）", SORT_MTIME_ASC),
    ("名称（A→Z）", SORT_NAME_ASC),
    ("名称（Z→A）", SORT_NAME_DESC),
    ("大小（大→小）", SORT_SIZE_DESC),
    ("大小（小→大）", SORT_SIZE_ASC),
]


class _Entry:
    __slots__ = ("path", "name", "mtime", "size")

    def __init__(self, path: Path, name: str, mtime: float, size: int) -> None:
        self.path = path
        self.name = name
        self.mtime = mtime
        self.size = size


def _roles() -> tuple[int, int, int]:
    base = int(Qt.ItemDataRole.UserRole) if hasattr(Qt, "ItemDataRole") else int(Qt.UserRole)
    return base, base + 1, base + 2  # path, thumb_loaded, kind


def _placeholder_icon() -> QIcon:
    global _PLACEHOLDER
    if _PLACEHOLDER is None:
        pix = QPixmap(_THUMB_W, _THUMB_H)
        gray = Qt.GlobalColor.lightGray if hasattr(Qt, "GlobalColor") else Qt.lightGray
        pix.fill(gray)
        _PLACEHOLDER = QIcon(pix)
    return _PLACEHOLDER


def _folder_icon() -> QIcon:
    global _FOLDER_ICON
    if _FOLDER_ICON is None:
        pix = QPixmap(_THUMB_W, _THUMB_H)
        pix.fill(QColor("#F8FAFC"))
        painter = QPainter(pix)
        painter.setRenderHint(
            QPainter.RenderHint.Antialiasing
            if hasattr(QPainter, "RenderHint")
            else QPainter.Antialiasing
        )
        painter.setBrush(QColor("#38BDF8"))
        painter.setPen(QColor("#0284C7"))
        painter.drawRoundedRect(18, 18, 60, 28, 4, 4)
        painter.drawRoundedRect(22, 12, 28, 10, 3, 3)
        painter.end()
        _FOLDER_ICON = QIcon(pix)
    return _FOLDER_ICON


def _thumb_cache_dir() -> Path:
    path = data_dir() / "thumb_cache"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _cache_key(path: Path) -> str:
    try:
        mtime = path.stat().st_mtime_ns
    except OSError:
        mtime = 0
    raw = f"{path.resolve()}|{mtime}".encode("utf-8", errors="replace")
    return hashlib.sha1(raw).hexdigest()


def _sort_entries(entries: list[_Entry], mode: str) -> None:
    if mode == SORT_MTIME_ASC:
        entries.sort(key=lambda e: (e.mtime, e.name.lower()))
    elif mode == SORT_NAME_ASC:
        entries.sort(key=lambda e: e.name.lower())
    elif mode == SORT_NAME_DESC:
        entries.sort(key=lambda e: e.name.lower(), reverse=True)
    elif mode == SORT_SIZE_DESC:
        entries.sort(key=lambda e: (e.size, e.name.lower()), reverse=True)
    elif mode == SORT_SIZE_ASC:
        entries.sort(key=lambda e: (e.size, e.name.lower()))
    else:
        # SORT_MTIME_DESC — newest first
        entries.sort(key=lambda e: (e.mtime, e.name.lower()), reverse=True)


def _list_dir_and_media(
    folder: Path,
    extensions: frozenset[str],
    *,
    sort_mode: str = SORT_MTIME_DESC,
) -> tuple[list[_Entry], list[_Entry]]:
    """Return (subdirs, media files). Fast scandir, no thumbnails."""
    dirs: list[_Entry] = []
    files: list[_Entry] = []
    try:
        with os.scandir(folder) as it:
            for entry in it:
                name = entry.name
                if name.startswith("."):
                    continue
                try:
                    is_dir = entry.is_dir(follow_symlinks=False)
                    is_file = entry.is_file(follow_symlinks=False)
                except OSError:
                    continue
                try:
                    st = entry.stat(follow_symlinks=False)
                    mtime = float(st.st_mtime)
                    size = int(st.st_size) if is_file else 0
                except OSError:
                    mtime = 0.0
                    size = 0
                path = Path(entry.path)
                item = _Entry(path, name, mtime, size)
                if is_dir:
                    dirs.append(item)
                elif is_file and path.suffix.lower() in extensions:
                    files.append(item)
    except OSError:
        return [], []
    # Folders: name A→Z so browsing stays predictable; files follow chosen sort.
    dirs.sort(key=lambda e: e.name.lower())
    _sort_entries(files, sort_mode)
    return dirs, files


def _windows_drives() -> list[Path]:
    drives: list[Path] = []
    for letter in string.ascii_uppercase:
        root = Path(f"{letter}:\\")
        if root.exists():
            drives.append(root)
    return drives


def _non_native_dir_options():
    """Return Options enum (not int) — PyQt rejects bare int for getExistingDirectory."""
    if QT_API == "pyqt6":
        return QFileDialog.Option.DontUseNativeDialog | QFileDialog.Option.ShowDirsOnly
    # PyQt5: DontUseNativeDialog is on QFileDialog; ShowDirsOnly is the default flag.
    return QFileDialog.DontUseNativeDialog | QFileDialog.ShowDirsOnly  # type: ignore[attr-defined]


class _ThumbWorker(QThread):
    ready = pyqtSignal(str, str)  # path, jpeg_path
    failed = pyqtSignal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._pending: list[Path] = []
        self._cancel = False
        self._ffmpeg = resolve_binary("ffmpeg")

    def enqueue(self, paths: list[Path]) -> None:
        for path in paths:
            if path not in self._pending:
                self._pending.append(path)
        if not self.isRunning():
            self.start()

    def clear_queue(self) -> None:
        self._pending.clear()

    def stop(self) -> None:
        self._cancel = True
        self._pending.clear()
        self.wait(2000)

    def run(self) -> None:
        while not self._cancel:
            if not self._pending:
                break
            path = self._pending.pop(0)
            out = self._make_thumb(path)
            if out is not None:
                self.ready.emit(str(path), str(out))
            else:
                self.failed.emit(str(path))

    def _make_thumb(self, path: Path) -> Path | None:
        if not path.is_file():
            return None
        cache = _thumb_cache_dir() / f"{_cache_key(path)}.jpg"
        if cache.is_file() and cache.stat().st_size > 0:
            return cache
        if self._ffmpeg is None:
            return None
        for seek in ("0.5", None):
            cmd = [
                str(self._ffmpeg),
                "-hide_banner",
                "-loglevel",
                "error",
            ]
            if seek is not None:
                cmd.extend(["-ss", seek])
            cmd.extend(
                [
                    "-i",
                    str(path),
                    "-frames:v",
                    "1",
                    "-vf",
                    f"scale={_THUMB_W}:-2",
                    "-y",
                    str(cache),
                ]
            )
            proc = run_hidden(cmd)
            if proc.returncode == 0 and cache.is_file() and cache.stat().st_size > 0:
                return cache
            try:
                if cache.is_file():
                    cache.unlink()
            except OSError:
                pass
        return None


class MediaFilePicker(QDialog):
    """Browse folders + list media; thumbnails only for visible video rows."""

    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        start_dir: str = "",
        kind: str = "video",
        title: str = "选择文件",
    ) -> None:
        super().__init__(parent)
        self.setObjectName("mediaFilePicker")
        self.setWindowTitle(title)
        self.resize(820, 580)
        self.setMinimumSize(560, 400)

        self._kind = kind
        self._exts = VIDEO_EXTENSIONS if kind == "video" else AUDIO_EXTENSIONS
        self._sort_mode = SORT_MTIME_DESC
        # None = Windows drive list ("此电脑")
        self._folder: Path | None = (
            Path(start_dir) if start_dir and Path(start_dir).is_dir() else Path.home()
        )
        self._items: dict[str, QListWidgetItem] = {}
        self._role_path, self._role_loaded, self._role_kind = _roles()
        self._worker = _ThumbWorker(self)
        self._worker.ready.connect(self._on_thumb_ready)
        self._scroll_timer = QTimer(self)
        self._scroll_timer.setSingleShot(True)
        self._scroll_timer.setInterval(90)
        self._scroll_timer.timeout.connect(self._request_visible_thumbs)

        root = QVBoxLayout(self)
        root.setContentsMargins(14, 14, 14, 14)
        root.setSpacing(10)

        nav = QHBoxLayout()
        nav.setSpacing(8)
        self.btn_up = QPushButton("上级")
        self.btn_browse = QPushButton("浏览…")
        self.btn_refresh = QPushButton("刷新")
        for btn, slot in (
            (self.btn_up, self._go_up),
            (self.btn_browse, self._browse_folder),
            (self.btn_refresh, self._reload),
        ):
            btn.setObjectName("pickerNavBtn")
            btn.setCursor(PointingHandCursor)
            btn.setFixedHeight(34)
            btn.clicked.connect(slot)

        self.path_edit = QLineEdit(str(self._folder) if self._folder else "此电脑")
        self.path_edit.setMinimumHeight(34)
        self.path_edit.setPlaceholderText("文件夹路径，回车打开")
        self.path_edit.returnPressed.connect(self._go_path)
        nav.addWidget(self.btn_up)
        nav.addWidget(self.path_edit, 1)
        nav.addWidget(self.btn_browse)
        nav.addWidget(self.btn_refresh)
        root.addLayout(nav)

        tools = QHBoxLayout()
        tools.setSpacing(8)
        sort_label = QLabel("排序")
        sort_label.setObjectName("mutedText")
        self.sort_combo = QComboBox()
        self.sort_combo.setObjectName("pickerSortCombo")
        self.sort_combo.setMinimumWidth(180)
        self.sort_combo.setFixedHeight(34)
        for label, mode in _SORT_CHOICES:
            self.sort_combo.addItem(label, mode)
        self.sort_combo.setCurrentIndex(0)  # 修改时间（新→旧）
        self.sort_combo.currentIndexChanged.connect(self._on_sort_changed)
        hint = QLabel(
            "双击文件夹进入，双击文件添加。缩略图只对当前可见视频按需生成。"
        )
        hint.setObjectName("mutedText")
        hint.setWordWrap(True)
        tools.addWidget(sort_label, 0, AlignVCenter)
        tools.addWidget(self.sort_combo, 0)
        tools.addWidget(hint, 1, AlignVCenter)
        root.addLayout(tools)

        self.list = QListWidget()
        self.list.setObjectName("mediaPickerList")
        self.list.setSelectionMode(ExtendedSelection)
        self.list.setIconSize(QSize(_THUMB_W, _THUMB_H))
        self.list.setSpacing(2)
        self.list.setUniformItemSizes(True)
        self.list.itemDoubleClicked.connect(self._on_double_click)
        self.list.verticalScrollBar().valueChanged.connect(self._on_scroll)
        root.addWidget(self.list, 1)

        foot = QHBoxLayout()
        self.count_label = QLabel("")
        self.count_label.setObjectName("mutedText")
        foot.addWidget(self.count_label, 0, AlignVCenter)
        foot.addStretch(1)

        self.cancel_btn = QPushButton("取消")
        self.ok_btn = QPushButton("添加所选")
        for btn in (self.cancel_btn, self.ok_btn):
            btn.setObjectName("pickerActionBtn")
            btn.setCursor(PointingHandCursor)
            btn.setFixedHeight(36)
            btn.setMinimumWidth(110)
        self.ok_btn.setObjectName("pickerActionBtnPrimary")
        self.cancel_btn.clicked.connect(self.reject)
        self.ok_btn.clicked.connect(self.accept)
        foot.addWidget(self.cancel_btn)
        foot.addWidget(self.ok_btn)
        root.addLayout(foot)

        self._reload()

    def selected_paths(self) -> list[Path]:
        paths: list[Path] = []
        for item in self.list.selectedItems():
            if item.data(self._role_kind) != "file":
                continue
            data = item.data(self._role_path)
            if data:
                paths.append(Path(str(data)))
        return paths

    def current_folder(self) -> Path:
        return self._folder if self._folder is not None else Path.home()

    def closeEvent(self, event) -> None:  # noqa: N802, ANN001
        self._worker.stop()
        super().closeEvent(event)

    def _browse_folder(self) -> None:
        start = str(self._folder) if self._folder is not None else ""
        folder = QFileDialog.getExistingDirectory(
            self,
            "选择文件夹",
            start,
            _non_native_dir_options(),
        )
        if folder:
            self._folder = Path(folder)
            self._reload()

    def _go_up(self) -> None:
        if self._folder is None:
            return
        parent = self._folder.parent
        if parent != self._folder:
            self._folder = parent
            self._reload()
            return
        # Already at drive root: show all drives on Windows.
        if os.name == "nt":
            self._folder = None
            self._reload()

    def _go_path(self) -> None:
        text = self.path_edit.text().strip().strip('"')
        if not text or text == "此电脑":
            if os.name == "nt":
                self._folder = None
                self._reload()
            return
        path = Path(text)
        if path.is_file():
            path = path.parent
        if path.is_dir():
            self._folder = path
            self._reload()
        else:
            self.count_label.setText("路径不存在")

    def _on_sort_changed(self, _index: int = 0) -> None:
        data = self.sort_combo.currentData()
        mode = str(data) if data else SORT_MTIME_DESC
        if mode == self._sort_mode:
            return
        self._sort_mode = mode
        self._reload()

    def _reload(self) -> None:
        self._worker.clear_queue()
        self.list.clear()
        self._items.clear()

        if self._folder is None:
            self.path_edit.setText("此电脑")
            drives = _windows_drives() if os.name == "nt" else [Path.home()]
            for drive in drives:
                self._add_dir_item(drive, label=str(drive))
            self.count_label.setText(f"{len(drives)} 个磁盘")
            return

        self.path_edit.setText(str(self._folder))
        dirs, files = _list_dir_and_media(
            self._folder, self._exts, sort_mode=self._sort_mode
        )
        for entry in dirs:
            self._add_dir_item(entry.path, label=entry.name or str(entry.path))
        for entry in files:
            self._add_file_item(entry.path)
        self.count_label.setText(
            f"{len(dirs)} 个文件夹 · {len(files)} 个文件 · {self._folder}"
        )
        QTimer.singleShot(0, self._request_visible_thumbs)

    def _add_dir_item(self, path: Path, *, label: str | None = None) -> None:
        item = QListWidgetItem(_folder_icon(), label or path.name or str(path))
        item.setData(self._role_path, str(path))
        item.setData(self._role_kind, "dir")
        item.setToolTip(str(path))
        item.setSizeHint(QSize(0, _ROW_H))
        self.list.addItem(item)

    def _add_file_item(self, path: Path) -> None:
        item = QListWidgetItem(_placeholder_icon(), path.name)
        item.setData(self._role_path, str(path))
        item.setData(self._role_kind, "file")
        item.setToolTip(str(path))
        item.setSizeHint(QSize(0, _ROW_H))
        self.list.addItem(item)
        self._items[str(path)] = item

    def _on_scroll(self, _value: int = 0) -> None:
        self._scroll_timer.start()

    def _on_double_click(self, item: QListWidgetItem) -> None:
        kind = item.data(self._role_kind)
        raw = item.data(self._role_path)
        if not raw:
            return
        path = Path(str(raw))
        if kind == "dir":
            self._folder = path
            self._reload()
            return
        self.list.clearSelection()
        item.setSelected(True)
        self.accept()

    def _visible_file_paths(self) -> list[Path]:
        viewport = self.list.viewport()
        top = self.list.indexAt(QPoint(4, 4)).row()
        bottom = self.list.indexAt(QPoint(4, max(4, viewport.height() - 4))).row()
        if top < 0:
            top = 0
        if bottom < 0:
            bottom = min(self.list.count() - 1, top + 12)
        bottom = max(bottom, top)
        bottom = min(self.list.count() - 1, bottom + 3)
        paths: list[Path] = []
        for row in range(top, bottom + 1):
            item = self.list.item(row)
            if item is None or item.data(self._role_kind) != "file":
                continue
            raw = item.data(self._role_path)
            if raw:
                paths.append(Path(str(raw)))
        return paths

    def _request_visible_thumbs(self) -> None:
        if self._kind != "video":
            return
        need: list[Path] = []
        for path in self._visible_file_paths():
            item = self._items.get(str(path))
            if item is None or item.data(self._role_loaded):
                continue
            cache = _thumb_cache_dir() / f"{_cache_key(path)}.jpg"
            if cache.is_file() and cache.stat().st_size > 0:
                self._apply_thumb(str(path), str(cache))
                continue
            need.append(path)
        if need:
            self._worker.enqueue(need)

    def _on_thumb_ready(self, path_str: str, jpeg_path: str) -> None:
        self._apply_thumb(path_str, jpeg_path)

    def _apply_thumb(self, path_str: str, jpeg_path: str) -> None:
        item = self._items.get(path_str)
        if item is None:
            return
        pix = QPixmap(jpeg_path)
        if pix.isNull():
            return
        item.setIcon(QIcon(pix))
        item.setData(self._role_loaded, True)


def pick_media_files(
    parent: QWidget | None,
    *,
    start_dir: str = "",
    kind: str = "video",
) -> tuple[list[Path], str]:
    """Return (selected files, folder used). Empty list if cancelled."""
    title = "选择视频文件" if kind == "video" else "选择音频文件"
    dialog = MediaFilePicker(parent, start_dir=start_dir, kind=kind, title=title)
    code = dialog.exec() if hasattr(dialog, "exec") else dialog.exec_()  # type: ignore[attr-defined]
    folder = str(dialog.current_folder())
    if int(code) != int(DialogAccepted):
        return [], folder
    return dialog.selected_paths(), folder
