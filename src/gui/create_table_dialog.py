"""Dialog for creating new Google Sheets tables."""
import logging
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton,
    QLabel, QLineEdit, QComboBox, QMessageBox, QGroupBox
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from ..sheets.google_sheets import GoogleSheetsWriter
from ..config import Config, TABLE_NAME_PATTERNS
from .theme import COLORS, COMBO_STYLE, INPUT_STYLE, GROUP_BOX_STYLE

logger = logging.getLogger(__name__)


class CreateTableDialog(QDialog):
    """Dialog for creating a new table in Google Sheets."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.config = Config()
        self.sheets_writer = None
        self.created_table_name = None
        
        self.setWindowTitle("Create New Table")
        self.setGeometry(200, 200, 500, 400)
        
        self._apply_styles()
        self._init_ui()
    
    def _apply_styles(self):
        """Apply dialog-wide styles."""
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {COLORS['background']};
            }}
            QWidget {{
                font-family: 'Segoe UI', 'Arial', sans-serif;
                font-size: 10pt;
            }}
        """)
    
    def _init_ui(self):
        """Initialize the user interface."""
        layout = QVBoxLayout()
        layout.setSpacing(8)
        layout.setContentsMargins(12, 12, 12, 12)
        self.setLayout(layout)
        
        # Header
        header_label = QLabel("Create New Table")
        header_font = QFont()
        header_font.setPointSize(18)
        header_font.setBold(True)
        header_label.setFont(header_font)
        header_label.setStyleSheet(f"color: {COLORS['on_surface']}; margin-bottom: 5px;")
        layout.addWidget(header_label)
        
        # Instructions
        info_label = QLabel(
            "Create a new table (sheet) in Google Sheets.\n"
            "You can choose a template or enter a custom name."
        )
        info_label.setWordWrap(True)
        info_label.setStyleSheet(f"color: {COLORS['on_surface_variant']}; padding: 12px; background-color: {COLORS['surface']}; border-radius: 8px;")
        layout.addWidget(info_label)
        
        # Table configuration group
        config_group = QGroupBox("Table Configuration")
        config_group.setStyleSheet(GROUP_BOX_STYLE)
        config_layout = QVBoxLayout()
        config_layout.setSpacing(6)
        config_layout.setContentsMargins(10, 8, 10, 10)
        
        # Table type selection
        type_layout = QHBoxLayout()
        type_layout.setSpacing(10)
        type_label = QLabel("Table Type:")
        type_label.setStyleSheet(f"color: {COLORS['on_surface_variant']}; font-weight: 500; font-size: 11pt; min-width: 100px;")
        type_layout.addWidget(type_label)
        # Material Design 3 Filled Dropdown
        self.type_combo = QComboBox()
        self.type_combo.addItems(["Social Network", "Media", "Custom"])
        self.type_combo.currentTextChanged.connect(self._on_type_changed)
        self.type_combo.setStyleSheet(COMBO_STYLE)
        type_layout.addWidget(self.type_combo)
        type_layout.addStretch()
        config_layout.addLayout(type_layout)
        
        # Year selection
        year_layout = QHBoxLayout()
        year_layout.setSpacing(10)
        year_label = QLabel("Year:")
        year_label.setStyleSheet(f"color: {COLORS['on_surface_variant']}; font-weight: 500; font-size: 11pt; min-width: 100px;")
        year_layout.addWidget(year_label)
        # Material Design 3 Filled Dropdown
        self.year_combo = QComboBox()
        from datetime import date
        current_year = date.today().year
        # Add years from 2020 to 2030
        for year in range(2020, 2031):
            self.year_combo.addItem(str(year))
        self.year_combo.setCurrentText(str(current_year))
        self.year_combo.currentTextChanged.connect(self._on_year_changed)
        self.year_combo.setStyleSheet(COMBO_STYLE)
        year_layout.addWidget(self.year_combo)
        year_layout.addStretch()
        config_layout.addLayout(year_layout)
        
        # Custom name input
        name_layout = QHBoxLayout()
        name_layout.setSpacing(10)
        name_label = QLabel("Table Name:")
        name_label.setStyleSheet(f"color: {COLORS['on_surface_variant']}; font-weight: 500; font-size: 11pt; min-width: 100px;")
        name_layout.addWidget(name_label)
        # Material Design 3 Filled Text Field
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("Enter table name or use template")
        self.name_input.textChanged.connect(self._on_name_changed)
        self.name_input.setStyleSheet(INPUT_STYLE)
        name_layout.addWidget(self.name_input)
        config_layout.addLayout(name_layout)
        
        config_group.setLayout(config_layout)
        layout.addWidget(config_group)
        
        # Preview label
        self.preview_label = QLabel()
        self.preview_label.setStyleSheet(f"""
            color: {COLORS['on_surface']};
            font-style: italic;
            padding: 10px;
            background-color: {COLORS['background']};
            border-radius: 6px;
            border: 1px solid {COLORS['outline_variant']};
        """)
        layout.addWidget(self.preview_label)
        
        # Buttons
        button_layout = QHBoxLayout()
        button_layout.setSpacing(10)
        
        cancel_button = QPushButton("Cancel")
        cancel_button.clicked.connect(self.reject)
        cancel_button.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLORS['surface']};
                color: {COLORS['on_surface']};
                border: none;
                box-shadow: 0px 2px 8px {COLORS['shadow']};
                border-radius: 6px;
                padding: 10px 24px;
                font-weight: 500;
            }}
            QPushButton:hover {{
                background-color: {COLORS['background']};
                border-color: {COLORS['secondary']};
            }}
        """)
        button_layout.addWidget(cancel_button)
        
        button_layout.addStretch()
        
        self.create_button = QPushButton("✨ Create Table")
        self.create_button.setDefault(True)
        self.create_button.clicked.connect(self._on_create)
        self.create_button.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLORS['primary']};
                color: white;
                border: none;
                border-radius: 6px;
                padding: 10px 24px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: {COLORS['primary']};
            }}
        """)
        button_layout.addWidget(self.create_button)
        
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
