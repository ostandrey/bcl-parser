"""Google Sheets integration using gspread."""
import gspread
from google.oauth2.credentials import Credentials
from google.oauth2 import service_account
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from typing import List, Dict, Optional
from ..database.models import ParsedEntry
from ..config import COLUMN_MAPPINGS, SOCIAL_NETWORK_OPTIONS


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
    
    def get_sheet(self, sheet_name: str):
        """Get a specific sheet by name."""
        if not self.spreadsheet:
            self.connect()
        
        try:
            return self.spreadsheet.worksheet(sheet_name)
        except gspread.exceptions.WorksheetNotFound:
            raise ValueError(f"Sheet '{sheet_name}' not found in spreadsheet")
    
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
        start_row: Optional[int] = None
    ) -> Dict[str, any]:
        """
        Write entries to Google Sheets.
        
        Returns:
            Dict with 'success' (bool), 'written' (int), 'failed' (List[Dict])
        """
        if not entries:
            return {'success': True, 'written': 0, 'failed': []}
        
        sheet = self.get_sheet(sheet_name)
        column_mapping = COLUMN_MAPPINGS.get(sheet_name, {})
        
        # Determine start row
        if start_row is None:
            start_row = self.find_last_row(sheet)
        
        written = 0
        failed = []
        
        for idx, entry in enumerate(entries):
            try:
                row_num = start_row + idx
                row_data = self._entry_to_row_data(entry, sheet_name, column_mapping)
                
                # Write row using update_cell for individual cells (more reliable)
                # Sort columns to write in order (A, B, C, D, E, F, G)
                sorted_cols = sorted(row_data.items(), key=lambda x: x[0])
                
                for col_letter, value in sorted_cols:
                    try:
                        # Validate col_letter is a single letter (A-Z)
                        if not col_letter or len(col_letter) != 1 or not col_letter.isalpha():
                            raise ValueError(f"Invalid column letter: {col_letter}")
                        
                        # Use update_cell(row, col, value) where col is 1-indexed
                        # Convert column letter to number (A=1, B=2, etc.)
                        col_num = ord(col_letter.upper()) - ord('A') + 1
                        # Ensure value is a string and not None
                        cell_value = str(value) if value is not None else ''
                        sheet.update_cell(row_num, col_num, cell_value)
                    except Exception as cell_error:
                        # Fallback: use range notation with proper format
                        # Double-check we have a valid cell reference
                        if col_letter and len(col_letter) == 1 and col_letter.isalpha():
                            cell_range = f"{col_letter}{row_num}"
                            cell_value = str(value) if value is not None else ''
                            # Use proper gspread update format: range, values (list of lists)
                            sheet.update(cell_range, [[cell_value]], value_input_option='RAW')
                        else:
                            raise ValueError(f"Invalid column letter for fallback: {col_letter}")
                
                written += 1
                
            except Exception as e:
                failed.append({
                    'entry': entry,
                    'error': str(e),
                    'row': start_row + idx
                })
        
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

