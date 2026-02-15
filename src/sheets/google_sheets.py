"""Google Sheets integration using gspread."""
import gspread
from google.oauth2.credentials import Credentials
from google.oauth2 import service_account
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from typing import List, Dict, Optional
import time
import logging
from ..database.models import ParsedEntry
from ..config import COLUMN_MAPPINGS, SOCIAL_NETWORK_OPTIONS, TAG_OPTIONS, get_column_mapping


class GoogleSheetsWriter:
    """Write data to Google Sheets."""
    
    SCOPES = ['https://www.googleapis.com/auth/spreadsheets']
    
    def __init__(self, spreadsheet_id: str, email: Optional[str] = None, password: Optional[str] = None):
        """
        Initialize Google Sheets writer.
        
        Args:
            spreadsheet_id: Google Sheets spreadsheet ID
            email: Google account email (for email/password auth)
            password: Google account password (for email/password auth)
        """
        self.spreadsheet_id = spreadsheet_id
        self.email = email
        self.password = password
        self.client: Optional[gspread.Client] = None
        self.spreadsheet: Optional[gspread.Spreadsheet] = None
    
    def connect(self):
        """Connect to Google Sheets."""
        try:
            from pathlib import Path
            creds_path = Path(__file__).parent / 'credentials.json'
            service_account_path = Path(__file__).parent / 'service_account.json'
            token_path = Path(__file__).parent / 'token.json'
            
            creds = None
            
            # Option 1: Try Service Account (simplest - no OAuth needed)
            if service_account_path.exists():
                creds = service_account.Credentials.from_service_account_file(
                    str(service_account_path),
                    scopes=self.SCOPES
                )
                self.client = gspread.authorize(creds)
                self.spreadsheet = self.client.open_by_key(self.spreadsheet_id)
                return
            
            # Option 2: Try OAuth with existing token
            if token_path.exists():
                creds = Credentials.from_authorized_user_file(str(token_path), self.SCOPES)
            
            # Option 3: Try OAuth flow if credentials.json exists
            if not creds or not creds.valid:
                if creds and creds.expired and creds.refresh_token:
                    creds.refresh(Request())
                elif creds_path.exists():
                    flow = InstalledAppFlow.from_client_secrets_file(str(creds_path), self.SCOPES)
                    creds = flow.run_local_server(port=0)
                else:
                    raise ValueError(
                        "No authentication method found.\n\n"
                        "Please use one of these options:\n"
                        "1. Service Account (recommended - no OAuth):\n"
                        "   - Create service account in Google Cloud Console\n"
                        "   - Download JSON key\n"
                        "   - Save as 'src/sheets/service_account.json'\n"
                        "   - Share your Google Sheet with the service account email\n\n"
                        "2. OAuth:\n"
                        "   - Set up OAuth credentials (credentials.json)\n"
                        "   - See TESTING_GUIDE.md for instructions"
                    )
            
            # Save token for future use (OAuth only)
            if token_path.parent.exists() and not isinstance(creds, service_account.Credentials):
                with open(token_path, 'w') as token:
                    token.write(creds.to_json())
            
            # Create gspread client
            self.client = gspread.authorize(creds)
            self.spreadsheet = self.client.open_by_key(self.spreadsheet_id)
            
        except Exception as e:
            raise ConnectionError(f"Failed to connect to Google Sheets: {e}")
    
    def get_sheet(self, sheet_name: str, create_if_missing: bool = True):
        """
        Get a specific sheet by name.
        
        Args:
            sheet_name: Name of the sheet
            create_if_missing: If True, create the sheet if it doesn't exist
        
        Returns:
            Worksheet object
        """
        if not self.spreadsheet:
            self.connect()
        
        try:
            return self.spreadsheet.worksheet(sheet_name)
        except gspread.exceptions.WorksheetNotFound:
            if create_if_missing:
                logger = logging.getLogger(__name__)
                logger.info(f"Sheet '{sheet_name}' not found, creating it...")
                return self.create_sheet(sheet_name)
            else:
                raise ValueError(f"Sheet '{sheet_name}' not found in spreadsheet")
    
    def create_sheet(self, sheet_name: str) -> 'gspread.Worksheet':
        """
        Create a new sheet with proper headers.
        
        Args:
            sheet_name: Name of the sheet to create
        
        Returns:
            Created Worksheet object
        """
        logger = logging.getLogger(__name__)
        
        try:
            # Create the sheet
            sheet = self.spreadsheet.add_worksheet(title=sheet_name, rows=1000, cols=10)
            logger.info(f"Created sheet '{sheet_name}'")
            
            # Get column mapping for this table
            column_mapping = get_column_mapping(sheet_name)
            
            # Create header row
            headers = []
            # Sort columns by column letter (A, B, C, ...)
            sorted_columns = sorted(column_mapping.items(), key=lambda x: x[1])
            for col_name, col_letter in sorted_columns:
                headers.append(col_name)
            
            # Write headers to first row
            if headers:
                sheet.update('A1', [headers])
                logger.info(f"Added headers to sheet '{sheet_name}': {headers}")
            
            return sheet
        except Exception as e:
            logger.error(f"Failed to create sheet '{sheet_name}': {e}")
            raise
    
    def find_last_row(self, sheet, start_row: int = 2) -> int:
        """Find the last non-empty row in a sheet."""
        try:
            # Get all values in the first column
            col_values = sheet.col_values(1)
            # Find last non-empty row
            for i in range(len(col_values), start_row - 1, -1):
                if col_values[i - 1]:
                    return i + 1
            return start_row
        except:
            return start_row
    
    def write_entries(
        self, 
        sheet_name: str, 
        entries: List[ParsedEntry], 
        start_row: Optional[int] = None,
        progress_callback: Optional[callable] = None
    ) -> Dict[str, any]:
        """
        Write entries to Google Sheets.
        
        Returns:
            Dict with 'success' (bool), 'written' (int), 'failed' (List[Dict])
        """
        if not entries:
            return {'success': True, 'written': 0, 'failed': []}
        
        # Initialize progress
        if progress_callback:
            progress_callback(0, len(entries), f"Preparing to write {len(entries)} entries to Google Sheets...")
        
        sheet = self.get_sheet(sheet_name, create_if_missing=True)
        column_mapping = get_column_mapping(sheet_name)
        
        # Determine start row
        if start_row is None:
            start_row = self.find_last_row(sheet)
        
        written = 0
        failed = []
        logger = logging.getLogger(__name__)
        
        # Prepare all rows for batch writing
        rows_to_write = []
        for entry in entries:
            row_data = self._entry_to_row_data(entry, sheet_name, column_mapping)
            # Convert row_data dict to list in column order (A, B, C, D, E, F, G)
            sorted_cols = sorted(row_data.items(), key=lambda x: x[0])
            row_values = [str(value) if value is not None else '' for _, value in sorted_cols]
            rows_to_write.append(row_values)
        
        # Write rows in batches to avoid rate limits
        # Google Sheets API allows up to 100 requests per 100 seconds per user
        # We'll write in batches of 5 rows with delays
        batch_size = 5
        delay_between_batches = 1.0  # 1 second delay between batches
        delay_between_retries = 2.0  # 2 seconds delay for retries
        
        for batch_start in range(0, len(rows_to_write), batch_size):
            batch_end = min(batch_start + batch_size, len(rows_to_write))
            batch_rows = rows_to_write[batch_start:batch_end]
            batch_entries = entries[batch_start:batch_end]
            
            # Try to write batch with retry logic
            max_retries = 3
            retry_count = 0
            batch_written = False
            
            while retry_count < max_retries and not batch_written:
                try:
                    # Write entire batch at once using range update (most efficient)
                    first_row_num = start_row + written
                    last_row_num = start_row + written + len(batch_rows) - 1
                    
                    # Get column range (e.g., A2:G6 for 5 rows)
                    first_col = sorted(column_mapping.values())[0] if column_mapping.values() else 'A'
                    last_col = sorted(column_mapping.values())[-1] if column_mapping.values() else 'G'
                    range_name = f"{first_col}{first_row_num}:{last_col}{last_row_num}"
                    
                    # Write entire batch at once (list of lists)
                    sheet.update(range_name, batch_rows, value_input_option='RAW')
                    
                    # All rows in batch written successfully
                    written += len(batch_rows)
                    batch_written = True
                    logger.info(f"Written batch: {len(batch_rows)} rows (total: {written}/{len(entries)})")
                    
                    # Update progress
                    if progress_callback:
                        progress_callback(written, len(entries), f"Writing to Google Sheets: {written}/{len(entries)} entries")
                    
                except Exception as e:
                    error_str = str(e)
                    # Check if it's a rate limit error (429)
                    if '429' in error_str or 'quota' in error_str.lower() or 'rate limit' in error_str.lower():
                        retry_count += 1
                        if retry_count < max_retries:
                            wait_time = delay_between_retries * (2 ** (retry_count - 1))  # Exponential backoff
                            logger.warning(f"Rate limit hit, waiting {wait_time:.1f}s before retry {retry_count}/{max_retries}")
                            time.sleep(wait_time)
                            continue
                        else:
                            # Max retries reached, write rows individually with delays
                            logger.warning(f"Batch write failed after {max_retries} retries, writing individually")
                            for idx, (row_values, entry) in enumerate(zip(batch_rows, batch_entries)):
                                individual_retry = 0
                                individual_written = False
                                
                                while individual_retry < 2 and not individual_written:
                                    try:
                                        row_num = start_row + written + idx
                                        first_col = sorted(column_mapping.values())[0] if column_mapping.values() else 'A'
                                        last_col = sorted(column_mapping.values())[-1] if column_mapping.values() else 'G'
                                        range_name = f"{first_col}{row_num}:{last_col}{row_num}"
                                        sheet.update(range_name, [row_values], value_input_option='RAW')
                                        written += 1
                                        individual_written = True
                                        
                                        # Update progress
                                        if progress_callback:
                                            progress_callback(written, len(entries), f"Writing to Google Sheets: {written}/{len(entries)} entries")
                                        
                                        time.sleep(0.5)  # Delay between individual writes
                                    except Exception as individual_error:
                                        individual_retry += 1
                                        if individual_retry < 2:
                                            time.sleep(1.0 * individual_retry)  # Exponential backoff
                                        else:
                                            failed.append({
                                                'entry': entry,
                                                'error': str(individual_error),
                                                'row': start_row + written + idx
                                            })
                            break
                    else:
                        # Non-rate-limit error, add to failed
                        for entry in batch_entries:
                            failed.append({
                                'entry': entry,
                                'error': error_str,
                                'row': start_row + written + len(failed)
                            })
                        break
            
            # Delay between batches to avoid rate limits
            if batch_end < len(rows_to_write):
                time.sleep(delay_between_batches)
        
        # Final progress update
        if progress_callback:
            if len(failed) == 0:
                progress_callback(len(entries), len(entries), f"Successfully wrote {written} entries to Google Sheets")
            else:
                progress_callback(written, len(entries), f"Wrote {written}/{len(entries)} entries ({len(failed)} failed)")
        
        return {
            'success': len(failed) == 0,
            'written': written,
            'failed': failed
        }
    
    def _entry_to_row_data(self, entry: ParsedEntry, sheet_name: str, column_mapping: Dict) -> Dict[str, str]:
        """Convert ParsedEntry to row data dictionary."""
        row_data = {}
        
        if sheet_name == 'Соцмережі 2025':
            # Extract month from date
            month_name = ''
            if entry.date:
                month_names_uk = [
                    '', 'Січень', 'Лютий', 'Березень', 'Квітень',
                    'Травень', 'Червень', 'Липень', 'Серпень',
                    'Вересень', 'Жовтень', 'Листопад', 'Грудень'
                ]
                month_name = month_names_uk[entry.date.month] if entry.date.month < len(month_names_uk) else ''
            
            row_data[column_mapping.get('Місяць', 'A')] = month_name
            row_data[column_mapping.get('Назва', 'B')] = entry.name or ''
            row_data[column_mapping.get('Хто це', 'C')] = entry.description or ''
            row_data[column_mapping.get('Тема', 'D')] = entry.tag or ''
            row_data[column_mapping.get('Соцмережа', 'E')] = entry.social_network or ''
            row_data[column_mapping.get('Лінк', 'F')] = entry.link or ''
            row_data[column_mapping.get('Примітки', 'G')] = entry.note or ''
        
        elif sheet_name == 'ЗМІ 2025':
            # Extract month from date
            month_name = ''
            if entry.date:
                month_names_uk = [
                    '', 'Січень', 'Лютий', 'Березень', 'Квітень',
                    'Травень', 'Червень', 'Липень', 'Серпень',
                    'Вересень', 'Жовтень', 'Листопад', 'Грудень'
                ]
                month_name = month_names_uk[entry.date.month] if entry.date.month < len(month_names_uk) else ''
            
            row_data[column_mapping.get('Місяць', 'A')] = month_name
            row_data[column_mapping.get('Медіа', 'B')] = entry.name or ''
            row_data[column_mapping.get('Тема', 'C')] = entry.tag or ''
            row_data[column_mapping.get('Лінк', 'D')] = entry.link or ''
            row_data[column_mapping.get('Примітки', 'E')] = entry.note or ''
        
        elif sheet_name == 'Вакансії':
            # Define when needed
            pass
        
        return row_data
    
    def get_dropdown_options(self, sheet_name: str, column: str) -> List[str]:
        """Get dropdown options from a column (for validation)."""
        # This would require reading data validation rules
        # For now, return predefined options
        if column == 'Соцмережа':
            return SOCIAL_NETWORK_OPTIONS
        elif column == 'Тема':
            return TAG_OPTIONS
        # Add other dropdowns as needed
        return []
    
    def validate_entry(self, entry: ParsedEntry, sheet_name: str) -> List[str]:
        """Validate entry against sheet dropdowns. Returns list of errors."""
        errors = []
        
        if sheet_name == 'Соцмережі 2025':
            # Validate social network
            if entry.social_network and entry.social_network not in SOCIAL_NETWORK_OPTIONS:
                errors.append(f"Social network '{entry.social_network}' not in dropdown options")
        
        return errors

