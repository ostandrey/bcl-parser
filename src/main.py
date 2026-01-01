"""Main entry point for BCL Parser application."""
import sys
import logging
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),  # Console output
        logging.FileHandler('bcl_parser.log', encoding='utf-8')  # File log
    ]
)
logger = logging.getLogger(__name__)

from PyQt6.QtWidgets import QApplication, QMessageBox
from src.gui.main_window import MainWindow


def main():
    """Run the BCL Parser application."""
    try:
        logger.info("Starting BCL Parser application")
        app = QApplication(sys.argv)
        app.setApplicationName("BCL Parser")
        
        logger.info("Creating main window")
        window = MainWindow()
        window.show()
        
        logger.info("Application started successfully")
        sys.exit(app.exec())
    except Exception as e:
        logger.exception("Fatal error in application")
        print(f"\n{'='*60}")
        print(f"FATAL ERROR: {e}")
        print(f"{'='*60}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()


