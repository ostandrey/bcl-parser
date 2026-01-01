# Recommendations & Thoughts

## Technology Choices - Final Recommendation

### ✅ **Desktop App with PyQt6** (Recommended)

**Why:**
- **Native Windows experience** - Feels like a real Windows application
- **No server setup** - Just run the .exe file
- **Single executable** - Can be packaged with PyInstaller
- **Better performance** - No web server overhead
- **Offline capable** - Works without network (except for parsing and Google Sheets)

**Alternative considered:** Local web app (Flask/FastAPI)
- ❌ Requires running a server command
- ❌ Less native feel
- ✅ Easier to style with CSS
- ✅ Can be accessed from other devices on network

**Decision: Desktop app wins** because you want to "start it locally, but without any scripts"

### ✅ **Playwright** (Recommended over Selenium)

**Why:**
- Better handling of modern JavaScript-heavy sites
- More reliable waiting for elements
- Better performance
- Easier to use API

### ✅ **SQLite** (Perfect choice)

**Why:**
- No server needed
- Fast and lightweight
- Perfect for local tracking
- Built into Python

## Architecture Decisions

### 1. **Social Network Detection**

**Approach:** Parse the link first, then determine table
- Extract link from share button
- Check domain against mapping
- Route to appropriate table

**Edge cases handled:**
- Multiple tags → use first one
- Missing data → empty field
- Unknown social network → route to "ЗМІ 2025"

### 2. **Date Parsing Strategy**

**Day-by-day parsing:**
- Parse one day at a time
- Track each day in database
- Show progress per day
- Allow user to fill missing days

**Default behavior:**
- Start with today (01.01.2026 to 01.01.2026)
- User can change date range
- Parse all days in range sequentially

### 3. **Data Preview & Submission**

**Two-stage process:**
1. **Parse stage:** Collect all data, show in preview
2. **Submit stage:** User reviews, optionally selects row, submits

**Benefits:**
- User can verify data before writing
- Can cancel if something looks wrong
- Can choose insertion point
- Better error handling

### 4. **Day Tracker Implementation**

**On startup:**
- Check database for parsed dates
- Compare with current date
- Show notification: "3 days missed since last parse"
- Offer to fill missing days

**Missing day filling:**
- User clicks "Fill Missing Days"
- App parses each missing day
- Shows progress
- Updates database after each day

## UI/UX Recommendations

### Main Window Layout

```
┌─────────────────────────────────────────┐
│  BCL Parser                    [⚙️]     │
├─────────────────────────────────────────┤
│                                         │
│  Table: [Соцмережі 2025 ▼]            │
│                                         │
│  Date Range:                            │
│  From: [01.01.2026]  To: [01.01.2026]  │
│                                         │
│  Status: ✅ All days parsed             │
│  ⚠️ 3 days missed (click to fill)      │
│                                         │
│  [Start Parsing]                        │
│                                         │
└─────────────────────────────────────────┘
```

### Parsing Dialog

```
┌─────────────────────────────────────────┐
│  Parsing Data...                        │
├─────────────────────────────────────────┤
│  Progress: ████████░░ 80%              │
│  Current: Parsing entry 8 of 10        │
│                                         │
│  Parsed Items (10):                     │
│  ┌───────────────────────────────────┐ │
│  │ Name        │ Network │ Tag        │ │
│  ├───────────────────────────────────┤ │
│  │ urban reform│ Instagram│Активні...│ │
│  │ skateukraine│ Instagram│Активні...│ │
│  │ ...         │ ...      │ ...       │ │
│  └───────────────────────────────────┘ │
│                                         │
│  Insert at row: [Auto ▼] or [Custom:__]│
│                                         │
│  [Cancel]              [Submit to Sheet]│
└─────────────────────────────────────────┘
```

## Implementation Challenges & Solutions

### Challenge 1: Dynamic Content Loading
**Problem:** Site may load content dynamically with JavaScript
**Solution:** Use Playwright's wait strategies
- Wait for specific selectors
- Wait for network idle
- Retry with timeouts

### Challenge 2: Google Sheets Rate Limits
**Problem:** Google Sheets API has rate limits
**Solution:**
- Batch writes when possible
- Implement exponential backoff
- Show progress to user
- Cache data locally if write fails

### Challenge 3: Site Structure Changes
**Problem:** Website structure may change, breaking parser
**Solution:**
- Use flexible selectors (multiple strategies)
- Log errors with context
- Allow manual data entry as fallback
- Version parser logic

### Challenge 4: Credential Security
**Problem:** Need to store site and Google credentials securely
**Solution:**
- Use `keyring` library for passwords
- Store OAuth tokens securely
- Never log credentials
- Encrypt sensitive config

## Development Phases

### Phase 1: MVP (Minimum Viable Product)
- Basic parsing for one table
- Simple date selection
- Google Sheets write
- Basic UI

### Phase 2: Full Features
- All three tables
- Day tracker
- Missing day filling
- Data preview

### Phase 3: Polish
- Error handling
- Progress indicators
- Settings management
- Logging

### Phase 4: Packaging
- Create .exe with PyInstaller
- User documentation
- Installation guide

## Questions to Consider

1. **Site URL:** What's the URL of the site to parse? (needed for implementation)

2. **Authentication:** How does site login work?
   - Username/password form?
   - OAuth?
   - Session-based?

3. **Data Structure:** 
   - How many entries per day typically?
   - Are entries paginated?
   - Any filters needed?

4. **Google Sheets:**
   - Do you have the spreadsheet ID?
   - Are column headers fixed?
   - Any data validation needed?

5. **Error Handling:**
   - What should happen if parsing fails for one entry?
   - Continue or stop?
   - Retry logic?

## Next Steps

1. **Get site details** - URL, login method, page structure
2. **Set up development environment** - Conda, install dependencies
3. **Create basic parser** - Test with one entry
4. **Build UI skeleton** - Main window, basic controls
5. **Integrate Google Sheets** - Test writing data
6. **Add day tracker** - Database operations
7. **Polish and test** - Error handling, edge cases

## Estimated Development Time

- **Setup & Infrastructure:** 2-3 hours
- **Base Parser:** 4-6 hours
- **Google Sheets Integration:** 2-3 hours
- **UI Development:** 4-6 hours
- **Day Tracker:** 2-3 hours
- **Testing & Polish:** 3-4 hours

**Total: ~20-25 hours** for a complete, polished application

