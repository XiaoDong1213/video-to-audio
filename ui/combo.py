"""Styled QComboBox popup — matches meeting-nameplate Swiss light dropdowns."""

from __future__ import annotations

from ui.qtcompat import QT_API, QComboBox, QFrame, QTimer, QWidget

if QT_API == "pyqt6":
    from PyQt6.QtCore import QPoint, QSize, Qt
    from PyQt6.QtGui import QColor, QPainter
    from PyQt6.QtWidgets import (
        QListView,
        QStyle,
        QStyledItemDelegate,
        QStyleOptionViewItem,
    )
else:  # pragma: no cover
    from PyQt5.QtCore import QPoint, QSize, Qt  # type: ignore
    from PyQt5.QtGui import QColor, QPainter  # type: ignore
    from PyQt5.QtWidgets import (  # type: ignore
        QListView,
        QStyle,
        QStyledItemDelegate,
        QStyleOptionViewItem,
    )

COMBO_MAX_VISIBLE = 8
_ROW_H = 34
_LIST_PAD = 8
_BOX_CHROME = 4

# Accent aligned with app.qss (#0284C7)
_SELECT_BG = "#0284C7"
_HOVER_BG = "#E0F2FE"
_TEXT = "#0F172A"
_BORDER = "#CBD5E1"

COMBO_POPUP_QSS = """
QListView#comboPopup {
    background: #FFFFFF;
    border: none;
    outline: 0;
    padding: 4px;
}
"""

CONTAINER_QSS = (
    "QFrame, QWidget {"
    "background-color: #FFFFFF;"
    f"border: 1px solid {_BORDER};"
    "border-radius: 8px;"
    "}"
)


class _PlainComboDelegate(QStyledItemDelegate):
    def sizeHint(self, option, index):  # noqa: N802, ANN001
        size = super().sizeHint(option, index)
        return QSize(size.width(), _ROW_H)

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index) -> None:  # noqa: N802, ANN001
        opt = QStyleOptionViewItem(option)
        self.initStyleOption(opt, index)
        painter.save()
        if QT_API == "pyqt6":
            selected = bool(opt.state & QStyle.StateFlag.State_Selected)
            hovered = bool(opt.state & QStyle.StateFlag.State_MouseOver)
            align = int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
        else:
            selected = bool(opt.state & QStyle.State_Selected)
            hovered = bool(opt.state & QStyle.State_MouseOver)
            align = int(Qt.AlignVCenter | Qt.AlignLeft)
        rect = opt.rect.adjusted(2, 1, -2, -1)
        if selected:
            painter.fillRect(rect, QColor(_SELECT_BG))
            color = QColor("#FFFFFF")
        elif hovered:
            painter.fillRect(rect, QColor(_HOVER_BG))
            color = QColor(_TEXT)
        else:
            color = QColor(_TEXT)
        painter.setPen(color)
        painter.drawText(rect.adjusted(12, 0, -8, 0), align, opt.text)
        painter.restore()


class _CappedListView(QListView):
    def __init__(self, combo: QComboBox, parent=None) -> None:  # noqa: ANN001
        super().__init__(parent)
        self._combo = combo

    def sizeHint(self) -> QSize:  # noqa: N802
        rows = max(1, min(self._combo.count(), COMBO_MAX_VISIBLE))
        return QSize(super().sizeHint().width(), rows * _ROW_H + _LIST_PAD)

    def minimumSizeHint(self) -> QSize:  # noqa: N802
        return self.sizeHint()


def _view_h(combo: QComboBox) -> int:
    rows = max(1, min(combo.count(), COMBO_MAX_VISIBLE))
    return rows * _ROW_H + _LIST_PAD


def _popup_h(combo: QComboBox) -> int:
    return _view_h(combo) + _BOX_CHROME


def _kill_popup_arrows(box: QWidget, view: QListView) -> None:
    lay = box.layout()
    if lay is not None:
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        lay.setEnabled(False)
    for ch in box.children():
        if isinstance(ch, QWidget) and ch is not view:
            ch.hide()


def _place_popup(combo: QComboBox, box: QWidget, view: QListView, min_w: int) -> None:
    try:
        w = max(combo.width(), min_w, 120)
        h = _popup_h(combo)
        vh = _view_h(combo)
        fits = combo.count() <= COMBO_MAX_VISIBLE

        if QT_API == "pyqt6":
            box.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
            off = Qt.ScrollBarPolicy.ScrollBarAlwaysOff
            as_needed = Qt.ScrollBarPolicy.ScrollBarAsNeeded
        else:
            box.setAttribute(Qt.WA_StyledBackground, True)
            off = Qt.ScrollBarAlwaysOff
            as_needed = Qt.ScrollBarAsNeeded

        box.setStyleSheet(CONTAINER_QSS)
        view.setStyleSheet(COMBO_POPUP_QSS)

        if fits:
            view.setVerticalScrollBarPolicy(off)
            view.setAutoScroll(False)
            view.verticalScrollBar().setEnabled(False)
            view.verticalScrollBar().setValue(0)
        else:
            view.setVerticalScrollBarPolicy(as_needed)
            view.setAutoScroll(True)
            view.verticalScrollBar().setEnabled(True)

        _kill_popup_arrows(box, view)
        box.setFixedSize(w, h)
        view.setGeometry(1, 1, max(w - 2, 1), vh)
        view.show()
        view.raise_()

        gap = 1
        below = combo.mapToGlobal(QPoint(0, combo.height() + gap))
        screen = combo.screen() if hasattr(combo, "screen") else None
        if screen is not None:
            avail = screen.availableGeometry()
            if below.y() + h > avail.bottom() and combo.mapToGlobal(QPoint(0, 0)).y() - h - gap >= avail.top():
                box.move(combo.mapToGlobal(QPoint(0, -h - gap)))
            else:
                x = min(max(avail.left(), below.x()), avail.right() - w + 1)
                box.move(QPoint(x, below.y()))
        else:
            box.move(below)
    except Exception:  # noqa: BLE001
        pass


def tune_combo(combo: QComboBox, min_w: int = 100) -> None:
    """Uniform popup: blue selection row, rounded chrome, chevron via QSS."""
    combo.setMaxVisibleItems(COMBO_MAX_VISIBLE)
    combo.setMinimumWidth(min_w)
    combo.setMinimumHeight(34)
    avg = max(7, combo.fontMetrics().averageCharWidth())
    combo.setMinimumContentsLength(max(4, (min_w - 40) // avg))
    if QT_API == "pyqt6":
        combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        no_frame = QFrame.Shape.NoFrame
        scroll_off = Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        scroll_need = Qt.ScrollBarPolicy.ScrollBarAsNeeded
        per_item = QListView.ScrollMode.ScrollPerItem
    else:
        combo.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
        no_frame = QFrame.NoFrame
        scroll_off = Qt.ScrollBarAlwaysOff
        scroll_need = Qt.ScrollBarAsNeeded
        per_item = QListView.ScrollPerItem

    view = _CappedListView(combo, combo)
    view.setObjectName("comboPopup")
    view.setFrameShape(no_frame)
    view.setUniformItemSizes(True)
    view.setAlternatingRowColors(False)
    view.setHorizontalScrollBarPolicy(scroll_off)
    view.setVerticalScrollBarPolicy(scroll_need)
    view.setVerticalScrollMode(per_item)
    view.setMinimumWidth(max(min_w, 120))
    view.setItemDelegate(_PlainComboDelegate(view))
    view.setStyleSheet(COMBO_POPUP_QSS)
    combo.setView(view)

    def show_popup() -> None:
        view.setMaximumHeight(_view_h(combo))
        QComboBox.showPopup(combo)

        def polish() -> None:
            box = view.window()
            if box is not None:
                _place_popup(combo, box, view, min_w)

        QTimer.singleShot(0, polish)

    combo.showPopup = show_popup  # type: ignore[method-assign]
