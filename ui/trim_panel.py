"""嵌入主窗口的视频预览 + 入出点裁剪面板。"""

from __future__ import annotations

from pathlib import Path

from core.trim_time import ms_to_stamp, parse_time_to_ms, stamp_to_ffmpeg
from ui.qtcompat import (
    QT_API,
    AlignCenter,
    Horizontal,
    PointingHandCursor,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSlider,
    QTimer,
    QVBoxLayout,
    QWidget,
    load_media_player,
    pyqtSignal,
    Qt,
)


def _left_button():
    if QT_API == "pyqt6":
        return Qt.MouseButton.LeftButton
    return Qt.LeftButton


def _event_x(event) -> float:
    if hasattr(event, "position"):
        return float(event.position().x())
    return float(event.x())


class JumpSlider(QSlider):
    """Click or drag anywhere on the groove jumps to that value."""

    def _value_at(self, event) -> int:
        span = max(1, self.maximum() - self.minimum())
        width = max(1, self.width() - 1)
        ratio = min(1.0, max(0.0, _event_x(event) / width))
        return int(round(self.minimum() + ratio * span))

    def mousePressEvent(self, event) -> None:  # noqa: N802, ANN001
        if event.button() == _left_button():
            self.setValue(self._value_at(event))
            self.setSliderDown(True)
            self.sliderPressed.emit()
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:  # noqa: N802, ANN001
        buttons = event.buttons() if hasattr(event, "buttons") else 0
        if buttons & _left_button():
            self.setValue(self._value_at(event))
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802, ANN001
        if event.button() == _left_button():
            self.setValue(self._value_at(event))
            self.setSliderDown(False)
            self.sliderReleased.emit()
            event.accept()
            return
        super().mouseReleaseEvent(event)


class PlayButton(QPushButton):
    """Circular play/pause control with a centered glyph."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._playing = False
        self.setText("")

    def set_playing(self, playing: bool) -> None:
        self._playing = bool(playing)
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802, ANN001
        super().paintEvent(event)
        if QT_API == "pyqt6":
            from PyQt6.QtCore import QPointF, QRectF, Qt as _Qt
            from PyQt6.QtGui import QColor, QPainter, QPolygonF
        else:
            from PyQt5.QtCore import QPointF, QRectF, Qt as _Qt  # type: ignore
            from PyQt5.QtGui import QColor, QPainter, QPolygonF  # type: ignore

        painter = QPainter(self)
        painter.setRenderHint(
            QPainter.RenderHint.Antialiasing
            if hasattr(QPainter, "RenderHint")
            else QPainter.Antialiasing
        )
        painter.setPen(_Qt.PenStyle.NoPen if hasattr(_Qt, "PenStyle") else _Qt.NoPen)
        painter.setBrush(QColor("#FFFFFF"))
        cx = self.width() / 2
        cy = self.height() / 2
        if self._playing:
            bar_w, bar_h, gap = 3.0, 12.0, 4.0
            left = cx - gap / 2 - bar_w
            painter.drawRoundedRect(QRectF(left, cy - bar_h / 2, bar_w, bar_h), 1.2, 1.2)
            painter.drawRoundedRect(QRectF(cx + gap / 2, cy - bar_h / 2, bar_w, bar_h), 1.2, 1.2)
        else:
            size = 8.0
            painter.drawPolygon(
                QPolygonF(
                    [
                        QPointF(cx - size * 0.28, cy - size),
                        QPointF(cx - size * 0.28, cy + size),
                        QPointF(cx + size * 0.85, cy),
                    ]
                )
            )
        painter.end()


class TrimWorkspace(QWidget):
    """左侧主区域：预览 + 裁剪。rangeChanged 发出 (start, end) ffmpeg 时间或 (None, None)。"""

    rangeChanged = pyqtSignal(object, object)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._path: Path | None = None
        self._duration = 0
        self._start_ms = 0
        self._end_ms = 0
        self._player = None
        self._dragging = False
        self._range_preview = False
        self._poster_pending = False
        self._priming_poster = False
        self._media_ok = False
        self._suppress = False
        self._end_to_eof = True

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(10)

        self._empty = QLabel("还没有添加视频\n\n点击下方「添加文件」导入后\n左侧选文件 · 右侧预览裁剪")
        self._empty.setObjectName("emptyState")
        self._empty.setAlignment(AlignCenter)
        self._empty.setWordWrap(True)
        root.addWidget(self._empty, 1)

        self._work = QWidget()
        work_lay = QVBoxLayout(self._work)
        work_lay.setContentsMargins(0, 0, 0, 0)
        work_lay.setSpacing(10)

        # ── Stage: queue (side) | player ───────────────────
        stage = QWidget()
        stage_lay = QHBoxLayout(stage)
        stage_lay.setContentsMargins(0, 0, 0, 0)
        stage_lay.setSpacing(12)

        self._side_host = QFrame()
        self._side_host.setObjectName("queuePanel")
        self._side_host.setFixedWidth(210)
        self._side_host.hide()
        self._side_lay = QVBoxLayout(self._side_host)
        self._side_lay.setContentsMargins(10, 10, 10, 10)
        self._side_lay.setSpacing(8)
        stage_lay.addWidget(self._side_host, 0)

        player = QFrame()
        player.setObjectName("playerCard")
        player_lay = QVBoxLayout(player)
        player_lay.setContentsMargins(0, 0, 0, 0)
        player_lay.setSpacing(0)

        self._video_host = QFrame()
        self._video_host.setObjectName("videoStage")
        self._video_host.setMinimumHeight(220)
        vh = QVBoxLayout(self._video_host)
        vh.setContentsMargins(0, 0, 0, 0)
        vh.setSpacing(0)

        self._video = None
        self._fallback = QLabel("添加视频后在此预览")
        self._fallback.setAlignment(AlignCenter)
        self._fallback.setObjectName("videoPlaceholder")
        self._fallback.setWordWrap(True)
        vh.addWidget(self._fallback)
        player_lay.addWidget(self._video_host, 1)

        transport = QFrame()
        transport.setObjectName("transportBar")
        transport.setFixedHeight(56)
        tl = QHBoxLayout(transport)
        tl.setContentsMargins(12, 8, 12, 8)
        tl.setSpacing(10)

        self._play_btn = PlayButton()
        self._play_btn.setObjectName("playButton")
        self._play_btn.setCursor(PointingHandCursor)
        self._play_btn.setFixedSize(40, 40)
        self._play_btn.setToolTip("播放 / 暂停")
        self._play_btn.clicked.connect(self._toggle_play)
        tl.addWidget(self._play_btn)

        self._back_btn = QPushButton("−1s")
        self._fwd_btn = QPushButton("+1s")
        for b, slot in (
            (self._back_btn, lambda: self._nudge(-1000)),
            (self._fwd_btn, lambda: self._nudge(1000)),
        ):
            b.setObjectName("nudgeButton")
            b.setCursor(PointingHandCursor)
            b.setFixedHeight(32)
            b.clicked.connect(slot)
            tl.addWidget(b)

        self._pos_slider = JumpSlider(Horizontal)
        self._pos_slider.setObjectName("seekSlider")
        self._pos_slider.setMinimumHeight(22)
        self._pos_slider.setRange(0, 0)
        self._pos_slider.sliderPressed.connect(lambda: setattr(self, "_dragging", True))
        self._pos_slider.sliderReleased.connect(self._on_seek_release)
        self._pos_slider.sliderMoved.connect(self._on_seek_moved)
        self._pos_slider.valueChanged.connect(self._on_pos_slider_value)
        tl.addWidget(self._pos_slider, 1)

        self._cur_label = QLabel("00:00.000")
        self._cur_label.setObjectName("timeChip")
        self._dur_label = QLabel("00:00.000")
        self._dur_label.setObjectName("timeChipMuted")
        tl.addWidget(self._cur_label)
        slash = QLabel("/")
        slash.setObjectName("timeChipMuted")
        tl.addWidget(slash)
        tl.addWidget(self._dur_label)
        player_lay.addWidget(transport)

        stage_lay.addWidget(player, 1)
        work_lay.addWidget(stage, 1)

        # ── Trim controls ─────────────────────────────────
        controls = QFrame()
        controls.setObjectName("trimControls")
        controls.setMinimumHeight(200)
        cl = QVBoxLayout(controls)
        cl.setContentsMargins(0, 4, 0, 6)
        cl.setSpacing(8)

        mark_row = QHBoxLayout()
        mark_row.setSpacing(8)
        self._mark_in_btn = QPushButton("设为入点")
        self._mark_in_btn.setObjectName("markButton")
        self._mark_out_btn = QPushButton("设为出点")
        self._mark_out_btn.setObjectName("markButton")
        self._clear_btn = QPushButton("整段")
        self._clear_btn.setObjectName("ghostButton")
        for b, slot in (
            (self._mark_in_btn, self._mark_in),
            (self._mark_out_btn, self._mark_out),
            (self._clear_btn, self._clear_range),
        ):
            b.setCursor(PointingHandCursor)
            b.setMinimumHeight(36)
            b.clicked.connect(slot)
            mark_row.addWidget(b, 1 if b is not self._clear_btn else 0)
        cl.addLayout(mark_row)

        start_row = QHBoxLayout()
        start_lab = QLabel("入点")
        start_lab.setObjectName("fieldLabel")
        start_lab.setFixedWidth(36)
        self._start_slider = JumpSlider(Horizontal)
        self._start_slider.setObjectName("trimSlider")
        self._start_slider.setMinimumHeight(22)
        self._start_slider.valueChanged.connect(self._on_start_changed)
        self._start_edit = QLineEdit("00:00.000")
        self._start_edit.setPlaceholderText("00:00.000")
        self._start_edit.setFixedWidth(110)
        self._start_edit.setMinimumHeight(32)
        self._start_edit.editingFinished.connect(self._on_start_edit_finished)
        start_row.addWidget(start_lab)
        start_row.addWidget(self._start_slider, 1)
        start_row.addWidget(self._start_edit)
        cl.addLayout(start_row)

        end_row = QHBoxLayout()
        end_lab = QLabel("出点")
        end_lab.setObjectName("fieldLabel")
        end_lab.setFixedWidth(36)
        self._end_slider = JumpSlider(Horizontal)
        self._end_slider.setObjectName("trimSlider")
        self._end_slider.setMinimumHeight(22)
        self._end_slider.valueChanged.connect(self._on_end_changed)
        self._end_edit = QLineEdit("")
        self._end_edit.setPlaceholderText("留空=到结尾")
        self._end_edit.setFixedWidth(110)
        self._end_edit.setMinimumHeight(32)
        self._end_edit.editingFinished.connect(self._on_end_edit_finished)
        end_row.addWidget(end_lab)
        end_row.addWidget(self._end_slider, 1)
        end_row.addWidget(self._end_edit)
        cl.addLayout(end_row)

        hint = QLabel("时间可输入 01:05.500 或秒数；出点留空 = 转到结尾")
        hint.setObjectName("mutedText")
        hint.setWordWrap(True)
        cl.addWidget(hint)

        self._summary = QLabel("区间：整段（转换全部）")
        self._summary.setObjectName("trimSummary")
        self._summary.setAlignment(AlignCenter)
        cl.addWidget(self._summary)

        work_lay.addWidget(controls, 0)
        root.addWidget(self._work, 1)
        self._work.hide()

        self._init_player()

    def attach_side_panel(self, widget: QWidget) -> None:
        """Put file queue on the left of the video stage."""
        while self._side_lay.count():
            item = self._side_lay.takeAt(0)
            w = item.widget()
            if w is not None:
                w.setParent(None)
        self._side_lay.addWidget(widget, 1)
        self._side_host.show()

    def detach_side_panel(self) -> QWidget | None:
        """Remove side panel from stage; caller reparents it."""
        widget = None
        while self._side_lay.count():
            item = self._side_lay.takeAt(0)
            w = item.widget()
            if w is not None:
                widget = w
                w.setParent(None)
        self._side_host.hide()
        return widget

    def _init_player(self) -> None:
        try:
            PlayerCls, VideoCls, bind = load_media_player()
        except ImportError as exc:
            self._fallback.setText(f"无法预览视频\n{exc}")
            self._media_ok = False
            return
        self._bind = bind
        layout = self._video_host.layout()
        self._video = VideoCls()
        self._video.setMinimumHeight(180)
        try:
            from PyQt6.QtCore import Qt as _Qt

            self._video.setAspectRatioMode(_Qt.AspectRatioMode.KeepAspectRatio)
        except Exception:  # noqa: BLE001
            pass
        layout.addWidget(self._video)
        self._video.hide()
        self._fallback.raise_()
        self._player = PlayerCls(self)
        if QT_API == "pyqt6":
            self._player.durationChanged.connect(self._on_duration)
            self._player.positionChanged.connect(self._on_position)
            self._player.playbackStateChanged.connect(self._on_state)
            self._player.mediaStatusChanged.connect(self._on_media_status)
        else:
            self._player.durationChanged.connect(self._on_duration)
            self._player.positionChanged.connect(self._on_position)
            self._player.stateChanged.connect(self._on_state_pyqt5)
            self._player.mediaStatusChanged.connect(self._on_media_status)
        self._media_ok = True

    def _on_media_status(self, status: int) -> None:
        """Decode one frame after load so the preview is not a black box."""
        if not self._poster_pending or self._player is None:
            return
        if QT_API == "pyqt6":
            from PyQt6.QtMultimedia import QMediaPlayer

            ready = status in (
                QMediaPlayer.MediaStatus.LoadedMedia,
                QMediaPlayer.MediaStatus.BufferedMedia,
            )
        else:
            from PyQt5.QtMultimedia import QMediaPlayer  # type: ignore

            ready = status in (QMediaPlayer.LoadedMedia, QMediaPlayer.BufferedMedia)
        if not ready:
            return
        self._poster_pending = False
        self._priming_poster = False
        # Seek only. play() on a long file blocks the UI and flashes the button.
        self._player.pause()
        self._player.setPosition(0)
        self._play_btn.set_playing(False)

    def clear(self) -> None:
        self._stop_player()
        self._path = None
        self._duration = 0
        self._start_ms = 0
        self._end_ms = 0
        self._end_to_eof = True
        self._pos_slider.setRange(0, 0)
        self._start_slider.setRange(0, 0)
        self._end_slider.setRange(0, 0)
        self._cur_label.setText("00:00.000")
        self._dur_label.setText("00:00.000")
        self._summary.setText("区间：整段（转换全部）")
        self._start_edit.setText("00:00.000")
        self._end_edit.clear()
        # Keep side-by-side stage visible when queue is attached
        if self._side_lay.count() > 0:
            self._empty.hide()
            self._work.show()
            if self._video is not None:
                self._video.hide()
            self._fallback.setText("添加视频后在此预览")
            self._fallback.show()
            self._fallback.raise_()
        else:
            self._work.hide()
            self._empty.show()

    def load_video(
        self,
        path: Path,
        start: str | None = None,
        end: str | None = None,
    ) -> None:
        self._empty.hide()
        self._work.show()
        self._path = path
        if self._video is not None:
            self._video.show()
            self._video.raise_()
        self._fallback.hide()
        self._suppress = True
        self._start_ms = 0
        self._end_ms = 0
        self._end_to_eof = end is None
        self._duration = 0
        self._pos_slider.setRange(0, 0)
        self._start_slider.setRange(0, 0)
        self._end_slider.setRange(0, 0)
        self._pending_start = start
        self._pending_end = end
        self._suppress = False
        self._play_btn.set_playing(False)
        self._poster_pending = True

        if not self._media_ok or self._player is None or self._video is None:
            if self._video is not None:
                self._video.hide()
            self._fallback.show()
            self._fallback.raise_()
            self._fallback.setText("当前环境无法播放预览\n仍可用下方滑条 / 输入框裁剪")
            return

        self._stop_player()
        self._bind(self._player, self._video, str(path.resolve()))
        QTimer.singleShot(350, self._ensure_duration)

    def ffmpeg_range(self) -> tuple[str | None, str | None]:
        if self._duration <= 0:
            return None, None
        start = None if self._start_ms <= 0 else stamp_to_ffmpeg(self._start_ms)
        if self._end_to_eof or self._end_ms >= self._duration:
            end = None
        else:
            end = stamp_to_ffmpeg(self._end_ms)
        if start is None and end is None:
            return None, None
        return start, end

    def _emit_range(self) -> None:
        if self._suppress or self._path is None:
            return
        s, e = self.ffmpeg_range()
        self.rangeChanged.emit(s, e)

    def _stop_player(self) -> None:
        if self._player is not None:
            try:
                self._player.stop()
            except Exception:  # noqa: BLE001
                pass

    def _ensure_duration(self) -> None:
        if self._player is None:
            return
        d = int(self._player.duration())
        if d > 0:
            self._on_duration(d)

    def _apply_pending_range(self) -> None:
        start = getattr(self, "_pending_start", None)
        end = getattr(self, "_pending_end", None)
        self._pending_start = None
        self._pending_end = None
        if self._duration <= 0:
            return
        self._suppress = True
        if start:
            try:
                ms = int(float(start) * 1000)
                self._start_slider.setValue(max(0, min(self._duration, ms)))
            except ValueError:
                self._start_slider.setValue(0)
        else:
            self._start_slider.setValue(0)
        if end:
            self._end_to_eof = False
            try:
                ms = int(float(end) * 1000)
                self._end_slider.setValue(max(0, min(self._duration, ms)))
            except ValueError:
                self._end_to_eof = True
                self._end_slider.setValue(self._duration)
        else:
            self._end_to_eof = True
            self._end_slider.setValue(self._duration)
        self._suppress = False
        self._refresh_range_labels()

    def _on_duration(self, duration: int) -> None:
        if duration <= 0:
            return
        self._duration = int(duration)
        self._pos_slider.setRange(0, self._duration)
        self._start_slider.setRange(0, self._duration)
        self._end_slider.setRange(0, self._duration)
        self._dur_label.setText(ms_to_stamp(self._duration))
        if getattr(self, "_pending_start", None) is not None or getattr(self, "_pending_end", None) is not None:
            self._apply_pending_range()
        else:
            self._suppress = True
            self._start_slider.setValue(0)
            self._end_to_eof = True
            self._end_slider.setValue(self._duration)
            self._suppress = False
            self._refresh_range_labels()

    def _on_position(self, pos: int) -> None:
        pos = int(pos)
        if self._range_preview and not self._end_to_eof and pos >= self._end_ms:
            self._range_preview = False
            if self._player is not None:
                self._player.pause()
                self._player.setPosition(self._end_ms)
            pos = self._end_ms
        if not self._dragging:
            self._pos_slider.blockSignals(True)
            self._pos_slider.setValue(pos)
            self._pos_slider.blockSignals(False)
        self._cur_label.setText(ms_to_stamp(pos))

    def _on_state(self, state) -> None:  # noqa: ANN001
        from PyQt6.QtMultimedia import QMediaPlayer

        playing = state == QMediaPlayer.PlaybackState.PlayingState
        self._play_btn.set_playing(playing)

    def _on_state_pyqt5(self, state: int) -> None:
        from PyQt5.QtMultimedia import QMediaPlayer  # type: ignore

        playing = state == QMediaPlayer.PlayingState
        self._play_btn.set_playing(playing)

    def _toggle_play(self) -> None:
        if self._player is None:
            return
        playing = self._is_playing()
        if playing:
            self._range_preview = False
            self._player.pause()
            return
        if self._has_trim_range():
            self._range_preview = True
            self._player.setPosition(self._start_ms)
        else:
            self._range_preview = False
        self._player.play()

    def _is_playing(self) -> bool:
        if self._player is None:
            return False
        if QT_API == "pyqt6":
            from PyQt6.QtMultimedia import QMediaPlayer

            return self._player.playbackState() == QMediaPlayer.PlaybackState.PlayingState
        from PyQt5.QtMultimedia import QMediaPlayer  # type: ignore

        return self._player.state() == QMediaPlayer.PlayingState

    def _has_trim_range(self) -> bool:
        if self._duration <= 0:
            return False
        return self._start_ms > 0 or not self._end_to_eof

    def _nudge(self, delta_ms: int) -> None:
        if self._player is None or self._duration <= 0:
            return
        pos = max(0, min(self._duration, self._player.position() + delta_ms))
        self._player.setPosition(pos)

    def _on_seek_moved(self, value: int) -> None:
        self._cur_label.setText(ms_to_stamp(value))

    def _on_pos_slider_value(self, value: int) -> None:
        self._cur_label.setText(ms_to_stamp(int(value)))
        if self._player is not None and self._dragging:
            self._player.setPosition(int(value))

    def _on_seek_release(self) -> None:
        self._dragging = False
        self._range_preview = False
        if self._player is not None:
            self._player.setPosition(self._pos_slider.value())

    def _on_start_changed(self, value: int) -> None:
        self._start_ms = int(value)
        if not self._end_to_eof and self._start_ms > self._end_ms:
            self._end_ms = self._start_ms
            self._end_slider.blockSignals(True)
            self._end_slider.setValue(self._end_ms)
            self._end_slider.blockSignals(False)
        self._refresh_range_labels()
        self._emit_range()

    def _on_end_changed(self, value: int) -> None:
        self._end_ms = int(value)
        self._end_to_eof = self._duration > 0 and self._end_ms >= self._duration
        if self._end_ms < self._start_ms:
            self._start_ms = self._end_ms
            self._start_slider.blockSignals(True)
            self._start_slider.setValue(self._start_ms)
            self._start_slider.blockSignals(False)
        self._refresh_range_labels()
        self._emit_range()

    def _on_start_edit_finished(self) -> None:
        text = self._start_edit.text().strip()
        if not text:
            self._start_slider.setValue(0)
            return
        ms = parse_time_to_ms(text)
        if ms is None:
            self._start_edit.setText(ms_to_stamp(self._start_ms))
            return
        if self._duration > 0:
            ms = max(0, min(self._duration, ms))
        self._start_slider.setValue(ms)

    def _on_end_edit_finished(self) -> None:
        text = self._end_edit.text().strip()
        if not text:
            self._end_to_eof = True
            if self._duration > 0:
                self._suppress = True
                self._end_slider.setValue(self._duration)
                self._suppress = False
                self._end_ms = self._duration
            self._refresh_range_labels()
            self._emit_range()
            return
        ms = parse_time_to_ms(text)
        if ms is None:
            if self._end_to_eof:
                self._end_edit.clear()
            else:
                self._end_edit.setText(ms_to_stamp(self._end_ms))
            return
        if self._duration > 0:
            ms = max(0, min(self._duration, ms))
        self._end_to_eof = self._duration > 0 and ms >= self._duration
        self._end_slider.setValue(ms if not self._end_to_eof else self._duration)

    def _mark_in(self) -> None:
        self._start_slider.setValue(self._pos_slider.value())

    def _mark_out(self) -> None:
        self._end_to_eof = False
        self._end_slider.setValue(self._pos_slider.value())

    def _clear_range(self) -> None:
        if self._duration <= 0:
            return
        self._end_to_eof = True
        self._start_slider.setValue(0)
        self._end_slider.setValue(self._duration)

    def _refresh_range_labels(self) -> None:
        self._start_edit.blockSignals(True)
        self._end_edit.blockSignals(True)
        self._start_edit.setText(ms_to_stamp(self._start_ms))
        if self._end_to_eof or (self._duration > 0 and self._end_ms >= self._duration):
            self._end_edit.clear()
            end_disp = "结尾"
        else:
            self._end_edit.setText(ms_to_stamp(self._end_ms))
            end_disp = ms_to_stamp(self._end_ms)
        self._start_edit.blockSignals(False)
        self._end_edit.blockSignals(False)

        if self._start_ms <= 0 and (
            self._end_to_eof or self._duration <= 0 or self._end_ms >= self._duration
        ):
            self._summary.setText("区间：整段（转换全部）")
        else:
            self._summary.setText(f"区间：{ms_to_stamp(self._start_ms)}  →  {end_disp}")
