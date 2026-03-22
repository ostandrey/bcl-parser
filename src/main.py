"""Main entry point for BCL Parser application."""
import sys
import logging
from pathlib import Path

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


def _build_app_icon() -> QIcon:
    """Generate a branded icon programmatically — no external file needed."""
    sizes = [16, 32, 48, 64, 128, 256]
    icon = QIcon()
    for s in sizes:
        px = QPixmap(s, s)
        px.fill(Qt.GlobalColor.transparent)
        p = QPainter(px)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Background: purple rounded square with subtle gradient
        grad = QLinearGradient(0, 0, s, s)
        grad.setColorAt(0.0, QColor('#7965AF'))
        grad.setColorAt(1.0, QColor('#5B3F96'))
        p.setBrush(grad)
        p.setPen(Qt.PenStyle.NoPen)
        radius = max(4, s // 7)
        p.drawRoundedRect(0, 0, s, s, radius, radius)

        # White "B" letter centered
        p.setPen(QColor('#FFFFFF'))
        font = QFont('Segoe UI', max(6, int(s * 0.48)), QFont.Weight.Bold)
        p.setFont(font)
        p.drawText(QRect(0, 0, s, s), Qt.AlignmentFlag.AlignCenter, 'B')

        p.end()
        icon.addPixmap(px)
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


