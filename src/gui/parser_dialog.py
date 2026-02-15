"""Parsing dialog with preview and error handling."""
import logging
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton,
    QTableWidget, QTableWidgetItem, QLabel, QProgressBar,
    QMessageBox, QSpinBox, QCheckBox, QTextEdit, QLineEdit, QFileDialog, QWidget
)
from PyQt6.QtCore import Qt, QThread
from PyQt6.QtCore import pyqtSignal
from typing import List, Optional, Dict
from datetime import date
from ..database.models import ParsedEntry
from ..parser.youscan_parser import YouScanParser
from ..sheets.google_sheets import GoogleSheetsWriter
from ..config import Config
from ..database.db_manager import DatabaseManager
from ..utils.date_tracker import DateTracker
from ..export.excel_exporter import export_entries_to_xlsx

logger = logging.getLogger(__name__)


class ParsingThread(QThread):
    """Thread for parsing to avoid blocking UI."""
    progress = pyqtSignal(int, int, str)  # current, total, message
    entry_parsed = pyqtSignal(object)  # ParsedEntry
    finished = pyqtSignal(list, list)  # entries, errors
    error = pyqtSignal(str, object)  # error message, entry
    
    def __init__(
        self, 
        parser: YouScanParser,
        dates: List[date],
        table_name: str
    ):
        super().__init__()
        self.parser = parser
        self.dates = dates
        self.table_name = table_name
        self.entries = []
        self.errors = []
        self._stop_requested = False
    
    def run(self):
        """Run parsing in thread."""
        import asyncio
        import logging
        logger = logging.getLogger(__name__)
        
        # Create new event loop for this thread
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            # Run async parsing
            loop.run_until_complete(self._run_async())
        finally:
            loop.close()
    
    async def _run_async(self):
        """Async parsing logic."""
        import logging
        logger = logging.getLogger(__name__)
        
        # Start browser in async mode
        try:
            logger.info("Starting browser in async mode...")
            print("[INFO] Starting browser in async mode...")
            await self.parser.start_async()
            logger.info("Browser started successfully")
            print("[INFO] Browser started successfully")
        except Exception as e:
            logger.exception("Failed to start browser")
            print(f"[ERROR] Failed to start browser: {str(e)}")
            import traceback
            traceback.print_exc()
            self.errors.append({'date': None, 'error': f"Failed to start browser: {str(e)}", 'entry': None})
            self.finished.emit(self.entries, self.errors)
            return
        
        try:
            total_days = len(self.dates)
            logger.info(f"Starting to parse {total_days} day(s)")
            print(f"[INFO] Starting to parse {total_days} day(s)")
            
            # Set the full date range once at the beginning
            # Get date_from (first date) and date_to (last date) from the dates list
            if self.dates:
                date_from = min(self.dates)
                date_to = max(self.dates)
                logger.info(f"Setting date range for full period: {date_from} to {date_to}")
                print(f"[INFO] Setting date range for full period: {date_from} to {date_to}")
                await self.parser.set_date_range_async(date_from, date_to)
            else:
                logger.warning("No dates to parse")
                print("[WARNING] No dates to parse")
            
            for day_idx, target_date in enumerate(self.dates):
                if self._stop_requested:
                    break
                
                self.progress.emit(day_idx + 1, total_days, f"Parsing {target_date}")
                logger.info(f"Parsing date: {target_date}")
                print(f"[INFO] Parsing date: {target_date}")
                
                try:
                    # Parse all entries for this day (date range already set above)
                    logger.info(f"Fetching entries for {target_date}")
                    print(f"[INFO] Fetching entries for {target_date}")
                    day_entries = await self.parser.parse_all_entries_async(target_date)
                    logger.info(f"Found {len(day_entries)} entries for {target_date}")
                    print(f"[INFO] Found {len(day_entries)} entries for {target_date}")
                    
                    for entry in day_entries:
                        if self._stop_requested:
                            break
                        # entry.table_name is already set by detect_table_from_entry() in parser
                        # Don't override it - let entries go to their automatically detected tables
                        self.entries.append(entry)
                        self.entry_parsed.emit(entry)
                    
                except Exception as e:
                    error_info = {
                        'date': target_date,
                        'error': str(e),
                        'entry': None
                    }
                    self.errors.append(error_info)
                    logger.exception(f"Error parsing {target_date}")
                    print(f"[ERROR] Error parsing {target_date}: {str(e)}")
                    import traceback
                    traceback.print_exc()
                    self.error.emit(f"Error parsing {target_date}: {str(e)}", None)
        finally:
            # Close browser
            try:
                logger.info("Closing browser...")
                print("[INFO] Closing browser...")
                await self.parser.close_async()
                logger.info("Browser closed")
                print("[INFO] Browser closed")
            except Exception as e:
                logger.warning(f"Error closing browser: {e}")
                print(f"[WARNING] Error closing browser: {e}")
        
        logger.info(f"Parsing finished. Total entries: {len(self.entries)}, Errors: {len(self.errors)}")
        print(f"[INFO] Parsing finished. Total entries: {len(self.entries)}, Errors: {len(self.errors)}")
        self.finished.emit(self.entries, self.errors)
    
    def stop(self):
        """Request to stop parsing."""
        self._stop_requested = True


class ParserDialog(QDialog):
    """Dialog for parsing with preview and submission."""
    
    def __init__(
        self,
        parent,
        config: Config,
        db_manager: DatabaseManager,
        date_tracker: DateTracker,
        table_name: str,
        date_from: date,
        date_to: date
    ):
        super().__init__(parent)
        self.config = config
        self.db_manager = db_manager
        self.date_tracker = date_tracker
        self.table_name = table_name
        self.date_from = date_from
        self.date_to = date_to
        
        self.entries: List[ParsedEntry] = []
        self.errors: List[Dict] = []
        self.parser: Optional[YouScanParser] = None
        self.parsing_thread: Optional[ParsingThread] = None
        self.table_checkboxes: Dict[str, QCheckBox] = {}  # {table_name: checkbox}
        
        self.setWindowTitle("Parsing Data")
        self.setMinimumSize(800, 600)
        self._init_ui()
    
    def _init_ui(self):
        """Initialize UI."""
        layout = QVBoxLayout()
        self.setLayout(layout)
        
        # Progress section
        progress_layout = QVBoxLayout()
        self.status_label = QLabel("Preparing to parse...")
        progress_layout.addWidget(self.status_label)
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        progress_layout.addWidget(self.progress_bar)
        
        layout.addLayout(progress_layout)
        
        # Parsed entries table
        table_label = QLabel("Parsed Entries:")
        layout.addWidget(table_label)
        
        self.entries_table = QTableWidget()
        self.entries_table.setColumnCount(7)
        self.entries_table.setHorizontalHeaderLabels([
            'Table', 'Name', 'Social Network', 'Tag', 'Link', 'Note', 'Description'
        ])
        self.entries_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        # Make table column wider
        self.entries_table.setColumnWidth(0, 150)
        layout.addWidget(self.entries_table)
        
        # Table selection section (shown after parsing)
        self.table_summary_label = QLabel("Tables to write:")
        self.table_summary_label.setVisible(False)
        layout.addWidget(self.table_summary_label)
        
        self.table_checkboxes_widget = QWidget()
        self.table_checkboxes_layout = QVBoxLayout()
        self.table_checkboxes_widget.setLayout(self.table_checkboxes_layout)
        self.table_checkboxes_widget.setVisible(False)
        layout.addWidget(self.table_checkboxes_widget)
        
        # Store table checkboxes
        self.table_checkboxes = {}  # {table_name: checkbox}
        
        # Errors section (collapsible)
        self.errors_checkbox = QCheckBox("Show Errors")
        self.errors_checkbox.setChecked(False)
        self.errors_checkbox.toggled.connect(self._toggle_errors)
        layout.addWidget(self.errors_checkbox)
        
        self.errors_text = QTextEdit()
        self.errors_text.setMaximumHeight(150)
        self.errors_text.setVisible(False)
        layout.addWidget(self.errors_text)
        
        # Options
        options_layout = QHBoxLayout()
        options_layout.addWidget(QLabel("Insert at row:"))
        
        self.row_spinbox = QSpinBox()
        self.row_spinbox.setMinimum(2)
        self.row_spinbox.setMaximum(100000)
        self.row_spinbox.setValue(0)  # 0 means auto (end of list)
        self.row_spinbox.setSpecialValueText("Auto (end of list)")
        options_layout.addWidget(self.row_spinbox)
        
        options_layout.addStretch()
        layout.addLayout(options_layout)

        # Offline export (Excel) options
        export_layout = QHBoxLayout()
        export_layout.addWidget(QLabel("Export path:"))

        self.export_path_input = QLineEdit()
        self.export_path_input.setPlaceholderText("Select a folder or file path for the Excel report...")
        self.export_path_input.setText(self.config.export_dir)
        export_layout.addWidget(self.export_path_input)

        self.browse_export_button = QPushButton("Browse…")
        self.browse_export_button.clicked.connect(self._on_browse_export_path)
        export_layout.addWidget(self.browse_export_button)

        layout.addLayout(export_layout)
        
        # Buttons
        button_layout = QHBoxLayout()
        
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.clicked.connect(self._on_cancel)
        button_layout.addWidget(self.cancel_button)
        
        self.export_button = QPushButton("Generate Excel report")
        self.export_button.setEnabled(False)
        self.export_button.clicked.connect(self._on_export_excel)
        button_layout.addWidget(self.export_button)

        self.submit_button = QPushButton("Submit to Google Sheets")
        self.submit_button.setEnabled(False)
        self.submit_button.clicked.connect(self._on_submit)
        button_layout.addWidget(self.submit_button)
        
        layout.addLayout(button_layout)
        
        # Start parsing
        self._start_parsing()
    
    def _start_parsing(self):
        """Start parsing process."""
        logger.info("Starting parsing process")
        # Get credentials
        email = self.config.site_username
        password = self.config.site_password
        
        logger.debug(f"Using email: {email}")
        print(f"[DEBUG] Starting parsing with email: {email}")
        
        if not email or not password:
            error_msg = "Please configure YouScan.io credentials in Settings."
            logger.error(error_msg)
            print(f"[ERROR] {error_msg}")
            QMessageBox.critical(
                self,
                "Missing Credentials",
                error_msg
            )
            self.reject()
            return
        
        # Initialize parser - will be started in thread with async
        try:
            logger.info("Initializing YouScan parser")
            print("[INFO] Initializing YouScan parser...")
            # Use persistent context to save cookies/session (helps avoid detection)
            self.parser = YouScanParser(email, password, headless=False, use_persistent_context=True)
            logger.info("Parser initialized (will start browser in thread)")
            print("[INFO] Parser initialized (will start browser in thread)")
        except Exception as e:
            error_msg = f"Failed to initialize parser:\n{str(e)}"
            logger.exception("Initialization error")
            print(f"[ERROR] {error_msg}")
            import traceback
            traceback.print_exc()
            QMessageBox.critical(
                self,
                "Initialization Error",
                error_msg
            )
            self.reject()
            return
        
        # Get date range
        from datetime import timedelta
        dates = []
        current = self.date_from
        while current <= self.date_to:
            dates.append(current)
            current += timedelta(days=1)
        
        # Start parsing thread (browser will be started in thread using async)
        self.parsing_thread = ParsingThread(self.parser, dates, self.table_name)
        self.parsing_thread.progress.connect(self._on_progress)
        self.parsing_thread.entry_parsed.connect(self._on_entry_parsed)
        self.parsing_thread.finished.connect(self._on_parsing_finished)
        self.parsing_thread.error.connect(self._on_parsing_error)
        self.parsing_thread.start()
    
    def _on_progress(self, current: int, total: int, message: str):
        """Update progress."""
        self.status_label.setText(message)
        self.progress_bar.setValue(int((current / total) * 100))
    
    def _on_entry_parsed(self, entry: ParsedEntry):
        """Add parsed entry to table."""
        self.entries.append(entry)
        
        # Log parsed entry
        logger.info(f"Parsed entry: {entry.name} - {entry.social_network}")
        print(f"[PARSED] Name: {entry.name}")
        print(f"         Social Network: {entry.social_network}")
        print(f"         Tag: {entry.tag}")
        print(f"         Link: {entry.link}")
        print(f"         Note: {entry.note[:50]}..." if len(entry.note) > 50 else f"         Note: {entry.note}")
        print(f"         Description: {entry.description}")
        print("-" * 60)
        
        row = self.entries_table.rowCount()
        self.entries_table.insertRow(row)
        
        # Column 0: Table name
        table_name = entry.table_name or 'ЗМІ 2025'
        self.entries_table.setItem(row, 0, QTableWidgetItem(table_name))
        
        # Column 1: Name
        self.entries_table.setItem(row, 1, QTableWidgetItem(entry.name or ''))
        # Column 2: Social Network
        self.entries_table.setItem(row, 2, QTableWidgetItem(entry.social_network or ''))
        # Column 3: Tag
        self.entries_table.setItem(row, 3, QTableWidgetItem(entry.tag or ''))
        # Column 4: Link
        self.entries_table.setItem(row, 4, QTableWidgetItem(entry.link or ''))
        # Column 5: Note
        self.entries_table.setItem(row, 5, QTableWidgetItem(entry.note[:100] + '...' if len(entry.note) > 100 else entry.note))
        # Column 6: Description
        self.entries_table.setItem(row, 6, QTableWidgetItem(entry.description or ''))
        
        # Auto-scroll to bottom
        self.entries_table.scrollToBottom()
    
    def _on_parsing_finished(self, entries: List[ParsedEntry], errors: List[Dict]):
        """Handle parsing completion."""
        self.entries = entries
        self.errors = errors
        
        self.status_label.setText(f"Parsing complete: {len(entries)} entries, {len(errors)} errors")
        self.progress_bar.setValue(100)
        
        # Group entries by table and show table selection
        from collections import defaultdict
        entries_by_table = defaultdict(list)
        for entry in entries:
            table_name = entry.table_name or 'ЗМІ 2025'
            entries_by_table[table_name].append(entry)
        
        # Update table selection UI
        self._update_table_selection(entries_by_table)
        
        # Show errors if any
        if errors:
            error_text = "\n".join([
                f"Date {err.get('date', 'Unknown')}: {err.get('error', 'Unknown error')}"
                for err in errors
            ])
            self.errors_text.setPlainText(error_text)
            self.errors_checkbox.setChecked(True)
            self.errors_text.setVisible(True)
        
        # Enable submit button
        self.submit_button.setEnabled(len(entries) > 0)
        self.export_button.setEnabled(len(entries) > 0)
        self.cancel_button.setText("Close")
    
    def _update_table_selection(self, entries_by_table: Dict[str, List[ParsedEntry]]):
        """Update table selection UI with checkboxes for each table."""
        # Clear existing checkboxes
        for checkbox in self.table_checkboxes.values():
            self.table_checkboxes_layout.removeWidget(checkbox)
            checkbox.deleteLater()
        self.table_checkboxes.clear()
        
        # Create checkboxes for each table
        for table_name, table_entries in entries_by_table.items():
            checkbox = QCheckBox(f"{table_name} ({len(table_entries)} entries)")
            checkbox.setChecked(True)  # Checked by default
            self.table_checkboxes_layout.addWidget(checkbox)
            self.table_checkboxes[table_name] = checkbox
        
        # Show the table selection UI if there are tables
        if entries_by_table:
            self.table_summary_label.setVisible(True)
            self.table_checkboxes_widget.setVisible(True)
        else:
            self.table_summary_label.setVisible(False)
            self.table_checkboxes_widget.setVisible(False)

    def _on_browse_export_path(self):
        """Select export directory (or file path)."""
        # Prefer selecting a directory; user can still type filename manually.
        start_dir = self.export_path_input.text().strip() or self.config.export_dir
        directory = QFileDialog.getExistingDirectory(self, "Select export folder", start_dir)
        if directory:
            self.export_path_input.setText(directory)
            self.config.export_dir = directory

    def _on_export_excel(self):
        """Generate Excel report locally (offline)."""
        if not self.entries:
            QMessageBox.warning(self, "No Data", "No entries to export.")
            return

        base = self.export_path_input.text().strip() or self.config.export_dir
        if not base:
            QMessageBox.warning(self, "Missing Path", "Please choose an export folder.")
            return

        # Build a default filename if user provided a folder
        from pathlib import Path
        safe_table = (self.table_name or "report").replace("/", "_").replace("\\", "_")
        filename = f"{safe_table}_{self.date_from.isoformat()}_{self.date_to.isoformat()}.xlsx"
        out_path = Path(base)
        if out_path.suffix.lower() != ".xlsx":
            out_path = out_path / filename

        self.config.export_dir = str(Path(base))

        class ExcelExportThread(QThread):
            progress = pyqtSignal(int, int, str)
            finished = pyqtSignal(str)
            failed = pyqtSignal(str)

            def __init__(self, entries, output_path):
                super().__init__()
                self._entries = entries
                self._output_path = output_path

            def run(self):
                try:
                    def cb(current, total, message):
                        self.progress.emit(current, total, message)

                    out = export_entries_to_xlsx(self._entries, self._output_path, progress_callback=cb)
                    self.finished.emit(str(out))
                except Exception as e:
                    self.failed.emit(str(e))

        # Disable buttons while exporting
        self.export_button.setEnabled(False)
        self.submit_button.setEnabled(False)
        self.cancel_button.setEnabled(False)
        self.browse_export_button.setEnabled(False)

        self.progress_bar.setValue(0)
        self.status_label.setText("Generating Excel report...")

        self._excel_thread = ExcelExportThread(list(self.entries), str(out_path))
        self._excel_thread.progress.connect(self._on_progress)

        def on_done(path_str: str):
            self.progress_bar.setValue(100)
            self.status_label.setText(f"Excel saved: {path_str}")
            QMessageBox.information(self, "Excel exported", f"Report saved to:\n{path_str}")
            self.export_button.setEnabled(True)
            self.submit_button.setEnabled(True)
            self.cancel_button.setEnabled(True)
            self.browse_export_button.setEnabled(True)

        def on_fail(err: str):
            QMessageBox.critical(self, "Excel export failed", err)
            self.export_button.setEnabled(True)
            self.submit_button.setEnabled(True)
            self.cancel_button.setEnabled(True)
            self.browse_export_button.setEnabled(True)

        self._excel_thread.finished.connect(on_done)
        self._excel_thread.failed.connect(on_fail)
        self._excel_thread.start()
    
    def _on_parsing_error(self, message: str, entry: Optional[ParsedEntry]):
        """Handle parsing error."""
        # Errors are collected and shown at the end
        pass
    
    def _toggle_errors(self, checked: bool):
        """Toggle errors visibility."""
        self.errors_text.setVisible(checked)
    
    def _on_cancel(self):
        """Handle cancel button."""
        if self.parsing_thread and self.parsing_thread.isRunning():
            reply = QMessageBox.question(
                self,
                "Cancel Parsing?",
                "Parsing is in progress. Do you want to cancel?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.Yes:
                self.parsing_thread.stop()
                self.parsing_thread.wait()
                if self.parser:
                    self.parser.close()
                self.reject()
        else:
            if self.parser:
                self.parser.close()
            self.reject()
    
    def _on_submit(self):
        """Submit data to Google Sheets."""
        if not self.entries:
            QMessageBox.warning(self, "No Data", "No entries to submit.")
            return
        
        # Get Google Sheets credentials
        spreadsheet_id = self.config.google_sheets_id
        if not spreadsheet_id:
            QMessageBox.critical(
                self,
                "Missing Configuration",
                "Please configure Google Sheets ID in Settings."
            )
            return
        
        # Connect to Google Sheets
        try:
            sheets_writer = GoogleSheetsWriter(spreadsheet_id)
            sheets_writer.connect()
        except Exception as e:
            QMessageBox.critical(
                self,
                "Connection Error",
                f"Failed to connect to Google Sheets:\n{str(e)}\n\n"
                "Please check your credentials and spreadsheet ID."
            )
            return
        
        # Get start row
        start_row = self.row_spinbox.value()
        if start_row == 0:
            start_row = None  # Auto
        
        # Reset progress bar for writing
        self.progress_bar.setValue(0)
        self.status_label.setText("Writing to Google Sheets...")
        
        # Write entries with progress callback
        def update_progress(current, total, message):
            """Update progress bar for Google Sheets writing."""
            self.status_label.setText(message)
            if total > 0:
                self.progress_bar.setValue(int((current / total) * 100))
        
        try:
            # Group entries by their automatically detected table_name
            from collections import defaultdict
            entries_by_table = defaultdict(list)
            for entry in self.entries:
                table_name = entry.table_name or 'ЗМІ 2025'  # Fallback if not set
                entries_by_table[table_name].append(entry)
            
            # Filter by selected tables only
            selected_tables = {
                table_name for table_name, checkbox in self.table_checkboxes.items()
                if checkbox.isChecked()
            }
            
            if not selected_tables:
                QMessageBox.warning(
                    self,
                    "No Tables Selected",
                    "Please select at least one table to write to."
                )
                return
            
            # Write entries to each selected table separately
            total_written = 0
            total_failed = []
            results_by_table = {}
            
            for table_name, table_entries in entries_by_table.items():
                # Skip if table not selected
                if table_name not in selected_tables:
                    logger.info(f"Skipping table '{table_name}' (not selected)")
                    print(f"[WRITE] Skipping table '{table_name}' (not selected)")
                    continue
                logger.info(f"Writing {len(table_entries)} entries to table '{table_name}'")
                print(f"[WRITE] Writing {len(table_entries)} entries to table '{table_name}'")
                
                result = sheets_writer.write_entries(
                    table_name, 
                    table_entries, 
                    start_row, 
                    progress_callback=update_progress
                )
                results_by_table[table_name] = result
                total_written += result['written']
                # Add table name to failed entries for better error reporting
                for failed_entry in result['failed']:
                    failed_entry['table'] = table_name
                total_failed.extend(result['failed'])
                
                # Mark dates as parsed for this table
                if result['success']:
                    for entry in table_entries:
                        if entry.date:
                            self.db_manager.mark_date_parsed(table_name, entry.date)
            
            # Show summary
            if total_failed:
                failed_count = len(total_failed)
                reply = QMessageBox.question(
                    self,
                    "Partial Success",
                    f"Wrote {total_written} entries across {len(entries_by_table)} table(s), "
                    f"but {failed_count} failed.\n\n"
                    "Do you want to see error details?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                )
                
                if reply == QMessageBox.StandardButton.Yes:
                    # Show error details
                    error_details = "\n".join([
                        f"Table {err.get('table', 'unknown')}, Row {err.get('row', 'unknown')}: {err.get('error', 'unknown error')}"
                        for err in total_failed[:20]  # Limit to first 20 errors
                    ])
                    if len(total_failed) > 20:
                        error_details += f"\n... and {len(total_failed) - 20} more errors"
                    QMessageBox.warning(self, "Failed Entries", error_details)
            else:
                table_names = ", ".join(entries_by_table.keys())
                QMessageBox.information(
                    self,
                    "Success",
                    f"Successfully wrote {total_written} entries to {len(entries_by_table)} table(s):\n{table_names}"
                )
            
            self.accept()
        
        except Exception as e:
            reply = QMessageBox.question(
                self,
                "Error Writing to Sheets",
                f"Error occurred while writing to Google Sheets:\n{str(e)}\n\n"
                "Do you want to continue and try again?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            
            if reply == QMessageBox.StandardButton.No:
                # User chose to stop
                return

