"""Main entry point for BCL Parser application."""
import sys
import logging
from pathlib import Path

# ── Windows taskbar fix ────────────────────────────────────────────────────────
# Without this, Windows shows the Python interpreter icon in the taskbar
# instead of our app icon when running as a script.
if sys.platform == 'win32':
    import ctypes
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID('BCL.Parser.App')

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Configure logging — INFO in production, DEBUG only when needed
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('bcl_parser.log', encoding='utf-8'),
    ]
)
logger = logging.getLogger(__name__)

from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QIcon, QPixmap, QPainter, QColor, QFont, QLinearGradient
from PyQt6.QtCore import Qt, QRect
from src.gui.main_window import MainWindow


_ICON_PATH = project_root / 'assets' / 'icon.ico'


def _build_app_icon() -> QIcon:
    """Generate a branded icon. Saves icon.ico on first run for PyInstaller."""
    # Prefer pre-saved .ico (faster, works in frozen exe)
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
        radius = max(4, s // 7)
        p.drawRoundedRect(0, 0, s, s, radius, radius)

        p.setPen(QColor('#FFFFFF'))
        font = QFont('Segoe UI', max(6, int(s * 0.48)), QFont.Weight.Bold)
        p.setFont(font)
        p.drawText(QRect(0, 0, s, s), Qt.AlignmentFlag.AlignCenter, 'B')
        p.end()

        icon.addPixmap(px)
        if s == 256:
            largest_px = px

    # Save as .ico so PyInstaller can embed it (done once, silently)
    try:
        _ICON_PATH.parent.mkdir(parents=True, exist_ok=True)
        if largest_px:
            largest_px.save(str(_ICON_PATH), 'ICO')
    except Exception:
        pass

    return icon


def main():
    """Run the BCL Parser application."""
    try:
        logger.info("Starting BCL Parser application")
        app = QApplication(sys.argv)
        app.setApplicationName("BCL Parser")
        app.setWindowIcon(_build_app_icon())
        
        logger.info("Creating main window")
        window = MainWindow()
        window.show()
        
        logger.info("Application started successfully")
        sys.exit(app.exec())
    except Exception as e:
        logger.exception("Fatal error in application: %s", e)
        sys.exit(1)


if __name__ == '__main__':
    main()


