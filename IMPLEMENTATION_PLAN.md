# Implementation Plan

## Phase 1: Setup & Core Infrastructure

### 1.1 Environment Setup
- Create conda environment with Python 3.10+
- Install dependencies: playwright, google-api-python-client, PyQt6, etc.
- Set up project structure

### 1.2 Database Setup
- Create SQLite database
- Implement day tracker
- Create models for parsed data

### 1.3 Configuration Management
- Config file for:
  - Site credentials
  - Google Sheets spreadsheet ID
  - Table mappings (which social networks go to which table)
  - Default settings

## Phase 2: Web Scraping Core

### 2.1 Base Parser
- Playwright browser automation
- Login to site
- Navigate to data view
- Date picker interaction

### 2.2 Social Network Parser
- Detect social network type
- Parse user name
- Extract link (share button → copy link)
- Extract user description (@username click)
- Extract tags (first one)
- Extract notes

### 2.3 Date Handling
- Default: today to today
- User can select date range
- Parse day by day
- Track parsed dates in database

## Phase 3: Google Sheets Integration

### 3.1 Authentication
- OAuth 2.0 setup
- Token storage and refresh
- User-friendly auth flow

### 3.2 Data Writing
- Find target sheet
- Find last row (or user-specified row)
- Append data with proper formatting
- Handle column mapping

## Phase 4: User Interface

### 4.1 Main Window
- Table selector dropdown
- Date range picker
- Settings button
- Start parsing button
- Day tracker status indicator

### 4.2 Parsing Dialog
- Progress indicator
- Scrollable list of parsed items
- Preview data in table format
- Row number selector (optional)
- Submit/Cancel buttons

### 4.3 Settings Dialog
- Site credentials input
- Google Sheets connection
- Table mappings configuration
- Default date settings

## Phase 5: Day Tracker & Missing Days

### 5.1 Day Detection
- On startup, check database for parsed dates
- Compare with current date
- Identify missing days
- Show notification in UI

### 5.2 Auto-fill Option
- User can choose to fill missing days
- Parse each missing day sequentially
- Show progress for each day

## Technical Details

### Social Network Detection Logic
```python
SOCIAL_NETWORKS = {
    'facebook.com': 'Соцмережі 2025',
    'instagram.com': 'Соцмережі 2025',
    'twitter.com': 'Соцмережі 2025',
    'x.com': 'Соцмережі 2025',
    'linkedin.com': 'Соцмережі 2025',
    'youtube.com': 'Соцмережі 2025',
    't.me': 'Соцмережі 2025',
    'tiktok.com': 'Соцмережі 2025',
    'threads.net': 'Соцмережі 2025',
    'soundcloud.com': 'Соцмережі 2025',
}
# All others → 'ЗМІ 2025'
```

### Parsing Flow for Each Entry
1. Wait for entry to load
2. Extract user name from visible text
3. Click share icon
4. Click "Скопіювати посилання" → extract link
5. Detect social network from link
6. Click @username → extract description
7. Extract tags (first one if multiple)
8. Extract notes
9. Store in memory for preview

### Data Structure
```python
ParsedEntry = {
    'name': str,           # Назва
    'social_network': str,  # Соцмережа
    'tag': str,            # Тема (first tag or empty)
    'note': str,           # Примітки
    'link': str,           # Лінк
    'description': str,    # Хто це
    'date': date,          # Date of the entry
}
```

## Error Handling

1. **Network Errors:**
   - Retry with exponential backoff
   - Show user-friendly error messages

2. **Parsing Errors:**
   - Log which entry failed
   - Continue with next entry
   - Show summary at end

3. **Google Sheets Errors:**
   - Validate credentials before parsing
   - Handle rate limits
   - Retry failed writes

## User Experience Flow

1. **First Launch:**
   - Setup wizard:
     - Enter site credentials
     - Connect Google Sheets
     - Select default tables

2. **Daily Use:**
   - Open app
   - Check day tracker (shows if days missed)
   - Select table
   - Select date (default: today)
   - Click "Start Parsing"
   - Review parsed data
   - Select row (optional)
   - Click "Submit"

3. **Filling Missing Days:**
   - App shows notification: "3 days missed"
   - User clicks "Fill Missing Days"
   - App parses each day sequentially
   - Shows progress

