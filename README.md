# BCL Parser

A desktop application for parsing social media and media data from a website and automatically populating Google Sheets.

## Features

- **Multi-table Support**: Parse data into different Google Sheets tables (Media, Vacancies, Social Networks)
- **Smart Routing**: Automatically routes data to correct table based on social network type
- **Date Tracking**: Tracks parsed dates and alerts about missing days
- **Flexible Date Selection**: Parse single days or date ranges
- **Data Preview**: Review parsed data before submitting to Google Sheets
- **Custom Row Insertion**: Choose where to insert data in the sheet

## Technology Stack

- **Python 3.10+** (Conda)
- **Playwright** - Web automation
- **Google Sheets API** - Data writing
- **PyQt6** - Desktop GUI
- **SQLite** - Local database for tracking

## Setup

### 1. Create Conda Environment

This will automatically install all dependencies from `requirements.txt`:

```bash
conda env create -f environment.yml
conda activate bcl-parser
```

### 2. Install Playwright Browsers

```bash
playwright install chromium
```

### 3. Configure Google Sheets API

**Choose one method:**

**Option A: OAuth (Recommended if you have Google account access)**
- See [OAUTH_SETUP.md](OAUTH_SETUP.md) for step-by-step guide
- One-time browser login, then works automatically

**Option B: Service Account (No browser login)**
- See [SERVICE_ACCOUNT_SETUP.md](SERVICE_ACCOUNT_SETUP.md) for step-by-step guide
- Download JSON key, share sheet with service account email

### 4. Configure Application

1. Run the application
2. Enter site credentials in Settings
3. Connect Google Sheets account
4. Configure table mappings

## Usage

1. Select target table (Соцмережі 2025, ЗМІ 2025, or Вакансії)
2. Select date range (default: today)
3. Click "Start Parsing"
4. Review parsed data in the preview dialog
5. Optionally select row number for insertion
6. Click "Submit" to write to Google Sheets

## Project Structure

```
bcl-parser/
├── src/
│   ├── main.py              # Entry point
│   ├── gui/                 # UI components
│   ├── parser/              # Web scraping logic
│   ├── sheets/              # Google Sheets integration
│   ├── database/            # SQLite operations
│   └── utils/               # Utilities
├── requirements.txt
├── environment.yml
└── README.md
```

## Development

See `ARCHITECTURE.md` and `IMPLEMENTATION_PLAN.md` for detailed documentation.

