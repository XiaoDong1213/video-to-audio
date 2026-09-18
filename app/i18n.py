"""Install Qt Chinese translations for built-in dialogs."""

from __future__ import annotations

from pathlib import Path

from core.paths import resource_dir
from ui.qtcompat import QT_API, QApplication


def install_qt_zh(app: QApplication) -> None:
    try:
        if QT_API == "pyqt6":
            from PyQt6.QtCore import QLibraryInfo, QLocale, QTranslator
        else:
            from PyQt5.QtCore import QLibraryInfo, QLocale, QTranslator  # type: ignore
    except ImportError:
        return

    locale = QLocale(QLocale.Language.Chinese, QLocale.Country.China) if QT_API == "pyqt6" else QLocale(QLocale.Chinese, QLocale.China)
    QLocale.setDefault(locale)

    dirs: list[Path] = [resource_dir() / "translations"]
    try:
        if QT_API == "pyqt6":
            qt_dir = QLibraryInfo.path(QLibraryInfo.LibraryPath.TranslationsPath)
        else:
            qt_dir = QLibraryInfo.location(QLibraryInfo.TranslationsPath)
        if qt_dir:
            dirs.append(Path(qt_dir))
    except Exception:  # noqa: BLE001
        pass

    try:
        if QT_API == "pyqt6":
            import PyQt6 as qt_mod
        else:
            import PyQt5 as qt_mod  # type: ignore
        base = Path(qt_mod.__file__).resolve().parent
        dirs.append(base / "Qt6" / "translations")
        dirs.append(base / "Qt5" / "translations")
    except Exception:  # noqa: BLE001
        pass

    for stem in ("qtbase_zh_CN", "qt_zh_CN"):
        translator = QTranslator(app)
        for folder in dirs:
            if translator.load(stem, str(folder)):
                app.installTranslator(translator)
                break
