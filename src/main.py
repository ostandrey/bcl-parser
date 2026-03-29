"""Main entry point for BCL Parser application."""
import os
import sys
import logging
import subprocess
from pathlib import Path

# ── Windows taskbar fix ────────────────────────────────────────────────────────
if sys.platform == 'win32':
    import ctypes
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID('BCL.Parser.App')

# ── Playwright frozen-exe fix ──────────────────────────────────────────────────
# Always store browsers in the user's AppData — works both as script and exe.
_BROWSERS_PATH = Path(os.environ.get('LOCALAPPDATA', Path.home())) / 'ms-playwright'
os.environ['PLAYWRIGHT_BROWSERS_PATH'] = str(_BROWSERS_PATH)

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('bcl_parser.log', encoding='utf-8'),
    ]
)
logger = logging.getLogger(__name__)

from PyQt6.QtWidgets import QApplication, QDialog, QVBoxLayout, QLabel, QProgressBar, QMessageBox
from PyQt6.QtGui import QIcon, QPixmap, QPainter, QColor, QFont, QLinearGradient
from PyQt6.QtCore import Qt, QRect, QThread, pyqtSignal

_ICON_PATH = project_root / 'assets' / 'icon.ico'


# ── App icon ───────────────────────────────────────────────────────────────────

def _build_app_icon() -> QIcon:
    if _ICON_PATH.exists():
        return QIcon(str(_ICON_PATH))

    sizes = [16, 32, 48, 64, 128, 256]
    icon = QIcon()
    largest_px = None
    for s in sizes:
        px = QPixmap(s, s)
        px.fill(Qt.GlobalColor.transparent)
        p = QPainter(px)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        grad = QLinearGradient(0, 0, s, s)
        grad.setColorAt(0.0, QColor('#7965AF'))
        grad.setColorAt(1.0, QColor('#5B3F96'))
        p.setBrush(grad)
        p.setPen(Qt.PenStyle.NoPen)
        p.drawRoundedRect(0, 0, s, s, max(4, s // 7), max(4, s // 7))
        p.setPen(QColor('#FFFFFF'))
        p.setFont(QFont('Segoe UI', max(6, int(s * 0.48)), QFont.Weight.Bold))
        p.drawText(QRect(0, 0, s, s), Qt.AlignmentFlag.AlignCenter, 'B')
        p.end()
        icon.addPixmap(px)
        if s == 256:
            largest_px = px
    try:
        _ICON_PATH.parent.mkdir(parents=True, exist_ok=True)
        if largest_px:
            largest_px.save(str(_ICON_PATH), 'ICO')
    except Exception:
        pass
    return icon


# ── Playwright browser setup ───────────────────────────────────────────────────

def _chromium_installed() -> bool:
    """Return True if Playwright Chromium binaries exist."""
    return bool(list(_BROWSERS_PATH.glob('chromium-*')))


class _BrowserInstallThread(QThread):
    done    = pyqtSignal(bool, str)   # success, error_message

    def run(self):
        try:
            from playwright._impl._driver import compute_driver_executable
            driver = compute_driver_executable()
            result = subprocess.run(
                [str(driver), 'install', 'chromium'],
                capture_output=True, text=True, timeout=600,
            )
            if result.returncode == 0:
                self.done.emit(True, '')
            else:
                self.done.emit(False, result.stderr or result.stdout)
        except Exception as e:
            self.done.emit(False, str(e))


def _ensure_browser(app_icon: QIcon) -> bool:
    """If Chromium is missing, show a setup dialog and install it. Returns False on failure."""
    if _chromium_installed():
        return True

    # ── Setup dialog ──────────────────────────────────────────────────────────
    dlg = QDialog()
    dlg.setWindowTitle('BCL Parser — First Run Setup')
    dlg.setWindowIcon(app_icon)
    dlg.setFixedSize(420, 170)
    dlg.setWindowFlags(
        dlg.windowFlags()
        & ~Qt.WindowType.WindowCloseButtonHint
        & ~Qt.WindowType.WindowContextHelpButtonHint
    )
    dlg.setStyleSheet("""
        QDialog { background: #FEF7FF; font-family: 'Segoe UI'; }
        QLabel  { color: #1C1B1F; font-size: 10pt; background: transparent; border: none; }
        QProgressBar {
            border: none; border-radius: 5px; height: 8px;
            background: #E8DEF8;
        }
        QProgressBar::chunk { background: #6750A4; border-radius: 5px; }
    """)

    lay = QVBoxLayout(dlg)
    lay.setContentsMargins(32, 28, 32, 28)
    lay.setSpacing(16)

    title = QLabel('🔧  First-time setup')
    title.setStyleSheet('font-size: 13pt; font-weight: 700; color: #6750A4; background: transparent; border: none;')
    lay.addWidget(title)

    info = QLabel('Downloading Chromium browser (~150 MB).\nThis happens only once.')
    info.setWordWrap(True)
    lay.addWidget(info)

    bar = QProgressBar()
    bar.setRange(0, 0)   # indeterminate spinner
    bar.setFixedHeight(8)
    lay.addWidget(bar)

    result: dict = {'ok': False, 'err': ''}

    thread = _BrowserInstallThread()

    def _on_done(ok: bool, err: str):
        result['ok'] = ok
        result['err'] = err
        dlg.accept()

    thread.done.connect(_on_done)
    thread.start()
    dlg.exec()

    if not result['ok']:
        QMessageBox.critical(
            None, 'Setup Failed',
            f'Could not download Chromium:\n\n{result["err"]}\n\n'
            'Please run manually:\n  playwright install chromium',
        )
        return False

    return True


# ── Entry point ────────────────────────────────────────────────────────────────

def main():
    try:
        logger.info("Starting BCL Parser")
        app = QApplication(sys.argv)
        app.setApplicationName("BCL Parser")

        icon = _build_app_icon()
        app.setWindowIcon(icon)

        if not _ensure_browser(icon):
            sys.exit(1)

        from src.gui.main_window import MainWindow
        window = MainWindow()
        window.show()

        sys.exit(app.exec())
    except Exception as e:
        logger.exception("Fatal error: %s", e)
        sys.exit(1)


if __name__ == '__main__':
    main()
