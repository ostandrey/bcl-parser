"""Dialog for creating new Google Sheets tables."""
import logging
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton,
    QLabel, QLineEdit, QComboBox, QMessageBox
)
from PyQt6.QtCore import Qt
from ..sheets.google_sheets import GoogleSheetsWriter
from ..config import Config, TABLE_NAME_PATTERNS

logger = logging.getLogger(__name__)


class CreateTableDialog(QDialog):
    """Dialog for creating a new table in Google Sheets."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.config = Config()
        self.sheets_writer = None
        self.created_table_name = None
        
        self.setWindowTitle("Create New Table")
        self.setGeometry(200, 200, 400, 200)
        
        self._init_ui()
    
    def _init_ui(self):
        """Initialize the user interface."""
        layout = QVBoxLayout()
        self.setLayout(layout)
        
        # Instructions
        info_label = QLabel(
            "Create a new table (sheet) in Google Sheets.\n"
            "You can choose a template or enter a custom name."
        )
        info_label.setWordWrap(True)
        layout.addWidget(info_label)
        
        # Table type selection
        type_layout = QHBoxLayout()
        type_layout.addWidget(QLabel("Table Type:"))
        self.type_combo = QComboBox()
        self.type_combo.addItems(["Social Network", "Media", "Custom"])
        self.type_combo.currentTextChanged.connect(self._on_type_changed)
        type_layout.addWidget(self.type_combo)
        layout.addLayout(type_layout)
        
        # Year selection
        year_layout = QHBoxLayout()
        year_layout.addWidget(QLabel("Year:"))
        self.year_combo = QComboBox()
        from datetime import date
        current_year = date.today().year
        # Add years from 2020 to 2030
        for year in range(2020, 2031):
            self.year_combo.addItem(str(year))
        self.year_combo.setCurrentText(str(current_year))
        self.year_combo.currentTextChanged.connect(self._on_year_changed)
        year_layout.addWidget(self.year_combo)
        layout.addLayout(year_layout)
        
        # Custom name input
        name_layout = QHBoxLayout()
        name_layout.addWidget(QLabel("Table Name:"))
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("Enter table name or use template")
        self.name_input.textChanged.connect(self._on_name_changed)
        name_layout.addWidget(self.name_input)
        layout.addLayout(name_layout)
        
        # Preview label
        self.preview_label = QLabel()
        self.preview_label.setStyleSheet("color: gray; font-style: italic;")
        layout.addWidget(self.preview_label)
        
        # Buttons
        button_layout = QHBoxLayout()
        
        self.create_button = QPushButton("Create Table")
        self.create_button.setDefault(True)
        self.create_button.clicked.connect(self._on_create)
        button_layout.addWidget(self.create_button)
        
        cancel_button = QPushButton("Cancel")
        cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(cancel_button)
        
        layout.addLayout(button_layout)
        
        # Initialize preview
        self._update_preview()
    
    def _on_type_changed(self, text):
        """Handle table type change."""
        self._update_preview()
    
    def _on_year_changed(self, text):
        """Handle year change."""
        self._update_preview()
    
    def _on_name_changed(self, text):
        """Handle name input change."""
        # If user is typing custom name, switch to custom type
        if text and text != self._get_template_name():
            self.type_combo.blockSignals(True)
            self.type_combo.setCurrentText("Custom")
            self.type_combo.blockSignals(False)
        self._update_preview()
    
    def _get_template_name(self):
        """Get template name based on selected type and year."""
        table_type = self.type_combo.currentText()
        year = self.year_combo.currentText()
        
        if table_type == "Social Network":
            return TABLE_NAME_PATTERNS['social_network'].format(YEAR=year)
        elif table_type == "Media":
            return TABLE_NAME_PATTERNS['media'].format(YEAR=year)
        else:
            return self.name_input.text() or ""
    
    def _update_preview(self):
        """Update preview label."""
        template_name = self._get_template_name()
        custom_name = self.name_input.text()
        
        if self.type_combo.currentText() == "Custom" and custom_name:
            preview_text = f"Will create: {custom_name}"
            self.name_input.setText(custom_name)
        else:
            preview_text = f"Will create: {template_name}"
            if not self.name_input.text() or self.name_input.text() == template_name:
                self.name_input.setText(template_name)
        
        self.preview_label.setText(preview_text)
    
    def _on_create(self):
        """Handle create button click."""
        table_name = self.name_input.text().strip()
        
        if not table_name:
            QMessageBox.warning(self, "Invalid Name", "Please enter a table name.")
            return
        
        # Check Google Sheets configuration
        if not self.config.google_sheets_id:
            QMessageBox.warning(
                self,
                "Missing Configuration",
                "Please configure Google Sheets ID in Settings."
            )
            return
        
        try:
            # Connect to Google Sheets
            if not self.sheets_writer:
                self.sheets_writer = GoogleSheetsWriter(self.config.google_sheets_id)
                self.sheets_writer.connect()
            
            # Create the sheet
            self.sheets_writer.create_sheet(table_name)
            
            self.created_table_name = table_name
            QMessageBox.information(
                self,
                "Success",
                f"Table '{table_name}' created successfully!"
            )
            self.accept()
            
        except Exception as e:
            logger.error(f"Failed to create table: {e}")
            QMessageBox.critical(
                self,
                "Error",
                f"Failed to create table:\n{str(e)}"
            )
    
    def get_created_table_name(self):
        """Get the name of the created table."""
        return self.created_table_name
