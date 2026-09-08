---
name: money-tracker-ui-testing
description: Run Money Tracker locally with isolated SQLite data and verify CSV import, charts, filters, and deletion through the browser.
---

# Setup
- Run from the repository root. Install `requirements-dev.txt` if dependencies are unavailable.
- Use `MONEY_TRACKER_DB=/tmp/<unique-test-name>.db uvicorn app.main:app --port 8000` so Clear all never touches the default user database. Confirm the file does not already exist when testing initial empty state.
- Open http://127.0.0.1:8000. No login is required. Chart.js is loaded from cdn.jsdelivr.net; verify CDN access before recording.

# UI testing
- Upload `sample_data/transactions.csv` with Choose CSV… and then Import.
- Import status disappears after six seconds; capture screenshots promptly.
- Date fields are native segmented browser inputs. Click month/day/year segments individually to type values; typing two-digit segments can auto-advance.
- Date filters affect cards, charts, and table. Category filters affect only the table, not cards/charts.
- Exercise Clear all cancellation before confirmation, then reload to verify persistence.
- Use disposable CSVs in /tmp for malformed-header and debit/credit scenarios.

## Devin Secrets Needed
None for local UI testing.
