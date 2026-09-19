"""Bottom-right corner toast (non-modal), works on Win7+."""

from __future__ import annotations

from ui.qtcompat import (
    QT_API,
    AlignTop,
    PointingHandCursor,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTimer,
    QVBoxLayout,
    QWidget,
    Qt,
)


def _window_flags():
    if QT_API == "pyqt6":
        return (
            Qt.WindowType.Tool
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
        )
    return Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint


def _show_without_activating_attr():
    if QT_API == "pyqt6":
        return Qt.WidgetAttribute.WA_ShowWithoutActivating
    return Qt.WA_ShowWithoutActivating


def _translucent_attr():
    if QT_API == "pyqt6":
        return Qt.WidgetAttribute.WA_TranslucentBackground
    return Qt.WA_TranslucentBackground


def _apply_round_mask(widget: QWidget, radius: int = 12) -> None:
    """Clip the native window so all four corners match the stylesheet."""
    if QT_API == "pyqt6":
        from PyQt6.QtCore import QRectF
        from PyQt6.QtGui import QPainterPath, QRegion
    else:
        from PyQt5.QtCore import QRectF  # type: ignore
        from PyQt5.QtGui import QPainterPath, QRegion  # type: ignore

    rect = QRectF(widget.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
    path = QPainterPath()
    path.addRoundedRect(rect, radius, radius)
    widget.setMask(QRegion(path.toFillPolygon().toPolygon()))


class CornerToast(QFrame):
    """Small floating panel at the bottom-right of the primary screen."""

    def __init__(
        self,
        title: str,
        message: str,
        *,
        kind: str = "ok",
        ms: int = 5000,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("cornerToast")
        self.setProperty("kind", kind if kind in {"ok", "error"} else "ok")
        self.setWindowFlags(_window_flags())
        self.setAttribute(_show_without_activating_attr(), True)
        self.setAutoFillBackground(True)
        self.setFixedWidth(340)

        root = QHBoxLayout(self)
        root.setContentsMargins(16, 14, 12, 16)
        root.setSpacing(10)

        icon = QLabel("✓" if kind != "error" else "!")
        icon.setObjectName("cornerToastIcon")
        icon.setProperty("kind", kind if kind in {"ok", "error"} else "ok")
        icon.setAlignment(AlignTop)
        root.addWidget(icon)

        text_col = QVBoxLayout()
        text_col.setContentsMargins(0, 0, 0, 0)
        text_col.setSpacing(4)
        title_lab = QLabel(title)
        title_lab.setObjectName("cornerToastTitle")
        title_lab.setWordWrap(True)
        body = QLabel(message)
        body.setObjectName("cornerToastBody")
        body.setWordWrap(True)
        text_col.addWidget(title_lab)
        text_col.addWidget(body)
        root.addLayout(text_col, 1)

        close_btn = QPushButton("×")
        close_btn.setObjectName("cornerToastClose")
        close_btn.setCursor(PointingHandCursor)
        close_btn.setToolTip("关闭")
        close_btn.clicked.connect(self.close)
        root.addWidget(close_btn, 0, AlignTop)

        for w in (self, icon):
            w.style().unpolish(w)
            w.style().polish(w)

        self.adjustSize()
        # Extra pixels so the bottom border is not clipped by the window.
        self.setFixedHeight(self.sizeHint().height() + 4)
        self._place()
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self.close)
        self._timer.start(max(2000, ms))

    def _place(self) -> None:
        try:
            from ui.qtcompat import QApplication

            qapp = QApplication.instance()
            if qapp is None:
                return
            if hasattr(qapp, "primaryScreen"):
                screen = qapp.primaryScreen()
                if screen is None:
                    return
                geo = screen.availableGeometry()
            elif hasattr(qapp, "desktop"):
                geo = qapp.desktop().availableGeometry()
            else:
                return
            margin = 18
            self.move(
                geo.right() - self.width() - margin,
                geo.bottom() - self.height() - margin,
            )
        except Exception:  # noqa: BLE001
            pass

    def resizeEvent(self, event) -> None:  # noqa: N802, ANN001
        super().resizeEvent(event)
        _apply_round_mask(self, 12)

    def show_toast(self) -> None:
        self.show()
        _apply_round_mask(self, 12)
        self._place()
        self.raise_()


def show_corner_toast(
    title: str,
    message: str,
    *,
    kind: str = "ok",
    ms: int = 5000,
    parent: QWidget | None = None,
) -> CornerToast:
    toast = CornerToast(title, message, kind=kind, ms=ms, parent=parent)
    app = None
    try:
        from ui.qtcompat import QApplication

        app = QApplication.instance()
    except Exception:  # noqa: BLE001
        pass
    if app is not None:
        held = getattr(app, "_corner_toasts", None)
        if held is None:
            held = []
            setattr(app, "_corner_toasts", held)
        held.append(toast)

        def _drop() -> None:
            try:
                held.remove(toast)
            except ValueError:
                pass

        toast.destroyed.connect(_drop)
    toast.show_toast()
    return toast
