"""应用入口：无参数启动 GUI；带 CLI 子命令则走命令行。"""

from __future__ import annotations

import logging
import os
import sys
import traceback
from pathlib import Path


def _set_windows_app_id() -> None:
    if os.name != "nt":
        return
    try:
        import ctypes

        from app.identity import APP_USER_MODEL_ID

        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APP_USER_MODEL_ID)
    except Exception:  # noqa: BLE001
        pass


def _ensure_cwd() -> None:
    from core.paths import project_root

    try:
        os.chdir(project_root())
    except OSError:
        pass


def _crash_log_path() -> Path:
    from core.paths import data_dir

    return data_dir() / "crash.log"


def _install_excepthook() -> None:
    def hook(exc_type, exc, tb) -> None:
        text = "".join(traceback.format_exception(exc_type, exc, tb))
        logging.error("Uncaught exception:\n%s", text)
        try:
            _crash_log_path().write_text(text, encoding="utf-8")
        except OSError:
            pass
        sys.__excepthook__(exc_type, exc, tb)
        try:
            from ui.qtcompat import QApplication, QMessageBox

            if QApplication.instance() is not None:
                QMessageBox.critical(
                    None,
                    "程序异常",
                    f"发生未处理错误，详情已写入 crash.log：\n{exc}",
                )
        except Exception:  # noqa: BLE001
            pass

    sys.excepthook = hook


def _prepare_high_dpi() -> None:
    """Must run before Qt is imported. PyQt5 otherwise draws at 96 DPI on scaled displays."""
    os.environ.setdefault("QT_ENABLE_HIGHDPI_SCALING", "1")
    os.environ.setdefault("QT_AUTO_SCREEN_SCALE_FACTOR", "1")


def _enable_qt5_high_dpi(qt_api: str, application_cls, qt_namespace) -> None:  # noqa: ANN001
    if qt_api != "pyqt5":
        return
    application_cls.setAttribute(qt_namespace.AA_EnableHighDpiScaling, True)
    application_cls.setAttribute(qt_namespace.AA_UseHighDpiPixmaps, True)
    policy = getattr(qt_namespace, "HighDpiScaleFactorRoundingPolicy", None)
    setter = getattr(application_cls, "setHighDpiScaleFactorRoundingPolicy", None)
    if policy is not None and setter is not None:
        setter(policy.PassThrough)


def _run_gui() -> int:
    _prepare_high_dpi()
    from ui.qtcompat import QT_API, QApplication, Qt, app_exec

    _enable_qt5_high_dpi(QT_API, QApplication, Qt)

    from app.i18n import install_qt_zh
    from app.identity import APP_NAME, APP_VERSION
    from core.paths import load_app_icon, load_app_stylesheet
    from ui.main_window import MainWindow

    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(APP_VERSION)
    if hasattr(app, "setApplicationDisplayName"):
        app.setApplicationDisplayName(APP_NAME)
    app.setStyle("Fusion")
    install_qt_zh(app)
    app.setStyleSheet(load_app_stylesheet())

    app_icon = load_app_icon()
    if not app_icon.isNull():
        app.setWindowIcon(app_icon)

    logging.info("Qt API: %s", QT_API)
    window = MainWindow()
    if not app_icon.isNull():
        window.setWindowIcon(app_icon)
    window.show()
    return app_exec(app)


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    _install_excepthook()
    _set_windows_app_id()
    _ensure_cwd()

    args = list(sys.argv[1:] if argv is None else argv)

    if not args or args[0] in {"gui", "--gui"}:
        return _run_gui()

    from app.cli import app as cli_app

    sys.argv = [sys.argv[0], *args]
    try:
        cli_app()
    except SystemExit as exc:
        code = exc.code
        return int(code) if isinstance(code, int) else (0 if code is None else 1)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
