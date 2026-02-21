"""Main window for BCL Parser application."""
import logging
from datetime import timedelta
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QDateEdit, QMessageBox, QDialog
)
from PyQt6.QtCore import QDate
from PyQt6.QtGui import QMouseEvent
from ..config import Config
from ..database.db_manager import DatabaseManager
from ..utils.date_tracker import DateTracker

logger = logging.getLogger(__name__)


class MainWindow(QMainWindow):
    """Main application window."""
    
    def __init__(self):
        super().__init__()
        self.config = Config()
        self.db_manager = DatabaseManager()
        self.date_tracker = DateTracker(self.db_manager)
        
        self.setWindowTitle("BCL Parser")
        self.setGeometry(100, 100, 600, 400)
        
        self._init_ui()
        self._check_missing_days()
    
    def _init_ui(self):
        """Initialize the user interface."""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        layout = QVBoxLayout()
        central_widget.setLayout(layout)
        
        # Date range selection
        date_layout = QHBoxLayout()
        date_layout.addWidget(QLabel("Date Range:"))
        
        self.date_from = QDateEdit()
        self.date_from.setDate(QDate.currentDate())
        self.date_from.setCalendarPopup(True)
        date_layout.addWidget(QLabel("From:"))
        date_layout.addWidget(self.date_from)
        
        self.date_to = QDateEdit()
        self.date_to.setDate(QDate.currentDate())
        self.date_to.setCalendarPopup(True)
        date_layout.addWidget(QLabel("To:"))
        date_layout.addWidget(self.date_to)
        
        layout.addLayout(date_layout)
        
        # Status label
        self.status_label = QLabel("Ready to parse")
        layout.addWidget(self.status_label)
        
        # Missing days notification
        self.missing_days_label = QLabel()
        self.missing_days_label.setStyleSheet("color: orange;")
        self.missing_days_label.mousePressEvent = self._on_missing_days_clicked
        layout.addWidget(self.missing_days_label)
        
        # Start parsing button
        self.parse_button = QPushButton("Start Parsing")
        self.parse_button.clicked.connect(self._on_start_parsing)
        layout.addWidget(self.parse_button)
        
        # Buttons layout
        buttons_layout = QHBoxLayout()
        
        # Create Table button
        create_table_button = QPushButton("Create Table")
        create_table_button.clicked.connect(self._on_create_table)
        buttons_layout.addWidget(create_table_button)
        
        # Settings button
        settings_button = QPushButton("Settings")
        settings_button.clicked.connect(self._on_settings)
        buttons_layout.addWidget(settings_button)
        
        layout.addLayout(buttons_layout)
    
    def _check_missing_days(self):
        """Check for missing days and display notification."""
        table_name = self.config.default_table
        today = self.date_tracker.get_today()
        
        # Check last 30 days for missing dates
        start_date = today - timedelta(days=30)
        missing = self.date_tracker.check_missing_days(table_name, start_date, today)
        
        if missing:
            self.missing_days_label.setText(
                f"⚠️ {len(missing)} days missed. Click to fill missing days."
            )
            self._has_missing_days = True
        else:
            self.missing_days_label.setText("✅ All days parsed")
            self._has_missing_days = False
    
    def _on_missing_days_clicked(self, event: QMouseEvent):
        """Handle click on missing days label."""
        if self._has_missing_days:
            self._fill_missing_days()
        event.accept()
    
    def _fill_missing_days(self):
        """Fill missing days with parsing."""
        # TODO: Implement missing days filling
        QMessageBox.information(
            self, 
            "Fill Missing Days", 
            "This feature will be implemented in the next phase."
        )
    
    def _on_start_parsing(self):
        """Handle start parsing button click."""
        try:
            logger.info("Start parsing button clicked")
            
            table_name = self.config.default_table
            date_from = self.date_from.date().toPyDate()
            date_to = self.date_to.date().toPyDate()
            
            # Validate date range
            if date_from > date_to:
                QMessageBox.warning(
                    self,
                    "Invalid Date Range",
                    "The 'From' date must be before or equal to the 'To' date."
                )
                return
            
            logger.info(f"Table: {table_name}, Date range: {date_from} to {date_to}")
            
            # Check credentials
            if not self.config.site_username or not self.config.site_password:
                logger.warning("Missing YouScan.io credentials")
                QMessageBox.warning(
                    self,
                    "Missing Credentials",
                    "Please configure YouScan.io credentials in Settings.\n\n"
                    "You can set YOUSCAN_EMAIL and YOUSCAN_PASSWORD environment variables."
                )
                return
            
            if not self.config.google_sheets_id:
                logger.warning("Missing Google Sheets ID")
                QMessageBox.warning(
                    self,
                    "Missing Configuration",
                    "Please configure Google Sheets ID in Settings."
                )
                return
            
            # Open parsing dialog
            logger.info("Opening parsing dialog")
            from .parser_dialog import ParserDialog
            dialog = ParserDialog(
                self,
                self.config,
                self.db_manager,
                self.date_tracker,
                table_name,
                date_from,
                date_to
            )
            dialog.exec()
            
            # Refresh missing days check
            self._check_missing_days()
        except Exception as e:
            logger.exception("Error in _on_start_parsing")
            QMessageBox.critical(
                self,
                "Error",
                f"An error occurred:\n{str(e)}\n\nCheck console for details."
            )
    
    def _on_settings(self):
        """Handle settings button click."""
        from .settings_dialog import SettingsDialog
        dialog = SettingsDialog(self, self.config)
        dialog.exec()
    
    def _on_create_table(self):
        """Handle create table button click."""
        from .create_table_dialog import CreateTableDialog
        dialog = CreateTableDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            created_table = dialog.get_created_table_name()
            if created_table:
                # Update default table to the newly created one
                self.config.default_table = created_table
                logger.info(f"Created new table: {created_table}")

