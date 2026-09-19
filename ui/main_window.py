"""Video to audio — 主窗口（PyQt6 / PyQt5 via qtcompat）。"""

from __future__ import annotations

import os
import subprocess
import sys
from dataclasses import replace
from pathlib import Path

from app.identity import APP_NAME
from core.config import existing_dir, load_config, save_config
from core.converter import (
    ConvertOptions,
    ConvertResult,
    MergeOptions,
    convert_file,
    merge_files,
    write_failure_log,
)
from core.formats import MP3_QUALITY_LABELS, OUTPUT_FORMATS, describe_mp3_quality
from core.paths import bundled_ffmpeg_dir, data_dir, load_app_icon
from core.utils import (
    FFmpegNotFoundError,
    collect_audio_files,
    collect_video_files,
    ensure_ffmpeg,
    move_selected,
    parse_optional_positive_int,
)
from ui.toast import show_corner_toast
from ui.qtcompat import (
    AlignCenter,
    AlignVCenter,
    ExtendedSelection,
    PointingHandCursor,
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QThread,
    QVBoxLayout,
    QWidget,
    ScrollBarAlwaysOff,
    ScrollBarAsNeeded,
    TopToBottom,
    geometry_from_hex,
    geometry_to_hex,
    pyqtSignal,
)
from ui.combo import tune_combo
from ui.trim_panel import TrimWorkspace

MODE_CONVERT = "convert"
MODE_MERGE = "merge"

QUALITY_CHOICES = [
    (MP3_QUALITY_LABELS["high"], "high"),
    (MP3_QUALITY_LABELS["medium"], "medium"),
    (MP3_QUALITY_LABELS["low"], "low"),
]

VIDEO_FILTER = "视频文件 (*.mp4 *.mkv *.avi *.mov *.webm *.flv *.wmv *.m4v *.mpeg *.mpg *.ts *.m2ts *.3gp *.ogv);;所有文件 (*.*)"
AUDIO_FILTER = "音频文件 (*.mp3 *.wav *.aac *.m4a *.flac *.ogg *.opus *.wma);;所有文件 (*.*)"


class ConvertWorker(QThread):
    progress = pyqtSignal(float, str)
    log_line = pyqtSignal(str)
    finished_report = pyqtSignal(object)
    failed = pyqtSignal(str)

    def __init__(self, jobs: list[tuple[Path, ConvertOptions]]) -> None:
        super().__init__()
        self._jobs = jobs

    def run(self) -> None:
        try:
            from core.converter import BatchReport

            report = BatchReport()
            total = len(self._jobs)
            for index, (path, options) in enumerate(self._jobs, start=1):
                base = (index - 1) / total

                def _cb(frac: float, msg: str, *, _i=index, _base=base, _name=path.name) -> None:
                    overall = min(1.0, _base + max(0.0, frac) / total)
                    pct = int(max(0.0, min(1.0, frac)) * 100)
                    self.progress.emit(
                        overall,
                        f"进度 {_i}/{total} · {pct}% — {_name}",
                    )

                result = convert_file(path, options=options, on_progress=_cb)
                report.results.append(result)
                self.progress.emit(
                    index / total,
                    f"进度 {index}/{total} · 100% — {result.input_path.name}",
                )
                mark = "成功" if result.ok else "失败"
                out = result.output_path or "-"
                self.log_line.emit(f"[{mark}] {result.input_path.name} → {out}")
                if not result.ok and result.message:
                    self.log_line.emit("  " + result.message.splitlines()[-1])
            log_path = write_failure_log(report, data_dir() / "video-to-audio-failures.log")
            self.finished_report.emit((report, log_path))
        except Exception as exc:  # noqa: BLE001
            self.failed.emit(str(exc))


class MergeWorker(QThread):
    progress = pyqtSignal(float, str)
    log_line = pyqtSignal(str)
    finished_result = pyqtSignal(object)
    failed = pyqtSignal(str)

    def __init__(self, paths: list[Path], options: MergeOptions) -> None:
        super().__init__()
        self._paths = paths
        self._options = options

    def run(self) -> None:
        try:
            self.progress.emit(0.1, "正在合并…")
            result = merge_files(self._paths, options=self._options)
            self.finished_result.emit(result)
        except Exception as exc:  # noqa: BLE001
            self.failed.emit(str(exc))


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(APP_NAME)
        qicon = load_app_icon()
        if not qicon.isNull():
            self.setWindowIcon(qicon)
        self.resize(1280, 920)
        self.setMinimumSize(1100, 820)

        loaded = load_config()
        self.config = loaded.config
        self._paths: list[Path] = []
        self._trims: dict[Path, tuple[str | None, str | None]] = {}
        self._mode = MODE_CONVERT
        self._worker: QThread | None = None
        self._loading_preview = False

        self._build_ui()
        self._restore_from_config()
        self._refresh_ffmpeg_status()
        self._sync_quality_enabled()
        self._apply_mode_ui()

        if loaded.warning:
            QMessageBox.warning(self, "配置提示", loaded.warning)

    def closeEvent(self, event) -> None:  # noqa: N802, ANN001
        if self._worker is not None and self._worker.isRunning():
            QMessageBox.information(self, "请稍候", "任务还在进行，完成后再关闭窗口。")
            event.ignore()
            return
        self._persist_config()
        if hasattr(self, "trim_workspace"):
            self.trim_workspace.clear()
        super().closeEvent(event)

    def _persist_config(self) -> None:
        self.config.last_format = self.format_combo.currentText()
        self.config.last_quality = self._quality_key()
        self.config.last_output_dir = self.outdir_edit.text().strip()
        self.config.overwrite = self.overwrite_check.isChecked()
        self.config.auto_open_output = self.auto_open_check.isChecked()
        try:
            self.config.window_geometry = geometry_to_hex(self)
        except Exception:  # noqa: BLE001
            pass
        try:
            save_config(self.config)
        except OSError:
            pass

    def _restore_from_config(self) -> None:
        fmt = self.config.last_format
        if fmt in OUTPUT_FORMATS:
            self.format_combo.setCurrentText(fmt)
        q = self.config.last_quality or "medium"
        for i in range(self.quality_combo.count()):
            if self.quality_combo.itemData(i) == q:
                self.quality_combo.setCurrentIndex(i)
                break
        if self.config.last_output_dir:
            self.outdir_edit.setText(self.config.last_output_dir)
        self.overwrite_check.setChecked(bool(self.config.overwrite))
        self.auto_open_check.setChecked(bool(self.config.auto_open_output))
        if self.config.window_geometry:
            try:
                geometry_from_hex(self, self.config.window_geometry)
            except Exception:  # noqa: BLE001
                pass
        # 旧配置可能记住过小窗口，强制保证控件区能放下
        if self.width() < 1280 or self.height() < 900:
            self.resize(1280, 920)

    def _build_ui(self) -> None:
        central = QWidget()
        central.setObjectName("centralRoot")
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addWidget(self._build_header())

        body = QWidget()
        body_lay = QHBoxLayout(body)
        body_lay.setContentsMargins(16, 12, 16, 12)
        body_lay.setSpacing(12)
        body_lay.addWidget(self._build_file_panel(), 3)
        body_lay.addWidget(self._build_option_panel(), 2)
        root.addWidget(body, 1)
        root.addWidget(self._build_footer())

    def _build_header(self) -> QFrame:
        header = QFrame()
        header.setObjectName("appHeader")
        lay = QHBoxLayout(header)
        lay.setContentsMargins(20, 10, 20, 10)
        lay.setSpacing(10)

        brand = QVBoxLayout()
        brand.setSpacing(2)
        title = QLabel(APP_NAME)
        title.setObjectName("appTitle")
        brand.addWidget(title)
        lay.addLayout(brand, 1)

        self.ffmpeg_badge = QLabel("检测 FFmpeg…")
        self.ffmpeg_badge.setObjectName("badgePill")
        self.ffmpeg_badge.setFixedHeight(36)
        self.ffmpeg_badge.setAlignment(AlignCenter)
        lay.addWidget(self.ffmpeg_badge)

        mode_wrap = QFrame()
        mode_wrap.setObjectName("modeTrack")
        mode_wrap.setFixedHeight(36)
        mode_box = QHBoxLayout(mode_wrap)
        mode_box.setContentsMargins(4, 4, 4, 4)
        mode_box.setSpacing(2)
        self.mode_group = QButtonGroup(self)
        self.btn_convert = QPushButton("视频转音频")
        self.btn_merge = QPushButton("音频合并")
        for btn in (self.btn_convert, self.btn_merge):
            btn.setObjectName("modeButton")
            btn.setCheckable(True)
            btn.setCursor(PointingHandCursor)
            mode_box.addWidget(btn)
        self.mode_group.addButton(self.btn_convert, 0)
        self.mode_group.addButton(self.btn_merge, 1)
        self.btn_convert.setChecked(True)
        if hasattr(self.mode_group, "idClicked"):
            self.mode_group.idClicked.connect(self._on_mode_id)
        else:
            self.mode_group.buttonClicked.connect(
                lambda btn: self._on_mode_id(self.mode_group.id(btn))
            )
        lay.addWidget(mode_wrap)
        return header

    def _build_file_panel(self) -> QFrame:
        panel = QFrame()
        panel.setObjectName("panel")
        lay = QVBoxLayout(panel)
        lay.setContentsMargins(14, 14, 14, 16)
        lay.setSpacing(10)

        top = QHBoxLayout()
        top.setContentsMargins(0, 2, 0, 2)
        top.setSpacing(8)
        self.file_title = QLabel("预览 / 裁剪")
        self.file_title.setObjectName("sectionTitle")
        self.file_count = QLabel("0 个")
        self.file_count.setObjectName("countBadge")
        self.file_count.setFixedHeight(36)
        self.file_count.setAlignment(AlignCenter)
        top.addWidget(self.file_title, 0, AlignVCenter)
        top.addWidget(self.file_count, 0, AlignVCenter)
        top.addStretch(1)

        self.panel_actions = QFrame()
        self.panel_actions.setObjectName("headerActions")
        ha = QHBoxLayout(self.panel_actions)
        ha.setContentsMargins(0, 0, 0, 0)
        ha.setSpacing(6)
        for text, slot, oid in (
            ("添加文件", self._add_files, "headerBtn"),
            ("添加文件夹", self._add_folder, "headerBtn"),
            ("移除", self._remove_selected, "headerBtnGhost"),
            ("清空", self._clear, "headerBtnGhost"),
        ):
            b = QPushButton(text)
            b.setObjectName(oid)
            b.setCursor(PointingHandCursor)
            b.setFixedHeight(36)
            b.clicked.connect(slot)
            ha.addWidget(b)
        top.addWidget(self.panel_actions, 0, AlignVCenter)
        lay.addLayout(top)

        # Queue column (beside video in convert mode)
        self.queue_box = QWidget()
        qb = QVBoxLayout(self.queue_box)
        qb.setContentsMargins(0, 0, 0, 0)
        qb.setSpacing(6)

        q_head = QHBoxLayout()
        q_lab = QLabel("文件队列")
        q_lab.setObjectName("queueTitle")
        q_head.addWidget(q_lab)
        q_head.addStretch(1)
        self.btn_move_up = QPushButton("↑")
        self.btn_move_down = QPushButton("↓")
        for b, tip, slot in (
            (self.btn_move_up, "上移", self._move_up),
            (self.btn_move_down, "下移", self._move_down),
        ):
            b.setObjectName("queueMoveBtn")
            b.setToolTip(tip)
            b.setCursor(PointingHandCursor)
            b.setFixedSize(26, 26)
            b.clicked.connect(slot)
            q_head.addWidget(b)
        qb.addLayout(q_head)

        self.list_widget = QListWidget()
        self.list_widget.setObjectName("queueList")
        self.list_widget.setSelectionMode(ExtendedSelection)
        self.list_widget.setFlow(TopToBottom)
        self.list_widget.setHorizontalScrollBarPolicy(ScrollBarAlwaysOff)
        self.list_widget.setVerticalScrollBarPolicy(ScrollBarAsNeeded)
        self.list_widget.setSpacing(2)
        self.list_widget.itemSelectionChanged.connect(self._on_list_selection)
        qb.addWidget(self.list_widget, 1)

        self.trim_workspace = TrimWorkspace()
        self.trim_workspace.rangeChanged.connect(self._on_trim_range)
        self.trim_workspace.attach_side_panel(self.queue_box)
        lay.addWidget(self.trim_workspace, 1)

        self.merge_list_host = QWidget()
        ml = QVBoxLayout(self.merge_list_host)
        ml.setContentsMargins(0, 0, 0, 0)
        ml.setSpacing(0)
        self.merge_list_host.hide()
        lay.addWidget(self.merge_list_host, 1)

        self.merge_hint = QLabel("还没有添加音频\n\n至少添加 2 个文件后再合并")
        self.merge_hint.setObjectName("emptyState")
        self.merge_hint.setAlignment(AlignCenter)
        self.merge_hint.setWordWrap(True)
        self.merge_hint.hide()
        lay.addWidget(self.merge_hint, 1)
        return panel

    def _build_option_panel(self) -> QFrame:
        panel = QFrame()
        panel.setObjectName("panel")
        lay = QVBoxLayout(panel)
        lay.setContentsMargins(14, 14, 14, 14)
        lay.setSpacing(10)

        title = QLabel("输出设置")
        title.setObjectName("sectionTitle")
        lay.addWidget(title)

        self.format_combo = QComboBox()
        self.format_combo.addItems(list(OUTPUT_FORMATS))
        self.format_combo.setCurrentText("mp3")
        self.format_combo.setMinimumHeight(34)
        self.format_combo.currentTextChanged.connect(self._sync_quality_enabled)
        tune_combo(self.format_combo, 120)
        lay.addWidget(self._field("格式", self.format_combo))

        self.quality_combo = QComboBox()
        for label, key in QUALITY_CHOICES:
            self.quality_combo.addItem(label, key)
        self.quality_combo.setCurrentIndex(1)
        self.quality_combo.setMinimumHeight(34)
        tune_combo(self.quality_combo, 160)
        lay.addWidget(self._field("MP3 质量", self.quality_combo))

        self.rate_edit = QLineEdit()
        self.rate_edit.setPlaceholderText("例如 44100，可留空")
        self.rate_edit.setMinimumHeight(34)
        lay.addWidget(self._field("采样率", self.rate_edit))

        self.channels_edit = QLineEdit()
        self.channels_edit.setPlaceholderText("1 或 2，可留空")
        self.channels_edit.setMinimumHeight(34)
        lay.addWidget(self._field("声道", self.channels_edit))

        self.copy_check = QCheckBox("直接拷贝音轨（不重新编码）")
        self.overwrite_check = QCheckBox("覆盖已存在的输出文件")
        self.auto_open_check = QCheckBox("完成后自动打开输出目录")
        lay.addWidget(self.copy_check)
        lay.addWidget(self.overwrite_check)
        lay.addWidget(self.auto_open_check)

        self.outdir_edit = QLineEdit()
        self.outdir_edit.setPlaceholderText("留空则与源文件同目录")
        self.outdir_edit.setMinimumHeight(34)
        browse = QPushButton("浏览")
        browse.setCursor(PointingHandCursor)
        browse.setFixedWidth(72)
        browse.setMinimumHeight(34)
        browse.clicked.connect(self._pick_outdir)
        out_row = QHBoxLayout()
        out_row.setContentsMargins(0, 0, 0, 0)
        out_row.setSpacing(8)
        out_row.addWidget(self.outdir_edit, 1)
        out_row.addWidget(browse)
        out_wrap = QWidget()
        out_wrap.setLayout(out_row)
        lay.addWidget(self._field("输出目录", out_wrap))

        log_title = QLabel("日志")
        log_title.setObjectName("sectionTitle")
        lay.addWidget(log_title)
        self.log = QPlainTextEdit()
        self.log.setObjectName("logView")
        self.log.setReadOnly(True)
        self.log.setMaximumBlockCount(2000)
        self.log.setPlaceholderText("转换日志会显示在这里")
        self.log.setMinimumHeight(100)
        lay.addWidget(self.log, 1)
        return panel

    def _field(self, label: str, widget: QWidget) -> QWidget:
        wrap = QWidget()
        lay = QVBoxLayout(wrap)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(4)
        lab = QLabel(label)
        lab.setObjectName("fieldLabel")
        lay.addWidget(lab)
        lay.addWidget(widget)
        return wrap

    def _build_footer(self) -> QFrame:
        footer = QFrame()
        footer.setObjectName("footerBar")
        lay = QVBoxLayout(footer)
        lay.setContentsMargins(20, 12, 20, 14)
        lay.setSpacing(8)

        self.progress_text = QLabel("就绪")
        self.progress_text.setObjectName("mutedText")
        lay.addWidget(self.progress_text)

        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.setTextVisible(True)
        self.progress.setFormat("%p%")
        self.progress.setMinimumHeight(18)
        lay.addWidget(self.progress)

        actions = QHBoxLayout()
        open_btn = QPushButton("打开输出目录")
        open_btn.setCursor(PointingHandCursor)
        open_btn.clicked.connect(self._open_outdir)
        actions.addWidget(open_btn)
        actions.addStretch(1)
        self.action_btn = QPushButton("开始转换")
        self.action_btn.setObjectName("primaryButton")
        self.action_btn.setCursor(PointingHandCursor)
        self.action_btn.clicked.connect(self._start_action)
        actions.addWidget(self.action_btn)
        lay.addLayout(actions)
        return footer

    def _on_mode_id(self, button_id: int) -> None:
        self._mode = MODE_MERGE if button_id == 1 else MODE_CONVERT
        self._clear()
        self._apply_mode_ui()

    def _apply_mode_ui(self) -> None:
        merge = self._mode == MODE_MERGE
        if merge:
            self.file_title.setText("待合并音频")
            self.action_btn.setText("开始合并")
            self.trim_workspace.hide()
            self.trim_workspace.clear()
            self.trim_workspace.detach_side_panel()
            self.merge_list_host.layout().addWidget(self.queue_box)
            self.queue_box.show()
            self.merge_list_host.show()
            self.list_widget.setObjectName("fileList")
            self.list_widget.setMaximumHeight(16777215)
            self.list_widget.setMinimumHeight(220)
            self.merge_hint.show()
        else:
            self.file_title.setText("预览 / 裁剪")
            self.action_btn.setText("开始转换")
            self.merge_hint.hide()
            self.merge_list_host.hide()
            # take queue out of merge host if present
            host_lay = self.merge_list_host.layout()
            if host_lay is not None:
                while host_lay.count():
                    item = host_lay.takeAt(0)
                    w = item.widget()
                    if w is not None:
                        w.setParent(None)
            self.list_widget.setObjectName("queueList")
            self.list_widget.setMaximumHeight(16777215)
            self.list_widget.setMinimumHeight(0)
            self.trim_workspace.attach_side_panel(self.queue_box)
            self.trim_workspace.show()
        self.list_widget.style().unpolish(self.list_widget)
        self.list_widget.style().polish(self.list_widget)
        self.copy_check.setEnabled(not merge)
        self._refresh_list()

    def _sync_quality_enabled(self, _text: str | None = None) -> None:
        self.quality_combo.setEnabled(self.format_combo.currentText() == "mp3")

    def _quality_key(self) -> str:
        data = self.quality_combo.currentData()
        return str(data) if data else "medium"

    def _dialog_start_dir(self, kind: str) -> str:
        if kind == "video":
            return existing_dir(self.config.last_video_dir)
        if kind == "audio":
            return existing_dir(self.config.last_audio_dir)
        if kind == "output":
            return existing_dir(self.config.last_output_dir) or existing_dir(
                self.outdir_edit.text().strip()
            )
        return ""

    def _selected_path(self) -> Path | None:
        rows = self._selected_rows()
        if len(rows) != 1:
            return None
        idx = rows[0]
        if idx < 0 or idx >= len(self._paths):
            return None
        return self._paths[idx]

    def _on_list_selection(self) -> None:
        if self._mode == MODE_MERGE:
            empty = len(self._paths) == 0
            self.merge_hint.setVisible(empty)
            self.list_widget.setVisible(True)
            return
        path = self._selected_path()
        if path is None:
            if not self._paths:
                self.trim_workspace.clear()
            return
        self._load_preview(path)

    def _on_trim_range(self, start: object, end: object) -> None:
        path = self._selected_path()
        if path is None:
            return
        if start is None and end is None:
            self._trims.pop(path, None)
        else:
            self._trims[path] = (start if isinstance(start, str) else None, end if isinstance(end, str) else None)
        # refresh scissors mark without reloading video
        row = self._paths.index(path)
        item = self.list_widget.item(row)
        if item is not None:
            mark = " ✂" if path in self._trims else ""
            item.setText(f"{path.name}{mark}")

    def _load_preview(self, path: Path) -> None:
        if self._loading_preview:
            return
        self._loading_preview = True
        try:
            start, end = self._trims.get(path, (None, None))
            self.trim_workspace.load_video(path, start=start, end=end)
        finally:
            self._loading_preview = False

    def _refresh_ffmpeg_status(self) -> None:
        try:
            ffmpeg, _ = ensure_ffmpeg()
            bundled = bundled_ffmpeg_dir() / "ffmpeg.exe"
            tag = "内置" if Path(ffmpeg).resolve() == bundled.resolve() else "系统"
            bits = "64" if sys.maxsize > 2**32 else "32"
            self.ffmpeg_badge.setText(f"FFmpeg {tag} · {bits}位")
            self.ffmpeg_badge.setProperty("status", "ok")
            self.ffmpeg_badge.style().unpolish(self.ffmpeg_badge)
            self.ffmpeg_badge.style().polish(self.ffmpeg_badge)
        except FFmpegNotFoundError:
            self.ffmpeg_badge.setText("未找到 FFmpeg")
            self.ffmpeg_badge.setProperty("status", "error")
            self.ffmpeg_badge.style().unpolish(self.ffmpeg_badge)
            self.ffmpeg_badge.style().polish(self.ffmpeg_badge)

    def _append_log(self, text: str) -> None:
        self.log.appendPlainText(text)

    def _set_progress(self, value: float, text: str) -> None:
        self.progress.setValue(int(max(0.0, min(1.0, value)) * 100))
        self.progress_text.setText(text)

    def _refresh_list(self) -> None:
        current = self._selected_path()
        self.list_widget.blockSignals(True)
        self.list_widget.clear()
        for path in self._paths:
            mark = " ✂" if path in self._trims else ""
            name = path.name
            if len(name) > 24:
                name = name[:12] + "…" + name[-8:]
            item = QListWidgetItem(f"{name}{mark}")
            tip = str(path)
            if path in self._trims:
                s, e = self._trims[path]
                tip += f"\n裁剪: {s or '0'} → {e or '结尾'}"
            item.setToolTip(tip)
            self.list_widget.addItem(item)
        self.list_widget.blockSignals(False)

        n = len(self._paths)
        self.file_count.setText(f"{n} 个")

        if self._mode == MODE_MERGE:
            self.merge_hint.setVisible(n == 0)
            self.trim_workspace.hide()
            return

        self.merge_hint.hide()
        self.trim_workspace.show()
        if n == 0:
            self.trim_workspace.clear()
            return

        # Keep selection / auto-select first
        target_row = 0
        if current is not None:
            try:
                target_row = self._paths.index(current)
            except ValueError:
                target_row = 0
        self.list_widget.setCurrentRow(target_row)
        self._load_preview(self._paths[target_row])

    def _add_files(self) -> None:
        if self._mode == MODE_MERGE:
            start = self._dialog_start_dir("audio")
            paths, _ = QFileDialog.getOpenFileNames(self, "选择音频文件", start, AUDIO_FILTER)
            if paths:
                self.config.last_audio_dir = str(Path(paths[0]).parent)
                self._ingest_paths([Path(p) for p in paths])
        else:
            start = self._dialog_start_dir("video")
            paths, _ = QFileDialog.getOpenFileNames(self, "选择视频文件", start, VIDEO_FILTER)
            if paths:
                self.config.last_video_dir = str(Path(paths[0]).parent)
                self._ingest_paths([Path(p) for p in paths])
        self._persist_config()

    def _add_folder(self) -> None:
        kind = "audio" if self._mode == MODE_MERGE else "video"
        folder = QFileDialog.getExistingDirectory(self, "选择文件夹", self._dialog_start_dir(kind))
        if not folder:
            return
        if self._mode == MODE_MERGE:
            self.config.last_audio_dir = folder
            files = collect_audio_files([Path(folder)], recursive=True)
        else:
            self.config.last_video_dir = folder
            files = collect_video_files(Path(folder), recursive=True)
        if not files:
            QMessageBox.information(self, "提示", "该文件夹里没有找到可用文件。")
            return
        self._ingest_paths(files)
        self._persist_config()

    def _ingest_paths(self, paths: list[Path]) -> None:
        existing = {p.resolve() for p in self._paths}
        added = 0
        first_new: Path | None = None
        for path in paths:
            path = path.resolve()
            if path.is_dir():
                try:
                    found = (
                        collect_audio_files([path], recursive=True)
                        if self._mode == MODE_MERGE
                        else collect_video_files(path, recursive=True)
                    )
                except (OSError, ValueError) as exc:
                    self._append_log(f"跳过 {path.name}：{exc}")
                    continue
                for f in found:
                    if f not in existing:
                        self._paths.append(f)
                        existing.add(f)
                        added += 1
                        if first_new is None:
                            first_new = f
            elif path.is_file() and path not in existing:
                self._paths.append(path)
                existing.add(path)
                added += 1
                if first_new is None:
                    first_new = path
        self._refresh_list()
        if first_new is not None and self._mode != MODE_MERGE:
            self.list_widget.setCurrentRow(self._paths.index(first_new))
        if added:
            self._append_log(f"已添加 {added} 个文件")

    def _selected_rows(self) -> list[int]:
        return sorted({i.row() for i in self.list_widget.selectedIndexes()})

    def _move_up(self) -> None:
        self._shift_selection(-1)

    def _move_down(self) -> None:
        self._shift_selection(1)

    def _shift_selection(self, delta: int) -> None:
        selected = move_selected(self._paths, self._selected_rows(), delta)
        if selected is None:
            return
        self._refresh_list()
        for index in selected:
            item = self.list_widget.item(index)
            if item is not None:
                item.setSelected(True)

    def _remove_selected(self) -> None:
        for i in reversed(self._selected_rows()):
            path = self._paths[i]
            self._trims.pop(path, None)
            del self._paths[i]
        self._refresh_list()

    def _clear(self) -> None:
        self._paths.clear()
        self._trims.clear()
        self.trim_workspace.clear()
        self._refresh_list()
        self._set_progress(0, "就绪")

    def _pick_outdir(self) -> None:
        folder = QFileDialog.getExistingDirectory(
            self, "选择输出目录", self._dialog_start_dir("output")
        )
        if folder:
            self.outdir_edit.setText(folder)
            self.config.last_output_dir = folder
            self._persist_config()

    def _open_outdir(self, *, quiet: bool = False) -> None:
        raw = self.outdir_edit.text().strip()
        if raw:
            path = Path(raw)
        elif self._paths:
            path = self._paths[0].parent
        else:
            remembered = existing_dir(self.config.last_output_dir)
            path = Path(remembered) if remembered else Path.cwd()
        if not path.exists():
            if not quiet:
                QMessageBox.information(self, "提示", f"目录不存在：{path}")
            return
        if sys.platform == "win32":
            os.startfile(path)  # type: ignore[attr-defined]
        elif sys.platform == "darwin":
            subprocess.run(["open", str(path)], check=False)
        else:
            subprocess.run(["xdg-open", str(path)], check=False)

    def _maybe_auto_open(self, file_path: Path | None = None) -> None:
        if not self.auto_open_check.isChecked():
            return
        if file_path is not None:
            folder = file_path if file_path.is_dir() else file_path.parent
            if folder.is_dir():
                if sys.platform == "win32":
                    os.startfile(folder)  # type: ignore[attr-defined]
                elif sys.platform == "darwin":
                    subprocess.run(["open", str(folder)], check=False)
                else:
                    subprocess.run(["xdg-open", str(folder)], check=False)
                return
        self._open_outdir(quiet=True)

    def _base_convert_options(self) -> ConvertOptions:
        outdir_raw = self.outdir_edit.text().strip()
        fmt = self.format_combo.currentText()
        return ConvertOptions(
            format=fmt,
            quality=self._quality_key() if fmt == "mp3" else None,
            sample_rate=parse_optional_positive_int(
                self.rate_edit.text(), "采样率", maximum=384000
            ),
            channels=parse_optional_positive_int(self.channels_edit.text(), "声道", maximum=8),
            copy_audio=self.copy_check.isChecked(),
            overwrite=self.overwrite_check.isChecked(),
            output_dir=Path(outdir_raw) if outdir_raw else None,
        )

    def _jobs_for_convert(self) -> list[tuple[Path, ConvertOptions]]:
        # Persist current preview trim before convert
        path = self._selected_path()
        if path is not None and self._mode == MODE_CONVERT:
            s, e = self.trim_workspace.ffmpeg_range()
            if s is None and e is None:
                self._trims.pop(path, None)
            else:
                self._trims[path] = (s, e)

        base = self._base_convert_options()
        jobs: list[tuple[Path, ConvertOptions]] = []
        for path in self._paths:
            if path in self._trims:
                start, end = self._trims[path]
                opts = replace(base, start=start, end=end)
            else:
                opts = replace(base)
            jobs.append((path, opts))
        return jobs

    def _build_merge_options(self) -> MergeOptions:
        outdir_raw = self.outdir_edit.text().strip()
        fmt = self.format_combo.currentText()
        return MergeOptions(
            format=fmt,
            quality=self._quality_key() if fmt == "mp3" else None,
            sample_rate=parse_optional_positive_int(
                self.rate_edit.text(), "采样率", maximum=384000
            ),
            channels=parse_optional_positive_int(self.channels_edit.text(), "声道", maximum=8),
            overwrite=self.overwrite_check.isChecked(),
            output_dir=Path(outdir_raw) if outdir_raw else None,
        )

    def _set_busy(self, busy: bool) -> None:
        self.action_btn.setEnabled(not busy)
        self.btn_convert.setEnabled(not busy)
        self.btn_merge.setEnabled(not busy)

    def _start_action(self) -> None:
        if self._worker and self._worker.isRunning():
            return
        self._persist_config()
        if self._mode == MODE_MERGE:
            self._start_merge()
        else:
            self._start_convert()

    def _start_convert(self) -> None:
        if not self._paths:
            QMessageBox.information(self, "提示", "请先添加至少一个视频文件。")
            return
        try:
            ensure_ffmpeg()
            jobs = self._jobs_for_convert()
        except FFmpegNotFoundError as exc:
            QMessageBox.critical(self, "缺少 FFmpeg", str(exc))
            return
        except ValueError as exc:
            QMessageBox.critical(self, "参数错误", str(exc))
            return

        q = self._quality_key()
        if jobs[0][1].format == "mp3":
            self._append_log(f"MP3 质量：{describe_mp3_quality(q)}")

        self._set_busy(True)
        self._set_progress(0, "开始转换…")
        worker = ConvertWorker(jobs)
        worker.progress.connect(self._set_progress)
        worker.log_line.connect(self._append_log)
        worker.finished_report.connect(self._on_convert_done)
        worker.failed.connect(self._on_worker_failed)
        worker.finished.connect(lambda: self._set_busy(False))
        self._worker = worker
        worker.start()

    def _on_convert_done(self, payload: object) -> None:
        report, log_path = payload  # type: ignore[misc]
        self._set_progress(1.0, "转换完成")
        msg = f"完成：成功 {len(report.succeeded)}，失败 {len(report.failed)}"
        if log_path:
            msg += f"\n失败日志：{log_path}"
        self._append_log(msg)
        kind = "error" if report.failed else "ok"
        title = "转换完成" if kind == "ok" else "转换未完成"
        show_corner_toast(title, msg.replace("\n", " "), kind=kind)
        if report.succeeded:
            self._maybe_auto_open()

    def _start_merge(self) -> None:
        if len(self._paths) < 2:
            QMessageBox.information(self, "提示", "合并至少需要 2 个音频文件。")
            return
        try:
            ensure_ffmpeg()
            options = self._build_merge_options()
        except FFmpegNotFoundError as exc:
            QMessageBox.critical(self, "缺少 FFmpeg", str(exc))
            return
        except ValueError as exc:
            QMessageBox.critical(self, "参数错误", str(exc))
            return

        self._set_busy(True)
        self._set_progress(0.05, "正在合并…")
        worker = MergeWorker(list(self._paths), options)
        worker.progress.connect(self._set_progress)
        worker.log_line.connect(self._append_log)
        worker.finished_result.connect(self._on_merge_done)
        worker.failed.connect(self._on_worker_failed)
        worker.finished.connect(lambda: self._set_busy(False))
        self._worker = worker
        worker.start()

    def _on_merge_done(self, result: object) -> None:
        assert isinstance(result, ConvertResult)
        self._set_progress(1.0, "合并完成" if result.ok else "合并失败")
        if result.ok:
            self._append_log(f"[成功] → {result.output_path}")
            show_corner_toast("合并完成", str(result.output_path), kind="ok")
            self._maybe_auto_open(result.output_path)
        else:
            tail = result.message.splitlines()[-1] if result.message else "未知错误"
            self._append_log("[失败] " + tail)
            show_corner_toast("合并失败", tail, kind="error")

    def _on_worker_failed(self, message: str) -> None:
        self._append_log("[异常] " + message)
        show_corner_toast("出错了", message, kind="error")
