# Setup Guide

## Prerequisites

1. **Conda** installed on your system
2. **Google Account** with access to the target spreadsheet
3. **YouScan.io account** credentials

## Step 1: Create Conda Environment

```bash
conda env create -f environment.yml
conda activate bcl-parser
```

## Step 2: Install Playwright Browsers

```bash
playwright install chromium
```

## Step 3: Configure Credentials

You have two options for setting credentials:

### Option A: Environment Variables (Recommended)

Create a `.env` file in the project root (or set system environment variables):

```bash
# Windows PowerShell
$env:YOUSCAN_EMAIL="your-email@example.com"
$env:YOUSCAN_PASSWORD="your-password"
$env:GOOGLE_SHEETS_EMAIL="your-google@gmail.com"
$env:GOOGLE_SHEETS_PASSWORD="your-password"
```

```bash
# Windows CMD
set YOUSCAN_EMAIL=your-email@example.com
set YOUSCAN_PASSWORD=your-password
set GOOGLE_SHEETS_EMAIL=your-google@gmail.com
set GOOGLE_SHEETS_PASSWORD=your-password
```

### Option B: Settings Dialog

Run the application and configure credentials in the Settings dialog.

## Step 4: Google Sheets Setup

### Get Spreadsheet ID

1. Open your Google Sheets spreadsheet
2. Look at the URL: `https://docs.google.com/spreadsheets/d/SPREADSHEET_ID/edit`
3. Copy the `SPREADSHEET_ID` part

### OAuth Setup (Recommended)

For Google Sheets, OAuth is the recommended authentication method:

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project (or select existing)
3. Enable **Google Sheets API**
4. Go to **Credentials** → **Create Credentials** → **OAuth client ID**
5. Choose **Desktop app**
6. Download the credentials JSON file
7. Save it as `src/sheets/credentials.json`

The first time you run the app, it will open a browser for OAuth authentication.

### Email/Password (Alternative)

If you prefer email/password authentication:
- Set `GOOGLE_SHEETS_EMAIL` and `GOOGLE_SHEETS_PASSWORD` environment variables
- Note: This may require additional setup depending on your Google account security settings

## Step 5: Verify Sheet Structure

Make sure your Google Sheets have the correct structure:

### Соцмережі 2025
- Column A: (Month - optional)
- Column B: Назва (Name)
- Column C: Хто це (Who is this)
- Column D: Тема (Topic/Tag)
- Column E: Соцмережа (Social Network)
- Column F: Лінк (Link)
- Column G: Примітки (Notes)

### ЗМІ 2025
- Column A: Місяць (Month)
- Column B: Медіа (Media)
- Column C: Тема (Topic)
- Column D: Лінк (Link)
- Column E: Примітки (Notes)

## Step 6: Run the Application

```bash
python src/main.py
```

Or if you're in the project root:

```bash
cd src
python main.py
```

## Troubleshooting

### "Failed to connect to YouScan.io"

- Check your credentials are correct
- Verify you have internet connection
- Try running with `headless=False` to see what's happening

### "Failed to connect to Google Sheets"

- Verify spreadsheet ID is correct
- Check OAuth credentials file exists (`src/sheets/credentials.json`)
- Ensure Google Sheets API is enabled in your Google Cloud project
- Check that your Google account has access to the spreadsheet

### "Sheet not found"

- Verify the sheet name exactly matches (case-sensitive)
- Check that the sheet exists in your spreadsheet

### Date Picker Issues

If the date picker doesn't work automatically:
- The parser will try to set dates, but you may need to set them manually in the browser
- Run with `headless=False` to see and interact with the browser

## Next Steps

1. Test with a small date range first
2. Verify data appears correctly in Google Sheets
3. Check that tags and social networks match dropdown options
4. Use the day tracker to identify missing days

