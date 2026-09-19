"""
Qt 兼容层：优先 PyQt6（64 位），回退 PyQt5（32 位老系统）。
"""

from __future__ import annotations

import sys

QT_API: str

try:
    from PyQt6.QtCore import Qt, QThread, QTimer, QUrl, pyqtSignal
    from PyQt6.QtGui import QIcon
    from PyQt6.QtWidgets import (
        QApplication,
        QButtonGroup,
        QCheckBox,
        QComboBox,
        QDialog,
        QDialogButtonBox,
        QFileDialog,
        QFrame,
        QGridLayout,
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
        QSlider,
        QStatusBar,
        QVBoxLayout,
        QWidget,
    )

    QT_API = "pyqt6"

    AlignLeft = Qt.AlignmentFlag.AlignLeft
    AlignCenter = Qt.AlignmentFlag.AlignCenter
    AlignVCenter = Qt.AlignmentFlag.AlignVCenter
    AlignRight = Qt.AlignmentFlag.AlignRight
    AlignTop = Qt.AlignmentFlag.AlignTop
    PointingHandCursor = Qt.CursorShape.PointingHandCursor
    ExtendedSelection = QListWidget.SelectionMode.ExtendedSelection
    Horizontal = Qt.Orientation.Horizontal
    DialogAccepted = QDialog.DialogCode.Accepted
    LeftToRight = QListWidget.Flow.LeftToRight
    TopToBottom = QListWidget.Flow.TopToBottom
    ScrollBarAlwaysOff = Qt.ScrollBarPolicy.ScrollBarAlwaysOff
    ScrollBarAsNeeded = Qt.ScrollBarPolicy.ScrollBarAsNeeded
    ScrollBarAlwaysOn = Qt.ScrollBarPolicy.ScrollBarAlwaysOn

    def app_exec(app: QApplication) -> int:
        return app.exec()

    def geometry_to_hex(widget) -> str:  # noqa: ANN001
        return bytes(widget.saveGeometry().data()).hex()

    def geometry_from_hex(widget, hex_str: str) -> None:  # noqa: ANN001
        widget.restoreGeometry(bytes.fromhex(hex_str))

except ImportError:  # pragma: no cover
    from PyQt5.QtCore import QByteArray, Qt, QThread, QTimer, QUrl, pyqtSignal  # type: ignore
    from PyQt5.QtGui import QIcon  # type: ignore
    from PyQt5.QtWidgets import (  # type: ignore
        QApplication,
        QButtonGroup,
        QCheckBox,
        QComboBox,
        QDialog,
        QDialogButtonBox,
        QFileDialog,
        QFrame,
        QGridLayout,
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
        QSlider,
        QStatusBar,
        QVBoxLayout,
        QWidget,
    )

    QT_API = "pyqt5"

    AlignLeft = Qt.AlignLeft
    AlignCenter = Qt.AlignCenter
    AlignVCenter = Qt.AlignVCenter
    AlignRight = Qt.AlignRight
    AlignTop = Qt.AlignTop
    PointingHandCursor = Qt.PointingHandCursor
    ExtendedSelection = QListWidget.ExtendedSelection
    Horizontal = Qt.Horizontal
    DialogAccepted = QDialog.Accepted
    LeftToRight = QListWidget.LeftToRight
    TopToBottom = QListWidget.TopToBottom
    ScrollBarAlwaysOff = Qt.ScrollBarAlwaysOff
    ScrollBarAsNeeded = Qt.ScrollBarAsNeeded
    ScrollBarAlwaysOn = Qt.ScrollBarAlwaysOn

    def app_exec(app: QApplication) -> int:
        return app.exec_()

    def geometry_to_hex(widget) -> str:  # noqa: ANN001
        return bytes(widget.saveGeometry().data()).hex()

    def geometry_from_hex(widget, hex_str: str) -> None:  # noqa: ANN001
        widget.restoreGeometry(QByteArray(bytes.fromhex(hex_str)))


def is_64bit() -> bool:
    return sys.maxsize > 2**32


def load_media_player():
    """Return (QMediaPlayer, QVideoWidget, bind_fn) or raise ImportError."""
    if QT_API == "pyqt6":
        from PyQt6.QtMultimedia import QAudioOutput, QMediaPlayer
        from PyQt6.QtMultimediaWidgets import QVideoWidget

        def bind(player: QMediaPlayer, video: QVideoWidget, path: str) -> None:
            audio = QAudioOutput(player)
            player.setAudioOutput(audio)
            player.setVideoOutput(video)
            player.setSource(QUrl.fromLocalFile(path))

        return QMediaPlayer, QVideoWidget, bind

    from PyQt5.QtMultimedia import QMediaContent, QMediaPlayer  # type: ignore
    from PyQt5.QtMultimediaWidgets import QVideoWidget  # type: ignore

    def bind(player: QMediaPlayer, video: QVideoWidget, path: str) -> None:
        player.setVideoOutput(video)
        player.setMedia(QMediaContent(QUrl.fromLocalFile(path)))

    return QMediaPlayer, QVideoWidget, bind


__all__ = [
    "QT_API",
    "Qt",
    "QThread",
    "QTimer",
    "QUrl",
    "pyqtSignal",
    "QIcon",
    "QApplication",
    "QButtonGroup",
    "QCheckBox",
    "QComboBox",
    "QDialog",
    "QDialogButtonBox",
    "QFileDialog",
    "QFrame",
    "QGridLayout",
    "QHBoxLayout",
    "QLabel",
    "QLineEdit",
    "QListWidget",
    "QListWidgetItem",
    "QMainWindow",
    "QMessageBox",
    "QPlainTextEdit",
    "QProgressBar",
    "QPushButton",
    "QSlider",
    "QStatusBar",
    "QVBoxLayout",
    "QWidget",
    "AlignLeft",
    "AlignCenter",
    "AlignVCenter",
    "AlignRight",
    "AlignTop",
    "PointingHandCursor",
    "ExtendedSelection",
    "Horizontal",
    "DialogAccepted",
    "LeftToRight",
    "TopToBottom",
    "ScrollBarAlwaysOff",
    "ScrollBarAsNeeded",
    "ScrollBarAlwaysOn",
    "app_exec",
    "geometry_to_hex",
    "geometry_from_hex",
    "is_64bit",
    "load_media_player",
]
