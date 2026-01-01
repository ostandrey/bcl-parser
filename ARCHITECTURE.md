# BCL Parser - Architecture Overview

## Technology Stack

### Core Technologies
- **Python 3.10+** (managed with conda)
- **Playwright** - Modern web automation (better than Selenium for modern sites)
- **Google Sheets API** - Write data to Google Sheets
- **SQLite** - Local database for caching and day tracking
- **PyQt6** - Desktop GUI framework

### Why These Choices?

1. **Playwright vs Selenium**
   - Better performance and reliability
   - Better handling of modern JavaScript-heavy sites
   - Easier to wait for elements

2. **SQLite**
   - Perfect for local storage
   - No server needed
   - Can track parsed dates, cache data
   - Lightweight and fast

3. **PyQt6**
   - Native Windows look and feel
   - Professional UI components
   - Can be packaged as single .exe
   - Better than tkinter for complex UIs

## Project Structure

```
bcl-parser/
├── src/
│   ├── main.py                 # Entry point
│   ├── gui/
│   │   ├── main_window.py      # Main UI window
│   │   ├── parser_dialog.py    # Parsing progress dialog
│   │   └── date_picker.py       # Date range selector
│   ├── parser/
│   │   ├── base_parser.py       # Base parser class
│   │   ├── social_parser.py     # Social networks parser
│   │   └── media_parser.py      # Media parser
│   ├── sheets/
│   │   ├── google_sheets.py     # Google Sheets API wrapper
│   │   └── credentials.json    # OAuth credentials (user provides)
│   ├── database/
│   │   ├── db_manager.py       # SQLite operations
│   │   └── models.py            # Database models
│   └── utils/
│       ├── config.py            # Configuration management
│       └── date_tracker.py     # Day tracking logic
├── requirements.txt
├── environment.yml             # Conda environment
└── README.md
```

## Key Features Implementation

### 1. Social Network Detection
- Parse social network from URL or page content
- Map to table:
  - Facebook, Instagram, Twitter, LinkedIn, YouTube, Telegram, TikTok, threads.net, soundcloud → "Соцмережі 2025"
  - Others → "ЗМІ 2025"

### 2. Data Parsing Flow
1. User selects date range (default: today to today)
2. Click date picker on site
3. Select date range
4. Parse each entry:
   - User name (Назва)
   - Social network (Соцмережа)
   - Tag (Тема) - first one if multiple
   - Note (Примітки)
   - Link (Лінк) - click share → "Скопіювати посилання"
   - User description (Хто це) - click @username → copy text

### 3. Day Tracker
- SQLite table: `parsed_dates`
- Track which dates have been parsed
- On startup, check for missing days
- Show notification in UI
- Option to fill missing days

### 4. User Interface Flow
1. **Main Window:**
   - Table selection (Соцмережі 2025, ЗМІ 2025, Вакансії)
   - Date range picker
   - Start parsing button
   - Settings (Google Sheets credentials, site credentials)

2. **Parsing Dialog:**
   - Show list of parsed items
   - Scrollable list
   - Preview data before submitting
   - Submit/Cancel buttons
   - Option to select row number for insertion

3. **Progress Indicator:**
   - Show current item being parsed
   - Progress bar
   - Estimated time remaining

## Database Schema

```sql
-- Track parsed dates
CREATE TABLE parsed_dates (
    id INTEGER PRIMARY KEY,
    table_name TEXT NOT NULL,
    date DATE NOT NULL,
    parsed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(table_name, date)
);

-- Cache parsed data (optional, for review before submission)
CREATE TABLE parsed_cache (
    id INTEGER PRIMARY KEY,
    table_name TEXT NOT NULL,
    data_json TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

## Google Sheets Integration

1. **Authentication:**
   - OAuth 2.0 flow
   - Store credentials securely
   - Refresh token handling

2. **Writing Data:**
   - Use Google Sheets API v4
   - Find last row in target sheet
   - Append data (or insert at specified row)
   - Handle rate limits

## Security Considerations

1. **Credentials Storage:**
   - Encrypt site credentials
   - Store Google OAuth tokens securely
   - Use keyring for sensitive data

2. **Error Handling:**
   - Retry logic for network issues
   - Graceful degradation
   - Log errors for debugging

## Next Steps

1. Set up conda environment
2. Create basic GUI structure
3. Implement base parser with Playwright
4. Add Google Sheets integration
5. Implement day tracker
6. Add data preview and submission flow

