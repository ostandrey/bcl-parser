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

            # Paths in the package directory (legacy / manual setup)
            sheets_dir            = Path(__file__).parent
            service_account_path  = sheets_dir / 'service_account.json'
            token_path            = sheets_dir / 'token.json'
            creds_path            = sheets_dir / 'credentials.json'

            # Standard gspread paths (~/.config/gspread/)
            gspread_dir           = Path.home() / '.config' / 'gspread'
            gspread_token         = gspread_dir / 'authorized_user.json'
            gspread_creds         = gspread_dir / 'credentials.json'

            creds = None

            # --- Option 1: Service Account JSON ----------------------------------
            for sa_path in (service_account_path, gspread_dir / 'service_account.json'):
                if sa_path.exists():
                    creds = service_account.Credentials.from_service_account_file(
                        str(sa_path), scopes=self.SCOPES
                    )
                    self.client = gspread.authorize(creds)
                    self.spreadsheet = self.client.open_by_key(self.spreadsheet_id)
                    return

            # --- Option 2: Existing OAuth token (token.json or gspread default) --
            for tp in (token_path, gspread_token):
                if tp.exists():
                    try:
                        creds = Credentials.from_authorized_user_file(str(tp), self.SCOPES)
                        if creds and creds.expired and creds.refresh_token:
                            creds.refresh(Request())
                            with open(tp, 'w') as f:
                                f.write(creds.to_json())
                        if creds and creds.valid:
                            self.client = gspread.authorize(creds)
                            self.spreadsheet = self.client.open_by_key(self.spreadsheet_id)
                            return
                    except Exception:
                        pass  # try next option

            # --- Option 3: gspread.oauth() – handles the full OAuth flow ---------
            for cp in (creds_path, gspread_creds):
                if cp.exists():
                    try:
                        # gspread.oauth opens a browser for consent if needed,
                        # then caches the token at gspread_token automatically.
                        gspread_dir.mkdir(parents=True, exist_ok=True)
                        self.client = gspread.oauth(
                            credentials_filename=str(cp),
                            authorized_user_filename=str(gspread_token),
                        )
                        self.spreadsheet = self.client.open_by_key(self.spreadsheet_id)
                        return
                    except Exception:
                        pass  # try next option

            # --- Nothing worked --------------------------------------------------
            raise ValueError(
                "Не знайдено жодного методу авторизації Google.\n\n"
                "Варіант 1 – Service Account (рекомендовано, без браузера):\n"
                "  • Створіть Service Account у Google Cloud Console\n"
                "  • Завантажте JSON-ключ\n"
                "  • Збережіть як  src/sheets/service_account.json\n"
                "  • Поділіться таблицею з email сервісного акаунта\n\n"
                "Варіант 2 – OAuth (потрібен браузер при першому запуску):\n"
                "  • Завантажте credentials.json з Google Cloud Console\n"
                "  • Збережіть як  ~/.config/gspread/credentials.json\n"
                "     або  src/sheets/credentials.json"
            )

        except Exception as e:
            raise ConnectionError(f"Failed to connect to Google Sheets: {e}")
    
    def get_sheet_names(self) -> list:
        """Return list of all worksheet titles in the spreadsheet."""
        if not self.spreadsheet:
            self.connect()
        return [ws.title for ws in self.spreadsheet.worksheets()]

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
    
    def _find_source_row(self, sheet, col_letter: str) -> Optional[int]:
        """Return 0-indexed row index of first data row with a value in col_letter. None if not found."""
        try:
            col_idx = ord(col_letter.upper()) - ord('A') + 1
            values = sheet.col_values(col_idx)
            for i, val in enumerate(values[1:], start=1):  # skip header
                if val and val.strip():
                    return i
        except Exception:
            pass
        return None

    def find_last_row(self, sheet, start_row: int = 2) -> int:
        """Find the last non-empty row in a sheet (checks all columns)."""
        try:
            all_values = sheet.get_all_values()
            for i in range(len(all_values) - 1, start_row - 2, -1):
                if any(cell.strip() for cell in all_values[i]):
                    return i + 2  # +1 for 1-based index, +1 for next empty row
            return start_row
        except Exception:
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
                    
                    # Write entire batch at once (USER_ENTERED so links become hyperlinks)
                    sheet.update(range_name, batch_rows, value_input_option='USER_ENTERED')
                    
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
                                        sheet.update(range_name, [row_values], value_input_option='USER_ENTERED')
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
        
        # Apply Montserrat font + copy data validation from row 2 to new rows
        if written > 0:
            col_count = len(column_mapping) if column_mapping else 7
            sheet_id  = sheet.id
            new_start = start_row - 1        # 0-indexed first new row
            new_end   = new_start + written  # 0-indexed exclusive

            try:
                first_col = sorted(column_mapping.values())[0] if column_mapping.values() else 'A'
                last_col  = sorted(column_mapping.values())[-1] if column_mapping.values() else 'G'
                fmt_range = f"{first_col}{start_row}:{last_col}{start_row + written - 1}"
                sheet.format(fmt_range, {'textFormat': {'fontFamily': 'Montserrat'}})
            except Exception as fmt_err:
                logger.warning(f"Could not apply Montserrat font: {fmt_err}")

            # Set actual hyperlinks on the Лінк column cells
            try:
                link_col = column_mapping.get('Лінк') or column_mapping.get('Лінк')
                if link_col:
                    link_col_idx = ord(link_col.upper()) - ord('A')
                    cell_updates = []
                    for i, entry in enumerate(entries):
                        url = entry.link or ''
                        if not url:
                            continue
                        cell_updates.append({
                            'updateCells': {
                                'rows': [{'values': [{
                                    'userEnteredValue': {'stringValue': url},
                                    'userEnteredFormat': {
                                        'textFormat': {
                                            'fontFamily': 'Montserrat',
                                            'link': {'uri': url},
                                            'foregroundColorStyle': {'rgbColor': {'red': 0.07, 'green': 0.36, 'blue': 0.78}},
                                            'underline': True,
                                        }
                                    },
                                }]}],
                                'fields': 'userEnteredValue,userEnteredFormat.textFormat',
                                'range': {
                                    'sheetId':        sheet_id,
                                    'startRowIndex':  new_start + i,
                                    'endRowIndex':    new_start + i + 1,
                                    'startColumnIndex': link_col_idx,
                                    'endColumnIndex':   link_col_idx + 1,
                                },
                            }
                        })
                    if cell_updates:
                        sheet.spreadsheet.batch_update({'requests': cell_updates})
            except Exception as link_err:
                logger.warning(f"Could not set hyperlinks: {link_err}")

            # Copy chip-style validation for Соцмережа and Тема
            for col_key, fallback_options in [
                ('Соцмережа', SOCIAL_NETWORK_OPTIONS),
                ('Тема',      TAG_OPTIONS),
            ]:
                col_letter = column_mapping.get(col_key)
                if not col_letter:
                    continue
                col_idx = ord(col_letter.upper()) - ord('A')

                src_row = self._find_source_row(sheet, col_letter)
                if src_row is not None:
                    # Copy chip-style from first existing data row
                    try:
                        sheet.spreadsheet.batch_update({'requests': [{
                            'copyPaste': {
                                'source': {
                                    'sheetId': sheet_id,
                                    'startRowIndex': src_row, 'endRowIndex': src_row + 1,
                                    'startColumnIndex': col_idx, 'endColumnIndex': col_idx + 1,
                                },
                                'destination': {
                                    'sheetId': sheet_id,
                                    'startRowIndex': new_start, 'endRowIndex': new_end,
                                    'startColumnIndex': col_idx, 'endColumnIndex': col_idx + 1,
                                },
                                'pasteType': 'PASTE_DATA_VALIDATION',
                                'pasteOrientation': 'NORMAL',
                            }
                        }]})
                        continue
                    except Exception as e:
                        logger.warning(f"copyPaste failed for {col_key}, falling back: {e}")

                # Fallback for new/empty sheets: setDataValidation (old style but functional)
                try:
                    sheet.spreadsheet.batch_update({'requests': [{
                        'setDataValidation': {
                            'range': {
                                'sheetId': sheet_id,
                                'startRowIndex':    new_start, 'endRowIndex': new_end,
                                'startColumnIndex': col_idx,   'endColumnIndex': col_idx + 1,
                            },
                            'rule': {
                                'condition': {
                                    'type':   'ONE_OF_LIST',
                                    'values': [{'userEnteredValue': v} for v in fallback_options],
                                },
                                'showCustomUi': True,
                                'strict':       False,
                            },
                        }
                    }]})
                except Exception as e:
                    logger.warning(f"Could not set validation for {col_key}: {e}")

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
    
    _MONTH_NAMES_UK = [
        '', 'Січень', 'Лютий', 'Березень', 'Квітень',
        'Травень', 'Червень', 'Липень', 'Серпень',
        'Вересень', 'Жовтень', 'Листопад', 'Грудень',
    ]

    def _entry_to_row_data(self, entry: ParsedEntry, sheet_name: str, column_mapping: Dict) -> Dict[str, str]:
        """Convert ParsedEntry to row data dictionary."""
        month_name = ''
        if entry.date and 0 < entry.date.month < len(self._MONTH_NAMES_UK):
            month_name = self._MONTH_NAMES_UK[entry.date.month]

        if 'Соцмережі' in sheet_name:
            return {
                column_mapping.get('Місяць',    'A'): month_name,
                column_mapping.get('Назва',      'B'): entry.name or '',
                column_mapping.get('Хто це',     'C'): entry.description or '',
                column_mapping.get('Тема',       'D'): entry.tag or '',
                column_mapping.get('Соцмережа',  'E'): entry.social_network or '',
                column_mapping.get('Лінк',       'F'): entry.link or '',
                column_mapping.get('Примітки',   'G'): entry.note or '',
            }

        if 'ЗМІ' in sheet_name:
            return {
                column_mapping.get('Місяць',   'A'): month_name,
                column_mapping.get('Медіа',    'B'): entry.name or '',
                column_mapping.get('Тема',     'C'): entry.tag or '',
                column_mapping.get('Лінк',     'D'): entry.link or '',
                column_mapping.get('Примітки', 'E'): entry.note or '',
            }

        return {}
    
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
        
        if 'Соцмережі' in sheet_name:
            if entry.social_network and entry.social_network not in SOCIAL_NETWORK_OPTIONS:
                errors.append(f"Social network '{entry.social_network}' not in dropdown options")
        
        return errors

