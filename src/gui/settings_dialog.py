"""Settings dialog for configuration."""
import logging
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton,
    QLabel, QLineEdit, QMessageBox
)
from ..config import Config

logger = logging.getLogger(__name__)


class SettingsDialog(QDialog):
    """Settings dialog for application configuration."""
    
    def __init__(self, parent, config: Config):
        super().__init__(parent)
        self.config = config
        self.setWindowTitle("Settings")
        self.setMinimumSize(400, 300)
        self._init_ui()
        self._load_settings()
    
    def _init_ui(self):
        """Initialize UI."""
        layout = QVBoxLayout()
        self.setLayout(layout)
        
        # YouScan.io credentials
        youscan_layout = QVBoxLayout()
        youscan_label = QLabel("YouScan.io Credentials:")
        youscan_label.setStyleSheet("font-weight: bold;")
        youscan_layout.addWidget(youscan_label)
        
        email_layout = QHBoxLayout()
        email_layout.addWidget(QLabel("Email:"))
        self.email_input = QLineEdit()
        self.email_input.setPlaceholderText("Or set YOUSCAN_EMAIL env variable")
        email_layout.addWidget(self.email_input)
        youscan_layout.addLayout(email_layout)
        
        password_layout = QHBoxLayout()
        password_layout.addWidget(QLabel("Password:"))
        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.password_input.setPlaceholderText("Or set YOUSCAN_PASSWORD env variable")
        password_layout.addWidget(self.password_input)
        youscan_layout.addLayout(password_layout)
        
        layout.addLayout(youscan_layout)
        
        # Google Sheets
        sheets_layout = QVBoxLayout()
        sheets_label = QLabel("Google Sheets:")
        sheets_label.setStyleSheet("font-weight: bold;")
        sheets_layout.addWidget(sheets_label)
        
        sheets_id_layout = QHBoxLayout()
        sheets_id_layout.addWidget(QLabel("Spreadsheet ID:"))
        self.sheets_id_input = QLineEdit()
        self.sheets_id_input.setPlaceholderText("From Google Sheets URL")
        sheets_id_layout.addWidget(self.sheets_id_input)
        sheets_layout.addLayout(sheets_id_layout)
        
        sheets_email_layout = QHBoxLayout()
        sheets_email_layout.addWidget(QLabel("Google Email:"))
        self.sheets_email_input = QLineEdit()
        self.sheets_email_input.setPlaceholderText("Or set GOOGLE_SHEETS_EMAIL env variable")
        sheets_email_layout.addWidget(self.sheets_email_input)
        sheets_layout.addLayout(sheets_email_layout)
        
        sheets_password_layout = QHBoxLayout()
        sheets_password_layout.addWidget(QLabel("Google Password:"))
        self.sheets_password_input = QLineEdit()
        self.sheets_password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.sheets_password_input.setPlaceholderText("Or set GOOGLE_SHEETS_PASSWORD env variable")
        sheets_password_layout.addWidget(self.sheets_password_input)
        sheets_layout.addLayout(sheets_password_layout)
        
        layout.addLayout(sheets_layout)
        
        layout.addStretch()
        
        # Info label
        info_label = QLabel(
            "Note: Credentials can also be set via environment variables:\n"
            "YOUSCAN_EMAIL, YOUSCAN_PASSWORD\n"
            "GOOGLE_SHEETS_EMAIL, GOOGLE_SHEETS_PASSWORD"
        )
        info_label.setWordWrap(True)
        info_label.setStyleSheet("color: gray; font-size: 9pt;")
        layout.addWidget(info_label)
        
        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        cancel_button = QPushButton("Cancel")
        cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(cancel_button)
        
        save_button = QPushButton("Save")
        save_button.clicked.connect(self._on_save)
        button_layout.addWidget(save_button)
        
        layout.addLayout(button_layout)
    
    def _load_settings(self):
        """Load current settings."""
        # Email (not from env, show stored value)
        stored_email = self.config.get('site_username')
        if stored_email:
            self.email_input.setText(stored_email)
        
        # Password - don't show, but allow setting
        # (We can't retrieve from keyring/env for display)
        
        # Google Sheets ID
        sheets_id = self.config.google_sheets_id
        if sheets_id:
            self.sheets_id_input.setText(sheets_id)
        
        # Google email
        stored_google_email = self.config.get('google_sheets_email')
        if stored_google_email:
            self.sheets_email_input.setText(stored_google_email)
    
    def _on_save(self):
        """Save settings."""
        try:
            logger.info("Saving settings")
            print("[INFO] Saving settings...")
            
            # Save YouScan credentials
            email = self.email_input.text().strip()
            if email:
                logger.debug(f"Saving YouScan email: {email}")
                print(f"[DEBUG] Saving YouScan email: {email}")
                self.config.site_username = email
            
            password = self.password_input.text().strip()
            if password:
                logger.debug("Saving YouScan password")
                print("[DEBUG] Saving YouScan password")
                self.config.site_password = password
            
            # Save Google Sheets ID
            sheets_id = self.sheets_id_input.text().strip()
            if sheets_id:
                logger.debug(f"Saving Google Sheets ID: {sheets_id}")
                print(f"[DEBUG] Saving Google Sheets ID: {sheets_id}")
                self.config.google_sheets_id = sheets_id
            
            # Save Google credentials
            google_email = self.sheets_email_input.text().strip()
            if google_email:
                logger.debug(f"Saving Google email: {google_email}")
                print(f"[DEBUG] Saving Google email: {google_email}")
                self.config.google_sheets_email = google_email
            
            google_password = self.sheets_password_input.text().strip()
            if google_password:
                logger.debug("Saving Google password")
                print("[DEBUG] Saving Google password")
                self.config.google_sheets_password = google_password
            
            logger.info("Settings saved successfully")
            print("[INFO] Settings saved successfully")
            
            QMessageBox.information(
                self,
                "Settings Saved",
                "Settings have been saved successfully."
            )
            self.accept()
        except Exception as e:
            logger.exception("Error saving settings")
            print(f"[ERROR] Error saving settings: {str(e)}")
            import traceback
            traceback.print_exc()
            QMessageBox.critical(
                self,
                "Error",
                f"Failed to save settings:\n{str(e)}\n\nCheck console for details."
            )


